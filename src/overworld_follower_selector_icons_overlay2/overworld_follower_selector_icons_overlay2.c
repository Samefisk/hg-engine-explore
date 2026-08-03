#include "../../include/types.h"
#include "../../include/pokemon.h"
#include "../../include/constants/sndseq.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_follower_selector.h"
#include "../../include/overworld_wild_helper.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/sound.h"

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
#define FOLLOWER_RELEASE_BOUNCE_ASCENT_FRAMES 30
#define FOLLOWER_RELEASE_BOUNCE_APEX_FRAME \
    (FOLLOWER_RELEASE_BOUNCE_ASCENT_FRAMES - 1)
#define FOLLOWER_RELEASE_BOUNCE_APEX_HOLD_FRAMES 4
#define FOLLOWER_RELEASE_BOUNCE_DESCENT_FRAME \
    (FOLLOWER_RELEASE_BOUNCE_ASCENT_FRAMES \
        + FOLLOWER_RELEASE_BOUNCE_APEX_HOLD_FRAMES)
#define FOLLOWER_RELEASE_BOUNCE_CAUGHT_ARC_FRAMES 18
#define FOLLOWER_RELEASE_BOUNCE_SOURCE_APEX_FRAME 5
#define FOLLOWER_RELEASE_BOUNCE_MOTION_FRAMES \
    (FOLLOWER_RELEASE_BOUNCE_DESCENT_FRAME \
        + FOLLOWER_RELEASE_BOUNCE_CAUGHT_ARC_FRAMES \
        - FOLLOWER_RELEASE_BOUNCE_SOURCE_APEX_FRAME - 1)
#define FOLLOWER_RELEASE_BOUNCE_READY_DELAY_FRAMES 16
#define FOLLOWER_RELEASE_BOUNCE_TOTAL_FRAMES \
    (FOLLOWER_RELEASE_BOUNCE_APEX_FRAME \
        + FOLLOWER_RELEASE_BOUNCE_READY_DELAY_FRAMES)
#define FOLLOWER_RELEASE_BOUNCE_PROGRESS_MAX 256
#define FOLLOWER_RELEASE_BOUNCE_DISTANCE_TILES 3
#define FOLLOWER_RELEASE_BOUNCE_ROTATION_35_DEGREES 0x18E4
#define FOLLOWER_RELEASE_BOUNCE_IMPACT_HEIGHT_FX32 0x8000
#define FOLLOWER_RELEASE_RETURN_HAND_HEIGHT_FX32 0x8000

typedef struct FieldSystem FieldSystem;

/* Prefix-compatible view of overlay 151's private Player Ball state. */
typedef struct FollowerReleaseBounceProjectile {
    u32 opaquePointers[6];
    s32 startX;
    s32 startY;
    s32 startZ;
    s32 targetX;
    s32 targetY;
    s32 targetZ;
    s32 startHeight;
    u32 rotationMatrix[9];
    s16 rotation;
    u16 mapId;
    u16 mapGeneration;
    u16 impactEncounterGeneration;
    s8 impactSlot;
    u8 elapsedFrames;
    u8 totalFrames;
    u8 phase;
    u8 objectId;
    u8 shakeChecks;
    u8 shakeIndex;
    u8 incomingDirection;
    u8 targetWhiteActive;
} FollowerReleaseBounceProjectile;

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

/* Match the original Y-hit rebound's acceleration and broad apex exactly. */
static const u16 sFollowerReleaseBounceProgress[] = {
    0, 1, 4, 10, 21, 39, 63, 90, 117, 143,
    165, 185, 201, 215, 225, 232, 237, 241, 244, 246,
    247, 248, 249, 250, 251, 252, 253, 254, 255, 256,
};

static const u16 sFollowerReleaseBounceRotationProgress[] = {
    0, 32, 51, 68, 84, 99, 112, 125, 136, 146,
    157, 166, 176, 184, 193, 200, 208, 214, 221, 226,
    232, 236, 241, 244, 248, 251, 253, 255, 256, 256,
};

