#include "../../include/item.h"
#include "../../include/message.h"
#include "../../include/pokemon.h"
#include "../../include/pokemon_move_history.h"
#include "../../include/pokemon_storage_system.h"
#include "../../include/save.h"
#include "../../include/summary.h"
#include "../../include/window.h"
#include "../../include/constants/moves.h"
#include "../../include/constants/species.h"

#define SUMMARY_RETAIL_SIZE              0x7D8
#define SUMMARY_RELEARN_STATE_SIZE       0x0C0
#define SUMMARY_PAGE_MODE_OFFSET         0x7BC
#define SUMMARY_MOVE_CURSOR_OFFSET       0x7BD
#define SUMMARY_TRANSITION_OFFSET        0x7BF
#define SUMMARY_MSG_DATA_OFFSET          0x7A0
#define SUMMARY_STRING_OFFSET            0x7AC

#define SUMMARY_MOVE_PAGE                1
#define SUMMARY_PARTY_DATA               1
#define SUMMARY_PARTY_CAPACITY           6
#define SUMMARY_BOX_DATA                 2
#define SUMMARY_NORMAL_MODE              0
#define SUMMARY_VISIBLE_CANDIDATES       4
#define SUMMARY_SHARED_TILE_WINDOW       16
#define SUMMARY_PROMPT_WINDOW            17
#define SUMMARY_PROSPECTIVE_WINDOW       12

#define SUMMARY_MSG_RELEARN_PROMPT       208
#define SUMMARY_MSG_PICK_BACK            209
#define SUMMARY_MSG_NO_MOVES             210
#define SUMMARY_MSG_PICK_SLOT            211
#define SUMMARY_MSG_CONFIRM              212
#define SUMMARY_MSG_SUCCESS              213

#define PAD_BUTTON_A                     0x0001
#define PAD_BUTTON_B                     0x0002
#define PAD_KEY_RIGHT                    0x0010
#define PAD_KEY_LEFT                     0x0020
#define PAD_KEY_UP                       0x0040
#define PAD_KEY_DOWN                     0x0080
#define PAD_BUTTON_X                     0x0400

#define SUMMARY_SELECT_SE                0x069B
#define SUMMARY_TEXT_COLOR               0x00010200

enum SummaryMoveRelearnMode {
    SUMMARY_RELEARN_INACTIVE,
    SUMMARY_RELEARN_LIST,
    SUMMARY_RELEARN_EMPTY,
    SUMMARY_RELEARN_SLOT,
    SUMMARY_RELEARN_CONFIRM,
    SUMMARY_RELEARN_HM_BLOCKED,
    SUMMARY_RELEARN_SUCCESS,
};

struct SummaryMoveRelearnState {
    struct SummaryBaseData *ownerArgs;
    u16 candidates[POKEMON_MOVE_RELEARN_MAX_CANDIDATES];
    u16 originalMoves[4];
    u8 originalCurPP[4];
    u8 originalMaxPP[4];
    u16 candidateCount;
    u16 candidateCursor;
    u16 candidateTop;
    u16 pendingMove;
    u16 originalArgMove;
    u8 ownerPos;
    u8 selectedSlot;
    u8 originalCursor;
    u8 mode;
    u8 promptVisible;
    u8 resumeAfterSwitch;
    struct BoxPokemon *ownerPokemon;
};

struct SummaryTouchRect {
    u8 top;
    u8 bottom;
    u8 left;
    u8 right;
};

static const struct SummaryTouchRect sMoveRowTouchRects[] = {
    { 8, 39, 8, 127 },
    { 40, 71, 8, 127 },
    { 72, 103, 8, 127 },
    { 104, 135, 8, 127 },
    { 0xFF, 0, 0, 0 },
};

static const struct SummaryTouchRect sPromptTouchRects[] = {
    { 136, 151, 8, 87 },
    { 0xFF, 0, 0, 0 },
};

static const struct SummaryTouchRect sActionTouchRects[] = {
    { 136, 151, 8, 41 },
    { 136, 151, 45, 128 },
    { 165, 188, 190, 249 },
    { 0xFF, 0, 0, 0 },
};

static const struct SummaryTouchRect sBackTouchRects[] = {
    { 136, 151, 40, 128 },
    { 165, 188, 190, 249 },
    { 0xFF, 0, 0, 0 },
};

static const struct SummaryTouchRect sConfirmTouchRects[] = {
    { 136, 151, 8, 32 },
    { 136, 151, 36, 128 },
    { 165, 188, 190, 249 },
    { 0xFF, 0, 0, 0 },
};

typedef char SummaryMoveRelearnStateFits[
    sizeof(struct SummaryMoveRelearnState) <= SUMMARY_RELEARN_STATE_SIZE
        ? 1 : -1];

extern u32 LONG_CALL Summary_VanillaMainState(
    struct SummaryState *summary);
