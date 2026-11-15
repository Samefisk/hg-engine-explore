#ifndef OVERWORLD_CARGO_QUERY_WILD_H
#define OVERWORLD_CARGO_QUERY_WILD_H
#include "overworld_cargo_query.h"
#include "overworld_pickup_route_wild.h"
/* The stock Field owner drains both workspace blocks before code/heap exit.
 * Code/catalog cold admission keeps 28 KiB on their respective heaps. On
 * FIELD1 that is the measured need after the catalog: the lazy 11268-byte
 * Cargo array plus its own 16 KiB reserve and margin (checked in
 * overworld_cargo_query_wild.c). 32 KiB kept Olivine, Cianwood and Routes
 * 38/39 (70.9-71.8 KB free) without Wild. FIELD2 keeps more than 20 KiB. */
#define OVERWORLD_FIELD_QUERY_HEAP_ID 4
#define OVERWORLD_FIELD_QUERY_HEAP_RESERVE 0x7000
/* Lazy arrays keep16KiB on heap4; owner/cache/path state keeps20KiB on11
 * for stock scripts. Each allocation also keeps64 bytes for heap overhead. */
#define OVERWORLD_FIELD_PICKUP_QUERY_HEAP_RESERVE 0x4000
#define OVERWORLD_FIELD_QUERY_CORE_HEAP_ID 11
#define OVERWORLD_FIELD_QUERY_CORE_HEAP_RESERVE (20u*1024u)
#define OVERWORLD_FIELD_QUERY_ALLOCATION_MARGIN 64u
/* Published only after both blocks are owned. Teardown reads this common
 * prefix before freeing either block; no addon callback survives the drain. */
#define OVERWORLD_FIELD_QUERY_ALLOCATION_VERSION 0x3251574Fu /* OWQ2 */
typedef struct OverworldCargoQueryWildAllocation {
    void *auxiliary;
    void (*destroy)(void *);
    u32 version;
} OverworldCargoQueryWildAllocation;
struct OverworldConditionNativeCall;
struct OverworldEntryRouteCommand;
/* Synchronous native setup for the sole Field query. It never owns movement.
 * The caller's actual lane/terrain rules also govern the returned START. */
typedef struct OverworldCargoQueryWildCall {
    OverworldPickupRouteWildWorld *world;
    const OverworldWildBehaviorProfile *profile;
    /* Observation borrows the existing native-condition callback here.
     * Route replaces it with authored options before any query Tick. */
    __extension__ union {
        const OverworldWildBehaviorConditionOptions *options;
        const struct OverworldEntryRouteCommand *entry;
        OverworldBehaviorConditionStatus (*conditionNative)(struct OverworldConditionNativeCall *);
    };
    void *(*allocate)(u32, u32);
    u32 (*freeSize)(u32);
    u32 heapId;
    u16 eligibleActorMask, allowedTerrainMask;
    u8 locomotion;
    __extension__ union { u8 reserved[3]; struct { u8 routeOperation, operationReserved[2]; }; };
} OverworldCargoQueryWildCall;
OverworldPickupRouteStatus OverworldCargoQueryWild_Tick(
    const OverworldCargoQueryWildCall *, OverworldCargoQueryResult *);
#endif
