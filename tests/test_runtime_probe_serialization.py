from __future__ import annotations

import importlib.util
import os
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_probe(module_name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


carla_sensor_topic_probe = _load_probe(
    "carla_sensor_topic_probe",
    "ops/runtime_probes/carla_sensor_topic_probe.py",
)
carla_dynamic_actor_probe = _load_probe(
    "carla_dynamic_actor_probe",
    "ops/runtime_probes/carla_dynamic_actor_probe.py",
)
carla_closed_loop_route_probe = _load_probe(
    "carla_closed_loop_route_probe",
    "ops/runtime_probes/carla_closed_loop_route_probe.py",
)
perception_readiness_probe = _load_probe(
    "perception_readiness_probe",
    "ops/runtime_probes/perception_readiness_probe.py",
)
bevfusion_public_road_metrics_probe = _load_probe(
    "bevfusion_public_road_metrics_probe",
    "ops/runtime_probes/bevfusion_public_road_metrics_probe.py",
)
lidar_calibration_metric_probe = _load_probe(
    "lidar_calibration_metric_probe",
    "ops/runtime_probes/lidar_calibration_metric_probe.py",
)
camera_fiducial_board_opencv_probe = _load_probe(
    "camera_fiducial_board_opencv_probe",
    "ops/runtime_probes/camera_fiducial_board_opencv_probe.py",
)
lidar_fiducial_board_hit_probe = _load_probe(
    "lidar_fiducial_board_hit_probe",
    "ops/runtime_probes/lidar_fiducial_board_hit_probe.py",
)
lidar_camera_projection_probe = _load_probe(
    "lidar_camera_projection_probe",
    "ops/runtime_probes/lidar_camera_projection_probe.py",
)


class _FakeActor:
    def __init__(
        self,
        type_id: str,
        role_name: str,
        *,
        actor_id: int = 1,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
    ) -> None:
        self.id = actor_id
        self.type_id = type_id
        self.attributes = {"role_name": role_name}
        self.destroyed = False
        self._location = SimpleNamespace(x=x, y=y, z=z)

    def get_transform(self) -> SimpleNamespace:
        return SimpleNamespace(location=self._location)

    def destroy(self) -> bool:
        self.destroyed = True
        return True


class _FakeActorList(list):
    def filter(self, pattern: str) -> "_FakeActorList":
        if pattern == "vehicle.*":
            return _FakeActorList(actor for actor in self if actor.type_id.startswith("vehicle."))
        return _FakeActorList()


class _FakeWorld:
    def __init__(self) -> None:
        self.calls = 0

    def get_actors(self) -> _FakeActorList:
        self.calls += 1
        if self.calls == 1:
            return _FakeActorList()
        return _FakeActorList([_FakeActor("vehicle.pixmoving.robobus", "ego_vehicle")])

    def wait_for_tick(self) -> None:
        return None


class RuntimeProbeSerializationTests(unittest.TestCase):
    def test_sensor_probe_has_bridge_only_profile(self) -> None:
        profile = carla_sensor_topic_probe.PROFILES["robobus117th_bridge_only"]
        topics = {spec.topic for spec in profile}

        self.assertIn("/sensing/camera/CAM_FRONT/image_raw", topics)
        self.assertIn("/sensing/lidar/top/pointcloud_before_sync", topics)
        self.assertIn("/sensing/imu/tamagawa/imu_raw", topics)
        self.assertIn("/vehicle/status/velocity_status", topics)
        self.assertNotIn("/tf", topics)
        self.assertNotIn("/vehicle/status/steering_status", topics)
        self.assertNotIn("/perception/object_recognition/objects", topics)
        self.assertNotIn("/control/command/control_cmd", topics)

    def test_sensor_probe_has_l0_closed_loop_profile(self) -> None:
        profile = carla_sensor_topic_probe.PROFILES["robobus117th_l0_closed_loop"]
        topics = {spec.topic for spec in profile}

        self.assertIn("/sensing/camera/CAM_FRONT/image_raw", topics)
        self.assertIn("/sensing/lidar/rear_top/pointcloud_before_sync", topics)
        self.assertIn("/vehicle/status/velocity_status", topics)
        self.assertIn("/control/command/control_cmd", topics)
        self.assertIn("/tf", topics)
        self.assertNotIn("/simulation/dummy_perception_publisher/object_info", topics)
        self.assertNotIn("/perception/object_recognition/objects", topics)

    def test_sensor_probe_has_presence_smoke_profile(self) -> None:
        profile = carla_sensor_topic_probe.PROFILES["robobus117th_presence_smoke"]
        topics = {spec.topic for spec in profile}

        self.assertIn("/sensing/camera/CAM_FRONT/image_raw", topics)
        self.assertIn("/sensing/lidar/top/pointcloud_before_sync", topics)
        self.assertIn("/control/command/control_cmd", topics)
        self.assertIn("/perception/object_recognition/objects", topics)
        self.assertTrue(all(not spec.sample_required for spec in profile))

    def test_sensor_probe_has_route_smoke_core_profile(self) -> None:
        profile = carla_sensor_topic_probe.PROFILES["robobus117th_route_smoke_core"]
        topics = {spec.topic for spec in profile}

        self.assertIn("/sensing/lidar/top/pointcloud_before_sync", topics)
        self.assertIn("/sensing/imu/tamagawa/imu_raw", topics)
        self.assertIn("/sensing/gnss/pose_with_covariance", topics)
        self.assertIn("/localization/kinematic_state", topics)
        self.assertIn("/control/command/control_cmd", topics)
        self.assertNotIn("/sensing/camera/CAM_FRONT/image_raw", topics)
        self.assertNotIn("/sensing/lidar/rear_top/pointcloud_before_sync", topics)
        self.assertFalse(next(spec for spec in profile if spec.topic == "/vehicle/status/control_mode").sample_required)
        self.assertFalse(next(spec for spec in profile if spec.topic == "/vehicle/status/steering_status").sample_required)

    def test_sensor_topic_tail_normalizes_timeout_bytes(self) -> None:
        self.assertEqual(
            carla_sensor_topic_probe._tail(b"prefix-\xe4\xb8\xad\xe6\x96\x87", limit=6),
            "fix-中文",
        )

    def test_sensor_probe_retries_until_samples_pass(self) -> None:
        original_profiles = carla_sensor_topic_probe.PROFILES
        original_topic_types = carla_sensor_topic_probe._topic_types
        original_sample_topic = carla_sensor_topic_probe._sample_topic
        calls: list[int] = []

        def fake_sample_topic(_spec, _timeout_sec):
            calls.append(1)
            return {
                "sample_received": len(calls) > 1,
                "sample_command": "ros2 topic echo --once /sample",
                "sample_returncode": 0 if len(calls) > 1 else "timeout",
                "sample_stdout_tail": "header: {}\n" if len(calls) > 1 else "",
                "sample_stderr_tail": "",
            }

        try:
            carla_sensor_topic_probe.PROFILES = {
                **original_profiles,
                "retry_test": (carla_sensor_topic_probe.TopicSpec("/sample", "sample"),),
            }
            carla_sensor_topic_probe._topic_types = lambda _timeout_sec: {
                "/sample": "std_msgs/msg/Header"
            }
            carla_sensor_topic_probe._sample_topic = fake_sample_topic

            payload = carla_sensor_topic_probe.run_probe(
                SimpleNamespace(
                    profile="retry_test",
                    discovery_timeout_sec=1.0,
                    topic_timeout_sec=1.0,
                    max_workers=1,
                    attempts=2,
                    retry_sleep_sec=0.0,
                )
            )
        finally:
            carla_sensor_topic_probe.PROFILES = original_profiles
            carla_sensor_topic_probe._topic_types = original_topic_types
            carla_sensor_topic_probe._sample_topic = original_sample_topic

        self.assertTrue(payload["overall_passed"])
        self.assertEqual(payload["attempt"], 2)
        self.assertEqual(len(payload["attempts"]), 2)

    def test_closed_loop_route_parser_defaults_to_simctl_runtime_env(self) -> None:
        original_argv = sys.argv[:]
        original_env = {
            "ROS_DOMAIN_ID": os.environ.get("ROS_DOMAIN_ID"),
            "RMW_IMPLEMENTATION": os.environ.get("RMW_IMPLEMENTATION"),
            "SIMCTL_CARLA_RPC_PORT": os.environ.get("SIMCTL_CARLA_RPC_PORT"),
            "SIMCTL_CARLA_ROS_Y_SIGN": os.environ.get("SIMCTL_CARLA_ROS_Y_SIGN"),
        }
        try:
            os.environ["ROS_DOMAIN_ID"] = "22"
            os.environ["RMW_IMPLEMENTATION"] = "rmw_cyclonedds_cpp"
            os.environ["SIMCTL_CARLA_RPC_PORT"] = "2010"
            os.environ["SIMCTL_CARLA_ROS_Y_SIGN"] = "1"
            sys.argv = ["carla_closed_loop_route_probe.py", "--run-dir", "/tmp/run"]

            args = carla_closed_loop_route_probe.parse_args()
        finally:
            sys.argv = original_argv
            for name, value in original_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

        self.assertEqual(args.ros_domain_id, 22)
        self.assertEqual(args.rmw_implementation, "rmw_cyclonedds_cpp")
        self.assertEqual(args.carla_port, 2010)
        self.assertEqual(args.carla_y_sign, 1.0)

    def test_closed_loop_route_carla_pose_respects_y_sign(self) -> None:
        map_pose = {"x": 1.0, "y": 2.0, "z": 3.0, "yaw_deg": 45.0}

        flipped = carla_closed_loop_route_probe.carla_pose_from_map_pose(map_pose, 0.5, -1.0)
        same_axis = carla_closed_loop_route_probe.carla_pose_from_map_pose(map_pose, 0.5, 1.0)

        self.assertEqual(flipped["y"], -2.0)
        self.assertEqual(same_axis["y"], 2.0)
        self.assertEqual(flipped["yaw"], 45.0)
        self.assertEqual(same_axis["yaw"], 45.0)
        self.assertEqual(carla_closed_loop_route_probe.ego_sample_to_map_xy({"x": 1.0, "y": 2.0}, 1.0), (1.0, 2.0))

    def test_closed_loop_route_segment_distance_detects_goal_crossing(self) -> None:
        previous_sample = {"x": -134.55, "y": 639.82}
        current_sample = {"x": -220.39, "y": 641.23}
        goal = {"x": -164.116, "y": 639.35}

        sample_distance = min(
            carla_closed_loop_route_probe.distance_to_goal_m(previous_sample, goal),
            carla_closed_loop_route_probe.distance_to_goal_m(current_sample, goal),
        )
        segment_distance = carla_closed_loop_route_probe.distance_to_goal_segment_m(
            previous_sample,
            current_sample,
            goal,
        )

        self.assertGreater(sample_distance, 25.0)
        self.assertLess(segment_distance, 2.0)

    def test_closed_loop_route_service_success_detects_adapi_success_false(self) -> None:
        self.assertFalse(
            carla_closed_loop_route_probe.service_call_successful(
                [
                    {
                        "returncode": 0,
                        "output": (
                            "ChangeOperationMode_Response(status="
                            "ResponseStatus(success=False, code=1, "
                            "message='The target mode is not available.'))"
                        ),
                    }
                ]
            )
        )
        self.assertTrue(
            carla_closed_loop_route_probe.service_call_successful(
                [
                    {
                        "returncode": 0,
                        "output": "ChangeOperationMode_Response(status=ResponseStatus(success=True, code=0, message=''))",
                    },
                    {
                        "returncode": 0,
                        "output": "Engage_Response(status=ResponseStatus(code=1, message=''))",
                    },
                ]
            )
        )

    def test_closed_loop_route_required_service_success_ignores_mode_transition_failure(self) -> None:
        calls = [
            {
                "step": "initialize_localization",
                "returncode": 0,
                "output": "InitializeLocalization_Response(status=ResponseStatus(success=True, code=0, message=''))",
            },
            {
                "step": "set_route_points",
                "returncode": 0,
                "output": "SetRoutePoints_Response(status=ResponseStatus(success=True, code=0, message=''))",
            },
            {
                "step": "change_to_autonomous",
                "returncode": 0,
                "output": (
                    "ChangeOperationMode_Response(status="
                    "ResponseStatus(success=False, code=1, "
                    "message='The target mode is not available.'))"
                ),
            },
        ]

        self.assertFalse(carla_closed_loop_route_probe.service_call_successful(calls))
        self.assertTrue(
            carla_closed_loop_route_probe.required_service_call_successful(
                calls,
                {"initialize_localization", "set_route_points"},
            )
        )

    def test_route_yaml_can_disable_goal_modification(self) -> None:
        goal = {"x": 314.0, "y": -1.98, "z": 0.0, "yaw_deg": 0.0}

        self.assertIn(
            "allow_goal_modification: true",
            carla_dynamic_actor_probe.route_yaml(goal),
        )
        self.assertIn(
            "allow_goal_modification: false",
            carla_dynamic_actor_probe.route_yaml(goal, allow_goal_modification=False),
        )

    def test_route_yaml_serializes_route_waypoints(self) -> None:
        goal = {"x": 30.0, "y": 4.0, "z": 0.0, "yaw_deg": 90.0}
        waypoints = [
            {"x": 10.0, "y": 2.0, "z": 0.0, "yaw_deg": 0.0},
            {"x": 20.0, "y": 3.0, "z": 0.0, "yaw": 45.0},
        ]

        payload = carla_dynamic_actor_probe.route_yaml(goal, waypoints=waypoints)

        self.assertIn("goal: {position: {x: 30.000000000, y: 4.000000000", payload)
        self.assertIn("waypoints: [{position: {x: 10.000000000, y: 2.000000000", payload)
        self.assertIn("{position: {x: 20.000000000, y: 3.000000000", payload)
        self.assertIn("z: 0.382683432365, w: 0.923879532511", payload)

    def test_closed_loop_route_extracts_route_points_as_waypoints_and_goal(self) -> None:
        fallback_goal = {"x": 99.0, "y": 0.0, "z": 0.0, "yaw_deg": 0.0}
        payload = {
            "route": {
                "points": [
                    {"pose": {"x": 1.0, "y": 2.0, "z": 0.0, "yaw_deg": 10.0}},
                    {"x": 3.0, "y": 4.0, "z": 0.0, "yaw_deg": 20.0},
                    {"pose": {"x": 5.0, "y": 6.0, "z": 0.0, "yaw_deg": 30.0}},
                ]
            }
        }

        waypoints, goal = carla_closed_loop_route_probe.route_from_payload(payload, fallback_goal)

        self.assertEqual([waypoint["x"] for waypoint in waypoints], [1.0, 3.0])
        self.assertEqual(goal["x"], 5.0)
        self.assertEqual(goal["yaw_deg"], 30.0)

    def test_closed_loop_route_extracts_intermediate_waypoints_with_root_goal(self) -> None:
        fallback_goal = {"x": 99.0, "y": 8.0, "z": 0.0, "yaw_deg": 90.0}
        payload = {
            "route": {
                "waypoints": [
                    {"x": 10.0, "y": 1.0, "z": 0.0, "yaw_deg": 0.0},
                    {"pose": {"x": 20.0, "y": 2.0, "z": 0.0, "yaw_deg": 45.0}},
                ]
            }
        }

        waypoints, goal = carla_closed_loop_route_probe.route_from_payload(payload, fallback_goal)

        self.assertEqual([waypoint["x"] for waypoint in waypoints], [10.0, 20.0])
        self.assertEqual(goal["x"], 99.0)
        self.assertEqual(goal["yaw_deg"], 90.0)

    def test_closed_loop_route_speed_target_summary(self) -> None:
        reached = carla_closed_loop_route_probe.speed_target_summary(10.8, 11.111111, 0.5)
        missed = carla_closed_loop_route_probe.speed_target_summary(8.0, 11.111111, 0.5)
        disabled = carla_closed_loop_route_probe.speed_target_summary(8.0, None, 0.5)

        self.assertTrue(reached["target_speed_reached"])
        self.assertAlmostEqual(reached["target_speed_kph"], 40.0, places=4)
        self.assertFalse(missed["target_speed_reached"])
        self.assertGreater(missed["target_speed_deficit_mps"], 2.0)
        self.assertIsNone(disabled["target_speed_reached"])

    def test_closed_loop_route_robust_jerk_ignores_low_speed_goal_creep(self) -> None:
        samples = [
            {"t": 0.0, "phase": "route_tracking", "ego": {"speed_mps": 0.0}},
            {"t": 1.0, "phase": "route_tracking", "ego": {"speed_mps": 1.2}},
            {"t": 2.0, "phase": "route_tracking", "ego": {"speed_mps": 2.4}},
            {"t": 3.0, "phase": "route_tracking", "ego": {"speed_mps": 3.6}},
            {"t": 4.0, "phase": "route_tracking", "ego": {"speed_mps": 4.8}},
            {"t": 5.0, "phase": "route_tracking", "ego": {"speed_mps": 0.2}},
            {"t": 6.0, "phase": "route_tracking", "ego": {"speed_mps": 0.8}},
            {"t": 7.0, "phase": "route_tracking", "ego": {"speed_mps": 0.1}},
            {"t": 8.0, "phase": "route_tracking", "ego": {"speed_mps": 0.9}},
            {"t": 9.0, "phase": "route_tracking", "ego": {"speed_mps": 0.0}},
        ]

        all_samples_jerk = carla_closed_loop_route_probe.robust_abs_jerk_mps3(samples)
        moving_jerk = carla_closed_loop_route_probe.robust_abs_jerk_mps3(
            samples,
            min_speed_mps=1.0,
            phase="route_tracking",
        )

        self.assertGreater(all_samples_jerk, 2.5)
        self.assertLess(moving_jerk, 2.5)

    def test_closed_loop_route_ros_summary_preserves_diagnostics(self) -> None:
        diagnostics = {
            "status_count": 3,
            "problem_count": 1,
            "max_level": 2,
            "problems": [
                {
                    "name": "operation_mode",
                    "level": 2,
                    "message": "The target mode is not available.",
                    "values": [{"key": "state", "value": "waiting"}],
                }
            ],
        }

        summary = carla_closed_loop_route_probe.summarize_ros_control_telemetry(
            [],
            {
                "enabled": True,
                "error": None,
                "counts": {"diagnostics": 4},
                "latest": {"diagnostics": diagnostics},
            },
        )

        self.assertEqual(summary["topic_counts"]["diagnostics"], 4)
        self.assertEqual(summary["diagnostics"]["problem_count"], 1)
        self.assertEqual(summary["diagnostics"]["problems"][0]["name"], "operation_mode")

    def test_closed_loop_route_diagnostic_level_accepts_bytes(self) -> None:
        self.assertEqual(carla_closed_loop_route_probe.diagnostic_level_to_int(b"\x00"), 0)
        self.assertEqual(carla_closed_loop_route_probe.diagnostic_level_to_int(b"\x02"), 2)
        self.assertEqual(carla_closed_loop_route_probe.diagnostic_level_to_int("1"), 1)
        self.assertEqual(carla_closed_loop_route_probe.diagnostic_level_to_int(None), 0)

    def test_closed_loop_route_service_retry_supersedes_transient_status_false(self) -> None:
        calls: list[dict[str, object]] = []
        attempt_count = 0
        original_run_cmd = carla_closed_loop_route_probe.run_cmd
        original_sleep = time.sleep

        def fake_run_cmd(
            step: str,
            args: list[str],
            env: dict[str, str],
            recorded_calls: list[dict[str, object]],
            timeout_sec: int = 20,
        ) -> dict[str, object]:
            nonlocal attempt_count
            attempt_count += 1
            output = (
                "ChangeOperationMode_Response(status=ResponseStatus("
                "success=False, code=1, message='The target mode is not available.'))"
                if attempt_count == 1
                else "ChangeOperationMode_Response(status=ResponseStatus(success=True, code=0, message=''))"
            )
            item = {
                "step": step,
                "returncode": 0,
                "output": output,
                "args": args,
            }
            recorded_calls.append(item)
            return item

        try:
            carla_closed_loop_route_probe.run_cmd = fake_run_cmd
            time.sleep = lambda _seconds: None
            result = carla_closed_loop_route_probe.run_service_cmd_with_retries(
                "change_to_autonomous",
                ["timeout", "25", "ros2", "service", "call"],
                {},
                calls,
                timeout_sec=28,
                retries=3,
                retry_delay_sec=0.0,
            )
        finally:
            carla_closed_loop_route_probe.run_cmd = original_run_cmd
            time.sleep = original_sleep

        self.assertEqual(result["attempt"], 2)
        self.assertTrue(calls[0]["superseded_by_success"])
        self.assertTrue(carla_closed_loop_route_probe.service_call_successful(calls))

    def test_closed_loop_route_waits_for_operation_mode_available(self) -> None:
        setup_checks: list[dict[str, object]] = []
        samples = iter(
            [
                {"returncode": 0, "sample_received": True, "output_tail": "false\n---"},
                {"returncode": 0, "sample_received": True, "output_tail": "true\n---"},
            ]
        )
        original_call_topic_echo = carla_closed_loop_route_probe.call_topic_echo
        original_sleep = time.sleep

        def fake_call_topic_echo(topic: str, env: dict[str, str], field: str | None = None) -> dict[str, object]:
            self.assertEqual(topic, "/api/operation_mode/state")
            self.assertEqual(field, "is_autonomous_mode_available")
            return next(samples)

        try:
            carla_closed_loop_route_probe.call_topic_echo = fake_call_topic_echo
            time.sleep = lambda _seconds: None
            ready = carla_closed_loop_route_probe.wait_for_operation_mode_autonomous_available(
                {},
                setup_checks,
                timeout_sec=10.0,
                poll_interval_sec=0.0,
            )
        finally:
            carla_closed_loop_route_probe.call_topic_echo = original_call_topic_echo
            time.sleep = original_sleep

        self.assertTrue(ready)
        self.assertTrue(setup_checks[0]["passed"])
        self.assertEqual(setup_checks[0]["attempt_count"], 2)

    def test_closed_loop_route_records_operation_mode_blocker_snapshot(self) -> None:
        setup_checks: list[dict[str, object]] = []
        original_call_topic_echo = carla_closed_loop_route_probe.call_topic_echo
        original_collect_snapshot = carla_closed_loop_route_probe.collect_operation_mode_blocker_snapshot

        def fake_call_topic_echo(topic: str, env: dict[str, str], field: str | None = None) -> dict[str, object]:
            self.assertEqual(topic, "/api/operation_mode/state")
            self.assertEqual(field, "is_autonomous_mode_available")
            return {"returncode": 0, "sample_received": True, "output_tail": "false\n---"}

        def fake_collect_snapshot(env: dict[str, str]) -> dict[str, object]:
            return {
                "created_wall_time": 1.0,
                "topics": {
                    "fail_safe_mrm_state": {
                        "topic": "/system/fail_safe/mrm_state",
                        "sample_received": True,
                        "output_tail": "state: emergency",
                    }
                },
            }

        try:
            carla_closed_loop_route_probe.call_topic_echo = fake_call_topic_echo
            carla_closed_loop_route_probe.collect_operation_mode_blocker_snapshot = fake_collect_snapshot
            ready = carla_closed_loop_route_probe.wait_for_operation_mode_autonomous_available(
                {},
                setup_checks,
                timeout_sec=0.0,
                poll_interval_sec=0.0,
            )
        finally:
            carla_closed_loop_route_probe.call_topic_echo = original_call_topic_echo
            carla_closed_loop_route_probe.collect_operation_mode_blocker_snapshot = original_collect_snapshot

        self.assertFalse(ready)
        self.assertFalse(setup_checks[0]["passed"])
        self.assertEqual(setup_checks[0]["attempt_count"], 1)
        snapshot = setup_checks[0]["blocker_snapshot"]
        self.assertEqual(snapshot["topics"]["fail_safe_mrm_state"]["output_tail"], "state: emergency")

    def test_closed_loop_route_operation_mode_blocker_snapshot_includes_component_states(self) -> None:
        topic_by_key = {
            key: topic for key, topic, _field in carla_closed_loop_route_probe.OPERATION_MODE_BLOCKER_TOPIC_SPECS
        }

        self.assertEqual(
            topic_by_key["component_autonomous_planning"],
            "/system/component_state_monitor/component/autonomous/planning",
        )
        self.assertEqual(
            topic_by_key["component_autonomous_control"],
            "/system/component_state_monitor/component/autonomous/control",
        )
        self.assertEqual(
            topic_by_key["component_launch_vehicle"],
            "/system/component_state_monitor/component/launch/vehicle",
        )

    def test_closed_loop_route_waits_for_localization_and_trajectory_before_autonomous(self) -> None:
        recorded_steps: list[str] = []
        calls: list[dict[str, object]] = []
        setup_checks: list[dict[str, object]] = []
        original_run_cmd = carla_closed_loop_route_probe.run_cmd
        original_run_service_cmd_with_retries = carla_closed_loop_route_probe.run_service_cmd_with_retries
        original_wait_for_topic_sample = carla_closed_loop_route_probe.wait_for_topic_sample
        original_wait_for_operation_mode = (
            carla_closed_loop_route_probe.wait_for_operation_mode_autonomous_available
        )
        original_sleep = time.sleep

        def fake_run_cmd(
            step: str,
            args: list[str],
            env: dict[str, str],
            recorded_calls: list[dict[str, object]],
            timeout_sec: int = 20,
        ) -> dict[str, object]:
            item = {"step": step, "returncode": 0, "output": ""}
            recorded_steps.append(step)
            recorded_calls.append(item)
            return item

        def fake_run_service_cmd_with_retries(
            step: str,
            args: list[str],
            env: dict[str, str],
            recorded_calls: list[dict[str, object]],
            **_kwargs: object,
        ) -> dict[str, object]:
            item = {"step": step, "returncode": 0, "output": ""}
            recorded_steps.append(step)
            recorded_calls.append(item)
            return item

        def fake_wait_for_topic_sample(
            step: str,
            topic: str,
            env: dict[str, str],
            checks: list[dict[str, object]],
            **_kwargs: object,
        ) -> bool:
            recorded_steps.append(step)
            checks.append({"step": step, "topic": topic, "passed": True})
            return True

        def fake_wait_for_operation_mode(
            env: dict[str, str],
            checks: list[dict[str, object]],
            **_kwargs: object,
        ) -> bool:
            recorded_steps.append("wait_operation_mode_autonomous_available")
            checks.append({"step": "wait_operation_mode_autonomous_available", "passed": True})
            return True

        try:
            carla_closed_loop_route_probe.run_cmd = fake_run_cmd
            carla_closed_loop_route_probe.run_service_cmd_with_retries = fake_run_service_cmd_with_retries
            carla_closed_loop_route_probe.wait_for_topic_sample = fake_wait_for_topic_sample
            carla_closed_loop_route_probe.wait_for_operation_mode_autonomous_available = fake_wait_for_operation_mode
            time.sleep = lambda _seconds: None
            carla_closed_loop_route_probe.setup_route(
                {},
                {"x": 229.7, "y": -2.0, "z": 0.0, "yaw": 0.0},
                {"x": 314.2, "y": -2.0, "z": 0.0, "yaw": 0.0},
                calls,
                setup_checks,
            )
        finally:
            carla_closed_loop_route_probe.run_cmd = original_run_cmd
            carla_closed_loop_route_probe.run_service_cmd_with_retries = original_run_service_cmd_with_retries
            carla_closed_loop_route_probe.wait_for_topic_sample = original_wait_for_topic_sample
            carla_closed_loop_route_probe.wait_for_operation_mode_autonomous_available = (
                original_wait_for_operation_mode
            )
            time.sleep = original_sleep

        self.assertLess(recorded_steps.index("initialize_localization"), recorded_steps.index("wait_localization_state"))
        self.assertLess(recorded_steps.index("wait_localization_state"), recorded_steps.index("set_route_points"))
        self.assertLess(recorded_steps.index("set_route_points"), recorded_steps.index("wait_planning_trajectory"))
        self.assertLess(recorded_steps.index("wait_planning_trajectory"), recorded_steps.index("enable_autoware_control"))
        self.assertLess(
            recorded_steps.index("wait_operation_mode_autonomous_available"),
            recorded_steps.index("change_to_autonomous"),
        )

    def test_closed_loop_route_clears_nearby_non_ego_start_traffic(self) -> None:
        ego = _FakeActor("vehicle.pixmoving.robobus", "ego_vehicle", actor_id=10, x=250.0, y=2.0)
        near_sumo = _FakeActor("vehicle.audi.tt", "sumo_driver", actor_id=11, x=215.0, y=2.0)
        far_sumo = _FakeActor("vehicle.toyota.prius", "sumo_driver", actor_id=12, x=180.0, y=2.0)
        world = SimpleNamespace(get_actors=lambda: _FakeActorList([ego, near_sumo, far_sumo]))

        report = carla_closed_loop_route_probe.clear_nearby_start_traffic(world, ego, radius_m=45.0)

        self.assertEqual(report["checked_count"], 2)
        self.assertEqual(report["nearby_count"], 1)
        self.assertEqual(report["destroyed_count"], 1)
        self.assertTrue(near_sumo.destroyed)
        self.assertFalse(far_sumo.destroyed)
        self.assertEqual(report["nearest_actor"]["id"], 11)

    def test_dynamic_actor_probe_detects_adapi_success_false(self) -> None:
        calls = [
            {
                "step": "change_to_autonomous",
                "returncode": 0,
                "output": (
                    "ChangeOperationMode_Response(status="
                    "ResponseStatus(success=False, code=1, "
                    "message='The target mode is not available.'))"
                ),
            }
        ]

        failures = carla_dynamic_actor_probe.service_call_failures(calls)

        self.assertFalse(carla_dynamic_actor_probe.service_calls_successful(calls))
        self.assertEqual(failures[0]["step"], "change_to_autonomous")
        self.assertEqual(failures[0]["reason"], "service_status_false")
        self.assertEqual(failures[0]["message"], "The target mode is not available.")

    def test_perception_tail_normalizes_timeout_bytes(self) -> None:
        self.assertEqual(perception_readiness_probe._tail(None), "")
        self.assertEqual(perception_readiness_probe._tail(b"abc", limit=2), "bc")

    def test_perception_readiness_requires_bevfusion_specific_objects(self) -> None:
        specs = perception_readiness_probe.PROFILES["bevfusion_public_road"]
        by_topic = {spec.topic: spec for spec in specs}

        bevfusion_objects = by_topic["/perception/object_recognition/detection/bevfusion/objects"]
        self.assertEqual(bevfusion_objects.group, "bevfusion")
        self.assertTrue(bevfusion_objects.required)
        self.assertTrue(bevfusion_objects.sample_required)
        self.assertTrue(by_topic["/perception/object_recognition/objects"].required)

    def test_bevfusion_metrics_probe_fail_closes_missing_quality_source(self) -> None:
        import argparse
        import tempfile

        with tempfile.TemporaryDirectory() as tempdir:
            args = argparse.Namespace(
                run_dir=tempdir,
                profile="bevfusion_public_road",
                source_metrics=None,
                output=bevfusion_public_road_metrics_probe.DEFAULT_OUTPUT,
                fail_closed_if_missing=True,
            )

            payload, rc = bevfusion_public_road_metrics_probe.build_payload(args)
            output = bevfusion_public_road_metrics_probe.write_payload(payload)

            self.assertEqual(rc, 0)
            self.assertTrue(output.exists())
            self.assertTrue(payload["complete"])
            self.assertFalse(payload["quality_ready"])
            self.assertTrue(payload["fail_closed"])
            self.assertEqual(payload["metrics"]["detection_recall"], 0.0)
            self.assertEqual(payload["metrics"]["latency_ms"], 999.0)
            self.assertIn("bevfusion_quality_metrics_not_ready", payload["blockers"])

    def test_lidar_calibration_probe_extracts_numeric_metrics(self) -> None:
        import argparse
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_lidar_calibration"
            result_dir = run_dir / "runtime_verification" / "calibration" / "lidar_sensor_kit_extrinsic"
            result_dir.mkdir(parents=True)
            result_file = result_dir / "calibration_result.json"
            result_file.write_text(
                json.dumps(
                    {
                        "calibration_type": "lidar_sensor_kit_extrinsic",
                        "status": "converged",
                        "estimated_transforms": [
                            {"child": "lidar_ft_base_link"},
                            {"child": "lidar_rt_base_link"},
                            {"child": "lidar_rear_base_link"},
                            {"child": "lidar_fl_base_link"},
                            {"child": "lidar_fr_base_link"},
                        ],
                        "metrics": {
                            "lidar_extrinsic_translation_error_m": 0.018,
                            "lidar_extrinsic_rotation_error_deg": 0.22,
                            "lidar_pairwise_registration_rmse_m": 0.032,
                        },
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                run_dir=str(run_dir),
                profile="lidar_sensor_kit_extrinsic",
                calibration_result=None,
                require_transform_count=5,
            )

            payload = lidar_calibration_metric_probe.run_probe(args)

            self.assertTrue(payload["overall_passed"])
            self.assertEqual(payload["blocked_reason"], None)
            self.assertEqual(payload["metrics"]["calibration_converged"], 1.0)
            self.assertEqual(payload["metrics"]["calibrated_lidar_count"], 5.0)
            self.assertEqual(payload["metrics"]["lidar_extrinsic_translation_error_m"], 0.018)

    def test_lidar_calibration_probe_requires_result_file(self) -> None:
        import argparse
        import tempfile

        with tempfile.TemporaryDirectory() as tempdir:
            args = argparse.Namespace(
                run_dir=str(Path(tempdir) / "run_lidar_calibration"),
                profile="lidar_sensor_kit_extrinsic",
                calibration_result=None,
                require_transform_count=5,
            )

            payload = lidar_calibration_metric_probe.run_probe(args)

            self.assertFalse(payload["overall_passed"])
            self.assertEqual(payload["blocked_reason"], "missing_calibration_result")
            self.assertEqual(payload["metrics"], {})

    def test_camera_fiducial_probe_prefers_colleague_apriltag_dictionary(self) -> None:
        self.assertEqual(
            camera_fiducial_board_opencv_probe.DEFAULT_ARUCO_DICTIONARIES[0],
            "DICT_APRILTAG_16h5",
        )

    def test_camera_fiducial_probe_retries_empty_carla_actor_list(self) -> None:
        world = _FakeWorld()

        ego = camera_fiducial_board_opencv_probe.find_ego_actor(world, "ego_vehicle")

        self.assertEqual(ego.type_id, "vehicle.pixmoving.robobus")
        self.assertEqual(world.calls, 2)

    def test_lidar_board_hit_probe_retries_empty_carla_actor_list(self) -> None:
        world = _FakeWorld()

        ego = lidar_fiducial_board_hit_probe.find_ego_actor(world, "ego_vehicle")

        self.assertEqual(ego.type_id, "vehicle.pixmoving.robobus")
        self.assertEqual(world.calls, 2)

    def test_lidar_fiducial_board_hit_probe_reports_board_hits(self) -> None:
        import argparse
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run_lidar_board_hits"
            scene_dir = run_dir / "runtime_verification" / "calibration_scene"
            scene_dir.mkdir(parents=True)
            (scene_dir / "calibration_workshop_bv1qk411d7ta_scene_spawn.json").write_text(
                json.dumps(
                    {
                        "targets": [
                            {
                                "target_id": "front_qr_board",
                                "kind": "fiducial_board",
                                "local_pose": {
                                    "x": 10.0,
                                    "y": 0.0,
                                    "z": 1.5,
                                    "yaw_deg": 180.0,
                                },
                                "size_m": [2.4, 1.6],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                run_dir=str(run_dir),
                scene_spawn_artifact=None,
                sensor_calibration=str(REPO_ROOT / "assets" / "calibration" / "lidar_sensor_kit_truth.yaml"),
                board_sample_grid=3,
                min_range_m=0.5,
                max_range_m=100.0,
                min_incidence_cos=0.08,
                min_total_hit_count=1,
                min_boards_hit=1,
                min_lidars_hit=1,
                capture_from_carla=False,
            )

            payload = lidar_fiducial_board_hit_probe.run_probe(args)

            self.assertTrue(payload["overall_passed"])
            self.assertEqual(payload["capture_mode"], "geometry_board_roi")
            self.assertGreater(payload["metrics"]["lidar_board_hit_count"], 0.0)
            self.assertEqual(payload["metrics"]["lidar_board_hit_board_count"], 1.0)

    def test_lidar_camera_projection_infers_ego_and_projects_front_point(self) -> None:
        scene_payload = {
            "targets": [
                {
                    "target_id": "front_qr_board",
                    "local_pose": {
                        "x": 8.0,
                        "y": 0.0,
                        "z": 1.5,
                        "yaw_deg": 180.0,
                    },
                }
            ],
            "spawned": [
                {
                    "target_id": "front_qr_board",
                    "world_transform": {
                        "x": 18.0,
                        "y": 3.0,
                        "z": 1.5,
                        "yaw": -180.0,
                    },
                }
            ],
        }

        ego_pose = lidar_camera_projection_probe.infer_ego_pose_from_scene(scene_payload)
        camera_pose = {
            "x": 2.0,
            "y": 0.0,
            "z": 2.0,
            "yaw_deg": 0.0,
            "pitch_deg": 0.0,
        }
        projection = lidar_camera_projection_probe.project_world_point(
            (10.0, 0.0, 2.0),
            camera_pose,
            1600,
            1000,
            95.0,
        )

        self.assertAlmostEqual(ego_pose["x"], 10.0)
        self.assertAlmostEqual(ego_pose["y"], 3.0)
        self.assertAlmostEqual(ego_pose["z"], 0.0)
        self.assertAlmostEqual(ego_pose["yaw_deg"], 0.0)
        self.assertIsNotNone(projection)
        assert projection is not None
        self.assertAlmostEqual(projection[0], 800.0)
        self.assertAlmostEqual(projection[1], 500.0)
        self.assertAlmostEqual(projection[2], 8.0)


if __name__ == "__main__":
    unittest.main()
