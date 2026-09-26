"""Extracted-C checks for the mounted chain adapter's start outcomes."""

from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

from scripts.verify_overworld_mount import function_body


ROOT = Path(__file__).resolve().parents[2]
CHAIN_SOURCE = ROOT / "src/overworld_mount_chain_overlay/overworld_mount_chain_overlay.c"


STUBS = r'''
#include <stdio.h>
#include <string.h>
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef int s32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define PLAYER_STATE_WALKING 0
#define OVERWORLD_MOUNT_PHASE_RIDING 3
#define OVERWORLD_MOUNT_WALK_END_NONE 0
#define OVERWORLD_MOUNT_WALK_END_CHAIN_HOP 4
#define OW_WILD_BEHAVIOR_LOCOMOTION_WALK 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP 2
#define OW_WILD_BEHAVIOR_BOOL_YES 1
#define OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY 0
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD 7
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE 1
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS 5
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE 6
#define OVERWORLD_MOUNT_ACTION_FINAL 0
#define OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT 7
#define OVERWORLD_MOTION_PHASE_IDLE 0
#define OVERWORLD_ACTOR_WALK_PENDING_CHAIN 1
#define OVERWORLD_ACTOR_WALK_PENDING_NONE 0
#define OVERWORLD_MOUNT_MOTION_NONE 0
#define OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION 1
#define OVERWORLD_WILD_OCCUPANCY_OBJECTS 1
#define OVERWORLD_ACTOR_WALK_POLICY_CHAIN_COMMIT 1
#define OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING 2
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED 1
#define OVERWORLD_ACTOR_WALK_POLICY_RESET 3
typedef struct {
    u8 chillAction, hopMinDistance, hopMaxDistance, hopTime, hopAllowNonCardinal;
    u8 hopAllowVerticalObstacles, walkOptions, chillSpeed;
} OverworldWildBehaviorProfileData;
typedef struct { int xCurr, yCurr; } LocalMapObject;
typedef struct {
    int state, unk0;
    LocalMapObject *mapObject;
} FIELD_PLAYER_AVATAR;
typedef struct {
    FIELD_PLAYER_AVATAR *playerAvatar;
    void *taskman;
} FieldSystem;
typedef struct {
    int phase, motionMode;
    OverworldWildBehaviorProfileData profile;
} OverworldMountSnapshot;
typedef struct {
    FieldSystem *fieldSystem;
    OverworldMountSnapshot snapshot;
    int walkEndState, presentationAttached, pendingFieldStep, motionStreamPreparing;
    int bufferedTogglePending;
    u16 motionCooldown;
} OverworldMountRuntimeState;
typedef struct {
    int pendingStep, motionPhase, chainPauseAction, chainPauseTicks, pendingSkid;
    struct { u8 direction, speed; } walkMomentum;
} OverworldActorPolicyView;
typedef struct { int unused; } OverworldActorWalkPolicyCall;
static OverworldMountRuntimeState mountState;
#define OVERWORLD_MOUNT_RUNTIME_STATE_ADDR (&mountState)
static OverworldActorPolicyView policyState;
static FIELD_PLAYER_AVATAR avatar;
static FieldSystem field = {&avatar};
static LocalMapObject avatarObject;
static int blockedFront, occupiedFront;
static BOOL IsMetatileBlockedAt(FieldSystem *fieldSystem, int x, int y) {
    (void)fieldSystem; return blockedFront && x == 1 && y == 0;
}
static BOOL OverworldWildOccupancy_Query(FieldSystem *fieldSystem, LocalMapObject *object,
    void *reserved, int x, int y, int flags, int kind) {
    (void)fieldSystem; (void)object; (void)reserved; (void)x; (void)y;
    (void)flags; (void)kind; return occupiedFront;
}
static u8 OverworldMount_GetInputDirection(u32 keys) {
    return keys == 16 ? 3 : 0xff;
}
static int startResult, starts, takes, commits, ordinary, resets, wrongLane;
static BOOL OverworldActorPolicy_Inspect(u8 slot, OverworldActorPolicyView *policy) {
    if (slot != OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT) return FALSE;
    *policy = policyState;
    return TRUE;
}
static BOOL Chain_Reduce(OverworldMountRuntimeState *state, u8 operation, u8 flags,
                         u8 chainAction, u8 chainTicks,
                         OverworldActorWalkPolicyCall *call) {
    (void)state; (void)flags; (void)chainAction; (void)chainTicks; (void)call;
    if (operation == OVERWORLD_ACTOR_WALK_POLICY_CHAIN_COMMIT) {
        commits++;
        policyState.pendingStep = 0;
        policyState.chainPauseAction = 0x80 | OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD;
        policyState.chainPauseTicks = 4;
    } else if (operation == OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING) {
        takes++;
        policyState.chainPauseAction = 0;
        policyState.chainPauseTicks = 0;
    } else return FALSE;
    return TRUE;
}
static BOOL Chain_ActionActive(const OverworldMountRuntimeState *state,
                               const OverworldActorPolicyView *policy) {
    (void)state; (void)policy; return FALSE;
}
static u8 Chain_StartAdapterAction(OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *player, const OverworldActorPolicyView *policy, u8 action) {
    (void)state; (void)player; (void)policy; (void)action;
    return OVERWORLD_MOUNT_ACTION_FINAL;
}
static BOOL OverworldMount_TryStartCustomMotion(FIELD_PLAYER_AVATAR *player,
                                                 u8 direction, u8 facing, BOOL first) {
    OverworldWildBehaviorProfileData *lane = &mountState.snapshot.profile;
    (void)player; (void)first;
    starts++;
    if (direction != 3 || facing != 3 || lane->chillAction != OW_WILD_BEHAVIOR_LOCOMOTION_HOP
        || lane->hopMinDistance != 2 || lane->hopMaxDistance != 2 || lane->hopTime != 4
        || lane->hopAllowNonCardinal != 1
        || mountState.walkEndState != OVERWORLD_MOUNT_WALK_END_CHAIN_HOP) wrongLane++;
    return startResult;
}
static void OverworldMount_ProcessPlayerControl(FIELD_PLAYER_AVATAR *player,
    u32 param1, s32 direction, u32 newKeys, u32 heldKeys, u32 param5) {
    (void)player; (void)param1; (void)direction; (void)newKeys; (void)heldKeys; (void)param5;
    ordinary++;
}
static BOOL OverworldActorPolicy_MountCommand(u8 operation, void *result) {
    (void)result;
    if (operation == OVERWORLD_ACTOR_WALK_POLICY_RESET) resets++;
    return TRUE;
}
'''


