#include "../include/overworld_wild_spawns.h"

#include "../include/config.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

#include "../include/constants/file.h"
#include "../include/constants/maps.h"
#include "../include/constants/species.h"
#include "../include/map_events_internal.h"
#include "../include/rtc.h"
#include "../include/script.h"

#define OW_WILD_MAX_SPAWNS 4
#define OW_WILD_GRASS_SLOTS 12
#define OW_WILD_SPECIES_MASK 0x7FF
#define OW_WILD_FORM_SHIFT 11
#define OW_WILD_SPAWN_MIN_DISTANCE 4
#define OW_WILD_SPAWN_MAX_DISTANCE 8
#define OW_WILD_DESPAWN_DISTANCE 14
#define OW_WILD_SPAWN_ATTEMPTS 48
#define OW_WILD_REFILL_COOLDOWN_STEPS 2
#define OW_WILD_TILE_ENCOUNTER_GRASS 2
#define OW_WILD_TILE_LONG_GRASS 3
#define OW_WILD_MOVE_WANDER_ALL_DIRECTIONS 3

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

typedef struct OverworldWildSpawnPosition {
    int x;
    int y;
} OverworldWildSpawnPosition;

typedef struct OverworldWildEncounterArea {
    u16 mapId;
    u16 encounterDataId;
} OverworldWildEncounterArea;

static OverworldWildSpawn sOverworldWildSpawns[OW_WILD_MAX_SPAWNS];
static int sOverworldWildSpawnMap = MAP_NOTHING;
static u8 sOverworldWildJustSpawned;
static u8 sOverworldWildSpawnCooldown;
static u16 sOverworldWildPendingSpecies;
static u8 sOverworldWildPendingLevel;
static s8 sOverworldWildPendingSlot = -1;

static const u8 sGrassSlotWeights[OW_WILD_GRASS_SLOTS] = {
    20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1,
};

