#ifndef OVERWORLD_APPEARANCE_POLICY_H
#define OVERWORLD_APPEARANCE_POLICY_H

#include "overworld_behavior_condition_runtime.h"

/* Inputs are read by the field update, never by a draw callback. Strength is
 * a sixteenth of the original-to-red palette blend, or zero at full HP.
 * Actor frames drive one triangle from fully off to the injury-based peak:
 * 1 + ceil(5 * missing HP / max HP). Periods are 128 frames for peaks 2/3,
 * 64 for 4/5, and 32 for 6. The valley keeps normal colors for half
 * the cycle. Strength rounds down; no separate pulse clock. */
u8 OverworldAppearancePolicy_DamageStrength(u16 hp, u16 maxHp, u32 frame);

/* This is a view of the prepared conditions and their existing clocks. Only
 * conditions that can contribute a profile for the current actor role count.
 * It owns no recovery timer and does not alter condition or movement state. */
BOOL OverworldAppearancePolicy_ShouldRestTint(
    const OverworldBehaviorConditionPreparedActor *prepared,
    const OverworldWildBehaviorDataBlob *blob,
    u32 enabledApplicationMask,
    u32 frame,
    u8 actorRole);

#endif
