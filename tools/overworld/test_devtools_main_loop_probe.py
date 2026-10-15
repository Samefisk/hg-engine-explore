"""Host-only checks for the bounded post-mandatory-wait loop reader."""
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_main_loop_probe import ENTRY_SITE, MainLoopProbe, RETURN_SITE, SYSTEM
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

    def wait_probe(self):
        callbacks, state, session, clock = self.fixture()
        hooks = SimpleNamespace(
            add=lambda address, callback: callbacks.__setitem__(address, callback) or address,
            remove=lambda token: callbacks.pop(token, None))
        probe = MainLoopProbe(session, hooks, clock, lambda: dict(actorFrame=1, nativeCycle=1))
        return probe, callbacks, session

    def test_entry_and_return_add_the_loop_wait_envelope(self):
        # The fixture clock advances 10 ticks per read, so entry and return
        # one read apart carry a 10-tick wait; an unpaired old-style row has none.
        probe, callbacks, session = self.wait_probe()
        self.assertEqual(ENTRY_SITE, 0x02000E1E)
        self.assertEqual(RETURN_SITE, 0x02000E22)
        probe.completed_frame(770)
        callbacks[ENTRY_SITE]()
        callbacks[RETURN_SITE]()
        rows = probe.completed_frame(771)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["waitArm9Ticks"], 10)
        self.assertEqual(rows[0]["waitEntrySite"], ENTRY_SITE)
        self.assertEqual(rows[0]["waitEntryArm9Timestamp"] + 10,
                         rows[0]["guestClock"]["arm9Timestamp"])
        callbacks[RETURN_SITE]()
        old = probe.completed_frame(772)[0]
        self.assertNotIn("waitArm9Ticks", old)
        self.assertNotIn("waitEntryArm9Timestamp", old)
        self.assertEqual(probe.result()["guestMemoryWrites"], 0)
        self.assertEqual(probe.result()["entrySite"], ENTRY_SITE)
        probe.close()
        self.assertFalse(callbacks)

    def test_entry_without_return_or_with_duplicate_entry_fails_closed(self):
        for order, reason in (((ENTRY_SITE,), "no matching return"),
                              ((ENTRY_SITE, ENTRY_SITE, RETURN_SITE), "duplicate or out-of-order"),
                              ((RETURN_SITE, ENTRY_SITE), "duplicate or out-of-order")):
            with self.subTest(order=order):
                probe, callbacks, session = self.wait_probe()
                probe.completed_frame(770)
                with self.assertRaisesRegex(ValueError, reason):
                    for site in order:
                        callbacks[site]()
                    probe.completed_frame(771)
                self.assertIn(reason, probe.result()["failure"])
                probe.close()
                self.assertFalse(callbacks)

    def test_entry_requires_system_owner_and_wait_arguments(self):
        for register, value in (("r4", 0), ("r0", 2), ("r1", 0)):
            with self.subTest(register=register):
                probe, callbacks, session = self.wait_probe()
                probe.completed_frame(770)
                setattr(session.emu.memory.register_arm9, register, value)
                with self.assertRaises(ValueError):
                    callbacks[ENTRY_SITE]()
                self.assertTrue(probe.result()["failure"])
                probe.close()
                self.assertFalse(callbacks)

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
