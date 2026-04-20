from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import find_repo_root, interpolate, load_yaml
from .models import AssetBundle


def manifest_path_for(bundle_ref: str, repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    candidate = Path(bundle_ref)
    if candidate.exists():
        return candidate.resolve()
    manifest = root / "assets" / "manifests" / f"{bundle_ref}.yaml"
    if not manifest.exists():
        raise FileNotFoundError(f"Unable to locate asset manifest for '{bundle_ref}'")
    return manifest


def load_asset_bundle(bundle_ref: str, repo_root: Path | None = None, asset_root: Path | None = None) -> AssetBundle:
    root = repo_root or find_repo_root()
    manifest_path = manifest_path_for(bundle_ref, root)
    context = {
        "REPO_ROOT": str(root),
        "SIM_ASSET_ROOT": str(asset_root or (root / "artifacts" / "assets")),
    }
    payload = interpolate(load_yaml(manifest_path), context)
    return AssetBundle.from_dict(payload, manifest_path)


def asset_snapshot(bundle: AssetBundle) -> dict[str, Any]:
    return {
        "bundle_id": bundle.bundle_id,
        "site_id": bundle.site_id,
        "description": bundle.description,
        "source": bundle.source,
        "maps": bundle.maps,
        "metadata": bundle.metadata,
        "manifest_path": str(bundle.manifest_path),
    }


def _is_virtual_path(path_value: str | None) -> bool:
    return bool(path_value and "://" in path_value)


def _normalize_path_value(path_value: str | None) -> str | None:
    if not path_value or _is_virtual_path(path_value):
        return path_value
    return str(Path(path_value))


def _path_status(path_value: str | None, fallback_value: str | None = None) -> dict[str, Any]:
    primary = _normalize_path_value(str(path_value) if path_value else None) or ""
    fallback = _normalize_path_value(str(fallback_value) if fallback_value else None) or ""

    if _is_virtual_path(primary):
        return {
            "path": primary,
            "exists": None,
            "fallback_path": fallback or None,
            "fallback_exists": None,
            "resolved_path": primary,
            "status": "virtual",
        }

    primary_exists = bool(primary) and Path(primary).exists()
    fallback_is_virtual = _is_virtual_path(fallback)
    fallback_exists = bool(fallback) and Path(fallback).exists() if fallback and not fallback_is_virtual else None

    if primary_exists:
        status = "present"
        resolved = primary
    elif fallback_is_virtual:
        status = "fallback_virtual"
        resolved = fallback
    elif fallback_exists:
        status = "fallback"
        resolved = fallback
    else:
        status = "missing"
        resolved = primary or fallback

    return {
        "path": primary or None,
        "exists": primary_exists,
        "fallback_path": fallback or None,
        "fallback_exists": fallback_exists,
        "resolved_path": resolved or None,
        "status": status,
    }


def inspect_asset_bundle(bundle: AssetBundle) -> dict[str, Any]:
    source = bundle.source
    archive_path = _normalize_path_value(str(source.get("archive_path", "")) or None)
    preferred_extract_dir = _normalize_path_value(str(source.get("preferred_extract_dir", "")) or None)
    archive_exists = None if _is_virtual_path(archive_path) else (Path(archive_path).exists() if archive_path else None)
    extract_dir_exists = (
        None if _is_virtual_path(preferred_extract_dir) else (Path(preferred_extract_dir).exists() if preferred_extract_dir else None)
    )

    checks: list[dict[str, Any]] = []
    for name, entry in bundle.maps.items():
        if not isinstance(entry, dict):
            continue
        check = _path_status(entry.get("path"), entry.get("fallback_repo_path"))
        checks.append({"name": name, **check})

    valid_statuses = {"present", "fallback", "virtual", "fallback_virtual"}
    summary: dict[str, Any] = {
        "all_required_present": all(check["status"] in valid_statuses for check in checks),
        "pointcloud_tiles_expected": bundle.metadata.get("pointcloud_tiles"),
        "pointcloud_tiles_actual": None,
        "pointcloud_tiles_match": None,
        "pointcloud_metadata_tiles": None,
        "pointcloud_metadata_matches_manifest": None,
        "pointcloud_metadata_matches_directory": None,
        "pointcloud_metadata_parse_error": None,
    }

    pointcloud_dir = next((check for check in checks if check["name"] == "pointcloud_dir"), None)
    if pointcloud_dir and pointcloud_dir["status"] in {"present", "fallback"} and pointcloud_dir["resolved_path"]:
        pointcloud_dir_path = Path(str(pointcloud_dir["resolved_path"]))
        if pointcloud_dir_path.is_dir():
            summary["pointcloud_tiles_actual"] = len(list(pointcloud_dir_path.glob("*.pcd")))

    pointcloud_metadata = next((check for check in checks if check["name"] == "pointcloud_metadata"), None)
    if pointcloud_metadata and pointcloud_metadata["status"] in {"present", "fallback"} and pointcloud_metadata["resolved_path"]:
        metadata_path = Path(str(pointcloud_metadata["resolved_path"]))
        if metadata_path.is_file():
            try:
                metadata_payload = load_yaml(metadata_path)
            except Exception as exc:
                summary["pointcloud_metadata_parse_error"] = str(exc)
            else:
                summary["pointcloud_metadata_tiles"] = sum(
                    1 for key in metadata_payload.keys() if str(key).endswith(".pcd")
                )

    expected_tiles = summary["pointcloud_tiles_expected"]
    actual_tiles = summary["pointcloud_tiles_actual"]
    metadata_tiles = summary["pointcloud_metadata_tiles"]
    if isinstance(expected_tiles, int) and isinstance(actual_tiles, int):
        summary["pointcloud_tiles_match"] = actual_tiles == expected_tiles
    if isinstance(expected_tiles, int) and isinstance(metadata_tiles, int):
        summary["pointcloud_metadata_matches_manifest"] = metadata_tiles == expected_tiles
    if isinstance(actual_tiles, int) and isinstance(metadata_tiles, int):
        summary["pointcloud_metadata_matches_directory"] = metadata_tiles == actual_tiles

    return {
        "bundle_id": bundle.bundle_id,
        "site_id": bundle.site_id,
        "description": bundle.description,
        "manifest_path": str(bundle.manifest_path),
        "source": {
            "type": source.get("type"),
            "archive_path": archive_path,
            "archive_exists": archive_exists,
            "preferred_extract_dir": preferred_extract_dir,
            "preferred_extract_dir_exists": extract_dir_exists,
            "archive_members": source.get("archive_members", []),
        },
        "checks": checks,
        "summary": summary,
    }
