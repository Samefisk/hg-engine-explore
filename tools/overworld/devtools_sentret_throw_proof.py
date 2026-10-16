"""Exact concurrent load/Throw proof; copied data grants no game credit."""
from copy import deepcopy
from tools.overworld.devtools_sentret_throw_measurement import KIND, REQUIREMENT, HANDLE_KEYS, need
from tools.overworld.devtools_records import select_current_actor, engine_binding_identity

NAMES = {
    "live-actor-identity": ("three-native-sentret-and-saved-mankey-full-identities",),
    "profile-resolution": ("same-natural-interest-cargo-through-native-held-windup",),
    "rendered-motion": ("same-cargo-native-outward-eight-tile-throw",),
    "frame-pacing": ("same-six-hundred-native-main-loop-returns-zero-late",
                     "normal-input-render-stalls-zero"),
}
CLAIMS = tuple(NAMES)
FAULTS = tuple(KIND+":"+n for n in ("third-refused", "missing-held", "missing-launch",
                                  "wrong-saved-mankey", "late-loop", "lost-native-data"))

def contract():
    return {claim:[dict(name=name,operator="eq",type="integer",validator="meaningful-observation",expected=1)
                   for name in names] for claim,names in NAMES.items()}

def measurements(replay,record):
    result=replay.get("measurements",{}).get(KIND,{})
    need(replay.get("passed") is True and replay.get("failures")==[]
         and result.get("passed") is True and result.get("ready") is True and result.get("closed") is True
         and result.get("failures")==[] and result.get("acceptedProof") is False
         and result.get("requirements")==[REQUIREMENT]
         and result.get("observedFrames")==replay.get("observedFrames")==600
         and result.get("observedFrameUnit")=="completed-main-loop-return"
         and set(result.get("subjects",{}))=={"mankey","sentret-a","sentret-b","sentret-c","cargo"}
         and len(result.get("pacing",[]))==600 and result.get("throw") is not None
         and result.get("movingFrames",0)>0 and result.get("renderStalls")==0
         and result.get("cpu")==dict(observedNativeFrames=1200,closed=True,failure=None),
         "combined Sentret Throw/pacing proof is incomplete")
    need(record.get("sessionCleanup")==dict(sessionId=record.get("sessionId"),closed=True,errors=[]),
         "owned Sentret Throw session did not close cleanly")
    return [dict(claim=claim,name=name,value=1,operator="eq",expected=1,passed=True)
            for claim,names in NAMES.items() for name in names]

class SentretThrowNegative:
    def __init__(self,fault):
        need(fault in FAULTS,"unknown copied fault")
        self.fault=fault.rsplit(":",1)[1];self.applied=False
        self.cargo=None;self.held_seen=False

    def _same_cargo(self,value):
        return all(value.get(k)==self.cargo.get(k) for k in (
            "handle","subjectIdentity","species","role","authorityGeneration",
            "engineAnchorGeneration","presentationGeneration")) \
            and engine_binding_identity(value.get("engineIdentity"))==engine_binding_identity(self.cargo.get("engineIdentity"))

    def mutate(self,row,subjects):
        if self.applied:return row
        changed=deepcopy(row)
        if row.get("action")=="spawn-cargo":
            sample=row["snapshot"];value=row["receipt"]["value"]
            native=value["entrySpawn"]["receipt"]["actor"]
            actors=[a for a in sample["actors"] if a.get("species")==69 and a.get("role")=="WILD"
                    and a.get("subjectIdentity")==value["personality"]
                    and all(a.get("handle",{}).get(k)==native.get(k) for k in HANDLE_KEYS)]
            need(len(actors)==1,"copied Cargo lacks its created full identity")
            self.cargo=select_current_actor(sample,actors[0])
        if self.cargo is not None and subjects.get("cargo") is not None:
            need(self._same_cargo(subjects["cargo"]),"copied Cargo binding changed")
        if self.fault=="third-refused" and row.get("action")=="spawn-sentret-c":
            changed["receipt"]["value"]["entrySpawn"]["receipt"]["status"]=0
            self.applied=True
        samples={s["frame"]:s for s in changed.get("samples",[])}
        if changed.get("snapshot") is not None:samples[changed["snapshot"]["frame"]]=changed["snapshot"]
        for sample in samples.values():
            if self.fault=="wrong-saved-mankey":
                next(p for p in sample["party"] if p["slot"]==2)["personality"]+=1;self.applied=True
            elif self.fault=="lost-native-data":
                sample["nativeObservation"]["eventsDropped"]=1;self.applied=True
            elif self.cargo is not None:
                cargo=select_current_actor(sample,self.cargo)
                carriers=sample.get("pokemonCombat",{}).get("interactions",{}).get("carriers",[])
                own=[r for r in carriers if r.get("role")=="FOLLOWER" and r.get("slot")==7]
                flags=own[0].get("throw",{}) if len(own)==1 else {}
                if flags.get("carried") is True and flags.get("targetSlot")==cargo["handle"]["slot"]:
                    self.held_seen=True
                    if self.fault=="missing-held":
                        timers=[t for t in sample.get("pokemonCombat",{}).get("movementTimers",[])
                                if t.get("handle")==cargo["handle"]
                                and t.get("sourceIdentity",{}).get("personality")==cargo["subjectIdentity"]]
                        if len(timers)==1 and timers[0].get("movementActorControlMode")==1:
                            timers[0]["movementActorControlMode"]=0;self.applied=True
            if self.applied:break
        for event in changed.get("events",[]):
            data=event.get("data",{})
            if self.fault=="late-loop" and data.get("observation")=="stock-main-loop-pacing" and data.get("intervalFromPrevious") is not None:
                data["frameCounter"]=3;self.applied=True;break
            if self.fault=="missing-launch" and self.cargo is not None and self.held_seen \
                    and event.get("kind")=="native" and data.get("event")=="MOTION_STARTED" \
                    and data.get("actorHandle")==self.cargo["handle"]["value"] \
                    and data.get("actor")=={k:self.cargo["handle"][k] for k in HANDLE_KEYS}:
                sample=samples.get(event["frame"])
                need(sample is not None and self._same_cargo(select_current_actor(sample,self.cargo)),
                     "copied launch lacks its current created Cargo")
                data["event"]="MOTION_FINISHED";self.applied=True;break
        return changed if self.applied else row

def validate_negative_result(result,fault):
    need(fault in FAULTS and result.get("passed") is False,"copied control did not fail")
    reason={"third-refused":"spawn lacks actual ADOPT", "missing-held":"Cargo has no native HELD control",
            "missing-launch":"no actual outward Throw launch", "wrong-saved-mankey":"saved Mankey party identity differs",
            "late-loop":"late main loop", "lost-native-data":"native reader lost data"}[fault.rsplit(":",1)[1]]
    text=repr(result.get("failures",[]))+repr(result.get("measurements",{}).get(KIND,{}).get("failures",[]))
    need(reason in text,"copied fault failed for an unrelated reason: "+fault)
