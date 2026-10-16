#include "overworld_entry_route.h"
#include "map_events_internal.h"
#define LEGAL OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL
#define BLOCKED OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED
#define DEFERRED OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED
#define INVALID OVERWORLD_PICKUP_ROUTE_EDGE_INVALID
#define LIMIT OVERWORLD_PICKUP_ROUTE_EDGE_RESOURCE_LIMIT
#define NONE OVERWORLD_PICKUP_ROUTE_NONE
#define OVERWORLD_ENTRY_MEMO_LEDGE_BEHAVIOR 7
static u8 Same(const void *a,const void *b,u16 size)
{ const u8 *x=a,*y=b;while(size--) if(*x++!=*y++) return 0;return 1; }
static int Abs(int v) { return v<0?-v:v; }
static OverworldEntryRouteMemoRead *Read(OverworldPickupRouteWildWorld *w,u8 operation,u8 cost)
{
    OverworldEntryRouteMemo *m=w->entryMemo;
    if (m==NULL || !m->valid) return NULL;
    if (m->cursor<m->count) {
        m->reserved=1;
        OverworldEntryRouteMemoRead *r=&m->reads[m->cursor++];
        if (r->operation!=operation) { m->terminal=INVALID;return NULL; }
        return r;
    }
    if (m->count==OVERWORLD_ENTRY_ROUTE_MEMO_READS) { m->terminal=LIMIT;return NULL; }
    if (cost>m->budget) return NULL;
    m->reserved=0;
    m->budget-=cost;m->used+=cost;
    OverworldEntryRouteMemoRead *r=&m->reads[m->count];
    *r=(OverworldEntryRouteMemoRead){0};r->operation=operation;
    return r;
}
static u8 Cached(const OverworldPickupRouteWildWorld *w)
{ return w->entryMemo->reserved==1; }
static OverworldPickupRouteEdgeResult Missing(OverworldPickupRouteWildWorld *w)
{ return w->entryMemo->terminal?(OverworldPickupRouteEdgeResult)w->entryMemo->terminal:DEFERRED; }
static void Save(OverworldPickupRouteWildWorld *w,OverworldEntryRouteMemoRead *r,
    OverworldPickupRouteEdgeResult result)
{
    r->result=result;
    if (result!=DEFERRED) { w->entryMemo->count++;w->entryMemo->cursor++; }
}
static OverworldPickupRouteEdgeResult Binding(void *raw,const OverworldPickupRouteQuery *q)
{
    OverworldPickupRouteWildWorld *w=raw;
    OverworldPickupRouteEdgeResult result=w->entryMemo->native->binding(raw,q);
    /* Entry proof owns these memo seams. Its root is the current Subject
     * pose, so exclude that exact Subject after the native binding guard. */
    if (result==LEGAL) w->routeRead=1;
    return result;
}
static OverworldPickupRouteEdgeResult Terrain(void *raw,s16 x,s16 y,u16 wanted,
    OverworldPickupRouteNativeTile *out)
{
    OverworldPickupRouteWildWorld *w=raw;
    OverworldEntryRouteMemoRead *r=Read(w,1,0);
    if (r==NULL) return Missing(w);
    if (!Cached(w)) {
        /* The sole Wild tile reducer spends individual native read phases;
         * Land's loaded behavior/block check is charged conservatively3. */
        OverworldPickupRouteEdgeResult d=w->entryMemo->native->terrain(raw,x,y,0xFFFF,&r->tile);
        r->hit=w->hit;r->hitValid=w->hitValid;Save(w,r,d);
    }
    if (r->result==LEGAL) {
        *out=r->tile;w->hitX=x;w->hitY=y;w->hit=r->hit;w->hitValid=r->hitValid;
        if (wanted!=0xFFFF && w->preparedPhysical!=NULL
            && x==w->preparedPhysical->targetX && y==w->preparedPhysical->targetY
            && (wanted&w->entryMemo->physicalPlayerMask)) {
            out->terrainMask|=w->entryMemo->physicalPlayerMask;
            out->flags|=OVERWORLD_PICKUP_ROUTE_NATIVE_TILE_OBJECT_OF_INTEREST;
        }
    }
    return r->result;
}
static OverworldPickupRouteEdgeResult Support(void *raw,const OverworldPickupRoutePosition *from,
    s16 x,s16 y,const OverworldPickupRouteNativeTile *tile,s32 *out)
{
    OverworldPickupRouteWildWorld *w=raw;OverworldEntryRouteMemoRead *r=Read(w,2,8);
    if (r==NULL) return Missing(w);
    if (!Cached(w)) Save(w,r,w->entryMemo->native->support(raw,from,x,y,tile,&r->height));
    if (r->result==LEGAL) *out=r->height;
    return r->result;
}
static OverworldPickupRouteEdgeResult Occupancy(void *raw,const OverworldActorHandle *subject,
    const OverworldPickupRoutePosition *pose,u8 include)
{
    OverworldPickupRouteWildWorld *w=raw;OverworldEntryRouteMemoRead *r=Read(w,3,1);
    if (r==NULL) return Missing(w);
    if (!Cached(w)) Save(w,r,w->entryMemo->native->occupancy(raw,subject,pose,include));
    return r->result;
}
static OverworldPickupRouteEdgeResult Reservations(void *raw,const OverworldActorHandle *subject,
    const OverworldPickupRoutePosition *pose)
{
    OverworldPickupRouteWildWorld *w=raw;OverworldEntryRouteMemoRead *r=Read(w,4,1);
    if (r==NULL) return Missing(w);
    if (!Cached(w)) Save(w,r,w->entryMemo->native->reservations(raw,subject,pose));
    return r->result;
}
static OverworldPickupRouteEdgeResult EdgePolicy(void *raw,const OverworldPickupRouteNativePolicy *p,
    u8 kind,const OverworldPickupRoutePosition *from,const OverworldPickupRouteNativeTile *source,
    const OverworldPickupRoutePosition *to,const OverworldPickupRouteNativeTile *target)
{
    OverworldPickupRouteWildWorld *w=raw;
    OverworldEntryRouteMemoRead *r=Read(w,5,0);
    if (r==NULL) return Missing(w);
    if (!Cached(w)) Save(w,r,w->entryMemo->native->edgePolicy(raw,p,kind,from,source,to,target));
    return r->result;
}
static OverworldPickupRouteEdgeResult Hop(void *raw,const OverworldPickupRouteNativePolicy *p,
    u8 kind,u16 distance,const OverworldPickupRoutePosition *from,const OverworldPickupRoutePosition *to)
{
    OverworldPickupRouteWildWorld *w=raw;OverworldEntryRouteMemo *m=w->entryMemo;
    OverworldEntryRouteMemoRead *r=Read(w,6,0);
    if (r==NULL) return Missing(w);
    if (Cached(w)) return r->result;
    if ((kind!=OVERWORLD_PICKUP_ROUTE_NATIVE_HOP && kind!=OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE) || p->resolvedProfile==NULL || p->resolvedLane==NULL)
        { Save(w,r,INVALID);return INVALID; }
    OverworldActorHopPlanCall outer={0};int decision;
    if (!m->hopStarted) {
        m->hopInput=(OverworldActorHopPlanCall){0};
        m->hopInput.profile=p->resolvedProfile;m->hopInput.lane=p->resolvedLane;
        m->hopInput.operation=OVERWORLD_ACTOR_HOP_PLAN_VECTOR;
        m->hopInput.deltaX=to->x-from->x;m->hopInput.deltaY=to->y-from->y;
        decision=kind==OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE
            ? OVERWORLD_MOTION_DECISION_ACCEPTED:w->ops->hopPlan(&m->hopInput);
        if (kind==OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE) m->hopInput.distance=distance;
        if (decision!=OVERWORLD_MOTION_DECISION_ACCEPTED || m->hopInput.distance!=distance) {
            OverworldPickupRouteEdgeResult d=decision==OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY?DEFERRED:
                decision==OVERWORLD_MOTION_DECISION_DIRECTION?BLOCKED:INVALID;
            Save(w,r,d);return d;
        }
        m->hopInput.operation=OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY;
        m->hopInput.fieldSystem=w->field;m->hopInput.surfaceCatalog=w->catalog;
        m->hopInput.object=w->subjectObject;m->hopInput.startBaseY=from->baseY;
        m->hopInput.targetBaseY=to->baseY;m->hopInput.startX=from->x;m->hopInput.startY=from->y;
        m->hopInput.targetX=to->x;m->hopInput.targetY=to->y;
        m->hopInput.spotState=OVERWORLD_ACTOR_HOP_PLAN_FLAG_STRICT_HEIGHT;
        m->hop=(OverworldActorHopClearanceCursor){0};m->hop.version=OVERWORLD_ACTOR_HOP_CLEARANCE_VERSION;
        m->hop.size=sizeof(m->hop);m->hop.input=&m->hopInput;
        m->hop.objectFlags=w->preparedPhysical!=NULL?w->preparedPhysical->flags:w->subjectObject->flags;
        m->hop.fallbackBaseY=from->baseY;m->hop.playable=w->ops->playable;m->hop.behavior=w->ops->behavior;
        outer.operation=OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_BEGIN;outer.clearanceCursor=&m->hop;
        decision=w->ops->hopPlan(&outer);
        if (decision!=OVERWORLD_MOTION_DECISION_ACCEPTED
            && !(decision==OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY
                && m->hop.phase!=OVERWORLD_ACTOR_HOP_CLEARANCE_DONE)) {
            Save(w,r,INVALID);return INVALID;
        }
        m->hopStarted=1;
    }
    outer.operation=OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_STEP;outer.clearanceCursor=&m->hop;
    m->hop.readBudget=m->budget;decision=w->ops->hopPlan(&outer);
    if (m->hop.readsUsed>m->budget || m->hop.readsUsed>OVERWORLD_ENTRY_ROUTE_MAX_READS)
        { Save(w,r,INVALID);return INVALID; }
    m->budget-=m->hop.readsUsed;m->used+=m->hop.readsUsed;
    if (m->hop.phase!=OVERWORLD_ACTOR_HOP_CLEARANCE_DONE) return DEFERRED;
    OverworldPickupRouteEdgeResult d=decision==OVERWORLD_MOTION_DECISION_ACCEPTED?LEGAL:
        decision==OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY?DEFERRED:
        decision==OVERWORLD_MOTION_DECISION_BLOCKED?BLOCKED:INVALID;
    if (d==DEFERRED) m->hopStarted=0;
    Save(w,r,d);return d;
}
static OverworldPickupRouteEdgeResult Pickup(void *raw,const OverworldPickupRouteNativePolicy *p,
    const OverworldPickupRoutePosition *from,const OverworldPickupRoutePosition *to)
{ (void)raw;(void)p;(void)from;(void)to;return INVALID; }
static const OverworldPickupRouteNativeSeams sMemo={Binding,Terrain,Support,Occupancy,Reservations,EdgePolicy,Hop,Pickup};
const OverworldPickupRouteNativeSeams *OverworldEntryRoute_MemoSeams(void) { return &sMemo; }
void OverworldEntryRoute_ResetMemo(OverworldEntryRouteSearch *s)
{ s->memo=(OverworldEntryRouteMemo){0};s->world.entryMemo=&s->memo; }
static u8 Current(void *raw)
{ OverworldEntryRouteSearch *s=raw;return s->active && s->current!=NULL && s->current(s->owner,&s->receipt); }
static u8 Goal(void *raw,const OverworldPickupRoutePosition *pose)
{
    OverworldEntryRouteSearch *s=raw;
    if (!Current(s)) return 0;
    if (!s->reverse) return Same(pose,&s->goal,sizeof(*pose));
    const LocalMapObject *player=s->world.field->playerAvatar!=NULL
        ?s->world.field->playerAvatar->mapObject:NULL;
    return player!=NULL && (Abs(pose->x-player->xCurr)>=13 || Abs(pose->y-player->yCurr)>=11);
}
static u32 Score(void *raw,s16 x,s16 y)
{
    OverworldEntryRouteSearch *s=raw;int dx=Abs(x-s->goal.x),dy=Abs(y-s->goal.y);
    if (!s->reverse) return dx>dy?dx:dy;
    /* Prefer the nearest edge of the safe offscreen rectangle. */
    const LocalMapObject *player=s->world.field->playerAvatar!=NULL
        ?s->world.field->playerAvatar->mapObject:NULL;
    if (player==NULL) return 0xFFFFFFFFu;
    dx=Abs(x-player->xCurr);dy=Abs(y-player->yCurr);
    dx=dx>=13?0:13-dx;dy=dy>=11?0:11-dy;return dx<dy?dx:dy;
}
static OverworldPickupRouteEdgeResult Edge(void *raw,const OverworldPickupRoutePosition *from,
    const OverworldPickupRouteEdge *edge,OverworldPickupRoutePosition *out)
{
    OverworldEntryRouteSearch *s=raw;OverworldEntryRouteMemo *m=&s->memo;
    if (!Current(s)) return INVALID;
    if (!m->valid || !Same(&m->from,from,sizeof(*from)) || !Same(&m->edge,edge,sizeof(*edge))) {
        u8 budget=m->budget,used=m->used;const OverworldPickupRouteNativeSeams *native=m->native;
        OverworldEntryRoute_ResetMemo(s);m=&s->memo;m->native=native;
        m->from=*from;m->edge=*edge;m->valid=1;m->budget=budget;m->used=used;
        m->physicalPlayerMask=s->policy.playerTerrainMask;
        m->dynamic=s->query.dynamicRevision;m->scope=s->query.scopeRevision;m->policy=s->query.movementPolicyRevision;
    }
    const OverworldPickupRoutePosition *destination;
    const OverworldPickupRouteCachedEdge *cached=OverworldPickupRoute_ReadMemo(
        &s->ledger->route,from,edge,&destination);
    if (cached && OverworldCargoQuery_Unchanged(s->ledger,from,destination,cached->dynamicRevision)) {
        *out=*destination;return LEGAL;
    }
    m->cursor=0;s->native.query=&s->query;
    if (s->reverse && (edge->tag>>OVERWORLD_PICKUP_ROUTE_NATIVE_KIND_SHIFT)==OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE
        && ((Abs(edge->dx)==2 && !edge->dy) || (Abs(edge->dy)==2 && !edge->dx))
        && !from->reserved && from->x>=0 && from->y>=0
        && from->x>=s->query.bounds.minX && from->x<=s->query.bounds.maxX
        && from->y>=s->query.bounds.minY && from->y<=s->query.bounds.maxY
        && from->x+edge->dx>=0 && from->y+edge->dy>=0
        && from->x+edge->dx>=s->query.bounds.minX && from->x+edge->dx<=s->query.bounds.maxX
        && from->y+edge->dy>=s->query.bounds.minY && from->y+edge->dy<=s->query.bounds.maxY) {
        /* Reject a non-ledge midpoint before predecessor/source/target
         * height work. A positive result never replaces full admission. */
        OverworldPickupRouteEdgeResult d=OverworldPickupRouteNative_ValidateBinding(&s->native);
        if (d!=LEGAL) return d;
        if (!(s->policy.allowedKinds&(1u<<OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE))
            || !(s->policy.directions&OVERWORLD_PICKUP_ROUTE_NATIVE_CARDINAL)) return BLOCKED;
        const OverworldWildBehaviorProfile *profile=s->policy.resolvedProfile;
        if (profile==NULL || s->world.ops==NULL || s->world.ops->behavior==NULL) return INVALID;
        OverworldEntryRouteMemoRead *r=Read(&s->world,OVERWORLD_ENTRY_MEMO_LEDGE_BEHAVIOR,1);
        if (r==NULL) return Missing(&s->world);
        if (!Cached(&s->world)) {
            u8 behavior=s->world.ops->behavior(s->world.field,from->x+edge->dx/2,from->y+edge->dy/2);
            u8 direction=edge->dx?2+(edge->dx<0):(edge->dy<0);
            d=behavior==0xFF?DEFERRED:OverworldPreparedMovement_LedgeDirectionLegal(
                profile->owner.jumpLevel,direction,behavior)?LEGAL:BLOCKED;
            r->tile.behavior=behavior;Save(&s->world,r,d);
        }
        if (r->result!=LEGAL) return r->result;
    }
    if (!s->reverse) return OverworldPickupRouteNative_Classify(&s->native,from,edge,out);
    OverworldPickupRoutePosition predecessor,forwardTarget;
    OverworldPickupRouteNativeLandingCall landing={0};
    landing.version=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION;landing.size=sizeof(landing);
    landing.policy=&s->policy;landing.seams=&sMemo;landing.world=&s->world;
    landing.origin=*from;landing.targetX=from->x+edge->dx;landing.targetY=from->y+edge->dy;
    landing.destination=&predecessor;
    OverworldPickupRouteEdgeResult d=OverworldPickupRouteNative_Landing(&landing);
    if (d!=LEGAL) return d;
    static const u8 opposite[8]={1,0,3,2,7,6,5,4};
    OverworldPickupRouteEdge forward={-edge->dx,-edge->dy,
        (edge->tag&~7u)|opposite[edge->tag&7]};
    d=OverworldPickupRouteNative_Classify(&s->native,&predecessor,&forward,&forwardTarget);
    if (d==LEGAL && !Same(&forwardTarget,from,sizeof(*from))) return BLOCKED;
    if (d==LEGAL) *out=predecessor;
    return d;
}
OverworldPickupRouteStatus OverworldEntryRoute_Begin(OverworldEntryRouteSearch *s,
    const OverworldEntryRouteRequest *receipt,const OverworldPickupRouteWildWorld *world,
    const OverworldPickupRouteNativePolicy *policy,OverworldCargoQueryState *ledger,
    const OverworldPickupRouteEdge *edges,u16 count,const OverworldPickupRouteBounds *bounds,
    u32 scope,u32 policyRevision,u32 dynamic,u8 (*current)(void *,const OverworldEntryRouteRequest *),void *owner)
{
    if (s==NULL || ledger==NULL || ledger->storage==NULL || receipt==NULL || receipt->version!=OVERWORLD_ENTRY_ROUTE_VERSION
        || receipt->size!=sizeof(*receipt) || !receipt->serial || world==NULL || policy==NULL
        || bounds==NULL || receipt->slot>=OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS || current==NULL
        || !current(owner,receipt)) return OVERWORLD_PICKUP_ROUTE_INVALID;
    *s=(OverworldEntryRouteSearch){0};s->ledger=ledger;s->receipt=*receipt;s->world=*world;s->policy=*policy;
    s->physical=receipt->physical;s->world.preparedPhysical=receipt->operation==OVERWORLD_ENTRY_ROUTE_PREPARE?&s->physical:NULL;
    s->reverse=receipt->operation==OVERWORLD_ENTRY_ROUTE_PREPARE;s->active=1;s->current=current;s->owner=owner;
    s->goal=receipt->destination;s->world.entryMemo=&s->memo;
    s->world.scopeRevision=scope;s->world.movementPolicyRevision=policyRevision;s->world.dynamicRevision=dynamic;
    s->extension=(OverworldPickupRouteExtension){OVERWORLD_PICKUP_ROUTE_EXTENSION_VERSION,sizeof(s->extension),
        s->reverse?OVERWORLD_PICKUP_ROUTE_EXTENSION_PREPARED:OVERWORLD_PICKUP_ROUTE_EXTENSION_ENTRY_ACTOR,
        s->reverse?OVERWORLD_PICKUP_ROUTE_EXTENSION_REVERSE:0,0,Current,Goal,Score,s};
    s->query.version=OVERWORLD_PICKUP_ROUTE_VERSION;s->query.size=sizeof(s->query);
    s->query.subject=receipt->actor;s->query.bounds=*bounds;s->query.origin=receipt->destination;
    if (!s->reverse) s->query.origin=receipt->origin;
    s->query.scopeRevision=scope;s->query.movementPolicyRevision=policyRevision;s->query.dynamicRevision=dynamic;
    s->query.goalRevision=receipt->serial;s->query.edges=edges;s->query.edgeCount=count;
    s->query.extension=&s->extension;s->query.context=s;s->query.legalEdge=Edge;
    s->native=(OverworldPickupRouteNativeContext){OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION,sizeof(s->native),
        &s->query,&s->policy,&sMemo,&s->world,{0}};
    s->memo.native=OverworldPickupRouteWild_GetSeams(&s->world);
    if (s->memo.native==NULL) { s->active=0;return OVERWORLD_PICKUP_ROUTE_INVALID; }
    OverworldCargoQuery_Clear(ledger);ledger->query=s->query;
    return OverworldPickupRoute_Begin(&ledger->route,&s->query,&ledger->storage->workspace);
}
OverworldPickupRouteStatus OverworldEntryRoute_Resume(OverworldEntryRouteSearch *s,
    u32 dynamic,const OverworldCargoQueryChangedTile *changes,u16 changeCount,u8 complete,
    OverworldEntryRoutePath *path,OverworldEntryRouteReceipt *out)
{
    if (out==NULL || s==NULL || path==NULL) return OVERWORLD_PICKUP_ROUTE_INVALID;
    *out=(OverworldEntryRouteReceipt){0};out->version=OVERWORLD_ENTRY_ROUTE_VERSION;out->size=sizeof(*out);
    out->serial=s->receipt.serial;out->queued=s->reverse;out->target=s->goal;out->status=OVERWORLD_PICKUP_ROUTE_PENDING;
    if (!Current(s)) return out->status=OVERWORLD_PICKUP_ROUTE_INVALID;
    if (++s->updates>OVERWORLD_ENTRY_ROUTE_MAX_UPDATES) return out->status=OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT;
    s->ledger->query.dynamicRevision=dynamic;s->ledger->lastWork=(OverworldCargoQueryWork){0};
    OverworldCargoQueryInput observed={0};observed.changedTiles=changes;
    observed.changedTileCount=changeCount;observed.changesComplete=complete;
    if ((changeCount && changes==NULL) || !OverworldCargoQuery_ObserveChanges(s->ledger,&observed))
        return out->status=OVERWORLD_PICKUP_ROUTE_INVALID;
    OverworldPickupRoutePosition edgeEnd=s->memo.from;
    edgeEnd.x+=s->memo.edge.dx;edgeEnd.y+=s->memo.edge.dy;
    if (s->memo.valid && !OverworldCargoQuery_Unchanged(s->ledger,&s->memo.from,&edgeEnd,s->memo.dynamic)) {
        const OverworldPickupRouteNativeSeams *native=s->memo.native;
        OverworldEntryRoute_ResetMemo(s);s->memo.native=native;
    }
    s->memo.dynamic=dynamic;s->memo.budget=OVERWORLD_ENTRY_ROUTE_MAX_READS;s->memo.used=0;
    s->query.dynamicRevision=dynamic;s->world.dynamicRevision=dynamic;
    OverworldPickupRouteResult result;u8 work=16;
    if (s->ledger->route.phase==OVERWORLD_PICKUP_ROUTE_PHASE_PROOF) {
        s->ledger->route.reserved[0]=OverworldCargoQuery_ProofUnchanged(s->ledger,8192)
            ?OVERWORLD_PICKUP_ROUTE_PROOF_SUFFIX_CURRENT:0;
        s->ledger->route.hashIndex=dynamic;
        work-=(s->ledger->lastWork.witnessProbes+511)/512;
    }
    OverworldPickupRouteStatus status=OverworldPickupRoute_Resume(&s->ledger->route,&s->query,work,&result);
    out->status=status;out->readsUsed=s->memo.used;
    if (status!=OVERWORLD_PICKUP_ROUTE_REACHABLE) return status;
    /* Camera/Player can move during a proof. A completed route still needs
     * its exact origin outside the current safe rectangle before creation. */
    if (s->reverse && !Goal(s,&s->ledger->route.workspace->nodes[s->ledger->route.goalNode].position)) {
        OverworldPickupRoute_Begin(&s->ledger->route,&s->query,&s->ledger->storage->workspace);
        return out->status=OVERWORLD_PICKUP_ROUTE_PENDING;
    }
    u16 count=OverworldPickupRoute_CopyForwardWitness(&s->ledger->route,path->edgeTags,path->endpoints,OVERWORLD_ENTRY_ROUTE_MAX_STEPS);
    if (count==NONE) return out->status=OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT;
    u8 sameTrip=path->valid && path->serial==s->receipt.serial
        && Same(&path->actor,&s->receipt.actor,sizeof(path->actor));
    if (!sameTrip) path->noProgress=0;
    path->actor=s->receipt.actor;path->serial=s->receipt.serial;path->policy=s->query.movementPolicyRevision;path->scope=s->query.scopeRevision;
    path->origin=s->ledger->route.workspace->nodes[s->reverse?s->ledger->route.goalNode:s->ledger->route.rootNode].position;
    path->target=s->goal;path->expected=path->origin;path->count=count;path->next=0;path->accepted=0;path->valid=1;
    out->origin=path->origin;out->actor=path->actor;out->stepsRemaining=count;
    if (count) { out->hasNextStep=1;out->nextStep=path->endpoints[0];out->edgeTag=path->edgeTags[0]; }
    return status;
}
OverworldPickupRouteStatus OverworldEntryRoute_ValidateStep(OverworldEntryRouteSearch *s,
    const OverworldEntryRoutePath *path,u32 dynamic,const OverworldCargoQueryChangedTile *changes,
    u16 count,u8 complete,OverworldEntryRouteReceipt *out)
{
    if (s==NULL || path==NULL || out==NULL || !Current(s) || s->reverse
        || !path->valid || path->next>=path->count) return OVERWORLD_PICKUP_ROUTE_INVALID;
    s32 dx=(s32)path->endpoints[path->next].x-path->expected.x;
    s32 dy=(s32)path->endpoints[path->next].y-path->expected.y;
    if ((((u32)dx + 32768u) | ((u32)dy + 32768u)) > 65535u)
        return OVERWORLD_PICKUP_ROUTE_INVALID;
    OverworldPickupRouteEdge edge={(s16)dx,(s16)dy,path->edgeTags[path->next]};
    if (++s->updates>OVERWORLD_ENTRY_ROUTE_MAX_UPDATES) return OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT;
    s->ledger->query.dynamicRevision=dynamic;
    OverworldCargoQueryInput observed={0};observed.changedTiles=changes;
    observed.changedTileCount=count;observed.changesComplete=complete;
    if (!OverworldCargoQuery_ObserveChanges(s->ledger,&observed)) return OVERWORLD_PICKUP_ROUTE_INVALID;
    if (s->memo.valid && !OverworldCargoQuery_Unchanged(s->ledger,&path->expected,
            &path->endpoints[path->next],s->memo.dynamic)) OverworldEntryRoute_ResetMemo(s);
    s->memo.native=OverworldPickupRouteWild_GetSeams(&s->world);
    if (s->memo.native==NULL) return OVERWORLD_PICKUP_ROUTE_INVALID;
    s->query.dynamicRevision=dynamic;s->world.dynamicRevision=dynamic;s->memo.dynamic=dynamic;
    s->memo.budget=OVERWORLD_ENTRY_ROUTE_MAX_READS;s->memo.used=0;
    if (s->memo.guideReady) {
        return OverworldEntryRoute_Guide(path,&path->actor,&path->expected,
            s->query.movementPolicyRevision,out)?OVERWORLD_PICKUP_ROUTE_REACHABLE:OVERWORLD_PICKUP_ROUTE_INVALID;
    }
    OverworldPickupRoutePosition endpoint;
    OverworldPickupRouteEdgeResult decision=Edge(s,&path->expected,&edge,&endpoint);
    out->readsUsed=s->memo.used;
    if (decision==DEFERRED) return OVERWORLD_PICKUP_ROUTE_PENDING;
    if (decision!=LEGAL) return decision==BLOCKED?OVERWORLD_PICKUP_ROUTE_UNREACHABLE:
        decision==LIMIT?OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT:OVERWORLD_PICKUP_ROUTE_INVALID;
    if (!Same(&endpoint,&path->endpoints[path->next],sizeof(endpoint))) return OVERWORLD_PICKUP_ROUTE_UNREACHABLE;
    s->memo.guideReady=1;
    /* The final proof update never also runs START. The next current update
     * observes changes again, then publishes a zero-read ready receipt. */
    return OVERWORLD_PICKUP_ROUTE_PENDING;
}
u8 OverworldEntryRoute_Guide(const OverworldEntryRoutePath *p,const OverworldActorHandle *actor,
    const OverworldPickupRoutePosition *pose,u32 policy,OverworldEntryRouteReceipt *out)
{
    if (p==NULL || actor==NULL || pose==NULL || out==NULL || !p->valid
        || !Same(actor,&p->actor,sizeof(*actor)) || !Same(pose,&p->expected,sizeof(*pose))
        || policy!=p->policy || p->next>=p->count) return 0;
    *out=(OverworldEntryRouteReceipt){0};out->version=OVERWORLD_ENTRY_ROUTE_VERSION;out->size=sizeof(*out);
    out->serial=p->serial;out->actor=p->actor;out->target=p->target;out->nextStep=p->endpoints[p->next];
    out->edgeTag=p->edgeTags[p->next];out->stepsRemaining=p->count-p->next;out->hasNextStep=1;
    out->status=OVERWORLD_PICKUP_ROUTE_REACHABLE;return 1;
}
u8 OverworldEntryRoute_Confirm(OverworldEntryRoutePath *p,const OverworldActorHandle *actor,
    const OverworldPickupRoutePosition *pose,const OverworldActorRuntimeSlot *slot)
{
    if (p==NULL || !p->valid || actor==NULL || pose==NULL || slot==NULL || !p->accepted
        || !Same(actor,&p->actor,sizeof(*actor)) || !Same(actor,&slot->snapshot.handle,sizeof(*actor))
        || p->next>=p->count) return 0;
    const OverworldMotionState *motion=&slot->motion;
    const OverworldMotionPlan *plan=&motion->plan;
    if (slot->snapshot.motionPhase!=OVERWORLD_ACTOR_PHASE_IDLE || slot->snapshot.reservationId) return 0;
    p->accepted=0;
    if (!motion->commitPublished || slot->snapshot.commitSequence<=p->acceptedSequence
        || plan->startX!=p->expected.x || plan->startY!=p->expected.y || plan->startBaseY!=p->expected.baseY
        || plan->targetX!=p->endpoints[p->next].x || plan->targetY!=p->endpoints[p->next].y
        || plan->targetBaseY!=p->endpoints[p->next].baseY
        || !Same(pose,&p->endpoints[p->next],sizeof(*pose))) return 0;
    p->expected=*pose;p->next++;p->noProgress=0;return 1;
}
u8 OverworldEntryRoute_IdleStall(OverworldEntryRoutePath *p,const OverworldActorHandle *actor,
    u8 idle,u8 offscreen)
{
    if (p==NULL || actor==NULL || !p->valid || !Same(actor,&p->actor,sizeof(*actor))) return 0;
    if (idle && p->noProgress<OVERWORLD_ENTRY_ROUTE_STALL_FRAMES) p->noProgress++;
    return p->noProgress>=OVERWORLD_ENTRY_ROUTE_STALL_FRAMES && offscreen;
}

