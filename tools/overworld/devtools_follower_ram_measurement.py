"""One follower Onix charges its captured Wild target through shared motion."""
from copy import deepcopy
import struct

from tools.overworld.devtools_profile_feature_measurement import (
    ProfileFeatureMeasurement, application_index, require,
)
from tools.overworld.devtools_pokemon_combat_measurement import PokemonCombatMeasurement
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel

KIND = "follower-ram-pokemon-v1"
REQUIREMENT = "current.follower-ram-pokemon"
CONDITION = 49626
APPLICATION = application_index("apply-ram")
RAM_MASK = 1 << APPLICATION
MIN_FRAMES = 35
WAIT_FRAMES = 240
TAIL_FRAMES = 16
SUBJECTS = (("onix", 95, "FOLLOWER", "existing"),
            ("snorlax", 143, "WILD", "spawn"))
SETUP_IDS = ("charge-tile", "prepare-onix", "spawn-onix", "spawn-snorlax",
             "settle-fixture", "bind-onix", "bind-snorlax")
ACTION_IDS = ("before-contact", "enter-line", "capture-target", "retreat-player", "observe-charge",
              "finish-knockback", "after-contact")


def validate_recipe(test):
    require(test["mode"] == "prepared"
            and test["subjects"] == [dict(id=n, species=s, role=r, acquire=a)
                                     for n, s, r, a in SUBJECTS]
            and test["measurements"] == [dict(kind=KIND, subject="onix")]
            and [a["id"] for a in test["setup"]] == list(SETUP_IDS)
            and [a["op"] for a in test["setup"]] == ["teleport", "party", "spawn", "spawn", "step", "bind", "bind"]
            and test["setup"][1]["args"] == dict(slot=0, species=95, level=50)
            and test["setup"][2]["args"] == dict(species=95, form=0, role="follower", slot=0, level=50)
            and test["setup"][3]["args"].get("species") == 143
            and test["setup"][3]["args"].get("role") == "wild"
            and test["setup"][3]["args"].get("level") == 50
            and test["setup"][4]["args"] == dict(frames=1, keys=[])
            and [a["args"] for a in test["setup"][5:]] == [dict(subject="onix"), dict(subject="snorlax")]
            and [a["id"] for a in test["actions"]] == list(ACTION_IDS)
            and [a["op"] for a in test["actions"]] == ["player-health.observe", "step", "step", "step", "step", "step", "player-health.observe"]
            and test["actions"][0]["args"] == test["actions"][-1]["args"] == {}
            and test["actions"][1]["args"] == dict(frames=16, keys=["RIGHT"])
            and test["actions"][2]["args"] == dict(frames=4, keys=[])
            and test["actions"][3]["args"] == dict(frames=32, keys=["LEFT"])
            and test["actions"][4]["args"] == dict(frames=WAIT_FRAMES, keys=[], until=dict(
                kind="measurement-stage", measurement=KIND, stage="landed", when="final"))
            and test["actions"][5]["args"] == dict(frames=TAIL_FRAMES, keys=[])
            and test["budgets"]["minObservedFrames"] == MIN_FRAMES
            and test["budgets"]["maxFrames"] <= 600,
            "Follower Ram fixture or normal input differs")


