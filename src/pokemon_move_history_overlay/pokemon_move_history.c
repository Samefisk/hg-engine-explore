#include "../../include/constants/moves.h"
#include "../../include/constants/save.h"
#include "../../include/pokemon_move_history.h"

#define MOVE_HISTORY_MAGIC 0x4D484953 // "MHIS"
#define MOVE_HISTORY_VERSION 1
#define MOVE_HISTORY_FIRST_SECTOR 59
#define MOVE_HISTORY_SECTOR_COUNT 5
#define MOVE_HISTORY_MIRROR_SECTOR_DELTA 64
#define MOVE_HISTORY_IMAGE_SIZE \
    (MOVE_HISTORY_SECTOR_COUNT * SAVE_SECTOR_SIZE)
#define MOVE_HISTORY_FOOTER_MAGIC 0x4D48464F // "MHFO"
#define MOVE_HISTORY_RECORD_CAPACITY 319
#define MOVE_HISTORY_RECORD_OCCUPIED (1 << 0)
#define MOVE_HISTORY_NO_MIRROR 0xFF
#define MOVE_HISTORY_OFFSETOF(type, member) __builtin_offsetof(type, member)
#define MOVE_HISTORY_PHYSICAL_SECTOR_COUNT 128

extern void *PokemonMoveHistory_OverlayMemcpy(
    void *destination,
    const void *source,
    u32 size);

struct PokemonMoveHistoryHeader {
    u32 magic;
    u16 version;
    u16 headerSize;
    u32 imageSize;
    u16 recordCapacity;
    u16 recordCount;
    u16 movesPerRecord;
    u16 recordSize;
    u32 nextAccessSequence;
    u32 ownerTrainerId;
    u32 reserved;
};

struct PokemonMoveHistoryRecord {
    u32 personality;
    u32 otId;
    u32 lastTouched;
    u16 speciesSnapshot;
    u8 moveCount;
    u8 flags;
    u16 moves[POKEMON_MOVE_HISTORY_MAX_MOVES];
};

struct PokemonMoveHistoryFooter {
    u32 magic;
    u32 mainSaveCounter;
    u32 payloadSize;
    u32 payloadCrc;
    u32 reserved;
    u16 version;
    u16 footerSize;
    u16 mirror;
    u16 reserved2;
    u32 footerCrc;
};

struct PokemonMoveHistoryStore {
    struct PokemonMoveHistoryHeader header;
    struct PokemonMoveHistoryRecord records[MOVE_HISTORY_RECORD_CAPACITY];
    struct PokemonMoveHistoryFooter footer;
};

typedef char MoveHistoryImageSizeAssert[
    sizeof(struct PokemonMoveHistoryStore) == MOVE_HISTORY_IMAGE_SIZE ? 1 : -1];
typedef char MoveHistoryHeaderSizeAssert[
    sizeof(struct PokemonMoveHistoryHeader) == 0x20 ? 1 : -1];
typedef char MoveHistoryRecordSizeAssert[
    sizeof(struct PokemonMoveHistoryRecord) == 0x40 ? 1 : -1];
typedef char MoveHistoryFooterSizeAssert[
    sizeof(struct PokemonMoveHistoryFooter) == 0x20 ? 1 : -1];
typedef char MoveHistoryFooterOffsetAssert[
    MOVE_HISTORY_OFFSETOF(struct PokemonMoveHistoryStore, footer) == 0x4FE0
        ? 1 : -1];
typedef char MoveHistoryPrimarySaveExtentAssert[
    SAVE_PAGE_MAX == 47 ? 1 : -1];
typedef char MoveHistoryFirstSectorAssert[
    MOVE_HISTORY_FIRST_SECTOR == 59 ? 1 : -1];
typedef char MoveHistorySectorRangeAssert[
    MOVE_HISTORY_FIRST_SECTOR + MOVE_HISTORY_SECTOR_COUNT <= 64 ? 1 : -1];
typedef char MoveHistoryMirrorRangeAssert[
    MOVE_HISTORY_FIRST_SECTOR + MOVE_HISTORY_MIRROR_SECTOR_DELTA
        + MOVE_HISTORY_SECTOR_COUNT <= MOVE_HISTORY_PHYSICAL_SECTOR_COUNT
        ? 1 : -1];
typedef char MoveHistorySectorImageSizeAssert[
    MOVE_HISTORY_IMAGE_SIZE == 5 * 0x1000 ? 1 : -1];
typedef char MoveHistorySaveDataSizeAssert[
    sizeof(SaveData) == 0x2F320 ? 1 : -1];
typedef char MoveHistoryPointerOffsetAssert[
    MOVE_HISTORY_OFFSETOF(SaveData, pokemonMoveHistory) == 0x2F30C
        ? 1 : -1];
