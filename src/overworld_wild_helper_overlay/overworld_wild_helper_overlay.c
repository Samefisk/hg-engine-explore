#include "../../include/overworld_wild_helper.h"
#include "../../include/config.h"
#include "../../include/constants/file.h"
#include "../../include/constants/species.h"
#include "../../include/overworld_wild_spawns.h"
#include "../../include/pokemon.h"
#include "../../include/rtc.h"

#define OW_WILD_HELPER_GRASS_SLOTS 12
#define OW_WILD_HELPER_SURF_SLOTS 5
#define OW_WILD_HELPER_FISH_SLOTS 5
#define OW_WILD_HELPER_HEADBUTT_NORMAL_SLOTS 12
#define OW_WILD_HELPER_HEADBUTT_SPECIAL_SLOTS 6
#define OW_WILD_HELPER_HEADBUTT_COORDS_PER_TREE 6
#define OW_WILD_HELPER_HEADBUTT_NORMAL_TREE 0
#define OW_WILD_HELPER_HEADBUTT_SPECIAL_TREE 1
#define OW_WILD_HELPER_HEADBUTT_EMPTY_COORD -1
#define OW_WILD_HELPER_HEADBUTT_TREE_TOPS_MAX_LOCATIONS 512
#define OW_WILD_HELPER_RANDOM_TIME_TABLE_CHANCE_PERCENT 20
#define OW_WILD_HELPER_SPAWN_MIN_DISTANCE 4
#define OW_WILD_HELPER_SPAWN_MAX_DISTANCE 8
#define OW_WILD_HELPER_PLAYER_RELATIVE_SPAWN_MIN_DISTANCE 1
#define OW_WILD_HELPER_PLAYER_RELATIVE_SPAWN_MAX_DISTANCE OW_WILD_HELPER_SPAWN_MAX_DISTANCE
#define OW_WILD_HELPER_DESPAWN_DISTANCE 14
#define OW_WILD_HELPER_SPAWN_MIN_MON_DISTANCE 3
#define OW_WILD_HELPER_SHINY_ODDS 8192
#define OW_WILD_HELPER_SPECIES_MASK 0x7FF
#define OW_WILD_HELPER_FORM_SHIFT 11
#define OW_WILD_HELPER_NELEMS(array) (sizeof(array) / sizeof((array)[0]))

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

typedef struct OverworldWildHelperHeadbuttCoord {
    s16 x;
    s16 y;
} OverworldWildHelperHeadbuttCoord;

typedef struct OverworldWildHelperHeadbuttTree {
    OverworldWildHelperHeadbuttCoord coords[OW_WILD_HELPER_HEADBUTT_COORDS_PER_TREE];
} OverworldWildHelperHeadbuttTree;

typedef struct OverworldWildHelperHeadbuttLandingOffset {
    s8 dx;
    s8 dy;
} OverworldWildHelperHeadbuttLandingOffset;

static const u8 sOverworldWildHelperGrassSlotWeights[OW_WILD_HELPER_GRASS_SLOTS] = {
    20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1,
};

static const u8 sOverworldWildHelperSurfSlotWeights[OW_WILD_HELPER_SURF_SLOTS] = {
    60, 30, 5, 4, 1,
};

static const u8 sOverworldWildHelperFishingSlotWeights[OW_WILD_HELPER_FISH_SLOTS] = {
    60, 30, 5, 4, 1,
};

static const OverworldWildHelperHeadbuttLandingOffset sOverworldWildHelperHeadbuttLandingOffsets[] = {
    { 0, 1 },
    { 0, -1 },
    { -1, 0 },
    { 1, 0 },
};

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
    return callbacks != NULL
        && callbacks->getPlayerState != NULL
        && callbacks->tryGetSpawnTerrain != NULL
        && callbacks->isTileOccupied != NULL
        && callbacks->isNearActiveSpawn != NULL
        && callbacks->isWalkableLandTile != NULL
        && callbacks->isFishingShoreTile != NULL
        && callbacks->getMapId != NULL
        && callbacks->loadArchiveData != NULL
        && callbacks->tryGetEncounterDataId != NULL
        && callbacks->findSavedShiny != NULL
        && callbacks->loadSavedShiny != NULL
        && callbacks->applyBehaviorTestSpecies != NULL;
}

