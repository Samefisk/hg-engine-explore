"""Bounded mounted Walk proof across the Route 29 field transition.

Prepared setup places the player beside the reviewed boundary. All credited
movement uses normal input and the shared completed-frame/event stream.
"""
from copy import deepcopy

from tools.overworld.devtools_records import HANDLE_FIELDS, select_current_actor
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel


KIND = "mounted-walk-transition-v1"
REQUIREMENT = "legacy.mounted-walk-transition"
LIFECYCLE = (
    "MOTION_STARTED",
    "LOGICAL_COMMIT",
    "MOTION_FINISHED",
    "CONTROL_RETURNED",
)
ORIGIN = (671, 402)
TRANSITION_ORIGIN = (672, 402)
TRANSITION_TARGET = (673, 402)
RECOVERY_TARGET = (674, 402)
STABLE_HANDLE = ("value", "slot", "generation", "encounterGeneration")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def full_event_handle(data):
    actor = data.get("actor")
    require(isinstance(actor, dict) and set(actor) == set(HANDLE_FIELDS) - {"value"},
            "mounted Walk transition event lacks a full actor handle")
    return {"value": data.get("actorHandle"), **actor}


def same_lifetime(left, right):
    return all(left.get(key) == right.get(key) for key in STABLE_HANDLE)


def paired_pose(snapshot, actor):
    player, mount = snapshot.get("player", {}), actor.get("engineObject", {})
    return (all(type(item.get(key)) is int for item in (player, mount)
                for key in ("x", "y", "pos_x", "pos_y", "pos_z", "facing", "face_y"))
            and all(player[key] == mount[key]
                    for key in ("x", "y", "pos_x", "pos_y", "pos_z", "facing"))
            and player["face_y"] - mount["face_y"] == 0x8000)