/* Synchronous native glue; graph/Hop ownership and public Entry reducer stay above. */
#include "overworld_cargo_query_wild.h"
#include "constants/species.h"
#include "overworld_wild_runtime_state_internal.h"
#define OW_WILD_RUNTIME(s) ((OverworldWildOverlayRuntimeState *)(s)->movementRuntimeState)
#define OW_WILD_SPAWNER_SPOT_STATE_CHILL OW_WILD_SPOT_STATE_OWNER
#define OW_WILD_SPAWNER_THROW_TARGET_NONE 0
#define OW_WILD_BEHAVIOR_LOCOMOTION_NONE 0
#define OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN 3
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE 0xFF
#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN 4
#define OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN 9
#define OW_WILD_BEHAVIOR_LOCOMOTION_APPEAR_HOP 7
#define OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE 8
#define OW_WILD_SPAWNER_SPAWN_FLY_IN_DISTANCE 16
#define OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_WIDTH_TILES 8
#define OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_HEIGHT_TILES 6
#define OW_WILD_SPAWNER_OFFSCREEN_SAFE_MARGIN_TILES 4
#define OW_WILD_SPAWNER_OFFSCREEN_COMMIT_RUNWAY_TILES 1
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP 0
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN 1
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT 2
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT 3
static u32 NativeArm(const OverworldEntryRouteNativeControl *c, OverworldWildSpawnState *state, OverworldWildSpawnTerrain terrain,int slot,const OverworldWildPreparedSpawn *prepared)
{
    OverworldWildOverlayRuntimeState *runtime=OW_WILD_RUNTIME(state);
    if (runtime->queuedSpawnSlotPlusOne && (runtime->queuedSpawnSlotPlusOne!=slot+1
            || prepared!=&runtime->queuedSpawn)) return 0;
    if (prepared!=&runtime->queuedSpawn) runtime->queuedSpawn=*prepared;
    if (!runtime->queuedSpawnSlotPlusOne) {
        /* Direct public queues never inherit ordinary refill ownership. */
        runtime->refillQueuedSerial=0;
        if (++runtime->queuedSpawnSerial==0) ++runtime->queuedSpawnSerial;
    }
    runtime->queuedSpawnTerrain=terrain;runtime->queuedSpawnSlotPlusOne=slot+1;
    if (prepared->behaviorResolution.primitives.spawnLocomotion
            ==OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN) {
        runtime->entryRouteReceipt=(OverworldEntryRouteReceipt){0};
        runtime->entryRouteReceipt.version=OVERWORLD_ENTRY_ROUTE_VERSION;
        runtime->entryRouteReceipt.size=sizeof(runtime->entryRouteReceipt);
        runtime->entryRouteReceipt.serial=runtime->queuedSpawnSerial;
        runtime->entryRouteReceipt.status=OVERWORLD_PICKUP_ROUTE_PENDING;
        runtime->entryRouteReceipt.queued=1;
    }
    return runtime->queuedSpawnSerial;
}
static OverworldPickupRouteStatus NativeQueryEntry(const OverworldCargoQueryWildCall *base,const OverworldEntryRouteNativeControl *c,OverworldWildSpawnState *state,
    FieldSystem *field,int slot,const OverworldWildBehaviorProfile *profile,u8 operation,
    const OverworldWildPreparedSpawn *prepared,u8 accepted,u8 usableIdle,u32 startCommitSequence,OverworldEntryRouteReceipt *out)
{
    const OverworldActorSystemState *actors=c->ops->actors();
    if(actors==NULL || state==NULL || state->movementRuntimeState==NULL
        || slot<0 || slot>=OW_WILD_MAX_SPAWNS || slot==OW_WILD_FOLLOWER_SLOT) return OVERWORLD_PICKUP_ROUTE_INVALID;
    OverworldWildOverlayRuntimeState *runtime=OW_WILD_RUNTIME(state);
    OverworldPickupRouteWildWorld world;OverworldCargoQueryWildCall call={0};
    OverworldEntryRouteCommand command={0};OverworldCargoQueryResult result;
    c->ops->initWorld(state,slot,&world);world.field=field;
    command.request.version=OVERWORLD_ENTRY_ROUTE_VERSION;command.request.size=sizeof(command.request);
    command.request.operation=operation;command.request.slot=slot;
    command.request.fieldEpoch=actors->fieldEpoch;command.request.mapGeneration=actors->mapGeneration;
    command.request.expectedSlotGeneration=actors->slots[slot].snapshot.handle.generation;
    command.request.serial=operation==OVERWORLD_ENTRY_ROUTE_PREPARE || operation==OVERWORLD_ENTRY_ROUTE_ADOPT
        ?runtime->queuedSpawnSerial:runtime->entryRouteSerial[slot];
    command.request.physical=(OverworldEntryRoutePhysical){MAPOBJECTFLAG_ACTIVE|MAPOBJECTFLAG_UNK2
        |MAPOBJECTFLAG_UNK11|MAPOBJECTFLAG_UNK12,0,-1,-1,0,0};
    if (prepared!=NULL) {
        command.request.destination=(OverworldPickupRoutePosition){prepared->startup.targetX,
            prepared->startup.targetY,0,OVERWORLD_PICKUP_ROUTE_NATIVE_GROUND,0};
    } else {
        command.request.destination=(OverworldPickupRoutePosition){state->movementSpawnRunTargetX[slot],
            state->movementSpawnRunTargetY[slot],0,OVERWORLD_PICKUP_ROUTE_NATIVE_GROUND,0};
    }
    command.request.physical.targetX=command.request.destination.x;
    command.request.physical.targetY=command.request.destination.y;
    if(operation==OVERWORLD_ENTRY_ROUTE_PREPARE) world.subjectObject=NULL;
    else {
        command.request.actor=actors->slots[slot].snapshot.handle;
        LocalMapObject *object=state->spawns[slot].object;
        if(object==NULL) return OVERWORLD_PICKUP_ROUTE_INVALID;
        command.request.origin=(OverworldPickupRoutePosition){object->xCurr,object->yCurr,(s32)object->posVec[1],
            actors->slots[slot].policy.targetSurfaceId,0};
        LocalMapObject *player=field->playerAvatar!=NULL?field->playerAvatar->mapObject:NULL;
        command.safelyOffscreen=player!=NULL && (Abs(object->xCurr-player->xCurr)>=13
            || Abs(object->yCurr-player->yCurr)>=11);
    }
    command.receipt=out;command.accepted=accepted;command.usableIdle=usableIdle;
    command.startCommitSequence=startCommitSequence;
    call.world=&world;call.profile=profile;call.entry=&command;call.routeOperation=OVERWORLD_FIELD_ROUTE_ENTRY;
    call.allocate=base->allocate;call.freeSize=base->freeSize;call.heapId=base->heapId;
    call.allowedTerrainMask=profile!=NULL?c->ops->allowed(profile,OW_WILD_SPAWNER_SPOT_STATE_CHILL):0;
    call.locomotion=profile!=NULL?profile->owner.chillAction:0;
    return OverworldCargoQueryWild_Tick(&call,&result);
}
static BOOL NativePrepare(const OverworldCargoQueryWildCall *base,const OverworldEntryRouteNativeControl *c,OverworldWildSpawnState *state,FieldSystem *field,
    OverworldWildSpawnTerrain terrain,int slot,OverworldWildPreparedSpawn *prepared)
{
    OverworldWildOverlayRuntimeState *runtime=OW_WILD_RUNTIME(state);
    if(!NativeArm(c,state,terrain,slot,prepared)) return FALSE;
    if(prepared!=&runtime->queuedSpawn) {
        runtime->refillPositionChecksRemaining=OW_WILD_SPAWN_ROUTE_PENDING;
        return FALSE; /* The caller may free its packet. Normal maintenance owns the copy. */
    }
    OverworldEntryRouteReceipt receipt;
    OverworldPickupRouteStatus status=NativeQueryEntry(base,c,state,field,slot,
        &prepared->behaviorResolution.profile,OVERWORLD_ENTRY_ROUTE_PREPARE,prepared,0,0,0,&receipt);
    if(status==OVERWORLD_PICKUP_ROUTE_PENDING) {
        runtime->refillPositionChecksRemaining=OW_WILD_SPAWN_ROUTE_PENDING;return FALSE;
    }
    if(status!=OVERWORLD_PICKUP_ROUTE_REACHABLE) {
        runtime->refillPositionChecksRemaining=0;runtime->queuedSpawnSlotPlusOne=0;return FALSE;
    }
    prepared->position.startX=receipt.origin.x;prepared->position.startY=receipt.origin.y;
    prepared->startup.startX=receipt.origin.x;prepared->startup.startY=receipt.origin.y;
    prepared->startup.targetBaseY=receipt.target.baseY;
    prepared->startup.locomotion=OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN;
    runtime->refillPositionChecksRemaining=OW_WILD_SPAWN_ROUTE_READY;
    return FALSE; /* Route completion and native finalization have separate updates. */
}
static int AirborneScore(
    u8 direction,
    int targetDx,
    int targetDy)
{
    if (direction < OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT
        && Abs(targetDx)
            > OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_WIDTH_TILES) {
        return 0;
    }
    if (direction >= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT
        && Abs(targetDy)
            > OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_HEIGHT_TILES) {
        return 0;
    }
    if (direction == OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP) {
        return OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_HEIGHT_TILES - targetDy;
    }
    if (direction == OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN) {
        return OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_HEIGHT_TILES + targetDy;
    }
    return OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_WIDTH_TILES
        + (direction == OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
            ? targetDx
            : -targetDx);
}
static BOOL AirborneOrigin(const OverworldCargoQueryWildCall *base,
    FieldSystem *fieldSystem,
    int maximumDistance,
    int targetX,
    int targetY,
    int *startX,
    int *startY)
{
    int playerX = fieldSystem->playerAvatar->mapObject->xCurr;
    int playerY = fieldSystem->playerAvatar->mapObject->yCurr;
    int targetDx = targetX - playerX;
    int targetDy = targetY - playerY;
    u8 triedDirections = 0;
    int rank;

    for (rank = 0; rank < 4; rank++) {
        int bestVisibleTravel = -1;
        u8 candidateDirection = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE;
        u8 direction;
        int entryDistance;
        int minimumCandidateDistance;
        int candidateDistance;

        for (direction = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP;
             direction <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT;
             direction++) {
            int visibleTravel;

            if ((triedDirections & (1u << direction)) != 0) {
                continue;
            }
            visibleTravel = AirborneScore(
                direction,
                targetDx,
                targetDy);
            if (visibleTravel > bestVisibleTravel) {
                bestVisibleTravel = visibleTravel;
                candidateDirection = direction;
            }
        }
        if (candidateDirection == OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE) {
            return FALSE;
        }
        triedDirections |= 1u << candidateDirection;
        entryDistance = AirborneScore(
            candidateDirection,
            targetDx,
            targetDy);
        minimumCandidateDistance = maximumDistance;
        for (candidateDistance = maximumDistance;
             candidateDistance >= minimumCandidateDistance;
             candidateDistance--) {
            int candidateX = targetX
                - (candidateDirection==2?-1:candidateDirection==3?1:0)
                    * candidateDistance;
            int candidateY = targetY
                - (candidateDirection==0?-1:candidateDirection==1?1:0)
                    * candidateDistance;

            if (candidateX < 0
                || candidateY < 0
                || entryDistance >= maximumDistance
                || (Abs(candidateX - playerX)
                        < OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_WIDTH_TILES
                            + OW_WILD_SPAWNER_OFFSCREEN_SAFE_MARGIN_TILES
                            + OW_WILD_SPAWNER_OFFSCREEN_COMMIT_RUNWAY_TILES
                    && Abs(candidateY - playerY)
                        < OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_HEIGHT_TILES
                            + OW_WILD_SPAWNER_OFFSCREEN_SAFE_MARGIN_TILES
                            + OW_WILD_SPAWNER_OFFSCREEN_COMMIT_RUNWAY_TILES)
                || base->world->ops->behavior(fieldSystem,candidateX,candidateY)==0xFF) {
                continue;
            }
            *startX = candidateX;
            *startY = candidateY;
            return TRUE;
        }
    }
    return FALSE;
}
static BOOL NativeAirborneStart(const OverworldCargoQueryWildCall *base,
    FieldSystem *fieldSystem,
    OverworldWildSpawnStartup *startup,
    u8 locomotion)
{
    if(fieldSystem->playerAvatar==NULL || fieldSystem->playerAvatar->mapObject==NULL) return FALSE;
    int startX;
    int startY;
    if (!AirborneOrigin(
            base,fieldSystem,
            locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN
                ? OW_WILD_SPAWNER_SPAWN_FLY_IN_DISTANCE
                : OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE,
            startup->targetX,
            startup->targetY,
            &startX,
            &startY)) {
        return FALSE;
    }

    startup->startX = (s16)startX;
    startup->startY = (s16)startY;
    startup->locomotion = locomotion;
    startup->hopDirection = startX == startup->targetX
        ? startY < startup->targetY
        : OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT
            + (startX < startup->targetX);
    return TRUE;
}
static BOOL NativeStartup(const OverworldCargoQueryWildCall *base,const OverworldEntryRouteNativeControl *c,
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    const OverworldWildBehaviorPrimitives *primitives,
    OverworldWildSpawnPosition *position,
    OverworldWildSpawnStartup *startup)
{
    startup->targetX = (s16)position->startX;
    startup->targetY = (s16)position->startY;
    startup->startX = startup->targetX;
    startup->startY = startup->targetY;
    startup->locomotion = OW_WILD_BEHAVIOR_LOCOMOTION_NONE;

    if (primitives->spawnLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN) {
        return FALSE; /* Move entry is admitted by PrepareMoveEntry before this generic branch. */
    } else if (primitives->spawnLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN) {
        return NativeAirborneStart(base,
            fieldSystem,
            startup,
            OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN);
    } else if (primitives->spawnLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN) {
        if(fieldSystem->playerAvatar==NULL || fieldSystem->playerAvatar->mapObject==NULL) return FALSE;
        startup->targetBaseY = c->ops->groundHeight(
            fieldSystem,
            fieldSystem->playerAvatar->mapObject,
            startup->targetX,
            startup->targetY);
        return NativeAirborneStart(base,
            fieldSystem,
            startup,
            OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN);
    } else if (primitives->spawnLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_APPEAR_HOP) {
        startup->locomotion = OW_WILD_BEHAVIOR_LOCOMOTION_APPEAR_HOP;
    }
    return TRUE;
}
static BOOL NativeFinalize(const OverworldCargoQueryWildCall *base,const OverworldEntryRouteNativeControl *c,
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    int slot,
    OverworldWildPreparedSpawn *prepared)
{
    BOOL isFollower = slot == OW_WILD_FOLLOWER_SLOT;
    u8 pendingStage = 0;

    if (state == NULL
        || fieldSystem == NULL
        || fieldSystem->savedata == NULL
        || prepared == NULL
        || prepared->encounter.species == SPECIES_NONE
        || prepared->encounter.level == 0) {
        return FALSE;
    }

    if (!isFollower
        && state->movementRuntimeState != NULL
        && prepared == &OW_WILD_RUNTIME(state)->queuedSpawn) {
        pendingStage = OW_WILD_RUNTIME(state)->refillPositionChecksRemaining;
    }
    if (prepared->startup.locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_NONE) {
        c->ops->resolve(
            prepared,
            terrain,
            isFollower
                ? OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER
                : -1);
        if (!isFollower
            && c->ops->limit(
                state,
                prepared->behaviorResolution.behaviorLimitKey,
                &prepared->behaviorResolution.profile)) {
            return FALSE;
        }
        /* The prepared value is single-use. Keep resolved metadata across the
         * later one-candidate destination updates instead of repeating it. */
        prepared->startup.locomotion = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE;
    }

    /* Direct Move callers may release their packet after FALSE. Own it
     * before the first resumable destination update, not after that scan. */
    if (!isFollower && state->movementRuntimeState!=NULL
        && prepared!=&OW_WILD_RUNTIME(state)->queuedSpawn
        && prepared->behaviorResolution.primitives.spawnLocomotion
            ==OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN) {
        if (NativeArm(c,state,terrain,slot,prepared))
            OW_WILD_RUNTIME(state)->refillPositionChecksRemaining=OW_WILD_SPAWN_MOVE_DESTINATION_PENDING;
        return FALSE;
    }

    /*
     * Followers prefer their configured destination, but retain the player
     * tile supplied by TrySpawnFollower when wild placement rules reject it.
     */
    if (pendingStage < OW_WILD_SPAWN_ROUTE_READY || pendingStage == OW_WILD_PROFILE_DESTINATION_SCAN_PENDING) {
        if (!c->ops->destination(
                state,
                fieldSystem,
                terrain,
                &prepared->behaviorResolution.profile,
                &prepared->position)
            && !isFollower) {
            return FALSE;
        }
        if (pendingStage == OW_WILD_PROFILE_DESTINATION_SCAN_PENDING) {
            OW_WILD_RUNTIME(state)->refillPositionChecksRemaining =
                OW_WILD_SPAWN_STARTUP_PENDING;
            return FALSE;
        }
    } else {
        /* The startup step is terminal, including an invalid entry origin. */
        OW_WILD_RUNTIME(state)->refillPositionChecksRemaining = 0;
    }
    if (!isFollower && prepared->behaviorResolution.primitives.spawnLocomotion
            ==OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN) {
        if(pendingStage!=OW_WILD_SPAWN_ROUTE_READY) {
            prepared->startup.targetX=prepared->position.startX;
            prepared->startup.targetY=prepared->position.startY;
            return NativePrepare(base,c,state,fieldSystem,terrain,slot,prepared);
        }
    } else if (!NativeStartup(base,c,state,fieldSystem,terrain,
            &prepared->behaviorResolution.primitives,&prepared->position,&prepared->startup)) return FALSE;
    if (isFollower) {
        /* Party ownership supplies the canonical personality and shiny state. */
        return TRUE;
    }
    return c->ops->personality(fieldSystem,prepared);
}
static BOOL NativeGuide(const OverworldCargoQueryWildCall *base,const OverworldEntryRouteNativeControl *c,OverworldWildSpawnState *state,int slot,
    LocalMapObject *object,const OverworldWildBehaviorProfile *profile,const OverworldWildBehaviorPrimitives *primitives)
{
    OverworldEntryRouteReceipt receipt;
    OverworldPickupRouteStatus status=NativeQueryEntry(base,c,state,state->movementFieldSystem,slot,
        profile,OVERWORLD_ENTRY_ROUTE_GUIDE,NULL,0,1,0,&receipt);
    if(status==OVERWORLD_PICKUP_ROUTE_UNREACHABLE && receipt.queued==2
        && state->movementActorControlModes[slot]==OW_WILD_ACTOR_CONTROL_AUTONOMOUS
        && state->movementQueuedBattleSlot!=slot
        && OW_WILD_RUNTIME(state)->throwState.targets[slot]==OW_WILD_SPAWNER_THROW_TARGET_NONE
        && OW_WILD_RUNTIME(state)->returnMoves[slot].phase==OW_WILD_RETURN_NONE) {
        c->ops->remove(state,state->movementFieldSystem,slot);return TRUE;
    }
    if(status!=OVERWORLD_PICKUP_ROUTE_REACHABLE || !receipt.hasNextStep) return FALSE;
    u32 startCommitSequence=0;
    BOOL started=c->ops->start(state,slot,object,profile,primitives,&receipt,&startCommitSequence);
    if(started) (void)NativeQueryEntry(base,c,state,state->movementFieldSystem,slot,profile,
        OVERWORLD_ENTRY_ROUTE_GUIDE,NULL,1,0,startCommitSequence,&receipt);
    return started;
}
static BOOL NativeUpdate(const OverworldCargoQueryWildCall *base,const OverworldEntryRouteNativeControl *c,
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object)
{
    int objectX;
    int objectY;
    int targetX;
    int targetY;
    OverworldActorPolicyView policy;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || state->movementSpawnRunActive[slot] != OW_WILD_SPAWN_ENTRY_MOVE
        || !state->spawns[slot].active) {
        return FALSE;
    }

    if (object == NULL) {
        c->ops->finish(state,fieldSystem,slot,object,0,0,2);
        return TRUE;
    }
    if ((object->flags&MAPOBJECTFLAG_SINGLE_MOVEMENT)
        || ((state->movementInProgressMask>>slot)&1u)) {
        return TRUE;
    }
    if (base->world->ops->inspectPolicy((u8)slot, &policy)
        && policy.motionPhase > OVERWORLD_MOTION_PHASE_IDLE
        && policy.motionPhase < OVERWORLD_MOTION_PHASE_CANCELED) {
        return FALSE;
    }

    objectX = object->xCurr;
    objectY = object->yCurr;
    targetX = state->movementSpawnRunTargetX[slot];
    targetY = state->movementSpawnRunTargetY[slot];
    if (objectX == targetX && objectY == targetY) {
        OverworldEntryRouteReceipt arrival;
        if (OW_WILD_RUNTIME(state)->entryRouteSerial[slot]
            && (NativeQueryEntry(base,c,state,fieldSystem,slot,NULL,
                    OVERWORLD_ENTRY_ROUTE_GUIDE,NULL,0,0,0,&arrival)!=OVERWORLD_PICKUP_ROUTE_REACHABLE
                || arrival.hasNextStep)) return FALSE;
        c->ops->finish(state,fieldSystem,slot,object,targetX,targetY,0);
        OverworldEntryRouteReceipt receipt;
        if(OW_WILD_RUNTIME(state)->entryRouteSerial[slot]) {
            (void)NativeQueryEntry(base,c,state,fieldSystem,slot,NULL,
                OVERWORLD_ENTRY_ROUTE_RETIRE,NULL,0,0,0,&receipt);
            OW_WILD_RUNTIME(state)->entryRouteSerial[slot]=0;
        }
        c->ops->finish(state,fieldSystem,slot,object,targetX,targetY,1);
        return TRUE;
    }

    /* An idle startup keeps its explicit target, but the shared intent
     * boundary must issue the next Owner move. */
    return FALSE;
}
static BOOL NativeReady(const OverworldEntryRouteNativeControl *c)
{
    LocalMapObject *player=c->field->playerAvatar!=NULL?c->field->playerAvatar->mapObject:NULL;
    return player!=NULL && (Abs(c->prepared->position.startX-player->xCurr)>=13
            || Abs(c->prepared->position.startY-player->yCurr)>=11)
        && !c->ops->occupied(c->field,c->prepared->position.startX,c->prepared->position.startY);
}

