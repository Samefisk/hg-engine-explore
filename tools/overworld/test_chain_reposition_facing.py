"""S1 facing ownership: actual tick caller and resident facing helper bodies.

The small host structs are not DS layouts. Policy reads and the preceding
Motion sample are host inputs; this does not prove scheduling or rendering.
The separate normal Ledyba scenario remains the required live witness.
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
RESIDENT = ROOT / "src/overworld_wild_movement.c"


def harness_source():
    spec = importlib.util.spec_from_file_location(
        "facing_bodies", ROOT / "scripts/verify_overworld_role_controller.py")
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    wild, resident = WILD.read_text(), RESIDENT.read_text()
    tick = extract.function_bodies(wild)["OverworldWildSpawns_TickMovementParams"]
    anchor = "if (OW_WILD_BEHAVIOR_WALK_FACES_PLAYER"
    if tick.count(anchor) != 1:
        raise ValueError("face-player caller seam differs")
    first = tick.index(anchor)
    clean = extract.strip_c_noncode(tick)
    last = extract.matching_delimiter(clean, clean.index("{", first), "{", "}")
    if last < 0:
        raise ValueError("face-player caller is incomplete")
    caller = tick[first:last + 1]
    helper = extract.function_bodies(resident)["OverworldWildSpawns_ApplyFacePlayerFacing"]
    definitions = {}
    for source in (wild, resident, (ROOT / "include/overworld_wild_behavior_data.h").read_text()):
        for line in source.replace("\\\n", " ").splitlines():
            match = re.match(r"#define\s+(\w+)\b", line)
            if match:
                definitions[match[1]] = line
    wanted = set(re.findall(r"\bOW_WILD_[A-Z_0-9]+\b", caller + helper + DRIVER))
    included, macros = set(), []
    while wanted:
        name = wanted.pop()
        if name in included:
            continue
        line = definitions[name]
        macros.append(line)
        included.add(name)
        wanted.update(re.findall(r"\bOW_WILD_[A-Z_0-9]+\b", line.split(name, 1)[1]))
    return "\n".join(macros) + SUPPORT.replace("/* @HELPER@ */", helper).replace(
        "/* @CALLER@ */", caller) + DRIVER


SUPPORT = r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef int BOOL;
typedef struct LocalMapObject { int xCurr, yCurr; u8 curFacing; } LocalMapObject;
typedef struct PlayerAvatar { LocalMapObject *mapObject; } PlayerAvatar;
typedef struct FieldSystem { PlayerAvatar *playerAvatar; } FieldSystem;
typedef struct OverworldWildSpawnState {
    struct { LocalMapObject *object; } spawns[10];
    FieldSystem *movementFieldSystem;
} OverworldWildSpawnState;
typedef struct OverworldActorPolicyView { u8 chainPauseAction; } OverworldActorPolicyView;
static OverworldActorPolicyView selectedPolicy;
static BOOL inspectOkay;
static BOOL motionOwnsFacing;
static unsigned inspectCalls, checks;
static BOOL OverworldActorPolicy_Inspect(u8 slot, OverworldActorPolicyView *out)
{
    if (slot != 3) exit(2);
    inspectCalls++;
    if (inspectOkay) *out = selectedPolicy;
    return inspectOkay;
}
static void OverworldWildSpawns_ApplyFacePlayerFacing(
    OverworldWildSpawnState *state, int slot, u8 emotePlayHopSound)
{ /* @HELPER@ */ }
static void ApplyTickFacing(OverworldWildSpawnState *state, u8 options, u8 sound)
{
    int i = 3;
    struct { struct { u8 walkOptions; } owner; } profile = {{options}};
    struct { u8 movementEmotePlayHopSound[10]; } runtimeValue = {{0}}, *runtime = &runtimeValue;
    OverworldActorPolicyView policy = {0};
    BOOL actorPolicyKnown = OverworldActorPolicy_Inspect((u8)i, &policy);
    BOOL actorMotionOwnsFacing = motionOwnsFacing;
    (void)actorPolicyKnown;
    (void)actorMotionOwnsFacing;
    runtime->movementEmotePlayHopSound[i] = sound;
    /* Keep the pre-fix source compilable so RED is an actual behavior failure. */
    (void)policy; (void)&OverworldActorPolicy_Inspect;
    /* @CALLER@ */
}
static void CheckFacing(OverworldWildSpawnState *state, int x, int y,
    u8 before, u8 expected, u8 options, u8 encoded, BOOL inspect, u8 sound)
{
    LocalMapObject *object = state->spawns[3].object;
    *object = (LocalMapObject){x, y, before};
    selectedPolicy.chainPauseAction = encoded;
    inspectOkay = inspect;
    inspectCalls = 0;
    ApplyTickFacing(state, options, sound);
    checks++;
    if (object->curFacing != expected) {
        fprintf(stderr, "facing invariant failed: actor=(%d,%d) player=(550,381) "
            "grid=0x%02x expected=%u actual=%u\n", x, y, encoded, expected, object->curFacing);
        exit(1);
    }
}
"""


