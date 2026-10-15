"""Check shipping disablement and the explicitly enabled experimental profile."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/overworld-viewer-v2"))
import native_resolver
from scripts.overworld_behavior_profile_viewer import (
    _runtime_source_behavior_catalog, _stable_condition_id, behavior_authoring_context,
)


class BasicAttackProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / "data/overworld_behavior_profiles.json").read_text())
        runtime = _runtime_source_behavior_catalog(cls.catalog)
        cls.app = next(i for i, a in enumerate(runtime["applications"])
                       if a["id"] == "apply-basic-attack")
        cls.condition = _stable_condition_id("basic-attack", "condition-basic-attack-next-to-pokemon")
        cls.shipping_executable = native_resolver.build_condition_preview(ROOT)
        # Basic attack is paused in the shipping catalog. Keep the opt-in
        # behavior checks using an explicit fixture, without changing that file.
        temporary = tempfile.TemporaryDirectory(prefix="basic-attack-enabled-", dir=ROOT / "build")
        cls.addClassCleanup(temporary.cleanup)
        fixture = Path(temporary.name)
        enabled = json.loads(json.dumps(cls.catalog))
        basic = next(p for p in enabled["profiles"] if p["id"] == "basic-attack")
        basic["conditions"][0]["when"]["chancePercent"] = 100
        catalog = fixture / "catalog.json"
        catalog.write_text(json.dumps(enabled))
        cls.executable = native_resolver.build_condition_preview(
            ROOT, catalog=catalog, output=fixture / "condition-preview")
        cls.resolver = native_resolver.build(
            ROOT, catalog=catalog, output=fixture / "resolver")
        cls.max_species = behavior_authoring_context()[2]["MAX_SPECIES_INCLUDING_FORMS"]

    def test_shipping_catalog_does_not_admit_basic_attack(self):
        for species in (56, 74, 95, 143, 155, self.max_species):
            for role in (1, 2):  # Wild and Follower.
                with self.subTest(species=species, role=role):
                    request = self.request(0, 0, species)
                    request["subject"]["roleMask"] = role
                    result = native_resolver.preview_conditions(
                        request, root=ROOT, executable=self.shipping_executable)
                    self.assertEqual(result["evaluatorStatus"], 0)
                    self.assertFalse(result["activeApplicationMask"] & (1 << self.app))
                    entry = next(e for e in result["entries"]
                                 if e["conditionId"] == self.condition)
                    self.assertFalse(entry["conditionTrue"])
                    self.assertFalse(entry["active"])
                    request["observation"]["frame"] = 2
                    request["conditionState"] = [dict(
                        conditionId=self.condition, active=1, hasTriggered=0,
                        activeUntil=0, cooldownUntil=0, targetKind=2,
                        targetCandidateIndex=0)]
                    result = native_resolver.preview_conditions(
                        request, root=ROOT, executable=self.shipping_executable)
                    self.assertFalse(result["activeApplicationMask"] & (1 << self.app))
                    entry = next(e for e in result["entries"]
                                 if e["conditionId"] == self.condition)
                    self.assertFalse(entry["active"])

    def request(self, dx=1, dy=0, species=155):
        def actor(species, slot, generation):
            return dict(species=species, level=5, terrain=0, shiny=0,
                        groupFlags=0, behaviorClass=0, roleMask=1,
                        handle=dict(slot=slot, generation=generation,
                                    fieldEpoch=3, mapGeneration=4,
                                    encounterGeneration=10 + generation))
        target = actor(143, 1, 2)
        target.update(x=10 + dx, y=10 + dy, valid=1, facingAndOcclusion=1)
        return dict(subject=actor(species, 0, 1), candidates=[target],
                    observation=dict(terrainMask=1, frame=1, x=10, y=10,
                                     facing=0, movementSpeed=16,
                                     player=dict(x=30, y=30, valid=0,
                                                 facingAndOcclusion=1)))

    def preview(self, request):
        result = native_resolver.preview_conditions(
            request, root=ROOT, executable=self.executable)
        self.assertEqual(result["evaluatorStatus"], 0)
        entry = next(e for e in result["entries"] if e["conditionId"] == self.condition)
        self.assertEqual(entry["applicationIndex"], self.app)
        return result, entry

    def test_all_species_are_admitted_by_actual_subject_preparation(self):
        for species in range(1, self.max_species + 1):
            with self.subTest(species=species):
                _, entry = self.preview(self.request(species=species))
                self.assertTrue(entry["conditionTrue"])
                self.assertTrue(entry["active"])

    def test_eight_adjacent_directions_and_while_true_end(self):
        for dx, dy in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
            with self.subTest(direction=(dx,dy)):
                request = self.request(dx, dy)
                result, entry = self.preview(request)
                self.assertTrue(entry["active"])
                self.assertEqual(result["resolvedTarget"]["actorSlot"], 1)
                request["observation"]["frame"] = 2
                request["candidates"][0]["x"] = 12
                request["conditionState"] = [dict(
                    conditionId=self.condition, active=1, hasTriggered=0,
                    activeUntil=0, cooldownUntil=0, targetKind=2,
                    targetCandidateIndex=0)]
                result, entry = self.preview(request)
                self.assertFalse(entry["conditionTrue"])
                self.assertFalse(entry["active"])
                self.assertFalse(result["activeApplicationMask"] & (1 << self.app))
        for facts in (2, 8):  # HELD and RECOVERING.
            request = self.request()
            request["observation"]["actorFacts"] = facts
            _, entry = self.preview(request)
            self.assertFalse(entry["active"])

    def test_same_tile_activates_and_preserves_current_target(self):
        for facing in range(4):
            with self.subTest(facing=facing):
                request = self.request(0, 0)
                request["observation"]["facing"] = facing
                result, entry = self.preview(request)
                self.assertTrue(entry["conditionTrue"])
                self.assertTrue(entry["active"])
                self.assertEqual(result["resolvedTarget"]["actorSlot"], 1)
                request["observation"]["frame"] = 2
                request["conditionState"] = [dict(conditionId=self.condition, active=1,
                    hasTriggered=0, activeUntil=0, cooldownUntil=0, targetKind=2,
                    targetCandidateIndex=0)]
                result, entry = self.preview(request)
                self.assertTrue(entry["conditionTrue"])
                self.assertTrue(entry["active"])
                self.assertFalse(entry["triggered"])
                self.assertEqual(result["resolvedTarget"]["actorSlot"], 1)

    def test_same_tile_self_and_occluded_target_do_not_activate(self):
        for rejected in ("self", "occluded", "invalid"):
            with self.subTest(rejected=rejected):
                request = self.request(0, 0)
                target = request["candidates"][0]
                if rejected == "self":
                    target["handle"] = dict(request["subject"]["handle"])
                elif rejected == "occluded":
                    target["facingAndOcclusion"] |= 4
                else:
                    target["valid"] = 0
                result, entry = self.preview(request)
                self.assertFalse(entry["conditionTrue"])
                self.assertFalse(entry["active"])
                self.assertFalse(result["activeApplicationMask"] & (1 << self.app))

    def test_same_tile_while_true_retires_on_far_held_or_recovery(self):
        for retired in ("far", "held", "recovering"):
            with self.subTest(retired=retired):
                request = self.request(0, 0)
                request["conditionState"] = [dict(conditionId=self.condition, active=1,
                    hasTriggered=0, activeUntil=0, cooldownUntil=0, targetKind=2,
                    targetCandidateIndex=0)]
                if retired == "far":
                    request["candidates"][0]["x"] = 12
                else:
                    request["observation"]["actorFacts"] = 2 if retired == "held" else 8
                result, entry = self.preview(request)
                self.assertFalse(entry["active"])
                self.assertFalse(result["activeApplicationMask"] & (1 << self.app))

    def test_same_tile_stale_captured_target_fails_closed(self):
        request = self.request(0, 0)
        request["candidates"][0]["valid"] = 0
        request["conditionState"] = [dict(conditionId=self.condition, active=1,
            hasTriggered=0, activeUntil=0, cooldownUntil=0, targetKind=2,
            targetCandidateIndex=0)]
        with self.assertRaisesRegex(RuntimeError, "condition preview evaluation failed: 3"):
            native_resolver.preview_conditions(request, root=ROOT, executable=self.executable)

    def test_attack_fields_compose_and_preserve_knockback(self):
        runtime = _runtime_source_behavior_catalog(self.catalog)
        ram = next(i for i,a in enumerate(runtime["applications"]) if a["id"] == "apply-ram")
        for active in (0, 1 << ram):
            request = dict(species=155, level=5, terrain=0, groupFlags=0,
                           activeConditionalMask=active)
            if active:
                condition = _stable_condition_id("ram", "condition-ram-notices-player")
                request.update(winningConditionId=condition, targetSourceApplication=ram,
                               resolvedTargetConditionId=condition, resolvedTarget=dict(kind="player"))
            before = native_resolver.resolve(None, request, root=ROOT, executable=self.resolver)
            request.update(activeConditionalMask=active | (1 << self.app),
                           winningConditionId=self.condition,
                           targetSourceApplication=self.app,
                           resolvedTargetConditionId=self.condition,
                           resolvedTarget=dict(kind="actor", actorSlot=1,
                               actorGeneration=2, fieldEpoch=3, mapGeneration=4,
                               encounterGeneration=12))
            after = native_resolver.resolve(None, request, root=ROOT, executable=self.resolver)
            self.assertEqual(after["status"], 0)
            original = bytes.fromhex(before["profileHex"])
            profile = bytes.fromhex(after["profileHex"])
            self.assertEqual((profile[0],profile[12],profile[13]), (3,2,10))
            self.assertEqual(int.from_bytes(profile[32:34],"little"), 16)
            self.assertEqual(profile[36], original[36])
            self.assertEqual(profile[42] >> 1, 1)  # Return after one controller move.
            self.assertEqual(profile[65], 0)  # Face movement, including the return.
            self.assertEqual((profile[72],profile[73],profile[74],profile[75]), (1,1,20,0))
            self.assertEqual(profile[79], original[79])


if __name__ == "__main__":
    unittest.main()
