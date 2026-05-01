#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - best effort helper
        return {"_error": f"failed to parse {path}: {exc}"}


def find_latest(run_root: Path, filename: str) -> Path | None:
    matches = sorted(run_root.rglob(filename), key=lambda p: p.stat().st_mtime)
    return matches[-1] if matches else None


def summarize_run(run_root: Path) -> dict[str, Any]:
    latest_run_result = find_latest(run_root, "run_result.json")
    latest_report_summary = find_latest(run_root, "summary.json")
    latest_health = find_latest(run_root, "health.json")
    latest_runtime_evidence = find_latest(run_root, "runtime_evidence_summary.json")

    run_result = load_json(latest_run_result) if latest_run_result else None
    report_summary = load_json(latest_report_summary) if latest_report_summary else None
    health = load_json(latest_health) if latest_health else None

    status = None
    reason = None
    top_keys: list[str] = []
    finalized = False
    if isinstance(run_result, dict):
        status = run_result.get("status") or run_result.get("run_status")
        reason = run_result.get("reason") or run_result.get("failure_reason") or run_result.get("message")
        top_keys = sorted(run_result.keys())
        finalized = bool(run_result.get("finalized_at") or run_result.get("finalized_by"))
        artifacts = run_result.get("artifacts") if isinstance(run_result.get("artifacts"), dict) else {}
        evidence_ref = run_result.get("runtime_evidence_path") or artifacts.get("runtime_evidence_summary")
        if evidence_ref:
            evidence_path = Path(str(evidence_ref))
            if evidence_path.exists():
                latest_runtime_evidence = evidence_path

    chain = {
        "run_result": bool(latest_run_result),
        "report_summary": bool(latest_report_summary),
        "health": bool(latest_health),
        "runtime_evidence": bool(latest_runtime_evidence),
        "finalized": finalized,
    }

    return {
        "run_root": str(run_root),
        "latest_run_result": str(latest_run_result) if latest_run_result else None,
        "latest_report_summary": str(latest_report_summary) if latest_report_summary else None,
        "latest_health": str(latest_health) if latest_health else None,
        "latest_runtime_evidence": str(latest_runtime_evidence) if latest_runtime_evidence else None,
        "run_result_status": status,
        "run_result_reason": reason,
        "run_result_top_level_keys": top_keys,
        "chain_presence": chain,
        "run_result": run_result,
        "report_summary": report_summary,
        "health": health,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize simctl run artifacts for Codex workflows.")
    parser.add_argument("--run-root", required=True, help="Run root directory to inspect")
    parser.add_argument("--output", required=False, help="Optional JSON output path")
    args = parser.parse_args()

    summary = summarize_run(Path(args.run_root))
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
