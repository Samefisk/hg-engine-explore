"""Typed mounted pacing windows; host contract checks, not gameplay proof."""
from copy import deepcopy
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import MOUNT_PACING, TestEvaluator, validate_test, validate_predicate, _same_mounted_reader_boundary, _mounted_input_boundary
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.test_devtools_test_contract import recipe as base_recipe


def recipe():
    value = base_recipe()
    value.update(mode="prepared", subjects=[dict(id="rider", species=155, role="MOUNTED", acquire="existing")],
        measurements=[dict(kind=MOUNT_PACING, subject="rider")],
        budgets=dict(maxSeconds=60, maxFrames=300, noProgressFrames=60, minObservedFrames=1),
        assertions=[dict(kind="measurement-complete", measurement=MOUNT_PACING)])
    budget = dict(maxSeconds=10, maxFrames=60, noProgressFrames=60)
    value["setup"] = [dict(id="bind", op="bind", args={"subject": "rider"}, budget=deepcopy(budget))]
    value["actions"] = []
    for op, args in (("mount-pacing.arm", {"subject": "rider"}),
                     ("mount-pacing.recovery", {}), ("mount-pacing.close", {})):
        value["actions"].append(dict(id=op, op=op, args=args, budget=deepcopy(budget)))
    for index, prefix in ((1, "recovery"), (0, "main")):
        actions = []
        for op, suffix, key in (("step", "started", "until"), ("wait", "complete", "predicate")):
            args = {key: dict(kind="measurement-stage", measurement=MOUNT_PACING, stage=prefix+"-"+suffix)}
            if op == "step": args.update(frames=60, keys=["RIGHT"])
            actions.append(dict(id=prefix+"-"+suffix, op=op, args=args, budget=deepcopy(budget)))
        value["actions"][index+1:index+1] = actions
    return value


