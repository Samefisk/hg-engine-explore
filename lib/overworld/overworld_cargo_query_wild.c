#include "overworld_cargo_query_wild.h"
#include "overworld_entry_route.h"
#include "overworld_wild_runtime_state_internal.h"
#include "overworld_actor_system_internal.h"
#include "map_events_internal.h"
#if defined(OVERWORLD_BEHAVIOR_HOST) || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#include <string.h>
#endif

#define OBJECTS 64 /* Stock Field manager, field_warp_tasks.c. */
#define CHANGES 160 /* Two endpoints each for64 objects +10 reservations +front. */
#define EDGES 256
#define PENDING OVERWORLD_PICKUP_ROUTE_PENDING
#define INVALID OVERWORLD_PICKUP_ROUTE_INVALID
#define LIMIT OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT
#define UNREACHABLE OVERWORLD_PICKUP_ROUTE_UNREACHABLE
#define LEGAL OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL
#define DEFERRED OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED

typedef struct Footprint { s16 x,y; s32 height; u32 flags; s32 identity; } Footprint;
typedef struct NativeQuery {
    OverworldCargoQueryState state;
    OverworldCargoQueryStorage storage;
    OverworldPickupRouteEdge edges[EDGES];
    Footprint objects[OBJECTS], reservations[OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS], front;
    OverworldCargoQueryChangedTile changed[CHANGES];
    MapObjectMan *manager;
    OverworldActorHandle owner;
    OverworldCargoQueryResult cached;
    OverworldPickupRouteBounds bounds;
    u32 frame, dynamicRevision, scopeRevision, policyRevision;
    u16 edgeCount, changeCount;
    u8 valid, changesComplete;
    u16 waitingMask; /* Existing tail padding; requests are not ownership. */
    u32 targetCheckFrame;
    u8 checkingTargets;
    OverworldEntryRouteSearch entry;
    /* Entry rejects the follower slot before path access. Keep one full
     * 96-step record for each of the nine admitted Wild slots. */
    OverworldEntryRoutePath entryPaths[OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS-1];
    OverworldWildPreparedSpawn prepared;
    OverworldWildBehaviorProfile entryProfile;
    u32 entryFrame, entryLifeSerial, entryLifeFrame;
    u16 entryLifeUpdates;
    u8 entryRootReady, entryFrameValid, entryLifeSlot, entryLifeFrameValid;
} NativeQuery;

/* Caller has already rejected slot7 and slots outside the Actor table.
 * This is storage indexing only; full slot identities remain unchanged. */
static OverworldEntryRoutePath *EntryPath(NativeQuery *q,u8 slot)
{ return &q->entryPaths[slot-(slot>OW_WILD_FOLLOWER_SLOT)]; }

static u8 Same(const void *a,const void *b,u16 bytes)
{ const u8 *x=a,*y=b;while(bytes--) if(*x++!=*y++) return 0;return 1; }
static u32 Hash(u32 hash,u32 value) { return (hash^value)*16777619u; }
static u8 CurrentActor(const OverworldPickupRouteWildWorld *,const OverworldActorSystemState *,const OverworldActorHandle *);
static void Change(NativeQuery *q,const Footprint *old,const Footprint *now,u8 ignored)
{
    if(Same(old,now,sizeof(*old))) return;
    q->dynamicRevision++;
    if(ignored) return;
    if(q->changeCount+2>CHANGES) { q->changesComplete=0;return; }
    if(old->flags) q->changed[q->changeCount++]=(OverworldCargoQueryChangedTile){old->x,old->y};
    if(now->flags) q->changed[q->changeCount++]=(OverworldCargoQueryChangedTile){now->x,now->y};
}
/* All native occupancy readers use current XY and rendered height. Player
 * front and Actor's current destination reservations are separate dependencies.
 * Compare the full conservative flag word, not just the Pokemon list. */
static __attribute__((noinline)) u8 Observe(NativeQuery *q,const OverworldCargoQueryWildCall *call,
    const OverworldActorSystemState *actors,u32 frame)
{
    MapObjectMan *manager=(MapObjectMan *)call->world->field->mapObjectMan;
    if(manager==NULL || manager->objects==NULL || manager->object_count>OBJECTS) return 0;
    q->frame=frame;
    const OverworldPickupRouteWildWorld *world=call->world;
    const OverworldWildOverlayRuntimeState *runtime=world->state->movementRuntimeState;
    const OverworldActorHandle *subject=&runtime->conditions->bindings[world->slot].subject;
    u8 ignoreSubject=subject->slot==world->slot
        && subject->fieldEpoch==actors->fieldEpoch && subject->mapGeneration==actors->mapGeneration
        && world->state->movementFieldSystem==world->field
        && CurrentActor(world,actors,subject)
        && world->subjectObject==world->state->spawns[world->slot].object;
    /* Occupancy/reservations ignore this exact current Subject. Its motion
     * still advances revisions and origin; it is not a collision dependency. */
    if(q->manager!=manager) q->changesComplete=0;
    for(u8 i=0;i<OBJECTS;i++) {
        Footprint now={0};
        if(i<manager->object_count) {
            const LocalMapObject *object=&manager->objects[i];
            if(object->flags&MAPOBJECTFLAG_ACTIVE) {
                now.x=object->xCurr;now.y=object->yCurr;
                now.height=(s32)object->posVec[1];now.flags=object->flags;now.identity=object->id;
            }
        }
        Change(q,&q->objects[i],&now,ignoreSubject && i<manager->object_count
            && &manager->objects[i]==world->subjectObject);q->objects[i]=now;
    }
    for(u8 i=0;i<OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS;i++) {
        const OverworldActorRuntimeSlot *actor=&actors->slots[i];
        Footprint now={0};
        if(actor->snapshot.reservationId) {
            now.x=actor->snapshot.targetX;now.y=actor->snapshot.targetY;
            now.height=actor->policy.targetSurfaceId;
            now.flags=actor->snapshot.reservationId|((u32)actor->snapshot.handle.generation<<16);
        }
        Change(q,&q->reservations[i],&now,ignoreSubject && i==subject->slot);q->reservations[i]=now;
    }
    Footprint front={0};
    LocalMapObject *player=call->world->field->playerAvatar!=NULL
        ?call->world->field->playerAvatar->mapObject:NULL;
    if(player!=NULL) {
        front.x=player->xCurr;front.y=player->yCurr;front.flags=1;
        u8 direction=player->curFacing;
        if(direction<2) front.y+=direction?1:-1;
        else if(direction<4) front.x+=direction==3?1:-1;
    }
    Change(q,&q->front,&front,0);q->front=front;q->manager=manager;
    if(!q->dynamicRevision) q->dynamicRevision=1;
    return 1;
}
/* Stock Field land manager has four slots at90..9C. Each slot's864 flag
 * says its860 matrix index is loaded (ov01_021F4C6C). Bound the loaded scope,
 * never a radius around Cargo. A stream in progress defers the whole query. */
static u8 Scope(OverworldPickupRouteWildWorld *world,NativeQuery *q)
{
    const u8 *matrix=(const u8 *)world->field->map_matrix;
    const u8 *land=*(const u8 **)((u8 *)world->field+0x2C);
    if(matrix==NULL || land==NULL || !matrix[0] || !matrix[1] || land[0xA0]) return 0;
    OverworldPickupRouteBounds bounds={32767,32767,0,0};u8 found=0;
    u32 hash=Hash(2166136261u,world->state->mapGeneration);
    for(u8 i=0;i<4;i++) {
        const u8 *slot=*(const u8 **)(land+0x90+4*i);
        if(slot==NULL || !*(const u32 *)(slot+0x864)) { hash=Hash(hash,0xFFFFFFFFu);continue; }
        u32 index=*(const u32 *)(slot+0x860),x=index,y=0;
        if(index>=(u32)matrix[0]*matrix[1]) return 0;
        while(x>=matrix[0]) { x-=matrix[0];y++; }
        s16 lowX=x<<5,lowY=y<<5,highX=lowX+31,highY=lowY+31;
        if(lowX<bounds.minX) bounds.minX=lowX;if(lowY<bounds.minY) bounds.minY=lowY;
        if(highX>bounds.maxX) bounds.maxX=highX;if(highY>bounds.maxY) bounds.maxY=highY;
        hash=Hash(hash,index);found=1;
    }
    if(!found) return 0;
    q->bounds=bounds;q->scopeRevision=hash?hash:1;return 1;
}
/* One native observation validity check. Return the current object so the
 * caller does not repeat the slot lookup before refreshing its XY. */
static __attribute__((noinline)) LocalMapObject *CurrentObservationObject(
    const OverworldPickupRouteWildWorld *world,
    const OverworldActorSystemState *actors,const OverworldActorHandle *handle)
{
    if(actors==NULL || handle->slot>=OW_WILD_MAX_SPAWNS) return NULL;
    const OverworldActorStateSnapshot *actor=&actors->slots[handle->slot].snapshot;
    const OverworldWildSpawn *spawn=&world->state->spawns[handle->slot];
    LocalMapObject *object=spawn->object;
    if(!actor->active || !Same(handle,&actor->handle,sizeof(*handle))
        || !spawn->active || actor->subjectIdentity!=spawn->personality
        || object==NULL || !(object->flags&MAPOBJECTFLAG_ACTIVE)
        || !world->ops->currentObject(world->field,object)) return NULL;
    return object;
}
static u8 CurrentActor(const OverworldPickupRouteWildWorld *world,
    const OverworldActorSystemState *actors,const OverworldActorHandle *handle)
{
    /* Retain CurrentActor's stricter encounter guard before currentObject. */
    if(actors==NULL || handle->slot>=OW_WILD_MAX_SPAWNS
        || world->state->spawns[handle->slot].encounterGeneration
            !=handle->encounterGeneration) return 0;
    return CurrentObservationObject(world,actors,handle)!=NULL;
}
static OverworldPickupRouteEdgeResult Position(void *raw,const OverworldActorHandle *handle,
    OverworldPickupRoutePosition *out)
{
    OverworldPickupRouteWildWorld *world=raw;
    if(!CurrentActor(world,world->ops->actorState(),handle)) return OVERWORLD_PICKUP_ROUTE_EDGE_INVALID;
    LocalMapObject *object=world->state->spawns[handle->slot].object;
    OverworldWildSurfaceHit hit;
    const OverworldWildSurfaceHit *support=world->ops->querySurface(world->field,world->catalog,
        object->xCurr,object->yCurr,&hit)?&hit:NULL;
    s32 height;
    if(world->ops->behavior(world->field,object->xCurr,object->yCurr)==0xFF
        || !world->ops->resolveBaseYAt(world->field,support,(s32)object->posVec[1],
            object->flags,object->xCurr,object->yCurr,&height)) return DEFERRED;
    *out=(OverworldPickupRoutePosition){object->xCurr,object->yCurr,height,
        support!=NULL?support->surfaceId:OVERWORLD_PICKUP_ROUTE_NATIVE_GROUND,0};return LEGAL;
}
static __attribute__((noinline)) u8 Policy(NativeQuery *q,const OverworldCargoQueryWildCall *call,
    OverworldPickupRouteNativePolicy *policy)
{
    const OverworldWildBehaviorProfileData *lane=&call->profile->owner;
    u8 mode=lane->hopAllowNonCardinal&3;
    u8 entry=call->routeOperation==OVERWORLD_FIELD_ROUTE_ENTRY;
    u8 teleport=entry && OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(call->locomotion);
    u8 hop=call->locomotion==OW_WILD_BEHAVIOR_LOCOMOTION_HOP
        || (entry && call->locomotion==OW_WILD_BEHAVIOR_LOCOMOTION_WALK
            && OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(mode));
    if(!hop && !teleport && call->locomotion!=OW_WILD_BEHAVIOR_LOCOMOTION_WALK) return 0;
    *policy=(OverworldPickupRouteNativePolicy){0};
    policy->version=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;policy->size=sizeof(*policy);
    policy->allowedTerrainMask=call->allowedTerrainMask;
    policy->playerTerrainMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER;
    policy->allowedKinds=1u<<(teleport?OVERWORLD_PICKUP_ROUTE_NATIVE_TELEPORT:
        hop?OVERWORLD_PICKUP_ROUTE_NATIVE_HOP:OVERWORLD_PICKUP_ROUTE_NATIVE_WALK);
    if(entry && !hop && !teleport && lane->jumpLevel)
        policy->allowedKinds|=1u<<OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE;
    policy->directions=(OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(mode)?1:0)
        |(OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(mode)?2:0);
    if(teleport) policy->directions=3;
    policy->flags=OVERWORLD_PICKUP_ROUTE_NATIVE_SAME_SURFACE
        |OVERWORLD_PICKUP_ROUTE_NATIVE_STRICT_DIAGONAL;
    if(call->world->slot==OW_WILD_FOLLOWER_SLOT) policy->flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_AVOID_SCRIPTED;
    if(call->allowedTerrainMask&OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER)
        policy->flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION;
    policy->hopMinDistance=teleport?1:hop?(call->locomotion==OW_WILD_BEHAVIOR_LOCOMOTION_WALK?1:lane->hopMinDistance):1;
    policy->hopMaxDistance=teleport?6:hop?(call->locomotion==OW_WILD_BEHAVIOR_LOCOMOTION_WALK?1:lane->hopMaxDistance):1;
    policy->resolvedProfile=call->profile;policy->resolvedLane=lane;
    if(!policy->hopMinDistance || policy->hopMinDistance>policy->hopMaxDistance) return 0;
    LocalMapObject *subject=call->world->subjectObject;
    const OverworldEntryRoutePhysical *prepared=call->world->preparedPhysical;
    if(subject==NULL && prepared==NULL) return 0;
    OverworldActorPolicyView view={0};
    if(subject!=NULL && !call->world->ops->inspectPolicy(call->world->slot,&view)) return 0;
    u32 hash=2166136261u;
    for(u8 i=4;i<13;i++) hash=Hash(hash,((const u8 *)policy)[i]);
    /* Walk legality does not depend on Hop timing or vertical clearance.
     * Preserve a prepared Walk route across a search-speed profile change. */
    if(hop) {
        hash=Hash(hash,OW_WILD_BEHAVIOR_SKID_BOOLEAN(lane->hopAllowVerticalObstacles));
        hash=Hash(hash,lane->hopTime);hash=Hash(hash,lane->hopElevationTimeScale);
        hash=Hash(hash,lane->hopElevationArcScale);
    }
    if (entry) {
        /* Current resolved policy is frozen once per queued attempt. Live
         * conditions/chains re-root from their own resolved policy. */
        for (u16 i=0;i<sizeof(*lane);i++) hash=Hash(hash,((const u8 *)lane)[i]);
    }
    if (subject==NULL) {
        hash=Hash(hash,prepared->flags2&(1u<<2));
        hash=Hash(hash,prepared->flags&((1u<<23)|(1u<<29)));
        hash=Hash(hash,prepared->rangeX);hash=Hash(hash,prepared->rangeY);
        /* A freshly created Subject is anchored at its prepared origin.
         * Include the same two zero offsets as the live policy hash. */
        hash=Hash(hash,0);hash=Hash(hash,0);
    } else {
    hash=Hash(hash,subject->flags2&(1u<<2));
    hash=Hash(hash,subject->flags&((1u<<23)|(1u<<29)));
    hash=Hash(hash,subject->xrange);hash=Hash(hash,subject->yrange);
    /* Ordinary accepted Walk updates current at its render midpoint, then
     * rebases init at completion. Previous stays the accepted origin; keep
     * that transient render change out of the relative range policy. */
    s32 anchorX=subject->xCurr,anchorY=subject->yCurr;
    if(!hop && view.pendingStep==OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED
        && (u8)(view.motionPhase-OVERWORLD_MOTION_PHASE_MOVING)<=1
        && !view.pendingSkid && !view.walkMomentum.skidRemaining) {
        anchorX=subject->xPrev;anchorY=subject->yPrev;
    }
    /* An unlimited axis has no anchor-dependent range restriction. Hop's
     * render midpoint must not invalidate the same legal route policy. */
    hash=Hash(hash,subject->xrange==-1?0:subject->xInit-anchorX);
    hash=Hash(hash,subject->yrange==-1?0:subject->yInit-anchorY);
    if((view.chainPauseAction&0xF0)==0x90) {
        hash=Hash(hash,view.chainPauseAction);hash=Hash(hash,view.chainStepsRemaining);
        hash=Hash(hash,subject->xCurr);hash=Hash(hash,subject->yCurr);
    }
    }
    u16 count=0;
    for(u16 distance=policy->hopMinDistance;distance<=policy->hopMaxDistance;distance++) {
        for(u8 direction=0;direction<8;direction++) {
            /* The same eight cardinal/diagonal offsets, in native tag order. */
            static const s8 directions[8][2] = {
                {0,-1},{0,1},{-1,0},{1,0},{-1,-1},{1,-1},{-1,1},{1,1}
            };
            if(!(policy->directions & (direction<4?1:2))) continue;
            s16 dx=directions[direction][0]*distance;
            s16 dy=directions[direction][1]*distance;
            if(count==EDGES) return 0;
            q->edges[count++]=(OverworldPickupRouteEdge){dx,dy,
                teleport?(OVERWORLD_PICKUP_ROUTE_NATIVE_ENTRY_TELEPORT|direction):
                OVERWORLD_PICKUP_ROUTE_NATIVE_TAG(hop?OVERWORLD_PICKUP_ROUTE_NATIVE_HOP:
                    OVERWORLD_PICKUP_ROUTE_NATIVE_WALK,direction)};
        }
    }
    if (entry && !hop && !teleport && lane->jumpLevel) {
        for (u8 direction=0;direction<4;direction++) {
            static const s8 offsets[4][2]={{0,-2},{0,2},{-2,0},{2,0}};
            if (count==EDGES) return 0;
            q->edges[count++]=(OverworldPickupRouteEdge){offsets[direction][0],offsets[direction][1],
                OVERWORLD_PICKUP_ROUTE_NATIVE_TAG(OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE,direction)};
        }
    }
    q->edgeCount=count;q->policyRevision=hash?hash:1;return count!=0;
}
/* Native callers use slot bits; the reducer uses compact observation bits.
 * Match the full Cargo identity again before publishing a native slot bit. */
