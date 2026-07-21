#include "../../include/overworld_follower_selector.h"

#include "../../include/constants/file.h"
#include "../../include/constants/species.h"
#include "../../include/pokemon.h"
#include "../../include/save.h"
#include "../../include/sprite.h"

#define FOLLOWER_SELECTOR_PARTY_SIZE 6
#define FOLLOWER_SELECTOR_HEAP_ID 11
#define FOLLOWER_SELECTOR_RENDERER_SIZE 0x12C
#define FOLLOWER_SELECTOR_CHAR_RES_BASE 0x7F20
#define FOLLOWER_SELECTOR_SHARED_RES_ID 0x7F30
#define FOLLOWER_SELECTOR_PALETTE_RES_ID 0x7F31
#define FOLLOWER_SELECTOR_ICON_PALETTE_COUNT 3
#define FOLLOWER_SELECTOR_FX32_ONE (1 << FX32_SHIFT)
#define FOLLOWER_SELECTOR_DISABLED_SCALE \
    (FOLLOWER_SELECTOR_FX32_ONE * 3 / 4)
#define FOLLOWER_SELECTOR_SELECTED_SCALE \
    (FOLLOWER_SELECTOR_FX32_ONE * 9 / 8)
#define FOLLOWER_SELECTOR_AFFINE_NORMAL 1
#define FOLLOWER_SELECTOR_MAIN_OBJ_PLANE 0x10

enum FollowerSelectorGfxResourceType {
    FOLLOWER_SELECTOR_GFX_CHAR = 0,
    FOLLOWER_SELECTOR_GFX_PLTT,
    FOLLOWER_SELECTOR_GFX_CELL,
    FOLLOWER_SELECTOR_GFX_ANIM,
    FOLLOWER_SELECTOR_GFX_COUNT,
};

typedef struct FollowerSelectorResourceManager FollowerSelectorResourceManager;
typedef struct FollowerSelectorResource FollowerSelectorResource;
typedef struct FollowerSelectorSprite FollowerSelectorSprite;
typedef struct FollowerSelectorSpriteList FollowerSelectorSpriteList;

typedef struct FollowerSelectorSpriteResourcesHeader {
    const void *imageProxy;
    const void *charData;
    const void *plttProxy;
    void *cellData;
    const void *cellAnim;
    const void *multiCellData;
    const void *multiCellAnim;
    int flag;
    u8 priority;
} FollowerSelectorSpriteResourcesHeader;

typedef struct FollowerSelectorSpriteTemplate {
    FollowerSelectorSpriteList *spriteList;
    const FollowerSelectorSpriteResourcesHeader *header;
    VecFx32 position;
    VecFx32 scale;
    u16 rotation;
    u16 padding;
    u32 drawPriority;
    u32 whichScreen;
    u32 heapId;
} FollowerSelectorSpriteTemplate;

typedef struct FollowerSelectorSlotVisual {
    FollowerSelectorSprite *sprite;
    FollowerSelectorSpriteResourcesHeader header;
    FollowerSelectorResource *charResource;
    VecFx32 basePosition;
    u16 species;
    u8 form;
    u8 isEgg;
    u8 eligible;
    u8 charTransferred;
} FollowerSelectorSlotVisual;

typedef struct FollowerSelectorUIState {
    /* G2dRenderer is 0x12C bytes in the field renderer used by overlay 1. */
    u32 rendererStorage[FOLLOWER_SELECTOR_RENDERER_SIZE / sizeof(u32)];
    FollowerSelectorSpriteList *spriteList;
    FollowerSelectorResourceManager *resourceManagers[
        FOLLOWER_SELECTOR_GFX_COUNT];
    FollowerSelectorResource *paletteResource;
    FollowerSelectorResource *cellResource;
    FollowerSelectorResource *animResource;
    FollowerSelectorSlotVisual slots[FOLLOWER_SELECTOR_PARTY_SIZE];
    FieldSystem *fieldSystem;
    u8 selectedSlot;
    u8 eligibleMask;
    u8 paletteTransferred;
    u8 isOpen;
    u8 frame;
} FollowerSelectorUIState;

