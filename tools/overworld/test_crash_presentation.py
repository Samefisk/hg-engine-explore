"""Actual production crash-shake source; no emulator or gameplay proof."""
from pathlib import Path
import subprocess
import sys
import unittest


class CrashPresentationTests(unittest.TestCase):
    def test_actual_c_lifecycle_and_mutation_controls(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable,"-B",str(root / "scripts/verify_overworld_crash_presentation.py")],
                                cwd=root,capture_output=True,text=True,timeout=40)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn("PASS actual crash presentation: 11 ticks",result.stdout)
        self.assertIn("PASS mutation controls: offset, sign, timer",result.stdout)


if __name__ == "__main__":
    unittest.main()
