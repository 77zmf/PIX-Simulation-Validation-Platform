from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def find_ffmpeg(repo_root: Path) -> str | None:
    local_ffmpeg = repo_root / ".local_tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
    if local_ffmpeg.is_file():
        return str(local_ffmpeg)
    return shutil.which("ffmpeg")


def extract_frames(video_path: Path, output_dir: Path, fps: float, max_width: int, overwrite: bool) -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[1]
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "frame_%06d.jpg"
    report = {
        "generated_at": _utc_now(),
        "video_path": str(video_path),
        "output_dir": str(output_dir),
        "fps": fps,
        "max_width": max_width,
        "ffmpeg": None,
        "passed": False,
        "frame_count": 0,
        "error": None,
    }
    if not video_path.is_file():
        report["error"] = f"video not found: {video_path}"
        return report

    ffmpeg = find_ffmpeg(repo_root)
    report["ffmpeg"] = ffmpeg
    if not ffmpeg:
        report["error"] = "ffmpeg not found"
        return report

    scale = f"scale='min({max_width},iw)':-2"
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if overwrite else "-n",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps},{scale}",
        "-q:v",
        "2",
        str(pattern),
    ]
    try:
        completed = subprocess.run(command, check=False, text=True, capture_output=True)
        if completed.returncode != 0:
            report["error"] = completed.stderr.strip() or completed.stdout.strip() or f"ffmpeg exited {completed.returncode}"
            return report
        frame_count = len(list(output_dir.glob("frame_*.jpg")))
        report["frame_count"] = frame_count
        report["passed"] = frame_count > 0
        if not report["passed"]:
            report["error"] = "ffmpeg completed but no frames were written"
    except Exception as exc:
        report["error"] = str(exc)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract reconstruction frames from a video using local FFmpeg")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/qiyu_loop/images"))
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--max-width", type=int, default=1920)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    report = extract_frames(args.video, args.output_dir, args.fps, args.max_width, args.overwrite)
    report_path = args.output_dir / "frame_extraction_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "json": str(report_path), "frame_count": report["frame_count"], "error": report["error"]}, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
