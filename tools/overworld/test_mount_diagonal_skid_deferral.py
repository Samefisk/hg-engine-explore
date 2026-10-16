#!/usr/bin/env python3
"""Host check for mounted diagonal handling before the Walk reducer."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.verify_overworld_mount import function_body


ROOT = Path(__file__).resolve().parents[2]
GAIT = ROOT / "src/overworld_mount_chain_overlay/overworld_mount_gait.c"
MOUNT = ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c"


def harness_source() -> str:
    resolver = function_body(GAIT.read_text(), "OverworldMount_ResolveMountedDiagonalBody")
    preview_gate = function_body(MOUNT.read_text(), "OverworldMount_DeferRawDiagonalGeometry")
    input_start = function_body(MOUNT.read_text(), "OverworldMount_TryStartWalkFromInput")
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define PAD_PLUS_KEY_MASK 0xF0
#define OW_WILD_BEHAVIOR_LOCOMOTION_WALK 1
#define OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION 1
#define OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY 0
#define OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY 2
#define OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(mode) ((mode) != 0)
#define OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(mode) ((mode) < 2)
#define OVERWORLD_MOUNT_CONTACT_DIAGONAL_REJECT 1
#define OVERWORLD_MOUNT_DIRECTION_NONE 255
#define OVERWORLD_MOUNT_DIRECTION_NORTH_WEST 4
#define OVERWORLD_MOUNT_DIRECTION_SOUTH_EAST 7
#define OW_WILD_FOLLOWER_SLOT 1
#define OW_WILD_SPAWNER_SPOT_STATE_CHILL 0
#define OVERWORLD_ACTOR_WALK_POLICY_VERSION 1
#define OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT 16
#define OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_PENDING_INDEX 3
#define OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL 1
#define OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED 2
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_DEFER_STOP 1
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED 8
#define OVERWORLD_ACTOR_WALK_STEP_VALIDATE 1
#define OVERWORLD_ACTOR_WALK_STEP_SKID 2
#define OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP 2

typedef struct OverworldActorWalkPolicyCall {
    u16 version, size;
    const void *lane;
    u8 actorSlot, operation, direction, stepDirection, facingDirection;
    u8 laneState, flags, stepFlags, decision;
    u8 reserved[4];
} OverworldActorWalkPolicyCall;
typedef struct PolicyService {
    BOOL (*reduceWalk)(OverworldActorWalkPolicyCall *);
} PolicyService;
typedef struct ServiceEntry { PolicyService *policy; } ServiceEntry;
static BOOL SpyPreview(OverworldActorWalkPolicyCall *call);
static PolicyService policyService = {SpyPreview};
static ServiceEntry serviceEntry = {&policyService};
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY (&serviceEntry)

typedef struct LocalMapObject { u8 curFacing; } LocalMapObject;
typedef struct FIELD_PLAYER_AVATAR { LocalMapObject *mapObject; } FIELD_PLAYER_AVATAR;
typedef struct OverworldMountRuntimeState {
    struct { struct { u8 hopAllowNonCardinal, chillAction, walkOptions; } profile; } snapshot;
    u8 pendingStep, pendingDirection, motionStreamPreparing;
} OverworldMountRuntimeState;
static OverworldMountRuntimeState sOverworldMountState;
static unsigned filterCalls, rejectCalls, contactCalls, handleCalls;
static u8 actualDirection;
static u8 skidOnTurn;
static unsigned previewCalls;

static u8 OverworldWalk_DirectionFromKeys(u32 keys) { return keys == 0xA0 ? 6 : 0; }
static u8 OverworldWalk_DiagonalFacing(LocalMapObject *obj, u8 dir, u32 keys) {
    (void)obj; (void)dir; (void)keys; return 3;
}
static u32 OverworldWalk_DirectionKey(u8 dir) { return dir == 3 ? 0x80 : 0; }
static u16 Walk_DiagonalRejection(OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar, u8 direction) {
    (void)state; (void)avatar; (void)direction; return 2;
}
static u16 Walk_RejectDiagonalCandidate(OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar, u8 direction, u16 flags) {
    (void)state; (void)avatar; (void)direction; (void)flags;
    ++rejectCalls; return 1;
}
static u16 SpyContact(FIELD_PLAYER_AVATAR *avatar, u8 direction, u8 reason,
    OverworldMountRuntimeState *state) {
    (void)avatar; (void)direction; (void)reason; (void)state;
    ++contactCalls; return 0;
}
#define OVERWORLD_MOUNT_PLAYER_CONTACT_ENTRY SpyContact
static BOOL OverworldMount_CanControl(FIELD_PLAYER_AVATAR *avatar) {
    (void)avatar; return TRUE;
}
static BOOL SpyPreview(OverworldActorWalkPolicyCall *call) {
    ++previewCalls;
    if (call->operation != OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT
        || call->direction != 6 || call->actorSlot != OW_WILD_FOLLOWER_SLOT)
        return FALSE;
    call->reserved[OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_PENDING_INDEX] =
        sOverworldMountState.pendingStep;
    if (sOverworldMountState.pendingStep == 0 && skidOnTurn) {
        call->decision = OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP;
        call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_SKID;
    }
    return TRUE;
}
static void OverworldMount_FilterMovementInput(FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys, u32 *heldKeys) {
    (void)avatar; (void)newKeys; (void)heldKeys;
    ++filterCalls;
    actualDirection = sOverworldMountState.pendingStep == 1
        ? sOverworldMountState.pendingDirection : skidOnTurn ? 3 : 6;
}
static BOOL OverworldMount_TryHandleDiagonalWalk(FIELD_PLAYER_AVATAR *avatar,
    u32 newKeys, u32 heldKeys, BOOL advanceFirstFrame) {
    (void)avatar; (void)newKeys; (void)heldKeys; (void)advanceFirstFrame;
    ++handleCalls; return TRUE;
}
static u16 OverworldMount_ResolveMountedDiagonalBody(
    OverworldMountRuntimeState *state, FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys, u32 *heldKeys) {
''' + resolver + r'''
}
static u16 OverworldWalk_ResolveMountedDiagonal(
    OverworldMountRuntimeState *state, FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys, u32 *heldKeys) {
    return OverworldMount_ResolveMountedDiagonalBody(state, avatar, newKeys, heldKeys);
}
static BOOL OverworldMount_DeferRawDiagonalGeometry(u32 keys) {
''' + preview_gate + r'''
}
static BOOL OverworldMount_TryStartWalkFromInput(
    FIELD_PLAYER_AVATAR *avatar, u32 *newKeys, u32 *heldKeys,
    BOOL advanceFirstFrame) {
''' + input_start + r'''
}
int main(int argc, char **argv) {
    LocalMapObject mapObject = {3};
    FIELD_PLAYER_AVATAR avatar = {&mapObject};
    u32 newKeys = 0, heldKeys = 0xA0;
    int scenario = argc > 1 ? atoi(argv[1]) : 0;
    sOverworldMountState.snapshot.profile.hopAllowNonCardinal = 1;
    sOverworldMountState.snapshot.profile.chillAction = 1;
    actualDirection = 255;
    if (scenario == 1) skidOnTurn = 1;
    if (scenario == 2) {
        sOverworldMountState.pendingStep = 1;
        sOverworldMountState.pendingDirection = 3;
    }
    if (scenario == 3) sOverworldMountState.pendingStep = 2;
    if (scenario == 4) sOverworldMountState.motionStreamPreparing = 1;
    printf("%d ", OverworldMount_TryStartWalkFromInput(
        &avatar, &newKeys, &heldKeys, FALSE));
    printf("%u %u %u %u %u\n", filterCalls, rejectCalls,
        contactCalls, handleCalls, actualDirection);
    return 0;
}
'''


class MountedDiagonalSkidDeferral(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        source = Path(cls._tmp.name) / "diagonal.c"
        cls.binary = Path(cls._tmp.name) / "diagonal"
        source.write_text(harness_source())
        subprocess.run(
            ["cc", "-std=c99", "-O0", "-Wall", "-Wextra", "-Werror",
             str(source), "-o", str(cls.binary)], check=True, capture_output=True,
            text=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def result(self, scenario: int) -> tuple[int, ...]:
        run = subprocess.run([str(self.binary), str(scenario)], check=True,
                             capture_output=True, text=True)
        return tuple(map(int, run.stdout.split()))

    def test_clear_old_heading_skid_ignores_blocked_raw_diagonal(self) -> None:
        self.assertEqual(self.result(1), (1, 1, 0, 0, 1, 3))

    def test_pending_skid_uses_saved_heading_before_raw_diagonal(self) -> None:
        self.assertEqual(self.result(2), (1, 1, 0, 0, 1, 3))

    def test_ordinary_blocked_diagonal_still_rejects_candidate(self) -> None:
        self.assertEqual(self.result(0), (1, 0, 1, 1, 0, 255))

    def test_accepted_pending_step_reaches_walk_handoff(self) -> None:
        self.assertEqual(self.result(3), (1, 1, 0, 0, 1, 6))

    def test_stream_wait_reaches_walk_handoff(self) -> None:
        self.assertEqual(self.result(4), (1, 1, 0, 0, 1, 6))


if __name__ == "__main__":
    unittest.main()
