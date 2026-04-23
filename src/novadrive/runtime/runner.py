from __future__ import annotations

import argparse
import math
import time
from pathlib import Path
from typing import Any

from novadrive.control import PurePursuitPidController
from novadrive.foundation import EgoState, RuntimeSample, RuntimeStatus, Vector3
from novadrive.foundation.geometry import distance_xy
from novadrive.perception import BEVFusionProvider, CarlaTruthProvider
from novadrive.reasoning import ConstantVelocityPredictor, NearestNeighborTracker, RiskAssessor
from novadrive.runtime.recorder import RuntimeRecorder
from novadrive.runtime.scenario_loader import NovaDriveActorSpec, load_novadrive_scenario
from novadrive.planning import BehaviorPlanner, ReferenceLinePlanner


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NovaDrive without Autoware")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--mode", choices=["mock", "carla"], default="carla")
    parser.add_argument("--carla-host", default="127.0.0.1")
    parser.add_argument("--carla-port", type=int, default=2000)
    parser.add_argument("--ego-vehicle-role-name", default="ego_vehicle")
    parser.add_argument("--bevfusion-json")
    parser.add_argument("--tick-sec", type=float, default=0.05)
    parser.add_argument("--max-duration-sec", type=float)
    return parser.parse_args(argv)


def run_mock(args: argparse.Namespace) -> int:
    scenario = load_novadrive_scenario(args.scenario)
    run_dir = Path(args.run_dir).resolve()
    recorder = RuntimeRecorder(run_dir, scenario.scenario_id)
    tracker = NearestNeighborTracker()
    predictor = ConstantVelocityPredictor()
    risk_assessor = RiskAssessor()
    behavior_planner = BehaviorPlanner(cruise_speed_mps=scenario.target_speed_mps)
    trajectory_planner = ReferenceLinePlanner()
    controller = PurePursuitPidController()

    start_time = time.time()
    duration = float(args.max_duration_sec or min(scenario.max_duration_sec, 10.0))
    steps = max(20, int(duration / args.tick_sec))
    for index in range(steps):
        alpha = min(1.0, (index + 1) / steps)
        x = scenario.start.x + (scenario.goal.x - scenario.start.x) * alpha
        y = scenario.start.y + (scenario.goal.y - scenario.start.y) * alpha
        timestamp = start_time + index * args.tick_sec
        ego = EgoState(timestamp, "carla_world", Vector3(x, y, scenario.start.z), yaw_rad=0.0, velocity_mps=scenario.target_speed_mps)
        detections = []
        tracks = tracker.update(detections)
        predictions = predictor.predict(tracks)
        risk = risk_assessor.assess(ego, predictions)
        route_completion = trajectory_planner.route_completion(ego, scenario.start, scenario.goal)
        behavior = behavior_planner.decide(risk, route_completion=route_completion)
        trajectory = trajectory_planner.plan(ego, scenario.goal, behavior)
        control = controller.control(ego, trajectory)
        recorder.add_sample(
            RuntimeSample(timestamp, ego, behavior, risk, control, route_completion, len(detections), len(tracks))
        )

    metrics = _metrics_from_samples(recorder.samples, perception_source=scenario.perception_source)
    payload = _evidence_payload(
        scenario_id=scenario.scenario_id,
        run_dir=run_dir,
        status=RuntimeStatus.COMPLETED,
        perception_source="mock",
        samples=recorder.samples,
        events=recorder.events,
        metrics=metrics,
    )
    recorder.write(payload)
    print(f"novadrive_evidence={payload['artifacts']['runtime_evidence']}")
    return 0


