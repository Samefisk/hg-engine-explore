"""Blocked Wild movement must preserve facing and use a retry delay."""

from pathlib import Path
import importlib.util
import os
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPAWNS = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def function_bodies():
    spec = importlib.util.spec_from_file_location(
        "blocked_facing_bodies",
        ROOT / "scripts/verify_overworld_role_controller.py",
    )
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    return extract.function_bodies(SPAWNS.read_text())


def walk_harness_source():
    bodies = function_bodies()
    return (
        PRELUDE
        + "\n"
        + bodies["OverworldWildSpawns_ApplyWalkPolicyOutput"]
        + "\n}\n"
        + EXECUTE_DECL
        + bodies["OverworldWildSpawns_ExecuteWalkPolicy"]
        + "\n}\n"
        + DRIVER
    )


PRELUDE = r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0

#define MAPOBJECTFLAG_UNK7 0x80
#define OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION 0x08
#define OVERWORLD_ACTOR_WALK_POLICY_INPUT 0
#define OVERWORLD_ACTOR_WALK_POLICY_START_RESULT 1
#define OVERWORLD_ACTOR_WALK_POLICY_COMMIT 2
#define OVERWORLD_ACTOR_WALK_POLICY_IGNORED 0
#define OVERWORLD_ACTOR_WALK_POLICY_CONSUMED 1
#define OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP 2
#define OVERWORLD_ACTOR_WALK_POLICY_START_NONE 0
#define OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED 1
#define OVERWORLD_ACTOR_WALK_POLICY_START_BLOCKED 2
#define OVERWORLD_ACTOR_WORLD_EFFECT_NONE 0
#define OVERWORLD_ACTOR_WORLD_EFFECT_SKID_DUST 1
#define OVERWORLD_ACTOR_WORLD_EFFECT_STOMP 2
#define OVERWORLD_ACTOR_WORLD_EFFECT_CRASH 3
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT 3
#define OW_WILD_WALK_DIRECTION_NONE 0xff
#define OW_WILD_SPAWNER_WALK_STOP_SKID_PAUSE_FRAMES 8
#define OW_WILD_SPAWNER_WALK_CRASH_SHAKE_FRAMES 8
#define OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION 1

typedef struct LocalMapObject {
    u32 flags;
    u8 facingInit;
    u8 curFacing;
    u8 nextFacing;
    u8 curFacingBak;
    u8 nextFacingBak;
} LocalMapObject;
typedef struct OverworldWildSpawnState {
    u8 movementPreviousTileLocked[1];
    u8 movementLastDistances[1];
    u8 movementCooldowns[1];
    u8 movementSpotStates[1];
} OverworldWildSpawnState;
typedef struct OverworldWildBehaviorProfileData { u8 walkOptions; } OverworldWildBehaviorProfileData;
typedef struct OverworldWildBehaviorProfile { int unused; } OverworldWildBehaviorProfile;
typedef struct OverworldWildDirectionStepContext {
    OverworldWildSpawnState *state;
    void *fieldSystem;
    LocalMapObject *object;
    const OverworldWildBehaviorProfile *profile;
    const void *primitives;
    u8 slot;
    u16 allowedTile;
    u8 jumpLevel;
    u8 avoidPreviousTile;
} OverworldWildDirectionStepContext;
typedef struct OverworldActorWalkPolicyCall {
    const OverworldWildBehaviorProfileData *lane;
    u8 operation;
    u8 decision;
    u8 startResult;
    u8 stepFlags;
    u8 facingDirection;
    u8 effect;
} OverworldActorWalkPolicyCall;

static int facingWrites;
static int startAccepted;
static int reducerReaddsClear;

static void SetFacing(LocalMapObject *object, u8 direction)
{
    facingWrites++;
    object->facingInit = object->curFacing = object->nextFacing = direction;
    object->curFacingBak = object->nextFacingBak = direction;
}
#define OverworldWildSpawns_SetObjectFacing SetFacing
static void PlayParticle(LocalMapObject *object) { (void)object; }
static const struct { void (*playLandingHopParticle)(LocalMapObject *); } runtimeEntry = { PlayParticle };
#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY (&runtimeEntry)
static void OverworldActor_PlayStompSound(u8 options) { (void)options; }
static void OverworldWildSpawns_PlayMovementCrashFeedback(
    const OverworldWildBehaviorProfile *profile, u8 state)
{ (void)profile; (void)state; }
static void OverworldWildSpawns_StartMovementCrashShake(
    OverworldWildSpawnState *state, int slot, LocalMapObject *object, int frames)
{ (void)state; (void)slot; (void)object; (void)frames; }
static BOOL OverworldWildSpawns_StartMomentumWalkStep(
    OverworldWildDirectionStepContext *context,
    OverworldActorWalkPolicyCall *call)
{
    (void)context;
    (void)call;
    return startAccepted;
}
static BOOL OverworldWildSpawns_ReduceWalk(OverworldActorWalkPolicyCall *call)
{
    if (call->operation == OVERWORLD_ACTOR_WALK_POLICY_START_RESULT) {
        call->decision = call->startResult == OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED
            ? OVERWORLD_ACTOR_WALK_POLICY_CONSUMED
            : OVERWORLD_ACTOR_WALK_POLICY_IGNORED;
        if (reducerReaddsClear) {
            call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION;
        }
    }
    return TRUE;
}

