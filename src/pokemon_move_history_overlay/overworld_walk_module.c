#include "../../include/overworld_walk_module.h"

#include "../../include/constants/buttons.h"
#include "../../include/constants/species.h"
#include "../../include/battle.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/overworld_wild_runtime.h"
#include "../../include/overworld_walk_direction_policy.h"
#include "../../include/overworld_walk_timing_policy.h"

#define WALK_DIRECTION_NONE 0xFF
#define WALK_DIRECTION_NORTH 0
#define WALK_DIRECTION_SOUTH 1
#define WALK_DIRECTION_WEST 2
#define WALK_DIRECTION_EAST 3
#define WALK_DIRECTION_NORTH_WEST 4
#define WALK_DIRECTION_NORTH_EAST 5
#define WALK_DIRECTION_SOUTH_WEST 6
#define WALK_DIRECTION_SOUTH_EAST 7
#define WALK_COLLISION_CHECK \
    ((int (*)(FIELD_PLAYER_AVATAR *, LocalMapObject *, int))0x0205DA35)
#define WALK_MOUNT_FREEZE_COMMAND 0x3C
#define WALK_MOUNT_AVATAR_FORCED_MOVEMENT (1u << 0)
#define WALK_PLAYER_MOVE_STATE_NONE 0
#define WALK_PLAYER_MOVE_STATE_END 3

#define WALK_CODE __attribute__((section(".overworld_walk_module")))
#define WALK_RODATA __attribute__((section(".overworld_walk_module_rodata")))

extern void *PokemonMoveHistory_OverlayMemset(
    void *destination,
    int value,
    u32 size);

#define WALK_WILD_BEHAVIOR_KIND_WANDER 2
#define WALK_WILD_BEHAVIOR_KIND_HEADBUTT_TREE_HOP 7
#define WALK_WILD_LOCOMOTION_NONE 0
#define WALK_WILD_LOCOMOTION_WANDER 1
#define WALK_WILD_LOCOMOTION_RAM 5
#define WALK_WILD_TARGET_NONE 0
#define WALK_WILD_TARGET_RANDOM_NEARBY 1
#define WALK_WILD_TARGET_TOWARD_PLAYER 2
#define WALK_WILD_TARGET_AWAY_FROM_PLAYER 3
#define WALK_WILD_TARGET_TREE_TOP 4
#define WALK_WILD_ALERT_RANGE_NONE 0
#define WALK_WILD_ALERT_RANGE_TERRAIN_ONLY 5
#define WALK_WILD_REACTION_NONE 0
#define WALK_WILD_REACTION_CONTACT 1
#define WALK_WILD_REACTION_FLEE 2
#define WALK_WILD_REACTION_EMOTE 4
#define WALK_WILD_REACTION_TIRED 5
#define WALK_WILD_GROUP_BABY (1u << 0)
#define WALK_WILD_GROUP_GHOST (1u << 1)
#define WALK_WILD_GROUP_TYPE_NORMAL (1u << 2)

static const u8 sWalkWildSpawnLocomotion[] WALK_RODATA = {
    WALK_WILD_LOCOMOTION_NONE,
    3,
    4,
    7,
};

static const u8 sWalkWildDefaultTarget[] WALK_RODATA = {
    WALK_WILD_TARGET_NONE,
    WALK_WILD_TARGET_NONE,
    WALK_WILD_TARGET_RANDOM_NEARBY,
    WALK_WILD_TARGET_TOWARD_PLAYER,
    WALK_WILD_TARGET_AWAY_FROM_PLAYER,
    WALK_WILD_TARGET_TOWARD_PLAYER,
    WALK_WILD_TARGET_TOWARD_PLAYER,
    WALK_WILD_TARGET_TREE_TOP,
};

static const u8 sWalkWildActiveReaction[] WALK_RODATA = {
    WALK_WILD_REACTION_NONE,
    WALK_WILD_REACTION_NONE,
    WALK_WILD_REACTION_NONE,
    WALK_WILD_REACTION_CONTACT,
    WALK_WILD_REACTION_FLEE,
    WALK_WILD_REACTION_EMOTE,
    WALK_WILD_REACTION_CONTACT,
    WALK_WILD_REACTION_CONTACT,
};

