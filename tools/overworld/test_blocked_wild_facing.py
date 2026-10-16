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


def function_bodies(source=SPAWNS):
    spec = importlib.util.spec_from_file_location(
        "blocked_facing_bodies",
        ROOT / "scripts/verify_overworld_role_controller.py",
    )
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    return extract.function_bodies(source.read_text())


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
#define OVERWORLD_ACTOR_WALK_STEP_SKID 0x02
#define OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION 0x08
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_CRASH_ON_BLOCKED 0x10
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
    u8 stepDirection;
    u8 facingDirection;
    u8 effect;
    u8 flags;
} OverworldActorWalkPolicyCall;
typedef struct OverworldActorPolicyView { int unused; } OverworldActorPolicyView;

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
static void OverworldWildSpawns_PublishWalkCrash(
    OverworldWildSpawnState *state, u8 slot) { (void)state; (void)slot; }
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
static BOOL OverworldActorPolicy_Inspect(u8 slot, OverworldActorPolicyView *view)
{ (void)slot; (void)view; return FALSE; }
static void OverworldWildSpawns_TryApplyPlayerCollisionAttack(
    OverworldWildDirectionStepContext *context, u8 direction,
    const OverworldActorPolicyView *view,
    const OverworldWildBehaviorProfileData *lane)
{ (void)context; (void)direction; (void)view; (void)lane; }

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


def heading_harness_source(source=SPAWNS):
    """Extract both full callers; mocks only record native owner seams."""
    bodies = function_bodies(source)
    helper = "OverworldWildSpawns_GetCommittedWalkDirection"
    # The preserved pre-fix source inlines the old decision at all three sites.
    shared = ("static u8 " + helper + "(const OverworldActorPolicyView *policy) {\n"
              + bodies[helper] + "\n}\n") if helper in bodies else ""
    return (HEADING_PRELUDE + shared + ACCELERATED_DECL
            + bodies["OverworldWildSpawns_TryStartAcceleratedWalkStep"]
            + "\n}\n" + HEADING_STEP_SEAM + SPAWNER_DECL
            + bodies["OverworldWildSpawns_TryStartSpawnerMovementCommand"]
            + "\n}\n" + HEADING_DRIVER)


HEADING_PRELUDE = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_WALK_COMMAND 1
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT 3
#define OW_WILD_BEHAVIOR_LOCOMOTION_WANDER 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_TURN_AROUND 8
#define OW_WILD_BEHAVIOR_TARGET_NONE 0
#define OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY 1
#define OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION 1
#define OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP 1
#define OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES 32
#define OVERWORLD_MOTION_PHASE_IDLE 0
#define OVERWORLD_MOTION_PHASE_CANCELED 6
#define OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE 255
#define OVERWORLD_ROLE_CONTROLLER_DIRECTION_MAX 7
#define OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST 1
#define OVERWORLD_ROLE_CONTROLLER_INTENT_WALK 1
#define OVERWORLD_ROLE_CONTROLLER_INPUT_RAM 1
#define OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED 2
#define OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED (1u << 24)
#define OW_WILD_SPAWNER_ROLE_INPUT_INTENT_SHIFT 8
#define OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT 16
#define OW_WILD_SPAWNER_ROLE_INPUT_COMMITTED_SHIFT 24
#define OVERWORLD_ACTOR_WALK_POLICY_INPUT 1
#define OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT 16
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED 8
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_CRASH_ON_BLOCKED 16
#define OVERWORLD_ACTOR_WALK_STEP_VALIDATE 1
#define OVERWORLD_ACTOR_WALK_STEP_SKID 2
#define OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_PENDING_INDEX 3
#define OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL 1
#define OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED 2
#define OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP 2
#define OW_WILD_DIRECTION_STEP_STARTED 2
#define OW_WILD_DIRECTION_STEP_BUSY 0
#define OW_WILD_DIRECTION_STEP_BLOCKED 1
typedef int OverworldWildDirectionStepResult;
typedef struct FieldSystem { int unused; } FieldSystem;
typedef struct LocalMapObject { u8 facing; } LocalMapObject;
typedef struct OverworldWildBehaviorProfileData {
    u8 walkOptions, ramMaxSpeed, wanderStraightChance;
} OverworldWildBehaviorProfileData;
typedef struct OverworldWildBehaviorProfile { u8 jumpLevel; } OverworldWildBehaviorProfile;
typedef struct OverworldWildBehaviorPrimitives { int unused; } OverworldWildBehaviorPrimitives;
typedef struct OverworldWildSpawnState {
    struct { LocalMapObject *object; } spawns[1];
    u8 movementSpotStates[1], movementCooldowns[1];
    u8 movementLastDistances[1], movementLastDirections[1];
} OverworldWildSpawnState;
typedef struct OverworldActorPolicyView {
    struct { u8 direction, speed, skidRemaining; } walkMomentum;
    u8 motionPhase;
} OverworldActorPolicyView;
typedef struct OverworldWildDirectionStepContext {
    OverworldWildSpawnState *state;
    FieldSystem *fieldSystem;
    LocalMapObject *object;
    const OverworldWildBehaviorProfile *profile;
    const OverworldWildBehaviorPrimitives *primitives;
    u8 slot;
    u16 allowedTile;
    u8 jumpLevel, avoidPreviousTile;
} OverworldWildDirectionStepContext;
typedef struct OverworldActorWalkPolicyCall {
    const OverworldWildBehaviorProfileData *lane;
    u8 operation, direction, laneState, flags, stepFlags, decision, reserved[4];
} OverworldActorWalkPolicyCall;
/* Linear carry belongs to the native owner, never to these direction callers. */
static struct { OverworldActorPolicyView view; u8 linearElapsed, linearCarry; } owner;
static OverworldWildBehaviorProfileData lane = { .walkOptions = 1 };
static int proposals, roleCalls, walkCalls;
static u8 proposed, walkDirection, walkFlags, roleFlags, committed;
static BOOL inspectAvailable = TRUE;
static BOOL MapObject_IsSingleMovementActive(LocalMapObject *o) { (void)o; return FALSE; }
static BOOL OverworldActorPolicy_Inspect(u8 slot, OverworldActorPolicyView *out)
{ (void)slot; *out = owner.view; return inspectAvailable; }
static void OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
    OverworldWildSpawnState *s, int slot, OverworldWildBehaviorProfile *p,
    OverworldWildBehaviorPrimitives *b) { (void)s; (void)slot; memset(p,0,sizeof(*p)); memset(b,0,sizeof(*b)); }
