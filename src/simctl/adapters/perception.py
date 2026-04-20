from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .base import AdapterContext


@dataclass
class PerceptionOutput:
    detections: list[dict[str, Any]] = field(default_factory=list)
    occupancy: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)


class PerceptionAdapter(ABC):
    @abstractmethod
    def infer(self, context: AdapterContext, sensor_frames: dict[str, Any]) -> PerceptionOutput:
        raise NotImplementedError