typedef char MoveHistoryDirtyOffsetAssert[
    MOVE_HISTORY_OFFSETOF(SaveData, pokemonMoveHistoryDirty) == 0x2F310
        ? 1 : -1];
typedef char MoveHistoryRevisionOffsetAssert[
    MOVE_HISTORY_OFFSETOF(SaveData, pokemonMoveHistoryRevision) == 0x2F314
        ? 1 : -1];
typedef char MoveHistoryStagedRevisionOffsetAssert[
    MOVE_HISTORY_OFFSETOF(SaveData, pokemonMoveHistoryStagedRevision) == 0x2F318
        ? 1 : -1];
typedef char MoveHistoryStagedCounterOffsetAssert[
    MOVE_HISTORY_OFFSETOF(SaveData, pokemonMoveHistoryStagedSaveCounter)
        == 0x2F31C ? 1 : -1];
typedef char MoveHistorySaveSlotSpecsOffsetAssert[
    MOVE_HISTORY_OFFSETOF(SaveData, saveSlotSpecs) == OFFSET_saveSlotSpecs
        ? 1 : -1];
typedef char MoveHistoryLastGoodSaveSlotOffsetAssert[
    MOVE_HISTORY_OFFSETOF(SaveData, lastGoodSaveSlot)
        == OFFSET_lastGoodSaveSlot ? 1 : -1];
typedef char MoveHistoryLastGoodSaveNoOffsetAssert[
    MOVE_HISTORY_OFFSETOF(SaveData, lastGoodSaveNo) == OFFSET_lastGoodSaveNo
        ? 1 : -1];
typedef char MoveHistorySectorCleanFlagOffsetAssert[
    MOVE_HISTORY_OFFSETOF(SaveData, sectorCleanFlag) == OFFSET_sectorCleanFlag
        ? 1 : -1];
typedef char MoveHistoryLastGoodSectorOffsetAssert[
    MOVE_HISTORY_OFFSETOF(SaveData, lastGoodSector) == OFFSET_lastGoodSector
        ? 1 : -1];

static u32 PokemonMoveHistory_GetMirrorOffset(u32 mirror)
{
    return (MOVE_HISTORY_FIRST_SECTOR
        + mirror * MOVE_HISTORY_MIRROR_SECTOR_DELTA) * SAVE_SECTOR_SIZE;
}

static int PokemonMoveHistory_CompareCounters(u32 first, u32 second)
{
    u32 difference;

    /*
     * RFC 1982-style serial arithmetic. Every pair of persisted generations
     * compared here must be less than 2^31 saves apart; the exact half-range
     * case is deliberately outside that invariant.
     */
    difference = first - second;
    if (difference == 0) {
        return 0;
    }
    if (difference < 0x80000000) {
        return 1;
    }
    return -1;
}

static u32 PokemonMoveHistory_CalcCrc32(const void *data, u32 size)
{
    const u8 *bytes = data;
    u32 crc = 0xFFFFFFFF;
    u32 i;

    while (size-- != 0) {
        crc ^= *bytes++;
        for (i = 0; i < 8; i++) {
            crc = (crc >> 1) ^ (0xEDB88320 & -(crc & 1));
        }
    }
    return ~crc;
}

static u32 PokemonMoveHistory_GetOwnerTrainerId(SaveData *saveData)
{
    struct PlayerProfile *profile;

    profile = Sav2_PlayerData_GetProfileAddr(saveData);
    if (profile == NULL) {
        return 0;
    }
    return profile->id;
}

static void PokemonMoveHistory_InitializeStore(SaveData *saveData)
{
    struct PokemonMoveHistoryStore *store;

    store = saveData->pokemonMoveHistory;
    if (store == NULL) {
        return;
    }

    MI_CpuClearFast(store, sizeof(*store));
    store->header.magic = MOVE_HISTORY_MAGIC;
    store->header.version = MOVE_HISTORY_VERSION;
    store->header.headerSize = sizeof(store->header);
    store->header.imageSize = sizeof(*store);
    store->header.recordCapacity = MOVE_HISTORY_RECORD_CAPACITY;
    store->header.movesPerRecord = POKEMON_MOVE_HISTORY_MAX_MOVES;
    store->header.recordSize = sizeof(struct PokemonMoveHistoryRecord);
    store->header.ownerTrainerId =
        PokemonMoveHistory_GetOwnerTrainerId(saveData);

    saveData->pokemonMoveHistoryDirty = TRUE;
    saveData->pokemonMoveHistoryActiveMirror = MOVE_HISTORY_NO_MIRROR;
    saveData->pokemonMoveHistorySaveReady = TRUE;
    saveData->pokemonMoveHistoryStagedMirror = MOVE_HISTORY_NO_MIRROR;
    saveData->pokemonMoveHistoryStagedRevision = 0;
    saveData->pokemonMoveHistoryStagedSaveCounter = 0;
    saveData->pokemonMoveHistoryRevision++;
}