static const u16 sWalkWildGroupSpecies[] WALK_RODATA = {
    SPECIES_GASTLY,
    SPECIES_HAUNTER,
    SPECIES_GENGAR,
    SPECIES_MISDREAVUS,
    SPECIES_DUSKULL,
    SPECIES_PICHU,
    SPECIES_CLEFFA,
    SPECIES_IGGLYBUFF,
    SPECIES_TOGEPI,
    SPECIES_TYROGUE,
    SPECIES_SMOOCHUM,
    SPECIES_ELEKID,
    SPECIES_MAGBY,
    SPECIES_AZURILL,
    SPECIES_WYNAUT,
    SPECIES_BUDEW,
    SPECIES_CHINGLING,
    SPECIES_BONSLY,
    SPECIES_MIME_JR,
    SPECIES_HAPPINY,
    SPECIES_MUNCHLAX,
    SPECIES_RIOLU,
    SPECIES_MANTYKE,
};

static u8 WALK_CODE Walk_ClampTime(u8 time)
{
    return OverworldWalkTimingPolicy_Clamp(time);
}

static u8 WALK_CODE Walk_AccelerateTime(u8 time, u8 fastestTime)
{
    return OverworldWalkTimingPolicy_Accelerate(time, fastestTime);
}

static u8 WALK_CODE Walk_SkidTiles(u8 time)
{
    return OverworldWalkTimingPolicy_SkidTiles(time);
}

static u8 WALK_CODE Walk_SkidTime(u8 time)
{
    return OverworldWalkTimingPolicy_SkidTime(time);
}

static BOOL WALK_CODE Walk_StompApplies(u8 time, u8 threshold)
{
    return OverworldWalkTimingPolicy_StompApplies(time, threshold);
}

static u8 WALK_CODE Walk_DirectionFromKeys(u32 keys)
{
    return OverworldWalkDirectionPolicy_FromKeys(keys);
}

static u32 WALK_CODE Walk_DirectionKey(u8 direction)
{
    return OverworldWalkDirectionPolicy_Key(direction);
}

static int WALK_CODE Walk_DeltaX(u8 direction)
{
    return OverworldWalkDirectionPolicy_DeltaX(direction);
}

static int WALK_CODE Walk_DeltaY(u8 direction)
{
    return OverworldWalkDirectionPolicy_DeltaY(direction);
}

static BOOL WALK_CODE Walk_IsFortyFiveDegreeTurn(u8 from, u8 to)
{
    return OverworldWalkDirectionPolicy_IsFortyFiveDegreeTurn(from, to);
}

static u8 WALK_CODE Walk_DirectionFromDelta(int dx, int dy)
{
    return OverworldWalkDirectionPolicy_FromDelta(dx, dy);
}

static void WALK_CODE Walk_GetComponents(
    u8 direction,
    u8 *vertical,
    u8 *horizontal)
{
    *vertical = direction >= WALK_DIRECTION_SOUTH_WEST
        ? WALK_DIRECTION_SOUTH
        : WALK_DIRECTION_NORTH;
    *horizontal = (direction & 1u)
        ? WALK_DIRECTION_EAST
        : WALK_DIRECTION_WEST;
}

static BOOL WALK_CODE Walk_CanCardinal(
    FIELD_PLAYER_AVATAR *avatar,
    u8 direction)
{
    return WALK_COLLISION_CHECK(avatar, avatar->mapObject, direction) == 0;
}

static BOOL WALK_CODE Walk_StrictDiagonalAllowed(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar,
    u8 direction)
{
    u8 vertical;
    u8 horizontal;
    int targetX;
    int targetY;

    if (direction < 4 || direction > 7) {
        return FALSE;
    }
    Walk_GetComponents(direction, &vertical, &horizontal);
    targetX = avatar->mapObject->xCurr + Walk_DeltaX(direction);
    targetY = avatar->mapObject->yCurr + Walk_DeltaY(direction);
    return Walk_CanCardinal(avatar, vertical)
        && Walk_CanCardinal(avatar, horizontal)
        && targetX >= 0
        && targetY >= 0
        && OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->validateHopLanding(
            &sOverworldWildSpawnState,
            OW_WILD_FOLLOWER_SLOT,
            state->fieldSystem,
            state->snapshot.profile.chillAllowedTerrainMask,
            targetX,
            targetY,
            targetX,
            targetY);
}

