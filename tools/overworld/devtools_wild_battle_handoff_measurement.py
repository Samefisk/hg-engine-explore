"""Bounded Wild battle handoff checks; never infer a native request from field loss."""
from copy import deepcopy

from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.normal_play_observer import live_identity
from tools.overworld.devtools_wild_teleport_measurement import IDENTITY, LIFECYCLE

KIND = "wild-battle-handoff-v1"
REQUIREMENT = "legacy.wild-battle-handoff"
OBSERVATION_GAP = "missing native wild-battle-request receipt"


def require(value, reason):
    if not value:
        raise ValueError(reason)


def identity(snapshot, subject):
    selected = select_current_actor(snapshot, subject)
    actor = next(a for a in snapshot["actors"] if a["handle"] == selected["handle"])
    require(live_identity(actor, actor.get("sourceIdentity", {}),
                          actor.get("engineIdentity", {}), species=19, role="WILD",
                          current_epoch=snapshot["context"]["fieldEpoch"])
            and actor.get("inputOwnership") == 0, "battle subject is not a current Wild Rattata")
    return actor


def adjacent_facing(player, actor):
    dx = actor["logical"]["x"] - player["x"]
    dy = actor["logical"]["y"] - player["y"]
    return (dx, dy) == {0: (0, -1), 1: (0, 1), 2: (-1, 0), 3: (1, 0)}.get(player.get("facing"))


