#include "../../include/map_teleport.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_walk_direction_policy.h"
#include "../../include/overworld_walk_module.h"
#include "../../include/overworld_wild_spawns_internal.h"

__asm__(
    ".thumb\n"
    ".thumb_func\n.thumb_set OverworldWalk_DeltaX, 0x023BF59C\n"
    ".thumb_func\n.thumb_set OverworldWalk_DeltaY, 0x023BF5BE\n"
    ".thumb_func\n.thumb_set OverworldWalk_EaseMountedWalk, 0x01FF8620\n"
    ".thumb_func\n.thumb_set OverworldWalk_RefreshMountedGraphics, 0x01FF8700\n"
    ".global memcpy\n.thumb_func\n.thumb_set memcpy, 0x023DEEBE\n");

#define OVERWORLD_FIELD_MOUNT_RIDER_HEIGHT_FX32 0x8000
#define OVERWORLD_FIELD_MOUNT_RIDER_SOUTH_BACK_FX32 0xA000
#define OVERWORLD_FIELD_MOUNT_IDLE_COOLDOWN 0xFF

BOOL __attribute__((section(".overworld_mount_presentation_entry"), used,
    noinline, optimize("Os"))) OverworldFieldService_SyncMountedPresentation(
    OverworldFieldMountPresentationCall *call)
{
    OverworldMountRuntimeState *mount;
    LocalMapObject *follower;
    LocalMapObject *player;
    s32 mountedArc;
    s32 riderDeltaY;

    mount = call->mount;
    player = call->player;
    follower = call->follower;
    if (mount->snapshot.motionMode == OVERWORLD_MOUNT_MOTION_NONE) {
        if (player->faceVec[1] != mount->lastAppliedPlayerFaceY) {
            mount->playerBaseFaceY = player->faceVec[1];
        }
        if (player->unk88[1] != mount->lastAppliedPlayerUnk88Y) {
            mount->playerBaseUnk88Y = player->unk88[1];
        }
    }
    mountedArc = mount->snapshot.motionMode == OVERWORLD_MOUNT_MOTION_HOP
        ? (s32)mount->lastAppliedPlayerFaceY
            - (s32)mount->playerBaseFaceY
            - OVERWORLD_FIELD_MOUNT_RIDER_HEIGHT_FX32
        : 0;
    OverworldWalk_EaseMountedWalk(mount, player);
    memcpy(follower->posVec, player->posVec, sizeof(follower->posVec));
    memcpy(&follower->xPrev, &player->xPrev, 6 * sizeof(int));
    follower->flags &= ~MAPOBJECTFLAG_UNK7;
    follower->faceVec[0] = 0;
    follower->faceVec[1] = (u32)(mountedArc + (s32)mount->playerBaseFaceY);
    follower->faceVec[2] = 0;
    follower->unk88[0] = 0;
    follower->unk88[1] = mount->playerBaseUnk88Y;
    follower->unk88[2] = 0;
    /* Mounted motion uses the shared face/height offsets, never the old
     * Follower command's native jump offset. */
    follower->unk94[1] = 0;
    follower->flags |= MAPOBJECTFLAG_UNK18 | MAPOBJECTFLAG_UNK31;
    if (mount->snapshot.motionMode != OVERWORLD_MOUNT_MOTION_TELEPORT) {
        follower->flags &= ~BIT_VANISH;
    }
    player->faceVec[1] = follower->faceVec[1]
        + OVERWORLD_FIELD_MOUNT_RIDER_HEIGHT_FX32;
    player->unk88[1] = follower->unk88[1];
    if (mount->snapshot.motionMode == OVERWORLD_MOUNT_MOTION_HOP) {
        player->unk94[1] = 0;
    }
    player->faceVec[0] = (u32)(-
        OverworldWalk_DeltaX(player->curFacing) << 15);
    riderDeltaY = OverworldWalk_DeltaY(player->curFacing);
    /* Keep the south rider near the usual half-tile seat. A small extra Z
     * offset puts the mount in front without the full-tile visual gap. */
    player->faceVec[2] = (u32)(-riderDeltaY *
        (player->curFacing == OVERWORLD_WALK_DIRECTION_SOUTH
             ? OVERWORLD_FIELD_MOUNT_RIDER_SOUTH_BACK_FX32
             : OVERWORLD_FIELD_MOUNT_RIDER_HEIGHT_FX32));
    /* Stock graphics tasks ran before this mounted position update. Publish
     * both poses now, including the terminal Walk frame. Crash shake adds a
     * later offset and republishes its final pose in the mount task. */
    OverworldMountGait_Apply(mount, player, follower);
    OverworldWalk_RefreshMountedGraphics(player, follower);
    mount->lastAppliedPlayerFaceY = player->faceVec[1];
    mount->lastAppliedPlayerUnk88Y = player->unk88[1];
    player->flags |= MAPOBJECTFLAG_UNK20;
    call->wild->movementCooldowns[OW_WILD_FOLLOWER_SLOT] =
        OVERWORLD_FIELD_MOUNT_IDLE_COOLDOWN;
    call->wild->movementCrashShakeTimers[OW_WILD_FOLLOWER_SLOT] = 0;
    return TRUE;
}
