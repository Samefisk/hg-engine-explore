"""Copied-data checks for one follower Ram witness; these are not ROM proof."""
from copy import deepcopy
import struct
import unittest

from tools.overworld.devtools_follower_ram_measurement import (
    ACTION_IDS, APPLICATION, CONDITION, KIND, RAM_MASK, SETUP_IDS, FollowerRamMeasurement,
)
from tools.overworld.devtools_follower_ram_proof import (
    FAULTS, FollowerRamNegative, measurements, validate_negative_result,
)
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion

SOURCE = dict(contractVersion=1, romSha256="a"*64, overlaySha256="b"*64, profileSha256="c"*64)
START, FIRST_END, SECOND_START, HIT, LAND = 52, 56, 57, 61, 84


def snapshot(frame):
    active = START <= frame <= HIT
    actors = []; hp_rows = []
    for name, species, role, slot, max_hp in (("onix",95,"FOLLOWER",7,107), ("snorlax",143,"WILD",0,224)):
        handle = dict(value=65536+slot, slot=slot, generation=1, fieldEpoch=1, mapGeneration=1, encounterGeneration=1)
        x, z = (593,398) if name == "onix" and frame < START else (594,398) if name == "onix" else (594,394)
        kind = "NONE"; phase = "IDLE"; elapsed = duration = 0; origin = target = [x,z]; reservation = 0
        if name == "onix" and frame >= START:
            z = 398 if frame < FIRST_END else 397 if frame < HIT else 396
            if START <= frame <= FIRST_END or SECOND_START <= frame <= HIT:
                start, origin_z = (START,398) if frame <= FIRST_END else (SECOND_START,397)
                elapsed = frame-start; duration = 4; origin=[594,origin_z]; target=[594,origin_z-1]
                kind, phase, reservation = ("WALK","MOVING",41) if elapsed < duration else ("NONE","IDLE",0)
        if name == "snorlax" and frame >= HIT:
            elapsed=min(frame-HIT,23); duration=23; origin=[594,394]; target=[594,391]
            z=391 if elapsed==23 else 394
            kind,phase,reservation=("HOP","MOVING",42) if elapsed < duration else ("NONE","IDLE",0)
        base=65536
        progress = ((target[1]-origin[1])*65536*elapsed//duration) if duration else 0
        pos_z=(origin[1]<<16)+32768+progress
        arc=4*65536*elapsed*(duration-elapsed)//(duration*duration) if name=="snorlax" and duration else 0
        actor=dict(handle=handle,subjectIdentity=100+slot,species=species,role=role,form=0,level=50,
            active=True,identityVerified=True,presentationAttached=True,authorityGeneration=1,
            engineAnchorGeneration=1,presentationGeneration=1,engineIdentity=dict(pointer=0x02110000+slot*512),
            sourceIdentity=dict(personality=100+slot),inputOwnership=0,reservationId=reservation,
            behaviorFingerprint=901 if name=="onix" else 902,matchedLayerMask=RAM_MASK if name=="onix" and active else 0,
            logical=dict(x=x,y=z),origin=dict(x=origin[0],y=origin[1]),target=dict(x=target[0],y=target[1]),
            motionKind=kind,motionPhase=phase,motionElapsed=elapsed,motionDuration=duration,
            commitSequence=int(frame>=FIRST_END)+int(frame>=HIT) if name=="onix" else int(frame>=LAND),
            engineObject=dict(pos_x=(x<<16)+32768,pos_z=pos_z,pos_y=base,face_y=0,unk88_y=arc,
                              x=x,y=z,facing=0,movement_cmd=255,flags=1))
        actors.append(actor)
        hit=name=="snorlax" and frame>=HIT
        motion=bytearray(52)
        if duration:
            struct.pack_into("<HBBHH4h2iHH",motion,0,1,2 if name=="snorlax" else 1,0,1,0,
                origin[0],origin[1],target[0],target[1],base,base,duration,42 if name=="snorlax" else 41)
            motion[28:38]=bytes((0,3 if name=="snorlax" else 1,16 if name=="snorlax" else 0,0,0,0,0,1,int(name=="snorlax"),int(name=="snorlax")))
            struct.pack_into("<4H4B",motion,40,elapsed,0,int(elapsed==duration),actor["commitSequence"],
                             2 if elapsed<duration else 0,0,int(elapsed==duration),0)
        hp_rows.append(dict(handle=deepcopy(handle),personality=100+slot,species=species,role=role,
            hp=max_hp-33*hit,currentHp=max_hp-33*hit,maxHp=max_hp,hpSource="party" if slot==7 else "wild-resident",
            hpMirrorMatches=True,hitCount=int(hit),lastDamage=33 if hit else 0,
            immunityFrames=max(0,60-(frame-HIT)) if hit else 0,knockbackPending=0,
            knockbackOptions=78 if hit else 0,motion=decode_motion(bytes(motion))))
    prepared=bytearray(52);prepared[:12]=raw_handle(actors[0]["handle"])
    struct.pack_into("<I",prepared,12,0x02270000);prepared[16]=12
    struct.pack_into("<BBH",prepared,48,1,1,1)
    capture=dict(preparedIndex=0,catalogIndex=12,conditionId=CONDITION,application=APPLICATION,
        activationMode=2,durationFrames=0,cooldownFrames=100,activeUntil=0,cooldownUntil=0,flags=11,
        target=dict(kind="ACTOR",actor=deepcopy(actors[1]["handle"])),targetCurrent=True,targetValid=True,
        targetPosition=[actors[1]["logical"][k] for k in ("x","y")],activeApplicationMask=RAM_MASK,
        preparedPointer=0x02250000+7*52,statesPointer=0x02270000,preparedRawHex=prepared.hex(),
        rawHex=struct.pack("<II3H2B",0,0,0,1,1,2,11).hex())
    return dict(frame=frame,nativeCycle=frame+1000,actorFrame=frame,romSha256=SOURCE["romSha256"],
        observationBoundary="main-task-queue-completion",fieldAvailable=True,
        context=dict(mapId=33,fieldEpoch=1,mapGeneration=1),fieldControl=dict(taskPointer=0,fieldPointer=0x02140000),
        player=dict(x=595 if 49<=frame<69 else 594 if frame<85 else 593,y=399,facing=0),
        actors=actors,party=[dict(personality=107,hp=107,maxHp=107)],
        nativeObservation=dict(profileFingerprints=[901,902]),pokemonCombat=dict(schemaVersion=1,available=True,
            frame=frame,nativeCycle=frame+1000,identity=dict(romSha256=SOURCE["romSha256"],overlaySha256=SOURCE["overlaySha256"]),
            targets=hp_rows,interactions=dict(schemaVersion=1,available=True,frame=frame,nativeCycle=frame+1000,
                observationBoundary="main-task-queue-completion",fieldSystem=0x02140000,
                identity=dict(romSha256=SOURCE["romSha256"]),carriers=[dict(handle=deepcopy(actors[0]["handle"]),
                    role="FOLLOWER",available=True,bindings={},conditionCaptures=[capture])])))


def events(sample):
    result=[]
    def add(actor,name,a,b,reason=0):
        result.append(dict(frame=sample["frame"],kind="native",data=dict(sequence=sample["frame"]*10+len(result),
            actorFrame=sample["actorFrame"],actorHandle=actor["handle"]["value"],
            actor={k:v for k,v in actor["handle"].items() if k!="value"},event=name,reason="OK",reasonId=reason,valueA=a,valueB=b)))
    onix,snorlax=sample["actors"];frame=sample["frame"]
    if frame==START:
        add(onix,"CONDITIONAL_RESOLVED",(1<<31)|CONDITION,0,APPLICATION|(APPLICATION<<5)|(2<<10)|(7<<12))
    if frame in (START,SECOND_START):add(onix,"MOTION_STARTED",1,4)
    if frame in (FIRST_END,HIT):
        commit=onix["commitSequence"]
        for name,a,b in (("LOGICAL_COMMIT",commit,1),("MOTION_FINISHED",commit,1),("CONTROL_RETURNED",0,commit)):
            add(onix,name,a,b)
    if frame==HIT:
        add(snorlax,"PLAN_ACCEPTED",(594<<16)|391,23);add(snorlax,"MOTION_STARTED",2,23)
    if frame==LAND:
        for name,a,b in (("LOGICAL_COMMIT",1,2),("MOTION_FINISHED",1,2),("CONTROL_RETURNED",0,1)):
            add(snorlax,name,a,b)
    return result


def raw(action,sample,phase="observe"):
    data=bytearray(216);data[72:75]=bytes((1,32,33));data[79]=78
    return dict(phase=phase,action=action,samples=[sample],completedGameFrames=1,observedFieldFrames=1,nativeCycles=1,
        cycleIntervals=[dict(completedGameFrame=sample["frame"],cpuNs=1,wallNs=1)],events=events(sample),
        profileCache=dict(frame=sample["frame"],nativeCycle=sample["nativeCycle"],resolvedProfiles=[dict(
            resolved=True,fingerprint=901,sourceSha256=SOURCE["profileSha256"],appliedOverrides=RAM_MASK,resultHex=data.hex())]))


def health(action,sample):
    return dict(phase="observe",action=action,command="player-health.observe",snapshot=sample,
        receipt=dict(playerHealth=dict(frame=sample["frame"],hp=100,savedHp=100,maxHp=100,acceptedHits=0,
                                      recoveryPending=False,identity=dict(overlaySha256=SOURCE["overlaySha256"]))))


def records():
    rows=[dict(phase="setup",initialSnapshot=snapshot(32))];frame=32
    for name in SETUP_IDS:
        if name=="settle-fixture":
            for frame in range(33,34):rows.append(raw(name,snapshot(frame),"setup"))
        else:
            sample=snapshot(frame);receipt={};command="bind" if name.startswith("bind-") else "party" if name=="prepare-onix" else "teleport" if name=="charge-tile" else "spawn"
            if command=="bind":receipt=select_current_actor(sample,sample["actors"][0 if name=="bind-onix" else 1])
            rows.append(dict(phase="setup",action=name,command=command,snapshot=sample,receipt=receipt))
    rows.append(health("before-contact",snapshot(33)))
    for frame in range(34,50):rows.append(raw("enter-line",snapshot(frame)))
    for frame in range(50,54):rows.append(raw("capture-target",snapshot(frame)))
    for frame in range(54,86):rows.append(raw("retreat-player",snapshot(frame)))
    rows.append(raw("observe-charge",snapshot(86)))
    for frame in range(87,103):rows.append(raw("finish-knockback",snapshot(frame)))
    rows.append(health("after-contact",snapshot(102)));return rows


def replay(fault=None, rows=None):
    meter=FollowerRamMeasurement(SOURCE);negative=FollowerRamNegative(fault) if fault else None
    for row in records() if rows is None else rows:
        meter.observe_record(negative.mutate(row,meter.subjects) if negative else row)
        if meter.failures:break
    result=meter.finish()
    return dict(passed=result["passed"],failures=result["failures"],observedFrames=meter.frames,measurements={KIND:result}),negative


class FollowerRamTest(unittest.TestCase):
    def test_real_hit_and_shared_jump_have_exact_claims(self):
        result,_=replay();self.assertTrue(result["passed"],result["failures"])
        meter=result["measurements"][KIND]
        self.assertEqual(meter["firstWalk"]["targetPosition"],[594,394])
        self.assertEqual(meter["hit"]["hpBefore"]-meter["hit"]["hpAfter"],33)
        self.assertEqual(meter["jump"]["plan"]["duration"],23)
        self.assertEqual(len(measurements(result,dict(sessionId="host",sessionCleanup=dict(sessionId="host",closed=True,errors=[])))),8)

    def test_each_copied_fault_removes_required_meaning(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                result,negative=replay(fault);self.assertTrue(negative.applied)
                self.assertTrue(validate_negative_result(result,fault),result)

    def test_wrong_west_charge_rejects_current_north_target(self):
        rows=records();sample=next(r["samples"][0] for r in rows if r.get("samples") and r["samples"][0]["frame"]==START)
        actor=sample["actors"][0];actor["target"]=dict(x=593,y=398)
        result,_=replay(rows=rows)
        self.assertFalse(result["passed"])
        self.assertIn("first Walk did not move toward",str(result["failures"]))

    def test_captured_engine_tile_controls_heading_while_public_tile_lags(self):
        rows=records()
        sample=next(r["samples"][0] for r in rows if r.get("samples") and r["samples"][0]["frame"]==START)
        sample["actors"][1]["logical"]["x"]=595
        result,_=replay(rows=rows)
        self.assertTrue(result["passed"],result["failures"])
        self.assertEqual(result["measurements"][KIND]["firstWalk"]["targetPosition"],[594,394])

    def test_missing_completed_frame_and_changed_role_fail(self):
        for fault in ("gap","role"):
            rows=records()
            if fault=="gap":rows.pop(next(i for i,r in enumerate(rows) if r.get("samples") and r["samples"][0]["frame"]==SECOND_START+1))
            else:next(r["samples"][0] for r in rows if r.get("samples") and r["samples"][0]["frame"]==START)["actors"][0]["role"]="MOUNTED"
            with self.subTest(fault=fault):self.assertFalse(replay(rows=rows)[0]["passed"])


if __name__ == "__main__":
    unittest.main()
