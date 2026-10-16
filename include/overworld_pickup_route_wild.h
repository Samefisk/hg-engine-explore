#ifndef OVERWORLD_PICKUP_ROUTE_WILD_H
#define OVERWORLD_PICKUP_ROUTE_WILD_H
#include "overworld_pickup_route_native.h"
#ifdef OVERWORLD_ACTOR_SYSTEM_HOST
typedef int BOOL;
typedef int8_t s8;
typedef struct FieldSystem FieldSystem;
#ifndef OVERWORLD_WILD_BEHAVIOR_DATA_H
typedef struct OverworldWildSurfaceCatalog OverworldWildSurfaceCatalog;
typedef struct OverworldWildSurfaceHit {
    s32 height; u16 surfaceId; u8 surfaceType, nodeId;
} OverworldWildSurfaceHit;
#endif
#else
#include "overworld_wild_behavior_data.h"
#endif

#define OVERWORLD_PICKUP_ROUTE_WILD_VERSION 3
/* resolveBaseYAt is a read-only physical query. Its key is Field, known
 * surface (including absence), XY, originBaseY and only these object flags.
 * Keep the native owner masked to this contract before extending the key. */
#define OVERWORLD_PICKUP_ROUTE_SUPPORT_FLAG_MASK ((1u << 23) | (1u << 29))
/* Private bare-landing policy. It changes occupancy only, never terrain. */
#define OVERWORLD_PICKUP_ROUTE_WILD_PERMIT_BOUND_OOI_OCCUPANCY 1u
struct LocalMapObject;
struct OverworldEntryRoutePhysical;
struct OverworldEntryRouteMemo;
struct OverworldWildSpawnState;
struct OverworldActorSystemState;
struct OverworldActorPolicyView;
struct OverworldActorHopPlanCall;
struct OverworldWildBehaviorDataBlob;
enum OverworldMotionDecision;
/* Borrowed only while Field and Wild are loaded. All targets are supplied by
 * the real Wild owner. The addon has no stock address inventory or imports.
 * actorState must authenticate the compiled resident layout before returning
 * it. pickupReach checks the same authored tile/ground range and height used
 * by route goals. Atomic pickup also checks the current fx32 body, using those
 * same allowances, so a moving Hop's arc cannot bypass height admission. */
typedef BOOL (*OverworldPickupRouteWildDirectionBlock)(u8);
typedef struct OverworldPickupRouteWildOps {
    u16 version, size;
    BOOL (*playable)(FieldSystem *, int, int);
    u8 (*behavior)(FieldSystem *, int, int);
    BOOL (*querySurface)(FieldSystem *, const OverworldWildSurfaceCatalog *, int, int, OverworldWildSurfaceHit *);
    BOOL (*resolveBaseYAt)(FieldSystem *, const OverworldWildSurfaceHit *, s32, u32, int, int, s32 *);
    BOOL (*surf)(u8);
    BOOL (*playerTile)(FieldSystem *, int, int);
    BOOL (*playerFront)(FieldSystem *, int, int);
    BOOL (*land)(FieldSystem *, int, int);
    BOOL (*scripted)(FieldSystem *, int, int);
    BOOL (*currentObject)(FieldSystem *, struct LocalMapObject *);
    BOOL (*occupancy)(FieldSystem *, struct LocalMapObject *, struct LocalMapObject *, int, int, s32, int);
    const struct OverworldActorSystemState *(*actorState)(void);
    BOOL (*inspectPolicy)(u8, struct OverworldActorPolicyView *);
    enum OverworldMotionDecision (*hopPlan)(struct OverworldActorHopPlanCall *);
    BOOL (*walkTerrain)(FieldSystem *, const void *originVector, int, int, s8 *);
    const OverworldPickupRouteWildDirectionBlock *sourceDirectionBlocks;
    const OverworldPickupRouteWildDirectionBlock *targetDirectionBlocks;
    OverworldPickupRouteEdgeResult (*pickupReach)(void *, const OverworldPickupRoutePosition *, const OverworldPickupRoutePosition *);
    /* Stock Walk's existing height leaf, then native collision. Entry saves
     * their boundary; the complete native height callback costs8 tokens. */
    int (*walkHeight)(FieldSystem *, const void *, int, int, u8 *);
    BOOL (*blockedTerrain)(FieldSystem *, int, int);
} OverworldPickupRouteWildOps;
/* Caller owns one borrowed world, not one per Actor. The field scheduler
 * advances revisions when terrain/support, policy, or relevant occupancy
 * changes. binding compares them with the query on every synchronous edge.
 * Native height starts from the supplied origin; subjectObject is never moved.
 * routeRead is set by binding, not by the caller. landingPolicy is private
 * bare-landing occupancy permission and must be zero for route queries.
 * lastDecision retains the legacy landing reason for the real START wrapper. */
typedef struct OverworldPickupRouteWildWorld {
    u16 version, size;
    FieldSystem *field;
    struct OverworldWildSpawnState *state;
    struct LocalMapObject *subjectObject, *heightObject, *collisionIgnoredObject;
    const OverworldWildSurfaceCatalog *catalog;
    const OverworldPickupRouteWildOps *ops;
    u32 scopeRevision, movementPolicyRevision, dynamicRevision;
    const OverworldPickupRouteQuery *query;
    s16 finalTargetX, finalTargetY;
    u8 slot, routeRead, hitValid, landingPolicy;
    s16 hitX, hitY;
    OverworldWildSurfaceHit hit;
    /* Landing stores its rejection here. Atomic pickup stores the exact
     * Cargo receipt to cancel only after every read-only admission passes. */
    __extension__ union { int lastDecision; u32 pickupMotionIdentity; };
    /* Optional proof of the current immutable Wild package. When provided,
     * catalog must equal its surfaceModels and its exact compiled header must
     * match. Only that package may prove surface absence before native reads.
     * Raw/custom worlds leave this NULL and retain the complete read path. */
    const struct OverworldWildBehaviorDataBlob *behaviorData;
    const struct OverworldEntryRoutePhysical *preparedPhysical;
    struct OverworldEntryRouteMemo *entryMemo;
} OverworldPickupRouteWildWorld;
/* Returns an addon-local immutable table only for the typed current world.
 * Context.seams may be NULL on its first call. Begin installs this borrowed
 * pointer; the loader drain MUST clear the Context before addon unload. */
const OverworldPickupRouteNativeSeams *OverworldPickupRouteWild_GetSeams(void *);
/* Pure admission rechecks exact claim/full identities, carrier idle receipt,
 * Cargo's idle or normal accepted Walk/Hop, strict support and actual fx32
 * reach/height (including its Hop arc). LEGAL publishes a Cargo receipt in
 * world.pickupMotionIdentity; the caller must cancel that exact motion before
 * writing HELD. Deferred/failed admission never changes an actor or claim. */
OverworldPickupRouteEdgeResult OverworldPickupRouteWild_AtomicPickup(
    void *, const OverworldActorHandle *, const OverworldActorHandle *);

#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char PickupRouteWildOpsMustRemain84[sizeof(OverworldPickupRouteWildOps)==84?1:-1];
typedef char PickupRouteWildWorldMustRemain84[sizeof(OverworldPickupRouteWildWorld)==84?1:-1];
#endif
#endif
