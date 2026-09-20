from copy import deepcopy
from pathlib import Path
import hashlib
import struct
import unittest

from tools.overworld.devtools_condition_probe import (
    BUFFER_BYTES,
    CASE_NAMES,
    CHANCE_SEED,
    PREPARED_BYTES,
    PREPARED_STRUCT_BYTES,
    RESULT_BYTES,
    SCRATCH_BYTES,
    buffer_layout,
    build_test_blob,
    candidates_bytes,
    context_bytes,
    fixture_patch_plan,
    handle_bytes,
    world_bytes,
)
from tools.overworld.devtools_condition_proof import (
    NAMES,
    condition_measurements,
    negative_controls,
)
from tools.overworld.test_devtools_condition_probe import source_blob


ROOT = Path(__file__).resolve().parents[2]


def target(kind, slot=0, generation=0):
    raw = bytearray(14)
    if kind == 2:
        raw[:12] = handle_bytes(slot, generation)
    raw[12] = kind
    return bytes(raw)


def state(active_until=0, cooldown_until=0, target_bytes=None,
          active=0, triggered=0):
    target_bytes = target_bytes or target(0)
    handle = struct.unpack_from("<6H", target_bytes)
    return struct.pack(
        "<IIHHHBB",
        active_until,
        cooldown_until,
        handle[0] if target_bytes[12] == 2 else 0,
        handle[1] if target_bytes[12] == 2 else 0,
        handle[4] if target_bytes[12] == 2 else 0,
        target_bytes[12],
        (1 if active else 0) | (2 if triggered else 0),
    )


def prepared(states, state_pointer):
    raw = bytearray(PREPARED_BYTES)
    raw[:12] = handle_bytes(0, 1)
    struct.pack_into("<I", raw, 12, state_pointer)
    struct.pack_into("<4B", raw, 16, 0, 1, 2, 3)
    for index, value in enumerate(states):
        start = PREPARED_STRUCT_BYTES + index * 16
        raw[start:start + 16] = value
    raw[48:52] = bytes((4, 1, 4, 0))
    return bytes(raw)


def entry(condition, application, target_bytes, active, truth, triggered):
    del condition, application, target_bytes
    return ((1 if active else 0)
            | (2 if truth else 0)
            | (4 if triggered else 0))


def scratch(entries):
    raw = bytearray(SCRATCH_BYTES)
    for index, value in enumerate(entries):
        raw[index] = value
    return bytes(raw)


def result(active, triggered, *, app1_target=None, app1_condition=501):
    raw = bytearray(RESULT_BYTES)
    struct.pack_into("<II", raw, 0, active, triggered)
    raw[8:22] = target(1)
    struct.pack_into("<H4B", raw, 22, 502, 2, 3, 503 & 0xff, 503 >> 8)
    struct.pack_into("<32H", raw, 28, *([0xFFFF] * 32))
    struct.pack_into("<H", raw, 28 + 2, app1_condition)
    struct.pack_into("<H", raw, 28 + 4, 502)
    struct.pack_into("<H", raw, 28 + 6, 503)
    for index in range(32):
        raw[92 + index * 14:92 + (index + 1) * 14] = target(0)
    raw[92 + 14:92 + 28] = app1_target or target(2, 2, 3)
    raw[92 + 28:92 + 42] = target(1)
    return bytes(raw)


