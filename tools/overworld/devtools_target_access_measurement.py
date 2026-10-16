"""Two finite native controls for shared actor-target physical access.

Uses the current actor, binding, terrain and motion readers. A requested spawn
tile is never surface credit. The inaccessible case must also complete a real
normal Follow movement, so a silent stopped follower cannot pass.
"""
from copy import deepcopy
import struct

from tools.overworld.devtools_follower_throw_measurement import (
    FollowerThrowMeasurement, TRIGGER_CONDITION, APPLICATION, APPLICATION_LOCAL, THROW_MASK,
    raw_handle, require, tile,
)
from tools.overworld.devtools_movement_predicates import check_movement_predicate
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion

KINDS = ("follower-target-access-signpost-v1", "follower-target-access-ground-v1")
CASES = {
    KINDS[0]: dict(id="follower.target-access-signpost", species=16, target=(581,397), raised=True),
    KINDS[1]: dict(id="follower.target-access-ground", species=143, target=(581,398), raised=False),
}
WINDOW = 8


def target_permission(cell):
    surface = cell.get("surface", {})
    require(surface.get("known") is True, "target access actual surface permission is unknown")
    if surface.get("present") is False:
        return 1  # This controlled target is supported LAND.
    require(surface.get("present") is True and surface.get("type") == "signpost",
        "target access actual surface permission differs")
    return 0x80


def requirement(kind):
    return "current." + CASES[kind]["id"].replace(".", "-", 1)


def subjects(kind):
    return (("mankey",56,"FOLLOWER","existing"),
            ("target",CASES[kind]["species"],"WILD","spawn"))


def stage(kind, name):
    return dict(kind="measurement-stage",measurement=kind,stage=name,when="final")


def setup(kind):
    x,z=CASES[kind]["target"]
    steps = (("route29", "teleport", dict(map=33,x=585,z=402,facing=1)),
        ("prepare-passive", "party", dict(slot=0,species=155,level=20)),
        ("create-passive", "spawn", dict(species=155,form=0,role="follower",slot=0,level=20)),
        ("spawn-target", "spawn", dict(species=CASES[kind]["species"],form=0,role="wild",level=5,x=x,z=z)),
        ("bind-target", "bind", dict(subject="target")),
        ("settle-target", "step", dict(frames=160,keys=[],until=stage(kind,"target-settled"))),
        ("read-target-terrain", "terrain", dict(x=581,z=398,radius=2)),
        ("walk-west", "step", dict(frames=80,keys=["LEFT"],until=dict(kind="player-field",path="x",operator="eq",value=580,when="final"))),
        ("settle-west", "step", dict(frames=16,keys=[],until=dict(kind="player-settled-at",map=33,x=580,z=402,when="final"))),
        ("walk-north", "step", dict(frames=64,keys=["UP"],until=dict(kind="player-field",path="y",operator="eq",value=398,when="final"))),
        ("settle-north", "step", dict(frames=16,keys=[],until=dict(kind="player-settled-at",map=33,x=580,z=398,when="final"))),
        ("settle-passive", "step", dict(frames=64,keys=[],until=dict(kind="follower-settled",species=155,partySlot=0,when="final"))),
        ("prepare-mankey", "party", dict(slot=0,species=56,level=20)),
        ("create-mankey", "spawn", dict(species=56,form=0,role="follower",slot=0,level=20)),
        ("bind-mankey", "bind", dict(subject="mankey")))
    # Finish follower setup before the wandering ground target is created.
    # Its ordinary profile and the landing/terrain checks remain unchanged.
    return steps if CASES[kind]["raised"] else steps[:3]+steps[7:12]+steps[12:]+steps[3:7]


