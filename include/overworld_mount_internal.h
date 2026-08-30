#ifndef OVERWORLD_MOUNT_INTERNAL_H
#define OVERWORLD_MOUNT_INTERNAL_H

#include "overworld_mount.h"

/* Stable Thumb entry in resident overlay 129. The package verifier checks
 * this address against the mount bridge literal on every ROM build. */
#define OVERWORLD_WILD_PLAYER_STEP_HANDLER_ADDR 0x023D9B65

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

#endif // OVERWORLD_MOUNT_INTERNAL_H
