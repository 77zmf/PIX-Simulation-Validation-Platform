#!/usr/bin/env python3
"""Validate that CARLA-published robobus sensor topics have live ROS samples.

Run this on the company Ubuntu runtime host after `simctl run --execute` has
started CARLA, the CARLA bridge, and Autoware. The probe writes JSON artifacts
under `<run-dir>/runtime_verification/` so `simctl finalize` can fold the
sensor evidence into `run_result.json`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TopicSpec:
    topic: str
    group: str
    required: bool = True
    sample_required: bool = True
    sample_field: str | None = "header"


ROBOBUS117TH_TOPICS: tuple[TopicSpec, ...] = (
    TopicSpec("/sensing/camera/CAM_FRONT/image_raw", "camera"),
    TopicSpec("/sensing/camera/CAM_BACK/image_raw", "camera"),
    TopicSpec("/sensing/camera/CAM_FRONT_LEFT/image_raw", "camera"),
    TopicSpec("/sensing/camera/CAM_FRONT_RIGHT/image_raw", "camera"),
    TopicSpec("/sensing/camera/CAM_BACK_LEFT/image_raw", "camera"),
    TopicSpec("/sensing/camera/CAM_BACK_RIGHT/image_raw", "camera"),
    TopicSpec("/sensing/camera/CAM_FRONT/camera_info", "camera_info"),
    TopicSpec("/sensing/camera/CAM_BACK/camera_info", "camera_info"),
    TopicSpec("/sensing/camera/CAM_FRONT_LEFT/camera_info", "camera_info"),
    TopicSpec("/sensing/camera/CAM_FRONT_RIGHT/camera_info", "camera_info"),
    TopicSpec("/sensing/camera/CAM_BACK_LEFT/camera_info", "camera_info"),
    TopicSpec("/sensing/camera/CAM_BACK_RIGHT/camera_info", "camera_info"),
    TopicSpec("/sensing/lidar/top/pointcloud_before_sync", "lidar"),
    TopicSpec("/sensing/lidar/rear_top/pointcloud_before_sync", "lidar"),
    TopicSpec("/sensing/lidar/rear/pointcloud_before_sync", "lidar"),
    TopicSpec("/sensing/lidar/left/pointcloud_before_sync", "lidar"),
    TopicSpec("/sensing/lidar/right/pointcloud_before_sync", "lidar"),
    TopicSpec("/sensing/imu/tamagawa/imu_raw", "imu"),
    TopicSpec("/sensing/gnss/pose_with_covariance", "gnss"),
    TopicSpec("/clock", "core", sample_required=False, sample_field=None),
    TopicSpec("/tf", "core", sample_required=False, sample_field=None),
    TopicSpec("/localization/kinematic_state", "localization"),
    TopicSpec("/vehicle/status/velocity_status", "vehicle"),
    TopicSpec("/control/command/control_cmd", "control", sample_required=False, sample_field=None),
    TopicSpec("/simulation/dummy_perception_publisher/object_info", "actor_bridge", sample_required=False),
    TopicSpec("/perception/object_recognition/objects", "perception", sample_required=False),
)

ROBOBUS117TH_BRIDGE_ONLY_TOPICS: tuple[TopicSpec, ...] = tuple(
    spec
    for spec in ROBOBUS117TH_TOPICS
    if spec.group in {"camera", "camera_info", "lidar", "imu", "gnss", "core", "vehicle"}
    and spec.topic != "/tf"
)

ROBOBUS117TH_L0_CLOSED_LOOP_TOPICS: tuple[TopicSpec, ...] = tuple(
    spec
    for spec in ROBOBUS117TH_TOPICS
    if spec.group not in {"actor_bridge", "perception"}
)

PROFILES: dict[str, tuple[TopicSpec, ...]] = {
    "robobus117th": ROBOBUS117TH_TOPICS,
    "robobus117th_bridge_only": ROBOBUS117TH_BRIDGE_ONLY_TOPICS,
    "robobus117th_l0_closed_loop": ROBOBUS117TH_L0_CLOSED_LOOP_TOPICS,
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
    passed = present and (not spec.sample_required or bool(result["sample_received"]))
    result["passed"] = passed if spec.required else True
    return result


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    specs = PROFILES[args.profile]
    topic_types = _topic_types(args.discovery_timeout_sec)
    max_workers = max(1, min(args.max_workers, len(specs)))
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_check_topic, spec, topic_types, args.topic_timeout_sec): spec.topic for spec in specs
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: item["topic"])
    required = [item for item in results if item["required"]]
    sample_required = [item for item in required if item["sample_required"]]
    passed = [item for item in required if item["passed"]]
    sample_received = [item for item in sample_required if item["sample_received"]]
    missing = [item["topic"] for item in required if not item["present"]]
    sample_missing = [item["topic"] for item in sample_required if not item["sample_received"]]
    groups: dict[str, dict[str, int]] = {}
    for item in results:
        bucket = groups.setdefault(item["group"], {"required": 0, "passed": 0, "sample_required": 0, "sampled": 0})
        if item["required"]:
            bucket["required"] += 1
            bucket["passed"] += int(bool(item["passed"]))
        if item["required"] and item["sample_required"]:
            bucket["sample_required"] += 1
            bucket["sampled"] += int(bool(item["sample_received"]))

    summary = {
        "profile": args.profile,
        "required_topic_count": len(required),
        "passing_topic_count": len(passed),
        "sample_required_topic_count": len(sample_required),
        "sample_received_count": len(sample_received),
        "missing_topics": missing,
        "sample_missing_topics": sample_missing,
        "groups": groups,
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": args.profile,
        "ros_domain_id": os.environ.get("ROS_DOMAIN_ID"),
        "rmw_implementation": os.environ.get("RMW_IMPLEMENTATION"),
        "overall_passed": len(passed) == len(required),
        "summary": summary,
        "topics": results,
    }


def write_artifacts(run_dir: Path, payload: dict[str, Any]) -> dict[str, str]:
    stamp = _utc_stamp()
    output_dir = run_dir / "runtime_verification" / f"sensor_topics_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"sensor_topics_{stamp}.json"
    summary = output_dir / "sensor_topics_summary.json"
    artifact.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    summary.write_text(
        json.dumps(
            {
                "overall_passed": payload["overall_passed"],
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
    parser.add_argument("--run-dir", required=True, help="simctl run directory")
    parser.add_argument("--profile", default="robobus117th", choices=sorted(PROFILES))
    parser.add_argument("--topic-timeout-sec", type=float, default=8.0)
    parser.add_argument("--discovery-timeout-sec", type=float, default=8.0)
    parser.add_argument("--max-workers", type=int, default=6)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = run_probe(args)
    paths = write_artifacts(Path(args.run_dir).resolve(), payload)
    payload.update(paths)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
