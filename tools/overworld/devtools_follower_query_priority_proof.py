"""A current Follower may take an unclaimed Wild search, then throw normally."""
from copy import deepcopy
import struct
from tools.overworld.devtools_follower_query_priority_measurement import KIND, REQUIREMENT, require
from tools.overworld.devtools_follower_throw_measurement import TRIGGER_CONDITION, raw_handle

NAMES={
    "live-actor-identity":("saved-mankey-and-two-distinct-current-geodude",),
    "profile-resolution":("fresh-sight-interest-enters-authored-half-speed-find-cargo",),
    "natural-input":("unchanged-continue-normal-input-recreates-unclaimed-wild-query",),
    "engine-boundary":("same-query-storage-hands-off-before-native-route-pickup-and-away-flight",),
    "control-release":("complete-native-flight-and-normal-follow-return",),
}
CLAIMS=tuple(NAMES)
FAULTS=tuple(KIND+":"+f for f in ("old-pending-owner", "wrong-target", "lost-claim", "missing-flight-control"))


def contract():
    return {c:[dict(name=n,operator="eq",type="integer",validator="meaningful-observation",expected=1)
               for n in ns] for c,ns in NAMES.items()}


def measurements(replay,record):
    r=replay.get("measurements",{}).get(KIND,{})
    require(replay.get("passed") is True and replay.get("failures")==[]
        and r.get("passed") is True and r.get("ready") is True and r.get("acceptedProof") is False
        and r.get("failures")==[] and r.get("observedFrames")==replay.get("observedFrames")
        and r.get("observedFrameUnit")=="completed-game-frame"
        and set(r.get("subjects",{}))=={"mankey","old-geodude","source"},
        "Follower priority lacks complete current proof")
    f=r["frames"];m=r["subjects"]["mankey"]["handle"]
    old=r["subjects"]["old-geodude"]["handle"];src=r["subjects"]["source"]["handle"]
    require(m!=old and old!=src and m!=src
        and all(type(f.get(n)) is int for n in ("notice","handoff","cargoBound","claim","pickup","windup","launch","landed","followStart","followReturn"))
        and r["busyOwner"]["frame"]<f["notice"]<=f["handoff"]<=f["cargoBound"]<=f["claim"]<=f["pickup"]
        <=f["windup"]<f["launch"]<f["landed"]<=f["followStart"]<f["followReturn"],
        "Follower priority stage order or distinct identity differs")
    busy=r["busyOwner"];h=r["handoff"];b=r["sightBinding"]["binding"];a=r["admission"]
    require(busy["actor"]["handle"]==old and busy["actor"]["logical"]==dict(x=595,y=407)
        and busy["actor"]["motionPhase"]=="IDLE" and busy["actor"]["reservationId"]==0
        and busy["binding"]["bindings"]["cargo"]["bound"] is False
        and busy["query"]["status"]=="PENDING" and busy["query"]["workspace"]["owner"]==old
        and busy["query"]["workspace"]["compatibility"]["required"]==0
        and h["before"]["workspace"]["owner"]==old and h["after"]["workspace"]["owner"]==m
        and h["before"]["queryPointer"]==h["after"]["queryPointer"]==busy["query"]["queryPointer"]
        and h["before"]["workspace"]["storage"]==h["after"]["workspace"]["storage"]
        and b["sourceConditionId"]==TRIGGER_CONDITION and b["bound"] is True and b["targetCurrent"] is True
        and b["target"]==dict(kind="ACTOR",actor=src)
        and a["status"]=="REACHABLE" and a["frame"]==f["cargoBound"]
        and a["workspace"]["owner"]==m and a["workspace"]["ownerCurrent"] is True
        and a["workspace"]["compatibility"]["cargo"]==src,
        "Follower priority lacks the current unclaimed owner, handoff or exact Cargo route")
    require(r["flight"]["handle"]==src and r["flight"]["commit"] is not None
        and r["flight"]["returnFrame"]==f["landed"] and r["flight"]["moved"] is True
        and r["normalFollow"]["handle"]==m and r["normalFollow"]["commit"] is not None
        and r["normalFollow"]["returnFrame"]==f["followReturn"] and r["normalFollow"]["moved"] is True,
        "Follower priority lacks complete flight and Follow native return")
    require(record.get("sessionCleanup")==dict(sessionId=record.get("sessionId"),closed=True,errors=[]),
        "Follower priority owned session cleanup is missing")
    return [dict(claim=c,name=n,value=1,operator="eq",expected=1,passed=True) for c,ns in NAMES.items() for n in ns]


