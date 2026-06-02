#include "../include/types.h"
#include "../include/config.h"
#include "../include/overworld_wild_spawns.h"
#include "../include/script.h"
#include "../include/repel.h"
#include "../include/constants/file.h"
#include "../include/constants/maps.h"
#include "../include/constants/species.h"

#define SCRIPT_NEW_CMD_REPEL_USE    0
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE 1
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE_CLEANUP 2
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_MEW_WARP 3

#define SCRIPT_NEW_CMD_MAX          256
#define VAR_BATTLE_RESULT           0x4013
#define SCRIPT_CMD_FADE_SCREEN      174
#define SCRIPT_CMD_WAIT_FADE        175
#define SCRIPT_CMD_WARP             176
#define SCRIPT_CMD_RELEASE_ALL      97
#define SCRIPT_CMD_END              2
#define OW_WILD_MEW_WARP_NONE       0xFFFF
#define OW_WILD_MEW_WARP_DIR_SOUTH  1

typedef struct OverworldWildMewWarpDestination {
    u16 mapId;
    u16 warpId;
    u16 x;
    u16 z;
    u16 direction;
} OverworldWildMewWarpDestination;

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

static u8 sOverworldWildMewWarpScript[] = {
    SCRIPT_CMD_FADE_SCREEN & 0xFF, SCRIPT_CMD_FADE_SCREEN >> 8,
    0x06, 0x00,
    0x01, 0x00,
    0x00, 0x00,
    0x00, 0x00,
    SCRIPT_CMD_WAIT_FADE & 0xFF, SCRIPT_CMD_WAIT_FADE >> 8,
    SCRIPT_CMD_WARP & 0xFF, SCRIPT_CMD_WARP >> 8,
    MAP_T21PC0101 & 0xFF, MAP_T21PC0101 >> 8,
    OW_WILD_MEW_WARP_NONE & 0xFF, OW_WILD_MEW_WARP_NONE >> 8,
    0x07, 0x00,
    0x07, 0x00,
    OW_WILD_MEW_WARP_DIR_SOUTH & 0xFF, OW_WILD_MEW_WARP_DIR_SOUTH >> 8,
    SCRIPT_CMD_FADE_SCREEN & 0xFF, SCRIPT_CMD_FADE_SCREEN >> 8,
    0x06, 0x00,
    0x01, 0x00,
    0x01, 0x00,
    0x00, 0x00,
    SCRIPT_CMD_WAIT_FADE & 0xFF, SCRIPT_CMD_WAIT_FADE >> 8,
    SCRIPT_CMD_RELEASE_ALL & 0xFF, SCRIPT_CMD_RELEASE_ALL >> 8,
    SCRIPT_CMD_END & 0xFF, SCRIPT_CMD_END >> 8,
};

static const OverworldWildMewWarpDestination sOverworldWildMewWarpDestinations[] = {
    { MAP_T21PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T22PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T23PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T24PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T25PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T26PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T27PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T28PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T30PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T02PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T03PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T04PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T05PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T06PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T07PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T08PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
    { MAP_T09PC0101, OW_WILD_MEW_WARP_NONE, 7, 7, OW_WILD_MEW_WARP_DIR_SOUTH },
};

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

    sOverworldWildBattleScript[2] = encodedSpecies & 0xFF;
    sOverworldWildBattleScript[3] = encodedSpecies >> 8;
    sOverworldWildBattleScript[4] = level;
    sOverworldWildBattleScript[5] = 0;
    sOverworldWildBattleScript[6] = 0;
    VarSet(ctx->fsys, VAR_BATTLE_RESULT, 0);
#endif

    ScriptJump(ctx, sOverworldWildBattleScript);
}

static void Script_QueueOverworldWildMewWarp(SCRIPTCONTEXT *ctx)
{
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
    const OverworldWildMewWarpDestination *destination =
        &sOverworldWildMewWarpDestinations[gf_rand() % NELEMS(sOverworldWildMewWarpDestinations)];

    Script_WriteHalfword(sOverworldWildMewWarpScript, 14, destination->mapId);
    Script_WriteHalfword(sOverworldWildMewWarpScript, 16, destination->warpId);
    Script_WriteHalfword(sOverworldWildMewWarpScript, 18, destination->x);
    Script_WriteHalfword(sOverworldWildMewWarpScript, 20, destination->z);
    Script_WriteHalfword(sOverworldWildMewWarpScript, 22, destination->direction);
#endif

    ScriptJump(ctx, sOverworldWildMewWarpScript);
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

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_MEW_WARP:
            Script_QueueOverworldWildMewWarp(ctx);
            break;

        default: break;
    }

    return FALSE;
}
