from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import find_repo_root, load_yaml


@dataclass(slots=True)
class SubagentSpec:
    spec_id: str
    name: str
    agent_type: str
    model: str
    reasoning_effort: str
    description: str
    prompt_template: str
    spec_path: Path

    def render_message(self, repo_root: Path) -> str:
        return self.prompt_template.format(repo_root=str(repo_root.resolve()))

    def as_payload(self, repo_root: Path) -> dict[str, Any]:
        resolved_root = repo_root.resolve()
        return {
            "spec_id": self.spec_id,
            "name": self.name,
            "description": self.description,
            "agent_type": self.agent_type,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "message": self.render_message(resolved_root),
            "spec_path": str(self.spec_path),
        }


def subagent_specs_root(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    path = root / "ops" / "subagents"
    if not path.exists():
        raise FileNotFoundError("Unable to locate subagent spec catalog")
    return path


def _load_spec(path: Path) -> SubagentSpec:
    payload = load_yaml(path)
    required = [
        "spec_id",
        "name",
        "agent_type",
        "model",
        "reasoning_effort",
        "description",
        "prompt_template",
    ]
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"{path} is missing required keys: {', '.join(missing)}")
    return SubagentSpec(
        spec_id=str(payload["spec_id"]),
        name=str(payload["name"]),
        agent_type=str(payload["agent_type"]),
        model=str(payload["model"]),
        reasoning_effort=str(payload["reasoning_effort"]),
        description=str(payload["description"]),
        prompt_template=str(payload["prompt_template"]),
        spec_path=path,
    )


def list_subagent_specs(repo_root: Path | None = None) -> list[SubagentSpec]:
    root = subagent_specs_root(repo_root)
    return sorted((_load_spec(path) for path in root.glob("*.yaml")), key=lambda spec: spec.spec_id)


def load_subagent_spec(spec_id: str, repo_root: Path | None = None) -> SubagentSpec:
    for spec in list_subagent_specs(repo_root):
        if spec.spec_id == spec_id:
            return spec
    raise FileNotFoundError(f"Unable to locate subagent spec '{spec_id}'")
