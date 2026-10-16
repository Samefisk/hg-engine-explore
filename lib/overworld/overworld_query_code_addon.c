#include "../../include/overworld_query_code_addon.h"

#if defined(OVERWORLD_BEHAVIOR_HOST)
static const u32 Addon_FixedImports[9] = {
    0x023DEEA3, 0x023DEEBF, 0x023DEE4D,
    0x01FF9A49, 0x01FF9C95, 0x01FFA39D, 0x023C2F75,
    0x02208201, 0x023C7EA9,
};
#else
#define Addon_FixedImports ((const u32 *)0x01FF9CDC)
#endif

enum { ADDON_EMPTY, ADDON_READY, ADDON_DRAINING, ADDON_REBINDING };
static u32 Addon_Address(const void *pointer) { return (u32)(uintptr_t)pointer; }
static BOOL Addon_Owner(const OverworldQueryCodeAddonOwner *o)
{ return o && o->fieldIdentity-0x02000000u<0x00400000u && o->fieldEpoch && o->mapGeneration; }
static BOOL Addon_SameOwner(const OverworldQueryCodeAddonOwner *a, const OverworldQueryCodeAddonOwner *b)
{ return a->fieldIdentity==b->fieldIdentity && a->fieldEpoch==b->fieldEpoch && a->mapGeneration==b->mapGeneration; }
static BOOL Addon_Ops(const OverworldQueryCodeAddonOps *o)
{ return o && o->loadBlob && o->freeBlob && o->flushData && o->waitWriteBuffer && o->invalidateCode && o->drain; }
static u32 Addon_Checksum(const u8 *bytes, u32 size)
{
    u32 hash=2166136261u, i;
    for(i=0;i<size;++i) hash=(hash^(i>=44 && i<48 ? 0 : bytes[i]))*16777619u;
    return hash;
}
static BOOL Addon_Offset(u32 offset,u32 size)
{ return !(offset&3) && offset<=size-4; }
/* Existing Wild notice capsule tail padding owns this private Thumb leaf. */
static BOOL
#if !defined(OVERWORLD_BEHAVIOR_HOST)
__attribute__((naked, noinline, optimize("Os"), section(".overworld_query_stock_coordinate_import")))
#endif
Addon_StockCoordinateImport(u32 fixed)
{
#if defined(__arm__) && !defined(OVERWORLD_BEHAVIOR_HOST)
    __asm__ volatile(
        ".syntax unified\n"
        "ldr r3, 1f\n"
        "cmp r0, r3\n"
        "beq 3f\n"
        "ldr r3, 2f\n"
        "subs r0, r0, r3\n"
        "cmp r0, #12\n"
        "beq 3f\n"
        "negs r3, r0\n"
        "adcs r0, r3\n"
        "bx lr\n"
        "3: movs r0, #1\n"
        "bx lr\n"
        ".balign 4\n"
        "1: .word 0x01FFD2CD\n"
        "2: .word 0x0205C67D\n"
        ".syntax divided\n");
#else
    return fixed==0x0205C67D || fixed==0x0205C689 || fixed==0x01FFD2CD;
#endif
}

