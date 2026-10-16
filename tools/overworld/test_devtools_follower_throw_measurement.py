"""Copied native-shape controls for one Follower Trigger/Cargo lifecycle."""
from copy import deepcopy
import gzip,json,struct,sys,unittest
from pathlib import Path
from unittest.mock import patch

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.overworld.devtools_follower_throw_measurement import (
    ACTIONS, APPLICATION, APPLICATION_LOCAL, AWAY, CARGO_CONDITION, FIND_CARGO, FIND_POSITION, FOLLOWER, KIND, RELEASE,
    REQUIREMENT, SETUP, TRIGGER_CONDITION, NON45_KIND, NON45_REQUIREMENT, NON45_SETUP, NON45_ACTIONS, FollowerThrowMeasurement, raw_handle,
)
from tools.overworld.devtools_follower_throw_proof import (
    FAULTS, FollowerThrowNegative, FollowerThrowFeatureNegative, contract, faults, measurements, validate_negative_result,
)
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor

ROOT=Path(__file__).resolve().parents[2]
SOURCE=dict(contractVersion=2,queryImage=dict(elfSha256="d"*64,packageSha256="e"*64),romSha256='a'*64,overlaySha256='b'*64,profileSha256='c'*64)


def binding(target,condition,source_application=APPLICATION):
    if target is None:raw=bytes(24)
    else:raw=raw_handle(target['handle'])+bytes([2,0])+struct.pack('<HIBBBB',condition,0,source_application,0,1,0)
    return dict(bound=target is not None,flags=int(target is not None),sourceConditionId=condition if target else 0,
        sourceApplication=APPLICATION if target else None,sourceApplicationLocal=source_application if target else 0,
        expiresAt=0,lifetime=0,reason=0,
        target=dict(kind='ACTOR' if target else 'NONE',actor=deepcopy(target['handle']) if target else None),
        targetCurrent=target is not None,rawHex=raw.hex())


def profile(mask, fingerprint):
    lane=bytearray(80);lane[0]=3;lane[1]=3
    lane[7]=lane[36]=3 if mask & (FIND_CARGO|FIND_POSITION) else 7
    lane[20]=1;lane[21]=6;lane[22]=5;lane[48]=30;lane[13]=14 if mask & AWAY else 12;lane[76]=8
    raw=bytearray(lane+lane+bytes(56));struct.pack_into('<II',raw,188,mask,fingerprint)
    return dict(observation='behavior-resolved',resolved=True,fingerprint=fingerprint,
        sourceSha256=SOURCE['profileSha256'],resultHex=raw.hex(),appliedOverrides=mask,
        lanes=[lane.hex(),lane.hex()])


def cargo_profile():
    # Independent target profile; it must remain unchanged by the claim.
    lane = bytearray(80); lane[0] = 1; lane[7] = 16
    raw = bytearray(lane + lane + bytes(56)); struct.pack_into('<II', raw, 188, 0, 777)
    return dict(observation='behavior-resolved',resolved=True,fingerprint=777,
        sourceSha256=SOURCE['profileSha256'],resultHex=raw.hex(),appliedOverrides=0,
        lanes=[lane.hex(),lane.hex()])


def carrier_motion(a, frame, position_motion=True):
    # Synthetic fixture only: ordinary one-tile search Hops and a two-tile
    # normal return. Complete native event shapes are supplied below.
    legs=((10,3,(586,408),(586,409),1),(22,3,(586,409),(586,408),2),
          (83,13,(586,408),(588,410),3))
    if not position_motion:legs=(legs[0],(83,13,(586,409),(588,410),2))
    for start,duration,origin,target,commit in legs:
        if frame<start:break
        a.update(commitSequence=commit,origin=dict(zip(('x','y'),origin)),target=dict(zip(('x','y'),target)))
        a['logical']=dict(zip(('x','y'),origin if frame<start+duration else target))
        if start<=frame<start+duration+5:
            elapsed=min(duration,frame-start);moving=elapsed<duration
            a.update(motionKind='HOP',motionPhase='MOVING' if moving else 'SETTLING',
                motionElapsed=elapsed,motionDuration=duration,reservationId=commit+20 if moving else 0,
                commitSequence=commit+int(not moving))
            e=a['engineObject'];e['pos_x']=(origin[0]<<16)+32768+(target[0]-origin[0])*65536*elapsed//duration
            e['pos_z']=(origin[1]<<16)+32768+(target[1]-origin[1])*65536*elapsed//duration
            e['unk88_y']=16384 if 0<elapsed<duration else 0
        elif frame>=start+duration+5:
            a.update(motionKind='NONE',motionPhase='IDLE',motionElapsed=duration,motionDuration=duration,
                reservationId=0,commitSequence=commit+1)
            a['engineObject'].update(pos_x=(target[0]<<16)+32768,pos_z=(target[1]<<16)+32768,unk88_y=0)
        raw=bytearray(52);direction=3 if target[0]>origin[0] else 1
        struct.pack_into('<HBBHH',raw,0,1,2,direction,a['handle']['fieldEpoch'],a['behaviorFingerprint']&65535)
        struct.pack_into('<4h2i',raw,8,*origin,*target,65536,65536)
        struct.pack_into('<HH',raw,24,duration,commit+20)
        raw[28:38]=bytes([direction,max(abs(x-y) for x,y in zip(origin,target)),16,0,0,0,5,1,0,0])
        elapsed=min(duration,max(0,frame-start));phase=2 if elapsed<duration else 4 if frame<start+duration+5 else 0
        struct.pack_into('<4H4B',raw,40,elapsed,max(0,start+duration+5-frame) if phase==4 else 0,0,0,phase,0,int(elapsed==duration),0)
        from tools.overworld.devtools_walk_matrix_observer import decode_motion
        a['nativeMotion']=decode_motion(bytes(raw))
    a['engineObject'].update(x=a['logical']['x'],y=a['logical']['y'])


