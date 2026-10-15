#include "../../include/overworld_actor_appearance_internal.h"
#include "../../include/map_events_internal.h"
#include "../../include/constants/file.h"

/* HeartGold USA: unk_02023694.s / nnsys kernel.h / nnsys.s.
 * The draw owns a RenderObj at +30, but model/texture resources are shared.
 * Stock rebinds the resource keys before each draw and releases them after it;
 * the draw's +9C key, not texture+2C, is the stable original palette owner. */
#define APPEARANCE_DRAW_BYTES 0xC4
#define APPEARANCE_DRAW_RENDER 0x30
#define APPEARANCE_DRAW_CALLBACK 0x50
#define APPEARANCE_DRAW_COMMAND 0x54
#define APPEARANCE_DRAW_TIMING 0x55
#define APPEARANCE_DRAW_MODEL 0x88
#define APPEARANCE_DRAW_TEXTURE 0x8C
#define APPEARANCE_DRAW_PALETTE_KEY 0x9C
#define APPEARANCE_TEX_HEADER_BYTES 0x3C
#define APPEARANCE_TEX_MAGIC 0x30584554 /* TEX0 */
#define APPEARANCE_MAX_PALETTE_BYTES 512
#define APPEARANCE_MATERIAL_COMMAND 4
#define APPEARANCE_MATERIAL_TIMING 2 /* after result, before command emission */
#define APPEARANCE_TEXFMT_PLTT16 3
#define APPEARANCE_OBJECT_ID_START 0xE0

typedef void (*AppearanceCallback)(void *);
typedef u32 (*AppearanceAllocPaletteFunc)(u32, BOOL, u32);
typedef int (*AppearanceFreePaletteFunc)(u32);
typedef void (*AppearanceFlushFunc)(const void *, u32);
typedef void (*AppearanceBeginLoadFunc)(void);
typedef BOOL (*AppearanceQueueFunc)(u32, u32, const void *, u32);
typedef u32 (*AppearancePendingFunc)(void);

typedef struct AppearanceRecord {
    OverworldActorAppearanceSnapshot view;
    struct AppearanceRecord *next;
    const OverworldActorStateSnapshot *actor;
    LocalMapObject *object;
    MapObjectMan *manager;
    void *draw;
    void *model;
    void *texture;
    AppearanceCallback originalCallback;
    u8 originalCommand;
    u8 originalTiming;
    u8 uploadPending; /* Existing private alignment byte. */
} AppearanceRecord;

static AppearanceRecord *sAppearance;

/* Both Field-capsule callers use the same native range check. */
BOOL AppearanceNative_RamSpan(const void *pointer, u32 bytes);

static inline BOOL Appearance_RamSpan(const void *pointer, u32 size)
{
    return AppearanceNative_RamSpan(pointer, size);
}

static BOOL Appearance_ScratchSpan(const void *pointer, u32 size)
{
    u32 address = (u32)(uintptr_t)pointer;
    /* NNS_G3dDraw's temporary render state/material may be on the native
     * public stack in DTCM. This does not widen heap/resource bounds. */
    return Appearance_RamSpan(pointer, size)
        || (address >= 0x027E0000 && address <= 0x027E3FC0
            && size <= 0x027E3FC0 - address);
}

static u32 Appearance_U32(const void *base, u32 offset)
{
    return *(const u32 *)((const u8 *)base + offset);
}

static u16 Appearance_U16(const void *base, u32 offset)
{
    return *(const u16 *)((const u8 *)base + offset);
}

static void *Appearance_Pointer(const void *base, u32 offset)
{
    return (void *)(uintptr_t)Appearance_U32(base, offset);
}

static AppearanceCallback Appearance_GetCallback(void *draw)
{
    return (AppearanceCallback)(uintptr_t)Appearance_U32(draw, APPEARANCE_DRAW_CALLBACK);
}

static void Appearance_SetCallback(void *draw, AppearanceCallback callback)
{
    *(u32 *)((u8 *)draw + APPEARANCE_DRAW_CALLBACK) = (u32)(uintptr_t)callback;
}

static void Appearance_FreePalette(u32 key)
{
    if (key != 0) {
        (*(AppearanceFreePaletteFunc *)0x02110930)(key);
    }
}

