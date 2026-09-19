"""Separate terminal Crash reader control; never a substitute for gameplay proof."""
from copy import deepcopy

from .devtools_mounted_crash_control_measurement import KIND, REQUIREMENT, validate_control
from .devtools_mounted_crash_control import BAD_MODE, EXPECTED_COUNTS
from .devtools_mounted_crash_proof import CrashNegative, FAULTS as BASELINE_FAULTS
from .devtools_mounted_crash_proof import validate_negative_result as validate_baseline_negative

RULES = (("live-actor-identity", "bound-crash-control-subject"),
         ("controlled-action", "same-reader-mode-fault"),
         ("controlled-action", "exact-mode-restoration"))
CLAIMS = tuple(dict.fromkeys(claim for claim, _ in RULES))
CONTROL_FAULTS = ("crash-control-missing", "crash-control-byte", "crash-control-restore",
                  "crash-control-clock", "crash-control-registers", "crash-control-address",
                  "crash-control-guard", "crash-control-latch")
FAULTS = (*BASELINE_FAULTS, *CONTROL_FAULTS)


def need(value, reason):
    if not value:
        raise ValueError(reason)


def contract():
    result = {}
    for claim, name in RULES:
        result.setdefault(claim, []).append(dict(name=name, operator="eq", type="integer",
            validator="meaningful-observation", expected=1))
    return result


def measurements(replay, record):
    from .devtools_mounted_crash_proof import validate_baseline
    meter = replay.get("measurements", {}).get(KIND, {})
    need(replay.get("passed") is True and replay.get("failures") == []
         and all(meter.get(key) is True for key in ("passed", "ready", "closed"))
         and meter.get("acceptedProof") is False and meter.get("failures") == [],
         "Crash control lacks closed independent replay")
    natural = meter["natural"]
    validate_baseline(natural)
    need(meter["subject"] == natural["subject"], "Crash control baseline subject differs")
    terminal, calibration, cleanup = meter["terminal"], meter["calibrationReceipt"], meter["cleanup"]
    validate_control(meter["control"], meter["control"]["terminalCrashReceipt"], terminal, meter["subject"])
    need(calibration.get("terminalGuard") is True and calibration.get("advancedFrames") == 0
         and calibration.get("prepared") is True and calibration.get("acceptedProof") is False
         and calibration.get("calibration") == meter["control"], "Crash control runtime guard differs")
    reader = cleanup["crashFeedback"]
    need(cleanup.get("closed") is True and cleanup.get("advancedFrames") == 0
         and cleanup.get("acceptedProof") is False and reader == calibration["crashFeedback"]
         and reader.get("armed") is True and reader.get("closed") is True
         and reader.get("failure") == BAD_MODE and reader.get("guestMemoryWrites") == 2
         and reader.get("calibration") == meter["control"] and reader.get("counts") == EXPECTED_COUNTS
         and reader.get("subject") == meter["subject"], "Crash control terminal reader differs")
    for receipt in (calibration, cleanup):
        need(receipt["snapshot"] == terminal, "Crash control terminal snapshot differs")
    # The meter authenticates the transition from the natural completed queue
    # to the calibrated same queue. Do not forge a natural close or pass flag.
    need(all(natural["terminalSnapshot"].get(key) == terminal.get(key) for key in
             ("frame", "actorFrame", "nativeCycle", "actors", "player", "context", "selector")),
         "Crash control moved after natural recovery")
    need(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
         "Crash control private session did not close")
    return [dict(claim=claim, name=name, value=1, expected=1, operator="eq", passed=True)
            for claim, name in RULES]


class CrashControlNegative:
    def __init__(self, fault):
        need(fault in FAULTS, "unknown Crash control copied fault")
        self.fault, self.applied = fault, False
        self.baseline = CrashNegative(fault) if fault in BASELINE_FAULTS else None

    def mutate(self, row, subjects):
        if self.baseline:
            result = self.baseline.mutate(row, subjects)
            self.applied = self.baseline.applied
            return result
        if self.applied or row.get("command") != "crash.calibrate":
            return row
        result = deepcopy(row)
        receipt = result.get("receipt", {})
        control = receipt.get("calibration")
        if self.fault == "crash-control-guard":
            receipt["terminalGuard"] = False
        elif self.fault == "crash-control-missing":
            receipt.pop("calibration", None)
        elif isinstance(control, dict):
            if self.fault == "crash-control-byte": control["bad"]["mountStateHex"] = control["clean"]["sample"]["mountStateHex"]
            elif self.fault == "crash-control-restore": control["restored"]["sample"]["mountStateHex"] = control["bad"]["mountStateHex"]
            elif self.fault == "crash-control-clock": control["restoredClock"]["nativeCycle"] += 1
            elif self.fault == "crash-control-registers": control["restoredRegisters"]["r0"] ^= 1
            elif self.fault == "crash-control-address": control["changedAddress"] += 1
            elif self.fault == "crash-control-latch": control["readerFailure"] = None
        else:
            return row
        self.applied = True
        return result


def validate_negative_result(result, fault):
    if fault in BASELINE_FAULTS:
        from .devtools_mounted_crash_proof import KIND as BASELINE_KIND
        copied = deepcopy(result)
        meter = copied.get("measurements", {}).get(KIND, {})
        natural = deepcopy(meter.get("natural", meter))
        natural["failures"] = natural.get("failures", []) + meter.get("failures", [])
        copied.setdefault("measurements", {})[BASELINE_KIND] = natural
        return validate_baseline_negative(copied, fault)
    need(fault in CONTROL_FAULTS and result.get("passed") is False, "Crash control copied fault did not fail")
    expected = {
        "crash-control-missing": "missing restoration or terminal failure latch",
        "crash-control-byte": "same-reader fault or exact restoration differs",
        "crash-control-restore": "same-reader fault or exact restoration differs",
        "crash-control-clock": "execution clocks differ", "crash-control-registers": "registers differ",
        "crash-control-address": "mode address or bytes differ",
        "crash-control-guard": "runtime terminal guard or boundary differs",
        "crash-control-latch": "missing restoration or terminal failure latch",
    }[fault]
    reasons = []
    def collect(value):
        if isinstance(value, str): reasons.append(value)
        elif isinstance(value, dict):
            for item in value.values(): collect(item)
        elif isinstance(value, list):
            for item in value: collect(item)
    collect(result.get("failures", []))
    collect(result.get("measurements", {}).get(KIND, {}).get("failures", []))
    need(any("Crash control " + expected in reason for reason in reasons),
         "Crash control copied fault failed for unrelated reason: " + fault)
