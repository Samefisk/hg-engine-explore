"""The mounted pacing reader is opt-in, typed and never an acceptance receipt."""
from copy import deepcopy
from unittest.mock import patch
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_contract import validate_command
from tools.overworld.devtools_records import validate_recipe
from tools.overworld.test_devtools_walk_reset_command import subject


class MountPacingCommandTests(unittest.TestCase):
    def args(self):
        value = subject()
        value["role"] = "MOUNTED"
        return dict(subject=value, maxFrames=1200)

    def test_exact_mounted_binding_and_bounded_window(self):
        args = self.args()
        self.assertEqual(validate_command("mount-pacing.arm", args), args)
        for frames in (0, 1201, True, 1.5):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                validate_command("mount-pacing.arm", {**args, "maxFrames": frames})
        for key in args["subject"]:
            bad = deepcopy(args)
            del bad["subject"][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_command("mount-pacing.arm", bad)
        for role in ("WILD", "FOLLOWER", "SCRIPTED"):
            bad = deepcopy(args)
            bad["subject"]["role"] = role
            with self.subTest(role=role), self.assertRaises(ValueError):
                validate_command("mount-pacing.arm", bad)

    def test_no_address_or_mutation_arguments(self):
        for args in ({}, {**self.args(), "address": 0x02000000},
                     {**self.args(), "speed": 2}, {"subject": self.args()["subject"]}):
            with self.assertRaises(ValueError):
                validate_command("mount-pacing.arm", args)
        self.assertEqual(validate_command("mount-pacing.close", {}), {})
        with self.assertRaises(ValueError):
            validate_command("mount-pacing.close", {"force": True})
        self.assertEqual(validate_command("mount-pacing.calibrate", {}), {})
        with self.assertRaises(ValueError):
            validate_command("mount-pacing.calibrate", {"address": 0x02000000})

    def test_recorded_setup_cannot_claim_normal_trigger(self):
        for action in (dict(op="mount-pacing.arm", args=self.args()),
                       dict(op="mount-pacing.close", args={})):
            recipe = dict(schemaVersion=1, mode="prepared", actions=[action])
            self.assertEqual(validate_recipe(recipe), recipe)
            with self.assertRaises(ValueError):
                validate_recipe({**recipe, "mode": "normal"})

    def test_runtime_arms_once_and_closes_without_advancing(self):
        from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure
        class Reader:
            def __init__(self, session, selected, frames):
                self.session, self.selected, self.frames = session, selected, frames
                self.armed = self.closed = False
            def arm(self): self.armed = True
            def close(self): self.closed = True
            def result(self):
                return dict(armed=self.armed, closed=self.closed, acceptedProof=False,
                            guestMemoryWrites=0)
        selected = self.args()["subject"]
        current = dict(frame=10)
        session = SimpleNamespace(mount_pacing=None, prepared=False,
                                  snapshot=lambda **kwargs: current)
        with patch("tools.overworld.devtools_records.select_current_actor", return_value=selected), \
                patch("tools.overworld.devtools_mount_pacing_observer.NativeMountedPacingObserver", Reader):
            receipt = DevtoolsSession.mount_pacing_arm(session, self.args())
            self.assertEqual(receipt["snapshot"], current)
            self.assertFalse(receipt["acceptedProof"])
            self.assertTrue(session.prepared)
            self.assertEqual(session.mount_pacing.frames, 1200)
            with self.assertRaises(DevtoolsFailure):
                DevtoolsSession.mount_pacing_arm(session, self.args())
            closed = DevtoolsSession.mount_pacing_close(session)
            self.assertEqual(closed["advancedFrames"], 0)
            self.assertEqual(closed["snapshot"], current)
            self.assertTrue(closed["mountPacing"]["closed"])
            self.assertFalse(closed["acceptedProof"])
            with self.assertRaises(DevtoolsFailure):
                DevtoolsSession.mount_pacing_arm(session, self.args())


if __name__ == "__main__":
    unittest.main()
