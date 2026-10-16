"""Positive replay and copied-fault sensitivity; these are not game proof."""

from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest

from tools.overworld.devtools_pokemon_combat_measurement import (
    KIND, PokemonCombatMeasurement, SETUP, TAIL_FRAMES,
)
from tools.overworld.devtools_pokemon_combat_proof import (
    FAULTS, PokemonCombatNegative, measurements, validate_negative_result,
)
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_walk_matrix_observer import decode_motion


ROOT = Path(__file__).resolve().parents[2]
SOURCE = dict(contractVersion=1,romSha256='a'*64,overlaySha256='b'*64,profileSha256='c'*64)
SLOTS = dict(cyndaquil=7,snorlax=0,weepinbell=1)
SPECIES = dict(cyndaquil=155,snorlax=143,weepinbell=70)
MAX_HP = dict(cyndaquil=90,snorlax=230,weepinbell=75)


def snapshot(frame, *, wild_hit=False, mount_hit=False, wild_arc=0, mount_arc=0,
             wild_tile=405,mount_tile=407):
    actors=[];targets=[]
    for name,slot in SLOTS.items():
        handle=dict(value=65536+slot,slot=slot,generation=1,fieldEpoch=1,mapGeneration=1,encounterGeneration=1)
        role='MOUNTED' if slot==7 else 'WILD'
        z=mount_tile if slot==7 else wild_tile if name=='snorlax' else 404
        arc=mount_arc if slot==7 else wild_arc if name=='snorlax' else 0
        actors.append(dict(handle=handle,subjectIdentity=100+slot,active=True,
            identityVerified=True,presentationAttached=True,authorityGeneration=1,
            engineAnchorGeneration=1,presentationGeneration=1,role=role,species=SPECIES[name],
            form=0,level=50 if name!='weepinbell' else 10,inputOwnership=1 if slot==7 else 0,
            engineIdentity=dict(pointer=0x02110000+slot*512),sourceIdentity=dict(personality=100+slot),
            engineObject=dict(pos_x=(585<<16)+32768,pos_z=(z<<16)+32768,pos_y=0,face_y=arc,unk88_y=0),
            matchedLayerMask=1<<25 if name=='weepinbell' else 0,
            behaviorFingerprint=901+slot,motionKind='HOP' if name=='weepinbell' else 'NONE',
            motionPhase='MOVING' if name=='weepinbell' else 'IDLE'))
        hit=mount_hit if slot==7 else wild_hit if name=='snorlax' else False
        target=dict(handle=deepcopy(handle),slot=slot,personality=100+slot,species=SPECIES[name],
            hp=MAX_HP[name]-20*hit,currentHp=MAX_HP[name]-20*hit,maxHp=MAX_HP[name],
            hitCount=int(hit),lastDamage=20 if hit else 0,immunityFrames=max(0,60-(frame-(30 if slot==7 else 14))) if hit else 0,
            knockbackPending=0,knockbackOptions=0,knockbackDirection=0,
            hpSource='party' if slot==7 else 'wild-resident')
        targets.append(target)
    return dict(frame=frame,nativeCycle=frame+1000,romSha256=SOURCE['romSha256'],fieldAvailable=True,
        observationBoundary='main-task-queue-completion',context=dict(mapId=33,fieldEpoch=1,mapGeneration=1),
        fieldControl=dict(taskPointer=0),actors=actors,
        player=dict(x=585,y=mount_tile,pos_x=(585<<16)+32768,pos_z=(mount_tile<<16)+32768,pos_y=0,face_y=32768+mount_arc,unk88_y=0),
        party=[dict(personality=107,hp=90-20*mount_hit,maxHp=90)],
        pokemonCombat=dict(schemaVersion=1,available=True,frame=frame,nativeCycle=frame+1000,
            identity=dict(romSha256=SOURCE['romSha256'],overlaySha256=SOURCE['overlaySha256']),targets=targets),
        nativeObservation=dict(profileFingerprints=[902]))


def cache(sample):
    data=bytearray(216);data[72:75]=bytes((1,16,20));data[79]=6
    return dict(frame=sample['frame'],nativeCycle=sample['nativeCycle'],resolvedProfiles=[dict(
        resolved=True,fingerprint=902,sourceSha256=SOURCE['profileSha256'],appliedOverrides=1<<25,resultHex=data.hex())])


