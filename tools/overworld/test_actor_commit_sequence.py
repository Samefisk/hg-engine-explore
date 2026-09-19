"""Actual actor publication body with real motion model; host-only proof."""
from pathlib import Path
import subprocess
import sys
import unittest


class ActorCommitSequenceTests(unittest.TestCase):
    def test_actual_multi_motion_commits_and_rejection_controls(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable, "-B", str(root / "scripts/verify_overworld_actor_commit_sequence.py")],
                                cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS actor lifetime commit cases", result.stdout)
        self.assertEqual(result.stdout.count("PASS known-bad actor commit rejected:"), 11)


if __name__ == "__main__":
    unittest.main()
