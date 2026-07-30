#ifndef POKEMON_MOVE_HISTORY_H
#define POKEMON_MOVE_HISTORY_H

#include "pokemon.h"
#include "save.h"

#define POKEMON_MOVE_HISTORY_MAX_MOVES 24

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
void PokemonMoveHistory_Init(SaveData *saveData);
void PokemonMoveHistory_Load(SaveData *saveData);
void PokemonMoveHistory_Reset(SaveData *saveData);

/**
 * Ensures that a Pokemon has a history record and unions in its four current
 * moves. This both seeds first observation and repairs missed observations.
 *
 * @return TRUE when the record is available.
 */
BOOL PokemonMoveHistory_CaptureSnapshot(
    struct BoxPokemon *pokemon,
    PokemonMoveHistorySnapshot *snapshot);
BOOL PokemonMoveHistory_Seed(
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
BOOL PokemonMoveHistory_RecordMove(
    SaveData *saveData,
    struct BoxPokemon *pokemon,
    u16 move);

/**
 * Adds all four captured moves to the keyed Pokemon's history. Capture and
 * record the snapshot before replacing a move so the forgotten move survives.
 *
 * @return TRUE when the record is available.
 */
BOOL PokemonMoveHistory_RecordSnapshot(
    SaveData *saveData,
    const PokemonMoveHistorySnapshot *snapshot);

/**
 * Seeds a first-observed Pokemon, then copies its move history to movesOut.
 * Passing NULL or a zero capacity only returns the stored count.
 *
 * @return The full stored count, which can be larger than movesOutCapacity.
 */
u32 PokemonMoveHistory_Query(
    SaveData *saveData,
    struct BoxPokemon *pokemon,
    u16 *movesOut,
    u32 movesOutCapacity);

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
BOOL PokemonMoveHistory_CommitIfDirty(SaveData *saveData);

/*
 * Save lifecycle integration. Feature callers should use the APIs above;
 * these entry points keep the resident save hooks small and transactional.
 * PrepareSave's result reports only the ancillary history attempt and must
 * not be used to gate primary saving. FinishSave promotes a staged mirror
 * only after primary success; CancelSave leaves history dirty for retry.
 */
void PokemonMoveHistory_LoadAndSeedParty(SaveData *saveData);
BOOL PokemonMoveHistory_PrepareSave(SaveData *saveData);
void PokemonMoveHistory_FinishSave(SaveData *saveData, BOOL success);
void PokemonMoveHistory_CancelSave(SaveData *saveData);
int PokemonMoveHistory_WriteSaveNow(SaveData *saveData);

#endif // POKEMON_MOVE_HISTORY_H
