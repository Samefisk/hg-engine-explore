"""Host controls for the prepared mounted Sprint obstacle Hop."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld import control
from tools.overworld.devtools_mounted_stantler_obstacle_hop_proof import (
    FAULTS, negative_controls, run,
)


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "tests/overworld/test-recipes/mount.stantler-sprint-obstacle-hop.json"
HANDLE = {"value": 131079, "slot": 7, "generation": 2, "fieldEpoch": 2,
          "mapGeneration": 2, "encounterGeneration": 2}
CONTEXT = {"mapId": 33, "fieldEpoch": 2, "mapGeneration": 2}
WALK_STARTS = {18: (582, 8), 26: (583, 7), 33: (584, 6),
               39: (585, 5), 44: (586, 4)}


def _sample(frame):
    if frame < 17:
        kind, phase = "HOP", "MOVING"
        origin_x, target_x, speed, duration, elapsed = 580, 582, 0, 16, frame
        logical_x = player_x = 580
    elif frame == 17:
        kind, phase = "NONE", "IDLE"
        origin_x, target_x, speed, duration, elapsed = 580, 582, 0, 16, 16
        logical_x = player_x = 582
    else:
        start = max(start for start in WALK_STARTS if start <= frame)
        origin_x, speed = WALK_STARTS[start]
        target_x, duration, elapsed = origin_x + 1, speed, frame - start + 1
        kind, phase = "WALK", "MOVING"
        logical_x = player_x = origin_x
    held = 16 if frame == 1 or frame >= 18 else 0
    actor = {
        "active": True, "role": "MOUNTED", "species": 234,
        "identityVerified": True, "presentationAttached": True,
        "inputOwnership": 1, "handle": deepcopy(HANDLE),
        "subjectIdentity": 3527744121,
        "logical": {"x": logical_x, "y": 397},
        "motionKind": kind, "motionPhase": phase,
        "motionElapsed": elapsed, "motionDuration": duration,
        "movementPolicy": {"speed": speed, "base": 8, "direction": 3},
        "origin": {"x": origin_x, "y": 397},
        "target": {"x": target_x, "y": 397},
    }
    return {
        "frame": frame, "nativeCycle": frame * 2,
        "observationBoundary": "main-task-queue-completion",
        "fieldAvailable": True, "context": deepcopy(CONTEXT),
        "actors": [actor],
        "selector": {"rawHeld": held, "heldKeys": held},
        "player": {"x": player_x, "y": 397},
    }


def fixture():
    samples = [_sample(frame) for frame in range(1, 45)]
    events = [{"frame": 1, "kind": "native", "data": {
        "actorHandle": HANDLE["value"], "event": "MOTION_STARTED",
        "reason": "OK", "valueA": 2, "valueB": 16}}]
    for name, a, b in (("LOGICAL_COMMIT", 2, 2),
                       ("MOTION_FINISHED", 2, 2),
                       ("CONTROL_RETURNED", 1, 2)):
        events.append({"frame": 17, "kind": "native", "data": {
            "actorHandle": HANDLE["value"], "event": name,
            "reason": "OK", "valueA": a, "valueB": b}})
    for start, (_, speed) in WALK_STARTS.items():
        events.append({"frame": start, "kind": "native", "data": {
            "actorHandle": HANDLE["value"], "event": "MOTION_STARTED",
            "reason": "OK", "valueA": 1, "valueB": speed}})
    return [
        {"phase": "observe", "action": "right-into-blocked-front",
         "samples": samples[:1], "completedGameFrames": 1,
         "events": [event for event in events if event["frame"] == 1]},
        {"phase": "observe", "action": "release-through-hop",
         "samples": samples[1:17], "completedGameFrames": 16,
         "events": [event for event in events if 1 < event["frame"] <= 17]},
        {"phase": "observe", "action": "walk-after-obstacle",
         "samples": samples[17:], "completedGameFrames": 27,
         "events": [event for event in events if event["frame"] > 17]},
    ]


class MountedStantlerObstacleHopProofTests(unittest.TestCase):
    def test_registered_proof_and_copied_controls(self):
        recipe = json.loads(RECIPE.read_text())
        control._shared_test_registration(recipe, ROOT)
        rows = fixture()
        original = deepcopy(rows)
        self.assertTrue(run(rows, recipe)["passed"], run(rows, recipe))
        controls = negative_controls(rows, recipe)
        self.assertTrue(controls["passed"], controls)
        self.assertEqual(set(controls["controls"]), set(FAULTS))
        self.assertEqual(rows, original)
        accepted = control._shared_mounted_stantler_obstacle_hop(
            recipe, rows,
            {"sessionId": "session-host", "sessionCleanup":
             {"sessionId": "session-host", "closed": True, "errors": []}}, ROOT)
        self.assertEqual(len(accepted["measurements"]), 7)

    def test_one_row_per_completed_frame_and_missing_frame(self):
        rows = fixture()
        streamed = []
        for row in rows:
            for index, sample in enumerate(row["samples"]):
                streamed.append({"phase": "observe", "action": row["action"],
                                 "samples": [sample], "completedGameFrames": 1,
                                 "events": row["events"] if index == 0 else []})
        self.assertTrue(run(streamed)["passed"], run(streamed))
        streamed.pop(10)
        self.assertIn("completed game frame is missing", run(streamed)["failures"][0])

    def test_short_landing_and_missing_commit_fail(self):
        rows = fixture()
        rows[0]["samples"][0]["actors"][0]["target"]["x"] = 581
        self.assertIn("two-tile forward Hop", run(rows)["failures"][0])
        rows = fixture()
        commit = next(event for event in rows[1]["events"]
                      if event["data"]["event"] == "LOGICAL_COMMIT")
        commit["data"]["event"] = "REMOVED_LOGICAL_COMMIT"
        self.assertIn("did not commit", run(rows)["failures"][0])


if __name__ == "__main__":
    unittest.main()
