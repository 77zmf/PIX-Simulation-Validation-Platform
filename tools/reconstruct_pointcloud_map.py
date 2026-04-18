from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from simctl.assets import inspect_asset_bundle, load_asset_bundle  # noqa: E402
from simctl.config import ensure_dir, load_yaml  # noqa: E402


@dataclass(frozen=True)
class PcdHeader:
    path: Path
    data_offset: int
    fields: list[str]
    size: list[int]
    types: list[str]
    count: list[int]
    width: int
    height: int
    points: int
    data: str

    @property
    def point_step(self) -> int:
        return sum(size * count for size, count in zip(self.size, self.count))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_pcd_header(path: Path) -> PcdHeader:
    header: dict[str, str] = {}
    data_offset = 0
    with path.open("rb") as fh:
        while True:
            raw = fh.readline()
            if not raw:
                break
            data_offset = fh.tell()
            line = raw.decode("utf-8", errors="replace").strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                header[parts[0].upper()] = parts[1]
            if line.startswith("DATA "):
                break

    fields = header.get("FIELDS", "").split()
    size = [int(value) for value in header.get("SIZE", "").split()]
    types = header.get("TYPE", "").split()
    count = [int(value) for value in header.get("COUNT", " ".join(["1"] * len(fields))).split()]
    points = int(header.get("POINTS", header.get("WIDTH", "0")))
    return PcdHeader(
        path=path,
        data_offset=data_offset,
        fields=fields,
        size=size,
        types=types,
        count=count,
        width=int(header.get("WIDTH", "0")),
        height=int(header.get("HEIGHT", "1")),
        points=points,
        data=header.get("DATA", "unknown").lower(),
    )


def _field_offsets(header: PcdHeader) -> dict[str, int]:
    offsets: dict[str, int] = {}
    cursor = 0
    for name, size, count in zip(header.fields, header.size, header.count):
        offsets[name] = cursor
        cursor += size * count
    return offsets


def _decode_rgb(raw: bytes, offset: int) -> tuple[int, int, int]:
    rgb_uint = struct.unpack_from("<I", raw, offset)[0]
    red = (rgb_uint >> 16) & 255
    green = (rgb_uint >> 8) & 255
    blue = rgb_uint & 255
    return red, green, blue


def _iter_binary_points(path: Path, header: PcdHeader, stride: int) -> Iterable[tuple[float, float, float, int, int, int]]:
    offsets = _field_offsets(header)
    required = {"x", "y", "z"}
    if not required.issubset(offsets):
        raise ValueError(f"{path} does not contain x/y/z fields")

    point_step = header.point_step
    rgb_offset = offsets.get("rgb")
    stride = max(stride, 1)

    with path.open("rb") as fh:
        fh.seek(header.data_offset)
        for index in range(header.points):
            raw = fh.read(point_step)
            if len(raw) < point_step:
                break
            if index % stride != 0:
                continue
            x = struct.unpack_from("<f", raw, offsets["x"])[0]
            y = struct.unpack_from("<f", raw, offsets["y"])[0]
            z = struct.unpack_from("<f", raw, offsets["z"])[0]
            if rgb_offset is not None:
                red, green, blue = _decode_rgb(raw, rgb_offset)
            else:
                red = green = blue = 180
            yield x, y, z, red, green, blue


def _iter_ascii_points(path: Path, header: PcdHeader, stride: int) -> Iterable[tuple[float, float, float, int, int, int]]:
    offsets = {name: index for index, name in enumerate(header.fields)}
    stride = max(stride, 1)
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("DATA "):
                break
        for index, line in enumerate(fh):
            if index % stride != 0:
                continue
            parts = line.split()
            if not parts:
                continue
            x = float(parts[offsets["x"]])
            y = float(parts[offsets["y"]])
            z = float(parts[offsets["z"]])
            red = green = blue = 180
            if "rgb" in offsets:
                rgb_float = float(parts[offsets["rgb"]])
                rgb_uint = struct.unpack("<I", struct.pack("<f", rgb_float))[0]
                red = (rgb_uint >> 16) & 255
                green = (rgb_uint >> 8) & 255
                blue = rgb_uint & 255
            yield x, y, z, red, green, blue


def iter_pcd_points(path: Path, stride: int = 1) -> Iterable[tuple[float, float, float, int, int, int]]:
    header = read_pcd_header(path)
    if header.data == "binary":
        return _iter_binary_points(path, header, stride)
    if header.data == "ascii":
        return _iter_ascii_points(path, header, stride)
    raise ValueError(f"Unsupported PCD DATA mode for {path}: {header.data}")


