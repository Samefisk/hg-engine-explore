#include "../../include/overworld_mount.h"
#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_wild_spawns_internal.h"

#include "../../include/constants/buttons.h"
#include "../../include/constants/sndseq.h"
#include "../../include/constants/species.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_follower_selector.h"
#include "../../include/overworld_wild_movement.h"
#include "../../include/overworld_wild_runtime.h"
#include "../../include/overworld_walk_module.h"
#include "../../include/save.h"
#include "../../include/script.h"
#include "../../include/sound.h"

#pragma GCC optimize("Os")

#define OVERWORLD_MOUNT_TOGGLE_BUTTON PAD_BUTTON_SELECT
#define OVERWORLD_MOUNT_RIDER_HEIGHT_FX32 0x8000
#define OVERWORLD_MOUNT_IDLE_COOLDOWN 0xFF
#define OVERWORLD_MOUNT_DIRECTION_NONE OW_WILD_WALK_DIRECTION_NONE
#define OVERWORLD_MOUNT_DIRECTION_NORTH 0
#define OVERWORLD_MOUNT_DIRECTION_SOUTH 1
#define OVERWORLD_MOUNT_DIRECTION_WEST 2
#define OVERWORLD_MOUNT_DIRECTION_EAST 3
#define OVERWORLD_MOUNT_DIRECTION_NORTH_WEST 4
#define OVERWORLD_MOUNT_DIRECTION_NORTH_EAST 5
#define OVERWORLD_MOUNT_DIRECTION_SOUTH_WEST 6
#define OVERWORLD_MOUNT_DIRECTION_SOUTH_EAST 7
#define OVERWORLD_MOUNT_PLAYER_MOVE_STATE_NONE 0
#define OVERWORLD_MOUNT_PLAYER_MOVE_STATE_END 3
#define OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT (1u << 0)
#define OVERWORLD_MOUNT_TELEPORT_MAX_DISTANCE 6
#define OVERWORLD_MOUNT_HOP_MAX_DISTANCE 16
#define OVERWORLD_MOUNT_TELEPORT_FLICKER_PHASE_FRAMES 2
#define OVERWORLD_MOUNT_CRASH_SHAKE_FRAMES 32
#define OVERWORLD_MOUNT_CRASH_SHAKE_FX32 0x2000
#define OVERWORLD_MOUNT_WALK_COMMAND 0x0C
#define OVERWORLD_MOUNT_RUN_COMMAND 0x58
#define OVERWORLD_MOUNT_WALK_FREEZE_COMMAND 0x3C
#define OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND 0x3E
#define OVERWORLD_MOUNT_FIELD_INPUT_END_MOVEMENT (1u << 1)
#define OVERWORLD_MOUNT_FIELD_INPUT_SIGN (1u << 5)
#define OVERWORLD_MOUNT_FIELD_INPUT_MAP_TRANSITION (1u << 6)
#define OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT (1u << 7)
/* These object-event sprite IDs resolve to overworld models 0073
 * (swimhero.pal) and 0074 (swimheroine.pal), respectively. */
#define OVERWORLD_MOUNT_RIDER_SPRITE_MALE 178
#define OVERWORLD_MOUNT_RIDER_SPRITE_FEMALE 179

typedef struct OverworldMountFieldInput {
    u16 flags;
    u16 unk2;
    u8 playerDirection;
    s8 transitionDirection;
    u16 newKeys;
    u16 heldKeys;
    u16 unkA;
} OverworldMountFieldInput;

static OverworldMountRuntimeState sOverworldMountState;
static u32 sOverworldMountNextSessionGeneration;

#define OW_WILD_POLICY_LOOK_PLAN_BASE_MASK 0x03
#define OW_WILD_POLICY_LOOK_PLAN_FIRST_SHIFT 2
#define OW_WILD_POLICY_LOOK_PLAN_SECOND_SHIFT 4
#define OW_WILD_POLICY_LOOK_PLAN_TWO_GLANCES (1u << 6)

static u8 OverworldWildMovementPolicy_BuildLookPlan(u8 baseDirection)
{
    u8 firstDirection;
    u8 secondDirection = baseDirection;
    BOOL twoGlances = (gf_rand() & 1u) != 0;

    do {
        firstDirection = gf_rand() & OW_WILD_POLICY_LOOK_PLAN_BASE_MASK;
    } while (firstDirection == baseDirection);
    if (twoGlances) {
        secondDirection = baseDirection ^ 1u;
        if (secondDirection == firstDirection) {
            secondDirection = baseDirection ^ 2u;
        }
    }
    return baseDirection
        | (firstDirection << OW_WILD_POLICY_LOOK_PLAN_FIRST_SHIFT)
        | (secondDirection << OW_WILD_POLICY_LOOK_PLAN_SECOND_SHIFT)
        | (twoGlances ? OW_WILD_POLICY_LOOK_PLAN_TWO_GLANCES : 0);
}

static int OverworldWildMovementPolicy_ResolveLook(
    u8 lookPlan,
    u8 phase,
    u8 totalFrames,
    u8 remainingFrames)
{
    BOOL twoGlances = (lookPlan & OW_WILD_POLICY_LOOK_PLAN_TWO_GLANCES) != 0;
    u8 shift = 0;

    if (totalFrames != 0) {
        if (phase == OW_WILD_MOVEMENT_POLICY_LOOK_SECOND
            && remainingFrames > (twoGlances
                    ? (totalFrames * 2) / 3
                    : totalFrames / 2)) {
            return -1;
        }
        if (phase == OW_WILD_MOVEMENT_POLICY_LOOK_RETURN
            && remainingFrames > (twoGlances
                    ? totalFrames / 3
                    : totalFrames / 2)) {
            return -1;
        }
    }
    if (phase == OW_WILD_MOVEMENT_POLICY_LOOK_FIRST) {
        shift = OW_WILD_POLICY_LOOK_PLAN_FIRST_SHIFT;
    } else if (phase == OW_WILD_MOVEMENT_POLICY_LOOK_SECOND) {
        shift = OW_WILD_POLICY_LOOK_PLAN_SECOND_SHIFT;
    }
    return (lookPlan >> shift) & OW_WILD_POLICY_LOOK_PLAN_BASE_MASK;
}

static int OverworldWildMovementPolicy_ChooseWanderDirection(
    const u8 *directions,
    int directionCount,
    u8 previousDirection,
    u8 chance)
{
    int i;

    if (chance == 100 || (chance != 0 && (gf_rand() % 100) < chance)) {
        for (i = 0; i < directionCount; i++) {
            if (directions[i] == previousDirection) {
                return i;
            }
        }
    }
    /* A negative value below -1 tells Wander to exclude the old direction.
     * This makes the authored percentage exact instead of only a preference. */
    return -2;
}

static inline __attribute__((always_inline)) void
OverworldWildMovementPolicy_RecordCompletedWalkTile(
    OverworldWildWalkMomentumState *walkMomentum,
    BOOL resetForWait)
{
    if (resetForWait) {
        walkMomentum->turnDirection = 0;
    } else if (walkMomentum->turnDirection != 0xFE) {
        walkMomentum->turnDirection++;
    }
}

static BOOL OverworldWildMovementPolicy_PrepareChainPause(
    u8 *stepsRemaining,
    u8 *deferredPauseTicks,
    u8 *deferredPauseAction,
    u8 *variancePhase,
    OverworldWildWalkMomentumState *walkMomentum,
    const OverworldWildBehaviorProfileData *lane,
    u8 locomotion)
{
    u8 pauseAction = lane->chainPauseAction;
    u8 pauseTicks;
    u32 pauseFrames;

    if (locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WALK) {
        OverworldWildMovementPolicy_RecordCompletedWalkTile(
            walkMomentum,
            lane->walkPause != 0);
    }
    if (pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE) {
        *deferredPauseTicks = 0;
        goto chain_disabled;
    }
    if ((locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WALK
            && !OW_WILD_BEHAVIOR_WALK_ALLOWS_TURNING(lane->walkOptions))
        || lane->ramAccelerationSteps == 0
        || !((locomotion >= OW_WILD_BEHAVIOR_LOCOMOTION_WALK
                && locomotion <= OW_WILD_BEHAVIOR_LOCOMOTION_HOP)
            || locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT)) {
chain_disabled:
        *stepsRemaining = 0;
        *deferredPauseAction = 0;
        return FALSE;
    }
    if (*stepsRemaining == 0) {
        *stepsRemaining = lane->ramAccelerationSteps;
        if (lane->chainMovementVariance != 0) {
            *variancePhase = (u8)(*variancePhase * 73u + 41u);
            *stepsRemaining += (u8)(((u16)*variancePhase
                * (lane->chainMovementVariance + 1u)) >> 8);
        }
    }
    (*stepsRemaining)--;
    if (*stepsRemaining != 0) {
        return FALSE;
    }
    if (lane->chainPauseActionChance != 0
        && lane->chainPauseActionChance < 100
        && (gf_rand() % 100) >= lane->chainPauseActionChance) {
        return FALSE;
    }
    if (pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE) {
        pauseTicks = 0;
    } else if (pauseAction >= OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_STEPS) {
        pauseTicks = lane->chainRepositionSpeed;
    } else {
        pauseFrames = lane->ramMaxSpeed;
        if (pauseFrames == 0
            && pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND) {
            pauseFrames = 60;
        }
        *variancePhase = (u8)(*variancePhase * 73u + 41u);
        pauseFrames += (u8)(((u16)*variancePhase
            * (lane->chainPauseVariance + 1u)) >> 8);
        pauseTicks = (u8)((pauseFrames + 1u) / 2u);
        if (pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS) {
            pauseTicks /= lane->chainRepositionJumpCount;
            if (pauseTicks == 0) {
                pauseTicks = 1;
            }
            pauseTicks += pauseTicks;
        }
    }
    *deferredPauseTicks = pauseTicks;
    *deferredPauseAction = pauseAction | 0x80;
    return TRUE;
}

const OverworldWildMovementPolicyEntry gOverworldWildMovementPolicyEntry
    __attribute__((section(".overworld_wild_movement_policy_entry"), used)) = {
        OverworldWildMovementPolicy_BuildLookPlan,
        OverworldWildMovementPolicy_ResolveLook,
        OverworldWildMovementPolicy_ChooseWanderDirection,
        OverworldWildMovementPolicy_PrepareChainPause,
    };

static void OverworldMount_FinishCustomMotion(void);
static void OverworldMount_UpdateCustomMotion(void);
static void OverworldMount_DrainLandStream(void);
static void OverworldMount_ResumeCustomMotionAfterMapTransition(void);
static BOOL __attribute__((noinline))
OverworldMount_CompletePendingStep(FIELD_PLAYER_AVATAR *avatar);
static void OverworldMount_ResetMomentum(void);
void OverworldMount_IssueHeldMovement(
    FIELD_PLAYER_AVATAR *avatar,
    LocalMapObject *object,
    u32 vanillaCommand);
