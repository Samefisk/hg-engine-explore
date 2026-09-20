"""Controller proof for the packaged condition service.

All semantic expectations below come from the fixed scenario contract.  They
are not computed by the product evaluator.  Package identities and linked call
addresses are supplied by the controller oracle.
"""
from copy import deepcopy
import struct

from tools.overworld.devtools_condition_probe import (
    BUFFER_BYTES,
    CASE_NAMES,
    CHANCE_SEED,
    CONTEXT_BYTES,
    HANDLE_BYTES,
    PREPARED_BYTES,
    PREPARED_STRUCT_BYTES,
    RESULT_BYTES,
    SCRATCH_BYTES,
    WORLD_BYTES,
    buffer_layout,
    candidates_bytes,
    context_bytes,
    handle_bytes,
    world_bytes,
)


NAMES = (
    "packaged-condition-service-entry",
    "authenticated-condition-source-blob",
    "condition-overlap-last-wins",
    "conditional-application-stacking",
    "timed-hold-cooldown-retrigger",
    "condition-player-target",
    "condition-actor-target-lifecycle",
    "copied-subject-role-parity",
    "owned-condition-buffer-cleanup",
    "condition-native-call-boundaries",
)

CONDITION_IDS = (500, 501, 502, 503)
CONDITION_APPLICATIONS = (1, 1, 2, 3)


def require(ok, reason):
    if not ok:
        raise ValueError("condition proof: " + reason)


def integer(value, low=0, high=0xFFFFFFFF):
    require(type(value) is int and low <= value <= high, "invalid integer")
    return value


def pointer(value, size=4):
    integer(value, 0x02000000, 0x02400000 - size)
    require(value % 4 == 0, "unaligned pointer")
    return value


def raw_hex(value, size):
    require(type(value) is str and len(value) == size * 2,
            "invalid byte receipt")
    try:
        raw = bytes.fromhex(value)
    except ValueError as error:
        raise ValueError("condition proof: invalid byte receipt") from error
    require(len(raw) == size, "invalid byte receipt")
    return raw


def clock(value):
    require(isinstance(value, dict)
            and {"frame", "nativeCycle"}.issubset(value),
            "missing call clock")
    return integer(value["frame"]), integer(value["nativeCycle"], 1)


def _target(raw, offset):
    handle = struct.unpack_from("<6H", raw, offset)
    return {"handle": handle, "kind": raw[offset + 12],
            "reserved": raw[offset + 13]}


def _result(raw):
    return {
        "active": struct.unpack_from("<I", raw, 0)[0],
        "triggered": struct.unpack_from("<I", raw, 4)[0],
        "resolvedTarget": _target(raw, 8),
        "resolvedCondition": struct.unpack_from("<H", raw, 22)[0],
        "targetSource": raw[24],
        "winningSource": raw[25],
        "winningId": struct.unpack_from("<H", raw, 26)[0],
        "winningIds": struct.unpack_from("<32H", raw, 28),
        "targets": tuple(_target(raw, 92 + index * 14) for index in range(32)),
    }


def _state(prepared, index):
    offset = PREPARED_STRUCT_BYTES + index * 16
    slot, generation, encounter = struct.unpack_from("<3H", prepared, offset + 8)
    kind = prepared[offset + 14]
    flags = prepared[offset + 15]
    return {
        "activeUntil": struct.unpack_from("<I", prepared, offset)[0],
        "cooldownUntil": struct.unpack_from("<I", prepared, offset + 4)[0],
        "target": {"handle": (slot, generation, 0, 0, encounter, 0),
                   "kind": kind, "reserved": 0},
        "active": flags & 1,
        "hasTriggered": (flags >> 1) & 1,
    }


def _entry(prepared, scratch, world, index):
    state = _state(prepared, index)
    target = state["target"]
    if target["kind"] == 2:
        actor_count = world[29]
        stored = target["handle"]
        matches = []
        for actor_index in range(actor_count):
            offset = 30 + actor_index * 20
            handle = struct.unpack_from("<6H", world, offset)
            if (world[offset + 16] != 0
                    and (handle[0], handle[1], handle[4])
                    == (stored[0], stored[1], stored[4])):
                matches.append(handle)
        require(len(matches) == 1,
                "stored condition target does not identify one live actor")
        target = {"handle": matches[0], "kind": 2, "reserved": 0}
    flags = scratch[index]
    return {
        "target": target,
        "conditionId": CONDITION_IDS[index],
        "application": CONDITION_APPLICATIONS[index],
        "active": 1 if flags & 1 else 0,
        "truth": 1 if flags & 2 else 0,
        "triggered": 1 if flags & 4 else 0,
    }


