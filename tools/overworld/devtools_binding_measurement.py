"""Pure current-owner binding witness; no emulator, input, writes or acceptance.

The public getContext return owns the simultaneous actor/owner comparison.
Later complete-queue samples keep that exact subject alive through one Walk
trace. This is not a rendered-motion or general transition proof.
"""
from copy import deepcopy

from tools.overworld.devtools_records import HANDLE_FIELDS, select_current_actor
from tools.overworld.spawn_identity import live_spawn_flags


KIND = "actor-binding-context-v1"
EVENTS = ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")
SUBJECT_KEYS = ("handle", "species", "role", "subjectIdentity")
GENERATIONS = ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration")
ENGINE_BINDING = ("pointer", "current_manager", "object_manager", "object_id", "object_map_id",
                  "encounter_generation", "script_id")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def integer(value, name, low=0, high=0xFFFFFFFF):
    require(type(value) is int and low <= value <= high, "invalid " + name)
    return value


def pointer(value, name, size=4):
    integer(value, name, 0x02000000, 0x02400000 - size)
    require(value % 4 == 0, "unaligned " + name)
    return value


def context(value):
    require(isinstance(value, dict), "missing owner context")
    for key in ("fieldEpoch", "mapGeneration"):
        integer(value.get(key), key, 1, 65535)
    integer(value.get("mapId"), "mapId", 0, 65535)
    return {key: value[key] for key in ("fieldEpoch", "mapGeneration", "mapId")}


def visible(actor):
    # The public header defines READY as ACTIVE|VISIBLE|CURRENT_MANAGER (7).
    return actor.get("active") is True and actor.get("species") == 19 \
        and actor.get("role") == "WILD" and actor.get("presentationAttached") is True \
        and type(actor.get("presentationState")) is int and actor["presentationState"] == 7


def checked_actor(actor, source, engine, pose, owner, frame):
    """Independently check raw native identity, then use the shared selector."""
    require(visible(actor), "selected Rattata is not a visible attached Wild actor")
    require(isinstance(source, dict) and isinstance(engine, dict) and isinstance(pose, dict),
            "missing native source, manager or pose")
    handle = actor.get("handle", {})
    require(set(handle) == set(HANDLE_FIELDS), "incomplete actor handle")
    # Slots 0..5 are land/surf; slot 6 is Wild Headbutt. Slot 7 is Follower.
    integer(handle.get("slot"), "Wild slot", 0, 6)
    for key in HANDLE_FIELDS[2:]:
        integer(handle.get(key), "handle " + key, 1, 65535)
    integer(handle.get("value"), "handle value", 1)
    require(handle["value"] == (handle["generation"] << 16) | handle["slot"],
            "handle value differs from its slot/generation")
    for key in GENERATIONS:
        integer(actor.get(key), key, 1)
    for key in ("form", "level"):
        integer(actor.get(key), key, 0 if key == "form" else 1, 65535)
        require(type(source.get(key)) is int and source[key] == actor[key], "source " + key + " differs")
    integer(actor.get("subjectIdentity"), "subject personality", 1)
    for key in ("active", "species", "personality", "object_id", "map_id", "encounter_generation"):
        integer(source.get(key), "source " + key)
    pointer(source.get("object"), "source object", 0x12C)
    pointer(engine.get("pointer"), "engine object", 0x12C)
    pointer(engine.get("object_manager"), "object manager")
    pointer(engine.get("current_manager"), "current manager")
    for key in ("object_id", "spawn_object_id", "object_map_id", "spawn_map_id",
                "current_map_id", "encounter_generation", "script_id"):
        integer(engine.get(key), "engine " + key)
    require(source["map_id"] == owner["mapId"], "source object is not on the owner map")
    require(live_spawn_flags(source["active"]) and source["species"] == 19
            and source["personality"] == actor["subjectIdentity"]
            and source["object"] == engine["pointer"]
            and engine.get("in_manager") is True and engine.get("active") is True
            and engine["object_manager"] == engine["current_manager"]
            and engine["object_id"] == engine["spawn_object_id"] == source["object_id"] == 224 + handle["slot"]
            and engine["object_map_id"] == engine["spawn_map_id"] == engine["current_map_id"] == source["map_id"]
            and engine["encounter_generation"] == source["encounter_generation"] == handle["encounterGeneration"]
            and engine["script_id"] == 2074, "native live identity differs")
    lookup = engine.get("id_lookup", {})
    require(lookup.get("status") == "complete" and lookup.get("pointer_matches") is True
            and type(lookup.get("eligible_count")) is int and lookup["eligible_count"] == 1
            and lookup.get("first_active_pointer") == source["object"], "stock object-ID lookup differs")
    flags = integer(pose.get("flags"), "object flags")
    # map_events_internal.h: ACTIVE is bit 0, SINGLE_MOVEMENT is bit 1,
    # BIT_VANISH is bit 9. A visible actor may have single movement active.
    require(flags & 1 and not flags & (1 << 9), "native object is inactive or hidden")
    for key in ("pos_x", "pos_y", "pos_z", "x", "y"):
        integer(pose.get(key), "object " + key, -0x80000000, 0x7FFFFFFF)
    checked = {**deepcopy(actor), "identityVerified": True,
               "sourceIdentity": deepcopy(source), "engineIdentity": deepcopy(engine),
               "engineObject": deepcopy(pose)}
    selected = select_current_actor({"frame": frame, "context": owner, "actors": [checked]}, checked)
    return selected, checked


