#!/usr/bin/env python3
"""Spawn calibration-workshop proxy targets into a running CARLA world.

The scene asset uses a vehicle-local ROS-style frame: x forward, y left, z up.
CARLA uses x forward, y right, z up, so y and yaw are mirrored when spawning
relative to the ego vehicle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment error path
    raise SystemExit("Missing PyYAML. Install python3-yaml or pip install pyyaml.") from exc


PLANE_BLUEPRINT_CANDIDATES = (
    "static.prop.advertisement",
    "static.prop.busstop",
    "static.prop.warningconstruction",
    "static.prop.streetbarrier",
    "static.prop.container",
    "static.prop.vendingmachine",
)
BOARD_BLUEPRINT_CANDIDATES = (
    "static.prop.advertisement",
    "static.prop.busstop",
    "static.prop.warningconstruction",
    "static.prop.streetbarrier",
    "static.prop.container",
    "static.prop.vendingmachine",
)
POLE_BLUEPRINT_CANDIDATES = (
    "static.prop.trafficcone01",
    "static.prop.trafficcone02",
    "static.prop.barrel",
    "static.prop.streetbarrier",
)
FIDUCIAL_MARKER_TYPES = {
    "qr",
    "qr_code",
    "qr_fiducial_grid",
    "aruco",
    "apriltag",
    "opencv_aruco_marker_board",
}


def _as_float_pair(value: Any, default: tuple[float, float]) -> list[float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return [float(value[0]), float(value[1])]
    return [default[0], default[1]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_scene(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def resolve_repo_asset_path(scene_file: Path, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    candidates = [
        Path.cwd() / path,
        scene_file.parent / path,
    ]
    if len(scene_file.parents) >= 3:
        candidates.append(scene_file.parents[2] / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return (Path.cwd() / path).resolve()


def load_board_asset(scene_file: Path, board_asset: str | None) -> dict[str, Any]:
    if not board_asset:
        return {}
    path = resolve_repo_asset_path(scene_file, board_asset)
    if not path.exists():
        raise FileNotFoundError(f"Board asset not found: {board_asset} resolved to {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    payload["asset_path"] = str(path)
    return payload


def target_specs(scene: dict[str, Any]) -> list[dict[str, Any]]:
    targets = scene.get("static_calibration_targets")
    if not isinstance(targets, dict):
        return []
    default_board_asset = targets.get("board_asset")
    specs: list[dict[str, Any]] = []
    for target in targets.get("fiducial_board_targets") or []:
        if isinstance(target, dict):
            marker = dict(target.get("marker") or {})
            marker.setdefault("type", "qr_fiducial_grid")
            marker.setdefault("proxy_rendering", "carla_debug_overlay_on_static_board")
            specs.append(
                {
                    "kind": "fiducial_board",
                    "target_id": str(target.get("target_id") or "fiducial_board"),
                    "role": str(target.get("role") or "fiducial_calibration_board"),
                    "pose": dict(target.get("pose") or {}),
                    "size_m": target.get("size_m") or [1.2, 1.2],
                    "material": str(target.get("material") or "printed_qr_fiducial_board"),
                    "board_asset": target.get("board_asset") or default_board_asset,
                    "panel": dict(target.get("panel") or {}),
                    "marker": marker,
                    "blueprint_candidates": list(BOARD_BLUEPRINT_CANDIDATES),
                }
            )
    for target in targets.get("lidar_plane_targets") or []:
        if isinstance(target, dict):
            specs.append(
                {
                    "kind": "plane",
                    "target_id": str(target.get("target_id") or "plane_target"),
                    "role": str(target.get("role") or "lidar_plane_target"),
                    "pose": dict(target.get("pose") or {}),
                    "size_m": target.get("size_m"),
                    "material": target.get("material"),
                    "marker": dict(target.get("marker") or {}),
                    "blueprint_candidates": list(PLANE_BLUEPRINT_CANDIDATES),
                }
            )
    for target in targets.get("lidar_corner_targets") or []:
        if isinstance(target, dict):
            specs.append(
                {
                    "kind": "pole",
                    "target_id": str(target.get("target_id") or "pole_target"),
                    "role": str(target.get("role") or "lidar_corner_target"),
                    "pose": dict(target.get("pose") or {}),
                    "height_m": target.get("height_m"),
                    "diameter_m": target.get("diameter_m"),
                    "material": target.get("material"),
                    "marker": dict(target.get("marker") or {}),
                    "blueprint_candidates": list(POLE_BLUEPRINT_CANDIDATES),
                }
            )
    return specs


def role_name(scene_id: str, target_id: str) -> str:
    return f"simctl_calibration_scene::{scene_id}::{target_id}"


def local_pose_for_plan(pose: dict[str, Any]) -> dict[str, float]:
    return {
        "x": float(pose.get("x") or 0.0),
        "y": float(pose.get("y") or 0.0),
        "z": float(pose.get("z") or 0.0),
        "roll_deg": float(pose.get("roll_deg") or 0.0),
        "pitch_deg": float(pose.get("pitch_deg") or 0.0),
        "yaw_deg": float(pose.get("yaw_deg") or 0.0),
    }


def normalized_size_m(value: Any, default: tuple[float, float] = (1.2, 1.2)) -> list[float]:
    return _as_float_pair(value, default)


def normalized_marker(marker: dict[str, Any], target_id: str) -> dict[str, Any]:
    if not marker:
        return {}
    payload = dict(marker)
    marker_type = str(payload.get("type") or "qr_fiducial_grid")
    payload["type"] = marker_type
    payload.setdefault("marker_id", target_id)
    module_count = int(payload.get("module_count") or 29)
    module_count = max(21, min(49, module_count))
    if module_count % 2 == 0:
        module_count += 1
    payload["module_count"] = module_count
    payload["border_modules"] = max(0, int(payload.get("border_modules") or 0))
    return payload


def qr_module_count(version: int, quiet_zone_modules: int) -> int:
    return 17 + (4 * version) + (2 * quiet_zone_modules)


def marker_set_from_board_asset(board_asset: dict[str, Any], target_id: str) -> list[dict[str, Any]]:
    layout = board_asset.get("layout") if isinstance(board_asset.get("layout"), dict) else {}
    contract = (
        board_asset.get("opencv_contract")
        if isinstance(board_asset.get("opencv_contract"), dict)
        else {}
    )
    marker_type = str(contract.get("marker_type") or contract.get("detector") or "").lower()
    if marker_type in {"qr", "qr_code", "qrcodedetector"}:
        payload_template = str(contract.get("payload_template") or "PIXCAL:{target_id}")
        payload = payload_template.format(target_id=target_id)
        version = int(contract.get("qr_version") or 2)
        quiet_zone_modules = int(contract.get("quiet_zone_modules") or 4)
        markers = []
        for marker in layout.get("markers") or [{"local_yz_m": [0.0, 0.0]}]:
            if not isinstance(marker, dict):
                continue
            local_yz = marker.get("local_yz_m") or [0.0, 0.0]
            markers.append(
                {
                    "type": "qr_code",
                    "marker_id": str(marker.get("marker_id") or target_id),
                    "qr_payload": str(marker.get("payload") or payload),
                    "qr_version": version,
                    "error_correction": str(contract.get("error_correction") or "L"),
                    "module_count": qr_module_count(version, quiet_zone_modules),
                    "border_modules": quiet_zone_modules,
                    "local_yz_m": [float(local_yz[0]), float(local_yz[1])],
                    "size_m": float(marker.get("size_m") or contract.get("marker_size_m") or 1.2),
                }
            )
        return markers

    dictionary = str(contract.get("dictionary") or "DICT_APRILTAG_16h5")
    markers = []
    for marker in layout.get("markers") or []:
        if not isinstance(marker, dict):
            continue
        marker_id = int(marker.get("marker_id"))
        local_yz = marker.get("local_yz_m") or [0.0, 0.0]
        markers.append(
            {
                "marker_id": marker_id,
                "opencv_aruco_dictionary": dictionary,
                "opencv_aruco_id": marker_id,
                "module_count": 24,
                "border_modules": 1,
                "local_yz_m": [float(local_yz[0]), float(local_yz[1])],
                "size_m": float(marker.get("size_m") or contract.get("marker_length_m") or 0.51),
            }
        )
    return markers


def is_fiducial_marker(marker: dict[str, Any]) -> bool:
    return str(marker.get("type") or "").lower() in FIDUCIAL_MARKER_TYPES


def build_spawn_plan(scene: dict[str, Any], scene_file: Path) -> dict[str, Any]:
    scene_id = str(scene.get("scene_asset_id") or scene_file.stem)
    specs = target_specs(scene)
    targets = []
    for spec in specs:
        target_id = spec["target_id"]
        marker = normalized_marker(spec.get("marker") or {}, target_id)
        board_asset_ref = spec.get("board_asset")
        board_asset = load_board_asset(scene_file, str(board_asset_ref)) if board_asset_ref else {}
        marker_set = marker_set_from_board_asset(board_asset, target_id)
        panel = {}
        if isinstance(board_asset.get("physical_panel"), dict):
            panel.update(board_asset["physical_panel"])
        if isinstance(spec.get("panel"), dict):
            panel.update(spec["panel"])
        if panel:
            panel.setdefault("panel_size_m", spec.get("size_m") or panel.get("panel_size_m") or [1.2, 1.2])
            panel["panel_size_m"] = normalized_size_m(panel.get("panel_size_m"))
            if "printable_area_m" in panel:
                panel["printable_area_m"] = _as_float_pair(panel["printable_area_m"], (1.0, 1.0))
            for numeric_key in (
                "panel_thickness_m",
                "frame_width_m",
                "flatness_tolerance_m",
                "placement_tolerance_m",
                "placement_tolerance_yaw_deg",
                "lower_edge_height_m",
                "qr_print_size_m",
            ):
                if numeric_key in panel:
                    panel[numeric_key] = float(panel[numeric_key])
        if board_asset:
            contract = board_asset.get("opencv_contract") or {}
            marker_type = str(contract.get("marker_type") or "").lower()
            marker["board_asset_id"] = str(board_asset.get("board_asset_id") or Path(str(board_asset_ref)).stem)
            marker["board_asset_path"] = str(board_asset.get("asset_path") or board_asset_ref)
            if marker_type in {"qr", "qr_code"}:
                marker.setdefault("type", "qr_code")
                marker.setdefault("family", str(contract.get("detector") or "QRCodeDetector"))
                marker["marker_count_per_board"] = int(contract.get("marker_num") or len(marker_set) or 1)
                if marker_set:
                    marker["qr_payload"] = str(marker_set[0].get("qr_payload") or target_id)
            else:
                marker.setdefault("type", "opencv_aruco_marker_board")
                marker.setdefault("family", str(contract.get("dictionary") or "DICT_APRILTAG_16h5"))
                marker["marker_order"] = [int(value) for value in contract.get("marker_order", [])]
        target = {
            "target_id": target_id,
            "kind": spec["kind"],
            "role": spec["role"],
            "role_name": role_name(scene_id, target_id),
            "local_pose": local_pose_for_plan(spec["pose"]),
            "blueprint_candidates": spec["blueprint_candidates"],
        }
        if spec.get("size_m") is not None:
            target["size_m"] = normalized_size_m(spec["size_m"])
        if spec.get("material"):
            target["material"] = str(spec["material"])
        if marker:
            target["marker"] = marker
        if marker_set:
            target["marker_set"] = marker_set
        if panel:
            target["panel"] = panel
        targets.append(target)
    return {
        "generated_at": utc_now(),
        "scene_asset_id": scene_id,
        "scene_file": str(scene_file),
        "target_count": len(specs),
        "coordinate_contract": {
            "source_frame": "calibration_workshop_local",
            "spawn_mode": "relative_to_ego_vehicle",
            "source_axes": "ROS style x-forward y-left z-up",
            "carla_axes": "CARLA x-forward y-right z-up",
        },
        "targets": targets,
    }


def load_carla_module() -> Any:
    try:
        import carla  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - host-only path
        raise SystemExit(
            "Missing CARLA Python module. Run on the Ubuntu runtime host with "
            "CARLA_0.9.15 PythonAPI on PYTHONPATH."
        ) from exc
    return carla


def wait_for_world(args: argparse.Namespace, carla: Any) -> Any:
    deadline = time.monotonic() + args.wait_sec
    last_error: Exception | None = None
    while time.monotonic() <= deadline:
        try:
            client = carla.Client(args.carla_host, args.carla_port)
            client.set_timeout(args.carla_timeout)
            world = client.get_world()
            _ = world.get_snapshot()
            return world
        except RuntimeError as exc:
            last_error = exc
            time.sleep(2.0)
    raise RuntimeError(
        f"CARLA RPC was not ready within {args.wait_sec:.1f}s at "
        f"{args.carla_host}:{args.carla_port}: {last_error}"
    )


def find_ego_actor(world: Any, role_name_value: str, wait_sec: float) -> Any:
    deadline = time.monotonic() + wait_sec
    while time.monotonic() <= deadline:
        candidates = [
            actor
            for actor in world.get_actors().filter("vehicle.*")
            if actor.attributes.get("role_name") in {role_name_value, "ego_vehicle", "hero", "autoware_v1"}
        ]
        if candidates:
            return candidates[0]
        time.sleep(1.0)
    raise RuntimeError(f"Unable to find ego vehicle with role_name={role_name_value}")


def select_blueprint(blueprint_library: Any, candidates: list[str]) -> Any | None:
    for blueprint_id in candidates:
        matches = list(blueprint_library.filter(blueprint_id))
        if matches:
            return matches[0]
    for blueprint in blueprint_library.filter("static.prop.*"):
        return blueprint
    return None


def carla_transform_from_local(carla: Any, ego_transform: Any, local_pose: dict[str, float]) -> Any:
    local_location = carla.Location(
        x=local_pose["x"],
        y=-local_pose["y"],
        z=local_pose["z"],
    )
    world_location = ego_transform.transform(local_location)
    rotation = carla.Rotation(
        roll=local_pose["roll_deg"],
        pitch=-local_pose["pitch_deg"],
        yaw=ego_transform.rotation.yaw - local_pose["yaw_deg"],
    )
    return carla.Transform(world_location, rotation)


def opencv_aruco_matrix(marker: dict[str, Any], module_count: int, border_modules: int) -> Optional[list[list[bool]]]:
    dictionary_name = str(marker.get("opencv_aruco_dictionary") or "DICT_6X6_250")
    marker_index = marker.get("opencv_aruco_id")
    if marker_index is None:
        return None
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError:
        return None
    if not hasattr(cv2, "aruco"):
        return None
    dictionary_id = getattr(cv2.aruco, dictionary_name, None)
    if dictionary_id is None or not hasattr(cv2.aruco, "Dictionary_get"):
        return None
    try:
        dictionary = cv2.aruco.Dictionary_get(dictionary_id)
        image = cv2.aruco.drawMarker(
            dictionary,
            int(marker_index),
            int(module_count),
            borderBits=max(1, int(border_modules) or 1),
        )
    except Exception:
        return None
    return [[int(image[row, col]) < 128 for col in range(module_count)] for row in range(module_count)]


def gf_multiply(left: int, right: int) -> int:
    product = 0
    while right:
        if right & 1:
            product ^= left
        right >>= 1
        left <<= 1
        if left & 0x100:
            left ^= 0x11D
    return product & 0xFF


def reed_solomon_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for index in range(degree):
            result[index] = gf_multiply(result[index], root)
            if index + 1 < degree:
                result[index] ^= result[index + 1]
        root = gf_multiply(root, 0x02)
    return result


def reed_solomon_remainder(data: list[int], degree: int) -> list[int]:
    divisor = reed_solomon_divisor(degree)
    result = [0] * degree
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for index, coefficient in enumerate(divisor):
            result[index] ^= gf_multiply(coefficient, factor)
    return result


def append_bits(bits: list[int], value: int, length: int) -> None:
    for index in range(length - 1, -1, -1):
        bits.append((value >> index) & 1)


def version2_l_codewords(payload: str) -> list[int]:
    data = payload.encode("utf-8")
    data_codeword_count = 34
    ecc_codeword_count = 10
    capacity_bits = data_codeword_count * 8
    bits: list[int] = []
    append_bits(bits, 0b0100, 4)
    append_bits(bits, len(data), 8)
    for byte in data:
        append_bits(bits, byte, 8)
    if len(bits) > capacity_bits:
        raise ValueError(f"QR payload is too long for version 2-L: {payload!r}")
    bits.extend([0] * min(4, capacity_bits - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    codewords = [
        sum(bits[index + bit] << (7 - bit) for bit in range(8))
        for index in range(0, len(bits), 8)
    ]
    pad_index = 0
    while len(codewords) < data_codeword_count:
        codewords.append(0xEC if pad_index % 2 == 0 else 0x11)
        pad_index += 1
    return codewords + reed_solomon_remainder(codewords, ecc_codeword_count)


def qr_format_bits(mask: int) -> int:
    error_correction_level_l = 1
    data = (error_correction_level_l << 3) | mask
    remainder = data
    for _ in range(10):
        remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)
    return ((data << 10) | remainder) ^ 0x5412


def qr_code_matrix(payload: str, quiet_zone_modules: int) -> list[list[bool]]:
    size = 25
    modules = [[False for _ in range(size)] for _ in range(size)]
    is_function = [[False for _ in range(size)] for _ in range(size)]

    def set_function(x: int, y: int, dark: bool) -> None:
        if 0 <= x < size and 0 <= y < size:
            modules[y][x] = dark
            is_function[y][x] = True

    def draw_finder(center_x: int, center_y: int) -> None:
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                distance = max(abs(dx), abs(dy))
                set_function(center_x + dx, center_y + dy, distance not in {2, 4})

    def draw_alignment(center_x: int, center_y: int) -> None:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                set_function(center_x + dx, center_y + dy, max(abs(dx), abs(dy)) != 1)

    draw_finder(3, 3)
    draw_finder(size - 4, 3)
    draw_finder(3, size - 4)
    draw_alignment(18, 18)
    for index in range(8, size - 8):
        value = index % 2 == 0
        set_function(6, index, value)
        set_function(index, 6, value)
    set_function(8, size - 8, True)

    mask = 0
    format_bits = qr_format_bits(mask)
    for index in range(6):
        set_function(8, index, ((format_bits >> index) & 1) != 0)
    set_function(8, 7, ((format_bits >> 6) & 1) != 0)
    set_function(8, 8, ((format_bits >> 7) & 1) != 0)
    set_function(7, 8, ((format_bits >> 8) & 1) != 0)
    for index in range(9, 15):
        set_function(14 - index, 8, ((format_bits >> index) & 1) != 0)
    for index in range(8):
        set_function(size - 1 - index, 8, ((format_bits >> index) & 1) != 0)
    for index in range(8, 15):
        set_function(8, size - 15 + index, ((format_bits >> index) & 1) != 0)

    data_bits: list[int] = []
    for codeword in version2_l_codewords(payload):
        append_bits(data_bits, codeword, 8)
    bit_index = 0
    row = size - 1
    direction = -1
    column = size - 1
    while column > 0:
        if column == 6:
            column -= 1
        while 0 <= row < size:
            for column_offset in range(2):
                x = column - column_offset
                if is_function[row][x]:
                    continue
                bit = data_bits[bit_index] if bit_index < len(data_bits) else 0
                if (x + row) % 2 == 0:
                    bit ^= 1
                modules[row][x] = bool(bit)
                bit_index += 1
            row += direction
        row -= direction
        direction = -direction
        column -= 2

    quiet_zone_modules = max(0, quiet_zone_modules)
    if quiet_zone_modules == 0:
        return modules
    wrapped_size = size + (2 * quiet_zone_modules)
    wrapped = [[False for _ in range(wrapped_size)] for _ in range(wrapped_size)]
    for y, row_values in enumerate(modules):
        for x, value in enumerate(row_values):
            wrapped[y + quiet_zone_modules][x + quiet_zone_modules] = value
    return wrapped


def qr_like_matrix(marker: dict[str, Any], marker_id: str, module_count: int, border_modules: int) -> list[list[bool]]:
    """Build a deterministic QR-style binary marker for visual validation.

    On hosts with OpenCV ArUco support, draw a real OpenCV marker matrix.
    Otherwise fall back to a deterministic QR-style proxy pattern.
    """
    marker_type = str(marker.get("type") or "").lower()
    qr_payload = marker.get("qr_payload")
    if marker_type in {"qr", "qr_code"} and qr_payload:
        try:
            return qr_code_matrix(str(qr_payload), border_modules or 4)
        except ValueError:
            pass

    aruco_matrix = opencv_aruco_matrix(marker, module_count, border_modules)
    if aruco_matrix is not None:
        return aruco_matrix

    seed_bytes = hashlib.sha256(marker_id.encode("utf-8")).digest()
    seed = int.from_bytes(seed_bytes[:4], "big")
    matrix = [[False for _ in range(module_count)] for _ in range(module_count)]

    def set_finder(row0: int, col0: int) -> None:
        for row in range(row0, min(row0 + 7, module_count)):
            for col in range(col0, min(col0 + 7, module_count)):
                local_row = row - row0
                local_col = col - col0
                outer = local_row in {0, 6} or local_col in {0, 6}
                inner = 2 <= local_row <= 4 and 2 <= local_col <= 4
                matrix[row][col] = outer or inner

    for row in range(module_count):
        for col in range(module_count):
            in_border = (
                row < border_modules
                or col < border_modules
                or row >= module_count - border_modules
                or col >= module_count - border_modules
            )
            if in_border:
                matrix[row][col] = True
                continue
            value = (row * 37 + col * 19 + seed + ((row ^ col) * 11)) % 9
            matrix[row][col] = value in {0, 2, 5}

    set_finder(border_modules, border_modules)
    set_finder(border_modules, max(border_modules, module_count - border_modules - 7))
    set_finder(max(border_modules, module_count - border_modules - 7), border_modules)
    return matrix


def draw_panel_overlay(
    world: Any,
    carla: Any,
    transform: Any,
    target: dict[str, Any],
    life_sec: float,
) -> dict[str, Any]:
    panel = target.get("panel") if isinstance(target.get("panel"), dict) else {}
    width_m, height_m = normalized_size_m(panel.get("panel_size_m") or target.get("size_m"))
    frame_width_m = float(panel.get("frame_width_m") or 0.05)
    thickness_m = float(panel.get("panel_thickness_m") or 0.03)
    center_z_m = float((target.get("local_pose") or {}).get("z") or 0.0)
    ground_z_m = -center_z_m + 0.04
    leg_y_offset_m = max(0.28, (width_m / 2.0) - 0.18)
    lower_z_m = -height_m / 2.0
    upper_z_m = height_m / 2.0
    half_width_m = width_m / 2.0
    line_count = 0

    def location(local_x: float, local_y: float, local_z: float) -> Any:
        return transform.transform(carla.Location(x=local_x, y=local_y, z=local_z))

    def draw_line(start: tuple[float, float, float], end: tuple[float, float, float], color: Any, thickness: float = 0.035) -> None:
        nonlocal line_count
        world.debug.draw_line(
            location(*start),
            location(*end),
            thickness=thickness,
            color=color,
            life_time=life_sec,
            persistent_lines=False,
        )
        line_count += 1

    frame_color = carla.Color(30, 30, 30)
    backing_color = carla.Color(235, 235, 225)
    stand_color = carla.Color(80, 80, 80)
    rail_color = carla.Color(40, 120, 180)
    x_front = 0.075
    x_back = -max(0.015, thickness_m)

    corners = [
        (x_front, -half_width_m, lower_z_m),
        (x_front, half_width_m, lower_z_m),
        (x_front, half_width_m, upper_z_m),
        (x_front, -half_width_m, upper_z_m),
    ]
    for start, end in zip(corners, [*corners[1:], corners[0]]):
        draw_line(start, end, frame_color, thickness=0.045)
    inner_half_width = max(0.01, half_width_m - frame_width_m)
    inner_lower_z = lower_z_m + frame_width_m
    inner_upper_z = upper_z_m - frame_width_m
    inner_corners = [
        (x_front + 0.004, -inner_half_width, inner_lower_z),
        (x_front + 0.004, inner_half_width, inner_lower_z),
        (x_front + 0.004, inner_half_width, inner_upper_z),
        (x_front + 0.004, -inner_half_width, inner_upper_z),
    ]
    for start, end in zip(inner_corners, [*inner_corners[1:], inner_corners[0]]):
        draw_line(start, end, backing_color, thickness=0.025)
    for y_value in (-half_width_m, half_width_m):
        draw_line((x_back, y_value, lower_z_m), (x_front, y_value, lower_z_m), frame_color, thickness=0.03)
        draw_line((x_back, y_value, upper_z_m), (x_front, y_value, upper_z_m), frame_color, thickness=0.03)

    mount_type = str(panel.get("mount_type") or panel.get("recommended_mount") or "")
    if "rail" in mount_type:
        rail_z = lower_z_m - 0.12
        draw_line((x_back, -half_width_m - 0.25, rail_z), (x_back, half_width_m + 0.25, rail_z), rail_color, thickness=0.045)
        draw_line((x_back, -half_width_m - 0.25, upper_z_m + 0.12), (x_back, half_width_m + 0.25, upper_z_m + 0.12), rail_color, thickness=0.045)
    else:
        for y_value in (-leg_y_offset_m, leg_y_offset_m):
            draw_line((x_back, y_value, lower_z_m), (x_back, y_value, ground_z_m), stand_color, thickness=0.04)
            draw_line((x_back, y_value - 0.32, ground_z_m), (x_back, y_value + 0.32, ground_z_m), stand_color, thickness=0.04)
        draw_line((x_back, -leg_y_offset_m, lower_z_m - 0.18), (x_back, leg_y_offset_m, lower_z_m - 0.18), stand_color, thickness=0.035)

    return {
        "status": "drawn_with_carla_debug_overlay",
        "panel_size_m": [width_m, height_m],
        "frame_width_m": frame_width_m,
        "panel_thickness_m": thickness_m,
        "mount_type": mount_type or None,
        "line_count": line_count,
    }


def draw_fiducial_overlay(
    world: Any,
    carla: Any,
    transform: Any,
    target: dict[str, Any],
    life_sec: float,
) -> dict[str, Any]:
    marker = target.get("marker") or {}
    if not is_fiducial_marker(marker):
        return {"status": "not_fiducial_marker"}

    width_m, height_m = normalized_size_m(target.get("size_m"))
    marker_set = target.get("marker_set") or []
    drawn_points = 0
    marker_summaries: list[dict[str, Any]] = []

    def draw_marker_patch(marker_payload: dict[str, Any], center_y: float, center_z: float, marker_size_m: float) -> dict[str, Any]:
        module_count = int(marker_payload.get("module_count") or marker.get("module_count") or 29)
        border_modules = int(marker_payload.get("border_modules") or marker.get("border_modules") or 0)
        marker_id = str(marker_payload.get("marker_id") or marker.get("marker_id") or target["target_id"])
        matrix = qr_like_matrix(marker_payload, marker_id, module_count, border_modules)
        module_count = len(matrix)
        module_size = marker_size_m / module_count
        point_size = max(0.018, module_size * 0.95)
        patch_points = 0

        for row, values in enumerate(matrix):
            local_z = center_z + (marker_size_m / 2.0) - ((row + 0.5) * module_size)
            for col, enabled in enumerate(values):
                local_y = center_y + (-marker_size_m / 2.0) + ((col + 0.5) * module_size)
                local_x = 0.08
                location = transform.transform(carla.Location(x=local_x, y=local_y, z=local_z))
                color = carla.Color(0, 0, 0) if enabled else carla.Color(255, 255, 255)
                world.debug.draw_point(
                    location,
                    size=point_size,
                    color=color,
                    life_time=life_sec,
                    persistent_lines=False,
                )
                patch_points += 1
        return {
            "marker_id": marker_id,
            "opencv_aruco_dictionary": marker_payload.get("opencv_aruco_dictionary"),
            "opencv_aruco_id": marker_payload.get("opencv_aruco_id"),
            "module_count": module_count,
            "drawn_points": patch_points,
            "size_m": marker_size_m,
            "local_yz_m": [center_y, center_z],
        }

    if marker_set:
        for marker_payload in marker_set:
            local_yz = marker_payload.get("local_yz_m") or [0.0, 0.0]
            marker_size_m = float(marker_payload.get("size_m") or marker.get("marker_length_m") or 0.51)
            summary = draw_marker_patch(
                dict(marker_payload),
                float(local_yz[0]),
                float(local_yz[1]),
                marker_size_m,
            )
            marker_summaries.append(summary)
            drawn_points += int(summary["drawn_points"])
    else:
        marker_size_m = min(width_m, height_m)
        summary = draw_marker_patch(marker, 0.0, 0.0, marker_size_m)
        marker_summaries.append(summary)
        drawn_points += int(summary["drawn_points"])

    label_location = transform.transform(carla.Location(x=0.12, y=0.0, z=(height_m / 2.0) + 0.25))
    world.debug.draw_string(
        label_location,
        str(marker.get("marker_id") or marker.get("board_asset_id") or target["target_id"]),
        draw_shadow=False,
        color=carla.Color(255, 230, 0),
        life_time=life_sec,
        persistent_lines=False,
    )
    return {
        "status": "drawn_with_carla_debug_overlay",
        "marker_id": str(marker.get("marker_id") or target["target_id"]),
        "board_asset_id": marker.get("board_asset_id"),
        "marker_count": len(marker_summaries),
        "markers": marker_summaries,
        "drawn_points": drawn_points,
        "size_m": [width_m, height_m],
    }


def set_role_attribute(blueprint: Any, value: str) -> None:
    if hasattr(blueprint, "has_attribute") and blueprint.has_attribute("role_name"):
        blueprint.set_attribute("role_name", value)


def maybe_delete_existing(world: Any, role_prefix: str) -> list[int]:
    deleted: list[int] = []
    for actor in world.get_actors():
        if str(actor.attributes.get("role_name") or "").startswith(role_prefix):
            actor.destroy()
            deleted.append(int(actor.id))
    return deleted


def spawn_scene(args: argparse.Namespace, scene: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    carla = load_carla_module()
    world = wait_for_world(args, carla)
    ego = find_ego_actor(world, args.ego_vehicle_role_name, args.ego_wait_sec)
    ego_transform = ego.get_transform()
    blueprint_library = world.get_blueprint_library()
    scene_id = plan["scene_asset_id"]
    role_prefix = f"simctl_calibration_scene::{scene_id}::"
    deleted = maybe_delete_existing(world, role_prefix) if args.delete_existing else []
    spawned: list[dict[str, Any]] = []

    for target in plan["targets"]:
        blueprint = select_blueprint(blueprint_library, target["blueprint_candidates"])
        if blueprint is None:
            spawned.append(
                {
                    "target_id": target["target_id"],
                    "status": "skipped",
                    "reason": "no_static_prop_blueprint_available",
                }
            )
            continue
        set_role_attribute(blueprint, target["role_name"])
        transform = carla_transform_from_local(carla, ego_transform, target["local_pose"])
        actor = world.try_spawn_actor(blueprint, transform)
        if actor is None:
            spawned.append(
                {
                    "target_id": target["target_id"],
                    "status": "failed",
                    "reason": "try_spawn_actor_returned_none",
                    "blueprint_id": blueprint.id,
                }
            )
            continue
        panel_overlay = (
            draw_panel_overlay(world, carla, transform, target, args.debug_life_sec)
            if args.debug_draw and target.get("panel")
            else {"status": "not_requested"}
        )
        marker_overlay = (
            draw_fiducial_overlay(world, carla, transform, target, args.debug_life_sec)
            if args.debug_draw and target.get("marker")
            else {"status": "not_requested"}
        )
        spawned.append(
            {
                "target_id": target["target_id"],
                "status": "spawned",
                "actor_id": int(actor.id),
                "type_id": actor.type_id,
                "blueprint_id": blueprint.id,
                "role_name": target["role_name"],
                "kind": target.get("kind"),
                "material": target.get("material"),
                "panel": target.get("panel"),
                "marker": target.get("marker"),
                "panel_overlay": panel_overlay,
                "marker_overlay": marker_overlay,
                "world_transform": {
                    "x": float(transform.location.x),
                    "y": float(transform.location.y),
                    "z": float(transform.location.z),
                    "roll": float(transform.rotation.roll),
                    "pitch": float(transform.rotation.pitch),
                    "yaw": float(transform.rotation.yaw),
                },
            }
        )
        if args.debug_draw:
            world.debug.draw_string(
                transform.location,
                target["target_id"],
                draw_shadow=False,
                color=carla.Color(255, 80, 0),
                life_time=args.debug_life_sec,
                persistent_lines=False,
            )

    return {
        **plan,
        "spawned_at": utc_now(),
        "ego_actor_id": int(ego.id),
        "ego_type_id": ego.type_id,
        "deleted_existing_actor_ids": deleted,
        "spawned": spawned,
        "spawned_count": sum(1 for item in spawned if item.get("status") == "spawned"),
        "failed_count": sum(1 for item in spawned if item.get("status") == "failed"),
        "skipped_count": sum(1 for item in spawned if item.get("status") == "skipped"),
    }


def write_artifact(run_dir: Path, scene_id: str, payload: dict[str, Any]) -> Path:
    output_dir = run_dir / "runtime_verification" / "calibration_scene"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{scene_id}_spawn.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-file", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--carla-host", default="127.0.0.1")
    parser.add_argument("--carla-port", type=int, default=2000)
    parser.add_argument("--carla-timeout", type=float, default=10.0)
    parser.add_argument("--wait-sec", type=float, default=120.0)
    parser.add_argument("--ego-wait-sec", type=float, default=90.0)
    parser.add_argument("--ego-vehicle-role-name", default="ego_vehicle")
    parser.add_argument("--delete-existing", action="store_true")
    parser.add_argument("--debug-draw", action="store_true")
    parser.add_argument("--debug-life-sec", type=float, default=600.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scene_file = Path(args.scene_file).resolve()
    run_dir = Path(args.run_dir).resolve()
    scene = load_scene(scene_file)
    plan = build_spawn_plan(scene, scene_file)
    payload = plan if args.dry_run else spawn_scene(args, scene, plan)
    artifact = write_artifact(run_dir, plan["scene_asset_id"], payload)
    payload["artifact"] = str(artifact)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not args.dry_run and payload.get("spawned_count", 0) <= 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
