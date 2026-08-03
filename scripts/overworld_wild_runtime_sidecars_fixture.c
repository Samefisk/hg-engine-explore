#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Host the exact private production primitives without importing the NDS SDK. */
#define OVERWORLD_WILD_SPAWNS_INTERNAL_H
#define OW_WILD_MAX_SPAWNS 10
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0

#define OW_WILD_RUNTIME_SIDECAR_CODE __attribute__((noinline))
#define OVERWORLD_WILD_RUNTIME_SIDECARS_IMPLEMENTATION
#include "../src/overworld_wild_spawns_overlay/overworld_wild_runtime_sidecars.h"

void OverworldWildRuntime_ClearSlotStorage(
    OverworldWildRuntimeSlotSidecar *slot)
{
    memset(slot, 0, sizeof(*slot));
}

void OverworldWildRuntime_InitializeStorage(
    OverworldWildBehaviorStackRuntime *runtime)
{
    int slotIndex;
    memset(runtime, 0, sizeof(*runtime));
    runtime->handleEpoch = 1;
    runtime->dataIncarnation = 1;
    runtime->lifetimeState = OW_WILD_RUNTIME_LIFETIME_ACTIVE;
    for (slotIndex = 0; slotIndex < OW_WILD_MAX_SPAWNS; slotIndex++) {
        OverworldWildRuntimeSlotSidecar *slot = &runtime->slots[slotIndex];
        slot->slotGeneration = 1;
        slot->staticContextGeneration = 1;
        slot->nextEntryGeneration = 1;
        slot->nextTimerGeneration = 1;
        slot->layerGeneration = 1;
        slot->effectiveGeneration = 1;
        slot->cacheIncarnation = 1;
        slot->lifecycleState = OW_WILD_RUNTIME_SLOT_LIFECYCLE_VIRGIN;
    }
}

void OverworldWildRuntime_MarkResidentCold(
    OverworldWildBehaviorStackRuntime *runtime)
{
    int slot;
    runtime->dataIncarnation = OverworldWildRuntime_AdvanceNonzeroGeneration(
        runtime->dataIncarnation);
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        runtime->slots[slot].cacheIncarnation =
            OverworldWildRuntime_AdvanceNonzeroGeneration(
                runtime->slots[slot].cacheIncarnation);
        memset(&runtime->slots[slot].staticCache, 0,
            sizeof(runtime->slots[slot].staticCache));
        memset(&runtime->slots[slot].effectiveCache, 0,
            sizeof(runtime->slots[slot].effectiveCache));
        memset(&runtime->slots[slot].provenance, 0,
            sizeof(runtime->slots[slot].provenance));
    }
    runtime->lifetimeState = OW_WILD_RUNTIME_LIFETIME_RESIDENT_COLD;
}

static int sLiveHelperCalls;

