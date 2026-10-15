#ifndef OVERWORLD_ACTOR_HOP_CLEARANCE_H
#define OVERWORLD_ACTOR_HOP_CLEARANCE_H

#include "overworld_actor_system_internal.h"
#include "../src/pokemon_move_history_task6_overlay/overworld_actor_hop_geometry.h"

#define OVERWORLD_ACTOR_HOP_CLEARANCE_VERSION 1
#define OVERWORLD_ACTOR_HOP_CLEARANCE_MAX_READS 8
/* Native height owns an entire update, including its loaded mesh/platform
 * callbacks. Reserve the worst-case physical ledger even for a fast catalog
 * or native-flags path. This bound does not prove guest CPU pacing. */
#define OVERWORLD_ACTOR_HOP_CLEARANCE_HEIGHT_READS 8

typedef enum OverworldActorHopClearancePhase {
    OVERWORLD_ACTOR_HOP_CLEARANCE_UNINITIALIZED = 0,
    OVERWORLD_ACTOR_HOP_CLEARANCE_NEXT,
    OVERWORLD_ACTOR_HOP_CLEARANCE_PLAYABLE,
    OVERWORLD_ACTOR_HOP_CLEARANCE_BEHAVIOR,
    OVERWORLD_ACTOR_HOP_CLEARANCE_SURFACE,
    OVERWORLD_ACTOR_HOP_CLEARANCE_HEIGHT,
    OVERWORLD_ACTOR_HOP_CLEARANCE_REDUCE,
    OVERWORLD_ACTOR_HOP_CLEARANCE_DONE,
} OverworldActorHopClearancePhase;

/* Caller owns input and its frozen profile/world through the last STEP. The
 * original48-byte TRAJECTORY/FLAT input remains unchanged. Prepared callers
 * supply real spawn flags and fallback explicitly, without a fake MapObject.
 * Both optional callbacks are present for Entry, or both NULL for stock Hop.
 * BEGIN does no physical reads. STEP consumes at most readBudget<=8, reports
 * readsUsed, and preserves the next phase. A BUSY result is a budget yield iff
 * phase!=DONE; terminal BUSY needs a world change and a new BEGIN. The route
 * owner invalidates this cursor when its Field/map/policy/world key changes. */
typedef struct OverworldActorHopClearanceCursor {
    u16 version;
    u16 size;
    const OverworldActorHopPlanCall *input;
    OverworldActorHopGeometry geometry;
    OverworldWildSurfaceHit hit;
    s32 obstacleBaseY;
    u32 trajectory;
    u32 objectFlags;
    s32 fallbackBaseY;
    BOOL (*playable)(struct FieldSystem *, int, int);
    u8 (*behavior)(struct FieldSystem *, int, int);
    u16 totalFrames;
    u8 phase;
    u8 decision;
    u8 readBudget;
    u8 readsUsed;
    u8 hasSurface;
    u8 reserved;
} OverworldActorHopClearanceCursor;

#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char OverworldActorHopClearanceCursorSizeMustRemain92[
    sizeof(OverworldActorHopClearanceCursor) == 92 ? 1 : -1];
#endif

#endif
