"""Prepared trace startup coverage, not gameplay proof."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_test_contract import TestEvaluator
from tools.overworld.test_devtools_test_contract import recipe, snapshot, event


def sample(frame):
    value = snapshot(frame)
    value.update(prepared=True, nativeCycle=frame * 2, fieldAvailable=True,
                 observationBoundary="main-task-queue-completion",
                 nativeObservation={"sequence": 2})
    return value


def evaluator():
    test = recipe(); test["mode"] = "prepared"
    result = TestEvaluator(test)
    result.observe(sample(10), count_frame=False)
    return result


class StartBoundaryTests(unittest.TestCase):
    def test_two_completions_seed_sequence_without_event_or_frame_credit(self):
        value = evaluator(); endpoint = sample(12)
        prefix = [event(12, "MOTION_STARTED", 1)]
        before = deepcopy(prefix)
        result = value.observe_start_boundary(endpoint, prefix, 10)
        self.assertNotEqual(result["state"], "failed", result)
        self.assertEqual(value.latest, endpoint)
        self.assertEqual(value.last_sequence, {1: 1})
        self.assertEqual(value.events, {})
        self.assertEqual(value.frames, 0)
        self.assertEqual(value.sampled_frames, 0)
        self.assertEqual(prefix, before)
        value.bind("subject", endpoint)
        result = value.observe(sample(13), [event(13, sequence=2)])
        self.assertNotEqual(result["state"], "failed", result)

    def test_old_native_diagnostics_are_retained_without_credit(self):
        value = evaluator()
        prefix = [dict(frame=frame, kind="native-observation", data=dict(
            observation="party-getter", sequence=sequence, setupMode="prepared"))
            for frame, sequence in ((2, 1), (8, 2))]
        result = value.observe_start_boundary(sample(12), prefix, 10)
        self.assertNotEqual(result["state"], "failed", result)
        self.assertEqual(value.events, {})

    def test_invalid_or_incomplete_prefix_fails(self):
        for fault in ("gap", "duplicate", "old-semantic", "future", "native-gap", "native-end", "coverage"):
            value = evaluator(); prefix = [event(12, sequence=1)]
            if fault == "gap": prefix[0]["data"]["sequence"] = 2
            elif fault == "duplicate": prefix.append(deepcopy(prefix[0]))
            elif fault == "old-semantic": prefix[0]["frame"] = 9
            elif fault == "future": prefix[0]["frame"] = 13
            elif fault in ("native-gap", "native-end"):
                prefix = [dict(frame=2, kind="native-observation", data=dict(sequence=n))
                          for n in ((1, 3) if fault == "native-gap" else (1,))]
            else: prefix.append(dict(frame=12, kind="trace-status", data=dict(coverageComplete=False)))
            with self.subTest(fault=fault):
                result = value.observe_start_boundary(sample(12), prefix, 10)
                self.assertEqual(result["state"], "failed", result)
                self.assertEqual(value.latest["frame"], 10)
                self.assertEqual(value.events, {})

    def test_no_subjects_or_existing_observation_can_cross_start_boundary(self):
        value = evaluator(); value.bind("subject", sample(10))
        with self.assertRaises(ValueError): value.observe_start_boundary(sample(12), [], 10)
        value = evaluator(); value.observe(sample(11))
        with self.assertRaises(ValueError): value.observe_start_boundary(sample(12), [], 11)

    def test_missing_prefix_does_not_waive_next_sequence_gap(self):
        value = evaluator(); value.observe_start_boundary(sample(12), [], 10)
        value.bind("subject", sample(12))
        result = value.observe(sample(13), [event(13, sequence=2)])
        self.assertEqual(result["state"], "failed")


if __name__ == "__main__": unittest.main()