def raw(action,sample,phase='observe'):
    return dict(phase=phase,action=action,samples=[sample],completedGameFrames=1,
        observedFieldFrames=1,nativeCycles=1,events=[],
        cycleIntervals=[dict(completedGameFrame=sample['frame'],cpuNs=1,wallNs=1)],profileCache=cache(sample))


def health(sample,hp,hits):
    return dict(phase='observe',action='before-contact' if hits==0 else 'after-contact',
        command='player-health.observe',snapshot=sample,receipt=dict(playerHealth=dict(
            frame=sample['frame'],hp=hp,savedHp=hp,maxHp=100,acceptedHits=hits,
            recoveryPending=False,identity=dict(overlaySha256=SOURCE['overlaySha256']))))


def motion(sample,name,*,kind,origin,target,duration,elapsed,phase=2,forced=False):
    actor=next(a for a in sample['actors'] if a['species']==SPECIES[name])
    row=next(t for t in sample['pokemonCombat']['targets'] if t['slot']==SLOTS[name])
    raw=bytearray(52)
    struct.pack_into('<HBBHH4h2iHH',raw,0,1,kind,1,1,0,585,origin,585,target,0,0,duration,42 if phase==2 else 0)
    raw[28:38]=bytes((1,1,16 if kind==2 else 0,0,0,0,0,2 if name=='cyndaquil' else 1,1,int(forced)))
    struct.pack_into('<4H4B',raw,40,elapsed,0,int(elapsed==duration),int(elapsed==duration),phase,0,int(elapsed==duration),0)
    row['motion']=decode_motion(bytes(raw))
    actor.update(origin=dict(x=585,y=origin),target=dict(x=585,y=target),
                 logical=dict(x=585,y=actor['engineObject']['pos_z']>>16),
                 motionKind='HOP' if kind==2 else 'WALK',motionPhase='MOVING' if phase==2 else 'IDLE',
                 motionElapsed=elapsed,motionDuration=duration,reservationId=42 if phase==2 else 0)
    return row


def lifecycle(sample,name,finish=False):
    actor=next(a for a in sample['actors'] if a['species']==SPECIES[name])
    values=(('MOTION_FINISHED',1,2),('CONTROL_RETURNED',int(name=='cyndaquil'),1)) if finish else (
        ('PLAN_ACCEPTED',(585<<16)|actor['target']['y'],13),('MOTION_STARTED',2,13))
    return [dict(frame=sample['frame'],kind='native',data=dict(
        sequence=sample['frame']*10+i,actorFrame=sample['frame'],actorHandle=actor['handle']['value'],
        actor={k:v for k,v in actor['handle'].items() if k!='value'},event=event,reason='OK',valueA=a,valueB=b))
        for i,(event,a,b) in enumerate(values)]


def records():
    initial=snapshot(1);rows=[dict(phase='setup',initialSnapshot=initial)];frame=1
    for action in SETUP:
        if action=='settle-mount':
            for _ in range(16):
                frame+=1;rows.append(raw(action,snapshot(frame),'setup'))
        else:
            sample=snapshot(frame);command='bind' if action.startswith('bind-') else 'party' if action.startswith('prepare-') else 'teleport' if action=='attack-tile' else 'spawn'
            receipt={}
            if command=='bind':
                name=action.removeprefix('bind-');actor=next(a for a in sample['actors'] if a['species']==SPECIES[name])
                receipt=select_current_actor(sample,actor)
            rows.append(dict(phase='setup',action=action,command=command,snapshot=sample,receipt=receipt))
    # Hit clocks are relative to the end of setup so copied samples remain valid.
    frame=17;initial=snapshot(frame);rows.append(health(initial,100,0))
    for frame in range(18,49):
        wild_hit=frame>=19;mount_hit=frame>=34
        wild_arc=32768 if 23<=frame<=34 else 0
        mount_arc=32768 if 35<=frame<=46 else 0
        sample=snapshot(frame,wild_hit=wild_hit,mount_hit=mount_hit,wild_arc=wild_arc,mount_arc=mount_arc,
                        wild_tile=407 if frame>=35 else 406 if frame>=21 else 405,mount_tile=408 if frame>=47 else 407)
        events=[]
        if frame<22:
            row=motion(sample,'snorlax',kind=1,origin=405,target=406,duration=4,elapsed=frame-17,
                       phase=2 if frame<21 else 0)
            actor=next(a for a in sample['actors'] if a['species']==143)
            actor['engineObject']['pos_z']=(405<<16)+32768+(frame-17)*16384
            row['knockbackOptions']=6 if wild_hit else 0
            row['knockbackDirection']=1 if wild_hit else 0
            row['knockbackPending']=int(wild_hit)
        else:
            row=motion(sample,'snorlax',kind=2,origin=406,target=407,duration=13,
                       elapsed=min(frame-22,13),phase=2 if frame<35 else 0,forced=True)
            row['knockbackOptions']=6;row['knockbackDirection']=1
            if frame in (22,35):events.extend(lifecycle(sample,'snorlax',finish=frame==35))
        if frame>=34:
            motion(sample,'cyndaquil',kind=2,origin=407,target=408,duration=13,
                   elapsed=min(frame-34,13),phase=2 if frame<47 else 0,forced=True)
            if frame in (34,47):events.extend(lifecycle(sample,'cyndaquil',finish=frame==47))
        for target in sample['pokemonCombat']['targets']:
            if target['hitCount']:
                target['immunityFrames']=max(0,60-(frame-(34 if target['slot']==7 else 19)))
        # Stop on the first complete pair of landings (47).
        if frame>47:break
        record=raw('observe-attacks',sample);record['events']=events;rows.append(record)
    for frame in range(48,48+TAIL_FRAMES):
        sample=snapshot(frame,wild_hit=True,mount_hit=True,wild_tile=407,mount_tile=408)
        motion(sample,'snorlax',kind=2,origin=406,target=407,duration=13,elapsed=13,phase=0,forced=True)
        motion(sample,'cyndaquil',kind=2,origin=407,target=408,duration=13,elapsed=13,phase=0,forced=True)
        for target in sample['pokemonCombat']['targets']:
            if target['hitCount']:target['immunityFrames']=max(0,60-(frame-(34 if target['slot']==7 else 19)))
        rows.append(raw('finish-knockback',sample))
    rows.append(health(sample,80,1));return rows


def replay(rows,fault=None):
    meter=PokemonCombatMeasurement(SOURCE);control=PokemonCombatNegative(fault) if fault else None
    for row in rows:
        meter.observe_record(control.mutate(row,meter.subjects) if control else row)
        if meter.failures:break
    done=meter.finish();return dict(passed=done['passed'],failures=done['failures'],
        observedFrames=meter.observed_frames,measurements={KIND:meter.result()}),control


def dispatcher_records():
    rows=records()
    rows[0]['initialSnapshot']['actors']=[]
    for row in rows:
        if row.get('action') not in ('spawn-snorlax','spawn-weepinbell'):
            continue
        sample=row['snapshot'];name=row['action'].removeprefix('spawn-')
        actor=next(a for a in sample['actors'] if a['species']==SPECIES[name])
        x,z=actor['engineObject']['pos_x']>>16,actor['engineObject']['pos_z']>>16
        locomotion=7 if name=='snorlax' else 0
        actor['logical']=actor['origin']=dict(x=x,y=z)
        encounter=dict(personality=actor['subjectIdentity'],species=actor['species'],
                       form=actor['form'],level=actor['level'])
        world=dict(sample['context'],statePointer=0x02040000,fieldPointer=0x02050000)
        common=dict(slot=actor['handle']['slot'],terrain=0,statePointer=world['statePointer'],
            fieldPointer=world['fieldPointer'],preparedPointer=0x02060000,worldContext=world,
            preparedPrefixHex=struct.pack('<iiB3xIHBB4hBB',x,z,0,encounter['personality'],
                encounter['species'],encounter['form'],encounter['level'],x,z,x,z,locomotion,0).hex(),
            preparedEncounter=encounter,position=[x,z],returnValue=1,
            startup=dict(target=[x,z],origin=[x,z],locomotion=locomotion,hopDirection=0,targetBaseY=0))
        final=dict(common,sequence=1,pairEligible=True,returnWorldContext=world)
        native=dict(common,observation='spawn-prepared',sequence=2,publicSubject=deepcopy(actor),
                    finalization=dict(status='matched',receipt=final))
        row['receipt']=dict(value=dict(slot=actor['handle']['slot'],species=actor['species'],
                           personality=actor['subjectIdentity']),
                           events=[dict(frame=sample['frame'],kind='native-observation',data=native)])
    return rows


