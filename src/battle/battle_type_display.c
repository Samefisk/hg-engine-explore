#include "../../include/battle.h"
#include "../../include/constants/file.h"
#include "../../include/sprite.h"

#define ENEMY_TYPE_MARKER_NONE 0xFF
#define ENEMY_TYPE_MARKER_SLOT_COUNT 2
#define ENEMY_TYPE_MARKER_WIDTH 4
#define ENEMY_TYPE_MARKER_BG GF_BGL_FRAME1_M
#define ENEMY_TYPE_MARKER_TILE_BASE 0x130
#define ENEMY_TYPE_MARKER_PALETTE 12
#define ENEMY_TYPE_MARKER_HEAP_ID 5

typedef struct EnemyTypeMarkerSlot {
    u8 type;
    u8 visible;
} EnemyTypeMarkerSlot;

static EnemyTypeMarkerSlot sEnemyTypeMarkerSlots[ENEMY_TYPE_MARKER_SLOT_COUNT];
static BOOL sEnemyTypeMarkerInitialized;
static struct BattleSystem *sEnemyTypeMarkerOwner;

static const u8 sEnemyTypeMarkerX[ENEMY_TYPE_MARKER_SLOT_COUNT] = {
    13, 13,
};

static const u8 sEnemyTypeMarkerY[ENEMY_TYPE_MARKER_SLOT_COUNT] = {
    3, 4,
};

static BOOL EnemyTypeMarker_IsDisplayableType(u8 type)
{
    return type <= TYPE_DARK || type == TYPE_STELLAR;
}

static void EnemyTypeMarker_AddType(u8 *types, u8 *count, u8 type)
{
    int i;

    if (*count >= 2 || !EnemyTypeMarker_IsDisplayableType(type)) {
        return;
    }

    for (i = 0; i < *count; i++) {
        if (types[i] == type) {
            return;
        }
    }

    types[*count] = type;
    (*count)++;
}

static void EnemyTypeMarker_CollectTypes(struct BattlePokemon *mon, u8 *types)
{
    u8 count = 0;

    types[0] = ENEMY_TYPE_MARKER_NONE;
    types[1] = ENEMY_TYPE_MARKER_NONE;

    if (mon->is_currently_terastallized) {
        EnemyTypeMarker_AddType(types, &count, mon->tera_type);
        return;
    }

    EnemyTypeMarker_AddType(types, &count, mon->type1);
    EnemyTypeMarker_AddType(types, &count, mon->type2);
    EnemyTypeMarker_AddType(types, &count, mon->type3);
}

static BOOL EnemyTypeMarker_ShouldShowBattler(struct BattleStruct *ctx, int battlerId, int maxBattlers)
{
    return battlerId < maxBattlers
        && ctx->battlemon[battlerId].species != 0
        && ctx->battlemon[battlerId].hp > 0;
}

static void EnemyTypeMarker_ResetSlots(void)
{
    int slot;

    for (slot = 0; slot < ENEMY_TYPE_MARKER_SLOT_COUNT; slot++) {
        sEnemyTypeMarkerSlots[slot].type = ENEMY_TYPE_MARKER_NONE;
        sEnemyTypeMarkerSlots[slot].visible = FALSE;
    }
}

static void EnemyTypeMarker_DrawSlot(struct BattleSystem *bsys, int slot, u8 type)
{
    u16 tilemap[ENEMY_TYPE_MARKER_WIDTH];
    int tile;

    for (tile = 0; tile < ENEMY_TYPE_MARKER_WIDTH; tile++) {
        tilemap[tile] = ENEMY_TYPE_MARKER_TILE_BASE
            + (type * ENEMY_TYPE_MARKER_WIDTH)
            + tile
            + (ENEMY_TYPE_MARKER_PALETTE << 12);
    }
    BgCopyOrUncompressTilemapBufferRangeToVram(
        bsys->bgConfig,
        ENEMY_TYPE_MARKER_BG,
        tilemap,
        sizeof(tilemap),
        (sEnemyTypeMarkerY[slot] * 32) + sEnemyTypeMarkerX[slot]
    );

    sEnemyTypeMarkerSlots[slot].type = type;
    sEnemyTypeMarkerSlots[slot].visible = TRUE;
}

static void EnemyTypeMarker_ClearSlot(struct BattleSystem *bsys, int slot)
{
    // These BG1 cells are transparent space beside the enemy status OBJ.
    static const u16 blank[ENEMY_TYPE_MARKER_WIDTH] = {0};

    if (!sEnemyTypeMarkerSlots[slot].visible) {
        return;
    }

    BgCopyOrUncompressTilemapBufferRangeToVram(
        bsys->bgConfig,
        ENEMY_TYPE_MARKER_BG,
        blank,
        sizeof(blank),
        (sEnemyTypeMarkerY[slot] * 32) + sEnemyTypeMarkerX[slot]
    );
    sEnemyTypeMarkerSlots[slot].type = ENEMY_TYPE_MARKER_NONE;
    sEnemyTypeMarkerSlots[slot].visible = FALSE;
}

