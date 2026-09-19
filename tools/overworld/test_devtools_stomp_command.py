"""Stomp observation uses bounded shared commands, never raw memory APIs."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from tools.overworld.devtools_contract import validate_command
from tools.overworld.devtools_records import validate_recipe
from tools.overworld.test_devtools_walk_reset_command import subject


class StompCommandTests(unittest.TestCase):
    def args(self):
        actor = subject()
        actor.update(role="MOUNTED", species=155)
        return dict(subject=actor, maxFrames=3000)

    def test_exact_subject_and_frame_bound(self):
        args = self.args()
        self.assertEqual(validate_command("stomp.arm", args), args)
        for frames in (0, 3001, True, 1.5):
            with self.assertRaises(ValueError):
                validate_command("stomp.arm", {**args, "maxFrames": frames})
        for key in args["subject"]:
            bad = deepcopy(args)
            del bad["subject"][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_command("stomp.arm", bad)
        for key, value in (("role", "WILD"), ("role", "FOLLOWER"), ("species", 56)):
            bad = deepcopy(args)
            bad["subject"][key] = value
            with self.assertRaises(ValueError):
                validate_command("stomp.arm", bad)

    def test_prepared_only_and_no_raw_addresses(self):
        for op, args in (("stomp.arm", self.args()), ("stomp.close", {}), ("stomp.calibrate", {})):
            self.assertEqual(validate_command(op, args), args)
            with self.assertRaises(ValueError):
                validate_command(op, {**args, "address": 1})
            recipe = dict(schemaVersion=1, mode="prepared", actions=[dict(op=op, args=args)])
            self.assertEqual(validate_recipe(recipe), recipe)
            with self.assertRaises(ValueError):
                validate_recipe({**recipe, "mode": "normal"})

    def test_arm_once_and_close_without_advancing_game(self):
        from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure

        class Reader:
            def __init__(self, *args): self.closed = False
            def arm(self): pass
            def close(self): self.closed = True
            def result(self): return dict(closed=self.closed, acceptedProof=False)

        endpoint = dict(frame=10)
        session = SimpleNamespace(stomp_feedback=None, prepared=False, snapshot=lambda **kw: endpoint)
        with patch("tools.overworld.devtools_records.select_current_actor", return_value=self.args()["subject"]), \
                patch("tools.overworld.devtools_stomp_observer.NativeStompObserver", Reader):
            start = DevtoolsSession.stomp_arm(session, self.args())
            self.assertFalse(start["acceptedProof"])
            with self.assertRaises(DevtoolsFailure): DevtoolsSession.stomp_arm(session, self.args())
            end = DevtoolsSession.stomp_close(session)
        self.assertEqual(end["advancedFrames"], 0)
        self.assertTrue(end["stompFeedback"]["closed"])
        self.assertEqual(end["snapshot"], endpoint)

    def test_calibration_sets_terminal_guard_even_on_failure(self):
        from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure
        session = SimpleNamespace(stomp_feedback=object())
        with patch("tools.overworld.devtools_stomp_control.calibrate_stomp_policy", side_effect=ValueError("fault")):
            with self.assertRaisesRegex(ValueError, "fault"):
                DevtoolsSession.stomp_calibrate(session)
            self.assertTrue(session.stomp_calibrated)
            with self.assertRaises(DevtoolsFailure): DevtoolsSession.stomp_calibrate(session)


if __name__ == "__main__": unittest.main()
