#include "../../include/constants/file.h"
#include "../../include/constants/moves.h"
#include "../../include/constants/species.h"
#include "../../include/battle.h"
#include "../../include/config.h"
#include "../../include/pokemon.h"
#include "../../include/pokemon_move_history.h"
#include "../../include/pokemon_storage_system.h"
#include "../../include/save.h"

typedef void (*DaycareDepositRetailFunc)(
    struct Party *,
    int,
    DaycareMon *,
    SaveData *);
typedef void (*TradeSlotCopyRetailFunc)(
    struct Party *,
    int,
    struct PartyPokemon *);
typedef void (*GTSDeleteBoxRetailFunc)(PCStorage *, u32, u32);
typedef BOOL (*GTSRemovePartyRetailFunc)(struct Party *, u32);
typedef BOOL (*GTSPlaceBoxRetailFunc)(
    PCStorage *,
    u32,
    struct BoxPokemon *);
typedef void (*PokewalkerRadioSuccessRetailFunc)(void *pokewalker);
typedef void (*PokewalkerRecoveryRetailFunc)(void *pokewalkerApp);
typedef void (*OverworldFieldReadyRetailPollFunc)(void *fieldSystem);

#define TASK6_SAVE_PCSTORAGE 41
#define TASK6_POKEWALKER_DIAGNOSTIC_WORDS (0x134 / sizeof(u32))

u32 __attribute__((section(".pokemon_move_history_task6_data")))
gPokemonMoveHistoryTask6PartyMenuSignalStorage;

/*
 * Export preparation is reversible until the Pokewalker IR state machine
 * reports status 15. Keep the selected owner's snapshot in resident transient
 * memory so cancel/recovery cannot allocate, touch, or evict persisted history.
 */
static PokemonMoveHistorySnapshot sPokewalkerPendingSnapshot;
static BOOL sPokewalkerPendingValid;
static u32 sPokewalkerDiagnosticBuffer[
    TASK6_POKEWALKER_DIAGNOSTIC_WORDS];

volatile PokemonMoveHistoryTask6DiagnosticMailbox
    gPokemonMoveHistoryTask6DiagnosticMailbox
    __attribute__((section(".pokemon_move_history_task6_diagnostic_data")));

typedef char PokemonMoveHistoryTask6DiagnosticMailboxSizeAssert[
    sizeof(PokemonMoveHistoryTask6DiagnosticMailbox) == 0x30 ? 1 : -1];

BOOL PokemonMoveHistoryTask6_IsCanonicalImpl(struct BoxPokemon *pokemon)
{
    u32 form;
    u32 species;
    u16 mappedSpecies;

    if (pokemon == NULL
        || GetBoxMonData(pokemon, MON_DATA_CHECKSUM_FAILED, NULL)
        || !GetBoxMonData(pokemon, MON_DATA_SPECIES_EXISTS, NULL)
        || GetBoxMonData(pokemon, MON_DATA_IS_EGG, NULL)) {
        return FALSE;
    }
    species = GetBoxMonData(pokemon, MON_DATA_SPECIES, NULL);
    form = GetBoxMonData(pokemon, MON_DATA_FORM, NULL);
    if (species == SPECIES_NONE
        || species == SPECIES_EGG
        || species == SPECIES_BAD_EGG
        || species > MAX_MON_NUM
        || form >= 32) {
        return FALSE;
    }
    if (form == 0) {
        return TRUE;
    }

    switch (species) {
    case SPECIES_CASTFORM:
    case SPECIES_CHERRIM:
        return FALSE;
    case SPECIES_BURMY:
    case SPECIES_WORMADAM:
    case SPECIES_SHELLOS:
    case SPECIES_GASTRODON:
    case SPECIES_ARCEUS:
    case SPECIES_DEOXYS:
    case SPECIES_UNOWN:
    case SPECIES_SHAYMIN:
    case SPECIES_ROTOM:
    case SPECIES_GIRATINA:
    case SPECIES_PICHU:
        return SanitizeFormNumber((u16)species, (u8)form) == form;
    }

    ArchiveDataLoadOfs(
        &mappedSpecies,
        ARC_CODE_ADDONS,
        CODE_ADDON_FORM_DATA,
        sizeof(u16) * (32 * species + form - 1),
        sizeof(mappedSpecies));
    return mappedSpecies != 0 && !(mappedSpecies & NEEDS_REVERSION);
}

