#include "../../include/overworld_wild_helper.h"
#include "../../include/config.h"
#include "../../include/constants/file.h"
#include "../../include/constants/species.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_wild_spawns.h"
#include "../../include/overworld_wild_movement.h"
#include "../../include/pokemon.h"
#include "../../include/rtc.h"
#include "../../include/script.h"
#include "../../include/sprite.h"

#define OW_WILD_HELPER_GRASS_SLOTS 12
#define OW_WILD_HELPER_SURF_SLOTS 5
#define OW_WILD_HELPER_FISH_SLOTS 5
#define OW_WILD_HELPER_HEADBUTT_NORMAL_SLOTS 12
#define OW_WILD_HELPER_HEADBUTT_SPECIAL_SLOTS 6
#define OW_WILD_HELPER_HEADBUTT_NORMAL_TREE 0
#define OW_WILD_HELPER_HEADBUTT_SPECIAL_TREE 1
#define OW_WILD_HELPER_RANDOM_TIME_TABLE_CHANCE_PERCENT 20
#define OW_WILD_HELPER_SPAWN_MIN_DISTANCE 4
#define OW_WILD_HELPER_SPAWN_MAX_DISTANCE 8
#define OW_WILD_HELPER_SPAWN_MIN_MON_DISTANCE 3
#define OW_WILD_HELPER_BUDGETED_SPAWN_POSITION_SEARCH 1
#define OW_WILD_HELPER_SPAWN_POSITION_BUDGET 16
#define OW_WILD_HELPER_SPAWN_POSITION_DIAMETER (OW_WILD_HELPER_SPAWN_MAX_DISTANCE * 2 + 1)
#define OW_WILD_HELPER_SPAWN_POSITION_TILE_COUNT \
    (OW_WILD_HELPER_SPAWN_POSITION_DIAMETER * OW_WILD_HELPER_SPAWN_POSITION_DIAMETER)
#define OW_WILD_HELPER_SPAWN_POSITION_STRIDE 73
#define OW_WILD_HELPER_SPECIES_MASK 0x7FF
#define OW_WILD_HELPER_FORM_SHIFT 11
#define OW_WILD_HELPER_THROW_CARRIED_Y_OFFSET_FX32 (0x10000 / 2)
#define OW_WILD_DESPAWN_TELEMETRY_MAGIC 0x4F574450
#define OW_WILD_DESPAWN_CONTEXT_CURRENT (1 << 0)
#define OW_WILD_DESPAWN_CONTEXT_TASK_BUSY (1 << 1)
#define OW_WILD_DESPAWN_CONTEXT_POINTER_IN_ARRAY (1 << 2)
#define OW_WILD_DESPAWN_CONTEXT_OBJECT_ACTIVE (1 << 3)
#define OW_WILD_DESPAWN_CONTEXT_EXACT_ID (1 << 4)
#define OW_WILD_DESPAWN_CONTEXT_EXACT_SCRIPT (1 << 5)
#define OW_WILD_BATTLE_RESULT_WIN 0x1
#define OW_WILD_BATTLE_RESULT_CAUGHT 0x4
#define OW_WILD_BATTLE_RESULT_PLAYER_FLED 0x5
#define OW_WILD_BATTLE_RESULT_TRY_FLEE 0x80
#define OW_WILD_HELPER_PAL_PARAM_SHINY 1
#define OW_WILD_HELPER_PAL_PARAM_ENABLE 2
#define OW_WILD_HELPER_NELEMS(array) (sizeof(array) / sizeof((array)[0]))
#define OverworldWildHelper_LoadHeadbuttDataByMapId(callbacks, context, mapId, offset, dest, size) \
    OverworldWildHelper_LoadArchiveData(callbacks, context, ARC_HEADBUTT_TREES, mapId, offset, dest, size)

typedef enum OverworldWildHelperFishingRodTable {
    OW_WILD_HELPER_FISHING_ROD_OLD,
    OW_WILD_HELPER_FISHING_ROD_GOOD,
    OW_WILD_HELPER_FISHING_ROD_SUPER,
} OverworldWildHelperFishingRodTable;

typedef struct OverworldWildHelperLandEncounterData {
    u8 levels[OW_WILD_HELPER_GRASS_SLOTS];
    u16 morningSpecies[OW_WILD_HELPER_GRASS_SLOTS];
    u16 daySpecies[OW_WILD_HELPER_GRASS_SLOTS];
    u16 nightSpecies[OW_WILD_HELPER_GRASS_SLOTS];
} OverworldWildHelperLandEncounterData;

typedef struct OverworldWildHelperEncounterDataSlot {
    u8 minLevel;
    u8 maxLevel;
    u16 species;
} OverworldWildHelperEncounterDataSlot;

typedef struct OverworldWildHelperEncounterData {
    u8 walkingRate;
    u8 surfingRate;
    u8 rockSmashRate;
    u8 oldRodRate;
    u8 goodRodRate;
    u8 superRodRate;
    u8 padding[2];
    OverworldWildHelperLandEncounterData landSlots;
    u16 hoennSoundsSpecies[2];
    u16 sinnohSoundsSpecies[2];
    OverworldWildHelperEncounterDataSlot surfSlots[OW_WILD_HELPER_SURF_SLOTS];
    OverworldWildHelperEncounterDataSlot rockSmashSlots[2];
    OverworldWildHelperEncounterDataSlot oldRodSlots[OW_WILD_HELPER_FISH_SLOTS];
    OverworldWildHelperEncounterDataSlot goodRodSlots[OW_WILD_HELPER_FISH_SLOTS];
    OverworldWildHelperEncounterDataSlot superRodSlots[OW_WILD_HELPER_FISH_SLOTS];
    u16 landSwarm;
    u16 surfSwarm;
    u16 nightFish;
    u16 fishSwarm;
} OverworldWildHelperEncounterData;

typedef struct OverworldWildHelperHeadbuttHeader {
    u16 normalTreeCount;
    u16 specialTreeCount;
} OverworldWildHelperHeadbuttHeader;

typedef struct OverworldWildHelperHeadbuttEncounterSlot {
    u16 species;
    u8 minLevel;
    u8 maxLevel;
} OverworldWildHelperHeadbuttEncounterSlot;

typedef struct OverworldWildHelperCoordOffset {
    s8 dx;
    s8 dy;
} OverworldWildHelperCoordOffset;

static const u8 sOverworldWildHelperGrassSlotWeights[OW_WILD_HELPER_GRASS_SLOTS] = {
    20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1,
};

static const u8 sOverworldWildHelperSurfSlotWeights[OW_WILD_HELPER_SURF_SLOTS] = {
    60, 30, 5, 4, 1,
};

static const u8 sOverworldWildHelperFishingSlotWeights[OW_WILD_HELPER_FISH_SLOTS] = {
    60, 30, 5, 4, 1,
};

static const OverworldWildHelperCoordOffset sOverworldWildHelperCardinalOffsets[] = {
    { 0, 1 },
    { 0, -1 },
    { -1, 0 },
    { 1, 0 },
};

#if OW_WILD_HELPER_BUDGETED_SPAWN_POSITION_SEARCH
// Stored as cursor + 1 so zero can mean uninitialized after the helper overlay is loaded.
static u16 sOverworldWildHelperSpawnPositionCursor[2];
#endif

static int OverworldWildHelper_Abs(int value)
{
    return value < 0 ? -value : value;
}

static int OverworldWildHelper_Max(int lhs, int rhs)
{
    return lhs > rhs ? lhs : rhs;
}

static int OverworldWildHelper_DirectionDeltaX(u8 direction)
{
    switch (direction) {
    case OW_WILD_HELPER_DIRECTION_LEFT:
        return -1;
    case OW_WILD_HELPER_DIRECTION_RIGHT:
        return 1;
    default:
        return 0;
    }
}

static int OverworldWildHelper_DirectionDeltaY(u8 direction)
{
    switch (direction) {
    case OW_WILD_HELPER_DIRECTION_UP:
        return -1;
    case OW_WILD_HELPER_DIRECTION_DOWN:
        return 1;
    default:
        return 0;
    }
}

static BOOL OverworldWildHelper_AreSpawnCallbacksValid(const OverworldWildHelperSpawnCallbacks *callbacks)
{
    const void * const *callbackFields = (const void * const *)callbacks;
    u32 callbackIndex;

    if (callbacks == NULL) {
        return FALSE;
    }

    for (callbackIndex = 0;
         callbackIndex < sizeof(*callbacks) / sizeof(callbackFields[0]);
         callbackIndex++) {
        if (callbackFields[callbackIndex] == NULL) {
            return FALSE;
        }
    }

    return TRUE;
}

static BOOL OverworldWildHelper_GetMapId(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    u16 *mapId)
{
    return callbacks->getMapId(context, mapId);
}

static BOOL OverworldWildHelper_LoadArchiveData(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    int arcId,
    int datId,
    int offset,
    void *dest,
    int size)
{
    return callbacks->loadArchiveData(context, arcId, datId, offset, dest, size);
}

