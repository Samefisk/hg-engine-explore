"""Wild clear observations use one typed, bounded shared-session command."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from tools.overworld.devtools_contract import validate_command
from tools.overworld.devtools_records import validate_recipe
from tools.overworld.test_devtools_walk_reset_command import subject


class WildWalkCommandTests(unittest.TestCase):
    def args(self):
        selected = subject()
        selected.update(role="WILD", species=19)
        return dict(subject=selected, maxFrames=1200)

    def test_exact_subject_and_bound(self):
        args = self.args()
        self.assertEqual(validate_command("wild-walk.arm", args), args)
        for frames in (0, 1201, True, 1.5):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                validate_command("wild-walk.arm", {**args, "maxFrames": frames})
        for key in args["subject"]:
            bad = deepcopy(args)
            del bad["subject"][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_command("wild-walk.arm", bad)
        for key, value in (("role", "MOUNTED"), ("role", "FOLLOWER"), ("species", 165)):
            bad = deepcopy(args)
            bad["subject"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_command("wild-walk.arm", bad)

    def test_no_arbitrary_memory_or_normal_trigger_claim(self):
        for op, args in (("wild-walk.arm", self.args()), ("wild-walk.close", {}),
                         ("wild-walk.calibrate", {})):
            self.assertEqual(validate_command(op, args), args)
            with self.assertRaises(ValueError):
                validate_command(op, {**args, "address": 0x02000000})
            recipe = dict(schemaVersion=1, mode="prepared", actions=[dict(op=op, args=args)])
            self.assertEqual(validate_recipe(recipe), recipe)
            with self.assertRaises(ValueError):
                validate_recipe({**recipe, "mode": "normal"})

    def test_runtime_arms_once_and_closes_without_advance(self):
        from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure
        class Reader:
            def __init__(self, session, selected, frames):
                self.frames = frames
                self.armed = self.closed = False
            def arm(self): self.armed = True
            def close(self): self.closed = True
            def result(self): return dict(armed=self.armed, closed=self.closed, acceptedProof=False)
        current = dict(frame=10)
        session = SimpleNamespace(wild_walk=None, prepared=False, snapshot=lambda **kw: current)
        with patch("tools.overworld.devtools_records.select_current_actor", return_value=self.args()["subject"]), \
                patch("tools.overworld.devtools_wild_walk_observer.NativeWildWalkObserver", Reader):
            receipt = DevtoolsSession.wild_walk_arm(session, self.args())
            self.assertTrue(session.prepared)
            self.assertFalse(receipt["acceptedProof"])
            self.assertEqual(session.wild_walk.frames, 1200)
            with self.assertRaises(DevtoolsFailure):
                DevtoolsSession.wild_walk_arm(session, self.args())
            closed = DevtoolsSession.wild_walk_close(session)
            self.assertEqual(closed["advancedFrames"], 0)
            self.assertEqual(closed["snapshot"], current)
            self.assertTrue(closed["wildWalk"]["closed"])
            self.assertFalse(closed["acceptedProof"])


if __name__ == "__main__": unittest.main()
