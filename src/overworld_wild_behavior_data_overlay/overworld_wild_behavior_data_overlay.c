#include "../../include/config.h"
#include "../../include/overworld_wild_behavior_data.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/overworld_wild_helper.h"
#include "../../include/map_events_internal.h"
#include "../../include/pokemon.h"
#include "../../include/pokemon_storage_system.h"
#include "../../include/overlay.h"
#include "../../include/save.h"
#include "../../include/script.h"
#include "../../include/constants/maps.h"
#include "../../include/constants/file.h"
#include "../../include/constants/generated/learnsets.h"
#include "../../include/constants/species.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

#define OW_WILD_LEGACY_ENCOUNTER_AREA_COUNT 150
#define OW_WILD_PLAYER_BALL_CAPTURE_DESTINATION_PARTY (-1)
#define OW_WILD_PLAYER_BALL_CAPTURE_DESTINATION_NONE (-2)
#define OW_WILD_PLAYER_BALL_PC_STORAGE_SAVE_BLOCK 41
#define OW_WILD_VAR_SPECIAL_LAST_TALKED 0x800D
#define OW_WILD_DIRECTION_UP 0
#define OW_WILD_DIRECTION_DOWN 1
#define OW_WILD_DIRECTION_LEFT 2
#define OW_WILD_DIRECTION_RIGHT 3
#define OW_WILD_SPAWN_METADATA_MAX_BLOB_SIZE 0x4000
#define OW_WILD_LEVELUP_LEARNSET_MEMBER_COUNT 1
#define OW_WILD_LEVELUP_LEARNSET_ROW_COUNT \
    (MAX_SPECIES_INCLUDING_FORMS + 1)
#define OW_WILD_LEVELUP_LEARNSET_ROW_SIZE (MAX_LEVELUP_MOVES * sizeof(u32))
#define OW_WILD_LEVELUP_LEARNSET_MEMBER_SIZE \
    (OW_WILD_LEVELUP_LEARNSET_ROW_COUNT * OW_WILD_LEVELUP_LEARNSET_ROW_SIZE)
#define OW_WILD_LEVELUP_LEARNSET_CACHE_INVALID 0xFFFF
#define OW_WILD_PERSONAL_ROW_COUNT (MAX_SPECIES_INCLUDING_FORMS + 1)
#define OW_WILD_PERSONAL_ROW_SIZE 44
#define OW_WILD_PERSONAL_ATTR_COUNT (PERSONAL_TM_ARRAY_4 + 1)
#define OW_WILD_PERSONAL_CACHE_INVALID 0
#define OW_WILD_PERSONAL_CACHE_FAILED ((void *)1)

typedef struct OverworldWildBehaviorDataOverlayHeader {
    OverworldWildBehaviorOverlayEntry behavior;
    OverworldWildEncounterLookupDataEntry legacyEncounterLookup;
    OverworldWildCustomJumpShadowEntry customJumpShadow;
    OverworldWildCaptureUtilitiesEntry captureUtilities;
    OverworldWildSpawnMetadataOverlayEntry spawnMetadata;
    OverworldWildLearnsetCacheOverlayEntry learnsetCache;
} OverworldWildBehaviorDataOverlayHeader;

static const u16 sOverworldWildLegacyEncounterAreaMapIds[OW_WILD_LEGACY_ENCOUNTER_AREA_COUNT];
static const u8 sOverworldWildLegacyEncounterAreaDataIds[OW_WILD_LEGACY_ENCOUNTER_AREA_COUNT];
static void *OverworldWildBehavior_CreateCustomJumpShadowEffectNoop(
    void *effectContext,
    void *object);
static void OverworldWildBehavior_ClearCustomJumpShadowEffectNoop(void);
static u8 OverworldWildBehavior_GetPlayerBallCatchValue(u8 catchRate);
static u8 OverworldWildBehavior_CalculatePlayerBallShakes(u8 catchValue);
static u32 OverworldWildBehavior_FinalizeSpawnPersonality(
    u32 personality,
    u32 trainerId,
    BOOL shiny);
static int OverworldWildBehavior_FindCapturedPokemonDestination(
    FieldSystem *fieldSystem);
static int OverworldWildBehavior_FindBattleTalkSlot(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    LocalMapObject *talkedObject,
    u16 excludedMask);
static BOOL OverworldWildBehavior_TryGetSpawnMetadata(
    u16 species,
    u8 form,
    OverworldWildSpawnMetadata *metadata);
static void OverworldWildBehavior_CleanupSpawnMetadata(void);
static u32 OverworldWildBehavior_GetSpawnSpriteId(u16 species, u8 form);
static void OverworldWildBehavior_ApplySpawnRenderParams(
    LocalMapObject *object,
    u16 species,
    u8 form,
    u32 spriteId,
    BOOL shiny);
static void OverworldWildBehavior_LoadLevelUpLearnset(
    int species,
    int form,
    u32 *levelUpLearnset);
static BOOL OverworldWildBehavior_WarmLevelUpLearnsetCache(void);
static void OverworldWildBehavior_CleanupLevelUpLearnsetCache(void);
static BOOL OverworldWildBehavior_TryResolveOverlap(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    u16 unstableMask,
    OverworldWildQueryPickupThrowTargetFunc queryTarget,
    OverworldWildStartSpawnerMovementFunc startMovement);
static u32 OverworldWildBehavior_GetPersonalParam(int species, int parameter);
static void OverworldWildBehavior_PublishPersonalDispatchers(void)
    __attribute__((section(".overworld_wild_personal_cache_dispatch"), noinline, used));
