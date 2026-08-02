#include "../include/overworld_wild_behavior_data.h"

/* Transitional runtime adapter.  The authoritative v40 graph remains member
 * 17; this independently frozen projection is authenticated only after v40. */
const u8 gOverworldWildBehaviorProjectionData[]
    __attribute__((aligned(4), used)) = {
#include "OverworldWildBehaviorProjectionV40.generated.inc"
};

typedef char OverworldWildBehaviorProjectionDataMustHaveExactSize[
    sizeof(gOverworldWildBehaviorProjectionData) == OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_SIZE ? 1 : -1];
