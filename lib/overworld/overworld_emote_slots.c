#include "overworld_emote_slots_internal.h"

#ifdef OVERWORLD_EMOTE_HOST
#define EMOTE_PART(name)
#define EMOTE_DATA
#else
#define EMOTE_PART(name) __attribute__((noinline,section(".overworld_emote_" name)))
#define EMOTE_DATA __attribute__((section(".overworld_emote_descriptor")))
#endif

/* Resource admission around the stock effect/model/animation/draw owners. */
enum { EMOTE_FREE, EMOTE_RESERVED, EMOTE_ACTIVE, EMOTE_RETIRING };
static void *EMOTE_PART("loadmember") OverworldEmoteSlots_LoadMember(void *context, int member)
{
    int bytes = ov01_021F149C(context, member);
    void *file = ov01_021F141C(context, bytes, 1);
    if (file) ov01_021F14A8(context, member, file);
    return file;
}

static void EMOTE_PART("collect") OverworldEmoteSlots_Collect(SysTask *task, void *raw);
static BOOL EMOTE_PART("initialize") OverworldEmoteSlots_Initialize(void *effect, OverworldEmoteNativeData *data);
static void EMOTE_PART("destroy") OverworldEmoteSlots_Destroy(void *effect, OverworldEmoteNativeData *data);
static void EMOTE_PART("update") OverworldEmoteSlots_Update(void *effect, OverworldEmoteNativeData *data);
static const OverworldEmoteNativeDescriptor descriptor EMOTE_DATA = {
    0x68, OverworldEmoteSlots_Initialize, OverworldEmoteSlots_Destroy,
    OverworldEmoteSlots_Update, ov01_02203DC0
};

static void EMOTE_PART("release") OverworldEmoteSlots_Release(OverworldEmoteSlot *slot)
{
    /* Only before any transfer, or at VWait after the native queue drained. */
    if (slot->textureKey) NNS_GfdDefaultFuncFreeTexVram(slot->textureKey);
    if (slot->paletteKey) NNS_GfdDefaultFuncFreePlttVram(slot->paletteKey);
    if (slot->animationFile) ov01_021F1448(slot->animationFile);
    if (slot->iconFile) ov01_021F1448(slot->iconFile);
    OverworldEmoteOwner *owner = slot->owner;
    MIi_CpuClear32(0, slot, sizeof(*slot));
    owner->count--;
}

static void EMOTE_PART("retire") OverworldEmoteSlots_Retire(OverworldEmoteSlot *slot)
{
    if (slot->state == EMOTE_FREE || slot->state == EMOTE_RETIRING) return;
    if (slot->model) sub_02023DA4(slot->model);
    slot->model = NULL;
    slot->effect = NULL;
    slot->state = EMOTE_RETIRING;
}

static void EMOTE_PART("collect") OverworldEmoteSlots_Collect(SysTask *task, void *raw)
{
    OverworldEmoteOwner *owner = raw;
    /* Main runs Field VBlank transfer work before its VWait task queue.
     * Never free a source or reuse its keys while the native queue references it. */
    if (GF_GetNumPendingVramTransferTasks()) return;
    for (unsigned i = 0; i < 3; i++)
        if (owner->slots[i].state == EMOTE_RETIRING)
            OverworldEmoteSlots_Release(&owner->slots[i]);
    if (!owner->count) {
        SysTask_Destroy(task);
        owner->retirementTask = NULL;
        if (owner->closing) {
            ov01_021F1448(owner->animationFile);
            ov01_021F1448(owner->modelFile);
            ov01_021F1448(owner);
        }
    }
}

OverworldEmoteOwner *EMOTE_PART("createowner") OverworldEmoteSlots_CreateOwner(void *context)
{
    OverworldEmoteOwner *owner = ov01_021F141C(context, sizeof(*owner), 0);
    if (!owner) return NULL;
    *owner = (OverworldEmoteOwner){0};
    owner->context = context;
    /* Exactly the two original native geometry/animation members. No extra
     * resource IDs, model pool, texture manager, or effect manager is created. */
    owner->modelFile = OverworldEmoteSlots_LoadMember(context, 130);
    owner->animationFile = OverworldEmoteSlots_LoadMember(context, 140);
    owner->texture = owner->modelFile ? NNS_G3dGetTex(owner->modelFile) : NULL;
    if (!owner->texture || !owner->animationFile) {
        if (owner->animationFile) ov01_021F1448(owner->animationFile);
        if (owner->modelFile) ov01_021F1448(owner->modelFile);
        ov01_021F1448(owner);
        return NULL;
    }
    return owner;
}

void EMOTE_PART("destroyowner") OverworldEmoteSlots_DestroyOwner(OverworldEmoteOwner *owner)
{
    /* Native ov01_021F13F4 destroys all effects before resource owners, then
     * destroys the context. Collect therefore needs no context access here. */
    if (!owner) return;
    owner->closing = TRUE;
    if (!owner->count) {
        if (owner->retirementTask) SysTask_Destroy(owner->retirementTask);
        ov01_021F1448(owner->animationFile);
        ov01_021F1448(owner->modelFile);
        ov01_021F1448(owner);
    }
}

static OverworldEmoteSlot *EMOTE_PART("select") OverworldEmoteSlots_Select(OverworldEmoteOwner *owner, LocalMapObject *object)
{
    OverworldEmoteSlot *slot = NULL;
    for (unsigned i = 0; i < 3; i++) {
        if (owner->slots[i].state && owner->slots[i].object == object) return NULL;
        if (!slot && owner->slots[i].state == EMOTE_FREE) slot = &owner->slots[i];
    }
    return slot;
}

