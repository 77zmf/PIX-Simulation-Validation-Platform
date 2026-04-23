from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from novadrive.foundation import DetectedObject, Vector3

from .provider import PerceptionSnapshot


class BEVFusionProvider:
    """Read BEVFusion detections from a JSON/JSONL handoff file.

    The provider deliberately consumes a small protocol instead of importing
    training or TensorRT internals. The latest object list can be either:

    {"timestamp": 1.0, "frame_id": "lidar", "detections": [...]}

    or a bare list of detections. JSONL files use the last non-empty line.
    """

    source = "bevfusion"

    def __init__(self, path: str | None, *, max_age_sec: float = 0.5) -> None:
        self.path = Path(path).expanduser().resolve() if path else None
        self.max_age_sec = max_age_sec

    def detect(self, timestamp: float) -> PerceptionSnapshot:
        if self.path is None:
            return PerceptionSnapshot(timestamp, self.source, healthy=False, reason="missing_bevfusion_path")
        if not self.path.exists():
            return PerceptionSnapshot(timestamp, self.source, healthy=False, reason=f"missing_file:{self.path}")
        try:
            payload = self._load_payload()
            detections = self._parse_detections(payload, timestamp)
        except Exception as exc:
            return PerceptionSnapshot(timestamp, self.source, healthy=False, reason=f"parse_failed:{exc}")

        mtime_age = max(0.0, time.time() - self.path.stat().st_mtime)
        if mtime_age > self.max_age_sec:
            return PerceptionSnapshot(
                timestamp,
                self.source,
                detections=detections,
                healthy=False,
                reason=f"stale_file:{mtime_age:.3f}s",
            )
        return PerceptionSnapshot(timestamp, self.source, detections=detections)

    def _load_payload(self) -> Any:
        text = self.path.read_text(encoding="utf-8")
        if self.path.suffix == ".jsonl":
            lines = [line for line in text.splitlines() if line.strip()]
            if not lines:
                return []
            return json.loads(lines[-1])
        return json.loads(text)

    def _parse_detections(self, payload: Any, timestamp: float) -> list[DetectedObject]:
        if isinstance(payload, dict):
            frame_id = str(payload.get("frame_id") or "lidar")
            source = str(payload.get("source") or self.source)
            timestamp = float(payload.get("timestamp", timestamp))
            raw_items = payload.get("detections", payload.get("objects", []))
        else:
            frame_id = "lidar"
            source = self.source
            raw_items = payload
        if not isinstance(raw_items, list):
            raise ValueError("detections must be a list")
        detections = []
        for index, item in enumerate(raw_items):
            if not isinstance(item, dict):
                continue
            detections.append(_detection_from_mapping(item, timestamp, frame_id, source, fallback_id=f"bev_{index}"))
        return detections


def _vector_from_any(value: Any, *, default_z: float = 0.0) -> Vector3:
    if isinstance(value, dict):
        return Vector3(float(value.get("x", 0.0)), float(value.get("y", 0.0)), float(value.get("z", default_z)))
    if isinstance(value, (list, tuple)):
        values = list(value) + [default_z, default_z, default_z]
        return Vector3(float(values[0]), float(values[1]), float(values[2]))
    return Vector3(0.0, 0.0, default_z)


def _detection_from_mapping(
    item: dict[str, Any],
    timestamp: float,
    frame_id: str,
    source: str,
    *,
    fallback_id: str,
) -> DetectedObject:
    center = _vector_from_any(item.get("center_xyz", item.get("center", item.get("translation"))))
    size = _vector_from_any(item.get("size_lwh", item.get("size", item.get("dimensions"))), default_z=1.0)
    velocity_value = item.get("velocity_xy", item.get("velocity"))
    velocity = _vector_from_any(velocity_value) if velocity_value is not None else None
    return DetectedObject(
        timestamp=float(item.get("timestamp", timestamp)),
        frame_id=str(item.get("frame_id", frame_id)),
        source=str(item.get("source", source)),
        object_id=str(item.get("object_id", item.get("track_id", fallback_id))),
        class_name=str(item.get("class_name", item.get("name", item.get("label", "unknown")))),
        score=float(item.get("score", item.get("confidence", 1.0))),
        center=center,
        size_lwh=size,
        yaw_rad=float(item.get("yaw", item.get("yaw_rad", 0.0))),
        velocity=velocity,
        covariance=item.get("covariance"),
    )

