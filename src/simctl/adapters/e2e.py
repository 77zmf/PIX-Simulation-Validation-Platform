from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .base import AdapterContext


@dataclass(slots=True)
class E2EOutput:
    shadow_only: bool = True
    planned_trajectory: dict[str, Any] = field(default_factory=dict)
    proposed_control: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class E2EAdapter(ABC):
    @abstractmethod
    def shadow_evaluate(self, context: AdapterContext, sensor_frames: dict[str, Any], baseline_output: dict[str, Any]) -> E2EOutput:
        raise NotImplementedError