static u32 Appearance_AllocPalette(u32 bytes)
{
    return (*(AppearanceAllocPaletteFunc *)0x0211092C)(bytes, FALSE, 0);
}

static BOOL Appearance_Upload(const void *palette, u32 key, u32 bytes)
{
    ((AppearanceFlushFunc)0x020D2894)(palette, bytes);
    return ((AppearanceQueueFunc)0x020205D9)(1, (key & 0xFFFF) << 3, palette, bytes);
}

static BOOL __attribute__((noinline)) Appearance_CompleteUpload(AppearanceRecord *record)
{
    if (record->uploadPending != 0
        && ((AppearancePendingFunc)0x02020639)() != 0) {
        return FALSE;
    }
    record->uploadPending = 0;
    return TRUE;
}

static u16 *Appearance_Original(AppearanceRecord *record)
{
    return (u16 *)(record + 1);
}

static u16 *Appearance_Tinted(AppearanceRecord *record)
{
    return Appearance_Original(record) + record->view.paletteBytes / 2;
}

static BOOL Appearance_IdentityMatches(
    const AppearanceRecord *record, const OverworldActorStateSnapshot *actor)
{
    const OverworldActorAppearanceSnapshot *view = &record->view;
    return Appearance_RamSpan(actor, sizeof(*actor))
        && actor->active && actor->presentationAttached
        && actor->version == OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        && actor->size == sizeof(*actor)
        && actor->handle.slot == view->handle.slot
        && actor->handle.generation == view->handle.generation
        && actor->handle.fieldEpoch == view->handle.fieldEpoch
        && actor->handle.mapGeneration == view->handle.mapGeneration
        && actor->handle.encounterGeneration == view->handle.encounterGeneration
        && actor->subjectIdentity == view->subjectIdentity
        && actor->authorityGeneration == view->authorityGeneration
        && actor->engineAnchorGeneration == view->engineAnchorGeneration
        && actor->presentationGeneration == view->presentationGeneration
        && actor->species == view->species && actor->form == view->form
        && actor->level == view->level && actor->role == view->role;
}

/* Check current pool membership before dereferencing a retained MapObject.
 * The old draw is never dereferenced after a manager or object replacement. */
static void *Appearance_CurrentDraw(
    MapObjectMan *manager, LocalMapObject *object, u16 slot)
{
    u32 index;
    u32 callback;
    void *draw;

    if (!Appearance_RamSpan(manager, sizeof(*manager)) || manager->fsys == NULL
        || manager->object_count > 128
        || !Appearance_RamSpan(manager->objects,
            manager->object_count * sizeof(*object))) {
        return NULL;
    }
    for (index = 0; index < manager->object_count; ++index) {
        if (&manager->objects[index] == object) {
            break;
        }
    }
    if (index == manager->object_count
        || (object->flags & (MAPOBJECTFLAG_ACTIVE | MAPOBJECTFLAG_UNK22))
            != MAPOBJECTFLAG_ACTIVE
        || object->id != APPEARANCE_OBJECT_ID_START + slot
        || (MapObjectMan *)(uintptr_t)object->unkB4 != manager) {
        return NULL;
    }
    callback = (u32)(uintptr_t)object->unkC8;
    if (callback != 0x021F7895 && callback != 0x021F88F1) {
        return NULL;
    }
    draw = Appearance_Pointer(object->unk108, callback == 0x021F7895 ? 0 : 4);
    return Appearance_RamSpan(draw, APPEARANCE_DRAW_BYTES) ? draw : NULL;
}

