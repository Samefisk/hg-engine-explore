"""Current baby fear and follower safety from ordinary completed field frames."""
from copy import deepcopy
from pathlib import Path
import struct

from tools.overworld.devtools_application_bank import canonical_bank, local_application
from scripts.overworld_behavior_profile_viewer import _stable_condition_id
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_profile_feature_measurement import application_index, decode_condition
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor, stock_bubble_admitted
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel

WILD_PLAYER = "baby-wild-player-fear-v1"
WILD_CRY = "baby-wild-igglybuff-cry-v1"
WILD_POKEMON = "baby-wild-pokemon-fear-v1"
FOLLOWER_SAFETY = "baby-follower-safety-v1"
FOLLOWER_DAMAGED = "baby-follower-damaged-v1"
WILD_DAMAGED = "wild-damaged-flee-v1"
BOUNDARY = "main-task-queue-completion"
CASES = {
    WILD_PLAYER: dict(test="wild.baby-player-fear", requirement="current.baby-player-fear",
                      role="WILD", condition="condition-baby-notices-player",
                      application="apply-skittish", target="PLAYER", behavior=(4, 3),
                      subjects=(("baby", 173, "WILD", "spawn"), ("passive", 155, "FOLLOWER", "existing")),
                      setup=(("fear-tile", "teleport", {"map": 33, "x": 585, "z": 407, "facing": 0}),
                             ("prepare-passive-party", "party", {"slot": 0, "species": 155, "level": 20}),
                             ("create-passive-follower", "spawn", {"species": 155, "form": 0, "role": "follower", "slot": 0, "level": 20}),
                             ("bind-passive", "bind", {"subject": "passive"}),
                             ("spawn-baby", "spawn", {"species": 173, "form": 0, "role": "wild", "level": 5, "x": 585, "z": 402}),
                             ("bind-baby", "bind", {"subject": "baby"})),
                      actions=(("pass-passive-follower", "step", {"frames": 4, "keys": ["RIGHT"]}),
                               ("enter-baby-vision", "step", {"frames": 32, "keys": ["UP"]}),
                               ("observe-player-fear", "step", {"frames": 180, "keys": []}))),
    WILD_POKEMON: dict(test="wild.baby-pokemon-fear", requirement="current.baby-pokemon-fear",
                       role="WILD", condition="condition-baby-notices-pokemon",
                       application="apply-skittish", target="ACTOR", behavior=(4, 3),
                       subjects=(("baby", 173, "WILD", "spawn"), ("threat", 155, "WILD", "spawn"),
                                 ("passive", 155, "FOLLOWER", "existing")),
                       setup=(("fear-tile", "teleport", {"map": 33, "x": 585, "z": 408, "facing": 0}),
                              ("prepare-passive-party", "party", {"slot": 0, "species": 155, "level": 20}),
                              ("create-passive-follower", "spawn", {"species": 155, "form": 0, "role": "follower", "slot": 0, "level": 20}),
                              ("bind-passive", "bind", {"subject": "passive"}),
                              ("spawn-baby", "spawn", {"species": 173, "form": 0, "role": "wild", "level": 5, "x": 585, "z": 402}),
                              ("bind-baby", "bind", {"subject": "baby"}),
                              ("spawn-threat", "spawn", {"species": 155, "form": 0, "role": "wild", "level": 5, "x": 586, "z": 402}),
                              ("bind-threat", "bind", {"subject": "threat"})),
                       actions=(("observe-pokemon-fear", "step", {"frames": 240, "keys": []}),)),
    FOLLOWER_SAFETY: dict(test="follower.baby-seek-safety", requirement="current.baby-follower-safety",
                          role="FOLLOWER", condition="condition-baby-follower-notices-pokemon",
                          application="apply-seek-safety", target="ACTOR", behavior=(3, 6),
                          subjects=(("baby", 173, "FOLLOWER", "existing"), ("threat", 155, "WILD", "spawn")),
                          setup=(("safety-tile", "teleport", {"map": 33, "x": 585, "z": 408, "facing": 1}),
                                 ("prepare-baby", "party", {"slot": 0, "species": 173, "level": 5}),
                                 ("spawn-baby", "spawn", {"species": 173, "form": 0, "role": "follower", "slot": 0, "level": 5}),
                                 ("bind-baby", "bind", {"subject": "baby"}),
                                 ("spawn-threat", "spawn", {"species": 155, "form": 0, "role": "wild", "level": 5, "x": 585, "z": 410}),
                                 ("bind-threat", "bind", {"subject": "threat"})),
                          actions=(("move-to-safety", "step", {"frames": 32, "keys": ["UP", "B"]}),
                                   ("observe-safety", "step", {"frames": 240, "keys": []}))),
}


