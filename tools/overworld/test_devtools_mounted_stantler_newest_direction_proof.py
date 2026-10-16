"""Copied completed-frame controls for the mounted newest-direction rule."""

from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import unittest

from tools.overworld import control
from tools.overworld.devtools_mounted_stantler_newest_direction_proof import (
    ACTIONS, CLAIMS, FAULTS, REQUIREMENT, contract, negative_controls, run,
    run_until,
)
from tools.overworld.devtools_test_contract import validate_test


ROOT = Path(__file__).resolve().parents[2]
TEST_ID = "mount.stantler-newest-held-direction"
RECIPE = ROOT / "tests/overworld/test-recipes" / (TEST_ID + ".json")
BASELINE = ROOT / "build/overworld-devtools/test-2ce0b23c10f24461ad3f45be9dccf5fb/observations.jsonl.gz"
BASELINE_RECIPE = BASELINE.parent / "test.json"
HANDLE = {"value": 131079, "slot": 7, "generation": 2, "fieldEpoch": 3,
          "mapGeneration": 3, "encounterGeneration": 1}


def _event(frame, sequence, name, a, b):
    return {"frame": frame, "kind": "native", "data": {
        "actorHandle": HANDLE["value"], "sequence": sequence,
        "event": name, "reason": "OK", "valueA": a, "valueB": b}}


def _walk(frame, operation, *, input_up=False):
    request = bytearray(28)
    response = bytearray(28)
    request[0] = response[0] = 1
    request[2] = response[2] = 28
    request[8] = response[8] = 7
    request[9] = response[9] = operation
    if operation == 1:
        request[10] = response[10] = 0 if input_up else 2
        response[11] = 2
        response[16] = 2
        response[17] = 2
        response[18] = 0
        response[20] = 0x83
    else:
        request[20] = response[20] = 0x83
        response[15] = 1
    return {"frame": frame, "kind": "native-observation", "data": {
        "observation": "walk-policy", "operation": operation,
        "publicSubject": {"handle": {"value": HANDLE["value"]}},
        "requestHex": request.hex(), "responseHex": response.hex()}}


