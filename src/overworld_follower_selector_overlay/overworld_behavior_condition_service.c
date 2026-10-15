#include "../../include/overworld_behavior_condition_runtime.h"
#include "../../include/overworld_query_code_addon_service.h"
#include "../../include/overworld_follower_selector.h"
#include "../../include/constants/file.h"
#include "../../include/overlay.h"

static BOOL __attribute__((section(".overworld_query_code_addon_field_acquire_current.tail"), noinline))
Service_FieldLoaded(PMiLoadedOverlay *table)
{
    /* Stock Field overlay 1 is in MAIN RAM. Use the same eight SDK records
     * as IsOverlayLoaded, without re-reading its known overlay destination. */
    PMiLoadedOverlay *end = table + MAX_ACTIVE_OVERLAYS;

    do {
        if (table->id == OVERLAY_FIELD && table->active == TRUE) {
            return TRUE;
        }
        table++;
    } while (table < end);
    return FALSE;
}

const OverworldBehaviorConditionServiceEntry *
__attribute__((section(".overworld_behavior_condition_service_gate"),
    noinline, used))
OverworldBehaviorConditionService_Get(void)
{
    const OverworldBehaviorConditionServiceEntry *service =
        OVERWORLD_BEHAVIOR_CONDITION_SERVICE_ENTRY;

    /* The direct-loaded flag can outlive Field overlay 1 during release.
     * Parent Field must remain loaded before any service use. */
    if (!OverworldFollowerSelector_IsDirectLoaded()
        || !Service_FieldLoaded(GetLoadedOverlaysInRegion(0))
        || service->version != OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION) {
        return NULL;
    }
    return service;
}

const OverworldBehaviorConditionServiceEntry
    gOverworldBehaviorConditionServiceEntry
    __attribute__((section(".overworld_behavior_condition_service_entry"), used)) = {
        OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC,
        OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION,
        sizeof(OverworldBehaviorConditionServiceEntry),
        OverworldQueryCodeAddon_ConditionPrepare,
        OverworldQueryCodeAddon_ConditionEvaluate,
        OverworldQueryCodeAddon_ResolverCall,
        OverworldQueryCodeAddon_ConditionNotify,
    };
