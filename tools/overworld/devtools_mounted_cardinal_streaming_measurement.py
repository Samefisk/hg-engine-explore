"""Public-path proof for one held Cyndaquil route across a stream boundary.

The worker owns prepared setup and normal input.  This meter consumes only the
shared completed-frame stream.  It proves that the stock cardinal path remains
owned by the field streamer; it does not install a private land-loader reader.
"""
from copy import deepcopy

from tools.overworld.devtools_records import (
    HANDLE_FIELDS,
    engine_binding_identity,
    select_current_actor,
)
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel


KIND = "mounted-cardinal-streaming-v1"
REQUIREMENT = "legacy.cyndaquil-streaming-stress"
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
ORIGIN = (584, 403)
TARGET = (604, 403)
ROUTE_MOVES = 20
MIN_SKID_MOVES = 1
MAX_SKID_MOVES = 2


def require(value, reason):
    if not value:
        raise ValueError(reason)


def full_event_handle(data):
    actor = data.get("actor")
    require(isinstance(actor, dict) and set(actor) == set(HANDLE_FIELDS) - {"value"},
            "cardinal streaming event lacks a full actor handle")
    return {"value": data.get("actorHandle"), **actor}


class MountedCardinalStreamingMeasurement:
    """Measure held east Walks, the normal stop skid, and one recovery Walk."""

    def __init__(self, test, *, max_frames):
        require(type(max_frames) is int and 1 <= max_frames <= 1200,
                "invalid cardinal streaming frame bound")
        require(test.get("mode") == "prepared"
                and test.get("fixture") == {"rom": "test.nds", "save": "test.sav"}
                and test.get("subjects") == [{
                    "id": "cyndaquil", "species": 155,
                    "role": "MOUNTED", "acquire": "existing",
                }], "cardinal streaming requires one prepared Cyndaquil mount")
        self.subject_id = "cyndaquil"
        self.max_frames = max_frames
        self.initial = self.last = self.target = self.route_terminal = self.terminal = None
        self.route_motion_count = None
        self.subject = self.actor = None
        self.frames = 0
        self.recorder = MotionRecorder()
        self.traces = []
        self.stream_samples = []
        self.failures = []
        self.closed = False

    def _observe_motion(self, snapshot, actor):
        """Let the shared recorder retain SKID without changing its broad contract."""
        actual_kind = actor["motionKind"]
        adapted = actor
        if actual_kind == "SKID":
            adapted = deepcopy(actor)
            adapted["motionKind"] = "WALK"
        completed = len(self.recorder.completed)
        self.recorder.observe(snapshot["frame"], adapted, actor["engineObject"])
        if self.recorder.current is not None \
                and "actualKind" not in self.recorder.current:
            self.recorder.current["actualKind"] = actual_kind
        for motion in self.recorder.completed[completed:]:
            motion["kind"] = motion.pop("actualKind", motion["kind"])

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
                "cardinal streaming identity or context changed")
        context = snapshot["context"]
        active = [item for item in snapshot["actors"] if item.get("active") is True]
        require(all(item.get("handle", {}).get("fieldEpoch") == context["fieldEpoch"]
                    and item.get("handle", {}).get("mapGeneration") == context["mapGeneration"]
                    and item.get("presentationAttached") is True
                    for item in active),
                "cardinal streaming active actor is stale or detached")
        reservations = [item["reservationId"] for item in active
                        if item.get("reservationId", 0) != 0]
        require(len(reservations) == len(set(reservations)),
                "cardinal streaming has duplicate active reservations")
        return actor

    def arm(self, subject, snapshot):
        require(self.initial is None and self.subject is None,
                "cardinal streaming meter was armed twice")
        selected = select_current_actor(snapshot, subject)
        actor = next(item for item in snapshot["actors"]
                     if item.get("handle") == selected["handle"])
        require(snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("context", {}).get("mapId") == 33
                and snapshot.get("player", {}).get("x") == ORIGIN[0]
                and snapshot.get("player", {}).get("y") == ORIGIN[1]
                and actor.get("active") is True
                and actor.get("species") == 155
                and actor.get("role") == "MOUNTED"
                and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True
                and actor.get("inputOwnership") == 1
                and actor.get("motionKind") == "NONE"
                and actor.get("motionPhase") == "IDLE"
                and actor.get("reservationId") == 0
                and actor.get("streamState") == 0
                and actor.get("logical") == {"x": ORIGIN[0], "y": ORIGIN[1]},
                "cardinal streaming requires idle Cyndaquil at the reviewed Route29 origin")
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
                "cardinal streaming semantic identity changed")
        name = data.get("event")
        require(name not in (
            "MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND", "CONTROL_REBOUND",
        ), "cardinal streaming motion canceled or rebound")
        if name in LIFECYCLE:
            require(data.get("reason") == "OK",
                    "cardinal streaming lifecycle has a non-OK result")
            self.traces.append(deepcopy(event))
            require(len(self.traces)
                    <= (ROUTE_MOVES + MAX_SKID_MOVES + 2) * len(LIFECYCLE),
                    "cardinal streaming lifecycle bound exceeded")

    def observe(self, snapshot, events):
        if self.failures or self.closed:
            return self.result()
        try:
            require(self.initial is not None and self.subject is not None,
                    "cardinal streaming observation preceded binding")
            require(isinstance(snapshot, dict) and isinstance(events, list)
                    and snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot.get("frame") == self.last["frame"] + 1
                    and snapshot.get("nativeCycle") >= self.last["nativeCycle"],
                    "cardinal streaming completed frame is missing or reordered")
            actor = self._actor(snapshot)
            for event in events:
                self._event(event)
            require(actor.get("motionKind") in ("NONE", "WALK", "SKID")
                    and actor.get("streamState") in (0, 1, 2)
                    and actor.get("logical", {}).get("y") == ORIGIN[1]
                    and snapshot.get("player", {}).get("y") == ORIGIN[1],
                    "cardinal streaming used an invalid path or public stream state")
            self._observe_motion(snapshot, actor)
            require(not self.recorder.failures,
                    "cardinal streaming Walk: " + str(self.recorder.failures))
            require(len(self.recorder.completed) <= ROUTE_MOVES + MAX_SKID_MOVES + 2,
                    "cardinal streaming observed too many motions")
            self.stream_samples.append(self._sample(snapshot, actor))
            require(len(self.stream_samples) <= self.max_frames + 1,
                    "cardinal streaming sample bound exceeded")
            self.frames += 1
            require(self.frames <= self.max_frames,
                    "cardinal streaming frame bound exceeded")
            self.last = deepcopy(snapshot)
            player = (snapshot["player"]["x"], snapshot["player"]["y"])
            if self.target is None and player[0] >= TARGET[0]:
                require(player == TARGET,
                        "cardinal streaming skipped the held-route target")
                self.target = deepcopy(snapshot)
            if self.target is not None and self.route_terminal is None \
                    and actor.get("motionKind") == "NONE" \
                    and actor.get("motionPhase") == "IDLE" \
                    and self.recorder.current is None \
                    and actor.get("logical", {}).get("x") >= TARGET[0]:
                require(TARGET[0] + MIN_SKID_MOVES
                        <= actor["logical"]["x"]
                        <= TARGET[0] + MAX_SKID_MOVES + 1,
                        "cardinal streaming stop exceeded the bounded skid and queued Walk")
                self.route_terminal = deepcopy(snapshot)
                self.route_motion_count = len(self.recorder.completed)
            if self.ready:
                self.terminal = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self._fail(error)
        return self.result()

    def _validate_complete(self):
        route_x = self.route_terminal["player"]["x"]
        route_motions = self.recorder.completed[:self.route_motion_count]
        skid_count = sum(motion["kind"] == "SKID" for motion in route_motions)
        route_count = len(route_motions) - skid_count
        require(route_count in (ROUTE_MOVES, ROUTE_MOVES + 1)
                and skid_count in range(MIN_SKID_MOVES, MAX_SKID_MOVES + 1)
                and route_x == ORIGIN[0] + route_count + skid_count
                and len(self.recorder.completed) == self.route_motion_count + 1
                and self.recorder.current is None,
                "cardinal streaming did not complete the held route and recovery")
        motions = self.recorder.completed
        route = motions[:route_count]
        skid = motions[route_count:self.route_motion_count]
        recovery = motions[-1]
        require([motion["origin"] for motion in route]
                    == [[ORIGIN[0] + index, ORIGIN[1]] for index in range(route_count)]
                and [motion["target"] for motion in route]
                    == [[ORIGIN[0] + index + 1, ORIGIN[1]] for index in range(route_count)]
                and [motion["origin"] for motion in skid]
                    == [[ORIGIN[0] + route_count + index, ORIGIN[1]]
                        for index in range(skid_count)]
                and [motion["target"] for motion in skid]
                    == [[ORIGIN[0] + route_count + index + 1, ORIGIN[1]]
                        for index in range(skid_count)]
                and recovery["origin"] == [route_x, ORIGIN[1]]
                and recovery["target"] == [route_x - 1, ORIGIN[1]]
                and all(motion["kind"] == "WALK" for motion in route + [recovery])
                and all(motion["kind"] == "SKID" for motion in skid)
                and all(complete_travel(motion)
                        and motion["handle"] == self.actor["handle"]
                        and motion["fingerprint"] == self.actor["behaviorFingerprint"]
                        and motion["commitAfter"] == (motion["commitBefore"] + 1) & 0xFFFFFFFF
                        for motion in motions),
                "cardinal streaming route or stop skid differs")
        groups = {name: [event for event in self.traces
                         if event["data"].get("event") == name]
                  for name in LIFECYCLE}
        require(all(len(groups[name]) == route_count + skid_count + 1
                    for name in LIFECYCLE),
                "cardinal streaming lifecycle count differs")
        for index, motion in enumerate(motions):
            lifecycle = [groups[name][index] for name in LIFECYCLE]
            sequences = [event["data"]["sequence"] for event in lifecycle]
            require(sequences == sorted(set(sequences))
                    and lifecycle[0]["frame"] == motion["startFrame"]
                    and lifecycle[1]["frame"] < lifecycle[2]["frame"]
                    and lifecycle[2]["frame"] == motion["commitFrame"]
                    and lifecycle[3]["frame"] == lifecycle[4]["frame"] == motion["finishFrame"]
                    and lifecycle[1]["data"].get("valueB")
                        == (4 if motion["kind"] == "SKID" else 1)
                    and lifecycle[2]["data"].get("valueA") == motion["commitAfter"],
                    "cardinal streaming ordered path lifecycle differs")
            states = [sample["streamState"] for sample in self.stream_samples
                      if motion["startFrame"] <= sample["frame"] <= motion["finishFrame"]]
            require(states and set(states).issubset({0, 1, 2})
                    and 1 in states and 2 in states
                    and states.index(1) < states.index(2),
                    "cardinal streaming public stream lifecycle differs")
        terminal = self._actor(self.terminal)
        require(self.target is not None
                and [self.target["player"]["x"], self.target["player"]["y"]] == list(TARGET)
                and terminal.get("motionKind") == "NONE"
                and terminal.get("motionPhase") == "IDLE"
                and terminal.get("streamState") == 0
                and terminal.get("reservationId") == 0
                and terminal.get("commitSequence")
                    == (self.actor["commitSequence"] + route_count
                        + skid_count + 1) & 0xFFFFFFFF
                and terminal.get("logical") == {"x": route_x - 1, "y": ORIGIN[1]}
                and [self.terminal["player"]["x"], self.terminal["player"]["y"]]
                    == [route_x - 1, ORIGIN[1]],
                "cardinal streaming did not return idle control after recovery")

    @property
    def target_reached(self):
        return self.target is not None and not self.failures

    @property
    def ready(self):
        if self.failures or self.target is None or self.route_terminal is None \
                or self.route_motion_count is None or self.last is None \
                or self.recorder.current is not None:
            return False
        route_x = self.route_terminal["player"]["x"]
        route_motions = self.recorder.completed[:self.route_motion_count]
        skid_count = sum(motion["kind"] == "SKID" for motion in route_motions)
        route_count = len(route_motions) - skid_count
        actor = next((item for item in self.last.get("actors", [])
                      if item.get("handle") == self.subject["handle"]), {})
        return (route_count in (ROUTE_MOVES, ROUTE_MOVES + 1)
                and skid_count in range(MIN_SKID_MOVES, MAX_SKID_MOVES + 1)
                and route_x == ORIGIN[0] + route_count + skid_count
                and len(self.recorder.completed) == self.route_motion_count + 1
                and actor.get("motionKind") == "NONE"
                and actor.get("motionPhase") == "IDLE"
                and actor.get("streamState") == 0
                and actor.get("reservationId") == 0
                and actor.get("logical") == {"x": route_x - 1, "y": ORIGIN[1]})

    def stage(self, name):
        if name == "target-reached":
            return self.target_reached
        if name == "recovered":
            return self.ready
        raise ValueError("unknown cardinal streaming stage")

    def finish(self):
        if not self.failures:
            try:
                require(self.ready,
                        "cardinal streaming did not complete the held route and recovery")
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
            "target": deepcopy(self.target),
            "routeTerminal": deepcopy(self.route_terminal),
            "routeMotionCount": self.route_motion_count,
            "terminal": deepcopy(self.terminal),
            "motions": deepcopy(self.recorder.completed),
            "traces": deepcopy(self.traces),
            "streamSamples": deepcopy(self.stream_samples),
            "completeMotions": len(self.recorder.completed),
        }
