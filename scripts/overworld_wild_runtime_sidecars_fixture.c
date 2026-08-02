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

_Static_assert(OW_WILD_MAX_SPAWNS == 10, "spawn capacity changed");
_Static_assert(OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT == 8, "layer capacity changed");
_Static_assert(sizeof(OverworldWildRuntimeLayer) == 16, "layer layout changed");
_Static_assert(sizeof(OverworldWildRuntimeLayerBank) == 112, "layer bank layout changed");
_Static_assert(sizeof(OverworldWildRuntimeSlotSidecar) == 140, "slot layout changed");
_Static_assert(sizeof(OverworldWildBehaviorStackRuntime) == 1408, "runtime layout changed");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, slotGeneration) == 0, "slot generation moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, staticContextGeneration) == 4, "static generation moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, nextEntryGeneration) == 8, "entry generation moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, nextTimerGeneration) == 12, "timer generation moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, layerGeneration) == 16, "layer generation moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, effectiveGeneration) == 20, "effective generation moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, lifecycleTransitions) == 24, "diagnostics moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, activeLayerCount) == 26, "active count moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, lifecycleState) == 27, "lifecycle state moved");
_Static_assert(offsetof(OverworldWildRuntimeSlotSidecar, layerBank) == 28, "layer bank moved");
_Static_assert(offsetof(OverworldWildBehaviorStackRuntime, handleEpoch) == 0, "runtime epoch moved");
_Static_assert(offsetof(OverworldWildBehaviorStackRuntime, lifetimeState) == 4, "runtime lifetime moved");
_Static_assert(offsetof(OverworldWildBehaviorStackRuntime, slots) == 8, "runtime slots moved");

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
    require(slot->lifecycleTransitions == transitions, "lifecycle diagnostic differs");
    require(slot->activeLayerCount == 0, "empty slot has active layers");
    require(slot->lifecycleState == lifecycleState, "lifecycle state differs");
    require(bytes_are_zero(&slot->layerBank, sizeof(slot->layerBank)), "empty slot retained layer bytes");
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
    for (i = 0; i < OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT; i++) {
        slot->layerBank.entryGenerations[i] = (u32)i + 17;
        slot->layerBank.definitionIds[i] = (u16)(100 + i);
        slot->layerBank.ownerIds[i] = (u16)(200 + i);
        slot->layerBank.instanceKeys[i] = (u16)(300 + i);
        slot->layerBank.requiredOwnerIds[i] = (u16)(400 + i);
        slot->layerBank.tiredOriginKinds[i] = (u8)i;
        slot->layerBank.generatedFlags[i] = 0xA5;
    }
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
    u32 generationsBeforeRestart[OW_WILD_MAX_SPAWNS];
    int slot;

    memset(&runtime, 0xA5, sizeof(runtime));
    OverworldWildRuntime_Init(&runtime);
    require(runtime.handleEpoch == 1, "virgin handle epoch is not one");
    require(runtime.lifetimeState == OW_WILD_RUNTIME_LIFETIME_ACTIVE,
        "virgin runtime is not active");
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        require_empty_slot(
            &runtime.slots[slot], 1, 0,
            OW_WILD_RUNTIME_SLOT_LIFECYCLE_VIRGIN);
    }

    fill_live_slot(&runtime, 3);
    before = runtime;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 3, TRUE);
    require(runtime.handleEpoch == 1, "ordinary invalidation changed handle epoch");
    require_empty_slot(
        &runtime.slots[3], 2, 1,
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED);
    require(!memcmp(&runtime.slots[2], &before.slots[2], sizeof(runtime.slots[2])),
        "invalidation changed the previous slot");
    require(!memcmp(&runtime.slots[4], &before.slots[4], sizeof(runtime.slots[4])),
        "invalidation changed the next slot");

    before = runtime;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 3, FALSE);
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
