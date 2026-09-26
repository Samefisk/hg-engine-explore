#include "../../include/overworld_wild_runtime.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_wild_spawns_internal.h"

#include "../../include/constants/species.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_walk_direction_policy.h"
#include "../../include/overworld_walk_module.h"
#include "../../include/overworld_walk_timing_policy.h"

/* Absolute linker imports do not carry ELF Thumb-function metadata. Mark the
 * resident helper entries here so direct BL relocations do not need veneers. */
__asm__(
    ".thumb\n"
    ".thumb_func\n.thumb_set OverworldWalk_DecelerateTime, 0x023BF400\n"
    ".thumb_func\n.thumb_set OverworldWalk_ProposeStep, 0x023BF45C\n"
    ".thumb_func\n.thumb_set OverworldWalk_ClampTime, 0x023BF488\n"
    ".thumb_func\n.thumb_set OverworldWalk_AccelerateTime, 0x023BF49E\n"
    ".thumb_func\n.thumb_set OverworldWalk_SkidTiles, 0x023BF4D6\n"
    ".thumb_func\n.thumb_set OverworldWalk_SkidTime, 0x023BF4F0\n"
    ".thumb_func\n.thumb_set OverworldWalk_StompApplies, 0x023BF504\n"
    ".thumb_func\n.thumb_set OverworldWalk_IsFortyFiveDegreeTurn, 0x023BF5E2\n"
    ".thumb_func\n.thumb_set OverworldWildSpawns_ResolveWalkPause, 0x023DFFCC\n");

/* Keep this fixed resident overlay inside its stable linker reserve. */
#pragma GCC optimize("no-tree-forwprop,no-tree-dominator-opts")

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
static OverworldWildRuntimeSurfaceBlockCache sOverworldWildSurfaceBlockCache
    __attribute__((section(".overworld_wild_runtime_tail_data"))) = {
    0,
    0xFF,
    OW_WILD_RUNTIME_SURFACE_MODEL_NONE,
};

typedef struct OverworldWildRuntimeMotionPrefix {
    OVERWORLD_WILD_CUSTOM_JUMP_RUNTIME_PREFIX_FIELDS;
} OverworldWildRuntimeMotionPrefix;

void OverworldWildRuntime_PlayStepDirtParticle(LocalMapObject *object);

#define OW_WILD_RUNTIME_MOTION(state) \
    ((OverworldWildRuntimeMotionPrefix *)((state)->movementRuntimeState))
#define OW_WILD_RUNTIME_STAGED_HOP_LEDGE_PENDING 2
#define OW_WILD_RUNTIME_STAGED_CHAIN_HOP_FORWARD_PENDING 4

/* Both motion adapters read the same public context. Keep one forwarding
 * body, leaving the fixed boundary entry room for its argument packet. */
static u32 __attribute__((naked, noinline))
OverworldWildRuntime_GetFieldContext(void)
{
#if defined(__arm__)
    /* Tail-call the fixed resident entry. LR already names our caller, so the
     * callback returns there without a bridge stack frame. */
    __asm__(
        "ldr r3, 1f\n"
        "ldr r3, [r3, #28]\n"
        "bx r3\n"
        ".align 2\n"
        "1: .word 0x023B6B18\n");
#else
    return OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext();
#endif
}

static OverworldMotionDecision __attribute__((optimize(
    "Os", "if-conversion", "if-conversion2")))
