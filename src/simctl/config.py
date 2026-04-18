from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT_MARKERS = ("pyproject.toml", ".git")
ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if any((candidate / marker).exists() for marker in ROOT_MARKERS):
            return candidate
    raise FileNotFoundError("Unable to locate repository root from current directory")


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping at the top level")
    return data


def dump_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def dump_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_run_id(scenario_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", scenario_id).strip("-")
    return f"{stamp}__{safe}"


def to_wsl_path(path: str | Path) -> str:
    raw = str(path)
    if len(raw) >= 2 and raw[1] == ":":
        drive = raw[0].lower()
        tail = raw[2:].replace("\\", "/").lstrip("/")
        return f"/mnt/{drive}/{tail}"
    posix_path = Path(raw)
    if posix_path.is_absolute():
        return raw
    return str(posix_path.resolve())


def interpolate(value: Any, context: dict[str, str]) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key in context:
                return context[key]
            return os.environ.get(key, match.group(0))

        return ENV_PATTERN.sub(replace, value)
    if isinstance(value, dict):
        return {k: interpolate(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [interpolate(item, context) for item in value]
    return value
