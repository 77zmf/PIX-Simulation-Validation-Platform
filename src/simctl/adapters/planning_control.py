from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .base import AdapterContext


@dataclass
class PlanningControlOutput:
    trajectory_source: str
    control_source: str
    metrics: dict[str, float] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class PlanningControlAdapter(ABC):
    @abstractmethod
    def evaluate(self, context: AdapterContext, localization: dict[str, Any], map_data: dict[str, Any], obstacles: dict[str, Any]) -> PlanningControlOutput:
        raise NotImplementedError
