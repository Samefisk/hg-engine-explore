#include "../include/player_health_presentation.h"

#include "../include/overworld_follower_selector.h"
#include "../include/pokemon.h"

/* These managers belong to the stock field renderer. Never create or reset them
 * here: the map, weather, and selector also submit to the same OAM buffer. */
#define PLAYER_HEALTH_MAIN_OAM_MANAGER_PTR 0x021D0EB0
#define PLAYER_HEALTH_MAIN_OBJ 1
#define PLAYER_HEALTH_PLTT_RES_ID 0x7F41
#define PLAYER_HEALTH_TILE_BYTES 1024
#define PLAYER_HEALTH_EDGE_TILE_BYTES 2560
#define PLAYER_HEALTH_EDGE_CORNER_BYTES 512
#define PLAYER_HEALTH_EDGE_HORIZONTAL_BYTES 1024
#define PLAYER_HEALTH_EDGE_DEPTH 32
#define PLAYER_HEALTH_EDGE_BLEND 0x3f40
#define PLAYER_HEALTH_BAR_WIDTH 44
#define PLAYER_HEALTH_BAR_X 8
#define PLAYER_HEALTH_BAR_Y 8
#define PLAYER_HEALTH_HEAP_ID 11
#define PLAYER_HEALTH_HIT_FLASH_FRAMES 16

typedef struct PlayerHealthCharBlock {
    u32 size;
    u32 offset;
    u16 vram;
    u16 isAtEnd;
} PlayerHealthCharBlock;

typedef struct PlayerHealthPaletteData {
    u32 fmt;
    BOOL extended;
    u32 size;
    void *raw;
} PlayerHealthPaletteData;

typedef struct PlayerHealthPaletteTask {
    PlayerHealthPaletteData *data;
    u32 vram;
    int count;
    int id;
} PlayerHealthPaletteTask;

typedef struct PlayerHealthOam {
    u16 attr0;
    u16 attr1;
    u16 attr2;
    u16 affine;
} PlayerHealthOam;

extern BOOL LONG_CALL sub_02021AC8(u32 size, BOOL atEnd, u32 vram,
    PlayerHealthCharBlock *block);
extern void LONG_CALL sub_02021B5C(PlayerHealthCharBlock *block);
extern BOOL LONG_CALL
    ObjPlttTransfer_CreateTaskAndDoTransferFromTemplate_ExtPlttBanned(
        const PlayerHealthPaletteTask *task);
extern void LONG_CALL ObjPlttTransfer_FreeTaskByID(int id);
extern void *LONG_CALL ObjPlttTransfer_GetPlttProxyByID(int id);
extern u32 LONG_CALL ObjPlttTransfer_GetPaletteVramOffset(void *proxy,
    u32 vram);
extern BOOL LONG_CALL NNS_G2dEntryOamManagerOamWithAffineIdx(void *manager,
    const PlayerHealthOam *oam, u16 affine);
extern void LONG_CALL GX_LoadOBJ(const void *source, u32 offset, u32 size);
extern void LONG_CALL DC_FlushRange(const void *source, u32 size);

typedef struct PlayerHealthPresentationRuntime {
    FieldSystem *field;
    PlayerHealthCharBlock charBlock;
    PlayerHealthPaletteData paletteData;
    PlayerHealthPaletteTask paletteTask;
    PlayerHealthPresentationReceipt receipt;
    u8 bound;
    u8 textureKey;
    u8 paletteSlot;
} PlayerHealthPresentationRuntime;

static PlayerHealthPresentationRuntime sPresentation
    __attribute__((section(".player_health_state"))) = {0};

#define sField sPresentation.field
#define sCharBlock sPresentation.charBlock
#define sPaletteData sPresentation.paletteData
#define sPaletteTask sPresentation.paletteTask
#define sReceipt sPresentation.receipt
#define sBound sPresentation.bound
#define sTextureKey sPresentation.textureKey
#define sPaletteSlot sPresentation.paletteSlot

static u8 sHitFlashFrames
    __attribute__((section(".player_health_state"))) = 0;