static BOOL OverworldWildHelper_TryPickSpawnPosition(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain requestedTerrain,
    OverworldWildSpawnPosition *position)
{
    OverworldWildHelperPlayerState playerState;
#if OW_WILD_HELPER_BUDGETED_SPAWN_POSITION_SEARCH
    u16 *storedCursor;
    u32 cursor;
    u32 checked = 0;
    u32 visited = 0;

    if (!callbacks->getPlayerState(context, &playerState)) {
        return FALSE;
    }

    storedCursor = &sOverworldWildHelperSpawnPositionCursor[
        requestedTerrain == OW_WILD_SPAWN_TERRAIN_SURF];
    cursor = *storedCursor == 0
        ? gf_rand() % OW_WILD_HELPER_SPAWN_POSITION_TILE_COUNT
        : *storedCursor - 1;

    while (checked < OW_WILD_HELPER_SPAWN_POSITION_BUDGET
        && visited < OW_WILD_HELPER_SPAWN_POSITION_TILE_COUNT) {
        u32 candidate = cursor;
        int dx;
        int dy;
        int x;
        int y;
        OverworldWildSpawnTerrain terrain;

        cursor = (cursor + OW_WILD_HELPER_SPAWN_POSITION_STRIDE)
            % OW_WILD_HELPER_SPAWN_POSITION_TILE_COUNT;
        visited++;
        dx = candidate % OW_WILD_HELPER_SPAWN_POSITION_DIAMETER
            - OW_WILD_HELPER_SPAWN_MAX_DISTANCE;
        dy = candidate / OW_WILD_HELPER_SPAWN_POSITION_DIAMETER
            - OW_WILD_HELPER_SPAWN_MAX_DISTANCE;

        if (OverworldWildHelper_Max(
                OverworldWildHelper_Abs(dx),
                OverworldWildHelper_Abs(dy))
            < OW_WILD_HELPER_SPAWN_MIN_DISTANCE) {
            continue;
        }

        checked++;
        x = playerState.playerX + dx;
        y = playerState.playerY + dy;
        if (!callbacks->tryGetSpawnTerrain(context, x, y, &terrain)
            || terrain != requestedTerrain
            || callbacks->isTileOccupied(context, x, y)
            || callbacks->isNearActiveSpawn(
                context,
                x,
                y,
                OW_WILD_HELPER_SPAWN_MIN_MON_DISTANCE)) {
            continue;
        }

        position->startX = x;
        position->startY = y;
        *storedCursor = cursor + 1;
        return TRUE;
    }

    *storedCursor = cursor + 1;
    return FALSE;
#else
    u32 candidateCount = 0;
    int x;
    int y;

    if (!callbacks->getPlayerState(context, &playerState)) {
        return FALSE;
    }

    for (y = playerState.playerY - OW_WILD_HELPER_SPAWN_MAX_DISTANCE;
         y <= playerState.playerY + OW_WILD_HELPER_SPAWN_MAX_DISTANCE;
         y++) {
        for (x = playerState.playerX - OW_WILD_HELPER_SPAWN_MAX_DISTANCE;
             x <= playerState.playerX + OW_WILD_HELPER_SPAWN_MAX_DISTANCE;
             x++) {
            int dx = x - playerState.playerX;
            int dy = y - playerState.playerY;
            int distance = OverworldWildHelper_Max(
                OverworldWildHelper_Abs(dx),
                OverworldWildHelper_Abs(dy));
            OverworldWildSpawnTerrain terrain;

            if (distance < OW_WILD_HELPER_SPAWN_MIN_DISTANCE
                || distance > OW_WILD_HELPER_SPAWN_MAX_DISTANCE
                || !callbacks->tryGetSpawnTerrain(context, x, y, &terrain)
                || terrain != requestedTerrain
                || callbacks->isTileOccupied(context, x, y)
                || callbacks->isNearActiveSpawn(
                    context,
                    x,
                    y,
                    OW_WILD_HELPER_SPAWN_MIN_MON_DISTANCE)) {
                continue;
            }

            candidateCount++;
            if ((gf_rand() % candidateCount) == 0) {
                position->startX = x;
                position->startY = y;
            }
        }
    }

    return candidateCount != 0;
#endif
}

static BOOL OverworldWildHelper_TryPickFishingSpawnPosition(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnPosition *position)
{
    OverworldWildHelperPlayerState playerState;
    u32 start;
    u32 i;

    if (position == NULL
        || !callbacks->getPlayerState(context, &playerState)) {
        return FALSE;
    }

    start = gf_rand() & 3;
    for (i = 0; i < OW_WILD_HELPER_NELEMS(sOverworldWildHelperCardinalOffsets); i++) {
        const OverworldWildHelperCoordOffset *offset =
            &sOverworldWildHelperCardinalOffsets[(start + i) & 3];
        OverworldWildSpawnTerrain terrain;
        int x = playerState.playerX + offset->dx;
        int y = playerState.playerY + offset->dy;

        if (!callbacks->tryGetSpawnTerrain(context, x, y, &terrain)
            || terrain != OW_WILD_SPAWN_TERRAIN_SURF
            || callbacks->isTileOccupied(context, x, y)) {
            continue;
        }

        position->startX = x;
        position->startY = y;
        return TRUE;
    }

    return FALSE;
}

static BOOL OverworldWildHelper_TryPickHeadbuttEncounterPool(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    u8 *treeType)
{
    OverworldWildHelperHeadbuttHeader header;
    u32 treeCount;
    u16 mapId;

    if (treeType == NULL
        || !OverworldWildHelper_GetMapId(callbacks, context, &mapId)
        || !OverworldWildHelper_LoadHeadbuttDataByMapId(
            callbacks,
            context,
            mapId,
            0,
            &header,
            sizeof(header))) {
        return FALSE;
    }

    treeCount = header.normalTreeCount + header.specialTreeCount;
    if (treeCount == 0) {
        return FALSE;
    }

    *treeType = (gf_rand() % treeCount) < header.normalTreeCount
        ? OW_WILD_HELPER_HEADBUTT_NORMAL_TREE
        : OW_WILD_HELPER_HEADBUTT_SPECIAL_TREE;
    return TRUE;
}

static BOOL OverworldWildHelper_TryPickSpawnPositionForTerrain(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    OverworldWildSpawnPosition *position)
{
    if (position == NULL) {
        return FALSE;
    }
    if (terrain == OW_WILD_SPAWN_TERRAIN_HEADBUTT) {
        return OverworldWildHelper_TryPickHeadbuttEncounterPool(
            callbacks,
            context,
            &position->headbuttTreeType);
    }
    if (terrain == OW_WILD_SPAWN_TERRAIN_FISHING) {
        return OverworldWildHelper_TryPickFishingSpawnPosition(callbacks, context, position);
    }
    return OverworldWildHelper_TryPickSpawnPosition(callbacks, context, terrain, position);
}

static u8 OverworldWildHelper_RollWeightedSlot(const u8 *weights, u8 count)
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

static BOOL OverworldWildHelper_TryRollHeadbuttEncounter(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    u8 treeType,
    OverworldWildRolledEncounter *encounter)
{
    int attempts;
    u32 slotOffset = sizeof(OverworldWildHelperHeadbuttHeader);
    u8 slotCount = OW_WILD_HELPER_HEADBUTT_NORMAL_SLOTS;
    u16 mapId;

    if (encounter == NULL
        || !OverworldWildHelper_GetMapId(callbacks, context, &mapId)) {
        return FALSE;
    }

    if (treeType == OW_WILD_HELPER_HEADBUTT_SPECIAL_TREE) {
        slotOffset += OW_WILD_HELPER_HEADBUTT_NORMAL_SLOTS
            * sizeof(OverworldWildHelperHeadbuttEncounterSlot);
        slotCount = OW_WILD_HELPER_HEADBUTT_SPECIAL_SLOTS;
    }

    for (attempts = 0; attempts < slotCount; attempts++) {
        OverworldWildHelperHeadbuttEncounterSlot slot;
        u32 slotIndex = gf_rand() % slotCount;
        u16 species;

        if (!OverworldWildHelper_LoadHeadbuttDataByMapId(
                callbacks,
                context,
                mapId,
                slotOffset + slotIndex * sizeof(slot),
                &slot,
                sizeof(slot))) {
            return FALSE;
        }

        species = slot.species & OW_WILD_HELPER_SPECIES_MASK;
        if (species != SPECIES_NONE && slot.minLevel != 0) {
            encounter->species = species;
            encounter->form = slot.species >> OW_WILD_HELPER_FORM_SHIFT;
            encounter->level = slot.minLevel;
            if (slot.maxLevel > slot.minLevel) {
                encounter->level += gf_rand() % (slot.maxLevel - slot.minLevel + 1);
            }
            return TRUE;
        }
    }

    if (treeType == OW_WILD_HELPER_HEADBUTT_SPECIAL_TREE) {
        return OverworldWildHelper_TryRollHeadbuttEncounter(
            callbacks,
            context,
            OW_WILD_HELPER_HEADBUTT_NORMAL_TREE,
            encounter);
    }

    return FALSE;
}

