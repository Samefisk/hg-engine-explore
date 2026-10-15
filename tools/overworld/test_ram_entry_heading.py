"""S1 Ram entry: current condition boundary plus the portable role reducer.

Condition publication and native Walk reset are host spies. This checks fresh
heading admission and retention of existing speed/acceleration state. It does
not prove Vision, target selection, native movement, timing, or ROM delivery.
The same-trigger live memory witness remains a separate acceptance check.
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
WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def extract_module():
    spec = importlib.util.spec_from_file_location(
        "ram_entry_extract", ROOT / "scripts/verify_overworld_role_controller.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def harness_source(with_reset=True):
    extract = extract_module()
    source = WILD.read_text()
    bodies = extract.function_bodies(source)
    boundary = bodies["OverworldWildSpawns_ResolveConditionsAtIntentBoundary"]
    if not with_reset:
        reset = "OverworldWildSpawns_ClearWalkMovementState(state, slot, object);"
        if boundary.count(reset) != 1:
            raise AssertionError("fresh Ram reset seam changed")
        boundary = boundary.replace(reset, "/* Copied-code missing-reset control. */")
    functions = (
        "static const OverworldWildBehaviorProfileData *"
        "OverworldWildSpawns_GetControllerLane(const OverworldWildBehaviorProfile *profile, u8 spotState) {"
        + bodies["OverworldWildSpawns_GetControllerLane"] + "}\n"
        + "static u8 OverworldWildSpawns_GetCommittedWalkDirection(const OverworldActorPolicyView *policy) {"
        + bodies["OverworldWildSpawns_GetCommittedWalkDirection"] + "}\n"
        + "static BOOL OverworldWildSpawns_ResolveConditionsAtIntentBoundary(OverworldWildSpawnState *state, int slot, "
        "OverworldWildBehaviorProfile *profile, OverworldWildBehaviorPrimitives *primitives) {"
        + boundary + "}\n"
    )
    actor = (ROOT / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c").read_text()
    locomotion = extract.function_bodies(actor)["OverworldActorSystem_SelectMovementLocomotion"]
    functions = (
        "static u8 OverworldWildSpawns_GetCurrentMovementLocomotion("
        "const OverworldWildBehaviorPrimitives *primitives, u8 laneState) {"
        + locomotion + "}\n" + functions
    )
    # Keep the production guard and continuation call. The outer native END
    # handler is outside this fixture; its already-cached policy is supplied
    # below so a missing reinspection would execute the stale chain work.
    finished = bodies["OverworldWildSpawns_HandleFinishedMovementCommand"]
    left = finished.index("        if (!OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary(")
    right = finished.index("\n\n        if (!OverworldWildSpawns_ApplyChainRepositionResult", left)
    continuation = finished[left:right]
    definitions = {}
    for path in (WILD, ROOT / "include/overworld_wild_behavior_data.h",
                 ROOT / "include/overworld_wild_movement.h",
                 ROOT / "include/overworld_walk_direction_policy.h"):
        for line in path.read_text().replace("\\\n", " ").splitlines():
            match = re.match(r"#define\s+(\w+)\b", line)
            if match:
                definitions[match[1]] = line
    wanted = set(re.findall(r"\b(?:OW_WILD|OVERWORLD_WALK_DIRECTION)_[A-Z_0-9]+\b",
                            SUPPORT + functions + continuation + DRIVER))
    included, macros = set(), []
    while wanted:
        name = wanted.pop()
        if name in included:
            continue
        if name not in definitions:
            raise AssertionError("missing production constant: " + name)
        included.add(name)
        line = definitions[name]
        macros.append(line)
        wanted.update(re.findall(r"\b(?:OW_WILD|OVERWORLD_WALK_DIRECTION)_[A-Z_0-9]+\b",
                                 line.split(name, 1)[1]))
    return (PRELUDE + "\n".join(macros) + "\n" + SUPPORT + functions
            + CHAIN_SUPPORT + "\nstatic void ContinueChain(OverworldWildSpawnState *state, int slot) {\n"
            + "OverworldWildBehaviorProfile profile = priorProfile;\n"
            + "OverworldActorPolicyView policy = nativePolicy;\n"
            + "OverworldWildChainRepositionResult repositionResult;\n"
            + continuation + "\n}\n" + DRIVER)


PRELUDE = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_role_controller.h"
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
"""

