"""Signed-height native Throw acceptance and named copied-stream controls."""
from copy import deepcopy
import struct
from tools.overworld.devtools_cross_height_throw_measurement import KINDS,requirement,require
from tools.overworld.devtools_walk_matrix_observer import decode_motion

NAMES={
    "live-actor-identity":("same-current-follower-trigger-and-cargo",),
    "profile-resolution":("current-authored-vision-captures-target-across-signed-height",),
    "natural-input":("real-pickup-and-windup-latch-physical-target-y",),
    "rendered-motion":("same-cargo-native-flight-keeps-signed-target-y",),
    "control-release":("same-flight-commits-returns-control-and-hits-current-trigger",),
}
ERRORS={"flat-aim":"flight flattened", "wrong-sign":"wrong physical height sign",
    "stale-trigger":"different subject or role", "player-fallback":"used Player fallback",
    "missing-vision":"ended without current Vision", "missing-start":"has no native START receipt",
    "missing-terminal":"native terminal commit", "missing-contact":"ended without current Vision"}

def claims(kind):
    require(kind in KINDS,"unknown signed-height proof");return tuple(NAMES)

def faults(kind):return tuple(kind+":"+n for n in ERRORS)

def contract(kind):
    claims(kind)
    return {c:[dict(name=n,operator="eq",type="integer",validator="meaningful-observation",expected=1) for n in ns]
            for c,ns in NAMES.items()}

def measurements(kind,replay,record):
    r=replay.get("measurements",{}).get(kind,{})
    require(replay.get("passed") is True and replay.get("failures")==[] and r.get("ready") is True
        and r.get("passed") is True and r.get("acceptedProof") is False
        and r.get("requirements")==[requirement(kind)]
        and r.get("observedFrames")==replay.get("observedFrames")
        and r.get("observedFrameUnit")=="completed-game-frame"
        and r.get("flightMoved") is True and r.get("cargoCompleted") is True
        and set(r.get("subjects",{}))=={"mankey","trigger","cargo"}, "signed-height Throw proof is incomplete")
    f=r["frames"]
    require(all(type(f.get(n)) is int for n in ("vision","claim","pickup","windup","launch","commit","terminal","contact"))
        and f["vision"]<=f["claim"]<=f["pickup"]<=f["windup"]<f["launch"]<=f["contact"]<=f["commit"]<=f["terminal"]
        and r["visionWitness"]["trigger"]==r["subjects"]["trigger"]["handle"]
        and r["windup"]["trigger"]==r["contact"]["trigger"]==r["subjects"]["trigger"]["handle"]
        and r["windup"]["cargo"]==r["flight"]["cargo"]==r["contact"]["cargo"]==r["subjects"]["cargo"]["handle"],
        "signed-height Throw stage identity or order differs")
    committed=r.get("flightCommit",{})
    require(committed.get("frame")==f["commit"] and type(committed.get("nativeCycle")) is int
        and r["flight"]["nativeCycle"]<=committed["nativeCycle"]
        and type(committed.get("sequence")) is int and committed["sequence"]>0
        and committed.get("commitSequence")==r["flight"]["commitSequence"]+1
        and committed.get("cargo")==r["flight"]["cargo"]==r["subjects"]["cargo"]["handle"]
        and committed.get("physicalY")==r["flight"]["plan"]["targetBaseY"],
        "signed-height Throw native commit identity or order differs")
    require(record.get("sessionCleanup")==dict(sessionId=record.get("sessionId"),closed=True,errors=[]),
            "signed-height Throw owned cleanup is missing")
    return [dict(claim=c,name=n,value=1,operator="eq",expected=1,passed=True) for c,ns in NAMES.items() for n in ns]