void __attribute__((section(".pokemon_move_history_task6_short_branch_targets")))
PokemonMoveHistoryTask6_DaycareDepositCommitImpl(
    struct Party *party,
    u32 partySlot,
    DaycareMon *daycareMon,
    SaveData *saveData)
{
    DaycareDepositRetailFunc retailCommit =
        (DaycareDepositRetailFunc)0x0206BE35;

    retailCommit(party, (int)partySlot, daycareMon, saveData);
    PokemonMoveHistory_Seed(saveData, &daycareMon->mon);
}

void PokemonMoveHistoryTask6_TradeReplacePartySlotImpl(
    struct Party *party,
    u32 partySlot,
    struct PartyPokemon *incoming)
{
    PokemonMoveHistorySnapshot outgoing;
    TradeSlotCopyRetailFunc retailCommit =
        (TradeSlotCopyRetailFunc)0x02074741;
    SaveData *saveData = SaveBlock2_get();
    BOOL captured = PokemonMoveHistory_CaptureSnapshot(
        &Party_GetMonByIndex(party, partySlot)->box,
        &outgoing);

    retailCommit(party, (int)partySlot, incoming);
    if (captured) {
        PokemonMoveHistory_RecordSnapshot(saveData, &outgoing);
    }
    PokemonMoveHistory_Seed(
        saveData,
        &Party_GetMonByIndex(party, partySlot)->box);
}

void PokemonMoveHistoryTask6_HatchClearEggImpl(
    struct PartyPokemon *pokemon,
    int attr,
    void *value)
{
    SetMonData(pokemon, attr, value);
    PokemonMoveHistory_Seed(SaveBlock2_get(), &pokemon->box);
}

struct BoxPokemon *PokemonMoveHistoryTask6_PCStorageGetAndStageImpl(
    PCStorage *storage,
    u32 boxno,
    u32 slotno)
{
    struct BoxPokemon *pokemon =
        PCStorage_GetMonByIndexPair(storage, boxno, slotno);

    sPokewalkerPendingValid = FALSE;
    if (PokemonMoveHistory_CaptureSnapshot(
            pokemon,
            &sPokewalkerPendingSnapshot)) {
        sPokewalkerPendingValid = TRUE;
    }
    return pokemon;
}

void PokemonMoveHistoryTask6_PokewalkerRadioSuccessImpl(void *pokewalker)
{
    PokewalkerRadioSuccessRetailFunc retailSuccess =
        (PokewalkerRadioSuccessRetailFunc)0x02032645;

    /* Retail advances the Walker transaction only after IR status 15. */
    retailSuccess(pokewalker);
    if (!sPokewalkerPendingValid) {
        return;
    }

    /* Clear first so a second success callback can never record twice. */
    sPokewalkerPendingValid = FALSE;
    PokemonMoveHistory_RecordSnapshot(
        SaveBlock2_get(),
        &sPokewalkerPendingSnapshot);
}

void PokemonMoveHistoryTask6_PokewalkerRecoverAndDiscardImpl(
    void *pokewalkerApp)
{
    PokewalkerRecoveryRetailFunc retailRecovery =
        (PokewalkerRecoveryRetailFunc)0x021EC135;

    /*
     * Retail's named ov112 caller always supplies its application owner.
     * NULL is reserved for the sealed emulator diagnostic, which exercises
     * this exact packaged pending-discard boundary while ov112 is unmapped.
     */
    if (pokewalkerApp != NULL) {
        retailRecovery(pokewalkerApp);
    }
    sPokewalkerPendingValid = FALSE;
}

