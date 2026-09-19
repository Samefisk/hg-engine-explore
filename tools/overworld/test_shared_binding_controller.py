"""Synthetic shared binding integration; no native game proof."""
import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.overworld import control
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.test_devtools_binding_measurement import fixture, EVENTS
from tools.overworld import test_devtools_test_proof as proof_fixture

ROOT = Path(__file__).resolve().parents[2]
KIND = "actor-binding-context-v1"


def recipe():
    return validate_test(json.loads((ROOT / "tests/overworld/test-recipes/actor.binding-current-context.json").read_text()))


def stream():
    samples = fixture()
    # Real collector can publish two returns at one completed queue boundary.
    second = deepcopy(samples[1][1][0])
    second["data"]["sequence"] = 2
    samples[1][1].append(second)
    for snapshot, _ in samples[1:]:
        snapshot["nativeObservation"]["sequence"] = 2
    for snapshot, _ in samples:
        snapshot["actors"][0]["engineIdentity"]["manager_index"] = 0
    rows = [{"phase": "setup", "initialSnapshot": samples[0][0]},
        {"phase": "setup", "action": "natural-rattata", "samples": [samples[1][0]],
         "events": samples[1][1], "completedGameFrames": 1},
        {"phase": "setup", "action": "bind-rattata", "command": "bind", "snapshot": samples[1][0],
         "receipt": select_current_actor(samples[1][0], samples[1][0]["actors"][0])},
        {"phase": "observe", "action": "context-and-walk", "samples": [s for s, _ in samples[2:]],
         "events": [e for _, events in samples[2:] for e in events], "completedGameFrames": 3}]
    return samples, rows


