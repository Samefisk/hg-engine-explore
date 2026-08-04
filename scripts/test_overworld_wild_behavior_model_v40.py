#!/usr/bin/env python3
"""Focused migration, codec, determinism, and history tests for OWBD v40."""

from __future__ import annotations

import copy
import hashlib
import struct
import unittest

from overworld_wild_behavior_model_v40 import (
    ModelError,
    append_stable_history_events,
    decode_blob,
    encode_model,
    intern_state_bodies,
    load_model,
    merge_authored_metadata,
    read_inc,
    stable_history_digest,
    validate_model,
    wire_projection,
)


GOLDEN_BASELINE_SIZE = 11028
GOLDEN_BASELINE_CHECKSUM = 0xCD843F3E
GOLDEN_BASELINE_FINGERPRINT = 0x9421CA4D
GOLDEN_BASELINE_SHA256 = "6523a0018887426d26fcc4e1f17541f5f375b968028a29d3ad4787db96515c95"


class OverworldWildBehaviorModelV40Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = load_model()
        cls.committed_blob = read_inc()

    def test_golden_baseline_migration_is_byte_identical(self):
        encoded = encode_model(self.model)
        self.assertEqual(encoded, self.committed_blob)
        self.assertEqual(len(encoded), GOLDEN_BASELINE_SIZE)
        self.assertEqual(struct.unpack_from("<I", encoded, 16)[0], GOLDEN_BASELINE_CHECKSUM)
        self.assertEqual(struct.unpack_from("<I", encoded, 20)[0], GOLDEN_BASELINE_FINGERPRINT)
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), GOLDEN_BASELINE_SHA256)

    def test_codec_round_trips_in_both_directions(self):
        encoded = encode_model(self.model)
        decoded = decode_blob(encoded, stable_id_history=self.model["stableIdHistory"])
        self.assertEqual(decoded, wire_projection(self.model))
        self.assertEqual(encode_model(decoded), encoded)

    def test_promotion_provenance_is_validated_and_restored_as_metadata(self):
        authored = copy.deepcopy(self.model)
        node = authored["controllers"][0]["nodes"][0]
        profile = next(
            item for item in authored["stateProfiles"]
            if item["stableId"] == node["profileId"]
        )
        promotion = {
            "kind": "effective-stack-preview",
            "sourceProfileId": profile["stableId"],
            "sourceBodyId": profile["bodyId"],
            "winningLayer": None,
            "normalizations": [],
            "fieldProvenance": {
                field: {
                    "kind": "base", "profileId": profile["stableId"],
                    "nodeId": node["stableId"],
                }
                for field in profile["body"]["values"]
            },
        }
        profile["promotionProvenance"] = promotion
        validate_model(authored)
        encoded = encode_model(authored)
        self.assertEqual(encoded, self.committed_blob)
        decoded = decode_blob(
            encoded, stable_id_history=authored["stableIdHistory"],
        )
        self.assertNotIn("promotionProvenance", next(
            item for item in decoded["stateProfiles"]
            if item["stableId"] == profile["stableId"]
        ))
        self.assertEqual(merge_authored_metadata(decoded, authored), authored)

        malformed = copy.deepcopy(authored)
        malformed_profile = next(
            item for item in malformed["stateProfiles"]
            if item["stableId"] == profile["stableId"]
        )
        malformed_profile["promotionProvenance"]["fieldProvenance"].pop(
            next(iter(profile["body"]["values"])),
        )
        with self.assertRaisesRegex(ModelError, "every state field"):
            validate_model(malformed)

        dangling = copy.deepcopy(authored)
        dangling_profile = next(
            item for item in dangling["stateProfiles"]
            if item["stableId"] == profile["stableId"]
        )
        dangling_profile["promotionProvenance"]["sourceProfileId"] = 0xFFFF
        with self.assertRaisesRegex(ModelError, "unknown stableId"):
            validate_model(dangling)

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
            "overrideDefinitions", "modifierOperations", "transitions", "importRecipes", "applicability",
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

    def test_exact_state_bodies_are_interned_without_merging_profiles(self):
        self.assertEqual(len(self.model["stateProfiles"]), 58)
        self.assertEqual(len({item["bodyId"] for item in self.model["stateProfiles"]}), 48)
        reinterned, retired = intern_state_bodies(self.model)
        self.assertEqual(retired, 0)
        self.assertEqual(reinterned, self.model)

        conflicting = copy.deepcopy(self.model)
        shared_id = next(
            body_id for body_id in {item["bodyId"] for item in conflicting["stateProfiles"]}
            if sum(item["bodyId"] == body_id for item in conflicting["stateProfiles"]) > 1
        )
        duplicate = [
            item for item in conflicting["stateProfiles"] if item["bodyId"] == shared_id
        ][1]
        duplicate["body"]["values"]["speed"] ^= 1
        with self.assertRaisesRegex(ModelError, "shared state body.*conflicting"):
            validate_model(conflicting)

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
        with self.assertRaisesRegex(ModelError, "not a provenance semanticId"):
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
        population_wrong_override["populationPolicies"][3]["provenanceId"] = 0xFFFF
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

    def test_candidate_priority_is_an_exact_u8_domain(self):
        for invalid in (256, -1, True, "100"):
            with self.subTest(priority=invalid):
                damaged = copy.deepcopy(self.model)
                damaged["overrideDefinitions"][0]["priority"] = invalid
                with self.assertRaisesRegex(ModelError, "definition.priority"):
                    validate_model(damaged)

    def test_transition_dispatch_domains_reject_only_intersecting_scopes(self):
        scoped = copy.deepcopy(self.model)
        left, right = scoped["transitions"][:2]
        right["dispatchPriority"] = left["dispatchPriority"]
        right["trigger"] = left["trigger"]
        right["fromRoleMask"] = left["fromRoleMask"]
        definitions = {
            record["stableId"]: record for record in scoped["overrideDefinitions"]
        }
        applicability = {
            record["stableId"]: record for record in scoped["applicability"]
        }
        controller_ids = [record["stableId"] for record in scoped["controllers"]]
        left_rule = applicability[definitions[left["definitionId"]]["applicabilityId"]]
        right_rule = applicability[definitions[right["definitionId"]]["applicabilityId"]]
        left_rule.update({"kind": left_rule["kind"] | 2,
                          "controllerId": controller_ids[0]})
        right_rule.update({"kind": right_rule["kind"] | 2,
                           "controllerId": controller_ids[1]})

        # Equal-priority rows are deterministic when their controller scopes
        # cannot apply to the same runtime composition.
        validate_model(scoped)

        same_controller = copy.deepcopy(scoped)
        same_applicability = {
            record["stableId"]: record
            for record in same_controller["applicability"]
        }
        same_applicability[right_rule["stableId"]]["controllerId"] = controller_ids[0]
        with self.assertRaisesRegex(ModelError, "ambiguous dispatch overlap"):
            validate_model(same_controller)

        global_scope = copy.deepcopy(scoped)
        global_applicability = {
            record["stableId"]: record for record in global_scope["applicability"]
        }
        global_applicability[left_rule["stableId"]].update({
            "kind": left_rule["kind"] & ~2,
            "controllerId": 0,
        })
        with self.assertRaisesRegex(ModelError, "ambiguous dispatch overlap"):
            validate_model(global_scope)

    def test_ordinary_system_safety_definition_is_rejected(self):
        system_safety = copy.deepcopy(self.model)
        system_safety["overrideDefinitions"][0]["channel"] = 5
        with self.assertRaisesRegex(ModelError, "ordinary definitions cannot use System Safety"):
            validate_model(system_safety)

    def _modifier_model(self, operations):
        model = copy.deepcopy(self.model)
        definition = model["overrideDefinitions"][0]
        definition.update({
            "kind": 2, "controllerId": 0, "nodeId": 0,
            "selectorKind": 0, "semanticRoleId": 0,
        })
        records = []
        for order, operation in enumerate(operations):
            key = f"editor:modifier-operation:test-{order}"
            model["stableIdHistory"], allocated = append_stable_history_events(
                model["stableIdHistory"], [("allocate", key)]
            )
            records.append({
                "stableId": allocated[key], "registryKey": key,
                "definitionId": definition["stableId"], "order": order,
                **operation,
            })
        model["modifierOperations"] = records
        return model

    def test_modifier_operations_round_trip_in_explicit_order(self):
        model = self._modifier_model([
            {"fieldNamespace": 1, "fieldId": 3, "operatorKind": 1,
             "operand": 4, "bound": 0},
            {"fieldNamespace": 1, "fieldId": 3, "operatorKind": 6,
             "operand": 2, "bound": 4},
        ])
        validate_model(model)
        encoded = encode_model(model)
        decoded = decode_blob(encoded, stable_id_history=model["stableIdHistory"])
        self.assertEqual([item["order"] for item in decoded["modifierOperations"]], [0, 1])
        self.assertEqual(encode_model(decoded), encoded)

    def test_modifier_operation_contract_rejects_malformed_relations(self):
        valid = self._modifier_model([{
            "fieldNamespace": 1, "fieldId": 3, "operatorKind": 2,
            "operand": -32768, "bound": 0,
        }])
        validate_model(valid)
        for channel, message in ((0, "modifier definition carries"),
                                 (5, "System Safety")):
            invalid_channel = copy.deepcopy(valid)
            invalid_channel["overrideDefinitions"][0]["channel"] = channel
            with self.subTest(channel=channel), self.assertRaisesRegex(ModelError, message):
                validate_model(invalid_channel)
        cases = []
        candidate_payload = copy.deepcopy(valid)
        candidate_payload["overrideDefinitions"][0].update({
            "kind": 1, "selectorKind": 2, "semanticRoleId": 2,
        })
        cases.append((candidate_payload, "state-candidate definition"))
        empty = self._modifier_model([])
        cases.append((empty, "must own 1..16"))
        behavior_kind = copy.deepcopy(valid); behavior_kind["modifierOperations"][0]["fieldId"] = 28
        cases.append((behavior_kind, "unsupported"))
        invalid_enum = copy.deepcopy(valid)
        invalid_enum["modifierOperations"][0].update({"fieldId": 1, "operatorKind": 1, "operand": 9})
        cases.append((invalid_enum, "outside the field domain"))
        conflicting = self._modifier_model([
            {"fieldNamespace": 2, "fieldId": 7, "operatorKind": 3, "operand": 1, "bound": 0},
            {"fieldNamespace": 2, "fieldId": 7, "operatorKind": 4, "operand": 63, "bound": 0},
        ])
        cases.append((conflicting, "AT_LEAST and AT_MOST"))
        too_many = self._modifier_model([
            {"fieldNamespace": 1, "fieldId": 3, "operatorKind": 2,
             "operand": index, "bound": 0}
            for index in range(17)
        ])
        cases.append((too_many, "must own 1..16"))
        for model, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ModelError, message):
                validate_model(model)

    def test_generated_owner_and_origin_metadata_is_closed(self):
        bad_pair = copy.deepcopy(self.model)
        bad_pair["overrideDefinitions"][0]["hasTiredOriginKind"] = 1
        with self.assertRaisesRegex(ModelError, "tired-origin tag/value pair"):
            validate_model(bad_pair)

        wrong_owner = copy.deepcopy(self.model)
        generated = next(
            item for item in wrong_owner["overrideDefinitions"]
            if item["tiredOriginKind"] == 1
        )
        generated["requiredOwnerId"] = next(
            item["stableId"] for item in wrong_owner["owners"]
            if item["registryKey"] == "owner:5"
        )
        with self.assertRaisesRegex(ModelError, "frozen owner/origin metadata"):
            validate_model(wrong_owner)

        wrong_translation = copy.deepcopy(self.model)
        translation = wrong_translation["tiredTranslations"][0]
        translation["definitionId"] = next(
            item["stableId"] for item in wrong_translation["overrideDefinitions"]
            if item["tiredOriginKind"] == 2
        )
        with self.assertRaisesRegex(ModelError, "does not match generated origin"):
            validate_model(wrong_translation)

    def test_complete_graph_domains_are_validated(self):
        assignment = copy.deepcopy(self.model)
        assignment["genericAssignments"][0]["controllerIndex"] = len(
            assignment["assignmentActions"]
        )
        with self.assertRaisesRegex(ModelError, "assignment-action index"):
            validate_model(assignment)

        hook = copy.deepcopy(self.model)
        hook["hookSets"][0]["pickupThrowEntry"] = 1
        with self.assertRaisesRegex(ModelError, "hook set"):
            validate_model(hook)

        static_action = copy.deepcopy(self.model)
        static_action["overrides"][0]["actions"][0]["payload"][2:4] = [0xFF, 0xFF]
        with self.assertRaisesRegex(ModelError, "static override action"):
            validate_model(static_action)

        applicability = copy.deepcopy(self.model)
        applicability["applicability"][0]["kind"] |= 2
        with self.assertRaisesRegex(ModelError, "applicability record"):
            validate_model(applicability)

        owner = copy.deepcopy(self.model)
        owner["owners"][0]["kind"] = 0
        with self.assertRaisesRegex(ModelError, "system-owned"):
            validate_model(owner)


if __name__ == "__main__":
    unittest.main()
