#include "../../include/overworld_wild_helper.h"
#include "../../include/config.h"
#include "../../include/constants/file.h"
#include "../../include/constants/game.h"
#include "../../include/constants/generated/learnsets.h"
#include "../../include/constants/item.h"
#include "../../include/constants/moves.h"
#include "../../include/constants/sndseq.h"
#include "../../include/constants/species.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_wild_spawns.h"
#include "../../include/overworld_wild_movement.h"
#include "../../include/pokemon.h"
#include "../../include/pokemon_storage_system.h"
#include "../../include/rtc.h"
#include "../../include/save.h"
#include "../../include/script.h"
#include "../../include/sound.h"
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
#define OW_WILD_HELPER_PLAYER_BALL_TAG 87
#define OW_WILD_HELPER_PLAYER_BALL_FORWARD_OFFSET_FX32 0x4000
#define OW_WILD_HELPER_PLAYER_BALL_HAND_HEIGHT_FX32 0x8000
#define OW_WILD_HELPER_PLAYER_BALL_ARC_HEIGHT_FX32 0x6000
#define OW_WILD_HELPER_PLAYER_BALL_BASE_FRAMES 8
#define OW_WILD_HELPER_PLAYER_BALL_FRAMES_PER_TILE 1
#define OW_WILD_HELPER_PLAYER_BALL_MAX_FRAMES 18
#define OW_WILD_HELPER_PLAYER_BALL_MIN_DISTANCE_FX32 0x30000
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_STEP_FX32 0x2000
#define OW_WILD_HELPER_PLAYER_BALL_MAX_CHARGE_FRAMES 40
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_RISE_FX32 0x3000
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_PULSE_STEP_FX32 0x100
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_SE SEQ_SE_GS_DOWSING_SINGLE
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_SLOW_INTERVAL 12
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_FAST_INTERVAL 5
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_SOUND_COMPLETE 0xFF
#define OW_WILD_HELPER_PLAYER_BALL_HIT_RADIUS_FX32 0x7000
#define OW_WILD_HELPER_PLAYER_BALL_AIM_HALF_WIDTH_FX32 0x18000
#define OW_WILD_HELPER_PLAYER_BALL_AIM_MIN_FORWARD_FX32 0x10000
#define OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT 12
#define OW_WILD_HELPER_PLAYER_BALL_IMPACT_FRAMES 12
#define OW_WILD_HELPER_PLAYER_BALL_IMPACT_REBOUND_STEP_FX32 0x1000
#define OW_WILD_HELPER_PLAYER_BALL_IMPACT_BUBBLE_ID 8
#define OW_WILD_HELPER_PLAYER_BALL_LAND_FRAMES 16
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_FRAMES 18
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_OFFSET_FX32 0x2800
#define OW_WILD_HELPER_PLAYER_BALL_RESULT_FRAMES 24
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_SE SEQ_SE_DP_KON
#define OW_WILD_HELPER_PLAYER_BALL_BREAKOUT_SE SEQ_SE_DP_BOWA2
#define OW_WILD_HELPER_PLAYER_BALL_CAUGHT_SE SEQ_SE_DP_GETTING
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE 0
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_CHARGING 1
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_FLYING 2
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT 3
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_LANDED 4
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_SHAKING 5
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_BREAKOUT 6
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_CAUGHT 7
#define OW_WILD_HELPER_PC_STORAGE_SAVE_BLOCK 41
#define OW_WILD_HELPER_CAPTURE_ENCOUNTER_TYPE 0
#define OW_WILD_HELPER_PERSONAL_RECORD_SIZE 28
#define OW_WILD_HELPER_PERSONAL_CATCH_RATE_OFFSET 8
#define OW_WILD_HELPER_PERSONAL_FRIENDSHIP_OFFSET 18
#define OW_WILD_HELPER_PERSONAL_GROWTH_OFFSET 19
#define OW_WILD_HELPER_PERSONAL_ABILITY_1_OFFSET 22
#define OW_WILD_HELPER_PERSONAL_ABILITY_2_OFFSET 26
#define OW_WILD_HELPER_SPECIES_NAME_MSG_FILE 237
#define OW_WILD_HELPER_SPECIES_NAME_CAPACITY 12
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
#define OW_WILD_HELPER_ENCOUNTER_DATA_SIZE 196
#define OW_WILD_HELPER_ENCOUNTER_DATA_OLD_ROD_RATE_OFFSET 3
#define OW_WILD_HELPER_ENCOUNTER_DATA_GOOD_ROD_RATE_OFFSET 4
#define OW_WILD_HELPER_ENCOUNTER_DATA_SUPER_ROD_RATE_OFFSET 5
#define OW_WILD_HELPER_SPARSE_RECORD_HEADER_SIZE 4
#define OW_WILD_HELPER_ENCOUNTER_LOOKUP_CHECKSUM_OFFSET 24
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

typedef struct OverworldWildHelperSparseEncounterSection {
    u8 mask;
    u8 targetOffset;
    u8 size;
} OverworldWildHelperSparseEncounterSection;

typedef struct OverworldWildHelperPlayerBallProjectileState {
    FieldSystem *fieldSystem;
    OverworldWildSpawnState *state;
    MapObjectMan *manager;
    LocalMapObject *objects;
    LocalMapObject *object;
    s32 startX;
    s32 startY;
    s32 startZ;
    s32 targetX;
    s32 targetY;
    s32 targetZ;
    s32 startHeight;
    u16 mapId;
    u16 mapGeneration;
    u16 impactEncounterGeneration;
    s8 impactSlot;
    u8 elapsedFrames;
    u8 totalFrames;
    u8 phase;
    u8 objectId;
    u8 shakeChecks;
    u8 shakeIndex;
    u8 targetHadPassThrough;
} OverworldWildHelperPlayerBallProjectileState;

/* Only values reachable by a full-HP Poké Ball catch (catch rate / 3). */
static const u16 sOverworldWildHelperShakeChance[] = {
    0, 23186, 26405, 28490, 30070, 31355, 32447, 33395,
    34243, 35007, 35705, 36348, 36949, 37506, 38032, 38529,
    38994, 39441, 39868, 40275, 40659, 41038, 41393, 41740,
    42074, 42400, 42710, 43018, 43310, 43598, 43876, 44143,
    44406, 44664, 44918, 45160, 45397, 45636, 45862, 46083,
    46305, 46522, 46733, 46937, 47143, 47343, 47535, 47730,
    47917, 48098, 48288, 48462, 48638, 48815, 48984, 49155,
    49317, 49490, 49645, 49802, 49960, 50118, 50268, 50419,
    50571, 50715, 50868, 51004, 51150, 51286, 51424, 51562,
    51701, 51831, 51972, 52103, 52224, 52357, 52480, 52613,
    52737, 52852, 52977, 53102, 53218, 53335,
};

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

static const OverworldWildHelperSparseEncounterSection sOverworldWildHelperSparseEncounterSections[] = {
    { OWED_SECTION_LAND_LEVELS, 8, 12 },
    { OWED_SECTION_LAND_MORNING, 20, 24 },
    { OWED_SECTION_LAND_DAY, 44, 24 },
    { OWED_SECTION_LAND_NIGHT, 68, 24 },
    { OWED_SECTION_SURF, 100, 20 },
    { OWED_SECTION_OLD_ROD, 128, 20 },
    { OWED_SECTION_GOOD_ROD, 148, 20 },
    { OWED_SECTION_SUPER_ROD, 168, 20 },
};

#if OW_WILD_HELPER_BUDGETED_SPAWN_POSITION_SEARCH
// Stored as cursor + 1 so zero can mean uninitialized after the helper overlay is loaded.
static u16 sOverworldWildHelperSpawnPositionCursor[2];
#endif
static void *sOverworldWildHelperEncounterLookupDataBlob;
static u32 sOverworldWildHelperEncounterLookupDataBlobSize;
static BOOL sOverworldWildHelperEncounterLookupLoadAttempted;
static OverworldWildHelperPlayerBallProjectileState sOverworldWildHelperPlayerBallProjectile;
static BOOL sOverworldWildHelperPlayerBallRWasDown;
static BOOL sOverworldWildHelperPlayerBallInputArmed = TRUE;
static BOOL sOverworldWildHelperPlayerBallStaleCheckDone;
static u8 sOverworldWildHelperPlayerBallChargeFrames;
static u8 sOverworldWildHelperPlayerBallChargeSoundTimer;

static int OverworldWildHelper_Abs(int value)
{
    return value < 0 ? -value : value;
}

static int OverworldWildHelper_Max(int lhs, int rhs)
{
    return lhs > rhs ? lhs : rhs;
}

static int OverworldWildHelper_Min(int lhs, int rhs)
{
    return lhs < rhs ? lhs : rhs;
}

static BOOL OverworldWildHelper_IsEncounterLookupRangeValid(
    u32 offset,
    u32 size,
    u32 totalSize)
{
    return offset <= totalSize && size <= totalSize - offset;
}

static u32 OverworldWildHelper_ComputeEncounterLookupChecksum(
    const u8 *blob,
    u32 size)
{
    u32 checksum = 0;
    u32 i;

    for (i = 0; i < size; i++) {
        if (i >= OW_WILD_HELPER_ENCOUNTER_LOOKUP_CHECKSUM_OFFSET
            && i < OW_WILD_HELPER_ENCOUNTER_LOOKUP_CHECKSUM_OFFSET + sizeof(u32)) {
            continue;
        }
        checksum += blob[i];
    }

    return checksum;
}

static BOOL OverworldWildHelper_IsSparseEncounterRecordValid(
    const u8 *record,
    u32 size)
{
    u32 recordOffset;
    u32 i;

    if (record == NULL || size < OW_WILD_HELPER_SPARSE_RECORD_HEADER_SIZE) {
        return FALSE;
    }

    recordOffset = OW_WILD_HELPER_SPARSE_RECORD_HEADER_SIZE;
    for (i = 0; i < OW_WILD_HELPER_NELEMS(sOverworldWildHelperSparseEncounterSections); i++) {
        const OverworldWildHelperSparseEncounterSection *section =
            &sOverworldWildHelperSparseEncounterSections[i];
        if ((record[3] & section->mask) == 0) {
            continue;
        }
        if (!OverworldWildHelper_IsEncounterLookupRangeValid(
                recordOffset,
                section->size,
                size)) {
            return FALSE;
        }
        recordOffset += section->size;
    }

    return recordOffset == size;
}

