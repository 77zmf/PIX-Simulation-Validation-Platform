from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimeStatus(str, Enum):
    INIT = "INIT"
    READY = "READY"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    STOPPING = "STOPPING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


@dataclass
class Vector3:
    x: float
    y: float
    z: float = 0.0


@dataclass
class EgoState:
    timestamp: float
    frame_id: str
    position: Vector3
    yaw_rad: float
    velocity_mps: float = 0.0
    acceleration_mps2: float = 0.0


@dataclass
class SensorFrame:
    timestamp: float
    frame_id: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectedObject:
    timestamp: float
    frame_id: str
    source: str
    class_name: str
    score: float
    center: Vector3
    size_lwh: Vector3
    yaw_rad: float
    object_id: str | None = None
    velocity: Vector3 | None = None
    covariance: list[float] | None = None


@dataclass
class TrackedObject:
    track_id: str
    detection: DetectedObject
    age: int
    missed: int = 0
    history: list[DetectedObject] = field(default_factory=list)

    @property
    def center(self) -> Vector3:
        return self.detection.center

    @property
    def velocity(self) -> Vector3:
        if self.detection.velocity is not None:
            return self.detection.velocity
        if len(self.history) < 2:
            return Vector3(0.0, 0.0, 0.0)
        prev = self.history[-2]
        curr = self.history[-1]
        dt = max(1e-3, curr.timestamp - prev.timestamp)
        return Vector3(
            (curr.center.x - prev.center.x) / dt,
            (curr.center.y - prev.center.y) / dt,
            (curr.center.z - prev.center.z) / dt,
        )


@dataclass
class PredictedObject:
    track_id: str
    class_name: str
    probability: float
    trajectory: list[Vector3]
    velocity: Vector3


@dataclass
class WorldState:
    timestamp: float
    frame_id: str
    ego: EgoState
    detections: list[DetectedObject] = field(default_factory=list)
    tracks: list[TrackedObject] = field(default_factory=list)
    predictions: list[PredictedObject] = field(default_factory=list)
    route_goal: Vector3 | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskAssessment:
    min_distance_m: float
    min_ttc_sec: float
    collision_risk: bool
    blocking_track_id: str | None = None
    reason: str = "clear"


@dataclass
class BehaviorDecision:
    mode: str
    target_speed_mps: float
    reason: str
    blocking_track_id: str | None = None


@dataclass
class TrajectoryPoint:
    timestamp: float
    position: Vector3
    yaw_rad: float
    target_speed_mps: float


@dataclass
class PlannedTrajectory:
    frame_id: str
    points: list[TrajectoryPoint]
    source: str
    valid: bool = True
    reason: str = "ok"


@dataclass
class ControlCommand:
    timestamp: float
    throttle: float
    brake: float
    steer: float
    target_speed_mps: float
    reason: str


@dataclass
class RuntimeSample:
    timestamp: float
    ego: EgoState
    behavior: BehaviorDecision
    risk: RiskAssessment
    control: ControlCommand
    route_completion: float
    detection_count: int
    track_count: int


@dataclass
class RuntimeEvidence:
    scenario_id: str
    run_id: str
    runtime_status: RuntimeStatus
    perception_source: str
    samples: list[RuntimeSample]
    metrics: dict[str, float]
    events: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    failure_reason: str | None = None


def to_jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {field.name: to_jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value

