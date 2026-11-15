#ifndef OVERWORLD_CARGO_QUERY_H
#define OVERWORLD_CARGO_QUERY_H
#include "overworld_pickup_route_native.h"
#include "overworld_behavior_conditions.h"

#define OVERWORLD_CARGO_QUERY_VERSION 2
#define OVERWORLD_CARGO_QUERY_SELECT_NEAREST 1u
#define OVERWORLD_CARGO_QUERY_SWITCH_ADVANTAGE_SHIFT 1
#define OVERWORLD_CARGO_QUERY_SELECTION_FLAGS 7u
#define OVERWORLD_CARGO_QUERY_SCORE_UNKNOWN 0xFFFFu
#define OVERWORLD_CARGO_QUERY_RANK_INCUMBENT 1
#define OVERWORLD_CARGO_QUERY_RANK_SCAN 2
#define OVERWORLD_CARGO_QUERY_RANK_REPROVE 3
#define OVERWORLD_CARGO_QUERY_RANK_DONE 4
#define OVERWORLD_CARGO_QUERY_RANK_FINAL_INCUMBENT 5
#define OVERWORLD_CARGO_QUERY_INTERNAL_WORK 16
#define OVERWORLD_CARGO_QUERY_NODES 256
#define OVERWORLD_CARGO_QUERY_EDGES 512
#define OVERWORLD_CARGO_QUERY_HASH 512
#define OVERWORLD_CARGO_QUERY_CHANGES 512

typedef struct OverworldCargoQueryChangedTile { s16 x, y; } OverworldCargoQueryChangedTile;
typedef struct OverworldCargoQueryTileStamp {
    s16 x, y;
    u32 revision;
} OverworldCargoQueryTileStamp;

/* One Field-owned descriptor shared by every pickup intent. Bind owned
 * arrays once; Init/Clear clear only64 validity bytes, never the large
 * backing arrays. They neither allocate nor free the owner's storage. */
typedef struct OverworldCargoQueryStorage {
    OverworldPickupRouteWorkspace workspace;
    u32 changeGeneration;
    OverworldCargoQueryTileStamp *changes;
    u8 *changesValid; /* OVERWORLD_CARGO_QUERY_CHANGES bits. */
} OverworldCargoQueryStorage;
/* Optional contiguous backing. The native owner splits the same arrays
 * across its two Field heaps; the descriptor never assumes adjacency. */
typedef struct OverworldCargoQueryBuffers {
    OverworldPickupRouteNode nodes[OVERWORLD_CARGO_QUERY_NODES];
    OverworldPickupRouteCachedEdge edges[OVERWORLD_CARGO_QUERY_EDGES];
    OverworldPickupRouteVisited visited[OVERWORLD_CARGO_QUERY_HASH];
    u8 visitedValid[OVERWORLD_CARGO_QUERY_HASH/8];
    OverworldCargoQueryTileStamp changes[OVERWORLD_CARGO_QUERY_CHANGES];
    u8 changesValid[OVERWORLD_CARGO_QUERY_CHANGES/8];
} OverworldCargoQueryBuffers;
/* Bind zeroed caller-owned backing once, before Init. Clear/Begin retain
 * these pointers and never clear the large node/edge/ledger arrays. */
static inline void OverworldCargoQuery_BindStorage(OverworldCargoQueryStorage *s,
    OverworldCargoQueryBuffers *b)
{
    *s=(OverworldCargoQueryStorage){
        {b->nodes,b->edges,b->visited,OVERWORLD_CARGO_QUERY_NODES,
         OVERWORLD_CARGO_QUERY_EDGES,OVERWORLD_CARGO_QUERY_HASH,0,b->visitedValid},
        0,b->changes,b->changesValid};
}

typedef struct OverworldCargoQueryWork {
    OverworldPickupRouteNativeWork native;
    u16 routeUnits;
    u8 positionReads, edgeQueries, goalQueries, candidateChecks;
    u16 changedTiles, changeProbes, witnessProbes;
} OverworldCargoQueryWork;

typedef struct OverworldCargoQueryInput {
    u16 version, size;
    /* Current synchronous Native world/policy, including resolved profile and
     * lane. No pointers to a caller's stack remain after Tick returns. */
    OverworldPickupRouteNativeContext *runtime;
    const OverworldBehaviorConditionWorldView *bindingsWorld;
    /* Current full subject, origin, loaded bounds, revisions and borrowed
     * resolved-policy edge candidates. Cargo/goals/callback are filled here.
     * Edges must stay at one stable address until Clear or policy change. */
    const OverworldPickupRouteQuery *seed;
    OverworldPickupRouteEdgeResult (*readPosition)(void *, const OverworldActorHandle *,
        OverworldPickupRoutePosition *);
    /* Default mode fixes this exact Cargo. Nearest mode proves it first as
     * the incumbent, then applies the authored switch advantage. */
    const OverworldActorHandle *requiredCargo;
    /* Complete old/new dynamic footprints from the native manager, player and
     * Actor reservation owner. Include occupancy/height/collision-flag changes,
     * player/front-tile dependencies and old/new reservation endpoints. Never
     * just Pokemon or frame numbers. Each changed tile needs the new revision.
     * Missing/too large history disables reuse, never grants LEGAL. */
    const OverworldCargoQueryChangedTile *changedTiles;
    u16 changedTileCount;
    u8 changesComplete, selectionFlags; /* Nearest bit0, advantage bits1..2. */
    u32 requestKey; /* Authored application/condition/action identity, nonzero. */
    u16 eligibleActorMask; /* Observation indices, same as condition input. */
    u8 pickupDistance, internalWork; /* Authored reach; work0..16. */
} OverworldCargoQueryInput;

