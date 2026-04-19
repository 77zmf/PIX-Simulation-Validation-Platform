from __future__ import annotations

import argparse
import csv
import json
import statistics
import struct
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


Point = tuple[float, float, float]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_ascii_ply_points(path: Path) -> list[Point]:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        vertex_count = None
        property_names: list[str] = []
        for line in fh:
            line = line.strip()
            if line.startswith("element vertex "):
                vertex_count = int(line.split()[-1])
            elif line.startswith("property "):
                parts = line.split()
                if len(parts) >= 3:
                    property_names.append(parts[-1])
            elif line == "end_header":
                break
        if vertex_count is None:
            raise ValueError(f"PLY vertex count not found: {path}")
        required = {"x", "y", "z"}
        if not required.issubset(set(property_names)):
            raise ValueError(f"PLY must contain x/y/z properties: {path}")
        x_index = property_names.index("x")
        y_index = property_names.index("y")
        z_index = property_names.index("z")

        points: list[Point] = []
        for _ in range(vertex_count):
            line = fh.readline()
            if not line:
                break
            parts = line.split()
            if len(parts) <= max(x_index, y_index, z_index):
                continue
            points.append((float(parts[x_index]), float(parts[y_index]), float(parts[z_index])))
        return points


def _height(values: list[float], stat: str) -> float:
    if stat == "min":
        return min(values)
    if stat == "mean":
        return sum(values) / len(values)
    return float(statistics.median(values))


