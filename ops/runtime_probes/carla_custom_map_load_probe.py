#!/usr/bin/env python3
"""Validate that a CARLA custom map package is visible and loadable.

Run this on the Ubuntu runtime host after a CARLA server is listening. The
probe writes a generic metric-probe artifact under
`<run-dir>/runtime_verification/metric_probe_carla_custom_map_load/` so
`simctl validate --finalize` can fold the import smoke into `run_result.json`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROBE_ID = "metric_probe_carla_custom_map_load"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def add_carla_python_paths(carla_root: str) -> None:
    if importlib.util.find_spec("carla") is not None:
        return
    root = Path(carla_root).expanduser()
    candidates = [
        root / "PythonAPI" / "carla" / "dist" / "carla-0.9.15-py3.10-linux-x86_64.egg",
        root / "PythonAPI" / "carla" / "dist" / "carla-0.9.15-py3.7-linux-x86_64.egg",
        root / "PythonAPI" / "carla",
    ]
    for candidate in candidates:
        if candidate.exists():
            sys.path.insert(0, str(candidate))


def normalize_map_ref(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"/+", "/", text)
    if text.startswith("/Game/"):
        return text
    if text.startswith("Game/"):
        return "/" + text
    if text.startswith("Carla/Maps/"):
        return "/Game/" + text
    if text.startswith("Town"):
        return f"/Game/Carla/Maps/{text}"
    return text


def map_matches(available_map: str, requested_map: str) -> bool:
    available = normalize_map_ref(available_map)
    requested = normalize_map_ref(requested_map)
    if not requested:
        return False
    if available == requested:
        return True
    requested_tail = requested.rsplit("/", 1)[-1]
    available_tail = available.rsplit("/", 1)[-1]
    return bool(requested_tail and available_tail == requested_tail)


def build_metrics(
    *,
    available: bool,
    load_passed: bool,
    current_match: bool,
    actor_count: int,
    expected_alignment_iou: float | None,
) -> dict[str, float]:
    metrics = {
        "carla_custom_map_available": 1.0 if available else 0.0,
        "carla_custom_map_load_passed": 1.0 if load_passed else 0.0,
        "carla_custom_map_current_match": 1.0 if current_match else 0.0,
        "carla_custom_map_actor_count": float(actor_count),
    }
    if expected_alignment_iou is not None:
        metrics["carla_custom_map_alignment_iou"] = float(expected_alignment_iou)
    return metrics


def overall_passed(metrics: dict[str, float], *, min_actors: int, min_alignment_iou: float | None) -> bool:
    if metrics["carla_custom_map_available"] < 1.0:
        return False
    if metrics["carla_custom_map_load_passed"] < 1.0:
        return False
    if metrics["carla_custom_map_current_match"] < 1.0:
        return False
    if metrics["carla_custom_map_actor_count"] < float(min_actors):
        return False
    if min_alignment_iou is not None:
        return metrics.get("carla_custom_map_alignment_iou", 0.0) >= float(min_alignment_iou)
    return True


def write_payload(run_dir: Path, payload: dict[str, Any]) -> Path:
    output_dir = run_dir / "runtime_verification" / PROBE_ID
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{PROBE_ID}_{utc_stamp()}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def get_available_maps_with_retries(
    client_factory: Any,
    attempts: int,
    retry_sleep_sec: float,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    for _ in range(max(1, attempts)):
        try:
            client = client_factory()
            return [str(item) for item in client.get_available_maps()], errors
        except Exception as exc:
            errors.append(repr(exc))
            time.sleep(max(0.0, retry_sleep_sec))
    return [], errors


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    add_carla_python_paths(args.carla_root)
    try:
        import carla  # type: ignore
    except Exception as exc:
        metrics = build_metrics(
            available=False,
            load_passed=False,
            current_match=False,
            actor_count=0,
            expected_alignment_iou=args.expected_alignment_iou,
        )
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "kind": PROBE_ID,
            "profile": args.profile,
            "overall_passed": False,
            "blocked_reason": f"carla_import_failed:{exc}",
            "metrics": metrics,
        }

    requested_map = normalize_map_ref(args.map_name)

    def connect_client(timeout_sec: float = args.connect_timeout_sec) -> Any:
        client = carla.Client(args.host, args.port)
        client.set_timeout(timeout_sec)
        return client

    available_maps, connect_errors = get_available_maps_with_retries(
        connect_client,
        args.connect_attempts,
        args.retry_sleep_sec,
    )
    if not available_maps:
        metrics = build_metrics(
            available=False,
            load_passed=False,
            current_match=False,
            actor_count=0,
            expected_alignment_iou=args.expected_alignment_iou,
        )
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "kind": PROBE_ID,
            "profile": args.profile,
            "overall_passed": False,
            "host": args.host,
            "port": args.port,
            "carla_root": args.carla_root,
            "requested_map": requested_map,
            "blocked_reason": "carla_available_maps_timeout",
            "connect_errors": connect_errors,
            "metrics": metrics,
        }
    matching_maps = [item for item in available_maps if map_matches(str(item), requested_map)]
    load_target = matching_maps[0] if matching_maps else requested_map
    client = connect_client(args.timeout_sec)
    load_passed = False
    current_map = ""
    actor_count = 0
    error = ""
    try:
        world = client.load_world(load_target) if not args.skip_load_world else client.get_world()
        current_map = str(world.get_map().name)
        actor_count = len(list(world.get_actors()))
        load_passed = True
    except Exception as exc:
        error = repr(exc)
        try:
            world = client.get_world()
            current_map = str(world.get_map().name)
            actor_count = len(list(world.get_actors()))
        except Exception:
            pass

    current_match = map_matches(current_map, requested_map)
    metrics = build_metrics(
        available=bool(matching_maps),
        load_passed=load_passed,
        current_match=current_match,
        actor_count=actor_count,
        expected_alignment_iou=args.expected_alignment_iou,
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": PROBE_ID,
        "profile": args.profile,
        "overall_passed": overall_passed(
            metrics,
            min_actors=args.min_actors,
            min_alignment_iou=args.min_alignment_iou,
        ),
        "host": args.host,
        "port": args.port,
        "carla_root": args.carla_root,
        "requested_map": requested_map,
        "load_target": str(load_target),
        "current_map": current_map,
        "available_match_count": len(matching_maps),
        "available_matches": [str(item) for item in matching_maps],
        "available_map_count": len(available_maps),
        "connect_errors": connect_errors,
        "actor_count": actor_count,
        "load_error": error,
        "metrics": metrics,
        "thresholds": {
            "min_actors": args.min_actors,
            "min_alignment_iou": args.min_alignment_iou,
        },
    }
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--carla-root", default=os.environ.get("CARLA_0915_ROOT", os.path.expanduser("~/CARLA_0.9.15")))
    parser.add_argument("--host", default=os.environ.get("SIMCTL_CARLA_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SIMCTL_CARLA_RPC_PORT", "2000")))
    parser.add_argument("--map-name", required=True)
    parser.add_argument("--profile", default="qiyu_loop_carla_import_smoke")
    parser.add_argument("--timeout-sec", type=float, default=60.0)
    parser.add_argument("--connect-timeout-sec", type=float, default=5.0)
    parser.add_argument("--connect-attempts", type=int, default=3)
    parser.add_argument("--retry-sleep-sec", type=float, default=5.0)
    parser.add_argument("--min-actors", type=int, default=1)
    parser.add_argument("--expected-alignment-iou", type=float)
    parser.add_argument("--min-alignment-iou", type=float)
    parser.add_argument("--skip-load-world", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = run_probe(args)
    output_path = write_payload(Path(args.run_dir), payload)
    payload["output_path"] = str(output_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