static BOOL PokemonMoveHistory_AllocateStore(SaveData *saveData)
{
    if (saveData->pokemonMoveHistory != NULL) {
        return TRUE;
    }

    saveData->pokemonMoveHistory = sys_AllocMemory(
        3,
        sizeof(struct PokemonMoveHistoryStore));
    if (saveData->pokemonMoveHistory == NULL) {
        /*
         * History is ancillary. Keep it pending for a later save attempt,
         * but never make this allocation failure fatal to the primary save.
         */
        saveData->pokemonMoveHistoryDirty = TRUE;
        saveData->pokemonMoveHistorySaveReady = FALSE;
        return FALSE;
    }
    return TRUE;
}

static BOOL PokemonMoveHistory_ValidateStore(
    SaveData *saveData,
    struct PokemonMoveHistoryStore *store,
    u32 mirror)
{
    struct PokemonMoveHistoryHeader *header;
    struct PokemonMoveHistoryFooter *footer;
    u32 i;
    u32 occupiedCount;

    header = &store->header;
    footer = &store->footer;
    if (header->magic != MOVE_HISTORY_MAGIC
        || header->version != MOVE_HISTORY_VERSION
        || header->headerSize != sizeof(*header)
        || header->imageSize != sizeof(*store)
        || header->recordCapacity != MOVE_HISTORY_RECORD_CAPACITY
        || header->movesPerRecord != POKEMON_MOVE_HISTORY_MAX_MOVES
        || header->recordSize != sizeof(struct PokemonMoveHistoryRecord)
        || header->ownerTrainerId
            != PokemonMoveHistory_GetOwnerTrainerId(saveData)
        || footer->magic != MOVE_HISTORY_FOOTER_MAGIC
        || footer->version != MOVE_HISTORY_VERSION
        || footer->footerSize != sizeof(*footer)
        || footer->payloadSize
            != MOVE_HISTORY_OFFSETOF(
                struct PokemonMoveHistoryStore,
                footer)
        || footer->mirror != mirror) {
        return FALSE;
    }

    if (footer->footerCrc
            != PokemonMoveHistory_CalcCrc32(footer,
                MOVE_HISTORY_OFFSETOF(
                    struct PokemonMoveHistoryFooter,
                    footerCrc))
        || footer->payloadCrc
            != PokemonMoveHistory_CalcCrc32(store,
                MOVE_HISTORY_OFFSETOF(
                    struct PokemonMoveHistoryStore,
                    footer))) {
        return FALSE;
    }

    occupiedCount = 0;
    for (i = 0; i < MOVE_HISTORY_RECORD_CAPACITY; i++) {
        struct PokemonMoveHistoryRecord *record = &store->records[i];
        u32 j;

        if (record->flags == 0) {
            continue;
        }
        if (record->flags != MOVE_HISTORY_RECORD_OCCUPIED
            || record->moveCount > POKEMON_MOVE_HISTORY_MAX_MOVES) {
            return FALSE;
        }
        for (j = 0; j < record->moveCount; j++) {
            if (record->moves[j] == MOVE_NONE
                || record->moves[j] >= NUM_OF_MOVES) {
                return FALSE;
            }
        }
        occupiedCount++;
    }

    return occupiedCount == header->recordCount;
}

void PokemonMoveHistory_InitImpl(SaveData *saveData)
{
    saveData->pokemonMoveHistory = NULL;
    saveData->pokemonMoveHistoryRevision = 0;
    saveData->pokemonMoveHistoryStagedRevision = 0;
    saveData->pokemonMoveHistoryStagedSaveCounter = 0;
    saveData->pokemonMoveHistoryActiveMirror = MOVE_HISTORY_NO_MIRROR;
    saveData->pokemonMoveHistoryStagedMirror = MOVE_HISTORY_NO_MIRROR;
    saveData->pokemonMoveHistorySaveReady = TRUE;
    saveData->pokemonMoveHistoryDirty = FALSE;

    if (PokemonMoveHistory_AllocateStore(saveData)) {
        PokemonMoveHistory_InitializeStore(saveData);
    }
}

void PokemonMoveHistory_ResetImpl(SaveData *saveData)
{
    if (PokemonMoveHistory_AllocateStore(saveData)) {
        PokemonMoveHistory_InitializeStore(saveData);
    }
}

