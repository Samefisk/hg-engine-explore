#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/overworld_wild_helper.h"
#include "../../include/map_events_internal.h"
__asm__(
    ".global OverworldWildSpawns_RenderFollowerReleaseBounce\n"
    ".type OverworldWildSpawns_RenderFollowerReleaseBounce, %function\n"
    ".set OverworldWildSpawns_RenderFollowerReleaseBounce, 0x0224F599\n"
    ".global OverworldWildSpawns_ReturnFollowerReleaseBall\n"
    ".type OverworldWildSpawns_ReturnFollowerReleaseBall, %function\n"
    ".set OverworldWildSpawns_ReturnFollowerReleaseBall, 0x0224F6AD\n");

void OverworldWildSpawns_RenderFollowerReleaseBounce(
    void *rawProjectile,
    OverworldWildFollowerReleaseRotationCallback rotate);
BOOL OverworldWildSpawns_ReturnFollowerReleaseBall(
    FieldSystem *fieldSystem,
    void *rawProjectile,
    u16 progress);
/* Prefix-compatible view of overlay 151's private Player Ball state. */
typedef struct OverworldWildFollowerReleaseProjectile {
    u32 opaquePointers[6];
    s32 startX;
    s32 startY;
    s32 startZ;
    s32 targetX;
    s32 targetY;
    s32 targetZ;
    s32 startHeight;
    u32 rotationMatrix[9];
    s16 rotation;
    u16 mapId;
    u16 mapGeneration;
    u16 impactEncounterGeneration;
    s8 impactSlot;
    u8 elapsedFrames;
    u8 totalFrames;
    u8 phase;
    u8 objectId;
    u8 shakeChecks;
    u8 shakeIndex;
} OverworldWildFollowerReleaseProjectile;

#define OW_WILD_FOLLOWER_PRIME_FRAMES 1
#define OW_WILD_FOLLOWER_APEX_HOLD_FRAMES 2
#define OW_WILD_FOLLOWER_FALL_FRAMES 8
#define OW_WILD_FOLLOWER_FALL_START_FRAME \
    (OW_WILD_FOLLOWER_PRIME_FRAMES + OW_WILD_FOLLOWER_APEX_HOLD_FRAMES)
#define OW_WILD_FOLLOWER_RELEASE_FRAMES \
    (OW_WILD_FOLLOWER_FALL_START_FRAME + OW_WILD_FOLLOWER_FALL_FRAMES)
#define OW_WILD_FOLLOWER_RETURN_FRAMES 12
#define OW_WILD_FOLLOWER_RELEASE_DISPATCH_RESTORE 1
#define OW_WILD_FOLLOWER_RELEASE_DISPATCH_CANCEL 2
#define OW_WILD_FOLLOWER_FALL_PROGRESS_SCALE 64
#define OW_WILD_FOLLOWER_BALL_VISUAL_CENTER_FX32 0x6000
#define OW_WILD_FOLLOWER_EMERGE_OVERLAP_FX32 0x20000

#define OW_WILD_FOLLOWER_BALL_SIDE_CURVE_FX32 0x5000
#define OW_WILD_FOLLOWER_BALL_MOTION_SCALE 256
#define OW_WILD_FOLLOWER_BALL_ACCEL_END 64
#define OW_WILD_FOLLOWER_BALL_DECEL_DIVISOR 192
#define OW_WILD_FOLLOWER_BALL_HANG_FRAMES 4
#define OW_WILD_FOLLOWER_BALL_FALL_FRAMES 12
#define OW_WILD_FOLLOWER_BALL_ROTATION_MIN_STEP 0x2000
#define OW_WILD_FOLLOWER_BALL_ROTATION_MAX_STEP 0x4000
#define OW_WILD_FOLLOWER_BALL_ROTATION_HANG_END_STEP 0x800

/* Match the follower recall's cubic pull, but apply it to the ball only. */
static const u16 sOverworldWildFollowerReturnProgress[
    OW_WILD_FOLLOWER_RETURN_FRAMES] = {
    0, 1, 4, 9, 18, 32, 50, 75, 108, 148, 197, 256
};

