"""Pure deployment-parity check; the controller supplies authenticated inputs.

`oracle` must be built from the current package/linked code and a fresh host
resolver run, never from the recorded native results. The parent controller
owns ROM/source/session identity and core cleanup checks. No actor credit.
"""
from copy import deepcopy
import hashlib
import json

from tools.overworld.devtools_resolver_parity import (
    CASE_NAMES,
    compare_resolver_parity,
    raw_hex,
)
from tools.overworld.devtools_resolver_probe import BUFFER_BYTES, REQUEST, RESULT, TRACE
from tools.overworld.devtools_raw_chunk import validate_raw_chunk

NAMES = ("packaged-resolver-entry", "packaged-behavior-blob", "status-parity",
         "profile-byte-parity", "primitive-byte-parity", "fingerprint-parity",
         "resolution-metadata-parity", "provenance-parity")


def require(ok, reason):
    if not ok:
        raise ValueError("resolver proof: " + reason)


def integer(value, low=0, high=0xFFFFFFFF):
    require(type(value) is int and low <= value <= high, "invalid integer")
    return value


def pointer(value, size=4):
    integer(value, 0x02000000, 0x02400000-size)
    require(value % 4 == 0, "unaligned owner pointer")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def clock(value):
    require(isinstance(value, dict), "missing clock")
    return integer(value.get("frame")), integer(value.get("nativeCycle"), 1)


def resolver_measurements(test, rows, record, repo, *, oracle):
    """Return eight registry rows and caseProof, never acceptedProof.

    Oracle keys: vectors, hostResults, blobIdentity, serviceIdentity,
    callAddresses (authenticated even allocate_work_memory/resolve_behavior/free).
    Rows are the shared job stream, not the manual event-details wrapper.
    """
    try:
        return _measure(test, rows, record, oracle)
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError("resolver proof: missing or malformed evidence") from error


def negative_controls(test, rows, record, repo, *, oracle):
    """Copied-data evaluator controls; never live observer-fault proof.

    Prove the original stream first. Each mutation uses the unchanged checker
    and controller oracle, and must fail for its specific changed evidence.
    """
    saved = []
    for row in rows:
        require(len(saved) < 4000, "unbounded control stream")
        saved.append(deepcopy(row))
    resolver_measurements(test, saved, record, repo, oracle=oracle)
    index = next(i for i, row in enumerate(saved) if row.get("command") == "resolver.probe")
    expected = {
        "missing-probe": "resolver proof: native probe is missing",
        "wrong-result-byte": "resolver parity: full result bytes differ",
        "wrong-ordered-trace": "resolver parity: ordered provenance differs",
        "missing-free": "resolver proof: exact allocation/resolves/free required",
        "wrong-entry-argument": "resolver proof: native call or entry arguments differ",
        "wrong-service-hash": "resolver parity: native blob or service identity differs",
        "wrong-blob-hash": "resolver parity: native blob or service identity differs",
    }
    controls = {}
    for name, reason in expected.items():
        changed = deepcopy(saved)
        receipt = changed[index]["receipt"]
        native = receipt["value"]["receipts"][0]
        if name == "missing-probe":
            # Retain endpoint clocks so later neutral waits remain coherent;
            # only the required command/native evidence is removed.
            changed[index] = {"phase": changed[index]["phase"],
                              "boundarySnapshot": changed[index]["snapshot"]}
        elif name == "wrong-result-byte":
            raw = bytearray.fromhex(native["resultHex"])
            raw[0] ^= 1
            native["resultHex"] = raw.hex()
        elif name == "wrong-ordered-trace":
            trace = native["trace"]
            pair = next(((a,b) for a in range(len(trace)) for b in range(a+1,len(trace))
                         if trace[a] != trace[b]), None)
            require(pair is not None, "ordered-trace control needs two distinct steps")
            a,b = pair
            trace[a],trace[b] = trace[b],trace[a]
        elif name == "missing-free":
            receipt["calls"].pop()
        elif name == "wrong-entry-argument":
            receipt["calls"][1]["entryArguments"][0] ^= 4
        else:
            identity = native["serviceIdentity" if name == "wrong-service-hash" else "blobIdentity"]
            field = "entrySha256" if name == "wrong-service-hash" else "sha256"
            raw = bytearray.fromhex(identity[field]); raw[0] ^= 1
            identity[field] = raw.hex()
        try:
            resolver_measurements(test, changed, record, repo, oracle=oracle)
        except ValueError as error:
            require(str(error) == reason, name + " rejected for unrelated reason: " + str(error))
            controls[name] = {"rejected": True, "reason": str(error)}
        else:
            raise ValueError("resolver proof: evaluator control was accepted: " + name)
    return {"scope": "copied-data evaluator controls only; not live observer faults", "controls": controls}


