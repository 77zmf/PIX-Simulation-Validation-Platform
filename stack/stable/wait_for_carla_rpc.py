#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def add_carla_python_paths(carla_root: str) -> None:
    root = Path(carla_root).expanduser()
    candidates = [
        root / "PythonAPI" / "carla" / "dist" / "carla-0.9.15-py3.10-linux-x86_64.egg",
        root / "PythonAPI" / "carla",
    ]
    for candidate in reversed(candidates):
        sys.path.insert(0, str(candidate))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wait until CARLA Python RPC is usable.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout-sec", type=float, default=90.0)
    parser.add_argument("--attempt-timeout-sec", type=float, default=5.0)
    parser.add_argument("--poll-sec", type=float, default=1.0)
    parser.add_argument("--carla-root", default="$HOME/CARLA_0.9.15")
    args = parser.parse_args(argv)

    carla_root = args.carla_root.replace("$HOME", str(Path.home()))
    add_carla_python_paths(carla_root)

    try:
        import carla  # type: ignore
    except Exception as exc:
        emit({"ok": False, "stage": "import_carla", "carla_root": carla_root, "error": str(exc)})
        return 2

    deadline = time.monotonic() + args.timeout_sec
    attempts = 0
    last_error = ""
    while time.monotonic() <= deadline:
        attempts += 1
        try:
            client = carla.Client(args.host, args.port)
            client.set_timeout(args.attempt_timeout_sec)
            world = client.get_world()
            world_map = world.get_map()
            emit(
                {
                    "ok": True,
                    "host": args.host,
                    "port": args.port,
                    "attempts": attempts,
                    "map": world_map.name if world_map else None,
                }
            )
            return 0
        except Exception as exc:
            last_error = str(exc)
            time.sleep(args.poll_sec)

    emit(
        {
            "ok": False,
            "stage": "connect",
            "host": args.host,
            "port": args.port,
            "attempts": attempts,
            "timeout_sec": args.timeout_sec,
            "error": last_error or "carla_rpc_unavailable",
        }
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
