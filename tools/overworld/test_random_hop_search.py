"""Actual-C controls for the bounded random Hop landing search."""

from pathlib import Path
import subprocess
import tempfile
import unittest

try:
    from tools.overworld.test_spawn_spatial import extract_function
except ModuleNotFoundError:
    from test_spawn_spatial import extract_function


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"
FUNCTIONS = (
    ("OverworldWildHelper_Abs", "int"),
    ("OverworldWildHelper_Max", "int"),
    ("OverworldWildHelper_BuildDirections", "int"),
    ("OverworldWildHelper_IsHopVectorShape", "BOOL"),
    ("OverworldWildHelper_TryGetHopVector", "BOOL"),
    ("OverworldWildHelper_SetHopResult", "BOOL"),
    ("OverworldWildHelper_PickRandomBehaviorHop", "BOOL"),
)

PRELUDE = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef int BOOL;
typedef uint8_t u8;
typedef int8_t s8;
typedef uint32_t u32;
#define TRUE 1
#define FALSE 0
#define OW_WILD_HELPER_DIRECTION_UP 0
#define OW_WILD_HELPER_DIRECTION_DOWN 1
#define OW_WILD_HELPER_DIRECTION_LEFT 2
#define OW_WILD_HELPER_DIRECTION_RIGHT 3
#define OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS 8
#define OW_WILD_HELPER_HOP_RESULT_FLAG_DIRECT 1
#define OW_WILD_HELPER_HOP_PLAN_DIRECT 0
#define OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY 1
typedef struct OverworldWildHelperHopConfig {
    int objectX, objectY, targetX, targetY;
    u8 minDistance, maxDistance, allowNonCardinal, planMode, directionCount;
    u8 directions[OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS];
} OverworldWildHelperHopConfig;
typedef struct OverworldWildHelperHopResult {
    int landingX, landingY, finalTargetX, finalTargetY;
    u8 direction, distance, flags, reserved;
} OverworldWildHelperHopResult;
typedef BOOL (*OverworldWildHelperHopTileValidator)(
    int, int, int, int, void *);