def condition_measurements(test, rows, record, repo, *, oracle):
    try:
        return _measure(test, rows, oracle)
    except (KeyError, TypeError, IndexError, AttributeError, struct.error) as error:
        raise ValueError("condition proof: missing or malformed evidence") from error


def _measure(test, rows, oracle):
    require(test.get("mode") == "prepared" and not test.get("subjects")
            and not test.get("setup"), "subjectless prepared scope differs")
    require(len(test.get("actions", [])) == 1
            and test["actions"][0].get("op") == "condition.probe"
            and test["actions"][0].get("args") == {},
            "exactly one authored condition probe required")
    saved = []
    for row in rows:
        require(len(saved) < 3 and isinstance(row, dict),
                "unbounded or invalid raw stream")
        saved.append(row)
    require(len(saved) == 2 and "initialSnapshot" in saved[0]
            and saved[1].get("command") == "condition.probe"
            and saved[1].get("phase") == "observe"
            and saved[1].get("action") == test["actions"][0]["id"],
            "native probe is missing")
    start = clock(saved[0]["initialSnapshot"])
    row = saved[1]
    receipt = row["receipt"]
    require(receipt.get("preparedOnly") is True
            and receipt.get("acceptedProof") is False
            and receipt.get("boundary") == "native-field-command-trampoline"
            and receipt.get("firstBadCheckpoint") is None
            and receipt.get("firstInvalidThreadSwitch") is None
            and receipt.get("nativeHeapAdaptation") == [],
            "native bridge scope differs")
    snapshot = row["snapshot"]
    end = clock(snapshot)
    if "snapshot" in receipt:
        require(receipt["snapshot"] == snapshot, "worker endpoint differs")
    boundary = receipt["setupBoundary"]
    require(boundary.get("eventsDrained") is True and clock(boundary) == end
            and integer(boundary["endpointNativeCycle"], 1) >= end[1]
            and start[0] <= end[0] and start[1] <= end[1]
            and isinstance(boundary.get("traceSequences"), dict),
            "setup boundary clocks differ")

    value = receipt["value"]
    require(value.get("completed") is True
            and value.get("acceptedProof") is False,
            "condition probe did not complete")
    source_identity = oracle["sourceBlobIdentity"]
    test_identity = oracle["testBlobIdentity"]
    require(value.get("sourceBlobIdentity") == source_identity,
            "source blob identity differs")
    require(value.get("testBlobIdentity") == test_identity,
            "temporary test blob identity differs")
    require(value.get("serviceIdentity") == oracle["serviceIdentity"],
            "service identity differs")
    require(value.get("fixture") == {
                **oracle["fixturePlan"],
                "patched": True,
                "intactBeforeRestore": True,
                "restored": True,
            }, "temporary fixture was not restored")
    layout = buffer_layout(source_identity["size"])
    require(value.get("layout") == layout, "owned buffer layout differs")
    allocation = value["allocation"]
    require(allocation.get("heapId") == 11
            and allocation.get("bytes") == BUFFER_BYTES
            and allocation.get("released") is True,
            "owned condition buffer was not released")
    work = pointer(allocation["pointer"], BUFFER_BYTES)

    natural = receipt["naturalDiscovery"]
    source = pointer(natural["blobAddress"], source_identity["size"])
    require(natural.get("status") == 0
            and natural.get("blobSize") == source_identity["size"],
            "natural condition blob discovery differs")
    require(work + BUFFER_BYTES <= source
            or source + source_identity["size"] <= work,
            "owned buffer overlaps source blob")

    trampoline = receipt["trampoline"]
    trampoline_address = pointer(trampoline["address"], 1536)
    require(trampoline.get("bytes") == 1536
            and trampoline.get("heapId") == 11
            and trampoline.get("lifetime") == "field-system-heap11"
            and trampoline["fieldPointer"] == pointer(natural["fieldPointer"])
            and trampoline["heapGeneration"] == integer(natural["heapGeneration"])
            and (work + BUFFER_BYTES <= trampoline_address
                 or trampoline_address + 1536 <= work),
            "native trampoline owner differs")
    raw_hex(trampoline["codeSha256"], 32)
    stack = receipt["stackOwnership"]
    sp = integer(stack["callSp"], 0x02000000, 0x02800000 - 32)
    thread = stack["thread"]
    require(sp % 8 == 0 and stack["hostRestoredFrameBytes"] == 0
            and stack["nativeFrameBytes"] == 80
            and stack["scratchBytes"] == 268
            and thread["mode"] == 31 and thread["irqDepth"] == 0
            and integer(thread["stackTop"]) < sp
            < integer(thread["stackBottom"]) - 32,
            "native stack owner differs")

    regions = layout["regions"]
    address = lambda name: work + regions[name]["offset"]
    prepare_args = [source, source_identity["size"],
                    address("context"), address("subject"), address("prepared")]
    evaluate_args = [source, source_identity["size"],
                     address("prepared"), address("world"), address("candidates"),
                     2, CHANCE_SEED, address("scratch"), address("result")]
    expected_calls = [
        ("allocate_work_memory", [11, BUFFER_BYTES], work),
        ("prepare_conditions", prepare_args, 0),
        *[("evaluate_conditions", evaluate_args, status)
          for status in (0, 0, 0, 0, 3, 0)],
        ("prepare_conditions", prepare_args, 0),
        ("evaluate_conditions", evaluate_args, 0),
        ("free", [work], None),
    ]
    calls = receipt["calls"]
    require(isinstance(calls, list) and len(calls) == len(expected_calls),
            "exact native call list differs")
    for call, (routine, arguments, result) in zip(calls, expected_calls):
        require(call.get("routine") == routine
                and call.get("address") == oracle["callAddresses"][routine],
                "packaged native entry differs")
        require(call.get("requestedArguments") == arguments
                and call.get("entryArguments") == arguments,
                "native call arguments differ")
        require(call.get("entryStack") == sp
                and call.get("entryLink") == trampoline_address + 0x4C
                and integer(call.get("entryCpsr")) & 0x3F == 0x3F
                and call.get("entryBoundary") == "native-trampoline-BLX-entry",
                "native call frame differs")
        integer(call.get("returnValue"))
        require(result is None or call["returnValue"] == result,
                "native call return differs")

    prepares = value["prepareReceipts"]
    cases = value["receipts"]
    require(isinstance(prepares, list) and len(prepares) == 2
            and [item.get("subjectRoleLabel") for item in prepares]
                == ["WILD", "FOLLOWER"]
            and all(item.get("status") == 0 for item in prepares),
            "condition prepare receipts differ")
    expected_states = address("prepared") + PREPARED_STRUCT_BYTES
    for item in prepares:
        prepared = raw_hex(item.get("preparedHex"), PREPARED_BYTES)
        require(struct.unpack_from("<I", prepared, 12)[0] == expected_states
                and prepared[16:20] == bytes((0, 1, 2, 3))
                and prepared[48:52] == bytes((4, 1, 4, 0)),
                "condition prepared storage differs")
    require(isinstance(cases, list) and len(cases) == len(CASE_NAMES)
            and tuple(item.get("name") for item in cases) == CASE_NAMES
            and [item.get("subjectRoleLabel") for item in cases]
                == ["WILD"] * 6 + ["FOLLOWER"]
            and [item.get("status") for item in cases]
                == [0, 0, 0, 0, 3, 0, 0],
            "condition status sequence differs")
    worlds = (
        world_bytes(100),
        world_bytes(103, player_x=30),
        world_bytes(104),
        world_bytes(105),
        world_bytes(106, follower_generation=9),
        world_bytes(107, follower_generation=9),
        world_bytes(100),
    )
    prepared_raw = []
    scratch_raw = []
    result_raw = []
    cycles = set()
    previous = start
    for case, world in zip(cases, worlds):
        require(case.get("chanceSeed") == CHANCE_SEED
                and raw_hex(case.get("contextHex"), CONTEXT_BYTES) == context_bytes()
                and raw_hex(case.get("subjectHex"), HANDLE_BYTES) == handle_bytes(0, 1)
                and raw_hex(case.get("worldHex"), WORLD_BYTES) == world
                and raw_hex(case.get("candidatesHex"), 32) == candidates_bytes(),
                "fixed condition inputs differ")
        prepared = raw_hex(case.get("preparedHex"), PREPARED_BYTES)
        require(struct.unpack_from("<I", prepared, 12)[0] == expected_states
                and prepared[16:20] == bytes((0, 1, 2, 3))
                and prepared[48:52] == bytes((4, 1, 4, 0)),
                "condition prepared storage differs")
        prepared_raw.append(prepared)
        scratch_raw.append(raw_hex(case.get("scratchHex"), SCRATCH_BYTES))
        result_raw.append(raw_hex(case.get("resultHex"), RESULT_BYTES))
        dispatched, returned = clock(case["dispatchClock"]), clock(case["returnClock"])
        require(previous[0] <= dispatched[0] <= returned[0] <= end[0]
                and previous[1] <= dispatched[1] <= returned[1] <= end[1]
                and returned[1] - dispatched[1] <= 180,
                "condition call clocks differ")
        cycles.update(range(dispatched[1], returned[1] + 1))
        previous = returned

    initial = _result(result_raw[0])
    entries = [
        _entry(prepared_raw[0], scratch_raw[0], worlds[0], index)
        for index in range(4)
    ]
    require(initial["active"] == 0xE and initial["triggered"] == 0xE
            and initial["winningIds"][2:4] == (502, 503)
            and initial["winningSource"] == 3 and initial["winningId"] == 503,
            "conditional application stacking differs")
    require(entries[0]["target"]["kind"] == 2
            and entries[0]["target"]["handle"][:2] == (1, 2)
            and entries[1]["target"]["kind"] == 2
            and entries[1]["target"]["handle"][:2] == (2, 3)
            and initial["targets"][1] == entries[1]["target"]
            and initial["winningIds"][1] == 501,
            "overlap last-wins differs")
    require(initial["resolvedTarget"]["kind"] == 1
            and initial["resolvedCondition"] == 502
            and initial["targetSource"] == 2
            and initial["targets"][2]["kind"] == 1,
            "player target differs")

    hold, blocked, retrigger = (_entry(
                                    prepared_raw[index],
                                    scratch_raw[index],
                                    worlds[index],
                                    2)
                                for index in (1, 2, 3))
    hold_state, blocked_state, retrigger_state = (
        _state(prepared_raw[index], 2) for index in (1, 2, 3))
    require((hold["active"], hold["truth"], hold["triggered"])
                == (1, 0, 0)
            and (blocked["active"], blocked["truth"], blocked["triggered"])
                == (1, 1, 0)
            and (retrigger["active"], retrigger["truth"], retrigger["triggered"])
                == (1, 1, 1)
            and (hold_state["activeUntil"], hold_state["cooldownUntil"])
                == (110, 105)
            and (blocked_state["activeUntil"], blocked_state["cooldownUntil"])
                == (110, 105)
            and (retrigger_state["activeUntil"], retrigger_state["cooldownUntil"])
                == (115, 110)
            and _result(result_raw[3])["triggered"] == 0x4,
            "timed retrigger differs")

    stale_state = _state(prepared_raw[4], 1)
    fresh_entry = _entry(prepared_raw[5], scratch_raw[5], worlds[5], 1)
    fresh_result = _result(result_raw[5])
    require(stale_state["active"] == 0
            and stale_state["target"]["kind"] == 0,
            "stale actor target differs")
    require((fresh_entry["active"], fresh_entry["truth"],
             fresh_entry["triggered"]) == (1, 1, 1)
            and fresh_entry["target"]["kind"] == 2
            and fresh_entry["target"]["handle"][:2] == (2, 9)
            and fresh_result["targets"][1] == fresh_entry["target"]
            and fresh_result["winningIds"][1] == 501,
            "fresh actor target differs")

    require(all(cases[-1][key] == cases[0][key] for key in (
                "status", "chanceSeed", "contextHex", "subjectHex",
                "worldHex", "candidatesHex", "preparedHex", "scratchHex",
                "resultHex")),
            "copied subject-role parity differs")
    require(1 <= len(cycles) <= 1260,
            "condition native observation budget differs")
    values = [1] * len(NAMES)
    return {
        "measurements": [
            {"claim": "profile-resolution", "name": name, "value": value,
             "operator": "eq", "expected": 1}
            for name, value in zip(NAMES, values)
        ],
        "caseProof": {
            "caseCount": len(cases),
            "caseNames": list(CASE_NAMES),
            "copiedSubjectRoles": ["WILD", "FOLLOWER"],
            "acceptedProof": False,
            "scope": value["scope"],
        },
        "observedFrames": len(cycles),
        "observedFrameUnit": "native-condition-service-cycles",
        "completedGameFrames": (cases[-1]["returnClock"]["frame"]
                                - cases[0]["dispatchClock"]["frame"]),
    }


