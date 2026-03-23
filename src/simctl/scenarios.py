from __future__ import annotations

from pathlib import Path

from .config import find_repo_root, load_yaml
from .models import ScenarioConfig


def resolve_scenario_path(ref: str, repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    candidate = Path(ref)
    if candidate.exists():
        return candidate.resolve()
    manifest = root / ref
    if manifest.exists():
        return manifest.resolve()
    raise FileNotFoundError(f"Unable to locate scenario '{ref}'")


def load_scenario(ref: str, repo_root: Path | None = None) -> ScenarioConfig:
    scenario_path = resolve_scenario_path(ref, repo_root)
    return ScenarioConfig.from_dict(load_yaml(scenario_path), scenario_path)
