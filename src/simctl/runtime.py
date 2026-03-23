from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .config import dump_json, ensure_dir, find_repo_root, interpolate, load_yaml, to_wsl_path
from .models import CommandStep, ScenarioConfig, StackProfile


class SafeDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def load_stack_profile(stack_id: str, repo_root: Path | None = None) -> StackProfile:
    root = repo_root or find_repo_root()
    profile_path = root / "stack" / "profiles" / f"{stack_id}.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"Unable to locate stack profile '{stack_id}'")
    payload = interpolate(load_yaml(profile_path), {"REPO_ROOT": str(root)})
    return StackProfile.from_dict(payload, where=str(profile_path))


def build_context(
    repo_root: Path,
    run_dir: Path | None,
    scenario: ScenarioConfig | None,
    asset_root: Path,
    asset_bundle_id: str = "",
    execute: bool = False,
) -> dict[str, str]:
    scenario_path = scenario.scenario_path if scenario else None
    context = {
        "repo_root": str(repo_root),
        "repo_root_wsl": to_wsl_path(repo_root),
        "asset_root": str(asset_root),
        "asset_root_wsl": to_wsl_path(asset_root),
        "run_dir": str(run_dir) if run_dir else "",
        "run_dir_wsl": to_wsl_path(run_dir) if run_dir else "",
        "scenario_id": scenario.scenario_id if scenario else "",
        "scenario_path": str(scenario_path) if scenario_path else "",
        "scenario_path_wsl": to_wsl_path(scenario_path) if scenario_path else "",
        "asset_bundle_id": asset_bundle_id,
        "execute_flag": "-Execute" if execute else "",
    }
    return context


def render_step(step: CommandStep, context: dict[str, str]) -> dict[str, Any]:
    return {
        "name": step.name,
        "runner": step.runner,
        "background": step.background,
        "cwd": step.cwd.format_map(SafeDict(context)) if step.cwd else None,
        "command": step.command.format_map(SafeDict(context)),
        "env": {key: value.format_map(SafeDict(context)) for key, value in step.env.items()},
    }


def render_action(profile: StackProfile, action: str, context: dict[str, str]) -> dict[str, Any]:
    steps = getattr(profile, action)
    return {
        "stack_id": profile.stack_id,
        "description": profile.description,
        "action": action,
        "software_versions": profile.software_versions,
        "steps": [render_step(step, context) for step in steps],
    }


def execute_plan(plan: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    command_dir = ensure_dir(run_dir / "command_logs")
    for index, step in enumerate(plan["steps"], start=1):
        log_path = command_dir / f"{index:02d}_{step['name'].replace(' ', '_')}.log"
        command = step["command"]
        if step["background"]:
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=step["cwd"] or None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            log_path.write_text(f"[background pid={process.pid}]\n{command}\n", encoding="utf-8")
            logs.append({"step": step["name"], "status": "started", "pid": process.pid, "log_path": str(log_path)})
            continue

        completed = subprocess.run(
            command,
            shell=True,
            cwd=step["cwd"] or None,
            capture_output=True,
            text=True,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        log_path.write_text(output, encoding="utf-8")
        logs.append(
            {
                "step": step["name"],
                "status": "completed" if completed.returncode == 0 else "failed",
                "returncode": completed.returncode,
                "log_path": str(log_path),
            }
        )
        if completed.returncode != 0:
            break
    return logs


def persist_plan(run_dir: Path, action: str, plan: dict[str, Any]) -> Path:
    plan_path = run_dir / f"{action}_plan.json"
    dump_json(plan_path, plan)
    return plan_path
