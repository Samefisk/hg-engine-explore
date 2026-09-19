"""Bounded public-path proof for two mounted diagonal Walk motions.

The worker owns setup and normal input.  This meter only consumes the shared
completed-frame stream.  It uses the public actor path and stream state; it
does not install a private land-loader reader or mutate an authored profile.
"""
from copy import deepcopy

from tools.overworld.devtools_records import (
    HANDLE_FIELDS,
    engine_binding_identity,
    select_current_actor,
)
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel


KIND = "mounted-streaming-path-v1"
REQUIREMENT = "legacy.mounted-streaming-path"
LIFECYCLE = (
    "MOTION_STARTED",
    "PATH_ADVANCED",
    "LOGICAL_COMMIT",
    "MOTION_FINISHED",
    "CONTROL_RETURNED",
)
IDENTITY = (
    "handle",
    "species",
    "form",
    "level",
    "role",
    "subjectIdentity",
    "authorityGeneration",
    "engineAnchorGeneration",
    "presentationGeneration",
    "behaviorFingerprint",
    "matchedLayerMask",
)


def require(value, reason):
    if not value:
        raise ValueError(reason)


def full_event_handle(data):
    actor = data.get("actor")
    require(isinstance(actor, dict) and set(actor) == set(HANDLE_FIELDS) - {"value"},
            "mounted streaming event lacks a full actor handle")
    return {"value": data.get("actorHandle"), **actor}


def compact(values):
    result = []
    for value in values:
        if not result or result[-1] != value:
            result.append(value)
    return result


