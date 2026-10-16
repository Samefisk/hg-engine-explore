"""Scoped checks for the TKT-0008 recorder, copied faults and typed routing."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_follower_stop_measurement import FollowerStopMeasurement, KIND
from tools.overworld.devtools_follower_stop_proof import (
    FollowerStopNegative, FAULTS, measurements, validate_negative_result,
)
from tools.overworld.devtools_test_contract import validate_test, TestEvaluator
from tools.overworld.devtools_test_inputs import measurement_inputs

ROOT = Path(__file__).resolve().parents[2]


def fixture():
    actor = {
        "handle": {"value": 65543, "slot": 7, "generation": 1, "fieldEpoch": 1,
                   "mapGeneration": 1, "encounterGeneration": 1},
        "subjectIdentity": 3282570314, "species": 234, "role": "FOLLOWER",
        "authorityGeneration": 1, "engineAnchorGeneration": 1, "presentationGeneration": 1,
        "active": True, "identityVerified": True, "presentationAttached": True,
        "engineIdentity": {}, "behaviorFingerprint": 107466734, "matchedLayerMask": 536888322,
        "motionKind": "WALK", "motionPhase": "MOVING", "motionElapsed": 0, "motionDuration": 3,
        "commitSequence": 0, "inputOwnership": 1, "reservationId": 1,
        "origin": {"x": 592, "y": 401}, "target": {"x": 592, "y": 402},
        "logical": {"x": 592, "y": 401},
        "engineObject": {"facing": 1, "movement_cmd": 60, "pos_x": 38830080, "pos_z": 26312704},
    }
    samples = []
    for frame in range(100, 142):
        row = deepcopy(actor)
        if frame < 103:
            row["motionElapsed"] = frame - 100
            row["engineObject"]["pos_z"] += (frame - 100) * 21845
        else:
            row.update(motionKind="NONE", motionPhase="IDLE", motionElapsed=0,
                       motionDuration=0, commitSequence=1, inputOwnership=0, reservationId=0)
            row["logical"] = deepcopy(row["target"])
            row["engineObject"].update(movement_cmd=255, pos_z=26378240)
        samples.append({"frame": frame, "actorFrame": frame, "context": {
            "mapId": 33, "fieldEpoch": 1, "mapGeneration": 1}, "actors": [row],
            "player": {"x": 593, "y": 403, "facing": 3}})
    events = [
        {"kind": "native", "frame": 100, "data": {"actorHandle": 65543,
         "event": "MOTION_STARTED", "valueA": 1, "valueB": 3}},
        {"kind": "native", "frame": 103, "data": {"actorHandle": 65543,
         "event": "LOGICAL_COMMIT", "valueA": 1, "valueB": 1}},
        {"kind": "native", "frame": 103, "data": {"actorHandle": 65543,
         "event": "CONTROL_RETURNED", "valueA": 0, "valueB": 1}},
    ]
    request = bytearray.fromhex("01001c0028367e020701ff0000000000000000000000000000000000")
    request[17:19] = b"\xff\xff"
    response = bytearray(request)
    response[20] = 8
    subject = deepcopy(samples[12]["actors"][0])
    events.append({"kind": "native-observation", "frame": 112, "data": {
        "observation": "walk-policy", "sequence": 455, "slot": 7, "operation": 1,
        "returnValue": 1, "entryActorFrame": 112, "returnActorFrame": 112,
        "publicSubject": subject, "publicSubjectAfter": deepcopy(subject),
        "requestHex": request.hex(), "responseHex": response.hex()}})
    return {"samples": samples, "events": events}


def replay(row):
    meter = FollowerStopMeasurement()
    for sample in row["samples"]:
        meter.observe(sample, [e for e in row["events"] if e["frame"] == sample["frame"]])
    result = meter.finish()
    return {"passed": result["passed"], "failures": result["failures"],
            "measurements": {KIND: result}}


class FollowerStopMeasurementTests(unittest.TestCase):
    def test_native_walk_and_stable_stop_make_exact_proof_rows(self):
        result = replay(fixture())
        self.assertTrue(result["passed"], result["failures"])
        rows = measurements(result, {"sessionId": "host", "sessionCleanup": {
            "sessionId": "host", "closed": True, "errors": []}})
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["passed"] for row in rows))

    def test_copied_faults_fail_the_named_rule_through_the_same_recorder(self):
        selected = {"stantler": fixture()["samples"][0]["actors"][0]}
        for fault in FAULTS:
            with self.subTest(fault=fault):
                negative = FollowerStopNegative(fault)
                result = replay(negative.mutate(fixture(), selected))
                self.assertTrue(negative.applied)
                validate_negative_result(result, fault)

    def test_missing_reply_gap_and_stale_native_owner_cannot_pass(self):
        for failure in ("reply", "gap", "owner"):
            with self.subTest(failure=failure):
                row = fixture()
                if failure == "reply": row["events"].pop()
                elif failure == "gap": row["samples"].pop(15)
                else: row["events"][-1]["data"]["publicSubject"]["handle"]["generation"] = 2
                self.assertFalse(replay(row)["passed"])

    def test_control_fault_skips_an_unobserved_setup_walk_return(self):
        row = fixture()
        row["events"].insert(0, {"kind": "native", "frame": 100, "data": {
            "actorHandle": 65543, "event": "CONTROL_RETURNED", "valueA": 0, "valueB": 0}})
        fault = KIND + ":missing-control"
        negative = FollowerStopNegative(fault)
        changed = negative.mutate(row, {"stantler": row["samples"][0]["actors"][0]})
        self.assertEqual(changed["events"][0]["data"]["event"], "CONTROL_RETURNED")
        self.assertEqual(changed["events"][3]["data"]["event"], "WORLD_EFFECT")
        validate_negative_result(replay(changed), fault)

    def test_stop_reply_control_waits_for_an_observed_walk(self):
        row = fixture()
        setup_reply = deepcopy(row["events"][-1])
        setup_reply["frame"] = 99
        setup = {"events": [setup_reply], "samples": []}
        negative = FollowerStopNegative(KIND + ":wrong-stop-reply")
        selected = {"stantler": row["samples"][0]["actors"][0]}
        self.assertEqual(negative.mutate(setup, selected), setup)
        self.assertFalse(negative.applied)
        result = replay(negative.mutate(row, selected))
        self.assertTrue(negative.applied)
        validate_negative_result(result, KIND + ":wrong-stop-reply")

    def test_explicit_stock_face_command_begins_a_new_stable_interval(self):
        row = fixture()
        for sample in row["samples"]:
            if sample["frame"] >= 108:
                sample["actors"][0]["engineObject"]["facing"] = 0
                if sample["frame"] == 108:
                    sample["actors"][0]["engineObject"]["movement_cmd"] = 0
        self.assertTrue(replay(row)["passed"])

    def test_registered_recipe_installs_the_leaf_via_the_shared_runner(self):
        test = validate_test(json.loads((ROOT / "tests/overworld/test-recipes/walk.follower.stop-facing.json").read_text()))
        inputs = measurement_inputs(test, ROOT)
        evaluator = TestEvaluator(test)
        evaluator.install_measurements(inputs)
        meter = evaluator.measurements[KIND]
        self.assertIsInstance(meter, FollowerStopMeasurement)
        setup = {"frame": 99, "prepared": False, "actors": []}
        self.assertEqual(evaluator.observe(setup, count_frame=False)["failures"], [])
        self.assertIsNone(meter.subject)  # Current setup's Mankey is not Stantler proof.
        current = fixture()["samples"][0]
        current["prepared"] = True
        evaluator.bind("stantler", current)
        following = fixture()["samples"][1]
        following["prepared"] = True
        self.assertEqual(evaluator.observe(following)["failures"], [])
        self.assertEqual(meter.subject["subjectIdentity"], 3282570314)
        self.assertEqual(meter.walks, [])  # The already-running setup Walk earns no credit.

    def test_subject_role_and_exact_input_contract_remain_strict(self):
        test = json.loads((ROOT / "tests/overworld/test-recipes/walk.follower.stop-facing.json").read_text())
        for field in ("role", "input"):
            changed = deepcopy(test)
            if field == "role": changed["subjects"][0]["role"] = "WILD"
            else: changed["actions"][0]["args"]["keys"] = ["UP"]
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_test(changed)
        # Existing profile-feature recipes still require their Wild subjects.
        wild = json.loads((ROOT / "tests/overworld/test-recipes/walk.wild.blocked-facing.json").read_text())
        validate_test(wild)
        wild["subjects"][0]["role"] = "FOLLOWER"
        with self.assertRaises(ValueError): validate_test(wild)


if __name__ == "__main__":
    unittest.main()