CASES = r'''
#define CHECK(value) do { if (!(value)) { fprintf(stderr, "line %d: %s\n", __LINE__, #value); return 1; } } while (0)
int main(int argc, char **argv) {
    CHECK(argc == 2);
    mountState.fieldSystem = &field;
    avatar.mapObject = &avatarObject;
    mountState.snapshot.phase = OVERWORLD_MOUNT_PHASE_RIDING;
    mountState.presentationAttached = TRUE;
    mountState.snapshot.profile.chillAction = OW_WILD_BEHAVIOR_LOCOMOTION_WALK;
    mountState.snapshot.profile.hopMinDistance = 1;
    mountState.snapshot.profile.hopMaxDistance = 3;
    mountState.snapshot.profile.hopTime = 12;
    mountState.snapshot.profile.hopAllowNonCardinal = 1;
    policyState.motionPhase = OVERWORLD_MOTION_PHASE_IDLE;
    policyState.walkMomentum.direction = 3;
    policyState.walkMomentum.speed = 4;
    if (!strcmp(argv[1], "retry")) {
        policyState.pendingStep = OVERWORLD_ACTOR_WALK_PENDING_CHAIN;
        startResult = 2;
        OverworldMount_ChainControl(&avatar, 0, 0, 0, 0, 0);
        CHECK(commits == 1 && starts == 1 && takes == 0 && ordinary == 0);
        CHECK(policyState.chainPauseAction == 0x87 && policyState.chainPauseTicks == 4);
        CHECK(mountState.walkEndState == OVERWORLD_MOUNT_WALK_END_NONE);
        CHECK(mountState.snapshot.profile.chillAction == OW_WILD_BEHAVIOR_LOCOMOTION_WALK);
        CHECK(mountState.snapshot.profile.hopMinDistance == 1
            && mountState.snapshot.profile.hopMaxDistance == 3
            && mountState.snapshot.profile.hopTime == 12
            && mountState.snapshot.profile.hopAllowNonCardinal == 1 && wrongLane == 0);
        startResult = 1;
        OverworldMount_ChainControl(&avatar, 0, 0, 0, 0, 0);
        CHECK(commits == 1 && starts == 2 && takes == 1 && ordinary == 0);
        CHECK(policyState.chainPauseAction == 0 && mountState.walkEndState == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP);
        CHECK(wrongLane == 0);
    } else if (!strcmp(argv[1], "abort")) {
        policyState.chainPauseAction = 0x87;
        startResult = 0;
        OverworldMount_ChainControl(&avatar, 0, 0, 0, 0, 0);
        CHECK(starts == 1 && takes == 1 && ordinary == 1);
        CHECK(policyState.chainPauseAction == 0 && mountState.walkEndState == OVERWORLD_MOUNT_WALK_END_NONE);
    } else if (!strcmp(argv[1], "not-ready")) {
        policyState.chainPauseAction = 0x87;
        avatar.state = 1;
        OverworldMount_ChainControl(&avatar, 0, 0, 0, 0, 0);
        CHECK(starts == 0 && takes == 0 && ordinary == 0 && policyState.chainPauseAction == 0x87);
    } else if (!strcmp(argv[1], "reset-active")) {
        mountState.walkEndState = OVERWORLD_MOUNT_WALK_END_CHAIN_HOP;
        OverworldMount_ResetMomentum();
        CHECK(resets == 0);
    } else if (!strcmp(argv[1], "reset-detached")) {
        mountState.walkEndState = OVERWORLD_MOUNT_WALK_END_CHAIN_HOP;
        mountState.presentationAttached = FALSE;
        OverworldMount_ResetMomentum();
        CHECK(resets == 1);
    } else if (!strcmp(argv[1], "reset-normal")) {
        OverworldMount_ResetMomentum();
        CHECK(resets == 1);
    } else if (!strcmp(argv[1], "obstacle")) {
        mountState.snapshot.profile.hopMinDistance = 2;
        mountState.snapshot.profile.hopMaxDistance = 2;
        mountState.snapshot.profile.hopAllowVerticalObstacles = 1;
        blockedFront = 1;
        startResult = 1;
        OverworldMount_ChainControl(&avatar, 0, 0, 16, 16, 0);
        CHECK(starts == 1 && ordinary == 0 && takes == 0 && wrongLane == 0);
        CHECK(mountState.snapshot.profile.chillAction == OW_WILD_BEHAVIOR_LOCOMOTION_WALK);
    } else if (!strcmp(argv[1], "obstacle-occupied")) {
        mountState.snapshot.profile.hopMinDistance = 2;
        mountState.snapshot.profile.hopMaxDistance = 2;
        mountState.snapshot.profile.hopAllowVerticalObstacles = 1;
        blockedFront = 1;
        occupiedFront = 1;
        OverworldMount_ChainControl(&avatar, 0, 0, 16, 16, 0);
        CHECK(starts == 0 && ordinary == 1);
    } else if (!strcmp(argv[1], "obstacle-turn")) {
        mountState.snapshot.profile.hopMinDistance = 2;
        mountState.snapshot.profile.hopMaxDistance = 2;
        mountState.snapshot.profile.hopAllowVerticalObstacles = 1;
        policyState.walkMomentum.direction = 0;
        blockedFront = 1;
        OverworldMount_ChainControl(&avatar, 0, 0, 16, 16, 0);
        CHECK(starts == 0 && ordinary == 1);
    } else if (!strcmp(argv[1], "obstacle-dismount")) {
        mountState.snapshot.profile.hopMinDistance = 2;
        mountState.snapshot.profile.hopMaxDistance = 2;
        mountState.snapshot.profile.hopAllowVerticalObstacles = 1;
        mountState.bufferedTogglePending = 1;
        blockedFront = 1;
        OverworldMount_ChainControl(&avatar, 0, 0, 16, 16, 0);
        CHECK(starts == 0 && ordinary == 1);
    } else return 2;
    return 0;
}
'''