static u32 NativeCommitOnce(const OverworldCargoQueryWildCall *base,const OverworldEntryRouteNativeControl *c,
    OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);
    OverworldWildPreparedSpawn *prepared = &runtime->queuedSpawn;
    OverworldWildQueuedSpawnGuard guard;
    int slot = runtime->queuedSpawnSlotPlusOne - 1;
    int x;
    int y;
    u32 byte;
    BOOL destinationFinished = FALSE;

    if (runtime->queuedSpawnSlotPlusOne == 0) {
        return OVERWORLD_ENTRY_COMMIT_NONE;
    }

    if (runtime->refillPositionChecksRemaining >= OW_WILD_SPAWN_MOVE_DESTINATION_PENDING) {
        if (!NativeFinalize(base,c,
                state,
                fieldSystem,
                (OverworldWildSpawnTerrain)runtime->queuedSpawnTerrain,
                slot,
                prepared)) {
            if (runtime->refillPositionChecksRemaining >= OW_WILD_SPAWN_MOVE_DESTINATION_PENDING) {
                return OVERWORLD_ENTRY_COMMIT_PENDING;
            }
            runtime->queuedSpawnSlotPlusOne = 0;
            runtime->refillPositionChecksRemaining = 0;
            return OVERWORLD_ENTRY_COMMIT_FAILED;
        }
        destinationFinished = TRUE;
    }

    x = prepared->startup.targetX;
    y = prepared->startup.targetY;

    /* Consume before calling any engine work: cancel/failure cannot retry the
     * same value or clear another encounter's saved shiny record. */
    runtime->queuedSpawnSlotPlusOne = 0;
    runtime->refillPositionChecksRemaining = 0;
    if ((u32)slot >= OW_WILD_MAX_SPAWNS || slot == OW_WILD_FOLLOWER_SLOT
        || !c->ops->guard(state, fieldSystem, prepared, slot,&guard)) {
        return OVERWORLD_ENTRY_COMMIT_FAILED;
    }
    if (!destinationFinished) {
        for (byte = 0; byte < sizeof(guard); byte++) {
            if (((const u8 *)&guard)[byte]
                    != ((const u8 *)&runtime->queuedSpawnGuard)[byte]) {
                return OVERWORLD_ENTRY_COMMIT_FAILED;
            }
        }
    }
    if (c->ops->placementBlocked(state,fieldSystem,x,y)
        || c->ops->limit(state,
            prepared->behaviorResolution.behaviorLimitKey,
            &prepared->behaviorResolution.profile)) {
        return OVERWORLD_ENTRY_COMMIT_FAILED;
    }
    if (c->ops->spawn(state, fieldSystem,
            runtime->queuedSpawnTerrain, slot, prepared)) {
        state->justSpawned = TRUE;
        return OVERWORLD_ENTRY_COMMIT_SUCCESS;
    }
    return OVERWORLD_ENTRY_COMMIT_FAILED;
}
/* The current Field lease authenticates this synchronous call. Keep its
 * actor owner/epoch and runtime exact across borrowed native callbacks. */
