#include "../../include/overworld_throw_away_wild.h"
#include "../../include/overworld_wild_runtime_state_internal.h"
#include "../../include/overworld_wild_helper.h"
#include "../../include/player_health_throw_observation.h"
#include "../../include/map_events_internal.h"

typedef struct AwayNativeWorld {
    OverworldPickupRouteWildWorld *world;
    OverworldPickupRouteNativePolicy policy;
    OverworldPickupRouteNativeLandingCall landing;
} AwayNativeWorld;

static OverworldMotionDecision AwayNativeLanding(void *raw,int x,int z,s32 *baseY)
{
    AwayNativeWorld *native=raw;
    OverworldPickupRoutePosition destination;
    OverworldPickupRouteEdgeResult result;
    native->landing.targetX=x;native->landing.targetY=z;
    native->world->finalTargetX=x;native->world->finalTargetY=z;
    native->landing.destination=&destination;
    result=OverworldPickupRouteNative_Landing(&native->landing);
    if(result==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL) {
        *baseY=destination.baseY;
        return OVERWORLD_MOTION_DECISION_ACCEPTED;
    }
    if(result==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED) return OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;
    return result==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED
        ?native->world->lastDecision:OVERWORLD_MOTION_DECISION_PROFILE;
}

BOOL OverworldThrowAwayWild_Read(const OverworldThrowAwayWildCall *input)
{
    OverworldPickupRouteWildWorld *world;
    const PlayerHealthThrowServiceEntry *service;
    u32 settings;
    u8 targetSlot,distance;
    if(input==NULL || input->reserved[0] || input->reserved[1] || input->reserved[2]) return FALSE;
    world=input->world;service=input->throwService;settings=input->settings;
    targetSlot=input->targetSlot;distance=settings&255;
    OverworldWildSpawnState *state;
    OverworldWildOverlayRuntimeState *runtime;
    OverworldTargetBindingPosition cargo,interest;
    LocalMapObject *carrier,*object,*player;
    OverworldWildSurfaceHit source;
    AwayNativeWorld native={0};
    OverworldThrowAwayAimCall call;
    OverworldThrowAwayAim aim;
    u8 slot,relation;
    if(world==NULL || service==NULL
        || service->magic!=PLAYER_HEALTH_THROW_SERVICE_MAGIC
        || service->version!=PLAYER_HEALTH_THROW_SERVICE_VERSION
        || service->size!=sizeof(*service) || service->bindingPosition==NULL
        || (state=world->state)==NULL || state->movementRuntimeState==NULL
        || world->field==NULL || state->movementFieldSystem!=world->field
        || world->ops==NULL || world->ops->currentObject==NULL
        || world->ops->querySurface==NULL || world->field->playerAvatar==NULL
        || (slot=world->slot)>=OW_WILD_MAX_SPAWNS || (u32)targetSlot>=OW_WILD_MAX_SPAWNS
        || targetSlot==slot || distance==0 || distance>8
        || (settings>>8)==0 || (settings>>8)>OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL) return FALSE;
    runtime=state->movementRuntimeState;relation=runtime->throwState.targets[slot];
    if(!(relation&OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG)
        || OW_WILD_HELPER_THROW_TARGET_DECODE(relation)!=targetSlot
        || !service->bindingPosition(state,slot,OVERWORLD_TARGET_BINDING_CARGO,&cargo)
        || cargo.target.kind!=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
        || cargo.target.actor.slot!=targetSlot
        || !service->bindingPosition(state,slot,OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST,&interest)) return FALSE;
    carrier=state->spawns[slot].object;object=state->spawns[targetSlot].object;
    player=world->field->playerAvatar->mapObject;
    if(!state->spawns[slot].active || !state->spawns[targetSlot].active
        || carrier==NULL || object==NULL || player==NULL
        || !(carrier->flags&object->flags&player->flags&MAPOBJECTFLAG_ACTIVE)
        || !world->ops->currentObject(world->field,carrier)
        || !world->ops->currentObject(world->field,object)
        || !world->ops->currentObject(world->field,player)
        || object->xCurr!=carrier->xCurr || object->yCurr!=carrier->yCurr) return FALSE;
    world->slot=targetSlot;world->subjectObject=object;world->heightObject=object;
    world->collisionIgnoredObject=carrier;
    native.world=world;
    native.policy.version=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;
    native.policy.size=sizeof(native.policy);native.policy.allowedTerrainMask=settings>>8;
    native.policy.playerTerrainMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER;
    native.policy.flags=OVERWORLD_PICKUP_ROUTE_NATIVE_SAME_SURFACE;
    native.landing.version=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;
    native.landing.size=sizeof(native.landing);native.landing.policy=&native.policy;
    native.landing.world=world;native.landing.subject=&cargo.target.actor;
    native.landing.origin=(OverworldPickupRoutePosition){object->xCurr,object->yCurr,
        (s32)object->posVec[1],OW_WILD_SURFACE_ID_NATIVE_GROUND,0};
    if(world->ops->querySurface(world->field,world->catalog,object->xCurr,object->yCurr,&source))
        native.landing.origin.surfaceId=source.surfaceId;
    call=(OverworldThrowAwayAimCall){carrier->xCurr,carrier->yCurr,player->xCurr,player->yCurr,
        distance,&native,AwayNativeLanding};
    if(input->required!=NULL) {
        if(!OverworldThrowAwayAim_Validate(&call,input->required)) return FALSE;
        aim=*input->required;
    } else if(!OverworldThrowAwayAim_Select(&call,&aim)) return FALSE;
    if(input->result!=NULL) *input->result=aim;
    return TRUE;
}