static int OverworldMount_DirectionDeltaX(u8 direction);
static int OverworldMount_DirectionDeltaY(u8 direction);
void OverworldMount_PlayCrashSound(u32 sequence);
extern void LONG_CALL ov01_021F62E8(
    VecFx32 *position,
    void *landDataManager);

static void * __attribute__((noinline, section(".overworld_mount_streaming")))
OverworldMount_GetLandDataManager(void)
{
    return *(void **)((u8 *)sOverworldMountState.fieldSystem + 0x2C);
}

static void __attribute__((noinline, section(".overworld_mount_streaming")))
OverworldMount_RestoreLandStreamTarget(LocalMapObject *player)
{
    if (sOverworldMountState.motionStreamPreparing) {
        ov01_021F62E8(
            (VecFx32 *)player->posVec,
            OverworldMount_GetLandDataManager());
    }
}

static void __attribute__((noinline))
OverworldMount_StartWalkCrash(void)
{
    if (sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_NONE
        && !OW_WILD_BEHAVIOR_WALK_ALLOWS_TURNING(
            sOverworldMountState.walkOptions)
        && sOverworldMountState.direction
            != OVERWORLD_MOUNT_DIRECTION_NONE) {
        sOverworldMountState.snapshot.motionMode =
            OVERWORLD_MOUNT_MOTION_CRASH;
        sOverworldMountState.motionFrameCount =
            OVERWORLD_MOUNT_CRASH_SHAKE_FRAMES;
        sOverworldMountState.motionElapsed = 0;
    } else {
        sOverworldMountState.motionCooldown = 4;
    }
    OverworldMount_ResetMomentum();
}

static void __attribute__((noinline, section(".overworld_mount_control_tail")))
OverworldMount_ApplyCrashPresentation(
    LocalMapObject *player,
    LocalMapObject *follower)
{
    s32 offset;

    if (sOverworldMountState.snapshot.motionMode
        != OVERWORLD_MOUNT_MOTION_CRASH) {
        return;
    }
    offset = (sOverworldMountState.motionElapsed & 2)
        ? OVERWORLD_MOUNT_CRASH_SHAKE_FX32
        : -OVERWORLD_MOUNT_CRASH_SHAKE_FX32;
    player->faceVec[0] = (u32)((s32)player->faceVec[0] + offset);
    player->faceVec[2] = (u32)((s32)player->faceVec[2] - offset);
    follower->faceVec[0] = (u32)offset;
    follower->faceVec[2] = (u32)-offset;
}

static void OverworldMount_ResetMomentum(void)
{
    sOverworldMountState.speed = sOverworldMountState.baseSpeed;
    sOverworldMountState.direction = OVERWORLD_MOUNT_DIRECTION_NONE;
    sOverworldMountState.tileCounter = 0;
    sOverworldMountState.skidRemaining = 0;
    /* Outside a skid, turnDirection stores uninterrupted Walk tile buildup. */
    sOverworldMountState.turnDirection = 0;
    sOverworldMountState.resumeSpeed = 0;
    sOverworldMountState.pendingStep = FALSE;
    sOverworldMountState.pendingSkid = FALSE;
    sOverworldMountState.bufferedDirection =
        OVERWORLD_MOUNT_DIRECTION_NONE;
    sOverworldMountState.stopPending = FALSE;
}

static BOOL __attribute__((noinline, section(".overworld_mount_precode")))
OverworldMount_BindingMatchesFollower(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    const OverworldWildSpawn *spawn;
    OverworldMountBinding *binding =
        &sOverworldMountState.snapshot.binding;

    if (fieldSystem == NULL
        || state == NULL
        || fieldSystem != sOverworldMountState.fieldSystem
        || fieldSystem != gFieldSysPtr
        || fieldSystem->location == NULL
        || state->movementFieldSystem != fieldSystem
        || state->mapId != fieldSystem->location->mapId
        || state->activeFollowerPartySlot == CUSTOM_FOLLOWER_PARTY_SLOT_NONE) {
        return FALSE;
    }
    spawn = &state->spawns[OW_WILD_FOLLOWER_SLOT];
    if (!spawn->active
        || spawn->object == NULL
        || spawn->mapId != state->mapId
        || spawn->personality != binding->personality
        || spawn->species != binding->species
        || spawn->encounterGeneration != binding->encounterGeneration
        || spawn->form != binding->form
        || spawn->level != binding->level
        || state->activeFollowerPartySlot != binding->partySlot
        || state->movementBehaviorClasses[OW_WILD_FOLLOWER_SLOT]
            != binding->behaviorClass) {
        return FALSE;
    }

    /* Seamless map-header transitions preserve the follower object and its
     * encounter identity, but intentionally advance these two context keys. */
    binding->mapId = spawn->mapId;
    binding->mapGeneration = state->mapGeneration;
    return TRUE;
}

static void __attribute__((noinline, section(".overworld_mount_precode")))
OverworldMount_ResumeFollowerCommand(
    LocalMapObject *follower,
    u32 freezeCommand)
{
    if (sOverworldMountState.snapshot.motionMode
            != OVERWORLD_MOUNT_MOTION_WALK) {
        MapObject_StartMovementCommandInternal(follower, freezeCommand);
    }
}

static LocalMapObject * __attribute__((noinline, section(".overworld_mount_precode")))
OverworldMount_GetFollowerObject(void)
{
    if (!OverworldMount_BindingMatchesFollower(
            sOverworldMountState.fieldSystem,
            &sOverworldWildSpawnState)) {
        return NULL;
    }
    return sOverworldWildSpawnState.spawns[OW_WILD_FOLLOWER_SLOT].object;
}

static BOOL OverworldMount_HasCurrentPlayer(void)
{
    FieldSystem *fieldSystem = sOverworldMountState.fieldSystem;

    return fieldSystem != NULL
        && fieldSystem == gFieldSysPtr
        && fieldSystem->playerAvatar != NULL
        && fieldSystem->playerAvatar->mapObject != NULL;
}

static void __attribute__((noinline, section(".overworld_mount_step_extra")))
OverworldMount_UpdatePlayerBaseHeight(LocalMapObject *player)
{
    if (player->faceVec[1] != sOverworldMountState.lastAppliedPlayerFaceY) {
        sOverworldMountState.playerBaseFaceY = player->faceVec[1];
    }
    if (player->unk88[1] != sOverworldMountState.lastAppliedPlayerUnk88Y) {
        sOverworldMountState.playerBaseUnk88Y = player->unk88[1];
    }
}

static void __attribute__((naked, noinline, section(".overworld_mount_field_input_extra")))
OverworldMount_ClearObjectCommand(LocalMapObject *player)
{
    __asm__(
        "ldr r3, 1f\n"
        "bx r3\n"
        ".align 2\n"
        "1: .word MapObject_ClearHeldMovement\n");
}

static void __attribute__((naked, noinline, section(".overworld_mount_field_input_extra")))
OverworldMount_ResetAvatarAfterCancel(FIELD_PLAYER_AVATAR *avatar)
{
    __asm__(
        "ldr r3, 1f\n"
        "bx r3\n"
        ".align 2\n"
        "1: .word PlayerAvatar_ResetMovement\n");
}

static void OverworldMount_SyncPresentation(void)
{
    FieldSystem *fieldSystem = sOverworldMountState.fieldSystem;
    LocalMapObject *follower = OverworldMount_GetFollowerObject();
    LocalMapObject *player;
    s32 mountedArc;

    if (!sOverworldMountState.presentationAttached
        || follower == NULL
        || !OverworldMount_HasCurrentPlayer()) {
        return;
    }
    player = fieldSystem->playerAvatar->mapObject;
    if (sOverworldMountState.snapshot.motionMode
        == OVERWORLD_MOUNT_MOTION_NONE) {
        OverworldMount_UpdatePlayerBaseHeight(player);
    }
    /* During a Hop, lastAppliedPlayerFaceY is the controller-owned composite
     * arc plus the fixed seat height. */
    mountedArc = sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_HOP
        ? (s32)sOverworldMountState.lastAppliedPlayerFaceY
            - (s32)sOverworldMountState.playerBaseFaceY
            - OVERWORLD_MOUNT_RIDER_HEIGHT_FX32
        : 0;

    /* This must not use MapObject_SetPositionFromVectorAndDirection: that
     * relocation helper clears the held movement which freezes both halves
     * of a mounted Hop. The follower is presentation-only while mounted, so
     * it must mirror the player even during the Walk completion boundary. */
    memcpy(follower->posVec, player->posVec, sizeof(follower->posVec));
    memcpy(&follower->xPrev, &player->xPrev, 6 * sizeof(int));
    follower->flags &= ~MAPOBJECTFLAG_UNK7;
    follower->faceVec[0] = 0;
    follower->faceVec[1] = (u32)(mountedArc
        + (s32)sOverworldMountState.playerBaseFaceY);
    follower->faceVec[2] = 0;
    follower->unk88[0] = 0;
    /* The renderer adds faceVec and unk88 to posVec. Keep the jump lift in
     * faceVec only, matching the native jump commands, so the mounted body
     * does not receive the same arc twice. */
    follower->unk88[1] = sOverworldMountState.playerBaseUnk88Y;
    follower->unk88[2] = 0;
    if (sOverworldMountState.snapshot.motionMode
        == OVERWORLD_MOUNT_MOTION_HOP) {
        /* The renderer sums faceVec, unk88, and unk94. Native player/object
         * animation may otherwise leave a second vertical transform active
         * while the mount controller owns the composite Hop. */
        follower->unk94[1] = 0;
    }
    /* UNK31 is unused by retail map objects. While set, the resident facing-
     * vector wrapper prevents overlay 1 from applying an independent vertical
     * render offset after the mounted pair has been synchronized. */
    follower->flags |= MAPOBJECTFLAG_UNK18 | MAPOBJECTFLAG_UNK31;
    if (sOverworldMountState.snapshot.motionMode
            != OVERWORLD_MOUNT_MOTION_TELEPORT) {
        follower->flags &= ~BIT_VANISH;
    }

    player->faceVec[1] = follower->faceVec[1]
        + OVERWORLD_MOUNT_RIDER_HEIGHT_FX32;
    player->unk88[1] = follower->unk88[1];
    if (sOverworldMountState.snapshot.motionMode
        == OVERWORLD_MOUNT_MOTION_HOP) {
        player->unk94[1] = 0;
    }
    /* Seat the rider over the mount's body instead of its forward-facing
     * sprite anchor. This generic half-tile back offset works for every
     * follower without introducing a separate mount-profile table. */
    player->faceVec[0] = (u32)(-OverworldMount_DirectionDeltaX(
        player->curFacing) << 15);
    player->faceVec[2] = (u32)(-OverworldMount_DirectionDeltaY(
        player->curFacing) << 15);
    sOverworldMountState.lastAppliedPlayerFaceY = player->faceVec[1];
    sOverworldMountState.lastAppliedPlayerUnk88Y = player->unk88[1];
    player->flags |= MAPOBJECTFLAG_UNK20;
    OverworldMount_ApplyCrashPresentation(player, follower);
    sOverworldWildSpawnState.movementCooldowns[OW_WILD_FOLLOWER_SLOT] =
        OVERWORLD_MOUNT_IDLE_COOLDOWN;
    /* A wild crash shake runs after mount sync and restores a saved position.
     * Once mounted, the follower is presentation-only and that saved tile is
     * stale, so discard the timer without applying its old base position. */
    sOverworldWildSpawnState.movementCrashShakeTimers[
        OW_WILD_FOLLOWER_SLOT] = 0;
}

