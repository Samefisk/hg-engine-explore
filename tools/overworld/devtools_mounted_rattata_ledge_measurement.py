"""One fresh Walk mount crosses a permitted ledge using the shared native Hop.

Only existing completed-frame actor, native motion, resolver and terrain data
are read. This is separate from the running Stantler momentum claim.
"""
from copy import deepcopy
from fractions import Fraction
from tools.overworld.normal_play_observer import arc_height
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion

KIND = "mounted-rattata-walking-ledge-v1"
TEST = "mount.rattata-walking-ledge"
REQUIREMENT = "current.mounted-rattata-walking-ledge"
SETUP = (
    ("south-ledge-from-rest", "teleport", dict(map=33,x=590,z=395,facing=1)),
    ("own-rattata", "party", dict(slot=0,species=19,level=20,status=0)),
    ("mount-own-rattata", "spawn", dict(species=19,form=0,role="mounted",slot=0,level=20)),
    ("bind-rattata", "bind", dict(subject="rattata")),
)
ORDER = ("down-into-permitted-ledge", "release-through-hop-terminal")
DURATION = 12


def need(value, reason):
    if not value:raise ValueError("mounted Rattata ledge: " + reason)


def validate_recipe(test):
    stage = dict(kind="measurement-stage",measurement=KIND,stage="started",when="final")
    need(test["id"] == TEST and test["mode"] == "prepared" and test["requirements"] == [REQUIREMENT]
         and test["subjects"] == [dict(id="rattata",species=19,role="MOUNTED",acquire="existing")]
         and test["measurements"] == [dict(kind=KIND,subject="rattata")]
         and tuple((a["id"],a["op"],a["args"]) for a in test["setup"]) == SETUP
         and tuple((a["id"],a["op"],a["args"]) for a in test["actions"]) == (
             (ORDER[0],"step",dict(frames=32,keys=["DOWN"],until=stage)),
             (ORDER[1],"step",dict(frames=48,keys=[])))
         and test["assertions"] == [dict(kind="measurement-complete",measurement=KIND,when="final")]
         and test["budgets"]["maxFrames"] <= 480 and test["budgets"]["minObservedFrames"] >= 24,
         "recipe differs from the exact fresh Walk ledge trigger")