class MountedPacingContractTests(unittest.TestCase):
    def test_one_already_polled_input_edge_is_retained_not_repeated(self):
        from tools.overworld.test_devtools_mount_pacing_measurement import pacing_fixture
        baseline, subject, _, samples = pacing_fixture()
        baseline['selector'] = {'heldKeys': 0}
        sample = deepcopy(samples[0][0])
        sample['mountPacing']['latestCompletedPose']['input'] = {'heldKeys': 0}
        _mounted_input_boundary(baseline, sample, [], subject, 0x10, True)
        with self.assertRaisesRegex(ValueError, 'live held input'):
            _mounted_input_boundary(sample, sample, [], subject, 0x10, False)
        start = {'kind':'native', 'data':{'actorHandle':subject['handle']['value'], 'event':'MOTION_STARTED'}}
        with self.assertRaisesRegex(ValueError, 'live held input'):
            _mounted_input_boundary(baseline, sample, [start], subject, 0x10, True)
        sample['mountPacing']['latestCompletedPose']['input']['heldKeys'] = 0x10
        _mounted_input_boundary(baseline, sample, [], subject, 0x10, True)
        _mounted_input_boundary(sample, sample, [], subject, 0, True)
        with self.assertRaisesRegex(ValueError, 'live held input'):
            _mounted_input_boundary(sample, sample, [start], subject, 0, True)
        with self.assertRaisesRegex(ValueError, 'live held input'):
            _mounted_input_boundary(sample, sample, [], subject, 0, False)
        sample['actors'][0]['motionPhase'] = 'IDLE'
        with self.assertRaisesRegex(ValueError, 'live held input'):
            _mounted_input_boundary(sample, sample, [], subject, 0, True)

    def test_missing_reader_is_not_reported_as_wrong_input(self):
        from tools.overworld.test_devtools_mount_pacing_measurement import pacing_fixture
        baseline, subject, _, samples = pacing_fixture()
        sample = deepcopy(samples[0][0]);sample.pop('mountPacing')
        with self.assertRaisesRegex(KeyError, 'mountPacing'):
            _mounted_input_boundary(baseline, sample, [], subject, 0x10, True)

    def test_compact_queue_cache_and_command_cache_are_same_game_boundary(self):
        from tools.overworld.test_devtools_mount_pacing_measurement import pacing_fixture
        before = pacing_fixture()[0]
        before['nativeObservation'].pop('resolvedProfiles', None)
        after = deepcopy(before)
        after['nativeObservation']['resolvedProfiles'] = [{'resultHex': 'retained-cache'}]
        self.assertTrue(_same_mounted_reader_boundary(before, after))
        after['nativeObservation']['sequence'] += 1
        self.assertFalse(_same_mounted_reader_boundary(before, after))
        after = deepcopy(before)
        after['actors'][0]['commitSequence'] += 1
        self.assertFalse(_same_mounted_reader_boundary(before, after))

    def replay(self, *, wrong_input=False):
        from tools.overworld.test_devtools_mount_pacing_measurement import pacing_fixture
        from tools.overworld.devtools_records import select_current_actor
        baseline, subject, reader, samples = pacing_fixture()
        subject = select_current_actor(baseline, subject)
        reader["subject"] = deepcopy(subject)
        for sample, events in samples:
            sample["mountPacing"]["subject"] = deepcopy(subject)
            sample["mountPacing"]["latestCompletedPose"]["subject"] = deepcopy(subject)
            for event in events:
                if "subject" in event.get("data", {}): event["data"]["subject"] = deepcopy(subject)
        baseline["fieldAvailable"] = True
        evaluator = TestEvaluator(recipe())
        evaluator.install_measurements({MOUNT_PACING: {"contractVersion": 1}})
        evaluator.observe_record(dict(phase="setup", initialSnapshot=deepcopy(baseline),
            initialEvents=[], initialEventStartFrame=baseline["frame"]))
        bound = select_current_actor(baseline, subject)
        evaluator.observe_record(dict(phase="setup", action="bind", command="bind",
            snapshot=deepcopy(baseline), receipt=bound))
        evaluator.observe_record(dict(phase="observe", action="mount-pacing.arm", command="mount-pacing.arm",
            snapshot=deepcopy(baseline), receipt=dict(armed=True, prepared=True, acceptedProof=False,
                snapshot=deepcopy(baseline), mountPacing=reader)))
        meter = evaluator.measurements[MOUNT_PACING]
        for sample, events in samples:
            phase = "main" if len(meter.windows) == 1 else "recovery"
            released = meter.stage(phase+"-started")
            action = phase + ("-complete" if released else "-started")
            sample["fieldAvailable"] = True
            sample["mountPacing"]["latestCompletedPose"]["input"] = {
                "heldKeys": 0 if released or wrong_input else 0x10, "newKeys": 0}
            previous = evaluator.latest["frame"]
            row = dict(phase="observe", action=action, requestedGameFrames=1, completedGameFrames=1,
                nativeCycles=2, observedFieldFrames=1, samples=[sample], events=events,
                cycleIntervals=[dict(cpuNs=100, wallNs=100, completedGameFrame=previous),
                                dict(cpuNs=100, wallNs=100, completedGameFrame=sample["frame"])])
            evaluator.observe_record(row)
            if evaluator.failures: return evaluator
            if meter.main_complete and len(meter.windows) == 1:
                snapshot = deepcopy(evaluator.latest)
                evaluator.observe_record(dict(phase="observe", action="mount-pacing.recovery", command="mount-pacing.recovery",
                    snapshot=snapshot, receipt=dict(snapshot=deepcopy(snapshot), advancedFrames=0, acceptedProof=False)))
        snapshot = deepcopy(evaluator.latest)
        closed = deepcopy(snapshot["mountPacing"])
        closed["closed"] = True
        close_snapshot = deepcopy(snapshot)
        close_snapshot["mountPacing"] = closed
        evaluator.observe_record(dict(phase="observe", action="mount-pacing.close", command="mount-pacing.close",
            snapshot=snapshot, receipt=dict(closed=True, advancedFrames=0, acceptedProof=False,
                snapshot=close_snapshot, mountPacing=closed)))
        return evaluator

    def test_real_raw_evaluator_seven_then_recovery_and_close(self):
        evaluator = self.replay()
        self.assertEqual(evaluator.failures, [])
        result = evaluator.finish()
        self.assertEqual(result["state"], "passed", result)

    def test_real_raw_evaluator_rejects_neutral_game_input(self):
        evaluator = self.replay(wrong_input=True)
        self.assertTrue(evaluator.failures)
        self.assertIn("live held input", str(evaluator.failures))

    def test_typed_window_and_fixed_inputs(self):
        value = validate_test(recipe())
        self.assertEqual(measurement_inputs(value, Path("/does-not-exist")),
                         {MOUNT_PACING: {"contractVersion": 1}})

    def test_exact_actor_and_mode(self):
        for field, bad in (("species", 95), ("role", "WILD"), ("acquire", "spawn")):
            value = recipe()
            value["subjects"][0][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError): validate_test(value)
        for mode in ("normal", "observer-control"):
            value = recipe()
            value["mode"] = mode
            with self.subTest(mode=mode), self.assertRaises(ValueError): validate_test(value)

    def test_missing_duplicate_or_reordered_window_rejected(self):
        for actions in ((0, 2), (0, 1, 1, 2), (1, 0, 2), (0, 2, 1)):
            value = recipe()
            value["actions"] = [deepcopy(value["actions"][i]) for i in actions]
            for i, action in enumerate(value["actions"]): action["id"] = "action-" + str(i)
            with self.subTest(actions=actions), self.assertRaises(ValueError): validate_test(value)

    def test_taps_neutral_wrong_direction_and_missing_semantic_stop_rejected(self):
        for keys in ([], ["UP"], ["RIGHT", "B"]):
            value = recipe()
            value["actions"][1]["args"]["keys"] = keys
            with self.subTest(keys=keys), self.assertRaises(ValueError): validate_test(value)
        value = recipe()
        del value["actions"][1]["args"]["until"]
        with self.assertRaises(ValueError): validate_test(value)

    def test_no_guest_setup_inside_motion_window(self):
        value = recipe()
        value["actions"].insert(1, dict(id="change-party", op="party",
            args=dict(slot=0, species=155), budget=deepcopy(value["actions"][0]["budget"])))
        with self.assertRaises(ValueError): validate_test(value)

    def test_actions_cannot_outlive_measurement_declaration(self):
        value = recipe()
        value["measurements"] = []
        value["assertions"] = [dict(kind="actor-present", subject="rider")]
        with self.assertRaises(ValueError): validate_test(value)

    def test_stages_are_separate_and_typed(self):
        for stage in ("main-started", "main-complete", "recovery-started", "recovery-complete"):
            self.assertEqual(validate_predicate(dict(kind="measurement-stage", measurement=MOUNT_PACING,
                stage=stage), {"rider"})["stage"], stage)
        with self.assertRaises(ValueError):
            validate_predicate(dict(kind="measurement-stage", measurement=MOUNT_PACING, stage="done"), {"rider"})

    def test_reader_budget_cannot_be_bypassed(self):
        value = recipe()
        value["budgets"]["maxFrames"] = 1201
        with self.assertRaises(ValueError): validate_test(value)


if __name__ == "__main__":
    unittest.main()
