#!/usr/bin/env python3
"""Check the actual diagonal gate sends blocked recovery to Crash policy."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MOUNT = ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c"


def strict_diagonal_branch() -> str:
    source = MOUNT.read_text()
    anchor = "if (requestedDirection >= OVERWORLD_MOUNT_DIRECTION_NORTH_WEST\n        && !OverworldWalk_StrictDiagonalAllowed("
    start = source.index(anchor)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError("strict diagonal branch is incomplete")


def harness() -> str:
    return r'''
#include <stdio.h>
typedef unsigned char u8;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OVERWORLD_MOUNT_DIRECTION_NORTH_WEST 4
#define OVERWORLD_MOUNT_CONTACT_DIAGONAL_REJECT 1
#define OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX 5
#define OVERWORLD_ACTOR_WALK_STEP_POST_SKID 0x20
typedef struct OverworldMountRuntimeState { u8 reservedPolicyState[9]; }
    OverworldMountRuntimeState;
typedef struct FIELD_PLAYER_AVATAR { int unused; } FIELD_PLAYER_AVATAR;
static OverworldMountRuntimeState sOverworldMountState;
static unsigned contacts, finishes, crashes;
static BOOL OverworldWalk_StrictDiagonalAllowed(
    OverworldMountRuntimeState *state, FIELD_PLAYER_AVATAR *avatar,
    u8 direction) {
    (void)state; (void)avatar; (void)direction; return FALSE;
}
static BOOL contact(FIELD_PLAYER_AVATAR *avatar, u8 direction, u8 reason,
    OverworldMountRuntimeState *state) {
    (void)avatar; (void)direction; (void)reason; (void)state;
    ++contacts; return TRUE;
}
#define OVERWORLD_MOUNT_PLAYER_CONTACT_ENTRY contact
static BOOL OverworldMount_ApplyWalkPolicy(FIELD_PLAYER_AVATAR *avatar,
    BOOL started, BOOL crashOnBlocked) {
    (void)avatar; (void)started; ++finishes; crashes += crashOnBlocked;
    return TRUE;
}
static BOOL strictGate(FIELD_PLAYER_AVATAR *avatar, u8 requestedDirection) {
''' + strict_diagonal_branch() + r'''
    return FALSE;
}
int main(void) {
    FIELD_PLAYER_AVATAR avatar = {0};
    sOverworldMountState.reservedPolicyState[
        OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX] =
        OVERWORLD_ACTOR_WALK_STEP_POST_SKID;
    if (!strictGate(&avatar, 6) || contacts != 1 || finishes != 1
        || crashes != 1) return 1;
    sOverworldMountState.reservedPolicyState[
        OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX] = 1;
    if (!strictGate(&avatar, 6) || contacts != 2 || finishes != 2
        || crashes != 1) return 2;
    puts("blocked post-skid diagonal requests Crash; ordinary reject does not");
    return 0;
}
'''


class MountedDiagonalRecovery(unittest.TestCase):
    def test_post_skid_block_requests_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "recovery.c"
            binary = Path(temp) / "recovery"
            source.write_text(harness())
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            run = subprocess.run([str(binary)], check=True,
                                 capture_output=True, text=True)
            self.assertIn("requests Crash", run.stdout)


if __name__ == "__main__":
    unittest.main()
