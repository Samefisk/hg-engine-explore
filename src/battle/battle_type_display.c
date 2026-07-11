#include "../../include/battle.h"
#include "../../include/constants/file.h"
#include "../../include/sprite.h"
#include "../../include/window.h"

#define ENEMY_TYPE_MARKER_NONE 0xFF
#define ENEMY_TYPE_MARKER_SLOT_COUNT 4
#define ENEMY_TYPE_MARKER_WIDTH 4
#define ENEMY_TYPE_MARKER_BG GF_BGL_FRAME0_M
#define ENEMY_TYPE_MARKER_TILE_BASE 0x380
#define ENEMY_TYPE_MARKER_PALETTE 12
#define ENEMY_TYPE_MARKER_HEAP_ID 5

typedef struct EnemyTypeMarkerSlot {
    u8 type;
    u8 visible;
} EnemyTypeMarkerSlot;

static EnemyTypeMarkerSlot sEnemyTypeMarkerSlots[ENEMY_TYPE_MARKER_SLOT_COUNT];
static BOOL sEnemyTypeMarkerInitialized;

static const u8 sEnemyTypeMarkerX[ENEMY_TYPE_MARKER_SLOT_COUNT] = {
    14, 14,
    14, 14,
};

static const u8 sEnemyTypeMarkerY[ENEMY_TYPE_MARKER_SLOT_COUNT] = {
    4, 5,
    9, 10,
};

static BOOL EnemyTypeMarker_IsDisplayableType(u8 type)
{
    return type <= TYPE_DARK;
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

static void EnemyTypeMarker_Init(struct BattleSystem *bsys)
{
    int slot;

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
        ENEMY_TYPE_MARKER_PALETTE * 0x20
    );

    for (slot = 0; slot < ENEMY_TYPE_MARKER_SLOT_COUNT; slot++) {
        sEnemyTypeMarkerSlots[slot].type = ENEMY_TYPE_MARKER_NONE;
        sEnemyTypeMarkerSlots[slot].visible = FALSE;
    }
    sEnemyTypeMarkerInitialized = TRUE;
}

static BOOL EnemyTypeMarker_DrawSlot(struct BattleSystem *bsys, int slot, u8 type)
{
    u16 tilemap[ENEMY_TYPE_MARKER_WIDTH];
    int tile;

    if (sEnemyTypeMarkerSlots[slot].visible
        && sEnemyTypeMarkerSlots[slot].type == type) {
        return FALSE;
    }

    for (tile = 0; tile < ENEMY_TYPE_MARKER_WIDTH; tile++) {
        tilemap[tile] = ENEMY_TYPE_MARKER_TILE_BASE
            + (type * ENEMY_TYPE_MARKER_WIDTH)
            + tile
            + (ENEMY_TYPE_MARKER_PALETTE << 12);
    }
    LoadRectToBgTilemapRect(
        bsys->bgConfig,
        ENEMY_TYPE_MARKER_BG,
        tilemap,
        sEnemyTypeMarkerX[slot],
        sEnemyTypeMarkerY[slot],
        ENEMY_TYPE_MARKER_WIDTH,
        1
    );

    sEnemyTypeMarkerSlots[slot].type = type;
    sEnemyTypeMarkerSlots[slot].visible = TRUE;
    return TRUE;
}

static BOOL EnemyTypeMarker_ClearSlot(struct BattleSystem *bsys, int slot)
{
    static const u16 blank[ENEMY_TYPE_MARKER_WIDTH] = {0};

    if (!sEnemyTypeMarkerSlots[slot].visible) {
        return FALSE;
    }

    LoadRectToBgTilemapRect(
        bsys->bgConfig,
        ENEMY_TYPE_MARKER_BG,
        blank,
        sEnemyTypeMarkerX[slot],
        sEnemyTypeMarkerY[slot],
        ENEMY_TYPE_MARKER_WIDTH,
        1
    );
    sEnemyTypeMarkerSlots[slot].type = ENEMY_TYPE_MARKER_NONE;
    sEnemyTypeMarkerSlots[slot].visible = FALSE;
    return TRUE;
}

static void EnemyTypeMarker_ClearAll(struct BattleSystem *bsys)
{
    int slot;
    BOOL changed = FALSE;

    if (!sEnemyTypeMarkerInitialized || bsys == NULL || bsys->bgConfig == NULL) {
        return;
    }

    for (slot = 0; slot < ENEMY_TYPE_MARKER_SLOT_COUNT; slot++) {
        changed |= EnemyTypeMarker_ClearSlot(bsys, slot);
    }
    if (changed) {
        ScheduleBgTilemapBufferTransfer(bsys->bgConfig, ENEMY_TYPE_MARKER_BG);
    }
    sEnemyTypeMarkerInitialized = FALSE;
}

void BattleSystem_UpdateEnemyTypeMarkers(struct BattleSystem *bsys, struct BattleStruct *ctx)
{
    int enemySlot;
    int maxBattlers;
    BOOL changed = FALSE;

    if (bsys == NULL || ctx == NULL || bsys->bgConfig == NULL || bsys->palette == NULL) {
        return;
    }
    if (ctx->fight_end_flag || ctx->server_seq_no == CONTROLLER_COMMAND_45) {
        EnemyTypeMarker_ClearAll(bsys);
        return;
    }
    if (!sEnemyTypeMarkerInitialized) {
        EnemyTypeMarker_Init(bsys);
    }

    maxBattlers = BattleWorkClientSetMaxGet(bsys);
    for (enemySlot = 0; enemySlot < 2; enemySlot++) {
        int battlerId = enemySlot == 0 ? BATTLER_ENEMY : BATTLER_ENEMY2;
        int slot = enemySlot * 2;
        u8 types[2];

        if (!EnemyTypeMarker_ShouldShowBattler(ctx, battlerId, maxBattlers)) {
            changed |= EnemyTypeMarker_ClearSlot(bsys, slot);
            changed |= EnemyTypeMarker_ClearSlot(bsys, slot + 1);
            continue;
        }

        EnemyTypeMarker_CollectTypes(&ctx->battlemon[battlerId], types);
        if (types[0] == ENEMY_TYPE_MARKER_NONE) {
            changed |= EnemyTypeMarker_ClearSlot(bsys, slot);
        } else {
            changed |= EnemyTypeMarker_DrawSlot(bsys, slot, types[0]);
        }
        if (types[1] == ENEMY_TYPE_MARKER_NONE) {
            changed |= EnemyTypeMarker_ClearSlot(bsys, slot + 1);
        } else {
            changed |= EnemyTypeMarker_DrawSlot(bsys, slot + 1, types[1]);
        }
    }

    if (changed) {
        ScheduleBgTilemapBufferTransfer(bsys->bgConfig, ENEMY_TYPE_MARKER_BG);
    }
}
