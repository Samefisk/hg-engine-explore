#ifndef OVERWORLD_WILD_MOVEMENT_H
#define OVERWORLD_WILD_MOVEMENT_H

#include "types.h"

struct FieldSystem;
struct LocalMapObject;
struct OverworldWildSpawnState;

#define OW_WILD_MOVE_CUSTOM_AI 47
#define OW_WILD_MOVE_STOCK_IDLE 0
#define OW_WILD_MOVE_STOCK_WANDER 3

#define OW_WILD_MOVEMENT_PARAM_COOLDOWN 0
#define OW_WILD_MOVEMENT_PARAM_BEHAVIOR 1
#define OW_WILD_MOVEMENT_PARAM_RENDER 2

#define OW_WILD_MOVEMENT_BEHAVIOR_CHASE_PLAYER 1
#define OW_WILD_MOVEMENT_BEHAVIOR_FLEE_PLAYER 2

#define OW_WILD_WALK_DIRECTION_NONE 0xFF
#define OW_WILD_WALK_DIRECTION_NO_TURN_SKID_FLAG 0x80
#define OW_WILD_WALK_TRAVEL_TIME_MIN 1
#define OW_WILD_WALK_TRAVEL_TIME_MAX 32
#define OW_WILD_WALK_SPEED_MIN OW_WILD_WALK_TRAVEL_TIME_MIN
#define OW_WILD_WALK_SPEED_MAX OW_WILD_WALK_TRAVEL_TIME_MAX
#define OW_WILD_WALK_TURN_SKIDS_DISABLED 0
#define OW_WILD_SPAWNER_SPOT_STATE_CHILL 0
#define OW_WILD_SPAWNER_SPOT_STATE_EMOTING 1
#define OW_WILD_SPAWNER_SPOT_STATE_ACTIVE 2
#define OW_WILD_SPAWNER_SPOT_STATE_TIRED 3

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
#define OverworldWildCustomMovement_SetFieldSystem(fieldSystem) ((void)(fieldSystem))
void OverworldWildSpawns_ApplyFacePlayerFacing(
    struct OverworldWildSpawnState *state,
    int slot,
    u8 emotePlayHopSound);
int OverworldWildSpawns_MovementDirectionDeltaX(u8 direction);
int OverworldWildSpawns_MovementDirectionDeltaY(u8 direction);
#endif
