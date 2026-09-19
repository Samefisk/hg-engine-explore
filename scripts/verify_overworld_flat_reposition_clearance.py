#!/usr/bin/env python3
"""S1 actual Wild start/wrapper and Hop planner; engine/world queries are stubs."""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import verify_overworld_hop_elevation_arc as arc
from scripts import verify_overworld_motion_start_transaction as start

FIXTURE = ROOT / "tools/overworld/fixtures/flat_reposition_clearance_harness.c"
PLANNER = ROOT / "src/pokemon_move_history_task6_overlay/overworld_actor_hop_planner.c"
WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("flat Reposition fixture seam differs: " + old[:100])
    return source.replace(old, new)


def harness_source():
    # Reuse the existing shell/engine fixture without modifying that file.
    source = start.harness_source()
    marker = "static void RunCase("
    if source.count(marker) != 1:
        raise ValueError("motion-start fixture driver differs")
    source = source[:source.index(marker)]
    source = replace_once(source,
        "typedef struct OverworldWildBehaviorProfileData { u8 walkOptions, hopSwayWidth; } OverworldWildBehaviorProfileData;",
        "typedef struct OverworldWildBehaviorProfileData { u8 walkOptions, hopSwayWidth; "
        "u8 hopTime, hopElevationTimeScale, hopElevationArcScale, hopAllowVerticalObstacles; } OverworldWildBehaviorProfileData;")
    source = replace_once(source,
        "{ static const OverworldWildBehaviorDataBlob blob = {0}; return &blob; }",
        "{ static OverworldWildSurfaceCatalog catalog; "
        "static const OverworldWildBehaviorDataBlob blob = {&catalog}; return &blob; }")
    source = replace_once(source, ".duration = duration, .startX =",
        ".duration = duration, .arcHeightQ4 = state->runtime.movementCustomJumpArcHeightsQ4[slot], .startX =")

    fixture = FIXTURE.read_text()
    if fixture.count("/* @DRIVER@ */") != 1:
        raise ValueError("flat Reposition driver marker differs")
    support, driver = fixture.split("/* @DRIVER@ */")
    header = (ROOT / "include/overworld_actor_system_internal.h").read_text()
    shapes = []
    for kind, name in (("enum", "OverworldActorHopPlanOperation"), ("struct", "OverworldActorHopPlanCall")):
        matches = re.findall(r"typedef " + kind + " " + name + r" \{[^}]*\} " + name + ";", header)
        if len(matches) != 1:
            raise ValueError("expected one production planning value: " + name)
        shapes += matches
    definitions = []
    for path, names in (
        (ROOT / "include/types.h", ("FX32_SHIFT",)),
        (ROOT / "include/overworld_wild_behavior_data.h", ("OW_WILD_BEHAVIOR_JUMP_ARC_HEIGHT_MIN_Q4", "OW_WILD_SURFACE_ID_NATIVE_GROUND")),
        (PLANNER, ("OVERWORLD_HOP_OBSTACLE_CLEARANCE_FX32", "OVERWORLD_HOP_OFFSCREEN_DISTANCE")),
        (WILD, ("OW_WILD_SPAWNER_CHAIN_REPOSITION_SKID", "OW_WILD_SPAWNER_CHAIN_REPOSITION_STEP")),
    ):
        for name in names:
            matches = re.findall(r"^#define " + name + r"\s+[^\n]+$", path.read_text(), re.M)
            if len(matches) != 1:
                raise ValueError("expected one production constant: " + name)
            definitions += matches
    production = PLANNER.read_text()
    substitutions = {
        "/* @TYPES@ */": "\n".join(shapes + definitions),
        "/* @TRAJECTORY@ */": arc.extract_function(arc.SOURCE.read_text(), "OverworldWildBehavior_CalculateJumpTrajectory", "u32"),
        "/* @ARC@ */": arc.extract_function(arc.SOURCE.read_text(), "OverworldWildBehavior_CalculateJumpArc", "s32"),
        "/* @LERP@ */": arc.extract_function(production, "OverworldActorHopPlanner_LerpFx32", "s32"),
        "/* @PLAN@ */": arc.extract_function(production, "OverworldActorHopPlanner_PlanTrajectory", "OverworldMotionDecision"),
        "/* @DISPATCH@ */": arc.extract_function(production, "OverworldActorHopPlanner_PlanImpl", "OverworldMotionDecision"),
        "/* @WRAPPER@ */": arc.extract_function(WILD.read_text(), "OverworldWildSpawns_ResolveHopTrajectory", "OverworldMotionDecision"),
    }
    for marker, body in substitutions.items():
        support = replace_once(support, marker, body)
    stub = arc.extract_function(source, "OverworldWildSpawns_ResolveHopTrajectory", "OverworldMotionDecision")
    return replace_once(source, stub, support) + driver


def known_bad_sources(source):
    body = arc.extract_function(source, "OverworldActorHopPlanner_PlanImpl", "OverworldMotionDecision")
    marker = "if (call->operation == OVERWORLD_ACTOR_HOP_PLAN_VECTOR)"
    yield "lost flat planning mode", replace_once(source, body, replace_once(body, marker,
        "call->operation = OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY;\n    " + marker))
    body = arc.extract_function(source, "OverworldActorHopPlanner_PlanTrajectory", "OverworldMotionDecision")
    yield "skipped raised-surface check", replace_once(source, body,
        replace_once(body, "if (obstacleBaseY <= baseY)", "if (1)"))


def main():
    source = harness_source()
    baseline = start.execute(source)
    print(baseline.stdout + baseline.stderr, end="")
    if baseline.returncode:
        return 1
    for label, mutant in known_bad_sources(source):
        result = start.execute(mutant)
        if result.returncode != 1 or "flat Reposition invariant failed" not in result.stderr:
            raise RuntimeError("known-bad planner was not rejected: " + label)
        print("PASS known-bad planner rejected: " + label)
    print("PASS S1 actual Wild caller/planner clearance; no gameplay claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
