"""Shared measurement replay using real native-control writes and readers.

The positive chain is the existing independently authored Stream fixture.
Only the RAM transport/public actor packet is fake; faults, receipts, source
and object readers, MotionRecorder and TestEvaluator are their actual code.
This is host proof, not a claim that the live ROM control has run.
"""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from tools.overworld.devtools_observer_control import NativeObserverControl
from tools.overworld.devtools_observer_control_measurement import LiveObserverControlMeasurement
from tools.overworld.devtools_runtime import actor_identity_checks
from tools.overworld.devtools_test_contract import TestEvaluator
from tools.overworld import test_devtools_observer_control as native_fixture
from tools.overworld.test_devtools_chain_measurement import SCHEMA, SOURCE, Stream
from tools.overworld.test_devtools_test_contract import recipe


KIND = "live-observer-control-v1"


class Fixture:
    def __init__(self):
        self.stream = Stream().complete()
        # Generic spawn binding also needs the actual attachment event. The
        # chain fixture has only motion traces; add this separate observation
        # and retain all subsequent sequence positions, counts and poses.
        attachment = deepcopy(self.stream.items[1][1][0])
        attachment["data"].update(event="ACTOR_ATTACHED", sequence=1)
        for _, events in self.stream.items:
            for event in events:
                if event["kind"] == "native": event["data"]["sequence"] += 1
        self.stream.items[1][1].insert(0, attachment)
        self.native = native_fixture.NativeControlTests()
        self.native.setUp()
        f = self.native
        # Use the baseline's exact source and generation values; do not change
        # its authored chain packets to agree with a different native fixture.
        f.actor = deepcopy(self.stream.actor)
        source, engine = f.actor["sourceIdentity"], f.actor["engineIdentity"]
        f.obj, f.manager = source["object"], engine["current_manager"]
        f.objects = f.obj - 17 * 0x12C
        rt, mem = f.session.rt, f.mem
        for address, value in ((f.field + 0x3C, f.manager), (f.manager + 4, 64),
                               (f.manager + 0x124, f.objects), (0x02120000, source["map_id"]),
                               (f.obj, 1), (f.obj + 8, source["object_id"]),
                               (f.obj + 12, source["map_id"]), (f.obj + 32, engine["script_id"]),
                               (f.obj + 0xB4, f.manager), (rt.WILD_STATE, f.obj),
                               (rt.WILD_STATE + 4, source["personality"])):
            mem.u32(address, value)
        for address, value in ((0x0230000C, f.actor["handle"]["fieldEpoch"]),
                               (0x0230002E, f.actor["handle"]["mapGeneration"]),
                               (rt.WILD_STATE + 8, source["map_id"]),
                               (rt.WILD_STATE + 10, source["species"]),
                               (rt.WILD_STATE + 18, source["encounter_generation"])):
            mem.u16(address, value)
        mem.put(rt.WILD_STATE + 12, bytes([source["form"], source["level"]]))
        mem.put(rt.WILD_STATE + 16, bytes([source["active"], source["object_id"]]))
        f.session.completed_frames = self.stream.frame
        rt.EXECUTED_FRAME_COUNT = self.stream.frame * 2
        f.subject = {key: deepcopy(f.actor[key]) for key in ("handle", "species", "role", "subjectIdentity")}
        self.control = None
        self.rows = []

    def baseline(self, measurement):
        for snapshot, events in self.stream.items:
            measurement.observe(snapshot, events)
        return measurement

    def arm(self, measurement, kind):
        args = measurement.arm_args(self.native.subject, kind)
        self.control = NativeObserverControl(self.native.session, args["subject"])
        self.control.arm(args["kind"], max_frames=args["maxFrames"])
        return args

    def boundary(self, *, elapsed=None):
        f, rt = self.native, self.native.session.rt
        if elapsed is not None:
            origin = deepcopy(f.actor["logical"])
            f.actor.update(motionKind="WALK", motionPhase="MOVING", motionDuration=8,
                           motionElapsed=elapsed, origin=origin,
                           target={"x": origin["x"] + 2, "y": origin["y"] + 2})
            for key, offset in (("x", 0x70), ("y", 0x78)):
                f.mem.u32(f.obj + offset, (origin[key] << 16) + 0x8000 + 2 * 0x10000 * elapsed // 8)
            f.mem.u32(f.obj + 0x74, 0)
            f.mem.u32(f.obj + 0x28, 2)
        f.session.completed_frames += 1
        rt.EXECUTED_FRAME_COUNT += 2
        self.control.completed_boundary()
        snapshot = self.snapshot()
        self.rows.append(deepcopy(snapshot))
        return snapshot

    def snapshot(self):
        f, rt = self.native, self.native.session.rt
        snapshot = deepcopy(self.stream.items[-1][0])
        snapshot.update(frame=f.session.completed_frames, nativeCycle=rt.EXECUTED_FRAME_COUNT, prepared=True,
                        actorFrame=f.session.completed_frames, observerControl=self.control.result())
        actor = rt.actor_state(f.session.emu, 0)
        source = rt.wild_spawn(f.session.emu, 0)
        engine = rt.live_wild_object_identity(f.session.emu, 0)
        checks = actor_identity_checks(actor, source, engine, snapshot["context"], 0)
        actor.update(sourceIdentity=source, engineIdentity=engine,
                     engineObject=rt.object_state(f.session.emu, f.obj),
                     identityVerified=all(checks.values()), identityChecks=checks,
                     identityFailures=[name for name, passed in checks.items() if not passed])
        snapshot["actors"] = [actor]
        return snapshot

    def cleanup(self):
        self.control.close()
        snapshot = self.snapshot()
        snapshot.update(observationBoundary="observer-control-restoration-readback", observedFrameCredit=0)
        return {"snapshot": snapshot, "observerControl": self.control.result(),
                "frame": self.native.session.completed_frames, "closed": True, "advancedFrames": 0}


def evaluator_recipe(mode="observer-control"):
    value = recipe()
    value.update(mode=mode, budgets={"maxSeconds": 300, "maxFrames": 1000,
                 "noProgressFrames": 600, "minObservedFrames": 2})
    value["subjects"][0]["acquire"] = "spawn"
    value["assertions"] = [{"kind": "frame-count", "operator": "gte", "value": 2}]
    if mode == "observer-control":
        value["measurements"] = [{"kind": KIND, "subject": "subject"}]
    return value


def shared_job_fixture():
    """Return (test, JSONL rows) from the real control fixture, not a claimed pass.

    Consumers use SCHEMA/SOURCE as their measurement inputs. The recipe is a
    host-only short route, not the registered live recipe. Every arm and close
    receipt comes from NativeObserverControl over the fixture's byte RAM.
    """
    fixture = Fixture()
    test = evaluator_recipe()

    def action(name, op, args, frames):
        return {"id": name, "op": op, "args": args,
                "budget": {"maxSeconds": 120, "maxFrames": frames, "noProgressFrames": frames}}

    def stage(value):
        return {"kind": "measurement-stage", "measurement": KIND, "stage": value}

    test["setup"] = [action("observe-spawn", "step", {"frames": 1, "keys": []}, 1)]
    test["actions"] = [
        action("bind-subject", "bind", {"subject": "subject"}, 1),
        action("normal-baseline", "wait", {"predicate": stage("baseline")}, 500),
        action("arm-render", "observer-control", {"subject": "subject", "fault": "render-stall"}, 1),
        action("render-rejection", "wait", {"predicate": stage("render-detected")}, 3),
        action("arm-inactive", "observer-control", {"subject": "subject", "fault": "inactive-object"}, 1),
        action("identity-rejection", "wait", {"predicate": stage("complete")}, 1),
    ]
    test["assertions"] = [{"kind": "measurement-complete", "measurement": KIND, "when": "final"}]
    evaluator = TestEvaluator(test)
    evaluator.install_measurements({KIND: {"schema": SCHEMA, "sourceSha256": SOURCE}})
    rows = []

    def sample(phase, name, snapshot, events=()):
        snapshot = deepcopy(snapshot)
        # The older chain fixture omits this diagnostic membership index.
        # Obtain it from the same real manager reader used by the fault path.
        for actor in snapshot["actors"]:
            actor["engineIdentity"].setdefault("manager_index", fixture.native.session.rt.live_wild_object_identity(
                fixture.native.session.emu, actor["handle"]["slot"])["manager_index"])
        rows.append({"phase": phase, "action": name, "snapshot": deepcopy(snapshot),
                     "samples": [snapshot], "events": deepcopy(list(events)),
                     "completedGameFrames": 1, "nativeCycles": 2})
        evaluator.observe(snapshot, events, count_frame=phase == "observe")
        if evaluator.failures:
            raise AssertionError(evaluator.result())
        return snapshot

    initial = deepcopy(fixture.stream.items[0][0])
    rows.append({"phase": "setup", "initialSnapshot": initial})
    evaluator.observe(initial, count_frame=False)
    snapshot = sample("setup", "observe-spawn", *fixture.stream.items[1])
    receipt = evaluator.bind("subject", snapshot)
    rows.append({"phase": "observe", "action": "bind-subject", "command": "bind",
                 "receipt": receipt, "snapshot": snapshot})
    for snapshot, events in fixture.stream.items[2:]:
        sample("observe", "normal-baseline", snapshot, events)

    def arm(name, kind):
        args = evaluator.observer_control_args("subject", kind)
        if fixture.control is not None:
            fixture.control.close()
        fixture.control = NativeObserverControl(fixture.native.session, args["subject"])
        fixture.control.arm(args["kind"], max_frames=args["maxFrames"])
        snapshot, native = fixture.snapshot(), fixture.control.result()
        receipt = {"snapshot": snapshot, "observerControl": native, "prepared": True,
                   "frame": snapshot["frame"], "armed": True}
        rows.append({"phase": "observe", "action": name, "command": "observer-control",
                     "receipt": receipt, "snapshot": deepcopy(snapshot)})

    arm("arm-render", "render-stall")
    for elapsed in range(3):
        sample("observe", "render-rejection", fixture.boundary(elapsed=elapsed))
    arm("arm-inactive", "inactive-object")
    sample("observe", "identity-rejection", fixture.boundary())
    cleanup = fixture.cleanup()
    rows.append({"phase": "cleanup", "command": "observer-control.close",
                 "receipt": cleanup, "snapshot": deepcopy(cleanup["snapshot"])})
    evaluator.observer_control_cleanup(cleanup)
    result = evaluator.finish()
    if not result["passed"]:
        raise AssertionError(result)
    # Also prove the exported shape survives the actual JSONL transport.
    return test, [json.loads(json.dumps(row, allow_nan=False)) for row in rows]


class MeasurementTests(unittest.TestCase):
    def ready(self):
        fixture = Fixture()
        meter = fixture.baseline(LiveObserverControlMeasurement(SCHEMA, SOURCE, max_frames=1000))
        self.assertTrue(meter.stage("baseline"), meter.result())
        self.assertFalse(meter.result()["ready"])
        return fixture, meter

    def render(self, fixture, meter):
        fixture.arm(meter, "render-stall")
        for elapsed in range(3):
            meter.observe(fixture.boundary(elapsed=elapsed))
        self.assertTrue(meter.stage("render-detected"), meter.result()["failures"])

    def test_shared_job_fixture_replays_real_receipts_and_subject_controls(self):
        from tools.overworld.control import _replay_shared_test
        test, rows = shared_job_fixture()
        with patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value={
                KIND: {"schema": SCHEMA, "sourceSha256": SOURCE}}):
            result = _replay_shared_test(test, rows)
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["observedFrames"], 410)
            self.assertTrue(result["measurements"][KIND]["cleanup"]["closed"])
            for fault in ("absent-subject", "stale-subject"):
                negative = _replay_shared_test(test, rows, fault=fault)
                self.assertFalse(negative["passed"], negative)
                self.assertTrue(negative["failures"])

    def test_full_real_control_path_retains_two_detections_and_frozen_three_chain_baseline(self):
        fixture, meter = self.ready()
        baseline = deepcopy(meter.result()["baseline"])
        self.assertTrue(baseline["spawnPassed"])
        self.assertEqual([item["count"] for item in baseline["intervals"]], [8, 14, 10])
        self.assertEqual([item["motions"] for item in baseline["actions"]], [4, 4, 4])
        self.render(fixture, meter)
        render = deepcopy(meter.result()["detections"]["render-stall"])
        self.assertEqual([item["reason"] for item in render["failures"]], ["render-stall"] * 2)
        fixture.control.close()
        fixture.arm(meter, "inactive-object")
        meter.observe(fixture.boundary())
        meter.observe_cleanup(fixture.cleanup())
        result = meter.finish()
        self.assertTrue(result["passed"], result)
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["baseline"], baseline)
        self.assertEqual(result["detections"]["render-stall"], render)
        self.assertEqual(set(result["detections"]), {"render-stall", "inactive-object"})
        self.assertEqual(result["failures"], [])
        self.assertIn("render-stall", [item["reason"] for item in meter.render.failures])

    def test_controls_cannot_arm_before_baseline_on_wrong_subject_or_wrong_order(self):
        fixture = Fixture()
        meter = LiveObserverControlMeasurement(SCHEMA, SOURCE, max_frames=1000)
        with self.assertRaisesRegex(ValueError, "baseline"):
            meter.arm_args(fixture.native.subject, "render-stall")
        for snapshot, events in fixture.stream.items[:-1]: meter.observe(snapshot, events)
        with self.assertRaisesRegex(ValueError, "baseline"):
            meter.arm_args(fixture.native.subject, "render-stall")
        meter.observe(*fixture.stream.items[-1])
        wrong = {**fixture.native.subject, "subjectIdentity": fixture.native.subject["subjectIdentity"] + 1}
        with self.assertRaisesRegex(ValueError, "subject"):
            meter.arm_args(wrong, "render-stall")
        with self.assertRaisesRegex(ValueError, "render detection"):
            meter.arm_args(fixture.native.subject, "inactive-object")

    def test_baseline_fault_or_early_fault_receipt_cannot_be_frozen_as_passed(self):
        for mode in ("motion-error", "injected"):
            with self.subTest(mode=mode):
                fixture = Fixture()
                items = deepcopy(fixture.stream.items)
                if mode == "injected": items[1][0]["observerControl"] = {"kind": "render-stall"}
                else: items[4][0]["actors"][0]["engineObject"]["pos_x"] = 0
                meter = LiveObserverControlMeasurement(SCHEMA, SOURCE, max_frames=1000)
                for snapshot, events in items: meter.observe(snapshot, events)
                self.assertFalse(meter.stage("baseline"))
                self.assertTrue(meter.result()["failures"])

    def test_wrong_source_frame_missing_write_and_readback_fail_closed(self):
        for fault in ("source", "frame", "missing-write", "readback", "history"):
            with self.subTest(fault=fault):
                fixture, meter = self.ready()
                fixture.arm(meter, "render-stall")
                for elapsed in range(2): meter.observe(fixture.boundary(elapsed=elapsed))
                row = fixture.boundary(elapsed=2)
                receipts = row["observerControl"]["receipts"]
                if fault == "source": receipts[-1]["sourceIdentity"]["personality"] += 1
                elif fault == "frame": receipts[-1]["frame"] += 1
                elif fault == "missing-write": receipts.pop()
                elif fault == "readback": receipts[-1]["afterPose"]["pos_z"] += 1
                else: receipts[0]["maxFrames"] += 1
                meter.observe(row)
                self.assertTrue(meter.result()["failures"], meter.result())
                self.assertFalse(meter.finish()["passed"])

    def test_render_detection_cannot_substitute_for_identity_detection(self):
        fixture, meter = self.ready()
        self.render(fixture, meter)
        with self.assertRaisesRegex(ValueError, "already used"):
            meter.arm_args(fixture.native.subject, "render-stall")
        self.assertFalse(meter.finish()["passed"])
        self.assertEqual(set(meter.result()["detections"]), {"render-stall"})

    def test_inactive_wrong_bit_and_identity_acceptance_cannot_pass(self):
        for fault in ("other-bit", "identity-accepted", "pointer", "frame"):
            with self.subTest(fault=fault):
                fixture, meter = self.ready()
                self.render(fixture, meter)
                fixture.control.close()
                fixture.arm(meter, "inactive-object")
                row = fixture.boundary()
                actor = row["actors"][0]
                if fault == "other-bit":
                    row["observerControl"]["receipts"][-1]["afterFlags"] ^= 2
                    actor["engineObject"]["flags"] ^= 2
                elif fault == "identity-accepted": actor["identityVerified"] = True
                elif fault == "pointer": actor["engineIdentity"]["pointer"] += 4
                else: row["frame"] += 1
                meter.observe(row)
                self.assertTrue(meter.result()["failures"], meter.result())
                self.assertFalse(meter.finish()["passed"])
                fixture.control.close()

    def test_generic_evaluator_exception_is_only_exact_inactive_frame_and_subject(self):
        fixture = Fixture()
        evaluator = TestEvaluator(evaluator_recipe())
        evaluator.install_measurements({KIND: {"schema": SCHEMA, "sourceSha256": SOURCE}})
        for index, (snapshot, events) in enumerate(fixture.stream.items):
            evaluator.observe(snapshot, events)
            if index == 1: evaluator.bind("subject", snapshot)
        self.assertEqual(evaluator.result()["failures"], [])
        meter = evaluator.measurements[KIND]
        args = evaluator.observer_control_args("subject", "render-stall")
        fixture.control = NativeObserverControl(fixture.native.session, args["subject"])
        fixture.control.arm(args["kind"], args["maxFrames"])
        for elapsed in range(3): evaluator.observe(fixture.boundary(elapsed=elapsed))
        self.assertEqual(evaluator.result()["failures"], [], evaluator.result())
        fixture.control.close()
        args = evaluator.observer_control_args("subject", "inactive-object")
        fixture.control = NativeObserverControl(fixture.native.session, args["subject"])
        fixture.control.arm(args["kind"], args["maxFrames"])
        row = fixture.boundary()
        evaluator.observe(row)
        self.assertEqual(evaluator.result()["failures"], [], evaluator.result())
        self.assertTrue(evaluator.expected_control_identity_failure(row, fixture.native.subject))
        wrong = {**fixture.native.subject, "subjectIdentity": fixture.native.subject["subjectIdentity"] + 1}
        self.assertFalse(evaluator.expected_control_identity_failure(row, wrong))
        later = deepcopy(row); later["frame"] += 1
        self.assertFalse(evaluator.expected_control_identity_failure(later, fixture.native.subject))
        evaluator.observer_control_cleanup(fixture.cleanup())
        self.assertTrue(evaluator.finish()["passed"], evaluator.result())
        # The same actual inactive snapshot is an error in a normal recipe.
        normal = TestEvaluator(evaluator_recipe("normal"))
        normal.observe(*fixture.stream.items[0])
        normal.observe(*fixture.stream.items[1])
        normal.bind("subject", fixture.stream.items[1][0])
        inactive = deepcopy(row); inactive.update(frame=3, prepared=False)
        normal.observe(inactive)
        self.assertTrue(normal.result()["failures"])
        self.assertIn("verified engine/presentation identity", normal.result()["failures"][0]["message"])
        self.assertFalse(normal.finish()["passed"])

    def test_cleanup_is_required_and_same_frame_exact_source_and_bit_are_checked(self):
        for fault in ("missing", "frame", "pending", "history", "wrong-bit", "source", "recycled-pointer"):
            with self.subTest(fault=fault):
                fixture, meter = self.ready()
                self.render(fixture, meter)
                fixture.control.close()
                fixture.arm(meter, "inactive-object")
                meter.observe(fixture.boundary())
                self.assertTrue(meter.stage("complete"), meter.result()["failures"])
                cleanup = fixture.cleanup()
                if fault == "missing":
                    self.assertFalse(meter.finish()["passed"])
                    continue
                if fault == "frame": cleanup["snapshot"]["frame"] += 1
                elif fault == "pending": cleanup["observerControl"]["cleanupPending"] = True
                elif fault == "history": cleanup["observerControl"]["receipts"][0]["maxFrames"] += 1
                elif fault == "wrong-bit":
                    cleanup["observerControl"]["receipts"][-1]["afterFlags"] ^= 2
                    cleanup["snapshot"]["actors"][0]["engineObject"]["flags"] ^= 2
                elif fault == "source": cleanup["observerControl"]["receipts"][-1]["sourceIdentity"]["personality"] += 1
                else: cleanup["snapshot"]["actors"][0]["engineIdentity"]["pointer"] += 0x12C
                with self.assertRaises(ValueError): meter.observe_cleanup(cleanup)
                self.assertFalse(meter.finish()["passed"])


if __name__ == "__main__": unittest.main()
