#!/usr/bin/env python3
"""Capture or inspect camera images and detect fiducial calibration boards with OpenCV."""

from __future__ import annotations

import argparse
import json
import queue
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}
DEFAULT_ARUCO_DICTIONARIES = ("DICT_APRILTAG_16h5", "DICT_6X6_250", "DICT_5X5_250", "DICT_4X4_250")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_cv2() -> Any:
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - host dependency path
        raise SystemExit("OpenCV is required. Install python3-opencv or opencv-python.") from exc
    return cv2


def find_scene_spawn_artifact(run_dir: Path, explicit_path: Optional[str]) -> Optional[Path]:
    if explicit_path:
        path = Path(explicit_path)
        return path if path.exists() else None
    scene_dir = run_dir / "runtime_verification" / "calibration_scene"
    candidates = sorted(scene_dir.glob("*_spawn.json")) if scene_dir.exists() else []
    return candidates[-1] if candidates else None


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_carla_module() -> Any:
    try:
        import carla  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - host-only path
        raise SystemExit("CARLA PythonAPI is required when --capture-from-carla is set.") from exc
    return carla


def find_ego_actor(world: Any, role_name_value: str, attempts: int = 5, sleep_sec: float = 1.0) -> Any:
    accepted_roles = {role_name_value, "ego_vehicle", "hero", "autoware_v1"}
    last_vehicle_count = 0
    for attempt_index in range(max(1, attempts)):
        vehicles = list(world.get_actors().filter("vehicle.*"))
        last_vehicle_count = len(vehicles)
        candidates = [actor for actor in vehicles if actor.attributes.get("role_name") in accepted_roles]
        if candidates:
            return candidates[0]
        if attempt_index < attempts - 1:
            try:
                world.wait_for_tick()
            except Exception:
                time.sleep(sleep_sec)
    raise RuntimeError(
        f"Unable to find ego vehicle with role_name={role_name_value}; "
        f"vehicle_count={last_vehicle_count}"
    )


def ego_relative_transform(carla: Any, ego_transform: Any, local_xyz: tuple[float, float, float], yaw_deg: float) -> Any:
    location = ego_transform.transform(carla.Location(x=local_xyz[0], y=local_xyz[1], z=local_xyz[2]))
    return carla.Transform(
        location,
        carla.Rotation(pitch=-5.0, yaw=ego_transform.rotation.yaw + yaw_deg, roll=0.0),
    )


def capture_from_carla(args: argparse.Namespace, image_dir: Path) -> list[Path]:
    carla = load_carla_module()
    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(args.carla_timeout)
    world = client.get_world()
    ego = find_ego_actor(world, args.ego_vehicle_role_name)
    ego_transform = ego.get_transform()
    blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
    blueprint.set_attribute("image_size_x", str(args.image_width))
    blueprint.set_attribute("image_size_y", str(args.image_height))
    blueprint.set_attribute("fov", str(args.camera_fov_deg))

    view_specs = {
        "front": ((2.0, 0.0, 2.0), 0.0),
        "left": ((0.0, -0.4, 2.0), -90.0),
        "right": ((0.0, 0.4, 2.0), 90.0),
        "rear": ((-2.0, 0.0, 2.0), 180.0),
    }
    captured: list[Path] = []
    for view_name in args.capture_views.split(","):
        view_name = view_name.strip()
        if not view_name:
            continue
        if view_name not in view_specs:
            raise ValueError(f"Unsupported capture view: {view_name}")
        local_xyz, yaw_deg = view_specs[view_name]
        transform = ego_relative_transform(carla, ego_transform, local_xyz, yaw_deg)
        image_queue: queue.Queue[Any] = queue.Queue(maxsize=1)

        def enqueue_image(image: Any) -> None:
            try:
                image_queue.put_nowait(image)
            except queue.Full:
                pass

        camera = world.spawn_actor(blueprint, transform)
        try:
            camera.listen(enqueue_image)
            deadline = time.monotonic() + args.capture_timeout_sec
            image = None
            while time.monotonic() <= deadline:
                try:
                    image = image_queue.get(timeout=1.0)
                    break
                except queue.Empty:
                    try:
                        world.wait_for_tick()
                    except RuntimeError:
                        time.sleep(0.1)
            if image is None:
                raise RuntimeError(f"Timed out waiting for CARLA camera image for view={view_name}")
            path = image_dir / f"{view_name}_camera.png"
            image.save_to_disk(str(path))
            captured.append(path)
        finally:
            try:
                camera.stop()
            except RuntimeError:
                pass
    return captured


