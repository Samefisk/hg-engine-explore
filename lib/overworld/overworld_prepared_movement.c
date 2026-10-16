#include "overworld_prepared_movement.h"
#include "overworld_actor_system_internal.h"

typedef OverworldPickupRouteEdgeResult Result;
#define LEGAL OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL
#define BLOCKED OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED
#define DEFERRED OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED
#define INVALID OVERWORLD_PICKUP_ROUTE_EDGE_INVALID

static int Abs(int value) { return value<0?-value:value; }
static Result Finish(OverworldPreparedMovementCursor *cursor, Result decision)
{
    cursor->phase=OVERWORLD_PREPARED_MOVEMENT_DONE;
    cursor->decision=decision;
    return decision;
}
Result OverworldPreparedMovement_Begin(OverworldPreparedMovementCursor *cursor)
{
    const OverworldPreparedMovementInput *input;
    int dx,dy,ax,ay,distance;
    if (cursor==NULL || cursor->version!=OVERWORLD_PREPARED_MOVEMENT_VERSION
        || cursor->size!=sizeof(*cursor) || cursor->input==NULL
        || cursor->reserved[0] || cursor->reserved[1]) return INVALID;
    input=cursor->input;
    cursor->readsUsed=0;
    cursor->direction=0;
    cursor->heightType=0;
    cursor->phase=OVERWORLD_PREPARED_MOVEMENT_DONE;
    cursor->decision=INVALID;
    if (input->version!=OVERWORLD_PREPARED_MOVEMENT_VERSION || input->size!=sizeof(*input)
        || (input->profile==NULL)!=(input->lane==NULL)
        || (input->kind!=OVERWORLD_PICKUP_ROUTE_NATIVE_WALK && input->profile==NULL)
        || input->field==NULL || input->ops==NULL
        || input->ops->version!=OVERWORLD_PICKUP_ROUTE_WILD_VERSION || input->ops->size!=sizeof(*input->ops)
        || input->reserved || input->allowObjectOfInterestDestination>1
        || input->from.reserved || input->to.reserved || input->source.reserved || input->target.reserved
        || (input->source.flags&~7u) || (input->target.flags&~7u)
        || input->from.x<0 || input->from.y<0 || input->to.x<0 || input->to.y<0
        || (input->kind!=OVERWORLD_PICKUP_ROUTE_NATIVE_WALK
            && input->kind!=OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE
            && input->kind!=OVERWORLD_PREPARED_MOVEMENT_TELEPORT)) return INVALID;
    dx=input->to.x-input->from.x;dy=input->to.y-input->from.y;
    ax=Abs(dx);ay=Abs(dy);distance=ax>ay?ax:ay;
    if (!distance || (ax && ay && ax!=ay)) return Finish(cursor,BLOCKED);
    if (input->source.behavior==0xFF || input->target.behavior==0xFF) return Finish(cursor,DEFERRED);
    if (input->kind==OVERWORLD_PREPARED_MOVEMENT_TELEPORT) {
        /* Spawn entry uses the shared ADJACENT Teleport planner: any native
         * cardinal/45 heading, segment1..6, no crossed-tile terrain probes.
         * The parent classifier still owns its full legal endpoint. */
        return Finish(cursor,distance<=6?LEGAL:BLOCKED);
    }
    if (!input->directions || (input->directions&~3u)) return INVALID;
    if (((!ax || !ay) && !(input->directions&OVERWORLD_PICKUP_ROUTE_NATIVE_CARDINAL))
        || ((ax && ay) && !(input->directions&OVERWORLD_PICKUP_ROUTE_NATIVE_DIAGONAL))) return Finish(cursor,BLOCKED);
    if ((input->kind==OVERWORLD_PICKUP_ROUTE_NATIVE_WALK && distance!=1)
        || (input->kind==OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE && (distance!=2 || (ax && ay)))) return Finish(cursor,BLOCKED);
    cursor->direction=dx?2+(dx>0):(dy>0);
    if (input->kind==OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE) {
        if (input->ops->behavior==NULL || input->ops->occupancy==NULL || input->blockedTerrain==NULL) return INVALID;
        cursor->phase=OVERWORLD_PREPARED_MOVEMENT_LEDGE_BEHAVIOR;
    } else {
        /* Existing custom diagonal Walk relies on the parent's side guards;
         * its real START has no stock cardinal range/direction/height test. */
        if (ax && ay) return Finish(cursor,LEGAL);
        if (input->ops->walkHeight==NULL || input->blockedTerrain==NULL
            || input->ops->behavior==NULL || input->ops->sourceDirectionBlocks==NULL
            || input->ops->targetDirectionBlocks==NULL
            || input->ops->sourceDirectionBlocks[cursor->direction]==NULL
            || input->ops->targetDirectionBlocks[cursor->direction]==NULL) return INVALID;
        dx=input->to.x-input->anchorX;dy=input->to.y-input->anchorY;
        if (((input->target.flags&OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_PLAYER)
                && !((input->target.flags&OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_OBJECT_OF_INTEREST)
                    && input->allowObjectOfInterestDestination))
            || (input->rangeX!=-1 && Abs(dx)>input->rangeX)
            || (input->rangeY!=-1 && Abs(dy)>input->rangeY)) return Finish(cursor,BLOCKED);
        cursor->phase=OVERWORLD_PREPARED_MOVEMENT_WALK_HEIGHT;
    }
    return DEFERRED;
}
Result OverworldPreparedMovement_Step(OverworldPreparedMovementCursor *cursor)
{
    const OverworldPreparedMovementInput *input;
    if (cursor==NULL || cursor->version!=OVERWORLD_PREPARED_MOVEMENT_VERSION
        || cursor->size!=sizeof(*cursor) || cursor->input==NULL
        || cursor->reserved[0] || cursor->reserved[1]
        || cursor->readBudget>OVERWORLD_PREPARED_MOVEMENT_MAX_READS
        || cursor->phase<OVERWORLD_PREPARED_MOVEMENT_WALK_HEIGHT
        || cursor->phase>OVERWORLD_PREPARED_MOVEMENT_DONE || cursor->direction>3) return INVALID;
    cursor->readsUsed=0;input=cursor->input;
    for (;;) {
        u8 cost=0;
        if (cursor->phase==OVERWORLD_PREPARED_MOVEMENT_DONE) return cursor->decision;
        if (cursor->phase==OVERWORLD_PREPARED_MOVEMENT_WALK_HEIGHT) cost=OVERWORLD_PREPARED_MOVEMENT_WALK_HEIGHT_READS;
        else if (cursor->phase==OVERWORLD_PREPARED_MOVEMENT_WALK_TERRAIN
            || cursor->phase==OVERWORLD_PREPARED_MOVEMENT_WALK_BEHAVIOR
            || cursor->phase>=OVERWORLD_PREPARED_MOVEMENT_LEDGE_BEHAVIOR) cost=1;
        if (cursor->readBudget<cost) return DEFERRED;
        cursor->readBudget-=cost;cursor->readsUsed+=cost;
        if (cursor->phase==OVERWORLD_PREPARED_MOVEMENT_WALK_HEIGHT) {
            VecFx32 position={(input->from.x*16+8)<<FX32_SHIFT,input->from.baseY,(input->from.y*16+8)<<FX32_SHIFT};
            /* Use the actual stock height threshold and its signed result. */
            if (input->ops->walkHeight(input->field,&position,input->to.x,input->to.y,&cursor->heightType)) return Finish(cursor,BLOCKED);
            cursor->phase=OVERWORLD_PREPARED_MOVEMENT_WALK_TERRAIN;
        } else if (cursor->phase==OVERWORLD_PREPARED_MOVEMENT_WALK_TERRAIN) {
            if (input->blockedTerrain(input->field,input->to.x,input->to.y)) return Finish(cursor,BLOCKED);
            cursor->phase=cursor->heightType==2?OVERWORLD_PREPARED_MOVEMENT_WALK_BEHAVIOR:OVERWORLD_PREPARED_MOVEMENT_SOURCE_DIRECTION;
        } else if (cursor->phase==OVERWORLD_PREPARED_MOVEMENT_WALK_BEHAVIOR) {
            /* Stock020549A8 reads this value only for unblocked height type2
             * and discards it. Preserve that call and its order. */
            input->ops->behavior(input->field,input->to.x,input->to.y);
            cursor->phase=OVERWORLD_PREPARED_MOVEMENT_SOURCE_DIRECTION;
        } else if (cursor->phase==OVERWORLD_PREPARED_MOVEMENT_SOURCE_DIRECTION) {
            if (input->objectFlags2&(1u<<2)) return Finish(cursor,LEGAL);
            if (input->ops->sourceDirectionBlocks[cursor->direction](input->source.behavior)==TRUE) return Finish(cursor,BLOCKED);
            cursor->phase=OVERWORLD_PREPARED_MOVEMENT_TARGET_DIRECTION;
        } else if (cursor->phase==OVERWORLD_PREPARED_MOVEMENT_TARGET_DIRECTION) {
            return Finish(cursor,input->ops->targetDirectionBlocks[cursor->direction](input->target.behavior)==TRUE?BLOCKED:LEGAL);
        } else if (cursor->phase==OVERWORLD_PREPARED_MOVEMENT_LEDGE_BEHAVIOR) {
            int x=(input->from.x+input->to.x)/2,y=(input->from.y+input->to.y)/2;
            int behavior=input->ops->behavior(input->field,x,y);
            if (behavior==0xFF) return Finish(cursor,DEFERRED);
            /* Exact current Wild ledge rule. A non-ledge blocked-obstacle Hop
             * remains a distinct turn/vertical-obstacle capability, not this
             * jumpLevel-ledged edge. Its caller must prove that separate path. */
            if (!OverworldPreparedMovement_LedgeDirectionLegal(
                    input->profile->owner.jumpLevel,cursor->direction,(u8)behavior))
                return Finish(cursor,BLOCKED);
            cursor->phase=OVERWORLD_PREPARED_MOVEMENT_LEDGE_OCCUPANCY;
        } else if (cursor->phase==OVERWORLD_PREPARED_MOVEMENT_LEDGE_OCCUPANCY) {
            int x=(input->from.x+input->to.x)/2,y=(input->from.y+input->to.y)/2;
            if (input->ops->occupancy(input->field,NULL,input->collisionIgnoredObject,x,y,0,0)) return Finish(cursor,BLOCKED);
            cursor->phase=OVERWORLD_PREPARED_MOVEMENT_LEDGE_LANDING;
        } else {
            return Finish(cursor,input->blockedTerrain(input->field,input->to.x,input->to.y)?BLOCKED:LEGAL);
        }
    }
}
Result OverworldPreparedMovement_Run(const OverworldPreparedMovementInput *input)
{
    OverworldPreparedMovementCursor cursor={0};
    Result decision;
    cursor.version=OVERWORLD_PREPARED_MOVEMENT_VERSION;cursor.size=sizeof(cursor);cursor.input=input;
    decision=OverworldPreparedMovement_Begin(&cursor);
    if (decision!=DEFERRED) return decision;
    while (cursor.phase!=OVERWORLD_PREPARED_MOVEMENT_DONE) {
        cursor.readBudget=OVERWORLD_PREPARED_MOVEMENT_MAX_READS;
        decision=OverworldPreparedMovement_Step(&cursor);
    }
    return decision;
}
