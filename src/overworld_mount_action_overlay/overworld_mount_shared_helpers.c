#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/overworld_wild_runtime.h"
#include "../../include/map_events_internal.h"
#include "../../include/constants/sndseq.h"

__asm__(".thumb\n.thumb_func\n.thumb_set OverworldMountWalkProposal_SaveReserved, 0x01FFF480\n");

/* Overlay 160 is boot-resident beside Mount. These helpers use Mount's one
 * fixed runtime state; they do not hold a second actor or motion state. */
#define MOUNT_STATE \
    ((OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR)
#define OVERWORLD_MOUNT_DIRECTION_NONE OW_WILD_WALK_DIRECTION_NONE
#define OVERWORLD_MOUNT_STOP_SKID_PAUSE_FRAMES 8

__asm__(
    ".thumb\n"
    ".thumb_func\n.thumb_set OverworldMount_GetSurfaceId, 0x01FF9A70\n"
    ".thumb_func\n.thumb_set OverworldMount_PlayCrashSound, 0x023BB740\n"
    ".thumb_func\n.thumb_set OverworldActor_PlayStompSound, 0x023BA118\n");

extern u16 OverworldMount_GetSurfaceId(int targetX, int targetY);
extern void OverworldMount_PlayCrashSound(u32 sequence);

typedef struct OverworldMountTeleportWorldContext {
    LocalMapObject *player;
} OverworldMountTeleportWorldContext;

BOOL __attribute__((noinline, used,
    section(".overworld_mount_landing_allowed")))
OverworldMount_IsLandingTileAllowed(int targetX, int targetY)
{
    const OverworldMountRuntimeState *state = MOUNT_STATE;

    return targetX >= 0
        && targetY >= 0
        && OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->validateHopLanding(
            OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION,
            OW_WILD_FOLLOWER_SLOT,
            state->fieldSystem,
            state->snapshot.profile.chillAllowedTerrainMask,
            targetX,
            targetY,
            targetX,
            targetY);
}

void __attribute__((noinline, used,
    section(".overworld_mount_teleport_classify")))
OverworldMount_ClassifyTeleportCandidate(
    void *rawContext,
    OverworldActorTeleportCandidate *candidate)
{
    OverworldMountTeleportWorldContext *context = rawContext;
    const OverworldMountRuntimeState *state = MOUNT_STATE;

    if (!OverworldMount_IsLandingTileAllowed(
            candidate->targetX,
            candidate->targetY)) {
        candidate->rejectionFlags |= OVERWORLD_MOTION_CANDIDATE_BAD_TERRAIN;
        return;
    }
    candidate->targetSurfaceId = OverworldMount_GetSurfaceId(
        candidate->targetX,
        candidate->targetY);
    candidate->targetBaseY =
        OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
            state->fieldSystem,
            state->surfaceCatalog,
            context->player,
            candidate->targetX,
            candidate->targetY);
}

void __attribute__((noinline, used,
    section(".overworld_mount_walk_policy_output")))
OverworldMount_ApplyWalkPolicyOutput(
    FIELD_PLAYER_AVATAR *avatar,
    LocalMapObject *follower,
    const OverworldActorWalkPolicyCall *call)
{
    OverworldMountRuntimeState *state = MOUNT_STATE;

    if (call->decision == OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP) {
        OverworldMountWalkProposal_SaveReserved(call);
        state->reservedPolicyProfile[
            OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX] = call->reserved[0];
        state->reservedPolicyState[
            OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX] = call->stepFlags;
        state->reservedPolicyProfile[
            OVERWORLD_MOUNT_WALK_SKID_PATH_TILES_INDEX] =
                call->reserved[
                    OVERWORLD_ACTOR_WALK_POLICY_SKID_PATH_TILES_INDEX];
        state->reservedPolicyState[
            OVERWORLD_MOUNT_WALK_STEP_DIRECTION_INDEX] = call->stepDirection;
        state->reservedPolicyState[
            OVERWORLD_MOUNT_WALK_FACING_DIRECTION_INDEX] =
                call->facingDirection;
        state->reservedPolicyState[
            OVERWORLD_MOUNT_WALK_TRAVEL_TIME_INDEX] = call->travelTime;
    }
    if ((call->stepFlags
            & OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION) != 0) {
        avatar->mapObject->flags &= ~MAPOBJECTFLAG_UNK7;
    }
    if (call->effect == OVERWORLD_ACTOR_WORLD_EFFECT_NONE) {
        return;
    }
    if (call->effect == OVERWORLD_ACTOR_WORLD_EFFECT_CRASH) {
        OverworldMount_PlayCrashSound(SEQ_SE_DP_WALL_HIT);
        return;
    }
    if (follower != NULL) {
        OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->playLandingHopParticle(follower);
        if (call->effect == OVERWORLD_ACTOR_WORLD_EFFECT_STOMP) {
            OverworldActor_PlayStompSound(call->lane->walkOptions);
        } else if (call->facingDirection
            == OVERWORLD_MOUNT_DIRECTION_NONE) {
            state->motionCooldown = OVERWORLD_MOUNT_STOP_SKID_PAUSE_FRAMES;
        }
    }
}

