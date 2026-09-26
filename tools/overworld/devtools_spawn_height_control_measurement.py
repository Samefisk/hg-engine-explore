"""Calibrate the shared spawn-height reader against one restored native read.

The current natural Appear Hop checker must reject only the observed Y error.
This module owns no memory writes, emulator, setup, or accepted proof.
"""
from copy import deepcopy

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_spawn_surface_measurement import (
    EXPECTED_HEIGHT_REASON,
    check_natural_appear_hop_surface,
)
from tools.overworld.normal_play_observer import live_identity


HEIGHT_ENVELOPE = frozenset(("observation", "sequence", "setupMode", "entryActorFrame",
                            "entryNativeCycle", "returnActorFrame", "returnNativeCycle",
                            "guestTiming"))
EXPECTED_REASON = EXPECTED_HEIGHT_REASON
JUMP_COMMANDS = frozenset((48, 49, 50, 51))
DELAY_COMMAND = 62
RESTORE_COMMAND = 74
IDLE_COMMAND = 255


class NaturalAppearHopHeightMeasurement:
    """One natural Wild Mareep from native spawn through Appear Hop release."""

    def __init__(self, schema, source_sha256, *, max_frames, authored_profiles):
        if schema.get("compactSize") != 72 or not isinstance(source_sha256, str) \
                or len(source_sha256) != 64 or not isinstance(authored_profiles, dict):
            raise ValueError("current profile inputs are missing")
        if type(max_frames) is not int or not 1 <= max_frames <= 60001:
            raise ValueError("invalid natural Appear Hop frame bound")
        self.max_frames = max_frames
        self.frames = 0
        self.first_handles = None
        self.required_height = None
        self.required_subject = None
        self.subject = self.spawn = self.initial = self.terminal = self.last = None
        self.stage = 0
        self.saw_jump = False
        self.saw_arc = False
        self.samples = []
        self.surface = None
        self.failures = []
        self.closed = False

    def _acquire(self, snapshot, events):
        candidates = []
        for event in events:
            data = event.get("data", {})
            if event.get("kind") == "native-observation" \
                    and data.get("observation") == "spawn-prepared" \
                    and data.get("returnValue") == 1 \
                    and data.get("setupMode") == "normal" \
                    and data.get("preparedEncounter", {}).get("species") == 179:
                candidates.append(data)
        if self.required_height is not None:
            clean = self.required_height
            candidates = [spawn for spawn in candidates
                          if {key: value for key, value in
                              spawn.get("initialLandingHeight", {}).items()
                              if key not in HEIGHT_ENVELOPE} == clean]
        if self.required_subject is not None:
            candidates = [spawn for spawn in candidates
                          if spawn.get("publicSubject", {}).get("handle")
                             == self.required_subject.get("handle")]
        if not candidates:
            return None
        if len(candidates) != 1 or self.spawn is not None:
            raise ValueError("natural Mareep spawn receipt is duplicated")
        spawn = candidates[0]
        subject = spawn.get("publicSubject", {})
        handle = subject.get("handle")
        if subject.get("species") != 179 or subject.get("role") != "WILD" \
                or not isinstance(handle, dict) \
                or tuple(handle.get(key) for key in
                         ("slot", "generation", "fieldEpoch", "mapGeneration")) in self.first_handles:
            raise ValueError("natural Mareep spawn does not name a new Wild actor")
        if spawn.get("startup", {}).get("locomotion") != 7 \
                or spawn.get("startup", {}).get("origin") != spawn.get("position") \
                or spawn.get("startup", {}).get("target") != spawn.get("position"):
            raise ValueError("natural Mareep did not use Appear Hop")
        height = spawn.get("initialLandingHeight")
        if not isinstance(height, dict) or height.get("status") != "observed" \
                or height.get("initialPlacement") is not True:
            raise ValueError("natural Mareep lacks its initial native height receipt")
        selected = select_current_actor(snapshot, subject)
        actor = next(item for item in snapshot.get("actors", [])
                     if item.get("handle") == selected["handle"])
        if not live_identity(actor, actor.get("sourceIdentity", {}),
                             actor.get("engineIdentity", {}), species=179,
                             role="WILD", current_epoch=snapshot["context"]["fieldEpoch"]):
            raise ValueError("natural Mareep identity differs at spawn")
        self.spawn = deepcopy(spawn)
        self.subject = deepcopy(selected)
        self.initial = deepcopy(snapshot)
        return actor

    def _actor(self, snapshot):
        selected = select_current_actor(snapshot, self.subject)
        actor = next(item for item in snapshot.get("actors", [])
                     if item.get("handle") == selected["handle"])
        if not live_identity(actor, actor.get("sourceIdentity", {}),
                             actor.get("engineIdentity", {}), species=179,
                             role="WILD", current_epoch=snapshot["context"]["fieldEpoch"]):
            raise ValueError("natural Mareep identity changed")
        return actor

    def observe(self, snapshot, events=()):
        if self.closed:
            raise ValueError("natural Appear Hop measurement is closed")
        if self.failures:
            return self.result()
        try:
            self.frames += 1
            if self.frames > self.max_frames:
                raise ValueError("natural Appear Hop frame bound exceeded")
            if self.first_handles is None:
                self.first_handles = {
                    tuple(actor.get("handle", {}).get(key) for key in
                          ("slot", "generation", "fieldEpoch", "mapGeneration"))
                    for actor in snapshot.get("actors", [])
                }
            actor = self._acquire(snapshot, events) if self.spawn is None else self._actor(snapshot)
            if actor is None:
                return self.result()
            if self.stage == 4 and self.surface is not None:
                self.last = deepcopy(snapshot)
                return self.result()
            if self.last is not None and snapshot.get("frame") != self.last.get("frame") + 1:
                raise ValueError("natural Appear Hop completed-frame stream has a gap")
            if actor.get("presentationAttached") is not True \
                    or (self.stage < 3 and (actor.get("motionKind") != "NONE"
                                           or actor.get("motionPhase") != "IDLE")):
                raise ValueError("Appear Hop changed shared actor motion or presentation")
            engine = actor.get("engineObject", {})
            command = engine.get("movement_cmd")
            state = actor.get("controllerState")
            if type(command) is not int or type(state) is not int:
                raise ValueError("Appear Hop command or controller state is missing")
            if self.stage == 0:
                if command in JUMP_COMMANDS:
                    self.saw_jump = True
                    if state not in ((0, 1) if not self.samples else (1,)):
                        raise ValueError("Appear Hop jump control order differs")
                elif command == DELAY_COMMAND and self.saw_jump:
                    self.stage = 1
                    if state != 1:
                        raise ValueError("Appear Hop delay control differs")
                else:
                    raise ValueError("Appear Hop jump command order differs")
            if self.stage == 1:
                if command == RESTORE_COMMAND:
                    self.stage = 2
                    if state != 1:
                        raise ValueError("Appear Hop restore control differs")
                elif command != DELAY_COMMAND:
                    raise ValueError("Appear Hop delay/restore command order differs")
                elif state != 1:
                    raise ValueError("Appear Hop delay control differs")
            elif self.stage == 2:
                if command == IDLE_COMMAND and state == 1:
                    self.stage = 3
                else:
                    raise ValueError("Appear Hop restore handoff differs")
            elif self.stage == 3:
                if command == DELAY_COMMAND and state == 0:
                    self.stage = 4
                else:
                    raise ValueError("Appear Hop release delay differs")
            face_y = engine.get("face_y")
            if type(face_y) is not int:
                raise ValueError("Appear Hop rendered height is missing")
            self.saw_arc = self.saw_arc or face_y > 0
            self.samples.append({"frame": snapshot["frame"], "command": command,
                                 "controllerState": state, "faceY": face_y})
            if len(self.samples) > 60:
                raise ValueError("Appear Hop sample bound exceeded")
            self.last = deepcopy(snapshot)
            if self.stage == 3 and self.surface is None:
                if not self.saw_arc:
                    raise ValueError("Appear Hop has no rendered vertical arc")
                self.surface = check_natural_appear_hop_surface(self.spawn, snapshot)
                self.terminal = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append({"code": "invalid-natural-appear-hop", "frame": snapshot.get("frame"),
                                  "message": str(error)})
        return self.result()

    def result(self):
        ready = self.stage == 4 and self.surface is not None and not self.failures
        return {"state": "failed" if self.failures or self.closed and not ready
                else "completed" if self.closed else "observing",
            "passed": self.closed and ready, "ready": ready, "acceptedProof": False,
            "subject": deepcopy(self.subject), "frames": self.frames,
            "identitySamples": len(self.samples), "selectedProfileObservationCount": 1 if self.spawn else 0,
            "spawn": deepcopy(self.spawn), "spawnPassed": ready,
            "stopBoundary": {"kind": "idle", "frame": self.terminal["frame"]} if self.terminal else None,
            "completeMotions": [{"kind": "APPEAR_HOP", "samples": deepcopy(self.samples)}] if ready else [],
            "measurementErrors": [], "surface": deepcopy(self.surface),
            "failures": deepcopy(self.failures),
            "scope": "one natural Wild Mareep initial height and complete Appear Hop release"}

    def finish(self):
        self.closed = True
        if not self.result()["ready"] and not self.failures:
            self.failures.append({"code": "incomplete-natural-appear-hop",
                                  "frame": self.last.get("frame") if self.last else None})
        return self.result()


