#include "../../include/types.h"
#include "../../include/pokemon.h"

#define FOLLOWER_SELECTOR_OW_NARC_ID 81
#define FOLLOWER_SELECTOR_OW_HEAP_ID 11
#define FOLLOWER_SELECTOR_OW_SMALL_DIM 32
#define FOLLOWER_SELECTOR_OW_LARGE_DIM 64
#define FOLLOWER_SELECTOR_OW_OUTPUT_SIZE 0x200
#define FOLLOWER_SELECTOR_OW_INPUT_MAX_SIZE 0x800
#define FOLLOWER_SELECTOR_OW_FRONT_FRAME_0 2
#define FOLLOWER_SELECTOR_OW_FRONT_FRAME_1 3
#define FOLLOWER_SELECTOR_OW_LARGE_PARAM 0x5208
#define FOLLOWER_SELECTOR_OW_BTX0_MAGIC 0x30585442
#define FOLLOWER_SELECTOR_OW_TEX0_MAGIC 0x30584554
#define FOLLOWER_SELECTOR_RESOLVE_OVERWORLD_TAG_ADDR 0x023C814D

typedef struct FieldSystem FieldSystem;

typedef struct FollowerSelectorFieldLightState {
    s16 lightVectors[12];
    u16 lightColors[4];
    u16 diffuse;
    u16 ambient;
    u16 specular;
    u16 emission;
} FollowerSelectorFieldLightState;

typedef struct FollowerSelectorResource {
    void *resource;
    int type;
    void *extra;
} FollowerSelectorResource;

typedef struct FollowerSelectorCharacterData {
    u16 height;
    u16 width;
    u32 pixelFormat;
    u32 mappingType;
    u32 characterFormat;
    u32 size;
    void *rawData;
} FollowerSelectorCharacterData;

typedef struct FollowerSelectorPaletteData {
    u32 format;
    BOOL extended;
    u32 size;
    void *rawData;
} FollowerSelectorPaletteData;

typedef struct FollowerSelectorCharExtraData {
    FollowerSelectorCharacterData *charData;
    int vram;
} FollowerSelectorCharExtraData;

typedef struct FollowerSelectorPlttExtraData {
    FollowerSelectorPaletteData *paletteData;
    int vram;
    int paletteCount;
} FollowerSelectorPlttExtraData;

typedef struct OVERWORLD_TAG *(*FollowerSelectorResolveOverworldTagFunc)(u16);
typedef void (*FollowerSelectorConvertTextureFunc)(
    const void *source,
    int sourceTileDimension,
    int x,
    int y,
    int width,
    int height,
    void *destination);

#define FOLLOWER_SELECTOR_CONVERT_TEXTURE \
    ((FollowerSelectorConvertTextureFunc)(0x020145B4 | 1))

static u32 FollowerSelectorOverworld_Divide31(u32 value)
{
    return (value + 1 + (value >> 5)) >> 5;
}

static void FollowerSelectorOverworld_CopyBytes(
    u8 *destination,
    const u8 *source,
    u32 size)
{
    while (size-- != 0) {
        *destination++ = *source++;
    }
}

static void FollowerSelectorOverworld_TintPalette(
    FieldSystem *fieldSystem,
    u16 *palette)
{
    FollowerSelectorFieldLightState *lightState;
    u8 shade[3];
    int index;

    if (fieldSystem == NULL || palette == NULL) {
        return;
    }
    lightState = *(FollowerSelectorFieldLightState **)
        ((u8 *)fieldSystem + 0x48);
    if (lightState == NULL) {
        return;
    }
    for (index = 0; index < 3; index++) {
        u8 shift = (u8)(index * 5);
        u32 litDiffuse = ((lightState->diffuse >> shift) & 0x1F)
            * ((lightState->lightColors[0] >> shift) & 0x1F) * 3;
        u32 value = ((lightState->emission >> shift) & 0x1F)
            + ((lightState->ambient >> shift) & 0x1F)
            + FollowerSelectorOverworld_Divide31(litDiffuse >> 2);

        shade[index] = value > 31 ? 31 : (u8)value;
    }
    for (index = 1; index < 16; index++) {
        u16 source = palette[index];
        u16 result = 0;
        int channel;

        for (channel = 0; channel < 3; channel++) {
            u8 shift = (u8)(channel * 5);
            u32 value = FollowerSelectorOverworld_Divide31(
                ((source >> shift) & 0x1F) * shade[channel]);

            result |= (u16)(value << shift);
        }
        palette[index] = result;
    }
}

static void FollowerSelectorOverworld_NormalizeFrame(
    const u8 *source,
    u8 sourceDimension,
    u8 *destination)
{
    int y;

    if (sourceDimension == FOLLOWER_SELECTOR_OW_SMALL_DIM) {
        FOLLOWER_SELECTOR_CONVERT_TEXTURE(source, 4, 0, 0, 4, 4, destination);
        return;
    }
    for (y = 0; y < FOLLOWER_SELECTOR_OW_SMALL_DIM; y++) {
        const u8 *sourceRow = source + y * 64;
        int tileX;

        for (tileX = 0; tileX < 4; tileX++) {
            u8 *destinationTile = destination
                + ((y / 8) * 4 + tileX) * 32 + (y & 7) * 4;
            const u8 *sourceTile = sourceRow + tileX * 8;
            int byte;

            for (byte = 0; byte < 4; byte++) {
                destinationTile[byte] = (sourceTile[byte * 2] & 0xF)
                    | ((sourceTile[byte * 2 + 1] & 0xF) << 4);
            }
        }
    }
}

