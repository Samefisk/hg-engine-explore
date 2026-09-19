"""Typed shared-test seams for the six mounted Crash rows.

This adapter only feeds authenticated raw receipts to the existing pure meter.
The caller owns setup, artifact expansion, command identity and acceptance.
No game control or calibration is implemented here.
"""
from copy import deepcopy

from .devtools_mounted_crash_measurement import KIND, MountedCrashMeasurement

CONTRACT_INPUT = {"contractVersion": 1}
STAGES = ("waiting", "crash", "restored", "recovered")
COMMANDS = ("crash.arm", "crash.close")
REQUIREMENT = "legacy.crash"
MEASUREMENTS = (
    ("natural-input", "crash-held-input-hit-frame"),
    ("live-actor-identity", "crash-cyndaquil-identity-flags"),
    ("engine-boundary", "single-stationary-crash"),
    ("frame-pacing", "crash-presentation-elapsed-schedule"),
    ("feedback-effect", "crash-sound-and-shake"),
    ("control-release", "crash-reset-and-recovery-state"),
)


def validate_measurement(specification, mode, max_frames, subjects):
    if not isinstance(specification, dict) or set(specification) != {"kind", "subject"} \
            or specification.get("kind") != KIND:
        raise ValueError("Crash measurement shape differs")
    selected = [s for s in subjects if s.get("id") == specification["subject"]]
    if mode != "prepared" or type(max_frames) is not int or not 1 <= max_frames <= 600 \
            or len(selected) != 1 or selected[0] != dict(id=specification["subject"],
                species=155, role="MOUNTED", acquire="existing"):
        raise ValueError("Crash requires a prepared mounted Cyndaquil and at most600 frames")
    return deepcopy(specification)


def validate_action(action, phase, mode, subjects):
    op, args = action.get("op"), action.get("args")
    if op not in COMMANDS or not isinstance(args, dict) \
            or set(args) != ({"subject"} if op == "crash.arm" else set()) \
            or phase != "actions" or mode != "prepared":
        raise ValueError("Crash command requires its prepared observation window")
    if op == "crash.arm" and args["subject"] not in subjects:
        raise ValueError("Crash command subject is not declared")
    return deepcopy(action)


def create_meter(inputs, max_frames):
    if inputs != CONTRACT_INPUT or type(inputs.get("contractVersion")) is not int:
        raise ValueError("Crash contract input is missing")
    return MountedCrashMeasurement(max_frames)


def feed_configuration(meter, receipt, snapshot, subject):
    """Authenticate the exact idle fixture without changing Crash gameplay."""
    from .devtools_mounted_crash_measurement import POSITION
    q = receipt.get("value", receipt)
    if getattr(meter, "_typed_configuration", None) is not None or meter.initial is not None \
            or q.get("completed") is not True or q.get("prepared") is not True \
            or q.get("acceptedProof") is not False or q.get("guestAdvanced") is not False \
            or q.get("scope") != "prepared-idle-mounted-walk-fixture" \
            or q.get("subject") != subject or q.get("directionMode") != 0 \
            or q.get("travelTime") is not None or "stompTime" in q \
            or q.get("turning") != "locked" or q.get("crashSound") != "wall-hit" \
            or q.get("changedOffsets") != [19, 65]:
        raise ValueError("Crash fixed lane fixture differs")
    before, after = q.get("before"), q.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("Crash fixed lane fixture lacks native states")
    raw, actual = bytes.fromhex(before["mountStateHex"]), bytes.fromhex(after["mountStateHex"])
    if len(raw) != 184 or len(actual) != 184:
        raise ValueError("Crash fixed lane fixture native state size differs")
    expected = bytearray(raw)
    expected[8 + 19] = 0
    expected[8 + 65] = (expected[8 + 65] | 0x11)
    readiness = after.get("readiness", {})
    actor = next(a for a in snapshot.get("actors", []) if a.get("handle") == subject["handle"])
    if actual != bytes(expected) or q.get("expectedStateHex") != actual.hex() \
            or before.get("profileHex") != raw[8:80].hex() \
            or after.get("profileHex") != actual[8:80].hex() \
            or before.get("bindingHex") != after.get("bindingHex") \
            or after.get("bindingHex") != actual[80:96].hex() \
            or before.get("readiness") != readiness or before.get("clock") != after.get("clock") \
            or before.get("sessionGeneration") != after.get("sessionGeneration") \
            or after.get("clock") != {k: snapshot[k] for k in ("frame", "nativeCycle")} \
            or actor.get("motionKind") != "NONE" or actor.get("motionPhase") != "IDLE" \
            or actor.get("reservationId") != 0 or actor.get("movementPolicy", {}).get("pending") != 0 \
            or any(readiness.get("actor", {}).get(k) != actor.get(k) for k in
                   ("handle", "species", "role", "subjectIdentity", "logical", "commitSequence")) \
            or any(type(actor.get("engineObject", {}).get(k)) is not int for k in POSITION):
        raise ValueError("Crash fixed lane fixture changed unrelated state")
    meter._typed_configuration = deepcopy(q)
    return meter.result()


