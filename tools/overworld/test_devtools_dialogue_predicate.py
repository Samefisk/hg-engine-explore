"""Same-boundary dialogue waits cannot use old or unowned input state."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_movement_predicates import (
    check_movement_predicate as check, validate_movement_predicate as validate,
)


class DialoguePredicateTests(unittest.TestCase):
    def snapshot(self):
        return {"frame": 12, "observationBoundary": "main-task-queue-completion",
                "fieldControl": {"fieldPointer": 0x02200000},
                "dialogue": {"frame": 12, "boundary": "main-task-queue-completion",
                             "fieldPointer": 0x02200000, "known": True,
                             "state": "page-wait"}}

    def test_exact_state_and_no_mutation(self):
        value = self.snapshot()
        before = deepcopy(value)
        self.assertTrue(check({"kind": "dialogue-state", "state": "page-wait"}, value))
        self.assertFalse(check({"kind": "dialogue-state", "state": "yes-no-ready"}, value))
        self.assertEqual(value, before)

    def test_unknown_cannot_be_ready(self):
        value = self.snapshot()
        value["dialogue"]["known"] = False
        self.assertFalse(check({"kind": "dialogue-state", "state": "page-wait"}, value))

    def test_missing_stale_or_foreign_field_fails(self):
        predicate = {"kind": "dialogue-state", "state": "page-wait"}
        for key, changed in (("frame", 11), ("frame", True),
                             ("boundary", "paused"), ("fieldPointer", 0x02201000)):
            with self.subTest(key=key, changed=changed):
                value = self.snapshot()
                value["dialogue"][key] = changed
                with self.assertRaises(ValueError):
                    check(predicate, value)
        value = self.snapshot()
        del value["dialogue"]
        with self.assertRaises(ValueError):
            check(predicate, value)

    def test_only_declared_states_and_fields(self):
        for state in ("idle", "busy", "printing", "page-wait", "yes-no-ready", "script-button-wait"):
            self.assertEqual(validate({"kind": "dialogue-state", "state": state})["state"], state)
        for invalid in ({"kind": "dialogue-state", "state": "unknown"},
                        {"kind": "dialogue-state", "state": True},
                        {"kind": "dialogue-state", "state": "page-wait", "address": 123}):
            with self.assertRaises(ValueError):
                validate(invalid)


if __name__ == "__main__":
    unittest.main()