static u8 sUploadedHitFlash
    __attribute__((section(".player_health_state"))) = 0;
static PlayerHealthCharBlock sImpactCharBlock
    __attribute__((section(".player_health_extended_state"))) = {0};
static u8 sImpactBound
    __attribute__((section(".player_health_extended_state"))) = 0;
static u8 sImpactSubmitted
    __attribute__((section(".player_health_extended_state"))) = 0;
static u8 sImpactBlendOwned
    __attribute__((section(".player_health_extended_state"))) = 0;
static u16 sImpactSavedAlpha
    __attribute__((section(".player_health_extended_state"))) = 0;
static u16 sImpactExpectedAlpha
    __attribute__((section(".player_health_extended_state"))) = 0;
static u8 sImpactReleasePending
    __attribute__((section(".player_health_extended_state"))) = 0;
static u8 sImpactSuppressed
    __attribute__((section(".player_health_extended_state"))) = 0;

/* Keep the colors in the reserved Throw text slot. Only the heap copy is
 * passed to DMA. */
static const u16 sHealthBarPalette[16]
    __attribute__((section(".player_health_throw_text"))) = {
    0,
    3 | (4 << 5) | (5 << 10),
    8 | (9 << 5) | (10 << 10),
    30 | (30 << 5) | (29 << 10),
    5 | (25 << 5) | (8 << 10),
    29 | (25 << 5) | (4 << 10),
    30 | (5 << 5) | (5 << 10),
    31 | (18 << 5) | (2 << 10),
    2 | (3 << 5) | (4 << 10),
    15 | (31 << 5) | (17 << 10),
    2 | (17 << 5) | (5 << 10),
    31 | (31 << 5) | (13 << 10),
    22 | (18 << 5) | (2 << 10),
    31 | (15 << 5) | (15 << 10),
    21 | (2 << 5) | (3 << 10),
    0,
};

/* Ordered coverage gives the red tint a soft inner edge without changing
 * the field's palettes. OBJ alpha then tints the visible pixels. */
static const u8 sEdgeDither[64]
    __attribute__((section(".player_health_throw_text"))) = {
    0, 48, 12, 60, 3, 51, 15, 63,
    32, 16, 44, 28, 35, 19, 47, 31,
    8, 56, 4, 52, 11, 59, 7, 55,
    40, 24, 36, 20, 43, 27, 39, 23,
    2, 50, 14, 62, 1, 49, 13, 61,
    34, 18, 46, 30, 33, 17, 45, 29,
    10, 58, 6, 54, 9, 57, 5, 53,
    42, 26, 38, 22, 41, 25, 37, 21,
};

/* A normal loop can become the cross-mode memcpy veneer at link time. Read
 * the ITCM source through volatile so this stays a small CPU copy. */
static void __attribute__((noinline, section(".player_health_palette_copy")))
PlayerHealthPresentation_CopyPalette(u16 *destination)
{
    const volatile u16 *source = sHealthBarPalette;
    u32 i;

    for (i = 0; i < 16; i++) {
        destination[i] = source[i];
    }
}

/* The first two words of the local FieldSystem are the vanilla unk0/unk4
 * pointers. unk4+8 is FieldDrawMapNameInfo*, whose first word is onScreen. */
static BOOL PlayerHealthPresentation_MapNameVisible(FieldSystem *fieldSystem)
{
    const void *fieldSub4 = *(const void *const *)((const u8 *)fieldSystem + 4);
    const void *mapName;

    if (fieldSub4 == NULL) {
        return FALSE;
    }
    mapName = *(const void *const *)((const u8 *)fieldSub4 + 8);
    return mapName != NULL && *(const u32 *)mapName != 0;
}

static u8 PlayerHealthPresentation_FillWidth(const PlayerHealthState *health)
{
    if (health == NULL || health->recoveryPending) {
        return 0;
    }
    return (u8)(((u32)health->hp * PLAYER_HEALTH_BAR_WIDTH
        + PLAYER_HEALTH_MAX_HP - 1) / PLAYER_HEALTH_MAX_HP);
}

