from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from novadrive.foundation import RuntimeSample, to_jsonable


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


class RuntimeRecorder:
    def __init__(self, run_dir: Path, scenario_id: str) -> None:
        self.run_dir = run_dir
        self.scenario_id = scenario_id
        self.runtime_dir = run_dir / "runtime_verification"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.samples: list[RuntimeSample] = []
        self.events: list[dict[str, Any]] = []

    def add_sample(self, sample: RuntimeSample) -> None:
        self.samples.append(sample)

    def add_event(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    def write(self, payload: dict[str, Any]) -> Path:
        path = self.runtime_dir / f"novadrive_{self.scenario_id}_{utc_stamp()}.json"
        path.write_text(json.dumps(to_jsonable(payload), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        summary_path = self.runtime_dir / "novadrive_summary.json"
        summary_path.write_text(json.dumps(to_jsonable(payload.get("summary", {})), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        return path

