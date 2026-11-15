"""T83 checker controls. Copied positive data are not game acceptance.

The retained red fixture is actual ROM3709 input/native memory. The small
positive stream below extends its native plan/poses to exercise the checker
and fault routing; it does not claim that any ROM has executed that stream.
"""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.overworld.devtools_mount_airborne_measurement import (
    KIND,TEST,SETUP,ACTION_SPEC,MountAirborneMeasurement,validate_recipe)
from tools.overworld.devtools_mount_airborne_proof import (
    FAULTS,MountAirborneNegative,validate_negative_result,measurements)
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.normal_play_observer import arc_height

RED=json.loads((ROOT/'tools/overworld/fixtures/mount_airborne_3709_red.json').read_text())


def source():
    s=RED['snapshots'][0]
    return dict(contractVersion=1,romSha256=s['romSha256'],
        overlaySha256=s['pokemonCombat']['identity']['overlaySha256'],profileSha256='a'*64)


def row(action,samples,events,previous):
    intervals=[];frame=previous['frame'];cycle=previous['nativeCycle']
    for s in samples:
        while cycle<s['nativeCycle']:
            cycle+=1
            if cycle==s['nativeCycle']:frame=s['frame']
            intervals.append(dict(completedGameFrame=frame,cpuNs=1,wallNs=1))
    spec=next(a for a in ACTION_SPEC if a[0]==action)
    return dict(phase='observe',action=action,requestedInput=dict(keys=spec[2]),samples=deepcopy(samples),
        completedGameFrames=len(samples),observedFieldFrames=len(samples),nativeCycles=len(intervals),
        cycleIntervals=intervals,events=deepcopy(events))


def armed():
    meter=MountAirborneMeasurement(source());s=deepcopy(RED['snapshots'][0])
    meter.arm(s,s['actors'][0]);meter.setup_index=len(SETUP)
    return meter


