from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def require_keys(data: dict[str, Any], required: list[str], *, where: str) -> None:
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Missing keys in {where}: {', '.join(missing)}")


@dataclass(slots=True)
class CommandStep:
    name: str
    runner: str
    command: str
    background: bool = False
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, where: str) -> "CommandStep":
        require_keys(payload, ["name", "runner", "command"], where=where)
        return cls(
            name=str(payload["name"]),
            runner=str(payload["runner"]),
            command=str(payload["command"]),
            background=bool(payload.get("background", False)),
            cwd=str(payload["cwd"]) if payload.get("cwd") else None,
            env={str(k): str(v) for k, v in payload.get("env", {}).items()},
        )


@dataclass(slots=True)
class StackProfile:
    stack_id: str
    description: str
    software_versions: dict[str, str]
    bootstrap: list[CommandStep] = field(default_factory=list)
    start: list[CommandStep] = field(default_factory=list)
    stop: list[CommandStep] = field(default_factory=list)
    replay: list[CommandStep] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, where: str) -> "StackProfile":
        require_keys(payload, ["stack_id", "description", "software_versions"], where=where)
        return cls(
            stack_id=str(payload["stack_id"]),
            description=str(payload["description"]),
            software_versions={str(k): str(v) for k, v in payload["software_versions"].items()},
            bootstrap=[CommandStep.from_dict(item, where=f"{where}.bootstrap") for item in payload.get("bootstrap", [])],
            start=[CommandStep.from_dict(item, where=f"{where}.start") for item in payload.get("start", [])],
            stop=[CommandStep.from_dict(item, where=f"{where}.stop") for item in payload.get("stop", [])],
            replay=[CommandStep.from_dict(item, where=f"{where}.replay") for item in payload.get("replay", [])],
        )


@dataclass(slots=True)
class AssetBundle:
    bundle_id: str
    site_id: str
    description: str
    source: dict[str, Any]
    maps: dict[str, Any]
    metadata: dict[str, Any]
    manifest_path: Path

    @classmethod
    def from_dict(cls, payload: dict[str, Any], manifest_path: Path) -> "AssetBundle":
        require_keys(payload, ["bundle_id", "site_id", "description", "source", "maps", "metadata"], where=str(manifest_path))
        return cls(
            bundle_id=str(payload["bundle_id"]),
            site_id=str(payload["site_id"]),
            description=str(payload["description"]),
            source=payload["source"],
            maps=payload["maps"],
            metadata=payload["metadata"],
            manifest_path=manifest_path,
        )


@dataclass(slots=True)
class ScenarioConfig:
    scenario_id: str
    stack: str
    map_id: str
    asset_bundle: str
    ego_init: dict[str, Any]
    goal: dict[str, Any]
    traffic_profile: dict[str, Any]
    weather_profile: dict[str, Any]
    sensor_profile: str
    algorithm_profile: str
    seed: int
    recording: dict[str, Any]
    kpi_gate: str
    labels: list[str]
    execution: dict[str, Any]
    scenario_path: Path

    @classmethod
    def from_dict(cls, payload: dict[str, Any], scenario_path: Path) -> "ScenarioConfig":
        require_keys(
            payload,
            [
                "scenario_id",
                "stack",
                "map_id",
                "asset_bundle",
                "ego_init",
                "goal",
                "traffic_profile",
                "weather_profile",
                "sensor_profile",
                "algorithm_profile",
                "seed",
                "recording",
                "kpi_gate",
            ],
            where=str(scenario_path),
        )
        stack = str(payload["stack"])
        if stack not in {"stable", "ue5"}:
            raise ValueError(f"{scenario_path} has unsupported stack '{stack}'")
        return cls(
            scenario_id=str(payload["scenario_id"]),
            stack=stack,
            map_id=str(payload["map_id"]),
            asset_bundle=str(payload["asset_bundle"]),
            ego_init=payload["ego_init"],
            goal=payload["goal"],
            traffic_profile=payload["traffic_profile"],
            weather_profile=payload["weather_profile"],
            sensor_profile=str(payload["sensor_profile"]),
            algorithm_profile=str(payload["algorithm_profile"]),
            seed=int(payload["seed"]),
            recording=payload["recording"],
            kpi_gate=str(payload["kpi_gate"]),
            labels=[str(item) for item in payload.get("labels", [])],
            execution=payload.get("execution", {"mode": "external"}),
            scenario_path=scenario_path,
        )


@dataclass(slots=True)
class KpiGate:
    gate_id: str
    description: str
    metrics: dict[str, dict[str, Any]]
    failure_labels: list[str]
    gate_path: Path

    @classmethod
    def from_dict(cls, payload: dict[str, Any], gate_path: Path) -> "KpiGate":
        require_keys(payload, ["gate_id", "description", "metrics"], where=str(gate_path))
        return cls(
            gate_id=str(payload["gate_id"]),
            description=str(payload["description"]),
            metrics={str(k): dict(v) for k, v in payload["metrics"].items()},
            failure_labels=[str(item) for item in payload.get("failure_labels", [])],
            gate_path=gate_path,
        )
