#!/usr/bin/env python3
"""S1 check: execute the production actor-view refresh with host engine stubs.

The real public snapshot layout and actual function bodies are compiled. The
engine boundary is stubbed; this is not ARM ABI, packaged ROM, or gameplay proof.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
ACTOR = ROOT / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c"
FIXTURE = ROOT / "tools/overworld/fixtures/actor_view_harness.c"


def production_function(path: Path, name: str) -> str:
    source = path.read_text()
    matches = list(re.finditer(r"\b" + re.escape(name) + r"\s*\([^;{}]*\)\s*\{", source))
    if len(matches) != 1:
        raise ValueError(f"expected one production definition of {name}")
    match = matches[0]
    depth = 1
    for offset in range(match.end(), len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                # Return attributes affect ARM placement/optimization only.
                # Every statement in the function body remains unchanged.
                return "static void " + source[match.start():offset + 1]
    raise ValueError(f"unterminated production function {name}")


def engine_constants() -> str:
    groups = {
        "include/overworld_wild_spawns_internal.h": (
            "OW_WILD_LAND_SURF_MAX_SPAWNS", "OW_WILD_HEADBUTT_MAX_SPAWNS",
            "OW_WILD_FISH_MAX_SPAWNS", "OW_WILD_HEADBUTT_SLOT_START",
            "OW_WILD_FISH_SLOT_START", "OW_WILD_FOLLOWER_SLOT", "OW_WILD_MAX_SPAWNS",
        ),
        "include/overworld_wild_movement.h": ("OW_WILD_SPAWNER_SPOT_STATE_CHILL",
            "OW_WILD_SPAWNER_SPOT_STATE_EMOTING", "OW_WILD_SPAWNER_SPOT_STATE_RESERVED",
            "OW_WILD_SPAWNER_SPOT_STATE_TIRED"),
        "include/map_events_internal.h": ("BIT_VANISH",),
    }
    resolver = (ROOT / "include/overworld_behavior_resolver.h").read_text()
    enums = re.findall(r"typedef enum BehaviorResolutionLane\s*\{[^}]+\}\s*BehaviorResolutionLane;", resolver)
    if len(enums) != 1:
        raise ValueError("expected one public BehaviorResolutionLane enum")
    lines = [enums[0]]
    for relative, names in groups.items():
        source = (ROOT / relative).read_text()
        for name in names:
            matches = re.findall(r"^#define " + name + r"\s+[^\n]+$", source, re.M)
            if len(matches) != 1 or matches[0].endswith("\\"):
                raise ValueError(f"cannot import production constant {name}")
            lines.append(matches[0])
    return "\n".join(lines)


def harness_source() -> str:
    source = FIXTURE.read_text()
    substitutions = {
        "/* @ENGINE_CONSTANTS@ */": engine_constants(),
        "/* @FILL_ACTOR_VIEW@ */": production_function(RUNTIME, "OverworldWildRuntime_FillActorView"),
        "/* @SYNC_ACTOR_VIEW@ */": production_function(ACTOR, "ActorSystem_SyncLegacyActor"),
    }
    for marker, value in substitutions.items():
        if source.count(marker) != 1:
            raise ValueError(f"harness marker differs: {marker}")
        source = source.replace(marker, value)
    return source


def execute(source: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="overworld-actor-view-") as directory:
        temporary = Path(directory)
        unit = temporary / "actor-view.c"
        binary = temporary / "actor-view"
        unit.write_text(source)
        command = [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2",
                   "-Wall", "-Wextra", "-Werror", "-DOVERWORLD_ACTOR_SYSTEM_HOST",
                   "-DOVERWORLD_MOTION_HOST", "-I", str(ROOT / "include"),
                   str(unit), "-o", str(binary)]
        compiled = subprocess.run(command, capture_output=True, text=True, check=False)
        if compiled.returncode:
            raise RuntimeError("actor-view host compile failed:\n" + compiled.stdout + compiled.stderr)
        return subprocess.run([str(binary)], capture_output=True, text=True, check=False)


def main() -> int:
    source = harness_source()
    baseline = execute(source)
    if baseline.returncode:
        print(baseline.stdout + baseline.stderr, end="")
        return 1
    print(baseline.stdout, end="")
    # These mutate the compiled production statements, not the expected values.
    # A test that cannot detect these known wrong refreshes is not useful proof.
    mutations = {
        "commit reset": ("view->active = spawn->active;", "view->active = spawn->active; view->commitSequence = 0;"),
        "unseeded refresh": ("view = *current;", "memset(&view, 0, sizeof(view));"),
        "stale mounted input": ("view->inputOwnership = mounted;", "if (mounted) view->inputOwnership = TRUE;"),
        "wrong mounted anchor": ("if (mounted && fieldSystem->playerAvatar != NULL)", "if (FALSE && fieldSystem->playerAvatar != NULL)"),
    }
    for label, (old, new) in mutations.items():
        if source.count(old) != 1:
            raise ValueError(f"production mutation seam changed: {label}")
        mutant = execute(source.replace(old, new))
        if mutant.returncode != 1 or "actor view invariant failed" not in mutant.stderr:
            raise RuntimeError(f"actor-view known-bad case did not fail its assertion: {label}")
        print(f"PASS known-bad refresh rejected: {label}")
    print("PASS S1 actor view preservation; engine stubs, no gameplay claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