static void OverworldWildBehavior_ResetPersonalDispatchers(void)
    __attribute__((noinline));
BOOL OverworldWildBehavior_ValidateOverlay(void);
void OverworldWildBehavior_CleanupOverlay(void);

#define OW_WILD_BEHAVIOR_OVERLAY_HEADER_INITIALIZER { \
    { \
        OVERWORLD_WILD_BEHAVIOR_OVERLAY_MAGIC, \
        OVERWORLD_WILD_BEHAVIOR_OVERLAY_VERSION, \
        sizeof(OverworldWildBehaviorOverlayEntry), \
    }, \
    { \
        sOverworldWildLegacyEncounterAreaMapIds, \
        sOverworldWildLegacyEncounterAreaDataIds, \
        OW_WILD_LEGACY_ENCOUNTER_AREA_COUNT, \
    }, \
    { \
        OverworldWildBehavior_CreateCustomJumpShadowEffectNoop, \
        OverworldWildBehavior_ClearCustomJumpShadowEffectNoop, \
    }, \
    { \
        OverworldWildBehavior_GetPlayerBallCatchValue, \
        OverworldWildBehavior_CalculatePlayerBallShakes, \
        OverworldWildBehavior_FinalizeSpawnPersonality, \
        OverworldWildBehavior_FindCapturedPokemonDestination, \
        OverworldWildBehavior_FindBattleTalkSlot, \
    }, \
    { \
        OVERWORLD_WILD_SPAWN_METADATA_OVERLAY_MAGIC, \
        OVERWORLD_WILD_SPAWN_METADATA_OVERLAY_VERSION, \
        sizeof(OverworldWildSpawnMetadataOverlayEntry), \
        OverworldWildBehavior_TryGetSpawnMetadata, \
        OverworldWildBehavior_CleanupSpawnMetadata, \
        OverworldWildBehavior_GetSpawnSpriteId, \
        OverworldWildBehavior_ApplySpawnRenderParams, \
    }, \
    { \
        OVERWORLD_WILD_LEARNSET_CACHE_OVERLAY_MAGIC, \
        OVERWORLD_WILD_LEARNSET_CACHE_OVERLAY_VERSION, \
        sizeof(OverworldWildLearnsetCacheOverlayEntry), \
        OverworldWildBehavior_LoadLevelUpLearnset, \
        OverworldWildBehavior_WarmLevelUpLearnsetCache, \
    }, \
}

static const OverworldWildBehaviorDataOverlayHeader
    sOverworldWildBehaviorExpectedOverlayHeader =
        OW_WILD_BEHAVIOR_OVERLAY_HEADER_INITIALIZER;

const OverworldWildBehaviorDataOverlayHeader gOverworldWildBehaviorDataOverlayHeader
    __attribute__((section(".overworld_wild_behavior_data_entry"), used)) =
        OW_WILD_BEHAVIOR_OVERLAY_HEADER_INITIALIZER;

const OverworldWildOverlapResolverEntry gOverworldWildOverlapResolverEntry
    __attribute__((section(".overworld_wild_overlap_resolver_entry"), used)) = {
        OverworldWildBehavior_TryResolveOverlap,
    };

#define OW_WILD_PERSONAL_CACHE_OVERLAY_ENTRY_INITIALIZER { \
    OVERWORLD_WILD_PERSONAL_CACHE_OVERLAY_MAGIC, \
    OVERWORLD_WILD_PERSONAL_CACHE_OVERLAY_VERSION, \
    sizeof(OverworldWildPersonalCacheOverlayEntry), \
    OverworldWildBehavior_GetPersonalParam, \
}

const OverworldWildPersonalCacheOverlayEntry
    gOverworldWildPersonalCacheOverlayEntry
        __attribute__((section(".overworld_wild_personal_cache_entry"), used)) =
            OW_WILD_PERSONAL_CACHE_OVERLAY_ENTRY_INITIALIZER;

typedef struct OverworldWildPersonalCacheState {
    void *narc;
    u16 cachedSpeciesPlusOne;
    u16 reserved;
    u8 row[OW_WILD_PERSONAL_ROW_SIZE];
} OverworldWildPersonalCacheState;

typedef char OverworldWildBehaviorOverlayEntrySizeMustRemain8Bytes[
    sizeof(OverworldWildBehaviorOverlayEntry) == 8 ? 1 : -1];
typedef char OverworldWildBehaviorDataOverlayHeaderSizeMustRemain88Bytes[
    sizeof(OverworldWildBehaviorDataOverlayHeader) == 88 ? 1 : -1];
typedef char OverworldWildLearnsetCacheOverlayEntrySizeMustRemain16Bytes[
    sizeof(OverworldWildLearnsetCacheOverlayEntry) == 16 ? 1 : -1];
typedef char OverworldWildPersonalCacheOverlayEntrySizeMustRemain12Bytes[
    sizeof(OverworldWildPersonalCacheOverlayEntry) == 12 ? 1 : -1];
typedef char OverworldWildPersonalCacheStateSizeMustRemain52Bytes[
    sizeof(OverworldWildPersonalCacheState) == 52 ? 1 : -1];
typedef char OverworldWildPersonalRowCountMustRemain1393[
    OW_WILD_PERSONAL_ROW_COUNT == 1393 ? 1 : -1];
typedef char OverworldWildPersonalRowSizeMustRemain44[
    OW_WILD_PERSONAL_ROW_SIZE == 44 ? 1 : -1];
typedef char OverworldWildPersonalAttrCountMustRemain33[
    OW_WILD_PERSONAL_ATTR_COUNT == 33 ? 1 : -1];