def snapshot(frame, position_motion=True):
    m=actor(56,7,107,408);m.update(role='FOLLOWER',level=20,commitSequence=1,inputOwnership=0,reservationId=0,matchedLayerMask=FOLLOWER)
    t=actor(69,0,700,405);t.update(commitSequence=0,inputOwnership=0,reservationId=0)
    c=actor(69,2,702,409);c.update(commitSequence=0,inputOwnership=0,reservationId=0,behaviorFingerprint=777,matchedLayerMask=0)
    c['logical']['x']=c['origin']['x']=c['target']['x']=585
    if 10<=frame<21:m['matchedLayerMask']=FOLLOWER|FIND_CARGO
    if 21<=frame<33:m['matchedLayerMask']=FOLLOWER|FIND_POSITION|AWAY
    if 33<=frame<37:m['matchedLayerMask']=FOLLOWER|FIND_POSITION|AWAY|RELEASE
    if frame>=10:
        t.update(motionKind='WALK',motionPhase='MOVING',motionElapsed=min(frame-10,15),motionDuration=16)
        t['target']['y']=404
    if 11<=frame<=15:
        c.update(motionKind='WALK',motionPhase='MOVING',motionElapsed=frame-11,motionDuration=5,target=dict(x=585,y=410))
    if frame>=16:c.update(commitSequence=1,logical=dict(x=585,y=410),origin=dict(x=585,y=409),target=dict(x=585,y=410))
    if frame>=21:c['logical']=dict(x=585,y=408)
    if 37<=frame<=41:
        c.update(motionKind='HOP',motionPhase='MOVING',motionElapsed=frame-37,motionDuration=5,
            origin=dict(x=585,y=408),target=dict(x=585,y=416),logical=dict(x=585,y=408))
    if frame>=42:c.update(commitSequence=2,logical=dict(x=585,y=416),origin=dict(x=585,y=408),target=dict(x=585,y=416))
    for a in (m,t,c):
        for field in ('logical','render','origin','target'):a[field]['x']+=1
        a['engineObject']=dict(x=a['logical']['x'],y=a['logical']['y'],pos_x=(a['logical']['x']<<16)+32768,
            pos_z=(a['logical']['y']<<16)+32768,pos_y=65536,face_y=0,unk88_y=0,movement_cmd=255,movement_step=0,facing=0,x_range=-1,y_range=-1)
    m['behaviorFingerprint']=1000+(2 if m['matchedLayerMask']&FIND_POSITION else 1 if m['matchedLayerMask']&FIND_CARGO else 0)
    carrier_motion(m,frame,position_motion)
    if 37<=frame<=42:
        elapsed=frame-37;c['engineObject']['pos_z']=(408<<16)+32768+8*65536*elapsed//5
        c['engineObject']['unk88_y']=16384 if 0<elapsed<5 else 0
        c.update(motionKind='HOP',motionPhase='MOVING' if elapsed<5 else 'SETTLING',motionElapsed=elapsed,motionDuration=5,reservationId=55 if elapsed<5 else 0)
    if 43<=frame<47:c.update(motionKind='HOP',motionPhase='SETTLING',motionElapsed=5,motionDuration=5,reservationId=0)
    if frame>=47:c.update(motionKind='NONE',motionPhase='IDLE',motionElapsed=5,motionDuration=5,reservationId=0)
    if frame>=37 and not position_motion:
        c['origin']['y']=409;c['target']['y']=417;c['logical']['y']=409 if frame<42 else 417
        c['engineObject'].update(x=586,y=c['logical']['y'],pos_z=(409<<16)+32768+8*65536*min(5,frame-37)//5)
    if frame>=37:
        native=bytearray(52);struct.pack_into('<HBBHH',native,0,1,2,1,c['handle']['fieldEpoch'],c['behaviorFingerprint']&65535)
        struct.pack_into('<4h2iHH',native,8,586,408 if position_motion else 409,586,416 if position_motion else 417,65536,65536,5,55)
        native[28:38]=bytes([1,8,16,0,0,0,5,1,0,0]);struct.pack_into('<4H4B',native,40,min(5,frame-37),max(0,47-frame) if frame>=42 else 0,0,0,2 if frame<42 else 4 if frame<47 else 0,0,int(frame>=42),0)
        from tools.overworld.devtools_walk_matrix_observer import decode_motion
        c['nativeMotion']=decode_motion(bytes(native))
    t=c
    trigger=binding(t if 10<=frame<37 else None,TRIGGER_CONDITION,APPLICATION_LOCAL)
    cargo=binding(c if 10<=frame<37 else None,CARGO_CONDITION,APPLICATION_LOCAL)
    encoded=3 if 11<=frame<21 else 131 if 21<=frame<33 else 195 if 33<=frame<37 else 0
    recovering=37<=frame<83
    throw=dict(targetRaw=encoded,targetSlot=2 if encoded else None,carried=bool(encoded&128),windup=bool(encoded&64),targeted=False,carrier=bool(encoded),recovering=recovering)
    targets=[0]*10;targets[7]=encoded
    masks=(4 if encoded else 0,128 if encoded else 0,128 if recovering else 0)
    native=bytes(targets)+struct.pack('<3H',*masks)
    carrier=dict(slot=7,handle=deepcopy(m['handle']),role='FOLLOWER',available=True,reason=None,
        bindings=dict(trigger=trigger,cargo=cargo),rawBindingsHex=(raw_handle(m['handle'])+bytes.fromhex(trigger['rawHex'])+bytes.fromhex(cargo['rawHex'])).hex(),throw=throw)
    if frame < 37:
        from tools.overworld.devtools_walk_matrix_observer import decode_motion
        raw = bytearray(52)
        kind = 1 if 11 <= frame < 16 else 0
        struct.pack_into('<HBBHH', raw, 0, 1, kind, 1, c['handle']['fieldEpoch'], 777)
        struct.pack_into('<4h2iHH', raw, 8, 586, 409, 586, 410, 65536, 65536, 5, 31)
        raw[29] = 1; struct.pack_into('<4H4B', raw, 40, max(0,min(5,frame-11)), 0, 0, 0, 2 if kind else 0, 0, int(frame>=16), 0)
        c['nativeMotion'] = decode_motion(bytes(raw))
        if kind:
            c['reservationId'] = 31
            c['engineObject'].update(pos_z=(409<<16)+32768+65536*(frame-11)//5)
    timers = []
    for a in (m,c):
        a['sourceIdentity'] = dict(object=a['engineIdentity']['pointer'],personality=a['subjectIdentity'],
            map_id=33,species=a['species'],form=a['form'],level=a['level'],active=1,
            object_id=0xE0+a['handle']['slot'],encounter_generation=a['handle']['encounterGeneration'])
        timers.append(dict(handle=deepcopy(a['handle']),slot=a['handle']['slot'],sourceIdentity=deepcopy(a['sourceIdentity']),
            movementActorControlMode=int(a is c and 21<=frame<37)))
    combat=dict(schemaVersion=1,available=True,frame=frame,nativeCycle=frame+1000,observationBoundary='main-task-queue-completion',fieldSystem=0x2200000,
        movementTimers=timers,identity=dict(romSha256=SOURCE['romSha256'],overlaySha256=SOURCE['overlaySha256']),
        targets=[dict(handle=deepcopy(a['handle']),role=a['role'],motion=a.pop('nativeMotion',{})) for a in (m,c)],
        interactions=dict(schemaVersion=1,available=True,frame=frame,nativeCycle=frame+1000,observationBoundary='main-task-queue-completion',fieldSystem=0x2200000,
            identity=dict(romSha256=SOURCE['romSha256']),carriers=[carrier],throwState=dict(targets=targets,targetMask=masks[0],carrierMask=masks[1],recoveringMask=masks[2],rawHex=native.hex())))
    return dict(frame=frame,actorFrame=frame,nativeCycle=frame+1000,fieldAvailable=True,romSha256=SOURCE['romSha256'],observationBoundary='main-task-queue-completion',
        fieldControl=dict(taskPointer=0,fieldPointer=0x2200000),context=dict(mapId=33,fieldEpoch=1,mapGeneration=1),
        actors=[m,c],player=dict(x=586+min(4,max(0,frame-37)//8),y=407),party=[dict(personality=107,species=56,identityVerified=True,hp=46,maxHp=46)],pokemonCombat=combat)


def events(sample):
    frame=sample['frame'];found=[]
    def add(sp,name,a,b):
        actor=next(x for x in sample['actors'] if x['species']==sp)
        found.append(dict(frame=frame,kind='native',data=dict(actorHandle=actor['handle']['value'],
            actor={k:v for k,v in actor['handle'].items() if k!='value'},sequence=frame*10+len(found),event=name,valueA=a,valueB=b)))
    if frame==16:
        add(69,'LOGICAL_COMMIT',1,1);add(69,'MOTION_FINISHED',1,1);add(69,'CONTROL_RETURNED',0,1)
    if frame==37:add(69,'MOTION_STARTED',2,5)
    if frame==42:add(69,'LOGICAL_COMMIT',2,2)
    if frame==47:add(69,'MOTION_FINISHED',2,2);add(69,'CONTROL_RETURNED',0,2)
    m=sample['actors'][0]
    for start,duration in ((10,3),(22,3),(83,13)):
        if start==22 and (frame==start and m['motionKind']!='HOP' or frame>start and m['commitSequence']<3):continue
        if frame==start:add(56,'MOTION_STARTED',2,duration)
        if frame==start+duration:add(56,'LOGICAL_COMMIT',m['commitSequence'],2)
        if frame==start+duration+5:
            add(56,'MOTION_FINISHED',m['commitSequence'],2);add(56,'CONTROL_RETURNED',0,m['commitSequence'])
    found.insert(0,dict(frame=frame,kind='native-observation',data=profile(m['matchedLayerMask'],m['behaviorFingerprint'])))
    found.insert(0,dict(frame=frame,kind='native-observation',data=cargo_profile()))
    if frame in (10,11,12,18):
        from tools.overworld.test_devtools_cargo_route_continuity import query_event
        query=query_event(sample, m, SOURCE['queryImage'])
        for key in ('before','after'):query['data'][key]['workspace']['compatibility']['cargo']=deepcopy(sample['actors'][1]['handle'])
        found.append(query)
    return found


def raw(action,samples,phase='observe'):
    return dict(phase=phase,action=action,samples=samples,events=[e for s in samples for e in events(s)],completedGameFrames=len(samples),
        observedFieldFrames=len(samples),nativeCycles=len(samples),cycleIntervals=[dict(completedGameFrame=s['frame'],cpuNs=1,wallNs=1) for s in samples])


def seeded(feature=KIND):
    m=FollowerThrowMeasurement(SOURCE, feature=feature);s=snapshot(9);m.latest=deepcopy(s);m.initial=deepcopy(s);m.setup_index=len(SETUP)
    m.subjects={n:select_current_actor(s,next(a for a in s['actors'] if a['species']==sp and a['role']==r)) for n,sp,r,_ in [('mankey',56,'FOLLOWER','existing'),('trigger',69,'WILD','spawn'),('cargo',69,'WILD','spawn')]}
    m._profile_events(events(s)); m._autonomy(s, events(s))
    return m


def stream(position_motion=True):
    return [raw(ACTIONS[0][0],[snapshot(f,position_motion) for f in range(10,38)]),
            raw(ACTIONS[1][0],[snapshot(f,position_motion) for f in range(38,70)]),
            raw(ACTIONS[2][0],[snapshot(f,position_motion) for f in range(70,102)])]


def moving_stream():
    """Copied native-shape fixture: pickup interrupts a still-moving Walk.

    This is a host control, not game evidence. All later flight, search and
    normal Follow samples retain their original complete native lifecycles.
    """
    from tools.overworld.devtools_walk_matrix_observer import decode_motion
    rows = stream()
    for row in rows:
        for sample in row["samples"]:
            frame = sample["frame"]; cargo = sample["actors"][1]
            combat = sample["pokemonCombat"]
            combat.update(schemaVersion=1, observationBoundary=sample["observationBoundary"],
                          fieldSystem=sample["fieldControl"]["fieldPointer"])
            combat["movementTimers"] = []
            for a in sample["actors"]:
                a["sourceIdentity"] = dict(object=a["engineIdentity"]["pointer"],
                    personality=a["subjectIdentity"], map_id=33, species=a["species"],
                    form=a["form"], level=a["level"], active=1,
                    object_id=0xE0+a["handle"]["slot"],
                    encounter_generation=a["handle"]["encounterGeneration"])
                combat["movementTimers"].append(dict(handle=deepcopy(a["handle"]),
                    slot=a["handle"]["slot"], sourceIdentity=deepcopy(a["sourceIdentity"]),
                    movementActorControlMode=int(a is cargo and 21 <= frame < 37)))
            target = next(t for t in combat["targets"] if t["handle"] == cargo["handle"])
            if 11 <= frame < 37:
                elapsed = min(10, frame-11); canceled = frame >= 21
                native = bytearray(52)
                struct.pack_into("<HBBHH",native,0,1,1,1,cargo["handle"]["fieldEpoch"],777)
                struct.pack_into("<4h2iHH",native,8,586,409,586,410,65536,65536,20,31)
                native[28:38] = bytes([1,1,0,0,0,0,0,0,0,0])
                struct.pack_into("<4H4B",native,40,elapsed,0,0,0,6 if canceled else 2,0,0,16 if canceled else 0)
                target["motion"] = decode_motion(bytes(native))
                cargo.update(commitSequence=0, motionKind="NONE" if canceled else "WALK",
                    motionPhase="CANCELED" if canceled else "MOVING", motionElapsed=elapsed,
                    motionDuration=20, reservationId=0 if canceled else 31,
                    origin=dict(x=586,y=409), target=dict(x=586,y=410))
                if not canceled:
                    cargo["logical"] = dict(x=586,y=409)
                    cargo["engineObject"].update(x=586,y=409,pos_x=(586<<16)+32768,
                        pos_z=(409<<16)+32768+65536*elapsed//20)
            elif frame >= 37:
                cargo["commitSequence"] -= 1
        kept = []
        for event in row["events"]:
            data = event.get("data", {})
            if event.get("kind") == "native" and data.get("actorHandle") == rows[0]["samples"][0]["actors"][1]["handle"]["value"]:
                if event["frame"] == 16:
                    continue
                if event["frame"] == 42: data["valueA"] = 1
                if event["frame"] == 47:
                    if data["event"] == "CONTROL_RETURNED": data["valueB"] = 1
                    else: data["valueA"] = 1
            kept.append(event)
        row["events"] = kept
        for sample in row["samples"]:
            if sample["frame"] != 21: continue
            cargo = sample["actors"][1]
            for sequence, name, a in ((210,"MOTION_CANCELED",1),(211,"CONTROL_RETURNED",0)):
                row["events"].append(dict(frame=21,kind="native",data=dict(event=name,valueA=a,valueB=0,
                    sequence=sequence,reason="CONTEXT_LOST",frame=21,actorFrame=21,
                    actorHandle=cargo["handle"]["value"],actor={k:v for k,v in cargo["handle"].items() if k!="value"})))
        row["events"].sort(key=lambda e:(e["frame"], e.get("data",{}).get("sequence",0)))
    return rows


def evaluate(rows,negative=None,feature=KIND):
    m=seeded(feature)
    for row in rows:
        m.observe_record(negative.mutate(row,m.subjects) if negative else row)
        if m.failures:break
    result=m.finish()
    return dict(passed=result['passed'],failures=result['failures'],observedFrames=result['observedFrames'],measurements={feature:result})


def non45_stream():
    """Copied unit data only; the registered fixture still needs a real run."""
    rows = stream()
    cargo_value = rows[0]["samples"][0]["actors"][1]["handle"]["value"]
    for row in rows:
        for sample in row["samples"]:
            frame = sample["frame"]
            sample["player"] = dict(x=583 + min(4,max(0,frame-37)//8), y=406)
            if frame < 37:
                continue
            cargo = sample["actors"][1]
            elapsed = min(24,frame-37)
            origin, target = (586,408),(594,413)
            cargo.update(origin=dict(zip(("x","y"),origin)), target=dict(zip(("x","y"),target)),
                logical=dict(zip(("x","y"),origin if frame<61 else target)),
                motionKind="HOP" if frame<66 else "NONE",
                motionPhase="MOVING" if frame<61 else "SETTLING" if frame<66 else "IDLE",
                motionElapsed=elapsed,motionDuration=24,reservationId=55 if frame<61 else 0,
                commitSequence=1 if frame<61 else 2)
            cargo["engineObject"].update(x=cargo["logical"]["x"],y=cargo["logical"]["y"],
                pos_x=(586<<16)+32768+8*65536*elapsed//24,
                pos_z=(408<<16)+32768+5*65536*elapsed//24,
                unk88_y=16384 if 0<elapsed<24 else 0)
            target_row=next(r for r in sample["pokemonCombat"]["targets"] if r["handle"]==cargo["handle"])
            native=bytearray.fromhex(target_row["motion"]["rawHex"])
            native[3]=native[28]=3
            struct.pack_into("<4h",native,8,*origin,*target)
            struct.pack_into("<H",native,24,24)
            struct.pack_into("<4H4B",native,40,elapsed,max(0,66-frame) if frame>=61 else 0,0,0,
                2 if frame<61 else 4 if frame<66 else 0,0,int(frame>=61),0)
            target_row["motion"]=__import__('tools.overworld.devtools_walk_matrix_observer',fromlist=['decode_motion']).decode_motion(bytes(native))
        kept=[]
        for event in row["events"]:
            data=event.get("data",{})
            if event.get("kind")=="native" and data.get("actorHandle")==cargo_value:
                if event["frame"] in (42,47):continue
                if event["frame"]==37:data["valueB"]=24
            kept.append(event)
        # Use the same authenticated subject event shape as existing fixtures.
        for frame,names in ((61,(("LOGICAL_COMMIT",2,2),)),
                            (66,(("MOTION_FINISHED",2,2),("CONTROL_RETURNED",0,2)))):
            sample=next((a for a in row["samples"] if a["frame"]==frame),None)
            if sample is None:continue
            cargo=sample["actors"][1]
            for index,(name,a,b) in enumerate(names):
                kept.append(dict(frame=frame,kind="native",data=dict(actorHandle=cargo["handle"]["value"],
                    actor={k:v for k,v in cargo["handle"].items() if k!="value"},sequence=frame*10+index+1,
                    event=name,valueA=a,valueB=b)))
        row["events"]=sorted(kept,key=lambda e:(e["frame"],e.get("data",{}).get("sequence",-1)))
    return rows


class FollowerThrowMeasurementTests(unittest.TestCase):
    def test_non45_variant_keeps_full_lifecycle_and_exact_radius_support(self):
        result=evaluate(non45_stream(),feature=NON45_KIND)
        self.assertTrue(result["passed"],result)
        measured=result["measurements"][NON45_KIND]
        self.assertEqual(measured["requirements"],[NON45_REQUIREMENT])
        self.assertEqual(measured["launchEndpoint"]["target"],[594,413])
        self.assertEqual(measured["launchEndpoint"]["plan"]["distance"],8)
        self.assertEqual(measured["flightWitness"]["duration"],24)
        self.assertEqual(measured["flightWitness"]["returnFrame"],66)
        record=dict(sessionId="owned",sessionCleanup=dict(sessionId="owned",closed=True,errors=[]))
        self.assertEqual(len(measurements(NON45_KIND,result,record)),sum(map(len,contract(NON45_KIND).values())))
        changed=deepcopy(result);changed["measurements"][NON45_KIND]["flightWitness"]["poses"][-1]["supportY"]+=4096
        with self.assertRaisesRegex(ValueError,"landing support"):
            measurements(NON45_KIND,changed,record)
        self.assertFalse(evaluate(non45_stream())["passed"],"cardinal case must remain cardinal")

    def test_non45_variant_all_original_and_angle_controls_reject(self):
        from tools.overworld.proof_adapters import get_adapter
        adapter=get_adapter(NON45_KIND)
        for fault in adapter.faults:
            with self.subTest(fault=fault):
                negative=adapter.negative(fault)
                result=evaluate(non45_stream(),negative,feature=NON45_KIND)
                self.assertTrue(negative.applied)
                self.assertFalse(result["passed"],result)
                adapter.validate_negative_result(result,fault)

    def test_non45_exact_recipe_and_shared_dispatch_are_bounded(self):
        from tools.overworld.proof_adapters import get_adapter
        recipe=json.loads((ROOT/'tests/overworld/test-recipes/follower.throw-away-non45.json').read_text())
        test=validate_test(recipe)
        evaluator=TestEvaluator(test);evaluator.install_measurements({NON45_KIND:SOURCE})
        self.assertTrue(evaluator.uses_raw_records)
        self.assertEqual(evaluator.measurements[NON45_KIND].setup,NON45_SETUP)
        self.assertEqual(evaluator.measurements[NON45_KIND].actions,NON45_ACTIONS)
        self.assertEqual(get_adapter(NON45_KIND).requirement,NON45_REQUIREMENT)
        self.assertEqual(get_adapter(NON45_KIND).contract(),contract(NON45_KIND))
        changed=deepcopy(recipe);changed['setup'][4]['args']['x']=589
        with self.assertRaisesRegex(ValueError,'fixture'):validate_test(changed)

    def test_search_keeps_its_authored_pause(self):
        from tools.overworld.devtools_walk_matrix_observer import decode_motion
        for pause in (0, 7):
            rows=stream()
            sample=rows[0]['samples'][0]
            motion=sample['pokemonCombat']['targets'][0]['motion']
            data=bytearray.fromhex(motion['rawHex']);data[34]=pause
            motion.clear();motion.update(decode_motion(bytes(data)))
            result=evaluate(rows)
            with self.subTest(pause=pause):
                self.assertFalse(result['passed'])
                self.assertTrue(any('Hop pause differs' in f for f in result['failures']))

    def test_same_targets_motion_pickup_launch_and_follow_return(self):
        result=evaluate(stream());self.assertTrue(result['passed'],result)
        r=result['measurements'][KIND]
        self.assertEqual({stage:w['duration'] for stage,w in r['speedWitnesses'].items()}, {'cargo':3,'position':3,'normal':13})
        self.assertEqual(r['frames']['cargoCommit'],16);self.assertEqual(r['frames']['launch'],37);self.assertEqual(r['frames']['followReturn'],101)
        record=dict(sessionId='owned',sessionCleanup=dict(sessionId='owned',closed=True,errors=[]))
        self.assertEqual(len(measurements(result,record)),sum(map(len,contract().values())))

    def test_checked_moving_cargo_handoff_keeps_complete_throw_and_follow(self):
        result = evaluate(moving_stream())
        self.assertTrue(result["passed"], result)
        value = result["measurements"][KIND]
        self.assertNotIn("cargoCommit", value["frames"])
        self.assertEqual(value["frames"]["cargoControl"], value["frames"]["pickup"])
        self.assertEqual(value["movingPickup"]["motionIdentity"], 31)
        record = dict(sessionId="owned", sessionCleanup=dict(sessionId="owned",closed=True,errors=[]))
        self.assertEqual(len(measurements(result,record)),sum(map(len,contract().values())))

    def test_natural_terminal_and_pickup_can_share_one_completed_queue(self):
        from tools.overworld.devtools_walk_matrix_observer import decode_motion
        rows = moving_stream()
        for row in rows:
            for sample in row["samples"]:
                frame = sample["frame"]; cargo = sample["actors"][1]
                motion = sample["pokemonCombat"]["targets"][1]["motion"]
                if 11 <= frame < 37:
                    raw = bytearray.fromhex(motion["rawHex"])
                    struct.pack_into("<H",raw,24,10)
                    if frame >= 21:
                        raw[48]=0;raw[50]=1;raw[51]=0
                        struct.pack_into("<H",raw,46,1)
                        cargo.update(commitSequence=1,motionPhase="IDLE")
                    else:
                        cargo["engineObject"]["pos_z"]=(409<<16)+32768+65536*(frame-11)//10
                    cargo["motionDuration"]=10
                    motion.clear();motion.update(decode_motion(bytes(raw)))
                elif frame >= 37:
                    cargo["commitSequence"]+=1
            for event in row["events"]:
                data=event.get("data",{})
                if event.get("kind")=="native" and data.get("actorHandle")==rows[0]["samples"][0]["actors"][1]["handle"]["value"]:
                    if event["frame"]==42:data["valueA"]=2
                    if event["frame"]==47:
                        if data["event"]=="CONTROL_RETURNED":data["valueB"]=2
                        else:data["valueA"]=2
            row["events"]=[e for e in row["events"] if not (e.get("kind")=="native" and e.get("frame")==21)]
            if any(s["frame"]==21 for s in row["samples"]):
                for sequence,name,a,b in ((210,"LOGICAL_COMMIT",1,1),(211,"MOTION_FINISHED",1,1),(212,"CONTROL_RETURNED",0,1)):
                    h=rows[0]["samples"][0]["actors"][1]["handle"]
                    row["events"].append(dict(frame=21,kind="native",data=dict(event=name,valueA=a,valueB=b,
                        sequence=sequence,actorHandle=h["value"],actor={k:v for k,v in h.items() if k!="value"})))
                row["events"].sort(key=lambda e:(e["frame"],e.get("data",{}).get("sequence",0)))
        result=evaluate(rows)
        self.assertTrue(result["passed"],result)
        value=result["measurements"][KIND]
        self.assertIsNone(value["movingPickup"])
        self.assertEqual(value["frames"]["cargoCommit"],value["frames"]["pickup"])
        missing=deepcopy(rows)
        missing[0]["events"]=[e for e in missing[0]["events"] if not (e.get("frame")==21 and e.get("data",{}).get("event")=="CONTROL_RETURNED")]
        self.assertFalse(evaluate(missing)["passed"])

    def test_moving_handoff_requires_exact_target_only_native_receipts(self):
        for fault in ("missing-cancel", "missing-return", "reversed", "token", "forced", "raw-plan",
                      "timer-owner", "held-mode", "commit", "carrier-cancel", "stopped-body", "clock"):
            rows = moving_stream()
            before = next(s for r in rows for s in r["samples"] if s["frame"]==20)
            after = next(s for r in rows for s in r["samples"] if s["frame"]==21)
            row = rows[0]
            own = [e for e in row["events"] if e.get("frame")==21 and e.get("kind")=="native"]
            motion = after["pokemonCombat"]["targets"][1]["motion"]
            if fault == "missing-cancel": row["events"].remove(own[0])
            elif fault == "missing-return": row["events"].remove(own[1])
            elif fault == "reversed": own[0]["data"]["sequence"],own[1]["data"]["sequence"]=211,210
            elif fault in ("token", "forced"):
                from tools.overworld.devtools_walk_matrix_observer import decode_motion
                data = bytearray.fromhex(motion["rawHex"])
                if fault == "token": struct.pack_into("<H",data,26,32)
                else: data[37]=1
                motion.clear();motion.update(decode_motion(bytes(data)))
            elif fault == "raw-plan": motion["plan"]["reservationId"]+=1
            elif fault == "timer-owner": after["pokemonCombat"]["movementTimers"][1]["sourceIdentity"]["object"]+=4
            elif fault == "held-mode": after["pokemonCombat"]["movementTimers"][1]["movementActorControlMode"]=0
            elif fault == "commit": after["actors"][1]["commitSequence"]+=1
            elif fault == "carrier-cancel":
                e=deepcopy(own[0]);h=after["actors"][0]["handle"]
                e["data"].update(actorHandle=h["value"],actor={k:v for k,v in h.items() if k!="value"})
                row["events"].append(e)
            elif fault == "stopped-body": before["actors"][1]["engineObject"]["pos_z"]=(409<<16)+32768
            else: after["actorFrame"]+=1
            with self.subTest(fault=fault):
                result=evaluate(rows)
                self.assertFalse(result["passed"],result)
                self.assertTrue(any("moving pickup" in m or "pickup autonomy" in m or "canceled its accepted carrier" in m
                                    for m in result["failures"]),result)

    def test_speed_witness_keeps_stable_engine_owner_when_motion_flags_change(self):
        result=evaluate(stream());self.assertTrue(result['passed'],result)
        meter=result['measurements'][KIND]
        def engine(value,flags):
            value=deepcopy(value)
            value['id_lookup']=dict(matching_objects=[dict(pointer=value['pointer'],flags=flags,
                active=True,flag25=False,lookup_eligible=True)])
            return value
        meter['subjects']['mankey']['engineIdentity']=engine(meter['subjects']['mankey']['engineIdentity'],1)
        for witness in meter['speedWitnesses'].values():witness['engineIdentity']=engine(witness['engineIdentity'],257)
        record=dict(sessionId='owned',sessionCleanup=dict(sessionId='owned',closed=True,errors=[]))
        self.assertEqual(len(measurements(result,record)),sum(map(len,contract().values())))
        meter['speedWitnesses']['cargo']['engineIdentity']['pointer']+=4
        with self.assertRaisesRegex(ValueError,'carrier speed witness'):measurements(result,record)

    def test_motion_replaced_control_waits_for_that_current_bound_cargo(self):
        early = snapshot(9);cargo = early['actors'][1]
        cargo.update(motionKind='WALK',motionPhase='MOVING',motionElapsed=1,motionDuration=5)
        row = raw(ACTIONS[0][0],[early])
        control = FollowerThrowNegative(KIND+':cargo-motion-replaced')
        subjects = seeded().subjects
        self.assertIs(control.mutate(row,subjects),row)
        self.assertFalse(control.applied)
        result = evaluate(stream(),control)
        self.assertTrue(control.applied)
        validate_negative_result(result,KIND+':cargo-motion-replaced')
        self.assertIn("replaced Cargo's accepted motion",result['measurements'][KIND]['failures'][0])
        once = FollowerThrowNegative(KIND+':cargo-motion-replaced')
        first = raw(ACTIONS[0][0],[snapshot(12)])
        self.assertNotEqual(once.mutate(first,subjects)['samples'][0]['actors'][1]['target'],
                            first['samples'][0]['actors'][1]['target'])
        following = raw(ACTIONS[0][0],[snapshot(13)])
        self.assertEqual(once.mutate(following,subjects),following)

    def test_all_copied_controls_reject_for_their_named_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                n=FollowerThrowNegative(fault);result=evaluate(stream(),n)
                self.assertTrue(n.applied);self.assertFalse(result['passed'],result);validate_negative_result(result,fault)

    def test_native_chunk_split_retains_action_work(self):
        rows=[raw(action,[s]) for row in stream() for s in row['samples'] for action in [row['action']]]
        self.assertTrue(evaluate(rows)['passed'])

    def test_follow_return_allows_fresh_current_trigger_after_old_binding_clear(self):
        def set_trigger(sample,target,current=True):
            row=sample['pokemonCombat']['interactions']['carriers'][0]
            value=binding(target,TRIGGER_CONDITION,APPLICATION_LOCAL);value['targetCurrent']=current
            row['bindings']['trigger']=value
            raw=bytearray.fromhex(row['rawBindingsHex']);raw[12:36]=bytes.fromhex(value['rawHex'])
            row['rawBindingsHex']=raw.hex()
        for reuse in (False,True):
            rows=stream();last=rows[-1]['samples'][-1]
            target=last['actors'][1] if reuse else actor(74,3,703,407)
            if not reuse:last['actors'].append(target)
            set_trigger(last,target)
            result=evaluate(rows);self.assertTrue(result['passed'],result)
            self.assertEqual(result['measurements'][KIND]['frames']['bindingsCleared'],37)
        rows=stream()
        for row in rows:
            for sample in row['samples']:
                if sample['frame']>=37:set_trigger(sample,sample['actors'][1])
        stale=evaluate(rows)
        self.assertFalse(stale['passed']);self.assertIn('old bindings before normal follow',stale['failures'][0])
        rows=stream();last=rows[-1]['samples'][-1];set_trigger(last,last['actors'][1],False)
        stale=evaluate(rows)
        self.assertFalse(stale['passed']);self.assertIn('not a current authored binding',stale['failures'][0])

    def test_current_tile_away_aim_needs_resolved_position_phase_but_no_position_hop(self):
        result=evaluate(stream(position_motion=False))
        self.assertTrue(result['passed'],result)
        r=result['measurements'][KIND]
        self.assertEqual(set(r['speedWitnesses']),{'cargo','normal'})
        self.assertTrue(r['positionProfile']['appliedOverrides'] & FIND_POSITION)
        self.assertEqual(r['launchEndpoint']['target'],[586,417])
        self.assertEqual(r['flightWitness']['returnFrame'],47)
        record=dict(sessionId='owned',sessionCleanup=dict(sessionId='owned',closed=True,errors=[]))
        self.assertEqual(len(measurements(result,record)),sum(map(len,contract().values())))

    def test_route_query_must_name_that_same_noticed_cargo(self):
        rows=stream()
        for event in rows[0]['events']:
            if event.get('data',{}).get('observation')=='throw-cargo-query':
                for key in ('before','after'):event['data'][key]['workspace']['compatibility']['cargo']['generation']+=1
                break
        result=evaluate(rows)
        self.assertFalse(result['passed'])
        self.assertIn('route query names a different Cargo',result['failures'][0])

    def test_exact_sight_recipe_spawn_reaches_real_prepared_dispatch(self):
        self._check_prepared_dispatch("follower.throw-moving-cargo",KIND)
        self._check_prepared_dispatch("follower.throw-away-non45",NON45_KIND)

    def _check_prepared_dispatch(self,case,feature):
        from tools.overworld.devtools_test_contract import _handle, _wild_spawn_setup
        from tools.overworld.test_devtools_wild_walk_contract import spawn_setup
        recipe = validate_test(json.loads((ROOT/f'tests/overworld/test-recipes/{case}.json').read_text()))
        spawn = next(a for a in recipe['setup'] if a['op']=='spawn' and a['args'].get('role')=='wild')
        self.assertEqual((spawn['id'],spawn['args']['species']),('spawn-trigger',69))
        receipt, sample = spawn_setup(species=69,locomotion=7)
        selected = _wild_spawn_setup(receipt,sample,species=69,locomotion=7)['subject']
        row = dict(phase='setup',action=spawn['id'],command=spawn['op'],receipt=receipt,snapshot=sample)
        def evaluate_dispatch(value):
            evaluator = TestEvaluator(recipe);evaluator.install_measurements({feature:SOURCE})
            meter = evaluator.measurements[feature]
            # The leaf's full lifecycle has separate dense tests above. Only
            # its callback is paused here; shared native acquisition is real.
            with patch.object(meter,'observe_record',return_value=meter.result()), \
                    patch('tools.overworld.devtools_test_contract._wild_spawn_setup',wraps=_wild_spawn_setup) as prepared:
                result = evaluator.observe_record(value)
            return evaluator,result,prepared
        evaluator,result,prepared = evaluate_dispatch(row)
        self.assertEqual(result['failures'],[])
        prepared.assert_called_once_with(receipt,sample,species=69,locomotion=7)
        self.assertIn(_handle(selected['handle']),evaluator._prepared_attached)
        self.assertEqual((result['observedFrames'],result['sampledFrames']),(0,0))
        self.assertFalse(result['acceptedProof'])
        wrong = deepcopy(row);wrong['receipt']['value']['species']=43
        evaluator,result,_ = evaluate_dispatch(wrong)
        self.assertEqual(evaluator._prepared_attached,set())
        self.assertTrue(any('command encounter identity' in f['message'] for f in result['failures']))

    def test_recipe_exact_sources_and_opt_in_job_wiring(self):
        recipe=json.loads((ROOT/'tests/overworld/test-recipes/follower.throw-moving-cargo.json').read_text())
        test=validate_test(recipe)
        evaluator=TestEvaluator(test);evaluator.install_measurements({KIND:SOURCE})
        self.assertTrue(evaluator.uses_raw_records);self.assertIn(KIND,evaluator.measurements)
        self.assertEqual(SETUP[3],('bind-mankey','bind',{'subject':'mankey'}))
        self.assertEqual(SETUP[6],('bind-cargo','bind',{'subject':'cargo'}))
        self.assertEqual(len(SETUP),7)
        changed=deepcopy(recipe);changed['setup'][4]['args']['x']=587
        with self.assertRaisesRegex(ValueError,'fixture'):validate_test(changed)
        changed=deepcopy(recipe);changed['subjects'][2]['species']=43
        with self.assertRaisesRegex(ValueError,'fixture'):validate_test(changed)
        changed=deepcopy(recipe);changed['setup'][0]['args']['facing']=0
        with self.assertRaisesRegex(ValueError,'fixture'):validate_test(changed)
        from tools.overworld.proof_adapters import get_adapter
        self.assertEqual(get_adapter(KIND).contract(),contract())

if __name__=='__main__':unittest.main()
