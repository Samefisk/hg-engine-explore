#include "../../include/io_reg.h"
#include "../../include/message.h"
#include "../../include/pokemon.h"
#include "../../include/party_menu.h"
#include "../../include/save.h"
#include "../../include/sprite.h"
#include "../../include/type_mastery.h"
#include "../../include/window.h"
#include "../../include/constants/buttons.h"
#include "../../include/constants/file.h"
#include "../../include/constants/species.h"

#define TYPE_MASTERY_UI_MSG_BANK 854
#define TYPE_NAME_MSG_BANK       735

#define PARTY_MENU_ORIGINAL_INPUT_ADDR 0x0207ADB9
#define TRAINER_CARD_ORIGINAL_INPUT_ADDR 0x021E6B45

#define TRAINER_CARD_HEAP_ID       25
#define TRAINER_CARD_BG_ID          4
#define TRAINER_CARD_ARGS_OFFSET 0xE8
#define TRAINER_CARD_SAVE_OFFSET 0x670
#define TRAINER_CARD_MODAL_TILE_COUNT (30 * 23)
#define TRAINER_CARD_MODAL_TILE_SIZE  32
#define TRAINER_CARD_MODAL_CHAR_SIZE  (TRAINER_CARD_MODAL_TILE_COUNT * TRAINER_CARD_MODAL_TILE_SIZE)

#define PARTY_MENU_PANEL_BG_ID      6
#define PARTY_MENU_PANEL_BASE_TILE 0x50
#define PARTY_MENU_PANEL_PALETTE    2
#define PARTY_MENU_PANEL_MARKER     0xA5
#define TEXT_COLOR_BLACK           MAKE_TEXT_COLOR(1, 2, 15)
#define PRINTING_MODE_LEFT_ALIGN   0

typedef u8 (*PartyMenuInputFunc)(struct PartyMenu *partyMenu);
typedef u32 (*TrainerCardInputFunc)(void *work);

typedef struct TypeCommitmentRow {
    u8 type;
    u8 count;
} TypeCommitmentRow;

typedef struct PartyMasteryPanelState {
    struct Window window;
} PartyMasteryPanelState;

typedef struct TrainerCardMasteryModalState {
    void *owner;
    BOOL active;
    u8 page;
    u8 padding[3];
    struct Window window;
    u16 savedTilemap[32 * 24];
    void *savedCharData;
} TrainerCardMasteryModalState;

static PartyMasteryPanelState sPartyPanel;
static TrainerCardMasteryModalState sTrainerCardModal;

static u32 TypeMasteryUi_GetNewKeys(void)
{
    return *(volatile u32 *)0x021D1154;
}

static void TypeMasteryUi_PrintMessage(
    struct Window *window,
    MsgData *messages,
    String *string,
    u32 messageId,
    u8 fontId,
    u32 x,
    u32 y)
{
    ReadMsgDataIntoString(messages, messageId, string);
    AddTextPrinterParameterizedWithColor(
        window,
        fontId,
        string,
        x,
        y,
        0,
        TEXT_COLOR_BLACK,
        NULL);
}

static u8 TypeMasteryUi_CountPartyType(struct Party *party, u32 type)
{
    int count;
    int i;
    u8 matches = 0;

    if (party == NULL || !TypeMastery_IsValidType(type))
    {
        return 0;
    }

    count = party->count;
    if (count < 0)
    {
        count = 0;
    }
    else if (count > 6)
    {
        count = 6;
    }

    for (i = 0; i < count; i++)
    {
        struct PartyPokemon *mon = Party_GetMonByIndex(party, i);
        u32 type1;
        u32 type2;

        if (mon == NULL
            || GetMonData(mon, MON_DATA_SPECIES, NULL) == SPECIES_NONE
            || GetMonData(mon, MON_DATA_IS_EGG, NULL))
        {
            continue;
        }

        type1 = GetMonData(mon, MON_DATA_TYPE_1, NULL);
        type2 = GetMonData(mon, MON_DATA_TYPE_2, NULL);
        if (type1 == type || type2 == type)
        {
            matches++;
        }
    }

    return matches;
}

