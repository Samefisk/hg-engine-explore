"""Focused checks for the CP7 conditional-profile catalog cutover."""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
VIEWER_PATH = REPO / "scripts/overworld_behavior_profile_viewer.py"


def load_viewer():
    spec = importlib.util.spec_from_file_location(
        "behavior_catalog_v4_test_viewer", VIEWER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {VIEWER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIEWER = load_viewer()
REMOVED_CONDITIONAL_STATES = "conditional" + "States"
REMOVED_DEFAULT_ACTIVE_BINDING = "default" + "ActiveApplication"
REMOVED_ACTIVE_PROFILE = "active" + "Profile"
REMOVED_ALERT_FIELDS = {
    "alert" + suffix for suffix in ("State", "ness", "Range", "Chance")
}


class BehaviorCatalogV5CutoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(VIEWER.BEHAVIOR_CATALOG_SOURCE.read_text())

    def profile(self, profile_id: str, catalog: dict | None = None) -> dict:
        source = self.catalog if catalog is None else catalog
        return next(profile for profile in source["profiles"] if profile["id"] == profile_id)

    def test_checked_in_catalog_and_generated_data_are_synchronized(self) -> None:
        VIEWER.validate_behavior_catalog(self.catalog)
        source = VIEWER.BEHAVIOR_DATA_SOURCE.read_text()
        header = VIEWER.BEHAVIOR_DATA_HEADER.read_text()
        self.assertEqual(VIEWER.render_behavior_catalog(self.catalog, source), source)
        self.assertEqual(
            VIEWER.render_behavior_catalog_header(header, self.catalog, source),
            header,
        )

    def test_checked_in_catalog_is_v5_and_old_versions_are_rejected(self) -> None:
        self.assertEqual(self.catalog["catalogVersion"], 5)
        for old_version in (1, 2, 3):
            changed = copy.deepcopy(self.catalog)
            changed["catalogVersion"] = old_version
            with self.assertRaisesRegex(
                VIEWER.ParseError, "unsupported behavior catalog version; expected 4 or 5"
            ):
                VIEWER.validate_behavior_catalog(changed)

    def test_v5_is_the_current_authoring_schema(self) -> None:
        schema = json.loads(VIEWER.BEHAVIOR_AUTHORING_SCHEMA_V5.read_text())
        self.assertEqual(schema["$id"], "behavior-authoring-v5.schema.json")
        self.assertEqual(schema["properties"]["catalogVersion"]["const"], 5)
        schema_dir = VIEWER.BEHAVIOR_AUTHORING_SCHEMA.parent
        self.assertFalse((schema_dir / "behavior-authoring-v2.schema.json").exists())
        self.assertFalse((schema_dir / "behavior-authoring-v3.schema.json").exists())

    def test_legacy_catalog_shapes_and_profile_fields_are_rejected(self) -> None:
        self.assertNotIn(REMOVED_CONDITIONAL_STATES, self.catalog)
        self.assertNotIn(REMOVED_DEFAULT_ACTIVE_BINDING, self.catalog["runtimeBindings"])
        removed_fields = {REMOVED_ACTIVE_PROFILE, *REMOVED_ALERT_FIELDS}
        self.assertFalse(any(
            removed_fields & set(profile["fields"])
            for profile in self.catalog["profiles"]
        ))

        changed = copy.deepcopy(self.catalog)
        changed[REMOVED_CONDITIONAL_STATES] = []
        with self.assertRaisesRegex(
            VIEWER.ParseError, f"unknown {REMOVED_CONDITIONAL_STATES}"
        ):
            VIEWER.validate_behavior_catalog(changed)

        changed = copy.deepcopy(self.catalog)
        changed["runtimeBindings"][REMOVED_DEFAULT_ACTIVE_BINDING] = "apply-default-active"
        with self.assertRaisesRegex(
            VIEWER.ParseError, f"unknown {REMOVED_DEFAULT_ACTIVE_BINDING}"
        ):
            VIEWER.validate_behavior_catalog(changed)

        changed = copy.deepcopy(self.catalog)
        changed["profiles"][0]["fields"][REMOVED_ACTIVE_PROFILE] = {
            "operator": "replace", "value": "apply-default-active"
        }
        with self.assertRaisesRegex(
            VIEWER.ParseError, f"cannot be overridden: {REMOVED_ACTIVE_PROFILE}"
        ):
            VIEWER.validate_behavior_catalog(changed)

    def test_notice_player_replaces_default_active(self) -> None:
        profile = self.profile("notice-player")
        application = next(
            item for item in self.catalog["applications"]
            if item["id"] == "apply-notice-player"
        )
        self.assertEqual(profile["kind"], "conditional")
        self.assertTrue(profile["conditions"])
        self.assertEqual(application["profile"], profile["id"])
        self.assertNotIn("target", application)

    def test_profile_owned_conditions_can_use_independent_subject_pools(self) -> None:
        changed = copy.deepcopy(self.catalog)
        profile = self.profile("perch", changed)
        extra = copy.deepcopy(profile["conditions"][0])
        extra["id"] = "condition-perch-other-pool"
        extra["subjects"] = {
            "mode": "members",
            "match": VIEWER.default_behavior_match_raws(),
            "members": ["SPECIES_BEEDRILL"],
        }
        profile["conditions"].append(extra)
        VIEWER.validate_behavior_catalog(changed)

    def test_runtime_projection_has_owner_data_and_tired_references_only(self) -> None:
        runtime = VIEWER.project_behavior_catalog_runtime(self.catalog)
        self.assertEqual(len(runtime["classProfiles"]), len(
            self.catalog["runtimeBindings"]["classOrder"]
        ))
        self.assertEqual(len(runtime["overrideProfiles"]), len(self.catalog["applications"]))
        self.assertNotIn(REMOVED_CONDITIONAL_STATES, runtime)
        self.assertNotIn(REMOVED_DEFAULT_ACTIVE_BINDING, runtime["runtimeBindings"])
        self.assertTrue(all(
            REMOVED_ACTIVE_PROFILE not in profile["fields"]
            for profile in runtime["classProfiles"] + runtime["overrideProfiles"]
        ))

        application_index = {
            application["id"]: index
            for index, application in enumerate(self.catalog["applications"])
        }
        root = runtime["classProfiles"][0]["fields"]
        self.assertEqual(
            int(root["tiredProfile"]),
            application_index[self.catalog["runtimeBindings"]["defaultTiredApplication"]],
        )

    def test_field_schema_uses_removed_storage_for_vision_and_walk_sway(self) -> None:
        source = json.loads(VIEWER.BEHAVIOR_SCHEMA_SOURCE.read_text())
        generated = json.loads(VIEWER.BEHAVIOR_SCHEMA_METADATA.read_text())
        self.assertEqual(source["schemaVersion"], 2)
        self.assertEqual(source["blobVersion"], 81)
        by_offset = {field["offset"]: field for field in source["fields"]}
        self.assertEqual(by_offset[1]["key"], "visionRange")
        self.assertEqual(by_offset[4]["key"], "visionCone")
        self.assertEqual(by_offset[14]["key"], "visionAdjacentAwareness")
        self.assertEqual(by_offset[46]["key"], "walkSwayWidth")
        self.assertNotIn("reserved", by_offset[46])
        self.assertEqual(by_offset[47]["key"], "tiredProfile")
        self.assertIn(
            "walkSwayWidth", {field["key"] for field in generated["editor"]["fields"]}
        )

    def test_legacy_lowering_entry_points_are_gone(self) -> None:
        for name in (
            "migrate_behavior_catalog_v1",
            "migrate_behavior_catalog_v2",
            "lower_behavior_catalog_v2",
            "lower_behavior_catalog_v3",
            "load_behavior_catalog_v3",
            "lift_compatibility_behavior_catalog",
        ):
            self.assertFalse(hasattr(VIEWER, name), name)


if __name__ == "__main__":
    unittest.main()