OverworldWildRuntime_RequestMotion(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfileData *lane,
    u8 kind,
    u8 visibilityPolicy,
    u8 arcHeightQ4,
    u8 facing,
    u16 duration,
    u8 spinSpeed,
    u8 swayWidth,
    u16 targetSurfaceId)
{
    OverworldWildRuntimeMotionPrefix *runtime;
    OverworldActorMotionRequestCall call;
    OverworldMotionIntent intent;
    OverworldMotionCandidate candidate;

    /* This private entry has one checked engine caller. Its state, lane,
     * slot, and motion kind are valid before the fixed-size adapter runs. */
    runtime = OW_WILD_RUNTIME_MOTION(state);
    intent.version = OVERWORLD_MOTION_MODEL_VERSION;
    intent.kind = kind;
    intent.facing = facing;
    intent.fieldEpoch = OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(
        OverworldWildRuntime_GetFieldContext());
    intent.behaviorFingerprint = 0;
    intent.duration = duration;
    intent.arcHeightQ4 = arcHeightQ4;
    intent.spinSpeed = spinSpeed;
    intent.swayWidth = swayWidth;
    intent.visibilityPolicy = visibilityPolicy;
    intent.pauseFrames = kind == OVERWORLD_MOTION_KIND_REPOSITION
        || kind == OVERWORLD_MOTION_KIND_FLY_IN
        || (kind == OVERWORLD_MOTION_KIND_HOP
            && (state->movementStagedHopPending[slot]
                    == OW_WILD_RUNTIME_STAGED_HOP_LEDGE_PENDING
                || state->movementStagedHopPending[slot]
                    == OW_WILD_RUNTIME_STAGED_CHAIN_HOP_FORWARD_PENDING))
        ? 0
        : kind == OVERWORLD_MOTION_KIND_WALK
            ? OverworldWildSpawns_ResolveWalkPause(lane)
            : lane->hopPause;
    intent.pathAdvancePolicy = kind == OVERWORLD_MOTION_KIND_FLY_IN
        ? OVERWORLD_MOTION_PATH_ADVANCE_NONE
        : OVERWORLD_MOTION_PATH_ADVANCE_AUTHORITY;
    *(u16 *)(void *)&intent.commitPolicy = kind == OVERWORLD_MOTION_KIND_REPOSITION
        ? OVERWORLD_MOTION_COMMIT_NO_CHAIN
        : kind == OVERWORLD_MOTION_KIND_FLY_IN
            ? OVERWORLD_MOTION_COMMIT_PRESENTATION_ONLY
            : OVERWORLD_MOTION_COMMIT_NORMAL;

    candidate.targetX = runtime->movementCustomJumpTargetX[slot];
    candidate.targetY = runtime->movementCustomJumpTargetY[slot];
    candidate.targetBaseY = runtime->movementCustomJumpTargetBaseY[slot];
    candidate.rejectionFlags = 0;
    candidate.direction = state->movementPendingDirections[slot];
    candidate.distance = state->movementPendingDistances[slot];

    call.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    call.size = sizeof(call);
    call.operation = OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST;
    call.actorSlot = (u8)slot;
    call.candidateCount = 1;
    call.startX = runtime->movementCustomJumpStartX[slot];
    call.startY = runtime->movementCustomJumpStartY[slot];
    call.startBaseY = runtime->movementCustomJumpStartBaseY[slot];
    call.intent = &intent;
    call.candidates = &candidate;
    call.plan = NULL;
    call.reserved = 0;
    call.targetSurfaceId = targetSurfaceId;
    if (OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&call)
        != OVERWORLD_ACTOR_RESULT_OK) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    /* Actor Motion returns zero on every rejection, so this also clears an
     * adapter token that did not acquire a new motion. */
    runtime->movementMotionIdentities[slot] = call.motionIdentity;
    return (OverworldMotionDecision)call.decision;
}

/* Private fixed-address bridge for the two engine adapters. The public
 * runtime table no longer exports motion ownership; this bridge only shapes
 * the caller's saved receipt into the Actor Motion boundary call. */
BOOL __attribute__((noinline, optimize("Os", "rename-registers",
    "if-conversion", "if-conversion2"),
    section(".overworld_wild_runtime_acknowledge")))
OverworldWildRuntime_ApplyMotionBoundary(
    int slot,
    u8 acknowledgements,
    u16 appliedThrough,
    OverworldMotionSample *sample,
    u8 *phase,
    u16 motionIdentity)
{
    OverworldActorMotionBoundaryCall call;

    call.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    call.size = sizeof(call);
    call.actorSlot = (u8)slot;
    call.operation = OVERWORLD_ACTOR_MOTION_SERVICE_ENGINE_BOUNDARY;
    call.acknowledgements = acknowledgements;
    call.phase = 0;
    call.reserved = 0;
    call.fieldEpoch = OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(
        OverworldWildRuntime_GetFieldContext());
    call.acknowledgedPathAdvance = appliedThrough;
    call.cancelReason = (u8)appliedThrough;
    call.motionIdentity = motionIdentity;
    call.pendingLastPathAdvance = 0;
    call.decision = 0;
    call.tickFlags = 0;
    call.sample = sample;
    call.walkPolicy = NULL;
    if (OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->boundary(&call)
            != OVERWORLD_ACTOR_RESULT_OK) {
        return FALSE;
    }
    *phase = call.phase;
    return call.decision == OVERWORLD_MOTION_DECISION_ACCEPTED;
}

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

void __attribute__((naked, noinline, used,
        section(".overworld_wild_runtime_landing_particle")))
OverworldWildRuntime_PlayLandingHopParticle(LocalMapObject *object)
{
    /* Callers own a live movement object. Tail-call the normal-ground
     * landing branch used by sub_02060114. */
    __asm__(
        "ldr r3, 1f\n"
        "bx r3\n"
        ".align 2\n"
        "1: .word ov01_021FF74C\n");
}