static BOOL Addon_Prepare(void *blob,u32 bytes,u8 **imageOut,u32 *sizeOut)
{
    const OverworldQueryCodeAddonHeader *h=blob;
    const u32 *relocations;
    const OverworldQueryCodeAddonImport *imports;
    u8 *image;
    u32 address=Addon_Address(blob), target, i, j=0;
    u16 *entry16;
    u32 *entry32;
    if(!blob || (address&3) || address<0x02000000 || address>0x02400000
        || bytes>0x02400000-address || bytes-64u>OVERWORLD_QUERY_CODE_ADDON_MAX_BLOB-64u
        || h->magic!=OVERWORLD_QUERY_CODE_ADDON_MAGIC || h->version!=OVERWORLD_QUERY_CODE_ADDON_VERSION || h->headerSize!=64
        || h->blobSize!=bytes || h->imageSize<OVERWORLD_QUERY_CODE_ADDON_ENTRY_BYTES || h->imageSize>OVERWORLD_QUERY_CODE_ADDON_MAX_IMAGE
        || (h->imageSize&3) || h->linkBase!=OVERWORLD_QUERY_CODE_ADDON_LINK_BASE
        || h->entryOffset || h->imageOffset!=64 || h->flags || h->reserved[0] || h->reserved[1]
        || h->entryVersion!=OVERWORLD_QUERY_CODE_ADDON_VERSION || h->entrySize!=OVERWORLD_QUERY_CODE_ADDON_ENTRY_BYTES
        || h->relocationCount>OVERWORLD_QUERY_CODE_ADDON_MAX_RELOCATIONS
        || h->importCount>OVERWORLD_QUERY_CODE_ADDON_MAX_RELOCATIONS
        || h->relocationOffset!=64+h->imageSize
        || h->importOffset!=h->relocationOffset+h->relocationCount*4
        || h->blobSize!=h->importOffset+h->importCount*8
        || h->checksum!=Addon_Checksum(blob,bytes)) return FALSE;
    image=(u8 *)blob+64; target=address+64;
    relocations=(const u32 *)((u8 *)blob+h->relocationOffset);
    imports=(const OverworldQueryCodeAddonImport *)((u8 *)blob+h->importOffset);
    entry16=(u16 *)image; entry32=(u32 *)image;
    if(entry32[0]!=OVERWORLD_QUERY_CODE_ADDON_MAGIC
        || entry32[1]!=(OVERWORLD_QUERY_CODE_ADDON_VERSION | (OVERWORLD_QUERY_CODE_ADDON_ENTRY_BYTES<<16))
        || entry16[4]!=60 || entry16[5]!=sizeof(OverworldPickupRouteState) || entry16[6]!=24 || entry16[7]!=108
        || entry16[8]!=36 || entry16[9]!=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION
        || entry16[38]!=OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION
        || entry16[39]!=OVERWORLD_QUERY_CODE_ADDON_CONDITION_WORLD_BYTES
        || entry16[40]!=88 || entry16[41]!=540
        || entry16[50]!=OVERWORLD_CARGO_QUERY_VERSION || entry16[51]!=sizeof(OverworldCargoQueryState)
        || entry16[52]!=40 || entry16[53]!=140 || entry16[54]!=24604 || entry16[55]) return FALSE;
    for(i=0;i<h->relocationCount;++i) {
        u32 offset=relocations[i], value;
        if(!Addon_Offset(offset,h->imageSize) || (i && offset<=relocations[i-1])) return FALSE;
        value=*(u32 *)(image+offset);
        if((value&~1u)-h->linkBase>=h->imageSize) return FALSE;
        while(j<h->importCount && imports[j].offset<offset) ++j;
        if(j<h->importCount && imports[j].offset==offset) return FALSE;
    }
    for(i=0;i<h->importCount;++i) {
        u32 offset=imports[i].offset, fixed=imports[i].target;
        const u32 *allowed=Addon_FixedImports;
        u32 k;
        for(k=0;k<9 && fixed!=allowed[k];++k) {}
        if(!Addon_Offset(offset,h->imageSize) || (i && offset<=imports[i-1].offset)
            /* The nine-word resident table fills its fixed36-byte slot. */
            || (k==9 && !Addon_StockCoordinateImport(fixed))
            || *(u32 *)(image+offset)!=fixed) return FALSE;
    }
    j=0;
    /* Walk the three callback spans, skipping their immutable ABI metadata. */
    for(i=20;i<OVERWORLD_QUERY_CODE_ADDON_ENTRY_BYTES;i+=4) {
        u32 offset=i, value;
        if(i==76) i=offset=84;
        if(i==100) i=offset=112;
        value=entry32[offset/4];
        while(j<h->relocationCount && relocations[j]<offset) ++j;
        if(j==h->relocationCount || relocations[j]!=offset || !(value&1)
            || (value&~1u)-h->linkBase-OVERWORLD_QUERY_CODE_ADDON_ENTRY_BYTES
                >=h->imageSize-OVERWORLD_QUERY_CODE_ADDON_ENTRY_BYTES) return FALSE;
    }
    /* All admission checks finish before changing any executable word. */
    for(i=0;i<h->relocationCount;++i) {
        u32 *word=(u32 *)(image+relocations[i]);
        *word=target+(*word-h->linkBase);
    }
    *imageOut=image; *sizeOut=h->imageSize;
    return TRUE;
}