static const s32 sFollowerReleaseBounceHeightFx32[] = {
    88473, 120422, 140083, 151142, 156057, 157286, 157163, 156794,
    155811, 153354, 144998, 127795, 100761, 58982, 6144, 2211, 614, 122,
};

static int FollowerReleaseBounce_DeltaX(u8 direction)
{
    return direction == OW_WILD_HELPER_DIRECTION_LEFT
        ? -1
        : direction == OW_WILD_HELPER_DIRECTION_RIGHT ? 1 : 0;
}

static int FollowerReleaseBounce_DeltaY(u8 direction)
{
    return direction == OW_WILD_HELPER_DIRECTION_UP
        ? -1
        : direction == OW_WILD_HELPER_DIRECTION_DOWN ? 1 : 0;
}

static BOOL FollowerReleaseBounce_IsTileAvailable(
    FieldSystem *fieldSystem,
    LocalMapObject *ballObject,
    int x,
    int y)
{
    const OverworldFollowerSelectorOverlayEntry *selectorEntry =
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY;
    MapObjectMan *manager;
    int i;

    if (fieldSystem == NULL
        || fieldSystem->mapObjectMan == NULL
        || selectorEntry->isReleaseTileAvailable == NULL
        || !selectorEntry->isReleaseTileAvailable(fieldSystem, x, y)) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    if (manager->objects == NULL) {
        return FALSE;
    }
    for (i = 0; i < (int)manager->object_count; i++) {
        LocalMapObject *object = &manager->objects[i];

        if (object == ballObject
            || (fieldSystem->playerAvatar != NULL
                && object == fieldSystem->playerAvatar->mapObject)
            || (object->flags & MAPOBJECTFLAG_ACTIVE) == 0) {
            continue;
        }
        if (MapObject_GetCurrentX(object) == x
            && MapObject_GetCurrentY(object) == y) {
            return FALSE;
        }
    }
    return TRUE;
}

static BOOL FollowerReleaseBounce_FindTile(
    FieldSystem *fieldSystem,
    LocalMapObject *ballObject,
    LocalMapObject *targetObject,
    u8 incomingDirection,
    int *bounceX,
    int *bounceY)
{
    int incomingX;
    int incomingY;
    int targetX;
    int targetY;
    int candidateX[4];
    int candidateY[4];
    int i;

    if (targetObject == NULL
        || bounceX == NULL
        || bounceY == NULL
        || incomingDirection > OW_WILD_HELPER_DIRECTION_RIGHT) {
        return FALSE;
    }
    incomingX = FollowerReleaseBounce_DeltaX(incomingDirection);
    incomingY = FollowerReleaseBounce_DeltaY(incomingDirection);
    incomingX *= FOLLOWER_RELEASE_BOUNCE_DISTANCE_TILES;
    incomingY *= FOLLOWER_RELEASE_BOUNCE_DISTANCE_TILES;
    targetX = MapObject_GetCurrentX(targetObject);
    targetY = MapObject_GetCurrentY(targetObject);

    candidateX[0] = targetX - incomingX;
    candidateY[0] = targetY - incomingY;
    candidateX[1] = targetX - incomingY;
    candidateY[1] = targetY + incomingX;
    candidateX[2] = targetX + incomingY;
    candidateY[2] = targetY - incomingX;
    candidateX[3] = targetX + incomingX;
    candidateY[3] = targetY + incomingY;

    for (i = 0; i < 4; i++) {
        if (FollowerReleaseBounce_IsTileAvailable(
                fieldSystem,
                ballObject,
                candidateX[i],
                candidateY[i])) {
            *bounceX = candidateX[i];
            *bounceY = candidateY[i];
            return TRUE;
        }
    }
    return FALSE;
}

