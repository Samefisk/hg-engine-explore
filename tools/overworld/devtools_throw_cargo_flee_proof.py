"""One current claim-backed Cargo Flee and copied-stream rejection controls."""
from copy import deepcopy
from tools.overworld.devtools_throw_cargo_flee_measurement import KIND, REQUIREMENT, require

NAMES = {
    "live-actor-identity": ("same-current-baby-cargo-and-pursuing-thrower",),
    "profile-resolution": ("targeted-for-pickup-while-true-targets-actual-pursuer",),
    "natural-input": ("normal-thrower-claim-leaves-cargo-free",),
    "rendered-motion": ("completed-native-flee-moves-away-from-actual-pursuer",),
    "control-release": ("flee-commits-and-returns-control-without-battle",),
}
CLAIMS = tuple(NAMES)
FAULTS = tuple(KIND+":"+name for name in ("player-substitution", "stale-claim", "wrong-direction", "missing-commit"))


def contract():
    return {claim: [dict(name=n, operator="eq", type="integer", validator="meaningful-observation", expected=1)
                    for n in names] for claim,names in NAMES.items()}


def measurements(replay, record):
    result = replay.get("measurements", {}).get(KIND, {})
    witness = result.get("witness", {}); motion = result.get("completedMotion", {})
    require(replay.get("passed") is True and replay.get("failures") == []
            and result.get("passed") is True and result.get("ready") is True
            and result.get("acceptedProof") is False and result.get("requirements") == [REQUIREMENT]
            and result.get("observedFrames") == replay.get("observedFrames")
            and result.get("observedFrameUnit") == "completed-game-frame"
            and set(result.get("subjects", {})) == {"cargo", "geodude"}
            and witness.get("cargo") == result["subjects"]["cargo"]["handle"]
            and witness.get("pursuer") == result["subjects"]["geodude"]["handle"]
            and motion.get("handle") == witness["cargo"] and motion.get("target") == witness["target"]
            and type(motion.get("finishFrame")) is int and motion["finishFrame"] > witness["startFrame"],
            "missing exact claim-backed completed Flee")
    require(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
            "owned session cleanup is missing")
    return [dict(claim=c, name=n, value=1, operator="eq", expected=1, passed=True)
            for c,names in NAMES.items() for n in names]


class ThrowCargoFleeNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown copied-stream control")
        self.fault = fault.rsplit(":", 1)[1]
        self.applied = False

    def mutate(self, row, subjects):
        if row.get("phase") != "observe": return row
        changed = deepcopy(row)
        if self.fault == "player-substitution":
            for receipt in changed.get("profileCache", {}).get("resolvedProfiles", []):
                data = bytearray.fromhex(receipt["resultHex"])
                data[196:210] = bytes(12) + bytes([1,0]); receipt["resultHex"] = data.hex(); self.applied = True
        for sample in changed.get("samples", []):
            cargo = next((a for a in sample.get("actors", []) if a.get("handle") == subjects.get("cargo", {}).get("handle")), None)
            if self.fault == "wrong-direction" and cargo and cargo.get("motionKind") in ("WALK", "HOP"):
                cargo["target"] = deepcopy(cargo["origin"]); self.applied = True
            if self.fault == "stale-claim":
                for carrier in sample.get("pokemonCombat", {}).get("interactions", {}).get("carriers", []):
                    if carrier.get("handle") == subjects.get("geodude", {}).get("handle"):
                        carrier["bindings"]["cargo"]["targetCurrent"] = False; self.applied = True
        if self.fault == "missing-commit":
            prior = changed.get("events", [])
            changed["events"] = [e for e in prior if not (e.get("kind") == "native"
                and e.get("data", {}).get("event") == "LOGICAL_COMMIT"
                and e["data"].get("actorHandle") == subjects.get("cargo", {}).get("handle", {}).get("value"))]
            self.applied |= len(prior) != len(changed["events"])
        return changed


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False and result.get("failures"), "copied control did not reject")
    expected = {"player-substitution": "full-current actual pursuer", "stale-claim": "claim is stale",
                "wrong-direction": "does not go away", "missing-commit": "lacks intent, commit or control return"}[fault.rsplit(":",1)[1]]
    require(any(expected in str(f) for f in result.get("measurements", {}).get(KIND, {}).get("failures", [])),
            "copied control rejected for the wrong reason")