static void PokemonMoveHistoryTask6_PokewalkerDiagnosticPollImpl(void)
{
    volatile PokemonMoveHistoryTask6DiagnosticMailbox *mailbox =
        &gPokemonMoveHistoryTask6DiagnosticMailbox;
    SaveData *saveData;
    PCStorage *storage;
    u32 requestSequence;
    u32 operation;
    u32 boxno;
    u32 slotno;
    u16 *walkerCounter;

    /* The zero-initialized retail path is one load, compare, and return. */
    if (mailbox->magic != POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_MAGIC) {
        return;
    }

    requestSequence = mailbox->requestSequence;
    operation = mailbox->operation;
    boxno = mailbox->boxno;
    slotno = mailbox->slotno;

    /* Consume before any packaged call; a crash cannot replay the request. */
    mailbox->magic = 0;
    mailbox->result = 0;
    mailbox->status = POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_RUNNING;

    if (mailbox->version != POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_VERSION
        || requestSequence == 0
        || requestSequence != mailbox->completionSequence + 1) {
        mailbox->status = POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_REJECTED;
        return;
    }

    saveData = SaveBlock2_get();
    if (saveData == NULL) {
        mailbox->status = POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_REJECTED;
        return;
    }
    storage = (PCStorage *)SaveArray_Get(saveData, TASK6_SAVE_PCSTORAGE);
    if (storage == NULL) {
        mailbox->status = POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_REJECTED;
        return;
    }

    switch (operation) {
    case POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STAGE:
        if (boxno >= NUM_PC_BOXES || slotno >= MONS_PER_BOX) {
            mailbox->status =
                POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_REJECTED;
            return;
        }
        mailbox->result = (u32)PokemonMoveHistoryTask6_PCStorageGetAndStage(
            storage,
            boxno,
            slotno);
        break;

    case POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_ACK_FIRST:
    case POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_ACK_SECOND:
        walkerCounter = (u16 *)((u8 *)sPokewalkerDiagnosticBuffer + 0x124);
        *walkerCounter = (u16)mailbox->walkerCounterSeed;
        if (operation == POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_ACK_FIRST) {
            PokemonMoveHistoryTask6_PokewalkerRadioSuccess(
                sPokewalkerDiagnosticBuffer);
        } else {
            PokemonMoveHistoryTask6_PokewalkerRadioSuccessSecond(
                sPokewalkerDiagnosticBuffer);
        }
        mailbox->walkerCounterAfter = *walkerCounter;
        mailbox->result = TRUE;
        break;

    case POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_RECOVER_DISCARD:
        PokemonMoveHistoryTask6_PokewalkerRecoverAndDiscard(NULL);
        mailbox->result = TRUE;
        break;

    default:
        mailbox->status = POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_REJECTED;
        return;
    }

    mailbox->status = POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_COMPLETE;
    /* Completion is the release word and is always published last. */
    mailbox->completionSequence = requestSequence;
}

void PokemonMoveHistoryTask6_FieldReadyDiagnosticPollImpl(void *fieldSystem)
{
    OverworldFieldReadyRetailPollFunc retailPoll =
        (OverworldFieldReadyRetailPollFunc)0x023C8011;

    /* Preserve the exact replaced call before any task-6 diagnostic work. */
    retailPoll(fieldSystem);
    PokemonMoveHistoryTask6_PokewalkerDiagnosticPollImpl();
}

BOOL __attribute__((section(".pokemon_move_history_task6_short_branch_targets")))
PokemonMoveHistoryTask6_PCStoragePlaceAndSeedImpl(
    PCStorage *storage,
    u32 boxno,
    u32 slotno,
    struct BoxPokemon *boxMon)
{
    struct BoxPokemon *placed;

    if (!PCStorage_PlaceMonInBoxByIndexPair(
            storage,
            boxno,
            slotno,
            boxMon)) {
        return FALSE;
    }
    placed = PCStorage_GetMonByIndexPair(storage, boxno, slotno);
    PokemonMoveHistory_Seed(SaveBlock2_get(), placed);
    return TRUE;
}

BOOL PokemonMoveHistoryTask6_GTSPlaceAndSeedImpl(
    PCStorage *storage,
    u32 boxno,
    struct BoxPokemon *boxMon)
{
    int resolvedBox = (int)boxno;
    int resolvedSlot = 0;
    struct BoxPokemon *placed;
    GTSPlaceBoxRetailFunc retailCommit =
        (GTSPlaceBoxRetailFunc)0x02073BFD;

