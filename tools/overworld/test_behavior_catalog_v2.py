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


class BehaviorCatalogV4Tests(unittest.TestCase):
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

    def test_only_catalog_v4_is_accepted(self) -> None:
        self.assertEqual(self.catalog["catalogVersion"], 4)
        for old_version in (1, 2, 3):
            changed = copy.deepcopy(self.catalog)
            changed["catalogVersion"] = old_version
            with self.assertRaisesRegex(
                VIEWER.ParseError, "unsupported behavior catalog version; expected 4"
            ):
                VIEWER.validate_behavior_catalog(changed)

    def test_only_authoring_schema_v4_remains(self) -> None:
        schema = json.loads(VIEWER.BEHAVIOR_AUTHORING_SCHEMA.read_text())
        self.assertEqual(schema["$id"], "behavior-authoring-v4.schema.json")
        self.assertEqual(schema["properties"]["catalogVersion"]["const"], 4)
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

    def test_default_active_names_remain_as_conditional_data(self) -> None:
        profile = self.profile("default-active")
        application = next(
            item for item in self.catalog["applications"]
            if item["id"] == "apply-default-active"
        )
        self.assertEqual(profile["kind"], "conditional")
        self.assertTrue(profile["conditions"])
        self.assertEqual(application["profile"], profile["id"])
        self.assertEqual(application["target"]["mode"], "disabled")

    def test_profile_owned_conditions_can_use_independent_subject_pools(self) -> None:
        changed = copy.deepcopy(self.catalog)
        profile = self.profile("bird-rooftop", changed)
        extra = copy.deepcopy(profile["conditions"][0])
        extra["id"] = "condition-bird-rooftop-other-pool"
        extra["subjects"] = {
            "application": "apply-flying-insect"
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

    def test_field_schema_reserves_removed_storage_without_authoring_it(self) -> None:
        source = json.loads(VIEWER.BEHAVIOR_SCHEMA_SOURCE.read_text())
        generated = json.loads(VIEWER.BEHAVIOR_SCHEMA_METADATA.read_text())
        self.assertEqual(source["schemaVersion"], 2)
        self.assertEqual(source["blobVersion"], 78)
        by_offset = {field["offset"]: field for field in source["fields"]}
        self.assertEqual(by_offset[46]["key"], "reserved46")
        self.assertTrue(by_offset[46]["reserved"])
        self.assertEqual(by_offset[47]["key"], "tiredProfile")
        self.assertNotIn(
            "reserved46", {field["key"] for field in generated["editor"]["fields"]}
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
