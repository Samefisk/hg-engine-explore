#include "../../include/overworld_follower_selector.h"

#include "../../include/constants/file.h"
#include "../../include/constants/species.h"
#include "../../include/pokemon.h"
#include "../../include/save.h"
#include "../../include/sprite.h"

#define FOLLOWER_SELECTOR_PARTY_SIZE 6
#define FOLLOWER_SELECTOR_HEAP_ID 11
#define FOLLOWER_SELECTOR_CHAR_RES_BASE 0x7F20
#define FOLLOWER_SELECTOR_PLTT_RES_BASE 0x7F28
#define FOLLOWER_SELECTOR_SHARED_RES_ID 0x7F30
#define FOLLOWER_SELECTOR_PALETTE_RES_ID 0x7F31
#define FOLLOWER_SELECTOR_ICON_PALETTE_COUNT 3
#define FOLLOWER_SELECTOR_FX32_ONE (1 << FX32_SHIFT)
#define FOLLOWER_SELECTOR_RENDERER_SIZE 0x12C
#define FOLLOWER_SELECTOR_MAIN_OBJ_PLANE 0x10
#define FOLLOWER_SELECTOR_GRID_CENTER_X 128
#define FOLLOWER_SELECTOR_COLUMN_SPACING_X 29

#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
typedef BOOL (*FollowerSelectorOverworldExtractFunc)(
    FieldSystem *fieldSystem,
    u16 species,
    u8 form,
    u8 female,
    u8 shiny,
    u8 isEgg,
    u8 iconPalette,
    void *charResource,
    void *paletteResource);

#define FOLLOWER_SELECTOR_EXTRACT_OVERWORLD \
    ((FollowerSelectorOverworldExtractFunc)(0x0224EF98 | 1))
#endif

enum FollowerSelectorGfxResourceType {
    FOLLOWER_SELECTOR_GFX_CHAR = 0,
    FOLLOWER_SELECTOR_GFX_PLTT,
    FOLLOWER_SELECTOR_GFX_CELL,
    FOLLOWER_SELECTOR_GFX_ANIM,
    FOLLOWER_SELECTOR_GFX_COUNT,
};

enum FollowerSelectorUILoadStage {
    FOLLOWER_SELECTOR_UI_CREATE_MANAGER = 0,
    FOLLOWER_SELECTOR_UI_CREATE_RENDERER,
    FOLLOWER_SELECTOR_UI_LOAD_PALETTE,
    FOLLOWER_SELECTOR_UI_TRANSFER_PALETTE,
    FOLLOWER_SELECTOR_UI_LOAD_CELL,
    FOLLOWER_SELECTOR_UI_LOAD_ANIM,
    FOLLOWER_SELECTOR_UI_LOAD_SLOT_CHAR,
    FOLLOWER_SELECTOR_UI_TRANSFER_SLOT_CHAR,
    FOLLOWER_SELECTOR_UI_CREATE_SLOT_SPRITE,
    FOLLOWER_SELECTOR_UI_LOAD_READY,
};

typedef struct FollowerSelectorResourceManager FollowerSelectorResourceManager;
typedef struct FollowerSelectorResource {
    void *resource;
    int type;
    void *extra;
} FollowerSelectorResource;
typedef struct FollowerSelectorSprite FollowerSelectorSprite;
typedef struct FollowerSelectorSpriteList FollowerSelectorSpriteList;
typedef BOOL (*FollowerSelectorAcquireMonLockFunc)(struct PartyPokemon *mon);
typedef BOOL (*FollowerSelectorReleaseMonLockFunc)(
    struct PartyPokemon *mon,
    BOOL locked);

#define FOLLOWER_SELECTOR_ACQUIRE_MON_LOCK \
    ((FollowerSelectorAcquireMonLockFunc)(0x0206DD40 | 1))
#define FOLLOWER_SELECTOR_RELEASE_MON_LOCK \
    ((FollowerSelectorReleaseMonLockFunc)(0x0206DD8C | 1))

