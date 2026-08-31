#include "../../include/overworld_wild_runtime.h"

#include "../../include/constants/species.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_walk_module.h"

#pragma GCC optimize("no-if-conversion")

#define OW_WILD_RUNTIME_FX32_ONE (1 << FX32_SHIFT)
#define OW_WILD_RUNTIME_MATCH_ANY_SPECIES SPECIES_NONE
#define OW_WILD_RUNTIME_MATCH_ANY_U8 0xFF
#define OW_WILD_RUNTIME_MATCH_LEVEL_ANY 0
#define OW_WILD_RUNTIME_BEHAVIOR_GROUP_NONE 0
#define OW_WILD_RUNTIME_BEHAVIOR_KIND_MAX 11
#define OW_WILD_RUNTIME_LOCOMOTION_MAX 11
#define OW_WILD_RUNTIME_TARGET_NONE 0
#define OW_WILD_RUNTIME_TARGET_MAX 9
#define OW_WILD_RUNTIME_BOOL_YES 1
#define OW_WILD_RUNTIME_STEP_PARTICLE_SET_BITS 0x00010004
#define OW_WILD_RUNTIME_STEP_PARTICLE_CLEAR_BITS 0x00100000
#define OW_WILD_RUNTIME_PROFILE_MOVEMENT_RANGE 32
#define OW_WILD_RUNTIME_CIRCLE_RADIUS_MAX 8
#define OW_WILD_RUNTIME_BATTLE_TRIGGER_MAX 2
#define OW_WILD_RUNTIME_SURFACE_MODEL_NONE 0xFF
/* Vanilla sub_02061248 queries terrain height into a caller-owned vector. */
#define OW_WILD_RUNTIME_QUERY_NATIVE_HEIGHT \
    ((BOOL (*)(FieldSystem *, VecFx32 *, BOOL))0x02061249)

typedef struct OverworldWildRuntimeSurfaceBlockCache {
    u16 blockIndex;
    u8 matrixId;
    u8 modelIndex;
} OverworldWildRuntimeSurfaceBlockCache;

/* The behavior-data overlay owns one fixed surface catalog. Matrix identity
 * is therefore sufficient to invalidate this compact per-block cache. */
static OverworldWildRuntimeSurfaceBlockCache sOverworldWildSurfaceBlockCache = {
    0,
    0xFF,
    OW_WILD_RUNTIME_SURFACE_MODEL_NONE,
};

/* Overlay 1 normally owns each object-facing vector. A mounted follower is a
 * presentation child of the player, so its controller-owned vector must not
 * be replaced later in the same frame. UNK31 is reserved for that one state. */
void __attribute__((naked, noinline, used,
        section(".overworld_wild_runtime_mount_facing")))
OverworldWildRuntime_SetFacingVectorUnlessMounted(
    LocalMapObject *object,
    VecFx32 *facingVector)
{
    __asm__(
        "ldr r2, [r0, #0]\n"
        "cmp r2, #0\n"
        "bmi 1f\n"
        "ldr r3, 2f\n"
        "bx r3\n"
        "1: bx lr\n"
        ".align 2\n"
        "2: .word 0x0205F97D\n");
}

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

