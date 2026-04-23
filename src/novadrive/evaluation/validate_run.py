from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate NovaDrive runtime artifacts exist and are parseable")
    parser.add_argument("--run-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    runtime_dir = run_dir / "runtime_verification"
    artifacts = sorted(path for path in runtime_dir.glob("novadrive_*.json") if path.name != "novadrive_summary.json")
    if not artifacts:
        print(f"No NovaDrive evidence found under {runtime_dir}")
        return 1
    latest = artifacts[-1]
    payload = json.loads(latest.read_text(encoding="utf-8"))
    if payload.get("kind") != "novadrive_run":
        print(f"Unexpected NovaDrive artifact kind in {latest}: {payload.get('kind')}")
        return 1
    print(json.dumps({"status": "passed", "artifact": str(latest), "metrics": payload.get("metrics", {})}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

