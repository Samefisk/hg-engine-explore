#include "overworld_cargo_query.h"
#define PENDING OVERWORLD_PICKUP_ROUTE_PENDING
#define INVALID OVERWORLD_PICKUP_ROUTE_INVALID
#define LIMIT OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT
#define REACHABLE OVERWORLD_PICKUP_ROUTE_REACHABLE
#define UNREACHABLE OVERWORLD_PICKUP_ROUTE_UNREACHABLE
#define LEGAL OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL
#define BLOCKED OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED
#define DEFERRED OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED

/* Sealed value layouts have no padding in these spans. Character access is
 * alias-safe; this keeps one comparison body without another resident import.
 * Handle12 includes reserved; Position10 excludes the validated reserved2. */
/* Image-private shared comparison. Every call remains inside this relocatable
 * addon; SHORT_CALL preserves a local Thumb BL rather than an imported pointer. */
#ifdef OVERWORLD_ACTOR_SYSTEM_HOST
extern u8 OverworldPickupRoute_EqualValues(const void *,const void *,u8) __attribute__((pure));
#else
extern u8 OverworldPickupRoute_EqualValues(const void *,const void *,u8) __attribute__((short_call,pure));
#endif
#define Equal OverworldPickupRoute_EqualValues
#define Handle(a,b) Equal(a,b,12)
#define Position(a,b) Equal(a,b,10)
static u8 ValidHandle(const OverworldActorHandle *a)
{ return a->slot<OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS && a->generation && a->fieldEpoch
    && a->mapGeneration && a->encounterGeneration && !a->reserved; }
void OverworldCargoQuery_Clear(OverworldCargoQueryState *s)
{ if(s) { OverworldCargoQueryStorage *storage=s->storage;*s=(OverworldCargoQueryState){0};
    s->storage=storage;s->version=OVERWORLD_CARGO_QUERY_VERSION;s->size=sizeof(*s);
    if(storage && storage->changeGeneration!=0xFFFFFFFFu) storage->changeGeneration++; } }
void OverworldCargoQuery_Init(OverworldCargoQueryState *s,OverworldCargoQueryStorage *storage)
{ if(s) { s->storage=storage;OverworldCargoQuery_Clear(s); } }
static u32 TileHash(s16 x,s16 y)
{ return ((u16)x*31u+(u16)y*71u)&(OVERWORLD_CARGO_QUERY_CHANGES-1); }
u8 OverworldCargoQuery_ObserveChanges(OverworldCargoQueryState *s,const OverworldCargoQueryInput *i)
{
    u32 now=s->query.dynamicRevision,generation=s->storage->changeGeneration;
    if(s->observedRevision && (now<s->observedRevision
        || (now==s->observedRevision && i->changedTileCount))) return 0;
    if(!s->observedRevision) s->evictionFloor=now;
    s->observedRevision=now;
    s->changesKnown=i->changesComplete && generation!=0xFFFFFFFFu
        && i->changedTileCount<=OVERWORLD_CARGO_QUERY_CHANGES;
    if(!s->changesKnown) {
        s->evictionFloor=now;return 1;
    }
    for(u16 n=0;n<i->changedTileCount;n++) {
        const OverworldCargoQueryChangedTile *tile=&i->changedTiles[n];
        u32 hash=TileHash(tile->x,tile->y),selected=hash;
        for(u8 p=0;p<8;p++) {
            OverworldCargoQueryTileStamp *entry=&s->storage->changes[hash];
            s->lastWork.changeProbes++;
            selected=hash;
            if(entry->generation!=generation || (entry->x==tile->x && entry->y==tile->y)) break;
            hash=(hash+1)&(OVERWORLD_CARGO_QUERY_CHANGES-1);
        }
        OverworldCargoQueryTileStamp *entry=&s->storage->changes[selected];
        if(entry->generation==generation && (entry->x!=tile->x || entry->y!=tile->y)
            && entry->revision>s->evictionFloor) s->evictionFloor=entry->revision;
        *entry=(OverworldCargoQueryTileStamp){tile->x,tile->y,now,generation};s->lastWork.changedTiles++;
    }
    return 1;
}
static __attribute__((noinline)) u8 Touches(s16 x,s16 y,
    const OverworldPickupRoutePosition *a,const OverworldPickupRoutePosition *b)
{
    return ((x>=a->x && x<=b->x) || (x>=b->x && x<=a->x))
        && ((y>=a->y && y<=b->y) || (y>=b->y && y<=a->y));
}
u8 OverworldCargoQuery_Unchanged(OverworldCargoQueryState *s,const OverworldPickupRoutePosition *from,
    const OverworldPickupRoutePosition *to,u32 revision)
{
    if(!s->changesKnown || revision<s->evictionFloor || revision>s->observedRevision) return 0;
    /* Rectangle includes diagonal guards and every straight Hop clearance
     * sample. Ignore height for a conservative witness. Fixed512 entries, no
     * distance-sized scan and no terrain/native calls. */
    for(u16 n=0;n<OVERWORLD_CARGO_QUERY_CHANGES;n++) {
        const OverworldCargoQueryTileStamp *tile=&s->storage->changes[n];
        s->lastWork.witnessProbes++;
        if(tile->generation==s->storage->changeGeneration && tile->revision>revision
            && Touches(tile->x,tile->y,from,to)) return 0;
    }
    return 1;
}
/* Check the actual directed suffix. Both endpoints bound every straight
 * Hop/diagonal clearance dependency; no empty bounding-box corner is a path. */
