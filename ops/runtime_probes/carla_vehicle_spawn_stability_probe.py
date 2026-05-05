#!/usr/bin/env python3
"""Probe CARLA vehicle spawn stability on a target map.

This probe is CARLA-only by design. It starts from an already running CARLA
server, optionally loads a custom map, spawns one vehicle blueprint at a fixed
pose, tries a small set of runtime physics variants, and writes a standard
``metric_probe_*`` artifact for ``simctl finalize``.
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


def _vector_payload(vec: Any) -> dict[str, float]:
    return {"x": _round_float(vec.x), "y": _round_float(vec.y), "z": _round_float(vec.z)}


def _rotation_payload(rot: Any) -> dict[str, float]:
    return {
        "pitch": _round_float(rot.pitch),
        "yaw": _round_float(rot.yaw),
        "roll": _round_float(rot.roll),
    }


def _parse_float_list(raw: str) -> list[float]:
    return [float(item.strip()) for item in raw.split(",") if item.strip()]


def _physics_variant_specs(args: argparse.Namespace) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = [{"name": "baseline"}]
    for com_z in _parse_float_list(args.com_z_cm_values):
        variants.append({"name": f"com_z_{int(com_z)}cm", "com_z_cm": com_z})
    for com_z in _parse_float_list(args.com_z_cm_values):
        variants.append({"name": f"com_x0_z_{int(com_z)}cm", "com_x_cm": 0.0, "com_z_cm": com_z})
    if args.mass_kg:
        for com_z in _parse_float_list(args.com_z_cm_values):
            variants.append(
                {
                    "name": f"mass{int(args.mass_kg)}_com_x0_z_{int(com_z)}cm",
                    "com_x_cm": 0.0,
                    "com_z_cm": com_z,
                    "mass_kg": args.mass_kg,
                }
            )
    return variants


def _sample_actor(actor: Any) -> dict[str, Any]:
    transform = actor.get_transform()
    return {
        "location_m": _vector_payload(transform.location),
        "rotation_deg": _rotation_payload(transform.rotation),
        "speed_mps": _round_float(_speed_mps(actor)),
    }


def _variant_score(variant: dict[str, Any]) -> tuple[float, float, float]:
    return (
        float(variant.get("max_abs_pitch_deg") or 999.0) + float(variant.get("max_abs_roll_deg") or 999.0),
        -float(variant.get("delta_xy_m") or 0.0),
        -float(variant.get("max_speed_mps") or 0.0),
    )


def build_metrics(summary: dict[str, Any]) -> dict[str, float]:
    variants = [item for item in summary.get("variants") or [] if isinstance(item, dict)]
    spawned = [item for item in variants if item.get("spawned")]
    stable = [item for item in spawned if item.get("stable")]
    driveable = [item for item in spawned if item.get("driveable")]
    best = min(spawned, key=_variant_score) if spawned else {}
    return {
        "robobus_qiyu_spawn_blueprint_found": _bool_metric(bool(summary.get("blueprint_found"))),
        "robobus_qiyu_spawn_variant_count": float(len(variants)),
        "robobus_qiyu_spawn_spawned_count": float(len(spawned)),
        "robobus_qiyu_spawn_stable_count": float(len(stable)),
        "robobus_qiyu_spawn_driveable_count": float(len(driveable)),
        "robobus_qiyu_spawn_stability_passed": _bool_metric(bool(summary.get("passed"))),
        "robobus_qiyu_spawn_best_max_abs_pitch_deg": float(best.get("max_abs_pitch_deg") or 999.0),
        "robobus_qiyu_spawn_best_max_abs_roll_deg": float(best.get("max_abs_roll_deg") or 999.0),
        "robobus_qiyu_spawn_best_min_z_m": float(best.get("min_z_m") or 0.0),
        "robobus_qiyu_spawn_best_max_speed_mps": float(best.get("max_speed_mps") or 0.0),
        "robobus_qiyu_spawn_best_delta_xy_m": float(best.get("delta_xy_m") or 0.0),
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
        "kind": "carla_vehicle_spawn_stability_probe",
        "profile": args.profile,
        "overall_passed": overall_passed,
        "blocked_reason": None if overall_passed else "failed_checks:" + ",".join(failed_checks),
        "missing_metrics": [],
        "missing_topics": [],
        "sample_missing_topics": [],
        "metrics": metrics,
        "summary": summary,
        "assumptions": [
            "probe validates CARLA actor spawn/settle/drivability only, not Autoware route closure",
            "runtime physics overrides are diagnostic; a pass should still be converted into asset authoring defaults",
        ],
    }


def _failure_payload(args: argparse.Namespace, reason: str, details: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "blueprint_found": False,
        "passed": False,
        "checks": {
            "blueprint_found": False,
            "spawned": False,
            "stable_variant_available": False,
            "driveable_variant_available": False,
        },
        "variants": [],
        "worker": details,
    }
    payload = _payload_from_summary(args, summary)
    payload["blocked_reason"] = reason
    return payload


def _destroy_matching_vehicles(world: Any, actor_id: str, ego_role_name: str) -> None:
    for actor in list(world.get_actors().filter("vehicle.*")):
        role_name = str(getattr(actor, "attributes", {}).get("role_name", ""))
        if str(actor.type_id) == actor_id or role_name == ego_role_name:
            try:
                actor.destroy()
            except Exception:
                pass


def _tick(world: Any, count: int = 1) -> None:
    for _ in range(count):
        try:
            world.tick()
        except RuntimeError:
            time.sleep(0.05)


def _apply_variant_physics(carla: Any, actor: Any, spec: dict[str, Any]) -> str | None:
    physics = actor.get_physics_control()
    if "com_z_cm" in spec or "com_x_cm" in spec:
        current = physics.center_of_mass
        physics.center_of_mass = carla.Vector3D(
            x=float(spec.get("com_x_cm", current.x)),
            y=float(spec.get("com_y_cm", current.y)),
            z=float(spec.get("com_z_cm", current.z)),
        )
    if "mass_kg" in spec:
        physics.mass = float(spec["mass_kg"])
    try:
        actor.apply_physics_control(physics)
    except Exception as exc:
        return str(exc)
    return None


def _run_variant(carla: Any, world: Any, blueprint: Any, args: argparse.Namespace, spec: dict[str, Any], z_offset: float) -> dict[str, Any]:
    _destroy_matching_vehicles(world, args.actor_id, args.ego_role_name)
    _tick(world, 5)
    transform = carla.Transform(
        carla.Location(x=args.spawn_x, y=args.spawn_y, z=args.spawn_z + z_offset),
        carla.Rotation(pitch=args.spawn_pitch_deg, yaw=args.spawn_yaw_deg, roll=args.spawn_roll_deg),
    )
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        return {"name": spec["name"], "spawned": False, "spawn_z_offset_m": z_offset}

    physics_error = _apply_variant_physics(carla, actor, spec)
    actor.set_target_velocity(carla.Vector3D(0.0, 0.0, 0.0))
    actor.set_target_angular_velocity(carla.Vector3D(0.0, 0.0, 0.0))
    actor.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0))

    samples: list[dict[str, Any]] = []
    for index in range(args.settle_ticks):
        _tick(world)
        if index in {0, 1, 2, 5, 10, 20, 40, 60, 80, args.settle_ticks - 1}:
            samples.append({"tick": index, **_sample_actor(actor)})

    drive_samples: list[dict[str, Any]] = []
    for index in range(args.drive_ticks):
        actor.apply_control(carla.VehicleControl(throttle=args.throttle, brake=0.0, steer=args.steer))
        _tick(world)
        if index in {0, 10, 20, 40, args.drive_ticks - 1}:
            drive_samples.append({"tick": index, **_sample_actor(actor)})

    final = _sample_actor(actor)
    all_samples = samples + drive_samples + [final]
    rotations = [item["rotation_deg"] for item in all_samples]
    locations = [item["location_m"] for item in all_samples]
    max_abs_pitch = max(abs(float(item["pitch"])) for item in rotations)
    max_abs_roll = max(abs(float(item["roll"])) for item in rotations)
    min_z = min(float(item["z"]) for item in locations)
    max_speed = max(float(item["speed_mps"]) for item in all_samples)
    first_location = samples[0]["location_m"] if samples else final["location_m"]
    final_location = final["location_m"]
    delta_xy = math.hypot(
        float(final_location["x"]) - float(first_location["x"]),
        float(final_location["y"]) - float(first_location["y"]),
    )
    stable = max_abs_pitch <= args.max_abs_pitch_deg and max_abs_roll <= args.max_abs_roll_deg and min_z >= args.min_z_m
    driveable = stable and delta_xy >= args.min_delta_m and max_speed >= args.min_speed_mps
    try:
        actor.destroy()
    except Exception:
        pass
    _tick(world, 5)
    return {
        "name": spec["name"],
        "spawned": True,
        "spawn_z_offset_m": z_offset,
        "requested_physics": {key: value for key, value in spec.items() if key != "name"},
        "physics_error": physics_error,
        "settle_samples": samples,
        "drive_samples": drive_samples,
        "final": final,
        "max_abs_pitch_deg": _round_float(max_abs_pitch),
        "max_abs_roll_deg": _round_float(max_abs_roll),
        "min_z_m": _round_float(min_z),
        "max_speed_mps": _round_float(max_speed),
        "delta_xy_m": _round_float(delta_xy),
        "stable": stable,
        "driveable": driveable,
    }


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    _add_carla_python_paths(args.carla_root)
    try:
        import carla  # type: ignore
    except Exception as exc:
        return _failure_payload(args, "carla_import_failed", {"error": str(exc)})

    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(args.carla_timeout_sec)
    world = client.get_world()
    if args.carla_map:
        world = client.load_world(args.carla_map)
        time.sleep(args.map_load_wait_sec)

    original_settings = world.get_settings()
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = args.fixed_delta_sec
    settings.no_rendering_mode = True
    world.apply_settings(settings)
    _tick(world, 20)

    try:
        blueprint = world.get_blueprint_library().find(args.actor_id)
    except Exception as exc:
        return _failure_payload(args, "blueprint_not_found", {"actor_id": args.actor_id, "error": str(exc)})
    if blueprint.has_attribute("role_name"):
        blueprint.set_attribute("role_name", args.ego_role_name)

    variants: list[dict[str, Any]] = []
    try:
        for z_offset in _parse_float_list(args.spawn_z_offsets):
            for spec in _physics_variant_specs(args):
                variants.append(_run_variant(carla, world, blueprint, args, spec, z_offset))
    finally:
        _destroy_matching_vehicles(world, args.actor_id, args.ego_role_name)
        _tick(world, 5)
        try:
            world.apply_settings(original_settings)
        except Exception:
            pass

    spawned_count = sum(1 for item in variants if item.get("spawned"))
    stable_count = sum(1 for item in variants if item.get("stable"))
    driveable_count = sum(1 for item in variants if item.get("driveable"))
    checks = {
        "blueprint_found": True,
        "spawned": spawned_count >= args.min_spawned_variants,
        "stable_variant_available": stable_count >= args.min_stable_variants,
        "driveable_variant_available": driveable_count >= args.min_driveable_variants,
    }
    summary = {
        "run_dir": str(Path(args.run_dir).resolve()),
        "map": world.get_map().name if world.get_map() else None,
        "actor_id": args.actor_id,
        "start_pose": {
            "x": args.spawn_x,
            "y": args.spawn_y,
            "z": args.spawn_z,
            "pitch_deg": args.spawn_pitch_deg,
            "yaw_deg": args.spawn_yaw_deg,
            "roll_deg": args.spawn_roll_deg,
            "z_offsets_m": _parse_float_list(args.spawn_z_offsets),
        },
        "thresholds": {
            "max_abs_pitch_deg": args.max_abs_pitch_deg,
            "max_abs_roll_deg": args.max_abs_roll_deg,
            "min_z_m": args.min_z_m,
            "min_delta_m": args.min_delta_m,
            "min_speed_mps": args.min_speed_mps,
        },
        "blueprint_found": True,
        "passed": all(checks.values()),
        "checks": checks,
        "variants": variants,
    }
    return _payload_from_summary(args, summary)


def write_artifacts(run_dir: Path, payload: dict[str, Any]) -> dict[str, str]:
    stamp = _utc_stamp()
    output_dir = run_dir / "runtime_verification" / f"metric_probe_robobus_qiyu_spawn_stability_{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"metric_probe_robobus_qiyu_spawn_stability_{stamp}.json"
    summary = output_dir / "metric_probe_robobus_qiyu_spawn_stability_summary.json"
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
    parser.add_argument("--profile", default="robobus117th_qiyu_spawn_stability")
    parser.add_argument("--carla-host", default=os.environ.get("SIMCTL_CARLA_HOST", "127.0.0.1"))
    parser.add_argument("--carla-port", type=int, default=int(os.environ.get("SIMCTL_CARLA_RPC_PORT", "2000")))
    parser.add_argument(
        "--carla-root",
        default=os.environ.get("CARLA_ROOT", os.environ.get("CARLA_0915_ROOT", str(Path.home() / "CARLA_0.9.15"))),
    )
    parser.add_argument("--carla-map", default="")
    parser.add_argument("--carla-timeout-sec", type=float, default=30.0)
    parser.add_argument("--map-load-wait-sec", type=float, default=2.0)
    parser.add_argument("--actor-id", default="vehicle.pixmoving.robobus")
    parser.add_argument("--ego-role-name", default="ego_vehicle")
    parser.add_argument("--spawn-x", type=float, default=103.34)
    parser.add_argument("--spawn-y", type=float, default=636.097)
    parser.add_argument("--spawn-z", type=float, default=-0.1021)
    parser.add_argument("--spawn-yaw-deg", type=float, default=178.90)
    parser.add_argument("--spawn-pitch-deg", type=float, default=0.0)
    parser.add_argument("--spawn-roll-deg", type=float, default=0.0)
    parser.add_argument("--spawn-z-offsets", default="0.0,1.0,2.0")
    parser.add_argument("--com-z-cm-values", default="-50,-100,-200")
    parser.add_argument("--mass-kg", type=float, default=12000.0)
    parser.add_argument("--fixed-delta-sec", type=float, default=0.05)
    parser.add_argument("--settle-ticks", type=int, default=100)
    parser.add_argument("--drive-ticks", type=int, default=60)
    parser.add_argument("--throttle", type=float, default=0.35)
    parser.add_argument("--steer", type=float, default=0.0)
    parser.add_argument("--max-abs-pitch-deg", type=float, default=12.0)
    parser.add_argument("--max-abs-roll-deg", type=float, default=12.0)
    parser.add_argument("--min-z-m", type=float, default=-20.0)
    parser.add_argument("--min-delta-m", type=float, default=1.0)
    parser.add_argument("--min-speed-mps", type=float, default=0.5)
    parser.add_argument("--min-spawned-variants", type=int, default=1)
    parser.add_argument("--min-stable-variants", type=int, default=1)
    parser.add_argument("--min-driveable-variants", type=int, default=1)
    parser.add_argument("--worker-timeout-sec", type=float, default=180.0)
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
                "robobus_qiyu_spawn_stability_worker_timeout",
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
                "robobus_qiyu_spawn_stability_worker_crashed",
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
