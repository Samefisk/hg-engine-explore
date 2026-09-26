"""Acceptance rows and copied-data controls for prompt follower resume."""
from __future__ import annotations

from copy import deepcopy

from tools.overworld.devtools_mount_detach_follower_resume import (
    KIND, LIFECYCLE, MAX_RESUME_FRAMES, REQUIREMENT, require,
)
from tools.overworld.normal_play_observer import complete_travel


CLAIMS = (
    "natural-input", "live-actor-identity", "profile-resolution", "engine-boundary",
    "logical-commit", "rendered-motion", "frame-pacing", "control-release",
)
FAULTS = (
    "detach-resume-absent-subject",
    "detach-resume-missing-actor-rebound",
    "detach-resume-missing-control-rebound",
    "detach-resume-changed-profile",
    "detach-resume-delayed-motion",
)


def _spec(name, expected, *, operator="eq", value_type=None):
    return {
        "name": name,
        "operator": operator,
        "type": value_type or ("array" if isinstance(expected, list)
                               else "integer" if isinstance(expected, int)
                               else "string"),
        "validator": "meaningful-observation",
        "expected": deepcopy(expected),
    }


def contract():
    return {
        "natural-input": [
            _spec("mount-detach-select-and-player-clearance", [1, 1]),
        ],
        "live-actor-identity": [
            _spec("mount-detach-follower-role", "FOLLOWER"),
            _spec("mount-detach-same-cyndaquil-identity", [1, 155, 7, 1, 1]),
        ],
        "profile-resolution": [
            _spec("mount-detach-policy-transition", [1, 1, 1]),
        ],
        "engine-boundary": [
            _spec("mount-detach-rebound-and-generation-counts", [1, 1, 1, 1]),
        ],
        "logical-commit": [
            _spec("mount-detach-first-follower-commit-count", 1),
        ],
        "rendered-motion": [
            _spec("mount-detach-first-follower-walk", [1, 1, 1]),
        ],
        "frame-pacing": [
            _spec("mount-detach-follower-clearance-resume-frame-count", MAX_RESUME_FRAMES,
                  operator="lte"),
        ],
        "control-release": [
            _spec("mount-detach-follower-terminal-control", [0, 1, 1]),
        ],
    }


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    require(replay.get("passed") is True and replay.get("failures") == []
            and meter.get("passed") is True and meter.get("ready") is True
            and meter.get("closed") is True and meter.get("acceptedProof") is False
            and meter.get("failures") == []
            and meter.get("requirements") == [REQUIREMENT],
            "detach follower resume lacks a closed independent replay")
    require(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": []},
        "detach follower resume session did not close cleanly")
    initial, terminal = meter["initial"], meter["terminal"]
    subject = meter["subject"]
    first = next(item for item in initial["actors"]
                 if item.get("handle") == subject["handle"])
    last = next(item for item in terminal["actors"]
                if item.get("handle") == subject["handle"])
    require(first["role"] == "MOUNTED" and last["role"] == "FOLLOWER"
            and first["species"] == last["species"] == 155
            and first["subjectIdentity"] == last["subjectIdentity"]
            and first["handle"] == last["handle"]
            and last.get("identityVerified") is True
            and last.get("presentationAttached") is True,
            "detach follower resume identity differs")
    require(first["behaviorFingerprint"] != last["behaviorFingerprint"]
            and first["matchedLayerMask"] != last["matchedLayerMask"],
            "detach follower policy identity was not restored")
    rebounds = meter["reboundEvents"]
    require(len(rebounds) == 2
            and [event["data"].get("event") for event in rebounds]
            == ["ACTOR_REBOUND", "CONTROL_REBOUND"]
            and [(event["data"].get("valueA"), event["data"].get("valueB"))
                 for event in rebounds] == [(3, 2), (1, 0)],
            "detach follower rebound receipts differ")
    motion = meter["motion"]
    require(complete_travel(motion) and motion["kind"] == "WALK"
            and motion["handle"] == first["handle"]
            and motion["fingerprint"] == last["behaviorFingerprint"]
            and motion["commitAfter"] == (motion["commitBefore"] + 1) & 0xFFFFFFFF
            and motion["terminalLogical"] == motion["target"]
            and [motion["terminalRender"][0], motion["terminalRender"][2]]
            == [(value << 16) + 32768 for value in motion["target"]],
            "detach follower first rendered Walk differs")
    events = meter["motionEvents"]
    names = [event["data"].get("event") for event in events]
    require(names.count("INTENT_CREATED") >= 1
            and names.count("PLAN_ACCEPTED") >= 1
            and all(names.count(name) == 1 for name in LIFECYCLE),
            "detach follower first normal lifecycle differs")
    latency = max(0, meter["motionStartFrame"] - meter["clearanceFrame"])
    require(latency <= MAX_RESUME_FRAMES,
            "detach follower resume latency exceeded")
    values = {
        "mount-detach-select-and-player-clearance": [
            int(type(meter["selectFrame"]) is int),
            int(type(meter["clearanceFrame"]) is int),
        ],
        "mount-detach-follower-role": last["role"],
        "mount-detach-same-cyndaquil-identity": [
            int(first["handle"] == last["handle"]), last["species"],
            last["handle"]["slot"], int(last["identityVerified"]),
            int(last["presentationAttached"]),
        ],
        "mount-detach-policy-transition": [
            int(first["behaviorFingerprint"] != last["behaviorFingerprint"]),
            int(first["matchedLayerMask"] != last["matchedLayerMask"]),
            int(motion["fingerprint"] == last["behaviorFingerprint"]),
        ],
        "mount-detach-rebound-and-generation-counts": [
            int(rebounds[0]["data"]["event"] == "ACTOR_REBOUND"),
            int(rebounds[1]["data"]["event"] == "CONTROL_REBOUND"),
            last["authorityGeneration"] - first["authorityGeneration"],
            last["engineAnchorGeneration"] - first["engineAnchorGeneration"],
        ],
        "mount-detach-first-follower-commit-count":
            motion["commitAfter"] - motion["commitBefore"],
        "mount-detach-first-follower-walk": [
            int(complete_travel(motion)), int(motion["kind"] == "WALK"),
            int(motion["terminalLogical"] == motion["target"]),
        ],
        "mount-detach-follower-clearance-resume-frame-count": latency,
        "mount-detach-follower-terminal-control": [
            last["inputOwnership"],
            int(names.count("CONTROL_RETURNED") == 1),
            int(next(event for event in events
                     if event["data"].get("event") == "CONTROL_RETURNED")
                ["data"].get("valueA") == 0),
        ],
    }
    rows = []
    for claim, specs in contract().items():
        for spec in specs:
            value = values[spec["name"]]
            expected = spec["expected"]
            require(value == expected if spec["operator"] == "eq"
                    else type(value) is int and value <= expected,
                    "detach follower proof failed " + spec["name"])
            rows.append({
                "claim": claim, "name": spec["name"], "value": deepcopy(value),
                "operator": spec["operator"], "expected": deepcopy(expected),
                "passed": True,
            })
    return rows


class MountDetachFollowerResumeNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown detach follower copied-data fault")
        self.fault = fault
        self.applied = False
        self.follower_policy = None

    def mutate(self, row, subjects):
        if self.applied and self.fault != "detach-resume-delayed-motion":
            return row
        if row.get("phase") != "observe" or not subjects:
            return row
        changed = deepcopy(row)
        handles = {item["handle"]["value"] for item in subjects.values()}
        for snapshot in changed.get("samples", []):
            actor = next((item for item in snapshot.get("actors", [])
                          if item.get("handle", {}).get("value") in handles), None)
            if actor is None:
                continue
            if self.fault == "detach-resume-absent-subject":
                snapshot["actors"].remove(actor)
                self.applied = True
                break
            if self.fault == "detach-resume-changed-profile" \
                    and actor.get("role") == "FOLLOWER":
                policy = (actor["behaviorFingerprint"], actor["matchedLayerMask"])
                if self.follower_policy is None:
                    self.follower_policy = policy
                else:
                    actor["behaviorFingerprint"] ^= 1
                    self.applied = True
                    break
            if self.fault == "detach-resume-delayed-motion" \
                    and actor.get("role") == "FOLLOWER":
                actor.update(motionKind="NONE", motionKindId=0,
                             motionPhase="IDLE", motionElapsed=0,
                             motionDuration=0, reservationId=0)
                actor["origin"] = deepcopy(actor["logical"])
                actor["target"] = deepcopy(actor["logical"])
                self.applied = True
        for event in changed.get("events", []):
            data = event.get("data", {})
            if data.get("actorHandle") not in handles:
                continue
            wanted = {
                "detach-resume-missing-actor-rebound": "ACTOR_REBOUND",
                "detach-resume-missing-control-rebound": "CONTROL_REBOUND",
            }.get(self.fault)
            if wanted and data.get("event") == wanted:
                data["event"] = "WORLD_EFFECT"
                self.applied = True
                break
            if self.fault == "detach-resume-delayed-motion" \
                    and data.get("event") in {
                        "INTENT_CREATED", "PLAN_ACCEPTED", *LIFECYCLE,
                    }:
                data["event"] = "WORLD_EFFECT"
                self.applied = True
        return changed if self.applied else row


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "detach follower copied control did not fail")
    failures = result.get("failures", []) + result.get("measurements", {}).get(
        KIND, {}).get("failures", [])
    reasons = []
    for item in failures:
        if isinstance(item, str):
            reasons.append(item)
        elif isinstance(item, dict):
            reasons.extend(item[key] for key in ("detail", "message")
                           if isinstance(item.get(key), str))
    expected = {
        "detach-resume-absent-subject": "missing or duplicate detach follower subject",
        "detach-resume-missing-actor-rebound": "role change lacks exact detach rebound receipts",
        "detach-resume-missing-control-rebound": "role change lacks exact detach rebound receipts",
        "detach-resume-changed-profile": "restored follower policy identity changed",
        "detach-resume-delayed-motion": "follower resume latency exceeded",
    }[fault]
    require(expected in reasons,
            "detach follower copied control failed for an unrelated reason: " + fault)
