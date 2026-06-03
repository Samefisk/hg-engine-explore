#include "../../include/overworld_wild_spawns_internal.h"

#include "../../include/config.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

#include "../../include/constants/file.h"
#include "../../include/constants/sndseq.h"
#include "../../include/constants/species.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_wild_movement.h"
#include "../../include/rtc.h"
#include "../../include/script.h"
#include "../../include/sound.h"

#define OW_WILD_GRASS_SLOTS 12
#define OW_WILD_SOUND_SLOTS 2
#define OW_WILD_SURF_SLOTS 5
#define OW_WILD_ROCK_SMASH_SLOTS 2
#define OW_WILD_FISH_SLOTS 5
#define OW_WILD_HEADBUTT_NORMAL_SLOTS 12
#define OW_WILD_HEADBUTT_SPECIAL_SLOTS 6
#define OW_WILD_HEADBUTT_COORDS_PER_TREE 6
#define OW_WILD_HEADBUTT_NORMAL_TREE 0
#define OW_WILD_HEADBUTT_SPECIAL_TREE 1
#define OW_WILD_HEADBUTT_EMPTY_COORD -1
#define OW_WILD_HEADBUTT_SPAWN_CHANCE_PERCENT 10
#define OW_WILD_HEADBUTT_REFILL_ATTEMPT_COOLDOWN 10
#define OW_WILD_FISHING_SPAWN_CHANCE_PERCENT 20
#define OW_WILD_FISHING_REFILL_ATTEMPT_COOLDOWN 4
#define OW_WILD_RANDOM_TIME_TABLE_CHANCE_PERCENT 20
#define OW_WILD_SPAWN_MIN_DISTANCE 4
#define OW_WILD_SPAWN_MAX_DISTANCE 8
#define OW_WILD_DESPAWN_DISTANCE 14
#define OW_WILD_SPAWN_ATTEMPTS 48
#define OW_WILD_SPAWN_MIN_MON_DISTANCE 3
#define OW_WILD_REFILL_COOLDOWN_STEPS 6
#define OW_WILD_AMBIENT_CRY_MIN_COOLDOWN_STEPS 48
#define OW_WILD_AMBIENT_CRY_RANDOM_COOLDOWN_STEPS 96
#define OW_WILD_AMBIENT_CRY_MAX_COOLDOWN_TICK 4
#define OW_WILD_OBJECT_ID_START 0xE0
#define OW_WILD_SHINY_ODDS 8192
#define OW_WILD_FLEE_GRACE_STEPS 3
#define OW_WILD_BATTLE_RESULT_PLAYER_FLED 0x5
#define OW_WILD_BATTLE_RESULT_TRY_FLEE 0x80
#define OW_WILD_TILE_ENCOUNTER_GRASS 2
#define OW_WILD_TILE_LONG_GRASS 3
#define OW_WILD_TILE_HEADBUTT 15
#define OW_WILD_STEP_DIAGNOSTIC_ENTRY_ONLY 0
#define OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY 1
#define OW_WILD_UPDATE_DIAGNOSTIC_READ_ONLY 0
#define OW_WILD_UPDATE_DIAGNOSTIC_STATE_READ_ONLY 0
#define OW_WILD_UPDATE_DIAGNOSTIC_SETTER_ONLY 0
#define OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR 1
// Param 2 mirrors the follower palette metadata without switching to follower rendering.
#define OW_WILD_PAL_PARAM_SHINY 1
#define OW_WILD_PAL_PARAM_ENABLE 2

typedef enum OverworldWildSpawnTerrain {
    OW_WILD_SPAWN_TERRAIN_LAND,
    OW_WILD_SPAWN_TERRAIN_SURF,
    OW_WILD_SPAWN_TERRAIN_HEADBUTT,
    OW_WILD_SPAWN_TERRAIN_FISHING,
} OverworldWildSpawnTerrain;

typedef enum OverworldWildFishingRodTable {
    OW_WILD_FISHING_ROD_OLD,
    OW_WILD_FISHING_ROD_GOOD,
    OW_WILD_FISHING_ROD_SUPER,
} OverworldWildFishingRodTable;

typedef struct OverworldWildLandEncounterData {
    u8 levels[OW_WILD_GRASS_SLOTS];
    u16 morningSpecies[OW_WILD_GRASS_SLOTS];
    u16 daySpecies[OW_WILD_GRASS_SLOTS];
    u16 nightSpecies[OW_WILD_GRASS_SLOTS];
} OverworldWildLandEncounterData;

typedef struct OverworldWildEncounterDataSlot {
    u8 minLevel;
    u8 maxLevel;
    u16 species;
} OverworldWildEncounterDataSlot;

typedef struct OverworldWildEncounterData {
    u8 walkingRate;
    u8 surfingRate;
    u8 rockSmashRate;
    u8 oldRodRate;
    u8 goodRodRate;
    u8 superRodRate;
    u8 padding[2];
    OverworldWildLandEncounterData landSlots;
    u16 hoennSoundsSpecies[OW_WILD_SOUND_SLOTS];
    u16 sinnohSoundsSpecies[OW_WILD_SOUND_SLOTS];
    OverworldWildEncounterDataSlot surfSlots[OW_WILD_SURF_SLOTS];
    OverworldWildEncounterDataSlot rockSmashSlots[OW_WILD_ROCK_SMASH_SLOTS];
    OverworldWildEncounterDataSlot oldRodSlots[OW_WILD_FISH_SLOTS];
    OverworldWildEncounterDataSlot goodRodSlots[OW_WILD_FISH_SLOTS];
    OverworldWildEncounterDataSlot superRodSlots[OW_WILD_FISH_SLOTS];
    u16 landSwarm;
    u16 surfSwarm;
    u16 nightFish;
    u16 fishSwarm;
} OverworldWildEncounterData;

typedef struct OverworldWildRolledEncounter {
    u32 personality;
    u16 species;
    u8 form;
    u8 level;
} OverworldWildRolledEncounter;

typedef struct OverworldWildSpawnPosition {
    int startX;
    int startY;
    u8 headbuttTreeType;
} OverworldWildSpawnPosition;

typedef struct OverworldWildEncounterArea {
    u16 mapId;
    u16 encounterDataId;
} OverworldWildEncounterArea;

typedef struct OverworldWildHeadbuttHeader {
    u16 normalTreeCount;
    u16 specialTreeCount;
} OverworldWildHeadbuttHeader;

typedef struct OverworldWildHeadbuttEncounterSlot {
    u16 species;
    u8 minLevel;
    u8 maxLevel;
} OverworldWildHeadbuttEncounterSlot;

