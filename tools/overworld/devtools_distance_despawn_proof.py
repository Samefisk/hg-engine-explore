"""Two exact map cases: free chase first, then the same protected pickup claim."""
from copy import deepcopy
import struct
from tools.overworld.devtools_distance_despawn_measurement import KINDS, requirement, require

NAMES = {
    "live-actor-identity": ("same-current-carrier-cargo-and-unrelated-wild",),
    "engine-boundary": ("two-scheduled-far-samples-during-current-claim", "exact-native-distance-deletion"),
    "natural-input": ("normal-two-tile-player-exit-no-post-bind-writes",),
    "rendered-motion": ("native-idle-terminal-before-distance-deletion",),
    "control-release": ("carrier-cargo-protected-unrelated-removed",),
}
FAULT_NAMES = ("blanket-protection", "stale-claim", "missing-first-sample", "stale-delete", "cancelled-motion", "stale-owner")


def claims(kind):
    require(kind in KINDS, "unknown map case")
    return tuple(NAMES)


def faults(kind):
    require(kind in KINDS, "unknown map case")
    return tuple(kind+":"+name for name in FAULT_NAMES)


def contract(kind):
    return {claim:[dict(name=n,operator="eq",type="integer",validator="meaningful-observation",expected=1)
                   for n in names] for claim,names in NAMES.items() if claim in claims(kind)}


def measurements(kind, replay, record):
    result = replay.get("measurements",{}).get(kind,{})
    require(replay.get("passed") is True and replay.get("failures") == []
            and result.get("ready") is True and result.get("passed") is True
            and result.get("acceptedProof") is False and result.get("requirements") == [requirement(kind)]
            and result.get("observedFrames") == replay.get("observedFrames")
            and result.get("observedFrameUnit") == "completed-game-frame"
            and set(result.get("subjects",{})) == {"cargo","carrier","unrelated"}
            and type(result.get("claimFrame")) is int and len(result.get("farSamples",[])) == 2
            and result.get("freeChaseWitness",{}).get("frame") == result["farSamples"][0]["frame"]
            and result["freeChaseWitness"]["carrier"] == result["subjects"]["carrier"]["handle"]
            and result["freeChaseWitness"]["cargo"] == result["subjects"]["cargo"]["handle"]
            and result.get("terminal",{}).get("frame",0) < result.get("deletion",{}).get("frame",0)
            and result["deletion"]["handle"] == result["subjects"]["unrelated"]["handle"]
            and (result["terminal"]["motion"]["handle"] if result["terminal"].get("motion") else result["terminal"]["actor"]["handle"]) == result["deletion"]["handle"]
            and len(result.get("calls",[])) >= 2, "missing exact claim-backed native deletion")
    require(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"),closed=True,errors=[]),
            "owned session cleanup is missing")
    return [dict(claim=c,name=n,value=1,operator="eq",expected=1,passed=True) for c,names in NAMES.items() for n in names]


class DistanceDespawnNegative:
    def __init__(self, kind, fault):
        require(fault in faults(kind), "unknown copied-stream control")
        self.kind=kind; self.fault=fault.rsplit(":",1)[1]; self.applied=False
        self.first_sample_removed=False
        self.finish_seen=False

    def mutate(self, row, subjects):
        if row.get("phase") != "observe": return row
        changed=deepcopy(row); slot=subjects["unrelated"]["handle"]["slot"]
        if self.fault == "stale-claim":
            for sample in changed.get("samples",[]):
                for carrier in sample.get("pokemonCombat",{}).get("interactions",{}).get("carriers",[]):
                    if carrier.get("handle") == subjects["carrier"]["handle"]:
                        carrier["bindings"]["cargo"]["targetCurrent"]=False; self.applied=True
        for event in list(changed.get("events",[])):
            d=event.get("data",{})
            if event.get("kind") == "native" \
                    and d.get("actorHandle") == subjects["unrelated"]["handle"]["value"] \
                    and d.get("actor") == {k:v for k,v in subjects["unrelated"]["handle"].items() if k!="value"}:
                if d.get("event") == "MOTION_FINISHED":
                    self.finish_seen=True
                    if self.fault == "cancelled-motion":
                        d["event"]="MOTION_CANCELED"; self.applied=True
                elif self.fault == "cancelled-motion" and d.get("event") == "ACTOR_DETACHED" and not self.finish_seen:
                    # An idle native owner may be deleted without a Walk.
                    # Alter its real detach event; never invent a terminal.
                    d["event"]="MOTION_CANCELED"; self.applied=True
            if event.get("kind") != "native-observation" or d.get("observation") != "distance-maintenance": continue
            if self.fault == "stale-owner":
                d["worldContext"]["fieldEpoch"] += 1; self.applied=True
            elif self.fault == "blanket-protection":
                d["hardProtectedMask"] |= 1<<slot; self.applied=True
            elif self.fault == "missing-first-sample" and not self.first_sample_removed \
                    and d["before"]["farSamples"][slot] == 0 and d["after"]["farSamples"][slot] == 1:
                changed["events"].remove(event); self.first_sample_removed=self.applied=True
            elif self.fault == "stale-delete" and d["after"]["telemetrySequence"] != d["before"]["telemetrySequence"]:
                raw=bytearray.fromhex(d["after"]["telemetryHex"])
                for index in range(8):
                    if raw[16+40*index+34] == slot and raw[16+40*index+32] == 3:
                        struct.pack_into("<I",raw,16+40*index+8,0); self.applied=True
                d["after"]["telemetryHex"]=raw.hex()
        return changed


def validate_negative_result(kind, result, fault):
    require(fault in faults(kind) and result.get("passed") is False and result.get("failures"), "copied control did not reject")
    expected={"blanket-protection":"unrelated actor was protected", "stale-claim":"claim is stale",
              "missing-first-sample":"distance sample history is incomplete", "stale-delete":"wrong identity",
              "cancelled-motion":"motion was cancelled", "stale-owner":"stale owner"}[fault.rsplit(":",1)[1]]
    expected=(expected,)
    if fault.rsplit(":",1)[1] == "missing-first-sample":
        # Removing the first receipt also removes permission for the omitted
        # zero-frame wait. The next request then fails before a second sample.
        expected += ("normal input stages skip or reverse",)
    require(any(message in str(f) for f in result.get("measurements",{}).get(kind,{}).get("failures",[])
                for message in expected),
            "copied control rejected for the wrong reason")
