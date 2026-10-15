"""Exact Ram lifetime claims; copied controls never replace a game run."""
from copy import deepcopy

from tools.overworld.devtools_ram_until_crash_measurement import (
    KIND, REQUIREMENT, BEHIND, BEHIND_REQUIREMENT, POST_CRASH_FRAMES, CONDITION,
)
from tools.overworld.devtools_profile_feature_proof import _spec, need

CLAIMS = ("live-actor-identity", "profile-resolution", "engine-boundary",
          "logical-commit", "rendered-motion", "frame-pacing", "control-release")
FAULTS = tuple(KIND + ":" + name for name in (
    "absent-subject", "old-activation", "alert-pause", "missing-crash",
    "missing-commit", "turned-charge", "speed-reset", "early-expiry", "cooldown-rearm"))
CONTRACT = {
    "live-actor-identity": [_spec("ram-current-wild-onix", [1, "WILD", 95, 1, 1])],
    "profile-resolution": [_spec("ram-until-crash-player-capture", [1, 1, 0])],
    "engine-boundary": [_spec("ram-continuous-heading-and-speed", [1, 1])],
    "logical-commit": [_spec("ram-complete-charge-walks", minimum=1)],
    "rendered-motion": [_spec("ram-player-off-axis-charge-continued", 1)],
    "frame-pacing": [_spec("ram-activation-to-walk-frames", 1, operator="lte"),
                     _spec("ram-charge-survives-old-96-frame-expiry", 1)],
    "control-release": [_spec("ram-real-crash-then-inactive-cooldown", [1, 100]),
                        _spec("ram-post-crash-cooldown-samples", minimum=POST_CRASH_FRAMES)],
}


def requirement(kind): return BEHIND_REQUIREMENT if kind==BEHIND else REQUIREMENT

def claims(kind): return CLAIMS

def faults(kind): return tuple(kind+":"+f.rsplit(":",1)[1] for f in FAULTS)

def contract(kind=KIND):
    value=deepcopy(CONTRACT)
    value['profile-resolution'].append(_spec('ram-authenticated-idle-entry-geometry', "behind" if kind==BEHIND else "side"))
    if kind==BEHIND:
        # Same engine, shorter known legal North lane. The original side case
        # alone owns the retained >96-frame lifetime claim.
        value['frame-pacing']=[s for s in value['frame-pacing'] if s['name']!='ram-charge-survives-old-96-frame-expiry']
    return value


def measurements(*args):
    kind,replay,record=(KIND,*args) if len(args)==2 else args
    meter = replay.get("measurements", {}).get(kind, {})
    need(replay.get("passed") is True and replay.get("failures") == []
         and meter.get("passed") is True and meter.get("ready") is True
         and meter.get("failures") == [], "Ram Until Crash replay failed")
    need(record.get("sessionCleanup") == {"sessionId": record.get("sessionId"),
                                          "closed": True, "errors": []},
         "owned session cleanup is missing")
    subject = meter["subjects"]["onix"]
    actor = next(a for a in meter["terminal"]["actors"] if a.get("handle") == subject["handle"])
    trigger, closed = meter["trigger"], meter["closedCondition"]
    completed = meter["completedChargeWalks"]
    entry=meter.get('entryWitness')
    need(isinstance(entry,dict) and entry.get('geometry') == ('behind' if kind==BEHIND else 'side')
         and entry['actor']['handle']==subject['handle'] and entry['actor']['subjectIdentity']==subject['subjectIdentity']
         and entry['triggerFrame']==trigger['frame']==entry['frame']+1,
         'Ram lacks the requested full-owner inactive idle entry')
    actual = {
        'ram-authenticated-idle-entry-geometry':entry['geometry'],
        "ram-current-wild-onix": [1, actor["role"], actor["species"],
                                  int(actor["identityVerified"]), int(actor["presentationAttached"])],
        "ram-until-crash-player-capture": [int(trigger["untilCrash"]), trigger["targetKind"], trigger["activeUntil"]],
        "ram-continuous-heading-and-speed": [int(bool(meter["walks"])), int(bool(meter["policyCalls"]))],
        "ram-complete-charge-walks": len(completed),
        "ram-player-off-axis-charge-continued": int(meter["offAxis"]),
        "ram-activation-to-walk-frames": meter["firstWalk"]["frame"] - trigger["frame"],
        "ram-charge-survives-old-96-frame-expiry": int(meter["longCharge"]),
        "ram-real-crash-then-inactive-cooldown": [int(meter["crash"] is not None),
            (closed["cooldownUntil"] - closed["actorFrame"]) & 0xffff],
        "ram-post-crash-cooldown-samples": len(meter["cooldownSamples"]),
    }
    rows = []
    for claim, specs in contract(kind).items():
        for spec in specs:
            value, expected = actual[spec["name"]], spec.get("expected", spec.get("minimum"))
            ok = value == expected if spec["operator"] == "eq" else \
                value <= expected if spec["operator"] == "lte" else value >= expected
            need(ok, "metric differs: " + spec["name"])
            rows.append({"claim": claim, "name": spec["name"], "value": deepcopy(value),
                         "operator": spec["operator"], "expected": deepcopy(expected), "passed": True})
    return rows


