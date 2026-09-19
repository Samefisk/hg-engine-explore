"""Controls at the shared job/worker boundary, not gameplay claims."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.overworld.devtools import Service
from tools.overworld.devtools_evidence_stream import load_observations
from tools.overworld.devtools_jobs import _command_snapshot, _valid_completed_frame_batch
from tools.overworld.test_devtools_test_contract import recipe, snapshot


class FrameWorker:
    block = None
    entered = None
    unrelated_motion = False
    move_player = False
    capture_error = False
    wrong_subject = False
    instances = []

    def __init__(self, root, directory):
        self.frame = 1
        self.closed = False
        self.calls = []
        self.instances.append(self)

    def call(self, op, args=None):
        self.calls.append((op, args))
        if op == "step":
            if self.entered: self.entered.set()
            if self.block: self.block.wait(3)
            samples = []
            for _ in range(args["frames"]):
                self.frame += 1
                current = snapshot(self.frame)
                if self.wrong_subject: current["actors"][0]["species"] = 56
                if self.move_player: current["player"]["x"] = self.frame
                if self.unrelated_motion:
                    other = deepcopy(current["actors"][0])
                    other.update(species=56, commitSequence=self.frame)
                    other["handle"].update(value=65537, slot=1)
                    current["actors"].append(other)
                samples.append(current)
            result = {"snapshot": samples[-1], "samples": samples, "events": [],
                      "completedGameFrames": len(samples), "nativeCycles": len(samples),
                      "cycleIntervals": [{"nativeCycle": sample["frame"], "cpuNs": 5, "wallNs": 10}
                                         for sample in samples]}
            self.last_step_result = deepcopy(result)
            return result
        if op == "capture":
            if self.capture_error:
                raise RuntimeError("screenshot transport must not run in checked tests")
            Path(args["path"]).write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            return {"path": args["path"], "frame": self.frame}
        if op == "diagnostics":
            return {"cpu": {"pc": 0x02000000}, "fieldControl": {"mapId": 33},
                    "lastCompleteSnapshot": snapshot(self.frame)}
        if op == "observer-control.close":
            return {"snapshot": snapshot(self.frame), "frame": self.frame,
                    "closed": True, "advancedFrames": 0, "observerControl": None}
        return snapshot(self.frame)

    def close(self): self.closed = True


class JobsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "test.nds").write_bytes(b"rom")
        (self.root / "test.sav").write_bytes(b"save")
        (self.root / "tools/overworld").mkdir(parents=True)
        (self.root / "tools/overworld/runtime_proof_registry.json").write_text('{"sharedTests": {}}')
        FrameWorker.block = FrameWorker.entered = None
        FrameWorker.unrelated_motion = False
        FrameWorker.move_player = False
        FrameWorker.capture_error = False
        FrameWorker.wrong_subject = False
        source = patch("tools.overworld.devtools_jobs.source_record", return_value={"content": "host-source"})
        source.start(); self.addCleanup(source.stop)
        space = patch("tools.overworld.devtools_jobs.shutil.disk_usage",
                      return_value=SimpleNamespace(free=8 * 1024**3))
        space.start(); self.addCleanup(space.stop)
        self.service = Service(self.root, FrameWorker)

    def tearDown(self):
        if FrameWorker.block: FrameWorker.block.set()
        if self.service.tests.thread: self.service.tests.thread.join(5)
        self.service._stop()
        self.temp.cleanup()

    def launch(self, value=None):
        value = value or recipe()
        value["setup"].append({"id": "bind", "op": "bind", "args": {"subject": "subject"},
            "budget": {"maxSeconds": 10, "maxFrames": 2, "noProgressFrames": 2}})
        self.service.tests.save(value["id"], value)
        return self.service.command({"op": "test.start", "args": {"name": value["id"]}})

    def finish(self):
        self.service.tests.thread.join(5)
        self.assertFalse(self.service.tests.thread.is_alive())
        return self.service.tests.status()

    def test_failed_initial_raw_boundary_is_retained_before_close(self):
        from tools.overworld.devtools_test_contract import TestEvaluator
        class RejectInitial(TestEvaluator):
            uses_raw_records = True
            def observe_record(self, record, **kwargs):
                self.fail("bad-initial-boundary", "synthetic rejected boot boundary")
                return self.result()
        with patch("tools.overworld.devtools_jobs.TestEvaluator", RejectInitial):
            self.assertTrue(self.launch()["ok"])
            done = self.finish()
        self.assertFalse(done["passed"])
        rows = load_observations(Path(done["observationsArtifact"]["path"]))
        self.assertEqual(len(rows), 1)
        self.assertIn("initialSnapshot", rows[0])
        self.assertEqual(done["totalGameFrames"], 0)
        self.assertIsNone(self.service.worker)

    def test_job_uses_the_evaluator_raw_boundary_set(self):
        from tools.overworld.devtools_jobs import RAW_BOUNDARY_READERS
        from tools.overworld.devtools_test_contract import ACCELERATION, RAW_BOUNDARY_MEASUREMENTS
        self.assertEqual(RAW_BOUNDARY_READERS, RAW_BOUNDARY_MEASUREMENTS | {ACCELERATION})

    def test_extra_completed_frames_require_a_loading_transition(self):
        loading = [{"frame": 8, "fieldAvailable": False},
                   {"frame": 9, "fieldAvailable": False}]
        self.assertTrue(_valid_completed_frame_batch(1, 2, loading))
        self.assertTrue(_valid_completed_frame_batch(
            1, 2, [loading[0], {"frame": 9, "fieldAvailable": True}]))
        self.assertFalse(_valid_completed_frame_batch(
            1, 2, [{"frame": 8, "fieldAvailable": True},
                   {"frame": 9, "fieldAvailable": True}]))
        self.assertFalse(_valid_completed_frame_batch(1, 2, loading[:1]))
        self.assertTrue(_valid_completed_frame_batch(1, 2, loading, allow_extra=True))

    def test_turn_skid_uses_its_bound_subject_arguments(self):
        from tools.overworld.devtools_jobs import _walk_matrix_args
        from tools.overworld.devtools_test_contract import TURN_SKID
        turn = SimpleNamespace(measurements={TURN_SKID: object()},
            turn_skid_args=lambda subject, snapshot: ("turn", subject, snapshot),
            matrix_args=lambda subject, snapshot: ("matrix", subject, snapshot))
        matrix = SimpleNamespace(measurements={"walk-matrix-v1": object()},
            turn_skid_args=turn.turn_skid_args, matrix_args=turn.matrix_args)
        self.assertEqual(_walk_matrix_args(turn, "actor", 1), ("turn", "actor", 1))
        self.assertEqual(_walk_matrix_args(matrix, "actor", 2), ("matrix", "actor", 2))

    def test_real_shared_dispatch_saves_complete_evidence(self):
        self.assertTrue(self.launch()["ok"])
        done = self.finish()
        self.assertTrue(done["passed"], done)
        self.assertFalse(done["acceptedProof"])
        self.assertIn("proof was not accepted", done["nextAction"])
        manifest = json.loads(Path(done["manifest"]).read_text())
        self.assertEqual(manifest["observedFrames"], 2)
        self.assertTrue(Path(manifest["observationsArtifact"]["path"]).is_file())
        self.assertEqual(Path(manifest["observationsArtifact"]["path"]).name, "observations.jsonl.gz")
        self.assertFalse(Path(manifest["manifest"]).with_name("observations.jsonl").exists())
        artifact = Path(manifest["observationsArtifact"]["path"])
        exported, _ = self.service.artifact(f"{artifact.parent.name}/{artifact.name}")
        self.assertEqual(exported, artifact.read_bytes())
        self.assertTrue(exported.startswith(b"\x1f\x8b"))
        self.assertIsNone(self.service.worker)

    def test_chain_arm_retains_exact_native_snapshot_not_cached_terrain(self):
        native = snapshot(12)
        cached = {**deepcopy(native), "terrain": {"observation": {"lastCompletedGameFrame": 1}}}
        receipt = {"snapshot": native, "armed": True, "prepared": True}
        self.service._observe({"snapshot": cached})
        self.service._observe(receipt)
        self.assertIn("terrain", self.service.snapshot)
        endpoint = _command_snapshot("chain-retry", receipt, self.service.snapshot)
        self.assertEqual(endpoint, native)
        self.assertNotIn("terrain", endpoint)
        endpoint["frame"] = 99
        self.assertEqual(native["frame"], 12)
        with self.assertRaises(KeyError):
            _command_snapshot("chain-retry", {}, cached)

    def test_low_disk_rejects_before_creating_job_or_worker(self):
        with patch("tools.overworld.devtools_jobs.shutil.disk_usage",
                   return_value=SimpleNamespace(free=1024**3 - 1)):
            reply = self.launch()
        self.assertFalse(reply["ok"])
        self.assertIn("test-storage-low", str(reply))
        self.assertIsNone(self.service.worker)
        self.assertIsNone(self.service.tests.current)
        self.assertIsNone(self.service.tests.thread)
        self.assertFalse(list((self.root / "build/overworld-devtools").glob("test-*")))

    def test_low_disk_mid_run_retains_failure_and_closes_owned_worker(self):
        before = len(FrameWorker.instances)

        def space(_path):
            stepped = any(worker.frame > 1 for worker in FrameWorker.instances[before:])
            return SimpleNamespace(free=191 * 1024**2 if stepped else 8 * 1024**3)

        with patch("tools.overworld.devtools_jobs.shutil.disk_usage", side_effect=space):
            self.assertTrue(self.launch()["ok"])
            done = self.finish()
        self.assertFalse(done["passed"])
        self.assertFalse(done["acceptedProof"])
        self.assertIn("test-storage-low", str(done["evaluation"]["failures"]))
        self.assertEqual(len(FrameWorker.instances[before:]), 1)
        self.assertGreater(FrameWorker.instances[-1].frame, 1)
        self.assertTrue(FrameWorker.instances[-1].closed)
        self.assertIsNone(self.service.worker)
        self.assertEqual(json.loads(Path(done["manifest"]).read_text())["state"], "failed")

    def test_cadence_nurse_detour_is_reported_and_rejected_before_boot(self):
        root = Path(__file__).resolve().parents[2]
        value = json.loads((root / "tests/overworld/test-recipes/world.cyndaquil-normal-setup.json").read_text())
        value["id"] = "test.slow-cadence"
        old, new = "cyndaquil-normal-setup-v1", "unmounted-cadence-v1"
        value["measurements"][0]["kind"] = new
        for predicate in value["assertions"] + [a["args"]["predicate"] for a in value["actions"]]:
            if predicate.get("measurement") == old:
                predicate["measurement"] = new
        response = self.service.command({"op": "test.validate", "args": {"test": value}})
        self.assertTrue(response["ok"], response)
        self.assertTrue(response["result"]["setupEfficiency"]["warnings"])
        self.service.tests.save(value["id"], value)
        with patch.object(self.service, "worker_factory") as factory:
            response = self.service.command({"op": "test.start", "args": {"name": value["id"]}})
            self.assertFalse(response["ok"])
            self.assertIn("avoidable test setup", str(response))
            factory.assert_not_called()
        self.assertIsNone(self.service.tests.thread)
        self.assertIsNone(self.service.worker)
        self.assertIsNone(self.service.tests.current)

    def test_rejected_native_frame_chunk_is_retained_before_shutdown(self):
        class ExtraFrameWorker(FrameWorker):
            def call(self, op, args=None):
                if op == "step":
                    result = super().call(op, {**args, "frames": args["frames"] + 1})
                    result["requestedGameFrames"] = args["frames"]
                    return result
                return super().call(op, args)
        self.service.worker_factory = ExtraFrameWorker
        self.assertTrue(self.launch()["ok"])
        done = self.finish()
        self.assertFalse(done["passed"])
        self.assertEqual(done["evaluation"]["failures"][0]["code"], "incomplete-frame-evidence")
        rows = load_observations(Path(done["observationsArtifact"]["path"]))
        rejected = [row for row in rows if "samples" in row][-1]
        self.assertEqual(rejected["requestedGameFrames"], 2)
        self.assertEqual(rejected["completedGameFrames"], 3)
        self.assertEqual([sample["frame"] for sample in rejected["samples"]], [2, 3, 4])
        self.assertNotIn("snapshot", rejected)
        self.assertTrue(Path(done["failureArtifact"]["path"]).is_file())
        self.assertIsNone(self.service.worker)

    def test_raw_neutral_setup_counts_every_extra_completion_and_keeps_budgets(self):
        from tools.overworld.devtools_test_contract import TestEvaluator
        # Isolate job scheduling/accounting here. The real raw meters have
        # their own dense-sample/native-cycle controls, not this fake meter.
        class RawGate(TestEvaluator):
            uses_raw_records = True
            def observe_record(self, record, *, frame_callback=None, full_report=True):
                if "initialSnapshot" in record:
                    self._raw_frame = record["initialSnapshot"]["frame"]
                    return self.observe(record["initialSnapshot"], count_frame=False)
                for sample in record.get("samples", []):
                    self._raw_frame = sample["frame"]
                    self.observe(sample, count_frame=record["phase"] == "observe")
                    if frame_callback:
                        frame_callback(sample, self)
                return self.result()
        class ExtraSetupWorker(FrameWorker):
            def call(self, op, args=None):
                if op == "step" and self.frame == 1:
                    result = super().call(op, {**args, "frames": args["frames"] + 1})
                    for sample in result["samples"]:
                        sample["player"]["x"] = sample["frame"]
                    result["snapshot"] = deepcopy(result["samples"][-1])
                    return result
                return super().call(op, args)
        self.service.worker_factory = ExtraSetupWorker
        for frame_bound in (1, 4):
            with self.subTest(frame_bound=frame_bound):
                value = recipe(); value["id"] += ".extra-setup-" + str(frame_bound)
                value["setup"] = [{"id": "neutral-arrival", "op": "wait", "args": {"predicate": {
                    "kind": "player-field", "path": "x", "operator": "gte", "value": 3}},
                    "budget": {"maxSeconds": 10, "maxFrames": frame_bound, "noProgressFrames": frame_bound}}]
                with patch("tools.overworld.devtools_jobs.TestEvaluator", RawGate):
                    self.assertTrue(self.launch(value)["ok"])
                    done = self.finish()
                self.assertEqual(done["passed"], frame_bound == 4, done["evaluation"])
                self.assertEqual(done["totalGameFrames"], 4 if frame_bound == 4 else 2)
                if frame_bound == 1:
                    self.assertEqual(done["evaluation"]["failures"][0]["code"], "action-frame-budget")
                self.assertIsNone(self.service.worker)

    def test_prepared_command_reaches_raw_checker_before_observation(self):
        from tools.overworld.devtools_test_contract import TestEvaluator
        received = []
        class RawGate(TestEvaluator):
            uses_raw_records = True
            def observe_record(self, record, *, frame_callback=None, full_report=True):
                received.append(deepcopy(record))
                if "initialSnapshot" in record:
                    self._raw_frame = record["initialSnapshot"]["frame"]
                    return self.observe(record["initialSnapshot"], count_frame=False)
                if record.get("command") == "party":
                    self._raw_frame = record["snapshot"]["frame"]
                    return self.observe(record["snapshot"], count_frame=False)
                for sample in record.get("samples", []):
                    self._raw_frame = sample["frame"]
                    self.observe(sample, count_frame=record["phase"] == "observe")
                    if frame_callback: frame_callback(sample, self)
                return self.result()
        class PartyWorker(FrameWorker):
            def call(self, op, args=None):
                if op == "party":
                    self.calls.append((op, args))
                    self.frame += 2
                    return {"snapshot": snapshot(self.frame), "setupBoundary": {"eventsDrained": True},
                            "events": [], "fixtureOnly": True}
                return super().call(op, args)
        self.service.worker_factory = PartyWorker
        value = recipe(); value["mode"] = "prepared"
        value["setup"] = [{"id": "party-ready", "op": "party", "args": {"slot": 1, "hp": 21},
                           "budget": {"maxSeconds": 10, "maxFrames": 4, "noProgressFrames": 4}}]
        with patch("tools.overworld.devtools_jobs.TestEvaluator", RawGate):
            self.assertTrue(self.launch(value)["ok"])
            done = self.finish()
        self.assertTrue(done["passed"], done)
        records = load_observations(Path(done["observationsArtifact"]["path"]))
        command = next(row for row in records if row.get("command") == "party")
        self.assertEqual(command["receipt"]["setupBoundary"], {"eventsDrained": True})
        self.assertTrue(command["receipt"]["fixtureOnly"])
        self.assertEqual(command["receipt"]["events"], [])
        self.assertIn(command, received)
        self.assertEqual(command["snapshot"]["frame"], 3)
        self.assertEqual(done["observedFrames"], 2)
        self.assertEqual(done["totalGameFrames"], 4)
        calls = FrameWorker.instances[-1].calls
        self.assertEqual(sum(op == "record.start" for op, _ in calls), 1)
        self.assertLess(next(i for i, (op, _) in enumerate(calls) if op == "record.start"),
                        next(i for i, (op, _) in enumerate(calls) if op == "party"))

    def test_step_rows_omit_only_endpoint_and_keep_setup_boundaries(self):
        for mode in ("normal", "prepared"):
            with self.subTest(mode=mode):
                value = recipe(); value["mode"] = mode; value["id"] += "." + mode
                skip = deepcopy(value["actions"][0]); skip["id"] = "already-present"
                skip["skipIf"] = {"kind": "actor-present", "subject": "subject"}
                value["setup"] = [skip]
                self.assertTrue(self.launch(value)["ok"])
                done = self.finish()
                self.assertTrue(done["passed"], done)
                rows = load_observations(Path(done["observationsArtifact"]["path"]))
                worker = FrameWorker.instances[-1]
                chunks = [row for row in rows if "samples" in row]
                self.assertEqual(len(chunks), 1)
                self.assertNotIn("snapshot", chunks[0])
                self.assertEqual(chunks[0], {"phase": "observe", "action": "sample",
                    **{key: item for key, item in worker.last_step_result.items() if key != "snapshot"}})
                self.assertEqual(rows[0]["initialSnapshot"]["frame"], 1)
                for command in ("skip", "bind"):
                    boundary = next(row for row in rows if row.get("command") == command)
                    self.assertEqual(boundary["snapshot"]["frame"], 1)
                    self.assertTrue(boundary["snapshot"]["actors"])
                boundaries = [row for row in rows if "boundarySnapshot" in row]
                self.assertEqual(len(boundaries), 1 if mode == "prepared" else 0)
                if boundaries:
                    self.assertEqual(boundaries[0]["boundarySnapshot"]["frame"], 1)
                self.assertTrue(all(args["diagnosticDetails"] is False
                                    for op, args in worker.calls if op == "step"))

    def test_terminal_timing_includes_successful_or_failed_proof_check(self):
        for raises in (False, True):
            with self.subTest(raises=raises):
                clock = [100.0]
                acceptance_statuses = []
                def finalize(test, record, **kwargs):
                    acceptance_statuses.append(self.service.tests.status())
                    self.assertIsNone(self.service.worker)
                    clock[0] += 7.25
                    if raises:
                        raise RuntimeError("controller failed")
                    return {"acceptedProof": False}
                with patch("tools.overworld.devtools_jobs.time.monotonic", side_effect=lambda: clock[0]), \
                        patch("tools.overworld.control.finalize_shared_test", side_effect=finalize):
                    value = recipe(); value["id"] += ".raises" if raises else ".success"
                    self.launch(value)
                    done = self.finish()
                self.assertEqual(len(acceptance_statuses), 1)
                pending = acceptance_statuses[0]
                self.assertEqual(pending["phase"], "acceptance")
                self.assertEqual(pending["state"], "running")
                self.assertFalse(pending["acceptedProof"])
                self.assertIsNone(pending["action"])
                self.assertIn("memory data", pending["nextAction"])
                self.assertEqual(done["executionSeconds"], 0)
                self.assertEqual(done["proofAcceptanceSeconds"], 7.25)
                self.assertEqual(done["elapsedSeconds"], 7.25)
                self.assertAlmostEqual(done["elapsedSeconds"],
                    done["executionSeconds"] + done["proofAcceptanceSeconds"], places=2)
                self.assertEqual(done["passed"], not raises)

    def test_accepted_terminal_result_has_success_hint(self):
        def finalize(_test, _record, **_kwargs):
            return {"passed": True, "acceptedProof": True,
                    "proofAcceptance": {"eligible": True}}
        with patch("tools.overworld.control.finalize_shared_test", side_effect=finalize):
            self.assertTrue(self.launch()["ok"])
            done = self.finish()
        self.assertEqual(done["state"], "completed")
        self.assertTrue(done["passed"])
        self.assertTrue(done["acceptedProof"])
        self.assertEqual(
            done["nextAction"],
            "Accepted proof is complete. No further action is required for this run.",
        )

    def test_valid_job_never_calls_broken_screenshot_transport(self):
        FrameWorker.capture_error = True
        self.assertTrue(self.launch()["ok"])
        done = self.finish()
        self.assertTrue(done["passed"], done)
        self.assertEqual(done["observedFrames"], 2)
        self.assertIsNone(done["visualArtifact"])
        self.assertNotIn("capture", [op for op, _ in FrameWorker.instances[-1].calls])
        self.assertIsNone(self.service.worker)

    def test_cancel_during_acceptance_cannot_publish_a_pass(self):
        def finalize(test, record, **kwargs):
            canceled = self.service.tests.cancel(record["runId"])
            self.assertEqual(canceled["state"], "canceling")
            self.assertIsNone(self.service.worker)
            return {"passed": True, "acceptedProof": True}
        with patch("tools.overworld.control.finalize_shared_test", side_effect=finalize):
            self.launch()
            done = self.finish()
        self.assertEqual(done["state"], "canceled")
        self.assertFalse(done["passed"])
        self.assertFalse(done["acceptedProof"])
        saved = json.loads(Path(done["manifest"]).read_text())
        self.assertEqual(saved["state"], "canceled")
        self.assertFalse(saved["acceptedProof"])

    def test_wrong_native_subject_fails_without_images_and_keeps_native_diagnostics(self):
        FrameWorker.wrong_subject = True
        for broken_capture in (False, True):
            with self.subTest(broken_capture=broken_capture):
                FrameWorker.capture_error = broken_capture
                value = recipe()
                value["id"] += ".broken-image" if broken_capture else ".available-image"
                self.assertTrue(self.launch(value)["ok"])
                done = self.finish()
                self.assertFalse(done["passed"], done)
                self.assertIn("observation-failed", str(done["evaluation"]["failures"]))
                calls = [op for op, _ in FrameWorker.instances[-1].calls]
                self.assertIn("step", calls)
                self.assertIn("diagnostics", calls)
                self.assertNotIn("capture", calls)
                self.assertIsNone(done["visualArtifact"])
                failure = json.loads(Path(done["failureArtifact"]["path"]).read_text())
                self.assertEqual(failure["native"]["cpu"], {"pc": 0x02000000})
                self.assertEqual(failure["native"]["fieldControl"], {"mapId": 33})
                self.assertIn("lastCompleteSnapshot", failure["native"])
                self.assertEqual(failure["lastSnapshot"]["actors"][0]["species"], 56)
                self.assertNotIn("capture", failure)
                self.assertIsNone(self.service.worker)

    def test_control_job_keeps_normal_boot_trace_and_evaluator_gate(self):
        # Transport seam only. The real contract/measurement has independent
        # baseline tests; this fake gate proves its rejection precedes a write.
        from tools.overworld.devtools_test_contract import TestEvaluator
        gate_calls = []
        rejected = [False]
        class Gate(TestEvaluator):
            def __init__(self, test):
                base = recipe()
                super().__init__(base)
            def observer_control_args(self, subject, fault):
                gate_calls.append((subject, fault))
                if rejected[0]: raise ValueError("baseline has not passed")
                return {"subject": deepcopy(self.subjects[subject]), "kind": fault, "maxFrames": 1200}
            def observer_control_cleanup(self, receipt):
                self.cleanup = receipt
        for reject in (False, True):
            with self.subTest(reject=reject):
                rejected[0] = reject
                value = recipe(); value["id"] += ".reject" if reject else ".arm"
                value["mode"] = "observer-control"
                # Cleanup routing follows the declared control kind, not the
                # mode shared with the separate spawn-height read control.
                value["measurements"] = [{"kind": "live-observer-control-v1", "subject": "subject"}]
                value["actions"].append({"id": "arm", "op": "observer-control",
                    "args": {"subject": "subject", "fault": "render-stall"},
                    "budget": {"maxSeconds": 10, "maxFrames": 2, "noProgressFrames": 2}})
                with patch("tools.overworld.devtools_jobs.validate_test", side_effect=deepcopy), \
                        patch("tools.overworld.devtools_jobs.TestEvaluator", Gate), \
                        patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value={}), \
                        patch("tools.overworld.control.prepare_shared_test", return_value={"passed": True}), \
                        patch.object(self.service, "_start", wraps=self.service._start) as start:
                    self.assertTrue(self.launch(value)["ok"])
                    done = self.finish()
                worker = FrameWorker.instances[-1]
                self.assertEqual(start.call_args.args[0]["mode"], "normal")
                operations = [op for op, _ in worker.calls]
                self.assertEqual(operations.count("record.start"), 1)
                self.assertLess(operations.index("record.start"), operations.index("step"))
                self.assertEqual(operations.count("observer-control.arm"), 0 if reject else 1)
                self.assertEqual(operations.count("observer-control.close"), 1)
                self.assertIsNotNone(done["observerControlCleanup"])
                if reject:
                    self.assertFalse(done["passed"])
                    self.assertIn("baseline has not passed", str(done["evaluation"]["failures"]))
                else:
                    self.assertTrue(done["evaluation"]["passed"], done)
                    self.assertFalse(done["acceptedProof"])  # Mock gate is not a control proof.
                    rows = load_observations(Path(done["observationsArtifact"]["path"]))
                    armed = next(row for row in rows if row.get("command") == "observer-control")
                    self.assertEqual(armed["snapshot"]["frame"], 3)
                    self.assertEqual(armed["receipt"]["frame"], 3)
                    cleanup = rows[-1]
                    self.assertEqual(cleanup["command"], "observer-control.close")
                    self.assertEqual(cleanup["snapshot"]["frame"], 3)
                    self.assertEqual(cleanup["snapshot"], cleanup["receipt"]["snapshot"])
                    self.assertNotIn("screenshot", cleanup["snapshot"])
        self.assertEqual(gate_calls, [("subject", "render-stall")] * 2)

    def test_attempt_identity_is_durable_before_preflight_without_a_session(self):
        captured = []
        def preflight(*args, **kwargs):
            manifest = Path(self.service.tests.status()["manifest"])
            retained = json.loads(manifest.read_text())
            captured.append(retained["attemptIdentity"])
            self.assertEqual(retained["phase"], "preflight")
            self.assertNotIn("identity", retained)
            raise RuntimeError("fixture fails before it can return a receipt")
        with patch("tools.overworld.control.prepare_shared_test", side_effect=preflight):
            self.launch()
            done = self.finish()
        self.assertFalse(done["passed"])
        self.assertIsNone(self.service.worker)
        self.assertEqual(len(captured), 1)
        self.assertEqual(done["attemptIdentity"], captured[0])
        self.assertEqual(captured[0]["source"], {"content": "host-source"})
        self.assertEqual(captured[0]["testSourceSha256"], done["testSourceSha256"])
        self.assertTrue(captured[0]["files"]["rom"]["present"])
        self.assertFalse(captured[0]["files"]["debugDescriptor"]["present"])

    def test_artifact_start_failure_does_not_leave_job_active(self):
        with patch("tools.overworld.devtools_jobs._write", side_effect=OSError("disk full")):
            reply = self.launch()
        self.assertFalse(reply["ok"])
        self.assertFalse(self.service.tests.active())
        self.assertEqual(self.service.tests.status()["state"], "failed")
        self.assertIsNone(self.service.worker)

    def test_past_run_can_be_read_after_service_restart_but_not_canceled(self):
        self.launch()
        done = self.finish()
        fresh = Service(self.root, FrameWorker)
        saved = fresh.tests.status(done["runId"])
        self.assertTrue(saved["passed"])
        self.assertTrue(saved["historical"])
        self.assertEqual(fresh.tests.status()["state"], "idle")
        with self.assertRaises(ValueError): fresh.tests.cancel(done["runId"])
        self.assertTrue(fresh.tests.export(done["runId"])["artifact"]["sha256"])

    def test_interrupted_manifest_cannot_claim_a_running_or_passing_job(self):
        run_id = "test-" + "a" * 32
        directory = self.root / "build/overworld-devtools" / run_id
        directory.mkdir(parents=True)
        (directory / "manifest.json").write_text(json.dumps({"runId": run_id, "execution": "shared-devtools", "state": "running", "passed": True}))
        result = self.service.tests.status(run_id)
        self.assertEqual(result["state"], "interrupted")
        self.assertFalse(result["passed"])
        with self.assertRaises(ValueError): self.service.tests.status("../test-file")

    def test_final_manifest_failure_does_not_leave_job_active_or_green(self):
        from tools.overworld.devtools_jobs import _write
        def write(path, value):
            if path.name == "manifest.json" and value.get("state") == "completed":
                raise OSError("disk full at finish")
            return _write(path, value)
        with patch("tools.overworld.devtools_jobs._write", side_effect=write):
            self.launch()
            done = self.finish()
        self.assertFalse(done["passed"])
        self.assertFalse(self.service.tests.active())
        self.assertIn("disk full", done["evidenceWriteError"])

    def test_unrelated_pokemon_cannot_reset_required_subject_watchdog(self):
        FrameWorker.unrelated_motion = True
        value = recipe()
        value["actions"] = [{"id": "wait-motion", "op": "wait", "args": {"predicate": {
            "kind": "actor-field", "subject": "subject", "path": "commitSequence", "operator": "gte", "value": 1}},
            "budget": {"maxSeconds": 10, "maxFrames": 20, "noProgressFrames": 8}}]
        self.launch(value)
        done = self.finish()
        self.assertFalse(done["passed"])
        self.assertEqual(done["totalGameFrames"], 8)
        self.assertIn("no-progress", str(done["evaluation"]))
        self.assertTrue(Path(done["failureArtifact"]["path"]).is_file())

    def test_measurement_wait_stops_at_240_despite_looking_and_other_actor_motion(self):
        from tools.overworld.devtools_test_contract import TestEvaluator
        fixed = {"subject": {key: deepcopy(snapshot()["actors"][0][key]) for key in
            ("handle", "subjectIdentity", "species", "role")}, "completeMotions": 55,
            "eligibleMoves": 54, "spawnPassed": True, "ready": False, "passed": False,
            "failures": [], "measurementErrors": []}
        class Metric:
            # Frozen measurement result isolates the real job watchdog, not the
            # Ledyba oracle. Saved native replay separately uses the real meter.
            def result(self): return deepcopy(fixed)
            def observe(self, *args, **kwargs): return self.result()
            def finish(self): return self.result()
        class Gate(TestEvaluator):
            def install_measurements(self, inputs):
                self.measurements_installed = True
                self.measurements = {"ledyba-chain-v1": Metric()}
            def bind(self, subject_id, current):
                # This test begins at a fixed measured-subject boundary; it
                # does not manufacture a native spawn/attachment proof.
                self.subjects[subject_id] = deepcopy(fixed["subject"])
                return deepcopy(self.subjects[subject_id])
        phase = ["IDLE"]
        class LookingWorker(FrameWorker):
            def call(self, op, args=None):
                result = super().call(op, args)
                for current in result.get("samples", [result.get("snapshot", result)]):
                    if "actors" not in current: continue
                    actor = current["actors"][0]
                    actor.update(commitSequence=55, motionElapsed=8, motionPhase=phase[0],
                        engineObject={"pos_x": 36339712, "pos_y": 65536, "pos_z": 24608768,
                            "facing": current["frame"] % 4, "flags": current["frame"]})
                    other = deepcopy(actor); other["species"] = 56; other["handle"]["slot"] = 1
                    other["handle"]["value"] += 1
                    other["engineObject"]["pos_x"] += current["frame"] * 4096
                    current["actors"].append(other)
                return result
        self.service.worker_factory = LookingWorker
        for motion_phase, previously_ready in (("IDLE", False), ("SETTLING", False),
                                                ("IDLE", True), ("SETTLING", True)):
            with self.subTest(motion_phase=motion_phase, previously_ready=previously_ready):
                phase[0] = motion_phase
                fixed["ready"] = previously_ready
                value = recipe(); value["id"] += "." + motion_phase.lower() + (".ready" if previously_ready else "")
                value["subjects"][0]["acquire"] = "spawn"
                value["measurements"] = [{"kind": "ledyba-chain-v1", "subject": "subject"}]
                value["budgets"].update(maxFrames=6000, minObservedFrames=5000, noProgressFrames=240)
                value["actions"] = [{"id": "wait-chain", "op": "wait", "args": {"predicate": {
                    "kind": "measurement-complete", "measurement": "ledyba-chain-v1"}},
                    "budget": {"maxSeconds": 10, "maxFrames": 300, "noProgressFrames": 240}}]
                with patch("tools.overworld.devtools_jobs.TestEvaluator", Gate), \
                        patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value={}):
                    self.assertTrue(self.launch(value)["ok"])
                    done = self.finish()
                self.assertFalse(done["passed"])
                self.assertEqual(done["totalGameFrames"], 240)
                self.assertEqual(done["evaluation"]["failures"][0]["code"], "no-progress")
                self.assertEqual(done["evaluation"]["failures"][0]["message"], "no-progress: wait-chain")
                self.assertIsNone(self.service.worker)
                steps = [args for op, args in FrameWorker.instances[-1].calls if op == "step"]
                self.assertEqual(len(steps), 30)
                self.assertTrue(all(args["frames"] == 8 for args in steps))

    def test_late_chunk_motion_cannot_hide_earlier_watchdog_failure(self):
        class LateWorker(FrameWorker):
            def call(self, op, args=None):
                result = super().call(op, args)
                for current in result.get("samples", [result.get("snapshot", result)]):
                    if "player" in current:
                        current["player"]["pos_x"] = 10 if current["frame"] >= 7 else 0
                return result
        self.service.worker_factory = LateWorker
        value = recipe()
        value["actions"][0]["args"] = {"frames": 8, "keys": ["RIGHT"]}
        value["actions"][0]["budget"].update(maxFrames=8, noProgressFrames=4)
        self.launch(value)
        done = self.finish()
        self.assertFalse(done["passed"], done)
        self.assertIn("no-progress", str(done["evaluation"]))
        self.assertEqual(done["totalGameFrames"], 4)

    def test_player_bookkeeping_churn_cannot_hide_control_stall(self):
        class ChurningWorker(FrameWorker):
            travels = False
            settles = False
            def call(self, op, args=None):
                result = super().call(op, args)
                for current in result.get("samples", [result.get("snapshot", result)]):
                    if "player" not in current:
                        continue
                    frame = current["frame"]
                    current["observationBoundary"] = "main-task-queue-completion"
                    current["context"].update(mapId=33, unrelatedCounter=frame)
                    current["fieldControl"] = {"taskPointer": 0}
                    current["nativeObservation"] = {"coverageComplete": True,
                        "playerStepFrame": frame, "playerStepCount": 0}
                    current["player"].update(x=1, y=2, x_prev=1, y_prev=2,
                        pos_x=0x18000, pos_z=0x28000, unk88_y=0,
                        flags=1 | (frame % 2) * 0x100, movement_cmd=frame % 4)
                    if self.travels:
                        current["player"]["pos_x"] += (frame // 3) * 4096
                    if self.settles:
                        current["player"].update(movement_cmd=255,
                                                flags=1 if frame >= 5 else 3)
                if "samples" in result:
                    result["snapshot"] = deepcopy(result["samples"][-1])
                return result
        self.service.worker_factory = ChurningWorker
        for kind in ("held-input", "player-step-count", "player-settled-at"):
            with self.subTest(kind=kind):
                value = recipe(); value["id"] += "." + kind
                args = {"frames": 8, "keys": ["RIGHT"]}
                if kind == "player-step-count":
                    args["until"] = {"kind": kind, "operator": "gte", "value": 1}
                elif kind == "player-settled-at":
                    args["until"] = {"kind": kind, "map": 33, "x": 2, "z": 2}
                value["actions"][0]["args"] = args
                value["actions"][0]["budget"].update(maxFrames=8, noProgressFrames=4)
                self.assertTrue(self.launch(value)["ok"])
                done = self.finish()
                self.assertFalse(done["passed"], done)
                self.assertEqual(done["evaluation"]["failures"][0]["code"], "no-progress")
                self.assertEqual(done["totalGameFrames"], 4)
                self.assertTrue(Path(done["failureArtifact"]["path"]).is_file())
                self.assertIsNone(self.service.worker)
        # Slow but real travel must still extend the same watchdog. Flags and
        # command churn remain present, so this differs only in actual motion.
        ChurningWorker.travels = True
        value = recipe(); value["id"] += ".moving-control"
        value["actions"][0]["args"] = {"frames": 8, "keys": ["RIGHT"]}
        value["actions"][0]["budget"].update(maxFrames=8, noProgressFrames=4)
        self.assertTrue(self.launch(value)["ok"])
        done = self.finish()
        self.assertTrue(done["passed"], done["evaluation"])
        self.assertEqual(done["totalGameFrames"], 8)
        # A finished action on the exact deadline is success, not a stall.
        # Position is already correct; only the genuine busy bit clears.
        ChurningWorker.travels = False
        ChurningWorker.settles = True
        value = recipe(); value["id"] += ".deadline-settle"
        value["actions"][0].update(op="wait", args={"predicate": {
            "kind": "player-settled-at", "map": 33, "x": 1, "z": 2}})
        value["actions"][0]["budget"].update(maxFrames=8, noProgressFrames=4)
        self.assertTrue(self.launch(value)["ok"])
        done = self.finish()
        self.assertTrue(done["passed"], done["evaluation"])
        self.assertEqual(done["totalGameFrames"], 4)

    def test_ready_measurement_batches_to_exact_floor_with_all_samples(self):
        from tools.overworld.devtools_test_contract import TestEvaluator
        class Metric:
            def result(self):
                return {"ready": True, "passed": True, "failures": [],
                    "subject": {key: deepcopy(snapshot()["actors"][0][key])
                        for key in ("handle", "subjectIdentity", "species", "role")}}
            def observe(self, *args, **kwargs): return self.result()
            def finish(self): return self.result()
        class Gate(TestEvaluator):
            def install_measurements(self, inputs):
                self.measurements_installed = True
                self.measurements = {"ledyba-chain-v1": Metric()}
            def bind(self, subject_id, current):
                # Boundary fixture only: native spawn proof is covered by the
                # real meter, not this ready-wait scheduling test.
                self.subjects[subject_id] = {key: deepcopy(current["actors"][0][key])
                    for key in ("handle", "subjectIdentity", "species", "role")}
                return deepcopy(self.subjects[subject_id])
        value = recipe()
        value["subjects"][0]["acquire"] = "spawn"
        value["measurements"] = [{"kind": "ledyba-chain-v1", "subject": "subject"}]
        value["budgets"].update(minObservedFrames=17, noProgressFrames=20)
        value["actions"] = [{"id": "wait-floor", "op": "wait", "args": {"predicate": {
            "kind": "measurement-complete", "measurement": "ledyba-chain-v1"}},
            "budget": {"maxSeconds": 10, "maxFrames": 20, "noProgressFrames": 20}}]
        with patch("tools.overworld.devtools_jobs.TestEvaluator", Gate), \
                patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value={}):
            self.launch(value)
            done = self.finish()
        self.assertTrue(done["passed"], done)
        self.assertEqual(done["observedFrames"], 17)
        steps = [args["frames"] for op, args in FrameWorker.instances[-1].calls if op == "step"]
        self.assertEqual(steps, [8, 8, 1])
        rows = load_observations(Path(done["observationsArtifact"]["path"]))
        self.assertEqual([s["frame"] for row in rows for s in row.get("samples", [])], list(range(2, 19)))

    def test_cancel_and_status_do_not_wait_for_worker_lock(self):
        FrameWorker.block, FrameWorker.entered = threading.Event(), threading.Event()
        self.launch()
        self.assertTrue(FrameWorker.entered.wait(2))
        current = self.service.command({"op": "test.status", "args": {}})
        self.assertTrue(current["ok"])
        run_id = current["result"]["runId"]
        cancel = self.service.command({"op": "test.cancel", "args": {"runId": run_id}})
        self.assertEqual(cancel["result"]["state"], "canceling")
        FrameWorker.block.set()
        done = self.finish()
        self.assertEqual(done["state"], "canceled")
        self.assertFalse(done["passed"])

    def test_key_hold_is_continuous_across_chunks_and_released(self):
        value = recipe()
        value["actions"][0]["args"] = {"frames": 16, "keys": ["RIGHT"]}
        value["actions"][0]["budget"].update(maxFrames=16, noProgressFrames=16)
        value["budgets"]["noProgressFrames"] = 20
        self.launch(value)
        done = self.finish()
        self.assertTrue(done["passed"], done)
        calls = FrameWorker.instances[-1].calls
        steps = [args for op, args in calls if op == "step"]
        self.assertEqual(len(steps), 2)
        self.assertTrue(all(args["releaseAtEnd"] is False for args in steps))
        self.assertGreaterEqual(sum(op == "release" for op, _ in calls), 2)

    def test_until_stops_on_exact_frame_not_end_of_eight_frame_chunk(self):
        FrameWorker.move_player = True
        value = recipe()
        value["actions"][0]["args"] = {"frames": 16, "keys": ["RIGHT"], "until": {
            "kind": "player-field", "path": "x", "operator": "eq", "value": 4}}
        value["actions"][0]["budget"].update(maxFrames=16, noProgressFrames=16)
        self.launch(value)
        done = self.finish()
        self.assertTrue(done["passed"], done)
        self.assertEqual(done["totalGameFrames"], 3)
        self.assertEqual(len([c for c in FrameWorker.instances[-1].calls if c[0] == "step"]), 3)

    def test_continuous_stream_keeps_5000_frames_beyond_diagnostic_ring(self):
        value = recipe()
        value["budgets"].update(maxFrames=5000, noProgressFrames=5000, minObservedFrames=5000)
        value["actions"] = [{"id": "part-" + str(i), "op": "step", "args": {"frames": 500, "keys": []},
            "budget": {"maxSeconds": 10, "maxFrames": 500, "noProgressFrames": 500}} for i in range(10)]
        self.launch(value)
        done = self.finish()
        self.assertTrue(done["passed"], done)
        self.assertEqual(done["observedFrames"], 5000)
        rows = load_observations(Path(done["observationsArtifact"]["path"]))
        self.assertEqual(sum(len(row.get("samples", [])) for row in rows), 5000)


class MeasurementProgressTests(unittest.TestCase):
    """Actual progress-key tests, not a claim that a stopped actor is fixed."""

    def test_batching_cannot_cross_the_bound_frame_floor_or_input_boundary(self):
        from tools.overworld.devtools_jobs import TestJobs
        from tools.overworld.devtools_test_contract import TestEvaluator
        value = recipe()
        value["budgets"].update(maxFrames=6000, minObservedFrames=5000)
        gate = TestEvaluator(value)
        gate.latest = snapshot()
        gate.measurements["ledyba-chain-v1"] = SimpleNamespace(result=lambda: {"ready": True})
        wait = {"op": "wait", "args": {"predicate": {
            "kind": "measurement-complete", "measurement": "ledyba-chain-v1"}}}
        for frames, expected in ((0, 8), (4991, 8), (4997, 3), (4999, 1), (5000, 1), (5001, 1)):
            gate.frames = frames
            self.assertEqual(TestJobs._chunk_frames(wait, gate, 100, "observe"), expected)
            if expected > 1:
                for intermediate in range(frames, frames + expected):
                    gate.frames = intermediate
                    self.assertFalse(gate.check(wait["args"]["predicate"]))
        gate.frames = 0
        self.assertEqual(TestJobs._chunk_frames(wait, gate, 2, "observe"), 2)
        self.assertEqual(TestJobs._chunk_frames(wait, gate, 100, "setup"), 1)
        wait["args"]["predicate"]["kind"] = "measurement-stage"
        self.assertEqual(TestJobs._chunk_frames(wait, gate, 100, "observe"), 1)
        step = {"op": "step", "args": {"until": {"kind": "player-settled-at"}}}
        self.assertEqual(TestJobs._chunk_frames(step, gate, 100, "observe"), 1)

    def setUp(self):
        self.snapshot = snapshot(1638)
        self.actor = self.snapshot["actors"][0]
        self.actor.update(commitSequence=55, motionPhase="IDLE", motionElapsed=8,
            engineObject={"pos_x": 36339712, "pos_y": 65536, "pos_z": 24608768,
                "facing": 1, "flags": 1098753, "face_x": 0, "face_y": -8192, "face_z": 0,
                "unk88_x": 0, "unk88_y": 0, "unk94_x": 0, "unk94_y": 0,
                "x": 554, "y": 375, "x_prev": 554, "y_prev": 375,
                "movement_cmd": 255, "movement_step": 0})
        self.measured = {"subject": {key: deepcopy(self.actor[key]) for key in
            ("handle", "subjectIdentity", "species", "role")},
            "completeMotions": 54, "eligibleMoves": 54, "spawnPassed": True}
        self.evaluator = SimpleNamespace(measurements={"ledyba-chain-v1":
            SimpleNamespace(result=lambda: deepcopy(self.measured))})

    def key(self, kind="measurement-complete"):
        from tools.overworld.devtools_jobs import TestJobs
        action = {"op": "wait", "args": {"predicate": {
            "kind": kind, "measurement": "ledyba-chain-v1"}}}
        return deepcopy(TestJobs._progress_key(action, self.snapshot, self.evaluator))

    def test_facing_flags_and_other_metadata_never_grant_motion_progress(self):
        for kind in ("measurement-complete", "measurement-stage"):
            for field in ("facing", "flags", "face_x", "face_y", "face_z", "unk88_x", "unk88_y",
                          "unk94_x", "unk94_y", "movement_cmd", "movement_step", "x_prev", "y_prev"):
                with self.subTest(kind=kind, field=field):
                    before = self.key(kind)
                    self.actor["engineObject"][field] += 1
                    self.assertEqual(self.key(kind), before)
            before = self.key(kind)
            self.snapshot["frame"] += 1
            self.measured["frames"] = self.snapshot["frame"]
            self.measured["identitySamples"] = self.snapshot["frame"]
            other = deepcopy(self.actor); other["handle"]["slot"] = 1
            other["engineObject"]["pos_x"] += 65536
            self.snapshot["actors"].append(other)
            self.assertEqual(self.key(kind), before)

    def test_actual_motion_commits_counts_and_selected_identity_are_progress(self):
        changes = (
            lambda: self.actor.update(commitSequence=56),
            lambda: self.actor.update(motionPhase="MOVING"),
            lambda: self.actor.update(motionElapsed=9),
            *(lambda field=field: self.actor["engineObject"].update({field: 1})
              for field in ("pos_x", "pos_y", "pos_z")),
            lambda: self.measured.update(completeMotions=55),
            lambda: self.measured.update(eligibleMoves=55),
            lambda: self.measured.update(spawnPassed=False),
            lambda: self.measured["subject"].update(subjectIdentity=124),
        )
        for change in changes:
            before = self.key()
            change()
            self.assertNotEqual(self.key(), before)

    def test_long_travel_progresses_but_stationary_pause_uses_declared_budget(self):
        self.actor["motionPhase"] = "MOVING"
        previous = self.key()
        for elapsed in range(1, 401):
            self.actor["motionElapsed"] = elapsed
            self.assertNotEqual(self.key(), previous)
            previous = self.key()
        self.actor["motionPhase"] = "SETTLING"
        settled = self.key()
        # The public elapsed value ends at duration during settling. Looking
        # around cannot extend a declared 240-frame no-progress allowance.
        for offset in range(1, 241):
            self.snapshot["frame"] += 1
            self.actor["engineObject"]["facing"] = offset % 4
            self.assertEqual(self.key(), settled)
        self.actor["motionPhase"] = "IDLE"
        self.assertNotEqual(self.key(), settled)


class LeanReplayTests(unittest.TestCase):
    def test_full_and_lean_rows_have_exact_controller_replay_parity(self):
        # Reuse the real chain stream fixture and actual controller, not a
        # second evaluator or a successful-result stub. This is host proof of
        # the storage format only, not a game run or claim acceptance.
        from tools.overworld import control
        from tools.overworld.test_devtools_test_proof import SharedLedybaProofTests
        fixture = SharedLedybaProofTests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        full = deepcopy(fixture.rows)
        for row in full:
            if "samples" in row:
                row["snapshot"] = deepcopy(row["snapshot"])
                row["snapshot"]["endpointOnlyDiagnostic"] = {"terrain": ["unused"] * 20}
                row["nativeCycles"] = len(row["samples"])
                row["cycleIntervals"] = [{"nativeCycle": sample["nativeCycle"], "cpuNs": 5, "wallNs": 10}
                                         for sample in row["samples"]]
        lean = [{key: value for key, value in row.items() if key != "snapshot" or "samples" not in row}
                for row in full]
        faults = (None, "absent-subject", "stale-subject", *(
            "missing-meaning:" + name for name in control._LEDYBA_REQUIRED_MEANINGS))
        with patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=fixture.inputs):
            for fault in faults:
                with self.subTest(fault=fault):
                    before = control._replay_shared_test(fixture.test, full, fault=fault, repo=fixture.root)
                    after = control._replay_shared_test(fixture.test, lean, fault=fault, repo=fixture.root)
                    self.assertEqual(after, before)
                    self.assertEqual(after["passed"], fault is None)
            for transform in (lambda row: row["samples"].pop(),
                              lambda row: row["events"].append({"frame": -1, "kind": "native"})):
                for rows in (full, lean):
                    damaged = deepcopy(rows)
                    transform(next(row for row in damaged if row.get("phase") == "observe" and "samples" in row))
                    with self.assertRaises(control.ValidationFailure):
                        control._replay_shared_test(fixture.test, damaged, repo=fixture.root)


if __name__ == "__main__": unittest.main()
