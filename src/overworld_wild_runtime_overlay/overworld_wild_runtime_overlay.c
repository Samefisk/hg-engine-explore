#include "../../include/overworld_wild_runtime.h"

#include "../../include/constants/species.h"
#include "../../include/map_events_internal.h"

#define OW_WILD_RUNTIME_FX32_ONE (1 << FX32_SHIFT)
#define OW_WILD_RUNTIME_MATCH_ANY_SPECIES SPECIES_NONE
#define OW_WILD_RUNTIME_MATCH_ANY_U8 0xFF
#define OW_WILD_RUNTIME_MATCH_LEVEL_ANY 0
#define OW_WILD_RUNTIME_BEHAVIOR_GROUP_NONE 0
#define OW_WILD_RUNTIME_BEHAVIOR_KIND_MAX 11
#define OW_WILD_RUNTIME_LOCOMOTION_MAX 8
#define OW_WILD_RUNTIME_TARGET_NONE 0
#define OW_WILD_RUNTIME_TARGET_MAX 9
#define OW_WILD_RUNTIME_BOOL_YES 1
#define OW_WILD_RUNTIME_STEP_PARTICLE_SET_BITS 0x00010004
#define OW_WILD_RUNTIME_STEP_PARTICLE_CLEAR_BITS 0x00100000
#define OW_WILD_RUNTIME_PROFILE_MOVEMENT_RANGE 32
#define OW_WILD_RUNTIME_CIRCLE_RADIUS_MAX 8
#define OW_WILD_RUNTIME_BATTLE_TRIGGER_MAX 2
#define OW_WILD_RUNTIME_SURFACE_MODEL_NONE 0xFF
static OverworldWildSurfaceBlockCache sFollowerSelectorSurfaceBlockCache;

void OverworldWildRuntime_PlayStepDirtParticle(LocalMapObject *object)
{
    if (object == NULL) {
        return;
    }

    MapObject_SetBits(object, OW_WILD_RUNTIME_STEP_PARTICLE_SET_BITS);
    ov01_022000DC(object);
    MapObject_ClearBits(object, OW_WILD_RUNTIME_STEP_PARTICLE_CLEAR_BITS);
}

void OverworldWildRuntime_PlayLandingHopParticle(LocalMapObject *object)
{
    if (object == NULL) {
        return;
    }

    /* This is the normal-ground landing branch used by sub_02060114. */
    ov01_021FF74C(object);
}

BOOL __attribute__((noinline, optimize("Os", "expensive-optimizations", "tree-dominator-opts", "if-conversion", "tree-pre", "tree-copy-prop")))
OverworldWildRuntime_QuerySurface(
    FieldSystem *fieldSystem,
    const OverworldWildSurfaceCatalog *catalog,
    int x,
    int y,
    OverworldWildSurfaceHit *hit)
{
    const OverworldWildSurfaceModelDirectoryEntry *model;
    const OverworldWildSurfaceInstance *instance;
    const OverworldWildSurfaceTemplate *template;
    const u8 *matrix;
    u32 anchorBlockIndex;
    u32 blockIndex;
    u8 modelIndex;
    int blockX = x >> OW_WILD_MAP_BLOCK_SHIFT;
    int blockY = y >> OW_WILD_MAP_BLOCK_SHIFT;
    int i;

    if (fieldSystem == NULL
        || fieldSystem->map_matrix == NULL
        || catalog == NULL
        || hit == NULL) {
        return FALSE;
    }
    matrix = (const u8 *)fieldSystem->map_matrix;
    if ((u32)blockX >= matrix[0]
        || (u32)blockY >= matrix[1]) {
        return FALSE;
    }
    blockIndex = blockX + blockY * matrix[0];
    if (sFollowerSelectorSurfaceBlockCache.catalog == catalog
        && sFollowerSelectorSurfaceBlockCache.matrixId == matrix[2]
        && sFollowerSelectorSurfaceBlockCache.blockIndex == blockIndex) {
        modelIndex = sFollowerSelectorSurfaceBlockCache.modelIndex;
    } else {
        u16 landDataId = *(const u16 *)(matrix
            + OW_WILD_MAP_MATRIX_MODELS_OFFSET
            + blockIndex * sizeof(u16));

        model = catalog->models;
        for (i = 0; i < OWBD_SURFACE_MODEL_COUNT; i++, model++) {
            if (model->landDataId >= landDataId) {
                break;
            }
        }
        if (i == OWBD_SURFACE_MODEL_COUNT || model->landDataId != landDataId) {
            modelIndex = OW_WILD_RUNTIME_SURFACE_MODEL_NONE;
        } else {
            modelIndex = (u8)i;
        }
        sFollowerSelectorSurfaceBlockCache.catalog = catalog;
        sFollowerSelectorSurfaceBlockCache.blockIndex = blockIndex;
        sFollowerSelectorSurfaceBlockCache.matrixId = matrix[2];
        sFollowerSelectorSurfaceBlockCache.modelIndex = modelIndex;
    }
    if (modelIndex == OW_WILD_RUNTIME_SURFACE_MODEL_NONE) {
        return FALSE;
    }
    model = &catalog->models[modelIndex];
    instance = OVERWORLD_WILD_SURFACE_SERVICE_ENTRY->query(
        &catalog->instances[model->firstInstance],
        catalog->templates,
        model->instanceCount,
        ((u32)x & OW_WILD_MAP_BLOCK_MASK)
            | (((u32)y & OW_WILD_MAP_BLOCK_MASK) << OW_WILD_MAP_BLOCK_SHIFT));
    if (instance == NULL || instance->surfaceType >= OW_WILD_SURFACE_TYPE_COUNT) {
        return FALSE;
    }
    template = &catalog->templates[instance->templateId];
    anchorBlockIndex = blockIndex + instance->anchorBlockDx
        + instance->anchorBlockDy * matrix[0];
    if (instance->heightPage == OW_WILD_SURFACE_HEIGHT_PAGE_NATIVE_GROUND) {
        hit->height = 0;
        hit->surfaceId = OW_WILD_SURFACE_ID_NATIVE_GROUND;
    } else {
        hit->height = (instance->heightPage << 20)
            + (instance->heightQ4 << OW_WILD_ROOF_HEIGHT_QUANTUM_SHIFT)
            + (matrix[OW_WILD_MAP_MATRIX_ALTITUDES_OFFSET + anchorBlockIndex]
                << OW_WILD_MAP_ALTITUDE_HEIGHT_SHIFT);
        hit->surfaceId = (u16)((anchorBlockIndex << OW_WILD_SURFACE_ID_BLOCK_SHIFT)
            | instance->localSurfaceId);
    }
    hit->surfaceType = instance->surfaceType;
    hit->nodeId = (u8)(((y & OW_WILD_MAP_BLOCK_MASK) - instance->minY)
            * template->width
        + (x & OW_WILD_MAP_BLOCK_MASK) - instance->minX);
    return TRUE;
}