extern FollowerSelectorSpriteList *LONG_CALL G2dRenderer_Init(
    int numSprites,
    void *renderer,
    int heapId);
extern BOOL LONG_CALL SpriteList_Delete(FollowerSelectorSpriteList *spriteList);
extern void LONG_CALL SpriteList_RenderAndAnimateSprites(
    FollowerSelectorSpriteList *spriteList);
extern FollowerSelectorSprite *LONG_CALL Sprite_CreateAffine(
    const FollowerSelectorSpriteTemplate *template);
extern void LONG_CALL Sprite_SetMatrix(
    FollowerSelectorSprite *sprite,
    VecFx32 *position);
extern void LONG_CALL Sprite_SetScaleAndAffineType(
    FollowerSelectorSprite *sprite,
    VecFx32 *scale,
    u8 affineType);
extern void LONG_CALL Sprite_SetPalIndexRespectVramOffset(
    FollowerSelectorSprite *sprite,
    int palette);

extern FollowerSelectorResourceManager *LONG_CALL Create2DGfxResObjMan(
    int count,
    int type,
    int heapId);
extern void LONG_CALL Destroy2DGfxResObjMan(
    FollowerSelectorResourceManager *manager);
extern FollowerSelectorResource *LONG_CALL AddCharResObjFromNarc(
    FollowerSelectorResourceManager *manager,
    int narcId,
    int member,
    BOOL compressed,
    int resourceId,
    int vram,
    int heapId);
extern FollowerSelectorResource *LONG_CALL AddPlttResObjFromNarc(
    FollowerSelectorResourceManager *manager,
    int narcId,
    int member,
    BOOL compressed,
    int resourceId,
    int vram,
    int paletteCount,
    int heapId);
extern FollowerSelectorResource *LONG_CALL AddCellOrAnimResObjFromNarc(
    FollowerSelectorResourceManager *manager,
    int narcId,
    int member,
    BOOL compressed,
    int resourceId,
    int type,
    int heapId);
extern BOOL LONG_CALL sub_0200ADA4(FollowerSelectorResource *charResource);
extern void LONG_CALL sub_0200AEB0(FollowerSelectorResource *charResource);
extern BOOL LONG_CALL sub_0200B00C(FollowerSelectorResource *paletteResource);
extern void LONG_CALL sub_0200B0A8(FollowerSelectorResource *paletteResource);
extern void LONG_CALL CreateSpriteResourcesHeader(
    FollowerSelectorSpriteResourcesHeader *header,
    int charId,
    int paletteId,
    int cellId,
    int animId,
    int multiCellId,
    int multiAnimId,
    int transfer,
    int priority,
    FollowerSelectorResourceManager *charManager,
    FollowerSelectorResourceManager *paletteManager,
    FollowerSelectorResourceManager *cellManager,
    FollowerSelectorResourceManager *animManager,
    FollowerSelectorResourceManager *multiCellManager,
    FollowerSelectorResourceManager *multiAnimManager);

static FollowerSelectorUIState sFollowerSelectorUI;

static BOOL OverworldFollowerSelector_ValidateImpl(void);
static void FollowerSelectorUI_RefreshTransforms(void);

const OverworldFollowerSelectorOverlayEntry gOverworldFollowerSelectorOverlayEntry
    __attribute__((section(".overworld_follower_selector_entry"), used)) = {
        OVERWORLD_FOLLOWER_SELECTOR_MAGIC,
        OVERWORLD_FOLLOWER_SELECTOR_VERSION,
        sizeof(OverworldFollowerSelectorOverlayEntry),
        OverworldFollowerSelector_ValidateImpl,
        OverworldFollowerSelectorUI_Open,
        OverworldFollowerSelectorUI_SetSelection,
        OverworldFollowerSelectorUI_Update,
        OverworldFollowerSelectorUI_Close,
        OverworldFollowerSelectorUI_IsOpen,
        OverworldFollowerSelectorInput_Filter,
        OverworldFollowerSelectorInput_Cancel,
        OverworldFollowerSelectorInput_IsActive,
};

