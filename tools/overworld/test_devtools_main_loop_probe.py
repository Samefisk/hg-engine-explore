"""Host-only checks for the bounded post-mandatory-wait loop reader."""
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_main_loop_probe import MainLoopProbe, RETURN_SITE, SYSTEM
from tools.overworld import test_devtools_wait_probe


class MainLoopProbeTests(unittest.TestCase):
    def fixture(self):
        wait, callbacks, state, session = test_devtools_wait_probe.WaitProbeTests().fixture()
        session.emu.memory.register_arm9.r4 = SYSTEM
        return callbacks, state, session, wait.clock

    def test_post_wait_rows_report_loop_clock_and_resettable_counter(self):
        callbacks, state, session, clock = self.fixture()
        state.update(actor=885, native=10, counter=3)
        native = lambda: dict(actorFrame=state["actor"], nativeCycle=state["native"])
        probe = MainLoopProbe(session, SimpleNamespace(
            add=lambda address, callback: callbacks.__setitem__(address, callback) or address,
            remove=lambda token: callbacks.pop(token, None)),
            clock, native)

        # Run the complete bounded prefix.  The counter intentionally resets
        # between the first two loops, as the stock code does after E22.
        for frame in range(770, 1531):
            probe.completed_frame(frame)
            callbacks[RETURN_SITE]()
            if frame == 770:
                state["counter"] = 2
            state["actor"] += 1
            state["native"] += 37
        rows = probe.completed_frame(1531)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["loopId"], 761)
        self.assertEqual(rows[0]["previousLoopId"], 760)
        self.assertEqual(rows[0]["returnSite"], RETURN_SITE)
        self.assertEqual(rows[0]["frameCounter"], 2)
        self.assertEqual(rows[0]["intervalFromPrevious"]["nativeCycles"], 37)
        self.assertNotIn("frameCounter", rows[0]["intervalFromPrevious"])
        self.assertEqual(probe.result()["completedLoops"], 761)
        self.assertFalse(callbacks)
        self.assertIsNone(probe.close()["failure"])

    def test_missing_and_duplicate_returns_latch_and_detach(self):
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate):
                callbacks, state, session, clock = self.fixture()
                hooks = SimpleNamespace(
                    add=lambda address, callback: callbacks.__setitem__(address, callback) or address,
                    remove=lambda token: callbacks.pop(token, None))
                probe = MainLoopProbe(session, hooks, clock,
                                      lambda: dict(actorFrame=1, nativeCycle=1))
                probe.completed_frame(770)
                if duplicate:
                    callbacks[RETURN_SITE]()
                    callbacks[RETURN_SITE]()
                with self.assertRaisesRegex(ValueError, "missing or duplicate"):
                    probe.completed_frame(771)
                self.assertIn("missing or duplicate", probe.result()["failure"])
                self.assertFalse(callbacks)
                probe.close()

    def test_nonbaseline_and_bad_identity_are_rejected_before_sampling(self):
        callbacks, state, session, clock = self.fixture()
        session.spawn_cost_probe.mode = "omit-spawn-details"
        with self.assertRaisesRegex(ValueError, "requires diagnostic baseline"):
            MainLoopProbe(session, SimpleNamespace(add=lambda *_: None, remove=lambda *_: None),
                          clock, lambda: dict(actorFrame=1, nativeCycle=1))

        session.spawn_cost_probe.mode = "baseline"
        hooks = SimpleNamespace(
            add=lambda address, callback: callbacks.__setitem__(address, callback) or address,
            remove=lambda token: callbacks.pop(token, None))
        probe = MainLoopProbe(session, hooks, clock,
                              lambda: dict(actorFrame=1, nativeCycle=1))
        probe.completed_frame(769)
        session.packaged_code = lambda address, size: bytes(size)
        with self.assertRaisesRegex(ValueError, "code identity"):
            probe.completed_frame(770)
        self.assertFalse(callbacks)
        probe.close()


if __name__ == "__main__":
    unittest.main()
