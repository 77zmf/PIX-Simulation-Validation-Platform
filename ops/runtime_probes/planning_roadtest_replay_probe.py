#!/usr/bin/env python3
"""Fold Mac-local planning road-test evidence into simctl KPI metrics.

This probe does not replay MCAP payloads directly. It reads the indexed
``analysis_summary*.json``, ``*diagnostics*.json``, reports, and handoff notes
from an external road-test manifest, then writes a standard ``metric_probe_*``
artifact that ``simctl finalize`` can collect. Raw MCAP/log/video assets remain
outside Git.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except Exception:  # pragma: no cover - dependency is checked by repo verification.
    yaml = None  # type: ignore[assignment]


GATE_MAX_THRESHOLDS = {
    "planning_validator_invalid_count": 0.0,
    "trajectory_jump_max_m": 1.0,
    "trajectory_silence_sec": 1.0,
    "route_empty_count": 0.0,
    "control_emergency_true_count": 0.0,
    "brake_takeover_count": 0.0,
    "lateral_shift_m": 0.5,
    "max_lateral_jerk_mps3": 3.0,
}

PROFILE_FILTERS = {
    "trajectory_jump": (
        "trajectory_jump",
        "trajectory_issue",
        "p_gear",
        "route_update",
        "static_obstacle_trajectory_jump",
        "lane_change_trajectory_jump",
    ),
    "trajectory_dropout": (
        "no_trajectory",
        "trajectory_disappeared",
        "trajectory_publication_dropout",
        "route_empty",
        "route_handler",
        "no_recovery",
    ),
    "out_of_lane_brake_takeover": (
        "out_of_lane",
        "out-of-lane",
        "lateral_shift",
        "slowdown_failure",
    ),
}

TEXT_FILE_NAMES = ("*report*.md", "rd_handoff.md", "manifest.txt")
JSON_FILE_NAMES = ("*summary*.json", "*diagnostic*.json", "*diagnostics*.json", "*stats*.json")


class CaseEvidence:
    def __init__(self, *, case_id: str, root: Path, missing: bool = False) -> None:
        self.case_id = case_id
        self.root = root
        self.json_payloads: list[tuple[Path, dict[str, Any]]] = []
        self.text_payloads: list[tuple[Path, str]] = []
        self.missing = missing

    @property
    def source_files(self) -> list[str]:
        return [str(path) for path, _ in self.json_payloads] + [str(path) for path, _ in self.text_payloads]

    @property
    def combined_text(self) -> str:
        return "\n".join(text for _, text in self.text_payloads)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _load_manifest(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to read road-test replay manifests")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"manifest is not a mapping: {path}")
    return payload


def _case_text(case: dict[str, Any]) -> str:
    values = [
        case.get("case_id"),
        case.get("symptom"),
        case.get("simulation_target"),
        case.get("candidate_scenario"),
    ]
    values.extend(case.get("key_observations") or [])
    return " ".join(str(value or "") for value in values).lower()


def _case_matches_profile(case: dict[str, Any], profile: str) -> bool:
    haystack = _case_text(case)
    return any(token in haystack for token in PROFILE_FILTERS[profile])


def _selected_cases(manifest: dict[str, Any], profile: str, case_ids: list[str]) -> list[dict[str, Any]]:
    cases = [case for case in manifest.get("cases") or [] if isinstance(case, dict)]
    if case_ids:
        wanted = set(case_ids)
        return [case for case in cases if str(case.get("case_id")) in wanted]
    return [case for case in cases if _case_matches_profile(case, profile)]


def _safe_read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _load_case_evidence(case: dict[str, Any]) -> CaseEvidence:
    case_id = str(case.get("case_id") or "unknown")
    root = Path(str(case.get("local_evidence_root") or "")).expanduser()
    evidence = CaseEvidence(case_id=case_id, root=root, missing=not root.exists())
    if evidence.missing:
        return evidence

    json_paths: set[Path] = set()
    for pattern in JSON_FILE_NAMES:
        json_paths.update(root.glob(pattern))
    for path in sorted(json_paths):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            evidence.json_payloads.append((path, payload))

    text_paths: set[Path] = set()
    for pattern in TEXT_FILE_NAMES:
        text_paths.update(root.glob(pattern))
    for path in sorted(text_paths):
        text = _safe_read_text(path)
        if text:
            evidence.text_payloads.append((path, text))
    return evidence


def _walk(payload: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = (*path, str(key))
            yield next_path, value
            yield from _walk(value, next_path)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            yield from _walk(value, (*path, str(index)))


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _numbers_for_leaf(payload: dict[str, Any], leaf_names: set[str]) -> list[float]:
    numbers: list[float] = []
    for path, value in _walk(payload):
        if not path or path[-1] not in leaf_names:
            continue
        number = _as_float(value)
        if number is not None:
            numbers.append(number)
    return numbers


def _validator_peak_values(payload: dict[str, Any], peak_names: set[str]) -> list[float]:
    validator = payload.get("validator") if isinstance(payload.get("validator"), dict) else {}
    peaks = validator.get("peaks") if isinstance(validator.get("peaks"), dict) else {}
    values: list[float] = []
    for name in peak_names:
        raw_peak = peaks.get(name)
        if isinstance(raw_peak, dict):
            value = _as_float(raw_peak.get("value"))
        else:
            value = _as_float(raw_peak)
        if value is not None:
            values.append(value)
    return values


def _max_or_zero(values: Iterable[float]) -> float:
    filtered = list(values)
    return max(filtered) if filtered else 0.0


def _sum_or_zero(values: Iterable[float]) -> float:
    return float(sum(values))


def _regex_numbers(text: str, patterns: Iterable[str]) -> list[float]:
    numbers: list[float] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            for group in match.groups():
                number = _as_float(group)
                if number is not None:
                    numbers.append(number)
                    break
    return numbers


def _contains_any(text: str, tokens: Iterable[str]) -> bool:
    lower = text.lower()
    return any(token in lower for token in tokens)


def _case_invalid_count(evidence: CaseEvidence) -> float:
    values: list[float] = []
    fallback_values: list[float] = []
    for _, payload in evidence.json_payloads:
        validator = payload.get("validator") if isinstance(payload.get("validator"), dict) else {}
        direct = _as_float(validator.get("invalid_messages")) if isinstance(validator, dict) else None
        if direct is not None:
            values.append(direct)
            continue
        fallback_values.extend(_numbers_for_leaf(payload, {"invalid_messages", "invalid_count"}))
    if values:
        return _max_or_zero(values)
    if fallback_values:
        return _max_or_zero(fallback_values)
    text = evidence.combined_text
    text_values = _regex_numbers(text, (r"\b(\d+(?:\.\d+)?)\s+invalid\s+messages?\b",))
    if text_values:
        return _sum_or_zero(text_values)
    return 1.0 if _contains_any(text, ("planning validator invalid", "invalid segment")) else 0.0


def _case_jump_max(evidence: CaseEvidence) -> float:
    values: list[float] = []
    for _, payload in evidence.json_payloads:
        values.extend(_numbers_for_leaf(payload, {"jump_m", "trajectory_jump_max_m"}))
    text = evidence.combined_text
    values.extend(
        _regex_numbers(
            text,
            (
                r"\bjump\w*[^.\n]{0,100}?\b(\d+(?:\.\d+)?)\s*m\b",
                r"\b(\d+(?:\.\d+)?)\s*m\b[^.\n]{0,100}?\bjump\w*",
            ),
        )
    )
    return _max_or_zero(values)


def _case_trajectory_silence(evidence: CaseEvidence) -> float:
    values: list[float] = []
    for _, payload in evidence.json_payloads:
        values.extend(
            _numbers_for_leaf(
                payload,
                {
                    "trajectory_silence_sec",
                    "silence_after_last_to_event_end_s",
                    "silence_to_end_s",
                },
            )
        )
    text = evidence.combined_text
    values.extend(
        _regex_numbers(
            text,
            (
                r"\b(?:silence|stops?|stop|no main planning|after last main planning publication)[^.\n]{0,120}?\b(\d+(?:\.\d+)?)\s*s\b",
                r"\b(\d+(?:\.\d+)?)\s*s\b[^.\n]{0,120}?\b(?:silence|stops?|stop|after last main planning publication)\b",
            ),
        )
    )
    return _max_or_zero(values)


def _case_route_empty_count(case: dict[str, Any], evidence: CaseEvidence) -> float:
    text = f"{_case_text(case)}\n{evidence.combined_text}"
    return 1.0 if _contains_any(text, ("route_empty", "route is empty", "planned route is empty", "empty route")) else 0.0


def _case_planner_crash_count(evidence: CaseEvidence) -> float:
    text = evidence.combined_text
    return 1.0 if _contains_any(text, ("crashed", "exit code -11", "segmentation fault", "sigsegv")) else 0.0


def _case_emergency_count(evidence: CaseEvidence) -> float:
    values: list[float] = []
    for _, payload in evidence.json_payloads:
        values.extend(_numbers_for_leaf(payload, {"emergency_true_count", "control_emergency_true_count"}))
    if values:
        return _sum_or_zero(values)
    text = evidence.combined_text
    return 1.0 if _contains_any(text, ("mrm emergency", "emergency stop", "vehicle_cmd_gate emergency")) else 0.0


def _case_brake_takeover_count(evidence: CaseEvidence) -> float:
    return 1.0 if _contains_any(evidence.combined_text, ("brake takeover", "brake plus teleop takeover")) else 0.0


def _case_lateral_shift(evidence: CaseEvidence) -> float:
    values: list[float] = []
    for _, payload in evidence.json_payloads:
        values.extend(_validator_peak_values(payload, {"lateral_shift_m", "lateral_shift"}))
    text = evidence.combined_text
    values.extend(
        _regex_numbers(
            text,
            (
                r"\blateral_shift\s*[:=]\s*`?(\d+(?:\.\d+)?)\s*m?\b",
                r"\blateral\s+shift[^.\n]{0,80}?\b(\d+(?:\.\d+)?)\s*m\b",
                r"\btrajectory\s+shift[^.\n]{0,80}?\b(\d+(?:\.\d+)?)\s*m\b",
                r"\b(\d+(?:\.\d+)?)\s*m\b[^.\n]{0,80}?\b(?:lateral\s+shift|trajectory\s+shift)\b",
            ),
        )
    )
    return _max_or_zero(values)


def _case_lateral_jerk(evidence: CaseEvidence) -> float:
    values: list[float] = []
    for _, payload in evidence.json_payloads:
        values.extend(_numbers_for_leaf(payload, {"max_lateral_jerk_mps3", "lateral_jerk_mps3", "lateral_jerk"}))
    text = evidence.combined_text
    values.extend(
        _regex_numbers(
            text,
            (
                r"\b(?:max_)?lateral[_\s]+jerk[^.\n]{0,80}?\b(\d+(?:\.\d+)?)\s*(?:m/s\^3|mps3)?\b",
                r"\b(\d+(?:\.\d+)?)\s*(?:m/s\^3|mps3)\b[^.\n]{0,80}?\b(?:max_)?lateral[_\s]+jerk\b",
            ),
        )
    )
    return _max_or_zero(values)


def _case_metrics(case: dict[str, Any], evidence: CaseEvidence) -> dict[str, float]:
    return {
        "planning_validator_invalid_count": _case_invalid_count(evidence),
        "trajectory_jump_max_m": _case_jump_max(evidence),
        "trajectory_silence_sec": _case_trajectory_silence(evidence),
        "route_empty_count": _case_route_empty_count(case, evidence),
        "control_emergency_true_count": _case_emergency_count(evidence),
        "brake_takeover_count": _case_brake_takeover_count(evidence),
        "lateral_shift_m": _case_lateral_shift(evidence),
        "max_lateral_jerk_mps3": _case_lateral_jerk(evidence),
        "planner_container_crash_count": _case_planner_crash_count(evidence),
    }


def _aggregate_metrics(per_case: list[dict[str, Any]]) -> dict[str, float]:
    case_metrics = [item["metrics"] for item in per_case]
    return {
        "planning_validator_invalid_count": _sum_or_zero(
            metrics["planning_validator_invalid_count"] for metrics in case_metrics
        ),
        "trajectory_jump_max_m": _max_or_zero(metrics["trajectory_jump_max_m"] for metrics in case_metrics),
        "trajectory_silence_sec": _max_or_zero(metrics["trajectory_silence_sec"] for metrics in case_metrics),
        "route_empty_count": _sum_or_zero(metrics["route_empty_count"] for metrics in case_metrics),
        "control_emergency_true_count": _sum_or_zero(metrics["control_emergency_true_count"] for metrics in case_metrics),
        "brake_takeover_count": _sum_or_zero(metrics["brake_takeover_count"] for metrics in case_metrics),
        "lateral_shift_m": _max_or_zero(metrics["lateral_shift_m"] for metrics in case_metrics),
        "max_lateral_jerk_mps3": _max_or_zero(metrics["max_lateral_jerk_mps3"] for metrics in case_metrics),
        "planner_container_crash_count": _sum_or_zero(metrics["planner_container_crash_count"] for metrics in case_metrics),
        "roadtest_replay_case_count": float(len(case_metrics)),
    }


def _failed_thresholds(metrics: dict[str, float]) -> list[str]:
    return [
        metric
        for metric, max_value in GATE_MAX_THRESHOLDS.items()
        if float(metrics.get(metric, 0.0)) > max_value
    ]


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = _load_manifest(manifest_path)
    cases = _selected_cases(manifest, args.profile, list(args.case_id or []))
    per_case: list[dict[str, Any]] = []
    missing_roots: list[str] = []
    for case in cases:
        evidence = _load_case_evidence(case)
        metrics = _case_metrics(case, evidence)
        if evidence.missing:
            missing_roots.append(str(evidence.root))
        per_case.append(
            {
                "case_id": evidence.case_id,
                "root": str(evidence.root),
                "missing": evidence.missing,
                "source_files": evidence.source_files,
                "metrics": metrics,
            }
        )

    metrics = _aggregate_metrics(per_case) if per_case else {
        **{name: 0.0 for name in GATE_MAX_THRESHOLDS},
        "planner_container_crash_count": 0.0,
        "roadtest_replay_case_count": 0.0,
    }
    failed = _failed_thresholds(metrics)
    blockers: list[str] = []
    if not per_case:
        blockers.append("no_matching_cases")
    if missing_roots:
        blockers.append("missing_evidence_roots")
    if failed:
        blockers.append("thresholds_failed:" + ",".join(failed))
    overall_passed = not blockers
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "planning_roadtest_replay_probe",
        "profile": args.profile,
        "manifest": str(manifest_path),
        "overall_passed": overall_passed,
        "blocked_reason": ";".join(blockers) if blockers else None,
        "missing_metrics": [],
        "missing_topics": [],
        "sample_missing_topics": [],
        "metrics": metrics,
        "summary": {
            "case_count": len(per_case),
            "case_ids": [item["case_id"] for item in per_case],
            "missing_roots": missing_roots,
            "failed_thresholds": failed,
            "cases": per_case,
        },
        "scope": "external_road_test_summary_replay_evidence",
        "assumptions": [
            "raw MCAP replay is not executed by this probe",
            "metrics are extracted from indexed road-test analysis summaries, diagnostics, reports, and handoff notes",
            "promotion to formal CARLA regression still requires a deterministic route fixture or MCAP replay harness",
        ],
    }


def write_artifacts(run_dir: Path, payload: dict[str, Any]) -> dict[str, str]:
    stamp = _utc_stamp()
    output_dir = run_dir / "runtime_verification" / f"metric_probe_planning_roadtest_replay_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"metric_probe_planning_roadtest_replay_{stamp}.json"
    summary = output_dir / "metric_probe_planning_roadtest_replay_summary.json"
    artifact.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    summary.write_text(
        json.dumps(
            {
                "profile": payload["profile"],
                "overall_passed": payload["overall_passed"],
                "blocked_reason": payload["blocked_reason"],
                "metrics": payload["metrics"],
                "summary": payload["summary"],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"artifact": str(artifact), "summary_path": str(summary)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--profile", choices=sorted(PROFILE_FILTERS), required=True)
    parser.add_argument("--case-id", action="append", default=[], help="Limit probe to an explicit manifest case id")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = run_probe(args)
    outputs = write_artifacts(Path(args.run_dir), payload)
    print(json.dumps({"payload": payload, "artifacts": outputs}, indent=2, ensure_ascii=False))
    return 0 if payload["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
