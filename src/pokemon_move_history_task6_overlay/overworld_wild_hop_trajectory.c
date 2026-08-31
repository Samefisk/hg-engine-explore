#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/overworld_wild_runtime.h"
#include "../../include/overworld_wild_helper.h"
#include "../../include/map_events_internal.h"

#define OW_WILD_CHAIN_REPOSITION_ACTIVE 0x80
#define OW_WILD_CHAIN_REPOSITION_STEP 0x40
#define OW_WILD_CHAIN_REPOSITION_SKID 0x20
#define OW_WILD_CHAIN_REPOSITION_DUST 0x10
#define OW_WILD_CHAIN_REPOSITION_MODE_MASK 0x60
#define OW_WILD_CHAIN_REPOSITION_COUNT_MASK 0x0F
#define OW_WILD_HOP_OBSTACLE_CLEARANCE_FX32 (1 << FX32_SHIFT)
#define OW_WILD_OFFSCREEN_HOP_DISTANCE 16

static s32 OverworldWild_LerpJumpFx32(
    s32 start,
    s32 target,
    u32 elapsed,
    u32 total);

static const OverworldWildBehaviorProfileData *
    __attribute__((noinline, section(".overworld_wild_hop_trajectory_code")))
OverworldWild_GetHopLane(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState)
{
    if (spotState == OW_WILD_SPOT_STATE_ACTIVE) {
        return &profile->active;
    }
    if (spotState == OW_WILD_SPOT_STATE_TIRED) {
        return &profile->tired;
    }
    return &profile->owner;
}

static BOOL __attribute__((section(".overworld_wild_hop_trajectory_code")))
OverworldWild_TryGetBehaviorHopVector(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState,
    int dx,
    int dy,
    u8 *direction,
    u8 *distance)
{
    const OverworldWildBehaviorProfileData *lane;
    int absDx = dx < 0 ? -dx : dx;
    int absDy = dy < 0 ? -dy : dy;
    int jumpDistance = absDx > absDy ? absDx : absDy;

    if (jumpDistance == 0) {
        return FALSE;
    }
    lane = OverworldWild_GetHopLane(profile, spotState);
    if (((absDx == 0 || absDy == 0)
            && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(
                lane->hopAllowNonCardinal))
        || (absDx != 0 && absDy != 0
            && (!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
                    lane->hopAllowNonCardinal)
                || absDx != absDy))
        || jumpDistance < lane->hopMinDistance
        || jumpDistance > lane->hopMaxDistance) {
        return FALSE;
    }

    if (direction == NULL) {
        return TRUE;
    }
    *direction = absDx >= absDy ? 2 + (dx > 0) : (dy > 0);
    *distance = (u8)jumpDistance;
    return TRUE;
}