static s32 __attribute__((noinline, optimize("Os", "expensive-optimizations", "tree-dominator-opts", "if-conversion", "tree-pre", "tree-copy-prop")))
OverworldWildRuntime_GetGroundBaseY(
    FieldSystem *fieldSystem,
    const OverworldWildSurfaceCatalog *catalog,
    LocalMapObject *object,
    int x,
    int y)
{
    OverworldWildSurfaceHit hit;
    u32 savedFlags;
    u32 savedFlags2;
    u32 savedPosX;
    u32 savedPosY;
    u32 savedPosZ;
    int savedHInit;
    int savedHPrev;
    int savedHCurr;
    s32 baseY;

    if (OverworldWildRuntime_QuerySurface(
            fieldSystem,
            catalog,
            x,
            y,
            &hit)
        && hit.surfaceId != OW_WILD_SURFACE_ID_NATIVE_GROUND) {
        return hit.height;
    }

    savedFlags = object->flags;
    savedFlags2 = object->flags2;
    savedPosX = object->posVec[0];
    savedPosY = object->posVec[1];
    savedPosZ = object->posVec[2];
    savedHInit = object->hInit;
    savedHPrev = object->hPrev;
    savedHCurr = object->hCurr;
    baseY = (s32)savedPosY;

    object->posVec[0] = (u32)((x << 4) * OW_WILD_RUNTIME_FX32_ONE
        + (OW_WILD_RUNTIME_FX32_ONE << 3));
    object->posVec[2] = (u32)((y << 4) * OW_WILD_RUNTIME_FX32_ONE
        + (OW_WILD_RUNTIME_FX32_ONE << 3));
    if (MapObject_RefreshHeightFromTerrain(object)) {
        baseY = (s32)object->posVec[1];
    }

    object->flags = savedFlags;
    object->flags2 = savedFlags2;
    object->posVec[0] = savedPosX;
    object->posVec[1] = savedPosY;
    object->posVec[2] = savedPosZ;
    object->hInit = savedHInit;
    object->hPrev = savedHPrev;
    object->hCurr = savedHCurr;
    return baseY;
}

static u8 OverworldWildRuntime_ClampWalkSpeed(u8 speed)
{
    if (speed < OW_WILD_WALK_SPEED_MIN) {
        return OW_WILD_WALK_SPEED_MIN;
    }
    if (speed > OW_WILD_WALK_SPEED_MAX) {
        return OW_WILD_WALK_SPEED_MAX;
    }
    return speed;
}

void OverworldWildRuntime_WalkMomentumReset(
    OverworldWildWalkMomentumState *state)
{
    if (state == NULL) {
        return;
    }

    state->direction = OW_WILD_WALK_DIRECTION_NONE;
    state->tileCounter = 0;
    state->speed = 0;
    state->baseSpeed = 0;
    state->spotState = OW_WILD_WALK_DIRECTION_NONE;
    state->skidRemaining = 0;
    state->turnDirection = OW_WILD_WALK_DIRECTION_NONE;
    state->resumeSpeed = 0;
}

static void OverworldWildRuntime_EnsureWalkMomentum(
    OverworldWildWalkMomentumState *state,
    u8 baseSpeed,
    u8 spotState,
    OverworldWildWalkEffectCallback effect,
    void *context)
{
    baseSpeed = OverworldWildRuntime_ClampWalkSpeed(baseSpeed);
    if (state->speed != 0
        && state->baseSpeed == baseSpeed
        && state->spotState == spotState) {
        return;
    }

    OverworldWildRuntime_WalkMomentumReset(state);
    state->speed = baseSpeed;
    state->baseSpeed = baseSpeed;
    state->spotState = spotState;
    if (effect != NULL) {
        effect(context, OW_WILD_WALK_DIRECTION_NONE, FALSE);
    }
}

static void OverworldWildRuntime_StopWalkMomentum(
    OverworldWildWalkMomentumState *state,
    u8 baseSpeed,
    u8 spotState,
    OverworldWildWalkEffectCallback effect,
    void *context)
{
    OverworldWildRuntime_WalkMomentumReset(state);
    state->speed = OverworldWildRuntime_ClampWalkSpeed(baseSpeed);
    state->baseSpeed = state->speed;
    state->spotState = spotState;
    if (effect != NULL) {
        effect(context, OW_WILD_WALK_DIRECTION_NONE, FALSE);
    }
}