static int TypeMasteryUi_BuildCommitmentRows(
    struct Party *party,
    TypeCommitmentRow rows[6])
{
    int rowCount = 0;
    u32 type;

    for (type = 0; type < TYPE_MASTERY_TYPE_COUNT; type++)
    {
        u8 count = TypeMasteryUi_CountPartyType(party, type);
        int insertAt;

        if (count < 2)
        {
            continue;
        }

        insertAt = rowCount;
        while (insertAt > 0
            && (rows[insertAt - 1].count < count
                || (rows[insertAt - 1].count == count
                    && rows[insertAt - 1].type > type)))
        {
            rows[insertAt] = rows[insertAt - 1];
            insertAt--;
        }

        rows[insertAt].type = (u8)type;
        rows[insertAt].count = count;
        rowCount++;
    }

    return rowCount;
}

static void TypeMasteryUi_DrawPartyPanel(struct PartyMenu *partyMenu)
{
    TypeCommitmentRow rows[6];
    TypeMasterySaveData *mastery = TypeMastery_GetSaveData(SaveBlock2_get());
    struct Window *window = &sPartyPanel.window;
    MsgData *uiMessages;
    MsgData *typeNames;
    String *string;
    int rowCount;
    int i;

    memset(window, 0, sizeof(*window));
    AddWindowParameterized(
        partyMenu->bgConfig,
        window,
        PARTY_MENU_PANEL_BG_ID,
        1,
        5,
        30,
        18,
        PARTY_MENU_PANEL_PALETTE,
        PARTY_MENU_PANEL_BASE_TILE);
    FillWindowPixelBuffer(window, 15);

    uiMessages = NewMsgDataFromNarc(
        MSGDATA_LOAD_LAZY,
        ARC_MSG_DATA,
        TYPE_MASTERY_UI_MSG_BANK,
        HEAP_ID_PARTY_MENU);
    typeNames = NewMsgDataFromNarc(
        MSGDATA_LOAD_LAZY,
        ARC_MSG_DATA,
        TYPE_NAME_MSG_BANK,
        HEAP_ID_PARTY_MENU);
    string = String_New(64, HEAP_ID_PARTY_MENU);

    if (uiMessages != NULL && typeNames != NULL && string != NULL)
    {
        TypeMasteryUi_PrintMessage(window, uiMessages, string, 4, 4, 0, 0);
        TypeMasteryUi_PrintMessage(window, uiMessages, string, 5, 4, 0, 16);

        rowCount = TypeMasteryUi_BuildCommitmentRows(partyMenu->args->party, rows);
        if (rowCount == 0)
        {
            TypeMasteryUi_PrintMessage(window, uiMessages, string, 6, 4, 12, 48);
        }
        else
        {
            for (i = 0; i < rowCount; i++)
            {
                u32 y = 32 + (i * 16);
                u8 level = TypeMastery_GetTypeLevel(mastery, rows[i].type);
                u8 boon = TypeMastery_CalculateBoonLevel(level, rows[i].count);

                ReadMsgDataIntoString(typeNames, rows[i].type, string);
                AddTextPrinterParameterizedWithColor(
                    window, 4, string, 4, y, 0, TEXT_COLOR_BLACK, NULL);
                PrintUIntOnWindow(
                    partyMenu->msgPrinter,
                    rows[i].count,
                    1,
                    PRINTING_MODE_LEFT_ALIGN,
                    window,
                    142,
                    y);
                PrintUIntOnWindow(
                    partyMenu->msgPrinter,
                    level,
                    1,
                    PRINTING_MODE_LEFT_ALIGN,
                    window,
                    180,
                    y);
                PrintUIntOnWindow(
                    partyMenu->msgPrinter,
                    boon,
                    2,
                    PRINTING_MODE_LEFT_ALIGN,
                    window,
                    218,
                    y);
            }
        }

        TypeMasteryUi_PrintMessage(window, uiMessages, string, 7, 4, 92, 128);
    }

    if (string != NULL)
    {
        String_Delete(string);
    }
    if (typeNames != NULL)
    {
        DestroyMsgData(typeNames);
    }
    if (uiMessages != NULL)
    {
        DestroyMsgData(uiMessages);
    }

    CopyWindowToVram(window);
    reg_GXS_DB_DISPCNT |= (1 << 10);
}

