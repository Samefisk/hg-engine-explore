"""Bounded, pure seven-Walk WILD/MOUNTED acceleration measurement.

Prepared RESET is a fixture, not gameplay credit. The caller authenticates its
outer native bridge and package. This reducer checks its retained readback and
then every completed sample. It neither drives a guest nor grants acceptance.
"""
from copy import deepcopy

from tools.overworld.devtools_chain_measurement import LedybaChainMeasurement, _bytes, _integer
from tools.overworld.devtools_records import GENERATION_FIELDS, select_current_actor, engine_binding_identity
from tools.overworld.normal_play_observer import MotionRecorder, observed_chain_reset

ROLES = ("WILD", "MOUNTED")
IDENTITY = ("handle", "subjectIdentity", "species", "form", "level", "role", *GENERATION_FIELDS)
POLICY_FIELDS = dict(zip(
    ("direction", "counter", "speed", "base", "spotState", "skid", "turn", "resume",
     "chain", "ticks", "action", "variance", "buffered", "stop", "pending", "pendingSkid", "streamState"),
    (*range(8), *range(16, 25))))


def policy_bytes(value, raw):
    raw = _bytes(raw, 32, "policy")
    if not isinstance(value, dict) or any(type(value.get(k)) is not int or value[k] != raw[i]
                                          for k, i in POLICY_FIELDS.items()):
        raise ValueError("policy bytes and decoded fields differ")
    return raw


def reset_value(receipt):
    """Check the immediate public RESET, not a later possibly moving endpoint."""
    if not isinstance(receipt, dict) or receipt.get("completed") is not True \
            or receipt.get("prepared") is not True or receipt.get("acceptedProof") is not False \
            or receipt.get("scope") != "prepared-idle-walk-policy-reset" \
            or receipt.get("scratchRestored") is not True or type(receipt.get("returnValue")) is not int \
            or receipt["returnValue"] != 1:
        raise ValueError("missing successful prepared RESET")
    before, after = receipt["before"], receipt["after"]
    for endpoint in (before, after):
        staged = endpoint.get("stagedMovement", {})
        actor = endpoint["actor"]
        selected = select_current_actor(endpoint["snapshot"], receipt["subject"])
        current = next(a for a in endpoint["snapshot"]["actors"] if a.get("handle") == selected["handle"])
        if any(current.get(k) != value for k, value in actor.items()):
            raise ValueError("RESET actor and immediate snapshot differ")
        if staged.get("known") is not True or staged.get("idle") is not True \
                or staged.get("slot") != actor["handle"]["slot"] \
                or staged.get("objectPointer") != actor["engineIdentity"]["pointer"] \
                or actor.get("stagedMovement") != staged:
            raise ValueError("RESET staged movement is unavailable or active")
    request = _bytes(receipt.get("requestHex"), 28, "RESET request")
    expected_request = b"\x01\x00\x1c\x00" + bytes(4) + bytes((receipt["subject"]["handle"]["slot"], 0)) + bytes(18)
    if request != expected_request or receipt.get("responseHex") != request.hex():
        raise ValueError("RESET request or response differs")
    prior = _bytes(before.get("policyHex"), 32, "RESET before")
    expected = bytearray(prior)
    expected[:8] = bytes((255, 0, 0, 0, 255, 0, 0, 0))
    expected[16:19] = bytes(3)
    expected[20:24] = bytes((255, 0, 0, 0))
    if after.get("policyHex") != expected.hex() or before.get("actor") != after.get("actor") \
            or before["snapshot"].get("player") != after["snapshot"].get("player") \
            or before.get("inputs") != after.get("inputs"):
        raise ValueError("RESET readback or unchanged actor differs")
    return bytes(expected)


