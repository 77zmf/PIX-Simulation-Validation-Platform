from __future__ import annotations

import argparse
import json
import shlex
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PYTHON = "/data/pix/reconstruction/venvs/3dgs/bin/python"
DEFAULT_RUNNER = "/data/pix/reconstruction/scripts/run_masked_lidar_gsplat_smoke.py"
DEFAULT_CAMERAS = "front_3mm,front_left,front_right"
DEFAULT_MIN_CAMERA_PSNR = 15.0


PROFILES: dict[str, dict[str, Any]] = {
    "psnr_retrain_high_detail": {
        "iterations": 360,
        "max_frames": 36,
        "max_points": 160000,
        "crop_margin_xy": 100,
        "crop_margin_z": 55,
        "init_scale": 0.9,
        "lr_scale": 0.006,
        "lr_means": 0.0001,
        "notes": [
            "Low PSNR with usable color coverage: increase frames, points, iterations, and allow small mean refinement.",
        ],
    },
    "coverage_repair": {
        "iterations": 420,
        "max_frames": 36,
        "max_points": 160000,
        "crop_margin_xy": 120,
        "crop_margin_z": 55,
        "init_scale": 0.9,
        "lr_scale": 0.006,
        "lr_means": 0.0001,
        "notes": [
            "Rebuild segment inputs with wider camera coverage if colorized ratio remains low after this retrain.",
            "Low image-colorized LiDAR ratio usually means point/image overlap is weak, not just insufficient optimization steps.",
        ],
    },
    "review_refine": {
        "iterations": 240,
        "max_frames": 32,
        "max_points": 120000,
        "crop_margin_xy": 95,
        "crop_margin_z": 50,
        "init_scale": 0.9,
        "lr_scale": 0.008,
        "lr_means": 0.00005,
        "notes": [
            "Review segment: run a lower-cost refinement before spending full budget.",
        ],
    },
    "camera_ablation": {
        "iterations": 180,
        "max_frames": 32,
        "max_points": 120000,
        "crop_margin_xy": 100,
        "crop_margin_z": 55,
        "init_scale": 0.9,
        "lr_scale": 0.008,
        "lr_means": 0.00005,
        "notes": [
            "Camera ablation: isolate whether a camera or camera pair is dragging down static/background 3DGS quality.",
        ],
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def q(value: Any) -> str:
    return shlex.quote(str(value))


def choose_profile(item: dict[str, Any]) -> str:
    colorized_ratio = float(item.get("image_colorized_ratio") or 0.0)
    psnr = float(item.get("psnr") or 0.0)
    status = str(item.get("status") or "")
    if colorized_ratio < 0.90:
        return "coverage_repair"
    if status == "fail" or psnr < 16.0:
        return "psnr_retrain_high_detail"
    return "review_refine"


def priority_key(item: dict[str, Any]) -> tuple[int, float, float, str]:
    status_rank = {"fail": 0, "review": 1, "pass": 2}.get(str(item.get("status")), 3)
    psnr = float(item.get("psnr") or 0.0)
    colorized_ratio = float(item.get("image_colorized_ratio") or 0.0)
    return status_rank, psnr, colorized_ratio, str(item.get("segment_id"))


def _remote_out_dir(remote_output_root: Path, segment_id: str, profile: str) -> Path:
    return remote_output_root / f"{segment_id}_{profile}"


def safe_camera_set_name(camera_set: str) -> str:
    return camera_set.replace(",", "_").replace(" ", "")


def split_camera_set(cameras: str) -> list[str]:
    return [camera.strip() for camera in cameras.split(",") if camera.strip()]


def select_camera_set(item: dict[str, Any], default_cameras: str, camera_policy: str, min_camera_psnr: float) -> str:
    if camera_policy == "fixed":
        return default_cameras
    if camera_policy != "quality-filter":
        raise ValueError(f"unknown camera policy: {camera_policy}")

    camera_scores = {
        str(camera): float(value)
        for camera, value in (item.get("camera_psnr_median", {}) or {}).items()
        if value is not None
    }
    if not camera_scores:
        return default_cameras

    ordered_cameras = split_camera_set(default_cameras)
    selected = [
        camera
        for camera in ordered_cameras
        if camera_scores.get(camera) is not None and camera_scores[camera] >= min_camera_psnr
    ]
    if selected:
        return ",".join(selected)

    best_camera = max(camera_scores, key=camera_scores.get)
    return best_camera


def build_command(
    *,
    python_bin: str,
    runner_path: str,
    segment_dir: str,
    map_ply: str,
    out_dir: Path,
    cameras: str,
    colorize_cameras: str,
    profile: dict[str, Any],
    seed: int,
) -> str:
    pose_prior_json = Path(segment_dir) / "camera_pose_prior_inputs_compat.json"
    parts = [
        "mkdir",
        "-p",
        q(out_dir),
        "&&",
        q(python_bin),
        q(runner_path),
        "--segment-dir",
        q(segment_dir),
        "--pose-prior-json",
        q(pose_prior_json),
        "--map-ply",
        q(map_ply),
        "--out-dir",
        q(out_dir),
        "--cameras",
        q(cameras),
    ]
    if colorize_cameras:
        parts.extend(["--colorize-cameras", q(colorize_cameras)])
    parts.extend([
        "--max-frames",
        str(profile["max_frames"]),
        "--max-points",
        str(profile["max_points"]),
        "--iterations",
        str(profile["iterations"]),
        "--crop-margin-xy",
        str(profile["crop_margin_xy"]),
        "--crop-margin-z",
        str(profile["crop_margin_z"]),
        "--init-scale",
        str(profile["init_scale"]),
        "--lr-scale",
        str(profile["lr_scale"]),
        "--lr-means",
        str(profile["lr_means"]),
        "--seed",
        str(seed),
    ])
    return " ".join(parts)


def build_job(
    *,
    item: dict[str, Any],
    remote_output_root: Path,
    python_bin: str,
    runner_path: str,
    cameras: str,
    colorize_cameras: str,
    camera_policy: str,
    min_camera_psnr: float,
    seed_base: int,
    index: int,
) -> dict[str, Any]:
    manifest_path = Path(str(item["manifest"]))
    source_manifest = read_json(manifest_path)
    segment_dir = source_manifest.get("segment_dir")
    map_ply = source_manifest.get("map_ply")
    if not segment_dir or not map_ply:
        raise ValueError(f"{manifest_path}: missing segment_dir or map_ply")
    profile_name = choose_profile(item)
    profile = PROFILES[profile_name]
    camera_set = select_camera_set(item, cameras, camera_policy, min_camera_psnr)
    out_dir = _remote_out_dir(remote_output_root, str(item["segment_id"]), profile_name)
    command = build_command(
        python_bin=python_bin,
        runner_path=runner_path,
        segment_dir=str(segment_dir),
        map_ply=str(map_ply),
        out_dir=out_dir,
        cameras=camera_set,
        colorize_cameras=colorize_cameras,
        profile=profile,
        seed=seed_base + index,
    )
    return {
        "job_index": index,
        "segment_id": item["segment_id"],
        "status": item.get("status"),
        "psnr": item.get("psnr"),
        "image_colorized_ratio": item.get("image_colorized_ratio"),
        "camera_set": camera_set,
        "colorize_camera_set": colorize_cameras or camera_set,
        "camera_policy": camera_policy,
        "min_camera_psnr": min_camera_psnr,
        "camera_psnr_median": item.get("camera_psnr_median", {}),
        "reasons": item.get("reasons", []),
        "profile": profile_name,
        "notes": profile["notes"],
        "segment_dir": str(segment_dir),
        "map_ply": str(map_ply),
        "out_dir": str(out_dir),
        "command": command,
    }


def build_camera_ablation_job(
    *,
    item: dict[str, Any],
    camera_set: str,
    remote_output_root: Path,
    python_bin: str,
    runner_path: str,
    seed: int,
    index: int,
) -> dict[str, Any]:
    manifest_path = Path(str(item["manifest"]))
    source_manifest = read_json(manifest_path)
    segment_dir = source_manifest.get("segment_dir")
    map_ply = source_manifest.get("map_ply")
    if not segment_dir or not map_ply:
        raise ValueError(f"{manifest_path}: missing segment_dir or map_ply")
    profile_name = "camera_ablation"
    profile = PROFILES[profile_name]
    out_dir = remote_output_root / f"{item['segment_id']}_{safe_camera_set_name(camera_set)}_{profile_name}"
    command = build_command(
        python_bin=python_bin,
        runner_path=runner_path,
        segment_dir=str(segment_dir),
        map_ply=str(map_ply),
        out_dir=out_dir,
        cameras=camera_set,
        colorize_cameras="",
        profile=profile,
        seed=seed,
    )
    return {
        "job_index": index,
        "segment_id": item["segment_id"],
        "status": item.get("status"),
        "psnr": item.get("psnr"),
        "image_colorized_ratio": item.get("image_colorized_ratio"),
        "camera_set": camera_set,
        "camera_psnr_median": item.get("camera_psnr_median", {}),
        "profile": profile_name,
        "notes": profile["notes"],
        "segment_dir": str(segment_dir),
        "map_ply": str(map_ply),
        "out_dir": str(out_dir),
        "command": command,
    }


def render_shell(plan: dict[str, Any]) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Generated reconstruction retrain jobs.",
        "# Gaussian output remains a visual/research layer; CARLA 0.9.15 drivable import remains mesh + OpenDRIVE + collision proxy.",
        "export TORCH_CUDA_ARCH_LIST=${TORCH_CUDA_ARCH_LIST:-8.6}",
        "",
    ]
    for job in plan["jobs"]:
        camera_note = f" cameras={job['camera_set']}" if "camera_set" in job else ""
        lines.append(f"echo '[{job['job_index']}/{plan['job_count']}] {job['segment_id']} profile={job['profile']}{camera_note}'")
        lines.append(job["command"])
        lines.append("")
    return "\n".join(lines)


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Reconstruction Retrain Plan",
        "",
        f"- generated_at: `{plan['generated_at']}`",
        f"- source_quality_gate: `{plan['source_quality_gate']}`",
        f"- job_count: `{plan['job_count']}`",
        f"- remote_output_root: `{plan['remote_output_root']}`",
        f"- cameras: `{plan.get('cameras') or ', '.join(plan.get('camera_sets', []))}`",
        f"- colorize_cameras: `{plan.get('colorize_cameras') or '-'}`",
        f"- camera_policy: `{plan.get('camera_policy', 'fixed')}`",
        f"- min_camera_psnr: `{plan.get('min_camera_psnr', '-')}`",
        f"- status_counts: `{plan['status_counts']}`",
        f"- profile_counts: `{plan['profile_counts']}`",
        "",
        "## Jobs",
        "",
        "| idx | segment | status | psnr | colorized | profile |",
        "| ---: | --- | --- | ---: | ---: | --- |",
    ]
    for job in plan["jobs"]:
        camera_suffix = f" cameras=`{job['camera_set']}`" if "camera_set" in job else ""
        lines.append(
            f"| {job['job_index']} | `{job['segment_id']}` | `{job['status']}` | "
            f"{float(job['psnr']):.3f} | {float(job.get('image_colorized_ratio') or 0.0):.3f} | `{job['profile']}`{camera_suffix} |"
        )
    lines.extend(["", "## Commands", ""])
    for job in plan["jobs"]:
        lines.append(f"### {job['job_index']}. {job['segment_id']}")
        for note in job["notes"]:
            lines.append(f"- {note}")
        lines.append("")
        lines.append("```bash")
        lines.append(job["command"])
        lines.append("```")
        lines.append("")
    lines.extend(
        [
            "## CARLA Boundary",
            "",
            "CARLA 0.9.15 import remains `mesh + OpenDRIVE + collision proxy`. These commands only improve the static/background Gaussian visual layer.",
            "",
        ]
    )
    return "\n".join(lines)