u8 LONG_CALL TypeMastery_PartyMenuHandleInput(struct PartyMenu *partyMenu)
{
    if (partyMenu != NULL
        && partyMenu->args != NULL
        && partyMenu->args->context == PARTY_MENU_CONTEXT_0
        && partyMenu->filler_CA0[0] != PARTY_MENU_PANEL_MARKER)
    {
        TypeMasteryUi_DrawPartyPanel(partyMenu);
        partyMenu->filler_CA0[0] = PARTY_MENU_PANEL_MARKER;
    }

    return ((PartyMenuInputFunc)PARTY_MENU_ORIGINAL_INPUT_ADDR)(partyMenu);
}

static u32 TypeMasteryUi_GetNextLevelThreshold(u8 level)
{
    static const u32 sThresholds[TYPE_MASTERY_MAX_TYPE_LEVEL] = {
        TYPE_MASTERY_LEVEL_1_EXP,
        TYPE_MASTERY_LEVEL_2_EXP,
        TYPE_MASTERY_LEVEL_3_EXP,
        TYPE_MASTERY_LEVEL_4_EXP,
        TYPE_MASTERY_LEVEL_5_EXP,
    };

    if (level >= TYPE_MASTERY_MAX_TYPE_LEVEL)
    {
        return TYPE_MASTERY_LEVEL_5_EXP;
    }
    return sThresholds[level];
}

static void *TypeMasteryUi_GetTrainerCardSaveData(void *work)
{
    void *args;

    if (work == NULL)
    {
        return NULL;
    }

    args = *(void **)((u8 *)work + TRAINER_CARD_ARGS_OFFSET);
    if (args == NULL)
    {
        return NULL;
    }
    return *(void **)((u8 *)args + TRAINER_CARD_SAVE_OFFSET);
}

