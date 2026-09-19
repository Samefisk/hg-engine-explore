"""Native Inspect readiness. This module does not grant controller acceptance."""
from copy import deepcopy
import struct
from tools.overworld.devtools_records import select_current_actor, _subject
from tools.overworld.normal_play_observer import live_identity
from tools.overworld.devtools_resolver_proof import integer, pointer, clock
from tools.overworld.devtools_actor_inspect_probe import GENERATION_KEYS, ENGINE_OWNER_KEYS


def require(ok, reason):
    if not ok:
        raise ValueError("actor inspect: " + reason)


def raw(value, size):
    require(type(value) is str and len(value) == size * 2, "invalid byte receipt")
    data = bytes.fromhex(value)
    require(len(data) == size, "invalid byte receipt")
    return data


def actor_bytes(a):
    h = a["handle"]
    values = [1, 88] + [h[k] for k in ("slot", "generation", "fieldEpoch", "mapGeneration", "encounterGeneration")] + [0]
    values += [a[k] for k in ("subjectIdentity", "behaviorFingerprint", "matchedLayerMask", "lastCommandSequence",
        "commitSequence", "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")]
    values += [a[k][axis] for k in ("logical", "render", "origin", "target") for axis in ("x", "y")]
    values += [a[k] for k in ("motionElapsed", "motionDuration", "reservationId", "species")]
    values += [a[k] for k in ("form", "level", "roleId", "laneId", "motionKindId", "motionPhaseId",
        "inputOwnership", "streamState", "controllerState", "lastIntent", "lastDecision", "lastCancelReason")]
    values += [int(a["active"]), int(a["presentationAttached"]), a["presentationState"], 0]
    return struct.pack("<HH6H8I8h4H16B", *values)


def checked_receipt(row, subject, *, oracle=None):
    receipt, snapshot = row["receipt"], row["snapshot"]
    require(receipt.get("boundary") == "native-field-command-trampoline" and receipt.get("preparedOnly") is True
            and receipt.get("acceptedProof") is False and not receipt.get("fatal") and not receipt.get("error")
            and receipt.get("firstBadCheckpoint") is None and receipt.get("firstInvalidThreadSwitch") is None
            and receipt.get("nativeHeapAdaptation") == [], "native bridge fault or foreign operation")
    boundary = receipt["setupBoundary"]
    require(boundary.get("eventsDrained") is True and clock(boundary) == clock(snapshot)
            and boundary["endpointNativeCycle"] >= snapshot["nativeCycle"], "endpoint differs")
    if "snapshot" in receipt:
        require(receipt["snapshot"] == snapshot, "endpoint differs")
    endpoint = select_current_actor(snapshot, subject)
    require(all(k in endpoint.get("engineIdentity", {}) and k in subject.get("engineIdentity", {})
                and endpoint["engineIdentity"][k] == subject["engineIdentity"][k] for k in ENGINE_OWNER_KEYS),
            "bound engine owner differs")
    value = receipt["value"]
    require(value.get("completed") is True and value.get("acceptedProof") is False, "incomplete probe")
    allocation = value["allocation"]
    work = pointer(allocation["pointer"], 232)
    require(allocation.get("heapId") == 11 and allocation.get("bytes") == 232
            and allocation.get("released") is True, "owned buffer not freed")
    cases, calls = value["receipts"], receipt["calls"]
    require(len(cases) == 2 and [c["name"] for c in cases] == ["current-handle", "stale-generation"], "case list differs")
    require(len(calls) == 4 and [c["routine"] for c in calls] ==
            ["allocate_work_memory", "inspect_actor", "inspect_actor", "free"], "native call list differs")
    trampoline, stack = receipt["trampoline"], receipt["stackOwnership"]
    address = pointer(trampoline["address"], 1536)
    require(trampoline["bytes"] == 1536 and trampoline["heapId"] == 11
            and trampoline["lifetime"] == "field-system-heap11"
            and (work + 232 <= address or address + 1536 <= work), "trampoline owner differs")
    sp = integer(stack["callSp"], 0x02000000, 0x02800000 - 32)
    require(sp % 8 == 0 and stack["hostRestoredFrameBytes"] == 0 and stack["nativeFrameBytes"] == 80
            and stack["scratchBytes"] == 268 and stack["thread"]["mode"] == 31
            and stack["thread"]["irqDepth"] == 0
            and stack["thread"]["stackTop"] < sp < stack["thread"]["stackBottom"] - 32, "stack owner differs")
    expected = [([11, 232], work), ([work + 16, work + 40], 0), ([work + 16, work + 40], 2), ([work], None)]
    for call, (args, status) in zip(calls, expected):
        require(call["requestedArguments"] == args == call["entryArguments"]
                and call["entryStack"] == sp and call["entryLink"] == address + 0x4c
                and call["entryCpsr"] & 0x3f == 0x3f
                and call["entryBoundary"] == "native-trampoline-BLX-entry", "native arguments differ")
        integer(call["returnValue"])
        require(status is None or call["returnValue"] == status, "native status differs")
        if oracle is not None:
            require(call["address"] == oracle["callAddresses"][call["routine"]], "packaged entry differs")
    cycles = set()
    previous = None
    for index, case in enumerate(cases):
        a = case["actor"]
        require(all(type(subject.get(k)) is int and subject[k] > 0 and a.get(k) == subject[k]
                    for k in GENERATION_KEYS), "bound generations differ")
        require(all(k in subject.get("engineIdentity", {}) and k in a.get("engineIdentity", {})
                    and a["engineIdentity"][k] == subject["engineIdentity"][k] for k in ENGINE_OWNER_KEYS)
                and a["sourceIdentity"]["object"] == subject["engineIdentity"]["pointer"], "bound engine owner differs")
        require(type(a.get("roleId")) is int and a["roleId"] == 2, "native follower role differs")
        require(_subject(a) == _subject(subject) and a["species"] == 56 and a["role"] == "FOLLOWER"
                and a.get("identityVerified") is True and live_identity(a, a["sourceIdentity"], a["engineIdentity"],
                    species=56, role="FOLLOWER", current_epoch=subject["handle"]["fieldEpoch"]), "bound subject differs")
        require(a["form"] == a["sourceIdentity"]["form"] and a["level"] == a["sourceIdentity"]["level"], "bound subject differs")
        current = raw(case["currentActorHex"], 88)
        require(current == actor_bytes(a) == raw(case["currentActorAfterHex"], 88), "current actor bytes differ")
        require(raw(case["stateBeforeSha256"], 32) == raw(case["stateAfterSha256"], 32), "state changed")
        if index:
            require(current == raw(cases[0]["currentActorHex"], 88), "actor changed between calls")
        handle = list(struct.unpack_from("<6H", current, 4))
        if index: handle[1] = handle[1] % 65535 + 1
        require(raw(case["queryHex"], 24) == struct.pack("<HHBBH6HI", 1, 24, 1, 0, 0, *handle, 0), "query differs")
        output = raw(case["outputHex"], 176)
        require(case["status"] == (0 if index == 0 else 2)
                and output[:8] == struct.pack("<HH4B", 1, 176, 1, int(index == 0), 0, 0)
                and output[20:108] == (current if index == 0 else bytes(88))
                and output[144:] == bytes(32), "native Inspect result differs")
        require(case["fieldPointer"] == trampoline["fieldPointer"] and case["heapGeneration"] == trampoline["heapGeneration"], "field heap differs")
        if oracle is not None:
            require(case["serviceIdentity"] == oracle["serviceIdentity"]
                    and oracle["callAddresses"]["inspect_actor"] | 1 == oracle["serviceIdentity"]["inspectAddress"], "packaged entry differs")
        start, end = clock(case["dispatchClock"]), clock(case["returnClock"])
        require(start[0] <= end[0] <= snapshot["frame"] and start[1] <= end[1] <= snapshot["nativeCycle"]
                and end[1] - start[1] <= 180 and (previous is None or start[0] >= previous[0] and start[1] >= previous[1]), "native clocks differ")
        previous = end
        cycles.update(range(start[1], end[1] + 1))
    return dict(observedFrames=len(cycles), observedFrameUnit="native-inspect-cycles",
                completedGameFrames=cases[-1]["returnClock"]["frame"] - cases[0]["dispatchClock"]["frame"])