static BOOL __attribute__((section(".overworld_wild_hop_trajectory_code")))
OverworldWild_ResolveHopTrajectory(
    FieldSystem *fieldSystem,
    const OverworldWildSurfaceCatalog *surfaceCatalog,
    const OverworldWildBehaviorProfileData *lane,
    LocalMapObject *object,
    s32 startBaseY,
    s32 targetBaseY,
    int startX,
    int startY,
    int targetX,
    int targetY,
    u8 distance,
    u32 *trajectoryOut)
{
    u32 trajectory;
    u32 totalFrames;
    u8 arcHeightQ4;
    int tileIndex;

    trajectory = OVERWORLD_WILD_SURFACE_SERVICE_ENTRY->calculateJumpTrajectory(
        lane->hopTime,
        distance,
        targetBaseY - startBaseY,
        lane->hopElevationTimeScale
            | ((u16)lane->hopElevationArcScale << 8));
    totalFrames = trajectory & 0xFFFF;
    arcHeightQ4 = (u8)(trajectory >> 16);
    if (totalFrames < 2 || distance < 2) {
        *trajectoryOut = trajectory;
        return TRUE;
    }

    for (tileIndex = 1; tileIndex < distance; tileIndex++) {
        u32 denominator = 2 * distance;
        OverworldWildSurfaceHit hit;
        s32 obstacleBaseY;
        int tileX;
        int tileY;
        int edge;

        tileX = OverworldWild_LerpJumpFx32(
            (startX << 16) + 0x8000,
            (targetX << 16) + 0x8000,
            tileIndex,
            distance) >> 16;
        tileY = OverworldWild_LerpJumpFx32(
            (startY << 16) + 0x8000,
            (targetY << 16) + 0x8000,
            tileIndex,
            distance) >> 16;
        if (distance != OW_WILD_OFFSCREEN_HOP_DISTANCE) {
            if (!OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->querySurface(
                    fieldSystem,
                    surfaceCatalog,
                    tileX,
                    tileY,
                    &hit)
                || hit.surfaceId == OW_WILD_SURFACE_ID_NATIVE_GROUND) {
                continue;
            }
            obstacleBaseY = hit.height;
        } else {
            obstacleBaseY = OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
                fieldSystem,
                surfaceCatalog,
                object,
                tileX,
                tileY);
        }

        /* Height is concave over one constant-height footprint, so the
         * travel interval's minimum is at one of its two boundaries. */
        for (edge = -1; edge <= 1; edge += 2) {
            u32 numerator = totalFrames * (2 * tileIndex + edge);
            u32 elapsed = edge < 0
                ? numerator / denominator
                : (numerator + denominator - 1) / denominator;
            s32 baseY;
            s32 unitArc;
            s32 obstructionDelta;
            u32 required;

            if (elapsed == 0) {
                elapsed = 1;
            } else if (elapsed >= totalFrames) {
                elapsed = totalFrames - 1;
            }
            baseY = OverworldWild_LerpJumpFx32(
                startBaseY,
                targetBaseY,
                elapsed,
                totalFrames);
            if (obstacleBaseY <= baseY) {
                continue;
            }
            unitArc = OVERWORLD_WILD_SURFACE_SERVICE_ENTRY->calculateJumpArc(
                elapsed,
                totalFrames,
                1);
            if (unitArc <= 0) {
                return FALSE;
            }
            obstructionDelta = obstacleBaseY - baseY
                + OW_WILD_HOP_OBSTACLE_CLEARANCE_FX32;
            if (unitArc * arcHeightQ4 >= obstructionDelta) {
                continue;
            }
            if (lane->hopAllowVerticalObstacles != 1) {
                return FALSE;
            }
            required = (u32)(obstructionDelta / unitArc) + 1;
            if (required > 0xFF) {
                return FALSE;
            }
            if (required > arcHeightQ4) {
                arcHeightQ4 = (u8)required;
            }
        }
    }

    *trajectoryOut = ((u32)arcHeightQ4 << 16) | totalFrames;
    return TRUE;
}

static BOOL __attribute__((section(".overworld_wild_hop_trajectory_code")))
OverworldWild_ValidateHopLanding(
    int landingX,
    int landingY,
    int targetX,
    int targetY,
    void *rawContext)
{
    OverworldWildBehaviorHopValidationContext *context = rawContext;

    /* The helper can call this from its large BFS frame. Keep planning to
     * landing rules here; StartPreparedCustomJumpCommand performs the exact
     * arc/surface check for the selected edge before any movement begins. */
    return context->baseValidator(
        context->state,
        context->slot,
        context->fieldSystem,
        context->allowedTile,
        landingX,
        landingY,
        targetX,
        targetY);
}

static void __attribute__((section(".overworld_wild_hop_trajectory_code")))
OverworldWild_BuildHopHelperConfig(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState,
    int objectX,
    int objectY,
    int targetX,
    int targetY,
    const u8 *directions,
    int directionCount,
    BOOL stopOneHopAway,
    void *rawConfig)
{
    OverworldWildHelperHopConfig *config = rawConfig;
    const OverworldWildBehaviorProfileData *lane =
        OverworldWild_GetHopLane(profile, spotState);

    config->objectX = objectX;
    config->objectY = objectY;
    config->targetX = targetX;
    config->targetY = targetY;
    config->minDistance = lane->hopMinDistance;
    config->maxDistance = lane->hopMaxDistance;
    config->allowNonCardinal = lane->hopAllowNonCardinal;
    config->stopOneHopAway = stopOneHopAway;
    config->directionCount = (u8)directionCount;
    while (directionCount != 0) {
        directionCount--;
        config->directions[directionCount] = directions[directionCount];
    }
}