# The reported Wild Igglybuff uses the existing Player fear case, its native
# Floaty Bounce spawn/Hop, and the same passive follower. Only its observed
# crying-face contract is new; no condition, movement or timer is prepared.
CASES[WILD_CRY] = deepcopy(CASES[WILD_PLAYER])
CASES[WILD_CRY].update(test="wild.igglybuff-player-fear-cry",
    requirement="current.igglybuff-player-fear-cry", species=174, bubble=10,
    subjects=(("baby", 174, "WILD", "spawn"), ("passive", 155, "FOLLOWER", "existing")))
CASES[WILD_CRY]["setup"] = tuple((name, op,
    {**args, "species": 174} if name == "spawn-baby" else args)
    for name, op, args in CASES[WILD_CRY]["setup"])
# Registered actions count completed queues, including the first queue before
# the new key poll. The measured Question baseline's fenced RIGHT4 consumed
# four real inputs across five queues. Keep all five queues here; do not change
# the shared runner's completed-frame or native-cycle accounting.
CASES[WILD_CRY]["actions"] = tuple((
    "observe-player-cry" if name == "observe-player-fear" else name, op,
    {**args, "frames": 5} if name == "pass-passive-follower" else args)
    for name, op, args in CASES[WILD_CRY]["actions"])

# The same safety response, with a real HP loss as its trigger. Preparation
# sets identities and placement only; normal Player input admits Ambush.
CASES[FOLLOWER_DAMAGED] = dict(
    test="follower.baby-damage-seek-safety", requirement="current.baby-follower-damage-safety",
    role="FOLLOWER", condition="condition-baby-follower-damaged",
    application="apply-seek-safety", target="PLAYER", behavior=(3, 6), damage=True,
    subjects=(("baby", 173, "FOLLOWER", "existing"), ("threat", 70, "WILD", "spawn")),
    setup=(("safety-tile", "teleport", {"map": 33, "x": 585, "z": 408, "facing": 1}),
           ("prepare-baby", "party", {"slot": 0, "species": 173, "level": 50}),
           ("spawn-baby", "spawn", {"species": 173, "form": 0, "role": "follower", "slot": 0, "level": 50}),
           ("bind-baby", "bind", {"subject": "baby"}),
           ("spawn-threat", "spawn", {"species": 70, "form": 0, "role": "wild", "level": 10, "x": 585, "z": 410}),
           ("bind-threat", "bind", {"subject": "threat"})),
    actions=(("enter-ambush-path", "step", {"frames": 32, "keys": ["DOWN", "B"]}),
             ("observe-damage-safety", "step", {"frames": 360, "keys": []})),
)