static u32 randomValues[4];
static int randomCursor;
static u32 gf_rand(void)
{
    if (randomCursor < 4) return randomValues[randomCursor++];
    randomCursor++;
    return 0;
}
static int validationCount;
static u8 visits[25][25];
static int validatorMode;
static BOOL landing(int x, int y, int tx, int ty, void *context)
{
    (void)tx; (void)ty; (void)context;
    assert(x >= -12 && x <= 12 && y >= -12 && y <= 12);
    assert(++visits[y + 12][x + 12] == 1);
    validationCount++;
    if (validatorMode == 0) return TRUE;
    if (validatorMode == 1) return FALSE;
    if (validatorMode == 2) return y == 0 && (x == -1 || x == 1);
    if (validatorMode == 3) return x == 2 && y == 0;
    if (validatorMode == 4) return x == 1 && y == 1;
    if (validatorMode == 5) return x == 3 && y == 3;
    assert(FALSE);
    return FALSE;
}
static void reset(int mode)
{
    validatorMode = mode;
    validationCount = 0;
    randomCursor = 0;
    memset(visits, 0, sizeof(visits));
}
static OverworldWildHelperHopConfig config(int min, int max, int shape)
{
    OverworldWildHelperHopConfig c;
    memset(&c, 0, sizeof(c));
    c.objectX = 0; c.objectY = 0;
    c.targetX = 8; c.targetY = 8;
    c.minDistance = (u8)min;
    c.maxDistance = (u8)max;
    c.allowNonCardinal = (u8)shape;
    c.planMode = OW_WILD_HELPER_HOP_PLAN_DIRECT;
    return c;
}
'''

HARNESS = r'''
int main(void)
{
    OverworldWildHelperHopConfig c;
    OverworldWildHelperHopResult result;
    int first, second, third;
    int shape, dx, dy;
    int chosenEast = 0;
    int chosenWest = 0;
    u8 directions[4];
    u8 direction, distance;

    /* Both compact vector leaves keep the old direction and distance for
     * every endpoint in the authored maximum square. Invalid vectors do
     * not write outputs. */
    for (shape = 0; shape < 3; shape++) {
        c = config(1, 12, shape);
        for (dy = -12; dy <= 12; dy++) {
            for (dx = -12; dx <= 12; dx++) {
                int absDx = dx < 0 ? -dx : dx;
                int absDy = dy < 0 ? -dy : dy;
                int expectedDistance = absDx > absDy ? absDx : absDy;
                BOOL legal = (dx != 0 || dy != 0)
                    && ((dx == 0 || dy == 0)
                        ? shape < 2 : shape != 0 && absDx == absDy);
                direction = 250;
                distance = 250;
                assert(OverworldWildHelper_TryGetHopVector(
                    &c, dx, dy, &direction, &distance) == legal);
                if (!legal) {
                    assert(direction == 250 && distance == 250);
                    continue;
                }
                assert(OverworldWildHelper_BuildDirections(
                    dx, dy, directions) != 0);
                assert(direction == directions[0]);
                assert(distance == expectedDistance);
                assert(OverworldWildHelper_SetHopResult(
                    &c, dx, dy, dx + 1, dy - 1, 7, &result));
                assert(result.landingX == dx && result.landingY == dy);
                assert(result.finalTargetX == dx + 1
                    && result.finalTargetY == dy - 1);
                assert(result.direction == directions[0]);
                assert(result.distance == expectedDistance);
                assert(result.flags == 7);
            }
        }
    }
    c = config(3, 5, 1);
    for (dy = -12; dy <= 12; dy++) {
        for (dx = -12; dx <= 12; dx++) {
            int absDx = dx < 0 ? -dx : dx;
            int absDy = dy < 0 ? -dy : dy;
            int max = absDx > absDy ? absDx : absDy;
            BOOL legal = max >= 3 && max <= 5
                && ((dx == 0 || dy == 0)
                    ? (dx != 0 || dy != 0) : absDx == absDy);
            assert(OverworldWildHelper_TryGetHopVector(
                &c, dx, dy, 0, 0) == legal);
        }
    }

    /* At the authored maximum of 12, an open world costs one landing read. */
    c = config(1, 12, 1);
    reset(0);
    assert(OverworldWildHelper_PickRandomBehaviorHop(&c, landing, 0, &result));
    assert(validationCount == 1);
    assert(result.landingX != 0 || result.landingY != 0);
    assert(result.distance >= 1 && result.distance <= 12);
    assert(result.flags == OW_WILD_HELPER_HOP_RESULT_FLAG_DIRECT);

    /* A blocked landing is never retried; every legal vector remains reachable. */
    reset(1);
    assert(!OverworldWildHelper_PickRandomBehaviorHop(&c, landing, 0, &result));
    assert(validationCount == 96);
    c = config(1, 2, 1);
    reset(3);
    assert(OverworldWildHelper_PickRandomBehaviorHop(&c, landing, 0, &result));
    assert(result.landingX == 2 && result.landingY == 0);
    assert(validationCount <= 16);

    /* The three authored shape modes and distance two keep their meaning. */
    c = config(2, 2, 0);
    reset(0);
    assert(OverworldWildHelper_PickRandomBehaviorHop(&c, landing, 0, &result));
    assert((result.landingX == 0) != (result.landingY == 0));
    assert(result.distance == 2);
    c.allowNonCardinal = 2;
    reset(0);
    assert(OverworldWildHelper_PickRandomBehaviorHop(&c, landing, 0, &result));
    assert(result.landingX != 0 && result.landingY != 0);
    assert(result.distance == 2);
    c.allowNonCardinal = 1;
    reset(0);
    assert(OverworldWildHelper_PickRandomBehaviorHop(&c, landing, 0, &result));
    assert(result.distance == 2);

    /* All 4! draw schedules give each of two legal tiles 12 first hits. */
    c = config(1, 1, 0);
    for (first = 0; first < 4; first++) {
        for (second = 0; second < 3; second++) {
            for (third = 0; third < 2; third++) {
                reset(2);
                randomValues[0] = (u32)first;
                randomValues[1] = (u32)second;
                randomValues[2] = (u32)third;
                randomValues[3] = 0;
                assert(OverworldWildHelper_PickRandomBehaviorHop(
                    &c, landing, 0, &result));
                if (result.landingX == 1 && result.landingY == 0) chosenEast++;
                else if (result.landingX == -1 && result.landingY == 0) chosenWest++;
                else assert(FALSE);
            }
        }
    }
    assert(chosenEast == 12 && chosenWest == 12);

    /* The history/straight candidate retains its old STOP and fallback rules. */
    c = config(1, 1, 1);
    c.objectX = 2; c.objectY = 2;
    c.targetX = 0; c.targetY = 0;
    c.directionCount = 0x80;
    c.planMode = OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY;
    reset(5);
    assert(OverworldWildHelper_PickRandomBehaviorHop(&c, landing, 0, &result));
    assert(result.landingX == 3 && result.landingY == 3);
    c.planMode = OW_WILD_HELPER_HOP_PLAN_DIRECT;
    reset(5);
    assert(OverworldWildHelper_PickRandomBehaviorHop(&c, landing, 0, &result));
    assert(result.landingX == 3 && result.landingY == 3);
    return 0;
}
'''


class RandomHopSearchTests(unittest.TestCase):
    def test_production_random_hop_work_and_rules(self):
        source = SOURCE.read_text()
        production = "\n\n".join(
            extract_function(source, name, returns) for name, returns in FUNCTIONS
        )
        with tempfile.TemporaryDirectory(prefix="random-hop-search-") as raw:
            unit = Path(raw) / "random_hop.c"
            binary = Path(raw) / "random_hop"
            unit.write_text(PRELUDE + production + HARNESS)
            compiled = subprocess.run(
                ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                 str(unit), "-o", str(binary)], capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)


if __name__ == "__main__":
    unittest.main()