def positive_rows(*,landed_cleanup=True,remount_lag=False):
    """A synthetic completion and role sequence copied from measured native data."""
    initial=deepcopy(RED['snapshots'][0]);template=deepcopy(RED['snapshots'][8])
    rows=[];previous=initial;sequence=9
    owner=template['actors'][0]['handle'];pid=template['actors'][0]['subjectIdentity']
    base_raw=bytes.fromhex(template['pokemonCombat']['targets'][0]['motion']['rawHex'])
    plans=[deepcopy(template['pokemonCombat']['targets'][0]['motion']['plan'])]
    plans.append(dict(plans[0],origin=[563,375],target=[564,375],direction=3,facing=3,
                      startBaseY=plans[0]['targetBaseY'],targetBaseY=plans[0]['startBaseY'],reservationId=66))
    def snap(keys=0,new=None):
        nonlocal previous
        s=deepcopy(template);s['frame']=previous['frame']+1;s['nativeCycle']=previous['nativeCycle']+3;s['actorFrame']=previous['actorFrame']+1
        s['pokemonCombat'].update(frame=s['frame'],nativeCycle=s['nativeCycle'])
        s['selector'].update(rawHeld=keys,heldKeys=keys,rawNew=keys&~previous['selector']['rawHeld'] if new is None else new,
                             newKeys=keys&~previous['selector']['rawHeld'] if new is None else new,
                             state=0,highlight=2,activeFollowerPartySlot=2)
        s['selector']['queue'].update(request=0,count=0,commands=0,headIssued=0)
        return s
    def motion(s,number,elapsed,phase=2,kind='HOP',control=1):
        p=plans[number];a=s['actors'][0];engine=a['engineObject'];player=s['player']
        raw=bytearray(base_raw)
        struct.pack_into('<HBBHH',raw,0,1,2,p['facing'],p['fieldEpoch'],p['behaviorFingerprint'])
        struct.pack_into('<4h2i',raw,8,*p['origin'],*p['target'],p['startBaseY'],p['targetBaseY'])
        struct.pack_into('<HH',raw,24,p['duration'],p['reservationId'])
        raw[28]=p['direction'];struct.pack_into('<H',raw,40,elapsed);raw[48]=phase;raw[51]=1 if phase==6 else 0
        if phase==0:struct.pack_into('<H',raw,46,2+number);raw[50]=1
        native=decode_motion(bytes(raw));s['pokemonCombat']['targets'][0]['motion']=native
        a.update(inputOwnership=control,motionKind=kind,motionKindId=2 if kind=='HOP' else 0,
            motionPhase=native['phase'],motionPhaseId=phase,motionElapsed=elapsed,motionDuration=p['duration'],
            reservationId=p['reservationId'] if phase in (2,3) else 0,origin=dict(zip(('x','y'),p['origin'])),
            target=dict(zip(('x','y'),p['target'])),logical=dict(zip(('x','y'),p['target'])),commitSequence=1+number+(phase==0))
        def lerp(x,y):return x+int(Fraction((y-x)*elapsed,p['duration']))
        for pose in (engine,player):
            pose.update(x=p['target'][0],y=p['target'][1],pos_x=lerp((p['origin'][0]<<16)+32768,(p['target'][0]<<16)+32768),
                pos_z=(375<<16)+32768,pos_y=lerp(p['startBaseY'],p['targetBaseY']),unk88_y=0)
        engine['face_y']=arc_height(elapsed,p['duration'])//16*p['arcHeightQ4']
        player['face_y']=engine['face_y']+32768 if control else 0
        return s
    def event(s,name,a,b,reason=0):
        nonlocal sequence
        sequence+=1;e=deepcopy(next(e for e in RED['events'] if e['data']['event']=='MOTION_STARTED'))
        e['frame']=s['frame'];e['data'].update(sequence=sequence,event=name,valueA=a,valueB=b,reasonId=reason)
        return e
    def add(action,samples,events=()):
        nonlocal previous
        rows.append(row(action,samples,list(events),previous));previous=deepcopy(samples[-1])
    # Preserve the actual eight pre-failure flight samples and all native events.
    first=deepcopy(RED['snapshots'][1:9]);add('left-to-tree',first,[e for e in RED['events'] if e['frame']<=first[-1]['frame']])
    s=motion(snap(4),0,9);add('air-select',[s])
    neutral=[];events=[]
    for elapsed in range(10,14):
        s=motion(snap(),0,elapsed,3 if elapsed==13 else 2);neutral.append(s);previous=s
    s=motion(snap(),0,13,0,'NONE');events += [event(s,'LOGICAL_COMMIT',2,2),event(s,'MOTION_FINISHED',2,2),event(s,'CONTROL_RETURNED',1,2)]
    neutral.append(s);previous=s
    for _ in range(27):s=motion(snap(),0,13,0,'NONE');neutral.append(s);previous=s
    previous=rows[-1]['samples'][-1];add('land-without-delayed-toggle',neutral,events)
    s=motion(snap(4),0,13,0,'NONE',0);add('fresh-ground-select',[s])
    s=motion(snap(),0,13,0,'NONE',0);s['actors'][0].update(role='FOLLOWER',roleId=2);add('wait-dismounted',[s])
    s=motion(snap(),0,13,0,'NONE',0);s['actors'][0].update(role='FOLLOWER',roleId=2);add('release-select-before-remount',[s])
    press=[]
    for index in range(2):
        s=deepcopy(previous);s.update(frame=previous['frame']+1,nativeCycle=previous['nativeCycle']+3)
        keys=0 if remount_lag and index==0 else 4
        new=keys&~previous['selector']['rawHeld']
        s['selector'].update(rawHeld=keys,heldKeys=keys,rawNew=new,newKeys=new)
        s['pokemonCombat'].update(frame=s['frame'],nativeCycle=s['nativeCycle'])
        press.append(s);previous=s
    previous=rows[-1]['samples'][-1];add('fresh-remount-select',press)
    s=motion(snap(),0,13,0,'NONE');add('wait-remounted',[s])
    s=motion(snap(16),1,1);events=[event(s,'INTENT_CREATED',2,1),event(s,'PLAN_ACCEPTED',0,13),event(s,'MOTION_STARTED',2,13)];add('right-hop-for-y',[s],events)
    s=motion(snap(2048),1,2);s['selector'].update(state=2,highlight=2);add('open-y-in-flight',[s])
    s=motion(snap(2560),1,3);s['selector'].update(state=2,highlight=1);add('choose-cyndaquil',[s])
    s=motion(snap(),1,4);s['selector'].update(highlight=1);s['selector']['queue']['request']=0x81;add('confirm-y-in-flight',[s])
    travel=[];events=[]
    for elapsed in range(5,14):
        phase=6 if elapsed==13 and landed_cleanup else 3 if elapsed==13 else 2
        s=motion(snap(),1,elapsed,phase,control=0 if phase==6 else 1);s['selector']['highlight']=1
        s['selector']['queue']['request']=0x81
        if phase==6:
            s['selector']['queue'].update(request=0,count=2,commands=0x17)
            events += [event(s,'MOTION_CANCELED',2,2,1),event(s,'CONTROL_RETURNED',0,2,1)]
        travel.append(s);previous=s
    if not landed_cleanup:
        s=motion(snap(),1,13,0,'NONE');s['selector']['queue'].update(request=0,count=2,commands=0x17)
        events += [event(s,'LOGICAL_COMMIT',3,2),event(s,'MOTION_FINISHED',3,2),event(s,'CONTROL_RETURNED',1,3)]
        travel.append(s);previous=s
    s=snap();a=s['actors'][0];a.update(species=155,role='FOLLOWER',roleId=2,subjectIdentity=next(p['personality'] for p in s['party'] if p['slot']==1),motionKind='NONE',motionPhase='IDLE')
    s['selector'].update(highlight=1,activeFollowerPartySlot=1);travel.append(s)
    previous=rows[-1]['samples'][-1];add('land-and-switch',travel,events)
    stable=[]
    for _ in range(24):
        t=deepcopy(s);t.update(frame=previous['frame']+1,nativeCycle=previous['nativeCycle']+3);stable.append(t);previous=t
    previous=rows[-1]['samples'][-1];add('verify-no-repeat',stable)
    return rows