static BOOL OverworldWildHelper_DecodeEncounterLookupDataBlob(void)
{
    const OverworldWildEncounterLookupDataBlobHeader *header;
    const u8 *base;
    u32 directorySize;
    u32 i;

    if (sOverworldWildHelperEncounterLookupDataBlob == NULL
        || sOverworldWildHelperEncounterLookupDataBlobSize < sizeof(*header)) {
        return FALSE;
    }

    base = (const u8 *)sOverworldWildHelperEncounterLookupDataBlob;
    header = (const OverworldWildEncounterLookupDataBlobHeader *)base;
    if (header->magic != OVERWORLD_WILD_ENCOUNTER_LOOKUP_DATA_MAGIC
        || header->version != OVERWORLD_WILD_ENCOUNTER_LOOKUP_DATA_VERSION
        || header->headerSize != sizeof(OverworldWildEncounterLookupDataBlobHeader)
        || header->recordCount != OWED_ENCOUNTER_AREA_COUNT
        || header->directoryEntrySize != sizeof(OverworldWildEncounterLookupDirectoryEntry)) {
        return FALSE;
    }
    directorySize = (u32)header->recordCount * (u32)header->directoryEntrySize;

    if (header->totalSize != sOverworldWildHelperEncounterLookupDataBlobSize
        || header->flags != 0
        || header->checksum != OverworldWildHelper_ComputeEncounterLookupChecksum(
            base,
            sOverworldWildHelperEncounterLookupDataBlobSize)
        || header->directoryOffset < header->headerSize
        || (header->directoryOffset & 3) != 0
        || !OverworldWildHelper_IsEncounterLookupRangeValid(
            header->directoryOffset,
            directorySize,
            header->totalSize)
        || header->payloadOffset != header->directoryOffset + directorySize
        || header->payloadOffset > header->totalSize) {
        return FALSE;
    }

    for (i = 0; i < header->recordCount; i++) {
        const OverworldWildEncounterLookupDirectoryEntry *entry =
            (const OverworldWildEncounterLookupDirectoryEntry *)(base
                + header->directoryOffset
                + i * sizeof(*entry));
        if (entry->flags != 0
            || entry->size < OW_WILD_HELPER_SPARSE_RECORD_HEADER_SIZE
            || entry->offset < header->payloadOffset
            || !OverworldWildHelper_IsEncounterLookupRangeValid(
                entry->offset,
                entry->size,
                header->totalSize)
            || !OverworldWildHelper_IsSparseEncounterRecordValid(
                base + entry->offset,
                entry->size)) {
            return FALSE;
        }
    }

    return TRUE;
}

static const OverworldWildEncounterLookupDataBlobHeader *
OverworldWildHelper_GetEncounterLookupDataBlob(void)
{
    void *narc;
    u32 size;

    if (!sOverworldWildHelperEncounterLookupLoadAttempted) {
        sOverworldWildHelperEncounterLookupLoadAttempted = TRUE;
        narc = NARC_ctor(ARC_CODE_ADDONS, HEAPID_WORLD);
        if (narc == NULL) {
            return NULL;
        }
        size = NARC_GetMemberSize(narc, CODE_ADDON_OVERWORLD_WILD_ENCOUNTER_LOOKUP);
        if (size != 0) {
            sOverworldWildHelperEncounterLookupDataBlob =
                sys_AllocMemory(HEAPID_WORLD, size);
        }
        if (sOverworldWildHelperEncounterLookupDataBlob != NULL) {
            NARC_ReadWholeMember(
                narc,
                CODE_ADDON_OVERWORLD_WILD_ENCOUNTER_LOOKUP,
                sOverworldWildHelperEncounterLookupDataBlob);
            sOverworldWildHelperEncounterLookupDataBlobSize = size;
        }
        NARC_dtor(narc);
        if (sOverworldWildHelperEncounterLookupDataBlob == NULL
            || !OverworldWildHelper_DecodeEncounterLookupDataBlob()) {
            sys_FreeMemoryEz(sOverworldWildHelperEncounterLookupDataBlob);
            sOverworldWildHelperEncounterLookupDataBlob = NULL;
            sOverworldWildHelperEncounterLookupDataBlobSize = 0;
        }
    }

    return (const OverworldWildEncounterLookupDataBlobHeader *)
        sOverworldWildHelperEncounterLookupDataBlob;
}

static const OverworldWildEncounterLookupDirectoryEntry *
OverworldWildHelper_FindEncounterLookupEntry(
    const OverworldWildEncounterLookupDataBlobHeader *blob,
    u16 mapId,
    int encounterDataId,
    BOOL matchEncounterDataId)
{
    const u8 *base;
    u32 i;

    if (blob == NULL) {
        return NULL;
    }

    base = (const u8 *)blob;
    for (i = 0; i < blob->recordCount; i++) {
        const OverworldWildEncounterLookupDirectoryEntry *entry =
            (const OverworldWildEncounterLookupDirectoryEntry *)(base
                + blob->directoryOffset
                + i * sizeof(*entry));
        if (entry->mapId == mapId
            && (!matchEncounterDataId || entry->dataId == encounterDataId)) {
            return entry;
        }
    }

    return NULL;
}

static BOOL OverworldWildHelper_TryGetEncounterDataIdForMap(
    u16 mapId,
    int *encounterDataId)
{
    const OverworldWildEncounterLookupDirectoryEntry *entry;

    if (mapId == MAP_NOTHING || encounterDataId == NULL) {
        return FALSE;
    }

    entry = OverworldWildHelper_FindEncounterLookupEntry(
        OverworldWildHelper_GetEncounterLookupDataBlob(),
        mapId,
        0,
        FALSE);
    if (entry == NULL) {
        return FALSE;
    }

    *encounterDataId = entry->dataId;
    return TRUE;
}

static BOOL OverworldWildHelper_TryCopySparseEncounterRecord(
    const OverworldWildEncounterLookupDataBlobHeader *blob,
    const OverworldWildEncounterLookupDirectoryEntry *entry,
    void *dest,
    int size)
{
    const u8 *record;
    u8 *destBytes;
    u32 recordOffset;
    u32 i;
    u32 j;

    if (blob == NULL
        || entry == NULL
        || dest == NULL
        || size != OW_WILD_HELPER_ENCOUNTER_DATA_SIZE) {
        return FALSE;
    }

    record = (const u8 *)blob + entry->offset;
    if (!OverworldWildHelper_IsSparseEncounterRecordValid(record, entry->size)) {
        return FALSE;
    }

    memset(dest, 0, size);
    destBytes = (u8 *)dest;
    destBytes[OW_WILD_HELPER_ENCOUNTER_DATA_OLD_ROD_RATE_OFFSET] = record[0];
    destBytes[OW_WILD_HELPER_ENCOUNTER_DATA_GOOD_ROD_RATE_OFFSET] = record[1];
    destBytes[OW_WILD_HELPER_ENCOUNTER_DATA_SUPER_ROD_RATE_OFFSET] = record[2];

    recordOffset = OW_WILD_HELPER_SPARSE_RECORD_HEADER_SIZE;
    for (i = 0; i < OW_WILD_HELPER_NELEMS(sOverworldWildHelperSparseEncounterSections); i++) {
        const OverworldWildHelperSparseEncounterSection *section =
            &sOverworldWildHelperSparseEncounterSections[i];
        if ((record[3] & section->mask) == 0) {
            continue;
        }
        for (j = 0; j < section->size; j++) {
            destBytes[section->targetOffset + j] = record[recordOffset + j];
        }
        recordOffset += section->size;
    }

    return TRUE;
}

