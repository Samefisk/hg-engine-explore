"""Bounded replay for one Wild actor invalidated by a field transition.

The shared worker owns input and capture.  This meter only consumes its typed
recipe records.  Prepared spawning selects one exact actor; all route and
recovery credit comes from normal player input after that setup.
"""
from copy import deepcopy

from tools.overworld.devtools_movement_predicates import player_settled_at
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import HANDLE_FIELDS, select_current_actor
from tools.overworld.spawn_identity import live_spawn_flags


KIND = "wild-transition-invalidation-v1"
REQUIREMENT = "legacy.wild-transition"
LIFECYCLE = ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def full_event_handle(data):
    actor = data.get("actor")
    require(isinstance(actor, dict) and set(actor) == set(HANDLE_FIELDS) - {"value"},
            "transition event lacks a full actor handle")
    return {"value": data.get("actorHandle"), **actor}


def same_actor_lifetime(left, right):
    return all(left.get(key) == right.get(key) for key in (
        "value", "slot", "generation", "encounterGeneration"))


class WildTransitionMeasurement:
    def __init__(self, test, *, max_frames, kind=KIND, requirement=REQUIREMENT,
                 subject_id="rattata", species=19, role="WILD", acquire="spawn"):
        require(type(max_frames) is int and 1 <= max_frames <= 65535,
                "invalid Wild transition frame bound")
        require(test.get("mode") == "prepared"
                and test.get("fixture") == {"rom": "test.nds", "save": "test.sav"},
                "Wild transition requires the prepared disposable test.sav fixture")
        subjects = test.get("subjects")
        require(subjects == [{"id": subject_id, "species": species,
                              "role": role, "acquire": acquire}],
                "field transition requires one exact actor")
        self.kind = kind
        self.requirement = requirement
        self.subject_id = subject_id
        self.species = species
        self.role = role
        self.actions = {(phase, action["id"]): deepcopy(action)
                        for phase, name in (("setup", "setup"), ("observe", "actions"))
                        for action in test.get(name, [])}
        require(len(self.actions) == len(test.get("setup", [])) + len(test.get("actions", [])),
                "Wild transition action IDs must be distinct")
        self.max_frames = max_frames
        self.latest = self.subject = self.initial_subject = None
        self.initial = self.terminal = self.rebound_handle = None
        self.frames = self.map_changes = 0
        self.lifecycle = []
        self.transition_events = []
        self.trace_sequences = {}
        self.old_handle_absent = False
        self.player_recovered = False
        self.failures = []
        self._closed = False

    def _fail(self, reason):
        if not self.failures:
            self.failures.append(str(reason))

    def _current_actor(self, snapshot):
        selected = select_current_actor(snapshot, self.subject)
        return next(actor for actor in snapshot["actors"]
                    if actor.get("handle") == selected["handle"])

    def _bind(self, snapshot, receipt):
        require(self.subject is None and self.initial is None,
                "Wild transition subject was bound twice")
        selected = select_current_actor(snapshot, receipt)
        actor = next(item for item in snapshot["actors"]
                     if item.get("handle") == selected["handle"])
        source, engine = actor.get("sourceIdentity", {}), actor.get("engineIdentity", {})
        require(actor.get("active") is True and actor.get("role") == self.role
                and actor.get("species") == self.species and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True
                and live_spawn_flags(source.get("active")) and source.get("species") == self.species
                and source.get("personality") == actor.get("subjectIdentity")
                and engine.get("active") is True and engine.get("in_manager") is True
                and engine.get("current_map_id") == snapshot["context"]["mapId"],
                "bound field actor lacks current live identity")
        self.subject = deepcopy(selected)
        self.initial_subject = deepcopy(selected)
        self.initial = deepcopy(snapshot)
        self.latest = deepcopy(snapshot)

    def _event(self, event):
        if event.get("kind") != "native":
            return
        data = event.get("data", {})
        handle = full_event_handle(data)
        if self.initial_subject is None:
            return
        name = data.get("event")
        old_handle = self.initial_subject["handle"]
        if name == "ACTOR_REBOUND" and same_actor_lifetime(handle, old_handle):
            old_context = self.initial["context"]
            require(self.rebound_handle is None
                    and handle.get("fieldEpoch") == ((old_context["fieldEpoch"] + 1) & 0xFFFF or 1)
                    and handle.get("mapGeneration") == ((old_context["mapGeneration"] + 1) & 0xFFFF or 1)
                    and data.get("reason") == "OK"
                    and data.get("valueA") == 33 and data.get("valueB") == 67,
                    "Wild transition rebound trace differs")
            self.rebound_handle = deepcopy(handle)
            self.transition_events.append(deepcopy(event))
            return
        if handle != old_handle:
            return
        if name in LIFECYCLE and self.map_changes == 0:
            if len(self.lifecycle) == len(LIFECYCLE):
                return
            if not self.lifecycle:
                if name != LIFECYCLE[0]:
                    return  # motion already in flight when the subject was bound
                require(data.get("reason") == "OK" and data.get("valueA") == 1,
                        "Wild transition precondition did not start one Walk")
            else:
                expected = LIFECYCLE[len(self.lifecycle)]
                require(name == expected and data.get("reason") == "OK",
                        "Wild transition precondition lifecycle is incomplete or reordered")
            self.lifecycle.append(deepcopy(event))
            require(len(self.lifecycle) <= len(LIFECYCLE),
                    "Wild transition observed more than one precondition motion")
            return
        if name == "CONTEXT_CHANGED":
            require(data.get("reason") == "CONTEXT_LOST"
                    and data.get("valueA") == self.initial["context"]["fieldEpoch"],
                    "Wild transition context trace differs")
            self.transition_events.append(deepcopy(event))

    def observe(self, snapshot, events):
        if self.failures or self._closed:
            return self.result()
        try:
            require(self.subject is not None and self.initial is not None,
                    "Wild transition observation preceded binding")
            require(isinstance(snapshot, dict) and isinstance(events, list),
                    "Wild transition sample is malformed")
            require(type(snapshot.get("frame")) is int
                    and self.latest["frame"] < snapshot["frame"],
                    "Wild transition frames are missing or reordered")
            for event in events:
                self._event(event)
            old_context = self.initial["context"]
            context = snapshot.get("context", {})
            if context != old_context:
                if self.map_changes == 0:
                    require(len(self.lifecycle) == len(LIFECYCLE),
                            "Wild transition occurred before one natural Wild motion")
                    require(context.get("mapId") == 67
                            and context.get("fieldEpoch") == ((old_context["fieldEpoch"] + 1) & 0xFFFF or 1)
                            and context.get("mapGeneration") == ((old_context["mapGeneration"] + 1) & 0xFFFF or 1),
                            "Wild transition owner context did not advance once to Cherrygrove")
                    self.map_changes = 1
                else:
                    require(context == self.terminal["context"],
                            "Wild transition changed owner context more than once")
                current = [actor for actor in snapshot.get("actors", [])
                           if actor.get("active") is True]
                require(not any(actor.get("handle") == self.initial_subject["handle"] for actor in current),
                        "old Wild handle remained active after transition")
                require(all(actor.get("handle", {}).get("fieldEpoch") == context["fieldEpoch"]
                            and actor.get("handle", {}).get("mapGeneration") == context["mapGeneration"]
                            for actor in current),
                        "active actor retained a stale field context")
                rebound = [actor for actor in current
                           if actor.get("handle") == self.rebound_handle]
                require(len(rebound) == 1, "Wild transition did not retain its rebound actor")
                actor = rebound[0]
                source, engine = actor.get("sourceIdentity", {}), actor.get("engineIdentity", {})
                require(actor.get("role") == self.role and actor.get("species") == self.species
                        and actor.get("subjectIdentity") == self.initial_subject["subjectIdentity"]
                        and actor.get("identityVerified") is True
                        and actor.get("presentationAttached") is True
                        and live_spawn_flags(source.get("active")) and source.get("species") == self.species
                        and source.get("personality") == actor.get("subjectIdentity")
                        and source.get("map_id") == 67
                        and engine.get("active") is True and engine.get("in_manager") is True
                        and engine.get("current_map_id") == 67
                        and engine.get("object_map_id") == 67,
                        "rebound field actor lacks current live identity")
                self.subject = select_current_actor(snapshot, actor)
                self.old_handle_absent = True
                self.terminal = deepcopy(snapshot)
                if player_settled_at(snapshot, 67, 574, 400):
                    self.player_recovered = True
            elif self.map_changes:
                raise ValueError("Wild transition owner context reverted")
            else:
                self._current_actor(snapshot)
            self.frames += 1
            require(self.frames <= self.max_frames,
                    "Wild transition exceeded its completed-frame bound")
            self.latest = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self._fail(error)
        return self.result()

    def observe_record(self, record, *, frame_callback=None, full_report=True):
        if self.failures or self._closed:
            return self.result()
        try:
            require(isinstance(record, dict), "Wild transition record is malformed")
            if "initialSnapshot" in record:
                require(self.latest is None, "duplicate Wild transition initial snapshot")
                self.latest = deepcopy(record["initialSnapshot"])
                if frame_callback:
                    frame_callback(self.latest, (), self)
                return self.result()
            require(self.latest is not None, "Wild transition initial snapshot is missing")
            phase = record.get("phase")
            action = self.actions.get((phase, record.get("action")))
            require(action is not None, "Wild transition record names an unknown action")
            command = record.get("command")
            if command in ("party", "spawn"):
                require(phase == "setup" and action["op"] == command
                        and record.get("receipt", {}).get("preparedOnly") is True,
                        "field transition prepared setup differs")
                traces = record["receipt"].get("setupBoundary", {}).get("traceSequences")
                require(isinstance(traces, dict)
                        and all(isinstance(stream, str) and stream.isdecimal()
                                and str(int(stream)) == stream and 0 < int(stream) <= 1000000
                                and type(sequence) is int and 0 <= sequence <= 0xFFFFFFFF
                                for stream, sequence in traces.items()),
                        "field transition setup trace watermark differs")
                self.trace_sequences = {int(stream): sequence for stream, sequence in traces.items()}
                self.latest = deepcopy(record["snapshot"])
                if frame_callback:
                    frame_callback(self.latest, (), self)
                return self.result()
            if command == "bind":
                require(phase == "setup" and action["op"] == "bind"
                        and record.get("snapshot") == self.latest,
                        "Wild transition bind boundary differs")
                self._bind(record["snapshot"], record["receipt"])
                return self.result()
            require(command is None and action["op"] in ("step", "wait"),
                    "Wild transition has an unsupported command")
            rows = validate_raw_chunk(record, self.latest)
            for snapshot, events, _ in rows:
                self.observe(snapshot, events)
                if self.failures:
                    break
                if frame_callback:
                    frame_callback(snapshot, events, self)
            require(self.latest["frame"] == record["samples"][-1]["frame"],
                    "Wild transition chunk did not reach its endpoint")
        except (ValueError, KeyError, TypeError, IndexError) as error:
            self._fail(error)
        return self.result()

    def stage(self, name):
        if name != "natural-motion-complete":
            raise ValueError("unknown Wild transition stage")
        return len(self.lifecycle) == len(LIFECYCLE) and not self.failures

    @property
    def ready(self):
        names = [event["data"]["event"] for event in self.transition_events]
        return (not self.failures and len(self.lifecycle) == len(LIFECYCLE)
                and self.map_changes == 1 and self.old_handle_absent
                and names.count("CONTEXT_CHANGED") == 1
                and names.count("ACTOR_REBOUND") == 1
                and self.player_recovered)

    def finish(self):
        if not self.ready and not self.failures:
            self._fail("Wild transition did not complete context rebind and restore player control")
        self._closed = True
        return self.result()

    def result(self):
        return {
            "kind": self.kind,
            "requirements": [self.requirement],
            "passed": self._closed and self.ready,
            "ready": self.ready,
            "closed": self._closed,
            "acceptedProof": False,
            "failures": list(self.failures),
            "frames": self.frames,
            "subject": deepcopy(self.subject),
            "initialSubject": deepcopy(self.initial_subject),
            "initial": deepcopy(self.initial),
            "terminal": deepcopy(self.terminal),
            "lifecycle": deepcopy(self.lifecycle),
            "transitionEvents": deepcopy(self.transition_events),
            "mapChanges": self.map_changes,
            "oldHandleInvalidated": self.old_handle_absent,
            "playerRecovered": self.player_recovered,
        }