static BOOL Appearance_PaletteSource(void *draw, const u16 **palette, u16 *bytes)
{
    const u8 *texture = Appearance_Pointer(draw, APPEARANCE_DRAW_TEXTURE);
    u32 size, paletteBytes, paletteOffset, dictionaryOffset, entryOffset, stride, count, index;
    const u8 *dictionary;

    if (((uintptr_t)texture & 3) != 0
        || !Appearance_RamSpan(texture, APPEARANCE_TEX_HEADER_BYTES)
        || Appearance_U32(texture, 0) != APPEARANCE_TEX_MAGIC) {
        return FALSE;
    }
    size = Appearance_U32(texture, 4);
    paletteBytes = (u32)Appearance_U16(texture, 0x30) << 3;
    paletteOffset = Appearance_U32(texture, 0x38);
    dictionaryOffset = Appearance_U16(texture, 0x0E);
    if (!Appearance_RamSpan(texture, size) || paletteBytes < 32
        || paletteBytes > APPEARANCE_MAX_PALETTE_BYTES || (paletteBytes & 31) != 0
        || (paletteOffset & 1) != 0
        || paletteOffset < APPEARANCE_TEX_HEADER_BYTES || paletteOffset > size
        || paletteBytes > size - paletteOffset
        || (dictionaryOffset & 3) != 0
        || dictionaryOffset < APPEARANCE_TEX_HEADER_BYTES || dictionaryOffset > size
        || size - dictionaryOffset < 8
        || Appearance_U32(draw, APPEARANCE_DRAW_PALETTE_KEY) == 0) {
        return FALSE;
    }
    dictionary = texture + dictionaryOffset;
    count = dictionary[1];
    entryOffset = Appearance_U16(dictionary, 6);
    size -= dictionaryOffset;
    if (Appearance_U16(dictionary, 2) < 8
        || Appearance_U16(dictionary, 2) > size) {
        return FALSE;
    }
    size = Appearance_U16(dictionary, 2);
    if (count == 0 || count > 64 || (entryOffset & 3) != 0
        || entryOffset < 8 || entryOffset > size
        || size - entryOffset < 4) {
        return FALSE;
    }
    stride = Appearance_U16(dictionary, entryOffset);
    entryOffset += 4;
    if (stride < 4 || (stride & 3) != 0 || count * stride > size - entryOffset) {
        return FALSE;
    }
    for (index = 0; index < count; ++index) {
        if (((Appearance_U32(dictionary, entryOffset + index * stride) >> 26) & 7)
            != APPEARANCE_TEXFMT_PLTT16) {
            return FALSE;
        }
    }
    *palette = (const u16 *)(texture + paletteOffset);
    *bytes = paletteBytes;
    return TRUE;
}

static void Appearance_BlendPalette(AppearanceRecord *record)
{
    const u16 *source = Appearance_Original(record);
    u16 *destination = Appearance_Tinted(record);
    u32 index, channel;
    u32 strength = record->view.strength;

    for (index = 0; index < record->view.paletteBytes / 2; ++index) {
        u16 color = source[index];
        u16 result = color & 0x8000;
        /* Keep each PLTT16 palette's color zero, including transparency and
         * black outlines. Never accumulate tint from the previous result. */
        if ((index & 15) == 0) {
            destination[index] = color;
            continue;
        }
        for (channel = 0; channel < 3; ++channel) {
            u32 original = (color >> (channel * 5)) & 31;
            u32 target = (record->view.mode == OVERWORLD_ACTOR_APPEARANCE_RED
                ? channel == 0 : channel == 2) ? 31 : 0;
            result |= ((original * (16 - strength) + target * strength + 8) >> 4)
                << (channel * 5);
        }
        destination[index] = result;
    }
}

static void Appearance_ApplyMaterial(void *renderState)
{
    AppearanceRecord *record;
    void *renderObject;
    u32 *material;

    if (!Appearance_ScratchSpan(renderState, 0xB4)) {
        return;
    }
    renderObject = Appearance_Pointer(renderState, 4);
    material = Appearance_Pointer(renderState, 0xB0);

    for (record = sAppearance; record != NULL; record = record->next) {
        u32 originalBase, offset;
        if ((u8 *)record->draw + APPEARANCE_DRAW_RENDER != renderObject
            || record->view.mode == OVERWORLD_ACTOR_APPEARANCE_NONE
            || record->view.strength == 0
            || record->view.yielded
            || !Appearance_CompleteUpload(record)
            || !Appearance_IdentityMatches(record, record->actor)
            || Appearance_CurrentDraw(record->manager, record->object,
                record->view.handle.slot) != record->draw
            || Appearance_Pointer(record->draw, APPEARANCE_DRAW_MODEL) != record->model
            || Appearance_Pointer(record->draw, APPEARANCE_DRAW_TEXTURE) != record->texture
            || Appearance_U32(record->draw, APPEARANCE_DRAW_PALETTE_KEY)
                != record->view.originalPaletteKey
            || !Appearance_ScratchSpan(material, 0x38)
            || ((material[4] >> 26) & 7) != APPEARANCE_TEXFMT_PLTT16) {
            continue;
        }
        originalBase = (record->view.originalPaletteKey & 0xFFFF) >> 1;
        if (material[5] < originalBase) {
            return;
        }
        offset = material[5] - originalBase;
        if (offset > (record->view.paletteBytes - 32) / 16 || (offset & 1) != 0) {
            return;
        }
        record->view.lastOriginalBase = material[5];
        material[5] = ((record->view.privatePaletteKey & 0xFFFF) >> 1) + offset;
        record->view.lastTintedBase = material[5];
        ++record->view.appliedMaterials;
        return;
    }
}

