"""S1 production spawn-order regression; no packaged-ROM/gameplay claim."""
from pathlib import Path
import subprocess
import sys
import unittest


class SpawnProfileLifecycleTests(unittest.TestCase):
    def test_actual_spawn_setup_order_and_failure_controls(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, str(root / "scripts/verify_overworld_spawn_profile_lifecycle.py")],
            cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS 32 spawn-order cases", result.stdout)
        self.assertEqual(result.stdout.count("PASS known-bad spawn rejected:"), 6)


if __name__ == "__main__":
    unittest.main()
