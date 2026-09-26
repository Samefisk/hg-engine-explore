"""Copied-data controls for the Jigglypuff Floaty Bounce cadence claim."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_profile_feature_measurement import (
    FLOATY_BOUNCE, ProfileFeatureMeasurement,
)
from tools.overworld.devtools_profile_feature_proof import (
    ProfileFeatureNegative, measurements, validate_negative_result, values,
)
from tools.overworld.devtools_test_contract import TestEvaluator
from tools.overworld.devtools_test_inputs import measurement_inputs


ROOT = Path(__file__).resolve().parents[2]


def hop(start, distance, commit):
    duration = 12 + 9 * (distance - 1)
    target = [distance, 0]
    return {
        "kind": "HOP", "startFrame": start, "finishFrame": start + duration + 10,
        "handle": {"value": 7}, "origin": [0, 0], "target": target,
        "duration": duration, "fingerprint": 777,
        "commitBefore": commit, "commitAfter": commit + 1,
        "commitFrame": start + duration, "pauseFrames": 10,
        "samples": [{"frame": start + frame, "elapsed": frame,
                     "render": [0, 0, 0]} for frame in range(duration + 1)],
        "travelEnd": {"frame": start + duration, "elapsed": duration,
                      "render": [0, 0]},
        "terminalLogical": target,
    }


def meter():
    motions = [hop(1, 3, 0), hop(43, 2, 1)]
    return {
        "kind": FLOATY_BOUNCE,
        "requirements": ["current.floaty-bounce-hop-pause"],
        "passed": True, "ready": True, "failures": [],
        "initial": {"frame": 0},
        "terminal": {"actors": [{"handle": {"value": 7}, "role": "WILD",
                                "species": 39, "identityVerified": True,
                                "presentationAttached": True}]},
        "subjects": {"jigglypuff": {"handle": {"value": 7}}},
        "floatyProfile": {"fingerprint": 777, "sourceSha256": "a" * 64,
                          "locomotion": 2, "hopTime": 12, "hopPause": 10},
        "motions": motions,
        "events": [{"frame": motion["finishFrame"], "kind": "native",
                    "data": {"event": "CONTROL_RETURNED", "actorHandle": 7}}
                   for motion in motions],
    }


def accept(value):
    return measurements(FLOATY_BOUNCE,
                        {"passed": True, "failures": [],
                         "measurements": {FLOATY_BOUNCE: value}},
                        {"sessionId": "copied", "sessionCleanup": {
                            "sessionId": "copied", "closed": True, "errors": []}})


class FloatyBounceHopPauseProofTests(unittest.TestCase):
    def test_full_boundary_receipt_authenticates_compact_completed_frames(self):
        observer = ProfileFeatureMeasurement(FLOATY_BOUNCE)
        lane = bytearray(72)
        lane[12], lane[22], lane[36] = 2, 10, 12
        profile = {"resolved": True, "fingerprint": 777,
                   "sourceSha256": "a" * 64,
                   "lanes": [lane.hex(), lane.hex()],
                   "resultHex": lane.hex() + "00" * 128}
        full = {"nativeObservation": {"coverageComplete": True,
                 "profilesEvicted": 0, "profileFingerprints": [777],
                 "resolvedProfiles": [profile]}}
        compact = {"nativeObservation": {"coverageComplete": True,
                    "profilesEvicted": 0, "profileFingerprints": [777]}}
        actor = {"behaviorFingerprint": 777}
        with self.assertRaisesRegex(ValueError, "no cached exact"):
            observer._observe_floaty_profile(compact, actor)
        observer._observe_floaty_profile(full, actor)
        observer._observe_floaty_profile(compact, actor)
        self.assertEqual(observer.floaty_profile["hopPause"], 10)

        lost = deepcopy(compact)
        lost["nativeObservation"]["profileFingerprints"] = []
        with self.assertRaisesRegex(ValueError, "coverage or fingerprint"):
            observer._observe_floaty_profile(lost, actor)
        other = deepcopy(compact)
        other["nativeObservation"]["profileFingerprints"].append(778)
        with self.assertRaisesRegex(ValueError, "no cached exact"):
            observer._observe_floaty_profile(other, {"behaviorFingerprint": 778})
        changed = deepcopy(full)
        changed["nativeObservation"]["resolvedProfiles"][0]["lanes"][0] = (
            lane[:22] + b"\x00" + lane[23:]).hex()
        changed["nativeObservation"]["resolvedProfiles"][0]["resultHex"] = (
            changed["nativeObservation"]["resolvedProfiles"][0]["lanes"][0]
            + "00" * 128)
        with self.assertRaisesRegex(ValueError, "profile changed"):
            observer._observe_floaty_profile(changed, actor)

    def test_registered_recipe_installs_its_fixed_contract_before_boot(self):
        recipe = json.loads((ROOT / "tests/overworld/test-recipes/"
                             "profile.floaty-bounce-hop-pause.json").read_text())
        teleport = recipe["setup"][0]
        self.assertEqual(teleport["id"], "route29-open-area")
        self.assertEqual((teleport["budget"]["maxFrames"],
                          teleport["budget"]["noProgressFrames"]), (80, 80))
        source = measurement_inputs(recipe, ROOT)
        self.assertEqual(source, {FLOATY_BOUNCE: {"contractVersion": 1}})
        evaluator = TestEvaluator(recipe)
        evaluator.install_measurements(source)
        self.assertIsInstance(evaluator.measurements[FLOATY_BOUNCE],
                              ProfileFeatureMeasurement)

    def test_retained_spawn_commit_is_not_a_new_hop(self):
        # Copied from the failed frame stream: the prepared spawn Hop commits
        # at 836, then settles through 845. Only the routine Hop at 855 is a
        # complete motion that this observer may measure.
        observer = ProfileFeatureMeasurement(FLOATY_BOUNCE)
        observed = []
        observer.motion.observe = lambda frame, actor, engine: observed.append(frame)
        spawn = {"motionKind": "HOP", "motionPhase": "MOVING",
                 "motionElapsed": 4, "commitSequence": 0,
                 "origin": {"x": 600, "y": 402},
                 "target": {"x": 592, "y": 402}}
        for frame, phase, elapsed, commit in (
                (765, "MOVING", 4, 0),
                (835, "MOVING", 74, 0),
                (836, "SETTLING", 75, 1),
                (845, "SETTLING", 75, 1)):
            actor = {**spawn, "motionPhase": phase,
                     "motionElapsed": elapsed, "commitSequence": commit}
            observer._observe_floaty_motion(frame, actor, {})
        self.assertEqual(observed, [])
        idle = {**spawn, "motionKind": "NONE", "motionPhase": "IDLE",
                "motionElapsed": 75, "commitSequence": 1}
        observer._observe_floaty_motion(846, idle, {})
        routine = {**spawn, "motionElapsed": 0, "commitSequence": 1,
                   "origin": {"x": 592, "y": 402},
                   "target": {"x": 592, "y": 400}}
        observer._observe_floaty_motion(855, routine, {})
        self.assertEqual(observed, [846, 855])

        # The next routine start must also work if the spawn never exposes
        # an idle frame between its settle and the new motion.
        no_idle = ProfileFeatureMeasurement(FLOATY_BOUNCE)
        seen = []
        no_idle.motion.observe = lambda frame, actor, engine: seen.append(frame)
        no_idle._observe_floaty_motion(765, spawn, {})
        no_idle._observe_floaty_motion(836, {**spawn, "motionPhase": "SETTLING",
                                             "motionElapsed": 75,
                                             "commitSequence": 1}, {})
        no_idle._observe_floaty_motion(846, routine, {})
        self.assertEqual(seen, [846])

    def test_two_complete_hops_have_exact_travel_and_settle_time(self):
        value = meter()
        observer = ProfileFeatureMeasurement(FLOATY_BOUNCE)
        self.assertEqual(observer.motion.expected_pause_by_kind["HOP"], 10)
        observer.subjects = value["subjects"]
        observer.initial = value["initial"]
        observer.floaty_profile = value["floatyProfile"]
        observer.motion.completed = value["motions"]
        observer.events = value["events"]
        self.assertTrue(observer.ready)
        self.assertEqual(values(FLOATY_BOUNCE, value)[
            "floaty-two-hop-pause-frames"], [10, 10])
        self.assertEqual(len(accept(value)), 7)

    def test_copied_zero_pause_and_fast_hop_are_rejected(self):
        source = meter()
        no_pause = deepcopy(source)
        no_pause["motions"][0]["pauseFrames"] = 0
        with self.assertRaisesRegex(ValueError, "floaty-two-hop-pause-frames"):
            accept(no_pause)
        too_fast = deepcopy(source)
        too_fast["motions"][1]["duration"] -= 1
        with self.assertRaisesRegex(ValueError, "floaty-hop-duration-errors"):
            accept(too_fast)
        self.assertEqual(source["motions"][0]["pauseFrames"], 10)

    def test_missing_jigglypuff_control_return_fails_the_live_meter(self):
        source = meter()
        observer = ProfileFeatureMeasurement(FLOATY_BOUNCE)
        observer.subjects = source["subjects"]
        observer.initial = source["initial"]
        observer.floaty_profile = source["floatyProfile"]
        observer.motion.completed = source["motions"]
        observer.events = deepcopy(source["events"])
        self.assertTrue(observer.ready)

        fault = ProfileFeatureNegative(
            FLOATY_BOUNCE, FLOATY_BOUNCE + ":missing-feature-evidence")
        row = {"events": source["events"] + [{
            "frame": 54, "kind": "native", "data": {
                "event": "CONTROL_RETURNED", "actorHandle": 8}}]}
        changed = fault.mutate(row, source["subjects"])
        self.assertTrue(fault.applied)
        self.assertEqual(
            [event["data"]["event"] for event in changed["events"]],
            ["WORLD_EFFECT", "WORLD_EFFECT", "CONTROL_RETURNED"])
        self.assertEqual(source["events"][0]["data"]["event"],
                         "CONTROL_RETURNED")
        observer.events = changed["events"]
        self.assertFalse(observer.ready)
        self.assertIn("Jigglypuff has fewer than two control-return events",
                      observer.finish()["failures"])

        fault_name = FLOATY_BOUNCE + ":missing-feature-evidence"
        rejection = {"passed": False, "failures": [{"code": "measurement-incomplete"}],
                     "measurements": {FLOATY_BOUNCE: observer.result()}}
        validate_negative_result(FLOATY_BOUNCE, rejection, fault_name)
        wrong_reason = deepcopy(rejection)
        wrong_reason["measurements"][FLOATY_BOUNCE]["failures"] = ["unrelated"]
        with self.assertRaisesRegex(ValueError, "control-return loss"):
            validate_negative_result(FLOATY_BOUNCE, wrong_reason, fault_name)


if __name__ == "__main__":
    unittest.main()