extern void LONG_CALL Summary_RefreshPokemonData(
    struct SummaryState *summary);
extern void LONG_CALL Summary_UpdateMoveSelection(
    struct SummaryState *summary);
extern void LONG_CALL Summary_UpdateMoveCursorSprite(
    struct SummaryState *summary);
extern void LONG_CALL Summary_RebuildMoveCategoryIcons(
    struct SummaryState *summary);
extern void LONG_CALL Summary_DrawMoveRows(
    struct SummaryState *summary);
extern void LONG_CALL Summary_ClearMoveDetailWindows(
    struct SummaryState *summary);
extern void LONG_CALL Summary_ShowHmBlockedMessage(
    struct SummaryState *summary);
extern int LONG_CALL Summary_GetPokemonSwitchTouch(void);
extern u32 LONG_CALL Summary_GetTouchAction(
    struct SummaryState *summary);
extern int LONG_CALL TouchscreenHitbox_FindRectAtTouchNew(
    const void *hitboxes);
extern void LONG_CALL ClearWindowTilemapAndScheduleTransfer(
    struct Window *window);
extern void LONG_CALL ScheduleSetBgPosText(
    void *bgConfig,
    u32 bgId,
    u32 op,
    s32 value);
extern void LONG_CALL PlaySE(u32 sequence);

static struct SummaryMoveRelearnState *SummaryMoveRelearn_GetState(
    struct SummaryState *summary)
{
    return (struct SummaryMoveRelearnState *)(
        (u8 *)summary + SUMMARY_RETAIL_SIZE);
}

static u32 SummaryMoveRelearn_GetNewKeys(void)
{
    return *(volatile u32 *)(0x021D110C + 0x48);
}

static u32 SummaryMoveRelearn_GetRepeatKeys(void)
{
    return *(volatile u32 *)(0x021D110C + 0x4C);
}

static s8 SummaryMoveRelearn_GetPage(
    struct SummaryState *summary)
{
    return *(s8 *)((u8 *)summary + SUMMARY_PAGE_MODE_OFFSET);
}

static u8 SummaryMoveRelearn_GetCursor(
    struct SummaryState *summary)
{
    return *(u8 *)((u8 *)summary + SUMMARY_MOVE_CURSOR_OFFSET);
}

static void SummaryMoveRelearn_SetCursor(
    struct SummaryState *summary,
    u8 slot)
{
    u8 *cursor = (u8 *)summary + SUMMARY_MOVE_CURSOR_OFFSET;

    *cursor = (*cursor & 0xF0) | (slot & 0x0F);
}

static BOOL SummaryMoveRelearn_IsStable(
    struct SummaryState *summary)
{
    return (*(u8 *)((u8 *)summary + SUMMARY_TRANSITION_OFFSET) & 0xF0) == 0;
}

static struct BoxPokemon *SummaryMoveRelearn_GetCurrentBoxMon(
    struct SummaryState *summary)
{
    int count;
    u32 limit;
    void *pokemon;
    struct Party *party;
    u32 pos;

    if (summary == NULL || summary->baseData == NULL
        || summary->baseData->ppd == NULL) {
        return NULL;
    }
    pos = summary->baseData->pos;
    limit = summary->baseData->limit;
    if (summary->baseData->dataType == SUMMARY_PARTY_DATA) {
        party = (struct Party *)summary->baseData->ppd;
        count = Party_GetCount(party);
        if (count < 1
            || count > SUMMARY_PARTY_CAPACITY
            || limit < 1
            || limit > SUMMARY_PARTY_CAPACITY
            || pos >= (u32)count
            || pos >= limit
            || pos >= SUMMARY_PARTY_CAPACITY) {
            return NULL;
        }
        pokemon = Summary_GetPokemonData(summary);
        if (pokemon == NULL) {
            return NULL;
        }
        return &((struct PartyPokemon *)pokemon)->box;
    }
    if (summary->baseData->dataType != SUMMARY_BOX_DATA
        || summary->baseData->limit != MONS_PER_BOX
        || pos >= MONS_PER_BOX) {
        return NULL;
    }
    return (struct BoxPokemon *)Summary_GetPokemonData(summary);
}

static BOOL SummaryMoveRelearn_IsValidEntryPokemon(
    struct BoxPokemon *pokemon)
{
    return PokemonMoveHistoryTask6_IsCanonical(pokemon);
}