static BOOL FollowerSelectorUI_IsOverlayCode(const void *function)
{
    u32 rawAddress = (u32)function;
    u32 address = rawAddress & ~1u;

    return (rawAddress & 1u) != 0
        && address >= OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY_ADDR
        && address < OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_END_ADDR;
}

static BOOL OverworldFollowerSelector_ValidateImpl(void)
{
    const OverworldFollowerSelectorOverlayEntry *entry =
        &gOverworldFollowerSelectorOverlayEntry;

    return entry->magic == OVERWORLD_FOLLOWER_SELECTOR_MAGIC
        && entry->version == OVERWORLD_FOLLOWER_SELECTOR_VERSION
        && entry->size == sizeof(*entry)
        && FollowerSelectorUI_IsOverlayCode((const void *)entry->validate)
        && FollowerSelectorUI_IsOverlayCode((const void *)entry->uiOpen)
        && FollowerSelectorUI_IsOverlayCode(
            (const void *)entry->uiSetSelection)
        && FollowerSelectorUI_IsOverlayCode((const void *)entry->uiUpdate)
        && FollowerSelectorUI_IsOverlayCode((const void *)entry->uiClose)
        && FollowerSelectorUI_IsOverlayCode((const void *)entry->uiIsOpen)
        && FollowerSelectorUI_IsOverlayCode((const void *)entry->inputFilter)
        && FollowerSelectorUI_IsOverlayCode((const void *)entry->inputCancel)
        && FollowerSelectorUI_IsOverlayCode(
            (const void *)entry->inputIsActive);
}

static void FollowerSelectorUI_EnableObjPlane(void)
{
    u32 planes = (reg_GX_DISPCNT & REG_GX_DISPCNT_DISPLAY_MASK)
        >> REG_GX_DISPCNT_DISPLAY_SHIFT;

    GX_SetVisiblePlane(planes | FOLLOWER_SELECTOR_MAIN_OBJ_PLANE);
}

static void FollowerSelectorUI_InitSlotVisual(
    FollowerSelectorSlotVisual *slot,
    struct Party *party,
    int partySlot,
    u8 eligibleMask)
{
    struct PartyPokemon *mon = NULL;
    u32 species = SPECIES_NONE;
    u32 form = 0;
    u32 isEgg = FALSE;
    u32 hp = 0;

    if (partySlot < party->count) {
        mon = Party_GetMonByIndex(party, partySlot);
    }
    if (mon != NULL) {
        species = GetMonData(mon, MON_DATA_SPECIES, NULL);
        isEgg = GetMonData(mon, MON_DATA_IS_EGG, NULL);
        hp = GetMonData(mon, MON_DATA_HP, NULL);
        form = PokeIconCgxPatternGet(&mon->box);
    }
    slot->species = (u16)species;
    slot->form = (u8)form;
    slot->isEgg = (u8)(isEgg != FALSE);
    slot->eligible = species != SPECIES_NONE
        && !isEgg
        && hp != 0
        && (eligibleMask & (1 << partySlot)) != 0;
}

static void FollowerSelectorUI_DestroyResources(void)
{
    int slot;
    int resourceType;

    if (sFollowerSelectorUI.spriteList != NULL) {
        SpriteList_Delete(sFollowerSelectorUI.spriteList);
        sFollowerSelectorUI.spriteList = NULL;
    }
    for (slot = 0; slot < FOLLOWER_SELECTOR_PARTY_SIZE; slot++) {
        FollowerSelectorSlotVisual *visual = &sFollowerSelectorUI.slots[slot];

        if (visual->charTransferred && visual->charResource != NULL) {
            sub_0200AEB0(visual->charResource);
            visual->charTransferred = FALSE;
        }
    }
    if (sFollowerSelectorUI.paletteTransferred
        && sFollowerSelectorUI.paletteResource != NULL) {
        sub_0200B0A8(sFollowerSelectorUI.paletteResource);
        sFollowerSelectorUI.paletteTransferred = FALSE;
    }
    for (resourceType = FOLLOWER_SELECTOR_GFX_COUNT - 1;
         resourceType >= 0;
         resourceType--) {
        if (sFollowerSelectorUI.resourceManagers[resourceType] != NULL) {
            Destroy2DGfxResObjMan(
                sFollowerSelectorUI.resourceManagers[resourceType]);
            sFollowerSelectorUI.resourceManagers[resourceType] = NULL;
        }
    }
}

