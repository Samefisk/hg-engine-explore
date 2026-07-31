#ifndef POKEMON_MOVE_HISTORY_H
#define POKEMON_MOVE_HISTORY_H

#include "constants/generated/learnsets.h"
#include "pokemon.h"
#include "save.h"

#define POKEMON_MOVE_HISTORY_MAX_MOVES 24
#define POKEMON_MOVE_RELEARN_MAX_CANDIDATES \
    (MAX_LEVELUP_MOVES + POKEMON_MOVE_HISTORY_MAX_MOVES)

typedef struct PokemonMoveHistorySnapshot {
    u32 personality;
    u32 otId;
    u16 species;
    u16 moves[4];
} PokemonMoveHistorySnapshot;

/*
 * Records use personality + original trainer ID because those fields remain
 * stable across trades and evolution without changing BoxPokemon. Exact
 * clones (including split-evolution descendants with the same pair) share
 * history by design; future candidate generation must still apply the
 * selected species' move-legality rules.
 */

/**
 * Initializes the transient move-history state and loads the newest valid
 * mirrored sidecar. Missing, incompatible, or corrupt sidecars are replaced
 * in memory and made dirty for the next save.
 */
void LONG_CALL PokemonMoveHistory_Init(SaveData *saveData);
void LONG_CALL PokemonMoveHistory_Load(SaveData *saveData);
void LONG_CALL PokemonMoveHistory_Reset(SaveData *saveData);

/**
 * Ensures that a Pokemon has a history record and unions in its four current
 * moves. This both seeds first observation and repairs missed observations.
 *
 * @return TRUE when the record is available.
 */
BOOL LONG_CALL PokemonMoveHistory_CaptureSnapshot(
    struct BoxPokemon *pokemon,
    PokemonMoveHistorySnapshot *snapshot);
BOOL LONG_CALL PokemonMoveHistory_Seed(
    SaveData *saveData,
    struct BoxPokemon *pokemon);

/**
 * Adds one move, ignoring MOVE_NONE and duplicate entries. When a Pokemon's
 * bounded history is full, the oldest stored move not among its current four
 * moves is discarded (falling back to the oldest move only if all are
 * current).
 *
 * @return TRUE when the record is available.
 */
BOOL LONG_CALL PokemonMoveHistory_RecordMove(
    SaveData *saveData,
    struct BoxPokemon *pokemon,
    u16 move);

/**
 * Adds all four captured moves to the keyed Pokemon's history. Capture and
 * record the snapshot before replacing a move so the forgotten move survives.
 *
 * @return TRUE when the record is available.
 */
BOOL LONG_CALL PokemonMoveHistory_RecordSnapshot(
    SaveData *saveData,
    const PokemonMoveHistorySnapshot *snapshot);

/**
 * Permanently replaces one move slot through the canonical BoxPokemon
 * accessors. The old four-move snapshot is recorded before mutation, and the
 * requested move is recorded only after a successful readback. Invalid slots,
 * duplicate assignments, MOVE_NONE, out-of-range moves, and unimplemented
 * moves do not add history.
 *
 * The current save is resolved at call time through SaveBlock2_get(); no
 * SaveData pointer is retained across save or overlay lifetimes.
 *
 * @return TRUE only when a distinct replacement is committed and read back.
 * Invalid, same-slot, or failed operations return FALSE.
 */
BOOL LONG_CALL PokemonMoveHistory_ReplaceMove(
    struct BoxPokemon *pokemon,
    u16 move,
    u32 slot);

/**
 * Records a PartyPokemon's current moves at a committed forget boundary,
 * then delegates to the retail canonical slot-deletion helper.
 */
void LONG_CALL PokemonMoveHistory_DeleteMoveSlot(
    struct PartyPokemon *pokemon,
    u32 slot);

/**
 * Seeds a first-observed Pokemon, then copies its move history to movesOut.
 * Passing NULL or a zero capacity only returns the stored count.
 *
 * @return The full stored count, which can be larger than movesOutCapacity.
 */
