"""Permanent instruction-level regression for failed grass-effect creation."""
import subprocess
import sys
import unittest
from pathlib import Path


class GrassEffectGuardTests(unittest.TestCase):
    def test_resident_extent_uses_real_boundary_not_legacy_headroom(self):
        from scripts.verify_summary_move_relearn import overlay129_extent_fits
        self.assertTrue(overlay129_extent_fits(0x7FEC))
        self.assertTrue(overlay129_extent_fits(0x8000))
        self.assertFalse(overlay129_extent_fits(0x8001))
        self.assertFalse(overlay129_extent_fits(0))

    def test_assembled_null_cleanup_and_success_parity(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "-B", "scripts/verify_overworld_grass_effect_guard.py"],
            cwd=root, capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