static BOOL NativeRefillOwner(const OverworldEntryRouteNativeControl *c,
    const OverworldWildOverlayRuntimeState *runtime,
    const OverworldActorSystemState *actors, u16 epoch, u16 generation)
{
    return actors!=NULL && c->ops->actors()==actors
        && actors->fieldEpoch==epoch && actors->mapGeneration==generation
        && c->state->mapGeneration==generation
        && c->state->movementRuntimeState==runtime
        && c->state->movementFieldSystem==c->field
        && c->field->playerAvatar!=NULL;
}
static u16 NativeRefillDelay(OverworldWildSpawnState *state, u8 failed)
{
    OverworldWildOverlayRuntimeState *runtime=OW_WILD_RUNTIME(state);
    u8 failures=runtime->refillFailureStreak&OVERWORLD_ENTRY_REFILL_FAILURE_COUNT;
    runtime->refillFailureStreak=0; /* consume the single active-series receipt */
    if(failed && failures<OVERWORLD_ENTRY_REFILL_SHORT_LIMIT) {
        runtime->refillFailureStreak=failures+1;
        return OVERWORLD_ENTRY_REFILL_RETRY_FRAMES;
    }
    u8 count=0;
    for(int slot=0;slot<OW_WILD_LAND_SURF_MAX_SPAWNS;slot++)
        count+=state->spawns[slot].active;
    return OVERWORLD_ENTRY_REFILL_BASE_FRAMES*(count?count:1);
}
static u32 NativeCommit(const OverworldCargoQueryWildCall *base,
    const OverworldEntryRouteNativeControl *c, OverworldWildSpawnState *state,
    FieldSystem *field)
{
    OverworldWildOverlayRuntimeState *runtime=OW_WILD_RUNTIME(state);
    const OverworldActorSystemState *actors=c->ops->actors();
    u16 epoch=actors!=NULL?actors->fieldEpoch:0;
    u16 generation=state->mapGeneration;
    u32 serial=runtime->refillQueuedSerial;
    BOOL ordinary=serial!=0 && serial==runtime->queuedSpawnSerial
        && runtime->queuedSpawnSlotPlusOne!=0
        && (runtime->refillFailureStreak&OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE)
        && NativeRefillOwner(c,runtime,actors,epoch,generation);
    u32 outcome=NativeCommitOnce(base,c,state,field);
    if(!ordinary || (outcome!=OVERWORLD_ENTRY_COMMIT_FAILED
            && outcome!=OVERWORLD_ENTRY_COMMIT_SUCCESS)
        || !NativeRefillOwner(c,runtime,actors,epoch,generation)
        || runtime->queuedSpawnSerial!=serial || runtime->refillQueuedSerial!=serial
        || runtime->queuedSpawnSlotPlusOne!=0) return outcome;
    /* Consume the serial before returning a delay to the sole resident timer.
     * A repeated COMMIT returns NONE; public/manual queues never own this mark. */
    runtime->refillQueuedSerial=0;
    if(outcome==OVERWORLD_ENTRY_COMMIT_SUCCESS) runtime->refillTerrainMask=0;
    if(runtime->refillTerrainMask!=0) return outcome;
    return outcome | ((u32)NativeRefillDelay(state,
        outcome==OVERWORLD_ENTRY_COMMIT_FAILED)<<8);
}
static u16 NativeFinishRefill(const OverworldEntryRouteNativeControl *c)
{
    OverworldWildOverlayRuntimeState *runtime=OW_WILD_RUNTIME(c->state);
    const OverworldActorSystemState *actors=c->ops->actors();
    if(actors==NULL || !NativeRefillOwner(c,runtime,actors,actors->fieldEpoch,c->state->mapGeneration)
        || runtime->queuedSpawnSlotPlusOne || runtime->refillQueuedSerial
        || runtime->refillTerrainMask || runtime->refillPositionChecksRemaining
        || !(runtime->refillFailureStreak&OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE)) return 0;
    return NativeRefillDelay(c->state,c->queryOperation==OVERWORLD_ENTRY_REFILL_FAILED);
}
static OverworldWildHelperPrepareResult NativeSpawn(const OverworldCargoQueryWildCall *base,const OverworldEntryRouteNativeControl *c,OverworldWildSpawnState *state, FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain, int slot)
{
    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);
    OverworldWildPreparedSpawn *prepared = &runtime->queuedSpawn;
    OverworldWildHelperPrepareResult result;

    if (runtime->queuedSpawnSlotPlusOne != 0) {
        return OW_WILD_HELPER_PREPARE_FAILED;
    }

    result = c->ops->prepare(
            state,
            fieldSystem,
            terrain,
            slot,
            prepared);
    if (result != OW_WILD_HELPER_PREPARE_READY) {
        return result;
    }

    if (!NativeArm(c,state,terrain,slot,prepared)) return OW_WILD_HELPER_PREPARE_FAILED;
    if (!NativeFinalize(base,c,
            state, fieldSystem, terrain, slot, prepared)) {
        if (runtime->refillPositionChecksRemaining>=OW_WILD_SPAWN_MOVE_DESTINATION_PENDING) {
            runtime->queuedSpawnTerrain = terrain;
            runtime->queuedSpawnSlotPlusOne = slot + 1;
            return OW_WILD_HELPER_PREPARE_READY;
        }
        runtime->queuedSpawnSlotPlusOne=0;return OW_WILD_HELPER_PREPARE_FAILED;
    }

    if (!c->ops->guard(state, fieldSystem, prepared,slot,&runtime->queuedSpawnGuard)) {
        runtime->queuedSpawnSlotPlusOne=0;return OW_WILD_HELPER_PREPARE_FAILED;
    }
    runtime->queuedSpawnTerrain = terrain;
    runtime->queuedSpawnSlotPlusOne = slot + 1;
    return OW_WILD_HELPER_PREPARE_READY;
}
/* The sole ordinary refill reducer reuses NativeSpawn and its prepared queue.
 * It does not own the wait or chance gates, RNG, or a second timer. */