static BOOL __attribute__((section(".overworld_wild_hop_trajectory_code"), optimize("Os")))
OverworldWild_RunChainReposition(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    u8 *movesRemaining)
{
    const OverworldWildBehaviorProfileData *lane;
    FieldSystem *fieldSystem;
    LocalMapObject *object;
    u8 encodedRemaining = *movesRemaining;
    u8 remaining;
    u8 repositionMode;
    u32 packedOffset;
    u8 startIndex;
    u8 attempt;
    u8 directionIndex;
    u8 distance;
    int targetX;
    int targetY;

    lane = OverworldWild_GetHopLane(profile, state->movementSpotStates[slot]);
    repositionMode = encodedRemaining & OW_WILD_CHAIN_REPOSITION_MODE_MASK;
    remaining = (encodedRemaining & OW_WILD_CHAIN_REPOSITION_ACTIVE) != 0
        ? (encodedRemaining & OW_WILD_CHAIN_REPOSITION_COUNT_MASK) - 1
        : lane->chainRepositionJumpCount;
    fieldSystem = state->movementFieldSystem;
    object = state->spawns[slot].object;
    if (fieldSystem == NULL || object == NULL) {
        *movesRemaining = 0;
        return FALSE;
    }
    startIndex = gf_rand();
    if (remaining == 0) {
        goto finished;
    }

    distance = repositionMode == OW_WILD_CHAIN_REPOSITION_SKID
        ? lane->chainRepositionDistance
        : 1;
    for (attempt = 0; attempt < 8; attempt++) {
        directionIndex = (startIndex + attempt) & 7;
        if ((&lane->chainRepositionAllowCardinal)[directionIndex >> 2] == 0) {
            continue;
        }
        packedOffset = 0x082A6419u >> (directionIndex << 2);
        targetX = object->xCurr + ((packedOffset & 3) - 1) * distance;
        targetY = object->yCurr + (((packedOffset >> 2) & 3) - 1) * distance;
        if (!OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->validateHopLanding(
                state,
                slot,
                fieldSystem,
                lane->chillAllowedTerrainMask,
                targetX,
                targetY,
                targetX,
                targetY)) {
            continue;
        }
        remaining |= lane->chainRepositionDust << 4;
        *movesRemaining = remaining
            | OW_WILD_CHAIN_REPOSITION_ACTIVE
            | repositionMode;
        if (OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->startPreparedCustomJump(
                state,
                fieldSystem,
                slot,
                object,
                object->curFacing,
                distance,
                targetX,
                targetY,
                profile,
                TRUE)) {
            movesRemaining[OW_WILD_MAX_SPAWNS * 2] +=
                (packedOffset & 3) - 1
                + (((packedOffset >> 2) & 3) - 1) * 4;
            state->movementStagedHopPending[slot] = TRUE;
            return TRUE;
        }
        break;
    }
finished:
    *movesRemaining = 0;
    return FALSE;
}

static s32 __attribute__((noinline)) OverworldWild_LerpJumpFx32(
    s32 start,
    s32 target,
    u32 elapsed,
    u32 total)
{
    s32 delta;
    s32 quotient;
    s32 remainder;

    if (total == 0 || elapsed >= total) {
        return target;
    }
    delta = target - start;
    quotient = delta / (s32)total;
    remainder = delta - quotient * (s32)total;
    return start + quotient * (s32)elapsed
        + remainder * (s32)elapsed / (s32)total;
}

static int OverworldWild_JumpTileFromFx32(s32 value)
{
    return value >> 16;
}

typedef struct OverworldWildCustomJumpRuntimePrefix {
    OVERWORLD_WILD_CUSTOM_JUMP_RUNTIME_PREFIX_FIELDS;
} OverworldWildCustomJumpRuntimePrefix;

