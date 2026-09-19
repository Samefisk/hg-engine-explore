/* Exact production start/immediate bodies are inserted below. Engine types
 * are host stubs, not the Nintendo DS layout. ForceSetHeldMovement/ClearHeld
 * match stock unk_02062108.s: command, step0, flags5 clear / commandFF reset.
 * The real portable OverworldMotion_Begin decides admission and preserves
 * existing SETTLING transactions; this harness does not pretend to run AI.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_motion_model.h"
typedef int BOOL;
#define OW_WILD_MAX_SPAWNS 10
#define MAPOBJECTFLAG_UNK7 (1u << 7)
#define MAPOBJECTFLAG_UNK13 (1u << 13)
/* @CONSTANTS@ */
typedef struct LocalMapObject {
    int xCurr, yCurr, hInit, hPrev, hCurr;
    u32 posVec[3], flags, movementCommand, movementStep;
    u8 curFacing;
    BOOL partnerPrepared;
} LocalMapObject;
typedef struct FieldSystem { int unused; } FieldSystem;
typedef struct OverworldWildBehaviorProfileData { u8 walkOptions, hopSwayWidth; } OverworldWildBehaviorProfileData;
typedef struct OverworldWildBehaviorProfile { OverworldWildBehaviorProfileData lane; } OverworldWildBehaviorProfile;
typedef struct OverworldWildBehaviorDataBlob { void *surfaceModels; } OverworldWildBehaviorDataBlob;
typedef struct OverworldWildSurfaceCatalog { int unused; } OverworldWildSurfaceCatalog;
typedef struct OverworldActorPolicyView { u8 chainStepsRemaining, chainPauseTicks, chainPauseAction, motionPhase, actorActive; } OverworldActorPolicyView;
typedef struct OverworldWildOverlayRuntimeState {
    u8 movementCustomMotionModes[10], movementCustomJumpArcHeightsQ4[10];
    u8 movementCustomJumpPrepActive[10], movementCustomJumpActive[10];
    s16 movementCustomJumpStartX[10], movementCustomJumpStartY[10];
    s16 movementCustomJumpTargetX[10], movementCustomJumpTargetY[10];
} OverworldWildOverlayRuntimeState;
typedef struct OverworldWildSpawnState {
    FieldSystem *movementFieldSystem;
    u8 movementSpotStates[10], movementPendingDirections[10], movementPendingDistances[10];
    u8 movementStagedHopDistances[10], movementBattleSettleFrames;
    u16 movementInProgressMask;
    OverworldWildOverlayRuntimeState runtime;
} OverworldWildSpawnState;
#define OW_WILD_RUNTIME(state) (&(state)->runtime)

static OverworldMotionState motion;
static OverworldActorPolicyView selectedPolicy;
static unsigned assertions, cases, shellStarts, prepareCalls, restoreCalls, beginCalls, taskCalls;
static unsigned shellBeforeAdmission, soundBeforeAdmission;
static BOOL admitted;
static BOOL inspectOkay, trajectoryOkay, prepOkay, requestOkay, sOverworldWildSpawnHopPreparing;
static const char *caseName;
#define CHECK(expression) do { assertions++; if (!(expression)) { \
    fprintf(stderr, "motion start invariant failed: %s, line %d: %s\n", caseName, __LINE__, #expression); \
    exit(1); } } while (0)