BOOL __attribute__((noinline, optimize("Os", "expensive-optimizations", "tree-dominator-opts",
    "tree-pre", "tree-copy-prop")))
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
    u8 anchorBlockOffsets;
    u8 heightPage;
    u8 localX;
    u8 localY;
    u8 modelIndex;
    u8 surfaceType;
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
    localX = (u8)x & OW_WILD_MAP_BLOCK_MASK;
    localY = (u8)y & OW_WILD_MAP_BLOCK_MASK;
    model = &catalog->models[modelIndex];
    instance = OVERWORLD_WILD_SURFACE_SERVICE_ENTRY->query(
        &catalog->instances[model->firstInstance],
        catalog->templates,
        model->instanceCount,
        localX | ((u32)localY << OW_WILD_MAP_BLOCK_SHIFT));
    if (instance == NULL) {
        return FALSE;
    }
    surfaceType = instance->heightPageAndSurfaceType >> 5;
    heightPage = instance->heightPageAndSurfaceType & 0x1F;
    anchorBlockOffsets = instance->anchorBlockOffsets;
    template = &catalog->templates[instance->templateId];
    anchorBlockIndex = blockIndex
        + ((s8)(anchorBlockOffsets << 4) >> 4)
        + ((s8)anchorBlockOffsets >> 4) * matrix[0];
    if (heightPage == OW_WILD_SURFACE_HEIGHT_PAGE_NATIVE_GROUND) {
        hit->height = instance->heightQ4 << OW_WILD_ROOF_HEIGHT_QUANTUM_SHIFT;
        hit->surfaceId = OW_WILD_SURFACE_ID_NATIVE_GROUND
            - (surfaceType >> 2);
    } else {
        hit->height = (heightPage << 20)
            + (instance->heightQ4 << OW_WILD_ROOF_HEIGHT_QUANTUM_SHIFT)
            + (matrix[OW_WILD_MAP_MATRIX_ALTITUDES_OFFSET + anchorBlockIndex]
                << OW_WILD_MAP_ALTITUDE_HEIGHT_SHIFT);
        hit->surfaceId = (u16)((anchorBlockIndex << OW_WILD_SURFACE_ID_BLOCK_SHIFT)
            | instance->localSurfaceId);
    }
    hit->surfaceType = surfaceType;
    hit->nodeId = (u8)((localY - instance->minY) * template->width
        + localX - instance->minX);
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

    hit.height = 0;

    if (OverworldWildRuntime_QuerySurface(
            fieldSystem,
            catalog,
            x,
            y,
            &hit)
        && (u16)(hit.surfaceId + 2) > 1) {
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
        return targetPosition.y + hit.height;
    }
    return (s32)object->posVec[1];
}

static void __attribute__((noinline,
    optimize("Os", "if-conversion", "if-conversion2",
        "no-tree-forwprop")))