OverworldQueryCodeAddonStatus OverworldQueryCodeAddon_Load(
    OverworldQueryCodeAddonState *state,const OverworldQueryCodeAddonOwner *owner,
    const OverworldQueryCodeAddonOps *ops,u32 member,u32 expected)
{
    void *blob=NULL; u32 loaded=0, imageSize=0; u8 *image=NULL;
    if(!state || !Addon_Owner(owner) || !Addon_Ops(ops)
        || expected-64u>OVERWORLD_QUERY_CODE_ADDON_MAX_BLOB-64u) return OVERWORLD_QUERY_ADDON_INVALID;
    if(state->blob || state->entry || state->phase!=ADDON_EMPTY) {
        return state->phase==ADDON_READY && state->blob && state->entry
            && state->memberId==member && state->blobSize==expected
            && Addon_SameOwner(&state->owner,owner)
            ? OVERWORLD_QUERY_ADDON_OK : OVERWORLD_QUERY_ADDON_BUSY;
    }
    if(!ops->loadBlob(member,expected,&blob,&loaded)) {
        if(blob) ops->freeBlob(blob);
        return OVERWORLD_QUERY_ADDON_LOAD_FAILED;
    }
    if(loaded!=expected || !Addon_Prepare(blob,loaded,&image,&imageSize)) {
        if(blob) ops->freeBlob(blob);
        return OVERWORLD_QUERY_ADDON_BAD_PACKAGE;
    }
    ops->flushData(image,imageSize);
    ops->waitWriteBuffer();
    ops->invalidateCode(image,imageSize);
    state->blob=blob; state->blobSize=loaded; state->owner=*owner; state->memberId=member;
    state->entry=(const OverworldQueryCodeAddonEntry *)image;
    state->phase=ADDON_READY;
    return OVERWORLD_QUERY_ADDON_OK;
}
const OverworldQueryCodeAddonEntry *OverworldQueryCodeAddon_Acquire(
    const OverworldQueryCodeAddonState *state,const OverworldQueryCodeAddonOwner *owner)
{
    return state && Addon_Owner(owner) && state->phase==ADDON_READY && state->blob
        && state->entry && Addon_SameOwner(&state->owner,owner) ? state->entry : NULL;
}
OverworldQueryCodeAddonStatus
#if !defined(OVERWORLD_BEHAVIOR_HOST)
__attribute__((noinline,section(".overworld_query_code_addon_rebind")))
#endif
OverworldQueryCodeAddon_Rebind(
    OverworldQueryCodeAddonState *state,const OverworldQueryCodeAddonOwner *owner,
    const OverworldQueryCodeAddonOps *ops,void *queryOwner)
{
    if(!state || !Addon_Owner(owner) || !Addon_Ops(ops) || !state->blob || !state->entry
        || (state->phase!=ADDON_READY && state->phase!=ADDON_REBINDING)
        || !Addon_Owner(&state->owner)
        || state->owner.fieldIdentity!=owner->fieldIdentity) return OVERWORLD_QUERY_ADDON_INVALID;
    if(state->owner.fieldEpoch!=owner->fieldEpoch) {
        u16 nextEpoch=state->owner.fieldEpoch+1;
        u16 nextMap=state->owner.mapGeneration+1;
        if(owner->fieldEpoch!=(nextEpoch ? nextEpoch : 1)
            || owner->mapGeneration!=(nextMap ? nextMap : 1))
            return OVERWORLD_QUERY_ADDON_INVALID;
    }
    if(state->phase==ADDON_READY && Addon_SameOwner(&state->owner,owner))
        return OVERWORLD_QUERY_ADDON_OK;
    state->phase=ADDON_REBINDING;
    if(!ops->drain(queryOwner)) return OVERWORLD_QUERY_ADDON_DRAIN_PENDING;
    state->owner=*owner;
    state->phase=ADDON_READY;
    return OVERWORLD_QUERY_ADDON_OK;
}
OverworldQueryCodeAddonStatus OverworldQueryCodeAddon_Unload(
    OverworldQueryCodeAddonState *state,const OverworldQueryCodeAddonOps *ops,void *queryOwner)
{
    void *blob;
    if(!state || !Addon_Ops(ops)) return OVERWORLD_QUERY_ADDON_INVALID;
    if(!state->blob) return state->entry || state->phase!=ADDON_EMPTY
        ? OVERWORLD_QUERY_ADDON_INVALID : OVERWORLD_QUERY_ADDON_OK;
    state->phase=ADDON_DRAINING;
    if(!ops->drain(queryOwner)) return OVERWORLD_QUERY_ADDON_DRAIN_PENDING;
    blob=state->blob;
    *state=(OverworldQueryCodeAddonState){0};
    ops->freeBlob(blob);
    return OVERWORLD_QUERY_ADDON_OK;
}
