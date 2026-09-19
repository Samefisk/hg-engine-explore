"""Host regression for mounted Hop landing-candidate order."""

from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

from scripts.verify_overworld_mount import function_body


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c"


PRELUDE = r'''
#include <stdio.h>
typedef unsigned char u8;
typedef signed short s16;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY 0
#define OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_AND_DIAGONAL 1
#define OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY 2
#define OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(mode) \
    ((mode) < OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY)
#define OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(mode) \
    ((mode) != OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY)
typedef struct OverworldWildBehaviorProfileData {
    u8 hopAllowNonCardinal;
} OverworldWildBehaviorProfileData;
typedef struct OverworldMountHopSearch {
    u8 lateral;
    u8 distance;
    u8 side;
} OverworldMountHopSearch;
static struct {
    s16 motionStartX;
    s16 motionStartY;
    s16 motionTargetX;
    s16 motionTargetY;
} sOverworldMountState;
static int queryX[16], queryY[16], queryCount;
static int OverworldMount_DirectionDeltaX(u8 direction) {
    (void)direction;
    return 1;
}
static int OverworldMount_DirectionDeltaY(u8 direction) {
    (void)direction;
    return 0;
}
static BOOL OverworldMount_IsLandingTileAllowed(int targetX, int targetY) {
    queryX[queryCount] = targetX;
    queryY[queryCount++] = targetY;
    return (targetX == 13 && targetY == 11)
        || (targetX == 13 && targetY == 13);
}
'''


DRIVER = r'''
#define CHECK(value) do { \
    if (!(value)) { \
        fprintf(stderr, "line %d: %s; chosen=(%d,%d) queries=%d\n", \
                __LINE__, #value, sOverworldMountState.motionTargetX, \
                sOverworldMountState.motionTargetY, queryCount); \
        return 1; \
    } \
} while (0)
int main(void) {
    OverworldWildBehaviorProfileData lane = {
        OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_AND_DIAGONAL
    };
    OverworldMountHopSearch search = {0, 3, 0};
    sOverworldMountState.motionStartX = 10;
    sOverworldMountState.motionStartY = 10;
    CHECK(OverworldMount_TryNextHopLandingCandidate(&lane, 0, 1, 3, &search));
    CHECK(sOverworldMountState.motionTargetX == 13);
    CHECK(sOverworldMountState.motionTargetY == 11);
    CHECK(queryCount == 4);
    CHECK(queryX[0] == 13 && queryY[0] == 10);
    CHECK(queryX[1] == 12 && queryY[1] == 10);
    CHECK(queryX[2] == 11 && queryY[2] == 10);
    CHECK(queryX[3] == 13 && queryY[3] == 11);
    return 0;
}
'''


def program(source: str | None = None) -> str:
    source = SOURCE.read_text() if source is None else source
    body = function_body(source, "OverworldMount_TryNextHopLandingCandidate")
    return PRELUDE + "\nstatic BOOL OverworldMount_TryNextHopLandingCandidate(\n" \
        "    const OverworldWildBehaviorProfileData *lane, u8 direction,\n" \
        "    u8 minDistance, u8 maxDistance, OverworldMountHopSearch *search) {" \
        + body + "}\n" + DRIVER


def execute(source: str | None = None) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="mount-hop-search-") as temporary:
        binary = Path(temporary) / "candidate-search"
        compile_result = subprocess.run(
            [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O0",
             "-x", "c", "-", "-o", str(binary)],
            input=program(source), text=True, capture_output=True)
        if compile_result.returncode:
            return compile_result
        return subprocess.run([str(binary)], text=True, capture_output=True)


class MountHopCandidateSearchTests(unittest.TestCase):
    def test_real_search_prefers_nearest_lateral_target_before_equal_diagonal(self):
        result = execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_equal_diagonal_only_mutation_is_rejected(self):
        source = SOURCE.read_text()
        correct = """            || (lateral != 0
                && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
                    lane->hopAllowNonCardinal))) {"""
        mutant = """            || (lateral != 0
                && (!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
                        lane->hopAllowNonCardinal)
                    || lateralMagnitude != search->distance))) {"""
        self.assertEqual(source.count(correct), 1, "candidate policy seam differs")
        result = execute(source.replace(correct, mutant))
        self.assertNotEqual(result.returncode, 0, "equal-diagonal-only control passed")
        self.assertIn("chosen=(13,13)", result.stderr)


if __name__ == "__main__":
    unittest.main()
