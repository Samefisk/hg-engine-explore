"""Accepted baby fear claims and copied-stream failure controls."""
from copy import deepcopy

from tools.overworld.devtools_baby_fear_measurement import CASES, FOLLOWER_SAFETY, WILD_CRY, require
from tools.overworld.devtools_records import stock_bubble_admitted
from tools.overworld.devtools_walk_matrix_observer import decode_motion

CLAIMS = ("live-actor-identity", "profile-resolution", "rendered-motion", "control-release")
FAULT_NAMES = ("wrong-condition", "wrong-source", "wrong-direction", "missing-commit")
SAFETY_CLAIM = "feedback-effect"
SAFETY_FAULTS = ("wrong-bubble", "wrong-bubble-object", "missing-bubble")
DAMAGE_FAULTS = ("missing-self-hp", "missing-hit-receipt", "wrong-timing",
                 "forced-motion", "held-control", "pending-knockback", "chain-pause")


def requirement(feature):
    return CASES[feature]["requirement"]


def needs_bubble(feature):
    return feature == FOLLOWER_SAFETY or "bubble" in CASES[feature]


def claims(feature):
    require(feature in CASES, "unknown baby fear feature")
    return CLAIMS + ((SAFETY_CLAIM,) if needs_bubble(feature) else ()) \
        + (("collision-decision",) if CASES[feature].get("damage") else ())


def faults(feature):
    require(feature in CASES, "unknown baby fear feature")
    return tuple(feature + ":" + name for name in
                 FAULT_NAMES + (SAFETY_FAULTS if needs_bubble(feature) else ())
                 + (DAMAGE_FAULTS if CASES[feature].get("damage") else ()))


def contract(feature):
    require(feature in CASES, "unknown baby fear feature")
    names = {
        "live-actor-identity": "current-baby-and-real-source",
        "profile-resolution": "exact-timed-condition-and-authored-target",
        "rendered-motion": "complete-native-fear-or-safety-movement",
        "control-release": "normal-commit-and-return-with-role-preserved",
        SAFETY_CLAIM: "stock-anguish-bubble-for-current-follower-before-safety-motion",
        "collision-decision": "same-subject-accepted-hit-before-self-damage-admission",
    }
    if feature == WILD_CRY:
        names[SAFETY_CLAIM] = "stock-anguish-bubble-for-current-wild-igglybuff-before-fear-motion"
    return {claim: [dict(name=names[claim], operator="eq", type="integer",
                         validator="meaningful-observation", expected=1)] for claim in claims(feature)}