static void PokemonMoveHistory_LoadForCounter(
    SaveData *saveData,
    u32 eligibleSaveCounter)
{
    struct PokemonMoveHistoryStore *store;
    u32 counter[2];
    u32 payloadCrc[2];
    BOOL valid[2];
    u32 selectedMirror;
    u32 i;

    if (!PokemonMoveHistory_AllocateStore(saveData)) {
        return;
    }
    store = saveData->pokemonMoveHistory;

    for (i = 0; i < 2; i++) {
        FlashLoadChunk(
            PokemonMoveHistory_GetMirrorOffset(i),
            store,
            sizeof(*store));
        valid[i] = PokemonMoveHistory_ValidateStore(saveData, store, i);
        counter[i] = store->footer.mainSaveCounter;
        payloadCrc[i] = store->footer.payloadCrc;
        if (valid[i]
            && PokemonMoveHistory_CompareCounters(
                    counter[i],
                    eligibleSaveCounter) > 0) {
            valid[i] = FALSE;
        }
    }

    if (!valid[0] && !valid[1]) {
        PokemonMoveHistory_InitializeStore(saveData);
        return;
    }

    if (valid[0] && valid[1]) {
        if (PokemonMoveHistory_CompareCounters(counter[1], counter[0]) > 0) {
            selectedMirror = 1;
        } else {
            selectedMirror = 0;
        }
    } else {
        selectedMirror = valid[1] ? 1 : 0;
    }

    FlashLoadChunk(
        PokemonMoveHistory_GetMirrorOffset(selectedMirror),
        store,
        sizeof(*store));
    if (!PokemonMoveHistory_ValidateStore(
            saveData,
            store,
            selectedMirror)) {
        PokemonMoveHistory_InitializeStore(saveData);
        return;
    }

    saveData->pokemonMoveHistoryActiveMirror = selectedMirror;
    saveData->pokemonMoveHistoryStagedMirror = MOVE_HISTORY_NO_MIRROR;
    saveData->pokemonMoveHistoryStagedRevision = 0;
    saveData->pokemonMoveHistoryStagedSaveCounter = 0;
    saveData->pokemonMoveHistorySaveReady = TRUE;
    saveData->pokemonMoveHistoryDirty =
        !valid[selectedMirror ^ 1]
        || (valid[0] && valid[1] && counter[0] == counter[1]
            && payloadCrc[0] != payloadCrc[1]);
    if (saveData->pokemonMoveHistoryDirty) {
        saveData->pokemonMoveHistoryRevision++;
    }
}

void PokemonMoveHistory_LoadImpl(SaveData *saveData)
{
    PokemonMoveHistory_LoadForCounter(
        saveData,
        saveData->saveCounter);
}

static struct PokemonMoveHistoryRecord *PokemonMoveHistory_FindRecord(
    struct PokemonMoveHistoryStore *store,
    u32 personality,
    u32 otId)
{
    u32 i;

    for (i = 0; i < MOVE_HISTORY_RECORD_CAPACITY; i++) {
        struct PokemonMoveHistoryRecord *record = &store->records[i];

        if ((record->flags & MOVE_HISTORY_RECORD_OCCUPIED)
            && record->personality == personality
            && record->otId == otId) {
            return record;
        }
    }
    return NULL;
}

static struct PokemonMoveHistoryRecord *PokemonMoveHistory_AllocateRecord(
    SaveData *saveData,
    u32 personality,
    u32 otId,
    u16 species)
{
    struct PokemonMoveHistoryStore *store;
    struct PokemonMoveHistoryRecord *record;
    u32 oldestAge;
    u32 i;

    store = saveData->pokemonMoveHistory;
    record = NULL;
    oldestAge = 0;
    for (i = 0; i < MOVE_HISTORY_RECORD_CAPACITY; i++) {
        struct PokemonMoveHistoryRecord *candidate = &store->records[i];

        if (!(candidate->flags & MOVE_HISTORY_RECORD_OCCUPIED)) {
            record = candidate;
            store->header.recordCount++;
            break;
        }
        if (record == NULL
            || store->header.nextAccessSequence - candidate->lastTouched
                > oldestAge) {
            record = candidate;
            oldestAge =
                store->header.nextAccessSequence - candidate->lastTouched;
        }
    }

    if (record == NULL) {
        return NULL;
    }
    MI_CpuClearFast(record, sizeof(*record));
    record->personality = personality;
    record->otId = otId;
    record->speciesSnapshot = species;
    record->flags = MOVE_HISTORY_RECORD_OCCUPIED;
    record->lastTouched = ++store->header.nextAccessSequence;
    saveData->pokemonMoveHistoryDirty = TRUE;
    saveData->pokemonMoveHistoryRevision++;
    return record;
}

static BOOL PokemonMoveHistory_IsCurrentMove(
    const PokemonMoveHistorySnapshot *snapshot,
    u16 move)
{
    u32 i;

    for (i = 0; i < 4; i++) {
        if (snapshot->moves[i] == move) {
            return TRUE;
        }
    }
    return FALSE;
}

