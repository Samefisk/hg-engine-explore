#include "overworld_pickup_route.h"
#define NONE OVERWORLD_PICKUP_ROUTE_NONE
enum { ROOT_LOOKUP, NODE_GOALS, SCAN_INIT, SCAN_EDGE, FIND_EDGE, SCORE_EDGE,
    TRY_EDGE, DEST_LOOKUP, PROBE_GOAL, PROBE_LOOKUP, PROOF };
/* Handle12 and Bounds8 have no padding. Position10 excludes reserved. */
u8 OverworldPickupRoute_EqualValues(const void *a,const void *b,u8 bytes)
{ const u8 *x=a,*y=b;while(bytes--) if(*x++!=*y++) return 0;return 1; }
#define Equal OverworldPickupRoute_EqualValues
#define Pos(a,b) Equal(a,b,10)
#define Handle(a,b) Equal(a,b,12)
static u8 ValidHandle(const OverworldActorHandle *a)
{ return a->slot<OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS && a->generation && a->fieldEpoch
    && a->mapGeneration && a->encounterGeneration; }
static u8 Inside(const OverworldPickupRouteBounds *b,s32 x,s32 y)
{ return x>=b->minX && x<=b->maxX && y>=b->minY && y<=b->maxY; }
static u8 ExtensionValid(const OverworldPickupRouteQuery *q)
{ const OverworldPickupRouteExtension *e=q->extension;
  static const OverworldActorHandle empty={0};
  return e && e->version==OVERWORLD_PICKUP_ROUTE_EXTENSION_VERSION
    && e->size==sizeof(*e) && !e->reserved && e->current && e->goal && e->score
    && Handle(&q->cargo,&empty) && !q->goals && !q->goalCount
    && ((e->kind==OVERWORLD_PICKUP_ROUTE_EXTENSION_PREPARED
         && e->flags==OVERWORLD_PICKUP_ROUTE_EXTENSION_REVERSE && Handle(&q->subject,&empty))
        || (e->kind==OVERWORLD_PICKUP_ROUTE_EXTENSION_ENTRY_ACTOR && !e->flags
            && !q->subject.reserved && ValidHandle(&q->subject)))
    && e->current(e->context); }
u8 OverworldPickupRoute_QueryCurrent(const OverworldPickupRouteQuery *q)
{ return q && q->version==OVERWORLD_PICKUP_ROUTE_VERSION && q->size==sizeof(*q)
    && (q->extension ? ExtensionValid(q) :
        (ValidHandle(&q->subject) && ValidHandle(&q->cargo)
         && !q->subject.reserved && !q->cargo.reserved
         && q->subject.slot!=q->cargo.slot
         && q->subject.fieldEpoch==q->cargo.fieldEpoch
         && q->subject.mapGeneration==q->cargo.mapGeneration
         && Inside(&q->bounds,q->cargoPosition.x,q->cargoPosition.y)))
    && q->scopeRevision && q->movementPolicyRevision && q->goalRevision && q->dynamicRevision
    && q->bounds.minX<=q->bounds.maxX && q->bounds.minY<=q->bounds.maxY
    && Inside(&q->bounds,q->origin.x,q->origin.y)
    && !q->origin.reserved && !q->cargoPosition.reserved && (!q->edgeCount || q->edges)
    && (!q->goalCount || q->goals) && q->legalEdge; }
#define Valid OverworldPickupRoute_QueryCurrent
static u8 Compatible(const OverworldPickupRouteQuery *a,const OverworldPickupRouteQuery *b)
{ return a->extension==b->extension
    && (!a->extension || a->goalRevision==b->goalRevision)
    && Handle(&a->subject,&b->subject) && Handle(&a->cargo,&b->cargo)
    && Equal(&a->bounds,&b->bounds,8)
    && a->scopeRevision==b->scopeRevision && a->movementPolicyRevision==b->movementPolicyRevision
    && a->edges==b->edges && a->edgeCount==b->edgeCount && a->legalEdge==b->legalEdge && a->context==b->context; }
