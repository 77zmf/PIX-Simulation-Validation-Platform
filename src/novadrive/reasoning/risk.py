from __future__ import annotations

import math

from novadrive.foundation import EgoState, PredictedObject, RiskAssessment
from novadrive.foundation.geometry import distance_xy


class RiskAssessor:
    def __init__(self, *, lane_half_width_m: float = 2.4, safe_distance_m: float = 5.0, safe_ttc_sec: float = 1.8) -> None:
        self.lane_half_width_m = lane_half_width_m
        self.safe_distance_m = safe_distance_m
        self.safe_ttc_sec = safe_ttc_sec

    def assess(self, ego: EgoState, predictions: list[PredictedObject]) -> RiskAssessment:
        min_distance = math.inf
        min_ttc = 999.0
        blocking_track_id = None
        reason = "clear"

        for prediction in predictions:
            if not prediction.trajectory:
                continue
            first = prediction.trajectory[0]
            lateral_gap = abs(first.y - ego.position.y)
            distance = distance_xy(ego.position.x, ego.position.y, first.x, first.y)
            min_distance = min(min_distance, distance)
            closing_speed = max(0.0, ego.velocity_mps - prediction.velocity.x)
            ttc = distance / closing_speed if closing_speed > 0.2 else 999.0
            if lateral_gap <= self.lane_half_width_m and first.x >= ego.position.x - 2.0 and ttc < min_ttc:
                min_ttc = ttc
                blocking_track_id = prediction.track_id
                reason = "same_lane_or_merge_conflict"

        if math.isinf(min_distance):
            min_distance = 999.0
        collision_risk = min_distance < self.safe_distance_m or min_ttc < self.safe_ttc_sec
        return RiskAssessment(
            min_distance_m=min_distance,
            min_ttc_sec=min_ttc,
            collision_risk=collision_risk,
            blocking_track_id=blocking_track_id,
            reason=reason if collision_risk else "clear",
        )