static void OverworldWildSpawns_ApplyWalkPolicyOutput(
    OverworldWildDirectionStepContext *stepContext,
    OverworldActorWalkPolicyCall *call)
{
"""


EXECUTE_DECL = r"""
static BOOL OverworldWildSpawns_ExecuteWalkPolicy(
    OverworldWildDirectionStepContext *stepContext,
    OverworldActorWalkPolicyCall *call)
{
"""


DRIVER = r"""
static void Check(BOOL condition, const char *message)
{
    if (!condition) { fprintf(stderr, "%s\n", message); exit(1); }
}

int main(void)
{
    LocalMapObject object = { .curFacing = 2 };
    OverworldWildSpawnState state = {0};
    OverworldWildBehaviorProfileData lane = {0};
    OverworldWildDirectionStepContext context = {
        .state = &state, .object = &object, .profile = NULL, .slot = 0,
    };
    OverworldActorWalkPolicyCall call = {
        .lane = &lane,
        .operation = OVERWORLD_ACTOR_WALK_POLICY_INPUT,
        .decision = OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP,
        .startResult = OVERWORLD_ACTOR_WALK_POLICY_START_NONE,
        .stepFlags = OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION,
        .facingDirection = 0,
    };

    startAccepted = FALSE;
    reducerReaddsClear = TRUE;
    Check(!OverworldWildSpawns_ExecuteWalkPolicy(&context, &call),
        "blocked proposal was not rejected");
    Check(object.curFacing == 2 && facingWrites == 0,
        "blocked Walk proposal changed facing");

    memset(&call, 0, sizeof(call));
    call.lane = &lane;
    call.operation = OVERWORLD_ACTOR_WALK_POLICY_COMMIT;
    call.decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
    call.stepFlags = OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION;
    call.facingDirection = 1;
    OverworldWildSpawns_ApplyWalkPolicyOutput(&context, &call);
    Check(object.curFacing == 1 && facingWrites == 1,
        "accepted terminal presentation did not apply facing");
    return 0;
}
"""


class BlockedWildFacingTests(unittest.TestCase):
    def test_blocked_walk_transaction_preserves_facing(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "blocked-facing"
            compiled = subprocess.run(
                [
                    *shlex.split(os.environ.get("HOST_CC", "cc")),
                    "-std=gnu11", "-O0", "-x", "c", "-", "-o", executable,
                ],
                input=walk_harness_source(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            run = subprocess.run([executable], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_fully_blocked_random_wander_has_no_turn_fallback(self):
        body = function_bodies()["OverworldWildSpawns_TryStartSpawnerMovementCommand"]
        random_target = body.index("OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY")
        fallback = body.index("goto turn_around;", random_target)
        self.assertIn("preferredDirectionIndex = 0;", body[random_target:fallback])
        self.assertIn("OW_WILD_BEHAVIOR_TARGET_NONE", body[random_target:fallback])
        self.assertIn("preferredDirectionIndex == -1", body[random_target:fallback])
        self.assertIn(
            "OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES",
            body[fallback:],
        )

    def test_blocked_random_hop_preserves_facing_and_waits(self):
        body = function_bodies()["OverworldWildSpawns_TryStartRandomBehaviorHopCommand"]
        failure_start = body.index("if (!helperEntry->pickRandomBehaviorHop(")
        failure_end = body.index("    }", failure_start) + len("    }")
        failure = body[failure_start:failure_end]
        before_plan = body[:failure_start]
        self.assertNotIn("OverworldWildSpawns_SetObjectFacing(", before_plan)
        self.assertNotIn("OverworldWildSpawns_SetObjectFacing(", failure)
        self.assertIn("OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES", failure)


if __name__ == "__main__":
    unittest.main()