void OverworldWildRuntime_HandleSlotGenerationWrap(
    OverworldWildBehaviorStackRuntime *runtime,
    int targetSlot)
{
    OverworldWildRuntimeSlotSidecar *target = &runtime->slots[targetSlot];
    u32 slotGeneration = target->slotGeneration + 1;
    u32 cacheIncarnation = OverworldWildRuntime_AdvanceNonzeroGeneration(
        target->cacheIncarnation);
    int slot;
    int layer;

    sLiveHelperCalls++;
    if (slotGeneration != 0) {
        OverworldWildRuntime_InitSlot(target);
        target->slotGeneration = slotGeneration;
        target->cacheIncarnation = cacheIncarnation;
        target->lifecycleTransitions = 1;
        target->lifecycleState =
            OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED;
        return;
    }
    if (runtime->handleEpoch == 0xFFFFFFFFu) {
        for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
            u32 generation = OverworldWildRuntime_AdvanceNonzeroGeneration(
                runtime->slots[slot].slotGeneration);
            u32 incarnation = OverworldWildRuntime_AdvanceNonzeroGeneration(
                runtime->slots[slot].cacheIncarnation);
            OverworldWildRuntime_InitSlot(&runtime->slots[slot]);
            runtime->slots[slot].slotGeneration = generation;
            runtime->slots[slot].cacheIncarnation = incarnation;
            runtime->slots[slot].lifecycleTransitions = 1;
            runtime->slots[slot].lifecycleState =
                OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED;
        }
        runtime->handleEpoch = 1;
        runtime->dataIncarnation = OverworldWildRuntime_AdvanceNonzeroGeneration(
            runtime->dataIncarnation);
        return;
    }
    runtime->dataIncarnation = OverworldWildRuntime_AdvanceNonzeroGeneration(
        runtime->dataIncarnation);
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        runtime->slots[slot].cacheIncarnation =
            OverworldWildRuntime_AdvanceNonzeroGeneration(
                runtime->slots[slot].cacheIncarnation);
        if (slot == targetSlot) continue;
        runtime->slots[slot].nextTimerGeneration = 1;
        for (layer = 0; layer < runtime->slots[slot].activeLayerCount; layer++) {
            runtime->slots[slot].layerBank.entryGenerations[layer] = layer + 1;
            if (runtime->slots[slot].timerBank.timers[layer].flags
                    & OW_WILD_RUNTIME_TIMER_VALID) {
                runtime->slots[slot].timerBank.timers[layer].entryGeneration =
                    layer + 1;
                runtime->slots[slot].timerBank.timers[layer].timerGeneration =
                    runtime->slots[slot].nextTimerGeneration++;
            }
        }
        runtime->slots[slot].nextEntryGeneration =
            runtime->slots[slot].activeLayerCount + 1;
        if (runtime->slots[slot].activeLayerCount)
            runtime->slots[slot].layerGeneration =
                OverworldWildRuntime_AdvanceNonzeroGeneration(
                    runtime->slots[slot].layerGeneration);
    }
    runtime->handleEpoch++;
    {
        u32 incarnation = runtime->slots[targetSlot].cacheIncarnation;
    OverworldWildRuntime_InitSlot(&runtime->slots[targetSlot]);
        runtime->slots[targetSlot].cacheIncarnation = incarnation;
    }
    runtime->slots[targetSlot].slotGeneration = 1;
    runtime->slots[targetSlot].lifecycleTransitions = 1;
    runtime->slots[targetSlot].lifecycleState =
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED;
}

_Static_assert(OW_WILD_MAX_SPAWNS == 10, "spawn capacity changed");
_Static_assert(OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT == 8, "layer capacity changed");
_Static_assert(sizeof(OverworldWildRuntimeLayer) == 16, "layer layout changed");
_Static_assert(sizeof(OverworldWildRuntimeLayerBank) == 112, "layer bank layout changed");
_Static_assert(sizeof(OverworldWildRuntimeTimer) == 24, "timer layout changed");
_Static_assert(sizeof(OverworldWildRuntimeTimerBank) == 192, "timer bank layout changed");
_Static_assert(sizeof(OverworldWildRuntimeTimerExpiry) == 32, "expiry layout changed");
_Static_assert(sizeof(OverworldWildRuntimeStaticContext) == 12, "static context layout changed");
_Static_assert(sizeof(OverworldWildRuntimeStaticModifierContribution) == 18, "static contribution layout changed");
_Static_assert(sizeof(OverworldWildRuntimeResolvedNode) == 38, "resolved node layout changed");
_Static_assert(sizeof(OverworldWildRuntimeStaticCache) == 540, "static cache layout changed");
_Static_assert(sizeof(OverworldWildRuntimeEffectiveCache) == 104, "effective cache layout changed");
_Static_assert(sizeof(OverworldWildRuntimeProvenance) == 728, "provenance layout changed");
_Static_assert(sizeof(OverworldWildRuntimeSlotSidecar) == 1712, "slot layout changed");
_Static_assert(sizeof(OverworldWildBehaviorStackRuntime) == 17132, "runtime layout changed");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, slotGeneration) == 0, "slot generation moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, staticContextGeneration) == 4, "static generation moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, nextEntryGeneration) == 8, "entry generation moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, nextTimerGeneration) == 12, "timer generation moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, layerGeneration) == 16, "layer generation moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, effectiveGeneration) == 20, "effective generation moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, cacheIncarnation) == 24, "cache incarnation moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, lifecycleTransitions) == 28, "diagnostics moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, activeLayerCount) == 30, "active count moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, lifecycleState) == 31, "lifecycle state moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, presentationGate) == 32, "timer gate moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, layerBank) == 36, "layer bank moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, timerBank) == 148, "timer bank moved");
_Static_assert(offsetof(OverworldWildBehaviorStackRuntime, handleEpoch) == 0, "runtime epoch moved");
_Static_assert(offsetof(OverworldWildBehaviorStackRuntime, dataIncarnation) == 4, "runtime incarnation moved");
_Static_assert(offsetof(OverworldWildBehaviorStackRuntime, lifetimeState) == 8, "runtime lifetime moved");
_Static_assert(offsetof(OverworldWildBehaviorStackRuntime, slots) == 12, "runtime slots moved");

