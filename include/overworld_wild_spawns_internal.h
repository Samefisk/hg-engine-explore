#ifndef OVERWORLD_WILD_SPAWNS_INTERNAL_H
#define OVERWORLD_WILD_SPAWNS_INTERNAL_H

#include "overworld_wild_spawns.h"
#include "constants/maps.h"

#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY_ADDR 0x023CD000

#define OW_WILD_GRASS_MAX_SPAWNS 3
#define OW_WILD_SURF_MAX_SPAWNS 3
#define OW_WILD_HEADBUTT_MAX_SPAWNS 2
#define OW_WILD_FISH_MAX_SPAWNS 2
#define OW_WILD_HEADBUTT_SLOT_START (OW_WILD_GRASS_MAX_SPAWNS + OW_WILD_SURF_MAX_SPAWNS)
#define OW_WILD_FISH_SLOT_START (OW_WILD_HEADBUTT_SLOT_START + OW_WILD_HEADBUTT_MAX_SPAWNS)
#define OW_WILD_MAX_SPAWNS (OW_WILD_GRASS_MAX_SPAWNS + OW_WILD_SURF_MAX_SPAWNS + OW_WILD_HEADBUTT_MAX_SPAWNS + OW_WILD_FISH_MAX_SPAWNS)
#define OW_WILD_SPECIES_MASK 0x7FF
#define OW_WILD_FORM_SHIFT 11

typedef struct OverworldWildSpawn {
    LocalMapObject *object;
    u16 species;
    u8 form;
    u8 level;
    u8 shiny;
    u8 active;
} OverworldWildSpawn;

typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[OW_WILD_MAX_SPAWNS];
    int mapId;
    void *mapObjectMan;
    void *mapObjects;
    u8 justSpawned;
    u8 spawnCooldown;
    u8 headbuttSpawnCooldown;
    u8 fishingSpawnCooldown;
    u8 ambientCryCooldown;
    u8 battleGraceSteps;
    u16 pendingSpecies;
    u8 pendingLevel;
    u8 pendingShiny;
    s8 pendingSlot;
} OverworldWildSpawnState;

typedef struct OverworldWildSpawnsOverlayEntry {
    BOOL (*onPlayerStep)(FieldSystem *fieldSystem, OverworldWildSpawnState *state);
    void (*cleanupPendingBattle)(OverworldWildSpawnState *state, u16 battleResult);
} OverworldWildSpawnsOverlayEntry;

#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY ((const OverworldWildSpawnsOverlayEntry *)OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY_ADDR)

#endif // OVERWORLD_WILD_SPAWNS_INTERNAL_H
