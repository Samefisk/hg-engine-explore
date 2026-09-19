"""Controller checks for the original four acceleration claims.

Package authentication and current recorder calibration remain controller duties.
Copied-data controls below test the evaluator, not the native reader.
"""
from copy import deepcopy

KIND = "acceleration-parity-v1"
REQUIREMENT = "legacy.acceleration-parity"
CLAIMS = ["live-actor-identity", "profile-resolution", "logical-commit", "engine-boundary"]
NAMES = ("observed-role-counts", "stable-profile-fingerprints", "consecutive-terminal-commits", "terminal-policy-states")
FAULTS = ("acceleration-absent-subject", "acceleration-missing-policy",
          "acceleration-missing-native-commit", "acceleration-wrong-policy-counter",
          "acceleration-wrong-duration", "acceleration-bad-reset")


def contract():
    specs = (
        dict(type="array", validator="meaningful-observation", expected=[7, 7]),
        dict(type="object", validator="acceleration-terminal-series-v1", aspect="profile",
             requiredKeys=["initials", "series", "durations"]),
        dict(type="object", validator="acceleration-terminal-series-v1", aspect="commits",
             requiredKeys=["initials", "series"]),
        dict(type="integer", validator="meaningful-observation", expected=14))
    return {claim: [dict(name=name, operator="eq", **spec)]
            for claim, name, spec in zip(CLAIMS, NAMES, specs)}


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    if replay.get("passed") is not True or replay.get("failures") != [] \
            or meter.get("passed") is not True or meter.get("acceptedProof") is not False \
            or meter.get("failures") != []:
        raise ValueError("acceleration lacks a passing sealed replay")
    roles = meter.get("roles", {})
    if set(roles) != {"WILD", "MOUNTED"}:
        raise ValueError("acceleration requires both exact roles")
    states = [roles[r] for r in ("WILD", "MOUNTED")]
    for role, state in zip(("WILD", "MOUNTED"), states):
        if state.get("subject", {}).get("role") != role or len(state.get("motions", [])) != 7 \
                or len(state.get("policies", [])) != 7 or not state.get("startupBoundary"):
            raise ValueError("acceleration lacks fourteen bound RESET-to-terminal lifecycles")
        traces = state.get("traces", [])
        for meaning in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
            if sum(e.get("data", {}).get("event") == meaning for e in traces) != 7:
                raise ValueError("acceleration lacks seven native " + meaning)
        reset = state.get("reset", {})
        if reset.get("scratchRestored") is not True or reset.get("acceptedProof") is not False:
            raise ValueError("acceleration RESET scratch cleanup is missing")
    values = ([7, 7],
              dict(initials=[s["fingerprint"] for s in states],
                   series=[[m["fingerprint"] for m in s["motions"]] for s in states],
                   durations=[[m["duration"] for m in s["motions"]] for s in states]),
              dict(initials=[s["initialCommit"] for s in states],
                   series=[[m["commitAfter"] for m in s["motions"]] for s in states]), 14)
    expected = [dict(claim=c, name=n, value=v, operator="eq") for c, n, v in zip(CLAIMS, NAMES, values)]
    if meter.get("measurements") != expected:
        raise ValueError("acceleration rows differ from native role proof")
    # Use the same original registry validators, not a second timing formula.
    from tools.overworld.control import _registry_validator_passes
    for row, specification in zip(expected, (contract()[c][0] for c in CLAIMS)):
        if not _registry_validator_passes(specification, row["value"], specification.get("expected")):
            raise ValueError("acceleration original terminal series contract failed")
    if record.get("sessionCleanup") != dict(sessionId=record.get("sessionId"), closed=True, errors=[]):
        raise ValueError("acceleration private session did not close cleanly")
    return [dict(row, passed=True) for row in expected]


class AccelerationNegative:
    """One changed meaning; native sequence numbers and clocks stay intact."""
    def __init__(self, fault):
        if fault not in FAULTS:
            raise ValueError("unknown acceleration fault")
        self.fault, self.applied = fault, False

    def mutate(self, row, subjects):
        if self.applied:
            return row
        result = deepcopy(row)
        if self.fault == "acceleration-bad-reset" and row.get("command") == "acceleration.begin":
            result["receipt"]["value"]["scratchRestored"] = False
            self.applied = True
        elif subjects and row.get("samples"):
            selected = {s["handle"]["value"] for s in subjects.values()}
            for sample in result["samples"]:
                actors = sample.get("actors", [])
                actor = next((a for a in actors if a.get("handle", {}).get("value") in selected), None)
                if actor and self.fault == "acceleration-absent-subject":
                    actors.remove(actor)
                    self.applied = True
                    break
                if actor and self.fault == "acceleration-wrong-duration" and actor.get("motionKind") == "WALK":
                    actor["motionDuration"] += 1
                    self.applied = True
                    break
            if not self.applied:
                for event in result.get("events", []):
                    data = event.get("data", {})
                    if event.get("kind") == "native-observation" and data.get("observation") == "walk-policy" \
                            and data.get("operation") == 3:
                        if self.fault == "acceleration-missing-policy":
                            data["observation"] = "copied-control-removed-policy"
                        elif self.fault == "acceleration-wrong-policy-counter":
                            raw = bytearray.fromhex(data["policyAfterHex"])
                            raw[1] ^= 1
                            data["policyAfterHex"] = raw.hex()
                            data["policyAfter"]["counter"] = raw[1]
                        else:
                            continue
                        self.applied = True
                        break
                    if self.fault == "acceleration-missing-native-commit" and event.get("kind") == "native" \
                            and data.get("event") == "LOGICAL_COMMIT":
                        data["event"] = "WORLD_EFFECT"
                        self.applied = True
                        break
        return result if self.applied else row


def validate_negative_result(result, fault):
    # _replay_shared_test separately rejects controls that never applied.
    if fault not in FAULTS or result.get("passed") is not False:
        raise ValueError("acceleration copied control was not applied and rejected")
    failures = result.get("failures", []) + result.get("measurements", {}).get(KIND, {}).get("failures", [])
    reasons = {failure.get(key) for failure in failures for key in ("message", "detail")}
    expected = {
        "acceleration-absent-subject": ("selected handle must name exactly one current active actor",),
        "acceleration-missing-policy": ("completed Walk lacks unique policy COMMIT",),
        "acceleration-missing-native-commit": ("missing or different native LOGICAL_COMMIT",),
        "acceleration-wrong-policy-counter": ("acceleration amount, clamp or tile-counter result differs",),
        "acceleration-wrong-duration": ("motion: incomplete-travel",),
        "acceleration-bad-reset": ("missing successful prepared RESET",),
    }[fault]
    if not any(reason in reasons for reason in expected):
        raise ValueError("acceleration copied control failed for an unrelated reason")