static BOOL PokemonMoveHistory_IsRecordableMove(u16 move)
{
    return move != MOVE_NONE
        && move < NUM_OF_MOVES
        && !IsMoveUnimplemented(move);
}

static BOOL PokemonMoveHistory_AppendMove(
    SaveData *saveData,
    const PokemonMoveHistorySnapshot *snapshot,
    struct PokemonMoveHistoryRecord *record,
    u16 move)
{
    struct PokemonMoveHistoryStore *store;
    u32 removeIndex;
    u32 i;

    if (!PokemonMoveHistory_IsRecordableMove(move)) {
        return FALSE;
    }
    for (i = 0; i < record->moveCount; i++) {
        if (record->moves[i] == move) {
            return FALSE;
        }
    }

    if (record->moveCount == POKEMON_MOVE_HISTORY_MAX_MOVES) {
        removeIndex = 0;
        for (i = 0; i < record->moveCount; i++) {
            if (!PokemonMoveHistory_IsCurrentMove(
                    snapshot,
                    record->moves[i])) {
                removeIndex = i;
                break;
            }
        }
        for (i = removeIndex; i + 1 < record->moveCount; i++) {
            u16 nextMove = record->moves[i + 1];

            PokemonMoveHistory_OverlayMemcpy(
                &record->moves[i],
                &nextMove,
                sizeof(nextMove));
        }
        record->moveCount--;
    }

    store = saveData->pokemonMoveHistory;
    record->moves[record->moveCount++] = move;
    record->speciesSnapshot = snapshot->species;
    record->lastTouched = ++store->header.nextAccessSequence;
    saveData->pokemonMoveHistoryDirty = TRUE;
    saveData->pokemonMoveHistoryRevision++;
    return TRUE;
}

BOOL PokemonMoveHistory_CaptureSnapshotImpl(
    struct BoxPokemon *pokemon,
    PokemonMoveHistorySnapshot *snapshot)
{
    u32 i;

    if (snapshot == NULL
        || !PokemonMoveHistoryTask6_IsCanonical(pokemon)) {
        return FALSE;
    }

    snapshot->personality =
        GetBoxMonData(pokemon, MON_DATA_PERSONALITY, NULL);
    snapshot->otId = GetBoxMonData(pokemon, MON_DATA_OTID, NULL);
    snapshot->species =
        (u16)GetBoxMonData(pokemon, MON_DATA_SPECIES, NULL);
    for (i = 0; i < 4; i++) {
        snapshot->moves[i] =
            (u16)GetBoxMonData(pokemon, MON_DATA_MOVE1 + i, NULL);
    }
    return TRUE;
}

/*
 * The task-6 canonical owner gate compiles 0x10 bytes smaller than the
 * task1-5 checksum/species guard. Preserve every following sealed resident
 * address while keeping the stronger fail-closed implementation above.
 */
void __attribute__((naked, used))
PokemonMoveHistoryTask6_CaptureSnapshotLayoutPad(void)
{
    __asm__(
        ".space 0x0e\n"
        "bx lr\n");
}

static struct PokemonMoveHistoryRecord *PokemonMoveHistory_ObserveSnapshot(
    SaveData *saveData,
    const PokemonMoveHistorySnapshot *snapshot)
{
    struct PokemonMoveHistoryStore *store;
    struct PokemonMoveHistoryRecord *record;
    u32 i;

    if (saveData == NULL || snapshot == NULL
        || saveData->pokemonMoveHistory == NULL
        || snapshot->species == 0) {
        return NULL;
    }

    store = saveData->pokemonMoveHistory;
    record = PokemonMoveHistory_FindRecord(
        store,
        snapshot->personality,
        snapshot->otId);
    if (record == NULL) {
        record = PokemonMoveHistory_AllocateRecord(
            saveData,
            snapshot->personality,
            snapshot->otId,
            snapshot->species);
        if (record == NULL) {
            return NULL;
        }
    }

    for (i = 0; i < 4; i++) {
        PokemonMoveHistory_AppendMove(
            saveData,
            snapshot,
            record,
            snapshot->moves[i]);
    }
    return record;
}

BOOL PokemonMoveHistory_SeedImpl(
    SaveData *saveData,
    struct BoxPokemon *pokemon)
{
    PokemonMoveHistorySnapshot snapshot;

    if (!PokemonMoveHistory_CaptureSnapshotImpl(pokemon, &snapshot)) {
        return FALSE;
    }
    return PokemonMoveHistory_ObserveSnapshot(saveData, &snapshot) != NULL;
}