def actions(kind):
    if not CASES[kind]["raised"]:
        return (("notice-ground", "step", dict(frames=64,keys=[],until=dict(kind="measurement-complete",measurement=kind,when="final"))),)
    return (("approach-post", "step", dict(frames=16,keys=["UP"],until=dict(kind="player-field",path="y",operator="eq",value=397,when="final"))),
        ("reject-post", "step", dict(frames=120,keys=[],until=stage(kind,"rejected"))),
        ("walk-away", "step", dict(frames=16,keys=["DOWN"],until=dict(kind="player-field",path="y",operator="eq",value=398,when="final"))),
        ("normal-follow", "step", dict(frames=120,keys=[],until=dict(kind="measurement-complete",measurement=kind,when="final"))))


def validate_recipe(test):
    kind=test["measurements"][0]["kind"]
    require(kind in CASES and test["id"]==CASES[kind]["id"] and test["mode"]=="prepared"
        and test["requirements"]==[requirement(kind)]
        and test["subjects"]==[dict(id=n,species=s,role=r,acquire=a) for n,s,r,a in subjects(kind)]
        and test["measurements"]==[dict(kind=kind,subject="mankey")]
        and tuple((a["id"],a["op"],a["args"]) for a in test["setup"])==setup(kind)
        and tuple((a["id"],a["op"],a["args"]) for a in test["actions"])==actions(kind)
        and test["assertions"]==[dict(kind="measurement-complete",measurement=kind,when="final")]
        and test["budgets"]["maxFrames"]==650 and test["budgets"]["minObservedFrames"]==WINDOW,
        "target access fixed native fixture differs")


