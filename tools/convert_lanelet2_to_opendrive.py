from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from simctl.lanelet_opendrive import (  # noqa: E402
    add_lanelet_to_opendrive_arguments,
    conversion_result_payload,
    convert_from_args,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert a Lanelet2 local-coordinate OSM file to first-pass OpenDRIVE")
    add_lanelet_to_opendrive_arguments(parser)
    result = convert_from_args(parser.parse_args(argv))
    print(json.dumps(conversion_result_payload(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