static BOOL OverworldMount_AttachPresentation(void)
{
    LocalMapObject *follower = OverworldMount_GetFollowerObject();
    LocalMapObject *player;

    if (sOverworldMountState.presentationAttached) {
        return TRUE;
    }
    if (follower == NULL || !OverworldMount_HasCurrentPlayer()) {
        return FALSE;
    }
    player = sOverworldMountState.fieldSystem->playerAvatar->mapObject;
    sOverworldMountState.savedFollowerCooldown =
        sOverworldWildSpawnState.movementCooldowns[OW_WILD_FOLLOWER_SLOT];
    sOverworldMountState.snapshot.reserved =
        (follower->flags & MAPOBJECTFLAG_MOVEMENT_PAUSED) != 0;
    sOverworldMountState.savedPlayerShadowSuppressed =
        (player->flags & MAPOBJECTFLAG_UNK20) != 0;
    sOverworldMountState.playerBaseFaceY = player->faceVec[1];
    sOverworldMountState.playerBaseUnk88Y = player->unk88[1];
    sOverworldMountState.lastAppliedPlayerFaceY = player->faceVec[1];
    sOverworldMountState.lastAppliedPlayerUnk88Y = player->unk88[1];
    sOverworldMountState.savedPlayerGfxId = (u16)MapObject_GetGfxID(player);
    ChangeMapObjSprite(
        player,
        sOverworldMountState.fieldSystem->playerAvatar->gender == 0
            ? OVERWORLD_MOUNT_RIDER_SPRITE_MALE
            : OVERWORLD_MOUNT_RIDER_SPRITE_FEMALE);
    sOverworldMountState.presentationAttached = TRUE;
    sOverworldMountState.snapshot.phase = OVERWORLD_MOUNT_PHASE_RIDING;
    /* A paused map object does not push subsequent position-vector writes to
     * its renderer. The mount controller already removes the follower from AI
     * movement ownership, so keep the presentation object unpaused while it
     * mirrors the player. */
    OverworldMount_ClearObjectCommand(follower);
    MapObject_UnpauseMovement(follower);
    OverworldMount_SyncPresentation();
    return TRUE;
}

static void OverworldMount_DetachPresentation(void)
{
    LocalMapObject *follower = OverworldMount_GetFollowerObject();
    LocalMapObject *player = NULL;
    FIELD_PLAYER_AVATAR *avatar;

    if (!sOverworldMountState.presentationAttached) {
        return;
    }
    if (OverworldMount_HasCurrentPlayer()) {
        avatar = sOverworldMountState.fieldSystem->playerAvatar;
        player = avatar->mapObject;
        /* A cancellation can arrive after stock code has changed the avatar
         * state but before pendingStep records the command. Always return
         * control ownership to the normal player controller on detach. */
        OverworldMount_ClearObjectCommand(player);
        avatar->unk0 &= ~OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT;
        OverworldMount_ResetAvatarAfterCancel(avatar);
        OverworldMount_UpdatePlayerBaseHeight(player);
        player->flags &= ~MAPOBJECTFLAG_UNK7;
        player->faceVec[1] = sOverworldMountState.playerBaseFaceY;
        player->faceVec[0] = 0;
        player->faceVec[2] = 0;
        player->unk88[1] = sOverworldMountState.playerBaseUnk88Y;
        ChangeMapObjSprite(player, sOverworldMountState.savedPlayerGfxId);
        if (sOverworldMountState.savedPlayerShadowSuppressed) {
            player->flags |= MAPOBJECTFLAG_UNK20;
        } else {
            player->flags &= ~MAPOBJECTFLAG_UNK20;
        }
    }
    if (follower != NULL) {
        OverworldMount_ClearObjectCommand(follower);
        follower->flags &= ~MAPOBJECTFLAG_UNK31;
        follower->xPrev = follower->xCurr;
        follower->hPrev = follower->hCurr;
        follower->yPrev = follower->yCurr;
        follower->faceVec[0] = 0;
        follower->faceVec[1] = 0;
        follower->faceVec[2] = 0;
        follower->unk88[0] = 0;
        follower->unk88[1] = 0;
        follower->unk88[2] = 0;
        if (sOverworldMountState.snapshot.reserved) {
            MapObject_PauseMovement(follower);
        } else {
            MapObject_UnpauseMovement(follower);
        }
        sOverworldWildSpawnState.movementCooldowns[OW_WILD_FOLLOWER_SLOT] =
            sOverworldMountState.savedFollowerCooldown;
    }
    sOverworldMountState.presentationAttached = FALSE;
}

static void OverworldMount_Cancel(u8 reason)
{
    if (sOverworldMountState.snapshot.phase == OVERWORLD_MOUNT_PHASE_NONE) {
        return;
    }
    if (reason == OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST
        && sOverworldMountState.preserveTransitionPrepared) {
        return;
    }

    if (sOverworldMountState.snapshot.motionMode
            != OVERWORLD_MOUNT_MOTION_NONE) {
        OverworldWalkMount_RebaseMotionTarget(&sOverworldMountState);
        OverworldMount_FinishCustomMotion();
    }
    if (sOverworldMountState.motionStreamPreparing
        && OverworldMount_HasCurrentPlayer()) {
        OverworldMount_RestoreLandStreamTarget(
            sOverworldMountState.fieldSystem->playerAvatar->mapObject);
        sOverworldMountState.motionStreamPreparing = FALSE;
    }
    OverworldMount_DetachPresentation();
    OverworldMount_ResetMomentum();
    sOverworldMountState.snapshot.phase = OVERWORLD_MOUNT_PHASE_NONE;
    sOverworldMountState.snapshot.lastCancelReason = reason;
    sOverworldMountState.fieldSystem = NULL;
}

static BOOL OverworldMount_Begin(
    FieldSystem *fieldSystem,
    const OverworldMountBinding *binding,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives,
    const OverworldWildSurfaceCatalog *surfaceCatalog)
{
    u32 generation;
    u8 baseSpeed;
    u8 maxSpeed;
    u8 bufferedToggleDown = sOverworldMountState.bufferedToggleDown;

    if (fieldSystem == NULL
        || binding == NULL
        || profile == NULL
        || primitives == NULL
        || surfaceCatalog == NULL
        || binding->species == SPECIES_NONE) {
        return FALSE;
    }

    generation = ++sOverworldMountNextSessionGeneration;
    if (generation == 0) {
        generation = ++sOverworldMountNextSessionGeneration;
    }
    memset(&sOverworldMountState, 0, sizeof(sOverworldMountState));
    /* The Select press that starts this session can still be physically held.
     * Preserve its resident edge state so it cannot become an immediate
     * second toggle after the session reset. */
    sOverworldMountState.bufferedToggleDown = bufferedToggleDown;
    sOverworldMountState.fieldSystem = fieldSystem;
    sOverworldMountState.surfaceCatalog = surfaceCatalog;
    sOverworldMountState.snapshot.profile = profile->owner;
    sOverworldMountState.snapshot.binding = *binding;
    sOverworldMountState.snapshot.sessionGeneration = generation;
    sOverworldMountState.snapshot.phase = OVERWORLD_MOUNT_PHASE_BOUND;

    /* Mount locomotion uses the resolved owner's ordinary Walk mechanics.
     * Active/Tired are AI lanes and remain snapshotted for future actions. */
    baseSpeed = OVERWORLD_WALK_MODULE_ENTRY->clampTime(
        profile->owner.chillSpeed);
    maxSpeed = profile->owner.maxWalkSpeed;
    if (OW_WILD_BEHAVIOR_WALK_DISABLES_ACCELERATION(
            profile->owner.walkOptions)) {
        maxSpeed = baseSpeed;
    }
    if (maxSpeed > baseSpeed) {
        maxSpeed = baseSpeed;
    }
    sOverworldMountState.baseSpeed = baseSpeed;
    sOverworldMountState.maxSpeed =
        OVERWORLD_WALK_MODULE_ENTRY->clampTime(maxSpeed);
    sOverworldMountState.tilesToAccelerate = profile->owner.tilesToAccelerate;
    sOverworldMountState.walkOptions = profile->owner.walkOptions;
    OverworldMount_ResetMomentum();
    return TRUE;
}

static void OverworldMount_PrepareMapTransition(u8 mode)
{
    if (mode == OW_WILD_MAP_HEADER_CHANGE_RESUME_PRESENTATION) {
        gOverworldWildFieldIdleRearmPending |=
            OW_WILD_FIELD_IDLE_REARM_PENDING
            | OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
        if (sOverworldMountState.snapshot.phase
            == OVERWORLD_MOUNT_PHASE_NONE) {
            return;
        }
        /* This callback runs after wild-object canonicalization, in the same
         * frame as the map-header change. Resume and advance the pair now so
         * the mount is never rendered at ground height between Hop frames. */
        OverworldMount_ResumeCustomMotionAfterMapTransition();
        OverworldMount_UpdateCustomMotion();
        OverworldMount_SyncPresentation();
        return;
    }
    if (sOverworldMountState.snapshot.phase == OVERWORLD_MOUNT_PHASE_NONE) {
        return;
    }
    if (mode == OW_WILD_MAP_HEADER_CHANGE_DISCARD) {
        OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_MAP_CHANGE);
        return;
    }
    if (mode != OW_WILD_MAP_HEADER_CHANGE_PRESERVE
        || sOverworldWildSpawnState.movementRuntimeState == NULL) {
        return;
    }
    if (sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_NONE
        && !sOverworldMountState.pendingStep) {
        OverworldMount_ResetMomentum();
        sOverworldMountState.motionCooldown = 0;
    }
    sOverworldMountState.preserveTransitionPrepared = TRUE;
}