def feed_command(meter, command, receipt, snapshot, *, subject=None, trace_sequences=None):
    """Caller supplies its bound subject, never an identity taken from a receipt."""
    from .devtools_test_contract import _same_mounted_reader_boundary
    if command not in COMMANDS or receipt.get("advancedFrames", 0 if command == "crash.arm" else None) != 0 \
            or receipt.get("acceptedProof") is not False \
            or not _same_mounted_reader_boundary(snapshot, receipt.get("snapshot", {})) \
            or any(snapshot.get(k) != receipt.get("snapshot", {}).get(k)
                   for k in ("selector", "fieldControl", "observationBoundary")):
        raise ValueError("Crash command changed its completed boundary")
    if command == "crash.arm":
        if not isinstance(subject, dict):
            raise ValueError("Crash arm requires the bound subject")
        if meter.initial is not None or getattr(meter, "_typed_pending_arm", None) is not None:
            raise ValueError("Crash reader already armed")
        r = receipt["crashFeedback"]
        if r.get("latestCompleted") is None:
            if receipt.get("armed") is not True or r.get("armed") is not True \
                    or r.get("closed") is not False or r.get("subject") != subject \
                    or r.get("failure") is not None or r.get("pending") != 0 \
                    or r.get("guestMemoryWrites") != 0 or r.get("acceptedProof") is not False \
                    or r.get("startFrame") != snapshot["frame"] \
                    or r.get("counts") != {key: 0 for key in meter.calls}:
                raise ValueError("Crash pending arm receipt differs")
            meter._typed_pending_arm = deepcopy(dict(subject=subject, snapshot=snapshot, receipt=receipt,
                trace_sequences=trace_sequences))
            return meter.result()
        return meter.arm(subject, snapshot, receipt, trace_sequences=trace_sequences)
    return meter.close(receipt, snapshot)


def feed_chunk(meter, request, receipt, samples, events):
    """Feed one completed shared-worker step chunk, command before observation.

    Jobs expand waits into neutral steps and resolve any event-detail artifacts
    before this boundary. Input gaps, skipped samples and extra events fail.
    """
    if not samples or len(samples) != request.get("args", {}).get("frames"):
        raise ValueError("Crash raw chunk sample count differs")
    frames = [sample["frame"] for sample in samples]
    if frames != list(range(request["startFrame"] + 1, request["startFrame"] + 1 + len(samples))):
        raise ValueError("Crash raw chunk frame order differs")
    grouped = {frame: [] for frame in frames}
    for event in events:
        if event.get("frame") not in grouped or event.get("data", {}).get("detailsOmitted"):
            raise ValueError("Crash raw event lies outside chunk or lacks details")
        grouped[event["frame"]].append(event)
    pending = getattr(meter, "_typed_pending_arm", None)
    if pending is not None:
        first, before = samples[0], pending["snapshot"]
        raw_receipt = receipt.get("receipt", receipt)
        if request != dict(op="step", startFrame=before["frame"], args=dict(frames=1, keys=[])) \
                or any(raw_receipt.get(key) != 1 for key in
                       ("requestedGameFrames", "completedGameFrames", "observedFieldFrames")) \
                or first.get("context") != before.get("context") \
                or first.get("fieldControl") != before.get("fieldControl") \
                or first.get("observationBoundary") != "main-task-queue-completion" \
                or first.get("fieldAvailable") is not True \
                or first["nativeCycle"] < before["nativeCycle"] \
                or any(first["selector"].get(key) != 0 for key in ("heldKeys", "rawHeld", "simulatedKeys")):
            raise ValueError("Crash bootstrap requires one fresh neutral queue")
        handle = pending["subject"]["handle"]
        actor = next(a for a in first["actors"] if a["handle"] == handle)
        prior = next(a for a in before["actors"] if a["handle"] == handle)
        from .devtools_wild_walk_measurement import IDENTITY, LIFECYCLE
        if any(actor.get(key) != prior.get(key) for key in
               (*IDENTITY, "sourceIdentity", "engineIdentity", "logical", "commitSequence")) \
                or actor.get("motionPhase") != "IDLE" or actor.get("reservationId") != 0:
            raise ValueError("Crash bootstrap changed bound actor")
        native_sequence = before["nativeObservation"]["sequence"]
        streams = dict(pending["trace_sequences"] or {})
        for event in events:
            data = event["data"]
            if data.get("observation", "").startswith("mounted-crash-") \
                    or (data.get("event") in (*LIFECYCLE, "MOTION_CANCELED")
                        and (type(data.get("actorHandle")) is not int
                             or data["actorHandle"] == handle["value"])):
                raise ValueError("Crash bootstrap contains motion or crash")
            if event["kind"] == "native-observation":
                if data["sequence"] != native_sequence + 1:
                    raise ValueError("Crash bootstrap native event gap")
                native_sequence = data["sequence"]
            elif event["kind"] == "native":
                stream = data["traceStream"]
                if data["sequence"] != streams.get(stream, data["sequence"] - 1) + 1:
                    raise ValueError("Crash bootstrap actor trace gap")
                streams[stream] = data["sequence"]
        if native_sequence != first["nativeObservation"]["sequence"]:
            raise ValueError("Crash bootstrap missing native tail")
        # Pure arm validates the new sample's complete native reader receipt.
        # No sample/clock is synthesized, and bootstrap gains no motion credit.
        meter.arm(pending["subject"], first, first["crashFeedback"],
                  trace_sequences=streams)
        meter._typed_pending_arm = None
        return meter.result()
    meter.command(request, receipt)
    for sample in samples:
        meter.observe(sample, grouped[sample["frame"]])
        if meter.failures:
            break
    return meter.result()
