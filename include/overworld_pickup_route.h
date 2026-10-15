#ifndef OVERWORLD_PICKUP_ROUTE_H
#define OVERWORLD_PICKUP_ROUTE_H
#include "overworld_actor_system.h"
#define OVERWORLD_PICKUP_ROUTE_VERSION 3
#define OVERWORLD_PICKUP_ROUTE_NONE 0xFFFF
#define OVERWORLD_PICKUP_ROUTE_PHASE_PROOF 10
#define OVERWORLD_PICKUP_ROUTE_PROOF_SUFFIX_CURRENT 1

typedef enum OverworldPickupRouteStatus {
    OVERWORLD_PICKUP_ROUTE_PENDING = 0, OVERWORLD_PICKUP_ROUTE_REACHABLE,
    OVERWORLD_PICKUP_ROUTE_UNREACHABLE, OVERWORLD_PICKUP_ROUTE_INVALID,
    OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT,
} OverworldPickupRouteStatus;
typedef struct OverworldPickupRoutePosition {
    s16 x, y; s32 baseY; u16 surfaceId, reserved;
} OverworldPickupRoutePosition;
typedef struct OverworldPickupRouteBounds {
    s16 minX, minY, maxX, maxY; /* Inclusive loaded scope, never a Cargo radius. */
} OverworldPickupRouteBounds;
typedef struct OverworldPickupRouteEdge { s16 dx, dy; u16 tag; } OverworldPickupRouteEdge;
typedef enum OverworldPickupRouteEdgeResult {
    OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED = 0, OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL,
    OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED, OVERWORLD_PICKUP_ROUTE_EDGE_INVALID,
    OVERWORLD_PICKUP_ROUTE_EDGE_RESOURCE_LIMIT,
} OverworldPickupRouteEdgeResult;
/* One bounded read-only native query, from the supplied hypothetical pose.
 * The caller enumerates resolved-policy candidates; this module never selects
 * Walk/Hop, resolves a profile, reserves Cargo or starts motion. Fill LEGAL
 * destination baseY/surfaceId. XY must equal origin + edge. DEFERRED is not
 * BLOCKED; missing current terrain must not prove no route. */
typedef OverworldPickupRouteEdgeResult (*OverworldPickupRouteLegalEdge)(
    void *, const OverworldPickupRoutePosition *, const OverworldPickupRouteEdge *,
    OverworldPickupRoutePosition *);
/* Optional typed traversal binding. Cargo leaves this NULL and retains its
 * two current full Actor handles. Entry uses a real prepared-attempt receipt,
 * never a fabricated Actor. The receipt, callbacks and context remain owned
 * by the sole Field query until Clear. Query.goalRevision freezes its serial. */
#define OVERWORLD_PICKUP_ROUTE_EXTENSION_VERSION 1
#define OVERWORLD_PICKUP_ROUTE_EXTENSION_PREPARED 1
#define OVERWORLD_PICKUP_ROUTE_EXTENSION_ENTRY_ACTOR 2
#define OVERWORLD_PICKUP_ROUTE_EXTENSION_REVERSE 1
typedef struct OverworldPickupRouteExtension {
    u16 version, size;
    u8 kind, flags; u16 reserved;
    u8 (*current)(void *);
    u8 (*goal)(void *, const OverworldPickupRoutePosition *);
    u32 (*score)(void *, s16, s16);
    void *context;
} OverworldPickupRouteExtension;
typedef struct OverworldPickupRouteQuery {
    u16 version, size;
    OverworldActorHandle subject, cargo;
    OverworldPickupRouteBounds bounds;
    OverworldPickupRoutePosition origin, cargoPosition;
    /* Static scope includes support heights/surfaces and loaded terrain.
     * scope/policy/full-handle changes require Begin, not cached reachability.
     * Dynamic occupancy advances dynamicRevision. It may invalidate an edge's
     * legality, never its static landing support; support changes are scope.
     * Cargo retargeting advances goalRevision. Arrays/context remain borrowed
     * and valid; policy candidates cannot change without policy revision. */
    u32 scopeRevision, movementPolicyRevision, goalRevision, dynamicRevision;
    const OverworldPickupRouteEdge *edges;
    const OverworldPickupRoutePosition *goals; /* Legal standing poses, not Cargo XY. */
    OverworldPickupRouteLegalEdge legalEdge;
    void *context;
    u16 edgeCount, goalCount;
    const OverworldPickupRouteExtension *extension;
} OverworldPickupRouteQuery;
/* Storage belongs to exactly one query. Caller zeroes table stamps once and
 * initializes generation=0. Begin increments generation without table clear.
 * Generation wrap fails RESOURCE_LIMIT; caller must explicitly reset storage.
 * Node/edge arrays do not require initialization. No allocation or recursion. */
