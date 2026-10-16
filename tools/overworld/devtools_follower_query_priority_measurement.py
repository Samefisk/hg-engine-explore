"""A current saved follower takes an unclaimed Wild query, then throws normally.

Only existing sealed query, interaction, profile and native motion observations
are consumed. Setup never grants a route, claim, pickup or movement receipt.
"""
from copy import deepcopy
import struct

from tools.overworld.devtools_damage_follower_measurement import DamageFollowerMeasurement
from tools.overworld.devtools_follower_throw_measurement import (
    APPLICATION, FIND_CARGO, FOLLOWER, SEARCH_TIME, THROW_MASK, TRIGGER_CONDITION,
    CARGO_CONDITION, require, raw_handle, tile,
)
from tools.overworld.devtools_follower_throw_approach_measurement import reachable_cargo_admission
from tools.overworld.devtools_cargo_route_continuity import packets, profile
from tools.overworld.devtools_movement_predicates import normal_input_at_edge
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor

KIND = "follower-throw-query-priority-v1"
REQUIREMENT = "current.follower-throw-query-priority"
CASE = "follower.throw-query-priority"
SUBJECTS = (("mankey",56,"FOLLOWER","existing"),
            ("old-geodude",74,"WILD","spawn"),("source",74,"WILD","spawn"))
SETUP = (("saved-route-approach","step",dict(frames=160,keys=["RIGHT"])),
         ("settle-route-approach","step",dict(frames=40,keys=[])),
         ("throw-tile","teleport",dict(map=33,x=586,z=407,facing=1)),
         ("settle-saved-follower","step",dict(frames=20,keys=[])),
         ("bind-mankey","bind",dict(subject="mankey")),
         ("spawn-old-geodude","spawn",dict(species=74,form=0,role="wild",level=5,x=587,z=408)),
         ("bind-old-geodude","bind",dict(subject="old-geodude")),
         ("first-natural-throw","step",dict(frames=180,keys=[])),
         ("spawn-occluded-geodude","spawn",dict(species=74,form=0,role="wild",level=5,x=589,z=408)),
         ("settle-occluded-geodude","step",dict(frames=220,keys=[])),
         ("face-clear-target","step",dict(frames=16,keys=["RIGHT"])),
         ("settle-clear-target","step",dict(frames=100,keys=[])),
         ("spawn-source","spawn",dict(species=74,form=0,role="wild",level=5,x=587,z=404)),
         ("bind-source","bind",dict(subject="source")))

def stage_args(frames,keys,stage):
    return dict(frames=frames,keys=keys,until=dict(kind="measurement-stage",measurement=KIND,stage=stage,when="final"))

ACTIONS = (("second-natural-throw","step",stage_args(300,[],"landed")),
           ("move-player-right","step",dict(frames=32,keys=["RIGHT"])),
           ("normal-follow-return","step",stage_args(240,[],"resumed")))

def validate_recipe(test):
    require(test["id"]==CASE and test["mode"]=="prepared"
        and test["requirements"]==[REQUIREMENT]
        and test["subjects"]==[dict(id=n,species=s,role=r,acquire=a) for n,s,r,a in SUBJECTS]
        and test["measurements"]==[dict(kind=KIND,subject="mankey")]
        and tuple((r["id"],r["op"],r["args"]) for r in test["setup"])==SETUP
        and tuple((r["id"],r["op"],r["args"]) for r in test["actions"])==ACTIONS
        and test["assertions"]==[dict(kind="measurement-complete",measurement=KIND,when="final")]
        and test["budgets"]["maxFrames"]==1500 and test["budgets"]["minObservedFrames"]==2,
        "Follower priority fixture differs from unchanged Continue and normal input")


