from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from novadrive.foundation import Vector3


@dataclass
class NovaDriveActorSpec:
    name: str
    type_id: str
    start: Vector3
    yaw_deg: float = 0.0
    final_y: float | None = None
    speed_x_mps: float = 0.0
    activation_sec: float = 0.0


@dataclass
class NovaDriveScenario:
    scenario_id: str
    scenario_path: Path
    map_id: str
    start: Vector3
    goal: Vector3
    start_yaw_deg: float = 0.0
    target_speed_mps: float = 4.0
    max_duration_sec: float = 45.0
    perception_source: str = "carla_truth"
    actors: list[NovaDriveActorSpec] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


def load_novadrive_scenario(path: str | Path) -> NovaDriveScenario:
    scenario_path = Path(path).resolve()
    payload = yaml.safe_load(scenario_path.read_text(encoding="utf-8")) or {}
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    novadrive = execution.get("novadrive") if isinstance(execution.get("novadrive"), dict) else {}
    ego_init = payload.get("ego_init", {})
    goal = payload.get("goal", {})
    start_pose = _pose_from(ego_init.get("pose", ego_init), default_y_sign=-1.0)
    goal_pose = _pose_from(goal.get("pose", goal), default_y_sign=-1.0)
    if "start_carla" in novadrive:
        start_pose = _pose_from(novadrive["start_carla"], default_y_sign=1.0)
    if "goal_carla" in novadrive:
        goal_pose = _pose_from(novadrive["goal_carla"], default_y_sign=1.0)
    return NovaDriveScenario(
        scenario_id=str(payload["scenario_id"]),
        scenario_path=scenario_path,
        map_id=str(payload.get("map_id", "Town01")),
        start=start_pose,
        goal=goal_pose,
        start_yaw_deg=float(_first_present(novadrive, ["start_yaw_deg"], ego_init.get("pose", {}), ["yaw_deg", "yaw"], default=0.0)),
        target_speed_mps=float(novadrive.get("target_speed_mps", 4.0)),
        max_duration_sec=float(novadrive.get("max_duration_sec", 45.0)),
        perception_source=str(novadrive.get("perception_source", "carla_truth")),
        actors=_actor_specs(payload.get("traffic_profile", {}).get("novadrive_actors", [])),
        payload=payload,
    )


def _first_present(primary: dict[str, Any], primary_keys: list[str], secondary: dict[str, Any], secondary_keys: list[str], *, default: Any) -> Any:
    for key in primary_keys:
        if key in primary:
            return primary[key]
    for key in secondary_keys:
        if key in secondary:
            return secondary[key]
    return default


def _pose_from(payload: dict[str, Any], *, default_y_sign: float) -> Vector3:
    if not isinstance(payload, dict):
        return Vector3(0.0, 0.0, 0.0)
    x = float(payload.get("x", 0.0))
    y = float(payload.get("y", 0.0))
    z = float(payload.get("z", 0.0))
    if payload.get("coordinate") == "map_y_flip":
        y = -y
    elif "coordinate" not in payload and default_y_sign > 0.0 and y < 0.0:
        y = -y
    return Vector3(x, y, z)


def _actor_specs(raw_items: Any) -> list[NovaDriveActorSpec]:
    if not isinstance(raw_items, list):
        return []
    actors: list[NovaDriveActorSpec] = []
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        start = _pose_from(item.get("start", {}), default_y_sign=1.0)
        actors.append(
            NovaDriveActorSpec(
                name=str(item.get("name", f"actor_{index}")),
                type_id=str(item.get("type_id", "vehicle.audi.tt")),
                start=start,
                yaw_deg=float(item.get("yaw_deg", item.get("yaw", 0.0))),
                final_y=float(item["final_y"]) if item.get("final_y") is not None else None,
                speed_x_mps=float(item.get("speed_x_mps", 0.0)),
                activation_sec=float(item.get("activation_sec", 0.0)),
            )
        )
    return actors

