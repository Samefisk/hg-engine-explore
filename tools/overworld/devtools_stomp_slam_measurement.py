"""One natural Stomp Slam, shared physical hit, and Player Jump knockback.

This meter reads the existing native motion and HP observations. It does not
plan movement, call guest code, or infer missing completed frames.
"""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import struct

from scripts.overworld_behavior_profile_viewer import _stable_condition_id
from tools.overworld.devtools_application_bank import canonical_bank, local_application
from tools.overworld.devtools_player_health_hop_contact_measurement import _inside_swept_body
from tools.overworld.devtools_profile_feature_measurement import application_index, decode_condition
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.normal_play_observer import arc_height
from tools.overworld.normal_play_observer import complete_travel

KIND = "stomp-slam-player-contact-v1"
TEST = "profile.stomp-slam.player-contact"
REQUIREMENT = "current.stomp-slam-player-contact"
MOUNTED_KIND = "stomp-slam-mounted-player-contact-v1"
MOUNTED_TEST = "profile.stomp-slam.mounted-player-contact"
MOUNTED_REQUIREMENT = "current.stomp-slam-mounted-player-contact"
BOUNDARY = "main-task-queue-completion"
RISE, HANG, DROP, PEAK, MAX_DISTANCE = 8, 4, 4, 56, 6
DURATION = RISE + HANG + DROP
SETUP = (
    ("slam-tile", "teleport", {"map": 33, "x": 585, "z": 407, "facing": 1}),
    ("prepare-passive-party", "party", {"slot": 0, "species": 155, "level": 50}),
    ("create-passive-follower", "spawn", {"species": 155, "form": 0, "role": "follower", "slot": 0, "level": 50}),
    ("bind-passive", "bind", {"subject": "passive"}),
    ("spawn-snorlax", "spawn", {"species": 143, "form": 0, "role": "wild", "level": 50, "x": 585, "z": 401}),
    ("bind-snorlax", "bind", {"subject": "snorlax"}),
)
ORDER = ("before-contact", "wait-slam-contact", "at-contact", "finish-slam-and-player-jump", "after-landing")


def case(kind=KIND, passive_role="FOLLOWER"):
    """Two exact fixtures share the same native Slam and contact checks."""
    need((kind, passive_role) in ((KIND, "FOLLOWER"), (MOUNTED_KIND, "MOUNTED")),
         "unsupported Slam case or passive role")
    if passive_role == "FOLLOWER":
        return TEST, REQUIREMENT, SETUP
    setup = list(SETUP)
    setup[2] = ("create-passive-mount", "spawn", dict(species=155, form=0, role="mounted", slot=0, level=50))
    return MOUNTED_TEST, MOUNTED_REQUIREMENT, tuple(setup)


def need(value, reason):
    if not value:
        raise ValueError("Stomp Slam: " + reason)


def validate_recipe(test, kind=KIND, passive_role="FOLLOWER"):
    test_id, requirement, setup = case(kind, passive_role)
    stage = lambda name: dict(kind="measurement-stage", measurement=kind, stage=name, when="final")
    actions = ((ORDER[0], "player-health.observe", {}),
               (ORDER[1], "step", dict(frames=300, keys=[], until=stage("contact"))),
               (ORDER[2], "player-health.observe", {}),
               (ORDER[3], "step", dict(frames=60, keys=[], until=stage("finished"))),
               (ORDER[4], "player-health.observe", {}))
    need(test["id"] == test_id and test["mode"] == "prepared"
         and test["requirements"] == [requirement]
         and test["subjects"] == [dict(id="snorlax", species=143, role="WILD", acquire="spawn"),
                                  dict(id="passive", species=155, role=passive_role, acquire="existing")]
         and test["measurements"] == [dict(kind=kind, subject="snorlax")]
         and tuple((a["id"], a["op"], a["args"]) for a in test["setup"]) == setup
         and tuple((a["id"], a["op"], a["args"]) for a in test["actions"]) == actions
         and test["assertions"] == [dict(kind="measurement-complete", measurement=kind, when="final")]
         and test["budgets"]["maxFrames"] <= 600
         and test["budgets"]["minObservedFrames"] >= 22,
         "recipe differs from the bounded ordinary notice/contact setup")


def pose(value):
    need(all(type(value.get("pos_" + axis)) is int for axis in "xyz"), "native pose is missing")
    return [value["pos_" + axis] + value.get("face_" + axis, 0) + value.get("unk88_" + axis, 0)
            for axis in "xyz"]


def contact_body(value):
    return {**dict(zip(("pos_x", "pos_y", "pos_z"), pose(value))),
            "face_x": 0, "face_y": 0, "face_z": 0}


