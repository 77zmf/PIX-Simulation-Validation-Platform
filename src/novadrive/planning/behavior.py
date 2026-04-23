from __future__ import annotations

from novadrive.foundation import BehaviorDecision, RiskAssessment


class BehaviorPlanner:
    def __init__(self, *, cruise_speed_mps: float = 4.0, yield_speed_mps: float = 1.5) -> None:
        self.cruise_speed_mps = cruise_speed_mps
        self.yield_speed_mps = yield_speed_mps

    def decide(self, risk: RiskAssessment, *, route_completion: float) -> BehaviorDecision:
        if route_completion >= 0.98:
            return BehaviorDecision("STOP", 0.0, "near_goal", risk.blocking_track_id)
        if risk.min_distance_m < 3.0:
            return BehaviorDecision("BRAKE", 0.0, "distance_critical", risk.blocking_track_id)
        if risk.collision_risk:
            return BehaviorDecision("YIELD", self.yield_speed_mps, risk.reason, risk.blocking_track_id)
        return BehaviorDecision("KEEP_LANE", self.cruise_speed_mps, "clear")

