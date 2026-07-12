#include "../../include/battle.h"

#define BATTLE_TYPE_MARKER_NONE 0xFF
#define BATTLE_TYPE_MARKER_SIDE_COUNT 2
#define BATTLE_TYPE_MARKER_SLOT_COUNT 2
#define BATTLE_TYPE_MARKER_TILE_WORDS 32
#define BATTLE_TYPE_MARKER_MAIN_OBJ_VRAM ((volatile u16 *)0x06400000)
#define BATTLE_TYPE_MARKER_MAIN_OBJ_VRAM_SIZE 0x10000
#define BATTLE_TYPE_MARKER_SINGLE_PLAYER_HP_BAR 0
#define BATTLE_TYPE_MARKER_SINGLE_ENEMY_HP_BAR 1
#define BATTLE_TYPE_MARKER_MAIN_RAM_START 0x02000000
#define BATTLE_TYPE_MARKER_MAIN_RAM_END 0x02400000

// OpponentData embeds BattleHpBar at 0x28; its boxObj and type are at +4 and +0x25.
#define BATTLE_TYPE_MARKER_BOX_OBJ_OFFSET 0x2C
#define BATTLE_TYPE_MARKER_HP_BAR_TYPE_OFFSET 0x4D
#define BATTLE_TYPE_MARKER_SPRITE_IMAGE_MAIN_VRAM_OFFSET 0xB8

enum BattleTypeMarkerSide {
    BATTLE_TYPE_MARKER_PLAYER,
    BATTLE_TYPE_MARKER_ENEMY,
};

static const u8 sBattleTypeMarkerBattler[BATTLE_TYPE_MARKER_SIDE_COUNT] = {
    BATTLER_PLAYER, BATTLER_ENEMY,
};

static const u8 sBattleTypeMarkerHpBarType[BATTLE_TYPE_MARKER_SIDE_COUNT] = {
    BATTLE_TYPE_MARKER_SINGLE_PLAYER_HP_BAR, BATTLE_TYPE_MARKER_SINGLE_ENEMY_HP_BAR,
};

static const u16 sBattleTypeMarkerVramOffset[BATTLE_TYPE_MARKER_SIDE_COUNT][BATTLE_TYPE_MARKER_SLOT_COUNT] = {
    { 0x300, 0x400 },
    { 0xAC0, 0xBC0 },
};

static const char sEnemyTypeMarkerLabels[NUMBER_OF_MON_TYPES][4] = {
    "NOR", "FGT", "FLY", "PSN", "GND", "RCK", "BUG", "GHO", "STL", "FAI",
    "FIR", "WAT", "GRS", "ELC", "PSY", "ICE", "DRA", "DRK", "NUL", "STR",
};

// Reuse colors already present in the stock enemy-gauge OBJ palette.
static const u8 sEnemyTypeMarkerColors[NUMBER_OF_MON_TYPES] = {
    3, 9, 12, 13, 7, 7, 6, 11, 2, 13,
    10, 12, 6, 8, 13, 12, 11, 1, 3, 11,
};

static const u8 sEnemyTypeMarkerGlyphs[26][5] = {
    ['A' - 'A'] = {2, 5, 7, 5, 5},
    ['B' - 'A'] = {6, 5, 6, 5, 6},
    ['C' - 'A'] = {3, 4, 4, 4, 3},
    ['D' - 'A'] = {6, 5, 5, 5, 6},
    ['E' - 'A'] = {7, 4, 6, 4, 7},
    ['F' - 'A'] = {7, 4, 6, 4, 4},
    ['G' - 'A'] = {3, 4, 5, 5, 3},
    ['H' - 'A'] = {5, 5, 7, 5, 5},
    ['I' - 'A'] = {7, 2, 2, 2, 7},
    ['K' - 'A'] = {5, 5, 6, 5, 5},
    ['L' - 'A'] = {4, 4, 4, 4, 7},
    ['N' - 'A'] = {5, 7, 7, 7, 5},
    ['O' - 'A'] = {2, 5, 5, 5, 2},
    ['P' - 'A'] = {6, 5, 6, 4, 4},
    ['R' - 'A'] = {6, 5, 6, 5, 5},
    ['S' - 'A'] = {3, 4, 2, 1, 6},
    ['T' - 'A'] = {7, 2, 2, 2, 2},
    ['U' - 'A'] = {5, 5, 5, 5, 7},
    ['W' - 'A'] = {5, 5, 7, 7, 5},
    ['Y' - 'A'] = {5, 5, 2, 2, 2},
};