static BOOL SummaryMoveRelearn_AllowPersistentFormMove(
    struct BoxPokemon *pokemon,
    u16 move,
    void *context)
{
    u32 form;
    u32 species;

    (void)context;
    species = GetBoxMonData(pokemon, MON_DATA_SPECIES, NULL);
    form = GetBoxMonData(pokemon, MON_DATA_FORM, NULL);
    if (species == SPECIES_ROTOM) {
        if (form == 0) {
            return move == MOVE_THUNDER_SHOCK;
        }
        if (form == 1) {
            return move == MOVE_OVERHEAT;
        }
        if (form == 2) {
            return move == MOVE_HYDRO_PUMP;
        }
        if (form == 3) {
            return move == MOVE_BLIZZARD;
        }
        if (form == 4) {
            return move == MOVE_AIR_SLASH;
        }
        if (form == 5) {
            return move == MOVE_LEAF_STORM;
        }
        return FALSE;
    }
    if (species == SPECIES_KYUREM) {
        if (form == 0) {
            return move == MOVE_GLACIATE || move == MOVE_SCARY_FACE;
        }
        if (form == 1) {
            return move == MOVE_ICE_BURN || move == MOVE_FUSION_FLARE;
        }
        if (form == 2) {
            return move == MOVE_FREEZE_SHOCK || move == MOVE_FUSION_BOLT;
        }
    }
    return FALSE;
}

static void SummaryMoveRelearn_HideStatus(
    struct SummaryState *summary);

static void SummaryMoveRelearn_RejectEntry(
    struct SummaryState *summary,
    struct SummaryMoveRelearnState *state)
{
    if (state->promptVisible) {
        SummaryMoveRelearn_HideStatus(summary);
    }
    state->candidateCount = 0;
    state->pendingMove = 0;
    state->promptVisible = FALSE;
    state->resumeAfterSwitch = FALSE;
    state->ownerPokemon = NULL;
}

static void SummaryMoveRelearn_PrintStatus(
    struct SummaryState *summary,
    u32 message)
{
    GF_BGL_BMPWIN *window;
    MsgData *msgData;
    String *string;

    if (summary->addlWindows == NULL
        || summary->addlWindowCount <= SUMMARY_PROMPT_WINDOW) {
        return;
    }
    window = &summary->addlWindows[SUMMARY_PROMPT_WINDOW];
    msgData = *(MsgData **)((u8 *)summary + SUMMARY_MSG_DATA_OFFSET);
    string = *(String **)((u8 *)summary + SUMMARY_STRING_OFFSET);
    if (msgData == NULL || string == NULL) {
        return;
    }
    /*
     * Retail windows 16 and 17 share char base 0x039D. Unmap window 16 before
     * drawing the prompt strip so the new glyphs cannot mirror over the page
     * selector at y=20.
     */
    ClearWindowTilemapAndScheduleTransfer(
        (struct Window *)&summary->addlWindows[SUMMARY_SHARED_TILE_WINDOW]);
    FillWindowPixelBuffer(window, 0);
    ReadMsgDataIntoString(msgData, message, string);
    AddTextPrinterParameterizedWithColor(
        window,
        0,
        string,
        0,
        0,
        0xFF,
        SUMMARY_TEXT_COLOR,
        NULL);
    ScheduleWindowCopyToVram((struct Window *)window);
}

static void SummaryMoveRelearn_HideStatus(
    struct SummaryState *summary)
{
    if (summary->addlWindows == NULL
        || summary->addlWindowCount <= SUMMARY_PROMPT_WINDOW) {
        return;
    }
    ClearWindowTilemapAndScheduleTransfer(
        (struct Window *)&summary->addlWindows[SUMMARY_SHARED_TILE_WINDOW]);
    ClearWindowTilemapAndScheduleTransfer(
        (struct Window *)&summary->addlWindows[SUMMARY_PROMPT_WINDOW]);
}

static int SummaryMoveRelearn_GetTouch(
    const struct SummaryTouchRect *rects)
{
    return TouchscreenHitbox_FindRectAtTouchNew(rects);
}

static void SummaryMoveRelearn_ClearProspective(
    struct SummaryState *summary)
{
    GF_BGL_BMPWIN *window;

    if (summary->addlWindows == NULL
        || summary->addlWindowCount <= SUMMARY_PROSPECTIVE_WINDOW) {
        return;
    }
    window = &summary->addlWindows[SUMMARY_PROSPECTIVE_WINDOW];
    FillWindowPixelBuffer(window, 0);
    ScheduleWindowCopyToVram((struct Window *)window);
}

static void SummaryMoveRelearn_SetMovePane(
    struct SummaryState *summary,
    BOOL visible)
{
    /*
     * Retail move selection exposes its prepared detail pane by setting
     * sub-screen BG5 X to 0x80. Reuse that presentation primitive without
     * borrowing retail's +0x7BE transition state or sprite lifecycle.
     */
    ScheduleSetBgPosText(summary->bgl, 5, 0, visible ? 0x80 : 0);
}

static void SummaryMoveRelearn_SaveCache(
    struct SummaryState *summary,
    struct SummaryMoveRelearnState *state)
{
    u32 i;

