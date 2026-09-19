"""Acceptance rows and copied-data controls for Wild field rebind."""
from copy import deepcopy

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_wild_transition_measurement import KIND, LIFECYCLE, REQUIREMENT
from tools.overworld.spawn_identity import live_spawn_flags


CLAIMS = ("natural-input", "live-actor-identity", "world-transition", "control-release")
FAULTS = (
    "wild-transition-absent-subject",
    "wild-transition-missing-motion",
    "wild-transition-missing-context",
    "wild-transition-old-handle-live",
    "wild-transition-missing-recovery",
)


def contract():
    return {
        "natural-input": [{
            "name": "wild-transition-acquisition-and-motion", "operator": "eq",
            "type": "array", "validator": "meaningful-observation", "expected": [1, 1],
        }],
        "live-actor-identity": [
            {
                "name": "wild-transition-role", "operator": "eq", "type": "string",
                "validator": "meaningful-observation", "expected": "WILD",
            },
            {
                "name": "wild-transition-identity-flags", "operator": "eq",
                "type": "array", "validator": "meaningful-observation",
                "expected": [1, "WILD", 19, 1, 1, 1, 1],
            },
        ],
        "world-transition": [
            {
                "name": "wild-transition-map-change", "operator": "eq",
                "type": "array", "validator": "meaningful-observation", "expected": [1, 67],
            },
            {
                "name": "wild-transition-old-handle-invalidated", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation", "expected": 1,
            },
        ],
        "control-release": [{
            "name": "wild-transition-player-recovery", "operator": "eq",
            "type": "integer", "validator": "meaningful-observation", "expected": 1,
        }],
    }


def require(value, reason):
    if not value:
        raise ValueError(reason)


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    require(replay.get("passed") is True and replay.get("failures") == []
            and meter.get("passed") is True and meter.get("ready") is True
            and meter.get("closed") is True and meter.get("acceptedProof") is False
            and meter.get("failures") == [],
            "Wild transition lacks closed independent replay")
    require(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": [],
    }, "Wild transition private session did not close cleanly")
    initial, terminal = meter["initial"], meter["terminal"]
    initial_subject, subject = meter["initialSubject"], meter["subject"]
    selected = select_current_actor(initial, initial_subject)
    actor = next(item for item in initial["actors"] if item.get("handle") == selected["handle"])
    rebound_selected = select_current_actor(terminal, subject)
    rebound = next(item for item in terminal["actors"]
                   if item.get("handle") == rebound_selected["handle"])
    source, engine = rebound["sourceIdentity"], rebound["engineIdentity"]
    require(actor.get("active") is True and actor.get("role") == "WILD"
            and actor.get("species") == 19 and actor.get("identityVerified") is True
            and actor.get("presentationAttached") is True
            and rebound.get("active") is True and rebound.get("role") == "WILD"
            and rebound.get("species") == 19 and rebound.get("identityVerified") is True
            and rebound.get("presentationAttached") is True
            and rebound.get("subjectIdentity") == actor.get("subjectIdentity")
            and live_spawn_flags(source.get("active")) and source.get("species") == 19
            and source.get("personality") == rebound.get("subjectIdentity")
            and source.get("map_id") == 67
            and engine.get("active") is True and engine.get("in_manager") is True
            and engine.get("current_map_id") == 67 and engine.get("object_map_id") == 67,
            "Wild transition lacks current Rattata identity")
    lifecycle = meter.get("lifecycle", [])
    require([event.get("data", {}).get("event") for event in lifecycle] == list(LIFECYCLE)
            and all(event.get("data", {}).get("actor")
                    == {key: value for key, value in initial_subject["handle"].items() if key != "value"}
                    and event.get("data", {}).get("actorHandle") == initial_subject["handle"]["value"]
                    and event.get("data", {}).get("reason") == "OK"
                    for event in lifecycle),
            "Wild transition lacks one bound natural Walk")
    transition = meter.get("transitionEvents", [])
    require([event.get("data", {}).get("event") for event in transition]
                == ["CONTEXT_CHANGED", "ACTOR_REBOUND"]
            and transition[0]["data"].get("reason") == "CONTEXT_LOST"
            and transition[1]["data"].get("reason") == "OK"
            and transition[0]["data"].get("valueA") == initial["context"]["fieldEpoch"]
            and transition[0]["data"].get("valueB") == terminal["context"]["fieldEpoch"]
            and transition[1]["data"].get("valueA") == 33
            and transition[1]["data"].get("valueB") == 67
            and transition[0]["data"]["sequence"] < transition[1]["data"]["sequence"],
            "Wild transition context and rebind trace differs")
    old, current = initial_subject["handle"], subject["handle"]
    require(terminal["context"]["mapId"] == 67
            and terminal["context"]["fieldEpoch"] == ((initial["context"]["fieldEpoch"] + 1) & 0xFFFF or 1)
            and terminal["context"]["mapGeneration"] == ((initial["context"]["mapGeneration"] + 1) & 0xFFFF or 1)
            and all(old[key] == current[key] for key in (
                "value", "slot", "generation", "encounterGeneration"))
            and current["fieldEpoch"] == terminal["context"]["fieldEpoch"]
            and current["mapGeneration"] == terminal["context"]["mapGeneration"]
            and not any(item.get("active") is True and item.get("handle") == old
                        for item in terminal.get("actors", []))
            and meter.get("mapChanges") == 1 and meter.get("oldHandleInvalidated") is True,
            "Wild transition did not invalidate the prior field handle")
    require(meter.get("playerRecovered") is True
            and terminal.get("player", {}).get("x") == 574
            and terminal.get("player", {}).get("y") == 400,
            "Wild transition did not restore player control")
    identity = [1, rebound["role"], rebound["species"],
                int(rebound.get("identityVerified") is True),
                int(rebound.get("presentationAttached") is True),
                int(live_spawn_flags(source.get("active"))),
                int(engine.get("active") is True and engine.get("in_manager") is True)]
    values = (
        ("natural-input", "wild-transition-acquisition-and-motion", [1, 1]),
        ("live-actor-identity", "wild-transition-role", rebound["role"]),
        ("live-actor-identity", "wild-transition-identity-flags", identity),
        ("world-transition", "wild-transition-map-change", [meter["mapChanges"], terminal["context"]["mapId"]]),
        ("world-transition", "wild-transition-old-handle-invalidated", int(meter["oldHandleInvalidated"])),
        ("control-release", "wild-transition-player-recovery", int(meter["playerRecovered"])),
    )
    return [{"claim": claim, "name": name, "value": deepcopy(value),
             "operator": "eq", "expected": deepcopy(value), "passed": True}
            for claim, name, value in values]


class WildTransitionNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown Wild transition fault")
        self.fault = fault
        self.applied = False

    def mutate(self, row, subjects):
        if (self.applied and self.fault != "wild-transition-missing-recovery") \
                or row.get("phase") != "observe" or not subjects:
            return row
        changed = deepcopy(row)
        subject = next(iter(subjects.values()))
        old = subject["handle"]
        if self.fault in ("wild-transition-missing-motion", "wild-transition-missing-context"):
            wanted = "MOTION_STARTED" if self.fault.endswith("motion") else "CONTEXT_CHANGED"
            for event in changed.get("events", []):
                data = event.get("data", {})
                if data.get("actorHandle") == old["value"] and data.get("event") == wanted:
                    data["event"] = "WORLD_EFFECT"
                    self.applied = True
                    break
        for sample in changed.get("samples", []):
            actors = sample.get("actors", [])
            if self.fault == "wild-transition-absent-subject" \
                    and sample.get("context") == row.get("samples", [{}])[0].get("context"):
                match = next((actor for actor in actors if actor.get("handle") == old), None)
                if match is not None:
                    actors.remove(match)
                    self.applied = True
                    break
            if self.fault == "wild-transition-old-handle-live" \
                    and sample.get("context", {}).get("mapId") == 67:
                actor = deepcopy(subject)
                actor["active"] = True
                actors.append(actor)
                self.applied = True
                break
            if self.fault == "wild-transition-missing-recovery" \
                    and sample.get("context", {}).get("mapId") == 67 \
                    and sample.get("player", {}).get("x") == 574:
                sample["player"]["x"] = 575
                sample["player"]["x_prev"] = 575
                sample["player"]["pos_x"] += 65536
                self.applied = True
                break
        return changed if self.applied else row


Negative = WildTransitionNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "Wild transition copied control did not fail")
    text = repr(result.get("failures", [])) + repr(
        result.get("measurements", {}).get(KIND, {}).get("failures", []))
    expected = {
        "wild-transition-absent-subject": "selected handle must name exactly one current active actor",
        "wild-transition-missing-motion": "before one natural Wild motion",
        "wild-transition-missing-context": "context",
        "wild-transition-old-handle-live": "old Wild handle remained active",
        "wild-transition-missing-recovery": "restore player control",
    }[fault]
    require(expected in text,
            "Wild transition copied control failed for an unrelated reason: " + fault)