def measurements(feature, replay, record):
    result = replay.get("measurements", {}).get(feature, {})
    witness = result.get("witness") or {}
    motion = result.get("completedMotion") or {}
    case = CASES[feature]
    subject_name = case.get("subject", "baby")
    expected_source = ("PLAYER" if case["target"] == "PLAYER"
                       else result.get("subjects", {}).get("threat", {}).get("handle"))
    require(replay.get("passed") is True and replay.get("failures") == []
            and result.get("passed") is True and result.get("ready") is True
            and result.get("acceptedProof") is False
            and result.get("requirements") == [case["requirement"]]
            and result.get("observedFrames") == replay.get("observedFrames")
            and result.get("observedFrameUnit") == "completed-game-frame"
            and set(result.get("subjects", {})) == {s[0] for s in case["subjects"]}
            and witness.get("baby") == result["subjects"][subject_name]["handle"]
            and witness.get("source") == expected_source
            and motion.get("handle") == witness["baby"]
            and motion.get("target") == witness.get("target")
            and type(motion.get("finishFrame")) is int
            and motion["finishFrame"] > witness.get("startFrame", 10**9),
            "missing exact current completed baby response")
    if needs_bubble(feature):
        bubble = result.get("safetyBubble") or {}
        data = bubble.get("data") or {}
        require(data.get("publicSubject", {}).get("handle") == witness["baby"]
                and data.get("publicSubjectAfter") == data.get("publicSubject")
                and data.get("bubbleId") == 10 and stock_bubble_admitted(data.get("returnValue"))
                and data.get("objectPointer") == data.get("sourceObjectPointer")
                == data.get("engineObjectPointer")
                and witness["condition"]["frame"] <= bubble.get("frame", -1)
                <= witness["startFrame"],
                "safety crying face is not the current baby's admitted bubble")
    if feature == FOLLOWER_SAFETY:
        origin, target, player, source = (witness[k] for k in
                                          ("origin", "target", "playerTile", "sourceTile"))
        distance = lambda a, b: max(abs(a[i] - b[i]) for i in (0, 1))
        require(distance(target, player) < distance(origin, player)
                and distance(target, source) > distance(origin, source),
                "follower safety motion does not reach toward the actual Player")
    if case.get("damage"):
        damage = result.get("subjectDamage") or {}
        before, after = damage.get("beforeRow") or {}, damage.get("afterRow") or {}
        native = witness.get("nativeResponse") or {}
        native_motion = native.get("motion") or {}
        condition = witness.get("condition") or {}
        require(damage.get("handle") == witness["baby"]
                and 0 < damage.get("after", 0) < damage.get("before", 0)
                and damage["before"] - damage["after"] == 20
                and before.get("handle") == after.get("handle") == witness["baby"]
                and before.get("hp") == damage["before"] and after.get("hp") == damage["after"]
                and before.get("personality") == after.get("personality")
                and after.get("hpSource") == ("party" if case["role"] == "FOLLOWER" else "wild-resident")
                and (after.get("hitCount", 0) - before.get("hitCount", 0)) & 0xFFFF == 1
                and after.get("lastDamage") == 20 and after.get("immunityFrames", 0) >= 59
                and damage.get("frame", 10**9) <= condition.get("frame", -1)
                and condition.get("triggered") is True and condition.get("truth") is True
                and (condition.get("activeUntil", 0) - condition.get("actorFrame", 0)) & 0xFFFF == 960
                and (condition.get("cooldownUntil", 0) - condition.get("actorFrame", 0)) & 0xFFFF == 970,
                "self damage does not belong to the same current subject and timed admission")
        require(native_motion == decode_motion(bytes.fromhex(native_motion.get("rawHex", "")))
                and native_motion["plan"]["flags"] == 0
                and native_motion["plan"]["origin"] == witness["origin"]
                and native_motion["plan"]["target"] == witness["target"]
                and native.get("control", {}).get("handle") == witness["baby"]
                and native["control"].get("movementActorControlMode") == 0
                and native.get("inputOwnership") == 0 and native.get("knockbackPending") == 0
                and native.get("startEvent", {}).get("sequence", -1) > condition["sequence"],
                "self damage proof counts forced knockback or another movement owner")
        origin, target, player = (witness[k] for k in ("origin", "target", "playerTile"))
        distance = lambda a, b: max(abs(a[i] - b[i]) for i in (0, 1))
        require(distance(target, player) < distance(origin, player) if case["role"] == "FOLLOWER"
                else distance(target, player) > distance(origin, player)
                and sum((target[i] - origin[i]) * (origin[i] - player[i]) for i in (0, 1)) > 0,
                "self damage proof has the wrong response direction")
    require(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
            "owned session cleanup is missing")
    return [dict(claim=claim, name=entry["name"], value=1, operator="eq", expected=1, passed=True)
            for claim, rows in contract(feature).items() for entry in rows]


