"""S1 admission proof: a rejected mounted diagonal is not a stop request.

Compile the current input-adapter bodies. Native collision, landing and the
policy/engine boundary are host spies. Motion decisions use the real portable
planner. This does not prove native scheduling, terrain, or ROM trace delivery.
"""
from pathlib import Path
import importlib.util
import os
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def harness_source():
    spec = importlib.util.spec_from_file_location(
        "diagonal_bodies", ROOT / "scripts/verify_overworld_role_controller.py")
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    walk = (ROOT / "src/pokemon_move_history_overlay/overworld_walk_module.c").read_text()
    mount = (ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text()
    internal = (ROOT / "include/overworld_actor_system_internal.h").read_text()
    behavior = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
    direction = (ROOT / "include/overworld_walk_direction_policy.h").read_text()
    timing = (ROOT / "include/overworld_walk_timing_policy.h").read_text().replace('#include "types.h"', '')
    table_match = re.search(
        r'sOverworldWalkDirectionKeys:\\n"\s*"\.hword ([^"\\n]+)\\n"\s*"\.hword ([^"\\n]+)',
        walk,
    )
    if table_match is None:
        raise AssertionError("mounted direction-key table was not found")
    direction_keys = ", ".join(
        item.strip() for row in table_match.groups() for item in row.split(",")
    )
    # Portable direction bodies are real code; only their target type include
    # is omitted because the motion model supplies the host integer types.
    direction = direction.replace('#include "types.h"', '')
    request_start = internal.index("typedef struct OverworldActorMotionRequestCall {")
    request_end = internal.index("} OverworldActorMotionRequestCall;", request_start)
    request = internal[request_start:request_end + len("} OverworldActorMotionRequestCall;")]
    enum_start = internal.index("typedef enum OverworldActorMotionServiceOperation {")
    enum_end = internal.index("} OverworldActorMotionServiceOperation;", enum_start)
    request += internal[enum_start:enum_end + len("} OverworldActorMotionServiceOperation;")]
    functions = []
    for source, signature in (
        (walk, "static void Walk_GetComponents(u8 direction, u8 *vertical, u8 *horizontal)"),
        (walk, "u8 OverworldWalk_DirectionFromKeys(u32 keys)"),
        (walk, "u32 OverworldWalk_DirectionKey(u8 direction)"),
        (walk, "int OverworldWalk_DeltaX(u8 direction)"),
        (walk, "int OverworldWalk_DeltaY(u8 direction)"),
        (walk, "static u16 Walk_DiagonalRejection(OverworldMountRuntimeState *state, FIELD_PLAYER_AVATAR *avatar, u8 direction)"),
        (walk, "BOOL OverworldWalk_StrictDiagonalAllowed(OverworldMountRuntimeState *state, FIELD_PLAYER_AVATAR *avatar, u8 direction)"),
        (walk, "u8 OverworldWalk_DiagonalFacing(LocalMapObject *player, u8 direction, u32 newKeys)"),
        (walk, "static u16 Walk_RejectDiagonalCandidate(OverworldMountRuntimeState *state, FIELD_PLAYER_AVATAR *avatar, u8 direction, u16 rejectionFlags)"),
        (walk, "u16 OverworldWalk_ResolveMountedDiagonal(OverworldMountRuntimeState *state, FIELD_PLAYER_AVATAR *avatar, u32 *newKeys, u32 *heldKeys)"),
        (mount, "static BOOL OverworldMount_TryStartWalkFromInput(FIELD_PLAYER_AVATAR *avatar, u32 *newKeys, u32 *heldKeys, BOOL advanceFirstFrame)"),
    ):
        name = signature.split("(", 1)[0].split()[-1]
        functions.append(signature + " {" + extract.function_bodies(source)[name] + "}\n")
    definitions = {}
    for source in (walk, behavior, internal, (ROOT / "include/overworld_wild_spawns_internal.h").read_text()):
        for line in source.replace("\\\n", " ").splitlines():
            match = re.match(r"#define\s+(\w+)\b", line)
            if match:
                definitions[match[1]] = line
    wanted = set(re.findall(r"\b(?:WALK_DIRECTION|OW_WILD|OVERWORLD_ACTOR)_[A-Z_0-9]+\b", "\n".join(functions) + SUPPORT + DRIVER))
    macros, included = [], set()
    while wanted:
        name = wanted.pop()
        if name in included or name not in definitions:
            continue
        included.add(name)
        line = definitions[name]
        macros.append(line)
        wanted.update(re.findall(r"\b[A-Z][A-Z_0-9]+\b", line.split(name, 1)[1]))
    table = "static const u16 sOverworldWalkDirectionKeys[] = {" + direction_keys + "};\n"
    return PRELUDE + direction + timing + "\n".join(macros) + "\n" + request + SUPPORT + table + "\n".join(functions) + DRIVER


PRELUDE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_motion_model.h"
#include "overworld_role_controller.h"
typedef int BOOL;
typedef struct OverworldActorHopPlanCall OverworldActorHopPlanCall;
typedef struct OverworldActorTeleportPlanCall OverworldActorTeleportPlanCall;
'''

SUPPORT = r'''
/* Host engine views contain only fields read by these admission bodies. */
typedef struct LocalMapObject { int xCurr, yCurr, curFacing; } LocalMapObject;
typedef struct FIELD_PLAYER_AVATAR { LocalMapObject *mapObject; } FIELD_PLAYER_AVATAR;
typedef struct OverworldMountRuntimeState {
    struct { struct { u8 hopAllowNonCardinal, chillAction, chillSpeed, walkOptions; } profile; } snapshot;
} OverworldMountRuntimeState;
static OverworldMountRuntimeState sOverworldMountState;
static unsigned blockedDirections, landingAllowed, policyCalls, requestCalls;
static unsigned reducedDirection = 254, rejectionDecision = 254;
static u8 committedDirection = OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE;
static u8 roleIntentFlags;
static BOOL Walk_CanCardinal(FIELD_PLAYER_AVATAR *avatar, u8 direction)
{ (void)avatar; return !(blockedDirections & (1u << direction)); }
static BOOL Walk_ValidateDiagonalLanding(OverworldMountRuntimeState *state, int x, int y)
{ (void)state; (void)x; (void)y; return landingAllowed; }
static BOOL OverworldMount_CanControl(FIELD_PLAYER_AVATAR *avatar)
{ return avatar != NULL; }
static void *PokemonMoveHistory_OverlayMemset(void *target, int value, u32 size)
{ return memset(target, value, size); }
static void OverworldMount_FilterMovementInput(FIELD_PLAYER_AVATAR *avatar, u32 *newKeys, u32 *heldKeys)
{
    OverworldRoleControllerInput input = {0};
    OverworldRoleControllerOutput output;
    (void)avatar;
    policyCalls++;
    reducedDirection = OverworldWalkDirectionPolicy_FromKeys(*newKeys | *heldKeys);
    if (reducedDirection == OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE) return;
    input.version = OVERWORLD_ROLE_CONTROLLER_VERSION;
    input.size = sizeof(input);
    input.role = OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED;
    input.event = OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST;
    input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_WALK;
    input.requestedDirection = reducedDirection;
    input.committedDirection = committedDirection;
    if (sOverworldMountState.snapshot.profile.walkOptions
            & OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION)
        input.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_RAM;
    /* Use the production role reducer, not a copy of its direction rule.
     * This spy does not claim to execute the later momentum/crash policy. */
    OverworldRoleController_Reduce(&input, &output);
    reducedDirection = output.direction;
    roleIntentFlags = output.intentFlags;
}
static BOOL OverworldMount_TryHandleDiagonalWalk(FIELD_PLAYER_AVATAR *avatar, u32 newKeys, u32 heldKeys, BOOL advanceFirstFrame)
{ (void)avatar; (void)newKeys; (void)heldKeys; (void)advanceFirstFrame; return FALSE; }
/* This service spy uses current request declarations and the real planner.
 * Its count proves adapter submission, not actor trace publication. */
static int SpyRequest(OverworldActorMotionRequestCall *call)
{
    OverworldMotionPlan plan;
    if (call->version != OVERWORLD_ACTOR_MOTION_CALL_VERSION
        || call->size != sizeof(*call)
        || call->operation != OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST
        || call->actorSlot != OW_WILD_FOLLOWER_SLOT
        || call->candidateCount != 1 || call->motionIdentity != 0
        || call->intent == NULL || call->candidates == NULL
        || call->intent->fieldEpoch != 1
        || call->intent->kind != OVERWORLD_MOTION_KIND_WALK
        || call->startX != 588 || call->startY != 406
        || call->candidates->targetX != 587 || call->candidates->targetY != 407) {
        fprintf(stderr, "invalid mounted candidate request\n");
        exit(3);
    }
    requestCalls++;
    call->decision = OverworldMotion_SelectPlan(call->intent, call->startX,
        call->startY, call->startBaseY, call->candidates, call->candidateCount,
        &plan, &call->selectedIndex);
    rejectionDecision = call->decision;
    return 0;
}
static const struct { int (*request)(OverworldActorMotionRequestCall *); }
    hostMotionEntry = { SpyRequest };
#define OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY (&hostMotionEntry)
static u32 SpyContext(void) { return 1; }
static const struct { u32 (*getContext)(void); } hostCompatEntry = { SpyContext };
#undef OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&hostCompatEntry)
'''

DRIVER = r'''
int main(int argc, char **argv)
{
    LocalMapObject object = {588, 406, 1};
    FIELD_PLAYER_AVATAR avatar = {&object};
    u32 newKeys = PAD_KEY_DOWN | PAD_KEY_LEFT, heldKeys = newKeys;
    BOOL consumed;
    if (argc != 2) return 2;
    sOverworldMountState.snapshot.profile.chillAction = OW_WILD_BEHAVIOR_LOCOMOTION_WALK;
    sOverworldMountState.snapshot.profile.chillSpeed = 8;
    sOverworldMountState.snapshot.profile.hopAllowNonCardinal = OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_AND_DIAGONAL;
    landingAllowed = TRUE;
    if (!strcmp(argv[1], "side")) blockedDirections = 1u << 1;
    else if (!strcmp(argv[1], "locked-side")) {
        blockedDirections = 1u << 1;
        committedDirection = WALK_DIRECTION_WEST;
        sOverworldMountState.snapshot.profile.walkOptions = OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION;
    }
    else if (!strcmp(argv[1], "locked-cardinal-start")) {
        blockedDirections = 1u << 1;
        sOverworldMountState.snapshot.profile.walkOptions = OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION;
        sOverworldMountState.snapshot.profile.hopAllowNonCardinal = OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
    }
    else if (!strcmp(argv[1], "locked-diagonal")) {
        blockedDirections = 1u << 1;
        committedDirection = WALK_DIRECTION_SOUTH_WEST;
        sOverworldMountState.snapshot.profile.walkOptions = OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION;
    }
    else if (!strcmp(argv[1], "landing")) landingAllowed = FALSE;
    else if (!strcmp(argv[1], "none")) newKeys = heldKeys = 0;
    else if (strcmp(argv[1], "clear")) return 2;
    consumed = OverworldMount_TryStartWalkFromInput(&avatar, &newKeys, &heldKeys, FALSE);
    if (!strcmp(argv[1], "locked-diagonal")
        && !(roleIntentFlags & OVERWORLD_ROLE_CONTROLLER_INTENT_CRASH_ON_BLOCKED)) return 4;
    printf("%u %u %u %u %u\n", policyCalls, reducedDirection, requestCalls,
        rejectionDecision, (unsigned)consumed);
    return 0;
}
'''


class MountedDiagonalRejectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="mounted-diagonal-host-")
        cls.addClassCleanup(cls.temp.cleanup)
        source = Path(cls.temp.name) / "admission.c"
        cls.binary = Path(cls.temp.name) / "admission"
        source.write_text(harness_source())
        command = shlex.split(os.environ.get("CC", "cc")) + [
            "-std=c99", "-DOVERWORLD_MOTION_HOST", "-DOVERWORLD_ROLE_CONTROLLER_HOST", "-I", str(ROOT / "include"),
            str(source), str(ROOT / "lib/overworld/overworld_motion_model.c"),
            str(ROOT / "lib/overworld/overworld_role_controller.c"),
            "-o", str(cls.binary)]
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            raise AssertionError("host harness did not compile:\n" + result.stderr)

    def observe(self, case):
        result = subprocess.run([str(self.binary), case], text=True, capture_output=True, check=True)
        return tuple(map(int, result.stdout.split()))

    def test_blocked_side_is_consumed_without_policy_stop(self):
        policy_calls, direction, _, _, consumed = self.observe("side")
        self.assertEqual(policy_calls, 0, f"blocked diagonal reached policy as direction {direction}")
        self.assertEqual(consumed, 1)

    def test_blocked_side_submits_one_side_rejection(self):
        _, _, requests, reason, _ = self.observe("side")
        self.assertEqual(requests, 1, "blocked side must reach Actor Motion once")
        self.assertEqual(reason, self.reason_value("SIDE_TILE"))

    def test_bad_landing_submits_distinct_terrain_rejection(self):
        policy_calls, _, requests, reason, consumed = self.observe("landing")
        self.assertEqual(requests, 1, "bad landing must reach Actor Motion once")
        self.assertEqual(reason, self.reason_value("TERRAIN"))
        self.assertEqual(policy_calls, 0)
        self.assertEqual(consumed, 1)

    def test_clear_diagonal_reaches_policy_unchanged(self):
        self.assertEqual(self.observe("clear"), (1, 6, 0, 254, 0))

    def test_real_none_still_reaches_stop_policy(self):
        self.assertEqual(self.observe("none"), (1, 255, 0, 254, 0))

    def test_locked_direction_uses_clear_committed_direction(self):
        self.assertEqual(self.observe("locked-side"), (1, 2, 0, 254, 0),
                         "raw blocked diagonal must not consume locked west travel")

    def test_locked_cardinal_start_preserves_direction_allowance(self):
        self.assertEqual(self.observe("locked-cardinal-start"), (1, 2, 0, 254, 0))

    def test_locked_diagonal_reaches_existing_crash_policy(self):
        self.assertEqual(self.observe("locked-diagonal"), (1, 6, 0, 254, 0))

    @staticmethod
    def reason_value(name):
        header = (ROOT / "include/overworld_motion_model.h").read_text()
        return int(re.search(r"OVERWORLD_MOTION_DECISION_" + name + r"\s*=\s*(\d+)", header).group(1))


if __name__ == "__main__":
    unittest.main()
