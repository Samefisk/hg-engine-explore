#ifndef OVERWORLD_THROW_HELD_WILD_H
#define OVERWORLD_THROW_HELD_WILD_H
#include "overworld_cargo_read_wild.h"
#include "overworld_throw_away_wild.h"
typedef struct OverworldThrowHeldWildOps {
    const struct LocalMapObject *(*bindingBody)(OverworldWildSpawnState *, int, u8, int, int);
    void (*clearMovement)(struct LocalMapObject *);
    BOOL (*startJump)(OverworldWildSpawnState *, FieldSystem *, int, struct LocalMapObject *, u8, u8, int, int, const OverworldWildBehaviorProfile *, BOOL);
    void (*recovery)(OverworldWildSpawnState *, int, const OverworldWildBehaviorProfile *, const OverworldWildBehaviorPrimitives *);
    void (*release)(OverworldWildSpawnState *, int, int, struct LocalMapObject *);
    void (*facing)(struct LocalMapObject *, u8);
    void (*bubble)(struct LocalMapObject *, u8);
    u8 (*bubbleId)(const OverworldWildBehaviorProfile *);
    void (*abort)(OverworldWildSpawnState *, int);
} OverworldThrowHeldWildOps;
typedef struct OverworldThrowHeldWildCall {
    OverworldPickupRouteWildWorld *world;
    const PlayerHealthThrowServiceEntry *throwService;
    const OverworldWildBehaviorProfile *profile;
    const OverworldWildBehaviorPrimitives *primitives;
    OverworldCargoReadWildTarget *read;
    const OverworldThrowHeldWildOps *ops;
    u8 throwTarget, movementTarget, reserved[2];
} OverworldThrowHeldWildCall;
BOOL OverworldThrowHeldWild_Run(const OverworldThrowHeldWildCall *);
/* The existing Throw owner may retire an unheld Cargo claim without ending
 * its Interest or touching an accepted Actor movement. */
BOOL OverworldThrowHeldWild_ReleaseCargo(const OverworldPickupRouteWildWorld *);
#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char ThrowHeldWildCallMustRemain28[sizeof(OverworldThrowHeldWildCall)==28?1:-1];
typedef char ThrowHeldWildOpsMustRemain36[sizeof(OverworldThrowHeldWildOps)==36?1:-1];
#endif
#endif