class WildBattleHandoffMeasurement:
    def __init__(self, max_frames=600):
        require(type(max_frames) is int and 1 <= max_frames <= 1200, "invalid battle frame bound")
        self.max_frames = max_frames
        self.initial = self.last = self.subject = self.actor = None
        self.frames = self.sequence = 0
        self.streams = {}
        self.failures, self.journal, self.lifecycle = [], [], []
        self.approached = self.a_edge = self.closed = False
        self.request = None

    def arm(self, subject, snapshot, trace_sequences=None):
        require(self.initial is None, "battle meter already armed")
        actor = identity(snapshot, subject)
        require(actor.get("motionPhase") == "IDLE" and actor.get("motionKind") == "NONE",
                "battle meter needs idle starting actor")
        self.subject = deepcopy(select_current_actor(snapshot, subject))
        self.actor = deepcopy(actor)
        self.initial = self.last = deepcopy(snapshot)
        self.sequence = snapshot["nativeObservation"]["sequence"]
        self.streams = {int(stream): sequence for stream, sequence in (trace_sequences or {}).items()}
        self.initial_streams = dict(self.streams)

    def _same(self, snapshot):
        actor = identity(snapshot, self.subject)
        require(snapshot["context"] == self.initial["context"]
                and all(actor.get(k) == self.actor.get(k) for k in IDENTITY)
                and actor["sourceIdentity"] == self.actor["sourceIdentity"]
                and engine_binding_identity(actor["engineIdentity"])
                    == engine_binding_identity(self.actor["engineIdentity"]),
                "battle subject identity changed")
        return actor

    def _request(self, data, snapshot):
        require(self.request is None, "duplicate battle request")
        require(self.a_edge and len(self.lifecycle) == 4, "battle request precedes natural A input or motion")
        actor = data["currentActor"]
        boundary = dict(snapshot, actors=[actor], context=deepcopy(self.initial["context"]))
        self._same(boundary)
        require(data["subject"]["handle"] == self.subject["handle"]
                and data["subject"]["subjectIdentity"] == self.subject["subjectIdentity"]
                and data["subject"]["role"] == "WILD" and data["subject"]["species"] == 19,
                "battle request subject differs")
        pending = data["pending"]
        require(pending == {"slot": self.actor["handle"]["slot"], "species": 19,
                            "personality": self.actor["subjectIdentity"],
                            "encounterGeneration": self.actor["handle"]["encounterGeneration"]},
                "battle pending identity differs")
        require(data.get("returnValue") == 1 and data.get("setupMode") == "prepared",
                "battle native request did not succeed")
        request_input = data.get("input", {})
        request_held = request_input.get("heldKeys")
        require(type(request_held) is int
                and request_input.get("rawHeld") == request_held
                and request_input.get("simulatedKeys") == 0
                and request_input.get("physicalPressed") in (0, request_held),
                "battle request input ownership differs")
        require(adjacent_facing(data["player"], actor), "battle request player is not facing the subject")
        require(actor.get("motionKind") == "NONE" and actor.get("motionPhase") == "IDLE"
                and actor.get("reservationId") == 0, "battle request actor is not stable")
        self.request = deepcopy(data)

    def observe(self, snapshot, events):
        if self.initial is None or self.failures:
            return self.result()
        try:
            require(not self.closed, "battle meter already closed")
            require(self.frames < self.max_frames and len(events) <= 256, "battle observation bound exceeded")
            self.journal.append([deepcopy(snapshot), deepcopy(events)])
            require(snapshot["frame"] == self.last["frame"] + 1
                    and snapshot["nativeCycle"] >= self.last["nativeCycle"]
                    and snapshot.get("observationBoundary") == "main-task-queue-completion",
                    "battle completed frame gap")
            native = snapshot["nativeObservation"]
            require(native.get("installedBeforeBoot") is True and native.get("coverageComplete") is True
                    and native.get("error") is None and native.get("eventsDropped") == 0
                    and native.get("profilesEvicted") == 0, "battle native coverage incomplete")
            inputs = snapshot["selector"]
            held, edge = inputs.get("heldKeys"), inputs.get("newKeys")
            require(inputs.get("rawHeld") == held and inputs.get("rawNew") == edge
                    and inputs.get("physicalPressed") in (0, held)
                    and inputs.get("simulatedKeys") == 0,
                    "battle input has competing owner")
            require(type(held) is int and type(edge) is int and held & ~241 == 0 and edge & ~241 == 0,
                    "battle unexpected input")
            if self.request is None:
                request_data = next((e["data"] for e in events if e.get("data", {}).get("observation") == "wild-battle-request"), None)
                actor = self._same(dict(snapshot, actors=[request_data["currentActor"]], context=self.initial["context"])) if request_data else self._same(snapshot)
                if held & 240 and any(snapshot["player"][k] != self.initial["player"][k] for k in ("x", "y")):
                    self.approached = True
                if edge & 1:
                    require(not self.a_edge and self.approached and len(self.lifecycle) == 4
                            and adjacent_facing(snapshot["player"], actor), "battle A input is not a prepared approach")
                    self.a_edge = True
            for event in events:
                require(event.get("frame") == snapshot["frame"], "battle event frame differs")
                data = event.get("data", {})
                if event.get("kind") == "native-observation":
                    require(data.get("sequence") == self.sequence + 1, "battle native sequence gap")
                    self.sequence += 1
                    require(self.last["nativeCycle"] <= data.get("entryNativeCycle", -1)
                            <= data.get("returnNativeCycle", -1) <= snapshot["nativeCycle"], "battle native clock differs")
                    if data.get("observation") == "wild-battle-request":
                        self._request(data, snapshot)
                elif event.get("kind") == "native":
                    stream, seq = data.get("traceStream"), data.get("sequence")
                    require(type(seq) is int and seq == self.streams.get(stream, 0) + 1, "battle trace sequence gap")
                    self.streams[stream] = seq
                    if data.get("actorHandle") == self.subject["handle"]["value"]:
                        require(data.get("actor") == {k: v for k, v in self.subject["handle"].items() if k != "value"}, "battle semantic identity differs")
                        name = data.get("event")
                        require(data.get("reason") == "OK", "battle semantic reason differs")
                        require(name != "MOTION_CANCELED", "battle observed canceled motion")
                        if name in LIFECYCLE:
                            require(len(self.lifecycle) < 4 and name == LIFECYCLE[len(self.lifecycle)], "battle motion lifecycle differs")
                            if name == "MOTION_STARTED":
                                require(data.get("valueA") == 1, "battle requires natural Walk")
                            if name in ("LOGICAL_COMMIT", "MOTION_FINISHED"):
                                require(data.get("valueA") == ((self.actor["commitSequence"] + 1) & 0xFFFFFFFF)
                                        and data.get("valueB") == 1,
                                        "battle motion commit differs")
                            self.lifecycle.append(name)
                elif event.get("kind") == "trace-status":
                    require(data.get("code") == "ring-overwrite"
                            and data.get("unreadEventsLost") == 0
                            and data.get("coverageComplete", True) is True
                            and data.get("diagnosticOnly") is True
                            and data.get("traceStream") in self.streams,
                            "battle trace coverage lost")
                else:
                    raise ValueError("battle unknown observation")
            require(native["sequence"] == self.sequence, "battle native receipt missing")
            self.frames += 1
            self.last = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    @property
    def ready(self):
        return self.request is not None and not self.failures

    def stage(self, name):
        return {"motion-started": len(self.lifecycle) >= 1,
                "motion-complete": len(self.lifecycle) == 4,
                "request-complete": self.ready}.get(name, False)

    def finish(self):
        if not self.ready and not self.failures:
            self.failures.append(OBSERVATION_GAP)
        self.closed = True
        return self.result()

    def result(self):
        return deepcopy(dict(kind=KIND, requirement=REQUIREMENT, acceptedProof=False,
            passed=self.closed and self.ready, ready=self.ready, closed=self.closed,
            failures=self.failures, subject=self.subject, initial=self.initial,
            traceSequences=getattr(self, "initial_streams", {}), maxFrames=self.max_frames,
            frames=self.frames, request=self.request, lifecycle=self.lifecycle,
            approached=self.approached, aEdge=self.a_edge, journal=self.journal))


def replay(result):
    meter = WildBattleHandoffMeasurement(result["maxFrames"])
    meter.arm(result["subject"], result["initial"], result["traceSequences"])
    for snapshot, events in result["journal"]:
        meter.observe(snapshot, events)
    return meter.finish()