    for (i = 0; i < 4; i++) {
        state->originalMoves[i] = summary->pokemonData.moves[i];
        state->originalCurPP[i] = summary->pokemonData.curPP[i];
        state->originalMaxPP[i] = summary->pokemonData.maxPP[i];
    }
}

static void SummaryMoveRelearn_RestoreCache(
    struct SummaryState *summary,
    struct SummaryMoveRelearnState *state)
{
    u32 i;

    for (i = 0; i < 4; i++) {
        summary->pokemonData.moves[i] = state->originalMoves[i];
        summary->pokemonData.curPP[i] = state->originalCurPP[i];
        summary->pokemonData.maxPP[i] = state->originalMaxPP[i];
    }
}

static void SummaryMoveRelearn_RenderList(
    struct SummaryState *summary,
    struct SummaryMoveRelearnState *state)
{
    u32 i;
    u32 index;
    u16 move;
    u8 pp;

    for (i = 0; i < SUMMARY_VISIBLE_CANDIDATES; i++) {
        index = state->candidateTop + i;
        move = index < state->candidateCount
            ? state->candidates[index]
            : 0;
        pp = move != 0 ? (u8)GetMoveMaxPP(move, 0) : 0;
        summary->pokemonData.moves[i] = move;
        summary->pokemonData.curPP[i] = pp;
        summary->pokemonData.maxPP[i] = pp;
    }
    SummaryMoveRelearn_ClearProspective(summary);
    summary->baseData->move = 0;
    Summary_RebuildMoveCategoryIcons(summary);
    summary->baseData->move = state->originalArgMove;
    SummaryMoveRelearn_SetCursor(
        summary,
        (u8)(state->candidateCursor - state->candidateTop));
    Summary_UpdateMoveSelection(summary);
    /*
     * Selection updates own the detail pane and can consume the same cached
     * move data. Draw the rows last so their name and full-PP presentation is
     * authoritative for the completed frame.
     */
    Summary_DrawMoveRows(summary);
    SummaryMoveRelearn_PrintStatus(summary, SUMMARY_MSG_PICK_BACK);
}

static void SummaryMoveRelearn_RenderSlot(
    struct SummaryState *summary,
    struct SummaryMoveRelearnState *state)
{
    u8 pp;

    SummaryMoveRelearn_RestoreCache(summary, state);
    pp = (u8)GetMoveMaxPP(state->pendingMove, 0);
    summary->pokemonData.moves[state->selectedSlot] = state->pendingMove;
    summary->pokemonData.curPP[state->selectedSlot] = pp;
    summary->pokemonData.maxPP[state->selectedSlot] = pp;
    SummaryMoveRelearn_ClearProspective(summary);
    summary->baseData->move = 0;
    Summary_RebuildMoveCategoryIcons(summary);
    summary->baseData->move = state->originalArgMove;
    SummaryMoveRelearn_SetCursor(summary, state->selectedSlot);
    Summary_UpdateMoveSelection(summary);
    /*
     * Preview the resulting four-move set in place. The selected row carries
     * the pending name/full PP and the retail detail pane describes it, while
     * the canonical Pokémon remains untouched until confirmation.
     */
    Summary_DrawMoveRows(summary);
    SummaryMoveRelearn_PrintStatus(summary, SUMMARY_MSG_PICK_BACK);
}

static void SummaryMoveRelearn_End(
    struct SummaryState *summary,
    struct SummaryMoveRelearnState *state)
{
    SummaryMoveRelearn_RestoreCache(summary, state);
    summary->baseData->move = state->originalArgMove;
    Summary_DrawMoveRows(summary);
    SummaryMoveRelearn_ClearProspective(summary);
    summary->baseData->move = 0;
    Summary_RebuildMoveCategoryIcons(summary);
    summary->baseData->move = state->originalArgMove;
    SummaryMoveRelearn_SetCursor(summary, state->originalCursor);
    Summary_UpdateMoveCursorSprite(summary);
    Summary_ClearMoveDetailWindows(summary);
    state->mode = SUMMARY_RELEARN_INACTIVE;
    state->candidateCount = 0;
    SummaryMoveRelearn_PrintStatus(summary, SUMMARY_MSG_RELEARN_PROMPT);
    state->promptVisible = TRUE;
    SummaryMoveRelearn_SetMovePane(summary, FALSE);
}

static BOOL SummaryMoveRelearn_IsKnown(
    struct BoxPokemon *pokemon,
    u16 move)
{
    u32 i;

    for (i = 0; i < 4; i++) {
        if ((u16)GetBoxMonData(
                pokemon,
                MON_DATA_MOVE1 + i,
                NULL) == move) {
            return TRUE;
        }
    }
    return FALSE;
}

static BOOL SummaryMoveRelearn_IsCachedCandidate(
    struct SummaryMoveRelearnState *state,
    u16 move)
{
    u32 i;

    for (i = 0; i < state->candidateCount; i++) {
        if (state->candidates[i] == move) {
            return TRUE;
        }
    }
    return FALSE;
}

