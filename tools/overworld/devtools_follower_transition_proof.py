"""Acceptance rows for the bounded unmounted follower field rebind."""
from copy import deepcopy

from tools.overworld.devtools_follower_transition_measurement import KIND, REQUIREMENT
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_wild_transition_measurement import LIFECYCLE
from tools.overworld.devtools_wild_transition_proof import (
    FAULTS,
    WildTransitionNegative,
)
from tools.overworld.spawn_identity import live_spawn_flags


CLAIMS = ("natural-input", "live-actor-identity", "world-transition", "control-release")

class FollowerTransitionNegative(WildTransitionNegative):
    def mutate(self, row, subjects):
        if self.fault != "wild-transition-missing-motion":
            return super().mutate(row, subjects)
        if row.get("phase") != "observe" or not subjects:
            return row
        changed = deepcopy(row)
        old = next(iter(subjects.values()))["handle"]
        row_changed = False
        for event in changed.get("events", []):
            data = event.get("data", {})
            if data.get("actorHandle") == old["value"] \
                    and data.get("event") == "MOTION_STARTED":
                data["event"] = "WORLD_EFFECT"
                self.applied = True
                row_changed = True
        return changed if row_changed else row


Negative = FollowerTransitionNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "Follower transition copied control did not fail")
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
            "Follower transition copied control failed for an unrelated reason: " + fault)


def contract():
    return {
        "natural-input": [{
            "name": "follower-transition-acquisition-and-motion", "operator": "eq",
            "type": "array", "validator": "meaningful-observation", "expected": [1, 1],
        }],
        "live-actor-identity": [
            {
                "name": "follower-transition-role", "operator": "eq", "type": "string",
                "validator": "meaningful-observation", "expected": "FOLLOWER",
            },
            {
                "name": "follower-transition-identity-flags", "operator": "eq",
                "type": "array", "validator": "meaningful-observation",
                "expected": [1, "FOLLOWER", 155, 1, 1, "FOLLOWER", 155, 1, 1, 1],
            },
        ],
        "world-transition": [
            {
                "name": "follower-transition-map-change", "operator": "eq",
                "type": "array", "validator": "meaningful-observation", "expected": [1, 67],
            },
            {
                "name": "follower-transition-field-rebind", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation", "expected": 1,
            },
        ],
        "control-release": [{
            "name": "follower-transition-player-recovery", "operator": "eq",
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
            and meter.get("failures") == [] and meter.get("requirements") == [REQUIREMENT],
            "Follower transition lacks closed independent replay")
    require(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": [],
    }, "Follower transition private session did not close cleanly")
    initial, terminal = meter["initial"], meter["terminal"]
    initial_subject, subject = meter["initialSubject"], meter["subject"]
    before_selected = select_current_actor(initial, initial_subject)
    after_selected = select_current_actor(terminal, subject)
    before = next(item for item in initial["actors"]
                  if item.get("handle") == before_selected["handle"])
    after = next(item for item in terminal["actors"]
                 if item.get("handle") == after_selected["handle"])
    after_source, after_engine = after["sourceIdentity"], after["engineIdentity"]
    require(all(actor.get("active") is True and actor.get("role") == "FOLLOWER"
                and actor.get("species") == 155 and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True for actor in (before, after))
            and before.get("subjectIdentity") == after.get("subjectIdentity")
            and live_spawn_flags(after_source.get("active")) and after_source.get("species") == 155
            and after_source.get("personality") == after.get("subjectIdentity")
            and after_source.get("map_id") == 67
            and after_engine.get("active") is True and after_engine.get("in_manager") is True
            and after_engine.get("current_map_id") == 67 and after_engine.get("object_map_id") == 67,
            "Follower transition lacks current Cyndaquil identity")
    lifecycle = meter.get("lifecycle", [])
    require([event.get("data", {}).get("event") for event in lifecycle] == list(LIFECYCLE)
            and all(event.get("data", {}).get("actor")
                    == {key: value for key, value in initial_subject["handle"].items() if key != "value"}
                    and event.get("data", {}).get("actorHandle") == initial_subject["handle"]["value"]
                    and event.get("data", {}).get("reason") == "OK"
                    for event in lifecycle),
            "Follower transition lacks one bound natural Walk")
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
            "Follower transition context and rebind trace differs")
    old, current = initial_subject["handle"], subject["handle"]
    rebound = (terminal["context"]["mapId"] == 67
        and terminal["context"]["fieldEpoch"] == ((initial["context"]["fieldEpoch"] + 1) & 0xFFFF or 1)
        and terminal["context"]["mapGeneration"] == ((initial["context"]["mapGeneration"] + 1) & 0xFFFF or 1)
        and all(old[key] == current[key] for key in (
            "value", "slot", "generation", "encounterGeneration"))
        and current["fieldEpoch"] == terminal["context"]["fieldEpoch"]
        and current["mapGeneration"] == terminal["context"]["mapGeneration"]
        and meter.get("oldHandleInvalidated") is True)
    require(rebound, "Follower transition did not rebind the prior field handle")
    require(meter.get("playerRecovered") is True
            and terminal.get("player", {}).get("x") == 574
            and terminal.get("player", {}).get("y") == 400,
            "Follower transition did not restore player control")
    identity = [1, before["role"], before["species"],
                int(before.get("identityVerified") is True),
                int(before.get("presentationAttached") is True),
                after["role"], after["species"],
                int(after.get("identityVerified") is True),
                int(after.get("presentationAttached") is True), int(rebound)]
    values = (
        ("natural-input", "follower-transition-acquisition-and-motion", [1, 1]),
        ("live-actor-identity", "follower-transition-role", after["role"]),
        ("live-actor-identity", "follower-transition-identity-flags", identity),
        ("world-transition", "follower-transition-map-change", [meter["mapChanges"], terminal["context"]["mapId"]]),
        ("world-transition", "follower-transition-field-rebind", int(rebound)),
        ("control-release", "follower-transition-player-recovery", int(meter["playerRecovered"])),
    )
    return [{"claim": claim, "name": name, "value": deepcopy(value),
             "operator": "eq", "expected": deepcopy(value), "passed": True}
            for claim, name, value in values]
