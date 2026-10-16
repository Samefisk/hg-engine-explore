#include "overworld_pickup_route_native.h"
/* Addon-local default adapter; custom Seams remain supported. */
extern const OverworldPickupRouteNativeSeams *OverworldPickupRouteWild_GetSeams(void *);

typedef OverworldPickupRouteEdgeResult Result;
#define LEGAL OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL
#define BLOCKED OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED
#define INVALID OVERWORLD_PICKUP_ROUTE_EDGE_INVALID

static Result Checked(Result result)
{
    return (u32)result <= OVERWORLD_PICKUP_ROUTE_EDGE_RESOURCE_LIMIT ? result : INVALID;
}
static int Inside(const OverworldPickupRouteBounds *bounds, int x, int y)
{
    return x >= 0 && y >= 0 && x >= bounds->minX && x <= bounds->maxX
        && y >= bounds->minY && y <= bounds->maxY;
}
static Result Begin(OverworldPickupRouteNativeContext *context)
{
    const OverworldPickupRouteNativeSeams *seams;
    const OverworldPickupRouteNativePolicy *policy;
    const OverworldPickupRouteQuery *query;

    if (context == 0) return INVALID;
    context->lastWork = (OverworldPickupRouteNativeWork){0};
    if (context->seams == 0)
        context->seams = OverworldPickupRouteWild_GetSeams(context->world);
    policy = context->policy; seams = context->seams; query = context->query;
    if (context->version != OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION
        || context->size != sizeof(*context) || policy == 0 || seams == 0 || query == 0
        || policy->version != OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION
        || policy->size != sizeof(*policy) || policy->allowedTerrainMask == 0
        || policy->allowedKinds == 0 || (policy->allowedKinds & ~(query!=NULL && query->extension!=NULL?31u:15u)) != 0
        || policy->directions == 0 || (policy->directions & ~3u) != 0
        || (policy->flags & ~31u) != 0
        || policy->reserved[0] || policy->reserved[1] || policy->reserved[2]
        || !OverworldPickupRoute_QueryCurrent(query)
        || query->scopeRevision == 0 || query->movementPolicyRevision == 0
        || query->goalRevision == 0 || query->dynamicRevision == 0
        || query->bounds.minX > query->bounds.maxX || query->bounds.minY > query->bounds.maxY
        || query->origin.reserved || query->cargoPosition.reserved
        || !Inside(&query->bounds, query->origin.x, query->origin.y)
        || (!query->extension && !Inside(&query->bounds, query->cargoPosition.x, query->cargoPosition.y))
        || seams->binding == 0 || seams->terrain == 0 || seams->support == 0
        || seams->occupancy == 0 || seams->reservations == 0 || seams->edgePolicy == 0
        || seams->hop == 0 || seams->pickupReach == 0) return INVALID;
    context->lastWork.binding++; context->lastWork.total++;
    Result result = Checked(seams->binding(context->world, query));
    return result == BLOCKED ? INVALID : result;
}
Result OverworldPickupRouteNative_ValidateBinding(OverworldPickupRouteNativeContext *context)
{
    return Begin(context);
}
static Result ReadPose(OverworldPickupRouteNativeContext *context,
    const OverworldPickupRoutePosition *origin, s16 x, s16 y,
    OverworldPickupRoutePosition *pose, OverworldPickupRouteNativeTile *tile,
    int destinationGuard)
{
    Result result;
    u16 wantedMask = 0xFFFF;
    if (destinationGuard >= 0) {
        wantedMask = context->policy->allowedTerrainMask;
        if (destinationGuard) wantedMask &= ~context->policy->playerTerrainMask;
    }
    *tile = (OverworldPickupRouteNativeTile){0};
    *pose = (OverworldPickupRoutePosition){x,y,0,0,0};
    context->lastWork.terrain++; context->lastWork.total++;
    result = Checked(context->seams->terrain(context->world, x, y, wantedMask, tile));
    if (result != LEGAL) return result;
    if (tile->reserved || (tile->flags & ~7u) != 0) return INVALID;
    pose->surfaceId = tile->surfaceId;
    /* SOURCE support is required even when its terrain is not an allowed
     * destination. A known-disallowed TARGET/GUARD needs no height read. */
    if (destinationGuard >= 0 && (wantedMask & tile->terrainMask) == 0) return BLOCKED;
    context->lastWork.support++; context->lastWork.total++;
    result = Checked(context->seams->support(context->world, origin, x, y, tile, &pose->baseY));
    /* A missing height cannot be promoted to a negative route proof. */
    return result == BLOCKED ? INVALID : result;
}
static Result Landing(OverworldPickupRouteNativeContext *context,
    const OverworldPickupRoutePosition *source, const OverworldPickupRoutePosition *pose,
    const OverworldPickupRouteNativeTile *tile, int guard, int checkSameSurface,
    const OverworldActorHandle *subject)
{
    const OverworldPickupRouteNativePolicy *policy = context->policy;
    u16 mask = policy->allowedTerrainMask;
    u8 includeObjectOfInterest = 1;
    Result result;
    context->lastWork.edgePolicy++; context->lastWork.total++;
    result = Checked(context->seams->edgePolicy(context->world, policy,
        OVERWORLD_PICKUP_ROUTE_NATIVE_LANDING_ONLY, source, 0, pose, tile));
    if (result != LEGAL) return result;
    if (guard) mask &= ~policy->playerTerrainMask;
    if ((mask & tile->terrainMask) == 0
        || ((policy->flags & OVERWORLD_PICKUP_ROUTE_NATIVE_AVOID_SCRIPTED)
            && (tile->flags & OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_SCRIPTED))) return BLOCKED;
    if (checkSameSurface && (policy->flags & OVERWORLD_PICKUP_ROUTE_NATIVE_SAME_SURFACE)
        && source->surfaceId != OVERWORLD_PICKUP_ROUTE_NATIVE_GROUND
        && pose->surfaceId != OVERWORLD_PICKUP_ROUTE_NATIVE_GROUND
        && source->surfaceId != pose->surfaceId) return BLOCKED;
    if (!guard && (tile->flags & OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_OBJECT_OF_INTEREST)
        && (policy->flags & OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION)) includeObjectOfInterest = 0;
    context->lastWork.occupancy++; context->lastWork.total++;
    return Checked(context->seams->occupancy(context->world, subject, pose, includeObjectOfInterest));
}
static Result Reservation(OverworldPickupRouteNativeContext *context,
    const OverworldPickupRoutePosition *pose)
{
    context->lastWork.reservations++; context->lastWork.total++;
    return Checked(context->seams->reservations(context->world, &context->query->subject, pose));
}
Result OverworldPickupRouteNative_Classify(void *rawContext,
    const OverworldPickupRoutePosition *origin, const OverworldPickupRouteEdge *edge,
    OverworldPickupRoutePosition *destination)
{
    OverworldPickupRouteNativeContext *context = rawContext;
    OverworldPickupRoutePosition source, target, side;
    OverworldPickupRouteNativeTile sourceTile, targetTile, sideTile;
    Result result = Begin(context);
    int dx, dy, ax, ay, distance, x, y;
    u8 kind;

    if (result != LEGAL) return result;
    if (origin == 0 || edge == 0 || destination == 0 || origin->reserved
        || !Inside(&context->query->bounds, origin->x, origin->y)) return INVALID;
    dx = edge->dx; dy = edge->dy; ax = dx < 0 ? -dx : dx; ay = dy < 0 ? -dy : dy;
    distance = ax > ay ? ax : ay; kind = edge->tag >> OVERWORLD_PICKUP_ROUTE_NATIVE_KIND_SHIFT;
    if (context->query->extension!=NULL && (edge->tag&OVERWORLD_PICKUP_ROUTE_NATIVE_ENTRY_TELEPORT))
        kind=OVERWORLD_PICKUP_ROUTE_NATIVE_TELEPORT;
    if (distance == 0 || !(context->policy->allowedKinds & (1u << kind))) return BLOCKED;
    if (kind != OVERWORLD_PICKUP_ROUTE_NATIVE_REPOSITION
        && kind != OVERWORLD_PICKUP_ROUTE_NATIVE_TELEPORT) {
        if ((ax && ay && ax != ay)
            || ((ax == 0 || ay == 0) && !(context->policy->directions & OVERWORLD_PICKUP_ROUTE_NATIVE_CARDINAL))
            || ((ax && ay) && !(context->policy->directions & OVERWORLD_PICKUP_ROUTE_NATIVE_DIAGONAL))) return BLOCKED;
    }
    if ((kind == OVERWORLD_PICKUP_ROUTE_NATIVE_WALK && distance != 1)
        || (kind == OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE && (distance != 2 || (ax && ay)))
        || (kind == OVERWORLD_PICKUP_ROUTE_NATIVE_REPOSITION && distance > 255)) return BLOCKED;
    if (kind == OVERWORLD_PICKUP_ROUTE_NATIVE_HOP) {
        if (context->policy->hopMinDistance == 0
            || context->policy->hopMinDistance > context->policy->hopMaxDistance) return INVALID;
        if (distance < context->policy->hopMinDistance || distance > context->policy->hopMaxDistance) return BLOCKED;
    }
    x = origin->x + dx; y = origin->y + dy;
    if (!Inside(&context->query->bounds, x, y)) return BLOCKED;
    result = ReadPose(context, origin, origin->x, origin->y, &source, &sourceTile, -1);
    if (result != LEGAL) return result;
    if (source.baseY != origin->baseY || source.surfaceId != origin->surfaceId) return INVALID;
    result = ReadPose(context, origin, (s16)x, (s16)y, &target, &targetTile, 0);
    if (result != LEGAL) return result;
    if (kind == OVERWORLD_PICKUP_ROUTE_NATIVE_WALK && ax && ay
        && (context->policy->flags & OVERWORLD_PICKUP_ROUTE_NATIVE_STRICT_DIAGONAL)) {
        for (u8 i = 0; i < 2; i++) {
            result = ReadPose(context, origin, i ? origin->x : (s16)x,
                i ? (s16)y : origin->y, &side, &sideTile, 1);
            if (result != LEGAL) return result;
            result = Landing(context, origin, &side, &sideTile, 1, 1, &context->query->subject);
            if (result != LEGAL) return result;
        }
    }
    result = Landing(context, origin, &target, &targetTile, 0, 1, &context->query->subject);
    if (result != LEGAL) return result;
    context->lastWork.edgePolicy++; context->lastWork.total++;
    result = Checked(context->seams->edgePolicy(context->world, context->policy, kind,
        origin, &sourceTile, &target, &targetTile));
    if (result != LEGAL) return result;
    if (kind != OVERWORLD_PICKUP_ROUTE_NATIVE_WALK
        && kind != OVERWORLD_PICKUP_ROUTE_NATIVE_TELEPORT) {
        context->lastWork.hop++; context->lastWork.total++;
        result = Checked(context->seams->hop(context->world, context->policy, kind,
            (u16)distance, origin, &target));
        if (result != LEGAL) return result;
    }
    result = Reservation(context, &target);
    if (result == LEGAL) *destination = target;
    return result;
}
Result OverworldPickupRouteNative_PickupGoal(OverworldPickupRouteNativeContext *context,
    s16 x, s16 y, OverworldPickupRoutePosition *destination)
{
    OverworldPickupRoutePosition target;
    OverworldPickupRouteNativeTile tile;
    Result result = Begin(context);
    if (result != LEGAL) return result;
    if (destination == 0) return INVALID;
    if (!Inside(&context->query->bounds, x, y)
        || (x == context->query->cargoPosition.x && y == context->query->cargoPosition.y)) return BLOCKED;
    result = ReadPose(context, &context->query->origin, x, y, &target, &tile, 1);
    if (result != LEGAL) return result;
    /* Goals do not inherit the distant origin's same-surface restriction.
     * A route can reach them through an intervening native-ground tile. */
    result = Landing(context, &context->query->origin, &target, &tile, 1, 0, &context->query->subject);
    if (result != LEGAL) return result;
    result = Reservation(context, &target);
    if (result != LEGAL) return result;
    context->lastWork.edgePolicy++; context->lastWork.total++;
    result = Checked(context->seams->pickupReach(context->world, context->policy,
        &target, &context->query->cargoPosition));
    if (result == LEGAL) *destination = target;
    return result;
}