static BOOL OverworldWildHelper_TryLoadEncounterData(
    u16 mapId,
    int encounterDataId,
    void *dest,
    int size)
{
    const OverworldWildEncounterLookupDataBlobHeader *blob;
    const OverworldWildEncounterLookupDirectoryEntry *entry;

    if (mapId == MAP_NOTHING
        || encounterDataId < 0
        || encounterDataId > 0xFFFF) {
        return FALSE;
    }

    blob = OverworldWildHelper_GetEncounterLookupDataBlob();
    entry = OverworldWildHelper_FindEncounterLookupEntry(
        blob,
        mapId,
        encounterDataId,
        TRUE);
    return OverworldWildHelper_TryCopySparseEncounterRecord(
        blob,
        entry,
        dest,
        size);
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
    (void)shinyAlreadySpawned;

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

static BOOL OverworldWildHelper_RemoveEncounter(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    int slot,
    u16 expectedGeneration,
    OverworldWildDespawnReason reason,
    u8 distance,
    OverworldWildHelperResetSlotFunc resetSlot);
static OverworldWildDespawnAuthorization OverworldWildHelper_AuthorizeDespawn(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    int slot,
    u16 expectedGeneration,
    OverworldWildDespawnReason reason,
    LocalMapObject **verifiedObject);

static void OverworldWildHelper_LoadPersonalRecord(u16 species, u8 *record)
{
    ArchiveDataLoadOfs(
        record,
        ARC_PERSONAL,
        species,
        0,
        OW_WILD_HELPER_PERSONAL_RECORD_SIZE);
}

static u16 OverworldWildHelper_ReadPersonalU16(const u8 *record, int offset)
{
    return (u16)(record[offset] | (record[offset + 1] << 8));
}

static BOOL OverworldWildHelper_LoadSpeciesName(u16 species, u16 *name)
{
    u16 header[2];
    u32 entry[2];
    u32 entryKey;
    u32 messageIndex = (u32)species + 1;
    u16 textKey;
    u32 i;

    ArchiveDataLoadOfs(
        header,
        ARC_MSG_DATA,
        OW_WILD_HELPER_SPECIES_NAME_MSG_FILE,
        0,
        sizeof(header));
    if (species >= header[0]) {
        return FALSE;
    }
    ArchiveDataLoadOfs(
        entry,
        ARC_MSG_DATA,
        OW_WILD_HELPER_SPECIES_NAME_MSG_FILE,
        sizeof(header) + species * sizeof(entry),
        sizeof(entry));
    entryKey = (765 * messageIndex * header[1]) & 0xFFFF;
    entryKey |= entryKey << 16;
    entry[0] ^= entryKey;
    entry[1] ^= entryKey;
    if (entry[1] == 0
        || entry[1] > OW_WILD_HELPER_SPECIES_NAME_CAPACITY) {
        return FALSE;
    }
    ArchiveDataLoadOfs(
        name,
        ARC_MSG_DATA,
        OW_WILD_HELPER_SPECIES_NAME_MSG_FILE,
        entry[0],
        entry[1] * sizeof(*name));
    textKey = (u16)(messageIndex * 596947);
    for (i = 0; i < entry[1]; i++) {
        name[i] ^= textKey;
        textKey += 18749;
    }
    return name[entry[1] - 1] == 0xFFFF;
}

static u8 OverworldWildHelper_CalculatePlayerBallShakes(u16 species)
{
    u8 personal[OW_WILD_HELPER_PERSONAL_RECORD_SIZE];
    u32 catchValue;
    u32 shakeChance;
    u8 shakes;

    OverworldWildHelper_LoadPersonalRecord(species, personal);
    catchValue = (personal[OW_WILD_HELPER_PERSONAL_CATCH_RATE_OFFSET] + 2) / 3;
    if (catchValue >= OW_WILD_HELPER_NELEMS(sOverworldWildHelperShakeChance)) {
        catchValue = OW_WILD_HELPER_NELEMS(sOverworldWildHelperShakeChance) - 1;
    }
    shakeChance = sOverworldWildHelperShakeChance[catchValue];
    for (shakes = 0; shakes < 4; shakes++) {
        if (gf_rand() >= shakeChance) {
            break;
        }
    }
    return shakes;
}

static u32 OverworldWildHelper_GetExperienceAtLevel(u8 growthRate, u8 level)
{
    u32 levelSquared = (u32)level * level;
    u32 levelCubed = levelSquared * level;

    if (level <= 1) {
        return 0;
    }

    switch (growthRate) {
    case 1: /* Erratic */
        if (level <= 50) {
            return levelCubed * (100 - level) / 50;
        }
        if (level <= 68) {
            return levelCubed * (150 - level) / 100;
        }
        if (level <= 98) {
            return levelCubed * ((1911 - 10 * level) / 3) / 500;
        }
        return levelCubed * (160 - level) / 100;
    case 2: /* Fluctuating */
        if (level <= 15) {
            return levelCubed * (((level + 1) / 3) + 24) / 50;
        }
        if (level <= 36) {
            return levelCubed * (level + 14) / 50;
        }
        return levelCubed * ((level / 2) + 32) / 50;
    case 3: /* Medium Slow */
        return 6 * levelCubed / 5
            - 15 * levelSquared
            + 100 * level
            - 140;
    case 4: /* Fast */
        return 4 * levelCubed / 5;
    case 5: /* Slow */
        return 5 * levelCubed / 4;
    default: /* Medium Fast */
        return levelCubed;
    }
}

static void OverworldWildHelper_InitCapturedMoves(
    struct PartyPokemon *pokemon,
    u16 species,
    u8 form,
    u8 level)
{
    u32 learnset[MAX_LEVELUP_MOVES];
    u16 moves[4] = { MOVE_NONE, MOVE_NONE, MOVE_NONE, MOVE_NONE };
    u32 value;
    int moveCount = 0;
    int i;
    int j;

    LoadLevelUpLearnset_HandleAlternateForm(species, form, learnset);
    for (i = 0; i < MAX_LEVELUP_MOVES; i++) {
        u32 entry = learnset[i];
        u16 move = LEVEL_UP_LEARNSET_MOVE(entry);

        if (move == LEVEL_UP_LEARNSET_END) {
            break;
        }
        if (LEVEL_UP_LEARNSET_LEVEL(entry) > level || move == MOVE_NONE) {
            continue;
        }
        for (j = 0; j < moveCount && moves[j] != move; j++) {
        }
        if (j < moveCount) {
            continue;
        }
        if (moveCount < 4) {
            moves[moveCount++] = move;
        } else {
            moves[0] = moves[1];
            moves[1] = moves[2];
            moves[2] = moves[3];
            moves[3] = move;
        }
    }
    for (i = 0; i < 4; i++) {
        value = moves[i];
        SetMonData(pokemon, MON_DATA_MOVE1 + i, &value);
        value = moves[i] == MOVE_NONE ? 0 : GetMoveMaxPP(moves[i], 0);
        SetMonData(pokemon, MON_DATA_MOVE1PP + i, &value);
        SetMonData(pokemon, MON_DATA_MOVE1MAXPP + i, &value);
        value = 0;
        SetMonData(pokemon, MON_DATA_MOVE1PPUP + i, &value);
    }
}

static void OverworldWildHelper_InitCapturedStats(
    struct PartyPokemon *pokemon,
    u16 species,
    const u8 *personal,
    u8 level)
{
    u32 value;
    int nature = GetMonNature(pokemon);
    int raisedStat = nature / 5;
    int loweredStat = nature % 5;
    int i;

    value = level;
    SetMonData(pokemon, MON_DATA_LEVEL, &value);

    value = species == SPECIES_SHEDINJA
        ? 1
        : ((2 * personal[PERSONAL_BASE_HP]
                + GetMonData(pokemon, MON_DATA_HP_IV, NULL)
                + GetMonData(pokemon, MON_DATA_HP_EV, NULL) / 4)
                    * level / 100)
            + level + 10;
    SetMonData(pokemon, MON_DATA_MAXHP, &value);
    SetMonData(pokemon, MON_DATA_HP, &value);

    for (i = 0; i < 5; i++) {
        value = ((2 * personal[PERSONAL_BASE_ATTACK + i]
                    + GetMonData(pokemon, MON_DATA_ATK_IV + i, NULL)
                    + GetMonData(pokemon, MON_DATA_ATK_EV + i, NULL) / 4)
                        * level / 100)
            + 5;
        if (raisedStat != loweredStat) {
            if (i == raisedStat) {
                value = value * 110 / 100;
            } else if (i == loweredStat) {
                value = value * 90 / 100;
            }
        }
        SetMonData(pokemon, MON_DATA_ATTACK + i, &value);
    }
}

static void OverworldWildHelper_InitCapturedBox(
    struct PartyPokemon *pokemon,
    const OverworldWildSpawn *spawn,
    const u8 *personal,
    u32 trainerId)
{
    BOOL fastMode;
    u16 speciesName[OW_WILD_HELPER_SPECIES_NAME_CAPACITY];
    u32 value;
    u32 randomIvs;
    int i;

    BoxMonInit(&pokemon->box);
    fastMode = BoxMonSetFastModeOn(&pokemon->box);

    value = spawn->personality;
    SetBoxMonData(&pokemon->box, MON_DATA_PERSONALITY, &value);
    value = trainerId;
    SetBoxMonData(&pokemon->box, MON_DATA_OTID, &value);
    value = LANG_ENGLISH;
    SetBoxMonData(&pokemon->box, MON_DATA_GAME_LANGUAGE, &value);
    value = spawn->species;
    SetBoxMonData(&pokemon->box, MON_DATA_SPECIES, &value);
    if (OverworldWildHelper_LoadSpeciesName(spawn->species, speciesName)) {
        SetBoxMonData(&pokemon->box, MON_DATA_NICKNAME, speciesName);
    }
    if (spawn->form != 0) {
        value = spawn->form;
        SetBoxMonData(&pokemon->box, MON_DATA_FORM, &value);
    }
    value = OverworldWildHelper_GetExperienceAtLevel(
        personal[OW_WILD_HELPER_PERSONAL_GROWTH_OFFSET],
        spawn->level);
    SetBoxMonData(&pokemon->box, MON_DATA_EXPERIENCE, &value);
    value = personal[OW_WILD_HELPER_PERSONAL_FRIENDSHIP_OFFSET];
    SetBoxMonData(&pokemon->box, MON_DATA_FRIENDSHIP, &value);
    value = spawn->level;
    SetBoxMonData(&pokemon->box, MON_DATA_MET_LEVEL, &value);
    value = VERSION_GOLD;
    SetBoxMonData(&pokemon->box, MON_DATA_GAME_VERSION, &value);
    value = ITEM_POKE_BALL;
    SetBoxMonData(&pokemon->box, MON_DATA_POKEBALL, &value);

    randomIvs = gf_rand();
    for (i = 0; i < 3; i++) {
        value = (randomIvs >> (i * 5)) & 31;
        SetBoxMonData(&pokemon->box, MON_DATA_HP_IV + i, &value);
    }
    randomIvs = gf_rand();
    for (i = 0; i < 3; i++) {
        value = (randomIvs >> (i * 5)) & 31;
        SetBoxMonData(&pokemon->box, MON_DATA_SPEED_IV + i, &value);
    }

    value = OverworldWildHelper_ReadPersonalU16(
        personal,
        OW_WILD_HELPER_PERSONAL_ABILITY_1_OFFSET);
    if ((spawn->personality & 1) != 0) {
        u32 secondAbility = OverworldWildHelper_ReadPersonalU16(
            personal,
            OW_WILD_HELPER_PERSONAL_ABILITY_2_OFFSET);
        if (secondAbility != 0) {
            value = secondAbility;
        }
    }
    SetBoxMonData(&pokemon->box, MON_DATA_ABILITY, &value);
    value = GetBoxMonGender(&pokemon->box);
    SetBoxMonData(&pokemon->box, MON_DATA_GENDER, &value);
    BoxMonSetFastModeOff(&pokemon->box, fastMode);
}

static BOOL OverworldWildHelper_IsPlayerBallCaptureTargetCurrent(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    int slot = sOverworldWildHelperPlayerBallProjectile.impactSlot;

    return slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && state == sOverworldWildHelperPlayerBallProjectile.state
        && state->mapGeneration
            == sOverworldWildHelperPlayerBallProjectile.mapGeneration
        && OverworldWildHelper_IsExactObject(fieldSystem, state, slot)
        && state->spawns[slot].encounterGeneration
            == sOverworldWildHelperPlayerBallProjectile
                .impactEncounterGeneration;
}

static void OverworldWildHelper_ReservePlayerBallCaptureTarget(
    OverworldWildSpawnState *state)
{
    int slot = sOverworldWildHelperPlayerBallProjectile.impactSlot;
    LocalMapObject *targetObject = state->spawns[slot].object;

    state->captureTargetMask |= (u16)(1u << slot);
    state->movementCooldowns[slot] = 0xFF;
    MapObject_SetBits(targetObject, BIT_VANISH | MAPOBJECTFLAG_UNK18);
}

static void OverworldWildHelper_RestorePlayerBallCaptureTarget(
    FieldSystem *fieldSystem)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    OverworldWildSpawnState *state = projectile->state;
    int slot = projectile->impactSlot;
    LocalMapObject *targetObject;

    if (state != NULL && slot >= 0 && slot < OW_WILD_MAX_SPAWNS) {
        state->captureTargetMask &= (u16)~(1u << slot);
    }
    if (state == NULL
        || !OverworldWildHelper_IsPlayerBallCaptureTargetCurrent(
            fieldSystem,
            state)) {
        return;
    }
    targetObject = state->spawns[slot].object;
    state->movementCooldowns[slot] = OW_WILD_HELPER_PLAYER_BALL_IMPACT_FRAMES;
    MapObject_ClearBits(targetObject, BIT_VANISH);
    if (!projectile->targetHadPassThrough) {
        MapObject_ClearBits(targetObject, MAPOBJECTFLAG_UNK18);
    }
}

