"""Shared raw-record integration controls; no emulator or gameplay proof."""
from copy import deepcopy
from pathlib import Path
import json
from tools.overworld.devtools_evidence_stream import load_observations
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.test_devtools_cadence_measurement import Route, CadenceSetupAbsenceTests


ROOT = Path(__file__).resolve().parents[2]
KIND = "unmounted-cadence-v1"


def typed(route, transitions=()):
    value = deepcopy(route.test)
    value.update(schemaVersion=1, id="test.cadence-integration", title="Raw cadence integration",
                 expectationSource="Synthetic shared-boundary controls, not gameplay proof", requirements=[],
                 budgets={"maxFrames": 32000, "maxSeconds": 3600, "noProgressFrames": 600, "minObservedFrames": 1},
                 assertions=[{"kind": "measurement-complete", "measurement": KIND}],
                 measurements=[{"kind": KIND, "subject": "cyndaquil", "setupTransitions": list(transitions)}])
    value["fixture"]["rom"] = "test.nds"
    value["subjects"][0]["acquire"] = "existing"
    return value


def installed(route, transitions=()):
    for index, record in enumerate(route.records):
        for snapshot in [record.get("initialSnapshot"), record.get("snapshot"), *record.get("samples", [])]:
            if snapshot:
                for actor in snapshot.get("actors", []): actor["engineIdentity"]["manager_index"] = 0
        if record.get("command") == "bind":
            record["snapshot"] = deepcopy(route.records[index - 1]["samples"][-1])
            record["receipt"] = select_current_actor(record["snapshot"], record["receipt"])
    test = validate_test(typed(route, transitions))
    meter = TestEvaluator(test)
    meter.install_measurements(measurement_inputs(test, ROOT))
    return meter


