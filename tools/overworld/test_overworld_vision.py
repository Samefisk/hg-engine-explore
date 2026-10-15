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
    OverworldVisionSpec sameTile = {
        1, OVERWORLD_VISION_CONE_FORWARD_90
            | OVERWORLD_VISION_ADJACENT_AWARENESS
            | OVERWORLD_VISION_SAME_TILE_AWARENESS
    };
    unsigned options;
    u8 facing;

    assert(sizeof(OverworldVisionSpec) == 2);
    assert(spec.range == 3);
    assert(spec.options == OVERWORLD_VISION_DEFAULT_OPTIONS && spec.options == 5);
    assert(OVERWORLD_VISION_SAME_TILE_AWARENESS == 8);
    assert(sameTile.options == 13 && OverworldVision_IsValidSpec(&sameTile));

    for (facing = OVERWORLD_VISION_FACING_NORTH;
         facing <= OVERWORLD_VISION_FACING_EAST;
         facing++) {
        CheckAllAdjacent(&spec, facing);
        CheckAllAdjacent(&sameTile, facing);
        assert(!OverworldVision_IsInView(&spec, 10, 10, facing, 10, 10));
        assert(OverworldVision_IsInView(&sameTile, 10, 10, facing, 10, 10));
        assert(OverworldVision_CanSee(&sameTile, 10, 10, facing, 10, 10, 0));
        assert(!OverworldVision_CanSee(&sameTile, 10, 10, facing, 10, 10, 1));
        assert(!OverworldVision_IsInView(&sameTile, 10, 10, facing, 12, 10));
    }
    for (options = 16; options <= 255; options++) {
        OverworldVisionSpec unknown = {1, (u8)options};
        assert(!OverworldVision_IsValidSpec(&unknown));
        assert(!OverworldVision_IsInView(&unknown, 10, 10, 0, 10, 10));
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

    /* Cardinal lines keep range/alignment/occlusion but ignore facing. */
    {
        OverworldVisionSpec cardinal = {32, OVERWORLD_VISION_CONE_CARDINAL_LINES};
        OverworldVisionSpec invalidCone = {32, OVERWORLD_VISION_ADJACENT_AWARENESS};
        assert(OverworldVision_IsValidSpec(&cardinal));
        assert(!OverworldVision_IsValidSpec(&invalidCone));
        for (facing = 0; facing <= OVERWORLD_VISION_FACING_EAST; facing++) {
            assert(OverworldVision_CanSee(&cardinal, 10, 10, facing, 42, 10, 0));
            assert(OverworldVision_CanSee(&cardinal, 10, 10, facing, -22, 10, 0));
            assert(OverworldVision_CanSee(&cardinal, 10, 10, facing, 10, 42, 0));
            assert(OverworldVision_CanSee(&cardinal, 10, 10, facing, 10, -22, 0));
            assert(!OverworldVision_CanSee(&cardinal, 10, 10, facing, 43, 10, 0));
            assert(!OverworldVision_CanSee(&cardinal, 10, 10, facing, 42, 11, 0));
            assert(!OverworldVision_CanSee(&cardinal, 10, 10, facing, 11, 11, 0));
            assert(!OverworldVision_CanSee(&cardinal, 10, 10, facing, 42, 10, 1));
            assert(!OverworldVision_CanSee(&cardinal, 10, 10, facing, 10, 10, 0));
        }
    }

    /* Invalid inputs and a same-tile target fail closed. */
    assert(!OverworldVision_CanSee(0, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 9, 0));
    assert(!OverworldVision_CanSee(&invalidRange, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 9, 0));
    assert(!OverworldVision_CanSee(&invalidOptions, 10, 10,
        OVERWORLD_VISION_FACING_NORTH, 10, 9, 0));
    assert(!OverworldVision_CanSee(&spec, 10, 10, 4, 10, 9, 0));
    assert(!OverworldVision_CanSee(&sameTile, 10, 10, 4, 10, 10, 0));
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

    def test_actual_native_visibility_ignores_above_below_elevation(self):
        from tools.overworld.test_picked_up_actor_control import extract_function
        native = (ROOT / "src/overworld_wild_helper_overlay/overworld_condition_visibility.c").read_text()
        source = CROSS_HEIGHT_PRELUDE + "\n".join(extract_function(native, name, returns) for name, returns in (("OverworldConditionVisibility_Abs", "u32"), ("OverworldConditionVisibility_TraceBlocked", "BOOL"), ("OverworldConditionVisibility_PopulateWorld", "void"))) + CROSS_HEIGHT_DRIVER
        extra = [str(ROOT / "lib/overworld/overworld_vision.c")]
        with tempfile.TemporaryDirectory(prefix="overworld-cross-height-") as directory:
            unit = Path(directory) / "height.c"; binary = Path(directory) / "height"
            unit.write_text(CROSS_HEIGHT_HOST_TYPES + source)
            compiled = subprocess.run(["cc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-Wno-sign-compare", "-DOVERWORLD_BEHAVIOR_HOST", "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-DOVERWORLD_VISION_HOST", "-I", str(ROOT / "include"), str(unit), *extra, "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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



CROSS_HEIGHT_HOST_TYPES = '\n/* The stock types.h declares ARM-only long_call imports. This host boundary\n * supplies the same scalar widths, not engine imports or guest layouts. */\n#include <stdint.h>\n#include <stddef.h>\n#ifdef __clang__\n#pragma clang diagnostic ignored "-Wunknown-attributes"\n#endif\n#define TYPES_H\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef uint64_t u64;\ntypedef int8_t s8;typedef int16_t s16;typedef int32_t s32;typedef int64_t s64;\ntypedef int BOOL;typedef s32 fx32;\ntypedef struct { fx32 x,y,z; } VecFx32;\n#define TRUE 1\n#define FALSE 0\n#define ALIGN4 __attribute__((aligned(4)))\n#define PACKED __attribute__((packed))\n#define LONG_CALL\n#define NELEMS(a) (sizeof(a)/sizeof((a)[0]))\n'
CROSS_HEIGHT_PRELUDE = '\n#include <assert.h>\n#include <string.h>\n#include "overworld_behavior_conditions.h"\ntypedef struct LocalMapObject { u8 curFacing; s32 posVec[3]; } LocalMapObject;\ntypedef struct FIELD_PLAYER_AVATAR { LocalMapObject *mapObject; int x,y; } FIELD_PLAYER_AVATAR;\ntypedef struct FieldSystem { FIELD_PLAYER_AVATAR *playerAvatar; } FieldSystem;\nstatic int wallX=-1,wallY=-1;\nstatic unsigned tileReads;\nstatic int GetPlayerXCoord(FIELD_PLAYER_AVATAR *a) {return a->x;}\nstatic int GetPlayerYCoord(FIELD_PLAYER_AVATAR *a) {return a->y;}\nstatic BOOL IsMetatileBlockedAt(FieldSystem *f,int x,int y) {\n    assert(f);tileReads++;return x==wallX && y==wallY;\n}\n'
CROSS_HEIGHT_DRIVER = '\nint main(void) {\n    LocalMapObject object={0}; FIELD_PLAYER_AVATAR avatar={&object,10,7};\n    FieldSystem field={&avatar};\n    OverworldBehaviorConditionWorldView world={0};\n    OverworldVisionSpec spec=OVERWORLD_VISION_DEFAULT_SPEC_INITIALIZER;\n    world.subjectX=10;world.subjectY=10;world.actorCount=2;\n    world.actors[0].valid=1;world.actors[0].x=10;world.actors[0].y=7;\n    world.actors[0].facingAndOcclusion=OVERWORLD_VISION_FACING_SOUTH;\n    world.actors[1].valid=0;world.actors[1].x=100;world.actors[1].y=100;\n    for(int elevation=-0x80000;elevation<=0x80000;elevation+=0x10000) {\n        object.posVec[1]=elevation;tileReads=0;\n        OverworldConditionVisibility_PopulateWorld(&field,&world);\n        assert(world.playerValid && world.playerX==10 && world.playerY==7);\n        assert(!(world.playerFacingAndOcclusion&12));\n        assert(!(world.actors[0].facingAndOcclusion&12));\n        assert(tileReads==4); /* Each valid target reads only two intermediate XY tiles. */\n        assert(OverworldVision_CanSee(&spec,10,10,0,10,7,world.actors[0].facingAndOcclusion&4));\n    }\n    wallX=10;wallY=9;\n    OverworldConditionVisibility_PopulateWorld(&field,&world);\n    assert((world.playerFacingAndOcclusion&12)==12 && (world.actors[0].facingAndOcclusion&12)==12);\n    assert(!OverworldVision_CanSee(&spec,10,10,0,10,7,world.actors[0].facingAndOcclusion&4));\n    wallX=wallY=-1;\n    avatar.x=11;avatar.y=8;\n    tileReads=0;OverworldConditionVisibility_PopulateWorld(&field,&world);\n    assert(world.playerX==11 && world.playerY==8 && tileReads==3);\n    avatar.x=10;avatar.y=7;\n    assert(!OverworldVision_CanSee(&spec,10,10,0,10,6,0));\n    assert(!OverworldVision_CanSee(&spec,10,10,0,10,12,0));\n    field.playerAvatar=0;OverworldConditionVisibility_PopulateWorld(&field,&world);assert(!world.playerValid);\n    return 0;\n}\n'

if __name__ == "__main__":
    unittest.main()