BOOL __attribute__((section(".follower_release_bounce_entry"), used))
OverworldWildSpawns_StartFollowerReleaseBounce(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    void *rawProjectile,
    int slot)
{
    FollowerReleaseBounceProjectile *projectile = rawProjectile;
    LocalMapObject *ballObject;
    LocalMapObject *targetObject;
    s32 impactX;
    s32 impactZ;
    int bounceX;
    int bounceY;

    if (state == NULL
        || projectile == NULL
        || (state->followerReleaseState
                & OW_WILD_FOLLOWER_RELEASE_STATE_MASK)
            != OW_WILD_FOLLOWER_RELEASE_FLYING
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || slot == OW_WILD_FOLLOWER_SLOT
        || !state->spawns[slot].active
        || state->spawns[slot].object == NULL) {
        return FALSE;
    }
    ballObject = (LocalMapObject *)projectile->opaquePointers[4];
    targetObject = state->spawns[slot].object;
    if (ballObject == NULL
        || (targetObject->flags & MAPOBJECTFLAG_ACTIVE) == 0
        || targetObject->id != OW_WILD_OBJECT_ID_START + slot) {
        return FALSE;
    }

    state->spawns[slot].active |=
        OW_WILD_SPAWN_AGGRO_FLAG | OW_WILD_SPAWN_AGGRO_PENDING_FLAG;
    state->followerReleaseState |=
        OW_WILD_FOLLOWER_RELEASE_AGGRO_FLAG;
    if (!FollowerReleaseBounce_FindTile(
            fieldSystem,
            ballObject,
            targetObject,
            projectile->incomingDirection,
            &bounceX,
            &bounceY)) {
        return FALSE;
    }
    /* This byte becomes the follower pass-through restore flag after launch. */
    projectile->incomingDirection = TRUE;

    impactX = (s32)targetObject->posVec[0];
    impactZ = (s32)targetObject->posVec[2];
    ballObject->posVec[0] = (u32)impactX;
    ballObject->posVec[1] = targetObject->posVec[1];
    ballObject->posVec[2] = (u32)impactZ;
    ballObject->hCurr = targetObject->hCurr;
    projectile->startX = impactX;
    projectile->startY = (s32)targetObject->posVec[1];
    projectile->startZ = impactZ;
    projectile->targetX = (s32)bounceX * 0x10000 + 0x8000;
    projectile->targetY = projectile->startY;
    projectile->targetZ = (s32)bounceY * 0x10000 + 0x8000;
    ballObject->faceVec[1] = targetObject->faceVec[1]
        + FOLLOWER_RELEASE_BOUNCE_IMPACT_HEIGHT_FX32;
    ballObject->unk88[1] = ballObject->faceVec[1];
    projectile->startHeight = (s32)ballObject->faceVec[1];
    projectile->elapsedFrames = 0;
    projectile->totalFrames = FOLLOWER_RELEASE_BOUNCE_TOTAL_FRAMES;
    projectile->impactSlot = (s8)slot;
    projectile->impactEncounterGeneration =
        state->spawns[slot].encounterGeneration;
    state->followerReleaseX = (s16)bounceX;
    state->followerReleaseY = (s16)bounceY;
    state->followerReleaseState =
        OW_WILD_FOLLOWER_RELEASE_BOUNCING
        | OW_WILD_FOLLOWER_RELEASE_AGGRO_FLAG;
    PlaySE(SEQ_SE_DP_BALL_OPEN);
    return TRUE;
}

