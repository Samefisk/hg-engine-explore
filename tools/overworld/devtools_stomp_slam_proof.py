"""Registered proof claims and copied controls for the shared Stomp Slam path."""
from copy import deepcopy
import struct

from tools.overworld.devtools_stomp_slam_measurement import KIND, REQUIREMENT, DURATION, RISE, HANG, PEAK, MAX_DISTANCE, need
from tools.overworld.devtools_walk_matrix_observer import decode_motion

CLAIMS = ("live-actor-identity", "profile-resolution", "rendered-motion", "collision-decision", "control-release")
NAMES = {
    "live-actor-identity": "same-current-wild-snorlax-and-passive-follower",
    "profile-resolution": "true-player-notice180-cooldown300-attack20-min16-jump2",
    "rendered-motion": "native-slam-range6-curved-rise8-hang4-drop4-peak56-locked-endpoint",
    "collision-decision": "physical-sweep-at-speed16-accepts-one-player-hit20",
    "control-release": "one-slam-commit-player-jump2-and-exact-final-heights",
}
FAULTS = ("wrong-condition", "wrong-target", "wrong-arc", "unlocked-target", "missing-height",
          "damage-receipt", "wrong-knockback", "wrong-distance", "missing-release")


def contract():
    return {claim: [dict(name=NAMES[claim], operator="eq", type="integer",
                         validator="meaningful-observation", expected=1)] for claim in CLAIMS}


def measurements(replay, record):
    result = replay.get("measurements", {}).get(KIND, {})
    slam, contact = result.get("slam", {}), result.get("contact", {})
    plan, condition = slam.get("plan", {}), slam.get("condition", {})
    before, hit, after = (result.get(key, {}) for key in ("beforeHP", "contactHP", "afterHP"))
    need(replay.get("passed") is True and replay.get("failures") == []
         and result.get("passed") is True and result.get("ready") is True and result.get("acceptedProof") is False
         and result.get("requirements") == [REQUIREMENT]
         and result.get("observedFrames") == replay.get("observedFrames")
         and result.get("observedFrameUnit") == "completed-game-frame"
         and set(result.get("subjects", {})) == {"snorlax", "passive"}
         and slam.get("actor") == result["subjects"]["snorlax"].get("handle")
         and (plan.get("duration"), plan.get("spinSpeed"), plan.get("swayWidth"), plan.get("arcHeightQ4"), plan.get("flags")) == (DURATION, RISE, HANG, PEAK, 2)
         and plan.get("distance") == MAX_DISTANCE
         and condition.get("truth") is True and condition.get("triggered") is True and condition.get("targetKind") == 1
         and (condition["activeUntil"] - condition["actorFrame"]) & 0xFFFF == 180
         and (condition["cooldownUntil"] - condition["actorFrame"]) & 0xFFFF == 300
         and contact.get("speed", 0) >= 16 and before.get("hp", 0) - hit.get("hp", 0) == 20
         and hit.get("acceptedHits") == before.get("acceptedHits", 0) + 1 and hit.get("lastDamage") == 20
         and after.get("hp") == hit.get("hp") and after.get("acceptedHits") == hit.get("acceptedHits")
         and result.get("completedMotion", {}).get("duration") == DURATION
         and result.get("slamRelease", {}).get("actor") == slam.get("actor")
         and [e["event"] for e in result.get("slamRelease", {}).get("events", [])]
             == ["LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"]
         and all(result.get("playerJump", {}).get(k) is True for k in ("commandSeen", "arcSeen", "fallingSeen")),
         "exact normal Slam, accepted physical hit and Jump2 landing are missing")
    need(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
         "owned Stomp session cleanup is missing")
    release = result["slamRelease"]
    travel_end = result["completedMotion"]["travelEnd"]["frame"]
    settle = release.get("settleSamples", [])
    events = release["events"]
    need(release["frame"] == travel_end + plan["pauseFrames"]
         and [event["frame"] for event in events] == [travel_end, release["frame"], release["frame"]]
         and events[0]["sequence"] < events[1]["sequence"] < events[2]["sequence"]
         and [row["frame"] for row in settle] == list(range(travel_end, release["frame"]))
         and all(row["nativeMotion"] == decode_motion(bytes.fromhex(row["nativeMotion"]["rawHex"]))
                 and row["nativeMotion"]["plan"] == plan
                 and row["nativeMotion"]["phase"] == "SETTLING"
                 and row["nativeMotion"]["elapsed"] == DURATION
                 and row["nativeMotion"]["settleRemaining"] == release["frame"] - row["frame"]
                 for row in settle),
         "exact travel commit, authored native settle and ordered release are missing")
    return [dict(claim=claim, name=NAMES[claim], value=1, operator="eq", expected=1, passed=True)
            for claim in CLAIMS]


