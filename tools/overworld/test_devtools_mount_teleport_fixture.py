"""Teleport setup preserves all bytes outside three named lane fields."""
import unittest
from unittest.mock import patch

from tools.overworld.devtools_mount_teleport_fixture import (
    MountTeleportFixture, MountTeleportFixtureError, STATE_ADDRESS, STATE_BYTES,
)
from tools.overworld.test_devtools_mount_walk_fixture import session, ROOT


class TeleportFixtureTests(unittest.TestCase):
    def setUp(self):
        for module in ('devtools_mount_walk_fixture', 'devtools_mount_teleport_fixture'):
            auth = patch('tools.overworld.' + module + '.authenticate_mount',
                         return_value={'stateAddress': STATE_ADDRESS})
            auth.start()
            self.addCleanup(auth.stop)

    def test_modes_bounds_and_reconfiguration_touch_only_three_bytes(self):
        s = session()
        for mode in (6, 9, 10, 11):
            for time, pause in ((1, 0), (32, 255)):
                original = s.read(STATE_ADDRESS, STATE_BYTES)
                expected = bytearray(original)
                expected[20], expected[31], expected[32] = mode, time, pause
                before_writes = len(s.writes)
                receipt = MountTeleportFixture(s, s.subject, mode, time, pause).run()
                self.assertEqual(s.read(STATE_ADDRESS, STATE_BYTES), bytes(expected))
                self.assertEqual(len(s.writes) - before_writes, 3)
                self.assertEqual(receipt['changedOffsets'], [12, 23, 24])
                self.assertTrue(receipt['completed'])
                self.assertFalse(receipt['acceptedProof'])
                self.assertEqual(receipt['before']['clock'], receipt['after']['clock'])
                self.assertEqual(receipt['before']['readiness'], receipt['after']['readiness'])

    def test_invalid_fields_are_rejected_before_writes(self):
        for index, invalid in ((0, (1, 2, 7, True, '6')), (1, (0, 33, True, 1.5)),
                               (2, (-1, 256, False, '0'))):
            for value in invalid:
                s = session()
                args = [6, 7, 0]
                args[index] = value
                with self.assertRaises(MountTeleportFixtureError):
                    MountTeleportFixture(s, s.subject, *args)
                self.assertFalse(s.writes)

    def test_private_idle_binding_and_owner_guards(self):
        for fault in ('prepared', 'bridge', 'source', 'input', 'staged', 'anchor',
                      'binding', 'busy', 'unsupported-lane'):
            s = session()
            if fault == 'prepared': s.prepared = False
            elif fault == 'bridge': s.native_bridge_active = True
            elif fault == 'source': s.rom = ROOT / 'test.nds'
            elif fault == 'input': s.inputs['heldKeys'] = 1
            elif fault == 'staged': s.actor['stagedMovement']['idle'] = False
            elif fault == 'anchor': s.actor['engineIdentity']['anchorInCurrentManager'] = False
            elif fault == 'binding': s.put(STATE_ADDRESS + 80, b'\x00')
            elif fault == 'busy': s.put(STATE_ADDRESS + 148, b'\x01')
            else: s.put(STATE_ADDRESS + 20, b'\x02')
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                MountTeleportFixture(s, s.subject, 6, 7, 0).run()
            self.assertFalse(s.writes)

    def test_partial_write_failure_restores_with_receipt(self):
        s = session()
        original, write = s.read(STATE_ADDRESS, STATE_BYTES), s.write
        def failed(address, data):
            write(address, data)
            if len(s.writes) == 2:
                raise ValueError('partial write')
        s.write = failed
        with self.assertRaises(ValueError) as caught:
            MountTeleportFixture(s, s.subject, 10, 3, 0).run()
        self.assertEqual(s.read(STATE_ADDRESS, STATE_BYTES), original)
        self.assertIsNotNone(caught.exception.receipt['restoredOnError'])
        self.assertFalse(s.aborted)

    def test_unverified_rollback_aborts_private_session(self):
        for fault in ('clock', 'owner', 'unrelated-byte'):
            s = session()
            write = s.write
            def changed(address, data):
                write(address, data)
                if len(s.writes) == 1:
                    if fault == 'clock': s.rt.EXECUTED_FRAME_COUNT += 1
                    elif fault == 'owner': s.native_heap_generation += 1
                    else: s.put(STATE_ADDRESS + 10, b'\xff')
            s.write = changed
            with self.subTest(fault=fault), self.assertRaises(MountTeleportFixtureError) as caught:
                MountTeleportFixture(s, s.subject, 11, 3, 0).run()
            self.assertTrue(caught.exception.fatal)
            self.assertEqual(s.aborted, [caught.exception])

    def test_single_use_and_package_reauthentication(self):
        s = session()
        fixture = MountTeleportFixture(s, s.subject, 9, 7, 0)
        fixture.run()
        with self.assertRaises(MountTeleportFixtureError): fixture.run()
        s = session()
        fixture = MountTeleportFixture(s, s.subject, 6, 7, 0)
        with patch('tools.overworld.devtools_mount_teleport_fixture.authenticate_mount',
                   return_value={'stateAddress': 0}):
            with self.assertRaises(MountTeleportFixtureError): fixture.run()
        self.assertFalse(s.writes)


if __name__ == '__main__':
    unittest.main()