void __attribute__((section(".follower_release_bounce_render"), used))
OverworldWildSpawns_RenderFollowerReleaseBounce(
    void *rawProjectile,
    OverworldWildFollowerReleaseRotationCallback rotate)
{
    FollowerReleaseBounceProjectile *projectile = rawProjectile;
    LocalMapObject *object;
    u8 frame;
    u16 progress;
    s32 height;
    s32 renderX;
    s32 renderZ;

    if (projectile == NULL || rotate == NULL) {
        return;
    }
    object = (LocalMapObject *)projectile->opaquePointers[4];
    if (object == NULL) {
        return;
    }
    frame = projectile->elapsedFrames;
    if (frame <= FOLLOWER_RELEASE_BOUNCE_APEX_FRAME) {
        progress = sFollowerReleaseBounceProgress[frame];
        height = projectile->startHeight
            + (sFollowerReleaseBounceHeightFx32[
                    FOLLOWER_RELEASE_BOUNCE_SOURCE_APEX_FRAME]
                - projectile->startHeight)
                * progress
                / FOLLOWER_RELEASE_BOUNCE_PROGRESS_MAX;
        renderX = projectile->startX
            + (projectile->targetX - projectile->startX)
                * progress
                / FOLLOWER_RELEASE_BOUNCE_PROGRESS_MAX;
        renderZ = projectile->startZ
            + (projectile->targetZ - projectile->startZ)
                * progress
                / FOLLOWER_RELEASE_BOUNCE_PROGRESS_MAX;
        if (frame > 0) {
            int rotationStep = 12
                * FOLLOWER_RELEASE_BOUNCE_ROTATION_35_DEGREES
                * (sFollowerReleaseBounceRotationProgress[frame]
                    - sFollowerReleaseBounceRotationProgress[frame - 1])
                / FOLLOWER_RELEASE_BOUNCE_PROGRESS_MAX;

            projectile->rotation = (s16)((u16)projectile->rotation
                + rotationStep);
        }
    } else {
        renderX = projectile->targetX;
        renderZ = projectile->targetZ;
        if (frame < FOLLOWER_RELEASE_BOUNCE_DESCENT_FRAME) {
            height = sFollowerReleaseBounceHeightFx32[
                FOLLOWER_RELEASE_BOUNCE_SOURCE_APEX_FRAME];
        } else if (frame >= FOLLOWER_RELEASE_BOUNCE_MOTION_FRAMES) {
            height = 0;
        } else {
            height = sFollowerReleaseBounceHeightFx32[
                FOLLOWER_RELEASE_BOUNCE_SOURCE_APEX_FRAME
                + 1
                + frame
                - FOLLOWER_RELEASE_BOUNCE_DESCENT_FRAME];
        }
    }
    object->posVec[0] = (u32)renderX;
    object->posVec[2] = (u32)renderZ;
    object->faceVec[0] = 0;
    object->faceVec[1] = (u32)height;
    object->faceVec[2] = 0;
    object->unk88[0] = 0;
    object->unk88[1] = (u32)height;
    object->unk88[2] = 0;
    object->unk94[0] = 0;
    object->unk94[1] = 0;
    object->unk94[2] = 0;
    rotate(projectile->rotation);
    MapObject_ClearBits(object, BIT_VANISH);
}

BOOL __attribute__((section(".follower_release_return"), used))
OverworldWildSpawns_ReturnFollowerReleaseBall(
    FieldSystem *fieldSystem,
    void *rawProjectile,
    u16 progress)
{
    FollowerReleaseBounceProjectile *projectile = rawProjectile;
    LocalMapObject *ball =
        (LocalMapObject *)projectile->opaquePointers[4];
    s32 handHeight = FOLLOWER_RELEASE_RETURN_HAND_HEIGHT_FX32;
    s32 height;

    if (fieldSystem->playerAvatar != NULL
        && fieldSystem->playerAvatar->mapObject != NULL) {
        handHeight +=
            (s32)fieldSystem->playerAvatar->mapObject->faceVec[1];
    }
    ball->posVec[0] = (u32)(projectile->targetX
        + (((projectile->startX - projectile->targetX)
            * (s32)progress) >> 8));
    ball->posVec[1] = (u32)(projectile->targetY
        + (((projectile->startY - projectile->targetY)
            * (s32)progress) >> 8));
    ball->posVec[2] = (u32)(projectile->targetZ
        + (((projectile->startZ - projectile->targetZ)
            * (s32)progress) >> 8));
    ball->hCurr = (int)((s32)ball->posVec[1] >> 15);
    height = projectile->startHeight
        + (((handHeight - projectile->startHeight)
                * (s32)progress)
            >> 8);
    ball->faceVec[1] = (u32)height;
    ball->unk88[1] = (u32)height;
    projectile->shakeIndex++;
    return TRUE;
}

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
