"""Actual-source native policy regression; no ROM or gameplay claim."""
from pathlib import Path
import subprocess
import sys
import unittest


class RebindPassThroughTests(unittest.TestCase):
    def test_actual_normalize_rebind_retains_native_pass_through_policy(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable,"-B",str(root / "scripts/verify_overworld_rebind_pass_through.py")],
                                cwd=root,capture_output=True,text=True,timeout=40)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn("PASS actual NORMALIZE_SLOT/REBIND pass-through: 40 cases",result.stdout)


if __name__ == "__main__":
    unittest.main()
