#include "../include/overworld_motion_model.h"
#include "../include/overworld_wild_spawns_internal.h"

extern u16 OverworldWalkPauseVariance_Rand(void);
__asm__(
    ".global OverworldWalkPauseVariance_Rand\n"
    ".thumb_func\n"
    ".set OverworldWalkPauseVariance_Rand, 0x0201FD45\n");

u8 __attribute__((section(".overworld_walk_pause_variance"), noinline, used))
OverworldWildSpawns_ResolveWalkPause(
    const OverworldWildBehaviorProfileData *lane)
{
    u8 variance = OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE(
        lane->chainRepositionAllowCardinal);

    if (variance == 0) {
        return lane->walkPause;
    }
    return OverworldMotion_ApplyWalkPauseVariance(
        lane->walkPause,
        variance,
        (u8)OverworldWalkPauseVariance_Rand());
}
