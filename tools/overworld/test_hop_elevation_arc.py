"""Host tests of real Hop helper bodies; not a live ROM result."""
import unittest

from scripts import verify_overworld_hop_elevation_arc as proof


class HopElevationArcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = proof.harness_source()
        cls.baseline = proof.execute(cls.source)

    def test_actual_trajectory_and_renderer_contract(self):
        self.assertEqual(self.baseline.returncode, 0,
                         self.baseline.stdout + self.baseline.stderr)

    def test_extraction_rejects_missing_body(self):
        with self.assertRaisesRegex(ValueError, "expected one production definition"):
            proof.harness_source("")

    def test_extraction_rejects_duplicate_body(self):
        body = proof.extract_function(proof.SOURCE.read_text(),
                                      "OverworldWildBehavior_CalculateJumpTrajectory", "u32")
        with self.assertRaisesRegex(ValueError, "expected one production definition"):
            proof.harness_source(proof.SOURCE.read_text() + "\n" + body)

    def test_known_bad_production_copies(self):
        if self.baseline.returncode:
            self.skipTest("known-bad controls wait for a passing actual-source baseline")
        for label, source in proof.known_bad_sources(self.source):
            with self.subTest(label=label):
                result = proof.execute(source)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("Hop arc invariant failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
