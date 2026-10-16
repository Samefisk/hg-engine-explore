"""One Route30 three-Sentret/saved-Mankey window through existing readers.

No recorder, input driver or native observer lives here. Prepared spawn calls
inside the timed window retain their native events, not invented snapshots.
"""
from copy import deepcopy

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.devtools_follower_throw_measurement import (
    FollowerThrowMeasurement, TRIGGER_CONDITION, CARGO_CONDITION,
    APPLICATION, APPLICATION_LOCAL, THROW_RANGE)
from tools.overworld.devtools_main_loop_probe import (
    MainLoopProbe, RETURN_SITE, SCOPE, NORMAL_MAIN_LOOP_NATIVE_CYCLES, MAX_ZERO_STUTTER_ARM9_TICKS)
from tools.overworld.devtools_walk_matrix_observer import decode_motion

KIND = "route30-sentret-throw-pacing-v1"
REQUIREMENT = "current.route30-sentret-throw-pacing"
TEST = "world.route30.sentret-throw-pacing"
SUBJECTS = (("mankey",56,"FOLLOWER","existing"),
            ("sentret-a",161,"WILD","spawn"), ("sentret-b",161,"WILD","spawn"),
            ("sentret-c",161,"WILD","spawn"), ("cargo",69,"WILD","spawn"))
SETUP = (("route30", "teleport", dict(map=34,x=565,z=369,facing=2)),
         ("route30-settle16","step",dict(frames=16,keys=[])),
         ("spawn-sentret-a","spawn",dict(species=161,form=0,role="wild",level=3,x=563,z=370)),
         ("bind-sentret-a","bind",dict(subject="sentret-a")),
         ("spawn-sentret-b","spawn",dict(species=161,form=0,role="wild",level=3,x=564,z=370)),
         ("bind-sentret-b","bind",dict(subject="sentret-b")),
         ("spawn-sentret-c","spawn",dict(species=161,form=0,role="wild",level=3,x=565,z=371)),
         ("bind-sentret-c","bind",dict(subject="sentret-c")),
         ("bind-mankey","bind",dict(subject="mankey")),
         ("arm600","main-loop-pacing.arm",dict(maxFrames=600)),
         ("cpu1200","cpu-work.start",dict(maxNativeFrames=1200)))
ACTIONS = (("left120","step",dict(frames=120,keys=["LEFT"])),
           ("down120","step",dict(frames=120,keys=["DOWN"])),
           ("settle16","step",dict(frames=16,keys=[])),
           ("spawn-cargo","spawn",dict(species=69,form=0,role="wild",level=5,x=564,z=375)),
           ("bind-cargo","bind",dict(subject="cargo")),
           ("neutral348","step",dict(frames=348,keys=[])),
           ("cpu-final","cpu-work.read",{}))
BUDGET = dict(maxFrames=1100,maxSeconds=360,noProgressFrames=600,minObservedFrames=600)
HANDLE_KEYS = ("slot","generation","fieldEpoch","mapGeneration","encounterGeneration")


def need(value, message):
    if not value:
        raise ValueError("Sentret Throw: " + message)


def validate_recipe(test):
    need(test.get("id")==TEST and test.get("mode")=="prepared"
         and test.get("fixture")==dict(rom="test.nds",save="test.sav")
         and test.get("requirements")==[REQUIREMENT]
         and test.get("subjects")==[dict(id=n,species=s,role=r,acquire=a) for n,s,r,a in SUBJECTS]
         and test.get("measurements")==[dict(kind=KIND,subject="mankey")]
         and tuple((a["id"],a["op"],a["args"]) for a in test["setup"])==SETUP
         and tuple((a["id"],a["op"],a["args"]) for a in test["actions"])==ACTIONS
         and test["setup"][0].get("budget")==dict(maxSeconds=90,maxFrames=120,noProgressFrames=120)
         and test["setup"][1].get("budget")==dict(maxSeconds=90,maxFrames=16,noProgressFrames=16)
         and test.get("budgets")==BUDGET
         and test.get("assertions")==[dict(kind="measurement-complete",measurement=KIND,when="final")],
         "exact fixture, input or budget differs")


