"""Current Follower identity, signed ranges and Walks across a field rebind."""
from copy import deepcopy

from tools.overworld.devtools_movement_predicates import player_settled_at
from tools.overworld.devtools_wild_transition_measurement import (
    LIFECYCLE, WildTransitionMeasurement, full_event_handle, require,
)
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel


KIND = "follower-transition-rebind-v1"
REQUIREMENT = "legacy.follower-transition"
ROUTE_START = {"map": 33, "x": 585, "z": 406, "facing": 1}


class FollowerTransitionMeasurement(WildTransitionMeasurement):
    def __init__(self, test, *, max_frames):
        super().__init__(
            test, max_frames=max_frames, kind=KIND, requirement=REQUIREMENT,
            subject_id="cyndaquil", species=155, role="FOLLOWER", acquire="existing",
        )
        self.route_start = None
        self.setup_commands = []
        self.post_lifecycle = []
        self.post_recorder = MotionRecorder()
        self.post_motion = None
        self.restored_ranges = False
        self._observing_frame = None

    @staticmethod
    def _ranges(actor):
        engine = actor.get("engineObject", {})
        require(all(type(engine.get(axis)) is int and engine[axis] == -1
                    for axis in ("x_range", "y_range")),
                "Follower transition native signed ranges are not -1/-1")

    def _bind(self, snapshot, receipt):
        require(self.route_start is not None and self.setup_commands == ["teleport", "party", "spawn"]
                and snapshot.get("context") == self.route_start["context"]
                and player_settled_at(snapshot, 33, 585, 406),
                "Follower transition binding lacks the prepared Route29 start")
        super()._bind(snapshot, receipt)
        self._ranges(self._current_actor(snapshot))
        self.setup_commands.append("bind")

    def observe_record(self, record, *, frame_callback=None, full_report=True):
        if self.failures or self._closed:
            return self.result()
        try:
            command = record.get("command") if isinstance(record, dict) else None
            if command == "teleport":
                action = self.actions.get((record.get("phase"), record.get("action")))
                receipt, snapshot = record.get("receipt", {}), record.get("snapshot", {})
                value, boundary = receipt.get("value", {}), receipt.get("setupBoundary", {})
                require(self.latest is not None and self.subject is None and not self.setup_commands
                        and record.get("phase") == "setup" and record.get("action") == "route-start"
                        and action is not None and action["op"] == "teleport" and action["args"] == ROUTE_START
                        and receipt.get("preparedOnly") is True and receipt.get("snapshot") == snapshot,
                        "Follower transition permits only its unbound Route29 setup warp")
                require({key: value.get(key) for key in ("mapId", "x", "z", "facing")}
                        == {"mapId": 33, "x": 585, "z": 406, "facing": 1}
                        and value.get("environmentOwnership") == "transferred-to-native-Task_ScriptWarp"
                        and value.get("environmentBytes") == 24
                        and value.get("constructor", {}).get("boundary") == "native-task-factory-return",
                        "Follower transition Route29 native warp receipt differs")
                require(snapshot.get("fieldAvailable") is True
                        and snapshot.get("observationBoundary") == "main-task-queue-completion"
                        and type(snapshot.get("frame")) is int and snapshot["frame"] > self.latest["frame"]
                        and type(snapshot.get("nativeCycle")) is int
                        and snapshot["nativeCycle"] > self.latest["nativeCycle"]
                        and all(type(snapshot.get("context", {}).get(key)) is int
                                and 1 <= snapshot["context"][key] <= 65535
                                for key in ("fieldEpoch", "mapGeneration"))
                        and type(snapshot.get("fieldControl", {}).get("fieldPointer")) is int
                        and snapshot["fieldControl"]["fieldPointer"] > 0
                        and player_settled_at(snapshot, 33, 585, 406)
                        and snapshot["player"].get("facing") == 1
                        and boundary.get("eventsDrained") is True
                        and boundary.get("frame") == snapshot["frame"]
                        and boundary.get("nativeCycle") == snapshot["nativeCycle"]
                        and boundary.get("endpointNativeCycle") == snapshot["nativeCycle"],
                        "Follower transition Route29 setup is not a current completed native boundary")
                traces = boundary.get("traceSequences")
                require(isinstance(traces, dict) and all(
                    isinstance(stream, str) and stream.isdecimal() and str(int(stream)) == stream
                    and 0 < int(stream) <= 1000000 and type(sequence) is int
                    and 0 <= sequence <= 0xFFFFFFFF for stream, sequence in traces.items()),
                    "Follower transition setup trace watermark differs")
                self.trace_sequences = {int(stream): sequence for stream, sequence in traces.items()}
                self.route_start = deepcopy(snapshot)
                self.setup_commands.append(command)
                self.latest = deepcopy(snapshot)
                if frame_callback:
                    frame_callback(self.latest, (), self)
                return self.result()
            if command in ("party", "spawn"):
                require(self.setup_commands == (["teleport"] if command == "party"
                        else ["teleport", "party"]),
                        "Follower transition prepared setup is missing or reordered")
                result = super().observe_record(record, frame_callback=frame_callback, full_report=full_report)
                if not self.failures:
                    self.setup_commands.append(command)
                return self.result()
            return super().observe_record(record, frame_callback=frame_callback, full_report=full_report)
        except (ValueError, KeyError, TypeError, IndexError) as error:
            self._fail(error)
        return self.result()

    def _event(self, event):
        super()._event(event)
        if event.get("kind") != "native" or self.rebound_handle is None or len(self.post_lifecycle) == 4:
            return
        data = event.get("data", {})
        if full_event_handle(data) != self.rebound_handle or data.get("event") not in LIFECYCLE:
            return
        name = data["event"]
        if not self.post_lifecycle and name != LIFECYCLE[0]:
            return  # An old accepted motion may finish immediately after rebind.
        require(event.get("frame") == self._observing_frame and data.get("reason") == "OK"
                and name == LIFECYCLE[len(self.post_lifecycle)]
                and (self.post_lifecycle or data.get("valueA") == 1)
                and type(data.get("sequence")) is int
                and data["sequence"] > self.transition_events[-1]["data"]["sequence"]
                and (not self.post_lifecycle
                     or data["sequence"] > self.post_lifecycle[-1]["data"]["sequence"]),
                "Follower transition fresh rebound Walk lifecycle differs")
        self.post_lifecycle.append(deepcopy(event))

    def observe(self, snapshot, events):
        if self.failures or self._closed:
            return self.result()
        self._observing_frame = snapshot.get("frame") if isinstance(snapshot, dict) else None
        super().observe(snapshot, events)
        try:
            if not self.failures and self.map_changes:
                actor = self._current_actor(snapshot)
                self._ranges(actor)
                self.restored_ranges = True
                if self.post_lifecycle and self.post_motion is None:
                    if len(self.post_lifecycle) == 1 and self.post_lifecycle[0]["frame"] == snapshot["frame"]:
                        require(actor.get("motionKind") == "WALK" and actor.get("motionPhase") == "MOVING"
                                and actor.get("motionElapsed") in (0, 1)
                                and type(actor.get("reservationId")) is int and actor["reservationId"] > 0
                                and abs(actor["target"]["x"] - actor["origin"]["x"])
                                  + abs(actor["target"]["y"] - actor["origin"]["y"]) == 1,
                                "Follower transition lacks a fresh accepted one-tile rebound Walk")
                    self.post_recorder.observe(snapshot["frame"], actor, actor["engineObject"])
                    require(not self.post_recorder.failures,
                            "Follower transition rebound Walk travel or commit differs: "
                            + repr(self.post_recorder.failures))
                    if self.post_recorder.completed:
                        motion = self.post_recorder.completed[0]
                        require(motion["kind"] == "WALK" and motion["handle"] == self.rebound_handle
                                and complete_travel(motion) and len(self.post_lifecycle) == 4,
                                "Follower transition lacks full rebound Walk travel and native control return")
                        self.post_motion = deepcopy(motion)
        except (ValueError, KeyError, TypeError, IndexError, StopIteration) as error:
            self._fail(error)
        finally:
            self._observing_frame = None
        return self.result()

    @property
    def ready(self):
        return super().ready and self.restored_ranges and self.post_motion is not None

    def finish(self):
        if not super().ready:
            return super().finish()
        if not self.ready and not self.failures:
            self._fail("Follower transition lacks signed -1/-1 and a fresh committed rebound Walk, or did not restore player control")
        self._closed = True
        return self.result()

    def result(self):
        return {**super().result(), "routeStart": deepcopy(self.route_start),
                "restoredRanges": self.restored_ranges,
                "postRebindLifecycle": deepcopy(self.post_lifecycle),
                "postRebindMotion": deepcopy(self.post_motion)}
