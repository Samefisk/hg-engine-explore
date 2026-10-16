#define OVERWORLD_FIELD_CAPSULE_IMPLEMENTATION 1
#include "../../include/overworld_wild_runtime_state_internal.h"

/* Physical code belongs to stock Field overlay 1. Only the current field
 * roles call this; the original runtime/service guards stay in one body. */
void __attribute__((used, noinline, section(".overworld_field_world_effect")))
OverworldWildConditions_NotifyWorldEffect(
    const OverworldWildSpawnState *state,
    const OverworldActorHandle *subject,
    u32 effect)
{
    OverworldWildConditions_NotifyWorldEffectInline(state, subject, effect);
}