static const OverworldWildEncounterArea sOverworldWildEncounterAreas[] = {
    {MAP_T20, 0}, {MAP_R29, 1}, {MAP_T21, 2}, {MAP_R30, 3},
    {MAP_R31, 4}, {MAP_T22, 5}, {MAP_D15R0102, 6}, {MAP_D15R0103, 7},
    {MAP_R32, 8}, {MAP_D24R0101, 9}, {MAP_D24, 10}, {MAP_D24R0201, 10},
    {MAP_D24R0202, 11}, {MAP_D24R0203, 12}, {MAP_D24R0204, 13},
    {MAP_D25R0101, 14}, {MAP_D25R0102, 15}, {MAP_D25R0103, 16},
    {MAP_R33, 17}, {MAP_D26R0101, 18}, {MAP_D26R0102, 18},
    {MAP_D26R0103, 19}, {MAP_D36R0101, 20}, {MAP_R34, 21},
    {MAP_R35, 22}, {MAP_D22R0101, 23}, {MAP_D22R0102, 24},
    {MAP_D22R0103, 24}, {MAP_R36, 25}, {MAP_R37, 26}, {MAP_T27, 27},
    {MAP_D18R0101, 28}, {MAP_D18R0102, 29}, {MAP_D17R0102, 30},
    {MAP_D17R0103, 31}, {MAP_D17R0104, 32}, {MAP_D17R0105, 33},
    {MAP_D17R0106, 34}, {MAP_D17R0107, 35}, {MAP_D17R0108, 36},
    {MAP_D17R0109, 37}, {MAP_R38, 38}, {MAP_R39, 39}, {MAP_T26, 40},
    {MAP_W40, 41}, {MAP_W41, 42}, {MAP_D40R0101, 43},
    {MAP_D40R0102, 44}, {MAP_D40R0104, 46}, {MAP_D40R0107, 48},
    {MAP_T24, 51}, {MAP_R42, 52}, {MAP_D38R0101, 53},
    {MAP_D38R0102, 54}, {MAP_D38R0103, 55}, {MAP_D38R0104, 56},
    {MAP_R43, 57}, {MAP_T29, 58}, {MAP_R44, 59}, {MAP_D39R0101, 60},
    {MAP_D39R0102, 61}, {MAP_D39R0103, 62}, {MAP_D39R0104, 63},
    {MAP_T30, 65}, {MAP_D44R0101, 66}, {MAP_D44R0102, 66},
    {MAP_R45, 67}, {MAP_R46, 68}, {MAP_D42R0102, 69},
    {MAP_D42R0101, 70}, {MAP_R47, 71}, {MAP_D11R0101, 74},
    {MAP_D11R0102, 75}, {MAP_D11R0103, 76}, {MAP_D11R0104, 77},
    {MAP_D11R0105, 78}, {MAP_D41R0105, 79}, {MAP_D41R0107, 80},
    {MAP_D41R0108, 81}, {MAP_D50R0101, 83}, {MAP_D17R0112, 84},
    {MAP_T31, 85}, {MAP_D41R0101, 86}, {MAP_D41R0102, 87},
    {MAP_D41R0103, 87}, {MAP_D41R0104, 88}, {MAP_SAF01, 91},
    {MAP_SAF02, 91}, {MAP_SAF03, 91}, {MAP_SAF04, 91}, {MAP_SAF05, 91},
    {MAP_SAF06, 91}, {MAP_SAF07, 91}, {MAP_SAF08, 91}, {MAP_SAF09, 91},
    {MAP_SAF10, 91}, {MAP_SAF11, 91}, {MAP_SAF12, 91}, {MAP_SAF13, 91},
    {MAP_SAF14, 91}, {MAP_R12, 92}, {MAP_W19, 93}, {MAP_W20, 94},
    {MAP_T01, 95}, {MAP_T02, 96}, {MAP_T04, 97}, {MAP_T06, 98},
    {MAP_T07, 99}, {MAP_T08, 100}, {MAP_T09, 101}, {MAP_R48, 102},
    {MAP_R26, 103}, {MAP_R27, 104}, {MAP_R28, 105}, {MAP_D02R0101, 106},
    {MAP_D02R0102, 107}, {MAP_D05R0101, 108}, {MAP_D05R0102, 109},
    {MAP_D43R0101, 110}, {MAP_R01, 111}, {MAP_R02, 112},
    {MAP_R03, 113}, {MAP_R04, 114}, {MAP_R05, 115}, {MAP_R06, 116},
    {MAP_R07, 117}, {MAP_R08, 118}, {MAP_R09, 119}, {MAP_R10, 120},
    {MAP_R11, 121}, {MAP_R13, 122}, {MAP_R14, 123}, {MAP_R15, 124},
    {MAP_R16, 125}, {MAP_R17, 126}, {MAP_R18, 127}, {MAP_W21, 128},
    {MAP_R22, 129}, {MAP_R24, 130}, {MAP_R25, 131}, {MAP_D45R0101, 132},
    {MAP_D45R0102, 132}, {MAP_D01R0101, 133}, {MAP_D43R0102, 134},
    {MAP_D43R0103, 135}, {MAP_R02R0101, 136}, {MAP_D46R0101, 137},
    {MAP_D03R0101, 139}, {MAP_D03R0102, 140}, {MAP_D03R0103, 141},
};

static int OverworldWildSpawns_Abs(int value)
{
    return value < 0 ? -value : value;
}

static int OverworldWildSpawns_Max(int a, int b)
{
    return a > b ? a : b;
}

static int OverworldWildSpawns_DistanceFromPlayer(FieldSystem *fieldSystem, int x, int y)
{
    int dx = x - GetPlayerXCoord(fieldSystem->playerAvatar);
    int dy = y - GetPlayerYCoord(fieldSystem->playerAvatar);

    return OverworldWildSpawns_Max(OverworldWildSpawns_Abs(dx), OverworldWildSpawns_Abs(dy));
}

static void OverworldWildSpawns_ClearSlot(int slot, BOOL deleteObject)
{
    if (deleteObject && sOverworldWildSpawns[slot].active && sOverworldWildSpawns[slot].object != NULL) {
        DeleteMapObject(sOverworldWildSpawns[slot].object);
    }

    sOverworldWildSpawns[slot].object = NULL;
    sOverworldWildSpawns[slot].species = SPECIES_NONE;
    sOverworldWildSpawns[slot].form = 0;
    sOverworldWildSpawns[slot].level = 0;
    sOverworldWildSpawns[slot].active = FALSE;
}

