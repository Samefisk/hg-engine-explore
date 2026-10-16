"""Run the real Mount detach/cancel reducers at the stock sprite boundary."""
from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile
import unittest

from scripts.verify_overworld_mount import function_body

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c"

STUBS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OVERWORLD_MOUNT_PHASE_NONE 0
#define OVERWORLD_MOUNT_PHASE_RIDING 3
#define OVERWORLD_MOUNT_MOTION_NONE 0
#define OVERWORLD_MOUNT_MOTION_HOP 1
#define OVERWORLD_MOUNT_WALK_END_NONE 0
#define OVERWORLD_MOUNT_CANCEL_EXPLICIT 1
#define OVERWORLD_MOUNT_CANCEL_FIELD_BUSY 2
#define OVERWORLD_MOUNT_CANCEL_MAP_CHANGE 3
#define OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST 4
#define OVERWORLD_MOUNT_CANCEL_IDENTITY_CHANGED 5
#define OVERWORLD_MOUNT_CANCEL_OVERLAY_CLEANUP 6
#define OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT 1u
#define MAPOBJECTFLAG_UNK7 (1u << 7)
#define MAPOBJECTFLAG_UNK14 (1u << 14)
#define MAPOBJECTFLAG_UNK20 (1u << 20)
#define MAPOBJECTFLAG_UNK31 (1u << 31)
#define MAPOBJECTFLAG_MOVEMENT_PAUSED (1u << 6)
#define OVERWORLD_MOUNT_ACTION_ADAPTER_VERSION 1
#define OVERWORLD_MOUNT_ACTION_CANCEL_CHAIN 2
#define OVERWORLD_ACTOR_WALK_POLICY_BIND_PROFILE 3
typedef struct {
    u32 flags;
    int xPrev, hPrev, yPrev, xCurr, hCurr, yCurr;
    int faceVec[3], unk88[3];
    u16 gfx;
} LocalMapObject;
typedef struct { LocalMapObject *mapObject; u32 unk0; } FIELD_PLAYER_AVATAR;
typedef struct { FIELD_PLAYER_AVATAR *playerAvatar; } FieldSystem;
typedef struct {
    FieldSystem *fieldSystem;
    struct { int phase, motionMode, reserved; } snapshot;
    int walkEndState, pendingFieldStep, presentationAttached;
    int preserveTransitionPrepared, motionStreamPreparing;
    int playerBaseFaceY, playerBaseUnk88Y;
    u16 savedPlayerGfxId;
    int savedPlayerShadowSuppressed, priorFollowerBehaviorFingerprint;
} OverworldMountRuntimeState;
typedef struct { int version, size, operation; OverworldMountRuntimeState *state; } OverworldMountActionCall;
static OverworldMountRuntimeState sOverworldMountState;
static LocalMapObject player, follower;
static FIELD_PLAYER_AVATAR avatar = {&player, 0};
static FieldSystem field = {&avatar};
static int sOverworldWildSpawnState;
static int hasPlayer = 1, hasFollower = 1, bindingMatches = 1, finalizePending;
static int clearPlayer, clearFollower, resetAvatar, updateHeight, clearCooldown;
static int clearBoundary, changeSprite, clearPresentation, setSprite, ended;
static int chainCancel, rebase, finish, sharedCancel, releaseStream, resetMomentum, bindPolicy;
static int sequence, clearedAt, setAt, rendererOldGfx;
static int endedReason, spriteTarget;
static LocalMapObject *OverworldMount_GetFollowerObject(void) { return hasFollower ? &follower : NULL; }
static BOOL OverworldMount_HasCurrentPlayer(void) { return hasPlayer; }
static void OverworldMount_ClearObjectCommand(LocalMapObject *object) {
    if (object == &player) clearPlayer++; else if (object == &follower) clearFollower++; else abort();
}
static void OverworldMount_ResetAvatarAfterCancel(FIELD_PLAYER_AVATAR *value) {
    if (value != &avatar) abort(); resetAvatar++;
}
static void OverworldMount_UpdatePlayerBaseHeight(LocalMapObject *object) {
    if (object != &player) abort(); updateHeight++;
}
/* This stand-in is the stock boundary, not a second detach implementation.
 * The native entry frees the current renderer before setting INVALID gfx. */
