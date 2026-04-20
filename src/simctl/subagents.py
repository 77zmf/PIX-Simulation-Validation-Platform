from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import find_repo_root, load_yaml


@dataclass
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

    def spawn_agent_payload(self, repo_root: Path) -> dict[str, Any]:
        resolved_root = repo_root.resolve()
        return {
            "agent_type": self.agent_type,
            "fork_context": True,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "message": self.render_message(resolved_root),
        }

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
            "spawn_agent_parameters": self.spawn_agent_payload(resolved_root),
        }


@dataclass(slots=True)
class OnboardingProfile:
    profile_id: str
    display_name: str
    description: str
    reading_order: list[str]
    recommended_subagents: list[str]
    related_skills: list[str]
    starter_commands: list[str]
    issue_sync_format: list[str]
    notes: list[str]
    source_path: Path

    def as_payload(self, repo_root: Path) -> dict[str, Any]:
        resolved_root = repo_root.resolve()
        spec_lookup = {spec.spec_id: spec for spec in list_subagent_specs(resolved_root)}
        recommended_specs = []
        for spec_id in self.recommended_subagents:
            spec = spec_lookup.get(spec_id)
            recommended_specs.append(
                {
                    "spec_id": spec_id,
                    "name": spec.name if spec else spec_id,
                    "description": spec.description if spec else None,
                    "show_command": f"python -m simctl subagent-spec --name {spec_id}",
                    "spawn_json_command": f"python -m simctl subagent-spec --name {spec_id} --format spawn_json",
                }
            )

        skills = []
        for skill_name in self.related_skills:
            skill_path = resolved_root / "ops" / "skills" / skill_name / "SKILL.md"
            skills.append(
                {
                    "skill_id": skill_name,
                    "skill_path": str(skill_path),
                    "exists": skill_path.exists(),
                }
            )

        return {
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "description": self.description,
            "reading_order": self.reading_order,
            "recommended_subagents": recommended_specs,
            "related_skills": skills,
            "starter_commands": self.starter_commands,
            "issue_sync_format": self.issue_sync_format,
            "notes": self.notes,
            "source_path": str(self.source_path),
        }


def subagent_specs_root(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    path = root / "ops" / "subagents"
    if not path.exists():
        raise FileNotFoundError("Unable to locate subagent spec catalog")
    return path


def onboarding_profiles_path(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    path = root / "ops" / "subagents" / "onboarding" / "profiles.yaml"
    if not path.exists():
        raise FileNotFoundError("Unable to locate onboarding profile catalog")
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


def _load_onboarding_profile_catalog(path: Path) -> dict[str, Any]:
    payload = load_yaml(path)
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError(f"{path} must define a top-level 'profiles' mapping")
    return profiles


def _load_onboarding_profile(profile_id: str, payload: dict[str, Any], source_path: Path) -> OnboardingProfile:
    required = [
        "display_name",
        "description",
        "reading_order",
        "recommended_subagents",
        "related_skills",
        "starter_commands",
        "issue_sync_format",
        "notes",
    ]
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"{source_path} onboarding profile '{profile_id}' is missing required keys: {', '.join(missing)}")

    return OnboardingProfile(
        profile_id=profile_id,
        display_name=str(payload["display_name"]),
        description=str(payload["description"]),
        reading_order=[str(item) for item in payload["reading_order"]],
        recommended_subagents=[str(item) for item in payload["recommended_subagents"]],
        related_skills=[str(item) for item in payload["related_skills"]],
        starter_commands=[str(item) for item in payload["starter_commands"]],
        issue_sync_format=[str(item) for item in payload["issue_sync_format"]],
        notes=[str(item) for item in payload["notes"]],
        source_path=source_path,
    )


def list_subagent_specs(repo_root: Path | None = None) -> list[SubagentSpec]:
    root = subagent_specs_root(repo_root)
    return sorted((_load_spec(path) for path in root.glob("*.yaml")), key=lambda spec: spec.spec_id)


def list_onboarding_profiles(repo_root: Path | None = None) -> list[OnboardingProfile]:
    path = onboarding_profiles_path(repo_root)
    payload = _load_onboarding_profile_catalog(path)
    return sorted(
        (_load_onboarding_profile(profile_id, profile_payload, path) for profile_id, profile_payload in payload.items()),
        key=lambda profile: profile.profile_id,
    )


def load_subagent_spec(spec_id: str, repo_root: Path | None = None) -> SubagentSpec:
    for spec in list_subagent_specs(repo_root):
        if spec.spec_id == spec_id:
            return spec
    raise FileNotFoundError(f"Unable to locate subagent spec '{spec_id}'")


def load_onboarding_profile(profile_id: str, repo_root: Path | None = None) -> OnboardingProfile:
    for profile in list_onboarding_profiles(repo_root):
        if profile.profile_id == profile_id:
            return profile
    raise FileNotFoundError(f"Unable to locate onboarding profile '{profile_id}'")
