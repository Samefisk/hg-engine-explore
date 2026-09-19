"""Direction input is bounded, exact-subject prepared control, not gameplay proof."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_contract import validate_command
from tools.overworld.devtools_records import validate_recipe
from tools.overworld.test_devtools_walk_reset_command import subject


class WalkIntentCommandTests(unittest.TestCase):
    def test_exact_wild_subject_and_bounded_direction_window(self):
        args = dict(subject=subject(), direction=4, maxFrames=600)
        self.assertEqual(validate_command("walk-intent.arm", args), args)
        for direction in range(8):
            self.assertEqual(validate_command("walk-intent.arm", {**args, "direction": direction})["direction"], direction)
        for field, values in (("direction", (-1, 8, True)),
                              ("maxFrames", (0, 601, True))):
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    validate_command("walk-intent.arm", {**args, field: value})
        for key in subject():
            bad = deepcopy(args)
            del bad["subject"][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_command("walk-intent.arm", bad)
        for role in ("MOUNTED", "FOLLOWER"):
            bad = deepcopy(args)
            bad["subject"]["role"] = role
            with self.subTest(role=role), self.assertRaises(ValueError):
                validate_command("walk-intent.arm", bad)

    def test_no_unbounded_or_address_commands(self):
        args = dict(subject=subject(), direction=4, maxFrames=20)
        for bad in ({}, {**args, "address": 0x02000000}, {**args, "speed": 2}):
            with self.assertRaises(ValueError):
                validate_command("walk-intent.arm", bad)
        self.assertEqual(validate_command("walk-intent.close", {}), {})
        with self.assertRaises(ValueError):
            validate_command("walk-intent.close", {"force": True})

    def test_both_operations_mark_recipes_prepared(self):
        for action in (dict(op="walk-intent.arm", args=dict(subject=subject(), direction=7, maxFrames=100)),
                       dict(op="walk-intent.close", args={})):
            recipe = dict(schemaVersion=1, mode="prepared", actions=[action])
            self.assertEqual(validate_recipe(recipe), recipe)
            with self.assertRaises(ValueError):
                validate_recipe({**recipe, "mode": "normal"})


if __name__ == "__main__":
    unittest.main()