typedef struct OverworldWildHeadbuttCoord {
    s16 x;
    s16 y;
} OverworldWildHeadbuttCoord;

typedef struct OverworldWildHeadbuttTree {
    OverworldWildHeadbuttCoord coords[OW_WILD_HEADBUTT_COORDS_PER_TREE];
} OverworldWildHeadbuttTree;

typedef struct OverworldWildHeadbuttLandingOffset {
    s8 dx;
    s8 dy;
} OverworldWildHeadbuttLandingOffset;

static BOOL OverworldWildSpawns_IsTileOccupiedByObject(FieldSystem *fieldSystem, int x, int y);
static BOOL OverworldWildSpawns_OverlayOnPlayerStep(FieldSystem *fieldSystem, OverworldWildSpawnState *state);
static void OverworldWildSpawns_OverlayCleanupPendingBattle(OverworldWildSpawnState *state, u16 battleResult);
static void OverworldWildSpawns_ClearSlot(OverworldWildSpawnState *state, int slot, BOOL deleteObject);
static void OverworldWildSpawns_ResetAmbientCryCooldown(OverworldWildSpawnState *state);

static volatile void *sOverworldWildDiagnosticMapObjectMan;
static volatile void *sOverworldWildDiagnosticMapObjects;
static volatile int sOverworldWildDiagnosticStateMapId;
static volatile void *sOverworldWildDiagnosticStateMapObjectMan;
static volatile void *sOverworldWildDiagnosticStateMapObjects;

const OverworldWildSpawnsOverlayEntry gOverworldWildSpawnsOverlayEntry __attribute__((section(".overworld_wild_spawns_entry"), used)) = {
    OverworldWildSpawns_OverlayOnPlayerStep,
    OverworldWildSpawns_OverlayCleanupPendingBattle,
};

static const u8 sGrassSlotWeights[OW_WILD_GRASS_SLOTS] = {
    20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1,
};

static const u8 sSurfSlotWeights[OW_WILD_SURF_SLOTS] = {
    60, 30, 5, 4, 1,
};

static const u8 sFishingSlotWeights[OW_WILD_FISH_SLOTS] = {
    60, 30, 5, 4, 1,
};

static const OverworldWildHeadbuttLandingOffset sHeadbuttLandingOffsets[] = {
    { 0, 1 },
    { 0, -1 },
    { -1, 0 },
    { 1, 0 },
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

static BOOL OverworldWildSpawns_IsNearActiveSpawn(OverworldWildSpawnState *state, int x, int y, int radius)
{
    int i;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (state->spawns[i].active && state->spawns[i].object != NULL) {
            int spawnX = MapObject_GetCurrentX(state->spawns[i].object);
            int spawnY = MapObject_GetCurrentY(state->spawns[i].object);
            int dx = OverworldWildSpawns_Abs(x - spawnX);
            int dy = OverworldWildSpawns_Abs(y - spawnY);

            if (OverworldWildSpawns_Max(dx, dy) <= radius) {
                return TRUE;
            }
        }
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_IsCurrentMapObject(FieldSystem *fieldSystem, LocalMapObject *object)
{
    MapObjectMan *mapObjectMan = (MapObjectMan *)fieldSystem->mapObjectMan;
    LocalMapObject *objects;
    u32 objectAddr;
    u32 startAddr;
    u32 endAddr;

    if (object == NULL || mapObjectMan == NULL || mapObjectMan->objects == NULL) {
        return FALSE;
    }

    objects = mapObjectMan->objects;
    objectAddr = (u32)object;
    startAddr = (u32)objects;
    endAddr = startAddr + mapObjectMan->object_count * sizeof(LocalMapObject);

    return objectAddr >= startAddr && objectAddr < endAddr;
}

static BOOL OverworldWildSpawns_IsCurrentSpawnObject(FieldSystem *fieldSystem, const OverworldWildSpawn *spawn)
{
    if (!spawn->active || !OverworldWildSpawns_IsCurrentMapObject(fieldSystem, spawn->object)) {
        return FALSE;
    }

    return (spawn->object->flags & MAPOBJECTFLAG_ACTIVE) != 0;
}

static void OverworldWildSpawns_ClearSavedShiny(OverworldWildSpawnState *state, int slot)
{
    state->savedShinies[slot].personality = 0;
    state->savedShinies[slot].mapId = MAP_NOTHING;
    state->savedShinies[slot].species = SPECIES_NONE;
    state->savedShinies[slot].form = 0;
    state->savedShinies[slot].level = 0;
    state->savedShinies[slot].terrain = 0;
    state->savedShinies[slot].active = FALSE;
}

static void OverworldWildSpawns_TrySaveShinyReservation(OverworldWildSpawnState *state, const OverworldWildSpawn *spawn)
{
    int i;

    if (!spawn->active
        || !spawn->shiny
        || spawn->species == SPECIES_NONE
        || spawn->mapId == MAP_NOTHING) {
        return;
    }

    for (i = 0; i < OW_WILD_MAX_SAVED_SHINIES; i++) {
        if (!state->savedShinies[i].active) {
            state->savedShinies[i].mapId = spawn->mapId;
            state->savedShinies[i].personality = spawn->personality;
            state->savedShinies[i].species = spawn->species;
            state->savedShinies[i].form = spawn->form;
            state->savedShinies[i].level = spawn->level;
            state->savedShinies[i].terrain = spawn->terrain;
            state->savedShinies[i].active = TRUE;
            return;
        }
    }
}

static int OverworldWildSpawns_FindSavedShiny(OverworldWildSpawnState *state, u16 mapId, OverworldWildSpawnTerrain terrain)
{
    int i;

    for (i = 0; i < OW_WILD_MAX_SAVED_SHINIES; i++) {
        if (state->savedShinies[i].active
            && state->savedShinies[i].mapId == mapId
            && state->savedShinies[i].terrain == terrain) {
            return i;
        }
    }

    return -1;
}

static void OverworldWildSpawns_LoadSavedShinyEncounter(OverworldWildSpawnState *state, int slot, OverworldWildRolledEncounter *encounter)
{
    encounter->personality = state->savedShinies[slot].personality;
    encounter->species = state->savedShinies[slot].species;
    encounter->form = state->savedShinies[slot].form;
    encounter->level = state->savedShinies[slot].level;
}

static void OverworldWildSpawns_ClearSlotAndSaveShiny(OverworldWildSpawnState *state, int slot, BOOL deleteObject)
{
    OverworldWildSpawns_TrySaveShinyReservation(state, &state->spawns[slot]);
    OverworldWildSpawns_ClearSlot(state, slot, deleteObject);
}

static void OverworldWildSpawns_DropStaleSlots(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    int i;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (state->spawns[i].active
            && !OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[i])) {
            OverworldWildSpawns_ClearSlotAndSaveShiny(state, i, FALSE);
        }
    }
}

static void OverworldWildSpawns_ResetAmbientCryCooldown(OverworldWildSpawnState *state)
{
    state->ambientCryCooldown = OW_WILD_AMBIENT_CRY_MIN_COOLDOWN_STEPS
        + (gf_rand() % OW_WILD_AMBIENT_CRY_RANDOM_COOLDOWN_STEPS);
}

static void OverworldWildSpawns_TryPlayAmbientCry(OverworldWildSpawnState *state)
{
    int i;
    int activeCount = 0;
    u8 cooldownTick;
    int chosen;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (state->spawns[i].active && state->spawns[i].object != NULL) {
            activeCount++;
        }
    }

    if (activeCount == 0) {
        OverworldWildSpawns_ResetAmbientCryCooldown(state);
        return;
    }

    cooldownTick = 1 + (activeCount / 3);
    if (cooldownTick > OW_WILD_AMBIENT_CRY_MAX_COOLDOWN_TICK) {
        cooldownTick = OW_WILD_AMBIENT_CRY_MAX_COOLDOWN_TICK;
    }

    if (state->ambientCryCooldown > cooldownTick) {
        state->ambientCryCooldown -= cooldownTick;
        return;
    }

    chosen = gf_rand() % activeCount;
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (state->spawns[i].active && state->spawns[i].object != NULL) {
            if (chosen == 0) {
                PlayCry(state->spawns[i].species, state->spawns[i].form);
                OverworldWildSpawns_ResetAmbientCryCooldown(state);
                return;
            }
            chosen--;
        }
    }

    OverworldWildSpawns_ResetAmbientCryCooldown(state);
}

static BOOL OverworldWildSpawns_IsSurfBehavior(u8 behavior)
{
    return behavior == 16 || behavior == 18 || behavior == 21 || behavior == 42;
}

static void OverworldWildSpawns_ClearSlot(OverworldWildSpawnState *state, int slot, BOOL deleteObject)
{
    if (deleteObject && state->spawns[slot].active && state->spawns[slot].object != NULL) {
        DeleteMapObject(state->spawns[slot].object);
    }

    state->spawns[slot].object = NULL;
    state->spawns[slot].personality = 0;
    state->spawns[slot].mapId = MAP_NOTHING;
    state->spawns[slot].species = SPECIES_NONE;
    state->spawns[slot].form = 0;
    state->spawns[slot].level = 0;
    state->spawns[slot].terrain = 0;
    state->spawns[slot].shiny = FALSE;
    state->spawns[slot].active = FALSE;
}

static void OverworldWildSpawns_Clear(OverworldWildSpawnState *state, BOOL deleteObjects)
{
    int i;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        OverworldWildSpawns_ClearSlotAndSaveShiny(state, i, deleteObjects);
    }

    state->justSpawned = FALSE;
    state->spawnCooldown = 0;
    state->headbuttSpawnCooldown = OW_WILD_HEADBUTT_REFILL_ATTEMPT_COOLDOWN;
    state->fishingSpawnCooldown = OW_WILD_FISHING_REFILL_ATTEMPT_COOLDOWN;
    OverworldWildSpawns_ResetAmbientCryCooldown(state);
    state->battleGraceSteps = 0;
    state->pendingPersonality = 0;
    state->pendingShiny = FALSE;
    state->pendingSlot = -1;
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

static const u16 *OverworldWildSpawns_GetTimeOfDaySpeciesTable(const OverworldWildLandEncounterData *landSlots)
{
    if ((gf_rand() % 100) < OW_WILD_RANDOM_TIME_TABLE_CHANCE_PERCENT) {
        switch (gf_rand() % 3) {
        case 0:
            return landSlots->morningSpecies;
        case 1:
            return landSlots->daySpecies;
        case 2:
        default:
            return landSlots->nightSpecies;
        }
    }

    switch (GF_RTC_GetTimeOfDayWildParam()) {
    case TIMEOFDAY_WILD_MORN:
        return landSlots->morningSpecies;
    case TIMEOFDAY_WILD_NITE:
        return landSlots->nightSpecies;
    case TIMEOFDAY_WILD_DAY:
    default:
        return landSlots->daySpecies;
    }
}

static u8 OverworldWildSpawns_RollWeightedSlot(const u8 *weights, u8 count)
{
    u32 roll = gf_rand() % 100;
    u8 slot;

    for (slot = 0; slot < count; slot++) {
        if (roll < weights[slot]) {
            return slot;
        }
        roll -= weights[slot];
    }

    return count - 1;
}

static BOOL OverworldWildSpawns_TryGetSpawnTerrain(FieldSystem *fieldSystem, int x, int y, OverworldWildSpawnTerrain *terrain)
{
    u8 behavior;

    if (x < 0 || y < 0) {
        return FALSE;
    }

    behavior = GetMetatileBehaviorAt(fieldSystem, x, y);
    if (OverworldWildSpawns_IsSurfBehavior(behavior)) {
        *terrain = OW_WILD_SPAWN_TERRAIN_SURF;
    } else if (behavior == OW_WILD_TILE_ENCOUNTER_GRASS
        || behavior == OW_WILD_TILE_LONG_GRASS
        || behavior == 5
        || behavior == 8
        || behavior == 11
        || behavior == 37
        || behavior == 112
        || behavior == 119
        || behavior == 123
        || behavior == 163
        || behavior == 164) {
        *terrain = OW_WILD_SPAWN_TERRAIN_LAND;
    } else {
        return FALSE;
    }

    return TRUE;
}