class TargetAccessMeasurement:
    _actor = FollowerThrowMeasurement._actor
    _carrier = FollowerThrowMeasurement._carrier
    _events = FollowerThrowMeasurement._events
    _profile_events = FollowerThrowMeasurement._profile_events

    def __init__(self, source, kind):
        require(kind in CASES and set(source)=={"contractVersion","romSha256","overlaySha256","profileSha256"}
            and source["contractVersion"]==1 and all(isinstance(source[n],str)
            and len(source[n])==64 and set(source[n])<=set("0123456789abcdef")
            for n in ("romSha256","overlaySha256","profileSha256")), "target access source identity missing")
        self.kind=kind;self.case=CASES[kind];self.source=source
        self.subjects={};self.profiles={};self.latest=None;self.terrain=None
        self.setup_index=self.action_index=self.step_frames=self.observed_frames=0
        self.failures=[];self.visible=[];self.notice=None;self.follow=None;self.follow_complete=None
        self.terminal=None

    def _boundary(self,s):
        require(s.get("fieldAvailable") is True and s.get("observationBoundary")=="main-task-queue-completion"
            and s.get("romSha256")==self.source["romSha256"] and type(s.get("frame")) is int
            and type(s.get("nativeCycle")) is int and s.get("context",{}).get("mapId")==33
            and s.get("fieldControl",{}).get("taskPointer")==0,
            "target access lacks current Route29 field control")

    def _target_settled(self,s):
        if "target" not in self.subjects:return False
        t=self._actor(s,"target")
        return tile(t)==self.case["target"] and t["motionPhase"]=="IDLE" and t["reservationId"]==0 \
            and t["engineObject"].get("unk88_y")==0

    def _terrain(self,s):
        terrain=s.get("terrain",{});o=terrain.get("observation",{})
        require(self.terrain is None and o.get("nativeCycle")==s["nativeCycle"]
            and o.get("lastCompletedGameFrame")==s["frame"] and o.get("context")==s["context"],
            "target access terrain clock or context differs")
        cells=[c for c in terrain.get("cells",[]) if (c.get("x"),c.get("z",c.get("y")))==self.case["target"]]
        require(len(cells)==1 and cells[0].get("loaded") is True
            and cells[0].get("provenance",{}).get("mapHeaderId")==33
            and cells[0]["provenance"].get("fieldPointer")==s["fieldControl"]["fieldPointer"]
            and cells[0]["provenance"].get("chunkModelLoaded")==1,
            "target access target terrain is unknown or foreign")
        c=cells[0];surface=c.get("surface",{})
        require(surface.get("known") is True and surface.get("present") is self.case["raised"],
            "target access actual native surface differs")
        if self.case["raised"]:
            require(surface.get("type")=="signpost" and surface.get("surfaceId")==9313
                and surface.get("heightMode")=="absolute" and surface.get("finalHeightKnown") is True
                and type(surface.get("heightFx32")) is int,
                "target access lacks real absolute Signpost support")
        else:require(c.get("collision") is False,"target access ground is blocked")
        require(self._target_settled(s),"target access target has not landed")
        t=self._actor(s,"target")
        require(not self.case["raised"] or t["engineObject"]["pos_y"]==surface["heightFx32"],
            "target access target pose differs from real surface")
        self.terrain=dict(frame=s["frame"],nativeCycle=s["nativeCycle"],context=deepcopy(s["context"]),
            romSha256=s["romSha256"],cell=deepcopy(c),target=deepcopy(t))

    def _condition(self,carrier,m):
        rows=[r for r in carrier.get("conditionCaptures",[]) if r.get("conditionId")==TRIGGER_CONDITION]
        require(len(rows)==1,"target access lacks the authored Notice state")
        r=rows[0];raw=bytes.fromhex(r.get("rawHex",""));prepared=bytes.fromhex(r.get("preparedRawHex",""))
        count,valid,capacity=(struct.unpack_from("<BBH",prepared,80) if len(prepared)==88 else (0,0,0))
        subject_damage_pending = struct.unpack_from("<H",prepared,86)[0] if len(prepared)==88 else None
        index=r.get("preparedIndex");catalog=r.get("catalogIndex")
        require(len(raw)==16 and len(prepared)==88 and prepared[:12]==raw_handle(m["handle"])
            and valid==1 and 0<=count<=capacity<=32 and type(index) is int and 0<=index<count
            and type(catalog) is int and 0<=catalog<=65535
            and struct.unpack_from("<H",prepared,16+2*index)[0]==catalog
            and struct.unpack_from("<H",prepared,84)[0]==m["species"] and subject_damage_pending in (0,1)
            and struct.unpack_from("<I",prepared,12)[0]==r.get("statesPointer")
            and r.get("application")==APPLICATION and r.get("applicationLocal")==APPLICATION_LOCAL
            and r.get("activationMode")==0
            and r.get("durationFrames")==r.get("cooldownFrames")==0
            and struct.unpack_from("<II",raw)==(r["activeUntil"],r["cooldownUntil"])
            and raw[15]==r["flags"] and not raw[15]&128,
            "target access Notice bytes or full owner differ")
        target=r["target"];actor=target.get("actor")
        require(raw[14]=={"NONE":0,"PLAYER":1,"ACTOR":2}.get(target["kind"])
            and (raw[14]!=2 or struct.unpack_from("<3H",raw,8)==tuple(actor[k] for k in
                ("slot","generation","encounterGeneration"))),"target access Notice capture differs")
        return r

    def _sample(self,s,events):
        self._boundary(s);self._profile_events(events)
        m,t=(self._actor(s,n) for n in ("mankey","target"))
        carrier,_=self._carrier(s,m);condition=self._condition(carrier,m)
        require(self.terrain is not None and self.terrain["context"]==s["context"]
            and tile(t)==self.case["target"],"target access lost its actual target fixture")
        if self.case["raised"]:
            require(t["engineObject"]["pos_y"]==self.terrain["cell"]["surface"]["heightFx32"]
                and t["motionPhase"]=="IDLE" and t["reservationId"]==0,
                "target access Signpost actor changed physical support")
        profile=self.profiles.get(m["behaviorFingerprint"])
        require(profile is not None and profile["appliedOverrides"]==m["matchedLayerMask"],
            "target access lacks the current resolved native profile")
        lane=bytes.fromhex(profile["lanes"][0]);allowed=struct.unpack_from("<H",lane,32)[0]
        physical_mask = target_permission(self.terrain["cell"])
        if self.case["raised"]:
            require(not allowed&physical_mask,"target access fixture permits actual Signpost")
        else:
            require(allowed&physical_mask,"target access fixture cannot reach actual LAND")
        dx,dy=(b-a for a,b in zip(tile(m),tile(t)))
        adjacent=max(abs(dx),abs(dy))==1
        # Adjacent awareness has no intermediate tile and needs no copied ray.
        if adjacent:
            witness=dict(frame=s["frame"],nativeCycle=s["nativeCycle"],subject=deepcopy(m["handle"]),
                target=deepcopy(t["handle"]),subjectTile=list(tile(m)),targetTile=list(tile(t)),
                subjectBaseY=m["engineObject"]["pos_y"],targetBaseY=t["engineObject"]["pos_y"],
                allowedTerrainMask=allowed,condition=deepcopy(condition),binding=deepcopy(carrier["bindings"]["trigger"]),
                profile=deepcopy(profile))
            if self.case["raised"]:
                require(not condition["flags"]&1 and carrier["bindings"]["trigger"]["bound"] is False
                    and not m["matchedLayerMask"]&THROW_MASK and not carrier["throw"]["targetRaw"],
                    "inaccessible Signpost admitted Notice or Throw")
                self.visible.append(witness)
            elif self.notice is None:
                b=carrier["bindings"]["trigger"]
                require(condition["flags"]&1 and condition["targetCurrent"] is True
                    and condition["target"]["actor"]==t["handle"] and b["bound"] is True
                    and b["sourceConditionId"]==TRIGGER_CONDITION and b["sourceApplication"]==APPLICATION
                    and b["sourceApplicationLocal"]==APPLICATION_LOCAL
                    and b["targetCurrent"] is True and b["target"]["actor"]==t["handle"]
                    and m["matchedLayerMask"]&(1<<APPLICATION_LOCAL),
                    "accessible ground lacks exact current Notice capture")
                self.notice=witness
        own=self._events(events,m)
        if self.case["raised"] and len(self.visible)>=WINDOW:
            require(not carrier["bindings"]["trigger"]["bound"] and not m["matchedLayerMask"]&THROW_MASK,
                "inaccessible Signpost later admitted Throw")
            if self.follow is None and any(e.get("event")=="MOTION_STARTED" for e in own):
                row=next(r for r in s["pokemonCombat"]["targets"] if r["handle"]==m["handle"])
                motion=decode_motion(bytes.fromhex(row["motion"]["rawHex"]));plan=motion["plan"]
                require(motion==row["motion"] and plan["kind"] in (1,2) and not plan["flags"]&1
                    and motion["phase"]=="MOVING" and motion["elapsed"]==0 and plan["reservationId"]==m["reservationId"]!=0
                    and plan["origin"]==list(tile(m,"origin")) and plan["target"]==list(tile(m,"target"))
                    and plan["origin"]!=plan["target"],"target access Follow has no current normal accepted plan")
                self.follow=dict(frame=s["frame"],plan=deepcopy(plan),commitBefore=m["commitSequence"],events=deepcopy(own))
            elif self.follow is not None and self.follow_complete is None:
                self.follow["events"].extend(deepcopy(own))
                if any(e.get("event")=="CONTROL_RETURNED" for e in own):
                    commit=self.follow["commitBefore"]+1
                    ordered=[e for e in self.follow["events"] if e.get("event") in
                        ("MOTION_STARTED","LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED")]
                    end=next(i for i,e in enumerate(ordered) if e["event"]=="CONTROL_RETURNED")
                    ordered=ordered[:end+1]
                    require([e["event"] for e in ordered]==["MOTION_STARTED","LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"]
                        and ordered[1]["valueA"]==ordered[2]["valueA"]==ordered[3]["valueB"]==commit
                        and m["commitSequence"]==commit and tile(m)==tuple(self.follow["plan"]["target"])
                        and m["inputOwnership"]==0
                        and s["frame"]==self.follow["frame"]+self.follow["plan"]["duration"]+self.follow["plan"]["pauseFrames"]
                        and [m["engineObject"][k] for k in ("pos_x","pos_z")]
                            ==[(v<<16)+32768 for v in self.follow["plan"]["target"]]
                        and m["engineObject"]["unk88_y"]==0,
                        "target access Follow lacks same-owner commit and control")
                    self.follow_complete=dict(self.follow,returnFrame=s["frame"],commitAfter=commit)
        self.observed_frames+=1;self.terminal=deepcopy(s)

    def _done(self,args,s):
        p=args.get("until")
        if p is None:return self.step_frames>=args["frames"]
        if p["kind"]=="measurement-stage":return self.stage(p["stage"])
        if p["kind"]=="measurement-complete":return self.ready
        if p["kind"]=="player-field":return s["player"][p["path"]]==p["value"]
        return check_movement_predicate(p,s)

    def observe_record(self,row,on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None,"duplicate target access initial boundary")
                self.latest=deepcopy(row["initialSnapshot"]);self._profile_events(row.get("initialEvents",[]));return self.result()
            is_setup=row.get("phase")=="setup";steps=setup(self.kind) if is_setup else actions(self.kind)
            index=self.setup_index if is_setup else self.action_index
            # The job emits no step row when this predicate is already true.
            # Admit only that exact wait, proved by the last full bound actor.
            if is_setup and index+1<len(steps) and steps[index][0]=="settle-target" \
                    and steps[index+1][0]==row.get("action")=="read-target-terrain" \
                    and row.get("command")=="terrain":
                require(self.latest is not None and self._target_settled(self.latest),
                    "target access skipped wait lacks its settled current target")
                self.setup_index+=1;index+=1;self.step_frames=0
            require(index<len(steps) and row.get("action")==steps[index][0]
                and (is_setup or self.setup_index==len(setup(self.kind))),"target access action order differs")
            _,op,args=steps[index]
            if op=="step":
                require("command" not in row,"target access movement used a prepared command")
                for sample,events,_ in validate_raw_chunk(row,self.latest):
                    self._boundary(sample);self._profile_events(events);self.step_frames+=1
                    require(self.step_frames<=args["frames"],"target access frame bound exceeded")
                    if not is_setup:self._sample(sample,events)
                    self.latest=deepcopy(sample)
                    if on_sample:on_sample(sample,self.observed_frames)
                if not self._done(args,self.latest):return self.result()
            else:
                require(is_setup and row.get("command")==op,"target access setup command differs")
                sample=row["snapshot"];self._boundary(sample)
                self._profile_events(row.get("events",[])+row.get("receipt",{}).get("events",[]))
                if op=="bind":
                    selected=select_current_actor(sample,row["receipt"]);name=args["subject"]
                    expected=next((s,r) for n,s,r,_ in subjects(self.kind) if n==name)
                    require((selected["species"],selected["role"])==expected,"target access bound subject differs")
                    self.subjects[name]=deepcopy(row["receipt"])
                if op=="terrain":self._terrain(sample)
                self.latest=deepcopy(sample)
            self.step_frames=0
            if is_setup:self.setup_index+=1
            else:self.action_index+=1
        except (ValueError,KeyError,TypeError,StopIteration,struct.error) as error:self.failures.append(str(error))
        return self.result()

    @property
    def ready(self):
        return not self.failures and self.observed_frames>=WINDOW and (self.follow_complete is not None
            if self.case["raised"] else self.notice is not None)

    def stage(self,name):
        require(name in ("target-settled","rejected"),"unknown target access stage")
        return self._target_settled(self.latest) if name=="target-settled" else len(self.visible)>=WINDOW

    def result(self):
        return dict(kind=self.kind,requirements=[requirement(self.kind)],ready=self.ready,passed=self.ready,
            acceptedProof=False,observedFrames=self.observed_frames,observedFrameUnit="completed-game-frame",
            subjects=deepcopy(self.subjects),terrainWitness=deepcopy(self.terrain),visibleWitnesses=deepcopy(self.visible[:WINDOW]),
            noticeWitness=deepcopy(self.notice),followComplete=deepcopy(self.follow_complete),terminal=deepcopy(self.terminal),failures=list(self.failures))

    def finish(self):
        if not self.ready and not self.failures:self.failures.append("target access ended without its complete access and movement proof")
        return self.result()