extern void OverworldFollowerSelector_ClearMemory(void *memory, u32 size);

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
#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
    FollowerSelectorResource *paletteResource;
#endif
    VecFx32 basePosition;
    u16 species;
    u8 form;
    u8 isEgg;
    u8 eligible;
    u8 palette;
    u8 charTransferred;
#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
    u8 overworldForm;
    u8 female;
    u8 shiny;
    u8 paletteTransferred;
#endif
} FollowerSelectorSlotVisual;

typedef struct FollowerSelectorUIState {
    u32 rendererStorage[FOLLOWER_SELECTOR_RENDERER_SIZE / sizeof(u32)];
    FollowerSelectorSpriteList *spriteList;
    FollowerSelectorResourceManager *resourceManagers[
        FOLLOWER_SELECTOR_GFX_COUNT];
#if !FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
    FollowerSelectorResource *paletteResource;
#endif
    FollowerSelectorResource *cellResource;
    FollowerSelectorResource *animResource;
    FollowerSelectorSlotVisual slots[FOLLOWER_SELECTOR_PARTY_SIZE];
    FieldSystem *fieldSystem;
    u8 selectedSlot;
    u8 eligibleMask;
#if !FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
    u8 paletteTransferred;
#endif
    u8 isOpen;
    u8 frame;
    u8 loadStage;
    u8 loadSlot;
    u8 managerLoadIndex;
    u8 loadedSlotMask;
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
extern void LONG_CALL Sprite_SetAnimActiveFlag(
    FollowerSelectorSprite *sprite,
    BOOL active);
extern void LONG_CALL Sprite_SetAnimCtrlSeq(
    FollowerSelectorSprite *sprite,
    int sequence);
extern void LONG_CALL Sprite_SetMatrix(
    FollowerSelectorSprite *sprite,
    VecFx32 *position);
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

static FollowerSelectorUIState *sFollowerSelectorUIStorage;
#define sFollowerSelectorUI (*sFollowerSelectorUIStorage)

static BOOL OverworldFollowerSelector_ValidateImpl(void);
static void FollowerSelectorUI_RefreshTransforms(void);
static BOOL FollowerSelectorUI_LoadNextUnit(void);

static BOOL FollowerSelectorUI_EnsureState(void)
{
    if (sFollowerSelectorUIStorage != NULL) {
        return TRUE;
    }
    sFollowerSelectorUIStorage = sys_AllocMemory(
        FOLLOWER_SELECTOR_HEAP_ID,
        sizeof(*sFollowerSelectorUIStorage));
    if (sFollowerSelectorUIStorage == NULL) {
        return FALSE;
    }
    OverworldFollowerSelector_ClearMemory(
        sFollowerSelectorUIStorage,
        sizeof(*sFollowerSelectorUIStorage));
    sFollowerSelectorUI.selectedSlot = 0xFF;
    return TRUE;
}

int OverworldFollowerSelector_BuildDirectedDirections(
    int dx,
    int dy,
    u8 *directions)
{
    int count = 0;
    int absDx = dx < 0 ? -dx : dx;
    int absDy = dy < 0 ? -dy : dy;

    if ((dx | dy) == 0) {
        return 0;
    }
    if (absDx >= absDy) {
        if (dx != 0) directions[count++] = dx > 0 ? 3 : 2;
        if (dy != 0) directions[count++] = dy > 0 ? 1 : 0;
    } else {
        if (dy != 0) directions[count++] = dy > 0 ? 1 : 0;
        if (dx != 0) directions[count++] = dx > 0 ? 3 : 2;
    }
    return count;
}

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
        OverworldFollowerSelector_GetSelectedPokemon,
        OverworldFollowerSelector_GetReleaseDistance,
        OverworldFollowerSelector_IsReleaseTileAvailable,
        OverworldFollowerSelector_BuildDirectedDirections,
};