static BOOL OverworldWildSpawns_TryGetFreeSlot(OverworldWildSpawnState *state, u8 start, u8 end, int *slot)
{
    u8 i;

    for (i = start; i < end; i++) {
        if (!state->spawns[i].active) {
            *slot = i;
            return TRUE;
        }
    }

    return FALSE;
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

static BOOL OverworldWildSpawns_TryPickSpawnPosition(OverworldWildSpawnState *state, FieldSystem *fieldSystem, OverworldWildSpawnTerrain requestedTerrain, OverworldWildSpawnPosition *position)
{
    int playerX = GetPlayerXCoord(fieldSystem->playerAvatar);
    int playerY = GetPlayerYCoord(fieldSystem->playerAvatar);
    int attempt;
    OverworldWildSpawnTerrain terrain;

    for (attempt = 0; attempt < OW_WILD_SPAWN_ATTEMPTS; attempt++) {
        int dx = (int)(gf_rand() % (OW_WILD_SPAWN_MAX_DISTANCE * 2 + 1)) - OW_WILD_SPAWN_MAX_DISTANCE;
        int dy = (int)(gf_rand() % (OW_WILD_SPAWN_MAX_DISTANCE * 2 + 1)) - OW_WILD_SPAWN_MAX_DISTANCE;
        int x = playerX + dx;
        int y = playerY + dy;
        int distance = OverworldWildSpawns_Max(OverworldWildSpawns_Abs(dx), OverworldWildSpawns_Abs(dy));

        if (distance < OW_WILD_SPAWN_MIN_DISTANCE || distance > OW_WILD_SPAWN_MAX_DISTANCE) {
            continue;
        }
        if (!OverworldWildSpawns_TryGetSpawnTerrain(fieldSystem, x, y, &terrain)) {
            continue;
        }
        if (terrain != requestedTerrain) {
            continue;
        }
        if (OverworldWildSpawns_IsTileOccupiedByObject(fieldSystem, x, y)) {
            continue;
        }
        if (OverworldWildSpawns_IsNearActiveSpawn(state, x, y, OW_WILD_SPAWN_MIN_MON_DISTANCE)) {
            continue;
        }

        position->startX = x;
        position->startY = y;
        return TRUE;
    }

    return FALSE;
}

static u32 OverworldWildSpawns_GetHeadbuttTreeDataOffset(void)
{
    return sizeof(OverworldWildHeadbuttHeader)
        + (OW_WILD_HEADBUTT_NORMAL_SLOTS + OW_WILD_HEADBUTT_SPECIAL_SLOTS) * sizeof(OverworldWildHeadbuttEncounterSlot);
}

static BOOL OverworldWildSpawns_IsHeadbuttLandingTile(FieldSystem *fieldSystem, int x, int y)
{
    u8 behavior;

    if (x < 0 || y < 0) {
        return FALSE;
    }
    if (OverworldWildSpawns_IsTileOccupiedByObject(fieldSystem, x, y)) {
        return FALSE;
    }
    if (IsMetatileBlockedAt(fieldSystem, x, y)) {
        return FALSE;
    }

    behavior = GetMetatileBehaviorAt(fieldSystem, x, y);
    if (behavior == OW_WILD_TILE_HEADBUTT || OverworldWildSpawns_IsSurfBehavior(behavior)) {
        return FALSE;
    }

    return TRUE;
}

static BOOL OverworldWildSpawns_HasAdjacentWater(FieldSystem *fieldSystem, int x, int y)
{
    static const OverworldWildHeadbuttLandingOffset waterOffsets[] = {
        { 0, 1 },
        { 0, -1 },
        { -1, 0 },
        { 1, 0 },
    };
    u32 i;

    for (i = 0; i < NELEMS(waterOffsets); i++) {
        int waterX = x + waterOffsets[i].dx;
        int waterY = y + waterOffsets[i].dy;

        if (waterX >= 0 && waterY >= 0
            && OverworldWildSpawns_IsSurfBehavior(GetMetatileBehaviorAt(fieldSystem, waterX, waterY))) {
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_IsFishingShoreTile(FieldSystem *fieldSystem, int x, int y)
{
    u8 behavior;

    if (x < 0 || y < 0) {
        return FALSE;
    }
    if (OverworldWildSpawns_IsTileOccupiedByObject(fieldSystem, x, y)) {
        return FALSE;
    }
    if (IsMetatileBlockedAt(fieldSystem, x, y)) {
        return FALSE;
    }

    behavior = GetMetatileBehaviorAt(fieldSystem, x, y);
    if (behavior == OW_WILD_TILE_HEADBUTT || OverworldWildSpawns_IsSurfBehavior(behavior)) {
        return FALSE;
    }

    return OverworldWildSpawns_HasAdjacentWater(fieldSystem, x, y);
}

static BOOL OverworldWildSpawns_TryPickFishingSpawnPosition(OverworldWildSpawnState *state, FieldSystem *fieldSystem, OverworldWildSpawnPosition *position)
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
        if (!OverworldWildSpawns_IsFishingShoreTile(fieldSystem, x, y)) {
            continue;
        }
        if (OverworldWildSpawns_IsNearActiveSpawn(state, x, y, OW_WILD_SPAWN_MIN_MON_DISTANCE)) {
            continue;
        }

        position->startX = x;
        position->startY = y;
        return TRUE;
    }

    return FALSE;
}

static void OverworldWildSpawns_TryPickHeadbuttLanding(OverworldWildSpawnState *state, FieldSystem *fieldSystem, int treeX, int treeY, u8 treeType, OverworldWildSpawnPosition *position, u32 *candidateCount)
{
    u32 landingStart = gf_rand() % NELEMS(sHeadbuttLandingOffsets);
    u32 landingAttempt;

    for (landingAttempt = 0; landingAttempt < NELEMS(sHeadbuttLandingOffsets); landingAttempt++) {
        const OverworldWildHeadbuttLandingOffset *landing =
            &sHeadbuttLandingOffsets[(landingStart + landingAttempt) % NELEMS(sHeadbuttLandingOffsets)];
        int spawnX = treeX + landing->dx;
        int spawnY = treeY + landing->dy;
        int distance = OverworldWildSpawns_DistanceFromPlayer(fieldSystem, spawnX, spawnY);

        if (distance < OW_WILD_SPAWN_MIN_DISTANCE || distance > OW_WILD_SPAWN_MAX_DISTANCE) {
            continue;
        }
        if (!OverworldWildSpawns_IsHeadbuttLandingTile(fieldSystem, spawnX, spawnY)) {
            continue;
        }
        if (OverworldWildSpawns_IsNearActiveSpawn(state, treeX, treeY, OW_WILD_SPAWN_MIN_MON_DISTANCE)) {
            continue;
        }

        (*candidateCount)++;
        if ((gf_rand() % *candidateCount) == 0) {
            position->startX = treeX;
            position->startY = treeY;
            position->headbuttTreeType = treeType;
        }
    }
}

static BOOL OverworldWildSpawns_TryPickHeadbuttSpawnPosition(OverworldWildSpawnState *state, FieldSystem *fieldSystem, OverworldWildSpawnPosition *position)
{
    OverworldWildHeadbuttHeader header;
    u32 treeDataOffset;
    u32 candidateCount = 0;
    u32 treeGroup;

    if (fieldSystem == NULL || fieldSystem->location == NULL) {
        return FALSE;
    }

    ArchiveDataLoadOfs(&header, ARC_HEADBUTT_TREES, fieldSystem->location->mapId, 0, sizeof(header));
    if (header.normalTreeCount == 0 && header.specialTreeCount == 0) {
        return FALSE;
    }

    treeDataOffset = OverworldWildSpawns_GetHeadbuttTreeDataOffset();

    for (treeGroup = 0; treeGroup < 2; treeGroup++) {
        u8 treeType = treeGroup == 0 ? OW_WILD_HEADBUTT_NORMAL_TREE : OW_WILD_HEADBUTT_SPECIAL_TREE;
        u32 treeCount = treeType == OW_WILD_HEADBUTT_NORMAL_TREE ? header.normalTreeCount : header.specialTreeCount;
        u32 treeOffset = treeDataOffset;
        u32 treeIndex;

        if (treeType == OW_WILD_HEADBUTT_SPECIAL_TREE) {
            treeOffset += header.normalTreeCount * sizeof(OverworldWildHeadbuttTree);
        }

        for (treeIndex = 0; treeIndex < treeCount; treeIndex++) {
            OverworldWildHeadbuttTree tree;
            u32 coordIndex;

            ArchiveDataLoadOfs(&tree, ARC_HEADBUTT_TREES, fieldSystem->location->mapId,
                treeOffset + treeIndex * sizeof(tree), sizeof(tree));
            for (coordIndex = 0; coordIndex < OW_WILD_HEADBUTT_COORDS_PER_TREE; coordIndex++) {
                int treeX = tree.coords[coordIndex].x;
                int treeY = tree.coords[coordIndex].y;

                if (treeX == OW_WILD_HEADBUTT_EMPTY_COORD || treeY == OW_WILD_HEADBUTT_EMPTY_COORD) {
                    continue;
                }

                OverworldWildSpawns_TryPickHeadbuttLanding(state, fieldSystem, treeX, treeY, treeType, position, &candidateCount);
            }
        }
    }

    return candidateCount != 0;
}

static BOOL OverworldWildSpawns_TryRollHeadbuttEncounter(FieldSystem *fieldSystem, u8 treeType, OverworldWildRolledEncounter *encounter)
{
    int attempts;
    u32 slotOffset = sizeof(OverworldWildHeadbuttHeader);
    u8 slotCount = OW_WILD_HEADBUTT_NORMAL_SLOTS;

    if (fieldSystem == NULL || fieldSystem->location == NULL) {
        return FALSE;
    }

    if (treeType == OW_WILD_HEADBUTT_SPECIAL_TREE) {
        slotOffset += OW_WILD_HEADBUTT_NORMAL_SLOTS * sizeof(OverworldWildHeadbuttEncounterSlot);
        slotCount = OW_WILD_HEADBUTT_SPECIAL_SLOTS;
    }

    for (attempts = 0; attempts < slotCount; attempts++) {
        OverworldWildHeadbuttEncounterSlot slot;
        u32 slotIndex = gf_rand() % slotCount;
        u16 species;

        ArchiveDataLoadOfs(&slot, ARC_HEADBUTT_TREES, fieldSystem->location->mapId,
            slotOffset + slotIndex * sizeof(slot), sizeof(slot));

        species = slot.species & OW_WILD_SPECIES_MASK;
        if (species != SPECIES_NONE && slot.minLevel != 0) {
            encounter->species = species;
            encounter->form = slot.species >> OW_WILD_FORM_SHIFT;
            encounter->level = slot.minLevel;
            if (slot.maxLevel > slot.minLevel) {
                encounter->level += gf_rand() % (slot.maxLevel - slot.minLevel + 1);
            }
            return TRUE;
        }
    }

    if (treeType == OW_WILD_HEADBUTT_SPECIAL_TREE) {
        return OverworldWildSpawns_TryRollHeadbuttEncounter(fieldSystem, OW_WILD_HEADBUTT_NORMAL_TREE, encounter);
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_TryRollLandEncounter(const OverworldWildEncounterData *encounterData, OverworldWildRolledEncounter *encounter)
{
    int attempts;
    const u16 *speciesTable;

    speciesTable = OverworldWildSpawns_GetTimeOfDaySpeciesTable(&encounterData->landSlots);

    for (attempts = 0; attempts < OW_WILD_GRASS_SLOTS; attempts++) {
        u8 slot = OverworldWildSpawns_RollWeightedSlot(sGrassSlotWeights, OW_WILD_GRASS_SLOTS);
        u16 encodedSpecies = speciesTable[slot];
        u16 species = encodedSpecies & OW_WILD_SPECIES_MASK;

        if (species != SPECIES_NONE && encounterData->landSlots.levels[slot] != 0) {
            encounter->species = species;
            encounter->form = encodedSpecies >> OW_WILD_FORM_SHIFT;
            encounter->level = encounterData->landSlots.levels[slot];
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_TryRollSurfEncounter(const OverworldWildEncounterData *encounterData, OverworldWildRolledEncounter *encounter)
{
    int attempts;

    for (attempts = 0; attempts < OW_WILD_SURF_SLOTS; attempts++) {
        u8 slot = OverworldWildSpawns_RollWeightedSlot(sSurfSlotWeights, OW_WILD_SURF_SLOTS);
        u16 encodedSpecies = encounterData->surfSlots[slot].species;
        u16 species = encodedSpecies & OW_WILD_SPECIES_MASK;

        if (species != SPECIES_NONE && encounterData->surfSlots[slot].minLevel != 0) {
            u8 minLevel = encounterData->surfSlots[slot].minLevel;
            u8 maxLevel = encounterData->surfSlots[slot].maxLevel;

            encounter->species = species;
            encounter->form = encodedSpecies >> OW_WILD_FORM_SHIFT;
            encounter->level = minLevel;
            if (maxLevel > minLevel) {
                encounter->level += gf_rand() % (maxLevel - minLevel + 1);
            }
            return TRUE;
        }
    }

    return FALSE;
}

static const OverworldWildEncounterDataSlot *OverworldWildSpawns_GetFishingSlots(
    const OverworldWildEncounterData *encounterData,
    OverworldWildFishingRodTable rodTable)
{
    switch (rodTable) {
    case OW_WILD_FISHING_ROD_OLD:
        return encounterData->oldRodSlots;
    case OW_WILD_FISHING_ROD_GOOD:
        return encounterData->goodRodSlots;
    case OW_WILD_FISHING_ROD_SUPER:
    default:
        return encounterData->superRodSlots;
    }
}

static u8 OverworldWildSpawns_GetFishingRate(const OverworldWildEncounterData *encounterData, OverworldWildFishingRodTable rodTable)
{
    switch (rodTable) {
    case OW_WILD_FISHING_ROD_OLD:
        return encounterData->oldRodRate;
    case OW_WILD_FISHING_ROD_GOOD:
        return encounterData->goodRodRate;
    case OW_WILD_FISHING_ROD_SUPER:
    default:
        return encounterData->superRodRate;
    }
}

static BOOL OverworldWildSpawns_FishingTableHasValidSlot(const OverworldWildEncounterDataSlot *slots)
{
    u8 slot;

    for (slot = 0; slot < OW_WILD_FISH_SLOTS; slot++) {
        if ((slots[slot].species & OW_WILD_SPECIES_MASK) != SPECIES_NONE && slots[slot].minLevel != 0) {
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_TryPickFishingRodTable(
    const OverworldWildEncounterData *encounterData,
    OverworldWildFishingRodTable *rodTable)
{
    u16 totalRate = 0;
    u16 roll;
    u8 rod;

    for (rod = 0; rod < 3; rod++) {
        OverworldWildFishingRodTable currentRod = (OverworldWildFishingRodTable)rod;
        const OverworldWildEncounterDataSlot *slots = OverworldWildSpawns_GetFishingSlots(encounterData, currentRod);
        u8 rate = OverworldWildSpawns_GetFishingRate(encounterData, currentRod);

        if (rate != 0 && OverworldWildSpawns_FishingTableHasValidSlot(slots)) {
            totalRate += rate;
        }
    }

    if (totalRate == 0) {
        return FALSE;
    }

    roll = gf_rand() % totalRate;
    for (rod = 0; rod < 3; rod++) {
        OverworldWildFishingRodTable currentRod = (OverworldWildFishingRodTable)rod;
        const OverworldWildEncounterDataSlot *slots = OverworldWildSpawns_GetFishingSlots(encounterData, currentRod);
        u8 rate = OverworldWildSpawns_GetFishingRate(encounterData, currentRod);

        if (rate == 0 || !OverworldWildSpawns_FishingTableHasValidSlot(slots)) {
            continue;
        }
        if (roll < rate) {
            *rodTable = currentRod;
            return TRUE;
        }
        roll -= rate;
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_TryRollFishingEncounter(const OverworldWildEncounterData *encounterData, OverworldWildRolledEncounter *encounter)
{
    OverworldWildFishingRodTable rodTable;
    const OverworldWildEncounterDataSlot *slots;
    int attempts;

    if (!OverworldWildSpawns_TryPickFishingRodTable(encounterData, &rodTable)) {
        return FALSE;
    }

    slots = OverworldWildSpawns_GetFishingSlots(encounterData, rodTable);
    for (attempts = 0; attempts < OW_WILD_FISH_SLOTS; attempts++) {
        u8 slot = OverworldWildSpawns_RollWeightedSlot(sFishingSlotWeights, OW_WILD_FISH_SLOTS);
        u16 encodedSpecies = slots[slot].species;
        u16 species = encodedSpecies & OW_WILD_SPECIES_MASK;

        if (species != SPECIES_NONE && slots[slot].minLevel != 0) {
            u8 minLevel = slots[slot].minLevel;
            u8 maxLevel = slots[slot].maxLevel;

            encounter->species = species;
            encounter->form = encodedSpecies >> OW_WILD_FORM_SHIFT;
            encounter->level = minLevel;
            if (maxLevel > minLevel) {
                encounter->level += gf_rand() % (maxLevel - minLevel + 1);
            }
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_TryRollEncounter(FieldSystem *fieldSystem, OverworldWildSpawnTerrain terrain, OverworldWildRolledEncounter *encounter)
{
    int encounterDataId;
    OverworldWildEncounterData encounterData;

    if (!OverworldWildSpawns_TryGetEncounterDataId(fieldSystem, &encounterDataId)) {
        return FALSE;
    }

    ArchiveDataLoadOfs(&encounterData, ARC_ENCOUNTERS, encounterDataId, 0, sizeof(encounterData));

    if (terrain == OW_WILD_SPAWN_TERRAIN_SURF) {
        return OverworldWildSpawns_TryRollSurfEncounter(&encounterData, encounter);
    }
    if (terrain == OW_WILD_SPAWN_TERRAIN_FISHING) {
        return OverworldWildSpawns_TryRollFishingEncounter(&encounterData, encounter);
    }
    return OverworldWildSpawns_TryRollLandEncounter(&encounterData, encounter);
}

static u32 OverworldWildSpawns_GetSpriteID(u16 species, u8 form)
{
    return FollowingPokemon_GetSpriteID(species, form, 0);
}

static BOOL OverworldWildSpawns_RollShiny(OverworldWildSpawnState *state)
{
    if (state->shinySpawned) {
        return FALSE;
    }

    return (gf_rand() % OW_WILD_SHINY_ODDS) == 0;
}

static u32 OverworldWildSpawns_RollPersonality(void)
{
    return gf_rand() | (gf_rand() << 16);
}

static u32 OverworldWildSpawns_MakePersonalityShiny(u32 personality)
{
    u32 shinyValue = SHINY_VALUE(OVERWORLD_WILD_BATTLE_SHINY_OTID, personality);

    if (shinyValue >= SHINY_ODDS) {
        if (shinyValue & 0xE000) {
            personality ^= (shinyValue << 16) & 0xE0000000;
        }
        personality ^= shinyValue & 0x1FFF;
        personality ^= gf_rand() % SHINY_ODDS;
    }

    return personality;
}

static LocalMapObject *OverworldWildSpawns_CreateObject(FieldSystem *fieldSystem, const OverworldWildSpawnPosition *position, u32 spriteId, BOOL shiny)
{
    OverworldWildCustomMovement_SetFieldSystem(fieldSystem);

    return CreateSpecialFieldObjectWithParams(
        fieldSystem->mapObjectMan,
        position->startX,
        position->startY,
        1,
        spriteId,
        OW_WILD_MOVE_STOCK_WANDER,
        fieldSystem->location->mapId,
        0,
        OW_WILD_MOVEMENT_BEHAVIOR_CHASE_PLAYER,
        OW_WILD_PAL_PARAM_ENABLE | (shiny ? OW_WILD_PAL_PARAM_SHINY : 0));
}

static void OverworldWildSpawns_ApplyMovementRange(LocalMapObject *object)
{
    MapObject_SetXRange(object, 2);
    MapObject_SetYRange(object, 2);
}

static void OverworldWildSpawns_ApplyPokemonRenderParams(LocalMapObject *object, u16 species, u8 form, u32 spriteId, BOOL shiny)
{
    FollowPokeMapObjectSetParams(object, species, form, shiny);
    if (shiny) {
        sub_02069DC8(object, TRUE);
        ChangeMapObjSprite(object, spriteId);
        MapObject_ClearBits(object, BIT_VANISH);
    }
}

static BOOL OverworldWildSpawns_SpawnOne(OverworldWildSpawnState *state, FieldSystem *fieldSystem, OverworldWildSpawnTerrain terrain, int slot)
{
    OverworldWildRolledEncounter encounter;
    OverworldWildSpawnPosition position = { 0 };
    LocalMapObject *object;
    u32 spriteId;
    int savedShinySlot;
    BOOL shiny;

    if (terrain == OW_WILD_SPAWN_TERRAIN_HEADBUTT) {
        if (!OverworldWildSpawns_TryPickHeadbuttSpawnPosition(state, fieldSystem, &position)) {
            return FALSE;
        }
    } else if (terrain == OW_WILD_SPAWN_TERRAIN_FISHING) {
        if (!OverworldWildSpawns_TryPickFishingSpawnPosition(state, fieldSystem, &position)) {
            return FALSE;
        }
    } else if (!OverworldWildSpawns_TryPickSpawnPosition(state, fieldSystem, terrain, &position)) {
        return FALSE;
    }

    savedShinySlot = OverworldWildSpawns_FindSavedShiny(state, fieldSystem->location->mapId, terrain);
    if (savedShinySlot >= 0) {
        OverworldWildSpawns_LoadSavedShinyEncounter(state, savedShinySlot, &encounter);
        shiny = TRUE;
    } else {
        if (terrain == OW_WILD_SPAWN_TERRAIN_HEADBUTT) {
            if (!OverworldWildSpawns_TryRollHeadbuttEncounter(fieldSystem, position.headbuttTreeType, &encounter)) {
                return FALSE;
            }
        } else if (!OverworldWildSpawns_TryRollEncounter(fieldSystem, terrain, &encounter)) {
            return FALSE;
        }

        encounter.personality = OverworldWildSpawns_RollPersonality();
        shiny = OverworldWildSpawns_RollShiny(state);
        if (shiny) {
            encounter.personality = OverworldWildSpawns_MakePersonalityShiny(encounter.personality);
        }
    }

    if (encounter.species == SPECIES_NONE || encounter.level == 0) {
        return FALSE;
    }

    spriteId = OverworldWildSpawns_GetSpriteID(encounter.species, encounter.form);

    object = OverworldWildSpawns_CreateObject(fieldSystem, &position, spriteId, shiny);
    if (object == NULL) {
        return FALSE;
    }

    MapObject_SetID(object, OW_WILD_OBJECT_ID_START + slot);
    OverworldWildSpawns_ApplyMovementRange(object);
    OverworldWildSpawns_ApplyPokemonRenderParams(object, encounter.species, encounter.form, spriteId, shiny);

    if (savedShinySlot >= 0) {
        OverworldWildSpawns_ClearSavedShiny(state, savedShinySlot);
    }

    state->spawns[slot].object = object;
    state->spawns[slot].personality = encounter.personality;
    state->spawns[slot].mapId = fieldSystem->location->mapId;
    state->spawns[slot].species = encounter.species;
    state->spawns[slot].form = encounter.form;
    state->spawns[slot].level = encounter.level;
    state->spawns[slot].terrain = terrain;
    state->spawns[slot].shiny = shiny;
    state->spawns[slot].active = TRUE;

    if (shiny) {
        state->shinySpawned = TRUE;
        PlaySE(SEQ_SE_PL_KIRAKIRA);
    }

    return TRUE;
}

static void OverworldWildSpawns_DespawnFarMons(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    int i;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (state->spawns[i].active && state->spawns[i].object != NULL) {
            int x = MapObject_GetCurrentX(state->spawns[i].object);
            int y = MapObject_GetCurrentY(state->spawns[i].object);

            if (!state->spawns[i].shiny
                && OverworldWildSpawns_DistanceFromPlayer(fieldSystem, x, y) > OW_WILD_DESPAWN_DISTANCE) {
                OverworldWildSpawns_ClearSlotAndSaveShiny(state, i, TRUE);
            }
        }
    }
}

static void OverworldWildSpawns_TryRefill(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    int slot;
    BOOL spawned = FALSE;

    if (state->spawnCooldown != 0) {
        state->spawnCooldown--;
        return;
    }

    if (OverworldWildSpawns_TryGetFreeSlot(state, OW_WILD_HEADBUTT_SLOT_START, OW_WILD_FISH_SLOT_START, &slot)) {
        if (state->headbuttSpawnCooldown != 0) {
            state->headbuttSpawnCooldown--;
        } else {
            state->headbuttSpawnCooldown = OW_WILD_HEADBUTT_REFILL_ATTEMPT_COOLDOWN;
            if ((gf_rand() % 100) < OW_WILD_HEADBUTT_SPAWN_CHANCE_PERCENT) {
                spawned = OverworldWildSpawns_SpawnOne(
                    state,
                    fieldSystem,
                    OW_WILD_SPAWN_TERRAIN_HEADBUTT,
                    slot);
            }
        }
    }

    if (!spawned && OverworldWildSpawns_TryGetFreeSlot(state, OW_WILD_FISH_SLOT_START, OW_WILD_MAX_SPAWNS, &slot)) {
        if (state->fishingSpawnCooldown != 0) {
            state->fishingSpawnCooldown--;
        } else {
            state->fishingSpawnCooldown = OW_WILD_FISHING_REFILL_ATTEMPT_COOLDOWN;
            if ((gf_rand() % 100) < OW_WILD_FISHING_SPAWN_CHANCE_PERCENT) {
                spawned = OverworldWildSpawns_SpawnOne(
                    state,
                    fieldSystem,
                    OW_WILD_SPAWN_TERRAIN_FISHING,
                    slot);
            }
        }
    }

    if (!spawned && OverworldWildSpawns_TryGetFreeSlot(state, 0, OW_WILD_GRASS_MAX_SPAWNS, &slot)) {
        spawned = OverworldWildSpawns_SpawnOne(state, fieldSystem, OW_WILD_SPAWN_TERRAIN_LAND, slot);
    }

    if (!spawned && OverworldWildSpawns_TryGetFreeSlot(state, OW_WILD_GRASS_MAX_SPAWNS, OW_WILD_GRASS_MAX_SPAWNS + OW_WILD_SURF_MAX_SPAWNS, &slot)) {
        spawned = OverworldWildSpawns_SpawnOne(state, fieldSystem, OW_WILD_SPAWN_TERRAIN_SURF, slot);
    }

    if (spawned) {
        state->justSpawned = TRUE;
        state->spawnCooldown = OW_WILD_REFILL_COOLDOWN_STEPS;
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

static BOOL OverworldWildSpawns_TryStartBattle(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    int i;

    if (state->battleGraceSteps != 0) {
        state->battleGraceSteps--;
        return FALSE;
    }

    if (state->pendingSlot >= 0
        || state->pendingSpecies != SPECIES_NONE
        || state->pendingLevel != 0) {
        return FALSE;
    }

    if (state->justSpawned) {
        state->justSpawned = FALSE;
        return FALSE;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (OverworldWildSpawns_IsTouchingPlayer(fieldSystem, &state->spawns[i])) {
            state->pendingPersonality = state->spawns[i].personality;
            state->pendingSpecies = state->spawns[i].species | (state->spawns[i].form << OW_WILD_FORM_SHIFT);
            state->pendingLevel = state->spawns[i].level;
            state->pendingShiny = state->spawns[i].shiny;
            state->pendingSlot = i;
            state->spawnCooldown = OW_WILD_REFILL_COOLDOWN_STEPS;

            EventSet_Script(fieldSystem, OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT, NULL);
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_BattleResultIsPlayerFlee(u16 battleResult)
{
    return battleResult == OW_WILD_BATTLE_RESULT_PLAYER_FLED
        || (battleResult & OW_WILD_BATTLE_RESULT_TRY_FLEE) != 0;
}

static void OverworldWildSpawns_OverlayCleanupPendingBattle(OverworldWildSpawnState *state, u16 battleResult)
{
    if (state->pendingSlot >= 0 && state->pendingSlot < OW_WILD_MAX_SPAWNS) {
        if (OverworldWildSpawns_BattleResultIsPlayerFlee(battleResult)) {
            state->battleGraceSteps = OW_WILD_FLEE_GRACE_STEPS;
        } else {
            OverworldWildSpawns_ClearSlot(state, state->pendingSlot, TRUE);
        }
    }

    state->pendingSlot = -1;
    state->pendingPersonality = 0;
}

static BOOL OverworldWildSpawns_UpdateMapState(FieldSystem *fieldSystem, OverworldWildSpawnState *state)
{
    MapObjectMan *mapObjectMan = (MapObjectMan *)fieldSystem->mapObjectMan;
    void *mapObjects = mapObjectMan != NULL ? mapObjectMan->objects : NULL;

#if OW_WILD_UPDATE_DIAGNOSTIC_READ_ONLY
    (void)state;
    sOverworldWildDiagnosticMapObjectMan = mapObjectMan;
    sOverworldWildDiagnosticMapObjects = mapObjects;
    return OverworldWildSpawns_IsEnabledMap(fieldSystem);
#endif

#if OW_WILD_UPDATE_DIAGNOSTIC_STATE_READ_ONLY
    sOverworldWildDiagnosticMapObjectMan = mapObjectMan;
    sOverworldWildDiagnosticMapObjects = mapObjects;
    sOverworldWildDiagnosticStateMapId = state != NULL ? state->mapId : MAP_NOTHING;
    sOverworldWildDiagnosticStateMapObjectMan = state != NULL ? state->mapObjectMan : NULL;
    sOverworldWildDiagnosticStateMapObjects = state != NULL ? state->mapObjects : NULL;
    return OverworldWildSpawns_IsEnabledMap(fieldSystem);
#endif

#if OW_WILD_UPDATE_DIAGNOSTIC_SETTER_ONLY
    (void)state;
    sOverworldWildDiagnosticMapObjectMan = mapObjectMan;
    sOverworldWildDiagnosticMapObjects = mapObjects;
    OverworldWildCustomMovement_SetFieldSystem(fieldSystem);
    return OverworldWildSpawns_IsEnabledMap(fieldSystem);
#endif

    if (!OverworldWildSpawns_IsEnabledMap(fieldSystem)) {
        OverworldWildCustomMovement_SetFieldSystem(NULL);
        if (state->mapId != MAP_NOTHING || state->mapObjectMan != NULL || state->mapObjects != NULL) {
#if OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR
            state->mapId = MAP_NOTHING;
            state->mapObjectMan = NULL;
            state->mapObjects = NULL;
#else
            OverworldWildSpawns_Clear(state, FALSE);
            state->mapId = MAP_NOTHING;
            state->mapObjectMan = NULL;
            state->mapObjects = NULL;
#endif
        }
        return FALSE;
    }

    if (state->mapId != fieldSystem->location->mapId
        || state->mapObjectMan != mapObjectMan
        || state->mapObjects != mapObjects) {
#if OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR
        state->mapId = fieldSystem->location->mapId;
        state->mapObjectMan = mapObjectMan;
        state->mapObjects = mapObjects;
#else
        OverworldWildSpawns_Clear(state, FALSE);
        state->mapId = fieldSystem->location->mapId;
        state->mapObjectMan = mapObjectMan;
        state->mapObjects = mapObjects;
#endif
    }

    OverworldWildCustomMovement_SetFieldSystem(fieldSystem);
    return TRUE;
}

static BOOL OverworldWildSpawns_OverlayOnPlayerStep(FieldSystem *fieldSystem, OverworldWildSpawnState *state)
{
#if OW_WILD_STEP_DIAGNOSTIC_ENTRY_ONLY
    (void)fieldSystem;
    (void)state;
    return FALSE;
#endif

    if (!OverworldWildSpawns_UpdateMapState(fieldSystem, state)) {
        return FALSE;
    }

#if OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY
    return FALSE;
#endif

    OverworldWildSpawns_DropStaleSlots(state, fieldSystem);
    OverworldWildSpawns_DespawnFarMons(state, fieldSystem);
    if (OverworldWildSpawns_TryStartBattle(state, fieldSystem)) {
        return TRUE;
    }

    OverworldWildSpawns_TryPlayAmbientCry(state);
    OverworldWildSpawns_TryRefill(state, fieldSystem);
    return FALSE;
}

#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS
