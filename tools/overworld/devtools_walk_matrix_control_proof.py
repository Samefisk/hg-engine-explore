"""Same-reader matrix calibration proof; never the complete 65-motion claim."""
from copy import deepcopy

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_contract import CASES, validate_motion
from tools.overworld.devtools_walk_matrix_control_measurement import KIND, validate_control, moving_summary
from tools.overworld.devtools_walk_matrix_proof import MatrixNegative, FAULTS as MATRIX_FAULTS, need
from tools.overworld.devtools_walk_matrix_proof import validate_negative_result as validate_matrix_negative

REQUIREMENT = "shared.walk-matrix-recorder-control-v1"
RULES = (("live-actor-identity", "bound-matrix-control-subject"),
         ("controlled-action", "same-reader-state-fault"),
         ("controlled-action", "exact-state-restoration"))
CLAIMS = tuple(dict.fromkeys(claim for claim, _ in RULES))
BASELINE_FAULTS = tuple(f for f in MATRIX_FAULTS if f not in ("matrix-gate-moved", "matrix-missing-final-motion"))
CONTROL_FAULTS = ("matrix-control-missing-control", "matrix-control-wrong-byte", "matrix-control-unrestored",
                  "matrix-control-clock", "matrix-control-registers", "matrix-control-address",
                  "matrix-control-missing-moving-tick")
FAULTS = (*BASELINE_FAULTS, *CONTROL_FAULTS)


def contract():
    result = {}
    for claim, name in RULES:
        result.setdefault(claim, []).append(dict(name=name, operator="eq", type="integer",
            validator="meaningful-observation", expected=1))
    return result


def validate_baseline(natural):
    need(natural.get("ready") is True and natural.get("failures") == []
         and natural.get("acceptedProof") is False and natural.get("prefixOnly") is True
         and natural.get("expectedCases") == natural.get("completedCases") == 2,
         "matrix control lacks original two-case baseline")
    subject = natural["subject"]
    for snapshot in (natural["initial"], natural["terminalSnapshot"]):
        selected = select_current_actor(snapshot, subject)
        actor = next(a for a in snapshot["actors"] if a["handle"] == selected["handle"])
        need(actor["role"] == "MOUNTED" and actor["species"] == 155 and actor["inputOwnership"] == 1,
             "matrix control baseline actor differs")
    need(len(natural["cases"]) == len(natural["configurations"]) == 2,
         "matrix control baseline case count differs")
    for expected, motion, config in zip(CASES[:2], natural["cases"], natural["configurations"]):
        need(motion["case"] == expected and motion["subject"] == subject,
             "matrix control baseline case differs")
        validate_motion(**motion)
        profile = bytes.fromhex(config["profileHex"])
        need(len(profile) == 72 and profile[7] == profile[51] == expected["duration"]
             and (profile[19] & 0x03) == expected["mode"] and profile[50] == 0,
             "matrix control baseline profile differs")
    need(natural["cases"][0]["reservation"] != natural["cases"][1]["reservation"],
         "matrix control baseline reservation reused")


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    need(replay.get("passed") is True and replay.get("failures") == []
         and all(meter.get(k) is True for k in ("passed", "closed", "ready"))
         and meter.get("acceptedProof") is False and meter.get("failures") == [],
         "matrix control lacks complete independent replay")
    natural = meter["natural"]
    validate_baseline(natural)
    need(meter["subject"] == natural["subject"] and meter["terminal"] == natural["terminalSnapshot"],
         "matrix control baseline owner differs")
    cleanup = meter["cleanup"]
    reader = cleanup["walkMatrix"]
    validate_control(meter["control"], meter["lastMovingTick"], meter["terminal"], meter["subject"], reader["motionPointer"])
    need(cleanup.get("closed") is True and cleanup.get("advancedFrames") == 0
         and cleanup.get("acceptedProof") is False and reader.get("armed") is True
         and reader.get("closed") is True and reader.get("failure") is None
         and reader.get("subject") == meter["subject"] and reader.get("guestMemoryWrites") == 2
         and reader.get("calibration") == meter["control"]
         and reader.get("lastMovingTick") == moving_summary(meter["lastMovingTick"]),
         "matrix control cleanup differs")
    need(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
         "matrix control private session did not close")
    return [dict(claim=c, name=n, value=1, expected=1, operator="eq", passed=True) for c, n in RULES]


class MatrixControlNegative:
    def __init__(self, fault):
        need(fault in FAULTS, "unknown matrix control fault")
        self.fault, self.applied = fault, False
        self.baseline = MatrixNegative(fault) if fault in BASELINE_FAULTS else None

    def mutate(self, row, subjects):
        if self.baseline:
            result = self.baseline.mutate(row, subjects)
            self.applied = self.baseline.applied
            return result
        if self.applied or row.get("command") != "walk-matrix.calibrate":
            return row
        result = deepcopy(row)
        receipt = result.get("receipt", {})
        control = receipt.get("calibration")
        if self.fault == "matrix-control-missing-control":
            receipt.pop("calibration", None)
            self.applied = True
        elif isinstance(control, dict):
            if self.fault == "matrix-control-wrong-byte": control["bad"]["rawHex"] = control["clean"]["motion"]["rawHex"]
            elif self.fault == "matrix-control-unrestored": control["restored"]["motion"]["rawHex"] = control["bad"]["rawHex"]
            elif self.fault == "matrix-control-clock": control["restoredClock"]["nativeCycle"] += 1
            elif self.fault == "matrix-control-registers": control["restoredRegisters"]["r0"] ^= 1
            elif self.fault == "matrix-control-address": control["changedAddress"] += 1
            elif self.fault == "matrix-control-missing-moving-tick": control["priorMovingTick"]["entryElapsed"] += 1
            self.applied = True
        return result if self.applied else row


def validate_negative_result(result, fault):
    if fault in BASELINE_FAULTS:
        from tools.overworld.devtools_walk_matrix_proof import KIND as MATRIX_KIND
        copied = deepcopy(result)
        meter = copied.get("measurements", {}).get(KIND, {})
        baseline = deepcopy(meter.get("natural", meter))
        # The wrapper owns finish and close. Its exact baseline finish failure
        # can be newer than the compact natural.result() nested in the report.
        # Preserve that cause; do not replace it with a generic incomplete pass.
        baseline["failures"] = list(dict.fromkeys(
            baseline.get("failures", []) + meter.get("failures", [])))
        copied.setdefault("measurements", {})[MATRIX_KIND] = baseline
        return validate_matrix_negative(copied, fault)
    need(fault in CONTROL_FAULTS and result.get("passed") is False, "matrix control copied fault did not fail")
    failures = result.get("failures", []) + result.get("measurements", {}).get(KIND, {}).get("failures", [])
    reasons = set()
    for value in failures:
        if isinstance(value, str): reasons.add(value)
        elif isinstance(value, dict):
            reasons.update(value[k] for k in ("detail", "message") if isinstance(value.get(k), str))
    expected = {
        "matrix-control-missing-control": "matrix control is missing or not restored",
        "matrix-control-wrong-byte": "matrix control bad state or restoration differs",
        "matrix-control-unrestored": "matrix control bad state or restoration differs",
        "matrix-control-clock": "matrix control clocks differ",
        "matrix-control-registers": "matrix control registers differ",
        "matrix-control-address": "matrix control address differs",
        "matrix-control-missing-moving-tick": "matrix control lacks actual completed moving Tick",
    }[fault]
    need(expected in reasons, "matrix control copied fault failed for unrelated reason: " + fault)