class MountedStreamingMeasurement:
    """Measure exactly two authored Ledyba diagonal Walks and stream cycles."""

    def __init__(self, test, *, max_frames):
        require(type(max_frames) is int and 1 <= max_frames <= 1200,
                "invalid mounted streaming frame bound")
        require(test.get("mode") == "prepared"
                and test.get("fixture") == {"rom": "test.nds", "save": "test.sav"}
                and test.get("subjects") == [{
                    "id": "ledyba", "species": 165,
                    "role": "MOUNTED", "acquire": "existing",
                }], "mounted streaming requires one prepared Ledyba mount")
        self.subject_id = "ledyba"
        self.max_frames = max_frames
        self.initial = self.last = self.terminal = None
        self.subject = self.actor = None
        self.frames = 0
        self.recorder = MotionRecorder()
        self.traces = []
        self.stream_samples = []
        self.failures = []
        self.closed = False

    def _fail(self, reason):
        if not self.failures:
            self.failures.append(str(reason))

    def _actor(self, snapshot):
        bound = select_current_actor(snapshot, self.subject)
        actor = next(item for item in snapshot["actors"]
                     if item.get("handle") == bound["handle"])
        require(all(actor.get(key) == self.actor.get(key) for key in IDENTITY)
                and actor.get("active") is True
                and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True
                and actor.get("inputOwnership") == 1
                and actor.get("sourceIdentity") == self.actor.get("sourceIdentity")
                and engine_binding_identity(actor.get("engineIdentity"))
                    == engine_binding_identity(self.actor.get("engineIdentity"))
                and snapshot.get("context") == self.initial.get("context"),
                "mounted streaming identity or context changed")
        context = snapshot["context"]
        active = [item for item in snapshot["actors"] if item.get("active") is True]
        require(all(item.get("handle", {}).get("fieldEpoch") == context["fieldEpoch"]
                    and item.get("handle", {}).get("mapGeneration") == context["mapGeneration"]
                    and item.get("presentationAttached") is True
                    for item in active),
                "mounted streaming active actor is stale or detached")
        reservations = [item["reservationId"] for item in active
                        if item.get("reservationId", 0) != 0]
        require(len(reservations) == len(set(reservations)),
                "mounted streaming has duplicate active reservations")
        return actor

    def arm(self, subject, snapshot):
        require(self.initial is None and self.subject is None,
                "mounted streaming meter was armed twice")
        selected = select_current_actor(snapshot, subject)
        actor = next(item for item in snapshot["actors"]
                     if item.get("handle") == selected["handle"])
        require(snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("context", {}).get("mapId") == 33
                and snapshot.get("player", {}).get("x") == 594
                and snapshot.get("player", {}).get("y") == 403
                and actor.get("active") is True
                and actor.get("species") == 165
                and actor.get("role") == "MOUNTED"
                and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True
                and actor.get("inputOwnership") == 1
                and actor.get("motionKind") == "NONE"
                and actor.get("motionPhase") == "IDLE"
                and actor.get("reservationId") == 0
                and actor.get("streamState") == 0
                and actor.get("logical") == {"x": 594, "y": 403},
                "mounted streaming requires idle Ledyba at the reviewed Route29 origin")
        self.subject = deepcopy(selected)
        self.actor = deepcopy(actor)
        self.initial = deepcopy(snapshot)
        self.last = deepcopy(snapshot)
        self.stream_samples.append(self._sample(snapshot, actor))
        return self.result()

    @staticmethod
    def _sample(snapshot, actor):
        return {
            "frame": snapshot["frame"],
            "streamState": actor["streamState"],
            "motionKind": actor["motionKind"],
            "motionPhase": actor["motionPhase"],
            "motionElapsed": actor["motionElapsed"],
            "reservationId": actor["reservationId"],
            "commitSequence": actor["commitSequence"],
            "logical": deepcopy(actor["logical"]),
            "origin": deepcopy(actor["origin"]),
            "target": deepcopy(actor["target"]),
            "player": [snapshot["player"]["x"], snapshot["player"]["y"]],
        }

    def _event(self, event):
        if event.get("kind") != "native":
            return
        data = event.get("data", {})
        if data.get("actorHandle") != self.subject["handle"]["value"]:
            return
        require(full_event_handle(data) == self.subject["handle"],
                "mounted streaming semantic identity changed")
        name = data.get("event")
        require(name not in ("MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND", "CONTROL_REBOUND"),
                "mounted streaming motion canceled or rebound")
        if name in LIFECYCLE:
            require(data.get("reason") == "OK",
                    "mounted streaming lifecycle has a non-OK result")
            self.traces.append(deepcopy(event))
            require(len(self.traces) <= 16,
                    "mounted streaming lifecycle bound exceeded")

    def observe(self, snapshot, events):
        if self.failures or self.closed:
            return self.result()
        try:
            require(self.initial is not None and self.subject is not None,
                    "mounted streaming observation preceded binding")
            require(isinstance(snapshot, dict) and isinstance(events, list)
                    and snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot.get("frame") == self.last["frame"] + 1
                    and snapshot.get("nativeCycle") >= self.last["nativeCycle"],
                    "mounted streaming completed frame is missing or reordered")
            actor = self._actor(snapshot)
            for event in events:
                self._event(event)
            require(actor.get("motionKind") in ("NONE", "WALK")
                    and actor.get("streamState") in (0, 1, 2),
                    "mounted streaming used another motion or stream state")
            if actor.get("motionKind") == "WALK":
                require(actor.get("motionDuration") == 8,
                        "mounted streaming requires authored eight-frame Walk")
            self.recorder.observe(snapshot["frame"], actor, actor["engineObject"])
            require(not self.recorder.failures,
                    "mounted streaming Walk: " + str(self.recorder.failures))
            require(len(self.recorder.completed) <= 2,
                    "mounted streaming observed more than two Walks")
            self.stream_samples.append(self._sample(snapshot, actor))
            require(len(self.stream_samples) <= self.max_frames + 1,
                    "mounted streaming sample bound exceeded")
            self.frames += 1
            require(self.frames <= self.max_frames,
                    "mounted streaming frame bound exceeded")
            self.last = deepcopy(snapshot)
            if self.ready:
                self.terminal = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self._fail(error)
        return self.result()

    def _validate_complete(self):
        require(len(self.recorder.completed) == 2 and self.recorder.current is None,
                "mounted streaming did not complete exactly two Walks")
        motions = self.recorder.completed
        require([motion["origin"] for motion in motions] == [[594, 403], [595, 402]]
                and [motion["target"] for motion in motions] == [[595, 402], [596, 401]]
                and all(motion["kind"] == "WALK" and motion["duration"] == 8
                        and complete_travel(motion)
                        and motion["commitAfter"] == (motion["commitBefore"] + 1) & 0xFFFFFFFF
                        for motion in motions),
                "mounted streaming Walk path differs")
        groups = {name: [event for event in self.traces
                         if event["data"].get("event") == name]
                  for name in LIFECYCLE}
        require(all(len(groups[name]) == 2 for name in LIFECYCLE),
                "mounted streaming lifecycle count differs")
        for index, motion in enumerate(motions):
            lifecycle = [groups[name][index] for name in LIFECYCLE]
            require([event["data"]["sequence"] for event in lifecycle]
                        == sorted({event["data"]["sequence"] for event in lifecycle})
                    and lifecycle[0]["frame"] == motion["startFrame"]
                    and lifecycle[1]["frame"] < lifecycle[2]["frame"]
                    and lifecycle[2]["frame"] == motion["commitFrame"]
                    and lifecycle[3]["frame"] == lifecycle[4]["frame"] == motion["finishFrame"]
                    and lifecycle[0]["data"].get("valueA") == 1
                    and lifecycle[0]["data"].get("valueB") == 8
                    and lifecycle[1]["data"].get("valueB") == 1
                    and lifecycle[2]["data"].get("valueA") == motion["commitAfter"],
                    "mounted streaming ordered path lifecycle differs")
            states = [sample["streamState"] for sample in self.stream_samples
                      if motion["startFrame"] <= sample["frame"] <= motion["finishFrame"]]
            require(compact(states) == [0, 1, 2, 0],
                    "mounted streaming public stream lifecycle differs")
        terminal = self._actor(self.terminal)
        require(terminal.get("motionKind") == "NONE"
                and terminal.get("motionPhase") == "IDLE"
                and terminal.get("streamState") == 0
                and terminal.get("reservationId") == 0
                and terminal.get("commitSequence") == 2
                and terminal.get("logical") == {"x": 596, "y": 401}
                and [self.terminal["player"]["x"], self.terminal["player"]["y"]]
                    == [596, 401],
                "mounted streaming did not return idle control at the final tile")

    @property
    def ready(self):
        if self.failures or len(self.recorder.completed) != 2 or self.recorder.current is not None:
            return False
        actor = next((item for item in self.last.get("actors", [])
                      if item.get("handle") == self.subject["handle"]), {})
        return (actor.get("motionKind") == "NONE"
                and actor.get("motionPhase") == "IDLE"
                and actor.get("streamState") == 0
                and actor.get("reservationId") == 0)

    def stage(self, name):
        if name != "two-complete":
            raise ValueError("unknown mounted streaming stage")
        return self.ready

    def finish(self):
        if not self.failures:
            try:
                require(self.ready, "mounted streaming did not complete two diagonal Walks")
                self.terminal = deepcopy(self.last)
                self._validate_complete()
            except (ValueError, KeyError, TypeError, StopIteration) as error:
                self._fail(error)
        self.closed = True
        return self.result()

    def result(self):
        return {
            "kind": KIND,
            "requirements": [REQUIREMENT],
            "passed": self.closed and self.ready and not self.failures,
            "ready": self.ready,
            "closed": self.closed,
            "acceptedProof": False,
            "failures": list(self.failures),
            "frames": self.frames,
            "subject": deepcopy(self.subject),
            "initial": deepcopy(self.initial),
            "terminal": deepcopy(self.terminal),
            "motions": deepcopy(self.recorder.completed),
            "traces": deepcopy(self.traces),
            "streamSamples": deepcopy(self.stream_samples),
            "completeMotions": len(self.recorder.completed),
        }
