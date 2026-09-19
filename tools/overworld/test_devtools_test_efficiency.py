"""Pure setup-cost accounting; no emulator or gameplay proof."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_efficiency import setup_efficiency_report


def action(name="walk", op="step", args=None):
    return {"id": name, "op": op, "args": {"frames": 1, "keys": ["UP"]} if args is None else args,
            "budget": {"maxSeconds": 10, "maxFrames": 16, "noProgressFrames": 8}}


def test_data(setup, kind="unmounted-cadence-v1", mode="normal"):
    return {"setup": setup, "measurements": [{"kind": kind}], "mode": mode,
            "budgets": {"maxSeconds": 20, "maxFrames": 40},
            "actions": [action("long-route")], "requirements": ["unchanged-movement-floor"]}


class EfficiencyTests(unittest.TestCase):
    def test_sums_all_setup_ceilings_not_runtime_or_observation_actions(self):
        conditional = action("optional")
        conditional["skipIf"] = {"kind": "party-field", "slot": 1, "path": "hp", "operator": "eq", "value": 21}
        value = test_data([action(), conditional, action("heal-party", "party", {"slot": 1, "hp": 21})], mode="prepared")
        before = deepcopy(value)
        report = setup_efficiency_report(value)
        self.assertEqual(report["setupActionCount"], 3)
        self.assertEqual(report["setupBudgetCeilings"], {"maxSeconds": 30, "maxFrames": 48})
        self.assertEqual(report["preparedOperationCount"], 1)
        self.assertIn("not estimated runtime", report["budgetNote"])
        self.assertEqual(report["warnings"], [])
        self.assertEqual(value, before)

    def test_typed_dialogue_in_each_setup_predicate_position_warns(self):
        predicate = {"kind": "dialogue-state", "state": "page-wait"}
        for position in ("predicate", "until", "skipIf"):
            with self.subTest(position=position):
                row = action("page-ready")
                if position == "skipIf": row[position] = predicate
                else: row["args"][position] = predicate
                report = setup_efficiency_report(test_data([row]))
                self.assertEqual(report["warnings"][0]["code"], "avoidable-dialogue-setup")
                self.assertEqual(report["warnings"][0]["actionIds"], ["page-ready"])

    def test_action_names_and_a_input_do_not_supply_dialogue_evidence(self):
        for name in ("nurse-start-a", "healed-page-a", "door-a", "nursewalk"):
            with self.subTest(name=name):
                report = setup_efficiency_report(test_data([action(name, args={"frames": 1, "keys": ["A"]})]))
                self.assertEqual(report["warnings"], [])

    def test_real_nurse_recipe_converted_to_cadence_is_flagged(self):
        from tools.overworld.devtools_test_contract import validate_test
        root = Path(__file__).resolve().parents[2]
        value = json.loads((root / "tests/overworld/test-recipes/world.cyndaquil-normal-setup.json").read_text())
        diagnostic = setup_efficiency_report(validate_test(value))
        self.assertEqual(diagnostic["warnings"], [])
        value["measurements"][0]["kind"] = "unmounted-cadence-v1"
        predicates = list(value["assertions"])
        for action in value["setup"] + value["actions"]:
            predicates.extend(p for p in (action["args"].get("predicate"),
                action["args"].get("until"), action.get("skipIf")) if p is not None)
        for predicate in predicates:
            if predicate.get("kind") == "measurement-complete":
                predicate["measurement"] = "unmounted-cadence-v1"
        report = setup_efficiency_report(validate_test(value))
        self.assertEqual(report["warnings"][0]["code"], "avoidable-dialogue-setup")
        self.assertIn("nurse-start-ready", report["warnings"][0]["actionIds"])
        self.assertEqual(report["setupBudgetCeilings"], diagnostic["setupBudgetCeilings"])

    def test_actual_setup_diagnostics_are_exempt_but_still_accounted(self):
        for kind in ("cyndaquil-normal-setup-v1", "center-entry-exit-v1"):
            report = setup_efficiency_report(test_data([
                action("nurse-a", args={"frames": 1, "keys": ["A"]}),
                action("dialogue", "wait", {"predicate": {"kind": "dialogue-state", "state": "idle"}})], kind))
            self.assertEqual(report["warnings"], [])
            self.assertEqual(report["setupActionCount"], 2)

    def test_prepared_operations_are_counted_not_rejected_or_warned_generically(self):
        value = test_data([action(op, op, {}) for op in ("party", "teleport", "spawn")], mode="prepared")
        report = setup_efficiency_report(value)
        self.assertEqual(report["preparedOperationCount"], 3)
        self.assertEqual(report["warnings"], [])
        self.assertNotIn("passed", report)
        self.assertNotIn("acceptedProof", report)

    def test_empty_or_large_plain_setup_has_no_arbitrary_length_warning(self):
        for count in (0, 2000):
            report = setup_efficiency_report(test_data([action(str(n)) for n in range(count)]))
            self.assertEqual(report["setupActionCount"], count)
            self.assertEqual(report["warnings"], [])