static u16 CargoObservationMask(const OverworldBehaviorConditionWorldView *view,
    u16 eligible, const OverworldActorHandle *cargo)
{
    for(u8 n=0;n<view->actorCount;n++)
        if((eligible&(1u<<n)) && view->actors[n].valid
            && Same(cargo,&view->actors[n].actor,sizeof(*cargo))) return 1u<<n;
    return 0;
}
static void PublishSlotMask(OverworldCargoQueryResult *result)
{
    result->eligibleActorMask=result->status==OVERWORLD_PICKUP_ROUTE_REACHABLE
        && result->eligibleActorMask && result->route.cargo.slot<OW_WILD_MAX_SPAWNS
        ?1u<<result->route.cargo.slot:0;
}
static u8 CurrentTarget(const OverworldPickupRouteWildWorld *world,
    const OverworldActorSystemState *actors,const OverworldBehaviorConditionWorldView *view,
    const OverworldTargetBinding *binding)
{
    if(binding->flags!=OVERWORLD_TARGET_BINDING_BOUND || binding->target.reserved) return 0;
    if(binding->target.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER) return view->playerValid;
    return binding->target.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
        && CurrentActor(world,actors,&binding->target.actor)
        && CargoObservationMask(view,(1u<<view->actorCount)-1,&binding->target.actor)!=0;
}
static OverworldPickupRouteStatus Pending(const OverworldCargoQueryWildCall *call,
    const OverworldActorSystemState *actors,const OverworldWildBehaviorConditionRuntime *conditions,
    OverworldCargoQueryResult *result)
{
    const OverworldPickupRouteWildWorld *world=call->world;
    const OverworldTargetBindingsState *bindings=&conditions->bindings[world->slot];
    const OverworldTargetBinding *objectOfInterest=&bindings->bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST];
    const OverworldTargetBinding *cargo=&bindings->bindings[OVERWORLD_TARGET_BINDING_CARGO];
    result->status=PENDING;result->flags=0;
    result->eligibleActorMask=0;result->route.hasNextStep=0;
    /* Retain only the exact current pair already admitted by a condition.
     * No height/edge proof is inferred, and new selection gets no flag. */
    if(bindings->subject.slot==world->slot
        && CurrentActor(world,actors,&bindings->subject)
        && world->subjectObject==world->state->spawns[world->slot].object
        && cargo->target.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
        && cargo->target.actor.slot<OW_WILD_MAX_SPAWNS
        && cargo->target.actor.slot!=world->slot
        && (call->eligibleActorMask&(1u<<cargo->target.actor.slot))
        && CurrentTarget(world,actors,&conditions->frame.world,cargo)
        && CurrentTarget(world,actors,&conditions->frame.world,objectOfInterest)
        && (objectOfInterest->target.kind!=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
            || (objectOfInterest->target.actor.slot!=world->slot
                && (call->options->usesBinding==OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST
                    || !Same(&objectOfInterest->target.actor,&cargo->target.actor,sizeof(cargo->target.actor))))))
        result->flags=OVERWORLD_CARGO_QUERY_RETAIN_BOUND_CARGO;
    return PENDING;
}
static __attribute__((noinline)) void Restart(NativeQuery *q)
{
    u32 frame=q->state.frame;u8 frameValid=q->state.frameValid;
    OverworldCargoQuery_Clear(&q->state);
    /* Changing owner must not grant another native query in this frame. */
    q->state.frame=frame;q->state.frameValid=frameValid;
    q->cached=(OverworldCargoQueryResult){0};q->cached.status=PENDING;q->valid=0;
    q->targetCheckFrame=0;q->checkingTargets=0;
}