DRIVER = r"""
int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    LocalMapObject player = {550, 381, 0}, object = {0};
    PlayerAvatar avatar = {&player};
    FieldSystem field = {&avatar};
    OverworldWildSpawnState state = {.movementFieldSystem = &field};
    state.spawns[3].object = &object;
    u8 facePlayer = OW_WILD_BEHAVIOR_WALK_OPTION_FACE_PLAYER;
    if (!strcmp(argv[1], "live")) {
        /* ROM3068 normal Ledyba, frames869..884. Every sample must face the
         * player, including the frames where the reposition path turns. */
        int forward[8][2] = {{559,375},{559,375},{559,375},{558,374},
            {558,374},{558,374},{558,374},{557,373}};
        int reverse[8][2] = {{557,373},{557,373},{558,374},{558,374},
            {558,374},{558,374},{559,375},{559,375}};
        for (unsigned n = 0; n < 8; n++)
            CheckFacing(&state, forward[n][0], forward[n][1], 0,
                forward[n][0] == 557 ? 1 : 2, facePlayer, 0x90, 1, 1);
        for (unsigned n = 0; n < 8; n++)
            CheckFacing(&state, reverse[n][0], reverse[n][1], 0,
                reverse[n][0] == 557 ? 1 : 2, facePlayer, 0x9A, 1, 1);
    } else if (!strcmp(argv[1], "grids")) {
        u8 grids[] = {0x90,0x91,0x92,0x94,0x95,0x96,0x98,0x99,0x9A};
        for (unsigned grid = 0; grid < sizeof(grids); grid++)
            for (u8 facing = 0; facing < 4; facing++) {
                CheckFacing(&state, 557, 373, facing, 1,
                    facePlayer, grids[grid], 1, 1);
                CheckFacing(&state, 558, 374, facing, 2,
                    facePlayer, grids[grid], 1, 1);
            }
    } else if (!strcmp(argv[1], "ordinary")) {
        /* Inactive chains and deferred actions are not active grid actions. */
        u8 ordinary[] = {0,0x81,0x82,0x83,0x84,0x85,0x8F,0xA0};
        for (unsigned n = 0; n < sizeof(ordinary); n++) {
            CheckFacing(&state, 557, 373, 0, 1, facePlayer, ordinary[n], 1, 1);
            CheckFacing(&state, 558, 374, 0, 2, facePlayer, ordinary[n], 1, 1);
        }
    } else if (!strcmp(argv[1], "options")) {
        for (u8 grid = 0; grid < 2; grid++) {
            u8 encoded = grid ? 0x95 : 0;
            CheckFacing(&state, 557, 373, 3, 3, 0, encoded, 1, 1);
            CheckFacing(&state, 557, 373, 3, 3,
                OW_WILD_BEHAVIOR_WALK_OPTION_FIXED_FACING, encoded, 1, 1);
        }
        CheckFacing(&state, 557, 373, 3, 3, facePlayer, 0, 1, 0);
        avatar.mapObject = NULL;
        CheckFacing(&state, 557, 373, 3, 3, facePlayer, 0, 1, 1);
        avatar.mapObject = &player;
        /* Policy inspection does not own a face-player profile's direction. */
        CheckFacing(&state, 557, 373, 2, 1, facePlayer, 0x95, 0, 1);
    } else if (!strcmp(argv[1], "motion")) {
        motionOwnsFacing = 1;
        CheckFacing(&state, 557, 373, 0, 1, facePlayer, 0, 1, 1);
        motionOwnsFacing = 0;
        CheckFacing(&state, 557, 373, 0, 1, facePlayer, 0, 1, 1);
    } else return 2;
    printf("facing: %s %u checks passed\n", argv[1], checks);
    return 0;
}
"""


def execute(source, case):
    with tempfile.TemporaryDirectory(prefix="chain-facing-") as directory:
        unit, binary = Path(directory) / "fixture.c", Path(directory) / "fixture"
        unit.write_text(source)
        command = shlex.split(os.environ.get("CC", "cc")) + [
            "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", str(unit), "-o", str(binary)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stderr)
        return subprocess.run([str(binary), case], capture_output=True, text=True)


class ChainRepositionFacingTests(unittest.TestCase):
    def test_exact_live_facing_owner(self):
        result = execute(harness_source(), "live")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_grid_scope_and_ordinary_options(self):
        source = harness_source()
        for case in ("grids", "ordinary", "options", "motion"):
            with self.subTest(case=case):
                result = execute(source, case)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_caller_mutations_are_rejected(self):
        source = harness_source()
        face_guard = "if (OW_WILD_BEHAVIOR_WALK_FACES_PLAYER"
        face_condition = "OW_WILD_BEHAVIOR_WALK_FACES_PLAYER(profile.owner.walkOptions)"
        guard = """&& (!actorPolicyKnown
                    || (policy.chainPauseAction
                        & OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER_MASK)
                        != OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER)"""
        self.assertEqual(source.count(guard), 0,
                         "chain reposition must not suppress face-player")
        self.assertEqual(source.count("!actorMotionOwnsFacing"), 0,
                         "ordinary Motion must not suppress face-player")
        result = execute(source.replace(
            face_guard,
            "if (!actorMotionOwnsFacing && OW_WILD_BEHAVIOR_WALK_FACES_PLAYER",
            1,
        ), "motion")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("facing invariant failed", result.stderr)
        for name, replacement, case in (
            ("active grid suppresses face-player",
             "&& (!actorPolicyKnown"
             " || (policy.chainPauseAction & 0xF0) != 0x90)", "grids"),
            ("all deferred actions suppress face-player",
             "&& (!actorPolicyKnown"
             " || (policy.chainPauseAction & 0x80) == 0)", "ordinary"),
            ("center grid suppresses face-player",
             "&& (!actorPolicyKnown"
             " || policy.chainPauseAction != 0x95)", "grids"),
        ):
            with self.subTest(mutation=name):
                result = execute(source.replace(
                    face_condition,
                    "(" + face_condition + " " + replacement + ")",
                    1,
                ), case)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("facing invariant failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
