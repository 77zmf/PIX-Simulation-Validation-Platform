from __future__ import annotations

import zipfile
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


def _probe_resolved_path(raw_path: str) -> dict[str, Any]:
    if not raw_path:
        return {"path": "", "exists": False, "kind": "missing"}
    if "://" in raw_path:
        return {"path": raw_path, "exists": True, "kind": "virtual"}
    path = Path(raw_path)
    return {
        "path": str(path),
        "exists": path.exists(),
        "kind": "directory" if path.exists() and path.is_dir() else "file",
    }


def _inspect_map_entry(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    primary = _probe_resolved_path(str(payload.get("path", "")))
    fallback = None
    selected = None

    if primary["exists"]:
        selected = {"origin": "primary", "path": primary["path"], "kind": primary["kind"]}
    elif payload.get("fallback_repo_path"):
        fallback = _probe_resolved_path(str(payload["fallback_repo_path"]))
        if fallback["exists"]:
            selected = {"origin": "fallback", "path": fallback["path"], "kind": fallback["kind"]}

    return {
        "name": name,
        "primary": primary,
        "fallback": fallback,
        "selected": selected,
        "ready": selected is not None,
    }


def _inspect_source(payload: dict[str, Any]) -> dict[str, Any]:
    source_type = str(payload.get("type", "unknown"))
    report: dict[str, Any] = {"type": source_type}
    if source_type != "local_archive":
        report["ready"] = True
        return report

    archive = _probe_resolved_path(str(payload.get("archive_path", "")))
    extract_dir = _probe_resolved_path(str(payload.get("preferred_extract_dir", "")))
    archive_members = [str(item) for item in payload.get("archive_members", [])]
    member_checks: list[dict[str, Any]] = []

    if archive["exists"] and archive["path"].lower().endswith(".zip"):
        with zipfile.ZipFile(archive["path"]) as archive_file:
            names = set(archive_file.namelist())
        member_checks = [{"member": member, "present": member in names} for member in archive_members]
    else:
        member_checks = [{"member": member, "present": False} for member in archive_members]

    report.update(
        {
            "archive": archive,
            "preferred_extract_dir": extract_dir,
            "archive_members": member_checks,
            "archive_members_ready": all(item["present"] for item in member_checks) if member_checks else True,
            "ready": archive["exists"] or extract_dir["exists"],
        }
    )
    return report


def inspect_asset_bundle(bundle: AssetBundle) -> dict[str, Any]:
    maps = {
        name: _inspect_map_entry(name, payload)
        for name, payload in bundle.maps.items()
    }
    source = _inspect_source(bundle.source)
    missing_required = [name for name, payload in maps.items() if not payload["ready"]]
    warnings: list[str] = []
    if not source.get("archive", {}).get("exists", True):
        warnings.append("source_archive_missing")
    if not source.get("archive_members_ready", True):
        warnings.append("source_archive_members_incomplete")

    return {
        "bundle_id": bundle.bundle_id,
        "site_id": bundle.site_id,
        "description": bundle.description,
        "manifest_path": str(bundle.manifest_path),
        "source": source,
        "maps": maps,
        "metadata": bundle.metadata,
        "summary": {
            "passed": not missing_required,
            "missing_required": missing_required,
            "warnings": warnings,
        },
    }
