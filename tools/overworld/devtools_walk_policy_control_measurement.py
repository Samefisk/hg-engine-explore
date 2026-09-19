"""One native COMMIT reader control and its normal Walk, without acceptance."""
from copy import deepcopy

from tools.overworld.devtools_acceleration_measurement import IDENTITY, policy_bytes
from tools.overworld.devtools_chain_measurement import _bytes, _integer
from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.normal_play_observer import MotionRecorder

KIND = "live-walk-policy-control-v1"


class WalkPolicyControlMeasurement:
    def __init__(self, *, max_frames):
        self.max_frames = _integer(max_frames, "control frame budget", 1, 1200)
        self.subject = self.initial = self.latest = None
        self.control = self.commit = None
        self.recorder = MotionRecorder()
        self.traces, self.failures = [], []
        self.frames = 0
        self.sequence = 0
        self.streams = {}
        self.closed = False
        self.arm_receipt = self.cleanup = None
        self.initial_commit = None

    def _actor(self, snapshot):
        selected = select_current_actor(snapshot, self.subject)
        actor = next(a for a in snapshot["actors"] if a.get("handle") == selected["handle"])
        old = next(a for a in self.initial["actors"] if a.get("handle") == self.subject["handle"])
        if snapshot["context"] != self.initial["context"] or any(actor.get(k) != old.get(k) for k in
                (*IDENTITY, "behaviorFingerprint", "matchedLayerMask", "sourceIdentity")) \
                or engine_binding_identity(actor.get("engineIdentity")) != engine_binding_identity(old.get("engineIdentity")):
            raise ValueError("Walk control subject or current owner changed")
        if actor.get("inputOwnership") != int(actor["role"] == "MOUNTED"):
            raise ValueError("Walk control input owner differs")
        if actor["role"] == "MOUNTED":
            pointer = _integer(actor["engineIdentity"].get("anchorPointer"), "mounted anchor", 0x02000000, 0x023FFFFF)
            if pointer & 3 or actor["engineIdentity"].get("anchorInCurrentManager") is not True:
                raise ValueError("Walk control mounted anchor is not current")
            return actor, snapshot["player"]
        return actor, actor["engineObject"]

    def _control(self, value):
        if not isinstance(value, dict) or value.get("state") not in ("armed", "complete") \
                or value.get("failure") is not None or value.get("cleanupPending") is not False \
                or value.get("acceptedProof") is not False or value.get("subject") != self.subject:
            raise ValueError("Walk reader control failed, is pending, or has a different subject")
        if value["state"] == "armed":
            if value.get("receipt") is not None or self.control is not None:
                raise ValueError("Walk reader control receipt disappeared")
            return
        receipt = value["receipt"]
        clean, bad, restored = (receipt[k] for k in ("clean", "bad", "restored"))
        raw = policy_bytes(clean.get("policy"), clean.get("rawHex"))
        policy_bytes(bad.get("policy"), bad.get("rawHex"))
        policy_bytes(restored.get("policy"), restored.get("rawHex"))
        address = _integer(receipt.get("policyAddress"), "policy address", 0x02000000, 0x02400000 - 32)
        expected = deepcopy(clean)
        changed = bytearray(raw)
        if changed[1] == 255:
            raise ValueError("reader control counter overflow")
        changed[1] += 1
        expected["rawHex"] = changed.hex()
        expected["policy"]["counter"] += 1
        clock = receipt.get("clock", {})
        if address & 3 or type(receipt.get("changedOffset")) is not int or receipt["changedOffset"] != 1 or type(receipt.get("guestInstructionAdvance")) is not int \
                or receipt["guestInstructionAdvance"] != 0 or restored != clean or bad != expected \
                or receipt.get("restoredClock") != clock or set(clock) != {"actorFrame", "nativeCycle"}:
            raise ValueError("same reader fault or exact restoration differs")
        for key in clock: _integer(clock[key], "control " + key)
        if self.control is not None and value != self.control:
            raise ValueError("completed reader control receipt changed")
        self.control = deepcopy(value)

    def arm(self, receipt, snapshot, *, trace_sequences=None):
        if self.initial is not None or self.closed or receipt.get("armed") is not True \
                or receipt.get("prepared") is not True or receipt.get("acceptedProof") is not False \
                or receipt.get("snapshot") != snapshot or snapshot.get("prepared") is not True:
            raise ValueError("Walk control arm is not its unique prepared endpoint")
        subject = receipt["walkPolicyControl"]["subject"]
        self.subject = select_current_actor(snapshot, subject)
        if self.subject != subject or subject["role"] not in ("WILD", "MOUNTED"):
            raise ValueError("Walk control requires the exact current Wild or Mounted subject")
        self.initial = deepcopy(snapshot)
        actor, _ = self._actor(snapshot)
        if actor.get("motionPhase") != "IDLE" or actor.get("reservationId") != 0:
            raise ValueError("Walk control starts before an idle motion boundary")
        self.initial_commit = actor["commitSequence"]
        self._control(receipt["walkPolicyControl"])
        if receipt["walkPolicyControl"]["state"] != "armed":
            raise ValueError("reader control already ran before its window")
        self.sequence = snapshot["nativeObservation"]["sequence"]
        self.streams = deepcopy(trace_sequences or {})
        self.latest = deepcopy(snapshot)
        self.arm_receipt = deepcopy(receipt)

    def observe(self, snapshot, events):
        if self.failures: return self.result()
        try:
            self._observe(snapshot, events)
        except (ValueError, KeyError, TypeError, IndexError) as error:
            self.failures.append(dict(code="walk-policy-control-observation-invalid", frame=snapshot.get("frame"), detail=str(error)))
        return self.result()

    def _observe(self, snapshot, events):
        if self.initial is None or self.closed:
            raise ValueError("Walk control observation is outside its armed window")
        if snapshot.get("frame") != self.latest["frame"] + 1 or snapshot.get("nativeCycle", -1) < self.latest["nativeCycle"] \
                or snapshot.get("observationBoundary") != "main-task-queue-completion" or snapshot.get("prepared") is not True:
            raise ValueError("Walk control completed boundary differs")
        native = snapshot["nativeObservation"]
        if native.get("installedBeforeBoot") is not True or native.get("coverageComplete") is not True \
                or native.get("eventsDropped") != 0 or native.get("profilesEvicted") != 0 \
                or native.get("pendingUnframedEvents") != 0 or native.get("error") is not None:
            raise ValueError("Walk control native coverage is incomplete")
        actor, engine = self._actor(snapshot)
        self._control(snapshot.get("walkPolicyControl"))
        self.frames += 1
        if self.frames > self.max_frames:
            raise ValueError("Walk control frame budget exceeded")
        for event in events:
            if event.get("frame") != snapshot["frame"]:
                raise ValueError("Walk control event frame differs")
            data = event["data"]
            if event["kind"] == "native-observation":
                if data.get("sequence") != self.sequence + 1 or data.get("setupMode") != "prepared":
                    raise ValueError("Walk control native receipt sequence differs")
                self.sequence += 1
                for entry, returned, lower, upper in (("entryNativeCycle", "returnNativeCycle", self.latest["nativeCycle"], snapshot["nativeCycle"]),
                        ("entryActorFrame", "returnActorFrame", self.latest["actorFrame"], snapshot["actorFrame"])):
                    a, b = (_integer(data.get(k), k) for k in (entry, returned))
                    if not lower <= a <= b <= upper:
                        raise ValueError("Walk control native clocks differ")
                if data.get("observation") == "walk-policy" and data.get("slot") == actor["handle"]["slot"] and data.get("operation") == 3:
                    if self.commit is not None or self.control is None:
                        raise ValueError("Walk control COMMIT is missing its unique control")
                    for key in ("publicSubject", "publicSubjectAfter"):
                        if any(data[key].get(k) != actor.get(k) for k in IDENTITY) \
                                or data[key].get("commitSequence") != self.initial_commit:
                            raise ValueError("Walk control COMMIT names another actor or commit")
                    request = _bytes(data.get("requestHex"), 28, "COMMIT request")
                    response = _bytes(data.get("responseHex"), 28, "COMMIT response")
                    if request[:4] != b"\x01\x00\x1c\x00" or request[8:10] != bytes((actor["handle"]["slot"], 3)) \
                            or request[11] != 1 or not request[14] & 4 or response[:16] != request[:16] \
                            or response[16] != 1 or response[20] & 0x6E or type(data.get("returnValue")) is not int or data["returnValue"] != 1:
                        raise ValueError("reader control is not an ordinary Walk COMMIT")
                    control = self.control["receipt"]
                    if control["clean"] != dict(rawHex=data.get("policyBeforeHex"), policy=data.get("policyBefore")) \
                            or control["clock"] != dict(actorFrame=data["entryActorFrame"], nativeCycle=data["entryNativeCycle"]):
                        raise ValueError("reader control differs from this native COMMIT entry")
                    policy_bytes(data.get("policyAfter"), data.get("policyAfterHex"))
                    self.commit = deepcopy(event)
            elif event["kind"] == "native":
                stream = _integer(data.get("traceStream"), "trace stream", 1)
                sequence = _integer(data.get("sequence"), "trace sequence", 1)
                if sequence != self.streams.get(stream, 0) + 1:
                    raise ValueError("Walk control semantic sequence gap")
                self.streams[stream] = sequence
                if data.get("actorHandle") == actor["handle"]["value"]:
                    if data.get("actor") != {k:v for k,v in actor["handle"].items() if k != "value"}:
                        raise ValueError("Walk control semantic generation differs")
                    if len(self.traces) >= 64: raise ValueError("Walk control trace bound exceeded")
                    self.traces.append(deepcopy(event))
            elif event["kind"] == "trace-status" and data.get("code") == "ring-overwrite":
                # The native ring also replaces records already retained by the
                # reader. Only that no-loss notice is safe inside this window.
                if type(data.get("unreadEventsLost")) is not int or data["unreadEventsLost"] != 0 \
                        or data.get("coverageComplete", True) is not True \
                        or data.get("diagnosticOnly") is not True \
                        or data.get("traceStream") not in self.streams:
                    raise ValueError("Walk control trace lost unread events")
                _integer(data.get("count"), "overwritten count", 1)
                _integer(data.get("traceStream"), "overwrite trace stream", 1)
            else:
                raise ValueError("Walk control trace status or unknown event")
        if native["sequence"] != self.sequence:
            raise ValueError("Walk control native endpoint differs")
        if actor["motionKind"] not in ("NONE", "WALK") or actor["motionPhase"] == "CANCELED":
            raise ValueError("Walk control motion was replaced")
        if actor["motionPhase"] == "IDLE" and actor.get("reservationId") != 0:
            raise ValueError("Walk control terminal still owns a reservation")
        if self.recorder.current is None and actor["motionKind"] == "WALK":
            if type(actor["motionElapsed"]) is not int or actor["motionElapsed"] not in (0, 1):
                raise ValueError("Walk control missed its motion start")
            if actor["motionElapsed"] == 1:
                previous, previous_engine = self._actor(self.latest)
                starts = [e["data"] for e in self.traces if e["frame"] == snapshot["frame"]
                          and e["data"].get("event") == "MOTION_STARTED"]
                if len(starts) != 1 or starts[0].get("reason") != "OK" \
                        or (starts[0].get("valueA"), starts[0].get("valueB")) != (1, actor["motionDuration"]):
                    raise ValueError("Walk control native lifecycle differs: MOTION_STARTED")
                if previous["motionPhase"] != "IDLE" or previous.get("reservationId") != 0 \
                        or previous["commitSequence"] != actor["commitSequence"] \
                        or previous["logical"] != actor["origin"] \
                        or [previous_engine["pos_x"], previous_engine["pos_z"]] != \
                            [(actor["origin"][k] << 16) + 0x8000 for k in ("x", "y")]:
                    raise ValueError("Walk control elapsed-one start lacks its settled native boundary")
        self.recorder.observe(snapshot["frame"], actor, engine)
        if self.recorder.failures or len(self.recorder.completed) > 1 \
                or sum(e["data"].get("event") == "MOTION_STARTED" for e in self.traces) > 1:
            raise ValueError("Walk control motion is incomplete or repeated")
        if self.recorder.completed:
            self._terminal()
        self.latest = deepcopy(snapshot)

    def _terminal(self):
        motion = self.recorder.completed[0]
        if self.commit is None or self.commit["frame"] != motion["commitFrame"]:
            raise ValueError("Walk terminal lacks its controlled COMMIT")
        expected = (("MOTION_STARTED", motion["startFrame"], 1, motion["duration"]),
            ("LOGICAL_COMMIT", motion["commitFrame"], motion["commitAfter"], 1),
            ("MOTION_FINISHED", motion["finishFrame"], motion["commitAfter"], 1),
            ("CONTROL_RETURNED", motion["finishFrame"], int(self.subject["role"] == "MOUNTED"), motion["commitAfter"]))
        sequences = []
        for name, frame, a, b in expected:
            matches = [e for e in self.traces if e["data"].get("event") == name]
            if len(matches) != 1 or matches[0]["frame"] != frame or matches[0]["data"].get("reason") != "OK" \
                    or (matches[0]["data"].get("valueA"), matches[0]["data"].get("valueB")) != (a,b):
                raise ValueError("Walk control native lifecycle differs: " + name)
            sequences.append(matches[0]["data"]["sequence"])
        if sequences != sorted(set(sequences)):
            raise ValueError("Walk control lifecycle order differs")

    @property
    def ready(self):
        return not self.failures and self.control is not None and self.commit is not None \
            and len(self.recorder.completed) == 1 and self.recorder.current is None

    def close(self, receipt):
        if self.closed or not self.ready or receipt.get("closed") is not True or receipt.get("advancedFrames") != 0 \
                or receipt.get("acceptedProof") is not False or receipt.get("walkPolicyControl") != self.control:
            raise ValueError("Walk control cleanup is missing or differs")
        self.closed = True
        self.cleanup = deepcopy(receipt)

    def result(self):
        return deepcopy(dict(kind=KIND, ready=self.ready, passed=self.ready and self.closed, acceptedProof=False,
            observedFrames=self.frames, subject=self.subject, failures=self.failures,
            arm=self.arm_receipt, control=self.control, commit=self.commit, motions=self.recorder.completed,
            traces=self.traces, cleanup=self.cleanup))

    def finish(self):
        if not self.ready or not self.closed:
            self.failures.append(dict(code="walk-policy-control-incomplete"))
        return self.result()
