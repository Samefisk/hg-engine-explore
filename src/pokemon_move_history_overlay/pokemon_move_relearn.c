#include "../../include/battle.h"
#include "../../include/config.h"
#include "../../include/item.h"
#include "../../include/pokemon_move_history.h"
#include "../../include/constants/file.h"
#include "../../include/constants/moves.h"
#include "../../include/constants/species.h"

#define MOVE_RELEARN_LINEAGE_LIMIT 8
#define MOVE_RELEARN_EGG_END 0xFFFF

extern const u16 sMachineMoves[NUM_MACHINE_MOVES];
extern void *PokemonMoveHistory_OverlayMemcpy(
    void *destination,
    const void *source,
    u32 size);
extern void *PokemonMoveHistory_OverlayMemset(
    void *destination,
    int value,
    u32 size);
u32 PokemonMoveHistory_QueryReadOnlyImpl(
    SaveData *saveData,
    struct BoxPokemon *pokemon,
    u16 *movesOut,
    u32 movesOutCapacity);

union MoveRelearnSourceData {
    u32 level[MAX_LEVELUP_MOVES];
    u32 machine[MACHINE_LEARNSETS_BITFIELD_COUNT];
    u16 egg[MAX_EGG_MOVES];
    u32 tutor[TUTOR_LEARNSETS_BITFIELD_COUNT];
};

