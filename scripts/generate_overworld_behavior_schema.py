#!/usr/bin/env python3
"""Generate C and host metadata from the named Overworld Behavior Schema."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.overworld.behavior_schema import (  # noqa: E402
    BehaviorSchemaError,
    GENERATED_HEADER_PATH,
    GENERATED_METADATA_PATH,
    load_schema,
    write_generated,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if committed outputs are absent or stale")
    args = parser.parse_args()
    try:
        stale = write_generated(load_schema(), check=args.check)
    except BehaviorSchemaError as exc:
        print(f"behavior schema: {exc}", file=sys.stderr)
        return 1
    if stale:
        for path in stale:
            print(f"stale: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1
    verb = "checked" if args.check else "generated"
    print(f"{verb}: {GENERATED_HEADER_PATH.relative_to(ROOT)}")
    print(f"{verb}: {GENERATED_METADATA_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