static u8 GoalValid(const OverworldPickupRouteQuery *q,const OverworldPickupRoutePosition *p)
{ return !p->reserved && Inside(&q->bounds,p->x,p->y)
    && !(p->x==q->cargoPosition.x && p->y==q->cargoPosition.y); }
static u32 Hash(const OverworldPickupRoutePosition *p)
{ u32 h=(u16)p->x*0x9E3779B1u;h^=(u16)p->y*0x85EBCA77u;h^=(u32)p->baseY*0xC2B2AE3Du;
  h^=(u32)p->surfaceId*0x27D4EB2Fu;return h^(h>>16); }
static void Inc(u32 *p) { if(*p!=0xFFFFFFFFu) ++*p; }
static void Lookup(OverworldPickupRouteState *s,const OverworldPickupRoutePosition *p,u8 phase)
{ s->candidate=*p;s->hashIndex=Hash(p)&(s->workspace->visitedCapacity-1u);s->phase=phase; }
static void Restart(OverworldPickupRouteState *s)
{ if(s->searchStamp==0xFFFFFFFFu) { s->status=OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT;return; }
  ++s->searchStamp;s->searchDynamicRevision=s->query.dynamicRevision;s->probeNeeded=0;
  s->hasNextStep=0;s->goalNode=NONE;Lookup(s,&s->query.origin,ROOT_LOOKUP); }
static void BeginProof(OverworldPickupRouteState *s,u16 node)
{ s->goalNode=s->proofNode=node;s->proofLength=0;s->proofRevision=s->query.dynamicRevision;
  s->reserved[0]=0;s->hashIndex=0;s->hasNextStep=0;s->phase=PROOF; }
static void Arrive(OverworldPickupRouteState *s,u16 destination)
{ OverworldPickupRouteNode *n=&s->workspace->nodes[destination];
  s->workspace->edges[s->candidateEdge].destination=destination;
  if(n->searchStamp!=s->searchStamp) { n->searchStamp=s->searchStamp;n->parent=s->candidateFrom;
    n->parentEdge=s->candidateEdge;s->currentNode=destination;s->nodeGoalIndex=0;s->phase=NODE_GOALS;
  } else { s->currentNode=s->candidateFrom;s->phase=SCAN_INIT; } }
static u8 CheckedDestination(OverworldPickupRouteState *s,const OverworldPickupRoutePosition *from,
    const OverworldPickupRouteEdge *edge)
{ return !s->candidate.reserved && s->candidate.x==(s32)from->x+edge->dx
    && s->candidate.y==(s32)from->y+edge->dy; }
static OverworldPickupRouteEdgeResult Ask(OverworldPickupRouteState *s,u16 from,u16 candidate)
{ const OverworldPickupRoutePosition *p=&s->workspace->nodes[from].position;
  const OverworldPickupRouteEdge *e=&s->query.edges[candidate];
  s->candidate=(OverworldPickupRoutePosition){(s16)((s32)p->x+e->dx),(s16)((s32)p->y+e->dy),0,0,0};
  Inc(&s->edgeCalls);return s->query.legalEdge(s->query.context,p,e,&s->candidate); }
static u8 Failure(OverworldPickupRouteState *s,OverworldPickupRouteEdgeResult decision)
{ if(decision==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID || (u32)decision>OVERWORLD_PICKUP_ROUTE_EDGE_RESOURCE_LIMIT)
    s->status=OVERWORLD_PICKUP_ROUTE_INVALID;
  else if(decision==OVERWORLD_PICKUP_ROUTE_EDGE_RESOURCE_LIMIT) s->status=OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT;
  return s->status!=OVERWORLD_PICKUP_ROUTE_PENDING; }
