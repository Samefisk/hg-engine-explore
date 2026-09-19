"""Exact retained ledge rows and copied-data controls."""
from copy import deepcopy

from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.devtools_wild_ledge_measurement import KIND, LIFECYCLE, REQUIREMENTS, require
from tools.overworld.devtools_wild_ledge_observer import IDENTITY, ORIGIN, SPECIES, TARGET
from tools.overworld.normal_play_observer import complete_travel

CLAIMS = ("collision-decision", "live-actor-identity")
FAULTS = ("ledge-absent-subject", "ledge-stale-subject", "ledge-south-return",
          "ledge-north-return", "ledge-missing-finish")


def contract(requirement):
    if requirement == REQUIREMENTS[0]:
        return {
            "collision-decision": [dict(name="south-ledge-custom-hop-decision", operator="eq", type="array",
                                        validator="meaningful-observation", expected=[1, 1, 0, ORIGIN, TARGET])],
            "live-actor-identity": [dict(name="ledge-clefairy-identity", operator="eq", type="array",
                                         validator="meaningful-observation", expected=[1, "WILD", SPECIES, 1])],
        }
    raise ValueError("unknown ledge requirement")


def _event(traces, name):
    rows = [event for event in traces if event.get("data", {}).get("event") == name]
    require(len(rows) == 2, "missing native " + name)
    return rows


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    require(replay.get("passed") is True and replay.get("failures") == []
        and meter.get("passed") is True and meter.get("ready") is True and meter.get("closed") is True
        and meter.get("acceptedProof") is False and meter.get("failures") == []
        and meter.get("requirements") == list(REQUIREMENTS), "wild ledge lacks closed independent replay")
    require(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
            "wild ledge private session did not close cleanly")
    initial, terminal, subject = meter["initial"], meter["terminal"], meter["subject"]
    selected = select_current_actor(initial, subject)
    actor = next(item for item in initial["actors"] if item["handle"] == selected["handle"])
    current = select_current_actor(terminal, subject)
    end = next(item for item in terminal["actors"] if item["handle"] == current["handle"])
    require(actor.get("identityVerified") is True and actor.get("presentationAttached") is True
        and actor.get("species") == SPECIES and actor.get("role") == "WILD" and actor.get("inputOwnership") == 0
        and [actor["logical"][key] for key in ("x", "y")] == ORIGIN
        and all(end.get(key) == actor.get(key) for key in IDENTITY)
        and end.get("sourceIdentity") == actor.get("sourceIdentity")
        and engine_binding_identity(end.get("engineIdentity")) == engine_binding_identity(actor.get("engineIdentity"))
        and terminal["context"] == initial["context"]
        and end.get("motionKind") == "NONE" and end.get("motionPhase") == "IDLE"
        and end.get("reservationId") == 0 and [end["logical"][key] for key in ("x", "y")] == ORIGIN,
        "wild ledge terminal identity or target differs")
    decisions = meter.get("decisionReceipts", [])
    require(len(decisions) == 2 and [item["data"].get("case") for item in decisions] == ["south", "north"],
            "wild ledge decision order differs")
    south, north = (item["data"] for item in decisions)
    for data, label, direction in ((south, "south", 1), (north, "north", 0)):
        before, after = data.get("before", {}), data.get("after", {})
        require(data.get("observation") == "wild-ledge-intent" and data.get("subject") == subject
            and data.get("case") == label and data.get("direction") == direction
            and data.get("returnValue") == 2 and data.get("suppressed") is False
            and data.get("jumpLevel") == 2 and data.get("guestMemoryWrites") == 2
            and data.get("pendingWrites", 0) == 0
            and data.get("profilePointer", 0) >= 0x02000000 and len(bytes.fromhex(data.get("profileHex", ""))) == 216
            and before.get("subject") == subject and after.get("subject") == subject,
            label + " ledge native decision differs")
    require([south["before"]["publicSubject"]["logical"][key] for key in ("x", "y")] == ORIGIN
        and south["after"]["publicSubject"].get("motionKind") == "HOP"
        and [south["after"]["publicSubject"]["target"][key] for key in ("x", "y")] == TARGET
        and [north["before"]["publicSubject"]["logical"][key] for key in ("x", "y")] == TARGET
        and north["after"]["publicSubject"].get("motionKind") == "HOP"
        and [north["after"]["publicSubject"]["target"][key] for key in ("x", "y")] == ORIGIN,
        "wild ledge decision endpoints differ")
    motions = meter.get("motions", [])
    require(meter.get("completeMotions") == 2 and len(motions) == 2
        and [(motion.get("origin"), motion.get("target"), motion.get("terminalLogical")) for motion in motions]
            == [(ORIGIN, TARGET, TARGET), (TARGET, ORIGIN, ORIGIN)]
        and all(motion.get("kind") == "HOP" and complete_travel(motion)
                and motion.get("pauseFrames") == 0
                and motion.get("handle") == actor["handle"]
                and motion.get("fingerprint") == actor["behaviorFingerprint"]
                and motion.get("commitAfter") == (motion.get("commitBefore") + 1) & 0xffffffff
                for motion in motions),
        "wild ledge lacks two complete real Hops without duplicate Hop pause")
    traces = meter.get("traces", [])
    for name in LIFECYCLE:
        _event(traces, name)
    lifecycle = [event for event in traces if event.get("data", {}).get("event") in LIFECYCLE]
    lifecycle_values = []
    if len(lifecycle) == len(LIFECYCLE) * len(motions):
        for index, motion in enumerate(motions):
            group = lifecycle[index * len(LIFECYCLE):(index + 1) * len(LIFECYCLE)]
            lifecycle_values.append([
                (group[0]["data"].get("valueA"), group[0]["data"].get("valueB")),
                (group[1]["data"].get("valueA"), group[1]["data"].get("valueB")),
                (group[2]["data"].get("valueA"), group[2]["data"].get("valueB")),
                (group[3]["data"].get("valueA"), group[3]["data"].get("valueB")),
            ])
    expected_lifecycle_values = [
        [(2, motion.get("duration")), (motion.get("commitAfter"), 2),
         (motion.get("commitAfter"), 2), (0, motion.get("commitAfter"))]
        for motion in motions
    ]
    require(not any(item.get("data", {}).get("event") == "MOTION_CANCELED" for item in traces)
        and [item["data"].get("event") for item in lifecycle] == list(LIFECYCLE) * 2
        and [item["data"]["sequence"] for item in lifecycle] == sorted(set(item["data"]["sequence"] for item in lifecycle))
        and all(item["data"].get("reason") == "OK"
                and item["data"].get("actorHandle") == actor["handle"]["value"] for item in lifecycle)
        and lifecycle_values == expected_lifecycle_values,
        "wild ledge lifecycle differs")
    cleanup = meter.get("cleanup", {})
    reader = cleanup.get("wildLedge", {})
    require(cleanup.get("closed") is True and cleanup.get("advancedFrames") == 0
        and cleanup.get("acceptedProof") is False and reader.get("closed") is True
        and reader.get("terminal") is True and reader.get("phase") == "terminal"
        and reader.get("failure") is None and reader.get("guestMemoryWrites") == 4
        and reader.get("pendingWrites") == 0 and len(reader.get("calls", [])) == 2
        and reader.get("provenance", {}).get("symbol") == "OverworldWildSpawns_TryStartLedgeJumpCommand"
        and reader.get("provenance", {}).get("size", 0) >= 32,
        "wild ledge reader cleanup differs")
    values = (
        (REQUIREMENTS[0], "collision-decision", [1, 1, 0, ORIGIN, TARGET]),
        (REQUIREMENTS[0], "live-actor-identity", [1, "WILD", SPECIES, 1]),
    )
    rows = []
    for requirement, claim, value in values:
        specification = contract(requirement)[claim][0]
        rows.append(dict(requirement=requirement, claim=claim, name=specification["name"],
                         value=deepcopy(value), operator="eq", expected=deepcopy(value), passed=True))
    return rows


class WildLedgeNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown wild ledge fault")
        self.fault, self.applied = fault, False

    def mutate(self, row, subjects):
        if self.applied or row.get("phase") != "observe" or not subjects:
            return row
        changed = deepcopy(row)
        handles = {value["handle"]["value"] for value in subjects.values()}
        for sample in changed.get("samples", []):
            actor = next((item for item in sample.get("actors", [])
                          if item.get("handle", {}).get("value") in handles), None)
            if actor is not None and self.fault == "ledge-absent-subject":
                sample["actors"].remove(actor); self.applied = True
            elif actor is not None and self.fault == "ledge-stale-subject":
                actor["authorityGeneration"] += 1; self.applied = True
            if self.applied:
                break
        if not self.applied:
            for event in changed.get("events", []):
                data = event.get("data", {})
                if self.fault == "ledge-south-return" and data.get("observation") == "wild-ledge-intent" \
                        and data.get("case") == "south":
                    data["returnValue"] = 1; self.applied = True
                elif self.fault == "ledge-north-return" and data.get("observation") == "wild-ledge-intent" \
                        and data.get("case") == "north":
                    data["returnValue"] = 0; self.applied = True
                elif self.fault == "ledge-missing-finish" and data.get("event") == "MOTION_FINISHED" \
                        and data.get("actorHandle") in handles:
                    data["event"] = "WORLD_EFFECT"; self.applied = True
                if self.applied:
                    break
        return changed if self.applied else row


Negative = WildLedgeNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "wild ledge copied control did not fail")
    strings = []
    def visit(value):
        if isinstance(value, str):
            strings.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(result.get("failures", []))
    visit(result.get("measurements", {}).get(KIND, {}).get("failures", []))
    expected = {
        "ledge-absent-subject": "selected handle must name exactly one current active actor",
        "ledge-stale-subject": "selected actor has a stale authorityGeneration",
        "ledge-south-return": "south ledge native decision differs",
        "ledge-north-return": "north ledge native decision differs",
        "ledge-missing-finish": "missing native MOTION_FINISHED",
    }[fault]
    require(any(expected in value for value in strings),
            "wild ledge copied control failed for an unrelated reason: " + fault)
