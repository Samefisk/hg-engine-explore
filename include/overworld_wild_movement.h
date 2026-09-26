#ifndef OVERWORLD_WILD_MOVEMENT_H
#define OVERWORLD_WILD_MOVEMENT_H

#include "types.h"

struct FieldSystem;
struct LocalMapObject;
struct OverworldWildBehaviorProfileData;
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
/* Value 2 is reserved so Tired keeps its existing controller ABI value. */
#define OW_WILD_SPAWNER_SPOT_STATE_RESERVED 2
#define OW_WILD_SPAWNER_SPOT_STATE_TIRED 3
#define OVERWORLD_ACTOR_WALK_POLICY_VERSION 1

typedef struct OverworldWildWalkMomentumState {
    u8 direction;
    /* Below max: acceleration cadence. At max: completed cap-speed Walks
     * used to fade time variance; saturates at 255. Reset with momentum. */
    u8 tileCounter;
    u8 speed;
    u8 baseSpeed;
    u8 spotState;
    u8 skidRemaining;
    u8 turnDirection;
    u8 resumeSpeed;
} OverworldWildWalkMomentumState;

typedef enum OverworldActorWalkPolicyOperation {
    OVERWORLD_ACTOR_WALK_POLICY_RESET = 0,
    OVERWORLD_ACTOR_WALK_POLICY_INPUT,
    OVERWORLD_ACTOR_WALK_POLICY_START_RESULT,
    OVERWORLD_ACTOR_WALK_POLICY_COMMIT,
    OVERWORLD_ACTOR_WALK_POLICY_CHAIN_COMMIT,
    OVERWORLD_ACTOR_WALK_POLICY_INSPECT,
    OVERWORLD_ACTOR_WALK_POLICY_BIND_PROFILE,
    OVERWORLD_ACTOR_WALK_POLICY_SAMPLE_VARIANCE,
    OVERWORLD_ACTOR_WALK_POLICY_BUFFER_DIRECTION,
    OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING,
    OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_BEGIN,
    OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_ADVANCE,
    OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH,
    OVERWORLD_ACTOR_WALK_POLICY_CHAIN_PUT_PENDING = 13,
    OVERWORLD_ACTOR_WALK_POLICY_PUBLISH_EFFECT = 14,
    OVERWORLD_ACTOR_WALK_POLICY_SWAP_PROFILE = 15,
} OverworldActorWalkPolicyOperation;

typedef enum OverworldActorWalkPolicyDecision {
    OVERWORLD_ACTOR_WALK_POLICY_IGNORED = 0,
    OVERWORLD_ACTOR_WALK_POLICY_CONSUMED,
    OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP,
} OverworldActorWalkPolicyDecision;

typedef enum OverworldActorWalkPolicyStartResult {
    OVERWORLD_ACTOR_WALK_POLICY_START_NONE = 0,
    OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED,
    OVERWORLD_ACTOR_WALK_POLICY_START_BLOCKED,
} OverworldActorWalkPolicyStartResult;

#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_DEFER_STOP 0x01
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_SUPPRESS_TURN_SKID 0x02
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_WALK_ACCEPTED 0x04
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED 0x08
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_CRASH_ON_BLOCKED 0x10

#define OVERWORLD_ACTOR_WALK_STEP_VALIDATE 0x01
#define OVERWORLD_ACTOR_WALK_STEP_SKID 0x02
#define OVERWORLD_ACTOR_WALK_STEP_STOP_SKID 0x04
#define OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION 0x08
#define OVERWORLD_ACTOR_WALK_STEP_CONTINUATION 0x10
#define OVERWORLD_ACTOR_WALK_STEP_POST_SKID 0x20
#define OVERWORLD_ACTOR_WALK_STEP_RESET_ACCELERATION 0x40
#define OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH 0x80
#define OVERWORLD_ACTOR_WALK_STEP_PLANNED_STOP_SKID \
    OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH

#define OVERWORLD_ACTOR_WALK_POLICY_SKID_PATH_TILES_INDEX 1
#define OVERWORLD_ACTOR_WALK_POLICY_STOP_SKID_TILES_INDEX \
    OVERWORLD_ACTOR_WALK_POLICY_SKID_PATH_TILES_INDEX

/* pendingStep is a fixed ABI byte shared by both adapters. */
#define OVERWORLD_ACTOR_WALK_PENDING_NONE 0
#define OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL 1
#define OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED 2
#define OVERWORLD_ACTOR_WALK_PENDING_CHAIN 3

typedef struct OverworldActorPolicyView {
    OverworldWildWalkMomentumState walkMomentum;
    u32 behaviorFingerprint;
    u32 matchedLayerMask;
    u8 chainStepsRemaining;
    u8 chainPauseTicks;
    u8 chainPauseAction;
    u8 variancePhase;
    u8 bufferedDirection;
    u8 stopPending;
    u8 pendingStep;
    u8 pendingSkid;
    u8 streamState;
    u8 lastWalkTime;
    u16 pendingFirstPathAdvance;
    u16 pendingLastPathAdvance;
    u8 actorActive;
    u8 motionPhase;
} OverworldActorPolicyView;

typedef struct OverworldActorPolicyProfileBinding {
    u32 behaviorFingerprint;
    u32 matchedLayerMask;
} OverworldActorPolicyProfileBinding;

typedef struct OverworldActorPolicyProfileTransaction {
    OverworldActorPolicyProfileBinding next;
    OverworldActorPolicyProfileBinding prior;
} OverworldActorPolicyProfileTransaction;

typedef struct OverworldActorWalkPolicyCall {
    u16 version;
    u16 size;
    union {
        const struct OverworldWildBehaviorProfileData *lane;
        OverworldActorPolicyView *policyView;
        const OverworldActorPolicyProfileBinding *profileBinding;
        OverworldActorPolicyProfileTransaction *profileTransaction;
    };
    u8 actorSlot;
    u8 operation;
    u8 direction;
    u8 distance;
    u8 locomotion;
    u8 laneState;
    u8 flags;
    u8 startResult;
    u8 decision;
    u8 stepDirection;
    u8 facingDirection;
    u8 travelTime;
    u8 stepFlags;
    u8 effect;
    u8 chainAction;
    u8 chainTicks;
    u8 reserved[4];
} OverworldActorWalkPolicyCall;

typedef char OverworldActorWalkPolicyCallSizeMustRemain28Bytes[
    sizeof(OverworldActorWalkPolicyCall) == 28 ? 1 : -1];
typedef char OverworldActorPolicyViewSizeMustRemain32Bytes[
    sizeof(OverworldActorPolicyView) == 32 ? 1 : -1];
typedef char OverworldActorPolicyProfileBindingSizeMustRemain8Bytes[
    sizeof(OverworldActorPolicyProfileBinding) == 8 ? 1 : -1];
typedef char OverworldActorPolicyProfileTransactionSizeMustRemain16Bytes[
    sizeof(OverworldActorPolicyProfileTransaction) == 16 ? 1 : -1];
typedef BOOL (*OverworldActorWalkPolicyReduceFunc)(
    OverworldActorWalkPolicyCall *call);

typedef u8 (*OverworldWildMovementPolicyBuildLookPlanFunc)(u8 baseDirection);
typedef int (*OverworldWildMovementPolicyResolveLookFunc)(
    u8 lookPlan,
    u8 phase,
    u8 totalFrames,
    u8 remainingFrames);
typedef int (*OverworldWildMovementPolicyChooseWanderDirectionFunc)(
    const u8 *directions,
    int directionCount,
    u8 previousDirection,
    u8 chance);
#define OverworldWildCustomMovement_SetFieldSystem(fieldSystem) ((void)(fieldSystem))
void OverworldWildSpawns_ApplyFacePlayerFacing(
    struct OverworldWildSpawnState *state,
    int slot,
    u8 emotePlayHopSound);
int OverworldWildSpawns_MovementDirectionDeltaX(u8 direction);
int OverworldWildSpawns_MovementDirectionDeltaY(u8 direction);
#endif