static int sChecks;

static void require(BOOL condition, const char *message)
{
    sChecks++;
    if (!condition) {
        fprintf(stderr, "runtime sidecar fixture failed: %s\n", message);
        fflush(stderr);
        _Exit(1);
    }
}

static BOOL bytes_are_zero(const void *data, size_t size)
{
    const u8 *bytes = (const u8 *)data;
    size_t i;

    for (i = 0; i < size; i++) {
        if (bytes[i] != 0) {
            return FALSE;
        }
    }
    return TRUE;
}

static void require_empty_slot(
    const OverworldWildRuntimeSlotSidecar *slot,
    u32 generation,
    u16 transitions,
    u8 lifecycleState)
{
    require(slot->slotGeneration == generation, "slot generation differs");
    require(slot->staticContextGeneration == 1, "static context generation is not virgin");
    require(slot->nextEntryGeneration == 1, "next entry generation is not virgin");
    require(slot->nextTimerGeneration == 1, "next timer generation is not virgin");
    require(slot->layerGeneration == 1, "layer generation is not virgin");
    require(slot->effectiveGeneration == 1, "effective generation is not virgin");
    require(slot->cacheIncarnation != 0, "cache incarnation is zero");
    require(slot->lifecycleTransitions == transitions, "lifecycle diagnostic differs");
    require(slot->activeLayerCount == 0, "empty slot has active layers");
    require(slot->lifecycleState == lifecycleState, "lifecycle state differs");
    require(slot->presentationGate == 0, "empty slot retained timer gate");
    require(bytes_are_zero(&slot->layerBank, sizeof(slot->layerBank)), "empty slot retained layer bytes");
    require(bytes_are_zero(&slot->timerBank, sizeof(slot->timerBank)), "empty slot retained timer bytes");
    require(bytes_are_zero(&slot->staticCache, sizeof(slot->staticCache)), "empty slot retained static cache bytes");
    require(bytes_are_zero(&slot->effectiveCache, sizeof(slot->effectiveCache)), "empty slot retained effective cache bytes");
    require(bytes_are_zero(&slot->provenance, sizeof(slot->provenance)), "empty slot retained provenance bytes");
}

static void fill_live_slot(OverworldWildBehaviorStackRuntime *runtime, int slotIndex)
{
    OverworldWildRuntimeSlotSidecar *slot = &runtime->slots[slotIndex];
    int i;

    OverworldWildRuntime_MarkSlotAssigned(runtime, slotIndex);
    slot->staticContextGeneration = 0x10203040u;
    slot->nextEntryGeneration = 0x13572468u;
    slot->nextTimerGeneration = 0x24681357u;
    slot->layerGeneration = 0x11223344u;
    slot->effectiveGeneration = 0x55667788u;
    slot->lifecycleTransitions = 0xA55Au;
    slot->activeLayerCount = OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT;
    slot->presentationGate = TRUE;
    for (i = 0; i < OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT; i++) {
        slot->layerBank.entryGenerations[i] = (u32)i + 17;
        slot->layerBank.definitionIds[i] = (u16)(100 + i);
        slot->layerBank.ownerIds[i] = (u16)(200 + i);
        slot->layerBank.instanceKeys[i] = (u16)(300 + i);
        slot->layerBank.requiredOwnerIds[i] = (u16)(400 + i);
        slot->layerBank.tiredOriginKinds[i] = (u8)i;
        slot->layerBank.generatedFlags[i] = 0xA5;
        slot->timerBank.timers[i].entryGeneration = (u32)i + 17;
        slot->timerBank.timers[i].timerGeneration = (u32)i + 33;
        slot->timerBank.timers[i].ownerId = (u16)(200 + i);
        slot->timerBank.timers[i].instanceKey = (u16)(300 + i);
        slot->timerBank.timers[i].definitionId = (u16)(100 + i);
        slot->timerBank.timers[i].remainingTicks = (u8)(8 - i);
        slot->timerBank.timers[i].armedDuration = 8;
        slot->timerBank.timers[i].clock = OW_WILD_RUNTIME_TIMER_CLOCK_FRAME;
        slot->timerBank.timers[i].hiddenPolicy =
            OW_WILD_RUNTIME_HIDDEN_TIMER_PAUSE_WHILE_HIDDEN;
        slot->timerBank.timers[i].recoveryPolicy = 1;
        slot->timerBank.timers[i].flags = OW_WILD_RUNTIME_TIMER_VALID;
    }
    memset(&slot->staticCache, 0x5A, sizeof(slot->staticCache));
    memset(&slot->effectiveCache, 0x6B, sizeof(slot->effectiveCache));
    memset(&slot->provenance, 0x7C, sizeof(slot->provenance));
}