class ActorInspectMeasurement:
    def __init__(self, test=None, **_kwargs):
        self.test = test
        self.subject = self.receipt = None
        self.failures = []
        self.closed = False
        self.rows = 0
        self.previous_clock = None
        self.counts = dict(observedFrames=0, observedFrameUnit="native-inspect-cycles", completedGameFrames=0)

    def observe_record(self, row, *, full_report=True):
        if self.failures: return self.result()
        try:
            require(not self.closed, "measurement is closed")
            require(isinstance(self.test, dict) and self.test.get("mode") == "prepared", "prepared test required")
            require(self.test.get("subjects") == [dict(id="mankey", species=56, role="FOLLOWER", acquire="existing")], "declared subject differs")
            setup, actions = self.test["setup"], self.test["actions"]
            require(len(setup) == len(actions) == 1 and setup[0]["op"] == "bind"
                    and actions[0]["op"] == "actor-inspect.probe"
                    and setup[0]["args"] == actions[0]["args"] == {"subject": "mankey"}, "authored actions differ")
            command = row.get("command")
            expected = (None, "bind", "actor-inspect.probe")
            require(self.rows < 3 and command == expected[self.rows], "row order differs")
            if self.rows:
                action = setup[0] if self.rows == 1 else actions[0]
                require(row.get("action") == action["id"] and row.get("phase") == ("setup" if self.rows == 1 else "observe"), "authored phase/action differs")
            current_clock = clock(row["snapshot"] if self.rows else row["initialSnapshot"])
            require(self.previous_clock is None or all(a <= b for a, b in zip(self.previous_clock, current_clock)), "row clocks differ")
            if command == "actor-inspect.probe":
                start = clock(row["receipt"]["value"]["receipts"][0]["dispatchClock"])
                require(all(a <= b for a, b in zip(self.previous_clock, start)), "probe predates binding")
            self.previous_clock = current_clock
            self.rows += 1
            if command == "bind":
                require(self.subject is None and self.receipt is None, "duplicate bind")
                self.subject = deepcopy(row["receipt"])
                require(select_current_actor(row["snapshot"], self.subject) == self.subject,
                        "bind receipt differs from snapshot")
            elif command == "actor-inspect.probe":
                require(self.subject is not None and self.receipt is None and row.get("phase") == "observe", "missing bind or duplicate probe")
                self.counts = checked_receipt(row, self.subject)
                self.receipt = deepcopy(row["receipt"])
            else:
                require(command is None and self.subject is None and "initialSnapshot" in row, "foreign row")
        except (ValueError, KeyError, TypeError, AttributeError, IndexError, OverflowError, struct.error) as error:
            self.failures.append(dict(code="actor-inspect-probe-invalid", detail=str(error)))
        return self.result()

    def result(self):
        ready = self.receipt is not None and not self.failures
        return dict(state="failed" if self.failures else "passed" if ready else "running", ready=ready,
                    passed=ready, acceptedProof=False, failures=deepcopy(self.failures), **self.counts)

    def finish(self):
        if self.receipt is None and not self.failures:
            self.failures.append(dict(code="actor-inspect-probe-missing", detail="native probe missing"))
        self.closed = True
        return self.result()