class MountedWalkTransitionMeasurement:
    def __init__(self, test, *, max_frames):
        require(type(max_frames) is int and 1 <= max_frames <= 1200,
                "invalid mounted Walk transition frame bound")
        require(test.get("mode") == "prepared"
                and test.get("fixture") == {"rom": "test.nds", "save": "test.sav"}
                and test.get("subjects") == [{
                    "id": "cyndaquil", "species": 155,
                    "role": "MOUNTED", "acquire": "existing",
                }], "mounted Walk transition requires one prepared Cyndaquil mount")
        self.subject_id = "cyndaquil"
        self.max_frames = max_frames
        self.initial = self.transition = self.terminal = self.last = None
        self.initial_subject = self.subject = None
        self.initial_actor = None
        self.frames = 0
        self.recorder = MotionRecorder()
        self.traces = []
        self.context_events = []
        self.pair_samples = []
        self.failures = []
        self.closed = False

    def _fail(self, reason):
        if not self.failures:
            self.failures.append(str(reason))

    @staticmethod
    def _current_actor(snapshot, subject):
        selected = select_current_actor(snapshot, subject)
        return next(actor for actor in snapshot["actors"]
                    if actor.get("handle") == selected["handle"])

    @staticmethod
    def _current_population(snapshot):
        context = snapshot["context"]
        active = [actor for actor in snapshot["actors"] if actor.get("active") is True]
        require(all(actor.get("handle", {}).get("fieldEpoch") == context["fieldEpoch"]
                    and actor.get("handle", {}).get("mapGeneration") == context["mapGeneration"]
                    and actor.get("presentationAttached") is True for actor in active),
                "mounted Walk transition retained a stale or detached actor")
        reservations = [actor["reservationId"] for actor in active
                        if actor.get("reservationId", 0)]
        require(len(reservations) == len(set(reservations)),
                "mounted Walk transition has duplicate reservations")

    def _validate_actor(self, snapshot, actor):
        source, engine = actor.get("sourceIdentity", {}), actor.get("engineIdentity", {})
        context = snapshot["context"]
        require(actor.get("active") is True and actor.get("role") == "MOUNTED"
                and actor.get("species") == 155 and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True
                and actor.get("inputOwnership") == 1
                and actor.get("subjectIdentity") == self.initial_actor["subjectIdentity"]
                and source.get("active") == 1 and source.get("species") == 155
                and source.get("personality") == actor.get("subjectIdentity")
                and source.get("map_id") == context["mapId"]
                and engine.get("active") is True and engine.get("in_manager") is True
                and engine.get("current_map_id") == context["mapId"]
                and engine.get("object_map_id") == context["mapId"]
                and paired_pose(snapshot, actor),
                "mounted Walk transition identity or paired pose differs")
        self._current_population(snapshot)

    def arm(self, subject, snapshot):
        require(self.initial is None and self.subject is None,
                "mounted Walk transition was armed twice")
        selected = select_current_actor(snapshot, subject)
        actor = self._current_actor(snapshot, selected)
        require(snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("context", {}).get("mapId") == 33
                and [snapshot.get("player", {}).get("x"), snapshot.get("player", {}).get("y")]
                    == list(ORIGIN)
                and actor.get("motionKind") == "NONE"
                and actor.get("motionPhase") == "IDLE"
                and actor.get("reservationId") == 0,
                "mounted Walk transition requires idle Cyndaquil at (671,402)")
        self.initial_subject = self.subject = deepcopy(selected)
        self.initial_actor = deepcopy(actor)
        self.initial = self.last = deepcopy(snapshot)
        self._validate_actor(snapshot, actor)
        return self.result()

    def _rebind(self, snapshot):
        old = self.initial_subject
        context, before = snapshot["context"], self.initial["context"]
        require(context.get("mapId") == 60
                and context.get("fieldEpoch") == ((before["fieldEpoch"] + 1) & 0xFFFF or 1)
                and context.get("mapGeneration") == ((before["mapGeneration"] + 1) & 0xFFFF or 1),
                "mounted Walk transition context did not advance from 33 to 60")
        matches = [actor for actor in snapshot.get("actors", [])
                   if actor.get("active") is True
                   and actor.get("role") == "MOUNTED"
                   and actor.get("species") == 155
                   and actor.get("subjectIdentity") == self.initial_actor["subjectIdentity"]
                   and same_lifetime(actor.get("handle", {}), old["handle"])]
        require(len(matches) == 1, "mounted Walk transition lacks one rebound Cyndaquil")
        actor = matches[0]
        selected = select_current_actor(snapshot, actor)
        require(actor.get("motionKind") == "WALK"
                and actor.get("motionPhase") == "MOVING"
                and actor.get("motionElapsed") == 0
                and actor.get("origin") == {"x": TRANSITION_ORIGIN[0], "y": TRANSITION_ORIGIN[1]}
                and actor.get("target") == {"x": TRANSITION_TARGET[0], "y": TRANSITION_TARGET[1]}
                and [snapshot["player"]["x"], snapshot["player"]["y"]]
                    == list(TRANSITION_ORIGIN),
                "mounted Walk transition did not expose the rebound elapsed-zero Walk")
        self.subject = deepcopy(selected)
        self.transition = deepcopy(snapshot)
        return actor

    def _event(self, event):
        if event.get("kind") != "native":
            return
        data = event.get("data", {})
        name = data.get("event")
        if name not in (*LIFECYCLE, "PATH_ADVANCED", "MOTION_CANCELED",
                        "CONTEXT_CHANGED", "ACTOR_REBOUND"):
            return
        handle = full_event_handle(data)
        old = self.initial_subject["handle"]
        if name == "CONTEXT_CHANGED" and handle == old:
            require(data.get("reason") == "CONTEXT_LOST"
                    and data.get("valueA") == self.initial["context"]["fieldEpoch"]
                    and data.get("valueB") == self.transition["context"]["fieldEpoch"],
                    "mounted Walk transition context trace differs")
            self.context_events.append(deepcopy(event))
            return
        if name == "ACTOR_REBOUND" and handle == self.subject["handle"]:
            require(data.get("reason") == "OK"
                    and data.get("valueA") == 33 and data.get("valueB") == 60,
                    "mounted Walk transition rebound trace differs")
            self.context_events.append(deepcopy(event))
            return
        if handle != self.subject["handle"]:
            return
        require(name != "MOTION_CANCELED" and data.get("reason") == "OK",
                "mounted Walk transition motion canceled or failed")
        if name in LIFECYCLE:
            self.traces.append(deepcopy(event))
            require(len(self.traces) <= 2 * len(LIFECYCLE),
                    "mounted Walk transition lifecycle bound exceeded")

    def observe(self, snapshot, events):
        if self.failures or self.closed:
            return self.result()
        try:
            require(self.initial is not None and self.subject is not None,
                    "mounted Walk transition observation preceded binding")
            require(isinstance(snapshot, dict) and isinstance(events, list)
                    and snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot.get("frame") == self.last["frame"] + 1
                    and snapshot.get("nativeCycle") >= self.last["nativeCycle"],
                    "mounted Walk transition frame is missing or reordered")
            context = snapshot.get("context", {})
            if self.transition is None:
                if context == self.initial["context"]:
                    actor = self._current_actor(snapshot, self.initial_subject)
                else:
                    actor = self._rebind(snapshot)
            else:
                require(context == self.transition["context"],
                        "mounted Walk transition context changed more than once")
                actor = self._current_actor(snapshot, self.subject)
            self._validate_actor(snapshot, actor)
            for event in events:
                self._event(event)
            if self.transition is not None:
                self.recorder.observe(snapshot["frame"], actor, actor["engineObject"])
                require(not self.recorder.failures,
                        "mounted Walk transition motion: " + str(self.recorder.failures))
                if actor.get("motionKind") == "WALK":
                    self.pair_samples.append({
                        "frame": snapshot["frame"],
                        "elapsed": actor["motionElapsed"],
                        "player": [snapshot["player"]["pos_x"], snapshot["player"]["pos_y"],
                                   snapshot["player"]["pos_z"]],
                        "mount": [actor["engineObject"]["pos_x"], actor["engineObject"]["pos_y"],
                                  actor["engineObject"]["pos_z"]],
                    })
                require(len(self.recorder.completed) <= 2,
                        "mounted Walk transition observed extra motions")
            self.frames += 1
            require(self.frames <= self.max_frames,
                    "mounted Walk transition frame bound exceeded")
            self.last = deepcopy(snapshot)
            if self.ready:
                self.terminal = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self._fail(error)
        return self.result()

    @property
    def transition_complete(self):
        return (not self.failures and self.transition is not None
                and len(self.recorder.completed) >= 1 and self.recorder.current is None)

    @property
    def ready(self):
        if self.failures or self.transition is None or self.last is None \
                or len(self.recorder.completed) != 2 or self.recorder.current is not None:
            return False
        try:
            actor = self._current_actor(self.last, self.subject)
        except (ValueError, KeyError, TypeError, StopIteration):
            return False
        return (actor.get("motionKind") == "NONE"
                and actor.get("motionPhase") == "IDLE"
                and actor.get("reservationId") == 0
                and actor.get("logical") == {"x": RECOVERY_TARGET[0], "y": RECOVERY_TARGET[1]}
                and [self.last["player"]["x"], self.last["player"]["y"]]
                    == list(RECOVERY_TARGET))

    def stage(self, name):
        if name == "context-changed":
            return self.transition is not None and not self.failures
        if name == "transition-motion-complete":
            return self.transition_complete
        if name == "recovered":
            return self.ready
        raise ValueError("unknown mounted Walk transition stage")

    def _validate_complete(self):
        require(self.ready, "mounted Walk transition and recovery did not finish")
        motions = self.recorder.completed
        transition, recovery = motions
        require(all(motion.get("kind") == "WALK" and complete_travel(motion)
                    and motion.get("handle") == self.subject["handle"]
                    and motion.get("commitAfter") == (motion.get("commitBefore") + 1) & 0xFFFFFFFF
                    for motion in motions)
                and transition["origin"] == list(TRANSITION_ORIGIN)
                and transition["target"] == list(TRANSITION_TARGET)
                and transition["samples"][0]["elapsed"] == 0
                and [sample["elapsed"] for sample in transition["samples"]]
                    == list(range(transition["duration"]))
                and transition["travelEnd"]["elapsed"] == transition["duration"]
                and recovery["origin"] == list(TRANSITION_TARGET)
                and recovery["target"] == list(RECOVERY_TARGET),
                "mounted Walk transition route or completed motion differs")
        grouped = {name: [event for event in self.traces
                          if event["data"].get("event") == name]
                   for name in LIFECYCLE}
        require(all(len(grouped[name]) == 2 for name in LIFECYCLE),
                "mounted Walk transition lifecycle count differs")
        for index, motion in enumerate(motions):
            lifecycle = [grouped[name][index] for name in LIFECYCLE]
            sequences = [event["data"]["sequence"] for event in lifecycle]
            start_matches = lifecycle[0]["frame"] == motion["startFrame"]
            if index == 0:
                start_matches = (self.initial["frame"] < lifecycle[0]["frame"]
                                 < motion["startFrame"]
                                 and full_event_handle(lifecycle[0]["data"])
                                     == self.initial_subject["handle"]
                                 and lifecycle[0]["data"]["sequence"]
                                     < self.context_events[0]["data"]["sequence"])
            require(sequences == sorted(set(sequences)) and start_matches
                    and lifecycle[1]["frame"] == motion["commitFrame"]
                    and lifecycle[2]["frame"] == lifecycle[3]["frame"] == motion["finishFrame"],
                    "mounted Walk transition lifecycle order differs")
        require([event["data"]["event"] for event in self.context_events]
                    == ["CONTEXT_CHANGED", "ACTOR_REBOUND"]
                and self.context_events[0]["data"]["sequence"]
                    < self.context_events[1]["data"]["sequence"],
                "mounted Walk transition context lifecycle differs")
        frames = [sample["frame"] for sample in self.pair_samples
                  if transition["startFrame"] <= sample["frame"] <= transition["finishFrame"]]
        require(len(frames) == transition["duration"] + 1
                and max((right - left for left, right in zip(frames, frames[1:])), default=0) <= 1
                and all(sample["player"] == sample["mount"] for sample in self.pair_samples),
                "mounted Walk transition paired frame schedule differs")

    def finish(self):
        if not self.failures:
            try:
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
            "initialSubject": deepcopy(self.initial_subject),
            "initial": deepcopy(self.initial),
            "transition": deepcopy(self.transition),
            "terminal": deepcopy(self.terminal),
            "motions": deepcopy(self.recorder.completed),
            "traces": deepcopy(self.traces),
            "contextEvents": deepcopy(self.context_events),
            "pairSamples": deepcopy(self.pair_samples),
        }
