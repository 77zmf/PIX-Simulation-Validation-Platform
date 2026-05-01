#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROBE_ID = "metric_probe_codex_stub_smoke"


def write_stub_metric_probe(run_dir: Path) -> dict[str, Any]:
    output_dir = run_dir / "runtime_verification" / PROBE_ID
    output_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "kind": "stub_metric_probe",
        "profile": "codex_stub_smoke",
        "scope": "stub_only",
        "overall_passed": True,
        "metrics": {
            "route_completion": 1.0,
            "collision_count": 0.0,
            "min_ttc_sec": 999.0,
        },
        "assumptions": [
            "not_ubuntu_runtime_acceptance",
            "not_real_carla_autoware_evidence",
            "for_repo_local_closure_audit_only",
        ],
    }
    output_path = output_dir / f"{PROBE_ID}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Write stub-only metric probe evidence for Codex audits.")
    parser.add_argument("--run-dir", required=True, help="Existing simctl run directory")
    args = parser.parse_args()
    payload = write_stub_metric_probe(Path(args.run_dir))
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