__attribute__((noinline)) u8 OverworldCargoQuery_ProofUnchanged(OverworldCargoQueryState *s,u16 limit)
{
    OverworldPickupRouteState *r=&s->route;
    u32 revision=r->proofRevision;
    if(!s->changesKnown || revision<s->evictionFloor || revision>s->observedRevision) return 0;
    for(u16 n=0;n<OVERWORLD_CARGO_QUERY_CHANGES;n++) {
        const OverworldCargoQueryTileStamp *tile=&s->storage->changes[n];
        if(s->lastWork.witnessProbes==limit) return 0;
        s->lastWork.witnessProbes++;
        if(tile->generation!=s->storage->changeGeneration || tile->revision<=revision) continue;
        u16 node=r->goalNode,count=0;
        while(node!=r->proofNode) {
            if(node>=r->nodeCount || ++count>r->nodeCount
                || s->lastWork.witnessProbes==limit) return 0;
            s->lastWork.witnessProbes++;
            const OverworldPickupRouteNode *child=&r->workspace->nodes[node];
            if(child->searchStamp!=r->searchStamp || child->parent>=r->nodeCount
                || child->parentEdge>=r->cachedEdgeCount
                || r->workspace->nodes[child->parent].searchStamp!=r->searchStamp) return 0;
            const OverworldPickupRouteCachedEdge *edge=&r->workspace->edges[child->parentEdge];
            if(edge->destination!=node || edge->decision!=LEGAL || edge->usedSearchStamp!=r->searchStamp) return 0;
            const OverworldPickupRoutePosition *a=&child->position,*b=&r->workspace->nodes[child->parent].position;
            if(Touches(tile->x,tile->y,a,b)) return 0;
            node=child->parent;
        }
    }
    return 1;
}
static void AddWork(OverworldCargoQueryState *s)
{ s->lastWork.native=s->runtime->lastWork; /* At most one native call per Tick. */ }
static OverworldPickupRouteEdgeResult Edge(void *raw,const OverworldPickupRoutePosition *from,
    const OverworldPickupRouteEdge *edge,OverworldPickupRoutePosition *to)
{
    OverworldCargoQueryState *s=raw;
    const OverworldPickupRoutePosition *destination;
    const OverworldPickupRouteCachedEdge *memo=OverworldPickupRoute_ReadMemo(&s->route,from,edge,&destination);
    if(memo && OverworldCargoQuery_Unchanged(s,from,destination,memo->dynamicRevision)) { *to=*destination;return LEGAL; }
    if(s->unitUsed) { s->edgeOwed=2;return DEFERRED; }
    s->unitUsed=1;s->edgeOwed=0;s->lastWork.edgeQueries++;
    OverworldPickupRouteEdgeResult result=OverworldPickupRouteNative_Classify(s->runtime,from,edge,to);
    AddWork(s);return result;
}
static OverworldPickupRouteStatus Failure(OverworldPickupRouteEdgeResult result)
{ return result==OVERWORLD_PICKUP_ROUTE_EDGE_RESOURCE_LIMIT?LIMIT:
    result==DEFERRED?PENDING:INVALID; }
