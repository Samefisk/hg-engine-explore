"""Two fixed signed-height Throw cases using existing native observations.

A catalog coordinate never earns height or contact credit. The lower geometry
is a candidate until a fresh native run proves it; every height gate stays strict.
"""
from copy import deepcopy
from fractions import Fraction
import struct
from tools.overworld.devtools_follower_throw_measurement import (
    FollowerThrowMeasurement, BOUNDARY, FOLLOWER, FIND_CARGO, RELEASE,
    TRIGGER_CONDITION, CARGO_CONDITION, require, tile,
)
from tools.overworld.devtools_pokemon_combat_measurement import PokemonCombatMeasurement
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.devtools_profile_feature_measurement import application_index

KINDS = ("follower-throw-target-above-v1", "follower-throw-target-below-v1")
CASES = {
    KINDS[0]: dict(id="follower.throw-target-above", sign=1, trigger=70, cargo=179,
                  player=(554,398,3), target=(550,398), cargoTile=(555,399)),
    KINDS[1]: dict(id="follower.throw-target-below", sign=-1, trigger=70, cargo=179,
                  player=(560,392,0), target=(560,396), cargoTile=(561,391)),
}
LIMIT = 1000
ABOVE_IDLE = 1 << application_index("apply-idle")
ABOVE_ATTACK = 1 << application_index("apply-ambush")