static __attribute__((noinline)) u8 Unclaimed(const OverworldPickupRouteWildWorld *world,
    const OverworldActorSystemState *actors,const OverworldTargetBindingsState *bindings,
    const OverworldWildOverlayRuntimeState *runtime)
{
    u8 slot=bindings->subject.slot;
    return CurrentActor(world,actors,&bindings->subject)
        && !bindings->bindings[OVERWORLD_TARGET_BINDING_CARGO].flags
        && runtime->throwState.targets[slot]==OW_WILD_HELPER_THROW_TARGET_NONE
        && !((runtime->throwState.carrierMask
            |world->state->captureTargetMask)&(1u<<slot))
        && world->state->movementActorControlModes[slot]==OW_WILD_ACTOR_CONTROL_AUTONOMOUS
        && !actors->slots[slot].snapshot.reservationId
        && actors->slots[slot].snapshot.motionPhase==OVERWORLD_ACTOR_PHASE_IDLE;
}

static __attribute__((noinline)) u8 NextWaiting(NativeQuery *q,
    const OverworldPickupRouteWildWorld *world,const OverworldActorSystemState *actors,
    const OverworldWildOverlayRuntimeState *runtime)
{
    u8 slot=q->owner.slot;
    for(u8 n=0;n<OW_WILD_MAX_SPAWNS;n++) {
        if(++slot>=OW_WILD_MAX_SPAWNS) slot=0;
        if(!(q->waitingMask&(1u<<slot))) continue;
        const OverworldTargetBindingsState *bindings=&runtime->conditions->bindings[slot];
        const OverworldTargetBinding *cargo=&bindings->bindings[OVERWORLD_TARGET_BINDING_CARGO];
        if(bindings->subject.slot==slot && CurrentActor(world,actors,&bindings->subject)
            && actors->slots[slot].snapshot.role!=OVERWORLD_ACTOR_ROLE_MOUNTED
            && world->state->movementActorControlModes[slot]==OW_WILD_ACTOR_CONTROL_AUTONOMOUS
            && !(world->state->captureTargetMask&(1u<<slot))
            && !(runtime->throwState.targets[slot]&OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG)
            && CurrentTarget(world,actors,&runtime->conditions->frame.world,
                &bindings->bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST])
            && (!cargo->flags || CurrentTarget(world,actors,&runtime->conditions->frame.world,cargo)))
            return slot;
        q->waitingMask&=~(1u<<slot);
    }
    return OW_WILD_MAX_SPAWNS;
}

/* Keep arbitration separate from the large native policy/graph frame. */
#if defined(__GNUC__) && !defined(__clang__)
__attribute__((optimize("no-tree-forwprop")))
#endif
static __attribute__((noinline)) u8 QueryTurn(NativeQuery *q,
    const OverworldCargoQueryWildCall *call,const OverworldActorSystemState *actors)
{
    OverworldPickupRouteWildWorld *world=call->world;
    OverworldWildOverlayRuntimeState *runtime=world->state->movementRuntimeState;
    OverworldWildBehaviorConditionRuntime *conditions=runtime->conditions;
    const OverworldTargetBindingsState *bindings=&conditions->bindings[world->slot];
    if(q->valid && Same(&q->owner,&bindings->subject,sizeof(q->owner))
        && q->cached.status==OVERWORLD_PICKUP_ROUTE_REACHABLE && q->state.frameValid
        && q->state.frame!=conditions->frame.world.frame
        && NextWaiting(q,world,actors,runtime)<OW_WILD_MAX_SPAWNS)
        return 0;
    if(q->valid && !Same(&q->owner,&bindings->subject,sizeof(q->owner))) {
        u8 priority=0;
        if(q->owner.slot<OW_WILD_MAX_SPAWNS) {
            const OverworldTargetBindingsState *owner=&conditions->bindings[q->owner.slot];
            if(Same(&q->owner,&owner->subject,sizeof(q->owner))
                && (owner->bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags&OVERWORLD_TARGET_BINDING_BOUND)
                && !(runtime->throwState.targets[q->owner.slot]&OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG)) {
                const OverworldActorStateSnapshot *old=&actors->slots[q->owner.slot].snapshot;
                const OverworldTargetBinding *interest=&bindings->bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST];
                /* A current follower's explicit Interest search can replace
                 * an unfinished Wild search, never an owned pickup/move. */
                u8 idle=Unclaimed(world,actors,owner,runtime);
                priority=idle && (((q->cached.status==LIMIT || q->cached.status==UNREACHABLE)
                    && Unclaimed(world,actors,bindings,runtime))
                    || (call->options->usesBinding==OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST
                    && actors->slots[world->slot].snapshot.role==OVERWORLD_ACTOR_ROLE_FOLLOWER
                    && CurrentActor(world,actors,&bindings->subject)
                    && world->subjectObject==world->state->spawns[world->slot].object
                    && interest->target.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
                    && (call->eligibleActorMask&(1u<<interest->target.actor.slot))
                    && old->role==OVERWORLD_ACTOR_ROLE_WILD
                    && CurrentActor(world,actors,&q->owner)
                    && CurrentTarget(world,actors,&conditions->frame.world,
                        &owner->bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST])
                    ));
                if(q->cached.status==OVERWORLD_PICKUP_ROUTE_REACHABLE) {
                    q->waitingMask|=1u<<world->slot;
                    priority=q->state.frameValid && q->state.frame!=conditions->frame.world.frame
                        && NextWaiting(q,world,actors,runtime)==world->slot;
                }
                if(!priority) return 0;
            }
        }
        q->waitingMask&=~(1u<<world->slot);
        Restart(q);
    }
    return 1;
}

static NativeQuery *AcquireQuery(const OverworldCargoQueryWildCall *call)
{
    OverworldWildOverlayRuntimeState *runtime=call->world->state->movementRuntimeState;
    NativeQuery *q=runtime->pickupQuery;
    if (q!=NULL) return q;
    if (call->allocate==NULL || call->freeSize==NULL
        || call->freeSize(call->heapId)<sizeof(*q)+OVERWORLD_FIELD_PICKUP_QUERY_HEAP_RESERVE) return NULL;
    q=call->allocate(call->heapId,sizeof(*q));if(q==NULL) return NULL;
    memset(q,0,sizeof(*q));q->storage.workspace=(OverworldPickupRouteWorkspace){
        q->storage.nodes,q->storage.edges,q->storage.visited,
        OVERWORLD_CARGO_QUERY_NODES,OVERWORLD_CARGO_QUERY_EDGES,OVERWORLD_CARGO_QUERY_HASH,0};
    OverworldCargoQuery_Init(&q->state,&q->storage);runtime->pickupQuery=q;return q;
}
static u8 EntryCurrent(void *raw,const OverworldEntryRouteRequest *r)
{
    NativeQuery *q=raw;const OverworldPickupRouteWildWorld *world=&q->entry.world;
    if (world->state==NULL || world->field==NULL || world->state->movementRuntimeState==NULL
        || world->state->movementFieldSystem!=world->field || r->slot>=OW_WILD_MAX_SPAWNS
        || r->slot==OW_WILD_FOLLOWER_SLOT || !r->serial) return 0;
    const OverworldActorSystemState *actors=world->ops->actorState();
    OverworldWildOverlayRuntimeState *runtime=world->state->movementRuntimeState;
    if (actors==NULL || actors->fieldEpoch!=r->fieldEpoch || actors->mapGeneration!=r->mapGeneration)
        return 0;
    if (r->operation==OVERWORLD_ENTRY_ROUTE_PREPARE) {
        return runtime->queuedSpawnSlotPlusOne==r->slot+1
            && runtime->queuedSpawnSerial==r->serial
            && !world->state->spawns[r->slot].active
            && !actors->slots[r->slot].snapshot.active
            && actors->slots[r->slot].snapshot.handle.generation==r->expectedSlotGeneration
            && Same(&q->prepared,&runtime->queuedSpawn,sizeof(q->prepared));
    }
    return CurrentActor(world,actors,&r->actor)
        && world->subjectObject==world->state->spawns[r->slot].object
        && world->state->movementSpawnRunActive[r->slot]==OW_WILD_SPAWN_ENTRY_MOVE
        && world->state->movementSpawnRunTargetX[r->slot]==r->destination.x
        && world->state->movementSpawnRunTargetY[r->slot]==r->destination.y
        && EntryPath(q,r->slot)->serial==r->serial;
}
/* A consumed or cancelled queue cannot retain the sole Field workspace.
 * Test the old exact owner before arbitration; never clear a current owner. */