class FollowerQueryPriorityNegative:
    def __init__(self,fault):
        require(fault in FAULTS,"unknown Follower priority copied fault")
        self.fault=fault.rsplit(":",1)[1];self.applied=False

    def mutate(self,row,subjects):
        if row.get("phase")!="observe":return row
        changed=deepcopy(row);m=subjects.get("mankey",{}).get("handle")
        old=subjects.get("old-geodude",{}).get("handle");src=subjects.get("source",{}).get("handle")
        if self.fault=="old-pending-owner":
            for e in changed.get("events",[]):
                d=e.get("data",{});q=d.get("after",{}).get("workspace")
                if d.get("observation")=="throw-cargo-query" and d.get("subject")==m and q and q.get("owner")==m:
                    q["owner"]=deepcopy(old);q["stateSubject"]=deepcopy(old)
                    raw=bytearray.fromhex(d["resultHex"]);raw[104:139]=bytes(35)
                    q["lastWorkHex"]=bytes(28).hex();d.update(resultHex=raw.hex(),returnValue=0,resultStatus=0,status="PENDING")
                    self.applied=True
        for sample in changed.get("samples",[]):
            carrier=next((r for r in sample.get("pokemonCombat",{}).get("interactions",{}).get("carriers",[])
                if r.get("handle")==m),None)
            if self.fault=="wrong-target" and carrier and carrier["bindings"]["trigger"]["bound"]:
                b=carrier["bindings"]["trigger"];raw=bytearray.fromhex(b["rawHex"])
                b["target"]["actor"]=deepcopy(old);raw[:12]=raw_handle(old);b["rawHex"]=raw.hex()
                whole=bytearray.fromhex(carrier["rawBindingsHex"]);whole[12:36]=raw;carrier["rawBindingsHex"]=whole.hex();self.applied=True
            if self.fault=="lost-claim" and carrier and carrier["throw"]["targetRaw"]:
                state=sample["pokemonCombat"]["interactions"]["throwState"]
                state["targetMask"]&=~(1<<src["slot"])
                raw=bytearray.fromhex(state["rawHex"]);struct.pack_into("<H",raw,10,state["targetMask"]);state["rawHex"]=raw.hex();self.applied=True
            if self.fault=="missing-flight-control" and carrier and carrier["throw"]["recovering"]:
                before=len(changed.get("events",[]))
                changed["events"]=[e for e in changed.get("events",[]) if not (e.get("frame")==sample["frame"]
                    and e.get("kind")=="native" and e.get("data",{}).get("actorHandle")==src["value"]
                    and e["data"].get("event")=="CONTROL_RETURNED")]
                self.applied|=len(changed["events"])!=before
        return changed if self.applied else row


def validate_negative_result(result,fault):
    require(fault in FAULTS and result.get("passed") is False and result.get("failures"),
        "Follower priority copied fault did not fail")
    errors=result.get("measurements",{}).get(KIND,{}).get("failures",result.get("failures",[]))
    expected={"old-pending-owner":("retained unrelated query owner",),
        "wrong-target":("Sight Interest differs",),"lost-claim":("lost current pickup claim",),
        "missing-flight-control":("ordered FINISH and CONTROL",)}[fault.rsplit(":",1)[1]]
    require(any(any(x in str(e) for x in expected) for e in errors),
        "Follower priority copied fault failed at another guard")
