#include "../../include/overworld_spawn_guard.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/map_events_internal.h"

/* The six-byte saved-shiny value copy uses the resident Thumb memcpy bridge.
 * A bare linker address would generate an ARM-mode veneer into Thumb code. */
__asm__(".thumb\n.global memcpy\n.thumb_func\n.thumb_set memcpy, 0x023DEEBE\n");

BOOL __attribute__((noinline, used, section(".overworld_spawn_guard_read")))
OverworldWildSpawnGuard_Read(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const OverworldWildPreparedSpawn *prepared,
    int slot,
    OverworldWildQueuedSpawnGuard *guard,
    OverworldWildSpawnGuardSurfaceQueryFunc querySurface)
{
    memset(guard, 0, sizeof(*guard));
    guard->context = OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext();
    guard->manager = fieldSystem->mapObjectMan;
    guard->mapId = fieldSystem->location->mapId;
    guard->generation = state->spawns[slot].encounterGeneration;
    guard->active = state->spawns[slot].active;
    guard->targetBehavior = GetMetatileBehaviorAt(fieldSystem,
        prepared->startup.targetX, prepared->startup.targetY);
    guard->originBehavior = GetMetatileBehaviorAt(fieldSystem,
        prepared->position.startX, prepared->position.startY);
    if (guard->active || guard->targetBehavior == 0xFF
        || guard->originBehavior == 0xFF
        || prepared->savedShinySlot >= OW_WILD_MAX_SAVED_SHINIES) {
        return FALSE;
    }
    guard->hasSurface = querySurface(fieldSystem,
        prepared->startup.targetX, prepared->startup.targetY, &guard->surface);
    if (prepared->savedShinySlot >= 0) {
        guard->savedShiny = state->savedShinies[prepared->savedShinySlot];
    }
    if ((prepared->behaviorResolution.profile.spawnDestinationMask
            & (OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER
                | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT)) != 0) {
        guard->playerX = GetPlayerXCoord(fieldSystem->playerAvatar);
        guard->playerY = GetPlayerYCoord(fieldSystem->playerAvatar);
        guard->playerFacing = fieldSystem->playerAvatar->mapObject->curFacing;
    }
    return TRUE;
}

static int OverworldWildSpawnGuard_Abs(int value)
{
    return value < 0 ? -value : value;
}

BOOL __attribute__((noinline, used, section(".overworld_spawn_guard_surf")))
OverworldWildSpawnGuard_IsSurfBehavior(u8 behavior)
{
    return behavior == 16 || behavior == 18 || behavior == 21 || behavior == 42;
}

static int OverworldWildSpawnGuard_Max(int a, int b)
{
    return a > b ? a : b;
}

BOOL __attribute__((noinline, used, section(".overworld_spawn_guard_near")))
OverworldWildSpawnGuard_IsNearActiveSpawn(
    const OverworldWildSpawnState *state,
    int x,
    int y,
    int radius)
{
    int i;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (state->spawns[i].active && state->spawns[i].object != NULL) {
            int spawnX = state->spawns[i].object->xCurr;
            int spawnY = state->spawns[i].object->yCurr;
            int dx = OverworldWildSpawnGuard_Abs(x - spawnX);
            int dy = OverworldWildSpawnGuard_Abs(y - spawnY);

            if (OverworldWildSpawnGuard_Max(dx, dy) <= radius) {
                return TRUE;
            }
            if (state->movementSpawnRunActive[i]) {
                dx = OverworldWildSpawnGuard_Abs(
                    x - state->movementSpawnRunTargetX[i]);
                dy = OverworldWildSpawnGuard_Abs(
                    y - state->movementSpawnRunTargetY[i]);
                if (OverworldWildSpawnGuard_Max(dx, dy) <= radius) {
                    return TRUE;
                }
            }
        }
    }
    return FALSE;
}
