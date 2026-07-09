#include "../include/types.h"
#include "../include/config.h"
#include "../include/overworld_wild_spawns.h"
#include "../include/script.h"
#include "../include/repel.h"
#include "../include/overlay.h"
#include "../include/constants/file.h"
#include "../include/constants/species.h"

#define SCRIPT_NEW_CMD_REPEL_USE    0
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE 1
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE_CLEANUP 2

#define SCRIPT_NEW_CMD_MAX          256
#define VAR_SPECIAL_x8004           0x8004
#define VAR_SPECIAL_x8005           0x8005
#define VAR_SPECIAL_x8006           0x8006
#define SCRIPTENV_BATTLE_WIN_FLAG   24
#define OVERWORLD_WILD_SCRIPT_SPECIES_MASK 0x7FF

static void Script_PrepareOverworldWildBattle(SCRIPTCONTEXT *ctx)
{
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
    u32 pendingBattle;
    u16 species;
    u8 level;
    BOOL shiny;
    LocalMapObject *talkedObject = NULL;
    LocalMapObject **lastTalkedObject =
        (LocalMapObject **)GetEvScriptWorkMemberAdrs(ctx->fsys, SCRIPTENV_LAST_TALKED);

    if (lastTalkedObject != NULL) {
        talkedObject = *lastTalkedObject;
    }

    pendingBattle = OverworldWildSpawns_PopPendingBattle(
        ctx->fsys,
        talkedObject);
    if (pendingBattle == 0) {
        VarSet(ctx->fsys, VAR_SPECIAL_x8004, SPECIES_NONE);
        VarSet(ctx->fsys, VAR_SPECIAL_x8005, 0);
        VarSet(ctx->fsys, VAR_SPECIAL_x8006, FALSE);
        return;
    }

    species = (u16)(pendingBattle & OVERWORLD_WILD_SCRIPT_SPECIES_MASK);
    level = (u8)(pendingBattle >> OVERWORLD_WILD_PENDING_BATTLE_LEVEL_SHIFT);
    shiny = (pendingBattle >> OVERWORLD_WILD_PENDING_BATTLE_SHINY_SHIFT) & 1;

    VarSet(ctx->fsys, VAR_SPECIAL_x8004, species);
    VarSet(ctx->fsys, VAR_SPECIAL_x8005, level);
    VarSet(ctx->fsys, VAR_SPECIAL_x8006, shiny ? TRUE : FALSE);

    /*
     * Overlay 149/150/151 share the high EWRAM overlay region with battle
     * extension overlays. Once the battle data has been copied into base
     * state/script vars, release them before WildBattleSp loads battle code.
     */
    UnloadOverworldWildOverlays();

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

            OverworldWildSpawns_CleanupPendingBattle(ctx->fsys, *winFlag);
        }
#endif
            break;

        default: break;
    }

    return FALSE;
}
