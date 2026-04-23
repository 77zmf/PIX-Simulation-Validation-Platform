from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .config import dump_json, utc_now


EMPTY_SCENE_TTC_SEC = 999.0
GOAL_DISTANCE_TOLERANCE_M = 8.0


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _xy(location: dict[str, Any] | None) -> tuple[float, float] | None:
    if not isinstance(location, dict):
        return None
    return (_as_float(location.get("x")), _as_float(location.get("y")))


def _distance_with_optional_y_flip(a: tuple[float, float], b: tuple[float, float]) -> float:
    direct = math.hypot(a[0] - b[0], a[1] - b[1])
    flipped = math.hypot(a[0] - b[0], a[1] + b[1])
    return min(direct, flipped)


def _service_calls_valid(evidence: dict[str, Any]) -> tuple[bool, list[str]]:
    invalid_steps: list[str] = []
    for call in evidence.get("service_calls") or []:
        if not isinstance(call, dict):
            continue
        rc = call.get("returncode")
        if rc not in (None, 0):
            invalid_steps.append(str(call.get("step") or call.get("name") or "unknown"))
    return not invalid_steps, invalid_steps


def _goal_reached(evidence: dict[str, Any], last_location: dict[str, Any] | None) -> bool:
    summary = evidence.get("summary") or {}
    if summary.get("reached_near_goal") is True:
        return True
    if summary.get("reached_near_goal") is False:
        return False
    goal_xy = _xy(evidence.get("goal"))
    last_xy = _xy(last_location)
    if goal_xy is None or last_xy is None:
        return False
    return _distance_with_optional_y_flip(last_xy, goal_xy) <= GOAL_DISTANCE_TOLERANCE_M


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _closed_loop_artifacts(runtime_dir: Path) -> list[Path]:
    patterns = [
        "closed_loop*.json",
        "*route_sync*.json",
        "*route_retry*.json",
    ]
    paths: set[Path] = set()
    for pattern in patterns:
        paths.update(runtime_dir.glob(pattern))
    return sorted(path for path in paths if not path.name.endswith("_summary.json"))


def _dynamic_probe_artifacts(runtime_dir: Path) -> list[Path]:
    paths: set[Path] = set()
    for pattern in ("l1_*/*.json", "l2_*/*.json", "l3_*/*.json", "carla_dynamic_*/*.json"):
        paths.update(runtime_dir.glob(pattern))
    return sorted(path for path in paths if not path.name.endswith("_summary.json"))


def _sensor_probe_artifacts(runtime_dir: Path) -> list[Path]:
    paths: set[Path] = set()
    paths.update(runtime_dir.glob("sensor_topics_*/*.json"))
    return sorted(path for path in paths if not path.name.endswith("_summary.json"))


def _metric_probe_artifacts(runtime_dir: Path) -> list[Path]:
    paths: set[Path] = set()
    for pattern in ("perception_readiness_*/*.json", "metric_probe_*/*.json"):
        paths.update(runtime_dir.glob(pattern))
    return sorted(path for path in paths if not path.name.endswith("_summary.json"))


def _sumo_cosim_artifacts(runtime_dir: Path) -> list[Path]:
    paths: set[Path] = set()
    paths.update(runtime_dir.glob("sumo_cosim_*/*.json"))
    return sorted(path for path in paths if not path.name.endswith("_summary.json"))


def _novadrive_artifacts(runtime_dir: Path) -> list[Path]:
    paths: set[Path] = set()
    paths.update(runtime_dir.glob("novadrive_*.json"))
    return sorted(path for path in paths if path.name != "novadrive_summary.json")


def _calibration_scene_artifacts(runtime_dir: Path) -> list[Path]:
    paths: set[Path] = set()
    paths.update(runtime_dir.glob("calibration_scene/*_spawn.json"))
    return sorted(paths)


def _camera_fiducial_artifacts(runtime_dir: Path) -> list[Path]:
    paths: set[Path] = set()
    paths.update(runtime_dir.glob("calibration/camera_fiducial_board_detection/detection_result.json"))
    return sorted(paths)


