"""Copied completed-frame controls for the natural pre-Cargo carrier hit."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld import test_devtools_test_contract as contract_tests
from tools.overworld.devtools_follower_throw_hit_abort_measurement import (
    KIND, NOTICE, CARGO, THROW_APP, RAM_APP,
    FollowerThrowHitAbortMeasurement, validate_recipe,
)
from tools.overworld.devtools_follower_throw_hit_abort_proof import (
    FAULTS, FollowerThrowHitAbortNegative, measurements,
)
from tools.overworld.proof_adapters import ADAPTERS


ROOT = Path(__file__).resolve().parents[2]
CONTEXT = {"mapId": 33, "fieldEpoch": 3, "mapGeneration": 3}


def actor(slot, species, role, x):
    handle = {"value": (2 << 16) | slot, "slot": slot, "generation": 2,
              "fieldEpoch": 3, "mapGeneration": 3, "encounterGeneration": 1}
    return {"handle": handle, "subjectIdentity": 100 + slot, "species": species,
            "role": role, "active": True, "identityVerified": True,
            "presentationAttached": True, "authorityGeneration": 1,
            "engineAnchorGeneration": 1, "presentationGeneration": 1,
            "logical": {"x": x, "y": 402}, "motionKind": "WALK" if slot else "NONE",
            "motionPhase": "MOVING" if slot else "IDLE",
            "matchedLayerMask": (1 << RAM_APP) if slot else (1 << THROW_APP)}


def row(frame):
    mankey = actor(0, 56, "FOLLOWER", 606)
    onix = actor(1, 95, "WILD", 602)
    captured = frame in (1, 2, 3, 4) or frame >= 6
    notice = int(captured)
    binding = lambda condition, bound: {"bound": bound, "targetCurrent": bound,
        "sourceConditionId": condition, "sourceApplication": THROW_APP,
        "target": {"kind": "ACTOR", "actor": deepcopy(onix["handle"])} if bound
                  else {"kind": "NONE", "actor": None}}
    carrier = {"available": True, "role": "FOLLOWER", "handle": mankey["handle"],
               "bindings": {"trigger": binding(NOTICE, captured),
                            "cargo": binding(CARGO, False)},
               "throw": {"carrier": False, "targetRaw": 0,
                         "targetSlot": None, "carried": False,
                         "windup": False}}
    target = {"handle": mankey["handle"], "role": "FOLLOWER", "species": 56,
              "hpMirrorMatches": True, "hpSource": "party", "maxHp": 48,
              "actualMaxHp": 48, "currentHp": 48 if frame < 4 else 24,
              "hp": 48 if frame < 4 else 24,
              "hitCount": 0 if frame < 4 else 1,
              "lastDamage": 0 if frame < 4 else 24,
              "immunityFrames": 0 if frame < 4 else 60}
    identity = {"romSha256": "a" * 64}
    interaction = {"schemaVersion": 1, "available": True, "frame": frame,
                   "nativeCycle": 1000 + frame,
                   "observationBoundary": "main-task-queue-completion",
                   "identity": identity, "carriers": [carrier]}
    owner = {"actor": deepcopy(mankey), "context": CONTEXT}
    conditions = {"available": True, "frame": frame, "owner": owner,
                  "states": [{"application": THROW_APP, "conditionId": NOTICE,
                              "flags": notice, "targetKind": 2 if captured else 0,
                              "targetSlot": 1 if captured else 0,
                              "targetGeneration": 2 if captured else 0,
                              "targetEncounterGeneration": 1 if captured else 0}]}
    sample = {"frame": frame, "actorFrame": frame, "nativeCycle": 1000 + frame,
              "romSha256": "a" * 64, "fieldAvailable": True,
              "observationBoundary": "main-task-queue-completion",
              "fieldControl": {"taskPointer": 0}, "context": CONTEXT,
              "player": {"x": 607, "y": 402}, "actors": [mankey, onix],
              "pokemonCombat": {"schemaVersion": 1, "available": True,
                                "frame": frame, "nativeCycle": 1000 + frame,
                                "observationBoundary": "main-task-queue-completion",
                                "identity": identity, "targets": [target],
                                "interactions": interaction},
              "pokemonAppearance": {"schemaVersion": 1, "available": True,
                                    "frame": frame, "nativeCycle": 1000 + frame,
                                    "observationBoundary": "main-task-queue-completion",
                                    "identity": identity, "conditions": {"0": conditions}}}
    return {"samples": [sample], "events": []}


class FollowerThrowHitAbortHostTests(unittest.TestCase):
    def test_prepared_current_mankey_follower_has_checked_handoff(self):
        recipe = validate_test(json.loads((ROOT / "tests/overworld/test-recipes/follower.throw-hit-abort.json").read_text()))
        self.assertLess(next(i for i, a in enumerate(recipe["setup"]) if a["id"] == "spawn-onix"),
                        next(i for i, a in enumerate(recipe["setup"]) if a["id"] == "bind-mankey"))
        _, source = contract_tests.RamLedgeAuxiliaryFollowerTests().fixture()
        for fault in (None, "personality", "moving", "lifecycle"):
            evaluator = TestEvaluator(recipe)
            evaluator.install_measurements({KIND: {"contractVersion": 1}})
            evaluator.latest = deepcopy(source["receipt"]["snapshot"])
            evaluator.latest["frame"] = 1
            evaluator.latest["nativeCycle"] = 1
            evaluator.latest["actors"] = []
            row = deepcopy(source)
            row["action"] = "create-mankey"
            row["snapshot"]["actors"][0].update(species=56, level=20)
            row["receipt"]["requestedSubject"].update(species=56, level=20)
            if fault == "personality":
                row["receipt"]["requestedSubject"]["personality"] += 1
            elif fault == "moving":
                row["snapshot"]["actors"][0]["motionPhase"] = "MOVING"
            elif fault == "lifecycle":
                row["receipt"]["lifecycle"] = "spawn-prepared"
            result = evaluator.observe_prepared_command(row)
            with self.subTest(fault=fault):
                self.assertEqual(result["state"] == "failed", fault is not None)
                if fault is None:
                    self.assertEqual(evaluator.subjects, {})
                    self.assertEqual(evaluator.measurements[KIND].prepared, [])

    def test_exact_recipe(self):
        recipe = validate_test(json.loads((ROOT / "tests/overworld/test-recipes/follower.throw-hit-abort.json").read_text()))
        validate_recipe(recipe)
        self.assertEqual(ADAPTERS[KIND].requirement, "current.follower-throw-hit-abort")
        changed = deepcopy(recipe)
        changed["setup"][0]["args"]["x"] = 606
        with self.assertRaises(ValueError):
            validate_recipe(changed)

    def test_hit_clears_and_same_target_rebinds_with_copied_controls(self):
        rows = [row(frame) for frame in range(15)]
        meter = FollowerThrowHitAbortMeasurement()
        for entry in rows:
            result = meter.observe(entry["samples"][0], entry["events"])
        self.assertTrue(result["passed"], result["failures"])
        record = {"sessionId": "host", "sessionCleanup": {
            "sessionId": "host", "closed": True, "errors": []}}
        proof = measurements({"passed": True, "failures": [],
                              "measurements": {KIND: result}}, record)
        self.assertEqual(len(proof), 6)
        for fault in FAULTS:
            control = FollowerThrowHitAbortNegative(fault)
            meter = FollowerThrowHitAbortMeasurement()
            for entry in rows:
                changed = control.mutate(entry, meter.subjects)
                for sample in changed["samples"]:
                    result = meter.observe(sample, changed["events"])
                if result["failures"]:
                    break
            if not result["failures"]:
                result = meter.finish()
            self.assertTrue(control.applied, fault)
            self.assertFalse(result["passed"], fault)
            self.assertTrue(result["failures"], fault)

    def test_copied_control_selects_live_carrier_not_first_entry_or_fixed_frame(self):
        source = row(3)
        sample = source["samples"][0]
        subjects = {"mankey": sample["actors"][0], "onix": sample["actors"][1]}
        combat = sample["pokemonCombat"]
        decoy_carrier = deepcopy(combat["interactions"]["carriers"][0])
        decoy_target = deepcopy(combat["targets"][0])
        decoy_carrier["handle"] = decoy_target["handle"] = {"slot": 9}
        combat["interactions"]["carriers"].insert(0, decoy_carrier)
        combat["targets"].insert(0, decoy_target)
        sample["frame"] += 800
        combat["frame"] = sample["frame"]
        combat["interactions"]["frame"] = sample["frame"]
        sample["pokemonAppearance"]["frame"] = sample["frame"]
        control = FollowerThrowHitAbortNegative(KIND + ":add-premature-cargo")
        changed = control.mutate(source, subjects)["samples"][0]["pokemonCombat"]
        self.assertTrue(control.applied)
        self.assertFalse(changed["interactions"]["carriers"][0]["bindings"]["cargo"]["bound"])
        self.assertTrue(changed["interactions"]["carriers"][1]["bindings"]["cargo"]["bound"])


if __name__ == "__main__":
    unittest.main()
