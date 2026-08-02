#ifndef OVERWORLD_WILD_RUNTIME_SIDECARS_H
#define OVERWORLD_WILD_RUNTIME_SIDECARS_H

#include "../../include/overworld_wild_spawns_internal.h"

#define OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT 8
#define OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS 16
#define OW_WILD_RUNTIME_MAX_CATALOG_DEFINITIONS 32
#define OW_WILD_RUNTIME_MAX_BOUND_NODES 8

#define OW_WILD_RUNTIME_DEFINITION_FLAG_RUNTIME_ELIGIBLE (1u << 0)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN (1u << 1)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER (1u << 2)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS (1u << 3)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES (1u << 4)

#define OW_WILD_RUNTIME_GENERATED_FLAG_HAS_TIRED_ORIGIN (1u << 0)
#define OW_WILD_RUNTIME_GENERATED_FLAG_HAS_REQUIRED_OWNER (1u << 1)

typedef enum OverworldWildRuntimeStatus {
    OW_WILD_RUNTIME_STATUS_OK = 0,
    OW_WILD_RUNTIME_STATUS_IDEMPOTENT = 1,
    OW_WILD_RUNTIME_STATUS_STALE_NOOP = 2,
    OW_WILD_RUNTIME_STATUS_STALE_HANDLE = 3,
    OW_WILD_RUNTIME_STATUS_INVALID_HANDLE = 4,
    OW_WILD_RUNTIME_STATUS_WRONG_SLOT = 5,
    OW_WILD_RUNTIME_STATUS_SLOT_GENERATION_MISMATCH = 6,
    OW_WILD_RUNTIME_STATUS_INVALID_DEFINITION = 7,
    OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER = 8,
    OW_WILD_RUNTIME_STATUS_OWNER_NOT_AUTHORIZED = 9,
    OW_WILD_RUNTIME_STATUS_GENERATED_WRAPPER_FAMILY_MISMATCH = 10,
    OW_WILD_RUNTIME_STATUS_OWNER_KEY_OCCUPIED = 11,
    OW_WILD_RUNTIME_STATUS_DEFINITION_OWNED = 12,
    OW_WILD_RUNTIME_STATUS_INSTANCE_KEY_NOT_ALLOWED = 13,
    OW_WILD_RUNTIME_STATUS_NOT_FOUND = 14,
    OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE = 15,
    OW_WILD_RUNTIME_STATUS_AMBIGUOUS_SELECTOR = 16,
    OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA = 17,
    OW_WILD_RUNTIME_STATUS_CAPACITY_EXCEEDED = 18,
    OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER = 19,
    OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION = 20,
    OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA = 21,
    OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION = 22,
    OW_WILD_RUNTIME_STATUS_INACTIVE_SLOT = 23,
    OW_WILD_RUNTIME_STATUS_RUNTIME_EPOCH_RESTARTED = 24,
    OW_WILD_RUNTIME_STATUS_DATA_BUSY = 25,
} OverworldWildRuntimeStatus;

typedef enum OverworldWildRuntimeDeltaOperationKind {
    OW_WILD_RUNTIME_DELTA_APPLY = 1,
    OW_WILD_RUNTIME_DELTA_REPLACE = 2,
    OW_WILD_RUNTIME_DELTA_REMOVE_REQUIRED = 3,
    OW_WILD_RUNTIME_DELTA_REMOVE_IF_PRESENT = 4,
    OW_WILD_RUNTIME_DELTA_REMOVE_OWNER_IF_PRESENT = 5,
    OW_WILD_RUNTIME_DELTA_REMOVE_POLICY = 6,
    OW_WILD_RUNTIME_DELTA_CLEAR = 7,
} OverworldWildRuntimeDeltaOperationKind;

typedef struct OverworldWildRuntimeLayerHandle {
    u32 runtimeEpoch;
    u32 slotGeneration;
    u32 entryGeneration;
    u32 validityTag;
    u16 ownerId;
    u16 instanceKey;
    u8 slotIndex;
    u8 reserved[3];
} OverworldWildRuntimeLayerHandle;

typedef union OverworldWildRuntimeDeltaOperationPayload {
    struct {
        u16 definitionId;
        u16 ownerId;
        u16 instanceKey;
        u8 reserved[18];
    } apply;
    OverworldWildRuntimeLayerHandle handle;
    struct {
        u16 ownerId;
        u8 reserved[22];
    } owner;
    struct {
        u8 mapLifetime;
        u8 reserved[23];
    } policy;
    u8 raw[24];
} OverworldWildRuntimeDeltaOperationPayload;