static void TypeMasteryUi_DrawTrainerCardPage(void *work)
{
    TypeMasterySaveData *mastery = TypeMastery_GetSaveData(
        TypeMasteryUi_GetTrainerCardSaveData(work));
    MsgData *uiMessages;
    MsgData *typeNames;
    MessageFormat *format;
    String *typeString;
    String *templateString;
    String *outputString;
    int i;

    FillWindowPixelBuffer(&sTrainerCardModal.window, 15);
    uiMessages = NewMsgDataFromNarc(
        MSGDATA_LOAD_LAZY,
        ARC_MSG_DATA,
        TYPE_MASTERY_UI_MSG_BANK,
        TRAINER_CARD_HEAP_ID);
    typeNames = NewMsgDataFromNarc(
        MSGDATA_LOAD_LAZY,
        ARC_MSG_DATA,
        TYPE_NAME_MSG_BANK,
        TRAINER_CARD_HEAP_ID);
    format = MessageFormat_New_Custom(4, 64, TRAINER_CARD_HEAP_ID);
    typeString = String_New(16, TRAINER_CARD_HEAP_ID);
    templateString = String_New(80, TRAINER_CARD_HEAP_ID);
    outputString = String_New(80, TRAINER_CARD_HEAP_ID);

    if (uiMessages != NULL
        && typeNames != NULL
        && format != NULL
        && typeString != NULL
        && templateString != NULL
        && outputString != NULL)
    {
        BufferIntegerAsString(
            format,
            0,
            sTrainerCardModal.page + 1,
            1,
            PRINTING_MODE_LEFT_ALIGN,
            FALSE);
        ReadMsgDataIntoString(uiMessages, 0, templateString);
        StringExpandPlaceholders(format, outputString, templateString);
        AddTextPrinterParameterizedWithColor(
            &sTrainerCardModal.window,
            0,
            outputString,
            8,
            4,
            0,
            TEXT_COLOR_BLACK,
            NULL);

        for (i = 0; i < 6; i++)
        {
            u32 type = (sTrainerCardModal.page * 6) + i;
            u32 exp = TypeMastery_GetExp(mastery, type);
            u8 level = TypeMastery_GetLevelFromExp(exp);

            ReadMsgDataIntoString(typeNames, type, typeString);
            SetStringAsPlaceholder(format, 0, typeString, NULL);
            if (level >= TYPE_MASTERY_MAX_TYPE_LEVEL)
            {
                ReadMsgDataIntoString(uiMessages, 2, templateString);
            }
            else
            {
                BufferIntegerAsString(
                    format, 1, level, 1, PRINTING_MODE_LEFT_ALIGN, FALSE);
                BufferIntegerAsString(
                    format, 2, exp, 6, PRINTING_MODE_LEFT_ALIGN, FALSE);
                BufferIntegerAsString(
                    format,
                    3,
                    TypeMasteryUi_GetNextLevelThreshold(level),
                    6,
                    PRINTING_MODE_LEFT_ALIGN,
                    FALSE);
                ReadMsgDataIntoString(uiMessages, 1, templateString);
            }
            StringExpandPlaceholders(format, outputString, templateString);
            AddTextPrinterParameterizedWithColor(
                &sTrainerCardModal.window,
                0,
                outputString,
                8,
                28 + (i * 22),
                0,
                TEXT_COLOR_BLACK,
                NULL);
        }

        TypeMasteryUi_PrintMessage(
            &sTrainerCardModal.window,
            uiMessages,
            outputString,
            3,
            0,
            40,
            164);
    }

    if (outputString != NULL)
    {
        String_Delete(outputString);
    }
    if (templateString != NULL)
    {
        String_Delete(templateString);
    }
    if (typeString != NULL)
    {
        String_Delete(typeString);
    }
    if (format != NULL)
    {
        MessageFormat_Delete(format);
    }
    if (typeNames != NULL)
    {
        DestroyMsgData(typeNames);
    }
    if (uiMessages != NULL)
    {
        DestroyMsgData(uiMessages);
    }

    CopyWindowToVram(&sTrainerCardModal.window);
    FillBgTilemapRect(
        sTrainerCardModal.window.bgConfig,
        TRAINER_CARD_BG_ID,
        0xF001,
        0,
        0,
        1,
        24,
        TILEMAP_FILL_OVWT_PAL);
    FillBgTilemapRect(
        sTrainerCardModal.window.bgConfig,
        TRAINER_CARD_BG_ID,
        0xF001,
        31,
        0,
        1,
        24,
        TILEMAP_FILL_OVWT_PAL);
    FillBgTilemapRect(
        sTrainerCardModal.window.bgConfig,
        TRAINER_CARD_BG_ID,
        0xF001,
        1,
        23,
        30,
        1,
        TILEMAP_FILL_OVWT_PAL);
    ScheduleBgTilemapBufferTransfer(
        sTrainerCardModal.window.bgConfig,
        TRAINER_CARD_BG_ID);
}

