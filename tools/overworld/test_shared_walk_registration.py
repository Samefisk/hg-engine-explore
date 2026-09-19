"""Current recipes are exact registered contracts, not accepted game results."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.overworld import control

ROOT = Path(__file__).resolve().parents[2]


class WalkRegistrationTests(unittest.TestCase):
    def test_crash_cannot_use_a_lower_presentation_proof_level(self):
        from tools.overworld.proof_adapters import get_adapter
        test = json.loads((ROOT / "tests/overworld/test-recipes/walk.crash.feedback.json").read_text())
        adapter = get_adapter("mounted-crash-v1")
        with patch("tools.overworld.control.get_adapter", return_value=replace(adapter, proof_level="S3")):
            with self.assertRaisesRegex(ValueError, "exact measurement or reader contract"):
                control._shared_test_registration(test, ROOT)

    def test_current_registered_contracts_and_hashes(self):
        for name in ("observation.walk-policy-control", "observation.mount-pose-control",
                     "mount.movement.frame-pacing",
                     "walk.crash.feedback", "observation.crash-reader-control"):
            test = json.loads((ROOT / "tests/overworld/test-recipes" / (name + ".json")).read_text())
            registration, digest = control._shared_test_registration(test, ROOT)
            self.assertEqual(registration["recipeSha256"], digest)
            self.assertEqual(registration["proofLevel"], "S4" if name in
                ("mount.movement.frame-pacing", "walk.crash.feedback") else "S3")
            self.assertNotIn("acceptedProof", registration)
            changed = deepcopy(test)
            changed["subjects"][0]["species"] += 1
            with self.subTest(name=name), self.assertRaises(ValueError):
                control._shared_test_registration(changed, ROOT)
            with patch("tools.overworld.control.file_record", return_value={"sha256": "00" * 32}):
                with self.assertRaises(ValueError):
                    control._shared_test_registration(test, ROOT)


if __name__ == "__main__":
    unittest.main()
