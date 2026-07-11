#include "../../include/battle.h"

#define ENEMY_TYPE_MARKER_NONE 0xFF
#define ENEMY_TYPE_MARKER_SLOT_COUNT 2
#define ENEMY_TYPE_MARKER_TILE_WORDS 32
#define ENEMY_TYPE_MARKER_MAIN_OBJ_VRAM ((volatile u16 *)0x06400000)
#define ENEMY_TYPE_MARKER_MAIN_OBJ_VRAM_SIZE 0x10000
#define ENEMY_TYPE_MARKER_SINGLE_ENEMY_HP_BAR 1
#define ENEMY_TYPE_MARKER_MAIN_RAM_START 0x02000000
#define ENEMY_TYPE_MARKER_MAIN_RAM_END 0x02400000

// OpponentData embeds BattleHpBar at 0x28; its boxObj and type are at +4 and +0x25.
#define ENEMY_TYPE_MARKER_BOX_OBJ_OFFSET 0x2C
#define ENEMY_TYPE_MARKER_HP_BAR_TYPE_OFFSET 0x4D
#define ENEMY_TYPE_MARKER_SPRITE_IMAGE_MAIN_VRAM_OFFSET 0xB8

static const u16 sEnemyTypeMarkerVramOffset[ENEMY_TYPE_MARKER_SLOT_COUNT] = {
    0xAC0, 0xBC0,
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

static const u8 sEnemyTypeMarkerOriginalTiles[ENEMY_TYPE_MARKER_SLOT_COUNT][ENEMY_TYPE_MARKER_TILE_WORDS * 2] = {
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
};
static BOOL sEnemyTypeMarkersDrawn;
static volatile u16 *sEnemyTypeMarkerGaugeVram;

static BOOL EnemyTypeMarker_IsDisplayableType(u8 type)
{
    return type < NUMBER_OF_MON_TYPES && type != TYPE_TYPELESS;
}

static void EnemyTypeMarker_AddType(u8 *types, u8 *count, u8 type)
{
    int i;

    if (*count >= ENEMY_TYPE_MARKER_SLOT_COUNT || !EnemyTypeMarker_IsDisplayableType(type)) {
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
    // The compact gauge surface intentionally shows at most two distinct types.
    EnemyTypeMarker_AddType(types, &count, mon->type3);
}

static BOOL EnemyTypeMarker_IsValidMainRamRange(const void *pointer, u32 size)
{
    u32 address = (u32)pointer;

    return address >= ENEMY_TYPE_MARKER_MAIN_RAM_START
        && size <= ENEMY_TYPE_MARKER_MAIN_RAM_END - ENEMY_TYPE_MARKER_MAIN_RAM_START
        && address <= ENEMY_TYPE_MARKER_MAIN_RAM_END - size
        && (address & 3) == 0;
}

static volatile u16 *EnemyTypeMarker_GetGaugeVram(struct BattleSystem *bsys)
{
    u8 *opponentData;
    void *managedSprite;
    u8 *sprite;
    u32 imageVramOffset;

    if (bsys == NULL || BATTLER_ENEMY >= BattleWorkClientSetMaxGet(bsys)) {
        return NULL;
    }
    opponentData = bsys->opponentData[BATTLER_ENEMY];
    if (!EnemyTypeMarker_IsValidMainRamRange(opponentData, ENEMY_TYPE_MARKER_HP_BAR_TYPE_OFFSET + 1)
     || opponentData[ENEMY_TYPE_MARKER_HP_BAR_TYPE_OFFSET] != ENEMY_TYPE_MARKER_SINGLE_ENEMY_HP_BAR) {
        return NULL;
    }
    managedSprite = *(void **)(opponentData + ENEMY_TYPE_MARKER_BOX_OBJ_OFFSET);
    if (!EnemyTypeMarker_IsValidMainRamRange(managedSprite, sizeof(void *))) {
        return NULL;
    }
    sprite = *(u8 **)managedSprite;
    if (!EnemyTypeMarker_IsValidMainRamRange(sprite, ENEMY_TYPE_MARKER_SPRITE_IMAGE_MAIN_VRAM_OFFSET + sizeof(u32))) {
        return NULL;
    }
    imageVramOffset = *(u32 *)(sprite + ENEMY_TYPE_MARKER_SPRITE_IMAGE_MAIN_VRAM_OFFSET);
    if ((imageVramOffset & 0x3F) != 0
     || imageVramOffset > ENEMY_TYPE_MARKER_MAIN_OBJ_VRAM_SIZE - 0xC00) {
        return NULL;
    }
    return ENEMY_TYPE_MARKER_MAIN_OBJ_VRAM + (imageVramOffset / sizeof(u16));
}

static void EnemyTypeMarker_WriteTiles(volatile u16 *dst, const u16 *src)
{
    int i;

    for (i = 0; i < ENEMY_TYPE_MARKER_TILE_WORDS; i++) {
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

static void EnemyTypeMarker_DrawSlot(volatile u16 *gaugeVram, int slot, u8 type)
{
    volatile u16 *target = gaugeVram + (sEnemyTypeMarkerVramOffset[slot] / sizeof(u16));
    u16 renderedTiles[ENEMY_TYPE_MARKER_TILE_WORDS];
    int i;

    for (i = 0; i < ENEMY_TYPE_MARKER_TILE_WORDS * 2; i++) {
        ((u8 *)renderedTiles)[i] = sEnemyTypeMarkerOriginalTiles[slot][i];
    }
    if (type != ENEMY_TYPE_MARKER_NONE) {
        EnemyTypeMarker_Render(renderedTiles, type);
    }
    EnemyTypeMarker_WriteTiles(target, renderedTiles);
}

void BattleSystem_ResetEnemyTypeMarkers(struct BattleSystem *bsys)
{
    (void)bsys;
    sEnemyTypeMarkersDrawn = FALSE;
    sEnemyTypeMarkerGaugeVram = NULL;
}

void BattleSystem_UpdateEnemyTypeMarkers(struct BattleSystem *bsys, struct BattleStruct *ctx)
{
    volatile u16 *gaugeVram;
    u8 types[ENEMY_TYPE_MARKER_SLOT_COUNT];
    int slot;

    if (bsys == NULL || ctx == NULL || ctx->fight_end_flag
     || ctx->battlemon[BATTLER_ENEMY].species == 0
     || ctx->battlemon[BATTLER_ENEMY].hp == 0) {
        sEnemyTypeMarkersDrawn = FALSE;
        sEnemyTypeMarkerGaugeVram = NULL;
        return;
    }
    if (ctx->server_seq_no != CONTROLLER_COMMAND_SELECTION_SCREEN_INPUT) {
        sEnemyTypeMarkersDrawn = FALSE;
        sEnemyTypeMarkerGaugeVram = NULL;
        return;
    }
    gaugeVram = EnemyTypeMarker_GetGaugeVram(bsys);
    if (gaugeVram == NULL) {
        return;
    }
    if (sEnemyTypeMarkersDrawn && sEnemyTypeMarkerGaugeVram == gaugeVram) {
        return;
    }
    EnemyTypeMarker_CollectTypes(&ctx->battlemon[BATTLER_ENEMY], types);

    for (slot = 0; slot < ENEMY_TYPE_MARKER_SLOT_COUNT; slot++) {
        EnemyTypeMarker_DrawSlot(gaugeVram, slot, types[slot]);
    }
    sEnemyTypeMarkersDrawn = TRUE;
    sEnemyTypeMarkerGaugeVram = gaugeVram;
}