static u8 Compatible(const OverworldCargoQueryState *s,const OverworldCargoQueryInput *i)
{
    const OverworldPickupRouteQuery *a=&s->query,*b=i->seed;
    return Handle(&a->subject,&b->subject) && s->requestKey==i->requestKey
        && s->roleMask==i->bindingsWorld->subjectRoleMask && s->distance==i->pickupDistance
        && s->selectionFlags==i->selectionFlags
        /* Binding the exact Cargo this search proved only fixes its owner.
         * Dropping that binding or selecting a different full identity resets. */
        && (i->selectionFlags&OVERWORLD_CARGO_QUERY_SELECT_NEAREST
            ?(i->requiredCargo?Handle(&s->incumbent,i->requiredCargo):!s->incumbent.generation)
            :(i->requiredCargo?Handle(&a->cargo,i->requiredCargo):!s->required))
        && a->scopeRevision==b->scopeRevision && a->movementPolicyRevision==b->movementPolicyRevision
        && Equal(&a->bounds,&b->bounds,8)
        && a->edges==b->edges && a->edgeCount==b->edgeCount;
}
static void NextCargo(OverworldCargoQueryState *s)
{
    if(s->selectionFlags&OVERWORLD_CARGO_QUERY_SELECT_NEAREST) {
        if(s->query.cargo.generation && s->query.cargo.slot<OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS)
            s->triedMask|=1u<<s->query.cargo.slot;
        if(s->rankPhase==OVERWORLD_CARGO_QUERY_RANK_INCUMBENT)
            s->rankPhase=OVERWORLD_CARGO_QUERY_RANK_SCAN;
        s->scan=0;
    } else s->scan=(u8)(s->candidate+1);
    s->active=s->started=s->goalValid=0;
}
static u16 Distance(s16 ax,s16 ay,s16 bx,s16 by)
{
    s32 dx=(s32)ax-bx,dy=(s32)ay-by;
    if(dx<0) dx=-dx;if(dy<0) dy=-dy;
    return (u16)(dx>dy?dx:dy);
}
static void BeginRanking(OverworldCargoQueryState *s,const OverworldCargoQueryInput *i)
{
    s->incumbent=i->requiredCargo?*i->requiredCargo:(OverworldActorHandle){0};
    s->bestCargo=(OverworldActorHandle){0};
    s->incumbentScore=s->bestScore=OVERWORLD_CARGO_QUERY_SCORE_UNKNOWN;
    s->incumbentX=s->bestX=-1;
    s->triedMask=s->scan=0;s->active=s->started=s->goalValid=0;
    s->rankPhase=i->requiredCargo?OVERWORLD_CARGO_QUERY_RANK_INCUMBENT:OVERWORLD_CARGO_QUERY_RANK_SCAN;
}
/* XY alone only selects a native goal query; it never proves pickup. */
static __attribute__((noinline)) u8 Near(const OverworldPickupRoutePosition *a,const OverworldPickupRoutePosition *b,u8 distance)
{ return (a->x!=b->x || a->y!=b->y)
    && (u16)(a->x-b->x+distance)<=2u*distance
    && (u16)(a->y-b->y+distance)<=2u*distance; }
/* A retained standing XY only estimates ranking. A moved Cargo outside that
 * reach requires reproof; this check never grants native route eligibility. */
static u16 Score(const OverworldCargoQueryState *s,const OverworldCargoQueryInput *i,
    const OverworldActorHandle *handle,s16 x,s16 y)
{
    if(x>=0) for(u8 n=0;n<i->bindingsWorld->actorCount;n++) {
        const OverworldBehaviorConditionActorObservation *a=&i->bindingsWorld->actors[n];
        if(a->valid && (i->eligibleActorMask&(1u<<n)) && Handle(handle,&a->actor)) {
            OverworldPickupRoutePosition goal={x,y,0,0,0},cargo={a->x,a->y,0,0,0};
            if(Near(&goal,&cargo,s->distance)) return Distance(s->query.origin.x,s->query.origin.y,x,y);
        }
    }
    return OVERWORLD_CARGO_QUERY_SCORE_UNKNOWN;
}
static void ForgetIncumbent(OverworldCargoQueryState *s)
{
    s->incumbentScore=OVERWORLD_CARGO_QUERY_SCORE_UNKNOWN;s->incumbentX=-1;
    if(Handle(&s->bestCargo,&s->incumbent)) {
        s->bestCargo=(OverworldActorHandle){0};s->bestScore=OVERWORLD_CARGO_QUERY_SCORE_UNKNOWN;s->bestX=-1;
    }
}
static void FirstGoal(OverworldCargoQueryState *s)
{ s->goalDX=s->goalDY=-(s16)s->distance;s->goalExhausted=s->goalValid=0; }
static void NextGoal(OverworldCargoQueryState *s)
{
    /* An out-of-grid priority attempt is followed by the entire ordinary
     * pickup square, including goals that are farther from the Subject. */
    if(s->goalDX>s->distance) FirstGoal(s);
    else if(++s->goalDX>s->distance) { s->goalDX=-(s16)s->distance;
        if(++s->goalDY>s->distance) s->goalExhausted=1; }
    s->goalValid=0;s->goalDirty=1;
}