def crossed_contact(old_cargo,old_target,cargo,target,landing):
    """Check the observed swept body against the unchanged native contact box."""
    enter,leave=Fraction(0),Fraction(1)
    for axis,lower,upper in ((0,-512,512),(1,-512,512),(2,-256,1280)):
        start=(old_cargo[axis]-old_target[axis])>>6
        end=(cargo[axis]-target[axis])>>6
        if not (-32768<=start<=32768 and -32768<=end<=32768):return False
        if landing:
            delta=(end-start)*1023
            end=start+(abs(delta)//1024 if delta>=0 else -(abs(delta)//1024))
        delta=end-start
        if not delta:
            if not lower<=start<=upper:return False
            continue
        a,b=sorted((Fraction(lower-start,delta),Fraction(upper-start,delta)))
        enter=max(enter,a);leave=min(leave,b)
    return enter<=leave and not (landing and old_cargo==cargo and old_target==target)


def requirement(kind):
    require(kind in CASES, "unknown signed-height Throw kind")
    return "current." + CASES[kind]["id"].replace(".", "-", 1)


def subjects(kind):
    c = CASES[kind]
    return (("mankey",56,"FOLLOWER","existing"),
            ("trigger",c["trigger"],"WILD","spawn"), ("cargo",c["cargo"],"WILD","spawn"))


def setup(kind):
    c=CASES[kind];x,z,facing=c["player"];tx,tz=c["target"];cx,cz=c["cargoTile"]
    rows=(("throw-tile","teleport",dict(map=67,x=x,z=z,facing=facing)),
        ("prepare-mankey","party",dict(slot=0,species=56,level=20)),
        ("create-follower","spawn",dict(species=56,form=0,role="follower",slot=0,level=20)),
        ("bind-mankey","bind",dict(subject="mankey")),
        ("spawn-trigger","spawn",dict(species=c["trigger"],form=0,role="wild",level=20,x=tx,z=tz)),
        ("bind-trigger","bind",dict(subject="trigger")),
        ("settle-trigger","step",dict(frames=64,keys=[])),
        ("notice-trigger","step",dict(frames=12,keys=[])),
        ("spawn-cargo","spawn",dict(species=c["cargo"],form=0,role="wild",level=20,x=cx,z=cz)),
        ("bind-cargo","bind",dict(subject="cargo")))
    if kind==KINDS[1]:
        # The completed native follower is already high before target creation.
        rows=rows[:3]+(("settle-follower","step",dict(frames=16,keys=[])),)+rows[3:6]+rows[7:]
    return rows


def actions(kind):
    return (("natural-signed-throw","step",dict(frames=600,keys=[],
        until=dict(kind="measurement-stage",measurement=kind,stage="launched",when="final"))),
        ("finish-signed-flight-and-vision","step",dict(frames=400,keys=[],
        until=dict(kind="measurement-complete",measurement=kind,when="final"))))


def validate_recipe(test):
    kind=test["measurements"][0]["kind"]
    require(kind in CASES and test["id"]==CASES[kind]["id"] and test["mode"]=="prepared"
        and test["requirements"]==[requirement(kind)]
        and test["subjects"]==[dict(id=n,species=s,role=r,acquire=a) for n,s,r,a in subjects(kind)]
        and test["measurements"]==[dict(kind=kind,subject="mankey")]
        and tuple((a["id"],a["op"],a["args"]) for a in test["setup"])==setup(kind)
        and tuple((a["id"],a["op"],a["args"]) for a in test["actions"])==actions(kind)
        and test["assertions"]==[dict(kind="measurement-complete",measurement=kind,when="final")]
        and test["budgets"]["maxFrames"]==1400 and test["budgets"]["minObservedFrames"]==2,
        "signed-height Throw fixed fixture or bounded normal input differs")


class CrossHeightThrowMeasurement:
    _actor = FollowerThrowMeasurement._actor
    _carrier = FollowerThrowMeasurement._carrier
    _events = FollowerThrowMeasurement._events
    _hp = PokemonCombatMeasurement._hp
    _pose = staticmethod(PokemonCombatMeasurement._pose)

    def __init__(self, source, kind):
        require(kind in CASES and source.get("contractVersion")==1
            and all(isinstance(source.get(n),str) and len(source[n])==64
                    for n in ("romSha256","overlaySha256","profileSha256")),
            "signed-height Throw source identity is missing")
        self.source=source;self.kind=kind;self.case=CASES[kind]
        self.subjects={};self.latest=None;self.failures=[];self.frames={};self.witness={}
        self.setup_index=self.setup_frames=self.observed_frames=self.action_frames=self.action_index=0
        self.was_bound=False;self.windup=None;self.flight=None;self.prior_hp=None
        self.flight_moved=False;self.flight_commit=None;self.cargo_completed=False;self.contact=None;self.prior_pose=None;self.prepared_cargo=None
        self.above_fixture=None;self.below_fixture=None;self.below_target=None

    def _boundary(self,sample,fixture=True):
        require(sample.get("fieldAvailable") is True and sample.get("observationBoundary")==BOUNDARY
            and sample.get("romSha256")==self.source["romSha256"]
            and type(sample.get("frame")) is int and type(sample.get("nativeCycle")) is int
            and sample.get("fieldControl",{}).get("taskPointer")==0
            and (not fixture or sample.get("context",{}).get("mapId")==67),
            "signed-height Throw lacks current field control or entered battle")
        if fixture:
            require((sample["player"]["x"],sample["player"]["y"])==self.case["player"][:2],
                    "signed-height Throw moved its prepared player")

    def _base_y(self,actor):
        value=actor.get("engineObject",{}).get("pos_y")
        require(type(value) is int, "signed-height Throw lacks native position Y")
        return value

    def _above_carrier(self,sample,m):
        require(tile(m,"engineObject")== (555,398) and self._base_y(m)==65536
            and m["engineObject"].get("facing")==2 and m["motionPhase"]=="IDLE"
            and m["reservationId"]==0 and sample["player"].get("pos_y")==65536
            and sample["player"].get("facing")==3,
            "signed-height Above lacks its settled ground West-facing carrier")

    def _above_support(self,sample,t):
        """A finalized native actor and a current loaded Pot must agree."""
        terrain=sample.get("terrain",{});obs=terrain.get("observation",{})
        cells=[c for c in terrain.get("cells",[]) if (c.get("x"),c.get("z"))==self.case["target"]]
        require(len(cells)==1 and obs.get("nativeCycle")==sample["nativeCycle"]
            and obs.get("lastCompletedGameFrame")==sample["frame"]
            and obs.get("context")==sample["context"],
            "signed-height Above lacks current native Pot terrain")
        # The declared East approach must not repeat the blocked North ray.
        # These are current native reads, not requested-position credit.
        for xy in tuple((x,398) for x in range(551,556))+(self.case["cargoTile"],):
            ray=[c for c in terrain.get("cells",[]) if (c.get("x"),c.get("z"))==xy]
            require(len(ray)==1 and ray[0].get("loaded") is True
                and ray[0].get("collision") is False
                and ray[0].get("surface",{}).get("known") is True
                and ray[0]["surface"].get("present") is False
                and ray[0].get("provenance",{}).get("chunkModelLoaded")==1
                and ray[0]["provenance"].get("mapHeaderId")==67
                and ray[0]["provenance"].get("chunkMatrixIndex")
                    ==ray[0]["provenance"].get("currentMatrixIndex")==581,
                "signed-height Above lacks its current clear East ray or Cargo site")
        pot=cells[0];surface=pot.get("surface",{});native=pot.get("provenance",{})
        require(pot.get("loaded") is True and pot.get("collision") is True
            and native.get("chunkModelLoaded")==1 and native.get("mapHeaderId")==67
            and native.get("chunkMatrixIndex")==native.get("currentMatrixIndex")==581
            and surface.get("known") is True and surface.get("present") is True
            and surface.get("finalHeightKnown") is True and surface.get("heightMode")=="absolute"
            and surface.get("type")=="flowerbed" and surface.get("surfaceId")==9304
            and surface.get("modelIndex")==5 and surface.get("instanceIndex")==130
            and surface.get("anchorMatrixIndex")==581 and surface.get("heightFx32")==122880
            and tile(t,"engineObject")==self.case["target"] and self._base_y(t)==122880
            and t["motionPhase"]=="IDLE" and t["reservationId"]==0,
            "signed-height Above finalized actor is not on its actual elevated Pot")
        require(t.get("matchedLayerMask",0)&ABOVE_IDLE
            and not t.get("matchedLayerMask",0)&ABOVE_ATTACK,
            "signed-height Above admitted Player Notice or Ambush")
        return dict(frame=sample["frame"],nativeCycle=sample["nativeCycle"],
            trigger=deepcopy(t["handle"]),physicalY=self._base_y(t),pot=deepcopy(pot))

    def _below_carrier(self,sample,m):
        """Normal native follower release, before any prepared Trigger exists."""
        require(tile(m,"engineObject")== (560,391) and self._base_y(m)==267648
            and m["engineObject"].get("facing")==1 and m["motionPhase"]=="IDLE"
            and m["reservationId"]==0 and sample["player"].get("pos_y")==65536
            and sample["player"].get("facing")==0,
            "signed-height Below lacks its settled native high South-facing carrier")
        row,_=self._carrier(sample,m)
        require(not row["bindings"]["trigger"]["bound"] and not row["bindings"]["cargo"]["bound"]
            and not any(row["throw"][n] for n in ("carrier","carried","windup","recovering")),
            "signed-height Below high start already has a binding or Throw owner")
        self._below_support(sample,(560,391),True)
        return dict(frame=sample["frame"],nativeCycle=sample["nativeCycle"],carrier=deepcopy(m["handle"]),
            physicalY=self._base_y(m))

    def _below_support(self,sample,xy,high):
        terrain=sample.get("terrain",{});obs=terrain.get("observation",{})
        cells=[c for c in terrain.get("cells",[]) if (c.get("x"),c.get("z"))==xy]
        require(len(cells)==1 and obs.get("nativeCycle")==sample["nativeCycle"]
            and obs.get("lastCompletedGameFrame")==sample["frame"] and obs.get("context")==sample["context"],
            "signed-height Below lacks current native support")
        cell=cells[0];surface=cell.get("surface",{});native=cell.get("provenance",{})
        require(cell.get("loaded") is True and surface.get("known") is True
            and native.get("chunkModelLoaded")==1 and native.get("mapHeaderId")==67
            and native.get("chunkMatrixIndex")==native.get("currentMatrixIndex")==581,
            "signed-height Below support is unknown or stale")
        if high:
            require(cell.get("collision") is True and surface.get("present") is True
                and surface.get("type")=="canopy" and surface.get("surfaceId")==65534
                and surface.get("modelIndex")==5 and surface.get("instanceIndex")==117
                and surface.get("heightMode")=="native-ground-offset"
                and surface.get("heightOffsetFx32")==202112,
                "signed-height Below lacks its actual high Canopy support")
        else:
            require(cell.get("collision") is False and surface.get("present") is False,
                "signed-height Below lacks its clear native ground ray")

    def _below_trigger(self,sample,t):
        require(self.below_fixture is not None and self.below_fixture["frame"]<=sample["frame"]
            and tile(t,"engineObject")==self.case["target"] and self._base_y(t)==65536
            and t["motionPhase"]=="IDLE" and t["reservationId"]==0
            and t.get("matchedLayerMask",0)&ABOVE_IDLE and not t.get("matchedLayerMask",0)&ABOVE_ATTACK,
            "signed-height Below lacks its current passive lower Trigger")
        for xy in tuple((560,y) for y in range(392,397)):
            self._below_support(sample,xy,False)
        return dict(frame=sample["frame"],trigger=deepcopy(t["handle"]),physicalY=self._base_y(t))

    def _probe(self,sample):
        """Current authored capture is the Vision witness, not placed geometry."""
        if not {"mankey","trigger"}<=self.subjects.keys():return
        m=self._actor(sample,"mankey");t=self._actor(sample,"trigger")
        if self.kind==KINDS[0] and self.flight is None:
            require(tile(t,"engineObject")==self.case["target"]
                and t.get("matchedLayerMask",0)&ABOVE_IDLE
                and not t.get("matchedLayerMask",0)&ABOVE_ATTACK,
                "signed-height Above target left its Pot or admitted Player Notice/Ambush")
        if self.kind==KINDS[1] and self.flight is None:
            require(self.below_target is not None and self.below_target["trigger"]==t["handle"]
                and tile(t,"engineObject")==self.case["target"]
                and t.get("matchedLayerMask",0)&ABOVE_IDLE and not t.get("matchedLayerMask",0)&ABOVE_ATTACK,
                "signed-height Below target left its native ground or admitted Player Notice/Ambush")
        row,_=self._carrier(sample,m);bound=row["bindings"]["trigger"]
        current=bound["bound"]
        if current:
            require(bound["targetCurrent"] is True and bound["target"]["kind"]=="ACTOR"
                and bound["target"]["actor"]==t["handle"]
                and bound["sourceConditionId"]==TRIGGER_CONDITION and bound["sourceApplication"]==20,
                "signed-height Throw lost its full current authored Trigger")
            if not self.was_bound:
                my=self._base_y(m);ty=self._base_y(t)
                if (ty-my)*self.case["sign"]>0 and self.flight is None:
                    if self.kind==KINDS[0] and "vision" not in self.frames:
                        require(self.above_fixture is not None and self.above_fixture["trigger"]==t["handle"],
                                "signed-height Above lacks its finalized native Pot witness")
                        self._above_carrier(sample,m)
                        require(tile(t,"engineObject")==self.case["target"] and ty==122880
                            and 0<m["engineObject"]["x"]-t["engineObject"]["x"]<=5
                            and t["engineObject"]["y"]==m["engineObject"]["y"],
                            "signed-height Above capture is not the current West Vision line")
                    if self.kind==KINDS[1]:
                        require(self.below_fixture is not None and self.below_fixture["carrier"]==m["handle"]
                            and self.below_fixture["frame"]<=sample["frame"]
                            and tile(m,"engineObject")== (560,391) and my==267648
                            and m["engineObject"].get("facing")==1 and m["motionPhase"]=="IDLE"
                            and m["reservationId"]==0 and tile(t,"engineObject")== (560,396),
                            "signed-height Below capture preceded its actual high settled owner")
                    self.frames.setdefault("vision",sample["frame"])
                    self.witness.setdefault("vision",dict(frame=sample["frame"],nativeCycle=sample["nativeCycle"],
                        carrier=deepcopy(m["handle"]),trigger=deepcopy(t["handle"]),carrierY=my,targetY=ty,
                        conditionId=bound["sourceConditionId"],application=bound["sourceApplication"]))
        self.was_bound=current

    def _sample(self,sample,events):
        self._boundary(sample)
        require(self.latest is None or sample["frame"]==self.latest["frame"]+1,
                "signed-height Throw completed stream has a gap")
        self._probe(sample)
        a={n:self._actor(sample,n) for n,_,_,_ in subjects(self.kind)}
        m,t,c=(a[n] for n in ("mankey","trigger","cargo"))
        require(len({(x["handle"]["slot"],x["handle"]["generation"]) for x in a.values()})==3
            and m.get("matchedLayerMask",0)&FOLLOWER, "signed-height Throw subjects or Follower role differ")
        row,_=self._carrier(sample,m);state=row["throw"];frame=sample["frame"]
        hp=self._hp(sample,"trigger");cargo_hp=self._hp(sample,"cargo")
        native=self._events(events,c)
        if self.prior_hp is None:
            require(hp["hp"]==hp["maxHp"] and hp["hitCount"]==0,
                    "signed-height Trigger was damaged before the measured Throw")
        if state["carrier"]:
            b=row["bindings"]["cargo"]
            require(b["bound"] and b["targetCurrent"] is True and b["target"]["kind"]=="ACTOR"
                and b["target"]["actor"]==c["handle"] and b["sourceConditionId"]==CARGO_CONDITION
                and b["sourceApplication"]==20 and state["targetSlot"]==c["handle"]["slot"],
                "signed-height Throw Cargo claim differs")
            self.frames.setdefault("claim",frame)
        if state["carried"]:
            self.frames.setdefault("pickup",frame)
        if state["windup"]:
            require(state["carried"] and m["matchedLayerMask"]&RELEASE,
                    "signed-height Throw windup lacks current held release")
            ty=self._base_y(t);my=self._base_y(m)
            if self.windup is None:
                require((ty-my)*self.case["sign"]>0, "signed-height Throw windup has wrong physical height sign")
                if self.kind==KINDS[0]:
                    require(ty==self.above_fixture["physicalY"],
                            "signed-height Above windup changed its current native Pot height")
                self.windup=dict(frame=frame,nativeCycle=sample["nativeCycle"],target=list(tile(t,"engineObject")),
                    physicalY=ty,carrierY=my,trigger=deepcopy(t["handle"]),cargo=deepcopy(c["handle"]))
                self.frames["windup"]=frame
            require(ty==self.windup["physicalY"], "signed-height Throw target Y changed during windup")
        starts=[e for e in native if e.get("event")=="MOTION_STARTED" and e.get("valueA")==2]
        if self.flight is None and state["recovering"] and c["motionKind"]=="HOP":
            require(starts, "signed-height Throw has no native START receipt")
        if self.flight is None and starts and state["recovering"] and not state["carrier"]:
            require(self.windup is not None and "pickup" in self.frames,
                    "signed-height Throw has no real pickup and windup")
            motion=cargo_hp["motion"]
            require(motion==decode_motion(bytes.fromhex(motion.get("rawHex",""))),
                    "signed-height Throw motion bytes differ")
            p=motion["plan"]
            require(len(starts)==1 and starts[0].get("reason")=="OK" and motion["phase"]=="MOVING"
                and p["kind"]==2 and p["fieldEpoch"]==c["handle"]["fieldEpoch"]
                and p["reservationId"]>0 and p["origin"]==list(tile(c,"origin"))
                and p["target"]==list(tile(c,"target"))==self.windup["target"]
                and p["targetBaseY"]==self.windup["physicalY"]
                and (p["targetBaseY"]-p["startBaseY"])*self.case["sign"]>0,
                "signed-height Throw flight flattened or changed the latched physical aim")
            require(not row["bindings"]["trigger"]["bound"] and not row["bindings"]["cargo"]["bound"],
                    "signed-height Throw did not clear launch bindings")
            self.flight=dict(frame=frame,nativeCycle=sample["nativeCycle"],plan=deepcopy(p),
                cargo=deepcopy(c["handle"]),launchPose=self._pose(c,sample),commitSequence=c["commitSequence"])
            self.frames["launch"]=frame
        if self.flight is not None and not self.cargo_completed:
            motion=cargo_hp["motion"]
            require(motion==decode_motion(bytes.fromhex(motion.get("rawHex",""))),
                    "signed-height Throw motion bytes differ")
            terminal={name:[e for e in native if e.get("event")==name]
                for name in ("LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED")}
            clock=sample.get("actorFrame")
            require(type(clock) is int and all(type(e.get("frame")) is int
                and type(e.get("actorFrame")) is int and e["frame"]==e["actorFrame"]==clock
                for e in native),
                "signed-height Throw terminal receipt is not the current Actor clock")
            committed=terminal["LOGICAL_COMMIT"]
            if committed:
                require(len(committed)==1 and self.flight_commit is None
                    and motion["plan"]==self.flight["plan"]
                    and committed[0].get("reason")=="OK"
                    and committed[0].get("valueA")==self.flight["commitSequence"]+1
                    and committed[0].get("valueB")==2
                    and c["commitSequence"]==self.flight["commitSequence"]+1
                    and tile(c)==tuple(self.flight["plan"]["target"])
                    and c["motionPhase"] in ("SETTLING","IDLE") and c["reservationId"]==0
                    and self._base_y(c)==self.flight["plan"]["targetBaseY"],
                    "signed-height Throw lacks its native terminal commit")
                self.flight_commit=dict(frame=frame,nativeCycle=sample["nativeCycle"],
                    sequence=committed[0]["sequence"],commitSequence=c["commitSequence"],
                    cargo=deepcopy(c["handle"]),physicalY=self._base_y(c))
                self.frames["commit"]=frame
            finished,returned=terminal["MOTION_FINISHED"],terminal["CONTROL_RETURNED"]
            if finished or returned:
                require(self.flight_commit is not None,
                        "signed-height Throw lacks its native terminal commit")
                require(len(finished)==len(returned)==1 and finished[0].get("reason")==returned[0].get("reason")=="OK"
                    and self.flight_commit["sequence"]<finished[0]["sequence"]<returned[0]["sequence"]
                    and finished[0].get("valueA")==self.flight_commit["commitSequence"]
                    and finished[0].get("valueB")==2 and returned[0].get("valueA")==0
                    and returned[0].get("valueB")==self.flight_commit["commitSequence"]
                    and c["commitSequence"]==self.flight_commit["commitSequence"],
                    "signed-height Throw lacks ordered native terminal finish and control return")
                later=[e for e in native if e.get("event")=="MOTION_STARTED"]
                if motion["plan"]!=self.flight["plan"] or c["reservationId"]!=0 or c["motionPhase"]!="IDLE":
                    require(len(later)==1 and later[0].get("reason")=="OK"
                        and later[0]["sequence"]>returned[0]["sequence"]
                        and later[0].get("valueA")==motion["plan"]["kind"]
                        and later[0].get("valueB")==motion["plan"]["duration"]
                        and motion["phase"]=="MOVING" and c["motionPhase"]=="MOVING"
                        and c["reservationId"]==motion["plan"]["reservationId"]>0
                        and motion["plan"]["fieldEpoch"]==c["handle"]["fieldEpoch"]
                        and motion["plan"]["origin"]==self.flight["plan"]["target"]==list(tile(c,"origin"))
                        and motion["plan"]["target"]==list(tile(c,"target"))
                        and motion["plan"]["startBaseY"]==self.flight["plan"]["targetBaseY"]
                        and c["motionKind"]=={1:"WALK",2:"HOP",3:"TELEPORT",4:"SKID",5:"REPOSITION",6:"FLY_IN"}.get(motion["plan"]["kind"]),
                        "signed-height Throw subsequent motion preceded exact control return")
                else:
                    require(tile(c)==tuple(self.flight["plan"]["target"])
                        and self._base_y(c)==self.flight["plan"]["targetBaseY"],
                        "signed-height Throw terminal pose differs")
                self.cargo_completed=True;self.frames["terminal"]=frame
            else:
                require(motion["plan"]==self.flight["plan"],
                        "signed-height Throw replaced its immutable flight")
                if self.flight_commit is None:
                    require(c["commitSequence"]==self.flight["commitSequence"]
                        and c["reservationId"]==self.flight["plan"]["reservationId"],
                        "signed-height Throw lacks its native terminal commit or flight reservation")
                else:
                    require(c["commitSequence"]==self.flight_commit["commitSequence"]
                        and c["reservationId"]==0 and c["motionPhase"]=="SETTLING"
                        and tile(c)==tuple(self.flight["plan"]["target"])
                        and self._base_y(c)==self.flight["plan"]["targetBaseY"],
                        "signed-height Throw changed its committed settling owner")
            self.flight_moved |= self._pose(c,sample)!=self.flight["launchPose"]
        if self.prior_hp is not None and hp["hitCount"]!=self.prior_hp["hitCount"]:
            delta=self.prior_hp["hp"]-hp["hp"]
            require(self.flight is not None and self.contact is None and delta>0
                and hp["hitCount"]==self.prior_hp["hitCount"]+1 and delta==hp["lastDamage"]
                and hp["immunityFrames"]>=59 and frame<=self.frames.get("terminal",frame)
                and self.prior_pose is not None
                and crossed_contact(*self.prior_pose,self._pose(c,sample),self._pose(t,sample),self.cargo_completed),
                "signed-height Throw lacks a real current flight contact")
            self.contact=dict(frame=frame,nativeCycle=sample["nativeCycle"],trigger=deepcopy(t["handle"]),
                cargo=deepcopy(c["handle"]),before=self.prior_hp["hp"],after=hp["hp"],damage=delta,
                hitCount=hp["hitCount"],triggerPose=self._pose(t,sample),cargoPose=self._pose(c,sample))
            self.frames["contact"]=frame
        self.prior_hp=deepcopy(hp);self.prior_pose=(self._pose(c,sample),self._pose(t,sample));self.latest=deepcopy(sample);self.observed_frames+=1

    def observe_record(self,row,on_sample=None):
        try:
            seq=setup(self.kind)
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase")=="setup", "signed-height initial boundary differs")
                self._boundary(row["initialSnapshot"],False);self.latest=deepcopy(row["initialSnapshot"])
                return self.result()
            if row.get("phase")=="setup":
                require(self.setup_index<len(seq) and row.get("action")==seq[self.setup_index][0], "signed-height setup order differs")
                _,op,args=seq[self.setup_index]
                if op=="step":
                    require("command" not in row, "signed-height setup must use normal frames")
                    for sample,events,_ in validate_raw_chunk(row,self.latest):
                        self._boundary(sample);self._probe(sample);self.latest=deepcopy(sample)
                        if on_sample:on_sample(sample,self.observed_frames)
                    self.setup_frames+=row["completedGameFrames"]
                    require(self.setup_frames<=args["frames"], "signed-height setup frame bound differs")
                    if self.setup_frames<args["frames"]:return self.result()
                    self.setup_frames=0
                else:
                    require(row.get("command")==op, "signed-height setup command differs")
                    sample=row["snapshot"];self._boundary(sample)
                    if row["action"]=="spawn-cargo" and self.case["cargo"]==70:
                        value=row["receipt"].get("value",{})
                        prepared=[e["data"] for e in row["receipt"].get("events",[]) if e.get("kind")=="native-observation"
                            and e.get("data",{}).get("observation")=="spawn-prepared"
                            and e["data"].get("slot")==value.get("slot")
                            and e["data"].get("preparedEncounter",{}).get("personality")==value.get("personality")]
                        require(len(prepared)==1 and prepared[0]["startup"]["target"]==list(self.case["cargoTile"])
                            and prepared[0]["startup"]["origin"]==list(self.case["cargoTile"])
                            and prepared[0]["startup"]["locomotion"]==0,
                            "signed-height Cargo lacks its exact native passive Canopy startup")
                        self.prepared_cargo=dict(slot=value["slot"],personality=value["personality"])
                    if row["action"]=="spawn-trigger":
                        encounter=row["receipt"].get("value",{})
                        candidates=[a for a in sample["actors"] if a.get("species")==self.case["trigger"]
                            and a.get("role")=="WILD" and a.get("handle",{}).get("slot")==encounter.get("slot")
                            and a.get("subjectIdentity")==encounter.get("personality")]
                        require(len(candidates)==1, "signed-height prepared Trigger lacks exact encounter identity")
                        self.subjects["trigger"]=select_current_actor(sample,candidates[0])
                        if self.kind==KINDS[1]:
                            from tools.overworld.devtools_test_contract import _wild_spawn_setup
                            prepared=_wild_spawn_setup(row["receipt"],sample,species=70,locomotion=0)
                            require(prepared["destination"]==list(self.case["target"]),
                                "signed-height Below passive Trigger startup changed its native ground")
                            self.below_target=self._below_trigger(sample,candidates[0])
                        if self.kind==KINDS[0]:
                            from tools.overworld.devtools_test_contract import _wild_spawn_setup
                            prepared=_wild_spawn_setup(row["receipt"],sample,species=70,locomotion=0)
                            require(prepared["destination"]==list(self.case["target"]),
                                    "signed-height Above passive startup changed its requested Pot")
                            self.above_fixture=self._above_support(sample,candidates[0])
                    if row["action"]=="spawn-cargo" and self.kind==KINDS[1]:
                        from tools.overworld.devtools_test_contract import _wild_spawn_setup
                        prepared=_wild_spawn_setup(row["receipt"],sample,species=179,locomotion=7)
                        require(prepared["destination"]==list(self.case["cargoTile"]),
                            "signed-height Below Cargo startup changed its native Canopy site")
                        self.prepared_cargo=dict(slot=prepared["subject"]["handle"]["slot"],
                            personality=prepared["subject"]["subjectIdentity"])
                    if op=="bind":
                        name=args["subject"];selected=select_current_actor(sample,row["receipt"])
                        expected=next(s for s in subjects(self.kind) if s[0]==name)
                        require((selected["species"],selected["role"])==expected[1:3], "signed-height bound species or role differs")
                        if name=="trigger" and name in self.subjects:
                            require(self.subjects[name]["handle"]==selected["handle"] and self.subjects[name]["subjectIdentity"]==selected["subjectIdentity"],
                                    "signed-height prepared Trigger changed before its explicit bind")
                        self.subjects[name]=deepcopy(row["receipt"])
                        if name=="mankey" and self.kind==KINDS[0]:
                            self._above_carrier(sample,self._actor(sample,name))
                        elif name=="mankey" and self.kind==KINDS[1]:
                            self.below_fixture=self._below_carrier(sample,self._actor(sample,name))
                        if name in ("trigger","cargo"):
                            expected_tile=self.case["target"] if name=="trigger" else self.case["cargoTile"]
                            if name=="cargo" and self.case["cargo"]==70:
                                require(self.prepared_cargo==dict(slot=selected["handle"]["slot"],personality=selected["subjectIdentity"]),
                                        "signed-height Cargo startup changed identity before bind")
                                require(tile(self._actor(sample,name),"engineObject")==expected_tile,
                                        "signed-height finalized native placement differs")
                            else:
                                actor=self._actor(sample,name)
                                require(tile(actor,"engineObject")==expected_tile,
                                        "signed-height finalized native placement differs")
                                if name=="cargo" and self.kind==KINDS[1]:
                                    require(self.prepared_cargo==dict(slot=selected["handle"]["slot"],personality=selected["subjectIdentity"])
                                        and self._base_y(actor)==267648 and actor["motionPhase"]=="IDLE"
                                        and actor["reservationId"]==0,
                                        "signed-height Below Cargo is not its full current settled high encounter")
                                    self._below_support(sample,expected_tile,True)
                    self._probe(sample);self.latest=deepcopy(sample)
                self.setup_index+=1;return self.result()
            require(self.setup_index==len(seq) and row.get("phase")=="observe"
                and self.action_index<len(actions(self.kind))
                and row.get("action")==actions(self.kind)[self.action_index][0] and "command" not in row,
                "signed-height natural action order differs")
            for sample,events,_ in validate_raw_chunk(row,self.latest):
                self.action_frames+=1;require(self.action_frames<=actions(self.kind)[self.action_index][2]["frames"], "signed-height natural frame bound exceeded")
                self._sample(sample,events)
                if on_sample:on_sample(sample,self.observed_frames)
            if (self.action_index==0 and "launch" in self.frames) or (self.action_index==1 and self.result()["ready"]):
                self.action_index+=1;self.action_frames=0
        except (ValueError,KeyError,TypeError,StopIteration,struct.error) as error:self.failures.append(str(error))
        return self.result()

    def stage(self,name):
        require(name=="launched", "unknown signed-height stage")
        return not self.failures and "launch" in self.frames

    def result(self):
        ready=not self.failures and "vision" in self.frames and self.cargo_completed and self.flight_moved and self.contact is not None
        if self.kind==KINDS[0]:ready=ready and self.above_fixture is not None
        else:ready=ready and self.below_fixture is not None and self.below_target is not None
        if ready:ready=self.frames["vision"]<=self.frames["claim"]
        return dict(kind=self.kind,requirements=[requirement(self.kind)],ready=ready,passed=ready,acceptedProof=False,
            observedFrames=self.observed_frames,observedFrameUnit="completed-game-frame",subjects=deepcopy(self.subjects),
            frames=deepcopy(self.frames),visionWitness=deepcopy(self.witness.get("vision")),windup=deepcopy(self.windup),
            flight=deepcopy(self.flight),flightCommit=deepcopy(self.flight_commit),flightMoved=self.flight_moved,cargoCompleted=self.cargo_completed,
            contact=deepcopy(self.contact),failures=list(self.failures),
            **(dict(aboveFixture=deepcopy(self.above_fixture)) if self.kind==KINDS[0]
               else dict(belowFixture=deepcopy(self.below_fixture),belowTarget=deepcopy(self.below_target))))

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("signed-height Throw ended without current Vision, flight terminal, movement and contact")
        return self.result()