def _sample(frame):
    phase = frame - 820
    if phase <= 20:
        # Four legal displayed Walks: nominal 6, 5, 4, 3 plus a possible
        # two-frame variance on the fourth. The fifth begins on frame 21.
        tile, start, duration, speed = next(
            (tile, start, duration, speed)
            for tile, start, duration, speed in
            ((0, 0, 6, 6), (1, 6, 5, 5),
             (2, 11, 4, 4), (3, 15, 5, 3))
            if phase <= start + duration)
        origin_x = 593 - tile
        target = {"x": origin_x - 1, "y": 402}
        origin = {"x": origin_x, "y": 402}
        kind, elapsed, facing, commit = "WALK", phase - start, 2, tile + 2
        logical = {"x": 593 if phase == 1 else target["x"], "y": 402}
    elif phase <= 23:
        origin, target = {"x": 589, "y": 402}, {"x": 588, "y": 402}
        kind, duration, elapsed, facing, commit = "WALK", 3, phase - 20, 2, 6
        logical = target
    elif phase <= 27:
        origin, target = {"x": 588, "y": 402}, {"x": 587, "y": 402}
        kind, duration, elapsed, facing, commit = "SKID", 4, phase - 23, 0, 7
        logical = origin if elapsed < duration else target
    elif phase <= 32:
        origin, target = {"x": 587, "y": 402}, {"x": 586, "y": 402}
        kind, duration, elapsed, facing, commit = "SKID", 5, phase - 27, 0, 8
        logical = origin if elapsed < duration else target
    else:
        origin, target = {"x": 586, "y": 402}, {"x": 586, "y": 401}
        kind, duration, elapsed, facing, commit = "WALK", 14, phase - 32, 0, 9
        logical = origin if elapsed < duration else target
    center_x = (origin["x"] << 16) + 32768
    center_z = (origin["y"] << 16) + 32768
    mount = {"pos_x": center_x, "pos_y": 65536, "pos_z": center_z,
             "face_x": center_x, "face_y": 65536, "face_z": center_z,
             "facing": facing}
    player = {"x": logical["x"], "y": logical["y"], "facing": facing,
              "pos_x": center_x, "pos_y": 65536, "pos_z": center_z,
              "face_x": center_x + (32768 if facing == 2 else 0),
              "face_y": 65536 + 32768,
              "face_z": center_z + (32768 if facing == 0 else 0)}
    actor = {"active": True, "role": "MOUNTED", "species": 234,
             "identityVerified": True, "presentationAttached": True,
             "inputOwnership": 1, "handle": deepcopy(HANDLE),
             "subjectIdentity": 579089699, "behaviorFingerprint": 444,
             "logical": logical, "origin": origin, "target": target,
             "motionKind": kind,
             "motionPhase": "COMMIT_PENDING" if elapsed == duration else "MOVING",
             "motionElapsed": elapsed, "motionDuration": duration,
             "commitSequence": commit, "engineObject": mount,
             "movementPolicy": {"direction": 2,
                                "speed": speed if phase <= 20 else 2,
                                "pending": 2}}
    held = 32 if phase <= 21 else 96
    new = 32 if phase == 1 else 64 if phase == 22 else 0
    return {"frame": frame, "observationBoundary": "main-task-queue-completion",
            "fieldAvailable": True,
            "context": {"mapId": 33, "fieldEpoch": 3, "mapGeneration": 3},
            "nativeObservation": {"installedBeforeBoot": True,
                                  "coverageComplete": True, "error": None,
                                  "eventsDropped": 0, "profilesEvicted": 0},
            "actors": [actor], "player": player,
            "selector": {"rawHeld": held, "heldKeys": held,
                         "rawNew": new, "newKeys": new,
                         "simulatedKeys": 0}}


def fixture():
    samples = [_sample(frame) for frame in range(821, 866)]
    events = [
        _event(844, 1, "LOGICAL_COMMIT", 7, 1),
        _event(844, 2, "MOTION_FINISHED", 7, 1),
        _event(844, 3, "CONTROL_RETURNED", 1, 7),
        _walk(844, 1, input_up=True),
        _walk(844, 2),
        _event(844, 5, "MOTION_STARTED", 4, 4),
        _event(848, 6, "LOGICAL_COMMIT", 8, 4),
        _event(848, 7, "MOTION_FINISHED", 8, 4),
        _event(848, 8, "CONTROL_RETURNED", 1, 8),
        _walk(848, 2),
        _event(848, 10, "MOTION_STARTED", 4, 5),
        _event(853, 11, "LOGICAL_COMMIT", 9, 4),
        _event(853, 12, "MOTION_FINISHED", 9, 4),
        _event(853, 13, "CONTROL_RETURNED", 1, 9),
        _event(853, 14, "MOTION_STARTED", 1, 14),
    ]
    return [
        {"phase": "observe", "action": "run-left", "samples": samples[:21],
         "completedGameFrames": 21, "events": []},
        {"phase": "observe", "action": "new-up-while-left-held",
         "samples": samples[21:], "completedGameFrames": 24, "events": events},
    ]


