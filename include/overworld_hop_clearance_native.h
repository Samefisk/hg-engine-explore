#ifndef OVERWORLD_HOP_CLEARANCE_NATIVE_H
#define OVERWORLD_HOP_CLEARANCE_NATIVE_H

#include "overworld_actor_hop_clearance.h"
#include "overworld_wild_runtime.h"

#define OVERWORLD_HOP_CLEARANCE_NATIVE_MAGIC 0x434E484F /* OHNC */
#define OVERWORLD_HOP_CLEARANCE_NATIVE_VERSION 2

/* Jump: a TRAJECTORY Hop whose lane has the Jump ability (the packed
 * hopAllowVerticalObstacles bit) and one exact Hop distance. Its arc keeps
 * the ordinary 16-unit apex and may rise only to the distance cap to clear a
 * crossed native obstacle. Heights are world units above the start ground
 * (16 = one tile), sampled at the crossed cell's centre. A wall needs a
 * centred four-tile Jump; an object clears a centred or short Jump. A ledge
 * cell crossed against its downhill side is a wall unless the lane jumps
 * Both. A blocked cell with no native ground is a cliff face, open to a
 * downhill Jump. */
#define OVERWORLD_JUMP_WALL_HEIGHT 20
#define OVERWORLD_JUMP_OBJECT_HEIGHT 12
#define OVERWORLD_JUMP_ARC_CAP_2 18
#define OVERWORLD_JUMP_ARC_CAP_3 22
#define OVERWORLD_JUMP_ARC_CAP_4 24
#define OVERWORLD_JUMP_ARC_CAP(distance) \
    ((distance) <= 2 ? OVERWORLD_JUMP_ARC_CAP_2 \
        : (distance) == 3 ? OVERWORLD_JUMP_ARC_CAP_3 : OVERWORLD_JUMP_ARC_CAP_4)

/* Jump reach from the current Walk time per tile (nominal, no variance):
 * 1-2 frames jump six tiles, 3 five, 4 four, 5-6 three; slower (7+) or
 * stopped jumps two. One nibble per time 0..6, read from the low end. */
#define OVERWORLD_JUMP_REACH(framesPerTile) \
    (((framesPerTile) < 7 ? 0x3345662u >> ((framesPerTile) << 2) : 2u) & 0xF)

/* Synchronous borrow from current Task6/Field. No pointer to this table is
 * retained by Query or its saved cursor. The sole reducer runs in the current
 * Query image; saved input/profile/geometry remain owned by the Field Memo.
 * current validates the exact currently leased Query entry, Field epoch and
 * map generation before any native callback or saved cursor is used. */
typedef struct OverworldHopClearanceNativeOps {
    u32 magic;
    u16 version, size;
    const void *leaseEntry;
    BOOL (*current)(FieldSystem *, const void *);
    void (*geometryInit)(OverworldActorHopGeometry *, const void *);
    void (*nextCell)(OverworldActorHopGeometry *);
    s32 (*lerp)(s32, s32, u32, u32);
    s32 (*slamArc)(u16, u16, u8);
    u32 (*slamPhaseCheck)(u32, u32, u32, s32);
    OverworldWildRuntimeQuerySurfaceFunc querySurface;
    OverworldWildRuntimeResolveBaseYAtFunc resolveBaseYAt;
    OverworldWildCalculateJumpTrajectoryFunc calculateTrajectory;
    OverworldWildCalculateJumpArcFunc calculateArc;
    /* Existing resident ABI helpers; preserve quotient signedness exactly. */
    u32 (*unsignedDivide)(u32, u32);
    s32 (*signedDivide)(s32, s32);
    /* Jump obstacle reads: stock collision and behavior, Wild occupancy. */
    BOOL (*blocked)(FieldSystem *, int, int);
    u8 (*tileBehavior)(FieldSystem *, int, int);
    BOOL (*occupied)(FieldSystem *, LocalMapObject *, LocalMapObject *,
        int, int, s32, int);
} OverworldHopClearanceNativeOps;

OverworldMotionDecision OverworldHopClearance_Run(
    OverworldActorHopPlanCall *, const OverworldHopClearanceNativeOps *);
#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char OverworldHopClearanceNativeOpsSizeMustRemain72[
    sizeof(OverworldHopClearanceNativeOps) == 72 ? 1 : -1];
#endif
#endif
