#ifndef OVERWORLD_SPAWN_GUARD_H
#define OVERWORLD_SPAWN_GUARD_H

#include "overworld_actor_system_internal.h"
#include "overworld_wild_helper.h"

#define OVERWORLD_WILD_SPAWN_GUARD_READ_ENTRY_ADDR 0x023C025C
#define OVERWORLD_WILD_SPAWN_GUARD_NEAR_ENTRY_ADDR 0x023C034C
#define OVERWORLD_WILD_SPAWN_GUARD_SURF_ENTRY_ADDR 0x023C03D0

typedef struct OverworldWildQueuedSpawnGuard {
    OverworldActorFieldContext context;
    void *manager;
    OverworldWildSurfaceHit surface;
    OverworldWildSavedShiny savedShiny;
    s16 playerX, playerY;
    u16 mapId, generation;
    u8 targetBehavior, originBehavior, hasSurface, playerFacing, active;
} OverworldWildQueuedSpawnGuard;

typedef BOOL (*OverworldWildSpawnGuardSurfaceQueryFunc)(
    FieldSystem *fieldSystem,
    int x,
    int y,
    OverworldWildSurfaceHit *hit);

BOOL OverworldWildSpawnGuard_Read(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const OverworldWildPreparedSpawn *prepared,
    int slot,
    OverworldWildQueuedSpawnGuard *guard,
    OverworldWildSpawnGuardSurfaceQueryFunc querySurface);

BOOL OverworldWildSpawnGuard_IsNearActiveSpawn(
    const OverworldWildSpawnState *state,
    int x,
    int y,
    int radius);

BOOL OverworldWildSpawnGuard_IsSurfBehavior(u8 behavior);

#endif