OverworldWildRuntime_FillActorView(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    OverworldActorStateSnapshot *view)
{
    OverworldWildSpawn *spawn = &state->spawns[slot];
    LocalMapObject *object = spawn->object;
    BOOL mounted;

    view->version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    view->size = sizeof(*view);
    view->handle.slot = (u16)slot;
    view->active = spawn->active;
    if (!view->active) {
        return;
    }
    mounted = slot == OW_WILD_FOLLOWER_SLOT
        && (OVERWORLD_MOUNT_OVERLAY_ENTRY->isActive()
            & OVERWORLD_MOUNT_ACTIVE_FLAG);
    view->handle.mapGeneration = state->mapGeneration;
    view->handle.encounterGeneration = spawn->encounterGeneration;
    view->subjectIdentity = spawn->personality;
    view->species = spawn->species;
    view->form = spawn->form;
    view->level = spawn->level;
    view->role = mounted
        ? OVERWORLD_ACTOR_ROLE_MOUNTED
        : slot == OW_WILD_FOLLOWER_SLOT
            ? OVERWORLD_ACTOR_ROLE_FOLLOWER
            : OVERWORLD_ACTOR_ROLE_WILD;
    view->controllerState = mounted
        ? OW_WILD_SPAWNER_SPOT_STATE_CHILL
        : state->movementSpotStates[slot];
    /* Emoting is presentation over the Owner lane. Reserved and unknown
     * controller values must not invent a resolved lane. */
    view->lane = view->controllerState == OW_WILD_SPAWNER_SPOT_STATE_TIRED
        ? BEHAVIOR_RESOLUTION_LANE_TIRED
        : view->controllerState == OW_WILD_SPAWNER_SPOT_STATE_CHILL
            || view->controllerState == OW_WILD_SPAWNER_SPOT_STATE_EMOTING
        ? BEHAVIOR_RESOLUTION_LANE_OWNER
        : BEHAVIOR_RESOLUTION_LANE_NONE;
    view->presentationState = 0;
    if (object != NULL
        && (object->flags & BIT_VANISH) == 0
        && GetMapObjectByID(fieldSystem->mapObjectMan, spawn->objectId)
            == object) {
        view->presentationState = OVERWORLD_ACTOR_PRESENTATION_READY;
    }
    view->presentationAttached = view->presentationState
        == OVERWORLD_ACTOR_PRESENTATION_READY;
    view->inputOwnership = mounted;
    if (mounted && fieldSystem->playerAvatar != NULL) {
        object = fieldSystem->playerAvatar->mapObject;
    }
    if (object == NULL) {
        return;
    }
    if (view->motionPhase != OVERWORLD_MOTION_PHASE_IDLE
        && view->motionPhase != OVERWORLD_MOTION_PHASE_CANCELED) {
        /* The actor-owned snapshot already contains the logical tile. */
    } else {
        view->logicalX = (s16)object->xCurr;
        view->logicalY = (s16)object->yCurr;
    }
    view->renderX = (s16)((s32)object->posVec[0] >> 16);
    view->renderY = (s16)((s32)object->posVec[2] >> 16);
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldWildRuntime_BindActor(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    OverworldActorHandle *handle)
{
    OverworldActorStateSnapshot view;

    memset(&view, 0, sizeof(view));
    OverworldWildRuntime_FillActorView(fieldSystem, state, slot, &view);
    return OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->bind(&view, handle)
        == OVERWORLD_ACTOR_RESULT_OK;
}

static void OverworldActorWalkPolicy_ResetState(
    OverworldActorPolicyState *policy,
    BOOL initialize,
    u8 baseSpeed,
    u8 laneState)
{
    typedef u32 WalkMomentumWord __attribute__((may_alias));
    WalkMomentumWord *words = (WalkMomentumWord *)&policy->walkMomentum;

    /* This resident owner is size-bound. Reset the packed byte state with two
     * aligned words instead of linking the larger byte-wise memset sequence. */
    words[0] = OW_WILD_WALK_DIRECTION_NONE;
    words[1] = OW_WILD_WALK_DIRECTION_NONE;
    if (initialize) {
        words[0] |= (u32)baseSpeed << 16 | (u32)baseSpeed << 24;
        words[1] = laneState;
    }
    policy->bufferedDirection = OW_WILD_WALK_DIRECTION_NONE;
    policy->stopPending = FALSE;
    policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_NONE;
    policy->pendingSkid = FALSE;
    policy->lastWalkTime = 0;
    policy->chainStepsRemaining = 0;
    policy->deferredChainPauseTicks = 0;
    policy->deferredChainPauseAction = 0;
}

static void OverworldActorWalkPolicy_ReduceInput(
    OverworldActorPolicyState *policy,
    OverworldActorWalkPolicyCall *call)
{
    OverworldWildWalkMomentumState *state = &policy->walkMomentum;
    u8 requestedDirection = call->direction;
    u8 baseSpeed = OverworldWalk_ClampTime(
        call->lane->chillSpeed);
    u8 visibleSpeed;
    u8 skidTiles;
    u8 turnSpeed;

    if ((requestedDirection < 4
            && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(
                call->lane->hopAllowNonCardinal))
        || (requestedDirection >= 4
            && requestedDirection != OW_WILD_WALK_DIRECTION_NONE
            && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
                call->lane->hopAllowNonCardinal))) {
        /* A rejected candidate is not a stop request. In particular, Wild
         * direction search must not clear an unfinished movement chain. */
        return;
    }
    if (state->speed == 0 || state->baseSpeed != baseSpeed
        || state->spotState != call->laneState) {
        OverworldActorWalkPolicy_ResetState(
            policy, TRUE, baseSpeed, call->laneState);
        call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION;
    }
    if (policy->bufferedDirection != OW_WILD_WALK_DIRECTION_NONE
        && policy->bufferedDirection != state->direction) {
        requestedDirection = policy->bufferedDirection;
    }
    if (state->skidRemaining != 0) {
        call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
        return;
    }
    /* Walk variance may leave the displayed tile behind nominal momentum.
     * A turn or stop must brake from the speed the player just saw. */
    visibleSpeed = policy->lastWalkTime != 0
        ? policy->lastWalkTime : state->speed;
    if (requestedDirection == OW_WILD_WALK_DIRECTION_NONE) {
        skidTiles = OverworldWalk_SkidTiles(visibleSpeed);
        if (state->direction != OW_WILD_WALK_DIRECTION_NONE && skidTiles != 0) {
            if ((call->flags & OVERWORLD_ACTOR_WALK_POLICY_FLAG_DEFER_STOP) != 0
                && !policy->stopPending) {
                policy->stopPending = TRUE;
                call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
                return;
            }
            policy->stopPending = FALSE;
            OverworldWalk_ProposeStep(
                policy, call, state->direction, state->direction,
                OverworldWalk_SkidTime(visibleSpeed),
                OVERWORLD_ACTOR_WALK_STEP_VALIDATE
                    | OVERWORLD_ACTOR_WALK_STEP_SKID
                    | OVERWORLD_ACTOR_WALK_STEP_STOP_SKID,
                skidTiles);
            return;
        }
        OverworldActorWalkPolicy_ResetState(
            policy, TRUE, baseSpeed, call->laneState);
        call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION;
        return;
    }
    policy->stopPending = FALSE;
    if (state->direction == OW_WILD_WALK_DIRECTION_NONE
        || requestedDirection == state->direction) {
        OverworldWalk_ProposeStep(
            policy, call, requestedDirection, requestedDirection,
            state->speed, call->stepFlags, 0);
        return;
    }
    if (!OW_WILD_BEHAVIOR_WALK_ALLOWS_TURNING(call->lane->walkOptions)) {
        call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
        call->stepDirection = state->direction;
        policy->bufferedDirection = OW_WILD_WALK_DIRECTION_NONE;
        return;
    }
    skidTiles = OverworldWalk_IsFortyFiveDegreeTurn(
            state->direction, requestedDirection)
        ? 0
        : OverworldWalk_SkidTiles(visibleSpeed);
    turnSpeed = OverworldWalk_DecelerateTime(
        visibleSpeed, state->baseSpeed, call->lane->walkAccelerationStep);
    if (skidTiles != 0
        && (call->flags
            & OVERWORLD_ACTOR_WALK_POLICY_FLAG_SUPPRESS_TURN_SKID) == 0
        && OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID(
            call->lane->tilesBeforeTurnSkid) != 0
        && state->turnDirection >= OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID(
            call->lane->tilesBeforeTurnSkid)) {
        OverworldWalk_ProposeStep(
            policy, call, state->direction, requestedDirection,
            OverworldWalk_SkidTime(visibleSpeed),
            OVERWORLD_ACTOR_WALK_STEP_VALIDATE
                | OVERWORLD_ACTOR_WALK_STEP_SKID,
            skidTiles);
        call->reserved[0] = turnSpeed;
        return;
    }
    OverworldWalk_ProposeStep(
        policy, call, requestedDirection, requestedDirection,
        turnSpeed,
        OVERWORLD_ACTOR_WALK_STEP_VALIDATE
            | OVERWORLD_ACTOR_WALK_STEP_RESET_ACCELERATION,
        0);
    /* A rejected turn must not change momentum. Commit the slower nominal
     * time only after the engine accepts this proposal. */
    call->reserved[0] = turnSpeed;
}

