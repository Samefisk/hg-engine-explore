"""Focused host tests for overworld scenario and actor evidence contracts."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools.overworld import actor_probe
from tools.overworld.actor_probe import (
    build_evidence_provenance,
    build_execution_record,
    evaluate_behavior_negative_control,
    evaluate_scenario_evidence,
    evaluate_subject_negative_control,
    load_execution_record,
    require_scenario_provenance,
    resolve_movement_policy_state,
)
from tools.overworld.runs import (
    OVERWORLD_LINKED_OUTPUTS,
    OVERWORLD_PRODUCT_OUTPUTS,
    RUN_SCHEMA,
    digest_value,
    make_run_manifest,
    run_id_for,
)
from tools.overworld.runtime_cadence import (
    actor_identity_is_current,
    classify_frame_hitches,
    classify_player_motion,
    count_player_step_callback_mismatches,
    count_player_timing_mismatches,
    counts_as_active_motion_frame,
)
from tools.overworld.control import (
    _command_record,
    _expand_command,
    _exact_runtime_scenarios,
    _roadmap_actor_evaluation_rejection,
    _roadmap_contract_audit,
    _roadmap_runtime_evidence,
    _roadmap_runtime_fixture,
    _roadmap_static_results,
    _registry_validator_passes,
    _runtime_runner_key,
    _run_command,
    _scenario_run,
    _verify_roadmap,
    build_parser,
)
from tools.overworld.trace import load_trace_schema
from tools.overworld.validation import (
    RuntimeProofSourceAudit,
    ValidationFailure,
    cross_validate,
    load_feature_manifest,
    load_scenarios,
    validate_scenario,
)


REPO = Path(__file__).resolve().parents[2]
TRACE_SCHEMA = load_trace_schema(
    REPO / "tools/overworld/schemas/semantic-trace-v1.json"
)


class RuntimeActorStateHelperTests(unittest.TestCase):
    def test_actor_state_decodes_public_snapshot_from_descriptor(self) -> None:
        source_path = REPO / "tools/overworld/devtools_engine.py"
        parsed = ast.parse(source_path.read_text(), filename=str(source_path))
        selected = [
            node for node in parsed.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in {"actor_memory_read", "actor_state"}
        ]
        self.assertEqual(
            [node.name for node in selected],
            ["actor_memory_read", "actor_state"],
        )

        actor_format = "<HH6H8I8h4H16B"
        actor_size = struct.calcsize(actor_format)
        descriptor = {
            "state": {
                "address": 16,
                "offsets": {"actors": 8},
                "actorStride": 96,
            },
            "publicLayouts": {
                "actorState": {"format": actor_format, "size": actor_size},
            },
            "enums": {
                "OverworldActorRole": {"OVERWORLD_ACTOR_ROLE_MOUNTED": 3},
                "BehaviorResolutionLane": {
                    "BEHAVIOR_RESOLUTION_LANE_OWNER": 0,
                },
                "OverworldActorMotionKind": {
                    "OVERWORLD_ACTOR_MOTION_HOP": 2,
                },
                "OverworldActorMotionPhase": {
                    "OVERWORLD_ACTOR_PHASE_MOVING": 2,
                },
            },
        }
        slot = 1
        address = 16 + 8 + slot * 96
        values = (
            1, actor_size,
            slot, 9, 4, 5, 6, 0,
            155, 0x1234, 0x56, 7, 8, 9, 10, 11,
            12, 13, 14, 15, 16, 17, 18, 19,
            3, 8, 21, 155,
            0, 22, 3, 0, 2, 2, 1, 2,
            0, 4, 5, 6, 1, 1, 7, 0,
        )
        memory = bytearray(address + actor_size + 4)
        memory[address:address + actor_size] = struct.pack(actor_format, *values)
        emu = SimpleNamespace(memory=SimpleNamespace(unsigned=memory))
        namespace = {
            "ACTOR_DESCRIPTOR": descriptor,
            "ACTOR_STATE_SIZE": actor_size,
            "actor_probe": actor_probe,
        }
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(source_path), "exec"), namespace)

        actor = namespace["actor_state"](emu, slot)

        self.assertEqual(actor["handle"]["slot"], slot)
        self.assertEqual(actor["handle"]["fieldEpoch"], 4)
        self.assertEqual(actor["species"], 155)
        self.assertEqual(actor["role"], "MOUNTED")
        self.assertEqual(actor["motionKind"], "HOP")
        self.assertEqual(actor["motionPhase"], "MOVING")
        self.assertEqual(actor["logical"], {"x": 12, "y": 13})
        self.assertEqual(actor["target"], {"x": 18, "y": 19})
        self.assertTrue(actor["active"])
        self.assertTrue(actor["presentationAttached"])
        self.assertEqual(actor["presentationState"], 7)


class RuntimeProofSourceAuditTests(unittest.TestCase):
    HEADER = """
SCENARIOS = {"case": scenario_case}
"""

    def audit(self, body: str, *, public: bool = True) -> list[str]:
        return RuntimeProofSourceAudit(self.HEADER + body).audit(
            "case",
            public_actor_evidence=public,
        )

    def test_public_actor_snapshot_measurement_passes(self) -> None:
        issues = self.audit("""
def scenario_case():
    actor = actor_state(emu, 0)
    return {
        "passed": actor["active"],
        "proofEvidence": {
            "live-actor-identity": [proof_measurement(
                "actor-active", actor["active"], True)]
        },
    }
""")
        self.assertEqual(issues, [])

    def test_private_mount_offset_mutation_fails(self) -> None:
        issues = self.audit("""
def scenario_case():
    phase = unsigned(emu, MOUNT + 0x64, 1)
    return {"passed": phase == 2}
""")
        self.assertTrue(any(
            issue.startswith("private-state-offset:") for issue in issues
        ))

    def test_transitive_private_policy_read_mutation_fails(self) -> None:
        issues = self.audit("""
def read_helper():
    return movement_policy_state(emu, 7)["pending"]

def scenario_case():
    return {"passed": read_helper() == 0}
""")
        self.assertTrue(any(
            issue.startswith("private-state-offset:") for issue in issues
        ))

    def test_module_private_read_consumed_by_scenario_fails(self) -> None:
        issues = self.audit("""
PRIVATE_PENDING = movement_policy_state(emu, 7)["pending"]

def scenario_case():
    return {"passed": PRIVATE_PENDING == 0}
""")
        self.assertTrue(any(
            issue.startswith("private-state-offset:") for issue in issues
        ))

    def test_sibling_nested_private_reader_fails(self) -> None:
        issues = self.audit("""
def scenario_case():
    def private_reader():
        return mount_state(emu)["pending"]

    def wrapper():
        return private_reader()

    return {"passed": wrapper() == 0}
""")
        self.assertTrue(any(
            issue.startswith("private-state-offset:") for issue in issues
        ))

    def test_fault_hook_cannot_export_private_state_through_global(self) -> None:
        issues = self.audit("""
FAULT_RESULT = None

def fault_inject_capture_state():
    global FAULT_RESULT
    FAULT_RESULT = mount_state(emu)

def scenario_case():
    fault_inject_capture_state()
    return {"passed": FAULT_RESULT["pending"] == 0}
""")
        self.assertTrue(any(
            issue.startswith("fault-hook-result:") for issue in issues
        ))

    def test_direct_private_write_mutations_fail(self) -> None:
        helper_issues = self.audit("""
def scenario_case():
    write_u8(emu, private_address, 1)
    return {"passed": True}
""")
        memory_issues = self.audit("""
def scenario_case():
    emu.memory.unsigned[private_address] = 1
    return {"passed": True}
""")
        self.assertTrue(any(
            issue.startswith("direct-private-state-write:")
            for issue in helper_issues
        ))
        self.assertTrue(any(
            issue.startswith("direct-private-state-write:")
            for issue in memory_issues
        ))

    def test_dynamic_memory_alias_read_and_write_mutations_fail(self) -> None:
        read_issues = self.audit("""
def scenario_case():
    port = getattr(emu.memory, "unsigned")
    return {"passed": port[private_address] == 0}
""")
        write_issues = self.audit("""
def scenario_case():
    port = getattr(emu.memory, "signed")
    port[private_address] = 0
    return {"passed": True}
""")
        self.assertTrue(any(
            issue.startswith("private-state-offset:") for issue in read_issues
        ))
        self.assertTrue(any(
            issue.startswith("direct-private-state-write:")
            for issue in write_issues
        ))

    def test_dynamic_lookup_and_execution_variants_fail(self) -> None:
        cases = (
            '''name = "unsigned"
port = getattr(emu.memory, name)
value = port[private_address]''',
            '''name = "unsigned"
port = emu.memory.__getattribute__(name)
value = port[private_address]''',
            '''value = eval("mount_state(emu)")''',
            '''exec("value = mount_state(emu)")
value = True''',
        )
        for setup in cases:
            with self.subTest(setup=setup):
                issues = self.audit(f"""
def scenario_case():
    {setup.replace(chr(10), chr(10) + '    ')}
    return {{"passed": bool(value)}}
""")
                self.assertTrue(any(
                    issue.startswith("forbidden-proof-language:")
                    for issue in issues
                ))

    def test_product_source_subprocess_mutations_fail(self) -> None:
        for expression in (
            'subprocess.run(["rg", "private", "src/actor.c"])',
            'subprocess.check_output(["sed", "-n", "1p", "src/actor.c"])',
        ):
            with self.subTest(expression=expression):
                issues = self.audit(f"""
def scenario_case():
    {expression}
    return {{"passed": True}}
""")
                self.assertTrue(any(
                    issue.startswith("product-c-source-string:")
                    for issue in issues
                ))

    def test_process_launch_with_indirect_source_path_fails(self) -> None:
        issues = self.audit('''
def scenario_case():
    product_path = REPO / "src" / ("actor" + ".c")
    subprocess.run(["rg", "private", str(product_path)])
    return {"passed": True}
''')
        self.assertTrue(any(
            issue.startswith("process-launch:") for issue in issues
        ))

    def test_fault_hook_mutable_side_channel_mutations_fail(self) -> None:
        cases = (
            """
STATE = {}
def fault_inject_case():
    STATE["value"] = mount_state(emu)
def scenario_case():
    fault_inject_case()
    return {"passed": True}
""",
            """
STATE = object()
def fault_inject_case():
    STATE.value = mount_state(emu)
def scenario_case():
    fault_inject_case()
    return {"passed": True}
""",
            """
def fault_inject_case(output):
    output["value"] = mount_state(emu)
def scenario_case():
    output = {}
    fault_inject_case(output)
    return {"passed": True}
""",
        )
        for source in cases:
            with self.subTest(source=source):
                self.assertTrue(any(
                    issue.startswith("fault-hook-result:")
                    for issue in self.audit(source)
                ))

    def test_fault_hook_nested_and_parameter_alias_sinks_fail(self) -> None:
        cases = (
            '''
STATE = {"nested": {}}
def fault_inject_case():
    alias = STATE["nested"]
    alias["value"] = mount_state(emu)
def scenario_case():
    fault_inject_case()
    return {"passed": True}
''',
            '''
def fault_inject_case(output):
    alias = output
    alias["value"] = mount_state(emu)
def scenario_case():
    output = {}
    fault_inject_case(output)
    return {"passed": True}
''',
        )
        for source in cases:
            with self.subTest(source=source):
                self.assertTrue(any(
                    issue.startswith("fault-hook-result:")
                    for issue in self.audit(source)
                ))

    def test_trusted_public_transport_shadow_mutations_fail(self) -> None:
        top_level = self.audit("""
def actor_state(emu, slot):
    return mount_state(emu)
def scenario_case():
    return {"passed": actor_state(emu, 7)["pending"] == 0}
""")
        nested = self.audit("""
def scenario_case():
    def actor_memory_read(emu, address, size):
        return mount_state(emu)
    return {"passed": bool(actor_memory_read(emu, 0, 1))}
""")
        self.assertTrue(any(
            issue.startswith("public-transport-shadow:")
            for issue in top_level
        ))
        self.assertTrue(any(
            issue.startswith("public-transport-shadow:")
            for issue in nested
        ))

    def test_raw_actor_memory_ports_cannot_reach_registered_proof(self) -> None:
        for expression in (
            "actor_memory_read(emu, 0x023BA1D4, 1)",
            "actor_memory_write(emu, 0x023BA1D4, bytes([1]))",
        ):
            with self.subTest(expression=expression):
                issues = self.audit(f"""
def scenario_case():
    {expression}
    return {{"passed": True}}
""")
                self.assertTrue(any(
                    issue.startswith("raw-actor-memory-port:")
                    for issue in issues
                ))

    def test_product_c_source_string_assertion_mutation_fails(self) -> None:
        issues = self.audit("""
def scenario_case():
    product = (REPO / "src/overworld_actor.c").read_text()
    return {"passed": "privateField" not in product}
""")
        self.assertTrue(any(
            issue.startswith("product-c-source-string:") for issue in issues
        ))

    def test_transitive_product_c_source_assertion_mutation_fails(self) -> None:
        issues = self.audit("""
def read_product(path):
    return path.read_text()

def scenario_case():
    product = read_product(REPO / "src/overworld_actor.c")
    return {"passed": "privateField" not in product}
""")
        self.assertTrue(any(
            issue.startswith("product-c-source-string:") for issue in issues
        ))

    def test_fault_hook_needs_public_actor_evidence(self) -> None:
        source = """
def fault_inject_blocked_start():
    write_u8(emu, MOUNT + 0x64, 1)

def scenario_case():
    fault_inject_blocked_start()
    actor = actor_state(emu, 7)
    return {"passed": actor["active"]}
"""
        self.assertEqual(self.audit(source), [])
        self.assertTrue(any(
            issue.startswith("fault-hook-public-proof:")
            for issue in self.audit(source, public=False)
        ))

    def test_fault_hook_result_cannot_feed_pass_logic(self) -> None:
        issues = self.audit("""
def fault_inject_blocked_start():
    write_u8(emu, MOUNT + 0x64, 1)
    return mount_state(emu)["phase"]

