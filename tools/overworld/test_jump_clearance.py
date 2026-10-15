"""Host checks for the shared Jump clearance model.

The fixture compiles the production Hop clearance reducer, geometry, height
interpolation and Hop trajectory/arc bodies against a tile grid. It proves the
Jump height rules and arc caps; it does not prove ARM layout or live play.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tools/overworld/fixtures/jump_clearance_harness.c"


def _helper():
    spec = importlib.util.spec_from_file_location(
        "jump_clearance_extract", ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _text(relative):
    return (ROOT / relative).read_text()


def _type(source, name, kind="struct"):
    match = re.search(r"typedef " + kind + " " + name + r"\s*\{.*?\}\s*" + name + ";", source, re.S)
    if match is None:
        raise AssertionError("production type changed: " + name)
    return match.group(0)


def _define(source, name):
    lines = re.findall(r"^#define " + name + r"\b(?:[^\n]*\\\n)*[^\n]*", source, re.M)
    if len(lines) != 1:
        raise AssertionError("expected one production define: " + name)
    return lines[0]


def _function(source, name):
    """Return one top-level definition, including its attributes."""
    match = re.search(r"\n(?:static\s+)?[A-Za-z_][^;{}]*?\b" + re.escape(name)
                      + r"\s*\([^;{}]*\)\s*\{", source)
    if match is None:
        raise AssertionError("production function changed: " + name)
    depth = 1
    for offset in range(match.end(), len(source)):
        depth += (source[offset] == "{") - (source[offset] == "}")
        if depth == 0:
            return source[match.start() + 1:offset + 1]
    raise AssertionError("unterminated production function: " + name)


def harness_source(clearance=None):
    clearance = _text("lib/overworld/overworld_hop_clearance_native.c") if clearance is None else clearance
    internal = _text("include/overworld_actor_system_internal.h")
    native = _text("include/overworld_hop_clearance_native.h")
    hop = _text("include/overworld_actor_hop_clearance.h")
    data = _text("include/overworld_wild_behavior_data.h")
    behavior = _text("src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c")
    helper = _helper()
    prelude = [
        "typedef unsigned char u8; typedef unsigned short u16; typedef unsigned int u32;",
        "typedef signed char s8; typedef short s16; typedef int s32; typedef int BOOL;",
        "#define TRUE 1\n#define FALSE 0",
        "#define OVERWORLD_ACTOR_SYSTEM_HOST 1",
        _define(_text("include/types.h"), "FX32_SHIFT"),
        "typedef struct FieldSystem FieldSystem;",
        "typedef struct LocalMapObject { u32 flags; s32 posVec[3]; } LocalMapObject;",
        "typedef struct OverworldWildSurfaceCatalog OverworldWildSurfaceCatalog;",
        "struct OverworldWildBehaviorProfile;",
        # Only the lane fields the clearance reducer reads.
        "typedef struct OverworldWildBehaviorProfileData { u8 hopAllowVerticalObstacles,"
        " hopMinDistance, hopMaxDistance, jumpLevel, hopTime, spawnHopTime,"
        " hopElevationTimeScale, hopElevationArcScale; } OverworldWildBehaviorProfileData;",
        _type(_text("include/overworld_motion_model.h"), "OverworldMotionDecision", "enum"),
        _type(internal, "OverworldActorHopPlanOperation", "enum"),
        *(_define(internal, name) for name in (
            "OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY",
            "OVERWORLD_ACTOR_HOP_PLAN_FLAG_STRICT_HEIGHT",
            "OVERWORLD_ACTOR_HOP_PLAN_FLAG_SLAM")),
        "struct OverworldActorHopClearanceCursor;",
        _type(internal, "OverworldActorHopPlanCall"),
        _type(_text("src/pokemon_move_history_task6_overlay/overworld_actor_hop_geometry.h"),
              "OverworldActorHopGeometry"),
        _type(data, "OverworldWildSurfaceHit"),
        *(_define(data, name) for name in (
            "OW_WILD_SURFACE_ID_NATIVE_GROUND", "OW_WILD_BEHAVIOR_JUMP_ARC_HEIGHT_MIN_Q4",
            "OW_WILD_BEHAVIOR_SKID_BOOLEAN")),
        *(_define(hop, name) for name in (
            "OVERWORLD_ACTOR_HOP_CLEARANCE_VERSION",
            "OVERWORLD_ACTOR_HOP_CLEARANCE_MAX_READS",
            "OVERWORLD_ACTOR_HOP_CLEARANCE_HEIGHT_READS")),
        _type(hop, "OverworldActorHopClearancePhase", "enum"),
        _type(hop, "OverworldActorHopClearanceCursor"),
        "enum { OVERWORLD_WILD_OCCUPANCY_OBJECTS };",
        "typedef BOOL (*OverworldWildRuntimeQuerySurfaceFunc)(FieldSystem *,"
        " const OverworldWildSurfaceCatalog *, int, int, OverworldWildSurfaceHit *);",
        "typedef BOOL (*OverworldWildRuntimeResolveBaseYAtFunc)(FieldSystem *,"
        " const OverworldWildSurfaceHit *, s32, u32, int, int, s32 *);",
        "typedef u32 (*OverworldWildCalculateJumpTrajectoryFunc)(u8, u8, s32, u16);",
        "typedef s32 (*OverworldWildCalculateJumpArcFunc)(u16, u16, u8);",
        *(_define(native, name) for name in (
            "OVERWORLD_HOP_CLEARANCE_NATIVE_MAGIC", "OVERWORLD_HOP_CLEARANCE_NATIVE_VERSION",
            "OVERWORLD_JUMP_WALL_HEIGHT", "OVERWORLD_JUMP_OBJECT_HEIGHT",
            "OVERWORLD_JUMP_ARC_CAP_2", "OVERWORLD_JUMP_ARC_CAP_3",
            "OVERWORLD_JUMP_ARC_CAP_4",
            "OVERWORLD_JUMP_ARC_CAP")),
        _type(native, "OverworldHopClearanceNativeOps"),
        "typedef struct OverworldQueryCodeAddonEntry { int unused; } OverworldQueryCodeAddonEntry;",
        "const OverworldQueryCodeAddonEntry gOverworldQueryCodeAddonEntry;",
        helper.production_function(behavior, "OverworldWildBehavior_CalculateJumpTrajectory", "u32"),
        helper.production_function(behavior, "OverworldWildBehavior_CalculateJumpArc", "s32"),
        _function(_text("lib/overworld/overworld_motion_model.c"), "OverworldActorHopGeometry_Init"),
        _function(_text("src/pokemon_move_history_overlay/overworld_hop_geometry.c"),
                  "OverworldActorHopGeometry_NextCell"),
        _function(_text("src/pokemon_move_history_overlay/overworld_hop_lerp.c"),
                  "OverworldActorHopPlanner_LerpFx32"),
    ]
    body = re.sub(r"^#(?:include|ifn?def|else|endif)[^\n]*\n", "", clearance, flags=re.M)
    body = re.sub(r"^extern const OverworldQueryCodeAddonEntry[^\n]*\n", "", body, flags=re.M)
    prelude.insert(4, "#define OVERWORLD_MOTION_KIND_HOP " + re.search(
        r"OVERWORLD_MOTION_KIND_HOP\s*=\s*(\d+)", _text("include/overworld_motion_model.h")).group(1))
    # Mach-O host objects cannot use ARM ELF section names.
    prelude = [re.sub(r'section\("[^"]*"\),?\s*', "", part) for part in prelude]
    body = re.sub(r'section\("[^"]*"\),?\s*', "", body)
    source = FIXTURE.read_text()
    if source.count("/* @PRELUDE@ */") != 1:
        raise AssertionError("Jump clearance fixture marker differs")
    return source.replace("/* @PRELUDE@ */", "\n".join(prelude) + "\n" + body)


def run_harness(clearance=None):
    with tempfile.TemporaryDirectory(prefix="jump-clearance-") as directory:
        unit, binary = Path(directory) / "jump.c", Path(directory) / "jump"
        unit.write_text(harness_source(clearance))
        command = [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=gnu11", "-O1", "-w",
                   str(unit), "-o", str(binary)]
        compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if compiled.returncode:
            raise AssertionError("Jump clearance host compile failed:\n" + compiled.stderr)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise AssertionError("Jump clearance harness failed:\n" + result.stderr)
    rows = {}
    for line in result.stdout.splitlines():
        label, accepted, arc = line.split()
        rows[label] = (accepted == "1", int(arc))
    return rows


class JumpClearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = run_harness()

    def accepted(self, label):
        return self.rows[label][0]

    def arc(self, label):
        return self.rows[label][1]

    def test_open_jumps_keep_base_arc(self):
        for distance in (2, 3, 4, 6, 8):
            self.assertEqual(self.rows[f"open-{distance}"], (True, 16))

    def test_wall_needs_a_full_speed_centred_jump(self):
        self.assertFalse(self.accepted("wall-2-1"))
        self.assertFalse(self.accepted("wall-3-1"))
        self.assertFalse(self.accepted("wall-3-2"))
        self.assertTrue(self.accepted("wall-4-2"))
        self.assertLessEqual(self.arc("wall-4-2"), 24)
        self.assertFalse(self.accepted("wall-4-1"), "too-early Jump must crash")
        self.assertFalse(self.accepted("wall-4-3"), "too-late Jump must crash")

    def test_object_clears_at_every_reach_within_the_cap(self):
        for distance in (2, 3, 4):
            for tile in range(1, distance):
                label = f"object-{distance}-{tile}"
                self.assertTrue(self.accepted(label), label)
        self.assertLessEqual(self.arc("object-2-1"), 18)
        self.assertGreater(self.arc("object-4-1"), 16, "an early object raises the arc")
        self.assertLessEqual(self.arc("object-3-1"), 22)
        self.assertLessEqual(self.arc("object-4-1"), 24)

    def test_long_reaches_clear_a_wall_only_mid_flight(self):
        for distance, clear in ((6, (2, 3, 4)), (8, (3, 4, 5))):
            self.assertEqual(self.rows[f"open-{distance}"], (True, 16))
            for tile in range(1, distance):
                label = f"wall-{distance}-{tile}"
                self.assertEqual(self.accepted(label), tile in clear, label)
                if tile in clear:
                    self.assertLessEqual(self.arc(label), 24)

    def test_ledges_pass_downhill_only_unless_both(self):
        self.assertEqual(self.rows["ledge-downhill"], (True, 16))
        self.assertFalse(self.accepted("ledge-uphill"))
        self.assertTrue(self.accepted("ledge-uphill-both"))

    def test_downhill_jump_crosses_a_cliff_face_only(self):
        for distance in (2, 3):
            self.assertEqual(self.rows[f"cliff-down-{distance}"], (True, 16), distance)
        self.assertEqual(self.rows["cliff-thick-down-3"], (True, 16))
        self.assertFalse(self.accepted("tree-down-2"), "a grounded wall stays a wall")
        self.assertFalse(self.accepted("cliff-level-2"), "only a descent crosses a cliff face")

    def test_model_applies_only_to_exact_distance_jump_lanes(self):
        self.assertEqual(self.rows["no-jump-wall"], (True, 16))
        self.assertEqual(self.rows["range-lane-wall"], (True, 16))

    def test_diagonal_jump_crosses_its_diagonal_cell(self):
        self.assertFalse(self.accepted("diagonal-wall-2"))

    def test_missing_cap_is_rejected(self):
        source = _text("lib/overworld/overworld_hop_clearance_native.c")
        old = "if (required > OVERWORLD_JUMP_ARC_CAP(call->distance)) {"
        self.assertEqual(source.count(old), 1)
        rows = run_harness(source.replace(old, "if (required > 0xFF) {"))
        self.assertTrue(rows["wall-2-1"][0], "control: an uncapped arc clears any wall")


if __name__ == "__main__":
    unittest.main()
