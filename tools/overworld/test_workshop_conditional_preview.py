"""Workshop proof that preview uses the shared condition evaluator and resolver."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
V2_TOOLS = REPO / "tools/overworld-viewer-v2"
if str(V2_TOOLS) not in sys.path:
    sys.path.insert(0, str(V2_TOOLS))

import reliability  # noqa: E402


def load_viewer():
    path = REPO / "scripts/overworld_behavior_profile_viewer.py"
    spec = importlib.util.spec_from_file_location("workshop_preview_test_viewer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIEWER = load_viewer()


class WorkshopConditionalPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(
            (REPO / "data/overworld_behavior_profiles.json").read_text()
        )

    def payload(self, catalog: dict, *, terrain_mask: int = 1) -> dict:
        return {
            "profileCatalog": {"catalog": catalog},
            "subject": {
                "species": "SPECIES_PIDGEY",
                "level": 20,
                "terrain": "OW_WILD_SPAWN_TERRAIN_LAND",
                "shiny": False,
                "behaviorClass": "auto",
            },
            "observation": {
                "frame": 100,
                "x": 10,
                "y": 10,
                "facing": 3,
                "terrainMask": terrain_mask,
                "movementSpeed": 8,
                "player": {"valid": True, "x": 13, "y": 10},
            },
            "candidates": [],
            "conditionState": [],
        }

    def test_saved_terrain_condition_reports_shared_resolver_provenance(self) -> None:
        result = reliability.resolve_conditional_preview(
            VIEWER,
            self.payload(self.catalog, terrain_mask=64),
        )

        evaluation = result["conditionEvaluation"]
        self.assertEqual(
            evaluation["activeApplicationIds"],
            ["apply-perch"],
        )
        self.assertEqual(
            evaluation["winningCondition"]["conditionId"],
            "condition-perch-on-elevated-surface",
        )
        self.assertIsNone(evaluation["targetSource"])
        layer = next(
            layer
            for layer in result["resolverLayers"]
            if layer["id"] == "apply-perch"
        )
        self.assertTrue(layer["applied"])
        self.assertEqual(layer["profileKind"], "conditional")
        self.assertIn("chillState", {change["field"] for change in layer["changes"]})
        self.assertIn("apply-perch", result["appliedApplicationIds"])

    def test_condition_owner_above_255_uses_subject_local_slots(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        applications = catalog["applications"]
        style = next(a for a in applications if a["id"] == "apply-waddle")
        expressions, order = VIEWER.parse_define_expressions(VIEWER.DEFINE_SOURCE_FILES)
        macros = VIEWER.evaluate_defines(expressions)
        species = VIEWER.parse_species(expressions, macros, order)[:270]
        self.assertEqual(len(species), 270)
        additions = []
        for index, entry in enumerate(species):
            application = copy.deepcopy(style)
            application["id"] = f"preview-growth-{index}"
            application["target"]["members"] = [entry["symbol"]]
            additions.append(application)
        insertion = applications.index(style) + 1
        applications[insertion:insertion] = additions
        runtime = VIEWER._runtime_source_behavior_catalog(catalog)["applications"]
        self.assertGreater(next(i for i, a in enumerate(runtime)
            if a["id"] == "apply-playful"), 255)

        payload = self.payload(catalog)
        payload["subject"]["species"] = "SPECIES_CLEFAIRY"
        payload["observation"]["player"]["valid"] = False
        payload["candidates"] = [{"id": "target-a", "species": "SPECIES_CLEFABLE",
            "role": "wild", "valid": True, "x": 11, "y": 10}]
        result = reliability.resolve_conditional_preview(
            VIEWER, payload)
        evaluation = result["conditionEvaluation"]
        self.assertEqual(evaluation["activeApplicationIds"], ["apply-find-playmate", "apply-playful"])
        self.assertEqual(evaluation["winningCondition"]["applicationId"], "apply-playful")
        entry = next(entry for entry in evaluation["entries"]
            if entry["applicationId"] == "apply-playful")
        self.assertTrue(entry["winsProfile"])
        self.assertIn("apply-playful", result["appliedApplicationIds"])

    def test_current_roster_rejects_two_generations_in_one_slot(self) -> None:
        candidate = {"id": "target-a", "species": "SPECIES_CLEFABLE", "role": "wild",
            "handle": {"slot": 1, "generation": 1}}
        payload = self.payload(self.catalog)
        payload["candidates"] = [candidate, {**candidate, "id": "target-b",
            "handle": {"slot": 1, "generation": 2}}]
        with self.assertRaisesRegex(ValueError, "candidate slots must be unique"):
            reliability.resolve_conditional_preview(VIEWER, payload)
        payload["candidates"] = [{**candidate, "handle": {"slot": 0, "generation": 2}}]
        with self.assertRaisesRegex(ValueError, "subject slot has a different current identity"):
            reliability.resolve_conditional_preview(VIEWER, payload)

    def test_actor_target_timer_state_round_trips_and_role_filter_is_shared(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        playful = next(
            profile for profile in catalog["profiles"]
            if profile["id"] == "find-playmate"
        )
        playful["conditions"][0]["target"]["roles"] = ["wild"]
        payload = self.payload(catalog, terrain_mask=65)
        payload["subject"]["species"] = "SPECIES_CLEFAIRY"
        payload["observation"]["player"]["valid"] = False
        payload["candidates"] = [
            {
                "id": "target-a",
                "species": "SPECIES_CLEFABLE",
                "role": "wild",
                "valid": True,
                "x": 11,
                "y": 10,
            }
        ]

        first = reliability.resolve_conditional_preview(VIEWER, payload)
        evaluation = first["conditionEvaluation"]
        winner = evaluation["winningCondition"]
        self.assertEqual(winner["conditionId"], "condition-playful-next-to-playmate")
        actor_entry = next(
            item
            for item in evaluation["entries"]
            if item["conditionId"] == "condition-find-playmate-notices-compatible-actor"
        )
        self.assertTrue(actor_entry["winsProfile"])
        self.assertEqual(
            evaluation["targetSource"]["target"],
            {"kind": "actor", "candidateId": "target-a"},
        )
        state = next(
            item
            for item in evaluation["nextState"]
            if item["conditionId"] == "condition-find-playmate-notices-compatible-actor"
        )
        self.assertEqual(state["activeUntil"], 520)
        self.assertEqual(state["cooldownUntil"], 530)

        payload["bindings"] = evaluation["bindings"]
        payload["bindingOwner"] = evaluation["bindingOwner"]
        payload["observation"]["frame"] = 105
        payload["candidates"][0]["x"] = 30
        payload["candidates"][0]["y"] = 30
        payload["conditionState"] = evaluation["nextState"]
        second = reliability.resolve_conditional_preview(VIEWER, payload)
        held = next(
            item
            for item in second["conditionEvaluation"]["entries"]
            if item["conditionId"] == "condition-find-playmate-notices-compatible-actor"
        )
        self.assertFalse(held["conditionTrue"])
        self.assertTrue(held["active"])
        self.assertFalse(held["triggered"])

        payload["observation"]["frame"] = 100
        payload["candidates"][0].update({"role": "follower", "x": 11, "y": 10})
        payload["conditionState"] = []
        payload.pop("bindings", None)
        payload.pop("bindingOwner", None)
        filtered = reliability.resolve_conditional_preview(VIEWER, payload)
        actor_entry = next(
            item
            for item in filtered["conditionEvaluation"]["entries"]
            if item["conditionId"] == "condition-find-playmate-notices-compatible-actor"
        )
        self.assertTrue(actor_entry["subjectMatched"])
        self.assertFalse(actor_entry["conditionTrue"])
        self.assertFalse(actor_entry["active"])


if __name__ == "__main__":
    unittest.main()
