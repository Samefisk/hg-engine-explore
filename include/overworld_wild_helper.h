#ifndef OVERWORLD_WILD_HELPER_H
#define OVERWORLD_WILD_HELPER_H

#include "overworld_wild_behavior_data.h"
#include "overworld_wild_spawns_internal.h"
#include "types.h"

#define OVERWORLD_WILD_HELPER_OVERLAY_ENTRY_ADDR 0x023C2000
#define OVERWORLD_WILD_HELPER_MAGIC 0x4F574831
#define OVERWORLD_WILD_HELPER_VERSION 1

typedef struct OverworldWildHelperOverlayEntry OverworldWildHelperOverlayEntry;

typedef BOOL (*OverworldWildHelperPickTargetFunc)(
    const OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const OverworldWildBehaviorProfile *profile,
    int slot,
    int currentX,
    int currentY,
    int *targetX,
    int *targetY);

typedef BOOL (*OverworldWildHelperPickTargetTowardFunc)(
    const OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const OverworldWildBehaviorProfile *profile,
    int slot,
    int currentX,
    int currentY,
    int desiredX,
    int desiredY,
    int *targetX,
    int *targetY);

struct OverworldWildHelperOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldWildHelperPickTargetFunc tryPickHeadbuttTreeHopTarget;
    OverworldWildHelperPickTargetFunc tryPickHeadbuttTreeReturnTarget;
    OverworldWildHelperPickTargetTowardFunc tryPickHeadbuttTreeHopTargetToward;
    OverworldWildHelperPickTargetFunc tryPickCanopyHopperTreeTopHopTarget;
};

#define OVERWORLD_WILD_HELPER_OVERLAY_ENTRY \
    ((const OverworldWildHelperOverlayEntry *)OVERWORLD_WILD_HELPER_OVERLAY_ENTRY_ADDR)

#endif // OVERWORLD_WILD_HELPER_H
