"""Mounted crash observation uses the same bounded, prepared worker commands."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from tools.overworld.devtools_contract import validate_command
from tools.overworld.devtools_records import validate_recipe
from tools.overworld.test_devtools_walk_reset_command import subject


class CrashCommandTests(unittest.TestCase):
    def args(self):
        actor = subject(); actor.update(role='MOUNTED', species=155)
        return dict(subject=actor, maxFrames=600)

    def test_exact_actor_and_bounds(self):
        args = self.args()
        self.assertEqual(validate_command('crash.arm', args), args)
        for bound in (0, 601, True, 1.5):
            with self.assertRaises(ValueError):
                validate_command('crash.arm', dict(args, maxFrames=bound))
        for key in args['subject']:
            bad = deepcopy(args); del bad['subject'][key]
            with self.subTest(key=key), self.assertRaises(ValueError):validate_command('crash.arm', bad)
        for key, value in (('role', 'WILD'), ('role', 'FOLLOWER'), ('species', 56)):
            bad = deepcopy(args); bad['subject'][key] = value
            with self.assertRaises(ValueError):validate_command('crash.arm', bad)

    def test_prepared_and_no_raw_address(self):
        for op, args in (('crash.arm', self.args()), ('crash.close', {}), ('crash.calibrate', {})):
            self.assertEqual(validate_command(op, args), args)
            with self.assertRaises(ValueError):validate_command(op, dict(args, address=1))
            recipe = dict(schemaVersion=1, mode='prepared', actions=[dict(op=op, args=args)])
            self.assertEqual(validate_recipe(recipe), recipe)
            with self.assertRaises(ValueError):validate_recipe(dict(recipe, mode='normal'))

    def test_runtime_arm_once_and_close_without_advance(self):
        from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure
        class Reader:
            def __init__(self, *args):self.closed = False
            def arm(self):pass
            def close(self):self.closed = True
            def result(self):return dict(closed=self.closed, acceptedProof=False)
        endpoint = dict(frame=10)
        session = SimpleNamespace(crash_feedback=None, prepared=False, snapshot=lambda **kw:endpoint)
        with patch('tools.overworld.devtools_records.select_current_actor', return_value=self.args()['subject']), \
                patch('tools.overworld.devtools_mounted_crash_observer.NativeMountedCrashObserver', Reader):
            start = DevtoolsSession.crash_arm(session, self.args())
            self.assertFalse(start['acceptedProof']); self.assertTrue(session.prepared)
            with self.assertRaises(DevtoolsFailure):DevtoolsSession.crash_arm(session, self.args())
            end = DevtoolsSession.crash_close(session)
        self.assertEqual(end['advancedFrames'], 0)
        self.assertTrue(end['crashFeedback']['closed'])
        self.assertEqual(end['snapshot'], endpoint)

    def test_calibration_latches_terminal_guard_before_failure(self):
        from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure
        session = SimpleNamespace(crash_feedback=object())
        def fail(reader):
            self.assertTrue(session.crash_calibrated)
            raise ValueError('owned fault')
        with patch('tools.overworld.devtools_mounted_crash_control.calibrate_mounted_crash', side_effect=fail):
            with self.assertRaisesRegex(ValueError, 'owned fault'):
                DevtoolsSession.crash_calibrate(session)
            with self.assertRaises(DevtoolsFailure):
                DevtoolsSession.crash_calibrate(session)

    def test_terminal_guard_blocks_actual_cycle_entry(self):
        from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure
        session = SimpleNamespace(runtime_health_failure=None, emu=object(), crash_calibrated=True)
        # No emulator methods exist: reaching native execution would fail this
        # test instead of reporting the required terminal guard.
        with self.assertRaisesRegex(DevtoolsFailure, 'Crash calibration is terminal'):
            DevtoolsSession.cycle(session, 1)


if __name__ == '__main__':unittest.main()
