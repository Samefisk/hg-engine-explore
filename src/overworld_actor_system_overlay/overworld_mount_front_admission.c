#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_mount_action_adapter.h"
#include "../../include/overworld_mount_jump.h"
#include "../../include/overworld_wild_occupancy.h"
#include "../../include/map_events_internal.h"

/* Stock GetMetatileBehaviorAt is within direct Thumb BL range here. */
extern u8 OverworldMountFront_Behavior(FieldSystem *fieldSystem, int x, int y);
__asm__(
    ".thumb\n"
    ".thumb_func\n.thumb_set OverworldWildOccupancy_Query, 0x023C0184\n"
    ".thumb_func\n.thumb_set OverworldMountFront_Behavior, 0x02054918\n");

/* Mounted Walk uses the existing two-tile forward Hop for a ledge. The ledge
 * rule is the ordinary Wild downhill/Both axis rule. A blocked tile is never
 * crossed automatically: the rider jumps it with B. This leaf does not own
 * input, motion, or momentum. It admits only a cardinal Walk lane whose held
 * direction agrees with its moving or locked heading. The shared Hop planner
 * still owns landing surface, occupancy, and arc clearance. Keep every fixed
 * actor/public entry and the native Slam rise. */
BOOL __attribute__((noinline, used, optimize("Os"),
    section(".overworld_mount_front_admission")))
OverworldMount_CanCrossFront(
    OverworldMountRuntimeState *state, LocalMapObject *player,
    const OverworldActorPolicyView *policy, u8 direction)
{
    const OverworldWildBehaviorProfileData *lane = &state->snapshot.profile;
    int frontX = player->xCurr + (direction == 2 ? -1 : direction == 3);
    int frontY = player->yCurr + (direction == 0 ? -1 : direction == 1);
    u32 ledge;

    if (lane->jumpLevel == 0 || direction > 3 || (frontX | frontY) < 0
        || lane->chillAction != OW_WILD_BEHAVIOR_LOCOMOTION_WALK
        || (((lane->walkOptions
                & OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION) != 0
                || policy->walkMomentum.speed != 0)
            && policy->walkMomentum.direction <= 3
            && policy->walkMomentum.direction != direction)) {
        return FALSE;
    }
    ledge = OverworldMountFront_Behavior(state->fieldSystem, frontX, frontY) - 56;
    if (ledge > 3
        || (ledge ^ (direction ^ (2 | (direction >> 1))))
            > (lane->jumpLevel >= 2)) {
        return FALSE;
    }
    /* A ledge does not grant permission to jump over an object on it. */
    return !OverworldWildOccupancy_Query(state->fieldSystem, player, NULL,
        frontX, frontY, 0, OVERWORLD_WILD_OCCUPANCY_NONPLAYER);
}

/* B pressed while standing still: a cosmetic Hop in place, no movement. */
void __attribute__((noinline, used, optimize("Os"),
        section(".overworld_mount_front_admission")))
OverworldMountJump_HopInPlace(OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar)
{
    OverworldMountActionCall call;
    OverworldMotionPlan plan;
    LocalMapObject *player = avatar->mapObject;

    call.version = OVERWORLD_MOUNT_ACTION_ADAPTER_VERSION;
    call.size = sizeof(call);
    call.operation = OVERWORLD_MOUNT_ACTION_START_KNOCKBACK;
    call.state = state;
    call.avatar = avatar;
    call.trajectory = (u32 *)&plan;
    plan.direction = player->curFacing;
    plan.targetX = player->xCurr;
    plan.targetY = player->yCurr;
    plan.distance = 0;
    plan.duration = OVERWORLD_MOUNT_JUMP_IN_PLACE_FRAMES;
    plan.arcHeightQ4 = OVERWORLD_MOUNT_JUMP_IN_PLACE_ARC;
    (void)OVERWORLD_MOUNT_ACTION_ADAPTER_DISPATCH(&call);
}
