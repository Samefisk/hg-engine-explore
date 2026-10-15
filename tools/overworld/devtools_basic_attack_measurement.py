"""One adjacent Wild Basic attack pair, from capture to HP loss and return.

Prepared placement is excluded. The meter never changes a profile or timer.
"""
from copy import deepcopy
import struct

from tools.overworld.devtools_profile_feature_measurement import application_index, decode_condition
from tools.overworld.devtools_pokemon_combat_measurement import PokemonCombatMeasurement
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel

KIND = "basic-attack-v1"
REQUIREMENT = "current.basic-attack"
APPLICATION = application_index("apply-basic-attack", allow_disabled=True)
ATTACK_MASK = 0 if APPLICATION is None else 1 << APPLICATION
CONDITION = 21375
MIN_FRAMES = 16
WAIT_FRAMES = 240
TAIL_FRAMES = 16
SUBJECTS = (("snorlax", 143, "WILD", "spawn"), ("cyndaquil", 155, "WILD", "spawn"),
            ("passive", 174, "FOLLOWER", "existing"))
SETUP_IDS = ("attack-tile", "prepare-passive", "spawn-passive", "bind-passive",
             "spawn-snorlax", "spawn-cyndaquil", "bind-snorlax", "bind-cyndaquil")
ACTION_IDS = ("before-contact", "observe-attack", "finish-contact", "after-contact")
NAMES = {
    "live-actor-identity": ("current-wild-snorlax-and-cyndaquil",),
    "profile-resolution": ("basic-captures-adjacent-pokemon-and-resolves-inherited-hop-time4",),
    "engine-boundary": ("basic-collision-removes-real20-hp",),
    "logical-commit": ("basic-hop-pair-commits-interest-then-saved-origin",),
    "rendered-motion": ("basic-hop4-pair-has-complete-airborne-travel-and-faces-movement",),
    "natural-input": ("basic-neutral-input-without-profile-or-timer-writes",),
    "control-release": ("basic-immediate-return-then-pause20-to40-frames",),
}
CLAIMS = tuple(NAMES)
FAULTS = ("basic:missing-condition", "basic:stale-target", "basic:wrong-hop-time", "basic:missing-hit", "basic:missing-return")


def require(value, message):
    if not value:
        raise ValueError("Basic attack: " + message)


def validate_recipe(test):
    require(test["id"] == "profile.basic-attack" and test["mode"] == "prepared"
            and test["requirements"] == [REQUIREMENT]
            and test["subjects"] == [dict(id=n, species=s, role=r, acquire=a) for n,s,r,a in SUBJECTS]
            and test["measurements"] == [dict(kind=KIND, subject="snorlax")]
            and [a["id"] for a in test["setup"]] == list(SETUP_IDS)
            and [a["op"] for a in test["setup"]] == ["teleport", "party", "spawn", "bind", "spawn", "spawn", "bind", "bind"]
            and test["setup"][0]["args"] == dict(map=33,x=594,z=399,facing=0)
            and test["setup"][1]["args"] == dict(slot=0,species=174,level=50)
            and test["setup"][2]["args"] == dict(species=174,form=0,role="follower",slot=0,level=50)
            and test["setup"][3]["args"] == dict(subject="passive")
            and test["setup"][4]["args"] == dict(species=143,form=0,role="wild",level=50,x=595,z=396)
            and test["setup"][5]["args"] == dict(species=155,form=0,role="wild",level=50,x=596,z=396)
            and [a["args"] for a in test["setup"][6:]] == [dict(subject="snorlax"), dict(subject="cyndaquil")]
            and [a["id"] for a in test["actions"]] == list(ACTION_IDS)
            and [a["op"] for a in test["actions"]] == ["player-health.observe", "step", "step", "player-health.observe"]
            and test["actions"][0]["args"] == test["actions"][-1]["args"] == {}
            and test["actions"][1]["args"] == dict(frames=WAIT_FRAMES, keys=[], until=dict(
                kind="measurement-stage",measurement=KIND,stage="landed",when="final"))
            and test["actions"][2]["args"] == dict(frames=TAIL_FRAMES,keys=[])
            and test["budgets"]["minObservedFrames"] == MIN_FRAMES
            and test["budgets"]["maxFrames"] <= 600,
            "fixture or normal input differs")


