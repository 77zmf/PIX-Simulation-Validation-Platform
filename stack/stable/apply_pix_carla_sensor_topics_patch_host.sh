#!/usr/bin/env bash
set -euo pipefail

AUTOWARE_WS="${AUTOWARE_WS:-$HOME/zmf_ws/projects/autoware_universe/autoware}"
ROLLBACK=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Apply the PIX robobus Autoware CARLA interface sensor-topic patch.

Default target:
  $HOME/zmf_ws/projects/autoware_universe/autoware

Why:
  The upstream autoware_carla_interface in this workspace publishes only
  top/left/right lidar topics and hardcodes camera output to
  /sensing/camera/traffic_light/*. PIX validation expects the 117th robobus
  topics declared by robobus117th_objects.json, including rear_top/rear lidar
  and CAM_FRONT/CAM_* camera topics.

Validation:
  Run scenarios/l0/robobus117th_town01_closed_loop.yaml with simctl --execute.
  The runtime health check should see all expected sensor topics for L0.

Rollback:
  Re-run this script with --rollback, or restore the generated .bak file.

Options:
  --autoware-ws PATH  Autoware workspace root.
  --dry-run           Check target files without writing.
  --rollback          Restore backups created by this script.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --autoware-ws) AUTOWARE_WS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --rollback) ROLLBACK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

SOURCE_FILE="${AUTOWARE_WS}/src/universe/autoware_universe/simulator/autoware_carla_interface/src/autoware_carla_interface/carla_ros.py"
BUILD_FILE="${AUTOWARE_WS}/build/autoware_carla_interface/src/autoware_carla_interface/carla_ros.py"
BACKUP_SUFFIX=".pix_sensor_topics.bak"

python3 - "$SOURCE_FILE" "$BUILD_FILE" "$BACKUP_SUFFIX" "$ROLLBACK" "$DRY_RUN" <<'PY'
from __future__ import annotations

import py_compile
import sys
from pathlib import Path

source_file = Path(sys.argv[1])
build_file = Path(sys.argv[2])
backup_suffix = sys.argv[3]
rollback = sys.argv[4] == "1"
dry_run = sys.argv[5] == "1"
targets = [source_file]
if build_file != source_file:
    targets.append(build_file)

topic_marker = "PIX_CARLA_SENSOR_TOPIC_PATCH"
lidar_marker = "PIX_CARLA_LIDAR_CHANNEL_PATCH"
camera_info_marker = "PIX_CARLA_CAMERA_INFO_RETURN_PATCH"
camera_frequency_marker = "PIX_CARLA_CAMERA_FREQUENCY_PATCH"
camera_frequency_init_marker = "PIX_CARLA_CAMERA_FREQUENCY_INIT_PATCH"

init_old = """        self.pub_lidar = {}
        self.sensor_frequencies = {
"""
init_new = """        self.pub_lidar = {}
        self.pub_camera = {}
        self.pub_camera_info = {}
        # PIX_CARLA_SENSOR_TOPIC_PATCH: publish per-sensor robobus camera/lidar topics.
        self.sensor_frequencies = {
"""

publisher_old = """            if sensor["type"] == "sensor.camera.rgb":
                self.pub_camera = self.ros2_node.create_publisher(
                    Image, "/sensing/camera/traffic_light/image_raw", 1
                )
                self.pub_camera_info = self.ros2_node.create_publisher(
                    CameraInfo, "/sensing/camera/traffic_light/camera_info", 1
                )
            elif sensor["type"] == "sensor.lidar.ray_cast":
                if sensor["id"] in self.sensor_frequencies:
                    self.pub_lidar[sensor["id"]] = self.ros2_node.create_publisher(
                        PointCloud2, f'/sensing/lidar/{sensor["id"]}/pointcloud_before_sync', 10
                    )
                else:
                    self.ros2_node.get_logger().info(
                        "Please use Top, Right, or Left as the LIDAR ID"
                    )
"""
publisher_new = """            if sensor["type"] == "sensor.camera.rgb":
                sensor_id = sensor["id"]
                self.pub_camera[sensor_id] = self.ros2_node.create_publisher(
                    Image, f"/sensing/camera/{sensor_id}/image_raw", 1
                )
                self.pub_camera_info[sensor_id] = self.ros2_node.create_publisher(
                    CameraInfo, f"/sensing/camera/{sensor_id}/camera_info", 1
                )
            elif sensor["type"] == "sensor.lidar.ray_cast":
                sensor_id = sensor["id"]
                if sensor_id not in self.sensor_frequencies:
                    self.sensor_frequencies[sensor_id] = 11
                    self.publish_prev_times[sensor_id] = datetime.datetime.now()
                self.pub_lidar[sensor_id] = self.ros2_node.create_publisher(
                    PointCloud2, f"/sensing/lidar/{sensor_id}/pointcloud_before_sync", 10
                )
"""

camera_old = """    def camera(self, carla_camera_data):
        \"\"\"Transform the received carla camera data into a ROS image and info message and publish.\"\"\"
        while self.first_:
            self._camera_info_ = self._build_camera_info(carla_camera_data)
            self.first_ = False

        if self.checkFrequency("camera"):
            return
        self.publish_prev_times["camera"] = datetime.datetime.now()

        image_data_array = numpy.ndarray(
            shape=(carla_camera_data.height, carla_camera_data.width, 4),
            dtype=numpy.uint8,
            buffer=carla_camera_data.raw_data,
        )
        # cspell:ignore interp bgra
        img_msg = self.cv_bridge.cv2_to_imgmsg(image_data_array, encoding="bgra8")
        img_msg.header = self.get_msg_header(
            frame_id="traffic_light_left_camera/camera_optical_link"
        )
        cam_info = self._camera_info
        cam_info.header = img_msg.header
        self.pub_camera_info.publish(cam_info)
        self.pub_camera.publish(img_msg)
"""
camera_new = """    def camera(self, carla_camera_data, id_):
        \"\"\"Transform the received carla camera data into a ROS image and info message and publish.\"\"\"
        if self.checkFrequency("camera"):
            return
        self.publish_prev_times["camera"] = datetime.datetime.now()

        if id_ not in self.id_to_camera_info_map:
            self.id_to_camera_info_map[id_] = self._build_camera_info(carla_camera_data)

        image_data_array = numpy.ndarray(
            shape=(carla_camera_data.height, carla_camera_data.width, 4),
            dtype=numpy.uint8,
            buffer=carla_camera_data.raw_data,
        )
        # cspell:ignore interp bgra
        img_msg = self.cv_bridge.cv2_to_imgmsg(image_data_array, encoding="bgra8")
        img_msg.header = self.get_msg_header(frame_id=f"{id_}/camera_optical_link")
        cam_info = self.id_to_camera_info_map[id_]
        cam_info.header = img_msg.header
        self.pub_camera_info[id_].publish(cam_info)
        self.pub_camera[id_].publish(img_msg)
"""

run_step_old = """            if sensor_type == "sensor.camera.rgb":
                self.camera(data[1])
"""
run_step_new = """            if sensor_type == "sensor.camera.rgb":
                self.camera(data[1], key)
"""

topic_replacements = [
    (init_old, init_new),
    (publisher_old, publisher_new),
    (camera_old, camera_new),
    (run_step_old, run_step_new),
]

lidar_old = """        header = self.get_msg_header(frame_id="velodyne_top_changed")
        fields = [
            PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name="intensity", offset=12, datatype=PointField.UINT8, count=1),
            PointField(name="return_type", offset=13, datatype=PointField.UINT8, count=1),
            PointField(name="channel", offset=14, datatype=PointField.UINT16, count=1),
        ]

        lidar_data = numpy.frombuffer(
            carla_lidar_measurement.raw_data, dtype=numpy.float32
        ).reshape(-1, 4)
        intensity = lidar_data[:, 3]
        intensity = (
            numpy.clip(intensity, 0, 1) * 255
        )  # CARLA lidar intensity values are between 0 and 1
        intensity = intensity.astype(numpy.uint8).reshape(-1, 1)

        return_type = numpy.zeros((lidar_data.shape[0], 1), dtype=numpy.uint8)
        channel = numpy.empty((0, 1), dtype=numpy.uint16)
        self.channels = self.sensors["sensors"]

        for i in range(self.channels[1]["channels"]):
            current_ring_points_count = carla_lidar_measurement.get_point_count(i)
            channel = numpy.vstack(
                (channel, numpy.full((current_ring_points_count, 1), i, dtype=numpy.uint16))
            )
"""

lidar_new = """        header = self.get_msg_header(frame_id=f"{id_}_changed")
        fields = [
            PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name="intensity", offset=12, datatype=PointField.UINT8, count=1),
            PointField(name="return_type", offset=13, datatype=PointField.UINT8, count=1),
            PointField(name="channel", offset=14, datatype=PointField.UINT16, count=1),
        ]

        lidar_data = numpy.frombuffer(
            carla_lidar_measurement.raw_data, dtype=numpy.float32
        ).reshape(-1, 4)
        intensity = lidar_data[:, 3]
        intensity = (
            numpy.clip(intensity, 0, 1) * 255
        )  # CARLA lidar intensity values are between 0 and 1
        intensity = intensity.astype(numpy.uint8).reshape(-1, 1)

        return_type = numpy.zeros((lidar_data.shape[0], 1), dtype=numpy.uint8)
        channel = numpy.empty((0, 1), dtype=numpy.uint16)
        sensor_channels = int(
            next(
                (
                    sensor.get("channels", 0)
                    for sensor in self.sensors["sensors"]
                    if sensor.get("id") == id_
                ),
                0,
            )
            or 0
        )
        if sensor_channels <= 0:
            sensor_channels = 1
        # PIX_CARLA_LIDAR_CHANNEL_PATCH: use the current lidar id, not a fixed sensor index.
        for i in range(sensor_channels):
            current_ring_points_count = carla_lidar_measurement.get_point_count(i)
            channel = numpy.vstack(
                (channel, numpy.full((current_ring_points_count, 1), i, dtype=numpy.uint16))
            )
        if channel.shape[0] != lidar_data.shape[0]:
            channel = numpy.zeros((lidar_data.shape[0], 1), dtype=numpy.uint16)
"""

camera_info_return_old = """        self._camera_info = camera_info

    def camera(self, carla_camera_data, id_):
"""
camera_info_return_new = """        self._camera_info = camera_info
        # PIX_CARLA_CAMERA_INFO_RETURN_PATCH: per-id camera publishers need a returned object.
        return camera_info

    def camera(self, carla_camera_data, id_):
"""

camera_frequency_old = """        if self.checkFrequency("camera"):
            return
        self.publish_prev_times["camera"] = datetime.datetime.now()

        if id_ not in self.id_to_camera_info_map:
"""
camera_frequency_new = """        if id_ not in self.sensor_frequencies:
            self.sensor_frequencies[id_] = self.sensor_frequencies.get("camera", 11)
            self.publish_prev_times[id_] = datetime.datetime.now()
        # PIX_CARLA_CAMERA_FREQUENCY_PATCH: each camera id needs independent throttling.
        if self.checkFrequency(id_):
            return
        self.publish_prev_times[id_] = datetime.datetime.now()

        if id_ not in self.id_to_camera_info_map:
"""

camera_frequency_init_old = """        if id_ not in self.sensor_frequencies:
            self.sensor_frequencies[id_] = self.sensor_frequencies.get("camera", 11)
            self.publish_prev_times[id_] = datetime.datetime.now()
        # PIX_CARLA_CAMERA_FREQUENCY_PATCH: each camera id needs independent throttling.
"""
camera_frequency_init_new = """        if id_ not in self.sensor_frequencies:
            self.sensor_frequencies[id_] = self.sensor_frequencies.get("camera", 11)
            # PIX_CARLA_CAMERA_FREQUENCY_INIT_PATCH: the first frame for a new camera id must publish.
            self.publish_prev_times[id_] = datetime.datetime.min
        # PIX_CARLA_CAMERA_FREQUENCY_PATCH: each camera id needs independent throttling.
"""

for path in targets:
    if not path.exists():
        raise SystemExit(f"target file not found: {path}")

    backup = Path(str(path) + backup_suffix)
    text = path.read_text()

    if rollback:
        if not backup.exists():
            print(f"no backup to restore: {backup}")
            continue
        if dry_run:
            print(f"would restore: {backup} -> {path}")
            continue
        path.write_text(backup.read_text())
        py_compile.compile(str(path), doraise=True)
        print(f"restored: {path}")
        continue

    patched_text = text
    changes = []
    if topic_marker not in patched_text:
        for old, new in topic_replacements:
            if old not in patched_text:
                raise SystemExit(f"target block not found in {path}")
            patched_text = patched_text.replace(old, new, 1)
        changes.append("sensor topics")
    if lidar_marker not in patched_text:
        if lidar_old not in patched_text:
            raise SystemExit(f"lidar channel block not found in {path}")
        patched_text = patched_text.replace(lidar_old, lidar_new, 1)
        changes.append("lidar channels")
    if camera_info_marker not in patched_text:
        if camera_info_return_old not in patched_text:
            raise SystemExit(f"camera info return block not found in {path}")
        patched_text = patched_text.replace(camera_info_return_old, camera_info_return_new, 1)
        changes.append("camera info return")
    if camera_frequency_marker not in patched_text:
        if camera_frequency_old not in patched_text:
            raise SystemExit(f"camera frequency block not found in {path}")
        patched_text = patched_text.replace(camera_frequency_old, camera_frequency_new, 1)
        changes.append("camera frequency")
    if camera_frequency_init_marker not in patched_text:
        if camera_frequency_init_old not in patched_text:
            raise SystemExit(f"camera frequency init block not found in {path}")
        patched_text = patched_text.replace(camera_frequency_init_old, camera_frequency_init_new, 1)
        changes.append("camera frequency init")

    if not changes:
        print(f"already patched: {path}")
        continue

    if dry_run:
        print(f"would patch ({', '.join(changes)}): {path}")
        continue

    if not backup.exists():
        backup.write_text(text)
        print(f"backup: {backup}")

    path.write_text(patched_text)
    py_compile.compile(str(path), doraise=True)
    print(f"patched ({', '.join(changes)}): {path}")
PY

echo "Patch operation completed."