void OverworldFollowerSelectorUI_Close(void)
{
    sFollowerSelectorUI.isOpen = FALSE;
    FollowerSelectorUI_DestroyResources();
    memset(&sFollowerSelectorUI, 0, sizeof(sFollowerSelectorUI));
    sFollowerSelectorUI.selectedSlot = 0xFF;
}

static BOOL FollowerSelectorUI_CreateManagers(void)
{
    static const u8 capacities[FOLLOWER_SELECTOR_GFX_COUNT] = { 6, 1, 1, 1 };
    int resourceType;

    for (resourceType = 0;
         resourceType < FOLLOWER_SELECTOR_GFX_COUNT;
         resourceType++) {
        sFollowerSelectorUI.resourceManagers[resourceType] =
            Create2DGfxResObjMan(
                capacities[resourceType],
                resourceType,
                FOLLOWER_SELECTOR_HEAP_ID);
        if (sFollowerSelectorUI.resourceManagers[resourceType] == NULL) {
            return FALSE;
        }
    }
    return TRUE;
}

static BOOL FollowerSelectorUI_LoadSharedResources(void)
{
    sFollowerSelectorUI.paletteResource = AddPlttResObjFromNarc(
        sFollowerSelectorUI.resourceManagers[FOLLOWER_SELECTOR_GFX_PLTT],
        ARC_POKEICON,
        PokeIconPalArcIndexGet(),
        FALSE,
        FOLLOWER_SELECTOR_PALETTE_RES_ID,
        NNS_G2D_VRAM_TYPE_2DMAIN,
        FOLLOWER_SELECTOR_ICON_PALETTE_COUNT,
        FOLLOWER_SELECTOR_HEAP_ID);
    if (sFollowerSelectorUI.paletteResource == NULL
        || !sub_0200B00C(sFollowerSelectorUI.paletteResource)) {
        return FALSE;
    }
    sFollowerSelectorUI.paletteTransferred = TRUE;

    sFollowerSelectorUI.cellResource = AddCellOrAnimResObjFromNarc(
        sFollowerSelectorUI.resourceManagers[FOLLOWER_SELECTOR_GFX_CELL],
        ARC_POKEICON,
        PokeIconAnmCellArcIndexGet(),
        FALSE,
        FOLLOWER_SELECTOR_SHARED_RES_ID,
        FOLLOWER_SELECTOR_GFX_CELL,
        FOLLOWER_SELECTOR_HEAP_ID);
    if (sFollowerSelectorUI.cellResource == NULL) {
        return FALSE;
    }
    sFollowerSelectorUI.animResource = AddCellOrAnimResObjFromNarc(
        sFollowerSelectorUI.resourceManagers[FOLLOWER_SELECTOR_GFX_ANIM],
        ARC_POKEICON,
        PokeIconAnmCellAnmArcIndexGet(),
        FALSE,
        FOLLOWER_SELECTOR_SHARED_RES_ID,
        FOLLOWER_SELECTOR_GFX_ANIM,
        FOLLOWER_SELECTOR_HEAP_ID);
    return sFollowerSelectorUI.animResource != NULL;
}