static const u8 sBattleTypeMarkerOriginalTiles[BATTLE_TYPE_MARKER_SIDE_COUNT][BATTLE_TYPE_MARKER_SLOT_COUNT][BATTLE_TYPE_MARKER_TILE_WORDS * 2] = {
    {
        {
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x40, 0xFE, 0xFF, 0x00, 0x40, 0xFE, 0xFF,
            0x00, 0x40, 0xFE, 0xFF, 0x00, 0x34, 0xF3, 0xFF,
            0x00, 0xE4, 0xFF, 0xFF, 0x00, 0xE4, 0xFF, 0xFF,
            0x00, 0xE4, 0xFF, 0xFF, 0x40, 0x33, 0xFF, 0xFF,
        },
        {
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x40,
            0x40, 0xFE, 0xFF, 0xFF, 0x40, 0x2E, 0x22, 0x22,
            0x40, 0xFE, 0xFF, 0xFF, 0x14, 0x21, 0x22, 0x22,
            0xE4, 0x22, 0x22, 0x22, 0xE4, 0x22, 0x22, 0x22,
            0xE4, 0x22, 0x22, 0x22, 0x11, 0x22, 0x22, 0x22,
        },
    },
    {
        {
            0xFF, 0x4E, 0x00, 0x00, 0xFF, 0x4E, 0x00, 0x00,
            0xFF, 0x33, 0x04, 0x00, 0xFF, 0xEF, 0x04, 0x00,
            0xFF, 0xEF, 0x04, 0x00, 0xFF, 0xEF, 0x04, 0x00,
            0xFF, 0x3F, 0x43, 0x00, 0xFF, 0xFF, 0x4E, 0x00,
        },
        {
            0xFF, 0xFF, 0x4E, 0x00, 0xFF, 0xFF, 0x4E, 0x00,
            0xFF, 0xFF, 0x33, 0x04, 0xFF, 0xFF, 0xEF, 0x04,
            0xFF, 0xFF, 0xEF, 0x04, 0xFF, 0xFF, 0xEF, 0x04,
            0xFF, 0xFF, 0x3F, 0x43, 0xFF, 0xFF, 0xFF, 0x4E,
        },
    },
};
struct BattleTypeMarkerSideState {
    volatile u16 *gaugeVram;
    u8 types[BATTLE_TYPE_MARKER_SLOT_COUNT];
    BOOL drawn;
};

static struct {
    struct BattleSystem *owner;
    struct BattleTypeMarkerSideState side[BATTLE_TYPE_MARKER_SIDE_COUNT];
} sBattleTypeMarkerState;

static BOOL EnemyTypeMarker_IsDisplayableType(u8 type)
{
    return type < NUMBER_OF_MON_TYPES && type != TYPE_TYPELESS;
}

