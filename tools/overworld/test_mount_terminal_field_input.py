"""Host checks of the real mount field-input boundary, not ROM acceptance."""
from pathlib import Path
import os
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
typedef int s32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define PAD_PLUS_KEY_MASK 1u
#define OVERWORLD_MOUNT_PHASE_RIDING 3
#define OVERWORLD_MOUNT_MOTION_WALK 1
#define OVERWORLD_MOUNT_MOTION_HOP 2
#define OW_WILD_BEHAVIOR_LOCOMOTION_WALK 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP 2
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT 6
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_NO_FLICKER 9
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE 10
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE_NO_FLICKER 11
#define OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(locomotion) \
    ((locomotion) == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT \
        || (locomotion) == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_NO_FLICKER \
        || (locomotion) == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE \
        || (locomotion) == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE_NO_FLICKER)
#define OVERWORLD_MOUNT_BOUNDARY_FINALIZE_PENDING 1
#define OVERWORLD_MOUNT_BOUNDARY_FINAL_WRITES_DONE 2
#define OVERWORLD_MOUNT_WALK_END_NONE 0
#define OVERWORLD_MOUNT_WALK_END_PENDING 1
#define OVERWORLD_MOUNT_WALK_END_CONTINUATION_READY 2
#define OVERWORLD_MOUNT_WALK_END_STOP 3
#define OVERWORLD_MOUNT_FIELD_INPUT_END_MOVEMENT 2
#define OVERWORLD_MOUNT_FIELD_INPUT_SIGN 32
#define OVERWORLD_MOUNT_FIELD_INPUT_MAP_TRANSITION 64
#define OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT 128
#define OVERWORLD_ACTOR_SYSTEM_ABI_VERSION 2
#define OVERWORLD_ACTOR_INSPECT_WORLD_GATE 6
#define OVERWORLD_ACTOR_WORLD_GATE_WARP 0
#define OVERWORLD_ACTOR_RESULT_OK 0
#define OVERWORLD_ACTOR_WALK_PENDING_CHAIN 1
#define OVERWORLD_MOTION_PHASE_IDLE 0
#define OVERWORLD_ACTOR_WALK_POLICY_CHAIN_COMMIT 1
#define OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING 2
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED 1
#define OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT 7
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD 7
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE 1
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS 5
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE 6
#define OVERWORLD_MOUNT_ACTION_FINAL 0
typedef struct { int unused; } LocalMapObject;
typedef struct { LocalMapObject *mapObject; } FIELD_PLAYER_AVATAR;
typedef struct { FIELD_PLAYER_AVATAR *playerAvatar; } FieldSystem;
typedef struct { unsigned flags; } OverworldMountFieldInput;
typedef struct { int version, size, kind, index; } OverworldActorQuery;
typedef struct { int unused; } OverworldActorSnapshot;
typedef struct {
    struct { struct { int chillAction; } profile; int phase, motionMode; } snapshot;
    FieldSystem *fieldSystem;
    int walkEndState, presentationAttached, pendingFieldStep, directionInputHeld;
    int bufferedTogglePending;
    u16 motionCooldown;
    int reservedPolicyState[4];
} OverworldMountRuntimeState;
typedef struct {
    int pendingStep, motionPhase, chainPauseAction, chainPauseTicks;
    struct { int direction, speed; } walkMomentum;
} OverworldActorPolicyView;
typedef struct { int unused; } OverworldActorWalkPolicyCall;
static OverworldMountRuntimeState sOverworldMountState;
#define OVERWORLD_MOUNT_BOUNDARY_FLAGS_INDEX 0
#define OVERWORLD_MOUNT_BOUNDARY_MOTION_INDEX 3
#define boundary_flags sOverworldMountState.reservedPolicyState[0]
#define boundary_motion sOverworldMountState.reservedPolicyState[3]
#define OVERWORLD_MOUNT_BOUNDARY_FLAGS boundary_flags
#define OVERWORLD_MOUNT_BOUNDARY_MOTION boundary_motion
static int ends, commits, stock_steps, drained, successors, consumed, resets, ready = 1;
static int policy_inputs, stop_skids, stock_controls, motion_updates;
static int walk_momentum_active = 1, stop_pending, stop_proposal;
static int first_frame_advance;
static LocalMapObject player;
static FIELD_PLAYER_AVATAR avatar = {&player};
static FieldSystem field = {&avatar}, other_field = {&avatar};
static BOOL OverworldMount_FinalizeIsPending(void) {
    return boundary_flags & OVERWORLD_MOUNT_BOUNDARY_FINALIZE_PENDING;
}
static BOOL OverworldMount_HasCurrentPlayer(void) {
    return sOverworldMountState.fieldSystem == &field && field.playerAvatar
        && field.playerAvatar->mapObject == &player;
}
static void OverworldMount_DrainLandStream(void) { drained++; }
static BOOL OverworldMount_CompletePendingStep(FIELD_PLAYER_AVATAR *value) {
    if (value != &avatar || sOverworldMountState.walkEndState != OVERWORLD_MOUNT_WALK_END_PENDING)
        return FALSE;
    ends++;
    if (!ready) return FALSE;
    commits++;
    boundary_flags = 0;
    sOverworldMountState.walkEndState = OVERWORLD_MOUNT_WALK_END_CONTINUATION_READY;
    return TRUE;
}
static int inspect(const OverworldActorQuery *query, OverworldActorSnapshot *snapshot) {
    (void)query; (void)snapshot;
    return commits ? OVERWORLD_ACTOR_RESULT_OK : 1;
}
static struct { int (*inspect)(const OverworldActorQuery *, OverworldActorSnapshot *); } entry = {inspect};
#define OVERWORLD_ACTOR_SYSTEM_ENTRY (&entry)
static BOOL StockStep(FieldSystem *value) { (void)value; stock_steps++; return consumed; }
#define OVERWORLD_WILD_PLAYER_STEP_HANDLER_ADDR StockStep
static BOOL OverworldMount_PlayerStepBridge(FieldSystem *);
static int StockFieldInput(OverworldMountFieldInput *input, FieldSystem *value) {
    if (input && (input->flags & OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT))
        return OverworldMount_PlayerStepBridge(value);
    return 0;
}
static void OverworldMount_ResetMomentum(void) { resets++; }
static BOOL OverworldActorPolicy_Inspect(int slot, OverworldActorPolicyView *policy) {
    (void)slot; (void)policy; return FALSE;
}
static BOOL Chain_Reduce(OverworldMountRuntimeState *state, u8 operation, u8 flags,
                         u8 chainAction, u8 chainTicks,
                         OverworldActorWalkPolicyCall *call) {
    (void)state; (void)operation; (void)flags; (void)chainAction;
    (void)chainTicks; (void)call; return FALSE;
}
static BOOL Chain_ActionActive(const OverworldMountRuntimeState *state,
                               const OverworldActorPolicyView *policy) {
    (void)state; (void)policy; return FALSE;
}
static u8 Chain_StartAdapterAction(OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *value, const OverworldActorPolicyView *policy, u8 action) {
    (void)state; (void)value; (void)policy; (void)action;
    return OVERWORLD_MOUNT_ACTION_FINAL;
}
static u8 Chain_StartForwardHop(OverworldMountRuntimeState *state, FIELD_PLAYER_AVATAR *value,
                                const OverworldActorPolicyView *policy) {
    (void)state; (void)value; (void)policy; return 0;
}
static void OverworldMount_FilterMovementInput(FIELD_PLAYER_AVATAR *value,
                                                u32 *newKeys, u32 *heldKeys) {
    (void)value;
    if (stop_proposal) {
        *heldKeys |= PAD_PLUS_KEY_MASK;
        return;
    }
    if (((*newKeys | *heldKeys) & PAD_PLUS_KEY_MASK) != 0) return;
    policy_inputs++;
    if (!walk_momentum_active) return;
    if (!stop_pending) {
        stop_pending = 1;
        return;
    }
    stop_pending = 0;
    stop_proposal = 1;
    *heldKeys |= PAD_PLUS_KEY_MASK;
}
static BOOL OverworldMount_TryStartWalkFromInput(FIELD_PLAYER_AVATAR *value, u32 *newKeys, u32 *heldKeys, BOOL first) {
    OverworldMount_FilterMovementInput(value, newKeys, heldKeys);
    if (((*newKeys | *heldKeys) & PAD_PLUS_KEY_MASK) == 0) return FALSE;
    first_frame_advance = first;
    successors++;
    if (stop_proposal) {
        stop_proposal = 0;
        stop_skids++;
    }
    return TRUE;
}
static void OverworldMount_UpdateCustomMotion(void) { motion_updates++; }
static void OverworldMount_SyncPresentation(void) {}
static BOOL OverworldMount_HandleCustomInput(FIELD_PLAYER_AVATAR *value, u32 *newKeys, u32 *heldKeys) {
    (void)value; (void)newKeys; (void)heldKeys; return FALSE;
}
static void PlayerAvatar_MoveControl(FIELD_PLAYER_AVATAR *value, u32 p1, s32 direction, u32 newKeys, u32 heldKeys, u32 p5) {
    (void)value; (void)p1; (void)direction; (void)newKeys; (void)heldKeys; (void)p5; stock_controls++;
}
'''

CASES = r'''
#define CHECK(value) do { if (!(value)) { fprintf(stderr, "line %d: %s\n", __LINE__, #value); return 1; } } while (0)
int main(int argc, char **argv) {
    CHECK(argc == 2);
    sOverworldMountState.snapshot.phase = OVERWORLD_MOUNT_PHASE_RIDING;
    sOverworldMountState.fieldSystem = &field;
    sOverworldMountState.presentationAttached = TRUE;
    sOverworldMountState.directionInputHeld = TRUE;
    sOverworldMountState.snapshot.profile.chillAction = OW_WILD_BEHAVIOR_LOCOMOTION_WALK;
    boundary_flags = OVERWORLD_MOUNT_BOUNDARY_FINALIZE_PENDING | OVERWORLD_MOUNT_BOUNDARY_FINAL_WRITES_DONE;
    boundary_motion = OVERWORLD_MOUNT_MOTION_WALK;
    OverworldMountFieldInput input = {OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT | OVERWORLD_MOUNT_FIELD_INPUT_END_MOVEMENT};
    if (!strcmp(argv[1], "terminal")) {
        OverworldMount_FieldInputProcess(&input, &field);
        CHECK(ends == 1 && commits == 1 && drained == 1 && stock_steps == 1);
        CHECK(sOverworldMountState.pendingFieldStep == 0);
        CHECK(input.flags & OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT);
        OverworldMount_FieldInputProcess(&input, &field);
        OverworldMount_PlayerStepBridge(&field);
        CHECK(ends == 1 && commits == 1 && drained == 1);
    } else if (!strcmp(argv[1], "delayed")) {
        ready = 0;
        OverworldMount_FieldInputProcess(&input, &field);
        CHECK(ends == 1 && commits == 0 && stock_steps == 0 && input.flags == 0);
        CHECK(sOverworldMountState.pendingFieldStep == 1);
        input.flags = OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT | OVERWORLD_MOUNT_FIELD_INPUT_END_MOVEMENT;
        OverworldMount_FieldInputProcess(&input, &field);
        CHECK(ends == 1 && drained == 1 && commits == 0);
        ready = 1;
        CHECK(OverworldMount_CompletePendingStep(&avatar));
        CHECK(commits == 1);
        OverworldMount_ChainControl(&avatar, 0, 0, 0, 1, 0);
        CHECK(successors == 0);
        CHECK(sOverworldMountState.walkEndState == OVERWORLD_MOUNT_WALK_END_CONTINUATION_READY);
        input.flags = 0;
        OverworldMount_FieldInputProcess(&input, &other_field);
        CHECK(stock_steps == 0 && sOverworldMountState.pendingFieldStep == 1);
        input.flags = 0;
        OverworldMount_FieldInputProcess(&input, &field);
        CHECK(stock_steps == 1 && sOverworldMountState.pendingFieldStep == 0);
        CHECK(ends == 2 && drained == 1);
        input.flags = 0;
        OverworldMount_FieldInputProcess(&input, &field);
        CHECK(stock_steps == 1 && commits == 1 && drained == 1);
        OverworldMount_ChainControl(&avatar, 0, 0, 0, 1, 0);
        CHECK(successors == 1);
        /* Field input precedes this frame's actor tick. No extra preload. */
        CHECK(first_frame_advance == FALSE);
    } else if (!strcmp(argv[1], "consumed")) {
        consumed = TRUE;
        CHECK(OverworldMount_FieldInputProcess(&input, &field) == TRUE);
        CHECK(commits == 1 && stock_steps == 1 && ends == 1 && drained == 1);
        CHECK(sOverworldMountState.pendingFieldStep == 0);
        CHECK(sOverworldMountState.walkEndState == OVERWORLD_MOUNT_WALK_END_STOP);
    } else if (!strcmp(argv[1], "fresh-direction-at-terminal")) {
        /* The tick has not sampled this frame's key yet. */
        sOverworldMountState.directionInputHeld = FALSE;
        sOverworldMountState.walkEndState = OVERWORLD_MOUNT_WALK_END_CONTINUATION_READY;
        OverworldMount_ChainControl(&avatar, 0, 0, 0, PAD_PLUS_KEY_MASK, 0);
        CHECK(successors == 1 && resets == 0);
        CHECK(motion_updates == 1);
        CHECK(sOverworldMountState.walkEndState == OVERWORLD_MOUNT_WALK_END_NONE);
        CHECK(first_frame_advance == FALSE);
    } else if (!strcmp(argv[1], "released-at-terminal")) {
        /* The tick still remembers yesterday's key. Current NONE must enter
         * the reducer and start the authored stop skid, never reset it. */
        sOverworldMountState.directionInputHeld = TRUE;
        sOverworldMountState.walkEndState = OVERWORLD_MOUNT_WALK_END_CONTINUATION_READY;
        OverworldMount_ChainControl(&avatar, 0, 0, 0, 0, 0);
        CHECK(policy_inputs == 1 && stop_pending == 1 && stop_skids == 0);
        CHECK(successors == 0 && resets == 0 && stock_controls == 0);
        CHECK(sOverworldMountState.walkEndState == OVERWORLD_MOUNT_WALK_END_NONE);
        OverworldMount_ChainControl(&avatar, 0, 0, 0, 0, 0);
        CHECK(policy_inputs == 2 && stop_pending == 0 && stop_skids == 1);
        CHECK(successors == 1 && resets == 0 && stock_controls == 0);
    } else if (!strcmp(argv[1], "stop-skid-continuation-at-terminal")) {
        /* COMMIT already proposed the next automatic skid tile. NONE must
         * start it in this same control pass, without an idle frame. */
        stop_proposal = 1;
        sOverworldMountState.walkEndState = OVERWORLD_MOUNT_WALK_END_CONTINUATION_READY;
        OverworldMount_ChainControl(&avatar, 0, 0, 0, 0, 0);
        CHECK(policy_inputs == 0 && stop_skids == 1);
        CHECK(successors == 1 && resets == 0 && stock_controls == 0);
    } else if (!strcmp(argv[1], "released-without-momentum")) {
        /* NONE still reaches policy. With no momentum it starts no skid and
         * does not call the out-of-band reset helper. */
        walk_momentum_active = 0;
        sOverworldMountState.walkEndState = OVERWORLD_MOUNT_WALK_END_CONTINUATION_READY;
        OverworldMount_ChainControl(&avatar, 0, 0, 0, 0, 0);
        CHECK(policy_inputs == 1 && stop_skids == 0);
        CHECK(successors == 0 && resets == 0 && stock_controls == 0);
        OverworldMount_ChainControl(&avatar, 0, 0, 0, 0, 0);
        CHECK(policy_inputs == 2 && stop_skids == 0);
        CHECK(successors == 0 && resets == 0 && stock_controls == 1);
    } else if (!strcmp(argv[1], "stale-bridge")) {
        OverworldMount_PlayerStepBridge(&other_field);
        CHECK(ends == 0 && commits == 0 && drained == 0);
    } else if (!strcmp(argv[1], "idle-walk")) {
        commits = 1;
        boundary_flags = 0;
        CHECK(OverworldMount_FieldInputProcess(&input, &field) == FALSE);
        CHECK(input.flags & OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT);
        CHECK(stock_steps == 1 && ends == 0 && drained == 0);
    } else if (!strcmp(argv[1], "idle-hop")
            || !strcmp(argv[1], "idle-teleport")
            || !strcmp(argv[1], "idle-teleport-no-flicker")
            || !strcmp(argv[1], "idle-teleport-per-tile")
            || !strcmp(argv[1], "idle-teleport-per-tile-no-flicker")) {
        commits = 1;
        boundary_flags = 0;
        if (!strcmp(argv[1], "idle-hop"))
            sOverworldMountState.snapshot.profile.chillAction = OW_WILD_BEHAVIOR_LOCOMOTION_HOP;
        else if (!strcmp(argv[1], "idle-teleport"))
            sOverworldMountState.snapshot.profile.chillAction = OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT;
        else if (!strcmp(argv[1], "idle-teleport-no-flicker"))
            sOverworldMountState.snapshot.profile.chillAction = OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_NO_FLICKER;
        else if (!strcmp(argv[1], "idle-teleport-per-tile"))
            sOverworldMountState.snapshot.profile.chillAction = OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE;
        else
            sOverworldMountState.snapshot.profile.chillAction = OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE_NO_FLICKER;
        CHECK(OverworldMount_FieldInputProcess(&input, &field) == FALSE);
        CHECK(input.flags == 0);
        CHECK(stock_steps == 0 && ends == 0 && drained == 0);
    } else {
        FieldSystem *current = &field;
        if (!strcmp(argv[1], "mid-motion")) boundary_flags = 0;
        else if (!strcmp(argv[1], "missing-final-writes")) boundary_flags = OVERWORLD_MOUNT_BOUNDARY_FINALIZE_PENDING;
        else if (!strcmp(argv[1], "hop")) boundary_motion = OVERWORLD_MOUNT_MOTION_HOP;
        else if (!strcmp(argv[1], "stale-field")) current = &other_field;
        else if (!strcmp(argv[1], "missing-player")) field.playerAvatar = NULL;
        else if (!strcmp(argv[1], "not-riding")) sOverworldMountState.snapshot.phase = 0;
        else if (!strcmp(argv[1], "no-movement")) input.flags = OVERWORLD_MOUNT_FIELD_INPUT_END_MOVEMENT;
        else if (!strcmp(argv[1], "no-end")) input.flags = OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT;
        else return 2;
        OverworldMount_FieldInputProcess(&input, current);
        CHECK(ends == 0 && commits == 0 && drained == 0 && stock_steps == 0);
    }
    return 0;
}
'''


def program(*, remove_terminal_handoff=False, remove_control_guard=False,
            restore_prior_frame_gate=False):
    source = SOURCE.read_text()
    chain_source = (
        ROOT / "src/overworld_mount_chain_overlay/overworld_mount_chain_overlay.c"
    ).read_text()
    bridge = function_body(source, "OverworldMount_PlayerStepBridge")
    field_input = function_body(source, "OverworldMount_FieldInputProcess")
    process_input = function_body(
        (ROOT / "src/field/overworld_mount_field_input.c").read_text(),
        "OverworldMount_ProcessFieldInput")
    retry = function_body(source, "OverworldMount_OnPlayerStep")
    player_control = function_body(source, "OverworldMount_ProcessPlayerControl")
    chain_control = function_body(chain_source, "OverworldMount_ChainControl")
    if remove_terminal_handoff:
        process_input = process_input.replace(
            "OVERWORLD_MOUNT_OVERLAY_ENTRY->onPlayerStep()",
            "FALSE /* omitted terminal handoff */")
    if remove_control_guard:
        guard = "if (state->pendingFieldStep) {\n        return;\n    }"
        if guard not in chain_control:
            raise ValueError("mounted chain deferred-step guard moved")
        chain_control = chain_control.replace(guard, "/* omitted deferred-step guard */", 1)
    if restore_prior_frame_gate:
        current = "if (((newKeys | heldKeys) & PAD_PLUS_KEY_MASK) == 0)"
        if current not in player_control:
            raise ValueError("mounted current-frame direction gate moved")
        player_control = player_control.replace(
            current, "if (!sOverworldMountState.directionInputHeld)", 1)
    fixed_state = "(OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR"
    if fixed_state not in chain_control:
        raise ValueError("mounted chain state binding moved")
    chain_control = chain_control.replace(fixed_state, "&sOverworldMountState", 1)
    # Replace fixed host-unusable addresses. The tested decisions and calls
    # still come directly from the production function bodies.
    process_input = process_input.replace("0x021E6AF5", "StockFieldInput")
    process_input = process_input.replace(
        "OVERWORLD_MOUNT_OVERLAY_ENTRY->onPlayerStep()", "OverworldMount_OnPlayerStep()")
    field_input = field_input.replace("OVERWORLD_MOUNT_FIELD_INPUT_HOST", "OverworldMount_ProcessFieldInput")
    return STUBS + "\nstatic BOOL OverworldMount_PlayerStepBridge(FieldSystem *fieldSystem) {" + bridge + "}\n" \
        + "static void OverworldMount_OnPlayerStep(void) {" + retry + "}\n" \
        + "static int OverworldMount_ProcessFieldInput(OverworldMountFieldInput *fieldInput, FieldSystem *fieldSystem, OverworldMountRuntimeState *state, BOOL currentMount) {" \
        + process_input + "}\n" \
        + "static int OverworldMount_FieldInputProcess(OverworldMountFieldInput *fieldInput, FieldSystem *fieldSystem) {" \
        + field_input + "}\n" \
        + "static void OverworldMount_ProcessPlayerControl(FIELD_PLAYER_AVATAR *avatar, u32 param1, s32 direction, u32 newKeys, u32 heldKeys, u32 param5) {" \
        + player_control + "}\n" \
        + "static void OverworldMount_ChainControl(FIELD_PLAYER_AVATAR *avatar, u32 param1, s32 direction, u32 newKeys, u32 heldKeys, u32 param5) {" \
        + chain_control + "}\n" + CASES


class MountTerminalFieldInputTests(unittest.TestCase):
    def compile(self, binary, *, remove_terminal_handoff=False,
                remove_control_guard=False, restore_prior_frame_gate=False):
        result = subprocess.run([*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O0",
                                 "-x", "c", "-", "-o", str(binary)],
                                input=program(remove_terminal_handoff=remove_terminal_handoff,
                                              remove_control_guard=remove_control_guard,
                                              restore_prior_frame_gate=restore_prior_frame_gate),
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_terminal_handoff_and_guards(self):
        with tempfile.TemporaryDirectory(prefix="mount-terminal-") as temporary:
            binary = Path(temporary) / "boundary"
            self.compile(binary)
            for case in ("terminal", "delayed", "consumed", "fresh-direction-at-terminal",
                         "released-at-terminal", "stop-skid-continuation-at-terminal",
                         "released-without-momentum", "stale-bridge", "idle-walk", "idle-hop", "idle-teleport",
                         "idle-teleport-no-flicker", "idle-teleport-per-tile", "idle-teleport-per-tile-no-flicker",
                         "mid-motion", "missing-final-writes", "hop", "stale-field", "missing-player", "not-riding",
                         "no-movement", "no-end"):
                with self.subTest(case=case):
                    result = subprocess.run([str(binary), case], text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_removed_terminal_handoff_reopens_circular_wait(self):
        with tempfile.TemporaryDirectory(prefix="mount-terminal-negative-") as temporary:
            binary = Path(temporary) / "boundary"
            self.compile(binary, remove_terminal_handoff=True)
            result = subprocess.run([str(binary), "terminal"], text=True, capture_output=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("ends == 1", result.stderr)

    def test_removed_control_guard_starts_successor_before_step_delivery(self):
        with tempfile.TemporaryDirectory(prefix="mount-control-negative-") as temporary:
            binary = Path(temporary) / "boundary"
            self.compile(binary, remove_control_guard=True)
            result = subprocess.run([str(binary), "delayed"], text=True, capture_output=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("successors == 0", result.stderr)

    def test_prior_frame_direction_gate_skips_origin_and_collapses_stop_defer(self):
        with tempfile.TemporaryDirectory(prefix="mount-direction-negative-") as temporary:
            binary = Path(temporary) / "boundary"
            self.compile(binary, restore_prior_frame_gate=True)
            for case, expected in (
                ("fresh-direction-at-terminal", "motion_updates == 1"),
                ("released-at-terminal", "stop_skids == 0"),
            ):
                with self.subTest(case=case):
                    result = subprocess.run(
                        [str(binary), case], text=True, capture_output=True)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn(expected, result.stderr)


if __name__ == "__main__":
    unittest.main()