static void OverworldActorWalkPolicy_ReduceStartResult(
    OverworldActorPolicyState *policy,
    OverworldActorWalkPolicyCall *call)
{
    OverworldWildWalkMomentumState *state = &policy->walkMomentum;

    if (policy->pendingStep != OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL) {
        return;
    }
    if (call->startResult != OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED) {
        BOOL stopSkid = (call->stepFlags
                & OVERWORLD_ACTOR_WALK_STEP_STOP_SKID) != 0
            || ((call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_SKID) != 0
                && state->turnDirection == OW_WILD_WALK_DIRECTION_NONE);
        u8 deferredAction = policy->deferredChainPauseAction;
        u8 deferredTicks = policy->deferredChainPauseTicks;

        policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_NONE;
        if ((call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_SKID) != 0) {
            call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
            /* A blocked planned turn skid brakes without a wall crash. */
            call->effect = stopSkid
                    || (call->stepFlags
                        & OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH) != 0
                ? OVERWORLD_ACTOR_WORLD_EFFECT_NONE
                : OVERWORLD_ACTOR_WORLD_EFFECT_CRASH;
            OverworldActorWalkPolicy_ResetState(
                policy, TRUE,
                OverworldWalk_ClampTime(call->lane->chillSpeed),
                call->laneState);
            if (stopSkid && (deferredAction & 0x80) != 0) {
                policy->deferredChainPauseAction = deferredAction;
                policy->deferredChainPauseTicks = deferredTicks;
            }
            call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION;
        } else {
            state->direction = OverworldWalkDirectionPolicy_ApplyStartResult(
                state->direction, call->stepDirection, FALSE);
            if ((call->flags
                    & OVERWORLD_ACTOR_WALK_POLICY_FLAG_CRASH_ON_BLOCKED) != 0) {
                call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
                call->effect = OVERWORLD_ACTOR_WORLD_EFFECT_CRASH;
            }
        }
        return;
    }
    policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED;
    if ((call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_SKID) != 0) {
        policy->lastWalkTime = 0;
        state->speed = OverworldWalk_ClampTime(call->travelTime);
        if ((call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_CONTINUATION) == 0) {
            state->skidRemaining = call->distance;
            state->turnDirection =
                (call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_STOP_SKID) != 0
                    ? OW_WILD_WALK_DIRECTION_NONE
                    : call->facingDirection;
            state->resumeSpeed =
                (call->stepFlags
                    & OVERWORLD_ACTOR_WALK_STEP_STOP_SKID) != 0
                    ? state->baseSpeed
                    : call->reserved[0];
        }
        policy->pendingSkid = TRUE;
        state->direction = OverworldWalkDirectionPolicy_ApplyStartResult(
            state->direction, call->stepDirection, TRUE);
    } else {
        /* ProposeStep stores nominal momentum before the Actor wrapper adds
         * per-tile presentation variance to travelTime. */
        state->speed = call->reserved[0];
        policy->lastWalkTime = call->travelTime;
        if ((call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_RESET_ACCELERATION) != 0) {
            state->tileCounter = 0;
            state->turnDirection = 0;
        }
        state->direction = call->stepDirection;
        policy->pendingSkid = FALSE;
        state->resumeSpeed =
            (call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_POST_SKID) != 0
                ? state->speed
                : 0;
    }
    call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
}

