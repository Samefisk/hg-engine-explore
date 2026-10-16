#!/usr/bin/env python3
"""Check actual Wild and Mount Reposition starts against blocked-tile stubs.

This host check does not prove an ARM build or live game behavior.
"""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_overworld_spawn_profile_lifecycle import production_function

FIXTURE = ROOT / "tools/overworld/fixtures/reposition_skid_collision_harness.c"
WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
MOUNT = ROOT / "src/overworld_mount_action_overlay/overworld_mount_action_overlay.c"


def harness_source() -> str:
    source = FIXTURE.read_text()
    for marker, path, name in (
        ("/* @WILD@ */", WILD, "OverworldWildSpawns_RunChainReposition"),
        ("/* @MOUNT@ */", MOUNT, "OverworldMountAction_RunReposition"),
        ("/* @RESET@ */", WILD, "OverworldWildSpawns_ClearWalkMovementState"),
        ("/* @HISTORY@ */", WILD, "OverworldWildSpawns_RecordFinishedMovementHistory"),
    ):
        if source.count(marker) != 1:
            raise ValueError(f"Reposition skid fixture seam differs: {marker}")
        return_type = "u8" if path == MOUNT else (
            "BOOL" if name == "OverworldWildSpawns_RunChainReposition"
            else "void")
        source = source.replace(
            marker, production_function(path.read_text(), name, return_type))
    return source


def execute(source: str, case: int = 0) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="reposition-skid-") as directory:
        unit = Path(directory) / "reposition.c"
        binary = Path(directory) / "reposition"
        unit.write_text(source)
        command = [*shlex.split(os.environ.get("HOST_CC", "cc")),
            "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-function", str(unit), "-o", str(binary)]
        compiled = subprocess.run(command, text=True, capture_output=True)
        if compiled.returncode:
            raise RuntimeError("Reposition skid host compile failed:\n"
                + compiled.stderr)
        return subprocess.run([str(binary), str(case)], text=True,
            capture_output=True)


def main() -> int:
    result = execute(harness_source())
    print(result.stdout + result.stderr, end="")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