const OverworldPickupRouteCachedEdge *OverworldPickupRoute_ReadMemo(const OverworldPickupRouteState *s,
    const OverworldPickupRoutePosition *from,const OverworldPickupRouteEdge *candidate,
    const OverworldPickupRoutePosition **to)
{
  u16 source,index;
  if(!s || !s->workspace || !from || !candidate || !to) return 0;
  source=s->candidateFrom;index=s->candidateEdge;
  if(s->phase==PROOF) {
    if(s->proofNode>=s->nodeCount) return 0;
    source=s->workspace->nodes[s->proofNode].parent;index=s->workspace->nodes[s->proofNode].parentEdge;
  } else if(s->phase!=TRY_EDGE) return 0;
  if(source>=s->nodeCount || index>=s->cachedEdgeCount
    || from!=&s->workspace->nodes[source].position) return 0;
  const OverworldPickupRouteCachedEdge *memo=&s->workspace->edges[index];
  if(memo->candidate>=s->query.edgeCount || candidate!=&s->query.edges[memo->candidate]
    || memo->decision!=OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL || memo->destination>=s->nodeCount) return 0;
  *to=&s->workspace->nodes[memo->destination].position;return memo;
}
OverworldPickupRouteStatus OverworldPickupRoute_Begin(OverworldPickupRouteState *s,
    const OverworldPickupRouteQuery *q,OverworldPickupRouteWorkspace *w)
{ if(!s) return OVERWORLD_PICKUP_ROUTE_INVALID;
  if(!Valid(q) || !w || !w->nodes || !w->edges || !w->visited || !w->nodeCapacity || !w->edgeCapacity
    || w->visitedCapacity>131072u || w->visitedCapacity<(u32)w->nodeCapacity*2u
    || (w->visitedCapacity&(w->visitedCapacity-1u))) {
    *s=(OverworldPickupRouteState){0};s->status=OVERWORLD_PICKUP_ROUTE_INVALID;return OVERWORLD_PICKUP_ROUTE_INVALID; }
  { OverworldPickupRouteQuery copy=*q;*s=(OverworldPickupRouteState){0};s->query=copy;s->workspace=w; }
  if(w->generation==0xFFFFFFFFu) s->status=OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT;
  else { ++w->generation;Restart(s); }
  return (OverworldPickupRouteStatus)s->status;
}
OverworldPickupRouteStatus OverworldPickupRoute_Resume(OverworldPickupRouteState *s,
    const OverworldPickupRouteQuery *q,u32 budget,OverworldPickupRouteResult *out)
{ u32 used=0;
  if(out) *out=(OverworldPickupRouteResult){0};
  if(!s) { if(out) out->status=OVERWORLD_PICKUP_ROUTE_INVALID;return OVERWORLD_PICKUP_ROUTE_INVALID; }
  if(!Valid(q) || !Valid(&s->query) || !Compatible(&s->query,q)) s->status=OVERWORLD_PICKUP_ROUTE_INVALID;
  else {
    u8 sameOrigin=Pos(&s->query.origin,&q->origin);
    u8 sameGoal=s->query.goalRevision==q->goalRevision && s->query.goals==q->goals && s->query.goalCount==q->goalCount;
    u8 endpoint=!sameOrigin || !sameGoal || !Pos(&s->query.cargoPosition,&q->cargoPosition);
    u8 dynamic=s->query.dynamicRevision!=q->dynamicRevision;
    u8 proofCurrent=s->phase==PROOF && s->reserved[0]==OVERWORLD_PICKUP_ROUTE_PROOF_SUFFIX_CURRENT
        && !(s->reserved[1]|s->reserved[2]) && s->hashIndex==q->dynamicRevision && sameGoal;
    s->reserved[0]=0;
    if(proofCurrent) s->proofRevision=q->dynamicRevision;
    s->query=*q;
    if(s->status==OVERWORLD_PICKUP_ROUTE_UNREACHABLE && (endpoint || dynamic)) {
      s->status=OVERWORLD_PICKUP_ROUTE_PENDING;Restart(s);
    } else if(s->status==OVERWORLD_PICKUP_ROUTE_REACHABLE && (endpoint || dynamic)) {
      if(proofCurrent) {
        if(!sameOrigin) { s->status=OVERWORLD_PICKUP_ROUTE_PENDING;BeginProof(s,s->goalNode); }
      } else { s->status=OVERWORLD_PICKUP_ROUTE_PENDING;s->phase=NODE_GOALS;s->nodeGoalIndex=0;s->probeNeeded=1; }
    } else if(s->status==OVERWORLD_PICKUP_ROUTE_PENDING && endpoint) {
      s->probeNeeded=1;s->nodeGoalIndex=0;
      /* Finish the current bounded edge scan before probing a moved goal.
       * Restarting scoring on every moving endpoint can starve TRY_EDGE.
       * A proof/probe belongs to the old goal and must restart immediately. */
      if(s->phase==PROOF && proofCurrent) s->probeNeeded=0;
      else if(s->phase==PROOF || s->phase==PROBE_GOAL || s->phase==PROBE_LOOKUP) s->phase=NODE_GOALS;
    } else if(s->status==OVERWORLD_PICKUP_ROUTE_PENDING && dynamic && s->phase==PROOF
        && !proofCurrent) BeginProof(s,s->goalNode);
  }
  while(s->status==OVERWORLD_PICKUP_ROUTE_PENDING && used<budget) {
    OverworldPickupRouteWorkspace *w=s->workspace;
    OverworldPickupRouteQuery *current=&s->query;
    ++used;Inc(&s->workUnits);
    switch(s->phase) {
    case ROOT_LOOKUP: case DEST_LOOKUP: {
      OverworldPickupRouteVisited *v=&w->visited[s->hashIndex];u16 node;
      if(v->stamp!=w->generation) {
        if(s->nodeCount==w->nodeCapacity) { s->status=OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT;break; }
        node=s->nodeCount++;w->nodes[node]=(OverworldPickupRouteNode){s->candidate,0,NONE,NONE,NONE,0};
        *v=(OverworldPickupRouteVisited){w->generation,node,0};
      } else {
        node=v->node;if(node>=s->nodeCount) { s->status=OVERWORLD_PICKUP_ROUTE_INVALID;break; }
        if(!Pos(&w->nodes[node].position,&s->candidate)) { s->hashIndex=(s->hashIndex+1)&(w->visitedCapacity-1u);break; }
      }
      if(s->phase==ROOT_LOOKUP) {
        s->rootNode=s->currentNode=node;w->nodes[node].searchStamp=s->searchStamp;
        w->nodes[node].parent=w->nodes[node].parentEdge=NONE;s->nodeGoalIndex=0;s->phase=NODE_GOALS;
      } else Arrive(s,node);
      break;
    }
    case NODE_GOALS:
      if(current->extension) {
        if(current->extension->goal(current->extension->context,&w->nodes[s->currentNode].position))
          BeginProof(s,s->currentNode);
        else s->phase=SCAN_INIT;
        break;
      }
      if(s->probeNeeded) { s->probeNeeded=0;s->goalIndex=0;s->phase=PROBE_GOAL;break; }
      if(s->nodeGoalIndex<current->goalCount) {
        const OverworldPickupRoutePosition *goal=&current->goals[s->nodeGoalIndex++];
        if(!GoalValid(current,goal)) s->status=OVERWORLD_PICKUP_ROUTE_INVALID;
        else if(Pos(goal,&w->nodes[s->currentNode].position)) BeginProof(s,s->currentNode);
      } else s->phase=SCAN_INIT;
      break;
    case PROBE_GOAL:
      if(s->goalIndex==current->goalCount) { s->phase=NODE_GOALS;s->nodeGoalIndex=0;break; }
      if(!GoalValid(current,&current->goals[s->goalIndex])) { s->status=OVERWORLD_PICKUP_ROUTE_INVALID;break; }
      if(Pos(&current->origin,&current->goals[s->goalIndex])) {
        s->goalNode=NONE;s->hasNextStep=0;s->status=OVERWORLD_PICKUP_ROUTE_REACHABLE;break;
      }
      Lookup(s,&current->goals[s->goalIndex],PROBE_LOOKUP);break;
    case PROBE_LOOKUP: {
      OverworldPickupRouteVisited *v=&w->visited[s->hashIndex];
      if(v->stamp!=w->generation) { ++s->goalIndex;s->phase=PROBE_GOAL;break; }
      if(v->node>=s->nodeCount) { s->status=OVERWORLD_PICKUP_ROUTE_INVALID;break; }
      if(Pos(&w->nodes[v->node].position,&s->candidate)) {
        if(w->nodes[v->node].searchStamp==s->searchStamp) BeginProof(s,v->node);
        else { ++s->goalIndex;s->phase=PROBE_GOAL; }
      } else s->hashIndex=(s->hashIndex+1)&(w->visitedCapacity-1u);
      break;
    }
    case SCAN_INIT:
      s->scanIndex=0;s->bestIndex=NONE;s->bestScore=0xFFFFFFFFu;s->phase=SCAN_EDGE;break;
    case SCAN_EDGE:
      if(s->scanIndex==current->edgeCount) {
        if(s->bestIndex!=NONE) { s->edgeCursor=w->nodes[s->currentNode].firstEdge;s->findSelected=1;s->phase=FIND_EDGE; }
        else if(w->nodes[s->currentNode].parent!=NONE) {
          s->currentNode=w->nodes[s->currentNode].parent;s->phase=NODE_GOALS;s->nodeGoalIndex=0;
        } else if(s->searchDynamicRevision!=current->dynamicRevision || !Pos(&w->nodes[s->rootNode].position,&current->origin)) Restart(s);
        else s->status=OVERWORLD_PICKUP_ROUTE_UNREACHABLE;
      } else {
        const OverworldPickupRoutePosition *p=&w->nodes[s->currentNode].position;
        const OverworldPickupRouteEdge *e=&current->edges[s->scanIndex];
        if(!Inside(&current->bounds,(s32)p->x+e->dx,(s32)p->y+e->dy)) ++s->scanIndex;
        else { s->edgeCursor=w->nodes[s->currentNode].firstEdge;s->findSelected=0;s->phase=FIND_EDGE; }
      }
      break;
    case FIND_EDGE:
      if(s->edgeCursor!=NONE) {
        OverworldPickupRouteCachedEdge *e;
        if(s->edgeCursor>=s->cachedEdgeCount) { s->status=OVERWORLD_PICKUP_ROUTE_INVALID;break; }
        e=&w->edges[s->edgeCursor];
        if(e->candidate!=(s->findSelected?s->bestIndex:s->scanIndex)) { s->edgeCursor=e->next;break; }
        if(!s->findSelected && e->usedSearchStamp==s->searchStamp) { ++s->scanIndex;s->phase=SCAN_EDGE;break; }
      }
      if(s->findSelected) s->phase=TRY_EDGE;
      else { s->scanGoal=0;s->score=0xFFFFFFFFu;s->phase=SCORE_EDGE; }
      break;
    case SCORE_EDGE:
      if(current->extension && !s->scanGoal) {
        const OverworldPickupRoutePosition *p=&w->nodes[s->currentNode].position;
        const OverworldPickupRouteEdge *e=&current->edges[s->scanIndex];
        s->score=current->extension->score(current->extension->context,p->x+e->dx,p->y+e->dy);
        s->scanGoal=1;
      }
      if(!current->extension && s->scanGoal<current->goalCount) {
        const OverworldPickupRoutePosition *p=&w->nodes[s->currentNode].position,*g=&current->goals[s->scanGoal++];
        const OverworldPickupRouteEdge *e=&current->edges[s->scanIndex];
        s32 dx=(s32)p->x+e->dx-g->x,dy=(s32)p->y+e->dy-g->y;
        u32 distance=(u32)(dx<0?-dx:dx)+(u32)(dy<0?-dy:dy);
        if(!GoalValid(current,g)) s->status=OVERWORLD_PICKUP_ROUTE_INVALID;
        else if(distance<s->score) s->score=distance;
      } else {
        if(s->score<s->bestScore) { s->bestScore=s->score;s->bestIndex=s->scanIndex; }
        /* Zero is unbeatable; keep the first tie and use the same native
         * edge/proof path before publishing a reachable route. */
        if(s->bestScore==0) {
          s->edgeCursor=w->nodes[s->currentNode].firstEdge;s->findSelected=1;s->phase=FIND_EDGE;
        } else { ++s->scanIndex;s->phase=SCAN_EDGE; }
      }
      break;
    case TRY_EDGE: {
      OverworldPickupRouteCachedEdge *e;OverworldPickupRouteEdgeResult decision;
      if(s->edgeCursor==NONE) {
        if(s->cachedEdgeCount==w->edgeCapacity) { s->status=OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT;break; }
        s->edgeCursor=s->cachedEdgeCount++;
        w->edges[s->edgeCursor]=(OverworldPickupRouteCachedEdge){0,0,NONE,w->nodes[s->currentNode].firstEdge,s->bestIndex,OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED,0};
        w->nodes[s->currentNode].firstEdge=s->edgeCursor;
      }
      e=&w->edges[s->edgeCursor];s->candidateFrom=s->currentNode;s->candidateEdge=s->edgeCursor;
      if(e->decision==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL && e->destination<s->nodeCount) {
        e->usedSearchStamp=s->searchStamp;Arrive(s,e->destination);break;
      }
      if(e->decision==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED && e->dynamicRevision==current->dynamicRevision) {
        e->usedSearchStamp=s->searchStamp;s->phase=SCAN_INIT;break;
      }
      decision=Ask(s,s->currentNode,s->bestIndex);
      if(decision==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED) goto done;
      if(Failure(s,decision)) break;
      e->decision=(u8)decision;e->dynamicRevision=current->dynamicRevision;e->usedSearchStamp=s->searchStamp;
      if(decision==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED) { s->phase=SCAN_INIT;break; }
      if(!CheckedDestination(s,&w->nodes[s->currentNode].position,&current->edges[s->bestIndex])) { s->status=OVERWORLD_PICKUP_ROUTE_INVALID;break; }
      Lookup(s,&s->candidate,DEST_LOOKUP);break;
    }
    case PROOF: {
      OverworldPickupRouteNode *node,*parent;OverworldPickupRouteCachedEdge *e;
      OverworldPickupRouteEdgeResult decision;
      if(s->proofNode>=s->nodeCount || s->proofLength++>s->nodeCount) { s->status=OVERWORLD_PICKUP_ROUTE_INVALID;break; }
      node=&w->nodes[s->proofNode];
      if(Pos(&node->position,&current->origin)) {
        s->hasNextStep=0;s->status=OVERWORLD_PICKUP_ROUTE_REACHABLE;break;
      }
      if(node->parent==NONE) { Restart(s);break; }
      if(node->parent>=s->nodeCount || node->parentEdge>=s->cachedEdgeCount || node->searchStamp!=s->searchStamp) {
        s->status=OVERWORLD_PICKUP_ROUTE_INVALID;break;
      }
      parent=&w->nodes[node->parent];e=&w->edges[node->parentEdge];
      if(parent->searchStamp!=s->searchStamp || e->destination!=s->proofNode) { Restart(s);break; }
      if(e->dynamicRevision!=current->dynamicRevision || e->decision!=OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL) {
        decision=Ask(s,node->parent,e->candidate);
        if(decision==OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED) { --s->proofLength;goto done; }
        if(Failure(s,decision)) break;
        e->decision=(u8)decision;e->dynamicRevision=current->dynamicRevision;
        if(decision==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED) { e->usedSearchStamp=0;Restart(s);break; }
        if(!CheckedDestination(s,&parent->position,&current->edges[e->candidate])) { s->status=OVERWORLD_PICKUP_ROUTE_INVALID;break; }
        if(!Pos(&s->candidate,&node->position)) { e->dynamicRevision=0;e->decision=OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED;Restart(s);break; }
      }
      if(Pos(&parent->position,&current->origin)) {
        s->candidate=node->position;s->candidateEdge=node->parentEdge;s->hasNextStep=1;
        s->status=OVERWORLD_PICKUP_ROUTE_REACHABLE;
      } else s->proofNode=node->parent;
      break;
    }
    default:s->status=OVERWORLD_PICKUP_ROUTE_INVALID;break;
    }
  }
done:
  if(out) {
    out->status=s->status;out->workUsed=used;out->totalWork=s->workUnits;out->edgeCalls=s->edgeCalls;out->visitedNodes=s->nodeCount;
    if(s->status==OVERWORLD_PICKUP_ROUTE_REACHABLE) {
      out->subject=s->query.subject;out->cargo=s->query.cargo;out->origin=s->query.origin;out->cargoPosition=s->query.cargoPosition;
      out->pickupPosition=s->goalNode==NONE?s->query.origin:s->workspace->nodes[s->goalNode].position;
      out->scopeRevision=s->query.scopeRevision;out->movementPolicyRevision=s->query.movementPolicyRevision;
      out->goalRevision=s->query.goalRevision;out->dynamicRevision=s->query.dynamicRevision;out->hasNextStep=s->hasNextStep;
      if(s->hasNextStep) { out->nextStep=s->candidate;out->edgeTag=s->query.edges[s->workspace->edges[s->candidateEdge].candidate].tag; }
    }
  }
  return (OverworldPickupRouteStatus)s->status;
}

