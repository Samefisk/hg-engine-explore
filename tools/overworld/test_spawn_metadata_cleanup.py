"""Keep the production-C nullable cleanup regression in the host gate."""
import subprocess
import sys
import unittest
from pathlib import Path


class SpawnMetadataCleanupTests(unittest.TestCase):
    def test_production_cleanup_and_removed_guard_control(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "-B", str(root / "scripts/verify_overworld_spawn_metadata_cleanup.py")],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("removed NULL guard rejected", result.stdout)
