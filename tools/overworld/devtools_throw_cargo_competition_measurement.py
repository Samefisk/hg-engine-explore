"""A nearer normal Throw carrier can take free Cargo claimed by another.

Only existing completed snapshots, raw claims/bindings and sealed Cargo Tick
receipts are used. Setup never writes claims, timers, profiles or control.
"""
from copy import deepcopy
import struct

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.devtools_wild_throw_moving_candidate_measurement import (
    WildThrowMovingCandidateMeasurement, require, tile, validate_route_binding,
    TRIGGER_CONDITION, CARGO_CONDITION, THROW_APPLICATION_BIT, THROW_RELEASE_BIT,
)
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_moving_cargo_pickup import pickup_motion, checked_moving_pickup

KIND = "throw-cargo-competition-v1"
CASE = "wild.throw-cargo-competition"
REQUIREMENT = "current.throw-cargo-competition"
SUBJECTS = (("far-geodude",74,"WILD","spawn"),
            ("cargo",155,"WILD","spawn"),("near-geodude",74,"WILD","spawn"))
LIMIT = 300

def stage_args(frames, stage):
    return dict(frames=frames,keys=[],until=dict(kind="measurement-stage",measurement=KIND,stage=stage,when="final"))

SETUP = (("throw-tile","teleport",dict(map=33,x=584,z=402,facing=1)),
         ("prepare-passive-follower","party",dict(slot=0,species=155,level=20)),
         ("create-passive-follower","spawn",dict(species=155,form=0,role="follower",slot=0,level=20)),
         ("spawn-cargo","spawn",dict(species=155,form=0,role="wild",level=20,x=586,z=403)),
         ("bind-cargo","bind",dict(subject="cargo")),
         ("spawn-far-geodude","spawn",dict(species=74,form=0,role="wild",level=20,x=579,z=402)),
         ("bind-far-geodude","bind",dict(subject="far-geodude")),
         ("wait-far-claim","step",stage_args(160,"far-claimed")),
         ("spawn-near-geodude","spawn",dict(species=74,form=0,role="wild",level=20,x=585,z=403)),
         ("bind-near-geodude","bind",dict(subject="near-geodude")))
ACTIONS = (("normal-cargo-competition","step",dict(frames=LIMIT,keys=[],until=dict(
    kind="measurement-complete",measurement=KIND,when="final"))),)


def validate_recipe(test):
    require(test["id"]==CASE and test["mode"]=="prepared"
        and test["requirements"]==[REQUIREMENT]
        and test["subjects"]==[dict(id=n,species=s,role=r,acquire=a) for n,s,r,a in SUBJECTS]
        and test["measurements"]==[dict(kind=KIND,subject="far-geodude")]
        and tuple((a["id"],a["op"],a["args"]) for a in test["setup"])==SETUP
        and tuple((a["id"],a["op"],a["args"]) for a in test["actions"])==ACTIONS
        and test["assertions"]==[dict(kind="measurement-complete",measurement=KIND,when="final")]
        and test["budgets"]==dict(maxSeconds=240,maxFrames=700,noProgressFrames=350,minObservedFrames=2),
        "Cargo competition fixture differs from normal triggers and bounded claims")