static u8 WALK_CODE Walk_DiagonalFacing(
    LocalMapObject *player,
    u8 direction,
    u32 newKeys)
{
    u8 vertical;
    u8 horizontal;

    Walk_GetComponents(direction, &vertical, &horizontal);
    if (player->curFacing == vertical || player->curFacing == horizontal) {
        return (u8)player->curFacing;
    }
    return (newKeys & Walk_DirectionKey(horizontal)) != 0
        ? horizontal
        : vertical;
}

static void WALK_CODE Walk_ResolveMountedDiagonal(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys,
    u32 *heldKeys)
{
    u8 direction = Walk_DirectionFromKeys(*newKeys | *heldKeys);
    u8 vertical;
    u8 horizontal;
    u8 first;

    if (direction < 4 || direction > 7) {
        return;
    }
    if (OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
            state->snapshot.profile.hopAllowNonCardinal)
        && Walk_StrictDiagonalAllowed(state, avatar, direction)) {
        return;
    }
    if (!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(
            state->snapshot.profile.hopAllowNonCardinal)) {
        *newKeys &= ~PAD_PLUS_KEY_MASK;
        *heldKeys &= ~PAD_PLUS_KEY_MASK;
        return;
    }
    Walk_GetComponents(direction, &vertical, &horizontal);
    first = avatar->mapObject->curFacing == vertical
            || avatar->mapObject->curFacing == horizontal
        ? (u8)avatar->mapObject->curFacing
        : Walk_DiagonalFacing(avatar->mapObject, direction, *newKeys);
    if (!Walk_CanCardinal(avatar, first)) {
        first = first == vertical ? horizontal : vertical;
        if (!Walk_CanCardinal(avatar, first)) {
            first = WALK_DIRECTION_NONE;
        }
    }
    *newKeys = (*newKeys & ~PAD_PLUS_KEY_MASK) | Walk_DirectionKey(first);
    *heldKeys = (*heldKeys & ~PAD_PLUS_KEY_MASK) | Walk_DirectionKey(first);
}

static BOOL WALK_CODE Walk_ValidateProfileData(
    const OverworldWildBehaviorProfileData *profile)
{
    return profile != NULL
        && profile->chillSpeed >= OW_WILD_WALK_TRAVEL_TIME_MIN
        && profile->chillSpeed <= OW_WILD_WALK_TRAVEL_TIME_MAX
        && profile->maxWalkSpeed >= OW_WILD_WALK_TRAVEL_TIME_MIN
        && profile->maxWalkSpeed <= profile->chillSpeed
        && profile->chainRepositionSpeed >= OW_WILD_WALK_TRAVEL_TIME_MIN
        && profile->chainRepositionSpeed <= OW_WILD_WALK_TRAVEL_TIME_MAX
        && profile->chaseBoostSpeed <= OW_WILD_WALK_TRAVEL_TIME_MAX
        && profile->walkStompTime <= OW_WILD_WALK_TRAVEL_TIME_MAX;
}

static BOOL WALK_CODE Walk_ValidateExactOverrideValue(
    u8 fieldIndex,
    u8 value)
{
    return OverworldWalkTimingPolicy_ValidateExactOverrideValue(
        fieldIndex,
        value);
}

static BOOL WALK_CODE Walk_ValidateExactOverrideProfile(
    const OverworldWildBehaviorOverrideProfile *profile)
{
    u32 operatorMask;
    u16 operatorMask2;
    u32 operatorMask3;

    if (profile == NULL) {
        return FALSE;
    }
    operatorMask = profile->relativeMask | profile->atLeastMask
        | profile->atMostMask;
    operatorMask2 = profile->relativeMask2 | profile->atLeastMask2
        | profile->atMostMask2;
    operatorMask3 = profile->relativeMask3 | profile->atLeastMask3
        | profile->atMostMask3;
    return !((profile->mask & OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED)
            && !(operatorMask & OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED)
            && !Walk_ValidateExactOverrideValue(
                7,
                profile->profile.chillSpeed))
        && !((profile->mask2
                & OW_WILD_BEHAVIOR_OVERRIDE2_CHASE_BOOST_SPEED)
            && !(operatorMask2
                & OW_WILD_BEHAVIOR_OVERRIDE2_CHASE_BOOST_SPEED)
            && !Walk_ValidateExactOverrideValue(
                36,
                profile->profile.chaseBoostSpeed))
        && !((profile->mask3 & OW_WILD_BEHAVIOR_OVERRIDE3_MAX_WALK_SPEED)
            && !(operatorMask3 & OW_WILD_BEHAVIOR_OVERRIDE3_MAX_WALK_SPEED)
            && !Walk_ValidateExactOverrideValue(
                49,
                profile->profile.maxWalkSpeed))
        && !((profile->mask3
                & OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_REPOSITION_SPEED)
            && !(operatorMask3
                & OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_REPOSITION_SPEED)
            && !Walk_ValidateExactOverrideValue(
                56,
                profile->profile.chainRepositionSpeed))
        && !((profile->mask3 & OW_WILD_BEHAVIOR_OVERRIDE3_WALK_STOMP_TIME)
            && !(operatorMask3 & OW_WILD_BEHAVIOR_OVERRIDE3_WALK_STOMP_TIME)
            && !Walk_ValidateExactOverrideValue(
                66,
                profile->profile.walkStompTime));
}