static u32 PlayerHealthPresentation_MappingBlock(void)
{
    u32 display = reg_GX_DISPCNT;
    u32 mapping = (display >> 20) & 3;

    if ((display & REG_GX_DISPCNT_OBJMAP_CH_MASK) == 0) {
        return 0;
    }
    return 32u << mapping;
}

static void PlayerHealthPresentation_SetPixel(u8 *pixels, u32 x, u32 y,
    u8 ink)
{
    u32 index = ((y / 8) * 8 + x / 8) * 32
        + (y % 8) * 4 + (x % 8) / 2;

    if (x & 1) {
        pixels[index] = (pixels[index] & 0x0f) | (ink << 4);
    } else {
        pixels[index] = (pixels[index] & 0xf0) | ink;
    }
}

static void PlayerHealthPresentation_SetEdgePixel(u8 *pixels, u32 tilesWide,
    u32 x, u32 y)
{
    u32 index = ((y / 8) * tilesWide + x / 8) * 32
        + (y % 8) * 4 + (x % 8) / 2;

    if (x & 1) {
        pixels[index] = (pixels[index] & 0x0f) | (6 << 4);
    } else {
        pixels[index] = (pixels[index] & 0xf0) | 6;
    }
}

static void PlayerHealthPresentation_FillTile(u8 *pixels, u8 hp,
    u8 fill, BOOL danger, BOOL hitFlash)
{
    u32 x, y;
    /* Match the stock HP bar's light/body/shade bands and color changes. */
    u8 fillInk = hitFlash ? 3 : hp > 50 ? 4 : hp > 20 ? 5 : 6;
    u8 lightInk = hitFlash ? 3 : hp > 50 ? 9 : hp > 20 ? 11 : 13;
    u8 shadeInk = hitFlash ? 3 : hp > 50 ? 10 : hp > 20 ? 12 : 14;
    u8 borderInk = hitFlash ? 6 : danger ? 7 : 3;

    for (x = 0; x < PLAYER_HEALTH_TILE_BYTES; x++) {
        pixels[x] = 0;
    }
    for (y = 4; y <= 20; y++) {
        for (x = 1; x <= 62; x++) {
            u8 ink = x == 1 || x == 62 || y == 4 || y == 20 ? 1 : 2;

            if (x >= 14 && x <= 61 && y >= 6 && y <= 17) {
                ink = x == 14 || x == 61 || y == 6 || y == 17
                    ? borderInk : 8;
            }
            if (x >= 16 && x < 16u + fill && y >= 9 && y <= 13) {
                ink = y == 9 ? lightInk : y == 13 ? shadeInk : fillInk;
            }
            /* Tiny HP label to distinguish this from a progress meter. */
            if ((x == 4 || x == 7 || (y == 11 && x >= 4 && x <= 7))
                    && y >= 8 && y <= 14) {
                ink = 3;
            }
            if ((x == 9 && y >= 8 && y <= 14)
                    || (x >= 9 && x <= 12 && (y == 8 || y == 11))
                    || (x == 12 && y >= 8 && y <= 11)) {
                ink = 3;
            }
            PlayerHealthPresentation_SetPixel(pixels, x, y, ink);
        }
    }
}

static BOOL PlayerHealthPresentation_Upload(u8 hp, u8 fill, BOOL danger,
    BOOL hitFlash)
{
    u8 *pixels = sys_AllocMemory(PLAYER_HEALTH_HEAP_ID,
        PLAYER_HEALTH_TILE_BYTES);

    if (pixels == NULL) {
        return FALSE;
    }
    PlayerHealthPresentation_FillTile(pixels, hp, fill, danger, hitFlash);
    DC_FlushRange(pixels, PLAYER_HEALTH_TILE_BYTES);
    GX_LoadOBJ(pixels, sCharBlock.offset, PLAYER_HEALTH_TILE_BYTES);
    sys_FreeMemoryEz(pixels);
    sTextureKey = (u8)((u32)hp * 2 + (danger ? 1u : 0u));
    sUploadedHitFlash = hitFlash;
    return TRUE;
}