static BOOL __attribute__((section(".overworld_appearance_release"), noinline))
Appearance_Release(AppearanceRecord **link, MapObjectMan *manager)
{
    AppearanceRecord *record = *link;
    void *draw;

    record->view.mode = OVERWORLD_ACTOR_APPEARANCE_NONE;
    record->view.strength = 0;
    if (!Appearance_CompleteUpload(record)) {
        return FALSE;
    }
    draw = manager == record->manager
        ? Appearance_CurrentDraw(manager, record->object, record->view.handle.slot) : NULL;

    if (draw == record->draw && Appearance_GetCallback(draw) == Appearance_ApplyMaterial) {
        Appearance_SetCallback(draw, record->originalCallback);
        *((u8 *)draw + APPEARANCE_DRAW_COMMAND) = record->originalCommand;
        *((u8 *)draw + APPEARANCE_DRAW_TIMING) = record->originalTiming;
    }
    *link = record->next;
    Appearance_FreePalette(record->view.privatePaletteKey);
    sys_FreeMemoryEz(record);
    return TRUE;
}

OverworldActorAppearanceResult OverworldActorAppearance_Update(
    MapObjectMan *manager, const OverworldActorAppearanceInput *input)
{
    AppearanceRecord **link = &sAppearance;
    AppearanceRecord *record;
    const OverworldActorStateSnapshot *actor;
    const u16 *palette;
    void *draw;
    u16 bytes;
    u8 mode, strength;
    u32 index;

    if (input == NULL || !Appearance_RamSpan(input->actor, sizeof(*actor))) {
        return OVERWORLD_ACTOR_APPEARANCE_INVALID;
    }
    actor = input->actor;
    if (!actor->active || !actor->presentationAttached
        || actor->version != OVERWORLD_ACTOR_SYSTEM_ABI_VERSION || actor->size != sizeof(*actor)
        || actor->handle.slot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
        || actor->handle.generation == 0 || actor->handle.fieldEpoch == 0
        || actor->role < OVERWORLD_ACTOR_ROLE_WILD || actor->role > OVERWORLD_ACTOR_ROLE_MOUNTED
        || input->redStrength > OVERWORLD_ACTOR_APPEARANCE_MAX_STRENGTH
        || (input->restTint | input->damageActive) > 1) {
        return OVERWORLD_ACTOR_APPEARANCE_INVALID;
    }
    while (*link != NULL && (*link)->view.handle.slot != actor->handle.slot) {
        link = &(*link)->next;
    }
    record = *link;
    draw = Appearance_CurrentDraw(manager, input->pokemon, actor->handle.slot);
    if (record != NULL && (!Appearance_IdentityMatches(record, actor)
        || record->actor != actor || record->manager != manager || record->object != input->pokemon
        || record->draw != draw
        || Appearance_Pointer(draw, APPEARANCE_DRAW_MODEL) != record->model
        || Appearance_Pointer(draw, APPEARANCE_DRAW_TEXTURE) != record->texture
        || Appearance_U32(draw, APPEARANCE_DRAW_PALETTE_KEY) != record->view.originalPaletteKey)) {
        if (!Appearance_Release(link, manager)) {
            return OVERWORLD_ACTOR_APPEARANCE_INVALID;
        }
        record = NULL;
    }
    if (draw == NULL) {
        return OVERWORLD_ACTOR_APPEARANCE_INVALID;
    }
    /* Recall can restore our generic callback after its old actor record
     * was forgotten. It owns no palette without a matching record. */
    if (record == NULL && Appearance_GetCallback(draw) == Appearance_ApplyMaterial) {
        Appearance_SetCallback(draw, NULL);
        *((u8 *)draw + APPEARANCE_DRAW_COMMAND) = 0;
        *((u8 *)draw + APPEARANCE_DRAW_TIMING) = 0;
    }
    mode = (input->redStrength | input->damageActive) != 0 ? OVERWORLD_ACTOR_APPEARANCE_RED
        : input->restTint ? OVERWORLD_ACTOR_APPEARANCE_BLUE : OVERWORLD_ACTOR_APPEARANCE_NONE;
    strength = (input->redStrength | input->damageActive) != 0 ? input->redStrength
        : input->restTint ? OVERWORLD_ACTOR_APPEARANCE_BLUE_STRENGTH : 0;
    if (record != NULL && Appearance_GetCallback(draw) != Appearance_ApplyMaterial
        && Appearance_GetCallback(draw) != NULL) {
        /* Recall may save our callback and restore it later. Keep the record
         * until then, but a full-HP/cleared mode must already draw normally. */
        record->view.mode = mode;
        record->view.strength = strength;
        record->view.yielded = TRUE;
        return OVERWORLD_ACTOR_APPEARANCE_YIELDED;
    }
    if (mode == OVERWORLD_ACTOR_APPEARANCE_NONE) {
        if (record != NULL) {
            Appearance_Release(link, manager);
        }
        return OVERWORLD_ACTOR_APPEARANCE_CLEAR;
    }
    if (record == NULL) {
        if (Appearance_GetCallback(draw) != NULL) {
            return OVERWORLD_ACTOR_APPEARANCE_YIELDED;
        }
        if (!Appearance_PaletteSource(draw, &palette, &bytes)
            || !Appearance_RamSpan(Appearance_Pointer(draw, APPEARANCE_DRAW_MODEL), 0x40)
            || Appearance_Pointer(draw, APPEARANCE_DRAW_RENDER + 4)
                != Appearance_Pointer(draw, APPEARANCE_DRAW_MODEL)) {
            return OVERWORLD_ACTOR_APPEARANCE_UNSUPPORTED;
        }
        record = sys_AllocMemory(HEAPID_WORLD, sizeof(*record) + bytes * 2);
        if (record == NULL) {
            return OVERWORLD_ACTOR_APPEARANCE_NO_MEMORY;
        }
        *record = (AppearanceRecord){0};
        record->view.privatePaletteKey = Appearance_AllocPalette(bytes);
        if (record->view.privatePaletteKey == 0) {
            sys_FreeMemoryEz(record);
            return OVERWORLD_ACTOR_APPEARANCE_NO_MEMORY;
        }
        record->actor = actor;
        record->object = input->pokemon;
        record->manager = manager;
        record->draw = draw;
        record->model = Appearance_Pointer(draw, APPEARANCE_DRAW_MODEL);
        record->texture = Appearance_Pointer(draw, APPEARANCE_DRAW_TEXTURE);
        record->originalCallback = Appearance_GetCallback(draw);
        record->originalCommand = *((u8 *)draw + APPEARANCE_DRAW_COMMAND);
        record->originalTiming = *((u8 *)draw + APPEARANCE_DRAW_TIMING);
        record->view.handle = actor->handle;
        record->view.subjectIdentity = actor->subjectIdentity;
        record->view.authorityGeneration = actor->authorityGeneration;
        record->view.engineAnchorGeneration = actor->engineAnchorGeneration;
        record->view.presentationGeneration = actor->presentationGeneration;
        record->view.species = actor->species;
        record->view.form = actor->form;
        record->view.level = actor->level;
        record->view.role = actor->role;
        record->view.actorPointer = (u32)(uintptr_t)actor;
        record->view.objectPointer = (u32)(uintptr_t)input->pokemon;
        record->view.drawPointer = (u32)(uintptr_t)draw;
        record->view.modelPointer = (u32)(uintptr_t)record->model;
        record->view.texturePointer = (u32)(uintptr_t)record->texture;
        record->view.paletteBytes = bytes;
        record->view.originalPalettePointer = (u32)(uintptr_t)Appearance_Original(record);
        record->view.tintedPalettePointer = (u32)(uintptr_t)Appearance_Tinted(record);
        record->view.originalPaletteKey = Appearance_U32(draw, APPEARANCE_DRAW_PALETTE_KEY);
        for (index = 0; index < bytes / 2; ++index) {
            Appearance_Original(record)[index] = palette[index];
        }
        record->next = *link;
        *link = record;
    }
    if (!Appearance_CompleteUpload(record)) {
        return OVERWORLD_ACTOR_APPEARANCE_YIELDED;
    }
    if (record->view.mode != mode || record->view.strength != strength
        || record->view.yielded || Appearance_GetCallback(draw) == NULL) {
        record->view.mode = mode;
        record->view.strength = strength;
        Appearance_BlendPalette(record);
        record->uploadPending = Appearance_Upload(Appearance_Tinted(record),
            record->view.privatePaletteKey, record->view.paletteBytes);
        if (!record->uploadPending) {
            record->view.yielded = TRUE;
            return OVERWORLD_ACTOR_APPEARANCE_YIELDED;
        }
    }
    record->view.yielded = FALSE;
    Appearance_SetCallback(draw, Appearance_ApplyMaterial);
    *((u8 *)draw + APPEARANCE_DRAW_COMMAND) = APPEARANCE_MATERIAL_COMMAND;
    *((u8 *)draw + APPEARANCE_DRAW_TIMING) = APPEARANCE_MATERIAL_TIMING;
    return OVERWORLD_ACTOR_APPEARANCE_TINTED;
}

