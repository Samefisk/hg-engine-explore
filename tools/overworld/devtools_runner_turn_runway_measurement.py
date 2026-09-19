"""One natural Wild Runner turn after its planned straight runway blocks."""

from copy import deepcopy

from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel, live_identity


KIND = "runner-turn-runway-v1"
REQUIREMENT = "current.runner-turn-runway"
IDENTITY = (
    "handle", "species", "form", "level", "role", "subjectIdentity",
    "authorityGeneration", "engineAnchorGeneration", "presentationGeneration",
    "behaviorFingerprint", "matchedLayerMask",
)
WALK_POLICY_INPUT = 1
WALK_POLICY_START_RESULT = 2
START_ACCEPTED = 1
START_BLOCKED = 2
DECISION_IGNORED = 0
DECISION_CONSUMED = 1
DECISION_TRY_STEP = 2
STRAIGHT_FLAGS = 0x81
TURN_FLAGS = 0x83
POST_SKID_FLAGS = 0xA1
RUNNER_LANE_HEX = (
    "0202070a03140a08200200030100020f64000000010800091e000001050608070100"
    "ff03040000000401000102040f10646401040f00000000010000040501010500506400c10001"
)


def require(value, reason):
    if not value:
        raise ValueError(reason)


def decode_call(value):
    raw = bytes.fromhex(value)
    require(len(raw) == 28 and raw[0:4] == b"\x01\x00\x1c\x00",
            "Runner turn-runway Walk-policy ABI differs")
    return raw


def same_public_subject(value, actor):
    return value.get("handle") == actor.get("handle") and all(
        value.get(key) == actor.get(key) for key in IDENTITY if key != "handle")


def direction_delta(direction):
    return {0: [0, -1], 1: [0, 1], 2: [-1, 0], 3: [1, 0]}[direction]


