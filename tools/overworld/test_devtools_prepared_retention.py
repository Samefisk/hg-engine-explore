"""Real observer queue controls for the 369→4833 long prepared release."""
from collections import deque
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_observer import NativeObservation
from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure
from tools.overworld import test_devtools_prepared_boundary as boundary_tests


class PreparedRetentionTests(unittest.TestCase):
    def session(self, retain):
        s=DevtoolsSession.__new__(DevtoolsSession)
        observer=NativeObservation.__new__(NativeObservation)
        observer.session=s
        observer.pending=deque();observer.ready=deque();observer.finalizations={}
        observer.queued_finalizations={};observer.wait_probe=observer.main_loop_probe=None
        observer.player_step_count=0;observer.player_step_frame=None
        observer.events_dropped=0;observer.player_steps_admitted=0
        s.native_observation=observer;s.trace_events=[];s.trace_events_dropped=0
        s.completed_frames=737;s.runtime_health_failure=None;s.emu=object()
        s._check_runtime_health=lambda:None
        s._prepared_retained_events=[] if retain else None;s._prepared_retained_bytes=0
        def cycle(emu,frames,mask):
            s.completed_frames+=1
            # Exact failed span: 509 frames, 4464 observations, last4833.
            count=9 if s.completed_frames-737 <=392 else 8
            first=369+sum(9 if i<=392 else 8 for i in range(1,s.completed_frames-737))
            observer.pending.extend({"sequence":first+i+1} for i in range(count))
            observer.completed_frame(s.completed_frames)
        s.rt=SimpleNamespace(h=SimpleNamespace(cycle=cycle))
        return s

    def test_actual_lost_count_red_without_collector_and_dense_with_it(self):
        for retain in (False,True):
            s=self.session(retain);s.cycle(509)
            self.assertEqual(s.completed_frames,1246)
            self.assertEqual(s.native_observation.events_dropped,0 if retain else 368)
            if retain:
                self.assertEqual([e["data"]["sequence"] for e in s._prepared_retained_events],list(range(370,4834)))
                self.assertEqual(s.native_observation.drain(),[])

    def test_pending_unframed_events_and_real_loss_are_not_cleared(self):
        s=self.session(True);s.native_observation.pending.append({"sequence":370})
        s.native_observation.events_dropped=5
        s._retain_prepared_events()
        self.assertEqual(list(s.native_observation.pending),[{"sequence":370}])
        self.assertEqual(s.native_observation.events_dropped,5)

    def test_cap_fails_with_last_batch_retained(self):
        s=self.session(True);s._prepared_retained_events=[{}]*32768
        s.trace_events=[{"frame":737,"kind":"trace-status","data":{}}]
        with self.assertRaises(DevtoolsFailure) as caught:s._retain_prepared_events()
        self.assertEqual(caught.exception.code,"prepared-event-retention-limit")
        self.assertEqual(len(s._prepared_retained_events),32769)

    def test_byte_cap_and_mixed_batch_order(self):
        s=self.session(True)
        expected=[]
        for frame in (738,739):
            semantic={"frame":frame,"kind":"native","data":{"sequence":frame-737,"traceStream":1}}
            native={"frame":frame,"kind":"native-observation","data":{"sequence":frame-369}}
            s.trace_events=[semantic];s.native_observation.ready.append(native)
            expected.extend((semantic,native));s._retain_prepared_events()
        self.assertEqual(s._prepared_retained_events,expected)
        s._prepared_retained_bytes=32*1024*1024
        s.trace_events=[{"frame":740,"kind":"trace-status","data":{}}]
        with self.assertRaises(DevtoolsFailure) as caught:s._retain_prepared_events()
        self.assertEqual(caught.exception.code,"prepared-event-retention-limit")

    def test_all_drained_streams_have_watermarks(self):
        s,_=boundary_tests.PreparedBoundaryTests().fixture()
        s.trace_events.append({"frame":10,"kind":"native","data":{"sequence":7,"traceStream":2}})
        receipt=s.spawn({"role":"follower","slot":0})
        self.assertEqual(receipt["setupBoundary"]["traceSequences"],{"1":1,"2":7})
        self.assertIsNone(s._prepared_retained_events)

    def test_failure_keeps_events_and_clears_command_scope(self):
        s,_=boundary_tests.PreparedBoundaryTests().fixture()
        def fail(*args,**kwargs):
            s._retain_prepared_events()
            raise DevtoolsFailure("original-fault","keep this first fault")
        s._spawn_party_subject=fail
        with self.assertRaises(DevtoolsFailure) as caught:s.spawn({"role":"follower","slot":0})
        self.assertEqual(caught.exception.code,"original-fault")
        self.assertTrue(caught.exception.details["preparedRetainedEvents"])
        self.assertIsNone(s._prepared_retained_events)
        self.assertEqual(s._prepared_retained_bytes,0)


if __name__ == "__main__":unittest.main()
