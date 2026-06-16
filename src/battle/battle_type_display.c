#include "../../include/battle.h"
#include "../../include/constants/file.h"

#define ENEMY_TYPE_ICON_SPRITE_TAG 22100
#define ENEMY_TYPE_ICON_PAL_TAG 22110
#define ENEMY_TYPE_ICON_CELL_TAG 22120
#define ENEMY_TYPE_ICON_CELL_ANIM_TAG 22121
#define ENEMY_TYPE_ICON_SLOT_COUNT 4
#define ENEMY_TYPE_NONE 0xFF

typedef struct EnemyTypeIconSlot {
    CATS_ACT_PTR actor;
    u8 type;
} EnemyTypeIconSlot;

static EnemyTypeIconSlot sEnemyTypeIcons[ENEMY_TYPE_ICON_SLOT_COUNT] = {
    {NULL, ENEMY_TYPE_NONE},
    {NULL, ENEMY_TYPE_NONE},
    {NULL, ENEMY_TYPE_NONE},
    {NULL, ENEMY_TYPE_NONE},
};

static BOOL sEnemyTypeIconCellLoaded = FALSE;

static const s16 sEnemyTypeIconX[ENEMY_TYPE_ICON_SLOT_COUNT] = {
    122, 154,
    122, 154,
};

static const s16 sEnemyTypeIconY[ENEMY_TYPE_ICON_SLOT_COUNT] = {
    15, 15,
    51, 51,
};

static const u16 sEnemyTypeIconGfxByType[NUMBER_OF_MON_TYPES] = {
    [TYPE_NORMAL] = TYPE_ICON_NORMAL_GFX,
    [TYPE_FIGHTING] = TYPE_ICON_FIGHTING_GFX,
    [TYPE_FLYING] = TYPE_ICON_FLYING_GFX,
    [TYPE_POISON] = TYPE_ICON_POISON_GFX,
    [TYPE_GROUND] = TYPE_ICON_GROUND_GFX,
    [TYPE_ROCK] = TYPE_ICON_ROCK_GFX,
    [TYPE_BUG] = TYPE_ICON_BUG_GFX,
    [TYPE_GHOST] = TYPE_ICON_GHOST_GFX,
    [TYPE_STEEL] = TYPE_ICON_STEEL_GFX,
    [TYPE_FAIRY] = TYPE_ICON_FAIRY_GFX,
    [TYPE_FIRE] = TYPE_ICON_FIRE_GFX,
    [TYPE_WATER] = TYPE_ICON_WATER_GFX,
    [TYPE_GRASS] = TYPE_ICON_GRASS_GFX,
    [TYPE_ELECTRIC] = TYPE_ICON_ELECTRIC_GFX,
    [TYPE_PSYCHIC] = TYPE_ICON_PSYCHIC_GFX,
    [TYPE_ICE] = TYPE_ICON_ICE_GFX,
    [TYPE_DRAGON] = TYPE_ICON_DRAGON_GFX,
    [TYPE_DARK] = TYPE_ICON_DARK_GFX,
};

static const OAMSpriteTemplate sEnemyTypeIconTemplate = {
    122,
    15,
    0,
    0,
    100,
    0,
    NNS_G2D_VRAM_TYPE_2DMAIN,
    {
        ENEMY_TYPE_ICON_SPRITE_TAG,
        ENEMY_TYPE_ICON_PAL_TAG,
        ENEMY_TYPE_ICON_CELL_TAG,
        ENEMY_TYPE_ICON_CELL_ANIM_TAG,
        CLACT_U_HEADER_DATA_NONE,
        CLACT_U_HEADER_DATA_NONE,
    },
    1,
    0,
};

static BOOL EnemyTypeIcon_IsDisplayableType(u8 type)
{
    return type < NUMBER_OF_MON_TYPES && sEnemyTypeIconGfxByType[type] != 0;
}