static const u16 *OverworldWildHelper_GetTimeOfDaySpeciesTable(
    const OverworldWildHelperLandEncounterData *landSlots)
{
    if ((gf_rand() % 100) < OW_WILD_HELPER_RANDOM_TIME_TABLE_CHANCE_PERCENT) {
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

static BOOL OverworldWildHelper_TryRollLandEncounter(
    const OverworldWildHelperEncounterData *encounterData,
    OverworldWildRolledEncounter *encounter)
{
    int attempts;
    const u16 *speciesTable;

    speciesTable = OverworldWildHelper_GetTimeOfDaySpeciesTable(&encounterData->landSlots);

    for (attempts = 0; attempts < OW_WILD_HELPER_GRASS_SLOTS; attempts++) {
        u8 slot = OverworldWildHelper_RollWeightedSlot(
            sOverworldWildHelperGrassSlotWeights,
            OW_WILD_HELPER_GRASS_SLOTS);
        u16 encodedSpecies = speciesTable[slot];
        u16 species = encodedSpecies & OW_WILD_HELPER_SPECIES_MASK;

        if (species != SPECIES_NONE && encounterData->landSlots.levels[slot] != 0) {
            encounter->species = species;
            encounter->form = encodedSpecies >> OW_WILD_HELPER_FORM_SHIFT;
            encounter->level = encounterData->landSlots.levels[slot];
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildHelper_TryRollSurfEncounter(
    const OverworldWildHelperEncounterData *encounterData,
    OverworldWildRolledEncounter *encounter)
{
    int attempts;

    for (attempts = 0; attempts < OW_WILD_HELPER_SURF_SLOTS; attempts++) {
        u8 slot = OverworldWildHelper_RollWeightedSlot(
            sOverworldWildHelperSurfSlotWeights,
            OW_WILD_HELPER_SURF_SLOTS);
        u16 encodedSpecies = encounterData->surfSlots[slot].species;
        u16 species = encodedSpecies & OW_WILD_HELPER_SPECIES_MASK;

        if (species != SPECIES_NONE && encounterData->surfSlots[slot].minLevel != 0) {
            u8 minLevel = encounterData->surfSlots[slot].minLevel;
            u8 maxLevel = encounterData->surfSlots[slot].maxLevel;

            encounter->species = species;
            encounter->form = encodedSpecies >> OW_WILD_HELPER_FORM_SHIFT;
            encounter->level = minLevel;
            if (maxLevel > minLevel) {
                encounter->level += gf_rand() % (maxLevel - minLevel + 1);
            }
            return TRUE;
        }
    }

    return FALSE;
}

static const OverworldWildHelperEncounterDataSlot *OverworldWildHelper_GetFishingSlots(
    const OverworldWildHelperEncounterData *encounterData,
    OverworldWildHelperFishingRodTable rodTable)
{
    switch (rodTable) {
    case OW_WILD_HELPER_FISHING_ROD_OLD:
        return encounterData->oldRodSlots;
    case OW_WILD_HELPER_FISHING_ROD_GOOD:
        return encounterData->goodRodSlots;
    case OW_WILD_HELPER_FISHING_ROD_SUPER:
    default:
        return encounterData->superRodSlots;
    }
}

static u8 OverworldWildHelper_GetFishingRate(
    const OverworldWildHelperEncounterData *encounterData,
    OverworldWildHelperFishingRodTable rodTable)
{
    switch (rodTable) {
    case OW_WILD_HELPER_FISHING_ROD_OLD:
        return encounterData->oldRodRate;
    case OW_WILD_HELPER_FISHING_ROD_GOOD:
        return encounterData->goodRodRate;
    case OW_WILD_HELPER_FISHING_ROD_SUPER:
    default:
        return encounterData->superRodRate;
    }
}

static BOOL OverworldWildHelper_FishingTableHasValidSlot(
    const OverworldWildHelperEncounterDataSlot *slots)
{
    u8 slot;

    for (slot = 0; slot < OW_WILD_HELPER_FISH_SLOTS; slot++) {
        if ((slots[slot].species & OW_WILD_HELPER_SPECIES_MASK) != SPECIES_NONE
            && slots[slot].minLevel != 0) {
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildHelper_TryPickFishingRodTable(
    const OverworldWildHelperEncounterData *encounterData,
    OverworldWildHelperFishingRodTable *rodTable)
{
    u16 totalRate = 0;
    u16 roll;
    u8 rod;

    for (rod = 0; rod < 3; rod++) {
        OverworldWildHelperFishingRodTable currentRod =
            (OverworldWildHelperFishingRodTable)rod;
        const OverworldWildHelperEncounterDataSlot *slots =
            OverworldWildHelper_GetFishingSlots(encounterData, currentRod);
        u8 rate = OverworldWildHelper_GetFishingRate(encounterData, currentRod);

        if (rate != 0 && OverworldWildHelper_FishingTableHasValidSlot(slots)) {
            totalRate += rate;
        }
    }

    if (totalRate == 0) {
        return FALSE;
    }

    roll = gf_rand() % totalRate;
    for (rod = 0; rod < 3; rod++) {
        OverworldWildHelperFishingRodTable currentRod =
            (OverworldWildHelperFishingRodTable)rod;
        const OverworldWildHelperEncounterDataSlot *slots =
            OverworldWildHelper_GetFishingSlots(encounterData, currentRod);
        u8 rate = OverworldWildHelper_GetFishingRate(encounterData, currentRod);

        if (rate == 0 || !OverworldWildHelper_FishingTableHasValidSlot(slots)) {
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

static BOOL OverworldWildHelper_TryRollFishingEncounter(
    const OverworldWildHelperEncounterData *encounterData,
    OverworldWildRolledEncounter *encounter)
{
    OverworldWildHelperFishingRodTable rodTable;
    const OverworldWildHelperEncounterDataSlot *slots;
    int attempts;

    if (!OverworldWildHelper_TryPickFishingRodTable(encounterData, &rodTable)) {
        return FALSE;
    }

    slots = OverworldWildHelper_GetFishingSlots(encounterData, rodTable);
    for (attempts = 0; attempts < OW_WILD_HELPER_FISH_SLOTS; attempts++) {
        u8 slot = OverworldWildHelper_RollWeightedSlot(
            sOverworldWildHelperFishingSlotWeights,
            OW_WILD_HELPER_FISH_SLOTS);
        u16 encodedSpecies = slots[slot].species;
        u16 species = encodedSpecies & OW_WILD_HELPER_SPECIES_MASK;

        if (species != SPECIES_NONE && slots[slot].minLevel != 0) {
            u8 minLevel = slots[slot].minLevel;
            u8 maxLevel = slots[slot].maxLevel;

            encounter->species = species;
            encounter->form = encodedSpecies >> OW_WILD_HELPER_FORM_SHIFT;
            encounter->level = minLevel;
            if (maxLevel > minLevel) {
                encounter->level += gf_rand() % (maxLevel - minLevel + 1);
            }
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildHelper_TryRollEncounter(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    OverworldWildRolledEncounter *encounter)
{
    int encounterDataId;
    OverworldWildHelperEncounterData encounterData;

    if (encounter == NULL
        || !callbacks->tryGetEncounterDataId(context, &encounterDataId)
        || !OverworldWildHelper_LoadArchiveData(
            callbacks,
            context,
            ARC_ENCOUNTERS,
            encounterDataId,
            0,
            &encounterData,
            sizeof(encounterData))) {
        return FALSE;
    }

    if (terrain == OW_WILD_SPAWN_TERRAIN_SURF) {
        return OverworldWildHelper_TryRollSurfEncounter(&encounterData, encounter);
    }
    if (terrain == OW_WILD_SPAWN_TERRAIN_FISHING) {
        return OverworldWildHelper_TryRollFishingEncounter(&encounterData, encounter);
    }
    return OverworldWildHelper_TryRollLandEncounter(&encounterData, encounter);
}

static BOOL OverworldWildHelper_RollShiny(BOOL shinyAlreadySpawned, u16 shinyOddsDenominator)
{
    if (shinyAlreadySpawned) {
        return FALSE;
    }

    return (gf_rand() % shinyOddsDenominator) == 0;
}

static u32 OverworldWildHelper_RollPersonality(void)
{
    return gf_rand() | (gf_rand() << 16);
}

static u32 OverworldWildHelper_MakePersonalityShiny(u32 personality)
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

static BOOL OverworldWildHelper_TryPrepareSpawnEncounter(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    const OverworldWildSpawnPosition *position,
    BOOL shinyAlreadySpawned,
    u16 shinyOddsDenominator,
    OverworldWildRolledEncounter *encounter,
    int *savedShinySlot,
    BOOL *shiny)
{
    *savedShinySlot = callbacks->findSavedShiny(context, terrain);
    if (*savedShinySlot >= 0) {
        callbacks->loadSavedShiny(context, *savedShinySlot, encounter);
        *shiny = TRUE;
    } else {
        if (terrain == OW_WILD_SPAWN_TERRAIN_HEADBUTT) {
            if (!OverworldWildHelper_TryRollHeadbuttEncounter(
                    callbacks,
                    context,
                    position->headbuttTreeType,
                    encounter)) {
                return FALSE;
            }
        } else if (!OverworldWildHelper_TryRollEncounter(callbacks, context, terrain, encounter)) {
            return FALSE;
        }

        encounter->personality = OverworldWildHelper_RollPersonality();
        *shiny = OverworldWildHelper_RollShiny(shinyAlreadySpawned, shinyOddsDenominator);
        if (*shiny) {
            encounter->personality = OverworldWildHelper_MakePersonalityShiny(encounter->personality);
        }
    }

    if (encounter->species == SPECIES_NONE || encounter->level == 0) {
        return FALSE;
    }

    return TRUE;
}

static BOOL OverworldWildHelper_CopyPreparedSpawn(
    const OverworldWildSpawnPosition *position,
    const OverworldWildRolledEncounter *encounter,
    BOOL shiny,
    int savedShinySlot,
    OverworldWildPreparedSpawn *prepared)
{
    if (encounter->species == SPECIES_NONE
        || encounter->level == 0) {
        return FALSE;
    }

    prepared->position = *position;
    prepared->encounter = *encounter;
    prepared->savedShinySlot = savedShinySlot;
    prepared->shiny = shiny;
    prepared->shinyCounterEligible = FALSE;
    prepared->behaviorLimitKey = 0;
    prepared->behaviorProfile = (OverworldWildBehaviorProfile){ 0 };
    prepared->startup = (OverworldWildSpawnStartup){ 0 };
    prepared->behaviorClass = 0;
    return TRUE;
}

static BOOL OverworldWildHelper_TryPrepareSpawn(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    int slot,
    BOOL shinyAlreadySpawned,
    u16 shinyOddsDenominator,
    OverworldWildPreparedSpawn *prepared)
{
    OverworldWildRolledEncounter encounter;
    OverworldWildSpawnPosition position = { 0 };
    int savedShinySlot;
    BOOL shiny;

    if (!OverworldWildHelper_AreSpawnCallbacksValid(callbacks)
        || prepared == NULL
        || !OverworldWildHelper_TryPickSpawnPositionForTerrain(
            callbacks,
            context,
            terrain,
            &position)
        || !OverworldWildHelper_TryPrepareSpawnEncounter(
            callbacks,
            context,
            terrain,
            &position,
            shinyAlreadySpawned,
            shinyOddsDenominator,
            &encounter,
            &savedShinySlot,
            &shiny)) {
        return FALSE;
    }

    (void)terrain;
    (void)slot;
    return OverworldWildHelper_CopyPreparedSpawn(
        &position,
        &encounter,
        shiny,
        savedShinySlot,
        prepared);
}

static BOOL OverworldWildHelper_TryPrepareEncounterSpawn(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    int slot,
    const OverworldWildRolledEncounter *encounter,
    BOOL shiny,
    int savedShinySlot,
    BOOL rollPersonality,
    OverworldWildPreparedSpawn *prepared)
{
    OverworldWildRolledEncounter rolledEncounter;
    OverworldWildSpawnPosition position = { 0 };

    if (!OverworldWildHelper_AreSpawnCallbacksValid(callbacks)
        || prepared == NULL
        || encounter == NULL
        || !OverworldWildHelper_TryPickSpawnPositionForTerrain(
            callbacks,
            context,
            terrain,
            &position)) {
        return FALSE;
    }

    rolledEncounter = *encounter;
    if (rollPersonality) {
        rolledEncounter.personality = OverworldWildHelper_RollPersonality();
    }

    (void)terrain;
    (void)slot;
    return OverworldWildHelper_CopyPreparedSpawn(
        &position,
        &rolledEncounter,
        shiny,
        savedShinySlot,
        prepared);
}

static int OverworldWildHelper_BuildDirections(int dx, int dy, u8 *directions)
{
    int count = 0;

    if (directions == NULL || (dx == 0 && dy == 0)) {
        return 0;
    }

    if (OverworldWildHelper_Abs(dx) >= OverworldWildHelper_Abs(dy)) {
        if (dx > 0) {
            directions[count++] = OW_WILD_HELPER_DIRECTION_RIGHT;
        }
        if (dx < 0 && count < 4) {
            directions[count++] = OW_WILD_HELPER_DIRECTION_LEFT;
        }
        if (dy > 0 && count < 4) {
            directions[count++] = OW_WILD_HELPER_DIRECTION_DOWN;
        }
        if (dy < 0 && count < 4) {
            directions[count++] = OW_WILD_HELPER_DIRECTION_UP;
        }
        return count;
    }

    if (dy > 0) {
        directions[count++] = OW_WILD_HELPER_DIRECTION_DOWN;
    }
    if (dy < 0 && count < 4) {
        directions[count++] = OW_WILD_HELPER_DIRECTION_UP;
    }
    if (dx > 0 && count < 4) {
        directions[count++] = OW_WILD_HELPER_DIRECTION_RIGHT;
    }
    if (dx < 0 && count < 4) {
        directions[count++] = OW_WILD_HELPER_DIRECTION_LEFT;
    }

    return count;
}

static BOOL OverworldWildHelper_IsHopVectorShape(
    const OverworldWildHelperHopConfig *config,
    int dx,
    int dy)
{
    int absDx = OverworldWildHelper_Abs(dx);
    int absDy = OverworldWildHelper_Abs(dy);

    if (absDx == 0 && absDy == 0) {
        return FALSE;
    }
    if (absDx == 0 || absDy == 0) {
        return TRUE;
    }
    return config != NULL
        && config->allowNonCardinal
        && absDx == absDy;
}

static BOOL OverworldWildHelper_TryGetHopVector(
    const OverworldWildHelperHopConfig *config,
    int dx,
    int dy,
    u8 *direction,
    u8 *distance)
{
    int jumpDistance;
    u8 directions[4];

    if (config == NULL
        || config->minDistance == 0
        || config->maxDistance < config->minDistance
        || !OverworldWildHelper_IsHopVectorShape(config, dx, dy)
        || OverworldWildHelper_BuildDirections(dx, dy, directions) == 0) {
        return FALSE;
    }

    jumpDistance = OverworldWildHelper_Max(
        OverworldWildHelper_Abs(dx),
        OverworldWildHelper_Abs(dy));
    if (jumpDistance < config->minDistance || jumpDistance > config->maxDistance) {
        return FALSE;
    }

    if (direction != NULL) {
        *direction = directions[0];
    }
    if (distance != NULL) {
        *distance = (u8)jumpDistance;
    }
    return TRUE;
}

static BOOL OverworldWildHelper_IsLandingAllowed(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    int landingX,
    int landingY)
{
    return config != NULL
        && validator != NULL
        && validator(
            landingX,
            landingY,
            config->targetX,
            config->targetY,
            context);
}

static BOOL OverworldWildHelper_SetHopResult(
    const OverworldWildHelperHopConfig *config,
    int landingX,
    int landingY,
    int finalTargetX,
    int finalTargetY,
    u8 flags,
    OverworldWildHelperHopResult *result)
{
    u8 direction;
    u8 distance;

    if (config == NULL
        || result == NULL
        || !OverworldWildHelper_TryGetHopVector(
            config,
            landingX - config->objectX,
            landingY - config->objectY,
            &direction,
            &distance)) {
        return FALSE;
    }

    result->landingX = landingX;
    result->landingY = landingY;
    result->finalTargetX = finalTargetX;
    result->finalTargetY = finalTargetY;
    result->direction = direction;
    result->distance = distance;
    result->flags = flags;
    result->reserved = 0;
    return TRUE;
}

static void OverworldWildHelper_AddHopPlanDirection(
    s8 *stepXs,
    s8 *stepYs,
    int *directionCount,
    int stepX,
    int stepY)
{
    int i;

    if (stepXs == NULL
        || stepYs == NULL
        || directionCount == NULL
        || (stepX == 0 && stepY == 0)) {
        return;
    }

    for (i = 0; i < *directionCount; i++) {
        if (stepXs[i] == stepX && stepYs[i] == stepY) {
            return;
        }
    }

    if (*directionCount >= OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS) {
        return;
    }

    stepXs[*directionCount] = (s8)stepX;
    stepYs[*directionCount] = (s8)stepY;
    (*directionCount)++;
}

static int OverworldWildHelper_BuildHopPlanDirections(
    const OverworldWildHelperHopConfig *config,
    int fromX,
    int fromY,
    s8 *stepXs,
    s8 *stepYs)
{
    int directionCount = 0;
    int dx;
    int dy;
    u8 targetDirections[4];
    int targetDirectionCount;
    int i;

    if (config == NULL || stepXs == NULL || stepYs == NULL) {
        return 0;
    }

    dx = config->targetX - fromX;
    dy = config->targetY - fromY;
    if (config->allowNonCardinal && dx != 0 && dy != 0) {
        OverworldWildHelper_AddHopPlanDirection(
            stepXs,
            stepYs,
            &directionCount,
            dx > 0 ? 1 : -1,
            dy > 0 ? 1 : -1);
    }

    targetDirectionCount = OverworldWildHelper_BuildDirections(
        dx,
        dy,
        targetDirections);
    for (i = 0; i < targetDirectionCount; i++) {
        OverworldWildHelper_AddHopPlanDirection(
            stepXs,
            stepYs,
            &directionCount,
            OverworldWildHelper_DirectionDeltaX(targetDirections[i]),
            OverworldWildHelper_DirectionDeltaY(targetDirections[i]));
    }

    for (i = 0; i < config->directionCount; i++) {
        OverworldWildHelper_AddHopPlanDirection(
            stepXs,
            stepYs,
            &directionCount,
            OverworldWildHelper_DirectionDeltaX(config->directions[i]),
            OverworldWildHelper_DirectionDeltaY(config->directions[i]));
    }

    OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 1, 0);
    OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, -1, 0);
    OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 0, 1);
    OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 0, -1);

    if (config->allowNonCardinal) {
        OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 1, 1);
        OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 1, -1);
        OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, -1, 1);
        OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, -1, -1);
    }

    return directionCount;
}

static int OverworldWildHelper_GetHopPlanDistance(
    int x,
    int y,
    int targetX,
    int targetY)
{
    return OverworldWildHelper_Max(
        OverworldWildHelper_Abs(targetX - x),
        OverworldWildHelper_Abs(targetY - y));
}

static BOOL OverworldWildHelper_IsHopTargetOneHopAway(
    const OverworldWildHelperHopConfig *config,
    int fromX,
    int fromY,
    int targetX,
    int targetY)
{
    return OverworldWildHelper_TryGetHopVector(
        config,
        targetX - fromX,
        targetY - fromY,
        NULL,
        NULL);
}

static BOOL OverworldWildHelper_HopPlanHasVisited(
    const s16 *nodeXs,
    const s16 *nodeYs,
    int nodeCount,
    int x,
    int y)
{
    int i;

    for (i = 0; i < nodeCount; i++) {
        if (nodeXs[i] == x && nodeYs[i] == y) {
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildHelper_IsHopPlanCandidate(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    int fromX,
    int fromY,
    int toX,
    int toY)
{
    return OverworldWildHelper_TryGetHopVector(
            config,
            toX - fromX,
            toY - fromY,
            NULL,
            NULL)
        && OverworldWildHelper_IsLandingAllowed(
            config,
            validator,
            context,
            toX,
            toY);
}

static BOOL OverworldWildHelper_PickRandomBehaviorHop(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    OverworldWildHelperHopResult *result)
{
    int dx;
    int dy;
    int targetX = 0;
    int targetY = 0;
    u32 candidateCount = 0;

    if (config == NULL
        || validator == NULL
        || result == NULL
        || config->minDistance == 0
        || config->maxDistance < config->minDistance) {
        return FALSE;
    }

    for (dy = -config->maxDistance; dy <= config->maxDistance; dy++) {
        for (dx = -config->maxDistance; dx <= config->maxDistance; dx++) {
            int candidateX;
            int candidateY;

            if (dx == 0 && dy == 0) {
                continue;
            }

            candidateX = config->objectX + dx;
            candidateY = config->objectY + dy;
            if (!OverworldWildHelper_TryGetHopVector(config, dx, dy, NULL, NULL)
                || !OverworldWildHelper_IsLandingAllowed(
                    config,
                    validator,
                    context,
                    candidateX,
                    candidateY)) {
                continue;
            }

            candidateCount++;
            if ((gf_rand() % candidateCount) == 0) {
                targetX = candidateX;
                targetY = candidateY;
            }
        }
    }

    if (candidateCount == 0) {
        return FALSE;
    }

    return OverworldWildHelper_SetHopResult(
        config,
        targetX,
        targetY,
        targetX,
        targetY,
        OW_WILD_HELPER_HOP_RESULT_FLAG_DIRECT,
        result);
}

static BOOL OverworldWildHelper_PlanBehaviorHopStep(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    OverworldWildHelperHopResult *result)
{
    s16 nodeXs[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    s16 nodeYs[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    s16 firstXs[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    s16 firstYs[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    u8 nodeDepths[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    int head = 0;
    int tail = 0;
    int bestFirstX = 0;
    int bestFirstY = 0;
    int bestTerminalX = 0;
    int bestTerminalY = 0;
    int bestDistance = 0x7FFF;
    u8 bestDepth = 0xFF;
    BOOL bestFound = FALSE;

    if (config == NULL
        || validator == NULL
        || result == NULL
        || config->minDistance == 0
        || config->maxDistance < config->minDistance) {
        return FALSE;
    }

    if ((config->stopOneHopAway
            || !OverworldWildHelper_IsLandingAllowed(
                config,
                validator,
                context,
                config->targetX,
                config->targetY))
        && (config->objectX != config->targetX || config->objectY != config->targetY)
        && OverworldWildHelper_IsHopTargetOneHopAway(
            config,
            config->objectX,
            config->objectY,
            config->targetX,
            config->targetY)) {
        return FALSE;
    }

    nodeXs[tail] = (s16)config->objectX;
    nodeYs[tail] = (s16)config->objectY;
    firstXs[tail] = (s16)config->objectX;
    firstYs[tail] = (s16)config->objectY;
    nodeDepths[tail] = 0;
    tail++;

    while (head < tail) {
        int fromX = nodeXs[head];
        int fromY = nodeYs[head];
        int nodeDistance = OverworldWildHelper_GetHopPlanDistance(
            fromX,
            fromY,
            config->targetX,
            config->targetY);
        s8 stepXs[OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS];
        s8 stepYs[OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS];
        int planDirectionCount = OverworldWildHelper_BuildHopPlanDirections(
            config,
            fromX,
            fromY,
            stepXs,
            stepYs);
        int directionIndex;

        if (nodeDepths[head] >= OW_WILD_HELPER_HOP_PLAN_MAX_HOPS) {
            head++;
            continue;
        }

        for (directionIndex = 0; directionIndex < planDirectionCount; directionIndex++) {
            int stepX = stepXs[directionIndex];
            int stepY = stepYs[directionIndex];
            int distance;

            for (distance = config->maxDistance; distance >= config->minDistance; distance--) {
                int landingX = fromX + stepX * distance;
                int landingY = fromY + stepY * distance;
                int landingDistance = OverworldWildHelper_GetHopPlanDistance(
                    landingX,
                    landingY,
                    config->targetX,
                    config->targetY);
                int firstX = nodeDepths[head] == 0 ? landingX : firstXs[head];
                int firstY = nodeDepths[head] == 0 ? landingY : firstYs[head];
                BOOL landingIsTarget;
                BOOL landingCanReachTarget;

                if (landingDistance >= nodeDistance) {
                    continue;
                }
                if (!OverworldWildHelper_IsHopPlanCandidate(
                        config,
                        validator,
                        context,
                        fromX,
                        fromY,
                        landingX,
                        landingY)) {
                    continue;
                }

                landingIsTarget = landingX == config->targetX
                    && landingY == config->targetY;
                landingCanReachTarget =
                    !landingIsTarget
                    && OverworldWildHelper_IsHopTargetOneHopAway(
                        config,
                        landingX,
                        landingY,
                        config->targetX,
                        config->targetY);

                if (!bestFound
                    || landingDistance < bestDistance
                    || (landingDistance == bestDistance
                        && nodeDepths[head] + 1 < bestDepth)) {
                    bestFound = TRUE;
                    bestFirstX = firstX;
                    bestFirstY = firstY;
                    bestTerminalX = firstX;
                    bestTerminalY = firstY;
                    bestDistance = landingDistance;
                    bestDepth = nodeDepths[head] + 1;
                }

                if ((!config->stopOneHopAway && landingIsTarget)
                    || (config->stopOneHopAway && landingCanReachTarget)) {
                    return OverworldWildHelper_SetHopResult(
                        config,
                        firstX,
                        firstY,
                        landingX,
                        landingY,
                        OW_WILD_HELPER_HOP_RESULT_FLAG_PLANNED,
                        result);
                }

                if (config->stopOneHopAway && landingIsTarget) {
                    continue;
                }

                if (nodeDepths[head] + 1 >= OW_WILD_HELPER_HOP_PLAN_MAX_HOPS
                    || tail >= OW_WILD_HELPER_HOP_PLAN_NODE_COUNT
                    || OverworldWildHelper_HopPlanHasVisited(
                        nodeXs,
                        nodeYs,
                        tail,
                        landingX,
                        landingY)) {
                    continue;
                }

                nodeXs[tail] = (s16)landingX;
                nodeYs[tail] = (s16)landingY;
                firstXs[tail] = (s16)firstX;
                firstYs[tail] = (s16)firstY;
                nodeDepths[tail] = nodeDepths[head] + 1;
                tail++;
            }
        }

        head++;
    }

    if (!bestFound) {
        return FALSE;
    }

    return OverworldWildHelper_SetHopResult(
        config,
        bestFirstX,
        bestFirstY,
        bestTerminalX,
        bestTerminalY,
        OW_WILD_HELPER_HOP_RESULT_FLAG_PLANNED,
        result);
}

static BOOL OverworldWildHelper_IsContextCurrent(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    MapObjectMan *manager;

    if (fieldSystem == NULL
        || state == NULL
        || fieldSystem->location == NULL
        || fieldSystem->mapObjectMan == NULL) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    return state->mapId == fieldSystem->location->mapId
        && state->mapObjectMan == manager
        && state->mapObjects == manager->objects;
}

static BOOL OverworldWildHelper_IsExactObject(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot)
{
    MapObjectMan *manager;
    LocalMapObject *object;
    BOOL pointerFound = FALSE;
    int i;

    if (slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !OverworldWildHelper_IsContextCurrent(fieldSystem, state)
        || !state->spawns[slot].active
        || state->spawns[slot].mapId != fieldSystem->location->mapId
        || state->spawns[slot].objectId != OW_WILD_OBJECT_ID_START + slot) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    object = state->spawns[slot].object;
    for (i = 0; object != NULL && i < (int)manager->object_count; i++) {
        if (object == &manager->objects[i]) {
            pointerFound = TRUE;
            break;
        }
    }
    return pointerFound
        && (object->flags & MAPOBJECTFLAG_ACTIVE) != 0
        && object->id == state->spawns[slot].objectId
        && object->scriptId == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT;
}

static BOOL OverworldWildHelper_IsPresentationContextCurrent(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    return fieldSystem == gFieldSysPtr
        && OverworldWildHelper_IsContextCurrent(fieldSystem, state);
}

static void OverworldWildHelper_NormalizeThrowPresentation(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot)
{
    LocalMapObject *object;
    int x;
    int y;

    if (!OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
        || !OverworldWildHelper_IsExactObject(fieldSystem, state, slot)) {
        return;
    }

    object = state->spawns[slot].object;
    x = MapObject_GetCurrentX(object);
    y = MapObject_GetCurrentY(object);
    MapObject_SetCurrentX(object, (u32)x);
    MapObject_SetCurrentY(object, (u32)y);
    object->xInit = x;
    object->yInit = y;
    object->xPrev = x;
    object->yPrev = y;
    object->posVec[0] = (u32)((s32)x * 0x10000 + 0x8000);
    object->posVec[2] = (u32)((s32)y * 0x10000 + 0x8000);
    (void)MapObject_RefreshHeightFromTerrain(object);
    object->faceVec[0] = 0;
    object->faceVec[1] = 0;
    object->faceVec[2] = 0;
    object->unk88[1] = 0;
    object->unk94[1] = 0;
    MapObject_ClearBits(
        object,
        BIT_VANISH | MAPOBJECTFLAG_UNK18);
}

static void OverworldWildHelper_SyncCarriedThrowTarget(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    int carrierSlot,
    int targetSlot)
{
    LocalMapObject *carrierObject;
    LocalMapObject *targetObject;

    if (presentation == NULL
        || !OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
        || !OverworldWildHelper_IsExactObject(fieldSystem, state, carrierSlot)
        || !OverworldWildHelper_IsExactObject(fieldSystem, state, targetSlot)) {
        return;
    }

    carrierObject = state->spawns[carrierSlot].object;
    targetObject = state->spawns[targetSlot].object;
    targetObject->xCurr = carrierObject->xCurr;
    targetObject->yCurr = carrierObject->yCurr;
    targetObject->hCurr = carrierObject->hCurr;
    targetObject->xPrev = carrierObject->xPrev;
    targetObject->yPrev = carrierObject->yPrev;
    targetObject->hPrev = carrierObject->hPrev;
    targetObject->posVec[0] = carrierObject->posVec[0];
    targetObject->posVec[1] = carrierObject->posVec[1];
    targetObject->posVec[2] = carrierObject->posVec[2];
    targetObject->faceVec[0] = carrierObject->faceVec[0];
    targetObject->faceVec[1] =
        carrierObject->faceVec[1] + OW_WILD_HELPER_THROW_CARRIED_Y_OFFSET_FX32;
    targetObject->faceVec[2] = carrierObject->faceVec[2];
    targetObject->unk88[0] = carrierObject->unk88[0];
    targetObject->unk88[1] =
        carrierObject->unk88[1] + OW_WILD_HELPER_THROW_CARRIED_Y_OFFSET_FX32;
    targetObject->unk88[2] = carrierObject->unk88[2];
    targetObject->unk94[0] = carrierObject->unk94[0];
    targetObject->unk94[1] = carrierObject->unk94[1];
    targetObject->unk94[2] = carrierObject->unk94[2];
    MapObject_SetBits(targetObject, MAPOBJECTFLAG_UNK18);
    MapObject_ClearBits(targetObject, BIT_VANISH);
    presentation->lastKnownX[carrierSlot] = (s16)MapObject_GetCurrentX(carrierObject);
    presentation->lastKnownY[carrierSlot] = (s16)MapObject_GetCurrentY(carrierObject);
    presentation->lastKnownX[targetSlot] = presentation->lastKnownX[carrierSlot];
    presentation->lastKnownY[targetSlot] = presentation->lastKnownY[carrierSlot];
}

static BOOL OverworldWildHelper_ConfirmDistanceDespawn(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    int slot,
    BOOL movementProtected,
    u8 *distance)
{
    LocalMapObject *object;
    int dx;
    int dy;
    int measured;

    if (state == NULL
        || fieldSystem == NULL
        || presentation == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || state->spawns[slot].shiny
        || movementProtected
        || fieldSystem->playerAvatar == NULL
        || !OverworldWildHelper_IsExactObject(fieldSystem, state, slot)) {
        if (state != NULL
            && presentation != NULL
            && slot >= 0
            && slot < OW_WILD_MAX_SPAWNS) {
            presentation->farSamples[slot] = 0;
        }
        return FALSE;
    }
    object = state->spawns[slot].object;
    presentation->lastKnownX[slot] = (s16)MapObject_GetCurrentX(object);
    presentation->lastKnownY[slot] = (s16)MapObject_GetCurrentY(object);
    dx = presentation->lastKnownX[slot] - GetPlayerXCoord(fieldSystem->playerAvatar);
    dy = presentation->lastKnownY[slot] - GetPlayerYCoord(fieldSystem->playerAvatar);
    dx = dx < 0 ? -dx : dx;
    dy = dy < 0 ? -dy : dy;
    measured = dx > dy ? dx : dy;
    if (distance != NULL) {
        *distance = measured > 255 ? 255 : (u8)measured;
    }
    if (measured <= OW_WILD_DISTANCE_DESPAWN_TILES) {
        presentation->farSamples[slot] = 0;
        return FALSE;
    }
    if (presentation->farSamples[slot] < OW_WILD_DISTANCE_DESPAWN_SAMPLES) {
        presentation->farSamples[slot]++;
    }
    return presentation->farSamples[slot] >= OW_WILD_DISTANCE_DESPAWN_SAMPLES;
}

static OverworldWildDespawnAuthorization OverworldWildHelper_AuthorizeDespawn(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    int slot,
    u16 expectedGeneration,
    OverworldWildDespawnReason reason,
    LocalMapObject **verifiedObject)
{
    MapObjectMan *manager;
    LocalMapObject *candidate = NULL;
    BOOL terminalBattle = reason == OW_WILD_DESPAWN_REASON_BATTLE_DEFEATED
        || reason == OW_WILD_DESPAWN_REASON_BATTLE_CAUGHT;
    int candidateCount = 0;
    int i;

    if (verifiedObject != NULL) {
        *verifiedObject = NULL;
    }
    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || presentation == NULL
        || !state->spawns[slot].active
        || expectedGeneration == 0
        || state->spawns[slot].encounterGeneration != expectedGeneration
        || reason <= OW_WILD_DESPAWN_REASON_NONE
        || reason > OW_WILD_DESPAWN_REASON_DISTANCE
        || (reason == OW_WILD_DESPAWN_REASON_DISTANCE
            && presentation->farSamples[slot] < OW_WILD_DISTANCE_DESPAWN_SAMPLES)) {
        return OW_WILD_DESPAWN_DENIED;
    }
    if (OverworldWildHelper_IsExactObject(fieldSystem, state, slot)) {
        if (verifiedObject != NULL) {
            *verifiedObject = state->spawns[slot].object;
        }
        return OW_WILD_DESPAWN_DELETE_VERIFIED_OBJECT;
    }
    if (!terminalBattle) {
        /* Distance removal never clears without the exact active presentation. */
        return OW_WILD_DESPAWN_DENIED;
    }
    if (!OverworldWildHelper_IsContextCurrent(fieldSystem, state)) {
        return OW_WILD_DESPAWN_CLEAR_LOGICAL_ONLY;
    }
    if (state->spawns[slot].mapId != fieldSystem->location->mapId) {
        return OW_WILD_DESPAWN_CLEAR_LOGICAL_ONLY;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    for (i = 0; i < (int)manager->object_count; i++) {
        LocalMapObject *object = &manager->objects[i];

        if (object->id == OW_WILD_OBJECT_ID_START + slot
            && object->scriptId == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT) {
            candidate = object;
            candidateCount++;
        }
    }
    if (candidateCount > 1) {
        return OW_WILD_DESPAWN_CLEAR_LOGICAL_ONLY;
    }
    if (candidateCount == 1) {
        if ((candidate->flags & MAPOBJECTFLAG_ACTIVE) != 0) {
            state->spawns[slot].object = candidate;
        }
        if (verifiedObject != NULL) {
            *verifiedObject = candidate;
        }
        return OW_WILD_DESPAWN_DELETE_VERIFIED_OBJECT;
    }
    return OW_WILD_DESPAWN_CLEAR_LOGICAL_ONLY;
}

static void OverworldWildHelper_RecordDespawnEvent(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    int slot,
    OverworldWildDespawnReason reason,
    OverworldWildDespawnAction action,
    u8 distance)
{
    OverworldWildDespawnRecord *record;
    OverworldWildSpawn *spawn;
    LocalMapObject *object;
    BOOL exactObject;
    u8 flags = 0;

    if (state == NULL
        || presentation == NULL
        || telemetry == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }
    if (telemetry->magic != OW_WILD_DESPAWN_TELEMETRY_MAGIC) {
        telemetry->magic = OW_WILD_DESPAWN_TELEMETRY_MAGIC;
        telemetry->sequence = 0;
        telemetry->writeIndex = 0;
        telemetry->unexpectedCount = 0;
    }
    spawn = &state->spawns[slot];
    object = spawn->object;
    exactObject = OverworldWildHelper_IsExactObject(fieldSystem, state, slot);
    if (OverworldWildHelper_IsContextCurrent(fieldSystem, state)) {
        flags |= OW_WILD_DESPAWN_CONTEXT_CURRENT;
    }
    if (fieldSystem != NULL && fieldSystem->taskman != NULL) {
        flags |= OW_WILD_DESPAWN_CONTEXT_TASK_BUSY;
    }
    if (exactObject) {
        flags |= OW_WILD_DESPAWN_CONTEXT_POINTER_IN_ARRAY
            | OW_WILD_DESPAWN_CONTEXT_OBJECT_ACTIVE
            | OW_WILD_DESPAWN_CONTEXT_EXACT_ID
            | OW_WILD_DESPAWN_CONTEXT_EXACT_SCRIPT;
    }
    record = &telemetry->records[telemetry->writeIndex];
    record->sequence = ++telemetry->sequence;
    record->objectPtr = (u32)object;
    record->objectFlags = exactObject ? object->flags : 0;
    record->personality = spawn->personality;
    record->mapId = fieldSystem != NULL && fieldSystem->location != NULL
        ? (u16)fieldSystem->location->mapId
        : MAP_NOTHING;
    record->spawnMapId = spawn->mapId;
    record->mapGeneration = state->mapGeneration;
    record->encounterGeneration = spawn->encounterGeneration;
    record->objectX = exactObject
        ? (s16)MapObject_GetCurrentX(object)
        : presentation->lastKnownX[slot];
    record->objectY = exactObject
        ? (s16)MapObject_GetCurrentY(object)
        : presentation->lastKnownY[slot];
    record->playerX = fieldSystem != NULL && fieldSystem->playerAvatar != NULL
        ? (s16)GetPlayerXCoord(fieldSystem->playerAvatar)
        : 0;
    record->playerY = fieldSystem != NULL && fieldSystem->playerAvatar != NULL
        ? (s16)GetPlayerYCoord(fieldSystem->playerAvatar)
        : 0;
    record->objectId = exactObject ? (s16)object->id : -1;
    record->reason = (u8)reason;
    record->action = (u8)action;
    record->slot = (u8)slot;
    record->distance = distance;
    record->contextFlags = flags;
    record->expectedObjectId = spawn->objectId;
    if (reason < 4) {
        telemetry->reasonCounts[reason]++;
    }
    if (action == OW_WILD_DESPAWN_ACTION_DELETE_SUPPRESSED
        || action == OW_WILD_DESPAWN_ACTION_IDENTITY_CONFLICT) {
        telemetry->unexpectedCount++;
    }
    telemetry->writeIndex = (telemetry->writeIndex + 1)
        % OW_WILD_DESPAWN_RECORD_COUNT;
}

static u8 OverworldWildHelper_ClassifyBattleResult(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u16 battleResult)
{
    int slot;

    if (state == NULL) {
        return OW_WILD_BATTLE_DISPOSITION_RETAIN;
    }
    slot = state->pendingSlot;
    if (slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active
        || state->pendingPersonality != state->spawns[slot].personality
        || state->pendingMapGeneration == 0
        || state->pendingMapGeneration != state->mapGeneration
        || state->pendingEncounterGeneration == 0
        || state->pendingEncounterGeneration != state->spawns[slot].encounterGeneration
        || state->spawns[slot].objectId != OW_WILD_OBJECT_ID_START + slot) {
        return OW_WILD_BATTLE_DISPOSITION_RETAIN;
    }
    (void)fieldSystem;
    switch (battleResult) {
    case OW_WILD_BATTLE_RESULT_WIN:
        return OW_WILD_BATTLE_DISPOSITION_DEFEATED;
    case OW_WILD_BATTLE_RESULT_CAUGHT:
        return OW_WILD_BATTLE_DISPOSITION_CAUGHT;
    case OW_WILD_BATTLE_RESULT_PLAYER_FLED:
        return OW_WILD_BATTLE_DISPOSITION_FLED;
    default:
        return (battleResult & OW_WILD_BATTLE_RESULT_TRY_FLEE) != 0
            ? OW_WILD_BATTLE_DISPOSITION_FLED
            : OW_WILD_BATTLE_DISPOSITION_RETAIN;
    }
}

static BOOL OverworldWildHelper_ReconcilePresentations(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    OverworldWildHelperRecreatePresentationFunc recreatePresentation)
{
    MapObjectMan *manager;
    int i;

    if (fieldSystem == NULL
        || state == NULL
        || presentation == NULL
        || recreatePresentation == NULL
        || !OverworldWildHelper_IsContextCurrent(fieldSystem, state)
        || fieldSystem->taskman != NULL) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        LocalMapObject *candidate = NULL;
        u16 slotMask = (u16)(1u << i);
        int candidateCount = 0;
        int j;

        if (!state->spawns[i].active) {
            presentation->managerRestoreMask &= (u16)~slotMask;
            continue;
        }
        if (OverworldWildHelper_IsExactObject(fieldSystem, state, i)) {
            presentation->lastKnownX[i] = (s16)MapObject_GetCurrentX(state->spawns[i].object);
            presentation->lastKnownY[i] = (s16)MapObject_GetCurrentY(state->spawns[i].object);
            presentation->managerRestoreMask &= (u16)~slotMask;
            continue;
        }
        state->spawns[i].object = NULL;
        for (j = 0; j < (int)manager->object_count; j++) {
            LocalMapObject *object = &manager->objects[j];

            if ((object->flags & MAPOBJECTFLAG_ACTIVE) != 0
                && object->id == OW_WILD_OBJECT_ID_START + i
                && object->scriptId == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT) {
                candidate = object;
                candidateCount++;
            }
        }
        if (candidateCount > 1) {
            OverworldWildHelper_RecordDespawnEvent(
                fieldSystem,
                state,
                presentation,
                telemetry,
                i,
                OW_WILD_DESPAWN_REASON_NONE,
                OW_WILD_DESPAWN_ACTION_IDENTITY_CONFLICT,
                0);
            return FALSE;
        }
        if (candidateCount == 1) {
            state->spawns[i].object = candidate;
            state->spawns[i].objectId = OW_WILD_OBJECT_ID_START + i;
            if (recreatePresentation(
                    state,
                    fieldSystem,
                    i,
                    candidate,
                    MapObject_GetCurrentX(candidate),
                    MapObject_GetCurrentY(candidate)) == NULL
                || !OverworldWildHelper_IsExactObject(fieldSystem, state, i)) {
                state->spawns[i].object = NULL;
                return FALSE;
            }
            presentation->lastKnownX[i] = (s16)MapObject_GetCurrentX(candidate);
            presentation->lastKnownY[i] = (s16)MapObject_GetCurrentY(candidate);
            if ((presentation->managerRestoreMask & slotMask) != 0) {
                presentation->farSamples[i] = 0;
            }
            presentation->managerRestoreMask &= (u16)~slotMask;
            OverworldWildHelper_RecordDespawnEvent(
                fieldSystem,
                state,
                presentation,
                telemetry,
                i,
                OW_WILD_DESPAWN_REASON_NONE,
                OW_WILD_DESPAWN_ACTION_REBIND_OBJECT,
                0);
            continue;
        }
        if ((presentation->managerRestoreMask & slotMask) == 0) {
            /* A missing record in an unchanged manager is an invariant failure. */
            OverworldWildHelper_RecordDespawnEvent(
                fieldSystem,
                state,
                presentation,
                telemetry,
                i,
                OW_WILD_DESPAWN_REASON_NONE,
                OW_WILD_DESPAWN_ACTION_DELETE_SUPPRESSED,
                0);
            return FALSE;
        }
        OverworldWildHelper_RecordDespawnEvent(
            fieldSystem,
            state,
            presentation,
            telemetry,
            i,
            OW_WILD_DESPAWN_REASON_NONE,
            OW_WILD_DESPAWN_ACTION_PRESENTATION_MISSING,
            0);
        if (GetMetatileBehaviorAt(
                fieldSystem,
                presentation->lastKnownX[i],
                presentation->lastKnownY[i]) == 0xFF
            || recreatePresentation(
                state,
                fieldSystem,
                i,
                NULL,
                presentation->lastKnownX[i],
                presentation->lastKnownY[i]) == NULL
            || !OverworldWildHelper_IsExactObject(fieldSystem, state, i)) {
            return FALSE;
        }
        presentation->managerRestoreMask &= (u16)~slotMask;
        presentation->farSamples[i] = 0;
        OverworldWildHelper_RecordDespawnEvent(
            fieldSystem,
            state,
            presentation,
            telemetry,
            i,
            OW_WILD_DESPAWN_REASON_NONE,
            OW_WILD_DESPAWN_ACTION_RECREATE_OBJECT,
            0);
    }
    return TRUE;
}

static BOOL OverworldWildHelper_RemoveEncounter(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    int slot,
    u16 expectedGeneration,
    OverworldWildDespawnReason reason,
    u8 distance,
    OverworldWildHelperResetSlotFunc resetSlot)
{
    LocalMapObject *verifiedObject = NULL;
    OverworldWildDespawnAuthorization authorization =
        OverworldWildHelper_AuthorizeDespawn(
            fieldSystem,
            state,
            presentation,
            slot,
            expectedGeneration,
            reason,
            &verifiedObject);

    OverworldWildHelper_RecordDespawnEvent(
        fieldSystem,
        state,
        presentation,
        telemetry,
        slot,
        reason,
        authorization == OW_WILD_DESPAWN_DELETE_VERIFIED_OBJECT
            ? OW_WILD_DESPAWN_ACTION_DELETE_OBJECT
            : authorization == OW_WILD_DESPAWN_CLEAR_LOGICAL_ONLY
                ? OW_WILD_DESPAWN_ACTION_CLEAR_LOGICAL_ONLY
                : OW_WILD_DESPAWN_ACTION_DELETE_SUPPRESSED,
        distance);
    if (authorization == OW_WILD_DESPAWN_DENIED || resetSlot == NULL) {
        return FALSE;
    }
    resetSlot(state, slot, TRUE);
    if (verifiedObject != NULL) {
        DeleteMapObject(verifiedObject);
    }
    return TRUE;
}

static void OverworldWildHelper_DespawnFarEncounters(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    u16 movementProtectedMask,
    OverworldWildHelperResetSlotFunc resetSlot)
{
    int i;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        u8 distance;
        BOOL movementProtected = (movementProtectedMask & (1u << i)) != 0
            || state->movementSpawnRunActive[i];

        if (OverworldWildHelper_ConfirmDistanceDespawn(
                fieldSystem,
                state,
                presentation,
                i,
                movementProtected,
                &distance)) {
            (void)OverworldWildHelper_RemoveEncounter(
                fieldSystem,
                state,
                presentation,
                telemetry,
                i,
                state->spawns[i].encounterGeneration,
                OW_WILD_DESPAWN_REASON_DISTANCE,
                distance,
                resetSlot);
        }
    }
}

static u8 OverworldWildHelper_FinishBattle(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    u16 battleResult,
    OverworldWildHelperResetSlotFunc resetSlot)
{
    u8 disposition = OverworldWildHelper_ClassifyBattleResult(
        fieldSystem,
        state,
        battleResult);

    if (disposition == OW_WILD_BATTLE_DISPOSITION_DEFEATED
        || disposition == OW_WILD_BATTLE_DISPOSITION_CAUGHT) {
        (void)OverworldWildHelper_RemoveEncounter(
            fieldSystem,
            state,
            presentation,
            telemetry,
            state->pendingSlot,
            state->pendingEncounterGeneration,
            disposition == OW_WILD_BATTLE_DISPOSITION_DEFEATED
                ? OW_WILD_DESPAWN_REASON_BATTLE_DEFEATED
                : OW_WILD_DESPAWN_REASON_BATTLE_CAUGHT,
            0,
            resetSlot);
    }
    return disposition;
}

static LocalMapObject *OverworldWildHelper_CreatePresentationObject(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    int x,
    int y,
    u8 facing,
    u8 movementBehavior,
    u8 range)
{
    OverworldWildSpawn *spawn = &state->spawns[slot];
    u32 spriteId = FollowingPokemon_GetSpriteID(spawn->species, spawn->form, 0);
    LocalMapObject *object;

    OverworldWildCustomMovement_SetFieldSystem(fieldSystem);
    object = CreateSpecialFieldObjectWithParams(
        fieldSystem->mapObjectMan,
        x,
        y,
        facing,
        spriteId,
        OW_WILD_MOVE_STOCK_IDLE,
        fieldSystem->location->mapId,
        0,
        movementBehavior,
        OW_WILD_HELPER_PAL_PARAM_ENABLE
            | (spawn->shiny ? OW_WILD_HELPER_PAL_PARAM_SHINY : 0));
    if (object == NULL) {
        return NULL;
    }
    MapObject_SetID(object, OW_WILD_OBJECT_ID_START + slot);
    MapObject_SetScript(object, OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT);
    if (range == 0) {
        range = 32;
    }
    MapObject_SetXRange(object, range);
    MapObject_SetYRange(object, range);
    FollowPokeMapObjectSetParams(object, spawn->species, spawn->form, spawn->shiny);
    if (spawn->shiny) {
        sub_02069DC8(object, TRUE);
        ChangeMapObjSprite(object, spriteId);
    }
    object->facingInit = facing;
    object->curFacing = facing;
    object->nextFacing = facing;
    object->curFacingBak = facing;
    object->nextFacingBak = facing;
    MapObject_SetCurrentX(object, (u32)x);
    MapObject_SetCurrentY(object, (u32)y);
    object->xInit = x;
    object->yInit = y;
    object->xPrev = x;
    object->yPrev = y;
    object->posVec[0] = (u32)((s32)x * 0x10000 + 0x8000);
    object->posVec[2] = (u32)((s32)y * 0x10000 + 0x8000);
    object->flags &= ~(BIT_VANISH | MAPOBJECTFLAG_UNK8);
    return object;
}

static BOOL OverworldWildHelper_ValidateDeferredBattle(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    u16 encounterGeneration)
{
    return state != NULL
        && slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && state->pendingSlot == slot
        && state->pendingMapGeneration == state->mapGeneration
        && state->pendingEncounterGeneration == encounterGeneration
        && state->pendingPersonality == state->spawns[slot].personality
        && state->spawns[slot].encounterGeneration == encounterGeneration
        && OverworldWildHelper_IsExactObject(fieldSystem, state, slot);
}

const OverworldWildHelperOverlayEntry gOverworldWildHelperOverlayEntry
    __attribute__((section(".overworld_wild_helper_entry"), used)) = {
    OVERWORLD_WILD_HELPER_OVERLAY_MAGIC,
    OVERWORLD_WILD_HELPER_OVERLAY_VERSION,
    sizeof(OverworldWildHelperOverlayEntry),
    OverworldWildHelper_TryPrepareSpawn,
    OverworldWildHelper_TryPrepareEncounterSpawn,
    OverworldWildHelper_PickRandomBehaviorHop,
    OverworldWildHelper_PlanBehaviorHopStep,
    OverworldWildHelper_IsPresentationContextCurrent,
    OverworldWildHelper_NormalizeThrowPresentation,
    OverworldWildHelper_SyncCarriedThrowTarget,
    OverworldWildHelper_ReconcilePresentations,
    OverworldWildHelper_DespawnFarEncounters,
    OverworldWildHelper_FinishBattle,
    OverworldWildHelper_CreatePresentationObject,
    OverworldWildHelper_ValidateDeferredBattle,
};