static void __attribute__((noinline, section(".overworld_mount_motion")))
OverworldMount_ResumeCustomMotionAfterMapTransition(void)
{
    LocalMapObject *follower;
    LocalMapObject *player;
    u32 freezeCommand;

    if (!sOverworldMountState.preserveTransitionPrepared) {
        return;
    }
    sOverworldMountState.preserveTransitionPrepared = FALSE;
    if ((sOverworldMountState.snapshot.motionMode
                != OVERWORLD_MOUNT_MOTION_HOP
            && sOverworldMountState.snapshot.motionMode
                != OVERWORLD_MOUNT_MOTION_TELEPORT
            && sOverworldMountState.snapshot.motionMode
                != OVERWORLD_MOUNT_MOTION_WALK)
        || !OverworldMount_HasCurrentPlayer()) {
        return;
    }
    follower = OverworldMount_GetFollowerObject();
    if (follower == NULL) {
        return;
    }
    player = sOverworldMountState.fieldSystem->playerAvatar->mapObject;
    /* Map-header canonicalization clears every wild object's held command.
     * Reassert the stationary shell without changing elapsed motion state. */
    freezeCommand = sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_WALK
        ? OVERWORLD_MOUNT_WALK_FREEZE_COMMAND
        : OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND;
    MapObject_StartMovementCommandInternal(
        player,
        freezeCommand);
    OverworldMount_ResumeFollowerCommand(follower, freezeCommand);
}

static BOOL __attribute__((noinline, section(".overworld_mount_control_tail")))
OverworldMount_IsActive(void)
{
    return sOverworldMountState.snapshot.phase != OVERWORLD_MOUNT_PHASE_NONE;
}

static u8 __attribute__((noinline, section(".overworld_mount_control_tail")))
OverworldMount_GetInputDirection(u32 keys)
{
    return OVERWORLD_WALK_MODULE_ENTRY->directionFromKeys(keys);
}

static void __attribute__((noinline, section(".overworld_mount_precode")))
OverworldMount_SetMountedFacing(u8 direction)
{
    LocalMapObject *follower = OverworldMount_GetFollowerObject();
    LocalMapObject *player;

    if (!OverworldMount_HasCurrentPlayer() || direction > 3) {
        return;
    }
    player = sOverworldMountState.fieldSystem->playerAvatar->mapObject;
    player->curFacing = direction;
    player->nextFacing = direction;
    player->curFacingBak = direction;
    player->nextFacingBak = direction;
    if (follower != NULL) {
        follower->curFacing = direction;
        follower->nextFacing = direction;
        follower->curFacingBak = direction;
        follower->nextFacingBak = direction;
    }
}

static void __attribute__((noinline, section(".overworld_mount_motion")))
OverworldMount_OnPlayerStep(void)
{
    if (sOverworldMountState.snapshot.phase != OVERWORLD_MOUNT_PHASE_RIDING
        || !OverworldMount_HasCurrentPlayer()) {
        return;
    }
    (void)OverworldMount_CompletePendingStep(
        sOverworldMountState.fieldSystem->playerAvatar);
}

BOOL __attribute__((section(".overworld_mount_step"), noinline, used))
OverworldMount_PlayerStepBridge(FieldSystem *fieldSystem)
{
    typedef BOOL (*PlayerStepHandler)(FieldSystem *);

    OverworldMount_OnPlayerStep();
    return ((PlayerStepHandler)OVERWORLD_WILD_PLAYER_STEP_HANDLER_ADDR)(
        fieldSystem);
}

int __attribute__((section(".overworld_mount_field_input"), noinline, used))
OverworldMount_FieldInputProcess(
    OverworldMountFieldInput *fieldInput,
    FieldSystem *fieldSystem)
{
    typedef int (*FieldInputProcessor)(OverworldMountFieldInput *, FieldSystem *);

    if (fieldInput != NULL
        && fieldSystem == sOverworldMountState.fieldSystem
        && sOverworldMountState.snapshot.phase == OVERWORLD_MOUNT_PHASE_RIDING
        && sOverworldMountState.presentationAttached
        && (sOverworldMountState.snapshot.motionMode
                == OVERWORLD_MOUNT_MOTION_HOP
            || sOverworldMountState.snapshot.motionMode
                == OVERWORLD_MOUNT_MOTION_TELEPORT
            || sOverworldMountState.snapshot.motionMode
                == OVERWORLD_MOUNT_MOTION_WALK)) {
        /* The stationary held command used by custom motion repeatedly looks
         * like a completed player step. Vanilla processes coordinate events
         * and warps before its forced-movement guard, so those synthetic step
         * boundaries must not escape while the mount controller owns the player.
         * Keep ordinary A/menu input intact, but disable every transition
         * signal, including the held-direction door check after landing. */
        fieldInput->flags &= ~(OVERWORLD_MOUNT_FIELD_INPUT_END_MOVEMENT
            | OVERWORLD_MOUNT_FIELD_INPUT_SIGN
            | OVERWORLD_MOUNT_FIELD_INPUT_MAP_TRANSITION
            | OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT);
    }
    return ((FieldInputProcessor)0x021E6AF5)(fieldInput, fieldSystem);
}

static void OverworldMount_EmitStepEffect(BOOL skid)
{
    LocalMapObject *follower = OverworldMount_GetFollowerObject();
    u8 stompTime = sOverworldMountState.snapshot.profile.walkStompTime;

    if (follower == NULL) {
        return;
    }
    if (skid) {
        OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->playLandingHopParticle(follower);
    } else if (OVERWORLD_WALK_MODULE_ENTRY->stompApplies(
            sOverworldMountState.speed,
            stompTime)) {
        OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->playLandingHopParticle(follower);
        PlaySE(SEQ_SE_GS_IWAOTOSHI02);
    }
}

static void __attribute__((noinline, section(".overworld_mount_motion")))
OverworldMount_NormalizeFollowerAfterStep(
    LocalMapObject *player)
{
    LocalMapObject *follower = OverworldMount_GetFollowerObject();

    if (follower == NULL) {
        return;
    }
    /* The player owns movement completion. The follower is only the mounted
     * presentation, so cancel its matching command and snap it to the
     * authoritative player tile instead of waiting forever for a second
     * movement-complete signal. */
    MapObject_SetPositionFromVectorAndDirection(
        follower,
        (VecFx32 *)player->posVec,
        player->curFacing);
    follower->xPrev = player->xPrev;
    follower->hPrev = player->hPrev;
    follower->yPrev = player->yPrev;
}

static BOOL __attribute__((noinline))
OverworldMount_CompletePendingStep(FIELD_PLAYER_AVATAR *avatar)
{
    u8 turnDirection;

    if (!sOverworldMountState.pendingStep
        || avatar == NULL
        || !MapObject_IsMovementPaused(avatar->mapObject)) {
        return FALSE;
    }
    sOverworldMountState.pendingStep = FALSE;
    OverworldMount_NormalizeFollowerAfterStep(avatar->mapObject);
    if (sOverworldMountState.pendingSkid) {
        if (sOverworldMountState.skidRemaining == 1) {
            OverworldMount_EmitStepEffect(TRUE);
        }
        sOverworldMountState.pendingSkid = FALSE;
        if (sOverworldMountState.skidRemaining != 0) {
            sOverworldMountState.skidRemaining--;
        }
        if (sOverworldMountState.skidRemaining != 0) {
            return TRUE;
        }
        turnDirection = sOverworldMountState.turnDirection;
        sOverworldMountState.turnDirection = 0;
        sOverworldMountState.tileCounter = 0;
        if (turnDirection == OVERWORLD_MOUNT_DIRECTION_NONE) {
            avatar->mapObject->flags &= ~MAPOBJECTFLAG_UNK7;
            OverworldMount_ResetMomentum();
        } else {
            avatar->mapObject->flags &= ~MAPOBJECTFLAG_UNK7;
            sOverworldMountState.direction = turnDirection;
            sOverworldMountState.speed = sOverworldMountState.resumeSpeed;
            sOverworldMountState.speed = OVERWORLD_WALK_MODULE_ENTRY->clampTime(
                sOverworldMountState.speed);
            /* The wild Walk implementation marks the first committed tile in
             * the new direction so it completes the turn before normal
             * acceleration accounting resumes. Reuse resumeSpeed as the same
             * one-step marker. */
            sOverworldMountState.resumeSpeed = sOverworldMountState.speed;
        }
        return TRUE;
    }

    OverworldMount_EmitStepEffect(FALSE);
    if (sOverworldMountState.turnDirection == OVERWORLD_MOUNT_DIRECTION_NONE) {
        sOverworldMountState.turnDirection = 1;
    } else if (sOverworldMountState.turnDirection != 0xFE) {
        sOverworldMountState.turnDirection++;
    }
    if (sOverworldMountState.resumeSpeed != 0) {
        sOverworldMountState.resumeSpeed = 0;
        return TRUE;
    }
    if (sOverworldMountState.tilesToAccelerate != 0
        && sOverworldMountState.speed > sOverworldMountState.maxSpeed) {
        if (sOverworldMountState.tileCounter != 0xFF) {
            sOverworldMountState.tileCounter++;
        }
        if (sOverworldMountState.tileCounter
            >= sOverworldMountState.tilesToAccelerate) {
            sOverworldMountState.tileCounter = 0;
            sOverworldMountState.speed =
                OVERWORLD_WALK_MODULE_ENTRY->accelerateTime(
                    sOverworldMountState.speed,
                    sOverworldMountState.maxSpeed);
        }
    }
    return TRUE;
}

static BOOL OverworldMount_CanControl(FIELD_PLAYER_AVATAR *avatar)
{
    return sOverworldMountState.snapshot.phase == OVERWORLD_MOUNT_PHASE_RIDING
        && sOverworldMountState.presentationAttached
        && avatar != NULL
        && sOverworldMountState.fieldSystem != NULL
        && sOverworldMountState.fieldSystem->playerAvatar == avatar
        && avatar->state == PLAYER_STATE_WALKING
        && (avatar->unk0 & OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT) == 0;
}

static int OverworldMount_DirectionDeltaX(u8 direction)
{
    return OVERWORLD_WALK_MODULE_ENTRY->deltaX(direction);
}

static int OverworldMount_DirectionDeltaY(u8 direction)
{
    return OVERWORLD_WALK_MODULE_ENTRY->deltaY(direction);
}

static BOOL OverworldMount_IsLandingTileAllowed(
    int targetX,
    int targetY)
{
    FieldSystem *fieldSystem = sOverworldMountState.fieldSystem;

    return targetX >= 0
        && targetY >= 0
        && OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->validateHopLanding(
            &sOverworldWildSpawnState,
            OW_WILD_FOLLOWER_SLOT,
            fieldSystem,
            sOverworldMountState.snapshot.profile
                .chillAllowedTerrainMask,
            targetX,
            targetY,
            targetX,
            targetY);
}

static s32 OverworldMount_LerpFx32(
    s32 start,
    s32 target,
    u32 elapsed,
    u32 total)
{
    if (elapsed >= total || total == 0) {
        return target;
    }
    return start + (target - start) * (s32)elapsed / (s32)total;
}

static void __attribute__((section(".overworld_mount_motion")))
OverworldMount_ApplyTeleportVisibility(BOOL visible)
{
    LocalMapObject *follower = OverworldMount_GetFollowerObject();
    LocalMapObject *player;

    if (follower == NULL || !OverworldMount_HasCurrentPlayer()) {
        return;
    }
    player = sOverworldMountState.fieldSystem->playerAvatar->mapObject;
    if (visible) {
        player->flags &= ~BIT_VANISH;
        follower->flags &= ~BIT_VANISH;
        if (!sOverworldMountState.savedFollowerShadowSuppressed) {
            follower->flags &= ~MAPOBJECTFLAG_UNK20;
        }
    } else {
        player->flags |= BIT_VANISH;
        follower->flags |= BIT_VANISH | MAPOBJECTFLAG_UNK20;
    }
}

static void OverworldMount_CommitMotionTarget(LocalMapObject *player)
{
    s32 targetBaseY = sOverworldMountState.motionTargetBaseY;

    player->posVec[0] = ((u32)(u16)sOverworldMountState.motionTargetX << 16)
        + 0x8000;
    player->posVec[1] = (u32)targetBaseY;
    player->posVec[2] = ((u32)(u16)sOverworldMountState.motionTargetY << 16)
        + 0x8000;
    /* Use the engine's relocation protocol so current/previous logical tiles,
     * height, facing backups, held movement, and single-movement ownership all
     * agree with the rendered landing position. */
    MapObject_SetPositionFromVectorAndDirection(
        player,
        (VecFx32 *)player->posVec,
        player->curFacing);
    player->faceVec[1] = (u32)((s32)sOverworldMountState.playerBaseFaceY
        + OVERWORLD_MOUNT_RIDER_HEIGHT_FX32);
    player->unk88[1] = sOverworldMountState.playerBaseUnk88Y;
}

static BOOL __attribute__((noinline, section(".overworld_mount_streaming")))
OverworldMount_UpdateLandStreamAnchor(void)
{
    LocalMapObject *player;
    s32 targetX;
    s32 targetZ;

    if (!sOverworldMountState.motionStreamPreparing) {
        return TRUE;
    }
    if ((sOverworldMountState.snapshot.motionMode
                == OVERWORLD_MOUNT_MOTION_HOP
            || sOverworldMountState.snapshot.motionMode
                == OVERWORLD_MOUNT_MOTION_WALK)
        && OverworldMount_HasCurrentPlayer()) {
        /* Follow each logical tile crossed by the rendered Hop. Loading the
         * final landing while the camera is still at the origin shifts the
         * rolling terrain window away from the camera once per jump. */
        player = sOverworldMountState.fieldSystem->playerAvatar->mapObject;
        if (sOverworldMountState.snapshot.motionMode
                == OVERWORLD_MOUNT_MOTION_WALK) {
            targetX = ((s32)player->posVec[0] & (s32)0xFFFF0000)
                + 0x8000;
            targetZ = ((s32)player->posVec[2] & (s32)0xFFFF0000)
                + 0x8000;
        } else {
            targetX = ((s32)player->xCurr << 16) + 0x8000;
            targetZ = ((s32)player->yCurr << 16) + 0x8000;
        }
    } else {
        targetX = ((s32)sOverworldMountState.motionTargetX << 16) + 0x8000;
        targetZ = ((s32)sOverworldMountState.motionTargetY << 16) + 0x8000;
    }
    /* The vanilla rolling-land manager has two work slots and asserts if a
     * third tile change is observed before either pending load completes.
     * Long Hops can cross tiles faster than land data is decoded, so do not
     * advance the watched anchor while even one request is outstanding. */
    if (*((u8 *)OverworldMount_GetLandDataManager() + 0xA0) != 0) {
        return FALSE;
    }
    if (sOverworldMountState.motionStreamAnchor.x != targetX) {
        /* The stock land task advances its rolling terrain window by one
         * tile per observed coordinate change. Never skip directly to the
         * landing coordinate: that updates its cached anchor while omitting
         * the intermediate chunk loads and leaves black terrain behind. */
        sOverworldMountState.motionStreamAnchor.x +=
            sOverworldMountState.motionStreamAnchor.x < targetX
            ? 0x10000
            : -0x10000;
        return FALSE;
    }
    if (sOverworldMountState.motionStreamAnchor.z != targetZ) {
        sOverworldMountState.motionStreamAnchor.z +=
            sOverworldMountState.motionStreamAnchor.z < targetZ
            ? 0x10000
            : -0x10000;
        return FALSE;
    }
    return TRUE;
}

static void __attribute__((noinline)) OverworldMount_DrainLandStream(void)
{
    LocalMapObject *player;

    if (!sOverworldMountState.motionStreamPreparing
        || sOverworldMountState.snapshot.motionMode
            != OVERWORLD_MOUNT_MOTION_NONE
        || !OverworldMount_HasCurrentPlayer()
        || !OverworldMount_UpdateLandStreamAnchor()) {
        return;
    }
    player = sOverworldMountState.fieldSystem->playerAvatar->mapObject;
    OverworldMount_RestoreLandStreamTarget(player);
    sOverworldMountState.motionStreamPreparing = FALSE;
}

static void OverworldMount_FinishCustomMotion(void)
{
    FIELD_PLAYER_AVATAR *avatar;
    LocalMapObject *follower;
    LocalMapObject *player;
    u16 pause;
    BOOL walkMotion;

    if (sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_NONE
        || !OverworldMount_HasCurrentPlayer()) {
        sOverworldMountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_NONE;
        sOverworldMountState.motionStreamPreparing = FALSE;
        sOverworldMountState.motionLandingPauseStarted = FALSE;
        return;
    }
    if (sOverworldMountState.snapshot.motionMode
        == OVERWORLD_MOUNT_MOTION_CRASH) {
        sOverworldMountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_NONE;
        sOverworldMountState.motionElapsed = 0;
        sOverworldMountState.motionFrameCount = 0;
        sOverworldMountState.motionLandingPauseStarted = FALSE;
        return;
    }
    avatar = sOverworldMountState.fieldSystem->playerAvatar;
    player = avatar->mapObject;
    follower = OverworldMount_GetFollowerObject();
    walkMotion = sOverworldMountState.snapshot.motionMode
        == OVERWORLD_MOUNT_MOTION_WALK;
    pause = walkMotion
        ? 0
        : sOverworldMountState.snapshot.motionMode
                == OVERWORLD_MOUNT_MOTION_TELEPORT
            ? sOverworldMountState.snapshot.profile.teleportPause
            : sOverworldMountState.snapshot.profile.hopPause;
    if (!sOverworldMountState.motionLandingPauseStarted) {
        sOverworldMountState.motionCooldown = pause;
    }
    if (!walkMotion) {
        OverworldMount_CommitMotionTarget(player);
    }
    if (walkMotion) {
        /* Keep the stationary command alive through the next player update.
         * That gives vanilla exactly one real END boundary for step scripts,
         * encounters, map connections, and warps. Relocation would clear the
         * command before that boundary can be observed. */
        player->xPrev = player->xCurr;
        player->hPrev = player->hCurr;
        player->yPrev = player->yCurr;
        player->xCurr = sOverworldMountState.motionTargetX;
        player->hCurr = sOverworldMountState.motionTargetBaseY >> 15;
        player->yCurr = sOverworldMountState.motionTargetY;
        player->posVec[0] =
            ((u32)(u16)sOverworldMountState.motionTargetX << 16) + 0x8000;
        player->posVec[1] = (u32)sOverworldMountState.motionTargetBaseY;
        player->posVec[2] =
            ((u32)(u16)sOverworldMountState.motionTargetY << 16) + 0x8000;
    }
    if (!walkMotion) {
        OverworldMount_ClearObjectCommand(player);
    }
    if (follower != NULL) {
        OverworldMount_ClearObjectCommand(follower);
    }
    OverworldMount_ApplyTeleportVisibility(TRUE);
    avatar->unk0 &= ~OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT;
    if (walkMotion) {
        avatar->unk10 = 1; /* AVATAR_MOVE_STATE_MOVING */
        avatar->unk14 = 2; /* PLAYER_MOVE_STATE_MOVING */
        sOverworldMountState.pendingStep = TRUE;
    } else {
        OverworldMount_ResetAvatarAfterCancel(avatar);
    }
    sOverworldMountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_NONE;
    sOverworldMountState.motionElapsed = 0;
    sOverworldMountState.motionFrameCount = 0;
    sOverworldMountState.motionLandingPauseStarted = FALSE;
    sOverworldMountState.lastAppliedPlayerFaceY = player->faceVec[1];
    sOverworldMountState.lastAppliedPlayerUnk88Y = player->unk88[1];
    if (!walkMotion) {
        OverworldMount_ResetMomentum();
    }
    OverworldMount_SyncPresentation();
}

