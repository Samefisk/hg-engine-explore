"""Historical CP6-to-building-block migration chain checks.

CP6 moved the old Active lane into conditional profiles. The PB migration then
replaced those intermediate profiles with small reusable building blocks. This
test keeps the recorded CP6 mapping complete without requiring retired profile
IDs to remain in the live catalog.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
CP6_FIXTURE = (
    ROOT / "tools/overworld/fixtures/conditional_profile_migration_v1.json"
)
PB_FIXTURE = (
    ROOT / "tools/overworld/fixtures/profile_building_blocks_target_v1.json"
)
V2_TOOLS = ROOT / "tools/overworld-viewer-v2"
if str(V2_TOOLS) not in sys.path:
    sys.path.insert(0, str(V2_TOOLS))

import native_resolver  # noqa: E402


class ConditionalProfileMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(
            (ROOT / "data/overworld_behavior_profiles.json").read_text()
        )
        cls.cp6 = json.loads(CP6_FIXTURE.read_text())
        cls.pb = json.loads(PB_FIXTURE.read_text())
        cls.live_profiles = {
            profile["id"]: profile for profile in cls.catalog["profiles"]
        }
        cls.live_applications = {
            application["id"]: application
            for application in cls.catalog["applications"]
        }
        cls.pb_migrations = {
            migration["source"]: migration["destinations"]
            for migration in cls.pb["migration"]["profiles"]
        }

    def test_every_cp6_intermediate_profile_has_a_recorded_pb_destination(self) -> None:
        self.assertEqual(self.cp6["version"], 1)
        intermediate_profiles = {
            mapping["conditionalProfile"] for mapping in self.cp6["mappings"]
        }
        intermediate_profiles.update(
            migration["conditionalProfile"]
            for migration in self.cp6["terrainMigrations"]
        )
        self.assertEqual(
            intermediate_profiles,
            {
                "default-active",
                "skittish",
                "swaying-plant-active",
                "ambush-plant-active",
                "canopy-hop-surface",
                "bird-rooftop",
            },
        )
        for profile_id in sorted(intermediate_profiles):
            with self.subTest(profile=profile_id):
                self.assertIn(profile_id, self.pb_migrations)
                self.assertTrue(self.pb_migrations[profile_id])

    def test_recorded_destinations_end_in_live_profiles_or_internal_state(self) -> None:
        for source, destinations in self.pb_migrations.items():
            for destination in destinations:
                with self.subTest(source=source, destination=destination):
                    if destination["type"] == "profile":
                        self.assertIn(destination["id"], self.live_profiles)
                    elif destination["type"] == "root":
                        self.assertEqual(
                            destination["id"], self.catalog["rootProfile"]
                        )
                    elif destination["type"] == "internal-state":
                        self.assertIn(
                            destination["id"], self.pb["target"]["internalStates"]
                        )
                    elif destination["type"] == "named-pool":
                        self.assertIn(
                            destination["id"],
                            {pool["id"] for pool in self.catalog["pools"]},
                        )
                    else:
                        self.fail(f"unsupported migration destination: {destination}")

    def test_retired_active_profiles_are_not_live_catalog_owners(self) -> None:
        retired = {
            "default-active",
            "swaying-plant-active",
            "ambush-plant-active",
        }
        self.assertTrue(retired.isdisjoint(self.live_profiles))
        self.assertTrue(
            retired.isdisjoint(
                application["profile"]
                for application in self.catalog["applications"]
            )
        )

    def test_live_conditional_profiles_own_subject_pools(self) -> None:
        for profile in self.live_profiles.values():
            if profile["kind"] != "conditional":
                continue
            application = self.live_applications[f"apply-{profile['id']}"]
            with self.subTest(profile=profile["id"]):
                self.assertNotIn("target", application)
                self.assertTrue(profile["conditions"])
                for condition in profile["conditions"]:
                    self.assertIn("subjects", condition)
                    self.assertNotIn("application", condition["subjects"])

    def test_host_adapter_rejects_removed_request_inputs(self) -> None:
        removed_terrain_key = "conditionTerrain" + "Mask"
        for request, message in (
            ({"requestVersion": 1}, "unsupported native resolver requestVersion 1"),
            ({"requestVersion": 0}, "unsupported native resolver requestVersion 0"),
            ({"conditionInputMode": "explicit"}, "conditionInputMode was removed"),
            ({removed_terrain_key: 1}, removed_terrain_key + " was removed"),
        ):
            with self.subTest(request=request), self.assertRaisesRegex(
                ValueError, message
            ):
                native_resolver.resolve(None, request, root=ROOT)


if __name__ == "__main__":
    unittest.main()
