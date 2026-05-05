from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_probe():
    path = REPO_ROOT / "ops" / "runtime_probes" / "carla_waypoint_lap_probe.py"
    spec = importlib.util.spec_from_file_location("carla_waypoint_lap_probe", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["carla_waypoint_lap_probe"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CarlaWaypointLapProbeTests(unittest.TestCase):
    def test_forward_lookahead_chooses_ahead_target_over_s_only_target(self) -> None:
        probe = _load_probe()
        route = [
            probe.RoutePoint(0.0, 0.0, 0.0, 0.0, 0.0),
            probe.RoutePoint(10.0, 10.0, 0.0, 0.0, 10.0),
            probe.RoutePoint(20.0, 20.0, 0.0, 0.0, 20.0),
            probe.RoutePoint(40.0, -5.0, 0.0, 0.0, 40.0),
        ]
        sample = {"x": 20.0, "y": 0.0, "yaw": 0.0}

        target_index, debug = probe.target_index_for_forward_lookahead(
            route,
            sample,
            0,
            lookahead_m=20.0,
            search_window=4,
            min_forward_m=4.0,
        )

        self.assertEqual(target_index, 3)
        self.assertEqual(debug["target_selection"], "forward_lookahead")
        self.assertGreater(debug["target_local_x_m"], 0.0)

    def test_pure_pursuit_control_limits_steer_and_uses_debug_curvature(self) -> None:
        probe = _load_probe()
        carla = SimpleNamespace(
            VehicleControl=lambda **kwargs: SimpleNamespace(**kwargs),
        )
        sample = {"x": 0.0, "y": 0.0, "yaw": 0.0, "speed_mps": 0.5}
        target = probe.RoutePoint(10.0, 8.0, 0.0, 0.0, 10.0)

        control, debug = probe.control_towards_target(
            carla,
            sample,
            target,
            target_speed_mps=2.0,
            turn_speed_mps=1.0,
            steer_gain=1.0,
            steer_sign=1.0,
            throttle_gain=0.1,
            brake_gain=0.4,
            max_throttle=0.2,
            max_brake=0.8,
            brake_heading_error_rad=3.2,
            overspeed_brake_margin_mps=0.5,
            pure_pursuit_wheelbase_m=6.0,
            pure_pursuit_max_steer_angle_rad=0.75,
        )

        self.assertGreater(control.steer, 0.0)
        self.assertLessEqual(abs(control.steer), 1.0)
        self.assertGreater(debug["curvature"], 0.0)
        self.assertIn("steering_angle_rad", debug)

    def test_nearest_route_index_guards_closed_route_terminal_jump(self) -> None:
        probe = _load_probe()
        route = [
            probe.RoutePoint(0.0, 0.0, 0.0, 0.0, 0.0),
            probe.RoutePoint(100.0, 0.0, 0.0, 0.0, 100.0),
            probe.RoutePoint(200.0, 0.0, 0.0, 0.0, 200.0),
            probe.RoutePoint(300.0, 0.0, 0.0, 0.0, 300.0),
            probe.RoutePoint(400.0, 0.0, 0.0, 0.0, 400.0),
            probe.RoutePoint(500.0, 0.0, 0.0, 0.0, 500.0),
            probe.RoutePoint(600.0, 0.0, 0.0, 0.0, 600.0),
            probe.RoutePoint(700.0, 0.0, 0.0, 0.0, 700.0),
            probe.RoutePoint(800.0, 0.0, 0.0, 0.0, 800.0),
            probe.RoutePoint(0.0, 0.0, 0.0, 0.0, 1000.0),
        ]

        index, _ = probe.nearest_route_index(
            route,
            (0.1, 0.0),
            current_index=5,
            search_window=10,
            terminal_guard_ratio=0.85,
        )

        self.assertNotEqual(index, 9)

    def test_route_heading_control_steers_back_toward_route_yaw(self) -> None:
        probe = _load_probe()
        carla = SimpleNamespace(
            VehicleControl=lambda **kwargs: SimpleNamespace(**kwargs),
        )
        sample = {"x": 1212.8, "y": 174.5, "yaw": -60.8, "speed_mps": 0.3}
        route_point = probe.RoutePoint(1216.4, 164.4, 0.0, -75.0, 23.2)

        control, debug = probe.control_along_route_heading(
            carla,
            sample,
            route_point,
            target_speed_mps=1.5,
            turn_speed_mps=0.7,
            steer_gain=1.0,
            steer_sign=1.0,
            throttle_gain=0.06,
            brake_gain=0.75,
            max_throttle=0.08,
            max_brake=0.9,
            brake_heading_error_rad=1.4,
            overspeed_brake_margin_mps=0.5,
            route_heading_cross_track_gain=0.08,
            route_heading_softening_mps=2.0,
            route_heading_max_steer_angle_rad=0.75,
        )

        self.assertGreater(control.steer, 0.0)
        self.assertLess(control.throttle, 0.08)
        self.assertLess(debug["heading_error_rad"], 0.0)
        self.assertLess(debug["cross_track_error_m"], 0.0)

    def test_interpolate_route_point_moves_by_s_distance(self) -> None:
        probe = _load_probe()
        route = [
            probe.RoutePoint(0.0, 0.0, 1.0, 0.0, 0.0),
            probe.RoutePoint(10.0, 0.0, 3.0, 0.0, 10.0),
        ]

        point = probe.interpolate_route_point(route, 4.0)

        self.assertAlmostEqual(point.x, 4.0)
        self.assertAlmostEqual(point.y, 0.0)
        self.assertAlmostEqual(point.z, 1.8)
        self.assertAlmostEqual(point.s_m, 4.0)

    def test_route_index_for_s_returns_next_route_point(self) -> None:
        probe = _load_probe()
        route = [
            probe.RoutePoint(0.0, 0.0, 0.0, 0.0, 0.0),
            probe.RoutePoint(10.0, 0.0, 0.0, 0.0, 10.0),
            probe.RoutePoint(20.0, 0.0, 0.0, 0.0, 20.0),
        ]

        self.assertEqual(probe.route_index_for_s(route, 10.0), 1)
        self.assertEqual(probe.route_index_for_s(route, 11.0), 2)
        self.assertEqual(probe.route_index_for_s(route, 99.0), 2)

    def test_apply_route_yaw_offset_keeps_positions_and_offsets_yaw(self) -> None:
        probe = _load_probe()
        route = [
            probe.RoutePoint(1.0, 2.0, 3.0, -72.0, 0.0),
        ]

        adjusted = probe.apply_route_yaw_offset(route, -90.0)

        self.assertEqual(adjusted[0].x, 1.0)
        self.assertEqual(adjusted[0].y, 2.0)
        self.assertEqual(adjusted[0].z, 3.0)
        self.assertEqual(adjusted[0].yaw_deg, -162.0)

    def test_parse_triplet_accepts_camera_transform_values(self) -> None:
        probe = _load_probe()

        self.assertEqual(probe.parse_triplet("-12, 0, 5", name="camera"), (-12.0, 0.0, 5.0))


if __name__ == "__main__":
    unittest.main()
