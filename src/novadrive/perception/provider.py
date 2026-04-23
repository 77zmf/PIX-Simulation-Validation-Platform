from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from novadrive.foundation import DetectedObject


@dataclass
class PerceptionSnapshot:
    timestamp: float
    source: str
    detections: list[DetectedObject] = field(default_factory=list)
    healthy: bool = True
    reason: str = "ok"


class PerceptionProvider(Protocol):
    source: str

    def detect(self, timestamp: float) -> PerceptionSnapshot:
        ...

