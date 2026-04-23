from __future__ import annotations

from novadrive.foundation import PredictedObject, TrackedObject, Vector3


class ConstantVelocityPredictor:
    def __init__(self, *, horizon_sec: float = 5.0, step_sec: float = 0.5) -> None:
        self.horizon_sec = horizon_sec
        self.step_sec = step_sec

    def predict(self, tracks: list[TrackedObject]) -> list[PredictedObject]:
        predictions: list[PredictedObject] = []
        steps = max(1, int(self.horizon_sec / self.step_sec))
        for track in tracks:
            center = track.center
            velocity = track.velocity
            trajectory = [
                Vector3(
                    center.x + velocity.x * self.step_sec * index,
                    center.y + velocity.y * self.step_sec * index,
                    center.z + velocity.z * self.step_sec * index,
                )
                for index in range(1, steps + 1)
            ]
            predictions.append(
                PredictedObject(
                    track_id=track.track_id,
                    class_name=track.detection.class_name,
                    probability=max(0.1, min(1.0, track.detection.score)),
                    trajectory=trajectory,
                    velocity=velocity,
                )
            )
        return predictions

