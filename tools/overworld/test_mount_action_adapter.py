"""Focused host checks for mounted action adapter target planning."""

from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile
import unittest

from scripts.verify_overworld_mount import function_body


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_mount_action_overlay/overworld_mount_action_overlay.c"
HEADER = ROOT / "include/overworld_mount_action_adapter.h"
WILD_SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
MOUNT_SOURCE = ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c"


STUBS = r'''
#include <stdio.h>
typedef unsigned char u8;
typedef unsigned short u16;
typedef short s16;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OVERWORLD_MOUNT_CHAIN_FORWARD_DISTANCE 2
#define OVERWORLD_MOUNT_ACTION_STRICT_DIAGONAL_MARKER 0x8000
#define OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION 1
#define OW_WILD_FOLLOWER_SLOT 7
typedef struct {
    struct { struct { u16 chillAllowedTerrainMask; } profile; } snapshot;
    void *fieldSystem;
    s16 motionStartX, motionStartY, motionTargetX, motionTargetY;
} OverworldMountRuntimeState;
typedef struct {
    u8 direction;
    OverworldMountRuntimeState *state;
} OverworldMountActionCall;
static int calls, allowLanding;
static int seenX, seenY, seenFinalX, seenFinalY;
static u16 seenMask;
static BOOL Validate(u16 version, u8 slot, void *fieldSystem, u16 mask,
    int x, int y, int finalX, int finalY) {
    if (version != OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION
        || slot != OW_WILD_FOLLOWER_SLOT || fieldSystem == 0) return FALSE;
    calls++;
    seenX = x; seenY = y; seenFinalX = finalX; seenFinalY = finalY;
    seenMask = mask;
    return allowLanding;
}
static struct { BOOL (*validateHopLanding)(u16, u8, void *, u16,
    int, int, int, int); } entry = { Validate };
#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY (&entry)
static int OverworldWalkDirectionPolicy_DeltaX(u8 direction) {
    static const signed char values[8] = {0, 0, -1, 1, -1, 1, -1, 1};
    return direction < 8 ? values[direction] : 0;
}
static int OverworldWalkDirectionPolicy_DeltaY(u8 direction) {
    static const signed char values[8] = {-1, 1, 0, 0, -1, -1, 1, 1};
    return direction < 8 ? values[direction] : 0;
}
'''


CASES = r'''
#define CHECK(value) do { if (!(value)) { \
    fprintf(stderr, "line %d: %s\n", __LINE__, #value); return 1; \
} } while (0)
int main(void) {
    OverworldMountRuntimeState state = {0};
    OverworldMountActionCall call = {0};
    int field;
    state.fieldSystem = &field;
    state.snapshot.profile.chillAllowedTerrainMask = 0x1234;
    state.motionStartX = 10;
    state.motionStartY = 20;
    call.state = &state;
    allowLanding = TRUE;

    call.direction = 3;
    CHECK(OverworldMountAction_ChainForwardTarget(&call));
    CHECK(state.motionTargetX == 12 && state.motionTargetY == 20);
    CHECK(calls == 1 && seenX == 12 && seenY == 20);
    CHECK(seenFinalX == 12 && seenFinalY == 20);
    CHECK(seenMask == (u16)(0x1234 | 0x8000));

    call.direction = 5;
    CHECK(OverworldMountAction_ChainForwardTarget(&call));
    CHECK(state.motionTargetX == 12 && state.motionTargetY == 18);
    CHECK(calls == 2 && seenX == 12 && seenY == 18);
    CHECK(seenFinalX == 12 && seenFinalY == 18);

    allowLanding = FALSE;
    state.motionTargetX = 77;
    state.motionTargetY = 88;
    call.direction = 3;
    CHECK(!OverworldMountAction_ChainForwardTarget(&call));
    CHECK(calls == 3);
    CHECK(state.motionTargetX == 77 && state.motionTargetY == 88);

    call.direction = 8;
    CHECK(!OverworldMountAction_ChainForwardTarget(&call));
    CHECK(calls == 3);
    return 0;
}
'''


class MountActionAdapterTests(unittest.TestCase):
    def test_cancel_does_not_clear_a_replacement_follower_chain(self):
        body = function_body(MOUNT_SOURCE.read_text(), "OverworldMount_Cancel")
        identity_check = body.index("restorePriorPolicy = OverworldMount_BindingMatchesFollower")
        guarded_cancel = body.index("if (restorePriorPolicy) {", identity_check)
        cancel = body.index("OVERWORLD_MOUNT_ACTION_CANCEL_CHAIN", guarded_cancel)
        guard_end = body.index("\n    }", guarded_cancel)
        guarded_reset = body.index("if (restorePriorPolicy) {", guard_end)
        reset = body.index("OverworldMount_ResetMomentum();", guarded_reset)
        reset_guard_end = body.index("\n    }", guarded_reset)
        self.assertLess(identity_check, guarded_cancel)
        self.assertLess(guarded_cancel, cancel)
        self.assertLess(cancel, guard_end)
        self.assertLess(guarded_reset, reset)
        self.assertLess(reset, reset_guard_end)

    def test_stream_rejection_is_terminal_not_an_unbounded_retry(self):
        body = function_body(SOURCE.read_text(), "OverworldMountAction_StartMotion")
        query = body.index("OVERWORLD_FIELD_TERRAIN_STREAM_QUERY_IDLE")
        begin = body.index("targetBaseY =", query)
        classification = body[query:begin]
        self.assertIn(
            "streamResult == OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED\n"
            "                ? OVERWORLD_MOUNT_ACTION_FINAL\n"
            "                : OVERWORLD_MOUNT_ACTION_RETRY;",
            classification)

    def test_forward_target_is_exact_and_has_no_fallback(self):
        source = SOURCE.read_text()
        program = (STUBS
            + "static u8 OverworldMountAction_ChainForwardTarget("
              "OverworldMountActionCall *call) {"
            + function_body(source, "OverworldMountAction_ChainForwardTarget")
            + "}\n"
            + CASES)
        with tempfile.TemporaryDirectory(prefix="mount-action-") as temporary:
            binary = Path(temporary) / "forward-target"
            compile_result = subprocess.run(
                [*shlex.split(os.environ.get("HOST_CC", "cc")),
                 "-std=c11", "-O0", "-x", "c", "-", "-o", str(binary)],
                input=program, text=True, capture_output=True)
            self.assertEqual(compile_result.returncode, 0,
                             compile_result.stdout + compile_result.stderr)
            run_result = subprocess.run([str(binary)], capture_output=True,
                                        text=True)
            self.assertEqual(run_result.returncode, 0,
                             run_result.stdout + run_result.stderr)

    def test_mount_and_wild_strict_diagonal_markers_match(self):
        mount = re.search(
            r"OVERWORLD_MOUNT_ACTION_STRICT_DIAGONAL_MARKER\s+(0x[0-9A-Fa-f]+)",
            HEADER.read_text())
        wild = re.search(
            r"OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER\s+(0x[0-9A-Fa-f]+)",
            WILD_SOURCE.read_text())
        self.assertIsNotNone(mount)
        self.assertIsNotNone(wild)
        self.assertEqual(int(mount.group(1), 0), int(wild.group(1), 0))


if __name__ == "__main__":
    unittest.main()
