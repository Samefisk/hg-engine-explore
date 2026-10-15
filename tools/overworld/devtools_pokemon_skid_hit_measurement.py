"""One natural Ambush hit interrupts a mounted skid with Crash, then Jump1.

Uses the current combat HP reader, completed native queue, motion events and
the shared exact Jump checker. Setup is excluded from observed frame counts.
"""
from copy import deepcopy

from tools.overworld.devtools_pokemon_combat_measurement import (
    PokemonCombatMeasurement, AMBUSH_BIT, require)
from tools.overworld.devtools_raw_chunk import validate_raw_chunk


KIND = "pokemon-skid-hit-v1"
REQUIREMENT = "current.pokemon-skid-hit"
SCENARIO = "pokemon-hp.skid-hit-crash-knockback"
MIN_FRAMES = 64
SUBJECTS = (("stantler", 234, "MOUNTED", "existing"),
            ("weepinbell", 70, "WILD", "spawn"))
FILLERS = (69, 43, 44, 45, 182)
SETUP = ("attack-tile", "prepare-stantler", "mount-stantler", "settle-mount",
         "bind-stantler", "configure-mount", *("spawn-filler-"+str(s) for s in FILLERS),
         "spawn-weepinbell", "settle-attacker", "bind-weepinbell", "arm-contact")
ORDER = ("before-contact", "run-up", "turn", "settle-knockback", "after-contact")
INPUTS = {"run-up": (8, ["UP"]), "turn": (24, ["RIGHT"]), "settle-knockback": (32, [])}
SETUP_STEPS = {"settle-mount": 16, "settle-attacker": 50, "arm-contact": 1}
SETUP_SPEC = (
    ("teleport", dict(map=33, x=586, z=407, facing=0)),
    ("party", dict(slot=0, species=234, level=50)),
    ("spawn", dict(species=234, form=0, role="mounted", slot=0, level=50)),
    ("step", dict(frames=16, keys=[])), ("bind", dict(subject="stantler")),
    ("mount-walk.configure", dict(subject="stantler", directionMode=0, travelTime=4,
                                 turning="free", crashSound="wall-hit", timeVariance=0)),
    *(("spawn", dict(species=s, form=0, role="wild", level=10, x=583, z=401+i))
      for i, s in enumerate(FILLERS)),
    ("spawn", dict(species=70, form=0, role="wild", level=10, x=586, z=402)),
    ("step", dict(frames=50, keys=[])), ("bind", dict(subject="weepinbell")),
    ("step", dict(frames=1, keys=[])),
)


def accepted_skid_hit(previous, current, before, after, native_events):
    """The same assertion also rejects the retained pre-fix native recording."""
    require(before["hp"]-after["hp"] == 20
            and after["hitCount"] == before["hitCount"]+1 and after["lastDamage"] == 20,
            "skid hit is not one accepted native 20-HP collision")
    motion = before["motion"]
    require(motion["plan"]["kind"] == 4 and motion["phase"] == "MOVING"
            and previous.get("movementPolicy", {}).get("skid") == 1,
            "accepted hit did not occur during an active native SKID")
    crashes = [e for e in native_events if e.get("event") == "WORLD_EFFECT" and e.get("valueA") == 3]
    require(len(crashes) == 1 and crashes[0].get("reason") == "OK",
            "accepted skid hit did not publish exactly one immediate Crash")
    require(current["handle"] == previous["handle"], "skid hit changed the actor generation")
    require(after.get("crashPhase") in ("NEEDS_SETTLE", "PLAYING")
            and after.get("knockbackRawFlags") in (10, 12)
            and after.get("crashMotionIdentity") == motion["plan"]["reservationId"] > 0,
            "skid hit did not retain the interrupted motion identity in Crash")
    return deepcopy(crashes[0])