def _measure(test, rows, record, oracle):
    require(test.get("mode") == "prepared", "prepared deployment scope required")
    actions = {a["id"]: a for a in test["setup"] + test["actions"]}
    phases = {a["id"]: phase for phase, values in (("setup", test["setup"]), ("observe", test["actions"]))
              for a in values}
    require(len(actions) == len(test["setup"])+len(test["actions"]), "duplicate authored action")
    require(sum(a["op"] == "resolver.probe" for a in actions.values()) == 1,
            "exactly one authored probe required")
    require(all(a["op"] in ("resolver.probe", "wait", "assert") for a in actions.values()),
            "unrelated action or mutation")
    probe_row = None
    latest = None
    for count, row in enumerate(rows, 1):
        require(count <= 4000 and isinstance(row, dict), "unbounded or invalid raw stream")
        if "initialSnapshot" in row or "boundarySnapshot" in row:
            require("command" not in row and "receipt" not in row, "mixed boundary record")
            latest = row.get("initialSnapshot", row.get("boundarySnapshot"))
            clock(latest)
            continue
        action = actions[row["action"]]
        require(row.get("phase") == phases[row["action"]], "unexpected command phase")
        command = row.get("command")
        if command is None:
            require(action["op"] == "wait" and latest is not None, "only neutral wait chunks allowed")
            validated = validate_raw_chunk(row, latest)
            latest = validated[-1][0]
            continue
        require(command in ("resolver.probe", "wait", "assert"), "unknown raw command")
        require(command == action["op"], "raw command differs from authored action")
        if command == "resolver.probe":
            require(probe_row is None and action.get("args") == {} and latest is not None,
                    "duplicate probe or missing initial boundary")
            probe_row = row
            start = clock(latest)
        latest = row["snapshot"]
        clock(latest)
    require(probe_row is not None, "native probe is missing")
    receipt = probe_row["receipt"]
    require(receipt.get("preparedOnly") is True and receipt.get("acceptedProof") is False
            and receipt.get("boundary") == "native-field-command-trampoline", "wrong bridge scope")
    require(receipt["firstBadCheckpoint"] is None and receipt["firstInvalidThreadSwitch"] is None,
            "native bridge fault")
    require(receipt["nativeHeapAdaptation"] == [], "unexpected party heap adaptation")
    value = receipt["value"]
    require(value.get("completed") is True and value.get("acceptedProof") is False, "probe did not complete")
    allocation = value["allocation"]
    require(allocation.get("released") is True and allocation.get("heapId") == 11
            and allocation.get("bytes") == BUFFER_BYTES,
            "owned allocation was not released")
    work = pointer(allocation["pointer"], BUFFER_BYTES)
    natural = receipt["naturalDiscovery"]
    blob = oracle["blobIdentity"]
    source = pointer(natural["blobAddress"], integer(blob["size"], 1, 1024*1024))
    require(natural.get("status") == 0 and type(natural.get("status")) is int
            and natural["blobSize"] == blob["size"], "natural resolver discovery differs")
    raw_hex(natural["requestHex"], 44)
    require(work + BUFFER_BYTES <= source or source + blob["size"] <= work,
            "source overlaps work buffer")
    trampoline = receipt["trampoline"]
    trampoline_address = pointer(trampoline["address"], 1536)
    require(trampoline.get("bytes") == 1536 and trampoline.get("heapId") == 11
            and trampoline.get("lifetime") == "field-system-heap11"
            and trampoline["fieldPointer"] == pointer(natural["fieldPointer"])
            and trampoline["heapGeneration"] == integer(natural["heapGeneration"]), "stale field/heap owner")
    raw_hex(trampoline["codeSha256"], 32)
    require(work + BUFFER_BYTES <= trampoline_address
            or trampoline_address + 1536 <= work, "work overlaps trampoline")
    stack = receipt["stackOwnership"]
    sp = integer(stack["callSp"], 0x02000000, 0x02800000-32)
    require(sp % 8 == 0 and stack["hostRestoredFrameBytes"] == 0
            and stack["nativeFrameBytes"] == 80 and stack["scratchBytes"] == 268, "native stack contract differs")
    thread = stack["thread"]
    require(thread["mode"] == 31 and thread["irqDepth"] == 0
            and integer(thread["stackTop"]) < sp < integer(thread["stackBottom"])-32,
            "call stack has no normal thread owner")
    boundary = receipt["setupBoundary"]
    end = clock(probe_row["snapshot"])
    if "snapshot" in receipt:
        require(receipt["snapshot"] == probe_row["snapshot"], "worker and row endpoints differ")
    require(boundary.get("eventsDrained") is True and clock(boundary) == end
            and integer(boundary["endpointNativeCycle"], 1) >= end[1]
            and start[0] <= end[0] and start[1] <= end[1], "setup boundary clocks differ")
    require(isinstance(boundary["traceSequences"], dict), "missing drained trace boundary")
    for stream, sequence in boundary["traceSequences"].items():
        require(isinstance(stream, str) and stream.isdecimal() and int(stream) > 0, "bad trace stream")
        integer(sequence)
    calls = receipt["calls"]
    require(isinstance(calls, list) and len(calls) == len(CASE_NAMES) + 2,
            "exact allocation/resolves/free required")
    expected = [("allocate_work_memory", [11, BUFFER_BYTES], work)] + [
        ("resolve_behavior", [source, blob["size"], work + REQUEST,
                              work + RESULT, work + TRACE], 0)
        ] * len(CASE_NAMES) + [
        ("free", [work], None)]
    addresses = oracle["callAddresses"]
    require(addresses["resolve_behavior"] | 1 == oracle["serviceIdentity"]["resolveAddress"],
            "oracle service target differs")
    for call, (name, args, result) in zip(calls, expected):
        require(call["routine"] == name and call["address"] == addresses[name]
                and call["requestedArguments"] == args and call["entryArguments"] == args,
                "native call or entry arguments differ")
        for arg in call["entryArguments"] + call["requestedArguments"]:
            integer(arg)
        require(call["entryStack"] == sp and call["entryLink"] == trampoline_address+0x4C
                and integer(call["entryCpsr"]) & 0x3F == 0x3F
                and call["entryBoundary"] == "native-trampoline-BLX-entry", "native entry frame differs")
        integer(call["returnValue"])
        require(result is None or call["returnValue"] == result, "native return differs")
    natives = value["receipts"]
    require(isinstance(natives, list) and all(isinstance(n, dict) and isinstance(n.get("trace"), list)
            and 1 <= len(n["trace"]) <= 96 for n in natives), "native trace exceeds owned capacity")
    proof = compare_resolver_parity(oracle["vectors"], natives, oracle["hostResults"],
        blob_identity=blob, service_identity=oracle["serviceIdentity"])
    previous = start
    cycles = set()
    for native in natives:
        dispatched, returned = clock(native["dispatchClock"]), clock(native["returnClock"])
        require(previous[0] <= dispatched[0] <= returned[0] <= end[0]
                and previous[1] <= dispatched[1] <= returned[1] <= end[1], "native case clocks differ")
        require(returned[1]-dispatched[1] <= 180, "case exceeds native bridge bound")
        cycles.update(range(dispatched[1], returned[1]+1))
        previous = returned
    require(1 <= integer(natural["entryNativeCycle"], 1) <= integer(natural["returnNativeCycle"], 1)
            <= natives[0]["dispatchClock"]["nativeCycle"], "natural discovery is later than controlled work")
    host = oracle["hostResults"]
    service = oracle["serviceIdentity"]
    metadata = ("behaviorClass", "behaviorLimitKey", "speciesClassRuleIndex", "matchedClassRuleMask",
                "matchedOverrideMask", "forcedOverrideMask", "conditionalOverrideMask", "appliedOverrideMask")
    values = ([service["magic"], service["version"], service["size"], service["resolveAddress"] & ~1],
        [blob["size"], blob["sha256"]], [r["status"] for r in host],
        [hashlib.sha256(bytes.fromhex(r["profileHex"])).hexdigest() for r in host],
        [r["primitivesHex"] for r in host], [r["fingerprint"] for r in host],
        digest([{k:r[k] for k in metadata} for r in host]),
        [digest({k:r[k] for k in ("traceDropped", "trace")}) for r in host])
    return {"measurements": [dict(claim="profile-resolution", name=name, value=deepcopy(v),
                operator="eq", threshold=deepcopy(v), passed=True) for name,v in zip(NAMES, values)],
            "caseProof": proof, "observedFrames": len(cycles), "observedFrameUnit": "native-resolver-cycles",
            "completedGameFrames": natives[-1]["returnClock"]["frame"]-natives[0]["dispatchClock"]["frame"]}