static void SummaryMoveRelearn_Enter(
    struct SummaryState *summary,
    struct SummaryMoveRelearnState *state,
    struct BoxPokemon *pokemon)
{
    static const PokemonMoveRelearnOptions options = {
        SummaryMoveRelearn_AllowPersistentFormMove,
        NULL,
    };
    u32 count;

    state->ownerArgs = summary->baseData;
    state->ownerPokemon = pokemon;
    state->ownerPos = summary->baseData->pos;
    state->originalCursor =
        SummaryMoveRelearn_GetCursor(summary) & 0x0F;
    state->originalArgMove = summary->baseData->move;
    state->candidateCursor = 0;
    state->candidateTop = 0;
    state->selectedSlot = 0;
    state->pendingMove = 0;
    state->resumeAfterSwitch = FALSE;
    SummaryMoveRelearn_SaveCache(summary, state);

    count = PokemonMoveRelearn_BuildCandidates(
        SaveBlock2_get(),
        pokemon,
        state->candidates,
        POKEMON_MOVE_RELEARN_MAX_CANDIDATES,
        &options);
    if (count > POKEMON_MOVE_RELEARN_MAX_CANDIDATES) {
        count = POKEMON_MOVE_RELEARN_MAX_CANDIDATES;
    }
    state->candidateCount = (u16)count;
    state->promptVisible = FALSE;
    if (state->candidateCount == 0) {
        state->mode = SUMMARY_RELEARN_EMPTY;
        SummaryMoveRelearn_PrintStatus(summary, SUMMARY_MSG_NO_MOVES);
        return;
    }
    state->mode = SUMMARY_RELEARN_LIST;
    SummaryMoveRelearn_SetMovePane(summary, TRUE);
    SummaryMoveRelearn_RenderList(summary, state);
}

static void SummaryMoveRelearn_MoveListCursor(
    struct SummaryState *summary,
    struct SummaryMoveRelearnState *state,
    BOOL down)
{
    if (down) {
        state->candidateCursor++;
        if (state->candidateCursor >= state->candidateCount) {
            state->candidateCursor = 0;
        }
    } else {
        state->candidateCursor =
            state->candidateCursor == 0
                ? state->candidateCount - 1
                : state->candidateCursor - 1;
    }
    if (state->candidateCursor < state->candidateTop) {
        state->candidateTop = state->candidateCursor;
    } else if (state->candidateCursor
        >= state->candidateTop + SUMMARY_VISIBLE_CANDIDATES) {
        state->candidateTop =
            state->candidateCursor - (SUMMARY_VISIBLE_CANDIDATES - 1);
    }
    if (state->candidateCursor == 0
        && state->candidateTop + SUMMARY_VISIBLE_CANDIDATES
            < state->candidateCount) {
        state->candidateTop = 0;
    }
    PlaySE(SUMMARY_SELECT_SE);
    SummaryMoveRelearn_RenderList(summary, state);
}

static void SummaryMoveRelearn_HandleList(
    struct SummaryState *summary,
    struct SummaryMoveRelearnState *state,
    u32 newKeys,
    u32 repeatKeys)
{
    int touch;

    touch = SummaryMoveRelearn_GetTouch(sMoveRowTouchRects);
    if (touch >= 0
        && touch < SUMMARY_VISIBLE_CANDIDATES
        && state->candidateTop + touch < state->candidateCount) {
        state->candidateCursor = state->candidateTop + touch;
        newKeys |= PAD_BUTTON_A;
    } else {
        touch = SummaryMoveRelearn_GetTouch(sActionTouchRects);
        if (touch == 0) {
            newKeys |= PAD_BUTTON_A;
        } else if (touch == 1 || touch == 2) {
            newKeys |= PAD_BUTTON_B;
        }
    }
    if (newKeys & PAD_BUTTON_B) {
        SummaryMoveRelearn_End(summary, state);
    } else if (repeatKeys & PAD_KEY_UP) {
        SummaryMoveRelearn_MoveListCursor(summary, state, FALSE);
    } else if (repeatKeys & PAD_KEY_DOWN) {
        SummaryMoveRelearn_MoveListCursor(summary, state, TRUE);
    } else if (newKeys & PAD_BUTTON_A) {
        PlaySE(SUMMARY_SELECT_SE);
        state->pendingMove = state->candidates[state->candidateCursor];
        state->selectedSlot = 0;
        state->mode = SUMMARY_RELEARN_SLOT;
        SummaryMoveRelearn_RenderSlot(summary, state);
    }
}