def run(rows,negative=None):
    meter=armed()
    for record in rows:
        if negative:record=negative.mutate(record,{})
        result=meter.observe_record(record)
        if result['failures']:break
    return meter.finish()


class MountAirborneTests(unittest.TestCase):
    def test_actual_3709_air_select_failure_is_rejected(self):
        meter=armed();ss=RED['snapshots']
        result=meter.observe_record(row('left-to-tree',ss[1:9],[e for e in RED['events'] if e['frame']<=ss[8]['frame']],ss[0]))
        self.assertFalse(result['failures'])
        result=meter.observe_record(row('air-select',ss[9:10],[e for e in RED['events'] if e['frame']==ss[9]['frame']],ss[8]))
        self.assertTrue(result['failures'])
        self.assertIn('current mount binding/input owner differs',str(result['failures']))
        self.assertFalse(result['passed'])

    def test_copied_controls_cover_both_valid_landed_completion_paths(self):
        for cleanup in (False,True):
            with self.subTest(landed_cleanup=cleanup):
                result=run(positive_rows(landed_cleanup=cleanup))
                self.assertTrue(result['passed'],result['failures'])
                self.assertFalse(result['acceptedProof'])
                replay=dict(passed=True,failures=[],observedFrames=result['observedFrames'],measurements={KIND:result})
                record=dict(sessionId='copied-host-control',sessionCleanup=dict(sessionId='copied-host-control',closed=True,errors=[]))
                self.assertEqual(len(measurements(replay,record)),4)

    def test_every_copied_fault_fails_for_its_declared_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                negative=MountAirborneNegative(fault)
                result=run(positive_rows(),negative)
                self.assertTrue(negative.applied)
                self.assertFalse(result['passed'],result)
                validate_negative_result(result,fault)

    def test_recipe_is_finite_and_does_not_replace_the_saved_party(self):
        recipe=json.loads((ROOT/'tests/overworld/test-recipes'/f'{TEST}.json').read_text())
        validate_recipe(recipe)
        bad=deepcopy(recipe);bad['actions'][1]['args']['keys']=[]
        with self.assertRaisesRegex(ValueError,'finite normal Select/Y trigger'):validate_recipe(bad)
        bad=deepcopy(recipe);bad['setup'][2]['args']['slot']=0
        with self.assertRaisesRegex(ValueError,'finite normal Select/Y trigger'):validate_recipe(bad)

    def test_explicit_release_is_required_by_the_real_recipe_contract(self):
        recipe=json.loads((ROOT/'tests/overworld/test-recipes'/f'{TEST}.json').read_text())
        index=next(i for i,a in enumerate(recipe['actions']) if a['id']=='release-select-before-remount')
        for fault in ('missing','held','too-long'):
            bad=deepcopy(recipe)
            if fault=='missing':bad['actions'].pop(index)
            elif fault=='held':bad['actions'][index]['args']['keys']=['SELECT']
            else:bad['actions'][index]['args']['frames']=2
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'finite normal Select/Y trigger'):
                validate_recipe(bad)

    def test_last_wait_sample_cannot_stand_in_for_a_real_select_release(self):
        rows=positive_rows()
        for action in ('wait-dismounted','release-select-before-remount'):
            sample=next(r for r in rows if r['action']==action)['samples'][0]
            # Real3710 tail: the first neutral wait still samples held Select.
            sample['selector'].update(rawHeld=4,heldKeys=4,rawNew=0,newKeys=0)
        result=run(rows)
        self.assertFalse(result['passed'])
        self.assertIn('Select was not released before the fresh remount press',str(result['failures']))

    def test_remount_accepts_one_real_edge_with_or_without_one_queue_lag(self):
        for lag in (False,True):
            with self.subTest(first_queue_neutral=lag):
                result=run(positive_rows(remount_lag=lag))
                self.assertTrue(result['passed'],result['failures'])
                self.assertFalse(result['acceptedProof'])
                self.assertIsInstance(result['remountSelectFrame'],int)

    def test_remount_rejects_missing_invented_and_repeated_press_edges(self):
        for fault,reason in (('missing','native input differs'),
                             ('invented','first remount queue'),
                             ('repeated','repeated its press edge')):
            rows=positive_rows(remount_lag=fault!='repeated')
            samples=next(r for r in rows if r['action']=='fresh-remount-select')['samples']
            if fault=='missing':samples[1]['selector'].update(rawHeld=0,heldKeys=0,rawNew=0,newKeys=0)
            elif fault=='invented':samples[0]['selector'].update(rawNew=4,newKeys=4)
            else:samples[1]['selector'].update(rawNew=4,newKeys=4)
            result=run(rows)
            with self.subTest(fault=fault):
                self.assertFalse(result['passed'])
                self.assertIn(reason,str(result['failures']))

    def test_remount_canceled_terminal_still_needs_exact_grounded_native_binding(self):
        rows=positive_rows();index=next(i for i,r in enumerate(rows) if r['action']=='wait-remounted')
        for fault in (None,'binding','pose','native-owner','airborne','reservation'):
            copied=deepcopy(rows[:index+1]);sample=copied[-1]['samples'][0];actor=sample['actors'][0]
            target=sample['pokemonCombat']['targets'][0]
            raw=bytearray.fromhex(target['motion']['rawHex']);raw[48]=6;raw[51]=16
            target['motion']=decode_motion(bytes(raw));actor.update(motionPhase='CANCELED',motionPhaseId=6)
            if fault=='binding':actor['engineIdentity']['pointer']+=4
            elif fault=='pose':actor['engineObject']['face_y']=4096
            elif fault=='native-owner':target['handle']=dict(target['handle'],generation=99)
            elif fault=='airborne':actor.update(motionKind='HOP',motionKindId=2)
            elif fault=='reservation':actor['reservationId']=77
            meter=armed()
            for record in copied:result=meter.observe_record(record)
            with self.subTest(fault=fault):
                self.assertEqual(meter.stage('remounted'),fault is None,result['failures'])
                self.assertFalse(result['passed'])

    def test_pending_native_spawn_cannot_select_or_credit_the_new_follower(self):
        for pending in ('queue','release','both'):
            rows=positive_rows();index=next(i for i,r in enumerate(rows) if r['action']=='land-and-switch')
            rows=deepcopy(rows[:index+1]);sample=rows[-1]['samples'][-1]
            sample['actors'][0].update(identityVerified=False,presentationAttached=False)
            if pending in ('queue','both'):sample['selector']['queue'].update(count=1,commands=2,headIssued=1)
            if pending in ('release','both'):sample['selector']['followerReleaseState']=4
            meter=armed()
            for record in rows:result=meter.observe_record(record)
            with self.subTest(pending=pending):
                self.assertEqual(result['failures'],[])
                self.assertFalse(meter.stage('switched'))
                self.assertFalse(result['passed'])

    def test_completed_native_switch_still_requires_the_verified_saved_follower(self):
        for fault in ('identity','presentation','saved-pid','missing'):
            rows=positive_rows();index=next(i for i,r in enumerate(rows) if r['action']=='land-and-switch')
            rows=deepcopy(rows[:index+1]);sample=rows[-1]['samples'][-1];actor=sample['actors'][0]
            if fault=='identity':actor['identityVerified']=False
            elif fault=='presentation':actor['presentationAttached']=False
            elif fault=='saved-pid':actor['subjectIdentity']^=1
            else:sample['actors']=[]
            meter=armed()
            for record in rows:result=meter.observe_record(record)
            with self.subTest(fault=fault):
                self.assertFalse(meter.stage('switched'))
                self.assertFalse(result['passed'])
                if fault!='missing':self.assertTrue(result['failures'])

    def test_incomplete_observation_never_passes(self):
        meter=armed()
        self.assertFalse(meter.finish()['passed'])
        self.assertFalse(meter.result()['acceptedProof'])


if __name__=='__main__':unittest.main()