class BasicAttackMeasurement:
    _boundary = PokemonCombatMeasurement._boundary
    _actor = PokemonCombatMeasurement._actor
    _hp = PokemonCombatMeasurement._hp
    _pose = staticmethod(PokemonCombatMeasurement._pose)
    _native = PokemonCombatMeasurement._events

    def __init__(self, source, test=None):
        require(APPLICATION is not None, "application is disabled; enable Basic attack before running this test")
        self.source, self.test = source, test
        self.latest = self.initial = self.terminal = None
        self.subjects = {}
        self.setup_index = self.action_index = self.frames = 0
        self.action_frames = [0] * len(ACTION_IDS)
        self.failures, self.events = [], []
        self.motion = MotionRecorder()
        self.before = self.previous_hp = self.after = None
        self.capture = self.trigger = self.start = self.hit = self.ended = None
        self.return_start = self.pair_pause = None
        self.busy_frames, self.skipped_pairs = [], []
        self.same_tile_capture = None
        self.arc = False

    def _capture(self, sample, actor, target):
        value = sample.get("pokemonCombat", {}).get("interactions", {})
        require(value.get("schemaVersion") == 1 and value.get("available") is True
                and value.get("frame") == sample["frame"] and value.get("nativeCycle") == sample["nativeCycle"]
                and value.get("observationBoundary") == "main-task-queue-completion"
                and value.get("fieldSystem") == sample["fieldControl"].get("fieldPointer")
                and value.get("identity", {}).get("romSha256") == self.source["romSha256"],
                "condition capture lacks a current native boundary")
        owners = [r for r in value.get("carriers",[]) if r.get("handle") == actor["handle"]]
        require(len(owners) == 1 and owners[0].get("available") is True and owners[0].get("role") == "WILD",
                "condition owner is absent or stale")
        captures = [c for c in owners[0].get("conditionCaptures",[]) if c.get("conditionId") == CONDITION]
        require(len(captures) == 1, "authored condition capture is absent")
        c = captures[0]
        raw, data = bytes.fromhex(c.get("preparedRawHex", "")), bytes.fromhex(c.get("rawHex", ""))
        index = c.get("preparedIndex")
        require(len(raw) == 52 and raw[:12] == raw_handle(actor["handle"]) and raw[49] == 1
                and type(index) is int and 0 <= index < raw[48] <= 32
                and raw[16+index] == c.get("catalogIndex") and struct.unpack_from("<I",raw,12)[0] == c.get("statesPointer")
                and len(data) == 16 and struct.unpack("<II3H2B",data) == (
                    0,0,target["handle"]["slot"],target["handle"]["generation"],target["handle"]["encounterGeneration"],2,1)
                and c.get("target") == dict(kind="ACTOR",actor=target["handle"])
                and c.get("targetCurrent") is True and c.get("targetValid") is True
                and c.get("targetPosition") == [target["engineObject"][k] for k in ("x","y")]
                and c.get("application") == APPLICATION and c.get("activationMode") == 0
                and c.get("durationFrames") == c.get("cooldownFrames") == 0
                and c.get("activeApplicationMask",0) & ATTACK_MASK,
                "while-true condition did not capture the exact current Pokemon")
        return deepcopy(c)

    def _profile(self, sample, actor, cache):
        require(isinstance(cache,dict) and cache.get("frame",-1) >= sample["frame"]
                and cache.get("nativeCycle",-1) >= sample["nativeCycle"]
                and actor["behaviorFingerprint"] in sample.get("nativeObservation",{}).get("profileFingerprints",[]),
                "profile lacks a coherent native cache")
        rows = [r for r in cache.get("resolvedProfiles",[]) if r.get("resolved") is True
                and r.get("fingerprint") == actor["behaviorFingerprint"]]
        require(len(rows) == 1 and rows[0].get("sourceSha256") == self.source["profileSha256"],
                "profile differs from sealed source")
        data = bytes.fromhex(rows[0].get("resultHex", ""))
        require(len(data) == 216 and data[0] == 3 and data[12:14] == bytes((2,10))
                and struct.unpack_from("<HH",data,32) == (16,1023) and data[36] == 4
                and data[42] >> 1 == 1 and data[65] == 0
                and data[72:76] == bytes((1,1,20,0)) and data[79]&3 == 0,
                "source lacks Chase/Hop, Interest-only terrain, inherited time4, return-after-move, Face movement, impact speed1, damage20 or inherited no-knockback")

    def _admission(self, sample, actor, native, starts, origin, target, commit_policy):
        motion = self._hp(sample,"snorlax").get("motion")
        require(isinstance(motion,dict) and motion == decode_motion(bytes.fromhex(motion.get("rawHex",""))),
                "Hop lacks exact native motion bytes")
        plan = motion["plan"]
        dx,dy = (target[i]-origin[i] for i in range(2))
        facing = 3 if dx==1 and dy==0 else 2 if dx==-1 and dy==0 else 1 if dy==1 and dx==0 else 0 if dy==-1 and dx==0 else None
        require(len(starts)==1 and starts[0].get("reason")=="OK" and starts[0].get("valueB")==4
                and actor["motionKind"]=="HOP" and actor["motionPhase"]=="MOVING"
                and actor["motionElapsed"] in (0,1)
                and plan["kind"]==2 and plan["duration"]==4 and plan["distance"]==1 and plan["flags"]==0
                and plan["origin"]==origin and plan["target"]==target and facing is not None
                and plan["facing"]==facing and plan["direction"]==facing and actor["engineObject"]["facing"]==facing
                and plan["startBaseY"]==plan["targetBaseY"] and plan["arcHeightQ4"]>=16
                and plan["pauseFrames"]==0 and plan["pathAdvancePolicy"]==1 and plan["commitPolicy"]==commit_policy,
                "Hop leg lacks exact normal four-frame travel, movement facing or pair commit policy")
        accepted = [e for e in native if e.get("event")=="PLAN_ACCEPTED" and e.get("reason")=="OK"
                    and e.get("valueA")==target[0]<<16|target[1] and e.get("valueB")==4
                    and e["sequence"]<starts[0]["sequence"]]
        require(len(accepted)==1,"Hop lacks its matching accepted destination")
        return dict(frame=sample["frame"],plan=deepcopy(plan),event=deepcopy(starts[0]))

    def _busy_origin(self,sample,actor,native):
        origin=self.start["plan"]["origin"]
        witnesses=[]
        for other in sample["actors"]:
            if other.get("handle")==actor["handle"] or other.get("active") is not True \
                    or other.get("motionPhase")!="MOVING" or other.get("motionKind") not in ("WALK","HOP") \
                    or not other.get("reservationId") or [other["target"][k] for k in ("x","y")]!=origin:
                continue
            selected=select_current_actor(sample,other)
            rows=[r for r in sample["pokemonCombat"]["targets"] if r.get("handle")==selected["handle"]]
            require(len(rows)==1,"busy origin lacks its exact foreign motion owner")
            motion=rows[0].get("motion")
            require(isinstance(motion,dict) and motion==decode_motion(bytes.fromhex(motion.get("rawHex","")))
                    and motion["phase"]=="MOVING" and motion["plan"]["reservationId"]==other["reservationId"]
                    and motion["plan"]["target"]==origin and motion["plan"]["kind"] in (1,2),
                    "busy origin lacks a current foreign MOVING reservation")
            witnesses.append(dict(subject=selected,motion=deepcopy(motion),actor=deepcopy(other)))
        retries=[e for e in native if e.get("event")=="CANDIDATE_REJECTED" and e.get("reason")=="REJECTED_RESERVED"]
        require(witnesses and len(retries)==1,"outward Hop ended without its immediate return or one current foreign reservation retry")
        require(type(sample.get("actorFrame")) is int,"busy return lacks the current Actor frame")
        if self.busy_frames:
            require(len(self.busy_frames)<2 and 0<sample["actorFrame"]-self.busy_frames[-1]["actorFrame"]
                    and sample["actorFrame"]-self.busy_frames[0]["actorFrame"]<=2,
                    "return retry repeated an Actor frame or exceeded two busy frames")
        engine=actor["engineObject"];target=self.start["plan"]["target"]
        require(actor["motionPhase"]=="IDLE" and actor["inputOwnership"]==0
                and [actor["logical"][k] for k in ("x","y")]==target
                and [engine["pos_x"],engine["pos_z"]]==[(v<<16)+32768 for v in target]
                and engine["pos_y"]==self.start["plan"]["targetBaseY"] and engine.get("unk88_y",0)==0,
                "busy return lost its grounded outward landing")
        self.busy_frames.append(dict(frame=sample["frame"],actorFrame=sample["actorFrame"],
                                     witnesses=witnesses,retry=deepcopy(retries[0])))

    def observe(self, sample, events, cache):
        self._boundary(sample)
        actor, target = self._actor(sample,"snorlax"), self._actor(sample,"cyndaquil")
        native = self._native(events,actor)
        same_tile_truth = None
        self.events.extend(deepcopy(events))
        require(not any(e.get("event") in ("MOTION_CANCELED","ACTOR_REBOUND","CONTEXT_CHANGED") for e in native),
                "attack owner or motion was canceled")
        for e in events:
            if e.get("kind") != "native" or e.get("data",{}).get("actorHandle") != actor["handle"]["value"] \
                    or e["data"].get("event") != "CONDITIONAL_RESOLVED":
                continue
            decoded = decode_condition(e)
            if decoded["application"] != APPLICATION or decoded["conditionId"] != CONDITION:
                continue
            require(decoded["activationMode"] == "while-true", "condition changed activation mode")
            if decoded["active"] and self.trigger is None:
                require(decoded["triggered"] and decoded["truth"] and decoded["targetKind"] == 2
                        and decoded["targetSlot"] == target["handle"]["slot"], "trigger lacks adjacent current target")
                self.capture = self._capture(sample,actor,target)
                prior = self._actor(self.latest,"snorlax")["engineObject"]
                current = target["engineObject"]
                require(max(abs(current[k]-prior[k]) for k in ("x","y")) == 1, "trigger target was not adjacent")
                self.trigger = deepcopy(decoded)
            elif self.trigger and not decoded["active"] and not decoded["truth"]:
                self.ended = deepcopy(decoded)
            if decoded["active"] and decoded["truth"] and decoded["targetKind"] == 2 \
                    and decoded["targetSlot"] == target["handle"]["slot"] \
                    and all(actor["engineObject"][k] == target["engineObject"][k] for k in ("x","y")):
                same_tile_truth = decoded
        starts = [e for e in native if e.get("event") == "MOTION_STARTED" and e.get("valueA") == 2]
        if self.trigger and self.start is None and starts:
            self._profile(sample,actor,cache)
            require(actor["matchedLayerMask"] & ATTACK_MASK,"outward Hop lacks Basic attack")
            self.capture=self._capture(sample,actor,target)
            self.start = self._admission(sample,actor,native,starts,
                [actor["origin"][k] for k in ("x","y")],self.capture["targetPosition"],1)
        elif self.start and self.return_start is None and starts:
            self.return_start = self._admission(sample,actor,native,starts,
                self.start["plan"]["target"],self.start["plan"]["origin"],0)
            delay=self.return_start["frame"]-self.start["frame"]-4
            require((delay==0 if not self.busy_frames else 0<delay<=2
                     and 0<sample["actorFrame"]-self.busy_frames[0]["actorFrame"]<=2)
                    and actor["motionElapsed"]==0
                    and all(self.return_start["plan"][k]==self.start["plan"][k]
                            for k in ("duration","distance","arcHeightQ4","spinSpeed","swayWidth","visibilityPolicy"))
                    and self.return_start["plan"]["startBaseY"]==self.start["plan"]["targetBaseY"]
                    and self.return_start["plan"]["targetBaseY"]==self.start["plan"]["startBaseY"],
                    "return did not start at its required immediate or bounded busy boundary with the saved style")
        pair = self.completed()
        if self.start and len(pair)<2:
            self.motion.observe(sample["frame"],actor,actor["engineObject"])
            self.arc |= self._pose(actor,sample)[2] > self.start["plan"]["startBaseY"]
            pair = self.completed()
            if pair and self.return_start is None:
                self._busy_origin(sample,actor,native)
        if len(pair)==2 and sample["frame"]>pair[1]["finishFrame"] and self.pair_pause is None:
            pause = sample["frame"]-pair[1]["finishFrame"]
            if starts:
                self._admission(sample,actor,native,starts,self.start["plan"]["origin"],
                    [actor["target"][k] for k in ("x","y")],1)
                require(20<=pause<=40,"next outward Hop lacks the full20-to40 frame pair pause")
                self.pair_pause = dict(startFrame=pair[1]["finishFrame"],endFrame=sample["frame"],
                                      frames=pause,nextHop=deepcopy(starts[0]))
            else:
                engine=actor["engineObject"];origin=self.start["plan"]["origin"]
                require(pause<=40 and actor["motionPhase"]=="IDLE" and actor["inputOwnership"]==0
                        and [actor["logical"][k] for k in ("x","y")]==origin
                        and [engine["pos_x"],engine["pos_z"]]==[(v<<16)+32768 for v in origin]
                        and engine["pos_y"]==self.start["plan"]["startBaseY"] and engine.get("unk88_y",0)==0,
                        "pair pause moved, held control or exceeded40 frames")
        if same_tile_truth and pair and self.same_tile_capture is None:
            self.same_tile_capture = dict(frame=sample["frame"],condition=deepcopy(same_tile_truth),
                                          capture=self._capture(sample,actor,target))
        hp = self._hp(sample,"cyndaquil")
        delta, hits = self.previous_hp["hp"]-hp["hp"], hp["hitCount"]-self.previous_hp["hitCount"]
        require(delta in (0,20) and hits == int(delta==20) and hp["maxHp"] == self.before["maxHp"],
                "collision HP did not change by the authored20")
        if hits and self.hit is None:
            require(self.start is not None and hp.get("lastDamage") == 20 and hp.get("immunityFrames",0) >= 59,
                    "HP hit lacks the authored normal Hop and damage guard")
            self.hit = dict(frame=sample["frame"],before=self.previous_hp["hp"],after=hp["hp"],target=deepcopy(target["handle"]))
        self.previous_hp = deepcopy(hp)
        self.frames += 1
        if len(pair)==2 and (self.busy_frames or self.hit is None):
            self.skipped_pairs.append(dict(reason="foreign-reservation" if self.busy_frames else "no-contact",
                capture=deepcopy(self.capture),firstHop=deepcopy(self.start),returnHop=deepcopy(self.return_start),
                completedHops=pair,hit=deepcopy(self.hit),busyFrames=deepcopy(self.busy_frames),immediateClaim=False))
            self.start=self.return_start=self.hit=self.same_tile_capture=None
            self.busy_frames=[];self.motion=MotionRecorder();self.arc=False

    def completed(self):
        if not self.start: return []
        result=[]
        for leg in (self.start,self.return_start):
            if leg is None: continue
            matches=[m for m in self.motion.completed if m["kind"]=="HOP" and m["startFrame"]==leg["frame"] and complete_travel(m)]
            if len(matches)!=1: continue
            m=matches[0]
            actor = self.subjects["snorlax"]["handle"]["value"]
            ordered=[]
            for name,a,b in (("MOTION_STARTED",2,4),("LOGICAL_COMMIT",m["commitAfter"],2),
                             ("MOTION_FINISHED",m["commitAfter"],2),("CONTROL_RETURNED",0,m["commitAfter"])):
                rows=[e["data"] for e in self.events if e.get("kind")=="native" and e["data"].get("actorHandle")==actor
                      and e["data"].get("event")==name and (e["frame"]==m["startFrame"] if name=="MOTION_STARTED"
                            else m["startFrame"]<=e["frame"]<=m["finishFrame"])
                      and e["data"].get("reason")=="OK" and (e["data"].get("valueA"),e["data"].get("valueB"))==(a,b)]
                if len(rows)!=1: break
                ordered.append(rows[0]["sequence"])
            if len(ordered)==4 and ordered==sorted(ordered) and m["target"]==leg["plan"]["target"] \
                    and m["origin"]==leg["plan"]["origin"] and all(s["facing"]==leg["plan"]["facing"] for s in m["samples"]):
                result.append(deepcopy(m))
        return result

    def observe_record(self,row,on_sample=None):
        if self.failures: return self.result()
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase")=="setup", "initial frame is misplaced")
                self._boundary(row["initialSnapshot"],fixture=False)
                self.latest=deepcopy(row["initialSnapshot"]); return self.result()
            require(self.latest is not None,"initial frame is missing")
            if row.get("phase")=="setup":
                require(self.setup_index<len(SETUP_IDS) and row.get("action")==SETUP_IDS[self.setup_index],"setup order differs")
                sample=row["snapshot"];self._boundary(sample)
                if row.get("command")=="bind":
                    name=row["action"].removeprefix("bind-");self.subjects[name]=deepcopy(row["receipt"]);self._actor(sample,name)
                self.latest=deepcopy(sample);self.setup_index+=1;return self.result()
            require(self.setup_index==len(SETUP_IDS) and row.get("phase")=="observe" and self.action_index<len(ACTION_IDS)
                    and row.get("action")==ACTION_IDS[self.action_index],"observation order differs")
            name=ACTION_IDS[self.action_index]
            if name in ("before-contact","after-contact"):
                require(row.get("command")=="player-health.observe", "boundary command differs")
                sample=row["snapshot"];self._boundary(sample)
                require(all(sample.get(k)==self.latest.get(k) for k in ("frame","nativeCycle","actors","pokemonCombat")),"boundary moved")
                if name=="before-contact":
                    passive=self._actor(sample,"passive")
                    followers=[a for a in sample["actors"] if a.get("active") is True and a.get("role")=="FOLLOWER"]
                    require(passive.get("species")==174 and passive.get("role")=="FOLLOWER"
                            and len(followers)==1 and followers[0]["handle"]==passive["handle"],
                            "prepared Igglybuff did not replace the competing Follower")
                    self.initial=deepcopy(sample)
                    self.before=deepcopy(self._hp(sample,"cyndaquil"));self.previous_hp=deepcopy(self.before)
                    require(self.before["hp"]==self.before["maxHp"] and self.before["hitCount"]==0,"target was hurt in excluded setup")
                else:self.after=deepcopy(self._hp(sample,"cyndaquil"));self.terminal=deepcopy(sample)
                self.action_index+=1
            else:
                for sample,events,_ in validate_raw_chunk(row,self.latest):
                    self.observe(sample,events,row.get("profileCache"));self.latest=deepcopy(sample)
                    self.action_frames[self.action_index]+=1
                    if on_sample:on_sample(sample,self.frames)
                limit=WAIT_FRAMES if name=="observe-attack" else TAIL_FRAMES
                require(self.action_frames[self.action_index]<=limit,"normal observation exceeded its bound")
                if name=="observe-attack" and self.stage("landed") or name=="finish-contact" and self.action_frames[self.action_index]==TAIL_FRAMES:
                    self.action_index+=1
        except (ValueError,KeyError,TypeError,StopIteration,IndexError) as error:
            self.failures.append(str(error) or type(error).__name__)
        return self.result()

    def stage(self,name):
        return name=="landed" and bool(self.hit and self.arc and len(self.completed())==2 and self.pair_pause) and not self.failures
    @property
    def ready(self):return self.action_index==len(ACTION_IDS) and self.frames>=MIN_FRAMES and self.stage("landed") and not self.motion.failures
    def finish(self):
        self.failures.extend("motion: "+f["reason"] for f in self.motion.failures)
        if not self.ready and not self.failures:self.failures.append("Basic attack lacks complete current Hop pair/contact/pause proof")
        return self.result()
    def result(self):
        return dict(kind=KIND,requirements=[REQUIREMENT],passed=self.ready,ready=self.ready,closed=self.ready,acceptedProof=False,
            failures=list(self.failures),observedFrames=self.frames,frames=self.frames,observedFrameUnit="completed-game-frame",
            subjects=deepcopy(self.subjects),initial=deepcopy(self.initial),terminal=deepcopy(self.terminal),trigger=deepcopy(self.trigger),
            conditionCapture=deepcopy(self.capture),firstHop=deepcopy(self.start),completedHops=self.completed(),hit=deepcopy(self.hit),
            returnHop=deepcopy(self.return_start),pairPause=deepcopy(self.pair_pause),
            skippedPairs=deepcopy(self.skipped_pairs),busyFrames=deepcopy(self.busy_frames),
            arc=self.arc,conditionEnded=deepcopy(self.ended),sameTileCapture=deepcopy(self.same_tile_capture),
            hpBefore=deepcopy(self.before),hpAfter=deepcopy(self.after))


