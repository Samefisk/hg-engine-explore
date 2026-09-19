"""Checks that Hop landing pauses stay explicit and opt-in."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data/overworld_behavior_profiles.json"

# A behavior with a deliberate landing pause must be named here. Keeping this
# list explicit prevents new Hop profiles from gaining pauses by copy/paste.
HOP_PAUSE_OPT_INS = {"hopping-scavenger": 5}


class HopPauseDefaultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text())
        cls.profiles = {
            profile["id"]: profile for profile in cls.catalog["profiles"]
        }

    def test_root_hop_pause_defaults_to_zero(self):
        root = self.profiles[self.catalog["rootProfile"]]
        self.assertEqual(root["fields"]["hopPause"]["operator"], "replace")
        self.assertEqual(int(root["fields"]["hopPause"]["value"]), 0)

    def test_nonzero_hop_pauses_are_named_opt_ins(self):
        actual = {}
        for profile_id, profile in self.profiles.items():
            hop_pause = profile.get("fields", {}).get("hopPause")
            if hop_pause is not None and int(hop_pause["value"]) != 0:
                actual[profile_id] = int(hop_pause["value"])
        self.assertEqual(actual, HOP_PAUSE_OPT_INS)


if __name__ == "__main__":
    unittest.main()
