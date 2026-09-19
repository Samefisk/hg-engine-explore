"""Diagnostic readiness for one bounded native resolver command.

This is not Workshop equality or controller acceptance. No actor or boot frame
is required. Only cycles occupied by retained resolver calls receive credit.
"""
from copy import deepcopy

from tools.overworld.devtools_resolver_parity import CASE_NAMES, raw_hex, checked_trace
from tools.overworld.devtools_resolver_probe import REQUEST, RESULT, TRACE


def require(ok, reason):
    if not ok:
        raise ValueError("resolver measurement: " + reason)


def number(value):
    require(type(value) is int and 0 <= value <= 0xFFFFFFFF, "invalid clock/integer")
    return value


def clock(value):
    require(isinstance(value, dict) and set(value) == {"frame", "nativeCycle"}, "missing call clock")
    return number(value["frame"]), number(value["nativeCycle"])


class ResolverMeasurement:
    def __init__(self, test=None, **_kwargs):
        self.receipt = None
        self.failures = []
        self.observed_frames = 0
        self.completed_frames = 0
        self.start_cycle = self.end_cycle = None
        self.closed = False

    def observe_record(self, record, *, full_report=True):
        if self.failures:
            return self.result()
        try:
            require(isinstance(record, dict), "invalid row")
            if record.get("command") != "resolver.probe":
                return self.result()  # Setup/boundary rows never earn proof time.
            require(self.receipt is None and not self.closed, "duplicate probe")
            require(record.get("phase") == "observe" and isinstance(record.get("action"), str),
                    "probe is not a declared observation action")
            receipt = record.get("receipt")
            require(isinstance(receipt, dict) and receipt.get("fatal") is not True
                    and not receipt.get("error"), "fatal or missing probe receipt")
            snapshot = record.get("snapshot")
            boundary = receipt.get("setupBoundary", {})
            require(isinstance(snapshot, dict) and snapshot == receipt.get("snapshot")
                    and number(snapshot.get("frame")) == number(boundary.get("frame"))
                    and number(snapshot.get("nativeCycle")) == number(boundary.get("nativeCycle"))
                    and boundary.get("eventsDrained") is True,
                    "probe endpoint differs")
            bridge = receipt
            require(isinstance(bridge, dict) and bridge.get("boundary") == "native-field-command-trampoline"
                    and bridge.get("preparedOnly") is True and not bridge.get("fatal")
                    and not bridge.get("error") and bridge.get("firstBadCheckpoint") is None
                    and bridge.get("firstInvalidThreadSwitch") is None, "native bridge failed")
            probe = bridge.get("value")
            require(isinstance(probe, dict) and probe.get("completed") is True
                    and probe.get("acceptedProof") is False, "probe is incomplete")
            allocation = probe.get("allocation", {})
            pointer = number(allocation.get("pointer"))
            require(allocation.get("heapId") == 11 and allocation.get("bytes") == 8000
                    and allocation.get("released") is True and not pointer & 3
                    and 0x02000000 <= pointer <= 0x02400000 - 8000, "owned allocation not freed")
            cases = probe.get("receipts")
            require(isinstance(cases, list) and len(cases) == len(CASE_NAMES)
                    and tuple(case.get("name") for case in cases if isinstance(case, dict)) == CASE_NAMES,
                    "resolver cases missing or reordered")
            calls = bridge.get("calls")
            require(isinstance(calls, list) and [c.get("routine") for c in calls] ==
                    ["allocate_work_memory"] + ["resolve_behavior"] * len(CASE_NAMES) + ["free"],
                    "native call list differs")
            require(calls[0].get("requestedArguments") == [11, 8000]
                    and calls[0].get("returnValue") == pointer
                    and calls[-1].get("requestedArguments") == [pointer]
                    and "returnValue" in calls[-1], "allocation/free call receipt differs")
            intervals = []; previous = None
            for case, call in zip(cases, calls[1:1 + len(CASE_NAMES)]):
                require(type(case.get("status")) is int and case["status"] == 0
                        and type(call.get("returnValue")) is int and call["returnValue"] == 0,
                        "resolver status failed")
                raw_hex(case.get("requestHex"), 44)
                raw_hex(case.get("resultHex"), 200)
                checked_trace(case)
                require(isinstance(case.get("blobIdentity"), dict) and isinstance(case.get("serviceIdentity"), dict),
                        "native input identity missing")
                args = call.get("requestedArguments")
                require(isinstance(args, list) and len(args) == 5 and args == call.get("entryArguments")
                        and args[2:] == [pointer + REQUEST, pointer + RESULT, pointer + TRACE],
                        "native arguments differ")
                start, end = clock(case.get("dispatchClock")), clock(case.get("returnClock"))
                require(start[0] <= end[0] <= snapshot["frame"] and start[1] <= end[1] <= snapshot["nativeCycle"]
                        and end[1] - start[1] < 600 and (previous is None or
                        start[0] >= previous[0] and start[1] >= previous[1]), "call clock order/bound differs")
                previous = end
                intervals.append((start, end))
            cycles = set()
            for start, end in intervals:
                cycles.update(range(start[1], end[1] + 1))
            require(len(cycles) <= 600, "native observation budget exceeded")
            self.observed_frames = len(cycles)
            self.completed_frames = intervals[-1][1][0] - intervals[0][0][0]
            self.start_cycle, self.end_cycle = intervals[0][0][1], intervals[-1][1][1]
            self.receipt = deepcopy(receipt)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            self.failures.append({"code": "resolver-probe-invalid", "detail": str(error)})
        return self.result()

    def result(self):
        ready = self.receipt is not None and not self.failures
        return {"state": "failed" if self.failures else "passed" if ready else "running",
                "ready": ready, "passed": ready, "observedFrames": self.observed_frames,
                "observedFrameUnit": "native-resolver-cycles",
                "completedGameFrames": self.completed_frames, "startNativeCycle": self.start_cycle,
                "endNativeCycle": self.end_cycle, "acceptedProof": False,
                "failures": deepcopy(self.failures), "receipt": deepcopy(self.receipt),
                "scope": "native bounded-call readiness only; Workshop comparison and live acceptance are separate"}

    def finish(self):
        if not self.closed and self.receipt is None and not self.failures:
            self.failures.append({"code": "resolver-probe-missing", "detail": "resolver.probe was not observed"})
        self.closed = True
        return self.result()
