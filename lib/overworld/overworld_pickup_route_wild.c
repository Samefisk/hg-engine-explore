#include "overworld_pickup_route_wild.h"
#include "overworld_entry_route.h"
#include "overworld_prepared_movement.h"
#include "overworld_actor_system_internal.h"
#include "overworld_wild_spawns_internal.h"
#include "overworld_wild_occupancy.h"
#include "map_events_internal.h"
#include "overworld_wild_runtime_state_internal.h"
#include "overworld_cargo_read_wild.h"
#include "overworld_application_bank.h"

typedef OverworldPickupRouteEdgeResult Result;
#define LEGAL OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL
#define BLOCKED OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED
#define INVALID OVERWORLD_PICKUP_ROUTE_EDGE_INVALID
#define DEFERRED OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED

/* Only a current immutable package supplied by the loaded Wild owner may
 * turn a surface-catalog miss into a known terrain rejection. The owner has
 * already validated its rows at package/build admission; this exact header
 * check preserves the compiled layout proof without a second catalog scan. */
static const OverworldWildBehaviorDataBlobHeader sWildExpectedBlobHeader = {
    .magic = OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC,
    .version = OVERWORLD_WILD_BEHAVIOR_DATA_VERSION,
    .headerSize = sizeof(OverworldWildBehaviorDataBlobHeader),
    .blobSize = sizeof(OverworldWildBehaviorDataBlob),
    .classProfilesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, classProfiles),
    .classProfileCount = OWBD_CLASS_PROFILE_COUNT,
    .classProfileSize = sizeof(OverworldWildBehaviorProfileData),
    .classRulesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, classRules),
    .classRuleCount = OWBD_CLASS_RULE_COUNT,
    .classRuleSize = sizeof(OverworldWildBehaviorClassRule),
    .speciesClassRulesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, speciesClassRules),
    .speciesClassRuleCount = OWBD_SPECIES_CLASS_RULE_COUNT,
    .speciesClassRuleSize = sizeof(OverworldWildBehaviorSpeciesClassRule),
    .overrideProfilesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, overrideProfiles),
    .overrideProfileCount = OWBD_OVERRIDE_PROFILE_COUNT,
    .overrideProfileSize = sizeof(OverworldWildBehaviorOverrideProfile),
    .overrideMembersOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, overrideMembers),
    .overrideMemberCount = OWBD_OVERRIDE_MEMBER_COUNT,
    .overrideMemberSize = sizeof(u16),
    .conditionEntriesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, conditionEntries),
    .conditionEntryCount = OWBD_CONDITION_ENTRY_COUNT,
    .conditionEntrySize = sizeof(OverworldWildBehaviorConditionEntry),
    .surfaceModelsOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, surfaceModels),
    .surfaceModelCount = OWBD_SURFACE_MODEL_COUNT,
    .surfaceModelSize = sizeof(OverworldWildSurfaceModelDirectoryEntry),
    .surfaceInstancesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, surfaceInstances),
    .surfaceInstanceCount = OWBD_SURFACE_INSTANCE_COUNT,
    .surfaceInstanceSize = sizeof(OverworldWildSurfaceInstance),
    .surfaceTemplatesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, surfaceTemplates),
    .surfaceTemplateCount = OWBD_SURFACE_TEMPLATE_COUNT,
    .surfaceTemplateSize = sizeof(OverworldWildSurfaceTemplate),
};
static BOOL CatalogCompatible(const OverworldPickupRouteWildWorld *world)
{
    const OverworldWildBehaviorDataBlob *blob=world->behaviorData;
    const u8 *actual;
    const u8 *expected=(const u8 *)&sWildExpectedBlobHeader;
    if (((unsigned long)blob&3u)
        || world->catalog!=(const OverworldWildSurfaceCatalog *)blob->surfaceModels)
        return FALSE;
    actual=__builtin_assume_aligned(blob,4);
    for (u8 i=0;i<sizeof(sWildExpectedBlobHeader)/sizeof(u32);i++) {
        u32 actualWord,expectedWord;
        /* memcpy preserves alias rules for the mixed-field native header.
         * Alignment admission above permits one native word load per copy. */
        __builtin_memcpy(&actualWord,actual+i*sizeof(u32),sizeof(actualWord));
        __builtin_memcpy(&expectedWord,expected+i*sizeof(u32),sizeof(expectedWord));
        if (actualWord!=expectedWord) return FALSE;
    }
    return TRUE;
}
static int Abs(int value) { return value<0?-value:value; }
static BOOL HandleMatches(const OverworldActorHandle *a,const OverworldActorHandle *b)
{
    return a->slot==b->slot && a->generation==b->generation
        && a->fieldEpoch==b->fieldEpoch && a->mapGeneration==b->mapGeneration
        && a->encounterGeneration==b->encounterGeneration && !a->reserved && !b->reserved;
}
static BOOL Bound(const OverworldPickupRouteWildWorld *world,
    const OverworldActorSystemState *system,const OverworldActorHandle *handle)
{
    const OverworldActorStateSnapshot *actor;
    const OverworldWildSpawn *spawn;
    if (handle->slot>=OW_WILD_MAX_SPAWNS) return FALSE;
    actor=&system->slots[handle->slot].snapshot;
    spawn=&world->state->spawns[handle->slot];
    return actor->active && spawn->active && HandleMatches(handle,&actor->handle)
        && actor->subjectIdentity==spawn->personality
        && handle->encounterGeneration==spawn->encounterGeneration
        && spawn->object!=NULL && (spawn->object->flags&MAPOBJECTFLAG_ACTIVE)
        && world->ops->currentObject(world->field,spawn->object);
}
/* Recover the published winner from this Subject's active condition states.
 * The shared result can belong to another Subject or a warm Cargo evaluation.
 * Unbound placement retains its Player destination. */
