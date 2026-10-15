"""Accepted-hit source, unchanged accepted move, and native Throw/Follow proof."""
from copy import deepcopy
import struct
from tools.overworld.devtools_damage_follower_measurement import (
    KIND, REQUIREMENT, DAMAGE_CONDITION, CARGO_CONDITION, THROW_APP,
    CONTACT_BIND_DELAY, require, raw_handle,
)
from tools.overworld.devtools_walk_matrix_observer import decode_motion

NAMES={
    "live-actor-identity":("same-living-follower-and-physical-hit-source",),
    "profile-resolution":("player-damaged-condition-captures-source-as-interest-and-cargo",),
    "natural-input":("normal-run-real-accepted-player-hit", "accepted-busy-move-finishes-before-pickup"),
    "engine-boundary":("normal-windup-legal-away-flight-and-native-return",),
    "control-release":("old-bindings-clear-and-complete-normal-follow-returns",),
}
CLAIMS=tuple(NAMES)
FAULTS=tuple(KIND+":"+f for f in ("contact-only","stale-health","sight-trigger","wrong-cargo",
    "missing-move-return","toward-player","early-flight-overwrite","missing-flight-control","missing-follow-control"))


def contract():
    return {c:[dict(name=n,operator="eq",type="integer",validator="meaningful-observation",expected=1)
               for n in ns] for c,ns in NAMES.items()}


def measurements(replay,record):
    r=replay.get("measurements",{}).get(KIND,{})
    require(replay.get("passed") is True and replay.get("failures")==[] and r.get("passed") is True
        and r.get("ready") is True and r.get("acceptedProof") is False and r.get("failures")==[]
        and r.get("observedFrames")==replay.get("observedFrames")
        and r.get("observedFrameUnit")=="completed-game-frame" and set(r.get("subjects",{}))=={"mankey","source"},
        "Damage Follower lacks its complete current proof")
    f=r["frames"];src=r["subjects"]["source"]["handle"];m=r["subjects"]["mankey"]["handle"]
    require(all(type(f.get(n)) is int for n in ("hit","moveReturn","capture","claim","pickup","windup","launch","landed","followStart","followReturn"))
        and f["hit"]<=f["capture"]<=f["claim"]<=f["pickup"]<=f["windup"]<f["launch"]
        and f["hit"]<=f["moveReturn"]<=f["claim"]
        <f["landed"]<=f["followStart"]<f["followReturn"],"Damage Follower stage order differs")
    contact=r["acceptedHit"].get("physicalContact",{})
    require(r["acceptedHit"]["source"]==src
        and contact.get("source")==src
        and type(contact.get("frame")) is int
        and 0<=f["hit"]-contact["frame"]<=CONTACT_BIND_DELAY
        and contact.get("plan",{}).get("kind")==2
        and contact["plan"].get("reservationId",0)>0
        and r["busyMovement"]["handle"]==m
        and r["busyMovement"]["frame"]<contact["frame"]
        and r["busyMovement"]["returnFrame"]==f["moveReturn"]
        and r["damageBinding"]["binding"]["sourceConditionId"]==DAMAGE_CONDITION
        and r["damageBinding"]["binding"]["target"]==dict(kind="ACTOR",actor=src)
        and r["flight"]["handle"]==src and r["flight"]["commit"] is not None
        and r["flight"]["returnFrame"]==f["landed"] and r["flight"]["moved"] is True
        and r["normalFollow"]["handle"]==m and r["normalFollow"]["returnFrame"]==f["followReturn"]
        and r["normalFollow"]["moved"] is True,"Damage Follower lost its actual hit source or full motion owner")
    b,a=r["healthBefore"],r["healthAfter"]
    # The contact/binding stage only stops normal input for this HP read. A
    # delayed knockback animation cannot grant or remove accepted-hit credit.
    require(b["hp"]-a["hp"]==a["lastDamage"]==20 and a["acceptedHits"]==b["acceptedHits"]+1,
            "Damage Follower contact is not accepted Player damage")
    require(record.get("sessionCleanup")==dict(sessionId=record.get("sessionId"),closed=True,errors=[]),
            "Damage Follower owned cleanup is missing")
    return [dict(claim=c,name=n,value=1,operator="eq",expected=1,passed=True) for c,ns in NAMES.items() for n in ns]


