"""One naturally selected Wild Gastly Teleport from shared frame data."""
from copy import deepcopy

from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel, live_identity


KIND = "wild-teleport-v1"
REQUIREMENT = "legacy.wild-teleport"
IDENTITY = (
    "handle", "species", "form", "level", "role", "subjectIdentity",
    "authorityGeneration", "engineAnchorGeneration", "presentationGeneration",
    "behaviorFingerprint", "matchedLayerMask",
)
LIFECYCLE = (
    "MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED",
)


def require(value, reason):
    if not value:
        raise ValueError(reason)


class WildTeleportMeasurement:
    def __init__(self, max_frames=600):
        require(type(max_frames) is int and 1 <= max_frames <= 1200,
                "invalid wild Teleport frame bound")
        self.max_frames = max_frames
        self.initial = self.last = self.actor = self.subject = None
        self.frames = self.sequence = 0
        self.streams = {}
        self.failures, self.traces, self.logical_samples = [], [], []
        self.recorder = MotionRecorder()
        self.motion = None

    def arm(self, subject, snapshot, trace_sequences=None):
        require(self.initial is None, "wild Teleport measurement already armed")
        selected = select_current_actor(snapshot, subject)
        actor = next(item for item in snapshot["actors"]
                     if item["handle"] == selected["handle"])
        require(
            live_identity(
                actor, actor.get("sourceIdentity", {}), actor.get("engineIdentity", {}),
                species=92, role="WILD", current_epoch=snapshot["context"]["fieldEpoch"],
            )
            and actor.get("identityVerified") is True
            and actor.get("presentationAttached") is True
            and actor.get("inputOwnership") == 0
            and actor.get("motionKind") == "NONE"
            and actor.get("motionPhase") == "IDLE"
            and actor.get("reservationId") == 0,
            "wild Teleport requires one idle live Gastly",
        )
        self.subject = deepcopy(selected)
        self.actor = deepcopy(actor)
        self.initial = self.last = deepcopy(snapshot)
        self.sequence = snapshot["nativeObservation"]["sequence"]
        self.streams = dict(trace_sequences or {})

    def _actor(self, snapshot):
        selected = select_current_actor(snapshot, self.subject)
        actor = next(item for item in snapshot["actors"]
                     if item["handle"] == selected["handle"])
        require(
            all(actor.get(key) == self.actor.get(key) for key in IDENTITY)
            and actor.get("inputOwnership") == 0
            and actor.get("sourceIdentity") == self.actor.get("sourceIdentity")
            and engine_binding_identity(actor.get("engineIdentity"))
                == engine_binding_identity(self.actor.get("engineIdentity"))
            and snapshot["context"] == self.initial["context"],
            "wild Teleport identity or profile changed",
        )
        return actor

    def _events(self, name):
        return [event for event in self.traces
                if event["data"].get("event") == name]

    def _check_world(self, snapshot):
        active = [actor for actor in snapshot["actors"] if actor.get("active") is True]
        require(all(actor.get("presentationAttached") is True
                    and actor.get("handle", {}).get("fieldEpoch")
                        == snapshot["context"]["fieldEpoch"]
                    for actor in active),
                "wild Teleport active actor world identity differs")
        reservations = [actor.get("reservationId") for actor in active
                        if actor.get("reservationId")]
        require(all(type(value) is int and value > 0 for value in reservations)
                and len(reservations) == len(set(reservations)),
                "wild Teleport target reservation is shared")

    def observe(self, snapshot, events):
        if self.failures:
            return self.result()
        try:
            require(self.initial is not None and not self.ready,
                    "wild Teleport window is not open")
            actor = self._actor(snapshot)
            require(snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot["frame"] == self.last["frame"] + 1
                    and snapshot["nativeCycle"] >= self.last["nativeCycle"],
                    "wild Teleport completed clock gap")
            selector = snapshot.get("selector", {})
            require(all(type(selector.get(key)) is int and selector[key] == 0
                        for key in ("heldKeys", "newKeys", "physicalPressed", "simulatedKeys")),
                    "wild Teleport requires neutral input")
            native = snapshot["nativeObservation"]
            require(native.get("installedBeforeBoot") is True
                    and native.get("coverageComplete") is True
                    and native.get("error") is None
                    and all(native.get(key) == 0
                            for key in ("eventsDropped", "profilesEvicted")),
                    "wild Teleport native coverage incomplete")
            self.frames += 1
            require(self.frames <= self.max_frames, "wild Teleport frame bound exceeded")
            self._check_world(snapshot)
            for event in events:
                data = event.get("data", {})
                require(event.get("frame") == snapshot["frame"],
                        "wild Teleport event frame differs")
                if event.get("kind") == "native-observation":
                    require(data.get("sequence") == self.sequence + 1,
                            "wild Teleport native receipt gap")
                    self.sequence += 1
                    require(self.last["nativeCycle"] <= data.get("entryNativeCycle", -1)
                            <= data.get("returnNativeCycle", -1) <= snapshot["nativeCycle"],
                            "wild Teleport native clock differs")
                elif event.get("kind") == "native":
                    stream, sequence = data.get("traceStream"), data.get("sequence")
                    require(type(stream) is int and stream > 0 and type(sequence) is int
                            and sequence == self.streams.get(stream, 0) + 1,
                            "wild Teleport semantic sequence gap")
                    self.streams[stream] = sequence
                    if data.get("actorHandle") == self.actor["handle"]["value"]:
                        require(data.get("actor") == {
                            key: value for key, value in self.actor["handle"].items()
                            if key != "value"
                        }, "wild Teleport semantic identity differs")
                        require(data.get("event") not in (
                            "MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND",
                            "CONTROL_REBOUND",
                        ), "wild Teleport motion canceled or rebound")
                        self.traces.append(deepcopy(event))
                        require(len(self.traces) <= 256,
                                "wild Teleport trace bound exceeded")
                elif event.get("kind") == "trace-status" \
                        and data.get("code") == "ring-overwrite":
                    require(type(data.get("unreadEventsLost")) is int
                            and data["unreadEventsLost"] == 0
                            and data.get("coverageComplete", True) is True
                            and data.get("diagnosticOnly") is True
                            and type(data.get("traceStream")) is int
                            and data["traceStream"] in self.streams,
                            "wild Teleport trace lost unread events")
                else:
                    raise ValueError("wild Teleport trace status or unknown event")
            require(native["sequence"] == self.sequence,
                    "wild Teleport missing native receipt")
            require(actor["motionKind"] in ("NONE", "TELEPORT"),
                    "wild Teleport was replaced by another motion")
            if actor["motionKind"] == "TELEPORT":
                require(type(actor.get("motionDuration")) is int
                        and actor["motionDuration"] == 9,
                        "wild Teleport requires its authored nine-frame travel")
            starts = self._events("MOTION_STARTED")
            require(len(starts) <= 1, "extra wild Teleport started")
            if starts and self.motion is None:
                self.logical_samples.append({
                    "frame": snapshot["frame"],
                    "logical": deepcopy(actor["logical"]),
                    "engineLogical": {
                        "x": actor["engineObject"]["x"],
                        "y": actor["engineObject"]["y"],
                    },
                    "commitSequence": actor["commitSequence"],
                    "motionKind": actor["motionKind"],
                    "motionPhase": actor["motionPhase"],
                    "elapsed": actor["motionElapsed"],
                })
            self.recorder.observe(snapshot["frame"], actor, actor["engineObject"])
            require(not self.recorder.failures,
                    "wild Teleport motion: " + str(self.recorder.failures))
            require(len(self.recorder.completed) <= 1,
                    "wild Teleport produced extra motion")
            if self.recorder.completed:
                require(self.recorder.current is None,
                        "wild Teleport terminal motion is still active")
                self.motion = self.recorder.completed[0]
                self._check_motion(actor)
            self.last = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def _check_motion(self, actor):
        motion = self.motion
        require(motion["kind"] == "TELEPORT" and motion["duration"] == 9
                and complete_travel(motion),
                "wild Teleport lacks one complete nine-frame motion")
        require(motion["origin"] != motion["target"],
                "wild Teleport target equals its origin")
        elapsed = [sample["elapsed"] for sample in motion["samples"]]
        require(elapsed and elapsed == list(range(elapsed[0], motion["duration"])),
                "wild Teleport elapsed schedule differs")
        require(motion["commitAfter"] == ((motion["commitBefore"] + 1) & 0xFFFFFFFF),
                "wild Teleport terminal commit differs")
        precommit = [sample for sample in self.logical_samples
                     if sample["commitSequence"] == motion["commitBefore"]]
        require(precommit
                and all(sample["logical"] != dict(zip(("x", "y"), motion["target"]))
                        and sample["engineLogical"]
                            == dict(zip(("x", "y"), motion["origin"]))
                        for sample in precommit),
                "wild Teleport reached target before commit")
        require(actor["logical"] == dict(zip(("x", "y"), motion["target"]))
                and actor["commitSequence"] == motion["commitAfter"],
                "wild Teleport terminal target differs")
        paths = self._events("PATH_ADVANCED")
        require(paths and all(event["data"].get("reason") == "OK"
                              and event["data"].get("valueB") == 3
                              and motion["startFrame"] < event["frame"]
                                  <= motion["commitFrame"]
                              for event in paths),
                "missing native PATH_ADVANCED")
        wanted = (
            ("MOTION_STARTED", motion["startFrame"], 3, 9),
            ("LOGICAL_COMMIT", motion["commitFrame"], motion["commitAfter"], 3),
            ("MOTION_FINISHED", motion["finishFrame"], motion["commitAfter"], 3),
            ("CONTROL_RETURNED", motion["finishFrame"], 0, 1),
        )
        sequence = []
        for name, frame, value_a, value_b in wanted:
            events = self._events(name)
            require(len(events) == 1 and events[0]["frame"] == frame
                    and events[0]["data"].get("reason") == "OK"
                    and (events[0]["data"].get("valueA"),
                         events[0]["data"].get("valueB")) == (value_a, value_b),
                    "missing native " + name)
            sequence.append(events[0]["data"]["sequence"])
        path_sequences = [event["data"]["sequence"] for event in paths]
        require(sequence == sorted(set(sequence))
                and sequence[0] < min(path_sequences)
                and max(path_sequences) < sequence[1],
                "wild Teleport lifecycle order differs")
        require(actor["motionKind"] == "NONE" and actor["motionPhase"] == "IDLE"
                and actor["reservationId"] == 0,
                "wild Teleport terminal control is not idle")

    @property
    def ready(self):
        return self.motion is not None and not self.failures

    @property
    def closed(self):
        return self.ready

    def finish(self):
        if not self.ready and not self.failures:
            self.failures.append("wild Teleport motion was not completed")
        return self.result()

    def result(self):
        return {
            "kind": KIND,
            "requirements": [REQUIREMENT],
            "passed": self.ready,
            "ready": self.ready,
            "closed": self.closed,
            "acceptedProof": False,
            "failures": list(self.failures),
            "frames": self.frames,
            "completeMotions": len(self.recorder.completed),
            "subject": deepcopy(self.subject),
            "initial": deepcopy(self.initial),
            "terminal": deepcopy(self.last),
            "motion": deepcopy(self.motion),
            "traces": deepcopy(self.traces),
            "logicalSamples": deepcopy(self.logical_samples),
        }