BOOL OverworldWildRuntime_WalkMomentumStart(
    OverworldWildWalkMomentumState *state,
    u8 requestedDirection,
    u8 baseSpeed,
    u8 spotState,
    OverworldWildWalkStartStepCallback startStep,
    OverworldWildWalkEffectCallback effect,
    void *context)
{
    u8 oldDirection;
    u8 speedGain;

    if (state == NULL || startStep == NULL) {
        return FALSE;
    }
    if (state->skidRemaining != 0) {
        /* The direction selected when the skid began owns the full skid. */
        return TRUE;
    }

    OverworldWildRuntime_EnsureWalkMomentum(
        state,
        baseSpeed,
        spotState,
        effect,
        context);
    oldDirection = state->direction;
    if (requestedDirection == OW_WILD_WALK_DIRECTION_NONE) {
        state->tileCounter = 0;
        speedGain = state->speed - state->baseSpeed;
        if (oldDirection != OW_WILD_WALK_DIRECTION_NONE && speedGain != 0) {
            /* Acceleration gains 1/2/3 map to 1/2/4 skid tiles. */
            state->skidRemaining = 1u << (speedGain - 1u);
            state->turnDirection = OW_WILD_WALK_DIRECTION_NONE;
            state->resumeSpeed = state->baseSpeed;
            state->speed--;
            if (startStep(
                    context,
                    oldDirection,
                    state->speed,
                    oldDirection,
                    TRUE,
                    TRUE)) {
                return TRUE;
            }
        }
        OverworldWildRuntime_StopWalkMomentum(
            state,
            baseSpeed,
            spotState,
            effect,
            context);
        return FALSE;
    }
    if (oldDirection == OW_WILD_WALK_DIRECTION_NONE
        || requestedDirection == oldDirection) {
        /* One committed move in the resumed direction breaks a skid chain. */
        state->direction = requestedDirection;
        if (startStep(
                context,
                requestedDirection,
                state->speed,
                requestedDirection,
                FALSE,
                FALSE)) {
            state->resumeSpeed = 0;
            return TRUE;
        }
        return FALSE;
    }

    state->tileCounter = 0;
    speedGain = state->speed - state->baseSpeed;
    if (speedGain != 0) {
        state->skidRemaining = 1u << (speedGain - 1u);
        state->turnDirection = requestedDirection;
        state->resumeSpeed = state->speed - 1u;
        state->speed--;
        if (startStep(
                context,
                oldDirection,
                state->speed,
                requestedDirection,
                TRUE,
                TRUE)) {
            return TRUE;
        }
        OverworldWildRuntime_StopWalkMomentum(
            state,
            baseSpeed,
            spotState,
            effect,
            context);
        /* The blocked skid consumes the chosen turn; AI may not dodge it. */
        return TRUE;
    }
    state->resumeSpeed = 0;

    if (effect != NULL) {
        effect(context, requestedDirection, FALSE);
    }
    state->direction = requestedDirection;
    return startStep(
        context,
        requestedDirection,
        state->speed,
        requestedDirection,
        FALSE,
        FALSE);
}

BOOL OverworldWildRuntime_WalkMomentumFinish(
    OverworldWildWalkMomentumState *state,
    u8 baseSpeed,
    u8 spotState,
    u8 tilesToAccelerate,
    u8 completedDirection,
    u8 completedDistance,
    BOOL walkStillActive,
    OverworldWildWalkStartStepCallback startStep,
    OverworldWildWalkEffectCallback effect,
    void *context)
{
    BOOL wasSkidding;
    u8 turnDirection;

    if (state == NULL || startStep == NULL) {
        return FALSE;
    }

    baseSpeed = OverworldWildRuntime_ClampWalkSpeed(baseSpeed);
    wasSkidding = state->skidRemaining != 0;
    if (!walkStillActive
        || state->speed == 0
        || state->baseSpeed != baseSpeed
        || state->spotState != spotState) {
        OverworldWildRuntime_WalkMomentumReset(state);
        if (effect != NULL) {
            effect(context, OW_WILD_WALK_DIRECTION_NONE, FALSE);
        }
        return wasSkidding;
    }

    if (wasSkidding) {
        turnDirection = state->turnDirection;
        if (effect != NULL) {
            effect(context, turnDirection, TRUE);
        }
        state->skidRemaining--;
        if (state->skidRemaining != 0) {
            if (state->speed > state->baseSpeed) {
                state->speed--;
            }
            if (startStep(
                    context,
                    state->direction,
                    state->speed,
                    turnDirection == OW_WILD_WALK_DIRECTION_NONE
                        ? state->direction
                        : turnDirection,
                    TRUE,
                    TRUE)) {
                return TRUE;
            }
            OverworldWildRuntime_StopWalkMomentum(
                state,
                baseSpeed,
                spotState,
                effect,
                context);
            return TRUE;
        }

        if (turnDirection == OW_WILD_WALK_DIRECTION_NONE) {
            OverworldWildRuntime_StopWalkMomentum(
                state,
                baseSpeed,
                spotState,
                effect,
                context);
            /* Stop skids begin after the real Walk tile's completion policy;
             * consume their final tile so cooldown/stamina are not applied twice. */
            return TRUE;
        }

        state->skidRemaining = 0;
        state->speed = state->resumeSpeed;
        state->resumeSpeed = 0;
        state->direction = turnDirection;
        state->turnDirection = OW_WILD_WALK_DIRECTION_NONE;
        state->tileCounter = 0;
        if (effect != NULL) {
            effect(context, turnDirection, FALSE);
        }
        if (startStep(
                context,
                turnDirection,
                state->speed,
                turnDirection,
                TRUE,
                FALSE)) {
            /* Mark the committed post-skid step so it cannot immediately
             * accelerate away the turn's one-speed momentum loss. */
            state->resumeSpeed = state->speed;
        } else {
            OverworldWildRuntime_StopWalkMomentum(
                state,
                baseSpeed,
                spotState,
                effect,
                context);
        }
        return TRUE;
    }

    if (completedDistance != 1 || completedDirection != state->direction) {
        return FALSE;
    }
    if (state->resumeSpeed != 0) {
        state->resumeSpeed = 0;
        return FALSE;
    }
    if (tilesToAccelerate != 0 && state->tileCounter != 0xFF) {
        state->tileCounter++;
    }
    if (tilesToAccelerate != 0
        && state->tileCounter >= tilesToAccelerate) {
        state->tileCounter = 0;
        if (state->speed < OW_WILD_WALK_SPEED_MAX) {
            state->speed++;
        }
    }
    return FALSE;
}

