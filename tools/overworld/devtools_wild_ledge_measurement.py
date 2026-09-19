"""One real downhill Wild Hop and one real uphill Wild Hop."""
from copy import deepcopy

from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.devtools_wild_ledge_observer import IDENTITY, ORIGIN, SPECIES, TARGET
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel

KIND = "wild-ledge-v1"
REQUIREMENTS = ("legacy.wild-ledge-hop",)
LIFECYCLE = ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")


def require(value, reason):
    if not value:
        raise ValueError(reason)


class WildLedgeMeasurement:
    def __init__(self, max_frames=600):
        require(type(max_frames) is int and 1 <= max_frames <= 1200, "invalid wild ledge frame bound")
        self.max_frames = max_frames
        self.initial = self.last = self.actor = self.subject = None
        self.frames = self.sequence = 0
        self.streams = {}
        self.receipts, self.traces, self.failures = [], [], []
        self.recorder = MotionRecorder()
        self.closed = False
        self.cleanup = None

    def _actor(self, snapshot):
        bound = select_current_actor(snapshot, self.subject)
        actor = next(item for item in snapshot["actors"] if item["handle"] == bound["handle"])
        require(all(actor.get(key) == self.actor.get(key) for key in IDENTITY)
            and actor.get("inputOwnership") == 0 and actor.get("sourceIdentity") == self.actor.get("sourceIdentity")
            and engine_binding_identity(actor.get("engineIdentity")) == engine_binding_identity(self.actor.get("engineIdentity"))
            and snapshot["context"] == self.initial["context"], "wild ledge identity or context changed")
        return actor

    def _reader(self, receipt, closed):
        value = receipt.get("wildLedge", receipt)
        require(value.get("armed") is True and value.get("closed") is closed
            and value.get("failure") is None and value.get("acceptedProof") is False
            and value.get("subject") == self.subject and value.get("startFrame") == self.initial["frame"]
            and value.get("pendingWrites") == 0
            and value.get("guestMemoryWrites") in (0, 2, 4), "wild ledge reader differs")
        return value

    def arm(self, subject, snapshot, receipt, trace_sequences=None):
        require(self.initial is None, "wild ledge reader already armed")
        self.subject = deepcopy(subject)
        selected = select_current_actor(snapshot, subject)
        actor = next(item for item in snapshot["actors"] if item["handle"] == selected["handle"])
        require(actor.get("species") == SPECIES and actor.get("role") == "WILD"
            and actor.get("identityVerified") is True and actor.get("presentationAttached") is True
            and actor.get("motionKind") == "NONE" and actor.get("motionPhase") == "IDLE"
            and actor.get("reservationId") == 0
            and [actor["logical"][key] for key in ("x", "y")] == ORIGIN,
            "wild ledge requires one idle live Clefairy at the origin")
        self.initial = self.last = deepcopy(snapshot)
        self.actor = deepcopy(actor)
        # A ledge crossing is one Wander step with a jump trajectory. The
        # normal locomotion completion owns its authored pause, so the shared
        # Hop must not settle for hopPause as well.
        self.recorder.expected_pause_by_kind["HOP"] = 0
        reader = self._reader(receipt, False)
        require(reader.get("phase") == "south-pending" and reader.get("calls") == []
            and reader.get("guestMemoryWrites") == 0 and reader.get("terminal") is False,
            "wild ledge reader contains prior decisions")
        self.sequence = snapshot["nativeObservation"]["sequence"]
        self.streams = dict(trace_sequences or {})

    def observe(self, snapshot, events):
        if self.failures:
            return self.result()
        try:
            require(self.initial is not None and not self.closed, "wild ledge window is not open")
            actor = self._actor(snapshot)
            reader = self._reader(snapshot["wildLedge"], False)
            require(snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot["frame"] == self.last["frame"] + 1
                and snapshot["nativeCycle"] >= self.last["nativeCycle"], "wild ledge completed clock gap")
            neutral = reader.get("latestCompletedInput", {})
            require(neutral.get("frame") == snapshot["frame"] and neutral.get("nativeCycle") == snapshot["nativeCycle"]
                and neutral.get("heldKeys") == 0 and neutral.get("newKeys") == 0,
                "wild ledge requires measured neutral input")
            native = snapshot["nativeObservation"]
            require(native.get("installedBeforeBoot") is True and native.get("coverageComplete") is True
                and native.get("error") is None and all(native.get(key) == 0 for key in ("eventsDropped", "profilesEvicted")),
                "wild ledge native coverage incomplete")
            self.frames += 1
            require(self.frames <= self.max_frames, "wild ledge frame bound exceeded")
            for event in events:
                data = event.get("data", {})
                require(event.get("frame") == snapshot["frame"], "wild ledge event frame differs")
                if event.get("kind") == "native-observation":
                    require(data.get("sequence") == self.sequence + 1, "wild ledge native receipt gap")
                    self.sequence += 1
                    if data.get("observation") == "wild-ledge-intent" and not data.get("suppressed"):
                        require(data.get("subject") == self.subject, "wild ledge receipt subject differs")
                        self.receipts.append(deepcopy(event))
                elif event.get("kind") == "native":
                    stream, sequence = data.get("traceStream"), data.get("sequence")
                    require(type(stream) is int and stream > 0 and type(sequence) is int
                        and sequence == self.streams.get(stream, 0) + 1, "wild ledge semantic sequence gap")
                    self.streams[stream] = sequence
                    if data.get("actorHandle") == self.actor["handle"]["value"]:
                        require(data.get("event") not in ("MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND", "CONTROL_REBOUND"),
                                "wild ledge motion canceled or rebound")
                        self.traces.append(deepcopy(event))
                elif event.get("kind") == "trace-status" and data.get("code") == "ring-overwrite":
                    require(data.get("unreadEventsLost") == 0 and data.get("coverageComplete", True) is True
                        and data.get("diagnosticOnly") is True and data.get("traceStream") in self.streams,
                        "wild ledge trace lost unread events")
                else:
                    raise ValueError("wild ledge unknown event")
            require(native["sequence"] == self.sequence, "wild ledge missing native receipt")
            require(len(self.receipts) <= 2 and len(reader.get("calls", [])) == len(self.receipts),
                    "wild ledge decision receipts differ")
            self.recorder.observe(snapshot["frame"], actor, actor["engineObject"])
            require(not self.recorder.failures, "wild ledge motion: " + str(self.recorder.failures))
            require(len(self.recorder.completed) <= 2, "wild ledge produced extra motion")
            self.last = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    @property
    def ready(self):
        if self.failures or len(self.recorder.completed) != 2 or self.recorder.current is not None \
                or len(self.receipts) != 2:
            return False
        reader = self.last.get("wildLedge", {}) if self.last else {}
        return reader.get("terminal") is True and reader.get("phase") == "terminal"

    def close(self, receipt, snapshot):
        require(self.ready and snapshot == self.last, "wild ledge measurement is incomplete")
        reader = self._reader(receipt, True)
        require(reader.get("terminal") is True and reader.get("phase") == "terminal"
            and reader.get("guestMemoryWrites") == 4 and len(reader.get("calls", [])) == 2
            and [row.get("case") for row in reader["calls"]] == ["south", "north"]
            and [row.get("returnValue") for row in reader["calls"]] == [2, 2],
            "wild ledge close decisions differ")
        self.cleanup = deepcopy(receipt)
        self.closed = True
        return self.result()

    def finish(self):
        if not self.closed and not self.failures:
            self.failures.append("wild ledge reader was not closed")
        return self.result()

    def result(self):
        return dict(kind=KIND, requirements=list(REQUIREMENTS), passed=self.closed and self.ready,
            ready=self.ready, closed=self.closed, acceptedProof=False, failures=list(self.failures),
            frames=self.frames, completeMotions=len(self.recorder.completed), subject=deepcopy(self.subject),
            initial=deepcopy(self.initial), terminal=deepcopy(self.last), motions=deepcopy(self.recorder.completed),
            decisionReceipts=deepcopy(self.receipts), traces=deepcopy(self.traces), cleanup=deepcopy(self.cleanup))
