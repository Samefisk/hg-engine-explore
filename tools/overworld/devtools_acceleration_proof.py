"""Controller-only authentication of prepared RESET; no motion/acceptance credit.

The caller supplies an oracle from current packaged/linked code, never from
the retained receipt: {callAddresses: {reduce_walk: address}, serviceIdentity}.
The parent controller still owns source/ROM/save hashes and session cleanup.
"""
from copy import deepcopy
import re
import struct

from tools.overworld.devtools_acceleration_measurement import policy_bytes, reset_value
from tools.overworld.devtools_records import GENERATION_FIELDS, select_current_actor
from tools.overworld.devtools_resolver_proof import clock, integer, pointer


def require(value, reason):
    if not value:
        raise ValueError("acceleration RESET proof: " + reason)


def checked_reset_receipt(row, subject, *, oracle):
    """Validate one raw walk-policy.reset row against its bound subject/oracle."""
    try:
        return _checked(row, subject, oracle)
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError("acceleration RESET proof: malformed receipt") from error


def _checked(row, subject, oracle):
    require(row.get("command") in ("walk-policy.reset", "acceleration.begin"), "wrong command")
    receipt, snapshot = row["receipt"], row["snapshot"]
    require(receipt.get("boundary") == "native-field-command-trampoline"
            and receipt.get("preparedOnly") is True and receipt.get("acceptedProof") is False
            and not receipt.get("fatal") and not receipt.get("error")
            and "firstBadCheckpoint" in receipt and receipt["firstBadCheckpoint"] is None
            and "firstInvalidThreadSwitch" in receipt and receipt["firstInvalidThreadSwitch"] is None
            and receipt.get("nativeHeapAdaptation") == [], "native bridge fault or foreign operation")
    value = receipt["value"]
    reset_value(value)  # Exact public v1, size28, slot, RESET0 and reset mask.
    require(value.get("scratchRestored") is True, "scratch not restored")
    target = integer(oracle["callAddresses"]["reduce_walk"], 0x02000000, 0x023FFFFE)
    require(target % 2 == 0, "oracle target is not a Thumb entry")
    service = oracle["serviceIdentity"]
    require(value.get("serviceIdentity") == service, "packaged service differs")
    require(service["reduceWalkAddress"] == target | 1
            and re.fullmatch(r"[0-9a-f]{64}", service["entrySha256"]) is not None,
            "oracle target differs")
    header, table = bytes.fromhex(service["entryHex"]), bytes.fromhex(service["tableHex"])
    require(len(header) == 16 and header[:8] == struct.pack("<IHH", 0x504D574F, 5, 16)
            and struct.unpack_from("<I", header, 12)[0] != 0 and len(table) == 24
            and struct.unpack_from("<I", table, 12)[0] == target | 1, "oracle public ABI differs")
    pointer(service["address"], 16)
    pointer(struct.unpack_from("<I", header, 8)[0], 24)
    pointer(struct.unpack_from("<I", header, 12)[0], 16)
    trampoline, stack = receipt["trampoline"], receipt["stackOwnership"]
    address = pointer(trampoline["address"], 1536)
    field, heap = pointer(value["fieldPointer"]), integer(value["heapGeneration"])
    require(trampoline.get("bytes") == 1536 and trampoline.get("heapId") == 11
            and trampoline.get("lifetime") == "field-system-heap11"
            and trampoline.get("fieldPointer") == field and trampoline.get("heapGeneration") == heap
            and isinstance(trampoline.get("codeSha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", trampoline["codeSha256"]) is not None,
            "trampoline field/heap owner differs")
    sp = integer(stack["callSp"], 0x02000000, 0x02800000 - 32)
    thread = stack["thread"]
    require(sp % 8 == 0 and stack.get("hostRestoredFrameBytes") == 0
            and stack.get("nativeFrameBytes") == 80 and stack.get("scratchBytes") == 268
            and thread.get("mode") == 31 and thread.get("irqDepth") == 0 and thread.get("state") == 1
            and thread.get("topGuard") == 0x7BF9DD5B and thread.get("bottomGuard") == 0xFDDB597D
            and integer(thread["stackTop"], 0x02000000, 0x02800000) < sp
            < integer(thread["stackBottom"], 0x02000000, 0x02800000) - 32,
            "native stack/thread owner differs")
    pointer(thread["pointer"])
    integer(thread["id"])
    calls = receipt["calls"]
    require(isinstance(calls, list) and len(calls) == 1, "exactly one RESET call required")
    call = calls[0]
    args = [address + 0x210]
    require(call.get("routine") == "reduce_walk" and call.get("address") == target
            and call.get("requestedArguments") == args == call.get("entryArguments")
            and call.get("entryStack") == sp and call.get("entryLink") == address + 0x4C
            and integer(call["entryCpsr"]) & 0x3F == 0x3F
            and call.get("entryBoundary") == "native-trampoline-BLX-entry"
            and type(call.get("returnValue")) is int and call["returnValue"] == 1,
            "native RESET call differs")
    require(all(key in subject for key in GENERATION_FIELDS), "bound generations missing")
    require(subject.get("role") in ("WILD", "MOUNTED"), "unsupported bound role")
    previous = None
    for endpoint in (value["before"], value["after"]):
        snap, actor = endpoint["snapshot"], endpoint["actor"]
        selected = select_current_actor(snap, subject)
        identity_keys = ("handle", "subjectIdentity", "species", "role", *GENERATION_FIELDS)
        require(all(value["subject"].get(k) == selected[k] for k in identity_keys)
                and selected["engineIdentity"] == subject["engineIdentity"], "bound subject differs")
        require(snap.get("prepared") is True and snap["fieldControl"]["fieldPointer"] == field
                and actor.get("motionPhase") == "IDLE" and actor.get("reservationId") == 0
                and actor.get("inputOwnership") == int(subject["role"] == "MOUNTED"), "RESET endpoint is not idle")
        inputs = endpoint["inputs"]
        require(inputs.get("state") == 0 and all(inputs.get(k) == 0 for k in
                ("heldKeys", "newKeys", "rawHeld", "rawNew", "simulatedKeys", "physicalPressed")),
                "RESET input is not released")
        raw = policy_bytes(endpoint["policy"], endpoint["policyHex"])
        require(int.from_bytes(raw[8:12], "little") == actor["behaviorFingerprint"]
                and int.from_bytes(raw[12:16], "little") == actor["matchedLayerMask"], "RESET profile binding differs")
        current = clock(snap)
        require(previous is None or all(a <= b for a, b in zip(previous, current)), "RESET clocks reversed")
        previous = current
    end = clock(snapshot)
    require(all(a <= b for a, b in zip(previous, end)), "RESET endpoint precedes native return")
    selected = select_current_actor(snapshot, subject)
    require(selected["engineIdentity"] == subject["engineIdentity"] and snapshot.get("prepared") is True,
            "outer endpoint subject differs")
    boundary = receipt["setupBoundary"]
    require(receipt.get("snapshot") == snapshot and boundary.get("eventsDrained") is True
            and clock(boundary) == end and integer(boundary["endpointNativeCycle"], end[1]) >= end[1],
            "setup boundary differs")
    require(isinstance(boundary.get("traceSequences"), dict) and isinstance(receipt.get("events"), list),
            "drained trace boundary missing")
    for stream, sequence in boundary["traceSequences"].items():
        require(isinstance(stream, str) and stream.isdecimal() and int(stream) > 0, "invalid trace stream")
        integer(sequence)
    return dict(scope="acceleration-reset-setup-only", acceptedProof=False, observedFrames=0,
                nativeCalls=1, subject=deepcopy(selected), reset=deepcopy(value))
