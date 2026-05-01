#!/usr/bin/env python3
"""Probe whether the live PIX Robobus CARLA ego actor can move under direct control.

This probe is intentionally host-side and destructive: it briefly applies
``VehicleControl`` to the live ego actor after the stable stack has spawned it.
Use it before route/control tests to isolate vehicle blueprint physics from
Autoware planning and controller behavior.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _tail(value: str | bytes | None, limit: int = 2400) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value[-limit:]


def _add_carla_python_paths(carla_root: str) -> None:
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


def _round_float(value: Any, digits: int = 6) -> float:
    return round(float(value), digits)


def _bool_metric(value: bool) -> float:
    return 1.0 if value else 0.0


def _speed_mps(actor: Any) -> float:
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x * velocity.x + velocity.y * velocity.y + velocity.z * velocity.z)


def _actor_role(actor: Any) -> str:
    return str(getattr(actor, "attributes", {}).get("role_name", ""))


def _vector_payload(vec: Any) -> dict[str, float]:
    return {"x": _round_float(vec.x), "y": _round_float(vec.y), "z": _round_float(vec.z)}


def _control_payload(control: Any) -> dict[str, Any]:
    return {
        "throttle": _round_float(getattr(control, "throttle", 0.0)),
        "brake": _round_float(getattr(control, "brake", 0.0)),
        "steer": _round_float(getattr(control, "steer", 0.0)),
        "hand_brake": bool(getattr(control, "hand_brake", False)),
        "reverse": bool(getattr(control, "reverse", False)),
        "manual_gear_shift": bool(getattr(control, "manual_gear_shift", False)),
        "gear": int(getattr(control, "gear", 0)),
    }


def _actor_sample(actor: Any) -> dict[str, Any]:
    transform = actor.get_transform()
    control = actor.get_control()
    speed = _speed_mps(actor)
    return {
        "id": int(actor.id),
        "type_id": str(actor.type_id),
        "role_name": _actor_role(actor),
        "location_m": _vector_payload(transform.location),
        "yaw_deg": _round_float(transform.rotation.yaw),
        "speed_mps": _round_float(speed),
        "speed_kph": _round_float(speed * 3.6),
        "control": _control_payload(control),
    }


def _find_ego(world: Any, actor_id: str, ego_role_name: str) -> tuple[Any | None, int]:
    vehicles = list(world.get_actors().filter("vehicle.*"))
    for actor in vehicles:
        if _actor_role(actor) == ego_role_name:
            return actor, len(vehicles)
    for actor in vehicles:
        if str(actor.type_id) == actor_id:
            return actor, len(vehicles)
    return (vehicles[0] if len(vehicles) == 1 else None), len(vehicles)


def _tick_or_sleep(world: Any, seconds: float) -> None:
    settings = world.get_settings()
    if getattr(settings, "synchronous_mode", False):
        world.tick()
        return
    time.sleep(seconds)


def _wait_for_ego(world: Any, args: argparse.Namespace) -> tuple[Any | None, int, int]:
    """Wait for the ego actor to become visible, ticking synchronous CARLA worlds."""
    deadline = time.time() + max(0.0, args.actor_wait_sec)
    attempts = 0
    last_vehicle_count = 0
    while True:
        attempts += 1
        actor, last_vehicle_count = _find_ego(world, args.actor_id, args.ego_role_name)
        if actor is not None:
            return actor, last_vehicle_count, attempts
        if time.time() >= deadline:
            return None, last_vehicle_count, attempts
        _tick_or_sleep(world, args.sample_period_sec)


def _reset_actor_pose(carla: Any, world: Any, actor: Any, args: argparse.Namespace) -> None:
    if not args.reset_pose:
        return
    actor.set_transform(
        carla.Transform(
            carla.Location(x=args.reset_x, y=args.reset_y, z=args.reset_z),
            carla.Rotation(yaw=args.reset_yaw_deg),
        )
    )
    actor.set_target_velocity(carla.Vector3D(0.0, 0.0, 0.0))
    actor.set_target_angular_velocity(carla.Vector3D(0.0, 0.0, 0.0))
    actor.apply_control(
        carla.VehicleControl(
            throttle=0.0,
            brake=1.0,
            steer=0.0,
            hand_brake=False,
            reverse=False,
            manual_gear_shift=False,
        )
    )
    _tick_or_sleep(world, args.sample_period_sec)


def _apply_brake(carla: Any, world: Any, actor: Any, duration_sec: float, sample_period_sec: float) -> None:
    deadline = time.time() + max(0.0, duration_sec)
    while time.time() < deadline:
        actor.apply_control(
            carla.VehicleControl(
                throttle=0.0,
                brake=1.0,
                steer=0.0,
                hand_brake=False,
                reverse=False,
                manual_gear_shift=False,
            )
        )
        _tick_or_sleep(world, sample_period_sec)


def _direct_throttle_samples(carla: Any, world: Any, actor: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    deadline = time.time() + max(0.0, args.throttle_duration_sec)
    while time.time() < deadline:
        actor.apply_control(
            carla.VehicleControl(
                throttle=args.throttle,
                brake=0.0,
                steer=args.steer,
                hand_brake=False,
                reverse=False,
                manual_gear_shift=False,
            )
        )
        _tick_or_sleep(world, args.sample_period_sec)
        samples.append({"t": time.time(), **_actor_sample(actor)})
    return samples


def build_metrics(summary: dict[str, Any]) -> dict[str, float]:
    checks = summary.get("checks") if isinstance(summary.get("checks"), dict) else {}
    return {
        "robobus_dynamics_ego_actor_seen": _bool_metric(bool(checks.get("ego_actor_seen"))),
        "robobus_dynamics_actor_type_match": _bool_metric(bool(checks.get("actor_type_match"))),
        "robobus_dynamics_actor_persisted": _bool_metric(bool(checks.get("actor_persisted"))),
        "robobus_dynamics_moved_enough": _bool_metric(bool(checks.get("moved_enough"))),
        "robobus_dynamics_speed_enough": _bool_metric(bool(checks.get("speed_enough"))),
        "robobus_dynamics_direct_throttle_passed": _bool_metric(bool(checks.get("direct_throttle_passed"))),
        "robobus_dynamics_vehicle_count_before": float(summary.get("vehicle_count_before") or 0.0),
        "robobus_dynamics_vehicle_count_after": float(summary.get("vehicle_count_after") or 0.0),
        "robobus_dynamics_direct_throttle_delta_m": float(summary.get("direct_throttle_delta_m") or 0.0),
        "robobus_dynamics_direct_throttle_max_speed_mps": float(
            summary.get("direct_throttle_max_speed_mps") or 0.0
        ),
        "robobus_dynamics_direct_throttle_max_speed_kph": float(
            summary.get("direct_throttle_max_speed_kph") or 0.0
        ),
        "robobus_dynamics_final_speed_mps": float(summary.get("final_speed_mps") or 0.0),
    }


def _failed_checks(summary: dict[str, Any]) -> list[str]:
    checks = summary.get("checks") if isinstance(summary.get("checks"), dict) else {}
    return [name for name, passed in checks.items() if not passed]


def _payload_from_summary(args: argparse.Namespace, summary: dict[str, Any]) -> dict[str, Any]:
    metrics = build_metrics(summary)
    failed_checks = _failed_checks(summary)
    overall_passed = not failed_checks
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "robobus_vehicle_dynamics_probe",
        "profile": args.profile,
        "overall_passed": overall_passed,
        "blocked_reason": None if overall_passed else "failed_checks:" + ",".join(failed_checks),
        "missing_metrics": [],
        "missing_topics": [],
        "sample_missing_topics": [],
        "metrics": metrics,
        "summary": summary,
        "assumptions": [
            "probe applies direct CARLA VehicleControl and should run before route-control validation",
            "passing direct throttle validates blueprint physics only, not Autoware planning/control closure",
        ],
    }


def _failure_payload(args: argparse.Namespace, reason: str, details: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "ego_actor_seen": False,
        "actor_type_match": False,
        "actor_persisted": False,
        "moved_enough": False,
        "speed_enough": False,
        "direct_throttle_passed": False,
    }
    summary = {"checks": checks, "worker": details}
    payload = _payload_from_summary(args, summary)
    payload["blocked_reason"] = reason
    return payload


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    _add_carla_python_paths(args.carla_root)
    try:
        import carla  # type: ignore
    except Exception as exc:
        return _failure_payload(args, "carla_import_failed", {"error": str(exc)})

    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(args.carla_timeout_sec)
    world = client.get_world()
    actor, vehicle_count_before, actor_wait_attempts = _wait_for_ego(world, args)
    if actor is None:
        summary = {
            "map": world.get_map().name if world.get_map() else None,
            "vehicle_count_before": vehicle_count_before,
            "vehicle_count_after": vehicle_count_before,
            "actor_wait_attempts": actor_wait_attempts,
            "actor_wait_sec": args.actor_wait_sec,
            "checks": {
                "ego_actor_seen": False,
                "actor_type_match": False,
                "actor_persisted": False,
                "moved_enough": False,
                "speed_enough": False,
                "direct_throttle_passed": False,
            },
        }
        return _payload_from_summary(args, summary)

    _reset_actor_pose(carla, world, actor, args)
    before = _actor_sample(actor)
    samples = _direct_throttle_samples(carla, world, actor, args)
    after_throttle = samples[-1] if samples else _actor_sample(actor)
    if args.stop_after:
        _apply_brake(carla, world, actor, args.brake_duration_sec, args.sample_period_sec)
    after_brake = _actor_sample(actor)
    persisted_actor, vehicle_count_after = _find_ego(world, args.actor_id, args.ego_role_name)
    before_location = before.get("location_m") if isinstance(before.get("location_m"), dict) else {}
    after_location = after_throttle.get("location_m") if isinstance(after_throttle.get("location_m"), dict) else {}
    delta_m = math.hypot(
        float(after_location.get("x") or 0.0) - float(before_location.get("x") or 0.0),
        float(after_location.get("y") or 0.0) - float(before_location.get("y") or 0.0),
    )
    max_speed_mps = max([float(sample.get("speed_mps") or 0.0) for sample in samples] or [0.0])
    checks = {
        "ego_actor_seen": True,
        "actor_type_match": str(actor.type_id) == args.actor_id,
        "actor_persisted": persisted_actor is not None,
        "moved_enough": delta_m >= args.min_delta_m,
        "speed_enough": max_speed_mps >= args.min_speed_mps,
        "direct_throttle_passed": delta_m >= args.min_delta_m and max_speed_mps >= args.min_speed_mps,
    }
    summary = {
        "map": world.get_map().name if world.get_map() else None,
        "vehicle_count_before": vehicle_count_before,
        "vehicle_count_after": vehicle_count_after,
        "actor_wait_attempts": actor_wait_attempts,
        "actor_wait_sec": args.actor_wait_sec,
        "actor_before": before,
        "actor_after_throttle": after_throttle,
        "actor_after_brake": after_brake,
        "sample_count": len(samples),
        "throttle": args.throttle,
        "steer": args.steer,
        "throttle_duration_sec": args.throttle_duration_sec,
        "sample_period_sec": args.sample_period_sec,
        "min_delta_m": args.min_delta_m,
        "min_speed_mps": args.min_speed_mps,
        "direct_throttle_delta_m": _round_float(delta_m),
        "direct_throttle_max_speed_mps": _round_float(max_speed_mps),
        "direct_throttle_max_speed_kph": _round_float(max_speed_mps * 3.6),
        "final_speed_mps": float(after_brake.get("speed_mps") or 0.0),
        "checks": checks,
    }
    return _payload_from_summary(args, summary)


def write_artifacts(run_dir: Path, payload: dict[str, Any]) -> dict[str, str]:
    stamp = _utc_stamp()
    output_dir = run_dir / "runtime_verification" / f"metric_probe_robobus_vehicle_dynamics_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"metric_probe_robobus_vehicle_dynamics_{stamp}.json"
    summary = output_dir / "metric_probe_robobus_vehicle_dynamics_summary.json"
    artifact.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    summary.write_text(
        json.dumps(
            {
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
    parser.add_argument("--profile", default="robobus117th_vehicle_dynamics")
    parser.add_argument("--carla-host", default=os.environ.get("SIMCTL_CARLA_HOST", "127.0.0.1"))
    parser.add_argument("--carla-port", type=int, default=int(os.environ.get("SIMCTL_CARLA_RPC_PORT", "2000")))
    parser.add_argument(
        "--carla-root",
        default=os.environ.get("CARLA_ROOT", os.environ.get("CARLA_0915_ROOT", str(Path.home() / "CARLA_0.9.15"))),
    )
    parser.add_argument("--carla-timeout-sec", type=float, default=15.0)
    parser.add_argument("--actor-id", default="vehicle.pixmoving.robobus")
    parser.add_argument("--ego-role-name", default="ego_vehicle")
    parser.add_argument("--throttle", type=float, default=0.8)
    parser.add_argument("--steer", type=float, default=0.0)
    parser.add_argument("--throttle-duration-sec", type=float, default=4.0)
    parser.add_argument("--sample-period-sec", type=float, default=0.05)
    parser.add_argument("--actor-wait-sec", type=float, default=5.0)
    parser.add_argument("--min-delta-m", type=float, default=2.0)
    parser.add_argument("--min-speed-mps", type=float, default=1.0)
    parser.add_argument("--reset-pose", action="store_true")
    parser.add_argument("--reset-x", type=float, default=229.7817)
    parser.add_argument("--reset-y", type=float, default=2.0201)
    parser.add_argument("--reset-z", type=float, default=0.45)
    parser.add_argument("--reset-yaw-deg", type=float, default=0.0)
    parser.add_argument("--stop-after", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--brake-duration-sec", type=float, default=1.0)
    parser.add_argument("--worker-timeout-sec", type=float, default=90.0)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_args = list(argv if argv is not None else sys.argv[1:])
    args = build_parser().parse_args(raw_args)
    if not args.worker:
        command = [sys.executable, str(Path(__file__).resolve()), *raw_args, "--worker"]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONFAULTHANDLER"] = "1"
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=args.worker_timeout_sec,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            payload = _failure_payload(
                args,
                "robobus_vehicle_dynamics_worker_timeout",
                {
                    "command": command,
                    "timeout_sec": args.worker_timeout_sec,
                    "stdout_tail": _tail(exc.stdout),
                    "stderr_tail": _tail(exc.stderr),
                },
            )
            outputs = write_artifacts(Path(args.run_dir), payload)
            print(json.dumps({**payload, "artifacts": outputs}, indent=2, ensure_ascii=False))
            return 1

        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)
        if completed.returncode < 0 or completed.returncode >= 128:
            payload = _failure_payload(
                args,
                "robobus_vehicle_dynamics_worker_crashed",
                {
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout_tail": _tail(completed.stdout),
                    "stderr_tail": _tail(completed.stderr),
                },
            )
            outputs = write_artifacts(Path(args.run_dir), payload)
            print(json.dumps({**payload, "artifacts": outputs}, indent=2, ensure_ascii=False))
            return 1
        return completed.returncode

    payload = run_probe(args)
    outputs = write_artifacts(Path(args.run_dir), payload)
    print(json.dumps({**payload, "artifacts": outputs}, indent=2, ensure_ascii=False))
    return 0 if payload["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