typedef char OverworldWildLevelUpLearnsetRowCountMustRemain1393[
    OW_WILD_LEVELUP_LEARNSET_ROW_COUNT == 1393 ? 1 : -1];
typedef char OverworldWildLevelUpLearnsetMemberSizeMustRemain228452[
    OW_WILD_LEVELUP_LEARNSET_MEMBER_SIZE == 228452 ? 1 : -1];
typedef char OverworldWildSpawnMetadataSizeMustRemain8Bytes[
    sizeof(OverworldWildSpawnMetadata) == 8 ? 1 : -1];
typedef char OverworldWildSpawnMetadataExceptionSizeMustRemain12Bytes[
    sizeof(OverworldWildSpawnMetadataException) == 12 ? 1 : -1];
typedef char OverworldWildSpawnMetadataHeaderSizeMustRemain36Bytes[
    sizeof(OverworldWildSpawnMetadataBlobHeader) == 36 ? 1 : -1];
typedef char OverworldWildRenderModeObjectOffsetMustRemain120[
    offsetof(LocalMapObject, unk108) + 0x18 == 0x120 ? 1 : -1];

static BOOL OverworldWildBehavior_TryResolveOverlap(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    u16 unstableMask,
    OverworldWildQueryPickupThrowTargetFunc queryTarget,
    OverworldWildStartSpawnerMovementFunc startMovement)
{
    static const u8 directions[] = {
        OW_WILD_DIRECTION_UP,
        OW_WILD_DIRECTION_RIGHT,
        OW_WILD_DIRECTION_DOWN,
        OW_WILD_DIRECTION_LEFT,
    };
    u16 excludedMask;
    int i;

    if (state == NULL
        || throwState == NULL
        || queryTarget == NULL
        || startMovement == NULL
        || state->movementFieldSystem == NULL) {
        return FALSE;
    }
    excludedMask = state->captureTargetMask
        | throwState->targetMask
        | throwState->carrierMask;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        LocalMapObject *object = state->spawns[i].object;
        int objectX;
        int objectY;
        int j;
        BOOL occupied;

        if (!state->spawns[i].active
            || object == NULL
            || (excludedMask & (1u << i)) != 0
            || state->movementEmoteTimers[i] != 0
            || state->movementPhantomVisiblePause[i]
            || !queryTarget(
                state,
                throwState,
                i == 0 ? 1 : 0,
                i,
                OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE,
                unstableMask)) {
            continue;
        }
        objectX = MapObject_GetCurrentX(object);
        objectY = MapObject_GetCurrentY(object);
        occupied = i != OW_WILD_FOLLOWER_SLOT
            && state->movementFieldSystem->playerAvatar != NULL
            && objectX == GetPlayerXCoord(state->movementFieldSystem->playerAvatar)
            && objectY == GetPlayerYCoord(state->movementFieldSystem->playerAvatar);
        for (j = 0; !occupied && j < OW_WILD_MAX_SPAWNS; j++) {
            LocalMapObject *other = state->spawns[j].object;

            occupied = j != i
                && state->spawns[j].active
                && other != NULL
                && MapObject_GetCurrentX(other) == objectX
                && MapObject_GetCurrentY(other) == objectY;
        }
        if (occupied
            && startMovement(
                state,
                state->movementFieldSystem,
                i,
                directions,
                4)) {
            return TRUE;
        }
    }
    return FALSE;
}

static void *sOverworldWildSpawnMetadataBlob;
static u32 sOverworldWildSpawnMetadataBlobSize;
static BOOL sOverworldWildSpawnMetadataLoadAttempted;
static void *sOverworldWildLevelUpLearnsetsNarc;
static u32 sOverworldWildLevelUpLearnsetCache[MAX_LEVELUP_MOVES];
static u16 sOverworldWildLevelUpLearnsetCachedSpecies =
    OW_WILD_LEVELUP_LEARNSET_CACHE_INVALID;
static BOOL sOverworldWildLevelUpLearnsetOpenAttempted;
static OverworldWildPersonalCacheState sOverworldWildPersonalCache;

static u32 OverworldWildBehavior_SpawnMetadataChecksum(const u8 *blob, u32 size)
{
    u32 checksum = 0;
    u32 i;

    for (i = 0; i < size; i++) {
        if (i < 32 || i >= 36) {
            checksum += blob[i];
        }
    }
    return checksum;
}

