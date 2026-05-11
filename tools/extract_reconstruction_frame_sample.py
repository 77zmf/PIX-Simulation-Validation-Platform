from __future__ import annotations

import argparse
import io
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
import yaml
from mcap.reader import make_reader
from mcap_ros2.decoder import DecoderFactory

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - exercised on hosts without Pillow.
    Image = None
    ImageDraw = None


COMPRESSED_IMAGE_TYPE = "sensor_msgs/msg/CompressedImage"


@dataclass(frozen=True)
class McapSpan:
    path: Path
    start_ns: int
    end_ns: int


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_topic_name(topic: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", topic.strip("/")) or "topic"


def load_metadata(metadata_path: Path) -> dict[str, Any]:
    with metadata_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def compressed_image_topics(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    topics = (
        metadata.get("rosbag2_bagfile_information", {})
        .get("topics_with_message_count", [])
    )
    rows: list[dict[str, Any]] = []
    for item in topics:
        topic_metadata = item.get("topic_metadata", {})
        if topic_metadata.get("type") != COMPRESSED_IMAGE_TYPE:
            continue
        rows.append(
            {
                "name": topic_metadata.get("name"),
                "type": topic_metadata.get("type"),
                "message_count": int(item.get("message_count") or 0),
            }
        )
    return sorted(rows, key=lambda row: row["name"] or "")


def mcap_spans(mcap_paths: list[Path]) -> list[McapSpan]:
    spans: list[McapSpan] = []
    for path in mcap_paths:
        with path.open("rb") as stream:
            summary = make_reader(stream).get_summary()
        if summary is None or summary.statistics is None:
            continue
        stats = summary.statistics
        spans.append(
            McapSpan(
                path=path,
                start_ns=int(stats.message_start_time),
                end_ns=int(stats.message_end_time),
            )
        )
    return sorted(spans, key=lambda span: (span.start_ns, span.path.name))


def sample_times(start_ns: int, end_ns: int, max_frames: int) -> list[int]:
    if max_frames <= 1:
        return [(start_ns + end_ns) // 2]
    # Avoid the exact endpoints because rosbag2 split boundaries can be sparse.
    span = end_ns - start_ns
    return [int(start_ns + span * ((idx + 0.5) / max_frames)) for idx in range(max_frames)]


def topic_time_span(spans: list[McapSpan], topic: str) -> tuple[int, int] | None:
    first: int | None = None
    last: int | None = None
    for span in spans:
        with span.path.open("rb") as stream:
            reader = make_reader(stream)
            for _, _, message in reader.iter_messages(topics=[topic], log_time_order=True):
                first = int(message.log_time) if first is None else min(first, int(message.log_time))
                break
        with span.path.open("rb") as stream:
            reader = make_reader(stream)
            for _, _, message in reader.iter_messages(topics=[topic], log_time_order=True, reverse=True):
                last = int(message.log_time) if last is None else max(last, int(message.log_time))
                break
    if first is None or last is None:
        return None
    return first, last


def iter_candidate_spans(spans: list[McapSpan], target_ns: int, window_ns: int) -> list[McapSpan]:
    end_ns = target_ns + window_ns
    return [
        span
        for span in spans
        if span.end_ns >= target_ns and span.start_ns <= end_ns
    ]


def first_message_at_or_after(
    spans: list[McapSpan],
    topic: str,
    target_ns: int,
    window_ns: int,
) -> tuple[int, Any] | None:
    best: tuple[int, Any] | None = None
    for span in iter_candidate_spans(spans, target_ns, window_ns):
        with span.path.open("rb") as stream:
            reader = make_reader(stream, decoder_factories=[DecoderFactory()])
            for _, _, message, decoded in reader.iter_decoded_messages(
                topics=[topic],
                start_time=target_ns,
                end_time=min(target_ns + window_ns, span.end_ns),
                log_time_order=True,
            ):
                if best is None or message.log_time < best[0]:
                    best = (int(message.log_time), decoded)
                break
    return best


def image_metrics(jpeg_bytes: bytes) -> dict[str, Any]:
    if Image is None:
        return {
            "width": None,
            "height": None,
            "brightness_mean": None,
            "brightness_std": None,
            "laplacian_variance": None,
            "quality_status": "not_evaluated_pillow_missing",
        }

    with Image.open(io.BytesIO(jpeg_bytes)) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        if max(width, height) > 960:
            scale = 960.0 / max(width, height)
            rgb = rgb.resize((int(width * scale), int(height * scale)))
        gray = np.asarray(rgb.convert("L"), dtype=np.float32)

    center = gray[1:-1, 1:-1]
    laplacian = (
        gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
        - 4.0 * center
    )
    brightness_mean = float(np.mean(gray))
    brightness_std = float(np.std(gray))
    laplacian_variance = float(np.var(laplacian))
    if laplacian_variance < 25.0:
        quality_status = "likely_blurry"
    elif brightness_mean < 35.0 or brightness_mean > 220.0:
        quality_status = "exposure_risk"
    else:
        quality_status = "sample_ok"
    return {
        "width": width,
        "height": height,
        "brightness_mean": round(brightness_mean, 3),
        "brightness_std": round(brightness_std, 3),
        "laplacian_variance": round(laplacian_variance, 3),
        "quality_status": quality_status,
    }


def make_contact_sheet(topic: str, samples: list[dict[str, Any]], output_path: Path) -> None:
    if Image is None or ImageDraw is None or not samples:
        return
    thumb_w = 320
    thumb_h = 180
    label_h = 36
    cols = min(4, max(1, len(samples)))
    rows = int(math.ceil(len(samples) / cols))
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, sample in enumerate(samples):
        row = idx // cols
        col = idx % cols
        x = col * thumb_w
        y = row * (thumb_h + label_h)
        with Image.open(sample["path"]) as image:
            image.thumbnail((thumb_w, thumb_h))
            paste_x = x + (thumb_w - image.width) // 2
            paste_y = y + (thumb_h - image.height) // 2
            sheet.paste(image.convert("RGB"), (paste_x, paste_y))
        label = f"{idx:02d} sharp={sample['metrics'].get('laplacian_variance')}"
        draw.text((x + 6, y + thumb_h + 4), label, fill="black")
        draw.text((x + 6, y + thumb_h + 18), sample["metrics"].get("quality_status", ""), fill="black")
    draw.text((6, 4), topic, fill="white")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=90)


def summarize_topic(samples: list[dict[str, Any]]) -> dict[str, Any]:
    sharpness = [
        sample["metrics"].get("laplacian_variance")
        for sample in samples
        if isinstance(sample["metrics"].get("laplacian_variance"), (int, float))
    ]
    brightness = [
        sample["metrics"].get("brightness_mean")
        for sample in samples
        if isinstance(sample["metrics"].get("brightness_mean"), (int, float))
    ]
    status_counts: dict[str, int] = {}
    for sample in samples:
        status = str(sample["metrics"].get("quality_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "sample_count": len(samples),
        "median_laplacian_variance": round(float(median(sharpness)), 3) if sharpness else None,
        "min_laplacian_variance": round(float(min(sharpness)), 3) if sharpness else None,
        "median_brightness": round(float(median(brightness)), 3) if brightness else None,
        "quality_status_counts": status_counts,
    }


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Reconstruction Frame Sample Report",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- source_bag: `{report['source_bag']}`",
        f"- global_time_span_ns: `{report['global_start_ns']}..{report['global_end_ns']}`",
        f"- requested_samples_per_topic: `{report['requested_samples_per_topic']}`",
        "",
        "## Topic Summary",
        "",
        "| topic | samples | median sharpness | min sharpness | median brightness | status counts | contact sheet |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for topic, summary in report["topic_summaries"].items():
        contact_sheet = summary.get("contact_sheet")
        contact_link = f"[png]({Path(contact_sheet).name})" if contact_sheet else ""
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{topic}`",
                    str(summary["sample_count"]),
                    str(summary["median_laplacian_variance"]),
                    str(summary["min_laplacian_variance"]),
                    str(summary["median_brightness"]),
                    "`" + json.dumps(summary["quality_status_counts"], sort_keys=True) + "`",
                    contact_link,
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `laplacian_variance` is a lightweight focus/sharpness proxy; low values indicate blur risk, not a final reconstruction verdict.",
            "- This sample is for Mac-side triage only. Formal 3DGS training and CARLA-importable mesh generation still belong on the NVIDIA/Ubuntu reconstruction host.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    bag_dir = args.bag_dir.resolve()
    metadata_path = bag_dir / "metadata.yaml"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.yaml not found under {bag_dir}")
    mcap_paths = sorted(bag_dir.glob("*.mcap"))
    if not mcap_paths:
        raise FileNotFoundError(f"no .mcap files found under {bag_dir}")

    output_dir = args.output_dir.resolve()
    frames_dir = output_dir / "frames"
    sheets_dir = output_dir / "contact_sheets"
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    sheets_dir.mkdir(parents=True, exist_ok=True)

    metadata = load_metadata(metadata_path)
    topics = compressed_image_topics(metadata)
    if args.topic:
        requested = set(args.topic)
        topics = [row for row in topics if row["name"] in requested]
    if not topics:
        raise RuntimeError("no sensor_msgs/msg/CompressedImage topics selected")

    spans = mcap_spans(mcap_paths)
    if not spans:
        raise RuntimeError("could not read MCAP time spans")
    global_start = min(span.start_ns for span in spans)
    global_end = max(span.end_ns for span in spans)
    window_ns = int(args.lookup_window_sec * 1_000_000_000)

    report: dict[str, Any] = {
        "generated_at": utc_now(),
        "source_bag": str(bag_dir),
        "output_dir": str(output_dir),
        "global_start_ns": global_start,
        "global_end_ns": global_end,
        "duration_sec": round((global_end - global_start) / 1_000_000_000.0, 3),
        "requested_samples_per_topic": args.max_frames_per_topic,
        "lookup_window_sec": args.lookup_window_sec,
        "topics": topics,
        "topic_summaries": {},
        "samples": {},
    }

    for topic_row in topics:
        topic = topic_row["name"]
        topic_span = topic_time_span(spans, topic)
        if topic_span is None:
            report["samples"][topic] = []
            report["topic_summaries"][topic] = {
                "sample_count": 0,
                "status": "no_messages_for_topic",
            }
            continue
        topic_start_ns, topic_end_ns = topic_span
        targets = sample_times(topic_start_ns, topic_end_ns, args.max_frames_per_topic)
        topic_dir = frames_dir / safe_topic_name(topic)
        topic_dir.mkdir(parents=True, exist_ok=True)
        samples: list[dict[str, Any]] = []
        for index, target_ns in enumerate(targets):
            found = first_message_at_or_after(spans, topic, target_ns, window_ns)
            if found is None:
                continue
            log_time, decoded = found
            jpeg_bytes = bytes(decoded.data)
            stamp = getattr(getattr(decoded, "header", None), "stamp", None)
            msg_stamp_ns = None
            if stamp is not None:
                msg_stamp_ns = int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
            image_path = topic_dir / f"{index:03d}_{log_time}.jpg"
            image_path.write_bytes(jpeg_bytes)
            samples.append(
                {
                    "target_time_ns": target_ns,
                    "log_time_ns": log_time,
                    "message_stamp_ns": msg_stamp_ns,
                    "path": str(image_path),
                    "metrics": image_metrics(jpeg_bytes),
                }
            )

        contact_sheet = sheets_dir / f"{safe_topic_name(topic)}.jpg"
        make_contact_sheet(topic, samples, contact_sheet)
        summary = summarize_topic(samples)
        summary["topic_start_ns"] = topic_start_ns
        summary["topic_end_ns"] = topic_end_ns
        summary["topic_duration_sec"] = round((topic_end_ns - topic_start_ns) / 1_000_000_000.0, 3)
        if contact_sheet.exists():
            summary["contact_sheet"] = str(contact_sheet)
        report["samples"][topic] = samples
        report["topic_summaries"][topic] = summary

    report_path = output_dir / "frame_quality_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown_report(report, output_dir / "frame_quality_report.md")
    print(json.dumps({"report": str(report_path), "output_dir": str(output_dir)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract a time-uniform JPEG frame sample from rosbag2 MCAP files for reconstruction triage."
    )
    parser.add_argument("--bag-dir", type=Path, required=True, help="rosbag2 directory containing metadata.yaml and .mcap files")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for frames, contact sheets, and reports")
    parser.add_argument("--topic", action="append", help="CompressedImage topic to sample. Defaults to all compressed image topics.")
    parser.add_argument("--max-frames-per-topic", type=int, default=12, help="Number of time-uniform samples per selected topic")
    parser.add_argument("--lookup-window-sec", type=float, default=5.0, help="Forward search window for each target timestamp")
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
