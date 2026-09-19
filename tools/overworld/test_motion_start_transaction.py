"""S1 actual motion start/rejection seam, not ARM or emulator proof."""
from pathlib import Path
import subprocess
import sys
import unittest


class MotionStartTransactionTests(unittest.TestCase):
    def test_actual_motion_start_and_rejection_controls(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable, str(root / "scripts/verify_overworld_motion_start_transaction.py")],
                                cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS 16 motion-start cases", result.stdout)
        self.assertEqual(result.stdout.count("PASS known-bad transaction rejected:"), 6)
        self.assertIn("PASS known-bad transaction rejected: prepare before owner readiness", result.stdout)


if __name__ == "__main__":
    unittest.main()
