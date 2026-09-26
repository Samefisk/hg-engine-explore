"""Mounted Sprint approaches walls without allowing unsafe skids."""

from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

from scripts.verify_overworld_mount import function_body


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_mount_action_overlay/overworld_mount_action_overlay.c"


def harness_source() -> str:
    source = SOURCE.read_text()
    functions = (
        ("OverworldMountAction_IsWalkCorridorTileOpen",
         "static BOOL OverworldMountAction_IsWalkCorridorTileOpen(OverworldMountRuntimeState *state, int x, int y)"),
        ("OverworldMountAction_IsWalkStepOpen",
         "static BOOL OverworldMountAction_IsWalkStepOpen(OverworldMountRuntimeState *state, int x, int y, int dx, int dy)"),
        ("OverworldMountAction_WalkCorridor",
         "static u8 OverworldMountAction_WalkCorridor(OverworldMountActionCall *call)"),
    )
    extracted = "\n".join(
        signature + " {" + function_body(source, name) + "}\n"
        for name, signature in functions
    )
    return STUBS + extracted + CASES


STUBS = r"""
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OW_WILD_FOLLOWER_SLOT 7
#define OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION 1
#define OVERWORLD_WILD_OCCUPANCY_NONPLAYER 2
#define OW_WILD_BEHAVIOR_LOCOMOTION_WALK 1
#define OW_WILD_BEHAVIOR_BOOL_YES 1
#define OVERWORLD_ACTOR_WALK_STEP_SKID 0x02
#define OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH 0x80
#define OVERWORLD_ACTOR_WALK_STEP_STOP_SKID 0x04
#define OVERWORLD_ACTOR_WALK_STEP_POST_SKID 0x20
#define OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX 0
#define OVERWORLD_MOUNT_WALK_FACING_DIRECTION_INDEX 1
#define OVERWORLD_MOUNT_WALK_SKID_PATH_TILES_INDEX 0
#define OVERWORLD_WALK_DIRECTION_NONE 0xff
typedef struct { int xCurr, yCurr; } LocalMapObject;
typedef struct { LocalMapObject *mapObject; } FIELD_PLAYER_AVATAR;
typedef struct { int unused; } FieldSystem;
typedef struct {
    u8 chillAction, hopMinDistance, hopMaxDistance, hopAllowVerticalObstacles;
    u16 chillAllowedTerrainMask;
} OverworldWildBehaviorProfileData;
typedef struct {
    OverworldWildBehaviorProfileData profile;
} OverworldMountSnapshot;
typedef struct {
    FieldSystem *fieldSystem;
    OverworldMountSnapshot snapshot;
    u8 reservedPolicyState[2];
    u8 reservedPolicyProfile[1];
} OverworldMountRuntimeState;
typedef struct {
    OverworldMountRuntimeState *state;
    FIELD_PLAYER_AVATAR *avatar;
    u8 direction;
} OverworldMountActionCall;
static u8 blocked[24][24], occupied[24][24], invalid[24][24];
static int landingChecks;
static BOOL InBounds(int x, int y)
{ return x >= 0 && x < 24 && y >= 0 && y < 24; }
static BOOL IsMetatileBlockedAt(FieldSystem *fieldSystem, int x, int y)
{
    (void)fieldSystem;
    return InBounds(x, y) && blocked[y][x];
}
static BOOL OverworldWildOccupancy_Query(FieldSystem *fieldSystem,
    LocalMapObject *object, void *reserved, int x, int y, int flags, int kind)
{
    (void)fieldSystem; (void)object; (void)reserved; (void)flags; (void)kind;
    return InBounds(x, y) && occupied[y][x];
}
static int OverworldWalk_DeltaX(u8 direction)
{ return direction == 2 ? -1 : direction == 3; }
static int OverworldWalk_DeltaY(u8 direction)
{ return direction == 0 ? -1 : direction == 1; }
static BOOL ValidateHopLanding(u16 version, int slot, FieldSystem *fieldSystem,
    u16 allowed, int x, int y, int finalX, int finalY)
{
    (void)version; (void)slot; (void)fieldSystem;
    (void)finalX; (void)finalY;
    landingChecks++;
    /* Non-Land terrain can pass the real classifier despite static collision. */
    return InBounds(x, y)
        && (!blocked[y][x] || (allowed == 2 && x == 13 && y == 10))
        && !occupied[y][x]
        && !invalid[y][x];
}
static const struct {
    BOOL (*validateHopLanding)(u16, int, FieldSystem *, u16,
        int, int, int, int);
} landingEntry = { ValidateHopLanding };
#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY (&landingEntry)
"""


CASES = r"""
#define CHECK(value) do { if (!(value)) { \
    fprintf(stderr, "line %d: %s\n", __LINE__, #value); return 1; \
} } while (0)
int main(void)
{
    FieldSystem field = {0};
    LocalMapObject player = {10, 10};
    FIELD_PLAYER_AVATAR avatar = {&player};
    OverworldMountRuntimeState state = {0};
    OverworldMountActionCall call = {&state, &avatar, 3};
    state.fieldSystem = &field;
    state.snapshot.profile.chillAction = OW_WILD_BEHAVIOR_LOCOMOTION_WALK;
    state.snapshot.profile.hopMinDistance = 2;
    state.snapshot.profile.hopMaxDistance = 2;
    state.snapshot.profile.hopAllowVerticalObstacles = 1;
    state.snapshot.profile.chillAllowedTerrainMask = 1;
    state.reservedPolicyProfile[OVERWORLD_MOUNT_WALK_SKID_PATH_TILES_INDEX] = 1;

    blocked[10][12] = 1;
    blocked[10][13] = 1;
    CHECK(OverworldMountAction_WalkCorridor(&call));
    CHECK(landingChecks == 0);
    state.reservedPolicyState[OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX] =
        OVERWORLD_ACTOR_WALK_STEP_POST_SKID;
    CHECK(OverworldMountAction_WalkCorridor(&call));

    state.reservedPolicyState[OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX] =
        OVERWORLD_ACTOR_WALK_STEP_SKID
            | OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH;
    state.reservedPolicyProfile[OVERWORLD_MOUNT_WALK_SKID_PATH_TILES_INDEX] = 2;
    state.reservedPolicyState[OVERWORLD_MOUNT_WALK_FACING_DIRECTION_INDEX] = 1;
    CHECK(!OverworldMountAction_WalkCorridor(&call));
    state.reservedPolicyProfile[OVERWORLD_MOUNT_WALK_SKID_PATH_TILES_INDEX] = 1;
    blocked[11][11] = 1;
    CHECK(!OverworldMountAction_WalkCorridor(&call));
    blocked[11][11] = 0;
    CHECK(OverworldMountAction_WalkCorridor(&call));
    blocked[10][11] = 1;
    CHECK(!OverworldMountAction_WalkCorridor(&call));
    state.reservedPolicyState[OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX] =
        OVERWORLD_ACTOR_WALK_STEP_SKID
            | OVERWORLD_ACTOR_WALK_STEP_STOP_SKID
            | OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH;
    CHECK(!OverworldMountAction_WalkCorridor(&call));
    puts("mounted clear approach and actual skid safety passed");
    return 0;
}
"""


class MountSprintObstacleApproachTests(unittest.TestCase):
    def test_sprint_approach_and_skid_guards(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mount-sprint-approach-") as directory:
            binary = Path(directory) / "mount-sprint-approach"
            compiled = subprocess.run(
                [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11",
                 "-O2", "-Wall", "-Wextra", "-Werror", "-x", "c", "-",
                 "-o", str(binary)],
                input=harness_source(), text=True, capture_output=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