static BOOL OverworldFollowerSelector_ValidateImpl(void)
{
    const OverworldFollowerSelectorOverlayEntry *entry =
        &gOverworldFollowerSelectorOverlayEntry;

    return entry->magic == OVERWORLD_FOLLOWER_SELECTOR_MAGIC
        && entry->version == OVERWORLD_FOLLOWER_SELECTOR_VERSION
        && entry->size == sizeof(*entry)
        && entry->validate != NULL
        && entry->inputFilter != NULL
        && entry->inputCancel != NULL
        && entry->inputIsActive != NULL
        && entry->getSelectedPokemon != NULL
        && entry->getReleaseDistance != NULL
        && entry->isReleaseTileAvailable != NULL
        && entry->buildDirectedDirections != NULL;
}

static void FollowerSelectorUI_EnableObjPlane(void)
{
    u32 planes = (reg_GX_DISPCNT & REG_GX_DISPCNT_DISPLAY_MASK)
        >> REG_GX_DISPCNT_DISPLAY_SHIFT;

    GX_SetVisiblePlane(planes | FOLLOWER_SELECTOR_MAIN_OBJ_PLANE);
}

void OverworldFollowerSelectorUI_BeginPartySnapshot(void)
{
    if (!FollowerSelectorUI_EnsureState()) {
        return;
    }
    sFollowerSelectorUI.eligibleMask = 0;
    sFollowerSelectorUI.loadSlot = 0;
}

BOOL OverworldFollowerSelectorUI_SnapshotNextPartySlot(
    FieldSystem *fieldSystem)
{
    FollowerSelectorSlotVisual *slot;
    struct Party *party;
    struct PartyPokemon *mon = NULL;
    u32 species = SPECIES_NONE;
    u32 form = 0;
    u32 isEgg = FALSE;
#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
    u32 overworldForm = 0;
    u32 female = FALSE;
    u32 shiny = FALSE;
#endif
    BOOL eligible = FALSE;
    BOOL locked;
    u8 partySlot;

    if (sFollowerSelectorUIStorage == NULL) {
        return TRUE;
    }
    partySlot = sFollowerSelectorUI.loadSlot;

    if (partySlot >= FOLLOWER_SELECTOR_PARTY_SIZE) {
        return TRUE;
    }
    party = fieldSystem == NULL || fieldSystem->savedata == NULL
        ? NULL
        : SaveData_GetPlayerPartyPtr(fieldSystem->savedata);
    if (party != NULL && partySlot < party->count) {
        mon = Party_GetMonByIndex(party, partySlot);
    }
    if (mon != NULL) {
        locked = FOLLOWER_SELECTOR_ACQUIRE_MON_LOCK(mon);
        species = GetMonData(mon, MON_DATA_SPECIES, NULL);
        isEgg = GetMonData(mon, MON_DATA_IS_EGG, NULL);
#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
        overworldForm = GetMonData(mon, MON_DATA_FORM, NULL);
        female = GetMonData(mon, MON_DATA_GENDER, NULL)
            == POKEMON_GENDER_FEMALE;
        shiny = MonIsShiny(mon);
#endif
        form = PokeIconCgxPatternGet(&mon->box);
        /* Reuse the canonical predicate while this mon is already decrypted. */
        eligible = OverworldWildSpawns_IsFollowerPartySlotEligible(
            fieldSystem,
            partySlot);
        FOLLOWER_SELECTOR_RELEASE_MON_LOCK(mon, locked);
    }
    slot = &sFollowerSelectorUI.slots[partySlot];
    slot->species = (u16)species;
    slot->form = (u8)form;
    slot->isEgg = (u8)(isEgg != FALSE);
    slot->eligible = eligible;
    slot->palette = species == SPECIES_NONE
        ? 0
        : GetMonIconPalette(species, form, isEgg);
#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
    slot->overworldForm = (u8)overworldForm;
    slot->female = (u8)female;
    slot->shiny = (u8)shiny;
#endif
    if (slot->eligible) {
        sFollowerSelectorUI.eligibleMask |= (u8)(1 << partySlot);
    }
    sFollowerSelectorUI.loadSlot++;
    return sFollowerSelectorUI.loadSlot >= FOLLOWER_SELECTOR_PARTY_SIZE;
}