static void DiscardStaleEntry(NativeQuery *q)
{
    if (q->entry.active && !EntryCurrent(q,&q->entry.receipt)) {
        q->entry.active=0;Restart(q);
    }
}
static u8 EntryRootMemoCurrent(NativeQuery *q,u32 scope,u32 policy,
    const OverworldPickupRoutePosition *root)
{
    q->state.query.dynamicRevision=q->dynamicRevision;
    OverworldCargoQueryInput observed={0};observed.changedTiles=q->changed;
    observed.changedTileCount=q->changeCount;observed.changesComplete=q->changesComplete;
    if (!OverworldCargoQuery_ObserveChanges(&q->state,&observed)) return 0;
    OverworldEntryRouteMemo *m=&q->entry.memo;
    if (m->valid && (m->scope!=scope || m->policy!=policy
            || !Same(&m->from,root,sizeof(*root))
            || !OverworldCargoQuery_Unchanged(&q->state,root,root,m->dynamic))) {
        const OverworldPickupRouteNativeSeams *native=m->native;
        OverworldEntryRoute_ResetMemo(&q->entry);m=&q->entry.memo;m->native=native;
    }
    m->valid=1;m->from=*root;m->scope=scope;m->policy=policy;m->dynamic=q->dynamicRevision;
    q->changeCount=0;q->changesComplete=1;return 1;
}
static OverworldPickupRouteStatus EntryTick(const OverworldCargoQueryWildCall *call,
    OverworldCargoQueryResult *result,u8 *publish)
{
    *publish=0;
    const OverworldEntryRouteCommand *command=call->entry;
    OverworldPickupRouteWildWorld *world=call->world;
    if (command==NULL || command->receipt==NULL || call->heapId!=OVERWORLD_FIELD_QUERY_HEAP_ID || call->operationReserved[0]
        || call->operationReserved[1] || command->reserved || command->accepted>1
        || command->usableIdle>1 || command->safelyOffscreen>1
        || command->request.version!=OVERWORLD_ENTRY_ROUTE_VERSION
        || command->request.size!=sizeof(command->request)
        || command->request.operation>OVERWORLD_ENTRY_ROUTE_RETIRE
        || command->request.slot!=world->slot || world->slot>=OW_WILD_MAX_SPAWNS
        || world->slot==OW_WILD_FOLLOWER_SLOT || world->state==NULL
        || world->state->movementRuntimeState==NULL || world->ops==NULL
        || world->version!=OVERWORLD_PICKUP_ROUTE_WILD_VERSION || world->size!=sizeof(*world)
        || world->ops->version!=OVERWORLD_PICKUP_ROUTE_WILD_VERSION || world->ops->size!=sizeof(*world->ops)
        || world->ops->actorState==NULL) return INVALID;
    OverworldEntryRouteReceipt *out=command->receipt;
    *out=(OverworldEntryRouteReceipt){0};out->version=OVERWORLD_ENTRY_ROUTE_VERSION;out->size=sizeof(*out);
    out->serial=command->request.serial;out->status=PENDING;
    OverworldWildOverlayRuntimeState *runtime=world->state->movementRuntimeState;
    const OverworldActorSystemState *actors=world->ops->actorState();
    if (actors==NULL) return out->status=INVALID;
    const OverworldEntryRouteRequest *request=&command->request;
    /* The caller may borrow an uninitialized stack receipt. Only a current
     * queued owner may publish an initialized PREPARE or ADOPT reply. */
    if (request->operation<=OVERWORLD_ENTRY_ROUTE_ADOPT
        && (world->field==NULL || world->state->movementFieldSystem!=world->field
            || !request->serial || runtime->queuedSpawnSerial!=request->serial
            || actors->fieldEpoch!=request->fieldEpoch || actors->mapGeneration!=request->mapGeneration))
        return out->status=INVALID;
    if (request->operation==OVERWORLD_ENTRY_ROUTE_PREPARE) {
        if (runtime->queuedSpawnSlotPlusOne!=request->slot+1
            || world->state->spawns[request->slot].active || actors->slots[request->slot].snapshot.active
            || actors->slots[request->slot].snapshot.handle.generation!=request->expectedSlotGeneration)
            return out->status=INVALID;
        *publish=1; /* Authentic owner also publishes finite resource/route failure. */
    }
    NativeQuery *q=AcquireQuery(call);if (q==NULL) return out->status=LIMIT;
    OverworldEntryRoutePath *path=EntryPath(q,world->slot);
    if (request->operation==OVERWORLD_ENTRY_ROUTE_RETIRE) {
        if (path->valid && Same(&path->actor,&request->actor,sizeof(request->actor)))
            *path=(OverworldEntryRoutePath){0};
        if (q->entry.active && q->entry.receipt.slot==request->slot
            && q->entry.receipt.serial==request->serial) { q->entry.active=0;Restart(q); }
        return out->status=OVERWORLD_PICKUP_ROUTE_REACHABLE;
    }
    if (request->operation==OVERWORLD_ENTRY_ROUTE_ADOPT) {
        OverworldPickupRoutePosition pose;
        if (!path->valid || path->serial!=request->serial || runtime->queuedSpawnSerial!=request->serial
            || !CurrentActor(world,actors,&request->actor)
            || world->subjectObject!=world->state->spawns[world->slot].object
            || world->subjectObject->xCurr!=path->origin.x || world->subjectObject->yCurr!=path->origin.y
            || (s32)world->subjectObject->posVec[1]!=path->origin.baseY) return out->status=INVALID;
        *publish=1; /* ADOPT consumed the queued slot; exact path/Actor/origin proves ownership. */
        pose=path->origin;path->actor=request->actor;path->expected=pose;path->noProgress=0;
        q->entryLifeUpdates=0;
        if(q->entry.active && q->entry.receipt.serial==path->serial) { q->entry.active=0;Restart(q); }
        /* Constructor/render flags are checked before path ownership. A
         * changed physical policy cannot inherit the pre-actor proof. */
        if ((world->subjectObject->flags&((1u<<23)|(1u<<29)))
                !=(request->physical.flags&((1u<<23)|(1u<<29)))
            || (world->subjectObject->flags2&(1u<<2))!=(request->physical.flags2&(1u<<2))
            || world->subjectObject->xrange!=request->physical.rangeX
            || world->subjectObject->yrange!=request->physical.rangeY) path->policy=0;
        out->actor=path->actor;out->origin=pose;out->target=path->target;
        return out->status=OVERWORLD_PICKUP_ROUTE_REACHABLE;
    }
    OverworldPickupRoutePosition currentPose=request->origin;
    if (request->operation==OVERWORLD_ENTRY_ROUTE_GUIDE) {
        if (!path->valid || path->serial!=request->serial
            || path->target.x!=request->destination.x || path->target.y!=request->destination.y
            || !Same(&path->actor,&request->actor,sizeof(request->actor))
            || !CurrentActor(world,actors,&request->actor)) return out->status=INVALID;
        const OverworldActorRuntimeSlot *slot=&actors->slots[world->slot];
        if (command->accepted) {
            if (slot->snapshot.commitSequence-command->startCommitSequence>1) return out->status=INVALID;
            path->accepted=1;path->acceptedSequence=command->startCommitSequence;
            if(q->entry.active && q->entry.receipt.serial==path->serial) { q->entry.active=0;Restart(q); }
            return out->status=OVERWORLD_PICKUP_ROUTE_REACHABLE;
        }
        if (slot->snapshot.motionPhase!=OVERWORLD_ACTOR_PHASE_IDLE || slot->snapshot.reservationId)
            return PENDING;
        LocalMapObject *object=world->subjectObject;
        if (object==NULL || object->xCurr!=slot->snapshot.logicalX || object->yCurr!=slot->snapshot.logicalY
            || object->posVec[0]!=((u32)(u16)object->xCurr<<16)+0x8000
            || object->posVec[2]!=((u32)(u16)object->yCurr<<16)+0x8000) return PENDING;
        currentPose=(OverworldPickupRoutePosition){object->xCurr,object->yCurr,(s32)object->posVec[1],
            slot->policy.targetSurfaceId,0};
        if (OverworldEntryRoute_Confirm(path,&request->actor,&currentPose,slot)) q->entryLifeUpdates=0;
        if (path->lastIdleFrame!=actors->frame) {
            path->lastIdleFrame=actors->frame;
            if (OverworldEntryRoute_IdleStall(path,&request->actor,
                    command->usableIdle,command->safelyOffscreen)) {
                out->actor=path->actor;out->queued=2;
                return out->status=UNREACHABLE;
            }
        }
        if (Same(&currentPose,&path->target,sizeof(currentPose))) {
            out->actor=path->actor;out->target=path->target;return out->status=OVERWORLD_PICKUP_ROUTE_REACHABLE;
        }
    }
    /* Arrival/lifecycle caller may inspect only the authentic full endpoint.
     * It cannot start or resolve a new traversal without a profile. */
    if (request->operation==OVERWORLD_ENTRY_ROUTE_GUIDE && call->profile==NULL) return PENDING;
    DiscardStaleEntry(q);
    /* One Field-owned traversal at a time. A different live entry waits;
     * Cargo does not clear it. It is finite even when support stays unknown. */
    if (q->entry.active && (q->entry.receipt.slot!=request->slot
            || q->entry.receipt.serial!=request->serial)) return PENDING;
    if (!q->entry.active) {
        if (request->operation==OVERWORLD_ENTRY_ROUTE_PREPARE)
            q->prepared=runtime->queuedSpawn; /* Runtime owns the packet before caller frees. */
        Restart(q);q->entry=(OverworldEntryRouteSearch){0};q->entry.active=1;
        if(request->operation!=OVERWORLD_ENTRY_ROUTE_PREPARE && call->profile!=NULL) q->entryProfile=*call->profile;
        q->entry.receipt=*request;q->entry.world=*world;q->entry.physical=request->physical;
        q->entry.world.preparedPhysical=request->operation==OVERWORLD_ENTRY_ROUTE_PREPARE?&q->entry.physical:NULL;
        q->entry.world.entryMemo=&q->entry.memo;q->entryRootReady=0;q->entryFrameValid=0;
        q->entry.current=EntryCurrent;q->entry.owner=q;
        q->entry.memo.native=OverworldPickupRouteWild_GetSeams(&q->entry.world);q->entry.memo.valid=1;
        if (q->entry.memo.native==NULL) { q->entry.active=0;return out->status=INVALID; }
    }
    if (!EntryCurrent(q,&q->entry.receipt)) { q->entry.active=0;Restart(q);return out->status=INVALID; }
    if(request->operation==OVERWORLD_ENTRY_ROUTE_GUIDE && (call->profile==NULL
            || !Same(call->profile,&q->entryProfile,sizeof(q->entryProfile)))) {
        q->entry.active=0;Restart(q);return PENDING;
    }
    if (q->entryFrameValid && q->entryFrame==actors->frame) return PENDING;
    q->entryFrame=actors->frame;q->entryFrameValid=1;
    /* Scope/support may stay unavailable before the graph can begin. The
     * owner-age survives a same-trip re-root and resets only on actual END. */
    if (q->entryLifeSerial!=request->serial || q->entryLifeSlot!=request->slot) {
        q->entryLifeSerial=request->serial;q->entryLifeSlot=request->slot;
        q->entryLifeUpdates=0;q->entryLifeFrameValid=0;
    }
    if (!q->entryLifeFrameValid || q->entryLifeFrame!=actors->frame) {
        q->entryLifeFrame=actors->frame;q->entryLifeFrameValid=1;
        if (q->entryLifeUpdates<=OVERWORLD_ENTRY_ROUTE_MAX_UPDATES) q->entryLifeUpdates++;
    }
    if (q->entryLifeUpdates>OVERWORLD_ENTRY_ROUTE_MAX_UPDATES) {
        q->entry.active=0;Restart(q);return out->status=LIMIT;
    }
    if (!Observe(q,call,actors,actors->frame) || !Scope(world,q)) {
        /* An unavailable world ends this proof. A later reload of the same
         * slot indexes must not replay pre-unload terrain or support. */
        q->entry.active=0;Restart(q);return PENDING;
    }
    OverworldCargoQueryWildCall local=*call;local.world=&q->entry.world;
    if (request->operation==OVERWORLD_ENTRY_ROUTE_PREPARE) local.profile=&q->prepared.behaviorResolution.profile;
    else local.profile=&q->entryProfile;
    OverworldPickupRouteNativePolicy policy;
    if (!Policy(q,&local,&policy)) { q->entry.active=0;return out->status=LIMIT; }
    if (!q->entryRootReady) {
        if (++q->entry.updates>OVERWORLD_ENTRY_ROUTE_MAX_UPDATES) {
            q->entry.active=0;Restart(q);return out->status=LIMIT;
        }
        OverworldPickupRoutePosition root=request->operation==OVERWORLD_ENTRY_ROUTE_GUIDE
            ?currentPose:request->destination;
        if (!EntryRootMemoCurrent(q,q->scopeRevision,q->policyRevision,&root)) {
            q->entry.active=0;Restart(q);return out->status=INVALID;
        }
        q->entry.memo.cursor=0;q->entry.memo.budget=8;q->entry.memo.used=0;
        q->entry.memo.physicalPlayerMask=policy.playerTerrainMask;
        OverworldPickupRouteNativeLandingCall landing={0};
        landing.version=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;landing.size=sizeof(landing);
        landing.policy=&policy;landing.seams=OverworldEntryRoute_MemoSeams();landing.world=&q->entry.world;
        landing.origin=root;
        landing.targetX=landing.origin.x;landing.targetY=landing.origin.y;OverworldPickupRoutePosition target;landing.destination=&target;
        OverworldPickupRouteEdgeResult decision=OverworldPickupRouteNative_Landing(&landing);
        out->readsUsed=q->entry.memo.used;
        if (decision==DEFERRED) return PENDING;
        if (decision!=LEGAL) { q->entry.active=0;Restart(q);return out->status=decision==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED?UNREACHABLE:INVALID; }
        OverworldEntryRouteRequest bound=*request;
        if (request->operation==OVERWORLD_ENTRY_ROUTE_GUIDE) {
            bound.origin=target;bound.destination=path->target;
        } else bound.destination=target;
        /* Copy before Begin clears its destination state. */
        OverworldPickupRouteWildWorld owned=q->entry.world;
        OverworldPickupRouteStatus status=OverworldEntryRoute_Begin(&q->entry,&bound,&owned,&policy,
            &q->state,q->edges,q->edgeCount,&q->bounds,q->scopeRevision,q->policyRevision,q->dynamicRevision,
            EntryCurrent,q);
        q->entryRootReady=1;
        if (status!=PENDING) { q->entry.active=0;Restart(q);return out->status=status; }
        return PENDING; /* No route search on final root read update. */
    }
    if (q->entry.query.scopeRevision!=q->scopeRevision
        || q->entry.query.movementPolicyRevision!=q->policyRevision) {
        q->entry.active=0;Restart(q);return PENDING; /* Next usable update re-roots same owner. */
    }
    /* Motion policy stores its last destination surface, not standing
     * support. The root landing already resolved current support under this
     * exact scope/policy. Each saved edge still rechecks source and target. */
    if (request->operation==OVERWORLD_ENTRY_ROUTE_GUIDE
        && Same(&currentPose,&q->entry.query.origin,8))
        currentPose.surfaceId=q->entry.query.origin.surfaceId;
    if (request->operation==OVERWORLD_ENTRY_ROUTE_GUIDE && path->valid
        && path->scope==q->scopeRevision && path->policy==q->policyRevision
        && Same(&currentPose,&path->expected,sizeof(currentPose)) && path->next<path->count) {
        OverworldPickupRouteStatus status=OverworldEntryRoute_ValidateStep(&q->entry,path,q->dynamicRevision,
            q->changed,q->changeCount,q->changesComplete,out);
        q->changeCount=0;q->changesComplete=1;
        if(status==OVERWORLD_PICKUP_ROUTE_REACHABLE) {
            result->route.subject=request->actor;result->route.origin=path->expected;
            result->route.nextStep=out->nextStep;result->route.edgeTag=out->edgeTag;result->route.hasNextStep=1;
        } else if(status!=PENDING) { q->entry.active=0;path->policy=0;Restart(q); }
        return out->status=status;
    }
    OverworldPickupRouteStatus status=OverworldEntryRoute_Resume(&q->entry,q->dynamicRevision,
        q->changed,q->changeCount,q->changesComplete,path,out);
    q->changeCount=0;q->changesComplete=1;
    if (status!=PENDING && !(request->operation==OVERWORLD_ENTRY_ROUTE_PREPARE
            && status==OVERWORLD_PICKUP_ROUTE_REACHABLE)) { q->entry.active=0;Restart(q); }
    result->status=status;return status;
}