BOOL OverworldWildRuntime_BehaviorMatchApplies(
    const OverworldWildBehaviorContext *context,
    const OverworldWildBehaviorMatch *match)
{
    if (context == NULL || match == NULL) {
        return FALSE;
    }
    if (match->species != OW_WILD_RUNTIME_MATCH_ANY_SPECIES
        && match->species != context->species) {
        return FALSE;
    }
    if (match->groupMask != OW_WILD_RUNTIME_BEHAVIOR_GROUP_NONE
        && (context->groupFlags & match->groupMask) == 0) {
        return FALSE;
    }
    if (match->terrain != OW_WILD_RUNTIME_MATCH_ANY_U8
        && match->terrain != context->terrain) {
        return FALSE;
    }
    if (match->minLevel != OW_WILD_RUNTIME_MATCH_LEVEL_ANY
        && context->level < match->minLevel) {
        return FALSE;
    }
    if (match->maxLevel != OW_WILD_RUNTIME_MATCH_LEVEL_ANY
        && context->level > match->maxLevel) {
        return FALSE;
    }
    if (match->shiny != OW_WILD_RUNTIME_MATCH_ANY_U8
        && match->shiny != context->shiny) {
        return FALSE;
    }
    if (match->behaviorClass != OW_WILD_RUNTIME_MATCH_ANY_U8
        && match->behaviorClass != context->behaviorClass) {
        return FALSE;
    }
    return TRUE;
}

BOOL OverworldWildRuntime_OverrideTargetsContext(
    const OverworldWildBehaviorContext *context,
    const OverworldWildBehaviorOverrideProfile *overrideProfile,
    const u16 *overrideMembers,
    u16 overrideMemberCount)
{
    int memberEnd;
    int i;

    if (overrideProfile == NULL
        || overrideProfile->targetMode == OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED
        || !OverworldWildRuntime_BehaviorMatchApplies(
            context,
            &overrideProfile->match)) {
        return FALSE;
    }
    if (overrideProfile->targetMode == OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL) {
        return TRUE;
    }
    if (overrideProfile->targetMode != OW_WILD_BEHAVIOR_OVERRIDE_TARGET_MEMBERS
        || overrideProfile->memberCount == 0
        || overrideMembers == NULL) {
        return FALSE;
    }
    memberEnd = overrideProfile->memberStart + overrideProfile->memberCount;
    if (memberEnd > overrideMemberCount) {
        return FALSE;
    }
    for (i = overrideProfile->memberStart; i < memberEnd; i++) {
        if (overrideMembers[i] == context->species) {
            return TRUE;
        }
    }
    return FALSE;
}

static const u8 sOverworldWildRuntimeBehaviorRelativeFieldMaximums[] = {
    0, 0, 0, 255, 64, 64, 64, 4, 64, 0, 0, 0, 0, 0, 0, 0, 100, 0, 0,
    0, 12, 12, 255, 64, 255, 0, 10, 8, 8, 32, 255, 0, 0, 0, 64, 32, 4,
    15, 64, 15, 0, 0, 32, 255, 0, 0, 255, 255, 32, 4, 0, 0, 0, 8, 8, 8, 4,
    5, 0, 0, 0,
};

typedef char OverworldWildRuntimeBehaviorRelativeFieldCountMustRemain61[
    NELEMS(sOverworldWildRuntimeBehaviorRelativeFieldMaximums) == 61 ? 1 : -1];
typedef char OverworldWildRuntimeBehaviorProfileDataSizeMustRemain66[
    sizeof(OverworldWildBehaviorProfileData) == 66 ? 1 : -1];
typedef char OverworldWildRuntimeBehaviorFieldsBeforeTerrainMustRemain32[
    __builtin_offsetof(OverworldWildBehaviorProfileData, chainPauseAction) == 31
        && __builtin_offsetof(OverworldWildBehaviorProfileData,
               chillAllowedTerrainMask) == 32
        ? 1
        : -1];
typedef char OverworldWildRuntimeBehaviorTerrainOverrideGapMustRemainTwoBytes[
    __builtin_offsetof(OverworldWildBehaviorProfileData,
        chillAllowedTerrainOverrideMask) == 34
        && __builtin_offsetof(OverworldWildBehaviorProfileData, hopTime) == 36
        ? 1
        : -1];
