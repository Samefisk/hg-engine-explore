"""Independent proof and copied faults for one normal Wild Cargo retarget."""
from copy import deepcopy
import struct

from tools.overworld.devtools_throw_cargo_retarget_measurement import KIND, REQUIREMENT, require

CLAIMS = ("live-actor-identity", "natural-input", "engine-boundary", "control-release")
NAMES = {
    "live-actor-identity": ("retarget-current-full-actors",),
    "natural-input": ("first-claim-before-new-cargo", "near-native-reachable-query"),
    "engine-boundary": ("same-wild-cargo-switch", "one-stable-held-owner", "near-cargo-normal-launch"),
    "control-release": ("old-cargo-claim-released", "accepted-walk-finished"),
}
FAULTS = tuple(KIND + ":" + name for name in (
    "wrong-query-owner", "stale-new-cargo", "old-claim-retained",
    "changed-player-interest", "canceled-walk", "missing-walk-finish",
    "two-held-owners", "forced-launch"))


def contract():
    return {claim: [dict(name=name, operator="eq", type="integer",
                         validator="meaningful-observation", expected=1)
                    for name in names] for claim, names in NAMES.items()}


def measurements(replay, record):
    m = replay.get("measurements", {}).get(KIND, {})
    require(replay.get("passed") is True and replay.get("failures") == []
            and m.get("ready") is True and m.get("failures") == []
            and m.get("requirements") == [REQUIREMENT]
            and m.get("observedFrameUnit") == "completed-game-frame"
            and m.get("observedFrames", 0) >= 2
            and record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"),
                                                      closed=True, errors=[]),
            "Cargo retarget replay or owned cleanup is incomplete")
    first, query, switch, pickup, launch = (m[k] for k in (
        "firstClaim", "nearQuery", "switch", "pickup", "launch"))
    subject = m["subjects"]["geodude"]["handle"]
    near = m["subjects"]["near-cargo"]["handle"]
    require(first["frame"] < query["frame"] <= switch["frame"] <= pickup["frame"]
            < launch["frame"]
            and all(row["handle"] == subject for row in (
                first["actor"], switch["actor"], pickup["actor"]))
            and switch["near"]["handle"] == near
            and pickup["near"]["handle"] == near
            and launch["cargo"]["handle"] == near
            and launch["event"]["data"]["actorHandle"] == near["value"]
            and m["firstPlanFinished"] is True and m["heldFrames"] >= 2
            and all(row["actor"] == subject and row["cargo"] == near
                    for row in m["heldOwners"]),
            "Cargo retarget exact native switch, Walk, HELD or launch differs")
    return [dict(claim=claim, name=name, value=1, operator="eq", expected=1,
                 passed=True) for claim, names in NAMES.items() for name in names]


class ThrowCargoRetargetNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown Cargo retarget copied control")
        self.fault = fault.rsplit(":", 1)[1]
        self.applied = False
        self.first_claim_frame = None

    def mutate(self, row, subjects):
        changed = deepcopy(row)
        if self.applied or not all(k in subjects for k in ("geodude", "first-cargo")):
            return row
        subject = subjects["geodude"]["handle"]
        first = subjects["first-cargo"]["handle"]
        near = subjects.get("near-cargo", {}).get("handle")
        for sample in changed.get("samples", []):
            rows = sample.get("pokemonCombat", {}).get("interactions", {}).get("carriers", [])
            state = sample.get("pokemonCombat", {}).get("interactions", {}).get("throwState", {})
            carrier = next((r for r in rows if r.get("handle") == subject), None)
            if carrier is None:
                continue
            relation = carrier["throw"]["targetRaw"]
            if self.fault == "missing-walk-finish" and self.first_claim_frame is None:
                actor = next((a for a in sample.get("actors", []) if a.get("handle") == subject), None)
                if (relation == first["slot"] + 1 and actor is not None
                        and actor.get("motionKind") == "WALK"
                        and actor.get("motionPhase") == "MOVING"):
                    self.first_claim_frame = sample["frame"]
            if self.fault == "wrong-query-owner" and near is not None:
                for event in changed.get("events", []):
                    data = event.get("data", {})
                    after = data.get("after", {})
                    workspace = after.get("workspace") or {}
                    if (data.get("observation") == "throw-cargo-query"
                            and data.get("subject") == subject
                            and data.get("status") == "REACHABLE"
                            and workspace.get("compatibility", {}).get("cargo") == near):
                        workspace["owner"] = deepcopy(first)
                        self.applied = True
                        return changed
            if self.fault == "canceled-walk" and relation == first["slot"] + 1:
                changed.setdefault("events", []).append(dict(frame=sample["frame"], kind="native",
                    data=dict(event="MOTION_CANCELED", actorHandle=subject["value"],
                              actor={k:v for k,v in subject.items() if k!="value"})))
                self.applied = True
                return changed
            if (self.fault == "missing-walk-finish" and self.first_claim_frame is not None
                    and any(
                    e.get("kind") == "native" and e.get("data", {}).get("event") == "MOTION_FINISHED"
                    and e["data"].get("actorHandle") == subject["value"]
                    and e.get("frame", -1) > self.first_claim_frame
                    for e in changed.get("events", []))):
                changed["events"] = [e for e in changed["events"]
                                     if not (e.get("kind") == "native"
                                         and e.get("data", {}).get("event") == "MOTION_FINISHED"
                                         and e["data"].get("actorHandle") == subject["value"]
                                         and e.get("frame", -1) > self.first_claim_frame)]
                self.applied = True
                return changed
            if (self.fault == "two-held-owners" and near is not None
                    and relation & 128 and (relation & 63) == near["slot"] + 1):
                extra = deepcopy(carrier)
                extra["handle"] = deepcopy(first)
                extra["throw"]["targetRaw"] = relation
                extra["throw"]["targetSlot"] = near["slot"]
                rows.append(extra)
                self.applied = True
                return changed
            if near is None or (relation & 63) != near["slot"] + 1:
                continue
            if self.fault == "old-claim-retained":
                state["targetMask"] |= 1 << first["slot"]
                state["rawHex"] = (bytes(state["targets"]) + struct.pack("<3H",
                    state["targetMask"], state["carrierMask"], state["recoveringMask"])).hex()
            elif self.fault == "stale-new-cargo":
                binding = carrier["bindings"]["cargo"]
                binding["target"]["actor"]["generation"] += 1
            elif self.fault == "changed-player-interest":
                carrier["bindings"]["trigger"]["sourceConditionId"] += 1
            elif self.fault == "forced-launch":
                continue
            else:
                continue
            self.applied = True
            return changed
        if self.fault == "forced-launch" and near is not None:
            for sample in changed.get("samples", []):
                actor = next((a for a in sample.get("actors", []) if a.get("handle") == near), None)
                if (actor is None or actor.get("motionKind") != "HOP"
                        or actor.get("motionPhase") != "MOVING"):
                    continue
                motion = next(r["motion"] for r in sample["pokemonCombat"]["targets"]
                              if r["handle"] == near)
                raw = bytearray.fromhex(motion["rawHex"])
                raw[3] |= 1
                motion["rawHex"] = raw.hex()
                motion["plan"]["flags"] |= 1
                self.applied = True
                return changed
        return row


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False
            and bool(result.get("failures")),
            "Cargo retarget copied control did not reject")