static void OverworldActorWalkPolicy_ReduceCommit(
    OverworldActorPolicyState *policy,
    OverworldActorWalkPolicyCall *call)
{
    OverworldWildWalkMomentumState *state = &policy->walkMomentum;
    u8 turnDirection;
    u8 baseSpeed;
    u8 fastestTime;
    BOOL wasSkidding = policy->pendingSkid;

    if (policy->pendingStep != OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED) {
        return;
    }
    policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_NONE;
    baseSpeed = OverworldWalk_ClampTime(call->lane->chillSpeed);
    if ((call->flags & OVERWORLD_ACTOR_WALK_POLICY_FLAG_WALK_ACCEPTED) == 0
        || state->speed == 0 || state->baseSpeed != baseSpeed
        || state->spotState != call->laneState) {
        OverworldActorWalkPolicy_ResetState(policy, FALSE, 0, 0);
        call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION;
        call->decision = wasSkidding
            ? OVERWORLD_ACTOR_WALK_POLICY_CONSUMED
            : OVERWORLD_ACTOR_WALK_POLICY_IGNORED;
        return;
    }
    fastestTime = OverworldWalk_ClampTime(
        call->lane->maxWalkSpeed);
    if (fastestTime > baseSpeed) {
        fastestTime = baseSpeed;
    }
    if (state->resumeSpeed != 0 && state->resumeSpeed < fastestTime) {
        state->resumeSpeed = fastestTime;
    }
    if (!wasSkidding && state->speed < fastestTime) {
        state->speed = fastestTime;
        state->tileCounter = 0;
    }
    call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
    if (wasSkidding) {
        call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_SKID;
        turnDirection = state->turnDirection;
        if (state->skidRemaining == 1) {
            call->effect = OVERWORLD_ACTOR_WORLD_EFFECT_SKID_DUST;
            call->facingDirection = turnDirection;
        }
        policy->pendingSkid = FALSE;
        if (state->skidRemaining != 0) {
            state->skidRemaining--;
        }
        if (state->skidRemaining != 0) {
            OverworldWalk_ProposeStep(
                policy, call, state->direction,
                turnDirection == OW_WILD_WALK_DIRECTION_NONE
                    ? state->direction : turnDirection,
                state->speed,
                OVERWORLD_ACTOR_WALK_STEP_VALIDATE
                    | OVERWORLD_ACTOR_WALK_STEP_SKID
                    | OVERWORLD_ACTOR_WALK_STEP_CONTINUATION,
                state->skidRemaining);
            return;
        }
        if (turnDirection == OW_WILD_WALK_DIRECTION_NONE) {
            OverworldActorWalkPolicy_ResetState(
                policy, TRUE,
                OverworldWalk_ClampTime(call->lane->chillSpeed),
                call->laneState);
            call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION;
            return;
        }
        state->speed = state->resumeSpeed;
        state->resumeSpeed = 0;
        state->direction = turnDirection;
        state->turnDirection = 0;
        state->tileCounter = 0;
        OverworldWalk_ProposeStep(
            policy, call, turnDirection, turnDirection, state->speed,
            OVERWORLD_ACTOR_WALK_STEP_VALIDATE
                | OVERWORLD_ACTOR_WALK_STEP_POST_SKID
                | OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION,
            0);
        return;
    }
    if (call->distance != 1 || call->direction != state->direction) {
        return;
    }
    if (OverworldWalk_StompApplies(
            state->speed, call->lane->walkStompTime)) {
        call->effect = OVERWORLD_ACTOR_WORLD_EFFECT_STOMP;
    }
    if (call->lane->walkPause != 0) {
        state->turnDirection = 0;
    } else if (state->turnDirection != 0xFE) {
        state->turnDirection++;
    }
    if (state->resumeSpeed != 0) {
        state->resumeSpeed = 0;
    } else if (!OW_WILD_BEHAVIOR_WALK_DISABLES_ACCELERATION(
            call->lane->walkOptions)
        && call->lane->tilesToAccelerate != 0) {
        /* At the cap this counts completed cap-speed Walks. The event that
         * first reaches the cap resets it, keeping full variance there. */
        if (state->tileCounter != 0xFF) {
            state->tileCounter++;
        }
        if (state->speed > fastestTime
            && state->tileCounter >= call->lane->tilesToAccelerate) {
            state->tileCounter = 0;
            state->speed = OverworldWalk_AccelerateTime(
                state->speed, fastestTime,
                call->lane->walkAccelerationStep);
        }
    }
}

static BOOL OverworldActorWalkPolicy_PublishEffect(
    OverworldActorStateSnapshot *actor,
    u32 effect,
    u32 sequence);

static u8 __attribute__((optimize("Os")))
OverworldActorWalkPolicy_SelectChainPauseAction(u8 actionMask)
{
    u8 action;

    /* The private caller receives a nonempty mask from the normalized lane. */
    do {
        action = (u8)(gf_rand() & 7u);
    } while ((actionMask & (1u << action)) == 0);
    return action + 1u;
}

