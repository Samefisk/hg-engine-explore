"""Wild Walk can approach a wall; actual skids keep their path checks."""

from pathlib import Path
import importlib.util
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPAWNS = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def function_bodies() -> dict[str, str]:
    path = ROOT / "scripts/verify_overworld_role_controller.py"
    spec = importlib.util.spec_from_file_location("turn_skid_bodies", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.function_bodies(SPAWNS.read_text())


def harness_source() -> str:
    bodies = function_bodies()
    return r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OW_WILD_WALK_DIRECTION_NONE 0xFF
#define OW_WILD_WALK_DIRECTION_OBSTACLE_APPROACH 0xFE
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT 3
#define OVERWORLD_ACTOR_WALK_STEP_VALIDATE 0x01
#define OVERWORLD_ACTOR_WALK_STEP_SKID 0x02
#define OVERWORLD_ACTOR_WALK_STEP_STOP_SKID 0x04
#define OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH 0x80
#define OVERWORLD_ACTOR_WALK_POLICY_SKID_PATH_TILES_INDEX 1
#define OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER 0x8000
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK 0
#define OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP 1
#define OW_WILD_SPAWNER_CUSTOM_MOTION_WALK_FLAG 1
#define OVERWORLD_MOTION_DECISION_ACCEPTED 1
#define MAPOBJECTFLAG_UNK7 0x80
#define OW_WILD_BEHAVIOR_BOOL_YES 1
#define OW_WILD_DIRECTION_STEP_BUSY 0
#define OW_WILD_DIRECTION_STEP_STARTED 2
#define OW_WILD_DIRECTION_STEP_OBSTACLE_HOP_STARTED 3
typedef struct LocalMapObject { int xCurr, yCurr; } LocalMapObject;
typedef struct OverworldWildSpawnState {
    u8 movementPreviousTileLocked[10];
    u8 movementSpotStates[10];
} OverworldWildSpawnState;
typedef struct OverworldWildBehaviorProfileData {
    u8 hopMinDistance, hopMaxDistance, hopAllowVerticalObstacles;
} OverworldWildBehaviorProfileData;
typedef struct OverworldWildDirectionStepContext {
    OverworldWildSpawnState *state;
    void *fieldSystem;
    LocalMapObject *object;
    void *profile;
    u16 allowedTile;
    u8 slot;
} OverworldWildDirectionStepContext;
typedef struct OverworldActorWalkPolicyCall {
    u8 stepDirection, facingDirection, travelTime, stepFlags;
    u8 reserved[4];
} OverworldActorWalkPolicyCall;
static u8 blocked[24][24];
static u8 occupied[24][24];
static OverworldWildBehaviorProfileData lane;
static int startCalls;
static BOOL IsMetatileBlockedAt(void *fieldSystem, int x, int y)
{ (void)fieldSystem; return x < 0 || x >= 24 || y < 0 || y >= 24 || blocked[y][x]; }
static BOOL OverworldWildSpawns_IsTileOccupiedByObject(void *fieldSystem, int x, int y)
{ (void)fieldSystem; return x < 0 || x >= 24 || y < 0 || y >= 24 || occupied[y][x]; }
static int OverworldWildSpawns_ObjectCurrentX(LocalMapObject *object)
{ return object->xCurr; }
static int OverworldWildSpawns_ObjectCurrentY(LocalMapObject *object)
{ return object->yCurr; }
static int OverworldWalk_DeltaX(u8 direction)
{ return direction == 2 || direction == 4 || direction == 6 ? -1
    : direction == 3 || direction == 5 || direction == 7; }
static int OverworldWalk_DeltaY(u8 direction)
{ return direction == 0 || direction == 4 || direction == 5 ? -1
    : direction == 1 || direction == 6 || direction == 7; }
static BOOL OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(
    OverworldWildSpawnState *state, int slot, void *fieldSystem,
    u16 allowedTile, int x, int y, int finalTargetX, int finalTargetY)
{
    (void)state; (void)slot; (void)fieldSystem; (void)allowedTile;
    (void)finalTargetX; (void)finalTargetY;
    return x >= 0 && x < 24 && y >= 0 && y < 24
        && !blocked[y][x] && !occupied[y][x];
}
static int OverworldWalk_DiagonalFacing(LocalMapObject *object, u8 direction, int key)
{ (void)object; (void)key; return direction; }
static int OverworldWalk_DirectionKey(u8 direction) { return direction; }
static int OverworldWildSpawns_TryStartLedgeJumpCommand(
    const OverworldWildDirectionStepContext *stepContext, u8 direction,
    BOOL obstacleHopAllowed, BOOL probeOnly)
{
    int dx = OverworldWalk_DeltaX(direction);
    int dy = OverworldWalk_DeltaY(direction);
    int frontX = stepContext->object->xCurr + 2 * dx;
    int frontY = stepContext->object->yCurr + 2 * dy;
    int landingX = frontX + dx;
    int landingY = frontY + dy;
    if (!probeOnly || !obstacleHopAllowed || lane.hopMinDistance != 2
        || lane.hopAllowVerticalObstacles != OW_WILD_BEHAVIOR_BOOL_YES
        || (!IsMetatileBlockedAt(stepContext->fieldSystem, frontX, frontY)
            && !OverworldWildSpawns_IsTileOccupiedByObject(
                stepContext->fieldSystem, frontX, frontY))
        || IsMetatileBlockedAt(stepContext->fieldSystem, landingX, landingY)
        || OverworldWildSpawns_IsTileOccupiedByObject(
            stepContext->fieldSystem, landingX, landingY)) {
        return OW_WILD_DIRECTION_STEP_BUSY;
    }
    return OW_WILD_DIRECTION_STEP_OBSTACLE_HOP_STARTED;
}
static void OverworldWildSpawns_SetObjectFacing(LocalMapObject *object, u8 direction)
{ (void)object; (void)direction; }
static void OverworldWildSpawns_SetObjectFlags(LocalMapObject *object, int flags)
{ (void)object; (void)flags; }
static int OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(
    OverworldWildSpawnState *state, void *fieldSystem, int slot,
    LocalMapObject *object, u8 direction, int distance, int targetX, int targetY,
    void *profile, int flags, u8 travelTime)
{
    (void)state; (void)fieldSystem; (void)slot; (void)object; (void)direction;
    (void)distance; (void)targetX; (void)targetY; (void)profile; (void)flags;
    (void)travelTime; startCalls++; return OVERWORLD_MOTION_DECISION_ACCEPTED;
}
""" + (
        "static BOOL OverworldWildSpawns_IsStopSkidTileOpen("
        "const OverworldWildDirectionStepContext *stepContext, int x, int y) {"
        + bodies["OverworldWildSpawns_IsStopSkidTileOpen"] + "}\n"
        "static BOOL OverworldWildSpawns_IsStopSkidCorridorOpen("
        "const OverworldWildDirectionStepContext *stepContext, u8 direction, "
        "u8 distance, u8 turnDirection) {"
        + bodies["OverworldWildSpawns_IsStopSkidCorridorOpen"] + "}\n"
        "static BOOL OverworldWildSpawns_StartMomentumWalkStep("
        "const OverworldWildDirectionStepContext *stepContext, "
        "const OverworldActorWalkPolicyCall *call) {"
        + bodies["OverworldWildSpawns_StartMomentumWalkStep"] + "}\n"
    ) + r"""
static void Check(BOOL condition, const char *message)
{ if (!condition) { fprintf(stderr, "%s\n", message); exit(1); } }
int main(void)
{
    OverworldWildSpawnState state = {0};
    LocalMapObject object = {10, 10};
    OverworldWildDirectionStepContext context = {&state, NULL, &object, NULL, 0, 0};
    OverworldActorWalkPolicyCall call = {3, 3, 4,
        OVERWORLD_ACTOR_WALK_STEP_VALIDATE, {0, 0, 0, 0}};

    Check(OverworldWildSpawns_IsStopSkidCorridorOpen(&context, 3, 2, 0),
        "open two-tile skid and north turn was rejected");
    blocked[10][11] = 1;
    Check(!OverworldWildSpawns_IsStopSkidCorridorOpen(&context, 3, 2, 0),
        "blocked skid tile was accepted");
    memset(blocked, 0, sizeof(blocked));
    blocked[9][12] = 1;
    Check(!OverworldWildSpawns_IsStopSkidCorridorOpen(&context, 3, 2, 0),
        "blocked post-skid turn tile was accepted");
    memset(blocked, 0, sizeof(blocked));
    blocked[8][12] = 1;
    Check(OverworldWildSpawns_IsStopSkidCorridorOpen(&context, 3, 2, 0),
        "path planner checked beyond the first post-skid step");

    memset(blocked, 0, sizeof(blocked));
    blocked[10][12] = 1;
    blocked[10][13] = 1;
    Check(OverworldWildSpawns_StartMomentumWalkStep(&context, &call)
            && startCalls == 1,
        "clear ordinary Walk step could not approach a long wall");
    lane.hopMinDistance = 2;
    lane.hopMaxDistance = 2;
    lane.hopAllowVerticalObstacles = OW_WILD_BEHAVIOR_BOOL_YES;
    Check(OverworldWildSpawns_StartMomentumWalkStep(&context, &call)
            && startCalls == 2,
        "Sprint still required a Hop landing for an ordinary Walk step");
    occupied[10][11] = 1;
    Check(!OverworldWildSpawns_StartMomentumWalkStep(&context, &call)
            && startCalls == 2,
        "ordinary Walk entered an occupied immediate tile");
    occupied[10][11] = 0;
    object.xCurr = 11;
    OverworldActorWalkPolicyCall stopSkid = {3, 3, 4,
        OVERWORLD_ACTOR_WALK_STEP_VALIDATE
            | OVERWORLD_ACTOR_WALK_STEP_SKID
            | OVERWORLD_ACTOR_WALK_STEP_STOP_SKID
            | OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH,
        {0, 1, 0, 0}};
    Check(!OverworldWildSpawns_StartMomentumWalkStep(&context, &stopSkid)
            && startCalls == 2,
        "stop skid crossed the wall from the adjacent tile");
    object.xCurr = 10;
    OverworldActorWalkPolicyCall turn = {3, 0, 4,
        OVERWORLD_ACTOR_WALK_STEP_VALIDATE
            | OVERWORLD_ACTOR_WALK_STEP_SKID
            | OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH,
        {0, 1, 0, 0}};
    turn.reserved[OVERWORLD_ACTOR_WALK_POLICY_SKID_PATH_TILES_INDEX] = 2;
    Check(!OverworldWildSpawns_StartMomentumWalkStep(&context, &turn)
            && startCalls == 2,
        "turn skid crossed a blocked second skid tile");
    turn.reserved[OVERWORLD_ACTOR_WALK_POLICY_SKID_PATH_TILES_INDEX] = 1;
    blocked[9][11] = 1;
    Check(!OverworldWildSpawns_StartMomentumWalkStep(&context, &turn)
            && startCalls == 2,
        "turn skid entered a blocked turn exit");
    blocked[9][11] = 0;
    Check(OverworldWildSpawns_StartMomentumWalkStep(&context, &turn)
            && startCalls == 3,
        "clear actual turn skid was rejected");

    memset(blocked, 0, sizeof(blocked));
    blocked[10][11] = 1;
    Check(!OverworldWildSpawns_IsStopSkidCorridorOpen(&context, 7, 1, 0),
        "blocked diagonal skid side tile was accepted");
    memset(blocked, 0, sizeof(blocked));
    blocked[9][11] = 1;
    Check(!OverworldWildSpawns_IsStopSkidCorridorOpen(&context, 3, 1, 4),
        "blocked diagonal turn side tile was accepted");
    puts("Wild clear approach and actual skid safety passed");
    return 0;
}
"""


class TurnSkidPathPlanningTests(unittest.TestCase):
    def test_clear_walk_approach_and_actual_skid_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="turn-skid-path-") as directory:
            source = Path(directory) / "fixture.c"
            binary = Path(directory) / "fixture"
            source.write_text(harness_source())
            command = shlex.split("cc") + [
                "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                str(source), "-o", str(binary),
            ]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_validation_precedes_facing_and_wander_owns_tile_validation(self) -> None:
        bodies = function_bodies()
        probe = bodies["OverworldWildSpawns_TryStartLedgeJumpCommand"]
        self.assertLess(probe.index("if (probeOnly)"), probe.index(
            "state->movementStagedHopPending[slot] ="
        ))
        start = bodies["OverworldWildSpawns_StartMomentumWalkStep"]
        self.assertLess(
            start.index("OverworldWildSpawns_IsStopSkidCorridorOpen"),
            start.index("OverworldWildSpawns_SetObjectFacing"),
        )
        single = bodies["OverworldWildSpawns_TryStartSingleDirectionMovementStep"]
        non_wander = single.index("locomotion != OW_WILD_BEHAVIOR_LOCOMOTION_WANDER")
        allowed_tile = single.index("OverworldWildSpawns_IsBehaviorAllowedMovementTile")
        canopy = single.index("OverworldWildSpawns_TryStartCanopyEntryHop")
        wander = single.index("locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER")
        self.assertLess(non_wander, allowed_tile)
        self.assertLess(allowed_tile, canopy)
        self.assertLess(canopy, wander)


if __name__ == "__main__":
    unittest.main()