def semantic_cases(state_pointer):
    actor1, actor2, actor2fresh = target(2, 1, 2), target(2, 2, 3), target(2, 2, 9)
    player, none = target(1), target(0)
    initial_states = [state(target_bytes=actor1, active=1),
                      state(target_bytes=actor2, active=1),
                      state(110, 105, player, 1, 1),
                      state(target_bytes=none, active=1)]
    initial_entries = [entry(500, 1, actor1, 1, 1, 1),
                       entry(501, 1, actor2, 1, 1, 1),
                       entry(502, 2, player, 1, 1, 1),
                       entry(503, 3, none, 1, 1, 1)]
    initial = (prepared(initial_states, state_pointer), scratch(initial_entries),
               result(0xE, 0xE))
    hold_entries = [entry(500, 1, actor1, 1, 1, 0),
                    entry(501, 1, actor2, 1, 1, 0),
                    entry(502, 2, player, 1, 0, 0),
                    entry(503, 3, none, 1, 1, 0)]
    hold = (prepared(initial_states, state_pointer), scratch(hold_entries), result(0xE, 0))
    blocked_entries = deepcopy(hold_entries)
    blocked_entries[2] = entry(502, 2, player, 1, 1, 0)
    blocked = (prepared(initial_states, state_pointer), scratch(blocked_entries), result(0xE, 0))
    retrigger_states = deepcopy(initial_states)
    retrigger_states[2] = state(115, 110, player, 1, 1)
    retrigger_entries = deepcopy(blocked_entries)
    retrigger_entries[2] = entry(502, 2, player, 1, 1, 1)
    retrigger = (prepared(retrigger_states, state_pointer), scratch(retrigger_entries), result(0xE, 0x4))
    stale_states = deepcopy(retrigger_states)
    stale_states[1] = state()
    stale_entries = [entry(500, 1, actor1, 1, 1, 0)]
    stale = (prepared(stale_states, state_pointer), scratch(stale_entries), bytes(RESULT_BYTES))
    fresh_states = deepcopy(retrigger_states)
    fresh_states[1] = state(target_bytes=actor2fresh, active=1)
    fresh_entries = [entry(500, 1, actor1, 1, 1, 0),
                     entry(501, 1, actor2fresh, 1, 1, 1),
                     entry(502, 2, player, 1, 1, 0),
                     entry(503, 3, none, 1, 1, 0)]
    fresh = (prepared(fresh_states, state_pointer), scratch(fresh_entries),
             result(0xE, 0x2, app1_target=actor2fresh))
    return [initial, hold, blocked, retrigger, stale, fresh, initial]


