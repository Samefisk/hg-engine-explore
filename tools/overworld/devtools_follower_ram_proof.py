"""Acceptance claims and copied-data controls for follower Ram contact."""
from copy import deepcopy

from tools.overworld.devtools_follower_ram_measurement import KIND, MIN_FRAMES, RAM_MASK, REQUIREMENT
from tools.overworld.devtools_walk_matrix_observer import decode_motion

NAMES = {
    "live-actor-identity": ("current-follower-onix-and-wild-snorlax",),
    "profile-resolution": ("follower-ram-captures-current-wild-target",),
    "engine-boundary": ("follower-ram-real33-hp-hit", "follower-ram-keeps-player-and-party-hp"),
    "logical-commit": ("follower-ram-complete-charge-walk",),
    "rendered-motion": ("follower-ram-shared-jump3-lands",),
    "natural-input": ("follower-ram-normal-line-entry",),
    "control-release": ("follower-ram-walk-and-jump-return-control",),
}
CLAIMS = tuple(NAMES)
FAULTS = tuple("follower-ram:" + name for name in (
    "absent-follower", "missing-condition", "missing-condition-capture", "stale-target",
    "wrong-first-heading", "attack-off", "player-recipient", "no-hp-hit", "self-hit", "player-damage",
    "ordinary-hop", "wrong-jump-duration", "missing-jump-start",
    "missing-walk-control", "missing-jump-control",
))


def contract():
    return {claim: [dict(name=name, operator="eq", type="integer",
                        validator="meaningful-observation", expected=1) for name in names]
            for claim, names in NAMES.items()}


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    jump = meter.get("jump") or {}
    if (replay.get("passed") is not True or replay.get("failures") != []
            or meter.get("passed") is not True or meter.get("ready") is not True
            or meter.get("acceptedProof") is not False
            or meter.get("observedFrames", 0) < MIN_FRAMES
            or meter.get("observedFrames") != replay.get("observedFrames")
            or set(meter.get("subjects", {})) != {"onix", "snorlax"}
            or meter["subjects"]["onix"].get("role") != "FOLLOWER"
            or meter["subjects"]["snorlax"].get("role") != "WILD"
            or not meter.get("conditionCapture") or not meter.get("firstWalk")
            or not meter.get("completedChargeWalks") or not meter.get("hit")
            or meter.get("attackFrames", 0) < 1 or meter.get("guardFrames", 0) < 10
            or meter.get("jumpArc") is not True or jump.get("finished") is not True
            or any(jump.get("plan", {}).get(k) != value for k, value in (
                ("kind", 2), ("duration", 23), ("distance", 3), ("arcHeightQ4", 16),
                ("flags", 1), ("commitPolicy", 1)))
            or meter.get("playerBefore", {}).get("hp") != meter.get("playerAfter", {}).get("hp")):
        raise ValueError("Follower Ram lacks captured-target charge, real HP loss and completed shared Jump proof")
    if record.get("sessionCleanup") != dict(sessionId=record.get("sessionId"), closed=True, errors=[]):
        raise ValueError("Follower Ram private session did not close")
    return [dict(claim=claim, name=name, value=1, operator="eq", expected=1, passed=True)
            for claim, names in NAMES.items() for name in names]


class FollowerRamNegative:
    def __init__(self, fault):
        if fault not in FAULTS:
            raise ValueError("unknown follower Ram copied-data control")
        self.fault = fault.rsplit(":", 1)[1]
        self.applied = False

    def mutate(self, row, subjects):
        if row.get("phase") != "observe":
            return row
        changed = deepcopy(row)
        samples = list(changed.get("samples", []))
        if isinstance(changed.get("snapshot"), dict):
            samples.append(changed["snapshot"])
        for sample in samples:
            actors = sample.get("actors", [])
            onix = next((a for a in actors if a.get("species") == 95 and a.get("role") == "FOLLOWER"), None)
            snorlax = next((a for a in actors if a.get("species") == 143 and a.get("role") == "WILD"), None)
            targets = sample.get("pokemonCombat", {}).get("targets", [])
            hp = next((h for h in targets if h.get("species") == 143), None)
            source = next((h for h in targets if h.get("species") == 95), None)
            if self.fault == "absent-follower" and onix and not self.applied:
                actors.remove(onix); self.applied = True
            elif self.fault in ("missing-condition-capture", "stale-target"):
                for carrier in sample.get("pokemonCombat", {}).get("interactions", {}).get("carriers", []):
                    if carrier.get("role") != "FOLLOWER": continue
                    if self.fault == "missing-condition-capture":
                        carrier.pop("conditionCaptures", None)
                    else:
                        for capture in carrier.get("conditionCaptures", []):
                            if capture.get("target", {}).get("actor"):
                                capture["target"]["actor"]["generation"] += 1
                    self.applied = True
            elif self.fault == "wrong-first-heading" and onix and snorlax \
                    and onix.get("matchedLayerMask", 0) & RAM_MASK and not self.applied:
                # Change the copied first destination while retaining the
                # current condition's native captured target and tile.
                onix["target"] = dict(x=onix["origin"]["x"]-1, y=onix["origin"]["y"])
                self.applied = True
            elif self.fault == "no-hp-hit" and hp and hp.get("hitCount", 0):
                hp.update(hp=hp["maxHp"], currentHp=hp["maxHp"], hitCount=0,
                          lastDamage=0, immunityFrames=0)
                self.applied = True
            elif self.fault == "self-hit" and source:
                source["hitCount"] += 1; self.applied = True
            if hp and hp.get("motion", {}).get("plan", {}).get("flags") == 1:
                raw = bytearray.fromhex(hp["motion"]["rawHex"])
                if self.fault == "ordinary-hop":
                    raw[37] = 0
                elif self.fault == "wrong-jump-duration":
                    raw[24:26] = (24).to_bytes(2, "little")
                else:
                    continue
                hp["motion"] = decode_motion(bytes(raw)); self.applied = True
        if self.fault == "player-damage" and changed.get("action") == "after-contact":
            health = changed["receipt"]["playerHealth"]
            health["hp"] = health["savedHp"] = health["hp"]-33
            health["acceptedHits"] += 1; self.applied = True
        if self.fault in ("attack-off", "player-recipient"):
            for profile in changed.get("profileCache", {}).get("resolvedProfiles", []):
                if profile.get("appliedOverrides", 0) & RAM_MASK:
                    raw = bytearray.fromhex(profile["resultHex"])
                    raw[72 if self.fault == "attack-off" else 79] = 0 if self.fault == "attack-off" else 46
                    profile["resultHex"] = raw.hex(); self.applied = True
        event_faults = {"missing-condition": ("onix", "CONDITIONAL_RESOLVED"),
                              "missing-walk-control": ("onix", "CONTROL_RETURNED"),
                              "missing-jump-start": ("snorlax", "MOTION_STARTED"),
                              "missing-jump-control": ("snorlax", "CONTROL_RETURNED")}
        if self.fault in event_faults:
            name, event_name = event_faults[self.fault]
            handle = subjects.get(name, {}).get("handle", {}).get("value")
            old = changed.get("events", [])
            changed["events"] = [e for e in old if not (e.get("kind") == "native"
                and e.get("data", {}).get("actorHandle") == handle and e["data"].get("event") == event_name)]
            self.applied |= len(old) != len(changed["events"])
        return changed


def validate_negative_result(result, fault):
    if fault not in FAULTS or result.get("passed") is not False or not result.get("failures"):
        raise ValueError("follower Ram control did not reject " + fault)
    return True