def list_image_paths(image_dir: Path) -> list[Path]:
    if not image_dir.exists():
        return []
    return sorted(path for path in image_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)


def aruco_detections(cv2: Any, gray: Any, dictionary_names: list[str]) -> list[dict[str, Any]]:
    if not hasattr(cv2, "aruco"):
        return []
    detections: list[dict[str, Any]] = []
    parameters = cv2.aruco.DetectorParameters_create() if hasattr(cv2.aruco, "DetectorParameters_create") else None
    for dictionary_name in dictionary_names:
        dictionary_id = getattr(cv2.aruco, dictionary_name, None)
        if dictionary_id is None or not hasattr(cv2.aruco, "Dictionary_get"):
            continue
        dictionary = cv2.aruco.Dictionary_get(dictionary_id)
        corners, ids, _ = cv2.aruco.detectMarkers(gray, dictionary, parameters=parameters)
        if ids is None:
            continue
        for marker_id, corner in zip(ids.flatten().tolist(), corners):
            points = corner.reshape(-1, 2).tolist()
            detections.append(
                {
                    "type": "aruco",
                    "dictionary": dictionary_name,
                    "id": int(marker_id),
                    "points": [[float(x), float(y)] for x, y in points],
                }
            )
    return detections


def qr_detections(cv2: Any, image: Any) -> list[dict[str, Any]]:
    if not hasattr(cv2, "QRCodeDetector"):
        return []
    detector = cv2.QRCodeDetector()
    detections: list[dict[str, Any]] = []
    try:
        ok, decoded_info, points, _ = detector.detectAndDecodeMulti(image)
    except Exception:
        ok, decoded_info, points = False, [], None
    if ok and points is not None:
        for decoded, corner in zip(decoded_info, points):
            detections.append(
                {
                    "type": "qr",
                    "payload": str(decoded),
                    "points": [[float(x), float(y)] for x, y in corner.reshape(-1, 2).tolist()],
                }
            )
        return detections
    try:
        decoded, points, _ = detector.detectAndDecode(image)
    except Exception:
        decoded, points = "", None
    if points is not None:
        detections.append(
            {
                "type": "qr",
                "payload": str(decoded),
                "points": [[float(x), float(y)] for x, y in points.reshape(-1, 2).tolist()],
            }
        )
    return detections


def texture_transition_score(cv2: Any, roi: Any) -> int:
    resized = cv2.resize(roi, (32, 32))
    rows = [8, 16, 24]
    cols = [8, 16, 24]
    score = 0
    for row in rows:
        values = resized[row, :]
        score += int((values[:-1] != values[1:]).sum())
    for col in cols:
        values = resized[:, col]
        score += int((values[:-1] != values[1:]).sum())
    return score


def binary_board_candidates(cv2: Any, gray: Any, min_area_px: float) -> list[dict[str, Any]]:
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    threshold = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        5,
    )
    contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[dict[str, Any]] = []
    max_area_px = float(gray.shape[0] * gray.shape[1]) * 0.25
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area_px or area > max_area_px:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
        if len(approx) < 4 or len(approx) > 10:
            continue
        x, y, width, height = cv2.boundingRect(approx)
        if width <= 0 or height <= 0:
            continue
        aspect = width / float(height)
        if not 0.35 <= aspect <= 3.2:
            continue
        roi = threshold[y : y + height, x : x + width]
        black_ratio = float((roi == 0).sum()) / float(roi.size)
        transitions = texture_transition_score(cv2, roi)
        if 0.08 <= black_ratio <= 0.92 and transitions >= 18:
            candidates.append(
                {
                    "type": "binary_fiducial_candidate",
                    "bbox_xywh": [int(x), int(y), int(width), int(height)],
                    "area_px": area,
                    "polygon_vertices": int(len(approx)),
                    "black_ratio": black_ratio,
                    "transition_score": transitions,
                }
            )
    return candidates


def annotate_image(cv2: Any, image: Any, detections: list[dict[str, Any]], output_path: Path) -> None:
    for detection in detections:
        if "points" in detection:
            import numpy as np  # type: ignore[import-not-found]

            points = detection["points"]
            contour = np.array(points, dtype="float32").reshape((-1, 1, 2)).astype("int32")
            cv2.polylines(image, [contour], True, (0, 255, 255), 3)
        elif "bbox_xywh" in detection:
            x, y, width, height = detection["bbox_xywh"]
            cv2.rectangle(image, (x, y), (x + width, y + height), (0, 255, 255), 3)
    cv2.imwrite(str(output_path), image)


