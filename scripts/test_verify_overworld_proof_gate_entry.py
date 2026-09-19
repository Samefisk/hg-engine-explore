"""Command selection for the host proof gate; this does not run the suite."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from scripts import verify_overworld_proof_gate as proof_gate


REPO = Path(__file__).resolve().parents[1]


class ProofGateEntryTests(unittest.TestCase):
    def test_one_listed_module_can_be_selected(self) -> None:
        selected = proof_gate._selected_tests(
            ["--test", "tools.overworld.test_spawn_destination_scan"]
        )
        self.assertEqual(selected, ["tools.overworld.test_spawn_destination_scan"])

    def test_host_only_fails_before_loading_the_broad_suite(self) -> None:
        result = subprocess.run(
            [sys.executable, str(REPO / "scripts/verify_overworld_proof_gate.py"), "--host-only"],
            cwd=REPO,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("all tests in this script are host-only", result.stderr)
        self.assertNotIn("test_", result.stderr)

    def test_unknown_or_unlisted_selector_fails(self) -> None:
        with self.assertRaises(SystemExit):
            proof_gate._selected_tests(["--unknown"])
        with self.assertRaises(SystemExit):
            proof_gate._selected_tests(["--test", "tools.overworld.not_in_the_suite"])


if __name__ == "__main__":
    unittest.main()