static void EnemyTypeMarker_ClearAll(struct BattleSystem *bsys)
{
    int slot;

    if (!sEnemyTypeMarkerInitialized || bsys == NULL || bsys->bgConfig == NULL) {
        return;
    }

    for (slot = 0; slot < ENEMY_TYPE_MARKER_SLOT_COUNT; slot++) {
        EnemyTypeMarker_ClearSlot(bsys, slot);
    }
}

void BattleSystem_PrepareEnemyTypeMarkers(struct BattleSystem *bsys, struct BattleStruct *ctx)
{
    if (bsys == NULL || ctx == NULL || bsys->bgConfig == NULL || bsys->palette == NULL) {
        return;
    }

    // BG1 tiles 0x130-0x17F and palette bank 12 are unused by the stock rival
    // command screen and Fell Stinger animation used for visual verification.
    // Existing battle UI reloads palettes 8, 10, and 11; the message window
    // occupies the lower screen while these cells live beside enemy gauges.
    GfGfxLoader_LoadCharData(
        ARC_BATTLE_GFX,
        ENEMY_TYPE_MARKER_GFX,
        bsys->bgConfig,
        ENEMY_TYPE_MARKER_BG,
        ENEMY_TYPE_MARKER_TILE_BASE,
        0,
        FALSE,
        ENEMY_TYPE_MARKER_HEAP_ID
    );
    PaletteData_LoadNarc(
        bsys->palette,
        ARC_BATTLE_GFX,
        ENEMY_TYPE_MARKER_GFX + 1,
        ENEMY_TYPE_MARKER_HEAP_ID,
        0,
        0x20,
        ENEMY_TYPE_MARKER_PALETTE * 16
    );

    sEnemyTypeMarkerOwner = bsys;
    sEnemyTypeMarkerInitialized = TRUE;
    EnemyTypeMarker_ResetSlots();
    BattleSystem_UpdateEnemyTypeMarkers(bsys, ctx);
}

void BattleSystem_ResetEnemyTypeMarkers(struct BattleSystem *bsys)
{
    if (bsys == NULL || sEnemyTypeMarkerOwner == bsys) {
        sEnemyTypeMarkerOwner = NULL;
        sEnemyTypeMarkerInitialized = FALSE;
        EnemyTypeMarker_ResetSlots();
    }
}

void BattleSystem_UpdateEnemyTypeMarkers(struct BattleSystem *bsys, struct BattleStruct *ctx)
{
    int maxBattlers;
    u8 types[2];

    if (bsys == NULL || ctx == NULL || bsys->bgConfig == NULL) {
        return;
    }
    if (ctx->fight_end_flag || ctx->server_seq_no == CONTROLLER_COMMAND_45) {
        EnemyTypeMarker_ClearAll(bsys);
        BattleSystem_ResetEnemyTypeMarkers(bsys);
        return;
    }
    if (!sEnemyTypeMarkerInitialized || sEnemyTypeMarkerOwner != bsys) {
        // Selection input is the first controller state where the main battle
        // BG and battler gauges are fully live in every standard battle path.
        if (ctx->server_seq_no < CONTROLLER_COMMAND_SELECTION_SCREEN_INPUT) {
            return;
        }
        BattleSystem_PrepareEnemyTypeMarkers(bsys, ctx);
        return;
    }

    maxBattlers = BattleWorkClientSetMaxGet(bsys);
    if (!EnemyTypeMarker_ShouldShowBattler(ctx, BATTLER_ENEMY, maxBattlers)) {
        EnemyTypeMarker_ClearSlot(bsys, 0);
        EnemyTypeMarker_ClearSlot(bsys, 1);
        return;
    }

    EnemyTypeMarker_CollectTypes(&ctx->battlemon[BATTLER_ENEMY], types);
    if (types[0] == ENEMY_TYPE_MARKER_NONE) {
        EnemyTypeMarker_ClearSlot(bsys, 0);
    } else {
        EnemyTypeMarker_DrawSlot(bsys, 0, types[0]);
    }
    if (types[1] == ENEMY_TYPE_MARKER_NONE) {
        EnemyTypeMarker_ClearSlot(bsys, 1);
    } else {
        EnemyTypeMarker_DrawSlot(bsys, 1, types[1]);
    }
}