static BOOL PlayerHealthPresentation_Bind(FieldSystem *fieldSystem)
{
    void *proxy;
    u16 *palette;
    u32 blockSize;

    if (sBound) {
        return sField == fieldSystem;
    }
    blockSize = PlayerHealthPresentation_MappingBlock();
    if (blockSize == 0 || !sub_02021AC8(PLAYER_HEALTH_TILE_BYTES,
            TRUE, PLAYER_HEALTH_MAIN_OBJ, &sCharBlock)) {
        return FALSE;
    }
    /* The overlay state is in ITCM. Stock palette transfer uses DMA for 32
     * bytes, so its source must live in ordinary, DMA-readable heap RAM. */
    palette = sys_AllocMemory(PLAYER_HEALTH_HEAP_ID,
        sizeof(sHealthBarPalette));
    if (palette == NULL) {
        sub_02021B5C(&sCharBlock);
        return FALSE;
    }
    PlayerHealthPresentation_CopyPalette(palette);
    /* NNS_G2dLoadPalette flushes this buffer before its DMA transfer. */
    sPaletteData.fmt = 3; /* GX_TEXFMT_PLTT16 */
    sPaletteData.extended = FALSE;
    sPaletteData.size = sizeof(sHealthBarPalette);
    sPaletteData.raw = palette;
    sPaletteTask.data = &sPaletteData;
    sPaletteTask.vram = PLAYER_HEALTH_MAIN_OBJ;
    sPaletteTask.count = 1;
    sPaletteTask.id = PLAYER_HEALTH_PLTT_RES_ID;
    if (!ObjPlttTransfer_CreateTaskAndDoTransferFromTemplate_ExtPlttBanned(
            &sPaletteTask)) {
        goto fail;
    }
    proxy = ObjPlttTransfer_GetPlttProxyByID(PLAYER_HEALTH_PLTT_RES_ID);
    if (proxy == NULL) {
        ObjPlttTransfer_FreeTaskByID(PLAYER_HEALTH_PLTT_RES_ID);
        goto fail;
    }
    sPaletteSlot = (u8)ObjPlttTransfer_GetPaletteVramOffset(proxy,
        PLAYER_HEALTH_MAIN_OBJ);
    if (sPaletteSlot >= 16 || sCharBlock.offset / blockSize > 1023) {
        ObjPlttTransfer_FreeTaskByID(PLAYER_HEALTH_PLTT_RES_ID);
        goto fail;
    }
    sBound = TRUE;
    sField = fieldSystem;
    sTextureKey = 0xff;
    return TRUE;

fail:
    sys_FreeMemoryEz(palette);
    sPaletteData.raw = NULL;
    sub_02021B5C(&sCharBlock);
    return FALSE;
}

/* The edge tint stays separate from the player's MapObject. Riding, doors,
 * and blackout own that object's visibility. One corner and two straight
 * strips are reused with OAM flips to cover the screen perimeter. */
static BOOL __attribute__((noinline,
    section(".player_health_extended_text")))
