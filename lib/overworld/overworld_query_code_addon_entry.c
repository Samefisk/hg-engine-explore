#include "../../include/overworld_query_code_addon.h"
#include "../../include/overworld_hop_clearance_native.h"
#include "../../include/overworld_cargo_read_wild.h"
#include "../../include/overworld_throw_away_wild.h"
#include "../../include/overworld_throw_held_wild.h"
#include "../../include/overworld_contact_geometry.h"
#include "../../include/overworld_throw_observation_native.h"
#include "../../include/overworld_behavior_condition_adapter.h"
#include "../../include/overworld_return_move_wild.h"
#include "../../include/overworld_condition_moving_notice_native.h"
extern void OverworldPlayerDamageCondition_Read(OverworldWildBehaviorConditionRuntime *, OverworldWildSpawnState *, FieldSystem *, u8, const OverworldWildBehaviorDataBlob *);

extern void OverworldPlayerDamageCondition_Publish(const OverworldWildSpawnState *, u8, BOOL (*)(const OverworldWildSpawnState *, u8));

const OverworldQueryCodeAddonEntry gOverworldQueryCodeAddonEntry
    __attribute__((used, section(".query_addon_entry"))) = {
    OVERWORLD_QUERY_CODE_ADDON_MAGIC, OVERWORLD_QUERY_CODE_ADDON_VERSION,
    OVERWORLD_QUERY_CODE_ADDON_ENTRY_BYTES,
    sizeof(OverworldTargetBindingsState), sizeof(OverworldPickupRouteState),
    sizeof(OverworldPickupRouteWorkspace), sizeof(OverworldPickupRouteResult),
    sizeof(OverworldPickupRouteNativeContext), OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION,
    OverworldTargetBindings_Init, OverworldTargetBindings_CaptureEntry,
    OverworldTargetBindings_Resolve, OverworldTargetBindings_Clear,
    OverworldTargetBindings_ClearAll, OverworldPickupRoute_Begin,
    OverworldPickupRoute_Resume, OverworldPickupRouteNative_Classify,
    OverworldPickupRouteNative_PickupGoal,
    OverworldPickupRouteNative_Landing,
    OverworldBehaviorCondition_PrepareActor, OverworldBehaviorCondition_EvaluatePrepared,
    OverworldBehaviorResolver_QueryCall, OverworldBehaviorCondition_NotifyWorldEffect,
    OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION, sizeof(OverworldBehaviorConditionWorldView),
    sizeof(OverworldBehaviorConditionPreparedActor), sizeof(OverworldBehaviorConditionResult),
    OverworldCargoQuery_Init, OverworldCargoQuery_Clear, OverworldCargoQuery_Tick,
    OverworldPickupRouteWild_AtomicPickup,
    OVERWORLD_CARGO_QUERY_VERSION, sizeof(OverworldCargoQueryState),
    sizeof(OverworldCargoQueryInput), sizeof(OverworldCargoQueryResult),
    sizeof(OverworldCargoQueryStorage), 0,
    OverworldCargoQueryWild_Tick,
    OverworldPickupLandingWild_Classify,
    OverworldCargoReadWild_Route, OverworldCargoReadWild_Observe,
    OverworldCargoReadWild_Reach, OverworldCargoReadWild_ActorState,
    OverworldCargoReadWild_Options,
    OverworldCargoReadWild_Target,
    OverworldThrowAwayWild_Read,
    OverworldPlayerDamageCondition_Read,
    OverworldConditionNative_Run,
    OverworldThrowObservationQuery_Observe,
    OverworldThrowHeldWild_Run,
    OverworldPlayerDamageCondition_Publish,
    OverworldContactGeometry_Intersects,
    OverworldReturnMoveWild_Request,
    OverworldReturnMoveWild_IsCurrent,
    OverworldReturnMoveWild_TryStart,
    OverworldReturnMoveWild_Finish,
    OverworldReturnMoveWild_CombatWork,
    OverworldHopClearance_Run,
};
