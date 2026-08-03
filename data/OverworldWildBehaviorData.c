#include "../include/overworld_wild_behavior_data.h"

/* The generator emits explicit little-endian wire bytes.  No host compiler
 * layout, enum width, or packed-member load participates in serialization. */
const u8 gOverworldWildBehaviorDataBlob[]
    __attribute__((aligned(4), used)) = {
#include "OverworldWildBehaviorDataV40.generated.inc"
};

typedef char OverworldWildBehaviorDataMustHaveExactGeneratedSize[
    sizeof(gOverworldWildBehaviorDataBlob) == OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE ? 1 : -1];
typedef char OverworldWildBehaviorDataMustFitAuthoredMemberCap[
    sizeof(gOverworldWildBehaviorDataBlob) <= OVERWORLD_WILD_BEHAVIOR_DATA_MAX_SIZE ? 1 : -1];