SUPPORT = r"""
typedef struct LocalMapObject { u8 unused; } LocalMapObject;
typedef struct FieldSystem { u8 unused; } FieldSystem;
typedef struct OverworldWildBehaviorProfileData { u8 walkOptions; } OverworldWildBehaviorProfileData;
typedef struct OverworldWildBehaviorProfile {
    OverworldWildBehaviorProfileData owner, tired;
} OverworldWildBehaviorProfile;
typedef struct OverworldWildBehaviorPrimitives {
    u8 chillLocomotion, tiredLocomotion, tiredReaction;
} OverworldWildBehaviorPrimitives;
typedef struct OverworldActorPolicyView {
    struct { u8 direction, speed, tileCounter; } walkMomentum;
    u8 linearElapsed, linearCarry, chainStepsRemaining;
} OverworldActorPolicyView;
typedef struct OverworldWildOverlayRuntimeState {
    struct { u8 targets[1]; u16 recoveringMask; } throwState;
} OverworldWildOverlayRuntimeState;
typedef struct OverworldWildSpawnState {
    struct { LocalMapObject *object; } spawns[1];
    FieldSystem *movementFieldSystem;
    u8 movementSpotStates[1], movementCooldowns[1], movementTeleportVisiblePause[1];
    OverworldWildOverlayRuntimeState runtime;
} OverworldWildSpawnState;
#define OW_WILD_RUNTIME(state) (&(state)->runtime)
static struct { u16 intentConditionsCheckedMask; } sOverworldWildFlags;
static OverworldActorPolicyView nativePolicy;
static OverworldWildBehaviorProfile priorProfile, nextProfile;
static OverworldWildBehaviorPrimitives nextPrimitives;
static unsigned resetCalls, alertCalls, chainCalls;
static u16 nextFlags;
static u8 playerDirection, chainRemaining;
static BOOL alertOwnsIntent;
static u16 OverworldWildSpawns_EvaluateConditionsForSlot(
    OverworldWildSpawnState *state, FieldSystem *field, int slot,
    OverworldWildBehaviorProfile *profile, OverworldWildBehaviorPrimitives *primitives)
{
    (void)state; (void)field; (void)slot;
    *profile = nextProfile; *primitives = nextPrimitives;
    return nextFlags | ((u16)playerDirection << 8);
}
static u32 OverworldWildSpawns_GetActiveConditionApplications(OverworldWildSpawnState *state, int slot)
{ (void)state; (void)slot; return 1; }
static void OverworldWildSpawns_ClearThrowStateForSlot(OverworldWildSpawnState *state, int slot)
{ (void)state; (void)slot; abort(); }
static void OverworldWildSpawns_StartTiredEmoteWithProfile(OverworldWildSpawnState *state, int slot,
    const OverworldWildBehaviorProfile *profile, const OverworldWildBehaviorPrimitives *primitives)
{ (void)state; (void)slot; (void)profile; (void)primitives; abort(); }
static void OverworldWildSpawns_ClearWalkMovementState(OverworldWildSpawnState *state, int slot, LocalMapObject *object)
{
    (void)state; (void)slot; (void)object; resetCalls++;
    memset(&nativePolicy, 0, sizeof(nativePolicy));
    nativePolicy.walkMomentum.direction = OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE;
}
static BOOL OverworldWildSpawns_TryStartSpotEmote(OverworldWildSpawnState *state, int slot,
    LocalMapObject *object, u8 direction, const OverworldWildBehaviorProfile *profile)
{
    (void)state; (void)slot; (void)object; (void)profile;
    if (direction != playerDirection) abort();
    alertCalls++; return alertOwnsIntent;
}
"""

