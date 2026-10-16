#ifndef OVERWORLD_PREPARED_MOVEMENT_H
#define OVERWORLD_PREPARED_MOVEMENT_H
#include "overworld_pickup_route_wild.h"

#define OVERWORLD_PREPARED_MOVEMENT_VERSION 1
#define OVERWORLD_PREPARED_MOVEMENT_MAX_READS 8
#define OVERWORLD_PREPARED_MOVEMENT_TELEPORT 4
/* The borrowed stock height service includes native mesh/platform work.
 * It owns the whole conservative eight-read ledger. Collision and the
 * conditional stock behavior read each have separate saved phases. */
#define OVERWORLD_PREPARED_MOVEMENT_WALK_HEIGHT_READS 8

/* The existing classifier already owns playable/loaded endpoint terrain,
 * canonical support, occupancy, reservations, diagonal side guards and exact
 * policy/binding admission. This leaf adds only native Walk/ledge direction
 * and terrain rules, or Teleport segment admission. It never creates an
 * object, writes pose, chooses a candidate, resolves a profile, or starts Hop.
 * All values and callback owners stay frozen through the final STEP. */
typedef struct OverworldPreparedMovementInput {
    u16 version, size;
    /* Walk may omit both profile/lane: its owner already chose the
     * authored heading. Partial pairs are invalid. Ledge and Teleport
     * retain both pointers; Ledge reads the Owner jump level. */
    const struct OverworldWildBehaviorProfile *profile;
    const struct OverworldWildBehaviorProfileData *lane;
    FieldSystem *field;
    const OverworldPickupRouteWildOps *ops;
    OverworldPickupRoutePosition from, to;
    OverworldPickupRouteNativeTile source, target;
    u32 objectFlags2;
    s16 anchorX, anchorY, rangeX, rangeY;
    BOOL (*blockedTerrain)(FieldSystem *, int, int);
    struct LocalMapObject *collisionIgnoredObject;
    u8 kind, directions, allowObjectOfInterestDestination, reserved;
} OverworldPreparedMovementInput;

typedef enum OverworldPreparedMovementPhase {
    OVERWORLD_PREPARED_MOVEMENT_UNINITIALIZED = 0,
    OVERWORLD_PREPARED_MOVEMENT_WALK_HEIGHT,
    OVERWORLD_PREPARED_MOVEMENT_WALK_TERRAIN,
    OVERWORLD_PREPARED_MOVEMENT_WALK_BEHAVIOR,
    OVERWORLD_PREPARED_MOVEMENT_SOURCE_DIRECTION,
    OVERWORLD_PREPARED_MOVEMENT_TARGET_DIRECTION,
    OVERWORLD_PREPARED_MOVEMENT_LEDGE_BEHAVIOR,
    OVERWORLD_PREPARED_MOVEMENT_LEDGE_OCCUPANCY,
    OVERWORLD_PREPARED_MOVEMENT_LEDGE_LANDING,
    OVERWORLD_PREPARED_MOVEMENT_DONE,
} OverworldPreparedMovementPhase;
/* Caller owns input. readBudget is the remaining common physical ledger.
 * readsUsed is a conservative charge: native height costs8 tokens; raw
 * collision and conditional behavior each cost1. Pure predicates cost0.
 * STEP with too few tokens preserves phase and returns nonterminal DEFERRED.
 * Loaded-world failure is terminal DEFERRED; only a new BEGIN may retry it. */
typedef struct OverworldPreparedMovementCursor {
    u16 version, size;
    const OverworldPreparedMovementInput *input;
    u8 phase, decision, readBudget, readsUsed, direction, heightType, reserved[2];
} OverworldPreparedMovementCursor;
/* Pure native ledge predicate, shared by full admission and Entry
 * negative-only midpoint checks. Unknown behavior is handled by the caller. */
static inline u8 OverworldPreparedMovement_LedgeDirectionLegal(u8 jumpLevel,u8 direction,u8 behavior)
{
    int ledgeIndex=behavior-56;
    return (u32)ledgeIndex<=3 && jumpLevel!=0 && direction<4
        && (ledgeIndex^(direction^(2|(direction>>1))))<=(jumpLevel>=2);
}
OverworldPickupRouteEdgeResult OverworldPreparedMovement_Begin(
    OverworldPreparedMovementCursor *);
OverworldPickupRouteEdgeResult OverworldPreparedMovement_Step(
    OverworldPreparedMovementCursor *);
/* Real START and ordinary Cargo share the exact reducer to terminal. Entry
 * uses BEGIN/STEP under its saved eight-read memo and immutable world key. */
OverworldPickupRouteEdgeResult OverworldPreparedMovement_Run(
    const OverworldPreparedMovementInput *);
#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char PreparedMovementInputMustRemain84[
    sizeof(OverworldPreparedMovementInput)==84?1:-1];
typedef char PreparedMovementCursorMustRemain16[
    sizeof(OverworldPreparedMovementCursor)==16?1:-1];
#endif
#endif