static LocalMapObject *InterestObject(const OverworldPickupRouteWildWorld *world)
{
    LocalMapObject *object;
    if (world->preparedPhysical!=NULL) {
        object=world->field->playerAvatar!=NULL?world->field->playerAvatar->mapObject:NULL;
        if (object==NULL || object->xCurr!=world->preparedPhysical->targetX
            || object->yCurr!=world->preparedPhysical->targetY) return NULL;
    } else if (world->subjectObject==NULL && world->state==NULL) {
        object=world->field->playerAvatar!=NULL?world->field->playerAvatar->mapObject:NULL;
    } else {
        const OverworldWildOverlayRuntimeState *runtime;
        const OverworldActorSystemState *system;
        const OverworldWildBehaviorConditionRuntime *conditions;
        const OverworldBehaviorConditionPreparedActor *prepared;
        const OverworldBehaviorConditionEntryState *winner=NULL;
        const OverworldWildBehaviorDataBlob *blob=world->behaviorData;
        OverworldApplicationBank bank;
        const OverworldActorHandle *subject;
        OverworldActorHandle target;
        u32 seen=0;
        u8 winnerApplication=0;
        if (world->state==NULL || world->slot>=OW_WILD_MAX_SPAWNS
            || world->state->movementFieldSystem!=world->field
            || (runtime=world->state->movementRuntimeState)==NULL
            || runtime->conditions==NULL || (system=world->ops->actorState())==NULL)
            return NULL;
        conditions=runtime->conditions;
        prepared=&conditions->actors[world->slot];
        subject=&prepared->subject;
        if (blob==NULL || !prepared->valid || prepared->states==NULL
            || prepared->count>OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES
            || prepared->count>prepared->stateCapacity
            || subject->slot!=world->slot || !subject->generation || !subject->fieldEpoch
            || subject->fieldEpoch!=system->fieldEpoch
            || subject->mapGeneration!=system->mapGeneration
            || !(conditions->targetValidMask&(1u<<world->slot))
            || !conditions->activeApplicationMasks[world->slot]
            || !Bound(world,system,subject)
            || !OverworldApplicationBank_Select(blob, prepared->subjectSpecies, &bank)
            || world->subjectObject!=world->state->spawns[world->slot].object)
            return NULL;
        /* Last active entry wins within an application; the highest active
         * application with a target wins overall, as in FoldResult. */
        for (u8 i=prepared->count;i!=0;) {
            u16 sourceIndex=prepared->catalogEntryIndexes[--i];
            const OverworldBehaviorConditionEntryState *state=&prepared->states[i];
            const OverworldWildBehaviorConditionEntry *entry;
            int localApplication;
            u32 bit;
            if (sourceIndex>=blob->header.conditionEntryCount) return NULL;
            entry=&blob->conditionEntries[sourceIndex];
            localApplication=OverworldApplicationBank_Local(&bank,
                blob->conditionGlobalApplications[sourceIndex]);
            if (localApplication<0)
                return NULL;
            bit=1u<<localApplication;
            if (!(state->flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)
                || blob->conditionOptions[sourceIndex].bindOnly
                || !(conditions->activeApplicationMasks[world->slot]&bit)
                || (seen&bit)) continue;
            seen|=bit;
            if (state->targetKind!=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE
                && (winner==NULL || localApplication>winnerApplication)) {
                winner=state;winnerApplication=localApplication;
            }
        }
        if (winner==NULL) return NULL;
        if (winner->targetKind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER) {
            object=world->field->playerAvatar!=NULL?world->field->playerAvatar->mapObject:NULL;
        } else {
            target=*subject;
            target.slot=winner->targetSlot;target.generation=winner->targetGeneration;
            target.encounterGeneration=winner->targetEncounterGeneration;
            if (winner->targetKind!=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
                || target.slot==world->slot || !target.generation
                || !Bound(world,system,&target)) return NULL;
            object=world->state->spawns[target.slot].object;
        }
        /* The publication owns the target identity. Its cached tile can lag
         * accepted motion; destination permission follows that current actor. */
        if (object==NULL) return NULL;
    }
    return object!=NULL && (object->flags&MAPOBJECTFLAG_ACTIVE)
        && world->ops->currentObject(world->field,object)?object:NULL;
}
/* Mounted uses the Player anchor plus one dependent Pokemon presentation.
 * That presentation belongs to the permitted Player target; other occupants
 * still take part in the same native occupancy query. */
