#include "../include/types.h"
#include "../include/config.h"
#include "../include/overworld_wild_spawns_internal.h"
#include "../include/overworld_wild_spawns.h"
#include "../include/script.h"
#include "../include/repel.h"
#include "../include/constants/file.h"
#include "../include/constants/sndseq.h"
#include "../include/constants/species.h"
#include "../include/overlay.h"
#include "../include/sound.h"

#define SCRIPT_NEW_CMD_REPEL_USE    0
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE 1
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE_CLEANUP 2
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_SOUND_TESTER_BUFFER_NUMBERS 3
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_SOUND_TESTER_PLAY 4
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_SOUND_TESTER_ADJUST 5
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_SOUND_TESTER_CLOSE 6
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_VISUAL_TESTER 7

#define SCRIPT_NEW_CMD_MAX          256
#define VAR_SPECIAL_x8004           0x8004
#define VAR_SPECIAL_x8005           0x8005
#define VAR_SPECIAL_x8006           0x8006
#define SOUND_TESTER_SE_FIRST       SEQ_SE_PL_W012
#define SOUND_TESTER_SE_COUNT       (SEQ_SE_END - SOUND_TESTER_SE_FIRST)
#define SOUND_TESTER_INITIAL_SE     SEQ_SE_DP_SELECT
#define SCRIPTENV_BATTLE_WIN_FLAG   24

u8 gOverworldWildSoundTesterActive;
u8 gOverworldWildVisualTesterActive;
static u16 sSoundTesterSelection = SOUND_TESTER_INITIAL_SE - SOUND_TESTER_SE_FIRST;

static u16 SoundTesterGetSequence(void)
{
    return (u16)(SOUND_TESTER_SE_FIRST + sSoundTesterSelection);
}

static void SoundTesterAdjust(s16 delta)
{
    int selection = (int)sSoundTesterSelection + delta;

    while (selection < 0) {
        selection += SOUND_TESTER_SE_COUNT;
    }
    while (selection >= SOUND_TESTER_SE_COUNT) {
        selection -= SOUND_TESTER_SE_COUNT;
    }

    sSoundTesterSelection = (u16)selection;
}

static void SoundTesterPlay(void)
{
    u16 sequence = SoundTesterGetSequence();

    GF_Snd_LoadSeqEx(sequence, NNS_SND_ARC_LOAD_ALL);
    PlaySE(sequence);
}

static void Script_PrepareOverworldWildBattle(SCRIPTCONTEXT *ctx)
{
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
    u16 encodedSpecies;
    u8 level;
    BOOL shiny;

    if (!OverworldWildSpawns_PopPendingBattle(&encodedSpecies, &level, &shiny)) {
        VarSet(ctx->fsys, VAR_SPECIAL_x8004, SPECIES_NONE);
        VarSet(ctx->fsys, VAR_SPECIAL_x8005, 0);
        VarSet(ctx->fsys, VAR_SPECIAL_x8006, FALSE);
        return;
    }

    VarSet(ctx->fsys, VAR_SPECIAL_x8004, encodedSpecies);
    VarSet(ctx->fsys, VAR_SPECIAL_x8005, level);
    VarSet(ctx->fsys, VAR_SPECIAL_x8006, shiny ? TRUE : FALSE);

    /*
     * Overworld wild overlays share the high EWRAM overlay region with battle
     * extension overlays. Once the battle data has been copied into base
     * state/script vars, release them before WildBattleSp loads battle code.
     */
    UnloadOverlayByID(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION);
#else
    (void)ctx;
#endif
}

BOOL Script_RunNewCmd(SCRIPTCONTEXT *ctx) {
    u8 sw = ScriptReadByte(ctx);
    u16 arg0 = ScriptReadHalfword(ctx);

    switch (sw) {
        case SCRIPT_NEW_CMD_REPEL_USE:;
#ifdef IMPLEMENT_REUSABLE_REPELS
            u16 most_recent_repel = Repel_GetMostRecent();
            SetScriptVar(arg0, most_recent_repel);
            Repel_Use(most_recent_repel, HEAPID_MAIN_HEAP);
#endif
            break;

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE:
            Script_PrepareOverworldWildBattle(ctx);
            break;

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE_CLEANUP:
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
        {
            u32 *winFlag = FieldSysGetAttrAddr(ctx->fsys, SCRIPTENV_BATTLE_WIN_FLAG);

            OverworldWildSpawns_CleanupPendingBattle(ctx->fsys, (u16)*winFlag);
        }
#endif
            break;

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_SOUND_TESTER_BUFFER_NUMBERS:
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
            VarSet(ctx->fsys, VAR_SPECIAL_x8004, SoundTesterGetSequence());
#endif
            break;

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_SOUND_TESTER_PLAY:
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
            SoundTesterPlay();
#endif
            break;

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_SOUND_TESTER_ADJUST:
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
            SoundTesterAdjust((s16)arg0);
#endif
            break;

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_SOUND_TESTER_CLOSE:
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
            gOverworldWildSoundTesterActive = FALSE;
#endif
            break;

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_VISUAL_TESTER:
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
            OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->visualTesterCommand(ctx->fsys, arg0);
#endif
            break;

        default: break;
    }

    return FALSE;
}