def negative_controls(test, rows, record, repo, *, oracle):
    saved = []
    for row in rows:
        require(len(saved) < 3, "unbounded control stream")
        saved.append(deepcopy(row))
    condition_measurements(test, saved, record, repo, oracle=oracle)
    expected = {
        "missing-probe": "condition proof: native probe is missing",
        "wrong-service-hash": "condition proof: service identity differs",
        "wrong-source-hash": "condition proof: source blob identity differs",
        "unrestored-fixture": "condition proof: temporary fixture was not restored",
        "missing-free": "condition proof: exact native call list differs",
        "wrong-ninth-argument": "condition proof: native call arguments differ",
        "wrong-overlap-winner": "condition proof: overlap last-wins differs",
        "wrong-retrigger-timer": "condition proof: timed retrigger differs",
        "wrong-stale-status": "condition proof: condition status sequence differs",
        "wrong-fresh-target": "condition proof: fresh actor target differs",
        "wrong-role-parity": "condition proof: copied subject-role parity differs",
    }
    controls = {}
    for name, reason in expected.items():
        changed = deepcopy(saved)
        if name == "missing-probe":
            changed[1] = {"phase": "observe",
                          "boundarySnapshot": changed[1]["snapshot"]}
        else:
            receipt = changed[1]["receipt"]
            value = receipt["value"]
            if name == "wrong-service-hash":
                value["serviceIdentity"]["evaluateEntrySha256"] = "ff" * 32
            elif name == "wrong-source-hash":
                value["sourceBlobIdentity"]["sha256"] = "ff" * 32
            elif name == "unrestored-fixture":
                value["fixture"]["restored"] = False
            elif name == "missing-free":
                receipt["calls"].pop()
            elif name == "wrong-ninth-argument":
                receipt["calls"][2]["entryArguments"][8] ^= 4
            elif name == "wrong-overlap-winner":
                raw = bytearray.fromhex(value["receipts"][0]["resultHex"])
                struct.pack_into("<H", raw, 30, 500)
                value["receipts"][0]["resultHex"] = raw.hex()
            elif name == "wrong-retrigger-timer":
                raw = bytearray.fromhex(value["receipts"][3]["preparedHex"])
                struct.pack_into(
                    "<I", raw, PREPARED_STRUCT_BYTES + 2 * 16, 114)
                value["receipts"][3]["preparedHex"] = raw.hex()
            elif name == "wrong-stale-status":
                value["receipts"][4]["status"] = 0
            elif name == "wrong-fresh-target":
                raw = bytearray.fromhex(value["receipts"][5]["resultHex"])
                struct.pack_into("<H", raw, 92 + 14 + 2, 8)
                value["receipts"][5]["resultHex"] = raw.hex()
            else:
                raw = bytearray.fromhex(value["receipts"][-1]["resultHex"])
                raw[-1] ^= 1
                value["receipts"][-1]["resultHex"] = raw.hex()
        try:
            condition_measurements(test, changed, record, repo, oracle=oracle)
        except ValueError as error:
            require(str(error) == reason,
                    name + " rejected for unrelated reason: " + str(error))
            controls[name] = {"rejected": True, "reason": str(error)}
        else:
            raise ValueError("condition proof: evaluator control was accepted: " + name)
    return {"scope": ("recorded-data evaluator controls only; not live role "
                      "callers or catalog-restoration execution"),
            "controls": controls}