u8 OverworldFollowerSelectorUI_GetEligibleMask(void)
{
    return sFollowerSelectorUIStorage == NULL
        ? 0
        : sFollowerSelectorUI.eligibleMask;
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
#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
        if (visual->paletteTransferred
            && visual->paletteResource != NULL) {
            sub_0200B0A8(visual->paletteResource);
            visual->paletteTransferred = FALSE;
        }
#endif
    }
#if !FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
    if (sFollowerSelectorUI.paletteTransferred
        && sFollowerSelectorUI.paletteResource != NULL) {
        sub_0200B0A8(sFollowerSelectorUI.paletteResource);
        sFollowerSelectorUI.paletteTransferred = FALSE;
    }
#endif
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
    FollowerSelectorUIState *state = sFollowerSelectorUIStorage;

    if (state == NULL) {
        return;
    }
    sFollowerSelectorUI.isOpen = FALSE;
    FollowerSelectorUI_DestroyResources();
    OverworldFollowerSelector_ClearMemory(state, sizeof(*state));
    sys_FreeMemoryEz(state);
    sFollowerSelectorUIStorage = NULL;
}

static BOOL FollowerSelectorUI_CreateNextManager(void)
{
#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
    static const u8 capacities[FOLLOWER_SELECTOR_GFX_COUNT] = { 6, 6, 1, 1 };
#else
    static const u8 capacities[FOLLOWER_SELECTOR_GFX_COUNT] = { 6, 1, 1, 1 };
#endif
    u8 resourceType = sFollowerSelectorUI.managerLoadIndex;

    if (resourceType >= FOLLOWER_SELECTOR_GFX_COUNT) {
        return TRUE;
    }
    sFollowerSelectorUI.resourceManagers[resourceType] =
        Create2DGfxResObjMan(
            capacities[resourceType],
            resourceType,
            FOLLOWER_SELECTOR_HEAP_ID);
    if (sFollowerSelectorUI.resourceManagers[resourceType] == NULL) {
        return FALSE;
    }
    sFollowerSelectorUI.managerLoadIndex++;
    return TRUE;
}

#if !FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
static BOOL FollowerSelectorUI_LoadPalette(void)
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
    return sFollowerSelectorUI.paletteResource != NULL;
}
#endif

static BOOL FollowerSelectorUI_LoadCell(void)
{
    sFollowerSelectorUI.cellResource = AddCellOrAnimResObjFromNarc(
        sFollowerSelectorUI.resourceManagers[FOLLOWER_SELECTOR_GFX_CELL],
        ARC_POKEICON,
        PokeIconAnmCellArcIndexGet(),
        FALSE,
        FOLLOWER_SELECTOR_SHARED_RES_ID,
        FOLLOWER_SELECTOR_GFX_CELL,
        FOLLOWER_SELECTOR_HEAP_ID);
    return sFollowerSelectorUI.cellResource != NULL;
}

