"""One natural Runner stop skid from the shared Wild and Walk observations."""

from copy import deepcopy

from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel, live_identity


KIND = "runner-stop-skid-v1"
REQUIREMENT = "legacy.runner-stop-skid"
IDENTITY = (
    "handle", "species", "form", "level", "role", "subjectIdentity",
    "authorityGeneration", "engineAnchorGeneration", "presentationGeneration",
)
LIFECYCLE = (
    "MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED",
)

WALK_POLICY_INPUT = 1
WALK_POLICY_START_RESULT = 2
WALK_DIRECTION_NONE = 0xFF
SPOT_STATE_TIRED = 3
START_ACCEPTED = 1
DECISION_CONSUMED = 1
DECISION_TRY_STEP = 2
STEP_VALIDATE = 0x01
STEP_SKID = 0x02
STEP_STOP_SKID = 0x04
STEP_PLANNED_SKID_PATH = 0x80
STOP_STEP_FLAGS = STEP_VALIDATE | STEP_SKID | STEP_STOP_SKID


def require(value, reason):
    if not value:
        raise ValueError(reason)


def decode_call(value):
    raw = bytes.fromhex(value)
    require(len(raw) == 28 and int.from_bytes(raw[0:2], "little") == 1
            and int.from_bytes(raw[2:4], "little") == 28,
            "Runner stop skid Walk-policy ABI differs")
    return raw


def same_public_subject(value, actor):
    handle = value.get("handle", {})
    return all(value.get(key) == actor.get(key) for key in IDENTITY if key != "handle") \
        and handle == actor.get("handle")


