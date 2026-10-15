#include "../../include/overworld_throw_binding_native.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_spawn_spatial.h"

__asm__(
    ".global OverworldBehaviorConditionAdapter_BuildFrame\n"
    ".thumb_func\n"
    ".thumb_set OverworldBehaviorConditionAdapter_BuildFrame, 0x023B6930\n"
    ".global OverworldThrowBinding_PlayerX\n"
    ".thumb_func\n"
    ".thumb_set OverworldThrowBinding_PlayerX, 0x0205C67C\n"
    ".global OverworldThrowBinding_PlayerY\n"
    ".thumb_func\n"
    ".thumb_set OverworldThrowBinding_PlayerY, 0x0205C688\n");
extern int OverworldThrowBinding_PlayerX(FIELD_PLAYER_AVATAR *);
extern int OverworldThrowBinding_PlayerY(FIELD_PLAYER_AVATAR *);

static BOOL __attribute__((noinline, section(".overworld_throw_binding_refresh.tail")))
OverworldThrowBinding_CurrentSpawn(
    FieldSystem *field, const OverworldWildSpawn *spawn)
{
    if (field->location == NULL || !spawn->active
        || spawn->mapId != field->location->mapId
        || !OverworldSpawnSpatial_IsCurrentMapObject(field, spawn->object)) {
        return FALSE;
    }
    return (spawn->object->flags & MAPOBJECTFLAG_ACTIVE) != 0
        && spawn->object->id == spawn->objectId
        && spawn->object->scriptId == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT;
}

const OverworldQueryCodeAddonEntry *
    __attribute__((noinline, section(".overworld_throw_binding_refresh")))
OverworldThrowBinding_Refresh(
    OverworldWildSpawnState *state,
    OverworldWildBehaviorConditionRuntime *conditions,
    const OverworldQueryCodeAddonServiceEntry *service,
    u8 slot)
{
    OverworldQueryCodeAddonOwner owner;
    const OverworldQueryCodeAddonEntry *entry;
    FieldSystem *field = state->movementFieldSystem;
    OverworldBehaviorConditionWorldView *world = &conditions->frame.world;

    owner.fieldIdentity = (u32)field;
    owner.fieldEpoch = conditions->actors[slot].subject.fieldEpoch;
    owner.mapGeneration = state->mapGeneration;
    entry = service->acquire(&owner);
    if (entry == NULL || field == NULL || field != gFieldSysPtr
        || !OverworldBehaviorConditionAdapter_BuildFrame(
            state, field, conditions, NULL, OverworldThrowBinding_CurrentSpawn)
        || (conditions->frame.actorSlotMask & (1u << slot)) == 0) {
        return NULL;
    }
    /* Use the stock Player owner, just as PopulateVisibility does. A read
     * does not need visibility rays or a new condition decision. */
    world->playerValid = field->playerAvatar != NULL;
    if (world->playerValid) {
        world->playerX = (s16)OverworldThrowBinding_PlayerX(field->playerAvatar);
        world->playerY = (s16)OverworldThrowBinding_PlayerY(field->playerAvatar);
    }
    return entry;
}