static LocalMapObject *MountedPlayerPresentation(
    const OverworldPickupRouteWildWorld *world,
    const OverworldPickupRoutePosition *pose)
{
    const OverworldActorSystemState *system;
    const OverworldActorStateSnapshot *actor;
    LocalMapObject *object;
    if (world->state==NULL || (system=world->ops->actorState())==NULL)
        return NULL;
    actor=&system->slots[OW_WILD_FOLLOWER_SLOT].snapshot;
    if (!actor->handle.generation || !actor->handle.encounterGeneration
        || actor->handle.slot!=OW_WILD_FOLLOWER_SLOT
        || actor->role!=OVERWORLD_ACTOR_ROLE_MOUNTED || !actor->inputOwnership
        || !actor->presentationAttached
        || actor->handle.fieldEpoch!=system->fieldEpoch
        || actor->handle.mapGeneration!=system->mapGeneration
        || !Bound(world,system,&actor->handle)) return NULL;
    object=world->state->spawns[OW_WILD_FOLLOWER_SLOT].object;
    return object->xCurr==pose->x && object->yCurr==pose->y ? object : NULL;
}
static Result Binding(void *raw,const OverworldPickupRouteQuery *query)
{
    OverworldPickupRouteWildWorld *world=raw;
    const OverworldPickupRouteWildOps *ops=world->ops;
    const OverworldActorSystemState *system;
    world->hitValid=0; world->query=query; world->routeRead=query!=NULL;
    world->lastDecision=OVERWORLD_MOTION_DECISION_TERRAIN;
    if (world->field==NULL
        || (world->landingPolicy&~OVERWORLD_PICKUP_ROUTE_WILD_PERMIT_BOUND_OOI_OCCUPANCY)
        || (query!=NULL && world->landingPolicy)) return INVALID;
    if (world->subjectObject!=NULL && (world->slot>=OW_WILD_MAX_SPAWNS
        || !ops->currentObject(world->field,world->subjectObject)
        || !(world->subjectObject->flags&MAPOBJECTFLAG_ACTIVE))) return INVALID;
    if (query==NULL) return LEGAL;
    if (world->catalog==NULL) return DEFERRED;
    if (query->extension!=NULL) {
        system=ops->actorState();
        if (!OverworldPickupRoute_QueryCurrent(query) || world->state==NULL
            || world->state->movementFieldSystem!=world->field || system==NULL
            || query->scopeRevision!=world->scopeRevision
            || query->movementPolicyRevision!=world->movementPolicyRevision
            || query->dynamicRevision!=world->dynamicRevision) return INVALID;
        if (query->extension->kind==OVERWORLD_PICKUP_ROUTE_EXTENSION_PREPARED)
            return world->preparedPhysical!=NULL && world->subjectObject==NULL?LEGAL:INVALID;
        return query->extension->kind==OVERWORLD_PICKUP_ROUTE_EXTENSION_ENTRY_ACTOR
            && query->subject.slot==world->slot
            && query->subject.fieldEpoch==system->fieldEpoch
            && query->subject.mapGeneration==system->mapGeneration
            && Bound(world,system,&query->subject)
            && world->subjectObject==world->state->spawns[world->slot].object?LEGAL:INVALID;
    }
    system=ops->actorState();
    if (world->state==NULL || world->state->movementFieldSystem!=world->field
        || system==NULL
        || query->subject.slot!=world->slot
        || query->scopeRevision!=world->scopeRevision
        || query->movementPolicyRevision!=world->movementPolicyRevision
        || query->dynamicRevision!=world->dynamicRevision
        || query->subject.fieldEpoch!=system->fieldEpoch
        || query->subject.mapGeneration!=system->mapGeneration
        || !Bound(world,system,&query->subject) || !Bound(world,system,&query->cargo)
        || world->subjectObject!=world->state->spawns[world->slot].object) return INVALID;
    return LEGAL;
}
/* The normal synchronous tile reader and Entry's saved tile reader run this
 * one reducer. Entry yields before a physical callback; no partial tile is
 * published. The source catalog/header check is repeated on every resume. */