class CrossHeightThrowNegative:
    def __init__(self,kind,fault):
        require(fault in faults(kind),"unknown signed-height copied control")
        self.kind=kind;self.fault=fault.rsplit(":",1)[1];self.applied=False

    def mutate(self,row,subjects):
        if row.get("phase")!="observe" and not (self.fault=="missing-vision" and row.get("phase")=="setup"):return row
        changed=deepcopy(row)
        samples=list(changed.get("samples",[]))
        if self.fault=="missing-vision" and isinstance(changed.get("snapshot"),dict):samples.append(changed["snapshot"])
        for s in samples:
            a={n:next((a for a in s.get("actors",[]) if a.get("handle")==h["handle"]),None) for n,h in subjects.items()}
            m,t,c=(a.get(n) for n in ("mankey","trigger","cargo"))
            carrier=next((r for r in s.get("pokemonCombat",{}).get("interactions",{}).get("carriers",[]) if m and r.get("handle")==m["handle"]),None)
            if self.fault=="stale-trigger" and t:t["subjectIdentity"]+=1;self.applied=True
            if self.fault=="player-fallback" and carrier and carrier["bindings"]["trigger"]["bound"]:
                b=carrier["bindings"]["trigger"];raw=bytearray.fromhex(b["rawHex"]);raw[:12]=bytes(12);raw[12]=1
                b.update(target=dict(kind="PLAYER",actor=None),rawHex=raw.hex())
                whole=bytearray.fromhex(carrier["rawBindingsHex"]);whole[12:36]=raw;carrier["rawBindingsHex"]=whole.hex();self.applied=True
            if self.fault=="wrong-sign" and t and m and carrier and carrier["throw"]["windup"]:
                t["engineObject"]["pos_y"]=m["engineObject"]["pos_y"];t["engineObject"]["face_y"]=t["engineObject"]["unk88_y"]=0;self.applied=True
            if self.fault=="missing-vision" and carrier and carrier["bindings"]["trigger"]["bound"]:
                # Remove the capture where it occurs, including setup command boundaries.
                # Keep physical support and aim; only the current Trigger witness is absent.
                b=carrier["bindings"]["trigger"]
                b.update(target=dict(kind="NONE",actor=None),sourceConditionId=0,expiresAt=0,
                    sourceApplication=0,lifetime=0,flags=0,reason=0,bound=False,targetCurrent=False,rawHex=bytes(24).hex())
                whole=bytearray.fromhex(carrier["rawBindingsHex"]);whole[12:36]=bytes(24)
                carrier["rawBindingsHex"]=whole.hex();self.applied=True
            if self.fault in ("flat-aim","missing-contact"):
                for hp in s.get("pokemonCombat",{}).get("targets",[]):
                    if self.fault=="flat-aim" and c and hp["handle"]==c["handle"] and hp.get("motion",{}).get("plan",{}).get("kind")==2:
                        raw=bytearray.fromhex(hp["motion"]["rawHex"]);raw[20:24]=raw[16:20];hp["motion"]=decode_motion(bytes(raw));self.applied=True
                    if self.fault=="missing-contact" and t and hp["handle"]==t["handle"]:
                        hp.update(hp=hp["maxHp"],currentHp=hp["maxHp"],hitCount=0,lastDamage=0,immunityFrames=0);self.applied=True
        if self.fault in ("missing-terminal","missing-start"):
            name="LOGICAL_COMMIT" if self.fault=="missing-terminal" else "MOTION_STARTED"
            prior=changed.get("events",[])
            changed["events"]=[e for e in prior if not (e.get("kind")=="native" and e.get("data",{}).get("event")==name
                and e["data"].get("actorHandle")==subjects.get("cargo",{}).get("handle",{}).get("value"))]
            self.applied |= len(prior)!=len(changed["events"])
        return changed


def validate_negative_result(kind,result,fault):
    require(fault in faults(kind) and result.get("passed") is False and result.get("failures"), "signed-height copied control did not reject")
    expected=ERRORS[fault.rsplit(":",1)[1]]
    require(any(expected in str(f) for f in result.get("measurements",{}).get(kind,{}).get("failures",[])),
            "signed-height copied control rejected for a different reason")