def scenario_case():
    injected_phase = fault_inject_blocked_start()
    actor = actor_state(emu, 7)
    return {"passed": actor["active"] and injected_phase == 2}
""")
        self.assertTrue(any(
            issue.startswith("fault-hook-result:") for issue in issues
        ))

    def test_comments_and_strings_cannot_supply_private_dependency(self) -> None:
        issues = self.audit("""
def scenario_case():
    note = "MOUNT + 0x64 and write_u8 are documentation only"
    return {"passed": bool(note)}
""")
        self.assertEqual(issues, [])


def retained_scenario_contract(path: Path) -> dict:
    """Historical trace fixture only. Its retired command is never executed."""
    history = json.loads((REPO / "tools/overworld/runtime_proof_migration.json").read_text())
    scenario = copy.deepcopy(history["historicalScenarios"][path.stem])
    adapter = scenario.get("adapter") or {}
    if adapter.get("commands"):
        old = adapter["commands"][0]
        name = old[old.index("--scenario") + 1]
        adapter["commands"] = [["{python}", "scripts/owctl", "scenario", "run",
                                "legacy." + name.replace("_", "-")]]
    return scenario


def scenario_document() -> dict:
    return {
        "verification": {
            "kind": "controlled-case",
            "expectationSource": "documentation/overworld-system/verification.md",
            "actor": "Synthetic host actor fixture, not live gameplay",
            "trigger": "Evaluate an exact public Walk trace",
            "observable": "One completion with exact frame timing and control return",
            "setupAudit": "complete", "setupMutations": [],
            "limits": ["Host evaluator proof only; no live collector claim."],
        },
        "schemaVersion": 1,
        "id": "actor.host-contract",
        "title": "Actor host contract",
        "status": "active",
        "capabilities": ["actor.system"],
        "proofLevel": "S3",
        "costTier": 1,
        "fixture": {"rom": "rom.nds", "save": None, "seed": 7},
        "events": [
            {"at": 0, "kind": "input", "value": "Move right once"},
        ],
        "stop": {"frameBudget": 60, "condition": "Control returns"},
        "expect": {
            "requiredEvents": ["MOTION_STARTED", "MOTION_FINISHED"],
            "forbiddenEvents": ["MOTION_CANCELED"],
            "invariants": [
                "Each accepted motion has exactly one terminal result",
                "Control returns after the selected motion finishes or cancels",
            ],
            "orderedEvents": [
                {
                    "id": "start",
                    "event": "MOTION_STARTED",
                    "reason": "OK",
                    "valueA": {"equals": 1},
                    "valueB": {"minimum": 8, "maximum": 8},
                },
                {
                    "id": "commit",
                    "event": "LOGICAL_COMMIT",
                    "reason": "OK",
                    "valueA": {"equals": 41},
                },
                {
                    "id": "finish",
                    "event": "MOTION_FINISHED",
                    "reason": "OK",
                    "valueB": {"equals": 1},
                },
            ],
            "eventCounts": [
                {
                    "event": "LOGICAL_COMMIT",
                    "reason": "OK",
                    "valueB": {"equals": 1},
                    "minimum": 1,
                    "maximum": 1,
                }
            ],
            "frameTiming": [
                {"from": "start", "to": "finish", "minimum": 8, "maximum": 8}
            ],
        },
        "capture": "always",
        "adapter": {
            "kind": "actor-observation",
            "commands": [["{python}", "scripts/example.py"]],
            "result": "json-passed",
            "evidence": "build/overworld-evidence/actor.host-contract.json",
            "claims": ["natural-input"],
            "checks": [
                "trace-window-complete",
                "terminal-result",
                "control-returned",
            ],
        },
    }


def trace_event(
    sequence: int,
    frame: int,
    event: str,
    *,
    reason: str = "OK",
    value_a: int = 0,
    value_b: int = 0,
) -> dict:
    event_ids = {name: int(value) for value, name in TRACE_SCHEMA["events"].items()}
    reason_ids = {name: int(value) for value, name in TRACE_SCHEMA["reasons"].items()}
    actor = {
        "slot": 1,
        "generation": 2,
        "fieldEpoch": 3,
        "mapGeneration": 4,
        "encounterGeneration": 5,
    }
    return {
        "sequence": sequence,
        "frame": frame,
        "actorHandle": (actor["generation"] << 16) | actor["slot"],
        "actor": actor,
        "eventId": event_ids[event],
        "event": event,
        "reasonId": reason_ids[reason],
        "reason": reason,
        "valueA": value_a,
        "valueB": value_b,
    }


def turn_skid_semantic_scenario() -> dict:
    path = REPO / "tests/overworld/scenarios/walk.turn-skid.control-release.json"
    scenario = retained_scenario_contract(path)
    scenario["status"] = "active"
    scenario["proofLevel"] = "S3"
    scenario.pop("subjects", None)
    scenario["expect"] = {
        "requiredEvents": [
            "MOTION_STARTED",
            "MOUNT_PRESENTATION_POSITION",
            "MOUNT_PRESENTATION_STATE",
            "LOGICAL_COMMIT",
            "MOTION_FINISHED",
            "CONTROL_RETURNED",
        ],
        "forbiddenEvents": ["MOTION_CANCELED"],
        "invariants": [
            "Each accepted motion has exactly one terminal result",
            "No logical commit occurs after motion cancellation",
            "Control returns after the selected motion finishes or cancels",
            "Mounted player and follower coordinates match for every published motion sample",
            "Mounted player and follower facing remains locked for every published skid sample",
        ],
        "orderedEvents": [
            {
                "id": "start",
                "event": "MOTION_STARTED",
                "reason": "OK",
                "valueA": {"equals": 4},
            },
            {
                "id": "position",
                "event": "MOUNT_PRESENTATION_POSITION",
                "reason": "OK",
            },
            {
                "id": "state",
                "event": "MOUNT_PRESENTATION_STATE",
                "reason": "OK",
            },
            {
                "id": "commit",
                "event": "LOGICAL_COMMIT",
                "reason": "OK",
                "valueB": {"equals": 4},
            },
            {
                "id": "finish",
                "event": "MOTION_FINISHED",
                "reason": "OK",
                "valueB": {"equals": 4},
            },
            {"id": "control", "event": "CONTROL_RETURNED", "reason": "OK"},
        ],
        "eventCounts": [
            {"event": "MOTION_STARTED", "minimum": 1, "maximum": 1},
            {"event": "MOUNT_PRESENTATION_POSITION", "minimum": 4, "maximum": 4},
            {"event": "MOUNT_PRESENTATION_STATE", "minimum": 4, "maximum": 4},
            {"event": "LOGICAL_COMMIT", "minimum": 1, "maximum": 1},
            {"event": "MOTION_FINISHED", "minimum": 1, "maximum": 1},
            {"event": "CONTROL_RETURNED", "minimum": 1, "maximum": 1},
        ],
        "frameTiming": [
            {"from": "start", "to": "finish", "minimum": 4, "maximum": 4}
        ],
    }
    scenario["adapter"] = {
        "kind": "actor-observation",
        "commands": [["{python}", "scripts/example.py"]],
        "result": "json-passed",
        "evidence": "build/overworld-evidence/walk.turn-skid.control-release.json",
        "claims": ["natural-input", "rendered-motion", "control-release"],
        "motionWindowCount": 2,
        "checks": [
            "trace-window-complete",
            "terminal-result",
            "no-commit-after-cancel",
            "control-returned",
            "mounted-presentation-coordinates-equal",
            "mounted-presentation-facing-locked",
        ],
    }
    return validate_scenario(scenario, path)


def actor_evidence() -> dict:
    events = [
        trace_event(1, 100, "MOTION_STARTED", value_a=1, value_b=8),
        trace_event(2, 107, "LOGICAL_COMMIT", value_a=41, value_b=1),
        trace_event(3, 108, "MOTION_FINISHED", value_a=41, value_b=1),
        trace_event(4, 108, "CONTROL_RETURNED", value_a=0, value_b=41),
    ]
    return {
        "observation": {
            "fieldEpoch": 3,
            "actors": [],
            "trace": {
                "schemaVersion": 1,
                "header": {
                    "capacity": 32,
                    "count": len(events),
                    "oldestSequence": 1,
                    "nextSequence": len(events) + 1,
                    "overwrittenCount": 0,
                    "fieldEpoch": 3,
                    "filterEventMask": 0,
                    "filterActor": {"slot": 0xFFFF, "generation": 0},
                    "filterFramesRemaining": 0,
                    "writeIndex": len(events),
                    "armed": 0,
                },
                "events": events,
            },
        }
    }


def skid_motion_events(
    sequence: int,
    frame: int,
    *,
    expected_facing: int = 3,
) -> tuple[list[dict], int]:
    events = [
        trace_event(sequence, frame, "MOTION_STARTED", value_a=4, value_b=4)
    ]
    sequence += 1
    packed_faces = sum(expected_facing << shift for shift in (0, 8, 16, 24))
    for elapsed in range(1, 5):
        position = ((20 + elapsed) << 16) | 30
        sample_state = (
            (elapsed << 16)
            | (1 << 15)
            | (1 << 14)
            | (4 << 8)
            | (4 << 4)
            | expected_facing
        )
        events.extend(
            [
                trace_event(
                    sequence,
                    frame + elapsed,
                    "MOUNT_PRESENTATION_POSITION",
                    value_a=position,
                    value_b=position,
                ),
                trace_event(
                    sequence + 1,
                    frame + elapsed,
                    "MOUNT_PRESENTATION_STATE",
                    value_a=packed_faces,
                    value_b=sample_state,
                ),
            ]
        )
        sequence += 2
    events.extend(
        [
            trace_event(
                sequence, frame + 4, "LOGICAL_COMMIT", value_a=1, value_b=4
            ),
            trace_event(
                sequence + 1,
                frame + 4,
                "MOTION_FINISHED",
                value_a=1,
                value_b=4,
            ),
            trace_event(
                sequence + 2,
                frame + 4,
                "CONTROL_RETURNED",
                value_a=0,
                value_b=1,
            ),
        ]
    )
    return events, sequence + 3


class ScenarioContractTests(unittest.TestCase):
    def validate(self, document: dict) -> dict:
        return validate_scenario(document, Path(f"{document['id']}.json"))

    def test_runtime_registry_rejects_dynamic_expected_as_acceptance(self) -> None:
        manifest = load_feature_manifest(
            REPO / "tools/overworld/system_features.yaml"
        )
        scenarios = load_scenarios(REPO / "tests/overworld/scenarios")
        registry_path = REPO / "tools/overworld/runtime_proof_registry.json"
        registry = json.loads(registry_path.read_text())
        mutated = copy.deepcopy(registry)
        measurement = mutated["measurementContracts"][
            "legacy.mounted-frames"
        ]["natural-input"][0]
        measurement.pop("expected")
        original_loader = __import__(
            "tools.overworld.validation", fromlist=["load_json_document"]
        ).load_json_document

        def load_document(path: Path):
            return mutated if Path(path) == registry_path else original_loader(path)

        with mock.patch(
            "tools.overworld.validation.load_json_document",
            side_effect=load_document,
        ), self.assertRaisesRegex(
            ValidationFailure, "no independent acceptance rule"
        ):
            cross_validate(manifest, scenarios, REPO)

    def test_mounted_frame_relation_rejects_self_consistent_bad_matrix(self) -> None:
        durations = [*range(1, 33), *range(1, 33), 5]
        specification = {
            "validator": "mounted-frame-matrix-v1",
            "aspect": "counts",
        }
        actual = {
            "durations": durations,
            "elapsedCounts": durations,
            "diagonalAttempt": {
                "before": [10, 10], "after": [10, 10],
                "mode": "IDLE", "pending": 0,
            },
        }
        self.assertTrue(_registry_validator_passes(specification, actual, actual))
        mutated = copy.deepcopy(actual)
        mutated["diagonalAttempt"]["after"] = [11, 10]
        self.assertFalse(
            _registry_validator_passes(specification, mutated, mutated)
        )

    def test_teleport_relation_rejects_self_consistent_bad_duration(self) -> None:
        actual = []
        for mode, variants in (
            ("fixed", ("visible_right", "visible_left", "visible_up",
                       "visible_down", "flicker")),
            ("per_tile", ("visible_left", "visible_right", "visible_up",
                          "visible_down", "flicker")),
        ):
            for variant in variants:
                distance = 2 if "right" in variant or variant == "flicker" else 3
                actual.append({
                    "name": f"{mode}_{variant}",
                    "start": [10, 10],
                    "target": [10 + distance, 10],
                    "final": [10 + distance, 10],
                    "frames": 3 * distance if mode == "per_tile" else 7,
                    "perTile": mode == "per_tile",
                    "travelTime": 3 if mode == "per_tile" else 7,
                })
        specification = {
            "validator": "teleport-timing-matrix-v1",
            "aspect": "endpoints",
        }
        self.assertTrue(_registry_validator_passes(specification, actual, actual))
        mutated = copy.deepcopy(actual)
        mutated[0]["frames"] = 8
        self.assertFalse(
            _registry_validator_passes(specification, mutated, mutated)
        )

    def test_packaged_relation_rejects_runner_supplied_false_oracle(self) -> None:
        specification = {
            "validator": "packaged-resolver-parity-v1",
            "aspect": "fingerprint",
        }
        with mock.patch(
            "tools.overworld.control._packaged_resolver_oracle",
            return_value={"fingerprint": [1, 2, 3]},
        ):
            self.assertTrue(
                _registry_validator_passes(specification, [1, 2, 3], [9, 9, 9])
            )
            self.assertFalse(
                _registry_validator_passes(specification, [9, 9, 9], [9, 9, 9])
            )

    def test_valid_order_payload_count_and_frame_timing_pass(self) -> None:
        scenario = self.validate(scenario_document())
        result = evaluate_scenario_evidence(scenario, actor_evidence(), TRACE_SCHEMA)

        self.assertTrue(result["passed"])
        self.assertEqual(result["orderedEventAssertions"][1]["matchedValueA"], 41)
        self.assertEqual(result["eventCountAssertions"][0]["actual"], 1)
        self.assertEqual(result["frameTimingAssertions"][0]["actualFrames"], 8)

    def test_phase7_path_order_rejects_missing_or_late_advances(self) -> None:
        scenario = scenario_document()
        scenario["expect"]["requiredEvents"].insert(1, "PATH_ADVANCED")
        scenario["expect"]["orderedEvents"].insert(1, {
            "id": "path",
            "event": "PATH_ADVANCED",
            "reason": "OK",
        })
        scenario["expect"]["invariants"].append(
            "Every path advance is ordered before the terminal logical commit"
        )
        scenario["adapter"]["checks"].append(
            "path-advances-before-commit"
        )
        scenario = self.validate(scenario)
        evidence = actor_evidence()
        path = trace_event(
            2, 104, "PATH_ADVANCED", value_a=(1 << 16) | 1, value_b=1
        )
        for event in evidence["observation"]["trace"]["events"]:
            if event["sequence"] >= 2:
                event["sequence"] += 1
        evidence["observation"]["trace"]["events"].insert(1, path)
        header = evidence["observation"]["trace"]["header"]
        header["count"] = 5
        header["nextSequence"] = 6
        header["writeIndex"] = 5

        self.assertTrue(
            evaluate_scenario_evidence(scenario, evidence, TRACE_SCHEMA)[
                "passed"
            ]
        )
        missing = copy.deepcopy(evidence)
        missing["observation"]["trace"]["events"] = [
            event for event in missing["observation"]["trace"]["events"]
            if event["event"] != "PATH_ADVANCED"
        ]
        self.assertFalse(
            evaluate_scenario_evidence(scenario, missing, TRACE_SCHEMA)[
                "passed"
            ]
        )
        late = copy.deepcopy(evidence)
        late_path = next(
            event for event in late["observation"]["trace"]["events"]
            if event["event"] == "PATH_ADVANCED"
        )
        late_path["sequence"] = 6
        self.assertFalse(
            evaluate_scenario_evidence(scenario, late, TRACE_SCHEMA)[
                "passed"
            ]
        )

    def test_phase7_reservation_rejects_overlapping_target_acceptance(self) -> None:
        scenario = scenario_document()
        scenario["expect"]["requiredEvents"].insert(
            0, "CANDIDATE_REJECTED"
        )
        scenario["expect"]["orderedEvents"].insert(0, {
            "id": "reserved",
            "event": "CANDIDATE_REJECTED",
            "reason": "REJECTED_RESERVED",
        })
        scenario["expect"]["invariants"].append(
            "A target reservation rejects another actor until the owner releases it"
        )
        scenario["adapter"]["checks"].append(
            "target-reservation-serialized"
        )
        scenario = self.validate(scenario)
        evidence = actor_evidence()
        original = evidence["observation"]["trace"]["events"]
        reserved = trace_event(
            1, 99, "CANDIDATE_REJECTED", reason="REJECTED_RESERVED"
        )
        for event in original:
            event["sequence"] += 1
        evidence["observation"]["trace"]["events"] = [reserved, *original]
        header = evidence["observation"]["trace"]["header"]
        header["count"] = 5
        header["nextSequence"] = 6
        header["writeIndex"] = 5
        self.assertTrue(
            evaluate_scenario_evidence(scenario, evidence, TRACE_SCHEMA)[
                "passed"
            ]
        )

        overlap = copy.deepcopy(evidence)
        owner = trace_event(1, 98, "PLAN_ACCEPTED", value_a=0x0029002A)
        owner["actorHandle"] = 0x00030002
        owner["actor"].update({"slot": 2, "generation": 3})
        contender = trace_event(2, 99, "PLAN_ACCEPTED", value_a=0x0029002A)
        for event in overlap["observation"]["trace"]["events"]:
            event["sequence"] += 2
        overlap["observation"]["trace"]["events"] = [
            owner, contender, *overlap["observation"]["trace"]["events"]
        ]
        self.assertFalse(
            evaluate_scenario_evidence(scenario, overlap, TRACE_SCHEMA)[
                "passed"
            ]
        )

    def test_ledyba_runtime_contract_keeps_full_live_identity(self) -> None:
        from tools.overworld.chain_retry_proof import contract as retry_contract

        registry = json.loads(
            (REPO / "tools/overworld/runtime_proof_registry.json").read_text()
        )
        contract = registry["measurementContracts"][
            "legacy.ledyba-chain-pause"
        ]["live-actor-identity"]

        self.assertEqual(
            contract,
            retry_contract()["live-actor-identity"],
        )

    def test_ledyba_runtime_contract_keeps_exact_chain_retry(self) -> None:
        from tools.overworld.chain_retry_proof import contract as retry_contract

        registry = json.loads(
            (REPO / "tools/overworld/runtime_proof_registry.json").read_text()
        )
        contract = registry["measurementContracts"][
            "legacy.ledyba-chain-pause"
        ]["logical-commit"]

        self.assertEqual(
            contract,
            retry_contract()["logical-commit"],
        )

    def test_cyndaquil_soak_keeps_a_live_mounted_subject_contract(self) -> None:
        path = REPO / "tests/overworld/scenarios/mount.detach-restores-control.json"
        scenario = validate_scenario(retained_scenario_contract(path), path)
        registry = json.loads(
            (REPO / "tools/overworld/runtime_proof_registry.json").read_text()
        )
        contract = registry["measurementContracts"][
            "legacy.cyndaquil-control-stress"
        ]

        self.assertEqual(scenario["adapter"]["kind"], "actor-observation")
        self.assertIn("live-actor-identity", scenario["adapter"]["claims"])
        self.assertEqual(
            scenario["subjects"],
            [{
                "id": "cyndaquil",
                "species": 155,
                "role": "MOUNTED",
                "acquisition": "mount",
                "minimum": 1,
                "maximum": 1,
                "motionActor": True,
                "requirePresentation": True,
            }],
        )
        self.assertEqual(
            {item["name"] for item in contract["live-actor-identity"]},
            {
                "cyndaquil-species",
                "mounted-object-pointer",
                "actor-handle",
                "mounted-object-identity-flags",
                "encounter-generation-match",
            },
        )
        self.assertEqual(
            contract["natural-input"],
            [
                {
                    "name": "held-input-commit-count",
                    "operator": "gte",
                    "type": "integer",
                    "validator": "meaningful-observation",
                    "minimum": 2000,
                },
                {
                    "name": "held-input-turn-count",
                    "operator": "gte",
                    "type": "integer",
                    "validator": "meaningful-observation",
                    "minimum": 250,
                },
                {
                    "name": "held-input-route-frame-count",
                    "operator": "gte",
                    "type": "integer",
                    "validator": "meaningful-observation",
                    "minimum": 5000,
                },
            ],
        )

    def test_hardened_actor_routes_measure_the_named_work(self) -> None:
        registry = json.loads(
            (REPO / "tools/overworld/runtime_proof_registry.json").read_text()
        )["measurementContracts"]

        acceleration_contract = registry[
            "legacy.acceleration-parity"
        ]
        self.assertEqual(
            acceleration_contract["live-actor-identity"][0]["expected"],
            [7, 7],
        )
        self.assertEqual(
            acceleration_contract["engine-boundary"][0]["expected"],
            14,
        )

        smoothness_path = (
            REPO / "tests/overworld/scenarios/mount.movement.frame-pacing.json"
        )
        smoothness = validate_scenario(
            retained_scenario_contract(smoothness_path), smoothness_path
        )
        self.assertEqual(smoothness["adapter"]["motionWindowCount"], 7)
        self.assertTrue(all(
            item["minimum"] == 7 and item["maximum"] == 7
            for item in smoothness["expect"]["eventCounts"]
        ))

        streaming_path = (
            REPO / "tests/overworld/scenarios/"
            "mount.streaming.cardinal-and-diagonal.json"
        )
        streaming = validate_scenario(
            retained_scenario_contract(streaming_path), streaming_path
        )
        self.assertEqual(streaming["proofLevel"], "S5")
        self.assertEqual(streaming["adapter"]["minimumFrames"], 5001)
        self.assertEqual(len(streaming["adapter"]["commands"]), 1)
        streaming_contract = registry[
            "legacy.mounted-diagonal-streaming"
        ]
        self.assertEqual(
            streaming_contract["natural-input"][2]["minimum"],
            5001,
        )
        self.assertEqual(
            streaming_contract["live-actor-identity"][1]["expected"],
            0,
        )

        transition_contract = registry[
            "legacy.mounted-transition"
        ]
        self.assertEqual(
            transition_contract["natural-input"][1]["minimum"],
            5000,
        )
        self.assertEqual(
            transition_contract["live-actor-identity"][1]["expected"],
            0,
        )

        population_contract = registry[
            "legacy.population-after-fast-travel"
        ]
        self.assertEqual(
            population_contract["live-actor-identity"][1]["expected"],
            0,
        )

    def test_s5_rejects_multiple_runtime_commands(self) -> None:
        path = (
            REPO / "tests/overworld/scenarios/"
            "mount.streaming.cardinal-and-diagonal.json"
        )
        scenario = retained_scenario_contract(path)
        scenario["adapter"]["commands"].append(
            list(scenario["adapter"]["commands"][0])
        )

        with self.assertRaisesRegex(
            ValidationFailure,
            "exactly one continuous runtime command",
        ):
            validate_scenario(scenario, path)

    def test_streaming_soak_does_not_count_idle_route_frames(self) -> None:
        self.assertFalse(counts_as_active_motion_frame(0, 4))
        self.assertFalse(counts_as_active_motion_frame(1, 4))
        self.assertFalse(counts_as_active_motion_frame(2, 4))
        self.assertFalse(counts_as_active_motion_frame(3, 4))
        self.assertTrue(counts_as_active_motion_frame(4, 4))

    def test_cadence_hitches_include_early_and_single_samples(self) -> None:
        one_hitch = classify_frame_hitches(
            [2_000_000, 100_000, 100_000, 100_000, 100_000],
            2000,
            250000,
        )
        two_hitches = classify_frame_hitches(
            [2_000_000, 2_000_000, 100_000, 100_000, 100_000],
            2000,
            250000,
        )

        self.assertEqual(one_hitch["sampleCount"], 5)
        self.assertEqual(one_hitch["hitchFrames"], [0])
        self.assertEqual(one_hitch["hitchCount"], 1)
        self.assertEqual(two_hitches["hitchFrames"], [0, 1])
        self.assertEqual(two_hitches["hitchCount"], 2)

    def test_player_cadence_rejects_idle_padding_and_visible_stalls(self) -> None:
        def samples(positions, accepted_from=0):
            return [
                {
                    "render": position,
                    "accepted": index >= accepted_from,
                }
                for index, position in enumerate(positions)
            ]

        options = {
            "maximum_acceptance_frames": 2,
            "maximum_start_frames": 2,
            "maximum_settle_frames": 4,
        }
        smooth = classify_player_motion(
            samples([[4, 0], [8, 0], [12, 0], [16, 0]]),
            [0, 0],
            [16, 0],
            **options,
        )
        idle = classify_player_motion(
            samples([[0, 0]] * 5001, accepted_from=5002),
            [0, 0],
            [16, 0],
            **options,
        )
        duplicate = classify_player_motion(
            samples([[4, 0], [4, 0], [8, 0], [12, 0], [16, 0]]),
            [0, 0],
            [16, 0],
            **options,
        )
        delayed = classify_player_motion(
            samples(
                [[0, 0], [0, 0], [4, 0], [8, 0], [12, 0], [16, 0]],
                accepted_from=2,
            ),
            [0, 0],
            [16, 0],
            **options,
        )
        delayed_render = classify_player_motion(
            samples([[0, 0], [0, 0], [0, 0], [4, 0], [16, 0]]),
            [0, 0],
            [16, 0],
            **options,
        )
        regressed = classify_player_motion(
            samples([[4, 0], [8, 0], [6, 0], [12, 0], [16, 0]]),
            [0, 0],
            [16, 0],
            **options,
        )

        self.assertEqual(smooth["activeFrames"], 4)
        self.assertEqual(smooth["acceptanceStall"], 0)
        self.assertEqual(smooth["interiorStalls"], 0)
        self.assertEqual(smooth["renderRegressions"], 0)
        self.assertTrue(smooth["reachedTarget"])
        self.assertEqual(idle["activeFrames"], 0)
        self.assertEqual(idle["acceptanceStall"], 1)
        self.assertEqual(duplicate["interiorStalls"], 1)
        self.assertEqual(delayed["acceptanceStall"], 1)
        self.assertEqual(delayed_render["startStall"], 1)
        self.assertEqual(regressed["renderRegressions"], 1)

    def test_player_cadence_rejects_acceptance_timing_variance(self) -> None:
        self.assertEqual(
            count_player_timing_mismatches(
                [[1, 0, 4, 0], [1, 0, 4, 0]]
            ),
            0,
        )
        self.assertEqual(
            count_player_timing_mismatches(
                [[1, 0, 4, 0], [2, 0, 4, 0]]
            ),
            1,
        )

    def test_player_cadence_rejects_step_callback_mutations(self) -> None:
        self.assertEqual(
            count_player_step_callback_mismatches([1, 1], 2, 2),
            0,
        )
        self.assertGreater(
            count_player_step_callback_mismatches([1, 0], 2, 2),
            0,
        )
        self.assertGreater(
            count_player_step_callback_mismatches([1], 2, 1),
            0,
        )

    def test_cadence_actor_identity_rejects_source_mutations(self) -> None:
        handle = {
            "value": 0x1234,
            "slot": 3,
            "fieldEpoch": 8,
            "encounterGeneration": 19,
        }
        actor = {
            "active": True,
            "role": "WILD",
            "species": 19,
            "presentationAttached": True,
            "handle": handle,
            "subjectIdentity": 0x5678,
        }
        source = {
            "active": 1,
            "species": 19,
            "object": 0x02010000,
            "object_id": 0xE3,
            "map_id": 22,
            "encounter_generation": 19,
        }
        live = {
            "pointer": 0x02010000,
            "in_manager": True,
            "active": True,
            "object_id": 0xE3,
            "spawn_object_id": 0xE3,
            "object_map_id": 22,
            "spawn_map_id": 22,
            "current_map_id": 22,
            "encounter_generation": 19,
        }

        def valid(**changes: object) -> bool:
            values = {
                "role": "WILD",
                "species": 19,
                "slot": 3,
                "actor": actor,
                "object_pointer": 0x02010000,
                "initial_handle": handle,
                "initial_subject": 0x5678,
                "initial_object": 0x02010000,
                "source_record": source,
                "live_object": live,
                "acquisition_passed": True,
            }
            values.update(changes)
            return actor_identity_is_current(**values)

        self.assertTrue(valid())
        self.assertFalse(valid(acquisition_passed=False))
        self.assertFalse(valid(object_pointer=0x02020000))
        self.assertFalse(valid(slot=7))
        for key, value in (
            ("active", 0),
            ("species", 165),
            ("object", 0x02020000),
            ("map_id", 23),
            ("encounter_generation", 20),
        ):
            with self.subTest(source_field=key):
                mutated = dict(source)
                mutated[key] = value
                self.assertFalse(valid(source_record=mutated))
        for key, value in (
            ("active", False),
            ("pointer", 0x02020000),
            ("current_map_id", 23),
            ("encounter_generation", 20),
        ):
            with self.subTest(live_field=key):
                mutated = dict(live)
                mutated[key] = value
                self.assertFalse(valid(live_object=mutated))

        follower_handle = dict(handle, slot=7)
        follower_actor = dict(
            actor,
            role="FOLLOWER",
            species=155,
            handle=follower_handle,
        )
        follower_source = dict(source, species=155, object_id=7)
        follower_live = dict(live, object_id=7, spawn_object_id=7)
        self.assertTrue(valid(
            role="FOLLOWER",
            species=155,
            slot=7,
            actor=follower_actor,
            initial_handle=follower_handle,
            source_record=follower_source,
            live_object=follower_live,
        ))
        self.assertFalse(valid(
            role="FOLLOWER",
            species=155,
            slot=7,
            actor=follower_actor,
            initial_handle=follower_handle,
            source_record=follower_source,
            live_object=follower_live,
            acquisition_passed=False,
        ))

    def test_named_actor_subject_fails_when_the_actor_is_absent(self) -> None:
        scenario = scenario_document()
        scenario["subjects"] = [
            {
                "id": "ledyba",
                "species": 165,
                "role": "WILD",
                "acquisition": "spawn",
                "minimum": 1,
                "maximum": 1,
                "motionActor": True,
                "requirePresentation": True,
            }
        ]
        scenario["adapter"]["claims"].append("live-actor-identity")
        scenario = self.validate(scenario)
        evidence = actor_evidence()
        evidence["observation"]["actors"] = [
            {
                "active": True,
                "subjectIdentity": 123,
                "authorityGeneration": 2,
                "engineAnchorGeneration": 2,
                "presentationGeneration": 2,
                "presentationState": 7,
                "species": 19,
                "role": "WILD",
                "presentationAttached": True,
                "handle": {
                    "slot": 1,
                    "generation": 2,
                    "fieldEpoch": 3,
                    "mapGeneration": 4,
                    "encounterGeneration": 5,
                    "value": (2 << 16) | 1,
                },
            }
        ]

        result = evaluate_scenario_evidence(scenario, evidence, TRACE_SCHEMA)

        self.assertFalse(result["passed"])
        self.assertEqual(result["subjectAssertions"][0]["actual"], 0)
        self.assertFalse(result["subjectAssertions"][0]["motionActorMatched"])

    def test_named_actor_live_evidence_runs_an_absent_subject_negative_control(self) -> None:
        scenario = scenario_document()
        scenario["subjects"] = [
            {
                "id": "ledyba",
                "species": 165,
                "role": "WILD",
                "acquisition": "spawn",
                "minimum": 1,
                "maximum": 1,
                "motionActor": True,
                "requirePresentation": True,
            }
        ]
        scenario["adapter"]["claims"].append("live-actor-identity")
        scenario = self.validate(scenario)
        evidence = actor_evidence()
        evidence["observation"]["actors"] = [
            {
                "active": True,
                "subjectIdentity": 123,
                "authorityGeneration": 2,
                "engineAnchorGeneration": 2,
                "presentationGeneration": 2,
                "presentationState": 7,
                "species": 165,
                "role": "WILD",
                "presentationAttached": True,
                "handle": {
                    "slot": 1,
                    "generation": 2,
                    "fieldEpoch": 3,
                    "mapGeneration": 4,
                    "encounterGeneration": 5,
                    "value": (2 << 16) | 1,
                },
            }
        ]

        positive = evaluate_scenario_evidence(scenario, evidence, TRACE_SCHEMA)
        negative = evaluate_subject_negative_control(
            scenario, evidence, TRACE_SCHEMA
        )

        self.assertTrue(positive["passed"])
        self.assertTrue(negative["passed"])
        self.assertEqual(negative["failedSubjects"], ["ledyba"])

    def test_mounted_subject_rejects_zero_public_identity_generations(self) -> None:
        scenario = scenario_document()
        scenario["subjects"] = [{
            "id": "mount",
            "species": 155,
            "role": "MOUNTED",
            "acquisition": "mount",
            "minimum": 1,
            "maximum": 1,
            "motionActor": True,
            "requirePresentation": True,
        }]
        scenario["adapter"]["claims"].append("live-actor-identity")
        scenario = self.validate(scenario)
        base = actor_evidence()
        actor = {
            "active": True,
            "subjectIdentity": 123,
            "authorityGeneration": 2,
            "engineAnchorGeneration": 2,
            "presentationGeneration": 2,
            "presentationState": 7,
            "species": 155,
            "role": "MOUNTED",
            "presentationAttached": True,
            "handle": {
                "slot": 1,
                "generation": 2,
                "fieldEpoch": 3,
                "mapGeneration": 4,
                "encounterGeneration": 5,
                "value": (2 << 16) | 1,
            },
        }
        base["observation"]["actors"] = [actor]
        self.assertTrue(
            evaluate_scenario_evidence(scenario, base, TRACE_SCHEMA)["passed"]
        )

        for field in (
            "subjectIdentity",
            "authorityGeneration",
            "engineAnchorGeneration",
            "presentationGeneration",
            "presentationState",
        ):
            with self.subTest(field=field):
                mutated = copy.deepcopy(base)
                mutated["observation"]["actors"][0][field] = 0
                self.assertFalse(
                    evaluate_scenario_evidence(
                        scenario, mutated, TRACE_SCHEMA
                    )["passed"]
                )

        vanished_but_synced = copy.deepcopy(base)
        vanished_actor = vanished_but_synced["observation"]["actors"][0]
        vanished_actor["presentationState"] = 5
        vanished_actor["logical"] = {"x": 10, "y": 10}
        vanished_actor["render"] = {"x": 10, "y": 10}
        self.assertFalse(
            evaluate_scenario_evidence(
                scenario, vanished_but_synced, TRACE_SCHEMA
            )["passed"]
        )

    def test_actor_behavior_runs_a_missing_event_negative_control(self) -> None:
        scenario = self.validate(scenario_document())
        evidence = actor_evidence()

        negative = evaluate_behavior_negative_control(
            scenario, evidence, TRACE_SCHEMA
        )

        self.assertTrue(negative["passed"])
        self.assertTrue(negative["applied"])
        self.assertEqual(negative["event"], "MOTION_FINISHED")
        self.assertEqual(negative["removed"], 1)

    def test_structured_subject_requires_live_identity_claim(self) -> None:
        scenario = scenario_document()
        scenario["subjects"] = [
            {
                "id": "ledyba",
                "species": 165,
                "role": "WILD",
                "acquisition": "spawn",
                "minimum": 1,
                "maximum": 1,
                "motionActor": True,
                "requirePresentation": True,
            }
        ]

        with self.assertRaisesRegex(
            ValidationFailure, "structured subject needs live-actor-identity"
        ):
            self.validate(scenario)

    def test_structured_subject_requires_controller_owned_observation(self) -> None:
        scenario = scenario_document()
        scenario["subjects"] = [
            {
                "id": "ledyba",
                "species": 165,
                "role": "WILD",
                "acquisition": "spawn",
                "minimum": 1,
                "maximum": 1,
                "motionActor": True,
                "requirePresentation": True,
            }
        ]
        scenario["adapter"] = {
            "kind": "command-sequence",
            "commands": [["{python}", "scripts/example.py"]],
            "result": "json-passed",
            "claims": ["live-actor-identity"],
        }

        with self.assertRaisesRegex(
            ValidationFailure, "controller-owned actor observation"
        ):
            self.validate(scenario)

    def test_executable_actor_observation_accepts_safe_evidence_output(self) -> None:
        scenario = scenario_document()
        scenario["adapter"].update(
            {
                "commands": [["{python}", "scripts/example.py"]],
                "result": "json-passed",
                "evidence": "build/overworld-evidence/actor.host-contract.json",
                "claims": ["rendered-motion", "control-release"],
            }
        )

        validated = self.validate(scenario)

        self.assertEqual(
            validated["adapter"]["evidence"],
            "build/overworld-evidence/actor.host-contract.json",
        )

    def test_executable_actor_observation_requires_complete_runner_contract(self) -> None:
        scenario = scenario_document()
        scenario["adapter"].pop("result")
        scenario["adapter"].pop("evidence")

        with self.assertRaisesRegex(
            ValidationFailure,
            "needs commands, result, and evidence",
        ):
            self.validate(scenario)

    def test_s3_executable_proof_requires_named_runtime_claims(self) -> None:
        scenario = scenario_document()
        scenario["adapter"].pop("claims")
        scenario["adapter"].update(
            {
                "commands": [["{python}", "scripts/example.py"]],
                "result": "json-passed",
                "evidence": "build/overworld-evidence/actor.host-contract.json",
            }
        )

        with self.assertRaisesRegex(
            ValidationFailure,
            "adapter.claims: must be an array",
        ):
            self.validate(scenario)

    def test_s4_executable_proof_requires_visual_measurement_claim(self) -> None:
        scenario = scenario_document()
        scenario["proofLevel"] = "S4"
        scenario["adapter"].update(
            {
                "commands": [["{python}", "scripts/example.py"]],
                "result": "json-passed",
                "evidence": "build/overworld-evidence/actor.host-contract.json",
                "claims": ["control-release"],
            }
        )

        with self.assertRaisesRegex(
            ValidationFailure,
            "S4 proof needs",
        ):
            self.validate(scenario)

    def test_shared_s4_capture_policy_is_optional_human_view_not_proof(self) -> None:
        scenario = scenario_document()
        scenario["proofLevel"] = "S4"
        scenario["fixture"] = {"rom": "test.nds", "save": {"path": "test.sav", "kind": "sav"}, "seed": 0}
        scenario["subjects"] = [{"id": "ledyba", "species": 165, "role": "WILD", "acquisition": "spawn",
            "minimum": 1, "maximum": 1, "motionActor": True, "requirePresentation": True}]
        scenario["adapter"] = {"kind": "devtools-test", "test": "test.native-observation",
            "claims": ["live-actor-identity", "rendered-motion"], "minimumFrames": 1}
        for capture in ("none", "failure", "always"):
            with self.subTest(capture=capture):
                scenario["capture"] = capture
                self.assertEqual(self.validate(scenario)["capture"], capture)

    def test_shipped_scenarios_disable_image_capture(self) -> None:
        directory = Path(__file__).resolve().parents[2] / "tests/overworld/scenarios"
        paths = sorted(directory.glob("*.json"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(scenario=path.name):
                self.assertEqual(json.loads(path.read_text())["capture"], "none")

    def test_s5_executable_proof_requires_soak_frame_budget(self) -> None:
        scenario = scenario_document()
        scenario["proofLevel"] = "S5"
        scenario["stop"]["frameBudget"] = 4999
        scenario["adapter"].update(
            {
                "commands": [["{python}", "scripts/example.py"]],
                "result": "json-passed",
                "evidence": "build/overworld-evidence/actor.host-contract.json",
                "claims": ["control-release"],
            }
        )

        with self.assertRaisesRegex(
            ValidationFailure,
            "at least 5000 frames",
        ):
            self.validate(scenario)

    def test_s5_executable_proof_requires_measured_frame_floor(self) -> None:
        scenario = scenario_document()
        scenario["proofLevel"] = "S5"
        scenario["stop"]["frameBudget"] = 5000

        with self.assertRaisesRegex(
            ValidationFailure,
            "adapter.minimumFrames",
        ):
            self.validate(scenario)

    def test_s5_frame_floor_must_fit_inside_the_scenario_budget(self) -> None:
        scenario = scenario_document()
        scenario["proofLevel"] = "S5"
        scenario["stop"]["frameBudget"] = 5000
        scenario["adapter"]["minimumFrames"] = 5001

        with self.assertRaisesRegex(
            ValidationFailure,
            "must not exceed stop.frameBudget",
        ):
            self.validate(scenario)

    def test_s4_executable_proof_requires_fresh_visual_artifact(self) -> None:
        scenario = scenario_document()
        scenario["proofLevel"] = "S4"
        scenario["adapter"]["claims"] = ["rendered-motion"]

        with self.assertRaisesRegex(
            ValidationFailure,
            "adapter.visualArtifact",
        ):
            self.validate(scenario)

    def test_actor_observation_always_requires_trace_window_check(self) -> None:
        scenario = scenario_document()
        scenario["adapter"]["checks"].remove("trace-window-complete")

        with self.assertRaisesRegex(
            ValidationFailure,
            "requires trace-window-complete",
        ):
            self.validate(scenario)

    def test_actor_observation_rejects_unregistered_invariant(self) -> None:
        scenario = scenario_document()
        scenario["expect"]["invariants"].append("unregistered-runtime-claim")

        with self.assertRaisesRegex(
            ValidationFailure,
            "exact registered invariant",
        ):
            self.validate(scenario)

    def test_actor_observation_requires_invariant_semantic_checks(self) -> None:
        scenario = scenario_document()
        scenario["adapter"]["checks"].remove("control-returned")

        with self.assertRaisesRegex(
            ValidationFailure,
            "needs adapter checks: control-returned",
        ):
            self.validate(scenario)

    def test_executable_actor_observation_rejects_unsafe_evidence_output(self) -> None:
        scenario = scenario_document()
        scenario["adapter"].update(
            {
                "commands": [["{python}", "scripts/example.py"]],
                "result": "exit-zero",
                "evidence": "../actor.host-contract.json",
            }
        )

        with self.assertRaisesRegex(
            ValidationFailure,
            "under build/overworld-evidence",
        ):
            self.validate(scenario)

    def test_invalid_ordered_payload_fails_evaluation(self) -> None:
        scenario = self.validate(scenario_document())
        scenario["expect"]["orderedEvents"][1]["valueA"]["equals"] = 42

        result = evaluate_scenario_evidence(scenario, actor_evidence(), TRACE_SCHEMA)

        self.assertFalse(result["passed"])
        self.assertEqual(result["motionWindow"]["candidateCount"], 0)

    def test_invalid_ordered_event_name_is_rejected(self) -> None:
        scenario = scenario_document()
        scenario["expect"]["orderedEvents"][0]["event"] = "NOT_AN_EVENT"

        with self.assertRaisesRegex(ValidationFailure, "must be one of"):
            self.validate(scenario)

    def test_duplicate_ordered_ids_are_rejected(self) -> None:
        scenario = scenario_document()
        scenario["expect"]["orderedEvents"][1]["id"] = "start"

        with self.assertRaisesRegex(ValidationFailure, "assertion ids must be unique"):
            self.validate(scenario)

    def test_dangling_frame_reference_is_rejected(self) -> None:
        scenario = scenario_document()
        scenario["expect"]["frameTiming"][0]["to"] = "missing"

        with self.assertRaisesRegex(
            ValidationFailure, "must reference an orderedEvents assertion id"
        ):
            self.validate(scenario)

    def test_invalid_event_count_range_is_rejected(self) -> None:
        scenario = scenario_document()
        scenario["expect"]["eventCounts"][0]["minimum"] = 2
        scenario["expect"]["eventCounts"][0]["maximum"] = 1

        with self.assertRaisesRegex(ValidationFailure, "minimum must not exceed"):
            self.validate(scenario)

    def test_invalid_frame_timing_range_is_rejected(self) -> None:
        scenario = scenario_document()
        scenario["expect"]["frameTiming"][0]["minimum"] = 9
        scenario["expect"]["frameTiming"][0]["maximum"] = 8

        with self.assertRaisesRegex(ValidationFailure, "minimum must not exceed"):
            self.validate(scenario)

    def test_event_count_and_frame_timing_fail_outside_bounds(self) -> None:
        scenario = self.validate(scenario_document())
        evidence = actor_evidence()
        evidence["observation"]["trace"]["events"].insert(
            2,
            trace_event(3, 107, "LOGICAL_COMMIT", value_a=42, value_b=1),
        )
        for sequence, event in enumerate(
            evidence["observation"]["trace"]["events"], start=1
        ):
            event["sequence"] = sequence
        evidence["observation"]["trace"]["events"][3]["frame"] = 109

        result = evaluate_scenario_evidence(scenario, evidence, TRACE_SCHEMA)

        self.assertFalse(result["passed"])
        self.assertEqual(result["eventCountAssertions"][0]["actual"], 2)
        self.assertEqual(result["frameTimingAssertions"][0]["actualFrames"], 9)

    def test_actor_detach_does_not_prove_control_returned(self) -> None:
        scenario = scenario_document()
        scenario["expect"]["requiredEvents"] = [
            "MOTION_STARTED",
            "ACTOR_DETACHED",
        ]
        scenario["expect"]["orderedEvents"] = [
            scenario["expect"]["orderedEvents"][0],
            {"id": "finish", "event": "ACTOR_DETACHED", "reason": "OK"},
        ]
        scenario["expect"].pop("eventCounts")
        scenario["expect"]["frameTiming"] = [
            {"from": "start", "to": "finish", "minimum": 8, "maximum": 8}
        ]
        scenario = self.validate(scenario)
        evidence = actor_evidence()
        evidence["observation"]["trace"]["events"] = [
            trace_event(1, 100, "MOTION_STARTED", value_a=1, value_b=8),
            trace_event(2, 108, "ACTOR_DETACHED"),
        ]

        result = evaluate_scenario_evidence(scenario, evidence, TRACE_SCHEMA)

        control = next(
            check
            for check in result["semanticChecks"]
            if check["check"] == "control-returned"
        )
        self.assertFalse(control["passed"])
        self.assertFalse(result["passed"])

    def test_turn_skid_uses_public_actor_lifecycle_assertions(self) -> None:
        scenario = turn_skid_semantic_scenario()
        evidence = actor_evidence()
        first, next_sequence = skid_motion_events(1, 100)
        second, next_sequence = skid_motion_events(next_sequence, 110)
        events = first + second
        evidence["observation"]["trace"]["events"] = events
        evidence["observation"]["trace"]["header"]["count"] = len(events)
        evidence["observation"]["trace"]["header"]["nextSequence"] = next_sequence

        result = evaluate_scenario_evidence(scenario, evidence, TRACE_SCHEMA)

        self.assertEqual(scenario["adapter"]["kind"], "actor-observation")
        self.assertEqual(result["motionWindow"]["candidateCount"], 2)
        self.assertTrue(result["passed"])
        coordinates = [
            check
            for check in result["semanticChecks"]
            if check["check"] == "mounted-presentation-coordinates-equal"
        ]
        facing = [
            check
            for check in result["semanticChecks"]
            if check["check"] == "mounted-presentation-facing-locked"
        ]
        self.assertEqual(len(coordinates), 2)
        self.assertEqual(len(facing), 2)
        self.assertTrue(all(check["passed"] for check in coordinates + facing))

    def test_turn_skid_rejects_coordinate_or_facing_split(self) -> None:
        scenario = turn_skid_semantic_scenario()
        evidence = actor_evidence()
        first, next_sequence = skid_motion_events(1, 100)
        second, next_sequence = skid_motion_events(next_sequence, 110)
        events = first + second
        position = next(
            event
            for event in events
            if event["event"] == "MOUNT_PRESENTATION_POSITION"
        )
        position["valueB"] += 1
        state = next(
            event
            for event in events
            if event["event"] == "MOUNT_PRESENTATION_STATE"
        )
        state["valueA"] ^= 1 << 16
        evidence["observation"]["trace"]["events"] = events
        evidence["observation"]["trace"]["header"]["count"] = len(events)
        evidence["observation"]["trace"]["header"]["nextSequence"] = next_sequence

        result = evaluate_scenario_evidence(scenario, evidence, TRACE_SCHEMA)

        failed = {
            check["check"]
            for check in result["semanticChecks"]
            if not check["passed"]
        }
        self.assertIn("mounted-presentation-coordinates-equal", failed)
        self.assertIn("mounted-presentation-facing-locked", failed)
        self.assertFalse(result["passed"])

    def test_turn_skid_requires_exactly_two_motion_windows(self) -> None:
        scenario = turn_skid_semantic_scenario()
        evidence = actor_evidence()
        events, next_sequence = skid_motion_events(1, 100)
        evidence["observation"]["trace"]["events"] = events
        evidence["observation"]["trace"]["header"]["count"] = len(events)
        evidence["observation"]["trace"]["header"]["nextSequence"] = next_sequence

        result = evaluate_scenario_evidence(scenario, evidence, TRACE_SCHEMA)

        self.assertFalse(result["passed"])
        self.assertEqual(result["motionWindow"]["candidateCount"], 1)
        self.assertEqual(result["motionWindow"]["expectedCount"], 2)

    def test_diagonal_corner_contract_selects_rejection_and_control_motion(self) -> None:
        path = REPO / "tests/overworld/scenarios/walk.diagonal.corner-block.json"
        scenario = validate_scenario(retained_scenario_contract(path), path)
        evidence = actor_evidence()
        events = [
            trace_event(
                1,
                100,
                "CANDIDATE_REJECTED",
                reason="REJECTED_SIDE_TILE",
            ),
            trace_event(2, 101, "MOTION_STARTED", value_a=1, value_b=5),
            trace_event(3, 105, "LOGICAL_COMMIT", value_a=1, value_b=1),
            trace_event(4, 106, "MOTION_FINISHED", value_a=1, value_b=1),
            trace_event(5, 106, "CONTROL_RETURNED", value_a=0, value_b=1),
        ]
        evidence["observation"]["trace"]["events"] = events
        evidence["observation"]["trace"]["header"]["count"] = len(events)
        evidence["observation"]["trace"]["header"]["nextSequence"] = 6
        evidence["observation"]["actors"] = [
            {
                "index": 1,
                "active": True,
                "species": 155,
                "role": "MOUNTED",
                "presentationAttached": True,
                "subjectIdentity": 155,
                "authorityGeneration": 1,
                "engineAnchorGeneration": 1,
                "presentationGeneration": 1,
                "presentationState": 7,
                "motionKind": "NONE",
                "reservationId": 0,
                "handle": {
                    "slot": 1,
                    "generation": 2,
                    "fieldEpoch": 3,
                    "mapGeneration": 4,
                    "encounterGeneration": 5,
                    "value": (2 << 16) | 1,
                },
            }
        ]

        result = evaluate_scenario_evidence(scenario, evidence, TRACE_SCHEMA)

        self.assertTrue(result["passed"])
        self.assertEqual(result["motionWindow"]["candidateCount"], 1)

    def test_chain_pause_contract_selects_four_reposition_motions(self) -> None:
        path = REPO / "tests/overworld/scenarios/chain.pause.counts-semantic-moves.json"
        scenario = validate_scenario(retained_scenario_contract(path), path)
        evidence = actor_evidence()
        events = []
        sequence = 1
        frame = 100
        for _ in range(4):
            events.extend(
                [
                    trace_event(
                        sequence,
                        frame,
                        "MOTION_STARTED",
                        value_a=5,
                        value_b=16,
                    ),
                    trace_event(
                        sequence + 1,
                        frame + 16,
                        "MOTION_FINISHED",
                        value_a=1,
                        value_b=5,
                    ),
                    trace_event(
                        sequence + 2,
                        frame + 16,
                        "CONTROL_RETURNED",
                        value_a=0,
                        value_b=1,
                    ),
                ]
            )
            sequence += 3
            frame += 17
        evidence["observation"]["trace"]["events"] = events
        evidence["observation"]["trace"]["header"]["count"] = len(events)
        evidence["observation"]["trace"]["header"]["nextSequence"] = sequence
        evidence["observation"]["actors"] = [
            {
                "active": True,
                "species": 165,
                "role": "WILD",
                "presentationAttached": True,
                "subjectIdentity": 165,
                "authorityGeneration": 1,
                "engineAnchorGeneration": 0,
                "presentationGeneration": 1,
                "presentationState": 7,
                "handle": {
                    "slot": 1,
                    "generation": 2,
                    "fieldEpoch": 3,
                    "mapGeneration": 4,
                    "encounterGeneration": 5,
                    "value": (2 << 16) | 1,
                },
            }
        ]

        result = evaluate_scenario_evidence(scenario, evidence, TRACE_SCHEMA)

        self.assertTrue(result["passed"])
        self.assertEqual(result["motionWindow"]["candidateCount"], 4)

    def test_turn_skid_rejects_an_extra_incomplete_skid_window(self) -> None:
        scenario = turn_skid_semantic_scenario()
        evidence = actor_evidence()
        first, next_sequence = skid_motion_events(1, 100)
        second, next_sequence = skid_motion_events(next_sequence, 110)
        events = first + second + [
            trace_event(
                next_sequence,
                120,
                "MOTION_STARTED",
                value_a=4,
                value_b=4,
            )
        ]
        evidence["observation"]["trace"]["events"] = events
        evidence["observation"]["trace"]["header"]["count"] = len(events)
        evidence["observation"]["trace"]["header"]["nextSequence"] = (
            next_sequence + 1
        )

        result = evaluate_scenario_evidence(scenario, evidence, TRACE_SCHEMA)

        self.assertFalse(result["passed"])
        self.assertEqual(result["motionWindow"]["candidateCount"], 2)
        self.assertEqual(result["motionWindow"]["targetCount"], 3)


class MovementPolicyDescriptorTests(unittest.TestCase):
    def test_private_policy_state_is_not_resolved_from_version_4_descriptor(self) -> None:
        descriptor = {
            "privateServices": [
                {
                    "name": "movementPolicy",
                    "reserved": 0,
                    "status": "available",
                    "version": 4,
                }
            ]
        }

        with self.assertRaisesRegex(
            ValidationFailure, "keeps actor policy state private"
        ):
            resolve_movement_policy_state(descriptor, 7)

    def test_version_3_policy_descriptor_is_stale(self) -> None:
        descriptor = {
            "privateServices": [
                {
                    "name": "movementPolicy",
                    "stateTable": 0x023B9000,
                    "stateSize": 32,
                    "stateCapacity": 7,
                    "status": "available",
                    "version": 3,
                }
            ]
        }

        with self.assertRaisesRegex(ValidationFailure, "not available at version 4"):
            resolve_movement_policy_state(descriptor, 7)


class ExecutionReceiptTests(unittest.TestCase):
    def test_changed_receipt_body_is_rejected(self) -> None:
        events = scenario_document()["events"]
        receipt = build_execution_record(
            scenario_id="actor.host-contract",
            declared_events=events,
            completed=True,
            session="a" * 32,
        )
        receipt["declaredEvents"][0]["value"] = "Move left once"

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "execution.json"
            path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(
                ValidationFailure, "declarationSha256 differs"
            ):
                load_execution_record(path)

    def test_receipt_event_sequence_must_match_scenario(self) -> None:
        scenario = scenario_document()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            rom = repo / "rom.nds"
            rom.write_bytes(b"rom")
            evidence = {
                "provenance": build_evidence_provenance(
                    scenario_id=scenario["id"],
                    rom=rom,
                    save=None,
                    seed=scenario["fixture"]["seed"],
                ),
                "execution": build_execution_record(
                    scenario_id=scenario["id"],
                    declared_events=[
                        {"at": 0, "kind": "input", "value": "Move left once"}
                    ],
                    completed=True,
                    session="a" * 32,
                ),
            }

            with self.assertRaisesRegex(
                ValidationFailure, "input declaration differs"
            ):
                require_scenario_provenance(
                    evidence, scenario, repo, "a" * 32
                )

    def test_receipt_trace_window_must_match_captured_trace(self) -> None:
        scenario = scenario_document()
        evidence = actor_evidence()
        evidence["execution"] = build_execution_record(
            scenario_id=scenario["id"],
            declared_events=scenario["events"],
            completed=True,
            session="a" * 32,
            trace=evidence["observation"]["trace"],
        )
        evidence["observation"]["trace"]["header"]["nextSequence"] += 1

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "rom.nds").write_bytes(b"rom")
            evidence["provenance"] = build_evidence_provenance(
                scenario_id=scenario["id"],
                rom=repo / "rom.nds",
                save=None,
                seed=scenario["fixture"]["seed"],
            )
            with self.assertRaisesRegex(ValidationFailure, "trace window differs"):
                require_scenario_provenance(
                    evidence, scenario, repo, "a" * 32
                )

    def test_receipt_records_public_trace_sequence_bounds(self) -> None:
        trace = actor_evidence()["observation"]["trace"]
        receipt = build_execution_record(
            scenario_id="actor.host-contract",
            declared_events=scenario_document()["events"],
            completed=True,
            session="a" * 32,
            trace=trace,
        )

        self.assertEqual(
            receipt["traceWindow"],
            {
                "oldestSequence": 1,
                "nextSequence": 5,
                "eventCount": 4,
                "fieldEpoch": 3,
                "eventsSha256": receipt["traceWindow"]["eventsSha256"],
            },
        )
        self.assertRegex(receipt["traceWindow"]["eventsSha256"], r"^[0-9a-f]{64}$")

    def test_receipt_trace_digest_rejects_changed_event_payload(self) -> None:
        scenario = scenario_document()
        evidence = actor_evidence()
        evidence["execution"] = build_execution_record(
            scenario_id=scenario["id"],
            declared_events=scenario["events"],
            completed=True,
            session="a" * 32,
            trace=evidence["observation"]["trace"],
        )
        evidence["observation"]["trace"]["events"][1]["valueA"] = 42

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "rom.nds").write_bytes(b"rom")
            evidence["provenance"] = build_evidence_provenance(
                scenario_id=scenario["id"],
                rom=repo / "rom.nds",
                save=None,
                seed=scenario["fixture"]["seed"],
            )
            with self.assertRaisesRegex(ValidationFailure, "trace events differ"):
                require_scenario_provenance(
                    evidence, scenario, repo, "a" * 32
                )

    def test_stale_actor_evidence_session_replay_fails_closed(self) -> None:
        scenario = scenario_document()
        evidence = actor_evidence()
        evidence["execution"] = build_execution_record(
            scenario_id=scenario["id"],
            declared_events=scenario["events"],
            completed=True,
            session="a" * 32,
            trace=evidence["observation"]["trace"],
        )
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "rom.nds").write_bytes(b"rom")
            evidence["provenance"] = build_evidence_provenance(
                scenario_id=scenario["id"],
                rom=repo / "rom.nds",
                save=None,
                seed=scenario["fixture"]["seed"],
            )
            with self.assertRaisesRegex(
                ValidationFailure, "different controller session"
            ):
                require_scenario_provenance(
                    evidence, scenario, repo, "b" * 32
                )


class RoadmapGateTests(unittest.TestCase):
    RUNNER = "legacy.mounted-frames"
    RUNNER_KEY = (
        "legacy.mounted-frames"
    )
    CLAIMS = [
        "natural-input",
        "live-actor-identity",
        "profile-resolution",
        "frame-pacing",
        "control-release",
    ]

    @classmethod
    def runtime_step(
        cls, command: list[str], *, minimum_frames: int = 0,
        maximum_frames: int = 0,
    ) -> dict:
        registry = json.loads(
            (REPO / "tools/overworld/runtime_proof_registry.json").read_text()
        )
        contract = registry["measurementContracts"][cls.RUNNER_KEY]
        evidence = {}
        for claim in cls.CLAIMS:
            evidence[claim] = []
            for specification in contract[claim]:
                actual = specification.get("expected")
                if specification.get("validator") == "mounted-frame-matrix-v1":
                    durations = [*range(1, 33), *range(1, 33), 5]
                    actual = (
                        {
                            "durations": durations,
                            "elapsedCounts": durations,
                            "diagonalAttempt": {
                                "before": [10, 10],
                                "after": [10, 10],
                                "mode": "IDLE",
                                "pending": 0,
                            },
                        }
                        if specification.get("aspect") == "counts"
                        else {
                            "durations": durations,
                            "sequences": [
                                list(range(duration)) for duration in durations
                            ],
                        }
                    )
                if actual is None:
                    actual = {
                        "integer": max(1, specification.get("minimum", 1)),
                        "array": [1],
                        "object": {"value": 1},
                        "string": "observed",
                    }[specification["type"]]
                expected = copy.deepcopy(actual)
                evidence[claim].append({
                    "name": specification["name"],
                    "actual": copy.deepcopy(actual),
                    "expected": expected,
                    **(
                        {"operator": specification["operator"]}
                        if specification["operator"] != "eq"
                        else {}
                    ),
                })
        evidence_hash = hashlib.sha256(json.dumps(
            evidence,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()).hexdigest()
        return {
            "command": command,
            "passed": True,
            "proofClaims": {claim: True for claim in cls.CLAIMS},
            "proofEvidence": evidence,
            "proofExecution": {
                "session": "a" * 32,
                "framesObserved": minimum_frames,
                "minimumFrames": minimum_frames,
                "maximumFrames": maximum_frames,
                "iterations": 1,
                "iterationPassed": [True],
                "iterationFrames": [minimum_frames],
                "iterationEvidenceSha256": [evidence_hash],
            },
        }

    @staticmethod
    def seal_run(document: dict) -> dict:
        run_id, result_sha256 = run_id_for(
            document["identity"],
            document["result"],
            document["proofLevel"],
            document["costTier"],
        )
        document["runId"] = run_id
        document["resultSha256"] = result_sha256
        return document

    @staticmethod
    def manifest(
        *,
        minimum_proof: list[str],
        scenario_ids: list[str],
    ) -> dict:
        return {
            "checks": [
                {
                    "id": "host.model",
                    "proofLevel": "S1",
                    "command": ["{python}", "scripts/model.py"],
                },
                {
                    "id": "runtime.motion",
                    "proofLevel": "S3",
                    "command": [
                        "{python}", "scripts/owctl", "scenario", "run",
                        RoadmapGateTests.RUNNER,
                    ],
                },
            ],
            "capabilities": [
                {
                    "id": "motion.capability",
                    "checks": ["host.model", "runtime.motion"],
                    "scenarios": scenario_ids,
                    "minimumProof": minimum_proof,
                    "traceGroups": ["motion"],
                }
            ],
        }

    @staticmethod
    def runtime_scenario(
        runner: str,
        *,
        proof_level: str = "S3",
        kind: str = "command-sequence",
        subjects: list[dict] | None = None,
    ) -> dict:
        scenario = {
            "status": "active",
            "proofLevel": proof_level,
            "capabilities": ["motion.capability"],
            "fixture": {"rom": "test.nds", "save": None, "seed": 0},
            "adapter": {
                "kind": kind,
                "claims": list(RoadmapGateTests.CLAIMS),
                "commands": [[
                    "{python}", "scripts/owctl", "scenario", "run",
                    runner,
                ]],
            },
        }
        if subjects is not None:
            scenario["subjects"] = subjects
        return scenario

    @staticmethod
    def static_results(passed: bool = True) -> list[dict]:
        return [{
            "id": "host.model",
            "proofLevel": "S1",
            "passed": passed,
        }]

    @staticmethod
    def accepted(*scenario_ids: str, proof_level: str = "S3") -> dict:
        return {
            scenario_id: {
                "proofLevel": proof_level,
                "runners": [RoadmapGateTests.RUNNER_KEY],
            }
            for scenario_id in scenario_ids
        }

    def test_roadmap_parser_exposes_the_permanent_gate(self) -> None:
        args = build_parser().parse_args(["verify", "roadmap", "--json"])

        self.assertEqual(args.verify_command, "roadmap")
        self.assertEqual(args.rom, Path("test.nds"))

    def test_roadmap_gate_reports_planned_scenarios(self) -> None:
        manifest = self.manifest(
            minimum_proof=["S1", "S3"],
            scenario_ids=["planned", "exact"],
        )
        scenarios = {
            "planned": {
                "status": "planned",
                "proofLevel": "S3",
                "capabilities": ["motion.capability"],
                "adapter": None,
            },
            "exact": self.runtime_scenario(
                self.RUNNER,
                kind="actor-observation",
                subjects=[{"id": "actor"}],
            ),
        }

        result = _roadmap_contract_audit(
            manifest,
            scenarios,
            self.static_results(),
            self.accepted("exact"),
        )

        self.assertEqual(
            [item["id"] for item in result["plannedScenarios"]],
            ["planned"],
        )

    def test_roadmap_gate_uses_exact_runner_matching(self) -> None:
        manifest = self.manifest(
            minimum_proof=["S1", "S3"],
            scenario_ids=["wrong"],
        )
        scenarios = {"wrong": self.runtime_scenario("different_motion")}

        result = _roadmap_contract_audit(
            manifest,
            scenarios,
            self.static_results(),
            {
                "wrong": {
                    "proofLevel": "S3",
                    "runners": [
                        "legacy.different-motion"
                    ],
                }
            },
        )

        self.assertEqual(
            result["runtimeCheckCoverageGaps"][0]["id"],
            "runtime.motion",
        )
        self.assertEqual(
            result["runtimeCheckCoverageGaps"][0]["expectedRunner"],
            self.RUNNER_KEY,
        )
        self.assertEqual(
            result["runtimeCheckCoverageGaps"][0]["exactScenarios"],
            [],
        )

    def test_roadmap_gate_requires_each_exact_minimum_proof_level(self) -> None:
        manifest = self.manifest(
            minimum_proof=["S1", "S3"],
            scenario_ids=["visual-only"],
        )
        scenarios = {
            "visual-only": self.runtime_scenario(
                self.RUNNER,
                proof_level="S4",
                kind="actor-observation",
                subjects=[{"id": "actor"}],
            )
        }

        result = _roadmap_contract_audit(
            manifest,
            scenarios,
            self.static_results(),
            self.accepted("visual-only", proof_level="S4"),
        )

        self.assertEqual(
            result["capabilityProofGaps"][0]["gaps"],
            ["S3"],
        )
        self.assertEqual(
            result["capabilityProofGaps"][0]["availableProof"],
            ["S1", "S4"],
        )
        self.assertEqual(
            result["runtimeCheckCoverageGaps"][0]["exactScenarios"],
            [],
        )

    def test_contract_validation_rejects_an_impossible_minimum_proof(self) -> None:
        manifest = copy.deepcopy(load_feature_manifest(
            REPO / "tools/overworld/system_features.yaml"
        ))
        scenarios = load_scenarios(REPO / "tests/overworld/scenarios")
        capability = next(
            item for item in manifest["capabilities"]
            if item["id"] == "battle.capture"
        )
        capability["minimumProof"] = ["S2", "S3", "S5"]

        with self.assertRaisesRegex(
            ValidationFailure,
            "minimum proof S5 has no linked scenario",
        ):
            cross_validate(manifest, scenarios, REPO)

    def test_roadmap_gate_does_not_credit_a_mounted_actor_as_wild(self) -> None:
        manifest = self.manifest(
            minimum_proof=["S1", "S3"],
            scenario_ids=["wrong-role"],
        )
        manifest["capabilities"][0]["roleProof"] = [
            {"proofLevel": "S3", "roles": ["Wild"]}
        ]
        scenarios = {
            "wrong-role": self.runtime_scenario(
                self.RUNNER,
                kind="actor-observation",
                subjects=[{
                    "id": "mounted",
                    "role": "MOUNTED",
                    "motionActor": True,
                }],
            )
        }

        result = _roadmap_contract_audit(
            manifest,
            scenarios,
            self.static_results(),
            self.accepted("wrong-role"),
        )

        self.assertEqual(
            result["capabilityRoleProofGaps"][0]["missingRoles"],
            ["Wild"],
        )

    def test_shared_lifecycle_contract_supplies_registered_gameplay_role_proof(self) -> None:
        manifest = load_feature_manifest(
            REPO / "tools/overworld/system_features.yaml"
        )
        scenarios = copy.deepcopy(load_scenarios(
            REPO / "tests/overworld/scenarios"
        ))
        saved = retained_scenario_contract(
            REPO / "tests/overworld/scenarios/mount.begin-current-follower.json")
        self.assertTrue(saved["roleProof"])
        scenarios["mount.begin-current-follower"]["roleProof"] = saved["roleProof"]

        cross_validate(manifest, scenarios, REPO)
        scenarios["mount.begin-current-follower"]["roleProof"][0]["measurement"] = (
            "missing-role-transition"
        )
        with self.assertRaisesRegex(ValidationFailure, "is not registered exactly once"):
            cross_validate(manifest, scenarios, REPO)

    def test_real_catalog_keeps_new_acceptance_gaps_visible(self) -> None:
        manifest = load_feature_manifest(
            REPO / "tools/overworld/system_features.yaml"
        )
        scenarios = load_scenarios(REPO / "tests/overworld/scenarios")
        static_results = [
            {
                "id": check["id"],
                "proofLevel": check["proofLevel"],
                "passed": True,
            }
            for check in manifest["checks"]
            if check["proofLevel"] in ("S0", "S1", "S2")
        ]
        accepted = {}  # No completed shared run is supplied by this host test.

        result = _roadmap_contract_audit(
            manifest,
            scenarios,
            static_results,
            accepted,
        )

        # The queue shrinks as audits and collectors are completed. Prove the
        # gate reports the exact remaining IDs, not a historic queue length.
        self.assertEqual({item["id"] for item in result["plannedScenarios"]}, {
            key for key, scenario in scenarios.items()
            if scenario["status"] == "planned"
        })
        self.assertEqual({item["id"] for item in result["verificationSetupGaps"]}, {
            key for key, scenario in scenarios.items()
            if scenario["status"] == "active"
            and scenario.get("verification", {}).get("setupAudit") == "pending"
        })
        self.assertEqual({item["id"] for item in result["runtimeCheckCoverageGaps"]},
                         {check["id"] for check in manifest["checks"]
                          if check["proofLevel"] in ("S3", "S4", "S5")})
        self.assertTrue(all(not item["passed"] and not item["exactScenarios"]
                            for item in result["runtimeCheckCoverageGaps"]))
        expected_proof_gaps = {item["id"]: [level for level in item["minimumProof"]
                                          if level in ("S3", "S4", "S5")]
                               for item in manifest["capabilities"]
                               if any(level in ("S3", "S4", "S5") for level in item["minimumProof"])}
        self.assertEqual({item["id"]: item["gaps"] for item in result["capabilityProofGaps"]},
                         expected_proof_gaps)
        self.assertEqual({(item["id"], item["proofLevel"]): item["missingRoles"]
                          for item in result["capabilityRoleProofGaps"]},
                         {(cap["id"], item["proofLevel"]): item["roles"]
                          for cap in manifest["capabilities"] for item in cap.get("roleProof", [])})
        self.assertEqual(result["weakActorScopedScenarios"], [])

    def test_roadmap_gate_does_not_credit_a_failed_static_check(self) -> None:
        manifest = self.manifest(
            minimum_proof=["S1", "S3"],
            scenario_ids=["exact"],
        )
        scenarios = {"exact": self.runtime_scenario(self.RUNNER)}

        result = _roadmap_contract_audit(
            manifest,
            scenarios,
            self.static_results(False),
            self.accepted("exact"),
        )

        self.assertEqual(result["staticCheckGaps"][0]["id"], "host.model")
        self.assertEqual(result["capabilityProofGaps"][0]["gaps"], ["S1"])

    def test_roadmap_gate_requires_an_accepted_runtime_run(self) -> None:
        manifest = self.manifest(
            minimum_proof=["S1", "S3"],
            scenario_ids=["exact"],
        )
        scenarios = {"exact": self.runtime_scenario(self.RUNNER)}

        result = _roadmap_contract_audit(
            manifest,
            scenarios,
            self.static_results(),
            {},
        )

        self.assertEqual(
            result["runtimeCheckCoverageGaps"][0]["exactScenarios"],
            [],
        )
        self.assertEqual(result["capabilityProofGaps"][0]["gaps"], ["S3"])

    def test_recorder_control_cannot_supply_gameplay_or_role_credit(self) -> None:
        manifest = self.manifest(minimum_proof=["S1", "S3"], scenario_ids=["control"])
        manifest["capabilities"][0]["roleProof"] = [{"proofLevel": "S3", "roles": ["Wild"]}]
        scenario = self.runtime_scenario(self.RUNNER, kind="actor-observation",
                                         subjects=[{"id": "actor", "role": "WILD", "motionActor": True}])
        scenario["verification"] = {"kind": "observer-control"}
        result = _roadmap_contract_audit(manifest, {"control": scenario},
                                         self.static_results(), self.accepted("control"))
        self.assertEqual(result["capabilityProofGaps"][0]["gaps"], ["S3"])
        self.assertEqual(result["capabilityRoleProofGaps"][0]["missingRoles"], ["Wild"])
        self.assertTrue(result["runtimeCheckCoverageGaps"])

    def test_roadmap_gate_requires_every_active_runtime_scenario(self) -> None:
        manifest = self.manifest(
            minimum_proof=["S1", "S3"],
            scenario_ids=["tested", "untested"],
        )
        scenarios = {
            scenario_id: self.runtime_scenario(
                self.RUNNER,
                kind="actor-observation",
                subjects=[{"id": "actor"}],
            )
            for scenario_id in ("tested", "untested")
        }

        result = _roadmap_contract_audit(
            manifest,
            scenarios,
            self.static_results(),
            self.accepted("tested"),
        )

        self.assertEqual(
            [item["id"] for item in result["runtimeScenarioEvidenceGaps"]],
            ["untested"],
        )
        self.assertEqual([item["id"] for item in result["runtimeCheckCoverageGaps"]], ["runtime.motion"])
        self.assertEqual(result["runtimeCheckCoverageGaps"][0]["exactScenarios"], [])
        self.assertEqual(result["capabilityProofGaps"], [])

    def test_roadmap_static_results_execute_only_s0_to_s2_checks(self) -> None:
        manifest = self.manifest(minimum_proof=["S1"], scenario_ids=[])
        manifest["checks"][0]["requires"] = ["source"]

        with mock.patch(
            "tools.overworld.control._run_command",
            return_value={"command": ["model"], "returnCode": 0, "passed": True},
        ) as run_command:
            results = _roadmap_static_results(manifest)

        self.assertEqual([item["id"] for item in results], ["host.model"])
        self.assertTrue(results[0]["passed"])
        run_command.assert_called_once()

    def test_roadmap_runtime_evidence_accepts_only_current_identity(self) -> None:
        scenario = self.runtime_scenario(self.RUNNER)
        source = {"revision": "current", "dirty": False}
        current_emulator = {
            "name": "DeSmuME",
            "present": True,
            "pythonExecutable": "/repo/.venv/bin/python3",
            "pythonFlags": ["-I", "-S", "-B"],
            "pythonPackage": "py-desmume",
            "pythonPackageVersion": "0.0.9",
        }
        file_identity = {
            "path": "test.nds",
            "present": True,
            "size": 128,
            "sha256": "a" * 64,
        }
        fixture = {
            "passed": True,
            "identity": {
                "rom": file_identity,
                "buildManifest": {**file_identity, "path": "build/seal.json"},
                "debugDescriptor": {
                    **file_identity,
                    "path": "build/overworld-system.debug.json",
                },
                **{
                    identity_name: {
                        **file_identity,
                        "path": path.as_posix(),
                    }
                    for _key, identity_name, _overlay_id, path
                    in OVERWORLD_PRODUCT_OUTPUTS
                },
                **{
                    identity_name: {
                        **file_identity,
                        "path": path.as_posix(),
                    }
                    for identity_name, path in OVERWORLD_LINKED_OUTPUTS
                },
            },
        }
        command = _expand_command(scenario["adapter"]["commands"][0])
        step = self.runtime_step(command)
        identity = {
            "kind": "scenario",
            "target": "exact",
            "source": source,
            "scenarioRevision": digest_value(scenario),
            "rom": fixture["identity"]["rom"],
            "save": None,
            "buildManifest": fixture["identity"]["buildManifest"],
            "debugDescriptor": fixture["identity"]["debugDescriptor"],
            **{
                identity_name: fixture["identity"][identity_name]
                for _key, identity_name, _overlay_id, _path
                in OVERWORLD_PRODUCT_OUTPUTS
            },
            **{
                identity_name: fixture["identity"][identity_name]
                for identity_name, _path in OVERWORLD_LINKED_OUTPUTS
            },
            "seed": scenario["fixture"]["seed"],
            "emulator": current_emulator,
            "commands": [command],
        }
        document = self.seal_run({
            "schema": RUN_SCHEMA,
            "identity": identity,
            "proofLevel": "S3",
            "costTier": 3,
            "result": {"passed": True, "steps": [step]},
        })

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "run.json"
            with mock.patch("tools.overworld.control.REPO", root):
                step.update(_command_record(command, subprocess.CompletedProcess(command, 0, b"{}", b"")))
            self.seal_run(document)
            manifest_path.write_text(json.dumps(document))
            with mock.patch("tools.overworld.control.REPO", root):
                accepted = _roadmap_runtime_evidence(
                    {"exact": scenario}, fixture, run_directory=root,
                    current_source=source, current_emulator=current_emulator)
            self.assertEqual(
                accepted["acceptedScenarios"]["exact"]["runners"],
                [self.RUNNER_KEY],
            )
            # Artifact identity remains mandatory when reusing a passed run.
            log = root / step["stdoutArtifact"]["path"]
            log.write_bytes(b"[]")  # Same size, different content.
            with mock.patch("tools.overworld.control.REPO", root):
                changed_log = _roadmap_runtime_evidence(
                    {"exact": scenario}, fixture, run_directory=root,
                    current_source=source, current_emulator=current_emulator)
            self.assertEqual(changed_log["acceptedScenarios"], {})
            self.assertIn("command output rejected", changed_log["currentFailures"][0]["reason"])
            log.write_bytes(b"{}")

            stale_product = json.loads(json.dumps(document))
            stale_product["identity"]["helperOverlay"]["sha256"] = "d" * 64
            self.seal_run(stale_product)
            manifest_path.write_text(json.dumps(stale_product))
            rejected_product = _roadmap_runtime_evidence(
                {"exact": scenario},
                fixture,
                run_directory=root,
                current_source=source,
                current_emulator=current_emulator,
            )
            self.assertEqual(rejected_product["acceptedScenarios"], {})
            self.assertEqual(
                rejected_product["rejectedRuns"][0]["reason"],
                "helperOverlay identity differs",
            )

            stale_cases = []
            stale_source = json.loads(json.dumps(document))
            stale_source["identity"]["source"] = {
                "revision": "stale",
                "dirty": False,
            }
            stale_cases.append(stale_source)
            stale_rom = json.loads(json.dumps(document))
            stale_rom["identity"]["rom"]["sha256"] = "b" * 64
            stale_cases.append(stale_rom)
            stale_scenario = json.loads(json.dumps(document))
            stale_scenario["identity"]["scenarioRevision"] = "c" * 64
            stale_cases.append(stale_scenario)
            wrong_proof = json.loads(json.dumps(document))
            wrong_proof["proofLevel"] = "S4"
            stale_cases.append(wrong_proof)
            wrong_seed = json.loads(json.dumps(document))
            wrong_seed["identity"]["seed"] = 7
            stale_cases.append(wrong_seed)
            wrong_emulator = json.loads(json.dumps(document))
            wrong_emulator["identity"]["emulator"]["pythonPackageVersion"] = "old"
            stale_cases.append(wrong_emulator)
            wrong_arguments = json.loads(json.dumps(document))
            wrong_arguments["identity"]["commands"][0].extend(["--extra", "1"])
            wrong_arguments["result"]["steps"][0]["command"].extend(
                ["--extra", "1"]
            )
            stale_cases.append(wrong_arguments)
            failed = json.loads(json.dumps(document))
            failed["result"]["passed"] = False
            stale_cases.append(failed)
            wrong_runner = json.loads(json.dumps(document))
            wrong_runner_command = list(command)
            wrong_runner_command[-1] = "mankey_hops"
            wrong_runner["identity"]["commands"] = [wrong_runner_command]
            wrong_runner["result"]["steps"][0]["command"] = wrong_runner_command
            stale_cases.append(wrong_runner)

            for stale in stale_cases:
                self.seal_run(stale)
                manifest_path.write_text(json.dumps(stale))
                rejected = _roadmap_runtime_evidence(
                    {"exact": scenario},
                    fixture,
                    run_directory=root,
                    current_source=source,
                    current_emulator=current_emulator,
                )
                self.assertEqual(rejected["acceptedScenarios"], {})

    def test_roadmap_current_failure_blocks_a_passing_repetition(self) -> None:
        scenario = self.runtime_scenario(self.RUNNER)
        source = {"revision": "current", "dirty": False}
        current_emulator = {"name": "DeSmuME", "present": True}
        file_identity = {
            "path": "test.nds",
            "present": True,
            "size": 128,
            "sha256": "a" * 64,
        }
        fixture = {
            "passed": True,
            "identity": {
                "rom": file_identity,
                "buildManifest": {**file_identity, "path": "build/seal.json"},
                "debugDescriptor": {
                    **file_identity,
                    "path": "build/overworld-system.debug.json",
                },
                **{
                    identity_name: {
                        **file_identity,
                        "path": path.as_posix(),
                    }
                    for _key, identity_name, _overlay_id, path
                    in OVERWORLD_PRODUCT_OUTPUTS
                },
                **{
                    identity_name: {
                        **file_identity,
                        "path": path.as_posix(),
                    }
                    for identity_name, path in OVERWORLD_LINKED_OUTPUTS
                },
            },
        }
        command = _expand_command(scenario["adapter"]["commands"][0])
        step = self.runtime_step(command)
        identity = {
            "kind": "scenario",
            "target": "exact",
            "source": source,
            "scenarioRevision": digest_value(scenario),
            "rom": fixture["identity"]["rom"],
            "save": None,
            "buildManifest": fixture["identity"]["buildManifest"],
            "debugDescriptor": fixture["identity"]["debugDescriptor"],
            **{
                identity_name: fixture["identity"][identity_name]
                for _key, identity_name, _overlay_id, _path
                in OVERWORLD_PRODUCT_OUTPUTS
            },
            **{
                identity_name: fixture["identity"][identity_name]
                for identity_name, _path in OVERWORLD_LINKED_OUTPUTS
            },
            "seed": 0,
            "emulator": current_emulator,
            "commands": [command],
        }
        passed = self.seal_run({
            "schema": RUN_SCHEMA,
            "identity": identity,
            "proofLevel": "S3",
            "costTier": 3,
            "result": {"passed": True, "steps": [step]},
        })
        failed = json.loads(json.dumps(passed))
        failed["result"]["passed"] = False
        failed["result"]["steps"][0]["passed"] = False
        self.seal_run(failed)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch("tools.overworld.control.REPO", root):
                step.update(_command_record(command, subprocess.CompletedProcess(command, 0, b"{}", b"")))
            self.seal_run(passed)
            (root / "passing.json").write_text(json.dumps(passed))
            (root / "failed.json").write_text(json.dumps(failed))
            with mock.patch("tools.overworld.control.REPO", root):
                evidence = _roadmap_runtime_evidence(
                    {"exact": scenario}, fixture, run_directory=root,
                    current_source=source, current_emulator=current_emulator)

        self.assertIn("exact", evidence["acceptedScenarios"])
        self.assertEqual(len(evidence["currentFailures"]), 1)
        self.assertEqual(evidence["currentFailures"][0]["reason"], "run failed")

    def test_roadmap_actor_observation_revalidates_evidence_and_controls(self) -> None:
        scenario = self.runtime_scenario(
            self.RUNNER,
            kind="actor-observation",
            subjects=[{"id": "actor"}],
        )
        scenario["expect"] = {
            "requiredEvents": ["CONTROL_RETURNED"],
            "orderedEvents": [],
            "eventCounts": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            evidence_path = Path(directory) / "actor-evidence.json"
            evidence_path.write_text("{}")
            scenario["adapter"]["evidence"] = str(evidence_path)
            evidence_identity = {
                "path": evidence_path.name,
                "size": 2,
                "sha256": hashlib.sha256(b"{}").hexdigest(),
            }
            positive = {
                "passed": True,
                "resultKind": "actor-observation",
                "subjectAssertions": [{"id": "actor", "passed": True}],
            }
            subject_negative = {
                "passed": True,
                "applied": True,
                "subjects": ["actor"],
                "failedSubjects": ["actor"],
            }
            behavior_negative = {
                "passed": True,
                "applied": True,
                "event": "CONTROL_RETURNED",
                "removed": 1,
            }
            evaluation = {
                **positive,
                "subjectNegativeControl": subject_negative,
                "behaviorNegativeControl": behavior_negative,
                "evidence": evidence_identity,
            }
            command_step = {
                "proofExecution": {"session": "a" * 32},
            }
            with (
                mock.patch("tools.overworld.control.REPO", evidence_path.parent),
                mock.patch(
                    "tools.overworld.control.load_evidence", return_value={}
                ),
                mock.patch(
                    "tools.overworld.control.load_debug_descriptor", return_value={}
                ),
                mock.patch("tools.overworld.control.require_descriptor_identity"),
                mock.patch("tools.overworld.control.require_scenario_provenance"),
                mock.patch(
                    "tools.overworld.control.evaluate_scenario_evidence",
                    return_value=positive,
                ),
                mock.patch(
                    "tools.overworld.control.evaluate_subject_negative_control",
                    return_value=subject_negative,
                ),
                mock.patch(
                    "tools.overworld.control.evaluate_behavior_negative_control",
                    return_value=behavior_negative,
                ),
            ):
                self.assertIsNone(
                    _roadmap_actor_evaluation_rejection(
                        scenario, [command_step, evaluation]
                    )
                )
                missing_control = json.loads(json.dumps(evaluation))
                missing_control.pop("behaviorNegativeControl")
                self.assertEqual(
                    _roadmap_actor_evaluation_rejection(
                        scenario, [command_step, missing_control]
                    ),
                    "stored actor-observation evaluation differs from current evidence",
                )
                self.assertEqual(
                    _roadmap_actor_evaluation_rejection(scenario, []),
                    "actor-observation evaluation is missing or duplicated",
                )

    def test_roadmap_gate_rejects_weak_actor_scoped_adapters(self) -> None:
        manifest = self.manifest(
            minimum_proof=["S1", "S3"],
            scenario_ids=["command", "observation", "strong"],
        )
        scenarios = {
            "command": self.runtime_scenario(self.RUNNER),
            "observation": self.runtime_scenario(
                self.RUNNER, kind="actor-observation"
            ),
            "strong": self.runtime_scenario(
                self.RUNNER,
                kind="actor-observation",
                subjects=[{"id": "actor"}],
            ),
        }

        result = _roadmap_contract_audit(
            manifest,
            scenarios,
            self.static_results(),
            self.accepted("command", "observation", "strong"),
        )

        weak = {
            item["id"]: item["reasons"]
            for item in result["weakActorScopedScenarios"]
        }
        self.assertEqual(
            weak,
            {
                "command": [
                    "adapter is not actor-observation",
                    "structured subjects are missing",
                ],
                "observation": ["structured subjects are missing"],
            },
        )

    def test_roadmap_fixture_reports_all_final_identities(self) -> None:
        file_record = {
            "present": True,
            "size": 128,
            "sha256": "a" * 64,
        }
        payload = {
            "schemaVersion": 1,
            "passed": True,
            "rom": {**file_record, "path": "test.nds"},
            "buildManifest": {**file_record, "path": "build/seal.json"},
            "checks": [
                {"name": "make-target-current", "passed": True},
                {"name": "sealed-build-manifest", "passed": True},
                {"name": "packaged-actor-system", "passed": True},
                {"name": "packaged-mount-system", "passed": True},
                {"name": "stock-main-queue-observation", "passed": True},
                {"name": "shared-devtools-isolated-startup", "passed": True},
                {
                    "name": "overworld-product-outputs",
                    "passed": True,
                    "outputs": {
                        key: {
                            "overlayId": overlay_id,
                            "output": {
                                **file_record,
                                "path": path.as_posix(),
                            },
                            "packaged": {
                                **file_record,
                                "path": f"test.nds#overlay/{overlay_id}",
                            },
                            "matched": True,
                        }
                        for key, _identity_name, overlay_id, path
                        in OVERWORLD_PRODUCT_OUTPUTS
                    },
                },
                {
                    "name": "debug-descriptor-overlay",
                    "passed": True,
                    "descriptor": {
                        **file_record,
                        "path": "build/overworld-system.debug.json",
                    },
                    "overlay": {
                        **file_record,
                        "path": "build/output_overworld_actor_system_overlay.bin",
                    },
                },
                {
                    "name": "runtime-linked-symbol-inputs",
                    "passed": True,
                    "outputs": {
                        name: {
                            "output": {
                                **file_record,
                                "path": path.as_posix(),
                            },
                            "matched": True,
                        }
                        for name, path in OVERWORLD_LINKED_OUTPUTS
                    },
                },
            ],
        }
        completed = SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

        with mock.patch(
            "tools.overworld.control.subprocess.run", return_value=completed
        ):
            result = _roadmap_runtime_fixture(Path("test.nds"))

        self.assertTrue(result["passed"])
        self.assertEqual(
            set(result["identity"]),
            {
                "rom",
                "buildManifest",
                "debugDescriptor",
                *(item[1] for item in OVERWORLD_PRODUCT_OUTPUTS),
                *(item[0] for item in OVERWORLD_LINKED_OUTPUTS),
            },
        )
        for missing in (True, False):
            with self.subTest(main_queue_probe_missing=missing):
                invalid = copy.deepcopy(payload)
                if missing:
                    invalid["checks"] = [check for check in invalid["checks"]
                                         if check["name"] != "stock-main-queue-observation"]
                else:
                    next(check for check in invalid["checks"]
                         if check["name"] == "stock-main-queue-observation")["passed"] = False
                reply = SimpleNamespace(returncode=0, stdout=json.dumps(invalid), stderr="")
                with mock.patch("tools.overworld.control.subprocess.run", return_value=reply):
                    self.assertFalse(_roadmap_runtime_fixture(Path("test.nds"))["passed"])

        with self.subTest(verified_extra_linked_output=True):
            extra = copy.deepcopy(payload)
            linked = next(
                check for check in extra["checks"]
                if check["name"] == "runtime-linked-symbol-inputs"
            )["outputs"]
            linked["walkHelperObject"] = {
                "output": {
                    **file_record,
                    "path": "build/pokemon_move_history_overlay/overworld_walk_module.o",
                },
                "matched": True,
            }
            reply = SimpleNamespace(
                returncode=0,
                stdout=json.dumps(extra),
                stderr="",
            )
            with mock.patch(
                "tools.overworld.control.subprocess.run",
                return_value=reply,
            ):
                result = _roadmap_runtime_fixture(Path("test.nds"))
            self.assertTrue(result["passed"])
            self.assertNotIn("walkHelperObject", result["identity"])

    def test_roadmap_fixture_fails_closed_on_missing_identity(self) -> None:
        completed = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"schemaVersion": 1, "passed": True, "checks": []}),
            stderr="",
        )

        with mock.patch(
            "tools.overworld.control.subprocess.run", return_value=completed
        ):
            result = _roadmap_runtime_fixture(Path("test.nds"))

        self.assertFalse(result["passed"])
        self.assertIn("missing, stale, or inconsistent", result["error"])


class CommandExpansionTests(unittest.TestCase):
    def test_historical_command_matching_cannot_supply_shared_proof(self) -> None:
        check = {
            "proofLevel": "S4",
            "command": [
                "{python}", "scripts/owctl", "scenario", "run",
                "legacy.mounted-smoothness",
            ]
        }
        scenarios = {
            "wrong": {
                "status": "active",
                "proofLevel": "S4",
                "adapter": {
                    "claims": [
                        "natural-input",
                        "rendered-motion",
                        "control-release",
                    ],
                    "commands": [[
                        "{python}", "scripts/owctl", "scenario", "run",
                        "legacy.mankey-hops",
                    ]],
                },
            },
            "right": {
                "status": "active",
                "proofLevel": "S4",
                "adapter": {
                    "claims": [
                        "natural-input",
                        "live-actor-identity",
                        "rendered-motion",
                        "frame-pacing",
                        "engine-boundary",
                        "control-release",
                    ],
                    "commands": [[
                        "{python}", "scripts/owctl", "scenario", "run",
                        "legacy.mounted-smoothness",
                    ]],
                },
            },
        }

        self.assertEqual(
            _exact_runtime_scenarios(check, {"wrong"}, scenarios),
            set(),
        )
        self.assertEqual(
            _exact_runtime_scenarios(check, {"wrong", "right"}, scenarios),
            set(),
        )

    def test_direct_runtime_runner_cannot_report_accepted_proof(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts/owctl"), "scenario", "run", "legacy.mounted-smoothness",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("migration-pending", completed.stderr)

    def test_public_environment_token_cannot_forge_an_owctl_session(self) -> None:
        environment = dict(os.environ)
        environment["OWCTL_RUNTIME_PROOF_SESSION"] = "0" * 32
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts/owctl"), "scenario", "run", "legacy.mounted-smoothness",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("migration-pending", completed.stderr)

    def test_shared_scenario_dry_run_names_job_without_execution_or_proof(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(REPO / "scripts/owctl"), "scenario", "run",
             "devtools.actor-identity", "--dry-run", "--json"],
            cwd=REPO, check=True, capture_output=True, text=True,
        )
        document = json.loads(completed.stdout)
        self.assertEqual(document["test"], "devtools.actor-identity")
        self.assertEqual(document["executionMethod"], "shared-devtools")
        self.assertFalse(document["executed"])
        self.assertFalse(document["passed"])
        self.assertFalse(document["acceptedProof"])
        self.assertNotIn("commands", document)

    def test_explicit_evidence_cannot_bypass_runtime_claims(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts/owctl"),
                "scenario",
                "run",
                "chain.pause.counts-semantic-moves",
                "--evidence",
                "build/replayed-evidence.json",
                "--dry-run",
                "--json",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn(
            "evidence replay and manifest overrides are unavailable",
            completed.stderr,
        )

    def test_reusable_actor_output_requires_execution_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.bin"
            rom = root / "rom.nds"
            memory.write_bytes(b"")
            rom.write_bytes(b"rom")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO / "scripts/owctl"),
                    "actor",
                    "capture",
                    str(memory),
                    "--scenario-id",
                    "actor.host-contract",
                    "--rom",
                    str(rom),
                    "--seed",
                    "7",
                    "--output",
                    str(root / "evidence.json"),
                ],
                cwd=REPO,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("execution receipt", completed.stderr)

    def test_reusable_actor_output_rejects_incomplete_execution_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.bin"
            rom = root / "rom.nds"
            execution = root / "execution.json"
            memory.write_bytes(b"")
            rom.write_bytes(b"rom")
            execution.write_text(
                json.dumps(
                    build_execution_record(
                        scenario_id="actor.host-contract",
                        declared_events=scenario_document()["events"],
                        completed=False,
                        session="a" * 32,
                    )
                )
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO / "scripts/owctl"),
                    "actor",
                    "capture",
                    str(memory),
                    "--scenario-id",
                    "actor.host-contract",
                    "--rom",
                    str(rom),
                    "--seed",
                    "7",
                    "--execution",
                    str(execution),
                    "--output",
                    str(root / "evidence.json"),
                ],
                cwd=REPO,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("did not complete", completed.stderr)

    def test_doctor_checks_repository_headless_interpreter(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(REPO / "scripts/owctl"), "doctor", "--json"],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        document = json.loads(completed.stdout)
        emulator = next(
            check for check in document["checks"] if check["name"] == "emulator-python"
        )

        self.assertEqual(emulator["state"], "ok")
        self.assertIn(str(REPO / ".venv/bin/python3"), emulator["detail"])

    def test_run_manifest_records_repository_headless_interpreter(self) -> None:
        manifest = make_run_manifest(
            repo=REPO,
            kind="host-test",
            target="runtime-identity",
            proof_level="S0",
            cost_tier=0,
            scenario=None,
            commands=[],
            results=[],
            started_at="2026-09-01T00:00:00Z",
        )
        record = manifest["identity"]["emulator"]
        from tools.overworld.melonds_backend import REVISION
        expected = REVISION

        self.assertTrue(record["present"])
        self.assertEqual(record["pythonExecutable"], str(REPO / ".venv/bin/python3"))
        self.assertEqual(record["name"], "melonDS")
        self.assertIsNone(record["pythonPackage"])
        self.assertEqual(record["pythonPackageVersion"], expected)
        for _key, identity_name, _overlay_id, path in OVERWORLD_PRODUCT_OUTPUTS:
            self.assertEqual(
                manifest["identity"][identity_name]["path"],
                path.as_posix(),
            )
            self.assertTrue(manifest["identity"][identity_name]["present"])


if __name__ == "__main__":
    unittest.main()