static u8 __attribute__((section(".overworld_wild_hop_trajectory_code"), optimize("Os")))
OverworldWild_ApplyJumpRenderMotion(
    const void *runtimeState,
    int slot,
    LocalMapObject *object,
    u32 elapsed,
    u8 arcHeightQ4)
{
    OverworldWildCustomJumpRuntimePrefix *runtime;
    s32 baseY;
    s32 baseX;
    s32 arc;
    s32 sway;
    u32 swayElapsed;
    int logicalX;
    int logicalY;
    BOOL logicalChanged;
    u8 result;
    u8 spinSpeed;
    u8 packedSpinSpeed;
    u16 totalFrames;

    runtime = (OverworldWildCustomJumpRuntimePrefix *)runtimeState;
    totalFrames = runtime->movementCustomJumpFrameCounts[slot];
    packedSpinSpeed = runtime->movementCustomJumpSpinSpeeds[slot];
    baseY = OverworldWild_LerpJumpFx32(
        runtime->movementCustomJumpStartBaseY[slot],
        runtime->movementCustomJumpTargetBaseY[slot], elapsed, totalFrames);
    baseX = OverworldWild_LerpJumpFx32(
        ((s32)runtime->movementCustomJumpStartX[slot] << 16) + 0x8000,
        ((s32)runtime->movementCustomJumpTargetX[slot] << 16) + 0x8000,
        elapsed, totalFrames);
    object->posVec[2] = (u32)OverworldWild_LerpJumpFx32(
        ((s32)runtime->movementCustomJumpStartY[slot] << 16) + 0x8000,
        ((s32)runtime->movementCustomJumpTargetY[slot] << 16) + 0x8000,
        elapsed, totalFrames);
    swayElapsed = elapsed << 1;
    sway = OVERWORLD_WILD_SURFACE_SERVICE_ENTRY->calculateJumpArc(
        swayElapsed >= totalFrames ? swayElapsed - totalFrames : swayElapsed,
        totalFrames, packedSpinSpeed >> 4);
    if (swayElapsed >= totalFrames) {
        sway = -sway;
    }
    object->posVec[0] = (u32)baseX;
    if (runtime->movementCustomJumpStartY[slot]
        == runtime->movementCustomJumpTargetY[slot]) {
        object->posVec[2] = (u32)((s32)object->posVec[2] + sway);
    } else {
        object->posVec[0] = (u32)((s32)object->posVec[0] + sway);
    }
    logicalX = OverworldWild_JumpTileFromFx32((s32)object->posVec[0]);
    logicalY = OverworldWild_JumpTileFromFx32((s32)object->posVec[2]);
    logicalChanged = object->xCurr != logicalX || object->yCurr != logicalY;
    if (logicalChanged) {
        object->xPrev = object->xCurr;
        object->yPrev = object->yCurr;
        object->xCurr = logicalX;
        object->yCurr = logicalY;
    }
    arc = OVERWORLD_WILD_SURFACE_SERVICE_ENTRY->calculateJumpArc(
        elapsed, totalFrames, arcHeightQ4);
    object->hCurr = (int)(baseY >> 15);
    object->faceVec[0] = 0;
    object->posVec[1] = (u32)baseY;
    /* Autonomous wild-object rendering uses unk88 as its stable body-offset
     * carrier. Keeping faceVec at floor level avoids applying the same arc
     * twice while preserving the visible custom Hop. Mounted player motion
     * has its own renderer path and deliberately uses faceVec instead. */
    object->faceVec[1] = 0;
    object->faceVec[2] = 0;
    object->unk88[0] = 0;
    object->unk88[1] = (u32)arc;
    object->unk94[1] = 0;
    object->flags = (object->flags
            & ~(BIT_JUMP_START | BIT_VANISH | MAPOBJECTFLAG_UNK4
                | MAPOBJECTFLAG_UNK8 | MAPOBJECTFLAG_UNK22
                | MAPOBJECTFLAG_UNK30))
        | BIT_MOVE_START
        | MAPOBJECTFLAG_UNK13
        | (arcHeightQ4 != 0 ? BIT_JUMP_START : 0);
    result = logicalChanged ? 0x10 : 0;
    spinSpeed = packedSpinSpeed & 0x0F;
    if (spinSpeed != 0
        && elapsed > runtime->movementCustomJumpSpinElapsedFrames[slot]) {
        runtime->movementCustomJumpSpinElapsedFrames[slot] = (u16)elapsed;
        if (runtime->movementCustomJumpSpinTimers[slot] > 1) {
            runtime->movementCustomJumpSpinTimers[slot]--;
        } else {
            runtime->movementCustomJumpSpinTimers[slot] = spinSpeed;
            runtime->movementCustomJumpSpinSteps[slot] =
                (runtime->movementCustomJumpSpinSteps[slot] + 1) & 3;
            result |= 0x80 | runtime->movementCustomJumpSpinSteps[slot];
        }
    }
    return result;
}

const OverworldWildHopTrajectoryEntry gOverworldWildHopTrajectoryEntry
    __attribute__((section(".overworld_wild_hop_trajectory_entry"), used)) =
{
    OverworldWild_ResolveHopTrajectory,
    OverworldWild_TryGetBehaviorHopVector,
    OverworldWild_ValidateHopLanding,
    OverworldWild_BuildHopHelperConfig,
    OverworldWild_RunChainReposition,
    OverworldWild_ApplyJumpRenderMotion,
};
