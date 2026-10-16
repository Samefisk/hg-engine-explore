"""Natural Onix charge: same-intent entry, fixed heading, then real Crash."""
from copy import deepcopy
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_profile_feature_measurement import (
    ProfileFeatureMeasurement, require, application_index,
)

KIND = "ram-until-crash-v1"
REQUIREMENT = "current.ram-until-crash"
BEHIND = "ram-behind-entry-v1"
BEHIND_REQUIREMENT = "current.ram-behind-entry"
CONDITION = 20305
COOLDOWN = 100
POST_CRASH_FRAMES = 16


APPLICATION = application_index("apply-ram")
RAM_MASK = 1 << APPLICATION


def validate_recipe(test):
    behind = test['measurements'][0]['kind'] == BEHIND
    kind = BEHIND if behind else KIND
    player, origin, dodge = ((594,399),(594,404),"RIGHT") if behind else ((607,402),(602,402),"DOWN")
    setup = (("teleport", {"map": 33, "x": player[0], "z": player[1], "facing": 2}),
             ("spawn", {"species": 95, "form": 0, "role": "wild", "level": 5,
                        "x": origin[0], "z": origin[1]}), ("bind", {"subject": "onix"}))
    if behind:
        setup = setup[:1] + (("party", {"slot": 0, "species": 155, "level": 20}),
            ("spawn", {"species": 155, "form": 0, "role": "follower", "slot": 0, "level": 20})) + setup[1:]
    start = {"kind": "measurement-stage", "measurement": kind,
             "stage": "charge-started", "when": "final"}
    end = {"kind": "measurement-complete", "measurement": kind, "when": "final"}
    actions = (("step", {"frames": 120, "keys": [], "until": start}),
               ("step", {"frames": 16, "keys": [dodge]}),
               ("step", {"frames": 480, "keys": [], "until": end}))
    require(tuple((a["op"], a["args"]) for a in test["setup"]) == setup
            and tuple((a["op"], a["args"]) for a in test["actions"]) == actions
            and test["budgets"]["minObservedFrames"] == 115
            and test["budgets"]["maxFrames"] <= 850,
            "Ram fixture or normal dodge input differs")


