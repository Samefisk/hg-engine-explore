#ifndef OVERWORLD_PICKUP_LANDING_WILD_H
#define OVERWORLD_PICKUP_LANDING_WILD_H

#include "overworld_pickup_route_wild.h"

/* Borrowed only for this real START/placement call. Coordinates remain native
 * int values until the legacy landing call applies its signed-halfword ABI.
 * The loaded Wild owner supplies all native functions and ignored occupancy.
 * behaviorData is its current immutable, build-validated package returned by
 * GetBehaviorDataBlob; it is not an arbitrary catalog or a caller-owned copy. */
typedef struct OverworldPickupRouteWildLandingCall {
    struct OverworldWildSpawnState *state;
    FieldSystem *field;
    const struct OverworldWildBehaviorDataBlob *behaviorData;
    const OverworldPickupRouteWildOps *ops;
    struct LocalMapObject *collisionIgnoredObject;
    int slot;
    u16 allowedTile;
    int x, y, finalTargetX, finalTargetY;
} OverworldPickupRouteWildLandingCall;

#define OVERWORLD_PICKUP_LANDING_WILD_STRICT_DIAGONAL_MARKER 0x8000
/* Outside authored masks; extracted into the private World policy before
 * Native_Landing sees the complete actual terrain/surface permission mask. */
#define OVERWORLD_PICKUP_LANDING_WILD_PERMIT_BOUND_OOI_MARKER 0x4000

enum OverworldMotionDecision OverworldPickupLandingWild_Classify(
    const OverworldPickupRouteWildLandingCall *);

#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char PickupRouteWildLandingCallMustRemain44[
    sizeof(OverworldPickupRouteWildLandingCall) == 44 ? 1 : -1];
#endif
#endif /* OVERWORLD_PICKUP_LANDING_WILD_H */
