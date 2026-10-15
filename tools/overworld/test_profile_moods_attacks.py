"""Moods/Attacks authoring controls; labels never supply combat fields."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "moods_attacks_viewer", REPO / "scripts/overworld_behavior_profile_viewer.py"
)
assert spec is not None and spec.loader is not None
VIEWER = importlib.util.module_from_spec(spec)
spec.loader.exec_module(VIEWER)
sys.path.insert(0, str(REPO / "tools/overworld-viewer-v2"))
import native_resolver


class ProfileMoodsAttacksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(VIEWER.BEHAVIOR_CATALOG_SOURCE.read_text())
        VIEWER.validate_behavior_catalog(cls.catalog)

    def test_angry_is_empty_normal_unassigned_and_first(self) -> None:
        profile = next(p for p in self.catalog["profiles"] if p["id"] == "angry")
        self.assertEqual(profile, {
            "id": "angry", "name": "Angry", "parent": "default",
            "kind": "normal", "classification": "mood", "fields": {},
        })
        app = self.catalog["applications"][0]
        self.assertEqual(app["id"], "apply-angry")
        self.assertEqual(app["profile"], "angry")
        self.assertEqual(app["target"], {
            "mode": "disabled", "match": VIEWER.default_behavior_match_raws(),
            "members": [],
        })
        runtime = VIEWER._runtime_source_behavior_catalog(self.catalog)
        self.assertEqual(runtime["applications"][0]["target"]["mode"], "disabled")

    def test_only_empty_normal_assignments_allow_disabled_target(self) -> None:
        malformed = copy.deepcopy(self.catalog)
        malformed["applications"][0]["target"]["members"] = ["SPECIES_RATTATA"]
        with self.assertRaisesRegex(VIEWER.ParseError, "unassigned target must have no members"):
            VIEWER.validate_behavior_catalog(malformed)

        malformed = copy.deepcopy(self.catalog)
        conditional = next(p for p in malformed["profiles"] if p["id"] == "ram")
        conditional["conditions"][0]["subjects"] = copy.deepcopy(
            malformed["applications"][0]["target"]
        )
        with self.assertRaisesRegex(VIEWER.ParseError, "mode must be members or all"):
            VIEWER.validate_behavior_catalog(malformed)

    def test_attacks_group_contains_damage_not_setup_and_keeps_basic_disabled(self) -> None:
        profiles = {p["id"]: p for p in self.catalog["profiles"]}
        attacks = [a["profile"] for a in self.catalog["applications"]
                   if profiles[a["profile"]]["classification"] == "attack"]
        self.assertEqual(attacks, [
            "throw-release", "ram", "basic-attack", "ambush", "stomp-slam",
            "throw-away",
        ])
        actual_damage = {
            p["id"] for p in profiles.values()
            if p["fields"].get("attacking", {}).get("value") in (1, "1")
            and int(p["fields"].get("collisionDamage", {}).get("value", 0)) > 0
        }
        self.assertEqual(set(attacks), actual_damage | {"throw-away"})
        for profile_id in ("throw", "throw-find-position"):
            self.assertEqual(profiles[profile_id]["classification"], "capability")
            self.assertEqual(int(profiles[profile_id]["fields"]["attacking"]["value"]), 0)
        basic = next(a for a in self.catalog["applications"] if a["id"] == "apply-basic-attack")
        self.assertIs(basic["enabled"], False)
        classes = list(VIEWER.PROFILE_CLASSIFICATIONS_V5)
        self.assertLess(classes.index("mood"), classes.index("routine"))
        self.assertEqual(classes.index("attack"), classes.index("capability") + 1)

    def test_attack_tag_on_assigned_empty_angry_grants_no_damage_in_production_c(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        next(p for p in catalog["profiles"] if p["id"] == "angry")["classification"] = "attack"
        app = catalog["applications"].pop(0)
        app["target"] = {
            "mode": "members", "match": VIEWER.default_behavior_match_raws(),
            "members": ["SPECIES_RATTATA"],
        }
        profiles = {p["id"]: p for p in catalog["profiles"]}
        first_attack = next(i for i, a in enumerate(catalog["applications"])
                            if profiles[a["profile"]]["classification"] == "attack")
        catalog["applications"].insert(first_attack, app)
        VIEWER.validate_behavior_catalog(catalog)
        # Native build generates into this private temporary directory; it does
        # not write the checked-in compatibility source or header.
        with tempfile.TemporaryDirectory(prefix="moods-attacks-") as raw_temp:
            temp = Path(raw_temp)
            catalog_file = temp / "catalog.json"
            catalog_file.write_text(json.dumps(catalog))
            exe = native_resolver.build(REPO, catalog=catalog_file, output=temp / "resolver")
            result = native_resolver.resolve_many(None, [{
                "requestVersion": 2, "species": 19, "level": 50,
                "terrain": 0, "groupFlags": 0,
            }], root=REPO, executable=exe)[0]
        self.assertEqual(result["status"], 0)
        runtime = VIEWER._runtime_source_behavior_catalog(catalog)
        angry_index = next(i for i, a in enumerate(runtime["applications"])
                           if a["id"] == "apply-angry")
        self.assertTrue(any(step["kind"] == 3 and step["sourceIndex"] == angry_index
                            for step in result["trace"]), "the empty tagged profile must actually match")
        owner = VIEWER.decode_native_profile({}, result["profileHex"], 0)
        self.assertEqual(owner["attacking"]["value"], 0)
        self.assertEqual(owner["collisionDamage"]["value"], 0)
        self.assertEqual(owner["minImpactSpeed"]["value"], 0)


if __name__ == "__main__":
    unittest.main()