def contract():
    return {claim:[dict(name=n,operator="eq",type="integer",validator="meaningful-observation",expected=1) for n in names]
            for claim,names in NAMES.items()}


def measurements(replay,record):
    meter=replay.get("measurements",{}).get(KIND,{})
    require(replay.get("passed") is True and replay.get("failures")==[] and meter.get("passed") is True
            and meter.get("ready") is True and meter.get("acceptedProof") is False
            and meter.get("observedFrames",0)>=MIN_FRAMES and meter.get("observedFrames")==replay.get("observedFrames")
            and set(meter.get("subjects",{}))=={s[0] for s in SUBJECTS} and meter.get("conditionCapture")
            and meter.get("firstHop") and meter.get("returnHop") and len(meter.get("completedHops",[]))==2
            and meter.get("pairPause") and meter.get("hit") and meter.get("arc") is True,
            "accepted claims lack native condition, complete Hop pair, pause and real HP loss")
    require(record.get("sessionCleanup")==dict(sessionId=record.get("sessionId"),closed=True,errors=[]),"private session did not close")
    return [dict(claim=c,name=n,value=1,operator="eq",expected=1,passed=True) for c,ns in NAMES.items() for n in ns]


class BasicAttackNegative:
    def __init__(self,fault):
        require(fault in FAULTS,"unknown copied-data control")
        self.fault=fault;self.applied=False
    def mutate(self,row,subjects):
        if row.get("phase")!="observe":return row
        changed=deepcopy(row)
        if self.fault in ("basic:missing-condition","basic:missing-return"):
            event="CONDITIONAL_RESOLVED" if self.fault.endswith("condition") else "CONTROL_RETURNED"
            owner=subjects.get("snorlax",{}).get("handle",{}).get("value")
            old=changed.get("events",[])
            changed["events"]=[e for e in old if not(e.get("kind")=="native" and e.get("data",{}).get("actorHandle")==owner and e["data"].get("event")==event)]
            self.applied|=len(old)!=len(changed["events"])
        for sample in [*changed.get("samples",[]),*([changed["snapshot"]] if "snapshot" in changed else [])]:
            combat=sample.get("pokemonCombat",{})
            if self.fault=="basic:stale-target":
                for owner in combat.get("interactions",{}).get("carriers",[]):
                    for c in owner.get("conditionCaptures",[]):
                        if c.get("conditionId")==CONDITION and c.get("target",{}).get("actor"):
                            c["target"]["actor"]["generation"]+=1;self.applied=True
            elif self.fault=="basic:missing-hit":
                for hp in combat.get("targets",[]):
                    if hp.get("species")==155 and hp.get("hitCount",0):
                        hp.update(hp=hp["maxHp"],currentHp=hp["maxHp"],hitCount=0,lastDamage=0,immunityFrames=0);self.applied=True
        if self.fault=="basic:wrong-hop-time":
            for p in changed.get("profileCache",{}).get("resolvedProfiles",[]):
                raw=bytearray.fromhex(p.get("resultHex",""))
                if len(raw)==216 and raw[72]==1:raw[36]=2;p["resultHex"]=raw.hex();self.applied=True
        return changed


def validate_negative_result(result,fault):
    require(fault in FAULTS and result.get("passed") is False and result.get("failures"),"copied control did not fail "+fault)
    return True