void OverworldActorAppearance_Forget(MapObjectMan *manager, u16 slot)
{
    AppearanceRecord **link = &sAppearance;
    while (*link != NULL) {
        if ((*link)->view.handle.slot == slot) {
            Appearance_Release(link, manager);
            return;
        }
        link = &(*link)->next;
    }
}

void OverworldActorAppearance_Reset(MapObjectMan *manager)
{
    AppearanceRecord **link = &sAppearance;
    while (*link != NULL) {
        if (!Appearance_Release(link, manager)) {
            link = &(*link)->next;
        }
    }
}

BOOL Appearance_ClearForUnload(MapObjectMan *manager)
{
    AppearanceRecord *record;
    u32 index;

    if (manager != NULL && (!Appearance_RamSpan(manager, sizeof(*manager))
        || manager->fsys == NULL || manager->object_count > 128
        || !Appearance_RamSpan(manager->objects,
            manager->object_count * sizeof(LocalMapObject)))) {
        return FALSE;
    }
    for (record = sAppearance; record != NULL; record = record->next) {
        void *draw = manager == record->manager
            ? Appearance_CurrentDraw(manager, record->object, record->view.handle.slot) : NULL;
        if (draw == record->draw && Appearance_GetCallback(draw) != NULL
            && Appearance_GetCallback(draw) != Appearance_ApplyMaterial) {
            return FALSE;
        }
    }
    OverworldActorAppearance_Reset(manager);
    if (sAppearance != NULL) {
        return FALSE;
    }
    if (manager == NULL) {
        return TRUE;
    }
    /* Cancel may restore a saved tint callback whose actor record is already
     * gone. Clear these callbacks too; they must not outlive overlay 1. */
    for (index = 0; index < manager->object_count; ++index) {
        LocalMapObject *object = &manager->objects[index];
        u32 slot = object->id - APPEARANCE_OBJECT_ID_START;
        void *draw;
        if (slot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS) {
            continue;
        }
        draw = Appearance_CurrentDraw(manager, object, slot);
        if (draw != NULL && Appearance_GetCallback(draw) == Appearance_ApplyMaterial) {
            Appearance_SetCallback(draw, NULL);
            *((u8 *)draw + APPEARANCE_DRAW_COMMAND) = 0;
            *((u8 *)draw + APPEARANCE_DRAW_TIMING) = 0;
        }
    }
    return TRUE;
}

const OverworldActorAppearanceSnapshot *OverworldActorAppearance_Inspect(u16 slot)
{
    const AppearanceRecord *record;
    for (record = sAppearance; record != NULL; record = record->next) {
        if (record->view.handle.slot == slot) {
            return &record->view;
        }
    }
    return NULL;
}
