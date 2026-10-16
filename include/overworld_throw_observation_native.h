#ifndef OVERWORLD_THROW_OBSERVATION_NATIVE_H
#define OVERWORLD_THROW_OBSERVATION_NATIVE_H

#include "player_health_throw_observation.h"

/* Two private Thumb entries in the resident Selector tail. The PTHO service
 * remains at its original address and retains its 32-byte version-2 ABI. */
#define OVERWORLD_THROW_OBSERVATION_OBSERVE_ADDR 0x023C2BA0
#define OVERWORLD_THROW_OBSERVATION_BINDING_POSITION_ADDR 0x023C2DA0

typedef u32 (*OverworldThrowObservationObserveFunc)(
    OverworldWildSpawnState *, int, const OverworldWildBehaviorProfile *,
    const OverworldWildBehaviorDataBlob *,
    const OverworldWildBehaviorConditionRuntime *,
    PlayerHealthThrowIsCurrentSpawnFunc, PlayerHealthThrowQueryTargetFunc);
typedef BOOL (*OverworldThrowObservationBindingPositionFunc)(
    OverworldWildSpawnState *, u8, u8, OverworldTargetBindingPosition *);

u32 OverworldThrowObservation_Observe(
    OverworldWildSpawnState *state, int slot,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorDataBlob *blob,
    const OverworldWildBehaviorConditionRuntime *conditions,
    PlayerHealthThrowIsCurrentSpawnFunc isCurrentSpawn,
    PlayerHealthThrowQueryTargetFunc queryTarget);
u32 OverworldThrowObservationQuery_Observe(OverworldWildSpawnState *, int,
    const OverworldWildBehaviorProfile *, const OverworldWildBehaviorDataBlob *,
    const OverworldWildBehaviorConditionRuntime *, PlayerHealthThrowIsCurrentSpawnFunc,
    PlayerHealthThrowQueryTargetFunc, OverworldThrowObservationBindingPositionFunc);
BOOL OverworldThrowObservation_BindingPosition(
    OverworldWildSpawnState *state, u8 slot, u8 name,
    OverworldTargetBindingPosition *position);

#define OVERWORLD_THROW_OBSERVATION_OBSERVE_ENTRY \
    ((OverworldThrowObservationObserveFunc)(OVERWORLD_THROW_OBSERVATION_OBSERVE_ADDR | 1u))
#define OVERWORLD_THROW_OBSERVATION_BINDING_POSITION_ENTRY \
    ((OverworldThrowObservationBindingPositionFunc)(OVERWORLD_THROW_OBSERVATION_BINDING_POSITION_ADDR | 1u))

#endif /* OVERWORLD_THROW_OBSERVATION_NATIVE_H */