static s32 OverworldWildFollowerRelease_DirectionDeltaX(u8 direction)
{
    return direction == OW_WILD_HELPER_DIRECTION_LEFT
        ? -1
        : direction == OW_WILD_HELPER_DIRECTION_RIGHT ? 1 : 0;
}

static s32 OverworldWildFollowerRelease_DirectionDeltaY(u8 direction)
{
    return direction == OW_WILD_HELPER_DIRECTION_UP
        ? -1
        : direction == OW_WILD_HELPER_DIRECTION_DOWN ? 1 : 0;
}

void __attribute__((section(".follower_release_render")))
OverworldWildSpawns_RenderPlayerBallProjectile(
    void *rawProjectile,
    OverworldWildFollowerReleaseRotationCallback rotate)
{
    OverworldWildFollowerReleaseProjectile *projectile = rawProjectile;
    OverworldWildSpawnState *state =
        (OverworldWildSpawnState *)projectile->opaquePointers[1];
    LocalMapObject *object = (LocalMapObject *)projectile->opaquePointers[4];
    u32 curve;
    u32 motionProgress;
    u32 phaseProgress;
    u32 timeProgress;
    u16 rotationStep;
    s32 renderX;
    s32 renderY;
    s32 renderZ;
    s32 handHeight;
    s32 sideOffset;

    if (object == NULL || projectile->totalFrames == 0) {
        return;
    }
    if (state != NULL
        && (state->followerReleaseState
                & OW_WILD_FOLLOWER_RELEASE_STATE_MASK)
            == OW_WILD_FOLLOWER_RELEASE_BOUNCING) {
        OverworldWildSpawns_RenderFollowerReleaseBounce(
            rawProjectile,
            rotate);
        return;
    }
    phaseProgress = projectile->totalFrames
        - OW_WILD_FOLLOWER_BALL_HANG_FRAMES
        - OW_WILD_FOLLOWER_BALL_FALL_FRAMES;
    if (projectile->elapsedFrames <= phaseProgress) {
        timeProgress = projectile->elapsedFrames
            * OW_WILD_FOLLOWER_BALL_MOTION_SCALE
            / phaseProgress;
        if (timeProgress <= OW_WILD_FOLLOWER_BALL_ACCEL_END) {
            motionProgress = timeProgress * timeProgress
                / OW_WILD_FOLLOWER_BALL_ACCEL_END;
            rotationStep = OW_WILD_FOLLOWER_BALL_ROTATION_MIN_STEP;
        } else {
            timeProgress -= OW_WILD_FOLLOWER_BALL_ACCEL_END;
            motionProgress = OW_WILD_FOLLOWER_BALL_ACCEL_END
                + 2 * timeProgress
                - timeProgress * timeProgress
                    / OW_WILD_FOLLOWER_BALL_DECEL_DIVISOR;
            rotationStep = OW_WILD_FOLLOWER_BALL_ROTATION_MIN_STEP
                + (OW_WILD_FOLLOWER_BALL_ROTATION_MAX_STEP
                    - OW_WILD_FOLLOWER_BALL_ROTATION_MIN_STEP)
                    * timeProgress
                    / OW_WILD_FOLLOWER_BALL_DECEL_DIVISOR;
        }
        handHeight = projectile->startHeight;
    } else if (projectile->elapsedFrames
        <= phaseProgress + OW_WILD_FOLLOWER_BALL_HANG_FRAMES) {
        motionProgress = OW_WILD_FOLLOWER_BALL_MOTION_SCALE;
        timeProgress = projectile->elapsedFrames - phaseProgress;
        rotationStep = OW_WILD_FOLLOWER_BALL_ROTATION_MAX_STEP
            - (OW_WILD_FOLLOWER_BALL_ROTATION_MAX_STEP
                - OW_WILD_FOLLOWER_BALL_ROTATION_HANG_END_STEP)
                * timeProgress
                / OW_WILD_FOLLOWER_BALL_HANG_FRAMES;
        handHeight = projectile->startHeight;
    } else {
        motionProgress = OW_WILD_FOLLOWER_BALL_MOTION_SCALE;
        timeProgress = projectile->elapsedFrames
            - phaseProgress
            - OW_WILD_FOLLOWER_BALL_HANG_FRAMES;
        rotationStep = OW_WILD_FOLLOWER_BALL_ROTATION_HANG_END_STEP
            - OW_WILD_FOLLOWER_BALL_ROTATION_HANG_END_STEP
                * timeProgress
                / OW_WILD_FOLLOWER_BALL_FALL_FRAMES;
        handHeight = projectile->startHeight
            - projectile->startHeight
                * (s32)timeProgress
                * (s32)timeProgress
                * (s32)timeProgress
                / (OW_WILD_FOLLOWER_BALL_FALL_FRAMES
                    * OW_WILD_FOLLOWER_BALL_FALL_FRAMES
                    * OW_WILD_FOLLOWER_BALL_FALL_FRAMES);
    }
    renderX = projectile->startX
        + (projectile->targetX - projectile->startX)
            * (s32)motionProgress
            / OW_WILD_FOLLOWER_BALL_MOTION_SCALE;
    renderY = projectile->startY
        + (projectile->targetY - projectile->startY)
            * (s32)motionProgress
            / OW_WILD_FOLLOWER_BALL_MOTION_SCALE;
    renderZ = projectile->startZ
        + (projectile->targetZ - projectile->startZ)
            * (s32)motionProgress
            / OW_WILD_FOLLOWER_BALL_MOTION_SCALE;
    curve = 4
        * motionProgress
        * (OW_WILD_FOLLOWER_BALL_MOTION_SCALE - motionProgress)
        / OW_WILD_FOLLOWER_BALL_MOTION_SCALE;
    sideOffset = (OW_WILD_FOLLOWER_BALL_SIDE_CURVE_FX32 * (s32)curve)
        / OW_WILD_FOLLOWER_BALL_MOTION_SCALE;
    renderX += OverworldWildFollowerRelease_DirectionDeltaY(object->curFacing)
        * sideOffset;
    renderZ -= OverworldWildFollowerRelease_DirectionDeltaX(object->curFacing)
        * sideOffset;
    object->posVec[0] = (u32)renderX;
    object->posVec[1] = (u32)renderY;
    object->posVec[2] = (u32)renderZ;
    object->hCurr = (int)(renderY >> 15);
    object->faceVec[0] = 0;
    object->faceVec[1] = (u32)handHeight;
    object->faceVec[2] = 0;
    object->unk88[0] = 0;
    object->unk88[1] = (u32)handHeight;
    object->unk88[2] = 0;
    object->unk94[0] = 0;
    object->unk94[1] = 0;
    object->unk94[2] = 0;
    if (projectile->elapsedFrames != 0) {
        projectile->rotation = (s16)((u16)projectile->rotation + rotationStep);
    }
    rotate(projectile->rotation);
    MapObject_ClearBits(object, BIT_VANISH);
}

