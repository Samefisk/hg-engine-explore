"""Exact legacy Mankey arc rows from closed independent shared replay."""
from copy import deepcopy

from .devtools_mounted_hop_arc import KIND, REQUIREMENT, DIRECTIONS
from .devtools_mount_control_stress import LIFECYCLE, require
from .normal_play_observer import complete_travel
from .devtools_records import select_current_actor
from .devtools_mount_control_stress import check_snapshot_pair

CLAIMS = ("natural-input", "live-actor-identity", "rendered-motion", "control-release")
FAULTS = ("hop-arc-absent-subject", "hop-arc-stale-subject", "hop-arc-missing-start",
          "hop-arc-bad-height", "hop-arc-missing-finish")


def contract():
    def row(name, **extra):
        return dict(name=name, operator="eq", type="integer", validator="meaningful-observation", **extra)
    return {
        "natural-input": [row("started-hop-count", expected=3)],
        "live-actor-identity": [dict(name="mankey-hops-identity", operator="eq", type="array",
                                      validator="meaningful-observation", expected=[1, "MOUNTED", 56, 1])],
        "rendered-motion": [dict(name="hop-arc-samples", operator="eq", type="object",
                                  validator="hop-arc-parabola-v1", caseCount=3, requiredKeys=["cases"])],
        "control-release": [row("recovered-hop-count", expected=3)],
    }