class RamUntilCrashNegative:
    def __init__(self, fault):
        need(fault in FAULTS, "unknown Ram copied-data fault")
        self.fault, self.applied = fault.rsplit(":", 1)[1], False
        self.started = False
        self.start_frame = None
        self.triggered = False
        self.subject_seen = False

    def mutate(self, row, subjects):
        if self.applied and self.fault != "missing-commit":
            return row
        changed = deepcopy(row)
        handle = subjects.get("onix", {}).get("handle", {}).get("value")
        for event in changed.get("events", []):
            data = event.get("data", {})
            native = event.get("kind") == "native" and data.get("actorHandle") == handle
            ram_trigger = native and data.get("event") == "CONDITIONAL_RESOLVED" \
                and data.get("valueA", 0) & 0xffff == CONDITION \
                and data.get("reasonId", 0) & (1 << 12)
            if ram_trigger:
                self.triggered = True
            if native and self.triggered and data.get("event") == "MOTION_STARTED" and data.get("valueA") == 1:
                if not self.started:
                    self.start_frame = event["frame"]
                self.started = True
                if self.fault == "alert-pause":
                    data["event"] = "WORLD_EFFECT"
                    data["valueA"] = 0
                    self.applied = True
                    break
            if self.fault == "old-activation" and ram_trigger:
                data["valueA"] &= ~(1 << 31)
                self.applied = True
                break
            if native and self.fault == "missing-crash" and data.get("event") == "WORLD_EFFECT" \
                    and data.get("valueA") == 3:
                data["valueA"] = 0
                self.applied = True
                break
            if native and self.fault == "missing-commit" and data.get("event") == "LOGICAL_COMMIT":
                data["event"] = "WORLD_EFFECT"
                data["valueA"] = 0
                self.applied = True
                continue
            if self.fault == "speed-reset" and self.triggered \
                    and event.get("kind") == "native-observation" \
                    and data.get("observation") == "walk-policy" and data.get("operation") == 1 \
                    and data.get("publicSubject", {}).get("handle") \
                        == subjects.get("onix", {}).get("handle"):
                response = bytearray.fromhex(data["responseHex"])
                before = bytes.fromhex(data["policyBeforeHex"])
                if response[16] == 2 and before[2] and before[4] == 0:
                    response[19] = 32
                    data["responseHex"] = response.hex()
                    self.applied = True
                    break
        for sample in changed.get("samples", []):
            actor = next((a for a in sample.get("actors", []) if a.get("handle", {}).get("value") == handle), None)
            if actor is None:
                continue
            from tools.overworld.devtools_ram_until_crash_measurement import RAM_MASK
            if self.fault == "absent-subject":
                if not self.subject_seen:
                    self.subject_seen = True
                    continue
                sample["actors"].remove(actor)
            elif self.fault == "early-expiry" and self.started and actor["matchedLayerMask"] & RAM_MASK:
                actor["matchedLayerMask"] &= ~RAM_MASK
            elif self.fault == "cooldown-rearm" and not actor["matchedLayerMask"] & RAM_MASK \
                    and self.started and sample["frame"] > self.start_frame:
                actor["matchedLayerMask"] |= RAM_MASK
            elif self.fault == "turned-charge" and self.started \
                    and sample["frame"] > self.start_frame \
                    and actor.get("motionElapsed") in (0, 1) and actor["matchedLayerMask"] & RAM_MASK \
                    and any(e.get("frame") == sample["frame"] and e.get("kind") == "native"
                            and e.get("data", {}).get("actorHandle") == handle
                            and e["data"].get("event") == "MOTION_STARTED"
                            and e["data"].get("valueA") == 1 for e in changed.get("events", [])):
                dx = actor["target"]["x"] - actor["origin"]["x"]
                dy = actor["target"]["y"] - actor["origin"]["y"]
                actor["target"]["x"] = actor["origin"]["x"] - dy
                actor["target"]["y"] = actor["origin"]["y"] + dx
            else:
                continue
            self.applied = True
            break
        if self.fault == "missing-commit":
            # The claim needs one complete native Walk. Remove every copied
            # commit so a later good tile cannot cover this missing receipt.
            return changed
        return changed if self.applied else row