BOOL __attribute__((section(".follower_release_tick")))
OverworldWildSpawns_TickFollowerReleasePresentation(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    void *rawProjectile,
    OverworldWildFollowerReleaseDispatchCallback dispatch,
    OverworldWildFollowerReleaseRotationCallback rotate)
{
    OverworldWildFollowerReleaseProjectile *projectile = rawProjectile;
    LocalMapObject *ball = (LocalMapObject *)projectile->opaquePointers[4];
    LocalMapObject *follower =
        state->spawns[OW_WILD_FOLLOWER_SLOT].object;
    u8 frame = projectile->shakeIndex;
    u8 fallFrame;

    rotate(projectile->rotation);

    if (frame == 0) {
        projectile->impactSlot = OW_WILD_FOLLOWER_SLOT;
        projectile->impactEncounterGeneration =
            state->spawns[OW_WILD_FOLLOWER_SLOT].encounterGeneration;
        projectile->startHeight = (s32)ball->faceVec[1]
            + (((s32)ball->posVec[1]
                - (s32)follower->posVec[1]
                + OW_WILD_FOLLOWER_BALL_VISUAL_CENTER_FX32
                + OW_WILD_FOLLOWER_EMERGE_OVERLAP_FX32) >> 1);
        follower->posVec[0] = ball->posVec[0];
        follower->posVec[2] = ball->posVec[2];
        follower->faceVec[0] = 0;
        follower->faceVec[2] = 0;
        follower->unk88[0] = 0;
        follower->unk88[2] = 0;
        follower->unk94[0] = 0;
        follower->unk94[1] = 0;
        follower->unk94[2] = 0;
        MapObject_SetBits(
            follower,
            BIT_VANISH
                | BIT_JUMP_START
                | BIT_MOVE_START
                | MAPOBJECTFLAG_UNK13);
        state->captureTargetMask |=
            (u16)(1u << OW_WILD_FOLLOWER_SLOT);
    }
    if (frame < OW_WILD_FOLLOWER_RELEASE_FRAMES) {
        if (frame < OW_WILD_FOLLOWER_FALL_START_FRAME) {
            follower->faceVec[1] = (u32)projectile->startHeight;
        } else {
            fallFrame = frame - OW_WILD_FOLLOWER_FALL_START_FRAME + 1;
            follower->faceVec[1] = (u32)(projectile->startHeight
                * (OW_WILD_FOLLOWER_FALL_PROGRESS_SCALE
                    - fallFrame * fallFrame)
                >> 6);
        }
        follower->unk88[1] = follower->faceVec[1];
        if (frame == OW_WILD_FOLLOWER_PRIME_FRAMES) {
            MapObject_ClearBits(follower, BIT_VANISH);
        }
        projectile->shakeIndex++;
        return TRUE;
    }
    if (frame == OW_WILD_FOLLOWER_RELEASE_FRAMES) {
        follower->faceVec[1] = 0;
        follower->unk88[1] = 0;
        MapObject_ClearBits(
            follower,
            BIT_JUMP_START | BIT_MOVE_START | MAPOBJECTFLAG_UNK13);
        dispatch(fieldSystem, OW_WILD_FOLLOWER_RELEASE_DISPATCH_RESTORE);
        /* The follower owns its AI again as soon as it has landed. */
        state->movementCooldowns[OW_WILD_FOLLOWER_SLOT] = 1;
        state->captureTargetMask &=
            (u16)~(1u << OW_WILD_FOLLOWER_SLOT);
        /* Palette scratch aliases targetZ; preserve the real endpoint. */
        projectile->targetZ = (s32)ball->posVec[2];
        projectile->startHeight = (s32)ball->faceVec[1];
    }
    frame -= OW_WILD_FOLLOWER_RELEASE_FRAMES;
    if (frame < OW_WILD_FOLLOWER_RETURN_FRAMES) {
        return OverworldWildSpawns_ReturnFollowerReleaseBall(
            fieldSystem,
            projectile,
            sOverworldWildFollowerReturnProgress[frame]);
    }
    state->followerReleaseState = OW_WILD_FOLLOWER_RELEASE_NONE;
    dispatch(fieldSystem, OW_WILD_FOLLOWER_RELEASE_DISPATCH_CANCEL);
    return FALSE;
}

void __attribute__((section(".follower_release_aggro")))
OverworldWildSpawns_EnterAggroState(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *spawnedFollower)
{
    state->spawns[slot].active = TRUE | OW_WILD_SPAWN_AGGRO_FLAG;
    state->movementActiveSteps[slot] = 0;
    if (spawnedFollower != NULL) {
        spawnedFollower->flags |= BIT_VANISH;
        state->movementSpotStates[slot] = 2;
    }
}
