"""Synthetic shared-stream checks, not native acceptance evidence."""
from copy import deepcopy
from pathlib import Path
import unittest

from tools.overworld.devtools_walk_policy_control_measurement import KIND, WalkPolicyControlMeasurement
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.test_devtools_acceleration_contract import integration_fixture


def fixture(role="WILD", *, first_elapsed=0):
    test, source = integration_fixture()
    subject = "walker" if role == "WILD" else "rider"
    # Use the existing complete native Walk fixture, rebasing only the second role's transport counters.
    if role != "WILD" or first_elapsed:
        from tools.overworld.test_devtools_acceleration_measurement import fixture as motion_fixture
        baseline, reset, samples = motion_fixture(role, species=155, first_elapsed=first_elapsed)
        baseline["fieldAvailable"] = True
        selected = select_current_actor(baseline, reset["subject"])
        raw = []
        for sample, events in samples[:10 - first_elapsed]:
            sample["fieldAvailable"] = True
            raw.append(dict(phase="observe", action="walk", requestedGameFrames=1, completedGameFrames=1,
                nativeCycles=2, observedFieldFrames=1, samples=[sample], events=events,
                cycleIntervals=[dict(cpuNs=100, wallNs=100, completedGameFrame=sample["frame"]-1),
                                dict(cpuNs=100, wallNs=100, completedGameFrame=sample["frame"])]))
    else:
        baseline = deepcopy(source[0]["initialSnapshot"])
        selected = deepcopy(source[1]["receipt"])
        raw = deepcopy([r for r in source if r.get("action") == "walker-walk"][:10])
    # Complete the native manager identity omitted by the lower-level motion
    # fixture. Keep every retained copy (including native entry/return actors)
    # coherent with the selected slot; the parent controller checks these too.
    def complete_identity(value):
        if isinstance(value, dict):
            handle = value.get("handle")
            if isinstance(handle, dict) and "slot" in handle:
                object_id = 224 + handle["slot"]
                if isinstance(value.get("sourceIdentity"), dict):
                    value["sourceIdentity"]["object_id"] = object_id
                if isinstance(value.get("engineIdentity"), dict):
                    value["engineIdentity"].update(manager_index=handle["slot"],
                        object_id=object_id, spawn_object_id=object_id)
            for child in value.values(): complete_identity(child)
        elif isinstance(value, list):
            for child in value: complete_identity(child)
    for value in (baseline, selected, raw): complete_identity(value)
    armed = dict(state="armed", failure=None, cleanupPending=False, subject=selected, receipt=None, acceptedProof=False)
    initial = deepcopy(baseline)
    initial["prepared"] = False
    baseline["walkPolicyControl"] = deepcopy(armed)
    arm = dict(armed=True, prepared=True, acceptedProof=False, snapshot=deepcopy(baseline), walkPolicyControl=deepcopy(armed))
    for row in raw:
        row.update(phase="observe", action="walk")
        row["samples"][0]["walkPolicyControl"] = deepcopy(armed)
    commit = next(e["data"] for e in raw[-1]["events"] if e["kind"] == "native-observation")
    clean = dict(rawHex=commit["policyBeforeHex"], policy=deepcopy(commit["policyBefore"]))
    bad = deepcopy(clean)
    changed = bytearray.fromhex(clean["rawHex"])
    changed[1] += 1
    bad["rawHex"] = changed.hex()
    bad["policy"]["counter"] += 1
    clock = dict(actorFrame=commit["entryActorFrame"], nativeCycle=commit["entryNativeCycle"])
    complete = deepcopy(armed)
    complete.update(state="complete", receipt=dict(clean=clean, bad=bad, restored=deepcopy(clean),
        policyAddress=0x022005BC, changedOffset=1, guestInstructionAdvance=0, clock=clock, restoredClock=deepcopy(clock)))
    raw[-1]["samples"][0]["walkPolicyControl"] = deepcopy(complete)
    close = dict(closed=True, advancedFrames=0, acceptedProof=False, walkPolicyControl=complete)
    budget = dict(maxSeconds=30, maxFrames=100, noProgressFrames=100)
    test.update(id="test.walk-control", mode="observer-control", subjects=[dict(id=subject, species=selected["species"], role=role, acquire="existing")],
        measurements=[dict(kind=KIND, subject=subject)], budgets=dict(maxSeconds=120, maxFrames=100, noProgressFrames=100, minObservedFrames=1),
        assertions=[dict(kind="measurement-complete", measurement=KIND)],
        setup=[dict(id="bind", op="bind", args=dict(subject=subject), budget=deepcopy(budget))],
        actions=[dict(id=name, op=op, args=args, budget=deepcopy(budget)) for name,op,args in (
            ("arm", "walk-policy-control.arm", dict(subject=subject)),
            ("walk", "wait", dict(predicate=dict(kind="measurement-complete", measurement=KIND))),
            ("close", "walk-policy-control.close", {}))])
    rows = [dict(phase="setup", initialSnapshot=initial, initialEvents=[], initialEventStartFrame=initial["frame"]),
        dict(phase="setup", action="bind", command="bind", snapshot=deepcopy(initial), receipt=selected),
        dict(phase="observe", action="arm", command="walk-policy-control.arm", snapshot=deepcopy(baseline), receipt=arm),
        *raw, dict(phase="observe", action="close", command="walk-policy-control.close", snapshot=deepcopy(raw[-1]["samples"][0]), receipt=close)]
    return test, rows


