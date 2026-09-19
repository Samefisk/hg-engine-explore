"""Same native reader over real fake-memory writes; these are host controls."""
from copy import deepcopy
import tempfile
import unittest

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_policy_control import NativeWalkPolicyReadControl, WalkPolicyControlError
from tools.overworld import test_devtools_observer as observer_fixture


class WalkPolicyReadControlTests(unittest.TestCase):
    def fixture(self, directory):
        f = observer_fixture.Fixture(directory)
        observer_fixture.WalkChainPolicyObserverTests.prepare_commit(f)
        f.native_bridge_active = False
        f.actor.update(identityVerified=True, presentationAttached=True,
                       sourceIdentity=dict(object=0x02210000),
                       engineIdentity=dict(pointer=0x02210000, current_manager=3, object_manager=3, manager_index=0))
        f._snapshot = lambda *args, **kwargs: dict(frame=12, actors=[deepcopy(f.actor)],
            context=dict(fieldEpoch=2, mapGeneration=3, mapId=34))
        f.write = f.put
        f.fatals = []
        def fatal(error):
            f.fatals.append(str(error))
            raise error
        f.abort_native_control = fatal
        c = NativeWalkPolicyReadControl(f, select_current_actor(f._snapshot(), f.actor))
        f.walk_policy_control = c
        c.arm()
        return f, c

    def test_installed_commit_reader_gets_bad_counter_then_clean_normal_event(self):
        with tempfile.TemporaryDirectory() as directory:
            f, c = self.fixture(directory)
            before = deepcopy(f.memory)
            f.enter("walk-policy", r0=0x02220000)
            self.assertIsNone(f.hooks.error)
            receipt = c.result()["receipt"]
            self.assertEqual(receipt["clean"], receipt["restored"])
            self.assertEqual(receipt["bad"]["policy"]["counter"], 2)
            self.assertEqual(receipt["clean"]["policy"]["counter"], 1)
            self.assertEqual(before, f.memory)
            f.returned(1); f.observer.completed_frame(12)
            event = f.observer.drain()[0]["data"]
            self.assertEqual(event["policyBefore"], receipt["clean"]["policy"])
            self.assertEqual(event["policyBeforeHex"], receipt["clean"]["rawHex"])
            self.assertEqual(c.state, "complete")
            f.enter("walk-policy", r0=0x02220000); f.returned(1)
            self.assertEqual(c.result()["receipt"], receipt)
            self.assertFalse(c.result()["cleanupPending"])
            self.assertEqual(f.fatals, [])

    def test_bad_read_raises_but_restores_without_erasing_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            f, c = self.fixture(directory)
            actual = f.observer._commit_policy
            calls = []
            def reader(slot):
                value = actual(slot); calls.append(value)
                if len(calls) == 2:
                    value[1]["speed"] += 1
                return value
            f.observer._commit_policy = reader
            original = f.read(0x022005BC, 32)
            f.enter("walk-policy", r0=0x02220000)
            self.assertEqual(f.read(0x022005BC, 32), original)
            self.assertEqual(len(calls), 3)
            self.assertEqual(c.state, "failed")
            self.assertIn("only changed counter", c.failure)
            self.assertEqual(f.fatals, [])

    def test_failed_restore_is_fatal_and_retains_pending_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            f, c = self.fixture(directory)
            writes = []
            def write(address, data):
                writes.append((address, data))
                if len(writes) == 2: raise RuntimeError("restore blocked")
                f.put(address, data)
            f.write = write
            f.enter("walk-policy", r0=0x02220000)
            self.assertEqual(f.fatals, ["restore blocked"])
            self.assertTrue(c.cleanup_pending)
            self.assertEqual(c.state, "failed")

    def test_owner_change_after_write_still_restores_then_fatally_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            f, c = self.fixture(directory)
            original = f.read(0x022005BC, 32)
            def write(address, data):
                f.put(address, data)
                f.actor["authorityGeneration"] += 1
            f.write = write
            f.enter("walk-policy", r0=0x02220000)
            self.assertEqual(f.read(0x022005BC, 32), original)
            self.assertEqual(len(f.fatals), 1)
            self.assertEqual(c.state, "failed")

    def test_unrelated_slot_does_not_consume_and_changed_bound_owner_cannot_write(self):
        with tempfile.TemporaryDirectory() as directory:
            f, c = self.fixture(directory)
            value = f.observer._commit_policy(1)
            self.assertEqual(c.capture(f.observer, 1, lambda: value), value)
            self.assertEqual(c.state, "armed")
            f.actor["engineIdentity"]["pointer"] += 4
            before = deepcopy(f.memory)
            f.enter("walk-policy", r0=0x02220000)
            self.assertEqual(f.memory, before)
            self.assertEqual(c.state, "failed")
            self.assertFalse(c.cleanup_pending)

    def test_counter_overflow_never_writes_and_clock_change_is_fatal_after_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            f, c = self.fixture(directory)
            f.put(f.observer._commit_policy_address(c.subject["handle"]["slot"]) + 1, b"\xff")
            before = deepcopy(f.memory)
            f.enter("walk-policy", r0=0x02220000)
            self.assertEqual(f.memory, before)
            self.assertIn("overflow", c.failure)
        with tempfile.TemporaryDirectory() as directory:
            f, c = self.fixture(directory)
            before = deepcopy(f.memory)
            def write(address, data):
                f.put(address, data)
                f.rt.EXECUTED_FRAME_COUNT += 1
            f.write = write
            f.enter("walk-policy", r0=0x02220000)
            self.assertEqual(f.memory, before)
            self.assertEqual(len(f.fatals), 1)
            self.assertIn("execution boundary", c.failure)


if __name__ == "__main__":
    unittest.main()
