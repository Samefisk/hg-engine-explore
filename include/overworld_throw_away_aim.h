#ifndef OVERWORLD_THROW_AWAY_AIM_H
#define OVERWORLD_THROW_AWAY_AIM_H

#include "overworld_motion_model.h"

/* Only aim selection. The caller authenticates the carrier, Cargo and Player,
 * and supplies the existing native landing classifier and height resolver.
 * This helper neither moves nor owns an actor. */
typedef OverworldMotionDecision (*OverworldThrowAwayLanding)(
    void *world, int x, int z, s32 *baseY);
typedef struct OverworldThrowAwayAimCall {
    int originX, originZ, playerX, playerZ;
    u8 distance;
    void *world;
    OverworldThrowAwayLanding landing;
} OverworldThrowAwayAimCall;
typedef struct OverworldThrowAwayAim {
    int x, z;
    s32 baseY;
    u8 direction, distance;
} OverworldThrowAwayAim;

/* Exact authored Chebyshev radius (1..8), never a shorter fallback. First
 * project the Player-to-carrier vector outward to that radius and round the
 * shorter axis to its nearest tile. A cardinal result uses the old cardinal
 * order instead: dominant outward axis (X wins ties), other outward axis,
 * then their opposites. At coincident Player/carrier tiles the order is W,N,E,S.
 * A new noncardinal projection is followed by those same four fallbacks:
 * at most five native landing queries, or four for cardinal-only candidates.
 * Each queried endpoint must lie in map bounds and increase its Chebyshev
 * distance from current Player. Unknown/busy results stop selection; only
 * blocked/terrain/occupancy/reservation failures permit the next candidate.
 * Direction is cardinal presentation only; the full X/Z endpoint owns aim.
 * No output is written on failure. Validate rechecks the saved endpoint's
 * radius, current Player separation, native landing and exact support height;
 * it never selects a replacement endpoint. */
u8 OverworldThrowAwayAim_Select(
    const OverworldThrowAwayAimCall *, OverworldThrowAwayAim *);
u8 OverworldThrowAwayAim_Validate(
    const OverworldThrowAwayAimCall *, const OverworldThrowAwayAim *);

#endif
