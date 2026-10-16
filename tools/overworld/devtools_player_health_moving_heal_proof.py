"""Moving-heal claims and copied-stream controls use the same exact meter."""
from copy import deepcopy
from tools.overworld.devtools_player_health_moving_heal_measurement import KINDS, REQUIREMENT, MODES, require

NAMES={"live-actor-identity":("same-field-and-current-role-actors",),
       "engine-boundary":("real-hit-minus20", "eligible-delay300-and-rate10", "saved-live-hp-equal"),
       "natural-input":("normal-travel-during-wait-and-healing",),
       "control-release":("no-second-hit-menu-battle-or-role-loss",)}
SUFFIXES=("wrong-damage", "old-movement-reset", "early-heal", "wrong-rate", "paused-clock", "missing-profile", "no-travel", "second-hit")


def requirement(kind):
    require(kind in KINDS,"unknown moving-heal kind");return REQUIREMENT


def claims(kind):require(kind in KINDS,"unknown moving-heal kind");return tuple(NAMES)


def faults(kind):require(kind in KINDS,"unknown moving-heal kind");return tuple(kind+":"+n for n in SUFFIXES)


def contract(kind):
    claims(kind)
    return {c:[dict(name=n,operator="eq",type="integer",validator="meaningful-observation",expected=1) for n in ns] for c,ns in NAMES.items()}


def measurements(kind,replay,record):
    result=replay.get("measurements",{}).get(kind,{})
    require(replay.get("passed") is True and replay.get("failures")==[] and result.get("ready") is True
            and result.get("mode")==MODES[kind] and result.get("acceptedProof") is False
            and result.get("observedFrames")==replay.get("observedFrames")
            and result.get("eligibleHealthFrames")==result.get("rawFramesAfterHit")==360 and result.get("hpAfter")==90,
            "moving-heal lacks exact current-role hit, wait and rate")
    require(record.get("sessionCleanup")==dict(sessionId=record.get("sessionId"),closed=True,errors=[]),"moving-heal owned session cleanup is missing")
    return [dict(claim=c,name=n,value=1,operator="eq",expected=1,passed=True) for c,ns in NAMES.items() for n in ns]


class MovingHealNegative:
    def __init__(self,kind,fault):
        require(fault in faults(kind),"unknown moving-heal copied control")
        self.kind,self.fault,self.applied=kind,fault.rsplit(":",1)[1],False

    def mutate(self,row,subjects):
        if row.get("phase")!="observe":return row
        changed=deepcopy(row);name=row.get("action");hp=changed.get("receipt",{}).get("playerHealth",{})
        targets={"wrong-damage":"at-contact","old-movement-reset":"after-delay","early-heal":"after-delay","wrong-rate":"after-one-second","paused-clock":"after-delay","second-hit":"first-heal"}
        if name==targets.get(self.fault):
            if self.fault=="wrong-damage":hp["hp"]=hp["savedHp"]=81
            elif self.fault=="old-movement-reset":hp["restFrames"]=0
            elif self.fault=="early-heal":hp["hp"]=hp["savedHp"]=81
            elif self.fault=="wrong-rate":hp["hp"]=hp["savedHp"]=89
            elif self.fault=="paused-clock":hp["lastHealthFrame"]-=1
            else:hp["acceptedHits"]=2
            self.applied=True
        elif self.fault=="missing-profile" and name=="wait-contact":
            changed.pop("profileCache",None);self.applied=True
        elif self.fault=="no-travel" and name and (name.startswith("move-") or name in ("after-delay","before-first-heal","first-heal","after-one-second")):
            # The dense stream stays coherent, but supplies no ordinary input motion.
            for sample in [*changed.get("samples",[]), *([changed["snapshot"]] if "snapshot" in changed else [])]:
                sample["player"]["movement_cmd"]=62
                for a in sample.get("actors",[]):
                    if a.get("role")=="MOUNTED":a["motionKind"]="HOP"
            self.applied=True
        return changed if self.applied else row


def validate_negative_result(kind,result,fault):
    require(fault in faults(kind) and result.get("passed") is False and result.get("failures"),"moving-heal copied control did not fail")
    failures=result.get("measurements",{}).get(kind,{}).get("failures",[])
    expected={"wrong-damage":"one real hit", "old-movement-reset":"delay, rate", "early-heal":"delay, rate", "wrong-rate":"delay, rate", "paused-clock":"eligible HP clock", "second-hit":"delay, rate", "missing-profile":"native profile cache", "no-travel":"real role-matched movement"}[fault.rsplit(":",1)[1]]
    require(any(expected in str(f) for f in failures),"moving-heal copied control failed for a different reason")