PlayerHealthPresentation_BindImpact(u32 blockSize)
{
    u8 *pixels;
    u32 x, y, i;

    if (sImpactBound) {
        return TRUE;
    }
    if (!sub_02021AC8(PLAYER_HEALTH_EDGE_TILE_BYTES, TRUE,
            PLAYER_HEALTH_MAIN_OBJ, &sImpactCharBlock)) {
        return FALSE;
    }
    if ((sImpactCharBlock.offset + PLAYER_HEALTH_EDGE_TILE_BYTES - 1)
            / blockSize > 1023) {
        sub_02021B5C(&sImpactCharBlock);
        return FALSE;
    }
    pixels = sys_AllocMemory(PLAYER_HEALTH_HEAP_ID,
        PLAYER_HEALTH_EDGE_TILE_BYTES);
    if (pixels == NULL) {
        sub_02021B5C(&sImpactCharBlock);
        return FALSE;
    }
    for (i = 0; i < PLAYER_HEALTH_EDGE_TILE_BYTES; i++) {
        pixels[i] = 0;
    }
    for (y = 0; y < PLAYER_HEALTH_EDGE_DEPTH; y++) {
        for (x = 0; x < PLAYER_HEALTH_EDGE_DEPTH; x++) {
            u32 distance = x < y ? x : y;
            if (sEdgeDither[(y & 7) * 8 + (x & 7)]
                    < (PLAYER_HEALTH_EDGE_DEPTH - distance) * 2) {
                PlayerHealthPresentation_SetEdgePixel(pixels, 4, x, y);
            }
        }
    }
    for (y = 0; y < PLAYER_HEALTH_EDGE_DEPTH; y++) {
        for (x = 0; x < 64; x++) {
            if (sEdgeDither[(y & 7) * 8 + (x & 7)]
                    < (PLAYER_HEALTH_EDGE_DEPTH - y) * 2) {
                PlayerHealthPresentation_SetEdgePixel(
                    pixels + PLAYER_HEALTH_EDGE_CORNER_BYTES, 8, x, y);
            }
        }
    }
    for (y = 0; y < 64; y++) {
        for (x = 0; x < PLAYER_HEALTH_EDGE_DEPTH; x++) {
            if (sEdgeDither[(y & 7) * 8 + (x & 7)]
                    < (PLAYER_HEALTH_EDGE_DEPTH - x) * 2) {
                PlayerHealthPresentation_SetEdgePixel(
                    pixels + PLAYER_HEALTH_EDGE_CORNER_BYTES
                        + PLAYER_HEALTH_EDGE_HORIZONTAL_BYTES,
                    4, x, y);
            }
        }
    }
    DC_FlushRange(pixels, PLAYER_HEALTH_EDGE_TILE_BYTES);
    GX_LoadOBJ(pixels, sImpactCharBlock.offset,
        PLAYER_HEALTH_EDGE_TILE_BYTES);
    sys_FreeMemoryEz(pixels);
    sImpactBound = TRUE;
    return TRUE;
}

static void __attribute__((noinline,
    section(".player_health_extended_text")))
PlayerHealthPresentation_EndImpactBlend(void)
{
    if (sImpactBlendOwned && reg_G2_BLDCNT == PLAYER_HEALTH_EDGE_BLEND
            && reg_G2_BLDALPHA == sImpactExpectedAlpha) {
        reg_G2_BLDCNT = 0;
        reg_G2_BLDALPHA = sImpactSavedAlpha;
    }
    sImpactBlendOwned = FALSE;
    sImpactReleasePending = FALSE;
}

/* Keep alpha at zero for one draw update after the last edge sprites. This
 * lets the OAM manager remove them before normal blend state returns. */
static void __attribute__((noinline,
    section(".player_health_extended_text")))
PlayerHealthPresentation_ReleaseImpactBlend(void)
{
    if (!sImpactBlendOwned) {
        return;
    }
    if (reg_G2_BLDCNT != PLAYER_HEALTH_EDGE_BLEND
            || reg_G2_BLDALPHA != sImpactExpectedAlpha) {
        sImpactBlendOwned = FALSE;
        sImpactReleasePending = FALSE;
        return;
    }
    if (sImpactReleasePending) {
        PlayerHealthPresentation_EndImpactBlend();
        return;
    }
    sImpactExpectedAlpha = 16 << 8;
    reg_G2_BLDALPHA = sImpactExpectedAlpha;
    sImpactReleasePending = TRUE;
}

static BOOL __attribute__((noinline,
    section(".player_health_extended_text")))
PlayerHealthPresentation_UpdateImpactBlend(u8 frames)
{
    u16 strength;

    if (sImpactBlendOwned
            && (reg_G2_BLDCNT != PLAYER_HEALTH_EDGE_BLEND
                || reg_G2_BLDALPHA != sImpactExpectedAlpha)) {
        sImpactBlendOwned = FALSE;
        return FALSE;
    }
    if (!sImpactBlendOwned) {
        if (reg_G2_BLDCNT != 0) {
            return FALSE;
        }
        sImpactSavedAlpha = reg_G2_BLDALPHA;
        reg_G2_BLDCNT = PLAYER_HEALTH_EDGE_BLEND;
        sImpactBlendOwned = TRUE;
    }
    strength = frames > 12 ? 7 : frames > 8 ? 6 : frames > 4 ? 4 : 2;
    sImpactExpectedAlpha = strength | ((16 - strength) << 8);
    reg_G2_BLDALPHA = sImpactExpectedAlpha;
    sImpactReleasePending = FALSE;
    return TRUE;
}

