#ifndef OVERWORLD_HOP_EFFECTS_INTERNAL_H
#define OVERWORLD_HOP_EFFECTS_INTERNAL_H

#include "types.h"

BOOL OverworldActorWalkPolicy_SampleChainChance(u32 chance);
u8 OverworldActorWalkPolicy_SampleHopEffects(u32 codes);

/* Low two bits select Heart; the next two select Cry. Off skips its draw.
 * This pure choice has no motion, presentation or Player Health state. */
static inline u8 __attribute__((always_inline))
OverworldActorWalkPolicy_SampleHopEffectsInline(u32 codes)
{
    u8 flags = 0;
    u8 effect = 1;

    do {
        u8 code = codes & 3u;

        if (code != 0 && OverworldActorWalkPolicy_SampleChainChance(
                25u << (code - 1))) {
            flags |= effect;
        }
        codes >>= 2;
        effect <<= 1;
    } while (effect != 4);
    return flags;
}

#endif