CHAIN_SUPPORT = r"""
typedef struct OverworldWildChainRepositionResult { u8 unused; } OverworldWildChainRepositionResult;
static BOOL OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary(
    OverworldWildSpawnState *state, int slot, OverworldWildBehaviorProfile *profile)
{
    OverworldWildBehaviorPrimitives primitives = nextPrimitives;
    return OverworldWildSpawns_ResolveConditionsAtIntentBoundary(state, slot, profile, &primitives);
}
static BOOL OverworldActorPolicy_Inspect(u8 slot, OverworldActorPolicyView *policy)
{ (void)slot; *policy = nativePolicy; return TRUE; }
static BOOL OverworldWildSpawns_RunChainReposition(OverworldWildSpawnState *state, int slot,
    const OverworldWildBehaviorProfile *profile, u8 remaining, OverworldWildChainRepositionResult *result)
{
    (void)state; (void)slot; (void)profile; (void)result;
    chainCalls++; chainRemaining = remaining; return TRUE;
}
"""

DRIVER = r"""
#define CHECK(value) do { if (!(value)) { fprintf(stderr, "%s line %d: %s\n", argv[1], __LINE__, #value); return 1; } } while (0)
/* Host glue supplies a requested target direction to the real role reducer.
 * It does not simulate Vision, path search, engine motion, or acceleration. */
static u8 SelectWalk(const OverworldWildBehaviorProfile *profile, u8 laneState, u8 requested)
{
    OverworldRoleControllerInput input = {0};
    OverworldRoleControllerOutput output;
    input.version = OVERWORLD_ROLE_CONTROLLER_VERSION;
    input.size = sizeof(input);
    input.role = OVERWORLD_ROLE_CONTROLLER_ROLE_WILD;
    input.event = OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST;
    input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_WALK;
    input.requestedDirection = requested;
    input.committedDirection = OverworldWildSpawns_GetCommittedWalkDirection(&nativePolicy);
    if (OverworldWildSpawns_GetControllerLane(profile, laneState)->walkOptions
            & OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION)
        input.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_RAM;
    OverworldRoleController_Reduce(&input, &output);
    if (output.decision != OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT) abort();
    return output.direction;
}
int main(int argc, char **argv)
{
    LocalMapObject object = {0}; FieldSystem field = {0};
    OverworldWildSpawnState state = {0};
    OverworldWildBehaviorPrimitives primitives;
    if (argc != 3) return 2;
    playerDirection = (u8)strtoul(argv[2], NULL, 10);
    if (playerDirection > OVERWORLD_WALK_DIRECTION_EAST) return 2;
    state.spawns[0].object = &object; state.movementFieldSystem = &field;
    state.movementSpotStates[0] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    state.movementCooldowns[0] = 9; state.movementTeleportVisiblePause[0] = TRUE;
    nativePolicy.walkMomentum.direction = playerDirection == OVERWORLD_WALK_DIRECTION_WEST
        ? OVERWORLD_WALK_DIRECTION_SOUTH : OVERWORLD_WALK_DIRECTION_WEST;
    nativePolicy.walkMomentum.speed = 4; nativePolicy.walkMomentum.tileCounter = 3;
    nativePolicy.linearElapsed = 11; nativePolicy.linearCarry = 27;
    nextPrimitives.chillLocomotion = nextPrimitives.tiredLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_WANDER;
    nextProfile.owner.walkOptions = OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION;
    nextFlags = OW_WILD_CONDITION_RESULT_TRIGGERED | OW_WILD_CONDITION_RESULT_PROFILE_CHANGED;
    primitives = nextPrimitives;
    if (!strcmp(argv[1], "fresh") || !strcmp(argv[1], "alert")) {
        alertOwnsIntent = !strcmp(argv[1], "alert");
        CHECK(OverworldWildSpawns_ResolveConditionsAtIntentBoundary(&state, 0, &priorProfile, &primitives) == !alertOwnsIntent);
        CHECK(resetCalls == 1 && alertCalls == 1);
        CHECK(nativePolicy.walkMomentum.speed == 0);
        CHECK(SelectWalk(&priorProfile, state.movementSpotStates[0], playerDirection) == playerDirection);
    } else if (!strcmp(argv[1], "continued") || !strcmp(argv[1], "locked-trigger")) {
        priorProfile = nextProfile;
        nativePolicy.walkMomentum.direction = playerDirection;
        OverworldActorPolicyView before = nativePolicy;
        nextFlags = !strcmp(argv[1], "continued") ? 0 : nextFlags;
        playerDirection = (playerDirection + 1) % 4;
        CHECK(OverworldWildSpawns_ResolveConditionsAtIntentBoundary(&state, 0, &priorProfile, &primitives));
        CHECK(resetCalls == 0 && !memcmp(&before, &nativePolicy, sizeof(before)));
        CHECK(SelectWalk(&priorProfile, state.movementSpotStates[0], playerDirection) == before.walkMomentum.direction);
    } else if (!strcmp(argv[1], "chain-reset") || !strcmp(argv[1], "chain-kept")) {
        nativePolicy.chainStepsRemaining = OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING | 2;
        if (!strcmp(argv[1], "chain-kept")) { priorProfile = nextProfile; nextFlags = 0; }
        ContinueChain(&state, 0);
        if (!strcmp(argv[1], "chain-reset")) CHECK(resetCalls == 1 && chainCalls == 0);
        else CHECK(resetCalls == 0 && chainCalls == 1 && chainRemaining == nativePolicy.chainStepsRemaining);
    } else {
        if (!strcmp(argv[1], "unrelated")) nextProfile.owner.walkOptions = 0;
        else if (!strcmp(argv[1], "non-walk")) nextPrimitives.chillLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_HOP;
        else if (!strcmp(argv[1], "tired-owner")) state.movementSpotStates[0] = OW_WILD_SPAWNER_SPOT_STATE_TIRED;
        else if (!strcmp(argv[1], "no-trigger")) nextFlags = OW_WILD_CONDITION_RESULT_PROFILE_CHANGED;
        else return 2;
        OverworldActorPolicyView before = nativePolicy;
        CHECK(OverworldWildSpawns_ResolveConditionsAtIntentBoundary(&state, 0, &priorProfile, &primitives));
        CHECK(resetCalls == 0 && !memcmp(&before, &nativePolicy, sizeof(before)));
    }
    CHECK(sOverworldWildFlags.intentConditionsCheckedMask == 1);
    return 0;
}
"""


class RamEntryHeadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ram-entry-host-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.binary = cls.compile_harness("current", True)
        cls.missing_reset = cls.compile_harness("missing-reset", False)

    @classmethod
    def compile_harness(cls, name, with_reset):
        source = Path(cls.temp.name) / (name + ".c")
        binary = Path(cls.temp.name) / name
        source.write_text(harness_source(with_reset))
        command = shlex.split(os.environ.get("CC", "cc")) + [
            "-std=c99", "-DOVERWORLD_ROLE_CONTROLLER_HOST", "-I", str(ROOT / "include"),
            str(source), str(ROOT / "lib/overworld/overworld_role_controller.c"), "-o", str(binary)]
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            raise AssertionError("Ram host harness did not compile:\n" + result.stderr)
        return binary

    def check_case(self, case, direction=0, binary=None):
        return subprocess.run([str(binary or self.binary), case, str(direction)],
                              text=True, capture_output=True)

    def test_fresh_ram_uses_target_in_each_cardinal_direction(self):
        for direction in range(4):
            with self.subTest(direction=direction):
                result = self.check_case("fresh", direction)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_alert_start_also_discards_ordinary_heading(self):
        result = self.check_case("alert")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_running_ram_keeps_heading_speed_and_acceleration(self):
        for case in ("continued", "locked-trigger"):
            for direction in range(4):
                with self.subTest(case=case, direction=direction):
                    result = self.check_case(case, direction)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_other_conditions_and_tired_owner_do_not_reset_walk(self):
        for case in ("unrelated", "non-walk", "tired-owner", "no-trigger"):
            with self.subTest(case=case):
                result = self.check_case(case)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_chain_continuation_reloads_policy_after_ram_entry(self):
        for case in ("chain-reset", "chain-kept"):
            with self.subTest(case=case):
                result = self.check_case(case)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_copied_missing_reset_control_is_rejected(self):
        result = self.check_case("fresh", binary=self.missing_reset)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("resetCalls == 1", result.stderr)


if __name__ == "__main__":
    unittest.main()
