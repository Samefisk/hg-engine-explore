#!/usr/bin/env python3
"""S1 checks for the reusable Canopy Hopper capability contract.

These checks cover authored composition and the production entry seam. They do
not replace a live Wild movement scenario.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.verify_overworld_role_controller import function_bodies


class CanopyHopperCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(
            (ROOT / "data/overworld_behavior_profiles.json").read_text()
        )
        cls.profiles = {
            profile["id"]: profile for profile in cls.catalog["profiles"]
        }
        cls.applications = {
            application["id"]: application
            for application in cls.catalog["applications"]
        }
        source = (
            ROOT
            / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
        ).read_text()
        cls.bodies = function_bodies(source)

    def test_capability_owns_canopy_permission_and_entry_tuning(self) -> None:
        self.assertEqual(
            set(self.profiles["canopy-hopper"]["fields"]),
            {
                "chillAllowedTerrainMask",
                "chillAllowedTerrainOverrideMask",
            },
        )
        self.assertEqual(
            self.profiles["canopy-hopper"]["fields"]["chillAllowedTerrainMask"],
            {"operator": "replace", "value": 4},
        )
        self.assertEqual(
            self.profiles["canopy-hopper"]["fields"]["chillAllowedTerrainOverrideMask"],
            {"operator": "replace", "value": 4},
        )
        canopy_members = self.applications["apply-canopy-hopper"]["target"]["members"]
        self.assertIn("SPECIES_SENTRET", canopy_members)
        self.assertNotIn("SPECIES_MAREEP", canopy_members)

    def test_mankey_keeps_a_land_hopping_archetype(self) -> None:
        self.assertEqual(
            self.profiles["hopping-scavenger"]["fields"]["chillAction"],
            {"operator": "replace", "value": "OW_WILD_BEHAVIOR_LOCOMOTION_HOP"},
        )
        self.assertIn(
            "SPECIES_MANKEY",
            self.applications["apply-hopping-scavenger"]["target"]["members"],
        )
        self.assertNotIn(
            "SPECIES_MANKEY",
            self.applications["apply-nervous-scavenger"]["target"]["members"],
        )
        for species in ("SPECIES_MANKEY", "SPECIES_PRIMEAPE", "SPECIES_ANNIHILAPE"):
            self.assertNotIn(
                species,
                self.applications["apply-teleport-stalker-override"]["target"]["members"],
            )

    def test_canopy_child_owns_the_conditional_hop(self) -> None:
        profile = self.profiles["canopy-hop-surface"]
        self.assertEqual(profile["parent"], "canopy-hopper")
        self.assertEqual(profile["kind"], "conditional")
        self.assertEqual(
            set(profile["fields"]),
            {
                "chillAction",
                "hopAllowNonCardinal",
                "hopMinDistance",
                "hopMaxDistance",
                "hopTime",
                "hopElevationTimeScale",
                "hopElevationArcScale",
                "hopAllowVerticalObstacles",
            },
        )
        self.assertEqual(
            profile["fields"]["chillAction"]["value"],
            "OW_WILD_BEHAVIOR_LOCOMOTION_HOP",
        )
        self.assertEqual(
            profile["fields"]["hopAllowNonCardinal"]["value"],
            "OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_AND_DIAGONAL",
        )
        self.assertEqual(
            profile["fields"]["hopAllowVerticalObstacles"]["value"],
            "OW_WILD_BEHAVIOR_BOOL_YES",
        )
        condition = next(
            condition
            for condition in profile["conditions"]
            if condition["id"] == "condition-canopy-hopper-on-canopy"
        )
        self.assertEqual(
            condition["subjects"],
            {"application": "apply-canopy-hopper"},
        )
        self.assertEqual(
            condition["when"]["terrainMask"],
            "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY",
        )
        self.assertEqual(
            condition["when"]["terrainOverrideMask"],
            "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY",
        )

    def test_selected_canopy_target_hops_before_ground_collision(self) -> None:
        body = self.bodies["OverworldWildSpawns_TryStartCanopyEntryHop"]
        self.assertIn("OverworldWildSpawns_GetElevatedTerrainBit", body)
        self.assertIn("lane->chillAllowedTerrainMask", body)
        self.assertNotIn("conditionTerrain" + "Mask", body)
        self.assertNotIn("OverworldWildSpawns_ResolveBehaviorProfileForContext", body)
        self.assertIn("lane->chillAction != OW_WILD_BEHAVIOR_LOCOMOTION_HOP", body)
        self.assertIn("OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand", body)
        self.assertLess(
            body.index("OverworldWildSpawns_ClearWalkMovementState"),
            body.index("OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand"),
        )
        self.assertGreaterEqual(body.count("targetX"), 5)
        self.assertGreaterEqual(body.count("targetY"), 5)
        movement = self.bodies["OverworldWildSpawns_TryStartSingleDirectionMovementStep"]
        self.assertLess(
            movement.index("OverworldWildSpawns_TryStartCanopyEntryHop"),
            movement.index("MapObject_IsMovementDirectionBlocked"),
        )

    def test_ordinary_walkers_validate_catalogued_surfaces(self) -> None:
        body = self.bodies["OverworldWildSpawns_TryStartAcceleratedWalkStep"]
        self.assertIn(
            "call.stepFlags = OVERWORLD_ACTOR_WALK_STEP_VALIDATE;",
            body,
        )
        runtime = (
            ROOT
            / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
        ).read_text()
        reducer = function_bodies(runtime)["OverworldActorWalkPolicy_ReduceInput"]
        self.assertIn(
            "OVERWORLD_ACTOR_WALK_STEP_VALIDATE\n"
            "            | OVERWORLD_ACTOR_WALK_STEP_RESET_ACCELERATION",
            reducer,
        )

    def test_visual_checks_use_the_cached_resolved_profile(self) -> None:
        body = self.bodies["OverworldWildSpawns_IsCanopyHopperTreeTopSlot"]
        self.assertIn("OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot", body)
        self.assertIn("OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY", body)


if __name__ == "__main__":
    unittest.main()