static BOOL OverworldActorPolicy_Inspect(u8 slot, OverworldActorPolicyView *policy)
{ (void)slot; *policy = selectedPolicy; policy->motionPhase = motion.phase; return inspectOkay; }
static BOOL MapObject_IsSingleMovementActive(LocalMapObject *object) { return (object->flags & 2) != 0; }
static void MapObject_SetSingleMovementActive(LocalMapObject *object) { object->flags |= 2; }
static void MapObject_ClearSingleMovementActive(LocalMapObject *object) { object->flags &= ~2u; }
static void MapObject_StartMovementCommand(LocalMapObject *object, u32 command)
{
    object->movementCommand = command; object->movementStep = 0; object->flags &= ~32u;
    if (command == OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND) {
        shellStarts++;
        shellBeforeAdmission += !admitted;
    }
    if (command == OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_PREP_COMMAND) prepareCalls++;
    if (command == OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND) restoreCalls++;
}
static void MapObject_ClearHeldMovement(LocalMapObject *object)
{ object->flags = (object->flags & ~16u) | 32; object->movementCommand = 255; object->movementStep = 0; }
static BOOL MapObject_UpdateMovementCommand(LocalMapObject *object)
{
    if (object->movementCommand == OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_PREP_COMMAND) {
        if (!prepOkay) return FALSE;
        object->partnerPrepared = TRUE;
    }
    if (object->movementCommand == OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND) object->partnerPrepared = FALSE;
    /* Stock sub_02062428 consumes END, resets commandFF/step0 and clears bit5;
     * the caller must still clear SINGLE_MOVEMENT separately. */
    object->movementCommand = 255;
    object->movementStep = 0;
    object->flags &= ~32u;
    return TRUE;
}
/* @IMMEDIATE@ */
static const OverworldWildBehaviorProfileData *OverworldWildSpawns_GetBehaviorStateLane(const OverworldWildBehaviorProfile *profile, u8 state)
{ (void)state; return &profile->lane; }
static u8 OverworldWalk_DirectionKey(u8 direction) { return direction; }
static u8 OverworldWalk_DiagonalFacing(LocalMapObject *object, u8 direction, u8 key)
{ (void)object; (void)direction; (void)key; return 2; }
static BOOL OverworldWildSpawns_IsHeadbuttTreeTopLocation(FieldSystem *field, int x, int y)
{ (void)field; (void)x; (void)y; return FALSE; }
static int OverworldWildSpawns_MovementDirectionDeltaX(u8 direction) { return direction == 2 ? -1 : direction == 3; }
static int OverworldWildSpawns_MovementDirectionDeltaY(u8 direction) { return direction == 0 ? -1 : direction == 1; }
static void OverworldWildSpawns_ResolveObjectLandingHeight(FieldSystem *field, LocalMapObject *object, int x, int y)
{ (void)field; object->xCurr = x; object->yCurr = y; }
static void OverworldWildSpawns_SetObjectTile(LocalMapObject *object, int x, int y)
{ object->xCurr = x; object->yCurr = y; }
static s32 OverworldWildSpawns_GetObjectGroundBaseYAt(FieldSystem *field, LocalMapObject *object, int x, int y)
{ (void)field; (void)x; (void)y; return object->posVec[1]; }
static u8 OverworldWalk_ClampTime(u8 time) { return time ? time : 1; }
static const OverworldWildBehaviorDataBlob *OverworldWildSpawns_GetBehaviorDataBlob(void)
{ static const OverworldWildBehaviorDataBlob blob = {0}; return &blob; }
static OverworldMotionDecision OverworldWildSpawns_ResolveHopTrajectory(FieldSystem *field, const OverworldWildSurfaceCatalog *catalog,
    const OverworldWildBehaviorProfileData *lane, LocalMapObject *object, s32 base, s32 target,
    int x, int y, int tx, int ty, u8 distance, BOOL usesArc, u32 *trajectory)
{ (void)field; (void)catalog; (void)lane; (void)object; (void)base; (void)target; (void)x; (void)y;
  (void)tx; (void)ty; (void)distance; (void)usesArc; *trajectory = 8 | (24u << 16);
  return trajectoryOkay ? OVERWORLD_MOTION_DECISION_ACCEPTED : OVERWORLD_MOTION_DECISION_BLOCKED; }