def build_heightmap(
    points: Iterable[Point],
    cell_size: float,
    min_points_per_cell: int,
    height_stat: str,
) -> dict[str, Any]:
    cell_size = max(cell_size, 0.01)
    min_points_per_cell = max(min_points_per_cell, 1)
    cells: dict[tuple[int, int], list[float]] = {}
    input_count = 0
    for x, y, z in points:
        input_count += 1
        key = (int(x // cell_size), int(y // cell_size))
        cells.setdefault(key, []).append(z)

    rows = []
    for (ix, iy), zs in sorted(cells.items()):
        if len(zs) < min_points_per_cell:
            continue
        x_center = (ix + 0.5) * cell_size
        y_center = (iy + 0.5) * cell_size
        rows.append(
            {
                "ix": ix,
                "iy": iy,
                "x": x_center,
                "y": y_center,
                "z": _height(zs, height_stat),
                "count": len(zs),
            }
        )

    z_values = [row["z"] for row in rows]
    x_values = [row["x"] for row in rows]
    y_values = [row["y"] for row in rows]
    summary = {
        "generated_at": _utc_now(),
        "input_points": input_count,
        "cell_size": cell_size,
        "min_points_per_cell": min_points_per_cell,
        "height_stat": height_stat,
        "raw_cells": len(cells),
        "populated_cells": len(rows),
        "x_range": [min(x_values), max(x_values)] if x_values else None,
        "y_range": [min(y_values), max(y_values)] if y_values else None,
        "z_range": [min(z_values), max(z_values)] if z_values else None,
    }
    return {"summary": summary, "cells": rows}


def write_heightmap_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ix", "iy", "x", "y", "z", "count"])
        writer.writeheader()
        writer.writerows(rows)


def write_heightmap_ply(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("ply\n")
        fh.write("format ascii 1.0\n")
        fh.write(f"element vertex {len(rows)}\n")
        fh.write("property float x\n")
        fh.write("property float y\n")
        fh.write("property float z\n")
        fh.write("property uchar red\n")
        fh.write("property uchar green\n")
        fh.write("property uchar blue\n")
        fh.write("end_header\n")
        for row in rows:
            fh.write(f"{row['x']:.6f} {row['y']:.6f} {row['z']:.6f} 40 120 220\n")


def write_heightmap_png(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        _write_png_rgb(path, 1, 1, [(245, 245, 245)])
        return

    min_ix = min(int(row["ix"]) for row in rows)
    max_ix = max(int(row["ix"]) for row in rows)
    min_iy = min(int(row["iy"]) for row in rows)
    max_iy = max(int(row["iy"]) for row in rows)
    min_z = min(float(row["z"]) for row in rows)
    max_z = max(float(row["z"]) for row in rows)
    width = max_ix - min_ix + 1
    height = max_iy - min_iy + 1
    scale = max(1, min(6, 1000 // max(width, height)))

    base_pixels = [(245, 245, 245)] * (width * height)
    for row in rows:
        ix = int(row["ix"]) - min_ix
        iy = max_iy - int(row["iy"])
        base_pixels[iy * width + ix] = _height_color(float(row["z"]), min_z, max_z)

    if scale > 1:
        pixels: list[tuple[int, int, int]] = []
        for y in range(height):
            row_pixels = base_pixels[y * width : (y + 1) * width]
            scaled_row = [pixel for pixel in row_pixels for _ in range(scale)]
            for _ in range(scale):
                pixels.extend(scaled_row)
        _write_png_rgb(path, width * scale, height * scale, pixels)
        return

    _write_png_rgb(path, width, height, base_pixels)


def _height_color(z: float, min_z: float, max_z: float) -> tuple[int, int, int]:
    if max_z <= min_z:
        return (96, 150, 96)
    t = (z - min_z) / (max_z - min_z)
    stops = [
        (0.0, (49, 130, 189)),
        (0.25, (116, 196, 118)),
        (0.55, (255, 255, 191)),
        (0.75, (217, 95, 14)),
        (1.0, (102, 37, 6)),
    ]
    for index in range(1, len(stops)):
        left_t, left_color = stops[index - 1]
        right_t, right_color = stops[index]
        if t <= right_t:
            local_t = (t - left_t) / (right_t - left_t)
            return tuple(
                int(round(left + (right - left) * local_t)) for left, right in zip(left_color, right_color)
            )
    return stops[-1][1]


def _write_png_rgb(path: Path, width: int, height: int, pixels: list[tuple[int, int, int]]) -> None:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    raw_rows = []
    for y in range(height):
        row = pixels[y * width : (y + 1) * width]
        raw_rows.append(b"\x00" + b"".join(bytes(pixel) for pixel in row))

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(raw_rows), level=9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def build_outputs(
    input_ply: Path,
    output_dir: Path,
    cell_size: float,
    min_points_per_cell: int,
    height_stat: str,
    render_png: bool = True,
) -> dict[str, Any]:
    points = read_ascii_ply_points(input_ply)
    payload = build_heightmap(points, cell_size, min_points_per_cell, height_stat)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "ground_heightmap.csv"
    json_path = output_dir / "ground_heightmap.json"
    ply_path = output_dir / "ground_heightmap_centroids.ply"
    png_path = output_dir / "ground_heightmap.png"

    rows = payload["cells"]
    write_heightmap_csv(csv_path, rows)
    write_heightmap_ply(ply_path, rows)
    outputs = {
        "csv": str(csv_path),
        "json": str(json_path),
        "ply": str(ply_path),
    }
    if render_png:
        write_heightmap_png(png_path, rows)
        outputs["png"] = str(png_path)

    report = {
        "input_ply": str(input_ply),
        "summary": payload["summary"],
        "outputs": outputs,
    }
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a regular ground heightmap from a cleaned pointcloud PLY")
    parser.add_argument("--input-ply", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--cell-size", type=float, default=1.0)
    parser.add_argument("--min-points-per-cell", type=int, default=1)
    parser.add_argument("--height-stat", choices=("median", "mean", "min"), default="median")
    parser.add_argument("--skip-png", action="store_true", help="Skip matplotlib PNG rendering and write CSV/JSON/PLY only")
    args = parser.parse_args(argv)

    output_dir = args.output_dir or (args.input_ply.parent / "heightmap")
    try:
        report = build_outputs(
            input_ply=args.input_ply,
            output_dir=output_dir,
            cell_size=args.cell_size,
            min_points_per_cell=args.min_points_per_cell,
            height_stat=args.height_stat,
            render_png=not args.skip_png,
        )
    except Exception as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"passed": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