static BOOL PokemonMoveRelearn_IsCurrentMove(
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

static BOOL PokemonMoveRelearn_IsImplementedMove(u16 move)
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

/*
 * Keep the task1-5 private call targets and combined footprint while the
 * implementations live in resident task-6 overlay 155. These tail wrappers
 * free exactly 0x40, balancing the two canonical-gate compatibility pads.
 */
static void __attribute__((naked, used))
PokemonMoveRelearn_MarkHistoryMove(
    const u16 *history UNUSED,
    u32 historyCount UNUSED,
    u8 *allowed UNUSED,
    u16 move UNUSED)
{
    __asm__(
        "push {r3}\n"
        "ldr r3, 1f\n"
        "mov r12, r3\n"
        "pop {r3}\n"
        "bx r12\n"
        ".align 2\n"
        "1: .word PokemonMoveHistoryTask6_MarkHistoryMove + 1\n"
        ".space 0x0a\n");
}

static BOOL __attribute__((naked, used))
PokemonMoveRelearn_Append(
    u16 *candidates UNUSED,
    u32 *count UNUSED,
    const u16 currentMoves[4] UNUSED,
    u16 move UNUSED)
{
    __asm__(
        "push {r3}\n"
        "ldr r3, 1f\n"
        "mov r12, r3\n"
        "pop {r3}\n"
        "bx r12\n"
        ".align 2\n"
        "1: .word PokemonMoveHistoryTask6_AppendCandidate + 1\n"
        ".space 0x16\n");
}

static BOOL PokemonMoveRelearn_IsBuiltInSpecial(
    u16 species,
    u16 form,
    u16 move)
{
    /*
     * Vanilla's Spiky-ear Pichu gift has these exact four scripted moves.
     * Keep event exceptions explicit and species/form scoped even when a move
     * also happens to be present in a generated compatibility table.
     */
    if (species != SPECIES_PICHU || form != 1) {
        return FALSE;
    }
    return move == MOVE_HELPING_HAND
        || move == MOVE_VOLT_TACKLE
        || move == MOVE_SWAGGER
        || move == MOVE_PAIN_SPLIT;
}

static u16 PokemonMoveRelearn_GetParent(u16 species)
{
    u16 parent;

    ArchiveDataLoadOfs(
        &parent,
        ARC_CODE_ADDONS,
        CODE_ADDON_MOVE_RELEARN_PARENTS,
        species * sizeof(parent),
        sizeof(parent));
    return parent;
}

u32 __attribute__((section(".pokemon_move_history_short_branch_targets")))
PokemonMoveRelearn_BuildCandidatesImpl(
    SaveData *saveData,
    struct BoxPokemon *boxPokemon,
    u16 *candidatesOut,
    u32 candidatesOutCapacity,
    const PokemonMoveRelearnOptions *options)
{
    union MoveRelearnSourceData source;
    u16 candidates[POKEMON_MOVE_RELEARN_MAX_CANDIDATES];
    u16 history[POKEMON_MOVE_HISTORY_MAX_MOVES];
    u16 tutorMoves[NUM_TUTOR_MOVES];
    u16 currentMoves[4];
    u8 historyAllowed[POKEMON_MOVE_HISTORY_MAX_MOVES];
    u16 species;
    u16 form;
    u16 lineageSpecies;
    u16 move;
    u32 historyCount;
    u32 candidateCount;
    u32 level;
    u32 lineageDepth;
    u32 i;
    u32 j;

    if (saveData == NULL
        || !PokemonMoveHistoryTask6_IsCanonical(boxPokemon)) {
        return 0;
    }

    species = (u16)GetBoxMonData(boxPokemon, MON_DATA_SPECIES, NULL);
    form = (u16)GetBoxMonData(boxPokemon, MON_DATA_FORM, NULL);
    level = GetBoxMonData(boxPokemon, MON_DATA_LEVEL, NULL);
    for (i = 0; i < 4; i++) {
        currentMoves[i] =
            (u16)GetBoxMonData(boxPokemon, MON_DATA_MOVE1 + i, NULL);
    }

    /*
     * Candidate browsing is observational. Opening and cancelling Summary
     * relearn mode must not allocate, reorder, or dirty the history sidecar.
     */
    historyCount = PokemonMoveHistory_QueryReadOnlyImpl(
        saveData,
        boxPokemon,
        history,
        POKEMON_MOVE_HISTORY_MAX_MOVES);
    if (historyCount > POKEMON_MOVE_HISTORY_MAX_MOVES) {
        historyCount = POKEMON_MOVE_HISTORY_MAX_MOVES;
    }
    PokemonMoveHistory_OverlayMemset(
        historyAllowed,
        0,
        sizeof(historyAllowed));
    ArchiveDataLoadOfs(
        tutorMoves,
        ARC_CODE_ADDONS,
        CODE_ADDON_TUTOR_LEARNSETS,
        TUTOR_MOVE_IDS_OFFSET,
        sizeof(tutorMoves));
    candidateCount = 0;
    lineageSpecies = (u16)PokeOtherFormMonsNoGet(species, form);

    for (lineageDepth = 0;
         lineageSpecies != SPECIES_NONE
            && lineageSpecies <= MAX_SPECIES_INCLUDING_FORMS
            && lineageDepth < MOVE_RELEARN_LINEAGE_LIMIT;
         lineageDepth++) {
        /*
         * HGSS can breed Volt Tackle onto ordinary Pichu through Light Ball,
         * outside the generated egg list. Treat it as an explicit Pichu
         * lineage source so legitimate evolved history remains legal.
         */
        if (lineageSpecies == SPECIES_PICHU) {
            PokemonMoveRelearn_MarkHistoryMove(
                history,
                historyCount,
                historyAllowed,
                MOVE_VOLT_TACKLE);
        }

        LoadLevelUpLearnset_HandleAlternateForm(
            lineageSpecies,
            0,
            source.level);
        for (i = 0; i < MAX_LEVELUP_MOVES; i++) {
            if (source.level[i] == LEVEL_UP_LEARNSET_END) {
                break;
            }
            if (LEVEL_UP_LEARNSET_LEVEL(source.level[i]) > level) {
                continue;
            }
            move = (u16)LEVEL_UP_LEARNSET_MOVE(source.level[i]);
            PokemonMoveRelearn_MarkHistoryMove(
                history,
                historyCount,
                historyAllowed,
                move);
            if (lineageDepth == 0) {
                PokemonMoveRelearn_Append(
                    candidates,
                    &candidateCount,
                    currentMoves,
                    move);
            }
        }

        ArchiveDataLoadOfs(
            source.machine,
            ARC_CODE_ADDONS,
            CODE_ADDON_MACHINE_LEARNSETS,
            lineageSpecies * sizeof(source.machine),
            sizeof(source.machine));
        for (i = 0; i < NUM_MACHINE_MOVES; i++) {
            if (source.machine[i / 32] & (1u << (i % 32))) {
                PokemonMoveRelearn_MarkHistoryMove(
                    history,
                    historyCount,
                    historyAllowed,
                    sMachineMoves[i]);
            }
        }

        ArchiveDataLoadOfs(
            source.egg,
            ARC_EGG_MOVES,
            0,
            lineageSpecies * sizeof(source.egg),
            sizeof(source.egg));
        for (i = 0;
             i < MAX_EGG_MOVES && source.egg[i] != MOVE_RELEARN_EGG_END;
             i++) {
            PokemonMoveRelearn_MarkHistoryMove(
                history,
                historyCount,
                historyAllowed,
                source.egg[i]);
        }

        ArchiveDataLoadOfs(
            source.tutor,
            ARC_CODE_ADDONS,
            CODE_ADDON_TUTOR_LEARNSETS,
            lineageSpecies * sizeof(source.tutor),
            sizeof(source.tutor));
        for (i = 0; i < NUM_TUTOR_MOVES; i++) {
            if (source.tutor[i / 32] & (1u << (i % 32))) {
                PokemonMoveRelearn_MarkHistoryMove(
                    history,
                    historyCount,
                    historyAllowed,
                    tutorMoves[i]);
            }
        }

        move = PokemonMoveRelearn_GetParent(lineageSpecies);
        if (move == lineageSpecies) {
            break;
        }
        lineageSpecies = move;
    }

    for (i = 0; i < historyCount; i++) {
        /*
         * Validate before consulting an extension policy so corrupt history
         * can never be interpreted by a task-specific callback.
         */
        if (!PokemonMoveRelearn_IsImplementedMove(history[i])) {
            continue;
        }
        if (!historyAllowed[i]
            && !PokemonMoveRelearn_IsBuiltInSpecial(
                species,
                form,
                history[i])
            && (options == NULL || options->allowSpecialMove == NULL
                || !options->allowSpecialMove(
                    boxPokemon,
                    history[i],
                    options->context))) {
            continue;
        }
        PokemonMoveRelearn_Append(
            candidates,
            &candidateCount,
            currentMoves,
            history[i]);
    }

    if (candidatesOut != NULL) {
        j = candidateCount;
        if (j > candidatesOutCapacity) {
            j = candidatesOutCapacity;
        }
        if (j != 0) {
            PokemonMoveHistory_OverlayMemcpy(
                candidatesOut,
                candidates,
                j * sizeof(*candidatesOut));
        }
    }
    return candidateCount;
}

/*
 * The shared task-6 canonical form gate compacts the builder by 0x30. Keep
 * generic overlay-153 code at its task1-5 sealed addresses.
 */
void __attribute__((
    naked,
    used,
    section(".pokemon_move_history_short_branch_targets")))
PokemonMoveHistoryTask6_CandidateBuilderLayoutPad(void)
{
    __asm__(
        ".space 0x2e\n"
        "bx lr\n");
}
