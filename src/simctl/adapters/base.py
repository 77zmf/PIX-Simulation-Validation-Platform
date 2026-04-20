from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdapterContext:
    run_id: str
    scenario_id: str
    stack: str
    sensor_profile: str
    algorithm_profile: str
    metadata: dict[str, Any] = field(default_factory=dict)