BOOL PokemonMoveHistory_RecordMoveImpl(
    SaveData *saveData,
    struct BoxPokemon *pokemon,
    u16 move)
{
    PokemonMoveHistorySnapshot snapshot;
    struct PokemonMoveHistoryRecord *record;

    if (!PokemonMoveHistory_IsRecordableMove(move)) {
        return FALSE;
    }
    if (!PokemonMoveHistory_CaptureSnapshotImpl(pokemon, &snapshot)) {
        return FALSE;
    }
    record = PokemonMoveHistory_ObserveSnapshot(saveData, &snapshot);
    if (record == NULL) {
        return FALSE;
    }
    PokemonMoveHistory_AppendMove(
        saveData,
        &snapshot,
        record,
        move);
    return TRUE;
}

BOOL PokemonMoveHistory_RecordSnapshotImpl(
    SaveData *saveData,
    const PokemonMoveHistorySnapshot *snapshot)
{
    return PokemonMoveHistory_ObserveSnapshot(saveData, snapshot) != NULL;
}

extern void LONG_CALL MonDeleteMoveSlot_Original(
    struct PartyPokemon *pokemon,
    u32 slot);

BOOL PokemonMoveHistory_ReplaceMoveImpl(
    struct BoxPokemon *pokemon,
    u16 move,
    u32 slot)
{
    PokemonMoveHistorySnapshot before;
    struct PokemonMoveHistoryRecord *record;
    SaveData *saveData;
    u8 ppUp;
    u8 pp;

    if (pokemon == NULL
        || slot >= 4
        || !PokemonMoveHistory_IsRecordableMove(move)) {
        return FALSE;
    }

    if ((u16)GetBoxMonData(
            pokemon,
            MON_DATA_MOVE1 + slot,
            NULL) == move) {
        return FALSE;
    }
    if (!PokemonMoveHistory_CaptureSnapshotImpl(pokemon, &before)) {
        return FALSE;
    }

    saveData = SaveBlock2_get();
    /*
     * This API is called only at committed mutation points. Preserve the
     * displaced move ordering before touching encrypted BoxPokemon data.
     */
    record = PokemonMoveHistory_ObserveSnapshot(saveData, &before);

    SetBoxMonData(pokemon, MON_DATA_MOVE1 + slot, &move);
    ppUp = 0;
    SetBoxMonData(pokemon, MON_DATA_MOVE1PPUP + slot, &ppUp);
    pp = (u8)GetMoveMaxPP(move, 0);
    SetBoxMonData(pokemon, MON_DATA_MOVE1PP + slot, &pp);

    if (GetBoxMonData(pokemon, MON_DATA_MOVE1 + slot, NULL) != move) {
        return FALSE;
    }
    if (record != NULL) {
        before.moves[slot] = move;
        PokemonMoveHistory_AppendMove(
            saveData,
            &before,
            record,
            move);
    }
    return TRUE;
}

void PokemonMoveHistory_DeleteMoveSlotImpl(
    struct PartyPokemon *pokemon,
    u32 slot)
{
    if (pokemon == NULL || slot >= 4) {
        return;
    }
    PokemonMoveHistory_SeedImpl(
        SaveBlock2_get(),
        &pokemon->box);
    MonDeleteMoveSlot_Original(pokemon, slot);
}

static u32 PokemonMoveHistory_QueryRecord(
    SaveData *saveData,
    struct BoxPokemon *pokemon,
    u16 *movesOut,
    u32 movesOutCapacity,
    BOOL observe)
{
    PokemonMoveHistorySnapshot snapshot;
    struct PokemonMoveHistoryRecord *record;
    u32 copyCount;

    if (!PokemonMoveHistory_CaptureSnapshotImpl(pokemon, &snapshot)) {
        return 0;
    }
    if (observe) {
        record = PokemonMoveHistory_ObserveSnapshot(saveData, &snapshot);
    } else if (saveData == NULL || saveData->pokemonMoveHistory == NULL) {
        record = NULL;
    } else {
        record = PokemonMoveHistory_FindRecord(
            saveData->pokemonMoveHistory,
            snapshot.personality,
            snapshot.otId);
    }
    if (record == NULL) {
        return 0;
    }

    copyCount = record->moveCount;
    if (copyCount > movesOutCapacity) {
        copyCount = movesOutCapacity;
    }
    if (movesOut != NULL && copyCount != 0) {
        PokemonMoveHistory_OverlayMemcpy(
            movesOut,
            record->moves,
            copyCount * sizeof(u16));
    }
    return record->moveCount;
}

u32 __attribute__((section(".pokemon_move_history_short_branch_targets")))
PokemonMoveHistory_QueryImpl(
    SaveData *saveData,
    struct BoxPokemon *pokemon,
    u16 *movesOut,
    u32 movesOutCapacity)
{
    return PokemonMoveHistory_QueryRecord(
        saveData,
        pokemon,
        movesOut,
        movesOutCapacity,
        TRUE);
}