class AccelerationMeasurement:
    """Bind one role at its exact RESET endpoint; observe dense shared frames.

    bind(role, subject, snapshot, reset_receipt) starts that role's window.
    Both windows can be separate sessions; each bind seeds that stream's native
    watermark. No frames or native events before that endpoint earn credit.
    All later events are consumed, including other actors, to detect trace loss.
    """
    def __init__(self, schema, source_sha256, *, max_frames):
        self.max_frames = _integer(max_frames, "max_frames", 1, 60000)
        self.profile_reader = LedybaChainMeasurement(schema, source_sha256, max_frames=max_frames,
                                                    accepted_setup_mode="prepared")
        self.fields = {f["key"]: f["offset"] for f in schema["fields"]}
        self.roles = {}
        self.active = None
        self.frames = 0
        self.failures = []

    def _actor(self, snapshot, state):
        selected = select_current_actor(snapshot, state["subject"])
        actor = next(a for a in snapshot["actors"] if a.get("handle") == selected["handle"])
        if any(actor.get(k) != state["identity"].get(k) for k in IDENTITY) \
                or snapshot["context"] != state["context"] \
                or actor.get("behaviorFingerprint") != state["fingerprint"] \
                or actor.get("matchedLayerMask") != state["mask"] \
                or actor.get("sourceIdentity") != state["source"] \
                or engine_binding_identity(actor.get("engineIdentity")) != engine_binding_identity(state["engineIdentity"]):
            raise ValueError("acceleration subject, context or profile changed")
        owner = int(actor["role"] == "MOUNTED")
        if actor.get("inputOwnership") != owner:
            raise ValueError("role input owner changed")
        if owner:
            identity = actor["engineIdentity"]
            pointer = _integer(identity.get("anchorPointer"), "mounted anchor", 0x02000000, 0x023FFFFF)
            if pointer & 3 or identity.get("anchorInCurrentManager") is not True:
                raise ValueError("mounted player anchor is not current")
            engine = snapshot["player"]
        else:
            engine = actor["engineObject"]
        if not isinstance(engine, dict) or type(engine.get("flags")) is not int or not engine["flags"] & 1:
            raise ValueError("logical engine anchor is absent")
        return actor, engine

    def bind(self, role, subject, snapshot, reset_receipt, *, resolved_profiles=None):
        if self.failures or role not in ROLES or role in self.roles \
                or (self.active is not None and len(self.roles[self.active]["motions"]) != 7):
            raise ValueError("acceleration role cannot be rebound")
        raw = reset_value(reset_receipt)
        if resolved_profiles is None:
            resolved_profiles = []
        if not isinstance(resolved_profiles, list) or len(resolved_profiles) > 64:
            raise ValueError("RESET profile cache is not a bounded receipt list")
        if reset_receipt["after"]["snapshot"] != snapshot or snapshot.get("prepared") is not True:
            raise ValueError("RESET endpoint differs")
        bound = select_current_actor(snapshot, subject)
        if role != bound["role"] or any(reset_receipt["subject"].get(k) != bound[k]
                                        for k in ("handle", "subjectIdentity", "species", "role", *GENERATION_FIELDS)):
            raise ValueError("RESET subject differs")
        actor = next(a for a in snapshot["actors"] if a.get("handle") == bound["handle"])
        inputs = reset_receipt["after"]["inputs"]
        if actor.get("motionPhase") != "IDLE" or actor.get("reservationId") != 0 \
                or inputs.get("state") != 0 or any(inputs.get(k) != 0 for k in
                ("heldKeys", "newKeys", "rawHeld", "rawNew", "simulatedKeys", "physicalPressed")):
            raise ValueError("RESET endpoint is not idle with released input")
        # The native RESET snapshots omit the profile cache for a cheap paused
        # read. The completed outer boundary can supply the original native
        # resolver receipts; they still pass the full profile/fingerprint check.
        for receipt in [*snapshot["nativeObservation"].get("resolvedProfiles", []), *resolved_profiles]:
            self.profile_reader._profile(receipt)
        fp = actor["behaviorFingerprint"]
        if fp not in self.profile_reader.profiles or int.from_bytes(raw[8:12], "little") != fp \
                or int.from_bytes(raw[12:16], "little") != actor["matchedLayerMask"] \
                or self.profile_reader.profiles[fp]["appliedOverrides"] != actor["matchedLayerMask"]:
            raise ValueError("RESET lacks captured profile binding")
        state = dict(subject=deepcopy(bound), identity={k: deepcopy(actor[k]) for k in IDENTITY},
            context=deepcopy(snapshot["context"]), source=deepcopy(actor["sourceIdentity"]),
            engineIdentity=deepcopy(actor["engineIdentity"]), fingerprint=fp, mask=actor["matchedLayerMask"],
            initialCommit=actor["commitSequence"], reset=deepcopy(reset_receipt), motions=[], policies=[],
            traces=[], terminalResets=[], recorder=MotionRecorder(), frame=snapshot["frame"], nativeCycle=snapshot["nativeCycle"],
            actorFrame=_integer(snapshot.get("actorFrame"), "RESET actor frame"),
            sequence=snapshot["nativeObservation"]["sequence"], streams={}, direction=None, lane=None,
            speed=None, counter=0, joined=0)
        checked_actor, checked_engine = self._actor(snapshot, state)
        state.update(previousActor=deepcopy(checked_actor), previousEngine=deepcopy(checked_engine))
        self.roles[role] = state
        self.active = role

    def seed_window_boundary(self, snapshot, events, trace_sequences):
        """Exclude RESET through its first completed field boundary.

        The controller validates the full prepared prefix first. This second
        guard rejects a lost completed update or any changed motion/anchor.
        """
        state = self.roles[self.active]
        if state.get("startupBoundary") is not None or state["motions"] or state["policies"]:
            raise ValueError("acceleration startup boundary already consumed")
        baseline = state["reset"]["after"]["snapshot"]
        actor, engine = self._actor(snapshot, state)
        old_actor, old_engine = self._actor(baseline, state)
        keys = ("logical", "origin", "target", "motionKind", "motionPhase", "motionElapsed",
                "motionDuration", "reservationId", "commitSequence", "inputOwnership")
        advance = snapshot["frame"] - state["frame"]
        if advance not in (0, 1) or snapshot.get("actorFrame") != state["actorFrame"] + advance \
                or snapshot.get("fieldAvailable") is not True \
                or snapshot.get("observationBoundary") != "main-task-queue-completion" \
                or snapshot["context"] != baseline["context"] or snapshot.get("player") != baseline.get("player") \
                or engine != old_engine or any(actor.get(k) != old_actor.get(k) for k in keys) \
                or snapshot["nativeCycle"] < state["nativeCycle"]:
            raise ValueError("RESET startup boundary advanced or changed pose")
        retained = []
        for event in events:
            data = event.get("data", {})
            if event.get("kind") == "native-observation" and data.get("sequence", 0) > state["sequence"]:
                if not state["frame"] <= event.get("frame", -1) <= snapshot["frame"] \
                        or data["sequence"] != state["sequence"] + 1:
                    raise ValueError("RESET startup native receipt gap")
                state["sequence"] += 1
                retained.append(deepcopy(event))
            elif event.get("kind") == "native" and data.get("actorHandle") == actor["handle"]["value"] \
                    and state["frame"] <= event.get("frame", -1) <= snapshot["frame"] and data.get("event") in (
                        "MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "MOTION_CANCELED", "CONTEXT_CHANGED"):
                raise ValueError("RESET startup contains unmeasured motion")
        if state["sequence"] != snapshot["nativeObservation"]["sequence"]:
            raise ValueError("RESET startup native watermark differs")
        state["streams"] = deepcopy(trace_sequences)
        state["nativeCycle"] = snapshot["nativeCycle"]
        state["frame"] = snapshot["frame"]
        state["actorFrame"] = snapshot["actorFrame"]
        state["previousActor"] = deepcopy(actor)
        state["previousEngine"] = deepcopy(engine)
        state["startupBoundary"] = dict(snapshot=deepcopy(snapshot), events=retained,
                                         traceSequences={str(k): v for k, v in trace_sequences.items()})

    def _subject(self, value, state):
        if not isinstance(value, dict) or value.get("status") != "observed-public-subject" \
                or any(value.get(k) != state["identity"][k] for k in IDENTITY) \
                or value.get("behaviorFingerprint") != state["fingerprint"] \
                or value.get("matchedLayerMask") != state["mask"]:
            raise ValueError("native policy subject differs")

    def _policy(self, event, state):
        data = event["data"]
        self._subject(data.get("publicSubject"), state)
        self._subject(data.get("publicSubjectAfter"), state)
        request = _bytes(data.get("requestHex"), 28, "COMMIT request")
        response = _bytes(data.get("responseHex"), 28, "COMMIT response")
        if request[:4] != b"\x01\x00\x1c\x00" or request[8] != state["subject"]["handle"]["slot"] \
                or request[9] != 3 or request[11] != 1 or not request[14] & 4 \
                or response[:16] != request[:16] or response[16] != 1 or response[20] & (2 | 4 | 8 | 32 | 64) \
                or type(data.get("returnValue")) is not int or data["returnValue"] != 1:
            raise ValueError("not an ordinary active one-tile COMMIT")
        before = policy_bytes(data.get("policyBefore"), data.get("policyBeforeHex"))
        after = policy_bytes(data.get("policyAfter"), data.get("policyAfterHex"))
        binding = state["fingerprint"].to_bytes(4, "little") + state["mask"].to_bytes(4, "little")
        if before[8:16] != binding or after[8:16] != binding:
            raise ValueError("raw policy profile binding differs")
        lane = _bytes(data.get("laneHex"), 72, "COMMIT lane")
        # GetBehaviorStateLane maps ACTIVE2/TIRED3, not raw enum indexes;
        # CHILL0 and EMOTING1 use Owner. Mount CommitWalkBoundary always Owner.
        if request[13] not in (0, 1, 2, 3) or (self.active == "MOUNTED" and request[13] != 0):
            raise ValueError("COMMIT role lane state differs")
        lane_index = {2: 1, 3: 2}.get(request[13], 0)
        if lane.hex() != self.profile_reader.profiles[state["fingerprint"]]["lanes"][lane_index]:
            raise ValueError("COMMIT does not use the role's resolved lane")
        field = lambda name: lane[self.fields[name]]
        base = min(32, max(1, field("chillSpeed")))
        fastest = min(base, min(32, max(1, field("maxWalkSpeed"))))
        tiles = field("tilesToAccelerate")
        acceleration_step = field("walkAccelerationStep")
        if not tiles or acceleration_step == 0 or field("walkOptions") & 32:
            raise ValueError("selected lane does not accelerate")
        if state["lane"] is None:
            state.update(lane=lane.hex(), speed=base, direction=request[10])
            state["recorder"].expected_pause_by_kind["WALK"] = field("walkPause")
        if state["lane"] != lane.hex() or request[10] != state["direction"] \
                or before[0] != state["direction"] or before[1] != state["counter"] \
                or before[2] != state["speed"] or before[3] != base or before[4] != request[13] \
                or before[5] or before[7] or before[21] or before[22] != 2 or before[23] \
                or before[6] != (0 if field("walkPause") else len(state["policies"])):
            raise ValueError("consecutive acceleration policy changed")
        counter, speed = state["counter"], state["speed"]
        if speed > fastest:
            counter += 1
            if counter >= tiles:
                counter = 0
                speed = max(
                    fastest,
                    (speed + 1) // 2
                    if acceleration_step == 33
                    else max(1, speed - acceleration_step),
                )
        expected = bytearray(before)
        expected[1], expected[2], expected[22] = counter, speed, 0
        expected[6] = 0 if field("walkPause") else min(254, before[6] + 1)
        if after != bytes(expected):
            raise ValueError("acceleration amount, clamp or tile-counter result differs")
        if len(state["policies"]) >= 7:
            raise ValueError("more than seven policy commits")
        commit = (state["initialCommit"] + len(state["policies"])) & 0xFFFFFFFF
        if any(data[key].get("commitSequence") != commit for key in ("publicSubject", "publicSubjectAfter")):
            raise ValueError("policy precommit sequence differs")
        state["policies"].append(deepcopy(event))
        state.update(speed=speed, counter=counter)

    def observe(self, snapshot, events):
        if self.failures:
            return self.result()
        try:
            self._observe(snapshot, events)
        except (ValueError, KeyError, TypeError, IndexError) as error:
            self.failures.append({"code": "acceleration-observation-invalid", "frame": snapshot.get("frame"),
                                  "detail": str(error)})
        return self.result()

    def _observe(self, snapshot, events):
        if self.active is None:
            raise ValueError("no RESET-bound acceleration subject")
        state = self.roles[self.active]
        frame = _integer(snapshot.get("frame"), "completed frame")
        cycle = _integer(snapshot.get("nativeCycle"), "native cycle", 1)
        actor_frame = _integer(snapshot.get("actorFrame"), "actor frame")
        if frame != state["frame"] + 1 or cycle < state["nativeCycle"] \
                or actor_frame < state["actorFrame"] \
                or snapshot.get("observationBoundary") != "main-task-queue-completion" \
                or snapshot.get("prepared") is not True:
            raise ValueError("completed observation gap or mode changed")
        native = snapshot["nativeObservation"]
        if native.get("installedBeforeBoot") is not True or native.get("coverageComplete") is not True \
                or native.get("eventsDropped") != 0 or native.get("profilesEvicted") != 0 \
                or native.get("error") is not None or native.get("pendingUnframedEvents") != 0:
            raise ValueError("native observation coverage is incomplete")
        actor, engine = self._actor(snapshot, state)
        self.frames += 1
        if self.frames > self.max_frames:
            raise ValueError("acceleration frame budget exceeded")
        terminal_resets = []
        for event in events:
            if event.get("frame") != frame:
                raise ValueError("event completed frame differs")
            data = event.get("data", {})
            if event.get("kind") == "native-observation":
                if data.get("sequence") != state["sequence"] + 1 or data.get("setupMode") != "prepared":
                    raise ValueError("native receipt sequence gap or mode differs")
                state["sequence"] += 1
                a, b = (_integer(data.get(k), k) for k in ("entryNativeCycle", "returnNativeCycle"))
                if not state["nativeCycle"] <= a <= b <= cycle:
                    raise ValueError("native policy clocks differ")
                a, b = (_integer(data.get(k), k) for k in ("entryActorFrame", "returnActorFrame"))
                if not state["actorFrame"] <= a <= b <= actor_frame:
                    raise ValueError("native actor clocks differ")
                if data.get("observation") == "walk-policy" and data.get("slot") == actor["handle"]["slot"]:
                    if data.get("operation") == 0:
                        # Native callbacks precede the completed-frame recorder.
                        # Defer only the decision, retaining the real receipt.
                        terminal_resets.append(deepcopy(event))
                    elif data.get("operation") == 3:
                        self._policy(event, state)
                    elif state["policies"] or state["recorder"].current is not None:
                        request = _bytes(data.get("requestHex"), 28, "policy request")
                        response = _bytes(data.get("responseHex"), 28, "policy response")
                        if observed_chain_reset(request, response, data.get("returnValue") == 1):
                            raise ValueError("policy reset interrupted consecutive series")
            elif event.get("kind") == "native":
                stream, sequence = data.get("traceStream"), data.get("sequence")
                _integer(stream, "trace stream", 1)
                _integer(sequence, "trace sequence", 1)
                prior = state["streams"].get(stream)
                if prior is not None and sequence != prior + 1:
                    raise ValueError("semantic trace sequence gap")
                state["streams"][stream] = sequence
                if data.get("actorHandle") == actor["handle"]["value"]:
                    if data.get("actor") != {k: v for k, v in actor["handle"].items() if k != "value"}:
                        raise ValueError("semantic actor generation differs")
                    if data.get("event") in ("MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND", "CONTROL_REBOUND"):
                        raise ValueError("native cancellation or rebind interrupted series")
                    if len(state["traces"]) >= 128:
                        raise ValueError("semantic trace bound exceeded")
                    state["traces"].append(deepcopy(event))
            elif event.get("kind") == "trace-status" and data.get("code") == "ring-overwrite":
                # Replacing already retained records is not a coverage gap.
                if type(data.get("unreadEventsLost")) is not int or data["unreadEventsLost"] != 0 \
                        or data.get("coverageComplete", True) is not True \
                        or data.get("diagnosticOnly") is not True \
                        or type(data.get("traceStream")) is not int \
                        or data["traceStream"] not in state["streams"]:
                    raise ValueError("acceleration trace lost unread events")
                _integer(data.get("count"), "overwritten count", 1)
                _integer(data["traceStream"], "overwrite trace stream", 1)
            elif event.get("kind") == "trace-status":
                raise ValueError("trace status interrupts acceleration window")
        if native.get("sequence") != state["sequence"]:
            raise ValueError("native endpoint watermark differs")
        if actor.get("motionKind") not in ("NONE", "WALK") or actor.get("motionPhase") == "CANCELED":
            raise ValueError("non-Walk interrupted acceleration")
        if actor.get("motionPhase") == "IDLE" and actor.get("reservationId") != 0:
            raise ValueError("terminal reservation remains active")
        recorder = state["recorder"]
        if recorder.current is None and actor.get("motionKind") == "WALK":
            if type(actor.get("motionElapsed")) is not int or actor["motionElapsed"] not in (0, 1):
                raise ValueError("initial Walk sample missing")
            if actor["motionElapsed"] == 1:
                previous, previous_engine = state["previousActor"], state["previousEngine"]
                starts = [e["data"] for e in state["traces"] if e["frame"] == frame
                          and e["data"].get("event") == "MOTION_STARTED"]
                if len(starts) != 1 or starts[0].get("reason") != "OK" \
                        or (starts[0].get("valueA"), starts[0].get("valueB")) != (1, actor["motionDuration"]) \
                        or previous["motionPhase"] != "IDLE" or previous.get("reservationId") != 0 \
                        or previous["commitSequence"] != actor["commitSequence"] \
                        or previous["logical"] != actor["origin"] \
                        or [previous_engine["pos_x"], previous_engine["pos_z"]] != \
                            [(actor["origin"][k] << 16) + 0x8000 for k in ("x", "y")]:
                    raise ValueError("elapsed-one Walk lacks its settled native start boundary")
        recorder.observe(frame, actor, engine)
        if recorder.failures:
            raise ValueError("motion: " + recorder.failures[0]["reason"])
        while state["joined"] < len(recorder.completed):
            motion = recorder.completed[state["joined"]]
            self._join(state, motion)
            state["motions"].append(deepcopy(motion))
            state["joined"] += 1
        for event in terminal_resets:
            self._terminal_reset(event, state, actor)
            state["terminalResets"].append(event)
        state.update(frame=frame, nativeCycle=cycle, actorFrame=actor_frame,
                     previousActor=deepcopy(actor), previousEngine=deepcopy(engine))

    def _terminal_reset(self, event, state, actor):
        """Input release may reset policy only after the seventh proven finish."""
        data = event["data"]
        if len(state["motions"]) != 7 or len(state["policies"]) != 7 \
                or state["recorder"].current is not None \
                or state["motions"][-1]["finishFrame"] != event["frame"] \
                or actor.get("motionKind") != "NONE" or actor.get("motionPhase") != "IDLE" \
                or actor.get("reservationId") != 0:
            raise ValueError("RESET interrupted consecutive series")
        final_commit = (state["initialCommit"] + 7) & 0xFFFFFFFF
        for public in (data.get("publicSubject"), data.get("publicSubjectAfter")):
            self._subject(public, state)
            if public.get("commitSequence") != final_commit \
                    or public.get("motionKind") != "NONE" or public.get("motionPhase") != "IDLE":
                raise ValueError("RESET lacks unchanged final idle subject")
        if data["publicSubject"] != data["publicSubjectAfter"] \
                or actor["commitSequence"] != final_commit \
                or state["policies"][-1]["data"]["sequence"] >= data["sequence"]:
            raise ValueError("RESET precedes final policy COMMIT or changes subject")
        terminal = [e["data"] for e in state["traces"] if e["frame"] == event["frame"]
                    and e["data"].get("event") in ("MOTION_FINISHED", "CONTROL_RETURNED")]
        if len(terminal) != 2 or any(
                _integer(e.get("actorFrame"), "terminal actor frame") > data["entryActorFrame"]
                for e in terminal):
            raise ValueError("RESET precedes native terminal boundary")
        request = _bytes(data.get("requestHex"), 28, "terminal RESET request")
        response = bytearray(request)
        for offset in (16, 21, 22):  # Native reducer clears decision, effect, chainAction.
            response[offset] = 0
        if request[:4] != b"\x01\x00\x1c\x00" \
                or request[8:10] != bytes((actor["handle"]["slot"], 0)) \
                or data.get("responseHex") != response.hex() \
                or type(data.get("returnValue")) is not int or data["returnValue"] != 1:
            raise ValueError("terminal RESET raw receipt differs")

    def _join(self, state, motion):
        index = state["joined"]
        if index >= 7 or index >= len(state["policies"]):
            raise ValueError("completed Walk lacks unique policy COMMIT")
        policy = state["policies"][index]
        raw = bytes.fromhex(policy["data"]["policyBeforeHex"])
        delta = tuple(b - a for a, b in zip(motion["origin"], motion["target"]))
        # Public directions: cardinal 0..3, then diagonals 4..7.
        directions = ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1))
        if state["direction"] not in range(8) or delta != directions[state["direction"]] \
                or motion["duration"] != raw[2] or policy["frame"] != motion["commitFrame"] \
                or motion["fingerprint"] != state["fingerprint"] \
                or motion["commitAfter"] != ((state["initialCommit"] + index + 1) & 0xFFFFFFFF):
            raise ValueError("Walk duration, direction or terminal policy differs")
        lane = bytes.fromhex(state["lane"])
        if motion["pauseFrames"] != lane[self.fields["walkPause"]] \
                or (index and motion["origin"] != state["motions"][-1]["target"]):
            raise ValueError("terminal pause or consecutive tile path differs")
        for sample in motion["samples"]:
            expected_pose = [(coordinate << 16) + 0x8000 + (1 if d >= 0 else -1)
                             * (abs(d) * 0x10000 * sample["elapsed"] // motion["duration"])
                             for coordinate, d in zip(motion["origin"], delta)]
            if [sample["render"][0], sample["render"][2]] != expected_pose or sample["jumpOffset"] != 0:
                raise ValueError("Walk sample differs from exact shared travel")
        expected = [("MOTION_STARTED", motion["startFrame"], 1, motion["duration"]),
                    ("LOGICAL_COMMIT", motion["commitFrame"], motion["commitAfter"], 1),
                    ("MOTION_FINISHED", motion["finishFrame"], motion["commitAfter"], 1),
                    ("CONTROL_RETURNED", motion["finishFrame"], int(self.active == "MOUNTED"), motion["commitAfter"])]
        matched = []
        for name, frame, a, b in expected:
            matches = [e for e in state["traces"] if e["frame"] == frame and e["data"].get("event") == name]
            if len(matches) != 1 or matches[0]["data"].get("reason") != "OK" \
                    or (matches[0]["data"].get("valueA"), matches[0]["data"].get("valueB")) != (a, b):
                raise ValueError("missing or different native " + name)
            matched.append(matches[0]["data"]["sequence"])
        if any(b <= a for a, b in zip(matched, matched[1:])):
            raise ValueError("native motion boundaries are out of order")
        if index == 6 and any(sum(e["data"].get("event") == name for e in state["traces"]) != 7
                              for name, *_ in expected):
            raise ValueError("extra native motion boundaries in seven-Walk series")

    @property
    def ready(self):
        if self.failures or set(self.roles) != set(ROLES):
            return False
        durations = [[m["duration"] for m in self.roles[r]["motions"]] for r in ROLES]
        return all(len(d) == 7 for d in durations) and durations[0] == durations[1] \
            and len(set(durations[0])) > 1 and all(self.roles[r]["recorder"].current is None for r in ROLES)

    def result(self):
        proof = {role: {k: deepcopy(s[k]) for k in ("subject", "reset", "initialCommit", "fingerprint", "motions", "policies", "traces", "startupBoundary", "terminalResets") if k in s}
                 for role, s in self.roles.items()}
        rows = []
        if self.ready:
            states = [self.roles[r] for r in ROLES]
            values = ([7, 7], {"initials": [s["fingerprint"] for s in states],
                "series": [[s["fingerprint"]] * 7 for s in states],
                "durations": [[m["duration"] for m in s["motions"]] for s in states]},
                {"initials": [s["initialCommit"] for s in states],
                 "series": [[m["commitAfter"] for m in s["motions"]] for s in states]}, 14)
            rows = [{"claim": claim, "name": name, "value": value, "operator": "eq"}
                    for (claim, name), value in zip((("live-actor-identity", "observed-role-counts"),
                    ("profile-resolution", "stable-profile-fingerprints"),
                    ("logical-commit", "consecutive-terminal-commits"),
                    ("engine-boundary", "terminal-policy-states")), values)]
        return {"kind": "acceleration-parity-v1", "passed": self.ready, "acceptedProof": False,
                "observedFrames": self.frames, "failures": deepcopy(self.failures), "roles": proof, "measurements": rows}

    def finish(self):
        if not self.ready and not self.failures:
            self.failures.append({"code": "acceleration-incomplete"})
        return self.result()