static BOOL OverworldWildHelper_TryStoreCapturedPokemon(
    FieldSystem *fieldSystem,
    const OverworldWildSpawn *spawn)
{
    struct PlayerProfile *profile;
    struct PartyPokemon *pokemon;
    struct Party *party;
    PCStorage *storage;
    u8 personal[OW_WILD_HELPER_PERSONAL_RECORD_SIZE];
    u16 personalSpecies;
    u32 value;
    BOOL stored;

    if (fieldSystem == NULL || fieldSystem->savedata == NULL || spawn == NULL) {
        return FALSE;
    }
    profile = Sav2_PlayerData_GetProfileAddr(fieldSystem->savedata);
    pokemon = AllocMonZeroed(HEAPID_WORLD);
    if (profile == NULL || pokemon == NULL) {
        sys_FreeMemoryEz(pokemon);
        return FALSE;
    }
    ZeroMonData(pokemon);
    personalSpecies = PokeOtherFormMonsNoGet(spawn->species, spawn->form);
    OverworldWildHelper_LoadPersonalRecord(personalSpecies, personal);
    OverworldWildHelper_InitCapturedBox(
        pokemon,
        spawn,
        personal,
        profile->id);
    OverworldWildHelper_InitCapturedMoves(
        pokemon,
        spawn->species,
        spawn->form,
        spawn->level);
    OverworldWildHelper_InitCapturedStats(
        pokemon,
        spawn->species,
        personal,
        spawn->level);
    sub_020720FC(
        pokemon,
        profile,
        ITEM_POKE_BALL,
        ITEM_POKE_BALL,
        OW_WILD_HELPER_CAPTURE_ENCOUNTER_TYPE,
        HEAPID_WORLD);
    TrySetBabyBondRibbon(pokemon);

    if (spawn->shiny != BoxMonIsShiny(&pokemon->box)) {
        value = spawn->shiny ? OVERWORLD_WILD_BATTLE_SHINY_OTID
                             : profile->id ^ 8;
        SetMonData(pokemon, MON_DATA_OTID, &value);
    }

    party = SaveData_GetPlayerPartyPtr(fieldSystem->savedata);
    stored = party != NULL && PokeParty_Add(party, pokemon);
    if (!stored) {
        storage = SaveArray_Get(
            fieldSystem->savedata,
            OW_WILD_HELPER_PC_STORAGE_SAVE_BLOCK);
        stored = storage != NULL
            && PCStorage_PlaceMonInFirstEmptySlotInAnyBox(
                storage,
                &pokemon->box);
    }
    if (stored) {
        UpdatePokedexWithReceivedSpecies(fieldSystem->savedata, pokemon);
    }
    sys_FreeMemoryEz(pokemon);
    return stored;
}

static void OverworldWildHelper_ResetPlayerBallProjectile(void)
{
    sOverworldWildHelperPlayerBallProjectile.fieldSystem = NULL;
    sOverworldWildHelperPlayerBallProjectile.state = NULL;
    sOverworldWildHelperPlayerBallProjectile.manager = NULL;
    sOverworldWildHelperPlayerBallProjectile.objects = NULL;
    sOverworldWildHelperPlayerBallProjectile.object = NULL;
    sOverworldWildHelperPlayerBallProjectile.startX = 0;
    sOverworldWildHelperPlayerBallProjectile.startY = 0;
    sOverworldWildHelperPlayerBallProjectile.startZ = 0;
    sOverworldWildHelperPlayerBallProjectile.targetX = 0;
    sOverworldWildHelperPlayerBallProjectile.targetY = 0;
    sOverworldWildHelperPlayerBallProjectile.targetZ = 0;
    sOverworldWildHelperPlayerBallProjectile.startHeight = 0;
    sOverworldWildHelperPlayerBallProjectile.mapId = MAP_NOTHING;
    sOverworldWildHelperPlayerBallProjectile.mapGeneration = 0;
    sOverworldWildHelperPlayerBallProjectile.impactEncounterGeneration = 0;
    sOverworldWildHelperPlayerBallProjectile.impactSlot = -1;
    sOverworldWildHelperPlayerBallProjectile.elapsedFrames = 0;
    sOverworldWildHelperPlayerBallProjectile.totalFrames = 0;
    sOverworldWildHelperPlayerBallProjectile.phase = 0;
    sOverworldWildHelperPlayerBallProjectile.objectId = 0;
    sOverworldWildHelperPlayerBallProjectile.shakeChecks = 0;
    sOverworldWildHelperPlayerBallProjectile.shakeIndex = 0;
    sOverworldWildHelperPlayerBallProjectile.targetHadPassThrough = FALSE;
    sOverworldWildHelperPlayerBallChargeSoundTimer = 0;
}

static BOOL OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(
    FieldSystem *fieldSystem)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    MapObjectMan *manager;
    int i;

    if (projectile->phase == 0
        || fieldSystem == NULL
        || fieldSystem != gFieldSysPtr
        || fieldSystem != projectile->fieldSystem
        || fieldSystem->location == NULL
        || fieldSystem->mapObjectMan == NULL
        || projectile->object == NULL
        || projectile->mapId != fieldSystem->location->mapId) {
        return FALSE;
    }

    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    if (manager != projectile->manager
        || manager->objects != projectile->objects) {
        return FALSE;
    }

    for (i = 0; i < (int)manager->object_count; i++) {
        if (projectile->object != &manager->objects[i]) {
            continue;
        }
        return (projectile->object->flags & MAPOBJECTFLAG_ACTIVE) != 0
            && projectile->object->id == projectile->objectId;
    }

    return FALSE;
}

static void OverworldWildHelper_DeletePlayerBallObject(LocalMapObject *object)
{
    object->faceVec[0] = 0;
    object->faceVec[1] = 0;
    object->faceVec[2] = 0;
    object->unk88[0] = 0;
    object->unk88[1] = 0;
    object->unk88[2] = 0;
    object->unk94[0] = 0;
    object->unk94[1] = 0;
    object->unk94[2] = 0;
    MapObject_ClearBits(
        object,
        BIT_JUMP_START | BIT_MOVE_START | MAPOBJECTFLAG_UNK13);
    DeleteMapObject(object);
}

static void OverworldWildHelper_CancelPlayerBallProjectile(
    FieldSystem *fieldSystem)
{
    LocalMapObject *object = sOverworldWildHelperPlayerBallProjectile.object;
    OverworldWildSpawnState *state =
        sOverworldWildHelperPlayerBallProjectile.state;
    int slot = sOverworldWildHelperPlayerBallProjectile.impactSlot;

    if (state != NULL && slot >= 0 && slot < OW_WILD_MAX_SPAWNS) {
        state->captureTargetMask &= (u16)~(1u << slot);
    }

    if (fieldSystem != NULL && fieldSystem->taskman != NULL) {
        OverworldWildHelper_ResetPlayerBallProjectile();
        return;
    }
    OverworldWildHelper_RestorePlayerBallCaptureTarget(fieldSystem);
    if (OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(fieldSystem)) {
        OverworldWildHelper_DeletePlayerBallObject(object);
    }
    OverworldWildHelper_ResetPlayerBallProjectile();
}

static BOOL OverworldWildHelper_PlayerBallObjectIdAvailable(FieldSystem *fieldSystem)
{
    MapObjectMan *manager;
    int i;

    if (fieldSystem == NULL
        || fieldSystem != gFieldSysPtr
        || fieldSystem->taskman != NULL
        || fieldSystem->location == NULL
        || fieldSystem->mapObjectMan == NULL) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    for (i = 0; i < (int)manager->object_count; i++) {
        LocalMapObject *object = &manager->objects[i];

        if ((object->flags & MAPOBJECTFLAG_ACTIVE) != 0
            && object->id == OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID) {
            if (sOverworldWildHelperPlayerBallProjectile.phase
                    == OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE
                && fieldSystem->taskman == NULL) {
                OverworldWildHelper_DeletePlayerBallObject(object);
                continue;
            }
            return FALSE;
        }
    }
    return TRUE;
}

static s32 OverworldWildHelper_LerpPlayerBallValue(
    s32 start,
    s32 target,
    u8 elapsed,
    u8 total)
{
    if (elapsed >= total) {
        return target;
    }
    return start + (((target - start) * elapsed) / total);
}

static void OverworldWildHelper_TickPlayerBallChargeSound(void)
{
    u8 interval = OW_WILD_HELPER_PLAYER_BALL_CHARGE_SLOW_INTERVAL
        - (sOverworldWildHelperPlayerBallChargeFrames
            * (OW_WILD_HELPER_PLAYER_BALL_CHARGE_SLOW_INTERVAL
                - OW_WILD_HELPER_PLAYER_BALL_CHARGE_FAST_INTERVAL))
            / OW_WILD_HELPER_PLAYER_BALL_MAX_CHARGE_FRAMES;

    if (sOverworldWildHelperPlayerBallChargeFrames
        >= OW_WILD_HELPER_PLAYER_BALL_MAX_CHARGE_FRAMES) {
        if (sOverworldWildHelperPlayerBallChargeSoundTimer
            != OW_WILD_HELPER_PLAYER_BALL_CHARGE_SOUND_COMPLETE) {
            PlaySE(OW_WILD_HELPER_PLAYER_BALL_CHARGE_SE);
            sOverworldWildHelperPlayerBallChargeSoundTimer =
                OW_WILD_HELPER_PLAYER_BALL_CHARGE_SOUND_COMPLETE;
        }
        return;
    }
    if (sOverworldWildHelperPlayerBallChargeSoundTimer > interval) {
        sOverworldWildHelperPlayerBallChargeSoundTimer = interval;
    }
    if (sOverworldWildHelperPlayerBallChargeSoundTimer != 0) {
        sOverworldWildHelperPlayerBallChargeSoundTimer--;
    }
    if (sOverworldWildHelperPlayerBallChargeSoundTimer == 0) {
        PlaySE(OW_WILD_HELPER_PLAYER_BALL_CHARGE_SE);
        sOverworldWildHelperPlayerBallChargeSoundTimer = interval;
    }
}