static void SummaryMoveRelearn_HandleSlot(
    struct SummaryState *summary,
    struct SummaryMoveRelearnState *state,
    struct BoxPokemon *pokemon,
    u32 newKeys,
    u32 repeatKeys)
{
    u16 oldMove;
    int touch;

    touch = SummaryMoveRelearn_GetTouch(sMoveRowTouchRects);
    if (touch >= 0 && touch < 4) {
        state->selectedSlot = (u8)touch;
        newKeys |= PAD_BUTTON_A;
    } else {
        touch = SummaryMoveRelearn_GetTouch(sActionTouchRects);
        if (touch == 0) {
            newKeys |= PAD_BUTTON_A;
        } else if (touch == 1 || touch == 2) {
            newKeys |= PAD_BUTTON_B;
        }
    }
    if (newKeys & PAD_BUTTON_B) {
        state->mode = SUMMARY_RELEARN_LIST;
        SummaryMoveRelearn_RenderList(summary, state);
    } else if (repeatKeys & PAD_KEY_UP) {
        state->selectedSlot =
            state->selectedSlot == 0 ? 3 : state->selectedSlot - 1;
        PlaySE(SUMMARY_SELECT_SE);
        SummaryMoveRelearn_RenderSlot(summary, state);
    } else if (repeatKeys & PAD_KEY_DOWN) {
        state->selectedSlot = (state->selectedSlot + 1) & 3;
        PlaySE(SUMMARY_SELECT_SE);
        SummaryMoveRelearn_RenderSlot(summary, state);
    } else if (newKeys & PAD_BUTTON_A) {
        /*
         * A row touch selects and activates in the same frame. Refresh the
         * inline preview before entering confirmation so that row is the
         * prospective move the player is confirming.
         */
        SummaryMoveRelearn_RenderSlot(summary, state);
        oldMove = (u16)GetBoxMonData(
            pokemon,
            MON_DATA_MOVE1 + state->selectedSlot,
            NULL);
        if (oldMove == state->pendingMove) {
            SummaryMoveRelearn_RenderSlot(summary, state);
        } else if (oldMove != 0 && MoveIsHM(oldMove)) {
            state->mode = SUMMARY_RELEARN_HM_BLOCKED;
            Summary_ShowHmBlockedMessage(summary);
            SummaryMoveRelearn_PrintStatus(summary, SUMMARY_MSG_CONFIRM);
        } else {
            state->mode = SUMMARY_RELEARN_CONFIRM;
            SummaryMoveRelearn_PrintStatus(summary, SUMMARY_MSG_CONFIRM);
        }
    }
}

static void SummaryMoveRelearn_Commit(
    struct SummaryState *summary,
    struct SummaryMoveRelearnState *state,
    struct BoxPokemon *pokemon)
{
    u16 oldMove;

    oldMove = (u16)GetBoxMonData(
        pokemon,
        MON_DATA_MOVE1 + state->selectedSlot,
        NULL);
    if (!SummaryMoveRelearn_IsCachedCandidate(state, state->pendingMove)
        || SummaryMoveRelearn_IsKnown(pokemon, state->pendingMove)
        || oldMove == state->pendingMove
        || (oldMove != 0 && MoveIsHM(oldMove))
        || !PokemonMoveHistory_ReplaceMove(
            pokemon,
            state->pendingMove,
            state->selectedSlot)) {
        state->mode = SUMMARY_RELEARN_SLOT;
        SummaryMoveRelearn_RenderSlot(summary, state);
        return;
    }

    /*
     * This is Summary's canonical ownership signal. The parent field/app
     * path observes it after Summary exits; the UI never writes a save.
     */
    summary->baseData->pokemonChanged = TRUE;
    Summary_RefreshPokemonData(summary);
    SummaryMoveRelearn_SaveCache(summary, state);
    summary->baseData->move = state->originalArgMove;
    Summary_DrawMoveRows(summary);
    SummaryMoveRelearn_ClearProspective(summary);
    summary->baseData->move = 0;
    Summary_RebuildMoveCategoryIcons(summary);
    summary->baseData->move = state->originalArgMove;
    SummaryMoveRelearn_SetCursor(summary, state->selectedSlot);
    Summary_UpdateMoveSelection(summary);
    state->mode = SUMMARY_RELEARN_SUCCESS;
    SummaryMoveRelearn_PrintStatus(summary, SUMMARY_MSG_SUCCESS);
}

static void SummaryMoveRelearn_CancelForNavigation(
    struct SummaryState *summary,
    struct SummaryMoveRelearnState *state,
    BOOL resumeAfterSwitch)
{
    if (state->ownerArgs == summary->baseData
        && state->ownerPos == summary->baseData->pos
        && state->ownerPokemon
            == SummaryMoveRelearn_GetCurrentBoxMon(summary)) {
        SummaryMoveRelearn_RestoreCache(summary, state);
        summary->baseData->move = state->originalArgMove;
    }
    SummaryMoveRelearn_HideStatus(summary);
    SummaryMoveRelearn_ClearProspective(summary);
    SummaryMoveRelearn_SetMovePane(summary, FALSE);
    Summary_ClearMoveDetailWindows(summary);
    state->mode = SUMMARY_RELEARN_INACTIVE;
    state->candidateCount = 0;
    state->pendingMove = 0;
    state->promptVisible = FALSE;
    state->resumeAfterSwitch = resumeAfterSwitch;
    state->ownerPokemon = NULL;
}

