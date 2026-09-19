"""Host checks for the production random-Walk straight candidate."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.overworld.test_spawn_spatial import extract_function


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
static u32 nextRandom;
static u32 gf_rand(void) { return nextRandom; }
static BOOL valid(int x, int y, int tx, int ty, void *context)
{ (void)x; (void)y; (void)tx; (void)ty; (void)context; return TRUE; }
static BOOL only_straight(int x, int y, int tx, int ty, void *context)
{
    (void)tx; (void)ty; (void)context;
    return x == 3 && y == 3;
}
static BOOL only_restricted(int x, int y, int tx, int ty, void *context)
{
    (void)tx; (void)ty; (void)context;
    return (x == 3 && y == 3) || (x == 1 && y == 1);
}
'''

HARNESS = r'''
int main(void)
{
    OverworldWildHelperHopConfig config;
    OverworldWildHelperHopResult result;
    int i;
    int seen;
    memset(&config, 0, sizeof(config));
    config.objectX = 2;
    config.objectY = 2;
    config.targetX = 0;
    config.targetY = 0;
    config.minDistance = 1;
    config.maxDistance = 1;
    config.allowNonCardinal = 1;
    config.directionCount = 0x80;

    config.planMode = OW_WILD_HELPER_HOP_PLAN_DIRECT;
    assert(OverworldWildHelper_PickRandomBehaviorHop(
        &config, valid, 0, &result));
    assert(result.landingX != 3 || result.landingY != 3);

    config.planMode = OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY;
    assert(OverworldWildHelper_PickRandomBehaviorHop(
        &config, valid, 0, &result));
    assert(result.landingX == 3 && result.landingY == 3);

    config.planMode = OW_WILD_HELPER_HOP_PLAN_DIRECT;
    assert(OverworldWildHelper_PickRandomBehaviorHop(
        &config, only_straight, 0, &result));
    assert(result.landingX == 3 && result.landingY == 3);

    config.targetX = 1;
    config.targetY = 1;
    config.directionCount = 0xC0;
    seen = 0;
    for (i = 0; i < 16; i++) {
        nextRandom = (u32)i;
        assert(OverworldWildHelper_PickRandomBehaviorHop(
            &config, only_restricted, 0, &result));
        if (result.landingX == 3 && result.landingY == 3) {
            seen |= 1;
        } else if (result.landingX == 1 && result.landingY == 1) {
            seen |= 2;
        } else {
            assert(FALSE);
        }
    }
    assert(seen == 3);
    return 0;
}
'''


class WanderStraightChanceTests(unittest.TestCase):
    def test_two_tile_history_controls_next_one_tile_direction(self):
        source = SOURCE.read_text()
        production = "\n\n".join(
            extract_function(source, name, returns)
            for name, returns in FUNCTIONS
        )
        with tempfile.TemporaryDirectory(prefix="straight-chance-") as raw:
            unit = Path(raw) / "straight.c"
            binary = Path(raw) / "straight"
            unit.write_text(PRELUDE + production + HARNESS)
            compiled = subprocess.run(
                ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                 str(unit), "-o", str(binary)],
                capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)


if __name__ == "__main__":
    unittest.main()