static void WALK_CODE Walk_NormalizeProfileData(
    OverworldWildBehaviorProfileData *profile)
{
    if (profile == NULL) {
        return;
    }
    profile->chillSpeed = Walk_ClampTime(profile->chillSpeed);
    profile->maxWalkSpeed = Walk_ClampTime(profile->maxWalkSpeed);
    if (profile->maxWalkSpeed > profile->chillSpeed) {
        profile->maxWalkSpeed = profile->chillSpeed;
    }
    profile->chainRepositionSpeed = Walk_ClampTime(
        profile->chainRepositionSpeed);
    if (profile->chaseBoostSpeed > OW_WILD_WALK_TRAVEL_TIME_MAX) {
        profile->chaseBoostSpeed = OW_WILD_WALK_TRAVEL_TIME_MAX;
    }
    if (profile->walkStompTime > OW_WILD_WALK_TRAVEL_TIME_MAX) {
        profile->walkStompTime = OW_WILD_WALK_TRAVEL_TIME_MAX;
    }
}

static BOOL WALK_CODE Walk_MountCanControl(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar)
{
    return state->snapshot.phase == OVERWORLD_MOUNT_PHASE_RIDING
        && state->presentationAttached
        && avatar != NULL
        && state->fieldSystem != NULL
        && state->fieldSystem->playerAvatar == avatar
        && avatar->state == PLAYER_STATE_WALKING
        && (avatar->unk0 & WALK_MOUNT_AVATAR_FORCED_MOVEMENT) == 0;
}

static void WALK_CODE Walk_MountForceDirection(
    u32 *newKeys,
    u32 *heldKeys,
    u8 direction)
{
    u32 key = Walk_DirectionKey(direction);

    *newKeys = (*newKeys & ~PAD_PLUS_KEY_MASK) | key;
    *heldKeys = (*heldKeys & ~PAD_PLUS_KEY_MASK) | key;
}

static void WALK_CODE Walk_MountResetMomentum(
    OverworldMountRuntimeState *state)
{
    state->speed = state->baseSpeed;
    state->direction = WALK_DIRECTION_NONE;
    state->tileCounter = 0;
    state->skidRemaining = 0;
    state->turnDirection = 0;
    state->resumeSpeed = 0;
    state->pendingStep = FALSE;
    state->pendingSkid = FALSE;
    state->bufferedDirection = WALK_DIRECTION_NONE;
    state->stopPending = FALSE;
}

