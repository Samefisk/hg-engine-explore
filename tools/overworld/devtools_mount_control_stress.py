"""Pure D4 stress/control witness over the shared completed-frame stream.

No emulator, hooks, inputs, files, or acceptance live here. Floors are the
retained legacy contracts. MotionRecorder owns travel checks; only its current
motion and a bounded lifecycle queue remain in memory after each join.
"""
from copy import deepcopy
from hashlib import sha256
import json

from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.devtools_movement_predicates import player_settled_at
from tools.overworld.normal_play_observer import MotionRecorder
from tools.overworld.spawn_identity import live_spawn_flags


KIND = "mounted-control-stress-v1"
ALIASES = {"walk":"legacy.cyndaquil-control-stress", "hop":"legacy.mankey-control-stress"}
CONTRACTS = {
    "legacy.cyndaquil-control-stress": dict(species=155, motion="WALK", kind=1, motions=2000, turns=250, frames=5000),
    "legacy.mankey-control-stress": dict(species=56, motion="HOP", kind=2, motions=200, turns=0, frames=5001),
}
MOTION_KIND_IDS = {"WALK": 1, "HOP": 2, "TELEPORT": 3, "SKID": 4}
LIFECYCLE = ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")
STABLE = ("handle", "subjectIdentity", "species", "form", "level", "behaviorFingerprint", "matchedLayerMask")
GENERATIONS = ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def check_snapshot_pair(snapshot, actor):
    """Check the vectors in the normal shared snapshot, without inventing Z offsets.

The standard snapshot exposes base XYZ, face XYZ and effect XY. The optional
full native pair reader can prove additional vectors; this witness cannot.
"""
    player, mount = snapshot["player"], actor["engineObject"]
    for key in ("pos_x", "pos_y", "pos_z", "face_x", "face_y", "face_z", "unk88_x", "unk88_y", "unk94_x", "unk94_y", "facing"):
        require(type(player.get(key)) is int and type(mount.get(key)) is int, "missing native pair vector " + key)
    require(all(player["pos_" + axis] == mount["pos_" + axis] for axis in "xyz"), "player/presentation base positions differ")
    offsets = {0: (0, 32768), 1: (0, -32768), 2: (32768, 0), 3: (-32768, 0)}
    require(player["facing"] in offsets and player["facing"] == mount["facing"], "player/presentation facing differs")
    x, z = offsets[player["facing"]]
    require(sum(player[p + "x"] - mount[p + "x"] for p in ("face_", "unk88_", "unk94_")) == x
            and player["face_z"] - mount["face_z"] == z
            and sum(player[p + "y"] - mount[p + "y"] for p in ("face_", "unk88_", "unk94_")) == 32768,
            "player/presentation rider offsets differ")


