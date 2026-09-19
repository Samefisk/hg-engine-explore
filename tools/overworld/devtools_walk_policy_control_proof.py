"""Controller contract and copied-data controls for the live Walk policy reader."""
from copy import deepcopy

KIND = "live-walk-policy-control-v1"
REQUIREMENT = "shared.walk-policy-recorder-control-v1"
RULES = (("live-actor-identity", "bound-control-subject"),
         ("controlled-action", "same-reader-counter-fault"),
         ("controlled-action", "exact-restoration"),
         ("controlled-action", "complete-walk-lifecycle"))
MEANINGS = {"walk-policy-missing-start": "MOTION_STARTED",
            "walk-policy-missing-commit": "LOGICAL_COMMIT",
            "walk-policy-missing-finish": "MOTION_FINISHED",
            "walk-policy-missing-return": "CONTROL_RETURNED"}
FAULTS = ("walk-policy-absent-subject", "walk-policy-stale-subject",
          "walk-policy-missing-control", "walk-policy-wrong-byte",
          "walk-policy-unrestored", "walk-policy-clock", *MEANINGS)


def contract():
    result = {}
    for claim, name in RULES:
        result.setdefault(claim, []).append(dict(name=name, operator="eq", type="integer",
            validator="meaningful-observation", expected=1))
    return result


def measurements(replay, record, *, policy_address):
    meter = replay.get("measurements", {}).get(KIND, {})
    if replay.get("passed") is not True or replay.get("failures") != [] \
            or meter.get("passed") is not True or meter.get("ready") is not True \
            or meter.get("acceptedProof") is not False or meter.get("failures") != []:
        raise ValueError("Walk policy control lacks a complete independent replay")
    subject, control = meter.get("subject"), meter.get("control", {})
    if not subject or control.get("subject") != subject or control.get("state") != "complete" \
            or control.get("cleanupPending") is not False or control.get("failure") is not None:
        raise ValueError("Walk policy control lacks its exact restored subject")
    receipt = control.get("receipt", {})
    if type(policy_address) is not int or receipt.get("policyAddress") != policy_address:
        raise ValueError("Walk policy control address differs from the current descriptor")
    cleanup = meter.get("cleanup", {})
    if cleanup.get("closed") is not True or cleanup.get("advancedFrames") != 0 \
            or cleanup.get("acceptedProof") is not False or cleanup.get("walkPolicyControl") != control:
        raise ValueError("Walk policy reader cleanup differs")
    if len(meter.get("motions", [])) != 1 or not meter.get("commit"):
        raise ValueError("Walk policy control lacks one complete ordinary Walk")
    for meaning in MEANINGS.values():
        if sum(e.get("data", {}).get("event") == meaning for e in meter.get("traces", [])) != 1:
            raise ValueError("Walk policy control lacks native " + meaning)
    if record.get("sessionCleanup") != dict(sessionId=record.get("sessionId"), closed=True, errors=[]):
        raise ValueError("Walk policy control private session did not close cleanly")
    return [dict(claim=c, name=n, value=1, operator="eq", expected=1, passed=True) for c, n in RULES]


class WalkPolicyNegative:
    """Mutate one retained meaning, not live memory or sequence watermarks."""
    def __init__(self, fault):
        if fault not in FAULTS:
            raise ValueError("unknown Walk policy copied-data fault")
        self.fault, self.applied = fault, False

    def mutate(self, row, subjects):
        if self.applied or row.get("phase") != "observe" or not row.get("samples") or not subjects:
            return row
        result = deepcopy(row)
        handles = {s["handle"]["value"] for s in subjects.values()}
        for sample in result["samples"]:
            actor = next((a for a in sample.get("actors", []) if a.get("handle", {}).get("value") in handles), None)
            if actor is not None and self.fault == "walk-policy-absent-subject":
                sample["actors"].remove(actor)
                self.applied = True
            elif actor is not None and self.fault == "walk-policy-stale-subject":
                actor["authorityGeneration"] += 1
                self.applied = True
            value = sample.get("walkPolicyControl")
            if not self.applied and isinstance(value, dict) and value.get("state") == "complete":
                if self.fault == "walk-policy-missing-control":
                    sample.pop("walkPolicyControl")
                    self.applied = True
                elif self.fault in ("walk-policy-wrong-byte", "walk-policy-unrestored", "walk-policy-clock"):
                    receipt = value["receipt"]
                    if self.fault == "walk-policy-wrong-byte": receipt["bad"] = deepcopy(receipt["clean"])
                    elif self.fault == "walk-policy-unrestored": receipt["restored"] = deepcopy(receipt["bad"])
                    else: receipt["restoredClock"]["nativeCycle"] += 1
                    self.applied = True
            if self.applied: break
        if not self.applied and self.fault in MEANINGS:
            for event in result.get("events", []):
                data = event.get("data", {})
                if event.get("kind") == "native" and data.get("actorHandle") in handles \
                        and data.get("event") == MEANINGS[self.fault]:
                    data["event"] = "WORLD_EFFECT"
                    self.applied = True
                    break
        return result if self.applied else row


def validate_negative_result(result, fault):
    if fault not in FAULTS or result.get("passed") is not False:
        raise ValueError("Walk policy copied control did not fail")
    failures = result.get("failures", []) + result.get("measurements", {}).get(KIND, {}).get("failures", [])
    reasons = {e.get(k) for e in failures for k in ("detail", "message") if isinstance(e.get(k), str)}
    if fault in MEANINGS:
        expected = "Walk control native lifecycle differs: " + MEANINGS[fault]
    else:
        expected = {"walk-policy-absent-subject": "selected handle must name exactly one current active actor",
            "walk-policy-stale-subject": "selected actor has a stale authorityGeneration",
            "walk-policy-missing-control": "Walk reader control failed, is pending, or has a different subject",
            "walk-policy-wrong-byte": "same reader fault or exact restoration differs",
            "walk-policy-unrestored": "same reader fault or exact restoration differs",
            "walk-policy-clock": "same reader fault or exact restoration differs"}[fault]
    if expected not in reasons:
        raise ValueError("Walk policy copied control failed for an unrelated reason: " + fault)
