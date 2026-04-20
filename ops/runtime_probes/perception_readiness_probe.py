#!/usr/bin/env python3
"""Validate perception interface readiness and fold real metric artifacts.

Run this on the Ubuntu runtime host after `simctl run --execute` has launched
CARLA and Autoware. The probe checks that key ROS interfaces are alive, then
loads a metrics JSON artifact produced by the perception evaluation pipeline.
It never fabricates BEVFusion quality metrics; missing metrics are reported as
blockers so `simctl finalize` keeps the KPI gate red.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_BEVFUSION_METRICS = (
    "detection_recall",
    "false_positive_per_frame",
    "tracking_id_switches",
    "occupancy_iou",
    "lane_topology_recall",
    "latency_ms",
    "planner_interface_disagreement_rate",
)
DEFAULT_METRICS_FILE = "runtime_verification/perception_metrics/bevfusion_public_road_metrics.json"


@dataclass(frozen=True)
class TopicSpec:
    topic: str
    group: str
    required: bool = True
    sample_required: bool = True
    sample_field: str | None = "header"


PROFILES: dict[str, tuple[TopicSpec, ...]] = {
    "bevfusion_public_road": (
        TopicSpec("/clock", "core", sample_required=False, sample_field=None),
        TopicSpec("/tf", "core", sample_required=False, sample_field=None),
        TopicSpec("/localization/kinematic_state", "localization"),
        TopicSpec("/sensing/lidar/top/pointcloud_before_sync", "sensor"),
        TopicSpec("/sensing/lidar/left/pointcloud_before_sync", "sensor"),
        TopicSpec("/sensing/lidar/right/pointcloud_before_sync", "sensor"),
        TopicSpec("/sensing/camera/CAM_FRONT/image_raw", "sensor"),
        TopicSpec("/perception/object_recognition/objects", "perception"),
        TopicSpec("/perception/object_recognition/detection/objects", "perception", required=False),
        TopicSpec("/perception/object_recognition/tracking/objects", "perception", required=False),
        TopicSpec("/planning/scenario_planning/trajectory", "planning", required=False, sample_required=False),
    ),
}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _tail(text: str | bytes | None, limit: int = 1200) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return text[-limit:]


def _run(cmd: list[str], timeout_sec: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
    )


def _topic_types(timeout_sec: float) -> dict[str, str]:
    try:
        proc = _run(["ros2", "topic", "list", "-t"], timeout_sec)
    except subprocess.TimeoutExpired:
        return {}
    if proc.returncode != 0:
        return {}
    topic_types: dict[str, str] = {}
    pattern = re.compile(r"^(?P<topic>/\S+)\s+\[(?P<type>[^\]]+)\]\s*$")
    for line in proc.stdout.splitlines():
        match = pattern.match(line.strip())
        if match:
            topic_types[match.group("topic")] = match.group("type")
    return topic_types


def _sample_topic(spec: TopicSpec, timeout_sec: float) -> dict[str, Any]:
    cmd = [
        "ros2",
        "topic",
        "echo",
        "--once",
        "--spin-time",
        "1",
        "--truncate-length",
        "96",
        "--flow-style",
    ]
    if spec.sample_field:
        cmd.extend(["--field", spec.sample_field])
    cmd.append(spec.topic)
    try:
        proc = _run(cmd, timeout_sec)
        return {
            "sample_received": proc.returncode == 0 and bool(proc.stdout.strip()),
            "sample_command": " ".join(cmd),
            "sample_returncode": proc.returncode,
            "sample_stdout_tail": _tail(proc.stdout),
            "sample_stderr_tail": _tail(proc.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "sample_received": False,
            "sample_command": " ".join(cmd),
            "sample_returncode": "timeout",
            "sample_stdout_tail": _tail(exc.stdout or ""),
            "sample_stderr_tail": _tail(exc.stderr or ""),
        }


def _check_topic(spec: TopicSpec, topic_types: dict[str, str], timeout_sec: float) -> dict[str, Any]:
    present = spec.topic in topic_types
    result: dict[str, Any] = {
        "topic": spec.topic,
        "group": spec.group,
        "required": spec.required,
        "sample_required": spec.sample_required,
        "sample_field": spec.sample_field,
        "present": present,
        "type": topic_types.get(spec.topic),
    }
    if present and spec.sample_required:
        result.update(_sample_topic(spec, timeout_sec))
    else:
        result.update(
            {
                "sample_received": None if not spec.sample_required else False,
                "sample_command": None,
                "sample_returncode": None,
                "sample_stdout_tail": "",
                "sample_stderr_tail": "",
            }
        )
    result["passed"] = present and (not spec.sample_required or bool(result["sample_received"]))
    if not spec.required:
        result["passed"] = True
    return result


def _resolve_metrics_file(run_dir: Path, metrics_file: str | None) -> Path:
    candidate = Path(metrics_file or DEFAULT_METRICS_FILE)
    return candidate if candidate.is_absolute() else run_dir / candidate


def _read_metrics(path: Path) -> tuple[dict[str, float], list[str], str | None]:
    if not path.exists():
        return {}, list(REQUIRED_BEVFUSION_METRICS), "missing_metrics_file"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, list(REQUIRED_BEVFUSION_METRICS), f"unreadable_metrics_file:{exc}"
    if not isinstance(payload, dict):
        return {}, list(REQUIRED_BEVFUSION_METRICS), "metrics_file_not_object"
    raw_metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else payload
    metrics: dict[str, float] = {}
    missing: list[str] = []
    for name in REQUIRED_BEVFUSION_METRICS:
        value = raw_metrics.get(name) if isinstance(raw_metrics, dict) else None
        if isinstance(value, bool) or value is None:
            missing.append(name)
            continue
        try:
            metrics[name] = float(value)
        except (TypeError, ValueError):
            missing.append(name)
    blocked = "missing_required_metrics" if missing else None
    return metrics, missing, blocked


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = Path(args.run_dir).resolve()
    topic_types = _topic_types(args.discovery_timeout_sec)
    topic_results = [
        _check_topic(spec, topic_types, args.topic_timeout_sec)
        for spec in PROFILES[args.profile]
    ]
    required = [item for item in topic_results if item["required"]]
    sample_required = [item for item in required if item["sample_required"]]
    missing_topics = [item["topic"] for item in required if not item["present"]]
    sample_missing_topics = [item["topic"] for item in sample_required if not item["sample_received"]]
    topic_ready = not missing_topics and not sample_missing_topics

    metrics_path = _resolve_metrics_file(run_dir, args.metrics_file)
    metrics, missing_metrics, metrics_blocker = _read_metrics(metrics_path)
    metrics_required_ok = not args.require_metrics or (not missing_metrics and metrics_blocker is None)
    overall_passed = topic_ready and metrics_required_ok
    blockers: list[str] = []
    if missing_topics:
        blockers.append("missing_required_topics")
    if sample_missing_topics:
        blockers.append("missing_required_topic_samples")
    if args.require_metrics and metrics_blocker:
        blockers.append(metrics_blocker)

    payload_metrics = {"perception_readiness": 1.0 if overall_passed else 0.0}
    payload_metrics.update(metrics)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": args.profile,
        "ros_domain_id": os.environ.get("ROS_DOMAIN_ID"),
        "rmw_implementation": os.environ.get("RMW_IMPLEMENTATION"),
        "overall_passed": overall_passed,
        "blocked_reason": ",".join(blockers) if blockers else None,
        "metrics_file": str(metrics_path),
        "require_metrics": args.require_metrics,
        "missing_metrics": missing_metrics,
        "missing_topics": missing_topics,
        "sample_missing_topics": sample_missing_topics,
        "metrics": payload_metrics,
        "summary": {
            "required_topic_count": len(required),
            "passing_topic_count": sum(1 for item in required if item["passed"]),
            "sample_required_topic_count": len(sample_required),
            "sample_received_count": sum(1 for item in sample_required if item["sample_received"]),
        },
        "topics": topic_results,
    }


def write_artifacts(run_dir: Path, payload: dict[str, Any]) -> dict[str, str]:
    stamp = _utc_stamp()
    output_dir = run_dir / "runtime_verification" / f"perception_readiness_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"perception_readiness_{stamp}.json"
    summary = output_dir / "perception_readiness_summary.json"
    artifact.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    summary.write_text(
        json.dumps(
            {
                "overall_passed": payload["overall_passed"],
                "blocked_reason": payload["blocked_reason"],
                "missing_metrics": payload["missing_metrics"],
                "missing_topics": payload["missing_topics"],
                "sample_missing_topics": payload["sample_missing_topics"],
                "metrics": payload["metrics"],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"artifact": str(artifact), "summary_path": str(summary)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="simctl run directory")
    parser.add_argument("--profile", default="bevfusion_public_road", choices=sorted(PROFILES))
    parser.add_argument("--metrics-file", help=f"Metrics JSON path, default: <run-dir>/{DEFAULT_METRICS_FILE}")
    parser.add_argument("--require-metrics", action="store_true", help="Fail if the metrics artifact is missing or incomplete")
    parser.add_argument("--topic-timeout-sec", type=float, default=8.0)
    parser.add_argument("--discovery-timeout-sec", type=float, default=8.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_dir = Path(args.run_dir).resolve()
    payload = run_probe(args)
    paths = write_artifacts(run_dir, payload)
    payload.update(paths)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
