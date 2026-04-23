from __future__ import annotations

from novadrive.foundation import DetectedObject, EgoState, PredictedObject, TrackedObject, Vector3, WorldState


class WorldModelBuilder:
    def build(
        self,
        *,
        timestamp: float,
        ego: EgoState,
        detections: list[DetectedObject],
        tracks: list[TrackedObject],
        predictions: list[PredictedObject],
        route_goal: Vector3,
        metadata: dict[str, object] | None = None,
    ) -> WorldState:
        return WorldState(
            timestamp=timestamp,
            frame_id=ego.frame_id,
            ego=ego,
            detections=detections,
            tracks=tracks,
            predictions=predictions,
            route_goal=route_goal,
            metadata=dict(metadata or {}),
        )

