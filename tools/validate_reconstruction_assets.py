from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from simctl.assets import inspect_asset_bundle, load_asset_bundle  # noqa: E402
from simctl.config import ensure_dir, load_yaml  # noqa: E402


PCD_HEADER_KEYS = ("VERSION", "FIELDS", "SIZE", "TYPE", "WIDTH", "HEIGHT", "POINTS", "DATA")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _tool_status() -> dict[str, bool]:
    tools = ("python", "ffmpeg", "colmap", "nvidia-smi")
    return {tool: shutil.which(tool) is not None for tool in tools}


def _count_lanelet_tokens(path: Path) -> dict[str, int | None]:
    if not path.exists():
        return {"nodes": None, "ways": None, "relations": None}
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {
        "nodes": text.count("<node "),
        "ways": text.count("<way "),
        "relations": text.count("<relation "),
    }


def _pcd_header(path: Path) -> dict[str, Any]:
    header_lines: list[str] = []
    try:
        with path.open("rb") as fh:
            for _ in range(80):
                raw = fh.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                header_lines.append(line)
                if line.startswith("DATA "):
                    break
    except OSError as exc:
        return {"path": str(path), "readable": False, "error": str(exc)}

    found = {}
    for key in PCD_HEADER_KEYS:
        found[key.lower()] = next((line for line in header_lines if line.startswith(f"{key} ")), None)
    return {
        "path": str(path),
        "readable": True,
        "line_count": len(header_lines),
        "has_required_header_keys": all(value is not None for value in found.values()),
        "fields": found,
    }


def _pointcloud_summary(pointcloud_dir: Path, metadata_path: Path, sample_count: int) -> dict[str, Any]:
    files = sorted(pointcloud_dir.glob("*.pcd")) if pointcloud_dir.is_dir() else []
    total_bytes = sum(path.stat().st_size for path in files)
    metadata_payload: dict[str, Any] = {}
    metadata_error = None
    if metadata_path.is_file():
        try:
            metadata_payload = load_yaml(metadata_path)
        except Exception as exc:  # pragma: no cover - defensive report path
            metadata_error = str(exc)

    metadata_tiles = sorted(key for key in metadata_payload.keys() if str(key).endswith(".pcd"))
    file_names = sorted(path.name for path in files)
    missing_from_metadata = sorted(set(file_names) - set(metadata_tiles))
    missing_from_directory = sorted(set(metadata_tiles) - set(file_names))

    samples = [_pcd_header(path) for path in files[:sample_count]]
    return {
        "directory": str(pointcloud_dir),
        "exists": pointcloud_dir.is_dir(),
        "tile_count": len(files),
        "total_bytes": total_bytes,
        "metadata_path": str(metadata_path),
        "metadata_exists": metadata_path.is_file(),
        "metadata_error": metadata_error,
        "metadata_tile_count": len(metadata_tiles),
        "metadata_matches_directory": not missing_from_metadata and not missing_from_directory,
        "missing_from_metadata": missing_from_metadata[:20],
        "missing_from_directory": missing_from_directory[:20],
        "sample_headers": samples,
    }


def _resolved_map_path(asset_check: dict[str, Any], name: str) -> Path | None:
    for check in asset_check.get("checks", []):
        if check.get("name") == name and check.get("resolved_path"):
            return Path(str(check["resolved_path"]))
    return None