def build_retrain_plan(
    *,
    quality_gate_json: Path,
    output_dir: Path,
    remote_output_root: Path,
    max_jobs: int,
    python_bin: str = DEFAULT_PYTHON,
    runner_path: str = DEFAULT_RUNNER,
    cameras: str = DEFAULT_CAMERAS,
    colorize_cameras: str = "",
    camera_policy: str = "fixed",
    min_camera_psnr: float = DEFAULT_MIN_CAMERA_PSNR,
    seed_base: int = 8200,
) -> dict[str, Any]:
    quality_gate = read_json(quality_gate_json)
    candidates = [
        item
        for item in quality_gate.get("segments", {}).get("items", [])
        if item.get("status") in {"fail", "review"}
    ]
    candidates.sort(key=priority_key)
    if max_jobs > 0:
        candidates = candidates[:max_jobs]
    jobs = [
        build_job(
            item=item,
            remote_output_root=remote_output_root,
            python_bin=python_bin,
            runner_path=runner_path,
            cameras=cameras,
            colorize_cameras=colorize_cameras,
            camera_policy=camera_policy,
            min_camera_psnr=min_camera_psnr,
            seed_base=seed_base,
            index=index,
        )
        for index, item in enumerate(candidates, start=1)
    ]
    plan = {
        "generated_at": utc_now(),
        "source_quality_gate": str(quality_gate_json),
        "remote_output_root": str(remote_output_root),
        "python_bin": python_bin,
        "runner_path": runner_path,
        "cameras": cameras,
        "colorize_cameras": colorize_cameras,
        "camera_policy": camera_policy,
        "min_camera_psnr": min_camera_psnr,
        "job_count": len(jobs),
        "status_counts": dict(Counter(str(job["status"]) for job in jobs)),
        "profile_counts": dict(Counter(str(job["profile"]) for job in jobs)),
        "jobs": jobs,
        "carla_import_boundary": (
            "CARLA 0.9.15 import remains mesh + OpenDRIVE + collision proxy; "
            "these jobs only retrain the Gaussian visual/research layer."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "reconstruction_retrain_plan.json", plan)
    shell_path = output_dir / "run_reconstruction_retrain_jobs.sh"
    shell_path.write_text(render_shell(plan), encoding="utf-8")
    shell_path.chmod(0o755)
    (output_dir / "reconstruction_retrain_plan.md").write_text(render_markdown(plan), encoding="utf-8")
    return plan


def build_camera_ablation_plan(
    *,
    quality_gate_json: Path,
    output_dir: Path,
    remote_output_root: Path,
    camera_sets: list[str],
    max_segments: int,
    python_bin: str = DEFAULT_PYTHON,
    runner_path: str = DEFAULT_RUNNER,
    seed_base: int = 9100,
) -> dict[str, Any]:
    quality_gate = read_json(quality_gate_json)
    candidates = [
        item
        for item in quality_gate.get("segments", {}).get("items", [])
        if item.get("status") in {"fail", "review"}
    ]
    candidates.sort(key=priority_key)
    if max_segments > 0:
        candidates = candidates[:max_segments]

    jobs: list[dict[str, Any]] = []
    for segment_index, item in enumerate(candidates, start=1):
        for camera_index, camera_set in enumerate(camera_sets, start=1):
            jobs.append(
                build_camera_ablation_job(
                    item=item,
                    camera_set=camera_set,
                    remote_output_root=remote_output_root,
                    python_bin=python_bin,
                    runner_path=runner_path,
                    seed=seed_base + (segment_index * 100) + camera_index,
                    index=len(jobs) + 1,
                )
            )

    plan = {
        "generated_at": utc_now(),
        "mode": "camera_ablation",
        "source_quality_gate": str(quality_gate_json),
        "remote_output_root": str(remote_output_root),
        "python_bin": python_bin,
        "runner_path": runner_path,
        "camera_sets": camera_sets,
        "job_count": len(jobs),
        "status_counts": dict(Counter(str(job["status"]) for job in jobs)),
        "profile_counts": dict(Counter(str(job["profile"]) for job in jobs)),
        "jobs": jobs,
        "carla_import_boundary": (
            "CARLA 0.9.15 import remains mesh + OpenDRIVE + collision proxy; "
            "these jobs only isolate Gaussian visual-layer camera quality."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "reconstruction_camera_ablation_plan.json", plan)
    shell_path = output_dir / "run_reconstruction_camera_ablation_jobs.sh"
    shell_path.write_text(render_shell(plan), encoding="utf-8")
    shell_path.chmod(0o755)
    (output_dir / "reconstruction_camera_ablation_plan.md").write_text(render_markdown(plan), encoding="utf-8")
    return plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build retrain commands from a reconstruction quality gate report.")
    parser.add_argument("--quality-gate-json", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--remote-output-root", required=True, type=Path)
    parser.add_argument("--max-jobs", type=int, default=0)
    parser.add_argument("--python-bin", default=DEFAULT_PYTHON)
    parser.add_argument("--runner-path", default=DEFAULT_RUNNER)
    parser.add_argument("--cameras", default=DEFAULT_CAMERAS)
    parser.add_argument("--colorize-cameras", default="")
    parser.add_argument("--camera-policy", choices=["fixed", "quality-filter"], default="fixed")
    parser.add_argument("--min-camera-psnr", type=float, default=DEFAULT_MIN_CAMERA_PSNR)
    parser.add_argument("--seed-base", type=int, default=8200)
    parser.add_argument("--camera-ablation", action="store_true")
    parser.add_argument("--camera-set", action="append", default=[])
    parser.add_argument("--max-segments", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.camera_ablation:
        camera_sets = args.camera_set or [
            "front_left",
            "front_3mm",
            "front_right",
            "front_left,front_right",
            "front_3mm,front_left",
        ]
        plan = build_camera_ablation_plan(
            quality_gate_json=args.quality_gate_json,
            output_dir=args.output_dir,
            remote_output_root=args.remote_output_root,
            camera_sets=camera_sets,
            max_segments=args.max_segments,
            python_bin=args.python_bin,
            runner_path=args.runner_path,
            seed_base=args.seed_base,
        )
        print(json.dumps({"job_count": plan["job_count"], "output_dir": str(args.output_dir)}, indent=2, sort_keys=True))
        return
    plan = build_retrain_plan(
        quality_gate_json=args.quality_gate_json,
        output_dir=args.output_dir,
        remote_output_root=args.remote_output_root,
        max_jobs=args.max_jobs,
        python_bin=args.python_bin,
        runner_path=args.runner_path,
        cameras=args.cameras,
        colorize_cameras=args.colorize_cameras,
        camera_policy=args.camera_policy,
        min_camera_psnr=args.min_camera_psnr,
        seed_base=args.seed_base,
    )
    print(json.dumps({"job_count": plan["job_count"], "output_dir": str(args.output_dir)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