def _percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    index = min(len(values) - 1, max(0, int(round((len(values) - 1) * ratio))))
    return sorted(values)[index]


def _bounds(points: list[tuple[float, float, float, int, int, int]]) -> dict[str, Any]:
    if not points:
        return {
            "x": None,
            "y": None,
            "z": None,
            "z_p05": None,
            "z_p50": None,
            "z_p95": None,
        }
    xs = [item[0] for item in points]
    ys = [item[1] for item in points]
    zs = [item[2] for item in points]
    return {
        "x": [min(xs), max(xs)],
        "y": [min(ys), max(ys)],
        "z": [min(zs), max(zs)],
        "z_p05": _percentile(zs, 0.05),
        "z_p50": _percentile(zs, 0.50),
        "z_p95": _percentile(zs, 0.95),
    }


def write_ascii_ply(path: Path, points: list[tuple[float, float, float, int, int, int]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("ply\n")
        fh.write("format ascii 1.0\n")
        fh.write(f"element vertex {len(points)}\n")
        fh.write("property float x\n")
        fh.write("property float y\n")
        fh.write("property float z\n")
        fh.write("property uchar red\n")
        fh.write("property uchar green\n")
        fh.write("property uchar blue\n")
        fh.write("end_header\n")
        for x, y, z, red, green, blue in points:
            fh.write(f"{x:.6f} {y:.6f} {z:.6f} {red} {green} {blue}\n")


def _safe_name(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in ("-", "_"):
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe).strip("_") or "default"


def default_run_name(
    selection: str,
    max_tiles: int,
    max_points: int,
    region: tuple[float, float, float, float] | None,
) -> str:
    tile_part = "all_tiles" if max_tiles == 0 else f"tiles{max_tiles}"
    point_part = f"points{max_points}"
    if region:
        region_part = "region_" + "_".join(str(int(value)) if value.is_integer() else str(value) for value in region)
        return _safe_name(f"{selection}_{region_part}_{tile_part}_{point_part}")
    return _safe_name(f"{selection}_{tile_part}_{point_part}")


def _metadata_tiles(metadata_path: Path) -> dict[str, list[float]]:
    payload = load_yaml(metadata_path)
    return {
        str(name): value
        for name, value in payload.items()
        if str(name).endswith(".pcd") and isinstance(value, list) and len(value) >= 2
    }


def _select_tiles(
    pointcloud_dir: Path,
    metadata_path: Path,
    max_tiles: int,
    region: tuple[float, float, float, float] | None,
    selection: str,
) -> list[Path]:
    files_by_name = {path.name: path for path in pointcloud_dir.glob("*.pcd")}
    metadata = _metadata_tiles(metadata_path)
    names: list[str] = []

    for name, xy in metadata.items():
        if name not in files_by_name:
            continue
        x, y = float(xy[0]), float(xy[1])
        if region:
            min_x, max_x, min_y, max_y = region
            if not (min_x <= x <= max_x and min_y <= y <= max_y):
                continue
        names.append(name)

    if not names:
        names = sorted(files_by_name)

    if selection == "largest":
        names = sorted(names, key=lambda item: files_by_name[item].stat().st_size, reverse=True)
    elif selection == "center":
        names = sorted(names, key=lambda item: abs(metadata.get(item, [0, 0])[0]) + abs(metadata.get(item, [0, 0])[1]))
    else:
        names = sorted(names)

    if max_tiles > 0:
        names = names[:max_tiles]
    return [files_by_name[name] for name in names]


def build_pointcloud_smoke_report(
    bundle_id: str,
    asset_root: Path,
    output_dir: Path,
    max_tiles: int,
    max_points: int,
    region: tuple[float, float, float, float] | None,
    selection: str,
    run_name: str | None = None,
) -> dict[str, Any]:
    bundle = load_asset_bundle(bundle_id, asset_root=asset_root)
    inspection = inspect_asset_bundle(bundle)
    checks = {item["name"]: item for item in inspection["checks"]}
    pointcloud_dir = Path(checks["pointcloud_dir"]["resolved_path"])
    metadata_path = Path(checks["pointcloud_metadata"]["resolved_path"])
    selected = _select_tiles(pointcloud_dir, metadata_path, max_tiles, region, selection)

    headers = [read_pcd_header(path) for path in selected]
    total_source_points = sum(header.points for header in headers)
    points_per_tile = max(1, math.ceil(max_points / max(len(selected), 1)))
    sampled_points: list[tuple[float, float, float, int, int, int]] = []
    tile_reports = []

    for path, header in zip(selected, headers):
        stride = max(1, math.ceil(header.points / points_per_tile))
        tile_points = list(iter_pcd_points(path, stride=stride))
        sampled_points.extend(tile_points)
        tile_reports.append(
            {
                "name": path.name,
                "source_points": header.points,
                "sample_stride": stride,
                "sampled_points": len(tile_points),
                "data": header.data,
                "fields": header.fields,
                "bounds": _bounds(tile_points),
            }
        )

    if len(sampled_points) > max_points:
        stride = math.ceil(len(sampled_points) / max_points)
        sampled_points = sampled_points[::stride]

    resolved_run_name = _safe_name(run_name) if run_name else default_run_name(selection, max_tiles, max_points, region)
    output_dir = ensure_dir(output_dir / bundle_id / resolved_run_name)
    ply_path = output_dir / "pointcloud_smoke_sample.ply"
    json_path = output_dir / "pointcloud_smoke.json"
    md_path = output_dir / "pointcloud_smoke.md"
    write_ascii_ply(ply_path, sampled_points)

    report = {
        "generated_at": _utc_now(),
        "bundle_id": bundle.bundle_id,
        "site_id": bundle.site_id,
        "mode": "pointcloud_map_static_reconstruction_smoke",
        "asset_root": str(asset_root),
        "pointcloud_dir": str(pointcloud_dir),
        "metadata_path": str(metadata_path),
        "selection": selection,
        "run_name": resolved_run_name,
        "region": region,
        "selected_tiles": len(selected),
        "total_source_points_in_selected_tiles": total_source_points,
        "sampled_points": len(sampled_points),
        "global_bounds": _bounds(sampled_points),
        "outputs": {
            "ply": str(ply_path),
            "json": str(json_path),
            "markdown": str(md_path),
        },
        "tiles": tile_reports,
        "passed": bool(selected and sampled_points),
        "next_action": "Open the PLY with Open3D or CloudCompare, then decide whether to run full-map merge, mesh, or Gaussian conversion.",
    }
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    bounds = report["global_bounds"]
    lines = [
        f"# Pointcloud Map Reconstruction Smoke: {report['bundle_id']}",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- passed: `{report['passed']}`",
        f"- mode: `{report['mode']}`",
        f"- run_name: `{report['run_name']}`",
        f"- selected_tiles: `{report['selected_tiles']}`",
        f"- total_source_points_in_selected_tiles: `{report['total_source_points_in_selected_tiles']}`",
        f"- sampled_points: `{report['sampled_points']}`",
        f"- output_ply: `{report['outputs']['ply']}`",
        "",
        "## Global Bounds",
        "",
        f"- x: `{bounds['x']}`",
        f"- y: `{bounds['y']}`",
        f"- z: `{bounds['z']}`",
        f"- z_p05: `{bounds['z_p05']}`",
        f"- z_p50: `{bounds['z_p50']}`",
        f"- z_p95: `{bounds['z_p95']}`",
        "",
        "## Tile Samples",
        "",
    ]
    for tile in report["tiles"][:20]:
        lines.append(
            f"- `{tile['name']}`: source=`{tile['source_points']}`, "
            f"stride=`{tile['sample_stride']}`, sampled=`{tile['sampled_points']}`"
        )
    lines.extend(
        [
            "",
            "## Next Action",
            "",
            report["next_action"],
            "",
        ]
    )
    return "\n".join(lines)


def _parse_region(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    parts = [float(item.strip()) for item in value.split(",")]
    if len(parts) != 4:
        raise ValueError("--region must be formatted as min_x,max_x,min_y,max_y")
    return parts[0], parts[1], parts[2], parts[3]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a lightweight pointcloud-map reconstruction smoke artifact")
    parser.add_argument("--bundle", default="site_gy_qyhx_gsh20260310")
    parser.add_argument("--asset-root", type=Path, default=REPO_ROOT / "artifacts" / "assets")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "outputs" / "pointcloud_reconstruction")
    parser.add_argument("--max-tiles", type=int, default=64, help="0 means all selected tiles")
    parser.add_argument("--max-points", type=int, default=200_000)
    parser.add_argument("--region", default=None, help="Optional tile coordinate filter: min_x,max_x,min_y,max_y")
    parser.add_argument("--selection", choices=("largest", "center", "metadata"), default="largest")
    parser.add_argument("--run-name", default=None, help="Output subdirectory name under the selected bundle")
    args = parser.parse_args(argv)

    report = build_pointcloud_smoke_report(
        bundle_id=args.bundle,
        asset_root=args.asset_root,
        output_dir=args.output_dir,
        max_tiles=args.max_tiles,
        max_points=args.max_points,
        region=_parse_region(args.region),
        selection=args.selection,
        run_name=args.run_name,
    )
    print(json.dumps({"passed": report["passed"], **report["outputs"]}, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