/* As in the portable Cargo reducer, keep GCC's forward propagation from
 * expanding this packed-view Tick beyond the fixed query image. */
#if defined(__GNUC__) && !defined(__clang__)
__attribute__((optimize("no-tree-forwprop")))
#endif
OverworldPickupRouteStatus OverworldCargoQueryWild_Tick(
    const OverworldCargoQueryWildCall *call,OverworldCargoQueryResult *result)
{
    if(result==NULL) return INVALID;
    *result=(OverworldCargoQueryResult){0};result->status=PENDING;
    if(call==NULL || call->world==NULL) return INVALID;
    if(call->routeOperation==OVERWORLD_FIELD_ROUTE_ENTRY) {
        if(call->entry!=NULL && call->entry->nativeControl!=NULL)
            return OverworldEntryRoute_NativeControl(call,result);
        u8 publish;
        OverworldPickupRouteStatus status=EntryTick(call,result,&publish);
        /* Rejected borrowed calls and live GUIDE/RETIRE replies cannot erase
         * the current queued/adopted public serial and full Actor handle. */
        if(publish) {
            OverworldWildOverlayRuntimeState *runtime=call->world->state->movementRuntimeState;
            runtime->entryRouteReceipt=*call->entry->receipt;
        }
        result->status=status;return status;
    }
    if(call->profile==NULL || call->reserved[0] || call->reserved[1] || call->reserved[2]) return INVALID;
    OverworldPickupRouteWildWorld *world=call->world;
    if(world->state==NULL || world->state->movementRuntimeState==NULL
        || world->slot>=OW_WILD_MAX_SPAWNS) return INVALID;
    OverworldWildOverlayRuntimeState *runtime=world->state->movementRuntimeState;
    OverworldWildBehaviorConditionRuntime *conditions=runtime->conditions;
    const OverworldActorSystemState *actors=world->ops->actorState();
    if(conditions==NULL || !conditions->frame.valid || actors==NULL
        || conditions->frame.world.actorCount>OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS) return INVALID;
    NativeQuery *q=runtime->pickupQuery;
    if(q!=NULL) q->waitingMask&=~(1u<<world->slot);
    if(call->options==NULL) {
        if(q!=NULL && q->owner.slot==world->slot) Restart(q);
        return INVALID;
    }
    const OverworldTargetBindingsState *bindings=&conditions->bindings[world->slot];
    if(!(bindings->bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags&OVERWORLD_TARGET_BINDING_BOUND)
        || bindings->subject.slot!=world->slot) return Pending(call,actors,conditions,result);
    u8 interval=OW_WILD_BEHAVIOR_CARGO_TARGET_CHECK_INTERVAL(call->profile->owner.continueWhenArrived);
    u8 nearest=interval && actors->slots[world->slot].snapshot.role==OVERWORLD_ACTOR_ROLE_WILD
        && !(runtime->throwState.targets[world->slot]&OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG);
    if(!CurrentTarget(world,actors,&conditions->frame.world,
            &bindings->bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST])
        || (!nearest && (bindings->bindings[OVERWORLD_TARGET_BINDING_CARGO].flags&OVERWORLD_TARGET_BINDING_BOUND)
            && !CurrentTarget(world,actors,&conditions->frame.world,
                &bindings->bindings[OVERWORLD_TARGET_BINDING_CARGO]))) {
        result->status=INVALID;return INVALID;
    }
    /* A busy workspace cannot make an unavailable Cargo worth waiting for.
     * Use ELIGIBLE, which includes moving targets, before owner arbitration.
     * This read neither takes another owner's route nor spends native work. */
    const OverworldTargetBinding *interest=&bindings->bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST];
    const OverworldTargetBinding *boundCargo=&bindings->bindings[OVERWORLD_TARGET_BINDING_CARGO];
    u16 candidates=0;
    for(u8 n=0;n<conditions->frame.world.actorCount;n++) {
        const OverworldBehaviorConditionActorObservation *actor=&conditions->frame.world.actors[n];
        if(actor->valid && actor->actor.slot<OW_WILD_MAX_SPAWNS
            && actor->actor.slot!=world->slot
            && (call->eligibleActorMask&(1u<<actor->actor.slot)))
            candidates|=1u<<actor->actor.slot;
    }
    if(interest->target.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR)
        candidates=call->options->usesBinding==OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST
            ?candidates&(1u<<interest->target.actor.slot)
            :candidates&~(1u<<interest->target.actor.slot);
    if((call->options->usesBinding==OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST
            && (interest->target.kind!=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR || !candidates))
        || (!nearest && (boundCargo->flags&OVERWORLD_TARGET_BINDING_BOUND)
            && (boundCargo->target.kind!=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
                || !(candidates&(1u<<boundCargo->target.actor.slot))))) {
        result->status=INVALID;return INVALID;
    }
    if(!candidates) { result->status=UNREACHABLE;return UNREACHABLE; }
    if(q==NULL) { q=AcquireQuery(call);if(q==NULL) return LIMIT; }
    DiscardStaleEntry(q);
    if(q->entry.active) return Pending(call,actors,conditions,result);
    if(!QueryTurn(q,call,actors)) return Pending(call,actors,conditions,result);
    if(nearest && (!q->state.frameValid || q->state.frame!=conditions->frame.world.frame)
        && (!boundCargo->flags || q->checkingTargets
            || !CurrentTarget(world,actors,&conditions->frame.world,boundCargo)
            || (u32)(conditions->frame.world.frame-q->targetCheckFrame)>=interval)) {
        if(!q->checkingTargets) {
            Restart(q);
            q->checkingTargets=1;
        }
    }
    if(q->valid && (q->cached.status==LIMIT || q->cached.status==UNREACHABLE)) {
        if(q->state.frameValid && q->state.frame==conditions->frame.world.frame) {
            *result=q->cached;return q->cached.status;
        }
        if(Unclaimed(world,actors,bindings,runtime)) Restart(q);
    }
    /* Retain the new owner even when native scope/position is not ready yet. */
    q->owner=bindings->subject;q->valid=1;
    if(!Observe(q,call,actors,conditions->frame.world.frame) || !Scope(world,q))
        return Pending(call,actors,conditions,result);
    OverworldBehaviorConditionWorldView view=conditions->frame.world;
    view.subject=bindings->subject;
    view.subjectX=world->subjectObject->xCurr;view.subjectY=world->subjectObject->yCurr;
    u8 role=actors->slots[world->slot].snapshot.role;
    view.subjectRoleMask=role==OVERWORLD_ACTOR_ROLE_FOLLOWER?2:
        role==OVERWORLD_ACTOR_ROLE_MOUNTED?4:1;
    for(u8 n=0;n<view.actorCount;n++) {
        OverworldBehaviorConditionActorObservation *observation=&view.actors[n];
        LocalMapObject *object=CurrentObservationObject(world,actors,&observation->actor);
        if(object==NULL) { observation->valid=0;continue; }
        observation->x=object->xCurr;observation->y=object->yCurr;
    }
    OverworldPickupRouteNativePolicy policy;
    if(!Policy(q,call,&policy)) return LIMIT;
    OverworldPickupRouteQuery seed={0};
    seed.version=OVERWORLD_PICKUP_ROUTE_VERSION;seed.size=sizeof(seed);
    seed.subject=bindings->subject;seed.bounds=q->bounds;
    if(Position(world,&seed.subject,&seed.origin)!=LEGAL) return Pending(call,actors,conditions,result);
    seed.scopeRevision=q->scopeRevision;seed.movementPolicyRevision=q->policyRevision;
    seed.dynamicRevision=q->dynamicRevision;seed.edges=q->edges;seed.edgeCount=q->edgeCount;
    world->scopeRevision=seed.scopeRevision;world->movementPolicyRevision=seed.movementPolicyRevision;
    world->dynamicRevision=seed.dynamicRevision;
    OverworldPickupRouteNativeContext native={0};
    native.version=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;native.size=sizeof(native);
    native.policy=&policy;native.world=world;
    OverworldCargoQueryInput input={0};
    input.version=OVERWORLD_CARGO_QUERY_VERSION;input.size=sizeof(input);
    input.runtime=&native;input.bindingsWorld=&view;input.seed=&seed;
    input.readPosition=Position;input.changedTiles=q->changed;input.changedTileCount=q->changeCount;
    input.changesComplete=q->changesComplete;
    for(u8 n=0;n<view.actorCount;n++)
        if(view.actors[n].valid && view.actors[n].actor.slot<OW_WILD_MAX_SPAWNS
            && (candidates&(1u<<view.actors[n].actor.slot)))
            input.eligibleActorMask|=1u<<n;
    const OverworldTargetBinding *objectOfInterest=&bindings->bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST];
    input.pickupDistance=call->options->pickupDistance;input.internalWork=OVERWORLD_CARGO_QUERY_INTERNAL_WORK;
    if(nearest && q->checkingTargets)
        input.selectionFlags=OVERWORLD_CARGO_QUERY_SELECT_NEAREST
            | (OW_WILD_BEHAVIOR_CARGO_TARGET_SWITCH_ADVANTAGE(call->profile->owner.continueWhenArrived)<<1);
    input.requestKey=call->options->captureBinding|((u32)call->options->pickupHeight<<8)
        |((u32)call->options->pickupDistance<<16)|((u32)call->options->usesBinding<<24);
    const OverworldTargetBinding *cargo=&bindings->bindings[OVERWORLD_TARGET_BINDING_CARGO];
    if(call->options->usesBinding==OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST) {
        if(objectOfInterest->target.kind!=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR) return INVALID;
        input.requiredCargo=&objectOfInterest->target.actor;
    }
    if(cargo->flags&OVERWORLD_TARGET_BINDING_BOUND) {
        if((!nearest && cargo->target.kind!=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR)
            || (input.requiredCargo!=NULL
                && !Same(input.requiredCargo,&cargo->target.actor,sizeof(cargo->target.actor)))) return INVALID;
        if(cargo->target.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR)
            input.requiredCargo=&cargo->target.actor;
    }
    q->owner=bindings->subject;q->valid=1;
    /* The condition observation and its admitted START can share one completed
     * frame. Reuse only that exact current receipt; never run a second search. */
    OverworldPickupRoutePosition currentCargo;
    if(q->state.frameValid && q->state.frame==view.frame
        && q->cached.status==OVERWORLD_PICKUP_ROUTE_REACHABLE
        && q->cached.eligibleActorMask!=0
        && CargoObservationMask(&view,input.eligibleActorMask,&q->cached.route.cargo)!=0
        && Same(&q->cached.route.subject,&seed.subject,sizeof(seed.subject))
        && Same(&q->cached.route.origin,&seed.origin,sizeof(seed.origin))
        && q->cached.route.scopeRevision==seed.scopeRevision
        && q->cached.route.movementPolicyRevision==seed.movementPolicyRevision
        && q->cached.route.dynamicRevision==seed.dynamicRevision
        && (input.requiredCargo==NULL
            || Same(input.requiredCargo,&q->cached.route.cargo,sizeof(seed.cargo)))
        && Position(world,&q->cached.route.cargo,&currentCargo)==LEGAL
        && Same(&currentCargo,&q->cached.route.cargoPosition,sizeof(currentCargo))) {
        *result=q->cached;
        result->eligibleActorMask=CargoObservationMask(&view,input.eligibleActorMask,&result->route.cargo);
        PublishSlotMask(result);return result->status;
    }
    OverworldPickupRouteStatus status=OverworldCargoQuery_Tick(&q->state,&input,result);
    if(status==OVERWORLD_PICKUP_ROUTE_REACHABLE && q->checkingTargets) {
        q->checkingTargets=0;q->targetCheckFrame=view.frame;
    }
    q->cached=*result;
    if(q->state.observedRevision==q->dynamicRevision) {
        q->changeCount=0;q->changesComplete=1;
    }
    PublishSlotMask(result);
    if(status==PENDING) return Pending(call,actors,conditions,result);
    return status;
}
