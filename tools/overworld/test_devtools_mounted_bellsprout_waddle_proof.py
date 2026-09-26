"""Copied completed-frame controls for mounted Meander plus Waddle."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld import control
from tools.overworld.devtools_mounted_bellsprout_waddle_proof import (
    FAULTS, LANE_Z, negative_controls, run,
)


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "tests/overworld/test-recipes/mount.bellsprout-waddle-sway.json"
HANDLE = {"value": 131079, "slot": 7, "generation": 2, "fieldEpoch": 2,
          "mapGeneration": 2, "encounterGeneration": 2}
CONTEXT = {"mapId": 33, "fieldEpoch": 2, "mapGeneration": 2}


def _sample(frame):
    elapsed = min(frame, 14)
    moving = frame <= 14
    phase = "MOVING" if frame < 14 else "COMMIT_PENDING" if moving else "IDLE"
    sway = (min(elapsed, 7 - elapsed) * 0x1000 if elapsed < 7 else
            -min(elapsed - 7, 14 - elapsed) * 0x1000 if elapsed < 14 else 0)
    x = (585 << 16) + 0x8000 + (0x10000 * elapsed) // 14
    engine = {"pos_x": x, "pos_y": 65536, "pos_z": LANE_Z + sway,
              "unk88_y": 0, "facing": 3}
    actor = {
        "active": True, "role": "MOUNTED", "species": 69,
        "identityVerified": True, "presentationAttached": True,
        "inputOwnership": 1, "handle": deepcopy(HANDLE),
        "subjectIdentity": 935221,
        "motionKind": "WALK" if moving else "NONE",
        "motionPhase": phase, "motionElapsed": elapsed,
        "motionDuration": 14, "movementPolicy": {"speed": 14},
        "origin": {"x": 585, "y": 402}, "target": {"x": 586, "y": 402},
        "logical": {"x": 585 if frame < 7 else 586, "y": 402},
        "engineObject": engine,
    }
    return {
        "frame": frame, "nativeCycle": frame * 2,
        "observationBoundary": "main-task-queue-completion",
        "fieldAvailable": True, "context": deepcopy(CONTEXT),
        "actors": [actor],
        "selector": {"rawHeld": 16 if frame == 1 else 0,
                     "heldKeys": 16 if frame == 1 else 0},
        "player": {"x": 585 if frame < 14 else 586, "y": 402,
                   "pos_x": x, "pos_z": LANE_Z + sway},
    }


def fixture():
    samples = [_sample(frame) for frame in range(1, 16)]
    start = {"frame": 1, "kind": "native", "data": {
        "actorHandle": HANDLE["value"], "event": "MOTION_STARTED",
        "reason": "OK", "valueA": 1, "valueB": 14}}
    terminal = [
        {"frame": 15, "kind": "native", "data": {
            "actorHandle": HANDLE["value"], "event": name,
            "reason": "OK", "valueA": a, "valueB": b}}
        for name, a, b in (("LOGICAL_COMMIT", 1, 1),
                           ("MOTION_FINISHED", 1, 1),
                           ("CONTROL_RETURNED", 1, 1))
    ]
    return [
        {"phase": "observe", "action": "start-one-right-walk",
         "samples": samples[:1], "completedGameFrames": 1, "events": [start]},
        {"phase": "observe", "action": "finish-one-right-walk",
         "samples": samples[1:], "completedGameFrames": 14, "events": terminal},
    ]


class MountedBellsproutWaddleProofTests(unittest.TestCase):
    def test_one_row_per_completed_frame_matches_shared_recorder(self):
        rows = fixture()
        streamed = []
        for row in rows:
            for index, sample in enumerate(row["samples"]):
                streamed.append({"phase": "observe", "action": row["action"],
                                 "samples": [sample], "completedGameFrames": 1,
                                 "events": row["events"] if index == 0 else []})
        self.assertTrue(run(streamed)["passed"], run(streamed))
        streamed[-1]["action"] = "start-one-right-walk"
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
        accepted = control._shared_mounted_bellsprout_waddle(
            recipe, rows,
            {"sessionId": "session-host", "sessionCleanup":
             {"sessionId": "session-host", "closed": True, "errors": []}}, ROOT)
        self.assertEqual(len(accepted["measurements"]), 8)

    def test_zero_sway_is_not_a_mounted_waddle_pass(self):
        rows = fixture()
        for row in rows:
            for sample in row["samples"]:
                sample["player"]["pos_z"] = LANE_Z
                sample["actors"][0]["engineObject"]["pos_z"] = LANE_Z
        result = run(rows)
        self.assertFalse(result["passed"])
        self.assertIn("sway", result["failures"][0])


if __name__ == "__main__":
    unittest.main()
