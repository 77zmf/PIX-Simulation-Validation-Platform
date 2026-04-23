from __future__ import annotations

import math

from novadrive.foundation import ControlCommand, EgoState, PlannedTrajectory
from novadrive.foundation.geometry import clamp, heading_error


class PurePursuitPidController:
    def __init__(self, *, kp_speed: float = 0.35, lookahead_index: int = 5) -> None:
        self.kp_speed = kp_speed
        self.lookahead_index = lookahead_index

    def control(self, ego: EgoState, trajectory: PlannedTrajectory) -> ControlCommand:
        if not trajectory.valid or not trajectory.points:
            return ControlCommand(ego.timestamp, throttle=0.0, brake=1.0, steer=0.0, target_speed_mps=0.0, reason="invalid_trajectory")

        target = trajectory.points[min(self.lookahead_index, len(trajectory.points) - 1)]
        target_yaw = math.atan2(target.position.y - ego.position.y, target.position.x - ego.position.x)
        steer = clamp(heading_error(target_yaw, ego.yaw_rad) / 0.65, -1.0, 1.0)
        speed_error = target.target_speed_mps - ego.velocity_mps
        if speed_error >= 0:
            throttle = clamp(speed_error * self.kp_speed, 0.0, 0.7)
            brake = 0.0
        else:
            throttle = 0.0
            brake = clamp(-speed_error * 0.45, 0.0, 1.0)
        return ControlCommand(
            timestamp=ego.timestamp,
            throttle=throttle,
            brake=brake,
            steer=steer,
            target_speed_mps=target.target_speed_mps,
            reason=trajectory.reason,
        )

