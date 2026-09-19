from argparse import Namespace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.overworld import control


class AffectedVerificationTests(unittest.TestCase):
    def test_spawn_pacing_gate_is_linked_to_profile_spawn_and_population_inputs(self):
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads((root / "tools/overworld/system_features.yaml").read_text())
        capabilities = {item["id"]: item for item in manifest["capabilities"]}

        for capability_id in ("profile.composition", "spawn", "population"):
            with self.subTest(capability=capability_id):
                capability = capabilities[capability_id]
                self.assertIn("host.spawn-refill-budget", capability["checks"])
                self.assertIn("host.spawn-destination-budget", capability["checks"])
                self.assertIn("population.spawn-work-budget", capability["scenarios"])

        profile = capabilities["profile.composition"]
        self.assertIn("world.unmounted.long-travel-cadence", profile["scenarios"])
        short_gate = json.loads(
            (root / "tests/overworld/scenarios/population.spawn-work-budget.json").read_text()
        )
        for capability_id in ("profile.composition", "spawn", "population"):
            self.assertIn(capability_id, short_gate["capabilities"])
        long_gate = json.loads(
            (root / "tests/overworld/scenarios/world.unmounted.long-travel-cadence.json").read_text()
        )
        self.assertIn("profile.composition", long_gate["capabilities"])

    def test_runs_ready_checks_before_reporting_missing_inputs(self):
        manifest = {
            "capabilities": [{
                "id": "cap",
                "sourcePatterns": ["src/foo"],
                "checks": ["host.check", "runtime.check"],
                "scenarios": [],
            }],
            "checks": [
                {
                    "id": "host.check",
                    "title": "ready host check",
                    "proofLevel": "S1",
                    "costTier": 1,
                    "sourcePatterns": [],
                    "requires": ["source"],
                    "command": ["host"],
                },
                {
                    "id": "runtime.check",
                    "title": "missing runtime check",
                    "proofLevel": "S2",
                    "costTier": 2,
                    "sourcePatterns": [],
                    "requires": ["build"],
                    "command": ["runtime"],
                },
            ],
        }
        calls = []
        response = []

        def run(command, result_kind, **kwargs):
            calls.append((command, result_kind))
            return {"command": command, "passed": True}

        def make_manifest(**kwargs):
            return {
                "runId": "test-run",
                "result": {
                    "passed": all(
                        item.get("passed", False) for item in kwargs["results"]
                    )
                },
            }

        with patch.object(control, "_load_contracts", return_value=(manifest, {})), \
                patch.object(control, "_requirement_state",
                             side_effect=lambda name: (name == "source", name)), \
                patch.object(control, "_run_command", side_effect=run), \
                patch.object(control, "make_run_manifest", side_effect=make_manifest), \
                patch.object(control, "write_run_manifest",
                             return_value=Path("manifest.json")), \
                patch.object(control, "artifact_directory", return_value=Path(".")), \
                patch.object(control, "utc_now", return_value="2026-09-07T00:00:00Z"), \
                patch.object(control, "_json", side_effect=response.append):
            result = control._verify_affected(Namespace(
                path=["src/foo"],
                base=None,
                run=True,
                json=True,
                manifest_output=None,
            ))

        self.assertEqual(result, 1)
        self.assertEqual(calls, [(["host"], "exit-zero")])
        self.assertEqual(
            response[0]["skipped"],
            [{"checkId": "runtime.check", "missingRequirements": ["build"]}],
        )
        self.assertTrue(response[0]["steps"][-1]["skipped"])


if __name__ == "__main__":
    unittest.main()
