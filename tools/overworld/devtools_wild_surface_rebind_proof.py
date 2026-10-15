"""Claim rows and copied-data controls for the two absolute-height witnesses."""
from copy import deepcopy
import json

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_movement_predicates import player_settled_at
from tools.overworld.devtools_wild_surface_rebind_measurement import CONFIG, ROOF, need


def requirement(kind):
    return CONFIG[kind]["requirement"]


def claims(kind):
    need(kind in CONFIG, "unknown proof witness")
    return ("natural-input", "live-actor-identity", "terrain-selection", "world-transition",
            "rendered-motion", "control-release")


def faults(kind):
    need(kind in CONFIG, "unknown copied-data witness")
    return tuple(kind + ":" + f for f in ("missing-surface", "old-height", "missing-rebound", "wrong-personality"))


def contract(kind):
    c = CONFIG[kind]
    expected = {
        "natural-input": ("retained-surface-natural-handoff", 1),
        "live-actor-identity": ("retained-surface-same-wild-subject", [c["species"], "WILD", 1]),
        "terrain-selection": ("retained-surface-absolute-support", [c["surfaceId"], 1, 1]),
        "world-transition": ("retained-surface-context-and-rebound", [1, 1, int(kind == ROOF)]),
        "rendered-motion": ("retained-surface-terminal-height-error", 0),
        "control-release": ("retained-surface-player-recovered", 1),
    }
    return {claim: [dict(name=name, operator="eq", type="array" if isinstance(value, list) else "integer",
                        validator="meaningful-observation", expected=value)]
            for claim, (name, value) in expected.items()}


def measurements(kind, replay, record):
    meter = replay.get("measurements", {}).get(kind, {})
    need(replay.get("passed") is True and replay.get("failures") == []
         and meter.get("passed") is True and meter.get("ready") is True
         and meter.get("closed") is True and meter.get("acceptedProof") is False
         and meter.get("failures") == [] and meter.get("groundFrames", 0) >= 4,
         "closed replay is missing")
    need(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
         "owned session cleanup is missing")
    terminal, c = meter["terminal"], CONFIG[kind]
    selected = select_current_actor(terminal, meter["subject"])
    actor = next(a for a in terminal["actors"] if a["handle"] == selected["handle"])
    events = [e["data"]["event"] for e in meter["transitionEvents"]]
    support = meter["surface"]["surface"]
    actual = {
        "retained-surface-natural-handoff": 1,
        "retained-surface-same-wild-subject": [actor["species"], actor["role"],
            int(actor["subjectIdentity"] == meter["initialSubject"]["subjectIdentity"])],
        "retained-surface-absolute-support": [support["surfaceId"], int(support["finalHeightKnown"]),
            int(support["heightMode"] == "absolute")],
        "retained-surface-context-and-rebound": [events.count("CONTEXT_CHANGED"),
            events.count("ACTOR_REBOUND"), events.count("MOTION_CANCELED")],
        "retained-surface-terminal-height-error": abs(actor["engineObject"]["pos_y"] - support["heightFx32"]),
        "retained-surface-player-recovered": int(player_settled_at(terminal, c["newMap"], *c["recovery"])),
    }
    rows = []
    for claim, specs in contract(kind).items():
        for spec in specs:
            value = actual[spec["name"]]
            need(value == spec["expected"], "claim differs: " + spec["name"])
            rows.append(dict(claim=claim, name=spec["name"], value=value,
                             operator="eq", expected=spec["expected"], passed=True))
    return rows


class WildSurfaceRebindNegative:
    def __init__(self, kind, fault):
        need(fault in faults(kind), "unknown copied-data fault")
        self.kind, self.fault, self.applied = kind, fault.rsplit(":", 1)[1], False

    def mutate(self, row, subjects):
        if self.applied:
            return row
        changed = deepcopy(row)
        handle = subjects.get(CONFIG[self.kind]["subject"], {}).get("handle", {}).get("value")
        if self.fault == "missing-surface" and row.get("command") == "terrain":
            for cell in changed["receipt"]["terrain"]["cells"]:
                cell["surface"]["known"] = False
            self.applied = True
        elif self.fault == "missing-rebound":
            for event in changed.get("events", []):
                if event.get("kind") == "native" and event["data"].get("actorHandle") == handle \
                        and event["data"].get("event") == "ACTOR_REBOUND":
                    event["data"]["event"] = "WORLD_EFFECT"
                    self.applied = True
                    break
        else:
            for sample in changed.get("samples", []):
                if sample.get("context", {}).get("mapId") != CONFIG[self.kind]["newMap"]:
                    continue
                actor = next((a for a in sample.get("actors", []) if a.get("handle", {}).get("value") == handle), None)
                if actor is not None:
                    if self.fault == "old-height":
                        actor["engineObject"]["pos_y"] += 16
                    elif self.fault == "wrong-personality":
                        actor["subjectIdentity"] ^= 1
                    else:
                        continue
                    self.applied = True
                    break
        return changed


def validate_negative_result(kind, result, fault):
    need(fault in faults(kind) and result.get("passed") is False, "copied fault passed")
    reason = {"missing-surface": "absolute surface height", "old-height": "ground height/pose",
              "missing-rebound": "transition trace", "wrong-personality": "actor lifetime"}[fault.rsplit(":", 1)[1]]
    need(reason in json.dumps(result.get("failures")), "copied fault failed for a different reason")
