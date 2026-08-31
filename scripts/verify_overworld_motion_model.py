#!/usr/bin/env python3
"""Build and run the deterministic host proof for the shared motion model."""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    compiler = shlex.split(os.environ.get("CC", "cc"))
    if not compiler:
        raise SystemExit("CC must name a C compiler")
    with tempfile.TemporaryDirectory(prefix="overworld-motion-") as directory:
        executable = Path(directory) / "overworld-motion-model"
        command = compiler + [
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pedantic",
            "-DOVERWORLD_MOTION_HOST=1",
            "-I",
            str(ROOT / "include"),
            str(ROOT / "lib/overworld/overworld_motion_model.c"),
            str(ROOT / "tools/overworld_motion_model_harness.c"),
            "-o",
            str(executable),
        ]
        subprocess.run(command, cwd=ROOT, check=True, timeout=30)
        subprocess.run([str(executable)], cwd=ROOT, check=True, timeout=30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