def run_carla(args: argparse.Namespace) -> int:
    scenario = load_novadrive_scenario(args.scenario)
    run_dir = Path(args.run_dir).resolve()
    recorder = RuntimeRecorder(run_dir, scenario.scenario_id)
    carla = _load_carla()
    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(10.0)
    world = client.get_world()
    ego = _get_or_spawn_ego(carla, world, scenario, args.ego_vehicle_role_name)
    spawned_actors = _spawn_scripted_actors(carla, world, scenario.actors)
    collision_count = 0
    collision_sensor = _attach_collision_sensor(carla, world, ego, lambda: _increment_collision(recorder))

    tracker = NearestNeighborTracker()
    predictor = ConstantVelocityPredictor()
    risk_assessor = RiskAssessor()
    behavior_planner = BehaviorPlanner(cruise_speed_mps=scenario.target_speed_mps)
    trajectory_planner = ReferenceLinePlanner()
    controller = PurePursuitPidController()
    perception = (
        BEVFusionProvider(args.bevfusion_json)
        if scenario.perception_source == "bevfusion"
        else CarlaTruthProvider(world, ego, ego_role_name=args.ego_vehicle_role_name)
    )

    started = time.monotonic()
    status = RuntimeStatus.RUNNING
    failure_reason = None
    try:
        while time.monotonic() - started <= float(args.max_duration_sec or scenario.max_duration_sec):
            elapsed = time.monotonic() - started
            _advance_scripted_actors(spawned_actors, scenario.actors, elapsed)
            now = time.time()
            ego_state = _ego_state(ego, now)
            snapshot = perception.detect(now)
            if not snapshot.healthy:
                status = RuntimeStatus.DEGRADED
                recorder.add_event({"type": "perception_unhealthy", "timestamp": now, "reason": snapshot.reason})
            tracks = tracker.update(snapshot.detections)
            predictions = predictor.predict(tracks)
            risk = risk_assessor.assess(ego_state, predictions)
            route_completion = trajectory_planner.route_completion(ego_state, scenario.start, scenario.goal)
            behavior = behavior_planner.decide(risk, route_completion=route_completion)
            trajectory = trajectory_planner.plan(ego_state, scenario.goal, behavior)
            control = controller.control(ego_state, trajectory)
            ego.apply_control(carla.VehicleControl(throttle=control.throttle, brake=control.brake, steer=control.steer))
            recorder.add_sample(
                RuntimeSample(now, ego_state, behavior, risk, control, route_completion, len(snapshot.detections), len(tracks))
            )
            if route_completion >= 0.98:
                break
            time.sleep(max(0.01, float(args.tick_sec)))
        if status != RuntimeStatus.DEGRADED:
            status = RuntimeStatus.COMPLETED
    except Exception as exc:
        status = RuntimeStatus.FAILED
        failure_reason = str(exc)
        recorder.add_event({"type": "runtime_exception", "timestamp": time.time(), "reason": failure_reason})
    finally:
        ego.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0))
        if collision_sensor is not None:
            collision_sensor.destroy()
        for actor in spawned_actors:
            actor.destroy()

    collision_count = sum(1 for event in recorder.events if event.get("type") == "collision")
    metrics = _metrics_from_samples(recorder.samples, perception_source=scenario.perception_source)
    metrics["collision_count"] = float(collision_count)
    payload = _evidence_payload(
        scenario_id=scenario.scenario_id,
        run_dir=run_dir,
        status=status,
        perception_source=scenario.perception_source,
        samples=recorder.samples,
        events=recorder.events,
        metrics=metrics,
        failure_reason=failure_reason,
    )
    recorder.write(payload)
    print(f"novadrive_evidence={payload['artifacts']['runtime_evidence']}")
    return 0 if status in {RuntimeStatus.COMPLETED, RuntimeStatus.DEGRADED} else 1


def _metrics_from_samples(samples: list[RuntimeSample], *, perception_source: str) -> dict[str, float]:
    if not samples:
        return {
            "route_completion": 0.0,
            "collision_count": 0.0,
            "min_ttc_sec": 0.0,
            "min_distance_m": 0.0,
            "control_rate_hz": 0.0,
            "perception_frame_rate_hz": 0.0,
            "trajectory_valid_ratio": 0.0,
            "novadrive_runtime_passed": 0.0,
        }
    duration = max(1e-3, samples[-1].timestamp - samples[0].timestamp)
    min_ttc = min(sample.risk.min_ttc_sec for sample in samples)
    min_distance = min(sample.risk.min_distance_m for sample in samples)
    control_rate_hz = len(samples) / duration
    perception_frames = sum(1 for sample in samples if sample.detection_count > 0 or perception_source in {"carla_truth", "mock"})
    metrics = {
        "route_completion": max(sample.route_completion for sample in samples),
        "collision_count": 0.0,
        "min_ttc_sec": min_ttc,
        "min_distance_m": min_distance,
        "control_rate_hz": control_rate_hz,
        "perception_frame_rate_hz": perception_frames / duration,
        "trajectory_valid_ratio": 1.0,
    }
    metrics["novadrive_runtime_passed"] = 1.0 if (
        metrics["route_completion"] >= 0.8
        and metrics["collision_count"] <= 0.0
        and metrics["min_ttc_sec"] >= 1.5
        and metrics["control_rate_hz"] >= 10.0
    ) else 0.0
    return metrics


