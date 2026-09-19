#!/usr/bin/env python3
"""S1 spawn-order regression: real setup bodies, host engine/cache boundaries.

This does not prove the real resolver, ARM ABI, or gameplay. The normal-play
Ledyba scenario must separately prove the public profile and full spawn motion.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


def production_function(source: str, name: str, result_type: str) -> str:
    # Require a static definition, not a same-named call in an if condition.
    matches = list(re.finditer(r"\bstatic\s+" + result_type + r"\b[^;{}]*?\b"
                              + re.escape(name) + r"\s*\([^;{}]*\)\s*\{", source))
    if len(matches) != 1:
        raise ValueError(f"expected one production definition: {name}")
    match = matches[0]
    start = source.index(name, match.start(), match.end())
    depth = 1
    for offset in range(match.end(), len(source)):
        depth += (source[offset] == "{") - (source[offset] == "}")
        if depth == 0:
            return f"static {result_type} " + source[start:offset + 1]
    raise ValueError(f"unterminated production function: {name}")


def harness_source(root: Path, fixture: Path) -> str:
    helper_path = root / "scripts/verify_overworld_actor_view.py"
    spec = importlib.util.spec_from_file_location("spawn_actor_view_extract", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    path = root / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
    wild = path.read_text()
    constants = helper.engine_constants()
    for name in (
        "OW_WILD_BEHAVIOR_LOCOMOTION_NONE",
        "OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN",
        "OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN",
        "OW_WILD_BEHAVIOR_LOCOMOTION_APPEAR_HOP",
        "OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK",
        "OW_WILD_SPAWNER_MANKEY_TREE_TOP_RENDER_OVERRIDE_SAVE_ENABLED",
        "OW_WILD_SPAWNER_MANKEY_TREE_TOP_DRAW_CALLBACK_OVERRIDE_ENABLED",
    ):
        matches = re.findall(r"^#define " + name + r"\s+[^\n]+$", wild, re.M)
        if len(matches) != 1:
            raise ValueError(f"missing production constant: {name}")
        constants += "\n" + matches[0]
    header = (root / "include/overworld_wild_spawns_internal.h").read_text()
    constants += "\n" + re.search(r"^#define OW_WILD_OBJECT_ID_START\s+[^\n]+$", header, re.M).group(0)
    substitutions = {
        "/* @CONSTANTS@ */": constants,
        "/* @INIT_SLOT@ */": production_function(wild, "OverworldWildSpawns_InitSpawnSlotState", "void"),
        "/* @STARTUP@ */": production_function(wild, "OverworldWildSpawns_StartSpawnStartup", "BOOL"),
    }
    source = fixture.read_text()
    for marker, value in substitutions.items():
        if source.count(marker) != 1:
            raise ValueError(f"harness marker differs: {marker}")
        source = source.replace(marker, value)
    return source


def execute(root: Path, source: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="overworld-spawn-profile-") as directory:
        work = Path(directory)
        unit, binary = work / "spawn.c", work / "spawn"
        unit.write_text(source)
        command = [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2",
                   "-Wall", "-Wextra", "-Werror", "-DOVERWORLD_ACTOR_SYSTEM_HOST",
                   "-I", str(root / "include"), str(unit), "-o", str(binary)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        if compiled.returncode:
            raise RuntimeError("spawn lifecycle host compile failed:\n" + compiled.stderr)
        return subprocess.run([str(binary)], cwd=work, capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--fixture", type=Path)
    args = parser.parse_args()
    fixture = args.fixture or args.repo / "tools/overworld/fixtures/spawn_profile_lifecycle_harness.c"
    source = harness_source(args.repo, fixture)
    baseline = execute(args.repo, source)
    print(baseline.stdout + baseline.stderr, end="")
    if baseline.returncode:
        return 1
    mutations = {
        "profile lookup before bind": (
            "OverworldActorHandle handle;",
            "OverworldActorHandle handle; HarnessProfileLookup(slot);"),
        "duplicate actor bind": (
            "OverworldWildSpawns_ApplySpawnPassThroughFlag(\n        state, slot, state->spawns[slot].object);",
            "(void)OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->bindActor(fieldSystem, state, slot, &handle);\n"
            "    OverworldWildSpawns_ApplySpawnPassThroughFlag(\n        state, slot, state->spawns[slot].object);"),
        "missing prepared profile reuse": (
            "OverworldWildSpawns_SeedPreparedBehaviorProfile(\n"
            "        state,\n"
            "        slot,\n"
            "        prepared);",
            "(void)prepared;"),
        "missing failed-hop unbind": (
            "(void)OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->unbind(",
            "(void)HARNESS_SKIP_UNBIND("),
        "wrong failed-hop handle": (
            "&handle,\n            OVERWORLD_ACTOR_REASON_CONTEXT_LOST",
            "&(OverworldActorHandle){.slot = 9, .generation = 1},\n            OVERWORLD_ACTOR_REASON_CONTEXT_LOST"),
    }
    rejection = re.search(
        r"(if\s*\(!OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->bindActor\([^;{}]+\)\)\s*\{)(\s*return FALSE;)", source)
    if rejection is None:
        raise ValueError("production rejected-bind branch changed")
    mutations["unbind previous actor on rejection"] = (
        rejection.group(0), rejection.group(1)
        + "\n        (void)OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->unbind("
        + "&(OverworldActorHandle){0}, OVERWORLD_ACTOR_REASON_CONTEXT_LOST);"
        + rejection.group(2))
    for label, (old, new) in mutations.items():
        if source.count(old) != 1:
            raise ValueError(f"production mutation seam changed: {label}")
        mutant = execute(args.repo, source.replace(old, new))
        if mutant.returncode != 1 or "spawn profile invariant failed" not in mutant.stderr:
            raise RuntimeError(f"known-bad spawn did not fail an assertion: {label}")
        print(f"PASS known-bad spawn rejected: {label}")
    print("PASS S1 spawn profile lifecycle; engine/cache stubs, no gameplay claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
