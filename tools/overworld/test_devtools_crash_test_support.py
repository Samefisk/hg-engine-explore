"""Shared raw-step replay using the retained diagnostic Crash fixture."""
from copy import deepcopy
import unittest

from . import devtools_crash_test_support as support
from .test_devtools_mounted_crash_measurement import fixture


class CrashTestSupportTests(unittest.TestCase):
    def bootstrap(self, alter=None):
        snapshots, _ = fixture()
        first = snapshots[0]
        # Synthetic pre-arm endpoint tests adapter mechanics only. The saved
        # game stream begins at783 and does not contain the real arm782 receipt.
        before = deepcopy(first)
        before["frame"] -= 1
        before["nativeCycle"] -= 1
        before["actorFrame"] -= 1
        r = deepcopy(first["crashFeedback"]); r["latestCompleted"] = None
        receipt = dict(armed=True, prepared=True, acceptedProof=False,
                       snapshot=before, crashFeedback=r)
        meter = support.create_meter(support.CONTRACT_INPUT, 120)
        support.feed_command(meter, "crash.arm", receipt, before, subject=r["subject"])
        self.assertIsNone(meter.initial)
        request = dict(op="step", startFrame=before["frame"], args=dict(frames=1, keys=[]))
        samples, events = [first], []
        if alter: alter(request, samples, events)
        support.feed_chunk(meter, request,
            dict(requestedGameFrames=1, completedGameFrames=1, observedFieldFrames=1), samples, events)
        return meter, first

    def test_synthetic_pending_arm_waits_for_real_first_queue_without_credit(self):
        meter, first = self.bootstrap()
        self.assertEqual(meter.initial, first)
        self.assertEqual(meter.frames, 0)
        self.assertEqual(meter.commands, [])
        self.assertFalse(meter.result()["acceptedProof"])

    def test_bootstrap_rejects_input_motion_and_wrong_subject(self):
        def input_fault(request, samples, events): request["args"]["keys"] = ["UP"]
        def motion_fault(request, samples, events):
            events.append(dict(frame=samples[0]["frame"], kind="native", data=dict(event="MOTION_STARTED")))
        def actor_fault(request, samples, events):
            subject = samples[0]["crashFeedback"]["subject"]
            next(a for a in samples[0]["actors"] if a["handle"] == subject["handle"])["species"] = 19
        for mutate in (input_fault, motion_fault, actor_fault):
            with self.assertRaises(ValueError): self.bootstrap(mutate)

    def test_bootstrap_scopes_motion_but_preserves_other_actor_trace_continuity(self):
        def motion(bound=False, gap=False):
            def alter(request, samples, events):
                handle = samples[0]["crashFeedback"]["subject"]["handle"]["value"]
                for sequence in (12, 14 if gap else 13):
                    events.append(dict(frame=samples[0]["frame"], kind="native",
                        data=dict(event="MOTION_STARTED", actorHandle=handle if bound else handle + 1,
                                  traceStream=1, sequence=sequence)))
            return alter
        meter, first = self.bootstrap(motion())
        self.assertEqual(meter.initial, first)
        self.assertEqual(meter.streams[1], 13)
        self.assertEqual(meter.frames, 0)
        with self.assertRaisesRegex(ValueError, "contains motion or crash"):
            self.bootstrap(motion(bound=True))
        with self.assertRaisesRegex(ValueError, "actor trace gap"):
            self.bootstrap(motion(gap=True))

    def test_typed_contract_is_bounded_and_calibration_is_not_gameplay(self):
        subject = dict(id="cyndaquil", species=155, role="MOUNTED", acquire="existing")
        spec = dict(kind=support.KIND, subject="cyndaquil")
        self.assertEqual(support.validate_measurement(spec, "prepared", 120, [subject]), spec)
        for mode, bound in (("normal", 120), ("observer-control", 120), ("prepared", 601), ("prepared", True)):
            with self.assertRaises(ValueError): support.validate_measurement(spec, mode, bound, [subject])
        for op, args in (("crash.calibrate", {}), ("crash.close", {"subject": "cyndaquil"}),
                         ("crash.arm", {"subject": "other"})):
            with self.assertRaises(ValueError):
                support.validate_action(dict(op=op, args=args), "actions", "prepared", {"cyndaquil"})
        for inputs in (None, {}, {"contractVersion": True}, {"contractVersion": 2}):
            with self.assertRaises(ValueError): support.create_meter(inputs, 120)

    def replay(self, mutate=None):
        snapshots, events = fixture()
        meter = support.create_meter(support.CONTRACT_INPUT, 120)
        first = snapshots[0]
        receipt = dict(snapshot=deepcopy(first), crashFeedback=deepcopy(first["crashFeedback"]),
            advancedFrames=0, acceptedProof=False)
        support.feed_command(meter, "crash.arm", receipt, first,
            subject=first["crashFeedback"]["subject"])
        offset = 1
        for n, keys in ((16, ["UP"]), (32, []), (8, ["RIGHT"]), (8, [])):
            chunk = snapshots[offset:offset+n]
            request = dict(op="step", startFrame=snapshots[offset-1]["frame"], args=dict(frames=n, keys=keys))
            raw = [e for sample in chunk for e in events[sample["frame"]]]
            if mutate: mutate(request, chunk, raw)
            support.feed_chunk(meter, request,
                dict(requestedGameFrames=n, completedGameFrames=n, observedFieldFrames=n), chunk, raw)
            if meter.failures: return meter
            offset += n
        last = snapshots[-1]
        # Host-only close fixture; never a claimed live cleanup receipt.
        closed = dict(snapshot=deepcopy(last), crashFeedback=dict(last["crashFeedback"], closed=True),
            closed=True, advancedFrames=0, acceptedProof=False)
        support.feed_command(meter, "crash.close", closed, last)
        return meter

    def test_real_retained_chunks_preserve_all_six_rows(self):
        result = self.replay().finish()
        self.assertTrue(result["passed"], result)
        self.assertFalse(result["acceptedProof"])
        self.assertEqual([(claim, values[0]["name"]) for claim, values in result["proofEvidence"].items()],
                         list(support.MEASUREMENTS))

    def test_missing_event_and_wrong_input_are_not_repaired(self):
        def missing(request, samples, events):
            if events: events.pop(0)
        self.assertTrue(self.replay(missing).failures)
        def wrong(request, samples, events):
            request["args"]["keys"] = ["RIGHT"]
        self.assertTrue(self.replay(wrong).failures)

    def test_chunk_rejects_missing_samples_and_unexpanded_event(self):
        for alter in (lambda request, samples, events: samples.pop(),
                      lambda request, samples, events: events.append(dict(frame=samples[0]["frame"], data={"detailsOmitted": True}))):
            with self.assertRaisesRegex(ValueError, "Crash raw"):
                self.replay(alter)


if __name__ == "__main__": unittest.main()