static void EnemyTypeMarker_AddType(u8 *types, u8 *count, u8 type)
{
    int i;

    if (*count >= BATTLE_TYPE_MARKER_SLOT_COUNT || !EnemyTypeMarker_IsDisplayableType(type)) {
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

    types[0] = BATTLE_TYPE_MARKER_NONE;
    types[1] = BATTLE_TYPE_MARKER_NONE;
    if (mon->is_currently_terastallized) {
        EnemyTypeMarker_AddType(types, &count, mon->tera_type);
        return;
    }
    EnemyTypeMarker_AddType(types, &count, mon->type1);
    EnemyTypeMarker_AddType(types, &count, mon->type2);
    // The compact gauge surface intentionally shows at most two distinct types.
    EnemyTypeMarker_AddType(types, &count, mon->type3);
}

static BOOL EnemyTypeMarker_IsValidMainRamRange(const void *pointer, u32 size)
{
    u32 address = (u32)pointer;

    return address >= BATTLE_TYPE_MARKER_MAIN_RAM_START
        && size <= BATTLE_TYPE_MARKER_MAIN_RAM_END - BATTLE_TYPE_MARKER_MAIN_RAM_START
        && address <= BATTLE_TYPE_MARKER_MAIN_RAM_END - size
        && (address & 3) == 0;
}

static volatile u16 *EnemyTypeMarker_GetGaugeVram(struct BattleSystem *bsys, int side)
{
    u8 battler = sBattleTypeMarkerBattler[side];
    u8 hpBarType = sBattleTypeMarkerHpBarType[side];
    u8 *opponentData;
    void *managedSprite;
    u8 *sprite;
    u32 imageVramOffset;
    u32 writeEnd = sBattleTypeMarkerVramOffset[side][BATTLE_TYPE_MARKER_SLOT_COUNT - 1]
        + (BATTLE_TYPE_MARKER_TILE_WORDS * sizeof(u16));

    if (bsys == NULL || battler >= BattleWorkClientSetMaxGet(bsys)) {
        return NULL;
    }
    opponentData = bsys->opponentData[battler];
    if (!EnemyTypeMarker_IsValidMainRamRange(opponentData, BATTLE_TYPE_MARKER_HP_BAR_TYPE_OFFSET + 1)
     || opponentData[BATTLE_TYPE_MARKER_HP_BAR_TYPE_OFFSET] != hpBarType) {
        return NULL;
    }
    managedSprite = *(void **)(opponentData + BATTLE_TYPE_MARKER_BOX_OBJ_OFFSET);
    if (!EnemyTypeMarker_IsValidMainRamRange(managedSprite, sizeof(void *))) {
        return NULL;
    }
    sprite = *(u8 **)managedSprite;
    if (!EnemyTypeMarker_IsValidMainRamRange(sprite, BATTLE_TYPE_MARKER_SPRITE_IMAGE_MAIN_VRAM_OFFSET + sizeof(u32))) {
        return NULL;
    }
    imageVramOffset = *(u32 *)(sprite + BATTLE_TYPE_MARKER_SPRITE_IMAGE_MAIN_VRAM_OFFSET);
    if ((imageVramOffset & 0x3F) != 0
     || writeEnd > BATTLE_TYPE_MARKER_MAIN_OBJ_VRAM_SIZE
     || imageVramOffset > BATTLE_TYPE_MARKER_MAIN_OBJ_VRAM_SIZE - writeEnd) {
        return NULL;
    }
    return BATTLE_TYPE_MARKER_MAIN_OBJ_VRAM + (imageVramOffset / sizeof(u16));
}

static void EnemyTypeMarker_WriteTiles(volatile u16 *dst, const u16 *src)
{
    int i;

    for (i = 0; i < BATTLE_TYPE_MARKER_TILE_WORDS; i++) {
        dst[i] = src[i];
    }
}

static void EnemyTypeMarker_SetPixel(u8 *tiles, int x, int y, u8 color)
{
    int offset = ((x / 8) * 32) + (y * 4) + ((x % 8) / 2);

    if (x & 1) {
        tiles[offset] = (tiles[offset] & 0x0F) | (color << 4);
    } else {
        tiles[offset] = (tiles[offset] & 0xF0) | color;
    }
}

static void EnemyTypeMarker_Render(u16 *tiles, u8 type)
{
    const char *label = sEnemyTypeMarkerLabels[type];
    u8 *pixels = (u8 *)tiles;
    u8 color = sEnemyTypeMarkerColors[type];
    int character;
    int x;
    int y;

    for (y = 0; y < 8; y++) {
        for (x = 0; x < 16; x++) {
            EnemyTypeMarker_SetPixel(pixels, x, y, (x == 0 || x == 15 || y == 0 || y == 7) ? 14 : color);
        }
    }
    for (character = 0; character < 3; character++) {
        const u8 *glyph = sEnemyTypeMarkerGlyphs[label[character] - 'A'];

        for (y = 0; y < 5; y++) {
            for (x = 0; x < 3; x++) {
                if (glyph[y] & (1 << (2 - x))) {
                    EnemyTypeMarker_SetPixel(pixels, 2 + (character * 4) + x, 1 + y, 4);
                }
            }
        }
    }
}

static void EnemyTypeMarker_DrawSlot(volatile u16 *gaugeVram, int side, int slot, u8 type)
{
    volatile u16 *target = gaugeVram + (sBattleTypeMarkerVramOffset[side][slot] / sizeof(u16));
    u16 renderedTiles[BATTLE_TYPE_MARKER_TILE_WORDS];
    int i;

    for (i = 0; i < BATTLE_TYPE_MARKER_TILE_WORDS * 2; i++) {
        ((u8 *)renderedTiles)[i] = sBattleTypeMarkerOriginalTiles[side][slot][i];
    }
    if (type != BATTLE_TYPE_MARKER_NONE) {
        EnemyTypeMarker_Render(renderedTiles, type);
    }
    EnemyTypeMarker_WriteTiles(target, renderedTiles);
}

void BattleSystem_ResetEnemyTypeMarkers(struct BattleSystem *bsys)
{
    int side;

    if (bsys != NULL && sBattleTypeMarkerState.owner != bsys) {
        return;
    }
    sBattleTypeMarkerState.owner = NULL;
    for (side = 0; side < BATTLE_TYPE_MARKER_SIDE_COUNT; side++) {
        sBattleTypeMarkerState.side[side].drawn = FALSE;
        sBattleTypeMarkerState.side[side].gaugeVram = NULL;
    }
}

static BOOL EnemyTypeMarker_TypesMatch(const u8 *left, const u8 *right)
{
    int slot;

    for (slot = 0; slot < BATTLE_TYPE_MARKER_SLOT_COUNT; slot++) {
        if (left[slot] != right[slot]) {
            return FALSE;
        }
    }
    return TRUE;
}

void BattleSystem_UpdateEnemyTypeMarkers(struct BattleSystem *bsys, struct BattleStruct *ctx)
{
    int side;
    int slot;

    if (bsys == NULL || ctx == NULL || ctx->fight_end_flag
     || ctx->server_seq_no != CONTROLLER_COMMAND_SELECTION_SCREEN_INPUT) {
        BattleSystem_ResetEnemyTypeMarkers(bsys);
        return;
    }
    if (sBattleTypeMarkerState.owner != bsys) {
        BattleSystem_ResetEnemyTypeMarkers(NULL);
        sBattleTypeMarkerState.owner = bsys;
    }
    for (side = 0; side < BATTLE_TYPE_MARKER_SIDE_COUNT; side++) {
        struct BattleTypeMarkerSideState *state = &sBattleTypeMarkerState.side[side];
        volatile u16 *gaugeVram;
        u8 battler = sBattleTypeMarkerBattler[side];
        u8 types[BATTLE_TYPE_MARKER_SLOT_COUNT];

        if (battler >= BattleWorkClientSetMaxGet(bsys)
         || ctx->battlemon[battler].species == 0
         || ctx->battlemon[battler].hp == 0) {
            state->drawn = FALSE;
            state->gaugeVram = NULL;
            continue;
        }
        gaugeVram = EnemyTypeMarker_GetGaugeVram(bsys, side);
        if (gaugeVram == NULL) {
            state->drawn = FALSE;
            state->gaugeVram = NULL;
            continue;
        }
        EnemyTypeMarker_CollectTypes(&ctx->battlemon[battler], types);

        if (state->drawn && state->gaugeVram == gaugeVram
         && EnemyTypeMarker_TypesMatch(state->types, types)) {
            continue;
        }
        for (slot = 0; slot < BATTLE_TYPE_MARKER_SLOT_COUNT; slot++) {
            EnemyTypeMarker_DrawSlot(gaugeVram, side, slot, types[slot]);
            state->types[slot] = types[slot];
        }
        state->drawn = TRUE;
        state->gaugeVram = gaugeVram;
    }
}