static void __attribute__((optimize("Os")))
OverworldActorWalkPolicy_ReduceChain(
    OverworldActorPolicyState *policy,
    OverworldActorStateSnapshot *actor,
    OverworldActorWalkPolicyCall *call)
{
    u8 encodedPauseAction = call->lane->chainPauseAction;
    u8 pauseAction;
    u8 pauseTicks;
    u32 pauseFrames;

    if (policy->pendingStep != OVERWORLD_ACTOR_WALK_PENDING_CHAIN) {
        return;
    }
    policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_NONE;
    if ((call->flags & OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED) == 0
        || (call->locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WALK
            && !OW_WILD_BEHAVIOR_WALK_ALLOWS_TURNING(call->lane->walkOptions))
        || call->lane->ramAccelerationSteps == 0
        || !((call->locomotion >= OW_WILD_BEHAVIOR_LOCOMOTION_WALK
                && call->locomotion <= OW_WILD_BEHAVIOR_LOCOMOTION_HOP)
            || call->locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT)) {
        policy->chainStepsRemaining = 0;
        policy->deferredChainPauseAction = 0;
        return;
    }
    if (policy->chainStepsRemaining == 0) {
        policy->chainStepsRemaining = call->lane->ramAccelerationSteps;
        if (call->lane->chainMovementVariance != 0) {
            policy->variancePhase = (u8)(policy->variancePhase * 73u + 41u);
            policy->chainStepsRemaining += (u8)(((u16)policy->variancePhase
                * (call->lane->chainMovementVariance + 1u)) >> 8);
        }
    }
    if (--policy->chainStepsRemaining != 0) {
        return;
    }
    if (encodedPauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE) {
        return;
    }
    if (call->lane->chainPauseActionChance != 0
        && gf_rand() % 100u >= call->lane->chainPauseActionChance) {
        return;
    }
    pauseAction = (encodedPauseAction
            & OW_WILD_BEHAVIOR_CHAIN_PAUSE_RANDOM_CHOICE) != 0
        ? OverworldActorWalkPolicy_SelectChainPauseAction(
            encodedPauseAction & OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_MASK)
        : encodedPauseAction;
    if (pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE
        || pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD) {
        pauseTicks = 0;
    } else if ((u8)(pauseAction
            - OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_STEPS)
        <= (OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS
            - OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_STEPS)) {
        pauseTicks = call->lane->chainRepositionSpeed;
    } else {
        pauseFrames = call->lane->ramMaxSpeed;
        if (pauseFrames == 0
            && pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND) {
            pauseFrames = 60;
        }
        policy->variancePhase = (u8)(policy->variancePhase * 73u + 41u);
        pauseFrames += (u8)(((u16)policy->variancePhase
            * (call->lane->chainPauseVariance + 1u)) >> 8);
        pauseTicks = (u8)((pauseFrames + 1u) / 2u);
        if (pauseAction
            == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS) {
            pauseTicks /= call->lane->chainRepositionJumpCount;
            if (pauseTicks == 0) {
                pauseTicks = 1;
            }
            pauseTicks += pauseTicks;
        }
    }
    call->chainAction = pauseAction;
    call->chainTicks = pauseTicks;
    policy->deferredChainPauseTicks = pauseTicks;
    policy->deferredChainPauseAction = pauseAction | 0x80;
    /* PAUSE records the passive chain boundary but starts no presentation
     * effect. The Wild adapter only consumes its pause clock. */
    (void)OverworldActorWalkPolicy_PublishEffect(
        actor, actor->commitSequence, pauseAction);
    call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldActorWalkPolicy_PublishEffect(
    OverworldActorStateSnapshot *actor,
    u32 effect,
    u32 sequence)
{
    return OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->recordTrace(
        &actor->handle,
        OVERWORLD_ACTOR_EVENT_WORLD_EFFECT,
        OVERWORLD_ACTOR_REASON_OK,
        effect,
        sequence) == OVERWORLD_ACTOR_RESULT_OK;
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldActorWalkPolicy_ApplyCommand(
    OverworldActorPolicyState *policy,
    OverworldActorStateSnapshot *actor,
    OverworldActorWalkPolicyCall *call)
{
    switch (call->operation) {
    case OVERWORLD_ACTOR_WALK_POLICY_INSPECT:
        if (call->policyView == NULL) {
            return FALSE;
        }
        memcpy(call->policyView, policy, 30);
        call->policyView->actorActive = actor->active;
        call->policyView->motionPhase = actor->motionPhase;
        break;
    case OVERWORLD_ACTOR_WALK_POLICY_SWAP_PROFILE: {
        OverworldActorPolicyProfileTransaction *transaction =
            call->profileTransaction;

        transaction->prior.behaviorFingerprint =
            policy->behaviorFingerprint;
        transaction->prior.matchedLayerMask = policy->matchedLayerMask;
        call->profileBinding = &transaction->next;
        /* The swap and ordinary bind share the same identity commit. */
    }
        /* fall through */
    case OVERWORLD_ACTOR_WALK_POLICY_BIND_PROFILE:
        if (call->profileBinding == NULL) {
            return FALSE;
        }
        policy->behaviorFingerprint =
            call->profileBinding->behaviorFingerprint;
        policy->matchedLayerMask = call->profileBinding->matchedLayerMask;
        actor->behaviorFingerprint = policy->behaviorFingerprint;
        actor->matchedLayerMask = policy->matchedLayerMask;
        break;
    case OVERWORLD_ACTOR_WALK_POLICY_SAMPLE_VARIANCE:
        policy->variancePhase = (u8)(policy->variancePhase * 73u + 41u);
        call->chainTicks = (u8)(((u16)policy->variancePhase
            * (call->distance + 1u)) >> 8);
        break;
    case OVERWORLD_ACTOR_WALK_POLICY_BUFFER_DIRECTION:
        policy->bufferedDirection = call->direction;
        break;
    case OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING:
        if ((policy->deferredChainPauseAction & 0x80) != 0) {
            call->chainAction = policy->deferredChainPauseAction & 0x7F;
            call->chainTicks = policy->deferredChainPauseTicks;
            policy->deferredChainPauseAction = 0;
            policy->walkMomentum.turnDirection = 0;
            call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
        }
        break;
    case OVERWORLD_ACTOR_WALK_POLICY_CHAIN_PUT_PENDING:
        if (call->chainAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE
            || call->chainAction > OVERWORLD_ROLE_CONTROLLER_CHAIN_ACTION_MAX) {
            return FALSE;
        }
        policy->deferredChainPauseTicks = call->chainTicks;
        policy->deferredChainPauseAction = call->chainAction | 0x80;
        call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
        break;
    case OVERWORLD_ACTOR_WALK_POLICY_PUBLISH_EFFECT:
        if ((u8)(call->effect - 1)
            >= OVERWORLD_ACTOR_WORLD_EFFECT_CRASH) {
            return FALSE;
        }
        call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
        return OverworldActorWalkPolicy_PublishEffect(
            actor, call->effect, 1);
    case OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_BEGIN:
        policy->chainStepsRemaining = call->distance;
        policy->deferredChainPauseAction = call->direction;
        break;
    case OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_ADVANCE:
        policy->chainStepsRemaining = call->distance;
        policy->deferredChainPauseAction += (s8)call->direction;
        break;
    case OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH:
        policy->chainStepsRemaining = 0;
        policy->deferredChainPauseAction = 0;
        break;
    default:
        return FALSE;
    }
    return TRUE;
}

BOOL __attribute__((optimize("Os")))
OverworldActorWalkPolicy_Reduce(
    OverworldActorPolicyState *policy,
    OverworldActorStateSnapshot *actor,
    OverworldActorWalkPolicyCall *call)
{
    if (policy == NULL || actor == NULL || call == NULL
        || call->version != OVERWORLD_ACTOR_WALK_POLICY_VERSION
        || call->size != sizeof(*call)
        || call->actorSlot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS) {
        return FALSE;
    }
    if (call->operation > OVERWORLD_ACTOR_WALK_POLICY_CHAIN_COMMIT) {
        return OverworldActorWalkPolicy_ApplyCommand(policy, actor, call);
    }
    if (call->operation != OVERWORLD_ACTOR_WALK_POLICY_RESET
        && call->lane == NULL) {
        return FALSE;
    }
    call->decision = OVERWORLD_ACTOR_WALK_POLICY_IGNORED;
    call->effect = OVERWORLD_ACTOR_WORLD_EFFECT_NONE;
    call->chainAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE;
    if (call->operation == OVERWORLD_ACTOR_WALK_POLICY_RESET) {
        OverworldActorWalkPolicy_ResetState(policy, FALSE, 0, 0);
    } else if (call->operation == OVERWORLD_ACTOR_WALK_POLICY_INPUT) {
        OverworldActorWalkPolicy_ReduceInput(policy, call);
    } else if (call->operation == OVERWORLD_ACTOR_WALK_POLICY_START_RESULT) {
        OverworldActorWalkPolicy_ReduceStartResult(policy, call);
    } else if (call->operation == OVERWORLD_ACTOR_WALK_POLICY_COMMIT) {
        OverworldActorWalkPolicy_ReduceCommit(policy, call);
    } else if (call->operation == OVERWORLD_ACTOR_WALK_POLICY_CHAIN_COMMIT) {
        OverworldActorWalkPolicy_ReduceChain(policy, actor, call);
    } else {
        return FALSE;
    }
    return TRUE;
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
        OverworldWildRuntime_FillActorView,
        0,
        OverworldWildRuntime_RequestMotion,
        OverworldRoleController_Reduce,
        0,
        OverworldWildRuntime_BindActor,
        OverworldWildRuntime_PlayStepDirtParticle,
        OverworldWildRuntime_PlayLandingHopParticle,
};

const OverworldActorWalkPolicyOwnerEntry gOverworldActorWalkPolicyOwnerEntry
    __attribute__((section(".overworld_actor_walk_policy_owner"), used)) = {
        OVERWORLD_ACTOR_WALK_POLICY_OWNER_MAGIC,
        OVERWORLD_ACTOR_WALK_POLICY_OWNER_VERSION,
        sizeof(OverworldActorWalkPolicyOwnerEntry),
        OverworldActorWalkPolicy_Reduce,
};

static BOOL __attribute__((section(".overworld_wild_runtime_acknowledge_tail"), used))
OverworldWildRuntime_ValidateImpl(void)
{
    const OverworldWildRuntimeOverlayEntry *entry =
        &gOverworldWildRuntimeOverlayEntry;
    const OverworldActorWalkPolicyOwnerEntry *walkOwner =
        &gOverworldActorWalkPolicyOwnerEntry;

    return entry->magic == OVERWORLD_WILD_RUNTIME_MAGIC
        && entry->version == OVERWORLD_WILD_RUNTIME_VERSION
        && entry->size == sizeof(*entry)
        && entry->validate != NULL
        && entry->querySurface != NULL
        && entry->getGroundBaseY != NULL
        && entry->fillActorView != NULL
        && entry->reservedPopulationControl == 0
        && entry->requestMotion != NULL
        && entry->reduceRole == OverworldRoleController_Reduce
        && entry->reservedAcknowledgeMotion == 0
        && entry->bindActor != NULL
        && entry->playStepDirtParticle != NULL
        && entry->playLandingHopParticle != NULL
        && walkOwner->magic == OVERWORLD_ACTOR_WALK_POLICY_OWNER_MAGIC
        && walkOwner->version == OVERWORLD_ACTOR_WALK_POLICY_OWNER_VERSION
        && walkOwner->size == sizeof(*walkOwner)
        && walkOwner->reduceWalk == OverworldActorWalkPolicy_Reduce;
}
