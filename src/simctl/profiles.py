from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import find_repo_root, load_yaml
from .models import AlgorithmProfile, SensorProfile


def sensor_profiles_path(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    path = root / "assets" / "sensors" / "profiles.yaml"
    if not path.exists():
        raise FileNotFoundError("Unable to locate sensor profile catalog")
    return path


def load_sensor_profile(profile_id: str, repo_root: Path | None = None) -> SensorProfile:
    path = sensor_profiles_path(repo_root)
    payload = load_yaml(path)
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError(f"{path} must contain a top-level 'profiles' mapping")
    entry = profiles.get(profile_id)
    if entry is None:
        raise FileNotFoundError(f"Unable to locate sensor profile '{profile_id}'")
    if not isinstance(entry, dict):
        raise ValueError(f"{path}:{profile_id} must contain a YAML mapping")
    return SensorProfile.from_catalog_entry(profile_id, entry, path)


def algorithm_profile_path(profile_ref: str, repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    candidate = Path(profile_ref)
    if candidate.exists():
        return candidate.resolve()
    path = root / "adapters" / "profiles" / f"{profile_ref}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Unable to locate algorithm profile '{profile_ref}'")
    return path


def load_algorithm_profile(profile_ref: str, repo_root: Path | None = None) -> AlgorithmProfile:
    path = algorithm_profile_path(profile_ref, repo_root)
    return AlgorithmProfile.from_dict(load_yaml(path), path)


def sensor_profile_snapshot(profile: SensorProfile) -> dict[str, Any]:
    return {**profile.payload, "profile_path": str(profile.profile_path)}


def algorithm_profile_snapshot(profile: AlgorithmProfile) -> dict[str, Any]:
    return {**profile.payload, "profile_path": str(profile.profile_path)}