typedef char OverworldWildRuntimeBehaviorLastByteFieldMustRemain51[
    __builtin_offsetof(OverworldWildBehaviorProfileData, tilesToAccelerate) == 50
        && __builtin_offsetof(OverworldWildBehaviorProfileData,
               maxWalkSpeed) == 51
        && __builtin_offsetof(OverworldWildBehaviorProfileData,
               spawnDestinationMask) == 52
        ? 1
        : -1];
typedef char OverworldWildRuntimeBehaviorVerticalObstacleOptionMustRemain56[
    __builtin_offsetof(OverworldWildBehaviorProfileData,
        hopAllowVerticalObstacles) == 56
        && __builtin_offsetof(OverworldWildBehaviorProfileData,
               chainRepositionJumpCount) == 57
            && __builtin_offsetof(OverworldWildBehaviorProfileData,
               hopSwayWidth) == 58
            && __builtin_offsetof(OverworldWildBehaviorProfileData,
               spawnHopSwayWidth) == 59
            && __builtin_offsetof(OverworldWildBehaviorProfileData,
               chainRepositionSpeed) == 60
            && __builtin_offsetof(OverworldWildBehaviorProfileData,
               chainRepositionDistance) == 61
            && __builtin_offsetof(OverworldWildBehaviorProfileData,
               chainRepositionDust) == 62
            && __builtin_offsetof(OverworldWildBehaviorProfileData,
               chainRepositionAllowCardinal) == 63
            && __builtin_offsetof(OverworldWildBehaviorProfileData,
               chainRepositionAllowDiagonal) == 64
        ? 1
        : -1];

static u8 OverworldWildRuntime_GetBehaviorOverrideFieldOffset(u8 fieldIndex)
{
    if (fieldIndex < 34) {
        return fieldIndex;
    }
    return fieldIndex < 52 ? fieldIndex + 2 : fieldIndex + 4;
}

#define OW_WILD_RUNTIME_BOUNDED_FIELDS_1 0x01C00180u
#define OW_WILD_RUNTIME_BOUNDED_FIELDS_2 0x00001F84u
#define OW_WILD_RUNTIME_BOUNDED_FIELDS_3 0x0000F8F3u

static BOOL OverworldWildRuntime_AreProfileMovementSpeedsValid(
    const OverworldWildBehaviorProfileData *profile)
{
    return profile != NULL
        && profile->chillSpeed >= OW_WILD_WALK_SPEED_MIN
        && profile->chillSpeed <= OW_WILD_WALK_SPEED_MAX;
}

static BOOL OverworldWildRuntime_AreExactOverrideMovementSpeedsValid(
    const OverworldWildBehaviorOverrideProfile *profile)
{
    u32 operatorMask;

    if (profile == NULL) {
        return FALSE;
    }
    operatorMask = profile->relativeMask | profile->atLeastMask
        | profile->atMostMask;
    if ((profile->mask & OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED)
        && !(operatorMask & OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED)
        && (profile->profile.chillSpeed < OW_WILD_WALK_SPEED_MIN
            || profile->profile.chillSpeed > OW_WILD_WALK_SPEED_MAX)) {
        return FALSE;
    }
    return TRUE;
}

static BOOL OverworldWildRuntime_IsMovementSpeedField(u8 fieldIndex)
{
    return fieldIndex == 7 || fieldIndex == 49 || fieldIndex == 53
        || fieldIndex == 56;
}

static BOOL OverworldWildRuntime_IsOverrideOperatorMaskValid(
    u32 activeMask,
    u32 operatorMask,
    u32 allowedMask,
    u8 fieldIndex,
    const OverworldWildBehaviorOverrideProfile *profile,
    u32 compoundMask,
    BOOL bounded)
{
    const u8 *overrideBytes = (const u8 *)&profile->profile;
    const u8 *compoundBytes = (const u8 *)&profile->compoundBoundProfile;

    if ((activeMask & ~allowedMask) != 0
        || (operatorMask & ~allowedMask) != 0) {
        return FALSE;
    }
    while (operatorMask != 0
        && fieldIndex
            < NELEMS(sOverworldWildRuntimeBehaviorRelativeFieldMaximums)) {
        if (operatorMask & 1u) {
            u8 maximum =
                sOverworldWildRuntimeBehaviorRelativeFieldMaximums[fieldIndex];
            u8 offset = OverworldWildRuntime_GetBehaviorOverrideFieldOffset(
                fieldIndex);
            u8 value = (compoundMask & 1u)
                ? compoundBytes[offset]
                : overrideBytes[offset];

            if (!(activeMask & 1u)
                || maximum == 0
                || (!bounded && value == 0x80)
                || (bounded && value > maximum)
                || (bounded
                    && OverworldWildRuntime_IsMovementSpeedField(fieldIndex)
                    && value == 0)) {
                return FALSE;
            }
        }
        activeMask >>= 1;
        operatorMask >>= 1;
        compoundMask >>= 1;
        fieldIndex++;
    }
    return operatorMask == 0;
}

