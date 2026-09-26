"""Focused host proof for PB4 Fly In motion and spawn integration."""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPAWNS = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
RUNTIME = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"


def function(source, name):
    matches = [
        match
        for match in re.finditer(
            r"\b" + name + r"\s*\([^;{}]*\)\s*\{", source
        )
        if source[source.rfind("\n", 0, match.start()) + 1:match.start()].startswith(
            "static "
        )
        or not source[
            source.rfind("\n", 0, match.start()) + 1:match.start()
        ]
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one {name} body")
    start = matches[0]
    depth = 1
    for end in range(start.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return source[start.start():end + 1]
    raise AssertionError(f"unterminated {name} body")


HARNESS = r"""
#include <assert.h>
#include <string.h>
#include "overworld_motion_model.h"

#define FLY_IN_DURATION 144
#define TILE_FX32 (16 * (1 << 12))
#define FLY_IN_HEIGHT (6 * TILE_FX32)

static void RunDescent(s32 targetBaseY)
{
    OverworldMotionIntent intent;
    OverworldMotionCandidate candidate;
    OverworldMotionPlan plan;
    OverworldMotionState state;
    OverworldMotionSample sample;
    OverworldMotionDecision decision;
    s32 previousBaseY;
    u16 flags;
    u16 frame;
    u8 selected = 0xFF;

    memset(&intent, 0, sizeof(intent));
    memset(&candidate, 0, sizeof(candidate));
    memset(&plan, 0, sizeof(plan));
    memset(&state, 0, sizeof(state));
    intent.version = OVERWORLD_MOTION_MODEL_VERSION;
    intent.kind = OVERWORLD_MOTION_KIND_FLY_IN;
    intent.facing = 3;
    intent.fieldEpoch = 7;
    intent.duration = FLY_IN_DURATION;
    intent.arcHeightQ4 = 0;
    intent.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_NONE;
    intent.commitPolicy = OVERWORLD_MOTION_COMMIT_PRESENTATION_ONLY;
    candidate.targetX = 16;
    candidate.targetY = 0;
    candidate.targetBaseY = targetBaseY;
    candidate.direction = 3;
    candidate.distance = 16;

    decision = OverworldMotion_SelectPlan(
        &intent,
        0,
        0,
        targetBaseY + FLY_IN_HEIGHT,
        &candidate,
        1,
        &plan,
        &selected);
    assert(decision == OVERWORLD_MOTION_DECISION_ACCEPTED);
    assert(selected == 0);
    assert(plan.kind == OVERWORLD_MOTION_KIND_FLY_IN);
    assert(plan.startBaseY == targetBaseY + FLY_IN_HEIGHT);
    assert(plan.targetBaseY == targetBaseY);
    assert(plan.arcHeightQ4 == 0);
    assert(plan.duration == FLY_IN_DURATION);
    assert(plan.pathAdvancePolicy == OVERWORLD_MOTION_PATH_ADVANCE_NONE);
    assert(plan.commitPolicy == OVERWORLD_MOTION_COMMIT_PRESENTATION_ONLY);
    assert(OverworldMotion_Begin(&state, &plan)
        == OVERWORLD_MOTION_DECISION_ACCEPTED);

    previousBaseY = plan.startBaseY;
    for (frame = 1; frame <= FLY_IN_DURATION; frame++) {
        flags = OverworldMotion_Tick(&state, 7, &sample);
        assert((flags & OVERWORLD_MOTION_TICK_MOVED) != 0);
        assert((flags & OVERWORLD_MOTION_TICK_PATH_ADVANCED) == 0);
        assert(sample.baseY <= previousBaseY);
        assert(sample.baseY >= targetBaseY);
        assert(sample.heightOffset == 0);
        assert(sample.swayOffset == 0);
        assert(sample.renderY == sample.baseY);
        previousBaseY = sample.baseY;
    }
    assert((flags & OVERWORLD_MOTION_TICK_REACHED_TARGET) != 0);
    assert((flags & OVERWORLD_MOTION_TICK_COMMIT_READY) != 0);
    assert(state.phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING);
    assert(sample.baseY == targetBaseY);
    assert(sample.renderY == targetBaseY);
    assert(sample.heightOffset == 0);
    assert(sample.renderX == (16 << 16) + 0x8000);
    assert(sample.renderZ == 0x8000);
    assert(OverworldMotion_AcknowledgeCommit(&state, 7)
        == OVERWORLD_MOTION_DECISION_ACCEPTED);
    assert(state.phase == OVERWORLD_MOTION_PHASE_IDLE);
}

int main(void)
{
    _Static_assert(OVERWORLD_MOTION_KIND_FLY_IN == 6, "Fly In kind ABI");
    RunDescent(3 * TILE_FX32);
    RunDescent(-2 * TILE_FX32);
    return 0;
}
"""


class SpawnFlyInTests(unittest.TestCase):
    def test_shared_motion_descends_to_exact_target_height(self):
        with tempfile.TemporaryDirectory(prefix="spawn-fly-in-") as directory:
            source = Path(directory) / "fly_in.c"
            binary = Path(directory) / "fly_in"
            source.write_text(HARNESS)
            compiled = subprocess.run(
                [
                    "cc",
                    "-std=c11",
                    "-O2",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-DOVERWORLD_MOTION_HOST",
                    "-I",
                    str(ROOT / "include"),
                    str(source),
                    str(ROOT / "lib/overworld/overworld_motion_model.c"),
                    "-o",
                    str(binary),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                compiled.returncode,
                0,
                compiled.stdout + compiled.stderr,
            )
            completed = subprocess.run(
                [str(binary)], capture_output=True, text=True
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )

    def test_spawn_adapter_uses_fixed_exact_landing_contract(self):
        source = SPAWNS.read_text()
        start = function(source, "OverworldWildSpawns_StartSpawnAirborne")
        shared_start = function(
            source, "OverworldWildSpawns_StartPreparedCustomJumpCommandTimed"
        )
        shared_request = function(
            source, "OverworldWildSpawns_BeginSharedMotion"
        )
        prepare = function(source, "OverworldWildSpawns_PrepareSpawnAirborneStart")
        prepare_startup = function(
            source, "OverworldWildSpawns_PrepareSpawnStartup"
        )
        render = function(source, "OverworldWildSpawns_ApplyCustomJumpRenderOffset")
        finish = function(source, "OverworldWildSpawns_HandleFinishedSpawnHopMovementCommand")
        commit = function(source, "OverworldWildSpawns_CommitCustomJumpLanding")
        spawn = function(source, "OverworldWildSpawns_SpawnPreparedEncounter")

        self.assertRegex(
            source,
            r"#define OW_WILD_SPAWNER_FLY_IN_DURATION_FRAMES\s+144",
        )
        self.assertRegex(
            source,
            r"#define OW_WILD_SPAWNER_FLY_IN_HEIGHT_FX32\s+\\\n"
            r"\s*\(6 \* OW_WILD_SPAWNER_TILE_FX32\)",
        )
        self.assertIn("OW_WILD_SPAWNER_SPAWN_FLY_IN_DISTANCE", prepare)
        self.assertIn("OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN", prepare)
        fly_branch_start = start.index("if (flyIn) {")
        fly_branch = start[fly_branch_start:start.index("} else {", fly_branch_start)]
        self.assertNotIn("OverworldWildSpawns_ResolveObjectLandingHeight(", fly_branch)
        self.assertIn("startup->targetBaseY =", prepare_startup)
        self.assertIn("OverworldWildSpawns_GetObjectGroundBaseYAt(", prepare_startup)
        self.assertLess(
            prepare_startup.index("startup->targetBaseY ="),
            prepare_startup.rindex("OverworldWildSpawns_PrepareSpawnAirborneStart("),
        )
        self.assertIn(
            "startBaseY = targetBaseY + OW_WILD_SPAWNER_FLY_IN_HEIGHT_FX32;",
            start,
        )
        self.assertLess(
            start.index("OW_WILD_SPAWN_ENTRY_FLY_IN"),
            start.index("OverworldWildSpawns_StartPreparedCustomJumpCommand("),
        )
        self.assertIn("OVERWORLD_MOTION_KIND_FLY_IN", shared_request)
        self.assertIn("if (flyIn)", shared_start)
        self.assertIn("OW_WILD_SPAWNER_FLY_IN_DURATION_FRAMES", shared_start)
        self.assertIn("&& !flyIn", shared_start)
        self.assertIn(
            "runtime->movementCustomJumpShadowBaseY[slot] = targetBaseY;",
            shared_start,
        )
        self.assertNotIn("ResolveHopTrajectory", start)
        self.assertNotIn("spawnHopTime", start)
        self.assertNotIn("spawnHopSwayWidth", start)
        self.assertIn("OW_WILD_SPAWN_ENTRY_FLY_IN", render)
        self.assertIn("OW_WILD_SPAWN_ENTRY_FLY_IN", finish)
        self.assertIn("OverworldWildSpawns_SetObjectLandingTile(", commit)
        self.assertIn("movementCustomJumpTargetBaseY[slot]", commit)
        self.assertIn("OW_WILD_SPAWN_ENTRY_FLY_IN", commit)
        self.assertIn("OW_WILD_SPAWNER_SPOT_STATE_CHILL", finish)
        self.assertIn("OverworldWildSpawns_ClearSpawnRunState", finish)
        self.assertIn("OverworldWildSpawns_SetPostSpawnStartupCooldown", finish)
        self.assertIn("OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN", spawn)

    def test_runtime_marks_flight_as_presentation_only(self):
        source = RUNTIME.read_text()
        request = function(source, "OverworldWildRuntime_RequestMotion")
        self.assertIn("intent.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_NONE;", request)
        self.assertIn("OVERWORLD_MOTION_COMMIT_PRESENTATION_ONLY", request)
        self.assertIn("kind == OVERWORLD_MOTION_KIND_FLY_IN", request)


if __name__ == "__main__":
    unittest.main()
