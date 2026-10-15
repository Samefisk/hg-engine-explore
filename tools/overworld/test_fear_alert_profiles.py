"""Visible scared-family alert choices; no native or gameplay execution."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ANGUISH = "OW_WILD_SPAWNER_BUBBLE_ID_ANGUISH"


class FearAlertProfilesTests(unittest.TestCase):
    def test_every_authored_retreat_and_safety_profile_owns_anguish(self):
        catalog = json.loads((ROOT / "data/overworld_behavior_profiles.json").read_text())
        profiles = {profile["id"]: profile for profile in catalog["profiles"]}
        retreat = {profile["id"] for profile in profiles.values()
                   if profile["fields"].get("chillState", {}).get("value")
                   == "OW_WILD_BEHAVIOR_KIND_FLEE"}
        self.assertEqual(retreat, {"startled", "skittish"})
        for name in sorted(retreat | {"seek-safety"}):
            with self.subTest(profile=name):
                self.assertEqual(profiles[name]["kind"], "conditional")
                self.assertEqual(profiles[name]["fields"]["alertEmote"],
                                 {"operator": "replace", "value": ANGUISH})
                alert_time = profiles[name]["fields"].get("alertTime",
                              profiles["default"]["fields"]["alertTime"])
                self.assertEqual(alert_time["operator"], "replace")
                self.assertEqual(int(alert_time["value"]), 10)
        self.assertNotEqual(profiles["default"]["fields"]["alertEmote"]["value"], ANGUISH)

    def test_cry_does_not_change_scared_roles_targets_or_timing(self):
        catalog = json.loads((ROOT / "data/overworld_behavior_profiles.json").read_text())
        profiles = {profile["id"]: profile for profile in catalog["profiles"]}
        for name, role, timing in (("skittish", "wild", (960, 970)),
                                   ("seek-safety", "follower", (960, 970)),
                                   ("startled", "wild", (44, 164))):
            with self.subTest(profile=name):
                for condition in profiles[name]["conditions"]:
                    self.assertEqual(condition["subjectRoles"], [role])
                    self.assertEqual(condition["activation"]["mode"], "timed")
                    self.assertEqual((condition["activation"]["durationFrames"],
                                      condition["activation"]["cooldownFrames"]), timing)
        self.assertEqual(profiles["skittish"]["fields"]["chillTarget"]["value"],
                         "OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER")
        self.assertEqual(profiles["startled"]["fields"]["chillTarget"]["value"],
                         "OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER")
        self.assertEqual(profiles["seek-safety"]["fields"]["chillTarget"]["value"],
                         "OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER")
        self.assertNotIn("chillAction", profiles["skittish"]["fields"])
        self.assertNotIn("chillAction", profiles["seek-safety"]["fields"])


if __name__ == "__main__":
    unittest.main()