static BOOL TileBudget(OverworldPickupRouteWildWorld *world,u8 count)
{
    OverworldEntryRouteMemo *memo=world->entryMemo;
    if (memo==NULL) return TRUE;
    if (count>memo->budget) return FALSE;
    memo->budget-=count;memo->used+=count;return TRUE;
}
static Result TileStep(OverworldPickupRouteWildWorld *world,OverworldEntryRouteTerrainCursor *c)
{
    const OverworldPickupRouteWildOps *ops=world->ops;
    if (world->behaviorData!=NULL && !CatalogCompatible(world)) return INVALID;
    if (world->catalog==NULL) return DEFERRED;
    for (;;) switch(c->phase) {
    case 0:
        if (!TileBudget(world,1)) return DEFERRED;
        if (!ops->playable(world->field,c->x,c->y)) return BLOCKED;
        c->tile=(OverworldPickupRouteNativeTile){OVERWORLD_PICKUP_ROUTE_NATIVE_GROUND,0,0,0,0};
        c->phase=1;break;
    case 1:
        if (c->wanted && !(c->wanted&~OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SURFACE_ALL)
            && world->behaviorData!=NULL) {
            if (!TileBudget(world,1)) return DEFERRED;
            c->hitValid=ops->querySurface(world->field,world->catalog,c->x,c->y,&c->hit);
            if (!c->hitValid) { c->phase=9;break; }
        }
        c->phase=2;break;
    case 2:
        if (!TileBudget(world,1)) return DEFERRED;
        c->tile.behavior=ops->behavior(world->field,c->x,c->y);
        if (c->tile.behavior==0xFF) { c->phase=0;return DEFERRED; }
        /* A catalogued surface may veto grass, but cannot make a non-grass
         * loaded metatile grass. Keep unknown, mixed-mask and SOURCE reads
         * complete; real grass still reaches the canonical surface veto. */
        if (c->wanted==OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS
            && c->tile.behavior!=2 && c->tile.behavior!=3) {
            c->phase=9;break;
        }
        c->phase=3;break;
    case 3:
        if (!c->hitValid) {
            if (!TileBudget(world,1)) return DEFERRED;
            c->hitValid=ops->querySurface(world->field,world->catalog,c->x,c->y,&c->hit);
        }
        if (c->hitValid) {
            c->tile.surfaceId=c->hit.surfaceId;
            c->tile.terrainMask=OW_WILD_SURFACE_TYPE_TERRAIN_MASK(c->hit.surfaceType);
            c->phase=6;break;
        }
        if (ops->surf(c->tile.behavior)) c->tile.terrainMask|=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER;
        if (c->tile.behavior==2 || c->tile.behavior==3)
            c->tile.terrainMask|=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS;
        c->phase=4;break;
    case 4:
        if (!TileBudget(world,1)) return DEFERRED;
        if (ops->playerFront(world->field,c->x,c->y)) c->tile.terrainMask|=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT;
        c->phase=5;break;
    case 5:
        if (c->wanted&OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND) {
            /* IsLandMapTile does playable, loaded behavior and blocked tile. */
            if (!TileBudget(world,3)) return DEFERRED;
            if (ops->land(world->field,c->x,c->y)) c->tile.terrainMask|=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND;
        }
        c->phase=6;break;
    case 6: {
        LocalMapObject *interest=c->wanted!=0xFFFF
            && (world->landingPolicy || (c->wanted&OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER))
            ?InterestObject(world):NULL;
        if (interest!=NULL && interest->xCurr==c->x && interest->yCurr==c->y) {
            c->tile.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_OBJECT_OF_INTEREST;
            if (!world->landingPolicy && (world->subjectObject!=NULL || !c->hitValid))
                c->tile.terrainMask|=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER;
        }
        c->phase=7;break;
    }
    case 7:
        if (!TileBudget(world,1)) return DEFERRED;
        if (ops->scripted(world->field,c->x,c->y)) c->tile.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_SCRIPTED;
        c->phase=8;break;
    case 8:
        if (!TileBudget(world,1)) return DEFERRED;
        if (ops->playerTile(world->field,c->x,c->y)) c->tile.flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_PLAYER;
        c->phase=9;break;
    case 9: return LEGAL;
    default: return INVALID;
    }
}
static Result Terrain(void *raw,s16 x,s16 y,u16 wantedMask,OverworldPickupRouteNativeTile *tile)
{
    OverworldPickupRouteWildWorld *world=raw;
    OverworldEntryRouteTerrainCursor local={0},*c=world->entryMemo!=NULL?&world->entryMemo->terrain:&local;
    if (c->x!=x || c->y!=y || c->wanted!=wantedMask || c->phase==9) {
        *c=(OverworldEntryRouteTerrainCursor){0};c->x=x;c->y=y;c->wanted=wantedMask;
    }
    Result d=TileStep(world,c);
    world->hitX=x;world->hitY=y;world->hitValid=c->hitValid;world->hit=c->hit;
    if (d==LEGAL) *tile=c->tile;
    if (d==BLOCKED || d==DEFERRED) world->lastDecision=OVERWORLD_MOTION_DECISION_BLOCKED;
    return d;
}
static Result Support(void *raw,const OverworldPickupRoutePosition *origin,s16 x,s16 y,
    const OverworldPickupRouteNativeTile *tile,s32 *height)
{
    OverworldPickupRouteWildWorld *world=raw;
    const OverworldWildSurfaceHit *hit=NULL;
    LocalMapObject *object=world->heightObject;
    if (world->hitX!=x || world->hitY!=y) return INVALID;
    if (world->hitValid) hit=&world->hit;
    if (object==NULL && world->preparedPhysical!=NULL) {
        return world->ops->resolveBaseYAt(world->field,hit,origin->baseY,
            world->preparedPhysical->flags,x,y,height)?LEGAL:DEFERRED;
    }
    if (object==NULL) {
        if (tile->surfaceId==OW_WILD_SURFACE_ID_NATIVE_CANOPY) {
            world->lastDecision=OVERWORLD_MOTION_DECISION_PROFILE;
            return INVALID;
        }
        *height=hit!=NULL?hit->height:origin->baseY;
        return LEGAL;
    }
    if (world->ops->resolveBaseYAt(world->field,hit,origin->baseY,
            object->flags,x,y,height)) return LEGAL;
    if (world->routeRead) return DEFERRED;
    /* Preserve the existing real START/placement fallback only. */
    *height=(s32)object->posVec[1];
    return LEGAL;
}
static Result Occupancy(void *raw,const OverworldActorHandle *subject,
    const OverworldPickupRoutePosition *pose,u8 includeObjectOfInterest)
{
    OverworldPickupRouteWildWorld *world=raw;
    LocalMapObject *ignored=world->subjectObject;
    LocalMapObject *collisionIgnored=world->routeRead?NULL:world->collisionIgnoredObject;
    u8 includePlayer=1;
    int mode;
    (void)subject; /* Binding checked the full query handle before this read. */
    if (!includeObjectOfInterest) {
        LocalMapObject *interest=InterestObject(world);
        if (interest!=NULL && interest->xCurr==pose->x && interest->yCurr==pose->y) {
            if (world->field->playerAvatar!=NULL
                && interest==world->field->playerAvatar->mapObject) {
                LocalMapObject *mounted=MountedPlayerPresentation(world,pose);
                includePlayer=0;
                if (mounted!=NULL) {
                    if (ignored==NULL || ignored->xCurr!=pose->x || ignored->yCurr!=pose->y)
                        ignored=mounted;
                    else if (collisionIgnored==NULL || collisionIgnored->xCurr!=pose->x
                        || collisionIgnored->yCurr!=pose->y) collisionIgnored=mounted;
                }
            }
            else if (interest!=ignored && interest!=collisionIgnored) {
                /* Keep the held carrier ignore. A nonzero move's Subject is
                 * off this tile and its ignore can cover the exact Interest. */
                if (ignored==NULL || ignored->xCurr!=pose->x || ignored->yCurr!=pose->y)
                    ignored=interest;
                else if (collisionIgnored==NULL || collisionIgnored->xCurr!=pose->x
                    || collisionIgnored->yCurr!=pose->y) collisionIgnored=interest;
            }
        }
    }
    if (pose->surfaceId!=OW_WILD_SURFACE_ID_NATIVE_GROUND)
        mode=includePlayer?OVERWORLD_WILD_OCCUPANCY_SURFACE_PLAYER:OVERWORLD_WILD_OCCUPANCY_SURFACE;
    else {
        mode=includePlayer?OVERWORLD_WILD_OCCUPANCY_OBJECTS:OVERWORLD_WILD_OCCUPANCY_NONPLAYER;
        if (!world->routeRead && includePlayer && ignored==world->subjectObject) ignored=NULL;
    }
    if (world->ops->occupancy(world->field,ignored,
            collisionIgnored,pose->x,pose->y,pose->baseY,mode)) {
        world->lastDecision=OVERWORLD_MOTION_DECISION_OCCUPIED;
        return BLOCKED;
    }
    return LEGAL;
}
static Result Reservations(void *raw,const OverworldActorHandle *subject,
    const OverworldPickupRoutePosition *pose)
{
    OverworldPickupRouteWildWorld *world=raw;
    const OverworldActorSystemState *system=world->ops->actorState();
    BOOL prepared=world->preparedPhysical!=NULL && world->query!=NULL
        && world->query->extension!=NULL
        && world->query->extension->kind==OVERWORLD_PICKUP_ROUTE_EXTENSION_PREPARED;
    if (system==NULL || (!prepared && (subject==NULL
        || subject->fieldEpoch!=system->fieldEpoch))) return INVALID;
    for (u8 i=0;i<OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS;i++) {
        const OverworldActorRuntimeSlot *slot=&system->slots[i];
        const OverworldActorStateSnapshot *other=&slot->snapshot;
        if ((prepared || i!=subject->slot) && other->reservationId
            && other->handle.fieldEpoch==system->fieldEpoch
            && other->targetX==pose->x && other->targetY==pose->y
            && slot->policy.targetSurfaceId==pose->surfaceId) return BLOCKED;
    }
    return LEGAL;
}
static Result EdgePolicy(void *raw,const OverworldPickupRouteNativePolicy *policy,u8 kind,
    const OverworldPickupRoutePosition *from,const OverworldPickupRouteNativeTile *source,
    const OverworldPickupRoutePosition *to,const OverworldPickupRouteNativeTile *target)
{
    OverworldPickupRouteWildWorld *world=raw;
    LocalMapObject *object=world->subjectObject;
    OverworldActorPolicyView view;
    int dx=to->x-from->x,dy=to->y-from->y;
    if (kind==OVERWORLD_PICKUP_ROUTE_NATIVE_LANDING_ONLY) {
        if (object==NULL) return LEGAL;
        if (!world->ops->inspectPolicy(world->slot,&view)) {
            world->lastDecision=OVERWORLD_MOTION_DECISION_PROFILE;
            return INVALID;
        }
        if ((view.chainPauseAction&0xF0)
                ==0x90) {
            if (world->routeRead) {
                /* A hypothetical next pose uses the same fixed grid anchor.
                 * Skid grid steps count accepted moves, not tile distance;
                 * that phase is not a route-query admission boundary. */
                if (view.chainStepsRemaining&0x20) return INVALID;
                dx=to->x-object->xCurr;dy=to->y-object->yCurr;
            } else if (view.chainStepsRemaining&0x20) {
                dx=(dx>0)-(dx<0);dy=(dy>0)-(dy<0);
            }
            if ((u32)((view.chainPauseAction&3)+dx)>2
                || (u32)(((view.chainPauseAction>>2)&3)+dy)>2) {
                world->lastDecision=OVERWORLD_MOTION_DECISION_BLOCKED;
                return BLOCKED;
            }
        }
        return LEGAL;
    }
    if (kind==OVERWORLD_PICKUP_ROUTE_NATIVE_HOP) return LEGAL;
    if ((object==NULL && world->preparedPhysical==NULL) || source==NULL || target==NULL)
        return INVALID;
    OverworldPreparedMovementInput input={0};
    input.version=OVERWORLD_PREPARED_MOVEMENT_VERSION;input.size=sizeof(input);
    input.profile=policy->resolvedProfile;input.lane=policy->resolvedLane;
    input.field=world->field;input.ops=world->ops;input.from=*from;input.to=*to;
    input.source=*source;input.target=*target;input.kind=kind;input.directions=policy->directions;
    input.objectFlags2=object!=NULL?object->flags2:world->preparedPhysical->flags2;
    input.rangeX=object!=NULL?object->xrange:world->preparedPhysical->rangeX;
    input.rangeY=object!=NULL?object->yrange:world->preparedPhysical->rangeY;
    input.anchorX=from->x;input.anchorY=from->y;
    if (object!=NULL && (!world->routeRead || (from->x==object->xCurr && from->y==object->yCurr))) {
        input.anchorX=object->xInit;input.anchorY=object->yInit;
    }
    input.blockedTerrain=world->ops->blockedTerrain;
    input.collisionIgnoredObject=object;
    input.allowObjectOfInterestDestination=(policy->flags&OVERWORLD_PICKUP_ROUTE_NATIVE_ALLOW_PLAYER_DESTINATION)!=0;
    if (world->entryMemo==NULL) return OverworldPreparedMovement_Run(&input);
    OverworldEntryRouteMemo *memo=world->entryMemo;
    if (!memo->movementStarted) {
        memo->movementInput=input;memo->movement=(OverworldPreparedMovementCursor){0};
        memo->movement.version=OVERWORLD_PREPARED_MOVEMENT_VERSION;
        memo->movement.size=sizeof(memo->movement);memo->movement.input=&memo->movementInput;
        Result result=OverworldPreparedMovement_Begin(&memo->movement);
        memo->movementStarted=1;
        if (memo->movement.phase==OVERWORLD_PREPARED_MOVEMENT_DONE) return result;
    }
    memo->movement.readBudget=memo->budget;
    Result result=OverworldPreparedMovement_Step(&memo->movement);
    if (memo->movement.readsUsed>memo->budget) return INVALID;
    memo->budget-=memo->movement.readsUsed;memo->used+=memo->movement.readsUsed;
    if (memo->movement.phase==OVERWORLD_PREPARED_MOVEMENT_DONE && result==DEFERRED)
        memo->movementStarted=0;
    return result;
}
static Result Hop(void *raw,const OverworldPickupRouteNativePolicy *policy,u8 kind,u16 distance,
    const OverworldPickupRoutePosition *from,const OverworldPickupRoutePosition *to)
{
    OverworldPickupRouteWildWorld *world=raw;
    OverworldActorHopPlanCall call={0};
    int decision;
    int dx=(to->x>from->x)-(to->x<from->x);
    int dy=(to->y>from->y)-(to->y<from->y);
    if (kind!=OVERWORLD_PICKUP_ROUTE_NATIVE_HOP || policy->resolvedProfile==NULL
        || policy->resolvedLane==NULL || world->subjectObject==NULL) return INVALID;
    call.profile=policy->resolvedProfile;call.lane=policy->resolvedLane;
    call.operation=OVERWORLD_ACTOR_HOP_PLAN_VECTOR;
    call.deltaX=to->x-from->x;call.deltaY=to->y-from->y;
    call.spotState=world->state->movementSpotStates[world->slot];
    decision=world->ops->hopPlan(&call);
    if (decision!=OVERWORLD_MOTION_DECISION_ACCEPTED) {
        if (decision==OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY) return DEFERRED;
        return decision==OVERWORLD_MOTION_DECISION_DIRECTION?BLOCKED:INVALID;
    }
    if (call.distance!=distance) return INVALID;
    /* This vector is cardinal or45 degrees. Check every crossed tile is
     * loaded before the shared clearance planner can read catalog support. */
    for (u16 i=1;i<distance;i++) {
        int x=from->x+dx*i,y=from->y+dy*i;
        if (!world->ops->playable(world->field,x,y)) return BLOCKED;
        if (world->ops->behavior(world->field,x,y)==0xFF) return DEFERRED;
    }
    call.operation=OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY;
    call.fieldSystem=world->field;call.surfaceCatalog=world->catalog;call.object=world->subjectObject;
    call.startBaseY=from->baseY;call.targetBaseY=to->baseY;
    call.startX=from->x;call.startY=from->y;call.targetX=to->x;call.targetY=to->y;
    call.spotState=OVERWORLD_ACTOR_HOP_PLAN_FLAG_STRICT_HEIGHT;
    decision=world->ops->hopPlan(&call);
    if (decision==OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY) return DEFERRED;
    if (decision==OVERWORLD_MOTION_DECISION_ACCEPTED) return LEGAL;
    return decision==OVERWORLD_MOTION_DECISION_BLOCKED?BLOCKED:INVALID;
}
static Result PickupReach(void *raw,const OverworldPickupRouteNativePolicy *policy,
    const OverworldPickupRoutePosition *standing,const OverworldPickupRoutePosition *cargo)
{
    OverworldPickupRouteWildWorld *world=raw;
    (void)policy;
    if (world->ops->pickupReach==NULL) return INVALID;
    return world->ops->pickupReach(world,standing,cargo);
}
static const OverworldPickupRouteNativeSeams sSeams={
    Binding,Terrain,Support,Occupancy,Reservations,EdgePolicy,Hop,PickupReach
};
const OverworldPickupRouteNativeSeams *OverworldPickupRouteWild_GetSeams(void *raw)
{
    OverworldPickupRouteWildWorld *world=raw;
    const OverworldPickupRouteWildOps *ops;
    if (world==NULL || world->version!=OVERWORLD_PICKUP_ROUTE_WILD_VERSION
        || world->size!=sizeof(*world)) return NULL;
    ops=world->ops;
    if (ops==NULL || ops->version!=OVERWORLD_PICKUP_ROUTE_WILD_VERSION
        || ops->size!=sizeof(*ops) || ops->playable==NULL || ops->behavior==NULL
        || ops->querySurface==NULL || ops->resolveBaseYAt==NULL || ops->surf==NULL
        || ops->playerTile==NULL || ops->playerFront==NULL || ops->land==NULL
        || ops->scripted==NULL || ops->currentObject==NULL || ops->occupancy==NULL
        || ops->actorState==NULL || ops->inspectPolicy==NULL || ops->hopPlan==NULL
        || ops->walkTerrain==NULL || ops->sourceDirectionBlocks==NULL
        || ops->targetDirectionBlocks==NULL) return NULL;
    if (world->behaviorData!=NULL && !CatalogCompatible(world)) return NULL;
    return &sSeams;
}

