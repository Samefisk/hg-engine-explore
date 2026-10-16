"""Accepted Player damage captures its physical source, then throws it away.

Uses the shared full-handle interactions, native 52-byte motion and HP receipt.
No prepared binding, timer or condition earns credit.
"""
from copy import deepcopy

from scripts.overworld_behavior_profile_viewer import _stable_condition_id
from tools.overworld.devtools_follower_throw_measurement import (
    FollowerThrowMeasurement, FIND_POSITION, RELEASE, SEARCH_TIME, raw_handle, require, tile,
)
from tools.overworld.devtools_player_health_hop_contact_measurement import _inside_swept_body
from tools.overworld.devtools_profile_feature_measurement import application_index
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_movement_predicates import player_settled_at, follower_settled, normal_input_at_edge
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion

KIND = "follower-throw-player-damage-v1"
REQUIREMENT = "current.follower-throw-player-damage"
CASE = "follower.throw-player-damage"
DAMAGE_CONDITION = _stable_condition_id("throw", "condition-throw-player-damaged")
CARGO_CONDITION = _stable_condition_id("throw", "condition-throw-picks-up-object-of-interest")
THROW_APP = application_index("apply-throw")
FOLLOWER = 1 << application_index("apply-follower")
FIND_CARGO = 1 << application_index("apply-throw")
AWAY = 1 << application_index("apply-throw-away")
THROW_MASK = sum(1 << application_index(n) for n in (
    "apply-throw", "apply-throw-find-position", "apply-throw-release", "apply-throw-away"))
SUBJECTS = (("mankey", 56, "FOLLOWER", "existing"), ("source", 70, "WILD", "spawn"))
SETUP = (("damage-tile", "teleport", dict(map=33,x=586,z=407,facing=1)),
         ("prepare-mankey", "party", dict(slot=0,species=56,level=20)),
         ("create-follower", "spawn", dict(species=56,form=0,role="follower",slot=0,level=20)),
         ("bind-mankey", "bind", dict(subject="mankey")),
         ("step-left-to-lane", "step", dict(frames=16,keys=["LEFT"],until=dict(kind="player-field",path="x",operator="eq",value=585,when="final"))),
         ("settle-player-at-lane", "step", dict(frames=16,keys=[],until=dict(kind="player-settled-at",map=33,x=585,z=407,when="final"))),
         ("settle-follower-at-lane", "step", dict(frames=16,keys=[],until=dict(kind="follower-settled",species=56,partySlot=0,when="final"))),
         ("spawn-source", "spawn", dict(species=70,form=0,role="wild",level=5,x=585,z=400)),
         ("bind-source", "bind", dict(subject="source")))
RUN_LIMIT, THROW_LIMIT, RETURN_LIMIT = 300, 600, 240
CONTACT_BIND_DELAY = 2  # The condition may resolve after both accepted motions return.

def stage_args(frames, keys, stage):
    return dict(frames=frames,keys=keys,until=dict(kind="measurement-stage",measurement=KIND,stage=stage,when="final"))

ACTIONS = (("before-hit", "player-health.observe", {}),
           ("run-to-hit", "step", stage_args(RUN_LIMIT,["UP","B"],"physical-hit")),
           ("accepted-hit", "player-health.observe", {}),
           ("natural-damage-throw", "step", stage_args(THROW_LIMIT,[],"landed")),
           ("move-player-right", "step", dict(frames=32,keys=["RIGHT"])),
           ("normal-follow-return", "step", stage_args(RETURN_LIMIT,[],"resumed")),
           ("after-return", "player-health.observe", {}))


def validate_recipe(test):
    require(test["id"]==CASE and test["mode"]=="prepared"
        and test["requirements"]==[REQUIREMENT]
        and test["subjects"]==[dict(id=n,species=s,role=r,acquire=a) for n,s,r,a in SUBJECTS]
        and test["measurements"]==[dict(kind=KIND,subject="mankey")]
        and tuple((r["id"],r["op"],r["args"]) for r in test["setup"])==SETUP
        and tuple((r["id"],r["op"],r["args"]) for r in test["actions"])==ACTIONS
        and test["assertions"]==[dict(kind="measurement-complete",measurement=KIND,when="final")]
        and test["budgets"]["maxFrames"]==1400 and test["budgets"]["minObservedFrames"]==2,
        "Damage Follower fixture or normal input differs")


class DamageFollowerMeasurement(FollowerThrowMeasurement):
    def __init__(self,source):
        super().__init__(source)
        self.context=self.field=self.hp_before=self.hp_after=None
        self.running=self.hit=self.binding=self.busy=self.busy_return=None
        self.flight=self.flight_commit=self.follow=None
        self.windup=None
        self.contact=self.contact_returned=None
        self.party_hp=self.party_owner=self.party_hits=None
        self.action_frames=[0]*len(ACTIONS)
        self.setup_action_frames=[0]*len(SETUP)

    def _boundary(self,sample,fixture=True):
        super()._boundary(sample,fixture)
        if self.context is not None:
            require(sample["context"]==self.context and sample["fieldControl"].get("fieldPointer")==self.field,
                    "Damage Follower changed Field context")
        require(not any(a.get("active") and a.get("role")=="MOUNTED" for a in sample.get("actors",[])),
                "Damage Follower must remain on foot")

    def _motion(self,sample,actor):
        rows=[r for r in sample["pokemonCombat"].get("targets",[]) if r.get("handle")==actor["handle"]]
        require(len(rows)==1 and rows[0].get("role")==actor["role"], "Damage Follower lacks current native motion")
        motion=rows[0]["motion"]
        require(motion==decode_motion(bytes.fromhex(motion.get("rawHex",""))),"Damage Follower motion bytes differ")
        return motion

    def _native(self,sample,events,actor):
        rows=self._events(events,actor)
        clock=sample.get("actorFrame")
        require(type(clock) is int,"Damage Follower native Actor clock differs")
        for event in rows:
            event_clock=event.get("actorFrame")
            current=type(event.get("frame")) is int and type(event_clock) is int and event["frame"]==event_clock==clock
            if not current and event.get("event")=="LANE_CHANGED":
                prior=self._actor(self.latest,"mankey" if actor["role"]=="FOLLOWER" else "source")
                current=(type(event.get("frame")) is int and type(event_clock) is int
                    and event["frame"]==event_clock==self.latest.get("actorFrame")==clock-1
                    and prior["handle"]==actor["handle"] and prior.get("laneId")!=actor.get("laneId")
                    and event.get("reason")=="OK" and event.get("valueA")==prior.get("laneId")
                    and event.get("valueB")==actor.get("laneId"))
            require(current,"Damage Follower native Actor clock differs")
        require(not any(e.get("event")=="MOTION_CANCELED" for e in rows),"Damage Follower canceled accepted motion")
        return rows

    def _start(self,sample,actor,motion,events):
        starts=[e for e in events if e.get("event")=="MOTION_STARTED"]
        p=motion["plan"]
        require(len(starts)==1 and starts[0].get("reason")=="OK" and motion["phase"]=="MOVING"
            and actor["motionPhase"]=="MOVING" and motion["elapsed"]==actor["motionElapsed"]==0
            and p["version"]==1 and p["fieldEpoch"]==actor["handle"]["fieldEpoch"]
            and p["origin"]==list(tile(actor,"origin")) and p["target"]==list(tile(actor,"target"))
            and p["reservationId"]==actor["reservationId"]>0
            and p["duration"]==actor["motionDuration"]>0
            and actor["motionKind"]=={1:"WALK",2:"HOP",3:"TELEPORT",4:"SKID",5:"REPOSITION",6:"FLY_IN"}.get(p["kind"])
            and starts[0].get("valueA")==p["kind"] and starts[0].get("valueB")==p["duration"],
            "Damage Follower lacks an accepted native START")
        return dict(frame=sample["frame"],nativeCycle=sample["nativeCycle"],handle=deepcopy(actor["handle"]),
            plan=deepcopy(p),commitBefore=actor["commitSequence"],startSequence=starts[0]["sequence"],
            commit=None,returnFrame=None,pose=self._pose(actor),moved=False)

    @staticmethod
    def _pose(actor):
        values=tuple(actor["engineObject"].get(k) for k in ("pos_x","pos_z","pos_y","unk88_y"))
        require(all(type(v) is int for v in values),"Damage Follower native pose is missing")
        return values

    def _advance(self,sample,actor,motion,events,w):
        """Complete the old owner before accepting a same-queue new START."""
        require(actor["handle"]==w["handle"],"Damage Follower completed a different full owner")
        committed=[e for e in events if e.get("event")=="LOGICAL_COMMIT"]
        finish=[e for e in events if e.get("event")=="MOTION_FINISHED"]
        control=[e for e in events if e.get("event")=="CONTROL_RETURNED"]
        n=w["commitBefore"]+1;kind=w["plan"]["kind"]
        if committed:
            same_queue_successor=motion["plan"]!=w["plan"] and len(finish)==len(control)==1 \
                and any(e.get("event")=="MOTION_STARTED" and e["sequence"]>control[0]["sequence"] for e in events)
            require(len(committed)==1 and w["commit"] is None
                and committed[0].get("reason")=="OK" and committed[0].get("valueA")==n
                and committed[0].get("valueB")==kind and actor["commitSequence"]==n
                and tile(actor)==tuple(w["plan"]["target"]) and self._pose(actor)[2]==w["plan"]["targetBaseY"]
                and (same_queue_successor or (motion["plan"]==w["plan"] and actor["reservationId"]==0
                    and actor["motionPhase"] in ("IDLE","SETTLING"))),
                "Damage Follower lacks exact native COMMIT")
            w["commit"]=dict(frame=sample["frame"],sequence=committed[0]["sequence"],commitSequence=n)
        if finish or control:
            require(w["commit"] is not None and len(finish)==len(control)==1
                and finish[0].get("reason")==control[0].get("reason")=="OK"
                and w["commit"]["sequence"]<finish[0]["sequence"]<control[0]["sequence"]
                and (finish[0].get("valueA"),finish[0].get("valueB"))==(n,kind)
                and (control[0].get("valueA"),control[0].get("valueB"))==(0,n)
                and actor["commitSequence"]==n,"Damage Follower lacks ordered FINISH and CONTROL")
            later=[e for e in events if e.get("event")=="MOTION_STARTED" and e["sequence"]>control[0]["sequence"]]
            if motion["plan"]!=w["plan"] or actor["reservationId"] or actor["motionPhase"]!="IDLE":
                p=motion["plan"]
                require(len(later)==1 and later[0].get("reason")=="OK"
                    and (later[0].get("valueA"),later[0].get("valueB"))==(p["kind"],p["duration"])
                    and motion["phase"]==actor["motionPhase"]=="MOVING"
                    and p["fieldEpoch"]==actor["handle"]["fieldEpoch"]
                    and p["origin"]==w["plan"]["target"]==list(tile(actor,"origin"))
                    and p["target"]==list(tile(actor,"target"))
                    and p["startBaseY"]==w["plan"]["targetBaseY"]
                    and actor["reservationId"]==p["reservationId"]>0
                    and actor["motionKind"]=={1:"WALK",2:"HOP",3:"TELEPORT",4:"SKID",5:"REPOSITION",6:"FLY_IN"}.get(p["kind"]),
                    "Damage Follower successor preceded full control return")
                if committed:
                    self._start(sample,actor,motion,later)
            else:
                require(tile(actor)==tuple(w["plan"]["target"]) and self._pose(actor)[2]==w["plan"]["targetBaseY"],
                        "Damage Follower terminal native pose differs")
            w["returnFrame"]=sample["frame"];w["returnSequence"]=control[0]["sequence"]
            return True
        require(motion["plan"]==w["plan"],"Damage Follower replaced accepted motion before return")
        if w["commit"] is None:
            require(actor["commitSequence"]==w["commitBefore"] and actor["reservationId"]==w["plan"]["reservationId"],
                    "Damage Follower lost its accepted reservation")
        else:
            require(actor["commitSequence"]==n and actor["reservationId"]==0
                and actor["motionPhase"]=="SETTLING" and tile(actor)==tuple(w["plan"]["target"]),
                "Damage Follower changed its settling owner")
        w["moved"] |= self._pose(actor)!=w["pose"]
        return False

    def _follow_state(self,sample,actor,carrier,returned=False):
        flags=carrier["throw"];fresh=carrier["bindings"]["trigger"]
        cargo=carrier["bindings"]["cargo"]
        require(self.flight is not None and self.flight["returnFrame"] is not None
            and not flags["targeted"] and not flags["recovering"]
            and (returned or not any(flags[k] for k in ("targetRaw","carrier","carried","windup"))),
            "Damage Follower normal Follow claimed before control return")
        if fresh["bound"]:
            require(fresh["flags"]==1 and fresh["targetCurrent"] is True
                and fresh["sourceConditionId"]==12365 and fresh["sourceApplication"]==THROW_APP
                and fresh["lifetime"]==0 and fresh["target"]["kind"]=="ACTOR"
                and actor.get("matchedLayerMask",0)&FOLLOWER
                and actor.get("matchedLayerMask",0)&THROW_MASK==FIND_CARGO,
                "Damage Follower return captured an invalid new Sight Interest")
            candidates=[a for a in sample["actors"] if a.get("handle")==fresh["target"]["actor"]]
            require(len(candidates)==1 and candidates[0].get("role")=="WILD",
                    "Damage Follower new Sight Interest has no current Wild owner")
            select_current_actor(sample,candidates[0])
            if cargo["bound"]:
                require(cargo["flags"]==1 and cargo["targetCurrent"] is True
                    and cargo["sourceConditionId"]==CARGO_CONDITION
                    and cargo["sourceApplication"]==THROW_APP and cargo["lifetime"]==0
                    and cargo["target"]==fresh["target"],
                    "Damage Follower new Sight Cargo differs from its current Interest")
            if flags["targetRaw"] or flags["carrier"] or flags["carried"] or flags["windup"]:
                require(returned and cargo["bound"] and flags["carrier"]
                    and flags["targetSlot"]==fresh["target"]["actor"]["slot"],
                    "Damage Follower normal Follow claimed a different fresh Sight target")
        else:
            require(not cargo["bound"] and not any(flags[k] for k in ("targetRaw","carrier","carried","windup"))
                and actor.get("matchedLayerMask",0)&FOLLOWER and not actor.get("matchedLayerMask",0)&THROW_MASK,
                    "Damage Follower return kept a Throw profile")

    def _follow_return(self,sample,actor,motion,events,carrier):
        if self.follow is None or self.follow["returnFrame"] is not None or not any(
                e.get("event") in ("MOTION_FINISHED","CONTROL_RETURNED") for e in events):return
        prior=self._actor(self.latest,"mankey")
        previous,_=self._carrier(self.latest,prior)
        self._follow_state(self.latest,prior,previous)
        require(self._advance(sample,actor,motion,events,self.follow) and self.follow["moved"],
                "Damage Follower normal Follow did not finish")
        self._follow_state(sample,actor,carrier,True)
        self.frames["followReturn"]=sample["frame"]

    def _binding(self,sample,carrier,source,launching=False):
        b=carrier["bindings"]["trigger"]
        if self.follow is not None:
            self._follow_state(sample,self._actor(sample,"mankey"),carrier,
                self.follow["returnFrame"] is not None)
            return
        if b["bound"]:
            require(self.hit is not None and self.hit["frame"]<=sample["frame"]
                and (self.hp_after is not None or sample["frame"]==self.hit["frame"]),
                    "Damage Follower captured before accepted damage")
            require(b["targetCurrent"] is True and b["sourceConditionId"]==DAMAGE_CONDITION
                and b["sourceApplication"]==THROW_APP and b["lifetime"]==0 and b["flags"]==1
                and b["target"]==dict(kind="ACTOR",actor=source["handle"]),
                "Damage Follower Interest is not the accepted physical damage source")
            if self.binding is None:
                self.binding=dict(frame=sample["frame"],nativeCycle=sample["nativeCycle"],binding=deepcopy(b))
                self.frames["capture"]=sample["frame"]
        elif self.binding is not None and self.flight is None and not launching:
            raise ValueError("Damage Follower lost its damage Interest before launch")
        cargo=carrier["bindings"]["cargo"]
        if cargo["bound"]:
            require(self.binding is not None and cargo["targetCurrent"] is True
                and cargo["sourceConditionId"]==CARGO_CONDITION and cargo["sourceApplication"]==THROW_APP
                and cargo["target"]==dict(kind="ACTOR",actor=source["handle"]),
                "Damage Follower Cargo is not Object of Interest itself")

    def _health(self,row,after=False):
        sample=row["snapshot"];self._boundary(sample)
        require(all(sample.get(k)==self.latest.get(k) for k in ("frame","nativeCycle","context","actors","player")),
                "Damage Follower HP read changed the completed boundary")
        h=row.get("receipt",{}).get("playerHealth",{});identity=h.get("identity",{})
        require(h.get("schemaVersion")==1 and identity.get("descriptorVersion")==1 and identity.get("overlayId")==161
            and identity.get("romSha256")==self.source["romSha256"]
            and identity.get("overlaySha256")==self.source["overlaySha256"]
            and h.get("frame")==sample["frame"] and h.get("nativeCycle")==sample["nativeCycle"]
            and h.get("frameActive") is False and h.get("recoveryPending") is False
            and h.get("maxHp")==100 and h.get("hp")==h.get("savedHp"),"Damage Follower HP receipt is stale")
        if not after:
            require((h.get("hp"),h.get("acceptedHits"),h.get("lastDamage"))==(100,0,0),"Damage Follower initial HP differs")
        else:
            require(self.hit is not None and h.get("acceptedHits")==self.hp_before["acceptedHits"]+1
                and self.hp_before["hp"]-h.get("hp",0)==h.get("lastDamage")==20
                and h["hp"]==80
                and h.get("lastHealthFrame",-1)-self.hp_before.get("lastHealthFrame",-1)==sample["frame"]-self.hp_before["frame"],"Damage Follower has contact without accepted HP damage")
        return deepcopy(h)

    def _launch(self,sample,s,sm,se,carrier):
        flags=carrier["throw"];frame=sample["frame"]
        require(self.position_profile is not None and self.windup is not None and "pickup" in self.frames and not flags["targetRaw"]
            and not carrier["bindings"]["trigger"]["bound"] and not carrier["bindings"]["cargo"]["bound"],
            "Damage Follower launched without pickup/windup or binding clear")
        require(frame-self.windup["frame"]==self.windup["timer"]+1
            and self.windup.get("zeroFrame")==frame-1,
                "Damage Follower launch skipped its authored windup")
        flight=self._start(sample,s,sm,se);p=flight["plan"];px,py=self.windup["player"]
        distance=sum(abs(a-b) for a,b in zip(p["origin"],p["target"]))
        require(p["kind"]==2 and p["origin"]==self.windup["carrier"]
            and (p["origin"][0]==p["target"][0] or p["origin"][1]==p["target"][1]) and 1<=distance<=8
            and max(abs(a-b) for a,b in zip(p["target"],[px,py]))>
                max(abs(a-b) for a,b in zip(p["origin"],[px,py])),
            "Damage Follower flight is not a legal cardinal throw away from Player")
        self.flight=flight;self.frames["launch"]=frame

    def _held_profile(self,sample,actor,flags):
        # Pickup changes carried after the intent profile was resolved. A
        # legitimate accepted hit move may own the next intent boundary.
        # Only the actually resolved held phase earns Away/windup credit.
        mask=actor.get("matchedLayerMask",0)
        if mask&FIND_POSITION:
            profile=self.profiles.get(actor["behaviorFingerprint"])
            raw=bytes.fromhex(profile.get("resultHex","")) if profile else b""
            require(len(raw)==216 and profile["fingerprint"]==actor["behaviorFingerprint"]
                and profile["appliedOverrides"]==mask and mask&AWAY
                and raw[13]==14 and raw[7]==raw[36]==SEARCH_TIME and raw[76]==8,
                "Damage Follower current Find Position lacks authored Throw Away")
            self.position_profile=deepcopy(profile);self.frames.setdefault("position",sample["frame"])
        if self.position_profile is not None:
            require(mask&AWAY and mask&(FIND_POSITION|RELEASE),
                    "Damage Follower lost its current held Away profile")
        if flags["windup"] and self.windup is None:
            profile=self.profiles.get(actor["behaviorFingerprint"])
            raw=bytes.fromhex(profile.get("resultHex","")) if profile else b""
            timers=[r for r in sample["pokemonCombat"].get("movementTimers",[]) if r.get("handle")==actor["handle"]]
            require(self.position_profile is not None and mask&AWAY and mask&RELEASE
                and len(raw)==216 and profile["fingerprint"]==actor["behaviorFingerprint"]
                and profile["appliedOverrides"]==mask and raw[13]==14 and raw[76]==8 and len(timers)==1
                and timers[0].get("movementCooldown")==raw[77]>0,
                "Damage Follower windup lacks its current authored Away profile and countdown")
            self.windup=dict(profile=deepcopy(profile),timer=timers[0]["movementCooldown"],frame=sample["frame"],
                player=[sample["player"][k] for k in ("x","y")],carrier=[actor["engineObject"][k] for k in ("x","y")])
            self.frames["windup"]=sample["frame"]

        if flags["windup"]:
            timers=[r for r in sample["pokemonCombat"].get("movementTimers",[]) if r.get("handle")==actor["handle"]]
            elapsed=sample["frame"]-self.windup["frame"]
            remaining=self.windup["timer"]-elapsed
            require(0<=remaining and len(timers)==1
                and timers[0].get("movementCooldown")==remaining,
                "Damage Follower windup changed its authored countdown")
            if remaining==0:self.windup["zeroFrame"]=sample["frame"]

    def _party_health(self,sample,actor,initial=False):
        party=[p for p in sample.get("party",[]) if p.get("personality")==actor["subjectIdentity"]]
        require(len(party)==1 and party[0].get("identityVerified") is True
            and party[0].get("species")==56 and type(party[0].get("hp")) is int
            and 0<party[0]["hp"]<=party[0].get("maxHp",0),
            "Damage Follower changed its living party owner")
        mon=party[0];owner={k:v for k,v in mon.items() if k!="hp"}
        require(initial or owner==self.party_owner,"Damage Follower changed its living party owner")
        provenance=sample.get("partyObservation",{});combat=sample.get("pokemonCombat",{})
        require(provenance.get("frame")==combat.get("frame")==sample["frame"]
            and provenance.get("boundary")==combat.get("observationBoundary")==sample["observationBoundary"]
            and combat.get("available") is True and combat.get("nativeCycle")==sample["nativeCycle"]
            and combat.get("identity",{}).get("romSha256")==self.source["romSha256"]
            and combat["identity"].get("overlaySha256")==self.source["overlaySha256"],
            "Damage Follower party health authority is stale")
        for field in ("hp","maxHp","species","level"):
            checks=[r for r in provenance.get("nativeGetterChecks",[]) if r.get("slot")==mon["slot"]
                and r.get("field")==field and r.get("personality")==mon["personality"]]
            require(len(checks)==1 and checks[0].get("passed") is True
                and checks[0].get("boundary")=="natural-GetMonData-return"
                and checks[0].get("frame")==sample["frame"]
                and type(checks[0].get("nativeCycle")) is int
                and (initial or self.latest["nativeCycle"]<checks[0]["nativeCycle"])
                and checks[0]["nativeCycle"]<=sample["nativeCycle"]
                and checks[0].get("native")==checks[0].get("decoded")==mon[field],
                "Damage Follower party health lacks current native authority")
        targets=[r for r in combat.get("targets",[]) if r.get("handle")==actor["handle"]]
        require(len(targets)==1,"Damage Follower native health owner differs")
        hp=targets[0]
        require(hp.get("role")=="FOLLOWER" and hp.get("initialized")==1
            and hp.get("personality")==mon["personality"] and hp.get("species")==mon["species"]
            and hp.get("form")==mon["form"] and hp.get("level")==mon["level"]
            and hp.get("mapId")==sample["context"]["mapId"]
            and hp.get("mapGeneration")==actor["handle"]["mapGeneration"]
            and hp.get("encounterGeneration")==actor["handle"]["encounterGeneration"]
            and hp.get("hpSource")=="party" and hp.get("hpMirrorMatches") is True
            and hp.get("hp")==hp.get("currentHp")==mon["hp"]
            and hp.get("maxHp")==hp.get("actualMaxHp")==mon["maxHp"]
            and type(hp.get("hitCount")) is int and type(hp.get("lastDamage")) is int,
            "Damage Follower native party health differs")
        if not initial:
            delta=self.party_hp-mon["hp"]
            require((delta==0 and hp["hitCount"]==self.party_hits)
                or (delta>0 and hp["hitCount"]==self.party_hits+1 and hp["lastDamage"]==delta),
                "Damage Follower HP changed without one current accepted native hit")
        self.party_owner=deepcopy(owner);self.party_hp=mon["hp"];self.party_hits=hp["hitCount"]

    def _physical_contact(self,sample,source):
        # A swept hit can precede the condition's next legal intent boundary.
        # This is a candidate only; the explicit HP receipt grants hit credit.
        return (self.hit is None and source["motionKind"]=="HOP"
            and source["motionPhase"]=="MOVING"
            and 0<source["motionElapsed"]<source["motionDuration"]
            and _inside_swept_body(self._actor(self.latest,"source")["engineObject"],
                source["engineObject"],sample["player"]))

    def _damage_contact(self,sample,source,carrier):
        b=carrier["bindings"]["trigger"]
        return (self._physical_contact(sample,source)
            and b["bound"] and b["targetCurrent"] is True and b["flags"]==1
            and b["sourceConditionId"]==DAMAGE_CONDITION
            and b["sourceApplication"]==THROW_APP and b["lifetime"]==0
            and b["target"]==dict(kind="ACTOR",actor=source["handle"]))

    def _delayed_damage_binding(self,sample,source,motion,carrier):
        b=carrier["bindings"]["trigger"]
        if not b["bound"] or self.contact is None or self.hit is not None:
            return False
        require(b["targetCurrent"] is True and b["flags"]==1
            and b["sourceConditionId"]==DAMAGE_CONDITION
            and b["sourceApplication"]==THROW_APP and b["lifetime"]==0
            and b["target"]==dict(kind="ACTOR",actor=source["handle"]),
            "Damage Follower Interest is not the accepted physical damage source")
        candidate=self.contact
        require(0<sample["frame"]-candidate["frame"]<=CONTACT_BIND_DELAY
            and source["handle"]==candidate["source"]
            and motion["plan"]==candidate["plan"]
            and (source["motionPhase"]=="MOVING"
                 and source["reservationId"]==candidate["plan"]["reservationId"]
                 or source["motionPhase"]=="IDLE"
                 and self.contact_returned is True
                 and source["reservationId"]==0
                 and source["commitSequence"]==candidate["commitBefore"]+1),
            "Damage Follower damage binding lost its accepted physical source")
        return True

    def _sample(self,sample,events,action):
        self._boundary(sample);self._profile_events(events)
        require(sample["frame"]==self.latest["frame"]+1 and sample["nativeCycle"]>self.latest["nativeCycle"],
                "Damage Follower skipped completed frames")
        m,s=(self._actor(sample,n) for n in ("mankey","source"))
        require(m["handle"]!=s["handle"],"Damage Follower source equals carrier")
        self._party_health(sample,m)
        carrier,state=self._carrier(sample,m);flags=carrier["throw"]
        me=self._native(sample,events,m);se=self._native(sample,events,s)
        mm=self._motion(sample,m);sm=self._motion(sample,s);frame=sample["frame"]
        if self.busy is not None and self.busy["returnFrame"] is None:
            if self._advance(sample,m,mm,me,self.busy):
                if self.hit is not None or self.contact is not None:
                    self.busy_return=deepcopy(self.busy);self.frames["moveReturn"]=frame
                else:self.busy=None
        if self.hit is None and any(e.get("event")=="MOTION_STARTED" for e in me):
            self.busy=self._start(sample,m,mm,me)
        if action=="run-to-hit":
            require(normal_input_at_edge(sample,self.latest,66,
                    first=self.action_frames[self.action_index]==1,events=events),
                    "Damage Follower lacks normal running input")
            for e in events:
                d=e.get("data",{})
                if e.get("kind")=="native-observation" and d.get("observation")=="player-step-admitted" \
                    and d.get("direction")==0 and d.get("objectAfter",{}).get("movement_cmd")==88:
                    self.running=frame
            if self._physical_contact(sample,s):
                if self.contact is not None:
                    require(s["handle"]==self.contact["source"]
                        and sm["plan"]==self.contact["plan"],
                        "Damage Follower replaced its accepted physical Hop")
                require(self.running is not None and self.running<frame and self.busy is not None
                    and self.busy["frame"]<frame and self.busy["returnFrame"] is None
                    and m["motionPhase"] in ("MOVING","COMMIT_PENDING","SETTLING"),
                    "Damage Follower hit lacks an already accepted busy follower move")
                profile=self.profiles.get(s["behaviorFingerprint"])
                raw=bytes.fromhex(profile.get("resultHex","")) if profile else b""
                require(len(raw)==216 and tuple(raw[72:75])==(1,16,20) and raw[79]==6,
                        "Damage Follower physical source lacks the current attacking Ambush profile")
                require(sm["plan"]["kind"]==2 and sm["plan"]["version"]==1
                    and sm["plan"]["fieldEpoch"]==s["handle"]["fieldEpoch"]
                    and sm["plan"]["reservationId"]==s["reservationId"]>0,
                    "Damage Follower physical source lacks its accepted Hop plan")
                self.contact=dict(frame=frame,nativeCycle=sample["nativeCycle"],
                    source=deepcopy(s["handle"]),plan=deepcopy(sm["plan"]),
                    commitBefore=s["commitSequence"],pose=deepcopy(s["engineObject"]),
                    player=deepcopy(sample["player"]))
                self.contact_returned=False
            if self.contact is not None and self.hit is None:
                require(frame-self.contact["frame"]<=CONTACT_BIND_DELAY
                    and s["handle"]==self.contact["source"]
                    and sm["plan"]==self.contact["plan"],
                    "Damage Follower damage binding missed its current Hop window")
                committed=[e for e in se if e.get("event")=="LOGICAL_COMMIT"]
                finished=[e for e in se if e.get("event")=="MOTION_FINISHED"]
                returned=[e for e in se if e.get("event")=="CONTROL_RETURNED"]
                if finished or returned:
                    require(len(committed)==len(finished)==len(returned)==1
                        and committed[0]["sequence"]<finished[0]["sequence"]<returned[0]["sequence"]
                        and committed[0]["valueA"]==self.contact["commitBefore"]+1
                        and finished[0]["valueA"]==committed[0]["valueA"]
                        and returned[0]["valueB"]==committed[0]["valueA"]
                        and (committed[0]["valueB"],finished[0]["valueB"])==(2,2)
                        and returned[0]["valueA"]==0
                        and s["motionPhase"]==sm["phase"]=="IDLE"
                        and s["reservationId"]==0,
                        "Damage Follower physical source lacks ordered Hop return")
                    self.contact_returned=True
            if (self._damage_contact(sample,s,carrier)
                    or self._delayed_damage_binding(sample,s,sm,carrier)):
                self.hit=dict(frame=frame,nativeCycle=sample["nativeCycle"],source=deepcopy(s["handle"]),
                    pose=deepcopy(s["engineObject"]),player=deepcopy(sample["player"]),
                    physicalContact=deepcopy(self.contact));self.frames["hit"]=frame
        else:
            require(normal_input_at_edge(sample,self.latest,16 if action=="move-player-right" else 0,
                    first=self.action_frames[self.action_index]==1,events=events),
                    "Damage Follower input differs")
        # The same-frame damage candidate still needs the explicit HP receipt.
        launching=self.windup is not None and flags["recovering"] and not flags["carrier"] and any(e.get("event")=="MOTION_STARTED" for e in se)
        self._follow_return(sample,m,mm,me,carrier)
        self._binding(sample,carrier,s,launching)
        if flags["targetRaw"] and self.follow is None:
            require(self.busy_return is not None and self.busy_return["returnFrame"]<=frame,
                    "Damage Follower claimed before accepted move return")
            require(self.binding is not None and flags["targetSlot"]==s["handle"]["slot"] and flags["carrier"]
                and state["targetMask"] & (1<<s["handle"]["slot"]),"Damage Follower claimed another source")
            self.frames.setdefault("claim",frame)
        if flags["carried"] and self.follow is None:
            require(self.frames.get("claim") is not None,"Damage Follower carried without a full native claim")
            self.frames.setdefault("pickup",frame)
            self._held_profile(sample,m,flags)
        starts=[e for e in se if e.get("event")=="MOTION_STARTED"]
        if self.flight is None and flags["recovering"] and not flags["carrier"] and starts:
            self._launch(sample,s,sm,se,carrier)
        elif self.flight is not None and self.flight["returnFrame"] is None:
            if self._advance(sample,s,sm,se,self.flight):
                require(self.flight["moved"],"Damage Follower flight lacks native movement")
                self.frames["landed"]=frame
        if self.flight is not None and self.flight["returnFrame"] is not None:
            normal=(not flags["recovering"] and not flags["targetRaw"] and not flags["carrier"]
                and not flags["targeted"] and not carrier["bindings"]["trigger"]["bound"]
                and not carrier["bindings"]["cargo"]["bound"] and m.get("matchedLayerMask",0)&FOLLOWER
                and not m.get("matchedLayerMask",0)&THROW_MASK)
            if normal and self.follow is None and any(e.get("event")=="MOTION_STARTED" for e in me):
                self.follow=self._start(sample,m,mm,me);self.frames["followStart"]=frame
            elif self.follow is not None and self.follow["returnFrame"] is None:
                self._follow_state(sample,m,carrier)
                if self._advance(sample,m,mm,me,self.follow):
                    require(self.follow["moved"],"Damage Follower normal Follow did not move")
                    self.frames["followReturn"]=frame
        self.latest=deepcopy(sample);self.observed_frames+=1

    def stage(self,name):
        require(name in ("physical-hit","landed","resumed"),"unknown Damage Follower stage")
        return not self.failures and {"physical-hit":self.hit,"landed":self.frames.get("landed"),
            "resumed":self.frames.get("followReturn")}[name] is not None

    def observe_record(self,row,on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase")=="setup","Damage Follower initial boundary differs")
                self._boundary(row["initialSnapshot"],False);self._profile_events(row.get("initialEvents",[]));self.latest=deepcopy(row["initialSnapshot"]);return self.result()
            if row.get("phase")=="setup":
                require(self.setup_index<len(SETUP),"Damage Follower extra setup")
                name,op,args=SETUP[self.setup_index]
                require(row.get("action")==name,"Damage Follower setup order differs")
                if op=="step":
                    for sample,events,_ in validate_raw_chunk(row,self.latest):
                        self._boundary(sample);self._profile_events(events);self.latest=deepcopy(sample)
                        self.setup_action_frames[self.setup_index]+=1
                        require(self.setup_action_frames[self.setup_index]<=args["frames"],
                                "Damage Follower lane setup exceeded its bound")
                        if name=="settle-follower-at-lane":
                            require(player_settled_at(sample,33,585,407),
                                    "Damage Follower Player moved during neutral follower settle")
                        if on_sample is not None:on_sample(sample,self.observed_frames)
                    require(self.latest["player"]["y"]==407 and self.latest["player"]["facing"]==2,
                            "Damage Follower sidestep changed lane or facing")
                    if name=="step-left-to-lane":
                        if self.latest["player"]["x"]!=585:return self.result()
                    elif name=="settle-player-at-lane":
                        if not player_settled_at(self.latest,33,585,407):return self.result()
                    else:
                        if not follower_settled(self.latest,56,0):return self.result()
                    actor=self._actor(self.latest,"mankey")
                    require(not (tile(actor)[0]==585 and tile(actor)[1]<=407)
                        and not (actor["engineObject"]["x"]==585 and actor["engineObject"]["y"]<=407),
                        "Damage Follower normal sidestep blocked the north lane")
                else:
                    require(row.get("command")==op,"Damage Follower setup command differs")
                    if name=="spawn-source":
                        require(player_settled_at(self.latest,33,585,407)
                                and follower_settled(self.latest,56,0),
                                "Damage Follower source spawn preceded normal movement return")
                    sample=row["snapshot"];self._boundary(sample);self._profile_events(row.get("events",[])+row.get("receipt",{}).get("events",[]));self.latest=deepcopy(sample)
                    if op=="bind":
                        who=args["subject"];selected=select_current_actor(sample,row["receipt"])
                        require(selected.get("species")==dict((n,s) for n,s,_,_ in SUBJECTS)[who]
                            and selected.get("role")==dict((n,r) for n,_,r,_ in SUBJECTS)[who],"Damage Follower bound a different role")
                        self.subjects[who]=selected;actor=self._actor(sample,who)
                        if who=="mankey":
                            party=[p for p in sample.get("party",[]) if p.get("personality")==actor["subjectIdentity"]]
                            require(len(party)==1 and party[0].get("hp",0)>0,"Damage Follower party identity is missing")
                            require(actor["motionPhase"]=="IDLE" and actor["reservationId"]==0,
                                    "Damage Follower did not settle before source creation")
                            require((sample["player"]["x"],sample["player"]["y"],sample["player"]["facing"])==(586,407,1)
                                and tile(actor)==(586,408)
                                and (actor["engineObject"]["x"],actor["engineObject"]["y"])==(586,408),
                                "Damage Follower native start blocks the north running path")
                            self._party_health(sample,actor,initial=True)
                        else:
                            m=self._actor(sample,"mankey");carrier,_=self._carrier(sample,m)
                            require(not carrier["bindings"]["trigger"]["bound"] and not carrier["bindings"]["cargo"]["bound"],
                                    "Damage Follower earned Sight before damage")
                            require(max(abs(a-b) for a,b in zip(tile(m),tile(actor)))>5,
                                    "Damage Follower source starts inside authored Sight")
                            self.context=deepcopy(sample["context"]);self.field=sample["fieldControl"].get("fieldPointer")
                self.setup_index+=1;return self.result()
            require(row.get("phase")=="observe" and self.setup_index==len(SETUP)
                and self.action_index<len(ACTIONS),"Damage Follower observation order differs")
            name,op,args=ACTIONS[self.action_index];require(row.get("action")==name,"Damage Follower action order differs")
            if op=="step":
                require("command" not in row,"Damage Follower needs dense native frames")
                for sample,events,_ in validate_raw_chunk(row,self.latest):
                    self.action_frames[self.action_index]+=1
                    require(self.action_frames[self.action_index]<=args["frames"],"Damage Follower action exceeded its bound")
                    self._sample(sample,events,name)
                    if on_sample is not None:on_sample(sample,self.observed_frames)
                until=args.get("until")
                if (until and self.stage(until["stage"])) or (not until and self.action_frames[self.action_index]==args["frames"]):
                    self.action_index+=1
            else:
                require(row.get("command")==op,"Damage Follower HP command differs")
                if name=="before-hit":self.hp_before=self._health(row)
                else:
                    h=self._health(row,True)
                    if name=="accepted-hit":
                        require(row["snapshot"]["frame"]==self.hit["frame"],"Damage Follower missed the accepted hit boundary")
                        self.hp_after=h
                    else:require(self.frames.get("followReturn") is not None,"Damage Follower has no normal follow return")
                self.latest=deepcopy(row["snapshot"]);self.action_index+=1
        except (KeyError,TypeError,ValueError,StopIteration) as error:self.failures.append(str(error))
        return self.result()

    def result(self):
        ready=not self.failures and self.action_index==len(ACTIONS)
        return dict(kind=KIND,requirements=[REQUIREMENT],ready=ready,passed=ready,acceptedProof=False,observedFrames=self.observed_frames,
            observedFrameUnit="completed-game-frame",failures=list(self.failures),subjects=deepcopy(self.subjects),
            frames=deepcopy(self.frames),acceptedHit=deepcopy(self.hit),healthBefore=deepcopy(self.hp_before),
            healthAfter=deepcopy(self.hp_after),damageBinding=deepcopy(self.binding),busyMovement=deepcopy(self.busy_return),
            flight=deepcopy(self.flight),windup=deepcopy(self.windup),normalFollow=deepcopy(self.follow))

    def finish(self):
        if not self.result()["ready"] and not self.failures:self.failures.append("Damage Follower normal Throw and Follow proof is incomplete")
        return dict(self.result(),passed=not self.failures,acceptedProof=False)