static void __attribute__((noinline, section(".overworld_mount_motion")))
OverworldMount_UpdateCustomMotion(void)
{
    FIELD_PLAYER_AVATAR *avatar;
    LocalMapObject *player;
    s32 baseX;
    s32 baseZ;
    s32 baseY;
    s32 arc;
    u32 swayElapsed;
    u8 spinFacing;
    u8 spinSpeed;
    u8 spinStep;

    if (sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_NONE
        || !OverworldMount_HasCurrentPlayer()) {
        return;
    }
    avatar = sOverworldMountState.fieldSystem->playerAvatar;
    player = avatar->mapObject;
    if ((sOverworldMountState.snapshot.motionMode
                == OVERWORLD_MOUNT_MOTION_HOP
            || sOverworldMountState.snapshot.motionMode
                == OVERWORLD_MOUNT_MOTION_TELEPORT)
        && sOverworldMountState.motionElapsed
            >= sOverworldMountState.motionFrameCount
        && !sOverworldMountState.motionLandingPauseStarted) {
        /* The authored pause starts when the actor visibly lands. Any final
         * terrain-stream drain overlaps that pause instead of extending it. */
        sOverworldMountState.motionCooldown =
            sOverworldMountState.snapshot.motionMode
                    == OVERWORLD_MOUNT_MOTION_TELEPORT
                ? sOverworldMountState.snapshot.profile.teleportPause
                : sOverworldMountState.snapshot.profile.hopPause;
        sOverworldMountState.motionLandingPauseStarted = TRUE;
    }
    (void)OverworldMount_UpdateLandStreamAnchor();
    if (sOverworldMountState.motionElapsed == 0
        && sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_TELEPORT) {
        OverworldMount_ApplyTeleportVisibility(
            sOverworldMountState.motionFlicker);
    }
    if (sOverworldMountState.motionElapsed
        >= sOverworldMountState.motionFrameCount) {
        OverworldMount_FinishCustomMotion();
        return;
    }
    sOverworldMountState.motionElapsed++;
    if (sOverworldMountState.snapshot.motionMode
        == OVERWORLD_MOUNT_MOTION_CRASH) {
        return;
    }
    if (sOverworldMountState.snapshot.motionMode
        == OVERWORLD_MOUNT_MOTION_TELEPORT) {
        OverworldMount_ApplyTeleportVisibility(
            sOverworldMountState.motionFlicker
                && ((sOverworldMountState.motionElapsed
                    / OVERWORLD_MOUNT_TELEPORT_FLICKER_PHASE_FRAMES) & 1)
                    == 0);
        return;
    }

    baseX = OverworldMount_LerpFx32(
        ((s32)sOverworldMountState.motionStartX << 16) + 0x8000,
        ((s32)sOverworldMountState.motionTargetX << 16) + 0x8000,
        sOverworldMountState.motionElapsed,
        sOverworldMountState.motionFrameCount);
    baseZ = OverworldMount_LerpFx32(
        ((s32)sOverworldMountState.motionStartY << 16) + 0x8000,
        ((s32)sOverworldMountState.motionTargetY << 16) + 0x8000,
        sOverworldMountState.motionElapsed,
        sOverworldMountState.motionFrameCount);
    baseY = OverworldMount_LerpFx32(
        sOverworldMountState.motionStartBaseY,
        sOverworldMountState.motionTargetBaseY,
        sOverworldMountState.motionElapsed,
        sOverworldMountState.motionFrameCount);
    arc = 0;
    if (sOverworldMountState.snapshot.motionMode
            != OVERWORLD_MOUNT_MOTION_WALK) {
        swayElapsed = sOverworldMountState.motionElapsed << 1;
        arc = OVERWORLD_WILD_SURFACE_SERVICE_ENTRY->calculateJumpArc(
            swayElapsed >= sOverworldMountState.motionFrameCount
                ? swayElapsed - sOverworldMountState.motionFrameCount
                : swayElapsed,
            sOverworldMountState.motionFrameCount,
            sOverworldMountState.motionFlicker >> 4);
        if (swayElapsed >= sOverworldMountState.motionFrameCount) {
            arc = -arc;
        }
        if (sOverworldMountState.motionStartY
            == sOverworldMountState.motionTargetY) {
            baseZ += arc;
        } else {
            baseX += arc;
        }
        arc = OVERWORLD_WILD_SURFACE_SERVICE_ENTRY->calculateJumpArc(
            sOverworldMountState.motionElapsed,
            sOverworldMountState.motionFrameCount,
            sOverworldMountState.motionArcHeightQ4);
    }
    player->posVec[0] = (u32)baseX;
    player->posVec[1] = (u32)baseY;
    player->posVec[2] = (u32)baseZ;
    if (sOverworldMountState.snapshot.motionMode
            != OVERWORLD_MOUNT_MOTION_WALK
        && (player->xCurr != baseX >> 16 || player->yCurr != baseZ >> 16)) {
        player->xPrev = player->xCurr;
        player->yPrev = player->yCurr;
        player->xCurr = baseX >> 16;
        player->yCurr = baseZ >> 16;
    }
    player->hCurr = baseY >> 15;
    player->faceVec[1] = (u32)(arc
        + (s32)sOverworldMountState.playerBaseFaceY
        + OVERWORLD_MOUNT_RIDER_HEIGHT_FX32);
    player->unk88[1] = sOverworldMountState.playerBaseUnk88Y;
    sOverworldMountState.lastAppliedPlayerFaceY = player->faceVec[1];
    sOverworldMountState.lastAppliedPlayerUnk88Y = player->unk88[1];
    if (sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_WALK) {
        if (sOverworldMountState.motionElapsed
            >= sOverworldMountState.motionFrameCount) {
            /* Commit on the Nth update. The stationary player command stays
             * active so vanilla still emits one movement-end boundary next. */
            OverworldMount_FinishCustomMotion();
            return;
        }
        /* PlayerAvatar_UpdateMovement runs before this controller. Hold its
         * state at MOVING until the visual step reaches the destination. */
        avatar->unk10 = 1;
        avatar->unk14 = 2;
        return;
    }
    spinSpeed = sOverworldMountState.motionFlicker & 0x0F;
    if (spinSpeed != 0) {
        /* Map the engine's N/S/W/E encoding onto the same clockwise
         * N/E/S/W spin steps used by wild custom hops. Incrementing the raw
         * direction value produces N/S/W/E jumps that look random. */
        spinFacing = sOverworldMountState.motionDirection;
        spinStep = (u8)(((spinFacing >> 1) & 1)
            | (((spinFacing ^ (spinFacing >> 1)) & 1) << 1));
        spinStep = (u8)((spinStep
            + sOverworldMountState.motionElapsed / spinSpeed) & 3);
        spinFacing = (u8)(((spinStep & 1) << 1)
            | ((spinStep ^ (spinStep >> 1)) & 1));
        OverworldMount_SetMountedFacing(spinFacing);
    }
}

typedef struct OverworldMountHopSearch {
    u8 lateral;
    u8 distance;
    u8 side;
} OverworldMountHopSearch;

static BOOL __attribute__((noinline, section(".overworld_mount_hop_search")))
OverworldMount_TryNextHopLandingCandidate(
    const OverworldWildBehaviorProfileData *lane,
    u8 direction,
    u8 minDistance,
    u8 maxDistance,
    OverworldMountHopSearch *search)
{
    int forwardX = OverworldMount_DirectionDeltaX(direction);
    int forwardY = OverworldMount_DirectionDeltaY(direction);
    int lateralMagnitude;
    int lateral;
    int sideCount;
    int targetX;
    int targetY;

    while (search->lateral <= maxDistance) {
        if (search->distance < minDistance) {
            search->lateral++;
            search->distance = maxDistance;
            search->side = 0;
            continue;
        }
        lateralMagnitude = search->lateral == maxDistance
            ? search->distance
            : search->lateral;
        if (search->lateral != maxDistance
            && lateralMagnitude >= search->distance) {
            search->distance--;
            search->side = 0;
            continue;
        }
        sideCount = lateralMagnitude == 0 ? 1 : 2;
        if (search->side >= sideCount) {
            search->distance--;
            search->side = 0;
            continue;
        }
        lateral = search->side++ == 0
            ? lateralMagnitude
            : -lateralMagnitude;
        if ((lateral == 0
                && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(
                    lane->hopAllowNonCardinal))
            || (lateral != 0
                && (!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
                        lane->hopAllowNonCardinal)
                    || lateralMagnitude != search->distance))) {
            continue;
        }
        targetX = sOverworldMountState.motionStartX
            + forwardX * search->distance - forwardY * lateral;
        targetY = sOverworldMountState.motionStartY
            + forwardY * search->distance + forwardX * lateral;
        if (!OverworldMount_IsLandingTileAllowed(targetX, targetY)) {
            continue;
        }
        sOverworldMountState.motionTargetX = (s16)targetX;
        sOverworldMountState.motionTargetY = (s16)targetY;
        return TRUE;
    }
    return FALSE;
}

static BOOL __attribute__((noinline, section(".overworld_mount_motion")))
OverworldMount_TryStartCustomMotion(
    FIELD_PLAYER_AVATAR *avatar,
    u8 direction,
    u8 facingDirection)
{
    const OverworldWildBehaviorProfileData *lane =
        &sOverworldMountState.snapshot.profile;
    LocalMapObject *follower;
    LocalMapObject *player;
    u8 rawLocomotion = lane->chillAction;
    u8 minDistance;
    u8 maxDistance;
    int startX;
    int startY;
    int targetX = 0;
    int targetY = 0;
    int distance;
    OverworldMountHopSearch hopSearch;
    u32 trajectory = 0;
    u32 frames;

    if (rawLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WALK) {
        follower = OverworldMount_GetFollowerObject();
        return OVERWORLD_WALK_MOUNT_MODULE_ENTRY->startFlatMotion(
            &sOverworldMountState,
            avatar,
            follower,
            OverworldMount_GetLandDataManager(),
            direction,
            facingDirection);
    }

    /* The caller establishes player ownership and validates Walk collision. */
    if (sOverworldMountState.motionCooldown != 0
        || sOverworldMountState.motionStreamPreparing
        || (rawLocomotion != OW_WILD_BEHAVIOR_LOCOMOTION_HOP
            && !OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(rawLocomotion))) {
        return FALSE;
    }
    player = avatar->mapObject;
    follower = OverworldMount_GetFollowerObject();
    /* A seamless map connection can leave rolling-land work pending for a
     * few frames after the mount has rebound to the new map. Starting a new
     * custom motion in that window can occupy the stream anchor indefinitely
     * at its landing frame. The input hook still consumes the held direction,
     * so simply defer the Hop/Teleport until the stock loader is idle. */
    if (follower == NULL
        || *((u8 *)OverworldMount_GetLandDataManager() + 0xA0) != 0) {
        return FALSE;
    }
    startX = player->xCurr;
    startY = player->yCurr;
    sOverworldMountState.motionStartBaseY = (s32)player->posVec[1];
    sOverworldMountState.motionStartX = (s16)startX;
    sOverworldMountState.motionStartY = (s16)startY;
    if (rawLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP) {
        minDistance = lane->hopMinDistance != 0 ? lane->hopMinDistance : 1;
        maxDistance = lane->hopMaxDistance >= minDistance
            ? lane->hopMaxDistance
            : minDistance;
        if (maxDistance > OVERWORLD_MOUNT_HOP_MAX_DISTANCE) {
            maxDistance = OVERWORLD_MOUNT_HOP_MAX_DISTANCE;
        }
        /* Preserve the requested heading as closely as possible. Try every
         * straight landing first, then widen the lateral miss one tile at a
         * time. Equal-axis (45 degree) diagonals are the final fallback. */
        hopSearch.lateral = 0;
        hopSearch.distance = maxDistance;
        hopSearch.side = 0;
        while (OverworldMount_TryNextHopLandingCandidate(
                lane,
                direction,
                minDistance,
                maxDistance,
                &hopSearch)) {
            distance = hopSearch.distance;
            targetX = sOverworldMountState.motionTargetX;
            targetY = sOverworldMountState.motionTargetY;
            sOverworldMountState.motionTargetBaseY =
                OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
                sOverworldMountState.fieldSystem,
                sOverworldMountState.surfaceCatalog,
                player,
                targetX,
                targetY);
            if (OVERWORLD_WILD_HOP_TRAJECTORY_ENTRY->resolve(
                    sOverworldMountState.fieldSystem,
                    sOverworldMountState.surfaceCatalog,
                    lane,
                    player,
                    sOverworldMountState.motionStartBaseY,
                    sOverworldMountState.motionTargetBaseY,
                    startX,
                    startY,
                    targetX,
                    targetY,
                    (u8)distance,
                    &trajectory)) {
                sOverworldMountState.motionTargetX = (s16)targetX;
                sOverworldMountState.motionTargetY = (s16)targetY;
                goto hop_target_found;
            }
        }
        return FALSE;
hop_target_found:
        ;
    } else {
        minDistance = 1;
        maxDistance = OVERWORLD_MOUNT_TELEPORT_MAX_DISTANCE;
        for (distance = maxDistance; distance >= minDistance; distance--) {
            targetX = startX
                + OverworldMount_DirectionDeltaX(direction) * distance;
            targetY = startY
                + OverworldMount_DirectionDeltaY(direction) * distance;
            if (OverworldMount_IsLandingTileAllowed(targetX, targetY)) {
                break;
            }
        }
        if (distance < minDistance) {
            return FALSE;
        }
        sOverworldMountState.motionTargetBaseY =
            OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
            sOverworldMountState.fieldSystem,
            sOverworldMountState.surfaceCatalog,
            player,
            targetX,
            targetY);
        sOverworldMountState.motionTargetX = (s16)targetX;
        sOverworldMountState.motionTargetY = (s16)targetY;
    }
    if (rawLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP) {
        frames = trajectory & 0xFFFF;
        if (frames == 0) {
            frames = 1;
        }
        sOverworldMountState.snapshot.motionMode =
            OVERWORLD_MOUNT_MOTION_HOP;
        sOverworldMountState.motionArcHeightQ4 = (u8)(trajectory >> 16);
        sOverworldMountState.motionFlicker =
            (u8)((lane->hopSwayWidth << 4)
                | (lane->hopSpinSpeed & 0x0F));
    } else {
        frames = lane->teleportTime;
        if (OW_WILD_BEHAVIOR_TELEPORT_USES_PER_TILE_TIME(rawLocomotion)) {
            frames *= distance;
        }
        if (frames > 0xFFFF) {
            frames = 0xFFFF;
        }
        sOverworldMountState.snapshot.motionMode =
            OVERWORLD_MOUNT_MOTION_TELEPORT;
        sOverworldMountState.motionArcHeightQ4 = 0;
        sOverworldMountState.motionFlicker = (u8)(
            OW_WILD_BEHAVIOR_TELEPORT_USES_FLICKER(rawLocomotion) << 4);
    }
    /* A spinning Hop starts from the mounted pair's current facing, matching
     * wild custom jumps. Non-spinning motion still faces its travel heading. */
    sOverworldMountState.motionDirection = direction;
    if ((sOverworldMountState.motionFlicker & 0x0F) != 0) {
        sOverworldMountState.motionDirection = player->curFacing;
    }
    sOverworldMountState.savedFollowerShadowSuppressed =
        (follower->flags & MAPOBJECTFLAG_UNK20) != 0;
    sOverworldMountState.motionCooldown = 0;
    sOverworldMountState.motionLandingPauseStarted = FALSE;
    sOverworldMountState.motionFrameCount = (u16)frames;
    sOverworldMountState.motionElapsed = 0;
    avatar->unk0 |= OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT;
    OverworldMount_ResetAvatarAfterCancel(avatar);
    /* Normalize any just-finished stock step before custom motion takes
     * ownership. This prevents a stale SINGLE_MOVEMENT flag from surviving
     * the entire jump and blocking control after landing. */
    MapObject_SetPositionFromVectorAndDirection(
        player,
        (VecFx32 *)player->posVec,
        sOverworldMountState.motionDirection);
    OverworldMount_SetMountedFacing(sOverworldMountState.motionDirection);
    /* Match the existing Pokémon custom-jump shell: both render objects run
     * the same stationary held command while the mount controller owns their
     * shared position and render offsets. This prevents either object's
     * ordinary animation callback from adding an independent movement. */
    MapObject_StartMovementCommandInternal(
        player,
        OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND);
    MapObject_StartMovementCommandInternal(
        follower,
        OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND);
    if (!sOverworldMountState.motionStreamPreparing) {
        sOverworldMountState.motionStreamAnchor = *(VecFx32 *)player->posVec;
        sOverworldMountState.motionStreamPreparing = TRUE;
        ov01_021F62E8(
            &sOverworldMountState.motionStreamAnchor,
            OverworldMount_GetLandDataManager());
    }
    OverworldMount_ResetMomentum();
    return TRUE;
}

static BOOL __attribute__((noinline)) OverworldMount_HandleCustomInput(
    FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys,
    u32 *heldKeys)
{
    u8 rawLocomotion = sOverworldMountState.snapshot.profile.chillAction;
    u8 direction;

    /* This hook is resident even after a mount session ends. A canceled Hop
     * can lose its old field context before its object cleanup is safe, so a
     * stale motion byte must never be allowed to consume controls by itself. */
    if (sOverworldMountState.snapshot.phase
            != OVERWORLD_MOUNT_PHASE_RIDING
        || !sOverworldMountState.presentationAttached
        || avatar == NULL
        || sOverworldMountState.fieldSystem == NULL
        || sOverworldMountState.fieldSystem->playerAvatar != avatar) {
        return FALSE;
    }
    if (sOverworldMountState.snapshot.motionMode
        != OVERWORLD_MOUNT_MOTION_NONE) {
        return TRUE;
    }
    direction = OverworldMount_GetInputDirection(*newKeys | *heldKeys);
    if (direction >= OVERWORLD_MOUNT_DIRECTION_NORTH_WEST
        && direction <= OVERWORLD_MOUNT_DIRECTION_SOUTH_EAST) {
        direction = OVERWORLD_WALK_MODULE_ENTRY->diagonalFacing(
            avatar->mapObject,
            direction,
            *newKeys);
    }
    if (rawLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP
        || OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(rawLocomotion)) {
        /* Overlay 1 asks the stock avatar collision helper about held input
         * after a custom Hop commits. That query changes unk10 to TURNING as
         * a side effect. Stock walking clears it on its next movement call,
         * but custom locomotion owns that call and must clear the stale state
         * itself. Otherwise field input stays unready and controls appear to
         * lock after landing, especially beside blocked tiles. */
        if (avatar->unk10 != OVERWORLD_MOUNT_PLAYER_MOVE_STATE_NONE
            || avatar->unk14 != OVERWORLD_MOUNT_PLAYER_MOVE_STATE_NONE) {
            OverworldMount_ResetAvatarAfterCancel(avatar);
        }
        if (direction != OVERWORLD_MOUNT_DIRECTION_NONE
            && OverworldMount_CanControl(avatar)) {
            (void)OverworldMount_TryStartCustomMotion(
                avatar,
                direction,
                direction);
        }
        /* Custom locomotion owns the player for its complete idle/move/pause
         * cycle. Letting an idle frame reach stock control can start a second
         * movement state from the map object's stationary command. */
        return TRUE;
    }
    if (sOverworldMountState.motionCooldown != 0) {
        /* Field input has already resolved its direction before this wrapper.
         * Calling stock control with cleared key masks can still start that
         * stale direction and leave the avatar in MOVE_STATE_START after a
         * Hop landing. Consume the whole control call during the pause. */
        return TRUE;
    }
    return FALSE;
}

static void __attribute__((noinline, section(".overworld_mount_motion")))
OverworldMount_FilterMovementInput(
    FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys,
    u32 *heldKeys)
{
    OVERWORLD_WALK_MOUNT_MODULE_ENTRY->filterInput(
        &sOverworldMountState,
        avatar,
        newKeys,
        heldKeys);
}

static void __attribute__((noinline))
OverworldMount_ResolveDiagonalInput(
    FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys,
    u32 *heldKeys)
{
    if (!OverworldMount_CanControl(avatar)
        || sOverworldMountState.snapshot.profile.chillAction
            != OW_WILD_BEHAVIOR_LOCOMOTION_WALK) {
        return;
    }
    OVERWORLD_WALK_MODULE_ENTRY->resolveMountedDiagonal(
        &sOverworldMountState,
        avatar,
        newKeys,
        heldKeys);
}

static BOOL __attribute__((noinline))
OverworldMount_TryHandleDiagonalWalk(
    FIELD_PLAYER_AVATAR *avatar,
    u32 newKeys,
    u32 heldKeys)
{
    u8 requestedDirection;
    u8 facingDirection;

    if (!OverworldMount_CanControl(avatar)
        || sOverworldMountState.snapshot.profile.chillAction
            != OW_WILD_BEHAVIOR_LOCOMOTION_WALK
        || sOverworldMountState.motionCooldown != 0) {
        return FALSE;
    }
    if (sOverworldMountState.pendingStep) {
        /* A flat diagonal tile still owns the stock movement-end boundary.
         * Do not start its successor before that boundary updates skid and
         * acceleration state. */
        return TRUE;
    }
    requestedDirection = OverworldMount_GetInputDirection(newKeys | heldKeys);
    if (requestedDirection == OVERWORLD_MOUNT_DIRECTION_NONE) {
        return FALSE;
    }
    if (requestedDirection >= OVERWORLD_MOUNT_DIRECTION_NORTH_WEST
        && !OVERWORLD_WALK_MODULE_ENTRY->strictDiagonalAllowed(
            &sOverworldMountState,
            avatar,
            requestedDirection)) {
        return TRUE;
    }
    facingDirection = requestedDirection;
    if (facingDirection >= OVERWORLD_MOUNT_DIRECTION_NORTH_WEST) {
        facingDirection = OVERWORLD_WALK_MODULE_ENTRY->diagonalFacing(
            avatar->mapObject,
            facingDirection,
            newKeys);
    }
    sOverworldMountState.direction = requestedDirection;
    sOverworldMountState.pendingSkid =
        sOverworldMountState.skidRemaining != 0;
    if (!OverworldMount_TryStartCustomMotion(
            avatar,
            requestedDirection,
            facingDirection)) {
        sOverworldMountState.pendingSkid = FALSE;
        OverworldMount_PlayCrashSound(SEQ_SE_DP_WALL_HIT);
    }
    return TRUE;
}

static BOOL OverworldMount_TryStartWalkFromInput(
    FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys,
    u32 *heldKeys)
{
    OverworldMount_ResolveDiagonalInput(avatar, newKeys, heldKeys);
    OverworldMount_FilterMovementInput(avatar, newKeys, heldKeys);
    return OverworldMount_TryHandleDiagonalWalk(
        avatar,
        *newKeys,
        *heldKeys);
}

static void __attribute__((noinline))
OverworldMount_ProcessPlayerControl(
    FIELD_PLAYER_AVATAR *avatar,
    u32 param1,
    s32 direction,
    u32 newKeys,
    u32 heldKeys,
    u32 param5)
{
    if (OverworldMount_HandleCustomInput(avatar, &newKeys, &heldKeys)) {
        return;
    }
    if (OverworldMount_TryStartWalkFromInput(
            avatar,
            &newKeys,
            &heldKeys)) {
        return;
    }
    PlayerAvatar_MoveControl(
        avatar,
        param1,
        direction,
        newKeys,
        heldKeys,
        param5);
}