static BOOL OverworldWildBehavior_DecodeSpawnMetadata(void)
{
    const OverworldWildSpawnMetadataBlobHeader *header =
        (const OverworldWildSpawnMetadataBlobHeader *)sOverworldWildSpawnMetadataBlob;
    const OverworldWildSpawnMetadata *base;
    const OverworldWildSpawnMetadataException *exceptions;
    u32 baseSize;
    u32 exceptionSize;
    u32 previousKey = 0;
    u32 i;

    if (header == NULL
        || sOverworldWildSpawnMetadataBlobSize < sizeof(*header)
        || header->magic != OVERWORLD_WILD_SPAWN_METADATA_MAGIC
        || header->version != OVERWORLD_WILD_SPAWN_METADATA_VERSION
        || header->headerSize != sizeof(*header)
        || header->totalSize != sOverworldWildSpawnMetadataBlobSize
        || header->baseCount != MAX_MON_NUM + 1
        || header->baseRecordSize != sizeof(OverworldWildSpawnMetadata)
        || header->exceptionRecordSize != sizeof(OverworldWildSpawnMetadataException)
        || header->formSpeciesBaseCount > header->baseCount
        || header->flags != 0
        || header->baseOffset != header->headerSize) {
        return FALSE;
    }

    baseSize = header->baseCount * sizeof(OverworldWildSpawnMetadata);
    exceptionSize = header->exceptionCount * sizeof(OverworldWildSpawnMetadataException);
    if (header->baseOffset > header->totalSize
        || baseSize > header->totalSize - header->baseOffset
        || header->exceptionsOffset != header->baseOffset + baseSize
        || header->exceptionsOffset > header->totalSize
        || exceptionSize > header->totalSize - header->exceptionsOffset
        || header->totalSize != header->exceptionsOffset + exceptionSize
        || header->checksum != OverworldWildBehavior_SpawnMetadataChecksum(
            (const u8 *)header,
            header->totalSize)) {
        return FALSE;
    }

    base = (const OverworldWildSpawnMetadata *)((const u8 *)header + header->baseOffset);
    for (i = 0; i < header->baseCount; i++) {
        if (base[i].renderModePlusOne == 0
            || base[i].renderModePlusOne > 64) {
            return FALSE;
        }
    }

    exceptions = (const OverworldWildSpawnMetadataException *)(
        (const u8 *)header + header->exceptionsOffset);
    for (i = 0; i < header->exceptionCount; i++) {
        u32 key = ((u32)exceptions[i].species << 8) | exceptions[i].form;

        if (exceptions[i].species >= header->baseCount
            || exceptions[i].form == 0
            || exceptions[i].form > OVERWORLD_WILD_SPAWN_METADATA_MAX_FORM
            || exceptions[i].reserved != 0
            || exceptions[i].metadata.renderModePlusOne == 0
            || exceptions[i].metadata.renderModePlusOne > 64
            || (i != 0 && key <= previousKey)) {
            return FALSE;
        }
        previousKey = key;
    }
    return TRUE;
}

static BOOL OverworldWildBehavior_LoadSpawnMetadata(void)
{
    void *narc;
    u32 size;

    if (sOverworldWildSpawnMetadataLoadAttempted) {
        return sOverworldWildSpawnMetadataBlob != NULL;
    }
    sOverworldWildSpawnMetadataLoadAttempted = TRUE;
    narc = NARC_ctor(ARC_CODE_ADDONS, HEAPID_WORLD);
    if (narc == NULL) {
        return FALSE;
    }
    if (NARC_GetFileCount(narc) <= CODE_ADDON_OVERWORLD_WILD_SPAWN_METADATA) {
        NARC_dtor(narc);
        return FALSE;
    }
    size = NARC_GetMemberSize(narc, CODE_ADDON_OVERWORLD_WILD_SPAWN_METADATA);
    if (size >= sizeof(OverworldWildSpawnMetadataBlobHeader)
        && size <= OW_WILD_SPAWN_METADATA_MAX_BLOB_SIZE) {
        sOverworldWildSpawnMetadataBlob = sys_AllocMemory(HEAPID_WORLD, size);
    }
    if (sOverworldWildSpawnMetadataBlob != NULL) {
        NARC_ReadWholeMember(
            narc,
            CODE_ADDON_OVERWORLD_WILD_SPAWN_METADATA,
            sOverworldWildSpawnMetadataBlob);
        sOverworldWildSpawnMetadataBlobSize = size;
    }
    NARC_dtor(narc);
    if (sOverworldWildSpawnMetadataBlob == NULL
        || !OverworldWildBehavior_DecodeSpawnMetadata()) {
        OverworldWildBehavior_CleanupSpawnMetadata();
        sOverworldWildSpawnMetadataLoadAttempted = TRUE;
        return FALSE;
    }
    return TRUE;
}

static BOOL OverworldWildBehavior_WarmLevelUpLearnsetCache(void)
{
    void *narc;

    /* Every mutable ARM9 target fails closed until this overlay authenticates. */
    gOverworldWildLevelUpLearnsetLoader =
        LoadLevelUpLearnset_HandleAlternateForm_Fallback;
    /* The helper authenticates this header immediately before calling warm. */
    /* ARC_PERSONAL remains closed until one of these dispatched calls arrives. */
    OverworldWildBehavior_PublishPersonalDispatchers();
    if (sOverworldWildLevelUpLearnsetOpenAttempted) {
        if (sOverworldWildLevelUpLearnsetsNarc != NULL) {
            gOverworldWildLevelUpLearnsetLoader =
                OverworldWildBehavior_LoadLevelUpLearnset;
            return TRUE;
        }
        return FALSE;
    }
    sOverworldWildLevelUpLearnsetOpenAttempted = TRUE;
    narc = NARC_ctor(ARC_LEVELUP_LEARNSETS, HEAPID_WORLD);
    if (narc == NULL) {
        return FALSE;
    }
    if (NARC_GetFileCount(narc) != OW_WILD_LEVELUP_LEARNSET_MEMBER_COUNT
        || NARC_GetMemberSize(narc, 0) != OW_WILD_LEVELUP_LEARNSET_MEMBER_SIZE) {
        NARC_dtor(narc);
        return FALSE;
    }
    sOverworldWildLevelUpLearnsetsNarc = narc;
    sOverworldWildLevelUpLearnsetCachedSpecies =
        OW_WILD_LEVELUP_LEARNSET_CACHE_INVALID;
    gOverworldWildLevelUpLearnsetLoader =
        OverworldWildBehavior_LoadLevelUpLearnset;
    return TRUE;
}

