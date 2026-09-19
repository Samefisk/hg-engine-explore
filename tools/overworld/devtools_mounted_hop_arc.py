"""Three cardinal Hop arcs over authenticated shared observations; no game control."""
from copy import deepcopy

from .devtools_mount_control_stress import (
    MountControlStressMeasurement, check_snapshot_pair, require,
)
from .normal_play_observer import complete_travel

KIND = "mounted-hop-arc-v1"
REQUIREMENT = "legacy.mankey-hops"
DIRECTIONS = (("DOWN", 128, (0, 1)), ("RIGHT", 16, (1, 0)), ("LEFT", 32, (-1, 0)))


def arc_height(elapsed, duration):
    return 16 * (((4 * elapsed * (duration - elapsed) // duration) << 12) // duration)


class MountedHopArcMeasurement(MountControlStressMeasurement):
    """Reuse identity, stream accounting and lifecycle joining, not stress floors.

    Each native-observation mounted-hop-start receipt contains the bound subject,
    entry/return cycles and start={elapsed,duration,origin,target,motionIdentity,
    baseFaceY,faceY}. Its zero sample is mandatory; an idle snapshot is not a start.
    """
    def __init__(self, max_frames=1600):
        require(type(max_frames) is int and 1 <= max_frames <= 4000, "invalid Hop arc frame bound")
        super().__init__("hop", 40000)
        self.max_frames = max_frames
        self.rules.update(motions=3, frames=0)
        self.cases = []
        self.pending_start = None
        self.arc_samples = []
        self.arc_frames = []
        self.start_snapshot = None
        self.previous_native_cycle = None

    def _start(self, event, snapshot, actor):
        data = event["data"]
        start = data.get("start", {})
        require(self.pending_start is None and self.recorder.current is None and len(self.cases) < 3,
                "duplicate or extra Hop start receipt")
        require(data.get("subject") == self.subject and event.get("kind") == "native-observation",
                "Hop start subject differs")
        require(type(data.get("entryNativeCycle")) is int and type(data.get("returnNativeCycle")) is int
                and self.last["nativeCycle"] <= data["entryNativeCycle"] <= data["returnNativeCycle"] <= snapshot["nativeCycle"],
                "Hop start native clock differs")
        require(start.get("elapsed") == 0 and type(start.get("elapsed")) is int
                and type(start.get("duration")) is int and 0 < start["duration"] <= self.max_frames
                and start["duration"] == actor["motionDuration"]
                and start.get("origin") == actor["origin"] and start.get("target") == actor["target"]
                and type(start.get("motionIdentity")) is int and start["motionIdentity"] > 0
                and start["motionIdentity"] == actor["reservationId"]
                and type(start.get("baseFaceY")) is int and type(start.get("faceY")) is int
                and start["faceY"] == start["baseFaceY"], "Hop native start fields differ")
        _, mask, direction = DIRECTIONS[len(self.cases)]
        require(snapshot["selector"].get("rawHeld", 0) & 0xF0 == mask
                and snapshot["selector"].get("heldKeys", snapshot["selector"].get("rawHeld", 0)) & 0xF0 == mask,
                "Hop start lacks requested natural cardinal input")
        delta = tuple(actor["target"][k] - actor["origin"][k] for k in ("x", "y"))
        require(tuple((n > 0) - (n < 0) for n in delta) == direction, "Hop requested axis differs")
        self.pending_start = deepcopy(event)
        self.start_snapshot = deepcopy(snapshot)
        self.previous_native_cycle = self.last["nativeCycle"]
        self.arc_samples = [[0, start["faceY"] - start["baseFaceY"]]]
        self.arc_frames = []

    def observe(self, snapshot, events):
        if self.phase == "unarmed" or self.failures:
            return self.result()
        try:
            require(not self.closed, "Hop arc observation already closed")
            require(snapshot.get("fieldAvailable") is True
                    and snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot["context"] == self.initial["context"], "Hop arc context differs")
            require(snapshot["frame"] == self.last["frame"] + 1
                    and snapshot["nativeCycle"] > self.last["nativeCycle"], "Hop arc completed clock gap")
            self.frames += 1
            require(self.frames <= self.max_frames, "Hop arc frame bound exceeded")
            native = snapshot["nativeObservation"]
            require(native.get("installedBeforeBoot") is True and native.get("coverageComplete") is True
                    and native.get("error") is None and all(native.get(k) == 0 for k in ("eventsDropped", "profilesEvicted")),
                    "Hop arc native coverage incomplete")
            actor = self._actor(snapshot)
            require(actor["role"] == "MOUNTED" and actor["inputOwnership"] == 1
                    and all(actor[k] == self.actor[k] for k in ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration")),
                    "Hop arc ownership changed")
            check_snapshot_pair(snapshot, actor)
            for event in events:
                if event.get("data", {}).get("observation") == "mounted-hop-start":
                    self._start(event, snapshot, actor)
            self._events(snapshot, events, actor)
            active = actor["motionPhase"] in ("PLANNED", "MOVING", "COMMIT_PENDING", "SETTLING")
            if active:
                require(actor["motionKind"] == "HOP" and actor["motionKindId"] == 2, "wrong Hop arc motion kind")
                require(self.pending_start is not None, "missing real native Hop start receipt")
            if self.pending_start is not None:
                start = self.pending_start["data"]["start"]
                elapsed = actor["motionElapsed"]
                if len(self.arc_samples) <= start["duration"]:
                    require(type(elapsed) is int and elapsed == len(self.arc_samples), "Hop arc elapsed gap")
                    height = actor["engineObject"]["face_y"] - start["baseFaceY"]
                    require(height == arc_height(elapsed, start["duration"]), "Hop arc parabola differs")
                    self.arc_samples.append([elapsed, height])
                    self.arc_frames.append(dict(frame=snapshot["frame"], elapsed=elapsed,
                                               faceY=actor["engineObject"]["face_y"]))
            self.recorder.observe(snapshot["frame"], actor, snapshot["player"])
            require(not self.recorder.failures, "Hop travel differs: " + str(self.recorder.failures))
            while self.recorder.completed:
                motion = self.recorder.completed.pop(0)
                require(complete_travel(motion) and self.pending_start is not None, "Hop lacks complete travel/start")
                require(len(self.arc_samples) == motion["duration"] + 1, "Hop arc endpoint missing")
                super()._join(motion)
                require(actor["motionPhase"] == "IDLE" and actor["reservationId"] == 0, "Hop terminal control not restored")
                self.cases.append(dict(startReceipt=self.pending_start, samples=deepcopy(self.arc_samples),
                                       startSnapshot=self.start_snapshot, previousNativeCycle=self.previous_native_cycle,
                                       observations=deepcopy(self.arc_frames), summary=deepcopy(self.motion_summaries[-1]),
                                       terminalActor=deepcopy(actor), terminalFrame=snapshot["frame"]))
                self.pending_start = None
            self.actor = deepcopy(actor)
            self.last = dict(frame=snapshot["frame"], nativeCycle=snapshot["nativeCycle"], player=deepcopy(snapshot["player"]))
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    @property
    def ready(self):
        return not self.failures and len(self.cases) == 3 and self.pending_start is None and not self.traces

    def finish(self):
        if not self.ready and not self.failures:
            self.failures.append("three complete native Hop arcs required")
        self.closed = True
        return self.result()

    def result(self, *_args):
        return dict(kind=KIND, contract=REQUIREMENT, passed=self.closed and self.ready,
                    ready=self.ready, closed=self.closed, acceptedProof=False, frames=self.frames,
                    failures=list(self.failures), subject=deepcopy(self.subject), initial=deepcopy(self.initial),
                    cases=deepcopy(self.cases))
