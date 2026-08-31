#ifndef OVERWORLD_MOUNT_INTERNAL_H
#define OVERWORLD_MOUNT_INTERNAL_H

#include "overworld_mount.h"

/* Stable Thumb entry in resident overlay 129. The package verifier checks
 * this address against the mount bridge literal on every ROM build. */
#define OVERWORLD_WILD_PLAYER_STEP_HANDLER_ADDR 0x023D9B79

typedef struct OverworldMountRuntimeState {
    FieldSystem *fieldSystem;
    const OverworldWildSurfaceCatalog *surfaceCatalog;
    OverworldMountSnapshot snapshot;
    u32 playerBaseFaceY;
    u32 playerBaseUnk88Y;
    u32 lastAppliedPlayerFaceY;
    u32 lastAppliedPlayerUnk88Y;
    u8 savedFollowerCooldown;
    u8 savedPlayerShadowSuppressed;
    u8 presentationAttached;
    u8 previousToggleDown;
    u16 savedPlayerGfxId;
    u8 baseSpeed;
    u8 maxSpeed;
    u8 speed;
    u8 tilesToAccelerate;
    u8 walkOptions;
    u8 direction;
    u8 tileCounter;
    u8 skidRemaining;
    u8 turnDirection;
    u8 resumeSpeed;
    u8 pendingStep;
    u8 pendingSkid;
    u8 bufferedDirection;
    u8 stopPending;
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
    /* The prior Walk time marks one derived acceleration transition tile. */
    u8 walkTransitionTime;
} OverworldMountRuntimeState;

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

/* Fixed resident helper in overlay 153. */
void OverworldWalkMount_RebaseMotionTarget(
    OverworldMountRuntimeState *state);

#endif // OVERWORLD_MOUNT_INTERNAL_H