#if defined(__GNUC__) && !defined(__clang__)
__attribute__((optimize("no-tree-forwprop")))
#endif
OverworldPickupRouteStatus OverworldCargoQuery_Tick(OverworldCargoQueryState *s,
    const OverworldCargoQueryInput *i,OverworldCargoQueryResult *out)
{
    OverworldPickupRouteStatus status=PENDING;
    OverworldPickupRouteNativeContext *native;
    const OverworldPickupRouteQuery *oldQuery;
    const OverworldBehaviorConditionWorldView *world;
    const OverworldBehaviorConditionActorObservation *actor=0;
    OverworldPickupRoutePosition cargo;
    OverworldPickupRouteEdgeResult decision;
    u8 found=0,work,moved,nearest;
    if(out) *out=(OverworldCargoQueryResult){0};
    if(!s || !i || !out || s->version!=OVERWORLD_CARGO_QUERY_VERSION || s->size!=sizeof(*s)
        || i->version!=OVERWORLD_CARGO_QUERY_VERSION || i->size!=sizeof(*i)
        || !s->storage || !i->runtime || !i->runtime->policy || !i->bindingsWorld || !i->seed
        || !i->readPosition || !i->requestKey || !i->pickupDistance
        || i->internalWork>OVERWORLD_CARGO_QUERY_INTERNAL_WORK || i->changesComplete>1
        || (i->selectionFlags&~OVERWORLD_CARGO_QUERY_SELECTION_FLAGS)
        || (!(i->selectionFlags&OVERWORLD_CARGO_QUERY_SELECT_NEAREST) && i->selectionFlags)
        || (i->changedTileCount && !i->changedTiles)) {
        if(out) out->status=INVALID;return INVALID;
    }
    world=i->bindingsWorld;native=i->runtime;
    if(native->version!=OVERWORLD_PICKUP_ROUTE_NATIVE_VERSION || native->size!=sizeof(*native)
        || i->seed->version!=OVERWORLD_PICKUP_ROUTE_VERSION || i->seed->size!=sizeof(*i->seed)
        || !i->seed->scopeRevision || !i->seed->movementPolicyRevision || !i->seed->dynamicRevision
        || !i->seed->edgeCount || !i->seed->edges || i->seed->origin.reserved
        || i->seed->bounds.minX<0 || i->seed->bounds.minY<0
        || i->seed->bounds.minX>i->seed->origin.x || i->seed->bounds.maxX<i->seed->origin.x
        || i->seed->bounds.minY>i->seed->origin.y || i->seed->bounds.maxY<i->seed->origin.y
        || world->actorCount>OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS
        || (i->eligibleActorMask>>world->actorCount) || !world->subjectRoleMask
        || !ValidHandle(&world->subject) || !Handle(&world->subject,&i->seed->subject)
        || world->subjectX!=i->seed->origin.x || world->subjectY!=i->seed->origin.y
        || (i->requiredCargo && !ValidHandle(i->requiredCargo))) {
        out->status=INVALID;return INVALID;
    }
    s->lastWork=(OverworldCargoQueryWork){0};s->unitUsed=0;
    if(s->frameValid && s->frame==world->frame) goto finished;
    if(s->requestKey && !Compatible(s,i)) OverworldCargoQuery_Clear(s);
    s->frame=world->frame;s->frameValid=1;
    if(!i->internalWork) goto finished;
    s->requestKey=i->requestKey;s->roleMask=world->subjectRoleMask;s->distance=i->pickupDistance;
    s->selectionFlags=i->selectionFlags;
    nearest=i->selectionFlags&OVERWORLD_CARGO_QUERY_SELECT_NEAREST;
    s->required=i->requiredCargo!=0 && !nearest;
    if(nearest && !s->rankPhase) BeginRanking(s,i);
    /* Keep the old Cargo pose until after comparison. Query/context storage is
     * resident, while Native policy/world are borrowed for this Tick only. */
    moved=!s->active || !Position(&s->query.origin,&i->seed->origin);
    cargo=s->query.cargoPosition;
    OverworldActorHandle cargoHandle=s->query.cargo;
    s->query=*i->seed;s->query.cargo=cargoHandle;s->query.cargoPosition=cargo;
    s->query.goalRevision=s->goalRevision?s->goalRevision:1;
    s->query.goals=&s->goal;s->query.goalCount=1;s->query.legalEdge=Edge;s->query.context=s;
    if(nearest) {
        s->incumbentScore=Score(s,i,&s->incumbent,s->incumbentX,s->incumbentY);
        s->bestScore=Score(s,i,&s->bestCargo,s->bestX,s->bestY);
    }
    if(!OverworldCargoQuery_ObserveChanges(s,i)) { status=INVALID;goto finished; }
    oldQuery=native->query;native->query=&s->query;s->runtime=native;
    if(s->active || s->required || (nearest && s->rankPhase!=OVERWORLD_CARGO_QUERY_RANK_SCAN)) {
        const OverworldActorHandle *wanted=s->active?&s->query.cargo:s->required?i->requiredCargo:
            (s->rankPhase==OVERWORLD_CARGO_QUERY_RANK_INCUMBENT
                || s->rankPhase==OVERWORLD_CARGO_QUERY_RANK_FINAL_INCUMBENT)?&s->incumbent:&s->bestCargo;
        for(u8 n=0;n<world->actorCount;n++) {
            if(world->actors[n].valid && Handle(wanted,&world->actors[n].actor)) {
                actor=&world->actors[n];s->candidate=n;found++;
            }
        }
        if(found!=1 || !(i->eligibleActorMask&(1u<<s->candidate))) {
            if(s->required) { status=INVALID;goto release; }
            if(nearest && s->rankPhase>=OVERWORLD_CARGO_QUERY_RANK_REPROVE) {
                BeginRanking(s,i);goto release;
            }
            if(nearest && s->rankPhase==OVERWORLD_CARGO_QUERY_RANK_INCUMBENT) {
                ForgetIncumbent(s);s->query.cargo.generation=0;
            }
            NextCargo(s);actor=0;
        }
    }
    if(!actor) {
        if(s->scan>=world->actorCount) {
            if(nearest && s->incumbentX>=0 && s->incumbentScore==OVERWORLD_CARGO_QUERY_SCORE_UNKNOWN) {
                s->rankPhase=OVERWORLD_CARGO_QUERY_RANK_INCUMBENT;
                s->active=s->started=s->goalValid=0;goto release;
            }
            if(nearest && s->bestCargo.generation) {
                s->rankPhase=OVERWORLD_CARGO_QUERY_RANK_REPROVE;
                s->active=s->started=s->goalValid=0;
            } else { status=UNREACHABLE;s->scan=0; }
            goto release;
        }
        s->candidate=s->scan++;s->lastWork.candidateChecks++;
        actor=&world->actors[s->candidate];
        if(!actor->valid || !(i->eligibleActorMask&(1u<<s->candidate))) goto release;
        if(nearest) {
            if(!ValidHandle(&actor->actor)) { status=INVALID;goto release; }
            u16 bit=1u<<actor->actor.slot;
            if(s->triedMask&bit) goto release;
            u16 distance=Distance(s->query.origin.x,s->query.origin.y,actor->x,actor->y);
            if(s->bestCargo.generation && distance>=s->distance
                && distance-s->distance>=s->bestScore) { s->triedMask|=bit;goto release; }
        }
    }
    if(!ValidHandle(&actor->actor) || Handle(&actor->actor,&world->subject)
        || actor->actor.fieldEpoch!=world->subject.fieldEpoch
        || actor->actor.mapGeneration!=world->subject.mapGeneration) { status=INVALID;goto release; }
    if(!s->active) {
        s->query.cargo=actor->actor;s->active=1;s->goalDirty=1;FirstGoal(s);
        s->goalDX=s->distance+2;
    }
    s->lastWork.positionReads++;
    decision=i->readPosition(native->world,&s->query.cargo,&cargo);
    if(decision!=LEGAL) { status=Failure(decision);goto release; }
    if(cargo.reserved || cargo.x!=actor->x || cargo.y!=actor->y) { status=INVALID;goto release; }
    if(!Position(&cargo,&s->query.cargoPosition)) {
        moved=1;
        if((!s->goalValid && s->goalDX!=s->distance+2) || (s->goalValid
                && s->goalDX==s->distance+2 && !Near(&s->goal,&cargo,s->distance))) FirstGoal(s);
        s->goalDirty=1;
    }
    s->query.cargoPosition=cargo;
    /* Reaching the physical range gives the current standing pose the first
     * native check. The out-of-grid cursor means one priority attempt; BLOCKED
     * resumes the complete ordinary scan instead of retrying this pose forever. */
    if(moved && Near(&s->query.origin,&cargo,s->distance)) {
        FirstGoal(s);s->goalDX=s->distance+1;s->goalDirty=1;
    }
    if(s->checkedDynamicRevision!=s->query.dynamicRevision) s->goalDirty=1;
    /* Once a goal consumed the sole native call, finish one edge call before
     * refreshing it again. Search can use that retained goal, but never publish
     * it while dirty. A goal occupied by current Cargo must refresh immediately. */
    if(!s->goalValid || (s->goalDirty && (!s->edgeOwed
            || (s->edgeOwed==1 && s->route.phase==OVERWORLD_PICKUP_ROUTE_PHASE_PROOF)))
        || (s->goal.x==cargo.x && s->goal.y==cargo.y)) {
        if(s->goalExhausted) {
            if(s->required) { status=UNREACHABLE;FirstGoal(s); }
            else if(nearest && s->rankPhase>=OVERWORLD_CARGO_QUERY_RANK_REPROVE) BeginRanking(s,i);
            else {
                if(nearest && s->rankPhase==OVERWORLD_CARGO_QUERY_RANK_INCUMBENT) ForgetIncumbent(s);
                NextCargo(s);
            }
            goto release;
        }
        /* Entire authored Chebyshev reach, never occupied Cargo XY. Keeping
         * the relative offset across moves preserves compatible exploration. */
        s32 x=(s32)cargo.x+s->goalDX,y=(s32)cargo.y+s->goalDY;
        /* A still-reachable standing pose need not follow every Cargo tile.
         * Native pickupReach/height/occupancy below revalidate it unchanged. */
        const OverworldPickupRoutePosition *standing=s->goalDX==s->distance+1?&s->query.origin:
            s->goalValid && Near(&s->goal,&cargo,s->distance)?&s->goal:0;
        if(standing) { x=standing->x;y=standing->y; }
        else if(s->goalDX>s->distance) {
            /* Nearest standing XY gets one native attempt. XY is not a
             * pickup proof; native height/reach/occupancy checks still own it. */
            x=s->query.origin.x;y=s->query.origin.y;
            if(x<cargo.x-s->distance) x=cargo.x-s->distance;
            if(x>cargo.x+s->distance) x=cargo.x+s->distance;
            if(y<cargo.y-s->distance) y=cargo.y-s->distance;
            if(y>cargo.y+s->distance) y=cargo.y+s->distance;
        }
        if(x==cargo.x && y==cargo.y) { NextGoal(s);goto release; }
        s->unitUsed=1;s->lastWork.goalQueries++;
        OverworldPickupRoutePosition oldGoal=s->goal;
        decision=(x<0 || y<0 || x>32767 || y>32767)?BLOCKED:
            OverworldPickupRouteNative_PickupGoal(native,(s16)x,(s16)y,&s->goal);
        if(x>=0 && y>=0 && x<=32767 && y<=32767) AddWork(s);
        if(decision==BLOCKED) { NextGoal(s);goto release; }
        if(decision!=LEGAL) { status=Failure(decision);goto release; }
        if(!s->goalRevision || !Position(&oldGoal,&s->goal)) {
            if(s->goalRevision==0xFFFFFFFFu) { status=LIMIT;goto release; }
            s->query.goalRevision=++s->goalRevision;
        }
        s->goalValid=1;s->goalDirty=0;s->edgeOwed=1;s->checkedDynamicRevision=s->query.dynamicRevision;
    }
    if(!s->started) {
        status=OverworldPickupRoute_Begin(&s->route,&s->query,&s->storage->workspace);
        if(status!=PENDING) goto release;
        s->started=1;
    }
    work=i->internalWork;
    if(s->route.phase==OVERWORLD_PICKUP_ROUTE_PHASE_PROOF) {
        /* Each up-to512 witness comparisons consumes one existing unit. */
        s->route.reserved[0]=OverworldCargoQuery_ProofUnchanged(s,(u16)(work*OVERWORLD_CARGO_QUERY_CHANGES))
            ?OVERWORLD_PICKUP_ROUTE_PROOF_SUFFIX_CURRENT:0;
        work-=(u8)((s->lastWork.witnessProbes+OVERWORLD_CARGO_QUERY_CHANGES-1)/OVERWORLD_CARGO_QUERY_CHANGES);
        s->route.hashIndex=s->query.dynamicRevision;
    }
    status=OverworldPickupRoute_Resume(&s->route,&s->query,work,&out->route);
    s->lastWork.routeUnits=(u16)out->route.workUsed;
    if(s->goalDirty && (status==REACHABLE || status==UNREACHABLE)) {
        /* A completed exploratory route needs a current native goal receipt
         * before eligibility. The next Tick gives that check its turn. */
        s->edgeOwed=0;status=PENDING;out->route=(OverworldPickupRouteResult){0};
    } else if(status==UNREACHABLE) {
        NextGoal(s);status=PENDING;
    } else if(status==REACHABLE) {
        if(nearest) {
            u16 score=Distance(s->query.origin.x,s->query.origin.y,
                out->route.pickupPosition.x,out->route.pickupPosition.y);
            if(Handle(&s->query.cargo,&s->incumbent)) {
                s->incumbentScore=score;s->incumbentX=out->route.pickupPosition.x;s->incumbentY=out->route.pickupPosition.y;
            }
            if(s->rankPhase==OVERWORLD_CARGO_QUERY_RANK_REPROVE
                || s->rankPhase==OVERWORLD_CARGO_QUERY_RANK_DONE
                || s->rankPhase==OVERWORLD_CARGO_QUERY_RANK_FINAL_INCUMBENT) {
                u8 advantage=i->selectionFlags>>OVERWORLD_CARGO_QUERY_SWITCH_ADVANTAGE_SHIFT;
                if(s->rankPhase==OVERWORLD_CARGO_QUERY_RANK_FINAL_INCUMBENT) {
                    if(s->bestScore==OVERWORLD_CARGO_QUERY_SCORE_UNKNOWN) {
                        BeginRanking(s,i);status=PENDING;
                        out->route=(OverworldPickupRouteResult){0};goto release;
                    }
                    if((u32)s->bestScore+advantage<=score) {
                        s->rankPhase=OVERWORLD_CARGO_QUERY_RANK_REPROVE;
                        s->active=s->started=s->goalValid=0;status=PENDING;
                        out->route=(OverworldPickupRouteResult){0};goto release;
                    }
                    s->bestCargo=s->incumbent;
                } else {
                    s->bestScore=score;s->bestX=out->route.pickupPosition.x;s->bestY=out->route.pickupPosition.y;
                    if(!Handle(&s->bestCargo,&s->incumbent)
                        && s->incumbentScore!=OVERWORLD_CARGO_QUERY_SCORE_UNKNOWN
                        && (u32)score+advantage>s->incumbentScore) {
                        s->rankPhase=OVERWORLD_CARGO_QUERY_RANK_FINAL_INCUMBENT;
                        s->active=s->started=s->goalValid=0;status=PENDING;
                        out->route=(OverworldPickupRouteResult){0};goto release;
                    }
                }
                s->bestScore=score;s->bestX=out->route.pickupPosition.x;s->bestY=out->route.pickupPosition.y;
                s->rankPhase=OVERWORLD_CARGO_QUERY_RANK_DONE;
            } else {
                if(score<s->bestScore || Handle(&s->bestCargo,&s->query.cargo)) {
                    s->bestScore=score;s->bestCargo=s->query.cargo;
                    s->bestX=out->route.pickupPosition.x;s->bestY=out->route.pickupPosition.y;
                }
                NextCargo(s);status=PENDING;
                out->route=(OverworldPickupRouteResult){0};goto release;
            }
        }
        out->eligibleActorMask=(u16)(1u<<s->candidate);
    }
release:
    native->query=oldQuery;s->runtime=0;
finished:
    out->status=(u8)status;out->lastWork=s->lastWork;return status;
}