static u8 OverworldWildSpawns_GetBehaviorHopSpinSpeed(const OverworldWildBehaviorProfile *profile, u8 state)
{ (void)profile; (void)state; return 0; }
static void OverworldWildSpawns_ClearStagedHopMovementListTask(OverworldWildSpawnState *state, int slot) { (void)state; (void)slot; }
static void OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary(OverworldWildSpawnState *state, FieldSystem *field, int slot)
{ (void)state; (void)field; (void)slot; }
static void OverworldWildSpawns_SetObjectFacing(LocalMapObject *object, u8 facing) { object->curFacing = facing; }
static void OverworldWildSpawns_ClearObjectFlags(LocalMapObject *object, u32 flags) { object->flags &= ~flags; }
static void OverworldWildSpawns_ClearCustomJumpLocal(OverworldWildSpawnState *state, int slot)
{ state->runtime.movementCustomJumpActive[slot] = FALSE; state->runtime.movementCustomMotionModes[slot] = OW_WILD_CUSTOM_MOTION_NONE; }
static void OverworldWildSpawns_StartCustomJump(OverworldWildSpawnState *state, int slot,
    int x, int y, int tx, int ty, s32 base, s32 target)
{ (void)base; (void)target; OverworldWildSpawns_ClearCustomJumpLocal(state, slot);
  state->runtime.movementCustomJumpActive[slot] = TRUE;
  state->runtime.movementCustomJumpStartX[slot] = x; state->runtime.movementCustomJumpStartY[slot] = y;
  state->runtime.movementCustomJumpTargetX[slot] = tx; state->runtime.movementCustomJumpTargetY[slot] = ty; }
static void OverworldWildSpawns_ReconcileNativeShadow(FieldSystem *field, LocalMapObject *object) { (void)field; (void)object; }
static void StopSE(int sound) { (void)sound; soundBeforeAdmission += !admitted; }
static void OverworldWildSpawns_PlayCanopyHopSE(OverworldWildSpawnState *state) { (void)state; soundBeforeAdmission += !admitted; }
static void OverworldWildSpawns_StartHopStartSoundSuppression(OverworldWildSpawnState *state, int slot)
{ (void)state; (void)slot; soundBeforeAdmission += !admitted; }
static void OverworldWildSpawns_SetPreviousTile(OverworldWildSpawnState *state, int slot, int x, int y) { (void)state; (void)slot; (void)x; (void)y; }
static OverworldMotionDecision OverworldWildSpawns_BeginSharedMotion(OverworldWildSpawnState *state, int slot, u8 facing,
    const OverworldWildBehaviorProfileData *lane, BOOL walk, BOOL reposition, u16 duration, u8 spin, u8 sway)
{
    (void)facing; (void)lane; (void)spin; (void)sway; beginCalls++;
    OverworldMotionPlan plan = {.version = OVERWORLD_MOTION_MODEL_VERSION,
        .kind = walk ? OVERWORLD_MOTION_KIND_WALK : reposition ? OVERWORLD_MOTION_KIND_REPOSITION : OVERWORLD_MOTION_KIND_HOP,
        .duration = duration, .startX = state->runtime.movementCustomJumpStartX[slot],
        .startY = state->runtime.movementCustomJumpStartY[slot], .targetX = state->runtime.movementCustomJumpTargetX[slot],
        .targetY = state->runtime.movementCustomJumpTargetY[slot]};
    if (!requestOkay) return OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;
    OverworldMotionDecision decision = OverworldMotion_Begin(&motion, &plan);
    admitted = decision == OVERWORLD_MOTION_DECISION_ACCEPTED;
    return decision;
}
static void OverworldWildSpawns_SetMovementSlotInProgress(OverworldWildSpawnState *state, int slot) { state->movementInProgressMask |= 1u << slot; }
static void OverworldWildSpawns_EnsureFrameMovementTask(OverworldWildSpawnState *state, FieldSystem *field) { (void)state; (void)field; taskCalls++; }
static void OverworldWildSpawns_RecordCustomJumpRamObject(OverworldWildSpawnState *state, int slot, LocalMapObject *object, int stage)
{ (void)state; (void)slot; (void)object; (void)stage; }
/* @START@ */

