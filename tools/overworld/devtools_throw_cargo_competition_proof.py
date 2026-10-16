"""Exact native Cargo competition claim and copied observation controls."""
from copy import deepcopy
import struct
from tools.overworld.devtools_throw_cargo_competition_measurement import KIND, REQUIREMENT, require

CLAIMS=("live-actor-identity","natural-input","engine-boundary","control-release")
NAMES={"live-actor-identity":("competition-current-full-actors",),
       "natural-input":("far-pursuit-before-near-query",),
       "engine-boundary":("near-picks-same-free-cargo","one-protected-held-owner","same-cargo-normal-launch"),
       "control-release":("losing-pursuit-cleared-at-pickup","losing-carrier-resumes",)}
FAULTS=tuple(KIND+":"+name for name in ("stale-cargo","wrong-query-owner","two-held-owners","uncleared-loser","forced-launch"))

def contract():
    return {claim:[dict(name=name,operator="eq",type="integer",validator="meaningful-observation",expected=1)
                   for name in names] for claim,names in NAMES.items()}


def measurements(replay,record):
    m=replay.get("measurements",{}).get(KIND,{})
    require(replay.get("passed") is True and replay.get("failures")==[] and m.get("ready") is True
        and m.get("failures")==[] and m.get("requirements")==[REQUIREMENT]
        and m.get("observedFrameUnit")=="completed-game-frame" and m.get("observedFrames",0)>=2
        and record.get("sessionCleanup")==dict(sessionId=record.get("sessionId"),closed=True,errors=[]),
        "Cargo competition replay or owned cleanup is incomplete")
    far,contest,pickup,launch,resumed=(m[k] for k in ("farClaim","competition","pickup","launch","loserResumed"))
    h=m["subjects"]["cargo"]["handle"];near=m["subjects"]["near-geodude"]["handle"]
    require(far["frame"]<contest["frame"]<=pickup["frame"]<launch["frame"]
        and pickup["frame"]<resumed["frame"]
        and all(v["handle"]==h for v in (far["cargo"],contest["cargo"],pickup["cargo"],launch["actor"]))
        and pickup["near"]["handle"]==near and m["heldFrames"]>=2
        and all(r["owner"]==near for r in m["heldProtection"])
        and launch["event"]["data"]["actorHandle"]==h["value"],
        "Cargo competition current claim/pickup/launch sequence differs")
    return [dict(claim=claim,name=name,value=1,operator="eq",expected=1,passed=True)
            for claim,names in NAMES.items() for name in names]


class ThrowCargoCompetitionNegative:
    def __init__(self,fault):
        require(fault in FAULTS,"unknown Cargo competition copied control")
        self.fault=fault.rsplit(":",1)[1];self.applied=False;self.far_row=None

    def mutate(self,row,subjects):
        changed=deepcopy(row)
        if self.applied:return row
        for s in changed.get("samples",[]):
            inter=s.get("pokemonCombat",{}).get("interactions",{})
            carriers=inter.get("carriers",[]);state=inter.get("throwState",{})
            if not all(k in subjects for k in ("cargo","far-geodude")):continue
            cargo=subjects["cargo"]["handle"];far=subjects["far-geodude"]["handle"]
            fr=next((r for r in carriers if r["handle"]==far),None)
            if fr and fr["throw"]["targetRaw"]==cargo["slot"]+1:self.far_row=deepcopy(fr)
            if "near-geodude" not in subjects:continue
            near=subjects["near-geodude"]["handle"];nr=next((r for r in carriers if r["handle"]==near),None)
            if self.fault=="wrong-query-owner":
                for e in changed.get("events",[]):
                    d=e.get("data",{})
                    if e["frame"]==s["frame"] and d.get("observation")=="throw-cargo-query" \
                            and d.get("subject")==near and d.get("status")=="REACHABLE":
                        d["after"]["workspace"]["owner"]=deepcopy(far);self.applied=True;return changed
            if self.fault=="forced-launch":
                a=next(a for a in s["actors"] if a["handle"]==cargo)
                if a["motionKind"]!="HOP" or a["motionPhase"]!="MOVING":continue
                motion=next(r["motion"] for r in s["pokemonCombat"]["targets"] if r["handle"]==cargo)
                raw=bytearray.fromhex(motion["rawHex"]);raw[3]|=1
                motion["rawHex"]=raw.hex();motion["plan"]["flags"]|=1
                self.applied=True;return changed
            if not nr or not nr["throw"]["carried"]:continue
            if self.fault=="stale-cargo":
                b=nr["bindings"]["cargo"];b["target"]["actor"]["generation"]+=1
                raw=bytearray.fromhex(b["rawHex"]);struct.pack_into("<H",raw,2,b["target"]["actor"]["generation"])
                b["rawHex"]=raw.hex();nr["rawBindingsHex"]=nr["rawBindingsHex"][:72]+raw.hex()
            else:
                require(self.far_row is not None,"Cargo competition control lacks its original pursuit")
                index=carriers.index(fr);carriers[index]=deepcopy(self.far_row);fr=carriers[index]
                encoded=cargo["slot"]+1|(128 if self.fault=="two-held-owners" else 0)
                state["targets"][far["slot"]]=encoded;state["carrierMask"]|=1<<far["slot"]
                state["targetMask"]|=1<<cargo["slot"]
                state["rawHex"]=(bytes(state["targets"])+struct.pack("<3H",state["targetMask"],state["carrierMask"],state["recoveringMask"])).hex()
                fr["throw"]["targetRaw"]=encoded;fr["throw"]["carried"]=bool(encoded&128)
            self.applied=True;return changed
        return row


def validate_negative_result(result,fault):
    require(fault in FAULTS and result.get("passed") is False and bool(result.get("failures")),
            "Cargo competition copied control did not reject")
