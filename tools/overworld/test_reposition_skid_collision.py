"""Extracted-C regression for Wild and Mount Reposition skid collision."""
import unittest

from scripts import verify_overworld_reposition_skid_collision as proof


class RepositionSkidCollisionTests(unittest.TestCase):
    def test_clear_prefix_and_blocked_first_tile(self):
        result = proof.execute(proof.harness_source())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