BOOL __attribute__((noinline, optimize("Os", "expensive-optimizations", "tree-dominator-opts", "tree-pre", "tree-copy-prop")))
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
        || fieldSystem->map_matrix == NULL) {
        return FALSE;
    }
    matrix = (const u8 *)fieldSystem->map_matrix;
    if ((u32)blockX >= matrix[0]
        || (u32)blockY >= matrix[1]) {
        return FALSE;
    }
    blockIndex = blockX + blockY * matrix[0];
    if (sOverworldWildSurfaceBlockCache.matrixId == matrix[2]
        && sOverworldWildSurfaceBlockCache.blockIndex == blockIndex) {
        modelIndex = sOverworldWildSurfaceBlockCache.modelIndex;
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
        sOverworldWildSurfaceBlockCache.blockIndex = blockIndex;
        sOverworldWildSurfaceBlockCache.matrixId = matrix[2];
        sOverworldWildSurfaceBlockCache.modelIndex = modelIndex;
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

static s32 __attribute__((noinline, optimize("Os", "expensive-optimizations", "tree-dominator-opts", "tree-pre", "tree-copy-prop")))
OverworldWildRuntime_GetGroundBaseY(
    FieldSystem *fieldSystem,
    const OverworldWildSurfaceCatalog *catalog,
    LocalMapObject *object,
    int x,
    int y)
{
    OverworldWildSurfaceHit hit;
    VecFx32 targetPosition;

    if (OverworldWildRuntime_QuerySurface(
            fieldSystem,
            catalog,
            x,
            y,
            &hit)
        && hit.surfaceId != OW_WILD_SURFACE_ID_NATIVE_GROUND) {
        return hit.height;
    }

    targetPosition.x = (x << 4) * OW_WILD_RUNTIME_FX32_ONE
        + (OW_WILD_RUNTIME_FX32_ONE << 3);
    targetPosition.y = (s32)object->posVec[1];
    targetPosition.z = (y << 4) * OW_WILD_RUNTIME_FX32_ONE
        + (OW_WILD_RUNTIME_FX32_ONE << 3);
    if ((object->flags & MAPOBJECTFLAG_UNK23) == 0
        && OW_WILD_RUNTIME_QUERY_NATIVE_HEIGHT(
            fieldSystem,
            &targetPosition,
            (object->flags & MAPOBJECTFLAG_UNK29) != 0)) {
        return targetPosition.y;
    }
    return (s32)object->posVec[1];
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
    state->turnDirection = 0;
    state->resumeSpeed = 0;
}

static void __attribute__((noinline)) OverworldWildRuntime_ApplyWalkEffect(
    OverworldWildWalkEffectCallback effect,
    void *context,
    u8 direction,
    BOOL skid)
{
    if (effect != NULL) {
        effect(context, direction, skid);
    }
}

static void OverworldWildRuntime_SetWalkMomentum(
    OverworldWildWalkMomentumState *state,
    u8 baseSpeed,
    u8 spotState,
    OverworldWildWalkEffectCallback effect,
    void *context)
{
    OverworldWildRuntime_WalkMomentumReset(state);
    state->speed = baseSpeed;
    state->baseSpeed = baseSpeed;
    state->spotState = spotState;
    OverworldWildRuntime_ApplyWalkEffect(
        effect,
        context,
        OW_WILD_WALK_DIRECTION_NONE,
        FALSE);
}

static void OverworldWildRuntime_EnsureWalkMomentum(
    OverworldWildWalkMomentumState *state,
    u8 baseSpeed,
    u8 spotState,
    OverworldWildWalkEffectCallback effect,
    void *context)
{
    if (state->speed == 0
        || state->baseSpeed != baseSpeed
        || state->spotState != spotState) {
        OverworldWildRuntime_SetWalkMomentum(
            state,
            baseSpeed,
            spotState,
            effect,
            context);
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
    BOOL preventTurnSkid = FALSE;
    BOOL fortyFiveDegreeTurn;
    u8 oldDirection;
    u8 skidTiles;

    if (state == NULL || startStep == NULL) {
        return FALSE;
    }
    if (state->skidRemaining != 0) {
        /* The direction selected when the skid began owns the full skid. */
        return TRUE;
    }
    baseSpeed = OVERWORLD_WALK_MODULE_ENTRY->clampTime(baseSpeed);
    if (requestedDirection != OW_WILD_WALK_DIRECTION_NONE) {
        preventTurnSkid = (requestedDirection
            & OW_WILD_WALK_DIRECTION_NO_TURN_SKID_FLAG) != 0;
        requestedDirection &=
            ~OW_WILD_WALK_DIRECTION_NO_TURN_SKID_FLAG;
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
        skidTiles = OVERWORLD_WALK_MODULE_ENTRY->skidTiles(state->speed);
        if (oldDirection != OW_WILD_WALK_DIRECTION_NONE && skidTiles != 0) {
            state->skidRemaining = skidTiles;
            state->turnDirection = OW_WILD_WALK_DIRECTION_NONE;
            state->resumeSpeed = state->baseSpeed;
            state->speed = OVERWORLD_WALK_MODULE_ENTRY->skidTime(state->speed);
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
        OverworldWildRuntime_SetWalkMomentum(
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
    fortyFiveDegreeTurn =
        OVERWORLD_WALK_MODULE_ENTRY->isFortyFiveDegreeTurn(
            oldDirection,
            requestedDirection);
    skidTiles = fortyFiveDegreeTurn
        ? 0
        : OVERWORLD_WALK_MODULE_ENTRY->skidTiles(state->speed);
    if (skidTiles != 0 && !preventTurnSkid) {
        state->skidRemaining = skidTiles;
        state->turnDirection = requestedDirection;
        state->resumeSpeed = state->speed;
        state->speed = OVERWORLD_WALK_MODULE_ENTRY->skidTime(state->speed);
        if (startStep(
                context,
                oldDirection,
                state->speed,
                requestedDirection,
                TRUE,
                TRUE)) {
            return TRUE;
        }
        OverworldWildRuntime_SetWalkMomentum(
            state,
            baseSpeed,
            spotState,
            effect,
            context);
        /* The blocked skid consumes the chosen turn; AI may not dodge it. */
        return TRUE;
    }
    state->resumeSpeed = 0;

    OverworldWildRuntime_ApplyWalkEffect(
        effect,
        context,
        requestedDirection,
        FALSE);
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
    u8 fastestTravelTime,
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

    baseSpeed = OVERWORLD_WALK_MODULE_ENTRY->clampTime(baseSpeed);
    fastestTravelTime = OVERWORLD_WALK_MODULE_ENTRY->clampTime(
        fastestTravelTime);
    if (fastestTravelTime > baseSpeed) {
        fastestTravelTime = baseSpeed;
    }
    wasSkidding = state->skidRemaining != 0;
    if (!walkStillActive
        || state->speed == 0
        || state->baseSpeed != baseSpeed
        || state->spotState != spotState) {
        OverworldWildRuntime_WalkMomentumReset(state);
        OverworldWildRuntime_ApplyWalkEffect(
            effect,
            context,
            OW_WILD_WALK_DIRECTION_NONE,
            FALSE);
        return wasSkidding;
    }

    if (wasSkidding) {
        turnDirection = state->turnDirection;
        /* A multi-tile skid is one maneuver. Emit its landing feedback once,
         * on the final tile, instead of allocating one effect per tile. */
        if (state->skidRemaining == 1) {
            OverworldWildRuntime_ApplyWalkEffect(
                effect,
                context,
                turnDirection,
                TRUE);
        }
        state->skidRemaining--;
        if (state->skidRemaining != 0) {
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
            OverworldWildRuntime_SetWalkMomentum(
                state,
                baseSpeed,
                spotState,
                effect,
                context);
            return TRUE;
        }

        if (turnDirection == OW_WILD_WALK_DIRECTION_NONE) {
            OverworldWildRuntime_SetWalkMomentum(
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
        state->turnDirection = 0;
        state->tileCounter = 0;
        OverworldWildRuntime_ApplyWalkEffect(
            effect,
            context,
            turnDirection,
            FALSE);
        if (startStep(
                context,
                turnDirection,
                state->speed,
                turnDirection,
                TRUE,
                FALSE)) {
            /* Mark the committed post-skid step so it completes the turn
             * before normal acceleration accounting resumes. */
            state->resumeSpeed = state->speed;
        } else {
            OverworldWildRuntime_SetWalkMomentum(
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
        state->speed = OVERWORLD_WALK_MODULE_ENTRY->accelerateTime(
            state->speed,
            fastestTravelTime);
    }
    return FALSE;
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
        { 0, 0, 0, 0, 0, 0 },
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
        && entry->reservedResolverCallbacks[0] == 0
        && entry->reservedResolverCallbacks[1] == 0
        && entry->reservedResolverCallbacks[2] == 0
        && entry->reservedResolverCallbacks[3] == 0
        && entry->reservedResolverCallbacks[4] == 0
        && entry->reservedResolverCallbacks[5] == 0
        && entry->playStepDirtParticle != NULL
        && entry->playLandingHopParticle != NULL;
}