static void OverworldMount_ClearPlayerPresentation(LocalMapObject *object) {
    if (object != &player) abort();
    rendererOldGfx = object->gfx;
    object->flags &= ~MAPOBJECTFLAG_UNK14;
    object->gfx = 0xFFFF;
    clearPresentation++;
    clearedAt = ++sequence;
}
static void MapObject_SetGfxID(LocalMapObject *object, u32 gfx) {
    if (object != &player) abort();
    if (clearPresentation != 1 || object->gfx != 0xFFFF) abort();
    object->gfx = (u16)gfx; setSprite++; setAt = ++sequence;
}
static void ChangeMapObjSprite(LocalMapObject *object, u32 gfx) {
    if (object != &player) abort();
    changeSprite++; spriteTarget = gfx; object->gfx = (u16)gfx;
}
static void OverworldMount_ClearFollowerDecisionCooldown(void) { clearCooldown++; }
static void MapObject_PauseMovement(LocalMapObject *object) { object->flags |= MAPOBJECTFLAG_MOVEMENT_PAUSED; }
static void MapObject_UnpauseMovement(LocalMapObject *object) { object->flags &= ~MAPOBJECTFLAG_MOVEMENT_PAUSED; }
static void OverworldMount_ClearBoundaryState(void) { clearBoundary++; }
static BOOL OverworldMount_BindingMatchesFollower(FieldSystem *value, int *spawns) {
    if (value != &field || spawns != &sOverworldWildSpawnState) abort(); return bindingMatches;
}
static int Dispatch(OverworldMountActionCall *call) {
    if (call->version != 1 || call->size != sizeof(*call) || call->operation != 2
        || call->state != &sOverworldMountState) abort(); chainCancel++; return 1;
}
#define OVERWORLD_MOUNT_ACTION_ADAPTER_DISPATCH Dispatch
static void OverworldWalkMount_RebaseMotionTarget(OverworldMountRuntimeState *state) {
    if (state != &sOverworldMountState) abort(); rebase++;
}
static void OverworldMount_FinishCustomMotion(void) { finish++; }
static void OverworldMount_CancelSharedMotion(u8 reason) { (void)reason; sharedCancel++; }
static BOOL OverworldMount_FinalizeIsPending(void) { return finalizePending; }
static BOOL OverworldMount_ReleaseTerrainStream(void) { releaseStream++; return TRUE; }
static void OverworldMount_ResetMomentum(void) { resetMomentum++; }
static BOOL OverworldMount_ApplyPolicyCommand(int operation, const int *fingerprint) {
    if (operation != 3 || fingerprint != &sOverworldMountState.priorFollowerBehaviorFingerprint) abort();
    bindPolicy++; return TRUE;
}
/* Native EndSession is a fixed assembly state writer; no sprite work. */
static void OverworldMount_EndSession(u8 reason) {
    ended++; endedReason = reason; sOverworldMountState.snapshot.phase = 0;
    sOverworldMountState.fieldSystem = NULL;
}
'''

CASES = r'''
#define CHECK(value) do { if (!(value)) { fprintf(stderr, "line %d: %s\n", __LINE__, #value); return 1; } } while (0)
int main(int argc, char **argv) {
    CHECK(argc == 2);
    sOverworldMountState.fieldSystem = &field;
    sOverworldMountState.snapshot.phase = OVERWORLD_MOUNT_PHASE_RIDING;
    sOverworldMountState.snapshot.reserved = TRUE;
    sOverworldMountState.presentationAttached = TRUE;
    sOverworldMountState.walkEndState = 2;
    sOverworldMountState.pendingFieldStep = TRUE;
    sOverworldMountState.playerBaseFaceY = 100;
    sOverworldMountState.playerBaseUnk88Y = 200;
    sOverworldMountState.savedPlayerGfxId = 7;
    player.gfx = 178;
    player.flags = MAPOBJECTFLAG_UNK7 | MAPOBJECTFLAG_UNK14 | MAPOBJECTFLAG_UNK20;
    player.faceVec[0] = player.faceVec[1] = player.faceVec[2] = 30;
    player.unk88[1] = 90;
    avatar.unk0 = OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT | 8;
    follower.flags = MAPOBJECTFLAG_UNK31;
    follower.xCurr = 10; follower.hCurr = 20; follower.yCurr = 30;
    follower.faceVec[0] = follower.faceVec[1] = follower.faceVec[2] = 99;
    follower.unk88[0] = follower.unk88[1] = follower.unk88[2] = 88;
    u8 reason = OVERWORLD_MOUNT_CANCEL_OVERLAY_CLEANUP;
    if (!strcmp(argv[1], "normal")) reason = OVERWORLD_MOUNT_CANCEL_EXPLICIT;
    else if (!strcmp(argv[1], "map")) reason = OVERWORLD_MOUNT_CANCEL_MAP_CHANGE;
    else if (!strcmp(argv[1], "context")) reason = OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST;
    else if (!strcmp(argv[1], "preserve")) {
        reason = OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST;
        sOverworldMountState.preserveTransitionPrepared = TRUE;
    } else if (!strcmp(argv[1], "shadow")) sOverworldMountState.savedPlayerShadowSuppressed = TRUE;
    else if (!strcmp(argv[1], "active")) {
        sOverworldMountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_HOP;
        sOverworldMountState.motionStreamPreparing = TRUE;
    } else if (!strcmp(argv[1], "finalize")) finalizePending = TRUE;
    else if (!strcmp(argv[1], "missing-player")) hasPlayer = FALSE;
    else if (!strcmp(argv[1], "missing-follower")) hasFollower = FALSE;
    else if (!strcmp(argv[1], "unattached")) sOverworldMountState.presentationAttached = FALSE;
    else if (!strcmp(argv[1], "stale-policy")) bindingMatches = FALSE;
    else if (!strcmp(argv[1], "idle")) sOverworldMountState.snapshot.phase = OVERWORLD_MOUNT_PHASE_NONE;
    else CHECK(!strcmp(argv[1], "cleanup"));
    OverworldMount_Cancel(reason);
    if (!strcmp(argv[1], "idle") || !strcmp(argv[1], "preserve")) {
        CHECK(changeSprite == 0 && clearPresentation == 0 && setSprite == 0 && ended == 0);
        CHECK(clearPlayer == 0 && clearFollower == 0 && clearBoundary == 0 && chainCancel == 0);
        CHECK(sOverworldMountState.presentationAttached && avatar.unk0 == 9 && player.gfx == 178);
        return 0;
    }
    CHECK(ended == 1 && endedReason == reason && sOverworldMountState.snapshot.phase == 0);
    CHECK(sOverworldMountState.fieldSystem == NULL);
    CHECK(sOverworldMountState.walkEndState == 0 && sOverworldMountState.pendingFieldStep == 0);
    CHECK(chainCancel == bindingMatches && resetMomentum == bindingMatches && bindPolicy == bindingMatches);
    if (!strcmp(argv[1], "unattached")) {
        CHECK(clearPlayer == 0 && clearFollower == 0 && changeSprite == 0 && clearPresentation == 0);
        return 0;
    }
    CHECK(!sOverworldMountState.presentationAttached && clearBoundary == 1);
    if (hasPlayer) {
        CHECK(clearPlayer == 1 && resetAvatar == 1 && updateHeight == 1);
        CHECK(avatar.unk0 == 8 && !(player.flags & MAPOBJECTFLAG_UNK7));
        CHECK(player.faceVec[0] == 0 && player.faceVec[1] == 100 && player.faceVec[2] == 0);
        CHECK(player.unk88[1] == 200 && player.gfx == 7);
        CHECK(!!(player.flags & MAPOBJECTFLAG_UNK20) == sOverworldMountState.savedPlayerShadowSuppressed);
        if (reason == OVERWORLD_MOUNT_CANCEL_OVERLAY_CLEANUP) {
            CHECK(changeSprite == 0 && clearPresentation == 1 && setSprite == 1);
            CHECK(rendererOldGfx == 178 && clearedAt < setAt);
            CHECK(!(player.flags & MAPOBJECTFLAG_UNK14));
        } else CHECK(changeSprite == 1 && spriteTarget == 7 && clearPresentation == 0 && setSprite == 0);
    } else CHECK(clearPlayer == 0 && changeSprite == 0 && clearPresentation == 0 && setSprite == 0);
    if (hasFollower) {
        CHECK(clearFollower == 1 && clearCooldown == 1 && !(follower.flags & MAPOBJECTFLAG_UNK31));
        CHECK(follower.xPrev == 10 && follower.hPrev == 20 && follower.yPrev == 30);
        CHECK(follower.flags & MAPOBJECTFLAG_MOVEMENT_PAUSED);
        for (int i = 0; i < 3; ++i) CHECK(follower.faceVec[i] == 0 && follower.unk88[i] == 0);
    } else CHECK(clearFollower == 0 && clearCooldown == 0);
    CHECK(rebase == !strcmp(argv[1], "active") && finish == rebase && releaseStream == rebase);
    CHECK(sharedCancel == (rebase || !strcmp(argv[1], "finalize")));
    return 0;
}
'''


def program(source, *, unsafe_cleanup=False):
    detach = function_body(source, "OverworldMount_DetachPresentation")
    cancel = function_body(source, "OverworldMount_Cancel")
    restore = ""
    if "static void OverworldMount_RestorePlayerSprite" in source:
        body = function_body(source, "OverworldMount_RestorePlayerSprite")
        if unsafe_cleanup:
            old = "reason == OVERWORLD_MOUNT_CANCEL_OVERLAY_CLEANUP"
            if old not in body:
                raise ValueError("parent cleanup guard moved")
            body = body.replace(old, "FALSE", 1)
        restore = "\nstatic void OverworldMount_RestorePlayerSprite(LocalMapObject *player, u8 reason) {" + body + "}\n"
        unsafe_cleanup = False
    if unsafe_cleanup:
        old = "reason == OVERWORLD_MOUNT_CANCEL_OVERLAY_CLEANUP"
        if old not in detach:
            raise ValueError("parent cleanup guard moved")
        detach = detach.replace(old, "FALSE", 1)
    signature = re.search(r"OverworldMount_DetachPresentation\(([^)]*)\)\s*\{", source)
    if signature is None:
        raise ValueError("detach signature missing")
    return (STUBS + restore + "\nstatic void OverworldMount_DetachPresentation("
            + signature.group(1) + ") {" + detach + "}\n"
            + "static void OverworldMount_Cancel(u8 reason) {" + cancel + "}\n" + CASES)


class MountParentExitTests(unittest.TestCase):
    def compile(self, binary, *, unsafe_cleanup=False):
        source = Path(os.environ.get("MOUNT_SOURCE", SOURCE)).read_text()
        result = subprocess.run([*shlex.split(os.environ.get("HOST_CC", "cc")),
                                 "-std=c11", "-O0", "-x", "c", "-", "-o", str(binary)],
                                input=program(source, unsafe_cleanup=unsafe_cleanup),
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_actual_cleanup_and_normal_restore(self):
        with tempfile.TemporaryDirectory(prefix="mount-parent-exit-") as temporary:
            binary = Path(temporary) / "cleanup"
            self.compile(binary)
            for case in ("cleanup", "normal", "map", "context", "preserve", "shadow",
                         "active", "finalize", "missing-player", "missing-follower",
                         "unattached", "stale-policy", "idle"):
                with self.subTest(case=case):
                    result = subprocess.run([str(binary), case], text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_reject_new_sprite_task_at_parent_exit(self):
        with tempfile.TemporaryDirectory(prefix="mount-parent-exit-fault-") as temporary:
            binary = Path(temporary) / "cleanup"
            self.compile(binary, unsafe_cleanup=True)
            result = subprocess.run([str(binary), "cleanup"], text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("changeSprite == 0", result.stderr)


if __name__ == "__main__":
    unittest.main()
