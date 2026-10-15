"""Host regression for explicit off-screen spawn Hop clearance."""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PLANNER = ROOT / "src/pokemon_move_history_task6_overlay/overworld_actor_hop_planner.c"
LERP = ROOT / "src/pokemon_move_history_overlay/overworld_hop_lerp.c"
GEOMETRY = ROOT / "src/pokemon_move_history_overlay/overworld_hop_geometry.c"
GEOMETRY_HEADER = ROOT / "src/pokemon_move_history_task6_overlay/overworld_actor_hop_geometry.h"
MOTION_HEADER = ROOT / "include/overworld_motion_model.h"
MOTION_SOURCE = ROOT / "lib/overworld/overworld_motion_model.c"
ACTOR_HEADER = ROOT / "include/overworld_actor_system_internal.h"


def planner_macros():
    header = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
    macro = re.search(r"^#define OW_WILD_BEHAVIOR_SKID_BOOLEAN[^\n]+$", header, re.M)
    if macro is None:
        raise AssertionError("missing current packed obstacle option")
    flags = (ROOT / "include/overworld_actor_system_internal.h").read_text()
    slam = re.search(r"^#define OVERWORLD_ACTOR_HOP_PLAN_FLAG_SLAM[^\n]+$", flags, re.M)
    if slam is None:
        raise AssertionError("missing typed Slam trajectory flag")
    call_type = re.search(
        r"typedef struct OverworldActorHopPlanCall\s*\{.*?\}\s*OverworldActorHopPlanCall;",
        ACTOR_HEADER.read_text(), re.S)
    kind_type = re.search(
        r"typedef enum OverworldMotionKind\s*\{.*?\}\s*OverworldMotionKind;",
        MOTION_HEADER.read_text(), re.S)
    if call_type is None or kind_type is None:
        raise AssertionError("missing current Hop packet or Motion kind")
    return ("#ifndef OVERWORLD_MOTION_HOST\n#define OVERWORLD_MOTION_HOST 1\n#endif\n"
            "#ifndef OVERWORLD_ACTOR_SYSTEM_HOST\n#define OVERWORLD_ACTOR_SYSTEM_HOST 1\n#endif\n"
            + macro.group(0) + "\n" + slam.group(0) + "\n"
            + call_type.group(0) + "\n" + kind_type.group(0) + "\n")