typedef struct OverworldCargoQueryResult {
    OverworldPickupRouteResult route;
    OverworldCargoQueryWork lastWork;
    u16 eligibleActorMask;
    u8 status, flags;
} OverworldCargoQueryResult;
/* PENDING may retain one previously admitted bound Cargo condition. This is
 * not route/landing/pickup admission: eligibleActorMask and hasNextStep stay0.
 * Consumers must reject unknown flags and must not select a new Cargo from
 * this flag. REACHABLE is still required before a real START or pickup. */
#define OVERWORLD_CARGO_QUERY_RETAIN_BOUND_CARGO 1u
#define OVERWORLD_CARGO_QUERY_RESULT_FLAGS OVERWORLD_CARGO_QUERY_RETAIN_BOUND_CARGO
typedef struct OverworldCargoQueryState OverworldCargoQueryState;

/* Only one owner may call this state. A second request/role/full identity or
 * static scope/policy change resets the search; moving Subject/Cargo and
 * relevant occupancy updates retain the compatible route graph. Do not use
 * frame counters as dynamicRevision. One Tick per completed Field frame;
 * duplicate calls publish no eligible mask and perform no native query.
 *
 * Candidate selection and every legal standing goal are resumed. No Cargo
 * distance cutoff. A single goal/edge classifier runs per Tick, plus one
 * bounded canonical Cargo-position read. DEFERRED stays PENDING; exhaustion
 * stays RESOURCE_LIMIT, never UNREACHABLE. Only a current proved route grants
 * eligibility. Its first edge goes to existing START. Tick never captures a
 * binding, claims Cargo, changes poses or cancels accepted Walk/Skid/Hop.
 * Physical pickup still uses the same Native pickupReach callback and exact
 * accepted-motion receipt at the real owner's atomic transfer boundary.
 *
 * Nearest is opt-in. It scores only a proved legal pickup position by
 * Chebyshev distance from the current origin. It uses the same workspace,
 * skips candidates whose geometric lower bound cannot improve the winner,
 * and re-proves that full winner before publishing eligibility. This is not
 * a shortest-path distance promise. A required Cargo is an incumbent in this
 * mode; invalid/unreachable incumbents do not require a switch advantage.
 * PENDING and RESOURCE_LIMIT never prove that an incumbent is unreachable.
 * Clear starts the next ranking pass; the caller owns its check interval.
 *
 * ARM: State424 + descriptor40 + backing19584 =20048 bytes, plus the caller's
 * resolved edge array (6 bytes/candidate) and Native world/context. Result140
 * is a synchronous receipt. Both512-cell tables use validity bitmaps, with
 * full32-bit generation/revision/wrap checks. Tick bounds:16 route units, one native
 * edge/goal, one canonical position read, <=4096 change-table probes and
 * <=8192 witness comparisons. Native Hop adds its authored stride clearance
 * budget. These counts are not a game-frame pacing proof.
 *
 * Clear BEFORE addon/Field teardown; clear the caller's Native world/query
 * pointers too. Caller may then free every owned backing block. */
/* Shared current dynamic ledger, also used by the sole Entry traversal.
 * These are read-only facts, not a new query or ownership grant. */
u8 OverworldCargoQuery_ObserveChanges(OverworldCargoQueryState *,const OverworldCargoQueryInput *);
u8 OverworldCargoQuery_Unchanged(OverworldCargoQueryState *,const OverworldPickupRoutePosition *,
    const OverworldPickupRoutePosition *,u32 revision);
u8 OverworldCargoQuery_ProofUnchanged(OverworldCargoQueryState *,u16 limit);
void OverworldCargoQuery_Init(OverworldCargoQueryState *state,
    OverworldCargoQueryStorage *storage);
void OverworldCargoQuery_Clear(OverworldCargoQueryState *state);
OverworldPickupRouteStatus OverworldCargoQuery_Tick(OverworldCargoQueryState *state,
    const OverworldCargoQueryInput *input, OverworldCargoQueryResult *result);

struct OverworldCargoQueryState {
    OverworldPickupRouteState route;
    OverworldPickupRouteQuery query;
    OverworldPickupRoutePosition goal;
    OverworldCargoQueryStorage *storage;
    OverworldPickupRouteNativeContext *runtime; /* Synchronous Tick only. */
    OverworldCargoQueryWork lastWork;
    u32 requestKey, frame, checkedDynamicRevision, goalRevision;
    s16 goalDX, goalDY;
    u32 observedRevision, evictionFloor;
    u16 version, size;
    u8 goalExhausted, edgeOwed; /* Reserved-byte phase:0 goal turn,1 edge owed,2 deferred edge. */
    u8 candidate, scan, roleMask, distance;
    u8 active, started, goalValid, goalDirty;
    u8 frameValid, unitUsed, required, changesKnown;
    OverworldActorHandle incumbent, bestCargo;
    u16 incumbentScore, bestScore, triedMask;
    u8 selectionFlags, rankPhase;
    s16 incumbentX, incumbentY, bestX, bestY; /* Proved standing XY; scores are estimates until reproof. */
};

#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char CargoQueryStorageMustRemain40[sizeof(OverworldCargoQueryStorage)==40?1:-1];
typedef char CargoQueryStateMustRemain424[sizeof(OverworldCargoQueryState)==424?1:-1];
typedef char CargoQueryInputMustRemain40[sizeof(OverworldCargoQueryInput)==40?1:-1];
typedef char CargoQueryResultMustRemain140[sizeof(OverworldCargoQueryResult)==140?1:-1];
#endif
#endif
