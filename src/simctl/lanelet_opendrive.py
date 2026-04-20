from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ensure_dir, load_yaml


Point = tuple[float, float, float]


@dataclass
class LaneletWay:
    way_id: str
    node_refs: list[str]
    tags: dict[str, str]


@dataclass
class LaneletRelation:
    relation_id: str
    left_way: str
    right_way: str
    tags: dict[str, str]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def float_attr(value: str | None, *, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def tag_payload(element: ET.Element) -> dict[str, str]:
    tags: dict[str, str] = {}
    for tag in element.findall("tag"):
        key = tag.attrib.get("k")
        value = tag.attrib.get("v")
        if key is not None and value is not None:
            tags[key] = value
    return tags


def parse_lanelet2(path: Path) -> dict[str, Any]:
    nodes: dict[str, Point] = {}
    ways: dict[str, LaneletWay] = {}
    lanelets: list[LaneletRelation] = []

    tree = ET.parse(path)
    root = tree.getroot()

    for node in root.findall("node"):
        node_id = node.attrib.get("id")
        if not node_id:
            continue
        tags = tag_payload(node)
        if "local_x" not in tags or "local_y" not in tags:
            continue
        nodes[node_id] = (
            float_attr(tags.get("local_x")),
            float_attr(tags.get("local_y")),
            float_attr(tags.get("ele")),
        )

    for way in root.findall("way"):
        way_id = way.attrib.get("id")
        if not way_id:
            continue
        node_refs = [nd.attrib["ref"] for nd in way.findall("nd") if nd.attrib.get("ref")]
        ways[way_id] = LaneletWay(way_id=way_id, node_refs=node_refs, tags=tag_payload(way))

    for relation in root.findall("relation"):
        relation_id = relation.attrib.get("id")
        if not relation_id:
            continue
        tags = tag_payload(relation)
        if tags.get("type") != "lanelet" or tags.get("subtype") != "road":
            continue
        left_way = ""
        right_way = ""
        for member in relation.findall("member"):
            if member.attrib.get("type") != "way":
                continue
            role = member.attrib.get("role")
            ref = member.attrib.get("ref", "")
            if role == "left":
                left_way = ref
            elif role == "right":
                right_way = ref
        if left_way and right_way:
            lanelets.append(LaneletRelation(relation_id=relation_id, left_way=left_way, right_way=right_way, tags=tags))

    return {"nodes": nodes, "ways": ways, "lanelets": lanelets}


def points_for_way(way: LaneletWay, nodes: dict[str, Point]) -> list[Point]:
    return [nodes[ref] for ref in way.node_refs if ref in nodes]


def distance_2d(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def polyline_length(points: list[Point]) -> float:
    return sum(distance_2d(a, b) for a, b in zip(points, points[1:]))


def resample_polyline(points: list[Point], sample_count: int) -> list[Point]:
    if not points:
        return []
    if len(points) == 1 or sample_count <= 1:
        return [points[0]]

    segments = [distance_2d(a, b) for a, b in zip(points, points[1:])]
    total = sum(segments)
    if total <= 1e-9:
        return [points[0] for _ in range(sample_count)]

    targets = [total * index / (sample_count - 1) for index in range(sample_count)]
    sampled: list[Point] = []
    segment_index = 0
    accumulated = 0.0
    for target in targets:
        while segment_index < len(segments) - 1 and accumulated + segments[segment_index] < target:
            accumulated += segments[segment_index]
            segment_index += 1
        start = points[segment_index]
        end = points[segment_index + 1]
        length = max(segments[segment_index], 1e-9)
        ratio = (target - accumulated) / length
        sampled.append(
            (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
                start[2] + (end[2] - start[2]) * ratio,
            )
        )
    return sampled


def mean_lane_width(left: list[Point], right: list[Point]) -> float:
    sample_count = max(2, min(20, max(len(left), len(right))))
    left_samples = resample_polyline(left, sample_count)
    right_samples = resample_polyline(right, sample_count)
    distances = [distance_2d(a, b) for a, b in zip(left_samples, right_samples)]
    distances = [distance for distance in distances if distance > 0.05]
    if not distances:
        return 3.5
    return sum(distances) / len(distances)


def reference_line(left: list[Point], right: list[Point], mode: str) -> list[Point]:
    if mode == "left":
        return left
    sample_count = max(2, min(40, max(len(left), len(right))))
    left_samples = resample_polyline(left, sample_count)
    right_samples = resample_polyline(right, sample_count)
    return [
        ((left_pt[0] + right_pt[0]) / 2, (left_pt[1] + right_pt[1]) / 2, (left_pt[2] + right_pt[2]) / 2)
        for left_pt, right_pt in zip(left_samples, right_samples)
    ]


def heading(a: Point, b: Point) -> float:
    return math.atan2(b[1] - a[1], b[0] - a[0])


def append_text(parent: ET.Element, tag: str, text: str) -> ET.Element:
    element = ET.SubElement(parent, tag)
    element.text = text
    return element


def fmt(value: float) -> str:
    return f"{value:.6f}"


def bbox(points: list[Point]) -> dict[str, float] | None:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    return {
        "west": min(xs),
        "east": max(xs),
        "south": min(ys),
        "north": max(ys),
        "min_z": min(zs),
        "max_z": max(zs),
    }


def road_type(speed_limit: str | None) -> ET.Element:
    element = ET.Element("type", {"s": "0.000000", "type": "town"})
    if speed_limit:
        ET.SubElement(element, "speed", {"max": str(speed_limit), "unit": "km/h"})
    return element


def add_plan_view(road: ET.Element, reference: list[Point]) -> tuple[float, int]:
    plan_view = ET.SubElement(road, "planView")
    road_length = 0.0
    segment_count = 0
    for start, end in zip(reference, reference[1:]):
        length = distance_2d(start, end)
        if length <= 0.01:
            continue
        geometry = ET.SubElement(
            plan_view,
            "geometry",
            {
                "s": fmt(road_length),
                "x": fmt(start[0]),
                "y": fmt(start[1]),
                "hdg": fmt(heading(start, end)),
                "length": fmt(length),
            },
        )
        ET.SubElement(geometry, "line")
        road_length += length
        segment_count += 1
    return road_length, segment_count


def add_lanes(road: ET.Element, width: float, lane_type: str) -> None:
    lanes = ET.SubElement(road, "lanes")
    section = ET.SubElement(lanes, "laneSection", {"s": "0.000000"})
    center = ET.SubElement(section, "center")
    center_lane = ET.SubElement(center, "lane", {"id": "0", "type": "none", "level": "false"})
    ET.SubElement(
        center_lane,
        "roadMark",
        {
            "sOffset": "0.000000",
            "type": "solid",
            "weight": "standard",
            "color": "white",
            "width": "0.150000",
            "laneChange": "none",
        },
    )
    right = ET.SubElement(section, "right")
    lane = ET.SubElement(right, "lane", {"id": "-1", "type": lane_type, "level": "false"})
    ET.SubElement(
        lane,
        "width",
        {"sOffset": "0.000000", "a": fmt(width), "b": "0.000000", "c": "0.000000", "d": "0.000000"},
    )
    ET.SubElement(
        lane,
        "roadMark",
        {
            "sOffset": "0.000000",
            "type": "broken",
            "weight": "standard",
            "color": "white",
            "width": "0.150000",
            "laneChange": "both",
        },
    )


def build_opendrive(
    parsed: dict[str, Any],
    *,
    map_name: str,
    projector: dict[str, Any] | None,
    reference_line_mode: str,
    lane_type: str,
    max_lanelets: int | None = None,
    flip_y: bool = False,
) -> tuple[ET.ElementTree, dict[str, Any]]:
    nodes: dict[str, Point] = parsed["nodes"]
    ways: dict[str, LaneletWay] = parsed["ways"]
    lanelets: list[LaneletRelation] = parsed["lanelets"]

    root = ET.Element("OpenDRIVE")
    all_points = list(nodes.values())
    if flip_y:
        nodes = {node_id: (point[0], -point[1], point[2]) for node_id, point in nodes.items()}
        all_points = list(nodes.values())
    bounds = bbox(all_points) or {"north": 0.0, "south": 0.0, "east": 0.0, "west": 0.0}

    header = ET.SubElement(
        root,
        "header",
        {
            "revMajor": "1",
            "revMinor": "4",
            "name": map_name,
            "version": "1.00",
            "date": utc_now_iso(),
            "north": fmt(float(bounds["north"])),
            "south": fmt(float(bounds["south"])),
            "east": fmt(float(bounds["east"])),
            "west": fmt(float(bounds["west"])),
            "vendor": "PIX Simulation Validation Platform",
        },
    )
    if projector and projector.get("map_origin"):
        origin = projector["map_origin"]
        append_text(
            header,
            "geoReference",
            f"+proj=tmerc +lat_0={origin.get('latitude')} +lon_0={origin.get('longitude')} +datum=WGS84 +units=m +no_defs",
        )

    skipped: list[dict[str, str]] = []
    road_summaries: list[dict[str, Any]] = []
    selected_lanelets = lanelets[:max_lanelets] if max_lanelets else lanelets

    for lanelet in selected_lanelets:
        left_way = ways.get(lanelet.left_way)
        right_way = ways.get(lanelet.right_way)
        if not left_way or not right_way:
            skipped.append({"relation_id": lanelet.relation_id, "reason": "missing_left_or_right_way"})
            continue
        left = points_for_way(left_way, nodes)
        right = points_for_way(right_way, nodes)
        if len(left) < 2 or len(right) < 2:
            skipped.append({"relation_id": lanelet.relation_id, "reason": "not_enough_boundary_points"})
            continue

        reference = reference_line(left, right, reference_line_mode)
        if len(reference) < 2 or polyline_length(reference) <= 0.01:
            skipped.append({"relation_id": lanelet.relation_id, "reason": "degenerate_reference_line"})
            continue

        width = mean_lane_width(left, right)
        road = ET.SubElement(
            root,
            "road",
            {"name": f"lanelet_{lanelet.relation_id}", "length": "0.000000", "id": lanelet.relation_id, "junction": "-1"},
        )
        road.append(road_type(lanelet.tags.get("speed_limit")))
        length, segment_count = add_plan_view(road, reference)
        road.set("length", fmt(length))
        elevation = ET.SubElement(road, "elevationProfile")
        mean_z = sum(point[2] for point in reference) / len(reference)
        ET.SubElement(
            elevation,
            "elevation",
            {"s": "0.000000", "a": fmt(mean_z), "b": "0.000000", "c": "0.000000", "d": "0.000000"},
        )
        add_lanes(road, width, lane_type)
        road_summaries.append(
            {
                "road_id": lanelet.relation_id,
                "left_way": lanelet.left_way,
                "right_way": lanelet.right_way,
                "length_m": length,
                "segment_count": segment_count,
                "lane_width_m": width,
                "speed_limit": lanelet.tags.get("speed_limit"),
            }
        )

    ET.indent(root, space="  ")
    report = {
        "generated_at": utc_now_iso(),
        "map_name": map_name,
        "format": "OpenDRIVE 1.4",
        "reference_line_mode": reference_line_mode,
        "lane_type": lane_type,
        "flip_y": flip_y,
        "input_counts": {"nodes": len(nodes), "ways": len(ways), "lanelet_relations": len(lanelets)},
        "output_counts": {"roads": len(road_summaries), "skipped_lanelets": len(skipped)},
        "bounds": bounds,
        "projector": projector,
        "roads_sample": road_summaries[:20],
        "skipped_sample": skipped[:20],
        "limitations": [
            "junction topology is not connected in this first-pass conversion",
            "road marks and traffic controls are simplified",
            "visual road mesh and terrain are not generated",
            "lanelet boundaries are converted to simple OpenDRIVE line geometries",
        ],
    }
    return ET.ElementTree(root), report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        f"# Lanelet2 To OpenDRIVE Conversion: {report['map_name']}",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- format: `{report['format']}`",
        f"- reference_line_mode: `{report['reference_line_mode']}`",
        f"- lane_type: `{report['lane_type']}`",
        f"- flip_y: `{report['flip_y']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in report["input_counts"].items():
        lines.append(f"- input_{key}: `{value}`")
    for key, value in report["output_counts"].items():
        lines.append(f"- output_{key}: `{value}`")
    lines.extend(["", "## Limitations", ""])
    for item in report["limitations"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Road Sample", ""])
    for road in report["roads_sample"][:10]:
        lines.append(
            f"- road `{road['road_id']}` length `{road['length_m']:.2f}` m, width `{road['lane_width_m']:.2f}` m, speed `{road['speed_limit']}`"
        )
    if report["skipped_sample"]:
        lines.extend(["", "## Skipped Sample", ""])
        for item in report["skipped_sample"]:
            lines.append(f"- relation `{item['relation_id']}`: {item['reason']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def convert_lanelet_to_opendrive(
    *,
    lanelet_path: Path,
    projector_path: Path | None,
    output_dir: Path,
    map_name: str,
    reference_line_mode: str,
    lane_type: str,
    max_lanelets: int | None = None,
    flip_y: bool = False,
) -> dict[str, Any]:
    parsed = parse_lanelet2(lanelet_path)
    projector = load_yaml(projector_path) if projector_path and projector_path.exists() else None
    tree, report = build_opendrive(
        parsed,
        map_name=map_name,
        projector=projector,
        reference_line_mode=reference_line_mode,
        lane_type=lane_type,
        max_lanelets=max_lanelets,
        flip_y=flip_y,
    )
    ensure_dir(output_dir)
    xodr_path = output_dir / f"{map_name}.xodr"
    json_path = output_dir / "conversion_report.json"
    markdown_path = output_dir / "conversion_report.md"
    tree.write(xodr_path, encoding="utf-8", xml_declaration=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(markdown_path, report)
    return {"xodr": str(xodr_path), "json": str(json_path), "markdown": str(markdown_path), "report": report}


def add_lanelet_to_opendrive_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--lanelet", required=True, type=Path, help="Lanelet2 OSM file with local_x/local_y/ele nodes")
    parser.add_argument("--projector", type=Path, help="map_projector_info.yaml for geoReference metadata")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--map-name", required=True)
    parser.add_argument("--reference-line", choices=["left", "center"], default="left")
    parser.add_argument("--lane-type", default="driving")
    parser.add_argument("--max-lanelets", type=int)
    parser.add_argument("--flip-y", action="store_true", help="Flip local_y when CARLA smoke shows a mirrored map")


def convert_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return convert_lanelet_to_opendrive(
        lanelet_path=args.lanelet,
        projector_path=args.projector,
        output_dir=args.output_dir,
        map_name=args.map_name,
        reference_line_mode=args.reference_line,
        lane_type=args.lane_type,
        max_lanelets=args.max_lanelets,
        flip_y=args.flip_y,
    )


def conversion_result_payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in result.items() if key != "report"}
    payload["summary"] = result["report"]["output_counts"]
    return payload
