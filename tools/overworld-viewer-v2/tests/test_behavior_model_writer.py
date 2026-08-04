import copy
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WRITER_PATH = ROOT / "tools/overworld-viewer-v2/behavior_model_writer.py"
VIEWER_PATH = ROOT / "scripts/overworld_behavior_profile_viewer.py"
MODEL_REL = Path("data/OverworldWildBehaviorModelV40.json")
INC_REL = Path("data/OverworldWildBehaviorDataV40.generated.inc")
HEADER_REL = Path("include/overworld_wild_behavior_data.h")
MANAGED = (MODEL_REL, INC_REL, HEADER_REL)


def load_writer():
    spec = importlib.util.spec_from_file_location("_behavior_model_writer_test", WRITER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_viewer():
    spec = importlib.util.spec_from_file_location("_behavior_model_writer_viewer_test", VIEWER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def profile_payload(profile, *, draft_id=None, name=None):
    result = {
        "name": name or profile["name"],
        "descriptiveTags": list(profile["descriptiveTags"]),
        "values": copy.deepcopy(profile["body"]["values"]),
    }
    if draft_id:
        result["draftId"] = draft_id
        result["templateProvenance"] = {
            "kind": profile["body"]["provenanceKind"],
            "provenanceId": profile["provenanceId"],
        }
    else:
        result["stableId"] = profile["stableId"]
    return result


def node_payload(node, *, draft_id=None, profile_ref=None):
    result = {
        "profileRef": profile_ref if profile_ref is not None else node["profileId"],
        "semanticRoleId": node["semanticRoleId"],
        "customRoleId": node["customRoleId"] or None,
        "base": bool(node["base"]),
        "optional": bool(node["optional"]),
        "hidden": bool(node["hidden"]),
    }
    result["draftId" if draft_id else "stableId"] = draft_id or node["stableId"]
    return result


def controller_payload(controller, *, draft_id=None, nodes=None, name=None):
    result = {
        "name": name or controller["name"],
        "nodes": nodes if nodes is not None else [node_payload(node) for node in controller["nodes"]],
        "scalarDefaults": {key: controller[key] for key in (
            "alertState", "alertEmote", "alertTime", "alertness",
            "alertRange", "alertChance", "stamina", "restTime",
        )},
        "policyIds": {key: controller[key] for key in (
            "spawnPolicyId", "populationPolicyId", "hookSetId",
        )},
    }
    result["draftId" if draft_id else "stableId"] = draft_id or controller["stableId"]
    return result


def applicability_payload(applicability, identity=None, **updates):
    excluded = {"stableId", "registryKey"}
    result = {key: copy.deepcopy(value) for key, value in applicability.items() if key not in excluded}
    chosen = applicability["stableId"] if identity is None else identity
    result["draftId" if isinstance(chosen, str) else "stableId"] = chosen
    result.update(updates)
    return result


def definition_payload(definition, identity, applicability, applicability_identity=None, **updates):
    excluded = {"stableId", "registryKey", "nameId"}
    result = {key: copy.deepcopy(value) for key, value in definition.items() if key not in excluded}
    result["draftId" if isinstance(identity, str) else "stableId"] = identity
    result["applicability"] = applicability_payload(applicability, applicability_identity)
    if applicability_identity is not None:
        result["applicabilityId"] = applicability_identity
    result.update(updates)
    return result


def transition_payload(transition, definition, applicability, identity, definition_identity,
                       *, applicability_identity=None, operation=None):
    controller_ids = ([definition["controllerId"]] if definition["controllerId"] else [12289, 12290, 12291])
    result = {
        "name": f"Transition {identity}",
        "controllerIds": controller_ids,
        "candidateDefinitionId": definition_identity,
        "candidateDefinition": definition_payload(
            definition, definition_identity, applicability, applicability_identity
        ),
        "ownerId": transition["ownerId"],
        "trigger": transition["trigger"],
        "fromRoleMask": transition["fromRoleMask"],
        "dispatchPriority": transition["dispatchPriority"],
        "order": transition["order"],
        "guards": [], "operations": [operation] if operation else [],
        "actions": [], "recoveryActions": [],
    }
    result["draftId" if isinstance(identity, str) else "stableId"] = identity
    return result


def saved_transition_payload(model, transition, *, name):
    definition = next(item for item in model["overrideDefinitions"]
                      if item["stableId"] == transition["definitionId"])
    applicability = next(item for item in model["applicability"]
                         if item["stableId"] == definition["applicabilityId"])
    result = transition_payload(
        transition, definition, applicability, transition["stableId"], definition["stableId"]
    )
    result["name"] = name
    result["guards"] = [{
        "stableId": child["stableId"], "kind": child["kind"],
        "negate": bool(child["negate"]), "payload": child["payload"],
        "referenceId": child["referenceId"] or None,
    } for child in transition["guards"]]
    result["operations"] = [{
        "stableId": child["stableId"], "definitionId": child["definitionId"] or None,
        "ownerId": child["ownerId"] or None,
        "replacementDefinitionId": child["replacementDefinitionId"] or None,
        "policyId": child["policyId"] or None, "instanceKey": child["instanceKey"] or None,
        "kind": child["kind"], "busyPolicy": child["busyPolicy"],
        "required": bool(child["required"]),
    } for child in transition["operations"]]
    result["actions"] = [{
        "stableId": child["stableId"], "phase": child["phase"], "kind": child["kind"],
        "referenceId": child["referenceId"] or None, "payload": child["payload"],
    } for child in transition["actions"]]
    result["recoveryActions"] = [{
        "stableId": child["stableId"], "ownerId": child["ownerId"],
        "kind": child["kind"], "required": bool(child["required"]),
    } for child in transition["recoveryActions"]]
    return result


def direct_payload(writer, domain, record):
    result = {"stableId": record["stableId"]}
    for field in writer.DIRECT_DOMAIN_FIELDS[domain]:
        if domain == "overrides" and field == "actions":
            result[field] = [{
                "stableId": action["stableId"],
                "kind": action["kind"],
                "flags": action["flags"],
                "payload": copy.deepcopy(action["payload"]),
            } for action in record[field]]
        else:
            result[field] = copy.deepcopy(record[field])
    return result


def direct_create_payload(writer, domain, record, draft_id):
    result = direct_payload(writer, domain, record)
    del result["stableId"]
    result["draftId"] = draft_id
    return result


class BehaviorModelWriterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.writer = load_writer()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        for relative in MANAGED:
            target = self.workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)

    def tearDown(self):
        self.temp.cleanup()

    def bytes(self):
        return {relative: (self.workspace / relative).read_bytes() for relative in MANAGED}

    def model(self):
        return json.loads((self.workspace / MODEL_REL).read_text())

    def test_noop_is_byte_identical(self):
        before = self.bytes()
        self.assertEqual(self.writer.apply_behavior_model_changes(
            self.workspace, {"modelVersion": 40}
        ), {})
        self.assertEqual(self.bytes(), before)

    def test_all_authored_direct_domains_participate_in_one_transaction(self):
        model = self.model()
        updates = {
            domain: {"update": [direct_payload(self.writer, domain, model[domain][0])]}
            for domain in self.writer.DIRECT_DOMAIN_FIELDS
        }
        before = self.bytes()
        self.assertEqual(
            self.writer.apply_behavior_model_changes(self.workspace, updates), {}
        )
        self.assertEqual(self.model(), model)
        after_noop = self.bytes()
        self.assertEqual(after_noop[INC_REL], before[INC_REL])
        self.assertEqual(after_noop[HEADER_REL], before[HEADER_REL])

        spawn = direct_payload(self.writer, "spawnPolicies", model["spawnPolicies"][0])
        spawn["spawnHopTime"] += 1
        self.writer.apply_behavior_model_changes(self.workspace, {
            "spawnPolicies": {"update": [spawn]},
        })
        saved = self.model()
        changed = next(
            item for item in saved["spawnPolicies"]
            if item["stableId"] == spawn["stableId"]
        )
        self.assertEqual(changed["spawnHopTime"], spawn["spawnHopTime"])
        self.assertNotEqual(self.bytes()[INC_REL], before[INC_REL])

    def test_generated_graph_domains_are_read_only_and_atomic(self):
        model = self.model()
        before = self.bytes()
        for domain in self.writer.READ_ONLY_DOMAIN_KEYS:
            with self.subTest(domain=domain), self.assertRaisesRegex(
                    self.writer.BehaviorModelWriteError, "generated/read-only"):
                self.writer.apply_behavior_model_changes(self.workspace, {
                    domain: {"remove": [model[domain][0]["stableId"]]},
                })
            self.assertEqual(self.bytes(), before)

        generated_transition = next(
            transition for transition in model["transitions"]
            if next(
                definition for definition in model["overrideDefinitions"]
                if definition["stableId"] == transition["definitionId"]
            )["hasRequiredOwnerId"]
        )
        update = saved_transition_payload(
            model, generated_transition,
            name=generated_transition.get("name", generated_transition["registryKey"]),
        )
        update["candidateDefinition"]["priority"] -= 1
        with self.assertRaisesRegex(
                self.writer.BehaviorModelWriteError,
                "generated candidate transitions and their children are read-only"):
            self.writer.apply_behavior_model_changes(self.workspace, {
                "transitions": {"update": [update]},
            })
        self.assertEqual(self.bytes(), before)

        for label, mutate in (
            ("trigger", lambda item: item.update({
                "trigger": 13 if item["trigger"] != 13 else 12,
            })),
            ("child", lambda item: item["actions"][0].update({
                "kind": 8 if item["actions"][0]["kind"] != 8 else 7,
            })),
        ):
            with self.subTest(label=label):
                update = saved_transition_payload(
                    model, generated_transition,
                    name=generated_transition.get(
                        "name", generated_transition["registryKey"]
                    ),
                )
                mutate(update)
                with self.assertRaisesRegex(
                        self.writer.BehaviorModelWriteError,
                        "generated candidate transitions and their children are read-only"):
                    self.writer.apply_behavior_model_changes(self.workspace, {
                        "transitions": {"update": [update]},
                    })
                self.assertEqual(self.bytes(), before)

        with self.assertRaisesRegex(
                self.writer.BehaviorModelWriteError,
                "generated candidate transitions and their children are read-only"):
            self.writer.apply_behavior_model_changes(self.workspace, {
                "transitions": {"remove": [generated_transition["stableId"]]},
            })
        self.assertEqual(self.bytes(), before)

    def test_ordinary_transition_deletion_may_renumber_generated_rows(self):
        model = self.model()
        generated_ids = {
            definition["stableId"] for definition in model["overrideDefinitions"]
            if definition["hasRequiredOwnerId"] or definition["hasTiredOriginKind"]
        }
        ordinary = model["transitions"][0]
        self.assertNotIn(ordinary["definitionId"], generated_ids)
        before_generated = {
            transition["stableId"]: {
                key: copy.deepcopy(value)
                for key, value in transition.items() if key != "order"
            }
            for transition in model["transitions"]
            if transition["definitionId"] in generated_ids
        }
        self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"remove": [ordinary["stableId"]]},
        })
        saved = self.model()
        self.assertNotIn(
            ordinary["stableId"],
            {transition["stableId"] for transition in saved["transitions"]},
        )
        after_generated = {
            transition["stableId"]: {
                key: copy.deepcopy(value)
                for key, value in transition.items() if key != "order"
            }
            for transition in saved["transitions"]
            if transition["definitionId"] in generated_ids
        }
        self.assertEqual(after_generated, before_generated)
        self.assertEqual(
            [transition["order"] for transition in saved["transitions"]],
            list(range(len(saved["transitions"]))),
        )

    def test_candidate_priority_overflow_is_rejected_atomically(self):
        model = self.model()
        transition = model["transitions"][0]
        update = saved_transition_payload(
            model, transition,
            name=transition.get("name", transition["registryKey"]),
        )
        update["candidateDefinition"]["priority"] = 256
        before = self.bytes()
        with self.assertRaisesRegex(
                self.writer.BehaviorModelWriteError, "priority must be an integer in 0..255"):
            self.writer.apply_behavior_model_changes(self.workspace, {
                "transitions": {"update": [update]},
            })
        self.assertEqual(self.bytes(), before)

    def test_assignment_action_delete_cannot_silently_retarget_indices(self):
        model = self.model()
        before = self.bytes()
        with self.assertRaisesRegex(
                self.writer.BehaviorModelWriteError,
                "still references a removed assignment action"):
            self.writer.apply_behavior_model_changes(self.workspace, {
                "assignmentActions": {
                    "remove": [model["assignmentActions"][0]["stableId"]],
                },
            })
        self.assertEqual(self.bytes(), before)

    def test_assignment_indices_follow_actual_prior_action_order(self):
        permuted = self.model()
        permuted["assignmentActions"].reverse()
        expected_targets = {
            (domain, assignment["stableId"]): permuted["assignmentActions"][
                assignment["controllerIndex"]
            ]["stableId"]
            for domain in ("genericAssignments", "speciesAssignments")
            for assignment in permuted[domain]
        }
        blob = self.writer.v40.encode_model(permuted)
        (self.workspace / MODEL_REL).write_bytes(
            self.writer.v40.canonical_json_bytes(permuted)
        )
        (self.workspace / INC_REL).write_text(self.writer.v40.render_inc(blob))
        header = (self.workspace / HEADER_REL).read_text()
        (self.workspace / HEADER_REL).write_text(
            self.writer.v40.render_header(permuted, blob, header)
        )

        profile = profile_payload(
            permuted["stateProfiles"][0], name="Unrelated metadata update"
        )
        self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"update": [profile]},
        })
        saved = self.model()
        for domain in ("genericAssignments", "speciesAssignments"):
            for assignment in saved[domain]:
                actual_action = saved["assignmentActions"][assignment["controllerIndex"]]
                self.assertEqual(
                    actual_action["stableId"],
                    expected_targets[(domain, assignment["stableId"])],
                )

    def test_typed_static_actions_resolve_same_transaction_drafts(self):
        model = self.model()
        source_profile = model["stateProfiles"][0]
        source_controller = model["controllers"][0]
        profile = profile_payload(
            source_profile, draft_id="draft:static-profile", name="Static target"
        )
        node = node_payload(
            source_controller["nodes"][0], draft_id="draft:static-node",
            profile_ref="draft:static-profile",
        )
        timer_node = node_payload(
            source_controller["nodes"][2], draft_id="draft:static-timer-node",
            profile_ref="draft:static-profile",
        )
        controller = controller_payload(
            source_controller, draft_id="draft:static-controller",
            nodes=[node, timer_node], name="Static action controller",
        )
        controller["policyIds"] = {
            "spawnPolicyId": "draft:static-spawn",
            "populationPolicyId": "draft:static-population",
            "hookSetId": "draft:static-hook",
        }
        action_specs = [
            ("draft:bind-node", 2, {
                "controllerRef": "draft:static-controller",
                "nodeRef": "draft:static-node",
                "profileRef": "draft:static-profile",
            }),
            ("draft:unbind-node", 3, {
                "controllerRef": "draft:static-controller",
                "nodeRef": "draft:static-timer-node",
            }),
            ("draft:modify-state", 4, {
                "field": 3, "operator": 2, "delta": 1, "bound": 0,
                "roleMask": 1, "controllerRef": "draft:static-controller",
            }),
            ("draft:bind-spawn", 6, {"spawnPolicyRef": "draft:static-spawn"}),
            ("draft:bind-population", 8, {
                "populationPolicyRef": "draft:static-population",
            }),
            ("draft:bind-hook", 10, {"hookSetRef": "draft:static-hook"}),
            ("draft:modify-timer", 11, {
                "controllerRef": "draft:static-controller",
                "nodeRef": "draft:static-timer-node",
                "operator": 2, "value": 1,
            }),
        ]
        override = {
            "draftId": "draft:static-override",
            "match": copy.deepcopy(model["overrides"][-1]["match"]),
            "members": [], "targetMode": 0,
            "order": len(model["overrides"]) + 1,
            "dispatchPriority": 0x5000,
            "actions": [{
                "draftId": draft_id, "kind": kind, "flags": 0,
                "payload": payload,
            } for draft_id, kind, payload in action_specs],
        }
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"create": [profile]},
            "controllers": {"create": [controller]},
            "spawnPolicies": {"create": [direct_create_payload(
                self.writer, "spawnPolicies", model["spawnPolicies"][0],
                "draft:static-spawn",
            )]},
            "populationPolicies": {"create": [direct_create_payload(
                self.writer, "populationPolicies", model["populationPolicies"][0],
                "draft:static-population",
            )]},
            "hookSets": {"create": [direct_create_payload(
                self.writer, "hookSets", model["hookSets"][0],
                "draft:static-hook",
            )]},
            "overrides": {"create": [override]},
        })
        saved_override = next(
            item for item in self.model()["overrides"]
            if item["stableId"] == mapping["draft:static-override"]
        )
        words = {
            action["kind"]: tuple(
                int.from_bytes(bytes(action["payload"][offset:offset + 2]), "little")
                for offset in range(0, 8, 2)
            )
            for action in saved_override["actions"]
        }
        self.assertEqual(words[2][:3], (
            mapping["draft:static-controller"], mapping["draft:static-node"],
            mapping["draft:static-profile"],
        ))
        self.assertEqual(words[3][:2], (
            mapping["draft:static-controller"], mapping["draft:static-timer-node"],
        ))
        self.assertEqual(words[4][3], mapping["draft:static-controller"])
        self.assertEqual(words[6][0], mapping["draft:static-spawn"])
        self.assertEqual(words[8][0], mapping["draft:static-population"])
        self.assertEqual(words[10][0], mapping["draft:static-hook"])
        self.assertEqual(words[11][:2], (
            mapping["draft:static-controller"], mapping["draft:static-timer-node"],
        ))

    def test_malformed_typed_static_payloads_are_rejected_atomically(self):
        model = self.model()
        source_override = model["overrides"][0]
        controller = model["controllers"][0]
        timer_node = next(
            node for node in controller["nodes"]
            if node["semanticRoleId"] == 3 and not node["base"]
        )
        cases = (
            (4, {"field": 22, "operator": 1, "delta": 0, "bound": 0,
                 "roleMask": 1, "controllerRef": controller["stableId"]}),
            (4, {"field": 3, "operator": 7, "delta": 0, "bound": 0,
                 "roleMask": 1, "controllerRef": controller["stableId"]}),
            (11, {"controllerRef": controller["stableId"],
                  "nodeRef": timer_node["stableId"], "operator": 2, "value": 33}),
        )
        before = self.bytes()
        for kind, payload in cases:
            with self.subTest(kind=kind, payload=payload), self.assertRaises(
                    (self.writer.BehaviorModelWriteError, self.writer.v40.ModelError)):
                override = direct_payload(self.writer, "overrides", source_override)
                override["actions"][0].update({"kind": kind, "payload": payload})
                self.writer.apply_behavior_model_changes(self.workspace, {
                    "overrides": {"update": [override]},
                })
            self.assertEqual(self.bytes(), before)

    def test_complete_behavior_set_and_explicit_assignment_save_atomically(self):
        model = self.model()
        source_controller = model["controllers"][0]
        source_nodes = source_controller["nodes"][:3]
        source_profiles = [
            next(profile for profile in model["stateProfiles"]
                 if profile["stableId"] == node["profileId"])
            for node in source_nodes
        ]
        profile_drafts = [
            profile_payload(profile, draft_id=f"draft:set-profile-{index}",
                            name=f"Behavior set profile {index}")
            for index, profile in enumerate(source_profiles)
        ]
        nodes = [
            node_payload(
                node, draft_id=f"draft:set-node-{index}",
                profile_ref=f"draft:set-profile-{index}",
            )
            for index, node in enumerate(source_nodes)
        ]
        controller = controller_payload(
            source_controller, draft_id="draft:set-controller", nodes=nodes,
            name="Complete behavior set controller",
        )
        controller["policyIds"] = {
            "spawnPolicyId": "draft:set-spawn",
            "populationPolicyId": "draft:set-population",
            "hookSetId": "draft:set-hooks",
        }

        source_transition = model["transitions"][0]
        source_definition = copy.deepcopy(next(
            item for item in model["overrideDefinitions"]
            if item["stableId"] == source_transition["definitionId"]
        ))
        source_rule = copy.deepcopy(next(
            item for item in model["applicability"]
            if item["stableId"] == source_definition["applicabilityId"]
        ))
        active_operation = {
            "draftId": "draft:set-active-operation",
            "definitionId": "draft:set-active-definition",
            "ownerId": source_transition["ownerId"],
            "replacementDefinitionId": None, "policyId": None,
            "instanceKey": "draft:set-active-definition",
            "kind": 1, "busyPolicy": 1, "required": False,
        }
        awareness = transition_payload(
            source_transition, source_definition, source_rule,
            "draft:set-awareness", "draft:set-active-definition",
            applicability_identity="draft:set-active-applicability",
            operation=active_operation,
        )
        awareness.update({
            "name": "Awareness", "controllerIds": ["draft:set-controller"],
            "trigger": 1, "fromRoleMask": 1, "dispatchPriority": 0xC000,
            "order": len(model["transitions"]),
        })

        tired_definition = copy.deepcopy(source_definition)
        tired_definition.update({
            "priority": 100, "channel": 2, "semanticRoleId": 3,
            "mapLifetime": 2, "battleLifetime": 1,
            "timerClock": 1, "timerSource": 1, "hiddenTimerPolicy": 1,
            "recoveryPolicy": 1, "timerValue": 4,
            "recoveryTransitionId": "draft:set-recovery",
        })
        tired_apply = {
            "draftId": "draft:set-tired-operation",
            "definitionId": "draft:set-tired-definition",
            "ownerId": model["owners"][1]["stableId"],
            "replacementDefinitionId": None, "policyId": None,
            "instanceKey": "draft:set-tired-definition",
            "kind": 1, "busyPolicy": 1, "required": False,
        }
        exhaustion = transition_payload(
            source_transition, tired_definition, source_rule,
            "draft:set-exhaustion", "draft:set-tired-definition",
            applicability_identity="draft:set-tired-applicability",
            operation=tired_apply,
        )
        exhaustion.update({
            "name": "Exhaustion", "controllerIds": ["draft:set-controller"],
            "ownerId": model["owners"][1]["stableId"],
            "trigger": 3, "fromRoleMask": 2, "dispatchPriority": 0xC001,
            "order": len(model["transitions"]) + 1,
        })
        tired_remove = {
            "draftId": "draft:set-recovery-operation",
            "definitionId": "draft:set-tired-definition",
            "ownerId": model["owners"][1]["stableId"],
            "replacementDefinitionId": None, "policyId": None,
            "instanceKey": None, "kind": 3, "busyPolicy": 1,
            "required": True,
        }
        recovery = transition_payload(
            source_transition, tired_definition, source_rule,
            "draft:set-recovery", "draft:set-tired-definition",
            applicability_identity="draft:set-tired-applicability",
            operation=tired_remove,
        )
        recovery.update({
            "name": "Recovery", "controllerIds": ["draft:set-controller"],
            "ownerId": model["owners"][1]["stableId"],
            "trigger": 4, "fromRoleMask": 4, "dispatchPriority": 0xC002,
            "order": len(model["transitions"]) + 2,
            "recoveryActions": [{
                "draftId": "draft:set-recovery-action",
                "ownerId": model["owners"][1]["stableId"],
                "kind": 1, "required": True,
            }],
        })

        assignment_action = {
            "draftId": "draft:set-assignment-action", "kind": 1, "flags": 0,
            "payload": {"controllerRef": "draft:set-controller"},
        }
        assignment = direct_create_payload(
            self.writer, "genericAssignments", model["genericAssignments"][0],
            "draft:set-assignment",
        )
        assignment.update({
            "controllerIndex": "draft:set-assignment-action",
            "dispatchPriority": 0x5000,
        })
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"create": profile_drafts},
            "controllers": {"create": [controller]},
            "transitions": {"create": [awareness, exhaustion, recovery]},
            "spawnPolicies": {"create": [direct_create_payload(
                self.writer, "spawnPolicies", model["spawnPolicies"][0],
                "draft:set-spawn",
            )]},
            "populationPolicies": {"create": [direct_create_payload(
                self.writer, "populationPolicies", model["populationPolicies"][0],
                "draft:set-population",
            )]},
            "hookSets": {"create": [direct_create_payload(
                self.writer, "hookSets", model["hookSets"][0],
                "draft:set-hooks",
            )]},
            "assignmentActions": {"create": [assignment_action]},
            "genericAssignments": {"create": [assignment]},
        })
        saved = self.model()
        saved_controller = next(
            item for item in saved["controllers"]
            if item["stableId"] == mapping["draft:set-controller"]
        )
        self.assertEqual(
            [node["profileId"] for node in saved_controller["nodes"]],
            [mapping[f"draft:set-profile-{index}"] for index in range(3)],
        )
        self.assertEqual(saved_controller["spawnPolicyId"], mapping["draft:set-spawn"])
        saved_action_index = next(
            index for index, item in enumerate(saved["assignmentActions"])
            if item["stableId"] == mapping["draft:set-assignment-action"]
        )
        saved_assignment = next(
            item for item in saved["genericAssignments"]
            if item["stableId"] == mapping["draft:set-assignment"]
        )
        self.assertEqual(saved_assignment["controllerIndex"], saved_action_index)
        saved_action = saved["assignmentActions"][saved_action_index]
        self.assertEqual(
            int.from_bytes(bytes(saved_action["payload"][:2]), "little"),
            saved_controller["stableId"],
        )
        self.assertLess(len(self.writer.v40.read_inc(self.workspace / INC_REL)), 0x3000)

    def test_real_complete_set_frontend_payload_persists_scoped_graph(self):
        viewer = load_viewer()
        viewer.V40_BEHAVIOR_DATA_SOURCE = self.workspace / INC_REL
        viewer.V40_BEHAVIOR_MODEL_SOURCE = self.workspace / MODEL_REL
        editor_model = viewer.build_v40_state_profile_editor_data()
        script = r'''import fs from "node:fs";
import {createCompleteBehaviorSetDraft, compactBehaviorModelDraft} from "./tools/overworld-viewer-v2/static/profiles.js";
const model = JSON.parse(fs.readFileSync(0, "utf8"));
const profiles = new Map(model.stateProfiles.map((item) => [String(item.stableId), item]));
const source = model.controllers[0];
const roleTemplates = Object.fromEntries([["calm", 1], ["active", 2], ["tired", 3]].map(([name, role]) => {
  const node = source.nodes.find((item) => Number(item.semanticRoleId) === role);
  return [name, profiles.get(String(node.profileStableId))];
}));
const graph = createCompleteBehaviorSetDraft({
  fields: model.stateProfileFields,
  templateProfile: roleTemplates.calm,
  roleTemplates,
  existingTransitions: model.transitionGraph.transitions,
  policyDefaults: source.policyIds,
  spawnPolicyTemplate: model.policyCatalog.spawnPolicies[0],
  populationPolicyTemplate: model.policyCatalog.populationPolicies[0],
  hookSetTemplate: model.policyCatalog.hookSets[0],
  awarenessOwnerId: model.owners[0].stableId,
  exhaustionOwnerId: model.owners[1].stableId,
  triggerIds: model.transitionGraph.triggerOptions.slice(0, 3).map((item) => item.value),
  transitionOrderStart: model.transitionGraph.transitions.length,
  stateName: "Frontend complete set",
  controllerName: "Frontend complete controller",
  assignment: {kind: "match", dispatchPriority: 0x5000, match: {
    groupMask: 1, species: 25, terrain: 255, minimumLevel: 0,
    maximumLevel: 0, shiny: 255, behaviorClass: 255,
  }},
});
const transaction = compactBehaviorModelDraft({
  stateProfiles: {create: graph.profiles},
  controllers: {create: [graph.controller]},
  transitions: {create: graph.transitions},
  spawnPolicies: {create: [graph.spawnPolicy]},
  populationPolicies: {create: [graph.populationPolicy]},
  hookSets: {create: [graph.hookSet]},
  assignmentActions: {create: [graph.assignmentAction]},
  genericAssignments: {create: [graph.assignment]},
}, model);
process.stdout.write(JSON.stringify({transaction, ids: {
  controller: graph.controller.draftId,
  profiles: graph.profiles.map((item) => item.draftId),
  spawn: graph.spawnPolicy.draftId,
  population: graph.populationPolicy.draftId,
  hook: graph.hookSet.draftId,
  assignmentAction: graph.assignmentAction.draftId,
  assignment: graph.assignment.draftId,
  transitions: graph.transitions.map((item) => item.draftId),
  activeDefinition: graph.transitions[0].candidateDefinition.draftId,
  tiredDefinition: graph.transitions[1].candidateDefinition.draftId,
}}));'''
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script], cwd=ROOT,
            input=json.dumps(editor_model), text=True, capture_output=True, check=True,
        )
        authored = json.loads(completed.stdout)
        mapping = self.writer.apply_behavior_model_changes(
            self.workspace, authored["transaction"]
        )
        ids = authored["ids"]
        saved = self.model()
        controller = next(
            item for item in saved["controllers"]
            if item["stableId"] == mapping[ids["controller"]]
        )
        self.assertEqual([node["profileId"] for node in controller["nodes"]], [
            mapping[draft] for draft in ids["profiles"]
        ])
        self.assertEqual(controller["spawnPolicyId"], mapping[ids["spawn"]])
        self.assertEqual(controller["populationPolicyId"], mapping[ids["population"]])
        self.assertEqual(controller["hookSetId"], mapping[ids["hook"]])

        authored_transitions = [
            next(item for item in saved["transitions"]
                 if item["stableId"] == mapping[draft_id])
            for draft_id in ids["transitions"]
        ]
        self.assertEqual([item["trigger"] for item in authored_transitions], [1, 2, 3])
        exhaustion = authored_transitions[1]
        self.assertEqual(
            [(guard["kind"], guard["payload"], guard["referenceId"])
             for guard in exhaustion["guards"]],
            [(8, 2, 0)],
        )
        recovery = authored_transitions[2]
        self.assertEqual(recovery["definitionId"], mapping[ids["tiredDefinition"]])
        self.assertEqual(
            [(guard["kind"], guard["payload"], guard["referenceId"])
             for guard in recovery["guards"]],
            [(6, 3, 0)],
        )
        self.assertEqual(
            [(operation["kind"], operation["definitionId"], operation["required"])
             for operation in recovery["operations"]],
            [(3, mapping[ids["tiredDefinition"]], 1)],
        )
        self.assertEqual(
            [(action["phase"], action["kind"]) for action in recovery["actions"]],
            [(2, 2), (2, 4)],
        )
        self.assertEqual(
            [(action["ownerId"], action["kind"], action["required"])
             for action in recovery["recoveryActions"]],
            [(recovery["ownerId"], 2, 1)],
        )

        definition_ids = {
            mapping[ids["activeDefinition"]], mapping[ids["tiredDefinition"]]
        }
        definitions = {
            item["stableId"]: item for item in saved["overrideDefinitions"]
            if item["stableId"] in definition_ids
        }
        self.assertEqual(set(definitions), definition_ids)
        rules = {item["stableId"]: item for item in saved["applicability"]}
        for definition in definitions.values():
            self.assertEqual((definition["controllerId"], definition["hasTiredOriginKind"],
                              definition["hasRequiredOwnerId"], definition["requiredOwnerId"]),
                             (controller["stableId"], 0, 0, 0))
            self.assertEqual(
                (rules[definition["applicabilityId"]]["kind"],
                 rules[definition["applicabilityId"]]["controllerId"]),
                (3, controller["stableId"]),
            )
        action_id = mapping[ids["assignmentAction"]]
        action_index = next(
            index for index, item in enumerate(saved["assignmentActions"])
            if item["stableId"] == action_id
        )
        assignment = next(
            item for item in saved["genericAssignments"]
            if item["stableId"] == mapping[ids["assignment"]]
        )
        self.assertEqual(assignment["controllerIndex"], action_index)
        self.assertEqual(
            int.from_bytes(bytes(saved["assignmentActions"][action_index]["payload"][:2]), "little"),
            controller["stableId"],
        )

    def test_two_frontend_complete_sets_fit_across_sequential_saves_and_resolve(self):
        viewer = load_viewer()
        viewer.V40_BEHAVIOR_DATA_SOURCE = self.workspace / INC_REL
        viewer.V40_BEHAVIOR_MODEL_SOURCE = self.workspace / MODEL_REL
        baseline_size = len(self.writer.v40.read_inc(self.workspace / INC_REL))
        script = r'''import fs from "node:fs";
import {createCompleteBehaviorSetDraft, compactBehaviorModelDraft} from "./tools/overworld-viewer-v2/static/profiles.js";
const {model, suffix} = JSON.parse(fs.readFileSync(0, "utf8"));
const profiles = new Map(model.stateProfiles.map((item) => [String(item.stableId), item]));
const source = model.controllers[0];
const roleTemplates = Object.fromEntries([["calm", 1], ["active", 2], ["tired", 3]].map(([name, role]) => {
  const node = source.nodes.find((item) => Number(item.semanticRoleId) === role);
  return [name, profiles.get(String(node.profileStableId))];
}));
const graph = createCompleteBehaviorSetDraft({
  fields: model.stateProfileFields, templateProfile: roleTemplates.calm, roleTemplates,
  existingTransitions: model.transitionGraph.transitions, policyDefaults: source.policyIds,
  spawnPolicyTemplate: model.policyCatalog.spawnPolicies[0],
  populationPolicyTemplate: model.policyCatalog.populationPolicies[0],
  hookSetTemplate: model.policyCatalog.hookSets[0],
  awarenessOwnerId: model.owners[0].stableId, exhaustionOwnerId: model.owners[1].stableId,
  triggerIds: model.transitionGraph.triggerOptions.slice(0, 3).map((item) => item.value),
  transitionOrderStart: model.transitionGraph.transitions.length,
  stateName: `Capacity set ${suffix}`, controllerName: `Capacity controller ${suffix}`,
  assignment: {kind: "match", dispatchPriority: 0x6000 + suffix, match: {
    groupMask: 1 << suffix, species: 1000 + suffix, terrain: 255,
    minimumLevel: 0, maximumLevel: 0, shiny: 255, behaviorClass: 255,
  }},
});
process.stdout.write(JSON.stringify(compactBehaviorModelDraft({
  stateProfiles: {create: graph.profiles}, controllers: {create: [graph.controller]},
  transitions: {create: graph.transitions}, spawnPolicies: {create: [graph.spawnPolicy]},
  populationPolicies: {create: [graph.populationPolicy]}, hookSets: {create: [graph.hookSet]},
  assignmentActions: {create: [graph.assignmentAction]},
  genericAssignments: {create: [graph.assignment]},
}, model)));'''
        sizes = []
        for suffix in (1, 2):
            editor_model = viewer.build_v40_state_profile_editor_data()
            completed = subprocess.run(
                ["node", "--input-type=module", "-e", script], cwd=ROOT,
                input=json.dumps({"model": editor_model, "suffix": suffix}),
                text=True, capture_output=True, check=True,
            )
            self.writer.apply_behavior_model_changes(
                self.workspace, json.loads(completed.stdout)
            )
            blob = self.writer.v40.read_inc(self.workspace / INC_REL)
            reparsed = self.writer.v40.decode_blob(
                blob, stable_id_history=self.model()["stableIdHistory"],
            )
            self.assertEqual(self.writer.v40.encode_model(reparsed), blob)
            sizes.append(len(blob))
            from scripts.resolve_overworld_wild_behavior_v40 import validate_wire
            with tempfile.TemporaryDirectory() as directory:
                blob_path = Path(directory) / "catalog.bin"
                blob_path.write_bytes(blob)
                validate_wire(blob_path, self.workspace / HEADER_REL)
        saved = self.model()
        self.assertEqual(len(saved["controllers"]), 5)
        self.assertEqual(len({profile["bodyId"] for profile in saved["stateProfiles"]}), 48)
        self.assertEqual(len(saved["stateProfiles"]), 64)
        self.assertGreater(sizes[0], baseline_size)
        self.assertGreater(sizes[1], sizes[0])
        self.assertLessEqual(sizes[1], 0x3000)
        self.assertEqual(sizes, [11480, 11940])

    def test_multi_entity_create_allocates_parent_then_owned_descendants(self):
        model = self.model()
        profile_draft = profile_payload(
            model["stateProfiles"][0], draft_id="draft:profile", name="Editor profile"
        )
        node = node_payload(
            model["controllers"][0]["nodes"][0],
            draft_id="draft:node", profile_ref="draft:profile",
        )
        controller_draft = controller_payload(
            model["controllers"][0], draft_id="draft:controller",
            nodes=[node], name="Editor controller",
        )
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "modelVersion": 40,
            "stateProfiles": {"create": [profile_draft]},
            "controllers": {"create": [controller_draft]},
        })
        self.assertEqual(mapping["draft:node"], mapping["draft:controller"] + 1)
        self.assertEqual(mapping["draft:controller"], mapping["draft:profile"] + 1)
        saved = self.model()
        profile = next(item for item in saved["stateProfiles"] if item["stableId"] == mapping["draft:profile"])
        controller = next(item for item in saved["controllers"] if item["stableId"] == mapping["draft:controller"])
        self.assertEqual(profile["name"], "Editor profile")
        self.assertEqual(profile["bodyId"], model["stateProfiles"][0]["bodyId"])
        self.assertEqual(controller["nodes"][0]["profileId"], mapping["draft:profile"])
        self.assertEqual(controller["nodes"][0]["stableId"], mapping["draft:node"])

    def test_reorder_and_metadata_update_preserve_existing_ids(self):
        model = self.model()
        controller = model["controllers"][0]
        original_ids = [node["stableId"] for node in controller["nodes"]]
        update = controller_payload(
            controller, nodes=[node_payload(node) for node in reversed(controller["nodes"])],
            name="Reordered controller",
        )
        profile = profile_payload(
            model["stateProfiles"][0], name="Renamed state"
        )
        profile["descriptiveTags"] = ["bird", "calm"]
        transition = model["transitions"][0]
        transition_update = saved_transition_payload(model, transition, name="Named transition")
        self.writer.apply_behavior_model_changes(self.workspace, {
            "controllers": {"update": [update]},
            "stateProfiles": {"update": [profile]},
            "transitions": {"update": [transition_update]},
        })
        saved = self.model()
        actual = next(item for item in saved["controllers"] if item["stableId"] == controller["stableId"])
        self.assertEqual([node["stableId"] for node in actual["nodes"]], list(reversed(original_ids)))
        self.assertEqual(actual["name"], "Reordered controller")
        actual_profile = next(item for item in saved["stateProfiles"] if item["stableId"] == profile["stableId"])
        self.assertEqual((actual_profile["name"], actual_profile["descriptiveTags"]),
                         ("Renamed state", ["bird", "calm"]))
        actual_transition = next(item for item in saved["transitions"]
                                 if item["stableId"] == transition["stableId"])
        self.assertEqual(actual_transition["name"], "Named transition")
        blob = self.writer.v40.read_inc(self.workspace / INC_REL)
        decoded = self.writer.v40.decode_blob(blob, stable_id_history=saved["stableIdHistory"])
        self.assertEqual(
            self.writer.v40.merge_authored_metadata(decoded, saved), saved
        )
        viewer = load_viewer()
        viewer.V40_BEHAVIOR_DATA_SOURCE = self.workspace / INC_REL
        viewer.V40_BEHAVIOR_MODEL_SOURCE = self.workspace / MODEL_REL
        editor = viewer.build_v40_state_profile_editor_data()
        self.assertEqual(next(item for item in editor["stateProfiles"]
                              if item["stableId"] == profile["stableId"])["name"], "Renamed state")
        self.assertEqual(next(item for item in editor["stateProfiles"]
                              if item["stableId"] == profile["stableId"])["descriptiveTags"],
                         ["bird", "calm"])
        self.assertEqual(next(item for item in editor["controllers"]
                              if item["stableId"] == controller["stableId"])["name"],
                         "Reordered controller")
        self.assertEqual(next(item for item in editor["transitionGraph"]["transitions"]
                              if item["stableId"] == transition["stableId"])["name"],
                         "Named transition")

    def test_transition_reorder_survives_wire_and_reader_reload(self):
        model = self.model()
        generated_ids = {
            item["stableId"] for item in model["overrideDefinitions"]
            if item["hasRequiredOwnerId"] or item["hasTiredOriginKind"]
        }
        first, second = next(
            (left, right)
            for left, right in zip(model["transitions"], model["transitions"][1:])
            if left["definitionId"] not in generated_ids
            and right["definitionId"] not in generated_ids
        )
        first_update = saved_transition_payload(
            model, first, name=first.get("name", first["registryKey"])
        )
        second_update = saved_transition_payload(
            model, second, name=second.get("name", second["registryKey"])
        )
        first_update["order"], second_update["order"] = second["order"], first["order"]
        stable_ids = {item["stableId"] for item in model["transitions"]}
        self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"update": [first_update, second_update]},
        })
        saved = self.model()
        self.assertEqual({item["stableId"] for item in saved["transitions"]}, stable_ids)
        start = first["order"]
        self.assertEqual([item["stableId"] for item in saved["transitions"][start:start + 2]],
                         [second["stableId"], first["stableId"]])
        self.assertEqual([item["order"] for item in saved["transitions"]],
                         list(range(len(saved["transitions"]))))
        blob = self.writer.v40.read_inc(self.workspace / INC_REL)
        decoded = self.writer.v40.decode_blob(blob, stable_id_history=saved["stableIdHistory"])
        self.assertEqual([item["stableId"] for item in decoded["transitions"][start:start + 2]],
                         [second["stableId"], first["stableId"]])
        viewer = load_viewer()
        viewer.V40_BEHAVIOR_DATA_SOURCE = self.workspace / INC_REL
        viewer.V40_BEHAVIOR_MODEL_SOURCE = self.workspace / MODEL_REL
        reloaded = viewer.build_v40_state_profile_editor_data()
        self.assertEqual(
            [item["stableId"] for item in reloaded["transitionGraph"]["transitions"][start:start + 2]],
            [second["stableId"], first["stableId"]],
        )

    def test_active_and_tired_duplicates_preserve_template_provenance(self):
        model = self.model()
        sources = [next(item for item in model["stateProfiles"]
                        if item["body"]["provenanceKind"] == kind) for kind in (2, 3)]
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"create": [
                profile_payload(sources[0], draft_id="draft:active"),
                profile_payload(sources[1], draft_id="draft:tired"),
            ]},
        })
        saved = self.model()
        by_id = {item["stableId"]: item for item in saved["stateProfiles"]}
        for draft, source in (("draft:active", sources[0]), ("draft:tired", sources[1])):
            copy_record = by_id[mapping[draft]]
            self.assertEqual(copy_record["body"]["provenanceKind"], source["body"]["provenanceKind"])
            self.assertEqual(copy_record["provenanceId"], source["provenanceId"])

    def test_local_clone_remaps_owned_applicability_and_controller_refs(self):
        model = self.model()
        source_controller = model["controllers"][0]
        node = node_payload(source_controller["nodes"][0], draft_id="draft:local-node")
        controller = controller_payload(
            source_controller, draft_id="draft:local-controller", nodes=[node]
        )
        source_transition = model["transitions"][0]
        definition = copy.deepcopy(next(item for item in model["overrideDefinitions"]
                                        if item["stableId"] == source_transition["definitionId"]))
        rule = copy.deepcopy(next(item for item in model["applicability"]
                                  if item["stableId"] == definition["applicabilityId"]))
        definition.update({
            "controllerId": "draft:local-controller",
            "nodeId": "draft:local-node",
            "selectorKind": 1,
            "semanticRoleId": 0,
        })
        rule["controllerId"] = "draft:local-controller"
        rule["kind"] |= 2
        transition = transition_payload(
            source_transition, definition, rule, "draft:local-transition", "draft:local-definition",
            applicability_identity="draft:local-applicability",
        )
        transition["controllerIds"] = ["draft:local-controller"]
        transition["dispatchPriority"] = 0xC010
        transition["order"] = len(model["transitions"])
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "controllers": {"create": [controller]},
            "transitions": {"create": [transition]},
        })
        saved = self.model()
        saved_definition = next(item for item in saved["overrideDefinitions"]
                                if item["stableId"] == mapping["draft:local-definition"])
        saved_rule = next(item for item in saved["applicability"]
                          if item["stableId"] == mapping["draft:local-applicability"])
        self.assertEqual(saved_definition["controllerId"], mapping["draft:local-controller"])
        self.assertEqual(saved_definition["nodeId"], mapping["draft:local-node"])
        self.assertEqual(saved_definition["applicabilityId"], saved_rule["stableId"])
        self.assertEqual(saved_rule["controllerId"], mapping["draft:local-controller"])

    def test_applicability_only_controller_scope_is_enforced(self):
        model = self.model()
        source_transition = model["transitions"][0]
        definition = copy.deepcopy(next(
            item for item in model["overrideDefinitions"]
            if item["stableId"] == source_transition["definitionId"]
        ))
        self.assertEqual(definition["controllerId"], 0)
        rule = copy.deepcopy(next(
            item for item in model["applicability"]
            if item["stableId"] == definition["applicabilityId"]
        ))
        controller_id = model["controllers"][0]["stableId"]
        rule.update({"kind": rule["kind"] | 2, "controllerId": controller_id})
        transition = transition_payload(
            source_transition, definition, rule,
            "draft:app-scoped-transition", "draft:app-scoped-definition",
            applicability_identity="draft:app-scoped-applicability",
        )
        transition.update({
            "controllerIds": [model["controllers"][1]["stableId"]],
            "dispatchPriority": 0xC011,
            "order": len(model["transitions"]),
        })
        before = self.bytes()
        with self.assertRaisesRegex(
                self.writer.BehaviorModelWriteError,
                "controllerIds conflicts with its candidate-definition scope"):
            self.writer.apply_behavior_model_changes(self.workspace, {
                "transitions": {"create": [transition]},
            })
        self.assertEqual(self.bytes(), before)

        transition["controllerIds"] = [controller_id]
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"create": [transition]},
        })
        saved = self.model()
        saved_definition = next(
            item for item in saved["overrideDefinitions"]
            if item["stableId"] == mapping["draft:app-scoped-definition"]
        )
        saved_rule = next(
            item for item in saved["applicability"]
            if item["stableId"] == saved_definition["applicabilityId"]
        )
        self.assertEqual(saved_definition["controllerId"], 0)
        self.assertEqual(saved_rule["controllerId"], controller_id)

    def test_shared_definition_and_applicability_retire_after_last_backlink(self):
        model = self.model()
        source_transition = model["transitions"][0]
        definition = copy.deepcopy(next(item for item in model["overrideDefinitions"]
                                        if item["stableId"] == source_transition["definitionId"]))
        rule = copy.deepcopy(next(item for item in model["applicability"]
                                  if item["stableId"] == definition["applicabilityId"]))
        definition.update({"controllerId": 0, "nodeId": 0, "recoveryTransitionId": 0})
        left = transition_payload(
            source_transition, definition, rule, "draft:shared-left", "draft:shared-definition",
            applicability_identity="draft:shared-applicability",
        )
        right = transition_payload(
            source_transition, definition, rule, "draft:shared-right", "draft:shared-definition",
            applicability_identity="draft:shared-applicability",
        )
        left["dispatchPriority"] = 0xC020
        right["dispatchPriority"] = 0xC021
        left["order"] = len(model["transitions"])
        right["order"] = len(model["transitions"]) + 1
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"create": [left, right]},
        })
        self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"remove": [mapping["draft:shared-left"]]},
        })
        middle = self.model()
        self.assertIn(mapping["draft:shared-definition"],
                      {item["stableId"] for item in middle["overrideDefinitions"]})
        self.assertIn(mapping["draft:shared-applicability"],
                      {item["stableId"] for item in middle["applicability"]})
        self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"remove": [mapping["draft:shared-right"]]},
        })
        final = self.model()
        self.assertNotIn(mapping["draft:shared-definition"],
                         {item["stableId"] for item in final["overrideDefinitions"]})
        self.assertNotIn(mapping["draft:shared-applicability"],
                         {item["stableId"] for item in final["applicability"]})
        tombstones = {event["registryKey"] for event in final["stableIdHistory"]["extensions"]
                      if event["kind"] == "retire"}
        self.assertIn(f"editor:override-definition:{mapping['draft:shared-definition']}", tombstones)
        self.assertIn(f"editor:applicability:{mapping['draft:shared-applicability']}", tombstones)

    def test_rebind_retires_replaced_owned_definition_and_applicability(self):
        model = self.model()
        source = model["transitions"][0]
        definition = copy.deepcopy(next(item for item in model["overrideDefinitions"]
                                        if item["stableId"] == source["definitionId"]))
        rule = copy.deepcopy(next(item for item in model["applicability"]
                                  if item["stableId"] == definition["applicabilityId"]))
        definition.update({"controllerId": 0, "nodeId": 0, "recoveryTransitionId": 0})
        created = transition_payload(
            source, definition, rule, "draft:rebind-transition", "draft:old-definition",
            applicability_identity="draft:old-applicability",
        )
        created["dispatchPriority"] = 0xC030
        created["order"] = len(model["transitions"])
        first = self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"create": [created]},
        })
        saved = self.model()
        transition = next(item for item in saved["transitions"]
                          if item["stableId"] == first["draft:rebind-transition"])
        rebound = transition_payload(
            transition, definition, rule, transition["stableId"], "draft:new-definition",
            applicability_identity="draft:new-applicability",
        )
        second = self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"update": [rebound]},
        })
        final = self.model()
        definition_ids = {item["stableId"] for item in final["overrideDefinitions"]}
        applicability_ids = {item["stableId"] for item in final["applicability"]}
        self.assertNotIn(first["draft:old-definition"], definition_ids)
        self.assertNotIn(first["draft:old-applicability"], applicability_ids)
        self.assertIn(second["draft:new-definition"], definition_ids)
        self.assertIn(second["draft:new-applicability"], applicability_ids)

    def test_delete_tombstones_profile_but_preserves_shared_body(self):
        source = self.model()["stateProfiles"][0]
        body_key = source["bodyRegistryKey"]
        first = self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"create": [profile_payload(source, draft_id="draft:first")]},
        })["draft:first"]
        self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"remove": [first]},
        })
        deleted = self.model()
        allocations = deleted["stableIdHistory"]["extensions"]
        retired = [event["registryKey"] for event in allocations if event["kind"] == "retire"]
        self.assertIn(f"editor:state-profile:{first}", retired)
        self.assertNotIn(body_key, retired)
        second = self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"create": [profile_payload(source, draft_id="draft:second")]},
        })["draft:second"]
        self.assertGreater(second, first)

    def test_shared_body_update_is_copy_on_write(self):
        model = self.model()
        shared_id = next(
            body_id for body_id in {item["bodyId"] for item in model["stateProfiles"]}
            if sum(item["bodyId"] == body_id for item in model["stateProfiles"]) > 1
        )
        left, right = [
            item for item in model["stateProfiles"] if item["bodyId"] == shared_id
        ][:2]
        update = profile_payload(left, name="Copy-on-write profile")
        update["values"]["speed"] = 2 if update["values"]["speed"] != 2 else 1
        self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"update": [update]},
        })
        saved = self.model()
        updated = next(item for item in saved["stateProfiles"] if item["stableId"] == left["stableId"])
        untouched = next(item for item in saved["stateProfiles"] if item["stableId"] == right["stableId"])
        self.assertNotEqual(updated["bodyId"], shared_id)
        self.assertEqual(untouched["bodyId"], shared_id)
        self.assertNotEqual(updated["body"]["values"], untouched["body"]["values"])

    def test_body_split_rejoin_and_last_reference_retirement(self):
        model = self.model()
        source = model["stateProfiles"][0]
        existing_signatures = {
            tuple(profile["body"]["values"][field] for field in self.writer.v40.STATE_FIELDS)
            for profile in model["stateProfiles"]
        }
        unique_values = []
        for movement_range in range(31, -1, -1):
            values = copy.deepcopy(source["body"]["values"])
            values["movementRange"] = movement_range
            signature = tuple(values[field] for field in self.writer.v40.STATE_FIELDS)
            if signature not in existing_signatures:
                unique_values.append(values)
                existing_signatures.add(signature)
            if len(unique_values) == 2:
                break
        self.assertEqual(len(unique_values), 2)

        left = profile_payload(source, draft_id="draft:lifecycle-left", name="Lifecycle left")
        right = profile_payload(source, draft_id="draft:lifecycle-right", name="Lifecycle right")
        left["values"] = copy.deepcopy(unique_values[0])
        right["values"] = copy.deepcopy(unique_values[0])
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"create": [left, right]},
        })
        saved = self.model()
        left_id, right_id = mapping["draft:lifecycle-left"], mapping["draft:lifecycle-right"]
        created_left = next(item for item in saved["stateProfiles"] if item["stableId"] == left_id)
        created_right = next(item for item in saved["stateProfiles"] if item["stableId"] == right_id)
        self.assertEqual(created_left["bodyId"], created_right["bodyId"])
        common_body_id = created_left["bodyId"]
        common_body_key = created_left["bodyRegistryKey"]

        split = profile_payload(created_left, name="Lifecycle split")
        split["values"] = copy.deepcopy(unique_values[1])
        self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"update": [split]},
        })
        saved = self.model()
        split_left = next(item for item in saved["stateProfiles"] if item["stableId"] == left_id)
        shared_right = next(item for item in saved["stateProfiles"] if item["stableId"] == right_id)
        self.assertNotEqual(split_left["bodyId"], common_body_id)
        self.assertEqual(shared_right["bodyId"], common_body_id)
        split_body_key = split_left["bodyRegistryKey"]
        allocations_before_rejoin = {
            event["registryKey"] for event in saved["stableIdHistory"]["extensions"]
            if event["kind"] == "allocate"
        }

        rejoin = profile_payload(split_left, name="Lifecycle rejoined")
        rejoin["values"] = copy.deepcopy(shared_right["body"]["values"])
        self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"update": [rejoin]},
        })
        saved = self.model()
        rejoined = next(item for item in saved["stateProfiles"] if item["stableId"] == left_id)
        self.assertEqual(rejoined["bodyId"], common_body_id)
        retired = {
            event["registryKey"] for event in saved["stableIdHistory"]["extensions"]
            if event["kind"] == "retire"
        }
        allocations_after_rejoin = {
            event["registryKey"] for event in saved["stableIdHistory"]["extensions"]
            if event["kind"] == "allocate"
        }
        self.assertEqual(allocations_after_rejoin, allocations_before_rejoin)
        self.assertIn(split_body_key, retired)
        self.assertNotIn(common_body_key, retired)

        self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"remove": [left_id]},
        })
        after_first_delete = self.model()
        retired = {
            event["registryKey"] for event in after_first_delete["stableIdHistory"]["extensions"]
            if event["kind"] == "retire"
        }
        self.assertNotIn(common_body_key, retired)
        self.assertIn(common_body_id, {
            item["bodyId"] for item in after_first_delete["stateProfiles"]
        })

        self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"remove": [right_id]},
        })
        after_last_delete = self.model()
        retired = {
            event["registryKey"] for event in after_last_delete["stableIdHistory"]["extensions"]
            if event["kind"] == "retire"
        }
        self.assertIn(common_body_key, retired)
        self.assertNotIn(common_body_id, {
            item["bodyId"] for item in after_last_delete["stateProfiles"]
        })

    def test_batch_body_reuse_updates_live_reference_counts(self):
        model = self.model()
        body_counts = {
            body_id: sum(item["bodyId"] == body_id for item in model["stateProfiles"])
            for body_id in {item["bodyId"] for item in model["stateProfiles"]}
        }
        unique_by_provenance = {}
        for profile in model["stateProfiles"]:
            if body_counts[profile["bodyId"]] == 1:
                unique_by_provenance.setdefault(
                    profile["body"]["provenanceKind"], [],
                ).append(profile)
        first, second = next(
            profiles[:2] for profiles in unique_by_provenance.values()
            if len(profiles) >= 2
        )
        existing_signatures = {
            tuple(profile["body"]["values"][field] for field in self.writer.v40.STATE_FIELDS)
            for profile in model["stateProfiles"]
        }
        third_values = None
        for movement_range in range(32, -1, -1):
            candidate = copy.deepcopy(second["body"]["values"])
            candidate["movementRange"] = movement_range
            signature = tuple(candidate[field] for field in self.writer.v40.STATE_FIELDS)
            if signature not in existing_signatures:
                third_values = candidate
                break
        self.assertIsNotNone(third_values)

        first_update = profile_payload(first)
        first_update["values"] = copy.deepcopy(second["body"]["values"])
        second_update = profile_payload(second)
        second_update["values"] = third_values
        self.writer.apply_behavior_model_changes(self.workspace, {
            "stateProfiles": {"update": [first_update, second_update]},
        })
        saved = self.model()
        saved_first = next(item for item in saved["stateProfiles"]
                           if item["stableId"] == first["stableId"])
        saved_second = next(item for item in saved["stateProfiles"]
                            if item["stableId"] == second["stableId"])
        self.assertEqual(saved_first["bodyId"], second["bodyId"])
        self.assertEqual(saved_first["body"]["values"], second["body"]["values"])
        self.assertNotEqual(saved_second["bodyId"], second["bodyId"])
        self.assertEqual(saved_second["body"]["values"], third_values)

    def test_deep_cycles_and_definition_references_are_remapped(self):
        model = self.model()
        transition = model["transitions"][0]
        definition = copy.deepcopy(next(
            item for item in model["overrideDefinitions"]
            if item["stableId"] == transition["definitionId"]
        ))
        applicability = copy.deepcopy(next(
            item for item in model["applicability"]
            if item["stableId"] == definition["applicabilityId"]
        ))
        definition["controllerId"] = 0
        definition["nodeId"] = 0
        left_op = {
            "draftId": "draft:left-op", "definitionId": "draft:left-def",
            "ownerId": transition["ownerId"], "replacementDefinitionId": "draft:right-def",
            "policyId": 0, "instanceKey": "draft:left-def", "kind": 2,
            "busyPolicy": 1, "required": False,
        }
        right_op = {
            "draftId": "draft:right-op", "definitionId": "draft:right-def",
            "ownerId": transition["ownerId"], "replacementDefinitionId": "draft:left-def",
            "policyId": 0, "instanceKey": "draft:right-def", "kind": 2,
            "busyPolicy": 1, "required": False,
        }
        left = transition_payload(
            transition, definition, applicability, "draft:left", "draft:left-def",
            applicability_identity="draft:left-applicability", operation=left_op,
        )
        right = transition_payload(
            transition, definition, applicability, "draft:right", "draft:right-def",
            applicability_identity="draft:right-applicability", operation=right_op,
        )
        left["dispatchPriority"] = 0xC040
        right["dispatchPriority"] = 0xC041
        left["order"] = len(model["transitions"])
        right["order"] = len(model["transitions"]) + 1
        left["candidateDefinition"]["recoveryTransitionId"] = "draft:right"
        right["candidateDefinition"]["recoveryTransitionId"] = "draft:left"
        left["candidateDefinition"]["recoveryPolicy"] = 1
        right["candidateDefinition"]["recoveryPolicy"] = 1
        mapping = self.writer.apply_behavior_model_changes(self.workspace, {
            "transitions": {"create": [left, right]},
        })
        saved = self.model()
        left_saved = next(item for item in saved["transitions"] if item["stableId"] == mapping["draft:left"])
        right_saved = next(item for item in saved["transitions"] if item["stableId"] == mapping["draft:right"])
        definitions = {item["stableId"]: item for item in saved["overrideDefinitions"]}
        self.assertEqual(definitions[left_saved["definitionId"]]["recoveryTransitionId"], right_saved["stableId"])
        self.assertEqual(definitions[right_saved["definitionId"]]["recoveryTransitionId"], left_saved["stableId"])
        self.assertEqual(left_saved["operations"][0]["replacementDefinitionId"], right_saved["definitionId"])
        self.assertEqual(right_saved["operations"][0]["replacementDefinitionId"], left_saved["definitionId"])
        self.assertEqual(right_saved["operations"][0]["instanceKey"], right_saved["definitionId"])

    def test_hard_cap_and_invalid_payload_leave_all_files_unchanged(self):
        source = self.model()["stateProfiles"][0]
        creates = [profile_payload(source, draft_id=f"draft:overflow-{index}") for index in range(200)]
        before = self.bytes()
        with self.assertRaises(self.writer.v40.ModelError):
            self.writer.apply_behavior_model_changes(self.workspace, {
                "stateProfiles": {"create": creates},
            })
        self.assertEqual(self.bytes(), before)
        with self.assertRaises(self.writer.BehaviorModelWriteError):
            self.writer.apply_behavior_model_changes(self.workspace, {"profiles": []})
        self.assertEqual(self.bytes(), before)
        mixed = profile_payload(source, draft_id="draft:mixed")
        mixed["registryKey"] = "legacy:caller-owned"
        with self.assertRaises(self.writer.BehaviorModelWriteError):
            self.writer.apply_behavior_model_changes(self.workspace, {
                "stateProfiles": {"create": [mixed]},
            })
        self.assertEqual(self.bytes(), before)

    def test_failure_before_or_during_replace_rolls_back_every_file(self):
        source = self.model()["stateProfiles"][0]
        update = profile_payload(source, name="Atomic rename")
        update["values"]["movementRange"] = (update["values"]["movementRange"] + 1) & 0xFF
        payload = {"stateProfiles": {"update": [update]}}
        before = self.bytes()

        def fail_before(index, _path):
            if index == 0:
                raise RuntimeError("before replace")

        with self.assertRaisesRegex(RuntimeError, "before replace"):
            self.writer.apply_behavior_model_changes(
                self.workspace, payload, _before_replace=fail_before
            )
        self.assertEqual(self.bytes(), before)

        def fail_during(index, _path):
            if index == 1:
                raise RuntimeError("during replace")

        with self.assertRaisesRegex(RuntimeError, "during replace"):
            self.writer.apply_behavior_model_changes(
                self.workspace, payload, _before_replace=fail_during
            )
        self.assertEqual(self.bytes(), before)

        attempts = 0
        def replace_then_raise(source, destination):
            nonlocal attempts
            os.replace(source, destination)
            attempts += 1
            if attempts == 1:
                raise RuntimeError("after replace")

        with self.assertRaisesRegex(RuntimeError, "after replace"):
            self.writer.apply_behavior_model_changes(
                self.workspace, payload, _replace_func=replace_then_raise
            )
        self.assertEqual(self.bytes(), before)


if __name__ == "__main__":
    unittest.main()
