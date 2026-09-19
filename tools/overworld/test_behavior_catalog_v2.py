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
    spec = importlib.util.spec_from_file_location("behavior_catalog_v3_test_viewer", VIEWER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {VIEWER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIEWER = load_viewer()


class BehaviorCatalogV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(VIEWER.BEHAVIOR_CATALOG_SOURCE.read_text())

    def condition_profile(self, catalog: dict | None = None, profile_id: str = "bird-rooftop") -> dict:
        source = self.catalog if catalog is None else catalog
        return next(profile for profile in source["profiles"] if profile["id"] == profile_id)

    def compatibility_v1(self, catalog: dict | None = None) -> dict:
        source = self.catalog if catalog is None else catalog
        return VIEWER.lower_behavior_catalog_v2(VIEWER.lower_behavior_catalog_v3(source))

    @staticmethod
    def notice_condition(
        condition_id: str,
        *,
        subjects: dict | None = None,
        target: dict | None = None,
    ) -> dict:
        return {
            "id": condition_id,
            "subjects": subjects or {"application": "apply-bird"},
            "when": {
                "kind": "notice-target",
                "rangeKind": "OW_WILD_BEHAVIOR_ALERT_RANGE_FACING_LINE_CLOSE_RADIUS",
                "rangeLength": 3,
                "chancePercent": 100,
            },
            "activation": {
                "mode": "timed",
                "durationFrames": 60,
                "cooldownFrames": 120,
            },
            "target": target or {"kind": "player"},
        }

    def test_checked_in_v3_catalog_lowers_to_byte_identical_compatibility_data(self) -> None:
        VIEWER.validate_behavior_catalog(self.catalog)
        source = VIEWER.BEHAVIOR_DATA_SOURCE.read_text()
        header = VIEWER.BEHAVIOR_DATA_HEADER.read_text()
        self.assertEqual(VIEWER.render_behavior_catalog(self.catalog, source), source)
        self.assertEqual(
            VIEWER.render_behavior_catalog_header(header, self.catalog, source),
            header,
        )

    def test_checked_in_catalog_has_explicit_kinds_and_owned_conditions(self) -> None:
        self.assertEqual(self.catalog["catalogVersion"], 3)
        self.assertNotIn("conditionalStates", self.catalog)
        self.assertTrue(all(profile["kind"] in {"normal", "conditional"}
                            for profile in self.catalog["profiles"]))
        conditional = {
            profile["id"]: profile for profile in self.catalog["profiles"]
            if profile["kind"] == "conditional"
        }
        self.assertEqual(set(conditional), {"canopy-hop-surface", "bird-rooftop"})
        self.assertEqual(
            conditional["canopy-hop-surface"]["conditions"][0]["id"],
            "condition-canopy-hopper-on-canopy",
        )
        self.assertEqual(
            conditional["bird-rooftop"]["conditions"][0]["id"],
            "condition-bird-rooftop",
        )

    def test_v3_schema_is_checked_in_and_names_v3(self) -> None:
        schema = json.loads(VIEWER.BEHAVIOR_AUTHORING_SCHEMA.read_text())
        self.assertEqual(schema["$id"], "behavior-authoring-v3.schema.json")
        self.assertEqual(schema["properties"]["catalogVersion"]["const"], 3)

    def test_v2_read_only_migration_recreates_owned_conditions(self) -> None:
        v2 = VIEWER.lower_behavior_catalog_v3(self.catalog)
        migrated = VIEWER.migrate_behavior_catalog_v2(v2)
        self.assertEqual(migrated, self.catalog)
        self.assertEqual(VIEWER.load_behavior_catalog_v2(), v2)

    def test_condition_order_and_overlapping_subject_pools_are_valid(self) -> None:
        changed = copy.deepcopy(self.catalog)
        profile = self.condition_profile(changed)
        inline_subjects = {
            "mode": "members",
            "match": copy.deepcopy(changed["applications"][0]["target"]["match"]),
            "members": ["SPECIES_PIDGEY"],
        }
        actor_target = {
            "kind": "actor",
            "roles": ["wild", "follower"],
            "selection": "nearest",
            "groupMask": "OW_WILD_BEHAVIOR_GROUP_NONE",
            "members": ["SPECIES_PIDGEY"],
        }
        profile["conditions"].extend([
            self.notice_condition("condition-bird-notices-player"),
            self.notice_condition(
                "condition-bird-notices-pokemon",
                subjects=inline_subjects,
                target=actor_target,
            ),
        ])
        VIEWER.validate_behavior_catalog(changed)
        self.assertEqual(
            [condition["id"] for condition in profile["conditions"]],
            [
                "condition-bird-rooftop",
                "condition-bird-notices-player",
                "condition-bird-notices-pokemon",
            ],
        )
        with self.assertRaisesRegex(VIEWER.ParseError, "cannot be lowered"):
            VIEWER.lower_behavior_catalog_v3(changed)

        source = VIEWER.BEHAVIOR_DATA_SOURCE.read_text()
        rendered = VIEWER.render_behavior_catalog(changed, source)
        counts = VIEWER.behavior_blob_counts(rendered)
        self.assertEqual(counts["OWBD_CONDITION_ENTRY_COUNT"], 4)
        self.assertEqual(counts["OWBD_OVERRIDE_MEMBER_COUNT"], 300)
        entries = VIEWER.parse_initializer(
            VIEWER.extract_braced_initializer(
                VIEWER.strip_c_comments(VIEWER.join_line_continuations(rendered)),
                "sOverworldWildBehaviorConditionEntries",
            )
        )
        self.assertEqual(len(entries), 4)
        self.assertTrue(all(len(entry) == 24 for entry in entries))

    def test_condition_reorder_changes_precedence_without_changing_ids(self) -> None:
        changed = copy.deepcopy(self.catalog)
        profile = self.condition_profile(changed)
        profile["conditions"].extend([
            self.notice_condition("condition-bird-first"),
            self.notice_condition("condition-bird-second"),
        ])
        metadata, before = VIEWER._catalog_condition_layout(changed)
        before_ids = [entry["conditionId"] for entry in before[-3:]]
        profile["conditions"][-2:] = reversed(profile["conditions"][-2:])
        reordered_metadata, after = VIEWER._catalog_condition_layout(changed)
        after_ids = [entry["conditionId"] for entry in after[-3:]]
        self.assertEqual(metadata, reordered_metadata)
        self.assertEqual(after_ids, [before_ids[0], before_ids[2], before_ids[1]])

    def test_canonical_loader_and_profile_read_model_return_v3(self) -> None:
        self.assertEqual(VIEWER.load_behavior_catalog_v3(), self.catalog)
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
            "lower_behavior_catalog_v3",
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
            VIEWER, "load_behavior_catalog_v3", return_value=self.catalog
        ), mock.patch.object(VIEWER, "write_behavior_catalog") as write:
            result = VIEWER.apply_profile_catalog_changes(body)
        self.assertEqual(
            result,
            {
                "saved": True,
                "message": "Saved profile catalog",
                "catalogVersion": 3,
            },
        )
        write.assert_called_once_with(changed)
        VIEWER.lower_behavior_catalog_v3(changed)

    def test_complete_catalog_save_no_op_does_not_write(self) -> None:
        body = json.dumps({"catalog": self.catalog}).encode()
        with mock.patch.object(
            VIEWER, "load_behavior_catalog_v3", return_value=self.catalog
        ), mock.patch.object(VIEWER, "write_behavior_catalog") as write:
            result = VIEWER.apply_profile_catalog_changes(body)
        self.assertEqual(result["saved"], False)
        self.assertEqual(result["catalogVersion"], 3)
        write.assert_not_called()

    def test_complete_catalog_save_rejects_unknown_wrapper_keys(self) -> None:
        body = json.dumps({"catalog": self.catalog, "sourceRevision": "unexpected"}).encode()
        with self.assertRaisesRegex(ValueError, "unknown sourceRevision"):
            VIEWER.apply_profile_catalog_changes(body)

    def test_v1_migration_and_compatibility_writer_are_lossless(self) -> None:
        v2 = VIEWER.lower_behavior_catalog_v3(self.catalog)
        lowered = VIEWER.lower_behavior_catalog_v2(v2)
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
            v2,
        )
        self.assertEqual(VIEWER.migrate_behavior_catalog_v2(v2), self.catalog)

    def test_selection_materializes_parent_but_application_uses_local_fields(self) -> None:
        lowered = self.compatibility_v1()
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

        lowered = self.compatibility_v1(changed)
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
        lowered = self.compatibility_v1(reordered)
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
        condition_profile = next(
            profile for profile in reordered["profiles"]
            if profile["id"] == "canopy-hop-surface"
        )
        condition = condition_profile["conditions"][0]
        conditional_application = next(
            application for application in reordered["applications"]
            if application["profile"] == condition_profile["id"]
        )
        state_compat = lowered["conditionalStates"][0]
        self.assertEqual(
            int(state_compat["parentProfile"]),
            application_indexes[condition["subjects"]["application"]],
        )
        self.assertEqual(
            int(state_compat["overrideProfile"]),
            application_indexes[conditional_application["id"]],
        )

    def test_normal_profiles_forbid_conditions(self) -> None:
        invalid = copy.deepcopy(self.catalog)
        root = next(profile for profile in invalid["profiles"] if profile["id"] == "default")
        root["conditions"] = []
        with self.assertRaisesRegex(VIEWER.ParseError, "unknown conditions"):
            VIEWER.validate_behavior_catalog(invalid)

    def test_conditional_profile_requires_conditions(self) -> None:
        invalid = copy.deepcopy(self.catalog)
        self.condition_profile(invalid)["conditions"] = []
        with self.assertRaisesRegex(VIEWER.ParseError, "needs at least one condition"):
            VIEWER.validate_behavior_catalog(invalid)

    def test_conditional_profile_requires_one_disabled_application(self) -> None:
        duplicate = copy.deepcopy(self.catalog)
        original = next(
            application for application in duplicate["applications"]
            if application["profile"] == "bird-rooftop"
        )
        extra = copy.deepcopy(original)
        extra["id"] = "apply-bird-rooftop-again"
        duplicate["applications"].append(extra)
        with self.assertRaisesRegex(VIEWER.ParseError, "exactly one application"):
            VIEWER.validate_behavior_catalog(duplicate)

        enabled = copy.deepcopy(self.catalog)
        application = next(
            application for application in enabled["applications"]
            if application["profile"] == "bird-rooftop"
        )
        application["target"]["mode"] = "all"
        with self.assertRaisesRegex(VIEWER.ParseError, "target must be disabled"):
            VIEWER.validate_behavior_catalog(enabled)

    def test_root_and_class_profiles_must_be_normal(self) -> None:
        invalid_root = copy.deepcopy(self.catalog)
        root = next(
            profile for profile in invalid_root["profiles"]
            if profile["id"] == invalid_root["rootProfile"]
        )
        root["kind"] = "conditional"
        root["conditions"] = [
            copy.deepcopy(self.condition_profile()["conditions"][0])
        ]
        with self.assertRaisesRegex(VIEWER.ParseError, "root profile must be normal"):
            VIEWER.validate_behavior_catalog(invalid_root)

        invalid_class = copy.deepcopy(self.catalog)
        class_profile = next(
            profile for profile in invalid_class["profiles"]
            if profile["id"] == "aggressive-chase"
        )
        class_profile["kind"] = "conditional"
        class_profile["conditions"] = [
            copy.deepcopy(self.condition_profile()["conditions"][0])
        ]
        with self.assertRaisesRegex(VIEWER.ParseError, "runtime class profile.*must be normal"):
            VIEWER.validate_behavior_catalog(invalid_class)

    def test_conditional_profile_must_inherit_from_normal_profile(self) -> None:
        invalid = copy.deepcopy(self.catalog)
        self.condition_profile(invalid)["parent"] = "canopy-hop-surface"
        with self.assertRaisesRegex(VIEWER.ParseError, "inherit from a normal profile"):
            VIEWER.validate_behavior_catalog(invalid)

    def test_condition_ids_are_unique_inside_profile(self) -> None:
        invalid = copy.deepcopy(self.catalog)
        profile = self.condition_profile(invalid)
        profile["conditions"].append(copy.deepcopy(profile["conditions"][0]))
        with self.assertRaisesRegex(VIEWER.ParseError, "condition id is duplicated"):
            VIEWER.validate_behavior_catalog(invalid)

    def test_activation_modes_enforce_timer_shape_and_bounds(self) -> None:
        while_true = copy.deepcopy(self.catalog)
        activation = self.condition_profile(while_true)["conditions"][0]["activation"]
        activation["durationFrames"] = 10
        with self.assertRaisesRegex(VIEWER.ParseError, "unknown durationFrames"):
            VIEWER.validate_behavior_catalog(while_true)

        timed = copy.deepcopy(self.catalog)
        activation = self.condition_profile(timed)["conditions"][0]["activation"]
        activation.clear()
        activation.update({
            "mode": "timed",
            "durationFrames": 0,
            "cooldownFrames": 120,
        })
        with self.assertRaisesRegex(VIEWER.ParseError, "durationFrames.*1..65535"):
            VIEWER.validate_behavior_catalog(timed)

        cooldown = copy.deepcopy(self.catalog)
        activation = self.condition_profile(cooldown)["conditions"][0]["activation"]
        activation.clear()
        activation.update({
            "mode": "timed",
            "durationFrames": 1,
            "cooldownFrames": 65536,
        })
        with self.assertRaisesRegex(VIEWER.ParseError, "cooldownFrames.*0..65535"):
            VIEWER.validate_behavior_catalog(cooldown)

    def test_notice_target_requires_a_target(self) -> None:
        invalid = copy.deepcopy(self.catalog)
        profile = self.condition_profile(invalid)
        profile["conditions"].append(
            self.notice_condition("condition-bird-notices-nothing", target={"kind": "none"})
        )
        with self.assertRaisesRegex(VIEWER.ParseError, "needs a player or actor target"):
            VIEWER.validate_behavior_catalog(invalid)

        terrain_target = copy.deepcopy(self.catalog)
        condition = self.condition_profile(terrain_target)["conditions"][0]
        condition["target"] = {"kind": "player"}
        with self.assertRaisesRegex(VIEWER.ParseError, "terrain-motion must be targetless"):
            VIEWER.validate_behavior_catalog(terrain_target)

    def test_terrain_motion_enforces_terrain_and_walk_time_bounds(self) -> None:
        terrain = copy.deepcopy(self.catalog)
        condition = self.condition_profile(terrain)["conditions"][0]
        condition["when"]["terrainMask"] = 1024
        with self.assertRaisesRegex(VIEWER.ParseError, "fit the current terrain bits"):
            VIEWER.validate_behavior_catalog(terrain)

        speed = copy.deepcopy(self.catalog)
        condition = self.condition_profile(speed)["conditions"][0]
        condition["when"]["maxMovementSpeed"] = 33
        with self.assertRaisesRegex(VIEWER.ParseError, "maxMovementSpeed.*0..32"):
            VIEWER.validate_behavior_catalog(speed)

        partial_speed = copy.deepcopy(self.catalog)
        condition = self.condition_profile(partial_speed)["conditions"][0]
        condition["when"]["minMovementSpeed"] = 1
        condition["when"]["maxMovementSpeed"] = 0
        VIEWER.validate_behavior_catalog(partial_speed)

        reversed_range = copy.deepcopy(self.catalog)
        condition = self.condition_profile(reversed_range)["conditions"][0]
        condition["when"]["minMovementSpeed"] = 20
        condition["when"]["maxMovementSpeed"] = 10
        with self.assertRaisesRegex(VIEWER.ParseError, "range is reversed"):
            VIEWER.validate_behavior_catalog(reversed_range)

        implicit_terrain = copy.deepcopy(self.catalog)
        condition = self.condition_profile(implicit_terrain)["conditions"][0]
        condition["when"]["terrainMask"] = 2
        condition["when"]["terrainOverrideMask"] = 1
        with self.assertRaisesRegex(VIEWER.ParseError, "enabled terrains must also be explicit"):
            VIEWER.validate_behavior_catalog(implicit_terrain)

        empty = copy.deepcopy(self.catalog)
        condition = self.condition_profile(empty)["conditions"][0]
        condition["when"]["terrainMask"] = 0
        condition["when"]["terrainOverrideMask"] = 0
        with self.assertRaisesRegex(VIEWER.ParseError, "must select a terrain or Walk-time"):
            VIEWER.validate_behavior_catalog(empty)

    def test_condition_subject_application_must_exist_and_be_normal(self) -> None:
        missing = copy.deepcopy(self.catalog)
        condition = self.condition_profile(missing)["conditions"][0]
        condition["subjects"]["application"] = "apply-missing"
        with self.assertRaisesRegex(VIEWER.ParseError, "missing application"):
            VIEWER.validate_behavior_catalog(missing)

        recursive = copy.deepcopy(self.catalog)
        condition = self.condition_profile(recursive)["conditions"][0]
        condition["subjects"]["application"] = "apply-bird-rooftop"
        with self.assertRaisesRegex(VIEWER.ParseError, "normal-profile application"):
            VIEWER.validate_behavior_catalog(recursive)

        disabled = copy.deepcopy(self.catalog)
        condition = self.condition_profile(
            disabled,
            "canopy-hop-surface",
        )["conditions"][0]
        condition["subjects"]["application"] = "apply-bird-rooftop"
        target_profile = next(
            profile for profile in disabled["profiles"]
            if profile["id"] == "bird-rooftop"
        )
        target_profile["kind"] = "normal"
        target_profile.pop("conditions")
        with self.assertRaisesRegex(VIEWER.ParseError, "has no subject pool"):
            VIEWER.validate_behavior_catalog(disabled)

    def test_actor_target_fields_are_bounded(self) -> None:
        invalid = copy.deepcopy(self.catalog)
        profile = self.condition_profile(invalid)
        profile["conditions"].append(self.notice_condition(
            "condition-bird-invalid-actor",
            target={
                "kind": "actor",
                "roles": ["wild", "wild"],
                "selection": "nearest",
                "groupMask": "OW_WILD_BEHAVIOR_GROUP_NONE",
                "members": [],
            },
        ))
        with self.assertRaisesRegex(VIEWER.ParseError, "roles must be unique"):
            VIEWER.validate_behavior_catalog(invalid)

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