BOOL __attribute__((noinline, used,
    section(".overworld_mount_ordinary_direction")))
OverworldMount_GetOrdinaryDirection(u32 movementCommand, u8 *directionOut)
{
    u8 direction;

    for (direction = 0; direction <= 3; direction++) {
        if (movementCommand == MapObject_MovementCommandFromDirection(
                direction, OVERWORLD_MOUNT_WALK_COMMAND)
            || movementCommand == MapObject_MovementCommandFromDirection(
                direction, OVERWORLD_MOUNT_RUN_COMMAND)) {
            *directionOut = direction;
            return TRUE;
        }
    }
    return FALSE;
}

BOOL __attribute__((noinline, used,
    section(".overworld_mount_finalize_pending")))
OverworldMount_FinalizeIsPending(void)
{
    const OverworldMountRuntimeState *state = MOUNT_STATE;

    return (state->reservedPolicyState[OVERWORLD_MOUNT_BOUNDARY_FLAGS_INDEX]
        & OVERWORLD_MOUNT_BOUNDARY_FINALIZE_PENDING) != 0;
}

void __attribute__((naked, noinline, used,
    section(".overworld_mount_follower_cooldown")))
OverworldMount_ClearFollowerDecisionCooldown(void)
{
    __asm__(
        "mov r2, #0\n"
        "ldr r3, 1f\n"
        "strb r2, [r3, #0]\n"
        "bx lr\n"
        ".align 2\n"
        "1: .word sOverworldWildSpawnState + 0xF4\n");
}

typedef char OverworldMountPlayerBaseFaceOffsetMustRemain112[
    offsetof(OverworldMountRuntimeState, playerBaseFaceY) == 112 ? 1 : -1];
typedef char OverworldMountPlayerBaseUnk88OffsetMustRemain116[
    offsetof(OverworldMountRuntimeState, playerBaseUnk88Y) == 116 ? 1 : -1];
typedef char OverworldMountLastFaceOffsetMustRemain184[
    offsetof(OverworldMountRuntimeState, lastAppliedPlayerFaceY) == 184 ? 1 : -1];
typedef char OverworldMountRuntimeSizeMustRemain188[
    sizeof(OverworldMountRuntimeState) == 188 ? 1 : -1];
typedef char OverworldMountPlayerFaceInputOffsetMustRemain128[
    offsetof(LocalMapObject, faceVec[1]) == 128 ? 1 : -1];
typedef char OverworldMountPlayerUnk88InputOffsetMustRemain140[
    offsetof(LocalMapObject, unk88[1]) == 140 ? 1 : -1];

/* The state-base literal points 64 bytes into the fixed state, putting all
 * four Y caches within Thumb's short load/store range. */
void __attribute__((naked, noinline, used,
    section(".overworld_mount_player_base")))
OverworldMount_UpdatePlayerBaseHeight(LocalMapObject *player)
{
    __asm__(
        "add r0, #128\n"
        "ldr r2, [r0, #0]\n"
        "ldr r3, 1f\n"
        "ldr r1, [r3, #124]\n"
        "cmp r2, r1\n"
        "beq 2f\n"
        "str r2, [r3, #48]\n"
        "2: add r0, #12\n"
        "ldr r2, [r0, #0]\n"
        "ldr r1, [r3, #120]\n"
        "cmp r2, r1\n"
        "beq 3f\n"
        "str r2, [r3, #52]\n"
        "3: bx lr\n"
        ".align 2\n"
        "1: .word 0x023BC784\n");
}
