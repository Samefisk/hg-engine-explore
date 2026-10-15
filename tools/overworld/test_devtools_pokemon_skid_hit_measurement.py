"""Bounded host replay controls. Synthetic rows are not accepted game proof."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest

from tools.overworld.test_devtools_pokemon_combat_measurement import SOURCE, snapshot as combat_snapshot, cache, raw, health
from tools.overworld.devtools_pokemon_skid_hit_measurement import (
    KIND, SCENARIO, SETUP, SETUP_SPEC, INPUTS, SETUP_STEPS, PokemonSkidHitMeasurement)
from tools.overworld.devtools_pokemon_skid_hit_proof import (
    FAULTS, PokemonSkidHitNegative, measurements, validate_negative_result)
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_walk_matrix_observer import decode_motion

ROOT = Path(__file__).resolve().parents[2]
START = 68
HIT, CRASH_END, JUMP, LAND = START+25, START+30, START+31, START+44


def snapshot(frame):
    sample = combat_snapshot(frame)
    sample['actors'] = [a for a in sample['actors'] if a['species'] != 143]
    sample['pokemonCombat']['targets'] = [t for t in sample['pokemonCombat']['targets'] if t['species'] != 143]
    mount, attacker = sample['actors']
    mount['species'] = 234
    attacker.update(subjectIdentity=105)
    attacker['handle'].update(slot=5,value=65541)
    attacker['sourceIdentity']['personality']=105
    for target in sample['pokemonCombat']['targets']:
        if target['species']==70:
            target.update(slot=5,personality=105,handle=deepcopy(attacker['handle']))
    for actor in sample['actors']:
        z = 402 if actor is attacker else 405 if frame >= LAND else 404 if frame >= HIT-1 else 407
        actor.update(logical=dict(x=586,y=z),origin=dict(x=586,y=z),target=dict(x=586,y=z),reservationId=0)
        actor['engineObject'].update(pos_x=(586<<16)+32768,pos_z=(z<<16)+32768,pos_y=65536,face_y=0,unk88_y=0,facing=1 if actor is attacker else 0)
    attacker['matchedLayerMask'] = 0 if frame <= START else 1<<25
    attacker['movementPolicy'] = dict(spotState=0)
    mount['movementPolicy'] = dict(skid=int(HIT-1 <= frame <= HIT),spotState=0)
    target = next(t for t in sample['pokemonCombat']['targets'] if t['slot']==7)
    hit = frame >= HIT
    target.update(species=234,maxHp=135,hp=135-20*hit,currentHp=135-20*hit,hitCount=int(hit),lastDamage=20*hit,
        immunityFrames=max(0,60-(frame-HIT)) if hit else 0,knockbackOptions=6 if hit else 0,
        crashPhase='NEEDS_SETTLE' if frame==HIT else 'PLAYING' if HIT<frame<CRASH_END else 'NONE',
        knockbackRawFlags=10 if frame==HIT else 12 if HIT<frame<CRASH_END else 0,
        crashMotionIdentity=28 if HIT<=frame<CRASH_END else 0,knockbackPending=0)
    sample['party'][0].update(hp=target['hp'],maxHp=135)
    sample['player'].update(x=586,y=mount['logical']['y'],pos_x=mount['engineObject']['pos_x'],pos_z=mount['engineObject']['pos_z'],pos_y=65536,face_y=32768,unk88_y=0)
    sample['pokemonCombat']['movementTimers']=[dict(handle=deepcopy(attacker['handle']),slot=1,sourceIdentity=deepcopy(attacker['sourceIdentity']),movementCooldown=9,movementEmoteTimer=0)]
    if frame >= HIT-1:
        forced = frame >= JUMP
        origin, destination = (404,405) if forced else (404,403)
        kind, duration, phase = (2,13,2 if frame<LAND else 0) if forced else (4,8,2 if frame<HIT else 5 if frame==HIT else 0)
        elapsed = min(frame-JUMP,13) if forced else 6 if frame<HIT else 7 if frame==HIT else 0
        plan = bytearray(52)
        struct.pack_into('<HBBHH4h2iHH',plan,0,1,kind,1 if forced else 3,1,901,586,origin,586,destination,65536,65536,duration,42 if forced else 28)
        plan[28:38]=bytes((1 if forced else 0,1,16 if forced else 0,0,0,0,0,2,int(forced),int(forced)))
        struct.pack_into('<4H4B',plan,40,elapsed,0,int(elapsed==duration),int(elapsed==duration),phase,2 if phase==5 else 0,int(elapsed==duration),0)
        target['motion']=decode_motion(bytes(plan))
        mount.update(origin=dict(x=586,y=origin),target=dict(x=586,y=destination),
            motionKind='HOP' if forced and frame<LAND else 'SKID' if frame<=HIT else 'NONE',
            motionPhase=target['motion']['phase'],motionElapsed=elapsed,motionDuration=duration,
            reservationId=42 if forced and frame<LAND else 28 if frame<=HIT else 0)
        if frame==HIT-1:
            # Native engine logical publication may precede shared commit.
            mount['logical']=dict(x=586,y=destination)
        if JUMP<frame<LAND:
            mount['engineObject']['face_y']=32768;sample['player']['face_y']=65536
    return sample


def events(sample, values):
    actor=next(a for a in sample['actors'] if a['species']==234)
    return [dict(frame=sample['frame'],kind='native',data=dict(sequence=sample['frame']*10+i,
        actorFrame=sample['frame'],actorHandle=actor['handle']['value'],
        actor={k:v for k,v in actor['handle'].items() if k!='value'},event=name,reason='OK',valueA=a,valueB=b))
        for i,(name,a,b) in enumerate(values)]


def configure_receipt(sample):
    actor=next(a for a in sample['actors'] if a['species']==234)
    original=bytearray(range(192))
    for offset,value in ((7,6),(12,1),(19,2),(50,10),(51,2),(64,5),(65,0xA5)):
        original[8+offset]=value
    expected=bytearray(original)
    for offset,value in ((7,4),(19,0),(50,0),(51,4),(64,1),(65,0xB4)):
        expected[8+offset]=value
    before=dict(mountStateHex=original.hex(),profileHex=original[8:88].hex(),
        bindingHex=original[88:104].hex(),sessionGeneration=1,
        clock=dict(frame=sample['frame'],nativeCycle=sample['nativeCycle']),readiness=dict(actor=deepcopy(actor)))
    after=deepcopy(before);after.update(mountStateHex=expected.hex(),profileHex=expected[8:88].hex())
    return dict(completed=True,prepared=True,acceptedProof=False,guestAdvanced=False,
        scope='prepared-idle-mounted-walk-fixture',directionMode=0,travelTime=4,
        turning='free',crashSound='wall-hit',timeVariance=0,
        changedOffsets=[7,19,50,51,64,65],before=before,after=after,
        expectedStateHex=expected.hex(),subject=select_current_actor(sample,actor))


def records():
    frame=1;initial=snapshot(frame);initial['actors']=[]
    rows=[dict(phase='setup',initialSnapshot=initial)]
    for action,(op,args) in zip(SETUP,SETUP_SPEC):
        if action in SETUP_STEPS:
            for _ in range(SETUP_STEPS[action]):
                frame+=1;rows.append(raw(action,snapshot(frame),'setup'))
            continue
        sample=snapshot(frame);receipt={}
        if op=='bind':
            actor=next(a for a in sample['actors'] if a['species']==(234 if args['subject']=='stantler' else 70))
            receipt=select_current_actor(sample,actor)
        elif op=='mount-walk.configure':
            receipt=configure_receipt(sample)
        elif op=='spawn' and args['role']=='wild':
            actor=deepcopy(sample['actors'][1]);slot=5 if args['species']==70 else [69,43,44,45,182].index(args['species'])
            actor.update(species=args['species'],level=10,subjectIdentity=100+slot,
                         logical=dict(x=args['x'],y=args['z']),origin=dict(x=args['x'],y=args['z']))
            actor['handle'].update(slot=slot,value=65536+slot)
            actor['engineObject'].update(pos_x=(args['x']<<16)+32768,pos_z=(args['z']<<16)+32768)
            actor['engineIdentity']['pointer']=0x02110000+slot*512
            actor['sourceIdentity']['personality']=100+slot
            sample['actors']=[a for a in sample['actors'] if a['species']!=actor['species']]+[actor]
            x,z=args['x'],args['z'];encounter=dict(personality=actor['subjectIdentity'],species=actor['species'],form=0,level=10)
            world=dict(sample['context'],statePointer=0x02040000,fieldPointer=0x02050000)
            locomotion=0 if args['species']==70 else 7
            common=dict(slot=slot,terrain=0,statePointer=world['statePointer'],fieldPointer=world['fieldPointer'],
                preparedPointer=0x02060000,worldContext=world,
                preparedPrefixHex=struct.pack('<iiB3xIHBB4hBB',x,z,0,encounter['personality'],encounter['species'],0,10,x,z,x,z,locomotion,0).hex(),
                preparedEncounter=encounter,position=[x,z],returnValue=1,
                startup=dict(target=[x,z],origin=[x,z],locomotion=locomotion,hopDirection=0,targetBaseY=0))
            final=dict(common,sequence=1,pairEligible=True,returnWorldContext=world)
            native=dict(common,observation='spawn-prepared',sequence=2,publicSubject=deepcopy(actor),finalization=dict(status='matched',receipt=final))
            receipt=dict(value=dict(slot=slot,species=actor['species'],personality=actor['subjectIdentity']),
                         events=[dict(frame=frame,kind='native-observation',data=native)])
        rows.append(dict(phase='setup',action=action,command=op,snapshot=sample,receipt=receipt))
    rows.append(health(snapshot(frame),100,0))
    for action,(count,_) in INPUTS.items():
        for _ in range(count):
            frame+=1;sample=snapshot(frame);row=raw(action,sample)
            if frame==HIT: row['events']=events(sample,[('WORLD_EFFECT',3,1)])
            if frame==JUMP: row['events']=events(sample,[('PLAN_ACCEPTED',(586<<16)|405,13),('MOTION_STARTED',2,13)])
            if frame==LAND: row['events']=events(sample,[('MOTION_FINISHED',1,2),('CONTROL_RETURNED',1,1)])
            rows.append(row)
    rows.append(health(sample,80,1));return rows


class SkidHitMeasurementTest(unittest.TestCase):
    def evaluator(self):
        recipe=json.loads((ROOT/'tests/overworld/test-recipes'/f'{SCENARIO}.json').read_text())
        evaluator=TestEvaluator(recipe);evaluator.install_measurements({KIND:SOURCE});return evaluator

    def replay(self, fault=None):
        evaluator=self.evaluator();control=PokemonSkidHitNegative(fault) if fault else None
        callbacks=[]
        for row in records():
            if control: row=control.mutate(row,evaluator.measurements[KIND].subjects)
            evaluator.observe_record(row,frame_callback=lambda sample,current:callbacks.append((sample['frame'],current.frames)))
            if evaluator.result()['state']=='failed': break
        return evaluator.finish(),control,callbacks

    def test_exact_recipe_dispatcher_and_crash_jump_order(self):
        evaluator=self.evaluator();self.assertEqual(validate_test(evaluator.test)['id'],SCENARIO)
        result,_,callbacks=self.replay();self.assertTrue(result['passed'],result['failures'])
        meter=result['measurements'][KIND]
        self.assertEqual(meter['crash']['hitFrame'],HIT)
        self.assertEqual(meter['crash']['groundFrame'],HIT+1)
        self.assertEqual(meter['crash']['finishFrame'],CRASH_END)
        self.assertEqual(meter['forcedKnockbacks']['stantler']['startFrame'],JUMP)
        self.assertEqual(meter['crash']['oldLogical'],dict(x=586,y=404))
        self.assertEqual(meter['forcedKnockbacks']['stantler']['plan']['origin'],[586,404])
        self.assertEqual(callbacks,[(f,0) for f in range(2,START+1)]+[(f,f-START) for f in range(START+1,START+65)])
        self.assertEqual(len(measurements(result,dict(sessionId='host',sessionCleanup=dict(sessionId='host',closed=True,errors=[])))),7)

    def test_copied_controls_reject_their_named_failure(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                result,control,_=self.replay(fault)
                self.assertTrue(control.applied)
                self.assertFalse(result['passed'],result['failures'])
                self.assertTrue(validate_negative_result(result,fault),result['failures'])

    def test_wrong_input_and_timer_admission_are_rejected(self):
        recipe=self.evaluator().test
        recipe['actions'][2]['args']['keys']=['LEFT']
        with self.assertRaisesRegex(ValueError,'exact natural head2'): validate_test(recipe)
        meter=PokemonSkidHitMeasurement(SOURCE)
        for row in records():
            if row.get('action')=='arm-contact':
                row['samples'][-1]['pokemonCombat']['movementTimers'][0]['movementCooldown']=17
            elif row.get('action')=='before-contact':
                row['snapshot']['pokemonCombat']['movementTimers'][0]['movementCooldown']=17
            meter.observe_record(row)
            if meter.failures: break
        self.assertIn('natural cooldown9',str(meter.failures))

    def test_missing_endpoint_cache_cannot_supply_attack_profile_proof(self):
        evaluator=self.evaluator()
        for row in records():
            if row.get('phase')=='observe' and row.get('samples'):
                row.pop('profileCache')
            result=evaluator.observe_record(row)
            if result['state']=='failed': break
        self.assertEqual(result['state'],'failed')
        self.assertIn('combat attack profile has no coherent native cache',str(result['failures']))

    def test_configure_receipt_requires_zero_variance_and_keeps_packed_neighbors(self):
        for fault in ('missing-variance','nonzero-variance','lost-diagonal','changed-other-option','changed-binding','advanced-clock'):
            with self.subTest(fault=fault):
                evaluator=self.evaluator()
                for row in records():
                    if row.get('action')=='configure-mount':
                        q=row['receipt']
                        if fault=='missing-variance':q.pop('timeVariance')
                        elif fault=='nonzero-variance':q['timeVariance']=2
                        elif fault=='advanced-clock':q['after']['clock']['frame']+=1
                        else:
                            actual=bytearray.fromhex(q['after']['mountStateHex'])
                            if fault=='lost-diagonal':actual[72]=0
                            elif fault=='changed-other-option':actual[73]^=4
                            else:actual[88]^=1
                            q['after'].update(mountStateHex=actual.hex(),profileHex=actual[8:88].hex(),bindingHex=actual[88:104].hex())
                            q['expectedStateHex']=actual.hex()
                    result=evaluator.observe_record(row)
                    if result['state']=='failed':break
                self.assertEqual(result['state'],'failed')
                self.assertIn('skid-hit configure',str(result['failures']))

    def test_uncommitted_target_grounding_is_rejected_even_if_public_logical_was_target(self):
        prior=snapshot(HIT-1)
        actor=next(a for a in prior['actors'] if a['species']==234)
        hp=next(t for t in prior['pokemonCombat']['targets'] if t['species']==234)
        self.assertEqual(actor['logical'],dict(x=586,y=403))
        self.assertEqual(hp['motion']['commitPublished'],0)
        evaluator=self.evaluator()
        for row in records():
            for sample in row.get('samples',[]):
                if sample['frame']==HIT+1:
                    actor=next(a for a in sample['actors'] if a['species']==234)
                    actor['engineObject']['pos_z']=(403<<16)+32768
                    sample['player']['pos_z']=(403<<16)+32768
            result=evaluator.observe_record(row)
            if result['state']=='failed': break
        self.assertEqual(result['state'],'failed')
        self.assertIn('Crash did not restore the current logical ground and shared mounted seat',str(result['failures']))

    def test_filler_appear_hop_keeps_exact_startup_identity_and_destination_guards(self):
        for action in ('spawn-filler-69','spawn-filler-43','spawn-filler-44','spawn-filler-45','spawn-filler-182'):
            for fault in ('none-startup','wrong-identity','wrong-destination'):
                with self.subTest(action=action,fault=fault):
                    evaluator=self.evaluator()
                    for row in records():
                        if row.get('action')==action:
                            native=row['receipt']['events'][0]['data']
                            for receipt in (native,native['finalization']['receipt']):
                                prefix=bytearray.fromhex(receipt['preparedPrefixHex'])
                                if fault=='none-startup': prefix[28]=0;receipt['startup']['locomotion']=0
                                elif fault=='wrong-identity': prefix[12]^=1
                                else: prefix[20]^=1
                                receipt['preparedPrefixHex']=prefix.hex()
                        result=evaluator.observe_record(row)
                        if row.get('action')==action: break
                    self.assertEqual(result['state'],'failed')
                    self.assertIn('wild Walk spawn identity or own native destination differs',str(result['failures']))


if __name__=='__main__': unittest.main()
