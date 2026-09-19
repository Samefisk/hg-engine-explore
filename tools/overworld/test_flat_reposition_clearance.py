"""Real caller/planner host regression; no live ROM or engine-layout claim."""
import unittest
from scripts import verify_overworld_flat_reposition_clearance as proof


class FlatRepositionClearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = proof.harness_source()
        cls.baseline = proof.start.execute(cls.source)

    def test_actual_caller_and_planner_agree_about_clearance(self):
        self.assertEqual(self.baseline.returncode, 0, self.baseline.stdout + self.baseline.stderr)

    def test_unmatched_fixture_seam_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "fixture seam differs"):
            proof.replace_once("missing", "wanted", "replacement")

    def test_known_bad_planner_copies(self):
        if self.baseline.returncode:
            self.skipTest("known-bad controls wait for a passing actual-source baseline")
        for label, source in proof.known_bad_sources(self.source):
            with self.subTest(label=label):
                result = proof.start.execute(source)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("flat Reposition invariant failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
