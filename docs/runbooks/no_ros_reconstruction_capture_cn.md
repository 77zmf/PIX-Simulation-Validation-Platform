# 不接入 ROS 的重建数据录制

这套流程用于车端不能新增 ROS 订阅/录制节点时的重建数据采集。录制阶段不调用 `ros2`、`rosbag2`、`tf2`，只做旁路数据抓取：

- IPC：用 `tcpdump` 被动抓 LiDAR UDP 原始包，落本机 PCAP。
- Orin：用 GStreamer `nvunixfdsrc` 从 RGBA socket 抽 JPEG 帧，默认录前后 3mm 摄像头。

默认本地输出：

```text
IPC:  /home/ipc/pix/road_tests/no_ros_reconstruction_capture
Orin: /home/nvidia/pix/road_tests/no_ros_reconstruction_capture
```

## IPC：雷达原始包

先做 10 秒被动发现，确认 UDP 来源和接口：

```bash
sudo bash ~/pix/no_ros_reconstruction_capture.sh discover \
  --role ipc-lidar \
  --iface any \
  --seconds 10 \
  --filter udp
```

开始录制：

```bash
sudo bash ~/pix/no_ros_reconstruction_capture.sh start \
  --role ipc-lidar \
  --iface any \
  --filter udp \
  --duration 0
```

停止录制：

```bash
sudo bash ~/pix/no_ros_reconstruction_capture.sh stop --role ipc-lidar
```

查看状态：

```bash
sudo bash ~/pix/no_ros_reconstruction_capture.sh status --role ipc-lidar
```

## Orin：摄像头 socket 帧

默认录 `front_3mm` 和 `rear_3mm`，采样 10Hz：

```bash
bash ~/pix/no_ros_reconstruction_capture.sh start \
  --role orin-camera \
  --fps 10 \
  --duration 0
```

停止录制：

```bash
bash ~/pix/no_ros_reconstruction_capture.sh stop --role orin-camera
```

如果要六路摄像头：

```bash
bash ~/pix/no_ros_reconstruction_capture.sh start \
  --role orin-camera \
  --all-channels \
  --fps 10 \
  --duration 0
```

## 录制产物

每次录制会生成一个 run 目录，里面包含：

- `capture_manifest.env`
- `started_at.txt`
- `finished_at.txt`
- `disk_before.txt` / `disk_after.txt`
- IPC 的 `lidar_udp_*.pcap`
- Orin 的 `front_3mm/frame_*.jpg`、`rear_3mm/frame_*.jpg`
- Orin 的 `frame_count.txt`，可用 `帧数 / 录制秒数` 复核帧率

## 边界

这不是在线 ROS bag。后处理时再把 PCAP、相机帧、标定和时间同步信息转换为重建链路需要的 bag、PCD 或 RGB 点云输入。
