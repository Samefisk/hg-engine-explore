"""Extracted-C checks for the mounted chain adapter: B Jump, ledge Hop, resets."""

from pathlib import Path
import os
import re
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
#define OW_WILD_BEHAVIOR_SKID_BOOLEAN(options) ((options) & 1u)
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
#define OVERWORLD_MOUNT_MOTION_HOP 1
#define OVERWORLD_MOUNT_MOTION_CRASH 3
#define OVERWORLD_MOUNT_MOTION_WALK 4
#define PAD_BUTTON_B 2
static u32 systemNewKeys;
#define OVERWORLD_MOUNT_JUMP_SYSTEM_NEW_KEYS ((unsigned long)&systemNewKeys)
#define OVERWORLD_MOUNT_JUMP_IDLE 1u
#define OVERWORLD_MOUNT_JUMP_MARK_CRASH (1u << 1)
#define OVERWORLD_MOUNT_JUMP_APPLY_CRASH (1u << 2)
#define OVERWORLD_MOUNT_JUMP_CRASH_MIN_DISTANCE 4
/* @JUMP_REACH@ */
#define OVERWORLD_MOUNT_JUMP_REACH(framesPerTile) \
    ((framesPerTile) == 0 ? 0 : OVERWORLD_JUMP_REACH(framesPerTile))
