"""Host proof for the ROM's mounted, render-only Walk path."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "src/overworld_mount_action_overlay/overworld_mount_walk_ease.c"
HARNESS = r"""
#include <assert.h>
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;
#define OVERWORLD_MOUNT_MOTION_WALK 1
typedef struct { u8 motionMode; } Snapshot;
typedef struct {
    Snapshot snapshot;
    u8 motionFlicker, motionElapsed, motionFrameCount;
    s32 motionStartX, motionTargetX, motionStartY, motionTargetY;
} OverworldMountRuntimeState;
typedef struct { u32 posVec[3]; } LocalMapObject;
"""
MAIN = r"""
int main(void) {
    u8 prior, current, elapsed;
    for (prior = 0; prior <= 32; prior++) {
        for (current = 1; current <= 32; current++) {
            OverworldMountRuntimeState state = {0};
            LocalMapObject player = {{0x8000, 0x8000, 0x8000}};
            u32 previous = 0x8000;
            state.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_WALK;
            state.motionFlicker = prior;
            state.motionFrameCount = current;
            state.motionTargetX = 1;
            for (elapsed = 1; elapsed <= current; elapsed++) {
                state.motionElapsed = elapsed;
                if (elapsed == current) {
                    /* The actor writes its exact endpoint before presentation. */
                    player.posVec[0] = 0x18000;
                }
                OverworldWalk_EaseMountedWalk(&state, &player);
                assert(player.posVec[0] >= previous && player.posVec[0] <= 0x18000);
                assert(player.posVec[2] == 0x8000);
                previous = player.posVec[0];
            }
            assert(previous == 0x18000);
        }
    }
    {
        OverworldMountRuntimeState state = {0};
        LocalMapObject player = {{0x8000, 0x8000, 0x8000}};
        state.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_WALK;
        state.motionFlicker = 3;
        state.motionFrameCount = 2;
        state.motionElapsed = 1;
        state.motionTargetX = 1;
        OverworldWalk_EaseMountedWalk(&state, &player);
        assert(player.posVec[0] < 0x10000);
    }
    return 0;
}
"""


class MountedWalkSpeedPresentationTests(unittest.TestCase):
    def test_every_speed_pair_is_monotone_and_reaches_its_tile_on_time(self):
        product = HELPER.read_text()
        function = "void " + product[
            product.index("OverworldWalk_EaseMountedWalk("):
            product.index("static void * __attribute__((section(\".overworld_mount_graphics_refresh_helper\")))")]
        with tempfile.TemporaryDirectory(prefix="mounted-walk-speed-") as directory:
            source = Path(directory) / "speed.c"
            binary = Path(directory) / "speed"
            source.write_text(HARNESS + function + MAIN)
            compiled = subprocess.run(
                ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                 str(source), "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)

    def test_previous_time_routes_only_to_mount_presentation(self):
        chain = (ROOT / "src/overworld_mount_chain_overlay/overworld_mount_chain_overlay.c").read_text()
        walk = (ROOT / "src/pokemon_move_history_overlay/overworld_walk_module.c").read_text()
        field = (ROOT / "src/overworld_mount_chain_overlay/overworld_mount_presentation.c").read_text()
        self.assertIn("call->reserved[3] =", chain)
        self.assertIn("state->motionFlicker = policyCall->reserved[3]", walk)
        self.assertIn("OverworldWalk_EaseMountedWalk(mount, player);", field)
        self.assertLess(field.index("OverworldWalk_EaseMountedWalk(mount, player);"),
                        field.index("memcpy(follower->posVec, player->posVec"))


if __name__ == "__main__":
    unittest.main()
