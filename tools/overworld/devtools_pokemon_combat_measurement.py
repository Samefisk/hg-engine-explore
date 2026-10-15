"""One ordinary Ambush damages a Wild target, then a mounted party target."""

from copy import deepcopy

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion


KIND = "pokemon-combat-v1"
REQUIREMENT = "current.pokemon-combat"
WAIT_LIMIT = 420
TAIL_FRAMES = 20
MIN_FRAMES = 35
SETUP = ("attack-tile", "prepare-cyndaquil", "mount-cyndaquil", "settle-mount",
         "bind-cyndaquil", "spawn-snorlax", "bind-snorlax",
         "spawn-weepinbell", "bind-weepinbell")
ORDER = ("before-contact", "observe-attacks", "finish-knockback", "after-contact")
SUBJECTS = (("cyndaquil", 155, "MOUNTED", "existing"),
            ("snorlax", 143, "WILD", "spawn"),
            ("weepinbell", 70, "WILD", "spawn"))
AMBUSH_BIT = 1 << 25


def require(value, message):
    if not value:
        raise ValueError(message)


class PokemonCombatMeasurement:
    def __init__(self, source):
        self.source = source
        self.latest = None
        self.subjects = {}
        self.setup_index = 0
        self.setup_frames = 0
        self.action_index = 0
        self.observed_frames = 0
        self.wait_frames = 0
        self.tail_frames = 0
        self.failures = []
        self.before = None
        self.after = None
        self.baseline = {}
        self.previous_hp = {}
        self.hits = {"cyndaquil": [], "snorlax": []}
        self.arcs = {"cyndaquil": False, "snorlax": False}
        self.lands = {"cyndaquil": False, "snorlax": False}
        self.knockback_origins = {}
        self.forced_knockbacks = {}
        self.queued_knockbacks = {}
        self.protected_frames = 0
        self.attack_frames = 0

    def _boundary(self, snapshot, fixture=True):
        require(isinstance(snapshot, dict)
                and snapshot.get("fieldAvailable") is True
                and snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("romSha256") == self.source["romSha256"]
                and snapshot.get("fieldControl", {}).get("taskPointer") == 0,
                "combat needs a current completed field queue without battle")
        if fixture:
            require(snapshot.get("context", {}).get("mapId") == 33,
                    "combat left its Route29 fixture map")

    def _actor(self, snapshot, name):
        selected = select_current_actor(snapshot, self.subjects[name])
        return next(a for a in snapshot["actors"] if a.get("handle") == selected["handle"])

    def _hp(self, snapshot, name):
        combat = snapshot.get("pokemonCombat", {})
        require(combat.get("schemaVersion") == 1 and combat.get("available") is True
                and combat.get("frame") == snapshot["frame"]
                and combat.get("nativeCycle") == snapshot["nativeCycle"]
                and combat.get("identity", {}).get("overlaySha256") == self.source["overlaySha256"]
                and combat["identity"].get("romSha256") == self.source["romSha256"],
                "combat HP has no current native record")
        actor = self._actor(snapshot, name)
        rows = [row for row in combat.get("targets", []) if row.get("handle") == actor["handle"]]
        require(len(rows) == 1, "combat HP target is missing or stale")
        row = rows[0]
        require(row.get("hp") == row.get("currentHp")
                and row.get("maxHp", 0) >= row.get("hp", -1) > 0
                and row.get("hpSource") == ("party" if actor["role"] == "MOUNTED" else "wild-resident"),
                "combat HP is not the real living target HP")
        if actor["role"] == "MOUNTED":
            party = [mon for mon in snapshot.get("party", [])
                     if mon.get("personality") == row["personality"]]
            require(len(party) == 1 and party[0].get("hp") == row["hp"]
                    and party[0].get("maxHp") == row["maxHp"],
                    "mount HP does not match the saved party Pokémon")
        return row

    @staticmethod
    def _pose(actor, snapshot):
        engine = actor.get("engineObject", {})
        if actor["role"] == "MOUNTED":
            engine = snapshot.get("player", {})
        fields = ("pos_x", "pos_y", "pos_z", "face_y", "unk88_y")
        require(all(type(engine.get(key)) is int for key in fields),
                "combat target has no native pose")
        return (engine["pos_x"], engine["pos_z"],
                engine["pos_y"] + engine["face_y"] + engine["unk88_y"])

    def _profile(self, snapshot, cache):
        attacker = self._actor(snapshot, "weepinbell")
        if not attacker.get("matchedLayerMask", 0) & AMBUSH_BIT:
            return
        require(isinstance(cache, dict)
                and type(cache.get("frame")) is int and cache["frame"] >= snapshot["frame"]
                and cache.get("nativeCycle", -1) >= snapshot["nativeCycle"]
                and attacker.get("behaviorFingerprint")
                    in snapshot.get("nativeObservation", {}).get("profileFingerprints", []),
                "combat attack profile has no coherent native cache")
        rows = [p for p in cache.get("resolvedProfiles", [])
                if p.get("fingerprint") == attacker.get("behaviorFingerprint")
                and p.get("resolved") is True]
        require(len(rows) == 1 and rows[0].get("sourceSha256") == self.source["profileSha256"],
                "combat attack profile differs from the sealed source")
        data = bytes.fromhex(rows[0].get("resultHex", ""))
        require(len(data) == 216 and tuple(data[72:75]) == (1, 16, 20)
                and data[79] == 6,
                "combat source lacks attacking 1/16/20 and Jump1")
        if attacker.get("motionKind") == "HOP" and attacker.get("motionPhase") == "MOVING":
            self.attack_frames += 1

    def _events(self, events, actor):
        result = []
        identity = {key: value for key, value in actor["handle"].items() if key != "value"}
        for event in events:
            data = event.get("data", {})
            if event.get("kind") != "native" or data.get("actorHandle") != actor["handle"]["value"]:
                continue
            require(data.get("actor") == identity
                    and type(data.get("sequence")) is int,
                    "combat motion event has a stale actor generation or failed boundary")
            result.append(data)
        return result

    def _knockback(self, name, actor, hp, sample, events):
        tracked = self.forced_knockbacks.get(name)
        if tracked is not None and tracked["finished"]:
            require(actor["handle"] == tracked["handle"], "combat forced Jump actor generation changed")
            return
        motion = hp.get("motion")
        require(isinstance(motion, dict) and motion == decode_motion(bytes.fromhex(motion.get("rawHex", ""))),
                "combat knockback has no exact native motion plan")
        plan = motion["plan"]
        native = self._events(events, actor)
        starts = [event for event in native if event.get("event") == "MOTION_STARTED"
                  and event.get("valueA") == 2 and event.get("valueB") == 13]
        if tracked is None:
            if not starts:
                if name == "snorlax":
                    require(hp.get("knockbackPending") == 1 and hp.get("knockbackOptions") == 6,
                            "accepted wild hit lost its queued Jump1 knockback")
                    self.queued_knockbacks[name] = True
                return
            require(len(starts) == 1 and starts[0].get("reason") == "OK"
                    and motion["phase"] == "MOVING"
                    and motion["elapsed"] in (0, 1)
                    and plan["version"] == 1 and plan["kind"] == 2
                    and plan["fieldEpoch"] == actor["handle"]["fieldEpoch"]
                    and plan["duration"] == 13 and plan["distance"] == 1
                    and plan["arcHeightQ4"] == 16 and plan["flags"] == 1
                    and plan["targetBaseY"] == plan["startBaseY"]
                    and plan["commitPolicy"] == 1 and plan["pauseFrames"] == 0
                    and plan["visibilityPolicy"] == 0 and plan["reservationId"] > 0
                    and plan["pathAdvancePolicy"] == (2 if actor["role"] == "MOUNTED" else 1)
                    and plan["origin"] == [actor["origin"][key] for key in ("x", "y")]
                    and plan["target"] == [actor["target"][key] for key in ("x", "y")]
                    and abs(plan["target"][0] - plan["origin"][0])
                        + abs(plan["target"][1] - plan["origin"][1]) == 1,
                    "combat motion is not the accepted forced 13-frame Jump1 plan")
            accepted = [event for event in native if event.get("event") == "PLAN_ACCEPTED"
                        and event.get("reason") == "OK"
                        and event.get("valueA") == ((plan["target"][0] & 0xFFFF) << 16 | (plan["target"][1] & 0xFFFF))
                        and event.get("valueB") == 13
                        and event["sequence"] < starts[0]["sequence"]]
            require(len(accepted) == 1,
                    "combat forced Jump has no matching accepted native destination")
            prior = self._actor(self.latest, name)
            if prior.get("motionPhase") not in ("IDLE", "CANCELED"):
                require(plan["origin"] == [prior["target"][key] for key in ("x", "y")]
                        and any(event.get("event") == "MOTION_FINISHED"
                                and event["sequence"] < accepted[0]["sequence"] for event in native),
                        "combat knockback interrupted its accepted normal motion")
            if name == "snorlax":
                require(hp.get("knockbackPending") == 0 and hp.get("knockbackOptions") == 6
                        and (self.queued_knockbacks.get(name) or self.hits[name][-1] == sample["frame"]),
                        "combat forced Jump did not acknowledge the queued wild hit")
            origin = (plan["origin"][0] * 65536 + 32768,
                      plan["origin"][1] * 65536 + 32768,
                      plan["startBaseY"] + (32768 if actor["role"] == "MOUNTED" else 0))
            tracked = dict(hitFrame=self.hits[name][-1], startFrame=sample["frame"],
                           handle=deepcopy(actor["handle"]), plan=deepcopy(plan),
                           startEvent=deepcopy(starts[0]), acceptedEvent=deepcopy(accepted[0]),
                           queuedAcknowledged=name != "snorlax" or hp["knockbackPending"] == 0,
                           finished=False)
            self.forced_knockbacks[name] = tracked
            self.knockback_origins[name] = origin
        require(actor["handle"] == tracked["handle"], "combat forced Jump actor generation changed")
        origin = self.knockback_origins[name]
        pose = self._pose(actor, sample)
        if pose[2] > origin[2] + 4096:
            self.arcs[name] = True
        finished = [event for event in native if event.get("event") == "MOTION_FINISHED"
                    and event.get("reason") == "OK" and event.get("valueB") == 2]
        if finished:
            returned = [event for event in native if event.get("event") == "CONTROL_RETURNED"
                        and event.get("reason") == "OK"
                        and event.get("valueA") == int(actor["role"] == "MOUNTED")
                        and event["sequence"] > finished[0]["sequence"]]
            target = (tracked["plan"]["target"][0] * 65536 + 32768,
                      tracked["plan"]["target"][1] * 65536 + 32768,
                      tracked["plan"]["targetBaseY"] + (32768 if actor["role"] == "MOUNTED" else 0))
            require(len(finished) == len(returned) == 1 and self.arcs[name]
                    and pose == target and abs(pose[0] - origin[0]) + abs(pose[1] - origin[1]) == 65536
                    and actor.get("inputOwnership") == int(actor["role"] == "MOUNTED")
                    and actor.get("reservationId") != tracked["plan"]["reservationId"],
                    "combat forced Jump did not land one tile and release its control")
            tracked.update(finished=True, finishFrame=sample["frame"],
                           finishEvent=deepcopy(finished[0]), controlEvent=deepcopy(returned[0]))
            self.lands[name] = True
        else:
            require(plan == tracked["plan"] and motion["phase"] in ("MOVING", "COMMIT_PENDING")
                    and motion["elapsed"] <= 13,
                    "combat forced Jump plan changed before its native finish")

    def _sample(self, sample, cache, events):
        self._boundary(sample)
        require(sample["frame"] == self.latest["frame"] + 1,
                "combat skipped or repeated a completed game frame")
        self._profile(sample, cache)
        source = self._hp(sample, "weepinbell")
        require(source["hitCount"] == 0 and source["hp"] == self.baseline["weepinbell"]["hp"],
                "attacker damaged itself or a non-attacking Pokémon caused damage")
        for name in self.hits:
            hp = self._hp(sample, name)
            previous = self.previous_hp[name]
            require(hp["maxHp"] == previous["maxHp"], "target max HP changed")
            delta = previous["hp"] - hp["hp"]
            hits = hp["hitCount"] - previous["hitCount"]
            require(delta in (0, 20) and hits == int(delta == 20),
                    "collision damage is not one fixed 20-HP hit")
            if hits:
                require(hp["lastDamage"] == 20 and hp["immunityFrames"] >= 59,
                        "accepted Pokémon hit has no 60-frame target guard")
                require(not self.hits[name] or sample["frame"] - self.hits[name][-1] >= 60,
                        "target was damaged twice inside its hit guard")
                self.hits[name].append(sample["frame"])
                self.forced_knockbacks.pop(name, None)
                self.queued_knockbacks.pop(name, None)
                self.arcs[name] = self.lands[name] = False
            if self.hits[name]:
                actor = self._actor(sample, name)
                if hp["immunityFrames"]:
                    self.protected_frames += 1
                self._knockback(name, actor, hp, sample, events)
                if name == "cyndaquil":
                    mount = actor["engineObject"]
                    player = sample["player"]
                    require(mount.get("pos_x") == player.get("pos_x")
                            and mount.get("pos_z") == player.get("pos_z")
                            and player.get("face_y") - mount.get("face_y", 0) == 32768,
                            "mounted knockback split rider and mount or changed seat height")
            self.previous_hp[name] = deepcopy(hp)
        self.latest = deepcopy(sample)
        self.observed_frames += 1

    def _health_command(self, row):
        sample = row.get("snapshot")
        self._boundary(sample)
        require(all(sample.get(k) == self.latest.get(k)
                    for k in ("frame", "nativeCycle", "actors", "player", "pokemonCombat")),
                "combat final HP read is not the last completed frame")
        hp = row.get("receipt", {}).get("playerHealth", {})
        require(hp.get("hp") == hp.get("savedHp") and hp.get("maxHp") == 100
                and hp.get("identity", {}).get("overlaySha256") == self.source["overlaySha256"]
                and hp.get("recoveryPending") is False
                and hp.get("frame") == sample["frame"],
                "combat rider HP has no matching saved native record")
        return deepcopy(hp)

    def observe_record(self, row, on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup", "combat initial frame is misplaced")
                self._boundary(row["initialSnapshot"], fixture=False)
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            require(self.latest is not None, "combat initial frame is missing")
            if row.get("phase") == "setup":
                require(self.setup_index < len(SETUP) and row.get("action") == SETUP[self.setup_index],
                        "combat setup order differs")
                if row.get("action") == "settle-mount":
                    for sample, _, _ in validate_raw_chunk(row, self.latest):
                        self._boundary(sample)
                        self.latest = deepcopy(sample)
                        self.setup_frames += 1
                        if on_sample:
                            on_sample(sample, self.observed_frames)
                    require(self.setup_frames <= 16, "combat mount settle exceeded its bound")
                    if self.setup_frames == 16:
                        self.setup_index += 1
                    return self.result()
                snapshot = row.get("snapshot")
                self._boundary(snapshot)
                name = {"bind-cyndaquil": "cyndaquil", "bind-snorlax": "snorlax",
                        "bind-weepinbell": "weepinbell"}.get(row["action"])
                if name:
                    require(row.get("command") == "bind", "combat subject did not bind normally")
                    self.subjects[name] = deepcopy(row.get("receipt"))
                    actor = self._actor(snapshot, name)
                    expected = next(s for s in SUBJECTS if s[0] == name)
                    require((actor["species"], actor["role"]) == expected[1:3], "combat actor role/species differs")
                self.latest = deepcopy(snapshot)
                self.setup_index += 1
                return self.result()
            require(self.setup_index == len(SETUP) and row.get("phase") == "observe"
                    and self.action_index < len(ORDER) and row.get("action") == ORDER[self.action_index],
                    "combat observation order differs")
            name = ORDER[self.action_index]
            if name in ("observe-attacks", "finish-knockback"):
                require("command" not in row, "combat input did not retain completed frames")
                for sample, events, _ in validate_raw_chunk(row, self.latest):
                    self._sample(sample, row.get("profileCache"), events)
                    if name == "observe-attacks":
                        self.wait_frames += 1
                    else:
                        self.tail_frames += 1
                    if on_sample:
                        on_sample(sample, self.observed_frames)
                require(self.wait_frames <= WAIT_LIMIT and self.tail_frames <= TAIL_FRAMES,
                        "combat exceeded its bounded attack/tail window")
                if (name == "observe-attacks" and self.stage("landed")
                        or name == "finish-knockback" and self.tail_frames == TAIL_FRAMES):
                    self.action_index += 1
                return self.result()
            require(row.get("command") == "player-health.observe", "combat rider HP command differs")
            if name == "before-contact":
                self.before = self._health_command(row)
                require(self.before.get("hp") == 100 and self.before.get("acceptedHits") == 0,
                        "combat rider did not start at full HP")
                self.baseline = {n: deepcopy(self._hp(row["snapshot"], n)) for n, *_ in SUBJECTS}
                require(all(hp["hp"] == hp["maxHp"] and hp["hitCount"] == 0 for hp in self.baseline.values()),
                        "combat Pokémon did not start at their normal full HP")
                self.previous_hp = {n: deepcopy(self.baseline[n]) for n in self.hits}
            else:
                self.after = self._health_command(row)
                hits = len(self.hits["cyndaquil"])
                require(hits > 0 and self.after.get("hp") == 100 - hits * 20
                        and self.after.get("acceptedHits") == hits,
                        "one mounted collision did not damage both rider and party Pokémon")
                require(self.stage("landed") and self.protected_frames >= 10,
                        "combat ended before both knockbacks landed and hit guards were observed")
            self.action_index += 1
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error) or type(error).__name__)
        return self.result()

    def stage(self, name):
        return name == "landed" and all(self.hits.values()) and all(self.arcs.values()) and all(self.lands.values())

    def result(self):
        ready = self.action_index == len(ORDER) and not self.failures and self.observed_frames >= MIN_FRAMES
        return dict(kind=KIND, passed=ready, ready=ready, acceptedProof=False,
                    observedFrames=self.observed_frames, observedFrameUnit="completed-game-frame",
                    subjects=deepcopy(self.subjects), hits=deepcopy(self.hits),
                    jumpArcs=deepcopy(self.arcs), landed=deepcopy(self.lands),
                    forcedKnockbacks=deepcopy(self.forced_knockbacks),
                    protectedFrames=self.protected_frames, attackFrames=self.attack_frames,
                    hpBefore=deepcopy(self.baseline), hpAfter=deepcopy(self.previous_hp),
                    riderBefore=deepcopy(self.before), riderAfter=deepcopy(self.after),
                    failures=list(self.failures))

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("combat ended before real Pokémon HP loss and both completed knockbacks")
        return {"passed": self.result()["ready"], "failures": list(self.failures)}