static BOOL SummaryMoveRelearn_OwnsCurrentTouch(
    struct SummaryState *summary,
    struct SummaryMoveRelearnState *state)
{
    int touch;

    if (state->mode == SUMMARY_RELEARN_LIST
        || state->mode == SUMMARY_RELEARN_SLOT) {
        return SummaryMoveRelearn_GetTouch(sMoveRowTouchRects) >= 0
            || SummaryMoveRelearn_GetTouch(sActionTouchRects) >= 0;
    }
    if (state->mode == SUMMARY_RELEARN_EMPTY) {
        return SummaryMoveRelearn_GetTouch(sBackTouchRects) >= 0;
    }
    touch = SummaryMoveRelearn_GetTouch(sConfirmTouchRects);
    if (state->mode == SUMMARY_RELEARN_SUCCESS) {
        return touch == 2;
    }
    return touch >= 0;
}

u32 SummaryMoveRelearn_MainState(
    struct SummaryState *summary)
{
    struct SummaryMoveRelearnState *state;
    struct BoxPokemon *pokemon;
    u32 newKeys;
    u32 repeatKeys;
    u32 vanillaState;
    BOOL sameOwnerArgs;
    u32 touchAction;
    int switchTouch;
    int touch;

    state = SummaryMoveRelearn_GetState(summary);
    pokemon = SummaryMoveRelearn_GetCurrentBoxMon(summary);
    sameOwnerArgs = state->ownerArgs == summary->baseData;
    if (state->mode != SUMMARY_RELEARN_INACTIVE
        && (!sameOwnerArgs
            || summary->baseData == NULL
            || state->ownerPos != summary->baseData->pos
            || state->ownerPokemon != pokemon
            || pokemon == NULL)) {
        u16 restoreMove;

        /*
         * args->move belongs to the args object, not the overlay position.
         * A position boundary on the same object restores our temporary
         * value; an identity boundary must preserve the new owner's value.
         */
        if (sameOwnerArgs && summary->baseData != NULL) {
            summary->baseData->move = state->originalArgMove;
        }
        state->mode = SUMMARY_RELEARN_INACTIVE;
        state->candidateCount = 0;
        state->promptVisible = FALSE;
        state->resumeAfterSwitch = FALSE;
        state->ownerPokemon = NULL;
        SummaryMoveRelearn_HideStatus(summary);
        SummaryMoveRelearn_ClearProspective(summary);
        if (pokemon != NULL && summary->baseData != NULL) {
            restoreMove = summary->baseData->move;
            Summary_RefreshPokemonData(summary);
            Summary_DrawMoveRows(summary);
            summary->baseData->move = 0;
            Summary_RebuildMoveCategoryIcons(summary);
            summary->baseData->move = restoreMove;
            SummaryMoveRelearn_SetCursor(summary, 0);
            Summary_UpdateMoveCursorSprite(summary);
            Summary_ClearMoveDetailWindows(summary);
        }
        SummaryMoveRelearn_SetMovePane(summary, FALSE);
    }

    if (state->mode == SUMMARY_RELEARN_INACTIVE) {
        if (pokemon == NULL) {
            SummaryMoveRelearn_RejectEntry(summary, state);
            return 2;
        }
        if (summary->baseData->mode != SUMMARY_NORMAL_MODE
            || SummaryMoveRelearn_GetPage(summary) != SUMMARY_MOVE_PAGE
            || !SummaryMoveRelearn_IsStable(summary)
            || GetBoxMonData(
                pokemon,
                MON_DATA_CHECKSUM_FAILED,
                NULL)
            || !GetBoxMonData(
                pokemon,
                MON_DATA_SPECIES_EXISTS,
                NULL)
            || GetBoxMonData(pokemon, MON_DATA_IS_EGG, NULL)) {
            state->resumeAfterSwitch = FALSE;
            if (state->promptVisible) {
                SummaryMoveRelearn_HideStatus(summary);
            }
            state->promptVisible = FALSE;
            return Summary_VanillaMainState(summary);
        }
        if (!state->promptVisible
            && !PokemonMoveHistoryTask6_IsCanonical(pokemon)) {
            state->resumeAfterSwitch = FALSE;
            return Summary_VanillaMainState(summary);
        }
        if (state->resumeAfterSwitch) {
            if (!SummaryMoveRelearn_IsValidEntryPokemon(pokemon)) {
                SummaryMoveRelearn_RejectEntry(summary, state);
                return 2;
            }
            SummaryMoveRelearn_Enter(summary, state, pokemon);
            return 2;
        }
        if (!state->promptVisible) {
            SummaryMoveRelearn_PrintStatus(
                summary,
                SUMMARY_MSG_RELEARN_PROMPT);
            state->promptVisible = TRUE;
        }
        newKeys = SummaryMoveRelearn_GetNewKeys();
        if (SummaryMoveRelearn_GetTouch(sPromptTouchRects) == 0) {
            newKeys |= PAD_BUTTON_X;
        }
        if (newKeys & PAD_BUTTON_X) {
            if (!SummaryMoveRelearn_IsValidEntryPokemon(pokemon)) {
                SummaryMoveRelearn_RejectEntry(summary, state);
                return 2;
            }
            PlaySE(SUMMARY_SELECT_SE);
            SummaryMoveRelearn_Enter(summary, state, pokemon);
            return 2;
        }
        vanillaState = Summary_VanillaMainState(summary);
        if (vanillaState != 2) {
            state->promptVisible = FALSE;
        }
        return vanillaState;
    }