static void WALK_CODE Walk_MountFilterInput(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys,
    u32 *heldKeys)
{
    u8 requestedDirection;
    u8 skidTiles;

    if (!Walk_MountCanControl(state, avatar)
        || (avatar->unk14 != WALK_PLAYER_MOVE_STATE_NONE
            && avatar->unk14 != WALK_PLAYER_MOVE_STATE_END)) {
        return;
    }
    requestedDirection = Walk_DirectionFromKeys(*heldKeys | *newKeys);
    if (requestedDirection < WALK_DIRECTION_NORTH_WEST
        && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(
            state->snapshot.profile.hopAllowNonCardinal)) {
        *newKeys &= ~PAD_PLUS_KEY_MASK;
        *heldKeys &= ~PAD_PLUS_KEY_MASK;
        requestedDirection = WALK_DIRECTION_NONE;
    }
    if (state->bufferedDirection != WALK_DIRECTION_NONE
        && state->bufferedDirection != state->direction) {
        if ((state->bufferedDirection < WALK_DIRECTION_NORTH_WEST
                && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(
                    state->snapshot.profile.hopAllowNonCardinal))
            || (state->bufferedDirection >= WALK_DIRECTION_NORTH_WEST
                && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
                    state->snapshot.profile.hopAllowNonCardinal))) {
            /* A queued direction cannot bypass the profile's movement mode. */
            state->bufferedDirection = WALK_DIRECTION_NONE;
        } else {
            /* The newest valid queued direction owns the next tile boundary. */
            requestedDirection = state->bufferedDirection;
            Walk_MountForceDirection(
                newKeys,
                heldKeys,
                requestedDirection);
        }
    }
    if (state->skidRemaining != 0) {
        Walk_MountForceDirection(
            newKeys,
            heldKeys,
            state->direction);
        return;
    }
    if (requestedDirection == WALK_DIRECTION_NONE) {
        skidTiles = Walk_SkidTiles(state->speed);
        if (state->direction != WALK_DIRECTION_NONE && skidTiles != 0) {
            if (!state->stopPending) {
                /* Defer stop skid for one sample so a physical reversal can
                 * become a turn skid on its following key state. */
                state->stopPending = TRUE;
                *newKeys &= ~PAD_PLUS_KEY_MASK;
                *heldKeys &= ~PAD_PLUS_KEY_MASK;
                return;
            }
            state->skidRemaining = skidTiles;
            state->turnDirection = WALK_DIRECTION_NONE;
            state->resumeSpeed = state->baseSpeed;
            state->stopPending = FALSE;
            state->speed = Walk_SkidTime(state->speed);
            Walk_MountForceDirection(
                newKeys,
                heldKeys,
                state->direction);
        } else {
            Walk_MountResetMomentum(state);
        }
        return;
    }
    state->stopPending = FALSE;
    if (state->direction == WALK_DIRECTION_NONE) {
        state->direction = requestedDirection;
        state->bufferedDirection = WALK_DIRECTION_NONE;
        return;
    }
    if (requestedDirection == state->direction) {
        state->bufferedDirection = WALK_DIRECTION_NONE;
        return;
    }
    if (!OW_WILD_BEHAVIOR_WALK_ALLOWS_TURNING(state->walkOptions)) {
        Walk_MountForceDirection(newKeys, heldKeys, state->direction);
        state->bufferedDirection = WALK_DIRECTION_NONE;
        return;
    }
    state->tileCounter = 0;
    if (Walk_IsFortyFiveDegreeTurn(state->direction, requestedDirection)) {
        state->turnDirection = 0;
        state->direction = requestedDirection;
        state->bufferedDirection = WALK_DIRECTION_NONE;
        return;
    }
    skidTiles = Walk_SkidTiles(state->speed);
    if (skidTiles != 0
        && state->snapshot.profile.tilesBeforeTurnSkid != 0
        && state->turnDirection
            >= state->snapshot.profile.tilesBeforeTurnSkid) {
        state->skidRemaining = skidTiles;
        state->turnDirection = requestedDirection;
        state->bufferedDirection = WALK_DIRECTION_NONE;
        state->resumeSpeed = state->speed;
        state->speed = Walk_SkidTime(state->speed);
        Walk_MountForceDirection(newKeys, heldKeys, state->direction);
        return;
    }
    state->turnDirection = 0;
    state->direction = requestedDirection;
    state->bufferedDirection = WALK_DIRECTION_NONE;
}

static void WALK_CODE Walk_SetFacing(LocalMapObject *object, u8 direction)
{
    object->curFacing = direction;
    object->nextFacing = direction;
    object->curFacingBak = direction;
    object->nextFacingBak = direction;
}

extern void LONG_CALL ov01_021F62E8(
    VecFx32 *position,
    void *landDataManager);

