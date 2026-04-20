from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def collect_images(image_dir: Path) -> list[Path]:
    if not image_dir.is_dir():
        return []
    return sorted(path for path in image_dir.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def _safe_count(obj: object, names: list[str]) -> int | None:
    for name in names:
        value = getattr(obj, name, None)
        if value is None:
            continue
        if callable(value):
            try:
                return int(value())
            except TypeError:
                continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def summarize_reconstructions(reconstructions: dict[int, object]) -> list[dict[str, Any]]:
    rows = []
    for reconstruction_id, reconstruction in sorted(reconstructions.items()):
        rows.append(
            {
                "reconstruction_id": reconstruction_id,
                "registered_images": _safe_count(reconstruction, ["num_reg_images", "num_registered_images"]),
                "points3d": _safe_count(reconstruction, ["num_points3D", "num_points3d"]),
            }
        )
    return rows


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# PyCOLMAP Sparse Smoke",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- status: `{report['status']}`",
        f"- passed: `{report['passed']}`",
        f"- image_dir: `{report['image_dir']}`",
        f"- image_count: `{report['image_count']}`",
        f"- output_dir: `{report['output_dir']}`",
        f"- database_path: `{report['database_path']}`",
        "",
        "## Reconstructions",
        "",
    ]
    if not report["reconstructions"]:
        lines.append("- none")
    for row in report["reconstructions"]:
        lines.append(
            f"- id={row['reconstruction_id']}, registered_images={row['registered_images']}, points3d={row['points3d']}"
        )
    if report.get("error"):
        lines.extend(["", "## Error", "", f"```text\n{report['error']}\n```"])
    lines.append("")
    return "\n".join(lines)


def write_report(output_dir: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "pycolmap_sparse_smoke.json"
    md_path = output_dir / "pycolmap_sparse_smoke.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def run_sparse_smoke(
    image_dir: Path,
    output_dir: Path,
    min_images: int,
    matcher: str,
    device_name: str,
    camera_mode_name: str,
) -> dict[str, Any]:
    images = collect_images(image_dir)
    database_path = output_dir / "database.db"
    sparse_dir = output_dir / "sparse"
    report: dict[str, Any] = {
        "generated_at": _utc_now(),
        "mode": "pycolmap_sparse_smoke",
        "status": "pending",
        "passed": False,
        "image_dir": str(image_dir),
        "image_count": len(images),
        "min_images": min_images,
        "output_dir": str(output_dir),
        "database_path": str(database_path),
        "matcher": matcher,
        "device": device_name,
        "camera_mode": camera_mode_name,
        "reconstructions": [],
        "error": None,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    sparse_dir.mkdir(parents=True, exist_ok=True)
    if len(images) < min_images:
        report["status"] = "insufficient_images"
        report["error"] = f"Need at least {min_images} images, found {len(images)}."
        return report

    try:
        import pycolmap

        device = getattr(pycolmap.Device, device_name)
        camera_mode = getattr(pycolmap.CameraMode, camera_mode_name)
        pycolmap.extract_features(database_path, image_dir, camera_mode=camera_mode, device=device)
        if matcher == "sequential":
            pycolmap.match_sequential(database_path, device=device)
        else:
            pycolmap.match_exhaustive(database_path, device=device)
        reconstructions = pycolmap.incremental_mapping(database_path, image_dir, sparse_dir)
        report["reconstructions"] = summarize_reconstructions(reconstructions)
        report["passed"] = any((row.get("registered_images") or 0) >= min_images for row in report["reconstructions"])
        report["status"] = "passed" if report["passed"] else "no_valid_reconstruction"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a small PyCOLMAP sparse reconstruction smoke test")
    parser.add_argument("--image-dir", type=Path, default=Path("data/raw/qiyu_loop/images"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/colmap_smoke/qiyu_loop"))
    parser.add_argument("--min-images", type=int, default=8)
    parser.add_argument("--matcher", choices=("exhaustive", "sequential"), default="exhaustive")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--camera-mode", choices=("AUTO", "SINGLE", "PER_FOLDER", "PER_IMAGE"), default="AUTO")
    parser.add_argument("--allow-insufficient", action="store_true")
    args = parser.parse_args(argv)

    report = run_sparse_smoke(
        image_dir=args.image_dir,
        output_dir=args.output_dir,
        min_images=max(args.min_images, 2),
        matcher=args.matcher,
        device_name=args.device,
        camera_mode_name=args.camera_mode,
    )
    json_path, md_path = write_report(args.output_dir, report)
    print(json.dumps({"passed": report["passed"], "status": report["status"], "json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False, indent=2))
    if report["passed"] or (args.allow_insufficient and report["status"] == "insufficient_images"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
