#include "../../include/overworld_behavior_condition_runtime.h"

const OverworldBehaviorConditionServiceEntry
    gOverworldBehaviorConditionServiceEntry
    __attribute__((section(".overworld_behavior_condition_service_entry"), used)) = {
        OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC,
        OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION,
        sizeof(OverworldBehaviorConditionServiceEntry),
        OverworldBehaviorCondition_PrepareActor,
        OverworldBehaviorCondition_EvaluatePrepared,
        OverworldBehaviorCondition_ValidateResolveRequest,
    };