def function(source, name, result):
    if name == "OverworldActorHopPlanner_LerpFx32":
        source = LERP.read_text()
    matches = [match for match in re.finditer(
        r"\b" + name + r"\s*\([^;{}]*\)\s*\{", source)
        if not source[source.rfind("\n", 0, match.start()) + 1:match.start()].strip()
        or re.search(r"\b" + re.escape(result) + r"\b",
                     source[source.rfind("\n", 0, match.start()) + 1:match.start()])]
    if len(matches) != 1:
        raise AssertionError(f"expected one {name} body")
    start = matches[0]
    depth = 1
    for end in range(start.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return f"static {result} " + source[start.start():end + 1]
    raise AssertionError(f"unterminated {name} body")


def trajectory_bodies(native):
    geometry_type = re.search(
        r"typedef struct OverworldActorHopGeometry\s*\{.*?\}\s*OverworldActorHopGeometry;",
        GEOMETRY_HEADER.read_text(), re.S)
    if geometry_type is None:
        raise AssertionError("missing private crossed-cell state")
    motion = MOTION_SOURCE.read_text()
    return "\n".join((
        function(MOTION_HEADER.read_text(), "OverworldMotion_SlamUnitHeight", "u32"),
        function(MOTION_HEADER.read_text(), "OverworldMotion_SlamRiseUnitHeight", "u32"),
        function(motion, "OverworldMotion_SlamPhasesValid", "u8"),
        PHASE_CALL_ADAPTER,
        geometry_type.group(0),
        function(motion, "OverworldActorHopGeometry_Init", "void"),
        function(GEOMETRY.read_text(), "OverworldActorHopGeometry_NextCell", "void"),
        function(native, "OverworldMotion_SlamUnitArc", "s32"),
        function(native, "OverworldActorHopPlanner_CallArc", "s32"),
        function(native, "OverworldActorHopPlanner_LerpFx32", "s32"),
        function(native, "OverworldActorHopPlanner_PlanTrajectory", "OverworldMotionDecision"),
    ))


PHASE_CALL_ADAPTER = r"""
/* The fixed native leaf receives duration minus hang. Reconstruct the same
 * portable shared predicate; its u16 duration must not wrap a negative input.
 * Planner has already bounded kind/peak and reads rise from its u8 alias. */
static u32 OverworldMotion_SlamPhaseCheck(
    u32 kind, u32 peak, u32 rise, s32 durationMinusHang)
{
    return durationMinusHang >= 0
        && OverworldMotion_SlamPhasesValid(
            kind, durationMinusHang, peak, rise, 0);
}
"""



def harness_source():
    product = PLANNER.read_text()
    bodies = trajectory_bodies(product)
    return PRELUDE + planner_macros() + bodies + DRIVER


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
#define OVERWORLD_ACTOR_HOP_PLAN_FLAG_STRICT_HEIGHT (1u << 1)
#define OW_WILD_SURFACE_ID_NATIVE_GROUND 0xFFFE
#define OW_WILD_SURFACE_ID_NATIVE_CANOPY 0xFFFD

typedef enum OverworldMotionDecision {
    OVERWORLD_MOTION_DECISION_ACCEPTED = 0,
    OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY = 1,
    OVERWORLD_MOTION_DECISION_BLOCKED = 2,
    OVERWORLD_MOTION_DECISION_PROFILE = 8,
} OverworldMotionDecision;
typedef struct FieldSystem { int unused; } FieldSystem;
typedef struct LocalMapObject { s32 posVec[3]; u32 flags; } LocalMapObject;
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
typedef struct SurfaceEntry {
    u32 (*calculateJumpTrajectory)(u8, u8, s32, u16);
    s32 (*calculateJumpArc)(u16, u16, u8);
} SurfaceEntry;
typedef struct RuntimeEntry {
    BOOL (*querySurface)(FieldSystem *, const OverworldWildSurfaceCatalog *,
        int, int, OverworldWildSurfaceHit *);
    BOOL (*resolveBaseYAt)(FieldSystem *, const OverworldWildSurfaceHit *,
        s32, u32, int, int, s32 *);
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

static s32 CalculateArc(u16 elapsed, u16 total, u8 height)
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

static BOOL ResolveBaseYAt(
    FieldSystem *field,
    const OverworldWildSurfaceHit *hit,
    s32 origin,
    u32 flags,
    int x,
    int y,
    s32 *height)
{
    (void)field; (void)hit; (void)origin; (void)flags; (void)x; (void)y;
    groundCalls++;
    *height = 1 << 20;
    return TRUE;
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
    runtimeEntry.resolveBaseYAt = ResolveBaseYAt;

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
    assert(queryCalls == 1);
    assert(groundCalls == 1);
    return 0;
}
"""


ANGLED_DRIVER = r"""
#include <stdio.h>
#define CHECK(test, message) do { \
    if (!(test)) { fprintf(stderr, "crossed-cell invariant failed: %s\n", message); return 1; } \
} while (0)
static int queriedX[32], queriedY[32];
static unsigned queryCount, resolveCount, arcCount;
static u32 arcElapsed[2], arcTotal[2];
static int blockerX, blockerY;
static unsigned queryMode;
static BOOL unresolved;
static u32 duration = 16, initialArc;
static s32 heightDelta;
static u16 elevationScales;
static u32 Calculate(u8 time, u8 distance, s32 delta, u16 scales)
{
    assert(time == 8 && distance != 0);
    heightDelta = delta;
    elevationScales = scales;
    return (initialArc << 16) | duration;
}
static s32 Arc(u16 elapsed, u16 total, u8 height)
{
    assert(height == 1);
    if (arcCount < 2) { arcElapsed[arcCount] = elapsed; arcTotal[arcCount] = total; }
    arcCount++;
    return 4096;
}
static BOOL Query(FieldSystem *field, const OverworldWildSurfaceCatalog *catalog,
    int x, int y, OverworldWildSurfaceHit *hit)
{
    assert(field && catalog && queryCount < 32);
    queriedX[queryCount] = x;
    queriedY[queryCount++] = y;
    if (queryMode == 0 || x != blockerX || y != blockerY) return FALSE;
    hit->height = 8192;
    hit->surfaceId = queryMode == 2 ? OW_WILD_SURFACE_ID_NATIVE_GROUND : 2;
    return TRUE;
}
static BOOL Resolve(FieldSystem *field, const OverworldWildSurfaceHit *hit,
    s32 origin, u32 flags, int x, int y, s32 *out)
{
    assert(field && origin == 0 && flags == 0);
    (void)x; (void)y;
    resolveCount++;
    if (unresolved && hit != NULL) return FALSE;
    *out = hit != NULL ? hit->height : 0;
    return TRUE;
}
static void Reset(void)
{
    queryCount = resolveCount = arcCount = 0;
    queryMode = 0;
    unresolved = FALSE;
    initialArc = 0;
    duration = 16;
}
static OverworldActorHopPlanCall Call(OverworldWildBehaviorProfileData *lane,
    FieldSystem *field, OverworldWildSurfaceCatalog *catalog, LocalMapObject *object,
    int dx, int dy)
{
    OverworldActorHopPlanCall call = {0};
    call.lane = lane; call.fieldSystem = field; call.surfaceCatalog = catalog; call.object = object;
    call.operation = OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY;
    call.startX = call.startY = 100;
    call.targetX = 100 + dx; call.targetY = 100 + dy;
    int ax = dx < 0 ? -dx : dx, ay = dy < 0 ? -dy : dy;
    call.distance = ax > ay ? ax : ay;
    return call;
}
int main(void)
{
    const int longCells[][2] = {
        {1,0},{1,1},{2,1},{2,2},{3,2},{4,2},
        {4,3},{5,3},{6,3},{6,4},{7,4},{7,5}
    };
    const int shortCells[][2] = {{1,0},{1,1},{2,1},{2,2}};
    OverworldWildBehaviorProfileData lane = {8,8,0,0,0};
    FieldSystem field = {0}; OverworldWildSurfaceCatalog catalog = {0}; LocalMapObject object = {0};
    surfaceEntry.calculateJumpTrajectory = Calculate; surfaceEntry.calculateJumpArc = Arc;
    runtimeEntry.querySurface = Query; runtimeEntry.resolveBaseYAt = Resolve;
    /* This cell lies between the old distance-center probes. Keep this first
     * so the old-sampling control fails on the real blocker claim itself. */
    OverworldActorHopPlanCall call = Call(&lane, &field, &catalog, &object, 8, 5);
    Reset(); queryMode = 1; blockerX = blockerY = 102;
    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call) == OVERWORLD_MOTION_DECISION_BLOCKED,
        "narrow blocker was skipped");
    CHECK(resolveCount == 1, "one obstacle height read");
    /* Fixed crossed-cell lists include cells skipped by distance-center samples.
     * Reflect and swap the same authored segments in all eight orientations. */
    for (unsigned shortPath = 0; shortPath < 2; shortPath++) {
        const int (*cells)[2] = shortPath ? shortCells : longCells;
        unsigned count = shortPath ? 4 : 12;
        for (int sx = -1; sx <= 1; sx += 2) for (int sy = -1; sy <= 1; sy += 2)
        for (unsigned swap = 0; swap < 2; swap++) {
            int dx = shortPath ? 3 : 8, dy = shortPath ? 2 : 5;
            OverworldActorHopPlanCall call = Call(&lane, &field, &catalog, &object,
                sx * (swap ? dy : dx), sy * (swap ? dx : dy));
            Reset();
            CHECK(OverworldActorHopPlanner_PlanTrajectory(&call) == OVERWORLD_MOTION_DECISION_ACCEPTED,
                "clear arbitrary-angle segment");
            CHECK(queryCount == count && resolveCount == 0 && call.trajectory == 16,
                "all crossed cells, unchanged clear duration");
            for (unsigned i = 0; i < count; i++) {
                CHECK(queriedX[i] == 100 + sx * cells[i][swap ? 1 : 0]
                    && queriedY[i] == 100 + sy * cells[i][swap ? 0 : 1],
                    "exact boundary order across narrow cells");
            }
        }
    }
    /* The same shared clearance rule raises an allowed arc; duration stays fixed. */
    Reset(); queryMode = 1; lane.hopAllowVerticalObstacles = 1;
    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call) == OVERWORLD_MOTION_DECISION_ACCEPTED
        && call.trajectory == (4u << 16 | 16u), "shared vertical clearance adjustment");
    CHECK(arcCount == 2 && arcElapsed[0] == 4 && arcElapsed[1] == 5
        && arcTotal[0] == 16 && arcTotal[1] == 16, "exact narrow-cell entry/exit clock");
    Reset(); queryMode = 1; call.operation = OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY;
    call.trajectory = 1;
    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call) == OVERWORLD_MOTION_DECISION_BLOCKED,
        "flat motion cannot raise its arc");
    CHECK(call.trajectory == 1, "flat authored duration stays fixed");
    Reset(); queryMode = 2; call.operation = OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY;
    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call) == OVERWORLD_MOTION_DECISION_ACCEPTED
        && resolveCount == 0, "ordinary Hop ignores native ground");
    Reset(); queryMode = 2; call.spotState = OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY;
    lane.hopAllowVerticalObstacles = 0;
    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call) == OVERWORLD_MOTION_DECISION_ACCEPTED
        && resolveCount == 12 && call.trajectory == (4u << 16 | 16u),
        "spawn entry retains native-ground clearance");
    Reset(); queryMode = 1; unresolved = TRUE;
    call.spotState = OVERWORLD_ACTOR_HOP_PLAN_FLAG_STRICT_HEIGHT;
    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call) == OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY,
        "strict failed height read retries");
    /* Geometry still crosses the narrow cell with a short, legal output clock. */
    Reset(); queryMode = 1; duration = 2; call.spotState = 0;
    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call) == OVERWORLD_MOTION_DECISION_BLOCKED,
        "short duration cannot skip crossed cells");
    /* Existing cardinal and 45-degree probes keep the same seven samples. */
    for (unsigned diagonal = 0; diagonal < 2; diagonal++) {
        Reset(); call = Call(&lane, &field, &catalog, &object, 8, diagonal ? 8 : 0);
        CHECK(OverworldActorHopPlanner_PlanTrajectory(&call) == OVERWORLD_MOTION_DECISION_ACCEPTED
            && queryCount == 7 && call.trajectory == 16, "ordinary Hop fast path");
        for (unsigned i = 0; i < 7; i++)
            CHECK(queriedX[i] == 101 + (int)i && queriedY[i] == (diagonal ? 101 + (int)i : 100),
                "ordinary Hop probe coordinates");
    }
    /* Signed target height and packed elevation scales still reach the owner. */
    Reset(); lane.hopElevationTimeScale = 2; lane.hopElevationArcScale = 3;
    call = Call(&lane, &field, &catalog, &object, 3, 2);
    call.startBaseY = 32768; call.targetBaseY = 8192;
    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call) == OVERWORLD_MOTION_DECISION_ACCEPTED
        && heightDelta == -24576 && elevationScales == 770, "signed height and elevation scales");
    return 0;
}
"""


class HopSpawnEntryFlagTests(unittest.TestCase):
    def test_slam_uses_exact_rise_clearance_without_raising_peak(self):
        self._run_slam_harness(PLANNER.read_text(), should_pass=True)

    def test_slam_known_bad_shortcut_and_peak_raise_are_rejected(self):
        native = PLANNER.read_text()
        mutations = (
            ("if (!slam && totalFrames < 2)", "if (totalFrames < 2)"),
            ("if (slam || call->operation ==", "if (call->operation =="),
        )
        for old, new in mutations:
            with self.subTest(guard=old):
                self.assertEqual(native.count(old), 1)
                self._run_slam_harness(native.replace(old, new), should_pass=False)

    def _run_slam_harness(self, native, *, should_pass):
        source = CROSS_HEIGHT_PRELUDE + planner_macros() + trajectory_bodies(native) + "\n" + SLAM_DRIVER
        with tempfile.TemporaryDirectory(prefix="hop-slam-clearance-") as directory:
            unit = Path(directory) / "trajectory.c"
            binary = Path(directory) / "trajectory"
            unit.write_text(source)
            compiled = subprocess.run(
                ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-Wno-sign-compare", str(unit), "-o", str(binary)],
                capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            if should_pass:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            else:
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("Slam clearance:", result.stderr)

    def test_actual_trajectory_uses_signed_target_height_and_keeps_clearance(self):
        native = PLANNER.read_text()
        source = CROSS_HEIGHT_PRELUDE + planner_macros() + trajectory_bodies(native) + CROSS_HEIGHT_DRIVER
        extra = []
        with tempfile.TemporaryDirectory(prefix="overworld-cross-height-") as directory:
            unit = Path(directory) / "height.c"; binary = Path(directory) / "height"
            unit.write_text(CROSS_HEIGHT_HOST_TYPES + source)
            compiled = subprocess.run(["cc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-Wno-sign-compare", "-DOVERWORLD_BEHAVIOR_HOST", "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-DOVERWORLD_VISION_HOST", "-I", str(ROOT / "include"), str(unit), *extra, "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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

    def test_arbitrary_angle_checks_every_crossed_cell_and_keeps_shared_rules(self):
        self._run_angled_harness(PLANNER.read_text(), should_pass=True)

    def test_truncated_crossed_cell_scan_rejects_the_narrow_blocker(self):
        native = PLANNER.read_text()
        old = "for (;;)"
        self.assertEqual(native.count(old), 1)
        self._run_angled_harness(native.replace(old,
            "for (unsigned truncated = 1; truncated < call->distance / 2; truncated++)"),
            should_pass=False)

    def _run_angled_harness(self, native, *, should_pass):
        source = CROSS_HEIGHT_PRELUDE + planner_macros() + trajectory_bodies(native) + ANGLED_DRIVER
        with tempfile.TemporaryDirectory(prefix="hop-crossed-cell-") as directory:
            unit = Path(directory) / "trajectory.c"
            binary = Path(directory) / "trajectory"
            unit.write_text(source)
            compiled = subprocess.run(
                ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-Wno-sign-compare", str(unit), "-o", str(binary)],
                capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            if should_pass:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            else:
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("crossed-cell invariant failed: narrow blocker was skipped", result.stderr)

    def test_distance_is_not_the_spawn_entry_switch(self):
        source = PLANNER.read_text()
        body = function(
            source,
            "OverworldActorHopPlanner_PlanTrajectory",
            "OverworldMotionDecision",
        )
        self.assertIn("OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY", body)
        self.assertNotRegex(body, r"distance\s*[!=]=\s*(8|16)")



CROSS_HEIGHT_HOST_TYPES = '\n/* The stock types.h declares ARM-only long_call imports. This host boundary\n * supplies the same scalar widths, not engine imports or guest layouts. */\n#include <stdint.h>\n#include <stddef.h>\n#ifdef __clang__\n#pragma clang diagnostic ignored "-Wunknown-attributes"\n#endif\n#define TYPES_H\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef uint64_t u64;\ntypedef int8_t s8;typedef int16_t s16;typedef int32_t s32;typedef int64_t s64;\ntypedef int BOOL;typedef s32 fx32;\ntypedef struct { fx32 x,y,z; } VecFx32;\n#define TRUE 1\n#define FALSE 0\n#define ALIGN4 __attribute__((aligned(4)))\n#define PACKED __attribute__((packed))\n#define LONG_CALL\n#define NELEMS(a) (sizeof(a)/sizeof((a)[0]))\n'
CROSS_HEIGHT_PRELUDE = '\n#include <assert.h>\n#include <stdint.h>\n#include <string.h>\ntypedef uint8_t u8;\ntypedef uint16_t u16;\ntypedef uint32_t u32;\ntypedef int16_t s16;\ntypedef int32_t s32;\ntypedef int BOOL;\n#define TRUE 1\n#define FALSE 0\n#define FX32_SHIFT 12\n#define OVERWORLD_HOP_OBSTACLE_CLEARANCE_FX32 (1 << FX32_SHIFT)\n#define OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY 1\n#define OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY 2\n#define OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY (1u << 0)\n#define OVERWORLD_ACTOR_HOP_PLAN_FLAG_STRICT_HEIGHT (1u << 1)\n#define OW_WILD_SURFACE_ID_NATIVE_GROUND 0xFFFE\n#define OW_WILD_SURFACE_ID_NATIVE_CANOPY 0xFFFD\n\ntypedef enum OverworldMotionDecision {\n    OVERWORLD_MOTION_DECISION_ACCEPTED = 0,\n    OVERWORLD_MOTION_DECISION_BLOCKED = 2,\n    OVERWORLD_MOTION_DECISION_PROFILE = 8,\n    OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY = 1,\n} OverworldMotionDecision;\ntypedef struct FieldSystem { int unused; } FieldSystem;\ntypedef struct LocalMapObject { s32 posVec[3]; u32 flags; } LocalMapObject;\ntypedef struct OverworldWildSurfaceCatalog { int unused; } OverworldWildSurfaceCatalog;\ntypedef struct OverworldWildSurfaceHit {\n    s32 height;\n    u16 surfaceId;\n    u8 surfaceType;\n    u8 nodeId;\n} OverworldWildSurfaceHit;\ntypedef struct OverworldWildBehaviorProfileData {\n    u8 hopTime;\n    u8 spawnHopTime;\n    u8 hopElevationTimeScale;\n    u8 hopElevationArcScale;\n    u8 hopAllowVerticalObstacles;\n} OverworldWildBehaviorProfileData;\ntypedef struct SurfaceEntry {\n    u32 (*calculateJumpTrajectory)(u8, u8, s32, u16);\n    s32 (*calculateJumpArc)(u16, u16, u8);\n} SurfaceEntry;\ntypedef struct RuntimeEntry {\n    BOOL (*querySurface)(FieldSystem *, const OverworldWildSurfaceCatalog *,\n        int, int, OverworldWildSurfaceHit *);\n    BOOL (*resolveBaseYAt)(FieldSystem *, const OverworldWildSurfaceHit *, s32, u32, int, int, s32 *);\n} RuntimeEntry;\nstatic SurfaceEntry surfaceEntry;\nstatic RuntimeEntry runtimeEntry;\n#define OVERWORLD_WILD_SURFACE_SERVICE_ENTRY (&surfaceEntry)\n#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY (&runtimeEntry)\n'
CROSS_HEIGHT_DRIVER = '\nstatic s32 lastDelta,obstacleHeight;\nstatic unsigned trajectoryCalls,supportCalls;\nstatic BOOL obstacle,unknown;\nstatic u32 Calculate(u8 time,u8 distance,s32 delta,u16 scales) {\n    assert(time==12 && distance>0 && scales==0);lastDelta=delta;trajectoryCalls++;return 12;\n}\nstatic s32 Arc(u16 elapsed,u16 total,u8 height) {(void)elapsed;(void)total;return height;}\nstatic BOOL Query(FieldSystem *f,const OverworldWildSurfaceCatalog *c,int x,int y,OverworldWildSurfaceHit *hit) {\n    (void)x;(void)y;assert(f && c);hit->surfaceId=2;hit->height=obstacleHeight;return obstacle;\n}\nstatic BOOL Resolve(FieldSystem *f,const OverworldWildSurfaceHit *hit,s32 origin,u32 flags,int x,int y,s32 *out) {\n    (void)origin;(void)flags;(void)x;(void)y;assert(f && hit);supportCalls++;if(unknown)return FALSE;*out=hit->height;return TRUE;\n}\nint main(void) {\n    OverworldWildBehaviorProfileData lane={12,12,0,0,0};\n    FieldSystem field={0};OverworldWildSurfaceCatalog catalog={0};LocalMapObject object={0};\n    OverworldActorHopPlanCall call={0};call.lane=&lane;call.fieldSystem=&field;call.surfaceCatalog=&catalog;call.object=&object;\n    call.operation=OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY;call.startX=10;call.startY=10;call.targetX=11;call.targetY=10;call.distance=1;\n    surfaceEntry.calculateJumpTrajectory=Calculate;surfaceEntry.calculateJumpArc=Arc;\n    runtimeEntry.querySurface=Query;runtimeEntry.resolveBaseYAt=Resolve;\n    const s32 starts[]={0,0x40000,0x80000};const s32 targets[]={0x80000,0x40000,0};\n    for(unsigned i=0;i<3;i++) {\n        call.startBaseY=starts[i];call.targetBaseY=targets[i];\n        assert(OverworldActorHopPlanner_PlanTrajectory(&call)==OVERWORLD_MOTION_DECISION_ACCEPTED);\n        assert(lastDelta==targets[i]-starts[i]);\n        assert(OverworldActorHopPlanner_LerpFx32(starts[i],targets[i],12,12)==targets[i]);\n    }\n    assert(trajectoryCalls==3 && supportCalls==0);\n    /* Height support remains strict for a real intermediate obstacle. */\n    call.distance=2;call.targetX=12;call.startBaseY=call.targetBaseY=0;\n    obstacle=TRUE;obstacleHeight=0x10000;\n    assert(OverworldActorHopPlanner_PlanTrajectory(&call)==OVERWORLD_MOTION_DECISION_BLOCKED);\n    call.spotState=OVERWORLD_ACTOR_HOP_PLAN_FLAG_STRICT_HEIGHT;unknown=TRUE;\n    assert(OverworldActorHopPlanner_PlanTrajectory(&call)==OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY);\n    return 0;\n}\n'

SLAM_DRIVER = '#include <stdio.h>\nstatic unsigned queries, resolves, stockTrajectoryCalls, stockArcCalls;\nstatic s32 obstacleHeight;\nstatic BOOL unresolved;\nstatic int obstacleX = 11;\n#define CHECK(c, label) do { if (!(c)) { fprintf(stderr,"Slam clearance: %s\\n",label); return 1; } } while (0)\nstatic u32 StockTrajectory(u8 time,u8 distance,s32 delta,u16 scales) {\n    (void)time;(void)distance;(void)delta;(void)scales;stockTrajectoryCalls++;\n    return (1u << 16) | 20u;\n}\nstatic s32 StockArc(u16 elapsed,u16 total,u8 peak) {\n    (void)elapsed;(void)total;stockArcCalls++;return peak;\n}\nstatic BOOL Query(FieldSystem *field,const OverworldWildSurfaceCatalog *catalog,\n    int x,int y,OverworldWildSurfaceHit *hit) {\n    assert(field && catalog);queries++;\n    assert(x != 18 || y != 13); /* Destination stays with normal landing owner. */\n    if(x != obstacleX || y != 10 || obstacleHeight == 0)return FALSE;\n    hit->height=obstacleHeight;hit->surfaceId=1;return TRUE;\n}\nstatic BOOL Resolve(FieldSystem *field,const OverworldWildSurfaceHit *hit,\n    s32 base,u32 flags,int x,int y,s32 *out) {\n    (void)base;(void)flags;(void)x;(void)y;assert(field && hit);resolves++;\n    if(unresolved)return FALSE;*out=hit->height;return TRUE;\n}\nstatic u32 Arc(u8 rise,u8 hang,u8 drop,u8 peak) {\n    return rise | (u32)hang << 8 | (u32)drop << 16 | (u32)peak << 24;\n}\nstatic void SetArc(OverworldActorHopPlanCall *call,u32 packed) {\n    call->arcRiseFrames=packed & 255;call->arcHangFrames=(packed >> 8) & 255;\n    call->trajectory=(packed & 255)+((packed >> 8) & 255)+((packed >> 16) & 255)\n        | ((packed >> 24) << 16);\n}\nstatic OverworldActorHopPlanCall Call(OverworldWildBehaviorProfileData *lane,\n    FieldSystem *field,OverworldWildSurfaceCatalog *catalog,LocalMapObject *object) {\n    OverworldActorHopPlanCall call={0};call.lane=lane;call.fieldSystem=field;\n    call.surfaceCatalog=catalog;call.object=object;call.startX=10;call.startY=10;\n    call.targetX=18;call.targetY=13;call.distance=8;\n    call.operation=OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY;\n    call.spotState=OVERWORLD_ACTOR_HOP_PLAN_FLAG_SLAM;\n    SetArc(&call,Arc(12,4,4,24));return call;\n}\nint main(void) {\n    OverworldWildBehaviorProfileData lane={12,12,0,0,1};\n    FieldSystem field={0};OverworldWildSurfaceCatalog catalog={0};LocalMapObject object={0};\n    OverworldActorHopPlanCall call;\n    surfaceEntry.calculateJumpTrajectory=StockTrajectory;surfaceEntry.calculateJumpArc=StockArc;\n    runtimeEntry.querySurface=Query;runtimeEntry.resolveBaseYAt=Resolve;\n    call=Call(&lane,&field,&catalog,&object);\n    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call)==OVERWORLD_MOTION_DECISION_ACCEPTED,\n        "clear default Slam accepted");\n    CHECK(call.trajectory == ((24u << 16) | 20u) && queries==10,\n        "default Slam keeps exact peak/total and all ten crossed cells");\n    CHECK(stockTrajectoryCalls==0 && stockArcCalls==0,\n        "Slam never calls the ordinary parabola planner");\n    /* Entry of the first crossed tile is exactly1/16 of rise. At peak24,\n     * its curved height11904 clears supported7808 plus normal4096 margin exactly. */\n    obstacleHeight=7808;call=Call(&lane,&field,&catalog,&object);\n    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call)==OVERWORLD_MOTION_DECISION_ACCEPTED\n        && call.trajectory == ((24u << 16) | 20u), "exact curved-rise clearance accepted");\n    obstacleHeight=7809;call=Call(&lane,&field,&catalog,&object);\n    u32 packed=call.trajectory;\n    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call)==OVERWORLD_MOTION_DECISION_BLOCKED,\n        "insufficient curved-rise clearance rejected without raising peak");\n    CHECK(call.trajectory==packed,"rejected Slam leaves authored input untouched");\n    /* One rendered rise frame still crosses all cells continuously. */\n    obstacleHeight=7808;call=Call(&lane,&field,&catalog,&object);\n    SetArc(&call,Arc(1,0,4,24));\n    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call)==OVERWORLD_MOTION_DECISION_ACCEPTED\n        && call.trajectory == ((24u << 16) | 5u), "rise1 uses exact geometric clearance");\n    obstacleHeight=7809;call=Call(&lane,&field,&catalog,&object);\n    SetArc(&call,Arc(1,0,4,24));\n    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call)==OVERWORLD_MOTION_DECISION_BLOCKED,\n        "rise1 multiple-tile low-clearance obstruction rejected");\n    obstacleHeight=8320;call=Call(&lane,&field,&catalog,&object);\n    call.targetBaseY=8192;\n    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call)==OVERWORLD_MOTION_DECISION_ACCEPTED,\n        "curved-rise support interpolation clears ascending target exactly");\n    obstacleHeight=7808;call=Call(&lane,&field,&catalog,&object);\n    call.targetBaseY=-8192;\n    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call)==OVERWORLD_MOTION_DECISION_BLOCKED,\n        "curved-rise support interpolation rejects descending low clearance");\n    unresolved=TRUE;call=Call(&lane,&field,&catalog,&object);\n    call.spotState |= OVERWORLD_ACTOR_HOP_PLAN_FLAG_STRICT_HEIGHT;\n    CHECK(OverworldActorHopPlanner_PlanTrajectory(&call)==OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY,\n        "Slam unavailable support stays a bounded retry");\n    unresolved=FALSE;\n    for(unsigned bad=0;bad<4;bad++) {\n        call=Call(&lane,&field,&catalog,&object);\n        switch(bad) {\n        case 0:SetArc(&call,Arc(0,4,4,24));break;\n        case 1:SetArc(&call,Arc(12,4,0,24));break;\n        case 2:SetArc(&call,Arc(12,4,4,0));break;\n        default:call.operation=OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY;break;\n        }\n        unsigned before=queries;\n        CHECK(OverworldActorHopPlanner_PlanTrajectory(&call)==OVERWORLD_MOTION_DECISION_PROFILE\n            && before==queries,"malformed Slam rejected before world reads");\n    }\n    CHECK(stockTrajectoryCalls==0 && stockArcCalls==0,"all Slam checks retain the distinct shape");\n    puts("Slam clearance uses the shared curved rise and fixed peak");return 0;\n}\n'

if __name__ == "__main__":
    unittest.main()
