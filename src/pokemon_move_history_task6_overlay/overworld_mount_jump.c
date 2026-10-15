#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_mount_jump.h"
#include "../../include/player_health.h"
#include "../../include/map_events_internal.h"
#include "../../include/constants/buttons.h"

/* Boot-resident B Jump receipts and crash for the mounted chain adapter,
 * whose fixed overlay-159 slot holds only the input boundary. */

__asm__(
    ".thumb\n"
    ".global OverworldActorPolicy_MountCommand\n"
    ".thumb_func\n.thumb_set OverworldActorPolicy_MountCommand, 0x023BA0E1\n");

/* B Jump receipts. Each holds the mount session that owns it, so a dismount
 * or remount cannot replay it. A riding session is never zero. */
static struct {
    u32 latchSession;
    u32 crashSession;
} sOverworldMountJump;

static void OverworldMountJump_Crash(OverworldMountRuntimeState *state);

/* One mounted Jump boundary. MARK_CRASH records a Jump that stopped short;
 * newKeys then carries its landed distance. APPLY_CRASH (mount tick) applies
 * a recorded crash once the pair has landed.
 * The input boundary keeps a B press made on the ground until the next idle
 * tile boundary and returns TRUE when that boundary should start the Jump.
 * A press in the air, during a crash shake, skid or other custom motion is
 * ignored. The tick passes no keys and no policy; it reads the press. */
u32 __attribute__((noinline, used, optimize("Os"),
        section(".overworld_mount_jump")))
OverworldMountJump_Boundary(OverworldMountRuntimeState *state,
    const OverworldActorPolicyView *policy, u32 newKeys, u32 flags)
{
    u32 session = state->snapshot.sessionGeneration;

    if (flags & OVERWORLD_MOUNT_JUMP_MARK_CRASH) {
        /* Only a Jump of OVERWORLD_MOUNT_JUMP_CRASH_MIN_DISTANCE or more tiles
         * hurts. A shorter one records ~session: it only stops the pair.
         * Sessions count mounts from one, so ~session is never a session. */
        sOverworldMountJump.crashSession =
            newKeys >= OVERWORLD_MOUNT_JUMP_CRASH_MIN_DISTANCE
                ? session : ~session;
        return FALSE;
    }
    /* Only the mount tick applies a crash: the player health frame is open
     * there, and the rider hit needs it. */
    if ((flags & OVERWORLD_MOUNT_JUMP_APPLY_CRASH) != 0) {
        if (state->snapshot.motionMode == OVERWORLD_MOUNT_MOTION_NONE) {
            if (sOverworldMountJump.crashSession == session) {
                sOverworldMountJump.crashSession = 0;
                OverworldMountJump_Crash(state);
            } else if (sOverworldMountJump.crashSession == ~session) {
                sOverworldMountJump.crashSession = 0;
                (void)OverworldActorPolicy_MountCommand(
                    OVERWORLD_ACTOR_WALK_POLICY_RESET, NULL);
            }
        }
        /* The tick runs every frame, also while a stock wall bump keeps the
         * chain control from running, so it latches this frame's B press
         * (stock gSystem.newKeys) unless a field task such as a menu or
         * script owns the input. */
        if (state->fieldSystem->taskman == NULL) {
            newKeys = *(volatile u32 *)OVERWORLD_MOUNT_JUMP_SYSTEM_NEW_KEYS;
        }
    }
    if ((newKeys & PAD_BUTTON_B) != 0
        && OW_WILD_BEHAVIOR_SKID_BOOLEAN(
            state->snapshot.profile.hopAllowVerticalObstacles)
        && (state->snapshot.motionMode == OVERWORLD_MOUNT_MOTION_NONE
            || state->snapshot.motionMode == OVERWORLD_MOUNT_MOTION_WALK)
        && state->motionCooldown == 0
        && (policy == NULL || policy->pendingSkid == 0)) {
        sOverworldMountJump.latchSession = session;
    }
    if ((flags & OVERWORLD_MOUNT_JUMP_IDLE) == 0
        || sOverworldMountJump.latchSession != session) {
        return FALSE;
    }
    sOverworldMountJump.latchSession = 0;
    return TRUE;
}

/* A Jump of four or more tiles that stopped short crashes after it lands: only the rider takes
 * the fixed damage, through the ordinary contact hit that also plays the
 * mounted crash, and the pair is knocked back one tile opposite its facing.
 * The crash ends the Walk momentum. The mount's party HP never changes. */
static void __attribute__((noinline, optimize("Os"),
        section(".overworld_mount_jump_tail")))
OverworldMountJump_Crash(OverworldMountRuntimeState *state)
{
    FieldSystem *fieldSystem = state->fieldSystem;

    (void)PLAYER_HEALTH_OVERLAY_ENTRY->tryContact(fieldSystem,
        1, 0, OVERWORLD_MOUNT_JUMP_CRASH_DAMAGE, 256,
        OVERWORLD_MOUNT_JUMP_CRASH_KNOCKBACK,
        fieldSystem->playerAvatar->mapObject->curFacing ^ 1);
    (void)OverworldActorPolicy_MountCommand(
        OVERWORLD_ACTOR_WALK_POLICY_RESET, NULL);
}
