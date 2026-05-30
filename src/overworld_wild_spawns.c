#include "../include/overworld_wild_spawns.h"

#include "../include/config.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

#include "../include/constants/maps.h"
#include "../include/constants/species.h"
#include "../include/map_events_internal.h"
#include "../include/rtc.h"
#include "../include/script.h"

#define OW_WILD_MAX_SPAWNS 3

typedef struct OverworldWildSpawn {
    LocalMapObject *object;
    u16 species;
    u8 form;
    u8 level;
    u8 active;
} OverworldWildSpawn;

static OverworldWildSpawn sOverworldWildSpawns[OW_WILD_MAX_SPAWNS];
static int sOverworldWildSpawnMap = MAP_NOTHING;
static u8 sOverworldWildJustSpawned;

static const u16 sRoute29MorningSpecies[12] = {
    SPECIES_SENTRET, SPECIES_PIDGEY,  SPECIES_SENTRET, SPECIES_PIDGEY,
    SPECIES_DELIBIRD, SPECIES_PIDGEY, SPECIES_PICHU,   SPECIES_PIDGEY,
    SPECIES_RATTATA, SPECIES_PIDGEY,  SPECIES_RATTATA, SPECIES_PIDGEY,
};

static const u16 sRoute29DaySpecies[12] = {
    SPECIES_SENTRET, SPECIES_PIDGEY, SPECIES_SENTRET,   SPECIES_PIDGEY,
    SPECIES_PIDGEY,  SPECIES_PIDGEY, SPECIES_PICHU,     SPECIES_IGGLYBUFF,
    SPECIES_RATTATA, SPECIES_PIDGEY, SPECIES_RATTATA,   SPECIES_PIDGEY,
};

static const u16 sRoute29NightSpecies[12] = {
    SPECIES_HOOTHOOT, SPECIES_HOOTHOOT, SPECIES_SPINARAK, SPECIES_SPINARAK,
    SPECIES_SPINARAK, SPECIES_RATTATA,  SPECIES_SENTRET,  SPECIES_RATTATA,
    SPECIES_RATTATA,  SPECIES_RATTATA,  SPECIES_RATTATA,  SPECIES_SENTRET,
};

static const u8 sRoute29WalkLevels[12] = {
    2, 3, 2, 3, 3, 3, 2, 2, 4, 4, 4, 4,
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

static const u16 *OverworldWildSpawns_GetRoute29SpeciesTable(void)
{
    switch (GF_RTC_GetTimeOfDayWildParam()) {
    case TIMEOFDAY_WILD_MORN:
        return sRoute29MorningSpecies;
    case TIMEOFDAY_WILD_NITE:
        return sRoute29NightSpecies;
    case TIMEOFDAY_WILD_DAY:
    default:
        return sRoute29DaySpecies;
    }
}

static void OverworldWildSpawns_RollRoute29Encounter(u16 *species, u8 *form, u8 *level)
{
    u32 slot = gf_rand() % 12;
    const u16 *speciesTable = OverworldWildSpawns_GetRoute29SpeciesTable();

    *species = speciesTable[slot] & 0x7FF;
    *form = (speciesTable[slot] >> 11) & 0x1F;
    *level = sRoute29WalkLevels[slot];
}

static BOOL OverworldWildSpawns_SpawnOne(FieldSystem *fieldSystem, int slot)
{
    int x;
    int y;
    u16 species;
    u8 form;
    u8 level;
    LocalMapObject *object;

    OverworldWildSpawns_RollRoute29Encounter(&species, &form, &level);

    x = GetPlayerXCoord(fieldSystem->playerAvatar) + sSpawnOffsets[slot][0];
    y = GetPlayerYCoord(fieldSystem->playerAvatar) + sSpawnOffsets[slot][1];

    object = CreateSpecialFieldObject(
        fieldSystem->mapObjectMan,
        x,
        y,
        1,
        FollowingPokemon_GetSpriteID(species, form, 0),
        0,
        fieldSystem->location->mapId);
    if (object == NULL) {
        return FALSE;
    }

    MapObject_SetParam(object, species, 0);
    MapObject_SetParam(object, form, 1);
    MapObject_SetParam(object, level, 2);

    sOverworldWildSpawns[slot].object = object;
    sOverworldWildSpawns[slot].species = species;
    sOverworldWildSpawns[slot].form = form;
    sOverworldWildSpawns[slot].level = level;
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

static u16 OverworldWildSpawns_GetRoute29BattleScript(u16 species, u8 level)
{
    switch (species) {
    case SPECIES_PIDGEY:
        if (level == 2) {
            return 2075;
        }
        if (level == 4) {
            return 2077;
        }
        return 2076;

    case SPECIES_RATTATA:
        if (level == 2) {
            return 2078;
        }
        if (level == 3) {
            return 2079;
        }
        return 2080;

    case SPECIES_SENTRET:
        if (level == 4) {
            return 2082;
        }
        return 2081;

    case SPECIES_HOOTHOOT:
        if (level == 3) {
            return 2084;
        }
        return 2083;

    case SPECIES_SPINARAK:
        if (level == 2) {
            return 2085;
        }
        return 2086;

    case SPECIES_PICHU:
        return 2087;

    case SPECIES_IGGLYBUFF:
        return 2088;

    case SPECIES_DELIBIRD:
        return 2089;

    default:
        return OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT;
    }
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
            u16 script = OverworldWildSpawns_GetRoute29BattleScript(
                sOverworldWildSpawns[i].species,
                sOverworldWildSpawns[i].level);

            DeleteMapObject(sOverworldWildSpawns[i].object);
            sOverworldWildSpawns[i].active = FALSE;
            sOverworldWildSpawns[i].object = NULL;

            EventSet_Script(fieldSystem, script, NULL);
            return TRUE;
        }
    }

    return FALSE;
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