class CombatMeasurementTest(unittest.TestCase):
    def evaluator(self):
        recipe=json.loads((ROOT/'tests/overworld/test-recipes/pokemon-hp.collision-knockback.json').read_text())
        evaluator=TestEvaluator(recipe);evaluator.install_measurements({KIND:SOURCE})
        return evaluator

    def test_dispatcher_runs_full_fixture_and_each_completed_frame_callback(self):
        evaluator=self.evaluator();callbacks=[]
        def observed(sample,current):
            self.assertIs(current,evaluator)
            self.assertEqual(current.latest,sample)
            callbacks.append((sample['frame'],current.frames))
        for row in dispatcher_records():
            result=evaluator.observe_record(row,frame_callback=observed)
            self.assertNotEqual(result['state'],'failed',result['failures'])
        result=evaluator.finish()
        self.assertTrue(result['passed'],result['failures'])
        self.assertEqual(callbacks,[(frame,0) for frame in range(2,18)]
                         +[(frame,frame-17) for frame in range(18,68)])
        self.assertEqual(result['observedFrames'],50)
        self.assertEqual(len(measurements(result,dict(sessionId='host',sessionCleanup=dict(
            sessionId='host',closed=True,errors=[])))),8)

    def test_dispatcher_callback_failure_cannot_be_rescued_by_later_landings(self):
        evaluator=self.evaluator();callbacks=[]
        def reject(sample,current):
            callbacks.append(sample['frame'])
            if sample['frame']==19:
                raise ValueError('per-frame callback rejected hit')
        for row in dispatcher_records():
            evaluator.observe_record(row,frame_callback=reject)
        result=evaluator.finish()
        self.assertFalse(result['passed'])
        self.assertEqual(callbacks[-1],19)
        self.assertIn('per-frame callback rejected hit',str(result['failures']))

    def test_dispatcher_rejects_wrong_spawn_startup_identity_and_destination_bytes(self):
        for action in ('spawn-snorlax','spawn-weepinbell'):
            for fault in ('wrong-locomotion','wrong-identity-byte','wrong-destination-byte'):
                with self.subTest(action=action,fault=fault):
                    rows=dispatcher_records()
                    row=next(r for r in rows if r.get('action')==action)
                    native=row['receipt']['events'][0]['data']
                    for receipt in (native,native['finalization']['receipt']):
                        raw=bytearray.fromhex(receipt['preparedPrefixHex'])
                        if fault=='wrong-locomotion':
                            raw[28]=0 if action=='spawn-snorlax' else 7
                            # Both decoded and native receipts agree, but this is
                            # still the wrong startup for the sealed species.
                            receipt['startup']['locomotion']=raw[28]
                        elif fault=='wrong-identity-byte':
                            raw[12]^=1
                        else:
                            raw[20]^=1
                        receipt['preparedPrefixHex']=raw.hex()
                    evaluator=self.evaluator()
                    for r in rows:
                        result=evaluator.observe_record(r)
                        if r is row:
                            break
                    self.assertEqual(result['state'],'failed')
                    self.assertIn('wild Walk spawn identity or own native destination differs',
                                  str(result['failures']))

    def test_recipe_valid_and_positive_replay_proves_both_targets(self):
        recipe=json.loads((ROOT/'tests/overworld/test-recipes/pokemon-hp.collision-knockback.json').read_text())
        self.assertEqual(validate_test(recipe)['id'],recipe['id'])
        result,_=replay(records());self.assertTrue(result['passed'],result['failures'])
        claims=measurements(result,dict(sessionId='host',sessionCleanup=dict(sessionId='host',closed=True,errors=[])))
        self.assertEqual(len(claims),8)

    def test_hit_during_walk_waits_for_forced_jump_origin(self):
        result,_=replay(records())
        self.assertTrue(result['passed'],result['failures'])
        jumps=result['measurements'][KIND]['forcedKnockbacks']
        self.assertEqual(jumps['snorlax']['hitFrame'],19)
        self.assertEqual(jumps['snorlax']['startFrame'],22)
        self.assertEqual(jumps['snorlax']['plan']['origin'],[585,406])
        self.assertEqual(jumps['snorlax']['plan']['target'],[585,407])

    def test_copied_faults_reject_missing_damage_motion_and_identity(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                result,control=replay(records(),fault);self.assertTrue(control.applied)
                self.assertFalse(result['passed']);self.assertTrue(validate_negative_result(result,fault))


if __name__=='__main__':unittest.main()
