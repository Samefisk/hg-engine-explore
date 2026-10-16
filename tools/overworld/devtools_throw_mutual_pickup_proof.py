"""Independent proof and copied faults for the normal two-Geodude pickup."""
from copy import deepcopy
import struct

from tools.overworld.devtools_throw_mutual_pickup_measurement import KIND, REQUIREMENT, require

CLAIMS = ("live-actor-identity", "natural-input", "engine-boundary", "control-release")
NAMES = {
    "live-actor-identity": ("two-current-full-geodude",),
    "natural-input": ("normal-first-pursuit", "fresh-reciprocal-query"),
    "engine-boundary": ("two-unheld-outgoing-claims", "one-physical-held-owner",
                        "same-pair-normal-launch"),
    "control-release": ("incoming-pursuit-retained", "loser-claim-released-at-pickup"),
}
FAULTS = tuple(KIND + ":" + name for name in (
    "incoming-abort-clear", "mutual-physical-rejection"))


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
            and 2 <= m.get("observedFrames", 0) <= 180
            and record.get("sessionCleanup") == dict(
                sessionId=record.get("sessionId"), closed=True, errors=[]),
            "mutual pickup replay or owned cleanup is incomplete")
    first, mutual, pickup, launch = (m[key] for key in
                                     ("firstClaim", "mutual", "pickup", "launch"))
    a = m["subjects"]["geodude-a"]["handle"]
    b = m["subjects"]["geodude-b"]["handle"]
    require(first["frame"] < mutual["frame"] < pickup["frame"] < launch["frame"]
            and first["actor"]["handle"] == mutual["a"]["handle"] == a
            and first["target"]["handle"] == mutual["b"]["handle"] == b
            and pickup["owner"]["handle"] in (a, b)
            and pickup["cargo"]["handle"] in (a, b)
            and pickup["owner"]["handle"] != pickup["cargo"]["handle"]
            and launch["owner"]["handle"] == pickup["owner"]["handle"]
            and launch["cargo"]["handle"] == pickup["cargo"]["handle"]
            and launch["event"]["data"]["actorHandle"] == pickup["cargo"]["handle"]["value"]
            and m["heldFrames"] >= 2,
            "mutual pickup full-owner pursuit, HELD or launch differs")
    return [dict(claim=claim, name=name, value=1, operator="eq",
                 expected=1, passed=True)
            for claim, names in NAMES.items() for name in names]


class ThrowMutualPickupNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown mutual pickup copied control")
        self.fault = fault.rsplit(":", 1)[1]
        self.applied = False
        self.unclaimed = None
        self.saw_claim = False

    def mutate(self, row, subjects):
        changed = deepcopy(row)
        if self.applied:
            return row
        if not all(name in subjects for name in ("geodude-a", "geodude-b")):
            return row
        a = subjects["geodude-a"]["handle"]
        b = subjects["geodude-b"]["handle"]
        for sample in changed.get("samples", []):
            inter = sample.get("pokemonCombat", {}).get("interactions", {})
            rows = inter.get("carriers", [])
            state = inter.get("throwState", {})
            ar = next((entry for entry in rows if entry["handle"] == a), None)
            br = next((entry for entry in rows if entry["handle"] == b), None)
            if ar is None or br is None:
                continue
            if ar["throw"]["targetRaw"] == 0 and self.unclaimed is None:
                self.unclaimed = deepcopy(ar)
            if ar["throw"]["targetRaw"] == b["slot"] + 1:
                if not self.saw_claim:
                    self.saw_claim = True
                    continue
                if self.fault == "incoming-abort-clear" and self.unclaimed is not None:
                    rows[rows.index(ar)] = deepcopy(self.unclaimed)
                    state["targets"][a["slot"]] = 0
                    state["carrierMask"] &= ~(1 << a["slot"])
                    state["targetMask"] &= ~(1 << b["slot"])
                    state["rawHex"] = (bytes(state["targets"]) + struct.pack(
                        "<3H", state["targetMask"], state["carrierMask"],
                        state["recoveringMask"])).hex()
                    self.applied = True
                    return changed
            if self.fault == "mutual-physical-rejection":
                carried = ar if ar["throw"]["carried"] else br if br["throw"]["carried"] else None
                if carried is None:
                    continue
                cargo = b if carried is ar else a
                timer = next(entry for entry in sample["pokemonCombat"]["movementTimers"]
                             if entry["handle"] == cargo)
                timer["movementActorControlMode"] = 0
                self.applied = True
                return changed
        return row


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False
            and bool(result.get("failures")),
            "mutual pickup copied control did not reject")