class RunnerStopSkidMeasurement:
    def __init__(self, max_frames=600):
        require(type(max_frames) is int and 1 <= max_frames <= 1200,
                "invalid Runner stop-skid frame bound")
        self.max_frames = max_frames
        self.initial = self.last = self.actor = self.subject = None
        self.frames = self.sequence = 0
        self.streams = {}
        self.failures = []
        self.traces = []
        self.policy_input = self.start_result = None
        self.continuation = None
        self.continuation_frame = None
        self.policy_frame = None
        self.stop_speed = None
        self.recorder = None
        self.motion = None
        self.motions = None

    def arm(self, subject, snapshot, trace_sequences=None):
        require(self.initial is None, "Runner stop-skid measurement already armed")
        selected = select_current_actor(snapshot, subject)
        actor = next(item for item in snapshot["actors"]
                     if item["handle"] == selected["handle"])
        require(
            live_identity(
                actor, actor.get("sourceIdentity", {}), actor.get("engineIdentity", {}),
                species=234, role="WILD",
                current_epoch=snapshot["context"]["fieldEpoch"],
            )
            and actor.get("identityVerified") is True
            and actor.get("presentationAttached") is True
            and actor.get("inputOwnership") == 0
            and actor.get("motionKind") == "NONE"
            and actor.get("motionPhase") == "IDLE"
            and actor.get("reservationId") == 0,
            "Runner stop skid requires one idle live Stantler",
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
            "Runner stop-skid live identity changed",
        )
        return actor

    def _check_world(self, snapshot):
        active = [actor for actor in snapshot["actors"] if actor.get("active") is True]
        require(all(actor.get("presentationAttached") is True
                    and actor.get("handle", {}).get("fieldEpoch")
                        == snapshot["context"]["fieldEpoch"]
                    for actor in active),
                "Runner stop-skid active actor world identity differs")
        reservations = [actor.get("reservationId") for actor in active
                        if actor.get("reservationId")]
        require(len(reservations) == len(set(reservations)),
                "Runner stop-skid target reservation is shared")

    def _walk_policy(self, event):
        data = event["data"]
        before = data.get("publicSubject", {})
        after = data.get("publicSubjectAfter", {})
        if data.get("slot") != self.actor["handle"]["slot"] \
                or not same_public_subject(before, self.actor) \
                or not same_public_subject(after, self.actor):
            return
        request = decode_call(data["requestHex"])
        response = decode_call(data["responseHex"])
        require(request[8] == response[8] == self.actor["handle"]["slot"]
                and request[9] == response[9] == data.get("operation"),
                "Runner stop skid Walk-policy owner differs")

        if data["operation"] == WALK_POLICY_START_RESULT and self.start_result is not None \
                and request[20] == 0x13:
            require(self.continuation is None
                    and request[11] == response[11] == 1
                    and request[15] == response[15] == START_ACCEPTED
                    and request[16] == DECISION_TRY_STEP and response[16] == DECISION_CONSUMED
                    and request[17] == request[18] == self._policy_response()[17]
                    and request[17:21] == response[17:21]
                    and request[19] == 8
                    and request[22] == request[23] == response[22] == response[23] == 0,
                    "Runner stop-skid continuation differs")
            self.continuation = deepcopy(data)
            self.continuation_frame = event["frame"]
            return

        if data["operation"] == WALK_POLICY_INPUT \
                and request[10] == WALK_DIRECTION_NONE \
                and request[13] == SPOT_STATE_TIRED \
                and response[16] == DECISION_TRY_STEP \
                and response[20] & STOP_STEP_FLAGS == STOP_STEP_FLAGS:
            require(self.policy_input is None and self.start_result is None,
                    "Runner stop skid produced duplicate stop input")
            prior = self._actor(self.last)
            speed = prior.get("movementPolicy", {}).get("speed")
            require(before.get("motionKind") == "NONE"
                    and before.get("motionPhase") == "IDLE"
                    and speed == 4
                    and request[11] == 0 and request[12] == 0
                    and request[14] == 0 and request[15] == 0
                    and response[10] == WALK_DIRECTION_NONE
                    and response[11] == 2 and response[12] == 0
                    and response[13] == SPOT_STATE_TIRED
                    and response[14] == 0 and response[15] == 0
                    and response[17] < 4 and response[18] == response[17]
                    and response[19] == 8 and response[20] == STOP_STEP_FLAGS,
                    "Runner stop skid normal NONE proposal differs")
            require(all(raw[22] == 0 and raw[23] == 0
                        for raw in (request, response)),
                    "Runner stop skid used a Movement Chain action or pause action")
            self.policy_input = deepcopy(data)
            self.policy_frame = event["frame"]
            self.stop_speed = speed
            return

        if data["operation"] == WALK_POLICY_START_RESULT \
                and self.policy_input is not None and self.start_result is None \
                and event["frame"] == self.policy_frame:
            require(request[10] == WALK_DIRECTION_NONE
                    and request[11] == 2 and request[12] == 0
                    and request[13] == SPOT_STATE_TIRED
                    and request[14] == 0
                    and request[15] == START_ACCEPTED
                    and response[15] == START_ACCEPTED
                    and request[16] == DECISION_TRY_STEP
                    and response[16] == DECISION_CONSUMED
                    and request[17:20] == response[17:20]
                    and request[17] == self._policy_response()[17]
                    and request[18] == request[17]
                    and request[19] == 8
                    and request[20] == response[20]
                        == (STOP_STEP_FLAGS | STEP_PLANNED_SKID_PATH)
                    and request[25] == response[25] == 2,
                    "Runner stop skid start was not two accepted planned tiles")
            require(all(raw[22] == 0 and raw[23] == 0
                        for raw in (request, response)),
                    "Runner stop skid used a Movement Chain action or pause action")
            self.start_result = deepcopy(data)

    def _policy_response(self):
        return decode_call(self.policy_input["responseHex"])

    def observe(self, snapshot, events):
        if self.failures:
            return self.result()
        try:
            require(self.initial is not None and not self.ready,
                    "Runner stop-skid window is not open")
            actor = self._actor(snapshot)
            require(snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot["frame"] == self.last["frame"] + 1
                    and snapshot["nativeCycle"] >= self.last["nativeCycle"],
                    "Runner stop-skid completed clock gap")
            selector = snapshot.get("selector", {})
            require(all(type(selector.get(key)) is int and selector[key] == 0
                        for key in ("heldKeys", "newKeys", "physicalPressed", "simulatedKeys")),
                    "Runner stop skid requires neutral input")
            native = snapshot["nativeObservation"]
            require(native.get("installedBeforeBoot") is True
                    and native.get("coverageComplete") is True
                    and native.get("error") is None
                    and all(native.get(key) == 0
                            for key in ("eventsDropped", "profilesEvicted")),
                    "Runner stop-skid native coverage incomplete")
            self.frames += 1
            require(self.frames <= self.max_frames,
                    "Runner stop-skid frame bound exceeded")
            self._check_world(snapshot)

            for event in events:
                data = event.get("data", {})
                require(event.get("frame") == snapshot["frame"],
                        "Runner stop-skid event frame differs")
                if event.get("kind") == "native-observation":
                    require(data.get("sequence") == self.sequence + 1,
                            "Runner stop-skid native receipt gap")
                    self.sequence += 1
                    require(self.last["nativeCycle"] <= data.get("entryNativeCycle", -1)
                            <= data.get("returnNativeCycle", -1) <= snapshot["nativeCycle"],
                            "Runner stop-skid native clock differs")
                    if data.get("observation") == "walk-policy":
                        self._walk_policy(event)
                elif event.get("kind") == "native":
                    stream, sequence = data.get("traceStream"), data.get("sequence")
                    require(type(stream) is int and stream > 0 and type(sequence) is int
                            and sequence == self.streams.get(stream, 0) + 1,
                            "Runner stop-skid semantic sequence gap")
                    self.streams[stream] = sequence
                    if data.get("actorHandle") == self.actor["handle"]["value"]:
                        require(data.get("actor") == {
                            key: value for key, value in self.actor["handle"].items()
                            if key != "value"
                        }, "Runner stop-skid semantic identity differs")
                        require(data.get("event") not in (
                            "MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND",
                            "CONTROL_REBOUND",
                        ), "Runner stop-skid motion canceled or rebound")
                        self.traces.append(deepcopy(event))
                        require(len(self.traces) <= 2048,
                                "Runner stop-skid trace bound exceeded")
                elif event.get("kind") == "trace-status" \
                        and data.get("code") == "ring-overwrite":
                    require(type(data.get("unreadEventsLost")) is int
                            and data["unreadEventsLost"] == 0
                            and data.get("coverageComplete", True) is True
                            and data.get("diagnosticOnly") is True
                            and type(data.get("traceStream")) is int
                            and data["traceStream"] in self.streams,
                            "Runner stop-skid trace lost unread events")
                else:
                    raise ValueError("Runner stop-skid trace status or unknown event")
            require(native["sequence"] == self.sequence,
                    "Runner stop-skid missing native receipt")

            if self.start_result is not None and self.recorder is None:
                response = self._policy_response()
                require(snapshot["frame"] == self.policy_frame
                        and actor.get("motionKind") == "WALK"
                        and actor.get("motionPhase") == "MOVING"
                        and actor.get("motionDuration") == 8
                        and actor.get("motionElapsed") == 0
                        and actor.get("reservationId", 0) > 0
                        and actor.get("movementPolicy", {}).get("action") == 0
                        and actor.get("movementPolicy", {}).get("ticks") == 0
                        and actor.get("movementPolicy", {}).get("pendingSkid") == 1
                        and actor.get("movementPolicy", {}).get("skid") == 2
                        and actor.get("movementPolicy", {}).get("turn") == WALK_DIRECTION_NONE
                        and actor.get("engineObject", {}).get("facing") == response[17],
                        "Runner stop skid did not start as normal Walk motion")
                self.recorder = MotionRecorder()

            if self.recorder is not None:
                self.recorder.observe(snapshot["frame"], actor, actor["engineObject"])
                require(not self.recorder.failures,
                        "Runner stop-skid motion: " + str(self.recorder.failures))
                require(len(self.recorder.completed) <= 2,
                        "Runner stop skid produced extra measured motion")
                if len(self.recorder.completed) == 2:
                    require(self.recorder.current is None,
                            "Runner stop-skid terminal motion is still active")
                    self.motions = deepcopy(self.recorder.completed)
                    self.motion = self.motions[-1]
                    self._check_motion(actor)
            self.last = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def _check_motion(self, actor):
        require(self.continuation is not None and len(self.motions) == 2
                and self.motions[0]["startFrame"] == self.policy_frame
                and self.motions[1]["startFrame"] == self.continuation_frame,
                "Runner stop-skid continuation lacks accepted start")
        for index, motion in enumerate(self.motions):
            if index:
                previous = self.motions[index - 1]
                require(motion["origin"] == previous["target"]
                        and motion["commitBefore"] == previous["commitAfter"]
                        and previous["finishFrame"] <= motion["startFrame"],
                        "Runner stop-skid continuation skipped a tile or commit")
            self._check_tile(motion)
        require(actor.get("logical") == dict(zip(("x", "y"), self.motion["target"]))
                and actor.get("motionKind") == "NONE"
                and actor.get("motionPhase") == "IDLE"
                and actor.get("reservationId") == 0,
                "Runner stop-skid terminal control differs")

    def _check_tile(self, motion):
        require(motion["kind"] == "WALK" and motion["duration"] == 8
                and complete_travel(motion),
                "Runner stop skid lacks one complete eight-frame Walk")
        delta = [target - origin
                 for origin, target in zip(motion["origin"], motion["target"])]
        require(sum(abs(value) for value in delta) == 1,
                "Runner stop skid did not move exactly one tile")
        direction_delta = {
            0: [0, -1], 1: [0, 1], 2: [-1, 0], 3: [1, 0],
        }[self._policy_response()[17]]
        require(delta == direction_delta,
                "Runner stop-skid tile differs from its retained direction")
        require([sample["elapsed"] for sample in motion["samples"]] == list(range(8))
                and motion.get("travelEnd", {}).get("elapsed") == 8,
                "Runner stop-skid elapsed schedule differs")
        require(motion["commitAfter"] == ((motion["commitBefore"] + 1) & 0xFFFFFFFF),
                "Runner stop-skid tile commit differs")

        start = [event for event in self.traces
                 if event["frame"] == motion["startFrame"]
                 and event["data"].get("event") == "MOTION_STARTED"
                 and (event["data"].get("valueA"), event["data"].get("valueB")) == (1, 8)]
        require(len(start) == 1, "Runner stop skid lacks its native motion start")
        start_sequence = start[0]["data"]["sequence"]
        wanted = (
            ("LOGICAL_COMMIT", motion["commitFrame"], motion["commitAfter"], 1),
            ("MOTION_FINISHED", motion["finishFrame"], motion["commitAfter"], 1),
            ("CONTROL_RETURNED", motion["finishFrame"], 0, motion["commitAfter"]),
        )
        sequences = [start_sequence]
        for name, frame, value_a, value_b in wanted:
            rows = [event for event in self.traces
                    if event["frame"] == frame
                    and event["data"].get("sequence", 0) > start_sequence
                    and event["data"].get("event") == name]
            require(len(rows) == 1 and rows[0]["frame"] == frame
                    and rows[0]["data"].get("reason") == "OK"
                    and (rows[0]["data"].get("valueA"), rows[0]["data"].get("valueB"))
                        == (value_a, value_b),
                    "Runner stop skid lacks native " + name)
            sequences.append(rows[0]["data"]["sequence"])
        require(sequences == sorted(set(sequences)),
                "Runner stop-skid lifecycle order differs")

    @property
    def ready(self):
        return self.motion is not None and not self.failures

    @property
    def closed(self):
        return self.ready

    def finish(self):
        if not self.ready and not self.failures:
            self.failures.append("Runner stop skid was not completed")
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
            "completeMotions": (0 if self.recorder is None
                                else len(self.recorder.completed)),
            "subject": deepcopy(self.subject),
            "initial": deepcopy(self.initial),
            "terminal": deepcopy(self.last),
            "policyFrame": self.policy_frame,
            "stopSpeed": self.stop_speed,
            "policyInput": deepcopy(self.policy_input),
            "startResult": deepcopy(self.start_result),
            "continuation": deepcopy(self.continuation),
            "continuationFrame": self.continuation_frame,
            "motion": deepcopy(self.motion),
            "motions": deepcopy(self.motions),
            "traces": deepcopy(self.traces),
        }