static BOOL WALK_CODE Walk_StartMountedFlatMotion(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar,
    LocalMapObject *follower,
    void *landDataManager,
    u8 direction,
    u8 facingDirection)
{
    LocalMapObject *player;
    int targetX;
    int targetY;

    if (state->motionCooldown != 0 || avatar == NULL || follower == NULL) {
        return FALSE;
    }
    player = avatar->mapObject;
    if (direction < WALK_DIRECTION_NORTH_WEST
        && !Walk_CanCardinal(avatar, direction)) {
        return FALSE;
    }
    targetX = player->xCurr + Walk_DeltaX(direction);
    targetY = player->yCurr + Walk_DeltaY(direction);
    state->motionStartBaseY = (s32)player->posVec[1];
    state->motionStartX = (s16)player->xCurr;
    state->motionStartY = (s16)player->yCurr;
    state->motionTargetBaseY =
        OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
            state->fieldSystem,
            state->surfaceCatalog,
            player,
            targetX,
            targetY);
    state->motionTargetX = (s16)targetX;
    state->motionTargetY = (s16)targetY;
    state->snapshot.motionMode = OVERWORLD_MOUNT_MOTION_WALK;
    state->motionDirection = facingDirection;
    state->motionArcHeightQ4 = 0;
    state->motionFlicker = 0;
    state->savedFollowerShadowSuppressed =
        (follower->flags & MAPOBJECTFLAG_UNK20) != 0;
    state->motionCooldown = 0;
    state->motionLandingPauseStarted = FALSE;
    state->motionFrameCount = Walk_ClampTime(state->speed);
    state->motionElapsed = 0;
    state->pendingStep = FALSE;
    state->pendingSkid = state->skidRemaining != 0;
    avatar->unk8 = WALK_MOUNT_FREEZE_COMMAND;
    avatar->unk10 = 1;
    avatar->unk14 = 2;
    MapObject_SetPositionFromVectorAndDirection(
        player,
        (VecFx32 *)player->posVec,
        facingDirection);
    Walk_SetFacing(player, facingDirection);
    Walk_SetFacing(follower, facingDirection);
    MapObject_StartMovementCommandInternal(player, WALK_MOUNT_FREEZE_COMMAND);
    /* The mounted follower is already removed from wild movement scheduling
     * and mirrors the player every field tick. Giving it an independent stock
     * command lets that command write the previous render tile after the
     * player commits, causing a one-frame full-tile split at every boundary. */
    if (!state->motionStreamPreparing) {
        state->motionStreamAnchor = *(VecFx32 *)player->posVec;
        state->motionStreamPreparing = TRUE;
        ov01_021F62E8(&state->motionStreamAnchor, landDataManager);
    }
    return TRUE;
}

static void WALK_CODE Walk_ApplyFacePlayerFacing(
    OverworldWildSpawnState *state,
    int slot,
    u8 enabled)
{
    LocalMapObject *object;
    LocalMapObject *player;
    int dx;
    int dy;
    u8 horizontal;
    u8 vertical;

    if (state == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS
        || !enabled) {
        return;
    }
    object = state->spawns[slot].object;
    if (object == NULL
        || state->movementFieldSystem == NULL
        || state->movementFieldSystem->playerAvatar == NULL) {
        return;
    }
    player = state->movementFieldSystem->playerAvatar->mapObject;
    if (player == NULL) {
        return;
    }
    dx = player->xCurr - object->xCurr;
    dy = player->yCurr - object->yCurr;
    horizontal = dx > 0 ? WALK_DIRECTION_EAST : WALK_DIRECTION_WEST;
    vertical = dy > 0 ? WALK_DIRECTION_SOUTH : WALK_DIRECTION_NORTH;
    if (dx < 0) {
        dx = -dx;
    }
    if (dy < 0) {
        dy = -dy;
    }
    object->curFacing = dx >= dy ? horizontal : vertical;
}

static void WALK_CODE Walk_WildNormalizeMovementPrimitives(
    u8 behaviorKind,
    u8 *locomotion,
    u8 *target)
{
    if (behaviorKind < WALK_WILD_BEHAVIOR_KIND_WANDER
        || behaviorKind > WALK_WILD_BEHAVIOR_KIND_HEADBUTT_TREE_HOP) {
        *locomotion = WALK_WILD_LOCOMOTION_NONE;
        *target = WALK_WILD_TARGET_NONE;
    } else if (*target == WALK_WILD_TARGET_NONE) {
        *target = sWalkWildDefaultTarget[behaviorKind];
    }
}

