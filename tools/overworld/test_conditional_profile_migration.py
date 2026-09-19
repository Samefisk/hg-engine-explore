"""Durable CP6 mapping and host semantics for the Active-profile migration."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tools/overworld/fixtures/conditional_profile_migration_v1.json"
VIEWER_PATH = ROOT / "scripts/overworld_behavior_profile_viewer.py"
V2_TOOLS = ROOT / "tools/overworld-viewer-v2"
if str(V2_TOOLS) not in sys.path:
    sys.path.insert(0, str(V2_TOOLS))

import native_resolver  # noqa: E402


def load_viewer():
    spec = importlib.util.spec_from_file_location(
        "conditional_profile_migration_viewer", VIEWER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {VIEWER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIEWER = load_viewer()


class ConditionalProfileMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(
            (ROOT / "data/overworld_behavior_profiles.json").read_text()
        )
        cls.fixture = json.loads(FIXTURE.read_text())
        cls.profiles = {
            profile["id"]: profile for profile in cls.catalog["profiles"]
        }
        cls.application_indexes = {
            application["id"]: index
            for index, application in enumerate(cls.catalog["applications"])
        }
        _, sources = VIEWER._catalog_condition_layout(cls.catalog)
        cls.conditions = {
            source["condition"]["id"]: source for source in sources
        }
        cls.schema = json.loads(
            (ROOT / "tools/overworld/behavior_schema.json").read_text()
        )
        cls.temporary = tempfile.TemporaryDirectory(
            prefix="conditional-profile-migration-"
        )
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.resolver = native_resolver.build(
            ROOT,
            force=True,
            output=Path(cls.temporary.name) / "resolver",
        )

    @classmethod
    def owner_field(cls, result: dict, field_key: str) -> int:
        field = next(
            item for item in cls.schema["fields"] if item["key"] == field_key
        )
        raw = bytes.fromhex(result["profileHex"])
        width = {"u8": 1, "u16": 2}[field["cType"]]
        value = int.from_bytes(
            raw[field["offset"]:field["offset"] + width], "little"
        )
        if "bitOffset" in field:
            value >>= field["bitOffset"]
            value &= (1 << field["bitWidth"]) - 1
        return value

    def test_every_legacy_active_reference_has_one_recorded_home(self) -> None:
        self.assertEqual(self.fixture["version"], 1)
        self.assertEqual(
            [mapping["legacySourceProfile"] for mapping in self.fixture["mappings"]],
            [
                "default",
                "flying-insect",
                "nervous-scavenger",
                "hopping-scavenger",
                "baby-pokemon",
                "swaying-plant",
                "ambush-plant",
            ],
        )
        for mapping in self.fixture["mappings"]:
            with self.subTest(mapping=mapping["legacySourceProfile"]):
                profile = self.profiles[mapping["conditionalProfile"]]
                self.assertEqual(profile["kind"], "conditional")
                self.assertEqual(
                    set(profile["fields"]), set(mapping["responseFields"])
                )
                application = self.catalog["applications"][
                    self.application_indexes[mapping["conditionalApplication"]]
                ]
                self.assertEqual(application["profile"], profile["id"])
                self.assertEqual(application["target"]["mode"], "disabled")
                for condition_id in mapping["conditionIds"]:
                    self.assertEqual(
                        self.conditions[condition_id]["profile"]["id"],
                        profile["id"],
                    )

    def test_old_terrain_records_are_profile_owned_conditions(self) -> None:
        for migration in self.fixture["terrainMigrations"]:
            with self.subTest(profile=migration["conditionalProfile"]):
                source = self.conditions[migration["conditionId"]]
                self.assertEqual(
                    source["profile"]["id"], migration["conditionalProfile"]
                )
                self.assertEqual(
                    source["condition"]["when"]["kind"], "terrain-motion"
                )

    def test_notice_disabled_test_profile_is_outside_the_default_pool(self) -> None:
        class_profiles = {
            binding["symbol"]: binding["profile"]
            for binding in self.catalog["runtimeBindings"]["classOrder"]
        }
        self.assertEqual(class_profiles["OW_WILD_BEHAVIOR_CLASS_TEST"], "test")
        selector = next(
            item for item in self.catalog["selectors"]
            if item["id"] == "select-mewtwo-test"
        )
        self.assertEqual(selector["profile"], "test")
        default_condition = self.conditions[
            "condition-default-notices-player"
        ]["condition"]
        self.assertEqual(
            default_condition["subjects"]["match"]["behaviorClass"],
            "OW_WILD_BEHAVIOR_CLASS_DEFAULT",
        )

    def test_migrated_response_fields_resolve_in_application_order(self) -> None:
        for case in self.fixture["semanticCases"]:
            application_index = self.application_indexes[
                case["conditionalApplication"]
            ]
            condition_id = self.conditions[case["conditionId"]]["conditionId"]
            base_request = {
                "species": case["species"],
                "level": 5,
                "terrain": 0,
                "shiny": 0,
                "groupFlags": 0,
                "behaviorClass": "auto",
                "requestVersion": 2,
            }
            inactive = native_resolver.resolve(
                None,
                base_request,
                root=ROOT,
                executable=self.resolver,
            )
            active = native_resolver.resolve(
                None,
                {
                    **base_request,
                    "activeConditionalMask": 1 << application_index,
                    "winningConditionId": condition_id,
                    "resolvedTarget": {"kind": "player"},
                    "targetSourceApplication": application_index,
                    "resolvedTargetConditionId": condition_id,
                },
                root=ROOT,
                executable=self.resolver,
            )
            with self.subTest(case=case["id"]):
                self.assertEqual(active["status"], 0)
                self.assertTrue(active["appliedOverrideMask"] & (1 << application_index))
                self.assertEqual(active["targetSourceApplication"], application_index)
                for field, expected in case["expectedOwnerFields"].items():
                    self.assertEqual(self.owner_field(active, field), expected)
                if not case["expectedOwnerFields"]:
                    self.assertEqual(active["profileHex"], inactive["profileHex"])

    def test_host_adapter_rejects_removed_request_inputs(self) -> None:
        for request, message in (
            ({"requestVersion": 1}, "unsupported native resolver requestVersion 1"),
            ({"requestVersion": 0}, "unsupported native resolver requestVersion 0"),
            ({"conditionInputMode": "explicit"}, "conditionInputMode was removed"),
            ({"conditionTerrainMask": 1}, "conditionTerrainMask was removed"),
        ):
            with self.subTest(request=request), self.assertRaisesRegex(
                ValueError, message
            ):
                native_resolver.resolve(
                    None,
                    request,
                    root=ROOT,
                    executable=self.resolver,
                )


if __name__ == "__main__":
    unittest.main()
