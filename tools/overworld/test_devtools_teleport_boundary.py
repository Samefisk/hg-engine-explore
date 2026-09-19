"""Native teleport completion must use the same drained boundary as other setup."""
from types import SimpleNamespace as NS
import unittest

from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure


class TeleportBoundaryTests(unittest.TestCase):
    def fixture(self):
        calls = []
        snapshot = dict(frame=727, nativeCycle=1923, prepared=True,
                        context=dict(mapId=33), player=dict(x=584, y=406, facing=0),
                        fieldControl=dict(taskPointer=0))
        receipt = dict(preparedOnly=True, boundary="native-field-command-trampoline",
                       calls=[{"routine": "create_field_task"}],
                       value={"constructor": {"tasks": []}})
        class Observer:
            closed = False
            def result(self):
                return {"eventCount": 1, "ownedEnvironmentFreeSeen": True, "closed": self.closed}
            def finish(self):
                self.closed = True
                return self.result()
        def wait(frame, predicate, **kwargs):
            calls.append("native-completion")
            self.assertTrue(predicate(snapshot))
            self.assertFalse(predicate({**snapshot, "fieldControl": {"taskPointer": 1}}))
            self.assertEqual(kwargs["native_limit"], 2400)
            return snapshot
        def drain(result):
            calls.append("drained-boundary")
            self.assertIs(result, receipt)
            self.assertIs(result["snapshot"], snapshot)
            return {**result, "events": [], "setupBoundary": {"eventsDrained": True}}
        session = NS(prepared=False, completed_frames=714,
            bridge=NS(run=lambda recipe: receipt), _wait_new_frame=wait,
            _new_script_warp_heap_free_observer=lambda _constructor: Observer(),
            _prepared_result_boundary=drain)
        return session, calls

    def test_drain_only_after_native_transition_completion(self):
        session, calls = self.fixture()
        result = DevtoolsSession.teleport(session, dict(map=33, x=584, z=406, facing=0))
        self.assertEqual(calls, ["native-completion", "drained-boundary"])
        self.assertTrue(session.prepared)
        self.assertTrue(result["setupBoundary"]["eventsDrained"])

    def test_failed_transition_cannot_publish_completed_boundary(self):
        session, calls = self.fixture()
        def fail(*args, **kwargs):
            raise DevtoolsFailure("transition-timeout", "native transition did not finish")
        session._wait_new_frame = fail
        with self.assertRaises(DevtoolsFailure):
            DevtoolsSession.teleport(session, dict(map=33, x=584, z=406, facing=0))
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