static u8 OverworldWildSpawns_GetCurrentMovementLocomotion(const OverworldWildBehaviorPrimitives *p, u8 state)
{ (void)p; (void)state; return OW_WILD_BEHAVIOR_LOCOMOTION_WANDER; }
static u8 OverworldWildSpawns_GetCurrentMovementTarget(const OverworldWildBehaviorPrimitives *p, u8 state)
{ (void)p; (void)state; return OW_WILD_BEHAVIOR_TARGET_NONE; }
static const OverworldWildBehaviorProfileData *OverworldWildSpawns_GetControllerLane(
    const OverworldWildBehaviorProfile *p, u8 state) { (void)p; (void)state; return &lane; }
static int ChooseWander(const u8 *d, int n, u8 previous, u8 chance)
{ (void)d; (void)n; (void)previous; (void)chance; return 0; }
static const struct { int (*chooseWanderDirection)(const u8 *,int,u8,u8); } policyEntry = { ChooseWander };
static const struct { const typeof(policyEntry) *policy; } movementEntry = { &policyEntry };
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY (&movementEntry)
static BOOL OverworldWildSpawns_ShouldAvoidPreviousTileForResolvedProfile(
    OverworldWildSpawnState *s, int slot, const OverworldWildBehaviorProfile *p)
{ (void)s; (void)slot; (void)p; return FALSE; }
static u16 OverworldWildSpawns_GetAllowedTileForSpotState(const OverworldWildBehaviorProfile *p, u8 state)
{ (void)p; (void)state; return 0; }
static BOOL OverworldWildSpawns_IsAvoidedBacktrackStep(OverworldWildSpawnState *s, int slot,
    LocalMapObject *o, u8 direction, int distance, BOOL avoid)
{ (void)s; (void)slot; (void)o; (void)direction; (void)distance; (void)avoid; return FALSE; }
static BOOL OverworldWildSpawns_HandleLockedWalkCrash(const OverworldWildDirectionStepContext *c, u8 d)
{ (void)c; (void)d; return FALSE; }
static BOOL OverworldWildSpawns_TryStartBlockedWalkStopSkid(OverworldWildSpawnState *s, int slot,
    const OverworldWildBehaviorProfile *p, const OverworldWildBehaviorProfileData *l,
    u8 locomotion, BOOL lock, BOOL blocked, int count)
{ (void)s; (void)slot; (void)p; (void)l; (void)locomotion; (void)lock; (void)blocked; (void)count; return FALSE; }
static void OverworldWildSpawns_SetObjectFacing(LocalMapObject *o, u8 d) { o->facing=d; }
static void OverworldWildSpawns_TryApplyPlayerCollisionAttack(const OverworldWildDirectionStepContext *c,
    u8 d, const OverworldActorPolicyView *p, const OverworldWildBehaviorProfileData *l)
{ (void)c; (void)d; (void)p; (void)l; }
/* Record the real packed request. The mock does not choose a locked heading. */
static u32 OverworldWildSpawns_ReduceRole(int slot, u32 request, u8 flags)
{ (void)slot; roleCalls++; committed=request>>24; roleFlags=flags;
  return OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED | ((request>>16)&255) | (24u<<6); }
static void OverworldWildSpawns_InitPolicyCall(OverworldActorWalkPolicyCall *c, u8 slot, u8 op)
{ (void)slot; memset(c,0,sizeof(*c)); c->operation=op; }
static BOOL OverworldWildSpawns_ReduceWalk(OverworldActorWalkPolicyCall *c)
{ walkCalls++; walkDirection=c->direction; walkFlags=c->flags;
  c->decision=OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP; c->stepFlags|=OVERWORLD_ACTOR_WALK_STEP_SKID; return TRUE; }
