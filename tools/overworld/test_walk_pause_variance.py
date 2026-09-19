#!/usr/bin/env python3
"""Verify deterministic Walk pause variance and its motion-request routing."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"

HARNESS = r"""
#include "overworld_motion_model.h"

static int Check(int condition)
{
    return condition ? 0 : 1;
}

int main(void)
{
    unsigned int sequence;
    int sawMinimum = 0;
    int sawMaximum = 0;

    if (Check(OverworldMotion_ApplyWalkPauseVariance(6, 0, 91) == 6)) {
        return 1;
    }
    for (sequence = 0; sequence < 256; sequence++) {
        unsigned char first = OverworldMotion_ApplyWalkPauseVariance(
            0, 6, sequence);

        if (Check(first <= 6)) {
            return 2;
        }
        sawMinimum |= first == 0;
        sawMaximum |= first == 6;
        if (Check(first == OverworldMotion_ApplyWalkPauseVariance(
                0, 6, sequence))) {
            return 3;
        }
    }
    if (Check(sawMinimum && sawMaximum)) {
        return 4;
    }
    for (sequence = 0; sequence < 256; sequence++) {
        if (OverworldMotion_ApplyWalkPauseVariance(250, 32, sequence)
                == 255) {
            return 0;
        }
    }
    return 5;
}
"""


def function_body(source: str, name: str) -> str:
    start = source.index(name)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise AssertionError(f"unterminated function {name}")


def main() -> int:
    source = RUNTIME.read_text(encoding="utf-8")
    request = function_body(source, "OverworldWildRuntime_RequestMotion")
    varied = request.index("OverworldWildSpawns_ResolveWalkPause")
    dispatch = request.index("OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request")
    if not varied < dispatch:
        raise AssertionError(
            "Walk pause variance must be carried into the shared motion request"
        )
    walk_guard = request.rfind("kind == OVERWORLD_MOTION_KIND_WALK", 0, varied)
    if walk_guard < 0:
        raise AssertionError("Hop or Reposition plans can receive Walk pause variance")

    compiler = os.environ.get("CC", "cc")
    with tempfile.TemporaryDirectory(prefix="walk-pause-variance-") as temp_dir:
        executable = Path(temp_dir) / "walk_pause_variance"
        completed = subprocess.run(
            [
                compiler,
                "-std=c99",
                "-Wall",
                "-Wextra",
                "-I",
                str(ROOT / "include"),
                "-x",
                "c",
                "-",
                "-o",
                str(executable),
            ],
            input=HARNESS,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr.strip())
        run = subprocess.run(
            [str(executable)],
            capture_output=True,
            text=True,
            check=False,
        )
        if run.returncode != 0:
            raise AssertionError(
                f"Walk pause variance harness failed with code {run.returncode}"
            )

    print("Walk pause variance formula and shared-motion routing verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
