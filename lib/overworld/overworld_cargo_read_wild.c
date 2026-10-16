#include "../../include/overworld_cargo_read_wild.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_runtime_state_internal.h"
#include "../../include/overworld_pickup_reach.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_condition_moving_notice_native.h"
#include "../../include/overworld_throw_held_wild.h"
/* Image-local identity comparison, shared with the route and Cargo reducers. */
extern u8 OverworldPickupRoute_EqualValues(const void *,const void *,u8)
    __attribute__((short_call,pure));

const OverworldWildBehaviorConditionOptions *OverworldCargoReadWild_Options(
    const OverworldPickupRouteWildWorld *world)
{
    OverworldWildSpawnState *state=world->state;
    u8 slot=world->slot;
    const OverworldWildBehaviorDataBlob *blob=world->behaviorData;
    OverworldWildBehaviorConditionRuntime *conditions;
    OverworldTargetBinding *cargo;
    const OverworldActorSystemState *actors;
    u8 role, roleMask;
    if (state==NULL || state->movementRuntimeState==NULL || slot>=OW_WILD_MAX_SPAWNS
        || blob==NULL || world->ops==NULL || world->ops->actorState==NULL
        || (conditions=((OverworldWildOverlayRuntimeState *)state->movementRuntimeState)->conditions)==NULL
        || (actors=world->ops->actorState())==NULL) return NULL;
    role=actors->slots[slot].snapshot.role;
    roleMask=role==OVERWORLD_ACTOR_ROLE_FOLLOWER?2:role==OVERWORLD_ACTOR_ROLE_MOUNTED?4:1;
    cargo=&conditions->bindings[slot].bindings[OVERWORLD_TARGET_BINDING_CARGO];
    for (u8 i=0;i<conditions->actors[slot].count;i++) {
        u16 index=conditions->actors[slot].catalogEntryIndexes[i];
        const OverworldWildBehaviorConditionOptions *options;
        if (index>=blob->header.conditionEntryCount) return NULL;
        options=&blob->conditionOptions[index];
        if (options->captureBinding!=2 || !options->mustBeReachableForPickup
            || !OverworldBehaviorCondition_RoleApplies(options->subjectRoleMask,roleMask)) continue;
        if ((cargo->flags&OVERWORLD_TARGET_BINDING_BOUND)
            && blob->conditionEntries[index].conditionId!=cargo->sourceConditionId) continue;
        return options;
    }
    return NULL;
}

OverworldPickupRouteEdgeResult OverworldCargoReadWild_Reach(void *raw,
    const OverworldPickupRoutePosition *standing,const OverworldPickupRoutePosition *cargo)
{
    const OverworldWildBehaviorConditionOptions *options=OverworldCargoReadWild_Options(raw);
    return options!=NULL?OverworldPickupReach_Check(standing,cargo,
        options->pickupDistance,options->pickupHeight):OVERWORLD_PICKUP_ROUTE_EDGE_INVALID;
}

OverworldPickupRouteStatus OverworldCargoReadWild_Route(
    const OverworldCargoQueryWildCall *input, OverworldCargoQueryResult *result)
{
    OverworldCargoQueryWildCall call=*input;
    call.options=OverworldCargoReadWild_Options(call.world);
    return OverworldCargoQueryWild_Tick(&call,result);
}

