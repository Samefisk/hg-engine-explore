"""Acceptance rows and copied-data controls for mounted population refill."""
from copy import deepcopy

from tools.overworld.devtools_population_fast_travel_measurement import (
    KIND,
    REQUIREMENT,
    require,
)
from tools.overworld.devtools_records import select_current_actor


CLAIMS = ("natural-input", "live-actor-identity", "population-bounds", "world-transition")
FAULTS = (
    "population-absent-mount",
    "population-burst-refill",
    "population-missing-refill",
    "population-missing-transition",
)


def contract():
    return {
        "natural-input": [{
            "name": "input-travel-distance", "operator": "gt",
            "type": "integer", "validator": "meaningful-observation", "minimum": 1,
        }],
        "live-actor-identity": [
            {
                "name": "population-mankey-identity", "operator": "eq",
                "type": "array", "validator": "meaningful-observation",
                "expected": [1, "MOUNTED", 56, 1],
            },
            {
                "name": "fast-travel-actor-mismatch-count", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation", "expected": 0,
            },
        ],
        "population-bounds": [
            {
                "name": "maximum-new-actors-per-frame", "operator": "lte",
                "type": "integer", "validator": "meaningful-observation",
                "minimum": 0, "maximum": 1,
            },
            {
                "name": "population-refill", "operator": "eq",
                "type": "array", "validator": "population-refill-v1",
            },
        ],
        "world-transition": [{
            "name": "map-and-field-epoch-change", "operator": "eq",
            "type": "array", "validator": "meaningful-observation", "expected": [1, 1],
        }],
    }


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    require(replay.get("passed") is True and replay.get("failures") == []
            and meter.get("passed") is True and meter.get("ready") is True
            and meter.get("closed") is True and meter.get("acceptedProof") is False
            and meter.get("failures") == []
            and meter.get("requirements") == [REQUIREMENT],
            "population fast travel lacks closed independent replay")
    require(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": [],
    }, "population fast-travel private session did not close cleanly")
    initial, terminal = meter["initial"], meter["terminal"]
    selected = select_current_actor(terminal, meter["subject"])
    actor = next(item for item in terminal["actors"]
                 if item.get("handle") == selected["handle"])
    source, engine = actor.get("sourceIdentity", {}), actor.get("engineIdentity", {})
    require(actor.get("active") is True and actor.get("role") == "MOUNTED"
            and actor.get("species") == 56 and actor.get("identityVerified") is True
            and actor.get("presentationAttached") is True and actor.get("inputOwnership") == 1
            and actor.get("motionKind") == "NONE" and actor.get("motionPhase") == "IDLE"
            and actor.get("reservationId") == 0
            and source.get("active") == 1 and source.get("species") == 56
            and source.get("personality") == actor.get("subjectIdentity")
            and source.get("map_id") == 67
            and engine.get("active") is True and engine.get("in_manager") is True
            and engine.get("current_map_id") == 67 and engine.get("object_map_id") == 67,
            "population refill lacks one current mounted Mankey")
    population = [meter["transitionPopulation"], meter["finalPopulation"], 6]
    require(0 <= population[0] < population[1] == population[2]
            and meter["maximumNewActorsPerFrame"] <= 1
            and meter["mismatchCount"] == 0
            and meter["travelDistance"] > 1
            and meter["mapChanges"] == 1
            and terminal["context"]["fieldEpoch"]
                == ((initial["context"]["fieldEpoch"] + 1) & 0xFFFF or 1),
            "population refill measurements differ from the stored contract")
    values = (
        ("natural-input", "input-travel-distance", meter["travelDistance"], "gt", 1),
        ("live-actor-identity", "population-mankey-identity",
         [1, actor["role"], actor["species"], int(actor["identityVerified"] is True)],
         "eq", [1, "MOUNTED", 56, 1]),
        ("live-actor-identity", "fast-travel-actor-mismatch-count",
         meter["mismatchCount"], "eq", 0),
        ("population-bounds", "maximum-new-actors-per-frame",
         meter["maximumNewActorsPerFrame"], "lte", 1),
        ("population-bounds", "population-refill", population, "eq", population),
        ("world-transition", "map-and-field-epoch-change",
         [meter["mapChanges"], terminal["context"]["fieldEpoch"]
          - initial["context"]["fieldEpoch"]], "eq", [1, 1]),
    )
    return [{
        "claim": claim, "name": name, "value": deepcopy(value),
        "operator": operator,
        **({"minimum": expected} if operator == "gt" else
           {"maximum": expected} if operator == "lte" else
           {"expected": deepcopy(expected)}),
        "passed": True,
    } for claim, name, value, operator, expected in values]


class PopulationFastTravelNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown population fast-travel copied fault")
        self.fault = fault
        self.applied = False
        self.removed_lifetime = None

    @staticmethod
    def _same_lifetime(actor, subject):
        return all(actor.get("handle", {}).get(key) == subject.get("handle", {}).get(key)
                   for key in ("value", "slot", "generation", "encounterGeneration"))

    @staticmethod
    def _active(sample):
        return [actor for actor in sample.get("actors", []) if actor.get("active") is True]

    def mutate(self, row, subjects):
        if row.get("phase") != "observe" or not subjects:
            return row
        changed = deepcopy(row)
        subject = next(iter(subjects.values()))
        if self.fault == "population-absent-mount" and not self.applied:
            for sample in changed.get("samples", []):
                actor = next((item for item in sample.get("actors", [])
                              if self._same_lifetime(item, subject)), None)
                if actor is not None:
                    sample["actors"].remove(actor)
                    self.applied = True
                    return changed
            return row
        if self.fault == "population-missing-transition" and not self.applied:
            for event in changed.get("events", []):
                data = event.get("data", {})
                if (data.get("actorHandle") == subject["handle"]["value"]
                        and data.get("event") == "CONTEXT_CHANGED"):
                    data["event"] = "WORLD_EFFECT"
                    self.applied = True
                    return changed
            return row
        if self.fault == "population-burst-refill" and not self.applied:
            for sample in changed.get("samples", []):
                removable = [item for item in self._active(sample)
                             if item.get("role") == "WILD"]
                if len(removable) >= 2:
                    for actor in removable[-2:]:
                        sample["actors"].remove(actor)
                    self.applied = True
                    return changed
            return row
        if self.fault == "population-missing-refill":
            for sample in changed.get("samples", []):
                active = self._active(sample)
                if self.removed_lifetime is None and len(active) == 6:
                    actor = next((item for item in reversed(active)
                                  if item.get("role") == "WILD"), None)
                    if actor is not None:
                        self.removed_lifetime = tuple(actor["handle"].get(key) for key in
                            ("value", "slot", "generation", "encounterGeneration"))
                        self.applied = True
                if self.removed_lifetime is not None:
                    actor = next((item for item in sample.get("actors", [])
                                  if tuple(item.get("handle", {}).get(key) for key in
                                      ("value", "slot", "generation", "encounterGeneration"))
                                  == self.removed_lifetime), None)
                    if actor is not None:
                        sample["actors"].remove(actor)
            return changed if self.applied else row
        return row


Negative = PopulationFastTravelNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "population fast-travel copied control did not fail")
    text = repr(result.get("failures", [])) + repr(
        result.get("measurements", {}).get(KIND, {}).get("failures", []))
    expected = {
        "population-absent-mount": "population mounted Mankey is absent",
        "population-burst-refill": "population added more than one actor in a completed frame",
        "population-missing-refill": "population fast travel did not reach six current actors",
        "population-missing-transition": "population transition trace differs",
    }[fault]
    require(expected in text,
            "population fast-travel copied control failed for an unrelated reason: " + fault)