class FollowerRamMeasurement(ProfileFeatureMeasurement):
    def __init__(self, source, test=None, max_frames=600):
        super().__init__(KIND, test, max_frames)
        self.source = source
        self.latest = None
        self.setup_index = self.setup_frames = self.action_index = 0
        self.action_frames = [0] * len(ACTION_IDS)
        self.current_events = []
        self.profile_cache = None
        self.before = self.after = self.trigger = self.capture = self.first_walk = None
        self.baseline = self.previous_hp = None
        self.hit = self.jump = None
        self.jump_arc = False
        self.victim_motion = MotionRecorder()
        self.attack_frames = self.guard_frames = 0

    _boundary = PokemonCombatMeasurement._boundary
    _actor = PokemonCombatMeasurement._actor
    _hp = PokemonCombatMeasurement._hp
    _pose = staticmethod(PokemonCombatMeasurement._pose)
    _native = PokemonCombatMeasurement._events

    def _discover(self, snapshot):
        found = {}
        for name, species, role, _ in SUBJECTS:
            candidates = [a for a in snapshot.get("actors", []) if a.get("active") is True
                          and a.get("species") == species and a.get("role") == role]
            require(len(candidates) == 1, "Follower Ram " + name + " is absent or ambiguous")
            found[name] = select_current_actor(snapshot, candidates[0])
        self.subjects = found
        self.subject = deepcopy(found["onix"])
        self.initial = deepcopy(snapshot)
        return True

    def _attacker_hp(self, sample, actor):
        combat = sample.get("pokemonCombat", {})
        rows = [r for r in combat.get("targets", []) if r.get("handle") == actor["handle"]]
        require(len(rows) == 1, "Follower Ram attacker lacks current party HP")
        hp = rows[0]
        party = [p for p in sample.get("party", []) if p.get("personality") == hp.get("personality")]
        require(hp.get("hpSource") == "party" and hp.get("hpMirrorMatches") is True
                and hp.get("role") == "FOLLOWER" and hp.get("hitCount") == 0
                and hp.get("hp") == hp.get("currentHp") == hp.get("maxHp")
                and hp.get("maxHp", 0) > 0 and len(party) == 1
                and party[0].get("hp") == hp["hp"] and party[0].get("maxHp") == hp["maxHp"],
                "Follower Ram damaged itself or lost real party HP")
        return hp

    def _capture(self, sample, actor, target):
        value = sample.get("pokemonCombat", {}).get("interactions", {})
        require(value.get("schemaVersion") == 1 and value.get("available") is True
                and value.get("frame") == sample["frame"] and value.get("nativeCycle") == sample["nativeCycle"]
                and value.get("observationBoundary") == "main-task-queue-completion"
                and value.get("fieldSystem") == sample["fieldControl"].get("fieldPointer")
                and value.get("identity", {}).get("romSha256") == self.source["romSha256"],
                "Follower Ram condition capture is absent or stale")
        rows = [r for r in value.get("carriers", []) if r.get("handle") == actor["handle"]]
        require(len(rows) == 1 and rows[0].get("available") is True and rows[0].get("role") == "FOLLOWER",
                "Follower Ram condition capture has a stale full owner")
        captures = [c for c in rows[0].get("conditionCaptures", []) if c.get("conditionId") == CONDITION]
        require(len(captures) == 1, "Follower Ram current condition capture is absent or ambiguous")
        capture = captures[0]
        raw = bytes.fromhex(capture.get("preparedRawHex", ""))
        data = bytes.fromhex(capture.get("rawHex", ""))
        index = capture.get("preparedIndex")
        require(len(raw) == 52 and raw[:12] == raw_handle(actor["handle"])
                and raw[49] == 1 and type(index) is int and 0 <= index < raw[48] <= 32
                and raw[16 + index] == capture.get("catalogIndex")
                and struct.unpack_from("<I", raw, 12)[0] == capture.get("statesPointer")
                and len(data) == 16 and struct.unpack("<II3H2B", data) == (
                    0, capture.get("cooldownUntil"), target["handle"]["slot"],
                    target["handle"]["generation"], target["handle"]["encounterGeneration"], 2, 11)
                and capture.get("targetCurrent") is True and capture.get("targetValid") is True
                and capture.get("application") == APPLICATION and capture.get("activationMode") == 2
                and capture.get("durationFrames") == 0 and capture.get("cooldownFrames") == 100
                and capture.get("flags") == 11 and capture.get("activeUntil") == 0
                and capture.get("activeApplicationMask", 0) & RAM_MASK
                and capture.get("targetPosition") == [target["engineObject"][k] for k in ("x", "y")]
                and capture.get("target") == dict(kind="ACTOR", actor=target["handle"]),
                "Follower Ram did not capture the current Wild target")
        return dict(frame=sample["frame"], owner=deepcopy(actor["handle"]), condition=deepcopy(capture))

    def _profile(self, sample, actor):
        cache = self.profile_cache
        require(isinstance(cache, dict) and cache.get("frame", -1) >= sample["frame"]
                and cache.get("nativeCycle", -1) >= sample["nativeCycle"]
                and actor["behaviorFingerprint"] in sample.get("nativeObservation", {}).get("profileFingerprints", []),
                "Follower Ram profile has no coherent native cache")
        rows = [r for r in cache.get("resolvedProfiles", []) if r.get("resolved") is True
                and r.get("fingerprint") == actor["behaviorFingerprint"]]
        require(len(rows) == 1 and rows[0].get("sourceSha256") == self.source["profileSha256"],
                "Follower Ram profile differs from sealed source")
        data = bytes.fromhex(rows[0].get("resultHex", ""))
        require(len(data) == 216 and tuple(data[72:75]) == (1, 32, 33) and data[79] == 78,
                "Follower Ram source lacks attacking33 and Jump3")

    def _jump(self, sample, actor, hp, native):
        if self.jump and self.jump.get("finished"):
            return
        motion = hp.get("motion")
        require(isinstance(motion, dict) and motion == decode_motion(bytes.fromhex(motion.get("rawHex", ""))),
                "Follower Ram victim has no exact native Jump plan")
        plan = motion["plan"]
        starts = [e for e in native if e.get("event") == "MOTION_STARTED" and e.get("valueA") == 2]
        if self.jump is None:
            if not starts:
                require(hp.get("knockbackPending") & 1 and hp.get("knockbackOptions") == 78,
                        "Follower Ram hit lost its queued Jump3")
                return
            origin, target = plan["origin"], plan["target"]
            require(len(starts) == 1 and starts[0].get("reason") == "OK"
                    and starts[0].get("valueB") == 23 and motion["phase"] == "MOVING"
                    and motion["elapsed"] in (0, 1) and plan["version"] == 1
                    and plan["kind"] == 2 and plan["flags"] == 1 and plan["distance"] == 3
                    and plan["duration"] == 23 and plan["arcHeightQ4"] == 16
                    and plan["fieldEpoch"] == actor["handle"]["fieldEpoch"]
                    and plan["targetBaseY"] == plan["startBaseY"]
                    and plan["commitPolicy"] == 1 and plan["pathAdvancePolicy"] == 1
                    and plan["pauseFrames"] == plan["visibilityPolicy"] == 0
                    and plan["reservationId"] > 0 and abs(target[0]-origin[0])+abs(target[1]-origin[1]) == 3
                    and hp.get("knockbackPending") == 0 and hp.get("knockbackOptions") == 78,
                    "Follower Ram hit did not start the shared forced23-frame Jump3")
            accepted = [e for e in native if e.get("event") == "PLAN_ACCEPTED" and e.get("reason") == "OK"
                        and e.get("valueA") == (target[0] << 16 | target[1]) and e.get("valueB") == 23
                        and e["sequence"] < starts[0]["sequence"]]
            require(len(accepted) == 1, "Follower Ram Jump lacks its accepted native destination")
            self.jump = dict(startFrame=sample["frame"], handle=deepcopy(actor["handle"]),
                             plan=deepcopy(plan), start=deepcopy(starts[0]), accepted=deepcopy(accepted[0]), finished=False)
        require(actor["handle"] == self.jump["handle"], "Follower Ram Jump changed actor generation")
        self.victim_motion.observe(sample["frame"], actor, actor["engineObject"])
        self.jump_arc |= self._pose(actor, sample)[2] > self.jump["plan"]["startBaseY"] + 4096
        finished = [e for e in native if e.get("event") == "MOTION_FINISHED" and e.get("valueB") == 2]
        if finished:
            returns = [e for e in native if e.get("event") == "CONTROL_RETURNED"
                       and e.get("reason") == "OK" and e.get("valueA") == 0 and e["sequence"] > finished[0]["sequence"]]
            complete = [m for m in self.victim_motion.completed if m["kind"] == "HOP" and complete_travel(m)]
            require(len(finished) == len(returns) == len(complete) == 1 and self.jump_arc
                    and complete[0]["origin"] == self.jump["plan"]["origin"]
                    and complete[0]["target"] == self.jump["plan"]["target"]
                    and actor["inputOwnership"] == 0 and actor["reservationId"] != self.jump["plan"]["reservationId"]
                    and self._pose(actor, sample) == tuple((v << 16)+32768 for v in self.jump["plan"]["target"])
                        + (self.jump["plan"]["targetBaseY"],),
                    "Follower Ram Jump did not land and release control")
            self.jump.update(finished=True, finishFrame=sample["frame"], motion=deepcopy(complete[0]),
                             finish=deepcopy(finished[0]), control=deepcopy(returns[0]))
        else:
            require(plan == self.jump["plan"] and motion["phase"] in ("MOVING", "COMMIT_PENDING"),
                    "Follower Ram Jump plan changed before its native finish")

    def _sample(self, sample, actors):
        self._boundary(sample)
        require(sample["context"] == self.initial["context"], "Follower Ram changed field context")
        actor, target = actors["onix"], actors["snorlax"]
        require(actor["role"] == "FOLLOWER" and actor["species"] == 95 and target["role"] == "WILD"
                and target["species"] == 143, "Follower Ram actor role or species changed")
        self._attacker_hp(sample, actor)
        own = self._native(self.current_events, actor); victim = self._native(self.current_events, target)
        require(all(e.get("actorFrame") == sample["actorFrame"] for e in own + victim),
                "Follower Ram event has a stale completed frame")
        require(not any(e.get("event") in ("MOTION_CANCELED", "ACTOR_DETACHED", "ACTOR_REBOUND", "CONTEXT_CHANGED")
                        for e in own + victim), "Follower Ram lost its native actor lifecycle")
        triggered = [c for c in self.conditions if c["triggered"] and c["frame"] == sample["frame"]]
        if self.trigger is None and triggered:
            require(len(triggered) == 1 and triggered[0]["active"] and triggered[0]["truth"]
                    and triggered[0]["untilCrash"] and not triggered[0]["timed"]
                    and triggered[0]["activeUntil"] == 0 and triggered[0]["targetKind"] == 2
                    and triggered[0]["targetSlot"] == target["handle"]["slot"]
                    and triggered[0]["targetSourceApplication"] == APPLICATION,
                    "Follower Ram condition did not admit its Wild target")
            self.trigger = deepcopy(triggered[0]); self.capture = self._capture(sample, actor, target)
        starts = [e for e in own if e.get("event") == "MOTION_STARTED"]
        if self.trigger and self.first_walk is None and starts:
            origin = [actor["origin"][k] for k in ("x", "y")]
            dest = [actor["target"][k] for k in ("x", "y")]
            current = self.capture["condition"]["targetPosition"]
            dx, dz = (b-a for a, b in zip(origin, current))
            heading = [0, -1 if dz < 0 else 1] if dx == 0 else [-1 if dx < 0 else 1, 0]
            require(len(starts) == 1 and actor["motionKind"] == "WALK" and actor["motionElapsed"] in (0, 1)
                    and starts[0].get("valueA") == 1 and starts[0].get("valueB") == actor["motionDuration"]
                    and 0 <= sample["frame"]-self.trigger["frame"] <= 1
                    and ((dx == 0) != (dz == 0)) and 0 < abs(dx)+abs(dz) <= 32
                    and [b-a for a, b in zip(origin, dest)] == heading,
                    "Follower Ram first Walk did not move toward its captured current target")
            self.first_walk = dict(frame=sample["frame"], origin=origin, target=dest,
                                   targetPosition=current, event=deepcopy(starts[0]))
        if self.trigger and actor["matchedLayerMask"] & RAM_MASK:
            self._profile(sample, actor)
            self.attack_frames += int(actor["motionKind"] == "WALK")
        if self.first_walk and not self._charge_walks():
            self.motion.observe(sample["frame"], actor, actor["engineObject"])
            if self._charge_walks():
                # Only this first complete charge tile is claimed. Later
                # Crash feedback is not a second charge-motion observation.
                self.motion.current = None
        hp = self._hp(sample, "snorlax")
        previous = self.previous_hp
        require(hp["maxHp"] == previous["maxHp"], "Follower Ram target max HP changed")
        delta, hits = previous["hp"]-hp["hp"], hp["hitCount"]-previous["hitCount"]
        require(delta in (0, 33) and hits == int(delta == 33), "Follower Ram contact is not one real33-HP hit")
        if hits:
            require(self.hit is None and self.first_walk is not None and actor["matchedLayerMask"] & RAM_MASK
                    and hp["lastDamage"] == 33 and hp["immunityFrames"] >= 59,
                    "Follower Ram hit lacks its active charge and target guard")
            self.hit = dict(frame=sample["frame"], hpBefore=previous["hp"], hpAfter=hp["hp"], target=deepcopy(target["handle"]))
        if self.hit:
            self.guard_frames += int(hp["immunityFrames"] > 0)
            self._jump(sample, target, hp, victim)
        self.previous_hp = deepcopy(hp)
        self.samples.append(dict(frame=sample["frame"], actorHandle=deepcopy(actor["handle"]),
                                 targetHandle=deepcopy(target["handle"]), hp=hp["hp"]))

    def _health(self, row):
        value = row.get("receipt", {}).get("playerHealth", {})
        sample = row["snapshot"]; self._boundary(sample)
        require(all(sample.get(k) == self.latest.get(k) for k in ("frame", "nativeCycle", "actors", "player", "pokemonCombat"))
                and value.get("frame") == sample["frame"] and value.get("hp") == value.get("savedHp")
                and value.get("maxHp") == 100 and value.get("recoveryPending") is False
                and value.get("identity", {}).get("overlaySha256") == self.source["overlaySha256"],
                "Follower Ram player HP has no matching saved native record")
        return deepcopy(value)

    def observe_record(self, row, on_sample=None):
        if self.failures:
            return self.result()
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup", "Follower Ram initial frame is misplaced")
                self._boundary(row["initialSnapshot"], fixture=False)
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            require(self.latest is not None, "Follower Ram initial frame is missing")
            if row.get("phase") == "setup":
                require(self.setup_index < len(SETUP_IDS) and row.get("action") == SETUP_IDS[self.setup_index],
                        "Follower Ram setup order differs")
                if row["action"] == "settle-fixture":
                    for sample, _, _ in validate_raw_chunk(row, self.latest):
                        self._boundary(sample); self.latest = deepcopy(sample); self.setup_frames += 1
                        if on_sample: on_sample(sample, self.frames)
                    require(self.setup_frames <= 1, "Follower Ram fixture settle exceeded its bound")
                    if self.setup_frames == 1: self.setup_index += 1
                    return self.result()
                sample = row["snapshot"]; self._boundary(sample)
                if row.get("command") == "bind":
                    name = row["action"].removeprefix("bind-")
                    self.subjects[name] = deepcopy(row["receipt"])
                    self._actor(sample, name)
                self.latest = deepcopy(sample); self.setup_index += 1
                return self.result()
            require(self.setup_index == len(SETUP_IDS) and row.get("phase") == "observe"
                    and self.action_index < len(ACTION_IDS) and row.get("action") == ACTION_IDS[self.action_index],
                    "Follower Ram observation order differs")
            name = ACTION_IDS[self.action_index]
            if name in ("before-contact", "after-contact"):
                require(row.get("command") == "player-health.observe", "Follower Ram player HP command differs")
                if name == "before-contact":
                    self.before = self._health(row)
                    require(self.before.get("hp") == 100 and self.before.get("acceptedHits") == 0,
                            "Follower Ram player did not start at full HP")
                    self._discover(row["snapshot"])
                    actor = self._actor(row["snapshot"], "onix")
                    require(not actor["matchedLayerMask"] & RAM_MASK, "Follower Ram activated during setup")
                    self._attacker_hp(row["snapshot"], actor)
                    self.baseline = deepcopy(self._hp(row["snapshot"], "snorlax"))
                    require(self.baseline["hp"] == self.baseline["maxHp"] and self.baseline["hitCount"] == 0,
                            "Follower Ram Wild target did not start at full HP")
                    self.previous_hp = deepcopy(self.baseline)
                else:
                    self.after = self._health(row)
                    require(self.after.get("hp") == self.before["hp"]
                            and self.after.get("acceptedHits") == self.before["acceptedHits"],
                            "Follower Ram damaged the player")
                self.action_index += 1
                if self.ready:
                    self.terminal = deepcopy(row["snapshot"])
            else:
                self.profile_cache = row.get("profileCache")
                for sample, events, _ in validate_raw_chunk(row, self.latest):
                    self.current_events = list(events); self.observe(sample, events)
                    if self.failures: break
                    self.latest = deepcopy(sample); self.action_frames[self.action_index] += 1
                    if on_sample: on_sample(sample, self.frames)
                limit = {"enter-line": 16, "capture-target": 4, "retreat-player": 32,
                         "observe-charge": WAIT_FRAMES, "finish-knockback": TAIL_FRAMES}[name]
                require(self.action_frames[self.action_index] <= limit, "Follower Ram exceeded its normal input bound")
                if name == "observe-charge" and self.stage("landed") or name != "observe-charge" and self.action_frames[self.action_index] == limit:
                    if name == "capture-target":
                        require(self.capture and self.first_walk,
                                "Follower Ram retreat started before native capture and charge")
                    self.action_index += 1
        except (ValueError, KeyError, TypeError, StopIteration, IndexError) as error:
            self.failures.append(str(error) or type(error).__name__)
        return self.result()

    def _charge_walks(self):
        if not self.first_walk:
            return []
        for motion in self.motion.completed:
            if motion["kind"] != "WALK" or motion["startFrame"] != self.first_walk["frame"] \
                    or not complete_travel(motion):
                continue
            rows = {}
            for name, a, b in (("MOTION_STARTED", 1, motion["duration"]),
                    ("LOGICAL_COMMIT", motion["commitAfter"], 1),
                    ("MOTION_FINISHED", motion["commitAfter"], 1),
                    ("CONTROL_RETURNED", 0, motion["commitAfter"])):
                rows[name] = [e["data"] for e in self._events(name, actor_name="onix")
                    if motion["startFrame"] <= e["frame"] <= motion["finishFrame"]
                    and e["data"].get("reason") == "OK"
                    and (e["data"].get("valueA"), e["data"].get("valueB")) == (a, b)]
            if all(len(events) == 1 for events in rows.values()) \
                    and rows["MOTION_STARTED"][0] == self.first_walk["event"] \
                    and [rows[name][0]["sequence"] for name in rows] == sorted(
                        rows[name][0]["sequence"] for name in rows):
                return [deepcopy(motion)]
        return []

    def stage(self, name):
        return name == "landed" and bool(self.hit and self.jump and self.jump["finished"] and self._charge_walks())

    def finish(self):
        if not self.failures:
            if self.trigger is None:
                self.failures.append("Follower Ram has no native captured-target condition")
            elif self.hit is None:
                self.failures.append("Follower Ram has no real Wild HP loss")
            elif not self._charge_walks():
                self.failures.append("Follower Ram charge has no completed shared Walk")
            elif not self.jump or not self.jump["finished"]:
                self.failures.append("Follower Ram hit has no completed shared Jump3")
        if self.victim_motion.failures:
            self.failures.extend("victim motion: " + f["reason"] for f in self.victim_motion.failures)
        return super().finish()

    @property
    def ready(self):
        return bool(not self.failures and self.action_index == len(ACTION_IDS) and self.stage("landed")
                    and self.frames >= MIN_FRAMES and self.guard_frames >= 10
                    and not self.victim_motion.failures and self.after)

    def result(self):
        return {**super().result(), "observedFrames": self.frames,
                "observedFrameUnit": "completed-game-frame", "trigger": deepcopy(self.trigger),
                "conditionCapture": deepcopy(self.capture), "firstWalk": deepcopy(self.first_walk),
                "completedChargeWalks": self._charge_walks(), "hit": deepcopy(self.hit),
                "jump": deepcopy(self.jump), "jumpArc": self.jump_arc, "guardFrames": self.guard_frames,
                "attackFrames": self.attack_frames, "hpBefore": deepcopy(self.baseline),
                "hpAfter": deepcopy(self.previous_hp), "playerBefore": deepcopy(self.before),
                "playerAfter": deepcopy(self.after)}