static BOOL OverworldWildHelper_GetMapId(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    u16 *mapId)
{
    return callbacks != NULL
        && callbacks->getMapId != NULL
        && callbacks->getMapId(context, mapId);
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

static int OverworldWildHelper_DistanceFromPlayer(
    const OverworldWildHelperPlayerState *playerState,
    int x,
    int y)
{
    if (playerState == NULL) {
        return OW_WILD_HELPER_DESPAWN_DISTANCE + 1;
    }

    return OverworldWildHelper_Max(
        OverworldWildHelper_Abs(x - playerState->playerX),
        OverworldWildHelper_Abs(y - playerState->playerY));
}

static BOOL OverworldWildHelper_TryPickSpawnPosition(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain requestedTerrain,
    OverworldWildSpawnPosition *position)
{
    OverworldWildHelperPlayerState playerState;
    u32 candidateCount = 0;
    int x;
    int y;

    if (position == NULL
        || !callbacks->getPlayerState(context, &playerState)) {
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
}

static BOOL OverworldWildHelper_TryPickFishingSpawnPosition(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnPosition *position)
{
    OverworldWildHelperPlayerState playerState;
    u32 candidateCount = 0;
    int x;
    int y;

    if (position == NULL
        || !callbacks->getPlayerState(context, &playerState)) {
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

            if (distance < OW_WILD_HELPER_SPAWN_MIN_DISTANCE
                || distance > OW_WILD_HELPER_SPAWN_MAX_DISTANCE
                || !callbacks->isFishingShoreTile(context, x, y)
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
}

static u32 OverworldWildHelper_GetHeadbuttTreeDataOffset(void)
{
    return sizeof(OverworldWildHelperHeadbuttHeader)
        + (OW_WILD_HELPER_HEADBUTT_NORMAL_SLOTS + OW_WILD_HELPER_HEADBUTT_SPECIAL_SLOTS)
            * sizeof(OverworldWildHelperHeadbuttEncounterSlot);
}

static void OverworldWildHelper_TryPickHeadbuttLanding(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    const OverworldWildHelperPlayerState *playerState,
    int treeX,
    int treeY,
    u8 treeType,
    OverworldWildSpawnPosition *position,
    u32 *candidateCount)
{
    u32 landingStart;
    u32 landingAttempt;

    if (position == NULL
        || candidateCount == NULL
        || treeX == OW_WILD_HELPER_HEADBUTT_EMPTY_COORD
        || treeY == OW_WILD_HELPER_HEADBUTT_EMPTY_COORD) {
        return;
    }

    landingStart = gf_rand() % OW_WILD_HELPER_NELEMS(sOverworldWildHelperHeadbuttLandingOffsets);
    for (landingAttempt = 0;
         landingAttempt < OW_WILD_HELPER_NELEMS(sOverworldWildHelperHeadbuttLandingOffsets);
         landingAttempt++) {
        const OverworldWildHelperHeadbuttLandingOffset *landing =
            &sOverworldWildHelperHeadbuttLandingOffsets[
                (landingStart + landingAttempt)
                    % OW_WILD_HELPER_NELEMS(sOverworldWildHelperHeadbuttLandingOffsets)];
        int spawnX = treeX + landing->dx;
        int spawnY = treeY + landing->dy;
        int distance = OverworldWildHelper_DistanceFromPlayer(playerState, spawnX, spawnY);

        if (distance < OW_WILD_HELPER_SPAWN_MIN_DISTANCE
            || distance > OW_WILD_HELPER_SPAWN_MAX_DISTANCE
            || !callbacks->isWalkableLandTile(context, spawnX, spawnY)
            || callbacks->isNearActiveSpawn(
                context,
                treeX,
                treeY,
                OW_WILD_HELPER_SPAWN_MIN_MON_DISTANCE)) {
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

static BOOL OverworldWildHelper_TryPickHeadbuttSpawnPosition(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnPosition *position)
{
    OverworldWildHelperHeadbuttHeader header;
    OverworldWildHelperPlayerState playerState;
    u32 treeDataOffset;
    u32 candidateCount = 0;
    u32 treeGroup;
    u16 mapId;

    if (position == NULL
        || !callbacks->getPlayerState(context, &playerState)
        || !OverworldWildHelper_GetMapId(callbacks, context, &mapId)
        || !OverworldWildHelper_LoadArchiveData(
            callbacks,
            context,
            ARC_HEADBUTT_TREES,
            mapId,
            0,
            &header,
            sizeof(header))) {
        return FALSE;
    }

    if (header.normalTreeCount == 0 && header.specialTreeCount == 0) {
        return FALSE;
    }

    treeDataOffset = OverworldWildHelper_GetHeadbuttTreeDataOffset();

    for (treeGroup = 0; treeGroup < 2; treeGroup++) {
        u8 treeType = treeGroup == 0
            ? OW_WILD_HELPER_HEADBUTT_NORMAL_TREE
            : OW_WILD_HELPER_HEADBUTT_SPECIAL_TREE;
        u32 treeCount = treeType == OW_WILD_HELPER_HEADBUTT_NORMAL_TREE
            ? header.normalTreeCount
            : header.specialTreeCount;
        u32 treeOffset = treeDataOffset;
        u32 treeIndex;

        if (treeType == OW_WILD_HELPER_HEADBUTT_SPECIAL_TREE) {
            treeOffset += header.normalTreeCount * sizeof(OverworldWildHelperHeadbuttTree);
        }

        for (treeIndex = 0; treeIndex < treeCount; treeIndex++) {
            OverworldWildHelperHeadbuttTree tree;
            u32 coordIndex;

            if (!OverworldWildHelper_LoadArchiveData(
                    callbacks,
                    context,
                    ARC_HEADBUTT_TREES,
                    mapId,
                    treeOffset + treeIndex * sizeof(tree),
                    &tree,
                    sizeof(tree))) {
                return FALSE;
            }

            for (coordIndex = 0;
                 coordIndex < OW_WILD_HELPER_HEADBUTT_COORDS_PER_TREE;
                 coordIndex++) {
                int treeX = tree.coords[coordIndex].x;
                int treeY = tree.coords[coordIndex].y;

                if (treeX == OW_WILD_HELPER_HEADBUTT_EMPTY_COORD
                    || treeY == OW_WILD_HELPER_HEADBUTT_EMPTY_COORD) {
                    continue;
                }

                OverworldWildHelper_TryPickHeadbuttLanding(
                    callbacks,
                    context,
                    &playerState,
                    treeX,
                    treeY,
                    treeType,
                    position,
                    &candidateCount);
            }
        }
    }

    return candidateCount != 0;
}

static BOOL OverworldWildHelper_TryPickSpawnPositionForTerrain(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    OverworldWildSpawnPosition *position)
{
    if (terrain == OW_WILD_SPAWN_TERRAIN_HEADBUTT) {
        return OverworldWildHelper_TryPickHeadbuttSpawnPosition(callbacks, context, position);
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

        if (!OverworldWildHelper_LoadArchiveData(
                callbacks,
                context,
                ARC_HEADBUTT_TREES,
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

static BOOL OverworldWildHelper_RollShiny(BOOL shinyAlreadySpawned)
{
    if (shinyAlreadySpawned) {
        return FALSE;
    }

    return (gf_rand() % OW_WILD_HELPER_SHINY_ODDS) == 0;
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
    int slot,
    const OverworldWildSpawnPosition *position,
    BOOL shinyAlreadySpawned,
    OverworldWildRolledEncounter *encounter,
    int *savedShinySlot,
    BOOL *shiny)
{
    if (position == NULL
        || encounter == NULL
        || savedShinySlot == NULL
        || shiny == NULL) {
        return FALSE;
    }

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
        *shiny = OverworldWildHelper_RollShiny(shinyAlreadySpawned);
        if (*shiny) {
            encounter->personality = OverworldWildHelper_MakePersonalityShiny(encounter->personality);
        }
    }

    if (encounter->species == SPECIES_NONE || encounter->level == 0) {
        return FALSE;
    }

    callbacks->applyBehaviorTestSpecies(context, terrain, slot, *savedShinySlot, encounter);
    return TRUE;
}

static BOOL OverworldWildHelper_CopyPreparedSpawn(
    const OverworldWildSpawnPosition *position,
    const OverworldWildRolledEncounter *encounter,
    BOOL shiny,
    int savedShinySlot,
    OverworldWildPreparedSpawn *prepared)
{
    if (position == NULL
        || encounter == NULL
        || prepared == NULL
        || encounter->species == SPECIES_NONE
        || encounter->level == 0) {
        return FALSE;
    }

    prepared->position = *position;
    prepared->encounter = *encounter;
    prepared->savedShinySlot = savedShinySlot;
    prepared->shiny = shiny;
    prepared->reserved[0] = 0;
    prepared->reserved[1] = 0;
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
            slot,
            &position,
            shinyAlreadySpawned,
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

const OverworldWildHelperOverlayEntry gOverworldWildHelperOverlayEntry
    __attribute__((section(".overworld_wild_helper_entry"), used)) = {
    OVERWORLD_WILD_HELPER_OVERLAY_MAGIC,
    OVERWORLD_WILD_HELPER_OVERLAY_VERSION,
    sizeof(OverworldWildHelperOverlayEntry),
    OverworldWildHelper_TryPrepareSpawn,
    OverworldWildHelper_TryPrepareEncounterSpawn,
    OverworldWildHelper_PickRandomBehaviorHop,
    OverworldWildHelper_PlanBehaviorHopStep,
};