static void WALK_CODE Walk_WildResolvePrimitives(
    const OverworldWildBehaviorProfile *profile,
    OverworldWildBehaviorPrimitives *primitives)
{
    PokemonMoveHistory_OverlayMemset(
        primitives,
        0,
        sizeof(*primitives));
    if (profile == NULL) {
        return;
    }
    if (profile->spawnState < NELEMS(sWalkWildSpawnLocomotion)) {
        primitives->spawnLocomotion =
            sWalkWildSpawnLocomotion[profile->spawnState];
    }
    primitives->chillLocomotion = profile->chillAction;
    primitives->chillTarget = profile->chillTarget;
    if (primitives->chillLocomotion == WALK_WILD_LOCOMOTION_RAM) {
        primitives->chillLocomotion = WALK_WILD_LOCOMOTION_WANDER;
    } else if (OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(
                   primitives->chillLocomotion)) {
        primitives->chillLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT;
    }
    Walk_WildNormalizeMovementPrimitives(
        profile->chillState,
        &primitives->chillLocomotion,
        &primitives->chillTarget);

    primitives->attentiveLocomotion = profile->movementStyle;
    primitives->attentiveTarget = profile->targetSelector;
    if (primitives->attentiveLocomotion == WALK_WILD_LOCOMOTION_RAM) {
        primitives->attentiveLocomotion = WALK_WILD_LOCOMOTION_WANDER;
    } else if (OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(
                   primitives->attentiveLocomotion)) {
        primitives->attentiveLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT;
    }
    if (profile->attentiveState < NELEMS(sWalkWildActiveReaction)) {
        primitives->activeReaction =
            sWalkWildActiveReaction[profile->attentiveState];
        if (profile->attentiveState >= WALK_WILD_BEHAVIOR_KIND_WANDER
            && primitives->attentiveTarget == WALK_WILD_TARGET_NONE) {
            primitives->attentiveTarget =
                sWalkWildDefaultTarget[profile->attentiveState];
        }
    }
    if (profile->alertness != 0 && profile->alertChance != 0
        && profile->alertRange <= WALK_WILD_ALERT_RANGE_TERRAIN_ONLY) {
        primitives->alertLogic = profile->alertRange;
        primitives->alertReaction =
            profile->alertRange == WALK_WILD_ALERT_RANGE_NONE
            ? WALK_WILD_REACTION_NONE
            : WALK_WILD_REACTION_EMOTE;
    }
    primitives->tiredLocomotion = profile->tired.chillAction;
    primitives->tiredTarget = profile->tired.chillTarget;
    if (primitives->tiredLocomotion == WALK_WILD_LOCOMOTION_RAM) {
        primitives->tiredLocomotion = WALK_WILD_LOCOMOTION_WANDER;
    } else if (OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(
                   primitives->tiredLocomotion)) {
        primitives->tiredLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT;
    }
    Walk_WildNormalizeMovementPrimitives(
        profile->tiredState,
        &primitives->tiredLocomotion,
        &primitives->tiredTarget);
    if (profile->tiredState != 0) {
        primitives->tiredReaction = WALK_WILD_REACTION_TIRED;
    }
}

static u32 WALK_CODE Walk_WildGroupFlagsForTypes(
    u16 species,
    u8 type1,
    u8 type2)
{
    u32 flags = 0;
    u32 i;

    for (i = 0; i < NELEMS(sWalkWildGroupSpecies); i++) {
        if (species == sWalkWildGroupSpecies[i]) {
            flags |= i < 5
                ? WALK_WILD_GROUP_GHOST
                : WALK_WILD_GROUP_BABY;
            break;
        }
    }
    if (species != SPECIES_NONE) {
        if (type1 <= TYPE_STELLAR) {
            flags |= WALK_WILD_GROUP_TYPE_NORMAL << type1;
        }
        if (type2 <= TYPE_STELLAR) {
            flags |= WALK_WILD_GROUP_TYPE_NORMAL << type2;
        }
    }
    return flags;
}