static void RunCase(unsigned mode, unsigned failure)
{
    static const char *names[] = {"success", "existing settlement", "profile failure", "trajectory failure", "prep failure", "admission failure"};
    caseName = names[failure];
    OverworldWildSpawnState state = {0}; FieldSystem field = {0};
    LocalMapObject object = {.xCurr = 551, .yCurr = 389, .posVec = {36143104, 65536, 25526272}, .flags = 1, .movementCommand = 255};
    OverworldWildBehaviorProfile profile = {0};
    inspectOkay = failure != 2; trajectoryOkay = failure != 3;
    prepOkay = failure != 4; requestOkay = failure != 5;
    shellStarts = prepareCalls = restoreCalls = beginCalls = taskCalls = 0;
    shellBeforeAdmission = soundBeforeAdmission = 0;
    admitted = FALSE;
    selectedPolicy = (OverworldActorPolicyView){.chainStepsRemaining = mode == 2 ? (0x80 | 0x20) : 0,
        .chainPauseAction = mode == 2 ? 0x95 : 0,
        .chainPauseTicks = 8, .actorActive = TRUE};
    memset(&motion, 0, sizeof(motion));
    if (failure == 1) {
        motion.phase = OVERWORLD_MOTION_PHASE_SETTLING;
        motion.plan.kind = OVERWORLD_MOTION_KIND_HOP;
        motion.plan.duration = motion.elapsed = 98;
        motion.plan.pauseFrames = 40;
        motion.plan.reservationId = 77;
    }
    OverworldMotionState preceding = motion;
    state.movementPendingDirections[0] = 7;
    state.movementPendingDistances[0] = 3;
    state.movementStagedHopDistances[0] = 6;
    OverworldWildSpawnState precedingAdapter = state;
    LocalMapObject precedingObject = object;
    OverworldMotionDecision reason = OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(
        &state, &field, 0, &object, 2, 1, 550, 390, &profile,
        mode == 0 ? OW_WILD_SPAWNER_CUSTOM_MOTION_WALK_FLAG : FALSE, 8);
    BOOL result = reason == OVERWORLD_MOTION_DECISION_ACCEPTED;
    cases++;
    CHECK(shellBeforeAdmission == 0 && soundBeforeAdmission == 0);
    if (failure == 0) {
        CHECK(reason == OVERWORLD_MOTION_DECISION_ACCEPTED);
        CHECK(result && shellStarts == 1 && beginCalls == 1);
        CHECK(MapObject_IsSingleMovementActive(&object));
        CHECK(object.movementCommand == OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND);
        CHECK((state.movementInProgressMask & 1) != 0 && taskCalls == 1);
        CHECK(motion.phase == OVERWORLD_MOTION_PHASE_MOVING);
        CHECK(object.partnerPrepared == (mode != 0));
    } else {
        static const u8 reasons[] = {OVERWORLD_MOTION_DECISION_ACCEPTED,
            OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE, OVERWORLD_MOTION_DECISION_PROFILE,
            OVERWORLD_MOTION_DECISION_BLOCKED, OVERWORLD_MOTION_DECISION_PROFILE,
            OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY};
        CHECK(reason == reasons[failure]);
        CHECK(state.movementPendingDirections[0] == 7);
        CHECK(state.movementPendingDistances[0] == 3);
        CHECK(state.movementStagedHopDistances[0] == 6);
        if (mode == 2) CHECK(object.curFacing == 0);
        CHECK(!result);
        CHECK(!MapObject_IsSingleMovementActive(&object));
        CHECK(shellStarts == 0); /* Native shell exists only for admitted work. */
        CHECK((state.movementInProgressMask & 1) == 0 && taskCalls == 0);
        CHECK(!object.partnerPrepared);
        CHECK(memcmp(&motion, &preceding, sizeof(motion)) == 0);
        if (failure == 1) {
            /* A still-owned pause must reject before local preparation,
             * facing writes, or a request that clears its adapter identity. */
            CHECK(beginCalls == 0 && prepareCalls == 0 && restoreCalls == 0);
            CHECK(memcmp(&state, &precedingAdapter, sizeof(state)) == 0);
            CHECK(memcmp(&object, &precedingObject, sizeof(object)) == 0);
        }
        CHECK(!state.runtime.movementCustomJumpActive[0]);
        CHECK(!state.runtime.movementCustomJumpPrepActive[0]);
        if (mode == 0 || prepareCalls == 0) CHECK(restoreCalls == 0);
    }
}
int main(void)
{
    /* Lead with the exact reported failure: Walk while spawn Hop settles. */
    RunCase(0, 1);
    for (unsigned mode = 0; mode < 3; mode++)
        for (unsigned failure = 0; failure < 6; failure++) {
            if (mode == 0 && (failure == 3 || failure == 4)) continue;
            if (mode == 0 && failure == 1) continue;
            RunCase(mode, failure);
        }
    printf("PASS %u motion-start cases, %u assertions\n", cases, assertions);
    return 0;
}