u16 OverworldPickupRoute_CopyForwardWitness(const OverworldPickupRouteState *s,
    u16 *edgeTags,OverworldPickupRoutePosition *poses,u16 capacity)
{ u16 node,count=0;
  if(!s || !edgeTags || s->status!=OVERWORLD_PICKUP_ROUTE_REACHABLE
    || !s->query.extension || !Valid(&s->query) || !s->workspace
    || s->goalNode>=s->nodeCount || s->proofRevision!=s->query.dynamicRevision) return NONE;
  node=s->goalNode;
  /* Count and validate first. A short output may not publish a partial trip. */
  while(node!=s->rootNode) {
    const OverworldPickupRouteNode *n;const OverworldPickupRouteCachedEdge *e;
    if(node>=s->nodeCount || count>=s->nodeCount || count>=capacity) return NONE;
    n=&s->workspace->nodes[node];
    if(n->parent>=s->nodeCount || n->parentEdge>=s->cachedEdgeCount
      || n->searchStamp!=s->searchStamp) return NONE;
    e=&s->workspace->edges[n->parentEdge];
    if(e->destination!=node || e->candidate>=s->query.edgeCount
      || e->decision!=OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL
      || e->dynamicRevision>s->query.dynamicRevision
      || e->usedSearchStamp!=s->searchStamp) return NONE;
    ++count;node=n->parent;
  }
  node=s->goalNode;
  for(u16 i=0;i<count;i++) {
    const OverworldPickupRouteNode *n=&s->workspace->nodes[node];
    u16 tag=s->query.edges[s->workspace->edges[n->parentEdge].candidate].tag;
    if(s->query.extension->flags&OVERWORLD_PICKUP_ROUTE_EXTENSION_REVERSE) {
      /* Preserve typed native kind/escape bits, invert direction only. */
      static const u8 opposite[8]={1,0,3,2,7,6,5,4};
      edgeTags[i]=(tag&~7u)|opposite[tag&7];
      if(poses) poses[i]=s->workspace->nodes[n->parent].position;
    } else { edgeTags[count-1-i]=tag;if(poses) poses[count-1-i]=n->position; }
    node=n->parent;
  }
  return count;
}
