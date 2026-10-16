#include "../../include/overworld_pickup_landing_wild.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/map_events_internal.h"

/* The same bare Landing setup used by Wild before it acquired an addon-local
 * code home. This function never creates a route query or publishes motion. */
OverworldMotionDecision OverworldPickupLandingWild_Classify(
    const OverworldPickupRouteWildLandingCall *input)
{
    OverworldPickupRouteWildWorld world = {0};
    OverworldPickupRouteNativePolicy policy = {0};
    OverworldPickupRouteNativeLandingCall call = {0};
    OverworldPickupRoutePosition destination;
    OverworldWildSurfaceHit sourceSurface;
    OverworldPickupRouteEdgeResult result;
    LocalMapObject *object = NULL;
    u16 allowedTile;
    if (input == NULL || input->field == NULL)
        return OVERWORLD_MOTION_DECISION_PROFILE;
    if (input->x < 0 || input->y < 0)
        return OVERWORLD_MOTION_DECISION_BLOCKED;
    allowedTile = input->allowedTile;
    if (input->state != NULL && (u32)input->slot < OW_WILD_MAX_SPAWNS
        && input->state->spawns[input->slot].active)
        object = input->state->spawns[input->slot].object;
    world.version = OVERWORLD_PICKUP_ROUTE_WILD_VERSION;
    world.size = sizeof(world);
    world.field = input->field;
    world.state = input->state;
    world.slot = (u8)input->slot;
    world.subjectObject = object;
    world.heightObject = object != NULL ? object
        : input->field->playerAvatar != NULL
            ? input->field->playerAvatar->mapObject : NULL;
    world.collisionIgnoredObject = input->collisionIgnoredObject;
    world.behaviorData = input->behaviorData;
    world.catalog = input->behaviorData != NULL
        ? (const OverworldWildSurfaceCatalog *)input->behaviorData->surfaceModels : NULL;
    world.ops = input->ops;
    world.finalTargetX = input->finalTargetX;
    world.finalTargetY = input->finalTargetY;
    if (allowedTile & OVERWORLD_PICKUP_LANDING_WILD_PERMIT_BOUND_OOI_MARKER)
        world.landingPolicy = OVERWORLD_PICKUP_ROUTE_WILD_PERMIT_BOUND_OOI_OCCUPANCY;
    policy.version = OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;
    policy.size = sizeof(policy);
    policy.allowedTerrainMask = allowedTile
        & ~(OVERWORLD_PICKUP_LANDING_WILD_STRICT_DIAGONAL_MARKER
            | OVERWORLD_PICKUP_LANDING_WILD_PERMIT_BOUND_OOI_MARKER);
    /* Occupancy permission must not make a forbidden physical tile legal.
     * All authored actual terrain/surface bits remain intact. */
    if (world.landingPolicy)
        policy.allowedTerrainMask &= ~OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER;
    policy.playerTerrainMask = OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER;
    if (policy.allowedTerrainMask == 0)
        return OVERWORLD_MOTION_DECISION_TERRAIN;
    if (input->state != NULL && input->slot == OW_WILD_FOLLOWER_SLOT)
        policy.flags |= OVERWORLD_PICKUP_ROUTE_NATIVE_AVOID_SCRIPTED;
    if (object != NULL) {
        policy.flags |= OVERWORLD_PICKUP_ROUTE_NATIVE_SAME_SURFACE;
        if (allowedTile & OVERWORLD_PICKUP_LANDING_WILD_STRICT_DIAGONAL_MARKER) {
            policy.flags |= OVERWORLD_PICKUP_ROUTE_NATIVE_STRICT_DIAGONAL
                | OVERWORLD_PICKUP_ROUTE_NATIVE_CHECK_WALK_EDGE;
            /* The real controller already selected its authored heading.
             * Bare Walk admission checks that exact physical vector. */
            policy.directions=OVERWORLD_PICKUP_ROUTE_NATIVE_CARDINAL
                | OVERWORLD_PICKUP_ROUTE_NATIVE_DIAGONAL;
        }
    }
    /* Both permissions admit only the current Interest marked by the Wild
     * seam. The private policy has no OOI pseudo-terrain permission. */
    if (world.landingPolicy || (allowedTile & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER))
        policy.flags |= OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION;
    call.version = OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;
    call.size = sizeof(call);
    call.policy = &policy;
    call.world = &world;
    call.targetX = input->x;
    call.targetY = input->y;
    call.destination = &destination;
    call.origin.surfaceId = OW_WILD_SURFACE_ID_NATIVE_GROUND;
    if (world.heightObject != NULL) {
        call.origin.x = world.heightObject->xCurr;
        call.origin.y = world.heightObject->yCurr;
        call.origin.baseY = (s32)world.heightObject->posVec[1];
    }
    /* Admit once before source lookup and pass the validated callbacks to
     * Native_Landing. Missing/malformed data is not a terrain rejection. */
    if (input->behaviorData == NULL)
        return OVERWORLD_MOTION_DECISION_PROFILE;
    call.seams = OverworldPickupRouteWild_GetSeams(&world);
    if (call.seams == NULL)
        return OVERWORLD_MOTION_DECISION_PROFILE;
    if (object != NULL && world.ops->querySurface(input->field,
            world.catalog, object->xCurr, object->yCurr, &sourceSurface))
        call.origin.surfaceId = sourceSurface.surfaceId;
    result = OverworldPickupRouteNative_Landing(&call);
    if (result == OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL)
        return OVERWORLD_MOTION_DECISION_ACCEPTED;
    return result == OVERWORLD_PICKUP_ROUTE_EDGE_INVALID
        ? OVERWORLD_MOTION_DECISION_PROFILE : world.lastDecision;
}
