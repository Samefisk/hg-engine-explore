#include "../include/types.h"
#include "../include/config.h"
#include "../include/overworld_wild_spawns.h"
#include "../include/script.h"
#include "../include/repel.h"
#include "../include/constants/file.h"
#include "../include/constants/species.h"

#define SCRIPT_NEW_CMD_REPEL_USE    0
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE 1
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE_CLEANUP 2

#define SCRIPT_NEW_CMD_MAX          256

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

static void Script_QueueOverworldWildBattle(SCRIPTCONTEXT *ctx)
{
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
    u16 encodedSpecies = SPECIES_RATTATA;
    u8 level = 4;

    OverworldWildSpawns_PopPendingBattle(&encodedSpecies, &level);

    sOverworldWildBattleScript[2] = encodedSpecies & 0xFF;
    sOverworldWildBattleScript[3] = encodedSpecies >> 8;
    sOverworldWildBattleScript[4] = level;
    sOverworldWildBattleScript[5] = 0;
#endif

    ScriptJump(ctx, sOverworldWildBattleScript);
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
            OverworldWildSpawns_CleanupPendingBattle();
#endif
            break;

        default: break;
    }

    return FALSE;
}