def _dynamic_probe_matches_scenario(attempt: dict[str, Any], traffic: dict[str, Any], empty_scene: bool) -> bool:
    if empty_scene:
        return False
    mode = str(traffic.get("mode") or "").lower()
    kind = str(attempt.get("kind") or "").lower()
    source = str(attempt.get("perception_source") or "").lower()
    try:
        vehicle_count = int(traffic.get("vehicles") or 0)
    except (TypeError, ValueError):
        vehicle_count = 0
    multi_actor_mode = "multi_actor" in mode or vehicle_count >= 2

    if "actor_bridge" in mode and source != "actor_bridge":
        return False
    if "dummy" in mode and source != "dummy_injection":
        return False
    pedestrian_mode = (
        "occluded_pedestrian" in mode
        or "occluded_crosswalk" in mode
        or "pedestrian" in mode
    )
    if pedestrian_mode and not kind.startswith("l3_occluded_pedestrian"):
        return False
    if "multi_actor" in mode and not kind.startswith("l2_multi_actor"):
        return False
    if "merge" in mode and kind != "l2_merge":
        if not (multi_actor_mode and kind.startswith("l2_multi_actor")):
            return False
    if "close_cut_in" in mode and kind != "l2_close_cut_in":
        return False
    if "cut_in" in mode and kind not in {"l2_cut_in", "l2_close_cut_in", "l2_multi_actor_cut_in_lead_brake"}:
        return False
    if "static" in mode and kind != "l1_static":
        return False
    return True