#define OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(value) (((value) & 2) != 0)
#define OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION 1
#define OVERWORLD_WILD_OCCUPANCY_OBJECTS 0
#define OVERWORLD_WILD_OCCUPANCY_NONPLAYER 1
#define OVERWORLD_ACTOR_WALK_POLICY_CHAIN_COMMIT 1
#define OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING 2
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED 1
#define OVERWORLD_ACTOR_WALK_POLICY_RESET 3
typedef struct {
    u8 chillAction, hopMinDistance, hopMaxDistance, hopTime, hopAllowNonCardinal;
    u8 hopAllowVerticalObstacles, walkOptions, chillSpeed, jumpLevel;
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
    unsigned sessionGeneration;
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
    struct { u8 direction, speed; int linearElapsed, linearCarry; } walkMomentum;
} OverworldActorPolicyView;
typedef struct { int unused; } OverworldActorWalkPolicyCall;
static OverworldMountRuntimeState mountState;
#define OVERWORLD_MOUNT_RUNTIME_STATE_ADDR (&mountState)
static OverworldActorPolicyView policyState;
static FIELD_PLAYER_AVATAR avatar;
static FieldSystem field = {&avatar};
static LocalMapObject avatarObject;
static int blockedFront, occupiedFront, frontBehavior, behaviorReads, occupancyReads;
static int expectedDirection=3, expectedNonCardinal=1, expectedTime=4;
static int crashes, inPlace, lastDistance, startsAt[5], acceptAt[5];
static void OverworldMountJump_Crash(OverworldMountRuntimeState *state) {
    (void)state; crashes++;
}
static void OverworldMountJump_HopInPlace(OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *player) {
    (void)state; (void)player; inPlace++;
}
static unsigned OverworldMountFront_Behavior(FieldSystem *fieldSystem, int x, int y) {
    (void)fieldSystem; (void)x; (void)y; behaviorReads++; return frontBehavior;
}
static BOOL IsMetatileBlockedAt(FieldSystem *fieldSystem, int x, int y) {
    (void)fieldSystem; (void)x; (void)y; return blockedFront;
}
static BOOL OverworldWildOccupancy_Query(FieldSystem *fieldSystem, LocalMapObject *object,
    void *reserved, int x, int y, int flags, int kind) {
    (void)fieldSystem; (void)object; (void)reserved; (void)x; (void)y;
    (void)flags; (void)kind; occupancyReads++; return occupiedFront;
}
/* Like the real key policy, only the D-pad bits select a direction. */
static u8 OverworldMount_GetInputDirection(u32 keys) {
    switch (keys & 0xF0) {
    case 64: return 0;
    case 128: return 1;
    case 32: return 2;
    case 16: return 3;
    default: return 0xff;
    }
}
static BOOL PlayerHealthOverlay_IsReady(void) { return FALSE; }
static BOOL PlayerHealthField_OverrideControlEntry(FIELD_PLAYER_AVATAR *player,
    s32 *direction, u32 *newKeys, u32 *heldKeys) {
    (void)player; (void)direction; (void)newKeys; (void)heldKeys; return FALSE;
}
static void OverworldWalk_ApplyReleaseGrace(OverworldMountRuntimeState *state,
    u32 *heldKeys) {
    (void)state; (void)heldKeys;
}
static void OverworldWalk_SelectNewestMountedInput(OverworldMountRuntimeState *state,
    u32 *newKeys, u32 *heldKeys) {
    (void)state; (void)newKeys; (void)heldKeys;
}
static int startResult, starts, takes, commits, ordinary, resets, wrongLane;
static void OverworldMount_ResetMomentum(void);
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
/* startResult applies to every distance unless acceptAt selects one. */
static BOOL OverworldMount_TryStartCustomMotion(FIELD_PLAYER_AVATAR *player,
                                                 u8 direction, u8 facing, BOOL first) {
    OverworldWildBehaviorProfileData *lane = &mountState.snapshot.profile;
    int result = startResult;
    (void)player; (void)first;
    starts++;
    lastDistance = lane->hopMaxDistance;
    if (lastDistance < 5) startsAt[lastDistance]++;
    if (direction != expectedDirection || facing != expectedDirection || lane->chillAction != OW_WILD_BEHAVIOR_LOCOMOTION_HOP
        || lane->hopMinDistance != lane->hopMaxDistance || lane->hopTime != expectedTime
        || lane->hopAllowNonCardinal != expectedNonCardinal
        || mountState.walkEndState != OVERWORLD_MOUNT_WALK_END_CHAIN_HOP) wrongLane++;
    if (acceptAt[0]) result = lastDistance < 5 && acceptAt[lastDistance];
    if (result == 1) OverworldMount_ResetMomentum();
    return result;
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
static void Boundary(u32 newKeys) {
    OverworldMount_ChainControl(&avatar, 0, 0, newKeys, newKeys, 0);
}
/* The mount tick, inside the player health frame, applies a crash. */
static void Tick(void) {
    (void)OverworldMountJump_Boundary(&mountState, NULL, 0, OVERWORLD_MOUNT_JUMP_APPLY_CRASH);
}
int main(int argc, char **argv) {
    CHECK(argc == 2);
    mountState.fieldSystem = &field;
    avatar.mapObject = &avatarObject;
    mountState.snapshot.phase = OVERWORLD_MOUNT_PHASE_RIDING;
    mountState.snapshot.sessionGeneration = 5;
    mountState.presentationAttached = TRUE;
    mountState.snapshot.profile.chillAction = OW_WILD_BEHAVIOR_LOCOMOTION_WALK;
    mountState.snapshot.profile.hopMinDistance = 1;
    mountState.snapshot.profile.hopMaxDistance = 3;
    mountState.snapshot.profile.hopTime = 12;
    mountState.snapshot.profile.hopAllowNonCardinal = 1;
    mountState.snapshot.profile.hopAllowVerticalObstacles = 1;
    policyState.motionPhase = OVERWORLD_MOTION_PHASE_IDLE;
    policyState.walkMomentum.direction = 3;
    policyState.walkMomentum.speed = 4;
    if (!strcmp(argv[1], "no-automatic-obstacle-hop")) {
        /* A Jump lane walking into a wall without B uses ordinary Walk. */
        mountState.snapshot.profile.hopMinDistance = 2;
        mountState.snapshot.profile.hopMaxDistance = 2;
        blockedFront = 1; startResult = 1;
        Boundary(16);
        CHECK(starts == 0 && ordinary == 1 && crashes == 0);
    } else if (!strcmp(argv[1], "chain-forward-hop-consumed")) {
        policyState.pendingStep = OVERWORLD_ACTOR_WALK_PENDING_CHAIN;
        startResult = 1;
        Boundary(0);
        CHECK(commits == 1 && takes == 1 && starts == 0 && ordinary == 1);
        CHECK(mountState.walkEndState == OVERWORLD_MOUNT_WALK_END_NONE);
    } else if (!strcmp(argv[1], "jump-reach")) {
        static const u8 speeds[] = {8, 7, 6, 5, 4, 3, 2, 1};
        static const u8 reach[] = {2, 2, 3, 3, 4, 5, 6, 6};
        for (unsigned i = 0; i < 8; i++) {
            OverworldWildBehaviorProfileData before = mountState.snapshot.profile;
            policyState.walkMomentum.speed = speeds[i];
            expectedTime = speeds[i];
            mountState.walkEndState = OVERWORLD_MOUNT_WALK_END_NONE;
            startResult = 1; starts = 0; ordinary = 0;
            Boundary(PAD_BUTTON_B | 16);
            CHECK(starts == 1 && lastDistance == reach[i] && ordinary == 0);
            CHECK(mountState.walkEndState == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP);
            CHECK(!memcmp(&before, &mountState.snapshot.profile, sizeof(before)));
            /* A full-reach landing records no crash. */
            mountState.walkEndState = OVERWORLD_MOUNT_WALK_END_NONE;
            Boundary(0);
            Tick();
            CHECK(crashes == 0 && wrongLane == 0);
        }
    } else if (!strcmp(argv[1], "jump-short-lands-then-crashes")) {
        /* Reach 6 at two frames per tile; landing four tiles still hurts. */
        int before;
        policyState.walkMomentum.speed = 2; expectedTime = 2;
        acceptAt[0] = 1; acceptAt[4] = 1;
        Boundary(PAD_BUTTON_B | 16);
        CHECK(lastDistance == 4 && crashes == 0 && ordinary == 0);
        /* Still airborne: no crash yet. */
        mountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_HOP;
        Tick();
        CHECK(crashes == 0);
        mountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_NONE;
        mountState.walkEndState = OVERWORLD_MOUNT_WALK_END_NONE;
        /* The input boundary never applies it outside the health frame. */
        Boundary(0);
        CHECK(crashes == 0);
        before = resets;
        Tick();
        CHECK(crashes == 1 && resets == before);
        Tick();
        CHECK(crashes == 1);
    } else if (!strcmp(argv[1], "jump-short-under-four-only-stops")) {
        /* Landing fewer than four tiles stops the pair: no hit, no knockback. */
        int before;
        policyState.walkMomentum.speed = 4; expectedTime = 4;
        acceptAt[0] = 1; acceptAt[3] = 1;
        Boundary(PAD_BUTTON_B | 16);
        CHECK(startsAt[4] == 1 && startsAt[3] == 1 && lastDistance == 3);
        mountState.walkEndState = OVERWORLD_MOUNT_WALK_END_NONE;
        before = resets;
        Tick();
        CHECK(crashes == 0 && resets == before + 1);
        Tick();
        CHECK(crashes == 0 && resets == before + 1);
    } else if (!strcmp(argv[1], "jump-blocked-crashes-in-place")) {
        /* No Jump clears: zero tiles, so the pair only stops. */
        int before;
        policyState.walkMomentum.speed = 4; expectedTime = 4;
        startResult = 0;
        Boundary(PAD_BUTTON_B | 16);
        CHECK(starts == 4 && ordinary == 0 && crashes == 0);
        CHECK(mountState.walkEndState == OVERWORLD_MOUNT_WALK_END_NONE);
        before = resets;
        Tick();
        CHECK(crashes == 0 && resets == before + 1);
    } else if (!strcmp(argv[1], "jump-stream-busy")) {
        policyState.walkMomentum.speed = 4; expectedTime = 4;
        startResult = 2;
        Boundary(PAD_BUTTON_B | 16);
        CHECK(starts == 1 && ordinary == 0);
        Boundary(0);
        Tick();
        CHECK(crashes == 0 && starts == 1);
    } else if (!strcmp(argv[1], "jump-in-place")) {
        policyState.walkMomentum.speed = 0;
        Boundary(PAD_BUTTON_B);
        CHECK(inPlace == 1 && starts == 0 && ordinary == 0 && crashes == 0);
    } else if (!strcmp(argv[1], "jump-standing-held-direction")) {
        /* Standing next to an object, B with a held direction Jumps over it. */
        policyState.walkMomentum.speed = 0;
        policyState.walkMomentum.direction = 0;
        mountState.snapshot.profile.chillSpeed = 6; expectedTime = 6;
        startResult = 1;
        Boundary(PAD_BUTTON_B | 16);
        CHECK(starts == 1 && lastDistance == 2 && inPlace == 0 && ordinary == 0);
        CHECK(wrongLane == 0 && mountState.snapshot.profile.hopTime == 12);
    } else if (!strcmp(argv[1], "jump-needs-ability")) {
        mountState.snapshot.profile.hopAllowVerticalObstacles = 0;
        startResult = 1;
        Boundary(PAD_BUTTON_B | 16);
        CHECK(starts == 0 && inPlace == 0 && ordinary == 1);
    } else if (!strcmp(argv[1], "jump-press-mid-step-waits")) {
        expectedTime = 4; startResult = 1;
        mountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_WALK;
        Boundary(PAD_BUTTON_B | 16);
        CHECK(starts == 0);
        mountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_NONE;
        Boundary(16);
        CHECK(starts == 1 && lastDistance == 4 && ordinary == 1);
    } else if (!strcmp(argv[1], "jump-press-in-air-ignored")) {
        startResult = 1;
        for (int mode = OVERWORLD_MOUNT_MOTION_HOP; mode <= OVERWORLD_MOUNT_MOTION_CRASH; mode++) {
            mountState.snapshot.motionMode = mode;
            Boundary(PAD_BUTTON_B | 16);
        }
        mountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_NONE;
        Boundary(16);
        CHECK(starts == 0 && ordinary == 4);
    } else if (!strcmp(argv[1], "jump-press-during-bump")) {
        /* A stock wall bump keeps the chain control from running; the tick
         * still sees the press, and the next idle boundary Jumps. */
        startResult = 1;
        systemNewKeys = PAD_BUTTON_B;
        Tick();
        systemNewKeys = 0;
        Boundary(16);
        CHECK(starts == 1 && lastDistance == 4);
    } else if (!strcmp(argv[1], "jump-press-in-field-task-ignored")) {
        /* B that closes a menu or script never becomes a Jump. */
        startResult = 1;
        field.taskman = &field;
        systemNewKeys = PAD_BUTTON_B;
        Tick();
        field.taskman = NULL;
        systemNewKeys = 0;
        Boundary(16);
        CHECK(starts == 0 && ordinary == 1);
    } else if (!strcmp(argv[1], "jump-press-session-bound")) {
        startResult = 1;
        mountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_WALK;
        Boundary(PAD_BUTTON_B | 16);
        mountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_NONE;
        mountState.snapshot.sessionGeneration = 6;
        Boundary(16);
        CHECK(starts == 0 && ordinary == 2);
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
    } else if (!strcmp(argv[1], "ledge-grid")) {
        avatarObject.xCurr=10; avatarObject.yCurr=10;
        mountState.snapshot.profile.hopMinDistance=1;
        mountState.snapshot.profile.hopMaxDistance=8;
        mountState.snapshot.profile.hopAllowVerticalObstacles=0;
        mountState.snapshot.profile.hopAllowNonCardinal=0;
        expectedNonCardinal=0; blockedFront=1; startResult=1;
        policyState.walkMomentum.linearElapsed=32;
        policyState.walkMomentum.linearCarry=173;
        for(unsigned ledge=0;ledge<4;ledge++) for(unsigned dir=0;dir<4;dir++) for(unsigned jump=0;jump<3;jump++) {
            OverworldWildBehaviorProfileData beforeProfile;
            OverworldActorPolicyView beforePolicy;
            frontBehavior=56+ledge;expectedDirection=dir;
            policyState.walkMomentum.direction=dir;
            mountState.snapshot.profile.jumpLevel=jump;
            mountState.walkEndState=OVERWORLD_MOUNT_WALK_END_NONE;
            beforeProfile=mountState.snapshot.profile;beforePolicy=policyState;
            int beforeStarts=starts,beforeResets=resets,beforeReads=behaviorReads;
            int expected=jump!=0 && (ledge^(dir^(2|(dir>>1)))) <= (jump>=2);
            CHECK(Chain_StartForwardHop(&mountState,&avatar,&policyState,dir,0)==expected);
            CHECK(starts-beforeStarts==expected && behaviorReads-beforeReads==(jump!=0));
            CHECK(expected==0 || lastDistance==2);
            CHECK(resets==beforeResets && wrongLane==0);
            CHECK(!memcmp(&beforeProfile,&mountState.snapshot.profile,sizeof(beforeProfile)));
            CHECK(!memcmp(&beforePolicy,&policyState,sizeof(beforePolicy)));
        }
    } else if (!strcmp(argv[1], "ledge-fresh-walk")) {
        avatarObject.xCurr=10;avatarObject.yCurr=10;
        frontBehavior=59;blockedFront=1;startResult=1;
        mountState.snapshot.profile.hopMinDistance=1;
        mountState.snapshot.profile.hopMaxDistance=8;
        mountState.snapshot.profile.hopAllowVerticalObstacles=0;
        mountState.snapshot.profile.hopAllowNonCardinal=0;
        mountState.snapshot.profile.jumpLevel=2;mountState.snapshot.profile.chillSpeed=6;
        policyState.walkMomentum.speed=0;policyState.walkMomentum.direction=0xFF;
        expectedDirection=1;expectedNonCardinal=0;expectedTime=6;
        OverworldMount_ChainControl(&avatar,0,1,128,128,0);
        CHECK(starts==1 && ordinary==0 && wrongLane==0 && resets==0);
        CHECK(mountState.walkEndState==OVERWORLD_MOUNT_WALK_END_CHAIN_HOP);
        CHECK(mountState.snapshot.profile.hopTime==12 && policyState.walkMomentum.speed==0);
    } else if (!strcmp(argv[1], "ledge-occupied")) {
        avatarObject.xCurr=10;avatarObject.yCurr=10;
        frontBehavior=59;blockedFront=1;occupiedFront=1;startResult=1;
        mountState.snapshot.profile.jumpLevel=2;
        policyState.walkMomentum.direction=1;expectedDirection=1;
        CHECK(Chain_StartForwardHop(&mountState,&avatar,&policyState,1,0)==0);
        CHECK(starts==0 && resets==0 && occupancyReads==1);
    } else if (!strcmp(argv[1], "ledge-retry") || !strcmp(argv[1], "ledge-landing-blocked")) {
        OverworldWildBehaviorProfileData beforeProfile;
        OverworldActorPolicyView beforePolicy;
        avatarObject.xCurr=10;avatarObject.yCurr=10;
        frontBehavior=59;blockedFront=1;
        mountState.snapshot.profile.hopMinDistance=1;
        mountState.snapshot.profile.hopMaxDistance=8;
        mountState.snapshot.profile.jumpLevel=2;
        mountState.snapshot.profile.hopAllowVerticalObstacles=0;
        policyState.walkMomentum.direction=1;
        policyState.walkMomentum.linearElapsed=32;
        policyState.walkMomentum.linearCarry=173;expectedDirection=1;
        beforeProfile=mountState.snapshot.profile;beforePolicy=policyState;
        startResult=!strcmp(argv[1],"ledge-retry")?2:0;
        OverworldMount_ChainControl(&avatar,0,1,128,128,0);
        CHECK(starts==1 && ordinary==(startResult==0) && takes==0 && commits==0);
        CHECK(mountState.walkEndState==OVERWORLD_MOUNT_WALK_END_NONE && crashes==0);
        CHECK(!memcmp(&beforeProfile,&mountState.snapshot.profile,sizeof(beforeProfile)));
        CHECK(!memcmp(&beforePolicy,&policyState,sizeof(beforePolicy)));
        if(startResult==2) {
            startResult=1;
            OverworldMount_ChainControl(&avatar,0,1,0,128,0);
            CHECK(starts==2 && ordinary==0 && wrongLane==0 && resets==0);
            CHECK(mountState.walkEndState==OVERWORLD_MOUNT_WALK_END_CHAIN_HOP);
            CHECK(!memcmp(&beforeProfile,&mountState.snapshot.profile,sizeof(beforeProfile)));
            CHECK(!memcmp(&beforePolicy,&policyState,sizeof(beforePolicy)));
        }
    } else if (!strcmp(argv[1], "ledge-busy-guards")) {
        avatarObject.xCurr=10;avatarObject.yCurr=10;
        frontBehavior=59;blockedFront=1;startResult=1;
        mountState.snapshot.profile.jumpLevel=2;policyState.walkMomentum.direction=1;expectedDirection=1;
        for(unsigned selected=0;selected<9;selected++) {
            mountState.snapshot.motionMode=0;mountState.motionStreamPreparing=0;
            mountState.pendingFieldStep=0;policyState.pendingStep=0;policyState.motionPhase=0;
            policyState.pendingSkid=0;field.taskman=NULL;avatar.state=0;avatar.unk0=0;
            if(selected==0)mountState.snapshot.motionMode=1;
            if(selected==1)mountState.motionStreamPreparing=1;
            if(selected==2)mountState.pendingFieldStep=1;
            if(selected==3)policyState.pendingStep=1;
            if(selected==4)policyState.motionPhase=1;
            if(selected==5)policyState.pendingSkid=1;
            if(selected==6)field.taskman=&field;
            if(selected==7)avatar.state=1;
            if(selected==8)avatar.unk0=1;
            CHECK(Chain_StartForwardHop(&mountState,&avatar,&policyState,1,0)==0);
            CHECK(starts==0 && behaviorReads==0 && resets==0);
        }
    } else if (!strcmp(argv[1], "ledge-turn-dismount")) {
        avatarObject.xCurr=10;avatarObject.yCurr=10;
        frontBehavior=59;blockedFront=1;startResult=1;mountState.snapshot.profile.jumpLevel=2;
        policyState.walkMomentum.direction=0;
        OverworldMount_ChainControl(&avatar,0,1,128,128,0);
        CHECK(starts==0 && ordinary==1 && behaviorReads==0);
        policyState.walkMomentum.direction=1;mountState.bufferedTogglePending=1;
        OverworldMount_ChainControl(&avatar,0,1,128,128,0);
        CHECK(starts==0 && ordinary==2 && behaviorReads==0);
    } else if (!strcmp(argv[1], "front-bounds")) {
        mountState.snapshot.profile.jumpLevel=2;
        policyState.walkMomentum.speed=0;
        CHECK(!OverworldMount_CanCrossFront(&mountState,&avatarObject,&policyState,0));
        CHECK(!OverworldMount_CanCrossFront(&mountState,&avatarObject,&policyState,2));
        CHECK(!OverworldMount_CanCrossFront(&mountState,&avatarObject,&policyState,4));
        CHECK(behaviorReads==0 && occupancyReads==0);
    } else return 2;
    return 0;
}
'''


def program():
    source = CHAIN_SOURCE.read_text()
    leaf = (ROOT / "src/overworld_actor_system_overlay/overworld_mount_front_admission.c").read_text()
    jump = (ROOT / "src/pokemon_move_history_task6_overlay/overworld_mount_jump.c").read_text()
    def extracted(name, signature):
        return signature + " {" + function_body(source, name) + "}\n"
    reach = re.search(r"^#define OVERWORLD_JUMP_REACH\(framesPerTile\)(?:[^\n]*\\\n)*[^\n]*",
                      (ROOT / "include/overworld_hop_clearance_native.h").read_text(), re.M)
    return (STUBS.replace("/* @JUMP_REACH@ */", reach.group(0))
        + "static struct { u32 latchSession, crashSession; } sOverworldMountJump;\n"
        + "static u32 OverworldMountJump_Boundary(OverworldMountRuntimeState *state, const OverworldActorPolicyView *policy, u32 newKeys, u32 flags) {"
        + function_body(jump, "OverworldMountJump_Boundary") + "}\n"
        + "static BOOL OverworldMount_CanCrossFront(OverworldMountRuntimeState *state, LocalMapObject *player, const OverworldActorPolicyView *policy, u8 direction) {"
        + function_body(leaf, "OverworldMount_CanCrossFront") + "}\n"
        + extracted("OverworldMount_ResetMomentum", "static void OverworldMount_ResetMomentum(void)")
        + extracted("Chain_StartForwardHop", "static u8 Chain_StartForwardHop(OverworldMountRuntimeState *state, FIELD_PLAYER_AVATAR *avatar, const OverworldActorPolicyView *policy, u8 direction, u32 newKeys)")
        + extracted("OverworldMount_ChainControl", "static void OverworldMount_ChainControl(FIELD_PLAYER_AVATAR *avatar, u32 param1, s32 direction, u32 newKeys, u32 heldKeys, u32 param5)")
        + CASES)


class MountChainActionLifecycleTests(unittest.TestCase):
    def test_mount_start_retries_only_pre_start_delays(self):
        source = (ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text()
        body = function_body(source, "OverworldMount_TryStartCustomMotion")
        retry = ("return sOverworldMountState.walkEndState\n"
                 "            == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP ? 2 : FALSE;")
        cooldown = body.index("if (sOverworldMountState.motionCooldown != 0")
        missing_follower = body.index("if (follower == NULL\n        || (!liveStream && !OverworldMount_TerrainStreamIsIdle())) {")
        # A cardinal ledge Hop or B Jump uses the live player streamer.
        self.assertIn("liveStream = sOverworldMountState.walkEndState\n"
                      "            == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP\n"
                      "        && direction < OVERWORLD_MOUNT_DIRECTION_NORTH_WEST;", body)
        self.assertIn("if (!liveStream && !OverworldMount_BeginTerrainStream())", body)
        self.assertIn(retry, body[cooldown:body.index("}", cooldown)])
        self.assertIn(retry, body[missing_follower:body.index("}", missing_follower)])
        self.assertEqual(body.count("? 2 : FALSE"), 2)
        # Every mounted Hop, including the Hop walking style, takes one exact
        # forward target per try, from hopMaxDistance down to hopMinDistance.
        self.assertNotIn("hop_target_found", body)
        self.assertNotIn("TryNextHopLandingCandidate", body)
        self.assertIn("distance = lane->hopMaxDistance;\nnext_distance:\n"
                      "        actionCall.action = (u8)distance;", body)
        self.assertIn("if (distance <= lane->hopMinDistance || distance <= 1) {\n"
                      "                return FALSE;\n            }\n"
                      "            distance--;\n            goto next_distance;", body)
        rejected = body.index("if (!actorMotionStarted && !OverworldMount_BeginSharedMotion(FALSE))")
        self.assertIn("return FALSE;", body[rejected:body.index("}", rejected)])

    def test_jump_crash_damages_only_the_rider_and_knocks_back(self):
        source = (ROOT / "src/pokemon_move_history_task6_overlay/overworld_mount_jump.c").read_text()
        body = function_body(source, "OverworldMountJump_Crash")
        self.assertIn("OVERWORLD_MOUNT_JUMP_CRASH_DAMAGE, 256,\n"
                      "        OVERWORLD_MOUNT_JUMP_CRASH_KNOCKBACK,\n"
                      "        fieldSystem->playerAvatar->mapObject->curFacing ^ 1);", body)
        self.assertNotIn("SetMonData", source)
        self.assertNotIn("MON_DATA_HP", source)
        header = (ROOT / "include/overworld_mount_jump.h").read_text()
        self.assertIn("OW_WILD_BEHAVIOR_KNOCKBACK_OPTIONS(OW_WILD_BEHAVIOR_KNOCKBACK_SLIDE, 1)", header)

    def test_jump_into_water_returns_a_non_water_runner(self):
        source = (ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text()
        body = function_body(source, "OverworldMount_JumpLanded")
        for needle in ("!= OVERWORLD_MOUNT_WALK_END_CHAIN_HOP",
                       "& OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER) != 0",
                       "OverworldMount_IsSurfBehavior(OverworldMount_TileBehavior(",
                       "OVERWORLD_MOUNT_JUMP_WATER_DAMAGE, 256, 0, 0);",
                       "OverworldWalkMount_RebaseMotionTarget(&sOverworldMountState);\n"
                       "    OverworldMount_CommitMotionTarget(player);",
                       "sOverworldMountState.walkEndState = OVERWORLD_MOUNT_WALK_END_NONE;"):
            self.assertIn(needle, body)
        tick = function_body(source, "OverworldMount_Tick")
        self.assertIn("OverworldMount_UpdateCustomMotion();\n    OverworldMount_JumpLanded();", tick)
        action = (ROOT / "src/overworld_mount_action_overlay/overworld_mount_action_overlay.c").read_text()
        self.assertIn("| (u32)state->walkEndState\n"
                      "                    / OVERWORLD_MOUNT_WALK_END_CHAIN_HOP\n"
                      "                    * OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER",
                      function_body(action, "OverworldMountAction_ChainForwardTarget"))

    def test_real_chain_adapter_start_and_reset_outcomes(self):
        with tempfile.TemporaryDirectory(prefix="mount-chain-") as temporary:
            binary = Path(temporary) / "chain"
            result = subprocess.run(
                [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O0",
                 "-x", "c", "-", "-o", str(binary)],
                input=program(), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for case in ("no-automatic-obstacle-hop", "chain-forward-hop-consumed",
                         "jump-reach", "jump-short-lands-then-crashes",
                         "jump-short-under-four-only-stops",
                         "jump-blocked-crashes-in-place", "jump-stream-busy",
                         "jump-in-place", "jump-standing-held-direction",
                         "jump-needs-ability",
                         "jump-press-mid-step-waits", "jump-press-in-air-ignored",
                         "jump-press-session-bound", "jump-press-during-bump",
                         "jump-press-in-field-task-ignored", "reset-active",
                         "reset-detached", "reset-normal", "ledge-grid",
                         "ledge-fresh-walk", "ledge-occupied", "ledge-retry",
                         "ledge-landing-blocked", "ledge-busy-guards",
                         "ledge-turn-dismount", "front-bounds"):
                with self.subTest(case=case):
                    result = subprocess.run([str(binary), case], text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