class DamageFollowerNegative:
    def __init__(self,fault):
        require(fault in FAULTS,"unknown Damage Follower copied fault")
        self.fault=fault.rsplit(":",1)[1];self.applied=False

    def mutate(self,row,subjects):
        if row.get("phase")!="observe":return row
        changed=deepcopy(row)
        if self.fault in ("contact-only","stale-health") and row.get("action")=="accepted-hit":
            h=changed["receipt"]["playerHealth"]
            if self.fault=="contact-only":h.update(hp=100,savedHp=100,lastDamage=0,acceptedHits=0)
            else:h["frame"]+=1
            self.applied=True
        m=subjects.get("mankey",{}).get("handle");src=subjects.get("source",{}).get("handle")
        for sample in changed.get("samples",[]):
            frame=sample["frame"]
            carrier=next((r for r in sample.get("pokemonCombat",{}).get("interactions",{}).get("carriers",[])
                          if r.get("handle")==m),None)
            # Keep the real contact and its same-frame HP receipt intact. This
            # copied fault tests the later damage-binding guard, rather than
            # removing the binding which admits the contact/HP-read stage.
            if self.fault in ("sight-trigger","wrong-cargo") and carrier \
                and (self.fault!="sight-trigger" or row.get("action")=="natural-damage-throw"):
                name="trigger" if self.fault=="sight-trigger" else "cargo";b=carrier["bindings"][name]
                if b["bound"]:
                    raw=bytearray.fromhex(b["rawHex"])
                    if name=="trigger":
                        b["sourceConditionId"]^=1;struct.pack_into("<H",raw,14,b["sourceConditionId"])
                    else:
                        b["target"]["actor"]["generation"]+=1;b["target"]["actor"]["value"]+=1<<16
                        raw[:12]=raw_handle(b["target"]["actor"])
                    b["rawHex"]=raw.hex();whole=bytearray.fromhex(carrier["rawBindingsHex"])
                    off=12 if name=="trigger" else 36;whole[off:off+24]=raw;carrier["rawBindingsHex"]=whole.hex();self.applied=True
            if self.fault in ("missing-move-return","missing-follow-control","missing-flight-control"):
                owner=src if self.fault=="missing-flight-control" else m
                eligible=row.get("action")==("normal-follow-return" if self.fault=="missing-follow-control" else "natural-damage-throw")
                if eligible:
                    before=len(changed.get("events",[]))
                    changed["events"]=[e for e in changed.get("events",[]) if not (e.get("frame")==frame
                        and e.get("kind")=="native" and e.get("data",{}).get("actorHandle")==owner.get("value")
                        and e["data"].get("event")=="CONTROL_RETURNED")]
                    self.applied |= len(changed["events"])!=before
            if self.fault in ("toward-player","early-flight-overwrite") and carrier and carrier["throw"]["recovering"]:
                actor=next((a for a in sample["actors"] if a.get("handle")==src),None)
                target=next((r for r in sample["pokemonCombat"].get("targets",[]) if r.get("handle")==src),None)
                if actor and target and actor.get("motionKind")=="HOP" and actor.get("motionPhase")=="MOVING" \
                    and (actor.get("motionElapsed")==0 if self.fault=="toward-player" else actor.get("motionElapsed",0)>0):
                    raw=bytearray.fromhex(target["motion"]["rawHex"])
                    xy=[sample["player"][k] for k in ("x","y")] if self.fault=="toward-player" else [actor["target"]["x"]+1,actor["target"]["y"]]
                    struct.pack_into("<2h",raw,12,*xy);target["motion"]=decode_motion(bytes(raw))
                    actor["target"]=dict(zip(("x","y"),xy));self.applied=True
        return changed if self.applied else row


def validate_negative_result(result,fault):
    require(fault in FAULTS and result.get("passed") is False and result.get("failures"),"Damage Follower copied fault did not fail")
    expected={"contact-only":"contact without accepted HP damage","stale-health":"HP receipt is stale",
        "sight-trigger":"Interest is not the accepted physical damage source", "wrong-cargo":"Cargo is not Object of Interest itself",
        "missing-move-return":"ordered FINISH and CONTROL","toward-player":"throw away from Player",
        "early-flight-overwrite":"replaced accepted motion before return","missing-flight-control":"ordered FINISH and CONTROL",
        "missing-follow-control":"ordered FINISH and CONTROL"}[fault.rsplit(":",1)[1]]
    errors=result.get("measurements",{}).get(KIND,{}).get("failures",result.get("failures",[]))
    require(any(expected in str(e) for e in errors),"Damage Follower copied fault failed at another guard")