static BOOL NativeRefillSlot(OverworldWildSpawnState *state,u8 first,u8 last,int *slot)
{
    for(u8 i=first;i<last;i++) {
        if(i!=OW_WILD_FOLLOWER_SLOT && !state->spawns[i].active
            && (state->movementRuntimeState==NULL
                || OW_WILD_RUNTIME(state)->queuedSpawnSlotPlusOne!=i+1)) {
            *slot=i;return TRUE;
        }
    }
    return FALSE;
}
static u32 NativeOrdinaryRefill(const OverworldCargoQueryWildCall *base,
    const OverworldEntryRouteNativeControl *c)
{
    OverworldWildSpawnState *state=c->state;
    FieldSystem *fieldSystem=c->field;
    OverworldWildOverlayRuntimeState *runtime=OW_WILD_RUNTIME(state);
    const OverworldActorSystemState *actors=c->ops->actors();
    u16 epoch=actors!=NULL?actors->fieldEpoch:0;
    u16 generation=state->mapGeneration;
    OverworldWildHelperPrepareResult prepareResult=OW_WILD_HELPER_PREPARE_FAILED;
    OverworldWildSpawnTerrain preferredTerrain=OW_WILD_SPAWN_TERRAIN_LAND;
    int slot=0;
    BOOL attempted=FALSE;
    if(!NativeRefillOwner(c,runtime,actors,epoch,generation)) return prepareResult;
    if (runtime->refillPositionChecksRemaining != 0) {
        slot = runtime->refillLandSurfSlot;
        if (state->spawns[slot].active) {
            prepareResult = OW_WILD_HELPER_PREPARE_FAILED;
            goto refill_attempt_finished;
        }
        preferredTerrain = ((slot & 1) != 0)
                == ((runtime->refillTerrainMask & 8) != 0)
            ? OW_WILD_SPAWN_TERRAIN_SURF : OW_WILD_SPAWN_TERRAIN_LAND;
        goto run_refill_attempt;
    }

    while (runtime->refillTerrainMask != 0) {
        if (runtime->refillTerrainMask & 1) {
            runtime->refillTerrainMask &= ~1;
            if (!NativeRefillSlot(state,
                    OW_WILD_HEADBUTT_SLOT_START, OW_WILD_FISH_SLOT_START, &slot)) {
                continue;
            }
            preferredTerrain = OW_WILD_SPAWN_TERRAIN_HEADBUTT;
        } else if (runtime->refillTerrainMask & 2) {
            runtime->refillTerrainMask &= ~2;
            if (!NativeRefillSlot(state,
                    OW_WILD_FISH_SLOT_START, OW_WILD_MAX_SPAWNS, &slot)) {
                continue;
            }
            preferredTerrain = OW_WILD_SPAWN_TERRAIN_FISHING;
        } else {
            if (runtime->refillTerrainMask & 4) {
                runtime->refillTerrainMask &= ~4;
                if (!NativeRefillSlot(state,
                        0, OW_WILD_LAND_SURF_MAX_SPAWNS, &slot)) {
                    runtime->refillTerrainMask = 0;
                    break;
                }
                runtime->refillLandSurfSlot = slot;
                preferredTerrain = (slot & 1) != 0
                    ? OW_WILD_SPAWN_TERRAIN_SURF : OW_WILD_SPAWN_TERRAIN_LAND;
            } else {
                runtime->refillTerrainMask = 0;
                slot = runtime->refillLandSurfSlot;
                if (!NativeRefillSlot(state, slot, slot + 1, &slot)) {
                    break;
                }
                preferredTerrain = (slot & 1) != 0
                    ? OW_WILD_SPAWN_TERRAIN_LAND : OW_WILD_SPAWN_TERRAIN_SURF;
            }
        }
        runtime->refillPositionChecksRemaining =
            preferredTerrain <= OW_WILD_SPAWN_TERRAIN_SURF
            ? OW_WILD_HELPER_SPAWN_POSITION_ATTEMPT_UPDATES
            : 1;
run_refill_attempt:
        attempted = TRUE;
        prepareResult = NativeSpawn(base,c,state,fieldSystem,preferredTerrain,slot);
        if(!NativeRefillOwner(c,runtime,actors,epoch,generation)) return prepareResult;
        if (prepareResult == OW_WILD_HELPER_PREPARE_POSITION_PENDING) {
            runtime->refillPositionChecksRemaining--;
            return prepareResult;
        }
        break; /* Never start a second terrain search in this update. */
    }
refill_attempt_finished:
    if (runtime->refillPositionChecksRemaining < OW_WILD_SPAWN_MOVE_DESTINATION_PENDING) {
        runtime->refillPositionChecksRemaining = 0;
    }
    if (prepareResult == OW_WILD_HELPER_PREPARE_READY) {
        /* READY is queue admission, including a deferred destination/route.
         * Keep the old terrain/RNG series termination; only defer its timer.
         * A preferred Land/Surf admission keeps the alternate terrain (bit 8)
         * pending: its destination is only checked at commit, and a failed
         * commit must still try the other terrain for this slot. Otherwise a
         * shore with no Land destination retried slot 0 on Land forever and
         * never placed a water spawn. A successful commit clears the bit. */
        runtime->refillTerrainMask &= 8;
        if (runtime->queuedSpawnSlotPlusOne == slot + 1
            && runtime->queuedSpawnTerrain == preferredTerrain
            && runtime->queuedSpawnSerial != 0
            && NativeRefillOwner(c,runtime,actors,epoch,generation)) {
            runtime->refillQueuedSerial = runtime->queuedSpawnSerial;
        }
        return prepareResult;
    }
    if (runtime->refillTerrainMask != 0) {
        return prepareResult;
    }

    /* No free slot is population backoff, not a failed-placement retry. */
    /* Only a current unqueued terminal series can publish natural timing. */
    return prepareResult | ((u32)NativeFinishRefill(&(OverworldEntryRouteNativeControl){
        .ops=c->ops,.state=state,.field=fieldSystem,
        .queryOperation=attempted?OVERWORLD_ENTRY_REFILL_FAILED:OVERWORLD_ENTRY_REFILL_BACKOFF})<<8);
}

