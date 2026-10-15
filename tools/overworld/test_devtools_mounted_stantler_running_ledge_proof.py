"""Copied-data guards for the two real running-ledge boundaries."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld import control
from tools.overworld.devtools_mounted_stantler_running_ledge_proof import (
    ACTION, FAULTS, negative_controls, run,
)
from tools.overworld.devtools_test_contract import validate_test


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "tests/overworld/test-recipes/mount.stantler-running-ledge.json"
HANDLE = {"value": 131079, "slot": 7, "generation": 2, "fieldEpoch": 3,
          "mapGeneration": 3, "encounterGeneration": 1}
CONTEXT = {"mapId": 33, "fieldEpoch": 3, "mapGeneration": 3}
IDENTITY = 4129255615


def _policy(speed, elapsed, carry, turns):
    packet = bytearray(36)
    packet[0], packet[2], packet[3], packet[6] = 1, speed, 6, turns
    packet[20], packet[25], packet[32], packet[33], packet[34] = 255, 4, elapsed, carry, 1
    return packet.hex()


def fixture():
    # These are controlled observations, not a substitute for the live run.
    route = ((392, 393, 8, 6), (393, 394, 6, 4), (394, 395, 4, 4),
             (395, 397, 6, 3), (397, 398, 4, 4), (398, 399, 3, 3),
             (399, 400, 3, 3), (400, 402, 4, 2), (402, 403, 3, 3))
    frames, events = [], []
    frame, elapsed_linear, turns, carry, commit_sequence = 1, 0, 0, 147, 3
    previous_policy = _policy(0, 0, 0, 0)
    for origin, target, duration, speed in route:
        hop = target - origin == 2
        start = frame
        if not hop:
            owner = {"handle": deepcopy(HANDLE), "subjectIdentity": IDENTITY,
                     "role": "MOUNTED", "species": 234}
            events.append({"frame": start, "kind": "native-observation", "data": {
                "observation": "walk-policy", "slot": 7, "operation": 1,
                "publicSubject": owner, "policyBeforeHex": previous_policy,
                "policyAfterHex": previous_policy}})
        kind, value = ("HOP", 2) if hop else ("WALK", 1)
        events.append({"frame": start, "kind": "native", "data": {
            "actorHandle": HANDLE["value"], "event": "MOTION_STARTED",
            "reason": "OK", "valueA": value, "valueB": duration}})
        for motion_elapsed in range(1, duration + 1):
            frames.append({"frame": frame, "nativeCycle": frame * 2,
                "observationBoundary": "main-task-queue-completion",
                "fieldAvailable": True, "context": deepcopy(CONTEXT),
                "selector": {"rawHeld": 128, "heldKeys": 128},
                "actors": [{"active": True, "role": "MOUNTED", "species": 234,
                    "identityVerified": True, "presentationAttached": True,
                    "inputOwnership": 1, "handle": deepcopy(HANDLE),
                    "subjectIdentity": IDENTITY, "behaviorFingerprint": 2219647879,
                    "commitSequence": commit_sequence,
                    "logical": {"x": 590, "y": target if origin == 402 and motion_elapsed >= 2 else origin},
                    "origin": {"x": 590, "y": origin}, "target": {"x": 590, "y": target},
                    "motionKind": kind, "motionPhase": "MOVING",
                    "motionElapsed": motion_elapsed, "motionDuration": duration,
                    "movementPolicy": {"direction": 1, "speed": speed, "base": 6}}]})
            frame += 1
        commit_sequence += 1
        for name in ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
            events.append({"frame": frame, "kind": "native", "data": {
                "actorHandle": HANDLE["value"], "event": name,
                "reason": "OK", "valueA": 1 if name == "CONTROL_RETURNED" else commit_sequence,
                "valueB": commit_sequence if name == "CONTROL_RETURNED" else value}})
        if not hop:
            elapsed_linear += duration
            turns += 1
            # Walk COMMIT carries a smaller rounded speed. Next INPUT can
            # admit speed+1 using its preserved fractional carry.
            after_speed = (3 if target in (395, 398, 399) else 2 if target == 400 else speed)
            previous_policy = _policy(after_speed, elapsed_linear, carry, turns)
            events.append({"frame": frame, "kind": "native-observation", "data": {
                "observation": "walk-policy", "slot": 7, "operation": 3,
                "publicSubject": {"handle": deepcopy(HANDLE), "subjectIdentity": IDENTITY,
                                  "role": "MOUNTED", "species": 234},
                "policyAfterHex": previous_policy}})
        else:
            idle = deepcopy(frames[-1])
            idle["frame"], idle["nativeCycle"] = frame, frame * 2
            idle["actors"][0].update(motionPhase="IDLE", motionKind="NONE",
                                    commitSequence=commit_sequence,
                                    logical={"x": 590, "y": target})
            frames.append(idle)
            frame += 1
    final = deepcopy(frames[-1])
    final["frame"], final["nativeCycle"] = frame, frame * 2
    final["actors"][0].update(motionPhase="MOVING", motionKind="WALK",
                              commitSequence=commit_sequence,
                              logical={"x": 590, "y": 403},
                              origin={"x": 590, "y": 403}, target={"x": 590, "y": 404},
                              motionElapsed=1, motionDuration=3)
    frames.append(final)
    events.append({"frame": frame, "kind": "native", "data": {
        "actorHandle": HANDLE["value"], "event": "MOTION_STARTED", "reason": "OK",
        "valueA": 1, "valueB": 3}})
    return [{"phase": "observe", "action": ACTION, "samples": frames,
             "completedGameFrames": len(frames), "events": events}]


class MountedStantlerRunningLedgeProofTests(unittest.TestCase):
    def test_reviewed_contract_and_each_control_reason(self):
        recipe = validate_test(json.loads(RECIPE.read_text()))
        control._shared_test_registration(recipe, ROOT)
        rows = fixture()
        original = deepcopy(rows)
        evidence = run(rows, recipe)
        self.assertTrue(evidence["passed"], evidence)
        self.assertEqual(len(evidence["hops"]), 2)
        self.assertGreater(evidence["hops"][1]["linearElapsed"], evidence["hops"][0]["linearElapsed"])
        controls = negative_controls(rows, recipe)
        self.assertTrue(controls["passed"], controls)
        self.assertEqual(set(controls["controls"]), set(FAULTS))
        self.assertEqual(rows, original)
        receipt = control._shared_mounted_stantler_running_ledge(recipe, rows,
            {"sessionId": "session-host", "sessionCleanup": {
                "sessionId": "session-host", "closed": True, "errors": []}}, ROOT)
        self.assertEqual(len(receipt["measurements"]), 6)

    def test_missing_completed_frame_and_released_input_reject(self):
        rows = fixture()
        rows[0]["samples"].pop(8)
        rows[0]["completedGameFrames"] -= 1
        self.assertIn("completed game frame is missing", run(rows)["failures"][0])
        rows = fixture()
        rows[0]["samples"][25]["selector"] = {"rawHeld": 0, "heldKeys": 0}
        self.assertIn("Down was released", run(rows)["failures"][0])

    def test_mid_walk_logical_target_does_not_supply_final_commit(self):
        rows = fixture()
        cutoff = next(sample["frame"] for sample in rows[0]["samples"]
                      if sample["actors"][0]["origin"]["y"] == 402
                      and sample["actors"][0]["motionElapsed"] == 2)
        rows[0]["samples"] = [sample for sample in rows[0]["samples"] if sample["frame"] <= cutoff]
        rows[0]["events"] = [event for event in rows[0]["events"] if event["frame"] <= cutoff]
        rows[0]["completedGameFrames"] = len(rows[0]["samples"])
        self.assertEqual(rows[0]["samples"][-1]["actors"][0]["logical"], {"x": 590, "y": 403})
        self.assertIn("normal South Walk lacks one native LOGICAL_COMMIT", run(rows)["failures"][0])


if __name__ == "__main__":
    unittest.main()
