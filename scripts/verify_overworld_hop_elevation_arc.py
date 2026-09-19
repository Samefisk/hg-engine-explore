#!/usr/bin/env python3
"""S1 real Hop trajectory/arc bodies; no engine, ARM ABI, or gameplay claim."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c"
FIXTURE = ROOT / "tools/overworld/fixtures/hop_elevation_arc_harness.c"


def extract_function(source, name, result_type):
    spec = importlib.util.spec_from_file_location(
        "hop_arc_extract", ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper.production_function(source, name, result_type)


def harness_source(production=None):
    production = SOURCE.read_text() if production is None else production
    constants = []
    for path, name in (
        (ROOT / "include/types.h", "FX32_SHIFT"),
        (ROOT / "include/overworld_wild_behavior_data.h", "OW_WILD_BEHAVIOR_JUMP_ARC_HEIGHT_MIN_Q4"),
    ):
        lines = re.findall(r"^#define " + name + r"\s+[^\n]+$", path.read_text(), re.M)
        if len(lines) != 1:
            raise ValueError("expected one production constant: " + name)
        constants.extend(lines)
    source = FIXTURE.read_text()
    substitutions = {
        "/* @CONSTANTS@ */": "\n".join(constants),
        "/* @TRAJECTORY@ */": extract_function(production, "OverworldWildBehavior_CalculateJumpTrajectory", "u32"),
        "/* @ARC@ */": extract_function(production, "OverworldWildBehavior_CalculateJumpArc", "s32"),
    }
    for marker, value in substitutions.items():
        if source.count(marker) != 1:
            raise ValueError("Hop arc fixture marker differs: " + marker)
        source = source.replace(marker, value)
    return source


def execute(source):
    with tempfile.TemporaryDirectory(prefix="hop-elevation-arc-") as directory:
        root = Path(directory)
        unit, binary = root / "arc.c", root / "arc"
        unit.write_text(source)
        command = [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2",
                   "-Wall", "-Wextra", "-Werror", "-DOVERWORLD_MOTION_HOST",
                   "-I", str(ROOT / "include"), str(unit),
                   str(ROOT / "lib/overworld/overworld_motion_model.c"), "-o", str(binary)]
        compiled = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if compiled.returncode:
            raise RuntimeError("Hop elevation arc host compile failed:\n" + compiled.stderr)
        return subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)


def known_bad_sources(source):
    name = "OverworldWildBehavior_CalculateJumpTrajectory"
    body = extract_function(source, name, "u32")
    tail = "return (arcHeightQ4 << 16) | frameCount;"
    mutations = {
        "old zero-scale conditional": (tail, "if ((packedElevationScales >> 8) == 0) arcHeightQ4 = 0;\n    " + tail),
        "missing base arc": (tail, "if (arcHeightQ4 >= 16) arcHeightQ4 -= 16;\n    " + tail),
        "wrong elevation sign": ("elevationDelta = -elevationDelta;", "elevationDelta = 0;"),
        "missing arc clamp": ("arcHeightQ4 = 0xFF;", "(void)arcHeightQ4;"),
        "missing duration clamp": ("frameCount = 0xFFFF;", "(void)frameCount;"),
    }
    for label, (old, new) in mutations.items():
        if body.count(old) != 1 or source.count(body) != 1:
            raise ValueError("Hop arc production mutation seam differs: " + label)
        yield label, source.replace(body, body.replace(old, new))


def main():
    source = harness_source()
    baseline = execute(source)
    print(baseline.stdout + baseline.stderr, end="")
    if baseline.returncode:
        return 1
    for label, mutant_source in known_bad_sources(source):
        mutant = execute(mutant_source)
        if mutant.returncode != 1 or "Hop arc invariant failed" not in mutant.stderr:
            raise RuntimeError("known-bad Hop trajectory was not rejected: " + label)
        print("PASS known-bad trajectory rejected: " + label)
    print("PASS S1 actual Hop helper and portable renderer; no gameplay claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