    /*
     * Both GTS receive paths have just resolved this same first empty slot.
     * Resolve it again before the retail commit so only the canonical
     * successful destination is observed; full/failure paths remain clean.
     */
    PCStorage_FindFirstEmptySlot(storage, &resolvedBox, &resolvedSlot);
    if (resolvedBox != (int)boxno
        || resolvedSlot < 0
        || resolvedSlot >= MONS_PER_BOX
        || !retailCommit(storage, boxno, boxMon)) {
        return FALSE;
    }
    placed = PCStorage_GetMonByIndexPair(
        storage,
        (u32)resolvedBox,
        (u32)resolvedSlot);
    PokemonMoveHistory_Seed(SaveBlock2_get(), placed);
    return TRUE;
}

void PokemonMoveHistoryTask6_GTSDeleteBoxAndRecordImpl(
    PCStorage *storage,
    u32 boxno,
    u32 slotno)
{
    PokemonMoveHistorySnapshot outgoing;
    GTSDeleteBoxRetailFunc retailCommit =
        (GTSDeleteBoxRetailFunc)0x02073D11;
    BOOL captured = PokemonMoveHistory_CaptureSnapshot(
        PCStorage_GetMonByIndexPair(storage, boxno, slotno),
        &outgoing);

    retailCommit(storage, boxno, slotno);
    if (captured) {
        PokemonMoveHistory_RecordSnapshot(SaveBlock2_get(), &outgoing);
    }
}

BOOL PokemonMoveHistoryTask6_GTSRemovePartyAndRecordImpl(
    struct Party *party,
    u32 partySlot)
{
    PokemonMoveHistorySnapshot outgoing;
    GTSRemovePartyRetailFunc retailCommit =
        (GTSRemovePartyRetailFunc)0x0207456D;
    BOOL captured = PokemonMoveHistory_CaptureSnapshot(
        &Party_GetMonByIndex(party, partySlot)->box,
        &outgoing);
    BOOL result = retailCommit(party, partySlot);

    if (result && captured) {
        PokemonMoveHistory_RecordSnapshot(SaveBlock2_get(), &outgoing);
    }
    return result;
}

void __attribute__((section(".pokemon_move_history_task6_short_branch_targets")))
PokemonMoveHistoryTask6_ScriptTeachMoveImpl(
    SaveData *saveData,
    struct BoxPokemon *pokemon,
    u32 encodedMoveSlot,
    u32 pp)
{
    u32 moveSlot = encodedMoveSlot & 0xFF;
    u32 move = encodedMoveSlot >> 8;
    u32 ppUps = 0;

    SetBoxMonData(pokemon, MON_DATA_MOVE1 + moveSlot, &move);
    SetBoxMonData(pokemon, MON_DATA_MOVE1PPUP + moveSlot, &ppUps);
    SetBoxMonData(pokemon, MON_DATA_MOVE1PP + moveSlot, &pp);
    PokemonMoveHistory_RecordMove(saveData, pokemon, (u16)move);
}

void __attribute__((section(".pokemon_move_history_task6_short_branch_targets")))
PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl(
    struct PartyPokemon *pokemon,
    u32 oldMove,
    u32 newMove,
    BOOL recordPermanentHistory)
{
    u32 slot;

    for (slot = 0; slot < 4; slot++) {
        if (GetMonData(pokemon, MON_DATA_MOVE1 + slot, NULL) == oldMove) {
            if (recordPermanentHistory) {
                PokemonMoveHistory_ReplaceMove(
                    &pokemon->box,
                    (u16)newMove,
                    slot);
                break;
            }
            SetMonData(pokemon, MON_DATA_MOVE1 + slot, &newMove);
            {
                u32 maxPP =
                    GetMonData(
                        pokemon,
                        MON_DATA_MOVE1MAXPP + slot,
                        NULL);
                if (GetMonData(
                        pokemon,
                        MON_DATA_MOVE1PP + slot,
                        NULL) > maxPP) {
                    SetMonData(
                        pokemon,
                        MON_DATA_MOVE1PP + slot,
                        &maxPP);
                }
            }
            break;
        }
    }
}

