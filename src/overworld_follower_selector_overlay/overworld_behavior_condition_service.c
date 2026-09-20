#include "../../include/overworld_behavior_condition_runtime.h"
#include "../../include/overworld_follower_selector.h"

const OverworldBehaviorConditionServiceEntry *
__attribute__((section(".overworld_behavior_condition_service_gate"),
    noinline, optimize("Os"), used))
OverworldBehaviorConditionService_Get(void)
{
    const OverworldBehaviorConditionServiceEntry *service =
        OVERWORLD_BEHAVIOR_CONDITION_SERVICE_ENTRY;

    if (!OverworldFollowerSelector_IsDirectLoaded()) {
        return NULL;
    }
    if (service->version != OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION) {
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
        OverworldBehaviorCondition_PrepareActor,
        OverworldBehaviorCondition_EvaluatePrepared,
        OverworldBehaviorCondition_ValidateResolveRequest,
        0,
    };
