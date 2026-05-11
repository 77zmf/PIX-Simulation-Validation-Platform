from __future__ import annotations

import importlib.util
import os
import sys
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = REPO_ROOT / "ops" / "runtime_probes" / "carla_dynamic_actor_probe.py"

spec = importlib.util.spec_from_file_location("carla_dynamic_actor_probe", PROBE_PATH)
carla_dynamic_actor_probe = importlib.util.module_from_spec(spec)
sys.modules["carla_dynamic_actor_probe"] = carla_dynamic_actor_probe
assert spec.loader is not None
spec.loader.exec_module(carla_dynamic_actor_probe)


class CarlaDynamicActorProbeTests(unittest.TestCase):
    def test_camera_video_close_does_not_drain_pending_frames_by_default(self) -> None:
        class FakeStdin:
            def __init__(self) -> None:
                self.closed = False
                self.write_calls = 0

            def write(self, _frame: bytes) -> None:
                self.write_calls += 1
                raise AssertionError("close should not drain pending frames by default")

            def close(self) -> None:
                self.closed = True

        class FakeProc:
            def __init__(self) -> None:
                self.stdin = FakeStdin()
                self.wait_calls = 0

            def wait(self, timeout: float | int | None = None) -> int:
                self.wait_calls += 1
                self.wait_timeout = timeout
                return 0

            def terminate(self) -> None:
                raise AssertionError("terminate should not be called when wait succeeds")

            def kill(self) -> None:
                raise AssertionError("kill should not be called when wait succeeds")

        recorder = carla_dynamic_actor_probe.CameraVideoRecorder(
            output_path=Path("/tmp/fake.mp4"),
            width=1280,
            height=720,
            fps=10,
        )
        fake_proc = FakeProc()
        recorder._proc = fake_proc
        recorder._queue.put_nowait(b"pending-frame")

        recorder.close()

        self.assertTrue(fake_proc.stdin.closed)
        self.assertEqual(fake_proc.stdin.write_calls, 0)
        self.assertEqual(fake_proc.wait_calls, 1)
        self.assertEqual(recorder.frames_written, 0)

    def test_camera_video_close_can_drain_when_explicitly_requested(self) -> None:
        class FakeStdin:
            def __init__(self) -> None:
                self.closed = False
                self.write_calls = 0

            def write(self, _frame: bytes) -> None:
                self.write_calls += 1

            def close(self) -> None:
                self.closed = True

        class FakeProc:
            def __init__(self) -> None:
                self.stdin = FakeStdin()

            def wait(self, timeout: float | int | None = None) -> int:
                return 0

            def terminate(self) -> None:
                raise AssertionError("terminate should not be called when wait succeeds")

            def kill(self) -> None:
                raise AssertionError("kill should not be called when wait succeeds")

        old_value = os.environ.get("PIX_CARLA_VIDEO_DRAIN_ON_CLOSE")
        recorder = carla_dynamic_actor_probe.CameraVideoRecorder(
            output_path=Path("/tmp/fake.mp4"),
            width=1280,
            height=720,
            fps=10,
        )
        fake_proc = FakeProc()
        recorder._proc = fake_proc
        recorder._queue.put_nowait(b"pending-frame")
        try:
            os.environ["PIX_CARLA_VIDEO_DRAIN_ON_CLOSE"] = "1"
            recorder.close()
        finally:
            if old_value is None:
                os.environ.pop("PIX_CARLA_VIDEO_DRAIN_ON_CLOSE", None)
            else:
                os.environ["PIX_CARLA_VIDEO_DRAIN_ON_CLOSE"] = old_value

        self.assertTrue(fake_proc.stdin.closed)
        self.assertEqual(fake_proc.stdin.write_calls, 1)
        self.assertEqual(recorder.frames_written, 1)

    def test_overview_spectator_centers_ego_and_targets(self) -> None:
        params = carla_dynamic_actor_probe.spectator_transform_params(
            "overview",
            {"x": 230.0, "y": 2.0, "z": 0.1, "yaw": 0.0},
            [
                {"x": 286.0, "y": 2.0},
                {"x": 260.0, "y": 6.0},
            ],
        )

        self.assertIsNotNone(params)
        assert params is not None
        self.assertAlmostEqual(params["x"], (230.0 + 286.0 + 260.0) / 3.0)
        self.assertAlmostEqual(params["y"], (2.0 + 2.0 + 6.0) / 3.0)
        self.assertEqual(params["pitch"], -90.0)
        self.assertGreaterEqual(params["z"], 38.0)

    def test_ego_chase_spectator_tracks_behind_ego(self) -> None:
        params = carla_dynamic_actor_probe.spectator_transform_params(
            "ego_chase",
            {"x": 230.0, "y": 2.0, "z": 0.1, "yaw": 0.0},
            [],
        )

        self.assertIsNotNone(params)
        assert params is not None
        self.assertAlmostEqual(params["x"], 216.0)
        self.assertAlmostEqual(params["y"], 2.0)
        self.assertAlmostEqual(params["z"], 7.1)
        self.assertEqual(params["pitch"], -22.0)

    def test_l3_occluded_pedestrian_probe_uses_walker_and_occluder(self) -> None:
        config = carla_dynamic_actor_probe.PROBES["l3_occluded_pedestrian"]

        self.assertEqual(config.target_type, "walker.pedestrian.0001")
        actor_types = [actor.target_type for actor in config.actors]
        self.assertIn("vehicle.audi.tt", actor_types)
        self.assertIn("walker.pedestrian.0001", actor_types)
        self.assertEqual(config.safe_ttc_sec, 1.8)
        self.assertEqual(config.min_actor_observed_count, 1)
        occluders = [actor for actor in config.actors if actor.name == "occluding_vehicle"]
        self.assertEqual(len(occluders), 1)
        self.assertFalse(occluders[0].perception_visible)

    def test_l3_dummy_injection_selects_visible_pedestrian(self) -> None:
        config = carla_dynamic_actor_probe.PROBES["l3_occluded_pedestrian"]
        injection_actor = carla_dynamic_actor_probe.dummy_injection_actor(config.actors)
        profile = carla_dynamic_actor_probe.dummy_object_profile("walker.pedestrian.0001")

        self.assertIsNotNone(injection_actor)
        assert injection_actor is not None
        self.assertEqual(injection_actor.name, "crossing_pedestrian")
        self.assertEqual(profile["classification"], "PEDESTRIAN")
        self.assertEqual(profile["shape"], "CYLINDER")
        self.assertEqual(profile["dimensions"], {"x": 0.6, "y": 0.6, "z": 2.0})

    def test_l3_expanded_variants_keep_one_visible_pedestrian(self) -> None:
        for kind in (
            "l3_occluded_pedestrian_close_yield",
            "l3_occluded_pedestrian_double_occluder",
        ):
            with self.subTest(kind=kind):
                config = carla_dynamic_actor_probe.PROBES[kind]
                visible = [actor for actor in config.actors if actor.perception_visible]
                occluders = [actor for actor in config.actors if not actor.perception_visible]

                self.assertEqual(len(visible), 1)
                self.assertTrue(visible[0].target_type.startswith("walker.pedestrian."))
                self.assertGreaterEqual(len(occluders), 1)
                self.assertEqual(config.min_actor_observed_count, 1)
                self.assertEqual(config.safe_ttc_sec, 1.8)

    def test_l2_crosswalk_vru_yield_uses_single_visible_pedestrian(self) -> None:
        config = carla_dynamic_actor_probe.PROBES["l2_crosswalk_vru_yield"]
        visible = [actor for actor in config.actors if actor.perception_visible]

        self.assertEqual(config.target_type, "walker.pedestrian.0001")
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0].name, "crosswalk_pedestrian")
        self.assertEqual(config.min_actor_observed_count, 1)
        self.assertEqual(config.safe_ttc_sec, 1.8)

    def test_l2_overtake_reference_uses_multi_lane_vehicle_layout(self) -> None:
        config = carla_dynamic_actor_probe.PROBES["l2_overtake_reference"]
        names = {actor.name for actor in config.actors}
        lane_offsets = {actor.start["y"] for actor in config.actors}

        self.assertEqual(config.classification, "l2_overtake_reference_multi_lane_with_perception_pipeline")
        self.assertGreaterEqual(len(config.actors), 4)
        self.assertEqual(config.min_actor_observed_count, 3)
        self.assertIn("slow_lead_vehicle", names)
        self.assertIn("left_lane_overtake_target", names)
        self.assertIn("right_lane_background_vehicle", names)
        self.assertTrue(any(abs(y - carla_dynamic_actor_probe.START_CARLA["y"]) < 0.7 for y in lane_offsets))
        self.assertTrue(any(y < carla_dynamic_actor_probe.START_CARLA["y"] - 3.0 for y in lane_offsets))
        self.assertTrue(any(y > carla_dynamic_actor_probe.START_CARLA["y"] + 3.0 for y in lane_offsets))

    def test_run_cmd_with_retries_retries_timeout_then_success(self) -> None:
        calls: list[dict[str, object]] = []
        seen: list[int] = []
        original_run_cmd = carla_dynamic_actor_probe.run_cmd
        original_sleep = time.sleep

        def fake_run_cmd(
            step: str,
            args: list[str],
            env: dict[str, str],
            recorded_calls: list[dict[str, object]],
            timeout_sec: int = 20,
        ) -> dict[str, object]:
            returncode = 124 if not seen else 0
            seen.append(returncode)
            item = {
                "step": step,
                "returncode": returncode,
                "output": "",
                "args": args,
            }
            recorded_calls.append(item)
            return item

        try:
            carla_dynamic_actor_probe.run_cmd = fake_run_cmd
            time.sleep = lambda _seconds: None
            result = carla_dynamic_actor_probe.run_cmd_with_retries(
                "engage_true",
                ["timeout", "15", "ros2", "service", "call"],
                {},
                calls,
                timeout_sec=18,
                retries=3,
                retry_delay_sec=0.0,
            )
        finally:
            carla_dynamic_actor_probe.run_cmd = original_run_cmd
            time.sleep = original_sleep

        self.assertEqual(result["returncode"], 0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["attempt"], 1)
        self.assertEqual(calls[1]["attempt"], 2)
        self.assertEqual(calls[1]["max_attempts"], 3)

    def test_run_service_cmd_with_retries_retries_success_false_then_supersedes_failure(self) -> None:
        calls: list[dict[str, object]] = []
        seen: list[str] = []
        original_run_cmd = carla_dynamic_actor_probe.run_cmd
        original_sleep = time.sleep

        def fake_run_cmd(
            step: str,
            args: list[str],
            env: dict[str, str],
            recorded_calls: list[dict[str, object]],
            timeout_sec: int = 20,
        ) -> dict[str, object]:
            output = (
                "ChangeOperationMode_Response(status=ResponseStatus("
                "success=False, code=1, message='The target mode is not available.'))"
                if not seen
                else "ChangeOperationMode_Response(status=ResponseStatus(success=True, code=0, message=''))"
            )
            seen.append(output)
            item = {
                "step": step,
                "returncode": 0,
                "output": output,
                "args": args,
            }
            recorded_calls.append(item)
            return item

        try:
            carla_dynamic_actor_probe.run_cmd = fake_run_cmd
            time.sleep = lambda _seconds: None
            result = carla_dynamic_actor_probe.run_service_cmd_with_retries(
                "change_to_autonomous",
                ["timeout", "25", "ros2", "service", "call"],
                {},
                calls,
                timeout_sec=28,
                retries=3,
                retry_delay_sec=0.0,
            )
        finally:
            carla_dynamic_actor_probe.run_cmd = original_run_cmd
            time.sleep = original_sleep

        self.assertEqual(result["returncode"], 0)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0]["superseded_by_success"])
        self.assertEqual(calls[0]["service_failure_reason"], "service_status_false")
        self.assertEqual(calls[1]["attempt"], 2)
        self.assertEqual(carla_dynamic_actor_probe.service_call_failures(calls), [])

    def test_setup_route_waits_for_localization_and_trajectory_before_autonomous(self) -> None:
        service_calls: list[dict[str, object]] = []
        setup_checks: list[dict[str, object]] = []
        recorded_steps: list[str] = []
        original_run_cmd = carla_dynamic_actor_probe.run_cmd
        original_run_cmd_with_retries = carla_dynamic_actor_probe.run_cmd_with_retries
        original_run_service_cmd_with_retries = carla_dynamic_actor_probe.run_service_cmd_with_retries
        original_sleep = time.sleep

        def fake_run_cmd(
            step: str,
            args: list[str],
            env: dict[str, str],
            calls: list[dict[str, object]],
            timeout_sec: int = 20,
        ) -> dict[str, object]:
            recorded_steps.append(step)
            item = {"step": step, "returncode": 0, "output": "", "args": args}
            calls.append(item)
            return item

        def fake_run_cmd_with_retries(
            step: str,
            args: list[str],
            env: dict[str, str],
            calls: list[dict[str, object]],
            *,
            timeout_sec: int = 20,
            retries: int = 1,
            retry_delay_sec: float = 2.0,
        ) -> dict[str, object]:
            recorded_steps.append(step)
            item = {"step": step, "returncode": 0, "output": "", "args": args, "attempt": 1, "max_attempts": retries}
            calls.append(item)
            return item

        try:
            carla_dynamic_actor_probe.run_cmd = fake_run_cmd
            carla_dynamic_actor_probe.run_cmd_with_retries = fake_run_cmd_with_retries
            carla_dynamic_actor_probe.run_service_cmd_with_retries = fake_run_cmd_with_retries
            time.sleep = lambda _seconds: None
            carla_dynamic_actor_probe.setup_route({}, service_calls, setup_checks)
        finally:
            carla_dynamic_actor_probe.run_cmd = original_run_cmd
            carla_dynamic_actor_probe.run_cmd_with_retries = original_run_cmd_with_retries
            carla_dynamic_actor_probe.run_service_cmd_with_retries = original_run_service_cmd_with_retries
            time.sleep = original_sleep

        self.assertLess(recorded_steps.index("initialize_localization"), recorded_steps.index("wait_localization_state"))
        self.assertLess(recorded_steps.index("set_route_points"), recorded_steps.index("wait_planning_trajectory"))
        self.assertLess(recorded_steps.index("wait_planning_trajectory"), recorded_steps.index("change_to_autonomous"))
        self.assertTrue(setup_checks)

    def test_setup_route_supersedes_enable_control_failure_when_autonomous_succeeds(self) -> None:
        service_calls: list[dict[str, object]] = []
        setup_checks: list[dict[str, object]] = []
        original_run_cmd = carla_dynamic_actor_probe.run_cmd
        original_run_cmd_with_retries = carla_dynamic_actor_probe.run_cmd_with_retries
        original_sleep = time.sleep

        def fake_run_cmd(
            step: str,
            args: list[str],
            env: dict[str, str],
            calls: list[dict[str, object]],
            timeout_sec: int = 20,
        ) -> dict[str, object]:
            if step == "enable_autoware_control":
                output = (
                    "ChangeOperationMode_Response(status=ResponseStatus("
                    "success=False, code=1, message='The mode change is blocked by the system.'))"
                )
            elif step == "change_to_autonomous":
                output = "ChangeOperationMode_Response(status=ResponseStatus(success=True, code=0, message=''))"
            else:
                output = ""
            item = {"step": step, "returncode": 0, "output": output, "args": args}
            calls.append(item)
            return item

        def fake_run_cmd_with_retries(
            step: str,
            args: list[str],
            env: dict[str, str],
            calls: list[dict[str, object]],
            *,
            timeout_sec: int = 20,
            retries: int = 1,
            retry_delay_sec: float = 2.0,
        ) -> dict[str, object]:
            item = {"step": step, "returncode": 0, "output": "", "args": args, "attempt": 1, "max_attempts": retries}
            calls.append(item)
            return item

        try:
            carla_dynamic_actor_probe.run_cmd = fake_run_cmd
            carla_dynamic_actor_probe.run_cmd_with_retries = fake_run_cmd_with_retries
            time.sleep = lambda _seconds: None
            carla_dynamic_actor_probe.setup_route({}, service_calls, setup_checks)
        finally:
            carla_dynamic_actor_probe.run_cmd = original_run_cmd
            carla_dynamic_actor_probe.run_cmd_with_retries = original_run_cmd_with_retries
            time.sleep = original_sleep

        enable_calls = [item for item in service_calls if item["step"] == "enable_autoware_control"]
        self.assertTrue(enable_calls)
        self.assertTrue(all(item["superseded_by_success"] for item in enable_calls))
        self.assertEqual(carla_dynamic_actor_probe.service_call_failures(service_calls), [])

    def test_publish_dummy_message_repeatedly_replays_add_for_late_subscribers(self) -> None:
        class FakePub:
            def __init__(self) -> None:
                self.messages: list[object] = []

            def publish(self, msg: object) -> None:
                self.messages.append(msg)

        class FakeRclpy:
            def __init__(self) -> None:
                self.spin_count = 0

            def spin_once(self, node: object, timeout_sec: float) -> None:
                self.spin_count += 1

        fake_pub = FakePub()
        fake_rclpy = FakeRclpy()
        original_sleep = time.sleep

        try:
            time.sleep = lambda _seconds: None
            carla_dynamic_actor_probe.publish_dummy_message_repeatedly(
                fake_rclpy,
                object(),
                fake_pub,
                {"action": "ADD"},
                repeat=4,
                spin_timeout_sec=0.01,
                sleep_sec=0.0,
            )
        finally:
            time.sleep = original_sleep

        self.assertEqual(len(fake_pub.messages), 4)
        self.assertEqual(fake_rclpy.spin_count, 4)


if __name__ == "__main__":
    unittest.main()