class MountedStantlerNewestDirectionProofTests(unittest.TestCase):
    def test_fixture_and_all_copied_faults(self):
        rows = fixture()
        original = deepcopy(rows)
        recipe = validate_test(json.loads(RECIPE.read_text()))
        self.assertTrue(run(rows, recipe)["passed"], run(rows, recipe))
        controls = negative_controls(rows, recipe)
        self.assertTrue(controls["passed"], controls)
        self.assertEqual(set(controls["controls"]), set(FAULTS))
        self.assertEqual(rows, original)

    def test_registered_claims_and_control_dispatch(self):
        recipe = validate_test(json.loads(RECIPE.read_text()))
        control._shared_test_registration(recipe, ROOT)
        registry = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json").read_text())
        scenario = json.loads((ROOT / "tests/overworld/scenarios" /
                               (TEST_ID + ".json")).read_text())
        features = json.loads((ROOT / "tools/overworld/system_features.yaml").read_text())
        self.assertEqual(registry["sharedTests"][TEST_ID]["recipeSha256"],
                         hashlib.sha256(RECIPE.read_bytes()).hexdigest())
        self.assertEqual(registry["sharedTests"][TEST_ID]["minimumObservedFrames"],
                         43)
        self.assertEqual(registry["measurementContracts"][REQUIREMENT], contract())
        self.assertEqual(scenario["adapter"]["claims"], list(CLAIMS))
        self.assertEqual([name for name, _, _ in ACTIONS],
                         [action["id"] for action in recipe["actions"]])
        for capability in scenario["capabilities"]:
            self.assertIn(TEST_ID, next(item["scenarios"] for item in
                                        features["capabilities"]
                                        if item["id"] == capability))
        result = control._shared_mounted_stantler_newest_direction(
            recipe, fixture(), {"sessionId": "session-host", "sessionCleanup":
                               {"sessionId": "session-host", "closed": True,
                                "errors": []}}, ROOT)
        self.assertEqual(len(result["measurements"]), 6)

    def test_run_stops_at_first_fifth_walk_target(self):
        recipe = validate_test(json.loads(RECIPE.read_text()))
        self.assertEqual(recipe["actions"][0]["args"],
                         {"frames": 32, "keys": ["LEFT"], "until": run_until()})
        self.assertEqual(recipe["actions"][1]["args"],
                         {"frames": 24, "keys": ["LEFT", "UP"]})
        too_early = fixture()
        too_early[0]["samples"][-2]["actors"][0]["target"]["x"] = 588
        self.assertIn("first completed fifth-Walk target",
                      run(too_early, recipe)["failures"][0])
        wrong_until = deepcopy(recipe)
        wrong_until["actions"][0]["args"]["until"]["value"] = 589
        self.assertIn("reviewed fifth-Walk normal-input route",
                      run(fixture(), wrong_until)["failures"][0])
        wrong_keys = deepcopy(recipe)
        wrong_keys["actions"][0]["args"]["keys"] = ["UP"]
        self.assertIn("reviewed fifth-Walk normal-input route",
                      run(fixture(), wrong_keys)["failures"][0])

    def test_preserved_rom3475_measurement_is_red(self):
        if not BASELINE.is_file() or not BASELINE_RECIPE.is_file():
            self.skipTest("ignored measured ROM3475 baseline is not in this checkout")
        legacy = validate_test(json.loads(BASELINE_RECIPE.read_text()))
        self.assertEqual([action["args"] for action in legacy["actions"]],
                         [{"frames": 24, "keys": ["LEFT"]},
                          {"frames": 24, "keys": ["LEFT", "UP"]}])
        with gzip.open(BASELINE, "rt") as source:
            rows = [json.loads(line) for line in source]
        combo = [sample for row in rows
                 if row.get("action") == "new-up-while-left-held"
                 for sample in row.get("samples", [])]
        self.assertEqual(len(combo), 24)
        self.assertEqual((combo[0]["selector"]["rawHeld"],
                          combo[0]["selector"]["rawNew"]), (96, 64))
        self.assertFalse(any(actor["motionKind"] == "SKID"
                             for sample in combo for actor in sample["actors"]
                             if actor.get("role") == "MOUNTED"))
        inputs = [bytes.fromhex(event["data"]["requestHex"])
                  for row in rows for event in row.get("events", [])
                  if event.get("kind") == "native-observation"
                  and event.get("frame", 0) >= combo[0]["frame"]
                  and event.get("data", {}).get("observation") == "walk-policy"
                  and event["data"].get("operation") == 1]
        self.assertTrue(inputs)
        self.assertEqual({request[10] for request in inputs}, {2})


if __name__ == "__main__":
    unittest.main()
