"""Host checks for the production directed-Hop progress rule."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.overworld.test_spawn_spatial import extract_function


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"

PRELUDE = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>

typedef int BOOL;
typedef int8_t s8;
typedef uint8_t u8;
typedef uint32_t u32;

#define TRUE 1
#define FALSE 0
#define OW_WILD_HELPER_DIRECTION_UP 0
#define OW_WILD_HELPER_DIRECTION_DOWN 1
#define OW_WILD_HELPER_DIRECTION_LEFT 2
#define OW_WILD_HELPER_DIRECTION_RIGHT 3
#define OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS 8
#define OW_WILD_HELPER_HOP_PLAN_MAX_DISTANCE 8
#define OW_WILD_HELPER_HOP_PLAN_VALIDATION_BUDGET 64
#define OW_WILD_HELPER_HOP_RESULT_FLAG_DIRECT 1
#define OW_WILD_HELPER_HOP_RESULT_FLAG_PLANNED 2
#define OW_WILD_HELPER_HOP_PLAN_DIRECT 0
#define OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY 1
#define OW_WILD_HELPER_HOP_PLAN_FLEE 2

typedef struct OverworldWildHelperHopConfig {
    int objectX;
    int objectY;
    int targetX;
    int targetY;
    u8 minDistance;
    u8 maxDistance;
    u8 allowNonCardinal;
    u8 planMode;
    u8 directionCount;
    u8 directions[OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS];
} OverworldWildHelperHopConfig;

typedef struct OverworldWildHelperHopResult {
    int landingX;
    int landingY;
    int finalTargetX;
    int finalTargetY;
    u8 direction;
    u8 distance;
    u8 flags;
    u8 reserved;
} OverworldWildHelperHopResult;

typedef BOOL (*OverworldWildHelperHopTileValidator)(
    int landingX, int landingY, int targetX, int targetY, void *context);
static u32 nextRandom;
static u32 gf_rand(void) { return nextRandom; }
'''

DEPENDENCIES = (
    ("OverworldWildHelper_Abs", "int"),
    ("OverworldWildHelper_Max", "int"),
    ("OverworldWildHelper_DirectionDeltaX", "int"),
    ("OverworldWildHelper_DirectionDeltaY", "int"),
    ("OverworldWildHelper_BuildDirections", "int"),
    ("OverworldWildHelper_IsHopVectorShape", "BOOL"),
    ("OverworldWildHelper_TryGetHopVector", "BOOL"),
    ("OverworldWildHelper_IsLandingAllowed", "BOOL"),
    ("OverworldWildHelper_SetHopResult", "BOOL"),
    ("OverworldWildHelper_AddHopPlanDirection", "void"),
    ("OverworldWildHelper_BuildHopPlanDirections", "int"),
    ("OverworldWildHelper_GetHopPlanDistance", "int"),
    ("OverworldWildHelper_IsHopTargetOneHopAway", "BOOL"),
    ("OverworldWildHelper_PlanBehaviorHopStep", "BOOL"),
)

HARNESS = r'''
enum ValidationMode {
    VALIDATE_PROGRESS_DIAGONAL,
    VALIDATE_NON_PROGRESS_ONLY,
    VALIDATE_PROGRESS_CARDINAL,
    VALIDATE_FLEE_EDGE,
    VALIDATE_ALL,
};

static BOOL validate_tile(
    int x, int y, int targetX, int targetY, void *rawMode)
{
    enum ValidationMode mode = (enum ValidationMode)(intptr_t)rawMode;
    (void)targetX;
    (void)targetY;
    if (mode == VALIDATE_PROGRESS_DIAGONAL) {
        return x == 2 && y == 2;
    }
    if (mode == VALIDATE_NON_PROGRESS_ONLY) {
        return (x == -1 && y == 0) || (x == 0 && y == 1);
    }
    if (mode == VALIDATE_PROGRESS_CARDINAL) {
        return x == 2 && y == 0;
    }
    if (mode == VALIDATE_FLEE_EDGE) {
        return x == 2 && y == -2;
    }
    return TRUE;
}

static OverworldWildHelperHopConfig config(int targetX, int targetY)
{
    OverworldWildHelperHopConfig value;
    memset(&value, 0, sizeof(value));
    value.targetX = targetX;
    value.targetY = targetY;
    value.minDistance = 1;
    value.maxDistance = 2;
    value.allowNonCardinal = 1;
    value.directions[0] = OW_WILD_HELPER_DIRECTION_RIGHT;
    value.directions[1] = OW_WILD_HELPER_DIRECTION_DOWN;
    value.directionCount = 2;
    return value;
}

int main(void)
{
    OverworldWildHelperHopConfig value;
    OverworldWildHelperHopResult result;
    int i;
    int seen;

    value = config(4, 2);
    assert(OverworldWildHelper_PlanBehaviorHopStep(
        &value, validate_tile, (void *)(intptr_t)VALIDATE_PROGRESS_DIAGONAL,
        &result));
    assert(result.landingX == 2 && result.landingY == 2);

    value = config(4, 0);
    assert(!OverworldWildHelper_PlanBehaviorHopStep(
        &value, validate_tile, (void *)(intptr_t)VALIDATE_NON_PROGRESS_ONLY,
        &result));

    value = config(4, 0);
    assert(OverworldWildHelper_PlanBehaviorHopStep(
        &value, validate_tile, (void *)(intptr_t)VALIDATE_PROGRESS_CARDINAL,
        &result));
    assert(result.landingX == 2 && result.landingY == 0);

    value = config(0, 0);
    assert(!OverworldWildHelper_PlanBehaviorHopStep(
        &value, validate_tile, (void *)(intptr_t)VALIDATE_ALL, &result));

    /* The target mirrors a player at (4, 4). The direct north-west escape is
     * blocked. A diagonal-only actor must use the legal north-east edge step,
     * which still increases its distance from that player. */
    value = config(-4, -4);
    value.planMode = OW_WILD_HELPER_HOP_PLAN_FLEE;
    assert(OverworldWildHelper_PlanBehaviorHopStep(
        &value, validate_tile, (void *)(intptr_t)VALIDATE_FLEE_EDGE, &result));
    assert(result.landingX == 2 && result.landingY == -2);

    /* The high-bit extension carries one straight-chance roll and the prior
     * one-tile vector into directed flat-Walk planning. */
    value = config(4, 4);
    value.maxDistance = 1;
    value.directionCount |= 0x80;
    value.directions[5] = 0;
    value.directions[6] = 1;
    value.directions[7] = 1;
    nextRandom = 0;
    assert(OverworldWildHelper_PlanBehaviorHopStep(
        &value, validate_tile, (void *)(intptr_t)VALIDATE_ALL, &result));
    assert(result.landingX == 1 && result.landingY == 1);
    value.directions[5] = 100;
    assert(OverworldWildHelper_PlanBehaviorHopStep(
        &value, validate_tile, (void *)(intptr_t)VALIDATE_ALL, &result));
    assert(result.landingX == 1 && result.landingY == 1);

    /* Directed flat Walk must choose among all legal progress directions,
     * not always take the first target-ordered direction. */
    seen = 0;
    for (i = 0; i < 24; i++) {
        value = config(4, 2);
        value.maxDistance = 1;
        value.directionCount |= 0x80;
        value.directions[5] = 100;
        value.directions[6] = (u8)-1;
        value.directions[7] = (u8)-1;
        nextRandom = (u32)i;
        assert(OverworldWildHelper_PlanBehaviorHopStep(
            &value, validate_tile, (void *)(intptr_t)VALIDATE_ALL, &result));
        if (result.landingX == 1 && result.landingY == 1) {
            seen |= 1;
        } else if (result.landingX == 1 && result.landingY == 0) {
            seen |= 2;
        } else if (result.landingX == 1 && result.landingY == -1) {
            seen |= 4;
        } else {
            assert(FALSE);
        }
    }
    assert(seen == 7);
    return 0;
}
'''


class DirectedHopProgressTests(unittest.TestCase):
    def test_only_a_strictly_closer_landing_can_start_a_directed_hop(self):
        source = SOURCE.read_text()
        production = "\n\n".join(
            extract_function(source, name, returns)
            for name, returns in DEPENDENCIES
        )
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            c_path = directory / "directed_hop_progress.c"
            binary = directory / "directed_hop_progress"
            c_path.write_text(PRELUDE + production + HARNESS)
            compile_result = subprocess.run(
                ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                 str(c_path), "-o", str(binary)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run(
                [str(binary)], check=False, capture_output=True, text=True)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)


if __name__ == "__main__":
    unittest.main()