static BOOL OverworldWildBehavior_LoadPersonalRow(int species)
{
    if ((u32)species >= OW_WILD_PERSONAL_ROW_COUNT) {
        return FALSE;
    }
    if (sOverworldWildPersonalCache.cachedSpeciesPlusOne == species + 1) {
        return TRUE;
    }
    if (sOverworldWildPersonalCache.narc == OW_WILD_PERSONAL_CACHE_FAILED) {
        return FALSE;
    }
    if (sOverworldWildPersonalCache.narc == NULL) {
        void *narc = NARC_ctor(ARC_PERSONAL, HEAPID_WORLD);

        if (narc == NULL) {
            sOverworldWildPersonalCache.narc = OW_WILD_PERSONAL_CACHE_FAILED;
            return FALSE;
        }
        if (NARC_GetFileCount(narc) != OW_WILD_PERSONAL_ROW_COUNT) {
            NARC_dtor(narc);
            sOverworldWildPersonalCache.narc = OW_WILD_PERSONAL_CACHE_FAILED;
            return FALSE;
        }
        sOverworldWildPersonalCache.narc = narc;
    }
    if (NARC_GetMemberSize(sOverworldWildPersonalCache.narc, species)
        != OW_WILD_PERSONAL_ROW_SIZE) {
        return FALSE;
    }
    NARC_ReadWholeMember(
        sOverworldWildPersonalCache.narc,
        species,
        sOverworldWildPersonalCache.row);
    sOverworldWildPersonalCache.cachedSpeciesPlusOne = species + 1;
    return TRUE;
}

static u32 OverworldWildBehavior_GetPersonalParam(int species, int parameter)
{
    if ((u32)parameter >= OW_WILD_PERSONAL_ATTR_COUNT
        || !OverworldWildBehavior_LoadPersonalRow(species)) {
        return PokePersonalParaGet_Fallback(species, parameter);
    }
    return GetPersonalAttr(sOverworldWildPersonalCache.row, parameter);
}

static void OverworldWildBehavior_LoadLevelUpLearnset(
    int species,
    int form,
    u32 *levelUpLearnset)
{
    u32 resolvedSpecies = PokeOtherFormMonsNoGet(species, form);

    if (levelUpLearnset == NULL
        || resolvedSpecies >= OW_WILD_LEVELUP_LEARNSET_ROW_COUNT
        || sOverworldWildLevelUpLearnsetsNarc == NULL) {
        LoadLevelUpLearnset_HandleAlternateForm_Fallback(
            species,
            form,
            levelUpLearnset);
        return;
    }
    if (sOverworldWildLevelUpLearnsetCachedSpecies != resolvedSpecies) {
        NARC_ReadFromMember(
            sOverworldWildLevelUpLearnsetsNarc,
            0,
            resolvedSpecies * OW_WILD_LEVELUP_LEARNSET_ROW_SIZE,
            OW_WILD_LEVELUP_LEARNSET_ROW_SIZE,
            sOverworldWildLevelUpLearnsetCache);
        sOverworldWildLevelUpLearnsetCachedSpecies = resolvedSpecies;
    }
    memcpy(
        levelUpLearnset,
        sOverworldWildLevelUpLearnsetCache,
        OW_WILD_LEVELUP_LEARNSET_ROW_SIZE);
}

static void OverworldWildBehavior_CleanupLevelUpLearnsetCache(void)
{
    /* No resident target may point into overlay 150 during any teardown. */
    OverworldWildBehavior_ResetPersonalDispatchers();
    gOverworldWildLevelUpLearnsetLoader =
        LoadLevelUpLearnset_HandleAlternateForm_Fallback;
    if (sOverworldWildPersonalCache.narc != NULL
        && sOverworldWildPersonalCache.narc != OW_WILD_PERSONAL_CACHE_FAILED) {
        NARC_dtor(sOverworldWildPersonalCache.narc);
    }
    sOverworldWildPersonalCache.narc = NULL;
    sOverworldWildPersonalCache.cachedSpeciesPlusOne =
        OW_WILD_PERSONAL_CACHE_INVALID;
    if (sOverworldWildLevelUpLearnsetsNarc != NULL) {
        NARC_dtor(sOverworldWildLevelUpLearnsetsNarc);
    }
    sOverworldWildLevelUpLearnsetsNarc = NULL;
    sOverworldWildLevelUpLearnsetCachedSpecies =
        OW_WILD_LEVELUP_LEARNSET_CACHE_INVALID;
    sOverworldWildLevelUpLearnsetOpenAttempted = FALSE;
}

BOOL OverworldWildBehavior_ValidateOverlay(void)
    __attribute__((section(".overworld_wild_behavior_data_validate"), noinline, used));
BOOL OverworldWildBehavior_ValidateOverlay(void)
{
    const volatile u32 *actual =
        (const volatile u32 *)OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR;
    const u32 *expected =
        (const u32 *)&sOverworldWildBehaviorExpectedOverlayHeader;
    const volatile u32 *personalEntry =
        (const volatile u32 *)OVERWORLD_WILD_PERSONAL_CACHE_ENTRY_ADDR;
    u32 i;

    for (i = 0;
         i < sizeof(OverworldWildBehaviorDataOverlayHeader) / sizeof(u32);
         i++) {
        if (actual[i] != expected[i]) {
            return FALSE;
        }
    }
    return personalEntry[0] == OVERWORLD_WILD_PERSONAL_CACHE_OVERLAY_MAGIC
        && personalEntry[1]
            == ((u32)sizeof(OverworldWildPersonalCacheOverlayEntry) << 16
                | OVERWORLD_WILD_PERSONAL_CACHE_OVERLAY_VERSION)
        && personalEntry[2] == (u32)OverworldWildBehavior_GetPersonalParam;
}

