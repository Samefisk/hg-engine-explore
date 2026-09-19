#ifndef OVERWORLD_WALK_MODULE_H
#define OVERWORLD_WALK_MODULE_H

#include "types.h"

struct FIELD_PLAYER_AVATAR;
struct LocalMapObject;
struct OverworldActorPolicyState;
struct OverworldActorWalkPolicyCall;
struct OverworldMountRuntimeState;

#define OVERWORLD_WALK_DECELERATE_TIME_ADDR 0x023BF400
#define OVERWORLD_WALK_PROPOSE_STEP_ADDR 0x023BF45C
#define OVERWORLD_WALK_CLAMP_TIME_ADDR 0x023BF488
#define OVERWORLD_WALK_ACCELERATE_TIME_ADDR 0x023BF49E
#define OVERWORLD_WALK_SKID_TILES_ADDR 0x023BF4D6
#define OVERWORLD_WALK_SKID_TIME_ADDR 0x023BF4F0
#define OVERWORLD_WALK_STOMP_APPLIES_ADDR 0x023BF504
#define OVERWORLD_WALK_DIRECTION_FROM_KEYS_ADDR 0x023BF534
#define OVERWORLD_WALK_DIRECTION_KEY_ADDR 0x023BF586
#define OVERWORLD_WALK_DELTA_X_ADDR 0x023BF59C
#define OVERWORLD_WALK_DELTA_Y_ADDR 0x023BF5BE
#define OVERWORLD_WALK_IS_FORTY_FIVE_DEGREE_TURN_ADDR 0x023BF5E2
#define OVERWORLD_WALK_DIRECTION_FROM_DELTA_ADDR 0x023BF68C
#define OVERWORLD_WALK_STRICT_DIAGONAL_ALLOWED_ADDR 0x023BF6CE
#define OVERWORLD_WALK_DIAGONAL_FACING_ADDR 0x023BF74E
#define OVERWORLD_WALK_RESOLVE_MOUNTED_DIAGONAL_ADDR 0x023BF780
#define OVERWORLD_WALK_START_MOUNTED_FLAT_ADDR 0x023BF840
#define OVERWORLD_WALK_FILTER_MOUNTED_INPUT_ADDR 0x023BF9A0
#define OVERWORLD_WALK_MARK_PLANNED_STOP_SKID_ADDR 0x023BFF14

u8 OverworldWalk_DecelerateTime(
    u8 time,
    u8 baseTime,
    u8 accelerationStep);
void OverworldWalk_ProposeStep(
    struct OverworldActorPolicyState *policy,
    struct OverworldActorWalkPolicyCall *call,
    u8 direction,
    u8 facing,
    u8 time,
    u8 stepFlags,
    u8 skidTiles);
u8 OverworldWalk_ClampTime(u8 time);
u8 OverworldWalk_AccelerateTime(
    u8 time,
    u8 fastestTime,
    u8 accelerationStep);
u8 OverworldWalk_SkidTiles(u8 time);
u8 OverworldWalk_SkidTime(u8 time);
BOOL OverworldWalk_StompApplies(u8 time, u8 threshold);
u8 OverworldWalk_DirectionFromKeys(u32 keys);
u32 OverworldWalk_DirectionKey(u8 direction);
int OverworldWalk_DeltaX(u8 direction);
int OverworldWalk_DeltaY(u8 direction);
BOOL OverworldWalk_IsFortyFiveDegreeTurn(
    u8 fromDirection,
    u8 toDirection);
u8 OverworldWalk_DirectionFromDelta(int dx, int dy);
BOOL OverworldWalk_StrictDiagonalAllowed(
    struct OverworldMountRuntimeState *state,
    struct FIELD_PLAYER_AVATAR *avatar,
    u8 direction);
u8 OverworldWalk_DiagonalFacing(
    struct LocalMapObject *player,
    u8 direction,
    u32 newKeys);
/* Returns Motion candidate rejection flags for a blocked strict diagonal.
 * Nonzero consumes this request; it must not be reduced as NONE/stop input.
 * Zero preserves the normal policy path and cardinal-only key projection. */
u16 OverworldWalk_ResolveMountedDiagonal(
    struct OverworldMountRuntimeState *state,
    struct FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys,
    u32 *heldKeys);
BOOL OverworldWalk_StartMountedFlat(
    struct OverworldMountRuntimeState *state,
    struct FIELD_PLAYER_AVATAR *avatar,
    struct LocalMapObject *follower,
    u8 direction,
    u8 facingDirection,
    BOOL advanceFirstFrame,
    BOOL (*beginSharedMotion)(BOOL advanceFirstFrame));
void OverworldWalk_FilterMountedInput(
    struct OverworldMountRuntimeState *state,
    struct FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys,
    u32 *heldKeys);
void OverworldWalk_MarkPlannedStopSkid(
    const struct OverworldActorPolicyState *policy,
    struct OverworldActorWalkPolicyCall *call);

#endif
