"""Exact S5 claims and copied-data controls; native LIMIT coverage is separate."""
from copy import deepcopy
import struct
from tools.overworld.devtools_wild_throw_soak_measurement import (
    KIND, REQUIREMENT, GEODUDES, MIN_FRAMES, SOAK_FRAMES, WildThrowSoakMeasurement,
    ground_state, require,
)
from tools.overworld.devtools_follower_throw_measurement import raw_handle

NAMES = {
    "live-actor-identity": ("three-initial-geodudes-two-current-through-5000-and-proved-faint-cleanup",),
    "profile-resolution": ("all-three-geodudes-naturally-capture-current-player-interest",),
    "natural-input": ("normal-lower-lane-b-cardinal-circuit-with-five-current-hp-checkpoints",),
    "engine-boundary": ("current-query-work-never-retains-terminal-owner-over-ready-search",),
    "control-release": ("repeated-pickup-flight-landing-and-recovery-pickup-cleanup",),
}
CLAIMS = tuple(NAMES)
FAULTS = tuple(KIND + ":" + fault for fault in (
    "terminal-owner", "recovery-pickup-leak", "orphan-held", "missing-landing-control", "frame-gap"))


def contract():
    return {claim:[dict(name=name, operator="eq", type="integer", validator="meaningful-observation", expected=1)
                   for name in names] for claim,names in NAMES.items()}


def measurements(replay, record):
    r = replay.get("measurements", {}).get(KIND, {})
    require(replay.get("passed") is True and replay.get("failures") == []
        and r.get("passed") is True and r.get("ready") is True and r.get("failures") == []
        and r.get("acceptedProof") is False and r.get("observedFrames") == replay.get("observedFrames")
        and r["observedFrameUnit"] == "completed-game-frame" and r["observedFrames"] >= MIN_FRAMES
        and r["soakFrames"] == SOAK_FRAMES
        and r["windowEnd"] - r["windowStart"] + 1 == r["observedFrames"]
        and all(r[k][name] > 0 for k in ("interests", "queries", "motionReturns") for name in GEODUDES)
        and len(r["completedThrows"]) >= 2 and r["recoveryPickups"] and r["ownershipCurrent"] is True,
        "complete continuous S5 Throw witness is missing")
    handles = [r["subjects"][name]["handle"] for name in GEODUDES]
    require(len({h["value"] for h in handles}) == 3 and r["queryCount"] > 0,
            "three distinct current search subjects are missing")
    survivors = r["survivors"]; retired = r["primaryRetirements"]
    require(isinstance(survivors, list) and len(set(survivors)) == len(survivors) >= 2
        and set(survivors).isdisjoint(retired)
        and set(survivors) | set(retired) == set(GEODUDES)
        and set(r["primaryCurrentFrames"]) == set(r["primaryHealthyFrames"]) == set(GEODUDES)
        and all(r["primaryCurrentFrames"][name] == r["primaryHealthyFrames"][name] == r["soakFrames"]
                for name in survivors), "two original healthy current subjects lack the full continuous window")
    for name, lifetime in retired.items():
        require(lifetime["handle"] == r["subjects"][name]["handle"] and lifetime["detach"] is not None
            and r["windowStart"] <= lifetime["frame"] < r["windowEnd"]
            and 0 < r["primaryHealthyFrames"][name] <= r["primaryCurrentFrames"][name] < r["soakFrames"],
                "initial primary lacks exact completed faint retirement without subject-frame credit")
    for cycle in r["completedThrows"]:
        require(cycle["carrier"] in handles and cycle["credited"] is True
            and r["windowStart"] <= cycle["claim"] <= cycle["pickup"] < cycle["launch"] < cycle["landed"] <= cycle["cleanup"] <= r["windowEnd"]
            and cycle["motion"]["handle"] == cycle["cargo"] and cycle["motion"]["commit"] is not None
            and cycle["motion"]["returnFrame"] == cycle["landed"], "complete owned flight and cleanup are missing")
        require(all(lifetime["handle"] not in (cycle["carrier"], cycle["cargo"])
            or cycle["cleanup"] < lifetime["hitFrame"]
            for lifetime in retired.values()), "fainted primary earned later Throw credit")
    checkpoints = r["playerCheckpoints"]
    require([value["leg"] for value in checkpoints] == [40, 80, 120, 160, 200]
        and all(value["soakFrames"] == value["leg"] * 24
            and value["playerHealth"]["frame"] == r["windowStart"] + value["soakFrames"] - 1
            and 0 < value["playerHealth"]["hp"] == value["playerHealth"]["savedHp"] <= 100
            and value["playerHealth"]["recoveryPending"] is False for value in checkpoints),
        "five current living Player HP checkpoints are missing")
    require(r["playerBefore"]["hp"] > 0 and r["playerAfter"]["hp"] > 0
        and record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
        "living Player or owned session cleanup is missing")
    return [dict(claim=c, name=n, value=1, operator="eq", expected=1, passed=True) for c,ns in NAMES.items() for n in ns]


class WildThrowSoakNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown S5 copied fault")
        self.fault = fault.rsplit(":", 1)[1]; self.applied = False; self.terminal = None
        self.held = {}; self.flights = {}; self.latest = None

    def mutate(self, row, subjects):
        if row.get("phase") != "observe" or self.applied: return row
        changed = deepcopy(row)
        for sample in changed.get("samples", []):
            if self.fault == "frame-gap":
                sample["frame"] += 1; self.applied = True; break
            combat = sample.get("pokemonCombat", {}); value = combat.get("interactions", {})
            state = value.get("throwState", {}); primary = [subjects[n]["handle"] for n in GEODUDES if n in subjects]
            timers = {t["slot"]:t for t in combat.get("movementTimers", [])}
            actors = {a["handle"]["slot"]:a for a in sample.get("actors", []) if a.get("active")}
            rows = {r["slot"]:r for r in value.get("carriers", []) if r.get("available")}
            for handle in primary:
                slot = handle["slot"]; actor = actors.get(slot); timer = timers.get(slot)
                if actor is None or timer is None: continue
                held = [n for n in state.get("targets", []) if n & 128 and n & 63 == slot + 1]
                if self.fault == "recovery-pickup-leak" and held and timer["movementEmoteTimer"] == timer["movementSpotState"] == 0:
                    state["recoveringMask"] |= 1 << slot
                    raw = bytearray.fromhex(state["rawHex"]); struct.pack_into("<H", raw, 14, state["recoveringMask"])
                    state["rawHex"] = raw.hex(); rows[slot]["throw"]["recovering"] = True
                    self.applied = True; break
                if self.fault == "orphan-held" and not held and not state.get("targetMask", 0) & (1 << slot) and actor["motionPhase"] == "IDLE":
                    timer["movementActorControlMode"] = 1; self.applied = True; break
            if self.fault == "missing-landing-control":
                for owner in rows.values():
                    flags=owner.get("throw",{});target=actors.get(flags.get("targetSlot"))
                    if owner["handle"] in primary and flags.get("carried") and target is not None \
                            and owner["bindings"]["cargo"]["target"].get("actor")==target["handle"]:
                        self.held[raw_handle(target["handle"]).hex()]=deepcopy(owner["handle"])
                for target in combat.get("targets", []):
                    actor=actors.get(target["handle"]["slot"]);key=raw_handle(target["handle"]).hex()
                    if actor is None or actor["handle"]!=target["handle"]:continue
                    native=WildThrowSoakMeasurement._events(self,sample,
                        [e for e in changed.get("events",[]) if e.get("frame")==sample["frame"]],actor)
                    starts=[e for e in native if e.get("event")=="MOTION_STARTED"]
                    owner=rows.get((self.held.get(key) or {}).get("slot"))
                    p=target.get("motion",{}).get("plan",{})
                    if key not in self.flights and owner is not None and owner["handle"]==self.held[key] \
                            and not owner["throw"]["targetRaw"] and not owner["throw"]["carrier"] \
                            and owner["throw"]["recovering"] and not any(owner["bindings"][k]["bound"] for k in ("trigger","cargo")) \
                            and state["targetMask"]&(1<<actor["handle"]["slot"]) and p.get("kind")==2 \
                            and len(starts)==1 and starts[0]["reason"]=="OK" \
                            and (starts[0]["valueA"],starts[0]["valueB"])==(2,p["duration"]):
                        motion=WildThrowSoakMeasurement._motion(None,sample,actor)
                        if motion["phase"]=="MOVING" and motion["elapsed"]==0:
                            self.flights[key]=deepcopy(p)
                    if key not in self.flights:continue
                    finishes=[e for e in native if e.get("event")=="MOTION_FINISHED" and e.get("valueB")==2]
                    controls=[e for e in native if e.get("event")=="CONTROL_RETURNED" and any(
                        f["sequence"]<e["sequence"] and f["valueA"]==e.get("valueB") for f in finishes)]
                    sequences={e["sequence"] for e in controls};old=len(changed.get("events",[]))
                    changed["events"] = [e for e in changed.get("events", []) if not (
                        e.get("frame") == sample["frame"] and e.get("kind") == "native"
                        and e.get("data", {}).get("actorHandle") == target["handle"]["value"]
                        and e["data"].get("sequence") in sequences)]
                    self.applied |= old != len(changed["events"])
            if self.fault == "terminal-owner":
                queries=[e for e in changed.get("events",[]) if e.get("frame")==sample["frame"]
                    and e.get("kind")=="native-observation" and e.get("data",{}).get("observation")=="throw-cargo-query"]
                # A real intervening Tick can invalidate the terminal cache.
                # Copy one adjacent same-frame owner/peer pair instead.
                for first,peer in zip(queries,queries[1:]):
                    d,p=first["data"],peer["data"];actor=actors.get(d.get("slot"));other=actors.get(p.get("slot"))
                    q=d.get("after",{}).get("workspace")
                    if actor is None or other is None or not q or actor["handle"] not in primary \
                            or other["handle"] not in primary or actor["handle"]==other["handle"] \
                            or d.get("subject")!=actor["handle"] or p.get("subject")!=other["handle"] \
                            or q.get("owner")!=actor["handle"] or q.get("stateSubject")!=actor["handle"] \
                            or q.get("ownerCurrent") is not True or q.get("valid") is not True \
                            or d["sequence"]>=p["sequence"] \
                            or not WildThrowSoakMeasurement._ready(actor,rows,timers) \
                            or not WildThrowSoakMeasurement._ready(other,rows,timers):continue
                    raw=bytearray.fromhex(d["resultHex"]);raw[104:139]=bytes(35);raw[104]=raw[138]=4
                    q.update(lastWorkHex=bytes(28).hex(),edgeQueries=0,goalQueries=0)
                    d.update(resultHex=raw.hex(),returnValue=4,resultStatus=4,status="RESOURCE_LIMIT")
                    self.terminal=deepcopy(d["after"])
                    p["after"]["queryPointer"]=self.terminal["queryPointer"]
                    p["after"]["workspace"]=deepcopy(self.terminal["workspace"])
                    raw=bytearray.fromhex(p["resultHex"]);raw[104:139]=bytes(35)
                    p.update(resultHex=raw.hex(),returnValue=0,resultStatus=0,status="PENDING")
                    self.applied=True;break
            self.latest=deepcopy(sample)
            if self.applied: break
        return changed if self.applied else row


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False and result.get("failures"), "copied S5 fault did not fail")
    errors = result.get("measurements", {}).get(KIND, {}).get("failures", result["failures"])
    expected = {
        "terminal-owner": ("terminal RESOURCE_LIMIT owner blocks", "terminal UNREACHABLE owner blocks"),
        "recovery-pickup-leak": ("recovery survives zero timer and CHILL",),
        "orphan-held": ("grounded HELD actor",),
        "missing-landing-control": ("ordered FINISH and CONTROL", "flight lacks continuous travel and landing control"),
        "frame-gap": ("raw completed samples skip", "continuous completed-frame window has a gap"),
    }[fault.rsplit(":", 1)[1]]
    require(any(any(text in str(error) for text in expected) for error in errors), "copied S5 fault failed at another guard")
