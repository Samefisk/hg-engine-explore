#ifndef OVERWORLD_RETURN_MOVE_WILD_H
#define OVERWORLD_RETURN_MOVE_WILD_H

#include "overworld_wild_spawns_internal.h"
#include "overworld_wild_movement.h"
#include "overworld_motion_model.h"

typedef struct OverworldWildDirectionStepContext {
    OverworldWildSpawnState *state;
    FieldSystem *fieldSystem;
    LocalMapObject *object;
    const OverworldWildBehaviorProfile *profile;
    const OverworldWildBehaviorPrimitives *primitives;
    u8 slot;
    u16 allowedTile;
    u8 jumpLevel;
    u8 avoidPreviousTile;
} OverworldWildDirectionStepContext;

/* Wild owns these engine operations. The current Query package borrows them
 * for this synchronous call; no callback or package pointer is retained. */
typedef struct OverworldReturnMoveWildOps {
    BOOL (*currentField)(OverworldWildSpawnState *, FieldSystem *);
    BOOL (*currentSpawn)(FieldSystem *, const OverworldWildSpawn *);
    BOOL (*mountActive)(void);
    BOOL (*querySurface)(FieldSystem *, int, int, OverworldWildSurfaceHit *);
    s32 (*groundBaseY)(FieldSystem *, LocalMapObject *, int, int);
    OverworldMotionDecision (*classifyLanding)(OverworldWildSpawnState *, int,
        FieldSystem *, u16, int, int, int, int);
    OverworldMotionDecision (*startTimed)(OverworldWildSpawnState *, FieldSystem *,
        int, LocalMapObject *, u8, u8, int, int,
        const OverworldWildBehaviorProfile *, BOOL, u8);
    void (*clearStaged)(OverworldWildSpawnState *, int);
    void (*initPolicyCall)(OverworldActorWalkPolicyCall *, int, u8);
    BOOL (*reduceWalk)(OverworldActorWalkPolicyCall *);
    u8 (*resolveWalkPause)(const OverworldWildBehaviorProfileData *);
    u8 (*directionFromDelta)(int, int);
    void (*clearCustomJump)(OverworldWildSpawnState *, int);
    BOOL (*executeWalk)(OverworldWildDirectionStepContext *, OverworldActorWalkPolicyCall *);
    void (*commitChain)(OverworldWildSpawnState *, int, OverworldWildBehaviorProfile *);
} OverworldReturnMoveWildOps;

typedef struct OverworldReturnMoveWildContext {
    OverworldWildSpawnState *state;
    FieldSystem *field;
    const OverworldReturnMoveWildOps *ops;
    int slot;
} OverworldReturnMoveWildContext;

typedef struct OverworldReturnMoveWildRequest {
    OverworldReturnMoveWildContext context;
    const OverworldWildBehaviorProfileData *lane;
    u16 duration;
    u16 targetSurfaceId;
    u8 kind, visibilityPolicy, arcHeightQ4, facing, spinSpeed, swayWidth;
    /* Private synchronous modifier; ordinary/forced callers keep zero. */
    __extension__ union { u8 reserved[2]; struct { u8 flags, unused; }; };
} OverworldReturnMoveWildRequest;

OverworldMotionDecision OverworldReturnMoveWild_Request(const OverworldReturnMoveWildRequest *);
BOOL OverworldReturnMoveWild_IsCurrent(const OverworldReturnMoveWildContext *);
void OverworldReturnMoveWild_TryStart(const OverworldReturnMoveWildContext *);
enum {
    OVERWORLD_RETURN_MOVE_BEFORE_WALK = 1,
    OVERWORLD_RETURN_MOVE_AFTER_WALK = 2,
    OVERWORLD_RETURN_MOVE_COMBAT_OWNED = 4,
    OVERWORLD_RETURN_MOVE_DESPAWN = 8,
    OVERWORLD_RETURN_MOVE_WALK_TERMINAL = 16,
    OVERWORLD_RETURN_MOVE_STOP_AFTER_COMMIT = 32,
    OVERWORLD_RETURN_MOVE_START = 64,
};
BOOL OverworldReturnMoveWild_Finish(const OverworldReturnMoveWildContext *,
    OverworldWildBehaviorProfile *, OverworldWildBehaviorPrimitives *, u8);
u8 OverworldReturnMoveWild_CombatWork(const OverworldReturnMoveWildContext *,
    OverworldMotionPlan *);
#if defined(__arm__)
_Static_assert(sizeof(OverworldReturnMoveWildOps) == 60, "return ops layout changed");
_Static_assert(sizeof(OverworldWildDirectionStepContext) == 28, "Walk step context layout changed");
_Static_assert(sizeof(OverworldReturnMoveWildContext) == 16, "return context layout changed");
_Static_assert(sizeof(OverworldReturnMoveWildRequest) == 32, "return request layout changed");
#endif
#endif