def validate_negative_result(*args):
    if len(args)==2:
        result,fault=args
    else:
        kind,result,fault=args
        need(kind==BEHIND and fault in faults(kind), "unknown Ram entry control")
        result=deepcopy(result);result["measurements"][KIND]=result["measurements"][kind]
        fault=KIND+":"+fault.rsplit(":",1)[1]
    need(fault in FAULTS and result.get("passed") is False and result.get("failures"),
         "Ram copied-data control did not fail")
    meter = result.get("measurements", {}).get(KIND, {})
    failures = meter.get("failures", [])
    name = fault.rsplit(":", 1)[1]
    if any("Ram reset momentum outside fresh charge admission" in f for f in failures):
        # A real entry Reset exposes a removed first Walk immediately. Removing
        # Crash instead exposes the later Reset while the checker still owns
        # the charge. Authenticate those exact states; do not accept this
        # rejection for another fault or an invalid baseline entry.
        trigger, entry, first = (meter.get(k) for k in ("trigger", "entryWitness", "firstWalk"))
        need(isinstance(trigger, dict) and isinstance(entry, dict)
             and entry.get("triggerFrame") == trigger.get("frame")
             and meter.get("crash") is None
             and (name == "alert-pause" and first is None
                  or name == "missing-crash" and isinstance(first, dict)
                  and 0 <= first["frame"] - trigger["frame"] <= 1
                  and bool(meter.get("policyCalls")) and len(meter.get("walks", [])) >= 2),
             "Ram control failed for a different reset rule")
        return
    expected = {
        "absent-subject": ("selected handle must name exactly one current active actor",),
        "old-activation": ("Ram did not capture the player with Until Crash",),
        "alert-pause": ("Ram paused after activation",),
        "missing-crash": ("Ram ended before an accepted Crash",
                          "Ram reset momentum before Crash"),
        "missing-commit": ("Ram Walk has no paired commit/control",),
        "turned-charge": ("Ram turned toward a moving target", "Ram input lost its committed heading"),
        "speed-reset": ("Ram profile entry slowed or reset current speed",),
        "early-expiry": ("Ram lost its profile before Crash",),
        "cooldown-rearm": ("Ram reactivated inside its Crash cooldown",),
    }[fault.rsplit(":", 1)[1]]
    need(any(reason in f for reason in expected for f in failures),
         "Ram control failed for a different rule")


class RamFeatureNegative:
    """Route the shorter behind leaf through the unchanged Ram fault engine."""
    def __init__(self, kind, fault):
        need(kind==BEHIND and fault in faults(kind), 'unknown Ram entry control')
        self.delegate=RamUntilCrashNegative(KIND+":"+fault.rsplit(":",1)[1])
    @property
    def applied(self): return self.delegate.applied
    def mutate(self,row,subjects): return self.delegate.mutate(row,subjects)
