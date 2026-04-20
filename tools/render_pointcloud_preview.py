from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import open3d as o3d  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_cloud(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    cloud = o3d.io.read_point_cloud(str(path))
    points = np.asarray(cloud.points)
    if points.size == 0:
        raise ValueError(f"empty point cloud: {path}")
    colors = np.asarray(cloud.colors) if cloud.has_colors() else None
    return points, colors


def _scatter_topdown(
    points: np.ndarray,
    colors: np.ndarray | None,
    output_path: Path,
    title: str,
    color_by_z: bool = False,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 12), dpi=180)
    if color_by_z or colors is None:
        scatter = ax.scatter(points[:, 0], points[:, 1], s=0.8, c=points[:, 2], cmap="turbo", linewidths=0)
        colorbar = fig.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04)
        colorbar.set_label("z (m)")
    else:
        ax.scatter(points[:, 0], points[:, 1], s=0.8, c=colors, linewidths=0)
    ax.set_title(title)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def _histogram_z(series: list[tuple[str, np.ndarray]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 7), dpi=180)
    for label, points in series:
        ax.hist(points[:, 2], bins=100, alpha=0.55, label=f"{label}: {len(points):,} pts")
    ax.set_title("Z distribution")
    ax.set_xlabel("z (m)")
    ax.set_ylabel("point count")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def render_preview(run_dir: Path, output_dir: Path | None = None) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    if output_dir is None:
        output_dir = run_dir / "previews"
    else:
        output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = run_dir / "pointcloud_smoke.json"
    metadata: dict[str, Any] = {}
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    sample_path = run_dir / "pointcloud_smoke_sample.ply"
    sample_points, sample_colors = _load_cloud(sample_path)

    outputs: dict[str, str] = {}
    sample_topdown = output_dir / "sample_topdown.png"
    _scatter_topdown(
        sample_points,
        sample_colors,
        sample_topdown,
        f"Pointcloud sample top-down: {len(sample_points):,} pts",
    )
    outputs["sample_topdown"] = str(sample_topdown)

    z_series = [("sample", sample_points)]
    classified_path = run_dir / "classified_ground_nonground.ply"
    if classified_path.is_file():
        classified_points, classified_colors = _load_cloud(classified_path)
        classified_topdown = output_dir / "classified_topdown.png"
        _scatter_topdown(
            classified_points,
            classified_colors,
            classified_topdown,
            f"Ground/non-ground classified top-down: {len(classified_points):,} pts",
        )
        outputs["classified_topdown"] = str(classified_topdown)
        z_series.append(("classified", classified_points))

    ground_path = run_dir / "ground_points.ply"
    if ground_path.is_file():
        ground_points, _ = _load_cloud(ground_path)
        z_series.append(("ground", ground_points))

    nonground_path = run_dir / "nonground_points.ply"
    if nonground_path.is_file():
        nonground_points, _ = _load_cloud(nonground_path)
        z_series.append(("nonground", nonground_points))

    clean_ground_path = run_dir / "site_proxy_ground_clean.ply"
    if clean_ground_path.is_file():
        clean_ground_points, clean_ground_colors = _load_cloud(clean_ground_path)
        clean_ground_topdown = output_dir / "site_proxy_ground_clean_topdown.png"
        _scatter_topdown(
            clean_ground_points,
            clean_ground_colors,
            clean_ground_topdown,
            f"Clean ground site proxy top-down: {len(clean_ground_points):,} pts",
        )
        outputs["site_proxy_ground_clean_topdown"] = str(clean_ground_topdown)
        z_series.append(("ground_clean", clean_ground_points))

    z_histogram = output_dir / "z_histogram.png"
    _histogram_z(z_series, z_histogram)
    outputs["z_histogram"] = str(z_histogram)

    summary = {
        "run_dir": str(run_dir),
        "metadata": {
            "bundle_id": metadata.get("bundle_id"),
            "run_name": metadata.get("run_name"),
            "selected_tiles": metadata.get("selected_tiles"),
            "sampled_points": metadata.get("sampled_points"),
            "ground_split": metadata.get("ground_split"),
            "ground_cleanup": metadata.get("ground_cleanup"),
        },
        "outputs": outputs,
    }
    (output_dir / "preview_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render pointcloud reconstruction preview images")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        summary = render_preview(args.run_dir, args.output_dir)
    except Exception as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"passed": True, **summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
