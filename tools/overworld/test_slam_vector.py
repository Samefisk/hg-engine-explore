"""Actual-C regression for Slam vectors; no game or native build."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from tools.overworld.test_hop_spawn_entry_flag import function

ROOT = Path(__file__).resolve().parents[2]
PLANNER = ROOT / "src/pokemon_move_history_task6_overlay/overworld_actor_hop_planner.c"


def macro(source, name):
    lines = source.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^#define " + name + r"(?:\(|\s)", line):
            result = [line]
            while result[-1].endswith("\\"):
                index += 1
                result.append(lines[index])
            return "\n".join(result) + "\n"
    raise AssertionError("missing typed macro: " + name)


def harness_source(root=ROOT, planner=None):
    actor = (root / "include/overworld_actor_system_internal.h").read_text()
    motion = (root / "include/overworld_motion_model.h").read_text()
    behavior = (root / "include/overworld_wild_behavior_data.h").read_text()
    movement = (root / "include/overworld_wild_movement.h").read_text()
    call = re.search(r"typedef struct OverworldActorHopPlanCall\s*\{.*?\}\s*OverworldActorHopPlanCall;", actor, re.S)
    decisions = re.search(r"typedef enum OverworldMotionDecision\s*\{.*?\}\s*OverworldMotionDecision;", motion, re.S)
    if call is None or decisions is None:
        raise AssertionError("missing current typed Hop packet/decisions")
    native = (planner or root / "src/pokemon_move_history_task6_overlay/overworld_actor_hop_planner.c").read_text()
    prelude = r"""
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef int16_t s16; typedef int32_t s32;
typedef struct OverworldWildBehaviorProfileData {
    u8 hopAllowNonCardinal, hopMinDistance, hopMaxDistance;
} OverworldWildBehaviorProfileData;
typedef struct OverworldWildBehaviorProfile {
    OverworldWildBehaviorProfileData owner, tired;
} OverworldWildBehaviorProfile;
"""
    flags = macro(actor, "OVERWORLD_ACTOR_HOP_PLAN_FLAG_SLAM") + macro(movement, "OW_WILD_SPAWNER_SPOT_STATE_TIRED")
    for name in ("OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY", "OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY", "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL", "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL"):
        flags += macro(behavior, name)
    bodies = function(native, "OverworldActorHopPlanner_GetLane", "const OverworldWildBehaviorProfileData *")
    bodies += function(native, "OverworldActorHopPlanner_PlanVector", "OverworldMotionDecision")
    return prelude + flags + call.group(0) + decisions.group(0) + bodies + DRIVER


DRIVER = r"""
static void Check(const OverworldWildBehaviorProfile *profile, u8 flags,
    s16 dx, s16 dy, OverworldMotionDecision expected, u8 direction, u8 distance)
{
    OverworldActorHopPlanCall call;
    memset(&call, 0, sizeof(call));
    call.profile = profile; call.spotState = flags;
    call.deltaX = dx; call.deltaY = dy;
    call.direction = 99; call.distance = 98; call.trajectory = 0x12345678;
    OverworldActorHopPlanCall before = call;
    assert(OverworldActorHopPlanner_PlanVector(&call) == expected);
    if (expected == OVERWORLD_MOTION_DECISION_ACCEPTED) {
        before.direction = direction; before.distance = distance;
    }
    assert(memcmp(&call, &before, sizeof(call)) == 0);
}
int main(void)
{
    OverworldWildBehaviorProfile p = {{1,1,6}, {0,1,2}};
    u8 slam = OVERWORLD_ACTOR_HOP_PLAN_FLAG_SLAM;
    u8 tired = OW_WILD_SPAWNER_SPOT_STATE_TIRED;
    /* The measured mounted Snorlax endpoint has dx2/dy5. */
    Check(&p, slam, 2, 5, OVERWORLD_MOTION_DECISION_ACCEPTED, 1, 5);
    Check(&p, slam, -2, -5, OVERWORLD_MOTION_DECISION_ACCEPTED, 0, 5);
    Check(&p, slam, 5, -2, OVERWORLD_MOTION_DECISION_ACCEPTED, 3, 5);
    Check(&p, 0, 2, 5, OVERWORLD_MOTION_DECISION_DIRECTION, 0, 0);
    Check(&p, 0, -5, 2, OVERWORLD_MOTION_DECISION_DIRECTION, 0, 0);
    Check(&p, 0, 5, 5, OVERWORLD_MOTION_DECISION_ACCEPTED, 3, 5);
    Check(&p, 0, 0, 5, OVERWORLD_MOTION_DECISION_ACCEPTED, 1, 5);
    Check(NULL, slam, 2, 5, OVERWORLD_MOTION_DECISION_PROFILE, 0, 0);
    Check(&p, slam, 0, 0, OVERWORLD_MOTION_DECISION_PROFILE, 0, 0);
    Check(&p, slam, 2, 7, OVERWORLD_MOTION_DECISION_PROFILE, 0, 0);
    p.owner.hopMinDistance = 6;
    Check(&p, slam, 2, 5, OVERWORLD_MOTION_DECISION_PROFILE, 0, 0);
    p.owner.hopMinDistance = 1;
    p.owner.hopAllowNonCardinal = 0;
    Check(&p, slam, 2, 5, OVERWORLD_MOTION_DECISION_DIRECTION, 0, 0);
    Check(&p, slam, 0, 5, OVERWORLD_MOTION_DECISION_ACCEPTED, 1, 5);
    p.owner.hopAllowNonCardinal = 2;
    Check(&p, slam, 0, 5, OVERWORLD_MOTION_DECISION_DIRECTION, 0, 0);
    Check(&p, slam, 2, 5, OVERWORLD_MOTION_DECISION_ACCEPTED, 1, 5);
    p.owner.hopAllowNonCardinal = 1;
    /* Mask only SLAM: it must still select the authored tired lane. */
    Check(&p, tired | slam, 2, 5, OVERWORLD_MOTION_DECISION_DIRECTION, 0, 0);
    p.tired.hopAllowNonCardinal = 1;
    Check(&p, tired | slam, 2, 5, OVERWORLD_MOTION_DECISION_PROFILE, 0, 0);
    p.tired.hopMaxDistance = 6;
    Check(&p, tired | slam, 2, 5, OVERWORLD_MOTION_DECISION_ACCEPTED, 1, 5);
    p.tired.hopMinDistance = 6;
    Check(&p, tired | slam, 2, 5, OVERWORLD_MOTION_DECISION_PROFILE, 0, 0);
    p.tired.hopMinDistance = 1;
    p.tired.hopAllowNonCardinal = 2;
    Check(&p, tired | slam, 0, 5, OVERWORLD_MOTION_DECISION_DIRECTION, 0, 0);
    Check(&p, tired | slam, 2, 5, OVERWORLD_MOTION_DECISION_ACCEPTED, 1, 5);
    return 0;
}
"""


class SlamVectorTests(unittest.TestCase):
    def test_actual_vector_guards_and_measured_angle(self):
        with tempfile.TemporaryDirectory(prefix="slam-vector-") as directory:
            source = Path(directory) / "check.c"
            binary = Path(directory) / "check"
            source.write_text(harness_source())
            compile_result = subprocess.run(["cc", "-std=c11", "-O0", str(source), "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
