#ifndef OVERWORLD_CARGO_READ_WILD_H
#define OVERWORLD_CARGO_READ_WILD_H

#include "overworld_cargo_query_wild.h"
#include "player_health_throw_observation.h"

struct OverworldActorSystemEntry;
struct OverworldActorSystemDebugLayout;
struct OverworldActorSystemState;

typedef struct OverworldCargoReadWildObservationCall {
    OverworldCargoQueryWildCall cargo;
    OverworldWildBehaviorConditionRuntime *conditions;
    const PlayerHealthThrowServiceEntry *throwService;
    PlayerHealthThrowIsCurrentSpawnFunc isCurrentSpawn;
    PlayerHealthThrowQueryTargetFunc queryTarget;
} OverworldCargoReadWildObservationCall;

/* Existing dispatcher targets; the caller asserts its legacy aliases. */
#define OVERWORLD_CARGO_READ_TARGET_ADJACENT 6
#define OVERWORLD_CARGO_READ_TARGET_CIRCLE 9
struct FIELD_PLAYER_AVATAR;
typedef struct OverworldCargoReadWildTargetOps {
    int (*playerX)(struct FIELD_PLAYER_AVATAR *);
    int (*playerY)(struct FIELD_PLAYER_AVATAR *);
    PlayerHealthThrowIsCurrentSpawnFunc isCurrentSpawn;
    PlayerHealthThrowQueryTargetFunc queryTarget;
    BOOL (*circleTarget)(OverworldWildSpawnState *,FieldSystem *,int,
        const OverworldWildBehaviorProfile *,u8,int,int,int,int,int *,int *);
    BOOL (*adjacentTarget)(OverworldWildSpawnState *,FieldSystem *,int,
        const OverworldWildBehaviorProfile *,int *,int *);
} OverworldCargoReadWildTargetOps;
typedef struct OverworldCargoReadWildTargetCall {
    OverworldWildSpawnState *state;
    struct LocalMapObject *object;
    const OverworldWildBehaviorProfile *profile;
    const PlayerHealthThrowServiceEntry *throwService;
    const OverworldCargoReadWildTargetOps *ops;
    u8 slot, movementTarget, throwTarget, reserved;
} OverworldCargoReadWildTargetCall;
typedef struct OverworldCargoReadWildTarget {
    struct LocalMapObject *targetObject;
    int objectX,objectY,playerX,playerY,impactX,impactY,dx,dy;
    u8 targetSlot,throwDistance,direction,reserved;
} OverworldCargoReadWildTarget;
enum OverworldCargoReadWildTargetResult {
    OVERWORLD_CARGO_READ_TARGET_NONE,
    OVERWORLD_CARGO_READ_TARGET_VALID,
    OVERWORLD_CARGO_READ_TARGET_ABORT
};
u8 OverworldCargoReadWild_Target(
    const OverworldCargoReadWildTargetCall *, OverworldCargoReadWildTarget *);

const OverworldWildBehaviorConditionOptions *OverworldCargoReadWild_Options(
    const OverworldPickupRouteWildWorld *);
OverworldPickupRouteStatus OverworldCargoReadWild_Route(
    const OverworldCargoQueryWildCall *, OverworldCargoQueryResult *);
u32 OverworldCargoReadWild_Observe(
    const OverworldCargoReadWildObservationCall *, BOOL *needAbort);
OverworldPickupRouteEdgeResult OverworldCargoReadWild_Reach(
    void *, const OverworldPickupRoutePosition *, const OverworldPickupRoutePosition *);
const struct OverworldActorSystemState *OverworldCargoReadWild_ActorState(
    const struct OverworldActorSystemEntry *,
    const struct OverworldActorSystemDebugLayout *,
    const struct OverworldActorSystemState *);

#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char CargoReadWildTargetCallMustRemain24[
    sizeof(OverworldCargoReadWildTargetCall) == 24 ? 1 : -1];
typedef char CargoReadWildTargetMustRemain40[
    sizeof(OverworldCargoReadWildTarget) == 40 ? 1 : -1];
typedef char CargoReadWildTargetOpsMustRemain24[
    sizeof(OverworldCargoReadWildTargetOps) == 24 ? 1 : -1];
typedef char CargoReadWildObservationCallMustRemain48[
    sizeof(OverworldCargoReadWildObservationCall) == 48 ? 1 : -1];
#endif
#endif /* OVERWORLD_CARGO_READ_WILD_H */
