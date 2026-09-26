"""Copied-data controls for the mounted Sprint wall-approach proof."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_mounted_stantler_wall_approach_proof import (
    FAULTS, negative_controls, run,
)


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "tests/overworld/test-recipes/mount.stantler-sprint-wall-approach.json"
HANDLE = {"value": 131079, "slot": 7, "generation": 2, "fieldEpoch": 2,
          "mapGeneration": 2, "encounterGeneration": 2}
CONTEXT = {"mapId": 33, "fieldEpoch": 2, "mapGeneration": 2}
STARTS = ((1, 585, 586, 10), (11, 586, 587, 7),
          (18, 587, 588, 7), (25, 588, 589, 7))


def _sample(frame):
    if frame <= 120:
        chosen = next(((start, x, target, duration) for start, x, target, duration
                       in STARTS if start <= frame < start + duration), None)
        player_x = (585 if frame < 10 else 586 if frame < 17
                    else 587 if frame < 24 else 588 if frame < 31 else 589)
        player_y = 406
        if chosen:
            start, x, target, duration = chosen
            origin = {"x": x, "y": 406}
            target = {"x": target, "y": 406}
            kind, phase = "WALK", "COMMIT_PENDING" if frame == start + duration - 1 else "MOVING"
            elapsed = frame - start + 1
            speed = 8 - STARTS.index(chosen)
        else:
            origin, target = {"x": 588, "y": 406}, {"x": 589, "y": 406}
            kind, phase, elapsed, duration, speed = "NONE", "IDLE", 7, 7, 5
        key = 16
    else:
        player_x, player_y = 589, 406 if frame < 130 else 405
        origin, target = {"x": 589, "y": 406}, {"x": 589, "y": 405}
        kind = "NONE" if frame == 131 else "WALK"
        phase = "IDLE" if frame == 131 else "COMMIT_PENDING" if frame == 130 else "MOVING"
        elapsed, duration, speed = min(frame - 120, 10), 10, 8
        key = 0 if frame == 131 else 64
    actor = {
        "active": True, "role": "MOUNTED", "species": 234,
        "identityVerified": True, "presentationAttached": True,
        "inputOwnership": 1, "handle": deepcopy(HANDLE),
        "subjectIdentity": 3527744121,
        "logical": {"x": player_x, "y": player_y},
        "origin": origin, "target": target,
        "motionKind": kind, "motionPhase": phase,
        "motionElapsed": elapsed, "motionDuration": duration,
        "movementPolicy": {"speed": speed, "base": 8, "direction": 3},
    }
    return {
        "frame": frame, "nativeCycle": frame * 2,
        "observationBoundary": "main-task-queue-completion",
        "fieldAvailable": True, "context": deepcopy(CONTEXT),
        "actors": [actor], "selector": {"rawHeld": key, "heldKeys": key},
        "player": {"x": player_x, "y": player_y},
    }


def fixture():
    events = []
    for start, _, _, duration in (*STARTS, (121, 589, 589, 10)):
        events.append({"frame": start, "kind": "native", "data": {
            "actorHandle": HANDLE["value"], "event": "MOTION_STARTED",
            "reason": "OK", "valueA": 1, "valueB": duration}})
        terminal = start + duration
        for name, a, b in (("LOGICAL_COMMIT", 3, 1),
                           ("MOTION_FINISHED", 3, 1),
                           ("CONTROL_RETURNED", 1, 3)):
            events.append({"frame": terminal, "kind": "native", "data": {
                "actorHandle": HANDLE["value"], "event": name,
                "reason": "OK", "valueA": a, "valueB": b}})
    return [
        {"phase": "observe", "action": "hold-right-to-wall",
         "samples": [_sample(frame) for frame in range(1, 121)],
         "completedGameFrames": 120,
         "events": [event for event in events if event["frame"] <= 120]},
        {"phase": "observe", "action": "turn-up-from-wall",
         "samples": [_sample(frame) for frame in range(121, 131)],
         "completedGameFrames": 10,
         "events": [event for event in events if 120 < event["frame"] <= 130]},
        {"phase": "observe", "action": "release-through-up-commit",
         "samples": [_sample(131)], "completedGameFrames": 1,
         "events": [event for event in events if event["frame"] > 130]},
    ]


class MountedStantlerWallApproachProofTests(unittest.TestCase):
    def test_exact_route_and_all_copied_controls(self):
        recipe = json.loads(RECIPE.read_text())
        rows = fixture()
        original = deepcopy(rows)
        self.assertTrue(run(rows, recipe)["passed"], run(rows, recipe))
        controls = negative_controls(rows, recipe)
        self.assertTrue(controls["passed"], controls)
        self.assertEqual(set(controls["controls"]), set(FAULTS))
        self.assertEqual(rows, original)

    def test_missing_frame_wrong_input_and_changed_actor_fail(self):
        rows = fixture()
        rows[0]["samples"].pop(50)
        rows[0]["completedGameFrames"] -= 1
        self.assertIn("exact Right120", run(rows)["failures"][0])
        rows = fixture()
        rows[0]["samples"][1]["selector"]["rawHeld"] = 0
        self.assertIn("normal Right/Up input differs", run(rows)["failures"][0])
        rows = fixture()
        rows[1]["samples"][0]["actors"][0]["subjectIdentity"] ^= 1
        self.assertIn("mounted Stantler changed", run(rows)["failures"][0])

    def test_missing_commit_is_rejected_for_the_final_clear_tile(self):
        rows = fixture()
        result = run(rows, fault="missing-commit")
        self.assertFalse(result["passed"])
        self.assertIn("did not commit", result["failures"][0])


if __name__ == "__main__":
    unittest.main()
