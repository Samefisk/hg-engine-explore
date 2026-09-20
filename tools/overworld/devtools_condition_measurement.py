"""Readiness meter for one bounded native condition-service probe.

Controller package authentication and semantic acceptance stay in
``devtools_condition_proof``.  This meter only validates the retained raw row
shape and native work-cycle credit.
"""
from copy import deepcopy

from tools.overworld.devtools_condition_probe import (
    BUFFER_BYTES,
    CASE_NAMES,
    PREPARED_BYTES,
    RESULT_BYTES,
    SCRATCH_BYTES,
)


def require(ok, reason):
    if not ok:
        raise ValueError("condition measurement: " + reason)


def number(value):
    require(type(value) is int and 0 <= value <= 0xFFFFFFFF,
            "invalid clock/integer")
    return value


def clock(value):
    require(isinstance(value, dict)
            and {"frame", "nativeCycle"}.issubset(value),
            "missing call clock")
    return number(value["frame"]), number(value["nativeCycle"])


class ConditionMeasurement:
    def __init__(self, test=None, **_kwargs):
        self.test = test
        self.rows = 0
        self.previous = None
        self.receipt = None
        self.failures = []
        self.closed = False
        self.counts = {
            "observedFrames": 0,
            "observedFrameUnit": "native-condition-service-cycles",
            "completedGameFrames": 0,
        }

    def observe_record(self, row, *, frame_callback=None, full_report=True):
        if self.failures:
            return self.result()
        try:
            require(not self.closed and isinstance(row, dict), "invalid row")
            require(isinstance(self.test, dict)
                    and self.test.get("mode") == "prepared"
                    and not self.test.get("subjects")
                    and not self.test.get("setup")
                    and len(self.test.get("actions", [])) == 1
                    and self.test["actions"][0].get("op") == "condition.probe",
                    "authored condition probe differs")
            require(self.rows < 2, "duplicate condition probe")
            if self.rows == 0:
                require("initialSnapshot" in row and "command" not in row,
                        "initial boundary is missing")
                self.previous = clock(row["initialSnapshot"])
                if frame_callback:
                    frame_callback(row["initialSnapshot"], (), self)
            else:
                action = self.test["actions"][0]
                require(row.get("command") == "condition.probe"
                        and row.get("phase") == "observe"
                        and row.get("action") == action["id"],
                        "condition probe action differs")
                endpoint = clock(row["snapshot"])
                require(self.previous[0] <= endpoint[0]
                        and self.previous[1] <= endpoint[1],
                        "condition endpoint clock moved backwards")
                receipt = row["receipt"]
                require(receipt.get("boundary") == "native-field-command-trampoline"
                        and receipt.get("preparedOnly") is True
                        and receipt.get("acceptedProof") is False
                        and receipt.get("firstBadCheckpoint") is None
                        and receipt.get("firstInvalidThreadSwitch") is None
                        and not receipt.get("fatal") and not receipt.get("error"),
                        "native bridge failed")
                value = receipt["value"]
                allocation = value["allocation"]
                require(value.get("completed") is True
                        and value.get("acceptedProof") is False
                        and value.get("fixture", {}).get("patched") is True
                        and value.get("fixture", {}).get("intactBeforeRestore") is True
                        and value.get("fixture", {}).get("restored") is True
                        and allocation.get("heapId") == 11
                        and allocation.get("bytes") == BUFFER_BYTES
                        and allocation.get("released") is True,
                        "owned condition allocation is incomplete")
                pointer = number(allocation["pointer"])
                require(pointer % 4 == 0
                        and 0x02000000 <= pointer <= 0x02400000 - BUFFER_BYTES,
                        "owned condition allocation is invalid")
                prepares = value["prepareReceipts"]
                cases = value["receipts"]
                require(len(prepares) == 2
                        and [item.get("subjectRoleLabel") for item in prepares]
                            == ["WILD", "FOLLOWER"]
                        and all(item.get("status") == 0 for item in prepares),
                        "condition prepare cases differ")
                require(len(cases) == len(CASE_NAMES)
                        and tuple(item.get("name") for item in cases) == CASE_NAMES
                        and [item.get("status") for item in cases]
                            == [0, 0, 0, 0, 3, 0, 0],
                        "condition evaluate cases differ")
                require([call.get("routine") for call in receipt["calls"]]
                        == ["allocate_work_memory", "prepare_conditions"]
                           + ["evaluate_conditions"] * 6
                           + ["prepare_conditions", "evaluate_conditions", "free"],
                        "condition native call list differs")
                intervals = []
                for case in cases:
                    require(len(bytes.fromhex(case["preparedHex"])) == PREPARED_BYTES
                            and len(bytes.fromhex(case["scratchHex"])) == SCRATCH_BYTES
                            and len(bytes.fromhex(case["resultHex"])) == RESULT_BYTES,
                            "condition raw readback size differs")
                    start, finish = clock(case["dispatchClock"]), clock(case["returnClock"])
                    require(start[0] <= finish[0] <= endpoint[0]
                            and start[1] <= finish[1] <= endpoint[1]
                            and finish[1] - start[1] <= 180
                            and (not intervals
                                 or intervals[-1][1][0] <= start[0]
                                 and intervals[-1][1][1] <= start[1]),
                            "condition call clock differs")
                    intervals.append((start, finish))
                cycles = set()
                for start, finish in intervals:
                    cycles.update(range(start[1], finish[1] + 1))
                require(1 <= len(cycles) <= 1260,
                        "condition native cycle budget differs")
                self.counts = {
                    "observedFrames": len(cycles),
                    "observedFrameUnit": "native-condition-service-cycles",
                    "completedGameFrames": intervals[-1][1][0] - intervals[0][0][0],
                }
                self.receipt = deepcopy(receipt)
                self.previous = endpoint
                if frame_callback:
                    frame_callback(row["snapshot"], (), self)
            self.rows += 1
        except (ValueError, KeyError, TypeError, AttributeError, IndexError) as error:
            self.failures.append({"code": "condition-probe-invalid",
                                  "detail": str(error)})
        return self.result()

    def result(self):
        ready = self.rows == 2 and self.receipt is not None and not self.failures
        return {
            "state": "failed" if self.failures else "passed" if ready else "running",
            "ready": ready,
            "passed": ready,
            **self.counts,
            "acceptedProof": False,
            "failures": deepcopy(self.failures),
            "receipt": deepcopy(self.receipt),
            "scope": ("native condition-service readiness only; controller package "
                      "authentication and S3 acceptance are separate"),
        }

    def finish(self):
        if not self.closed and not self.failures and self.receipt is None:
            self.failures.append({"code": "condition-probe-missing",
                                  "detail": "condition.probe was not observed"})
        self.closed = True
        return self.result()