static int OverworldWildHelper_FindPlayerBallHit(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    s32 oldX,
    s32 oldZ,
    s32 newX,
    s32 newZ)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    s32 startX;
    s32 startZ;
    s32 endX;
    s32 endZ;
    s32 stepX;
    s32 stepZ;
    s32 lengthSquared;
    s32 radius = OW_WILD_HELPER_PLAYER_BALL_HIT_RADIUS_FX32
        >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
    s32 bestEntry = 0x7FFFFFFF;
    int bestSlot = -1;
    int i;

    if (!OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
        || state->presentationRestorePending
        || state->mapGeneration != projectile->mapGeneration) {
        return -1;
    }
    startX = oldX >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
    startZ = oldZ >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
    endX = newX >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
    endZ = newZ >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
    stepX = endX - startX;
    stepZ = endZ - startZ;
    lengthSquared = stepX * stepX + stepZ * stepZ;
    if (lengthSquared == 0) {
        return -1;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        LocalMapObject *targetObject;
        s32 targetX;
        s32 targetZ;
        s32 relativeX;
        s32 relativeZ;
        s32 dot;
        s32 distanceSquared;
        s32 entry;

        if (!OverworldWildHelper_IsExactObject(fieldSystem, state, i)) {
            continue;
        }
        targetObject = state->spawns[i].object;
        if (state->movementPhantomHidden[i]
            || (targetObject->flags & BIT_VANISH) != 0) {
            continue;
        }
        targetX = (s32)targetObject->posVec[0]
            >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
        targetZ = (s32)targetObject->posVec[2]
            >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
        if (targetX < OverworldWildHelper_Min(startX, endX) - radius
            || targetX > OverworldWildHelper_Max(startX, endX) + radius
            || targetZ < OverworldWildHelper_Min(startZ, endZ) - radius
            || targetZ > OverworldWildHelper_Max(startZ, endZ) + radius) {
            continue;
        }
        relativeX = targetX - startX;
        relativeZ = targetZ - startZ;
        dot = relativeX * stepX + relativeZ * stepZ;
        if (dot <= 0) {
            distanceSquared = relativeX * relativeX + relativeZ * relativeZ;
            entry = 0;
        } else if (dot >= lengthSquared) {
            relativeX = targetX - endX;
            relativeZ = targetZ - endZ;
            distanceSquared = relativeX * relativeX + relativeZ * relativeZ;
            entry = lengthSquared;
        } else {
            s32 cross = relativeX * stepZ - relativeZ * stepX;

            if (cross * cross > radius * radius * lengthSquared) {
                continue;
            }
            distanceSquared = 0;
            entry = dot;
        }
        if (distanceSquared > radius * radius) {
            continue;
        }
        if (entry < bestEntry) {
            bestEntry = entry;
            bestSlot = i;
        }
    }
    return bestSlot;
}

static BOOL OverworldWildHelper_TryApplyPlayerBallAimAssist(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    LocalMapObject *playerObject,
    int directionX,
    int directionY,
    s32 distanceFx32)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    s32 playerX = (s32)playerObject->posVec[0];
    s32 playerZ = (s32)playerObject->posVec[2];
    s32 bestCross = 0x7FFFFFFF;
    s32 bestForward = 0x7FFFFFFF;
    int bestSlot = -1;
    int i;

    if (!OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
        || state->presentationRestorePending
        || state->mapGeneration != projectile->mapGeneration) {
        return FALSE;
    }
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        LocalMapObject *targetObject;
        s32 deltaX;
        s32 deltaZ;
        s32 forward;
        s32 cross;

        if (!OverworldWildHelper_IsExactObject(fieldSystem, state, i)) {
            continue;
        }
        targetObject = state->spawns[i].object;
        if (state->movementPhantomHidden[i]
            || (targetObject->flags & BIT_VANISH) != 0) {
            continue;
        }
        deltaX = (s32)targetObject->posVec[0] - playerX;
        deltaZ = (s32)targetObject->posVec[2] - playerZ;
        forward = deltaX * directionX + deltaZ * directionY;
        cross = OverworldWildHelper_Abs(
            deltaX * directionY - deltaZ * directionX);
        if (forward < OW_WILD_HELPER_PLAYER_BALL_AIM_MIN_FORWARD_FX32
            || forward > distanceFx32
            || cross > OW_WILD_HELPER_PLAYER_BALL_AIM_HALF_WIDTH_FX32) {
            continue;
        }
        if (cross < bestCross
            || (cross == bestCross && forward < bestForward)) {
            bestCross = cross;
            bestForward = forward;
            bestSlot = i;
        }
    }
    if (bestSlot < 0
        || !OverworldWildHelper_IsExactObject(fieldSystem, state, bestSlot)) {
        return FALSE;
    }
    projectile->targetX = (s32)state->spawns[bestSlot].object->posVec[0];
    projectile->targetY = (s32)state->spawns[bestSlot].object->posVec[1];
    projectile->targetZ = (s32)state->spawns[bestSlot].object->posVec[2];
    return TRUE;
}

static BOOL OverworldWildHelper_StartPlayerBallImpact(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    OverworldWildHelperPrepareCaptureTargetFunc prepareCaptureTarget)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    LocalMapObject *ballObject;
    LocalMapObject *targetObject;

    if (slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || state == NULL
        || state->mapGeneration != projectile->mapGeneration
        || !OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(fieldSystem)
        || !OverworldWildHelper_IsExactObject(fieldSystem, state, slot)) {
        return FALSE;
    }
    if (prepareCaptureTarget != NULL) {
        prepareCaptureTarget(state, slot);
    }
    if (!OverworldWildHelper_IsExactObject(fieldSystem, state, slot)) {
        return FALSE;
    }
    ballObject = projectile->object;
    targetObject = state->spawns[slot].object;
    ballObject->posVec[0] = targetObject->posVec[0];
    ballObject->posVec[1] = targetObject->posVec[1];
    ballObject->posVec[2] = targetObject->posVec[2];
    ballObject->hCurr = targetObject->hCurr;
    ballObject->faceVec[1] = targetObject->faceVec[1]
        + OW_WILD_HELPER_PLAYER_BALL_HAND_HEIGHT_FX32;
    ballObject->unk88[1] = ballObject->faceVec[1];
    projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT;
    projectile->elapsedFrames = 0;
    projectile->totalFrames = OW_WILD_HELPER_PLAYER_BALL_IMPACT_FRAMES;
    projectile->impactSlot = (s8)slot;
    projectile->impactEncounterGeneration =
        state->spawns[slot].encounterGeneration;
    projectile->shakeChecks =
        OverworldWildHelper_CalculatePlayerBallShakes(
            state->spawns[slot].species);
    projectile->shakeIndex = 0;
    projectile->targetHadPassThrough =
        (targetObject->flags & MAPOBJECTFLAG_UNK18) != 0;
    state->captureTargetMask |= (u16)(1u << slot);
    if (state->movementCooldowns[slot]
        < OW_WILD_HELPER_PLAYER_BALL_IMPACT_FRAMES) {
        state->movementCooldowns[slot] =
            OW_WILD_HELPER_PLAYER_BALL_IMPACT_FRAMES;
    }
    PlayCry(state->spawns[slot].species, state->spawns[slot].form);
    (void)ov01_02203A48(
        targetObject,
        OW_WILD_HELPER_PLAYER_BALL_IMPACT_BUBBLE_ID);
    return TRUE;
}

static BOOL OverworldWildHelper_ApplyPlayerBallChargeRender(
    FieldSystem *fieldSystem)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    LocalMapObject *playerObject;
    LocalMapObject *object = projectile->object;
    u8 pulseFrame;
    s32 pulseStep;
    s32 rise;
    s32 pulse;
    s32 renderY;

    if (object == NULL
        || fieldSystem == NULL
        || fieldSystem->playerAvatar == NULL
        || fieldSystem->playerAvatar->mapObject == NULL) {
        return FALSE;
    }
    playerObject = fieldSystem->playerAvatar->mapObject;
    if (playerObject->curFacing > 3) {
        return FALSE;
    }
    rise = (sOverworldWildHelperPlayerBallChargeFrames
        * OW_WILD_HELPER_PLAYER_BALL_CHARGE_RISE_FX32)
        / OW_WILD_HELPER_PLAYER_BALL_MAX_CHARGE_FRAMES;
    pulseFrame = projectile->elapsedFrames & 15;
    if (pulseFrame > 8) {
        pulseFrame = 16 - pulseFrame;
    }
    pulseStep = OW_WILD_HELPER_PLAYER_BALL_CHARGE_PULSE_STEP_FX32;
    if (sOverworldWildHelperPlayerBallChargeFrames
        == OW_WILD_HELPER_PLAYER_BALL_MAX_CHARGE_FRAMES) {
        pulseStep *= 2;
    }
    pulse = pulseFrame * pulseStep;
    renderY = (s32)playerObject->posVec[1];
    MapObject_SetCurrentX(object, MapObject_GetCurrentX(playerObject));
    MapObject_SetCurrentY(object, MapObject_GetCurrentY(playerObject));
    object->xInit = playerObject->xInit;
    object->yInit = playerObject->yInit;
    object->xPrev = playerObject->xPrev;
    object->yPrev = playerObject->yPrev;
    object->hPrev = playerObject->hPrev;
    object->posVec[0] = (u32)((s32)playerObject->posVec[0]
        + OverworldWildHelper_DirectionDeltaX(playerObject->curFacing)
            * OW_WILD_HELPER_PLAYER_BALL_FORWARD_OFFSET_FX32);
    object->posVec[1] = (u32)renderY;
    object->posVec[2] = (u32)((s32)playerObject->posVec[2]
        + OverworldWildHelper_DirectionDeltaY(playerObject->curFacing)
            * OW_WILD_HELPER_PLAYER_BALL_FORWARD_OFFSET_FX32);
    object->hCurr = (int)(renderY >> 15);
    object->curFacing = playerObject->curFacing;
    object->nextFacing = playerObject->nextFacing;
    projectile->startHeight = (s32)playerObject->faceVec[1]
        + OW_WILD_HELPER_PLAYER_BALL_HAND_HEIGHT_FX32
        + rise
        + pulse;
    object->faceVec[0] = 0;
    object->faceVec[1] = projectile->startHeight;
    object->faceVec[2] = 0;
    object->unk88[0] = 0;
    object->unk88[1] = object->faceVec[1];
    object->unk88[2] = 0;
    object->unk94[0] = 0;
    object->unk94[1] = 0;
    object->unk94[2] = 0;
    MapObject_ClearBits(object, BIT_VANISH);
    return TRUE;
}