def fixture():
    source = source_blob()
    copied = build_test_blob(source)
    source_identity = {"size": len(source),
                       "sha256": hashlib.sha256(source).hexdigest()}
    test_identity = {"size": len(copied),
                     "sha256": hashlib.sha256(copied).hexdigest(),
                     "fixtureVersion": 2}
    patch_plan = fixture_patch_plan(source, copied)
    service = {
        "magic": 0x4342574F,
        "version": 8,
        "size": 24,
        "serviceAddress": 0x023C22A0,
        "prepareAddress": 0x023C2CD1,
        "evaluateAddress": 0x023C2DC5,
        "validateAddress": 0x023C2B59,
        "serviceSha256": "a" * 64,
        "prepareEntrySha256": "b" * 64,
        "evaluateEntrySha256": "c" * 64,
        "validateEntrySha256": "d" * 64,
    }
    addresses = {
        "allocate_work_memory": 0x0201AA8C,
        "prepare_conditions": 0x023C2CD0,
        "evaluate_conditions": 0x023C2DC4,
        "free": 0x0201AB0C,
    }
    oracle = {"sourceBlobIdentity": deepcopy(source_identity),
              "testBlobIdentity": deepcopy(test_identity),
              "fixturePlan": deepcopy(patch_plan),
              "serviceIdentity": deepcopy(service),
              "callAddresses": addresses}
    work, source_address = 0x02040000, 0x02020000
    trampoline, sp = 0x02220000, 0x027E0000
    layout = buffer_layout(len(source))["regions"]
    address = lambda name: work + layout[name]["offset"]
    state_pointer = address("prepared") + PREPARED_STRUCT_BYTES
    prepare_args = [source_address, len(source), address("context"),
                    address("subject"), address("prepared")]
    evaluate_args = [source_address, len(source), address("prepared"),
                     address("world"), address("candidates"), 2, CHANCE_SEED,
                     address("scratch"), address("result")]
    calls = []
    specifications = [
        ("allocate_work_memory", [11, BUFFER_BYTES], work),
        ("prepare_conditions", prepare_args, 0),
        *[("evaluate_conditions", evaluate_args, value)
          for value in (0, 0, 0, 0, 3, 0)],
        ("prepare_conditions", prepare_args, 0),
        ("evaluate_conditions", evaluate_args, 0),
        ("free", [work], 128),
    ]
    for routine, arguments, return_value in specifications:
        calls.append({
            "routine": routine,
            "address": addresses[routine],
            "requestedArguments": arguments[:],
            "entryArguments": arguments[:],
            "entryStack": sp,
            "entryLink": trampoline + 0x4C,
            "entryCpsr": 63,
            "entryBoundary": "native-trampoline-BLX-entry",
            "returnValue": return_value,
        })
    worlds = [world_bytes(100), world_bytes(103, player_x=30),
              world_bytes(104), world_bytes(105),
              world_bytes(106, follower_generation=9),
              world_bytes(107, follower_generation=9), world_bytes(100)]
    receipts = []
    statuses = [0, 0, 0, 0, 3, 0, 0]
    for index, (name, world, status, raw) in enumerate(
            zip(CASE_NAMES, worlds, statuses, semantic_cases(state_pointer))):
        prepared_raw, scratch_raw, result_raw = raw
        receipts.append({
            "name": name,
            "subjectRoleLabel": "WILD" if index < 6 else "FOLLOWER",
            "status": status,
            "chanceSeed": CHANCE_SEED,
            "contextHex": context_bytes().hex(),
            "subjectHex": handle_bytes(0, 1).hex(),
            "worldHex": world.hex(),
            "candidatesHex": candidates_bytes().hex(),
            "preparedHex": prepared_raw.hex(),
            "scratchHex": scratch_raw.hex(),
            "resultHex": result_raw.hex(),
            "dispatchClock": {"frame": 10, "nativeCycle": 25 + index},
            "returnClock": {"frame": 10, "nativeCycle": 25 + index},
        })
    prepared_zero = bytearray(PREPARED_BYTES)
    prepared_zero[:12] = handle_bytes(0, 1)
    struct.pack_into("<I", prepared_zero, 12, state_pointer)
    struct.pack_into("<4B", prepared_zero, 16, 0, 1, 2, 3)
    prepared_zero[48:52] = bytes((4, 1, 4, 0))
    value = {
        "completed": True,
        "acceptedProof": False,
        "sourceBlobIdentity": deepcopy(source_identity),
        "testBlobIdentity": deepcopy(test_identity),
        "serviceIdentity": deepcopy(service),
        "fixture": {**deepcopy(patch_plan), "patched": True,
                    "intactBeforeRestore": True, "restored": True},
        "layout": buffer_layout(len(source)),
        "prepareReceipts": [
            {"subjectRoleLabel": role, "status": 0,
             "preparedHex": bytes(prepared_zero).hex(),
             "dispatchClock": {"frame": 10, "nativeCycle": cycle},
             "returnClock": {"frame": 10, "nativeCycle": cycle}}
            for role, cycle in (("WILD", 24), ("FOLLOWER", 31))
        ],
        "receipts": receipts,
        "allocation": {"heapId": 11, "bytes": BUFFER_BYTES,
                       "pointer": work, "released": True},
        "scope": "controlled native condition-service calls",
    }
    snapshot = {"frame": 12, "nativeCycle": 34}
    receipt = {
        "preparedOnly": True,
        "acceptedProof": False,
        "boundary": "native-field-command-trampoline",
        "firstBadCheckpoint": None,
        "firstInvalidThreadSwitch": None,
        "nativeHeapAdaptation": [],
        "calls": calls,
        "value": value,
        "naturalDiscovery": {
            "blobAddress": source_address,
            "blobSize": len(source),
            "fieldPointer": 0x02230000,
            "heapGeneration": 0,
            "status": 0,
            "requestHex": bytes(44).hex(),
            "entryNativeCycle": 20,
            "returnNativeCycle": 20,
        },
        "trampoline": {
            "address": trampoline,
            "bytes": 1536,
            "heapId": 11,
            "lifetime": "field-system-heap11",
            "fieldPointer": 0x02230000,
            "heapGeneration": 0,
            "codeSha256": "e" * 64,
        },
        "stackOwnership": {
            "callSp": sp,
            "hostRestoredFrameBytes": 0,
            "nativeFrameBytes": 80,
            "scratchBytes": 268,
            "thread": {"mode": 31, "irqDepth": 0,
                       "stackTop": sp - 1000, "stackBottom": sp + 1000},
        },
        "setupBoundary": {"eventsDrained": True, "traceSequences": {},
                          "frame": 12, "nativeCycle": 34,
                          "endpointNativeCycle": 34},
        "snapshot": snapshot,
    }
    test = {
        "mode": "prepared",
        "subjects": [],
        "setup": [],
        "actions": [{"id": "probe", "op": "condition.probe", "args": {}}],
    }
    rows = [
        {"phase": "setup", "initialSnapshot": {"frame": 10, "nativeCycle": 23}},
        {"phase": "observe", "action": "probe", "command": "condition.probe",
         "receipt": receipt, "snapshot": snapshot},
    ]
    return test, rows, oracle


