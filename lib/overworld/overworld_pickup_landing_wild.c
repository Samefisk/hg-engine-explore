#include "../../include/overworld_pickup_landing_wild.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/map_events_internal.h"

/* The same bare Landing setup used by Wild before it acquired an addon-local
 * code home. This function never creates a route query or publishes motion. */
OverworldMotionDecision OverworldPickupLandingWild_Classify(
    const OverworldPickupRouteWildLandingCall *input)
{
    struct {
        OverworldPickupRouteNativePolicy policy;
        OverworldPickupRouteNativeLandingCall call;
        OverworldPickupRouteWildWorld world;
    } setup = {0};
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
    setup.world.version = OVERWORLD_PICKUP_ROUTE_WILD_VERSION;
    setup.world.size = sizeof(setup.world);
    setup.world.field = input->field;
    setup.world.state = input->state;
    setup.world.slot = (u8)input->slot;
    setup.world.subjectObject = object;
    setup.world.heightObject = object != NULL ? object
        : input->field->playerAvatar != NULL
            ? input->field->playerAvatar->mapObject : NULL;
    setup.world.collisionIgnoredObject = input->collisionIgnoredObject;
    setup.world.behaviorData = input->behaviorData;
    setup.world.catalog = input->behaviorData != NULL
        ? (const OverworldWildSurfaceCatalog *)input->behaviorData->surfaceModels : NULL;
    setup.world.ops = input->ops;
    setup.world.finalTargetX = input->finalTargetX;
    setup.world.finalTargetY = input->finalTargetY;
    /* Authenticate the catalog and callbacks before any surface query. */
    if (input->behaviorData == NULL)
        return OVERWORLD_MOTION_DECISION_PROFILE;
    setup.call.seams = OverworldPickupRouteWild_GetSeams(&setup.world);
    if (setup.call.seams == NULL)
        return OVERWORLD_MOTION_DECISION_PROFILE;
    /* Spawn placement only. A roof's north/back row is ordinary ground;
     * neither the roof nor this selector grants a movement permission.
     * Ignore other destination choices while the restriction is enabled. */
    if (allowedTile & OW_WILD_SPAWN_DESTINATION_MASK_BEHIND_BUILDINGS) {
        if (input->state != NULL || input->slot != -1
            || !setup.world.ops->playable(input->field, input->x, input->y + 1)
            || !setup.world.ops->querySurface(input->field, setup.world.catalog,
                input->x, input->y + 1, &sourceSurface)
            || sourceSurface.surfaceType != OW_WILD_SURFACE_TYPE_ROOFTOP)
            return OVERWORLD_MOTION_DECISION_TERRAIN;
        allowedTile = OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND;
    }
    if (allowedTile & OVERWORLD_PICKUP_LANDING_WILD_PERMIT_BOUND_OOI_MARKER)
        setup.world.landingPolicy = OVERWORLD_PICKUP_ROUTE_WILD_PERMIT_BOUND_OOI_OCCUPANCY;
    setup.policy.version = OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;
    setup.policy.size = sizeof(setup.policy);
    setup.policy.allowedTerrainMask = allowedTile
        & ~(OVERWORLD_PICKUP_LANDING_WILD_STRICT_DIAGONAL_MARKER
            | OVERWORLD_PICKUP_LANDING_WILD_PERMIT_BOUND_OOI_MARKER);
    /* Occupancy permission must not make a forbidden physical tile legal.
     * All authored actual terrain/surface bits remain intact. */
    if (allowedTile & OVERWORLD_PICKUP_LANDING_WILD_PERMIT_BOUND_OOI_MARKER)
        setup.policy.allowedTerrainMask &= ~OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER;
    setup.policy.playerTerrainMask = OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER;
    if (setup.policy.allowedTerrainMask == 0)
        return OVERWORLD_MOTION_DECISION_TERRAIN;
    if (input->state != NULL && input->slot == OW_WILD_FOLLOWER_SLOT)
        setup.policy.flags |= OVERWORLD_PICKUP_ROUTE_NATIVE_AVOID_SCRIPTED;
    if (object != NULL) {
        setup.policy.flags |= OVERWORLD_PICKUP_ROUTE_NATIVE_SAME_SURFACE;
        if (allowedTile & OVERWORLD_PICKUP_LANDING_WILD_STRICT_DIAGONAL_MARKER) {
            setup.policy.flags |= OVERWORLD_PICKUP_ROUTE_NATIVE_STRICT_DIAGONAL
                | OVERWORLD_PICKUP_ROUTE_NATIVE_CHECK_WALK_EDGE;
            /* The real controller already selected its authored heading.
             * Bare Walk admission checks that exact physical vector. */
            setup.policy.directions=OVERWORLD_PICKUP_ROUTE_NATIVE_CARDINAL
                | OVERWORLD_PICKUP_ROUTE_NATIVE_DIAGONAL;
        }
    }
    /* Both permissions admit only the current Interest marked by the Wild
     * seam. The private setup.policy has no OOI pseudo-terrain permission. */
    if (allowedTile & (OVERWORLD_PICKUP_LANDING_WILD_PERMIT_BOUND_OOI_MARKER
        | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER))
        setup.policy.flags |= OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION;
    setup.call.version = OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;
    setup.call.size = sizeof(setup.call);
    setup.call.policy = &setup.policy;
    setup.call.world = &setup.world;
    setup.call.targetX = input->x;
    setup.call.targetY = input->y;
    setup.call.destination = &destination;
    setup.call.origin.surfaceId = OW_WILD_SURFACE_ID_NATIVE_GROUND;
    if (setup.world.heightObject != NULL) {
        setup.call.origin.x = setup.world.heightObject->xCurr;
        setup.call.origin.y = setup.world.heightObject->yCurr;
        setup.call.origin.baseY = (s32)setup.world.heightObject->posVec[1];
    }
    if (object != NULL && setup.world.ops->querySurface(input->field,
            setup.world.catalog, object->xCurr, object->yCurr, &sourceSurface))
        setup.call.origin.surfaceId = sourceSurface.surfaceId;
    result = OverworldPickupRouteNative_Landing(&setup.call);
    if (result == OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL)
        return OVERWORLD_MOTION_DECISION_ACCEPTED;
    return result == OVERWORLD_PICKUP_ROUTE_EDGE_INVALID
        ? OVERWORLD_MOTION_DECISION_PROFILE : setup.world.lastDecision;
}
