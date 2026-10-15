/* Extracted production Reposition starts. World and motion admission are stubs. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef unsigned char u8;
typedef signed char s8;
typedef unsigned short u16;
typedef signed short s16;
typedef unsigned int u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OW_WILD_FOLLOWER_SLOT 0
#define OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT 0
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_CARDINAL_MASK 1
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER 0x4000
#define OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING 0x80
#define OW_WILD_SPAWNER_CHAIN_REPOSITION_FLAT_MASK 0x60
#define OW_WILD_SPAWNER_CHAIN_REPOSITION_SKID 0x20
#define OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER 0x90
#define OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER_MASK 0xF0
#define OW_WILD_SPAWNER_PREVIOUS_TILE_LOGICAL 1
#define OW_WILD_SPAWNER_PREVIOUS_TILE_PHYSICAL 2
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE 0xFF
#define OW_WILD_MAX_SPAWNS 1
#define MAPOBJECTFLAG_UNK7 0x80
#define OVERWORLD_MOUNT_CHAIN_PENDING 0x80
#define OVERWORLD_MOUNT_REPOSITION_FLAT_MASK 0x60
#define OVERWORLD_MOUNT_REPOSITION_SKID 0x20
#define OVERWORLD_MOUNT_ACTION_STATE_ACTION 0
#define OVERWORLD_MOUNT_ACTION_STATE_FIRST 1
#define OVERWORLD_MOUNT_ACTION_STATE_SECOND 2
#define OVERWORLD_MOUNT_ACTION_STATE_THIRD 3
#define OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST 1
#define OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION 1
#define OVERWORLD_MOTION_KIND_REPOSITION 3
#define OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_ADVANCE 1
#define OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH 2
#define OVERWORLD_ACTOR_WALK_POLICY_RESET 3
#define OVERWORLD_MOUNT_ACTION_FINAL 0
#define OVERWORLD_MOUNT_ACTION_STARTED 1
#define OVERWORLD_MOUNT_ACTION_RETRY 2
#define OW_WILD_CHAIN_COMPLETE 0
#define OW_WILD_CHAIN_RETRY 1
#define OW_WILD_CHAIN_STARTED 2
#define OW_WILD_CHAIN_ABORT 3

typedef enum OverworldMotionDecision {
    OVERWORLD_MOTION_DECISION_ACCEPTED,
    OVERWORLD_MOTION_DECISION_BLOCKED,
    OVERWORLD_MOTION_DECISION_TERRAIN,
    OVERWORLD_MOTION_DECISION_OCCUPIED,
    OVERWORLD_MOTION_DECISION_PROFILE,
    OVERWORLD_MOTION_DECISION_NO_CANDIDATE,
    OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY
} OverworldMotionDecision;
typedef struct FieldSystem { int unused; } FieldSystem;
typedef struct LocalMapObject { int xCurr, yCurr; } LocalMapObject;
typedef struct OverworldWildBehaviorProfileData {
    u8 chainRepositionJumpCount;
    u8 chainRepositionDistance;
    u8 chainRepositionDust;
    u8 directionAllow[2];
    u16 chillAllowedTerrainMask;
    u8 chainRepositionSpeed;
} OverworldWildBehaviorProfileData;
#define chainRepositionAllowCardinal directionAllow[0]
#define chainRepositionAllowDiagonal directionAllow[1]
typedef struct OverworldWildBehaviorProfile {
    OverworldWildBehaviorProfileData lane;
} OverworldWildBehaviorProfile;
typedef struct OverworldWildSpawn { LocalMapObject *object; } OverworldWildSpawn;
typedef struct OverworldWildSpawnState {
    u8 movementSpotStates[1];
    u8 movementPendingDirections[1];
    u8 movementPendingDistances[1];
    u8 movementPreviousTileLocked[1];
    u8 movementLastDirections[1];
    u8 movementLastDistances[1];
    u8 movementStagedHopPending[1];
    FieldSystem *movementFieldSystem;
    OverworldWildSpawn spawns[1];
    struct { s16 lastKnownX[1], lastKnownY[1]; } spawnPresentations;
} OverworldWildSpawnState;
#define OW_WILD_RUNTIME(state) (state)
typedef struct OverworldWildChainRepositionResult {
    u8 encodedRemaining;
    u8 outcome;
    u8 reason;
    s8 gridDelta;
} OverworldWildChainRepositionResult;
typedef struct OverworldActorPolicyView {
    u8 chainPauseAction;
    u8 chainStepsRemaining;
} OverworldActorPolicyView;
typedef struct OverworldActorWalkPolicyCall { u8 operation; } OverworldActorWalkPolicyCall;
typedef struct OverworldMountRuntimeState {
    struct { OverworldWildBehaviorProfileData profile; } snapshot;
    FieldSystem *fieldSystem;
    u8 reservedPriorFollowerPolicy[4];
} OverworldMountRuntimeState;
typedef struct FIELD_PLAYER_AVATAR { LocalMapObject *mapObject; } FIELD_PLAYER_AVATAR;
typedef struct OverworldMountActionCall {
    OverworldMountRuntimeState *state;
    FIELD_PLAYER_AVATAR *avatar;
    u8 action;
} OverworldMountActionCall;

static int g_mode, g_blocked_at, g_side_block, g_start_index, g_reset_chain;
static int g_start_count, g_target_x, g_target_y, g_distance;
static int g_reduce_finish, g_reduce_advance;

static u32 gf_rand(void) { return (u32)g_start_index; }
static BOOL OverworldActorPolicy_Inspect(u8 slot, OverworldActorPolicyView *policy)
{
    (void)slot;
    policy->chainPauseAction = g_mode == 2 ? 0x96 : 0x95;
    policy->chainStepsRemaining = g_reset_chain
        ? OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING
            | OW_WILD_SPAWNER_CHAIN_REPOSITION_SKID : 0;
    return TRUE;
}
static void OverworldWildSpawns_InitPolicyCall(
    OverworldActorWalkPolicyCall *call, int slot, u8 operation)
{ (void)slot; call->operation = operation; }
static BOOL OverworldWildSpawns_ReduceWalk(OverworldActorWalkPolicyCall *call)
{ (void)call; return TRUE; }
static BOOL OverworldWildSpawns_MountIsActive(void) { return FALSE; }
static void OverworldWildSpawns_ClearObjectFlags(LocalMapObject *object, u8 flags)
{ (void)object; (void)flags; }
static void OverworldWildSpawns_ResolveObjectLandingHeight(
    FieldSystem *field, LocalMapObject *object, int x, int y)
{ (void)field; (void)object; (void)x; (void)y; }
static int IsBlocked(int x, int y)
{
    if (g_mode == 0) {
        return y != 10 || x < 10 || x == 10 + g_blocked_at;
    }
    if (g_mode == 2) return !((y == 10 && x >= 10 && x <= 13)
        || (x == 10 && y >= 7 && y <= 10));
    if (x < 10 || y < 10 || x > 13 || y > 13) return 1;
    if (x == 10 && y == 10) return 0;
    if (x == y) return x == 10 + g_blocked_at;
    if (abs(x - y) == 1) return g_side_block && x == 12 && y == 11;
    return 1;
}
static const OverworldWildBehaviorProfileData *
OverworldWildSpawns_GetControllerLane(const OverworldWildBehaviorProfile *profile, u8 spot)
{ (void)spot; return &profile->lane; }
static OverworldMotionDecision OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
    OverworldWildSpawnState *state, int slot, FieldSystem *fieldSystem,
    u16 allowed, int x, int y, int finalX, int finalY)
{
    (void)state; (void)slot; (void)fieldSystem; (void)allowed;
    (void)finalX; (void)finalY;
    if (g_mode == 2 && x > 10) return OVERWORLD_MOTION_DECISION_BLOCKED;
    return IsBlocked(x, y) ? OVERWORLD_MOTION_DECISION_BLOCKED
        : OVERWORLD_MOTION_DECISION_ACCEPTED;
}
static OverworldMotionDecision OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(
    OverworldWildSpawnState *state, FieldSystem *fieldSystem, int slot,
    LocalMapObject *object, u8 direction, u8 distance, int targetX,
    int targetY, const OverworldWildBehaviorProfile *profile,
    BOOL suppressHopStartSound, u8 walkTime)
{
    (void)fieldSystem; (void)object; (void)profile;
    (void)suppressHopStartSound; (void)walkTime;
    g_start_count++; g_target_x = targetX; g_target_y = targetY;
    g_distance = distance;
    state->movementPendingDirections[slot] = direction;
    state->movementPendingDistances[slot] = distance;
    return OVERWORLD_MOTION_DECISION_ACCEPTED;
}
static u8 *OverworldMountAction_State(OverworldMountRuntimeState *state)
{ return state->reservedPriorFollowerPolicy; }
static int ValidateHopLanding(u8 version, int slot, FieldSystem *fieldSystem,
    u16 allowed, int x, int y, int finalX, int finalY)
{
    (void)version; (void)slot; (void)fieldSystem; (void)allowed;
    (void)finalX; (void)finalY;
    if (g_mode == 2 && x > 10) return FALSE;
    return !IsBlocked(x, y);
}
static struct { int (*validateHopLanding)(u8, int, FieldSystem *, u16,
    int, int, int, int); } g_wild_entry = { ValidateHopLanding };
#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY (&g_wild_entry)
static BOOL OverworldMountAction_IsOccupied(OverworldMountRuntimeState *state,
    LocalMapObject *player, int x, int y)
{ (void)state; (void)player; return IsBlocked(x, y); }
static BOOL OverworldMountAction_IsWalkStepOpen(
    OverworldMountRuntimeState *state, int x, int y, int dx, int dy)
{
    (void)state;
    return !(dx && dy && (IsBlocked(x + dx, y) || IsBlocked(x, y + dy)))
        && !IsBlocked(x + dx, y + dy);
}
static OverworldMotionDecision OverworldMountAction_PlanReposition(
    OverworldMountRuntimeState *state, LocalMapObject *player, u8 action,
    u8 distance, int targetX, int targetY, u16 *duration, u8 *arcHeightQ4)
{
    (void)state; (void)player; (void)action; (void)distance;
    (void)targetX; (void)targetY;
    *duration = 4; *arcHeightQ4 = 0;
    return OVERWORLD_MOTION_DECISION_ACCEPTED;
}
static u8 OverworldMountAction_StartMotion(OverworldMountActionCall *call,
    u8 kind, u8 direction, int targetX, int targetY, u8 distance,
    u16 duration, u8 arcHeightQ4)
{
    (void)call; (void)kind; (void)direction; (void)duration; (void)arcHeightQ4;
    g_start_count++; g_target_x = targetX; g_target_y = targetY;
    g_distance = distance;
    return OVERWORLD_MOUNT_ACTION_STARTED;
}
static BOOL OverworldMountAction_Reduce(OverworldMountRuntimeState *state,
    u8 operation, u8 direction, u8 distance)
{
    (void)state; (void)direction; (void)distance;
    if (operation == OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_ADVANCE)
        g_reduce_advance++;
    if (operation == OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH)
        g_reduce_finish++;
    return TRUE;
}
static void OverworldMountAction_Boundary(OverworldMountRuntimeState *state,
    u8 acknowledgement, u8 reason)
{ (void)state; (void)acknowledgement; (void)reason; }
#define OVERWORLD_ACTOR_BOUNDARY_CANCEL 1

/* @WILD@ */
/* @MOUNT@ */
/* @RESET@ */
/* @HISTORY@ */