void __attribute__((section(".overworld_mount_control"), noinline, used))
OverworldMount_PlayerMoveControl(
    FIELD_PLAYER_AVATAR *avatar,
    u32 param1,
    s32 direction,
    u32 newKeys,
    u32 heldKeys,
    u32 param5)
{
    OverworldMount_ProcessPlayerControl(
        avatar,
        param1,
        direction,
        newKeys,
        heldKeys,
        param5);
}

void __attribute__((section(".overworld_mount_crash"), noinline, used))
OverworldMount_PlayCrashSound(u32 sequence)
{
    if (sOverworldMountState.snapshot.phase == OVERWORLD_MOUNT_PHASE_RIDING) {
        OverworldMount_StartWalkCrash();
        if (OW_WILD_BEHAVIOR_WALK_CRASH_SOUND(
                sOverworldMountState.walkOptions)
            != OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_WALL_HIT) {
            return;
        }
    }
    PlaySE(sequence);
}

static BOOL __attribute__((section(".overworld_mount_motion"), noinline))
OverworldMount_GetOrdinaryDirection(
    u32 movementCommand,
    u8 *directionOut)
{
    u8 direction;

    for (direction = OVERWORLD_MOUNT_DIRECTION_NORTH;
         direction <= OVERWORLD_MOUNT_DIRECTION_EAST;
         direction++) {
        if (movementCommand == MapObject_MovementCommandFromDirection(
                direction,
                OVERWORLD_MOUNT_WALK_COMMAND)
            || movementCommand == MapObject_MovementCommandFromDirection(
                direction,
                OVERWORLD_MOUNT_RUN_COMMAND)) {
            *directionOut = direction;
            return TRUE;
        }
    }
    return FALSE;
}

void OverworldMount_IssueHeldMovement(
    FIELD_PLAYER_AVATAR *avatar,
    LocalMapObject *object,
    u32 vanillaCommand)
{
    u32 movementCommand = vanillaCommand;
    u8 direction;
    BOOL trackedStep = FALSE;
    BOOL mountedPlayer = OverworldMount_CanControl(avatar)
        && object == avatar->mapObject;

    if (mountedPlayer
        && OverworldMount_GetOrdinaryDirection(vanillaCommand, &direction)) {
        trackedStep = TRUE;
        sOverworldMountState.direction = direction;
        sOverworldMountState.pendingSkid =
            sOverworldMountState.skidRemaining != 0;
    } else if (mountedPlayer) {
        /* Ledge jumps, bumps, forced steps, and other stock commands interrupt
         * ordinary Walk ownership. Clear any forced skid direction so the
         * special command cannot leave mounted input locked afterward. */
        OverworldMount_NormalizeFollowerAfterStep(object);
        OverworldMount_ResetMomentum();
    }
    if (trackedStep) {
        u8 facingDirection = direction;

        if (sOverworldMountState.snapshot.motionMode
                != OVERWORLD_MOUNT_MOTION_NONE) {
            /* The held-movement hook can run before the current exact-frame
             * Walk reaches its final update. Keep ownership with that motion;
             * replacing it here drops its last frame and logical boundary. */
            return;
        }
        /* A turn skid keeps both travel and facing on the committed heading.
         * Apply the requested facing only after the last skid tile lands. */
        (void)OverworldMount_TryStartCustomMotion(
            avatar,
            direction,
            facingDirection);
        return;
    }
    object->flags &= ~MAPOBJECTFLAG_UNK7;
    avatar->unk8 = movementCommand;
    MapObject_StartMovementCommandInternal(object, movementCommand);
}

static BOOL OverworldMount_CanToggle(FieldSystem *fieldSystem)
{
    FIELD_PLAYER_AVATAR *avatar;

    if (fieldSystem == NULL
        || fieldSystem->taskman != NULL
        || fieldSystem->playerAvatar == NULL) {
        return FALSE;
    }
    avatar = fieldSystem->playerAvatar;
    return avatar->state == PLAYER_STATE_WALKING
        && (avatar->unk0 & OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT) == 0
        && (avatar->unk14 == OVERWORLD_MOUNT_PLAYER_MOVE_STATE_NONE
            || avatar->unk14 == OVERWORLD_MOUNT_PLAYER_MOVE_STATE_END);
}

static void OverworldMount_HandleFollowerSelectionRequest(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    volatile OverworldFollowerTransitionQueueStorage *queue =
        OVERWORLD_FOLLOWER_TRANSITION_QUEUE;
    OverworldWildSpawn *follower = &state->spawns[OW_WILD_FOLLOWER_SLOT];
    u8 request = queue->reserved;
    u8 partySlot = request
        & OVERWORLD_FOLLOWER_SELECTION_REQUEST_SLOT_MASK;
    u8 selectedSlot = CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
    BOOL mount = (request
        & OVERWORLD_FOLLOWER_SELECTION_REQUEST_MOUNT) != 0;

    if ((request & OVERWORLD_FOLLOWER_SELECTION_REQUEST_PENDING) != 0) {
        (void)OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY->getSelectedPokemon(
            fieldSystem,
            &selectedSlot);
        if (!mount && selectedSlot == partySlot) {
            /* A second Y on the already selected follower only closes the
             * menu; it must not recall or respawn that follower. */
            queue->reserved = 0;
            return;
        }
        if (follower->active
            && state->activeFollowerPartySlot == partySlot) {
            if (!mount
                || OverworldMount_IsActive()
                || OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY
                    ->beginMountSelectedFollower(fieldSystem, state)) {
                queue->reserved = 0;
            }
            return;
        }
        if (queue->count != 0) {
            return;
        }
        OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_EXPLICIT);
        queue->reserved = mount
            ? OVERWORLD_FOLLOWER_SELECTION_REQUEST_MOUNT | partySlot
            : 0;
        (void)OVERWORLD_FOLLOWER_TRANSITION_QUEUE_APPEND(
            OVERWORLD_FOLLOWER_TRANSITION_QUEUE_DESPAWN_COMMAND);
        (void)OVERWORLD_FOLLOWER_TRANSITION_QUEUE_APPEND(partySlot + 1);
        return;
    }
    if (!mount || queue->count != 0) {
        return;
    }
    if (!follower->active
        || state->activeFollowerPartySlot != partySlot) {
        queue->reserved = 0;
    } else if (OverworldMount_IsActive()
        || OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY
            ->beginMountSelectedFollower(fieldSystem, state)) {
        queue->reserved = 0;
    }
}

static void OverworldRuntime_TickWildRefillTimer(
    OverworldWildSpawnState *state)
{
    if (state == NULL
        || state->movementRuntimeState == NULL
        || gOverworldWildFieldIdleRearmPending != 0) {
        return;
    }
    if (state->spawnCooldown == OW_WILD_REFILL_TIMER_PENDING) {
        return;
    }
    if (state->spawnCooldown != 0) {
        state->spawnCooldown--;
        return;
    }
    state->spawnCooldown = OW_WILD_REFILL_TIMER_PENDING;
    gOverworldWildFieldIdleRearmPending |=
        OW_WILD_FIELD_IDLE_REARM_PENDING;
}

static BOOL __attribute__((used)) OverworldMount_Tick(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u16 physicalKeys)
{
    BOOL togglePressed = sOverworldMountState.bufferedTogglePending != 0;

    OverworldRuntime_TickWildRefillTimer(state);
    OverworldMount_HandleFollowerSelectionRequest(fieldSystem, state);
    if (togglePressed
        && !OverworldFollowerSelector_IsActiveFlagSet()
        && !OverworldFollowerSelector_IsReleaseGated()
        && OverworldMount_CanToggle(fieldSystem)) {
        /* A buffered edge belongs to the mount controller until it is
         * accepted. Do not discard it merely because a Hop or a field update
         * made this particular frame unable to toggle. */
        sOverworldMountState.bufferedTogglePending = FALSE;
        if (OverworldMount_IsActive()) {
            OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_EXPLICIT);
        } else {
            (void)OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY
                ->beginMountSelectedFollower(fieldSystem, state);
        }
    }
    if (!OverworldMount_IsActive()) {
        return FALSE;
    }
    if (fieldSystem != sOverworldMountState.fieldSystem
        || !OverworldMount_BindingMatchesFollower(fieldSystem, state)) {
        OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_IDENTITY_CHANGED);
        return FALSE;
    }
    OverworldMount_ResumeCustomMotionAfterMapTransition();
    if (sOverworldMountState.pendingStep
        && sOverworldMountState.skidRemaining == 0) {
        u8 requestedDirection = OverworldMount_GetInputDirection(physicalKeys);

        if (requestedDirection != OVERWORLD_MOUNT_DIRECTION_NONE
            && requestedDirection != sOverworldMountState.direction) {
            /* Buffer turns while the current tile owns PlayerMoveControl. */
            sOverworldMountState.bufferedDirection = requestedDirection;
        } else if (requestedDirection == sOverworldMountState.direction) {
            /* The player deliberately returned to the committed heading
             * before the boundary, so discard an older buffered turn. */
            sOverworldMountState.bufferedDirection =
                OVERWORLD_MOUNT_DIRECTION_NONE;
        }
    }
    if (sOverworldMountState.motionCooldown != 0) {
        sOverworldMountState.motionCooldown--;
    }
    OverworldMount_UpdateCustomMotion();
    OverworldMount_DrainLandStream();
    if (!OverworldMount_AttachPresentation()) {
        OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_IDENTITY_CHANGED);
        return FALSE;
    }
    OverworldMount_SyncPresentation();
    return TRUE;
}

static BOOL __attribute__((naked, noinline, used,
    section(".overworld_mount_toggle_latch")))
OverworldMount_TickLatched(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u16 physicalKeys)
{
    __asm__(
        "push {r0}\n"
        "ldr r3, 2f\n"
        "ldrb r0, [r3, #0]\n"
        "lsl r0, r0, #2\n"
        "orr r2, r0\n"
        /* Preserve the wrapper's fixed ABI size while leaving the buffered
         * edge owned by OverworldMount_Tick until a toggle succeeds. */
        "nop\n"
        "nop\n"
        "pop {r0}\n"
        "ldr r3, 3f\n"
        "bx r3\n"
        ".align 2\n"
        "2: .word 0x023BC78A\n"
        "3: .word OverworldMount_Tick + 1\n");
}

const OverworldMountOverlayEntry gOverworldMountOverlayEntry
    __attribute__((section(".overworld_mount_entry"), used)) = {
        OVERWORLD_MOUNT_OVERLAY_MAGIC,
        OVERWORLD_MOUNT_OVERLAY_VERSION,
        sizeof(OverworldMountOverlayEntry),
        OverworldMount_Begin,
        OverworldMount_Cancel,
        OverworldMount_PrepareMapTransition,
        OverworldMount_OnPlayerStep,
        OverworldMount_IsActive,
        OverworldMount_TickLatched,
    };