def detect_image(cv2: Any, image_path: Path, dictionary_names: list[str], min_area_px: float, annotated_dir: Path) -> dict[str, Any]:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        return {"image": str(image_path), "status": "unreadable", "detections": []}
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    detections = []
    detections.extend(aruco_detections(cv2, gray, dictionary_names))
    detections.extend(qr_detections(cv2, image))
    detections.extend(binary_board_candidates(cv2, gray, min_area_px))
    annotated_path = annotated_dir / f"{image_path.stem}_opencv_detections.png"
    annotate_image(cv2, image, detections, annotated_path)
    return {
        "image": str(image_path),
        "status": "processed",
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "detections": detections,
        "detection_count": len(detections),
        "annotated_image": str(annotated_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--scene-spawn-artifact")
    parser.add_argument("--image-dir")
    parser.add_argument("--capture-from-carla", action="store_true")
    parser.add_argument("--carla-host", default="127.0.0.1")
    parser.add_argument("--carla-port", type=int, default=2000)
    parser.add_argument("--carla-timeout", type=float, default=10.0)
    parser.add_argument("--ego-vehicle-role-name", default="ego_vehicle")
    parser.add_argument("--capture-views", default="front,left,right,rear")
    parser.add_argument("--image-width", type=int, default=1600)
    parser.add_argument("--image-height", type=int, default=1000)
    parser.add_argument("--camera-fov-deg", type=float, default=95.0)
    parser.add_argument("--capture-timeout-sec", type=float, default=20.0)
    parser.add_argument("--aruco-dictionaries", default=",".join(DEFAULT_ARUCO_DICTIONARIES))
    parser.add_argument("--min-area-px", type=float, default=1200.0)
    parser.add_argument("--min-detections", type=int, default=1)
    parser.add_argument("--expected-board-count", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cv2 = load_cv2()
    run_dir = Path(args.run_dir).resolve()
    output_dir = run_dir / "runtime_verification" / "calibration" / "camera_fiducial_board_detection"
    image_dir = Path(args.image_dir).resolve() if args.image_dir else output_dir / "images"
    annotated_dir = output_dir / "annotated"
    image_dir.mkdir(parents=True, exist_ok=True)
    annotated_dir.mkdir(parents=True, exist_ok=True)

    captured_images = capture_from_carla(args, image_dir) if args.capture_from_carla else []
    image_paths = list_image_paths(image_dir)
    spawn_artifact_path = find_scene_spawn_artifact(run_dir, args.scene_spawn_artifact)
    spawn_artifact = read_json(spawn_artifact_path)
    expected_board_count = args.expected_board_count or int(spawn_artifact.get("target_count") or 0)
    dictionary_names = [item.strip() for item in args.aruco_dictionaries.split(",") if item.strip()]
    image_results = [
        detect_image(cv2, image_path, dictionary_names, args.min_area_px, annotated_dir)
        for image_path in image_paths
    ]
    detection_count = sum(int(result.get("detection_count") or 0) for result in image_results)
    aruco_count = sum(
        1
        for result in image_results
        for detection in result.get("detections", [])
        if detection.get("type") == "aruco"
    )
    qr_count = sum(
        1
        for result in image_results
        for detection in result.get("detections", [])
        if detection.get("type") == "qr"
    )
    binary_candidate_count = sum(
        1
        for result in image_results
        for detection in result.get("detections", [])
        if detection.get("type") == "binary_fiducial_candidate"
    )
    passed = detection_count >= args.min_detections
    payload = {
        "generated_at": utc_now(),
        "run_dir": str(run_dir),
        "opencv_version": str(cv2.__version__),
        "capture_from_carla": bool(args.capture_from_carla),
        "captured_images": [str(path) for path in captured_images],
        "image_dir": str(image_dir),
        "scene_spawn_artifact": str(spawn_artifact_path) if spawn_artifact_path else None,
        "expected_board_count": expected_board_count,
        "min_detections": args.min_detections,
        "detection_count": detection_count,
        "aruco_count": aruco_count,
        "qr_count": qr_count,
        "binary_fiducial_candidate_count": binary_candidate_count,
        "passed": passed,
        "images": image_results,
    }
    output_path = output_dir / "detection_result.json"
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({**payload, "result_path": str(output_path)}, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
