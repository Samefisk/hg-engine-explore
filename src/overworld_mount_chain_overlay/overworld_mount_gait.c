#include "../../include/overworld_mount_internal.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_mount_gait_model.h"

__asm__(
    ".thumb\n"
    ".global __aeabi_uidiv\n.thumb_func\n.thumb_set __aeabi_uidiv, 0x023DEE4C\n"
    ".global __aeabi_uidivmod\n.thumb_func\n.thumb_set __aeabi_uidivmod, 0x023DEE4C\n"
    ".global memset\n.thumb_func\n.thumb_set memset, 0x023DEEA2\n");

#include "../../lib/overworld/overworld_mount_gait_model.c"

/* Boot-resident, explicitly loaded data; no heap or field-overlay BSS. */
OverworldMountGaitState sOverworldMountGaitState
    __attribute__((section(".overworld_mount_gait_state"), used)) = {0};
typedef char OverworldMountGaitStateFitsReserve[
    sizeof(OverworldMountGaitState) <= 128 ? 1 : -1];

void __attribute__((section(".overworld_mount_gait_entry"), used, noinline,
    optimize("Os"))) OverworldMountGait_Apply(
    OverworldMountRuntimeState *mount, LocalMapObject *player,
    LocalMapObject *follower)
{
    OverworldMountGaitInput input;
    const OverworldMountGaitPose *pose;

    input.x = (s32)player->posVec[0];
    input.z = (s32)player->posVec[2];
    /* Stock gSystem.vblankCounter (+0x2C) changes between main task queues,
     * never inside one queue. See pokeheartgold/src/main.c and system.h.
     * Only equality matters: a slow main loop can span multiple VBlanks. */
    input.stamp = *(volatile u32 *)(0x021D110C + 0x2C);
    input.session = mount->snapshot.sessionGeneration;
    input.owner = (u32)player;
    input.mode = mount->snapshot.motionMode == OVERWORLD_MOUNT_MOTION_WALK
        ? 1 : mount->snapshot.motionMode == OVERWORLD_MOUNT_MOTION_NONE ? 0 : 2;
    input.options = mount->snapshot.profile.mountBounce;
    OverworldMountGait_Sample(&sOverworldMountGaitState, &input);
    pose = &sOverworldMountGaitState.pose;
    follower->unk88[1] += pose->bodyY;
    player->unk88[1] += pose->riderY;
    player->faceVec[0] += pose->leanX;
    player->faceVec[2] += pose->leanZ;
}
