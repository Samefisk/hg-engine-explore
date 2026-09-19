"""Keep overlay-reload transition identity in the permanent host gate."""

import subprocess
import sys
import unittest
from pathlib import Path


class FieldTransitionReloadTests(unittest.TestCase):
    def test_actual_driver_reload_retry_and_wrap(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "-B", "scripts/verify_overworld_field_transition_reload.py"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