class PokemonSkidHitMeasurement(PokemonCombatMeasurement):
    def __init__(self, source):
        super().__init__(source)
        self.hits = {"stantler": []}
        self.arcs = {"stantler": False}
        self.lands = {"stantler": False}
        self.crash = None
        self.crash_effects = []
        self.input_frames = {name: 0 for name in INPUTS}
        self.setup_step_frames = {name: 0 for name in SETUP_STEPS}
        self.clean_frames = 0
        self.admission = None
        self.configuration = None

    def _configure(self, row, sample):
        q = row["receipt"].get("value", row["receipt"])
        require(q.get("completed") is True and q.get("prepared") is True
                and q.get("acceptedProof") is False and q.get("guestAdvanced") is False
                and q.get("scope") == "prepared-idle-mounted-walk-fixture"
                and q.get("directionMode") == 0 and q.get("travelTime") == 4
                and q.get("turning") == "free" and q.get("crashSound") == "wall-hit"
                and q.get("timeVariance") == 0
                and q.get("changedOffsets") == [7, 19, 50, 51, 64, 65],
                "skid-hit configure must name only its deterministic prepared Walk fields")
        before, after = q["before"], q["after"]
        original = bytes.fromhex(before["mountStateHex"])
        actual = bytes.fromhex(after["mountStateHex"])
        require(len(original) == len(actual) == 192, "skid-hit configure state size differs")
        expected = bytearray(original)
        for offset, value in ((7, 4), (19, 0), (50, 0), (51, 4),
                              (64, original[72] & 1), (65, (original[73] & ~1) | 16)):
            expected[8+offset] = value
        require(actual == bytes(expected) and q["expectedStateHex"] == actual.hex()
                and before["profileHex"] == original[8:88].hex()
                and after["profileHex"] == actual[8:88].hex()
                and before["bindingHex"] == after["bindingHex"] == actual[88:104].hex()
                and original[88:104] == actual[88:104]
                and before["readiness"] == after["readiness"]
                and before["clock"] == after["clock"] == dict(frame=sample["frame"], nativeCycle=sample["nativeCycle"])
                and before["sessionGeneration"] == after["sessionGeneration"],
                "skid-hit configure changed packed neighbors, binding, clock or unrelated state")
        actor = self._actor(sample, "stantler")
        selected = self.subjects["stantler"]
        from tools.overworld.devtools_records import select_current_actor
        require(select_current_actor(sample, q["subject"])["handle"] == selected["handle"]
                and actor["motionPhase"] == "IDLE" and actor["motionKind"] == "NONE"
                and actor["reservationId"] == 0
                and before["readiness"]["actor"]["handle"] == actor["handle"],
                "skid-hit configure is not the same idle mounted generation")
        self.configuration = deepcopy(q)

    def _admit(self, sample):
        mount, attacker = (self._actor(sample, n) for n in ("stantler", "weepinbell"))
        timers = sample.get("pokemonCombat", {}).get("movementTimers", [])
        timer = [t for t in timers if t.get("handle") == attacker["handle"]]
        require(len(timer) == 1 and timer[0].get("movementCooldown") == 9
                and timer[0].get("movementEmoteTimer") == 0
                and attacker.get("movementPolicy", {}).get("spotState") == 0
                and not attacker.get("matchedLayerMask", 0) & AMBUSH_BIT
                and attacker.get("logical") == dict(x=586, y=402)
                and attacker.get("engineObject", {}).get("facing") == 1
                and mount.get("logical") == dict(x=586, y=407)
                and mount.get("engineObject", {}).get("facing") == 0,
                "skid-hit starting placement, Down-facing CHILL or natural cooldown9 differs")
        self.admission = deepcopy(timer[0])

    def _ground(self, sample, actor, hp):
        motion = hp["motion"]
        require(motion["phase"] == "IDLE" and actor.get("motionKind") == "NONE"
                and actor.get("reservationId") == 0 and actor.get("inputOwnership") == 1,
                "Crash did not settle the old motion and hold mounted control")
        tile = [self.crash["oldLogical"][key] for key in ("x", "y")]
        engine = actor["engineObject"]
        body = (engine["pos_x"], engine["pos_z"], engine["pos_y"]+engine["face_y"]+engine["unk88_y"])
        expected = (tile[0]*65536+32768, tile[1]*65536+32768, self.crash["oldPlan"]["startBaseY"])
        require(body == expected and self._pose(actor, sample) == (expected[0], expected[1], expected[2]+32768),
                "Crash did not restore the current logical ground and shared mounted seat")
        self.crash.setdefault("groundFrame", sample["frame"])
        self.crash["groundPose"] = body

    def _sample(self, sample, cache, events):
        self._boundary(sample)
        require(sample["frame"] == self.latest["frame"] + 1,
                "skid hit skipped or repeated a completed frame")
        actor = self._actor(sample, "stantler")
        attacker = self._actor(sample, "weepinbell")
        self._profile(sample, cache)
        hp = self._hp(sample, "stantler")
        native = self._events(events, actor)
        crashes = [e for e in native if e.get("event") == "WORLD_EFFECT" and e.get("valueA") == 3]
        previous = self.previous_hp["stantler"]
        require(hp["maxHp"] == previous["maxHp"], "skid-hit target max HP changed")
        delta = hp["hitCount"]-previous["hitCount"]
        require(delta in (0, 1), "skid-hit native hit count was lost or repeated")
        if delta:
            require(self.crash is None and attacker.get("motionKind") == "HOP"
                    and attacker.get("motionPhase") == "MOVING"
                    and attacker.get("matchedLayerMask", 0) & AMBUSH_BIT,
                    "skid hit has no one ordinary attacking Ambush Hop")
            require(hp["immunityFrames"] >= 59, "skid hit has no native per-target hit guard")
            prior_actor = self._actor(self.latest, "stantler")
            effect = accepted_skid_hit(prior_actor, actor, previous, hp, native)
            self.hits["stantler"].append(sample["frame"])
            self.crash = dict(hitFrame=sample["frame"], effect=effect,
                oldPlan=deepcopy(previous["motion"]["plan"]),
                # The engine can already publish its destination as logical
                # before native commit. Crash settles this uncommitted plan
                # at its saved origin, never at that early logical target.
                oldLogical=dict(zip(("x", "y"), previous["motion"]["plan"]["origin"])),
                identity=hp["crashMotionIdentity"], handle=deepcopy(actor["handle"]), finished=False)
        self.crash_effects.extend(crashes)
        if self.crash is not None:
            require(len(self.crash_effects) == 1, "skid hit repeated its Crash effect")
            require(hp["hitCount"] == self.baseline["stantler"]["hitCount"]+1
                    and hp["hp"] == self.baseline["stantler"]["hp"]-20,
                    "skid-hit damage changed during its Crash or knockback")
            require(not any(e.get("event") == "MOTION_CANCELED"
                    or e.get("event") in ("LOGICAL_COMMIT", "MOTION_FINISHED") and e.get("valueB") == 4
                    for e in native), "interrupted SKID committed, finished or canceled after its hit")
            if hp["crashPhase"] == "NEEDS_SETTLE":
                require(hp["motion"]["phase"] == "SUSPENDED"
                        and hp["motion"]["plan"] == self.crash["oldPlan"]
                        and hp["crashMotionIdentity"] == self.crash["identity"],
                        "Crash did not freeze the exact interrupted native SKID")
            elif hp["crashPhase"] == "PLAYING":
                require(hp["crashMotionIdentity"] == self.crash["identity"]
                        and hp["knockbackRawFlags"] == 12 and hp["knockbackPending"] == 0,
                        "grounded Crash lost its queued hit or motion identity")
                self._ground(sample, actor, hp)
            elif not self.crash["finished"]:
                require("groundFrame" in self.crash and hp["crashMotionIdentity"] == 0
                        and hp["knockbackPending"] == 0
                        and sample["frame"]-self.crash["groundFrame"] == 4,
                        "knockback started before Crash ground restoration and completion")
                self._ground(sample, actor, hp)
                self.crash.update(finished=True, finishFrame=sample["frame"])
            if not self.crash["finished"]:
                require(not any(e.get("event") == "CONTROL_RETURNED"
                        or e.get("event") == "MOTION_STARTED" and e.get("valueA") == 2 for e in native),
                        "Crash released control or started knockback before completion")
            else:
                self._knockback("stantler", actor, hp, sample, events)
                jump = self.forced_knockbacks.get("stantler")
                if sample["frame"] == self.crash["finishFrame"]:
                    require(jump is None and hp["knockbackPending"] == 0,
                            "Crash completion lost its held queued knockback boundary")
                    self.previous_hp["stantler"] = deepcopy(hp)
                    self.latest = deepcopy(sample)
                    self.observed_frames += 1
                    return
                require(jump is not None and jump["startFrame"] == self.crash["finishFrame"]+1
                        and hp["knockbackPending"] == 0
                        and jump["plan"]["origin"] == [self.crash["oldLogical"][key] for key in ("x", "y")],
                        "Crash did not hand its restored ground directly to the same forced Jump")
                if jump["finished"]:
                    target = jump["plan"]["target"]
                    pose = (target[0]*65536+32768, target[1]*65536+32768,
                            jump["plan"]["targetBaseY"]+32768)
                    require(self._pose(actor, sample) == pose and actor.get("inputOwnership") == 1,
                            "mounted knockback did not keep its landed height and released control")
                    self.clean_frames += 1
        else:
            require(not crashes and hp["hp"] == previous["hp"], "Crash appeared without an accepted skid hit")
        self.previous_hp["stantler"] = deepcopy(hp)
        self.latest = deepcopy(sample)
        self.observed_frames += 1

    def observe_record(self, row, on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup", "skid-hit initial frame is misplaced")
                self._boundary(row["initialSnapshot"], fixture=False)
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            require(self.latest is not None, "skid-hit initial frame is missing")
            if row.get("phase") == "setup":
                require(self.setup_index < len(SETUP) and row.get("action") == SETUP[self.setup_index],
                        "skid-hit setup order differs")
                action = row["action"]
                if action in SETUP_STEPS:
                    for sample, _, _ in validate_raw_chunk(row, self.latest):
                        self._boundary(sample)
                        self.latest = deepcopy(sample)
                        self.setup_step_frames[action] += 1
                        if on_sample: on_sample(sample, self.observed_frames)
                    require(self.setup_step_frames[action] <= SETUP_STEPS[action], "skid-hit setup wait exceeded its bound")
                    if self.setup_step_frames[action] == SETUP_STEPS[action]: self.setup_index += 1
                    return self.result()
                sample = row["snapshot"]
                self._boundary(sample)
                if action == "configure-mount":
                    self._configure(row, sample)
                if action.startswith("bind-"):
                    name = action.removeprefix("bind-")
                    self.subjects[name] = deepcopy(row["receipt"])
                    actor = self._actor(sample, name)
                    expected = next(s for s in SUBJECTS if s[0] == name)
                    require((actor["species"], actor["role"]) == expected[1:3], "skid-hit subject role/species differs")
                self.latest = deepcopy(sample)
                self.setup_index += 1
                return self.result()
            require(self.setup_index == len(SETUP) and row.get("phase") == "observe"
                    and self.action_index < len(ORDER) and row.get("action") == ORDER[self.action_index],
                    "skid-hit observation order differs")
            action = ORDER[self.action_index]
            if action in INPUTS:
                for sample, events, _ in validate_raw_chunk(row, self.latest):
                    self._sample(sample, row.get("profileCache"), events)
                    self.input_frames[action] += 1
                    if on_sample: on_sample(sample, self.observed_frames)
                require(self.input_frames[action] <= INPUTS[action][0], "skid-hit input exceeded its exact frame bound")
                if self.input_frames[action] == INPUTS[action][0]: self.action_index += 1
                return self.result()
            require(row.get("command") == "player-health.observe", "skid-hit rider HP observation differs")
            if action == "before-contact":
                self.before = self._health_command(row)
                self._admit(row["snapshot"])
                hp = self._hp(row["snapshot"], "stantler")
                require(hp["hp"] == hp["maxHp"] > 20 and hp["hitCount"] == 0,
                        "skid-hit mount did not start at its real full native HP")
                self.baseline = {"stantler": deepcopy(hp)}
                self.previous_hp = deepcopy(self.baseline)
            else:
                self.after = self._health_command(row)
                require(self.after["hp"] == self.before["hp"]-20
                        and self.after["acceptedHits"] == self.before["acceptedHits"]+1,
                        "the same skid collision did not damage rider and mount once")
                require(self.stage("landed") and self.clean_frames >= 10,
                        "skid-hit ended before one Crash, Jump landing and ten clean restored frames")
            self.latest = deepcopy(row["snapshot"])
            self.action_index += 1
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error) or type(error).__name__)
        return self.result()

    def stage(self, name):
        return (name == "landed" and self.crash is not None and self.crash["finished"]
                and self.lands["stantler"] and self.arcs["stantler"])

    def result(self):
        ready = self.action_index == len(ORDER) and not self.failures and self.observed_frames == MIN_FRAMES
        return dict(kind=KIND, ready=ready, passed=ready, acceptedProof=False,
            observedFrames=self.observed_frames, observedFrameUnit="completed-game-frame",
            subjects=deepcopy(self.subjects), admission=deepcopy(self.admission),
            configuration=deepcopy(self.configuration),
            hits=deepcopy(self.hits), crash=deepcopy(self.crash), crashEffects=deepcopy(self.crash_effects),
            forcedKnockbacks=deepcopy(self.forced_knockbacks), jumpArcs=deepcopy(self.arcs),
            landed=deepcopy(self.lands), cleanFrames=self.clean_frames, attackFrames=self.attack_frames,
            hpBefore=deepcopy(self.baseline), hpAfter=deepcopy(self.previous_hp),
            riderBefore=deepcopy(self.before), riderAfter=deepcopy(self.after), failures=list(self.failures))

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("skid-hit ended before one immediate Crash and the same restored Jump knockback")
        return dict(passed=self.result()["ready"], failures=list(self.failures))