static BOOL FollowerSelectorUI_LoadAnim(void)
{
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

static BOOL FollowerSelectorUI_LoadSlotChar(int partySlot)
{
    FollowerSelectorSlotVisual *visual =
        &sFollowerSelectorUI.slots[partySlot];
    int charResourceId = FOLLOWER_SELECTOR_CHAR_RES_BASE + partySlot;

    if (visual->species == SPECIES_NONE) {
        return TRUE;
    }

    visual->charResource = AddCharResObjFromNarc(
        sFollowerSelectorUI.resourceManagers[FOLLOWER_SELECTOR_GFX_CHAR],
        ARC_POKEICON,
        PokeIconIndexGetByMonsNumber(
            visual->species,
            visual->isEgg,
            visual->form),
        FALSE,
        charResourceId,
        NNS_G2D_VRAM_TYPE_2DMAIN,
        FOLLOWER_SELECTOR_HEAP_ID);
#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
    if (visual->charResource == NULL) {
        return FALSE;
    }
    visual->paletteResource = AddPlttResObjFromNarc(
        sFollowerSelectorUI.resourceManagers[FOLLOWER_SELECTOR_GFX_PLTT],
        ARC_POKEICON,
        PokeIconPalArcIndexGet(),
        FALSE,
        FOLLOWER_SELECTOR_PLTT_RES_BASE + partySlot,
        NNS_G2D_VRAM_TYPE_2DMAIN,
        1,
        FOLLOWER_SELECTOR_HEAP_ID);
    return visual->paletteResource != NULL;
#else
    return visual->charResource != NULL;
#endif
}

static BOOL FollowerSelectorUI_CreateSlotSprite(int partySlot)
{
    FollowerSelectorSlotVisual *visual =
        &sFollowerSelectorUI.slots[partySlot];
    FollowerSelectorSpriteTemplate template;
    int charResourceId = FOLLOWER_SELECTOR_CHAR_RES_BASE + partySlot;

    if (visual->species == SPECIES_NONE) {
        return TRUE;
    }
    CreateSpriteResourcesHeader(
        &visual->header,
        charResourceId,
#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
        FOLLOWER_SELECTOR_PLTT_RES_BASE + partySlot,
#else
        FOLLOWER_SELECTOR_PALETTE_RES_ID,
#endif
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

    OverworldFollowerSelector_ClearMemory(&template, sizeof(template));
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
    Sprite_SetAnimCtrlSeq(visual->sprite, 3);
    Sprite_SetAnimActiveFlag(visual->sprite, TRUE);
#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
    Sprite_SetPalIndexRespectVramOffset(visual->sprite, 0);
#else
    Sprite_SetPalIndexRespectVramOffset(visual->sprite, visual->palette);
#endif
    return TRUE;
}

static BOOL FollowerSelectorUI_LoadNextUnit(void)
{
    FollowerSelectorSlotVisual *visual;
    u8 slot;

    switch (sFollowerSelectorUI.loadStage) {
    case FOLLOWER_SELECTOR_UI_CREATE_MANAGER:
        if (!FollowerSelectorUI_CreateNextManager()) {
            return FALSE;
        }
        if (sFollowerSelectorUI.managerLoadIndex
                >= FOLLOWER_SELECTOR_GFX_COUNT) {
            sFollowerSelectorUI.loadStage =
                FOLLOWER_SELECTOR_UI_CREATE_RENDERER;
        }
        break;

    case FOLLOWER_SELECTOR_UI_CREATE_RENDERER:
        sFollowerSelectorUI.spriteList = G2dRenderer_Init(
            FOLLOWER_SELECTOR_PARTY_SIZE,
            sFollowerSelectorUI.rendererStorage,
            FOLLOWER_SELECTOR_HEAP_ID);
        if (sFollowerSelectorUI.spriteList == NULL) {
            return FALSE;
        }
        FollowerSelectorUI_EnableObjPlane();
#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
        sFollowerSelectorUI.loadStage = FOLLOWER_SELECTOR_UI_LOAD_CELL;
#else
        sFollowerSelectorUI.loadStage = FOLLOWER_SELECTOR_UI_LOAD_PALETTE;
#endif
        break;

#if !FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
    case FOLLOWER_SELECTOR_UI_LOAD_PALETTE:
        if (!FollowerSelectorUI_LoadPalette()) {
            return FALSE;
        }
        sFollowerSelectorUI.loadStage =
            FOLLOWER_SELECTOR_UI_TRANSFER_PALETTE;
        break;

    case FOLLOWER_SELECTOR_UI_TRANSFER_PALETTE:
        if (!sub_0200B00C(sFollowerSelectorUI.paletteResource)) {
            return FALSE;
        }
        sFollowerSelectorUI.paletteTransferred = TRUE;
        sFollowerSelectorUI.loadStage = FOLLOWER_SELECTOR_UI_LOAD_CELL;
        break;
#endif

    case FOLLOWER_SELECTOR_UI_LOAD_CELL:
        if (!FollowerSelectorUI_LoadCell()) {
            return FALSE;
        }
        sFollowerSelectorUI.loadStage = FOLLOWER_SELECTOR_UI_LOAD_ANIM;
        break;

    case FOLLOWER_SELECTOR_UI_LOAD_ANIM:
        if (!FollowerSelectorUI_LoadAnim()) {
            return FALSE;
        }
        sFollowerSelectorUI.loadStage = FOLLOWER_SELECTOR_UI_LOAD_SLOT_CHAR;
        break;

    case FOLLOWER_SELECTOR_UI_LOAD_SLOT_CHAR:
        while (sFollowerSelectorUI.loadedSlotMask
                != (1 << FOLLOWER_SELECTOR_PARTY_SIZE) - 1) {
            slot = sFollowerSelectorUI.selectedSlot;
            if (slot >= FOLLOWER_SELECTOR_PARTY_SIZE
                || (sFollowerSelectorUI.loadedSlotMask & (1 << slot)) != 0) {
                for (slot = 0;
                     slot < FOLLOWER_SELECTOR_PARTY_SIZE;
                     slot++) {
                    if ((sFollowerSelectorUI.loadedSlotMask & (1 << slot))
                            == 0) {
                        break;
                    }
                }
            }
            sFollowerSelectorUI.loadSlot = slot;
            visual = &sFollowerSelectorUI.slots[slot];
            if (visual->species == SPECIES_NONE) {
                sFollowerSelectorUI.loadedSlotMask |= (u8)(1 << slot);
                continue;
            }
            if (!FollowerSelectorUI_LoadSlotChar(slot)) {
                return FALSE;
            }
            sFollowerSelectorUI.loadStage =
                FOLLOWER_SELECTOR_UI_TRANSFER_SLOT_CHAR;
            break;
        }
        if (sFollowerSelectorUI.loadedSlotMask
                == (1 << FOLLOWER_SELECTOR_PARTY_SIZE) - 1) {
            sFollowerSelectorUI.loadStage = FOLLOWER_SELECTOR_UI_LOAD_READY;
        }
        break;

    case FOLLOWER_SELECTOR_UI_TRANSFER_SLOT_CHAR:
        visual = &sFollowerSelectorUI.slots[sFollowerSelectorUI.loadSlot];
#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
        (void)FOLLOWER_SELECTOR_EXTRACT_OVERWORLD(
            sFollowerSelectorUI.fieldSystem,
            visual->species,
            visual->overworldForm,
            visual->female,
            visual->shiny,
            visual->isEgg,
            visual->palette,
            visual->charResource,
            visual->paletteResource);
#endif
        if (visual->charResource == NULL
            || !sub_0200ADA4(visual->charResource)) {
            return FALSE;
        }
        visual->charTransferred = TRUE;
#if FOLLOWER_SELECTOR_USE_OVERWORLD_ICONS
        if (visual->paletteResource == NULL
            || !sub_0200B00C(visual->paletteResource)) {
            return FALSE;
        }
        visual->paletteTransferred = TRUE;
#endif
        sFollowerSelectorUI.loadStage =
            FOLLOWER_SELECTOR_UI_CREATE_SLOT_SPRITE;
        break;

    case FOLLOWER_SELECTOR_UI_CREATE_SLOT_SPRITE:
        if (!FollowerSelectorUI_CreateSlotSprite(
                sFollowerSelectorUI.loadSlot)) {
            return FALSE;
        }
        sFollowerSelectorUI.loadedSlotMask |=
            (u8)(1 << sFollowerSelectorUI.loadSlot);
        sFollowerSelectorUI.loadStage =
            FOLLOWER_SELECTOR_UI_LOAD_SLOT_CHAR;
        break;

    case FOLLOWER_SELECTOR_UI_LOAD_READY:
        break;

    default:
        return FALSE;
    }
    return TRUE;
}

BOOL OverworldFollowerSelectorUI_Open(
    FieldSystem *fieldSystem,
    u8 highlightedSlot)
{
    int slot;

    if (!FollowerSelectorUI_EnsureState()) {
        return FALSE;
    }

    sFollowerSelectorUI.fieldSystem = fieldSystem;
    sFollowerSelectorUI.selectedSlot = 0xFF;
    for (slot = 0; slot < FOLLOWER_SELECTOR_PARTY_SIZE; slot++) {
        FollowerSelectorSlotVisual *visual = &sFollowerSelectorUI.slots[slot];

        visual->basePosition.x =
            (FOLLOWER_SELECTOR_GRID_CENTER_X
                + ((slot % 3) - 1)
                    * FOLLOWER_SELECTOR_COLUMN_SPACING_X)
            * FOLLOWER_SELECTOR_FX32_ONE;
        visual->basePosition.y =
            (32 + (slot / 3) * 24) * FOLLOWER_SELECTOR_FX32_ONE;
        visual->basePosition.z = 0;
    }
    sFollowerSelectorUI.isOpen = TRUE;
    sFollowerSelectorUI.loadStage = FOLLOWER_SELECTOR_UI_CREATE_MANAGER;
    sFollowerSelectorUI.loadSlot = 0;
    sFollowerSelectorUI.managerLoadIndex = 0;
    sFollowerSelectorUI.loadedSlotMask = 0;
    OverworldFollowerSelectorUI_SetSelection(highlightedSlot);
    return TRUE;
}

static void FollowerSelectorUI_RefreshTransforms(void)
{
    int slot;

    for (slot = 0; slot < FOLLOWER_SELECTOR_PARTY_SIZE; slot++) {
        FollowerSelectorSlotVisual *visual = &sFollowerSelectorUI.slots[slot];
        VecFx32 position = visual->basePosition;

        if (visual->sprite == NULL) {
            continue;
        }
        if (slot == sFollowerSelectorUI.selectedSlot && visual->eligible) {
            position.y -= (4 + ((sFollowerSelectorUI.frame >> 2) & 1))
                * FOLLOWER_SELECTOR_FX32_ONE;
        }
        Sprite_SetMatrix(visual->sprite, &position);
    }
}

void OverworldFollowerSelectorUI_SetSelection(u8 highlightedSlot)
{
    if (sFollowerSelectorUIStorage == NULL || !sFollowerSelectorUI.isOpen) {
        return;
    }
    if (highlightedSlot >= FOLLOWER_SELECTOR_PARTY_SIZE
        || (sFollowerSelectorUI.eligibleMask & (1 << highlightedSlot)) == 0) {
        return;
    }
    if (sFollowerSelectorUI.selectedSlot != highlightedSlot) {
        sFollowerSelectorUI.selectedSlot = highlightedSlot;
        sFollowerSelectorUI.frame = 0;
        FollowerSelectorUI_RefreshTransforms();
    }
}

BOOL OverworldFollowerSelectorUI_Update(void)
{
    if (sFollowerSelectorUIStorage == NULL) {
        return FALSE;
    }
    if (sFollowerSelectorUI.loadStage
            != FOLLOWER_SELECTOR_UI_LOAD_READY
        && !FollowerSelectorUI_LoadNextUnit()) {
        OverworldFollowerSelectorUI_Close();
        return FALSE;
    }
    if (sFollowerSelectorUI.loadStage
            != FOLLOWER_SELECTOR_UI_LOAD_READY) {
        return FALSE;
    }
    if (OverworldFollowerSelector_IsActiveFlagSet()
        && sFollowerSelectorUI.spriteList != NULL) {
        sFollowerSelectorUI.frame++;
        FollowerSelectorUI_RefreshTransforms();
        SpriteList_RenderAndAnimateSprites(sFollowerSelectorUI.spriteList);
    }
    return TRUE;
}

BOOL OverworldFollowerSelectorUI_IsOpen(void)
{
    return sFollowerSelectorUIStorage != NULL && sFollowerSelectorUI.isOpen;
}