class MountedRattataLedgeMeasurement:
    def __init__(self, source):
        self.source=source
        self.latest=self.subject=self.baseline=self.hop=self.release=None
        self.setup_index=self.action_index=self.observed_frames=self.neutral_frames=0
        self.events=[]
        self.failures=[]

    def _boundary(self, sample, fixture=True):
        need(sample.get("fieldAvailable") is True and sample.get("observationBoundary") == "main-task-queue-completion"
             and sample.get("romSha256") == self.source["romSha256"] and sample.get("fieldControl",{}).get("taskPointer") == 0,
             "completed current field boundary differs")
        if fixture:need(sample.get("context",{}).get("mapId") == 33,"left Route29")

    def _actor(self, sample):
        selected=select_current_actor(sample,self.subject)
        actor=next(a for a in sample["actors"] if a["handle"] == selected["handle"])
        need((actor["species"],actor["role"]) == (19,"MOUNTED") and actor.get("inputOwnership") == 1
             and actor["handle"]["slot"] == 7,"mounted identity or input owner differs")
        engine,player=actor["engineObject"],sample["player"]
        need(all(engine.get(k) == player.get(k) for k in ("pos_x","pos_y","pos_z","unk88_y"))
             and player.get("face_y",0)-engine.get("face_y",0) == 32768,
             "mount and rider split their shared anchor")
        return actor

    def _profile(self, sample, actor, cache):
        coverage=sample.get("nativeObservation",{})
        need(isinstance(cache,dict) and cache.get("frame",-1) >= sample["frame"]
             and cache.get("nativeCycle",-1) >= sample["nativeCycle"] and coverage.get("coverageComplete") is True
             and coverage.get("profilesEvicted") == 0 and actor["behaviorFingerprint"] in coverage.get("profileFingerprints",[]),
             "missing current native resolver coverage")
        rows=[r for r in cache.get("resolvedProfiles",[]) if r.get("resolved") is True
              and r.get("fingerprint") == actor["behaviorFingerprint"]]
        need(rows and len({r.get("resultHex") for r in rows}) == 1
             and all(r.get("sourceSha256") == self.source["profileSha256"] for r in rows),
             "resolved mounted lane differs from sealed profile source")
        raw=bytes.fromhex(rows[0]["resultHex"])
        lane=raw[80:160]
        need(len(raw)==216 and lane[7]==6 and lane[9]==2 and lane[12]==1
             and tuple(lane[20:22])==(1,8) and lane[19]&3 == 0 and lane[58]&1 == 0
             and int.from_bytes(raw[192:196],"little")==actor["behaviorFingerprint"],
             "requires authored Walk/time6/jumpBoth/hop1..8/obstacleHopNo")
        return deepcopy(rows[0])

    def _native(self, sample, actor):
        combat=sample.get("pokemonCombat",{})
        need(combat.get("available") is True and combat.get("schemaVersion")==1
             and combat.get("frame")==sample["frame"] and combat.get("nativeCycle")==sample["nativeCycle"]
             and combat.get("identity",{}).get("romSha256")==self.source["romSha256"]
             and combat["identity"].get("overlaySha256")==self.source["overlaySha256"],
             "missing coherent native motion owner")
        rows=[r for r in combat.get("targets",[]) if r.get("handle")==actor["handle"]]
        need(len(rows)==1 and (rows[0].get("species"),rows[0].get("role"),rows[0].get("personality"))
             ==(19,"MOUNTED",actor["subjectIdentity"]) and rows[0].get("hpSource")=="party"
             and rows[0].get("hp",0)>0 and rows[0].get("knockbackPending")==0,
             "native motion has another living party owner or pending hit")
        motion=rows[0].get("motion")
        need(isinstance(motion,dict) and motion==decode_motion(bytes.fromhex(motion.get("rawHex",""))),
             "native motion bytes differ")
        return motion

    def arm(self, sample, subject):
        self._boundary(sample)
        self.subject=deepcopy(select_current_actor(sample,subject))
        actor=self._actor(sample)
        need(actor.get("motionKind")=="NONE" and actor.get("motionPhase")=="IDLE"
             and actor.get("reservationId")==0 and actor.get("logical")==dict(x=590,y=395)
             and (sample["player"]["x"],sample["player"]["y"])==(590,395)
             and all(actor.get("movementPolicy",{}).get(k)==0 for k in ("speed","base","skid","turn")),
             "baseline is not a fresh zero-speed idle Walk mount")
        cells={tuple(c.get(k) for k in ("x","y")):c for c in sample.get("terrain",{}).get("cells",[])}
        ledge,landing=cells.get((590,396),{}),cells.get((590,397),{})
        need(ledge.get("loaded") is True and ledge.get("behavior")==59 and ledge.get("collision") is True
             and landing.get("loaded") is True and landing.get("collision") is False,
             "measured South ledge or clear landing differs")
        self.baseline=dict(actor=deepcopy(actor),player=deepcopy(sample["player"]),ledge=deepcopy(ledge),landing=deepcopy(landing))
        self.latest=deepcopy(sample)

    def _sample(self,sample,events,cache):
        self._boundary(sample)
        need(sample["context"]==self.latest["context"],"field context changed")
        actor=self._actor(sample)
        selector=sample.get("selector",{})
        mask=128 if self.action_index==0 else 0
        # A key release can become visible at the next input queue. It cannot
        # keep DOWN held after that one boundary or admit another motion.
        allowed=(mask,128) if self.action_index==1 and self.neutral_frames==0 else (mask,)
        need(selector.get("rawHeld")==selector.get("heldKeys") and selector.get("rawHeld") in allowed
             and selector.get("simulatedKeys")==0,"normal DOWN/released input differs")
        for event in events:
            data=event.get("data",{})
            if event.get("kind")=="trace-status":
                need(data.get("unreadEventsLost",0)==0 and data.get("coverageComplete",True) is True,
                     "native trace coverage incomplete")
            if event.get("kind")!="native" or data.get("actorHandle")!=self.subject["handle"]["value"]:continue
            need(data.get("actor")=={k:v for k,v in self.subject["handle"].items() if k!="value"}
                 and type(data.get("sequence")) is int,"native event has another full owner")
            need(data.get("event") not in ("MOTION_CANCELED","ACTOR_REBOUND","CONTEXT_CHANGED")
                 and not (data.get("event")=="WORLD_EFFECT" and data.get("valueA")==3),
                 "crash, cancel or rebound during the ledge Hop")
            self.events.append(dict(data,frame=event["frame"]))
        motion=self._native(sample,actor)
        if self.hop is None and actor["motionKind"]=="HOP":
            profile=self._profile(sample,actor,cache)
            plan=motion["plan"]
            need(motion["elapsed"]==actor["motionElapsed"]==1 and plan["version"]==1 and plan["kind"]==2
                 and plan["flags"]==0 and plan["fieldEpoch"]==actor["handle"]["fieldEpoch"]
                 and plan["behaviorFingerprint"]==actor["behaviorFingerprint"]&65535
                 and plan["origin"]==[590,395] and plan["target"]==[590,397]
                 and (plan["distance"],plan["duration"],plan["arcHeightQ4"],plan["direction"],plan["facing"])==(2,12,16,1,1),
                 "normal admitted two-tile time6 Hop differs")
            starts=[e for e in self.events if e["frame"]==sample["frame"] and e["event"]=="MOTION_STARTED"
                    and (e.get("valueA"),e.get("valueB"))==(2,12) and e.get("reasonId")==0]
            need(len(starts)==1 and any(e["event"]=="INTENT_CREATED" and e["frame"]==sample["frame"]
                 and e["sequence"]<starts[0]["sequence"] for e in self.events),"Hop lacks a new normal input intent/start")
            self.hop=dict(actor=deepcopy(actor["handle"]),plan=deepcopy(plan),sourceProfile=profile,
                          startFrame=sample["frame"],startSequence=starts[0]["sequence"],samples=[])
        if self.hop is None:
            need(actor["motionKind"]=="NONE" and actor["logical"]==dict(x=590,y=395),"walked into the blocked ledge")
        elif self.release is None:
            plan=self.hop["plan"]
            need(motion["plan"]==plan,"Hop native plan or endpoint changed")
            elapsed=motion["elapsed"]
            previous=self.hop["samples"][-1]["elapsed"] if self.hop["samples"] else 0
            engine=actor["engineObject"]
            if actor["motionKind"]=="HOP":
                need(elapsed==actor["motionElapsed"]==previous+1 and elapsed<=DURATION
                     and actor["reservationId"]==plan["reservationId"] and actor["origin"]==dict(x=590,y=395)
                     and actor["target"]==dict(x=590,y=397),"Hop skipped a native flight sample")
                base=plan["startBaseY"]+int(Fraction((plan["targetBaseY"]-plan["startBaseY"])*elapsed,DURATION))
                need(engine.get("pos_x")== (590<<16)+32768
                     and engine.get("pos_z")== (395<<16)+32768+int(Fraction(131072*elapsed,DURATION))
                     and engine.get("pos_y")==base and engine.get("face_y")==arc_height(elapsed,DURATION)
                     and engine.get("unk88_y")==self.baseline["actor"]["engineObject"].get("unk88_y",0),
                     "Hop rendered arc or base height differs")
                self.hop["samples"].append(dict(frame=sample["frame"],elapsed=elapsed,engine=deepcopy(engine)))
            else:
                terminal=[e for e in self.events if e["sequence"]>self.hop["startSequence"]
                          and e["event"] in ("LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED")]
                commit=self.baseline["actor"]["commitSequence"]+1
                need(previous==DURATION and [e["event"] for e in terminal]
                     ==["LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"]
                     and all(e["frame"]==sample["frame"] and e.get("reasonId")==0 for e in terminal)
                     and terminal[0]["sequence"]<terminal[1]["sequence"]<terminal[2]["sequence"]
                     and [(e.get("valueA"),e.get("valueB")) for e in terminal]==[(commit,2),(commit,2),(1,commit)]
                     and actor["commitSequence"]==commit and actor["motionKind"]=="NONE"
                     and actor["motionPhase"]=="IDLE" and actor["reservationId"]==0,
                     "Hop lacks one ordered normal commit/finish/input return")
                self.release=dict(frame=sample["frame"],events=deepcopy(terminal),commitSequence=commit)
        if self.release is not None:
            engine=actor["engineObject"]
            need(actor["logical"]==dict(x=590,y=397) and (sample["player"]["x"],sample["player"]["y"])==(590,397)
                 and actor["motionKind"]=="NONE" and actor["motionPhase"]=="IDLE" and actor["reservationId"]==0
                 and actor["commitSequence"]==self.release["commitSequence"]
                 and engine.get("pos_x")== (590<<16)+32768 and engine.get("pos_z")== (397<<16)+32768
                 and all(engine.get(k,0)==self.baseline["actor"]["engineObject"].get(k,0) for k in ("pos_y","face_y","unk88_y")),
                 "released mount did not stay at the exact ledge landing/base")
        self.latest=deepcopy(sample)
        self.observed_frames+=1
        if self.action_index==1:self.neutral_frames+=1

    def stage(self,name):
        need(name in ("started","finished"),"unknown stage")
        return not self.failures and (self.hop is not None if name=="started" else self.release is not None and self.neutral_frames==48)

    def observe_record(self,row,on_sample=None):
        try:
            if "initialSnapshot" in row:
                need(self.latest is None and row.get("phase")=="setup","initial boundary differs")
                self._boundary(row["initialSnapshot"],False)
                self.latest=deepcopy(row["initialSnapshot"])
            elif row.get("phase")=="setup":
                need(self.setup_index<len(SETUP) and (row.get("action"),row.get("command"))==SETUP[self.setup_index][:2],"setup order differs")
                self._boundary(row["snapshot"])
                if row["action"]=="mount-own-rattata":
                    need(row.get("receipt",{}).get("lifecycle")=="prepared-native-follower-lifecycle","normal native mount lifecycle differs")
                if row["command"]=="bind":self.arm(row["snapshot"],row["receipt"])
                self.latest=deepcopy(row["snapshot"])
                self.setup_index+=1
            else:
                need(self.setup_index==len(SETUP) and row.get("phase")=="observe" and self.action_index<len(ORDER)
                     and row.get("action")==ORDER[self.action_index] and "command" not in row,"observation order differs")
                for sample,events,_ in validate_raw_chunk(row,self.latest):
                    need(self.observed_frames<80,"observation exceeds its bound")
                    self._sample(sample,events,row.get("profileCache"))
                    if on_sample:on_sample(sample,self.observed_frames)
                if self.stage("started" if self.action_index==0 else "finished"):self.action_index+=1
        except (ValueError,KeyError,TypeError,StopIteration,IndexError) as error:self.failures.append(str(error))
        return self.result()

    def result(self):
        ready=not self.failures and self.action_index==len(ORDER) and self.stage("finished") and self.observed_frames>=24
        return dict(kind=KIND,requirements=[REQUIREMENT],ready=ready,passed=ready,acceptedProof=False,
                    observedFrames=self.observed_frames,observedFrameUnit="completed-game-frame",
                    subject=deepcopy(self.subject),baseline=deepcopy(self.baseline),hop=deepcopy(self.hop),release=deepcopy(self.release),
                    finalActor=deepcopy(self._actor(self.latest)) if ready else None,failures=list(self.failures))

    def finish(self):
        if not self.result()["ready"] and not self.failures:self.failures.append("mounted Rattata ledge: no complete fresh ledge Hop and input return")
        return self.result()