class CadenceIntegrationTests(unittest.TestCase):
    def test_prepared_same_frame_receipt_refresh_is_validated_not_frame_credit(self):
        from tools.overworld.test_devtools_cadence_measurement import PreparedCadenceSetupTests
        for fault in (None,"context","pid","duplicate","native-cycle","generic"):
            with self.subTest(fault=fault):
                source,commands=PreparedCadenceSetupTests().fixture()
                test=typed(Route())
                test["mode"]="prepared"
                test["setup"]=[deepcopy(a) for (phase,_),a in source.actions.items() if phase=="setup"]
                for action in test["setup"]:
                    if action["op"]=="spawn":action["args"]["role"]="follower"
                test=validate_test(test)
                evaluator=TestEvaluator(test)
                evaluator.install_measurements(measurement_inputs(test,ROOT))
                evaluator.observe_record({"phase":"setup","initialSnapshot":source.latest})
                evaluator.observe_record(commands[0])
                record=deepcopy(commands[1])
                snapshot=record["snapshot"]
                snapshot.update(frame=1,nativeCycle=2)
                snapshot["partyObservation"]["frame"]=1
                snapshot["partyObservation"]["nativeGetterChecks"][0].update(frame=1,decodedAtFrame=1)
                snapshot["nativeObservation"]["playerStepFrame"]=1
                if fault=="context":snapshot["context"]["mapId"]+=1
                elif fault=="pid":snapshot["party"][1]["personality"]+=1
                elif fault=="native-cycle":snapshot["nativeCycle"]+=1
                record["receipt"]["snapshot"]=deepcopy(snapshot)
                record["receipt"]["setupBoundary"].update(frame=1,nativeCycle=snapshot["nativeCycle"])
                if fault=="generic":evaluator.observe(snapshot,count_frame=False)
                else:evaluator.observe_record(record)
                if fault=="duplicate":evaluator.observe_record(record)
                if fault is None:
                    self.assertEqual(evaluator.failures,[])
                    self.assertEqual(evaluator.latest["frame"],1)
                    self.assertEqual(evaluator.sampled_frames,0)
                    self.assertEqual(evaluator.measurements[KIND].result()["preparedSetup"][-1]["excludedFrames"],0)
                else:self.assertTrue(evaluator.failures)

    def test_raw_job_watchdog_keeps_last_real_progress_frame_inside_chunk(self):
        """A move at16 cannot rescue the four-frame idle deadline at15.

        The first8-frame native follower motion returns at11. The chunk ending
        at14 therefore last progressed at11, not14. Exercise the real job
        callback; the copied old endpoint-only path is a negative control.
        """
        from tools.overworld.devtools import Service
        route = Route(); route.setup_bind(); route.move(1)
        route.records = route.records[:13]  # Exact first follower return at11.
        route.frame = 11
        route.actor = deepcopy(route.records[-1]["samples"][0]["actors"][0])
        # Rebuild observation clocks for later fixture frames, not actor state.
        route.actor.pop("crashPresentation")
        for _ in range(4): route.append("idle")
        route.move(9)  # A second valid follower motion starts at16.
        for record in route.records:
            if "samples" not in record: continue
            record["events"] = [event for event in record["events"] if event["kind"] != "native-observation"]
            for sample in record["samples"]:
                sample["player"] = deepcopy(route.records[0]["initialSnapshot"]["player"])
                sample["nativeObservation"].update(sequence=0, playerStepCount=0)
        test = installed(route).test
        test["setup"] = [action for action in test["setup"] if action["id"] in ("open", "choose")]
        for action in test["setup"]: action["args"]["frames"] = 1
        test["budgets"]["minObservedFrames"] = 5000
        test["actions"] = [test["actions"][0], {"id": "idle", "op": "wait",
            "args": {"predicate": {"kind": "measurement-complete", "measurement": KIND}},
            "budget": {"maxSeconds": 30, "maxFrames": 32, "noProgressFrames": 4}}]
        chunks = [record for record in route.records if "samples" in record]
        original = TestEvaluator.observe_record

        def endpoint_only(current, record, *, frame_callback=None, full_report=True):
            result = original(current, record, full_report=full_report)
            if frame_callback and record.get("samples") and not result["failures"]:
                frame_callback(record["samples"][-1], current)
            return result

        def run(old_endpoint_only):
            class Worker:
                sizes = []
                def __init__(self, *_):
                    self.index = 0
                    self.snapshot = deepcopy(route.records[0]["initialSnapshot"])
                def call(self, op, args=None):
                    if op == "capture": raise AssertionError("image capture is forbidden")
                    if op != "step": return deepcopy(self.snapshot)
                    self.sizes.append(args["frames"])
                    selected = chunks[self.index:self.index + args["frames"]]
                    self.index += len(selected)
                    self.snapshot = deepcopy(selected[-1]["samples"][0])
                    return {"snapshot": self.snapshot, "samples": [deepcopy(r["samples"][0]) for r in selected],
                        "events": [deepcopy(e) for r in selected for e in r["events"]],
                        "cycleIntervals": [deepcopy(i) for r in selected for i in r["cycleIntervals"]],
                        "completedGameFrames": len(selected), "observedFieldFrames": len(selected),
                        "nativeCycles": len(selected) * 2}
                def close(self): pass
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "test.nds").write_bytes(b"rom")
                (root / "test.sav").write_bytes(b"save")
                service = Service(root, Worker)
                with patch("tools.overworld.devtools_jobs.source_record", return_value={"content": "host-source"}), \
                        patch("tools.overworld.control.prepare_shared_test", return_value={"passed": True}), \
                        patch("tools.overworld.control.finalize_shared_test", return_value={"acceptedProof": False}), \
                        patch.object(TestEvaluator, "observe_record", endpoint_only if old_endpoint_only else original):
                    service.tests.save(test["id"], test)
                    started = service.command({"op": "test.start", "args": {"name": test["id"]}})
                    self.assertTrue(started["ok"], started)
                    service.tests.thread.join(10)
                    self.assertFalse(service.tests.thread.is_alive())
                    done = service.tests.status()
                rows = load_observations(Path(done["observationsArtifact"]["path"]))
                self.assertIsNone(service.worker)
                return done, [sample["frame"] for row in rows for sample in row.get("samples", [])], Worker.sizes

        done, frames, sizes = run(False)
        self.assertEqual(done["evaluation"]["failures"][-1]["code"], "no-progress")
        self.assertEqual(done["evaluation"]["failures"][-1]["frame"], 15)
        self.assertEqual(frames[-1], 15)
        self.assertEqual(sizes[-1], 1)
        self.assertEqual(done["evaluation"]["measurements"][KIND]["followerMotions"], 1)
        _, stale_frames, _ = run(True)
        self.assertIn(16, stale_frames)  # The old endpoint-only path misses15.

    def test_actual_shared_job_and_controller_replay_have_same_cadence_measurement(self):
        from tools.overworld.devtools import Service
        from tools.overworld.control import _replay_shared_test
        route = Route(); route.setup_bind(); route.move(1)
        evaluator = installed(route)
        test = evaluator.test
        test["setup"] = [a for a in test["setup"] if a["id"] in ("open", "choose")]
        for action in test["setup"]: action["args"]["frames"] = 1
        test["actions"] = test["actions"][:2]
        test["actions"][1]["args"]["frames"] = 32
        chunks = [r for r in route.records if "samples" in r]
        class Worker:
            calls = []
            def __init__(self, *_): self.index = 0; self.snapshot = deepcopy(route.records[0]["initialSnapshot"])
            def call(self, op, args=None):
                self.calls.append(op)
                if op == "capture": raise AssertionError("image capture is forbidden")
                if op == "step":
                    selected = chunks[self.index:self.index + args["frames"]]
                    self.index += len(selected)
                    self.snapshot = deepcopy(selected[-1]["samples"][0])
                    return {"snapshot": self.snapshot, "samples": [deepcopy(r["samples"][0]) for r in selected],
                            "events": [deepcopy(e) for r in selected for e in r["events"]],
                            "cycleIntervals": [deepcopy(i) for r in selected for i in r["cycleIntervals"]],
                            "completedGameFrames": len(selected), "observedFieldFrames": len(selected),
                            "nativeCycles": len(selected) * 2}
                return deepcopy(self.snapshot)
            def close(self): pass
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test.nds").write_bytes(b"rom"); (root / "test.sav").write_bytes(b"save")
            service = Service(root, Worker)
            with patch("tools.overworld.devtools_jobs.source_record", return_value={"content": "host-source"}), \
                    patch("tools.overworld.control.prepare_shared_test", return_value={"passed": True}), \
                    patch("tools.overworld.control.finalize_shared_test", return_value={"acceptedProof": False}):
                service.tests.save(test["id"], test)
                result = service.command({"op": "test.start", "args": {"name": test["id"]}})
                self.assertTrue(result["ok"], result)
                service.tests.thread.join(10)
                self.assertFalse(service.tests.thread.is_alive())
                done = service.tests.status()
            rows = load_observations(Path(done["observationsArtifact"]["path"]))
            replayed = _replay_shared_test(test, rows, repo=root)
            self.assertEqual(done["evaluation"]["measurements"], replayed["measurements"])
            meter = replayed["measurements"][KIND]
            self.assertEqual(meter["playerMotions"], 1)
            self.assertEqual(meter["sampledFrames"], 34)
            self.assertEqual(meter["nativeCycles"], 68)
            self.assertFalse(meter["passed"])  # Short synthetic case cannot close the long route.
            self.assertNotIn("capture", Worker.calls)
            self.assertIsNone(service.worker)

    def test_service_and_memory_ring_do_not_keep_old_field_data(self):
        from tools.overworld.devtools import Service
        from tools.overworld.devtools_records import Recording
        route, _ = CadenceSetupAbsenceTests().route()
        with tempfile.TemporaryDirectory() as directory:
            service = Service(Path(directory))
            service._observe(route.records[0]["initialSnapshot"])
            service.snapshot["sessionMetadata"] = {"mode": "normal"}
            service.recording = Recording(); service.recording_active = True
            service._observe({**route.records[1], "snapshot": route.records[1]["samples"][0]})
            self.assertNotIn("player", service.snapshot)
            self.assertNotIn("actors", service.snapshot)
            self.assertEqual(service.snapshot["sessionMetadata"], {"mode": "normal"})
            exported = service.recording.export({}, "normal")
            self.assertEqual(exported["subjects"], [])
            self.assertNotIn("actors", exported["snapshots"][0])
            self.assertFalse(exported["acceptedProof"])

    def test_absence_ring_rejects_stale_or_invented_absence_and_invalidates_identity(self):
        from tools.overworld.devtools_records import Recording
        route, _ = CadenceSetupAbsenceTests().route()
        absent = route.records[1]["samples"][0]
        for fault in ("stale-actor", "stale-party", "wrong-reason", "bad-pointer", "missing-hash", "missing-clock"):
            value = deepcopy(absent)
            if fault == "stale-actor": value["actors"] = []
            elif fault == "stale-party": value["partyObservation"] = {}
            elif fault == "wrong-reason": value["fieldAvailability"]["reasons"] = ["maybe-transition"]
            elif fault == "bad-pointer": value["fieldAvailability"]["fieldPointer"] = 7
            elif fault == "missing-hash": value.pop("romSha256")
            elif fault == "missing-clock": value.pop("nativeCycle")
            with self.subTest(fault=fault), self.assertRaises(ValueError): Recording().add_snapshot(1, value)
        recording = Recording()
        recording.add_snapshot(0, route.records[0]["initialSnapshot"])
        self.assertTrue(recording._previous)
        recording.add_snapshot(1, absent)
        self.assertEqual(recording._previous, {})
        output = recording.export({}, "normal")
        self.assertEqual(output["subjects"], [])
        self.assertTrue(output["subjectSelectionErrors"])
        self.assertEqual(output["snapshots"][1], absent)

    def test_actual_native_absence_shape_is_retained_by_the_same_ring(self):
        from tools.overworld.test_devtools_runtime import CompletedFieldAvailabilityTests
        from tools.overworld.devtools_records import Recording
        fixture = CompletedFieldAvailabilityTests()
        try:
            session, memory, boundary, *_ = fixture.fixture()
            memory[0x02001000] = 0
            boundary()
            native = session.pending_samples[0]
            recording = Recording(); recording.add_snapshot(native["frame"], native)
            self.assertEqual(recording.export({}, "normal")["snapshots"], [native])
        finally:
            fixture.doCleanups()

    def test_typed_transition_contract_cannot_leak_to_other_measurements(self):
        route = Route()
        value = typed(route)
        value["measurements"][0]["kind"] = "ledyba-chain-v1"
        with self.assertRaises(ValueError): validate_test(value)
        value = typed(route); value["mode"] = "prepared"
        self.assertEqual(validate_test(value)["mode"], "prepared")
        for fault in ("missing-transitions", "wrong-role", "observer-control", "unknown-action"):
            value = typed(route)
            if fault == "missing-transitions": value["measurements"][0].pop("setupTransitions")
            elif fault == "wrong-role": value["subjects"][0]["role"] = "MOUNTED"
            elif fault == "observer-control": value["mode"] = "observer-control"
            elif fault == "unknown-action": value["measurements"][0]["setupTransitions"] = [
                {"action": "unknown", "departure": {"map": 33, "x": 0, "z": 0},
                 "arrival": {"map": 69, "x": 8, "z": 13}, "maxFrames": 8}]
            with self.subTest(fault=fault), self.assertRaises(ValueError): validate_test(value)

    def test_typed_cadence_installs_and_consumes_real_raw_record_shape(self):
        route = Route(); route.setup_bind(); route.move(1)
        evaluator = installed(route)
        for record in route.records:
            result = evaluator.observe_record(record)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["measurements"][KIND]["playerMotions"], 1)
        self.assertEqual(result["measurements"][KIND]["nativeCycles"], 68)
        self.assertEqual(result["observedFrames"], 32)

    def test_same_shared_replay_keeps_exact_result_and_immutable_rows(self):
        from tools.overworld.control import _replay_shared_test
        route = Route(); route.setup_bind(); route.move(1)
        evaluator = installed(route)
        before = deepcopy(route.records)
        for record in route.records: evaluator.observe_record(record)
        self.assertEqual(_replay_shared_test(evaluator.test, route.records), evaluator.finish())
        self.assertEqual(route.records, before)

    def test_missing_raw_native_data_and_unrelated_direct_observation_fail(self):
        for fault in ("missing-interval", "wrong-clock", "stale-subject", "absent-subject", "missing-event", "duplicate-row"):
            with self.subTest(fault=fault):
                route = Route(); route.setup_bind(); route.move(1)
                evaluator = installed(route)
                record = route.records[4]
                if fault == "missing-interval": record["cycleIntervals"].pop()
                elif fault == "wrong-clock": record["samples"][0]["nativeCycle"] += 1
                elif fault == "stale-subject": record["samples"][0]["context"]["fieldEpoch"] += 1
                elif fault == "absent-subject": record["samples"][0]["actors"] = []
                elif fault == "missing-event": record["events"] = []
                elif fault == "duplicate-row": route.records.insert(5, deepcopy(record))
                for record in route.records: result = evaluator.observe_record(record)
                self.assertTrue(result["failures"])
                self.assertLessEqual(result["observedFrames"], 1)
        route = Route(); evaluator = installed(route)
        self.assertTrue(evaluator.observe(route.records[0]["initialSnapshot"], count_frame=False)["failures"])

    def test_malformed_raw_shapes_fail_without_escaping_or_credit(self):
        for fault in ("null-sample", "missing-availability", "numeric-availability", "null-interval", "boolean-count", "bad-native"):
            route = Route(); route.setup_bind(); route.move(1)
            evaluator = installed(route)
            record = route.records[4]
            if fault == "null-sample": record["samples"] = [None]
            elif fault == "missing-availability": record["samples"][0].pop("fieldAvailable")
            elif fault == "numeric-availability": record["samples"][0]["fieldAvailable"] = 1
            elif fault == "null-interval": record["cycleIntervals"][0] = None
            elif fault == "boolean-count": record["completedGameFrames"] = True
            elif fault == "bad-native": record["samples"][0]["nativeObservation"] = []
            for row in route.records: result = evaluator.observe_record(row)
            self.assertTrue(result["failures"], fault)
            self.assertEqual(result["observedFrames"], 0)

    def test_multi_frame_chunk_never_credits_future_motion_or_predicate(self):
        route = Route(); route.setup_bind(); route.move(1)
        evaluator = installed(route)
        for record in route.records[:4]: evaluator.observe_record(record)
        records = route.records[4:]
        chunk = {"phase": "observe", "action": "route-0", "samples": [r["samples"][0] for r in records],
                 "events": [e for r in records for e in r["events"]],
                 "cycleIntervals": [i for r in records for i in r["cycleIntervals"]],
                 "completedGameFrames": 32, "observedFieldFrames": 32, "nativeCycles": 64}
        seen = []
        def inspect_frame(sample, current):
            seen.append((sample["frame"], current.measurements[KIND].result()["playerMotions"]))
            self.assertEqual(current.latest["frame"], sample["frame"])
            with self.assertRaises(ValueError):
                current.check({"kind": "measurement-complete", "measurement": KIND}, {"frame": sample["frame"] + 1})
        result = evaluator.observe_record(chunk, frame_callback=inspect_frame)
        self.assertEqual(result["failures"], [])
        self.assertEqual([count for _, count in seen[:-1]], [0] * 31)
        self.assertEqual(seen[-1][1], 1)

    def test_exact_setup_absence_path_and_loading_budget(self):
        for fail in (False, True):
            route, spec = CadenceSetupAbsenceTests().route()
            if fail: spec["maxFrames"] = 1
            evaluator = installed(route, [spec])
            for record in route.records: result = evaluator.observe_record(record)
            self.assertEqual(bool(result["failures"]), fail)
            self.assertEqual(result["observedFrames"], 0)
            if not fail:
                self.assertEqual(result["measurements"][KIND]["absentSetupFrames"], 1)
                self.assertEqual(len(result["measurements"][KIND]["setupTransitions"]), 1)

    def test_rebind_requires_same_native_terminal_generation_contract(self):
        route = Route(); route.setup_bind()
        for tile in range(1, 65): route.move(tile)
        for wrong in (False, True):
            current = deepcopy(route)
            evaluator = installed(current)
            if wrong:
                for event in current.records[-1]["events"]:
                    if event["data"].get("event") == "ACTOR_REBOUND": event["data"]["valueA"] = 999
            for record in current.records: result = evaluator.observe_record(record)
            self.assertEqual(bool(result["failures"]), wrong)
            self.assertEqual(result["subjects"]["cyndaquil"]["handle"]["fieldEpoch"], 2 if wrong else 3)

    def test_action_budget_and_duplicate_binding_fail(self):
        for fault in ("budget", "duplicate-bind"):
            route = Route(); route.setup_bind(); route.move(1)
            if fault == "budget": route.test["actions"][1]["args"]["frames"] = 1
            evaluator = installed(route)
            if fault == "duplicate-bind": route.records.insert(4, deepcopy(route.records[3]))
            for record in route.records: result = evaluator.observe_record(record)
            self.assertTrue(result["failures"])


if __name__ == "__main__":
    unittest.main()