class BindingMeasurement:
    def __init__(self, *, max_frames=900, max_native_cycles=4096):
        self.max_frames = integer(max_frames, "post-boot frame cap", 1, 900)
        self.max_native_cycles = integer(max_native_cycles, "post-boot native-cycle cap", 1, 4096)
        self.last_frame = self.first_frame = self.last_cycle = self.first_cycle = None
        self.last_actor_frame = None
        self.frames = self.identity_samples = self.receipt_count = 0
        self.last_sequence = None
        self.trace_sequences = {}
        self.trace_stream = None
        self.subject = self.binding_receipt = self.initial_snapshot = self.terminal_snapshot = None
        self.owner = self.walk_start = None
        self.unmeasured_motion = None
        self.lifecycle = []
        self.context_mismatches = self.identity_failures = 0
        self.failures = []
        self.closed = False
        self.group = "observation"

    def seed_trace_prefix(self, sequences):
        """Only the shared initial-prefix validator may supply this watermark."""
        require(self.first_frame is None and not self.trace_sequences and not self.closed,
                "trace prefix is not an initial boundary")
        require(isinstance(sequences, dict) and len(sequences) <= 16, "invalid initial trace streams")
        for stream, sequence in sequences.items():
            integer(stream, "initial trace stream", 1)
            integer(sequence, "initial trace sequence", 1)
        self.trace_sequences = deepcopy(sequences)

    def _fail(self, reason):
        if not self.failures:
            if self.group == "context": self.context_mismatches += 1
            if self.group == "identity": self.identity_failures += 1
            self.failures.append({"code": "binding-" + self.group + "-invalid",
                                  "frame": self.last_frame, "detail": str(reason)})

    def _receipt(self, data, snapshot, prior_cycle, prior_actor_frame):
        self.receipt_count += 1
        require(self.receipt_count <= 1024, "binding receipt bound exceeded")
        require(data.get("status") == "observed" and data.get("readError") is None
                and data.get("boundary") == "public-getContext-return", "missing native public-return observation")
        entry = integer(data.get("entryNativeCycle"), "entry native cycle")
        returned = integer(data.get("returnNativeCycle"), "return native cycle")
        require(entry <= returned <= snapshot["nativeCycle"] and
                (prior_cycle is None or returned >= prior_cycle), "stale or future public-return cycle")
        entered_frame = integer(data.get("entryActorFrame"), "entry actor frame")
        returned_frame = integer(data.get("returnActorFrame"), "return actor frame")
        require(entered_frame <= returned_frame <= snapshot["actorFrame"] and
                (prior_actor_frame is None or returned_frame >= prior_actor_frame), "stale or future public-return actor frame")
        pointer(data.get("fieldPointer"), "native field owner")
        field = data.get("fieldLifecycle", {})
        require(field.get("authenticated") is True and field.get("reason") is None
                and type(field.get("fieldReady")) is int and field["fieldReady"] == 1,
                "native field owner is unavailable or unauthenticated")
        pointer(field.get("controlPointer"), "field control")
        pointer(field.get("managerPointer"), "field overlay manager")
        require(field.get("managerExecState") == 2 and field.get("managerProcState") == 0,
                "native field owner is not in its active execution state")
        owner = context(data.get("ownerContext"))
        packed = integer(data.get("packedContext"), "packed public context", 1)
        require(type(data.get("returnValue")) is int and data["returnValue"] == packed,
                "packed context differs from the native return register")
        candidates = data.get("candidates")
        require(isinstance(candidates, list) and len(candidates) <= 7, "unbounded or missing native candidates")
        for candidate in candidates:
            require(isinstance(candidate, dict) and isinstance(candidate.get("publicSubject"), dict),
                    "malformed native candidate")
            integer(candidate.get("slot"), "candidate slot", 0, 6)
        require(len({candidate["slot"] for candidate in candidates}) == len(candidates), "duplicate candidate slot")
        # Eligibility never looks at owner/map generations, identityVerified,
        # or the reader's check verdict. A bad first subject cannot disappear.
        if self.subject is None:
            eligible = sorted((candidate for candidate in candidates if visible(candidate["publicSubject"])),
                              key=lambda candidate: candidate["slot"])
            if not eligible:
                return
            candidate = eligible[0]
        else:
            matches = [candidate for candidate in candidates
                       if candidate["slot"] == self.subject["handle"]["slot"]]
            self.group = "identity"
            require(len(matches) == 1, "selected subject absent at native context return")
            candidate = matches[0]
        actor = candidate["publicSubject"]
        self.group = "context"
        require(context(data.get("residentContext")) == owner and data.get("returnMatchesResident") is True,
                "public context differs from the same-return resident owner")
        require((packed & 65535, packed >> 16) == (owner["fieldEpoch"], owner["mapGeneration"]),
                "native getContext return differs from the field owner")
        require(all(actor.get("handle", {}).get(key) == owner[key]
                    for key in ("fieldEpoch", "mapGeneration")), "selected actor differs from same-return owner context")
        require(owner == context(snapshot.get("context")), "owner changed before the complete-queue sample")
        if self.owner is not None:
            require(owner == self.owner, "selected actor owner context changed")
        self.group = "identity"
        require(candidate["slot"] == actor.get("handle", {}).get("slot"), "native candidate slot differs")
        require(candidate.get("readError") is None, "native candidate read failed")
        checks = candidate.get("identityChecks")
        require(isinstance(checks, dict) and checks and all(value is True for value in checks.values()),
                "native candidate identity checks failed or are missing")
        selected, checked = checked_actor(actor, candidate.get("sourceIdentity"), candidate.get("engineIdentity"),
                                          candidate.get("engineObject"), owner, snapshot["frame"])
        if self.subject is not None:
            require(all(selected[key] == self.subject[key] for key in (*SUBJECT_KEYS, *GENERATIONS)),
                    "native return now names a replacement subject")
            require(all(selected["engineIdentity"][key] == self.subject["engineIdentity"][key] for key in ENGINE_BINDING),
                    "native return changed the selected engine binding")
        else:
            self.subject = selected
            self.owner = owner
            self.binding_receipt = deepcopy(data)
            self.initial_snapshot = {"frame": snapshot["frame"], "actorFrame": returned_frame,
                "nativeCycle": returned, "context": deepcopy(owner), "actors": [checked],
                "observationBoundary": "public-getContext-return", "prepared": False}
            if actor.get("motionKind") != "NONE" and actor.get("motionPhase") != "IDLE":
                kind = {"WALK": 1, "HOP": 2, "TELEPORT": 3, "REPOSITION": 5}.get(actor.get("motionKind"))
                require(kind is not None, "binding has an unknown existing motion")
                require(actor.get("motionPhase") in ("PLANNED", "MOVING", "COMMIT_PENDING", "SETTLING"),
                        "binding has a canceled or unknown existing motion")
                committed = actor["motionPhase"] == "SETTLING"
                self.unmeasured_motion = {"kind": kind,
                    "commit": (integer(actor.get("commitSequence"), "binding commit") + (not committed)) & 0xFFFFFFFF,
                    "next": 1 if committed else 0}

    def _identity(self, snapshot):
        self.group = "context"
        require(context(snapshot.get("context")) == self.owner, "selected owner context changed after binding")
        self.group = "identity"
        matches = [actor for actor in snapshot["actors"] if actor.get("handle") == self.subject["handle"]]
        require(len(matches) == 1, "selected subject disappeared or its handle changed")
        actor = matches[0]
        selected, _ = checked_actor(actor, actor.get("sourceIdentity"), actor.get("engineIdentity"),
                                    actor.get("engineObject"), context(snapshot.get("context")), snapshot["frame"])
        require(actor.get("identityVerified") is True, "complete-queue native identity check failed")
        require(all(selected[key] == self.subject[key] for key in (*SUBJECT_KEYS, *GENERATIONS)),
                "selected actor changed subject or presentation generation")
        require(all(selected["engineIdentity"][key] == self.subject["engineIdentity"][key] for key in ENGINE_BINDING),
                "selected actor changed engine binding")
        self.identity_samples += 1
        return actor

    def _trace(self, event, actor, snapshot):
        data = event["data"]
        handle = {"value": data.get("actorHandle"), **data.get("actor", {})}
        if handle != self.subject["handle"]:
            return
        self.group = "lifecycle"
        name = data.get("event")
        require(name != "MOTION_CANCELED", "selected actor motion was canceled")
        if len(self.lifecycle) == 4:
            return  # A successor is unmeasured; keep later identity/coverage checks.
        trace_frame = integer(data.get("actorFrame"), "semantic actor frame")
        require(trace_frame <= snapshot["actorFrame"], "semantic event is from a future actor frame")
        if trace_frame < self.initial_snapshot["actorFrame"]:
            return  # A trace that predates the native binding earns no credit.
        if trace_frame == self.initial_snapshot["actorFrame"]:
            if name == "MOTION_STARTED":
                if self.unmeasured_motion is None:
                    # There is no ordering clock within one actor frame. Keep
                    # this complete prefix, but require a later Walk for proof.
                    kind = integer(data.get("valueA"), "same-frame motion kind", 1, 5)
                    require(data.get("reason") == "OK", "same-frame start reason differs")
                    self.unmeasured_motion = {"kind": kind,
                        "commit": (self.initial_snapshot["actors"][0]["commitSequence"] + 1) & 0xFFFFFFFF,
                        "next": 0}
                return
            if self.unmeasured_motion is None:
                return  # Already-terminal native binding: these events predate it.
            if name == "LOGICAL_COMMIT" and self.unmeasured_motion["next"] == 1:
                return  # The native binding already observed SETTLING/this commit.
        if not self.lifecycle:
            if name in EVENTS[1:]:
                prior = self.unmeasured_motion
                require(prior is not None and name == EVENTS[prior["next"] + 1]
                        and data.get("reason") == "OK", "orphan terminal: selected motion start is missing")
                commit_field, kind_field, kind_value = ("valueB", "valueA", 0) if name == "CONTROL_RETURNED" else ("valueA", "valueB", prior["kind"])
                require(data.get(commit_field) == prior["commit"] and data.get(kind_field) == kind_value,
                        "unmeasured existing motion terminal differs")
                prior["next"] += 1
                if prior["next"] == 3: self.unmeasured_motion = None
                return
            if name != "MOTION_STARTED": return
            require(self.unmeasured_motion is None, "new motion before existing terminal completed")
            require(data.get("reason") == "OK", "Walk start reason differs")
            if data.get("valueA") != 1:
                kind = integer(data.get("valueA"), "unmeasured motion kind", 2, 5)
                self.unmeasured_motion = {"kind": kind,
                    "commit": (integer(actor.get("commitSequence"), "unmeasured start commit") + 1) & 0xFFFFFFFF, "next": 0}
                return
            integer(data.get("valueB"), "Walk duration", 1, 65535)
            require(actor.get("motionKind") == "WALK" and actor.get("motionPhase") in ("PLANNED", "MOVING")
                    and actor.get("motionElapsed") in (0, 1) and actor.get("motionDuration") == data["valueB"],
                    "Walk trace does not match the current actor motion")
            require(actor.get("origin") != actor.get("target"), "Walk has no displacement")
            self.walk_start = deepcopy(actor)
            self.trace_stream = data["traceStream"]
        else:
            if name not in (*EVENTS, "MOTION_CANCELED"):
                return
            expected = EVENTS[len(self.lifecycle)]
            require(name == expected and data.get("reason") == "OK", "Walk events are missing, duplicated or reordered")
            require(data["traceStream"] == self.trace_stream, "Walk trace changed stream")
            commit = (integer(self.walk_start.get("commitSequence"), "start commit") + 1) & 0xFFFFFFFF
            field, kind_field, kind_value = ("valueB", "valueA", 0) if name == "CONTROL_RETURNED" else ("valueA", "valueB", 1)
            require(type(data.get(field)) is int and data[field] == commit
                    and type(data.get(kind_field)) is int and data[kind_field] == kind_value,
                    "Walk terminal has a different commit or motion kind")
            if name == "CONTROL_RETURNED":
                require(actor.get("commitSequence") == commit and actor.get("logical") == self.walk_start["target"],
                        "Walk terminal snapshot lacks the committed destination")
                self.terminal_snapshot = deepcopy(snapshot)
        self.lifecycle.append(deepcopy(event))

    def observe(self, snapshot, events=()):
        if self.closed:
            raise ValueError("binding measurement is closed")
        if self.failures:
            return self.result()
        try:
            self.group = "observation"
            require(isinstance(snapshot, dict), "missing complete-queue snapshot")
            frame = integer(snapshot.get("frame"), "complete game frame")
            cycle = integer(snapshot.get("nativeCycle"), "native cycle")
            actor_frame = integer(snapshot.get("actorFrame"), "actor frame")
            prior_cycle, prior_actor_frame = self.last_cycle, self.last_actor_frame
            require(self.last_frame is None or frame == self.last_frame + 1, "complete frame missing, duplicated or reordered")
            require(prior_cycle is None or cycle >= prior_cycle, "native clock moved backwards")
            if self.first_frame is None:
                self.first_frame, self.first_cycle = frame, cycle
            self.last_frame, self.last_cycle, self.last_actor_frame = frame, cycle, actor_frame
            self.frames += 1
            require(frame - self.first_frame <= self.max_frames and cycle - self.first_cycle <= self.max_native_cycles,
                    "post-boot observation budget exceeded")
            require(snapshot.get("prepared") is False and snapshot.get("fieldAvailable") is True
                    and snapshot.get("observationBoundary") == "main-task-queue-completion",
                    "observation is prepared, field-absent or not a completed main queue")
            context(snapshot.get("context"))
            require(isinstance(snapshot.get("actors"), list), "missing actor list")
            coverage = snapshot.get("nativeObservation", {})
            require(coverage.get("installedBeforeBoot") is True and coverage.get("coverageComplete") is True
                    and coverage.get("eventsDropped") == 0 and coverage.get("profilesEvicted") == 0
                    and coverage.get("pendingUnframedEvents") == 0 and coverage.get("error") is None,
                    "native event coverage is incomplete")
            watermark = integer(coverage.get("sequence"), "native sequence watermark")
            require(isinstance(events, (tuple, list)) and len(events) <= 2048, "frame event bound exceeded")
            native = [event for event in events if event.get("kind") == "native-observation"]
            if self.last_sequence is None:
                self.last_sequence = integer(native[0].get("data", {}).get("sequence"), "initial native sequence", 1) - 1 if native else watermark
            traces = []
            for event in events:
                require(isinstance(event, dict) and event.get("frame") == frame and isinstance(event.get("data"), dict),
                        "event is not attached to its completed frame")
                data = event["data"]
                if event.get("kind") == "trace-status":
                    require(data.get("coverageComplete") is not False and data.get("code") not in
                            {"sequence-reset", "window-rearmed-externally", "unread-events-lost", "trace-filter-changed"},
                            "semantic trace coverage is incomplete")
                if event.get("kind") == "native":
                    stream = integer(data.get("traceStream"), "trace stream", 1)
                    sequence = integer(data.get("sequence"), "trace sequence", 1)
                    require(sequence == self.trace_sequences.get(stream, 0) + 1, "semantic event was lost or reordered")
                    self.trace_sequences[stream] = sequence
                    require(len(self.trace_sequences) <= 16, "trace stream bound exceeded")
                    require(isinstance(data.get("actor"), dict) and set(data["actor"]) == set(HANDLE_FIELDS) - {"value"},
                            "trace lacks complete actor identity")
                    for key in ("valueA", "valueB", "actorHandle"):
                        integer(data.get(key), "semantic " + key)
                    for key, value in data["actor"].items():
                        integer(value, "semantic handle " + key, 0 if key == "slot" else 1, 65535)
                    require(data["actorHandle"] == (data["actor"]["generation"] << 16) | data["actor"]["slot"],
                            "semantic actor handle differs")
                    traces.append(event)
                elif event.get("kind") == "native-observation":
                    require(data.get("setupMode") == "normal", "native observation used prepared setup")
                    sequence = integer(data.get("sequence"), "native sequence", 1)
                    require(sequence == self.last_sequence + 1, "native context receipt was lost or reordered")
                    self.last_sequence = sequence
                    if data.get("observation") == "actor-binding-context":
                        self._receipt(data, snapshot, prior_cycle, prior_actor_frame)
            self.group = "observation"
            require(self.last_sequence == watermark, "native receipts do not reach their watermark")
            if self.subject is not None:
                actor = self._identity(snapshot)
                for event in traces:
                    self._trace(event, actor, snapshot)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            self._fail(error)
        return self.result()

    def result(self):
        ready = self.subject is not None and len(self.lifecycle) == 4 and not self.failures
        return {"kind": KIND, "state": "failed" if self.failures else "completed" if self.closed and ready else "observing",
            "ready": ready, "passed": self.closed and ready, "acceptedProof": False,
            "bindingObserved": self.subject is not None, "subject": deepcopy(self.subject),
            "bindingReceipt": deepcopy(self.binding_receipt), "initialSnapshot": deepcopy(self.initial_snapshot),
            "terminalSnapshot": deepcopy(self.terminal_snapshot), "lifecycleEvents": deepcopy(self.lifecycle),
            "identitySamples": self.identity_samples, "observedFrames": max(0, self.frames - 1),
            "nativeCycles": self.last_cycle - self.first_cycle if self.first_cycle is not None else 0,
            "contextReceipts": self.receipt_count, "failures": deepcopy(self.failures),
            "measurements": {"binding-live-subject-count": int(self.subject is not None),
                "binding-owner-context-mismatch-count": self.context_mismatches,
                "binding-identity-failure-count": self.identity_failures},
            "scope": "one natural Wild Rattata owner binding and subsequent Walk terminal; no broad movement claim"}

    def finish(self):
        if not self.closed and not self.result()["ready"] and not self.failures:
            self.group = "identity" if self.receipt_count else "observation"
            self._fail("native context receipt missing" if not self.receipt_count else
                       "natural Rattata missing" if self.subject is None else "same-subject Walk lifecycle incomplete")
        self.closed = True
        return self.result()