typedef struct OverworldPickupRouteNode {
    OverworldPickupRoutePosition position;
    u32 searchStamp;
    u16 parent, parentEdge, firstEdge, reserved;
} OverworldPickupRouteNode;
typedef struct OverworldPickupRouteCachedEdge {
    u32 dynamicRevision, usedSearchStamp;
    u16 destination, next, candidate;
    u8 decision, reserved;
} OverworldPickupRouteCachedEdge;
typedef struct OverworldPickupRouteVisited {
    u32 stamp; u16 node, reserved;
} OverworldPickupRouteVisited;
typedef struct OverworldPickupRouteWorkspace {
    OverworldPickupRouteNode *nodes;
    OverworldPickupRouteCachedEdge *edges;
    OverworldPickupRouteVisited *visited;
    u16 nodeCapacity, edgeCapacity;
    u32 visitedCapacity, generation; /* H power of two, >=2N, <=131072. */
} OverworldPickupRouteWorkspace;
typedef struct OverworldPickupRouteState {
    OverworldPickupRouteQuery query;
    OverworldPickupRouteWorkspace *workspace;
    OverworldPickupRoutePosition candidate;
    u32 hashIndex, workUnits, edgeCalls, searchStamp;
    u32 searchDynamicRevision, proofRevision, score, bestScore;
    u16 nodeCount, cachedEdgeCount, currentNode, rootNode, goalNode, proofNode;
    u16 scanIndex, bestIndex, edgeCursor, scanGoal, goalIndex, nodeGoalIndex;
    u16 proofLength, candidateFrom, candidateEdge;
    u8 phase, findSelected, probeNeeded, status, hasNextStep, reserved[3];
    /* During PROOF only: proofRevision is the complete-ledger witness
     * revision for every checked directed suffix edge.
     * A caller may set reserved[0]=PROOF_SUFFIX_CURRENT and hashIndex=current
     * dynamicRevision only after proving that whole suffix unchanged. Resume
     * consumes it once; unknown flags or a different stamp grant no reuse.
     * Every other phase keeps the original score/hash meanings. */
} OverworldPickupRouteState;
typedef struct OverworldPickupRouteResult {
    OverworldActorHandle subject, cargo;
    OverworldPickupRoutePosition origin, cargoPosition, pickupPosition, nextStep;
    u32 scopeRevision, movementPolicyRevision, goalRevision, dynamicRevision;
    u32 workUsed, totalWork, edgeCalls;
    u16 visitedNodes, edgeTag;
    u8 status, hasNextStep, reserved[2];
} OverworldPickupRouteResult;
/* One goal-directed resumable DFS. Cargo changes retain compatible graph and
 * exploration. Subject movement is provisional until a forward predecessor
 * path reaches the exact current origin; otherwise search re-roots over cache.
 * REACHABLE validates EVERY returned path edge at current dynamicRevision.
 * Caller rechecks result binding and physical pickup height/reach before use.
 * Chase submits nextStep/tag to the existing motion owner; no second executor.
 * Dynamic change during a failed traversal prevents UNREACHABLE until a full
 * current-origin/current-revision traversal completes. Capacity is never used
 * as a no-route proof. No shortest-path promise and no distance cutoff.
 *
 * ARM storage: State 188 + Workspace 24 + 24N + 16M + 8H bytes; Result108.
 * Example N256/M512/H512: 18,640 bytes, plus borrowed candidates/goals.
 * Begin/re-root constant work. Each Resume iteration consumes one work unit:
 * pose-table probe, candidate/cache comparison, goal score, or proof edge.
 * At most one bounded native callback per unit; deferred returns immediately.
 */
/* One typed binding check shared with the native edge adapter. */
u8 OverworldPickupRoute_QueryCurrent(const OverworldPickupRouteQuery *);
OverworldPickupRouteStatus OverworldPickupRoute_Begin(OverworldPickupRouteState *,
    const OverworldPickupRouteQuery *, OverworldPickupRouteWorkspace *);
OverworldPickupRouteStatus OverworldPickupRoute_Resume(OverworldPickupRouteState *,
    const OverworldPickupRouteQuery *, u32, OverworldPickupRouteResult *);
/* Copy a completed reverse witness in execution order: admitted offscreen
 * origin toward the immutable target. Capacity failure writes nothing and
 * returns NONE. Full endpoints retain displacement; tags retain native forward
 * direction and kind, not reverse search tags. Guidance is not an executor. */
u16 OverworldPickupRoute_CopyForwardWitness(const OverworldPickupRouteState *,
    u16 *edgeTags, OverworldPickupRoutePosition *, u16 capacity);
/* Read-only witness for the exact legalEdge callback now in progress. This
 * exposes an existing LEGAL memo, never a different candidate or old root.
 * No callback, search mutation, or layout change. The caller may reuse it only
 * after independently proving all dynamic edge facts unchanged since revision.
 */
const OverworldPickupRouteCachedEdge *OverworldPickupRoute_ReadMemo(const OverworldPickupRouteState *,
    const OverworldPickupRoutePosition *, const OverworldPickupRouteEdge *,
    const OverworldPickupRoutePosition **destination);
#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char PickupRouteStateMustRemain188[sizeof(OverworldPickupRouteState)==188?1:-1];
typedef char PickupRouteWorkspaceMustRemain24[sizeof(OverworldPickupRouteWorkspace)==24?1:-1];
#endif
typedef char PickupRouteNodeMustRemain24[sizeof(OverworldPickupRouteNode)==24?1:-1];
typedef char PickupRouteEdgeMustRemain16[sizeof(OverworldPickupRouteCachedEdge)==16?1:-1];
typedef char PickupRouteVisitedMustRemain8[sizeof(OverworldPickupRouteVisited)==8?1:-1];
typedef char PickupRouteResultMustRemain108[sizeof(OverworldPickupRouteResult)==108?1:-1];
#endif
