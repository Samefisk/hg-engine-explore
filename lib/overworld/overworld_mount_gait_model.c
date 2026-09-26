#include "../../include/overworld_mount_gait_model.h"

#ifdef OVERWORLD_MOUNT_GAIT_HOST
#define GAIT_CODE
#else
#define GAIT_CODE __attribute__((section(".overworld_mount_gait_code"), optimize("Os")))
#endif

static s32 GAIT_CODE GaitAbs(s32 value)
{
    return value < 0 ? -value : value;
}

static s32 GAIT_CODE GaitClamp(s32 value, s32 limit)
{
    return value < -limit ? -limit : value > limit ? limit : value;
}

static s32 GAIT_CODE GaitFollow(s32 from, s32 target, u32 divisor)
{
    s32 delta = target - from;
    if (GaitAbs(delta) < 16) {
        return target;
    }
    return from + (delta < 0
        ? -(s32)((u32)-delta / divisor) : (s32)((u32)delta / divisor));
}

void GAIT_CODE OverworldMountGait_Sample(
    OverworldMountGaitState *state, const OverworldMountGaitInput *input)
{
    OverworldMountGaitPose *pose = &state->pose;
    s32 dx, dz, distance, target, limit;
    u32 phaseStep, phase;
    u8 bounce = input->options & 3;
    u8 stride = ((input->options >> 2) & 3) + 1;
    u8 settle = (input->options >> 4) & 3;
    u8 lean = input->options >> 6;

    if (!state->initialized || state->owner != input->owner
        || state->session != input->session
        || GaitAbs(input->x - pose->x) > 131072
        || GaitAbs(input->z - pose->z) > 131072
        || input->mode == 2) {
        *state = (OverworldMountGaitState){0};
        pose->x = input->x;
        pose->z = input->z;
        state->previous = *pose;
        state->stamp = input->stamp;
        state->session = input->session;
        state->owner = input->owner;
        state->initialized = 1;
    }
    if (input->mode == 2) {
        return;
    }
    if (state->stamp != input->stamp) {
        state->previous = *pose;
        state->stamp = input->stamp;
    }
    /* A tile can publish both its end and its successor in one update.
     * Recompute from the previous update; duplicate callbacks never advance
     * phase or damping twice, and the last pose includes the full distance. */
    *pose = state->previous;
    dx = input->x - pose->x;
    dz = input->z - pose->z;
    pose->x = input->x;
    pose->z = input->z;
    if (input->mode != 1 && !pose->walking) {
        dx = dz = 0;
    }
    pose->walking = input->mode == 1;
    distance = GaitAbs(dx) > GaitAbs(dz) ? GaitAbs(dx) : GaitAbs(dz);
    /* Tile distance drives the gait, including diagonal travel. At extreme
     * speeds cap its visual frequency at one cycle per eight updates, so a
     * one-frame Walk cannot alias the bounce into a flashing sprite. */
    phaseStep = (u32)distance / stride;
    if (phaseStep > 8192) {
        phaseStep = 8192;
    }
    pose->phase += (u16)phaseStep;
    phase = pose->phase >> 8;
    target = distance == 0 ? 0 : (s32)(phase * (256 - phase) * bounce / 4);
    pose->bodyY += GaitClamp(target - pose->bodyY, 1024);
    pose->riderY = GaitFollow(pose->riderY, pose->bodyY, settle + 1);
    /* Keep the rider within 1/8 pixel per settling level of its seat. */
    pose->riderY = pose->bodyY
        + GaitClamp(pose->riderY - pose->bodyY, settle * 512);
    limit = lean * 4096;
    target = GaitClamp(-(dx - pose->velocityX) / 8, limit);
    pose->leanX += GaitClamp(target - pose->leanX, 512);
    target = GaitClamp(-(dz - pose->velocityZ) / 8, limit);
    pose->leanZ += GaitClamp(target - pose->leanZ, 512);
    pose->velocityX = GaitFollow(pose->velocityX, dx, 2);
    pose->velocityZ = GaitFollow(pose->velocityZ, dz, 2);
}