class BindingControllerTests(unittest.TestCase):
    def test_two_queue_record_start_retains_initial_semantic_sequence(self):
        """A start-cycle prefix is coverage, never a credited Walk/frame."""
        samples, rows = stream()
        prefix = deepcopy(samples[2][1][0])
        prefix["frame"] = samples[0][0]["frame"]
        prefix["data"].update(event="WORLD_EFFECT", actorFrame=samples[0][0]["actorFrame"],
                              valueA=0, valueB=0, sequence=1)
        tree = ast.parse((ROOT / "tools/overworld/devtools_runtime.py").read_text())
        method = next(node for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == "DevtoolsSession"
                      for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_record_control")
        def require(ok, message, *args):
            if not ok: raise ValueError(message)
        scope = {"require": require}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "_record_control", "exec"), scope)
        session = SimpleNamespace(emu=object(), trace_request=None, sample_error=None,
            semantic_trace=SimpleNamespace(running=False), completed_frames=98, prepared=False,
            _ensure_trace=lambda: None, snapshot=lambda: deepcopy(samples[0][0]),
            drain_events=lambda: [deepcopy(prefix)])
        def cycle(count):
            self.assertEqual(count, 1)
            # First completion starts the ring; the second publishes sequence 1.
            session.completed_frames += 2
            session.semantic_trace.running = True
            session.trace_request["complete"] = True
        session.cycle = cycle
        receipt = scope["_record_control"](session, "start", 900)
        self.assertEqual(receipt["frame"], 100)
        self.assertEqual(receipt["events"], [prefix])
        for row in rows:
            for event in row.get("events", []):
                if event["kind"] == "native": event["data"]["sequence"] += 1
        # Proposed explicit retained start-boundary field. Current replay drops
        # it just as current jobs drops record.start's returned events.
        rows[0]["initialEvents"] = receipt["events"]
        result = control._replay_shared_test(recipe(), rows)
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["observedFrames"], 3)
        self.assertEqual(len(result["measurements"][KIND]["lifecycleEvents"]), 4)

    def test_initial_prefix_controls_fail_without_frame_or_meaning_credit(self):
        samples, _ = stream()
        snapshot = samples[0][0]
        prefix = deepcopy(samples[2][1][0])
        prefix["frame"] = snapshot["frame"]
        prefix["data"].update(event="WORLD_EFFECT", actorFrame=snapshot["actorFrame"], sequence=1)
        for fault in ("future", "before-start", "missing-first", "duplicate", "coverage", "early-binding"):
            evaluator = TestEvaluator(recipe())
            evaluator.install_measurements({KIND: {"contractVersion": 1}})
            events = [deepcopy(prefix)]
            if fault == "future": events[0]["frame"] += 1
            elif fault == "before-start": events[0]["frame"] -= 2
            elif fault == "missing-first": events[0]["data"]["sequence"] = 2
            elif fault == "duplicate": events.append(deepcopy(events[0]))
            elif fault == "coverage": events.append(dict(frame=100, kind="trace-status", data=dict(coverageComplete=False)))
            else:
                event = deepcopy(samples[1][1][0]); event["frame"] = 100
                events.append(event)
            with self.subTest(fault=fault):
                result = evaluator.observe_initial(snapshot, events, start_frame=99)
                self.assertEqual(result["state"], "failed", result)
                self.assertEqual(result["observedFrames"], 0)
                self.assertIsNone(result["measurements"][KIND]["bindingReceipt"])

    def test_missing_start_prefix_still_rejects_the_next_real_sequence(self):
        _, rows = stream()
        for row in rows:
            for event in row.get("events", []):
                if event["kind"] == "native": event["data"]["sequence"] += 1
        result = control._replay_shared_test(recipe(), rows)
        self.assertFalse(result["passed"])
        self.assertIn("native event sequence", str(result["failures"]))

    def test_boot_native_prefix_precedes_trace_start_without_proof_credit(self):
        snapshot = deepcopy(stream()[0][0][0])
        snapshot.update(frame=714, actorFrame=714, nativeCycle=1800)
        snapshot["nativeObservation"]["sequence"] = 335
        events = [dict(frame=413 + min(sequence - 1, 293), kind="native-observation",
            data=dict(observation="party-getter", sequence=sequence, setupMode="normal"))
            for sequence in range(1, 336)]
        events.append(dict(frame=714, kind="trace-status", data=dict(code="window-started")))
        evaluator = TestEvaluator(recipe())
        evaluator.install_measurements({KIND: {"contractVersion": 1}})
        result = evaluator.observe_initial(snapshot, events, start_frame=713)
        self.assertNotEqual(result["state"], "failed", result["failures"])
        self.assertEqual(result["observedFrames"], 0)
        self.assertFalse(result["measurements"][KIND]["bindingObserved"])
        self.assertEqual(evaluator.events, {})

    def test_record_start_enables_only_after_successful_start_and_default_is_disabled(self):
        tree = ast.parse((ROOT / "tools/overworld/devtools_runtime.py").read_text())
        method = next(node for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == "DevtoolsSession"
                      for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "record_start")
        def require(ok, message):
            if not ok: raise ValueError(message)
        scope = dict(integer=lambda *args: None, require=require)
        exec(compile(ast.Module(body=[method], type_ignores=[]), "record_start", "exec"), scope)
        calls = []
        result = {"events": ["initial trace"]}
        session = SimpleNamespace(native_observation=SimpleNamespace(binding_context=SimpleNamespace(
            enable=lambda: calls.append("enable"))),
            _record_control=lambda *args: (calls.append("record"), result)[1])
        self.assertIs(scope["record_start"](session), result)
        self.assertEqual(calls, ["record"])
        calls.clear()
        self.assertIs(scope["record_start"](session, binding_context=True), result)
        self.assertEqual(calls, ["record", "enable"])
        calls.clear()
        def fail(*args):
            calls.append("record")
            raise RuntimeError("record failed")
        session._record_control = fail
        with self.assertRaisesRegex(RuntimeError, "record failed"):
            scope["record_start"](session, binding_context=True)
        self.assertEqual(calls, ["record"])

    def test_multiple_candidates_bind_the_native_meter_subject_not_first_actor(self):
        samples, _ = stream()
        evaluator = TestEvaluator(recipe())
        evaluator.install_measurements({KIND: {"contractVersion": 1}})
        for snapshot, events in samples[:2]:
            evaluator.observe(snapshot, events, count_frame=False)
        snapshot = deepcopy(samples[1][0])
        other = deepcopy(snapshot["actors"][0])
        other["handle"].update(slot=1, value=65537)
        other["subjectIdentity"] = 54321
        snapshot["actors"].insert(0, other)
        selected = evaluator.bind("rattata", snapshot)
        self.assertEqual(selected["handle"], samples[1][0]["actors"][0]["handle"])

    def test_real_replay_controls_remove_both_returns_and_each_walk_meaning(self):
        _, rows = stream(); original = deepcopy(rows)
        result = control._replay_shared_test(recipe(), rows)
        self.assertTrue(result["passed"], result)
        for fault in ["binding-wrong-return", "binding-missing-return", *["binding-missing:" + name for name in EVENTS]]:
            with self.subTest(fault=fault):
                rejected = control._replay_shared_test(recipe(), rows, fault=fault)
                self.assertFalse(rejected["passed"], rejected)
                self.assertTrue(rejected["failures"])
        self.assertEqual(rows, original)

    def test_registered_acceptance_rechecks_exact_exported_measurement_values(self):
        f = proof_fixture.SharedProofTests(); f.setUp(); self.addCleanup(f.doCleanups)
        test = recipe(); _, rows = stream()
        source = f.root / "tests/overworld/test-recipes/actor.binding-current-context.json"
        source.write_text(json.dumps(test))
        registry = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json").read_text())
        registration = registry["sharedTests"][test["id"]]
        registration["recipeSha256"] = proof_fixture.sha(source)
        (f.root / "tools/overworld/runtime_proof_registry.json").write_text(json.dumps(registry))
        f.rows = rows; f.write_rows()
        record = deepcopy(f.record)
        record.update(testSourceSha256=proof_fixture.sha(source), observationsArtifact=f.artifact(),
            evaluation=control._replay_shared_test(test, rows),
            sessionCleanup={"sessionId": "session-proof", "closed": True, "errors": []})
        record["fixtureProof"].update(registration=registration, testSourceSha256=proof_fixture.sha(source))
        with patch.object(control, "source_record", return_value={"hash": "source"}):
            accepted = control.finalize_shared_test(test, record, f.root)
            self.assertTrue(accepted["acceptedProof"], accepted)
            for value in (True, 2, -1):
                bad = deepcopy(record["evaluation"])
                bad["measurements"][KIND]["measurements"]["binding-live-subject-count"] = value
                changed = deepcopy(record); changed["evaluation"] = bad
                # Isolate the independent export gate, after matching replay.
                with patch.object(control, "_replay_shared_test", return_value=bad):
                    rejected = control.finalize_shared_test(test, changed, f.root)
                self.assertFalse(rejected["acceptedProof"], rejected)
                self.assertIn("original exact rules", str(rejected))


if __name__ == "__main__":
    unittest.main()
