#!/usr/bin/env python3
"""S1 real motion-start body with stock-command stubs and real Motion admission.

This proves host-side start/rejection ownership, not ARM ABI or live gameplay.
"""
from pathlib import Path
import importlib.util
import os
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
FIXTURE = ROOT / "tools/overworld/fixtures/motion_start_transaction_harness.c"


def harness_source():
    spec = importlib.util.spec_from_file_location("motion_start_extract", ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py")
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    production = SOURCE.read_text()
    definitions = {}
    for path in (SOURCE, ROOT / "include/overworld_wild_behavior_data.h",
                 ROOT / "include/map_events_internal.h", ROOT / "include/constants/sndseq.h"):
        normalized = path.read_text().replace("\\\n", " ")
        for name, line in re.findall(r"^(#define\s+([A-Za-z_]\w*)[^\n]*)$", normalized, re.M):
            definitions[line] = name
    needed = set()
    def constant(name):
        if name in needed:
            return
        if name not in definitions:
            raise ValueError("missing production macro " + name)
        needed.add(name)
        for token in re.findall(r"\b(?:OW_WILD_|BIT_|SEQ_SE_)[A-Z_0-9]+\b", definitions[name].split(name, 1)[1]):
            if token != name:
                constant(token)
    for name in (
        "OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING", "OW_WILD_SPAWNER_CHAIN_REPOSITION_FLAT_MASK",
        "OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER", "OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER_MASK",
        "OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT", "OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT",
        "OW_WILD_BEHAVIOR_WALK_PRESERVES_FACING",
        "OW_WILD_SPAWNER_CUSTOM_MOTION_WALK_FLAG", "OW_WILD_SPAWNER_CUSTOM_JUMP_SPIN_SPEED_MASK",
        "OW_WILD_SPAWNER_CUSTOM_JUMP_OWNED_BITS", "BIT_VANISH",
        "OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_PREP_COMMAND", "OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND",
        "OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND", "OW_WILD_CUSTOM_MOTION_NONE",
        "OW_WILD_CUSTOM_MOTION_WALK", "OW_WILD_CUSTOM_MOTION_JUMP", "OW_WILD_SPAWNER_SPOT_EMOTE_SE",
        "OW_WILD_SPAWNER_HOP_START_SE", "OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK",
        "OW_WILD_SPAWNER_MOVEMENT_BURST_UPDATE_STEPS"):
        constant(name)
    source = FIXTURE.read_text()
    substitutions = {
        "/* @CONSTANTS@ */": "\n".join(definitions[name] for name in sorted(needed)),
        "/* @IMMEDIATE@ */": extract.production_function(production, "OverworldWildSpawns_RunImmediateCanopyMovementCommand", "BOOL"),
        "/* @START@ */": extract.production_function(production, "OverworldWildSpawns_StartPreparedCustomJumpCommandTimed", "OverworldMotionDecision"),
    }
    for marker, value in substitutions.items():
        if source.count(marker) != 1:
            raise ValueError("fixture marker differs: " + marker)
        source = source.replace(marker, value)
    return source


def execute(source):
    with tempfile.TemporaryDirectory(prefix="motion-start-transaction-") as directory:
        root = Path(directory)
        unit, binary = root / "start.c", root / "start"
        unit.write_text(source)
        command = [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                   "-Wno-unused-function", "-DOVERWORLD_MOTION_HOST", "-I", str(ROOT / "include"),
                   str(unit), str(ROOT / "lib/overworld/overworld_motion_model.c"), "-o", str(binary)]
        compiled = subprocess.run(command, text=True, capture_output=True)
        if compiled.returncode:
            raise RuntimeError("motion transaction host compile failed:\n" + compiled.stderr)
        return subprocess.run([str(binary)], text=True, capture_output=True)


def mutate_start_body(source, old, new):
    signature = "static OverworldMotionDecision OverworldWildSpawns_StartPreparedCustomJumpCommandTimed("
    if source.count(signature) != 1:
        raise ValueError("extracted production start signature differs")
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 1
    for end in range(brace + 1, len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            body = source[start:end + 1]
            if body.count(old) != 1:
                raise ValueError("production start mutation seam differs: " + old)
            return source[:start] + body.replace(old, new) + source[end + 1:]
    raise ValueError("unterminated extracted production start")


def main():
    source = harness_source()
    baseline = execute(source)
    print(baseline.stdout + baseline.stderr, end="")
    if baseline.returncode:
        return 1
    # Negative controls alter extracted production statements, never expectations.
    mutations = {
        "orphan shell on rejection": (
            "OverworldWildSpawns_ClearCustomJumpLocal(state, slot);",
            "OverworldWildSpawns_ClearCustomJumpLocal(state, slot);\n"
            "        MapObject_StartMovementCommand(object, OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND);\n"
            "        MapObject_SetSingleMovementActive(object);"),
        "missing successful controller owner": (
            "OverworldWildSpawns_SetMovementSlotInProgress(state, slot);",
            "(void)state; (void)slot;"),
        "cancel preceding motion on rejection": (
            "if (policy.motionPhase != OVERWORLD_MOTION_PHASE_IDLE",
            "OverworldMotion_Reset(&motion);\n    if (policy.motionPhase != OVERWORLD_MOTION_PHASE_IDLE"),
        "prepare before owner readiness": (
            "if (policy.motionPhase != OVERWORLD_MOTION_PHASE_IDLE\n"
            "        && policy.motionPhase != OVERWORLD_MOTION_PHASE_CANCELED)",
            "if (FALSE)"),
        "sound effect before admission": (
            "reason = OverworldWildSpawns_BeginSharedMotion(",
            "StopSE(OW_WILD_SPAWNER_SPOT_EMOTE_SE);\n    reason = OverworldWildSpawns_BeginSharedMotion("),
        "rejected prep remains owned": (
            "runtime->movementCustomJumpPrepActive[slot] = FALSE;",
            "runtime->movementCustomJumpPrepActive[slot] = TRUE;"),
    }
    for label, (old, new) in mutations.items():
        mutant = execute(mutate_start_body(source, old, new))
        if mutant.returncode != 1 or "motion start invariant failed" not in mutant.stderr:
            raise RuntimeError("known-bad transaction was not rejected: " + label)
        print("PASS known-bad transaction rejected: " + label)
    print("PASS S1 motion-start transaction; engine stubs, no gameplay claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
