"""D1 shared-job integration controls. Fake worker, no core or gameplay claim."""
from copy import deepcopy
import json
from tools.overworld.devtools_evidence_stream import load_observations
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld import control
from tools.overworld.devtools import Service
from tools.overworld.devtools_runtime import DevtoolsFailure, DevtoolsSession
from tools.overworld.devtools_test_contract import TestEvaluator
from tools.overworld.test_devtools_observer import Fixture as NativeFixture
from tools.overworld.test_devtools_jobs import FrameWorker
from tools.overworld.test_devtools_test_contract import recipe
from tools.overworld.test_devtools_chain_measurement import SCHEMA, SOURCE, Stream


class SetupWorker(FrameWorker):
    """Expose changing public setup state while the player stands still."""
    def call(self, op, args=None):
        value = super().call(op, args)

        def enrich(snapshot):
            frame = snapshot["frame"]
            snapshot.update(observationBoundary="main-task-queue-completion",
                party=[{"slot": 0, "identityVerified": True, "hp": frame}],
                partyObservation={"frame": frame, "boundary": "main-task-queue-completion"})
            return snapshot

        if isinstance(value, dict) and "snapshot" in value:
            value["samples"] = [enrich(item) for item in value["samples"]]
            value["snapshot"] = enrich(value["snapshot"])
        elif isinstance(value, dict) and "actors" in value:
            enrich(value)
        return value


class D1WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="devtools-d1-workflow-")
        self.root = Path(self.temp.name)
        (self.root / "test.nds").write_bytes(b"host rom fixture")
        (self.root / "test.sav").write_bytes(b"host save fixture")
        (self.root / "tools/overworld").mkdir(parents=True)
        (self.root / "tools/overworld/runtime_proof_registry.json").write_text('{"sharedTests": {}}')
        FrameWorker.block = FrameWorker.entered = None
        FrameWorker.move_player = FrameWorker.unrelated_motion = False
        patcher = patch("tools.overworld.devtools_jobs.source_record", return_value={"content": "host-source"})
        patcher.start(); self.addCleanup(patcher.stop)
        self.service = Service(self.root, SetupWorker)

    def tearDown(self):
        if self.service.tests.thread:
            self.service.tests.thread.join(5)
        self.service._stop()
        self.temp.cleanup()

    def make_recipe(self):
        value = recipe()
        value["subjects"] = []
        value["assertions"] = [{"kind": "frame-count", "operator": "gte", "value": 2}]
        return value

    def run_job(self, value):
        self.service.tests.save(value["id"], value)
        launched = self.service.command({"op": "test.start", "args": {"name": value["id"]}})
        self.assertTrue(launched["ok"], launched)
        self.service.tests.thread.join(5)
        self.assertFalse(self.service.tests.thread.is_alive())
        return self.service.tests.status()

    def test_true_setup_skip_never_sends_input_and_false_replay_skip_fails(self):
        value = self.make_recipe()
        value["setup"] = [{"id": "already-eligible", "op": "step", "args": {"frames": 3, "keys": ["Y"]},
            "budget": {"maxSeconds": 10, "maxFrames": 3, "noProgressFrames": 3},
            "skipIf": {"kind": "party-field", "slot": 0, "path": "hp", "operator": "gte", "value": 1}}]
        done = self.run_job(value)
        self.assertTrue(done["passed"], done)
        self.assertFalse(any(op == "step" and args["keys"] == ["Y"] for op, args in SetupWorker.instances[-1].calls))
        rows = load_observations(Path(done["observationsArtifact"]["path"]))
        skipped = [row for row in rows if row.get("command") == "skip"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["action"], "already-eligible")
        self.assertTrue(control._replay_shared_test(value, rows, repo=self.root)["passed"])
        changed = deepcopy(value); changed["setup"][0]["skipIf"]["value"] = 9
        with self.assertRaisesRegex(control.ValidationFailure, "skip lacks"):
            control._replay_shared_test(changed, rows, repo=self.root)

    def test_until_watchdog_tracks_the_public_predicate_not_stationary_player(self):
        value = self.make_recipe()
        value["setup"] = [{"id": "observe-normal-setup-progress", "op": "step",
            "args": {"frames": 8, "keys": ["A"], "until": {
                "kind": "party-field", "slot": 0, "path": "hp", "operator": "gte", "value": 5}},
            "budget": {"maxSeconds": 10, "maxFrames": 8, "noProgressFrames": 2}}]
        done = self.run_job(value)
        self.assertTrue(done["passed"], done.get("evaluation", done))
        calls = [args for op, args in SetupWorker.instances[-1].calls if op == "step" and args["keys"] == ["A"]]
        self.assertEqual(len(calls), 4)

    def test_measurement_requires_installed_current_inputs(self):
        value = recipe()
        value["subjects"][0]["acquire"] = "spawn"
        value["measurements"] = [{"kind": "ledyba-chain-v1", "subject": "subject"}]
        evaluator = TestEvaluator(value)
        with self.assertRaisesRegex(ValueError, "source inputs are missing"):
            evaluator.install_measurements({})
        evaluator.observe(Stream().items[0][0], count_frame=False)
        result = evaluator.finish()
        self.assertFalse(result["passed"])
        self.assertIn("current source inputs", str(result["failures"]))

    def test_cached_complete_frame_does_not_hide_a_later_native_observer_failure(self):
        native_root = self.root / "native"
        native_root.mkdir()
        native = NativeFixture(native_root)
        self.addCleanup(native.observer.close)
        native.observer.completed_frame(42)
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.sample_error = None
        session.latest_frame = {"frame": 42, "nativeObservation": native.observer.snapshot()}
        session.native_observation, session.party_getter_hooks = native.observer, native.hooks
        session.latest_party_frame, session.latest_party = 42, []
        session.party_getter_checks, session.latest_resolved_profiles = {}, []
        session.prepared = False
        session.terrain = lambda radius: {"terrain": {}}
        # Run the real installed observer against an invalid two-tile native
        # reservation after frame42. No later queue has copied its error yet.
        native.enter("player-step-admitted", r0=native.player_pointer, r1=3)
        native.player.update(x_prev=550, y_prev=381, x=552)
        native.returned(0)
        self.assertIn("exactly one cardinal tile", native.hooks.error)
        self.assertIsNone(session.sample_error)
        self.assertIsNone(session.latest_frame["nativeObservation"]["error"])
        with self.assertRaisesRegex(DevtoolsFailure, "cardinal tile"):
            session.snapshot()

    def test_complete_measurement_does_not_replace_required_subject_binding(self):
        value = recipe()
        value["subjects"][0]["acquire"] = "spawn"
        value["measurements"] = [{"kind": "ledyba-chain-v1", "subject": "subject"}]
        value["budgets"].update(maxFrames=5000)
        value["assertions"] = [{"kind": "measurement-complete", "measurement": "ledyba-chain-v1"}]
        evaluator = TestEvaluator(value)
        evaluator.install_measurements({"ledyba-chain-v1": {"schema": SCHEMA, "sourceSha256": SOURCE}})
        for snapshot, events in Stream().complete().items:
            evaluator.observe(snapshot, events)
        result = evaluator.finish()
        self.assertTrue(result["measurements"]["ledyba-chain-v1"]["passed"], result["failures"])
        self.assertFalse(result["passed"])
        self.assertIn("subject-unbound", [failure["code"] for failure in result["failures"]])


if __name__ == "__main__":
    unittest.main()