static BOOL OverworldWildRuntime_IsOverrideOperatorFamilyValid(
    const OverworldWildBehaviorOverrideProfile *profile,
    u32 operatorMask,
    u16 operatorMask2,
    u32 operatorMask3,
    BOOL bounded)
{
    u32 compoundMask = bounded ? profile->relativeMask & operatorMask : 0;
    u32 compoundMask2 = bounded ? profile->relativeMask2 & operatorMask2 : 0;
    u32 compoundMask3 = bounded ? profile->relativeMask3 & operatorMask3 : 0;

    if (bounded
        && ((operatorMask & ~OW_WILD_RUNTIME_BOUNDED_FIELDS_1) != 0
            || (operatorMask2 & ~OW_WILD_RUNTIME_BOUNDED_FIELDS_2) != 0
            || (operatorMask3 & ~OW_WILD_RUNTIME_BOUNDED_FIELDS_3) != 0)) {
        return FALSE;
    }
    return OverworldWildRuntime_IsOverrideOperatorMaskValid(
               profile->mask,
               operatorMask,
               0x07FFFFFF,
               0,
               profile,
               compoundMask,
               bounded)
        && OverworldWildRuntime_IsOverrideOperatorMaskValid(
            profile->mask2,
            operatorMask2,
            0x00007FFF,
            27,
            profile,
            compoundMask2,
            bounded)
        && OverworldWildRuntime_IsOverrideOperatorMaskValid(
            profile->mask3,
            operatorMask3,
            0x0007FFFF,
            42,
            profile,
            compoundMask3,
            bounded);
}

static BOOL OverworldWildRuntime_AreOverrideOperatorMasksValid(
    const OverworldWildBehaviorOverrideProfile *profile)
{
    if (profile == NULL
        || ((profile->atLeastMask & profile->atMostMask) != 0)
        || ((profile->atLeastMask2 & profile->atMostMask2) != 0)
        || ((profile->atLeastMask3 & profile->atMostMask3) != 0)) {
        return FALSE;
    }
    return OverworldWildRuntime_IsOverrideOperatorFamilyValid(
               profile,
               profile->relativeMask,
               profile->relativeMask2,
               profile->relativeMask3,
               FALSE)
        && OverworldWildRuntime_IsOverrideOperatorFamilyValid(
            profile,
            profile->atLeastMask,
            profile->atLeastMask2,
            profile->atLeastMask3,
            TRUE)
        && OverworldWildRuntime_IsOverrideOperatorFamilyValid(
            profile,
            profile->atMostMask,
            profile->atMostMask2,
            profile->atMostMask3,
            TRUE);
}

BOOL OverworldWildRuntime_ValidateBehaviorDataBlob(
    const OverworldWildBehaviorDataBlob *blob)
{
    const OverworldWildBehaviorDataBlobHeader *header;
    int i;

    if (blob == NULL) {
        return FALSE;
    }
    header = &blob->header;
    if (header->magic != OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC
        || header->version != OVERWORLD_WILD_BEHAVIOR_DATA_VERSION
        || header->headerSize != sizeof(OverworldWildBehaviorDataBlobHeader)
        || header->blobSize != sizeof(OverworldWildBehaviorDataBlob)
        || header->classProfileSize != sizeof(OverworldWildBehaviorProfileData)
        || header->overrideProfileSize
            != sizeof(OverworldWildBehaviorOverrideProfile)) {
        return FALSE;
    }

    for (i = 0; i < OWBD_CLASS_PROFILE_COUNT; i++) {
        if (!OverworldWildRuntime_AreProfileMovementSpeedsValid(
                &blob->classProfiles[i])) {
            return FALSE;
        }
    }
    for (i = 0; i < OWBD_OVERRIDE_PROFILE_COUNT; i++) {
        const OverworldWildBehaviorOverrideProfile *profile =
            &blob->overrideProfiles[i];

        if (!OverworldWildRuntime_AreOverrideOperatorMasksValid(profile)
            || !OverworldWildRuntime_AreExactOverrideMovementSpeedsValid(
                profile)) {
            return FALSE;
        }
    }
    return TRUE;
}

static u16 OverworldWildRuntime_GetLegacySpawnDestinationMask(u8 destination)
{
    switch ((OverworldWildSpawnDestination)destination) {
    case OW_WILD_SPAWN_DESTINATION_CANOPY:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY;
    case OW_WILD_SPAWN_DESTINATION_LAND:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND;
    case OW_WILD_SPAWN_DESTINATION_GRASS:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS;
    case OW_WILD_SPAWN_DESTINATION_SHORE:
    case OW_WILD_SPAWN_DESTINATION_WATER:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER;
    case OW_WILD_SPAWN_DESTINATION_FRONT_OF_PLAYER:
    case OW_WILD_SPAWN_DESTINATION_TWO_TILES_FRONT_OF_PLAYER:
    case OW_WILD_SPAWN_DESTINATION_THREE_TILES_FRONT_OF_PLAYER:
    case OW_WILD_SPAWN_DESTINATION_FOUR_TILES_FRONT_OF_PLAYER:
    case OW_WILD_SPAWN_DESTINATION_FIVE_TILES_FRONT_OF_PLAYER:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT;
    case OW_WILD_SPAWN_DESTINATION_FIVE_TILES_BEHIND_PLAYER:
    case OW_WILD_SPAWN_DESTINATION_ONE_TILE_BEHIND_PLAYER:
    case OW_WILD_SPAWN_DESTINATION_TWO_TILES_BEHIND_PLAYER:
    case OW_WILD_SPAWN_DESTINATION_THREE_TILES_BEHIND_PLAYER:
    case OW_WILD_SPAWN_DESTINATION_FOUR_TILES_BEHIND_PLAYER:
    case OW_WILD_SPAWN_DESTINATION_NEXT_TO_PLAYER:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER;
    case OW_WILD_SPAWN_DESTINATION_ROOFTOP:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ROOFTOP;
    case OW_WILD_SPAWN_DESTINATION_SIGNPOST:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SIGNPOST;
    case OW_WILD_SPAWN_DESTINATION_MAILBOX:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_MAILBOX;
    case OW_WILD_SPAWN_DESTINATION_FLOWERBED:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_FLOWERBED;
    case OW_WILD_SPAWN_DESTINATION_POOL:
    default:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND
            | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER
            | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY
            | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS;
    }
}

