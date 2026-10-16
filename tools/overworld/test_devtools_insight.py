import unittest
from tools.overworld.devtools_insight import explain_actor, first_difference


class InsightTests(unittest.TestCase):
    def test_unknown_profile_is_not_filled_from_config(self):
        result = explain_actor({"actors": [{"handle": {"value": 1}}]}, 1)
        self.assertIsNone(result["resolvedProfile"])
        self.assertIn("unknown", result["profileStatus"])

    def test_exact_observed_fingerprint_and_schema_units(self):
        snapshot = {"actors": [{"handle": {"value": 1}, "behaviorFingerprint": 7}],
                    "nativeObservation": {"resolvedProfiles": [{"fingerprint": 7, "lanes": ["08"]}]}}
        result = explain_actor(snapshot, 1, {"compactSize": 1, "fields": [
            {"key": "walkTime", "offset": 0, "cType": "u8", "unit": "frames"}]})
        self.assertEqual(result["resolvedProfile"]["decodedLanes"]["owner"]["walkTime"], {"value": 8, "unit": "frames"})

    def test_stale_and_ambiguous_actor_rejected(self):
        for actors in ([], [{"handle": {"value": 1}}] * 2):
            with self.assertRaises(ValueError): explain_actor({"actors": actors}, 1)

    def test_packed_profile_fields_have_separate_values(self):
        snapshot = {"actors": [{"handle": {"value": 1}, "behaviorFingerprint": 7}],
                    "nativeObservation": {"resolvedProfiles": [{"fingerprint": 7, "lanes": ["8b"]}]}}
        result = explain_actor(snapshot, 1, {"compactSize": 1, "fields": [
            {"key": "dust", "offset": 0, "cType": "u8", "unit": "boolean", "bitOffset": 0, "bitWidth": 1},
            {"key": "stopSkidTime", "offset": 0, "cType": "u8", "unit": "frames", "bitOffset": 1, "bitWidth": 7}]})
        values = result["resolvedProfile"]["decodedLanes"]["owner"]
        self.assertEqual(values["dust"]["value"], 1)
        self.assertEqual(values["stopSkidTime"]["value"], 69)

    def test_first_difference_keeps_missing_distinct_from_null(self):
        value = first_difference({"frames": [{"x": None}]}, {"frames": [{}]})
        self.assertEqual(value["firstDifference"]["path"], ["frames", 0, "x"])
        self.assertFalse(value["firstDifference"]["rightPresent"])
        self.assertFalse(value["acceptedProof"])
        self.assertTrue(first_difference({"a": [1]}, {"a": [1]})["equal"])


if __name__ == "__main__": unittest.main()
