from __future__ import annotations

import math

from novadrive.foundation import BehaviorDecision, EgoState, PlannedTrajectory, TrajectoryPoint, Vector3
from novadrive.foundation.geometry import distance_xy


class ReferenceLinePlanner:
    def __init__(self, *, horizon_sec: float = 5.0, step_sec: float = 0.2) -> None:
        self.horizon_sec = horizon_sec
        self.step_sec = step_sec

    def route_completion(self, ego: EgoState, start: Vector3, goal: Vector3) -> float:
        total = max(1e-3, distance_xy(start.x, start.y, goal.x, goal.y))
        remaining = distance_xy(ego.position.x, ego.position.y, goal.x, goal.y)
        return max(0.0, min(1.0, 1.0 - remaining / total))

    def plan(self, ego: EgoState, goal: Vector3, behavior: BehaviorDecision) -> PlannedTrajectory:
        dx = goal.x - ego.position.x
        dy = goal.y - ego.position.y
        yaw = math.atan2(dy, dx) if abs(dx) + abs(dy) > 1e-6 else ego.yaw_rad
        points: list[TrajectoryPoint] = []
        speed = max(0.0, behavior.target_speed_mps)
        steps = max(1, int(self.horizon_sec / self.step_sec))
        for index in range(1, steps + 1):
            t = index * self.step_sec
            travel = speed * t
            points.append(
                TrajectoryPoint(
                    timestamp=ego.timestamp + t,
                    position=Vector3(
                        ego.position.x + math.cos(yaw) * travel,
                        ego.position.y + math.sin(yaw) * travel,
                        ego.position.z,
                    ),
                    yaw_rad=yaw,
                    target_speed_mps=speed,
                )
            )
        return PlannedTrajectory(frame_id=ego.frame_id, points=points, source="reference_line")

