#include "../include/types.h"
#include "../include/config.h"
#include "../include/overworld_wild_spawns.h"
#include "../include/script.h"
#include "../include/sound.h"
#include "../include/repel.h"
#include "../include/constants/file.h"
#include "../include/constants/sndseq.h"
#include "../include/constants/species.h"

#define SCRIPT_NEW_CMD_REPEL_USE    0
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE 1
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE_CLEANUP 2
#define SCRIPT_NEW_CMD_SOUND_TEST_GET_ID 4
#define SCRIPT_NEW_CMD_SOUND_TEST_ACTION 5

#define SCRIPT_NEW_CMD_MAX          256
#define SOUND_TEST_SE_MIN           SEQ_SE_PL_W012
#define SOUND_TEST_SE_MAX           (SEQ_SE_END - 1)
#define SOUND_TEST_SE_COUNT         (SOUND_TEST_SE_MAX - SOUND_TEST_SE_MIN + 1)
#define SOUND_TEST_ACTION_PLAY      0
#define SOUND_TEST_ACTION_NEXT      1
#define SOUND_TEST_ACTION_PREVIOUS  2
#define SOUND_TEST_ACTION_FORWARD   3
#define SOUND_TEST_ACTION_BACK      4
#define VAR_BATTLE_RESULT           0x4013
#define SCRIPT_CMD_RUN_NEW_COMMAND  208
#define SCRIPT_CMD_RELEASE_ALL      97
#define SCRIPT_CMD_END              2
#define OW_WILD_BATTLE_SCRIPT_SPECIES_OFFSET 2
#define OW_WILD_BATTLE_SCRIPT_LEVEL_OFFSET 4
#define OW_WILD_BATTLE_SCRIPT_SHINY_OFFSET 6

static u8 sOverworldWildBattleScript[] = {
    0x4D, 0x02, // wild_battle
    0x13, 0x00, // species fallback: Rattata
    0x04, 0x00, // level fallback: 4
    0x00,       // shiny
    0xD0, 0x00, // RunNewCommand
    SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE_CLEANUP,
    0x00, 0x00,
    0x61, 0x00, // releaseall
    0x02, 0x00, // end
};

static u16 sSoundTestSeqId = SOUND_TEST_SE_MIN;

static void Script_WriteHalfword(u8 *script, u32 offset, u16 value)
{
    script[offset] = value & 0xFF;
    script[offset + 1] = value >> 8;
}

static void Script_QueueOverworldWildBattle(SCRIPTCONTEXT *ctx)
{
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
    u16 encodedSpecies = SPECIES_RATTATA;
    u8 level = 4;

    OverworldWildSpawns_PopPendingBattle(&encodedSpecies, &level);

    Script_WriteHalfword(sOverworldWildBattleScript, OW_WILD_BATTLE_SCRIPT_SPECIES_OFFSET, encodedSpecies);
    Script_WriteHalfword(sOverworldWildBattleScript, OW_WILD_BATTLE_SCRIPT_LEVEL_OFFSET, level);
    sOverworldWildBattleScript[OW_WILD_BATTLE_SCRIPT_SHINY_OFFSET] = 0;
    VarSet(ctx->fsys, VAR_BATTLE_RESULT, 0);
#endif

    ScriptJump(ctx, sOverworldWildBattleScript);
}

static void Script_SoundTestOffset(s16 offset)
{
    s32 nextSeqId = sSoundTestSeqId + offset;

    while (nextSeqId < SOUND_TEST_SE_MIN) {
        nextSeqId += SOUND_TEST_SE_COUNT;
    }

    while (nextSeqId > SOUND_TEST_SE_MAX) {
        nextSeqId -= SOUND_TEST_SE_COUNT;
    }

    sSoundTestSeqId = nextSeqId;
}

static void Script_SoundTestRunAction(u16 action)
{
    switch (action) {
        case SOUND_TEST_ACTION_PLAY:
            break;

        case SOUND_TEST_ACTION_NEXT:
            Script_SoundTestOffset(1);
            break;

        case SOUND_TEST_ACTION_PREVIOUS:
            Script_SoundTestOffset(-1);
            break;

        case SOUND_TEST_ACTION_FORWARD:
            Script_SoundTestOffset(10);
            break;

        case SOUND_TEST_ACTION_BACK:
            Script_SoundTestOffset(-10);
            break;

        default:
            return;
    }

    PlaySE(sSoundTestSeqId);
}

BOOL Script_RunNewCmd(SCRIPTCONTEXT *ctx) {
    u8 sw = ScriptReadByte(ctx);
    u16 UNUSED arg0 = ScriptReadHalfword(ctx);

    switch (sw) {
        case SCRIPT_NEW_CMD_REPEL_USE:;
#ifdef IMPLEMENT_REUSABLE_REPELS
            u16 most_recent_repel = Repel_GetMostRecent();
            SetScriptVar(arg0, most_recent_repel);
            Repel_Use(most_recent_repel, HEAPID_MAIN_HEAP);
#endif
            break;

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE:
            Script_QueueOverworldWildBattle(ctx);
            break;

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE_CLEANUP:
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
            OverworldWildSpawns_CleanupPendingBattle(VarGet(ctx->fsys, VAR_BATTLE_RESULT));
#endif
            break;

        case SCRIPT_NEW_CMD_SOUND_TEST_GET_ID:
            SetScriptVar(arg0, sSoundTestSeqId);
            break;

        case SCRIPT_NEW_CMD_SOUND_TEST_ACTION:
            Script_SoundTestRunAction(GetScriptVar(arg0));
            break;

        default: break;
    }

    return FALSE;
}