class RunnerTurnRunwayMeasurement:
    def __init__(self, max_frames=300):
        require(type(max_frames) is int and 1 <= max_frames <= 600,
                "invalid Runner turn-runway frame bound")
        self.max_frames = max_frames
        self.initial = self.last = self.actor = self.subject = None
        self.frames = self.sequence = 0
        self.streams = {}
        self.failures = []
        self.traces = []
        self.straight_input = self.blocked_result = None
        self.turn_input = self.turn_result = self.post_skid_result = None
        self.policy_frame = self.old_direction = self.turn_direction = None
        self.recorder = None
        self.motions = self.lifecycle = None

    def arm(self, subject, snapshot, trace_sequences=None):
        require(self.initial is None, "Runner turn-runway measurement already armed")
        selected = select_current_actor(snapshot, subject)
        actor = next(item for item in snapshot["actors"] if item["handle"] == selected["handle"])
        require(live_identity(actor, actor.get("sourceIdentity", {}),
                              actor.get("engineIdentity", {}), species=234, role="WILD",
                              current_epoch=snapshot["context"]["fieldEpoch"])
                and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True
                and actor.get("inputOwnership") == 0
                and actor.get("motionKind") == "NONE"
                and actor.get("motionPhase") == "IDLE"
                and actor.get("reservationId") == 0
                and actor.get("behaviorFingerprint") == 2279901407
                and actor.get("matchedLayerMask") == 98312,
                "Runner turn runway requires one idle live Runner Stantler")
        self.subject, self.actor = deepcopy(selected), deepcopy(actor)
        self.initial = self.last = deepcopy(snapshot)
        self.sequence = snapshot["nativeObservation"]["sequence"]
        self.streams = dict(trace_sequences or {})

    def _actor(self, snapshot):
        selected = select_current_actor(snapshot, self.subject)
        actor = next(item for item in snapshot["actors"] if item["handle"] == selected["handle"])
        require(all(actor.get(key) == self.actor.get(key) for key in IDENTITY)
                and actor.get("inputOwnership") == 0
                and actor.get("sourceIdentity") == self.actor.get("sourceIdentity")
                and engine_binding_identity(actor.get("engineIdentity"))
                    == engine_binding_identity(self.actor.get("engineIdentity"))
                and snapshot["context"] == self.initial["context"],
                "Runner turn-runway identity or profile changed")
        return actor

    def _walk_policy(self, event):
        data = event["data"]
        before, after = data.get("publicSubject", {}), data.get("publicSubjectAfter", {})
        if data.get("slot") != self.actor["handle"]["slot"] \
                or not same_public_subject(before, self.actor) \
                or not same_public_subject(after, self.actor):
            return
        request, response = decode_call(data["requestHex"]), decode_call(data["responseHex"])
        operation = data.get("operation")
        require(request[8] == response[8] == self.actor["handle"]["slot"]
                and request[9] == response[9] == operation,
                "Runner turn-runway Walk-policy owner differs")
        if operation == WALK_POLICY_INPUT:
            require(data.get("laneHex") == RUNNER_LANE_HEX,
                    "Runner turn-runway profile lane differs")
            if self.turn_result is not None:
                return
            if response[16] == DECISION_TRY_STEP and response[10] in range(4) \
                    and response[11] == 0 and response[17] == response[18] == response[10] \
                    and response[19] == 5 and response[20] == STRAIGHT_FLAGS \
                    and response[22] == response[23] == 0 \
                    and response[24] == 4 and response[25] == 1:
                self.straight_input, self.blocked_result = deepcopy(data), None
                self.policy_frame, self.old_direction = event["frame"], response[10]
                return
            if self.blocked_result is not None and event["frame"] == self.policy_frame \
                    and response[16] == DECISION_TRY_STEP and response[10] in range(4) \
                    and response[10] != self.old_direction:
                old_delta, new_delta = direction_delta(self.old_direction), direction_delta(response[10])
                require(sum(a * b for a, b in zip(old_delta, new_delta)) == 0
                        and response[11] == 1 and response[17] == self.old_direction
                        and response[18] == response[10] and response[19] == 8
                        and response[20] == TURN_FLAGS and response[22] == response[23] == 0
                        and response[24] == 5 and response[25] == 1,
                        "Runner turn-runway alternate turn proposal differs")
                self.turn_input, self.turn_direction = deepcopy(data), response[10]
                return
        if operation != WALK_POLICY_START_RESULT:
            return
        if self.turn_result is not None and response[20] == POST_SKID_FLAGS:
            require(request[15] == response[15] == START_ACCEPTED
                    and request[16] == DECISION_TRY_STEP and response[16] == DECISION_CONSUMED
                    and request[10] == response[10] == self.old_direction
                    and request[11] == response[11] == 0
                    and request[17] == response[17] == self.turn_direction
                    and request[18] == response[18] == self.turn_direction
                    and request[19] == response[19] == 6
                    and request[22] == response[22] == request[23] == response[23] == 0
                    and request[24] == response[24] == 5
                    and request[25] == response[25] == 1,
                    "Runner turn-runway recovery start differs")
            self.post_skid_result = deepcopy(data)
            return
        if self.straight_input is not None and self.blocked_result is None \
                and event["frame"] == self.policy_frame and request[20] == STRAIGHT_FLAGS:
            if request[15] == response[15] == START_BLOCKED \
                    and request[16] == DECISION_TRY_STEP and response[16] == DECISION_IGNORED:
                self.blocked_result = deepcopy(data)
            return
        if self.turn_input is not None and self.turn_result is None \
                and event["frame"] == self.policy_frame and request[20] == TURN_FLAGS:
            require(request[15] == response[15] == START_ACCEPTED
                    and request[16] == DECISION_TRY_STEP and response[16] == DECISION_CONSUMED,
                    "Runner turn-runway alternate turn was not accepted")
            self.turn_result = deepcopy(data)

    def observe(self, snapshot, events):
        if self.failures:
            return self.result()
        try:
            require(self.initial is not None and not self.ready,
                    "Runner turn-runway window is not open")
            actor = self._actor(snapshot)
            require(snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot["frame"] == self.last["frame"] + 1
                    and snapshot["nativeCycle"] >= self.last["nativeCycle"],
                    "Runner turn-runway completed clock gap")
            selector = snapshot.get("selector", {})
            require(all(type(selector.get(key)) is int and selector[key] == 0
                        for key in ("heldKeys", "newKeys", "physicalPressed", "simulatedKeys")),
                    "Runner turn runway requires neutral input")
            native = snapshot["nativeObservation"]
            require(native.get("installedBeforeBoot") is True
                    and native.get("coverageComplete") is True and native.get("error") is None
                    and all(native.get(key) == 0 for key in ("eventsDropped", "profilesEvicted")),
                    "Runner turn-runway native coverage incomplete")
            self.frames += 1
            require(self.frames <= self.max_frames, "Runner turn-runway frame bound exceeded")
            active = [item for item in snapshot["actors"] if item.get("active") is True]
            reservations = [item.get("reservationId") for item in active if item.get("reservationId")]
            require(len(reservations) == len(set(reservations)),
                    "Runner turn-runway target reservation is shared")

            for event in events:
                data = event.get("data", {})
                require(event.get("frame") == snapshot["frame"],
                        "Runner turn-runway event frame differs")
                if event.get("kind") == "native-observation":
                    require(data.get("sequence") == self.sequence + 1,
                            "Runner turn-runway native receipt gap")
                    self.sequence += 1
                    if data.get("observation") == "walk-policy":
                        self._walk_policy(event)
                elif event.get("kind") == "native":
                    stream, sequence = data.get("traceStream"), data.get("sequence")
                    require(type(stream) is int and stream > 0 and type(sequence) is int
                            and sequence == self.streams.get(stream, 0) + 1,
                            "Runner turn-runway semantic sequence gap")
                    self.streams[stream] = sequence
                    if data.get("actorHandle") == self.actor["handle"]["value"]:
                        require(data.get("event") not in ("MOTION_CANCELED", "CONTEXT_CHANGED",
                                                          "ACTOR_REBOUND", "CONTROL_REBOUND"),
                                "Runner turn-runway motion canceled or rebound")
                        self.traces.append(deepcopy(event))
                elif event.get("kind") == "trace-status" and data.get("code") == "ring-overwrite":
                    require(data.get("unreadEventsLost") == 0 and data.get("coverageComplete", True) is True,
                            "Runner turn-runway trace lost unread events")
                else:
                    raise ValueError("Runner turn-runway trace status or unknown event")
            require(native["sequence"] == self.sequence,
                    "Runner turn-runway missing native receipt")

            if self.turn_result is not None and self.recorder is None:
                response = decode_call(self.turn_input["responseHex"])
                require(snapshot["frame"] == self.policy_frame
                        and actor.get("motionKind") == "WALK" and actor.get("motionPhase") == "MOVING"
                        and actor.get("motionDuration") == 8 and actor.get("motionElapsed") == 0
                        and actor.get("movementPolicy", {}).get("direction") == self.old_direction
                        and actor.get("movementPolicy", {}).get("speed") == 8
                        and actor.get("movementPolicy", {}).get("skid") == 1
                        and actor.get("movementPolicy", {}).get("turn") == self.turn_direction
                        and actor.get("movementPolicy", {}).get("resume") == 5
                        and actor.get("movementPolicy", {}).get("action") == 0
                        and actor.get("movementPolicy", {}).get("ticks") == 0
                        and actor.get("movementPolicy", {}).get("pendingSkid") == 1
                        and actor.get("engineObject", {}).get("facing") == response[18],
                        "Runner turn-runway skid did not start")
                self.recorder = MotionRecorder()
            if self.recorder is not None:
                self.recorder.observe(snapshot["frame"], actor, actor["engineObject"])
                require(not self.recorder.failures,
                        "Runner turn-runway motion: " + str(self.recorder.failures))
                if len(self.recorder.completed) >= 2:
                    require(self.post_skid_result is not None,
                            "Runner turn-runway recovery lacks accepted start")
                    self.motions = deepcopy(self.recorder.completed[:2])
                    self._check_motions(actor)
            if self.turn_result is None and self.policy_frame is not None \
                    and snapshot["frame"] > self.policy_frame:
                self.straight_input = self.blocked_result = self.turn_input = None
                self.policy_frame = self.old_direction = self.turn_direction = None
            self.last = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def _check_motions(self, actor):
        first, second = self.motions
        require([motion["duration"] for motion in self.motions] == [8, 6]
                and all(motion["kind"] == "WALK" and complete_travel(motion)
                        for motion in self.motions)
                and first["target"] == second["origin"]
                and [target - origin for origin, target in zip(first["origin"], first["target"])]
                    == direction_delta(self.old_direction)
                and [target - origin for origin, target in zip(second["origin"], second["target"])]
                    == direction_delta(self.turn_direction),
                "Runner turn-runway motion pair differs")
        require([sample["elapsed"] for sample in first["samples"]] == list(range(8))
                and [sample["elapsed"] for sample in second["samples"]] == list(range(6))
                and all(motion["commitAfter"] == ((motion["commitBefore"] + 1) & 0xFFFFFFFF)
                        for motion in self.motions)
                and actor.get("logical") == dict(zip(("x", "y"), second["target"])),
                "Runner turn-runway commits or elapsed schedules differ")
        lifecycle = []
        for motion in self.motions:
            starts = [event for event in self.traces
                      if event["frame"] == motion["startFrame"]
                      and event["data"].get("event") == "MOTION_STARTED"
                      and (event["data"].get("valueA"), event["data"].get("valueB"))
                          == (1, motion["duration"])]
            require(len(starts) == 1, "Runner turn-runway lacks native motion start")
            lifecycle.append(starts[0])
            for name, frame, values in (
                    ("LOGICAL_COMMIT", motion["commitFrame"], (motion["commitAfter"], 1)),
                    ("MOTION_FINISHED", motion["finishFrame"], (motion["commitAfter"], 1)),
                    ("CONTROL_RETURNED", motion["finishFrame"], (0, motion["commitAfter"]))):
                rows = [event for event in self.traces if event["frame"] == frame
                        and event["data"].get("event") == name
                        and (event["data"].get("valueA"), event["data"].get("valueB")) == values]
                require(len(rows) == 1, "Runner turn-runway lacks native " + name)
                lifecycle.append(rows[0])
        sequences = [event["data"]["sequence"] for event in lifecycle]
        require(sequences == sorted(sequences) and len(sequences) == len(set(sequences)),
                "Runner turn-runway lifecycle order differs")
        self.lifecycle = lifecycle

    @property
    def ready(self):
        return self.motions is not None and self.lifecycle is not None and not self.failures

    @property
    def closed(self):
        return self.ready

    def finish(self):
        if not self.ready and not self.failures:
            self.failures.append("Runner turn runway was not completed")
        return self.result()

    def result(self):
        return {
            "kind": KIND, "requirements": [REQUIREMENT], "passed": self.ready,
            "ready": self.ready, "closed": self.closed, "acceptedProof": False,
            "failures": list(self.failures), "frames": self.frames,
            "completeMotions": 0 if self.recorder is None else len(self.recorder.completed),
            "subject": deepcopy(self.subject), "initial": deepcopy(self.initial),
            "terminal": deepcopy(self.last), "policyFrame": self.policy_frame,
            "oldDirection": self.old_direction, "turnDirection": self.turn_direction,
            "profileLaneHex": RUNNER_LANE_HEX,
            "straightInput": deepcopy(self.straight_input),
            "blockedResult": deepcopy(self.blocked_result),
            "turnInput": deepcopy(self.turn_input), "turnResult": deepcopy(self.turn_result),
            "postSkidResult": deepcopy(self.post_skid_result),
            "motions": deepcopy(self.motions), "lifecycle": deepcopy(self.lifecycle),
        }