static BOOL FollowerSelectorUI_CreateSlotSprite(int partySlot)
{
    FollowerSelectorSlotVisual *visual =
        &sFollowerSelectorUI.slots[partySlot];
    FollowerSelectorSpriteTemplate template;
    VecFx32 scale;
    int charResourceId = FOLLOWER_SELECTOR_CHAR_RES_BASE + partySlot;
    u32 iconMember = PokeIconIndexGetByMonsNumber(
        visual->species,
        visual->isEgg,
        visual->form);

    visual->charResource = AddCharResObjFromNarc(
        sFollowerSelectorUI.resourceManagers[FOLLOWER_SELECTOR_GFX_CHAR],
        ARC_POKEICON,
        iconMember,
        FALSE,
        charResourceId,
        NNS_G2D_VRAM_TYPE_2DMAIN,
        FOLLOWER_SELECTOR_HEAP_ID);
    if (visual->charResource == NULL
        || !sub_0200ADA4(visual->charResource)) {
        return FALSE;
    }
    visual->charTransferred = TRUE;
    CreateSpriteResourcesHeader(
        &visual->header,
        charResourceId,
        FOLLOWER_SELECTOR_PALETTE_RES_ID,
        FOLLOWER_SELECTOR_SHARED_RES_ID,
        FOLLOWER_SELECTOR_SHARED_RES_ID,
        -1,
        -1,
        FALSE,
        0,
        sFollowerSelectorUI.resourceManagers[FOLLOWER_SELECTOR_GFX_CHAR],
        sFollowerSelectorUI.resourceManagers[FOLLOWER_SELECTOR_GFX_PLTT],
        sFollowerSelectorUI.resourceManagers[FOLLOWER_SELECTOR_GFX_CELL],
        sFollowerSelectorUI.resourceManagers[FOLLOWER_SELECTOR_GFX_ANIM],
        NULL,
        NULL);

    memset(&template, 0, sizeof(template));
    template.spriteList = sFollowerSelectorUI.spriteList;
    template.header = &visual->header;
    template.position = visual->basePosition;
    template.scale.x = FOLLOWER_SELECTOR_FX32_ONE;
    template.scale.y = FOLLOWER_SELECTOR_FX32_ONE;
    template.scale.z = FOLLOWER_SELECTOR_FX32_ONE;
    template.whichScreen = NNS_G2D_VRAM_TYPE_2DMAIN;
    template.heapId = FOLLOWER_SELECTOR_HEAP_ID;
    visual->sprite = Sprite_CreateAffine(&template);
    if (visual->sprite == NULL) {
        return FALSE;
    }
    Sprite_SetPalIndexRespectVramOffset(
        visual->sprite,
        GetMonIconPalette(visual->species, visual->form, visual->isEgg));
    scale.x = visual->eligible
        ? FOLLOWER_SELECTOR_FX32_ONE
        : FOLLOWER_SELECTOR_DISABLED_SCALE;
    scale.y = scale.x;
    scale.z = FOLLOWER_SELECTOR_FX32_ONE;
    Sprite_SetScaleAndAffineType(
        visual->sprite,
        &scale,
        FOLLOWER_SELECTOR_AFFINE_NORMAL);
    return TRUE;
}

