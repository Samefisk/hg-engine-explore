"""Host controls for the prepared mounted Stantler Sprint scenario."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld import control
from tools.overworld.devtools_mounted_stantler_sprint_proof import (
    FAULTS, negative_controls, run,
)


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "tests/overworld/test-recipes/mount.stantler-sprint-parity.json"
HANDLE = {"value": 131079, "slot": 7, "generation": 2, "fieldEpoch": 2,
          "mapGeneration": 2, "encounterGeneration": 2}
STARTS = {
    1: (8, 10), 11: (7, 7), 18: (6, 7), 25: (5, 5),
    30: (4, 4), 34: (4, 4), 38: (4, 4), 42: (4, 4),
    46: (4, 4), 55: (4, 4), 59: (4, 4), 63: (4, 4),
    67: (4, 4), 71: (4, 4), 75: (4, 4), 79: (4, 4),
    83: (4, 4), 87: (4, 4), 91: (4, 4), 101: (4, 4),
    162: (4, 4),
}


def fixture():
    samples = []
    for frame in range(1, 202):
        speed, duration = STARTS.get(frame, (4, 0))
        kind = "WALK" if duration else "NONE"
        walk_number = sum(start <= frame for start in STARTS)
        origin_x = 584 + walk_number
        actor = {"active": True, "role": "MOUNTED", "species": 234,
                 "identityVerified": True, "presentationAttached": True,
                 "inputOwnership": 1, "handle": deepcopy(HANDLE),
                 "subjectIdentity": 12345, "logical": {"x": 585, "y": 402},
                 "motionKind": kind, "motionPhase": "MOVING" if kind != "NONE" else "IDLE",
                 "motionElapsed": 1 if kind != "NONE" else 0,
                 "motionDuration": duration,
                 "movementPolicy": {"speed": speed},
                 "origin": {"x": origin_x, "y": 402},
                 "target": {"x": origin_x + 1, "y": 402}}
        raw_held = 16 if frame <= 160 else 80 if frame >= 162 else 0
        samples.append({"frame": frame, "nativeCycle": frame * 2,
                        "observationBoundary": "main-task-queue-completion",
                        "fieldAvailable": True,
                        "context": {"mapId": 33, "fieldEpoch": 2, "mapGeneration": 2},
                        "actors": [actor],
                        "selector": {"rawHeld": raw_held, "heldKeys": raw_held},
                        "player": {"x": 585, "y": 402}})
    events = []
    for start, (speed, duration) in STARTS.items():
        for frame, name, a, b in ((start, "MOTION_STARTED", 1, duration),
                                   (start + duration, "LOGICAL_COMMIT", 1, 1),
                                   (start + duration, "MOTION_FINISHED", 1, 1),
                                   (start + duration, "CONTROL_RETURNED", 1, 1)):
            events.append({"frame": frame, "kind": "native",
                           "data": {"actorHandle": HANDLE["value"], "event": name,
                                    "reason": "OK", "valueA": a, "valueB": b}})
    return [
        {"phase": "observe", "action": "sprint-right", "samples": samples[:160],
         "completedGameFrames": 160,
         "events": [event for event in events if event["frame"] <= 160]},
        {"phase": "observe", "action": "settle-right", "samples": samples[160:161],
         "completedGameFrames": 1,
         "events": [event for event in events if event["frame"] == 161]},
        {"phase": "observe", "action": "hold-two-directions", "samples": samples[161:],
         "completedGameFrames": 40,
         "events": [event for event in events if event["frame"] >= 162]},
    ]


class MountedStantlerSprintProofTests(unittest.TestCase):
    def test_registered_proof_and_copied_controls(self):
        recipe = json.loads(RECIPE.read_text())
        control._shared_test_registration(recipe, ROOT)
        rows = fixture()
        original = deepcopy(rows)
        self.assertTrue(run(rows, recipe)["passed"])
        checked = negative_controls(rows, recipe)
        self.assertTrue(checked["passed"], checked)
        self.assertEqual(set(checked["controls"]), set(FAULTS))
        self.assertEqual(rows, original)
        accepted_rows = control._shared_mounted_stantler_sprint(
            recipe, rows,
            {"sessionId": "session-host", "sessionCleanup":
             {"sessionId": "session-host", "closed": True, "errors": []}}, ROOT)
        self.assertEqual(len(accepted_rows["measurements"]), 8)

    def test_clear_lane_hop_and_speed_reset_fail(self):
        rows = fixture()
        rows[0]["samples"][45]["actors"][0]["motionKind"] = "HOP"
        self.assertIn("Hop started", run(rows)["failures"][0])
        rows = fixture()
        rows[0]["samples"][33]["actors"][0]["movementPolicy"]["speed"] = 8
        self.assertIn("Sprint speed reset", run(rows)["failures"][0])


if __name__ == "__main__":
    unittest.main()