static void TypeMasteryUi_OpenTrainerCardModal(void *work)
{
    void *bgConfig;
    void *tilemap;
    u8 *charData;
    void *savedCharData;

    if (work == NULL)
    {
        return;
    }

    bgConfig = *(void **)work;
    if (bgConfig == NULL)
    {
        return;
    }
    tilemap = GetBgTilemapBuffer(bgConfig, TRAINER_CARD_BG_ID);
    charData = BgGetCharPtr(TRAINER_CARD_BG_ID);
    if (tilemap == NULL || charData == NULL)
    {
        return;
    }

    savedCharData = sys_AllocMemory(
        TRAINER_CARD_HEAP_ID,
        TRAINER_CARD_MODAL_CHAR_SIZE);
    if (savedCharData == NULL)
    {
        return;
    }

    memcpy(sTrainerCardModal.savedTilemap, tilemap, sizeof(sTrainerCardModal.savedTilemap));
    memcpy(
        savedCharData,
        charData + TRAINER_CARD_MODAL_TILE_SIZE,
        TRAINER_CARD_MODAL_CHAR_SIZE);
    memset(&sTrainerCardModal.window, 0, sizeof(sTrainerCardModal.window));
    sTrainerCardModal.savedCharData = savedCharData;
    sTrainerCardModal.owner = work;
    sTrainerCardModal.active = TRUE;
    sTrainerCardModal.page = 0;
    AddWindowParameterized(
        bgConfig,
        &sTrainerCardModal.window,
        TRAINER_CARD_BG_ID,
        1,
        0,
        30,
        23,
        15,
        1);
    TypeMasteryUi_DrawTrainerCardPage(work);
}

static void TypeMasteryUi_CloseTrainerCardModal(void)
{
    void *work = sTrainerCardModal.owner;
    void *bgConfig;
    void *tilemap;

    if (work != NULL)
    {
        bgConfig = *(void **)work;
        RemoveWindow(&sTrainerCardModal.window);
        if (sTrainerCardModal.savedCharData != NULL)
        {
            BG_LoadCharTilesData(
                bgConfig,
                TRAINER_CARD_BG_ID,
                sTrainerCardModal.savedCharData,
                TRAINER_CARD_MODAL_CHAR_SIZE,
                1);
        }
        tilemap = GetBgTilemapBuffer(bgConfig, TRAINER_CARD_BG_ID);
        if (tilemap != NULL)
        {
            memcpy(tilemap, sTrainerCardModal.savedTilemap, sizeof(sTrainerCardModal.savedTilemap));
            ScheduleBgTilemapBufferTransfer(bgConfig, TRAINER_CARD_BG_ID);
        }
    }

    if (sTrainerCardModal.savedCharData != NULL)
    {
        sys_FreeMemoryEz(sTrainerCardModal.savedCharData);
        sTrainerCardModal.savedCharData = NULL;
    }

    sTrainerCardModal.owner = NULL;
    sTrainerCardModal.active = FALSE;
}

u32 LONG_CALL TypeMastery_TrainerCardHandleInput(void *work)
{
    u32 newKeys = TypeMasteryUi_GetNewKeys();

    if (sTrainerCardModal.active)
    {
        if (sTrainerCardModal.owner != work)
        {
            if (sTrainerCardModal.savedCharData != NULL)
            {
                sys_FreeMemoryEz(sTrainerCardModal.savedCharData);
            }
            memset(&sTrainerCardModal, 0, sizeof(sTrainerCardModal));
        }
        else
        {
            if (newKeys & (PAD_BUTTON_X | PAD_BUTTON_B))
            {
                TypeMasteryUi_CloseTrainerCardModal();
            }
            else if (newKeys & PAD_BUTTON_L)
            {
                sTrainerCardModal.page = (sTrainerCardModal.page + 2) % 3;
                TypeMasteryUi_DrawTrainerCardPage(work);
            }
            else if (newKeys & PAD_BUTTON_R)
            {
                sTrainerCardModal.page = (sTrainerCardModal.page + 1) % 3;
                TypeMasteryUi_DrawTrainerCardPage(work);
            }
            return 0;
        }
    }

    if (work != NULL && (newKeys & PAD_BUTTON_X))
    {
        TypeMasteryUi_OpenTrainerCardModal(work);
        return 0;
    }

    return ((TrainerCardInputFunc)TRAINER_CARD_ORIGINAL_INPUT_ADDR)(work);
}