def _evidence_payload(
    *,
    scenario_id: str,
    run_dir: Path,
    status: RuntimeStatus,
    perception_source: str,
    samples: list[RuntimeSample],
    events: list[dict[str, Any]],
    metrics: dict[str, float],
    failure_reason: str | None = None,
) -> dict[str, Any]:
    evidence_path = run_dir / "runtime_verification"
    summary = {
        "runtime_status": status.value,
        "sample_count": len(samples),
        "route_completion": metrics.get("route_completion", 0.0),
        "collision_count": metrics.get("collision_count", 0.0),
        "min_ttc_sec": metrics.get("min_ttc_sec", 0.0),
        "min_distance_m": metrics.get("min_distance_m", 0.0),
        "control_rate_hz": metrics.get("control_rate_hz", 0.0),
        "perception_frame_rate_hz": metrics.get("perception_frame_rate_hz", 0.0),
        "trajectory_valid_ratio": metrics.get("trajectory_valid_ratio", 0.0),
        "failure_reason": failure_reason,
    }
    return {
        "kind": "novadrive_run",
        "scenario_id": scenario_id,
        "perception_source": perception_source,
        "overall_passed": bool(metrics.get("novadrive_runtime_passed", 0.0) >= 1.0),
        "summary": summary,
        "metrics": metrics,
        "events": events,
        "samples": samples[-200:],
        "artifacts": {
            "runtime_evidence": str(evidence_path),
        },
    }


def _load_carla() -> Any:
    try:
        import carla  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit("Missing CARLA Python module. Run on the Ubuntu runtime host with CARLA PythonAPI on PYTHONPATH.") from exc
    return carla


def _get_or_spawn_ego(carla: Any, world: Any, scenario: Any, role_name: str) -> Any:
    for actor in world.get_actors().filter("vehicle.*"):
        if actor.attributes.get("role_name") in {role_name, "ego_vehicle", "hero"}:
            return actor
    bp_lib = world.get_blueprint_library()
    candidates = bp_lib.filter("vehicle.pixmoving.robobus") or bp_lib.filter("vehicle.*")
    if not candidates:
        raise RuntimeError("No vehicle blueprint is available for NovaDrive ego")
    blueprint = candidates[0]
    blueprint.set_attribute("role_name", role_name)
    transform = carla.Transform(
        carla.Location(x=scenario.start.x, y=scenario.start.y, z=max(0.2, scenario.start.z + 0.2)),
        carla.Rotation(yaw=scenario.start_yaw_deg),
    )
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise RuntimeError("Unable to spawn NovaDrive ego actor")
    return actor


def _spawn_scripted_actors(carla: Any, world: Any, specs: list[NovaDriveActorSpec]) -> list[Any]:
    actors = []
    bp_lib = world.get_blueprint_library()
    for spec in specs:
        candidates = bp_lib.filter(spec.type_id)
        if not candidates:
            continue
        transform = carla.Transform(
            carla.Location(x=spec.start.x, y=spec.start.y, z=max(0.2, spec.start.z + 0.2)),
            carla.Rotation(yaw=spec.yaw_deg),
        )
        actor = world.try_spawn_actor(candidates[0], transform)
        if actor is not None:
            actors.append(actor)
    return actors


def _advance_scripted_actors(actors: list[Any], specs: list[NovaDriveActorSpec], elapsed: float) -> None:
    for actor, spec in zip(actors, specs):
        if elapsed < spec.activation_sec:
            actor.set_target_velocity(type(actor.get_velocity())(0.0, 0.0, 0.0))
            continue
        transform = actor.get_transform()
        velocity = actor.get_velocity()
        velocity.x = spec.speed_x_mps
        if spec.final_y is not None:
            dy = spec.final_y - transform.location.y
            velocity.y = max(-1.0, min(1.0, dy))
        actor.set_target_velocity(velocity)


def _attach_collision_sensor(carla: Any, world: Any, ego: Any, callback: Any) -> Any:
    bp = world.get_blueprint_library().find("sensor.other.collision")
    sensor = world.spawn_actor(bp, carla.Transform(), attach_to=ego)
    sensor.listen(lambda _event: callback())
    return sensor


def _increment_collision(recorder: RuntimeRecorder) -> None:
    recorder.add_event({"type": "collision", "timestamp": time.time()})


def _ego_state(actor: Any, timestamp: float) -> EgoState:
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x * velocity.x + velocity.y * velocity.y + velocity.z * velocity.z)
    return EgoState(
        timestamp=timestamp,
        frame_id="carla_world",
        position=Vector3(float(transform.location.x), float(transform.location.y), float(transform.location.z)),
        yaw_rad=math.radians(float(transform.rotation.yaw)),
        velocity_mps=float(speed),
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "mock":
        return run_mock(args)
    return run_carla(args)


if __name__ == "__main__":
    raise SystemExit(main())