class StompSlamMeasurement:
    def __init__(self, source, *, kind=KIND, passive_role="FOLLOWER"):
        self.test, self.requirement, self.setup = case(kind, passive_role)
        self.kind, self.passive_role = kind, passive_role
        self.source = source
        self.application = local_application(canonical_bank(Path(__file__).resolve().parents[2]),
                                             143, application_index("apply-stomp-slam"))
        self.condition_id = _stable_condition_id("stomp-slam", "condition-stomp-slam-notices-player")
        self.latest = None
        self.subjects = {}
        self.setup_index = self.action_index = self.observed_frames = 0
        self.failures = []
        self.pending_events = []
        self.events = []
        self.condition = self.slam = self.contact = self.completed = self.release = None
        self.before_hp = self.hit_hp = self.after_hp = self.player_baseline = None
        self.mount_baseline = None
        self.before_mount_hp = self.hit_mount_hp = self.after_mount_hp = None
        self.mount_events = []
        self.mount_jump = self.mount_jump_release = None
        self.settle_samples = []
        self.jump = dict(commandSeen=False, arcSeen=False, fallingSeen=False, samples=[])

    def _boundary(self, sample, route=True):
        need(sample.get("fieldAvailable") is True and sample.get("observationBoundary") == BOUNDARY
             and sample.get("romSha256") == self.source["romSha256"]
             and sample.get("fieldControl", {}).get("taskPointer") == 0,
             "current completed field boundary differs")
        if route:
            need(sample.get("context", {}).get("mapId") == 33, "left Route29")

    def _actor(self, sample, name="snorlax"):
        selected = select_current_actor(sample, self.subjects[name])
        return next(a for a in sample["actors"] if a["handle"] == selected["handle"])

    def _passive(self, sample):
        passive = self._actor(sample, "passive")
        need((passive["species"], passive["role"]) == (155, self.passive_role), "fixture subjects changed")
        if self.passive_role == "MOUNTED":
            engine, player = passive["engineObject"], sample["player"]
            need(passive.get("inputOwnership") == 1 and passive["handle"]["slot"] == 7,
                 "passive mount lost current input ownership")
            need(all(engine.get(k) == player.get(k) for k in ("pos_x", "pos_y", "pos_z"))
                 and player.get("face_y", 0) - engine.get("face_y", 0) == 32768
                 and player.get("unk88_y", 0) == engine.get("unk88_y", 0),
                 "mounted Player split its shared anchor or rider height")
        return passive

    def _native(self, sample, actor):
        combat = sample.get("pokemonCombat", {})
        need(combat.get("schemaVersion") == 1 and combat.get("available") is True
             and combat.get("frame") == sample["frame"] and combat.get("nativeCycle") == sample["nativeCycle"]
             and combat.get("identity", {}).get("romSha256") == self.source["romSha256"]
             and combat["identity"].get("overlaySha256") == self.source["overlaySha256"],
             "motion has no coherent native combat owner")
        rows = [r for r in combat.get("targets", []) if r.get("handle") == actor["handle"]]
        timers = [r for r in combat.get("movementTimers", []) if r.get("handle") == actor["handle"]]
        need(len(rows) == len(timers) == 1 and rows[0].get("species") == 143
             and rows[0].get("role") == "WILD" and rows[0].get("personality") == actor["subjectIdentity"]
             and rows[0].get("hpSource") == "wild-resident" and rows[0].get("hp", 0) > 0
             and rows[0].get("knockbackPending") == 0 and timers[0].get("movementActorControlMode") == 0
             and actor.get("inputOwnership") == 0,
             "Slam is not the same free living Wild subject")
        motion = rows[0].get("motion")
        need(isinstance(motion, dict) and motion == decode_motion(bytes.fromhex(motion.get("rawHex", ""))),
             "native motion bytes differ from decoded motion")
        return motion

    def _events(self, sample, events):
        handle = self.subjects["snorlax"]["handle"]
        for event in events:
            data = event.get("data", {})
            if event.get("kind") == "trace-status":
                need(data.get("unreadEventsLost", 0) == 0 and data.get("coverageComplete", True) is True
                     and data.get("code") not in ("sequence-reset", "invalid-native-ring", "trace-filter-changed"),
                     "semantic trace is incomplete")
            if self.passive_role == "MOUNTED" and event.get("kind") == "native" \
                    and data.get("actorHandle") == self.subjects["passive"]["handle"]["value"]:
                mount_handle = self.subjects["passive"]["handle"]
                need(data.get("actor") == {k:v for k,v in mount_handle.items() if k != "value"}
                     and type(data.get("sequence")) is int, "event has a stale mounted Jump owner")
                self.mount_events.append(dict(data, frame=event["frame"]))
            if event.get("kind") != "native" or data.get("actorHandle") != handle["value"]:
                continue
            need(data.get("actor") == {k: v for k, v in handle.items() if k != "value"}
                 and type(data.get("sequence")) is int, "event has a stale Slam owner")
            if data.get("event") == "CONDITIONAL_RESOLVED":
                condition = decode_condition(event)
                if condition["conditionId"] == self.condition_id and condition["active"]:
                    need(condition["timed"] and condition["application"] == self.application
                         and condition["targetSourceApplication"] == self.application and condition["targetKind"] == 1,
                         "notice condition has another source or target")
                    if self.condition is None:
                        need(condition["truth"] and condition["triggered"] and not condition["untilCrash"]
                             and (condition["activeUntil"] - condition["actorFrame"]) & 0xFFFF == 180
                             and (condition["cooldownUntil"] - condition["actorFrame"]) & 0xFFFF == 300,
                             "notice lacks true authored 180/300 admission")
                        self.condition = deepcopy(condition)
                    else:
                        need(all(condition[k] == self.condition[k] for k in ("activeUntil", "cooldownUntil", "targetKind", "targetSlot")),
                             "captured notice target or lifetime changed")
            self.events.append(dict(data, frame=event["frame"]))

    def _profile(self, sample, actor, cache):
        coverage = sample.get("nativeObservation", {})
        need(isinstance(cache, dict) and cache.get("frame", -1) >= sample["frame"]
             and cache.get("nativeCycle", -1) >= sample["nativeCycle"] and coverage.get("coverageComplete") is True
             and coverage.get("profilesEvicted") == 0 and actor["behaviorFingerprint"] in coverage.get("profileFingerprints", [])
             and actor["matchedLayerMask"] & (1 << self.application), "Slam lacks coherent authored resolver coverage")
        rows = [r for r in cache.get("resolvedProfiles", []) if r.get("resolved") is True
                and r.get("fingerprint") == actor["behaviorFingerprint"]]
        need(rows and len({r.get("resultHex") for r in rows}) == 1
             and all(r.get("sourceSha256") == self.source["profileSha256"] for r in rows),
             "Slam differs from sealed authored source")
        raw = bytes.fromhex(rows[0]["resultHex"])
        need(len(raw) == 216 and raw[0] == 3 and raw[2] == 2 and raw[12:14] == bytes((2, 10))
             and tuple(raw[20:22]) == (1, MAX_DISTANCE)
             and tuple(raw[72:75]) == (1, 16, 20) and raw[79] == 10
             and struct.unpack_from("<I", raw, 192)[0] == actor["behaviorFingerprint"]
             and raw[196:210] == bytes(12) + bytes((1, 0)) and raw[212] == self.application
             and raw[213] == 0 and struct.unpack_from("<H", raw, 214)[0] == self.condition_id,
             "Slam does not capture full Player with Chase/Hop range6, attack20/min16 and Jump2")
        return raw

    def _start(self, sample, actor, motion, cache):
        plan = motion["plan"]
        need(self.condition is not None and motion["elapsed"] in (0, 1), "Slam launch or notice admission was not observed")
        profile = self._profile(sample, actor, cache)
        need(plan["version"] == 1 and plan["kind"] == 2 and plan["flags"] == 2
             and (plan["duration"], plan["spinSpeed"], plan["swayWidth"], plan["arcHeightQ4"]) == (DURATION, RISE, HANG, PEAK)
             and plan["fieldEpoch"] == actor["handle"]["fieldEpoch"]
             and plan["behaviorFingerprint"] == actor["behaviorFingerprint"] & 0xFFFF
             and plan["pauseFrames"] == profile[22]
             and plan["target"] == [sample["player"][k] for k in ("x", "y")]
             and plan["distance"] == MAX_DISTANCE
             and max(abs(plan["target"][i] - plan["origin"][i]) for i in (0, 1)) == MAX_DISTANCE,
             "native admitted plan lacks authored ordinary 8/4/4 Slam arc, range6 and current Player endpoint")
        starts = [e for e in self.events if e["frame"] == sample["frame"] and e["event"] == "MOTION_STARTED"
                  and e["sequence"] > self.condition["sequence"] and (e["valueA"], e["valueB"]) == (2, DURATION)]
        need(len(starts) == 1 and any(e["event"] == "INTENT_CREATED" and e["frame"] == sample["frame"]
             and self.condition["sequence"] < e["sequence"] < starts[0]["sequence"] for e in self.events),
             "Slam lacks a new normal intent after notice")
        self.slam = dict(actor=deepcopy(actor["handle"]), plan=deepcopy(plan), condition=deepcopy(self.condition),
                         startFrame=sample["frame"], startSequence=starts[0]["sequence"],
                         commitBefore=actor["commitSequence"], samples=[], sourceProfile=deepcopy(cache))

    def _arc(self, sample, actor, motion):
        plan = self.slam["plan"]
        if motion["plan"] != plan:
            self._successor_terminal(sample, actor, motion)
            return
        need(motion["plan"] == plan and motion["elapsed"] == actor["motionElapsed"]
             and actor["motionDuration"] == DURATION and actor["origin"] == dict(zip(("x", "y"), plan["origin"]))
             and actor["target"] == dict(zip(("x", "y"), plan["target"])), "Slam endpoint or native plan changed in flight")
        elapsed = motion["elapsed"]
        need(0 <= elapsed <= DURATION and (not self.slam["samples"] or elapsed == self.slam["samples"][-1]["elapsed"] + 1),
             "Slam arc skips a native elapsed frame")
        lerp = lambda start, end: start + int(Fraction((end - start) * min(elapsed, RISE), RISE))
        base = lerp(plan["startBaseY"], plan["targetBaseY"])
        if elapsed <= RISE:
            q = min(4096, (elapsed << 12) // RISE)
            unit_height = 2 * q - ((q * q) >> 12)
        else:
            unit_height = 4096 if elapsed <= RISE + HANG else ((DURATION - elapsed) << 12) // DROP
        height = PEAK * unit_height
        expected = [lerp((plan["origin"][0] << 16) + 32768, (plan["target"][0] << 16) + 32768),
                    base + height,
                    lerp((plan["origin"][1] << 16) + 32768, (plan["target"][1] << 16) + 32768)]
        engine = actor["engineObject"]
        need(pose(engine) == expected and engine.get("pos_y") == base and engine.get("face_y", 0) == 0
             and engine.get("unk88_y") == height, "native body differs from rise/hang/drop arc or exact base height")
        self.slam["samples"].append(dict(frame=sample["frame"], elapsed=elapsed, renderXYZ=pose(engine),
                                         nativeMotion=deepcopy(motion), player=deepcopy(sample["player"])))
        if elapsed == DURATION:
            complete = dict(kind="HOP", duration=DURATION, origin=plan["origin"], target=plan["target"],
                            samples=self.slam["samples"], travelEnd=dict(frame=sample["frame"], elapsed=DURATION,
                                render=[expected[0], expected[2]]), finishFrame=sample["frame"])
            need(complete_travel(complete), "Slam lacks full completed-frame travel coverage")
            self.completed = complete

    def _release_events(self, frame):
        return [e for e in self.events if e["sequence"] > self.slam["startSequence"]
                and e["frame"] <= frame and e["event"] in
                    ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")]

    def _capture_release(self, sample, actor, motion):
        if self.release is not None or self.completed is None:
            return
        events = self._release_events(sample["frame"])
        expected_commit = (self.slam["commitBefore"] + 1) & 0xFFFFFFFF
        names = ["LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"]
        values = [(expected_commit, 2), (expected_commit, 2), (0, expected_commit)]
        commit_frame = self.completed["travelEnd"]["frame"]
        plan, engine = self.slam["plan"], actor["engineObject"]
        release_frame = commit_frame + plan["pauseFrames"]
        need(1 <= len(events) <= 3 and [e["event"] for e in events] == names[:len(events)]
             and all(e["reasonId"] == 0 for e in events)
             and all(a["sequence"] < b["sequence"] for a, b in zip(events, events[1:]))
             and [(e["valueA"], e["valueB"]) for e in events] == values[:len(events)]
             and events[0]["frame"] == commit_frame
             and all(e["frame"] == release_frame for e in events[1:])
             and actor["commitSequence"] == expected_commit and actor["inputOwnership"] == 0,
             "first Slam lacks its one ordered normal commit/finish/control return")
        # Retail ov01_021F8D80 subtracts 2<<12 from facing Y during
        # its model step animation. Shared Motion normalizes the commit,
        # but it does not reset this native model dip at control return.
        face_y = engine.get("face_y", 0)
        allowed_face_y = (0, -8192) if commit_frame < sample["frame"] else (0,)
        need([actor["logical"][k] for k in ("x", "y")] == plan["target"]
             and pose(engine) == [(plan["target"][0] << 16) + 32768, plan["targetBaseY"] + face_y,
                                     (plan["target"][1] << 16) + 32768]
             and engine["pos_y"] == plan["targetBaseY"]
             and face_y in allowed_face_y and engine["unk88_y"] == 0,
             "first Slam release lacks its exact terminal pose and base height")
        need(sample["frame"] <= release_frame,
             "first Slam lacks its one ordered normal commit/finish/control return")
        if sample["frame"] < release_frame:
            need(len(events) == 1 and motion["plan"] == plan
                 and motion["phase"] == actor["motionPhase"] == "SETTLING"
                 and motion["elapsed"] == actor["motionElapsed"] == DURATION
                 and actor["motionDuration"] == DURATION and actor["motionKind"] == "HOP"
                 and actor["origin"] == dict(zip(("x", "y"), plan["origin"]))
                 and actor["target"] == dict(zip(("x", "y"), plan["target"]))
                 and actor["reservationId"] == 0
                 and motion["settleRemaining"] == release_frame - sample["frame"]
                 and motion["commitSequence"] == motion["commitPublished"] == 1
                 and motion["pathAdvancesPublished"] == MAX_DISTANCE
                 and motion["phaseBeforeSuspend"] == motion["cancelReason"] == 0
                 and sample["frame"] == commit_frame + len(self.settle_samples),
                 "first Slam native settle changed or skipped its authored pause")
            self.settle_samples.append(dict(frame=sample["frame"], nativeMotion=deepcopy(motion),
                                            terminalPose=deepcopy(engine)))
            return
        need(len(events) == 3 and len(self.settle_samples) == plan["pauseFrames"],
             "first Slam lacks its one ordered normal commit/finish/control return")
        if motion["plan"] == plan:
            need(actor["reservationId"] == 0 and actor["motionPhase"] == motion["phase"] == "IDLE"
                 and motion["elapsed"] == actor["motionElapsed"] == DURATION
                 and actor["motionDuration"] == DURATION and actor["motionKind"] == "NONE"
                 and motion["settleRemaining"] == 0 and motion["pathAdvancesPublished"] == MAX_DISTANCE
                 and motion["commitSequence"] == motion["commitPublished"] == 1
                 and motion["phaseBeforeSuspend"] == motion["cancelReason"] == 0,
                 "first Slam release retains its old motion ownership")
        else:
            self._successor_origin(sample, actor, motion, events)
        self.completed["finishFrame"] = sample["frame"]
        self.release = dict(frame=sample["frame"], actor=deepcopy(actor["handle"]),
                            commitSequence=expected_commit, events=deepcopy(events),
                            terminalPose=deepcopy(engine), observedMotion=deepcopy(motion),
                            settleSamples=deepcopy(self.settle_samples))

    def _successor_origin(self, sample, actor, motion, events):
        plan, successor = self.slam["plan"], motion["plan"]
        starts = [e for e in self.events if e["frame"] == sample["frame"] and e["event"] == "MOTION_STARTED"]
        need(motion["phase"] in ("PLANNED", "MOVING") and actor["motionPhase"] == motion["phase"]
             and motion["elapsed"] == actor["motionElapsed"] == 0
             and not successor["flags"] & 1 and successor["fieldEpoch"] == plan["fieldEpoch"]
             and successor["origin"] == plan["target"] and successor["startBaseY"] == plan["targetBaseY"]
             and actor["origin"] == dict(zip(("x", "y"), plan["target"]))
             and actor["target"] == dict(zip(("x", "y"), successor["target"]))
             and actor["motionDuration"] == successor["duration"]
             and actor["reservationId"] == successor["reservationId"] != plan["reservationId"]
             and len(starts) == 1 and events[-1]["sequence"] < starts[0]["sequence"]
             and (starts[0]["valueA"], starts[0]["valueB"]) == (successor["kind"], successor["duration"]),
             "first Slam release borrowed a later motion")

    def _successor_terminal(self, sample, actor, motion):
        """A real zero-pause successor origin is the old terminal pose, not an old native sample."""
        plan, samples, successor = self.slam["plan"], self.slam["samples"], motion["plan"]
        events = self._release_events(sample["frame"])
        starts = [e for e in self.events if e["frame"] == sample["frame"] and e["event"] == "MOTION_STARTED"]
        need(samples and samples[-1]["elapsed"] == plan["duration"] - 1
             and plan["pauseFrames"] == 0
             and sample["frame"] == samples[-1]["frame"] + 1
             and motion["phase"] in ("PLANNED", "MOVING") and motion["elapsed"] == actor["motionElapsed"] == 0
             and not successor["flags"] & 1 and successor["fieldEpoch"] == plan["fieldEpoch"]
             and successor["origin"] == plan["target"] and successor["startBaseY"] == plan["targetBaseY"]
             and actor["origin"] == dict(zip(("x", "y"), plan["target"]))
             and actor["target"] == dict(zip(("x", "y"), successor["target"]))
             and actor["motionDuration"] == successor["duration"]
             and actor["reservationId"] == successor["reservationId"] != plan["reservationId"]
             and [e["event"] for e in events] == ["LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"]
             and all(e["frame"] == sample["frame"] for e in events)
             and len(starts) == 1 and events[-1]["sequence"] < starts[0]["sequence"]
             and (starts[0]["valueA"], starts[0]["valueB"]) == (successor["kind"], successor["duration"]),
             "Slam endpoint or native plan changed in flight")
        # Slam finishes vertically after horizontal travel has already ended.
        # The generic coverage check proves every preceding flight frame; the
        # ordered native commit and exact real successor-origin pose prove the
        # adjacent terminal frame separately. No elapsed/native bytes are made up.
        prefix = dict(duration=plan["duration"] - 1, origin=plan["origin"], target=plan["target"], samples=samples,
                      travelEnd=dict(frame=samples[-1]["frame"], elapsed=plan["duration"] - 1,
                                     render=[samples[-1]["renderXYZ"][0], samples[-1]["renderXYZ"][2]]))
        need(complete_travel(prefix), "Slam lacks full completed-frame travel coverage")
        engine = actor["engineObject"]
        self.completed = dict(kind="HOP", duration=plan["duration"], origin=plan["origin"], target=plan["target"],
            samples=deepcopy(samples), finishFrame=sample["frame"],
            travelEnd=dict(frame=sample["frame"], elapsed=plan["duration"],
                render=[engine["pos_x"], engine["pos_z"]], observedBy="successor-origin", successorElapsed=0),
            terminalNativeMotion=deepcopy(motion))
        self._capture_release(sample, actor, motion)

    def _mounted_hp(self, sample, mount):
        combat = sample.get("pokemonCombat", {})
        need(combat.get("schemaVersion") == 1 and combat.get("available") is True
             and combat.get("frame") == sample["frame"] and combat.get("nativeCycle") == sample["nativeCycle"]
             and combat.get("observationBoundary") == BOUNDARY
             and type(combat.get("fieldSystem")) is int and 0x02000000 <= combat["fieldSystem"] < 0x02400000
             and combat["fieldSystem"] == sample["fieldControl"].get("fieldPointer")
             and combat.get("identity") == dict(descriptorVersion=1,romSha256=self.source["romSha256"],
                  overlaySha256=self.source["overlaySha256"]), "mounted Slam has no current native combat HP owner")
        rows = [r for r in combat.get("targets", []) if r.get("handle") == mount["handle"]]
        party = [r for r in sample.get("party", []) if r.get("personality") == mount["subjectIdentity"]]
        need(len(rows) == len(party) == 1, "mounted Slam HP has a stale party or combat owner")
        hp = rows[0]
        need(hp.get("role") == "MOUNTED" and hp.get("species") == 155
             and hp.get("personality") == mount["subjectIdentity"] and hp.get("initialized") == 1
             and hp.get("hpSource") == "party" and hp.get("hpMirrorMatches") is True
             and type(hp.get("hp")) is int and type(hp.get("maxHp")) is int
             and 0 < hp["hp"] <= hp["maxHp"] == hp.get("actualMaxHp")
             and hp["hp"] == hp.get("currentHp") and hp.get("knockbackPending") == 0
             and party[0].get("identityVerified") is True and party[0].get("species") == 155
             and party[0].get("hp") == hp["hp"] and party[0].get("maxHp") == hp["maxHp"]
             and sample.get("partyObservation", {}).get("frame") == sample["frame"]
             and sample["partyObservation"].get("boundary") == BOUNDARY,
             "mounted Slam HP differs from the real current party mount")
        motion = hp.get("motion", {})
        need(motion == decode_motion(bytes.fromhex(motion.get("rawHex", ""))),
             "mounted Jump native motion bytes differ")
        return hp, motion

    def _mounted_motion(self, sample, mount):
        hp, motion = self._mounted_hp(sample, mount)
        if self.before_mount_hp is None:
            return
        if self.contact is None:
            need(hp["hp"] == self.before_mount_hp["hp"] and hp.get("hitCount") == self.before_mount_hp["hitCount"]
                 and hp.get("lastDamage") == 0, "mount changed HP before the physical Slam contact")
        else:
            need(hp["hp"] == self.before_mount_hp["hp"]-20 and hp.get("lastDamage") == 20
                 and hp.get("hitCount") == self.before_mount_hp["hitCount"]+1,
                 "mounted physical contact did not accept exactly one normal20 hit")
        active = mount.get("motionKind") != "NONE" or mount.get("motionPhase") != "IDLE"
        if active:
            plan, elapsed = motion["plan"], motion["elapsed"]
            baseline = self.player_baseline
            origin = [baseline[k] for k in ("x", "y")]
            # This fixture is a South Slam. Mount and rider share one forced plan.
            need(self.contact is not None and mount.get("motionKind") == "HOP"
                 and mount.get("motionPhase") == motion["phase"] in ("MOVING", "COMMIT_PENDING")
                 and plan.get("version") == 1 and plan.get("kind") == 2 and plan.get("flags") == 1
                 and plan.get("fieldEpoch") == mount["handle"]["fieldEpoch"]
                 and plan.get("behaviorFingerprint") == mount["behaviorFingerprint"] & 0xFFFF
                 and plan.get("origin") == origin and plan.get("target") == [origin[0],origin[1]+2]
                 and plan.get("direction") == 1 and plan.get("distance") == 2
                 and plan.get("duration") == 18 and plan.get("arcHeightQ4") == 16
                 and plan.get("startBaseY") == plan.get("targetBaseY") == baseline["pos_y"]
                 and plan.get("pathAdvancePolicy") == 2 and plan.get("commitPolicy") == 1
                 and plan.get("reservationId",0) > 0,
                 "mount has another movement owner instead of one queued forced Jump2")
            if self.mount_jump is None:
                starts = [e for e in self.mount_events if e["frame"] == sample["frame"]
                          and e["event"] == "MOTION_STARTED" and (e["valueA"],e["valueB"]) == (2,18)]
                need(0 <= elapsed <= 1 and self.contact["frame"] < sample["frame"] <= self.contact["frame"]+8
                     and len(starts) == 1 and any(e["frame"] == sample["frame"] and e["event"] == "INTENT_CREATED"
                         and e["sequence"] < starts[0]["sequence"] for e in self.mount_events),
                     "mounted Jump2 has no bounded accepted hit handoff and normal new intent")
                self.mount_jump = dict(actor=deepcopy(mount["handle"]),plan=deepcopy(plan),
                    startFrame=sample["frame"],startElapsed=elapsed,startSequence=starts[0]["sequence"],
                    commitBefore=mount["commitSequence"],samples=[])
            jump = self.mount_jump
            expected_elapsed = jump["startElapsed"] + len(jump["samples"])
            need(self.mount_jump_release is None and plan == jump["plan"] and elapsed == expected_elapsed <= 18
                 and mount["reservationId"] == plan["reservationId"]
                 and mount["motionElapsed"] == elapsed and mount["motionDuration"] == 18
                 and mount["origin"] == dict(zip(("x","y"),origin))
                 and mount["target"] == dict(x=origin[0],y=origin[1]+2)
                 and mount["commitSequence"] == jump["commitBefore"]
                 and motion.get("commitPublished") == motion.get("commitSequence") == 0,
                 "mounted Jump2 owner, locked plan or elapsed coverage changed")
            engine = mount["engineObject"]
            need(engine["pos_x"] == baseline["pos_x"]
                 and engine["pos_z"] == baseline["pos_z"] + 131072*elapsed//18
                 and engine["pos_y"] == self.mount_baseline["pos_y"]
                 and engine.get("face_y",0) == self.mount_baseline.get("face_y",0) + arc_height(elapsed,18)
                 and engine.get("unk88_y",0) == self.mount_baseline.get("unk88_y",0)
                 and sample["player"].get("movement_cmd") == 62,
                 "mounted Jump2 does not use the shared native Hop pose")
            jump["samples"].append(dict(frame=sample["frame"],elapsed=elapsed,nativeMotion=deepcopy(motion),
                                       mount=deepcopy(engine),player=deepcopy(sample["player"])))
        elif self.mount_jump is not None and self.mount_jump_release is None:
            jump = self.mount_jump
            commit = jump["commitBefore"]+1
            terminal = [e for e in self.mount_events if e["sequence"] > jump["startSequence"]
                        and e["event"] in ("LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED")]
            need(jump["samples"][-1]["elapsed"] == 18
                 and [e["event"] for e in terminal] == ["LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"]
                 and all(e["frame"] == sample["frame"] and e.get("reasonId") == 0 for e in terminal)
                 and terminal[0]["sequence"] < terminal[1]["sequence"] < terminal[2]["sequence"]
                 and [(e["valueA"],e["valueB"]) for e in terminal] == [(commit,2),(commit,2),(1,commit)]
                 and mount["commitSequence"] == commit and mount["reservationId"] == 0
                 and mount["logical"] == dict(zip(("x","y"),jump["plan"]["target"])),
                 "mounted Jump2 lacks one ordered commit/finish/input return")
            self.mount_jump_release = dict(frame=sample["frame"],actor=deepcopy(mount["handle"]),
                                           commitSequence=commit,events=deepcopy(terminal))
        else:
            need(mount.get("motionKind") == "NONE" and mount.get("motionPhase") == "IDLE"
                 and mount.get("reservationId") == 0, "passive mount has an ordinary autonomous movement")

    def _player_jump(self, sample):
        if self.contact is None:
            return
        player = sample["player"]
        baseline = self.player_baseline
        height = pose(player)[1] - pose(baseline)[1]
        previous = self.jump["samples"][-1]["height"] if self.jump["samples"] else 0
        if player.get("movement_cmd") == 62:
            need(player["pos_y"] == baseline["pos_y"]
                 and player.get("unk88_y", 0) == baseline.get("unk88_y", 0)
                 and player.get("face_y", 0) >= baseline.get("face_y", 0),
                 "Player jump changed its base height or inherited mount offset")
        self.jump["commandSeen"] |= player.get("movement_cmd") == 62
        self.jump["arcSeen"] |= height > 0
        self.jump["fallingSeen"] |= height < previous
        self.jump["samples"].append(dict(frame=sample["frame"], tile=[player["x"], player["y"]],
                                          height=height, pose=deepcopy(player)))

    def _exclude_other_hit(self, sample, cache, player):
        """A simultaneous attack cannot supply this Slam's accepted HP receipt."""
        prior = {a["handle"]["value"]: a for a in self.latest["actors"] if a.get("active")}
        for other in sample["actors"]:
            if not other.get("active") or other["handle"] == self.subjects["snorlax"]["handle"]:
                continue
            if self.passive_role == "MOUNTED" and other["handle"] == self.subjects["passive"]["handle"]:
                continue
            previous = prior.get(other["handle"]["value"])
            body_after = contact_body(other["engineObject"])
            if previous is None or previous["handle"] != other["handle"]:
                # Its unknown previous pose could have crossed the Player even
                # when the current endpoint lies outside the contact box.
                overlaps = True
            else:
                overlaps = _inside_swept_body(contact_body(previous["engineObject"]), body_after, player)
            if not overlaps:
                continue
            rows = [r for r in cache.get("resolvedProfiles", []) if r.get("resolved") is True
                    and r.get("fingerprint") == other.get("behaviorFingerprint")]
            need(rows, "another crossing body lacks an authored attack gate")
            for row in rows:
                raw = bytes.fromhex(row.get("resultHex", ""))
                need(len(raw) == 216 and row.get("sourceSha256") == self.source["profileSha256"],
                     "another crossing body lacks an authored attack gate")
                need(raw[72] == raw[152] == 0, "another attacking body could supply the contact HP receipt")

    def _sample(self, sample, events, cache):
        self._boundary(sample)
        actor = self._actor(sample)
        passive = self._passive(sample)
        need((actor["species"], actor["role"]) == (143, "WILD"), "fixture subjects changed")
        self._events(sample, events)
        motion = self._native(sample, actor)
        if self.slam is None and actor["motionKind"] == "HOP" and motion["plan"]["flags"] & 2:
            self._start(sample, actor, motion, cache)
        if self.slam is not None and self.completed is None:
            self._profile(sample, actor, cache)
            self._arc(sample, actor, motion)
            before = contact_body(self._actor(self.latest)["engineObject"])
            after = contact_body(actor["engineObject"])
            speed = min(255, max(abs(after[k] - before[k]) for k in ("pos_x", "pos_y", "pos_z")) >> 8)
            recipient = self._actor(self.latest, "passive")["engineObject"] if self.passive_role == "MOUNTED" else self.latest["player"]
            if self.contact is None and speed >= 16 and _inside_swept_body(before, after, contact_body(recipient)):
                need(self.before_hp is not None and self.action_index == 1, "contact preceded the HP baseline")
                self._exclude_other_hit(sample, cache, contact_body(recipient))
                self.contact = dict(frame=sample["frame"], elapsed=motion["elapsed"], speed=speed,
                                    beforeBody=before, afterBody=after, playerBefore=deepcopy(self.latest["player"]),
                                    recipientRole=self.passive_role if self.passive_role == "MOUNTED" else "PLAYER",
                                    recipientBefore=deepcopy(recipient))
        if self.passive_role == "MOUNTED":
            self._mounted_motion(sample, passive)
        self._capture_release(sample, actor, motion)
        self._player_jump(sample)
        self.latest = deepcopy(sample)
        self.observed_frames += 1

    def _health(self, row):
        sample = row["snapshot"]
        self._boundary(sample)
        passive = self._passive(sample)
        need(all(sample[k] == self.latest[k] for k in ("frame", "nativeCycle", "context", "player", "actors")),
             "HP read is not at the last completed frame")
        hp = row.get("receipt", {}).get("playerHealth", {})
        need(hp.get("schemaVersion") == 1 and hp.get("identity", {}).get("descriptorVersion") == 1
             and hp["identity"].get("overlayId") == 161 and hp["identity"].get("romSha256") == self.source["romSha256"]
             and hp["identity"].get("overlaySha256") == self.source["overlaySha256"]
             and hp.get("frame") == sample["frame"] and hp.get("nativeCycle") == sample["nativeCycle"]
             and hp.get("hp") == hp.get("savedHp") and hp.get("maxHp") == 100
             and hp.get("frameActive") is False and hp.get("recoveryPending") is False,
             "HP receipt has another owner or incomplete saved state")
        if self.action_index == 0:
            need(hp["hp"] > 20 and hp["protectionFrames"] == 0, "living pre-hit HP is protected or too low")
            self.before_hp = deepcopy(hp)
            self.player_baseline = deepcopy(sample["player"])
            if self.passive_role == "MOUNTED":
                self.mount_baseline = deepcopy(passive["engineObject"])
                mount_hp, _ = self._mounted_hp(sample,passive)
                need(mount_hp["hp"] == mount_hp["maxHp"] > 20 and mount_hp.get("hitCount") == 0
                     and mount_hp.get("lastDamage") == 0, "mounted Slam requires a full living unhit mount")
                self.before_mount_hp = deepcopy(mount_hp)
        elif self.passive_role == "MOUNTED":
            need(hp["hp"] == self.before_hp["hp"] and hp["acceptedHits"] == self.before_hp["acceptedHits"]
                 and hp["lastDamage"] == self.before_hp["lastDamage"]
                 and hp["lastHealthFrame"]-self.before_hp["lastHealthFrame"] == sample["frame"]-self.before_hp["frame"],
                 "mounted-body contact changed the separate Player HP target")
            mount_hp, _ = self._mounted_hp(sample,passive)
            need(mount_hp["hp"] == self.before_mount_hp["hp"]-20 and mount_hp.get("lastDamage") == 20
                 and mount_hp.get("hitCount") == self.before_mount_hp["hitCount"]+1,
                 "mounted physical contact did not accept exactly one normal20 hit")
            if self.action_index == 2:
                need(self.contact["frame"] == sample["frame"] and mount_hp.get("immunityFrames",0) > 0,
                     "accepted mount hit was not read at its physical contact")
                self.hit_hp, self.hit_mount_hp = deepcopy(hp), deepcopy(mount_hp)
            else:
                need(self.stage("finished"), "landing lacks normal mount Jump2 release and exact pair heights")
                self.after_hp, self.after_mount_hp = deepcopy(hp), deepcopy(mount_hp)
        else:
            need(hp["hp"] == self.before_hp["hp"] - 20 and hp["lastDamage"] == 20
                 and hp["acceptedHits"] == self.before_hp["acceptedHits"] + 1
                 and hp["lastHealthFrame"] - self.before_hp["lastHealthFrame"] == sample["frame"] - self.before_hp["frame"],
                 "measured contact did not accept exactly one normal20 hit")
            if self.action_index == 2:
                need(self.contact["frame"] == sample["frame"] and hp["protectionFrames"] > 0,
                     "accepted hit was not read at its physical contact")
                self.hit_hp = deepcopy(hp)
            else:
                need(self.stage("finished"), "landing lacks normal commit/control release or exact Player Jump2")
                self.after_hp = deepcopy(hp)

    def stage(self, name):
        need(name in ("contact", "finished"), "unknown stage")
        if self.failures:
            return False
        if name == "contact":
            return self.contact is not None and self.contact["frame"] == self.latest["frame"]
        if self.completed is None or self.hit_hp is None:
            return False
        plan = self.slam["plan"]
        delta = [plan["target"][i] - plan["origin"][i] for i in (0, 1)]
        direction = ([1 if delta[0] > 0 else -1, 0] if abs(delta[0]) >= abs(delta[1])
                     else [0, 1 if delta[1] > 0 else -1])
        landing = [self.player_baseline[k] + 2 * direction[i] for i, k in enumerate(("x", "y"))]
        player = self.latest["player"]
        if self.passive_role == "MOUNTED":
            mount = self._passive(self.latest)["engineObject"]
            if self.mount_jump_release is None or self.mount_baseline is None or any(mount.get(k, 0) != self.mount_baseline.get(k, 0)
                    for k in ("pos_y", "face_y", "unk88_y")):
                return False
        return (self.release is not None and self.release["actor"] == self.subjects["snorlax"]["handle"]
                and [player[k] for k in ("x", "y")] == landing and player.get("movement_cmd") != 62
                and [player[k] for k in ("pos_x", "pos_z")] == [(tile << 16) + 32768 for tile in landing]
                and all(player.get(k, 0) == self.player_baseline.get(k, 0) for k in ("pos_y", "face_y", "unk88_y"))
                and all(self.jump[k] for k in ("commandSeen", "arcSeen", "fallingSeen")))

    def observe_record(self, row, on_sample=None):
        try:
            if "initialSnapshot" in row:
                need(self.latest is None and row.get("phase") == "setup", "initial boundary differs")
                self._boundary(row["initialSnapshot"], route=False)
                self.latest = deepcopy(row["initialSnapshot"])
            elif row.get("phase") == "setup":
                need(self.setup_index < len(self.setup) and (row.get("action"), row.get("command")) == self.setup[self.setup_index][:2],
                     "setup order differs")
                sample = row["snapshot"]
                self._boundary(sample)
                if row["action"] == "prepare-passive-party":
                    party = [p for p in sample.get("party", []) if p.get("slot") == 0]
                    need(len(party) == 1 and party[0].get("species") == 155 and party[0].get("identityVerified") is True
                         and not any(a.get("active") and a.get("role") == "FOLLOWER" for a in sample["actors"]),
                         "saved follower was not replaced and recalled")
                if row["action"] == self.setup[2][0]:
                    need(row.get("receipt", {}).get("lifecycle") == "prepared-native-follower-lifecycle"
                         and sample.get("selector", {}).get("activeFollowerPartySlot") == 0,
                         "passive native follower lifecycle differs")
                self.pending_events.extend(row.get("receipt", {}).get("events", []))
                if row["command"] == "bind":
                    name = self.setup[self.setup_index][2]["subject"]
                    selected = select_current_actor(sample, row["receipt"])
                    need((selected["species"], selected["role"]) == ((143, "WILD") if name == "snorlax" else (155, self.passive_role)),
                         "bound subject differs")
                    self.subjects[name] = deepcopy(row["receipt"])
                if self.setup_index == len(self.setup) - 1:
                    self._events(sample, self.pending_events)
                    self.pending_events.clear()
                    actor = self._actor(sample)
                    need(not (actor["motionKind"] == "HOP" and self._native(sample, actor)["plan"]["flags"] & 2),
                         "Slam started during preparation before its HP baseline")
                self.latest = deepcopy(sample)
                self.setup_index += 1
            else:
                need(self.setup_index == len(self.setup) and row.get("phase") == "observe"
                     and self.action_index < len(ORDER) and row.get("action") == ORDER[self.action_index],
                     "observation order differs")
                action = ORDER[self.action_index]
                if action in (ORDER[1], ORDER[3]):
                    need("command" not in row and self.observed_frames < 360, "observation exceeds its bound")
                    for sample, events, _ in validate_raw_chunk(row, self.latest):
                        self._sample(sample, events, row.get("profileCache"))
                        if on_sample:
                            on_sample(sample, self.observed_frames)
                    if self.stage("contact" if action == ORDER[1] else "finished"):
                        self.action_index += 1
                else:
                    need(row.get("command") == "player-health.observe", "HP read is not typed native observation")
                    self._health(row)
                    self.action_index += 1
        except (ValueError, KeyError, TypeError, StopIteration, struct.error) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = not self.failures and self.action_index == len(ORDER) and self.stage("finished")
        return dict(kind=self.kind, requirements=[self.requirement], passiveRole=self.passive_role,
                    ready=ready, passed=ready, acceptedProof=False,
                    observedFrames=self.observed_frames, observedFrameUnit="completed-game-frame",
                    subjects=deepcopy(self.subjects), slam=deepcopy(self.slam), contact=deepcopy(self.contact),
                    completedMotion=deepcopy(self.completed), playerJump=deepcopy(self.jump),
                    slamRelease=deepcopy(self.release),
                    mountedBaseline=deepcopy(self.mount_baseline),
                    mountedTerminal=deepcopy(self._actor(self.latest, "passive")["engineObject"])
                        if ready and self.passive_role == "MOUNTED" else None,
                    beforeHP=deepcopy(self.before_hp), contactHP=deepcopy(self.hit_hp), afterHP=deepcopy(self.after_hp),
                    beforeMountHP=deepcopy(self.before_mount_hp), contactMountHP=deepcopy(self.hit_mount_hp),
                    afterMountHP=deepcopy(self.after_mount_hp), mountedJump=deepcopy(self.mount_jump),
                    mountedJumpRelease=deepcopy(self.mount_jump_release),
                    failures=list(self.failures))

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("Stomp Slam: no complete normal Slam/contact/Player Jump2 landing")
        return self.result()
