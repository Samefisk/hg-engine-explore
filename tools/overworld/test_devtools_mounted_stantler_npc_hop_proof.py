"""Copied-data controls for the mounted Sprint stock-NPC Hop proof."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_mounted_stantler_npc_hop_proof import (
    FAULTS, negative_controls, run,
)


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "tests/overworld/test-recipes/mount.stantler-sprint-npc-hop.json"
HANDLE = {"value": 131079, "slot": 7, "generation": 2, "fieldEpoch": 2,
          "mapGeneration": 2, "encounterGeneration": 2}
CONTEXT = {"mapId": 33, "fieldEpoch": 2, "mapGeneration": 2}


def _sample(frame):
    moving = frame < 17
    actor = {
        "active": True, "role": "MOUNTED", "species": 234,
        "identityVerified": True, "presentationAttached": True,
        "inputOwnership": 1, "handle": deepcopy(HANDLE),
        "subjectIdentity": 3527744121,
        "logical": {"x": 599 if moving else 601, "y": 395},
        "motionKind": "HOP" if moving else "NONE",
        "motionPhase": "MOVING" if moving else "IDLE",
        "motionElapsed": frame if moving else 16,
        "motionDuration": 16,
        "movementPolicy": {"speed": 0, "base": 8, "direction": 3},
        "origin": {"x": 599, "y": 395},
        "target": {"x": 601, "y": 395},
    }
    return {
        "frame": frame, "nativeCycle": frame * 2,
        "observationBoundary": "main-task-queue-completion",
        "fieldAvailable": True, "context": deepcopy(CONTEXT),
        "actors": [actor],
        "selector": {"rawHeld": 16 if frame == 1 else 0,
                     "heldKeys": 16 if frame == 1 else 0},
        "player": {"x": 599 if moving else 601, "y": 395},
    }


def fixture():
    samples = [_sample(frame) for frame in range(1, 18)]
    events = [{"frame": 1, "kind": "native", "data": {
        "actorHandle": HANDLE["value"], "event": "MOTION_STARTED",
        "reason": "OK", "valueA": 2, "valueB": 16}}]
    for name, a, b in (("LOGICAL_COMMIT", 2, 2),
                       ("MOTION_FINISHED", 2, 2),
                       ("CONTROL_RETURNED", 1, 2)):
        events.append({"frame": 17, "kind": "native", "data": {
            "actorHandle": HANDLE["value"], "event": name,
            "reason": "OK", "valueA": a, "valueB": b}})
    return [
        {"phase": "observe", "action": "right-into-npc-front",
         "samples": samples[:1], "completedGameFrames": 1,
         "events": [event for event in events if event["frame"] == 1]},
        {"phase": "observe", "action": "release-through-npc-hop",
         "samples": samples[1:], "completedGameFrames": 16,
         "events": [event for event in events if event["frame"] > 1]},
    ]


class MountedStantlerNpcHopProofTests(unittest.TestCase):
    def test_exact_route_and_all_copied_controls(self):
        recipe = json.loads(RECIPE.read_text())
        rows = fixture()
        original = deepcopy(rows)
        self.assertTrue(run(rows, recipe)["passed"], run(rows, recipe))
        controls = negative_controls(rows, recipe)
        self.assertTrue(controls["passed"], controls)
        self.assertEqual(set(controls["controls"]), set(FAULTS))
        self.assertEqual(rows, original)

    def test_missing_frame_and_wrong_input_fail(self):
        rows = fixture()
        rows[1]["samples"].pop(7)
        rows[1]["completedGameFrames"] -= 1
        self.assertIn("completed game frame is missing", run(rows)["failures"][0])
        rows = fixture()
        rows[1]["samples"][1]["selector"]["rawHeld"] = 16
        self.assertIn("normal Right/release input differs", run(rows)["failures"][0])

    def test_terminal_event_must_stay_in_release_window(self):
        rows = fixture()
        rows[1]["events"][0]["frame"] = 1
        self.assertIn("outside the release window", run(rows)["failures"][0])

    def test_pending_terminal_pose_and_event_order(self):
        rows = fixture()
        rows[1]["samples"][-2]["actors"][0]["motionPhase"] = "COMMIT_PENDING"
        self.assertTrue(run(rows)["passed"], run(rows))
        rows[1]["events"][0]["frame"] = 17
        rows[1]["events"][1]["frame"] = 16
        self.assertIn("terminal order differs", run(rows)["failures"][0])


if __name__ == "__main__":
    unittest.main()