Result OverworldPickupRouteNative_Landing(const OverworldPickupRouteNativeLandingCall *call)
{
    OverworldPickupRouteNativeContext context = {0};
    OverworldPickupRoutePosition target, side, source;
    OverworldPickupRouteNativeTile targetTile, sideTile, sourceTile;
    const OverworldPickupRouteNativePolicy *policy;
    const OverworldPickupRouteNativeSeams *seams;
    Result result;
    if (call == 0 || call->version != OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION
        || call->size != sizeof(*call) || call->destination == 0
        || call->origin.reserved || call->targetX < 0 || call->targetY < 0)
        return INVALID;
    policy=call->policy; seams=call->seams;
    if (seams == 0) seams=OverworldPickupRouteWild_GetSeams(call->world);
    if (policy == 0 || seams == 0
        || policy->version != OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION
        || policy->size != sizeof(*policy) || policy->allowedTerrainMask == 0
        || (policy->flags & ~31u) || policy->reserved[0]
        || policy->reserved[1] || policy->reserved[2]
        || seams->binding == 0 || seams->terrain == 0 || seams->support == 0
        || seams->occupancy == 0 || seams->edgePolicy == 0
        || (call->subject != 0 && (call->subject->reserved
            || call->subject->slot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
            || call->subject->generation == 0 || call->subject->fieldEpoch == 0)))
        return INVALID;
    context.version=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;
    context.size=sizeof(context); context.policy=policy;
    context.seams=seams; context.world=call->world;
    context.lastWork.binding++; context.lastWork.total++;
    result=Checked(seams->binding(call->world, 0));
    if (result == BLOCKED) result=INVALID;
    if (result != LEGAL) goto finished;
    if ((policy->flags & OVERWORLD_PICKUP_ROUTE_NATIVE_STRICT_DIAGONAL)
        && call->targetX != call->origin.x && call->targetY != call->origin.y) {
        for (u8 i=0; i<2; i++) {
            result=ReadPose(&context, &call->origin,
                i ? call->origin.x : call->targetX,
                i ? call->targetY : call->origin.y, &side, &sideTile, 1);
            if (result != LEGAL) goto finished;
            result=Landing(&context, &call->origin, &side, &sideTile, 1, 1, call->subject);
            if (result != LEGAL) goto finished;
        }
    }
    result=ReadPose(&context, &call->origin, call->targetX, call->targetY,
        &target, &targetTile, 0);
    if (result != LEGAL) goto finished;
    result=Landing(&context, &call->origin, &target, &targetTile, 0, 1, call->subject);
    if (result != LEGAL) goto finished;
    if (policy->flags & OVERWORLD_PICKUP_ROUTE_NATIVE_CHECK_WALK_EDGE) {
        result=ReadPose(&context,&call->origin,call->origin.x,call->origin.y,&source,&sourceTile, -1);
        if (result != LEGAL) goto finished;
        context.lastWork.edgePolicy++;context.lastWork.total++;
        result=Checked(seams->edgePolicy(call->world,policy,OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,
            &call->origin,&sourceTile,&target,&targetTile));
    }
    if (result == LEGAL) *call->destination=target;
finished:
    if (call->work != 0) *call->work=context.lastWork;
    return result;
}
