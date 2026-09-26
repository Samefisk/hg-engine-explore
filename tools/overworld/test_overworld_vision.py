"""Focused host proof for portable overworld Vision geometry."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


HARNESS = r"""
#include <assert.h>
#include "overworld_vision.h"

static void CheckAllAdjacent(const OverworldVisionSpec *spec, u8 facing)
{
    int dx;
    int dy;

    for (dy = -1; dy <= 1; dy++) {
        for (dx = -1; dx <= 1; dx++) {
            if (dx == 0 && dy == 0) {
                continue;
            }
            assert(OverworldVision_CanSee(
                spec, 10, 10, facing, (s16)(10 + dx), (s16)(10 + dy), 0));
        }
    }
}

int main(void)
{
    OverworldVisionSpec spec = OVERWORLD_VISION_DEFAULT_SPEC_INITIALIZER;
    OverworldVisionSpec invalidRange = {0, OVERWORLD_VISION_DEFAULT_OPTIONS};
    OverworldVisionSpec invalidOptions = {3, 0x80};
    OverworldVisionSpec noAdjacent = {
        3, OVERWORLD_VISION_CONE_FORWARD_90
    };
    u8 facing;

    assert(sizeof(OverworldVisionSpec) == 2);
    assert(spec.range == 3);
    assert(spec.options == OVERWORLD_VISION_DEFAULT_OPTIONS);

    for (facing = OVERWORLD_VISION_FACING_NORTH;
         facing <= OVERWORLD_VISION_FACING_EAST;
         facing++) {
        CheckAllAdjacent(&spec, facing);
    }

    /* North: straight ahead, both inclusive diagonal edges, and outside. */
    assert(OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 7, 0));
    assert(OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 7, 7, 0));
    assert(OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 13, 7, 0));
    assert(!OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 7, 8, 0));
    assert(!OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 12, 0));
    assert(!OverworldVision_CanSee(&noAdjacent, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 11, 0));
    assert(OverworldVision_CanSee(&noAdjacent, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 9, 0));

    /* South, west, and east use the same inclusive cone rule. */
    assert(OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_SOUTH, 13, 13, 0));
    assert(!OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_SOUTH, 13, 12, 0));
    assert(OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_WEST, 7, 7, 0));
    assert(!OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_WEST, 8, 7, 0));
    assert(OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_EAST, 13, 13, 0));
    assert(!OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_EAST, 12, 13, 0));

    /* Range is Chebyshev distance, with the configured edge included. */
    assert(OverworldVision_IsInView(&spec, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 7));
    assert(!OverworldVision_IsInView(&spec, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 6));

    /* Behind is visible only for one-tile adjacent awareness. */
    assert(OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 11, 0));
    assert(!OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 12, 0));

    /* Occlusion is a simple caller-owned fact, applied after geometry. */
    assert(OverworldVision_IsInView(&spec, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 8));
    assert(!OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 8, 1));

    /* Invalid inputs and a same-tile target fail closed. */
    assert(!OverworldVision_CanSee(0, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 9, 0));
    assert(!OverworldVision_CanSee(&invalidRange, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 9, 0));
    assert(!OverworldVision_CanSee(&invalidOptions, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 9, 0));
    assert(!OverworldVision_CanSee(&spec, 10, 10, 4, 10, 9, 0));
    assert(!OverworldVision_CanSee(&spec, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 10, 0));

    return 0;
}
"""


class OverworldVisionTests(unittest.TestCase):
    def test_visibility_trace_uses_three_argument_collision_helper(self):
        source = (
            ROOT
            / "src/overworld_wild_helper_overlay"
            / "overworld_condition_visibility.c"
        ).read_text()
        linker = (ROOT / "rom.ld").read_text()

        self.assertIn(
            ".thumb_set OverworldConditionVisibility_MetatileBlocked, "
            "0x020548C0",
            source,
        )
        self.assertNotIn(
            ".thumb_set OverworldConditionVisibility_MetatileBlocked, "
            "0x02054954",
            source,
        )
        self.assertIn("IsMetatileBlockedAt = 0x020548C0 | 1;", linker)

    def test_visibility_callback_keeps_thumb_interworking_bit(self):
        header = (
            ROOT / "include/overworld_condition_visibility.h"
        ).read_text()
        caller = (
            ROOT
            / "src/overworld_wild_spawns_overlay"
            / "overworld_wild_spawns_overlay.c"
        ).read_text()

        self.assertIn(
            "OVERWORLD_CONDITION_VISIBILITY_POPULATE_ADDR | 1u",
            header,
        )
        self.assertIn(
            "OVERWORLD_CONDITION_VISIBILITY_POPULATE_ENTRY,",
            caller,
        )
        self.assertNotIn(
            "            OverworldConditionVisibility_PopulateWorld,",
            caller,
        )

    def test_engine_condition_bridge_preserves_definition_pointer(self):
        source = (
            ROOT / "lib/overworld/overworld_behavior_conditions.c"
        ).read_text()
        bridge = source.split(
            "static u8 __attribute__((naked, noinline))\n"
            "OverworldBehaviorCondition_CanSee(",
            1,
        )[1].split("\n}\n#endif", 1)[0]

        self.assertIn('"push {r4, lr}\\n"', bridge)
        self.assertIn('"mov r4, r0\\n"', bridge)
        self.assertIn('"ldr r0, [sp, #24]\\n"', bridge)
        self.assertIn('"ldrb r3, [r4, #14]\\n"', bridge)
        self.assertNotIn('"ldrb r3, [r0, #14]\\n"', bridge)

    def test_portable_truth_table(self):
        with tempfile.TemporaryDirectory(prefix="overworld-vision-") as directory:
            source = Path(directory) / "vision_harness.c"
            binary = Path(directory) / "vision_harness"
            source.write_text(HARNESS)
            compiled = subprocess.run(
                [
                    "cc",
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-DOVERWORLD_VISION_HOST",
                    "-I",
                    str(ROOT / "include"),
                    str(source),
                    str(ROOT / "lib/overworld/overworld_vision.c"),
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


if __name__ == "__main__":
    unittest.main()