def measurements(result):
    meter = result.get("measurements", {}).get(KIND, result)
    require(result.get("passed") is True and result.get("failures") == []
            and meter.get("passed") is True and meter.get("closed") is True
            and meter.get("acceptedProof") is False and meter.get("failures") == []
            and meter.get("contract") == REQUIREMENT, "Hop arc lacks closed independent replay")
    actor = meter["initial"]["actor"]
    require(actor["species"] == 56 and actor["role"] == "MOUNTED" and actor["inputOwnership"] == 1
            and actor["identityVerified"] is True and actor["presentationAttached"] is True
            and actor["handle"] == meter["subject"]["handle"], "Hop arc proof subject differs")
    cases = meter["cases"]
    require(len(cases) == 3, "Hop arc proof requires three cases")
    output = []
    prior = meter["initial"]["frame"]
    for case, (_, mask, direction) in zip(cases, DIRECTIONS):
        summary = case["summary"]; motion = summary["motion"]
        receipt = case["startReceipt"]; data = receipt["data"]; start = data["start"]
        duration = motion["duration"]
        first = case["startSnapshot"]
        select_current_actor(first, meter["subject"])
        first_actor = next(a for a in first["actors"] if a["handle"] == actor["handle"])
        check_snapshot_pair(first, first_actor)
        require(first["frame"] == receipt["frame"] == motion["startFrame"]
                and first["context"] == meter["initial"]["context"]
                and first["selector"]["rawHeld"] & 0xF0 == mask
                and first_actor["reservationId"] == start["motionIdentity"]
                and case["previousNativeCycle"] <= data["entryNativeCycle"]
                    <= data["returnNativeCycle"] <= first["nativeCycle"], "Hop proof start boundary differs")
        require(complete_travel(motion) and motion["kind"] == "HOP"
                and motion["handle"] == actor["handle"] and motion["fingerprint"] == actor["behaviorFingerprint"]
                and motion["commitAfter"] == (motion["commitBefore"] + 1) & 0xFFFFFFFF
                and motion["terminalLogical"] == motion["target"], "Hop proof motion differs")
        require(receipt["kind"] == "native-observation" and data["observation"] == "mounted-hop-start"
                and data["subject"] == meter["subject"] and start["elapsed"] == 0
                and start["duration"] == duration and start["motionIdentity"] > 0
                and [start["origin"][k] for k in ("x", "y")] == motion["origin"]
                and [start["target"][k] for k in ("x", "y")] == motion["target"]
                and start["faceY"] == start["baseFaceY"], "Hop proof native start differs")
        require(tuple((b > a) - (b < a) for a, b in zip(motion["origin"], motion["target"])) == direction,
                "Hop proof cardinal order differs")
        require(prior < motion["startFrame"] <= motion["commitFrame"] <= motion["finishFrame"]
                == case["terminalFrame"] <= meter["initial"]["frame"] + meter["frames"], "Hop proof frame order differs")
        prior = motion["finishFrame"]
        events = summary["lifecycle"]
        require([e["event"] for e in events] == list(LIFECYCLE)
                and all(e["reason"] == "OK" and e["actorHandle"] == actor["handle"]["value"] for e in events)
                and [(e["valueA"], e["valueB"]) for e in events] == [(2, duration), (motion["commitAfter"], 2),
                    (motion["commitAfter"], 2), (1, motion["commitAfter"])]
                and [e["sequence"] for e in events] == sorted(set(e["sequence"] for e in events)),
                "Hop proof lifecycle differs")
        expected = [[i, 16 * (((4 * i * (duration - i) // duration) << 12) // duration)]
                    for i in range(duration + 1)]
        observed = case["observations"]
        require(case["samples"] == expected and len(observed) == duration
                and [[s["elapsed"], s["faceY"] - start["baseFaceY"]] for s in observed] == expected[1:]
                and [s["frame"] for s in observed] == list(range(motion["startFrame"], motion["startFrame"] + duration)),
                "Hop proof parabola/observation differs")
        terminal = case["terminalActor"]
        require(terminal["handle"] == actor["handle"] and terminal["species"] == 56
                and terminal["role"] == "MOUNTED" and terminal["motionPhase"] == "IDLE"
                and terminal["reservationId"] == 0 and terminal["inputOwnership"] == 1,
                "Hop proof terminal control differs")
        output.append(dict(duration=duration, samples=deepcopy(case["samples"])))
    values = (3, [1, "MOUNTED", 56, 1], dict(cases=output), 3)
    return [dict(claim=claim, name=contract()[claim][0]["name"], operator="eq", actual=value,
                 expected=deepcopy(value)) for claim, value in zip(CLAIMS, values)]


class MountedHopArcNegative:
    """Change one copied observation fact; never touch the live session."""
    def __init__(self, fault):
        require(fault in FAULTS, "unknown Hop arc negative fault")
        self.fault, self.applied = fault, False

    def mutate(self, row, subjects):
        if self.applied or row.get("phase") != "observe" or not subjects:
            return row
        changed = deepcopy(row)
        handles = {subject["handle"]["value"] for subject in subjects.values()}
        for sample in changed.get("samples", []):
            actor = next((item for item in sample.get("actors", [])
                          if item.get("handle", {}).get("value") in handles), None)
            if actor is None:
                continue
            if self.fault == "hop-arc-absent-subject":
                sample["actors"].remove(actor)
                self.applied = True
            elif self.fault == "hop-arc-stale-subject":
                actor["authorityGeneration"] += 1
                self.applied = True
            elif self.fault == "hop-arc-bad-height" and actor.get("motionKind") == "HOP" \
                    and actor.get("motionElapsed") == 2:
                actor["engineObject"]["face_y"] += 1
                sample["player"]["face_y"] += 1
                self.applied = True
            if self.applied:
                break
        if not self.applied:
            for event in changed.get("events", []):
                data = event.get("data", {})
                if self.fault == "hop-arc-missing-start" \
                        and data.get("observation") == "mounted-hop-start":
                    data["observation"] = "mounted-hop-start-removed"
                    self.applied = True
                elif self.fault == "hop-arc-missing-finish" and event.get("kind") == "native" \
                        and data.get("actorHandle") in handles and data.get("event") == "MOTION_FINISHED":
                    data["event"] = "WORLD_EFFECT"
                    self.applied = True
                if self.applied:
                    break
        return changed if self.applied else row


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "Hop arc copied control did not fail")
    failures = result.get("failures", []) + result.get("measurements", {}).get(KIND, {}).get("failures", [])
    reasons = []
    def collect(item):
        if isinstance(item, str):
            reasons.append(item)
        elif isinstance(item, dict):
            for value in item.values():
                collect(value)
        elif isinstance(item, list):
            for value in item:
                collect(value)
    collect(failures)
    expected = {
        "hop-arc-absent-subject": "missing or duplicate mounted subject",
        "hop-arc-stale-subject": "ownership changed",
        "hop-arc-missing-start": "missing real native Hop start receipt",
        "hop-arc-bad-height": "Hop arc parabola differs",
        "hop-arc-missing-finish": "missing/duplicate native MOTION_FINISHED",
    }[fault]
    require(any(expected in reason for reason in reasons),
            "Hop arc copied control failed for an unrelated reason: " + fault)