static u32 WALK_CODE Walk_WildSelectConditionalOverrideMask(
    const OverworldWildBehaviorDataBlob *behaviorData,
    const OverworldWildBehaviorContext *context,
    u32 normalOverrideMask,
    u8 movementSpeed)
{
    const OverworldWildBehaviorConditionalState *conditionalState =
        &behaviorData->conditionalStates[0];
    u16 explicitTerrainMask = conditionalState->terrainOverrideMask;
    u16 acceptedTerrainMask = conditionalState->terrainMask
        & explicitTerrainMask;

    if ((normalOverrideMask & (1u << conditionalState->parentProfile)) == 0
        || (explicitTerrainMask != 0
            && (context->conditionTerrainMask == 0
                || (acceptedTerrainMask != 0
                    && (context->conditionTerrainMask & acceptedTerrainMask) == 0)
                || (context->conditionTerrainMask
                    & (explicitTerrainMask & ~acceptedTerrainMask)) != 0))
        || (conditionalState->minMovementSpeed != 0
            && movementSpeed < conditionalState->minMovementSpeed)
        || (conditionalState->maxMovementSpeed != 0
            && movementSpeed > conditionalState->maxMovementSpeed)) {
        return 0;
    }
    return 1u << conditionalState->overrideProfile;
}

const OverworldWalkModuleEntry gOverworldWalkModuleEntry
    __attribute__((section(".overworld_walk_module_entry"), used)) = {
        OVERWORLD_WALK_MODULE_MAGIC,
        OVERWORLD_WALK_MODULE_VERSION,
        sizeof(OverworldWalkModuleEntry),
        Walk_ClampTime,
        Walk_AccelerateTime,
        Walk_SkidTiles,
        Walk_SkidTime,
        Walk_StompApplies,
        Walk_DirectionFromKeys,
        Walk_DirectionKey,
        Walk_DeltaX,
        Walk_DeltaY,
        Walk_IsFortyFiveDegreeTurn,
        Walk_ResolveMountedDiagonal,
        Walk_StrictDiagonalAllowed,
        Walk_DiagonalFacing,
        Walk_DirectionFromDelta,
    };

const OverworldWalkProfileModuleEntry gOverworldWalkProfileModuleEntry
    __attribute__((section(".overworld_walk_profile_module_entry"), used)) = {
        OVERWORLD_WALK_PROFILE_MODULE_MAGIC,
        OVERWORLD_WALK_MODULE_VERSION,
        sizeof(OverworldWalkProfileModuleEntry),
        Walk_ValidateProfileData,
        Walk_ValidateExactOverrideValue,
        Walk_NormalizeProfileData,
        Walk_ValidateExactOverrideProfile,
    };

const OverworldWalkMountModuleEntry gOverworldWalkMountModuleEntry
    __attribute__((section(".overworld_walk_mount_module_entry"), used)) = {
        OVERWORLD_WALK_MOUNT_MODULE_MAGIC,
        OVERWORLD_WALK_MODULE_VERSION,
        sizeof(OverworldWalkMountModuleEntry),
        Walk_MountFilterInput,
        Walk_StartMountedFlatMotion,
    };

/* Keep canceled custom motion on a complete tile. The mount state stores the
 * two start coordinates directly before the two target coordinates, followed
 * by start and target base height. */
void __attribute__((naked, noinline, used, aligned(2),
        section(".overworld_walk_mount_abort")))
OverworldWalkMount_RebaseMotionTargetImpl(
    OverworldMountRuntimeState *state)
{
    __asm__(
        "add r0, #0x98\n"
        "ldr r1, [r0, #0]\n"
        "str r1, [r0, #4]\n"
        "ldr r1, [r0, #8]\n"
        "str r1, [r0, #12]\n"
        "bx lr\n");
}

const OverworldWalkFaceModuleEntry gOverworldWalkFaceModuleEntry
    __attribute__((section(".overworld_walk_face_module_entry"), used)) = {
        OVERWORLD_WALK_FACE_MODULE_MAGIC,
        OVERWORLD_WALK_MODULE_VERSION,
        sizeof(OverworldWalkFaceModuleEntry),
        Walk_ApplyFacePlayerFacing,
    };

const OverworldWalkWildPolicyModuleEntry gOverworldWalkWildPolicyModuleEntry
    __attribute__((section(".overworld_walk_wild_policy_module_entry"), used)) = {
        OVERWORLD_WALK_WILD_POLICY_MODULE_MAGIC,
        OVERWORLD_WALK_MODULE_VERSION,
        sizeof(OverworldWalkWildPolicyModuleEntry),
        Walk_WildResolvePrimitives,
        Walk_WildGroupFlagsForTypes,
        Walk_WildSelectConditionalOverrideMask,
    };
