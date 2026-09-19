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
            evaluation["activeApplicationIds"], ["apply-bird-rooftop"]
        )
        self.assertEqual(
            evaluation["winningCondition"]["conditionId"],
            "condition-bird-rooftop",
        )
        self.assertIsNone(evaluation["targetSource"])
        layer = next(
            layer
            for layer in result["resolverLayers"]
            if layer["id"] == "apply-bird-rooftop"
        )
        self.assertTrue(layer["applied"])
        self.assertEqual(layer["profileKind"], "conditional")
        self.assertIn("chillState", {change["field"] for change in layer["changes"]})
        self.assertIn("apply-bird-rooftop", result["appliedApplicationIds"])

    def test_actor_target_timer_state_round_trips_and_role_filter_is_shared(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        profile = next(
            item for item in catalog["profiles"] if item["id"] == "bird-rooftop"
        )
        profile["conditions"].append(
            {
                "id": "condition-bird-notices-pikachu",
                "subjects": {"application": "apply-bird"},
                "when": {
                    "kind": "notice-target",
                    "rangeKind": "OW_WILD_BEHAVIOR_ALERT_RANGE_RADIUS",
                    "rangeLength": 5,
                    "chancePercent": 100,
                },
                "activation": {
                    "mode": "timed",
                    "durationFrames": 10,
                    "cooldownFrames": 20,
                },
                "target": {
                    "kind": "actor",
                    "roles": ["wild"],
                    "selection": "nearest",
                    "groupMask": "OW_WILD_BEHAVIOR_GROUP_NONE",
                    "members": ["SPECIES_PIKACHU"],
                },
            }
        )
        payload = self.payload(catalog, terrain_mask=65)
        payload["candidates"] = [
            {
                "id": "target-a",
                "species": "SPECIES_PIKACHU",
                "role": "wild",
                "valid": True,
                "x": 11,
                "y": 10,
            }
        ]

        first = reliability.resolve_conditional_preview(VIEWER, payload)
        evaluation = first["conditionEvaluation"]
        winner = evaluation["winningCondition"]
        self.assertEqual(winner["conditionId"], "condition-bird-notices-pikachu")
        rooftop = next(
            item
            for item in evaluation["entries"]
            if item["conditionId"] == "condition-bird-rooftop"
        )
        actor_entry = next(
            item
            for item in evaluation["entries"]
            if item["conditionId"] == "condition-bird-notices-pikachu"
        )
        self.assertFalse(rooftop["winsProfile"])
        self.assertTrue(actor_entry["winsProfile"])
        self.assertEqual(
            evaluation["targetSource"]["target"],
            {"kind": "actor", "candidateId": "target-a"},
        )
        state = next(
            item
            for item in evaluation["nextState"]
            if item["conditionId"] == "condition-bird-notices-pikachu"
        )
        self.assertEqual(state["activeUntil"], 110)
        self.assertEqual(state["cooldownUntil"], 120)

        payload["observation"]["frame"] = 105
        payload["candidates"][0]["x"] = 30
        payload["candidates"][0]["y"] = 30
        payload["conditionState"] = evaluation["nextState"]
        second = reliability.resolve_conditional_preview(VIEWER, payload)
        held = next(
            item
            for item in second["conditionEvaluation"]["entries"]
            if item["conditionId"] == "condition-bird-notices-pikachu"
        )
        self.assertFalse(held["conditionTrue"])
        self.assertTrue(held["active"])
        self.assertFalse(held["triggered"])

        payload["observation"]["frame"] = 100
        payload["candidates"][0].update({"role": "follower", "x": 11, "y": 10})
        payload["conditionState"] = []
        filtered = reliability.resolve_conditional_preview(VIEWER, payload)
        actor_entry = next(
            item
            for item in filtered["conditionEvaluation"]["entries"]
            if item["conditionId"] == "condition-bird-notices-pikachu"
        )
        self.assertTrue(actor_entry["subjectMatched"])
        self.assertFalse(actor_entry["conditionTrue"])
        self.assertFalse(actor_entry["active"])


if __name__ == "__main__":
    unittest.main()
