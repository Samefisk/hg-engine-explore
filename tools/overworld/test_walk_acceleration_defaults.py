"""Checks that Walk acceleration uses small, explicit frame steps."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data/overworld_behavior_profiles.json"

# Profiles may opt into another acceleration amount only when named here.
WALK_ACCELERATION_OPT_INS = {"runner": 2}


class WalkAccelerationDefaultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text())
        cls.profiles = {
            profile["id"]: profile for profile in cls.catalog["profiles"]
        }

    def test_root_acceleration_removes_one_frame(self):
        root = self.profiles[self.catalog["rootProfile"]]
        acceleration = root["fields"]["walkAccelerationStep"]
        self.assertEqual(acceleration["operator"], "replace")
        self.assertEqual(int(acceleration["value"]), 1)

    def test_runner_uses_two_frame_acceleration(self):
        runner = self.profiles["runner"]
        self.assertEqual(runner["parent"], self.catalog["rootProfile"])
        acceleration = runner["fields"]["walkAccelerationStep"]
        self.assertEqual(acceleration["operator"], "replace")
        self.assertEqual(int(acceleration["value"]), 2)

    def test_other_acceleration_amounts_are_named_opt_ins(self):
        actual = {}
        for profile_id, profile in self.profiles.items():
            acceleration = profile.get("fields", {}).get("walkAccelerationStep")
            if acceleration is not None and int(acceleration["value"]) != 1:
                actual[profile_id] = int(acceleration["value"])
        self.assertEqual(actual, WALK_ACCELERATION_OPT_INS)


if __name__ == "__main__":
    unittest.main()
