#!/usr/bin/env python3
"""Focused migration, codec, determinism, and history tests for OWBD v40."""

from __future__ import annotations

import copy
import hashlib
import struct
import unittest

from overworld_wild_behavior_model_v40 import (
    ModelError,
    decode_blob,
    encode_model,
    load_model,
    read_inc,
    stable_history_digest,
    validate_model,
    wire_projection,
)


EXPECTED_SIZE = 11636
EXPECTED_CHECKSUM = 0x191F4869
EXPECTED_FINGERPRINT = 0xE9C872AA
EXPECTED_SHA256 = "4131c29b137f594060bebb2193b29522f1c0a315fff00ca9ed63e1d93db92ac0"


class OverworldWildBehaviorModelV40Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = load_model()
        cls.committed_blob = read_inc()

    def test_canonical_migration_is_byte_identical(self):
        encoded = encode_model(self.model)
        self.assertEqual(encoded, self.committed_blob)
        self.assertEqual(len(encoded), EXPECTED_SIZE)
        self.assertEqual(struct.unpack_from("<I", encoded, 16)[0], EXPECTED_CHECKSUM)
        self.assertEqual(struct.unpack_from("<I", encoded, 20)[0], EXPECTED_FINGERPRINT)
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), EXPECTED_SHA256)

    def test_codec_round_trips_in_both_directions(self):
        encoded = encode_model(self.model)
        decoded = decode_blob(encoded, stable_id_history=self.model["stableIdHistory"])
        self.assertEqual(decoded, wire_projection(self.model))
        self.assertEqual(encode_model(decoded), encoded)

    def test_real_blob_decodes_directly_with_explicit_history(self):
        decoded = decode_blob(
            self.committed_blob, stable_id_history=self.model["stableIdHistory"]
        )
        self.assertEqual(len(decoded["stateProfiles"]), 58)
        self.assertEqual(len(decoded["controllers"]), 3)
        self.assertEqual(len(decoded["transitions"]), 26)
        self.assertEqual(encode_model(decoded), self.committed_blob)
        with self.assertRaisesRegex(ModelError, "requires explicit authenticated"):
            decode_blob(self.committed_blob)

    def test_top_level_record_order_is_canonical(self):
        reordered = copy.deepcopy(self.model)
        for key in (
            "stateProfiles", "controllers", "genericAssignments", "speciesAssignments",
            "overrides", "spawnPolicies", "populationPolicies", "hookSets", "owners",
            "overrideDefinitions", "transitions", "importRecipes", "applicability",
            "tiredTranslations", "semanticIds",
        ):
            reordered[key].reverse()
        self.assertEqual(encode_model(reordered), self.committed_blob)

    def test_profiles_own_complete_bodies_but_not_roles(self):
        for profile in self.model["stateProfiles"]:
            self.assertEqual(len(profile["body"]["values"]), 28)
            self.assertNotIn("semanticRoleId", profile)
            self.assertNotIn("semanticRole", profile)
        for controller in self.model["controllers"]:
            self.assertEqual(sum(bool(node["base"]) for node in controller["nodes"]), 1)
            self.assertTrue(all(node["semanticRoleId"] for node in controller["nodes"]))

    def test_history_and_tombstones_are_sealed(self):
        history = self.model["stableIdHistory"]
        self.assertEqual(history["checkpointSha256"], stable_history_digest(history))
        self.assertGreater(len(history["tombstones"]), 300)

        # Removing a retired allocation and recomputing every model-local seal
        # must still fail the independent checkpoint.
        damaged = copy.deepcopy(self.model)
        damaged_history = damaged["stableIdHistory"]
        victim = damaged_history["tombstones"].pop()
        del damaged_history["allocations"][victim]
        local_reseal = stable_history_digest(damaged_history)
        damaged_history["checkpointSha256"] = local_reseal
        damaged_history["historySha256"] = local_reseal
        with self.assertRaisesRegex(ModelError, "independent pinned history"):
            validate_model(damaged)

        swapped = copy.deepcopy(self.model)
        swapped_history = swapped["stableIdHistory"]
        first, second = list(swapped_history["allocations"])[:2]
        swapped_history["allocations"][first], swapped_history["allocations"][second] = \
            swapped_history["allocations"][second], swapped_history["allocations"][first]
        local_reseal = stable_history_digest(swapped_history)
        swapped_history["checkpointSha256"] = local_reseal
        swapped_history["historySha256"] = local_reseal
        with self.assertRaisesRegex(ModelError, "independent pinned history"):
            validate_model(swapped)

        wrong_policy = copy.deepcopy(self.model)
        wrong_policy["stableIdHistory"]["allocationPolicy"] = "lowest-free"
        with self.assertRaisesRegex(ModelError, "allocation policy"):
            validate_model(wrong_policy)

    def test_history_rejects_unretired_deletion_and_tail_truncation(self):
        removed_without_retire = copy.deepcopy(self.model)
        victim = next(
            record for record in removed_without_retire["speciesAssignments"]
            if record["registryKey"] == "assignment:114"
        )
        removed_without_retire["speciesAssignments"].remove(victim)
        with self.assertRaisesRegex(ModelError, "requires explicit retirement"):
            validate_model(removed_without_retire)

        reservation_escape = copy.deepcopy(removed_without_retire)
        reservation_escape["stableIdHistory"]["reservedRegistryKeys"] = ["assignment:114"]
        with self.assertRaisesRegex(ModelError, "does not permit unauthenticated reservations"):
            validate_model(reservation_escape)

        truncated = copy.deepcopy(self.model)
        history = truncated["stableIdHistory"]
        history["extensions"] = []
        history["historySha256"] = history["checkpointSha256"]
        with self.assertRaisesRegex(ModelError, "independently accepted head"):
            validate_model(truncated)

    def test_closed_domains_and_invariants_are_rejected(self):
        locomotion = copy.deepcopy(self.model)
        locomotion["stateProfiles"][0]["body"]["values"]["locomotion"] = 255
        with self.assertRaisesRegex(ModelError, "closed typed domains"):
            validate_model(locomotion)

        hop_range = copy.deepcopy(self.model)
        values = hop_range["stateProfiles"][0]["body"]["values"]
        values["hopMinDistance"], values["hopMaxDistance"] = 12, 1
        with self.assertRaisesRegex(ModelError, "closed typed domains"):
            validate_model(hop_range)

        spawn = copy.deepcopy(self.model)
        spawn["spawnPolicies"][0]["destination"] = 255
        with self.assertRaisesRegex(ModelError, "spawn policy"):
            validate_model(spawn)

        population = copy.deepcopy(self.model)
        population["populationPolicies"][0]["limit"] = 11
        with self.assertRaisesRegex(ModelError, "population policy"):
            validate_model(population)

    def test_registry_keys_and_references_are_exact(self):
        wrong_key = copy.deepcopy(self.model)
        wrong_key["controllers"][0]["registryKey"] = \
            wrong_key["controllers"][1]["registryKey"]
        with self.assertRaisesRegex(ModelError, "does not match its live registryKey"):
            validate_model(wrong_key)

        wrong_body_key = copy.deepcopy(self.model)
        wrong_body_key["stateProfiles"][0]["bodyRegistryKey"] = \
            wrong_body_key["stateProfiles"][1]["bodyRegistryKey"]
        with self.assertRaisesRegex(ModelError, "state body.*registryKey"):
            validate_model(wrong_body_key)

        dangling = copy.deepcopy(self.model)
        dangling["controllers"][0]["nodes"][0]["profileId"] = 0xFFFF
        with self.assertRaisesRegex(ModelError, "unknown profile"):
            validate_model(dangling)

    def test_semantic_id_kinds_and_role_boundaries_are_exact(self):
        semantic = {
            (record["kind"], record["value"]): record["stableId"]
            for record in self.model["semanticIds"]
        }

        cross_kind_profile = copy.deepcopy(self.model)
        cross_kind_profile["stateProfiles"][0]["provenanceId"] = semantic[(2, 1)]
        with self.assertRaisesRegex(ModelError, "provenance does not match"):
            validate_model(cross_kind_profile)

        cross_kind_custom = copy.deepcopy(self.model)
        custom_node = cross_kind_custom["controllers"][0]["nodes"][-1]
        custom_node["customRoleId"] = semantic[(3, 1)]
        with self.assertRaisesRegex(ModelError, "custom semanticId"):
            validate_model(cross_kind_custom)

        cross_kind_population = copy.deepcopy(self.model)
        cross_kind_population["populationPolicies"][0]["populationGroupId"] = semantic[(1, 1)]
        with self.assertRaisesRegex(ModelError, "population-group semanticId"):
            validate_model(cross_kind_population)

        role_outside_domain = copy.deepcopy(self.model)
        role_outside_domain["controllers"][0]["nodes"][-1]["semanticRoleId"] = 8
        with self.assertRaisesRegex(ModelError, "outside 1..7"):
            validate_model(role_outside_domain)

        custom_on_builtin = copy.deepcopy(self.model)
        custom_on_builtin["controllers"][0]["nodes"][0]["customRoleId"] = semantic[(2, 1)]
        with self.assertRaisesRegex(ModelError, "noncustom node"):
            validate_model(custom_on_builtin)

        missing_custom = copy.deepcopy(self.model)
        missing_custom["controllers"][0]["nodes"][-1]["customRoleId"] = 0
        with self.assertRaisesRegex(ModelError, "custom semanticId"):
            validate_model(missing_custom)

        custom_value = copy.deepcopy(self.model)
        next(record for record in custom_value["semanticIds"] if record["kind"] == 2)["value"] = 255
        with self.assertRaisesRegex(ModelError, "invalid kind/value"):
            validate_model(custom_value)

        population_group_value = copy.deepcopy(self.model)
        next(record for record in population_group_value["semanticIds"]
             if record["kind"] == 3)["value"] = 255
        with self.assertRaisesRegex(ModelError, "invalid kind/value"):
            validate_model(population_group_value)

        spawn_cross_kind = copy.deepcopy(self.model)
        spawn_cross_kind["spawnPolicies"][0]["provenanceId"] = semantic[(2, 1)]
        with self.assertRaisesRegex(ModelError, "wrong provenance semanticId"):
            validate_model(spawn_cross_kind)

        spawn_wrong_value = copy.deepcopy(self.model)
        spawn_wrong_value["spawnPolicies"][0]["provenanceId"] = semantic[(1, 2)]
        with self.assertRaisesRegex(ModelError, "wrong provenance semanticId"):
            validate_model(spawn_wrong_value)

        population_cross_kind = copy.deepcopy(self.model)
        population_cross_kind["populationPolicies"][0]["provenanceId"] = semantic[(2, 1)]
        with self.assertRaisesRegex(ModelError, "wrong provenance"):
            validate_model(population_cross_kind)

        population_wrong_override = copy.deepcopy(self.model)
        population_wrong_override["populationPolicies"][3]["provenanceId"] = 0x5003
        with self.assertRaisesRegex(ModelError, "wrong provenance"):
            validate_model(population_wrong_override)

    def test_profile_roles_and_controller_selectors_are_rejected(self):
        role_on_profile = copy.deepcopy(self.model)
        role_on_profile["stateProfiles"][0]["semanticRoleId"] = 1
        with self.assertRaisesRegex(ModelError, "roles belong to controller nodes"):
            validate_model(role_on_profile)
        duplicate = copy.deepcopy(self.model)
        duplicate["controllers"][0]["nodes"][1]["semanticRoleId"] = \
            duplicate["controllers"][0]["nodes"][0]["semanticRoleId"]
        duplicate["controllers"][0]["nodes"][1]["customRoleId"] = \
            duplicate["controllers"][0]["nodes"][0]["customRoleId"]
        with self.assertRaisesRegex(ModelError, "duplicate semantic selector"):
            validate_model(duplicate)


if __name__ == "__main__":
    unittest.main()
