"""Shared-controller copy policy: same proof, no repeated untouched-frame copy.

These are host checks of the actual controller and chain evaluator. They do not
run a core, waive input freshness, or grant new gameplay acceptance.
"""
from copy import deepcopy
import inspect
import unittest
from unittest.mock import patch

from tools.overworld import control
from tools.overworld.devtools_test_contract import TestEvaluator
from tools.overworld import test_devtools_test_proof as proof_fixtures


def eager_replay():
    """Restore just the old eager-copy policy in the actual current function."""
    source = inspect.getsource(control._replay_shared_test)
    seam = "if can_mutate:"
    if source.count(seam) != 1:
        raise AssertionError("controller copy-policy comparison seam differs")
    namespace = dict(control.__dict__)
    exec(compile(source.replace(seam, "if True:"), "<eager shared replay comparison>", "exec"), namespace)
    return namespace["_replay_shared_test"]


class ReplayCopyOnWriteTests(unittest.TestCase):
    def setUp(self):
        self.fixture = proof_fixtures.SharedLedybaProofTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def replay(self, rows=None, fault=None, replay=None):
        with patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=self.fixture.inputs):
            return (replay or control._replay_shared_test)(
                self.fixture.test, self.fixture.rows if rows is None else rows,
                fault=fault, repo=self.fixture.root)

    def test_ordinary_frames_reach_real_evaluator_without_a_second_copy(self):
        originals = {sample["frame"]: sample for row in self.fixture.rows for sample in row.get("samples", [])}
        seen = []
        observe = TestEvaluator.observe

        def checked(evaluator, snapshot, events=(), count_frame=True):
            if snapshot["frame"] in originals:
                seen.append(snapshot is originals[snapshot["frame"]])
            return observe(evaluator, snapshot, events, count_frame=count_frame)

        before = deepcopy(self.fixture.rows)
        with patch.object(TestEvaluator, "observe", checked):
            result = self.replay()
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(seen), len(originals))
        self.assertTrue(all(seen), "controller repeated the evaluator's frame copy")
        self.assertEqual(self.fixture.rows, before)

    def test_all_six_negative_results_and_positive_are_exactly_equal(self):
        before = deepcopy(self.fixture.rows)
        eager = eager_replay()
        for fault in (None, "absent-subject", "stale-subject", *(
                "missing-meaning:" + name for name in control._LEDYBA_REQUIRED_MEANINGS)):
            with self.subTest(fault=fault):
                old = self.replay(fault=fault, replay=eager)
                new = self.replay(fault=fault)
                self.assertEqual(new, old)
                self.assertEqual(new["passed"], fault is None)
                self.assertEqual(self.fixture.rows, before, "replay changed retained memory data")

    def test_subject_controls_copy_the_mutated_frame_but_not_setup(self):
        originals = {sample["frame"]: sample for row in self.fixture.rows for sample in row.get("samples", [])}
        first_observed = next(row["samples"][0]["frame"] for row in self.fixture.rows
                              if row.get("phase") == "observe" and row.get("samples"))
        observe = TestEvaluator.observe
        for fault in ("absent-subject", "stale-subject"):
            seen = {}

            def checked(evaluator, snapshot, events=(), count_frame=True):
                if snapshot["frame"] in originals:
                    seen[snapshot["frame"]] = snapshot is originals[snapshot["frame"]]
                return observe(evaluator, snapshot, events, count_frame=count_frame)

            with self.subTest(fault=fault), patch.object(TestEvaluator, "observe", checked):
                self.assertFalse(self.replay(fault=fault)["passed"])
                self.assertFalse(seen[first_observed], "control changed the original subject frame")
                self.assertTrue(all(same for frame, same in seen.items() if frame < first_observed))

    def test_malformed_coverage_still_has_exact_same_failure(self):
        eager = eager_replay()
        for damage in ("missing-frame", "wrong-event-frame", "missing-active-object", "wrong-profile"):
            rows = deepcopy(self.fixture.rows)
            row = next(row for row in rows if row.get("phase") == "observe" and row.get("samples"))
            if damage == "missing-frame": row["samples"].pop()
            elif damage == "wrong-event-frame": row["events"].append({"frame": -1, "kind": "native"})
            elif damage == "missing-active-object": row["samples"][0]["actors"][0]["engineIdentity"]["active"] = False
            else: row["samples"][0]["actors"][0]["behaviorFingerprint"] ^= 1
            outcomes = []
            for replay in (eager, control._replay_shared_test):
                try:
                    result = self.replay(rows=rows, replay=replay)
                except control.ValidationFailure as error:
                    outcomes.append(("exception", str(error)))
                else:
                    self.assertFalse(result["passed"], damage)
                    outcomes.append(("result", result))
            with self.subTest(damage=damage): self.assertEqual(*outcomes)

    def test_controller_acceptance_and_input_hash_rejection_are_unchanged(self):
        with patch.object(control, "_replay_shared_test", eager_replay()):
            old = self.fixture.finish()
        self.assertTrue(old["acceptedProof"], old)
        self.assertEqual(self.fixture.finish(), old)
        # No source/ROM/stream hash cache is added. A changed file is rejected
        # on the next call through the actual controller even after a pass.
        self.fixture.observations.write_text(self.fixture.observations.read_text() + "\n")
        rejected = self.fixture.finish()
        self.assertFalse(rejected["acceptedProof"], rejected)
        self.assertIn("hash/size differs", rejected["proofAcceptance"]["reason"])


if __name__ == "__main__":
    unittest.main()
