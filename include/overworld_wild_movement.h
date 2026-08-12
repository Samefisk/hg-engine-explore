#ifndef OVERWORLD_WILD_MOVEMENT_H
#define OVERWORLD_WILD_MOVEMENT_H

#include "types.h"

struct FieldSystem;

#define OW_WILD_MOVE_CUSTOM_AI 47
#define OW_WILD_MOVE_STOCK_IDLE 0
#define OW_WILD_MOVE_STOCK_WANDER 3

#define OW_WILD_MOVEMENT_PARAM_COOLDOWN 0
#define OW_WILD_MOVEMENT_PARAM_BEHAVIOR 1
#define OW_WILD_MOVEMENT_PARAM_RENDER 2

#define OW_WILD_MOVEMENT_BEHAVIOR_CHASE_PLAYER 1
#define OW_WILD_MOVEMENT_BEHAVIOR_FLEE_PLAYER 2

#define OW_WILD_WALK_DIRECTION_NONE 0xFF
#define OW_WILD_WALK_SPEED_MIN 1
#define OW_WILD_WALK_SPEED_MAX 4

typedef struct OverworldWildWalkMomentumState {
    u8 direction;
    u8 tileCounter;
    u8 speed;
    u8 baseSpeed;
    u8 spotState;
    u8 skidRemaining;
    u8 turnDirection;
    u8 resumeSpeed;
} OverworldWildWalkMomentumState;

typedef BOOL (*OverworldWildWalkStartStepCallback)(
    void *context,
    u8 direction,
    u8 speed,
    u8 facingDirection,
    BOOL validateStep,
    BOOL skidStep);
typedef void (*OverworldWildWalkEffectCallback)(
    void *context,
    u8 direction,
    BOOL playDirt);

void LONG_CALL OverworldWildCustomMovement_SetFieldSystem(struct FieldSystem *fieldSystem);

#endif