u32 PokemonMoveHistory_QueryReadOnlyImpl(
    SaveData *saveData,
    struct BoxPokemon *pokemon,
    u16 *movesOut,
    u32 movesOutCapacity)
{
    return PokemonMoveHistory_QueryRecord(
        saveData,
        pokemon,
        movesOut,
        movesOutCapacity,
        FALSE);
}

BOOL PokemonMoveHistory_CommitIfDirtyImpl(SaveData *saveData)
{
    struct PokemonMoveHistoryStore *store;
    struct PokemonMoveHistoryFooter invalidFooter;
    struct PokemonMoveHistoryFooter *footer;
    u32 targetMirror;
    u32 targetOffset;
    u32 ownerTrainerId;

    saveData->pokemonMoveHistorySaveReady = TRUE;
    saveData->pokemonMoveHistoryStagedMirror = MOVE_HISTORY_NO_MIRROR;
    saveData->pokemonMoveHistoryStagedRevision = 0;
    saveData->pokemonMoveHistoryStagedSaveCounter = 0;
    store = saveData->pokemonMoveHistory;
    if (store != NULL) {
        ownerTrainerId = PokemonMoveHistory_GetOwnerTrainerId(saveData);
        if (store->header.ownerTrainerId != ownerTrainerId) {
            if (store->header.ownerTrainerId != 0 && ownerTrainerId != 0) {
                PokemonMoveHistory_InitializeStore(saveData);
            } else {
                store->header.ownerTrainerId = ownerTrainerId;
                saveData->pokemonMoveHistoryDirty = TRUE;
                saveData->pokemonMoveHistoryRevision++;
            }
        }
    }
    if (store == NULL) {
        saveData->pokemonMoveHistoryDirty = TRUE;
        saveData->pokemonMoveHistorySaveReady = FALSE;
        return FALSE;
    }
    if (!saveData->pokemonMoveHistoryDirty) {
        return TRUE;
    }

    targetMirror =
        saveData->pokemonMoveHistoryActiveMirror == MOVE_HISTORY_NO_MIRROR
        ? (saveData->lastGoodSector == 0)
        : (saveData->pokemonMoveHistoryActiveMirror ^ 1);
    targetOffset = PokemonMoveHistory_GetMirrorOffset(targetMirror);

    footer = &store->footer;
    MI_CpuClearFast(footer, sizeof(*footer));
    footer->magic = MOVE_HISTORY_FOOTER_MAGIC;
    footer->version = MOVE_HISTORY_VERSION;
    footer->footerSize = sizeof(*footer);
    footer->mainSaveCounter = saveData->saveCounter;
    footer->payloadSize = MOVE_HISTORY_OFFSETOF(
        struct PokemonMoveHistoryStore,
        footer);
    footer->mirror = targetMirror;
    footer->payloadCrc =
        PokemonMoveHistory_CalcCrc32(store,
            MOVE_HISTORY_OFFSETOF(
                struct PokemonMoveHistoryStore,
                footer));
    footer->footerCrc =
        PokemonMoveHistory_CalcCrc32(footer,
            MOVE_HISTORY_OFFSETOF(
                struct PokemonMoveHistoryFooter,
                footerCrc));

    MI_CpuFillFast(&invalidFooter, -1, sizeof(invalidFooter));
    if (FlashWriteChunk(
            targetOffset + MOVE_HISTORY_OFFSETOF(
                struct PokemonMoveHistoryStore,
                footer),
            &invalidFooter,
            sizeof(invalidFooter)) != TRUE
        || FlashWriteChunk(
            targetOffset,
            store,
            MOVE_HISTORY_OFFSETOF(
                struct PokemonMoveHistoryStore,
                footer)) != TRUE
        || FlashWriteChunk(
            targetOffset + MOVE_HISTORY_OFFSETOF(
                struct PokemonMoveHistoryStore,
                footer),
            footer,
            sizeof(*footer)) != TRUE) {
        saveData->pokemonMoveHistoryDirty = TRUE;
        saveData->pokemonMoveHistorySaveReady = FALSE;
        return FALSE;
    }

    saveData->pokemonMoveHistoryStagedMirror = targetMirror;
    saveData->pokemonMoveHistoryStagedRevision =
        saveData->pokemonMoveHistoryRevision;
    saveData->pokemonMoveHistoryStagedSaveCounter = saveData->saveCounter;
    return TRUE;
}

static void PokemonMoveHistory_SeedParty(
    SaveData *saveData) __attribute__((noinline, used));

