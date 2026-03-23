from __future__ import annotations

import argparse
import zipfile
from collections import Counter
from pathlib import Path

import yaml


def build_manifest(zip_path: Path, bundle_id: str, site_id: str, repo_root: Path, asset_root: Path) -> dict:
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        counters = Counter()
        for name in names:
            if name.endswith("/"):
                continue
            suffix = Path(name).suffix.lower().lstrip(".") or "<noext>"
            counters[suffix] += 1

        projector_name = next(name for name in names if name.endswith("map_projector_info.yaml"))
        projector = yaml.safe_load(archive.read(projector_name).decode("utf-8"))

    extract_dir = f"${{SIM_ASSET_ROOT}}/{bundle_id}"
    return {
        "bundle_id": bundle_id,
        "site_id": site_id,
        "description": f"Generated manifest for {site_id}",
        "source": {
            "type": "local_archive",
            "archive_path": f"${{REPO_ROOT}}/{zip_path.name}",
            "preferred_extract_dir": extract_dir,
        },
        "maps": {
            "lanelet2": {"path": f"{extract_dir}/lanelet2_map.osm"},
            "projector": {"path": f"{extract_dir}/map_projector_info.yaml"},
            "pointcloud_dir": {"path": f"{extract_dir}/pointcloud_map.pcd"},
        },
        "metadata": {
            "map_origin": projector["map_origin"],
            "projector_type": projector["projector_type"],
            "extension_counts": dict(counters),
            "generated_from": str(zip_path.relative_to(repo_root)),
            "asset_root_hint": str(asset_root),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a site asset manifest from a local ZIP archive")
    parser.add_argument("--zip", dest="zip_path", required=True)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--site-id", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--asset-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    asset_root = Path(args.asset_root).resolve()
    manifest = build_manifest(Path(args.zip_path).resolve(), args.bundle_id, args.site_id, repo_root, asset_root)
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
