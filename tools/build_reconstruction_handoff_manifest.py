from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


KNOWN_OUTPUTS = {
    "pointcloud_smoke.json": "run_summary",
    "pointcloud_smoke.md": "run_report",
    "pointcloud_smoke_sample.ply": "sample_pointcloud",
    "ground_points.ply": "ground_layer",
    "nonground_points.ply": "nonground_layer",
    "classified_ground_nonground.ply": "classified_pointcloud",
    "site_proxy_ground_clean.ply": "site_proxy_ground_clean",
    "heightmap/ground_heightmap.csv": "ground_heightmap_csv",
    "heightmap/ground_heightmap.json": "ground_heightmap_report",
    "heightmap/ground_heightmap_centroids.ply": "ground_heightmap_centroids",
    "heightmap/ground_heightmap.png": "ground_heightmap_preview",
    "previews/sample_topdown.png": "sample_topdown_preview",
    "previews/classified_topdown.png": "classified_topdown_preview",
    "previews/site_proxy_ground_clean_topdown.png": "site_proxy_ground_preview",
    "previews/z_histogram.png": "z_histogram",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    run_dir: Path,
    site_id: str,
    handoff_root_uri: str | None,
    hash_max_mb: float,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    files = []
    hash_limit = int(hash_max_mb * 1024 * 1024)
    for relative_path, role in KNOWN_OUTPUTS.items():
        path = run_dir / relative_path
        if not path.exists() or not path.is_file():
            continue
        normalized_relative_path = relative_path.replace("\\", "/")
        stat = path.stat()
        record: dict[str, Any] = {
            "role": role,
            "relative_path": normalized_relative_path,
            "local_path": str(path),
            "size_bytes": stat.st_size,
        }
        if handoff_root_uri:
            record["handoff_uri"] = f"{handoff_root_uri.rstrip('/')}/{normalized_relative_path}"
        if stat.st_size <= hash_limit:
            record["sha256"] = _sha256(path)
        else:
            record["sha256"] = None
            record["hash_skipped_reason"] = f"file exceeds hash_max_mb={hash_max_mb}"
        files.append(record)

    return {
        "generated_at": _utc_now(),
        "site_id": site_id,
        "run_dir": str(run_dir),
        "producer_host_role": "home_windows_reconstruction_host",
        "consumer_host_role": "company_ubuntu_validation_host",
        "handoff_policy": (
            "The local Windows host generates reconstruction assets. The company Ubuntu host consumes synced "
            "assets only and does not run reconstruction jobs."
        ),
        "handoff_root_uri": handoff_root_uri,
        "file_count": len(files),
        "files": files,
    }


def write_markdown(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        f"# Reconstruction Handoff Manifest - {manifest['site_id']}",
        "",
        f"- Generated at: `{manifest['generated_at']}`",
        f"- Producer: `{manifest['producer_host_role']}`",
        f"- Consumer: `{manifest['consumer_host_role']}`",
        f"- Run dir: `{manifest['run_dir']}`",
        f"- Handoff root: `{manifest.get('handoff_root_uri') or 'local-only'}`",
        "",
        manifest["handoff_policy"],
        "",
        "## Files",
        "",
        "| Role | Relative Path | Size Bytes | SHA256 |",
        "| --- | --- | ---: | --- |",
    ]
    for item in manifest["files"]:
        sha = item.get("sha256") or item.get("hash_skipped_reason") or ""
        lines.append(f"| `{item['role']}` | `{item['relative_path']}` | {item['size_bytes']} | `{sha}` |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a manifest for local reconstruction assets consumed by Ubuntu hosts")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--site-id", default="site_gy_qyhx_gsh20260310")
    parser.add_argument("--handoff-root-uri", default=None, help="Shared path or object-storage prefix visible to the company host")
    parser.add_argument("--hash-max-mb", type=float, default=256.0)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    args = parser.parse_args(argv)

    manifest = build_manifest(
        run_dir=args.run_dir,
        site_id=args.site_id,
        handoff_root_uri=args.handoff_root_uri,
        hash_max_mb=args.hash_max_mb,
    )
    json_path = args.output_json or args.run_dir / "handoff_manifest.json"
    md_path = args.output_md or args.run_dir / "handoff_manifest.md"
    json_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(md_path, manifest)
    print(json.dumps({"passed": True, "json": str(json_path), "markdown": str(md_path), "file_count": manifest["file_count"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
