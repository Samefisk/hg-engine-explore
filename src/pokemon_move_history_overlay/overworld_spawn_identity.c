/* Wild-owned presentation lifecycle, hosted in the explicit resident tail.
 * Stock saves contain map objects but not dynamic encounter ownership.
 * Remove only unowned script-2074 remnants before a new slot is allocated.
 */
#include "../../include/overworld_spawn_identity.h"
#include "../../include/map_events_internal.h"

#define OW_WILD_OBJECT_ID_START 0xE0
#define OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT 2074

typedef struct OverworldWildSpawnRuntimePrefix {
    OVERWORLD_WILD_CUSTOM_JUMP_RUNTIME_PREFIX_FIELDS;
} OverworldWildSpawnRuntimePrefix;

int __attribute__((noinline, used, section(".overworld_spawn_identity")))
OverworldWildSpawnIdentity_PrepareSlot(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildPresentationState *presentation)
{
    MapObjectMan *manager;
    const OverworldWildSpawnRuntimePrefix *runtime;
    int deleted = 0;
    int i;
    int j;

    if (state == NULL
        || fieldSystem == NULL
        || presentation == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || state->movementRuntimeState == NULL
        || fieldSystem->location == NULL
        || fieldSystem->mapObjectMan == NULL
        || state->mapId != fieldSystem->location->mapId
        || state->spawns[slot].active
        || state->spawns[slot].object != NULL
        || state->pendingSlot == slot
        || state->movementQueuedBattleSlot == slot
        || (presentation->managerRestoreMask & (1u << slot)) != 0) {
        return -1;
    }

    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    if (manager != state->mapObjectMan
        || manager->fsys != fieldSystem
        || manager->objects == NULL
        || manager->objects != state->mapObjects
        || manager->object_count == 0
        || manager->object_count > 64) {
        return -1;
    }
    runtime = (const OverworldWildSpawnRuntimePrefix *)state->movementRuntimeState;

    /* Validate every match before deleting any orphan. Native ID lookup does
     * not filter script or map; never delete a foreign object or live binding.
     * Flag25 does not make a saved private object owned, so clear it too. */
    for (i = 0; i < (int)manager->object_count; i++) {
        LocalMapObject *candidate = &manager->objects[i];

        if ((candidate->flags & MAPOBJECTFLAG_ACTIVE) == 0
            || (u32)candidate->id != OW_WILD_OBJECT_ID_START + (u32)slot) {
            continue;
        }
        if (candidate->scriptId != OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT) {
            return -1;
        }
        for (j = 0; j < OW_WILD_MAX_SPAWNS; j++) {
            if (state->spawns[j].object == candidate
                || (state->spawns[j].active
                    && state->spawns[j].objectId == candidate->id)
                || state->movementMankeyTreeTopProxyObjects[j] == candidate
                || state->movementTeleportFlickerObjects[j] == candidate
                || runtime->movementEmotePartnerPrepObjects[j] == candidate) {
                return -1;
            }
        }
    }
    for (i = 0; i < (int)manager->object_count; i++) {
        LocalMapObject *candidate = &manager->objects[i];

        if ((candidate->flags & MAPOBJECTFLAG_ACTIVE) != 0
            && (u32)candidate->id == OW_WILD_OBJECT_ID_START + (u32)slot) {
            DeleteMapObject(candidate);
            deleted++;
        }
    }
    return deleted;
}
