"""Shared typed acceleration windows; synthetic host data, no guest driver."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.test_devtools_test_contract import recipe as base_recipe
from tools.overworld.test_devtools_acceleration_measurement import fixture, SCHEMA, SOURCE
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_jobs import _command_snapshot

KIND = "acceleration-parity-v1"


def recipe():
    value = base_recipe()
    value.update(id="test.acceleration", mode="prepared", measurements=[{
        "kind": KIND, "subjects": {"WILD": "walker", "MOUNTED": "rider"}}],
        subjects=[dict(id="walker", species=165, role="WILD", acquire="existing"),
                  dict(id="rider", species=155, role="MOUNTED", acquire="existing")],
        budgets=dict(maxSeconds=120, maxFrames=2000, noProgressFrames=600, minObservedFrames=1),
        assertions=[dict(kind="measurement-complete", measurement=KIND)])
    budget = dict(maxSeconds=30, maxFrames=600, noProgressFrames=600)
    value["setup"] = []
    for subject in ("walker", "rider"):
        for suffix, op, args in (
                ("bind", "bind", {"subject": subject}),
                ("begin", "acceleration.begin", {"subject": subject}),
                ("walk", "wait", {"predicate": {"kind": "acceleration-role-complete", "subject": subject}}),
                ("end", "acceleration.end", {"subject": subject})):
            value["setup"].append(dict(id=subject + "-" + suffix, op=op, args=args, budget=deepcopy(budget)))
    value["actions"] = [dict(id="complete", op="assert", args={"predicate": value["assertions"][0]}, budget=deepcopy(budget))]
    return value


def integration_fixture(*, intent=False, direction=3, delta=(1, 0)):
    """Two existing motion fixtures in one monotonic stream, with excluded setup."""
    test = recipe()
    budget = deepcopy(test["setup"][0]["budget"])
    test["setup"].insert(4, dict(id="prepare-rider", op="spawn",
        args=dict(species=155, role="mounted", slot=1), budget=budget))
    rows = []
    frame_shift = native_shift = trace_shift = 0
    for role, subject in (("WILD", "walker"), ("MOUNTED", "rider")):
        baseline, reset, samples = fixture(role, species=165 if role == "WILD" else 155,
            direction=direction if role == "WILD" else 3, delta=delta if role == "WILD" else (1, 0),
            direction_mode=2 if role == "WILD" and direction >= 4 else 0,
            fingerprint=12346 if role == "WILD" and direction >= 4 else 12345)
        snapshots = [baseline, reset["before"]["snapshot"], reset["after"]["snapshot"], *[s for s, _ in samples]]
        for snapshot in snapshots:
            snapshot["fieldAvailable"] = True
            snapshot["frame"] += frame_shift
            snapshot["actorFrame"] += frame_shift
            snapshot["nativeCycle"] += frame_shift * 2
            snapshot["nativeObservation"]["sequence"] += native_shift
        for _, events in samples:
            for event in events:
                event["frame"] += frame_shift
                data = event["data"]
                if event["kind"] == "native-observation":
                    data["sequence"] += native_shift
                    for key in ("entryActorFrame", "returnActorFrame"): data[key] += frame_shift
                    for key in ("entryNativeCycle", "returnNativeCycle"): data[key] += frame_shift * 2
                else:
                    data["sequence"] += trace_shift
        traces = {"1": trace_shift} if trace_shift else {}
        boundary = dict(eventsDrained=True, traceSequences=traces, frame=baseline["frame"],
                        nativeCycle=baseline["nativeCycle"], endpointNativeCycle=baseline["nativeCycle"])
        if role == "WILD":
            rows.append(dict(phase="setup", initialSnapshot=deepcopy(baseline), initialEvents=[],
                             initialEventStartFrame=baseline["frame"]))
        else:
            rows.append(dict(phase="setup", action="prepare-rider", command="spawn", snapshot=deepcopy(baseline),
                receipt=dict(preparedOnly=True, snapshot=deepcopy(baseline), events=[], setupBoundary=deepcopy(boundary))))
        selected = select_current_actor(baseline, reset["subject"])
        rows.append(dict(phase="setup", action=subject + "-bind", command="bind", snapshot=deepcopy(baseline), receipt=selected))
        receipt = dict(boundary="native-field-command-trampoline", preparedOnly=True, acceptedProof=False,
            fatal=False, error=None, firstBadCheckpoint=None, firstInvalidThreadSwitch=None, nativeHeapAdaptation=[],
            trampoline=dict(address=0x02200000),
            calls=[dict(routine="reduce_walk", requestedArguments=[0x02200210], returnValue=1)],
            snapshot=deepcopy(baseline), value=reset, events=[], setupBoundary=deepcopy(boundary))
        rows.append(dict(phase="setup", action=subject + "-begin", command="acceleration.begin", snapshot=deepcopy(baseline), receipt=receipt))
        if intent and role == "WILD":
            arm = dict(id="arm-intent", op="walk-intent.arm", args=dict(subject=subject, direction=direction, maxFrames=600), budget=deepcopy(budget))
            test["setup"].insert(2, arm)
            control = dict(armed=True, closed=False, failure=None, acceptedStarts=0, terminal=False,
                direction=direction, subject=deepcopy(selected), calls=[], guestMemoryWrites=0, acceptedProof=False)
            rows.append(dict(phase="setup", action="arm-intent", command="walk-intent.arm", snapshot=deepcopy(baseline),
                receipt=dict(armed=True, prepared=True, frame=baseline["frame"], snapshot=deepcopy(baseline), walkIntent=control)))
        previous = baseline["frame"]
        for sample, events in samples:
            rows.append(dict(phase="setup", action=subject + "-walk", requestedGameFrames=1, completedGameFrames=1,
                nativeCycles=2, observedFieldFrames=1, samples=[sample], events=events,
                cycleIntervals=[dict(cpuNs=100, wallNs=100, completedGameFrame=previous),
                                dict(cpuNs=100, wallNs=100, completedGameFrame=sample["frame"])]))
            previous = sample["frame"]
        endpoint = samples[-1][0]
        rows.append(dict(phase="setup", action=subject + "-end", command="acceleration.end", snapshot=deepcopy(endpoint),
            receipt=dict(subject=selected, role=role, frame=endpoint["frame"], nativeCycle=endpoint["nativeCycle"],
                         completedWalks=7, advancedFrames=0, acceptedProof=False)))
        if intent and role == "WILD":
            test["setup"].insert(5, dict(id="close-intent", op="walk-intent.close", args={}, budget=deepcopy(budget)))
            control = {**deepcopy(control), "closed": True, "terminal": True, "acceptedStarts": 7}
            rows.append(dict(phase="setup", action="close-intent", command="walk-intent.close", snapshot=deepcopy(endpoint),
                receipt=dict(closed=True, advancedFrames=0, walkIntent=control)))
        frame_shift = endpoint["frame"]
        native_shift = endpoint["nativeObservation"]["sequence"]
        trace_shift += 28
    return test, rows


def replay(test, rows):
    evaluator = TestEvaluator(test)
    evaluator.install_measurements({KIND: {"schema": SCHEMA, "sourceSha256": SOURCE}})
    for row in rows:
        if evaluator.observe_record(row)["state"] == "failed":
            break
    return evaluator


class AccelerationContractTests(unittest.TestCase):
    def test_unmodified_boot_boundary_is_excluded_not_prepared_motion(self):
        test, rows = integration_fixture()
        initial = deepcopy(rows[0])
        initial["initialSnapshot"]["prepared"] = False
        evaluator = replay(test, [initial])
        self.assertEqual(evaluator.failures, [])
        self.assertEqual(evaluator.frames, 0)
        self.assertFalse(evaluator.measurements[KIND].ready)
        for field, value in (("prepared", None), ("fieldAvailable", False),
                             ("observationBoundary", "unknown")):
            bad = deepcopy(initial)
            bad["initialSnapshot"][field] = value
            with self.subTest(field=field):
                self.assertTrue(replay(test, [bad]).failures)

    def test_typed_two_windows(self):
        checked = validate_test(recipe())
        self.assertEqual(checked["measurements"][0]["subjects"], {"WILD": "walker", "MOUNTED": "rider"})

    def test_wrong_mode_subject_duplicate_and_open_window_reject(self):
        for mutation in ("mode", "subject", "duplicate", "open", "mutation"):
            value = recipe()
            if mutation == "mode": value["mode"] = "normal"
            elif mutation == "subject": value["measurements"][0]["subjects"]["WILD"] = "rider"
            elif mutation == "duplicate": value["setup"][5]["args"]["subject"] = "walker"
            elif mutation == "open": value["setup"].pop()
            else: value["setup"][2] = dict(id="party", op="party", args={"slot": 1, "hp": 21}, budget=value["setup"][2]["budget"])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_test(value)

    def test_real_evaluator_two_windows_excludes_between_setup_frames(self):
        test, rows = integration_fixture()
        evaluator = replay(test, rows)
        self.assertEqual(evaluator.failures, [])
        result = evaluator.finish()
        self.assertTrue(result["passed"], result["failures"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["observedFrames"], sum(len(row.get("samples", [])) for row in rows))
        self.assertLess(result["observedFrames"], result["lastFrame"] - rows[0]["initialSnapshot"]["frame"])
        self.assertEqual(len(result["measurements"][KIND]["measurements"]), 4)

    def test_raw_missing_boundary_gap_wrong_end_and_bridge_fault_reject(self):
        for mutation in ("prefix", "sample", "end", "bridge", "drift", "watermark"):
            test, rows = integration_fixture()
            begin = next(row for row in rows if row.get("command") == "acceleration.begin")
            if mutation == "prefix": del rows[0]["initialEvents"]
            elif mutation == "sample": rows.pop(next(i for i, row in enumerate(rows) if "samples" in row))
            elif mutation == "end": next(row for row in rows if row.get("command") == "acceleration.end")["receipt"]["completedWalks"] = 6
            elif mutation == "bridge": begin["receipt"]["calls"][0]["requestedArguments"][0] += 4
            elif mutation == "drift":
                begin["snapshot"]["player"]["pos_x"] += 1
                begin["receipt"]["snapshot"] = deepcopy(begin["snapshot"])
            else: begin["receipt"]["setupBoundary"]["traceSequences"] = {"1": 9}
            with self.subTest(mutation=mutation):
                self.assertTrue(replay(test, rows).failures)

    def test_job_uses_native_begin_snapshot_not_diagnostic_ui_cache(self):
        native = {"frame": 10}
        self.assertEqual(_command_snapshot("acceleration.begin", {"snapshot": native}, {**native, "terrain": "stale"}), native)

    def test_typed_intent_cardinal_and_diagonal_without_frame_credit(self):
        for direction, delta in ((0, (0, -1)), (7, (1, 1))):
            test, rows = integration_fixture(intent=True, direction=direction, delta=delta)
            evaluator = replay(test, rows)
            self.assertEqual(evaluator.failures, [])
            self.assertTrue(evaluator.finish()["passed"])
            self.assertEqual(evaluator.frames, sum(len(r.get("samples", [])) for r in rows))
            for change in ("pose", "native-cycle", "subject", "close-count", "close-direction"):
                bad = deepcopy(rows)
                arm = next(r for r in bad if r.get("command") == "walk-intent.arm")
                close = next(r for r in bad if r.get("command") == "walk-intent.close")
                if change == "pose": arm["snapshot"]["player"]["pos_x"] += 1
                elif change == "native-cycle": arm["snapshot"]["nativeCycle"] += 1
                elif change == "subject": arm["receipt"]["walkIntent"]["subject"]["subjectIdentity"] += 1
                elif change == "close-count": close["receipt"]["walkIntent"]["acceptedStarts"] = 6
                else: close["receipt"]["walkIntent"]["direction"] ^= 1
                with self.subTest(direction=direction, change=change):
                    self.assertTrue(replay(test, bad).failures)

    def test_intent_close_matches_arm_receipt_not_older_bind_time(self):
        test, rows = integration_fixture(intent=True)
        arm_index = next(i for i, r in enumerate(rows) if r.get("command") == "walk-intent.arm")
        end = next(r for r in rows if r.get("command") == "acceleration.end")["receipt"]
        end["subject"] = deepcopy(end["subject"])
        end["subject"]["observedFrame"] -= 1
        def replay_with_older_binding():
            evaluator = replay(test, rows[:arm_index])
            # Model the cached binding from before RESET's completed frame.
            subject = test["setup"][2]["args"]["subject"]
            evaluator.subjects[subject]["observedFrame"] -= 1
            for row in rows[arm_index:]:
                if evaluator.observe_record(row)["state"] == "failed":
                    break
            return evaluator
        evaluator = replay_with_older_binding()
        self.assertEqual(evaluator.failures, [])
        self.assertTrue(evaluator.finish()["passed"])
        close = next(r for r in rows if r.get("command") == "walk-intent.close")
        close["receipt"]["walkIntent"]["subject"]["observedFrame"] -= 1
        self.assertTrue(replay_with_older_binding().failures)

    def test_shared_job_dispatches_reset_and_retains_raw_windows(self):
        from tools.overworld.test_devtools_jobs import JobsTests, FrameWorker
        from tools.overworld.devtools import Service
        from tools.overworld.devtools_evidence_stream import load_observations
        from pathlib import Path
        test, rows = integration_fixture()
        chunks = iter([r for r in rows if "samples" in r])
        begins = iter([r for r in rows if r.get("command") == "acceleration.begin"])
        spawn = next(r for r in rows if r.get("command") == "spawn")
        class Worker(FrameWorker):
            def __init__(self, *args):
                super().__init__(*args)
                self.current = deepcopy(rows[0]["initialSnapshot"])
            def call(self, op, args=None):
                self.calls.append((op, deepcopy(args)))
                if op == "step":
                    self.assert_single(args)
                    chunk = deepcopy(next(chunks))
                    self.current = deepcopy(chunk["samples"][-1])
                    return {**chunk, "snapshot": deepcopy(self.current)}
                if op == "walk-policy.reset":
                    row = next(begins)
                    self.current = deepcopy(row["snapshot"])
                    return deepcopy(row["receipt"])
                if op == "spawn":
                    self.current = deepcopy(spawn["snapshot"])
                    return deepcopy(spawn["receipt"])
                if op == "record.start":
                    return {"snapshot": deepcopy(self.current), "events": []}
                return deepcopy(self.current)
            def assert_single(self, args):
                if args["frames"] != 1:
                    raise ValueError("role completion must stop at one-frame requests")
        harness = JobsTests()
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        self.addCleanup(harness.tearDown)
        harness.service = Service(harness.root, Worker)
        with patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value={KIND: {"schema": SCHEMA, "sourceSha256": SOURCE}}), \
                patch("tools.overworld.control.prepare_shared_test", return_value={"passed": True}):
            harness.service.tests.save(test["id"], test)
            started = harness.service.command({"op": "test.start", "args": {"name": test["id"]}})
            self.assertTrue(started["ok"], started)
            done = harness.finish()
        self.assertTrue(done["passed"], done.get("evaluation"))
        retained = load_observations(Path(done["observationsArtifact"]["path"]))
        self.assertIn("initialEvents", retained[0])
        self.assertEqual([r["command"] for r in retained if r.get("command", "").startswith("acceleration.")],
                         ["acceleration.begin", "acceleration.end"] * 2)
        worker = Worker.instances[-1]
        calls = [args for op, args in worker.calls if op == "walk-policy.reset"]
        self.assertEqual([args["subject"]["role"] for args in calls], ["WILD", "MOUNTED"])


if __name__ == "__main__":
    unittest.main()