static void PokemonMoveHistory_SeedParty(SaveData *saveData)
{
    struct Party *party;
    int partyCount;
    int i;

    party = SaveData_GetPlayerPartyPtr(saveData);
    if (party == NULL) {
        return;
    }
    partyCount = Party_GetCount(party);
    if (partyCount < 0) {
        return;
    }
    if (partyCount > 6) {
        partyCount = 6;
    }
    for (i = 0; i < partyCount; i++) {
        struct PartyPokemon *pokemon;

        /*
         * The retail Party accessor owns the persisted 0xEC record stride.
         * GCC may pad our source-level PartyPokemon to 0xF0, so indexing the
         * members array here would walk into encrypted payload bytes.
         */
        pokemon = Party_GetMonByIndex(party, i);
        PokemonMoveHistory_SeedImpl(
            saveData,
            &pokemon->box);
    }
}

void PokemonMoveHistory_LoadAndSeedPartyImpl(SaveData *saveData)
{
    PokemonMoveHistory_LoadImpl(saveData);
}

BOOL PokemonMoveHistory_PrepareSaveImpl(SaveData *saveData)
{
    BOOL historyReady;

    if (saveData->pokemonMoveHistory == NULL) {
        /*
         * Save_WriteManInit has already advanced saveCounter. A sidecar
         * recovered after an earlier allocation failure is therefore
         * eligible only through the last committed primary generation.
         */
        PokemonMoveHistory_LoadForCounter(
            saveData,
            saveData->saveCounter - 1);
    }
    PokemonMoveHistory_SeedParty(saveData);
    historyReady = PokemonMoveHistory_CommitIfDirtyImpl(saveData);
    return historyReady;
}

void PokemonMoveHistory_FinishSaveImpl(
    SaveData *saveData,
    BOOL success)
{
    if (saveData->pokemonMoveHistoryStagedMirror
            != MOVE_HISTORY_NO_MIRROR) {
        if (success
            && saveData->pokemonMoveHistoryStagedSaveCounter
                == saveData->saveCounter) {
            saveData->pokemonMoveHistoryActiveMirror =
                saveData->pokemonMoveHistoryStagedMirror;
            if (saveData->pokemonMoveHistoryRevision
                == saveData->pokemonMoveHistoryStagedRevision) {
                saveData->pokemonMoveHistoryDirty = FALSE;
            }
        } else {
            /*
             * The mirror may be valid but is not paired with a committed
             * primary generation, so keep the sidecar pending for retry.
             */
            saveData->pokemonMoveHistoryDirty = TRUE;
        }
    }
    saveData->pokemonMoveHistoryStagedMirror = MOVE_HISTORY_NO_MIRROR;
    saveData->pokemonMoveHistoryStagedRevision = 0;
    saveData->pokemonMoveHistoryStagedSaveCounter = 0;
}

void PokemonMoveHistory_CancelSaveImpl(SaveData *saveData)
{
    if (saveData->pokemonMoveHistoryStagedMirror
            != MOVE_HISTORY_NO_MIRROR) {
        saveData->pokemonMoveHistoryDirty = TRUE;
    }
    saveData->pokemonMoveHistoryStagedMirror = MOVE_HISTORY_NO_MIRROR;
    saveData->pokemonMoveHistoryStagedRevision = 0;
    saveData->pokemonMoveHistoryStagedSaveCounter = 0;
}

int PokemonMoveHistory_WriteSaveNowImpl(SaveData *saveData)
{
    struct AsyncWriteManager writeManager;
    int result;

    Save_WriteManInit(saveData, &writeManager, 2);
    do {
        if (writeManager.curSector == 1) {
            result = HandleWriteSaveAsync_PCBoxes(
                saveData,
                &writeManager);
        } else {
            result = HandleWriteSaveAsync_NormalData(
                saveData,
                &writeManager);
        }
    } while (result == WRITE_STATUS_CONTINUE
        || result == WRITE_STATUS_NEXT);
    Save_WriteManFinish(saveData, &writeManager, result);
    return result;
}

int SaveGameNormalImpl(SaveData *saveData)
{
    int result;

    if (!saveData->flashChipDetected) {
        return WRITE_STATUS_TOTAL_FAIL;
    }
    if (saveData->isNewGame) {
        Sys_SetSleepDisableFlag(1);
        FlashClobberChunkFooter(
            saveData,
            0,
            saveData->lastGoodSector == 0 ? 1 : 0);
        FlashClobberChunkFooter(
            saveData,
            1,
            saveData->lastGoodSector == 0 ? 1 : 0);
        FlashClobberChunkFooter(
            saveData,
            0,
            saveData->lastGoodSector);
        FlashClobberChunkFooter(
            saveData,
            1,
            saveData->lastGoodSector);
        Sys_ClearSleepDisableFlag(1);
    }
    result = PokemonMoveHistory_WriteSaveNowImpl(saveData);
    if (result == WRITE_STATUS_SUCCESS) {
        saveData->saveFileExists = TRUE;
        saveData->isNewGame = FALSE;
    }
    return result;
}
