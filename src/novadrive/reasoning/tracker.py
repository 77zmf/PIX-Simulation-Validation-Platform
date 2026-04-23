from __future__ import annotations

from novadrive.foundation import DetectedObject, TrackedObject
from novadrive.foundation.geometry import distance_xy


class NearestNeighborTracker:
    def __init__(self, *, max_match_distance_m: float = 4.0, max_missed: int = 5) -> None:
        self.max_match_distance_m = max_match_distance_m
        self.max_missed = max_missed
        self._next_track_id = 1
        self._tracks: dict[str, TrackedObject] = {}

    def update(self, detections: list[DetectedObject]) -> list[TrackedObject]:
        unmatched_tracks = set(self._tracks)
        updated: dict[str, TrackedObject] = {}

        for detection in detections:
            best_id = None
            best_distance = self.max_match_distance_m
            for track_id in list(unmatched_tracks):
                track = self._tracks[track_id]
                d = distance_xy(
                    track.center.x,
                    track.center.y,
                    detection.center.x,
                    detection.center.y,
                )
                if d <= best_distance:
                    best_id = track_id
                    best_distance = d
            if best_id is None:
                track_id = f"trk_{self._next_track_id:05d}"
                self._next_track_id += 1
                updated[track_id] = TrackedObject(track_id=track_id, detection=detection, age=1, history=[detection])
                continue

            old = self._tracks[best_id]
            history = [*old.history, detection][-20:]
            updated[best_id] = TrackedObject(
                track_id=best_id,
                detection=detection,
                age=old.age + 1,
                missed=0,
                history=history,
            )
            unmatched_tracks.discard(best_id)

        for track_id in unmatched_tracks:
            old = self._tracks[track_id]
            if old.missed + 1 <= self.max_missed:
                updated[track_id] = TrackedObject(
                    track_id=track_id,
                    detection=old.detection,
                    age=old.age,
                    missed=old.missed + 1,
                    history=old.history,
                )

        self._tracks = updated
        return list(self._tracks.values())