/*
 * Battle-only form rewrites are deliberately non-permanent. They reuse the
 * audited swap implementation with history capture disabled, so transient
 * battle state can never enter the permanent learned/forgotten record.
 *
 * Written as if-chains to avoid Thumb switch helper relocations in this
 * independently linked resident overlay.
 */
void PokemonMoveHistoryTask6_CorrectBattleFormMovesImpl(
    struct PartyPokemon *pokemon,
    unsigned int expectedForm,
    int *unused)
{
    u32 species = GetMonData(pokemon, MON_DATA_SPECIES, NULL);

    (void)unused;
    if (species == SPECIES_KYUREM) {
        if (expectedForm == 0) {
            PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl(
                pokemon, MOVE_ICE_BURN, MOVE_GLACIATE, FALSE);
            PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl(
                pokemon, MOVE_FREEZE_SHOCK, MOVE_GLACIATE, FALSE);
            PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl(
                pokemon, MOVE_FUSION_FLARE, MOVE_SCARY_FACE, FALSE);
            PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl(
                pokemon, MOVE_FUSION_BOLT, MOVE_SCARY_FACE, FALSE);
        } else if (expectedForm == 1) {
            PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl(
                pokemon, MOVE_GLACIATE, MOVE_ICE_BURN, FALSE);
            PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl(
                pokemon, MOVE_SCARY_FACE, MOVE_FUSION_FLARE, FALSE);
        } else if (expectedForm == 2) {
            PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl(
                pokemon, MOVE_GLACIATE, MOVE_FREEZE_SHOCK, FALSE);
            PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl(
                pokemon, MOVE_SCARY_FACE, MOVE_FUSION_BOLT, FALSE);
        }
    } else if (species == SPECIES_ZACIAN) {
        if (expectedForm == 0) {
            PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl(
                pokemon, MOVE_BEHEMOTH_BLADE, MOVE_IRON_HEAD, FALSE);
        } else if (expectedForm == 1) {
            PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl(
                pokemon, MOVE_IRON_HEAD, MOVE_BEHEMOTH_BLADE, FALSE);
        }
    } else if (species == SPECIES_ZAMAZENTA) {
        if (expectedForm == 0) {
            PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl(
                pokemon, MOVE_BEHEMOTH_BASH, MOVE_IRON_HEAD, FALSE);
        } else if (expectedForm == 1) {
            PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl(
                pokemon, MOVE_IRON_HEAD, MOVE_BEHEMOTH_BASH, FALSE);
        }
    }
}

void PokemonMoveHistoryTask6_MarkHistoryMoveImpl(
    const u16 *history,
    u32 historyCount,
    u8 *allowed,
    u16 move)
{
    u32 i;

    for (i = 0; i < historyCount; i++) {
        if (history[i] == move) {
            allowed[i] = TRUE;
        }
    }
}

static BOOL PokemonMoveHistoryTask6_IsCurrentMove(
    const u16 currentMoves[4],
    u16 move)
{
    u32 i;

    for (i = 0; i < 4; i++) {
        if (currentMoves[i] == move) {
            return TRUE;
        }
    }
    return FALSE;
}

static BOOL PokemonMoveHistoryTask6_IsImplementedMove(u16 move)
{
    struct BattleMove moveData;

    if (move == MOVE_NONE || move >= NUM_OF_MOVES) {
        return FALSE;
    }
#ifdef BLOCK_LEARNING_UNIMPLEMENTED_MOVES
    ArchiveDataLoad(&moveData, ARC_MOVE_DATA, move);
    return (moveData.flag & FLAG_UNUSED_MOVE) == 0;
#else
    return TRUE;
#endif
}

BOOL PokemonMoveHistoryTask6_AppendCandidateImpl(
    u16 *candidates,
    u32 *count,
    const u16 currentMoves[4],
    u16 move)
{
    u32 i;

    if (PokemonMoveHistoryTask6_IsCurrentMove(currentMoves, move)) {
        return FALSE;
    }
    for (i = 0; i < *count; i++) {
        if (candidates[i] == move) {
            return FALSE;
        }
    }
    if (!PokemonMoveHistoryTask6_IsImplementedMove(move)) {
        return FALSE;
    }
    candidates[(*count)++] = move;
    return TRUE;
}