class StompSlamNegative:
    def __init__(self, fault):
        need(fault in FAULTS, "unknown copied Stomp control")
        self.fault, self.applied = fault, False
        self.setup_handle = None
        self.jump_seen = False

    def _player(self, sample):
        player = sample.get("player", {})
        self.jump_seen |= player.get("movement_cmd") == 62
        if self.fault == "wrong-distance" and self.jump_seen and player.get("movement_cmd") != 62:
            player["y"] -= 1
            player["pos_z"] -= 65536
            self.applied = True
        if self.fault == "wrong-knockback" and player.get("movement_cmd") == 62:
            player["face_y"] = 0
            self.applied = True

    def mutate(self, row, subjects):
        changed = deepcopy(row)
        if changed.get("phase") == "setup" and changed.get("action") == "bind-snorlax":
            self.setup_handle = changed.get("receipt", {}).get("handle")
        handle = subjects.get("snorlax", {}).get("handle", self.setup_handle or {})
        if "snapshot" in changed:
            self._player(changed["snapshot"])
        if self.fault == "damage-receipt" and not self.applied and changed.get("action") == "at-contact":
            changed["receipt"]["playerHealth"]["acceptedHits"] -= 1
            self.applied = True
        events = changed.get("receipt", {}).get("events", []) if changed.get("phase") == "setup" else changed.get("events", [])
        if self.fault in ("wrong-condition", "missing-release"):
            for event in list(events):
                data = event.get("data", {})
                if event.get("kind") != "native" or data.get("actorHandle") != handle.get("value"):
                    continue
                if self.fault == "wrong-condition" and not self.applied and data.get("event") == "CONDITIONAL_RESOLVED" \
                        and data.get("reasonId", 0) & (1 << 14):
                    data["valueB"] += 1
                    self.applied = True
                if self.fault == "missing-release" and data.get("event") == "CONTROL_RETURNED":
                    events.remove(event)
                    self.applied = True
        if changed.get("phase") != "observe" or "samples" not in changed:
            return changed
        if self.fault == "wrong-target" and not self.applied:
            cache = changed.get("profileCache", {})
            for profile in cache.get("resolvedProfiles", []):
                raw = bytearray.fromhex(profile.get("resultHex", ""))
                if len(raw) == 216 and raw[12:14] == bytes((2, 10)) and raw[79] == 10:
                    raw[208] = 2
                    profile["resultHex"] = raw.hex()
                    self.applied = True
                    break
        for sample in changed["samples"]:
            self._player(sample)
            actors = [a for a in sample.get("actors", []) if a.get("handle") == handle]
            if not actors:
                continue
            actor = actors[0]
            if actor.get("motionKind") == "HOP" and actor.get("motionDuration") == DURATION:
                if self.fault in ("wrong-arc", "unlocked-target") and not self.applied:
                    for target in sample.get("pokemonCombat", {}).get("targets", []):
                        if target.get("handle") != handle:
                            continue
                        raw = bytearray.fromhex(target["motion"]["rawHex"])
                        if self.fault == "wrong-arc":
                            raw[32] = 3
                        elif actor["motionElapsed"] > RISE:
                            struct.pack_into("<h", raw, 14, actor["target"]["y"] + 1)
                        else:
                            continue
                        target["motion"] = decode_motion(bytes(raw))
                        self.applied = True
                if self.fault == "missing-height" and not self.applied and actor["motionElapsed"] > 0:
                    actor["engineObject"]["unk88_y"] = 0
                    self.applied = True
        return changed


def validate_negative_result(result, fault):
    need(fault in FAULTS and result.get("passed") is False and result.get("failures"),
         "copied Stomp control did not reject")
    reasons = {"wrong-condition": "180/300 admission", "wrong-target": "capture full Player",
               "wrong-arc": "8/4/4 Slam arc", "unlocked-target": "plan changed in flight",
               "missing-height": "rise/hang/drop arc", "damage-receipt": "exactly one normal20 hit",
               "wrong-knockback": "no complete normal Slam", "wrong-distance": "no complete normal Slam",
               "missing-release": "ordered normal commit/finish/control return"}
    need(any(reasons[fault] in str(failure) for failure in result["failures"]),
         "copied Stomp control failed for another reason")