void OverworldWildRuntime_ApplyBehaviorOverrideMask(
    OverworldWildBehaviorProfileData *profile,
    const OverworldWildBehaviorProfileData *overrideProfile,
    u32 mask,
    u32 relativeMask,
    u32 atLeastMask,
    u32 atMostMask,
    const OverworldWildBehaviorProfileData *compoundBoundProfile,
    u8 fieldIndex)
{
    u8 *profileBytes = (u8 *)profile;
    const u8 *overrideBytes = (const u8 *)overrideProfile;
    const u8 *compoundBoundBytes = (const u8 *)compoundBoundProfile;

    while (mask != 0
        && fieldIndex < NELEMS(sOverworldWildRuntimeBehaviorRelativeFieldMaximums)) {
        if (mask & 1u) {
            u8 offset = OverworldWildRuntime_GetBehaviorOverrideFieldOffset(
                fieldIndex);
            if (relativeMask & 1u) {
                int adjusted = (int)profileBytes[offset]
                    + (int)(s8)overrideBytes[offset];
                int minimum = fieldIndex == 7
                    || fieldIndex == 27
                    || fieldIndex == 28
                    || (fieldIndex >= 48 && fieldIndex < 54)
                    || fieldIndex == 56
                    || fieldIndex == 57;
                int maximum =
                    sOverworldWildRuntimeBehaviorRelativeFieldMaximums[fieldIndex];
                if (adjusted < minimum) {
                    adjusted = minimum;
                } else if (adjusted > maximum) {
                    adjusted = maximum;
                }
                profileBytes[offset] = (u8)adjusted;
            }
            if ((atLeastMask & 1u) || (atMostMask & 1u)) {
                u8 threshold = (relativeMask & 1u)
                    ? compoundBoundBytes[offset]
                    : overrideBytes[offset];
                if ((atLeastMask & 1u) && profileBytes[offset] < threshold) {
                    profileBytes[offset] = threshold;
                } else if ((atMostMask & 1u) && profileBytes[offset] > threshold) {
                    profileBytes[offset] = threshold;
                }
            } else if (!(relativeMask & 1u)) {
                profileBytes[offset] = overrideBytes[offset];
            }
        }
        mask >>= 1;
        relativeMask >>= 1;
        atLeastMask >>= 1;
        atMostMask >>= 1;
        fieldIndex++;
    }
}

static void OverworldWildRuntime_ApplyBehaviorOverride(
    OverworldWildBehaviorProfileData *profile,
    const OverworldWildBehaviorOverrideProfile *overrideProfile)
{
    u16 explicitDestinationMask;
    u16 explicitTerrainMask;
    u16 mask2;
    u32 mask3;

    if (profile == NULL || overrideProfile == NULL) {
        return;
    }
    mask2 = overrideProfile->mask2;
    mask3 = overrideProfile->mask3;
    OverworldWildRuntime_ApplyBehaviorOverrideMask(
        profile, &overrideProfile->profile, overrideProfile->mask,
        overrideProfile->relativeMask, overrideProfile->atLeastMask,
        overrideProfile->atMostMask, &overrideProfile->compoundBoundProfile, 0);
    OverworldWildRuntime_ApplyBehaviorOverrideMask(
        profile,
        &overrideProfile->profile,
        mask2 & ~(OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TERRAIN_MASK
            | OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TERRAIN_OVERRIDE_MASK),
        overrideProfile->relativeMask2,
        overrideProfile->atLeastMask2,
        overrideProfile->atMostMask2,
        &overrideProfile->compoundBoundProfile,
        27);
    if (mask2 & OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TERRAIN_OVERRIDE_MASK) {
        explicitTerrainMask = overrideProfile->profile.chillAllowedTerrainOverrideMask
            & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
        profile->chillAllowedTerrainMask =
            (profile->chillAllowedTerrainMask & ~explicitTerrainMask)
            | (overrideProfile->profile.chillAllowedTerrainMask & explicitTerrainMask);
    }
    OverworldWildRuntime_ApplyBehaviorOverrideMask(
        profile,
        &overrideProfile->profile,
        mask3 & ~(OW_WILD_BEHAVIOR_OVERRIDE3_SPAWN_DESTINATION_MASK
            | OW_WILD_BEHAVIOR_OVERRIDE3_SPAWN_DESTINATION_OVERRIDE_MASK),
        overrideProfile->relativeMask3,
        overrideProfile->atLeastMask3,
        overrideProfile->atMostMask3,
        &overrideProfile->compoundBoundProfile,
        42);
    if (mask3 & OW_WILD_BEHAVIOR_OVERRIDE3_SPAWN_DESTINATION_OVERRIDE_MASK) {
        explicitDestinationMask = overrideProfile->profile.spawnDestinationOverrideMask
            & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
        profile->spawnDestinationMask =
            (profile->spawnDestinationMask & ~explicitDestinationMask)
            | (overrideProfile->profile.spawnDestinationMask & explicitDestinationMask);
        profile->spawnDestinationOverrideMask |= explicitDestinationMask;
    } else if (overrideProfile->mask & OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_DESTINATION) {
        profile->spawnDestinationMask =
            OverworldWildRuntime_GetLegacySpawnDestinationMask(
                profile->spawnDestination);
        profile->spawnDestinationOverrideMask = OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
    }
}