__attribute__((section(".query_native_observation")))
u32 OverworldCargoReadWild_Observe(
    const OverworldCargoReadWildObservationCall *input, BOOL *needAbort)
{
    const OverworldCargoQueryWildCall *call=&input->cargo;
    OverworldPickupRouteWildWorld *world=call->world;
    OverworldWildBehaviorConditionRuntime *conditions=input->conditions;
    int slot=world->slot;
    /* Access is a fresh fact for this subject, before any Notice or capture.
     * This packet borrows the already validated route world; it makes no move. */
    for(u8 i=0;i<conditions->frame.world.actorCount
            && i<OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS;i++)
        conditions->frame.candidates[i].reserved[0] |=
            OVERWORLD_BEHAVIOR_CONDITION_CANDIDATE_INACCESSIBLE;
    if(call->conditionNative!=NULL) {
        OverworldConditionNativeCall access={
            .runtime=conditions,.state=world->state,.field=world->field,
            .blob=world->behaviorData,.blobSize=sizeof(*world->behaviorData),
            .allowedTerrainMask=call->allowedTerrainMask,
            .version=OVERWORLD_CONDITION_NATIVE_CALL_VERSION,.size=sizeof(access),
            .slot=(u8)slot,.operation=OVERWORLD_CONDITION_NATIVE_TARGET_ACCESS,
            .targetAccessWorld=world,
        };
        (void)call->conditionNative(&access);
    }
    u32 observation=input->throwService->observe(world->state,slot,call->profile,
        world->behaviorData,conditions,input->isCurrentSpawn,input->queryTarget);
    const OverworldActorSystemState *actors=world->ops->actorState();
    BOOL nearest=actors!=NULL && actors->slots[slot].snapshot.role==OVERWORLD_ACTOR_ROLE_WILD
        && OW_WILD_BEHAVIOR_CARGO_TARGET_CHECK_INTERVAL(call->profile->owner.continueWhenArrived)
        && !(observation&OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD);
    *needAbort=FALSE;
    if ((conditions->bindings[slot].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags
            & OVERWORLD_TARGET_BINDING_BOUND)
        && !(observation & OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID)) {
        *needAbort=TRUE;
        return 0;
    }
    if (conditions->bindings[slot].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags
            & OVERWORLD_TARGET_BINDING_BOUND) {
        OverworldTargetBindingPosition cargo;
        if (!input->throwService->bindingPosition(world->state,slot,
                OVERWORLD_TARGET_BINDING_CARGO,&cargo)) {
            if(!nearest || !OverworldThrowHeldWild_ReleaseCargo(world)) {
                *needAbort=TRUE;
                return 0;
            }
            observation&=~OVERWORLD_BEHAVIOR_ACTOR_FACT_RESERVED;
        }
    }
    if (OverworldCargoReadWild_Options(world)!=NULL
        && !(observation&OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD)) {
        OverworldCargoQueryResult route;
        OverworldCargoQueryWildCall current=*call;
        current.eligibleActorMask=(observation>>8)&((1u<<OW_WILD_MAX_SPAWNS)-1);
        OverworldPickupRouteStatus status=OverworldCargoReadWild_Route(&current,&route);
        observation&=~(((1u<<OW_WILD_MAX_SPAWNS)-1)<<8);
        if((route.flags&~OVERWORLD_CARGO_QUERY_RESULT_FLAGS)
            || (route.flags && status!=OVERWORLD_PICKUP_ROUTE_PENDING)) {
            *needAbort=TRUE;
            return 0;
        }
        if(status==OVERWORLD_PICKUP_ROUTE_PENDING
            && route.flags==OVERWORLD_CARGO_QUERY_RETAIN_BOUND_CARGO) {
            const OverworldTargetBinding *cargo=&conditions->bindings[slot].bindings[OVERWORLD_TARGET_BINDING_CARGO];
            /* This keeps one existing while-true condition. The route remains
             * PENDING with no eligible mask/next edge for START or pickup. */
            if(cargo->flags==OVERWORLD_TARGET_BINDING_BOUND
                && cargo->target.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
                && cargo->target.actor.slot<OW_WILD_MAX_SPAWNS)
                observation|=(u32)(1u<<cargo->target.actor.slot)<<8;
        } else if(status==OVERWORLD_PICKUP_ROUTE_REACHABLE) {
            const OverworldTargetBinding *cargo=&conditions->bindings[slot].bindings[OVERWORLD_TARGET_BINDING_CARGO];
            if(nearest && cargo->flags && (cargo->target.kind!=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
                || !OverworldPickupRoute_EqualValues(&cargo->target.actor,&route.route.cargo,12))) {
                if(!OverworldThrowHeldWild_ReleaseCargo(world)) { *needAbort=TRUE;return 0; }
                observation&=~OVERWORLD_BEHAVIOR_ACTOR_FACT_RESERVED;
            }
            observation|=(u32)route.eligibleActorMask<<8;
        }
        else if(status==OVERWORLD_PICKUP_ROUTE_UNREACHABLE
            || status==OVERWORLD_PICKUP_ROUTE_INVALID
            || status==OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT) {
            const OverworldWildBehaviorConditionOptions *options = OverworldCargoReadWild_Options(world);
            if(nearest && status==OVERWORLD_PICKUP_ROUTE_UNREACHABLE) {
                (void)OverworldThrowHeldWild_ReleaseCargo(world);
                return observation&~OVERWORLD_BEHAVIOR_ACTOR_FACT_RESERVED;
            }
            if ((conditions->bindings[slot].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags
                    & OVERWORLD_TARGET_BINDING_BOUND)
                || (options != NULL
                    && (options->usesBinding == OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST
                        || status == OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT
                        || status == OVERWORLD_PICKUP_ROUTE_UNREACHABLE)
                    && (conditions->bindings[slot].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags
                        & OVERWORLD_TARGET_BINDING_BOUND))) {
                *needAbort=TRUE;
                return 0;
            }
        }
    }
    return observation;
}

