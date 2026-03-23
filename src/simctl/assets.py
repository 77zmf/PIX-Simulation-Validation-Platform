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
