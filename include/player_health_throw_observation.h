#ifndef PLAYER_HEALTH_THROW_OBSERVATION_H
#define PLAYER_HEALTH_THROW_OBSERVATION_H

#include "overworld_behavior_condition_adapter.h"
#include "overworld_wild_spawns_internal.h"

#define PLAYER_HEALTH_THROW_SERVICE_ADDR 0x01FFC180
#define PLAYER_HEALTH_THROW_SERVICE_MAGIC 0x4F485450 /* PTHO */
#define PLAYER_HEALTH_THROW_SERVICE_VERSION 2

typedef BOOL (*PlayerHealthThrowIsCurrentSpawnFunc)(
    FieldSystem *fieldSystem, const OverworldWildSpawn *spawn);
typedef BOOL (*PlayerHealthThrowQueryTargetFunc)(
    OverworldWildSpawnState *state, int carrierSlot, int targetSlot,
    u8 query, u32 motionMasks);
typedef struct OverworldWildHelperOverlayEntry OverworldWildHelperOverlayEntry;
typedef void (*PlayerHealthThrowStartTiredFunc)(
    OverworldWildSpawnState *state, int slot,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives);

typedef struct PlayerHealthThrowServiceEntry {
    u32 magic;
    u16 version;
    u16 size;
    u32 (*observe)(OverworldWildSpawnState *state, int slot,
        const OverworldWildBehaviorProfile *profile,
        const OverworldWildBehaviorDataBlob *blob,
        const OverworldWildBehaviorConditionRuntime *conditions,
        PlayerHealthThrowIsCurrentSpawnFunc isCurrentSpawn,
        PlayerHealthThrowQueryTargetFunc queryTarget);
    BOOL (*tryReserve)(OverworldWildSpawnState *state,
        int carrierSlot, int targetSlot,
        const OverworldWildHelperOverlayEntry *helperEntry,
        PlayerHealthThrowIsCurrentSpawnFunc isCurrentSpawn);
    void (*startRecovery)(OverworldWildSpawnState *state, int slot,
        const OverworldWildBehaviorProfile *profile,
        const OverworldWildBehaviorPrimitives *primitives,
        PlayerHealthThrowStartTiredFunc startTired);
    BOOL (*isStableTarget)(OverworldWildSpawnState *state,
        int carrierSlot, int targetSlot,
        PlayerHealthThrowQueryTargetFunc queryTarget);
    u16 (*unstableMask)(OverworldWildSpawnState *state);
    BOOL (*bindingPosition)(OverworldWildSpawnState *, u8, u8, OverworldTargetBindingPosition *);
} PlayerHealthThrowServiceEntry;

#define PLAYER_HEALTH_THROW_SERVICE_ENTRY \
    ((const PlayerHealthThrowServiceEntry *)PLAYER_HEALTH_THROW_SERVICE_ADDR)

static inline BOOL PlayerHealthThrowService_IsReady(void)
{
    const PlayerHealthThrowServiceEntry *entry =
        PLAYER_HEALTH_THROW_SERVICE_ENTRY;

    return entry->magic == PLAYER_HEALTH_THROW_SERVICE_MAGIC
        && entry->version == PLAYER_HEALTH_THROW_SERVICE_VERSION
        && entry->size == sizeof(*entry);
}

#endif // PLAYER_HEALTH_THROW_OBSERVATION_H