/* Delta uses unsigned subtraction so every signed fx32 input is bounded
 * without signed overflow. One native tile is 16 units, or 0x10000 fx32. */
static u32 PickupDelta(s32 a,s32 b)
{ return a>=b?(u32)a-(u32)b:(u32)b-(u32)a; }

static BOOL PickupOrdinaryMotion(const OverworldPickupRouteWildWorld *world,
    const OverworldActorRuntimeSlot *slot,const OverworldActorHandle *cargo)
{
    const OverworldMotionPlan *plan=&slot->motion.plan;
    const OverworldActorStateSnapshot *actor=&slot->snapshot;
    const OverworldWildOverlayRuntimeState *runtime=world->state->movementRuntimeState;
    u8 staged=world->state->movementStagedHopPending[cargo->slot];
    return actor->motionPhase>=OVERWORLD_ACTOR_PHASE_MOVING
        && actor->motionPhase<=OVERWORLD_ACTOR_PHASE_SETTLING
        && slot->motion.phase==actor->motionPhase
        && (plan->kind==OVERWORLD_MOTION_KIND_WALK || plan->kind==OVERWORLD_MOTION_KIND_HOP)
        && actor->motionKind==plan->kind && plan->version==OVERWORLD_MOTION_MODEL_VERSION
        && plan->fieldEpoch==cargo->fieldEpoch
        && actor->reservationId!=0 && actor->reservationId==plan->reservationId
        && actor->reservationId==runtime->movementMotionIdentities[cargo->slot]
        && plan->flags==0 && plan->visibilityPolicy==OVERWORLD_MOTION_VISIBILITY_VISIBLE
        && (staged==0 || (staged==(plan->kind==OVERWORLD_MOTION_KIND_WALK?3:1)
            && world->state->movementStagedHopTargetX[cargo->slot]==plan->targetX
            && world->state->movementStagedHopTargetY[cargo->slot]==plan->targetY));
}

