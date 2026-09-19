"""Bounded copied-data faults for the unchanged unmounted route checker."""
from copy import deepcopy

from tools.overworld.route_control_negatives import (
    MEANINGS, RouteControlNegative, validate_negative_result as validate_route_result,
)

BASE_FAULTS = ("absent-subject", "stale-subject", *MEANINGS)
FAULTS = (*BASE_FAULTS, "cadence-cpu-hitch", "cadence-player-start-stall")
KIND = "unmounted-cadence-v1"
GAME_KIND = "unmounted-game-cadence-v1"


def validate_negative_result(fault, result, *, kind=KIND):
    if fault not in FAULTS or not isinstance(result, dict) or result.get("passed") is not False:
        raise ValueError("cadence negative control did not fail")
    measurements = result.get("measurements")
    meter = measurements.get(kind) if isinstance(measurements, dict) else None
    if not isinstance(meter, dict):
        raise ValueError("cadence negative control lacks its measurement")
    if fault in BASE_FAULTS:
        return validate_route_result(fault, {**result, "measurements": {"live-route-control-v1": meter}})
    code = {"cadence-cpu-hitch": "host-process-cpu-hitch",
            "cadence-player-start-stall": "player-render-start-stall"}[fault]
    failures = meter.get("failures")
    if not isinstance(failures, list) or not any(
            isinstance(error, dict) and error.get("code") == code for error in failures):
        raise ValueError("cadence negative control failed for another reason: " + fault)
    return True


class CadenceNegative:
    def __init__(self, fault):
        if fault not in FAULTS:
            raise ValueError("unknown cadence copied-data fault")
        self.fault = fault
        self.applied = False
        self.delegate = RouteControlNegative(fault) if fault in BASE_FAULTS else None
        self.pin = None
        self.pin_count = 0

    def mutate(self, row, subjects):
        if self.delegate is not None:
            result = self.delegate.mutate(row, subjects)
            self.applied = self.delegate.applied
            return result
        if not isinstance(row, dict) or row.get("phase") != "observe" or not row.get("samples"):
            return row
        if self.applied and (self.fault == "cadence-cpu-hitch" or self.pin_count == 4):
            return row
        values = subjects.values() if isinstance(subjects, dict) else subjects
        selected = [s for s in values if isinstance(s, dict) and s.get("species") == 155
                    and s.get("role") == "FOLLOWER"]
        if len(selected) != 1:
            if self.pin is not None:
                raise ValueError("cadence pin lost its bound subject")
            return row
        subject = selected[0]
        if self.fault == "cadence-cpu-hitch":
            for index, interval in enumerate(row.get("cycleIntervals", [])):
                if type(interval.get("cpuNs")) is int and 0 < interval["cpuNs"] < 10**12:
                    result = deepcopy(row)
                    result["cycleIntervals"][index]["cpuNs"] = 10**12
                    if "callbackCosts" in result["cycleIntervals"][index]:
                        # Inject CPU work outside the measured callbacks. Its
                        # copied envelope must name the same changed total;
                        # otherwise this checks transport, not the hitch rule.
                        result["cycleIntervals"][index]["callbackCosts"]["totalCpuNs"] = 10**12
                    self.applied = True
                    return result
            return row
        result = row
        for index, sample in enumerate(row["samples"]):
            if self.pin_count == 4:
                break
            if self.pin is None:
                admissions = [event.get("data", {}) for event in row.get("events", [])
                    if event.get("kind") == "native-observation" and event.get("frame") == sample.get("frame")
                    and event.get("data", {}).get("observation") == "player-step-admitted"]
                if not admissions:
                    continue
                if len(admissions) != 1:
                    raise ValueError("cadence pin needs one actual admission")
                before = admissions[0].get("objectBefore", {})
                if any(type(before.get(key)) is not int for key in ("pos_x", "pos_z")):
                    raise ValueError("cadence pin lacks admitted origin")
                self.pin = {"origin": (before["pos_x"], before["pos_z"]),
                    "context": deepcopy(sample.get("context")), "subject": deepcopy(subject),
                    "nextFrame": sample["frame"], "action": row.get("action")}
            if sample.get("frame") != self.pin["nextFrame"] or sample.get("context") != self.pin["context"] \
                    or subject != self.pin["subject"] or row.get("action") != self.pin["action"]:
                raise ValueError("cadence pin lost its same-step frame window")
            if result is row:
                result = deepcopy(row)
            player = result["samples"][index]["player"]
            player["pos_x"], player["pos_z"] = self.pin["origin"]
            self.pin_count += 1
            self.pin["nextFrame"] += 1
            self.applied = True
        return result
