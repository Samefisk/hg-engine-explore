#ifndef OVERWORLD_BEHAVIOR_PACKED_OPTIONS_H
#define OVERWORLD_BEHAVIOR_PACKED_OPTIONS_H
#include "overworld_wild_behavior_data.h"
/* One private profile-composition implementation; its physical ARM host
 * is resident ITCM and has no Player HP state dependency. */
static inline __attribute__((always_inline)) void
OverworldBehaviorPackedOptions_ApplyInline(
    OverworldWildBehaviorProfileData *profile,
    const OverworldWildBehaviorOverrideProfile *overrideProfile, u32 knockbackMask)
{
    u32 mask2 = overrideProfile->mask2;
    u32 mask3 = overrideProfile->mask3;
    profile->continueWhenArrived ^= (profile->continueWhenArrived
        ^ overrideProfile->profile.continueWhenArrived)
        & (((mask2 >> 13) & 1u) | (((mask2 >> 25) & 1u) * 0x02u)
            | (((mask2 >> 26) & 1u) * 0x3Cu)
            | (((mask2 >> 27) & 1u) * 0xC0u));
    profile->avoidPreviousTile ^= (profile->avoidPreviousTile
        ^ overrideProfile->profile.avoidPreviousTile)
        & (((mask2 >> 14) & 1u) | (((mask2 >> 29) & 1u) * 0xFEu));
    profile->chainRepositionJumpCount ^= (profile->chainRepositionJumpCount
        ^ overrideProfile->profile.chainRepositionJumpCount)
        & ((((mask2 >> 28) & 1u) * 0x30u) | (((mask2 >> 30) & 1u) * 0xC0u));
    profile->onReachAction ^= (profile->onReachAction
        ^ overrideProfile->profile.onReachAction)
        & (((mask2 >> 16) & 1u) | (((mask2 >> 31) & 1u) * 0xC0u));
    /* Each new threshold and its old boolean compose independently. */
    profile->hopAllowVerticalObstacles ^= (profile->hopAllowVerticalObstacles
        ^ overrideProfile->profile.hopAllowVerticalObstacles)
        & ((((mask2 >> 23) & 1u) * 0xFEu) | ((mask3 >> 10) & 1u));
    profile->chainRepositionDust ^= (profile->chainRepositionDust
        ^ overrideProfile->profile.chainRepositionDust)
        & ((((mask2 >> 24) & 1u) * 0xFEu) | ((mask3 >> 16) & 1u));
    profile->knockbackOptions ^= (profile->knockbackOptions
        ^ overrideProfile->profile.knockbackOptions) & knockbackMask;
}
#endif