static void OverworldWildHelper_ApplyPlayerBallRender(void)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    LocalMapObject *object = projectile->object;
    u32 curve;
    s32 renderX;
    s32 renderY;
    s32 renderZ;
    s32 handHeight;
    s32 arc;

    if (object == NULL || projectile->totalFrames == 0) {
        return;
    }
    renderX = OverworldWildHelper_LerpPlayerBallValue(
        projectile->startX,
        projectile->targetX,
        projectile->elapsedFrames,
        projectile->totalFrames);
    renderY = OverworldWildHelper_LerpPlayerBallValue(
        projectile->startY,
        projectile->targetY,
        projectile->elapsedFrames,
        projectile->totalFrames);
    renderZ = OverworldWildHelper_LerpPlayerBallValue(
        projectile->startZ,
        projectile->targetZ,
        projectile->elapsedFrames,
        projectile->totalFrames);
    handHeight = OverworldWildHelper_LerpPlayerBallValue(
        projectile->startHeight,
        0,
        projectile->elapsedFrames,
        projectile->totalFrames);
    curve = (4
        * projectile->elapsedFrames
        * (projectile->totalFrames - projectile->elapsedFrames))
        / projectile->totalFrames;
    arc = (OW_WILD_HELPER_PLAYER_BALL_ARC_HEIGHT_FX32 * (s32)curve)
        / projectile->totalFrames;
    object->posVec[0] = (u32)renderX;
    object->posVec[1] = (u32)renderY;
    object->posVec[2] = (u32)renderZ;
    object->hCurr = (int)(renderY >> 15);
    object->faceVec[0] = 0;
    object->faceVec[1] = (u32)(handHeight + arc);
    object->faceVec[2] = 0;
    object->unk88[0] = 0;
    object->unk88[1] = object->faceVec[1];
    object->unk88[2] = 0;
    object->unk94[0] = 0;
    object->unk94[1] = 0;
    object->unk94[2] = 0;
    MapObject_ClearBits(object, BIT_VANISH);
}

static BOOL OverworldWildHelper_TryStartPlayerBallCharge(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    MapObjectMan *manager;
    LocalMapObject *playerObject;
    LocalMapObject *object;

    if (projectile->phase != OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE
        || fieldSystem == NULL
        || fieldSystem->taskman != NULL
        || state == NULL
        || state->pendingSlot >= 0
        || state->movementQueuedBattleSlot >= 0
        || fieldSystem->playerAvatar == NULL
        || fieldSystem->playerAvatar->mapObject == NULL
        || !OverworldWildHelper_PlayerBallObjectIdAvailable(fieldSystem)) {
        return FALSE;
    }
    playerObject = fieldSystem->playerAvatar->mapObject;
    if (playerObject->curFacing > 3) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    OverworldWildCustomMovement_SetFieldSystem(fieldSystem);
    object = CreateSpecialFieldObjectWithParams(
        manager,
        MapObject_GetCurrentX(playerObject),
        MapObject_GetCurrentY(playerObject),
        playerObject->curFacing,
        OW_WILD_HELPER_PLAYER_BALL_TAG,
        OW_WILD_MOVE_STOCK_IDLE,
        fieldSystem->location->mapId,
        0,
        0,
        0);
    if (object == NULL) {
        return FALSE;
    }

    MapObject_SetID(object, OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID);
    MapObject_SetBits(object, MAPOBJECTFLAG_UNK18);
    MapObject_ClearBits(object, BIT_VANISH);
    projectile->fieldSystem = fieldSystem;
    projectile->state = state;
    projectile->manager = manager;
    projectile->objects = manager->objects;
    projectile->object = object;
    projectile->mapId = fieldSystem->location->mapId;
    projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_CHARGING;
    projectile->objectId = OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID;
    projectile->elapsedFrames = 0;
    projectile->totalFrames = 0;
    if (!OverworldWildHelper_ApplyPlayerBallChargeRender(fieldSystem)) {
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return FALSE;
    }
    sOverworldWildHelperPlayerBallChargeSoundTimer = 0;
    OverworldWildHelper_TickPlayerBallChargeSound();
    return TRUE;
}

static BOOL OverworldWildHelper_TryLaunchPlayerBallProjectile(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    s32 distanceFx32)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    LocalMapObject *playerObject;
    LocalMapObject *object;
    int directionX;
    int directionY;
    int distanceSpan;
    int distanceTiles;
    int totalFrames;

    if (projectile->phase != OW_WILD_HELPER_PLAYER_BALL_PHASE_CHARGING
        || fieldSystem == NULL
        || fieldSystem->taskman != NULL
        || fieldSystem->playerAvatar == NULL
        || fieldSystem->playerAvatar->mapObject == NULL
        || !OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
        || state->presentationRestorePending
        || !OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(fieldSystem)) {
        return FALSE;
    }
    playerObject = fieldSystem->playerAvatar->mapObject;
    if (playerObject->curFacing > 3) {
        return FALSE;
    }
    object = projectile->object;
    projectile->mapGeneration = state->mapGeneration;
    projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_FLYING;
    projectile->elapsedFrames = 0;
    projectile->startX = (s32)object->posVec[0];
    projectile->startY = (s32)object->posVec[1];
    projectile->startZ = (s32)object->posVec[2];
    directionX = OverworldWildHelper_DirectionDeltaX(playerObject->curFacing);
    directionY = OverworldWildHelper_DirectionDeltaY(playerObject->curFacing);
    projectile->targetX = (s32)playerObject->posVec[0]
        + directionX * distanceFx32;
    projectile->targetY = (s32)playerObject->posVec[1];
    projectile->targetZ = (s32)playerObject->posVec[2]
        + directionY * distanceFx32;
    (void)OverworldWildHelper_TryApplyPlayerBallAimAssist(
        fieldSystem,
        state,
        playerObject,
        directionX,
        directionY,
        distanceFx32);
    distanceSpan = OverworldWildHelper_Max(
        OverworldWildHelper_Abs(projectile->targetX - projectile->startX),
        OverworldWildHelper_Abs(projectile->targetZ - projectile->startZ));
    distanceTiles = (distanceSpan + 0xFFFF) >> 16;
    totalFrames = OW_WILD_HELPER_PLAYER_BALL_BASE_FRAMES
        + distanceTiles * OW_WILD_HELPER_PLAYER_BALL_FRAMES_PER_TILE;
    if (totalFrames > OW_WILD_HELPER_PLAYER_BALL_MAX_FRAMES) {
        totalFrames = OW_WILD_HELPER_PLAYER_BALL_MAX_FRAMES;
    }
    projectile->totalFrames = (u8)totalFrames;
    OverworldWildHelper_ApplyPlayerBallRender();
    return TRUE;
}

static void OverworldWildHelper_RenderPlayerBallOnCaptureTarget(
    LocalMapObject *targetObject,
    s32 offsetX,
    s32 height)
{
    LocalMapObject *ballObject =
        sOverworldWildHelperPlayerBallProjectile.object;

    ballObject->posVec[0] = (u32)((s32)targetObject->posVec[0] + offsetX);
    ballObject->posVec[1] = targetObject->posVec[1];
    ballObject->posVec[2] = targetObject->posVec[2];
    ballObject->hCurr = targetObject->hCurr;
    ballObject->faceVec[1] = (u32)height;
    ballObject->unk88[1] = ballObject->faceVec[1];
}

static void OverworldWildHelper_BeginPlayerBallBreakout(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;

    OverworldWildHelper_RestorePlayerBallCaptureTarget(fieldSystem);
    projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_BREAKOUT;
    projectile->elapsedFrames = 0;
    projectile->totalFrames = OW_WILD_HELPER_PLAYER_BALL_RESULT_FRAMES;
    PlaySE(OW_WILD_HELPER_PLAYER_BALL_BREAKOUT_SE);
    PlayCry(
        state->spawns[projectile->impactSlot].species,
        state->spawns[projectile->impactSlot].form);
}

static BOOL OverworldWildHelper_TickPlayerBallCapture(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    OverworldWildHelperResetSlotFunc resetSlot)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    LocalMapObject *targetObject;
    s32 offset;
    u8 frame;
    u8 visibleShakes;
    LocalMapObject *verifiedTarget;

    sOverworldWildHelperPlayerBallInputArmed = TRUE;
    sOverworldWildHelperPlayerBallChargeFrames = 0;
    if (!OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(fieldSystem)
        || !OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
        || state->presentationRestorePending
        || !OverworldWildHelper_IsPlayerBallCaptureTargetCurrent(
            fieldSystem,
            state)) {
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return FALSE;
    }
    targetObject = state->spawns[projectile->impactSlot].object;

    switch (projectile->phase) {
    case OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT:
        frame = projectile->elapsedFrames;
        if (frame >= projectile->totalFrames) {
            OverworldWildHelper_ReservePlayerBallCaptureTarget(state);
            OverworldWildHelper_RenderPlayerBallOnCaptureTarget(
                targetObject,
                0,
                0);
            projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_LANDED;
            projectile->elapsedFrames = 0;
            projectile->totalFrames = OW_WILD_HELPER_PLAYER_BALL_LAND_FRAMES;
            return TRUE;
        }
        if (frame >= projectile->totalFrames / 2) {
            OverworldWildHelper_ReservePlayerBallCaptureTarget(state);
        }
        if (frame > projectile->totalFrames / 2) {
            frame = projectile->totalFrames - frame;
        }
        OverworldWildHelper_RenderPlayerBallOnCaptureTarget(
            targetObject,
            0,
            targetObject->faceVec[1]
                + OW_WILD_HELPER_PLAYER_BALL_HAND_HEIGHT_FX32
                + frame * OW_WILD_HELPER_PLAYER_BALL_IMPACT_REBOUND_STEP_FX32);
        projectile->elapsedFrames++;
        return TRUE;

    case OW_WILD_HELPER_PLAYER_BALL_PHASE_LANDED:
        OverworldWildHelper_ReservePlayerBallCaptureTarget(state);
        OverworldWildHelper_RenderPlayerBallOnCaptureTarget(targetObject, 0, 0);
        if (++projectile->elapsedFrames < projectile->totalFrames) {
            return TRUE;
        }
        if (projectile->shakeChecks == 0) {
            OverworldWildHelper_BeginPlayerBallBreakout(fieldSystem, state);
            return TRUE;
        }
        projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_SHAKING;
        projectile->elapsedFrames = 0;
        projectile->totalFrames = OW_WILD_HELPER_PLAYER_BALL_SHAKE_FRAMES;
        PlaySE(OW_WILD_HELPER_PLAYER_BALL_SHAKE_SE);
        return TRUE;

    case OW_WILD_HELPER_PLAYER_BALL_PHASE_SHAKING:
        OverworldWildHelper_ReservePlayerBallCaptureTarget(state);
        frame = projectile->elapsedFrames;
        if (frame > projectile->totalFrames / 2) {
            frame = projectile->totalFrames - frame;
        }
        offset = (frame * OW_WILD_HELPER_PLAYER_BALL_SHAKE_OFFSET_FX32)
            / (projectile->totalFrames / 2);
        if ((projectile->shakeIndex & 1) != 0) {
            offset = -offset;
        }
        OverworldWildHelper_RenderPlayerBallOnCaptureTarget(
            targetObject,
            offset,
            0);
        if (++projectile->elapsedFrames < projectile->totalFrames) {
            return TRUE;
        }
        projectile->shakeIndex++;
        visibleShakes = projectile->shakeChecks == 4
            ? 3
            : projectile->shakeChecks;
        if (projectile->shakeIndex < visibleShakes) {
            projectile->elapsedFrames = 0;
            PlaySE(OW_WILD_HELPER_PLAYER_BALL_SHAKE_SE);
            return TRUE;
        }
        if (projectile->shakeChecks < 4) {
            OverworldWildHelper_BeginPlayerBallBreakout(fieldSystem, state);
            return TRUE;
        }
        projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_CAUGHT;
        projectile->elapsedFrames = 0;
        projectile->totalFrames = OW_WILD_HELPER_PLAYER_BALL_RESULT_FRAMES;
        OverworldWildHelper_RenderPlayerBallOnCaptureTarget(targetObject, 0, 0);
        PlaySE(OW_WILD_HELPER_PLAYER_BALL_CAUGHT_SE);
        return TRUE;

    case OW_WILD_HELPER_PLAYER_BALL_PHASE_BREAKOUT:
        frame = projectile->elapsedFrames;
        if (frame >= projectile->totalFrames) {
            OverworldWildHelper_DeletePlayerBallObject(projectile->object);
            projectile->object = NULL;
            OverworldWildHelper_ResetPlayerBallProjectile();
            return FALSE;
        }
        if (frame > projectile->totalFrames / 2) {
            frame = projectile->totalFrames - frame;
        }
        OverworldWildHelper_RenderPlayerBallOnCaptureTarget(
            targetObject,
            0,
            frame * OW_WILD_HELPER_PLAYER_BALL_IMPACT_REBOUND_STEP_FX32);
        projectile->elapsedFrames++;
        return TRUE;

    case OW_WILD_HELPER_PLAYER_BALL_PHASE_CAUGHT:
        OverworldWildHelper_ReservePlayerBallCaptureTarget(state);
        OverworldWildHelper_RenderPlayerBallOnCaptureTarget(targetObject, 0, 0);
        if (++projectile->elapsedFrames < projectile->totalFrames) {
            return TRUE;
        }
        verifiedTarget = NULL;
        if (telemetry == NULL
            || resetSlot == NULL
            || OverworldWildHelper_AuthorizeDespawn(
                    fieldSystem,
                    state,
                    presentation,
                    projectile->impactSlot,
                    projectile->impactEncounterGeneration,
                    OW_WILD_DESPAWN_REASON_BATTLE_CAUGHT,
                    &verifiedTarget)
                != OW_WILD_DESPAWN_DELETE_VERIFIED_OBJECT
            || verifiedTarget != targetObject
            || !OverworldWildHelper_TryStoreCapturedPokemon(
                fieldSystem,
                &state->spawns[projectile->impactSlot])) {
            OverworldWildHelper_BeginPlayerBallBreakout(fieldSystem, state);
            return TRUE;
        }
        (void)OverworldWildHelper_RemoveEncounter(
            fieldSystem,
            state,
            presentation,
            telemetry,
            projectile->impactSlot,
            projectile->impactEncounterGeneration,
            OW_WILD_DESPAWN_REASON_BATTLE_CAUGHT,
            0,
            resetSlot);
        OverworldWildHelper_DeletePlayerBallObject(projectile->object);
        projectile->object = NULL;
        OverworldWildHelper_ResetPlayerBallProjectile();
        return FALSE;

    default:
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return FALSE;
    }
}