# The same self-damage record admits Flee for a Wild subject. This fixture
# uses the ordinary Ambush collision path, not a prepared hit or HP write.
CASES[WILD_DAMAGED] = dict(
    test="wild.damage-flee", requirement="current.wild-self-damage-flee",
    subject="cleffa", species=173, profile="skittish", role="WILD",
    condition="condition-wild-subject-damaged", application="apply-skittish",
    target="PLAYER", behavior=(4, 3), damage=True,
    subjects=(("cleffa", 173, "WILD", "spawn"), ("threat", 70, "WILD", "spawn"),
              ("passive", 155, "FOLLOWER", "existing")),
    setup=(("damage-tile", "teleport", {"map": 33, "x": 585, "z": 407, "facing": 1}),
           ("prepare-passive-party", "party", {"slot": 0, "species": 155, "level": 50}),
           ("create-passive-follower", "spawn", {"species": 155, "form": 0, "role": "follower", "slot": 0, "level": 50}),
           ("bind-passive", "bind", {"subject": "passive"}),
           ("spawn-cleffa", "spawn", {"species": 173, "form": 0, "role": "wild", "level": 50, "x": 585, "z": 405}),
           ("bind-cleffa", "bind", {"subject": "cleffa"}),
           ("spawn-threat", "spawn", {"species": 70, "form": 0, "role": "wild", "level": 10, "x": 585, "z": 404}),
           ("bind-threat", "bind", {"subject": "threat"})),
    actions=(("observe-damage-flee", "step", {"frames": 420, "keys": []}),),
)


def require(value, reason):
    if not value:
        raise ValueError("Baby fear: " + reason)


def validate_recipe(test):
    kind = test["measurements"][0]["kind"]
    case = CASES[kind]
    require(test["id"] == case["test"] and test["mode"] == "prepared"
            and test["requirements"] == [case["requirement"]]
            and test["subjects"] == [dict(id=n, species=s, role=r, acquire=a)
                                      for n, s, r, a in case["subjects"]]
            and test["measurements"] == [dict(kind=kind, subject=case.get("subject", "baby"))]
            and tuple((a["id"], a["op"], a["args"]) for a in test["setup"]) == case["setup"]
            and tuple((a["id"], a["op"], {k: v for k, v in a["args"].items() if k != "until"})
                      for a in test["actions"]) == case["actions"]
            and test["actions"][-1]["args"].get("until") == {
                "kind": "measurement-complete", "measurement": kind, "when": "final"}
            and test["assertions"] == [{"kind": "measurement-complete", "measurement": kind, "when": "final"}]
            and test["budgets"]["maxFrames"] <= 600
            and test["budgets"]["minObservedFrames"] >= 2,
            "recipe differs from the bounded normal trigger")