static void OverworldWildBehavior_PublishPersonalDispatchers(void)
{
    gOverworldWildPersonalParamLoader = OverworldWildBehavior_GetPersonalParam;
}

static void OverworldWildBehavior_ResetPersonalDispatchers(void)
{
    gOverworldWildPersonalParamLoader = PokePersonalParaGet_Fallback;
}

void OverworldWildBehavior_CleanupOverlay(void)
    __attribute__((section(".overworld_wild_behavior_data_cleanup"), noinline, used));
void OverworldWildBehavior_CleanupOverlay(void)
{
    OverworldWildBehavior_ClearCustomJumpShadowEffectNoop();
}

static BOOL OverworldWildBehavior_TryGetSpawnMetadata(
    u16 species,
    u8 form,
    OverworldWildSpawnMetadata *metadata)
{
    const OverworldWildSpawnMetadataBlobHeader *header;
    const OverworldWildSpawnMetadata *base;
    const OverworldWildSpawnMetadataException *exceptions;
    int low;
    int high;

    if (metadata == NULL
        || species == SPECIES_NONE
        || species > MAX_MON_NUM
        || form > OVERWORLD_WILD_SPAWN_METADATA_MAX_FORM
        || !OverworldWildBehavior_LoadSpawnMetadata()) {
        return FALSE;
    }
    header = (const OverworldWildSpawnMetadataBlobHeader *)sOverworldWildSpawnMetadataBlob;
    if (form != 0 && species >= header->formSpeciesBaseCount) {
        return FALSE;
    }
    base = (const OverworldWildSpawnMetadata *)((const u8 *)header + header->baseOffset);
    exceptions = (const OverworldWildSpawnMetadataException *)(
        (const u8 *)header + header->exceptionsOffset);
    low = 0;
    high = header->exceptionCount - 1;
    while (low <= high) {
        int middle = low + (high - low) / 2;
        const OverworldWildSpawnMetadataException *candidate = &exceptions[middle];

        if (candidate->species < species
            || (candidate->species == species && candidate->form < form)) {
            low = middle + 1;
        } else if (candidate->species > species
            || (candidate->species == species && candidate->form > form)) {
            high = middle - 1;
        } else {
            *metadata = candidate->metadata;
            return TRUE;
        }
    }
    *metadata = base[species];
    return TRUE;
}

static void OverworldWildBehavior_CleanupSpawnMetadata(void)
{
    sys_FreeMemoryEz(sOverworldWildSpawnMetadataBlob);
    sOverworldWildSpawnMetadataBlob = NULL;
    sOverworldWildSpawnMetadataBlobSize = 0;
    sOverworldWildSpawnMetadataLoadAttempted = FALSE;
}

static u32 OverworldWildBehavior_GetSpawnSpriteId(u16 species, u8 form)
{
    OverworldWildSpawnMetadata metadata;

    if (OverworldWildBehavior_TryGetSpawnMetadata(species, form, &metadata)) {
        return metadata.spriteId;
    }
    return FollowingPokemon_GetSpriteID(species, form, 0);
}

static void OverworldWildBehavior_ApplySpawnRenderParams(
    LocalMapObject *object,
    u16 species,
    u8 form,
    u32 spriteId,
    BOOL shiny)
{
    OverworldWildSpawnMetadata metadata;
    u8 renderModePlusOne = 0;

    if (OverworldWildBehavior_TryGetSpawnMetadata(species, form, &metadata)) {
        object->param[2] = (object->param[2] & ~1) | (shiny ? 1 : 0);
        object->param[1] = metadata.followerParam;
        object->param[0] = species;
        renderModePlusOne = metadata.renderModePlusOne;
    } else {
        FollowPokeMapObjectSetParams(object, species, form, shiny);
    }
    /* Preserve the stock post-param shiny refresh for every presentation path. */
    if (shiny) {
        sub_02069DC8(object, TRUE);
        ChangeMapObjSprite(object, spriteId);
    }
    /* ChangeMapObjSprite may clear renderer-private state, so publish last. */
    object->unk108[0x18] = renderModePlusOne;
}

static BOOL OverworldWildBehavior_IsCurrentSpawnObject(
    FieldSystem *fieldSystem,
    const OverworldWildSpawn *spawn,
    int slot)
{
    MapObjectMan *mapObjectMan;
    u32 objectAddress;
    u32 objectsStart;
    u32 objectsEnd;

    if (fieldSystem == NULL
        || fieldSystem->location == NULL
        || !spawn->active
        || spawn->mapId != fieldSystem->location->mapId
        || spawn->object == NULL) {
        return FALSE;
    }

    mapObjectMan = (MapObjectMan *)fieldSystem->mapObjectMan;
    if (mapObjectMan == NULL || mapObjectMan->objects == NULL) {
        return FALSE;
    }
    objectAddress = (u32)spawn->object;
    objectsStart = (u32)mapObjectMan->objects;
    objectsEnd = objectsStart + mapObjectMan->object_count * sizeof(LocalMapObject);
    if (objectAddress < objectsStart || objectAddress >= objectsEnd) {
        return FALSE;
    }

    return slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && (spawn->object->flags & MAPOBJECTFLAG_ACTIVE) != 0
        && spawn->object->id == OW_WILD_OBJECT_ID_START + slot
        && spawn->object->scriptId == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT;
}