class RamUntilCrashMeasurement(ProfileFeatureMeasurement):
    def __init__(self, kind=KIND, test=None, max_frames=850):
        super().__init__(kind, test, max_frames)
        self.current_events = []
        self.trigger = self.first_walk = self.crash = self.closed_condition = None
        self.heading = None
        self.walks = []
        self.off_axis = self.long_charge = False
        self.policy_calls = []
        self.cooldown_samples = []
        self.condition_reader_identity = None
        self.crash_terminal_overlap = None
        self.entry_candidate = self.entry_witness = None
        self.entry_reset = None
        self.passive_follower = None
        self.expected_entry = "behind" if kind == BEHIND else "side"

    def observe(self, snapshot, events):
        self.current_events = list(events)
        return super().observe(snapshot, events)

    def _policy(self, snapshot, actor):
        for event in self.current_events:
            data = event.get("data", {})
            if event.get("kind") != "native-observation" \
                    or data.get("observation") != "walk-policy" \
                    or data.get("slot") != actor["handle"]["slot"]:
                continue
            require(all(isinstance(data.get(name), dict) and all(
                data[name].get(k) == actor.get(k) for k in (
                    "handle", "subjectIdentity", "species", "role",
                    "authorityGeneration", "engineAnchorGeneration", "presentationGeneration"))
                for name in ("publicSubject", "publicSubjectAfter")),
                "Ram policy receipt has a stale owner")
            request, response = (bytes.fromhex(data[k]) for k in ("requestHex", "responseHex"))
            require(len(request) == len(response) == 28
                    and request[:4] == response[:4] == b"\x01\x00\x1c\x00"
                    and request[8:10] == response[8:10] == bytes((actor["handle"]["slot"], data["operation"]))
                    and event["frame"] == snapshot["frame"] and data.get("returnValue") == 1,
                    "Ram policy ABI or completed boundary differs")
            if self.trigger is None or self.crash is not None:
                continue
            if data["operation"] == 0:
                # Reset receipts have no private state payload. The following
                # real Input reads that same owner's post-reset state before
                # its reducer can initialize the new run.
                following = [e["data"] for e in self.current_events
                    if e.get("kind") == "native-observation"
                    and e.get("frame") == event["frame"]
                    and e.get("data", {}).get("observation") == "walk-policy"
                    and e["data"].get("operation") == 1
                    and e["data"].get("slot") == data["slot"]
                    and e["data"].get("sequence", -1) > data.get("sequence", -1)
                    and e["data"].get("publicSubject", {}).get("handle") == actor["handle"]]
                after = bytes.fromhex(following[0].get("policyBeforeHex", "")) if len(following) == 1 else b""
                require(self.entry_reset is None and self.entry_witness is not None
                        and event["frame"] == self.trigger["frame"]
                        and self.first_walk is not None
                        and self.first_walk["frame"] == event["frame"]
                        and len(after) == 36
                        and after[:8] == bytes.fromhex("ff000000ff000000")
                        and after[16:20] == bytes(4)
                        and after[20] == 255 and after[21:24] == bytes(3)
                        and after[25] == 0 and after[32:] == bytes(4),
                        "Ram reset momentum outside fresh charge admission")
                self.entry_reset = deepcopy(event)
                continue
            if data["operation"] == 1 and response[16] == 2 and self.heading is not None:
                before = bytes.fromhex(data["policyBeforeHex"])
                require(len(before) == 36 and response[17] == self.heading
                        and 1 <= response[19] <= 32,
                        "Ram input lost its committed heading")
                if before[2] and before[4] == request[13]:
                    if before[34]:
                        # Linear duration carries a Q8 fraction across accepted
                        # tiles. A legal next tile can take one more frame than
                        # lastWalkTime while nominal speed keeps accelerating.
                        lane = bytes.fromhex(data["laneHex"])
                        require(before[34] == 1 and len(lane) == 80 and lane[71] == 34
                                and not lane[65] & 32 and lane[19] >> 2 == 0
                                and before[3] == lane[7]
                                and 1 <= lane[51] <= lane[7] <= 32
                                and lane[50] > 0,
                                "Ram Linear timing lane differs")
                        base, fastest, ramp, elapsed = lane[7], lane[51], lane[50], before[32]
                        q8 = fastest << 8 if elapsed >= ramp else (
                            base * fastest * ramp << 8) // (
                                fastest * ramp + (base - fastest) * elapsed)
                        expected = max(1, min(32, (q8 + before[33]) >> 8))
                        require(response[19] == expected,
                                "Ram profile entry slowed or reset current speed")
                    else:
                        visible = before[25] or before[2]
                        require(response[19] <= visible,
                                "Ram profile entry slowed or reset current speed")
                self.policy_calls.append({"frame": event["frame"], "travelTime": response[19],
                                          "beforeHex": before.hex(), "responseHex": response.hex()})

    def _entry(self, snapshot, actor):
        # An initial native spawn command is not idle. Only a completed queue
        # with centered, inactive native owner and no reservation grants entry.
        if self.test is None:
            return
        frame = snapshot["frame"]; engine = actor["engineObject"]
        if self.trigger is None:
            if actor["motionKind"] != "NONE" or actor["motionPhase"] != "IDLE" or actor["reservationId"] != 0 \
                    or engine.get("movement_cmd") not in (0,1,2,3,255) or engine.get("flags",2)&2 \
                    or engine.get("unk88_y") != 0 \
                    or [engine.get("pos_x"),engine.get("pos_z")] != [(actor["logical"][k]<<16)+32768 for k in ("x","y")]:
                return
            state, _, owner = self._condition_state(snapshot, actor)
            require(not state["flags"]&1 and not actor["matchedLayerMask"]&RAM_MASK,
                    "Ram pretrigger idle is already active")
            self.entry_candidate = dict(frame=frame,actorFrame=snapshot["actorFrame"],
                actor=deepcopy(actor),player=deepcopy(snapshot["player"]),condition=deepcopy(state),owner=deepcopy(owner))
        elif self.entry_witness is None:
            pre = self.entry_candidate
            require(pre is not None and pre["frame"] == self.trigger["frame"]-1,
                    "Ram lacks immediately preceding authenticated inactive idle")
            origin = tuple(pre["actor"]["logical"][k] for k in ("x","y"))
            player = tuple(pre["player"][k] for k in ("x","y")); dx,dy=(b-a for a,b in zip(origin,player))
            vectors=((0,-1),(0,1),(-1,0),(1,0)); facing=pre["actor"]["engineObject"].get("facing")
            require(facing == 1 and ((dx==0) != (dy==0)) and 0<abs(dx)+abs(dy)<=32,
                    "Ram pretrigger native facing, cardinal alignment or range differs")
            fx,fy=vectors[facing]; dot=dx*fx+dy*fy
            geometry="side" if dot==0 else "behind" if dot<0 else "front"
            require(geometry == self.expected_entry, "Ram inactive entry is not the requested "+self.expected_entry)
            require(tuple(snapshot["player"][k] for k in ("x","y")) == player,
                    "Ram target moved before activation")
            self.entry_witness = dict(**deepcopy(pre),geometry=geometry,delta=[dx,dy],triggerFrame=self.trigger["frame"])

    def _sample(self, snapshot, actors):
        actor = actors["onix"]
        if self.kind == BEHIND and self.test is not None and self.passive_follower is None:
            # This prepared Ram case isolates the charge from the saved
            # Mankey's intended sight pickup. It does not relax Ram's Reset
            # or Crash rules when another actor takes ownership of Onix.
            followers = [a for a in snapshot["actors"]
                if a.get("active") is True and a.get("role") == "FOLLOWER"]
            require(len(followers) == 1 and followers[0].get("species") == 155
                    and followers[0].get("level") == 20 and followers[0]["handle"]["slot"] == 7,
                    "Ram passive follower setup differs")
            follower = followers[0]
            selected = select_current_actor(snapshot, follower)
            throw_mask = sum(1 << application_index(name) for name in (
                "apply-throw", "apply-throw-find-position", "apply-throw-release", "apply-throw-away"))
            require(not follower["matchedLayerMask"] & throw_mask,
                    "Ram passive follower has a Throw profile")
            health = [h for h in snapshot.get("pokemonCombat", {}).get("targets", [])
                if h.get("handle") == follower["handle"]]
            require(len(health) == 1 and health[0].get("role") == "FOLLOWER"
                    and health[0].get("hpMirrorMatches") is True
                    and health[0].get("hp") == health[0].get("maxHp")
                    and health[0].get("maxHp", 0) > 0,
                    "Ram passive follower is not current and healthy")
            self.passive_follower = {"frame": snapshot["frame"], "actor": selected,
                                     "health": deepcopy(health[0])}
        require(snapshot["context"] == self.initial["context"]
                and snapshot["context"]["mapId"] == 33,
                "Ram charge changed field context")
        frame = snapshot["frame"]
        events = [e for e in self.current_events if e.get("kind") == "native"
                  and e.get("data", {}).get("actorHandle") == actor["handle"]["value"]]
        crashes = [e for e in events if e["data"].get("event") == "WORLD_EFFECT"
                   and e["data"].get("valueA") == 3]
        if crashes and (self.trigger is not None or any(c["triggered"] for c in self.conditions)):
            require(all(e["data"].get("actor") == {k: v for k, v in actor["handle"].items()
                        if k != "value"} and e["data"].get("actorFrame") == snapshot["actorFrame"]
                        for e in crashes), "Ram Crash owner or completed frame differs")
            require(self.crash is None and len(crashes) == 1, "Ram published duplicate Crash")
            self.crash = deepcopy(crashes[0])
        for condition in self.conditions:
            if condition["triggered"] and self.trigger is None:
                require(condition["untilCrash"] and not condition["timed"]
                        and condition["active"] and condition["activeUntil"] == 0
                        and condition["targetKind"] == 1,
                        "Ram did not capture the player with Until Crash")
                self.trigger = deepcopy(condition)
        self._entry(snapshot, actor)
        for event in events:
            data = event["data"]
            if self.trigger is None:
                continue
            if data.get("event") == "MOTION_CANCELED" and self.crash is None:
                require(False, "Ram canceled its charge before Crash")
            elif data.get("event") == "MOTION_STARTED" and self.crash is None:
                origin = [actor["origin"][k] for k in ("x", "y")]
                target = [actor["target"][k] for k in ("x", "y")]
                delta = tuple(b-a for a, b in zip(origin, target))
                directions = ((0, -1), (0, 1), (-1, 0), (1, 0))
                require(actor["motionKind"] == "WALK" and delta in directions
                        and data.get("valueA") == 1 and data.get("valueB") == actor["motionDuration"],
                        "Ram has no genuine one-tile Walk start")
                direction = directions.index(delta)
                if self.first_walk is None:
                    require(0 <= frame - self.trigger["frame"] <= 1,
                            "Ram paused after activation")
                    if self.test is not None:
                        require((direction,origin,target) == ((0,[594,404],[594,403]) if self.kind == BEHIND else (3,[602,402],[603,402])),
                                "Ram did not enter the measured "+("North x594" if self.kind == BEHIND else "East row402")+" start")
                    self.first_walk = deepcopy(event)
                    self.heading = direction
                require(direction == self.heading, "Ram turned toward a moving target")
                self.walks.append({"startFrame": frame, "origin": origin, "target": target,
                                   "duration": actor["motionDuration"]})
        self._policy(snapshot, actor)
        self._cooldown(snapshot, actor)
        if self.first_walk is not None and self.crash is None:
            require(actor["matchedLayerMask"] & RAM_MASK,
                    "Ram lost its profile before Crash")
            dx = snapshot["player"]["x"] - actor["logical"]["x"]
            dy = snapshot["player"]["y"] - actor["logical"]["y"]
            off_axis = (dx != 0 if self.heading in (0, 1) else dy != 0)
            self.off_axis |= off_axis
            self.long_charge |= off_axis and frame - self.trigger["frame"] > 96
        if self.closed_condition is not None:
            require(not actor["matchedLayerMask"] & RAM_MASK,
                    "Ram reactivated inside its Crash cooldown")
            if frame - self.closed_condition["frame"] < COOLDOWN:
                self.cooldown_samples.append({"frame": frame, "mask": actor["matchedLayerMask"]})
        terminal = deepcopy(self.motion.current) if self.crash is not None \
            and self.crash["frame"] == frame else None
        failure_start = len(self.motion.failures)
        super()._sample(snapshot, actors)
        if terminal and self._crash_hides_terminal(snapshot, actor, terminal, events):
            added = self.motion.failures[failure_start:]
            if [item["reason"] for item in added] == [
                    "incomplete-travel", "terminal-render-target"]:
                # The real same-queue Crash shake hides this one endpoint.
                # Keep its raw record; it is NOT a credited complete Walk.
                self.crash_terminal_overlap = {"frame": frame,
                    "motion": deepcopy(self.motion.completed[-1]),
                    "withheldChecks": deepcopy(added)}
                del self.motion.failures[failure_start:]

    def _crash_hides_terminal(self, snapshot, actor, motion, events):
        frame = snapshot["frame"]
        samples = motion["samples"]
        if not samples or motion["kind"] != "WALK" \
                or motion["handle"] != actor["handle"] \
                or motion["fingerprint"] != actor["behaviorFingerprint"] \
                or actor["motionKind"] != "NONE" or actor["motionPhase"] != "IDLE" \
                or actor["reservationId"] != 0 or actor["motionElapsed"] != motion["duration"] \
                or actor["motionDuration"] != motion["duration"] \
                or actor["commitSequence"] != (motion["commitBefore"] + 1) & 0xffffffff \
                or [actor["logical"][k] for k in ("x", "y")] != motion["target"] \
                or [actor["origin"][k] for k in ("x", "y")] != motion["origin"] \
                or [actor["target"][k] for k in ("x", "y")] != motion["target"] \
                or [s["elapsed"] for s in samples] != list(range(samples[0]["elapsed"], motion["duration"])) \
                or samples[0]["elapsed"] not in (0, 1) \
                or [s["frame"] for s in samples] != list(range(samples[0]["frame"], frame)):
            return False
        engine = actor["engineObject"]
        target = [(v << 16) + 0x8000 for v in motion["target"]]
        # Wild's first 32-frame Crash shake: timer31, X-256/Z+256.
        if [engine["pos_x"], engine["pos_z"]] != [target[0]-256, target[1]+256] \
                or engine["unk88_y"] != 0:
            return False
        previous = 0
        for name in ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
            match = next((e for e in events if e["frame"] == frame
                and e["data"].get("event") == name
                and e["data"].get("actor") == {k:v for k,v in actor["handle"].items() if k != "value"}
                and e["data"].get("actorFrame") == snapshot["actorFrame"]
                and previous < e["data"]["sequence"] < self.crash["data"]["sequence"]
                and e["data"].get("valueB" if name == "CONTROL_RETURNED" else "valueA") == actor["commitSequence"]
                and e["data"].get("valueA" if name == "CONTROL_RETURNED" else "valueB") == (0 if name == "CONTROL_RETURNED" else 1)), None)
            if match is None:
                return False
            previous = match["data"]["sequence"]
        return True

    def _condition_state(self, snapshot, actor):
        data = snapshot.get("pokemonAppearance", {})
        identity = data.get("identity", {})
        require(data.get("schemaVersion") == 1 and data.get("available") is True
                and data.get("frame") == snapshot["frame"]
                and data.get("nativeCycle") == snapshot["nativeCycle"]
                and data.get("observationBoundary") == "main-task-queue-completion"
                and identity.get("romSha256") == snapshot.get("romSha256")
                and all(isinstance(identity.get(k), str) and len(identity[k]) == 64
                    and all(c in "0123456789abcdef" for c in identity[k]) for k in
                    ("romSha256", "capsuleElfSha256", "behaviorBlobSha256")),
                "Ram lacks an authenticated current condition-state reader")
        if self.condition_reader_identity is None:
            self.condition_reader_identity = deepcopy(identity)
        require(identity == self.condition_reader_identity,
                "Ram condition-state package identity changed")
        states = data.get("conditions", {})
        conditions = states.get(str(actor["handle"]["slot"]), states.get(actor["handle"]["slot"]))
        require(isinstance(conditions, dict) and conditions.get("available") is True
                and conditions.get("frame") == snapshot["actorFrame"],
                "Ram current prepared condition state is missing")
        owner = conditions.get("owner", {})
        require(owner.get("context") == snapshot["context"]
                and owner.get("objectPointer") == actor.get("engineIdentity", {}).get("pointer")
                and type(owner.get("actorPointer")) is int and owner["actorPointer"] != 0
                and type(owner.get("fieldPointer")) is int and owner["fieldPointer"] != 0
                and all(owner.get("actor", {}).get(k) == actor.get(k) for k in
                    ("handle", "subjectIdentity", "species", "role", "authorityGeneration",
                     "engineAnchorGeneration", "presentationGeneration")),
                "Ram prepared condition state has a stale full owner")
        entries = [s for s in conditions.get("states", [])
                   if s.get("application") == APPLICATION and s.get("conditionId") == CONDITION]
        require(len(entries) == 1, "Ram exact prepared condition entry is missing")
        state = entries[0]
        require(state.get("activationMode") == 2 and state.get("durationFrames") == 0
                and state.get("cooldownFrames") == COOLDOWN,
                "Ram native activation or cooldown metadata differs")
        return state, conditions, owner

    def _cooldown(self, snapshot, actor):
        if self.trigger is None:
            return
        state, conditions, owner = self._condition_state(snapshot, actor)
        if state["flags"] & 1:
            require(self.closed_condition is None, "Ram reactivated inside its Crash cooldown")
            return
        require(self.crash is not None and snapshot["frame"] >= self.crash["frame"],
                "Ram ended before an accepted Crash")
        require(not actor["matchedLayerMask"] & RAM_MASK,
                "Ram reactivated inside its Crash cooldown")
        if self.closed_condition is None:
            # The shared condition service consumes CRASH_PENDING, then stores
            # HAS_TRIGGERED | UNTIL_CRASH | REARM for the authored cooldown.
            require(state["flags"] == 26
                    and ((state["cooldownUntil"] - conditions["frame"]) & 0xffffffff) == COOLDOWN,
                    "Ram Crash did not start its authored cooldown")
            self.closed_condition = {**deepcopy(state), "frame": snapshot["frame"],
                "actorFrame": conditions["frame"], "source": "authenticated-prepared-state",
                "owner": deepcopy(owner)}

    def stage(self, name):
        return name == "charge-started" and self.first_walk is not None and not self.failures

    def _completed_charge_walks(self):
        if self.trigger is None or self.crash is None:
            return []
        result = []
        for motion in self.motion.completed:
            if motion.get("kind") != "WALK" or not self._complete_motion(motion) \
                    or motion["startFrame"] < self.trigger["frame"] \
                    or motion["finishFrame"] > self.crash["frame"]:
                continue
            previous = 0
            for name in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
                event = next((e for e in self._events(name, actor_name="onix")
                              if motion["startFrame"] <= e["frame"] <= motion["finishFrame"]
                              and e["data"]["sequence"] > previous), None)
                if event is None:
                    break
                previous = event["data"]["sequence"]
            else:
                result.append(deepcopy(motion))
        return result

    @property
    def ready(self):
        return bool(self.trigger and self.first_walk and self.off_axis and (self.long_charge or self.kind == BEHIND)
                    and (self.test is None or self.entry_witness is not None)
                    and self.crash and self.closed_condition and self.policy_calls
                    and len(self.cooldown_samples) >= POST_CRASH_FRAMES
                    and len(self.walks) >= 2
                    and self._completed_charge_walks())

    def finish(self):
        if self.kind != BEHIND and not self.long_charge and not self.failures:
            self.failures.append("Ram did not survive its old96-frame expiry before Crash")
        if self.closed_condition is None and not self.failures:
            self.failures.append("Ram has no authenticated inactive cooldown")
        if self.crash and not self._completed_charge_walks() and not self.failures:
            self.failures.append("Ram Walk has no paired commit/control")
        return super().finish()

    def result(self):
        return {**super().result(), "trigger": deepcopy(self.trigger),
                "firstWalk": deepcopy(self.first_walk), "heading": self.heading,
                "walks": deepcopy(self.walks), "offAxis": self.off_axis,
                "longCharge": self.long_charge, "crash": deepcopy(self.crash),
                "closedCondition": deepcopy(self.closed_condition),
                "policyCalls": deepcopy(self.policy_calls),
                "completedChargeWalks": self._completed_charge_walks(),
                "cooldownSamples": deepcopy(self.cooldown_samples),
                "crashTerminalOverlap": deepcopy(self.crash_terminal_overlap),
                "entryWitness": deepcopy(self.entry_witness),
                "passiveFollower": deepcopy(self.passive_follower)}