static void Reset(int mode, int blockedAt, int sideBlock)
{
    g_mode = mode;
    g_blocked_at = blockedAt;
    g_side_block = sideBlock;
    g_start_index = mode == 1 ? 7 : 3;
    g_reset_chain = 0;
    g_start_count = g_target_x = g_target_y = g_distance = 0;
    g_reduce_finish = g_reduce_advance = 0;
}
static void Check(const char *actor, const char *caseName, int expectedX,
    int expectedY, int expectedDistance, int expectedCrash, int marker)
{
    if (g_start_count != 1 || g_target_x != expectedX
        || g_target_y != expectedY || g_distance != expectedDistance
        || (!!(marker & 0x80)) != expectedCrash) {
        fprintf(stderr, "Reposition skid collision failed: %s %s: starts=%d "
            "target=(%d,%d) distance=%d crash=%d\n", actor, caseName,
            g_start_count, g_target_x, g_target_y, g_distance,
            !!(marker & 0x80));
        exit(1);
    }
}
static void RunWild(int mode, int blockedAt, int sideBlock,
    const char *caseName, int x, int y, int distance, int crash)
{
    FieldSystem field = {0};
    LocalMapObject object = {10, 10};
    OverworldWildBehaviorProfile profile = {0};
    OverworldWildSpawnState state = {0};
    OverworldWildChainRepositionResult result = {0};
    Reset(mode, blockedAt, sideBlock);
    state.spawns[0].object = &object;
    state.movementFieldSystem = &field;
    profile.lane.chainRepositionJumpCount = 1;
    profile.lane.chainRepositionDistance = 3;
    profile.lane.chainRepositionAllowCardinal = mode != 1;
    profile.lane.chainRepositionAllowDiagonal = mode == 1;
    (void)OverworldWildSpawns_RunChainReposition(&state, 0, &profile,
        OW_WILD_SPAWNER_CHAIN_REPOSITION_SKID, &result);
    Check("Wild", caseName, x, y, distance, crash,
        state.movementPendingDistances[0]);
    if (result.outcome != OW_WILD_CHAIN_STARTED
        || state.movementPreviousTileLocked[0]
            != OW_WILD_SPAWNER_PREVIOUS_TILE_PHYSICAL) {
        fprintf(stderr, "Reposition skid collision failed: Wild %s outcome=%d lock=%d\n",
            caseName, result.outcome, state.movementPreviousTileLocked[0]);
        exit(1);
    }
}
static void RunMount(int mode, int blockedAt, int sideBlock,
    const char *caseName, int x, int y, int distance, int crash)
{
    FieldSystem field = {0};
    LocalMapObject object = {10, 10};
    FIELD_PLAYER_AVATAR avatar = {&object};
    OverworldMountRuntimeState state = {0};
    OverworldMountActionCall call = {&state, &avatar, 6};
    Reset(mode, blockedAt, sideBlock);
    state.fieldSystem = &field;
    state.snapshot.profile.chainRepositionJumpCount = 1;
    state.snapshot.profile.chainRepositionDistance = 3;
    state.snapshot.profile.chainRepositionAllowCardinal = mode != 1;
    state.snapshot.profile.chainRepositionAllowDiagonal = mode == 1;
    if (OverworldMountAction_RunReposition(&call,
            OVERWORLD_MOUNT_REPOSITION_SKID) != OVERWORLD_MOUNT_ACTION_STARTED) {
        fprintf(stderr, "Reposition skid collision failed: Mount %s rejected\n",
            caseName);
        exit(1);
    }
    Check("Mount", caseName, x, y, distance, crash,
        state.reservedPriorFollowerPolicy[OVERWORLD_MOUNT_ACTION_STATE_THIRD]);
    if (g_reduce_advance != 1 || g_reduce_finish != 0) {
        fprintf(stderr, "Reposition skid collision failed: Mount %s chain=%d/%d\n",
            caseName, g_reduce_advance, g_reduce_finish);
        exit(1);
    }
}
static void CheckResetHistory(int pending, int pendingChain, int lock,
    int previous, int expected)
{
    OverworldWildSpawnState state = {0};
    LocalMapObject object = {10, 10};
    Reset(0, 0, 0);
    g_reset_chain = pendingChain;
    state.spawns[0].object = &object;
    state.movementPendingDirections[0] = 3;
    state.movementPendingDistances[0] = (u8)pending;
    state.movementPreviousTileLocked[0] = (u8)lock;
    state.movementLastDistances[0] = (u8)previous;
    OverworldWildSpawns_ClearWalkMovementState(&state, 0, &object);
    OverworldWildSpawns_RecordFinishedMovementHistory(&state, 0);
    if ((lock == OW_WILD_SPAWNER_PREVIOUS_TILE_LOGICAL
            && state.movementLastDirections[0] != 3)
        || (lock == OW_WILD_SPAWNER_PREVIOUS_TILE_PHYSICAL
            && state.movementLastDirections[0] != 0)
        || state.movementLastDistances[0] != expected
        || state.movementPendingDistances[0] != 0) {
        fprintf(stderr, "Reposition skid reset/history failed: pending=%d "
            "chain=%d lock=%d last=%d cleared=%d\n", pending, pendingChain,
            lock,
            state.movementLastDistances[0], state.movementPendingDistances[0]);
        exit(1);
    }
}
int main(int argc, char **argv)
{
    int only = argc > 1 ? atoi(argv[1]) : 0;
#define RUN_CASE(n, call) do { if (only == 0 || only == (n)) { call; } } while (0)
    RUN_CASE(1, RunWild(0, 3, 0, "blocked endpoint", 12, 10, 2, 1));
    RUN_CASE(2, RunWild(0, 2, 0, "blocked middle", 11, 10, 1, 1));
    RUN_CASE(3, RunWild(0, 1, 0, "blocked first", 10, 10, 1, 1));
    RUN_CASE(4, RunWild(0, 0, 0, "clear", 13, 10, 3, 0));
    RUN_CASE(5, RunWild(1, 0, 1, "diagonal side", 11, 11, 1, 1));
    RUN_CASE(6, RunMount(0, 3, 0, "blocked endpoint", 12, 10, 2, 1));
    RUN_CASE(7, RunMount(0, 2, 0, "blocked middle", 11, 10, 1, 1));
    RUN_CASE(8, RunMount(0, 1, 0, "blocked first", 10, 10, 0, 1));
    RUN_CASE(9, RunMount(0, 0, 0, "clear", 13, 10, 3, 0));
    RUN_CASE(10, RunMount(1, 0, 1, "diagonal side", 11, 11, 1, 1));
    RUN_CASE(11, RunWild(2, 0, 0, "grid rejects east then up", 10, 7, 3, 0));
    RUN_CASE(12, RunMount(2, 0, 0, "grid rejects east then up", 10, 7, 3, 0));
    RUN_CASE(13, CheckResetHistory(0x82, 1,
        OW_WILD_SPAWNER_PREVIOUS_TILE_PHYSICAL, 7, 7));
    RUN_CASE(14, CheckResetHistory(200, 0,
        OW_WILD_SPAWNER_PREVIOUS_TILE_LOGICAL, 7, 200));
    puts("PASS extracted Reposition skid clear-prefix admission");
    return 0;
}