def build_report(bundle_id: str, asset_root: Path | None, sample_count: int) -> dict[str, Any]:
    bundle = load_asset_bundle(bundle_id, asset_root=asset_root)
    asset_check = inspect_asset_bundle(bundle)
    lanelet_path = _resolved_map_path(asset_check, "lanelet2")
    projector_path = _resolved_map_path(asset_check, "projector")
    pointcloud_dir = _resolved_map_path(asset_check, "pointcloud_dir")
    metadata_path = _resolved_map_path(asset_check, "pointcloud_metadata")

    projector_payload: dict[str, Any] | None = None
    projector_error = None
    if projector_path and projector_path.is_file():
        try:
            projector_payload = load_yaml(projector_path)
        except Exception as exc:  # pragma: no cover - defensive report path
            projector_error = str(exc)

    pointcloud = _pointcloud_summary(
        pointcloud_dir or Path("__missing_pointcloud_dir__"),
        metadata_path or Path("__missing_pointcloud_metadata__"),
        sample_count,
    )

    checks = {
        "asset_bundle_present": bool(asset_check["summary"]["all_required_present"]),
        "pointcloud_tiles_match_manifest": bool(asset_check["summary"]["pointcloud_tiles_match"]),
        "pointcloud_metadata_matches_manifest": bool(asset_check["summary"]["pointcloud_metadata_matches_manifest"]),
        "pointcloud_metadata_matches_directory": bool(asset_check["summary"]["pointcloud_metadata_matches_directory"]),
        "projector_has_origin": bool(projector_payload and projector_payload.get("map_origin")),
        "pcd_sample_headers_readable": all(item.get("has_required_header_keys") for item in pointcloud["sample_headers"]),
    }
    return {
        "generated_at": _utc_now(),
        "bundle_id": bundle.bundle_id,
        "site_id": bundle.site_id,
        "asset_root": str(asset_root or (REPO_ROOT / "artifacts" / "assets")),
        "asset_check": asset_check,
        "lanelet2": {
            "path": str(lanelet_path) if lanelet_path else None,
            "token_counts": _count_lanelet_tokens(lanelet_path) if lanelet_path else None,
        },
        "projector": {
            "path": str(projector_path) if projector_path else None,
            "payload": projector_payload,
            "error": projector_error,
        },
        "pointcloud": pointcloud,
        "tool_status": _tool_status(),
        "checks": checks,
        "passed": all(checks.values()),
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["asset_check"]["summary"]
    tool_status = report["tool_status"]
    lines = [
        f"# Reconstruction Asset Validation: {report['bundle_id']}",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- site_id: `{report['site_id']}`",
        f"- passed: `{report['passed']}`",
        f"- asset_root: `{report['asset_root']}`",
        "",
        "## Asset Summary",
        "",
        f"- all_required_present: `{summary['all_required_present']}`",
        f"- pointcloud_tiles_expected: `{summary['pointcloud_tiles_expected']}`",
        f"- pointcloud_tiles_actual: `{summary['pointcloud_tiles_actual']}`",
        f"- pointcloud_metadata_tiles: `{summary['pointcloud_metadata_tiles']}`",
        f"- pointcloud_tiles_match: `{summary['pointcloud_tiles_match']}`",
        "",
        "## Lanelet2",
        "",
    ]
    token_counts = report["lanelet2"]["token_counts"] or {}
    lines.extend(
        [
            f"- path: `{report['lanelet2']['path']}`",
            f"- nodes: `{token_counts.get('nodes')}`",
            f"- ways: `{token_counts.get('ways')}`",
            f"- relations: `{token_counts.get('relations')}`",
            "",
            "## Projector",
            "",
            f"- path: `{report['projector']['path']}`",
            f"- error: `{report['projector']['error']}`",
            f"- map_origin: `{json.dumps((report['projector']['payload'] or {}).get('map_origin'), ensure_ascii=False)}`",
            "",
            "## Pointcloud",
            "",
            f"- directory: `{report['pointcloud']['directory']}`",
            f"- tile_count: `{report['pointcloud']['tile_count']}`",
            f"- total_bytes: `{report['pointcloud']['total_bytes']}`",
            f"- metadata_matches_directory: `{report['pointcloud']['metadata_matches_directory']}`",
            "",
            "## Tool Status",
            "",
        ]
    )
    for tool, available in tool_status.items():
        lines.append(f"- {tool}: `{available}`")
    lines.extend(["", "## Checks", ""])
    for name, passed in report["checks"].items():
        lines.append(f"- {name}: `{passed}`")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate local reconstruction asset readiness")
    parser.add_argument("--bundle", default="site_gy_qyhx_gsh20260310")
    parser.add_argument("--asset-root", type=Path, default=REPO_ROOT / "artifacts" / "assets")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "outputs" / "reconstruction_validation")
    parser.add_argument("--sample-count", type=int, default=5)
    args = parser.parse_args(argv)

    report = build_report(args.bundle, args.asset_root, args.sample_count)
    output_dir = ensure_dir(args.output_dir / args.bundle)
    json_path = output_dir / "asset_validation.json"
    md_path = output_dir / "asset_validation.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps({"passed": report["passed"], "json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