static void OverworldWildSpawns_Clear(BOOL deleteObjects)
{
    int i;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        OverworldWildSpawns_ClearSlot(i, deleteObjects);
    }

    sOverworldWildJustSpawned = FALSE;
    sOverworldWildSpawnCooldown = 0;
    sOverworldWildPendingSlot = -1;
}

static BOOL OverworldWildSpawns_TryGetEncounterDataId(FieldSystem *fieldSystem, int *encounterDataId)
{
    u32 i;

    if (fieldSystem == NULL || fieldSystem->location == NULL) {
        return FALSE;
    }

    for (i = 0; i < sizeof(sOverworldWildEncounterAreas) / sizeof(sOverworldWildEncounterAreas[0]); i++) {
        if (sOverworldWildEncounterAreas[i].mapId == fieldSystem->location->mapId) {
            *encounterDataId = sOverworldWildEncounterAreas[i].encounterDataId;
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_IsEnabledMap(FieldSystem *fieldSystem)
{
    int encounterDataId;

    return fieldSystem != NULL
        && fieldSystem->location != NULL
        && fieldSystem->mapObjectMan != NULL
        && fieldSystem->playerAvatar != NULL
        && OverworldWildSpawns_TryGetEncounterDataId(fieldSystem, &encounterDataId);
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

static BOOL OverworldWildSpawns_IsGrassTile(FieldSystem *fieldSystem, int x, int y)
{
    u8 behavior;

    if (x < 0 || y < 0) {
        return FALSE;
    }

    behavior = GetMetatileBehaviorAt(fieldSystem, x, y);
    return behavior == OW_WILD_TILE_ENCOUNTER_GRASS || behavior == OW_WILD_TILE_LONG_GRASS;
}

static BOOL OverworldWildSpawns_IsTileOccupiedByObject(FieldSystem *fieldSystem, int x, int y)
{
    u32 i;
    MapObjectMan *mapObjectMan = (MapObjectMan *)fieldSystem->mapObjectMan;
    LocalMapObject *objects;

    if (x == GetPlayerXCoord(fieldSystem->playerAvatar) && y == GetPlayerYCoord(fieldSystem->playerAvatar)) {
        return TRUE;
    }

    if (mapObjectMan == NULL || mapObjectMan->objects == NULL) {
        return FALSE;
    }

    objects = mapObjectMan->objects;
    for (i = 0; i < mapObjectMan->object_count; i++) {
        LocalMapObject *object = &objects[i];

        if ((object->flags & MAPOBJECTFLAG_ACTIVE) != 0
            && (int)MapObject_GetCurrentX(object) == x
            && (int)MapObject_GetCurrentY(object) == y) {
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_TryPickSpawnPosition(FieldSystem *fieldSystem, OverworldWildSpawnPosition *position)
{
    int playerX = GetPlayerXCoord(fieldSystem->playerAvatar);
    int playerY = GetPlayerYCoord(fieldSystem->playerAvatar);
    int attempt;

    for (attempt = 0; attempt < OW_WILD_SPAWN_ATTEMPTS; attempt++) {
        int dx = (int)(gf_rand() % (OW_WILD_SPAWN_MAX_DISTANCE * 2 + 1)) - OW_WILD_SPAWN_MAX_DISTANCE;
        int dy = (int)(gf_rand() % (OW_WILD_SPAWN_MAX_DISTANCE * 2 + 1)) - OW_WILD_SPAWN_MAX_DISTANCE;
        int x = playerX + dx;
        int y = playerY + dy;
        int distance = OverworldWildSpawns_Max(OverworldWildSpawns_Abs(dx), OverworldWildSpawns_Abs(dy));

        if (distance < OW_WILD_SPAWN_MIN_DISTANCE || distance > OW_WILD_SPAWN_MAX_DISTANCE) {
            continue;
        }
        if (!OverworldWildSpawns_IsGrassTile(fieldSystem, x, y)) {
            continue;
        }
        if (OverworldWildSpawns_IsTileOccupiedByObject(fieldSystem, x, y)) {
            continue;
        }

        position->x = x;
        position->y = y;
        return TRUE;
    }

    return FALSE;
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

static void OverworldWildSpawns_ApplyMovementRange(LocalMapObject *object)
{
    MapObject_SetXRange(object, 2);
    MapObject_SetYRange(object, 2);
}

static BOOL OverworldWildSpawns_SpawnOne(FieldSystem *fieldSystem, int slot)
{
    OverworldWildRolledEncounter encounter;
    OverworldWildSpawnPosition position;
    LocalMapObject *object;

    if (!OverworldWildSpawns_TryPickSpawnPosition(fieldSystem, &position)) {
        return FALSE;
    }
    if (!OverworldWildSpawns_TryRollGrassEncounter(fieldSystem, &encounter)) {
        return FALSE;
    }

    object = CreateSpecialFieldObject(
        fieldSystem->mapObjectMan,
        position.x,
        position.y,
        1,
        FollowingPokemon_GetSpriteID(encounter.species, encounter.form, 0),
        OW_WILD_MOVE_WANDER_ALL_DIRECTIONS,
        fieldSystem->location->mapId);
    if (object == NULL) {
        return FALSE;
    }

    OverworldWildSpawns_ApplyMovementRange(object);
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

static void OverworldWildSpawns_DespawnFarMons(FieldSystem *fieldSystem)
{
    int i;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (sOverworldWildSpawns[i].active && sOverworldWildSpawns[i].object != NULL) {
            int x = MapObject_GetCurrentX(sOverworldWildSpawns[i].object);
            int y = MapObject_GetCurrentY(sOverworldWildSpawns[i].object);

            if (OverworldWildSpawns_DistanceFromPlayer(fieldSystem, x, y) > OW_WILD_DESPAWN_DISTANCE) {
                OverworldWildSpawns_ClearSlot(i, TRUE);
            }
        }
    }
}

static void OverworldWildSpawns_TryRefill(FieldSystem *fieldSystem)
{
    int i;

    if (sOverworldWildSpawnCooldown != 0) {
        sOverworldWildSpawnCooldown--;
        return;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (!sOverworldWildSpawns[i].active) {
            if (OverworldWildSpawns_SpawnOne(fieldSystem, i)) {
                sOverworldWildJustSpawned = TRUE;
                sOverworldWildSpawnCooldown = OW_WILD_REFILL_COOLDOWN_STEPS;
            }
            return;
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
            sOverworldWildPendingSlot = i;
            sOverworldWildSpawnCooldown = OW_WILD_REFILL_COOLDOWN_STEPS;

            EventSet_Script(fieldSystem, OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT, NULL);
            return TRUE;
        }
    }

    return FALSE;
}

void OverworldWildSpawns_CleanupPendingBattle(void)
{
    if (sOverworldWildPendingSlot >= 0 && sOverworldWildPendingSlot < OW_WILD_MAX_SPAWNS) {
        OverworldWildSpawns_ClearSlot(sOverworldWildPendingSlot, TRUE);
    }

    sOverworldWildPendingSlot = -1;
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
    if (!OverworldWildSpawns_IsEnabledMap(fieldSystem)) {
        if (sOverworldWildSpawnMap != MAP_NOTHING) {
            OverworldWildSpawns_Clear(FALSE);
            sOverworldWildSpawnMap = MAP_NOTHING;
        }
        return FALSE;
    }

    if (sOverworldWildSpawnMap != fieldSystem->location->mapId) {
        OverworldWildSpawns_Clear(FALSE);
        sOverworldWildSpawnMap = fieldSystem->location->mapId;
    }

    OverworldWildSpawns_DespawnFarMons(fieldSystem);
    if (OverworldWildSpawns_TryStartBattle(fieldSystem)) {
        return TRUE;
    }

    OverworldWildSpawns_TryRefill(fieldSystem);
    return FALSE;
}

#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS
