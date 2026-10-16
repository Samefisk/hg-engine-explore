#include "../../include/overworld_mount_internal.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_mount_gait_model.h"
#include "../../include/overworld_walk_module.h"
#include "../../include/constants/buttons.h"

/* These two private Walk helpers have checked fixed section starts in
 * overlay 153. The public resolver entry stays at 0x023BF780. */
extern u16 Walk_DiagonalRejection(
    OverworldMountRuntimeState *, FIELD_PLAYER_AVATAR *, u8);
extern u16 Walk_RejectDiagonalCandidate(
    OverworldMountRuntimeState *, FIELD_PLAYER_AVATAR *, u8, u16);
__asm__(
    ".thumb\n"
    ".thumb_func\n.thumb_set Walk_DiagonalRejection, 0x023BF6D8\n"
    ".thumb_func\n.thumb_set Walk_RejectDiagonalCandidate, 0x023BFE50\n"
    ".thumb_func\n.thumb_set OverworldWalk_DirectionFromKeys, 0x023BF534\n"
    ".thumb_func\n.thumb_set OverworldWalk_DiagonalFacing, 0x023BF74E\n"
    ".thumb_func\n.thumb_set OverworldWalk_DirectionKey, 0x023BF586\n");

u16 __attribute__((noinline, used, optimize("Os"),
    section(".overworld_mount_diagonal_resolver")))
OverworldMount_ResolveMountedDiagonalBody(
    OverworldMountRuntimeState *state, FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys, u32 *heldKeys)
{
    u8 direction = OverworldWalk_DirectionFromKeys(*newKeys | *heldKeys);
    u8 vertical;
    u8 horizontal;
    u8 first;
    u16 rejectionFlags;
    int (*collision)(FIELD_PLAYER_AVATAR *, LocalMapObject *, int) =
        (int (*)(FIELD_PLAYER_AVATAR *, LocalMapObject *, int))0x0205DA35;

    if (direction < 4 || direction > 7) {
        return 0;
    }
    if (OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
            state->snapshot.profile.hopAllowNonCardinal)) {
        rejectionFlags = Walk_DiagonalRejection(state, avatar, direction);
        if (rejectionFlags != 0) {
            (void)OVERWORLD_MOUNT_PLAYER_CONTACT_ENTRY(
                avatar, direction,
                OVERWORLD_MOUNT_CONTACT_DIAGONAL_REJECT, state);
            return Walk_RejectDiagonalCandidate(
                state, avatar, direction, rejectionFlags);
        }
        return 0;
    }
    if (!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(
            state->snapshot.profile.hopAllowNonCardinal)) {
        *newKeys &= ~PAD_PLUS_KEY_MASK;
        *heldKeys &= ~PAD_PLUS_KEY_MASK;
        return 0;
    }
    vertical = direction >= 6 ? 1 : 0;
    horizontal = (direction & 1u) ? 3 : 2;
    first = avatar->mapObject->curFacing == vertical
            || avatar->mapObject->curFacing == horizontal
        ? (u8)avatar->mapObject->curFacing
        : OverworldWalk_DiagonalFacing(avatar->mapObject, direction, *newKeys);
    if (collision(avatar, avatar->mapObject, first) != 0) {
        first = first == vertical ? horizontal : vertical;
        if (collision(avatar, avatar->mapObject, first) != 0) {
            first = 0xFF;
        }
    }
    *newKeys = (*newKeys & ~PAD_PLUS_KEY_MASK)
        | OverworldWalk_DirectionKey(first);
    *heldKeys = (*heldKeys & ~PAD_PLUS_KEY_MASK)
        | OverworldWalk_DirectionKey(first);
    return 0;
}

BOOL __attribute__((noinline, used, optimize("Os"),
    section(".overworld_mount_strict_diagonal_allowed_body")))
OverworldMount_StrictDiagonalAllowedBody(
    OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar, u8 direction)
{
    return Walk_DiagonalRejection(state, avatar, direction) == 0;
}

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