def program():
    source = CHAIN_SOURCE.read_text()
    def extracted(name, signature):
        return signature + " {" + function_body(source, name) + "}\n"
    return (STUBS
        + extracted("OverworldMount_ResetMomentum", "static void OverworldMount_ResetMomentum(void)")
        + extracted("Chain_StartForwardHop", "static u8 Chain_StartForwardHop(OverworldMountRuntimeState *state, FIELD_PLAYER_AVATAR *avatar, const OverworldActorPolicyView *policy, u8 direction, BOOL obstacleOnly)")
        + extracted("OverworldMount_ChainControl", "static void OverworldMount_ChainControl(FIELD_PLAYER_AVATAR *avatar, u32 param1, s32 direction, u32 newKeys, u32 heldKeys, u32 param5)")
        + CASES)


class MountChainActionLifecycleTests(unittest.TestCase):
    def test_mount_start_retries_only_pre_start_delays(self):
        source = (ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text()
        body = function_body(source, "OverworldMount_TryStartCustomMotion")
        retry = ("return sOverworldMountState.walkEndState\n"
                 "            == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP ? 2 : FALSE;")
        cooldown = body.index("if (sOverworldMountState.motionCooldown != 0")
        missing_follower = body.index("if (follower == NULL || !OverworldMount_TerrainStreamIsIdle())")
        self.assertIn(retry, body[cooldown:body.index("}", cooldown)])
        self.assertIn(retry, body[missing_follower:body.index("}", missing_follower)])
        self.assertEqual(body.count("? 2 : FALSE"), 2)
        self.assertIn("return FALSE;\nhop_target_found:", body)
        rejected = body.index("if (!actorMotionStarted && !OverworldMount_BeginSharedMotion(FALSE))")
        self.assertIn("return FALSE;", body[rejected:body.index("}", rejected)])

    def test_real_chain_adapter_start_and_reset_outcomes(self):
        with tempfile.TemporaryDirectory(prefix="mount-chain-") as temporary:
            binary = Path(temporary) / "chain"
            result = subprocess.run(
                [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O0",
                 "-x", "c", "-", "-o", str(binary)],
                input=program(), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for case in ("retry", "abort", "not-ready", "reset-active",
                         "reset-detached", "reset-normal", "obstacle",
                         "obstacle-occupied", "obstacle-turn",
                         "obstacle-dismount"):
                with self.subTest(case=case):
                    result = subprocess.run([str(binary), case], text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
