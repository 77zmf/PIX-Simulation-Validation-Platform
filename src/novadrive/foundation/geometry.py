from __future__ import annotations

import math


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def distance_xy(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def wrap_angle(angle_rad: float) -> float:
    return (angle_rad + math.pi) % (2.0 * math.pi) - math.pi


def heading_error(target_yaw_rad: float, current_yaw_rad: float) -> float:
    return wrap_angle(target_yaw_rad - current_yaw_rad)


def yaw_to_vector(yaw_rad: float) -> tuple[float, float]:
    return math.cos(yaw_rad), math.sin(yaw_rad)