class ThrowCargoCompetitionMeasurement:
    def __init__(self,source):
        require(source["contractVersion"]==2,"Cargo competition needs the sealed Query source")
        self.source=source;self.latest=None;self.subjects={};self.passive_subject=None
        self.setup_index=0;self.observed_frames=0;self.failures=[]
        self.far_claim=self.competition=self.pickup=self.launch=self.loser_resumed=None
        self.held_motion=None
        self.held_frames=0;self.held_protection=[]
        self.alerts={};self.helper=WildThrowMovingCandidateMeasurement(source)

    def _boundary(self,s):
        require(s.get("observationBoundary")=="main-task-queue-completion" and s.get("fieldAvailable") is True
            and type(s.get("frame")) is int and type(s.get("nativeCycle")) is int
            and type(s.get("actorFrame")) is int and s.get("context",{}).get("mapId")==33
            and s.get("fieldControl",{}).get("taskPointer")==0
            and (s["player"]["x"],s["player"]["y"])==(584,402),
            "Cargo competition left its current normal field boundary")
        if self.passive_subject is not None:
            a=next(a for a in s["actors"] if a["handle"]==select_current_actor(s,self.passive_subject)["handle"])
            require(a["species"]==155 and a["role"]=="FOLLOWER" and a["level"]==20
                and not a.get("matchedLayerMask",0)&THROW_APPLICATION_BIT,
                "Cargo competition passive follower changed")

    def _actor(self,s,name):
        h=select_current_actor(s,self.subjects[name])["handle"]
        a=next(a for a in s["actors"] if a["handle"]==h)
        require(a["active"] is True and a["presentationAttached"] is True
            and a["role"]=="WILD" and a["species"]==(155 if name=="cargo" else 74),
            "Cargo competition current full subject differs")
        return a

    def _relations(self,s):
        cargo=self._actor(s,"cargo");far=self._actor(s,"far-geodude")
        self.helper._claim(s,far,cargo)  # authenticate reader, raw masks and exact bindings
        inter=s["pokemonCombat"]["interactions"];state=inter["throwState"]
        rows={}
        for name in ("far-geodude","near-geodude"):
            if name not in self.subjects:continue
            actor=self._actor(s,name)
            row=next(r for r in inter["carriers"] if r["handle"]==actor["handle"])
            raw=bytes.fromhex(row["rawBindingsHex"])
            require(row["available"] is True and row["role"]=="WILD" and len(raw)==60
                and raw[:12]==raw_handle(actor["handle"])
                and raw[12:36].hex()==row["bindings"]["trigger"]["rawHex"]
                and raw[36:60].hex()==row["bindings"]["cargo"]["rawHex"],
                "Cargo competition binding owner/raw copy differs")
            encoded=state["targets"][actor["handle"]["slot"]]
            expected=dict(targetRaw=encoded,targetSlot=(encoded&63)-1 if encoded else None,
                carried=bool(encoded&128),windup=bool(encoded&64),
                targeted=bool(state["targetMask"]&(1<<actor["handle"]["slot"])),
                carrier=bool(state["carrierMask"]&(1<<actor["handle"]["slot"])),
                recovering=bool(state["recoveringMask"]&(1<<actor["handle"]["slot"])))
            require(row["throw"]==expected,"Cargo competition decoded claim differs")
            for key,kind,condition in (("trigger","PLAYER",TRIGGER_CONDITION),("cargo","ACTOR",CARGO_CONDITION)):
                b=row["bindings"][key]
                if b["bound"]:
                    target=b["target"]["actor"]
                    if kind=="ACTOR":
                        selected=next(a for a in s["actors"] if a["handle"]==target)
                        select_current_actor(s,selected)
                    validate_route_binding(b,kind,condition,target)
            if encoded:
                b=row["bindings"]["cargo"]
                require(b["bound"] and b["target"]["actor"]["slot"]==(encoded&63)-1
                    and state["carrierMask"]&(1<<actor["handle"]["slot"])
                    and state["targetMask"]&(1<<((encoded&63)-1)),
                    "Cargo competition relation lacks exact current Cargo binding")
            rows[name]=(actor,row,encoded)
        holders=[r for r in inter["carriers"] if r["throw"]["carried"]
                 and r["throw"]["targetSlot"]==cargo["handle"]["slot"]]
        require(len(holders)<=1,"Cargo competition has two HELD owners")
        if holders:
            require(holders[0]["bindings"]["cargo"]["target"]==dict(kind="ACTOR",actor=cargo["handle"]),
                    "Cargo competition HELD owner has stale Cargo")
        return cargo,rows,state,holders

    def _queries(self,s,events,actor):
        valid=[]
        for e in events:
            d=e.get("data",{})
            if e.get("kind")!="native-observation" or d.get("observation")!="throw-cargo-query" \
                    or d.get("slot")!=actor["handle"]["slot"]:continue
            raw=bytes.fromhex(d["resultHex"]);after=d["after"];image=d["imageIdentity"]
            require(e["frame"]==s["frame"] and d["subject"]==actor["handle"]
                and d["entryActorFrame"]==d["returnActorFrame"]==s["actorFrame"]
                and self.latest["nativeCycle"]<d["entryNativeCycle"]<=d["returnNativeCycle"]<=s["nativeCycle"]
                and d["boundary"]=="native-cargo-tick-return"
                and all(image.get(k)==v for k,v in self.source["queryImage"].items())
                and type(image.get("loadedEntry")) is int and image["loadedEntry"]>0
                and image.get("tickEntry",0)>image["loadedEntry"]
                and len(bytes.fromhex(image.get("loaderOwner","")))==28
                and len(raw)==140 and raw[138]==d["returnValue"]==d["resultStatus"]
                and after["frameValid"] is True and after["worldFrame"]==s["actorFrame"]
                and after["subject"]==after["worldSubject"]==actor["handle"]
                and struct.unpack_from("<H",raw,124)[0]<=16 and raw[127]+raw[128]<=1,
                "Cargo competition native query owner/source/clock/work differs")
            if d["status"]=="REACHABLE":
                q=after["workspace"]
                require(raw[138]==1 and q["owner"]==q["stateSubject"]==actor["handle"]
                    and q["ownerCurrent"] is True and q["valid"] is True,
                    "Cargo competition reachable query has wrong full owner")
            valid.append(deepcopy(e))
        return valid

    def _sample(self,s,events=(),*,observed=True):
        self._boundary(s);cargo,rows,state,holders=self._relations(s)
        far,fr,fe=rows["far-geodude"];target=cargo["handle"]["slot"]+1
        if self.far_claim is None and fe==target:
            require(far.get("motionKind")=="WALK" and far.get("motionPhase")=="MOVING"
                and far.get("reservationId",0)>0,
                "Cargo competition first claim is not normal accepted pursuit")
            motion,control=pickup_motion(s,far,self.source)
            require(motion["plan"]["flags"]==0 and motion["plan"]["reservationId"]==far["reservationId"]
                and motion["plan"]["kind"]==1 and control["movementActorControlMode"]==0,
                "Cargo competition first pursuit native plan differs")
            self.far_claim=dict(frame=s["frame"],actor=deepcopy(far),cargo=deepcopy(cargo),row=deepcopy(fr))
        if "near-geodude" in rows:
            near,nr,ne=rows["near-geodude"]
            qs=self._queries(s,events,near)
            if self.competition is None and fe==target and not holders and qs \
                    and nr["bindings"]["trigger"]["bound"]:
                require(self.far_claim is not None and self.far_claim["frame"]<s["frame"]
                    and sum(abs(a-b) for a,b in zip(tile(near,"logical"),tile(cargo,"logical")))
                      <sum(abs(a-b) for a,b in zip(tile(far,"logical"),tile(cargo,"logical"))),
                    "Cargo competition does not have a nearer current normal contender")
                self.competition=dict(frame=s["frame"],far=deepcopy(far),near=deepcopy(near),cargo=deepcopy(cargo),query=qs[0])
            if self.pickup is None and holders:
                require(holders[0]["handle"]==near["handle"] and ne&128 and ne&63==target
                    and self.competition is not None,
                    "Cargo competition farther carrier kept the free Cargo")
                require(fe==0 and not fr["bindings"]["cargo"]["bound"]
                    and not fr["bindings"]["trigger"]["bound"]
                    and not state["carrierMask"]&(1<<far["handle"]["slot"]),
                    "Cargo competition losing pursuit was not cleared at pickup")
                if cargo["motionPhase"]=="CANCELED":
                    checked_moving_pickup(self.latest,s,events,self.source,
                        self._actor(self.latest,"cargo"),cargo,
                        self._actor(self.latest,"near-geodude"),near)
                    self.held_motion=deepcopy(pickup_motion(s,cargo,self.source)[0])
                self.pickup=dict(frame=s["frame"],cargo=deepcopy(cargo),near=deepcopy(near),far=deepcopy(far),state=deepcopy(state))
            if self.pickup is not None and self.launch is None:
                timers=[r for r in s["pokemonCombat"]["movementTimers"] if r["handle"]==cargo["handle"]]
                require(len(timers)==1 and timers[0]["movementActorControlMode"]==1,
                    "Cargo competition Cargo lost HELD control before launch")
                if ne&128:
                    stopped=cargo["motionKind"]=="NONE" and cargo["motionPhase"]=="IDLE"
                    if self.held_motion is not None:
                        stopped=cargo["motionPhase"]=="CANCELED" \
                            and pickup_motion(s,cargo,self.source)[0]==self.held_motion
                    require(len(holders)==1 and holders[0]["handle"]==near["handle"]
                        and stopped and cargo["reservationId"]==0,
                        "Cargo competition already HELD Cargo changed owner")
                    self.held_frames+=1
                    self.held_protection.append(dict(frame=s["frame"],owner=deepcopy(near["handle"]),targetRaw=ne))
                else:
                    native=next(r["motion"] for r in s["pokemonCombat"]["targets"] if r["handle"]==cargo["handle"])
                    motion=decode_motion(bytes.fromhex(native["rawHex"]))
                    starts=[e for e in events if e.get("kind")=="native" and e.get("data",{}).get("event")=="MOTION_STARTED"
                            and e["data"].get("actorHandle")==cargo["handle"]["value"]]
                    require(ne==0 and len(starts)==1 and starts[0]["data"]["actor"]=={k:v for k,v in cargo["handle"].items() if k!="value"}
                        and cargo["motionKind"]=="HOP" and cargo["motionPhase"]=="MOVING"
                        and motion==native and motion["plan"]["flags"]==0 and motion["plan"]["reservationId"]==cargo["reservationId"]>0
                        and near["matchedLayerMask"]&THROW_RELEASE_BIT and self.held_frames>=2,
                        "Cargo competition lacks same exact Cargo normal launch")
                    self.launch=dict(frame=s["frame"],actor=deepcopy(cargo),event=deepcopy(starts[0]))
            if self.pickup is not None and self.loser_resumed is None:
                other=fr["bindings"]["cargo"]
                if s["frame"]>self.pickup["frame"] and ((other["bound"] and other["target"]["actor"]!=cargo["handle"])
                    or (far["motionPhase"]=="MOVING" and tile(far,"logical")!=tile(self.pickup["far"],"logical"))):
                    require(fe&63!=target,"Cargo competition losing carrier still targets HELD Cargo")
                    self.loser_resumed=dict(frame=s["frame"],actor=deepcopy(far),row=deepcopy(fr))
        if observed:self.observed_frames+=1
        require(self.observed_frames<=LIMIT,"Cargo competition exceeded its bounded window")
        self.latest=deepcopy(s)

    def observe_record(self,row,on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row["phase"]=="setup","Cargo competition initial boundary differs")
                self.latest=deepcopy(row["initialSnapshot"]);return self.result()
            if row.get("phase")=="setup":
                name,op,args=SETUP[self.setup_index]
                require(row.get("action")==name,"Cargo competition setup order differs")
                if op=="step":
                    for s,events,_ in validate_raw_chunk(row,self.latest):
                        self._sample(s,events,observed=False)
                        if on_sample:on_sample(s,self.observed_frames)
                    if self.stage("far-claimed"):self.setup_index+=1
                    return self.result()
                require(row.get("command")==op,"Cargo competition setup command differs")
                s=row["snapshot"];self._boundary(s)
                if name=="create-passive-follower":
                    actors=[a for a in s["actors"] if a["active"] and a["role"]=="FOLLOWER"]
                    require(len(actors)==1 and row["receipt"].get("lifecycle")=="prepared-native-follower-lifecycle",
                            "Cargo competition passive follower lifecycle differs")
                    self.passive_subject=select_current_actor(s,actors[0])
                if op=="bind":self.subjects[args["subject"]]=deepcopy(row["receipt"]);self._actor(s,args["subject"])
                self.latest=deepcopy(s);self.setup_index+=1;return self.result()
            require(self.setup_index==len(SETUP) and row.get("phase")=="observe"
                and row.get("action")==ACTIONS[0][0] and "command" not in row,
                "Cargo competition normal action differs")
            for s,events,_ in validate_raw_chunk(row,self.latest):
                self._sample(s,events)
                if on_sample:on_sample(s,self.observed_frames)
        except (KeyError,TypeError,ValueError,StopIteration,IndexError) as e:self.failures.append(str(e))
        return self.result()

    def stage(self,name):return not self.failures and name=="far-claimed" and self.far_claim is not None
    def result(self):
        ready=not self.failures and self.launch is not None and self.loser_resumed is not None
        return dict(ready=ready,observedFrames=self.observed_frames,observedFrameUnit="completed-game-frame",
            requirements=[REQUIREMENT],subjects=deepcopy(self.subjects),farClaim=deepcopy(self.far_claim),
            competition=deepcopy(self.competition),pickup=deepcopy(self.pickup),launch=deepcopy(self.launch),
            loserResumed=deepcopy(self.loser_resumed),heldFrames=self.held_frames,
            heldProtection=deepcopy(self.held_protection),failures=list(self.failures))
    def finish(self):
        if not self.result()["ready"] and not self.failures:self.failures.append("Cargo competition ended without nearer pickup, protected HELD owner, launch and losing carrier progress")
        return dict(passed=self.result()["ready"],failures=list(self.failures))
