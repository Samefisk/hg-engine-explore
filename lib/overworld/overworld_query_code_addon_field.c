#include "../../include/overworld_query_code_addon_field.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/map_events_internal.h"
#include "overworld_query_code_addon_package.h"

extern const OverworldBehaviorConditionServiceEntry gOverworldBehaviorConditionServiceEntry;

static const OverworldQueryCodeAddonServiceEntry *Field_Service(void)
{
    const OverworldBehaviorConditionServiceEntry *public =
        OverworldBehaviorConditionService_Get();
    const OverworldQueryCodeAddonServiceEntry *private = &gOverworldQueryCodeAddonServiceEntry;
    if(public!=&gOverworldBehaviorConditionServiceEntry
        || public->magic!=OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC
        || public->version!=OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION
        || public->size!=sizeof(*public)
        || private->magic!=OVERWORLD_QUERY_CODE_ADDON_SERVICE_MAGIC
        || private->version!=OVERWORLD_QUERY_CODE_ADDON_SERVICE_VERSION
        || private->size!=sizeof(*private) || private->state!=&gOverworldQueryCodeAddonState
        || !private->load || !private->acquire || !private->unload) return NULL;
    return private;
}
const OverworldQueryCodeAddonEntry *
__attribute__((noinline,used,section(".overworld_query_code_addon_field_acquire")))
OverworldQueryCodeAddonField_Acquire(
    FieldSystem *field,u16 epoch,u16 mapGeneration,const OverworldQueryCodeAddonOps *ops,void *query)
{
    const OverworldQueryCodeAddonServiceEntry *service=Field_Service();
    OverworldQueryCodeAddonOwner owner={(u32)(uintptr_t)field,epoch,mapGeneration};
    OverworldQueryCodeAddonStatus status;
    if(!service) return NULL;
    if(service->state->blob) {
        status=OverworldQueryCodeAddon_Rebind(service->state,&owner,ops,query);
    } else {
        status=service->load(&owner,ops,OVERWORLD_QUERY_CODE_ADDON_MEMBER_ID,
            OVERWORLD_QUERY_CODE_ADDON_PACKAGE_BYTES);
    }
    return status==OVERWORLD_QUERY_ADDON_OK ? service->acquire(&owner) : NULL;
}
OverworldQueryCodeAddonStatus
__attribute__((noinline,used,section(".overworld_query_code_addon_field_unload")))
OverworldQueryCodeAddonField_Unload(
    const OverworldQueryCodeAddonOps *ops,void *query)
{
    const OverworldQueryCodeAddonServiceEntry *service=Field_Service();
    return service ? service->unload(ops,query) : OVERWORLD_QUERY_ADDON_INVALID;
}

/* Only entered after the Wild caller's loaded Condition gate. Keep the exact
 * Actor context check before Field_Acquire can drain the previous owner. */
const OverworldQueryCodeAddonEntry *
__attribute__((noinline,used,section(".overworld_query_code_addon_field_acquire_current")))
OverworldQueryCodeAddonField_AcquireCurrent(
    FieldSystem *field,const OverworldActorTransitionCall *transition,
    const OverworldQueryCodeAddonOps *ops,void *query)
{
    u32 context;
    if(transition!=NULL && (field->location==NULL || field->mapObjectMan==NULL
        || ((MapObjectMan *)field->mapObjectMan)->objects==NULL
        || transition->currentMapId!=field->location->mapId
        || transition->nextFieldEpoch==0 || transition->nextMapGeneration==0)) return NULL;
    context=OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext();
    if(transition!=NULL && context!=((u32)transition->nextFieldEpoch
        | ((u32)transition->nextMapGeneration<<16))) return NULL;
    return OverworldQueryCodeAddonField_Acquire(field,
        OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(context),
        OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(context),ops,query);
}