void PlayerHealthPresentation_End(FieldSystem *fieldSystem)
{
    if (sField != NULL && fieldSystem != NULL && sField != fieldSystem) {
        return;
    }
    if (sBound) {
        ObjPlttTransfer_FreeTaskByID(PLAYER_HEALTH_PLTT_RES_ID);
        sub_02021B5C(&sCharBlock);
    }
    PlayerHealthPresentation_EndImpactBlend();
    if (sImpactBound) {
        sub_02021B5C(&sImpactCharBlock);
        sImpactBound = FALSE;
    }
    sImpactSubmitted = 0;
    if (sPaletteData.raw != NULL) {
        sys_FreeMemoryEz(sPaletteData.raw);
        sPaletteData.raw = NULL;
    }
    sBound = FALSE;
    sField = NULL;
    sTextureKey = 0xff;
    sHitFlashFrames = 0;
    sImpactSuppressed = 0;
    sUploadedHitFlash = 0;
    sReceipt.requestedFill = 0;
    sReceipt.drawnFill = 0;
    sReceipt.danger = 0;
    sReceipt.submittedSprites = 0;
}

static BOOL PlayerHealthPresentation_Submit(u32 blockSize, void *manager)
{
    PlayerHealthOam oam;
    u32 tile = sCharBlock.offset / blockSize;

    oam.attr0 = PLAYER_HEALTH_BAR_Y | (1 << 14);
    oam.attr1 = PLAYER_HEALTH_BAR_X | (3 << 14); /* 64x32 wide OBJ. */
    oam.attr2 = (u16)(tile | ((u16)sPaletteSlot << 12));
    oam.affine = 0;
    return NNS_G2dEntryOamManagerOamWithAffineIdx(manager, &oam,
        0xfffe);
}

static BOOL __attribute__((noinline,
    section(".player_health_extended_text")))
PlayerHealthPresentation_SubmitEdgeSprite(u32 blockSize, void *manager,
    u32 tileOffset, u16 x, u16 y, u16 shape, u16 size, u16 flip)
{
    PlayerHealthOam oam;
    u32 tile = (sImpactCharBlock.offset + tileOffset) / blockSize;

    oam.attr0 = y | (1 << 10) | (shape << 14); /* Translucent OBJ. */
    oam.attr1 = x | (flip << 12) | (size << 14);
    oam.attr2 = (u16)(tile | ((u16)sPaletteSlot << 12));
    oam.affine = 0;
    return NNS_G2dEntryOamManagerOamWithAffineIdx(manager, &oam, 0xfffe);
}

static BOOL __attribute__((noinline,
    section(".player_health_extended_text")))
PlayerHealthPresentation_SubmitImpact(u32 blockSize, void *manager)
{
    u32 x, y;
    u32 horizontal = PLAYER_HEALTH_EDGE_CORNER_BYTES;
    u32 vertical = horizontal + PLAYER_HEALTH_EDGE_HORIZONTAL_BYTES;
    BOOL complete = TRUE;

    /* Four 32x32 corners. Flip bits: 1 horizontal, 2 vertical. */
    complete &= PlayerHealthPresentation_SubmitEdgeSprite(blockSize,
        manager, 0, 0, 0, 0, 2, 0);
    complete &= PlayerHealthPresentation_SubmitEdgeSprite(blockSize,
        manager, 0, 224, 0, 0, 2, 1);
    complete &= PlayerHealthPresentation_SubmitEdgeSprite(blockSize,
        manager, 0, 0, 160, 0, 2, 2);
    complete &= PlayerHealthPresentation_SubmitEdgeSprite(blockSize,
        manager, 0, 224, 160, 0, 2, 3);
    /* Three 64x32 strips across each horizontal edge. */
    for (x = 32; x <= 160; x += 64) {
        complete &= PlayerHealthPresentation_SubmitEdgeSprite(blockSize,
            manager, horizontal, x, 0, 1, 3, 0);
        complete &= PlayerHealthPresentation_SubmitEdgeSprite(blockSize,
            manager, horizontal, x, 160, 1, 3, 2);
    }
    /* Two 32x64 strips on each vertical edge. */
    for (y = 32; y <= 96; y += 64) {
        complete &= PlayerHealthPresentation_SubmitEdgeSprite(blockSize,
            manager, vertical, 0, y, 2, 3, 0);
        complete &= PlayerHealthPresentation_SubmitEdgeSprite(blockSize,
            manager, vertical, 224, y, 2, 3, 1);
    }
    return complete;
}

