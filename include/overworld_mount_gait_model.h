#ifndef OVERWORLD_MOUNT_GAIT_MODEL_H
#define OVERWORLD_MOUNT_GAIT_MODEL_H

#ifdef OVERWORLD_MOUNT_GAIT_HOST
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int16_t s16;
typedef int32_t s32;
#else
#include "types.h"
#endif

/* Presentation values only. One pixel is 4096 world-vector units. */
typedef struct OverworldMountGaitPose {
    s32 x, z;
    s32 velocityX, velocityZ;
    s16 bodyY, riderY, leanX, leanZ;
    u16 phase;
    u8 walking;
    u8 reserved;
} OverworldMountGaitPose;

typedef struct OverworldMountGaitState {
    OverworldMountGaitPose previous, pose;
    u32 stamp, session, owner;
    u8 initialized;
    u8 reserved[3];
} OverworldMountGaitState;

typedef struct OverworldMountGaitInput {
    s32 x, z;
    u32 stamp, session, owner;
    /* 0: idle/settle, 1: Walk, 2: another motion (no gait). */
    u8 mode;
    /* Four two-bit profile fields: bounce, stride, settle, lean. */
    u8 options;
} OverworldMountGaitInput;

void OverworldMountGait_Sample(
    OverworldMountGaitState *state, const OverworldMountGaitInput *input);

#endif
