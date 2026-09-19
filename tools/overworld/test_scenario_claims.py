"""Host proof of scenario scope and runtime result-contract enforcement.

These tests check the test tools. They do not constitute ROM behavior proof.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools.overworld import control, validation
from tools.overworld.test_host_verification import retained_scenario_contract
from tools.overworld.control import _run_command, _roadmap_contract_audit
from tools.overworld.validation import (
    RuntimeProofSourceAudit,
    ValidationFailure,
    cross_validate,
    load_feature_manifest,
    load_scenarios,
    validate_scenario,
)


REPO = Path(__file__).resolve().parents[2]
SCENARIOS = REPO / "tests/overworld/scenarios"
LEDYBA_RUNNER = "legacy.ledyba-chain-pause"


class ScenarioClaimRecipeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = SCENARIOS / "chain.pause.counts-semantic-moves.json"
        self.scenario = retained_scenario_contract(self.path)

    def test_existing_forced_ledyba_case_declares_its_actual_scope(self) -> None:
        validated = validate_scenario(self.scenario, self.path)
        recipe = validated["verification"]
        self.assertEqual(recipe["kind"], "controlled-case")
        self.assertEqual(recipe["setupAudit"], "complete")
        self.assertEqual(
            {item["target"] for item in recipe["setupMutations"]
             if item["phase"] == "during-observation"},
            {"rng", "control-result", "counters"},
        )
        self.assertIn("controlled-action", validated["adapter"]["claims"])
        self.assertNotIn("natural-input", validated["adapter"]["claims"])

    def test_runtime_scenario_cannot_omit_verification_recipe(self) -> None:
        del self.scenario["verification"]
        with self.assertRaisesRegex(ValidationFailure, "verification"):
            validate_scenario(self.scenario, self.path)

    def test_recipe_rejects_wrong_types_and_missing_claim_fields(self) -> None:
        for field in ("kind", "expectationSource", "actor", "trigger", "observable"):
            for value in (None, [], {}, 0, True, ""):
                with self.subTest(field=field, value=value):
                    scenario = copy.deepcopy(self.scenario)
                    scenario["verification"][field] = value
                    with self.assertRaises(ValidationFailure):
                        validate_scenario(scenario, self.path)
        for field in ("setupAudit", "setupMutations", "limits"):
            with self.subTest(field=field):
                scenario = copy.deepcopy(self.scenario)
                del scenario["verification"][field]
                with self.assertRaises(ValidationFailure):
                    validate_scenario(scenario, self.path)

    def test_normal_play_rejects_unreviewed_setup(self) -> None:
        self.scenario["verification"].update(
            kind="normal-play", setupAudit="pending", setupMutations=[]
        )
        with self.assertRaisesRegex(ValidationFailure, "complete setup mutation audit"):
            validate_scenario(self.scenario, self.path)

    def test_normal_play_rejects_hidden_case_mutations(self) -> None:
        for phase, target in (
            ("before-observation", "actors"),
            ("before-observation", "profile"),
            ("before-observation", "counters"),
            ("before-observation", "rng"),
            ("before-observation", "control-result"),
            ("during-observation", "position"),
        ):
            with self.subTest(phase=phase, target=target):
                self.scenario["verification"].update(
                    kind="normal-play", setupAudit="complete",
                    setupMutations=[{
                        "phase": phase, "target": target, "change": "Force case state.",
                    }],
                )
                with self.assertRaisesRegex(ValidationFailure, "normal-play cannot force"):
                    validate_scenario(self.scenario, self.path)

    def test_observer_control_requires_a_distinct_failure_boundary(self) -> None:
        recipe = self.scenario["verification"]
        recipe["kind"] = "observer-control"
        with self.assertRaisesRegex(ValidationFailure, "control"):
            validate_scenario(self.scenario, self.path)
        recipe["control"] = {
            "boundary": "recorded-evidence",
            "fault": "Remove a captured event.",
            "expectedFailure": "The evaluator rejects the missing event.",
        }
        self.assertEqual(
            validate_scenario(self.scenario, self.path)["verification"]["control"]["boundary"],
            "recorded-evidence",
        )
        recipe["control"]["boundary"] = "negative-control"
        with self.assertRaises(ValidationFailure):
            validate_scenario(self.scenario, self.path)

    def test_normal_and_control_recipes_keep_exact_port_or_pending_requirements(self) -> None:
        migration = json.loads((REPO / "tools/overworld/runtime_proof_migration.json").read_text())
        registry = json.loads((REPO / "tools/overworld/runtime_proof_registry.json").read_text())
        ported = {
            "legacy.ledyba-normal-profile": ("chain.ledyba-witness", 5000),
            "legacy.live-observer-controls": ("observation.ledyba-live-controls", 16),
            "legacy.unmounted-long-travel": ("world.unmounted.long-travel-cadence", 5000),
            "legacy.live-route-observer-controls": ("observation.live-route-control", 4),
        }
        for scenario_id, key, kind, species, role in (
            ("chain.pause.ledyba-normal-profile", "legacy.ledyba-normal-profile", "normal-play", 165, "WILD"),
            ("world.unmounted.long-travel-cadence", "legacy.unmounted-long-travel", "normal-play", 155, "FOLLOWER"),
            ("observation.live-actor-and-motion-control", "legacy.live-observer-controls", "observer-control", 165, "WILD"),
            ("observation.live-route-control", "legacy.live-route-observer-controls", "observer-control", 155, "FOLLOWER"),
        ):
            with self.subTest(scenario_id=scenario_id):
                path = SCENARIOS / f"{scenario_id}.json"
                scenario = validate_scenario(json.loads(path.read_text()), path)
                requirement = migration["requirements"][key]
                if key in ported:
                    from tools.overworld.control import _shared_test_registration
                    name, minimum_frames = ported[key]
                    test = json.loads((REPO / "tests/overworld/test-recipes" / (name + ".json")).read_text())
                    registration, _ = _shared_test_registration(test, REPO)
                    self.assertEqual(scenario["status"], "active")
                    self.assertEqual(scenario["adapter"], {"kind": "devtools-test", "test": name,
                        "claims": registry["runners"][key],
                        "minimumFrames": minimum_frames})
                    self.assertEqual(registration["requirements"], [key])
                    self.assertEqual(registration["claims"], requirement["claims"])
                    self.assertEqual(requirement["status"], "ported")
                    self.assertEqual(requirement["tests"], [name])
                else:
                    self.assertEqual(scenario["status"], "planned")
                    self.assertIsNone(scenario["adapter"])
                    self.assertEqual(requirement["status"], "pending")
                    self.assertEqual(requirement["tests"], [])
                self.assertEqual(scenario["verification"]["kind"], kind)
                self.assertEqual(scenario["verification"]["setupAudit"], "complete")
                subject = scenario["subjects"][0]
                self.assertEqual((subject["species"], subject["role"]), (species, role))
                self.assertEqual(requirement["claims"], registry["runners"][key])
                self.assertIn(scenario_id, requirement["scenarios"])
                self.assertFalse("passed" in scenario)

    def test_split_control_receipts_are_independently_required_by_roadmap(self) -> None:
        manifest = load_feature_manifest(REPO / "tools/overworld/system_features.yaml")
        scenarios = {key: retained_scenario_contract(SCENARIOS / f"{key}.json")
                     for key in json.loads((REPO / "tools/overworld/runtime_proof_migration.json").read_text())["historicalScenarios"]}
        controls = ("observation.live-actor-and-motion-control", "observation.live-route-control")
        actor = next(item for item in manifest["capabilities"] if item["id"] == "actor.system")
        self.assertTrue(set(controls).issubset(actor["scenarios"]))
        # These are upstream-accepted receipt fixtures, not manufactured live proof.
        receipts = {key: {"manifest": "host-receipt-fixture"} for key in scenarios}
        self.assertEqual(_roadmap_contract_audit(manifest, scenarios, [], receipts)
                         ["runtimeScenarioEvidenceGaps"], [])
        for missing in controls:
            with self.subTest(missing=missing):
                result = _roadmap_contract_audit(manifest, scenarios, [],
                    {key: value for key, value in receipts.items() if key != missing})
                self.assertEqual([item["id"] for item in result["runtimeScenarioEvidenceGaps"]], [missing])

    def test_planned_normal_recipe_cannot_activate_before_setup_audit(self) -> None:
        path = SCENARIOS / "chain.pause.ledyba-normal-profile.json"
        scenario = validate_scenario(retained_scenario_contract(path), path)
        adapter = scenario["adapter"]
        scenario["status"] = "planned"
        scenario["adapter"] = None
        scenario["verification"]["setupAudit"] = "pending"
        validate_scenario(scenario, path)
        scenario["status"] = "active"
        scenario["adapter"] = adapter
        with self.assertRaisesRegex(ValidationFailure, "complete setup mutation audit"):
            validate_scenario(scenario, path)


class RegistryClaimContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_feature_manifest(REPO / "tools/overworld/system_features.yaml")
        cls.scenarios = load_scenarios(SCENARIOS)
        cls.registry = json.loads(
            (REPO / "tools/overworld/runtime_proof_registry.json").read_text()
        )

    def check_registry(self, registry, *, scenarios=None) -> None:
        original = validation.load_json_document

        def load(path):
            if path.name == "runtime_proof_registry.json":
                return registry
            return original(path)

        with mock.patch.object(validation, "load_json_document", side_effect=load):
            cross_validate(self.manifest, scenarios or self.scenarios, REPO)

    def test_catalog_and_registry_are_consistent(self) -> None:
        self.check_registry(self.registry)

    def test_runner_kind_must_match_scenario_kind(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["runnerKinds"][LEDYBA_RUNNER] = "normal-play"
        with self.assertRaisesRegex(ValidationFailure, "changed its original measurement contract"):
            self.check_registry(registry)

    def test_registry_requires_an_independent_measurement_rule(self) -> None:
        registry = copy.deepcopy(self.registry)
        measurement = registry["measurementContracts"][LEDYBA_RUNNER]["controlled-action"][0]
        del measurement["expected"]
        with self.assertRaisesRegex(ValidationFailure, "no independent acceptance rule"):
            self.check_registry(registry)

    def test_observer_control_does_not_make_gameplay_proof_feasible(self) -> None:
        manifest = {
            "_capabilityIds": {"test.behavior"},
            "_scenarioReferences": {"test.observer"},
            "checks": [],
            "capabilities": [{
                "id": "test.behavior", "checks": [],
                "scenarios": ["test.observer"], "minimumProof": ["S3"],
            }],
        }
        scenarios = {"test.observer": {
            "capabilities": ["test.behavior"], "proofLevel": "S3",
            "verification": {"kind": "observer-control"},
        }}
        with self.assertRaisesRegex(ValidationFailure, "minimum proof S3 has no linked scenario"):
            cross_validate(manifest, scenarios)
        scenarios["test.observer"]["verification"]["kind"] = "controlled-case"
        cross_validate(manifest, scenarios)

    def test_observer_control_cannot_supply_explicit_gameplay_role_witness(self) -> None:
        scenarios = copy.deepcopy(self.scenarios)
        scenario = scenarios["world.transition.follower-rebind"]
        scenario["verification"]["kind"] = "observer-control"
        scenario["roleProof"] = [{
            "role": "Follower", "claim": "live-actor-identity",
            "measurement": "follower-transition-role",
        }]
        registry = copy.deepcopy(self.registry)
        registry["runnerKinds"][
            "legacy.follower-transition"
        ] = "observer-control"
        with self.assertRaisesRegex(ValidationFailure, "observer-control cannot supply gameplay role proof"):
            self.check_registry(registry, scenarios=scenarios)

    def test_registry_rejects_mismatched_claim_sets_and_nonstring_claims(self) -> None:
        for claims in (["logical-commit"], [{}]):
            with self.subTest(claims=claims):
                registry = copy.deepcopy(self.registry)
                registry["runners"][LEDYBA_RUNNER] = claims
                with self.assertRaises(ValidationFailure):
                    self.check_registry(registry)

    def test_expectation_source_must_exist(self) -> None:
        scenarios = copy.deepcopy(self.scenarios)
        scenarios["chain.pause.counts-semantic-moves"]["verification"]["expectationSource"] = (
            "documentation/this-requirement-does-not-exist.md"
        )
        with self.assertRaisesRegex(ValidationFailure, "expectation source does not exist"):
            self.check_registry(self.registry, scenarios=scenarios)

    def test_retained_identity_measurement_names_cannot_change_without_a_new_contract(self) -> None:
        registry = copy.deepcopy(self.registry)
        for index, item in enumerate(
            registry["measurementContracts"][LEDYBA_RUNNER]["live-actor-identity"]
        ):
            item["name"] = f"subject-identity-{index}"
        with self.assertRaisesRegex(ValidationFailure, "changed its original measurement contract"):
            self.check_registry(registry)

    def test_private_state_checks_remain_active_after_shape_refactor(self) -> None:
        audit = RuntimeProofSourceAudit(
            "def collect_case():\n    return MOUNT\n"
            "SCENARIOS = {'case': collect_case}\n"
        )
        self.assertTrue(audit.audit("case", public_actor_evidence=True))