__attribute__((section(".query_pickup_handoff")))
Result OverworldPickupRouteWild_AtomicPickup(void *raw,
    const OverworldActorHandle *subject, const OverworldActorHandle *cargo)
{
    OverworldPickupRouteWildWorld *world=raw;
    const OverworldPickupRouteWildOps *ops;
    const OverworldActorSystemState *system;
    OverworldWildOverlayRuntimeState *runtime;
    const OverworldWildBehaviorConditionOptions *options;
    OverworldPickupRoutePosition poses[2];
    const OverworldActorHandle *handles[2]={subject,cargo};
    LocalMapObject *objects[2];
    u16 receipt=0;
    u8 relation;
    if (OverworldPickupRouteWild_GetSeams(raw)==NULL || subject==NULL || cargo==NULL
        || world->state==NULL || world->state->movementRuntimeState==NULL
        || world->state->movementFieldSystem!=world->field
        || world->slot!=subject->slot || subject->slot==cargo->slot) return INVALID;
    world->pickupMotionIdentity=0;
    ops=world->ops;system=ops->actorState();
    if (system==NULL || !Bound(world,system,subject) || !Bound(world,system,cargo)
        || subject->fieldEpoch!=system->fieldEpoch || subject->mapGeneration!=system->mapGeneration
        || cargo->fieldEpoch!=system->fieldEpoch || cargo->mapGeneration!=system->mapGeneration
        || system->slots[subject->slot].snapshot.role==OVERWORLD_ACTOR_ROLE_MOUNTED
        || system->slots[cargo->slot].snapshot.role==OVERWORLD_ACTOR_ROLE_MOUNTED)
        return INVALID;
    runtime=world->state->movementRuntimeState;
    relation=runtime->throwState.targets[subject->slot];
    if (relation!=OW_WILD_HELPER_THROW_TARGET_ENCODE(cargo->slot)
        || !(runtime->throwState.targetMask&(1u<<cargo->slot))
        || !(runtime->throwState.carrierMask&(1u<<subject->slot))
        || (runtime->throwState.targets[cargo->slot]&OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG)
        || world->state->movementActorControlModes[subject->slot]!=OW_WILD_ACTOR_CONTROL_AUTONOMOUS
        || world->state->movementActorControlModes[cargo->slot]!=OW_WILD_ACTOR_CONTROL_AUTONOMOUS)
        return INVALID;
    for (u8 i=0;i<OW_WILD_MAX_SPAWNS;i++)
        if (i!=subject->slot
            && (runtime->throwState.targets[i]&OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG)
            && OW_WILD_HELPER_THROW_TARGET_DECODE(runtime->throwState.targets[i])==cargo->slot)
            return INVALID;
    if ((world->state->captureTargetMask&(1u<<cargo->slot))
        || world->state->movementSpawnRunActive[cargo->slot]
        || world->state->movementCrashShakeTimers[cargo->slot]
        || world->state->movementTeleportHidden[cargo->slot]
        || world->state->movementTeleportFlickerTimers[cargo->slot]
        || world->state->movementTeleportFlickerObjects[cargo->slot]!=NULL
        || world->state->movementQueuedBattleSlot==cargo->slot
        || world->state->pendingSlot==cargo->slot) return DEFERRED;
    for (u8 i=0;i<2;i++) {
        LocalMapObject *object=world->state->spawns[handles[i]->slot].object;
        const OverworldActorRuntimeSlot *slot=&system->slots[handles[i]->slot];
        const OverworldActorStateSnapshot *actor=&slot->snapshot;
        OverworldWildSurfaceHit hit;
        const OverworldWildSurfaceHit *known=NULL;
        objects[i]=object;
        if (actor->motionPhase!=OVERWORLD_ACTOR_PHASE_IDLE || actor->reservationId
            || (object->flags&MAPOBJECTFLAG_SINGLE_MOVEMENT)) {
            if (i==0 || !PickupOrdinaryMotion(world,slot,cargo)) return DEFERRED;
            receipt=actor->reservationId;
        }
        poses[i]=(OverworldPickupRoutePosition){object->xCurr,object->yCurr,0,
            OW_WILD_SURFACE_ID_NATIVE_GROUND,0};
        if (ops->querySurface(world->field,world->catalog,object->xCurr,object->yCurr,&hit)) {
            known=&hit;poses[i].surfaceId=hit.surfaceId;
        }
        if (!ops->resolveBaseYAt(world->field,known,(s32)object->posVec[1],object->flags,
                object->xCurr,object->yCurr,&poses[i].baseY)) return DEFERRED;
    }
    Result reach=ops->pickupReach!=NULL?ops->pickupReach(world,&poses[0],&poses[1]):INVALID;
    if (reach!=LEGAL) return reach;
    options=OverworldCargoReadWild_Options(world);
    if (options==NULL) return INVALID;
    if (PickupDelta((s32)objects[0]->posVec[0],(s32)objects[1]->posVec[0])>((u32)options->pickupDistance<<16)
        || PickupDelta((s32)objects[0]->posVec[2],(s32)objects[1]->posVec[2])>((u32)options->pickupDistance<<16)
        || PickupDelta((s32)objects[0]->posVec[1],(s32)objects[1]->posVec[1])>((u32)options->pickupHeight<<12))
        return receipt!=0 ? DEFERRED : BLOCKED;
    world->pickupMotionIdentity=receipt;
    return LEGAL;
}
