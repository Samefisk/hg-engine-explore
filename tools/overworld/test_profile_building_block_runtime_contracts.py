"""Permanent PB9 registration checks; these do not grant live runtime proof."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from tools.overworld.devtools_profile_feature_proof import CONTRACTS as EVALUATOR_CONTRACTS


ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "tests/overworld/scenarios"
REGISTRY = ROOT / "tools/overworld/runtime_proof_registry.json"
FEATURES = ROOT / "tools/overworld/system_features.yaml"
CATALOG = ROOT / "data/overworld_behavior_profiles.json"


CONTRACTS = {
    "profile.notice-player.routine-return": {
        "requirement": "current.notice-player-routine-return",
        "capabilities": ["condition.evaluation", "alert"],
        "subjects": [(179, "WILD")],
        "claims": ["live-actor-identity", "profile-resolution", "feedback-effect",
                   "rendered-motion", "frame-pacing", "control-release"],
        "facts": {
            "notice-player-presentation-pause-frames": 10,
            "notice-player-exclamation-count": 1,
            "notice-player-post-pause-routine-and-repeat-counts": [1, 0],
        },
    },
    "profile.stalker.visibility-gate": {
        "requirement": "current.stalker-visibility-gate",
        "capabilities": ["condition.evaluation", "vision", "chase"],
        "subjects": [(92, "WILD")],
        "claims": ["live-actor-identity", "profile-resolution", "engine-boundary",
                   "rendered-motion", "control-release"],
        "facts": {
            "stalker-unseen-seen-and-routine-motion-counts": [1, 0, 1],
            "stalker-seen-routine-resume-count": 1,
        },
    },
    "profile.playful.target-and-collision": {
        "requirement": "current.playful-target-and-collision",
        "capabilities": ["condition.evaluation", "alert", "chase"],
        "subjects": [(35, "WILD"), (36, "WILD")],
        "claims": ["live-actor-identity", "profile-resolution", "collision-decision",
                   "logical-commit", "rendered-motion", "control-release"],
        "facts": {
            "playful-target-tile-rejection-counts": [1, 1],
            "playful-noncolliding-terminal-commit-count": 2,
        },
    },
    "profile.startled.timed-retreat": {
        "requirement": "current.startled-timed-retreat",
        "capabilities": ["condition.evaluation", "alert", "chase"],
        "subjects": [(69, "WILD")],
        "claims": ["live-actor-identity", "profile-resolution", "engine-boundary",
                   "rendered-motion", "frame-pacing", "control-release"],
        "facts": {
            "startled-active-frame-count": 44,
            "startled-post-expiry-routine-resume-count": 1,
        },
    },
    "spawn.fly-in.uneven-height": {
        "requirement": "current.fly-in-uneven-height",
        "capabilities": ["spawn"],
        "subjects": [(16, "WILD")],
        "claims": ["live-actor-identity", "profile-resolution", "terrain-selection",
                   "logical-commit", "rendered-motion", "frame-pacing", "control-release"],
        "facts": {
            "fly-in-origin-target-height-delta": 0,
            "fly-in-monotonic-and-terminal-height-errors": [0, 0, 0, 0],
            "fly-in-open-ground-shadow-observations": 1,
            "fly-in-suppressed-surface-shadow-errors": 0,
            "fly-in-ground-height-count": 2,
            "fly-in-duration-frames": 144,
            "fly-in-routine-control-return-count": 1,
        },
    },
    "profile.waddle.walk-presentation-only": {
        "requirement": "current.waddle-walk-presentation-only",
        "capabilities": ["walk"],
        "subjects": [(69, "WILD")],
        "claims": ["live-actor-identity", "profile-resolution", "logical-commit",
                   "rendered-motion", "frame-pacing", "control-release"],
        "facts": {
            "waddle-changed-walk-sample-fields": ["swayOffset"],
            "waddle-non-walk-sway-sample-count": 0,
        },
    },
    "profile.floaty-bounce-hop-pause": {
        "requirement": "current.floaty-bounce-hop-pause",
        "capabilities": ["hop"],
        "subjects": [(39, "WILD")],
        "claims": ["live-actor-identity", "profile-resolution", "logical-commit",
                   "rendered-motion", "frame-pacing", "control-release"],
        "facts": {
            "floaty-resolved-hop-contract": [2, 12, 10],
            "floaty-hop-duration-errors": 0,
            "floaty-two-hop-pause-frames": [10, 10],
        },
    },
    "actor.held-control-resume": {
        "requirement": "current.held-actor-control-resume",
        "capabilities": ["actor.system"],
        "subjects": [(56, "WILD"), (19, "WILD")],
        "claims": ["live-actor-identity", "profile-resolution", "controlled-action",
                   "engine-boundary", "rendered-motion", "control-release"],
        "facts": {
            "held-no-picked-up-profile-and-class-equality": [0, 1],
            "held-control-mode-sequence": ["AUTONOMOUS", "HELD", "AUTONOMOUS"],
            "held-during-and-after-autonomous-intent-counts": [0, 1],
        },
    },
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def measurements(contract: dict) -> dict[str, dict]:
    return {
        measurement["name"]: measurement
        for claim in contract.values()
        for measurement in claim
    }


class ProfileBuildingBlockRuntimeContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load(REGISTRY)
        cls.features = load(FEATURES)
        cls.catalog = load(CATALOG)
        cls.scenarios = {
            scenario_id: load(SCENARIOS / f"{scenario_id}.json")
            for scenario_id in CONTRACTS
        }

    def test_each_exact_claim_has_an_active_runtime_adapter(self) -> None:
        for scenario_id, expected in CONTRACTS.items():
            with self.subTest(scenario=scenario_id):
                scenario = self.scenarios[scenario_id]
                self.assertEqual(scenario["id"], scenario_id)
                self.assertEqual(scenario["status"], "active")
                self.assertEqual(scenario["adapter"]["kind"], "devtools-test")
                self.assertEqual(scenario["adapter"]["test"], scenario_id)
                self.assertEqual(scenario["adapter"]["claims"], expected["claims"])
                self.assertEqual(scenario["proofLevel"], "S3" if scenario_id !=
                                 "spawn.fly-in.uneven-height" and scenario_id !=
                                 "profile.waddle.walk-presentation-only" and scenario_id !=
                                 "profile.floaty-bounce-hop-pause" else "S4")
                self.assertEqual(scenario["capabilities"], expected["capabilities"])
                self.assertEqual(
                    [(subject["species"], subject["role"])
                     for subject in scenario["subjects"]],
                    expected["subjects"],
                )
                self.assertEqual(scenario["verification"]["setupAudit"], "complete")
                self.assertTrue(scenario["verification"]["limits"])

    def test_registry_keeps_exact_unweakened_acceptance_measurements(self) -> None:
        runners = self.registry["runners"]
        kinds = self.registry["runnerKinds"]
        registered = self.registry["sharedTests"]
        contracts = self.registry["measurementContracts"]
        for expected in CONTRACTS.values():
            requirement = expected["requirement"]
            with self.subTest(requirement=requirement):
                self.assertEqual(kinds[requirement], "controlled-case")
                self.assertEqual(runners[requirement], expected["claims"])
                registration = registered[next(
                    scenario_id for scenario_id, test in registered.items()
                    if requirement in test.get("requirements", []))]
                self.assertEqual(registration["requirements"], [requirement])
                self.assertEqual(registration["claims"], expected["claims"])
                self.assertEqual(registration["measurementContract"],
                                 contracts[requirement])
                self.assertEqual(
                    registration["measurementContract"],
                    EVALUATOR_CONTRACTS[registration["evaluator"]],
                )
                contract = contracts[requirement]
                self.assertEqual(list(contract), expected["claims"])
                by_name = measurements(contract)
                for name, value in expected["facts"].items():
                    self.assertIn(name, by_name)
                    row = by_name[name]
                    if row["operator"] == "ne":
                        self.assertEqual((row["expected"], value), (0, 0))
                    elif row["operator"] == "gte":
                        self.assertEqual(row["minimum"], value)
                    else:
                        self.assertEqual(row["expected"], value)

    def test_feature_map_links_scenarios_both_ways(self) -> None:
        capabilities = {item["id"]: item for item in self.features["capabilities"]}
        check = next(item for item in self.features["checks"]
                     if item["id"] == "host.pb9-profile-building-block-scenarios")
        self.assertEqual(check["command"][-1],
                         "tools/overworld/test_profile_building_block_runtime_contracts.py")
        for scenario_id, expected in CONTRACTS.items():
            for capability_id in expected["capabilities"]:
                with self.subTest(scenario=scenario_id, capability=capability_id):
                    capability = capabilities[capability_id]
                    self.assertIn(scenario_id, capability["scenarios"])
                    self.assertIn("host.pb9-profile-building-block-scenarios",
                                  capability["checks"])

    def test_scenario_contracts_match_current_authored_values(self) -> None:
        profiles = {item["id"]: item for item in self.catalog["profiles"]}
        self.assertEqual(profiles["notice-player"]["fields"]["alertTime"]["value"], 10)
        notice = profiles["notice-player"]["conditions"][0]
        self.assertEqual(notice["id"], "condition-notice-player")
        self.assertEqual(notice["activation"], {
            "mode": "timed", "durationFrames": 960, "cooldownFrames": 970})

        stalker = profiles["stalker"]["conditions"][0]
        self.assertEqual(stalker["id"], "condition-stalker-unseen-by-player")
        self.assertEqual(stalker["when"]["kind"], "target-cannot-see-subject")
        self.assertEqual(stalker["activation"], {"mode": "while-true"})

        playful = profiles["playful"]["conditions"]
        self.assertEqual([item["id"] for item in playful], [
            "condition-playful-notices-compatible-actor",
            "condition-playful-notices-player",
        ])
        self.assertEqual([item["target"]["kind"] for item in playful],
                         ["actor", "player"])

        startled = profiles["startled"]["conditions"][0]
        self.assertEqual(startled["activation"], {
            "mode": "timed", "durationFrames": 44, "cooldownFrames": 164})
        self.assertEqual(profiles["fly-in"]["fields"]["spawnState"]["value"],
                         "OW_WILD_BEHAVIOR_SPAWN_STATE_FLY_IN")
        self.assertEqual(profiles["waddle"]["fields"]["walkSwayWidth"]["value"], 4)
        floaty = profiles["floaty-bounce"]["fields"]
        self.assertEqual(floaty["chillAction"]["value"],
                         "OW_WILD_BEHAVIOR_LOCOMOTION_HOP")
        self.assertEqual(floaty["hopTime"]["value"], 12)
        self.assertEqual(floaty["hopPause"]["value"], 10)
        application = next(item for item in self.catalog["applications"]
                           if item["id"] == "apply-floaty-bounce")
        self.assertEqual(application["profile"], "floaty-bounce")
        self.assertTrue({"SPECIES_JIGGLYPUFF", "SPECIES_IGGLYBUFF"}
                        <= set(application["target"]["members"]))
        self.assertNotIn("picked-up", profiles)


if __name__ == "__main__":
    unittest.main()