static BOOL OverworldWildHelper_TickPlayerBallProjectile(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    OverworldWildHelperResetSlotFunc resetSlot,
    OverworldWildHelperPrepareCaptureTargetFunc prepareCaptureTarget)
{
    u32 pad = PAD_Read();
    BOOL rDown = (pad & PAD_BUTTON_R) != 0;
    BOOL rPressed = rDown && !sOverworldWildHelperPlayerBallRWasDown;
    BOOL rReleased = !rDown && sOverworldWildHelperPlayerBallRWasDown;
    s32 distanceFx32;
    s32 oldX;
    s32 oldZ;
    int hitSlot;

    sOverworldWildHelperPlayerBallRWasDown = rDown;

    if (fieldSystem == NULL) {
        sOverworldWildHelperPlayerBallInputArmed = FALSE;
        sOverworldWildHelperPlayerBallChargeFrames = 0;
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return FALSE;
    }
    if (fieldSystem->taskman != NULL) {
        sOverworldWildHelperPlayerBallInputArmed = FALSE;
        sOverworldWildHelperPlayerBallChargeFrames = 0;
        sOverworldWildHelperPlayerBallChargeSoundTimer = 0;
        return sOverworldWildHelperPlayerBallProjectile.phase
            != OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE;
    }
    if (sOverworldWildHelperPlayerBallProjectile.phase
        == OW_WILD_HELPER_PLAYER_BALL_PHASE_CHARGING) {
        if (!sOverworldWildHelperPlayerBallInputArmed
            || (pad & PAD_BUTTON_L) != 0
            || !OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(
                fieldSystem)) {
            if (rDown) {
                sOverworldWildHelperPlayerBallInputArmed = FALSE;
            }
            sOverworldWildHelperPlayerBallChargeFrames = 0;
            OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
            return FALSE;
        }
        if (rDown) {
            if (sOverworldWildHelperPlayerBallChargeFrames
                < OW_WILD_HELPER_PLAYER_BALL_MAX_CHARGE_FRAMES) {
                sOverworldWildHelperPlayerBallChargeFrames++;
            }
            sOverworldWildHelperPlayerBallProjectile.elapsedFrames++;
            if (!OverworldWildHelper_ApplyPlayerBallChargeRender(fieldSystem)) {
                sOverworldWildHelperPlayerBallInputArmed = FALSE;
                sOverworldWildHelperPlayerBallChargeFrames = 0;
                OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
                return FALSE;
            }
            OverworldWildHelper_TickPlayerBallChargeSound();
            return TRUE;
        }
        if (rReleased) {
            if (!OverworldWildHelper_ApplyPlayerBallChargeRender(fieldSystem)) {
                sOverworldWildHelperPlayerBallInputArmed = FALSE;
                sOverworldWildHelperPlayerBallChargeFrames = 0;
                OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
                return FALSE;
            }
            sOverworldWildHelperPlayerBallChargeSoundTimer = 0;
            distanceFx32 = OW_WILD_HELPER_PLAYER_BALL_MIN_DISTANCE_FX32
                + sOverworldWildHelperPlayerBallChargeFrames
                    * OW_WILD_HELPER_PLAYER_BALL_CHARGE_STEP_FX32;
            sOverworldWildHelperPlayerBallChargeFrames = 0;
            if (OverworldWildHelper_TryLaunchPlayerBallProjectile(
                    fieldSystem,
                    state,
                    distanceFx32)) {
                return TRUE;
            }
        }
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return FALSE;
    }
    if (sOverworldWildHelperPlayerBallProjectile.phase
            >= OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT
        && sOverworldWildHelperPlayerBallProjectile.phase
            <= OW_WILD_HELPER_PLAYER_BALL_PHASE_CAUGHT) {
        return OverworldWildHelper_TickPlayerBallCapture(
            fieldSystem,
            state,
            presentation,
            telemetry,
            resetSlot);
    }
    if (sOverworldWildHelperPlayerBallProjectile.phase
        == OW_WILD_HELPER_PLAYER_BALL_PHASE_FLYING) {
        if (rDown) {
            sOverworldWildHelperPlayerBallInputArmed = FALSE;
        } else {
            sOverworldWildHelperPlayerBallInputArmed = TRUE;
        }
        sOverworldWildHelperPlayerBallChargeFrames = 0;
        if (!OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(fieldSystem)
            || !OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
            || state->presentationRestorePending
            || state->mapGeneration
                != sOverworldWildHelperPlayerBallProjectile.mapGeneration) {
            OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
            return FALSE;
        }
        if (sOverworldWildHelperPlayerBallProjectile.elapsedFrames
            >= sOverworldWildHelperPlayerBallProjectile.totalFrames) {
            OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
            return FALSE;
        }
        oldX = (s32)sOverworldWildHelperPlayerBallProjectile.object->posVec[0];
        oldZ = (s32)sOverworldWildHelperPlayerBallProjectile.object->posVec[2];
        sOverworldWildHelperPlayerBallProjectile.elapsedFrames++;
        OverworldWildHelper_ApplyPlayerBallRender();
        hitSlot = OverworldWildHelper_FindPlayerBallHit(
            fieldSystem,
            state,
            oldX,
            oldZ,
            (s32)sOverworldWildHelperPlayerBallProjectile.object->posVec[0],
            (s32)sOverworldWildHelperPlayerBallProjectile.object->posVec[2]);
        if (hitSlot >= 0
            && OverworldWildHelper_StartPlayerBallImpact(
                fieldSystem,
                state,
                hitSlot,
                prepareCaptureTarget)) {
            return TRUE;
        }
        return TRUE;
    }
    if (sOverworldWildHelperPlayerBallProjectile.phase
        != OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE) {
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return FALSE;
    }
    if (!sOverworldWildHelperPlayerBallStaleCheckDone
        && OverworldWildHelper_PlayerBallObjectIdAvailable(fieldSystem)) {
        sOverworldWildHelperPlayerBallStaleCheckDone = TRUE;
    }
    if (!sOverworldWildHelperPlayerBallInputArmed) {
        if (!rDown) {
            sOverworldWildHelperPlayerBallInputArmed = TRUE;
        }
        sOverworldWildHelperPlayerBallChargeFrames = 0;
        return FALSE;
    }
    if ((pad & PAD_BUTTON_L) != 0) {
        if (rDown) {
            sOverworldWildHelperPlayerBallInputArmed = FALSE;
        }
        sOverworldWildHelperPlayerBallChargeFrames = 0;
        return FALSE;
    }
    if (rPressed) {
        sOverworldWildHelperPlayerBallChargeFrames = 0;
        return OverworldWildHelper_TryStartPlayerBallCharge(
            fieldSystem,
            state);
    }
    return FALSE;
}

static BOOL OverworldWildHelper_IsPlayerBallProjectileActive(void)
{
    return sOverworldWildHelperPlayerBallProjectile.phase
        != OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE;
}

