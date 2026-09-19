"""Prepared receipts exclude only already-published setup events."""
import unittest
from types import SimpleNamespace
from tools.overworld.devtools_runtime import DevtoolsFailure

from tools.overworld.test_devtools_runtime import NativeFollowerSetupTests
from tools.overworld.test_devtools_trace import NativeRing


class PreparedBoundaryTests(unittest.TestCase):
    def fixture(self):
        s, _, _, snapshot = NativeFollowerSetupTests.fixture(self)
        s.rt.EXECUTED_FRAME_COUNT = 30
        s.sample_error = None
        old_wait = s._wait_new_frame
        def wait(*args, **kwargs):
            value = old_wait(*args, **kwargs)
            value.update(frame=s.completed_frames, nativeCycle=29, prepared=True)
            return value
        s._wait_new_frame = wait
        ring = NativeRing()
        trace = ring.tap()
        trace.start()
        ring.emit()
        published = trace.sample(10)
        ring.emit()
        pending = trace.sample(0)
        s.semantic_trace, s.trace_events, s.trace_pending = trace, published, pending
        s.trace_events_dropped = 0
        native_events = [{"frame": 10, "kind": "native-observation", "data": {"sequence": 1}}]
        def drain():
            result = native_events[:]
            native_events.clear()
            return result
        s.native_observation = SimpleNamespace(drain=drain, hooks=SimpleNamespace(error=None))
        return s, snapshot

    def test_successful_follower_setup_retains_events_and_completed_watermark(self):
        s, _ = self.fixture()
        result = s.spawn({"role": "follower", "slot": 0})
        self.assertTrue(result["setupBoundary"]["eventsDrained"])
        self.assertEqual(result["setupBoundary"]["traceSequences"], {"1": 1})
        self.assertEqual([e["data"]["sequence"] for e in result["events"] if e["kind"] == "native"], [1])
        self.assertEqual(s.drain_events(), [])
        self.assertEqual(s.trace_pending[-1]["data"]["sequence"], 2)
        self.assertEqual(s.semantic_trace._next, 3)
        self.assertEqual(result["setupBoundary"]["frame"], result["snapshot"]["frame"])
        s.trace_observing, s.trace_request, s.trace_pending_dropped = True, None, 0
        s.completed_frames += 1
        s._complete_trace_boundary()
        self.assertEqual([e["data"]["sequence"] for e in s.drain_events() if e["kind"] == "native"], [2])
        self.assertEqual(s.drain_events(), [])

    def test_successful_party_edit_has_the_same_retained_boundary(self):
        s, snapshot = self.fixture()
        mon = s.party_snapshot()[0]
        mon.update(status=0, maxHp=10)
        snapshot["party"] = [mon]
        s.rt.actor_state = lambda *args: {"active": False}
        s.bridge.run = lambda *args, **kwargs: {"value": {"slot": 0}}
        receipt = s.party({"slot": 0, "status": 0})
        self.assertEqual(receipt["party"], [mon])
        self.assertEqual(receipt["setupBoundary"]["traceSequences"], {"1": 1})
        self.assertTrue(receipt["events"])
        self.assertEqual(s.drain_events(), [])

    def test_inactive_trace_is_explicit_and_fault_notice_is_retained(self):
        s, _ = self.fixture()
        s.semantic_trace.running = False
        fault = {"frame": 10, "kind": "trace-status", "data": {
            "code": "unread-events-lost", "coverageComplete": False, "count": 1}}
        s.trace_events.append(fault)
        receipt = s.spawn({"role": "follower", "slot": 0})
        # A stopped reader can still have completed events to retain. Its
        # drained stream must remain part of the excluded setup watermark.
        self.assertEqual(receipt["setupBoundary"]["traceSequences"], {"1": 1})
        self.assertIn(fault, receipt["events"])

    def test_failed_prepared_request_does_not_drain_events(self):
        s, _ = self.fixture()
        s.party_snapshot = lambda: [{"hp": 0, "isEgg": False, "species": 56}]
        before = list(s.trace_events)
        with self.assertRaisesRegex(DevtoolsFailure, "cannot be a follower"):
            s.spawn({"role": "follower", "slot": 0})
        self.assertEqual(s.trace_events, before)

    def test_failed_readback_or_observer_does_not_claim_a_boundary(self):
        for fault in ("readback", "observer"):
            s, snapshot = self.fixture()
            before = list(s.trace_events)
            if fault == "readback":
                s._wait_new_frame = lambda *args, **kwargs: {**snapshot, "frame": 9, "nativeCycle": 29}
            else:
                s.native_observation.hooks.error = "native reader failed"
            with self.subTest(fault=fault), self.assertRaises(DevtoolsFailure) as caught:
                s.spawn({"role": "follower", "slot": 0})
            retained = caught.exception.details["preparedRetainedEvents"]
            self.assertEqual(retained[:len(before)], before)
            self.assertEqual(s.trace_events, [])
            self.assertIsNone(s._prepared_retained_events)


if __name__ == "__main__":
    unittest.main()
