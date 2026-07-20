#!/usr/bin/env python3
"""Create a NARC at a sibling temporary path, then publish it atomically."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--narcpy", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{args.output.name}.",
        suffix=".tmp",
        dir=args.output.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    try:
        subprocess.run(
            [
                sys.executable,
                str(args.narcpy),
                "create",
                str(temporary),
                str(args.source),
                "-nf",
            ],
            check=True,
        )
        os.replace(temporary, args.output)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