    newKeys = SummaryMoveRelearn_GetNewKeys();
    repeatKeys = SummaryMoveRelearn_GetRepeatKeys();
    if (!SummaryMoveRelearn_OwnsCurrentTouch(summary, state)) {
        touchAction = Summary_GetTouchAction(summary);
        switchTouch = summary->baseData->dataType == SUMMARY_BOX_DATA
            ? Summary_GetPokemonSwitchTouch()
            : -1;
        if ((repeatKeys & (PAD_KEY_LEFT | PAD_KEY_RIGHT))
            || touchAction <= 9
            || switchTouch == 0
            || switchTouch == 1) {
            BOOL resumeAfterSwitch =
                (touchAction >= 4 && touchAction <= 9)
                || switchTouch == 0
                || switchTouch == 1;

            SummaryMoveRelearn_CancelForNavigation(
                summary,
                state,
                resumeAfterSwitch);
            return Summary_VanillaMainState(summary);
        }
    }
    if (state->mode == SUMMARY_RELEARN_LIST) {
        SummaryMoveRelearn_HandleList(
            summary,
            state,
            newKeys,
            repeatKeys);
    } else if (state->mode == SUMMARY_RELEARN_EMPTY) {
        touch = SummaryMoveRelearn_GetTouch(sBackTouchRects);
        if (touch == 0 || touch == 1) {
            newKeys |= PAD_BUTTON_B;
        }
        if (newKeys & (PAD_BUTTON_A | PAD_BUTTON_B)) {
            SummaryMoveRelearn_End(summary, state);
        }
    } else if (state->mode == SUMMARY_RELEARN_SLOT) {
        SummaryMoveRelearn_HandleSlot(
            summary,
            state,
            pokemon,
            newKeys,
            repeatKeys);
    } else if (state->mode == SUMMARY_RELEARN_CONFIRM) {
        touch = SummaryMoveRelearn_GetTouch(sConfirmTouchRects);
        if (touch == 0) {
            newKeys |= PAD_BUTTON_A;
        } else if (touch == 1 || touch == 2) {
            newKeys |= PAD_BUTTON_B;
        }
        if (newKeys & PAD_BUTTON_B) {
            state->mode = SUMMARY_RELEARN_SLOT;
            SummaryMoveRelearn_RenderSlot(summary, state);
        } else if (newKeys & PAD_BUTTON_A) {
            SummaryMoveRelearn_Commit(summary, state, pokemon);
        }
    } else if (state->mode == SUMMARY_RELEARN_HM_BLOCKED) {
        touch = SummaryMoveRelearn_GetTouch(sConfirmTouchRects);
        if (touch == 0) {
            newKeys |= PAD_BUTTON_A;
        } else if (touch == 1 || touch == 2) {
            newKeys |= PAD_BUTTON_B;
        }
        if (newKeys & (PAD_BUTTON_A | PAD_BUTTON_B)) {
            state->mode = SUMMARY_RELEARN_SLOT;
            SummaryMoveRelearn_RenderSlot(summary, state);
        }
    } else if (state->mode == SUMMARY_RELEARN_SUCCESS) {
        touch = SummaryMoveRelearn_GetTouch(sConfirmTouchRects);
        if (touch == 2) {
            newKeys |= PAD_BUTTON_B;
        }
        if (newKeys & (PAD_BUTTON_A | PAD_BUTTON_B)) {
            SummaryMoveRelearn_End(summary, state);
        }
    } else {
        SummaryMoveRelearn_SetMovePane(summary, FALSE);
        state->mode = SUMMARY_RELEARN_INACTIVE;
        state->promptVisible = FALSE;
    }
    return 2;
}