class BabyFearMeasurement:
    def __init__(self, kind, source):
        self.kind = kind
        self.case = CASES[kind]
        self.subject_name = self.case.get("subject", "baby")
        self.species = self.case.get("species", 173)
        self.self_damage = self.case.get("damage", False)
        self.needs_bubble = kind == FOLLOWER_SAFETY or "bubble" in self.case
        self.source = source
        self.application = application_index(self.case["application"])
        self.application_local = local_application(
            canonical_bank(Path(__file__).resolve().parents[2]), self.species, self.application)
        self.condition_id = _stable_condition_id(
            self.case.get("profile", "seek-safety" if self.case["role"] == "FOLLOWER" else "skittish"),
            self.case["condition"])
        self.latest = None
        self.subjects = {}
        self.setup_index = self.observed_frames = 0
        self.failures = []
        self.condition = self.witness = self.completed = self.safety_bubble = None
        self.motion = MotionRecorder()
        self.events = []
        self.pending_setup_events = []
        self.previous_hp = None
        self.previous_hp_row = None
        self.damage = None

    def _hp_row(self, sample):
        combat = sample.get("pokemonCombat", {})
        require(combat.get("schemaVersion") == 1 and combat.get("available") is True
                and combat.get("frame") == sample["frame"]
                and combat.get("nativeCycle") == sample["nativeCycle"]
                and combat.get("identity", {}).get("overlaySha256") == self.source["overlaySha256"]
                and combat["identity"].get("romSha256") == self.source["romSha256"],
                "self damage HP has no current native record")
        baby = self._actor(sample, self.subject_name)
        rows = [row for row in combat.get("targets", []) if row.get("handle") == baby["handle"]]
        require(len(rows) == 1 and rows[0].get("hp") == rows[0].get("currentHp")
                and 0 < rows[0]["hp"] <= rows[0].get("maxHp", 0)
                and rows[0].get("hpSource") == ("party" if self.case["role"] == "FOLLOWER" else "wild-resident")
                and rows[0].get("personality") == baby["subjectIdentity"]
                and (rows[0].get("species"), rows[0].get("role")) == (self.species, self.case["role"]),
                "self damage HP is not the same living subject")
        if self.case["role"] == "FOLLOWER":
            party = [mon for mon in sample.get("party", [])
                     if mon.get("personality") == rows[0].get("personality")]
            require(len(party) == 1 and party[0].get("hp") == rows[0]["hp"]
                    and party[0].get("maxHp") == rows[0]["maxHp"],
                    "self damage HP does not match its exact saved party identity")
        return rows[0]

    def _hp(self, sample):
        return self._hp_row(sample)["hp"]

    def _damage(self, sample, baby):
        hp = self._hp_row(sample)
        previous = self.previous_hp_row
        require(previous is not None, "self damage lacks a pre-hit HP baseline")
        require(hp["maxHp"] == previous["maxHp"] and hp["personality"] == previous["personality"],
                "self damage HP owner or maximum changed")
        delta = previous["hp"] - hp["hp"]
        hits = (hp["hitCount"] - previous["hitCount"]) & 0xFFFF
        require(hits == int(delta > 0) and (delta <= 0 or delta == 20),
                "self damage has no accepted collision hit")
        if delta > 0:
            require(hp["lastDamage"] == 20 and hp["immunityFrames"] >= 59,
                    "self damage has no accepted collision hit guard")
            if self.damage is None:
                self.damage = dict(frame=sample["frame"], nativeCycle=sample["nativeCycle"],
                                   handle=deepcopy(baby["handle"]), before=previous["hp"], after=hp["hp"],
                                   beforeRow=deepcopy(previous), afterRow=deepcopy(hp))
        self.previous_hp = hp["hp"]
        self.previous_hp_row = deepcopy(hp)
        return hp

    def _free_motion(self, sample, baby, hp):
        motion = hp.get("motion")
        require(isinstance(motion, dict)
                and motion == decode_motion(bytes.fromhex(motion.get("rawHex", ""))),
                "self damage response has no exact native motion")
        timers = [row for row in sample["pokemonCombat"].get("movementTimers", [])
                  if row.get("handle") == baby["handle"]]
        require(len(timers) == 1, "self damage response has no current native control")
        plan = motion["plan"]
        if hp.get("knockbackPending") != 0 or plan["flags"] != 0 \
                or timers[0].get("movementActorControlMode") != 0 or baby.get("inputOwnership") != 0:
            return None
        require(plan["kind"] == (1 if baby["motionKind"] == "WALK" else 2)
                and plan["fieldEpoch"] == baby["handle"]["fieldEpoch"]
                and plan["behaviorFingerprint"] == baby["behaviorFingerprint"] & 0xFFFF
                and plan["origin"] == [baby["origin"][k] for k in ("x", "y")]
                and plan["target"] == [baby["target"][k] for k in ("x", "y")]
                and plan["duration"] == baby["motionDuration"]
                and motion["elapsed"] == baby["motionElapsed"]
                and motion["phase"] == baby["motionPhase"],
                "self damage response differs from its admitted normal plan")
        return dict(motion=deepcopy(motion), control=deepcopy(timers[0]),
                    inputOwnership=baby["inputOwnership"], knockbackPending=hp["knockbackPending"])

    def _boundary(self, sample, *, map_required=True):
        require(sample.get("fieldAvailable") is True
                and sample.get("observationBoundary") == BOUNDARY
                and sample.get("romSha256") == self.source["romSha256"]
                and sample.get("fieldControl", {}).get("taskPointer") == 0,
                "completed field boundary, ROM or control differs")
        if map_required:
            require(sample.get("context", {}).get("mapId") == 33, "left Route29")

    def _actor(self, sample, name):
        selected = select_current_actor(sample, self.subjects[name])
        return next(a for a in sample["actors"] if a["handle"] == selected["handle"])

    def _events(self, sample, events):
        baby_handle = self.subjects[self.subject_name]["handle"]
        for event in events:
            data = event.get("data", {})
            if self.needs_bubble and event.get("kind") == "native-observation" \
                    and data.get("observation") == "safety-bubble":
                subject = data.get("publicSubject", {})
                require(subject.get("handle") == baby_handle
                        and subject.get("species") == self.species
                        and subject.get("form") == 0
                        and subject.get("role") == self.case["role"]
                        and data.get("publicSubjectAfter") == subject
                        and data.get("objectPointer") == data.get("sourceObjectPointer")
                        == data.get("engineObjectPointer")
                        and type(data.get("objectPointer")) is int
                        and data["objectPointer"] != 0,
                        "safety bubble has another current baby or object")
                if self.kind == WILD_CRY:
                    current = self._actor(sample, self.subject_name)
                    require(all(subject.get(k) == current.get(k) for k in (
                        "subjectIdentity", "authorityGeneration", "engineAnchorGeneration",
                        "presentationGeneration"))
                        and data["objectPointer"] == current.get("engineIdentity", {}).get("pointer"),
                        "safety bubble has another current baby or object")
                require(data.get("bubbleId") == 10 and stock_bubble_admitted(data.get("returnValue")),
                        "safety crying face was not admitted by stock bubble")
                if self.safety_bubble is None:
                    self.safety_bubble = dict(frame=event["frame"], data=deepcopy(data))
            if event.get("kind") == "trace-status":
                require(data.get("code") not in ("unread-events-lost", "sequence-reset", "invalid-native-ring", "trace-filter-changed")
                        and data.get("unreadEventsLost", 0) == 0 and data.get("coverageComplete", True) is True,
                        "semantic trace is incomplete")
            if event.get("kind") != "native" or data.get("actorHandle") != baby_handle["value"]:
                continue
            require(data.get("actor") == {k: v for k, v in baby_handle.items() if k != "value"}
                    and type(data.get("sequence")) is int,
                    "fear event has stale actor identity")
            if data.get("event") == "CONDITIONAL_RESOLVED":
                decoded = decode_condition(event)
                if decoded["conditionId"] == self.condition_id and decoded["active"]:
                    expected = self.case["target"]
                    require(decoded["timed"]
                            and decoded["application"] == self.application_local
                            and decoded["targetSourceApplication"] == self.application_local
                            and decoded["targetKind"] == (1 if expected == "PLAYER" else 2),
                            "timed fear condition or target kind differs")
                    if expected == "ACTOR":
                        threat = self._actor(sample, "threat")
                        require(decoded["targetSlot"] == threat["handle"]["slot"],
                                "fear condition names another actor")
                    if self.condition is None:
                        require(decoded["truth"], "timed fear has no true admission")
                        if self.self_damage:
                            require(self.damage is not None
                                    and self.damage["frame"] <= event["frame"],
                                    "self damage condition has no HP loss by this subject")
                            require(decoded["triggered"] and not decoded["untilCrash"]
                                    and (decoded["activeUntil"] - decoded["actorFrame"]) & 0xFFFF == 960
                                    and (decoded["cooldownUntil"] - decoded["actorFrame"]) & 0xFFFF == 970,
                                    "self damage admission lacks authored 960/970 timing")
                        if self.kind == WILD_CRY:
                            require(decoded["triggered"] and not decoded["untilCrash"]
                                    and (decoded["activeUntil"] - decoded["actorFrame"]) & 0xFFFF == 960
                                    and (decoded["cooldownUntil"] - decoded["actorFrame"]) & 0xFFFF == 970,
                                    "notice fear admission lacks authored 960/970 timing")
                        self.condition = deepcopy(decoded)
                    else:
                        require(decoded["activeUntil"] == self.condition["activeUntil"]
                                and decoded["cooldownUntil"] == self.condition["cooldownUntil"],
                                "timed fear window changed during its response")
            self.events.append(dict(data, frame=event["frame"]))

    def _profile(self, sample, baby, cache):
        require(isinstance(cache, dict) and cache.get("frame", -1) >= sample["frame"]
                and cache.get("nativeCycle", -1) >= sample["nativeCycle"]
                and sample.get("nativeObservation", {}).get("coverageComplete") is True
                and sample["nativeObservation"].get("profilesEvicted") == 0
                and baby["behaviorFingerprint"] in sample["nativeObservation"].get("profileFingerprints", []),
                "fear profile has no coherent native cache")
        rows = [r for r in cache.get("resolvedProfiles", [])
                if r.get("resolved") is True and r.get("fingerprint") == baby["behaviorFingerprint"]]
        require(len(rows) == 1 and rows[0].get("sourceSha256") == self.source["profileSha256"],
                "fear resolver differs from sealed authored source")
        data = bytes.fromhex(rows[0].get("resultHex", ""))
        require(len(data) == 216 and (data[0], data[13]) == self.case["behavior"]
                and struct.unpack_from("<I", data, 192)[0] == baby["behaviorFingerprint"]
                and data[212] == self.application_local and data[213] == 0
                and struct.unpack_from("<H", data, 214)[0] == self.condition_id,
                "resolved fear kind, target mode or winning condition differs")
        if self.case["role"] == "FOLLOWER":
            require(data[7] <= 4 and data[12] == 1 and data[29] == 0,
                    "follower safety lacks authored Walk, time4 and no acceleration")
            require(data[2] == 10 and data[3] == 10,
                    "follower safety lacks authored crying-face alert")
        if self.kind == WILD_CRY:
            require(data[2] == 10 and data[3] == 10 and data[12] == 2,
                    "Wild Igglybuff lacks resolved Cry and inherited Floaty Bounce")
        if self.self_damage:
            require(data[31] == 0, "self damage response has a chain pause action")
            if self.case["role"] == "WILD":
                require(data[2:4] == bytes((10, 10)),
                        "Wild self damage response lacks authored Anguish10 and alert time10")
        target = (bytes(12) + bytes((1, 0)) if self.case["target"] == "PLAYER"
                  else raw_handle(self._actor(sample, "threat")["handle"]) + bytes((2, 0)))
        require(data[196:210] == target, "fear target is not the full current source")

    def _sample(self, sample, events, cache):
        self._boundary(sample)
        baby = self._actor(sample, self.subject_name)
        require(baby["role"] == self.case["role"] and baby["species"] == self.species,
                "baby role or species changed")
        if self.case["role"] != "FOLLOWER":
            passive = self._actor(sample, "passive")
            require(passive["role"] == "FOLLOWER" and passive["species"] == 155
                    and all(a.get("handle") == passive["handle"]
                            for a in sample.get("actors", [])
                            if a.get("active") is True and a.get("role") == "FOLLOWER"),
                    "Wild fear fixture changed its exact passive follower")
        hp = self._damage(sample, baby) if self.self_damage else None
        self._events(sample, events)
        if self.witness is None and self.condition is not None \
                and baby["motionKind"] in ("WALK", "HOP") \
                and (self.kind != WILD_CRY or baby["motionKind"] == "HOP") \
                and baby["motionPhase"] in ("PLANNED", "MOVING") \
                and baby["motionElapsed"] in (0, 1) \
                and (self.case["role"] != "FOLLOWER" or 1 <= baby["motionDuration"] <= 4) \
                and baby["matchedLayerMask"] & (1 << self.application_local):
            native_response = self._free_motion(sample, baby, hp) if self.self_damage else None
            if self.self_damage and native_response is None:
                self.latest = deepcopy(sample)
                self.observed_frames += 1
                return
            if self.self_damage:
                starts = [e for e in self.events if e["frame"] == sample["frame"]
                          and e["event"] == "MOTION_STARTED"
                          and e["valueA"] == native_response["motion"]["plan"]["kind"]
                          and e["valueB"] == baby["motionDuration"]
                          and e["sequence"] > self.condition["sequence"]]
                require(len(starts) == 1 and any(e["frame"] == sample["frame"]
                        and e["event"] == "INTENT_CREATED"
                        and self.condition["sequence"] < e["sequence"] < starts[0]["sequence"]
                        for e in self.events),
                        "self damage response lacks a new normal intent after its condition")
                native_response["startEvent"] = deepcopy(starts[0])
            self._profile(sample, baby, cache)
            origin = [baby["origin"][k] for k in ("x", "y")]
            target = [baby["target"][k] for k in ("x", "y")]
            player = [sample["player"][k] for k in ("x", "y")]
            anchor = (player if self.case["target"] == "PLAYER"
                      else [self._actor(sample, "threat")["logical"][k] for k in ("x", "y")])
            distance = lambda point, other: max(abs(point[i] - other[i]) for i in (0, 1))
            if self.case["role"] == "FOLLOWER":
                require(distance(target, player) < distance(origin, player)
                        and (self.self_damage
                             or distance(target, anchor) > distance(origin, anchor)),
                        "follower did not move toward the actual Player and away from its source")
            else:
                require(distance(target, anchor) > distance(origin, anchor)
                        and sum((target[i] - origin[i]) * (origin[i] - anchor[i]) for i in (0, 1)) > 0,
                        "Wild baby did not flee from its exact fear source")
            self.witness = dict(startFrame=sample["frame"], baby=deepcopy(baby["handle"]),
                                source=("PLAYER" if self.case["target"] == "PLAYER"
                                        else deepcopy(self._actor(sample, "threat")["handle"])),
                                sourceTile=anchor, playerTile=player, origin=origin, target=target,
                                condition=deepcopy(self.condition))
            if self.self_damage:
                self.witness["nativeResponse"] = native_response
        if self.witness is not None and self.completed is None:
            if self.self_damage and baby["motionKind"] in ("WALK", "HOP"):
                require(self._free_motion(sample, baby, hp) is not None,
                        "self damage response lost normal AUTO control to knockback")
            self._profile(sample, baby, cache)
            self.motion.observe(sample["frame"], baby, baby["engineObject"])
            require(not self.motion.failures, "native fear travel failed: " + str(self.motion.failures))
            if self.motion.completed:
                complete = self.motion.completed[0]
                require(complete["kind"] in ("WALK", "HOP") and complete_travel(complete)
                        and complete["origin"] == self.witness["origin"]
                        and complete["target"] == self.witness["target"],
                        "fear motion did not complete as admitted")
                names = {e["event"] for e in self.events
                         if self.witness["startFrame"] <= e["frame"] <= complete["finishFrame"]}
                require({"INTENT_CREATED", "MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"} <= names,
                        "fear lacks intent, commit or normal control return")
                if self.needs_bubble:
                    require(self.safety_bubble is not None
                            and self.condition["frame"] <= self.safety_bubble["frame"]
                            <= self.witness["startFrame"],
                            "safety crying face did not precede the same response")
                self.completed = deepcopy(complete)
        self.latest = deepcopy(sample)
        self.observed_frames += 1

    def observe_record(self, row, on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup", "initial boundary differs")
                self._boundary(row["initialSnapshot"], map_required=False)
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            if row.get("phase") == "setup":
                require(self.setup_index < len(self.case["setup"])
                        and row.get("action") == self.case["setup"][self.setup_index][0]
                        and row.get("command") == self.case["setup"][self.setup_index][1],
                        "setup order differs")
                sample = row["snapshot"]
                self._boundary(sample)
                if row["action"] == "prepare-passive-party":
                    party = [p for p in sample.get("party", []) if p.get("slot") == 0]
                    require(len(party) == 1 and party[0].get("species") == 155
                            and party[0].get("identityVerified") is True
                            and not any(a.get("active") is True and a.get("role") == "FOLLOWER"
                                        for a in sample.get("actors", [])),
                            "saved thrower follower was not replaced and recalled")
                if row["action"] == "create-passive-follower":
                    followers = [a for a in sample.get("actors", [])
                                 if a.get("active") is True and a.get("role") == "FOLLOWER"]
                    require(len(followers) == 1 and followers[0].get("species") == 155
                            and sample.get("selector", {}).get("activeFollowerPartySlot") == 0
                            and row.get("receipt", {}).get("lifecycle")
                            == "prepared-native-follower-lifecycle",
                            "public follower setup did not replace saved Mankey")
                receipt = row.get("receipt", {})
                if isinstance(receipt, dict):
                    self.pending_setup_events.extend(receipt.get("events", []))
                if row["command"] == "bind":
                    name = self.case["setup"][self.setup_index][2]["subject"]
                    selected = select_current_actor(sample, row["receipt"])
                    expected = next(s for s in self.case["subjects"] if s[0] == name)
                    require((selected["species"], selected["role"]) == expected[1:3],
                            "bound baby or source identity differs")
                    self.subjects[name] = deepcopy(row["receipt"])
                if self.setup_index + 1 == len(self.case["setup"]):
                    if self.case["role"] == "FOLLOWER":
                        baby = self._actor(sample, "baby")
                        threat = self._actor(sample, "threat")
                        require([baby["logical"][k] for k in ("x", "y")] == [585, 409]
                                and [threat["logical"][k] for k in ("x", "y")] == [585, 410]
                                and [sample["player"][k] for k in ("x", "y")] == [585, 408],
                                "follower is not between the adjacent threat and Player")
                    if self.self_damage:
                        self.previous_hp_row = deepcopy(self._hp_row(sample))
                        self.previous_hp = self.previous_hp_row["hp"]
                        require(self.previous_hp == self.previous_hp_row["maxHp"]
                                and self.previous_hp_row["hitCount"] == 0,
                                "self damage lacks a living unhit initial subject")
                    self._events(sample, self.pending_setup_events)
                    self.pending_setup_events = []
                self.latest = deepcopy(sample)
                self.setup_index += 1
                return self.result()
            require(self.setup_index == len(self.case["setup"]) and row.get("phase") == "observe"
                    and row.get("action") in [a[0] for a in self.case["actions"]]
                    and "command" not in row,
                    "observation order differs")
            for sample, events, _ in validate_raw_chunk(row, self.latest):
                require(self.observed_frames < 600, "bounded fear observation exceeded")
                self._sample(sample, events, row.get("profileCache"))
                if on_sample:
                    on_sample(sample, self.observed_frames)
        except (ValueError, KeyError, TypeError, StopIteration, struct.error) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = not self.failures and self.completed is not None \
            and (not self.needs_bubble or self.safety_bubble is not None)
        return dict(kind=self.kind, requirements=[self.case["requirement"]],
                    ready=ready, passed=ready, acceptedProof=False,
                    observedFrames=self.observed_frames, observedFrameUnit="completed-game-frame",
                    subjects=deepcopy(self.subjects), witness=deepcopy(self.witness),
                    completedMotion=deepcopy(self.completed),
                    safetyBubble=deepcopy(self.safety_bubble),
                    subjectDamage=deepcopy(self.damage), failures=list(self.failures))

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("Baby fear: no exact completed fear or safety movement")
        return self.result()
