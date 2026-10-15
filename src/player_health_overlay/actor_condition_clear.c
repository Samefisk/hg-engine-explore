#include "../../include/overworld_behavior_condition_adapter.h"

/* This is a fixed resident code slot. It owns no player-HP state. */
void __attribute__((section(".actor_condition_clear"), noinline, used))
OverworldBehaviorConditionAdapter_ClearResolution(
    OverworldWildBehaviorConditionRuntime *runtime,
    u8 slot)
{
    runtime->activeApplicationMasks[slot] = 0;
    runtime->timedWinningApplicationMasks[slot] = 0;
    /* The validity bit owns the target cache. Coordinates are ignored while
     * it is clear and are replaced before it is set again. */
    runtime->targetValidMask &= (u16)~(1u << slot);
    runtime->frame.valid = FALSE;
}
