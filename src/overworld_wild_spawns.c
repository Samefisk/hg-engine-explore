#include "../include/overworld_wild_spawns.h"

#include "../include/config.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

#include "../include/constants/file.h"
#include "../include/constants/maps.h"
#include "../include/constants/species.h"
#include "../include/map_events_internal.h"
#include "../include/rtc.h"
#include "../include/script.h"

#define OW_WILD_MAX_SPAWNS 3
#define OW_WILD_GRASS_SLOTS 12
#define OW_WILD_SPECIES_MASK 0x7FF
#define OW_WILD_FORM_SHIFT 11

typedef struct OverworldWildSpawn {
    LocalMapObject *object;
    u16 species;
    u8 form;
    u8 level;
    u8 active;
} OverworldWildSpawn;

typedef struct OverworldWildGrassEncounterData {
    u8 rates[6];
    u8 padding[2];
    u8 walkLevels[OW_WILD_GRASS_SLOTS];
    u16 morningSpecies[OW_WILD_GRASS_SLOTS];
    u16 daySpecies[OW_WILD_GRASS_SLOTS];
    u16 nightSpecies[OW_WILD_GRASS_SLOTS];
} OverworldWildGrassEncounterData;

typedef struct OverworldWildRolledEncounter {
    u16 species;
    u8 form;
    u8 level;
} OverworldWildRolledEncounter;

static OverworldWildSpawn sOverworldWildSpawns[OW_WILD_MAX_SPAWNS];
static int sOverworldWildSpawnMap = MAP_NOTHING;
static u8 sOverworldWildJustSpawned;
static u16 sOverworldWildPendingSpecies;
static u8 sOverworldWildPendingLevel;

static const u8 sGrassSlotWeights[OW_WILD_GRASS_SLOTS] = {
    20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1,
};

static const s8 sSpawnOffsets[OW_WILD_MAX_SPAWNS][2] = {
    { 3,  0 },
    {-3,  1 },
    { 0,  3 },
};

static void OverworldWildSpawns_Clear(BOOL deleteObjects)
{
    int i;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (deleteObjects && sOverworldWildSpawns[i].active && sOverworldWildSpawns[i].object != NULL) {
            DeleteMapObject(sOverworldWildSpawns[i].object);
        }
        sOverworldWildSpawns[i].object = NULL;
        sOverworldWildSpawns[i].species = SPECIES_NONE;
        sOverworldWildSpawns[i].form = 0;
        sOverworldWildSpawns[i].level = 0;
        sOverworldWildSpawns[i].active = FALSE;
    }
}

static BOOL OverworldWildSpawns_IsTestMap(FieldSystem *fieldSystem)
{
    return fieldSystem != NULL
        && fieldSystem->location != NULL
        && fieldSystem->mapObjectMan != NULL
        && fieldSystem->playerAvatar != NULL
        && fieldSystem->location->mapId == OVERWORLD_WILD_SPAWNS_TEST_MAP;
}

static BOOL OverworldWildSpawns_TryGetEncounterDataId(FieldSystem *fieldSystem, int *encounterDataId)
{
    if (fieldSystem == NULL || fieldSystem->location == NULL) {
        return FALSE;
    }

    switch (fieldSystem->location->mapId) {
    case MAP_R29:
        *encounterDataId = 1;
        return TRUE;
    default:
        return FALSE;
    }
}

static const u16 *OverworldWildSpawns_GetTimeOfDaySpeciesTable(const OverworldWildGrassEncounterData *encounterData)
{
    switch (GF_RTC_GetTimeOfDayWildParam()) {
    case TIMEOFDAY_WILD_MORN:
        return encounterData->morningSpecies;
    case TIMEOFDAY_WILD_NITE:
        return encounterData->nightSpecies;
    case TIMEOFDAY_WILD_DAY:
    default:
        return encounterData->daySpecies;
    }
}

static u8 OverworldWildSpawns_RollGrassSlot(void)
{
    u32 roll = gf_rand() % 100;
    u8 slot;

    for (slot = 0; slot < OW_WILD_GRASS_SLOTS; slot++) {
        if (roll < sGrassSlotWeights[slot]) {
            return slot;
        }
        roll -= sGrassSlotWeights[slot];
    }

    return OW_WILD_GRASS_SLOTS - 1;
}