class FollowerQueryPriorityMeasurement(DamageFollowerMeasurement):
    def __init__(self,source):
        super().__init__(source)
        require(source["contractVersion"]==2,"Follower priority needs the sealed current query image")
        self.action_frames=[0]*len(ACTIONS)
        self.setup_action_frames=[0]*len(SETUP)
        self.busy_owner=self.handoff=self.admission=None
        self.search_move=self.cargo_move=None
        self.search_returns=[]
        self.source_capture=None

    def _old_lease(self,sample):
        old=self._actor(sample,"old-geodude")
        m=self._actor(sample,"mankey");_,state=self._carrier(sample,m)
        rows=[r for r in sample["pokemonCombat"]["interactions"]["carriers"] if r["handle"]==old["handle"]]
        require(len(rows)==1 and rows[0].get("available") is True and rows[0].get("role")=="WILD",
                "Follower priority old owner is not a current Wild")
        row=rows[0];raw=bytes.fromhex(row["rawBindingsHex"])
        require(len(raw)==60 and raw[:12]==raw_handle(old["handle"])
            and raw[12:36].hex()==row["bindings"]["trigger"]["rawHex"]
            and raw[36:60].hex()==row["bindings"]["cargo"]["rawHex"],
            "Follower priority old binding owner differs")
        slot=old["handle"]["slot"]
        require(row["bindings"]["trigger"]["bound"] is True and raw[34]==1
            and row["bindings"]["trigger"]["targetCurrent"] is True
            and row["bindings"]["cargo"]["bound"] is False and raw[58]==0
            and state["targets"][slot]==0
            and not (state["targetMask"]|state["carrierMask"])&(1<<slot)
            and old["motionPhase"]=="IDLE" and old["reservationId"]==0,
            "Follower priority old owner already owns Cargo or movement")
        return old,row

    def _remember_busy(self,sample,events):
        if "old-geodude" not in self.subjects:return
        old=self._actor(sample,"old-geodude")
        owned=[e for e in events if e.get("data",{}).get("after",{}).get("workspace",{}) is not None
            and e.get("data",{}).get("after",{}).get("workspace",{}).get("owner")==old["handle"]
            and e.get("data",{}).get("status")=="PENDING"]
        rows=packets(sample,owned,old,self.source["queryImage"],self.latest["nativeCycle"],pending_ok=True)
        for row in rows:
            if row["status"]!="PENDING" or tile(old)!=(595,407):continue
            # Native logical arrival can precede flight control return. That
            # setup sample is not the idle unclaimed owner needed for the stop.
            if old["motionPhase"]!="IDLE" or old["reservationId"]!=0:continue
            old,binding=self._old_lease(sample)
            require(row["workspace"]["owner"]==old["handle"]
                and row["workspace"]["compatibility"]["required"]==0,
                "Follower priority old query is not an unbound search")
            self.busy_owner=dict(frame=sample["frame"],actor=deepcopy(old),
                binding=deepcopy(binding),query=deepcopy(row))

    def _queries(self,sample,events,m):
        image=self.source["queryImage"];current=[]
        for event in events:
            d=event.get("data",{})
            if event.get("kind")!="native-observation" or d.get("observation")!="throw-cargo-query" \
                    or d.get("slot")!=m["handle"]["slot"]:continue
            raw=bytes.fromhex(d["resultHex"]);after=d["after"];q=after["workspace"]
            identity=d.get("imageIdentity",{})
            require(event.get("frame")==sample["frame"]
                and d.get("subject")==m["handle"]
                and d.get("entryActorFrame")==d.get("returnActorFrame")==sample["actorFrame"]
                and self.latest["nativeCycle"]<d.get("entryNativeCycle",0)<=d.get("returnNativeCycle",0)<=sample["nativeCycle"]
                and d.get("boundary")=="native-cargo-tick-return"
                and all(identity.get(k)==image[k] for k in ("elfSha256","packageSha256"))
                and type(identity.get("loadedEntry")) is int and identity["loadedEntry"]>0
                and type(identity.get("tickEntry")) is int and identity["tickEntry"]>identity["loadedEntry"]
                and len(bytes.fromhex(identity.get("loaderOwner","")))==28
                and len(raw)==140 and d.get("returnValue")==d.get("resultStatus")==raw[138]
                and after.get("subject")==after.get("worldSubject")==m["handle"]
                and after.get("frameValid") is True and after.get("worldFrame")==sample["actorFrame"]
                and type(d.get("sequence")) is int,
                "Follower priority native query identity or clock differs")
            require(struct.unpack_from("<H",raw,124)[0]<=16 and raw[127]+raw[128]<=1,
                    "Follower priority route work exceeded its existing budget")
            if self.handoff is None and q is not None and self.busy_owner is not None:
                before=d["before"]["workspace"];old=self.busy_owner["actor"]
                # Observe runs before the Notice entry captures its binding.
                # That capture queue may still contain the old Pending read.
                # It earns no route credit; the next current read must hand off.
                if q.get("owner")==old["handle"] and (self.binding is None or self.binding["frame"]==sample["frame"]):
                    require(raw[138]==0 and d.get("status")=="PENDING" and raw[105]==0
                        and raw[108:138]==bytes(30) and q.get("ownerCurrent") is True,
                        "Follower priority old Pending read granted eligibility")
                    continue
                require(q.get("owner")==m["handle"] and q.get("ownerCurrent") is True,
                        "Follower priority retained unrelated query owner")
                require(before is not None and before.get("owner")==old["handle"]
                    and before.get("ownerCurrent") is True and before.get("valid") is True
                    and q.get("valid") is True
                    and after["queryPointer"]==d["before"]["queryPointer"]==self.busy_owner["query"]["queryPointer"]
                    and q["storage"]==before["storage"],
                    "Follower priority handoff replaced storage or the old full owner")
                self._old_lease(sample)
                if before["stateFrame"]==sample["actorFrame"]:
                    require(raw[108:136]==bytes(28) and raw[138]==0 and raw[136:138]==bytes(2)
                        and raw[105]==0,"Follower priority handoff used a second same-frame native query")
                self.handoff=dict(frame=sample["frame"],before=deepcopy(d["before"]),after=deepcopy(after),resultHex=raw.hex())
                self.frames["handoff"]=sample["frame"]
            if q is not None and q.get("stateSubject")==m["handle"]:
                current.extend(packets(sample,[event],m,image,self.latest["nativeCycle"],pending_ok=True))
        return current

    def _binding(self,sample,carrier,source,launching=False):
        b=carrier["bindings"]["trigger"]
        if self.frames.get("followReturn")==sample["frame"]:return
        if b["bound"]:
            require(b["targetCurrent"] is True and b["flags"]==1 and b["lifetime"]==0
                and b["sourceConditionId"]==TRIGGER_CONDITION and b["sourceApplication"]==APPLICATION
                and b["target"]==dict(kind="ACTOR",actor=source["handle"]),
                "Follower priority Sight Interest differs from the second Geodude")
            require(self.busy_owner is not None,"Follower priority lacks the earlier busy Wild query")
            if self.binding is None:
                self.binding=dict(frame=sample["frame"],binding=deepcopy(b));self.frames["notice"]=sample["frame"]
        elif self.binding is not None and self.flight is None and not launching:
            raise ValueError("Follower priority lost Sight Interest before launch")
        cargo=carrier["bindings"]["cargo"]
        if cargo["bound"]:
            require(self.binding is not None and cargo["targetCurrent"] is True and cargo["flags"]==1
                and cargo["sourceConditionId"]==CARGO_CONDITION and cargo["sourceApplication"]==APPLICATION
                and cargo["target"]==dict(kind="ACTOR",actor=source["handle"]),
                "Follower priority Cargo differs from the second Geodude")

    def _launch(self,sample,s,sm,se,carrier):
        flags=carrier["throw"];frame=sample["frame"]
        require(self.position_profile is not None and self.windup is not None and "pickup" in self.frames
            and not flags["targetRaw"] and not carrier["bindings"]["trigger"]["bound"]
            and not carrier["bindings"]["cargo"]["bound"]
            and frame-self.windup["frame"]==self.windup["timer"]+1
            and self.windup.get("zeroFrame")==frame-1,
            "Follower priority launch lacks the full authored pickup/windup")
        flight=self._start(sample,s,sm,se);p=flight["plan"]
        require(p["kind"]==2 and p["origin"]==self.windup["carrier"]
            and max(abs(a-b) for a,b in zip(p["origin"],p["target"]))==8
            and max(abs(a-b) for a,b in zip(p["target"],self.windup["player"]))>
                max(abs(a-b) for a,b in zip(p["origin"],self.windup["player"])),
            "Follower priority flight is not an exact-radius throw away from Player")
        self.flight=flight;self.frames["launch"]=frame

    @staticmethod
    def _hop_speed(move,lane,time):
        p=move["plan"];distance=max(abs(a-b) for a,b in zip(p["origin"],p["target"]))
        duration=min(65535,time+(distance-1)*(time-(time>>2))
            +((abs(p["targetBaseY"]-p["startBaseY"])>>12)*time*lane[48])//1600)
        require(lane[7]==lane[36]==time and p["kind"]==2 and distance>0
            and p["duration"]==duration and p["pauseFrames"]==lane[22]==5,
            "Follower priority Hop differs from authored speed or pause")

    def _sample(self,sample,events,action):
        self._boundary(sample);self._profile_events(events)
        require(sample["frame"]==self.latest["frame"]+1 and sample["nativeCycle"]>self.latest["nativeCycle"],
                "Follower priority skipped completed frames")
        m,s=(self._actor(sample,n) for n in ("mankey","source"));self._party_health(sample,m)
        carrier,state=self._carrier(sample,m);flags=carrier["throw"]
        me=self._native(sample,events,m);se=self._native(sample,events,s)
        mm=self._motion(sample,m);sm=self._motion(sample,s);frame=sample["frame"]
        require(normal_input_at_edge(sample,self.latest,16 if action=="move-player-right" else 0,
            first=self.action_frames[self.action_index]==1,events=events),"Follower priority normal input differs")
        launching=self.windup is not None and flags["recovering"] and not flags["carrier"] and any(e.get("event")=="MOTION_STARTED" for e in se)
        self._follow_return(sample,m,mm,me,carrier);self._binding(sample,carrier,s,launching)
        rows=self._queries(sample,events,m) if self.flight is None and not launching else []
        if carrier["bindings"]["cargo"]["bound"] and self.admission is None:
            position=dict(handle=s["handle"],x=s["engineObject"]["x"],y=s["engineObject"]["y"],baseY=s["engineObject"]["pos_y"])
            reached=[r for r in rows if reachable_cargo_admission(r,position)]
            require(self.handoff is not None and reached,"Follower priority Cargo lacks current full native route proof")
            self.admission=deepcopy(reached[-1]);self.frames["cargoBound"]=frame
        if self.binding is not None and self.flight is None and not launching:
            lane=profile(self.profiles.get(m["behaviorFingerprint"]),m,self.source)
            timers=[r for r in sample["pokemonCombat"].get("movementTimers",[]) if r.get("handle")==m["handle"]]
            require(len(timers)==1 and timers[0].get("movementEmoteTimer",21)<=20,
                    "Follower priority extended the authored Notice pause")
            if not flags["carried"]:
                require(m["matchedLayerMask"]&FIND_CARGO and lane[7]==lane[36]==SEARCH_TIME,
                        "Follower priority Find Cargo lost authored half-speed")
        if flags["targetRaw"]:
            require(self.admission is not None and flags["targetSlot"]==s["handle"]["slot"] and flags["carrier"]
                and state["targetMask"]&(1<<s["handle"]["slot"]),"Follower priority lost current pickup claim")
            self.frames.setdefault("claim",frame)
        if self.search_move is not None and self.search_move["returnFrame"] is None:
            if self._advance(sample,m,mm,me,self.search_move):self.search_returns.append(deepcopy(self.search_move))
        if self.cargo_move is not None and self.cargo_move["returnFrame"] is None:
            self._advance(sample,s,sm,se,self.cargo_move)
        if not flags["carried"] and self.flight is None and not launching:
            if any(e.get("event")=="MOTION_STARTED" for e in me) and m["matchedLayerMask"]&FIND_CARGO:
                require(self.admission is not None and frame-self.frames["notice"]>=20,
                        "Follower priority pursuit preceded full route or Notice pause")
                move=self._start(sample,m,mm,me)
                lane=profile(self.profiles.get(m["behaviorFingerprint"]),m,self.source)
                self._hop_speed(move,lane,SEARCH_TIME)
                self.search_move=move
            if any(e.get("event")=="MOTION_STARTED" for e in se):self.cargo_move=self._start(sample,s,sm,se)
        if flags["carried"]:
            require("claim" in self.frames and (self.cargo_move is None or self.cargo_move["returnFrame"] is not None),
                    "Follower priority carried Cargo before its accepted motion returned")
            self.frames.setdefault("pickup",frame);self._held_profile(sample,m,flags)
        if self.flight is None and launching:self._launch(sample,s,sm,se,carrier)
        elif self.flight is not None and self.flight["returnFrame"] is None:
            if self._advance(sample,s,sm,se,self.flight):
                require(self.flight["moved"],"Follower priority flight lacks native movement")
                self.frames["landed"]=frame
        if self.flight is not None and self.flight["returnFrame"] is not None:
            normal=not any(flags[k] for k in ("recovering","targetRaw","carrier","targeted")) \
                and not carrier["bindings"]["trigger"]["bound"] and not carrier["bindings"]["cargo"]["bound"] \
                and m["matchedLayerMask"]&FOLLOWER and not m["matchedLayerMask"]&THROW_MASK
            if normal and self.follow is None and any(e.get("event")=="MOTION_STARTED" for e in me):
                self.follow=self._start(sample,m,mm,me)
                self._hop_speed(self.follow,profile(self.profiles.get(m["behaviorFingerprint"]),m,self.source),7)
                self.frames["followStart"]=frame
            elif self.follow is not None and self.follow["returnFrame"] is None:
                require(normal,"Follower priority normal Follow retained old Throw state")
                if self._advance(sample,m,mm,me,self.follow):
                    require(self.follow["moved"],"Follower priority normal Follow did not move")
                    self.frames["followReturn"]=frame
        self.latest=deepcopy(sample);self.observed_frames+=1

    def stage(self,name):
        require(name in ("source-ready","landed","resumed"),"unknown Follower priority stage")
        if name=="source-ready":
            if self.failures or self.latest is None or self.busy_owner is None:return False
            if self.busy_owner["frame"]!=self.latest["frame"]:return False
            m=self._actor(self.latest,"mankey");x,z=tile(m)
            carrier,_=self._carrier(self.latest,m)
            vx,vz=587-x,404-z
            fx,fz=((0,-1),(0,1),(-1,0),(1,0))[m["engineObject"]["facing"]]
            forward=vx*fx+vz*fz;side=abs(vx*fz-vz*fx)
            return m["motionPhase"]=="IDLE" and m["reservationId"]==0 \
                and 0<max(abs(vx),abs(vz))<=4 and 0<forward and side<=forward \
                and not any(carrier["bindings"][k]["bound"] for k in ("trigger","cargo")) \
                and self.busy_owner["frame"]==self.latest["frame"]
        return not self.failures and self.frames.get("landed" if name=="landed" else "followReturn") is not None

    def observe_record(self,row,on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase")=="setup","Follower priority initial boundary differs")
                self._boundary(row["initialSnapshot"],False)
                require(row["initialSnapshot"].get("prepared") is False,"Follower priority needs unchanged Continue")
                self._profile_events(row.get("initialEvents",[]));self.latest=deepcopy(row["initialSnapshot"])
                return self.result()
            phase=row.get("phase")
            sequence=SETUP if phase=="setup" else ACTIONS
            index=self.setup_index if phase=="setup" else self.action_index
            require(phase in ("setup","observe") and index<len(sequence)
                and (phase=="setup" or self.setup_index==len(SETUP)),"Follower priority observation order differs")
            name,op,args=sequence[index];require(row.get("action")==name,"Follower priority action order differs")
            counts=self.setup_action_frames if phase=="setup" else self.action_frames
            if op=="step":
                for sample,events,_ in validate_raw_chunk(row,self.latest):
                    counts[index]+=1;require(counts[index]<=args["frames"],"Follower priority action exceeded its bound")
                    if phase=="observe":self._sample(sample,events,name)
                    else:
                        self._boundary(sample,name not in ("saved-route-approach","settle-route-approach"))
                        self._profile_events(events)
                        require(normal_input_at_edge(sample,self.latest,
                            16 if name in ("saved-route-approach","face-clear-target") else 0,
                            first=counts[index]==1,events=events),"Follower priority setup input differs")
                        self._remember_busy(sample,events)
                        self.latest=deepcopy(sample);self.observed_frames+=1
                    if on_sample is not None:on_sample(sample,self.observed_frames)
                if "until" in args:
                    if not self.stage(args["until"]["stage"]):return self.result()
                elif counts[index]<args["frames"]:return self.result()
            else:
                require(row.get("command")==op,"Follower priority setup command differs")
                sample=row["snapshot"];self._boundary(sample)
                events=row.get("events",[])+row.get("receipt",{}).get("events",[])
                self._profile_events(events)
                if name=="spawn-source":
                    # Native spawn can complete a field queue and capture
                    # Notice before Bind. Keep that actual boundary; placement
                    # alone still grants no route, pickup or motion credit.
                    self.source_capture=dict(sample=deepcopy(sample),events=deepcopy(events),previous=deepcopy(self.latest))
                if op=="bind":
                    who=args["subject"];selected=select_current_actor(sample,row["receipt"])
                    require(selected["species"]==dict((n,s) for n,s,_,_ in SUBJECTS)[who]
                        and selected["role"]==dict((n,r) for n,_,r,_ in SUBJECTS)[who],"Follower priority bound a different actor")
                    self.subjects[who]=selected
                    if who=="mankey":
                        actor=self._actor(sample,who)
                        require(actor["motionPhase"]=="IDLE" and actor["reservationId"]==0,
                            "Follower priority saved Mankey did not settle")
                        self._party_health(sample,actor,initial=True)
                        self.context=deepcopy(sample["context"]);self.field=sample["fieldControl"].get("fieldPointer")
                    if who=="source":
                        require(self.busy_owner is not None,"Follower priority lacks the earlier busy Wild query")
                        require(tile(self._actor(sample,who))==(587,404)
                            and selected["handle"]!=self.subjects["old-geodude"]["handle"],
                            "Follower priority second Geodude differs from the clear native spawn")
                        capture=self.source_capture
                        require(capture is not None,"Follower priority source capture is missing")
                        saved=self.latest;self.latest=capture["previous"]
                        captured=capture["sample"];m=self._actor(captured,"mankey");source=self._actor(captured,"source")
                        carrier,_=self._carrier(captured,m)
                        self._binding(captured,carrier,source)
                        self._queries(captured,capture["events"],m)
                        self.latest=saved
                self.latest=deepcopy(sample)
            if phase=="setup":self.setup_index+=1
            else:self.action_index+=1
        except (KeyError,TypeError,ValueError,StopIteration) as error:self.failures.append(str(error))
        return self.result()

    def result(self):
        ready=not self.failures and self.action_index==len(ACTIONS)
        return dict(kind=KIND,requirements=[REQUIREMENT],ready=ready,passed=ready,acceptedProof=False,
            observedFrames=self.observed_frames,observedFrameUnit="completed-game-frame",failures=list(self.failures),
            subjects=deepcopy(self.subjects),frames=deepcopy(self.frames),busyOwner=deepcopy(self.busy_owner),
            handoff=deepcopy(self.handoff),sightBinding=deepcopy(self.binding),admission=deepcopy(self.admission),
            flight=deepcopy(self.flight),windup=deepcopy(self.windup),normalFollow=deepcopy(self.follow),
            searchReturns=deepcopy(self.search_returns))

    def finish(self):
        if not self.result()["ready"] and not self.failures:self.failures.append("Follower priority complete handoff/Throw/Follow proof is missing")
        return dict(self.result(),passed=not self.failures,acceptedProof=False)
