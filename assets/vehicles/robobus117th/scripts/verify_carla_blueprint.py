#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify that a CARLA blueprint id is available at runtime.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--blueprint-id", default="vehicle.pixmoving.robobus")
    parser.add_argument("--list-prefix", default="")
    args = parser.parse_args(argv)

    try:
        import carla  # type: ignore
    except Exception as exc:
        emit({"ok": False, "stage": "import_carla", "error": str(exc)})
        return 2

    try:
        client = carla.Client(args.host, args.port)
        client.set_timeout(args.timeout)
        world = client.get_world()
        library = world.get_blueprint_library()
    except Exception as exc:
        emit({"ok": False, "stage": "connect", "host": args.host, "port": args.port, "error": str(exc)})
        return 2

    matches = [bp.id for bp in library.filter(args.blueprint_id)]
    prefix_matches: list[str] = []
    if args.list_prefix:
        prefix_matches = [bp.id for bp in library.filter(f"{args.list_prefix}*")]

    ok = args.blueprint_id in matches
    emit(
        {
            "ok": ok,
            "blueprint_id": args.blueprint_id,
            "matches": matches,
            "prefix_matches": prefix_matches,
            "map": world.get_map().name if world.get_map() else None,
        }
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
