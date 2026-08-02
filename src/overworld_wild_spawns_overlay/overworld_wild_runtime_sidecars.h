#ifndef OVERWORLD_WILD_RUNTIME_SIDECARS_H
#define OVERWORLD_WILD_RUNTIME_SIDECARS_H

#include "../../include/overworld_wild_spawns_internal.h"

#define OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT 8
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
    int globalSlot;
    u32 slotGeneration;

    if (!wasLive) {
        return;
    }

    slot = &runtime->slots[slotIndex];
    slotGeneration = slot->slotGeneration + 1;
    if (slotGeneration == 0) {
        if (runtime->handleEpoch == 0xFFFFFFFFu) {
            for (globalSlot = 0;
                 globalSlot < OW_WILD_MAX_SPAWNS;
                 globalSlot++) {
                slot = &runtime->slots[globalSlot];
                slotGeneration = OverworldWildRuntime_AdvanceNonzeroGeneration(
                    slot->slotGeneration);
                OverworldWildRuntime_InitSlot(slot);
                slot->slotGeneration = slotGeneration;
                slot->lifecycleTransitions = 1;
                slot->lifecycleState =
                    OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED;
            }
            runtime->handleEpoch = 1;
            return;
        }
        runtime->handleEpoch++;
        slotGeneration = 1;
    }

    OverworldWildRuntime_InitSlot(slot);
    slot->slotGeneration = slotGeneration;
    slot->lifecycleTransitions = 1;
    slot->lifecycleState =
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED;
}

#endif // OVERWORLD_WILD_RUNTIME_SIDECARS_IMPLEMENTATION