OverworldPickupRouteStatus OverworldEntryRoute_NativeControl(
    const OverworldCargoQueryWildCall *base,OverworldCargoQueryResult *result)
{
    if(base==NULL || base->world==NULL || base->entry==NULL || result==NULL) return OVERWORLD_PICKUP_ROUTE_INVALID;
    OverworldEntryRouteNativeControl *c=base->entry->nativeControl;
    if(c==NULL || c->version!=OVERWORLD_ENTRY_NATIVE_VERSION || c->size!=sizeof(*c)
        || c->operation>OVERWORLD_ENTRY_NATIVE_FINISH_REFILL || c->reserved[0] || c->reserved[1]
        || c->accepted>1 || c->usableIdle>1 || c->ops==NULL
        || c->ops->magic!=OVERWORLD_ENTRY_NATIVE_MAGIC || c->ops->version!=OVERWORLD_ENTRY_NATIVE_VERSION
        || c->ops->size!=sizeof(*c->ops) || c->state==NULL || c->field==NULL
        || c->slot>=OW_WILD_MAX_SPAWNS || base->world->state!=c->state
        || base->world->field!=c->field || base->world->slot!=c->slot
        || base->world->version!=OVERWORLD_PICKUP_ROUTE_WILD_VERSION || base->world->size!=sizeof(*base->world)
        || base->world->ops==NULL || base->world->ops->version!=OVERWORLD_PICKUP_ROUTE_WILD_VERSION
        || base->world->ops->size!=sizeof(*base->world->ops) || base->operationReserved[0] || base->operationReserved[1]
        || base->heapId!=OVERWORLD_FIELD_QUERY_HEAP_ID || base->allocate==NULL || base->freeSize==NULL
        || c->ops->actors==NULL || c->ops->initWorld==NULL || c->ops->allowed==NULL
        || c->ops->start==NULL || c->ops->finish==NULL || c->ops->remove==NULL || c->ops->occupied==NULL
        || c->ops->resolve==NULL || c->ops->limit==NULL || c->ops->destination==NULL || c->ops->groundHeight==NULL
        || c->ops->personality==NULL || c->ops->prepare==NULL || c->ops->guard==NULL
        || c->ops->placementBlocked==NULL || c->ops->spawn==NULL || (c->slot==OW_WILD_FOLLOWER_SLOT && c->operation!=OVERWORLD_ENTRY_NATIVE_FINALIZE))
        return OVERWORLD_PICKUP_ROUTE_INVALID;
    if(c->operation==OVERWORLD_ENTRY_NATIVE_COMMIT
        || c->operation==OVERWORLD_ENTRY_NATIVE_FINISH_REFILL) {
        if(c->value || c->slot || c->terrain || c->accepted || c->usableIdle
            || c->profile!=NULL || c->primitives!=NULL || c->prepared!=NULL
            || c->object!=NULL || c->receipt!=NULL || c->startCommitSequence
            || (c->operation==OVERWORLD_ENTRY_NATIVE_COMMIT?c->queryOperation!=0:
                c->queryOperation>OVERWORLD_ENTRY_REFILL_FAILED)) return OVERWORLD_PICKUP_ROUTE_INVALID;
    }
    if(c->operation==OVERWORLD_ENTRY_NATIVE_SPAWN) {
        if(c->queryOperation>OVERWORLD_ENTRY_SPAWN_ORDINARY_REFILL
            || (c->queryOperation==OVERWORLD_ENTRY_SPAWN_ORDINARY_REFILL
                && (c->value || c->slot || c->terrain || c->accepted || c->usableIdle
                    || c->profile!=NULL || c->primitives!=NULL || c->prepared!=NULL
                    || c->object!=NULL || c->receipt!=NULL || c->startCommitSequence)))
            return OVERWORLD_PICKUP_ROUTE_INVALID;
    }
    c->value=0;
    switch(c->operation) {
    case OVERWORLD_ENTRY_NATIVE_ARM:
        if(c->state->movementRuntimeState==NULL || c->prepared==NULL) return OVERWORLD_PICKUP_ROUTE_INVALID;
        c->value=NativeArm(c,c->state,c->terrain,c->slot,c->prepared);break;
    case OVERWORLD_ENTRY_NATIVE_QUERY:
        if(c->receipt==NULL || c->queryOperation>OVERWORLD_ENTRY_ROUTE_RETIRE) return OVERWORLD_PICKUP_ROUTE_INVALID;
        c->value=NativeQueryEntry(base,c,c->state,c->field,c->slot,c->profile,c->queryOperation,c->prepared,
            c->accepted,c->usableIdle,c->startCommitSequence,c->receipt);break;
    case OVERWORLD_ENTRY_NATIVE_FINALIZE:
        if(c->prepared==NULL) return OVERWORLD_PICKUP_ROUTE_INVALID;
        c->value=NativeFinalize(base,c,c->state,c->field,c->terrain,c->slot,c->prepared);break;
    case OVERWORLD_ENTRY_NATIVE_GUIDE:
        if(c->profile==NULL || c->primitives==NULL || c->object==NULL || c->state->movementRuntimeState==NULL)
            return OVERWORLD_PICKUP_ROUTE_INVALID;
        c->value=NativeGuide(base,c,c->state,c->slot,c->object,c->profile,c->primitives);break;
    case OVERWORLD_ENTRY_NATIVE_UPDATE:
        c->value=NativeUpdate(base,c,c->state,c->field,c->slot,c->object);break;
    case OVERWORLD_ENTRY_NATIVE_READY:
        if(c->prepared==NULL) return OVERWORLD_PICKUP_ROUTE_INVALID;
        c->value=NativeReady(c);break;
    case OVERWORLD_ENTRY_NATIVE_COMMIT:
        if(c->state->movementRuntimeState==NULL) return OVERWORLD_PICKUP_ROUTE_INVALID;
        c->value=NativeCommit(base,c,c->state,c->field);break;
    case OVERWORLD_ENTRY_NATIVE_FINISH_REFILL:
        if(c->state->movementRuntimeState==NULL) return OVERWORLD_PICKUP_ROUTE_INVALID;
        c->value=NativeFinishRefill(c);break;
    case OVERWORLD_ENTRY_NATIVE_SPAWN:
        if(c->state->movementRuntimeState==NULL) return OVERWORLD_PICKUP_ROUTE_INVALID;
        c->value=c->queryOperation==OVERWORLD_ENTRY_SPAWN_ORDINARY_REFILL
            ? NativeOrdinaryRefill(base,c)
            : NativeSpawn(base,c,c->state,c->field,c->terrain,c->slot);break;
    case OVERWORLD_ENTRY_NATIVE_RETIRE:
        if(c->state->movementRuntimeState!=NULL && OW_WILD_RUNTIME(c->state)->entryRouteSerial[c->slot]) {
            OverworldEntryRouteReceipt receipt;
            (void)NativeQueryEntry(base,c,c->state,c->field,c->slot,NULL,OVERWORLD_ENTRY_ROUTE_RETIRE,NULL,0,0,0,&receipt);
            OW_WILD_RUNTIME(c->state)->entryRouteSerial[c->slot]=0;
        }
        break;
    }
    result->status=OVERWORLD_PICKUP_ROUTE_REACHABLE;return result->status;
}