class MountControlStressMeasurement:
    def __init__(self, contract, max_frames=40000):
        contract = ALIASES.get(contract, contract)
        require(contract in CONTRACTS, "unknown mounted stress contract")
        require(type(max_frames) is int and CONTRACTS[contract]["frames"] <= max_frames <= 40000,
                "invalid stress frame bound")
        self.contract, self.rules, self.max_frames = contract, dict(CONTRACTS[contract]), max_frames
        self.allowed_motion_kinds = (("WALK", "SKID")
                                     if self.rules["motion"] == "WALK"
                                     else (self.rules["motion"],))
        self.initial = self.last = self.actor = self.subject = None
        self.frames = self.route_frames = self.motions = self.turns = self.recovery = 0
        self.phase = "unarmed"
        self.closed = False
        self.failures = []
        self.recorder = MotionRecorder()
        self.traces, self.streams = [], {}
        self.sequence = 0
        self.direction = None
        self.milestones = {}
        self.milestone_evidence = {}
        self.digest = sha256()
        self.motion_summaries = []
        self.select_frame = None
        self.unmounted_origin = None
        self.unmounted_render_changed = False

    def _actor(self, snapshot):
        actors = [a for a in snapshot["actors"] if a.get("handle") == self.subject["handle"]]
        require(len(actors) == 1, "missing or duplicate mounted subject")
        actor = actors[0]
        require(all(actor.get(k) == self.initial["actor"].get(k) for k in STABLE), "stress subject/profile changed")
        require(actor.get("role") in ("MOUNTED", "FOLLOWER"), "wrong stress role")
        require(actor["handle"].get("slot") == 7, "stress subject is not the follower slot")
        selected = dict(self.subject, role=actor["role"])
        for key in GENERATIONS:
            selected.pop(key, None)
        select_current_actor(snapshot, selected)
        source, engine = actor["sourceIdentity"], actor["engineIdentity"]
        initial_engine = self.initial["actor"]["engineIdentity"]
        # The player anchor is only present in Mounted engine identity.
        clean = lambda value: {k: v for k, v in engine_binding_identity(value).items()
                               if k not in ("anchorPointer", "anchorInCurrentManager")}
        require(clean(engine) == clean(initial_engine)
                and source == self.initial["actor"]["sourceIdentity"], "stress engine/source identity changed")
        require(source.get("species") == actor["species"] and source.get("personality") == actor["subjectIdentity"]
                and live_spawn_flags(source.get("active"))
                and source.get("object") == engine.get("pointer")
                and actor["handle"]["encounterGeneration"] == source.get("encounter_generation") == engine.get("encounter_generation")
                and engine.get("in_manager") is True and engine.get("active") is True,
                "stress native identity differs")
        if actor["role"] == "MOUNTED":
            require(engine.get("anchorPointer") == initial_engine.get("anchorPointer")
                    and engine.get("anchorInCurrentManager") is True, "mounted engine anchor changed")
        require(source.get("object_id") == engine.get("object_id") == 231
                and engine.get("spawn_object_id") == 231
                and source.get("map_id") == engine.get("object_map_id") == engine.get("spawn_map_id") == engine.get("current_map_id") == snapshot["context"]["mapId"]
                and source.get("form") == actor.get("form") and source.get("level") == actor.get("level")
                and engine.get("script_id") == 2074 and engine.get("object_manager") == engine.get("current_manager")
                and engine.get("current_manager", 0) > 0 and engine.get("pointer", 0) > 0,
                "stress object ownership differs")
        return actor

    def arm(self, subject, snapshot, trace_sequences=None):
        require(self.phase == "unarmed", "stress already armed")
        selected = select_current_actor(snapshot, subject)
        actor = next(a for a in snapshot["actors"] if a["handle"] == selected["handle"])
        require(actor.get("species") == self.rules["species"] and actor.get("role") == "MOUNTED"
                and actor.get("inputOwnership") == 1 and actor.get("motionPhase") == "IDLE"
                and actor.get("reservationId") == 0, "requires exact idle mounted stress subject")
        self.subject = deepcopy(subject)
        self.initial = dict(frame=snapshot["frame"], context=deepcopy(snapshot["context"]), actor=deepcopy(actor))
        self.actor = deepcopy(self._actor(snapshot))
        self.last = dict(frame=snapshot["frame"], nativeCycle=snapshot["nativeCycle"], player=deepcopy(snapshot["player"]))
        self.sequence = snapshot["nativeObservation"]["sequence"]
        self.streams = dict(trace_sequences or {})
        self.phase = "stress"

    def _events(self, snapshot, events, actor):
        own = []
        for event in events:
            require(event.get("frame") == snapshot["frame"], "stress event completion frame differs")
            data = event.get("data", {})
            if event.get("kind") == "native-observation":
                require(data.get("sequence") == self.sequence + 1, "native receipt sequence gap")
                self.sequence += 1
            elif event.get("kind") == "native":
                stream, sequence = data["traceStream"], data["sequence"]
                require(stream not in self.streams or sequence == self.streams[stream] + 1, "semantic sequence gap")
                self.streams[stream] = sequence
                if data.get("actorHandle") != actor["handle"]["value"]:
                    continue
                require(data.get("actor") == {k: v for k, v in actor["handle"].items() if k != "value"}, "semantic generation differs")
                own.append(event)
                if data.get("event") in LIFECYCLE and not (data.get("event") == "CONTROL_RETURNED" and self.phase == "detach" and data.get("valueA") == 0):
                    self.traces.append(deepcopy(event))
                    require(len(self.traces) <= 64, "unjoined lifecycle bound exceeded")
                if data.get("event") == "MOTION_CANCELED":
                    require(self.phase == "detach" and self.select_frame is not None,
                            "unexpected motion cancellation")
                    require(self.recorder.current is not None and actor["commitSequence"] == self.recorder.current["commitBefore"],
                            "canceled motion committed or has no start")
                    self.recorder = MotionRecorder()
                    self.traces.clear()
                    self.milestones["cancel"] = snapshot["frame"]
                if data.get("event") == "CONTROL_RETURNED" and self.phase == "detach" and data.get("valueA") == 0:
                    require(self.select_frame is not None and actor["reservationId"] == 0,
                            "detach return retained reservation or lacks input")
                    self.milestones["control-released"] = snapshot["frame"]
                require(data.get("event") not in ("CONTEXT_CHANGED", "ACTOR_DETACHED"), "stress actor/context was discarded")
            elif event.get("kind") == "trace-status":
                require(data.get("code") == "ring-overwrite" and data.get("unreadEventsLost") == 0
                        and data.get("coverageComplete", True) is True and data.get("diagnosticOnly") is True
                        and data.get("traceStream") in self.streams, "stress trace lost events")
        require(snapshot["nativeObservation"]["sequence"] == self.sequence, "missing native receipt")
        return own

    def _join(self, motion):
        require(motion["kind"] in self.allowed_motion_kinds, "wrong completed stress motion kind")
        motion_kind_id = MOTION_KIND_IDS[motion["kind"]]
        wanted = (("MOTION_STARTED", motion["startFrame"], motion_kind_id, motion["duration"]),
                  ("LOGICAL_COMMIT", motion["commitFrame"], motion["commitAfter"], motion_kind_id),
                  ("MOTION_FINISHED", motion["finishFrame"], motion["commitAfter"], motion_kind_id),
                  ("CONTROL_RETURNED", motion["finishFrame"], 1, motion["commitAfter"]))
        matched = []
        for name, frame, a, b in wanted:
            candidates = [e for e in self.traces if e["frame"] == frame and e["data"]["event"] == name]
            require(len(candidates) == 1, "missing/duplicate native " + name)
            event = candidates[0]
            require(event["data"].get("reason") == "OK" and (event["data"].get("valueA"), event["data"].get("valueB")) == (a, b),
                    "wrong native " + name)
            matched.append(event)
        sequences = [e["data"]["sequence"] for e in matched]
        require(sequences == sorted(set(sequences)), "motion lifecycle order differs")
        for event in matched:
            self.traces.remove(event)
        direction = tuple((motion["target"][i] > motion["origin"][i]) - (motion["target"][i] < motion["origin"][i]) for i in (0, 1))
        require(direction != (0, 0), "stationary motion cannot supply travel")
        if self.phase == "stress":
            if motion["kind"] == self.rules["motion"]:
                self.motions += 1
                self.turns += int(self.direction is not None and self.direction != direction)
                self.direction = direction
        elif self.phase == "recovery":
            require(motion["kind"] == self.rules["motion"], "wrong recovery motion kind")
            self.recovery += 1
        self.digest.update(json.dumps(dict(motion=motion, lifecycle=matched), sort_keys=True).encode())
        self.motion_summaries.append(dict(kind=motion["kind"], startFrame=motion["startFrame"],
            commitFrame=motion["commitFrame"], finishFrame=motion["finishFrame"],
            commitBefore=motion["commitBefore"],commitAfter=motion["commitAfter"],
            duration=motion["duration"],origin=motion["origin"],target=motion["target"],
            phase=self.phase,lifecycle=[e["data"] for e in matched],motion=motion,
            sha256=sha256(json.dumps(motion,sort_keys=True).encode()).hexdigest()))
        require(len(self.motion_summaries) <= self.max_frames, "motion summary bound exceeded")

    @property
    def main_complete(self):
        return not self.failures and self.motions >= self.rules["motions"] and self.turns >= self.rules["turns"] and self.route_frames >= self.rules["frames"]

    def begin_detach(self, snapshot):
        require(self.phase == "stress" and self.main_complete and snapshot["frame"] == self.last["frame"], "stress floors not complete at detach boundary")
        self.phase = "detach"
        self.select_frame = None

    def _point(self, name, snapshot, actor):
        self.milestone_evidence[name] = dict(frame=snapshot["frame"],nativeCycle=snapshot["nativeCycle"],
            observationBoundary=snapshot["observationBoundary"],fieldAvailable=snapshot["fieldAvailable"],
            context=deepcopy(snapshot["context"]),player=deepcopy(snapshot["player"]),
            fieldControl=deepcopy(snapshot["fieldControl"]),actor=deepcopy(actor))

    def observe(self, snapshot, events):
        if self.phase == "unarmed":
            return self.result(False)
        if self.failures:
            return self.result(False)
        try:
            require(self.phase != "unarmed" and not self.closed, "stress observation is not open")
            require(snapshot.get("fieldAvailable") is True and snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot["context"] == self.initial["context"], "stress field/context differs")
            require(snapshot["frame"] == self.last["frame"] + 1 and snapshot["nativeCycle"] > self.last["nativeCycle"], "stress completed clock gap")
            self.frames += 1
            require(self.frames <= self.max_frames, "stress frame bound exceeded")
            native = snapshot["nativeObservation"]
            require(native.get("installedBeforeBoot") is True and native.get("coverageComplete") is True and native.get("error") is None
                    and all(native.get(k) == 0 for k in ("eventsDropped", "profilesEvicted")), "stress native coverage incomplete")
            actor = self._actor(snapshot)
            selector = snapshot["selector"]
            if selector.get("rawNew", 0) & selector.get("newKeys", 0) & 4:
                if self.phase == "stress" and self.main_complete:
                    self.phase = "detach"
                self.select_frame = snapshot["frame"]
            own = self._events(snapshot, events, actor)
            role_changed = actor["role"] != self.actor["role"]
            if role_changed:
                require(self.select_frame is not None and snapshot["frame"] - self.select_frame <= 120, "role change lacks Select edge")
                pair = (3, 2) if actor["role"] == "FOLLOWER" else (2, 3)
                require(sum(e["data"].get("event") == "ACTOR_REBOUND" and (e["data"].get("valueA"),e["data"].get("valueB")) == pair for e in own) == 1,
                        "role change lacks exact rebound receipt")
                require(actor["authorityGeneration"] > self.actor["authorityGeneration"]
                        and actor["engineAnchorGeneration"] > self.actor["engineAnchorGeneration"], "role ownership generation did not advance")
                if actor["role"] == "FOLLOWER":
                    require(self.phase == "detach" and actor["inputOwnership"] == 0 and actor["reservationId"] == 0 and self.recorder.current is None,
                            "detach retained motion/control")
                    self.phase = "unmounted"
                    self.unmounted_origin = deepcopy(snapshot["player"])
                    self.milestones["detach"] = snapshot["frame"]
                    self._point("detach",snapshot,actor)
                else:
                    require(self.phase == "unmounted" and "unmounted-step" in self.milestones and actor["inputOwnership"] == 1,
                            "remount preceded a completed normal step")
                    require(any(e["data"].get("event") == "CONTROL_REBOUND" and (e["data"].get("valueA"),e["data"].get("valueB")) == (0,1) for e in own),
                            "remount lacks control receipt")
                    self.phase = "recovery"
                    self.milestones["remount"] = snapshot["frame"]
                    self._point("remount",snapshot,actor)
                    self.select_frame = None
            else:
                require(all(actor[k] == self.actor[k] for k in GENERATIONS), "ownership changed without role rebound")
            if self.phase in ("stress", "recovery") and self.recorder.current is None:
                require(actor["commitSequence"] == self.actor["commitSequence"], "commit has no observed motion start")
            if self.phase == "unmounted":
                require(actor["role"] == "FOLLOWER" and actor["inputOwnership"] == 0, "unmounted control differs")
                p = snapshot["player"]
                if (p["pos_x"],p["pos_z"]) != (self.unmounted_origin["pos_x"],self.unmounted_origin["pos_z"]):
                    require(selector.get("rawHeld",0) & 0xF0 or self.unmounted_render_changed,
                            "normal player motion lacks directional input")
                    self.unmounted_render_changed |= (p["pos_x"],p["pos_z"]) != ((p["x"]<<16)+32768,(p["y"]<<16)+32768)
                    if self.unmounted_render_changed and "unmounted-progress" not in self.milestone_evidence:
                        self._point("unmounted-progress",snapshot,actor)
                if self.unmounted_render_changed and (p["x"],p["y"]) != (self.unmounted_origin["x"],self.unmounted_origin["y"]) \
                        and player_settled_at(snapshot, snapshot["context"]["mapId"],p["x"],p["y"]):
                    self.milestones["unmounted-step"] = snapshot["frame"]
                    self._point("unmounted-step",snapshot,actor)
            elif actor["inputOwnership"] == 1:
                require(actor["role"] == "MOUNTED", "wrong controlled role")
                # Select removes the rider presentation before the public actor
                # view reports its FOLLOWER rebound on the next field frame.
                # The exact input frame is therefore already unmounted visually.
                if self.phase != "detach" or snapshot["frame"] != self.select_frame:
                    check_snapshot_pair(snapshot, actor)
                if actor["motionPhase"] in ("PLANNED","MOVING","COMMIT_PENDING","SETTLING"):
                    allowed = (self.allowed_motion_kinds if self.phase == "stress"
                               else (self.rules["motion"],))
                    require(actor["motionKind"] in allowed
                            and actor.get("motionKindId") == MOTION_KIND_IDS[actor["motionKind"]],
                            "wrong active stress motion kind")
                recorder_actor = actor
                if actor["motionKind"] == "SKID":
                    recorder_actor = deepcopy(actor)
                    recorder_actor["motionKind"] = "WALK"
                    recorder_actor["motionKindId"] = MOTION_KIND_IDS["WALK"]
                self.recorder.observe(snapshot["frame"],recorder_actor,snapshot["player"])
                if actor["motionKind"] == "SKID" and self.recorder.current is not None:
                    self.recorder.current["sourceKind"] = "SKID"
                require(not self.recorder.failures, "stress motion: " + str(self.recorder.failures))
                while self.recorder.completed:
                    completed = self.recorder.completed.pop(0)
                    if completed.pop("sourceKind", None) == "SKID":
                        completed["kind"] = "SKID"
                        completed["key"][1] = "SKID"
                    self._join(completed)
                if self.phase == "stress" and (self.recorder.current is not None or actor["motionPhase"] == "IDLE" and any(e["data"].get("event") == "MOTION_FINISHED" for e in own)):
                    self.route_frames += 1
                if self.phase == "recovery" and self.recovery and actor["motionPhase"] == "IDLE" and actor["reservationId"] == 0:
                    self.milestones["recovery"] = snapshot["frame"]
                    self._point("recovery",snapshot,actor)
            else:
                require(self.phase == "detach" and actor["reservationId"] == 0 and self.select_frame is not None, "mounted control lost")
            self.actor = deepcopy(actor)
            self.last = dict(frame=snapshot["frame"], nativeCycle=snapshot["nativeCycle"], player=deepcopy(snapshot["player"]))
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result(False)

    def stage(self, name):
        return {"main-complete": self.main_complete, "detached": "detach" in self.milestones,
                "unmounted-step": "unmounted-step" in self.milestones, "remounted": "remount" in self.milestones,
                "recovery-complete": "recovery" in self.milestones and not self.failures}.get(name,False)

    def finish(self):
        if not self.failures:
            if not self.main_complete or not self.stage("recovery-complete") or self.recorder.current is not None or self.traces:
                self.failures.append("stress floors, lifecycle or detach/recovery milestones incomplete")
        self.closed = True
        return self.result()

    def result(self, full_report=True):
        proof = {}
        passed = self.closed and not self.failures and self.main_complete and self.stage("recovery-complete")
        if passed:
            actor = self.initial["actor"]
            if self.rules["kind"] == 1:
                rows = [("natural-input","held-input-commit-count",self.motions,self.rules["motions"],"gte"),
                        ("natural-input","held-input-turn-count",self.turns,self.rules["turns"],"gte"),
                        ("natural-input","held-input-route-frame-count",self.route_frames,self.rules["frames"],"gte"),
                        ("live-actor-identity","cyndaquil-species",actor["species"],155,"eq"),
                        ("live-actor-identity","mounted-object-pointer",actor["engineIdentity"]["pointer"],actor["engineIdentity"]["pointer"],"eq"),
                        ("live-actor-identity","actor-handle",actor["handle"],actor["handle"],"eq"),
                        ("live-actor-identity","mounted-object-identity-flags",[1,1,1,1,7,155,1],[1,1,1,1,7,155,1],"eq"),
                        ("live-actor-identity","encounter-generation-match",[actor["handle"]["encounterGeneration"],actor["sourceIdentity"]["encounter_generation"],actor["engineIdentity"]["encounter_generation"]],None,"eq"),
                        ("rendered-motion","valid-mounted-walk-callback-count",[self.motions,self.motions],None,"eq"),
                        ("control-release","dismount-remount-control-milestones",["IDLE",0,1,1,1,1,1],["IDLE",0,1,1,1,1,1],"eq")]
            else:
                rows = [("natural-input","completed-natural-hop-count",self.motions,self.rules["motions"],"gte"),
                        ("natural-input","mankey-stress-active-frame-count",self.route_frames,self.rules["frames"],"gte"),
                        ("live-actor-identity","mankey-stress-identity",[1,"MOUNTED",56,1],[1,"MOUNTED",56,1],"eq"),
                        ("live-actor-identity","actor-owned-hop-motion-count",self.motions,1,"gte"),
                        ("rendered-motion","valid-mounted-hop-motion-count",[self.motions,self.motions],None,"eq"),
                        ("control-release","dismount-and-remount-milestones",[1,1,1,1,"IDLE",0],[1,1,1,1,"IDLE",0],"eq")]
            for claim,name,actual,expected,operator in rows:
                proof.setdefault(claim,[]).append(dict(name=name,actual=actual,expected=actual if expected is None else expected,operator=operator))
        result = dict(passed=passed,ready=passed,acceptedProof=False,kind=KIND,contract=self.contract,subject=deepcopy(self.subject),
                    frames=self.frames,routeFrames=self.route_frames,motions=self.motions,turns=self.turns,recoveryMotions=self.recovery,
                    phase=self.phase,mainComplete=self.main_complete,closed=self.closed,failures=list(self.failures),
                    milestones=dict(self.milestones),motionEvidenceSha256=self.digest.hexdigest(),proofEvidence=proof)
        if full_report:
            result.update(initial=deepcopy(self.initial),motionSummaries=deepcopy(self.motion_summaries),
                          milestoneEvidence=deepcopy(self.milestone_evidence))
        return result
