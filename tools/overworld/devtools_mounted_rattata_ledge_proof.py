"""Exact fresh mounted Rattata ledge claim and bounded copied controls."""
from copy import deepcopy
from tools.overworld.devtools_mounted_rattata_ledge_measurement import KIND, REQUIREMENT, DURATION, need

CLAIMS=("natural-input","live-actor-identity","profile-resolution","rendered-motion","logical-commit","control-release")
NAMES=dict(zip(CLAIMS,("normal-down-then-release","same-current-mounted-rattata-from-rest",
    "walk-time6-jumpBoth-hop1to8-obstacleHopNo","native-two-tile-ledge-hop12-with-full-observed-arc",
    "one-real-hop-commit-at-south-landing","ordered-input-return-and-exact-mount-rider-base")))
FAULTS=("wrong-owner","wrong-profile","wrong-target","missing-frame","missing-release","height-drift","held-after-release")


def contract():
    return {c:[dict(name=NAMES[c],operator="eq",type="integer",validator="meaningful-observation",expected=1)] for c in CLAIMS}


def measurements(replay,record):
    result=replay.get("measurements",{}).get(KIND,{})
    hop=result.get("hop",{})
    need(replay.get("passed") is True and replay.get("failures")==[]
         and result.get("passed") is True and result.get("ready") is True and result.get("acceptedProof") is False
         and result.get("requirements")==[REQUIREMENT] and result.get("observedFrames")==replay.get("observedFrames")
         and result.get("observedFrames",0)>=24 and result.get("observedFrameUnit")=="completed-game-frame"
         and result.get("subject",{}).get("role")=="MOUNTED" and result["subject"].get("species")==19
         and hop.get("actor")==result["subject"].get("handle")
         and hop.get("plan",{}).get("origin")==[590,395] and hop["plan"].get("target")==[590,397]
         and hop["plan"].get("duration")==DURATION
         and [s["elapsed"] for s in hop.get("samples",[])]==list(range(1,DURATION+1))
         and [e["event"] for e in result.get("release",{}).get("events",[])]
            ==["LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"]
         and result.get("finalActor",{}).get("logical")==dict(x=590,y=397),
         "complete fresh Rattata ledge Hop/input return is missing")
    need(record.get("sessionCleanup")==dict(sessionId=record.get("sessionId"),closed=True,errors=[]),
         "owned Rattata session cleanup is missing")
    return [dict(claim=c,name=NAMES[c],value=1,operator="eq",expected=1,passed=True) for c in CLAIMS]


class MountedRattataLedgeNegative:
    def __init__(self,fault):
        need(fault in FAULTS,"unknown copied Rattata control")
        self.fault,self.applied=fault,False

    def mutate(self,row,subjects):
        value=deepcopy(row)
        if self.applied or value.get("phase")!="observe" or not value.get("samples"):return value
        sample=value["samples"][0]
        actor=next(a for a in sample["actors"] if a.get("role")=="MOUNTED")
        if self.fault=="wrong-owner":actor["handle"]["encounterGeneration"]+=1
        elif self.fault=="wrong-profile":
            for row in value.get("profileCache",{}).get("resolvedProfiles",[]):
                if row.get("fingerprint")==actor.get("behaviorFingerprint"):
                    raw=bytearray.fromhex(row["resultHex"]);raw[89]=0;row["resultHex"]=raw.hex()
        elif self.fault=="wrong-target":
            # Change decoded-only data; byte equality must reject it first.
            target=next(t for t in sample["pokemonCombat"]["targets"] if t.get("role")=="MOUNTED")
            target["motion"]["plan"]["target"][1]=396
        elif self.fault=="missing-frame":value["samples"]=[]
        elif self.fault=="missing-release":
            event=next((e for e in value.get("events",[]) if e.get("data",{}).get("event")=="CONTROL_RETURNED"),None)
            if event is None:return value
            value["events"].remove(event)
        elif self.fault=="height-drift":
            if actor["motionPhase"]!="IDLE" or actor["logical"]!=dict(x=590,y=397):return value
            actor["engineObject"]["pos_y"]+=1;sample["player"]["pos_y"]+=1
        elif self.fault=="held-after-release":
            if value.get("action")!="release-through-hop-terminal" or actor["motionElapsed"]<3:return value
            sample["selector"].update(rawHeld=128,heldKeys=128)
        self.applied=True
        return value


def validate_negative_result(result,fault):
    reasons={"wrong-owner":"exactly one current active actor","wrong-profile":"authored Walk",
        "wrong-target":"native motion bytes differ","missing-frame":"raw chunk has missing",
        "missing-release":"ordered normal commit","height-drift":"exact ledge landing/base",
        "held-after-release":"normal DOWN/released input differs"}
    need(fault in FAULTS and result.get("passed") is False
         and any(reasons[fault] in str(f) for f in result.get("failures",[])),
         "copied Rattata control did not reject its exact fault")