void __attribute__((noinline, optimize("Os", "expensive-optimizations", "tree-dominator-opts", "if-conversion", "tree-pre", "tree-copy-prop")))
OverworldWildRuntime_NormalizeMovementProfile(
    OverworldWildBehaviorProfileData *profile,
    u8 invalidState)
{
    if (profile->chillState > OW_WILD_RUNTIME_BEHAVIOR_KIND_MAX) {
        profile->chillState = invalidState;
    }
    if (profile->chillAction > OW_WILD_RUNTIME_LOCOMOTION_MAX) {
        profile->chillAction = 0;
    }
    if (profile->chillTarget > OW_WILD_RUNTIME_TARGET_MAX) {
        profile->chillTarget = OW_WILD_RUNTIME_TARGET_NONE;
    }
    if (profile->hopAllowNonCardinal > OW_WILD_RUNTIME_BOOL_YES) {
        profile->hopAllowNonCardinal = OW_WILD_RUNTIME_BOOL_YES;
    }
    if (profile->hopMaxDistance < profile->hopMinDistance) {
        profile->hopMaxDistance = profile->hopMinDistance;
    }
    if (profile->ramAccelerationSteps > OW_WILD_RUNTIME_PROFILE_MOVEMENT_RANGE) {
        profile->ramAccelerationSteps = OW_WILD_RUNTIME_PROFILE_MOVEMENT_RANGE;
    }
    if (profile->chainMovementVariance > OW_WILD_RUNTIME_PROFILE_MOVEMENT_RANGE) {
        profile->chainMovementVariance = OW_WILD_RUNTIME_PROFILE_MOVEMENT_RANGE;
    }
    if (profile->tilesToAccelerate == 0) {
        profile->tilesToAccelerate = OW_WILD_BEHAVIOR_TILES_TO_ACCELERATE_DEFAULT;
    } else if (profile->tilesToAccelerate > OW_WILD_RUNTIME_PROFILE_MOVEMENT_RANGE) {
        profile->tilesToAccelerate = OW_WILD_RUNTIME_PROFILE_MOVEMENT_RANGE;
    }
    if (profile->chainPauseAction > OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS) {
        profile->chainPauseAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE;
    }
    if (profile->circleRadius > OW_WILD_RUNTIME_CIRCLE_RADIUS_MAX) {
        profile->circleRadius = OW_WILD_RUNTIME_CIRCLE_RADIUS_MAX;
    }
    if (profile->battleTrigger > OW_WILD_RUNTIME_BATTLE_TRIGGER_MAX) {
        profile->battleTrigger = OW_WILD_RUNTIME_TARGET_NONE;
    }
}

void OverworldWildRuntime_ResolveInheritedPolicies(
    OverworldWildBehaviorProfileData *profile)
{
    u16 explicitTerrainMask = profile->chillAllowedTerrainOverrideMask
        & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
    u16 explicitDestinationMask = profile->spawnDestinationOverrideMask
        & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
    u16 legacyDestinationMask =
        OverworldWildRuntime_GetLegacySpawnDestinationMask(
            profile->spawnDestination);

    profile->chillAllowedTerrainMask =
        (profile->chillAllowedTerrainMask & explicitTerrainMask)
        | (OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_DEFAULT & ~explicitTerrainMask);
    profile->spawnDestinationMask =
        (profile->spawnDestinationMask & explicitDestinationMask)
        | (legacyDestinationMask & ~explicitDestinationMask);
    profile->spawnDestinationOverrideMask = explicitDestinationMask;
}


static BOOL OverworldWildRuntime_ValidateImpl(void);

const OverworldWildRuntimeOverlayEntry gOverworldWildRuntimeOverlayEntry
    __attribute__((section(".overworld_wild_runtime_entry"), used)) = {
        OVERWORLD_WILD_RUNTIME_MAGIC,
        OVERWORLD_WILD_RUNTIME_VERSION,
        sizeof(OverworldWildRuntimeOverlayEntry),
        OverworldWildRuntime_ValidateImpl,
        OverworldWildRuntime_QuerySurface,
        OverworldWildRuntime_GetGroundBaseY,
        OverworldWildRuntime_WalkMomentumReset,
        OverworldWildRuntime_WalkMomentumStart,
        OverworldWildRuntime_WalkMomentumFinish,
        OverworldWildRuntime_BehaviorMatchApplies,
        OverworldWildRuntime_OverrideTargetsContext,
        OverworldWildRuntime_ApplyBehaviorOverride,
        OverworldWildRuntime_NormalizeMovementProfile,
        OverworldWildRuntime_ResolveInheritedPolicies,
        OverworldWildRuntime_ValidateBehaviorDataBlob,
        OverworldWildRuntime_PlayStepDirtParticle,
        OverworldWildRuntime_PlayLandingHopParticle,
};

static BOOL OverworldWildRuntime_ValidateImpl(void)
{
    const OverworldWildRuntimeOverlayEntry *entry =
        &gOverworldWildRuntimeOverlayEntry;

    return entry->magic == OVERWORLD_WILD_RUNTIME_MAGIC
        && entry->version == OVERWORLD_WILD_RUNTIME_VERSION
        && entry->size == sizeof(*entry)
        && entry->validate != NULL
        && entry->querySurface != NULL
        && entry->getGroundBaseY != NULL
        && entry->walkMomentumReset != NULL
        && entry->walkMomentumStart != NULL
        && entry->walkMomentumFinish != NULL
        && entry->behaviorMatchApplies != NULL
        && entry->overrideTargetsContext != NULL
        && entry->applyBehaviorOverride != NULL
        && entry->normalizeMovementProfile != NULL
        && entry->resolveInheritedPolicies != NULL
        && entry->validateBehaviorDataBlob != NULL
        && entry->playStepDirtParticle != NULL
        && entry->playLandingHopParticle != NULL;
}
