"""Bounded population refill after one normal mounted field crossing."""
from copy import deepcopy

from tools.overworld.devtools_records import HANDLE_FIELDS, select_current_actor


KIND = "population-fast-travel-v1"
REQUIREMENT = "legacy.population-after-fast-travel"
LIFECYCLE = ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def _lifetime(handle):
    return tuple(handle.get(key) for key in (
        "value", "slot", "generation", "encounterGeneration"))


def _event_handle(data):
    actor = data.get("actor")
    require(isinstance(actor, dict) and set(actor) == set(HANDLE_FIELDS) - {"value"},
            "population event lacks a full actor handle")
    return {"value": data.get("actorHandle"), **actor}


class PopulationFastTravelMeasurement:
    """Measure one Mankey crossing and the current-map refill to six actors."""

    def __init__(self, test, *, max_frames):
        require(type(max_frames) is int and 1 <= max_frames <= 1200,
                "invalid population fast-travel frame bound")
        require(test.get("mode") == "prepared"
                and test.get("fixture") == {"rom": "test.nds", "save": "test.sav"}
                and test.get("subjects") == [{
                    "id": "mankey", "species": 56,
                    "role": "MOUNTED", "acquire": "existing",
                }], "population fast travel requires one prepared Mankey mount")
        self.max_frames = max_frames
        self.initial = self.last = self.terminal = None
        self.subject = self.initial_subject = None
        self.actor_identity = None
        self.frames = 0
        self.map_changes = 0
        self.transition_population = None
        self.final_population = 0
        self.maximum_new_actors = 0
        self.previous_lifetimes = set()
        self.population_series = []
        self.lifecycle = []
        self.transition_events = []
        self.cancel_events = []
        self.mismatch_count = 0
        self.failures = []
        self.closed = False

    def _fail(self, reason):
        if not self.failures:
            self.failures.append(str(reason))

    @staticmethod
    def _active(snapshot):
        context = snapshot.get("context", {})
        active = [actor for actor in snapshot.get("actors", [])
                  if actor.get("active") is True]
        require(0 < len(active) <= 6, "population active count is outside 1..6")
        require(all(actor.get("identityVerified") is True
                    and actor.get("presentationAttached") is True
                    and actor.get("handle", {}).get("fieldEpoch") == context.get("fieldEpoch")
                    and actor.get("handle", {}).get("mapGeneration") == context.get("mapGeneration")
                    for actor in active),
                "population actor retained stale identity, context, or presentation")
        reservations = [actor.get("reservationId") for actor in active
                        if type(actor.get("reservationId")) is int
                        and actor.get("reservationId") != 0]
        require(len(reservations) == len(set(reservations)),
                "population actors share a nonzero target reservation")
        return active

    def _mount(self, snapshot):
        matches = [actor for actor in snapshot.get("actors", [])
                   if actor.get("active") is True
                   and _lifetime(actor.get("handle", {}))
                       == _lifetime(self.initial_subject["handle"])]
        require(len(matches) == 1, "population mounted Mankey is absent")
        actor = matches[0]
        expected = self.actor_identity
        keys = ("species", "form", "level", "role", "subjectIdentity",
                "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")
        if (any(actor.get(key) != expected.get(key) for key in keys)
                or actor.get("species") != 56 or actor.get("role") != "MOUNTED"
                or actor.get("identityVerified") is not True
                or actor.get("presentationAttached") is not True
                or actor.get("inputOwnership") != 1):
            self.mismatch_count += 1
            raise ValueError("population mounted Mankey identity differs")
        selected = select_current_actor(snapshot, actor)
        self.subject = deepcopy(selected)
        return actor

    def arm(self, receipt, snapshot):
        try:
            require(self.initial is None and self.subject is None,
                    "population fast travel was armed twice")
            selected = select_current_actor(snapshot, receipt)
            actor = next(item for item in snapshot["actors"]
                         if item.get("handle") == selected["handle"])
            require(snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot.get("context", {}).get("mapId") == 33
                    and snapshot.get("player", {}).get("x") == 576
                    and snapshot.get("player", {}).get("y") == 402
                    and actor.get("species") == 56
                    and actor.get("role") == "MOUNTED"
                    and actor.get("identityVerified") is True
                    and actor.get("presentationAttached") is True
                    and actor.get("inputOwnership") == 1
                    and actor.get("motionKind") == "NONE"
                    and actor.get("motionPhase") == "IDLE"
                    and actor.get("reservationId") == 0,
                    "population fast travel requires idle Mankey at the reviewed Route29 origin")
            active = self._active(snapshot)
            self.subject = self.initial_subject = deepcopy(selected)
            self.actor_identity = deepcopy(actor)
            self.initial = self.last = deepcopy(snapshot)
            self.previous_lifetimes = {_lifetime(item["handle"]) for item in active}
            self.population_series.append({
                "frame": snapshot["frame"], "mapId": 33,
                "total": len(active),
                "wild": sum(item.get("role") == "WILD" for item in active),
            })
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self._fail(error)
        return self.result()

    def _event(self, event):
        if event.get("kind") != "native" or self.initial_subject is None:
            return
        data = event.get("data", {})
        if data.get("actorHandle") != self.initial_subject["handle"]["value"]:
            return
        handle = _event_handle(data)
        require(_lifetime(handle) == _lifetime(self.initial_subject["handle"]),
                "population Mankey event changed actor lifetime")
        name = data.get("event")
        if name in LIFECYCLE:
            require(data.get("reason") == "OK",
                    "population Mankey lifecycle has a non-OK result")
            if name == "MOTION_STARTED":
                require(data.get("valueA") == 2,
                        "population fast travel used a non-Hop motion")
            self.lifecycle.append(deepcopy(event))
        elif name == "MOTION_CANCELED":
            self.cancel_events.append(deepcopy(event))
        elif name in ("CONTEXT_CHANGED", "ACTOR_REBOUND"):
            self.transition_events.append(deepcopy(event))

    def observe(self, snapshot, events):
        if self.failures or self.closed:
            return self.result()
        try:
            require(self.initial is not None and self.subject is not None,
                    "population fast travel observation preceded binding")
            require(isinstance(snapshot, dict) and isinstance(events, list)
                    and snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot.get("frame") == self.last["frame"] + 1
                    and snapshot.get("nativeCycle") >= self.last["nativeCycle"],
                    "population completed frame is missing or reordered")
            for event in events:
                self._event(event)
            active = self._active(snapshot)
            actor = self._mount(snapshot)
            current_lifetimes = {_lifetime(item["handle"]) for item in active}
            added = len(current_lifetimes - self.previous_lifetimes)
            self.maximum_new_actors = max(self.maximum_new_actors, added)
            require(added <= 1,
                    "population added more than one actor in a completed frame")
            context = snapshot["context"]
            initial_context = self.initial["context"]
            if context != initial_context:
                if self.map_changes == 0:
                    require(context.get("mapId") == 67
                            and context.get("fieldEpoch")
                                == ((initial_context["fieldEpoch"] + 1) & 0xFFFF or 1)
                            and context.get("mapGeneration")
                                == ((initial_context["mapGeneration"] + 1) & 0xFFFF or 1),
                            "population owner context did not advance once to Cherrygrove")
                    self.map_changes = 1
                    self.transition_population = len(active)
                else:
                    require(context.get("mapId") == 67
                            and context.get("fieldEpoch")
                                == ((initial_context["fieldEpoch"] + 1) & 0xFFFF or 1)
                            and context.get("mapGeneration")
                                == ((initial_context["mapGeneration"] + 1) & 0xFFFF or 1),
                            "population owner context changed more than once")
            elif self.map_changes:
                raise ValueError("population owner context reverted")
            total = len(active)
            if not self.population_series or total != self.population_series[-1]["total"] \
                    or context["mapId"] != self.population_series[-1]["mapId"]:
                self.population_series.append({
                    "frame": snapshot["frame"], "mapId": context["mapId"],
                    "total": total,
                    "wild": sum(item.get("role") == "WILD" for item in active),
                })
            self.final_population = total
            self.frames += 1
            require(self.frames <= self.max_frames,
                    "population fast travel frame bound exceeded")
            self.previous_lifetimes = current_lifetimes
            self.last = deepcopy(snapshot)
            if self.ready:
                require(actor.get("motionKind") == "NONE"
                        and actor.get("motionPhase") == "IDLE"
                        and actor.get("reservationId") == 0,
                        "population fast travel did not return idle mounted control")
                self.terminal = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self._fail(error)
        return self.result()

    @property
    def travel_distance(self):
        if self.initial is None or self.last is None:
            return 0
        return sum(abs(self.last["player"][key] - self.initial["player"][key])
                   for key in ("x", "y"))

    @property
    def ready(self):
        names = [event.get("data", {}).get("event") for event in self.lifecycle]
        transition = [event.get("data", {}).get("event") for event in self.transition_events]
        return (not self.failures and self.map_changes == 1
                and self.transition_population is not None
                and 0 <= self.transition_population < self.final_population == 6
                and self.maximum_new_actors <= 1 and self.mismatch_count == 0
                and not self.cancel_events and names == list(LIFECYCLE) * 2
                and transition == ["CONTEXT_CHANGED", "ACTOR_REBOUND"]
                and self.travel_distance > 1)

    def stage(self, name):
        if name != "refilled":
            raise ValueError("unknown population fast-travel stage")
        return self.ready

    def _validate_complete(self):
        require(self.map_changes == 1,
                "population fast travel did not cross one field boundary")
        require(not self.cancel_events and [event["data"]["event"] for event in self.lifecycle]
                == list(LIFECYCLE) * 2,
                "population fast travel lacks two complete Mankey Hops")
        require([event["data"]["event"] for event in self.transition_events]
                == ["CONTEXT_CHANGED", "ACTOR_REBOUND"],
                "population transition trace differs")
        sequence = [event["data"]["sequence"] for event in
                    [*self.lifecycle[:4], self.lifecycle[4],
                     *self.transition_events, *self.lifecycle[5:]]]
        require(sequence == sorted(set(sequence)),
                "population Mankey lifecycle and transition order differs")
        require(self.transition_population is not None
                and 0 <= self.transition_population < self.final_population == 6,
                "population fast travel did not reach six current actors")
        require(self.maximum_new_actors <= 1,
                "population added more than one actor in a completed frame")
        require(self.travel_distance > 1,
                "population fast travel did not use meaningful normal input")
        require(self.mismatch_count == 0,
                "population mounted Mankey identity differs")

    def finish(self):
        if not self.failures:
            try:
                self._validate_complete()
            except (ValueError, KeyError, TypeError) as error:
                self._fail(error)
        self.closed = True
        return self.result()

    def result(self):
        return {
            "kind": KIND,
            "requirements": [REQUIREMENT],
            "passed": self.closed and self.ready,
            "ready": self.ready,
            "closed": self.closed,
            "acceptedProof": False,
            "failures": list(self.failures),
            "frames": self.frames,
            "initial": deepcopy(self.initial),
            "terminal": deepcopy(self.terminal),
            "subject": deepcopy(self.subject),
            "initialSubject": deepcopy(self.initial_subject),
            "populationSeries": deepcopy(self.population_series),
            "transitionPopulation": self.transition_population,
            "finalPopulation": self.final_population,
            "maximumNewActorsPerFrame": self.maximum_new_actors,
            "mismatchCount": self.mismatch_count,
            "travelDistance": self.travel_distance,
            "mapChanges": self.map_changes,
            "lifecycle": deepcopy(self.lifecycle),
            "transitionEvents": deepcopy(self.transition_events),
            "cancelEvents": deepcopy(self.cancel_events),
        }