u32 LONG_CALL PokemonMoveHistory_Query(
    SaveData *saveData,
    struct BoxPokemon *pokemon,
    u16 *movesOut,
    u32 movesOutCapacity);

/**
 * Optional additive policy for persisted moves whose exact acquisition source
 * is not represented by hg-engine's level, machine, egg, or tutor tables
 * (notably event/script gifts). It is called only for otherwise-ineligible,
 * valid implemented moves. Returning TRUE admits the move.
 *
 * Task-specific policy must be species/form-aware through boxPokemon. It must
 * not treat persisted presence alone as universal legality.
 */
typedef BOOL (*PokemonMoveRelearnSpecialPolicy)(
    struct BoxPokemon *boxPokemon,
    u16 move,
    void *context);

typedef struct PokemonMoveRelearnOptions {
    PokemonMoveRelearnSpecialPolicy allowSpecialMove;
    void *context;
} PokemonMoveRelearnOptions;

/**
 * Builds relearn candidates for either a boxed Pokemon or the BoxPokemon
 * prefix of a PartyPokemon.
 *
 * Ordering is the current form's level-up table order (all entries at or
 * below the XP-derived current level), followed by accepted persisted moves
 * in acquisition order. The result excludes current moves, invalid or
 * unimplemented moves, and duplicates.
 *
 * Persisted moves are accepted only when an hg-engine level/machine/egg/tutor
 * table authorizes them for the current form-aware evolutionary lineage, when
 * a built-in HGSS rule authorizes them (Light Ball Volt Tackle or the
 * Spiky-ear Pichu gift), or when options->allowSpecialMove explicitly
 * authorizes them. The callback is an extension point for task 6; it cannot
 * override invalid/unimplemented-move rejection.
 *
 * Passing NULL candidatesOut or zero capacity performs a count-only query.
 * The function writes at most candidatesOutCapacity entries and returns the
 * full deduplicated count, so return > capacity reports truncation. No heap
 * allocation or ownership is transferred to the caller. Because construction
 * performs bounded archive reads, UI callers should cache the result for the
 * selected Pokemon instead of rebuilding it every frame.
 */
u32 LONG_CALL PokemonMoveRelearn_BuildCandidates(
    SaveData *saveData,
    struct BoxPokemon *boxPokemon,
    u16 *candidatesOut,
    u32 candidatesOutCapacity,
    const PokemonMoveRelearnOptions *options);

/**
 * Persists a dirty sidecar to the inactive mirror. Save code calls this
 * before writing the primary save. A failure leaves history dirty for retry
 * and never blocks the primary save; an interrupted or failed sidecar can
 * lose recent history, but cannot damage the main save. Persisted generation
 * comparisons require relevant primary/sidecar counters to remain less than
 * 2^31 saves apart.
 *
 * @return TRUE when no sidecar write was needed or the write was staged.
 */
BOOL LONG_CALL PokemonMoveHistory_CommitIfDirty(SaveData *saveData);

/*
 * Save lifecycle integration. Feature callers should use the APIs above;
 * these entry points keep the resident save hooks small and transactional.
 * PrepareSave's result reports only the ancillary history attempt and must
 * not be used to gate primary saving. FinishSave promotes a staged mirror
 * only after primary success; CancelSave leaves history dirty for retry.
 */
void LONG_CALL PokemonMoveHistory_LoadAndSeedParty(SaveData *saveData);
BOOL LONG_CALL PokemonMoveHistory_PrepareSave(SaveData *saveData);
void LONG_CALL PokemonMoveHistory_FinishSave(SaveData *saveData, BOOL success);
void LONG_CALL PokemonMoveHistory_CancelSave(SaveData *saveData);
int LONG_CALL PokemonMoveHistory_WriteSaveNow(SaveData *saveData);

/* Boot-resident task-6 transaction/validation bridge in overlay 155. */
BOOL LONG_CALL PokemonMoveHistoryTask6_IsCanonical(
    struct BoxPokemon *pokemon);
void LONG_CALL PokemonMoveHistoryTask6_DaycareDepositCommit(
    struct Party *party,
    u32 partySlot,
    DaycareMon *daycareMon,
    SaveData *saveData);
