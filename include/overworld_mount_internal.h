#ifndef OVERWORLD_MOUNT_INTERNAL_H
#define OVERWORLD_MOUNT_INTERNAL_H

#include "overworld_mount.h"

#define OVERWORLD_MOUNT_RUNTIME_STATE_ADDR 0x023BC744

#define OVERWORLD_MOUNT_FIELD_INPUT_END_MOVEMENT (1u << 1)
#define OVERWORLD_MOUNT_FIELD_INPUT_SIGN (1u << 5)
#define OVERWORLD_MOUNT_FIELD_INPUT_MAP_TRANSITION (1u << 6)
#define OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT (1u << 7)
#define OVERWORLD_MOUNT_WALK_END_NONE 0
#define OVERWORLD_MOUNT_WALK_END_PENDING 1
#define OVERWORLD_MOUNT_WALK_END_CONTINUATION_READY 2
#define OVERWORLD_MOUNT_WALK_END_STOP 3
typedef struct OverworldMountFieldInput {
    u16 flags;
    u16 unk2;
    u8 playerDirection;
    s8 transitionDirection;
    u16 newKeys;
    u16 heldKeys;
    u16 unkA;
} OverworldMountFieldInput;



/* Stable Thumb entry in resident overlay 129. The package verifier checks
 * this address against the mount bridge literal on every ROM build. */
#define OVERWORLD_WILD_PLAYER_STEP_HANDLER_ADDR 0x023D9B69

typedef struct OverworldMountRuntimeState {
    FieldSystem *fieldSystem;
    const OverworldWildSurfaceCatalog *surfaceCatalog;
    OverworldMountSnapshot snapshot;
    u32 playerBaseFaceY;
    u32 playerBaseUnk88Y;
    u32 lastAppliedPlayerFaceY;
    u32 lastAppliedPlayerUnk88Y;
    /* Current physical D-pad state, sampled by the mount frame task. It stops
     * a completed step from reusing an old proposal after input is released. */
    u8 directionInputHeld;
    u8 savedPlayerShadowSuppressed;
    u8 presentationAttached;
    /* One normal player-step receipt. It can wait for streaming, suppress
     * continuation when a step event consumes control, or start one next
     * held Walk after the terminal actor commit. */
    u8 walkEndState;
    u16 savedPlayerGfxId;
    /* Actor Motion returns this reservation ID only after Begin accepts. The
     * mounted adapter carries it on every later engine-boundary receipt. */
    u16 motionIdentity;
    /* One stock step signal retained while terminal stream acks complete. */
    u8 pendingFieldStep;
    /* The first byte keeps the nominal Walk time across the mounted engine
     * call. The second byte remains reserved for the fixed layout. */
    u8 reservedPolicyProfile[2];
    /* Fixed adapter-boundary storage. These bytes replaced retired mount-
     * local policy state without changing the fixed runtime layout. */
    u8 reservedPolicyState[9];
    u8 motionDirection;
    u8 motionArcHeightQ4;
    u8 motionFlicker;
    u16 motionFrameCount;
    u16 motionElapsed;
    u16 motionCooldown;
    /* These bytes also keep the coordinate pairs word-aligned. The resident
     * field task uses them to preserve one Select edge while frame services
     * are temporarily stopped. */
    u8 bufferedTogglePending;
    u8 bufferedToggleDown;
    s16 motionStartX;
    s16 motionStartY;
    s16 motionTargetX;
    s16 motionTargetY;
    s32 motionStartBaseY;
    s32 motionTargetBaseY;
    VecFx32 motionStreamAnchor;
    u8 motionStreamPreparing;
    u8 savedFollowerShadowSuppressed;
    u8 motionLandingPauseStarted;
    u8 preserveTransitionPrepared;
} OverworldMountRuntimeState;

#define OVERWORLD_MOUNT_BOUNDARY_FLAGS_INDEX 0
#define OVERWORLD_MOUNT_BOUNDARY_APPLIED_LO_INDEX 1
#define OVERWORLD_MOUNT_BOUNDARY_APPLIED_HI_INDEX 2
#define OVERWORLD_MOUNT_BOUNDARY_MOTION_INDEX 3
#define OVERWORLD_MOUNT_BOUNDARY_PHASE_INDEX 4
#define OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX 0
#define OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX 5
#define OVERWORLD_MOUNT_WALK_STEP_DIRECTION_INDEX 6
#define OVERWORLD_MOUNT_WALK_FACING_DIRECTION_INDEX 7
#define OVERWORLD_MOUNT_WALK_TRAVEL_TIME_INDEX 8

#define OVERWORLD_MOUNT_BOUNDARY_HAS_APPLIED_PATH (1u << 0)
#define OVERWORLD_MOUNT_BOUNDARY_FINAL_WRITES_DONE (1u << 1)
#define OVERWORLD_MOUNT_BOUNDARY_ENGINE_END_SEEN (1u << 2)
#define OVERWORLD_MOUNT_BOUNDARY_FINALIZE_PENDING (1u << 3)

typedef char OverworldMountMotionStartXOffsetMustRemain98[
    offsetof(OverworldMountRuntimeState, motionStartX) == 0x98 ? 1 : -1];
typedef char OverworldMountMotionTargetXOffsetMustRemain9C[
    offsetof(OverworldMountRuntimeState, motionTargetX) == 0x9C ? 1 : -1];
typedef char OverworldMountMotionStartBaseYOffsetMustRemainA0[
    offsetof(OverworldMountRuntimeState, motionStartBaseY) == 0xA0 ? 1 : -1];
typedef char OverworldMountMotionTargetBaseYOffsetMustRemainA4[
    offsetof(OverworldMountRuntimeState, motionTargetBaseY) == 0xA4 ? 1 : -1];
typedef char OverworldMountTogglePendingOffsetMustRemain96[
    offsetof(OverworldMountRuntimeState, bufferedTogglePending) == 0x96
        ? 1 : -1];
typedef char OverworldMountRuntimeAddressMustReachToggleLatch[
    OVERWORLD_MOUNT_RUNTIME_STATE_ADDR
            + offsetof(OverworldMountRuntimeState, bufferedTogglePending)
        == OVERWORLD_MOUNT_TOGGLE_LATCH_ADDR
        ? 1 : -1];
typedef char OverworldMountBoundaryStorageMustRemain9[
    sizeof(((OverworldMountRuntimeState *)0)->reservedPolicyState) == 9
        ? 1 : -1];

/* Fixed resident helper in overlay 153. */
void OverworldWalkMount_RebaseMotionTarget(
    OverworldMountRuntimeState *state);

/* Private physical code host in field overlay 131, loaded with field input.
 * The mount retains state and terminal commit ownership. */
#define OVERWORLD_MOUNT_FIELD_INPUT_HOST_ADDR 0x023CCE99
typedef int (*OverworldMountFieldInputHost)(
    OverworldMountFieldInput *, FieldSystem *, OverworldMountRuntimeState *, BOOL);
#define OVERWORLD_MOUNT_FIELD_INPUT_HOST \
    ((OverworldMountFieldInputHost)OVERWORLD_MOUNT_FIELD_INPUT_HOST_ADDR)

#endif // OVERWORLD_MOUNT_INTERNAL_H
