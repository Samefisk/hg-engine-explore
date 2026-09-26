"""Host regression for explicit off-screen spawn Hop clearance."""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PLANNER = ROOT / "src/pokemon_move_history_task6_overlay/overworld_actor_hop_planner.c"


def function(source, name, result):
    matches = list(re.finditer(r"\b" + name + r"\s*\([^;{}]*\)\s*\{", source))
    if len(matches) != 1:
        raise AssertionError(f"expected one {name} body")
    start = matches[0]
    depth = 1
    for end in range(start.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return f"static {result} " + source[start.start():end + 1]
    raise AssertionError(f"unterminated {name} body")


def harness_source():
    product = PLANNER.read_text()
    bodies = "\n".join(
        (
            function(product, "OverworldActorHopPlanner_LerpFx32", "s32"),
            function(
                product,
                "OverworldActorHopPlanner_PlanTrajectory",
                "OverworldMotionDecision",
            ),
        )
    )
    return PRELUDE + bodies + DRIVER


PRELUDE = r"""
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int16_t s16;
typedef int32_t s32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define FX32_SHIFT 12
#define OVERWORLD_HOP_OBSTACLE_CLEARANCE_FX32 (1 << FX32_SHIFT)
#define OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY 1
#define OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY 2
#define OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY (1u << 0)
#define OW_WILD_SURFACE_ID_NATIVE_GROUND 0xFFFE
#define OW_WILD_SURFACE_ID_NATIVE_CANOPY 0xFFFD

typedef enum OverworldMotionDecision {
    OVERWORLD_MOTION_DECISION_ACCEPTED = 0,
    OVERWORLD_MOTION_DECISION_BLOCKED = 2,
    OVERWORLD_MOTION_DECISION_PROFILE = 8,
} OverworldMotionDecision;
typedef struct FieldSystem { int unused; } FieldSystem;
typedef struct LocalMapObject { int unused; } LocalMapObject;
typedef struct OverworldWildSurfaceCatalog { int unused; } OverworldWildSurfaceCatalog;
typedef struct OverworldWildSurfaceHit {
    s32 height;
    u16 surfaceId;
    u8 surfaceType;
    u8 nodeId;
} OverworldWildSurfaceHit;
typedef struct OverworldWildBehaviorProfileData {
    u8 hopTime;
    u8 spawnHopTime;
    u8 hopElevationTimeScale;
    u8 hopElevationArcScale;
    u8 hopAllowVerticalObstacles;
} OverworldWildBehaviorProfileData;
typedef struct OverworldActorHopPlanCall {
    const void *profile;
    const OverworldWildBehaviorProfileData *lane;
    FieldSystem *fieldSystem;
    const OverworldWildSurfaceCatalog *surfaceCatalog;
    LocalMapObject *object;
    s32 startBaseY;
    s32 targetBaseY;
    s16 startX;
    s16 startY;
    s16 targetX;
    s16 targetY;
    s16 deltaX;
    s16 deltaY;
    u32 trajectory;
    u8 operation;
    u8 spotState;
    u8 direction;
    u8 distance;
} OverworldActorHopPlanCall;
typedef struct SurfaceEntry {
    u32 (*calculateJumpTrajectory)(u8, u8, s32, u16);
    s32 (*calculateJumpArc)(u32, u32, u8);
} SurfaceEntry;
typedef struct RuntimeEntry {
    BOOL (*querySurface)(FieldSystem *, const OverworldWildSurfaceCatalog *,
        int, int, OverworldWildSurfaceHit *);
    s32 (*getGroundBaseY)(FieldSystem *, const OverworldWildSurfaceCatalog *,
        LocalMapObject *, int, int);
} RuntimeEntry;
static SurfaceEntry surfaceEntry;
static RuntimeEntry runtimeEntry;
#define OVERWORLD_WILD_SURFACE_SERVICE_ENTRY (&surfaceEntry)
#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY (&runtimeEntry)
"""


DRIVER = r"""
static unsigned queryCalls;
static unsigned groundCalls;

static u32 CalculateTrajectory(u8 time, u8 distance, s32 delta, u16 scales)
{
    (void)time; (void)distance; (void)delta; (void)scales;
    return (1u << 16) | 16u;
}

static s32 CalculateArc(u32 elapsed, u32 total, u8 height)
{
    (void)elapsed; (void)total; (void)height;
    return 1;
}

static BOOL QuerySurface(
    FieldSystem *field,
    const OverworldWildSurfaceCatalog *catalog,
    int x,
    int y,
    OverworldWildSurfaceHit *hit)
{
    (void)field; (void)catalog; (void)x; (void)y;
    queryCalls++;
    hit->height = 0;
    hit->surfaceId = OW_WILD_SURFACE_ID_NATIVE_GROUND;
    return TRUE;
}

static s32 GetGroundBaseY(
    FieldSystem *field,
    const OverworldWildSurfaceCatalog *catalog,
    LocalMapObject *object,
    int x,
    int y)
{
    (void)field; (void)catalog; (void)object; (void)x; (void)y;
    groundCalls++;
    return 1 << 20;
}

static OverworldActorHopPlanCall Call(
    const OverworldWildBehaviorProfileData *lane,
    FieldSystem *field,
    const OverworldWildSurfaceCatalog *catalog,
    LocalMapObject *object,
    u8 flags)
{
    OverworldActorHopPlanCall call;
    memset(&call, 0, sizeof(call));
    call.lane = lane;
    call.fieldSystem = field;
    call.surfaceCatalog = catalog;
    call.object = object;
    call.startX = 0;
    call.startY = 0;
    call.targetX = 8;
    call.targetY = 0;
    call.distance = 8;
    call.operation = OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY;
    call.spotState = flags;
    return call;
}

int main(void)
{
    OverworldWildBehaviorProfileData lane = {8, 8, 0, 0, 0};
    OverworldWildSurfaceCatalog catalog = {0};
    LocalMapObject object = {0};
    FieldSystem field = {0};
    OverworldActorHopPlanCall ordinary;
    OverworldActorHopPlanCall spawn;

    surfaceEntry.calculateJumpTrajectory = CalculateTrajectory;
    surfaceEntry.calculateJumpArc = CalculateArc;
    runtimeEntry.querySurface = QuerySurface;
    runtimeEntry.getGroundBaseY = GetGroundBaseY;

    ordinary = Call(&lane, &field, &catalog, &object, 0);
    assert(OverworldActorHopPlanner_PlanTrajectory(&ordinary)
        == OVERWORLD_MOTION_DECISION_ACCEPTED);
    assert(queryCalls == 7);
    assert(groundCalls == 0);

    queryCalls = 0;
    groundCalls = 0;
    spawn = Call(
        &lane,
        &field,
        &catalog,
        &object,
        OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY);
    assert(OverworldActorHopPlanner_PlanTrajectory(&spawn)
        == OVERWORLD_MOTION_DECISION_BLOCKED);
    assert(queryCalls == 0);
    assert(groundCalls == 1);
    return 0;
}
"""


class HopSpawnEntryFlagTests(unittest.TestCase):
    def test_normal_eight_tile_hop_keeps_normal_obstacle_rules(self):
        with tempfile.TemporaryDirectory(prefix="hop-spawn-entry-") as directory:
            source = Path(directory) / "hop_spawn_entry.c"
            binary = Path(directory) / "hop_spawn_entry"
            source.write_text(harness_source())
            compiled = subprocess.run(
                [
                    "cc",
                    "-std=c11",
                    "-O2",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-Wno-sign-compare",
                    str(source),
                    "-o",
                    str(binary),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                compiled.returncode,
                0,
                compiled.stdout + compiled.stderr,
            )
            completed = subprocess.run(
                [str(binary)], capture_output=True, text=True
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )

    def test_distance_is_not_the_spawn_entry_switch(self):
        source = PLANNER.read_text()
        body = function(
            source,
            "OverworldActorHopPlanner_PlanTrajectory",
            "OverworldMotionDecision",
        )
        self.assertIn("OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY", body)
        self.assertNotRegex(body, r"distance\s*[!=]=\s*(8|16)")


if __name__ == "__main__":
    unittest.main()