typedef struct OverworldWildRuntimeDeltaOperation {
    u16 operationId;
    u8 kind;
    u8 reserved;
    OverworldWildRuntimeDeltaOperationPayload payload;
} OverworldWildRuntimeDeltaOperation;

typedef struct OverworldWildRuntimeApplicabilityInput {
    u32 immutableContextMask;
    u16 controllerId;
    u16 boundNodeIds[OW_WILD_RUNTIME_MAX_BOUND_NODES];
    u8 boundNodeCount;
    u8 semanticRoleMask;
    u16 effectiveProfileId;
    u8 effectiveSemanticRole;
    u8 reserved;
} OverworldWildRuntimeApplicabilityInput;

typedef struct OverworldWildRuntimeStackDeltaRequest {
    u32 expectedSlotGeneration;
    u8 slotIndex;
    u8 operationCount;
    u16 reserved;
    OverworldWildRuntimeApplicabilityInput applicability;
    OverworldWildRuntimeDeltaOperation
        operations[OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS];
} OverworldWildRuntimeStackDeltaRequest;

typedef struct OverworldWildRuntimeDeltaOperationResult {
    u16 operationId;
    u8 status;
    u8 matched;
    OverworldWildRuntimeLayerHandle handle;
} OverworldWildRuntimeDeltaOperationResult;

typedef struct OverworldWildRuntimeStackDeltaResult {
    u32 runtimeEpochBefore;
    u32 runtimeEpochAfter;
    u32 slotGenerationBefore;
    u32 slotGenerationAfter;
    u32 layerGenerationBefore;
    u32 layerGenerationAfter;
    u32 effectiveGenerationBefore;
    u32 effectiveGenerationAfter;
    u8 status;
    u8 ok;
    u8 mutated;
    u8 operationResultCount;
    OverworldWildRuntimeDeltaOperationResult
        operationResults[OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS];
} OverworldWildRuntimeStackDeltaResult;

typedef enum OverworldWildRuntimeLifetimeState {
    OW_WILD_RUNTIME_LIFETIME_UNINITIALIZED = 0,
    OW_WILD_RUNTIME_LIFETIME_ACTIVE,
    OW_WILD_RUNTIME_LIFETIME_RESIDENT_COLD,
} OverworldWildRuntimeLifetimeState;

typedef enum OverworldWildRuntimeSlotLifecycleState {
    OW_WILD_RUNTIME_SLOT_LIFECYCLE_VIRGIN = 0,
    OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED,
    OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED,
} OverworldWildRuntimeSlotLifecycleState;

/*
 * Runtime layers contain stable data identity only. They never own a spawn,
 * species, map-object, save-data, or effective-profile pointer.
 */
typedef struct OverworldWildRuntimeLayer {
    u32 entryGeneration;
    u16 definitionId;
    u16 ownerId;
    u16 instanceKey;
    u16 requiredOwnerId;
    u8 hasTiredOriginKind;
    u8 tiredOriginKind;
    u8 hasRequiredOwnerId;
    u8 reserved;
} OverworldWildRuntimeLayer;

