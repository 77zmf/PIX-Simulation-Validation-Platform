from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


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
    def __init__(self, type_id: str, role_name: str) -> None:
        self.type_id = type_id
        self.attributes = {"role_name": role_name}


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

    def test_sensor_topic_tail_normalizes_timeout_bytes(self) -> None:
        self.assertEqual(
            carla_sensor_topic_probe._tail(b"prefix-\xe4\xb8\xad\xe6\x96\x87", limit=6),
            "fix-中文",
        )

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

    def test_perception_tail_normalizes_timeout_bytes(self) -> None:
        self.assertEqual(perception_readiness_probe._tail(None), "")
        self.assertEqual(perception_readiness_probe._tail(b"abc", limit=2), "bc")

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
