"""One naturally selected Rattata Walk, measured through shared native data.

The four-frame expectation is the retained exact-Walk scenario contract, not
learned from the executor. Waiting does not supply motion or clear evidence.
"""
from copy import deepcopy

from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel

IDENTITY = ("handle", "species", "form", "level", "role", "subjectIdentity",
    "authorityGeneration", "engineAnchorGeneration", "presentationGeneration",
    "behaviorFingerprint", "matchedLayerMask")
LIFECYCLE = ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")


class WildWalkMeasurement:
    def __init__(self, max_frames):
        if type(max_frames) is not int or not 1 <= max_frames <= 1200:
            raise ValueError("invalid wild Walk frame bound")
        self.max_frames = max_frames
        self.initial = self.last = None
        self.closed = False
        self.frames = self.sequence = 0
        self.streams = {}
        self.failures, self.traces, self.clears, self.logical_samples = [], [], [], []
        self.idle_noop_clears = []
        self.recorder = MotionRecorder()
        self.motion = None
        self.motion_facing = None
        self.cleanup = None

    @staticmethod
    def _require(value, message):
        if not value:
            raise ValueError(message)

    def _actor(self, snapshot):
        bound = select_current_actor(snapshot, self.subject)
        actor = next(a for a in snapshot["actors"] if a["handle"] == bound["handle"])
        self._require(all(actor.get(k) == self.actor.get(k) for k in IDENTITY)
            and actor.get("inputOwnership") == 0
            and actor.get("sourceIdentity") == self.actor.get("sourceIdentity")
            and engine_binding_identity(actor.get("engineIdentity")) == engine_binding_identity(self.actor.get("engineIdentity"))
            and snapshot["context"] == self.initial["context"], "wild Walk identity or profile changed")
        return actor

    def _reader(self, receipt, closed):
        value = receipt.get("wildWalk", receipt)
        self._require(value.get("armed") is True and value.get("closed") is closed
            and value.get("failure") is None and value.get("acceptedProof") is False
            and value.get("guestMemoryWrites") == 0 and value.get("subject") == self.subject
            and value.get("startFrame") == self.initial["frame"], "wild Walk reader differs")
        return value

    def arm(self, subject, snapshot, receipt, trace_sequences=None):
        self._require(self.initial is None, "wild Walk reader already armed")
        self.subject = deepcopy(subject)
        bound = select_current_actor(snapshot, subject)
        actor = next(a for a in snapshot["actors"] if a["handle"] == bound["handle"])
        self._require(actor["species"] == 19 and actor["role"] == "WILD"
            and 0 <= actor["handle"]["slot"] < 6 and actor.get("inputOwnership") == 0
            and actor["motionPhase"] == "IDLE" and actor["motionKind"] == "NONE"
            and actor["reservationId"] == 0, "requires idle live wild Rattata")
        self.initial, self.last, self.actor = deepcopy(snapshot), deepcopy(snapshot), deepcopy(actor)
        self._require(self._reader(receipt, False).get("counts") == {"clear": 0}, "wild Walk reader contains prior clears")
        self.sequence = snapshot["nativeObservation"]["sequence"]
        self.streams = dict(trace_sequences or {})

    def _clear(self, event):
        from tools.overworld.devtools_wild_walk_observer import ENGINE
        data = event["data"]
        self._require(data.get("subject") == self.subject, "wild Walk clear subject differs")
        for endpoint in (data["before"], data["after"]):
            current = endpoint["current"]
            self._require(current.get("subject") == self.subject
                and all(current["publicSubject"].get(k) == self.actor.get(k) for k in IDENTITY)
                and current.get("sourceIdentity") == self.actor["sourceIdentity"]
                and current.get("engineIdentity") == {k:self.actor["engineIdentity"].get(k) for k in ENGINE}
                and current.get("objectPointer") == self.actor["engineIdentity"]["pointer"]
                and current.get("slot") == self.actor["handle"]["slot"], "wild Walk clear binding differs")
            world = current.get("worldContext", {})
            self._require(all(world.get(k) == self.initial["context"][k] for k in ("mapId","fieldEpoch","mapGeneration"))
                and current.get("statePointer") == world.get("statePointer")
                and all(type(current.get(k)) is int and 0x02000000 <= current[k] < 0x02400000 and current[k] % 4 == 0
                        for k in ("statePointer","runtimePointer","objectPointer")), "wild Walk clear world differs")
        self._require(data["before"]["current"] == data["after"]["current"], "wild Walk clear changed authority")
        from tools.overworld.devtools_wild_walk_observer import check_cleared_state
        before = data["before"]
        if type(before.get("active")) is int and before["active"] == 0 and type(before.get("mode")) is int and before["mode"] == 0:
            public = before["current"]["publicSubject"]
            self._require(self.recorder.current is None and self.motion is None and not self.clears
                and before == data["after"] and type(before.get("objectFlags")) is int
                and public.get("motionPhase") == "IDLE" and public.get("motionKind") == "NONE"
                and public.get("commitSequence") == self.actor["commitSequence"]
                and public.get("logical") == self.actor["logical"] and public.get("reservationId") == 0,
                "wild Walk idle no-op clear differs")
            check_cleared_state(before)
            self.idle_noop_clears.append(deepcopy(event))
            self._require(len(self.idle_noop_clears) < 64, "wild Walk idle no-op clear bound exceeded")
            return
        self._require(type(data["before"].get("active")) is int and data["before"]["active"] == 1
            and type(data["before"].get("mode")) is int and data["before"]["mode"] == 1,
            "wild Walk clear lacks active Walk entry")
        self._require(all(type(data["after"].get(k)) is int for k in ("active","mode","objectFlags")),
            "wild Walk clear state types differ")
        check_cleared_state(data["after"])
        self.clears.append(deepcopy(event))
        self._require(len(self.clears) == 1, "duplicate wild Walk clear")

    def observe(self, snapshot, events):
        if self.failures:
            return self.result()
        try:
            self._require(self.initial is not None and not self.closed, "wild Walk window is not open")
            actor = self._actor(snapshot)
            reader = self._reader(snapshot["wildWalk"], False)
            self._require(snapshot["observationBoundary"] == "main-task-queue-completion"
                and snapshot["frame"] == self.last["frame"] + 1
                and snapshot["nativeCycle"] >= self.last["nativeCycle"], "wild Walk completed clock gap")
            neutral = reader.get("latestCompletedInput", {})
            self._require(neutral.get("frame") == snapshot["frame"] and neutral.get("nativeCycle") == snapshot["nativeCycle"]
                and type(neutral.get("heldKeys")) is int and neutral["heldKeys"] == 0
                and type(neutral.get("newKeys")) is int and neutral["newKeys"] == 0,
                "wild Walk requires measured neutral input")
            native = snapshot["nativeObservation"]
            self._require(native.get("installedBeforeBoot") is True and native.get("coverageComplete") is True
                and native.get("error") is None and all(native.get(k) == 0 for k in ("eventsDropped", "profilesEvicted")),
                "wild Walk native coverage incomplete")
            self.frames += 1
            self._require(self.frames <= self.max_frames, "wild Walk frame bound exceeded")
            for event in events:
                data = event["data"]
                self._require(event.get("frame") == snapshot["frame"], "wild Walk event frame differs")
                if event["kind"] == "native-observation":
                    self._require(data.get("sequence") == self.sequence + 1, "wild Walk native receipt gap")
                    self.sequence += 1
                    self._require(self.last["nativeCycle"] <= data["entryNativeCycle"] <= data["returnNativeCycle"] <= snapshot["nativeCycle"],
                        "wild Walk native clock differs")
                    if data.get("observation") == "wild-walk-clear": self._clear(event)
                elif event["kind"] == "native":
                    stream, sequence = data["traceStream"], data["sequence"]
                    self._require(type(stream) is int and stream > 0 and type(sequence) is int
                        and sequence == self.streams.get(stream, 0) + 1, "wild Walk semantic sequence gap")
                    self.streams[stream] = sequence
                    if data.get("actorHandle") == self.actor["handle"]["value"]:
                        self._require(data.get("actor") == {k:v for k,v in self.actor["handle"].items() if k != "value"}, "wild Walk semantic identity differs")
                        self._require(data.get("event") not in ("MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND", "CONTROL_REBOUND"), "wild Walk canceled or rebound")
                        self.traces.append(deepcopy(event))
                        self._require(len(self.traces) <= 256, "wild Walk trace bound exceeded")
                elif event["kind"] == "trace-status" and data.get("code") == "ring-overwrite":
                    self._require(type(data.get("unreadEventsLost")) is int and data["unreadEventsLost"] == 0
                        and data.get("coverageComplete", True) is True and data.get("diagnosticOnly") is True
                        and type(data.get("count")) is int and data["count"] > 0
                        and type(data.get("traceStream")) is int and data["traceStream"] in self.streams,
                        "wild Walk trace lost unread events")
                else: raise ValueError("wild Walk trace status or unknown event")
            self._require(native["sequence"] == self.sequence, "wild Walk missing native receipt")
            self._require(reader.get("counts") == {"clear": len(self.clears) + len(self.idle_noop_clears)}, "wild Walk clear receipts lost")
            self._require(actor["motionKind"] in ("NONE", "WALK"), "wild Walk replaced by another motion")
            if actor["motionKind"] == "WALK":
                self._require(type(actor["motionDuration"]) is int and actor["motionDuration"] == 4,
                    "wild Walk requires exact four-frame travel")
                facing = actor["engineObject"].get("facing")
                self._require(type(facing) is int and 0 <= facing <= 3,
                    "wild Walk facing is invalid")
                if self.motion_facing is None:
                    self.motion_facing = facing
                self._require(facing == self.motion_facing,
                    "wild Walk facing changed before Motion returned control")
            starts = self._events("MOTION_STARTED")
            self._require(len(starts) <= 1, "extra wild Walk started")
            if starts:
                self.logical_samples.append(dict(frame=snapshot["frame"], logical=deepcopy(actor["logical"])))
            self.recorder.observe(snapshot["frame"], actor, actor["engineObject"])
            self._require(not self.recorder.failures, "wild Walk motion: " + str(self.recorder.failures))
            if self.recorder.completed:
                self._require(len(self.recorder.completed) == 1 and self.recorder.current is None, "extra wild Walk motion")
                self.motion = self.recorder.completed[0]
                self._check_motion(actor)
            self.last = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def _events(self, name):
        return [e for e in self.traces if e["data"].get("event") == name]

    def _check_motion(self, actor):
        m = self.motion
        self._require(m["kind"] == "WALK" and m["duration"] == 4 and complete_travel(m), "wild Walk requires exact four-frame travel")
        delta = [b-a for a,b in zip(m["origin"], m["target"])]
        self._require(max(map(abs, delta)) == 1, "wild Walk must travel one tile")
        positive = []
        for sample in m["samples"]:
            expected = [(m["origin"][i] << 16) + 0x8000 + delta[i]*0x10000*sample["elapsed"]//4 for i in (0,1)]
            self._require([sample["render"][0],sample["render"][2]] == expected and sample["jumpOffset"] == 0, "wild Walk nonlinear render")
            if sample["elapsed"] > 0: positive.append(sample["elapsed"])
        if not positive or positive[-1] != 4: positive.append(m["travelEnd"]["elapsed"])
        self._require(positive == [1,2,3,4], "wild Walk positive elapsed schedule differs")
        self._require(bool(self._events("MOTION_STARTED")), "missing native MOTION_STARTED")
        positions = [[s["logical"][k] for k in ("x","y")] for s in self.logical_samples]
        self._require(bool(positions), "wild Walk logical samples missing")
        self._require(positions[0] == m["origin"] and positions[-1] == m["target"]
            and all(p in (m["origin"],m["target"]) for p in positions)
            and sum(a != b for a,b in zip(positions,positions[1:])) == 1, "wild Walk logical transition differs")
        wanted = (("MOTION_STARTED",m["startFrame"],1,4), ("LOGICAL_COMMIT",m["commitFrame"],m["commitAfter"],1),
            ("MOTION_FINISHED",m["finishFrame"],m["commitAfter"],1), ("CONTROL_RETURNED",m["finishFrame"],0,m["commitAfter"]))
        sequence = []
        for name, frame, a, b in wanted:
            events = self._events(name)
            self._require(len(events) == 1 and events[0]["frame"] == frame and events[0]["data"].get("reason") == "OK"
                and (events[0]["data"].get("valueA"), events[0]["data"].get("valueB")) == (a,b), "missing native " + name)
            sequence.append(events[0]["data"]["sequence"])
        self._require(sequence == sorted(set(sequence)), "wild Walk lifecycle order differs")
        self._require(len(self.clears) == 1, "missing native wild Walk clear")
        clear = self.clears[0]["data"]
        public = clear["before"]["current"]["publicSubject"]
        self._require(public.get("commitSequence") == m["commitAfter"]
            and public.get("logical") == dict(zip(("x","y"),m["target"]))
            and public.get("motionPhase") in ("IDLE","SETTLING"), "wild Walk clear precedes committed target")
        self._require(self._events("LOGICAL_COMMIT")[0]["data"]["actorFrame"] <= clear["entryActorFrame"] <= clear["returnActorFrame"]
            <= self._events("MOTION_FINISHED")[0]["data"]["actorFrame"], "wild Walk clear outside terminal window")
        self._require(actor["motionPhase"] == "IDLE" and actor["motionKind"] == "NONE" and actor["reservationId"] == 0,
            "wild Walk terminal control is not idle")

    @property
    def ready(self):
        return self.motion is not None and not self.failures

    def close(self, receipt, snapshot):
        self._require(self.ready and snapshot == self.last, "wild Walk is incomplete")
        self._require(self._reader(receipt, True).get("counts") == {"clear": 1 + len(self.idle_noop_clears)}, "wild Walk close count differs")
        self.cleanup = deepcopy(receipt)
        self.closed = True
        return self.result()

    def finish(self):
        if not self.closed and not self.failures: self.failures.append("wild Walk reader was not closed")
        return self.result()

    def result(self):
        return dict(passed=self.closed and self.ready, acceptedProof=False, ready=self.ready, closed=self.closed,
            failures=list(self.failures), frames=self.frames, subject=deepcopy(getattr(self,"subject",None)),
            initial=deepcopy(self.initial), motion=deepcopy(self.motion), clearReceipts=deepcopy(self.clears),
            idleNoopClears=deepcopy(self.idle_noop_clears),
            terminal=deepcopy(self.last),
            motionFacing=self.motion_facing,
            traces=deepcopy(self.traces), logicalSamples=deepcopy(self.logical_samples), cleanup=deepcopy(self.cleanup),
            completeMotions=len(self.recorder.completed))
