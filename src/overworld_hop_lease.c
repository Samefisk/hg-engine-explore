#include "../include/overworld_hop_presentation_native.h"
#include "../include/overworld_query_code_addon_service.h"
#include "../include/overworld_actor_system_internal.h"

/* Borrow only while the parent Field is loaded. No heap or owner mutation. */
const OverworldQueryCodeAddonEntry *
__attribute__((noinline, target("arch=armv5te"), section(".overworld_hop_lease")))
OverworldHopPresentation_Acquire(FieldSystem *field)
{
    const OverworldQueryCodeAddonServiceEntry *service =
        (const OverworldQueryCodeAddonServiceEntry *)OVERWORLD_QUERY_CODE_ADDON_SERVICE_ADDR;
    union { OverworldQueryCodeAddonOwner owner; u32 words[2]; } lease;
    typedef u32 HopLeaseWord __attribute__((may_alias));
    if (field == NULL || OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE() == NULL
        || service->magic != OVERWORLD_QUERY_CODE_ADDON_SERVICE_MAGIC
        || *(const HopLeaseWord *)(const void *)&service->version
            != (OVERWORLD_QUERY_CODE_ADDON_SERVICE_VERSION | (sizeof(*service) << 16)) || service->acquire == NULL) return NULL;
    lease.owner.fieldIdentity = (u32)field;
    lease.words[1] = OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext();
    return service->acquire(&lease.owner);
}