class ConditionProofTests(unittest.TestCase):
    def check(self, test, rows, oracle):
        return condition_measurements(test, iter(rows), {}, ROOT, oracle=oracle)

    def test_fixed_cases_and_all_registered_measurements(self):
        test, rows, oracle = fixture()
        before = deepcopy((test, rows, oracle))
        result = self.check(test, rows, oracle)
        self.assertEqual([item["name"] for item in result["measurements"]],
                         list(NAMES))
        self.assertEqual(result["caseProof"]["caseNames"], list(CASE_NAMES))
        self.assertEqual(result["observedFrameUnit"],
                         "native-condition-service-cycles")
        self.assertNotIn("acceptedProof", result)
        self.assertEqual((test, rows, oracle), before)

    def test_damaged_native_evidence_cannot_authorize_service_semantics(self):
        mutations = {
            "service": lambda value, receipt: value["serviceIdentity"].update(
                evaluateEntrySha256="f" * 64),
            "blob": lambda value, receipt: value["sourceBlobIdentity"].update(
                sha256="f" * 64),
            "free": lambda value, receipt: receipt["calls"].pop(),
            "argument": lambda value, receipt: receipt["calls"][2]["entryArguments"].__setitem__(8, 0),
            "case": lambda value, receipt: value["receipts"].pop(),
            "timer": lambda value, receipt: value["receipts"][3].update(
                preparedHex="00" * PREPARED_BYTES),
            "target": lambda value, receipt: value["receipts"][5].update(
                scratchHex="00" * SCRATCH_BYTES),
            "role": lambda value, receipt: value["receipts"][-1].update(
                resultHex="00" * RESULT_BYTES),
        }
        for name, mutate in mutations.items():
            test, rows, oracle = fixture()
            mutate(rows[1]["receipt"]["value"], rows[1]["receipt"])
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.check(test, rows, oracle)

    def test_eleven_recorded_data_controls_reject_for_exact_reasons(self):
        test, rows, oracle = fixture()
        before = deepcopy((test, rows, oracle))
        result = negative_controls(test, iter(rows), {}, ROOT, oracle=oracle)
        self.assertEqual(len(result["controls"]), 11)
        self.assertTrue(all(item["rejected"]
                            for item in result["controls"].values()))
        self.assertIn("not live role callers", result["scope"])
        self.assertEqual((test, rows, oracle), before)


if __name__ == "__main__":
    unittest.main()