static int OverworldWildBehavior_FindTalkedObjectSlot(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    LocalMapObject *talkedObject)
{
    u16 lastTalkedObjectId;
    int slot;
    int i;

    if (fieldSystem->taskman != NULL) {
        lastTalkedObjectId = VarGet(fieldSystem, OW_WILD_VAR_SPECIAL_LAST_TALKED);
        if (lastTalkedObjectId >= OW_WILD_OBJECT_ID_START
            && lastTalkedObjectId < OW_WILD_OBJECT_ID_START + OW_WILD_MAX_SPAWNS) {
            slot = lastTalkedObjectId - OW_WILD_OBJECT_ID_START;
            if (state->spawns[slot].object != NULL
                && state->spawns[slot].object->id == lastTalkedObjectId
                && OverworldWildBehavior_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot], slot)) {
                return slot;
            }
        }
    }

    if (talkedObject == NULL) {
        return -1;
    }
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (state->spawns[i].object == talkedObject
            && OverworldWildBehavior_IsCurrentSpawnObject(fieldSystem, &state->spawns[i], i)) {
            return i;
        }
    }
    return -1;
}

static int OverworldWildBehavior_FindBattleTalkSlot(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    LocalMapObject *talkedObject,
    u16 excludedMask)
{
    MapObjectMan *mapObjectMan;
    LocalMapObject *playerObject;
    int playerX;
    int playerY;
    int targetX;
    int targetY;
    int facing;
    int previousTileSlot = -1;
    int slot;

    if (state == NULL
        || fieldSystem == NULL
        || fieldSystem != gFieldSysPtr
        || fieldSystem->location == NULL
        || fieldSystem->mapObjectMan == NULL
        || fieldSystem->playerAvatar == NULL
        || fieldSystem->playerAvatar->mapObject == NULL) {
        return -1;
    }

    mapObjectMan = (MapObjectMan *)fieldSystem->mapObjectMan;
    if (state->presentationRestorePending
        || state->mapId != fieldSystem->location->mapId
        || state->mapObjectMan != mapObjectMan
        || state->mapObjects != mapObjectMan->objects) {
        return -1;
    }

    slot = OverworldWildBehavior_FindTalkedObjectSlot(fieldSystem, state, talkedObject);
    if (slot >= 0) {
        return slot;
    }

    playerObject = fieldSystem->playerAvatar->mapObject;
    facing = playerObject->curFacing;
    if (facing > OW_WILD_DIRECTION_RIGHT) {
        return -1;
    }

    playerX = GetPlayerXCoord(fieldSystem->playerAvatar);
    playerY = GetPlayerYCoord(fieldSystem->playerAvatar);
    targetX = playerX + (facing == OW_WILD_DIRECTION_LEFT ? -1 : facing == OW_WILD_DIRECTION_RIGHT);
    targetY = playerY + (facing == OW_WILD_DIRECTION_UP ? -1 : facing == OW_WILD_DIRECTION_DOWN);

    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        LocalMapObject *spawnObject = state->spawns[slot].object;

        if (state->movementSpawnRunActive[slot]
            || (excludedMask & (1u << slot)) != 0
            || state->movementPhantomHidden[slot]
            || !state->spawns[slot].active
            || spawnObject == NULL) {
            continue;
        }
        if ((MapObject_GetCurrentX(spawnObject) == targetX
                && MapObject_GetCurrentY(spawnObject) == targetY)
            || (MapObject_GetCurrentX(spawnObject) == playerX
                && MapObject_GetCurrentY(spawnObject) == playerY)) {
            return slot;
        }
        if (previousTileSlot < 0
            && state->movementPreviousTileLocked[slot]
            && state->movementPreviousTileX[slot] == targetX
            && state->movementPreviousTileY[slot] == targetY) {
            previousTileSlot = slot;
        }
    }

    return previousTileSlot;
}