typedef struct FixtureColdSpawn {
    u8 active;
    u8 shiny;
} FixtureColdSpawn;

typedef struct FixtureColdContext {
    OverworldWildBehaviorStackRuntime *runtime;
    FixtureColdSpawn spawns[OW_WILD_MAX_SPAWNS];
    u16 savedHp[OW_WILD_MAX_SPAWNS];
    u8 auxiliaryOwned[OW_WILD_MAX_SPAWNS];
    u8 residentAttached;
    u8 resetCalls;
    u8 shinySaves;
} FixtureColdContext;

static void fixture_reset_slot(FixtureColdContext *context, int slotIndex)
{
    OverworldWildRuntime_DestructivelyInvalidateSlot(
        context->runtime,
        slotIndex,
        context->spawns[slotIndex].active);
    OverworldWildRuntime_Activate(context->runtime);
    context->savedHp[slotIndex] = 0;
    context->auxiliaryOwned[slotIndex] = 0;
    context->spawns[slotIndex].active = FALSE;
    context->spawns[slotIndex].shiny = FALSE;
    context->resetCalls++;
}

/* Production-shaped cold DISCARD: the retained allocation reattaches its
 * canonical resident block and reuses the full authoritative reset route. */
static void fixture_clear_context_lite(FixtureColdContext *context)
{
    int slot;

    if (context->runtime != NULL) {
        context->residentAttached = TRUE;
        for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
            if (context->spawns[slot].active) {
                if (context->spawns[slot].shiny) {
                    context->shinySaves++;
                }
                fixture_reset_slot(context, slot);
            }
        }
    } else {
        for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
            if (context->spawns[slot].active
                && context->spawns[slot].shiny) {
                context->shinySaves++;
            }
        }
        memset(context->spawns, 0, sizeof(context->spawns));
    }
}

int main(void)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime before;
    FixtureColdContext cold;
    u32 assignedGeneration;
    u32 cacheIncarnationBefore;
    u32 generationsBeforeRestart[OW_WILD_MAX_SPAWNS];
    int slot;

    memset(&runtime, 0xA5, sizeof(runtime));
    OverworldWildRuntime_Init(&runtime);
    require(runtime.handleEpoch == 1, "virgin handle epoch is not one");
    require(runtime.dataIncarnation == 1, "virgin data incarnation is not one");
    require(runtime.lifetimeState == OW_WILD_RUNTIME_LIFETIME_ACTIVE,
        "virgin runtime is not active");
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        require_empty_slot(
            &runtime.slots[slot], 1, 0,
            OW_WILD_RUNTIME_SLOT_LIFECYCLE_VIRGIN);
    }

    fill_live_slot(&runtime, 3);
    before = runtime;
    cacheIncarnationBefore = runtime.slots[3].cacheIncarnation;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 3, TRUE);
    require(sLiveHelperCalls == 1,
        "ordinary live wrapper did not delegate exactly once");
    require(runtime.handleEpoch == 1, "ordinary invalidation changed handle epoch");
    require_empty_slot(
        &runtime.slots[3], 2, 1,
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED);
    require(runtime.slots[3].cacheIncarnation
            == OverworldWildRuntime_AdvanceNonzeroGeneration(
                cacheIncarnationBefore),
        "ordinary invalidation did not advance the prior cache incarnation");
    require(!memcmp(&runtime.slots[2], &before.slots[2], sizeof(runtime.slots[2])),
        "invalidation changed the previous slot");
    require(!memcmp(&runtime.slots[4], &before.slots[4], sizeof(runtime.slots[4])),
        "invalidation changed the next slot");

    fill_live_slot(&runtime, 3);
    before = runtime;
    cacheIncarnationBefore = runtime.slots[3].cacheIncarnation;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 3, TRUE);
    require(sLiveHelperCalls == 2,
        "repeated live wrapper did not delegate exactly once");
    require_empty_slot(
        &runtime.slots[3], 3, 1,
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED);
    require(runtime.slots[3].cacheIncarnation
            == OverworldWildRuntime_AdvanceNonzeroGeneration(
                cacheIncarnationBefore),
        "repeated live invalidation did not advance the prior cache incarnation");
    require(!memcmp(&runtime.slots[2], &before.slots[2], sizeof(runtime.slots[2]))
            && !memcmp(&runtime.slots[4], &before.slots[4],
                sizeof(runtime.slots[4])),
        "repeated live invalidation changed bystander slots");

    before = runtime;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 3, FALSE);
    require(sLiveHelperCalls == 2,
        "false destructive wrapper delegated to the live helper");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "repeated empty invalidation was not idempotent");

    assignedGeneration = runtime.slots[3].slotGeneration;
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 3);
    require(runtime.slots[3].slotGeneration == assignedGeneration,
        "new assignment advanced slot generation");
    require(runtime.slots[3].lifecycleTransitions == 1,
        "assignment changed destructive lifecycle diagnostics");
    require(runtime.slots[3].lifecycleState == OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED,
        "new assignment did not publish assigned lifecycle");
    require_empty_slot(
        &runtime.slots[3], assignedGeneration, 1,
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED);

    before = runtime;
    require(OverworldWildRuntime_AdvanceNonzeroGeneration(0) == 1,
        "zero generation was not repaired to one");
    require(OverworldWildRuntime_AdvanceNonzeroGeneration(1) == 2,
        "ordinary generation did not advance");
    require(OverworldWildRuntime_AdvanceNonzeroGeneration(0xFFFFFFFFu) == 1,
        "generation wrap did not skip zero");

    memset(&cold, 0, sizeof(cold));
    OverworldWildRuntime_Init(&runtime);
    cold.runtime = &runtime;
    fill_live_slot(&runtime, 2);
    fill_live_slot(&runtime, 7);
    cold.spawns[2].active = TRUE;
    cold.spawns[2].shiny = TRUE;
    cold.spawns[7].active = TRUE;
    cold.savedHp[2] = 40;
    cold.savedHp[7] = 80;
    cold.auxiliaryOwned[2] = TRUE;
    cold.auxiliaryOwned[7] = TRUE;
    OverworldWildRuntime_MarkResidentCold(&runtime);
    before = runtime;
    fixture_clear_context_lite(&cold);
    require(cold.residentAttached, "cold discard did not reattach resident data");
    require(cold.resetCalls == 2, "cold discard did not reset each live slot once");
    require(cold.shinySaves == 1, "cold discard did not preserve shiny reservation behavior");
    require(cold.savedHp[2] == 0 && cold.savedHp[7] == 0,
        "cold discard retained saved HP");
    require(cold.auxiliaryOwned[2] == 0 && cold.auxiliaryOwned[7] == 0,
        "cold discard retained auxiliary ownership");
    require(!cold.spawns[2].active && !cold.spawns[7].active,
        "cold discard retained live spawn records");
    require(runtime.lifetimeState == OW_WILD_RUNTIME_LIFETIME_ACTIVE,
        "cold discard did not reactivate retained runtime cleanup");
    require_empty_slot(
        &runtime.slots[2], 2, 1,
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED);
    require_empty_slot(
        &runtime.slots[7], 2, 1,
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED);
    require(!memcmp(&runtime.slots[4], &before.slots[4], sizeof(runtime.slots[4])),
        "cold discard changed an empty sidecar");
    before = runtime;
    fixture_clear_context_lite(&cold);
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "repeated cold discard changed empty sidecars");
    require(cold.resetCalls == 2 && cold.shinySaves == 1,
        "repeated cold discard repeated logical cleanup");
    assignedGeneration = runtime.slots[2].slotGeneration;
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 2);
    require(runtime.slots[2].slotGeneration == assignedGeneration,
        "cold-slot reassignment advanced generation");
    cold.spawns[2].active = TRUE;
    fixture_clear_context_lite(&cold);
    require_empty_slot(
        &runtime.slots[2], assignedGeneration + 1, 1,
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED);
    require(cold.resetCalls == 3, "reused cold slot did not reset exactly once");

    memset(&cold, 0, sizeof(cold));
    cold.spawns[1].active = TRUE;
    cold.spawns[1].shiny = TRUE;
    fixture_clear_context_lite(&cold);
    require(!cold.spawns[1].active
        && cold.runtime == NULL
        && cold.shinySaves == 1,
        "runtime-null fallback fabricated resident lifecycle state");

    OverworldWildRuntime_Init(&runtime);
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        fill_live_slot(&runtime, slot);
        runtime.slots[slot].slotGeneration = (u32)(100 + slot);
        generationsBeforeRestart[slot] = runtime.slots[slot].slotGeneration;
    }
    runtime.handleEpoch = 0xFFFFFFFFu;
    runtime.slots[7].slotGeneration = 0xFFFFFFFFu;
    generationsBeforeRestart[7] = 0xFFFFFFFFu;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 7, TRUE);
    require(runtime.handleEpoch == 1, "handle epoch wrap did not skip zero");
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        u32 expectedGeneration =
            OverworldWildRuntime_AdvanceNonzeroGeneration(
                generationsBeforeRestart[slot]);
        require_empty_slot(
            &runtime.slots[slot], expectedGeneration, 1,
            OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED);
        require(runtime.slots[slot].slotGeneration != 0,
            "terminal epoch restart published zero slot generation");
    }
    require(runtime.slots[7].lifecycleTransitions == 1,
        "terminal restart double-counted target invalidation");
    before = runtime;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 7, FALSE);
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "empty cleanup after terminal restart was not idempotent");

    OverworldWildRuntime_Init(&runtime);
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        fill_live_slot(&runtime, slot);
        OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, slot, TRUE);
    }
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        require_empty_slot(
            &runtime.slots[slot], 2, 1,
            OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED);
    }

    before = runtime;
    OverworldWildRuntime_MarkResidentCold(&runtime);
    require(runtime.lifetimeState == OW_WILD_RUNTIME_LIFETIME_RESIDENT_COLD,
        "resident cleanup did not publish cold lifetime");
    before.dataIncarnation = OverworldWildRuntime_AdvanceNonzeroGeneration(
        before.dataIncarnation);
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        before.slots[slot].cacheIncarnation =
            OverworldWildRuntime_AdvanceNonzeroGeneration(
                before.slots[slot].cacheIncarnation);
        memset(&before.slots[slot].staticCache, 0,
            sizeof(before.slots[slot].staticCache));
        memset(&before.slots[slot].effectiveCache, 0,
            sizeof(before.slots[slot].effectiveCache));
        memset(&before.slots[slot].provenance, 0,
            sizeof(before.slots[slot].provenance));
    }
    before.lifetimeState = OW_WILD_RUNTIME_LIFETIME_RESIDENT_COLD;
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "resident-cold transition changed logical sidecars");
    OverworldWildRuntime_Activate(&runtime);
    require(runtime.lifetimeState == OW_WILD_RUNTIME_LIFETIME_ACTIVE,
        "resident reactivation did not publish active lifetime");
    before.lifetimeState = OW_WILD_RUNTIME_LIFETIME_ACTIVE;
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "resident activation changed logical sidecars");

    printf(
        "runtime sidecars host fixture: %d checks; layer=%lu bank=%lu slot=%lu runtime=%lu; 10 slots x 8 layers\n",
        sChecks,
        (unsigned long)sizeof(OverworldWildRuntimeLayer),
        (unsigned long)sizeof(OverworldWildRuntimeLayerBank),
        (unsigned long)sizeof(OverworldWildRuntimeSlotSidecar),
        (unsigned long)sizeof(OverworldWildBehaviorStackRuntime));
    return 0;
}
