"""Focused parity and reference checks for the unified behavior catalog."""

from __future__ import annotations

import copy
import gzip
import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[2]
VIEWER_PATH = REPO / "scripts/overworld_behavior_profile_viewer.py"


def load_viewer():
    spec = importlib.util.spec_from_file_location("behavior_catalog_v2_test_viewer", VIEWER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {VIEWER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIEWER = load_viewer()


class BehaviorCatalogV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(VIEWER.BEHAVIOR_CATALOG_SOURCE.read_text())

    def test_checked_in_v2_catalog_lowers_to_byte_identical_compatibility_data(self) -> None:
        VIEWER.validate_behavior_catalog(self.catalog)
        source = VIEWER.BEHAVIOR_DATA_SOURCE.read_text()
        header = VIEWER.BEHAVIOR_DATA_HEADER.read_text()
        self.assertEqual(VIEWER.render_behavior_catalog(self.catalog, source), source)
        self.assertEqual(
            VIEWER.render_behavior_catalog_header(header, self.catalog, source),
            header,
        )

    def test_canonical_loader_and_profile_read_model_return_v2(self) -> None:
        self.assertEqual(VIEWER.load_behavior_catalog_v2(), self.catalog)
        payload = VIEWER.build_data(
            include_routes=False,
            include_spawn_settings=False,
        )
        self.assertEqual(payload["profileCatalog"], self.catalog)
        self.assertNotIn("classProfiles", payload["profileCatalog"])
        self.assertNotIn("overrideProfiles", payload["profileCatalog"])

    def test_focused_profile_deck_builder_is_compact_and_skips_legacy_resolution(self) -> None:
        retired_calls = (
            "resolve_native_requests",
            "lower_behavior_catalog_v2",
            "catalog_class_profiles",
            "catalog_behavior_overrides",
            "catalog_conditional_states",
        )
        patches = [
            mock.patch.object(
                VIEWER,
                name,
                side_effect=AssertionError(f"focused Profile Deck called {name}"),
            )
            for name in retired_calls
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        payload = VIEWER.build_profile_deck_data()
        self.assertEqual(set(payload), {
            "profilesAvailable",
            "profileError",
            "profileCatalog",
            "fields",
            "numericProfileFieldKeys",
            "numericOverrideOperatorFieldKeys",
            "boundedOverrideOperatorFieldKeys",
            "editOptions",
            "assignments",
            "labels",
        })
        self.assertEqual(payload["profileCatalog"], self.catalog)
        self.assertEqual(set(payload["labels"]), {"groups", "terrains"})
        for assignment in payload["assignments"]:
            self.assertEqual(set(assignment), {"species", "groups"})
            self.assertLessEqual(
                set(assignment["species"]),
                {
                    "symbol", "name", "aliases", "iconUrl",
                    "familyBaseSymbol", "familyBaseName", "types",
                },
            )
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        self.assertLess(len(gzip.compress(encoded, compresslevel=6)), 250_000)

    def test_complete_catalog_save_is_one_validated_write(self) -> None:
        changed = copy.deepcopy(self.catalog)
        changed_profile = next(
            profile for profile in changed["profiles"] if profile["id"] == "test"
        )
        changed_profile["name"] = "Test renamed"
        changed["selectors"][0]["profile"] = "aggressive-chase"
        changed["applications"][0], changed["applications"][1] = (
            changed["applications"][1],
            changed["applications"][0],
        )
        body = json.dumps({"catalog": changed}).encode()
        with mock.patch.object(
            VIEWER, "load_behavior_catalog_v2", return_value=self.catalog
        ), mock.patch.object(VIEWER, "write_behavior_catalog") as write:
            result = VIEWER.apply_profile_catalog_changes(body)
        self.assertEqual(
            result,
            {
                "saved": True,
                "message": "Saved profile catalog",
                "catalogVersion": 2,
            },
        )
        write.assert_called_once_with(changed)
        VIEWER.lower_behavior_catalog_v2(changed)

    def test_complete_catalog_save_no_op_does_not_write(self) -> None:
        body = json.dumps({"catalog": self.catalog}).encode()
        with mock.patch.object(
            VIEWER, "load_behavior_catalog_v2", return_value=self.catalog
        ), mock.patch.object(VIEWER, "write_behavior_catalog") as write:
            result = VIEWER.apply_profile_catalog_changes(body)
        self.assertEqual(result["saved"], False)
        self.assertEqual(result["catalogVersion"], 2)
        write.assert_not_called()

    def test_complete_catalog_save_rejects_unknown_wrapper_keys(self) -> None:
        body = json.dumps({"catalog": self.catalog, "sourceRevision": "unexpected"}).encode()
        with self.assertRaisesRegex(ValueError, "unknown sourceRevision"):
            VIEWER.apply_profile_catalog_changes(body)

    def test_v1_migration_and_compatibility_writer_are_lossless(self) -> None:
        lowered = VIEWER.lower_behavior_catalog_v2(self.catalog)
        plain_v1 = json.loads(json.dumps(lowered))
        migrated = VIEWER.migrate_behavior_catalog_v1(plain_v1)
        round_trip = VIEWER.lower_behavior_catalog_v2(migrated)
        for key in (
            "classProfiles",
            "classRules",
            "speciesClassRules",
            "overrideProfiles",
            "conditionalStates",
        ):
            self.assertEqual(round_trip[key], plain_v1[key])
        self.assertEqual(
            VIEWER.lift_compatibility_behavior_catalog(lowered),
            self.catalog,
        )

    def test_selection_materializes_parent_but_application_uses_local_fields(self) -> None:
        lowered = VIEWER.lower_behavior_catalog_v2(self.catalog)
        root = next(
            profile
            for profile in self.catalog["profiles"]
            if profile["id"] == self.catalog["rootProfile"]
        )
        selected = next(
            profile
            for profile in self.catalog["profiles"]
            if profile["id"] == "aggressive-chase"
        )
        selected_compat = next(
            profile
            for profile in lowered["classProfiles"]
            if profile.profile_id == selected["id"]
        )
        application = self.catalog["applications"][0]
        application_profile = next(
            profile
            for profile in self.catalog["profiles"]
            if profile["id"] == application["profile"]
        )
        inherited_field = next(
            field
            for field in VIEWER.PROFILE_FIELDS
            if field not in selected["fields"] and field not in application_profile["fields"]
        )
        self.assertEqual(
            selected_compat["fields"][inherited_field],
            str(root["fields"][inherited_field]["value"]),
        )

        application_compat = lowered["overrideProfiles"][0]
        self.assertEqual(
            set(application_compat["fields"]),
            set(application_profile["fields"]),
        )
        self.assertNotIn(inherited_field, application_compat["fields"])

    def test_empty_application_profile_is_a_valid_inherit_only_layer(self) -> None:
        changed = copy.deepcopy(self.catalog)
        profile = next(
            profile
            for profile in changed["profiles"]
            if profile["id"] == "default-active"
        )
        profile["fields"] = {}

        lowered = VIEWER.lower_behavior_catalog_v2(changed)
        application_index = next(
            index
            for index, application in enumerate(changed["applications"])
            if application["profile"] == profile["id"]
        )
        self.assertEqual(lowered["overrideProfiles"][application_index]["fields"], {})

    def test_stable_references_follow_application_reordering(self) -> None:
        reordered = copy.deepcopy(self.catalog)
        reordered["applications"][0], reordered["applications"][1] = (
            reordered["applications"][1],
            reordered["applications"][0],
        )
        lowered = VIEWER.lower_behavior_catalog_v2(reordered)
        application_indexes = {
            application["id"]: index
            for index, application in enumerate(reordered["applications"])
        }
        root = next(
            profile
            for profile in reordered["profiles"]
            if profile["id"] == reordered["rootProfile"]
        )
        root_compat = lowered["classProfiles"][0]["fields"]
        self.assertEqual(
            int(root_compat["activeProfile"]),
            application_indexes[root["fields"]["activeProfile"]["value"]],
        )
        state = reordered["conditionalStates"][0]
        state_compat = lowered["conditionalStates"][0]
        self.assertEqual(
            int(state_compat["parentProfile"]),
            application_indexes[state["parentApplication"]],
        )
        self.assertEqual(
            int(state_compat["overrideProfile"]),
            application_indexes[state["application"]],
        )

    def test_profile_cycle_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.catalog)
        root = next(
            profile
            for profile in invalid["profiles"]
            if profile["id"] == invalid["rootProfile"]
        )
        root["parent"] = invalid["profiles"][1]["id"]
        with self.assertRaisesRegex(VIEWER.ParseError, "root profile cannot have a parent"):
            VIEWER.validate_behavior_catalog(invalid)


if __name__ == "__main__":
    unittest.main()
