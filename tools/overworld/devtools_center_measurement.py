"""Normal saved Center doorway lifecycle; no follower/cadence claim."""
from copy import deepcopy

from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement
from tools.overworld.devtools_records import validate_field_absence
from tools.overworld.devtools_movement_predicates import player_settled_at, check_movement_predicate


class CenterEntryExitMeasurement:
    # Use the same exact, unbound, action-scoped doorway absence rules as
    # cadence. This tracker has no actor acquisition or travel measurement.
    _setup_transition = UnmountedCadenceMeasurement._setup_transition

    def __init__(self, test, *, max_frames, setup_transitions):
        if test.get("mode") != "normal" or test.get("fixture", {}).get("save") != "test.sav" \
                or test.get("subjects") != []:
            raise ValueError("Center regression requires normal test.sav and no actor subjects")
        self.actions = {(phase, action["id"]): deepcopy(action)
                        for phase, name in (("setup", "setup"), ("observe", "actions"))
                        for action in test[name]}
        if any(a["op"] not in ("assert", "step", "wait") or a.get("skipIf")
               or set(a["args"].get("keys", [])) - {"UP", "DOWN", "LEFT", "RIGHT"}
               for a in self.actions.values()):
            raise ValueError("Center regression accepts only normal cardinal input and reads")
        if not isinstance(setup_transitions, list) or len(setup_transitions) != 2:
            raise ValueError("Center regression needs exactly entry and exit transitions")
        self.setup_transitions = {}
        for index, spec in enumerate(setup_transitions):
            if not isinstance(spec, dict) or set(spec) - {"action", "departure", "arrival", "maxFrames", "reveal"} \
                    or not {"action", "departure", "arrival", "maxFrames"} <= set(spec):
                raise ValueError("Center transition shape differs")
            action = self.actions.get(("setup", spec["action"]))
            if action is None or action["op"] != "wait" or spec["action"] in self.setup_transitions:
                raise ValueError("Center transition must name its distinct neutral arrival wait")
            for name in ("departure", "arrival"):
                point = spec[name]
                if not isinstance(point, dict) or set(point) != {"map", "x", "z"} \
                        or any(type(v) is not int or not 0 <= v <= 32767 for v in point.values()):
                    raise ValueError("Center transition needs exact map/x/z")
            if (spec["departure"]["map"], spec["arrival"]["map"]) != ((67, 69) if index == 0 else (69, 67)) \
                    or type(spec["maxFrames"]) is not int or not 1 <= spec["maxFrames"] <= 240:
                raise ValueError("Center transition maps or bound differ")
            if "reveal" in spec and spec["reveal"] != {"map": spec["arrival"]["map"],
                    "x": spec["arrival"]["x"], "z": spec["arrival"]["z"] - 1}:
                raise ValueError("Center reveal must precede the stock DOWN arrival")
            self.setup_transitions[spec["action"]] = deepcopy(spec)
        self.max_frames, self.frames = max_frames, 0
        self.subject = None
        self.pending_transition = None
        self.completed_setup_transitions = []
        self.absent_setup_frames = 0
        self.latest = None
        self.exit_steps = None
        self.failures = []
        self.native_cycles = self.cpu_ns = 0
        self.ready = self.closed = False

    def observe_record(self, record, *, frame_callback=None):
        if self.closed or self.failures:
            return self.result()
        try:
            initial = "initialSnapshot" in record
            if initial and self.latest is not None:
                raise ValueError("duplicate initial Center snapshot")
            from tools.overworld.devtools_raw_chunk import validate_raw_chunk
            rows = [(record["initialSnapshot"], (), ())] if initial else validate_raw_chunk(record, self.latest)
            if self.frames + (0 if initial else len(rows)) > self.max_frames:
                raise ValueError("Center frame budget exceeded")
            for snapshot, sample_events, finished_intervals in rows:
                if snapshot.get("prepared") is not False or type(snapshot.get("fieldAvailable")) is not bool \
                        or snapshot.get("observationBoundary") != "main-task-queue-completion" \
                        or type(snapshot.get("frame")) is not int or type(snapshot.get("nativeCycle")) is not int:
                    raise ValueError("Center snapshot is not normal completed memory data")
                if self.latest is not None and (snapshot["frame"] != self.latest["frame"] + 1
                        or snapshot["nativeCycle"] < self.latest["nativeCycle"]):
                    raise ValueError("Center clock is missing, duplicated or stale")
                native = snapshot.get("nativeObservation", {})
                if native.get("coverageComplete") is not True or native.get("installedBeforeBoot") is not True \
                        or any(native.get(key) not in (0, None) for key in ("eventsDropped", "error")) \
                        or native.get("pendingPlayerSteps") != 0 or native.get("pendingUnframedEvents") != 0 \
                        or native.get("playerStepFrame") != snapshot["frame"] or snapshot.get("observationErrors", []):
                    raise ValueError("Center native observation is incomplete")
                if self.latest is not None and any(snapshot.get(key) != self.latest.get(key)
                        for key in ("romSha256", "sourceSaveSha256")):
                    raise ValueError("Center ROM or save identity changed")
                if snapshot["fieldAvailable"] is False:
                    validate_field_absence(snapshot)
                    if initial:
                        raise ValueError("Center initial field absent")
                if not initial:
                    self.frames += 1
                    if self.frames > self.max_frames:
                        raise ValueError("Center frame budget exceeded")
                    phase = record.get("phase")
                    action = self.actions.get((phase, record.get("action")))
                    if action is None:
                        raise ValueError("Center action is not authored")
                    self._setup_transition(snapshot, phase, action, [])
                    order = list(self.setup_transitions)
                    if [r["action"] for r in self.completed_setup_transitions] != order[:len(self.completed_setup_transitions)]:
                        raise ValueError("Center transitions are repeated or reordered")
                    if len(self.completed_setup_transitions) == 2 and self.exit_steps is None:
                        self.exit_steps = snapshot["nativeObservation"]["playerStepCount"]
                        check_movement_predicate({"kind": "player-step-count", "operator": "eq",
                                                  "value": self.exit_steps}, snapshot)
                    if phase == "observe" and len(self.completed_setup_transitions) == 2:
                        arrival = list(self.setup_transitions.values())[-1]["arrival"]
                        self.ready = player_settled_at(snapshot, arrival["map"], arrival["x"], arrival["z"] + 1) \
                            and check_movement_predicate({"kind": "player-step-count", "operator": "eq",
                                                          "value": self.exit_steps + 1}, snapshot) \
                            and type(snapshot.get("fieldControl", {}).get("actorTransitionPhase")) is int \
                            and snapshot["fieldControl"]["actorTransitionPhase"] in (0, 4)
                self.latest = deepcopy(snapshot)
                self.native_cycles += len(finished_intervals)
                self.cpu_ns += sum(interval["cpuNs"] for interval in finished_intervals)
                if frame_callback:
                    frame_callback(self.latest, sample_events, self)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            self.failures.append({"code": "center-lifecycle-invalid", "detail": str(error)})
        return self.result()

    def result(self):
        return deepcopy({"ready": self.ready and not self.failures,
                         "passed": self.closed and self.ready and not self.failures,
                         "subject": None, "failures": self.failures,
                         "nativeCycles": self.native_cycles, "cpuNs": self.cpu_ns,
                         "setupTransitions": self.completed_setup_transitions,
                         "absentSetupFrames": self.absent_setup_frames, "sampledFrames": self.frames})

    def finish(self):
        if not self.closed and (not self.ready or self.pending_transition):
            self.failures.append({"code": "center-exit-control-not-restored"})
        self.closed = True
        return self.result()
