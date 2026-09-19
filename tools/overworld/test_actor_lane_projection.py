"""D2 actual-C lane projection and known-wrong mutation controls; not ROM proof."""

from pathlib import Path
import subprocess
import sys
import unittest


class ActorLaneProjectionTests(unittest.TestCase):
    def test_actual_native_state_projection_and_preservation(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "-B", str(root / "scripts/verify_overworld_actor_lane_projection.py")],
            cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS actual actor lane projection: 252 Fill cases, 252 Sync cases", result.stdout)
        self.assertEqual(result.stdout.count("PASS known-bad actor lane projection rejected:"), 2)


if __name__ == "__main__":
    unittest.main()
