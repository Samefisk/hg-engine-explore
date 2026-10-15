#ifndef OVERWORLD_PICKUP_ROUTE_NATIVE_H
#define OVERWORLD_PICKUP_ROUTE_NATIVE_H
#include "overworld_pickup_route.h"

#define OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION 3
#define OVERWORLD_PICKUP_ROUTE_NATIVE_GROUND 0xFFFF
#define OVERWORLD_PICKUP_ROUTE_NATIVE_KIND_SHIFT 14
#define OVERWORLD_PICKUP_ROUTE_NATIVE_TAG(kind, payload) \
    (((u16)(kind) << OVERWORLD_PICKUP_ROUTE_NATIVE_KIND_SHIFT) | ((payload) & 0x3FFF))
typedef enum OverworldPickupRouteNativeKind {
    OVERWORLD_PICKUP_ROUTE_NATIVE_WALK = 0,
    OVERWORLD_PICKUP_ROUTE_NATIVE_HOP,
    OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE,
    OVERWORLD_PICKUP_ROUTE_NATIVE_REPOSITION,
    OVERWORLD_PICKUP_ROUTE_NATIVE_TELEPORT,
} OverworldPickupRouteNativeKind;
/* Private Entry escape, interpreted only with an authenticated extension. */
#define OVERWORLD_PICKUP_ROUTE_NATIVE_ENTRY_TELEPORT 0x2000u
#define OVERWORLD_PICKUP_ROUTE_NATIVE_LANDING_ONLY 0xFF
#define OVERWORLD_PICKUP_ROUTE_NATIVE_CARDINAL 1
#define OVERWORLD_PICKUP_ROUTE_NATIVE_DIAGONAL 2
#define OVERWORLD_PICKUP_ROUTE_NATIVE_STRICT_DIAGONAL 1
#define OVERWORLD_PICKUP_ROUTE_NATIVE_SAME_SURFACE 2
#define OVERWORLD_PICKUP_ROUTE_NATIVE_AVOID_SCRIPTED 4
#define OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION 8
#define OVERWORLD_PICKUP_ROUTE_NATIVE_CHECK_WALK_EDGE 16
#define OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_SCRIPTED 1
#define OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_PLAYER 2
#define OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_OBJECT_OF_INTEREST 4
/* These masks remain caller supplied, from the resolved terrain contract. */
typedef struct OverworldPickupRouteNativePolicy {
    u16 version, size, allowedTerrainMask, playerTerrainMask;
    u8 allowedKinds, directions, hopMinDistance, hopMaxDistance;
    u8 flags, reserved[3];
    const void *resolvedProfile, *resolvedLane;
} OverworldPickupRouteNativePolicy;
typedef struct OverworldPickupRouteNativeTile {
    u16 surfaceId, terrainMask;
    u8 behavior, flags;
    u16 reserved;
} OverworldPickupRouteNativeTile;
typedef struct OverworldPickupRouteNativeWork {
    u16 binding, terrain, support, occupancy, reservations, edgePolicy, hop;
    u16 total;
} OverworldPickupRouteNativeWork;

/* All callbacks are bounded and read-only. LEGAL means a complete read or a
 * passed check. Missing loaded terrain/support is DEFERRED. INVALID rejects
 * changed identities/revisions or a malformed callback receipt. A capacity
 * failure is RESOURCE_LIMIT, never BLOCKED. No callback starts motion, changes
 * a MapObject, reserves Cargo, resolves a profile, or loads an archive.
 *
 * terrain receives the wanted destination mask, or 0xFFFF for a complete
 * SOURCE read. It may omit the native LAND collision query when LAND is not
 * wanted. For a nonzero surface-only mask, the current immutable Wild
 * package may prove absence before native behavior/support reads. A matching
 * catalog candidate still requires loaded behavior and canonical support.
 * Catalog precedence, surface identity and scripted/player flags remain
 * canonical. Missing/unproven catalog data cannot prove absence.
 * support uses the supplied
 * origin.baseY and native subject flags, never
 * the live object's pose; absolute support and relative/native canopy remain
 * distinct. A failed support query must not substitute the old base height.
 *
 * occupancy skips the validated subject. includeObjectOfInterest is Boolean:
 * zero admits only the published, identity-checked target on its current tile;
 * one keeps that target occupied. Player follows the normal height policy
 * unless it is that target. Unrelated actors and Cargo stay occupied. reservations
 * checks the Actor owner's current target/surface/epoch ledger without REQUEST.
 * edgePolicy applies origin-aware native direction/height/ledge/Reposition
 * constraints to the supplied source and destination behaviors. It must not
 * read the live object's cached source behavior. kind LANDING_ONLY checks only
 * the native Reposition grid and must accept sourceTile==NULL. binding receives
 * NULL Query only for the explicit bare Landing call; it validates the field
 * and native object without requiring Cargo. occupancy receives NULL subject
 * only for unbound placement. hop delegates to the shared
 * Hop planner (including flat Reposition), with explicit endpoints/heights and
 * resolved vertical-obstacle rules. It returns no movement identity.
 * pickupReach tests a hypothetical standing pose against the current Cargo
 * pose and physical height/reach rules. Atomic pickup rechecks these facts at
 * the actual accepted-motion boundary; a route/goal receipt is not ownership.
 */
