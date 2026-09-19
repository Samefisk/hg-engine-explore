"""Controller rows for same-reader Wild clear calibration, not movement credit."""
from copy import deepcopy
from tools.overworld.devtools_wild_clear_control_measurement import KIND, validate_control
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.normal_play_observer import complete_travel
from tools.overworld.devtools_wild_walk_proof import validate_idle_noop_clears

REQUIREMENT="shared.wild-clear-recorder-control-v1"
RULES=(("live-actor-identity","bound-wild-clear-subject"),
       ("controlled-action","same-reader-clear-fault"),
       ("controlled-action","exact-clear-restoration"),
       ("controlled-action","complete-natural-walk-before-control"))
CLAIMS=tuple(dict.fromkeys(c for c,_ in RULES))
FAULTS=("wild-clear-control-absent-subject","wild-clear-control-stale-subject",
        "wild-clear-control-missing-control","wild-clear-control-wrong-byte",
        "wild-clear-control-unrestored","wild-clear-control-clock","wild-clear-control-missing-clear")


def contract():
    result={}
    for claim,name in RULES:
        result.setdefault(claim,[]).append(dict(name=name,operator="eq",type="integer",validator="meaningful-observation",expected=1))
    return result


def measurements(replay,record):
    meter=replay.get("measurements",{}).get(KIND,{})
    if replay.get("passed") is not True or replay.get("failures")!=[] or meter.get("passed") is not True \
            or meter.get("closed") is not True or meter.get("ready") is not True or meter.get("acceptedProof") is not False \
            or meter.get("failures")!=[]:
        raise ValueError("Wild clear calibration lacks complete replay")
    subject=meter.get("subject",{})
    bound=select_current_actor(meter["terminal"],subject)
    if bound.get("role")!="WILD" or bound.get("species")!=19:raise ValueError("Wild clear calibration wrong subject")
    natural=meter.get("natural",{})
    if natural.get("ready") is not True or natural.get("failures")!=[] or natural.get("completeMotions")!=1 \
            or natural.get("subject")!=subject or natural.get("motion",{}).get("duration")!=4 \
            or not complete_travel(natural["motion"]) or len(natural.get("clearReceipts",[]))!=1:
        raise ValueError("Wild clear calibration lacks natural Walk")
    for name in ("MOTION_STARTED","LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"):
        if sum(e.get("data",{}).get("event")==name for e in natural.get("traces",[]))!=1:
            raise ValueError("Wild clear calibration missing native "+name)
    noops=natural.get("idleNoopClears",[])
    if not isinstance(noops,list) or len(noops)>63:
        raise ValueError("Wild clear calibration invalid idle no-op list")
    actual=natural["clearReceipts"][0]["data"]
    start=next(e for e in natural["traces"] if e["data"]["event"]=="MOTION_STARTED")
    sequences=validate_idle_noop_clears(noops,subject,natural["initial"],natural["motion"],start)
    if any(sequence>=actual["sequence"] for sequence in sequences):
        raise ValueError("Wild clear calibration idle no-op follows actual clear")
    validate_control(meter["control"],natural["clearReceipts"][0],meter["terminal"])
    cleanup=meter.get("cleanup",{});reader=cleanup.get("wildWalk",{})
    if cleanup.get("closed") is not True or cleanup.get("advancedFrames")!=0 or cleanup.get("acceptedProof") is not False \
            or reader.get("closed") is not True or reader.get("failure") is not None or reader.get("subject")!=subject \
            or reader.get("counts")!={"clear":len(natural["clearReceipts"])+len(natural.get("idleNoopClears",[]))} \
            or reader.get("guestMemoryWrites")!=2 \
            or reader.get("clearCalibration")!=meter["control"]:
        raise ValueError("Wild clear calibration cleanup differs")
    if record.get("sessionCleanup")!=dict(sessionId=record.get("sessionId"),closed=True,errors=[]):
        raise ValueError("Wild clear calibration private session did not close")
    return [dict(claim=c,name=n,value=1,operator="eq",expected=1,passed=True) for c,n in RULES]


class WildClearControlNegative:
    def __init__(self,fault):
        if fault not in FAULTS:raise ValueError("unknown Wild clear control fault")
        self.fault,self.applied=fault,False

    def mutate(self,row,subjects):
        if self.applied or row.get("phase")!="observe" or not subjects:return row
        result=deepcopy(row);handles={s["handle"]["value"] for s in subjects.values()}
        for sample in result.get("samples",[]):
            actor=next((a for a in sample.get("actors",[]) if a.get("handle",{}).get("value") in handles),None)
            if actor and self.fault=="wild-clear-control-absent-subject":sample["actors"].remove(actor);self.applied=True
            elif actor and self.fault=="wild-clear-control-stale-subject":actor["authorityGeneration"]+=1;self.applied=True
            if self.applied:break
        if not self.applied and self.fault=="wild-clear-control-missing-clear":
            for event in result.get("events",[]):
                if event.get("data",{}).get("observation")=="wild-walk-clear":
                    event["data"]["observation"]="unrelated-native-observation";self.applied=True;break
        if result.get("command")=="wild-walk.calibrate":
            receipt=result.get("receipt",{});control=receipt.get("wildWalkControl")
            if self.fault=="wild-clear-control-missing-control":receipt.pop("wildWalkControl",None);self.applied=True
            elif control and self.fault in ("wild-clear-control-wrong-byte","wild-clear-control-unrestored","wild-clear-control-clock"):
                if self.fault=="wild-clear-control-wrong-byte":control["bad"]=deepcopy(control["clean"])
                elif self.fault=="wild-clear-control-unrestored":control["restored"]=deepcopy(control["bad"])
                else:control["restoredClock"]["nativeCycle"]+=1
                self.applied=True
        return result if self.applied else row


def validate_negative_result(result,fault):
    if fault not in FAULTS or result.get("passed") is not False:raise ValueError("Wild clear copied fault did not fail")
    errors=result.get("failures",[])+result.get("measurements",{}).get(KIND,{}).get("failures",[])
    reasons=set()
    for error in errors:
        if isinstance(error,str):reasons.add(error)
        elif isinstance(error,dict):reasons.update(error[k] for k in ("detail","message") if isinstance(error.get(k),str))
    expected={"wild-clear-control-absent-subject":"selected handle must name exactly one current active actor",
        "wild-clear-control-stale-subject":"selected actor has a stale authorityGeneration",
        "wild-clear-control-missing-control":"Wild clear control is missing or not restored",
        "wild-clear-control-wrong-byte":"Wild clear fault or restoration differs",
        "wild-clear-control-unrestored":"Wild clear fault or restoration differs",
        "wild-clear-control-clock":"Wild clear control clocks differ",
        "wild-clear-control-missing-clear":"wild Walk clear receipts lost"}[fault]
    if expected not in reasons:raise ValueError("Wild clear copied fault failed for unrelated reason: "+fault)