class LiveSpawnHeightControlMeasurement:
    def __init__(self, schema, source_sha256, *, max_frames, authored_profiles):
        self.baseline = NaturalAppearHopHeightMeasurement(schema, source_sha256,
            max_frames=max_frames, authored_profiles=authored_profiles)
        self.receipt = self.receipt_frame = self.height_frame = None
        self.detection = self.cleanup = None
        self.failures = []
        self.closed = False

    def _check_control(self, snapshot, baseline):
        receipt = self.receipt
        terminal = self.baseline.terminal
        if not isinstance(terminal, dict):
            raise ValueError("natural Appear Hop terminal snapshot is missing")
        if not isinstance(receipt, dict):
            raise ValueError("native spawn-height read control is missing")
        if (receipt.get("state") != "complete" or receipt.get("scope") != "native-observer-control-only"
                or receipt.get("cleanupPending") is not False or receipt.get("failure") is not None
                or receipt.get("acceptedProof") is not False
                or type(receipt.get("delta")) is not int or receipt["delta"] != 4096
                or type(receipt.get("writes")) is not int or receipt["writes"] != 2):
            raise ValueError("native spawn-height control lacks exact write/restore completion")
        spawn = self.baseline.spawn
        height = spawn["initialLandingHeight"]
        raw = {key: value for key, value in height.items() if key not in HEIGHT_ENVELOPE}
        if receipt.get("clean") != raw or receipt.get("restored") != raw:
            raise ValueError("native height control clean/restored source, context, point or data differs")
        # Both rows are queued synchronously by the same native return hook.
        # The sampler increments completed_frames before flushing that queue,
        # so the read's completed-frame count is exactly one before its row.
        # No emulated instruction runs between the return clock and the read.
        clocks = ("entryActorFrame", "entryNativeCycle", "returnActorFrame", "returnNativeCycle")
        if (self.receipt_frame != self.height_frame
                or type(receipt.get("frame")) is not int or receipt["frame"] != self.receipt_frame - 1
                or receipt["frame"] < 0
                or any(type(receipt.get(key)) is not int or receipt[key] != height[key] for key in clocks)
                or type(receipt.get("nativeCycle")) is not int
                or receipt["nativeCycle"] != height["returnNativeCycle"]):
            raise ValueError("native height control is stale or outside its height read boundary")
        bad = deepcopy(raw)
        y = bad["positionAfter"]["pos_y"]
        if type(y) is not int or not -0x80000000 <= y + 4096 <= 0x7FFFFFFF:
            raise ValueError("native control Y delta is outside signed position bounds")
        bad["positionAfter"]["pos_y"] = y + 4096
        if receipt.get("bad") != bad:
            raise ValueError("native bad receipt did not change only preparation Y by 4096")
        altered = deepcopy(spawn)
        altered["initialLandingHeight"] = {
            **deepcopy(receipt["bad"]), **{key: deepcopy(height[key]) for key in HEIGHT_ENVELOPE if key in height}}
        try:
            check_natural_appear_hop_surface(altered, terminal)
        except ValueError as error:
            if str(error) != EXPECTED_REASON:
                raise ValueError("native bad height failed for a different reason: " + str(error)) from error
        else:
            raise ValueError("native bad height was accepted by the unchanged surface checker")
        self.detection = {"kind": "spawn-height-read", "reason": EXPECTED_REASON,
            "frame": terminal["frame"], "subject": deepcopy(baseline["subject"]),
            "target": deepcopy(raw["target"]), "cleanY": y, "badY": y + 4096,
            "stopBoundary": deepcopy(baseline["stopBoundary"])}
        self.cleanup = {"restored": True, "cleanupPending": False,
            "receipt": deepcopy(receipt), "frame": self.receipt_frame}

    def observe_initial(self, snapshot, events):
        """Replay the bounded pre-record boot trace without gameplay credit."""
        if self.baseline.last is not None or self.receipt is not None or self.closed:
            raise ValueError("spawn height boot trace can be consumed only once")
        rows = [event for event in events
                if event.get("kind") == "native-observation"
                and event.get("data", {}).get("observation")
                    in ("spawn-prepared", "spawn-landing-height",
                        "spawn-height-read-control", "spawn-appear-hop-frame")]
        frames = sorted({event.get("frame") for event in rows
                         if event.get("data", {}).get("observation")
                            == "spawn-appear-hop-frame"})
        if not frames or any(type(frame) is not int for frame in frames) \
                or frames != list(range(frames[0], frames[-1] + 1)):
            raise ValueError("spawn height boot trace is missing or has a frame gap")
        controls = [event["data"] for event in rows
                    if event["data"].get("observation") == "spawn-height-read-control"]
        if len(controls) > 1 or controls and not isinstance(controls[0].get("clean"), dict):
            raise ValueError("spawn height boot control receipt is missing or duplicated")
        trace_subjects = [event["data"].get("subject") for event in rows
                          if event["data"].get("observation") == "spawn-appear-hop-frame"]
        handles = {tuple(subject.get("handle", {}).get(key) for key in
                         ("slot", "generation", "fieldEpoch", "mapGeneration"))
                   for subject in trace_subjects if isinstance(subject, dict)}
        if len(handles) != 1 or not trace_subjects:
            raise ValueError("spawn height boot trace subject is missing or duplicated")
        self.baseline.required_subject = deepcopy(trace_subjects[0])
        if controls:
            self.baseline.required_height = deepcopy(controls[0]["clean"])
        self.baseline.first_handles = set()
        for frame in frames:
            frame_rows = [event for event in rows if event.get("frame") == frame]
            samples = [event["data"] for event in frame_rows
                       if event["data"].get("observation") == "spawn-appear-hop-frame"]
            if len(samples) != 1:
                raise ValueError("spawn height boot frame is missing or duplicated")
            sample = samples[0]
            synthetic = {
                "frame": frame,
                "nativeCycle": sample["nativeCycle"],
                "actorFrame": sample["actorFrame"],
                "actors": [deepcopy(sample["actor"])],
                "context": deepcopy(sample["worldContext"]),
                "prepared": sample["prepared"],
                "observationBoundary": sample["observationBoundary"],
            }
            result = self.observe(synthetic, frame_rows)
            if result["failures"]:
                break
        if not self.result()["ready"]:
            raise ValueError("spawn height boot trace did not complete")
        self.baseline._actor(snapshot)
        return self.result()

    def observe(self, snapshot, events=()):
        if self.closed:
            raise ValueError("spawn height control measurement is closed")
        if self.failures:
            return self.result()
        observed = self.baseline.observe(snapshot, events)
        try:
            for event in events:
                data = event.get("data", {})
                if event.get("kind") != "native-observation":
                    continue
                if data.get("observation") == "spawn-height-read-control":
                    if self.receipt is not None:
                        raise ValueError("native spawn-height control is duplicated")
                    self.receipt, self.receipt_frame = deepcopy(data), event["frame"]
                if data.get("observation") == "spawn-landing-height" and self.baseline.spawn is not None:
                    height = self.baseline.spawn["initialLandingHeight"]
                    if data == height:
                        self.height_frame = event["frame"]
            if observed["ready"] and self.detection is None:
                self._check_control(snapshot, observed)
        except (ValueError, KeyError, TypeError, AttributeError, IndexError) as error:
            self.failures.append({"code": "invalid-spawn-height-control", "frame": snapshot.get("frame"),
                                  "message": str(error)})
        return self.result()

    def result(self):
        baseline = self.baseline.result()
        failures = deepcopy(self.failures) + baseline["failures"]
        ready = baseline["ready"] and self.detection is not None and self.cleanup is not None and not failures
        return {"state": "failed" if failures or self.closed and not ready
                else "completed" if self.closed else "observing",
            "passed": self.closed and ready, "ready": ready, "acceptedProof": False,
            "subject": deepcopy(baseline["subject"]), "frames": baseline["frames"],
            "baseline": baseline, "detections": {"spawn-height-read": deepcopy(self.detection)} if self.detection else {},
            "cleanup": deepcopy(self.cleanup), "failures": failures,
            "measurementErrors": baseline["measurementErrors"], "completeMotions": baseline["completeMotions"],
            "spawnPassed": baseline["spawnPassed"], "scope": "separate native spawn-height reader calibration; no normal-play credit"}

    def finish(self):
        self.baseline.finish()
        self.closed = True
        if not self.result()["ready"] and not self.result()["failures"]:
            self.failures.append({"code": "incomplete-spawn-height-control",
                                  "frame": self.baseline.last.get("frame") if self.baseline.last else None})
        return self.result()
