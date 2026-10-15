"""Shared target-access acceptance with finite copied-data controls."""
from copy import deepcopy
import struct
from tools.overworld.devtools_target_access_measurement import KINDS, CASES, WINDOW, requirement, require, target_permission

NAMES={
    "live-actor-identity":("target-access-current-full-follower-and-target",),
    "terrain-selection":("target-access-actual-native-supported-surface",),
    "profile-resolution":("target-access-authored-notice-uses-current-physical-permissions",),
    "natural-input":("target-access-normal-input-without-profile-or-state-writes",),
}


def claims(kind):
    return tuple(NAMES)+(("control-release",) if CASES[kind]["raised"] else ())


def contract(kind):
    names=dict(NAMES)
    if CASES[kind]["raised"]:names["control-release"]=("target-access-rejected-signpost-keeps-normal-follow",)
    return {c:[dict(name=n,operator="eq",type="integer",validator="meaningful-observation",expected=1)
            for n in ns] for c,ns in names.items()}


def faults(kind):
    return tuple(kind+":"+n for n in (("unknown-surface","stale-target","admitted-signpost","missing-follow-return")
        if CASES[kind]["raised"] else ("unknown-surface","stale-target","missing-ground-notice")))


def measurements(kind,replay,record):
    r=replay.get("measurements",{}).get(kind,{})
    require(replay.get("passed") is True and replay.get("failures")==[] and r.get("ready") is True
        and r.get("passed") is True and r.get("acceptedProof") is False and r.get("failures")==[]
        and r.get("requirements")==[requirement(kind)] and r.get("observedFrames",0)>=WINDOW
        and r.get("observedFrames")==replay.get("observedFrames")
        and r.get("observedFrameUnit")=="completed-game-frame"
        and set(r.get("subjects",{}))=={"mankey","target"},"target access proof is incomplete")
    require(record.get("sessionCleanup")==dict(sessionId=record.get("sessionId"),closed=True,errors=[]),
        "target access owned cleanup missing")
    terrain=r["terrainWitness"]
    require(terrain["target"]["handle"]==r["subjects"]["target"]["handle"]
        and terrain["context"]==r["terminal"]["context"],"target access terrain owner differs")
    witnesses=r["visibleWitnesses"] if CASES[kind]["raised"] else [r["noticeWitness"]]
    require(len(witnesses)==(WINDOW if CASES[kind]["raised"] else 1)
        and all(w["subject"]==r["subjects"]["mankey"]["handle"]
            and w["target"]==r["subjects"]["target"]["handle"]
            and max(abs(a-b) for a,b in zip(w["subjectTile"],w["targetTile"]))==1
            for w in witnesses),"target access adjacent full-target witness differs")
    physical_mask=target_permission(terrain["cell"])
    require(all(type(w.get("allowedTerrainMask")) is int
        and w["allowedTerrainMask"]==struct.unpack_from("<H",bytes.fromhex(w["profile"]["lanes"][0]),32)[0]
        and bool(w["allowedTerrainMask"]&physical_mask) is (not CASES[kind]["raised"])
        for w in witnesses),"target access proof actual target permission differs")
    if CASES[kind]["raised"]:
        f=r["followComplete"]
        require(f["frame"]>=witnesses[-1]["frame"] and f["commitAfter"]==f["commitBefore"]+1
            and f["returnFrame"]==f["frame"]+f["plan"]["duration"]+f["plan"]["pauseFrames"],
            "target access rejected follower did not return control")
    return [dict(claim=c,name=s["name"],value=1,operator="eq",expected=1,passed=True)
        for c,specs in contract(kind).items() for s in specs]


class TargetAccessNegative:
    def __init__(self,kind,fault):
        require(fault in faults(kind),"unknown target access copied fault")
        self.kind=kind;self.fault=fault.rsplit(":",1)[1];self.applied=False

    def mutate(self,row,subjects):
        changed=deepcopy(row)
        samples=list(changed.get("samples",[]))
        if isinstance(changed.get("snapshot"),dict):samples.append(changed["snapshot"])
        for s in samples:
            if self.fault=="unknown-surface" and row.get("command")=="terrain":
                for c in s.get("terrain",{}).get("cells",[]):c["surface"]["known"]=False
                self.applied=True
            if row.get("phase")!="observe":continue
            target=next((a for a in s.get("actors",[]) if a.get("handle")==subjects.get("target",{}).get("handle")),None)
            if self.fault=="stale-target" and target:target["subjectIdentity"]+=1;self.applied=True
            for c in s.get("pokemonCombat",{}).get("interactions",{}).get("carriers",[]):
                if c.get("handle")!=subjects.get("mankey",{}).get("handle"):continue
                for state in c.get("conditionCaptures",[]):
                    if state.get("conditionId")!=12365:continue
                    if self.fault=="admitted-signpost":state["flags"]|=1
                    elif self.fault=="missing-ground-notice":state["flags"]&=~1
                    else:continue
                    raw=bytearray.fromhex(state["rawHex"]);raw[15]=state["flags"];state["rawHex"]=raw.hex();self.applied=True
        if self.fault=="missing-follow-return" and row.get("phase")=="observe":
            old=changed.get("events",[])
            changed["events"]=[e for e in old if not (e.get("kind")=="native"
                and e.get("data",{}).get("event")=="CONTROL_RETURNED"
                and e["data"].get("actorHandle")==subjects.get("mankey",{}).get("handle",{}).get("value"))]
            self.applied|=len(old)!=len(changed["events"])
        return changed


def validate_negative_result(kind,result,fault):
    expected={"unknown-surface":"actual native surface differs","stale-target":"different subject or role",
        "admitted-signpost":"inaccessible Signpost admitted","missing-follow-return":"ended without",
        "missing-ground-notice":"accessible ground lacks"}[fault.rsplit(":",1)[1]]
    require(fault in faults(kind) and result.get("passed") is False
        and any(expected in str(e) for e in result.get("measurements",{}).get(kind,{}).get("failures",[])),
        "target access copied fault failed at another guard")