class SentretThrowMeasurement:
    def __init__(self, test, source):
        validate_recipe(test)
        need(source.get("contractVersion")==2 and set(source)=={
            "contractVersion","romSha256","sourceSaveSha256","overlaySha256","profileSha256","queryImage"},
            "source identity differs")
        self.test,self.source=test,deepcopy(source)
        self.throw=FollowerThrowMeasurement({k:v for k,v in source.items() if k!="sourceSaveSha256"})
        self.latest=None
        self.subjects={}
        self.setup_index=self.action_index=self.action_frames=0
        self.observed_frames=0
        self.first=None
        self.pacing=[]
        self.last_sequence=None
        self.held=self.windup=self.launch=None
        self.cargo_birth=None
        self.cpu=None
        self.last_player_pose=None
        self.moving_frames=0
        self.failures=[]
        self.closed=False

    def _boundary(self, sample):
        need(sample.get("fieldAvailable") is True
             and sample.get("observationBoundary")=="main-task-queue-completion"
             and sample.get("romSha256")==self.source["romSha256"]
             and sample.get("sourceSaveSha256")==self.source["sourceSaveSha256"]
             and sample.get("context",{}).get("mapId")==34
             and sample.get("fieldControl",{}).get("taskPointer")==0,
             "current Route30 field or source differs")
        native=sample.get("nativeObservation",{})
        need(native.get("coverageComplete") is True and native.get("installedBeforeBoot") is True
             and native.get("eventsDropped")==0 and native.get("pendingUnframedEvents")==0
             and native.get("profilesEvicted")==0 and native.get("error") is None,
             "native reader lost data")
        need(not any(a.get("active") and a.get("role")=="MOUNTED" for a in sample.get("actors",[])),
             "player became mounted")
        party=[p for p in sample.get("party",[]) if p.get("slot")==2]
        need(len(party)==1 and party[0].get("species")==56
             and party[0].get("personality")==2920357538 and party[0].get("identityVerified") is True,
             "saved Mankey party identity differs")

    def _actor(self,sample,name):
        bound=select_current_actor(sample,self.subjects[name])
        need(engine_binding_identity(bound["engineIdentity"])==engine_binding_identity(self.subjects[name]["engineIdentity"]),
             "full current engine identity changed")
        actor=next(a for a in sample["actors"] if a.get("handle")==bound["handle"])
        need(actor.get("form")==0 and actor.get("level")== (5 if name=="cargo" else 3),
             "current actor form or level changed")
        return actor

    def _adopt(self,name,row):
        sample,receipt=row["snapshot"],row["receipt"]
        value=receipt.get("value",{})
        observed=value.get("entrySpawn",{})
        entry=observed.get("receipt",{})
        native=entry.get("actor",{})
        species,level=(69,5) if name=="cargo" else (161,3)
        need(receipt.get("snapshot")==sample and entry.get("version")==1 and entry.get("size")==64
             and type(entry.get("serial")) is int and entry["serial"]>0
             and entry.get("status")==1 and entry.get("queued")==0 and native.get("reserved")==0
             and observed.get("frame")==sample["frame"] and value.get("species")==species
             and native.get("slot")==value.get("slot"), "spawn lacks actual ADOPT")
        actors=[a for a in sample.get("actors",[]) if a.get("species")==species
                and a.get("role")=="WILD" and a.get("level")==level
                and a.get("subjectIdentity")==value.get("personality")
                and all(a.get("handle",{}).get(k)==native.get(k) for k in HANDLE_KEYS)]
        need(len(actors)==1,"ADOPT lacks one full current Actor")
        selected=select_current_actor(sample,actors[0])
        need(all(selected["handle"]!=s["handle"] for s in self.subjects.values()),
             "prepared actors share a handle")
        self.subjects[name]=selected
        if name=="cargo": self.cargo_birth=sample["frame"]

    def _events(self,events,end_frame,on_events=None):
        need(isinstance(events,list) and len(events)<=8192,"event prefix exceeds its bound")
        by_frame={}
        for event in events:
            need(isinstance(event,dict) and type(event.get("frame")) is int
                 and 0<=event["frame"]<=end_frame and isinstance(event.get("data"),dict),
                 "event is outside its actual completed boundary")
            by_frame.setdefault(event["frame"],[]).append(event)
        # Reuse TestEvaluator's strict full-handle, stream, sequence and event
        # decoder. Commands may drain several real completed boundaries.
        if on_events is not None:
            for frame,rows in sorted(by_frame.items()):on_events(rows,frame)
        for event in events:
            data=event.get("data",{})
            if event.get("kind")=="trace-status":
                code=data.get("code")
                need(type(data.get("traceStream")) is int and data["traceStream"]>0
                     and data.get("diagnosticOnly") is True
                     and data.get("coverageComplete") is not False
                     and code in ("window-started","field-epoch-changed","ring-overwrite","window-ended"),
                     "semantic trace lost data or unknown notice")
                if code=="ring-overwrite":
                    need(type(data.get("count")) is int and data["count"]>0
                         and type(data.get("unreadEventsLost")) is int and data["unreadEventsLost"]==0,
                         "semantic trace lost data")
                elif code=="window-ended":
                    need(data.get("reason")=="stopped","semantic trace expired before completion")
                elif code=="field-epoch-changed":
                    need(data.get("sequenceReset") is False,"semantic trace reset during field change")
            if event.get("kind")!="native-observation": continue
            sequence=data.get("sequence")
            need(type(sequence) is int and sequence>0 and (self.last_sequence is None or sequence==self.last_sequence+1),
                 "native receipt sequence gap")
            self.last_sequence=sequence
            if data.get("observation")!="stock-main-loop-pacing" or self.first is None: continue
            after=data.get("afterQueueFrame")
            if type(after) is not int or not self.first<=after<self.first+600: continue
            need(MainLoopProbe._clock_ok(data.get("guestClock"))
                 and all(type(data.get(k)) is int and data[k]>=0 for k in ("actorFrame","nativeCycle","frameCounter"))
                 and data.get("returnSite")==RETURN_SITE and data.get("scope")==SCOPE
                 and data.get("diagnosticOnly") is False and data.get("setupMode")=="prepared"
                 and data.get("flushedAtQueueFrame")==event.get("frame")<=end_frame
                 and data["flushedAtQueueFrame"]==after+1
                 and data.get("windowIndex")==0
                 and data.get("loopId")==len(self.pacing)+1
                 and after==self.first+len(self.pacing), "pacing owner or continuous600 window differs")
            need(data["frameCounter"]<=NORMAL_MAIN_LOOP_NATIVE_CYCLES,"late main loop")
            interval=data.get("intervalFromPrevious")
            if self.pacing:
                need(interval==MainLoopProbe._interval(self.pacing[-1],data)
                     and isinstance(interval,dict) and all(type(interval.get(k)) is int and interval[k]>=0
                     for k in ("arm9Ticks","nativeCycles","frameSequence","actorFrames")),
                     "pacing interval is missing")
                need(interval["nativeCycles"]<=NORMAL_MAIN_LOOP_NATIVE_CYCLES
                     and interval["frameSequence"]<=NORMAL_MAIN_LOOP_NATIVE_CYCLES
                     and interval["arm9Ticks"]<=MAX_ZERO_STUTTER_ARM9_TICKS
                     and data.get("frameCounter")<=NORMAL_MAIN_LOOP_NATIVE_CYCLES,
                     "late main loop")
            else: need(interval is None,"first pacing sample has an unbound interval")
            self.pacing.append(deepcopy(data));self.observed_frames=len(self.pacing)

    def _player_sample(self,sample):
        player=sample.get("player",{})
        need(all(type(player.get(k)) is int for k in ("x","y","x_prev","y_prev","pos_x","pos_z")),
             "Player movement sample is missing")
        pose=[player["pos_x"],player["pos_z"]]
        if player["x"]!=player["x_prev"] or player["y"]!=player["y_prev"]:
            need(pose!=self.last_player_pose,"Player render froze during normal input")
            self.moving_frames+=1
        self.last_player_pose=pose

    def _throw_sample(self,sample,events):
        if self.cargo_birth is None or sample["frame"]<=self.cargo_birth or self.launch is not None: return
        if not self.first<=sample["frame"]-1<self.first+600: return
        mankey,cargo=self._actor(sample,"mankey"),self._actor(sample,"cargo")
        row,state=self.throw._carrier(sample,mankey)
        flags=row["throw"]
        if flags["carried"] and flags["targetSlot"]==cargo["handle"]["slot"]:
            for key,condition in (("trigger",TRIGGER_CONDITION),("cargo",CARGO_CONDITION)):
                b=row["bindings"][key]
                need(b["bound"] and b["targetCurrent"] and b["sourceConditionId"]==condition
                     and b["sourceApplication"]==APPLICATION and b["sourceApplicationLocal"]==APPLICATION_LOCAL
                     and b["lifetime"]==0 and b["target"]==dict(kind="ACTOR",actor=cargo["handle"]),
                     "HELD is not the noticed Cargo")
            timers=[t for t in sample["pokemonCombat"]["movementTimers"] if t.get("handle")==cargo["handle"]]
            need(len(timers)==1 and timers[0].get("movementActorControlMode")==1,
                 "Cargo has no native HELD control")
            self.held=self.held or sample["frame"]
            if flags["windup"]:self.windup=sample["frame"]
        if self.held is None or self.windup is None or not (flags["recovering"] and not flags["carried"] and flags["targetRaw"]==0):return
        motions=[t["motion"] for t in sample["pokemonCombat"]["targets"] if t.get("handle")==cargo["handle"]]
        need(len(motions)==1,"Cargo motion lacks a current native owner")
        motion=motions[0]
        if motion.get("phase")!="MOVING" or motion.get("elapsed")!=0:return
        raw=bytes.fromhex(motion.get("rawHex",""))
        need(decode_motion(raw)==motion,"Cargo native motion decode differs")
        plan=motion["plan"];origin,target=plan["origin"],plan["target"]
        player=(sample["player"]["x"],sample["player"]["y"])
        launches=[e for e in self.throw._events(events,cargo) if e.get("event")=="MOTION_STARTED"]
        need(plan["kind"]==2 and plan["distance"]==THROW_RANGE
             and max(abs(a-b) for a,b in zip(origin,target))==THROW_RANGE
             and max(abs(a-b) for a,b in zip(target,player))>max(abs(a-b) for a,b in zip(origin,player))
             and self.held<=self.windup<sample["frame"] and len(launches)==1
             and launches[0]["valueA"]==2 and launches[0]["valueB"]==plan["duration"],
             "no actual outward Throw launch")
        self.launch=dict(frame=sample["frame"],heldFrame=self.held,windupFrame=self.windup,
                         nativeMotion=deepcopy(motion),event=deepcopy(launches[0]))

    def observe_record(self,row,on_sample=None,on_events=None):
        try:
            if "initialSnapshot" in row:
                need(self.latest is None and row.get("phase")=="setup","initial boundary is misplaced")
                sample=row["initialSnapshot"]
                need(sample.get("romSha256")==self.source["romSha256"]
                     and sample.get("sourceSaveSha256")==self.source["sourceSaveSha256"],"source ROM/save differs")
                initial=row.get("initialEvents",[])
                start=row.get("initialEventStartFrame",sample["frame"])
                need(type(start) is int and 0<=start<=sample["frame"]
                     and all(e.get("kind")=="native-observation" or start<=e.get("frame",-1)
                             for e in initial),"initial semantic prefix is outside record start")
                self._events(initial,sample["frame"],on_events)
                self.latest=deepcopy(sample);return self.result()
            phase=row.get("phase")
            need(phase in ("setup","observe") and (phase=="setup" or self.setup_index==len(SETUP)),
                 "action phase is misplaced")
            expected=SETUP if phase=="setup" else ACTIONS
            index=self.setup_index if phase=="setup" else self.action_index
            need(index<len(expected) and row.get("action")==expected[index][0],"action order differs")
            name,op,args=expected[index]
            if op=="step":
                need("command" not in row,"normal input became a command")
                need(row.get("requestedInput")==dict(frames=row.get("completedGameFrames"),keys=args["keys"],
                                                     releaseAtEnd=False,diagnosticDetails=False),
                     "actual normal input keys or count changed")
                for sample,events,_ in validate_raw_chunk(row,self.latest):
                    self._boundary(sample)
                    for subject in self.subjects:self._actor(sample,subject)
                    self._events(events,sample["frame"],on_events)
                    # The post-warp setup wait keeps coverage but earns no
                    # movement, pacing or Throw credit before the probes arm.
                    if phase=="observe":
                        self._player_sample(sample);self._throw_sample(sample,events)
                    self.latest=deepcopy(sample);self.action_frames+=1
                    if on_sample:on_sample(sample,self.observed_frames)
                need(self.action_frames<=args["frames"],"input frame bound exceeded")
                if self.action_frames<args["frames"]:return self.result()
                if name=="settle16":
                    need((self.latest["player"]["x"],self.latest["player"]["y"])==(565,376)
                         and self._actor(self.latest,"mankey")["logical"]==dict(x=565,y=375),
                         "normal input did not reach the retained Cargo corridor")
                    cells=[c for c in self.latest["terrain"]["cells"] if (c["x"],c["z"])==(564,375)]
                    need(len(cells)==1 and cells[0].get("loaded") is True
                         and cells[0].get("collision") is False and cells[0].get("behavior")==0,
                         "Cargo tile is not legal loaded land")
                self.action_frames=0
            else:
                need(row.get("command")==op,"native command differs")
                sample=row["snapshot"];receipt=row.get("receipt",{})
                self._boundary(sample)
                self._events(receipt.get("events",[]),sample["frame"],on_events)
                if op=="spawn":
                    self._adopt("cargo" if name=="spawn-cargo" else name.removeprefix("spawn-"),row)
                elif op=="bind":
                    subject=args["subject"]
                    if subject=="mankey":
                        actors=[a for a in sample["actors"] if a.get("species")==56 and a.get("role")=="FOLLOWER"
                                and a.get("subjectIdentity")==2920357538]
                        need(len(actors)==1,"saved Mankey follower is missing")
                        self.subjects[subject]=select_current_actor(sample,actors[0])
                    need(receipt==select_current_actor(sample,self.subjects[subject]),"bound full Actor differs")
                elif op=="main-loop-pacing.arm":
                    need(set(self.subjects)=={n for n,_,_,_ in SUBJECTS if n!="cargo"},"three Sentret are not admitted")
                    for subject in self.subjects:self._actor(sample,subject)
                    probe=receipt.get("probe",{})
                    need(sample["frame"]==self.latest["frame"] and probe.get("armedAtQueueFrame")==sample["frame"]
                         and probe.get("firstObservedQueueFrame")==sample["frame"]+1
                         and probe.get("lastObservedQueueFrame")==sample["frame"]+601
                         and probe.get("guestMemoryWrites")==0,"pacing arm differs")
                    self.first=probe["firstObservedQueueFrame"]
                elif op.startswith("cpu-work"):
                    probe=receipt.get("probe",{})
                    need(sample["frame"]==self.latest["frame"] and probe.get("maxNativeFrames")==1200
                         and probe.get("failure") is None,"CPU owner or bound differs")
                    if op=="cpu-work.read":
                        frames=probe.get("frames",[])
                        need(probe.get("closed") is True and probe.get("observedNativeFrames")==1200
                             and len(frames)==1200 and all(b["nativeFrame"]==a["nativeFrame"]+1
                             for a,b in zip(frames,frames[1:])),"CPU1200 is incomplete")
                        self.cpu=dict(observedNativeFrames=1200,closed=True,failure=None)
                self.latest=deepcopy(sample)
            if phase=="setup":self.setup_index+=1
            else:self.action_index+=1
        except (ValueError,KeyError,TypeError,StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def close(self):
        self.closed=True
        if not self.ready():self.failures.append("Sentret Throw: incomplete600 loops or real Throw")
        return self.result()

    finish = close

    def ready(self):
        return not self.failures and self.setup_index==len(SETUP) and self.action_index==len(ACTIONS) \
            and len(self.pacing)==600 and self.launch is not None and self.cpu is not None

    def result(self):
        return dict(kind=KIND,passed=self.ready(),ready=self.ready(),closed=self.closed,
            acceptedProof=False,source=deepcopy(self.source),requirements=[REQUIREMENT],
            failures=deepcopy(self.failures),observedFrames=self.observed_frames,
            observedFrameUnit="completed-main-loop-return",subjects=deepcopy(self.subjects),
            timingWindow=[self.first,self.first+600] if self.first is not None else None,
            pacing=deepcopy(self.pacing),movingFrames=self.moving_frames,renderStalls=0,
            throw=deepcopy(self.launch),cpu=deepcopy(self.cpu))