class BabyFearNegative:
    def __init__(self, feature, fault):
        require(feature in CASES and fault in faults(feature), "unknown copied baby fear control")
        self.feature = feature
        self.fault = fault.rsplit(":", 1)[1]
        self.applied = False

    def mutate(self, row, subjects):
        phase = row.get("phase")
        if phase not in ("setup", "observe"):
            return row
        changed = deepcopy(row)
        baby = subjects.get(CASES[self.feature].get("subject", "baby"), {}).get("handle", {})
        if self.fault in SAFETY_FAULTS:
            events = (changed.get("receipt", {}).get("events", []) if phase == "setup"
                      else changed.get("events", []))
            for event in list(events):
                data = event.get("data", {})
                if event.get("kind") != "native-observation" or data.get("observation") != "safety-bubble" \
                        or data.get("publicSubject", {}).get("handle") != baby:
                    continue
                if self.fault == "wrong-bubble":
                    data["bubbleId"] = 2
                elif self.fault == "wrong-bubble-object":
                    data["objectPointer"] ^= 4
                else:
                    events.remove(event)
                self.applied = True
                break
        if self.fault == "wrong-condition":
            events = (changed.get("receipt", {}).get("events", []) if phase == "setup"
                      else changed.get("events", []))
            for event in events:
                data = event.get("data", {})
                if event.get("kind") == "native" and data.get("actorHandle") == baby.get("value") \
                        and data.get("event") == "CONDITIONAL_RESOLVED":
                    data["valueA"] ^= 1
                    self.applied = True
        if phase == "setup":
            return changed
        if self.fault == "wrong-timing":
            for event in changed.get("events", []):
                data = event.get("data", {})
                if event.get("kind") == "native" and data.get("actorHandle") == baby.get("value") \
                        and data.get("event") == "CONDITIONAL_RESOLVED":
                    data["valueB"] ^= 1
                    self.applied = True
        if self.fault == "missing-self-hp":
            for sample in changed.get("samples", []):
                combat = sample.get("pokemonCombat", {})
                for target in combat.get("targets", []):
                    if target.get("handle") == baby:
                        target["hp"] = target["currentHp"] = target["maxHp"]
                        target["hitCount"] = target["lastDamage"] = target["immunityFrames"] = 0
                        for mon in sample.get("party", []):
                            if mon.get("personality") == target.get("personality"):
                                mon["hp"] = target["maxHp"]
                        self.applied = True
        if self.fault in ("missing-hit-receipt", "forced-motion", "held-control", "pending-knockback"):
            for sample in changed.get("samples", []):
                combat = sample.get("pokemonCombat", {})
                for target in combat.get("targets", []):
                    if target.get("handle") != baby:
                        continue
                    if self.fault == "missing-hit-receipt":
                        target["hitCount"] = 0
                    elif self.fault == "pending-knockback":
                        target["knockbackPending"] = 1
                    elif self.fault == "forced-motion":
                        raw = bytearray.fromhex(target["motion"]["rawHex"])
                        raw[37] = 1
                        target["motion"] = decode_motion(bytes(raw))
                    else:
                        for timer in combat.get("movementTimers", []):
                            if timer.get("handle") == baby:
                                timer["movementActorControlMode"] = 1
                    self.applied = True
        if self.fault == "chain-pause":
            for receipt in changed.get("profileCache", {}).get("resolvedProfiles", []):
                raw = bytearray.fromhex(receipt.get("resultHex", ""))
                if len(raw) == 216:
                    raw[31] = 1
                    receipt["resultHex"] = raw.hex()
                    self.applied = True
        if self.fault == "wrong-source":
            for receipt in changed.get("profileCache", {}).get("resolvedProfiles", []):
                raw = bytearray.fromhex(receipt.get("resultHex", ""))
                if len(raw) == 216:
                    raw[196:210] = bytes(14)
                    receipt["resultHex"] = raw.hex()
                    self.applied = True
        if self.fault == "missing-commit":
            events = changed.get("events", [])
            changed["events"] = [e for e in events if not (e.get("kind") == "native"
                and e.get("data", {}).get("actorHandle") == baby.get("value")
                and e["data"].get("event") == "LOGICAL_COMMIT")]
            self.applied |= len(events) != len(changed["events"])
        if self.fault == "wrong-direction":
            for sample in changed.get("samples", []):
                for actor in sample.get("actors", []):
                    if actor.get("handle") == baby and actor.get("motionKind") in ("WALK", "HOP"):
                        actor["target"] = deepcopy(actor["origin"])
                        if CASES[self.feature].get("damage"):
                            for hp in sample.get("pokemonCombat", {}).get("targets", []):
                                if hp.get("handle") == baby:
                                    raw = bytearray.fromhex(hp["motion"]["rawHex"])
                                    raw[12:16] = raw[8:12]
                                    hp["motion"] = decode_motion(bytes(raw))
                        self.applied = True
        return changed


def validate_negative_result(feature, result, fault):
    require(fault in faults(feature) and result.get("passed") is False and result.get("failures"),
            "copied baby fear control did not reject")
    expected = {"wrong-condition": "no exact completed fear",
                "wrong-source": "full current source",
                "wrong-direction": "did not",
                "missing-commit": "lacks intent, commit",
                "wrong-bubble": "safety crying face was not admitted",
                "wrong-bubble-object": "safety bubble has another current baby or object",
                "missing-bubble": "safety crying face did not precede",
                "missing-self-hp": "self damage condition has no HP loss",
                "missing-hit-receipt": "no accepted collision hit",
                "wrong-timing": "authored 960/970 timing",
                "forced-motion": "no exact completed fear",
                "held-control": "no exact completed fear",
                "pending-knockback": "no exact completed fear",
                "chain-pause": "chain pause action"}[fault.rsplit(":", 1)[1]]
    require(any(expected in str(f) for f in result.get("measurements", {}).get(feature, {}).get("failures", [])),
            "copied baby fear control rejected for another reason")