BOOL OverworldFollowerSelectorUI_Open(
    FieldSystem *fieldSystem,
    u8 highlightedSlot)
{
    struct Party *party;
    u8 eligibleMask;
    int slot;

    if (fieldSystem == NULL || fieldSystem->savedata == NULL) {
        return FALSE;
    }
    OverworldFollowerSelectorUI_Close();
    party = (struct Party *)SaveData_GetPlayerPartyPtr(fieldSystem->savedata);
    if (party == NULL) {
        return FALSE;
    }
    eligibleMask = OverworldWildSpawns_GetEligibleFollowerPartyMask(fieldSystem);
    sFollowerSelectorUI.fieldSystem = fieldSystem;
    sFollowerSelectorUI.eligibleMask = eligibleMask;
    sFollowerSelectorUI.selectedSlot = 0xFF;
    for (slot = 0; slot < FOLLOWER_SELECTOR_PARTY_SIZE; slot++) {
        FollowerSelectorSlotVisual *visual = &sFollowerSelectorUI.slots[slot];

        FollowerSelectorUI_InitSlotVisual(visual, party, slot, eligibleMask);
        visual->basePosition.x =
            (96 + (slot % 3) * 32) * FOLLOWER_SELECTOR_FX32_ONE;
        visual->basePosition.y =
            (32 + (slot / 3) * 32) * FOLLOWER_SELECTOR_FX32_ONE;
        visual->basePosition.z = 0;
        if (!visual->eligible) {
            sFollowerSelectorUI.eligibleMask &= ~(1 << slot);
        }
    }
    if (!FollowerSelectorUI_CreateManagers()
        || !FollowerSelectorUI_LoadSharedResources()) {
        OverworldFollowerSelectorUI_Close();
        return FALSE;
    }
    sFollowerSelectorUI.spriteList = G2dRenderer_Init(
        FOLLOWER_SELECTOR_PARTY_SIZE,
        sFollowerSelectorUI.rendererStorage,
        FOLLOWER_SELECTOR_HEAP_ID);
    if (sFollowerSelectorUI.spriteList == NULL) {
        OverworldFollowerSelectorUI_Close();
        return FALSE;
    }
    for (slot = 0; slot < FOLLOWER_SELECTOR_PARTY_SIZE; slot++) {
        if (!FollowerSelectorUI_CreateSlotSprite(slot)) {
            OverworldFollowerSelectorUI_Close();
            return FALSE;
        }
    }
    FollowerSelectorUI_EnableObjPlane();
    sFollowerSelectorUI.isOpen = TRUE;
    OverworldFollowerSelectorUI_SetSelection(highlightedSlot);
    FollowerSelectorUI_RefreshTransforms();
    return TRUE;
}

static void FollowerSelectorUI_RefreshTransforms(void)
{
    int slot;

    for (slot = 0; slot < FOLLOWER_SELECTOR_PARTY_SIZE; slot++) {
        FollowerSelectorSlotVisual *visual = &sFollowerSelectorUI.slots[slot];
        VecFx32 position = visual->basePosition;
        VecFx32 scale;

        if (visual->sprite == NULL) {
            continue;
        }
        if (slot == sFollowerSelectorUI.selectedSlot && visual->eligible) {
            position.y -= (4 + ((sFollowerSelectorUI.frame >> 2) & 1))
                * FOLLOWER_SELECTOR_FX32_ONE;
            scale.x = FOLLOWER_SELECTOR_SELECTED_SCALE;
        } else if (visual->eligible) {
            scale.x = FOLLOWER_SELECTOR_FX32_ONE;
        } else {
            scale.x = FOLLOWER_SELECTOR_DISABLED_SCALE;
        }
        scale.y = scale.x;
        scale.z = FOLLOWER_SELECTOR_FX32_ONE;
        Sprite_SetMatrix(visual->sprite, &position);
        Sprite_SetScaleAndAffineType(
            visual->sprite,
            &scale,
            FOLLOWER_SELECTOR_AFFINE_NORMAL);
    }
}

void OverworldFollowerSelectorUI_SetSelection(u8 highlightedSlot)
{
    if (!sFollowerSelectorUI.isOpen
        || highlightedSlot >= FOLLOWER_SELECTOR_PARTY_SIZE
        || (sFollowerSelectorUI.eligibleMask & (1 << highlightedSlot)) == 0) {
        return;
    }
    sFollowerSelectorUI.selectedSlot = highlightedSlot;
    sFollowerSelectorUI.frame = 0;
    FollowerSelectorUI_RefreshTransforms();
}

void OverworldFollowerSelectorUI_Update(void)
{
    if (!sFollowerSelectorUI.isOpen
        || sFollowerSelectorUI.spriteList == NULL) {
        return;
    }
    sFollowerSelectorUI.frame++;
    FollowerSelectorUI_RefreshTransforms();
    SpriteList_RenderAndAnimateSprites(sFollowerSelectorUI.spriteList);
}

BOOL OverworldFollowerSelectorUI_IsOpen(void)
{
    return sFollowerSelectorUI.isOpen;
}