typedef struct OverworldPickupRouteNativeSeams {
    OverworldPickupRouteEdgeResult (*binding)(void *, const OverworldPickupRouteQuery *);
    OverworldPickupRouteEdgeResult (*terrain)(void *, s16, s16, u16 wantedMask,
        OverworldPickupRouteNativeTile *);
    OverworldPickupRouteEdgeResult (*support)(void *, const OverworldPickupRoutePosition *,
        s16, s16, const OverworldPickupRouteNativeTile *, s32 *);
    OverworldPickupRouteEdgeResult (*occupancy)(void *, const OverworldActorHandle *,
        const OverworldPickupRoutePosition *, u8 includeObjectOfInterest);
    OverworldPickupRouteEdgeResult (*reservations)(void *, const OverworldActorHandle *,
        const OverworldPickupRoutePosition *);
    OverworldPickupRouteEdgeResult (*edgePolicy)(void *, const OverworldPickupRouteNativePolicy *,
        u8 kind, const OverworldPickupRoutePosition *, const OverworldPickupRouteNativeTile *,
        const OverworldPickupRoutePosition *, const OverworldPickupRouteNativeTile *);
    OverworldPickupRouteEdgeResult (*hop)(void *, const OverworldPickupRouteNativePolicy *,
        u8 kind, u16 distance, const OverworldPickupRoutePosition *, const OverworldPickupRoutePosition *);
    OverworldPickupRouteEdgeResult (*pickupReach)(void *, const OverworldPickupRouteNativePolicy *,
        const OverworldPickupRoutePosition *, const OverworldPickupRoutePosition *);
} OverworldPickupRouteNativeSeams;
/* One small field-owned scheduler context borrows the active shared query's
 * current binding/policy. Do not switch its owner during Resume. There is no
 * second search, allocation, motion owner, or per-actor workspace here.
 * lastWork counts bounded seam calls, not guest CPU cycles. Internal native
 * Hop clearance work is additionally bounded by its authored stride.
 * ARM: Policy24, Tile8, Work16, Seams32, Context36. */
typedef struct OverworldPickupRouteNativeContext {
    u16 version, size;
    const OverworldPickupRouteQuery *query;
    const OverworldPickupRouteNativePolicy *policy;
    const OverworldPickupRouteNativeSeams *seams;
    void *world;
    OverworldPickupRouteNativeWork lastWork;
} OverworldPickupRouteNativeContext;

/* Addon-private admission only: run the exact classifier validation and
 * current binding before an Entry negative-only physical read. No route or
 * motion is accepted by this function; service/layout ABI stays unchanged. */
OverworldPickupRouteEdgeResult OverworldPickupRouteNative_ValidateBinding(
    OverworldPickupRouteNativeContext *);

/* A synchronous real START/placement check. NULL subject means unbound
 * placement, not a fabricated handle. This call requires no Cargo or Query.
 * The caller supplies its actual source support and a field-scoped world.
 * seams==NULL selects the typed Wild world's addon-local table.
 * CHECK_WALK_EDGE makes real Walk START use the same origin-aware native
 * edge policy; cardinal and diagonal Walk both set it. Hop/placement do not.
 * Native seams must not retain this stack call. ARM size44. */
typedef struct OverworldPickupRouteNativeLandingCall {
    u16 version, size;
    const OverworldPickupRouteNativePolicy *policy;
    const OverworldPickupRouteNativeSeams *seams;
    void *world;
    const OverworldActorHandle *subject;
    OverworldPickupRoutePosition origin;
    s16 targetX, targetY;
    OverworldPickupRoutePosition *destination;
    OverworldPickupRouteNativeWork *work;
} OverworldPickupRouteNativeLandingCall;
OverworldPickupRouteEdgeResult OverworldPickupRouteNative_Landing(
    const OverworldPickupRouteNativeLandingCall *);

/* Matches Query.legalEdge. Destination is published only on LEGAL.
 * No Cargo distance limit; bounds are the caller's active loaded scope.
 * Walk diagonal guards validate both side landings without player permission.
 * Reservations apply to the endpoint, matching the native owner's START.
 * Maximum calls: diagonal Walk17, cardinal Walk9, Hop/Ledge/Reposition10.
 * PickupGoal7. Native callbacks must retain their own scan/sample budgets. */
OverworldPickupRouteEdgeResult OverworldPickupRouteNative_Classify(void *,
    const OverworldPickupRoutePosition *, const OverworldPickupRouteEdge *, OverworldPickupRoutePosition *);
OverworldPickupRouteEdgeResult OverworldPickupRouteNative_PickupGoal(
    OverworldPickupRouteNativeContext *, s16, s16, OverworldPickupRoutePosition *);

#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char PickupRouteNativeLandingCallMustRemain44[sizeof(OverworldPickupRouteNativeLandingCall)==44?1:-1];
typedef char PickupRouteNativePolicyMustRemain24[sizeof(OverworldPickupRouteNativePolicy)==24?1:-1];
typedef char PickupRouteNativeSeamsMustRemain32[sizeof(OverworldPickupRouteNativeSeams)==32?1:-1];
typedef char PickupRouteNativeContextMustRemain36[sizeof(OverworldPickupRouteNativeContext)==36?1:-1];
#endif
typedef char PickupRouteNativeTileMustRemain8[sizeof(OverworldPickupRouteNativeTile)==8?1:-1];
typedef char PickupRouteNativeWorkMustRemain16[sizeof(OverworldPickupRouteNativeWork)==16?1:-1];
#endif
