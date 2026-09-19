"""Focused tests for the CP0 Active-profile migration inventory."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/report_overworld_active_profile_migration.py"


def load_inventory_module():
    spec = importlib.util.spec_from_file_location("active_profile_migration_inventory", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


INVENTORY = load_inventory_module()


class ActiveProfileMigrationInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = INVENTORY.build_inventory(REPO)
        cls.findings = cls.report["findings"]

    def findings_for(self, **expected):
        return [
            finding for finding in self.findings
            if all(finding.get(key) == value for key, value in expected.items())
        ]

    def test_current_tree_is_complete_and_classified(self) -> None:
        self.assertGreater(self.report["summary"]["findingCount"], 100)
        self.assertEqual(self.report["summary"]["unclassifiedCount"], 0)
        self.assertEqual(self.report["summary"]["mappedLegacySourceCount"], 7)
        self.assertEqual(self.report["summary"]["unmappedLegacySourceCount"], 0)
        self.assertEqual(self.report["unmappedLegacySourceFindingIds"], [])
        self.assertEqual(self.report["unclassifiedFindingIds"], [])
        observed = set(self.report["summary"]["byClassification"])
        self.assertEqual(observed, set(INVENTORY.CLASSIFICATIONS))

    def test_catalog_semantics_name_every_migration_record(self) -> None:
        self.assertEqual(len(self.findings_for(kind="catalog_active_profile_reference")), 7)
        self.assertEqual(len(self.findings_for(kind="catalog_default_active_binding")), 1)
        self.assertEqual(len(self.findings_for(kind="catalog_conditional_state_entry")), 0)
        response_profiles = {
            finding["symbol"]
            for finding in self.findings_for(kind="catalog_active_response_profile")
        }
        self.assertEqual(response_profiles, {
            "default-active",
            "nervous-scavenger",
            "hopping-scavenger",
            "skittish",
            "swaying-plant-active",
            "ambush-plant-active",
        })
        self.assertEqual(
            {
                profile["id"]
                for profile in json.loads(
                    (REPO / INVENTORY.CATALOG_PATH).read_text()
                )["profiles"]
                if profile.get("kind") == "conditional"
            },
            {
                "ambush-plant-active",
                "bird-rooftop",
                "canopy-hop-surface",
                "default-active",
                "skittish",
                "swaying-plant-active",
            },
        )

    def test_report_covers_runtime_workshop_packages_traces_and_tests(self) -> None:
        required = (
            ("condition_input", "lib/overworld/overworld_behavior_resolver.c"),
            ("profile_response", "include/overworld_wild_behavior_data.h"),
            ("presentation_state", "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"),
            ("compatibility_adapter", "scripts/overworld_behavior_profile_viewer.py"),
            ("compatibility_adapter", "tools/overworld/devtools_resolver_parity.py"),
            ("compatibility_adapter", "tools/overworld-viewer-v2/reliability.py"),
            ("test", "tools/overworld/test_devtools_spawn_measurement.py"),
            ("dead_code", "design_previews/overworld-tools-v2/index.html"),
        )
        for classification, path in required:
            self.assertTrue(
                self.findings_for(classification=classification, path=path),
                f"missing {classification} coverage for {path}",
            )

        symbols = {finding["symbol"] for finding in self.findings}
        self.assertIn("BEHAVIOR_RESOLUTION_LANE_ACTIVE", symbols)
        self.assertIn("OW_WILD_SPAWNER_SPOT_STATE_ACTIVE", symbols)
        self.assertIn("OverworldWildBehaviorProfileSizeMustRemain216Bytes", symbols)
        self.assertTrue(self.findings_for(kind="primitive_binary_record"))
        self.assertTrue(self.findings_for(kind="resolve_result_binary_record"))
        self.assertTrue(self.findings_for(kind="three_lane_package"))
        self.assertTrue(self.findings_for(kind="behavior_version_record"))
        self.assertTrue(self.findings_for(kind="catalog_version_record"))

    def test_unowned_legacy_consumer_is_unclassified_and_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="active-profile-inventory-") as directory:
            root = Path(directory)
            source = root / "misc/unowned.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = activeProfile\n")
            report = INVENTORY.build_inventory(
                root,
                files=[Path("misc/unowned.py")],
                include_catalog_semantics=False,
            )
        self.assertEqual(report["summary"]["unclassifiedCount"], 1)
        self.assertIsNone(report["findings"][0]["classification"])
        with mock.patch.object(INVENTORY, "build_inventory", return_value=report), \
                mock.patch.object(INVENTORY, "write_json"):
            self.assertEqual(INVENTORY.main([]), 1)

    def test_cli_emits_json_and_forbidden_mode_is_cp7_gate(self) -> None:
        normal = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--compact"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(normal.returncode, 0, normal.stderr)
        normal_report = json.loads(normal.stdout)
        self.assertEqual(normal_report["summary"]["unclassifiedCount"], 0)

        forbidden = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--compact", "--forbid-legacy"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(forbidden.returncode, 2, forbidden.stderr)
        forbidden_report = json.loads(forbidden.stdout)
        self.assertGreater(forbidden_report["summary"]["forbiddenAtCp7Count"], 0)
        self.assertEqual(forbidden_report["summary"]["unclassifiedCount"], 0)

    def test_catalog_semantics_accept_complete_cp7_removal(self) -> None:
        catalog = {
            "profiles": [{"id": "root", "fields": {}}],
            "applications": [{"id": "apply-root", "profile": "root"}],
            "runtimeBindings": {},
        }
        with tempfile.TemporaryDirectory(prefix="active-profile-cp7-") as directory:
            root = Path(directory)
            path = root / INVENTORY.CATALOG_PATH
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(catalog, indent=2) + "\n")
            self.assertEqual(INVENTORY.scan_catalog(root), [])


if __name__ == "__main__":
    unittest.main()