def _dynamic_probe_attempt(path: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    verdict = payload.get("verdict")
    summary = payload.get("summary")
    if not isinstance(verdict, dict) or not isinstance(summary, dict):
        return None
    valid, invalid_steps = _service_calls_valid(payload)
    object_pipeline = payload.get("object_pipeline") if isinstance(payload.get("object_pipeline"), dict) else {}
    recording = payload.get("recording") if isinstance(payload.get("recording"), dict) else {}
    classification = str(payload.get("classification") or path.stem)
    kind = path.stem
    for known_kind in (
        "l3_occluded_pedestrian_double_occluder",
        "l3_occluded_pedestrian_close_yield",
        "l3_occluded_pedestrian",
        "l2_multi_actor_cut_in_lead_brake",
        "l2_close_cut_in",
        "l2_merge",
        "l2_cut_in",
        "l1_static",
    ):
        if path.stem == known_kind or path.stem.startswith(f"{known_kind}_"):
            kind = known_kind
            break
    attempt = {
        "path": str(path),
        "valid": valid,
        "kind": kind,
        "classification": classification,
        "perception_source": object_pipeline.get("perception_source"),
        "overall_passed": bool(verdict.get("overall_passed")),
        "safety_passed": bool(verdict.get("safety_passed")),
        "autoware_dynamic_actor_response_passed": bool(
            verdict.get("autoware_dynamic_actor_response_passed")
        ),
        "objects_topic_nonempty": bool(object_pipeline.get("objects_topic_nonempty_after_injection")),
        "dummy_object_injected": bool(object_pipeline.get("dummy_object_injected")),
        "moved": bool(summary.get("moved")),
        "collision_count": _as_float(summary.get("collision_count")),
        "min_distance_m": _as_float(summary.get("min_distance_m"), math.nan),
        "min_ttc_sec": _as_float(summary.get("min_ttc_sec"), math.nan),
        "actor_count_spawned": _as_float(summary.get("actor_count_spawned"), math.nan),
        "actor_count_observed": _as_float(summary.get("actor_count_observed"), math.nan),
        "object_pipeline_nonempty_duration_ratio": _as_float(
            summary.get("object_pipeline_nonempty_duration_ratio"), math.nan
        ),
        "total_delta_m": _as_float(summary.get("total_delta_m")),
        "max_speed_mps": _as_float(summary.get("max_speed_mps")),
        "sample_count": int(summary.get("sample_count") or 0),
        "reaction_reason": summary.get("reaction_reason"),
        "rosbag_dir": recording.get("rosbag_dir"),
        "carla_recorder": recording.get("carla_recorder"),
    }
    if not valid:
        attempt["invalid_steps"] = invalid_steps
    return attempt


def _sensor_probe_attempt(path: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    summary = payload.get("summary")
    if "overall_passed" not in payload or not isinstance(summary, dict):
        return None
    required_topic_count = int(summary.get("required_topic_count") or 0)
    passing_topic_count = int(summary.get("passing_topic_count") or 0)
    sample_required_topic_count = int(summary.get("sample_required_topic_count") or 0)
    sample_received_count = int(summary.get("sample_received_count") or 0)
    return {
        "path": str(path),
        "profile": payload.get("profile"),
        "overall_passed": bool(payload.get("overall_passed")),
        "required_topic_count": required_topic_count,
        "passing_topic_count": passing_topic_count,
        "sample_required_topic_count": sample_required_topic_count,
        "sample_received_count": sample_received_count,
        "missing_topics": summary.get("missing_topics") or [],
        "sample_missing_topics": summary.get("sample_missing_topics") or [],
        "groups": summary.get("groups") or {},
    }


def _metric_probe_attempt(path: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    raw_metrics = payload.get("metrics")
    if not isinstance(raw_metrics, dict):
        return None
    metrics: dict[str, float] = {}
    non_numeric_metrics: list[str] = []
    for name, value in raw_metrics.items():
        if isinstance(value, bool):
            non_numeric_metrics.append(str(name))
            continue
        try:
            metrics[str(name)] = float(value)
        except (TypeError, ValueError):
            non_numeric_metrics.append(str(name))
    if not metrics:
        return None
    return {
        "path": str(path),
        "profile": payload.get("profile"),
        "overall_passed": bool(payload.get("overall_passed")),
        "metrics": metrics,
        "missing_metrics": payload.get("missing_metrics") or [],
        "missing_topics": payload.get("missing_topics") or [],
        "sample_missing_topics": payload.get("sample_missing_topics") or [],
        "blocked_reason": payload.get("blocked_reason"),
        "metrics_file": payload.get("metrics_file"),
        "non_numeric_metrics": non_numeric_metrics,
    }


def _sumo_cosim_attempt(path: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("kind") != "sumo_cosim_probe":
        return None
    raw_metrics = payload.get("metrics")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if not isinstance(raw_metrics, dict):
        return None
    metrics: dict[str, float] = {}
    for name, value in raw_metrics.items():
        if isinstance(value, bool):
            metrics[str(name)] = 1.0 if value else 0.0
            continue
        try:
            metrics[str(name)] = float(value)
        except (TypeError, ValueError):
            continue
    if not metrics:
        return None
    return {
        "path": str(path),
        "profile": payload.get("profile"),
        "overall_passed": bool(payload.get("overall_passed")),
        "metrics": metrics,
        "summary": summary,
        "sumo_cosim_alive": bool(summary.get("sumo_cosim_alive")),
        "sumo_actor_count": int(summary.get("sumo_actor_count") or 0),
        "sumo_route_loaded": bool(summary.get("sumo_route_loaded")),
        "autoware_object_stream_seen": bool(summary.get("autoware_object_stream_seen")),
        "ego_control_command_seen": bool(summary.get("ego_control_command_seen")),
    }


def _calibration_scene_attempt(path: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    if "target_count" not in payload or "spawned_count" not in payload:
        return None
    spawned = payload.get("spawned") if isinstance(payload.get("spawned"), list) else []
    targets = payload.get("targets") if isinstance(payload.get("targets"), list) else []
    marker_overlay_count = 0
    panel_overlay_line_count = 0
    panel_count = 0
    marker_payload_count = 0
    for item in spawned:
        if not isinstance(item, dict):
            continue
        marker_overlay = item.get("marker_overlay") if isinstance(item.get("marker_overlay"), dict) else {}
        panel_overlay = item.get("panel_overlay") if isinstance(item.get("panel_overlay"), dict) else {}
        panel = item.get("panel") if isinstance(item.get("panel"), dict) else {}
        marker = item.get("marker") if isinstance(item.get("marker"), dict) else {}
        marker_overlay_count += int(marker_overlay.get("marker_count") or 0)
        panel_overlay_line_count += int(panel_overlay.get("line_count") or 0)
        if panel:
            panel_count += 1
        if marker.get("qr_payload"):
            marker_payload_count += 1
    if not marker_payload_count:
        for target in targets:
            if not isinstance(target, dict):
                continue
            marker = target.get("marker") if isinstance(target.get("marker"), dict) else {}
            if marker.get("qr_payload"):
                marker_payload_count += 1
    spawned_count = int(payload.get("spawned_count") or 0)
    target_count = int(payload.get("target_count") or 0)
    return {
        "path": str(path),
        "scene_asset_id": payload.get("scene_asset_id"),
        "target_count": target_count,
        "spawned_count": spawned_count,
        "failed_count": int(payload.get("failed_count") or 0),
        "skipped_count": int(payload.get("skipped_count") or 0),
        "marker_overlay_count": marker_overlay_count,
        "panel_overlay_line_count": panel_overlay_line_count,
        "panel_count": panel_count,
        "marker_payload_count": marker_payload_count,
        "overall_passed": spawned_count >= target_count and target_count > 0,
    }


def _camera_fiducial_attempt(path: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    if "detection_count" not in payload or "passed" not in payload:
        return None
    captured_images = payload.get("captured_images") if isinstance(payload.get("captured_images"), list) else []
    return {
        "path": str(path),
        "overall_passed": bool(payload.get("passed")),
        "capture_from_carla": bool(payload.get("capture_from_carla")),
        "expected_board_count": int(payload.get("expected_board_count") or 0),
        "captured_image_count": len(captured_images),
        "detection_count": int(payload.get("detection_count") or 0),
        "qr_count": int(payload.get("qr_count") or 0),
        "aruco_count": int(payload.get("aruco_count") or 0),
        "binary_fiducial_candidate_count": int(payload.get("binary_fiducial_candidate_count") or 0),
        "image_dir": payload.get("image_dir"),
    }


def _novadrive_attempt(path: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("kind") != "novadrive_run":
        return None
    raw_metrics = payload.get("metrics")
    if not isinstance(raw_metrics, dict):
        return None
    metrics: dict[str, float] = {}
    for name, value in raw_metrics.items():
        if isinstance(value, bool):
            metrics[str(name)] = 1.0 if value else 0.0
            continue
        try:
            metrics[str(name)] = float(value)
        except (TypeError, ValueError):
            continue
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {
        "path": str(path),
        "overall_passed": bool(payload.get("overall_passed")),
        "scenario_id": payload.get("scenario_id"),
        "perception_source": payload.get("perception_source"),
        "runtime_status": summary.get("runtime_status"),
        "sample_count": int(summary.get("sample_count") or 0),
        "failure_reason": summary.get("failure_reason") or payload.get("failure_reason"),
        "metrics": metrics,
        "event_count": len(payload.get("events") or []),
    }


def collect_runtime_evidence(run_dir: Path, run_result: dict[str, Any]) -> dict[str, Any]:
    runtime_dir = run_dir / "runtime_verification"
    artifacts = _closed_loop_artifacts(runtime_dir) if runtime_dir.exists() else []
    dynamic_artifacts = _dynamic_probe_artifacts(runtime_dir) if runtime_dir.exists() else []
    sensor_artifacts = _sensor_probe_artifacts(runtime_dir) if runtime_dir.exists() else []
    metric_artifacts = _metric_probe_artifacts(runtime_dir) if runtime_dir.exists() else []
    sumo_cosim_artifacts = _sumo_cosim_artifacts(runtime_dir) if runtime_dir.exists() else []
    novadrive_artifacts = _novadrive_artifacts(runtime_dir) if runtime_dir.exists() else []
    calibration_scene_artifacts = _calibration_scene_artifacts(runtime_dir) if runtime_dir.exists() else []
    camera_fiducial_artifacts = _camera_fiducial_artifacts(runtime_dir) if runtime_dir.exists() else []
    attempts: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    dynamic_attempts: list[dict[str, Any]] = []
    ignored_dynamic: list[dict[str, Any]] = []
    sensor_attempts: list[dict[str, Any]] = []
    ignored_sensor: list[dict[str, Any]] = []
    metric_attempts: list[dict[str, Any]] = []
    ignored_metric: list[dict[str, Any]] = []
    sumo_cosim_attempts: list[dict[str, Any]] = []
    ignored_sumo_cosim: list[dict[str, Any]] = []
    novadrive_attempts: list[dict[str, Any]] = []
    ignored_novadrive: list[dict[str, Any]] = []
    calibration_scene_attempts: list[dict[str, Any]] = []
    ignored_calibration_scene: list[dict[str, Any]] = []
    camera_fiducial_attempts: list[dict[str, Any]] = []
    ignored_camera_fiducial: list[dict[str, Any]] = []

    for path in artifacts:
        payload = _load_json(path)
        if payload is None:
            ignored.append({"path": str(path), "reason": "unreadable_json"})
            continue
        valid, invalid_steps = _service_calls_valid(payload)
        summary = payload.get("summary") or {}
        last_location = summary.get("last_location") or payload.get("end_location")
        total_delta_m = _as_float(summary.get("total_delta_m"))
        max_speed_mps = _as_float(summary.get("max_speed_mps"))
        moved = bool(summary.get("moved")) or total_delta_m > 5.0
        reached = _goal_reached(payload, last_location if isinstance(last_location, dict) else None)
        attempt = {
            "path": str(path),
            "valid": valid,
            "moved": moved,
            "reached_near_goal": reached,
            "total_delta_m": total_delta_m,
            "max_speed_mps": max_speed_mps,
            "effective_goal": summary.get("effective_goal"),
            "final_map_location": summary.get("final_map_location"),
            "final_carla_waypoint": summary.get("final_carla_waypoint"),
            "lateral_error_m": _as_float(summary.get("lateral_error_m"), math.nan),
            "route_goal_lateral_error_m": _as_float(
                summary.get("route_goal_lateral_error_m"), math.nan
            ),
            "longitudinal_error_m": _as_float(summary.get("longitudinal_error_m"), math.nan),
            "jerk_mps3": _as_float(summary.get("jerk_mps3"), math.nan),
            "max_jerk_mps3": _as_float(summary.get("max_jerk_mps3"), math.nan),
            "stopped_before_goal": bool(summary.get("stopped_before_goal")),
            "sample_count": int(summary.get("sample_count") or 0),
        }
        ros_telemetry = summary.get("ros_telemetry")
        if isinstance(ros_telemetry, dict):
            attempt["ros_telemetry"] = {
                "enabled": bool(ros_telemetry.get("enabled")),
                "error": ros_telemetry.get("error"),
                "topic_counts": ros_telemetry.get("topic_counts") or {},
                "tail_stats": ros_telemetry.get("tail_stats") or {},
            }
        if valid:
            attempts.append(attempt)
        else:
            attempt["invalid_steps"] = invalid_steps
            ignored.append({"path": str(path), "reason": "service_call_failed", "invalid_steps": invalid_steps})

    successful = [item for item in attempts if item["moved"] and item["reached_near_goal"]]
    traffic = (run_result.get("scenario_params") or {}).get("traffic_profile") or {}
    traffic_mode = str(traffic.get("mode", "")).lower()
    empty_scene = (
        (traffic_mode in {"none", "empty"} or traffic_mode.startswith("empty_"))
        and int(traffic.get("vehicles") or 0) == 0
        and int(traffic.get("pedestrians") or 0) == 0
    )

    for path in dynamic_artifacts:
        payload = _load_json(path)
        if payload is None:
            ignored_dynamic.append({"path": str(path), "reason": "unreadable_json"})
            continue
        attempt = _dynamic_probe_attempt(path, payload)
        if attempt is None:
            ignored_dynamic.append({"path": str(path), "reason": "not_dynamic_probe_artifact"})
            continue
        if not _dynamic_probe_matches_scenario(attempt, traffic, empty_scene):
            ignored_dynamic.append({"path": str(path), "reason": "scenario_filter_mismatch"})
            continue
        if attempt["valid"]:
            dynamic_attempts.append(attempt)
        else:
            ignored_dynamic.append(
                {"path": str(path), "reason": "service_call_failed", "invalid_steps": attempt["invalid_steps"]}
            )

    if dynamic_attempts:
        latest_by_probe: dict[str, dict[str, Any]] = {}
        superseded: list[dict[str, Any]] = []
        for attempt in sorted(dynamic_attempts, key=lambda item: str(item.get("path") or "")):
            probe_key = ":".join(
                [
                    str(attempt.get("kind") or "unknown"),
                    str(attempt.get("classification") or "default"),
                    str(attempt.get("perception_source") or "default"),
                ]
            )
            previous = latest_by_probe.get(probe_key)
            if previous is not None:
                superseded.append(
                    {
                        "path": previous["path"],
                        "reason": "superseded_by_newer_dynamic_probe",
                        "probe_key": probe_key,
                    }
                )
            latest_by_probe[probe_key] = attempt
        dynamic_attempts = list(latest_by_probe.values())
        ignored_dynamic.extend(superseded)

    for path in sensor_artifacts:
        payload = _load_json(path)
        if payload is None:
            ignored_sensor.append({"path": str(path), "reason": "unreadable_json"})
            continue
        attempt = _sensor_probe_attempt(path, payload)
        if attempt is None:
            ignored_sensor.append({"path": str(path), "reason": "not_sensor_probe_artifact"})
            continue
        sensor_attempts.append(attempt)

    for path in metric_artifacts:
        payload = _load_json(path)
        if payload is None:
            ignored_metric.append({"path": str(path), "reason": "unreadable_json"})
            continue
        attempt = _metric_probe_attempt(path, payload)
        if attempt is None:
            ignored_metric.append({"path": str(path), "reason": "not_metric_probe_artifact"})
            continue
        metric_attempts.append(attempt)

    for path in sumo_cosim_artifacts:
        payload = _load_json(path)
        if payload is None:
            ignored_sumo_cosim.append({"path": str(path), "reason": "unreadable_json"})
            continue
        attempt = _sumo_cosim_attempt(path, payload)
        if attempt is None:
            ignored_sumo_cosim.append({"path": str(path), "reason": "not_sumo_cosim_artifact"})
            continue
        sumo_cosim_attempts.append(attempt)

    for path in novadrive_artifacts:
        payload = _load_json(path)
        if payload is None:
            ignored_novadrive.append({"path": str(path), "reason": "unreadable_json"})
            continue
        attempt = _novadrive_attempt(path, payload)
        if attempt is None:
            ignored_novadrive.append({"path": str(path), "reason": "not_novadrive_artifact"})
            continue
        novadrive_attempts.append(attempt)

    for path in calibration_scene_artifacts:
        payload = _load_json(path)
        if payload is None:
            ignored_calibration_scene.append({"path": str(path), "reason": "unreadable_json"})
            continue
        attempt = _calibration_scene_attempt(path, payload)
        if attempt is None:
            ignored_calibration_scene.append({"path": str(path), "reason": "not_calibration_scene_artifact"})
            continue
        calibration_scene_attempts.append(attempt)

    for path in camera_fiducial_artifacts:
        payload = _load_json(path)
        if payload is None:
            ignored_camera_fiducial.append({"path": str(path), "reason": "unreadable_json"})
            continue
        attempt = _camera_fiducial_attempt(path, payload)
        if attempt is None:
            ignored_camera_fiducial.append({"path": str(path), "reason": "not_camera_fiducial_artifact"})
            continue
        camera_fiducial_attempts.append(attempt)

    if sensor_attempts:
        latest_by_profile: dict[str, dict[str, Any]] = {}
        superseded: list[dict[str, Any]] = []
        for attempt in sorted(sensor_attempts, key=lambda item: str(item.get("path") or "")):
            profile = str(attempt.get("profile") or "default")
            previous = latest_by_profile.get(profile)
            if previous is not None:
                superseded.append(
                    {
                        "path": previous["path"],
                        "reason": "superseded_by_newer_sensor_probe",
                        "profile": profile,
                    }
                )
            latest_by_profile[profile] = attempt
        sensor_attempts = list(latest_by_profile.values())
        ignored_sensor.extend(superseded)

    if metric_attempts:
        latest_by_profile: dict[str, dict[str, Any]] = {}
        superseded: list[dict[str, Any]] = []
        for attempt in sorted(metric_attempts, key=lambda item: str(item.get("path") or "")):
            profile = str(attempt.get("profile") or "default")
            previous = latest_by_profile.get(profile)
            if previous is not None:
                superseded.append(
                    {
                        "path": previous["path"],
                        "reason": "superseded_by_newer_metric_probe",
                        "profile": profile,
                    }
                )
            latest_by_profile[profile] = attempt
        metric_attempts = list(latest_by_profile.values())
        ignored_metric.extend(superseded)

    successful_dynamic = [item for item in dynamic_attempts if item["overall_passed"]]
    successful_sensor = [item for item in sensor_attempts if item["overall_passed"]]
    successful_metric = [item for item in metric_attempts if item["overall_passed"]]
    successful_sumo_cosim = [item for item in sumo_cosim_attempts if item["overall_passed"]]
    successful_novadrive = [item for item in novadrive_attempts if item["overall_passed"]]
    successful_calibration_scene = [item for item in calibration_scene_attempts if item["overall_passed"]]
    successful_camera_fiducial = [item for item in camera_fiducial_attempts if item["overall_passed"]]
    route_completion = (len(successful) / len(attempts)) if attempts else 0.0
    route_completion_source = "real_carla_samples"
    if dynamic_attempts:
        dynamic_completion = len(successful_dynamic) / len(dynamic_attempts)
        if attempts:
            route_completion = min(route_completion, dynamic_completion)
            route_completion_source = "real_carla_samples_and_runtime_dynamic_probe"
        else:
            route_completion = dynamic_completion
            route_completion_source = "runtime_dynamic_probe"

    collision_count = 0.0 if empty_scene else math.nan
    min_ttc_sec = EMPTY_SCENE_TTC_SEC if empty_scene else math.nan
    if dynamic_attempts:
        collision_count = sum(_as_float(item.get("collision_count")) for item in dynamic_attempts)
        ttc_values = [_as_float(item.get("min_ttc_sec"), math.nan) for item in dynamic_attempts]
        finite_ttc_values = [value for value in ttc_values if not math.isnan(value)]
        if finite_ttc_values:
            min_ttc_sec = min(finite_ttc_values)

    metrics: dict[str, float] = {"route_completion": route_completion}
    metric_sources = {
        "route_completion": route_completion_source,
    }
    if not math.isnan(collision_count):
        metrics["collision_count"] = collision_count
        metric_sources["collision_count"] = (
            "runtime_dynamic_probe" if dynamic_attempts else "inferred_empty_scene_no_dynamic_actors"
        )
    if not math.isnan(min_ttc_sec):
        metrics["min_ttc_sec"] = min_ttc_sec
        metric_sources["min_ttc_sec"] = (
            "runtime_dynamic_probe" if dynamic_attempts else "inferred_empty_scene_no_dynamic_actors"
        )
    if attempts:
        for metric_name in (
            "lateral_error_m",
            "route_goal_lateral_error_m",
            "longitudinal_error_m",
            "jerk_mps3",
        ):
            values = [_as_float(item.get(metric_name), math.nan) for item in attempts]
            finite_values = [value for value in values if not math.isnan(value)]
            if finite_values:
                metrics[metric_name] = max(finite_values)
                metric_sources[metric_name] = "real_carla_samples"
    if dynamic_attempts:
        metrics["dynamic_actor_response"] = len(successful_dynamic) / len(dynamic_attempts)
        metric_sources["dynamic_actor_response"] = "runtime_dynamic_probe"
        observed_counts = [
            _as_float(item.get("actor_count_observed"), math.nan)
            for item in dynamic_attempts
        ]
        finite_observed_counts = [value for value in observed_counts if not math.isnan(value)]
        if finite_observed_counts:
            metrics["actor_count_observed"] = max(finite_observed_counts)
            metric_sources["actor_count_observed"] = "runtime_dynamic_probe"
        spawned_counts = [
            _as_float(item.get("actor_count_spawned"), math.nan)
            for item in dynamic_attempts
        ]
        finite_spawned_counts = [value for value in spawned_counts if not math.isnan(value)]
        if finite_spawned_counts:
            metrics["actor_count_spawned"] = max(finite_spawned_counts)
            metric_sources["actor_count_spawned"] = "runtime_dynamic_probe"
        metrics["yield_response_count"] = float(
            sum(1 for item in dynamic_attempts if item.get("autoware_dynamic_actor_response_passed"))
        )
        metric_sources["yield_response_count"] = "runtime_dynamic_probe"
        nonempty_ratios = [
            _as_float(item.get("object_pipeline_nonempty_duration_ratio"), math.nan)
            for item in dynamic_attempts
        ]
        finite_nonempty_ratios = [value for value in nonempty_ratios if not math.isnan(value)]
        if finite_nonempty_ratios:
            metrics["object_pipeline_nonempty_duration_ratio"] = min(finite_nonempty_ratios)
            metric_sources["object_pipeline_nonempty_duration_ratio"] = "runtime_dynamic_probe"
    if sensor_attempts:
        required_topic_total = sum(int(item.get("required_topic_count") or 0) for item in sensor_attempts)
        passing_topic_total = sum(int(item.get("passing_topic_count") or 0) for item in sensor_attempts)
        sample_required_total = sum(int(item.get("sample_required_topic_count") or 0) for item in sensor_attempts)
        sample_received_total = sum(int(item.get("sample_received_count") or 0) for item in sensor_attempts)
        if required_topic_total:
            metrics["sensor_topic_coverage"] = passing_topic_total / required_topic_total
            metric_sources["sensor_topic_coverage"] = "runtime_sensor_probe"
        if sample_required_total:
            metrics["sensor_sample_coverage"] = sample_received_total / sample_required_total
            metric_sources["sensor_sample_coverage"] = "runtime_sensor_probe"
    for attempt in metric_attempts:
        for name, value in attempt["metrics"].items():
            metrics[name] = value
            metric_sources[name] = "runtime_metric_probe"
    if sumo_cosim_attempts:
        latest_sumo = sorted(sumo_cosim_attempts, key=lambda item: str(item.get("path") or ""))[-1]
        for name, value in latest_sumo["metrics"].items():
            metrics[name] = value
            metric_sources[name] = "runtime_sumo_cosim_probe"
    if novadrive_attempts:
        latest_novadrive = sorted(novadrive_attempts, key=lambda item: str(item.get("path") or ""))[-1]
        for name, value in latest_novadrive["metrics"].items():
            metrics[name] = value
            metric_sources[name] = "novadrive_runtime"
    if calibration_scene_attempts:
        latest_scene = sorted(calibration_scene_attempts, key=lambda item: str(item.get("path") or ""))[-1]
        scene_metric_map = {
            "calibration_scene_target_count": "target_count",
            "calibration_scene_spawned_count": "spawned_count",
            "calibration_scene_failed_count": "failed_count",
            "calibration_scene_skipped_count": "skipped_count",
            "calibration_scene_marker_overlay_count": "marker_overlay_count",
            "calibration_scene_panel_overlay_line_count": "panel_overlay_line_count",
            "calibration_scene_panel_count": "panel_count",
            "calibration_scene_marker_payload_count": "marker_payload_count",
        }
        for metric_name, attempt_key in scene_metric_map.items():
            metrics[metric_name] = _as_float(latest_scene.get(attempt_key))
            metric_sources[metric_name] = "runtime_calibration_scene_spawn"
    if camera_fiducial_attempts:
        latest_camera = sorted(camera_fiducial_attempts, key=lambda item: str(item.get("path") or ""))[-1]
        camera_metric_map = {
            "camera_fiducial_expected_board_count": "expected_board_count",
            "camera_fiducial_captured_image_count": "captured_image_count",
            "camera_fiducial_detection_count": "detection_count",
            "camera_fiducial_qr_count": "qr_count",
            "camera_fiducial_aruco_count": "aruco_count",
            "camera_fiducial_binary_candidate_count": "binary_fiducial_candidate_count",
        }
        for metric_name, attempt_key in camera_metric_map.items():
            metrics[metric_name] = _as_float(latest_camera.get(attempt_key))
            metric_sources[metric_name] = "runtime_camera_fiducial_probe"

    return {
        "generated_at": utc_now(),
        "runtime_dir": str(runtime_dir),
        "attempt_count": len(attempts),
        "successful_attempt_count": len(successful),
        "ignored_attempts": ignored,
        "attempts": attempts,
        "dynamic_probe_attempt_count": len(dynamic_attempts),
        "successful_dynamic_probe_count": len(successful_dynamic),
        "ignored_dynamic_probe_attempts": ignored_dynamic,
        "dynamic_probe_attempts": dynamic_attempts,
        "sensor_probe_attempt_count": len(sensor_attempts),
        "successful_sensor_probe_count": len(successful_sensor),
        "ignored_sensor_probe_attempts": ignored_sensor,
        "sensor_probe_attempts": sensor_attempts,
        "metric_probe_attempt_count": len(metric_attempts),
        "successful_metric_probe_count": len(successful_metric),
        "ignored_metric_probe_attempts": ignored_metric,
        "metric_probe_attempts": metric_attempts,
        "sumo_cosim_attempt_count": len(sumo_cosim_attempts),
        "successful_sumo_cosim_count": len(successful_sumo_cosim),
        "ignored_sumo_cosim_attempts": ignored_sumo_cosim,
        "sumo_cosim_attempts": sumo_cosim_attempts,
        "novadrive_attempt_count": len(novadrive_attempts),
        "successful_novadrive_count": len(successful_novadrive),
        "ignored_novadrive_attempts": ignored_novadrive,
        "novadrive_attempts": novadrive_attempts,
        "calibration_scene_attempt_count": len(calibration_scene_attempts),
        "successful_calibration_scene_count": len(successful_calibration_scene),
        "ignored_calibration_scene_attempts": ignored_calibration_scene,
        "calibration_scene_attempts": calibration_scene_attempts,
        "camera_fiducial_attempt_count": len(camera_fiducial_attempts),
        "successful_camera_fiducial_count": len(successful_camera_fiducial),
        "ignored_camera_fiducial_attempts": ignored_camera_fiducial,
        "camera_fiducial_attempts": camera_fiducial_attempts,
        "metrics": metrics,
        "metric_sources": metric_sources,
        "assumptions": [
            "collision_count and min_ttc_sec are inferred only for empty L0 smoke scenes with no configured vehicles or pedestrians"
        ]
        if empty_scene
        else [],
    }


def write_runtime_evidence_summary(run_dir: Path, summary: dict[str, Any]) -> Path:
    path = run_dir / "runtime_evidence_summary.json"
    dump_json(path, summary)
    return path
