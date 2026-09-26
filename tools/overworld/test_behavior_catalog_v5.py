"""Focused checks for the structural behavior-authoring v5 foundation."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
VIEWER_PATH = REPO / "scripts/overworld_behavior_profile_viewer.py"
MIGRATOR = REPO / "scripts/migrate_overworld_behavior_catalog_v4_to_v5.py"
CLASSIFICATIONS = [
    "routine",
    "placement",
    "capability",
    "attitude",
    "style",
    "follower-mount",
    "modifier",
]


def load_viewer():
    spec = importlib.util.spec_from_file_location(
        "behavior_catalog_v5_test_viewer", VIEWER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {VIEWER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIEWER = load_viewer()


class BehaviorCatalogV5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.v5 = json.loads(VIEWER.BEHAVIOR_CATALOG_SOURCE.read_text())
        VIEWER.validate_behavior_catalog(cls.v5)
        cls.v4 = VIEWER._runtime_source_behavior_catalog(cls.v5)

    def test_schema_has_the_exact_classification_order_and_pool_shapes(self) -> None:
        schema = json.loads(VIEWER.BEHAVIOR_AUTHORING_SCHEMA_V5.read_text())
        self.assertEqual(schema["$id"], "behavior-authoring-v5.schema.json")
        self.assertEqual(schema["properties"]["catalogVersion"]["const"], 5)
        self.assertEqual(schema["$defs"]["profileClassification"]["enum"], CLASSIFICATIONS)
        self.assertIn(
            "classification",
            schema["$defs"]["conditionalProfile"]["required"],
        )
        self.assertEqual(
            schema["$defs"]["normalProfile"]["allOf"][0]["then"]["required"],
            ["classification"],
        )
        self.assertIn("pools", schema["required"])
        self.assertEqual(
            schema["$defs"]["namedPool"]["required"],
            ["id", "name", "mode", "match", "members"],
        )
        self.assertNotIn("pool", schema["$defs"]["namedPool"]["properties"])

    def test_migration_is_non_mutating_valid_and_idempotent(self) -> None:
        original = copy.deepcopy(self.v4)
        migrated = VIEWER.migrate_behavior_catalog_v4_to_v5(self.v4)
        self.assertEqual(self.v4, original)
        VIEWER.validate_behavior_catalog(migrated)
        self.assertEqual(migrated["catalogVersion"], 5)
        self.assertEqual(migrated["schema"], VIEWER.BEHAVIOR_CATALOG_SCHEMA_V5)
        self.assertIn("pools", migrated)
        self.assertEqual(
            VIEWER.migrate_behavior_catalog_v4_to_v5(migrated),
            migrated,
        )

    def test_v5_requires_a_classification_on_every_non_root_profile(self) -> None:
        changed = copy.deepcopy(self.v5)
        profile = next(
            item for item in changed["profiles"]
            if item["id"] != changed["rootProfile"]
        )
        profile.pop("classification")
        with self.assertRaisesRegex(
            VIEWER.ParseError,
            "classification is required for every non-root profile",
        ):
            VIEWER.validate_behavior_catalog(changed)

    def test_v5_applications_follow_classification_group_order(self) -> None:
        changed = copy.deepcopy(self.v5)
        routine_index = next(
            index for index, application in enumerate(changed["applications"])
            if next(
                profile for profile in changed["profiles"]
                if profile["id"] == application["profile"]
            )["classification"] == "routine"
        )
        modifier_index = next(
            index for index, application in enumerate(changed["applications"])
            if next(
                profile for profile in changed["profiles"]
                if profile["id"] == application["profile"]
            )["classification"] == "modifier"
        )
        changed["applications"][routine_index], changed["applications"][modifier_index] = (
            changed["applications"][modifier_index],
            changed["applications"][routine_index],
        )
        with self.assertRaisesRegex(
            VIEWER.ParseError,
            "breaks application classification order",
        ):
            VIEWER.validate_behavior_catalog(changed)

    def test_mounted_is_a_visible_empty_system_override(self) -> None:
        mounted_application_id = self.v5["runtimeBindings"]["mountedApplication"]
        mounted_application = next(
            application
            for application in self.v5["applications"]
            if application["id"] == mounted_application_id
        )
        mounted_profile = next(
            profile
            for profile in self.v5["profiles"]
            if profile["id"] == mounted_application["profile"]
        )

        self.assertEqual(mounted_profile["name"], "Mounted")
        self.assertEqual(mounted_profile["classification"], "follower-mount")
        self.assertEqual(mounted_profile["fields"], {})
        self.assertNotIn("target", mounted_application)

    def test_migration_moves_subject_ownership_without_changing_runtime_projection(self) -> None:
        profiles = {profile["id"]: profile for profile in self.v5["profiles"]}
        for application in self.v5["applications"]:
            if profiles[application["profile"]]["kind"] == "conditional":
                self.assertNotIn("target", application)
        self.assertFalse(any(
            set(condition["subjects"]) == {"application"}
            for profile in self.v5["profiles"]
            for condition in profile.get("conditions", [])
        ))

        v4_runtime = VIEWER.project_behavior_catalog_runtime(self.v4)
        v5_runtime = VIEWER.project_behavior_catalog_runtime(self.v5)
        v4_runtime.pop("catalogVersion")
        v5_runtime.pop("catalogVersion")
        self.assertEqual(v5_runtime, v4_runtime)
        source = VIEWER.BEHAVIOR_DATA_SOURCE.read_text()
        header = VIEWER.BEHAVIOR_DATA_HEADER.read_text()
        self.assertEqual(
            VIEWER.render_behavior_catalog(self.v5, source),
            VIEWER.render_behavior_catalog(self.v4, source),
        )
        self.assertEqual(
            VIEWER.render_behavior_catalog_header(header, self.v5, source),
            VIEWER.render_behavior_catalog_header(header, self.v4, source),
        )

    def test_named_pool_references_lower_for_all_three_supported_owners(self) -> None:
        changed = copy.deepcopy(self.v5)
        normal_application = next(
            application
            for application in changed["applications"]
            if "target" in application and set(application["target"]) != {"pool"}
        )
        assignment_pool = {
            "id": "assignment-pool",
            "name": "Assignment Pool",
            **copy.deepcopy(normal_application["target"]),
        }
        normal_application["target"] = {"pool": assignment_pool["id"]}

        conditional_profile = next(
            profile for profile in changed["profiles"]
            if profile["kind"] == "conditional"
            and profile["conditions"][0]["when"]["kind"] == "notice-target"
        )
        condition = conditional_profile["conditions"][0]
        subject_source = condition["subjects"]
        if set(subject_source) == {"pool"}:
            subject_source = next(
                pool for pool in changed["pools"]
                if pool["id"] == subject_source["pool"]
            )
        subject_pool = {
            "id": "subject-pool",
            "name": "Subject Pool",
            "mode": subject_source["mode"],
            "match": copy.deepcopy(subject_source["match"]),
            "members": copy.deepcopy(subject_source["members"]),
        }
        condition["subjects"] = {"pool": subject_pool["id"]}

        actor_pool = {
            "id": "actor-target-pool",
            "name": "Actor Target Pool",
            "mode": "members",
            "match": VIEWER.default_behavior_match_raws(),
            "members": ["SPECIES_BULBASAUR"],
        }
        condition["target"] = {
            "kind": "actor",
            "roles": ["wild"],
            "selection": "nearest",
            "pool": actor_pool["id"],
        }
        changed["pools"].extend([assignment_pool, subject_pool, actor_pool])

        VIEWER.validate_behavior_catalog(changed)
        lowered = VIEWER._runtime_source_behavior_catalog(changed)
        lowered_application = next(
            item for item in lowered["applications"]
            if item["id"] == normal_application["id"]
        )
        self.assertEqual(
            lowered_application["target"],
            {
                "mode": assignment_pool["mode"],
                "match": assignment_pool["match"],
                "members": assignment_pool["members"],
            },
        )
        lowered_profile = next(
            profile for profile in lowered["profiles"]
            if profile["id"] == conditional_profile["id"]
        )
        lowered_condition = lowered_profile["conditions"][0]
        if "application" in lowered_condition["subjects"]:
            lowered_subject_application = next(
                item for item in lowered["applications"]
                if item["id"] == lowered_condition["subjects"]["application"]
            )
            self.assertEqual(
                lowered_subject_application["target"]["members"],
                subject_pool["members"],
            )
        else:
            self.assertEqual(
                lowered_condition["subjects"]["members"],
                subject_pool["members"],
            )
        self.assertEqual(
            lowered_condition["target"],
            {
                "kind": "actor",
                "roles": ["wild"],
                "selection": "nearest",
                "groupMask": actor_pool["match"]["groupMask"],
                "members": actor_pool["members"],
            },
        )

    def test_v5_rejects_ambiguous_or_recursive_ownership(self) -> None:
        conditional = copy.deepcopy(self.v5)
        profiles = {profile["id"]: profile for profile in conditional["profiles"]}
        conditional_application = next(
            item for item in conditional["applications"]
            if profiles[item["profile"]]["kind"] == "conditional"
        )
        conditional_application["target"] = {
            "mode": "all",
            "match": VIEWER.default_behavior_match_raws(),
            "members": [],
        }
        with self.assertRaisesRegex(VIEWER.ParseError, "must not have a target"):
            VIEWER.validate_behavior_catalog(conditional)

        unowned = copy.deepcopy(self.v5)
        normal_application = next(
            item for item in unowned["applications"] if "target" in item
        )
        normal_application.pop("target")
        with self.assertRaisesRegex(VIEWER.ParseError, "target or an explicit link"):
            VIEWER.validate_behavior_catalog(unowned)

        borrowed = copy.deepcopy(self.v5)
        profile = next(item for item in borrowed["profiles"] if item["kind"] == "conditional")
        profile["conditions"][0]["subjects"] = {"application": "apply-flying-insect"}
        with self.assertRaisesRegex(VIEWER.ParseError, "cannot reference another application"):
            VIEWER.validate_behavior_catalog(borrowed)

        recursive = copy.deepcopy(self.v5)
        recursive["pools"] = [{
            "id": "recursive-pool",
            "name": "Recursive Pool",
            "mode": "all",
            "match": VIEWER.default_behavior_match_raws(),
            "members": [],
            "pool": "recursive-pool",
        }]
        with self.assertRaisesRegex(VIEWER.ParseError, "unknown pool"):
            VIEWER.validate_behavior_catalog(recursive)

    def test_v5_vision_conditions_lower_to_compact_runtime_fields(self) -> None:
        changed = copy.deepcopy(self.v5)
        profile = next(
            item for item in changed["profiles"]
            if item["kind"] == "conditional"
            and item["conditions"][0]["when"]["kind"] == "notice-target"
        )
        condition = profile["conditions"][0]
        condition["when"] = {
            "kind": "notice-target",
            "vision": {"mode": "current"},
            "chancePercent": 100,
        }
        VIEWER.validate_behavior_catalog(changed)
        lowered = VIEWER._runtime_source_behavior_catalog(changed)
        lowered_profile = next(
            item for item in lowered["profiles"] if item["id"] == profile["id"]
        )
        self.assertEqual(
            lowered_profile["conditions"][0]["when"],
            {
                "kind": "notice-target",
                "rangeKind": "OW_WILD_BEHAVIOR_CONDITION_RANGE_VISION_CURRENT",
                "rangeLength": 0,
                "chancePercent": 100,
                "visionOptions": 0,
            },
        )

        condition["when"] = {
            "kind": "target-cannot-see-subject",
            "vision": {
                "mode": "custom",
                "range": 7,
                "cone": "forward-90",
                "adjacentAwareness": True,
            },
            "chancePercent": 80,
        }
        VIEWER.validate_behavior_catalog(changed)
        lowered = VIEWER._runtime_source_behavior_catalog(changed)
        lowered_profile = next(
            item for item in lowered["profiles"] if item["id"] == profile["id"]
        )
        self.assertEqual(
            lowered_profile["conditions"][0]["when"],
            {
                "kind": "target-cannot-see-subject",
                "rangeKind": "OW_WILD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM",
                "rangeLength": 7,
                "chancePercent": 80,
                "visionOptions": 5,
            },
        )
        rendered = VIEWER.render_behavior_catalog(
            changed, VIEWER.BEHAVIOR_DATA_SOURCE.read_text()
        )
        self.assertIn(
            "OW_WILD_BEHAVIOR_CONDITION_TARGET_CANNOT_SEE_SUBJECT",
            rendered,
        )

    def test_conditional_profile_cannot_override_its_stable_vision(self) -> None:
        changed = copy.deepcopy(self.v5)
        profile = next(item for item in changed["profiles"] if item["kind"] == "conditional")
        profile["fields"]["visionRange"] = {"operator": "replace", "value": 9}
        with self.assertRaisesRegex(VIEWER.ParseError, "cannot override Vision"):
            VIEWER.validate_behavior_catalog(changed)

    def test_migration_command_dry_run_is_deterministic_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="behavior-v5-migration-") as raw_temp:
            temp = Path(raw_temp)
            source = temp / "input.json"
            output = temp / "output.json"
            source.write_text(json.dumps(self.v4, indent=2) + "\n")
            command = [
                sys.executable,
                str(MIGRATOR),
                "--input", str(source),
                "--output", str(output),
                "--dry-run",
            ]
            first = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
            second = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(
                json.loads(first.stdout),
                VIEWER.migrate_behavior_catalog_v4_to_v5(self.v4),
            )
            self.assertFalse(output.exists())
            self.assertEqual(json.loads(source.read_text()), self.v4)

    def test_migration_command_fails_closed_on_unexpected_input(self) -> None:
        with tempfile.TemporaryDirectory(prefix="behavior-v5-invalid-") as raw_temp:
            temp = Path(raw_temp)
            source = temp / "input.json"
            output = temp / "output.json"
            source.write_text('{"catalogVersion": 99}\n')
            result = subprocess.run(
                [
                    sys.executable,
                    str(MIGRATOR),
                    "--input", str(source),
                    "--output", str(output),
                ],
                cwd=REPO,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("version 4 or already-migrated version 5", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