const OverworldActorSystemState *OverworldCargoReadWild_ActorState(
    const OverworldActorSystemEntry *entry,
    const OverworldActorSystemDebugLayout *debug,
    const OverworldActorSystemState *state)
{
    if (entry->magic!=OVERWORLD_ACTOR_SYSTEM_MAGIC
        || entry->version!=OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        || entry->size!=sizeof(*entry)
        || debug->magic!=OVERWORLD_ACTOR_SYSTEM_DEBUG_MAGIC
        || debug->version!=OVERWORLD_ACTOR_SYSTEM_DEBUG_VERSION
        || debug->size!=sizeof(*debug)
        || debug->stateAddress!=(u32)state
        || debug->stateSize!=sizeof(OverworldActorSystemState)
        || debug->actorsOffset!=offsetof(OverworldActorSystemState,slots)
        || debug->actorStride!=sizeof(OverworldActorRuntimeSlot)) return NULL;
    return state->magic==OVERWORLD_ACTOR_SYSTEM_STATE_MAGIC
        && state->version==OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        && state->size==sizeof(*state)?state:NULL;
}

/* Position and identity reads from the existing frame dispatcher. The caller
 * keeps all launch, windup, pickup, START and cleanup writes. */
u8 OverworldCargoReadWild_Target(const OverworldCargoReadWildTargetCall *call,
    OverworldCargoReadWildTarget *out)
{
    OverworldWildSpawnState *state=call->state;
    OverworldWildOverlayRuntimeState *runtime=state->movementRuntimeState;
    const OverworldWildBehaviorProfile *profile=call->profile;
    FieldSystem *field=state->movementFieldSystem;
    u8 slot=call->slot,target=call->movementTarget,relation=call->throwTarget;
    int dx,dy;
    if(target==OW_WILD_BEHAVIOR_TARGET_PLAYER_AWAY_THROW_LINE
        && !(relation&OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG)) return OVERWORLD_CARGO_READ_TARGET_NONE;
    out->objectX=(u32)call->object->xCurr;
    out->objectY=(u32)call->object->yCurr;
    out->playerX=state->movementSpawnRunActive[slot]==OW_WILD_SPAWN_ENTRY_MOVE
        ?state->movementSpawnRunTargetX[slot]:call->ops->playerX(field->playerAvatar);
    out->playerY=state->movementSpawnRunActive[slot]==OW_WILD_SPAWN_ENTRY_MOVE
        ?state->movementSpawnRunTargetY[slot]:call->ops->playerY(field->playerAvatar);
    if(state->movementSpawnRunActive[slot]!=OW_WILD_SPAWN_ENTRY_MOVE
        && (relation==OW_WILD_HELPER_THROW_TARGET_NONE
            || target==OW_WILD_BEHAVIOR_TARGET_CONDITION_ACTOR)) {
        const OverworldWildBehaviorConditionRuntime *conditions=runtime->conditions;
        if(conditions!=NULL && (conditions->targetValidMask&(1u<<slot))) {
            out->playerX=conditions->targetX[slot];out->playerY=conditions->targetY[slot];
        }
    }
    if(target==OW_WILD_BEHAVIOR_TARGET_CARGO || target==OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE) {
        OverworldTargetBindingPosition binding;
        u8 name=target==OW_WILD_BEHAVIOR_TARGET_CARGO
            ?OVERWORLD_TARGET_BINDING_CARGO:OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST;
        /* Sight starts Find Cargo before a route can bind a Cargo. Keep that
         * search alive; a failed existing binding must still abort. */
        if(target==OW_WILD_BEHAVIOR_TARGET_CARGO
            && relation==OW_WILD_HELPER_THROW_TARGET_NONE
            && call->throwService!=NULL
            && runtime->conditions!=NULL
            && runtime->conditions->bindings[slot].bindings[name].flags==0)
            return OVERWORLD_CARGO_READ_TARGET_NONE;
        if(call->throwService==NULL || !call->throwService->bindingPosition(state,slot,name,&binding))
            return OVERWORLD_CARGO_READ_TARGET_ABORT;
        out->playerX=binding.x;out->playerY=binding.y;
    }
    out->impactX=out->playerX;out->impactY=out->playerY;
    out->targetObject=call->object;out->targetSlot=slot;
    if(relation!=OW_WILD_HELPER_THROW_TARGET_NONE) {
        u8 targetSlot=OW_WILD_HELPER_THROW_TARGET_DECODE(relation);
        if(targetSlot>=OW_WILD_MAX_SPAWNS || !state->spawns[targetSlot].active
            || state->spawns[targetSlot].object==NULL
            || !call->ops->isCurrentSpawn(field,&state->spawns[targetSlot]))
            return OVERWORLD_CARGO_READ_TARGET_ABORT;
        out->targetSlot=targetSlot;out->targetObject=state->spawns[targetSlot].object;
        if(!(relation&OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG)
            && (OW_WILD_BEHAVIOR_ON_REACH_ACTION(profile->onReachAction)!=OW_WILD_BEHAVIOR_ON_REACH_PICKUP_CONDITION_ACTOR
                || (target!=OW_WILD_BEHAVIOR_TARGET_CONDITION_ACTOR && target!=OW_WILD_BEHAVIOR_TARGET_CARGO)
                || !call->ops->queryTarget(state,slot,targetSlot,OW_WILD_HELPER_PICKUP_THROW_QUERY_VALID,0)))
            return OVERWORLD_CARGO_READ_TARGET_ABORT;
    }
    if(relation==OW_WILD_HELPER_THROW_TARGET_NONE) {
        if(target==OVERWORLD_CARGO_READ_TARGET_CIRCLE)
            (void)call->ops->circleTarget(state,field,slot,profile,OW_WILD_SPAWNER_SPOT_STATE_CHILL,
                out->objectX,out->objectY,out->playerX,out->playerY,&out->playerX,&out->playerY);
        else if(target==OVERWORLD_CARGO_READ_TARGET_ADJACENT
            && !call->ops->adjacentTarget(state,field,slot,profile,&out->playerX,&out->playerY))
            return OVERWORLD_CARGO_READ_TARGET_NONE;
    } else if(!(relation&OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG)
        && (target==OW_WILD_BEHAVIOR_TARGET_CONDITION_ACTOR || target==OW_WILD_BEHAVIOR_TARGET_CARGO)) {
        out->playerX=(u32)out->targetObject->xCurr;out->playerY=(u32)out->targetObject->yCurr;
    }
    out->dx=out->playerX-out->objectX;out->dy=out->playerY-out->objectY;
    if(relation&OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG) {
        if(relation&0x40) { /* Existing private Throw windup flag. */
            out->impactX=runtime->movementCustomJumpTargetX[slot];
            out->impactY=runtime->movementCustomJumpTargetY[slot];
        }
        out->dx=out->impactX-out->objectX;out->dy=out->impactY-out->objectY;
        dx=out->dx<0?-out->dx:out->dx;dy=out->dy<0?-out->dy:out->dy;
        out->throwDistance=(u8)(target==OW_WILD_BEHAVIOR_TARGET_PLAYER_AWAY_THROW_LINE
            ? (dx>dy?dx:dy) : dx+dy);
        out->direction=dx>=dy?OW_WILD_HELPER_DIRECTION_LEFT+(out->dx>0):(out->dy>0);
        /* These coordinates are only consumed by the positioning branch after
         * launch/windup/held-stage exits. Impact deltas above stay unchanged. */
        if(profile->throwMaxRange!=0 && target!=OW_WILD_BEHAVIOR_TARGET_PLAYER_AWAY_THROW_LINE
            && out->throwDistance>profile->throwMaxRange) {
            if(dx>dy) {
                out->playerX=out->impactX+(out->dx<0?profile->throwMaxRange:-profile->throwMaxRange);
                out->playerY=out->impactY;
            } else {
                out->playerX=out->impactX;
                out->playerY=out->impactY+(out->dy<0?profile->throwMaxRange:-profile->throwMaxRange);
            }
        }
    }
    return OVERWORLD_CARGO_READ_TARGET_VALID;
}