static BOOL EMOTE_PART("prepare") OverworldEmoteSlots_Prepare(OverworldEmoteSlot *slot, void *context, int emote)
{
    slot->iconFile = OverworldEmoteSlots_LoadMember(context, emote + 2);
    slot->animationFile = OverworldEmoteSlots_LoadMember(context, emote + 150);
    slot->texture = slot->iconFile ? NNS_G3dGetTex(slot->iconFile) : NULL;
    if (!slot->texture || !slot->animationFile || sub_020209AC(slot->texture, 0) != 512)
        return FALSE;
    slot->textureKey = NNS_GfdDefaultFuncAllocTexVram(512, FALSE, 0);
    if (!slot->textureKey) return FALSE;
    slot->paletteKey = NNS_GfdDefaultFuncAllocPlttVram(32, FALSE, 0);
    if (!slot->paletteKey) return FALSE;
    return TRUE;
}

void *EMOTE_PART("admit") OverworldEmoteSlots_Admit(void *context, LocalMapObject *object, int emote)
{
    OverworldEmoteOwner *owner = ov01_021F1450(context, 18);
    OverworldEmoteSlot *slot = NULL;
    VecFx32 position, facing;
    if (emote < 0 || emote >= 14 || !owner || owner->closing || owner->count >= 3)
        return NULL;
    slot = OverworldEmoteSlots_Select(owner, object);
    if (!slot) return NULL;
    /* Reserve cleanup before resources or native construction. The task ends
     * after this finite active burst; an idle owner has no scheduled task. */
    if (!owner->retirementTask) {
        owner->retirementTask = SysTask_CreateOnVWaitQueue(OverworldEmoteSlots_Collect, owner, 0);
        if (!owner->retirementTask) return NULL;
    }
    *slot = (OverworldEmoteSlot){.owner=owner, .object=object, .state=EMOTE_RESERVED};
    owner->count++;
    if (!OverworldEmoteSlots_Prepare(slot, context, emote)) goto reject;
    MapObject_CopyPositionVector(object, &position);
    MapObject_CopyFacingVector(object, &facing);
    position.x += facing.x;
    position.z += facing.z;
    OverworldEmoteInit init = {context, owner, object, slot};
    /* Same native constructor as ov01_021F1620, without its NULL-result assert:
     * a failed effect/task/init allocation must roll back this reservation. */
    void *effectManager = ((void **)context)[7];
    void *effect = sub_02068B0C(effectManager, &descriptor, &position, emote,
        &init, MapObject_GetPriority(object) + 1);
    if (effect) return effect;
    /* Failed native init has no destructor. A partially queued transfer must
     * retain its sources/keys until Collect; rollback otherwise is immediate. */
    OverworldEmoteSlots_Retire(slot);
    if (GF_GetNumPendingVramTransferTasks()) return NULL;
reject:
    OverworldEmoteSlots_Release(slot);
    if (!owner->count) {
        SysTask_Destroy(owner->retirementTask);
        owner->retirementTask = NULL;
    }
    return NULL;
}

static BOOL EMOTE_PART("initialize") OverworldEmoteSlots_Initialize(void *effect, OverworldEmoteNativeData *data)
{
    const OverworldEmoteInit *init = sub_02068D98(effect);
    OverworldEmoteSlot *slot = init->slot;
    OverworldEmoteNativeModelTemplate model = {
        .modelFile=init->owner->modelFile, .texture=init->owner->texture,
        .animation=ov01_0220952C, .textureKey=slot->textureKey, .paletteKey=slot->paletteKey
    };
    VecFx32 position;
    sub_02026E18(init->owner->animationFile, model.animationState);
    sub_02068DB8(effect, &position);
    slot->model = ov01_021F16EC(init->context, &model, &position);
    if (!slot->model) return FALSE;
    data->context=init->context; data->owner=init->owner;
    data->object=init->object; data->slot=slot; data->model=slot->model;
    data->objectId=MapObject_GetID(init->object); data->mapId=MapObject_GetMapID(init->object);
    data->riseVelocity=6 << 12;
    sub_02026E18(slot->animationFile, &data->frames);
    data->frames.texture=slot->texture; data->frames.animationFile=slot->animationFile;
    data->frames.iconFile=slot->iconFile;
    data->frames.destination=(slot->textureKey & 0xFFFF) << 3;
    data->frames.frameBytes=512;
    NNS_G3dMdlSetMdlFogEnableFlagAll(sub_02023F90(slot->model), FALSE);
    sub_02023EA4(slot->model, FALSE);
    slot->effect=effect;
    slot->state=EMOTE_ACTIVE;
    if (!GF_CreateNewVramTransferTask(0, data->frames.destination,
            sub_02020838(slot->texture, 0), 512)
        || !GF_CreateNewVramTransferTask(1, (slot->paletteKey & 0xFFFF) << 3,
            sub_02020888(slot->texture, 0), 32)) return FALSE;
    PlaySE(1501); /* Existing quiet caller pairs this with its unchanged StopSE. */
    return TRUE;
}

static void EMOTE_PART("destroy") OverworldEmoteSlots_Destroy(void *effect, OverworldEmoteNativeData *data)
{
    if (data->slot && data->slot->effect == effect)
        OverworldEmoteSlots_Retire(data->slot);
}

static void EMOTE_PART("update") OverworldEmoteSlots_Update(void *effect, OverworldEmoteNativeData *data)
{
    /* Only replace the stock global-busy clear at its terminal phase. All
     * rise/animation/hold phases and draw execute the unchanged stock owner. */
    if (data->phase == 3) ov01_021F1640(effect);
    else ov01_02203CB8(effect, data);
}