static void EnemyTypeIcon_AddType(u8 *types, u8 *count, u8 type)
{
    int i;

    if (*count >= 2 || !EnemyTypeIcon_IsDisplayableType(type)) {
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

static void EnemyTypeIcon_CollectTypes(struct BattlePokemon *mon, u8 *types)
{
    u8 count = 0;

    types[0] = ENEMY_TYPE_NONE;
    types[1] = ENEMY_TYPE_NONE;

    if (mon->is_currently_terastallized) {
        EnemyTypeIcon_AddType(types, &count, mon->tera_type);
        return;
    }

    EnemyTypeIcon_AddType(types, &count, mon->type1);
    EnemyTypeIcon_AddType(types, &count, mon->type2);
    EnemyTypeIcon_AddType(types, &count, mon->type3);
}

static BOOL EnemyTypeIcon_ShouldHideAll(struct BattleSystem *bsys, struct BattleStruct *ctx)
{
    return bsys == NULL
        || ctx == NULL
        || ctx->fight_end_flag
        || ctx->server_seq_no == CONTROLLER_COMMAND_45;
}

static BOOL EnemyTypeIcon_ShouldShowBattler(struct BattleStruct *ctx, int battlerId, int maxBattlers)
{
    return battlerId < maxBattlers
        && ctx->battlemon[battlerId].species != 0
        && ctx->battlemon[battlerId].hp > 0;
}

static void EnemyTypeIcon_FreeSlot(void *crp, int slot)
{
    if (sEnemyTypeIcons[slot].actor == NULL) {
        sEnemyTypeIcons[slot].type = ENEMY_TYPE_NONE;
        return;
    }

    OAM_FreeResourceChar(crp, ENEMY_TYPE_ICON_SPRITE_TAG + slot);
    OAM_FreeResourcePltt(crp, ENEMY_TYPE_ICON_PAL_TAG + slot);
    CATS_ActorPointerDelete_S(sEnemyTypeIcons[slot].actor);
    sEnemyTypeIcons[slot].actor = NULL;
    sEnemyTypeIcons[slot].type = ENEMY_TYPE_NONE;
}

static BOOL EnemyTypeIcon_HasAnyActor(void)
{
    int slot;

    for (slot = 0; slot < ENEMY_TYPE_ICON_SLOT_COUNT; slot++) {
        if (sEnemyTypeIcons[slot].actor != NULL) {
            return TRUE;
        }
    }

    return FALSE;
}

static void EnemyTypeIcon_FreeSharedResources(void *crp)
{
    if (!sEnemyTypeIconCellLoaded || EnemyTypeIcon_HasAnyActor()) {
        return;
    }

    OAM_FreeResourceCell(crp, ENEMY_TYPE_ICON_CELL_TAG);
    OAM_FreeResourceCellAnm(crp, ENEMY_TYPE_ICON_CELL_ANIM_TAG);
    sEnemyTypeIconCellLoaded = FALSE;
}

static void EnemyTypeIcon_HideAll(void *crp)
{
    int slot;

    if (crp == NULL) {
        return;
    }

    for (slot = 0; slot < ENEMY_TYPE_ICON_SLOT_COUNT; slot++) {
        EnemyTypeIcon_FreeSlot(crp, slot);
    }
    EnemyTypeIcon_FreeSharedResources(crp);
}

static void EnemyTypeIcon_LoadSharedResources(void *csp, void *crp)
{
    if (sEnemyTypeIconCellLoaded) {
        return;
    }

    OAM_LoadResourceCellArc(csp, crp, ARC_ITEM_GFX_DATA, 1, 0, ENEMY_TYPE_ICON_CELL_TAG);
    OAM_LoadResourceCellAnmArc(csp, crp, ARC_ITEM_GFX_DATA, 0, 0, ENEMY_TYPE_ICON_CELL_ANIM_TAG);
    sEnemyTypeIconCellLoaded = TRUE;
}

static void EnemyTypeIcon_ShowSlot(struct BattleSystem *bsys, void *csp, void *crp, int slot, u8 type)
{
    OAMSpriteTemplate template = sEnemyTypeIconTemplate;
    u16 gfx = sEnemyTypeIconGfxByType[type];
    void *pfd = BattleWorkPfdGet(bsys);

    if (pfd == NULL) {
        return;
    }

    EnemyTypeIcon_LoadSharedResources(csp, crp);

    OAM_LoadResourcePlttWorkArc(
        pfd,
        FADE_MAIN_OBJ,
        csp,
        crp,
        ARC_BATTLE_GFX,
        gfx + 1,
        0,
        1,
        NNS_G2D_VRAM_TYPE_2DMAIN,
        ENEMY_TYPE_ICON_PAL_TAG + slot
    );
    OAM_LoadResourceCharArc(
        csp,
        crp,
        ARC_BATTLE_GFX,
        gfx,
        0,
        NNS_G2D_VRAM_TYPE_2DMAIN,
        ENEMY_TYPE_ICON_SPRITE_TAG + slot
    );

    template.x = sEnemyTypeIconX[slot];
    template.y = sEnemyTypeIconY[slot];
    template.id[CLACT_U_CHAR_RES] = ENEMY_TYPE_ICON_SPRITE_TAG + slot;
    template.id[CLACT_U_PLTT_RES] = ENEMY_TYPE_ICON_PAL_TAG + slot;
    template.id[CLACT_U_CELL_RES] = ENEMY_TYPE_ICON_CELL_TAG;
    template.id[CLACT_U_CELLANM_RES] = ENEMY_TYPE_ICON_CELL_ANIM_TAG;

    sEnemyTypeIcons[slot].actor = OAM_ObjectAdd_S(csp, crp, &template);
    sEnemyTypeIcons[slot].type = type;

    if (sEnemyTypeIcons[slot].actor != NULL) {
        OAM_ObjectUpdate(sEnemyTypeIcons[slot].actor->act);
    }
}

static void EnemyTypeIcon_SyncSlot(struct BattleSystem *bsys, void *csp, void *crp, int slot, u8 type)
{
    if (type == ENEMY_TYPE_NONE) {
        EnemyTypeIcon_FreeSlot(crp, slot);
        return;
    }

    if (sEnemyTypeIcons[slot].actor != NULL && sEnemyTypeIcons[slot].type == type) {
        return;
    }

    EnemyTypeIcon_FreeSlot(crp, slot);
    EnemyTypeIcon_ShowSlot(bsys, csp, crp, slot, type);
}

void BattleSystem_UpdateEnemyTypeIcons(struct BattleSystem *bsys, struct BattleStruct *ctx)
{
    int enemySlot;
    int maxBattlers;
    void *csp;
    void *crp;

    if (bsys == NULL) {
        return;
    }

    csp = BattleWorkCATS_SYS_PTRGet(bsys);
    crp = BattleWorkCATS_RES_PTRGet(bsys);
    maxBattlers = BattleWorkClientSetMaxGet(bsys);

    if (EnemyTypeIcon_ShouldHideAll(bsys, ctx) || csp == NULL || crp == NULL) {
        EnemyTypeIcon_HideAll(crp);
        return;
    }

    for (enemySlot = 0; enemySlot < 2; enemySlot++) {
        int battlerId = enemySlot == 0 ? BATTLER_ENEMY : BATTLER_ENEMY2;
        int slot = enemySlot * 2;
        u8 types[2];

        if (!EnemyTypeIcon_ShouldShowBattler(ctx, battlerId, maxBattlers)) {
            EnemyTypeIcon_FreeSlot(crp, slot);
            EnemyTypeIcon_FreeSlot(crp, slot + 1);
            continue;
        }

        EnemyTypeIcon_CollectTypes(&ctx->battlemon[battlerId], types);
        EnemyTypeIcon_SyncSlot(bsys, csp, crp, slot, types[0]);
        EnemyTypeIcon_SyncSlot(bsys, csp, crp, slot + 1, types[1]);
    }

    EnemyTypeIcon_FreeSharedResources(crp);
}