static void OverworldWildHelper_CleanupResidentData(FieldSystem *fieldSystem)
{
    OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
    sOverworldWildHelperPlayerBallRWasDown = FALSE;
    sOverworldWildHelperPlayerBallInputArmed = FALSE;
    sOverworldWildHelperPlayerBallStaleCheckDone = FALSE;
    sOverworldWildHelperPlayerBallChargeFrames = 0;
    sys_FreeMemoryEz(sOverworldWildHelperEncounterLookupDataBlob);
    sOverworldWildHelperEncounterLookupDataBlob = NULL;
    sOverworldWildHelperEncounterLookupDataBlobSize = 0;
    sOverworldWildHelperEncounterLookupLoadAttempted = FALSE;
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

static BOOL OverworldWildHelper_IsPickupThrowMovementContextCurrent(
    OverworldWildSpawnState *state)
{
    FieldSystem *fieldSystem;
    int encounterDataId;

    if (state == NULL) {
        return FALSE;
    }
    fieldSystem = state->movementFieldSystem;
    return fieldSystem != NULL
        && fieldSystem->playerAvatar != NULL
        && OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
        && OverworldWildHelper_TryGetEncounterDataIdForMap(
            fieldSystem->location->mapId,
            &encounterDataId);
}

static BOOL OverworldWildHelper_IsValidPickupThrowTarget(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    int carrierSlot,
    int targetSlot)
{
    if (state == NULL
        || throwState == NULL
        || carrierSlot < 0
        || carrierSlot >= OW_WILD_MAX_SPAWNS
        || targetSlot < 0
        || targetSlot >= OW_WILD_MAX_SPAWNS
        || carrierSlot == targetSlot
        || !state->spawns[targetSlot].active
        || state->spawns[targetSlot].object == NULL
        || state->movementBehaviorClasses[targetSlot] == OW_WILD_BEHAVIOR_CLASS_PICKED_UP
        || state->movementQueuedBattleSlot == targetSlot
        || state->pendingSlot == targetSlot
        || throwState->targets[targetSlot] != OW_WILD_HELPER_THROW_TARGET_NONE) {
        return FALSE;
    }

    return OverworldWildHelper_IsPickupThrowMovementContextCurrent(state)
        && OverworldWildHelper_IsExactObject(
            state->movementFieldSystem,
            state,
            targetSlot);
}

static BOOL OverworldWildHelper_IsStablePickupThrowTarget(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    int carrierSlot,
    int targetSlot,
    u16 unstableMask)
{
    LocalMapObject *object;

    if (!OverworldWildHelper_IsValidPickupThrowTarget(
            state,
            throwState,
            carrierSlot,
            targetSlot)
        || state->movementSpotStates[targetSlot] == 1
        || (unstableMask & (1u << targetSlot)) != 0
        || state->movementSpawnRunActive[targetSlot]
        || state->movementStagedHopPending[targetSlot]
        || state->movementRamCrashShakeTimers[targetSlot] != 0
        || state->movementPhantomHidden[targetSlot]
        || state->movementPhantomFlickerTimers[targetSlot] != 0
        || state->movementPhantomTeleportHasTarget[targetSlot]
        || state->movementPhantomFlickerObjects[targetSlot] != NULL
        || state->movementPhantomTeleportFlickerObjects[targetSlot] != NULL
        || (state->movementInProgressMask & (1u << targetSlot)) != 0) {
        return FALSE;
    }

    object = state->spawns[targetSlot].object;
    return !MapObject_IsSingleMovementActive(object)
        && (object->flags & BIT_VANISH) == 0;
}

static BOOL OverworldWildHelper_IsReservedPickupTargetNearCarrier(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    int targetSlot)
{
    int carrierSlot;

    if (state == NULL
        || throwState == NULL
        || targetSlot < 0
        || targetSlot >= OW_WILD_MAX_SPAWNS
        || (throwState->targetMask & (1u << targetSlot)) == 0
        || state->movementBehaviorClasses[targetSlot] == OW_WILD_BEHAVIOR_CLASS_PICKED_UP) {
        return FALSE;
    }

    for (carrierSlot = 0; carrierSlot < OW_WILD_MAX_SPAWNS; carrierSlot++) {
        u8 relation = throwState->targets[carrierSlot];
        LocalMapObject *carrierObject;
        LocalMapObject *targetObject;

        if (relation == OW_WILD_HELPER_THROW_TARGET_NONE
            || (relation & OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG) != 0
            || OW_WILD_HELPER_THROW_TARGET_DECODE(relation) != targetSlot
            || !OverworldWildHelper_IsValidPickupThrowTarget(
                state,
                throwState,
                carrierSlot,
                targetSlot)
            || !OverworldWildHelper_IsExactObject(
                state->movementFieldSystem,
                state,
                carrierSlot)) {
            continue;
        }

        carrierObject = state->spawns[carrierSlot].object;
        targetObject = state->spawns[targetSlot].object;
        return OverworldWildHelper_Max(
            OverworldWildHelper_Abs(
                MapObject_GetCurrentX(carrierObject) - MapObject_GetCurrentX(targetObject)),
            OverworldWildHelper_Abs(
                MapObject_GetCurrentY(carrierObject) - MapObject_GetCurrentY(targetObject))) <= 1;
    }
    return FALSE;
}

static BOOL OverworldWildHelper_QueryPickupThrowTarget(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    int carrierSlot,
    int targetSlot,
    u8 query,
    u16 unstableMask)
{
    if (query == OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE) {
        return OverworldWildHelper_IsStablePickupThrowTarget(
            state,
            throwState,
            carrierSlot,
            targetSlot,
            unstableMask);
    }
    if (query == OW_WILD_HELPER_PICKUP_THROW_QUERY_RESERVED_NEAR) {
        return OverworldWildHelper_IsReservedPickupTargetNearCarrier(
            state,
            throwState,
            targetSlot);
    }
    return query == OW_WILD_HELPER_PICKUP_THROW_QUERY_VALID
        && OverworldWildHelper_IsValidPickupThrowTarget(
            state,
            throwState,
            carrierSlot,
            targetSlot);
}

static u16 OverworldWildHelper_ClearPickupThrowState(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    OverworldWildPresentationState *presentation,
    int slot)
{
    u16 restoreMask = 0;
    int i;

    if (state == NULL
        || throwState == NULL
        || presentation == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return 0;
    }

    throwState->targetMask &= ~(1u << slot);
    throwState->carrierMask &= ~(1u << slot);
    presentation->farSamples[slot] = 0;
    if (state->movementBehaviorClasses[slot] == OW_WILD_BEHAVIOR_CLASS_PICKED_UP) {
        restoreMask |= 1u << slot;
    }
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        u8 relation = throwState->targets[i];
        u8 target;

        if (relation == OW_WILD_HELPER_THROW_TARGET_NONE) {
            continue;
        }
        target = OW_WILD_HELPER_THROW_TARGET_DECODE(relation);
        if (target >= OW_WILD_MAX_SPAWNS) {
            throwState->targets[i] = OW_WILD_HELPER_THROW_TARGET_NONE;
            throwState->carrierMask &= ~(1u << i);
            state->movementEmoteTimers[i] = 0;
            continue;
        }
        if (i == slot || target == slot) {
            throwState->targetMask &= ~(1u << target);
            presentation->farSamples[target] = 0;
            if ((relation & OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG) != 0
                && state->movementBehaviorClasses[target]
                    == OW_WILD_BEHAVIOR_CLASS_PICKED_UP) {
                restoreMask |= 1u << target;
            }
            throwState->targets[i] = OW_WILD_HELPER_THROW_TARGET_NONE;
            throwState->carrierMask &= ~(1u << i);
            state->movementEmoteTimers[i] = 0;
        }
    }
    return restoreMask;
}

static BOOL OverworldWildHelper_TryStartPickupThrowAction(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    OverworldWildPresentationState *presentation,
    int slot,
    u16 unstableMask)
{
    int i;

    if (state == NULL
        || throwState == NULL
        || presentation == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || throwState->targets[slot] != OW_WILD_HELPER_THROW_TARGET_NONE
        || ((throwState->targetMask | throwState->carrierMask) & (1u << slot)) != 0) {
        return FALSE;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        u16 targetMask = 1u << i;

        if (OverworldWildHelper_IsStablePickupThrowTarget(
                state,
                throwState,
                slot,
                i,
                unstableMask)
            && throwState->targets[i] == OW_WILD_HELPER_THROW_TARGET_NONE
            && (throwState->targetMask & targetMask) == 0) {
            throwState->targets[slot] = OW_WILD_HELPER_THROW_TARGET_ENCODE(i);
            throwState->targetMask |= targetMask;
            throwState->carrierMask |= 1u << slot;
            presentation->farSamples[slot] = 0;
            presentation->farSamples[i] = 0;
            state->movementEmoteTimers[slot] =
                OW_WILD_HELPER_THROW_RESERVATION_DECISIONS;
            return TRUE;
        }
    }
    return FALSE;
}

static BOOL OverworldWildHelper_StartCarriedThrowTarget(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    OverworldWildPresentationState *presentation,
    int carrierSlot,
    int targetSlot)
{
    LocalMapObject *targetObject;

    if (state == NULL
        || throwState == NULL
        || presentation == NULL
        || !OverworldWildHelper_IsPickupThrowMovementContextCurrent(state)
        || !OverworldWildHelper_IsExactObject(
            state->movementFieldSystem,
            state,
            carrierSlot)
        || !OverworldWildHelper_IsExactObject(
            state->movementFieldSystem,
            state,
            targetSlot)) {
        return FALSE;
    }

    targetObject = state->spawns[targetSlot].object;
    state->movementSpotStates[targetSlot] = 0;
    state->movementEmoteTimers[targetSlot] = 0;
    state->movementActiveSteps[targetSlot] = 0;
    state->movementBehaviorClasses[targetSlot] = OW_WILD_BEHAVIOR_CLASS_PICKED_UP;
    MapObject_SetBits(targetObject, MAPOBJECTFLAG_UNK18);
    MapObject_ClearBits(targetObject, BIT_VANISH);
    throwState->targets[carrierSlot] =
        OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(targetSlot);
    throwState->targetMask |= 1u << targetSlot;
    throwState->carrierMask |= 1u << carrierSlot;
    state->movementEmoteTimers[carrierSlot] = 0;
    OverworldWildHelper_SyncCarriedThrowTarget(
        state->movementFieldSystem,
        state,
        presentation,
        carrierSlot,
        targetSlot);
    return TRUE;
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
    OverworldWildHelper_TryGetEncounterDataIdForMap,
    OverworldWildHelper_TryLoadEncounterData,
    OverworldWildHelper_TickPlayerBallProjectile,
    OverworldWildHelper_CancelPlayerBallProjectile,
    OverworldWildHelper_IsPlayerBallProjectileActive,
    OverworldWildHelper_CleanupResidentData,
    OverworldWildHelper_ClearPickupThrowState,
    OverworldWildHelper_QueryPickupThrowTarget,
    OverworldWildHelper_TryStartPickupThrowAction,
    OverworldWildHelper_StartCarriedThrowTarget,
};