def replay(test, rows):
    evaluator = TestEvaluator(test)
    evaluator.install_measurements({KIND: {"contractVersion": 1}})
    for row in rows:
        evaluator.observe_record(row)
        if evaluator.failures: break
    return evaluator


class WalkControlTests(unittest.TestCase):
    def test_first_completed_update_can_already_be_elapsed_one(self):
        test, rows = fixture("MOUNTED")
        index = next(i for i, r in enumerate(rows) if r.get("samples"))
        row = rows[index]
        actor = next(a for a in row["samples"][0]["actors"] if a["role"] == "MOUNTED")
        actor["motionElapsed"] = 1
        self.assertFalse(replay(test, rows[:index + 1]).failures)
        for change in ("pose", "commit", "event-frame"):
            bad = deepcopy(rows[:index + 1])
            if change == "pose":
                bad[index - 1]["snapshot"]["player"]["pos_x"] += 1
                bad[index - 1]["receipt"]["snapshot"]["player"]["pos_x"] += 1
            elif change == "commit":
                next(a for a in bad[index]["samples"][0]["actors"] if a["role"] == "MOUNTED")["commitSequence"] += 1
            else:
                next(e for e in bad[index]["events"] if e.get("data", {}).get("event") == "MOTION_STARTED")["frame"] -= 1
            with self.subTest(change=change):
                self.assertTrue(replay(test, bad).failures)
        actor["motionElapsed"] = 2
        self.assertTrue(replay(test, rows[:index + 1]).failures)
        actor["motionElapsed"] = 1
        row["events"] = [e for e in row["events"] if e.get("data", {}).get("event") != "MOTION_STARTED"]
        self.assertTrue(replay(test, rows[:index + 1]).failures)

    def test_consumed_ring_overwrite_is_not_missing_events(self):
        test, rows = fixture()
        row = [r for r in rows if r.get("samples")][-1]
        notice = dict(frame=row["samples"][0]["frame"], kind="trace-status",
            data=dict(code="ring-overwrite", traceStream=1, diagnosticOnly=True,
                      count=1, unreadEventsLost=0))
        row["events"].insert(0, notice)
        self.assertTrue(replay(test, rows).finish()["passed"])
        for lost in (1, None, False, "0"):
            with self.subTest(lost=lost):
                notice["data"]["unreadEventsLost"] = lost
                self.assertTrue(replay(test, rows).failures)
        notice["data"]["unreadEventsLost"] = 0
        for key, value in (("diagnosticOnly", False), ("traceStream", 99), ("coverageComplete", False)):
            bad = deepcopy(rows)
            [r for r in bad if r.get("samples")][-1]["events"][0]["data"][key] = value
            with self.subTest(key=key):
                self.assertTrue(replay(test, bad).failures)

    def test_both_roles_shared_path(self):
        for role in ("WILD", "MOUNTED"):
            with self.subTest(role=role):
                test, rows = fixture(role)
                evaluator = replay(test, rows)
                self.assertFalse(evaluator.failures, evaluator.failures)
                self.assertTrue(evaluator.finish()["passed"])
                result = evaluator.measurements[KIND].result()
                self.assertEqual(len(result["motions"]), 1)
                self.assertEqual(evaluator.frames, 10)
                self.assertFalse(result["acceptedProof"])

    def test_fixed_inputs(self):
        test, _ = fixture()
        self.assertEqual(measurement_inputs(test, Path("/not/a/repo")), {KIND: {"contractVersion": 1}})

    def test_seventh_start_precedes_terminal_and_closed_window(self):
        from tools.overworld.test_devtools_acceleration_contract import KIND as ACCELERATION, SCHEMA, SOURCE
        test, rows = integration_fixture()
        evaluator = TestEvaluator(test)
        evaluator.install_measurements({ACCELERATION: dict(schema=SCHEMA, sourceSha256=SOURCE)})
        predicate = dict(kind="acceleration-role-started", subject="walker", value=7)
        saw = False
        for row in rows:
            evaluator.observe_record(row)
            if evaluator.check(predicate) and not evaluator.acceleration_role_complete("walker"):
                saw = True
            if row.get("command") == "acceleration.end" and row["receipt"]["role"] == "WILD":
                self.assertFalse(evaluator.check(predicate))
                break
        self.assertFalse(evaluator.failures, evaluator.failures)
        self.assertTrue(saw)

    def test_shared_job_dispatch_retention(self):
        from unittest.mock import patch
        from tools.overworld.test_devtools_jobs import JobsTests, FrameWorker
        from tools.overworld.devtools import Service
        from tools.overworld.devtools_evidence_stream import load_observations
        test, rows = fixture()
        chunks = iter(deepcopy(rows[3:-1]))
        class Worker(FrameWorker):
            def __init__(self, *args):
                super().__init__(*args)
                self.current = deepcopy(rows[0]["initialSnapshot"])
            def call(self, op, args=None):
                self.calls.append((op, deepcopy(args)))
                if op == "step":
                    chunk = next(chunks)
                    self.current = deepcopy(chunk["samples"][-1])
                    return {**chunk, "snapshot": deepcopy(self.current)}
                if op == "walk-policy-control.arm":
                    self.current = deepcopy(rows[2]["snapshot"])
                    return deepcopy(rows[2]["receipt"])
                if op == "walk-policy-control.close": return deepcopy(rows[-1]["receipt"])
                if op == "record.start": return dict(snapshot=deepcopy(self.current), events=[])
                return deepcopy(self.current)
        harness = JobsTests()
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        self.addCleanup(harness.tearDown)
        harness.service = Service(harness.root, Worker)
        with patch("tools.overworld.control.prepare_shared_test", return_value={"passed": True}):
            harness.service.tests.save(test["id"], test)
            started = harness.service.command(dict(op="test.start", args=dict(name=test["id"])))
            self.assertTrue(started["ok"], started)
            done = harness.finish()
        self.assertTrue(done["passed"], {k: v for k,v in done.items() if k in ("error", "failure", "evaluation")})
        retained = load_observations(Path(done["observationsArtifact"]["path"]))
        self.assertIn("initialEvents", retained[0])
        arm = next(r for r in retained if r.get("command") == "walk-policy-control.arm")
        self.assertEqual(arm["receipt"], rows[2]["receipt"])

    def test_mutations_fail_closed(self):
        def bad_restore(rows): rows[-2]["samples"][0]["walkPolicyControl"]["receipt"]["restored"]["policy"]["counter"] += 1
        def missing_finish(rows): rows[-2]["events"] = [e for e in rows[-2]["events"] if e["data"].get("event") != "MOTION_FINISHED"]
        def bad_clock(rows): rows[-2]["samples"][0]["walkPolicyControl"]["receipt"]["restoredClock"]["nativeCycle"] += 1
        def bad_subject(rows): rows[2]["receipt"]["walkPolicyControl"]["subject"]["handle"]["generation"] += 1
        def arm_advance(rows): rows[2]["snapshot"]["nativeCycle"] += 1
        def bad_cleanup(rows): rows[-1]["receipt"]["advancedFrames"] = 1
        for mutation in (bad_restore, missing_finish, bad_clock, bad_subject, arm_advance, bad_cleanup):
            with self.subTest(mutation=mutation.__name__):
                test, rows = fixture()
                mutation(rows)
                evaluator = replay(test, rows)
                self.assertTrue(evaluator.failures, evaluator.result())

    def test_missing_close_not_pass(self):
        test, rows = fixture()
        evaluator = replay(test, rows[:-1])
        self.assertFalse(evaluator.failures, evaluator.failures)
        self.assertTrue(evaluator.measurements[KIND].ready)
        self.assertFalse(evaluator.finish()["passed"])

    def test_wrong_mode_and_mutating_window(self):
        for change in (lambda t: t.update(mode="prepared"),
                       lambda t: t["actions"].insert(1, deepcopy(dict(t["setup"][0], id="extra")))):
            test, _ = fixture()
            change(test)
            with self.assertRaises(ValueError): validate_test(test)


if __name__ == "__main__": unittest.main()