void LONG_CALL PokemonMoveHistoryTask6_TradeReplacePartySlot(
    struct Party *party,
    u32 partySlot,
    struct PartyPokemon *incoming);
void LONG_CALL PokemonMoveHistoryTask6_HatchClearEgg(
    struct PartyPokemon *pokemon,
    int attr,
    void *value);
struct PokemonStorageSystem;
struct BoxPokemon *LONG_CALL PokemonMoveHistoryTask6_PCStorageGetAndStage(
    struct PokemonStorageSystem *storage,
    u32 boxno,
    u32 slotno);
/* Legacy symbol retained at the same ABI address as GetAndStage. */
struct BoxPokemon *LONG_CALL PokemonMoveHistoryTask6_PCStorageGetAndSeed(
    struct PokemonStorageSystem *storage,
    u32 boxno,
    u32 slotno);
BOOL LONG_CALL PokemonMoveHistoryTask6_PCStoragePlaceAndSeed(
    struct PokemonStorageSystem *storage,
    u32 boxno,
    u32 slotno,
    struct BoxPokemon *boxMon);
BOOL LONG_CALL PokemonMoveHistoryTask6_GTSPlaceAndSeed(
    struct PokemonStorageSystem *storage,
    u32 boxno,
    struct BoxPokemon *boxMon);
void LONG_CALL PokemonMoveHistoryTask6_GTSDeleteBoxAndRecord(
    struct PokemonStorageSystem *storage,
    u32 boxno,
    u32 slotno);
BOOL LONG_CALL PokemonMoveHistoryTask6_GTSRemovePartyAndRecord(
    struct Party *party,
    u32 partySlot);
void LONG_CALL PokemonMoveHistoryTask6_PokewalkerRadioSuccess(
    void *pokewalker);
void LONG_CALL PokemonMoveHistoryTask6_PokewalkerRadioSuccessSecond(
    void *pokewalker);
void LONG_CALL PokemonMoveHistoryTask6_PokewalkerRecoverAndDiscard(
    void *pokewalkerApp);
/*
 * Retail-unreferenced legacy fail-stop slot. Sealed runtime evidence never
 * redirects the host PC here; the game-native mailbox dispatcher is used.
 */
void LONG_CALL PokemonMoveHistoryTask6_PokewalkerDiagnosticReturn(void);

#define POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_MAGIC 0x36574B50
#define POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_VERSION 1
#define POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_RUNNING 0x52554E36
#define POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_COMPLETE 0xC0016D48
#define POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_REJECTED 0xBAD60000

enum PokemonMoveHistoryTask6DiagnosticOperation {
    POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STAGE = 1,
    POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_ACK_FIRST = 2,
    POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_ACK_SECOND = 3,
    POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_RECOVER_DISCARD = 4,
};

typedef struct PokemonMoveHistoryTask6DiagnosticMailbox {
    u32 magic;
    u32 version;
    u32 requestSequence;
    u32 completionSequence;
    u32 operation;
    u32 boxno;
    u32 slotno;
    u32 result;
    u32 status;
    u32 walkerCounterSeed;
    u32 walkerCounterAfter;
    u32 reserved;
} PokemonMoveHistoryTask6DiagnosticMailbox;

extern volatile PokemonMoveHistoryTask6DiagnosticMailbox
    gPokemonMoveHistoryTask6DiagnosticMailbox;

/*
 * Replaces only the already-existing overworld field-ready call to
 * OverworldFollowerSelectorTaskPollEntry, preserving its r0 FieldSystem ABI
 * before checking the zero-by-default task-6 mailbox.
 */
void LONG_CALL PokemonMoveHistoryTask6_FieldReadyDiagnosticPoll(
    void *fieldSystem);
void LONG_CALL PokemonMoveHistoryTask6_ScriptTeachMove(
    SaveData *saveData,
    struct BoxPokemon *pokemon,
    u32 encodedMoveSlot,
    u32 pp);
#endif // POKEMON_MOVE_HISTORY_H