BOOL __attribute__((section(".follower_selector_ow_entry"), used))
FollowerSelectorOverworld_Extract(
    FieldSystem *fieldSystem,
    u16 species,
    u8 form,
    u8 female,
    u8 shiny,
    u8 isEgg,
    u8 iconPalette,
    void *rawCharResource,
    void *rawPaletteResource)
{
    FollowerSelectorResource *charResource = rawCharResource;
    FollowerSelectorResource *paletteResource = rawPaletteResource;
    FollowerSelectorCharExtraData *charExtra;
    FollowerSelectorPlttExtraData *paletteExtra;
    FollowerSelectorCharacterData *charData;
    FollowerSelectorPaletteData *paletteData;
    u8 *sourcePixels = NULL;
    u16 *destinationPalette;
    struct OVERWORLD_TAG *entry;
    void *narc = NULL;
    u8 header[0x50];
    u32 blockOffset;
    u32 textureOffset;
    u32 paletteOffset;
    u32 frameSize;
    u8 sourceDimension;
    BOOL result = FALSE;

    if (species == 0 || charResource == NULL || paletteResource == NULL) {
        return FALSE;
    }
    charExtra = (FollowerSelectorCharExtraData *)charResource->extra;
    paletteExtra = (FollowerSelectorPlttExtraData *)paletteResource->extra;
    if (charExtra == NULL || paletteExtra == NULL
        || charExtra->charData == NULL || paletteExtra->paletteData == NULL) {
        return FALSE;
    }
    charData = charExtra->charData;
    paletteData = paletteExtra->paletteData;
    if (charData->rawData == NULL
        || charData->size < FOLLOWER_SELECTOR_OW_OUTPUT_SIZE * 2
        || paletteData->rawData == NULL || paletteData->size < 0x20) {
        return FALSE;
    }
    destinationPalette = paletteData->rawData;
    if ((u32)(iconPalette + 1) * 0x20 <= paletteData->size
        && iconPalette != 0) {
        FollowerSelectorOverworld_CopyBytes(
            (u8 *)destinationPalette,
            (const u8 *)(destinationPalette + iconPalette * 16),
            0x20);
    }
    if (isEgg) {
        return TRUE;
    }
    entry = ((FollowerSelectorResolveOverworldTagFunc)
        FOLLOWER_SELECTOR_RESOLVE_OVERWORLD_TAG_ADDR)(
            get_mon_ow_tag(species, form, female));
    if (entry == NULL) {
        return FALSE;
    }
    sourceDimension = entry->callback_params == FOLLOWER_SELECTOR_OW_LARGE_PARAM
        ? FOLLOWER_SELECTOR_OW_LARGE_DIM : FOLLOWER_SELECTOR_OW_SMALL_DIM;
    frameSize = sourceDimension == FOLLOWER_SELECTOR_OW_LARGE_DIM
        ? FOLLOWER_SELECTOR_OW_INPUT_MAX_SIZE
        : FOLLOWER_SELECTOR_OW_OUTPUT_SIZE;
    sourcePixels = sys_AllocMemory(
        FOLLOWER_SELECTOR_OW_HEAP_ID,
        frameSize * 2);
    narc = NARC_ctor(FOLLOWER_SELECTOR_OW_NARC_ID, FOLLOWER_SELECTOR_OW_HEAP_ID);
    if (sourcePixels == NULL || narc == NULL) {
        goto cleanup;
    }
    NARC_ReadFromMember(narc, entry->gfx, 0, sizeof(header), header);
    blockOffset = *(u32 *)(header + 0x10);
    if (*(u32 *)header != FOLLOWER_SELECTOR_OW_BTX0_MAGIC
        || blockOffset > sizeof(header) - 0x3C
        || *(u32 *)(header + blockOffset) != FOLLOWER_SELECTOR_OW_TEX0_MAGIC) {
        goto cleanup;
    }
    textureOffset = blockOffset + *(u32 *)(header + blockOffset + 0x14)
        + frameSize * FOLLOWER_SELECTOR_OW_FRONT_FRAME_0;
    paletteOffset = blockOffset + *(u32 *)(header + blockOffset + 0x38)
        + (shiny ? 0x20 : 0);
    NARC_ReadFromMember(narc, entry->gfx, textureOffset, frameSize * 2,
        sourcePixels);
    NARC_ReadFromMember(narc, entry->gfx, paletteOffset, 0x20,
        destinationPalette);
    FollowerSelectorOverworld_NormalizeFrame(
        sourcePixels,
        sourceDimension,
        charData->rawData);
    FollowerSelectorOverworld_NormalizeFrame(
        sourcePixels + frameSize
            * (FOLLOWER_SELECTOR_OW_FRONT_FRAME_1
                - FOLLOWER_SELECTOR_OW_FRONT_FRAME_0),
        sourceDimension,
        (u8 *)charData->rawData + FOLLOWER_SELECTOR_OW_OUTPUT_SIZE);
    FollowerSelectorOverworld_TintPalette(fieldSystem, destinationPalette);
    result = TRUE;

cleanup:
    if (narc != NULL) {
        NARC_dtor(narc);
    }
    if (sourcePixels != NULL) {
        sys_FreeMemoryEz(sourcePixels);
    }
    return result;
}