static BOOL OverworldWildSpawns_TryRollGrassEncounter(FieldSystem *fieldSystem, OverworldWildRolledEncounter *encounter)
{
    int encounterDataId;
    int attempts;
    OverworldWildGrassEncounterData encounterData;
    const u16 *speciesTable;

    if (!OverworldWildSpawns_TryGetEncounterDataId(fieldSystem, &encounterDataId)) {
        return FALSE;
    }

    ArchiveDataLoadOfs(&encounterData, ARC_ENCOUNTERS, encounterDataId, 0, sizeof(encounterData));
    speciesTable = OverworldWildSpawns_GetTimeOfDaySpeciesTable(&encounterData);

    for (attempts = 0; attempts < OW_WILD_GRASS_SLOTS; attempts++) {
        u8 slot = OverworldWildSpawns_RollGrassSlot();
        u16 encodedSpecies = speciesTable[slot];
        u16 species = encodedSpecies & OW_WILD_SPECIES_MASK;

        if (species != SPECIES_NONE && encounterData.walkLevels[slot] != 0) {
            encounter->species = species;
            encounter->form = encodedSpecies >> OW_WILD_FORM_SHIFT;
            encounter->level = encounterData.walkLevels[slot];
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_SpawnOne(FieldSystem *fieldSystem, int slot)
{
    int x;
    int y;
    OverworldWildRolledEncounter encounter;
    LocalMapObject *object;

    if (!OverworldWildSpawns_TryRollGrassEncounter(fieldSystem, &encounter)) {
        return FALSE;
    }

    x = GetPlayerXCoord(fieldSystem->playerAvatar) + sSpawnOffsets[slot][0];
    y = GetPlayerYCoord(fieldSystem->playerAvatar) + sSpawnOffsets[slot][1];

    object = CreateSpecialFieldObject(
        fieldSystem->mapObjectMan,
        x,
        y,
        1,
        FollowingPokemon_GetSpriteID(encounter.species, encounter.form, 0),
        0,
        fieldSystem->location->mapId);
    if (object == NULL) {
        return FALSE;
    }

    MapObject_SetParam(object, encounter.species, 0);
    MapObject_SetParam(object, encounter.form, 1);
    MapObject_SetParam(object, encounter.level, 2);

    sOverworldWildSpawns[slot].object = object;
    sOverworldWildSpawns[slot].species = encounter.species;
    sOverworldWildSpawns[slot].form = encounter.form;
    sOverworldWildSpawns[slot].level = encounter.level;
    sOverworldWildSpawns[slot].active = TRUE;

    return TRUE;
}

static void OverworldWildSpawns_EnsureSpawned(FieldSystem *fieldSystem)
{
    int i;

    if (sOverworldWildSpawnMap != fieldSystem->location->mapId) {
        OverworldWildSpawns_Clear(FALSE);
        sOverworldWildSpawnMap = fieldSystem->location->mapId;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (!sOverworldWildSpawns[i].active) {
            if (OverworldWildSpawns_SpawnOne(fieldSystem, i)) {
                sOverworldWildJustSpawned = TRUE;
            }
        }
    }
}

static BOOL OverworldWildSpawns_IsTouchingPlayer(FieldSystem *fieldSystem, const OverworldWildSpawn *spawn)
{
    int dx;
    int dy;

    if (!spawn->active || spawn->object == NULL) {
        return FALSE;
    }

    dx = (int)MapObject_GetCurrentX(spawn->object) - GetPlayerXCoord(fieldSystem->playerAvatar);
    dy = (int)MapObject_GetCurrentY(spawn->object) - GetPlayerYCoord(fieldSystem->playerAvatar);

    if (dx < 0) {
        dx = -dx;
    }
    if (dy < 0) {
        dy = -dy;
    }

    return (dx + dy) <= 1;
}

static BOOL OverworldWildSpawns_TryStartBattle(FieldSystem *fieldSystem)
{
    int i;

    if (sOverworldWildJustSpawned) {
        sOverworldWildJustSpawned = FALSE;
        return FALSE;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (OverworldWildSpawns_IsTouchingPlayer(fieldSystem, &sOverworldWildSpawns[i])) {
            sOverworldWildPendingSpecies = sOverworldWildSpawns[i].species | (sOverworldWildSpawns[i].form << 11);
            sOverworldWildPendingLevel = sOverworldWildSpawns[i].level;

            DeleteMapObject(sOverworldWildSpawns[i].object);
            sOverworldWildSpawns[i].active = FALSE;
            sOverworldWildSpawns[i].object = NULL;

            EventSet_Script(fieldSystem, OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT, NULL);
            return TRUE;
        }
    }

    return FALSE;
}

BOOL OverworldWildSpawns_PopPendingBattle(u16 *encodedSpecies, u8 *level)
{
    if (sOverworldWildPendingSpecies == SPECIES_NONE || sOverworldWildPendingLevel == 0) {
        return FALSE;
    }

    *encodedSpecies = sOverworldWildPendingSpecies;
    *level = sOverworldWildPendingLevel;

    sOverworldWildPendingSpecies = SPECIES_NONE;
    sOverworldWildPendingLevel = 0;

    return TRUE;
}

BOOL OverworldWildSpawns_OnPlayerStep(FieldSystem *fieldSystem)
{
    if (!OverworldWildSpawns_IsTestMap(fieldSystem)) {
        if (sOverworldWildSpawnMap != MAP_NOTHING) {
            OverworldWildSpawns_Clear(FALSE);
            sOverworldWildSpawnMap = MAP_NOTHING;
        }
        return FALSE;
    }

    OverworldWildSpawns_EnsureSpawned(fieldSystem);
    return OverworldWildSpawns_TryStartBattle(fieldSystem);
}

#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS
