"""Copied-data sensitivity for Basic attack; these checks do not prove a ROM."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest
from unittest import mock

from tools.overworld import devtools_basic_attack_measurement as basic_measurement

from tools.overworld.devtools_basic_attack_measurement import (
    APPLICATION, ATTACK_MASK, CONDITION, KIND, ACTION_IDS, SETUP_IDS, SUBJECTS, BasicAttackMeasurement,
    BasicAttackNegative, FAULTS, measurements, validate_negative_result,
)
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_walk_matrix_observer import decode_motion

ROOT = Path(__file__).resolve().parents[2]
SOURCE = dict(contractVersion=1,romSha256="a"*64,overlaySha256="b"*64,profileSha256="c"*64)
# These are copied host data, not the disabled application's current ROM bit.
# Both the copied records and their meter use this isolated, enabled fixture.
APPLICATION = 24
ATTACK_MASK = 1 << APPLICATION


def snapshot(frame,pause_frames=24):
    # First pair 10..18; pause24; next outward admission42, followed by its pair.
    next_out=18+pause_frames
    starts=[10,14,next_out,next_out+4]
    leg=max((i for i,start in enumerate(starts) if frame>=start),default=-1)
    leg_start=starts[leg] if leg>=0 else frame
    active=leg>=0 and frame<leg_start+4
    actors=[];hp_rows=[]
    for name,species,slot,max_hp in (("snorlax",143,0,220),("cyndaquil",155,1,120)):
        owner=name=="snorlax"
        outward=leg in (0,2)
        origin,target=(([595,396],[596,396]) if outward else ([596,396],[595,396])) if owner and leg>=0 else ([595+slot,396],[595+slot,396])
        elapsed=min(frame-leg_start,4) if owner and leg>=0 else 0
        moving=owner and active
        x=(target if elapsed>=2 else origin)[0] if owner else 596
        direction=3 if outward else 2
        commit=sum(frame>=f for f in (14,18,next_out+4,next_out+8)) if owner else 0
        handle=dict(value=65536+slot,slot=slot,generation=1,fieldEpoch=1,mapGeneration=1,encounterGeneration=1)
        actor=dict(handle=handle,subjectIdentity=100+slot,species=species,role="WILD",form=0,level=50,
            active=True,identityVerified=True,presentationAttached=True,authorityGeneration=1,
            engineAnchorGeneration=1,presentationGeneration=1,engineIdentity=dict(pointer=0x02110000+slot*512),
            sourceIdentity=dict(personality=100+slot),inputOwnership=0,reservationId=41+leg if moving else 0,
            behaviorFingerprint=901+slot,matchedLayerMask=ATTACK_MASK if owner and frame>=10 else 0,
            logical=dict(x=x,y=396),origin=dict(x=origin[0],y=origin[1]),target=dict(x=target[0],y=target[1]),
            motionKind="HOP" if moving else "NONE",motionPhase="MOVING" if moving else "IDLE",
            motionElapsed=elapsed,motionDuration=4 if owner and leg>=0 else 0,commitSequence=commit,
            engineObject=dict(pos_x=(origin[0]<<16)+32768+((target[0]-origin[0])*65536*elapsed//4 if owner else 0),
                pos_z=(396<<16)+32768,pos_y=65536,face_y=0,
                unk88_y=16*((((4*elapsed*(4-elapsed))//4)<<12)//4) if owner else 0,
                x=x,y=396,facing=direction if owner and leg>=0 else 0,movement_cmd=255,flags=1))
        actors.append(actor)
        raw=bytearray(52)
        if owner and leg>=0:
            struct.pack_into("<HBBHH4h2iHH",raw,0,1,2,direction,1,0,*origin,*target,65536,65536,4,41+leg)
            raw[28:38]=bytes((direction,1,16,0,0,0,0,1,int(outward),0))
            struct.pack_into("<4H4B",raw,40,elapsed,0,int(elapsed>=2),commit,2 if moving else 0,0,int(not moving),0)
        hit=not owner and frame>=12
        hp_rows.append(dict(handle=deepcopy(handle),personality=100+slot,species=species,role="WILD",
            hp=max_hp-20*hit,currentHp=max_hp-20*hit,maxHp=max_hp,hpSource="wild-resident",hitCount=int(hit),
            lastDamage=20 if hit else 0,immunityFrames=max(0,60-(frame-12)) if hit else 0,motion=decode_motion(bytes(raw))))
    passive=deepcopy(actors[1]);passive.update(species=174,role="FOLLOWER",subjectIdentity=102,
        handle=dict(value=65538,slot=2,generation=1,fieldEpoch=1,mapGeneration=1,encounterGeneration=1),
        engineIdentity=dict(pointer=0x02110400),sourceIdentity=dict(personality=102),behaviorFingerprint=903,
        logical=dict(x=594,y=400),origin=dict(x=594,y=400),target=dict(x=594,y=400))
    passive["engineObject"].update(pos_x=(594<<16)+32768,pos_z=(400<<16)+32768,x=594,y=400)
    actors.append(passive)
    prepared=bytearray(52);prepared[:12]=raw_handle(actors[0]["handle"])
    struct.pack_into("<I",prepared,12,0x02270000);prepared[16]=13;struct.pack_into("<BBH",prepared,48,1,1,1)
    c=dict(preparedIndex=0,catalogIndex=13,conditionId=CONDITION,application=APPLICATION,
        activationMode=0,durationFrames=0,cooldownFrames=0,target=dict(kind="ACTOR",actor=deepcopy(actors[1]["handle"])),
        targetCurrent=True,targetValid=True,targetPosition=[596,396],activeApplicationMask=ATTACK_MASK,
        statesPointer=0x02270000,preparedRawHex=prepared.hex(),rawHex=struct.pack("<II3H2B",0,0,1,1,1,2,1).hex())
    return dict(frame=frame,nativeCycle=frame+1000,actorFrame=frame,romSha256=SOURCE["romSha256"],
        observationBoundary="main-task-queue-completion",fieldAvailable=True,context=dict(mapId=33,fieldEpoch=1,mapGeneration=1),
        fieldControl=dict(taskPointer=0,fieldPointer=0x02140000),actors=actors,player=dict(x=594,y=399),party=[],
        nativeObservation=dict(profileFingerprints=[901,902]),pokemonCombat=dict(schemaVersion=1,available=True,
            frame=frame,nativeCycle=frame+1000,identity=dict(romSha256=SOURCE["romSha256"],overlaySha256=SOURCE["overlaySha256"]),
            targets=hp_rows,interactions=dict(schemaVersion=1,available=True,frame=frame,nativeCycle=frame+1000,
                observationBoundary="main-task-queue-completion",fieldSystem=0x02140000,identity=dict(romSha256=SOURCE["romSha256"]),
                carriers=[dict(handle=deepcopy(actors[0]["handle"]),role="WILD",available=True,conditionCaptures=[c])])) )


def events(s,pause_frames=24):
    owner=s["actors"][0];frame=s["frame"];result=[]
    def add(name,a,b,reason=0):
        result.append(dict(frame=frame,kind="native",data=dict(sequence=frame*10+len(result),actorFrame=frame,
            actorHandle=owner["handle"]["value"],actor={k:v for k,v in owner["handle"].items() if k!="value"},
            event=name,reason="OK",reasonId=reason,valueA=a,valueB=b)))
    next_out=18+pause_frames
    if frame in (10,next_out):
        add("CONDITIONAL_RESOLVED",(1<<16)|CONDITION,0,APPLICATION|(APPLICATION<<5)|(2<<10)|((7 if frame==10 else 6)<<12))
        add("PLAN_ACCEPTED",(596<<16)|396,4);add("MOTION_STARTED",2,4)
    if frame in (14,next_out+4):
        commit=1 if frame==14 else 3
        add("LOGICAL_COMMIT",commit,2);add("MOTION_FINISHED",commit,2);add("CONTROL_RETURNED",0,commit)
        add("CONDITIONAL_RESOLVED",(1<<16)|CONDITION,0,APPLICATION|(APPLICATION<<5)|(2<<10)|(6<<12))
        add("PLAN_ACCEPTED",(595<<16)|396,4);add("MOTION_STARTED",2,4)
    if frame in (18,next_out+8):
        commit=2 if frame==18 else 4
        add("LOGICAL_COMMIT",commit,2);add("MOTION_FINISHED",commit,2);add("CONTROL_RETURNED",0,commit)
    return result


def cache():
    raw=bytearray(216);raw[0]=3;raw[12:14]=bytes((2,10));struct.pack_into("<HH",raw,32,16,1023)
    raw[36]=4;raw[42]=2;raw[65]=0;raw[72:76]=bytes((1,1,20,0));raw[79]=4
    return dict(frame=100,nativeCycle=1100,resolvedProfiles=[dict(resolved=True,fingerprint=901,
        sourceSha256=SOURCE["profileSha256"],resultHex=raw.hex())])


def rows(pause_frames=24):
    result=[dict(phase="setup",initialSnapshot=snapshot(0))]
    for i,name in enumerate(SETUP_IDS):
        s=snapshot(i+1);op="bind" if name.startswith("bind-") else "teleport" if i==0 else "party" if name=="prepare-passive" else "spawn"
        receipt=select_current_actor(s,s["actors"][{"bind-snorlax":0,"bind-cyndaquil":1,"bind-passive":2}[name]]) if op=="bind" else {}
        result.append(dict(phase="setup",action=name,command=op,snapshot=s,receipt=receipt))
    result.append(dict(phase="observe",action="before-contact",command="player-health.observe",snapshot=snapshot(len(SETUP_IDS)),receipt={}))
    previous=len(SETUP_IDS)
    next_out=18+pause_frames
    for name,end in (("observe-attack",next_out),("finish-contact",next_out+16)):
        samples=[snapshot(f,pause_frames) for f in range(previous+1,end+1)]
        result.append(dict(phase="observe",action=name,command="step",samples=samples,events=[e for s in samples for e in events(s,pause_frames)],
            completedGameFrames=len(samples),nativeCycles=len(samples),observedFieldFrames=len(samples),
            cycleIntervals=[dict(cpuNs=1000,wallNs=2000,completedGameFrame=s["frame"]) for s in samples],profileCache=cache()))
        previous=end
    result.append(dict(phase="observe",action="after-contact",command="player-health.observe",snapshot=snapshot(next_out+16,pause_frames),receipt={}))
    return result


def busy_rows(delay=1,retry_count=1):
    """One fully witnessed busy pair, then a clear pair with a second real hit."""
    def hop(s,slot,start,origin,target,facing,commit_before,commit_policy):
        elapsed=min(s["frame"]-start,4);moving=elapsed<4;actor=s["actors"][slot]
        x=(target if elapsed>=2 else origin)[0]
        actor.update(origin=dict(x=origin[0],y=origin[1]),target=dict(x=target[0],y=target[1]),
            logical=dict(x=x,y=396),motionKind="HOP" if moving else "NONE",
            motionPhase="MOVING" if moving else "IDLE",motionElapsed=elapsed,motionDuration=4,
            commitSequence=commit_before+int(not moving),reservationId=90+slot if moving else 0)
        actor["engineObject"].update(x=x,y=396,facing=facing,
            pos_x=(origin[0]<<16)+32768+(target[0]-origin[0])*65536*elapsed//4,
            pos_z=(396<<16)+32768,pos_y=65536,unk88_y=16*((((4*elapsed*(4-elapsed))//4)<<12)//4))
        raw=bytearray(52)
        struct.pack_into("<HBBHH4h2iHH",raw,0,1,2,facing,1,0,*origin,*target,65536,65536,4,90+slot)
        raw[28:38]=bytes((facing,1,16,0,0,0,0,1,commit_policy,0))
        struct.pack_into("<4H4B",raw,40,elapsed,0,int(elapsed>=2),actor["commitSequence"],2 if moving else 0,0,int(not moving),0)
        s["pokemonCombat"]["targets"][slot]["motion"]=decode_motion(bytes(raw))
    def sample(frame):
        s=snapshot(frame if frame<80 else frame-70)
        s.update(frame=frame,nativeCycle=frame+1000,actorFrame=frame)
        for section in (s["pokemonCombat"],s["pokemonCombat"]["interactions"]):
            section.update(frame=frame,nativeCycle=frame+1000)
        if frame>=80:
            s["actors"][0]["commitSequence"]+=2
            motion=s["pokemonCombat"]["targets"][0]["motion"]
            raw=bytearray.fromhex(motion["rawHex"]);struct.pack_into("<H",raw,46,motion["commitSequence"]+2)
            s["pokemonCombat"]["targets"][0]["motion"]=decode_motion(bytes(raw))
            hop(s,1,14+delay,[595,396],[596,396],3,1,0)
        if 10<=frame<80:
            if frame<14+delay:hop(s,0,10,[595,396],[596,396],3,0,1)
            else:hop(s,0,14+delay,[596,396],[595,396],2,1,0)
            if frame>=10+delay:
                if frame<14+delay:hop(s,1,10+delay,[596,396],[595,396],2,0,1)
                else:hop(s,1,14+delay,[595,396],[596,396],3,1,0)
        if frame>=12:
            victim=s["pokemonCombat"]["targets"][1];hits=1+int(frame>=82)
            victim.update(hp=120-20*hits,currentHp=120-20*hits,hitCount=hits,lastDamage=20,
                          immunityFrames=max(0,60-(frame-(82 if hits==2 else 12))))
        s["pokemonCombat"]["interactions"]["carriers"][0]["conditionCaptures"][0]["targetPosition"]=[s["actors"][1]["engineObject"][k] for k in ("x","y")]
        return s
    def native(s):
        f=s["frame"]
        if f>=80:
            result=events(snapshot(f-70))
        elif f==10:result=events(snapshot(10))
        elif f==14:result=[e for e in events(snapshot(14)) if e["data"]["event"] in ("LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED")]
        elif f==18+delay:result=events(snapshot(18))
        else:result=[]
        if 14<=f<14+delay:
            for _ in range(retry_count):
                for name,reason,a,b in (("INTENT_CREATED","OK",2,1),("CANDIDATE_REJECTED","REJECTED_RESERVED",0,1)):
                    result.append(dict(frame=f,kind="native",data=dict(actorHandle=s["actors"][0]["handle"]["value"],
                        actor={k:v for k,v in s["actors"][0]["handle"].items() if k!="value"},
                        event=name,reason=reason,reasonId=6 if reason!="OK" else 0,valueA=a,valueB=b)))
        if f==14+delay:
            result += [e for e in events(snapshot(14)) if e["data"]["event"] in ("PLAN_ACCEPTED","MOTION_STARTED")]
        for i,e in enumerate(result):
            e["frame"]=f;e["data"].update(sequence=f*10+i,actorFrame=f)
            if f>=80:
                if e["data"]["event"] in ("LOGICAL_COMMIT","MOTION_FINISHED"):e["data"]["valueA"]+=2
                elif e["data"]["event"]=="CONTROL_RETURNED":e["data"]["valueB"]+=2
        return result
    result=rows()
    # Keep the ordinary setup unchanged and replace only copied observations.
    result=result[:len(SETUP_IDS)+2]
    previous=len(SETUP_IDS)
    for name,end in (("observe-attack",112),("finish-contact",128)):
        samples=[sample(f) for f in range(previous+1,end+1)]
        result.append(dict(phase="observe",action=name,command="step",samples=samples,events=[e for s in samples for e in native(s)],
            completedGameFrames=len(samples),nativeCycles=len(samples),observedFieldFrames=len(samples),
            cycleIntervals=[dict(cpuNs=1000,wallNs=2000,completedGameFrame=s["frame"]) for s in samples],
            profileCache=dict(cache(),frame=200,nativeCycle=1200)))
        previous=end
    result.append(dict(phase="observe",action="after-contact",command="player-health.observe",snapshot=sample(128),receipt={}))
    return result


def replay(data):
    meter=BasicAttackMeasurement(SOURCE)
    for row in data:meter.observe_record(row)
    return meter.finish()


class BasicAttackChecks(unittest.TestCase):
    def setUp(self):
        for name, value in (("APPLICATION", APPLICATION), ("ATTACK_MASK", ATTACK_MASK)):
            patch = mock.patch.object(basic_measurement, name, value)
            patch.start()
            self.addCleanup(patch.stop)
    def test_complete_current_chain(self):
        result=replay(rows());self.assertTrue(result["passed"],result["failures"])
        self.assertEqual(result["firstHop"]["plan"]["target"],[596,396])
        self.assertEqual(result["firstHop"]["plan"]["duration"],4)
        self.assertEqual([s["elapsed"] for s in result["completedHops"][0]["samples"]],[0,1,2,3])
        self.assertEqual(result["completedHops"][0]["travelEnd"]["elapsed"],4)
        self.assertEqual(result["sameTileCapture"]["frame"],14)
        self.assertEqual(len(result["completedHops"]),2)
        self.assertEqual(result["returnHop"]["frame"],14)
        self.assertEqual(result["returnHop"]["plan"]["target"],[595,396])
        self.assertEqual([s["elapsed"] for s in result["completedHops"][1]["samples"]],[0,1,2,3])
        self.assertEqual(result["completedHops"][1]["travelEnd"]["elapsed"],4)
        self.assertEqual([s["facing"] for s in result["completedHops"][0]["samples"]],[3]*4)
        self.assertEqual([s["facing"] for s in result["completedHops"][1]["samples"]],[2]*4)
        self.assertEqual(result["pairPause"]["frames"],24)
        self.assertEqual(result["hit"]["before"]-result["hit"]["after"],20)
        envelope=dict(passed=True,failures=[],observedFrames=result["observedFrames"],measurements={KIND:result})
        self.assertEqual(len(measurements(envelope,dict(sessionId="private",sessionCleanup=dict(sessionId="private",closed=True,errors=[])))),7)
    def test_copied_faults_are_red(self):
        for fault in FAULTS:
            control=BasicAttackNegative(fault);data=rows();subjects={n:select_current_actor(snapshot(len(SETUP_IDS)),snapshot(len(SETUP_IDS))["actors"][i]) for i,(n,_,_,_) in enumerate(SUBJECTS)}
            result=replay([control.mutate(r,subjects) for r in data])
            with self.subTest(fault=fault):
                self.assertTrue(control.applied);self.assertFalse(result["passed"]);validate_negative_result(result,fault)
    def test_missing_native_frame_is_red(self):
        data=rows();data[len(SETUP_IDS)+2]["samples"].pop(1)
        self.assertFalse(replay(data)["passed"])
    def test_wrong_hop_destination_is_red(self):
        data=rows();data[len(SETUP_IDS)+2]["samples"][1]["actors"][0]["target"]["x"]=594
        self.assertFalse(replay(data)["passed"])
    def test_missing_endpoint_cache_is_red(self):
        data=rows()
        for row in data:row.pop("profileCache",None)
        result=replay(data);self.assertFalse(result["passed"])
        self.assertIn("profile lacks a coherent native cache",result["failures"][0])
    def test_old_zero_impact_speed_is_red(self):
        data=rows()
        for row in data:
            for profile in row.get("profileCache",{}).get("resolvedProfiles",[]):
                raw=bytearray.fromhex(profile["resultHex"]);raw[73]=0;profile["resultHex"]=raw.hex()
        result=replay(data);self.assertFalse(result["passed"])
        self.assertIn("impact speed1",result["failures"][0])
    def test_pair_pause_exact_bounds(self):
        for pause in (20,40):
            with self.subTest(pause=pause):
                result=replay(rows(pause));self.assertTrue(result["passed"],result["failures"])
                self.assertEqual(result["pairPause"]["frames"],pause)
        for pause in (19,41):
            with self.subTest(pause=pause):
                result=replay(rows(pause));self.assertFalse(result["passed"])
                self.assertIn("20-to40",result["failures"][0])
    def test_return_and_face_profile_options_are_required(self):
        for offset,value in ((42,0),(65,64)):
            with self.subTest(offset=offset):
                data=rows()
                for row in data:
                    for profile in row.get("profileCache",{}).get("resolvedProfiles",[]):
                        raw=bytearray.fromhex(profile["resultHex"]);raw[offset]=value;profile["resultHex"]=raw.hex()
                result=replay(data);self.assertFalse(result["passed"])
                self.assertIn("return-after-move, Face movement",result["failures"][0])
    def test_return_has_exact_origin_facing_and_no_gap(self):
        for fault in ("target","facing","gap","accepted"):
            with self.subTest(fault=fault):
                data=rows();row=data[len(SETUP_IDS)+2]
                sample=next(s for s in row["samples"] if s["frame"]==14)
                if fault=="target":
                    raw=bytearray.fromhex(sample["pokemonCombat"]["targets"][0]["motion"]["rawHex"])
                    struct.pack_into("<h",raw,12,594)
                    sample["pokemonCombat"]["targets"][0]["motion"]=decode_motion(bytes(raw))
                elif fault=="facing":
                    next(s for s in row["samples"] if s["frame"]==15)["actors"][0]["engineObject"]["facing"]=3
                elif fault=="gap":
                    row["events"]=[e for e in row["events"] if not(e["frame"]==14 and e["data"]["event"]=="MOTION_STARTED")]
                else:
                    row["events"]=[e for e in row["events"] if not(e["frame"]==14 and e["data"]["event"]=="PLAN_ACCEPTED")]
                result=replay(data);self.assertFalse(result["passed"],result)
    def test_busy_pair_is_retained_without_immediate_credit_then_later_clear_pair_passes(self):
        for delay in (1,2):
            with self.subTest(delay=delay):
                result=replay(busy_rows(delay));self.assertTrue(result["passed"],result["failures"])
                skipped=result["skippedPairs"];self.assertEqual(len(skipped),1)
                self.assertEqual(skipped[0]["reason"],"foreign-reservation")
                self.assertFalse(skipped[0]["immediateClaim"])
                self.assertEqual(skipped[0]["returnHop"]["frame"],14+delay)
                self.assertEqual(len(skipped[0]["completedHops"]),2)
                self.assertEqual(len(skipped[0]["busyFrames"]),delay)
                witness=skipped[0]["busyFrames"][0]["witnesses"][0]
                self.assertEqual(witness["subject"]["handle"]["value"],65537)
                self.assertEqual(witness["motion"]["plan"]["target"],[595,396])
                self.assertEqual(result["firstHop"]["frame"],80)
                self.assertEqual(result["returnHop"]["frame"],84)
                self.assertEqual(result["hit"]["before"]-result["hit"]["after"],20)
                self.assertEqual(result["pairPause"]["frames"],24)
    def test_busy_retry_needs_current_foreign_owner_distinct_frames_and_a_real_return(self):
        for fault in ("stale","target","not-moving","repeated","late","no-return"):
            with self.subTest(fault=fault):
                data=busy_rows(3 if fault=="late" else 1,3 if fault=="repeated" else 1)
                row=data[len(SETUP_IDS)+2];s=next(s for s in row["samples"] if s["frame"]==14)
                if fault=="stale":s["actors"][1]["identityVerified"]=False
                elif fault=="target":s["actors"][1]["target"]["x"]=594
                elif fault=="not-moving":s["actors"][1]["motionPhase"]="IDLE"
                elif fault=="no-return":
                    row["events"]=[e for e in row["events"] if not(e["frame"]==15 and e["data"]["event"]=="MOTION_STARTED")]
                result=replay(data);self.assertFalse(result["passed"],result)
    def test_competing_follower_is_red(self):
        data=rows();before=data[len(SETUP_IDS)+1]["snapshot"]
        competing=deepcopy(before["actors"][2]);competing.update(species=56,handle=dict(
            value=65539,slot=3,generation=1,fieldEpoch=1,mapGeneration=1,encounterGeneration=1))
        before["actors"].append(competing)
        data[len(SETUP_IDS)]["snapshot"]["actors"].append(deepcopy(competing))
        result=replay(data);self.assertFalse(result["passed"])
        self.assertIn("prepared Igglybuff did not replace the competing Follower",result["failures"][0])
    def test_recipe_and_dispatch(self):
        test=validate_test(json.loads((ROOT/"tests/overworld/test-recipes/profile.basic-attack.json").read_text()))
        e=TestEvaluator(test);e.install_measurements({KIND:SOURCE});self.assertIsInstance(e.measurements[KIND],BasicAttackMeasurement)

if __name__=="__main__":unittest.main()