static BOOL OverworldWildSpawns_ExecuteWalkPolicy(OverworldWildDirectionStepContext *c,
    OverworldActorWalkPolicyCall *call) { (void)c; (void)call; return TRUE; }
"""

ACCELERATED_DECL = r"""
static u8 OverworldWildSpawns_TryStartAcceleratedWalkStep(const OverworldWildDirectionStepContext *stepContext,
    const OverworldActorPolicyView *priorPolicy, u8 direction, BOOL previewOnly) {
"""

HEADING_STEP_SEAM = r"""
static OverworldWildDirectionStepResult OverworldWildSpawns_TryStartSingleDirectionMovementStep(
    OverworldWildDirectionStepContext *c, const OverworldActorPolicyView *p, u8 direction, BOOL keep)
{ (void)keep; proposals++; proposed=direction;
  return OverworldWildSpawns_TryStartAcceleratedWalkStep(c,p,direction,FALSE)
      ? OW_WILD_DIRECTION_STEP_STARTED : OW_WILD_DIRECTION_STEP_BLOCKED; }
"""

SPAWNER_DECL = r"""
static BOOL OverworldWildSpawns_TryStartSpawnerMovementCommand(OverworldWildSpawnState *state,
    FieldSystem *fieldSystem, int slot, const u8 *directions, int directionCount,
    const OverworldWildBehaviorProfile *profile, const OverworldWildBehaviorPrimitives *primitives) {
"""

HEADING_DRIVER = r"""
static int failures;
static void Check(BOOL ok, const char *message, int stale, int wanted)
{ if (!ok) { fprintf(stderr,"%s: stale=%d wanted=%d\n",message,stale,wanted); failures++; } }
int main(void)
{
    LocalMapObject object={0}; FieldSystem field={0};
    OverworldWildSpawnState state={ .spawns={{&object}} };
    OverworldWildBehaviorProfile profile={0}; OverworldWildBehaviorPrimitives primitives={0};
    OverworldWildDirectionStepContext context={ .state=&state, .fieldSystem=&field,
        .object=&object, .profile=&profile, .primitives=&primitives };
    for (int speed=0; speed<=8; speed+=8) for (int stale=0; stale<4; stale++) for (int wanted=0; wanted<4; wanted++) {
        u8 directions[]={wanted,(wanted+1)%4};
        memset(&owner,0,sizeof(owner)); owner.view.walkMomentum.direction=stale;
        owner.view.walkMomentum.speed=speed;
        if (speed || stale) { owner.linearElapsed=137; owner.linearCarry=29; }
        typeof(owner) before=owner; u8 expected=speed?stale:wanted;
        proposals=roleCalls=walkCalls=0;
        Check(OverworldWildSpawns_TryStartSpawnerMovementCommand(&state,&field,0,directions,2,&profile,&primitives),
            "native START rejected",stale,wanted);
        Check(proposals==1 && proposed==expected && walkDirection==expected,
            speed?"moving native heading changed":"stopped native START used stale heading",stale,wanted);
        Check(roleCalls==1 && committed==(speed?stale:255) && (roleFlags&1),
            "role request has wrong committed heading",stale,wanted);
        Check(memcmp(&owner,&before,sizeof(owner))==0,"START changed native speed or linear carry",stale,wanted);
        roleCalls=walkCalls=0;
        Check(OverworldWildSpawns_TryStartAcceleratedWalkStep(&context,&owner.view,wanted,TRUE)==TRUE,
            "preview did not reach Walk seam",stale,wanted);
        Check(walkCalls==1 && roleCalls==0 && walkDirection==expected && (walkFlags&16),
            speed?"moving preview heading changed":"stopped preview used stale heading",stale,wanted);
        Check(memcmp(&owner,&before,sizeof(owner))==0,"preview changed native speed or linear carry",stale,wanted);
    }
    for (int busy=0; busy<3; busy++) {
        u8 directions[]={1}; memset(&owner,0,sizeof(owner)); proposals=0;
        owner.view.motionPhase=busy==0?1:0; owner.view.walkMomentum.skidRemaining=busy==1;
        inspectAvailable=busy!=2;
        Check(!OverworldWildSpawns_TryStartSpawnerMovementCommand(&state,&field,0,directions,1,&profile,&primitives)
            && proposals==0,"busy/unavailable owner reached native START",busy,1);
    }
    if (!failures) puts("stopped16/moving16 native START+preview+role controls; native speed/carry and3owner gates preserved");
    return failures?1:0;
}
"""


class BlockedWildFacingTests(unittest.TestCase):
    def test_stopped_and_moving_locked_heading_at_native_seams(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "locked-heading"
            compiled = subprocess.run(
                [*shlex.split(os.environ.get("HOST_CC", "cc")),
                 "-std=gnu11", "-O0", "-x", "c", "-", "-o", executable],
                input=heading_harness_source(), text=True, capture_output=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            run = subprocess.run([executable], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)

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