/* Only values reachable by a full-HP Poké Ball catch (catch rate / 3). */
static const u16 sOverworldWildPlayerBallShakeChance[] = {
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

static u8 OverworldWildBehavior_GetPlayerBallCatchValue(u8 catchRate)
{
    u32 catchValue = (catchRate + 2) / 3;

    if (catchValue >= NELEMS(sOverworldWildPlayerBallShakeChance)) {
        catchValue = NELEMS(sOverworldWildPlayerBallShakeChance) - 1;
    }
    return (u8)catchValue;
}

static u8 OverworldWildBehavior_CalculatePlayerBallShakes(u8 catchValue)
{
    u32 shakeChance;
    u8 shakes;

    if (catchValue >= NELEMS(sOverworldWildPlayerBallShakeChance)) {
        catchValue = NELEMS(sOverworldWildPlayerBallShakeChance) - 1;
    }
    shakeChance = sOverworldWildPlayerBallShakeChance[catchValue];
    for (shakes = 0; shakes < 4; shakes++) {
        if (gf_rand() >= shakeChance) {
            break;
        }
    }
    return shakes;
}

static u32 OverworldWildBehavior_FinalizeSpawnPersonality(
    u32 personality,
    u32 trainerId,
    BOOL shiny)
{
    if (shiny == CalcShininessByOtIdAndPersonality(trainerId, personality)) {
        return personality;
    }
    if (shiny) {
        return GenerateShinyPIDKeepSubstructuresIntact(trainerId, personality);
    }
    return personality ^ 0x10000000;
}

static int OverworldWildBehavior_FindCapturedPokemonDestination(
    FieldSystem *fieldSystem)
{
    struct Party *party;
    PCStorage *storage;
    int box;

    if (fieldSystem == NULL || fieldSystem->savedata == NULL) {
        return OW_WILD_PLAYER_BALL_CAPTURE_DESTINATION_NONE;
    }
    party = SaveData_GetPlayerPartyPtr(fieldSystem->savedata);
    if (party != NULL && party->count < party->maxPossibleCount) {
        return OW_WILD_PLAYER_BALL_CAPTURE_DESTINATION_PARTY;
    }
    storage = SaveArray_Get(
        fieldSystem->savedata,
        OW_WILD_PLAYER_BALL_PC_STORAGE_SAVE_BLOCK);
    if (storage == NULL) {
        return OW_WILD_PLAYER_BALL_CAPTURE_DESTINATION_NONE;
    }
    box = PCStorage_FindFirstBoxWithEmptySlot(storage);
    return box < NUM_PC_BOXES ? box : OW_WILD_PLAYER_BALL_CAPTURE_DESTINATION_NONE;
}

static void *OverworldWildBehavior_CreateCustomJumpShadowEffectNoop(
    void *effectContext,
    void *object)
{
    (void)effectContext;
    (void)object;
    return NULL;
}

static void OverworldWildBehavior_ClearCustomJumpShadowEffectNoop(void)
{
    OverworldWildBehavior_CleanupLevelUpLearnsetCache();
    OverworldWildBehavior_CleanupSpawnMetadata();
}

static const u16 sOverworldWildLegacyEncounterAreaMapIds[OW_WILD_LEGACY_ENCOUNTER_AREA_COUNT] = {
    MAP_T20, MAP_R29, MAP_T21, MAP_R30,
    MAP_R31, MAP_T22, MAP_D15R0102, MAP_D15R0103,
    MAP_R32, MAP_D24R0101, MAP_D24, MAP_D24R0201,
    MAP_D24R0202, MAP_D24R0203, MAP_D24R0204, MAP_D25R0101,
    MAP_D25R0102, MAP_D25R0103, MAP_R33, MAP_D26R0101,
    MAP_D26R0102, MAP_D26R0103, MAP_D36R0101, MAP_R34,
    MAP_R35, MAP_D22R0101, MAP_D22R0102, MAP_D22R0103,
    MAP_R36, MAP_R37, MAP_T27, MAP_D18R0101,
    MAP_D18R0102, MAP_D17R0102, MAP_D17R0103, MAP_D17R0104,
    MAP_D17R0105, MAP_D17R0106, MAP_D17R0107, MAP_D17R0108,
    MAP_D17R0109, MAP_R38, MAP_R39, MAP_T26,
    MAP_W40, MAP_W41, MAP_D40R0101, MAP_D40R0102,
    MAP_D40R0104, MAP_D40R0107, MAP_T24, MAP_R42,
    MAP_D38R0101, MAP_D38R0102, MAP_D38R0103, MAP_D38R0104,
    MAP_R43, MAP_T29, MAP_R44, MAP_D39R0101,
    MAP_D39R0102, MAP_D39R0103, MAP_D39R0104, MAP_T30,
    MAP_D44R0101, MAP_D44R0102, MAP_R45, MAP_R46,
    MAP_D42R0102, MAP_D42R0101, MAP_R47, MAP_D11R0101,
    MAP_D11R0102, MAP_D11R0103, MAP_D11R0104, MAP_D11R0105,
    MAP_D41R0105, MAP_D41R0107, MAP_D41R0108, MAP_D50R0101,
    MAP_D17R0112, MAP_T31, MAP_D41R0101, MAP_D41R0102,
    MAP_D41R0103, MAP_D41R0104, MAP_SAF01, MAP_SAF02,
    MAP_SAF03, MAP_SAF04, MAP_SAF05, MAP_SAF06,
    MAP_SAF07, MAP_SAF08, MAP_SAF09, MAP_SAF10,
    MAP_SAF11, MAP_SAF12, MAP_SAF13, MAP_SAF14,
    MAP_R12, MAP_W19, MAP_W20, MAP_T01,
    MAP_T02, MAP_T04, MAP_T06, MAP_T07,
    MAP_T08, MAP_T09, MAP_R48, MAP_R26,
    MAP_R27, MAP_R28, MAP_D02R0101, MAP_D02R0102,
    MAP_D05R0101, MAP_D05R0102, MAP_D43R0101, MAP_R01,
    MAP_R02, MAP_R03, MAP_R04, MAP_R05,
    MAP_R06, MAP_R07, MAP_R08, MAP_R09,
    MAP_R10, MAP_R11, MAP_R13, MAP_R14,
    MAP_R15, MAP_R16, MAP_R17, MAP_R18,
    MAP_W21, MAP_R22, MAP_R24, MAP_R25,
    MAP_D45R0101, MAP_D45R0102, MAP_D01R0101, MAP_D43R0102,
    MAP_D43R0103, MAP_R02R0101, MAP_D46R0101, MAP_D03R0101,
    MAP_D03R0102, MAP_D03R0103,
};

static const u8 sOverworldWildLegacyEncounterAreaDataIds[OW_WILD_LEGACY_ENCOUNTER_AREA_COUNT] = {
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 11, 12, 13, 14,
    15, 16, 17, 18, 18, 19, 20, 21, 22, 23, 24, 24, 25, 26, 27, 28,
    29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
    46, 48, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65,
    66, 66, 67, 68, 69, 70, 71, 74, 75, 76, 77, 78, 79, 80, 81, 83,
    84, 85, 86, 87, 87, 88, 91, 91, 91, 91, 91, 91, 91, 91, 91, 91,
    91, 91, 91, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103,
    104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117,
    118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131,
    132, 132, 133, 134, 135, 136, 137, 139, 140, 141,
};

#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS
