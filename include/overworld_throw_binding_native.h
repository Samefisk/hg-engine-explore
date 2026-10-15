#ifndef OVERWORLD_THROW_BINDING_NATIVE_H
#define OVERWORLD_THROW_BINDING_NATIVE_H

#include "overworld_throw_observation_native.h"
#include "overworld_query_code_addon_service.h"

/* Private current-position refresh. The public Adapter/PTHO tables do not
 * change. NULL buildContext reads positions only and leaves the condition
 * candidate cache invalid for the next real evaluation. */
#define OVERWORLD_CONDITION_FRAME_BUILD_ADDR 0x023B6930
#define OVERWORLD_THROW_BINDING_REFRESH_ADDR 0x02208600

BOOL OverworldBehaviorConditionAdapter_BuildFrame(
    OverworldWildSpawnState *, FieldSystem *,
    OverworldWildBehaviorConditionRuntime *,
    OverworldBehaviorConditionBuildContextFunc,
    OverworldBehaviorConditionIsCurrentSpawnFunc);

const OverworldQueryCodeAddonEntry *OverworldThrowBinding_Refresh(
    OverworldWildSpawnState *, OverworldWildBehaviorConditionRuntime *,
    const OverworldQueryCodeAddonServiceEntry *, u8);

typedef const OverworldQueryCodeAddonEntry *(*OverworldThrowBindingRefreshFunc)(
    OverworldWildSpawnState *, OverworldWildBehaviorConditionRuntime *,
    const OverworldQueryCodeAddonServiceEntry *, u8);

#define OVERWORLD_THROW_BINDING_REFRESH_ENTRY \
    ((OverworldThrowBindingRefreshFunc)(OVERWORLD_THROW_BINDING_REFRESH_ADDR | 1u))

#endif /* OVERWORLD_THROW_BINDING_NATIVE_H */
