"""Extract and exercise the mounted key-order helper as C."""

import subprocess
import tempfile
import unittest
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/pokemon_move_history_overlay/overworld_walk_module.c"
NAME = "OverworldWalk_SelectNewestMountedInput"
GRACE = "OverworldWalk_ApplyReleaseGrace"


GRACE_SOURCE = ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c"


def function_source(name_text=NAME, path=SOURCE):
    source = path.read_text()
    name = source.index(name_text + "(")
    start = source.rfind("void __attribute__", 0, name)
    brace = source.index("{", name)
    depth = 0
    for end in range(brace, len(source)):
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
            if depth == 0:
                return re.sub(
                    r'__attribute__\(\(noinline,( used,)?( optimize\("Os"\),)?\s*section\("[^"]+"\)\)\)',
                    '', source[start:end + 1])
    raise AssertionError("mounted key-order helper has no closing brace")


class MountedLatestDirectionInputTest(unittest.TestCase):
    def test_ordered_pairs_and_release(self):
        prefix = r'''
#include <assert.h>
#include <stdint.h>
typedef uint8_t u8;
typedef uint32_t u32;
#define PAD_PLUS_KEY_MASK 0xF0
#define PAD_KEY_RIGHT 0x10
#define PAD_KEY_LEFT 0x20
#define PAD_KEY_UP 0x40
#define PAD_KEY_DOWN 0x80
#define OVERWORLD_MOUNT_MOTION_WALK 1
#define OVERWORLD_MOUNT_RELEASE_GRACE_FRAMES 4
#define OVERWORLD_MOUNT_RELEASE_GRACE_MAX_TIME 4
#define OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX 0
typedef struct OverworldMountRuntimeState {
    u8 directionInputHeld;
    u8 skidRemaining;
    u8 pendingStep;
    u8 directionReleaseGrace;
    struct { u8 motionMode; } snapshot;
    u8 reservedPolicyProfile[2];
} OverworldMountRuntimeState;
static u32 OverworldWalk_DirectionKey(u8 direction) {
    static const u32 keys[] = {PAD_KEY_UP, PAD_KEY_DOWN,
                               PAD_KEY_LEFT, PAD_KEY_RIGHT};
    return direction < 4 ? keys[direction] : 0;
}
static u8 OverworldWalk_DirectionFromKeys(u32 keys) {
    for (u8 direction = 0; direction < 4; ++direction)
        if (keys == OverworldWalk_DirectionKey(direction))
            return direction;
    return 8;
}
'''
        suffix = r'''
static void step(OverworldMountRuntimeState *state, u32 fresh, u32 held,
                 u32 expectedFresh, u32 expectedHeld, u8 expectedRaw,
                 u8 expectedSelected) {
    OverworldWalk_SelectNewestMountedInput(state, &fresh, &held);
    assert((fresh & PAD_PLUS_KEY_MASK) == expectedFresh);
    assert((held & PAD_PLUS_KEY_MASK) == expectedHeld);
    assert((state->directionInputHeld & PAD_PLUS_KEY_MASK) == expectedRaw);
    assert((state->directionInputHeld & 0x0F) == expectedSelected);
    assert(state->skidRemaining == 2 && state->pendingStep == 3);
}
/* Mounted chain control order: key order, then release grace. */
static void control(OverworldMountRuntimeState *state, u32 *fresh, u32 *held) {
    OverworldWalk_SelectNewestMountedInput(state, fresh, held);
    OverworldWalk_ApplyReleaseGrace(state, held);
}
int main(void) {
    const u32 keys[] = {PAD_KEY_UP, PAD_KEY_DOWN,
                        PAD_KEY_LEFT, PAD_KEY_RIGHT};
    for (u8 first = 0; first < 4; ++first) {
        for (u8 newest = 0; newest < 4; ++newest) {
            if (first == newest) continue;
            u32 a = keys[first], b = keys[newest];
            OverworldMountRuntimeState state = {0, 2, 3, 0, {0}, {0, 0}};
            step(&state, a, a, a, a, a, first + 1);
            step(&state, 0, a, 0, a, a, first + 1);
            step(&state, b, a | b, b, b, a | b, newest + 1);
            step(&state, 0, a | b, 0, b, a | b, newest + 1);
            step(&state, 0, a, 0, a, a, 0);
            step(&state, 0, 0, 0, 0, 0, 0);
            /* The frame task can see the new bit before player control. */
            state.directionInputHeld = a | (first + 1);
            step(&state, 0, a | b, 0, b, a | b, newest + 1);
            step(&state, b, a | b, b, b, a | b, newest + 1);
        }
    }
    /* A truly simultaneous chord keeps the raw direction mode. */
    OverworldMountRuntimeState chord = {0, 2, 3, 0, {0}, {0, 0}};
    step(&chord, PAD_KEY_UP | PAD_KEY_LEFT,
         PAD_KEY_UP | PAD_KEY_LEFT,
         PAD_KEY_UP | PAD_KEY_LEFT, PAD_KEY_UP | PAD_KEY_LEFT,
         PAD_KEY_UP | PAD_KEY_LEFT, 0);
    step(&chord, 0, PAD_KEY_UP | PAD_KEY_LEFT,
         0, PAD_KEY_UP | PAD_KEY_LEFT,
         PAD_KEY_UP | PAD_KEY_LEFT, 0);

    /* Mid-Walk release grace: blank control frames 1..4 after the last
     * held frame keep that key; frame 5 releases it, and it stays released. */
    OverworldMountRuntimeState grace = {0, 2, 3, 0, {0}, {0, 0}};
    grace.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_WALK;
    grace.reservedPolicyProfile[OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX] = 2;
    {
        u32 fresh = PAD_KEY_RIGHT, held = PAD_KEY_RIGHT | 2;
        control(&grace, &fresh, &held);
        for (u32 blank = 1; blank <= 6; blank++) {
            fresh = 0; held = 2; /* B-style non-D-pad bit stays intact. */
            control(&grace, &fresh, &held);
            assert(fresh == 0);
            assert(held == (blank <= 4 ? (PAD_KEY_RIGHT | 2) : 2u));
        }
        /* Expired grace does not re-arm from a press while stopped. */
        grace.snapshot.motionMode = 0;
        fresh = PAD_KEY_UP; held = PAD_KEY_UP;
        control(&grace, &fresh, &held);
        fresh = 0; held = 0;
        control(&grace, &fresh, &held);
        assert(held == 0);
        grace.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_WALK;
    }
    /* Rolled turn: Right, two blank frames, then Up selects Up. */
    {
        u32 fresh = PAD_KEY_RIGHT, held = PAD_KEY_RIGHT;
        grace.directionReleaseGrace = 0;
        grace.directionInputHeld = 0;
        control(&grace, &fresh, &held);
        fresh = 0; held = 0;
        control(&grace, &fresh, &held);
        assert(held == PAD_KEY_RIGHT);
        fresh = 0; held = 0;
        control(&grace, &fresh, &held);
        assert(held == PAD_KEY_RIGHT);
        fresh = PAD_KEY_UP; held = PAD_KEY_UP;
        control(&grace, &fresh, &held);
        assert(held == PAD_KEY_UP);
    }
    /* A slow Walk (nominal 6 frames per tile) never arms grace. */
    {
        OverworldMountRuntimeState slow = {0, 2, 3, 0, {0}, {0, 0}};
        u32 fresh = PAD_KEY_UP, held = PAD_KEY_UP;
        slow.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_WALK;
        slow.reservedPolicyProfile[OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX] = 6;
        control(&slow, &fresh, &held);
        fresh = 0; held = 0;
        control(&slow, &fresh, &held);
        assert(held == 0);
    }
    /* Held while stopped (a wall), armed grace lapses: no extra tile. */
    {
        OverworldMountRuntimeState wall = {0, 2, 3, 0, {0}, {2, 0}};
        u32 fresh = PAD_KEY_RIGHT, held = PAD_KEY_RIGHT;
        wall.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_WALK;
        control(&wall, &fresh, &held);
        wall.snapshot.motionMode = 0;
        for (int frame = 0; frame < 4; frame++) {
            fresh = PAD_KEY_RIGHT; held = PAD_KEY_RIGHT;
            control(&wall, &fresh, &held);
        }
        fresh = 0; held = 0;
        control(&wall, &fresh, &held);
        assert(held == 0);
    }
    /* Standing still never arms grace: a tap only turns. */
    {
        OverworldMountRuntimeState idle = {0, 2, 3, 0, {0}, {0, 0}};
        u32 fresh = PAD_KEY_UP, held = PAD_KEY_UP;
        control(&idle, &fresh, &held);
        fresh = 0; held = 0;
        control(&idle, &fresh, &held);
        assert(held == 0 && (idle.directionReleaseGrace & 0xF) == 0);
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "mounted_input.c"
            binary = Path(directory) / "mounted_input"
            source.write_text(prefix + function_source(GRACE, GRACE_SOURCE) + "\n"
                              + function_source() + suffix)
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