void PlayerHealthPresentation_Update(FieldSystem *fieldSystem,
    const PlayerHealthState *health, BOOL danger)
{
    void *manager;
    u32 blockSize;
    u8 hp = health == NULL ? 0 : health->hp;
    u8 fill = PlayerHealthPresentation_FillWidth(health);
    u8 warning = health != NULL && !health->recoveryPending && danger ? 1 : 0;
    u8 hitFlash;
    u8 impactActive;
    BOOL mapNameVisible;
    BOOL barReady;

    if (health != NULL && health->hitThisFrame) {
        sHitFlashFrames = PLAYER_HEALTH_HIT_FLASH_FRAMES;
        sImpactSuppressed = 0;
    }
    impactActive = sHitFlashFrames != 0;
    hitFlash = sHitFlashFrames > PLAYER_HEALTH_HIT_FLASH_FRAMES - 4;
    if (sHitFlashFrames != 0) {
        sHitFlashFrames--;
    }

    sReceipt.requestedFill = fill;
    sReceipt.drawnFill = 0;
    sReceipt.danger = warning;
    sReceipt.submittedSprites = 0;
    sImpactSubmitted = 0;
    if (fieldSystem != NULL
        && OverworldFollowerSelector_IsActiveFlagSet()) {
        PlayerHealthPresentation_End(fieldSystem);
        return;
    }
    if (fieldSystem == NULL || fill == 0) {
        PlayerHealthPresentation_EndImpactBlend();
        return;
    }
    mapNameVisible = PlayerHealthPresentation_MapNameVisible(fieldSystem);
    if (!PlayerHealthPresentation_Bind(fieldSystem)) {
        PlayerHealthPresentation_EndImpactBlend();
        return;
    }
    blockSize = PlayerHealthPresentation_MappingBlock();
    manager = *(void **)PLAYER_HEALTH_MAIN_OAM_MANAGER_PTR;
    if (manager == NULL || blockSize == 0) {
        PlayerHealthPresentation_EndImpactBlend();
        return;
    }
    if (!mapNameVisible) {
        barReady = (sTextureKey == (u8)((u32)hp * 2 + warning)
                && sUploadedHitFlash == hitFlash)
            || PlayerHealthPresentation_Upload(hp, fill, warning, hitFlash);
        if (barReady && PlayerHealthPresentation_Submit(blockSize, manager)) {
            sReceipt.submittedSprites = 1;
            sReceipt.drawnFill = fill;
        }
    }
    if (impactActive && !sImpactSuppressed
            && PlayerHealthPresentation_BindImpact(blockSize)
            && PlayerHealthPresentation_UpdateImpactBlend(
                sHitFlashFrames + 1)) {
        sImpactSubmitted = PlayerHealthPresentation_SubmitImpact(blockSize,
            manager);
        if (!sImpactSubmitted) {
            sImpactSuppressed = 1;
            PlayerHealthPresentation_ReleaseImpactBlend();
        }
    } else {
        PlayerHealthPresentation_ReleaseImpactBlend();
    }
}

const PlayerHealthPresentationReceipt *PlayerHealthPresentation_GetReceipt(void)
{
    return &sReceipt;
}