typedef struct OverworldWildRuntimeLayerBank {
    u32 entryGenerations[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    u16 definitionIds[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    u16 ownerIds[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    u16 instanceKeys[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    u16 requiredOwnerIds[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    u8 tiredOriginKinds[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    u8 generatedFlags[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
} OverworldWildRuntimeLayerBank;

typedef struct OverworldWildRuntimeSlotSidecar {
    u32 slotGeneration;
    u32 staticContextGeneration;
    u32 nextEntryGeneration;
    u32 nextTimerGeneration;
    u32 layerGeneration;
    u32 effectiveGeneration;
    u16 lifecycleTransitions;
    u8 activeLayerCount;
    u8 lifecycleState;
    OverworldWildRuntimeLayerBank layerBank;
} OverworldWildRuntimeSlotSidecar;

typedef struct OverworldWildBehaviorStackRuntime {
    u32 handleEpoch;
    u8 lifetimeState;
    u8 reserved[3];
    OverworldWildRuntimeSlotSidecar slots[OW_WILD_MAX_SPAWNS];
} OverworldWildBehaviorStackRuntime;

typedef char OverworldWildRuntimeSpawnCapacityMustRemain10[
    OW_WILD_MAX_SPAWNS == 10 ? 1 : -1];
typedef char OverworldWildRuntimeLayerCapacityMustRemain8[
    OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT == 8 ? 1 : -1];
typedef char OverworldWildRuntimeLayerSizeMustRemain16[
    sizeof(OverworldWildRuntimeLayer) == 16 ? 1 : -1];
typedef char OverworldWildRuntimeLayerBankSizeMustRemain112[
    sizeof(OverworldWildRuntimeLayerBank) == 112 ? 1 : -1];
typedef char OverworldWildRuntimeSlotSidecarSizeMustRemain140[
    sizeof(OverworldWildRuntimeSlotSidecar) == 140 ? 1 : -1];
typedef char OverworldWildBehaviorStackRuntimeSizeMustRemain1408[
    sizeof(OverworldWildBehaviorStackRuntime) == 1408 ? 1 : -1];
typedef char OverworldWildRuntimeLayerArrayMustRemainFixed[
    sizeof(((OverworldWildRuntimeLayerBank *)0)->entryGenerations)
        == sizeof(u32) * OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT
        ? 1 : -1];
typedef char OverworldWildRuntimeSlotArrayMustRemainFixed[
    sizeof(((OverworldWildBehaviorStackRuntime *)0)->slots)
        == sizeof(OverworldWildRuntimeSlotSidecar) * OW_WILD_MAX_SPAWNS
        ? 1 : -1];
typedef char OverworldWildRuntimeHandleSizeMustRemain24[
    sizeof(OverworldWildRuntimeLayerHandle) == 24 ? 1 : -1];
typedef char OverworldWildRuntimeDeltaOperationSizeMustRemain28[
    sizeof(OverworldWildRuntimeDeltaOperation) == 28 ? 1 : -1];
typedef char OverworldWildRuntimeApplicabilityInputSizeMustRemain28[
    sizeof(OverworldWildRuntimeApplicabilityInput) == 28 ? 1 : -1];
typedef char OverworldWildRuntimeStackDeltaRequestSizeMustRemain484[
    sizeof(OverworldWildRuntimeStackDeltaRequest) == 484 ? 1 : -1];
typedef char OverworldWildRuntimeDeltaOperationResultSizeMustRemain28[
    sizeof(OverworldWildRuntimeDeltaOperationResult) == 28 ? 1 : -1];
typedef char OverworldWildRuntimeStackDeltaResultSizeMustRemain484[
    sizeof(OverworldWildRuntimeStackDeltaResult) == 484 ? 1 : -1];

#ifndef OW_WILD_RUNTIME_SIDECAR_CODE
#ifdef OVERWORLD_WILD_RUNTIME_SIDECARS_IMPLEMENTATION
#define OW_WILD_RUNTIME_SIDECAR_CODE \
    __attribute__((noinline, used, section(".ow_wild_runtime_sidecars")))
#else
#define OW_WILD_RUNTIME_SIDECAR_CODE
#endif
#endif

static inline u32 OverworldWildRuntime_AdvanceNonzeroGeneration(u32 generation)
{
    generation++;
    return generation != 0 ? generation : 1;
}

void OW_WILD_RUNTIME_SIDECAR_CODE OverworldWildRuntime_InitSlot(
    OverworldWildRuntimeSlotSidecar *slot);
void OW_WILD_RUNTIME_SIDECAR_CODE OverworldWildRuntime_Init(
    OverworldWildBehaviorStackRuntime *runtime);
void OW_WILD_RUNTIME_SIDECAR_CODE OverworldWildRuntime_DestructivelyInvalidateSlot(
    OverworldWildBehaviorStackRuntime *runtime,
    int slotIndex,
    BOOL wasLive);
void OverworldWildRuntime_HandleSlotGenerationWrap(
    OverworldWildBehaviorStackRuntime *runtime,
    int targetSlotIndex);

/* Lifecycle-only binding. Definitions and generated metadata are copied from
 * the installed validated v40 bundle through a private resident accessor. */
OverworldWildRuntimeStatus OverworldWildRuntime_BindPrivateIdentity(
    OverworldWildBehaviorStackRuntime *runtime);

OverworldWildRuntimeStatus OverworldWildRuntime_ApplyStackDelta(
    OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeStackDeltaRequest *request,
    OverworldWildRuntimeStackDeltaResult *result);
OverworldWildRuntimeStatus OverworldWildRuntime_Apply(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeApplicabilityInput *applicability,
    u16 definitionId,
    u16 ownerId,
    u16 instanceKey,
    OverworldWildRuntimeStackDeltaResult *result);
OverworldWildRuntimeStatus OverworldWildRuntime_Replace(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeApplicabilityInput *applicability,
    u16 ownerId,
    u16 instanceKey,
    u16 definitionId,
    OverworldWildRuntimeStackDeltaResult *result);
OverworldWildRuntimeStatus OverworldWildRuntime_Remove(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeLayerHandle *handle,
    OverworldWildRuntimeStackDeltaResult *result);
OverworldWildRuntimeStatus OverworldWildRuntime_RemoveOwner(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    u16 ownerId,
    OverworldWildRuntimeStackDeltaResult *result);
OverworldWildRuntimeStatus OverworldWildRuntime_ClearAllForSlot(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    OverworldWildRuntimeStackDeltaResult *result);

u8 OverworldWildRuntime_GetLayerCount(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration);
OverworldWildRuntimeStatus OverworldWildRuntime_GetLayerByIndex(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    u8 layerIndex,
    OverworldWildRuntimeLayer *layerOut);
OverworldWildRuntimeStatus OverworldWildRuntime_FindLayer(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    u16 ownerId,
    u16 instanceKey,
    OverworldWildRuntimeLayer *layerOut,
    OverworldWildRuntimeLayerHandle *handleOut);

static inline void OverworldWildRuntime_MarkResidentCold(
    OverworldWildBehaviorStackRuntime *runtime)
{
    runtime->lifetimeState = OW_WILD_RUNTIME_LIFETIME_RESIDENT_COLD;
}

static inline void OverworldWildRuntime_Activate(
    OverworldWildBehaviorStackRuntime *runtime)
{
    runtime->lifetimeState = OW_WILD_RUNTIME_LIFETIME_ACTIVE;
}

static inline void OverworldWildRuntime_MarkSlotAssigned(
    OverworldWildBehaviorStackRuntime *runtime,
    int slotIndex)
{
    runtime->slots[slotIndex].lifecycleState =
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED;
}

#endif // OVERWORLD_WILD_RUNTIME_SIDECARS_H

#ifdef OVERWORLD_WILD_RUNTIME_SIDECARS_IMPLEMENTATION

void OW_WILD_RUNTIME_SIDECAR_CODE OverworldWildRuntime_InitSlot(
    OverworldWildRuntimeSlotSidecar *slot)
{
    memset(slot, 0, sizeof(*slot));
    slot->slotGeneration = 1;
    slot->staticContextGeneration = 1;
    slot->nextEntryGeneration = 1;
    slot->nextTimerGeneration = 1;
    slot->layerGeneration = 1;
    slot->effectiveGeneration = 1;
    slot->lifecycleState = OW_WILD_RUNTIME_SLOT_LIFECYCLE_VIRGIN;
}

void OW_WILD_RUNTIME_SIDECAR_CODE OverworldWildRuntime_Init(
    OverworldWildBehaviorStackRuntime *runtime)
{
    int slot;

    runtime->handleEpoch = 1;
    runtime->lifetimeState = OW_WILD_RUNTIME_LIFETIME_ACTIVE;
    runtime->reserved[0] = 0;
    runtime->reserved[1] = 0;
    runtime->reserved[2] = 0;
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        OverworldWildRuntime_InitSlot(&runtime->slots[slot]);
    }
}

void OW_WILD_RUNTIME_SIDECAR_CODE OverworldWildRuntime_DestructivelyInvalidateSlot(
    OverworldWildBehaviorStackRuntime *runtime,
    int slotIndex,
    BOOL wasLive)
{
    OverworldWildRuntimeSlotSidecar *slot;
    u32 slotGeneration;

    if (!wasLive) {
        return;
    }

    slot = &runtime->slots[slotIndex];
    slotGeneration = slot->slotGeneration + 1;
    if (slotGeneration == 0) {
        OverworldWildRuntime_HandleSlotGenerationWrap(runtime, slotIndex);
        return;
    }

    OverworldWildRuntime_InitSlot(slot);
    slot->slotGeneration = slotGeneration;
    slot->lifecycleTransitions = 1;
    slot->lifecycleState =
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED;
}

#endif // OVERWORLD_WILD_RUNTIME_SIDECARS_IMPLEMENTATION
