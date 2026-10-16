#ifndef OVERWORLD_CARGO_QUERY_WILD_H
#define OVERWORLD_CARGO_QUERY_WILD_H
#include "overworld_cargo_query.h"
#include "overworld_pickup_route_wild.h"
/* Query code and the sole work buffer share stock Field resource heap4.
 * Both must drain before parent Field exit, leaving32KiB for stock work. */
#define OVERWORLD_FIELD_QUERY_HEAP_ID 4
#define OVERWORLD_FIELD_QUERY_HEAP_RESERVE 0x8000
/* The lazy work buffer keeps16KiB of heap4 free. FIELD1 now also holds the
 * behavior catalog and sits near63KiB free on a populated route, so the
 * blob reserve would refuse every pickup and entry route. */
#define OVERWORLD_FIELD_PICKUP_QUERY_HEAP_RESERVE 0x4000
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
