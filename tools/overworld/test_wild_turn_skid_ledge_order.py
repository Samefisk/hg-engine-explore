"""Extract the Wild movement frontend and prove due skids outrank ledge Hops."""

from pathlib import Path
import importlib.util
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def harness_source() -> str:
    path = ROOT / "scripts/verify_overworld_role_controller.py"
    spec = importlib.util.spec_from_file_location("wild_ledge_bodies", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bodies = module.function_bodies(SOURCE.read_text())
    return r"""
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
#define OW_WILD_BEHAVIOR_LOCOMOTION_WANDER 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP 2
#define OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION 1
#define OVERWORLD_ROLE_CONTROLLER_DIRECTION_MAX 7
#define OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT 16
#define OVERWORLD_ACTOR_WALK_POLICY_INPUT 1
#define OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_PENDING_INDEX 3
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED 8
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_CRASH_ON_BLOCKED 16
#define OVERWORLD_ACTOR_WALK_STEP_VALIDATE 1
#define OVERWORLD_ACTOR_WALK_STEP_SKID 2
#define OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL 1
#define OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED 2
#define OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP 2
#define OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED 2
#define OVERWORLD_ROLE_CONTROLLER_INPUT_RAM 1
#define OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST 1
#define OVERWORLD_ROLE_CONTROLLER_INTENT_WALK 1
#define OW_WILD_SPAWNER_ROLE_INPUT_INTENT_SHIFT 8
#define OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT 16
#define OW_WILD_SPAWNER_ROLE_INPUT_COMMITTED_SHIFT 24
#define OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED (1u << 24)
#define OW_WILD_SPAWNER_ROLE_RESULT_FLAGS_SHIFT 8
#define OVERWORLD_ROLE_CONTROLLER_INTENT_ENABLE_CHAIN 2
#define OVERWORLD_ROLE_CONTROLLER_INTENT_CRASH_ON_BLOCKED 4
#define OW_WILD_DIRECTION_STEP_BUSY 0
#define OW_WILD_DIRECTION_STEP_BLOCKED 1
#define OW_WILD_DIRECTION_STEP_STARTED 2
#define OW_WILD_DIRECTION_STEP_OBSTACLE_HOP_STARTED 3
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK 0
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT 3
#define MAPOBJECTFLAG_UNK7 0x80
#define OW_WILD_SPAWNER_CANOPY_HOPPER_JUMP_1_COMMAND 5
#define OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP 1
typedef int OverworldWildDirectionStepResult;
typedef struct LocalMapObject { int xCurr, yCurr; } LocalMapObject;
typedef struct OverworldWildBehaviorProfileData { u8 walkOptions, chillSpeed; }
    OverworldWildBehaviorProfileData;
typedef struct OverworldWildBehaviorProfile {
    OverworldWildBehaviorProfileData owner, tired;
} OverworldWildBehaviorProfile;
typedef struct OverworldWildBehaviorPrimitives { u8 locomotion; }
    OverworldWildBehaviorPrimitives;
typedef struct OverworldWildSpawnState {
    struct { BOOL active; } spawns[10];
    u8 movementSpotStates[10];
} OverworldWildSpawnState;
typedef struct OverworldWildDirectionStepContext {
    OverworldWildSpawnState *state;
    void *fieldSystem;
    LocalMapObject *object;
    const OverworldWildBehaviorProfile *profile;
    const OverworldWildBehaviorPrimitives *primitives;
    u8 slot;
    u16 allowedTile;
} OverworldWildDirectionStepContext;
typedef struct OverworldActorPolicyView {
    struct { u8 direction; } walkMomentum;
} OverworldActorPolicyView;
typedef struct OverworldActorWalkPolicyCall {
    const OverworldWildBehaviorProfileData *lane;
    u8 actorSlot, operation, direction, laneState, flags, stepFlags, decision;
    u8 reserved[4];
} OverworldActorWalkPolicyCall;
static int previewDue, previewPending, previewCalls, ledgeCalls, walkCalls;
static int canopyCalls, clearCalls, expectedDirection, livePolicy = 41;
static int roleCalls, inspectCalls, realReduceCalls;
static int ledgeAnswer;
static BOOL sOverworldWildMovementDiagnosticDirectionBlocked;
static const OverworldWildBehaviorProfileData *OverworldWildSpawns_GetControllerLane(
    const OverworldWildBehaviorProfile *profile, u8 spotState)
{ (void)spotState; return &profile->owner; }
static void OverworldWildSpawns_InitPolicyCall(
    OverworldActorWalkPolicyCall *call, int slot, u8 operation)
{ memset(call, 0, sizeof(*call)); call->actorSlot = (u8)slot; call->operation = operation; }
static BOOL OverworldWildSpawns_ReduceWalk(OverworldActorWalkPolicyCall *call)
{
    if ((call->operation != OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT
            && call->operation != OVERWORLD_ACTOR_WALK_POLICY_INPUT)
        || call->direction != expectedDirection
        || call->lane == NULL || call->laneState != 0
        || (call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_VALIDATE) == 0
        || (call->flags & OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED) == 0) {
        fprintf(stderr, "bad reduce op=%u direction=%u expected=%d lane=%p laneState=%u flags=%u step=%u\n",
            call->operation, call->direction, expectedDirection,
            (void *)call->lane, call->laneState, call->flags, call->stepFlags);
        return FALSE;
    }
    if (call->operation == OVERWORLD_ACTOR_WALK_POLICY_INPUT) {
        realReduceCalls++;
        return TRUE;
    }
    previewCalls++;
    call->reserved[OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_PENDING_INDEX] = previewPending;
    if (!previewPending) {
        call->decision = OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP;
        if (previewDue) call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_SKID;
    }
    return TRUE;
}
static BOOL OverworldActorPolicy_Inspect(u8 slot, OverworldActorPolicyView *policy)
{ (void)slot; inspectCalls++; policy->walkMomentum.direction = 3; return TRUE; }
static u32 OverworldWildSpawns_ReduceRole(int slot, u32 request, u8 flags)
{ (void)slot; roleCalls++;
  return OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED
      | ((request >> (flags & OVERWORLD_ROLE_CONTROLLER_INPUT_RAM
              ? OW_WILD_SPAWNER_ROLE_INPUT_COMMITTED_SHIFT
              : OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT)) & 0x0f)
      | (OVERWORLD_ROLE_CONTROLLER_INTENT_ENABLE_CHAIN
          << OW_WILD_SPAWNER_ROLE_RESULT_FLAGS_SHIFT)
      | ((flags & OVERWORLD_ROLE_CONTROLLER_INPUT_RAM
          ? OVERWORLD_ROLE_CONTROLLER_INTENT_CRASH_ON_BLOCKED : 0)
          << OW_WILD_SPAWNER_ROLE_RESULT_FLAGS_SHIFT); }
static u8 OverworldWildSpawns_GetCurrentMovementLocomotion(
    const OverworldWildBehaviorPrimitives *primitives, u8 spotState)
{ (void)spotState; return primitives->locomotion; }
static BOOL OverworldWildSpawns_ExecuteWalkPolicy(
    OverworldWildDirectionStepContext *context, OverworldActorWalkPolicyCall *call)
{ (void)context; (void)call; walkCalls++; return TRUE; }
static int OverworldWildSpawns_TryStartLedgeJumpCommand(
    const OverworldWildDirectionStepContext *context, u8 direction,
    BOOL obstacleHopAllowed, BOOL probeOnly)
{ (void)context; (void)direction; (void)obstacleHopAllowed; (void)probeOnly;
  ledgeCalls++; return ledgeAnswer; }
static void OverworldWildSpawns_ClearObjectFlags(LocalMapObject *object, int flags)
{ (void)object; (void)flags; }
static void OverworldWildSpawns_ClearWalkMovementState(
    OverworldWildSpawnState *state, int slot, LocalMapObject *object)
{ (void)state; (void)slot; (void)object; clearCalls++; }
static int OverworldWildSpawns_ObjectCurrentX(LocalMapObject *object)
{ return object->xCurr; }
static int OverworldWildSpawns_ObjectCurrentY(LocalMapObject *object)
{ return object->yCurr; }
static int OverworldWildSpawns_MovementDirectionDeltaX(u8 direction)
{ return direction == 3; }
static int OverworldWildSpawns_MovementDirectionDeltaY(u8 direction)
{ return direction == 1; }
static BOOL OverworldWildSpawns_IsBehaviorAllowedMovementTile(
    void *fieldSystem, u16 allowedTile, int x, int y)
{ (void)fieldSystem; (void)allowedTile; (void)x; (void)y; return TRUE; }
static BOOL OverworldWildSpawns_TryStartCanopyEntryHop(
    const OverworldWildDirectionStepContext *context, u8 direction)
{ (void)context; (void)direction; canopyCalls++; return FALSE; }
static u32 OverworldWildSpawns_GetMovementWalkCommandForSpeed(u8 speed)
{ return speed; }
static u32 MapObject_MovementCommandFromDirection(u8 direction, u32 command)
{ return command + direction; }
static void OverworldWildSpawns_StartMovementCommandForSlot(
    OverworldWildSpawnState *state, int slot, LocalMapObject *object,
    u32 command, u8 direction, int distance)
{ (void)state; (void)slot; (void)object; (void)command; (void)direction;
  (void)distance; }
""" + (
        "static u8 OverworldWildSpawns_TryStartAcceleratedWalkStep("
        "const OverworldWildDirectionStepContext *stepContext, "
        "const OverworldActorPolicyView *priorPolicy, u8 direction, "
        "BOOL previewOnly) {"
        + bodies["OverworldWildSpawns_TryStartAcceleratedWalkStep"] + "}\n"
        + "static OverworldWildDirectionStepResult "
        "OverworldWildSpawns_TryStartSingleDirectionMovementStep("
        "const OverworldWildDirectionStepContext *stepContext, "
        "const OverworldActorPolicyView *policy, u8 direction, "
        "BOOL obstacleHopAllowed) {"
        + bodies["OverworldWildSpawns_TryStartSingleDirectionMovementStep"] + "}\n"
    ) + r"""
static void Check(BOOL condition, const char *message)
{ if (!condition) { fprintf(stderr, "%s: preview=%d walk=%d ledge=%d canopy=%d inspect=%d role=%d real=%d\n",
    message, previewCalls, walkCalls, ledgeCalls, canopyCalls,
    inspectCalls, roleCalls, realReduceCalls); exit(1); } }
static void Reset(void)
{ previewDue = previewPending = previewCalls = ledgeCalls = walkCalls = 0;
  roleCalls = inspectCalls = realReduceCalls = 0;
  canopyCalls = clearCalls = 0; ledgeAnswer = OW_WILD_DIRECTION_STEP_BUSY;
  sOverworldWildMovementDiagnosticDirectionBlocked = FALSE; }
int main(void)
{
    OverworldWildSpawnState state = {0};
    OverworldWildBehaviorProfile profile = {0};
    OverworldWildBehaviorPrimitives primitives = {OW_WILD_BEHAVIOR_LOCOMOTION_WANDER};
    LocalMapObject object = {10, 10};
    OverworldActorPolicyView policy = {{3}};
    OverworldWildDirectionStepContext context = {
        &state, NULL, &object, &profile, &primitives, 0, 0};
    state.spawns[0].active = TRUE;
    expectedDirection = 1;

    Reset(); previewDue = TRUE; ledgeAnswer = OW_WILD_DIRECTION_STEP_BLOCKED;
    Check(OverworldWildSpawns_TryStartSingleDirectionMovementStep(
              &context, &policy, 1, FALSE) == OW_WILD_DIRECTION_STEP_STARTED
          && previewCalls == 1 && walkCalls == 1 && ledgeCalls == 0
          && canopyCalls == 0 && livePolicy == 41
          && inspectCalls == 0 && roleCalls == 1 && realReduceCalls == 1,
          "due skid lost to rejected ledge or preview changed policy");
    Reset(); previewDue = TRUE; ledgeAnswer = OW_WILD_DIRECTION_STEP_STARTED;
    Check(OverworldWildSpawns_TryStartSingleDirectionMovementStep(
              &context, &policy, 1, FALSE) == OW_WILD_DIRECTION_STEP_STARTED
          && previewCalls == 1 && walkCalls == 1 && ledgeCalls == 0
          && clearCalls == 0 && inspectCalls == 0 && roleCalls == 1,
          "due skid was replaced by ledge Hop");
    Reset(); ledgeAnswer = OW_WILD_DIRECTION_STEP_STARTED;
    Check(OverworldWildSpawns_TryStartSingleDirectionMovementStep(
              &context, &policy, 1, FALSE) == OW_WILD_DIRECTION_STEP_STARTED
          && previewCalls == 1 && ledgeCalls == 1 && walkCalls == 0
          && clearCalls == 1 && inspectCalls == 0 && roleCalls == 0,
          "ordinary ledge Hop lost priority below skid threshold");
    Reset(); ledgeAnswer = OW_WILD_DIRECTION_STEP_BLOCKED;
    Check(OverworldWildSpawns_TryStartSingleDirectionMovementStep(
              &context, &policy, 1, FALSE) == OW_WILD_DIRECTION_STEP_BLOCKED
          && ledgeCalls == 1 && walkCalls == 0,
          "ordinary blocked ledge no longer blocks");
    Reset();
    Check(OverworldWildSpawns_TryStartSingleDirectionMovementStep(
              &context, &policy, 1, FALSE) == OW_WILD_DIRECTION_STEP_STARTED
          && ledgeCalls == 1 && canopyCalls == 1 && walkCalls == 1,
          "ordinary clear turn did not reach Walk");
    Reset(); previewPending = OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL;
    Check(OverworldWildSpawns_TryStartSingleDirectionMovementStep(
              &context, &policy, 1, FALSE) == OW_WILD_DIRECTION_STEP_BUSY
          && ledgeCalls == 0 && walkCalls == 0 && livePolicy == 41,
          "pending Walk proposal was replaced by ledge");
    Reset(); previewPending = OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED;
    Check(OverworldWildSpawns_TryStartSingleDirectionMovementStep(
              &context, &policy, 1, FALSE) == OW_WILD_DIRECTION_STEP_BUSY
          && ledgeCalls == 0 && walkCalls == 0,
          "accepted Walk was replaced by ledge");
    Reset(); profile.owner.walkOptions = OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION;
    expectedDirection = 3; previewDue = TRUE;
    Check(OverworldWildSpawns_TryStartSingleDirectionMovementStep(
              &context, &policy, 1, FALSE) == OW_WILD_DIRECTION_STEP_STARTED
          && walkCalls == 1 && ledgeCalls == 0,
          "locked preview used raw candidate instead of committed direction");
    Reset(); profile.owner.walkOptions = 0; expectedDirection = 1;
    Check(OverworldWildSpawns_TryStartAcceleratedWalkStep(
              &context, NULL, 1, FALSE) == TRUE
          && inspectCalls == 1 && roleCalls == 1 && realReduceCalls == 1
          && walkCalls == 1 && previewCalls == 0,
          "direct Walk failed to inspect its policy before real reduction");
    puts("Wild due skid keeps ledge order and preview ownership");
    return 0;
}
"""


class WildTurnSkidLedgeOrderTests(unittest.TestCase):
    def test_due_skid_reaches_walk_before_ledge(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wild-skid-ledge-") as folder:
            source = Path(folder) / "fixture.c"
            binary = Path(folder) / "fixture"
            source.write_text(harness_source())
            compiled = subprocess.run(
                ["cc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                 str(source), "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
