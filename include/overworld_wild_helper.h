#ifndef OVERWORLD_WILD_HELPER_H
#define OVERWORLD_WILD_HELPER_H

#include "types.h"

#define OVERWORLD_WILD_HELPER_OVERLAY_ENTRY_ADDR 0x023C4000
#define OVERWORLD_WILD_HELPER_OVERLAY_MAGIC 0x4F574831
#define OVERWORLD_WILD_HELPER_OVERLAY_VERSION 1

#define OW_WILD_HELPER_DIRECTION_NONE 0xFF
#define OW_WILD_HELPER_DIRECTION_UP 0
#define OW_WILD_HELPER_DIRECTION_DOWN 1
#define OW_WILD_HELPER_DIRECTION_LEFT 2
#define OW_WILD_HELPER_DIRECTION_RIGHT 3

#define OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS 8
#define OW_WILD_HELPER_HOP_PLAN_MAX_HOPS 5
#define OW_WILD_HELPER_HOP_PLAN_NODE_COUNT 64

#define OW_WILD_HELPER_HOP_RESULT_FLAG_DIRECT 0x01
#define OW_WILD_HELPER_HOP_RESULT_FLAG_PLANNED 0x02
#define OW_WILD_HELPER_HOP_RESULT_FLAG_FALLBACK 0x04

typedef struct OverworldWildHelperHopConfig {
    int objectX;
    int objectY;
    int targetX;
    int targetY;
    u8 minDistance;
    u8 maxDistance;
    u8 allowNonCardinal;
    u8 stopOneHopAway;
    u8 directionCount;
    u8 directions[OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS];
} OverworldWildHelperHopConfig;

typedef struct OverworldWildHelperHopResult {
    int landingX;
    int landingY;
    int finalTargetX;
    int finalTargetY;
    u8 direction;
    u8 distance;
    u8 flags;
    u8 reserved;
} OverworldWildHelperHopResult;

typedef BOOL (*OverworldWildHelperHopTileValidator)(
    int landingX,
    int landingY,
    int targetX,
    int targetY,
    void *context);

typedef BOOL (*OverworldWildHelperPickHopFunc)(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    OverworldWildHelperHopResult *result);

typedef struct OverworldWildHelperOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldWildHelperPickHopFunc pickRandomBehaviorHop;
    OverworldWildHelperPickHopFunc planBehaviorHopStep;
} OverworldWildHelperOverlayEntry;

#define OVERWORLD_WILD_HELPER_OVERLAY_ENTRY \
    ((const OverworldWildHelperOverlayEntry *)OVERWORLD_WILD_HELPER_OVERLAY_ENTRY_ADDR)

#endif // OVERWORLD_WILD_HELPER_H
