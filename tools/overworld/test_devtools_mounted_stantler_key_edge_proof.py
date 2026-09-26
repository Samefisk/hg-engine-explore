"""Copied completed-frame controls for mounted Stantler's terminal key edge."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld import control
from tools.overworld.devtools_mounted_stantler_key_edge_proof import (
    FAULTS, negative_controls, run,
)


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "tests/overworld/test-recipes/mount.stantler-key-edge.json"
HANDLE = {"value": 131079, "slot": 7, "generation": 2, "fieldEpoch": 2,
          "mapGeneration": 2, "encounterGeneration": 2}
CONTEXT = {"mapId": 33, "fieldEpoch": 2, "mapGeneration": 2}


def _sample(frame):
    if frame <= 8:
        origin, target, speed, elapsed = 585, 586, 8, frame
        phase = "COMMIT_PENDING" if frame == 8 else "MOVING"
    elif frame <= 16:
        origin, target, speed, elapsed = 586, 587, 7, frame - 8
        phase = "COMMIT_PENDING" if frame == 16 else "MOVING"
    else:
        origin, target, speed, elapsed = 587, 588, 6, frame - 16
        phase = "MOVING"
    keys = 16 if frame <= 9 or frame >= 17 else 0
    new_keys = 16 if frame in (1, 17) else 0
    actor = {
        "active": True, "role": "MOUNTED", "species": 234,
        "identityVerified": True, "presentationAttached": True,
        "inputOwnership": 1, "handle": deepcopy(HANDLE),
        "subjectIdentity": 3527744121,
        "logical": {"x": 585 if frame == 1 else target if phase == "COMMIT_PENDING" else origin,
                    "y": 402},
        "motionKind": "WALK", "motionPhase": phase,
        "motionElapsed": elapsed, "motionDuration": 8,
        "movementPolicy": {"speed": speed, "base": 8, "direction": 3},
        "origin": {"x": origin, "y": 402},
        "target": {"x": target, "y": 402},
    }
    return {
        "frame": frame, "nativeCycle": frame * 2,
        "observationBoundary": "main-task-queue-completion",
        "fieldAvailable": True, "context": deepcopy(CONTEXT),
        "actors": [actor],
        "selector": {"rawHeld": keys, "heldKeys": keys,
                     "rawNew": new_keys, "newKeys": new_keys},
        "player": {"x": origin, "y": 402},
    }


def fixture():
    samples = [_sample(frame) for frame in range(1, 19)]
    events = [
        {"frame": 17, "kind": "native", "data": {
            "actorHandle": HANDLE["value"], "event": name,
            "reason": "OK", "valueA": a, "valueB": b}}
        for name, a, b in (
            ("LOGICAL_COMMIT", 2, 1), ("MOTION_FINISHED", 2, 1),
            ("CONTROL_RETURNED", 1, 2), ("MOTION_STARTED", 1, 8))
    ]
    return [
        {"phase": "observe", "action": "reach-speed-seven",
         "samples": samples[:9], "completedGameFrames": 9, "events": []},
        {"phase": "observe", "action": "neutral-through-tile-end",
         "samples": samples[9:16], "completedGameFrames": 7, "events": []},
        {"phase": "observe", "action": "fresh-right-edge",
         "samples": samples[16:], "completedGameFrames": 2, "events": events},
    ]


class MountedStantlerKeyEdgeProofTests(unittest.TestCase):
    def test_one_row_per_completed_frame_matches_shared_recorder(self):
        rows = fixture()
        streamed = []
        for row in rows:
            for index, sample in enumerate(row["samples"]):
                streamed.append({"phase": "observe", "action": row["action"],
                                 "samples": [sample], "completedGameFrames": 1,
                                 "events": row["events"] if index == 0 else []})
        self.assertTrue(run(streamed)["passed"], run(streamed))
        streamed[-1]["action"] = "reach-speed-seven"
        self.assertFalse(run(streamed)["passed"])

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
        accepted = control._shared_mounted_stantler_key_edge(
            recipe, rows,
            {"sessionId": "session-host", "sessionCleanup":
             {"sessionId": "session-host", "closed": True, "errors": []}}, ROOT)
        self.assertEqual(len(accepted["measurements"]), 5)

    def test_preserved_idle_and_reset_symptom_is_rejected(self):
        rows = fixture()
        edge = rows[-1]["samples"][0]["actors"][0]
        edge["motionKind"] = "NONE"
        edge["motionPhase"] = "IDLE"
        edge["motionElapsed"] = 8
        edge["movementPolicy"]["speed"] = 0
        following = rows[-1]["samples"][1]["actors"][0]
        following["motionElapsed"] = 1
        following["movementPolicy"]["speed"] = 8
        result = run(rows)
        self.assertFalse(result["passed"])
        self.assertIn("idle frame", result["failures"][0])


if __name__ == "__main__":
    unittest.main()
