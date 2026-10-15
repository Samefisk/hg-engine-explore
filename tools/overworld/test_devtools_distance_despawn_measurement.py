"""Copied-stream controls only; native map geometry remains a live prerequisite."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest

HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'tools/overworld/devtools_records.py').exists())
sys.path.insert(0,str(ROOT))
for name in ('devtools_distance_despawn_measurement','devtools_distance_despawn_proof'):
    spec=importlib.util.spec_from_file_location('tools.overworld.'+name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
from tools.overworld.devtools_distance_despawn_measurement import CASES,KINDS,ROUTE,CITY,REMOTE,CARGO,CARRIER,EXIT,BOUNDARY,DistanceDespawnMeasurement,setup,actions
from tools.overworld.devtools_distance_despawn_proof import DistanceDespawnNegative,faults,measurements,validate_negative_result
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor

SOURCE=dict(contractVersion=1,romSha256='a'*64,overlaySha256='b'*64,helperAddress=0x23D9000,helperEntrySha256='c'*64)


def sample(frame,kind=ROUTE):
    _,map_id,x,y=CASES[kind]
    cx,cy=CARGO[kind];gx,gy=CARRIER[kind];rx,ry=REMOTE[kind]
    actors=[actor(179,0,179000,cy),actor(74,1,74000,gy),actor(143,2,143000,ry)]
    for a,ax in zip(actors,(cx,gx,rx)):
        for k in ('logical','origin','target'):a[k]['x']=ax
        a['engineObject'].update(x=ax,y=a['logical']['y'],pos_x=(ax<<16)+32768,pos_y=65536,unk88_y=0,facing=3,flags=1)
        a['behaviorFingerprint']=1234;a['inputOwnership']=0
    ordinary=actors[2]
    if frame>=2:
        ordinary.update(origin=dict(x=rx,y=ry),target=dict(x=rx+1,y=ry),motionDuration=4,motionElapsed=min(frame-2,4))
        ordinary['engineObject']['pos_x']+=(min(frame-2,4)*16384)
        if frame<=6:
            ordinary.update(motionKind='WALK',motionPhase='MOVING' if frame<6 else 'COMMIT_PENDING',reservationId=9 if frame<6 else 0)
        else:
            ordinary.update(logical=dict(x=rx+1,y=ry),commitSequence=1)
            ordinary['engineObject']['x']=rx+1
    raw_cargo=raw_handle(actors[0]['handle'])+bytes([2,0])+struct.pack('<HIBBBB',57932,0,20,0,1,0)
    binding=dict(bound=True,flags=1,targetCurrent=True,target=dict(kind='ACTOR',actor=deepcopy(actors[0]['handle'])),rawHex=raw_cargo.hex(),
                 sourceConditionId=57932,expiresAt=0,sourceApplication=20,lifetime=0,reason=0)
    raw_trigger=bytes(12)+bytes([1,0])+struct.pack('<HIBBBB',24737,0,20,0,1,0)
    trigger=dict(bound=True,flags=1,targetCurrent=True,target=dict(kind='PLAYER',actor=None),rawHex=raw_trigger.hex(),
                 sourceConditionId=24737,expiresAt=0,sourceApplication=20,lifetime=0,reason=0)
    targets=[0]*10;targets[1]=1;native=bytes(targets)+struct.pack('<3H',1,2,0)
    carrier=dict(handle=deepcopy(actors[1]['handle']),role='WILD',available=True,bindings=dict(trigger=trigger,cargo=binding),
                 rawBindingsHex=(raw_handle(actors[1]['handle'])+raw_trigger+raw_cargo).hex(),
                 throw=dict(targetRaw=1,targetSlot=0,carried=False,windup=False,targeted=False,carrier=True,recovering=False))
    if frame==8:actors.pop()
    result=dict(frame=frame,actorFrame=frame,nativeCycle=1000+frame,fieldAvailable=True,romSha256=SOURCE['romSha256'],observationBoundary=BOUNDARY,
        context=dict(mapId=map_id,fieldEpoch=1,mapGeneration=1),fieldControl=dict(taskPointer=0,fieldPointer=0x2200000),actors=actors,player=dict(x=x,y=y+EXIT[kind]),
        nativeObservation=dict(coverageComplete=True,error=None,eventsDropped=0,calls={'distance-maintenance':dict(address=SOURCE['helperAddress'],entrySha256=SOURCE['helperEntrySha256'],nonmatchingEntries=0)}),
        pokemonCombat=dict(available=True,frame=frame,nativeCycle=1000+frame,identity=dict(romSha256=SOURCE['romSha256'],overlaySha256=SOURCE['overlaySha256']),
          interactions=dict(available=True,schemaVersion=1,frame=frame,nativeCycle=1000+frame,observationBoundary=BOUNDARY,fieldSystem=0x2200000,
            identity=dict(romSha256=SOURCE['romSha256']),carriers=[carrier],throwState=dict(targets=targets,targetMask=1,carrierMask=2,recoveringMask=0,rawHex=native.hex()))))
    return result


def state(kind,count,deleted=False):
    _,map_id,x,y=CASES[kind];cx,cy=CARGO[kind];gx,gy=CARRIER[kind];rx,ry=REMOTE[kind];raw=bytearray(336);struct.pack_into('<IHBB',raw,0,0x4F574450,int(deleted),int(deleted),0)
    if deleted:
        struct.pack_into('<III5H5h6B',raw,16,0x2100200,1,143000,1,map_id,map_id,1,1,rx+1,ry,x,y+EXIT[kind],0xE2,3,1,2,max(abs(rx+1-x),abs(ry-y-EXIT[kind])),61,0xE2)
    targets=[0]*10;targets[1]=1;far=[0]*10;far[2]=count
    return dict(lastKnownX=[cx,gx,rx+1]+[0]*7,lastKnownY=[cy,gy,ry]+[0]*7,farSamples=far,managerRestoreMask=0,
        distanceDespawnPendingMask=4 if count==2 else 0,throwState=dict(targets=targets,targetMask=1,carrierMask=2,recoveringMask=0),
        telemetrySequence=int(deleted),telemetryWriteIndex=int(deleted),telemetryHex=raw.hex())


def receipt(frame,kind,sequence,before,after,deferred):
    d=dict(observation='distance-maintenance',sequence=sequence,entryActorFrame=frame-1,returnActorFrame=frame-1,
        entryNativeCycle=1000+frame,returnNativeCycle=1000+frame,setupMode='prepared',returnValue=0,
        fieldPointer=0x2200000,statePointer=0x23D7FD8,runtimePointer=0x22B7000,presentationPointer=0x22B9000,telemetryPointer=0x22B9040,resetSlotPointer=0x23D6001,
        worldContext=dict(fieldPointer=0x2200000,statePointer=0x23D7FD8,**sample(frame,kind)['context']),
        hardProtectedMask=3,movementDeferredMask=4 if deferred else 0,before=before,after=after,
        scope='native scheduled distance-maintenance entry/return',diagnosticOnly=True,acceptedProof=False)
    return dict(frame=frame,kind='native-observation',data=d)


def stream(kind=ROUTE):
    values=[sample(f,kind) for f in range(2,9)];handle=values[0]['actors'][2]['handle'];events=[]
    for f,names in ((2,('INTENT_CREATED','MOTION_STARTED')),(7,('LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED'))):
        for i,name in enumerate(names):events.append(dict(frame=f,kind='native',data=dict(event=name,actorFrame=f,sequence=f*10+i,
            actorHandle=handle['value'],actor={k:v for k,v in handle.items() if k!='value'})))
    events.extend((receipt(3,kind,1,state(kind,0),state(kind,1),True),receipt(6,kind,2,state(kind,1),state(kind,2),True),
                   receipt(8,kind,3,state(kind,2),state(kind,0,True),False)))
    return [dict(phase='observe',action='scheduled-distance-removal',samples=values,events=events,completedGameFrames=7,observedFieldFrames=7,nativeCycles=7,
        cycleIntervals=[dict(completedGameFrame=s['frame'],cpuNs=1,wallNs=1) for s in values])]


def two_walk_stream(kind=ROUTE):
    """A completed first Walk followed by the actual far-confirmed owner."""
    rx,ry=REMOTE[kind];direction=1 if kind==ROUTE else -1;end_x=rx+1+direction;values=[];events=[]
    for frame in range(2,15):
        snap=sample(min(frame,7),kind);snap.update(frame=frame,actorFrame=frame,nativeCycle=1000+frame)
        snap['pokemonCombat'].update(frame=frame,nativeCycle=1000+frame)
        snap['pokemonCombat']['interactions'].update(frame=frame,nativeCycle=1000+frame)
        a=snap['actors'][2]
        if frame>=8:
            elapsed=min(frame-8,4)
            a.update(origin=dict(x=rx+1,y=ry),target=dict(x=end_x,y=ry),motionDuration=4,motionElapsed=elapsed,
                logical=dict(x=rx+1+direction*int(frame>=13),y=ry),commitSequence=1+int(frame>=13),
                motionKind='WALK' if frame<=12 else 'NONE',
                motionPhase='MOVING' if frame<12 else 'COMMIT_PENDING' if frame==12 else 'IDLE',
                reservationId=10 if frame<12 else 0)
            a['engineObject'].update(x=rx+1+direction*int(frame>=13),pos_x=((rx+1)<<16)+32768+direction*elapsed*16384,facing=3 if direction==1 else 2)
        if frame==14:snap['actors'].pop()
        values.append(snap)
    handle=values[0]['actors'][2]['handle']
    for frame,names in ((2,('INTENT_CREATED','MOTION_STARTED')),(7,('LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED')),
                        (8,('INTENT_CREATED','MOTION_STARTED')),(13,('LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED'))):
        for i,name in enumerate(names):events.append(dict(frame=frame,kind='native',data=dict(event=name,actorFrame=frame,
            sequence=frame*10+i,actorHandle=handle['value'],actor={k:v for k,v in handle.items() if k!='value'})))
    for frame,seq,before,after,deferred in ((10,1,0,1,True),(12,2,1,2,True),(14,3,2,0,False)):
        old=state(kind,before);new=state(kind,after,frame==14)
        for value in (old,new):
            value['lastKnownX'][2]=end_x
            if value['telemetrySequence']:
                raw=bytearray.fromhex(value['telemetryHex']);struct.pack_into('<h',raw,16+22,end_x)
                raw[16+35]=max(abs(end_x-CASES[kind][2]),abs(ry-CASES[kind][3]-EXIT[kind]))
                value['telemetryHex']=raw.hex()
        events.append(receipt(frame,kind,seq,old,new,deferred))
    return [dict(phase='observe',action='scheduled-distance-removal',samples=values,events=events,
        completedGameFrames=len(values),observedFieldFrames=len(values),nativeCycles=len(values),
        cycleIntervals=[dict(completedGameFrame=s['frame'],cpuNs=1,wallNs=1) for s in values])]


def evaluate(rows,kind=ROUTE,negative=None):
    recipe=json.loads((HERE.parents[1]/'tests/overworld/test-recipes'/ (CASES[kind][0]+'.json')).read_text())
    meter=DistanceDespawnMeasurement(recipe,SOURCE);initial=sample(1,kind);meter.latest=deepcopy(initial);meter.context=deepcopy(initial['context'])
    meter.setup_index=len(setup(kind));meter.action_index=len(actions(kind))-1
    meter.subjects={n:select_current_actor(initial,a) for n,a in zip(('cargo','carrier','unrelated'),initial['actors'])}
    for row in rows:meter.observe_record(negative.mutate(row,meter.subjects) if negative else row)
    result=meter.finish()
    return dict(passed=result['passed'],failures=result['failures'],observedFrames=result['observedFrames'],measurements={kind:result})


def current_meter(kind, action_index=0):
    recipe=json.loads((ROOT/'tests/overworld/test-recipes'/(CASES[kind][0]+'.json')).read_text())
    meter=DistanceDespawnMeasurement(recipe,SOURCE);initial=sample(1,kind)
    meter.latest=deepcopy(initial);meter.context=deepcopy(initial['context'])
    meter.setup_index=len(setup(kind));meter.action_index=action_index
    meter.subjects={n:select_current_actor(initial,a) for n,a in zip(('cargo','carrier','unrelated'),initial['actors'])}
    return meter,SimpleNamespace(measurements={kind:meter},subjects=meter.subjects)


def chunk(row, action, first, last):
    values=[deepcopy(s) for s in row['samples'] if first<=s['frame']<=last]
    return dict(phase='observe',action=action,samples=values,
        events=[deepcopy(e) for e in row['events'] if first<=e['frame']<=last],
        completedGameFrames=len(values),observedFieldFrames=len(values),nativeCycles=len(values),
        cycleIntervals=[deepcopy(c) for c in row['cycleIntervals'] if first<=c['completedGameFrame']<=last])


def native_identities(snap):
    """Give the copied actors the real generic manager/source fields."""
    for a in snap['actors']:
        slot=a['handle']['slot'];pointer=0x2100000+slot*0x100;map_id=snap['context']['mapId']
        a['sourceIdentity']=dict(active=1,species=a['species'],personality=a['subjectIdentity'],
            encounter_generation=a['handle']['encounterGeneration'],object_id=0xE0+slot,
            map_id=map_id,object=pointer)
        a['engineIdentity']=dict(pointer=pointer,in_manager=True,active=True,script_id=2074,
            object_id=0xE0+slot,object_map_id=map_id,current_map_id=map_id,
            current_manager=0x2110000,object_manager=0x2110000,manager_index=slot)
    return snap


def pickup_stream(kind=ROUTE, encoded=129, start=4):
    rows=stream(kind)
    for snap in rows[0]['samples']:
        if snap['frame'] < start:continue
        value=snap['pokemonCombat']['interactions'];state=value['throwState'];row=value['carriers'][0]
        state['targets'][1]=encoded;state['rawHex']=(bytes(state['targets'])+struct.pack('<3H',state['targetMask'],state['carrierMask'],state['recoveringMask'])).hex()
        row['throw'].update(targetRaw=encoded,carried=bool(encoded&128),windup=bool(encoded&64))
        snap['actors'][0]['engineObject'].update({k:snap['actors'][1]['engineObject'][k] for k in ('x','y','pos_x','pos_z')})
    for event in rows[0]['events']:
        if event['kind']=='native-observation' and event['frame'] >= start:
            for name in ('before','after'):event['data'][name]['throwState']['targets'][1]=encoded
    return rows


class DistanceTests(unittest.TestCase):
    def test_missing_first_control_hits_exact_omitted_wait_entry_guard(self):
        for kind in KINDS:
            meter,_=current_meter(kind);original=stream(kind)[0]
            first=chunk(original,'walk-first-tile-settle',2,3)
            for snap in first['samples']:snap['player']['y']=CASES[kind][3]+EXIT[kind]//2
            negative=DistanceDespawnNegative(kind,kind+':missing-first-sample')
            changed=negative.mutate(first,meter.subjects)
            # Only the real first maintenance receipt is removed. Its neutral
            # wait had no row; the next normal request must now be rejected.
            removed=[e for e in first['events'] if e not in changed['events']]
            self.assertEqual(len(removed),1)
            self.assertEqual(removed[0]['data']['before']['farSamples'][2],0)
            self.assertEqual(removed[0]['data']['after']['farSamples'][2],1)
            self.assertEqual(changed['samples'],first['samples'])
            self.assertEqual(meter.observe_record(changed)['failures'],[])
            request=negative.mutate(chunk(original,'request-second-sample',4,4),meter.subjects)
            result=meter.observe_record(request)
            self.assertEqual(result['failures'],['Distance despawn: normal input stages skip or reverse'])
            validate_negative_result(kind,dict(passed=False,failures=result['failures'],measurements={kind:result}),negative.kind+':missing-first-sample')
            self.assertTrue(negative.applied)

    def test_cancel_control_uses_real_full_owner_detach_only_without_prior_finish(self):
        for kind in KINDS:
            meter,_=current_meter(kind);subject=meter.subjects['unrelated'];handle=subject['handle']
            native=dict(event='ACTOR_DETACHED',actorFrame=9,sequence=90,
                actorHandle=handle['value'],actor={k:v for k,v in handle.items() if k!='value'})
            detach=dict(phase='observe',events=[dict(frame=9,kind='native',data=native)])
            negative=DistanceDespawnNegative(kind,kind+':cancelled-motion')
            changed=negative.mutate(detach,meter.subjects)
            self.assertTrue(negative.applied)
            expected=deepcopy(detach);expected['events'][0]['data']['event']='MOTION_CANCELED'
            self.assertEqual(changed,expected) # Same event, clock, sequence and full handle.
            for field in handle:
                wrong=deepcopy(detach);data=wrong['events'][0]['data']
                if field=='value':data['actorHandle']+=1
                else:data['actor'][field]+=1
                other=DistanceDespawnNegative(kind,kind+':cancelled-motion')
                with self.subTest(kind=kind,field=field):
                    self.assertEqual(other.mutate(wrong,meter.subjects),wrong)
                    self.assertFalse(other.applied)
            # A completed Walk supplies its own stronger cancellation control.
            # Its later detach must remain a detach, not become a second fault.
            finished=deepcopy(detach);finished['events'][0]['data']['event']='MOTION_FINISHED'
            prior=DistanceDespawnNegative(kind,kind+':cancelled-motion')
            self.assertEqual(prior.mutate(finished,meter.subjects)['events'][0]['data']['event'],'MOTION_CANCELED')
            self.assertEqual(prior.mutate(detach,meter.subjects),detach)

    def test_second_request_split_rows_keep_valid_delete_and_later_frames(self):
        for kind in KINDS:
            for split in (False,True):
                meter,_=current_meter(kind);row=stream(kind)[0]
                first=chunk(row,'walk-first-tile-settle',2,3)
                for snap in first['samples']:snap['player']['y']=CASES[kind][3]+EXIT[kind]//2
                self.assertEqual(meter.observe_record(first)['failures'],[])
                self.assertTrue(meter.stage('first-far-sample'))
                later=deepcopy(row['samples'][-1]);later.update(frame=9,actorFrame=9,nativeCycle=1009)
                later['pokemonCombat'].update(frame=9,nativeCycle=1009)
                later['pokemonCombat']['interactions'].update(frame=9,nativeCycle=1009)
                row['samples'].append(later);row['cycleIntervals'].append(dict(completedGameFrame=9,cpuNs=1,wallNs=1))
                windows=((4,6),(7,8),(9,9)) if split else ((4,9),)
                for start,end in windows:
                    result=meter.observe_record(chunk(row,'request-second-sample',start,end))
                    self.assertEqual(result['failures'],[],(kind,split,start,result))
                self.assertTrue(result['passed'],result)
                self.assertEqual([v['after'] for v in result['farSamples']],[1,2])
                self.assertEqual(result['deletion']['frame'],8)
                self.assertEqual(result['observedFrames'],8)
                self.assertFalse(meter.stage('first-far-sample'))

    def test_second_request_entry_rejects_bad_order_far_sample_and_corridor(self):
        for kind in KINDS:
            for fault in ('skipped','early','no-first-far','wrong-x','wrong-y','reverse'):
                meter,_=current_meter(kind,1);row=stream(kind)[0]
                first=chunk(row,'first-scheduled-far-sample',2,3)
                for snap in first['samples']:snap['player']['y']=CASES[kind][3]+EXIT[kind]//2
                if fault=='no-first-far':first['events']=[e for e in first['events'] if e['kind']!='native-observation']
                self.assertEqual(meter.observe_record(first)['failures'],[])
                request=chunk(row,'request-second-sample',4,4)
                if fault=='skipped':request['action']='scheduled-distance-removal'
                elif fault=='early':meter.action_index=0
                elif fault=='wrong-x':meter.latest['player']['x']+=1
                elif fault=='wrong-y':meter.latest['player']['y']+=1
                elif fault=='reverse':request['action']='walk-first-tile-settle'
                result=meter.observe_record(request)
                expected=('second request precedes' if fault=='no-first-far' else
                    'exact corridor tile' if fault in ('wrong-x','wrong-y') else 'stages skip or reverse')
                with self.subTest(kind=kind,fault=fault):
                    self.assertIn(expected,' '.join(result['failures']))
                    self.assertIsNone(result['deletion'])

    def test_generic_retirement_requires_leaf_delete_and_checks_protected_bodies(self):
        from tools.overworld import control
        for kind in KINDS:
            meter,current=current_meter(kind,len(actions(kind))-1);row=stream(kind)[0]
            for snap in row['samples']:native_identities(snap)
            checked=[]
            def verify(snap,_):
                for name,subject in current.subjects.items():
                    if not control._distance_subject_retired(snap,current,subject):
                        control._verify_shared_subject_observation(snap,subject)
                        checked.append((snap['frame'],name))
            result=meter.observe_record(row,on_sample=verify)
            self.assertTrue(result['passed'],result)
            self.assertEqual(set(checked),{(f,n) for f in range(2,9) for n in ('cargo','carrier','unrelated')}
                -{(8,'unrelated')})
            final=row['samples'][-1];unrelated=current.subjects['unrelated']
            self.assertTrue(control._distance_subject_retired(final,current,unrelated))
            for fault in ('no-delete','failed-leaf','early','wrong-full-handle','wrong-subject','other-measurement'):
                value=SimpleNamespace(measurements={kind:deepcopy(meter)})
                snap=deepcopy(final);subject=deepcopy(unrelated)
                if fault=='no-delete':value.measurements[kind].deleted=None
                elif fault=='failed-leaf':value.measurements[kind].failures.append('invalid native DELETE')
                elif fault=='early':snap['frame']=7
                elif fault=='wrong-full-handle':value.measurements[kind].deleted['handle']['encounterGeneration']+=1
                elif fault=='wrong-subject':subject['subjectIdentity']+=1
                else:value.measurements={}
                with self.subTest(kind=kind,fault=fault):
                    self.assertFalse(control._distance_subject_retired(snap,value,subject))
            for name in ('cargo','carrier'):
                subject=current.subjects[name]
                self.assertFalse(control._distance_subject_retired(final,current,subject))
                bad=deepcopy(final)
                next(a for a in bad['actors'] if a['handle']==subject['handle'])['engineIdentity']['in_manager']=False
                with self.subTest(kind=kind,protected=name),self.assertRaises(control.ValidationFailure):
                    control._verify_shared_subject_observation(bad,subject)

    def test_generic_retirement_rejects_absence_without_valid_native_delete(self):
        from tools.overworld import control
        for kind in KINDS:
            for fault in ('no-delete','wrong-delete-identity','stale-claim'):
                meter,current=current_meter(kind,len(actions(kind))-1);row=stream(kind)[0]
                if fault=='no-delete':row['events']=[e for e in row['events'] if e['frame']!=8]
                elif fault=='wrong-delete-identity':
                    raw=bytearray.fromhex(row['events'][-1]['data']['after']['telemetryHex'])
                    struct.pack_into('<I',raw,16+8,0);row['events'][-1]['data']['after']['telemetryHex']=raw.hex()
                else:row['samples'][-1]['pokemonCombat']['interactions']['carriers'][0]['bindings']['cargo']['targetCurrent']=False
                result=meter.observe_record(row)
                with self.subTest(kind=kind,fault=fault):
                    self.assertTrue(result['failures'],result)
                    self.assertFalse(control._distance_subject_retired(row['samples'][-1],current,current.subjects['unrelated']))

    def test_free_chase_then_valid_pickup_and_windup_keep_protection(self):
        for kind in KINDS:
            for encoded in (129,193):
                with self.subTest(kind=kind,encoded=encoded):
                    result=evaluate(pickup_stream(kind,encoded),kind)
                    self.assertTrue(result['passed'],result)
                    value=result['measurements'][kind]
                    self.assertEqual(value['freeChaseWitness']['frame'],3)
                    self.assertEqual(value['freeChaseWitness']['native']['targets'][1],1)
                    self.assertEqual(value['freeChaseWitness']['bindings']['trigger']['target']['kind'],'PLAYER')
                    self.assertEqual([x['after'] for x in value['farSamples']],[1,2])
                    self.assertEqual(value['terminal']['frame'],7)
                    self.assertEqual(value['deletion']['frame'],8)

    def test_pickup_before_first_far_does_not_replace_free_chase(self):
        result=evaluate(pickup_stream(start=2))
        self.assertFalse(result['passed'],result)
        self.assertIn('first far sample lacks its free chase witness',' '.join(result['failures']))

    def test_held_claim_rejects_lost_stale_flags_masks_and_flight(self):
        for fault in ('trigger-missing','trigger-stale','cargo-stale','owner','raw-flags','target-mask','carrier-mask',
                      'recovery','dropped','wrong-cargo','flight','held-pose','windup-without-carry'):
            rows=pickup_stream();snap=rows[0]['samples'][2]
            value=snap['pokemonCombat']['interactions'];state=value['throwState'];row=value['carriers'][0]
            if fault=='trigger-missing':row['bindings']['trigger']['bound']=False
            elif fault=='trigger-stale':row['bindings']['trigger']['targetCurrent']=False
            elif fault=='cargo-stale':row['bindings']['cargo']['targetCurrent']=False
            elif fault=='owner':row['rawBindingsHex']='00'*12+row['rawBindingsHex'][24:]
            elif fault=='raw-flags':row['throw']['carried']=False
            elif fault=='target-mask':state['targetMask']=0
            elif fault=='carrier-mask':state['carrierMask']=0
            elif fault=='recovery':state['recoveringMask']=2;row['throw']['recovering']=True
            elif fault=='dropped':state['targets'][1]=0
            elif fault=='wrong-cargo':state['targets'][1]=130
            elif fault=='flight':snap['actors'][0].update(motionKind='HOP',motionPhase='MOVING',reservationId=10)
            elif fault=='held-pose':snap['actors'][0]['engineObject']['x']+=1
            elif fault=='windup-without-carry':state['targets'][1]=65
            state['rawHex']=(bytes(state['targets'])+struct.pack('<3H',state['targetMask'],state['carrierMask'],state['recoveringMask'])).hex()
            with self.subTest(fault=fault):self.assertFalse(evaluate(rows)['passed'],fault)

    def test_scheduled_held_claim_still_requires_exact_pair_masks(self):
        for fault in ('target-mask','carrier-mask','recovery','wrong-cargo','windup-without-carry'):
            rows=pickup_stream();event=next(e for e in rows[0]['events'] if e.get('data',{}).get('sequence')==2)
            state=event['data']['after']['throwState']
            if fault=='target-mask':state['targetMask']=0
            elif fault=='carrier-mask':state['carrierMask']=0
            elif fault=='recovery':state['recoveringMask']=1
            elif fault=='wrong-cargo':state['targets'][1]=130
            else:state['targets'][1]=65
            with self.subTest(fault=fault):self.assertIn('exact protected Cargo claim',' '.join(evaluate(rows)['failures']))

    def test_controller_accepts_only_unrelated_measurement_for_each_map(self):
        from unittest.mock import patch
        from tools.overworld import control
        repo=HERE.parents[1]
        registry_path=repo/'tools/overworld/runtime_proof_registry.json'
        registry_text=registry_path.read_text()
        original_loads=json.loads
        for kind in KINDS:
            name=CASES[kind][0]
            test=original_loads((repo/'tests/overworld/test-recipes'/(name+'.json')).read_text())
            self.assertEqual(test['measurements'],[dict(kind=kind,subject='unrelated')])
            registration,_=control._shared_test_registration(test,repo)
            self.assertEqual(registration['evaluator'],kind)
            for subject in ('cargo','carrier'):
                changed=deepcopy(test);changed['measurements'][0]['subject']=subject
                with self.subTest(kind=kind,subject=subject),self.assertRaises(ValueError):
                    control._shared_test_registration(changed,repo)
            for fault in ('contract','claims'):
                changed=original_loads(registry_text)
                if fault=='contract':
                    changed['sharedTests'][name]['measurementContract']['engine-boundary'][0]['expected']=0
                else:changed['sharedTests'][name]['claims'].pop()
                def loads(value,*args,**kwargs):
                    return changed if value==registry_text else original_loads(value,*args,**kwargs)
                with self.subTest(kind=kind,fault=fault),patch.object(control.json,'loads',side_effect=loads),self.assertRaises(ValueError):
                    control._shared_test_registration(test,repo)

    def test_two_map_claim_motion_and_exact_delete(self):
        for kind in KINDS:
            result=evaluate(stream(kind),kind);self.assertTrue(result['passed'],result)
            self.assertEqual(len(measurements(kind,result,dict(sessionId='owned',sessionCleanup=dict(sessionId='owned',closed=True,errors=[])))),6)

    def test_named_copied_controls(self):
        for kind in KINDS:
            for fault in faults(kind):
                with self.subTest(kind=kind,fault=fault):
                    control=DistanceDespawnNegative(kind,fault);result=evaluate(stream(kind),kind,control)
                    self.assertTrue(control.applied);validate_negative_result(kind,result,fault)

    def test_idle_actor_needs_real_far_calls_and_delete_but_no_fake_motion(self):
        rows=stream()
        for snap in rows[0]['samples']:
            if snap['frame'] != 8:
                ordinary=snap['actors'][2]
                ordinary.update(motionKind='NONE',motionPhase='IDLE',motionElapsed=0,motionDuration=0,reservationId=0,commitSequence=0,
                    logical=deepcopy(ordinary['origin']),target=deepcopy(ordinary['origin']))
                ordinary['engineObject']['pos_x']=(ordinary['origin']['x']<<16)+32768
                ordinary['engineObject']['x']=ordinary['origin']['x']
        rows[0]['events']=[e for e in rows[0]['events'] if e['kind']=='native-observation']
        for event in rows[0]['events']:
            event['data']['movementDeferredMask']=0
            for key in ('before','after'):
                value=event['data'][key];value['lastKnownX'][2]=REMOTE[ROUTE][0]
                if value['telemetrySequence']:
                    raw=bytearray.fromhex(value['telemetryHex']);struct.pack_into('<h',raw,16+22,REMOTE[ROUTE][0]);value['telemetryHex']=raw.hex()
        result=evaluate(rows);self.assertTrue(result['passed'],result)
        self.assertIsNone(result['measurements'][ROUTE]['terminal']['motion'])

    def test_second_idle_call_can_delete_without_an_invented_deferred_bit(self):
        rows=stream();rows[0]['events']=[e for e in rows[0]['events'] if not (e['kind']=='native-observation' and e['frame']==6)]
        last=rows[0]['events'][-1];last['data']['sequence']=2;last['data']['before']=state(ROUTE,1)
        result=evaluate(rows);self.assertTrue(result['passed'],result)

    def test_first_far_sample_does_not_credit_an_earlier_motion_terminal(self):
        for kind in KINDS:
            rows=two_walk_stream(kind);result=evaluate(rows,kind)
            self.assertTrue(result['passed'],result)
            r=result['measurements'][kind]
            self.assertEqual(r['deferredMotion']['frame'],12)
            self.assertEqual(r['terminal']['motion']['startFrame'],8)
            self.assertEqual(r['terminal']['frame'],13)
            self.assertEqual(r['deletion']['frame'],14)
            # A prior full Walk cannot stand in for this second owner.
            bad=deepcopy(rows);bad[0]['events']=[e for e in bad[0]['events']
                if not(e['frame']==13 and e.get('data',{}).get('event')=='CONTROL_RETURNED')]
            self.assertIn('exact native commit and control return',' '.join(evaluate(bad,kind)['failures']))

    def test_confirmed_deferred_owner_can_finish_in_its_receipt_queue(self):
        rows=stream();second=next(e for e in rows[0]['events'] if e.get('data',{}).get('sequence')==2)
        second['frame']=7;second['data'].update(entryActorFrame=6,returnActorFrame=6,entryNativeCycle=1007,returnNativeCycle=1007)
        result=evaluate(rows);self.assertTrue(result['passed'],result)
        self.assertEqual(result['measurements'][ROUTE]['terminal']['frame'],7)

    def test_new_motion_after_confirmed_terminal_is_rejected(self):
        rows=two_walk_stream();last=rows[0]['samples'][-1];last['actors'].append(deepcopy(rows[0]['samples'][-2]['actors'][2]))
        last['actors'][-1].update(motionKind='WALK',motionPhase='MOVING',motionElapsed=0,reservationId=11,
            origin=deepcopy(last['actors'][-1]['logical']),target=dict(x=REMOTE[ROUTE][0]+3,y=REMOTE[ROUTE][1]))
        rows[0]['events']=[e for e in rows[0]['events'] if not(e['frame']==14 and e['kind']=='native-observation')]
        result=evaluate(rows);self.assertFalse(result['passed'],result)
        self.assertIn('follow-on movement before removal',' '.join(result['failures']))

    def test_native_delete_can_leave_only_the_exact_cleared_resident_row(self):
        for kind in KINDS:
            rows=stream(kind)
            retired=deepcopy(rows[0]['samples'][-2]['actors'][2])
            retired.pop('engineObject')
            retired.update(identityVerified=False,motionKind='NONE',motionPhase='IDLE',reservationId=0,
                engineIdentity=dict(pointer=0,in_manager=False,active=False),
                sourceIdentity=dict(object=0,active=0,personality=0,species=0))
            rows[0]['samples'][-1]['actors'].append(retired)
            result=evaluate(rows,kind)
            self.assertTrue(result['passed'],result)
            self.assertEqual(result['measurements'][kind]['deletion']['frame'],8)
            for fault in ('no-delete','live-identity','native-pointer','source-object','source-active',
                          'personality','moving','reservation','delete-pointer','pending-clear'):
                bad=deepcopy(rows);a=bad[0]['samples'][-1]['actors'][2]
                if fault=='no-delete':bad[0]['events']=[e for e in bad[0]['events'] if e['frame']!=8]
                elif fault=='live-identity':a['identityVerified']=True
                elif fault=='native-pointer':a['engineIdentity']['pointer']=0x2100200
                elif fault=='source-object':a['sourceIdentity']['object']=0x2100200
                elif fault=='source-active':a['sourceIdentity']['active']=1
                elif fault=='personality':a['subjectIdentity']+=1
                elif fault=='moving':a['motionPhase']='MOVING'
                elif fault=='reservation':a['reservationId']=1
                elif fault=='pending-clear':bad[0]['events'][-1]['data']['after']['distanceDespawnPendingMask']=4
                else:
                    d=bad[0]['events'][-1]['data'];raw=bytearray.fromhex(d['after']['telemetryHex'])
                    struct.pack_into('<I',raw,16,0x2100300);d['after']['telemetryHex']=raw.hex()
                with self.subTest(kind=kind,fault=fault):self.assertFalse(evaluate(bad,kind)['passed'],fault)

    def test_native_receipt_must_stay_inside_its_completed_queue(self):
        for fault in (None,'before','after','split','reverse','sequence'):
            rows=stream(CITY);first=next(e for e in rows[0]['events'] if e.get('data',{}).get('observation')=='distance-maintenance')
            d=first['data'];d['entryNativeCycle']=d['returnNativeCycle']=1002
            if fault=='before':d['entryNativeCycle']=d['returnNativeCycle']=1001
            elif fault=='after':d['entryNativeCycle']=d['returnNativeCycle']=1004
            elif fault=='split':d['returnNativeCycle']=1003
            elif fault=='reverse':d['entryNativeCycle']=1003
            elif fault=='sequence':d['sequence']=0
            result=evaluate(rows,CITY)
            if fault not in (None,'split'):self.assertIn('clock, sequence or source differs',' '.join(result['failures']))
            else:self.assertTrue(result['passed'],result)

    def test_frozen_two_case_wiring_uses_existing_reader_and_adapter(self):
        for name in ('devtools_test_contract','devtools_test_inputs','proof_adapters'):
            spec=importlib.util.spec_from_file_location('tools.overworld.'+name,HERE/(name+'.py'))
            module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        from tools.overworld.devtools_test_contract import TestEvaluator,validate_test,DISTANCE_KINDS
        from tools.overworld.devtools_test_inputs import measurement_inputs
        from tools.overworld.proof_adapters import get_adapter
        registry=json.loads((HERE/'runtime_proof_registry.json').read_text())
        for kind in KINDS:
            path=HERE.parents[1]/'tests/overworld/test-recipes'/(CASES[kind][0]+'.json')
            test=validate_test(json.loads(path.read_text()))
            order=[a['id'] for a in test['setup']]
            self.assertLess(order.index('natural-cargo-claim'),order.index('spawn-unrelated'))
            self.assertNotIn('natural-cargo-claim',[a['id'] for a in test['actions']])
            self.assertEqual(len([a for a in test['setup'] if a['id']=='spawn-unrelated']),1)
            _,map_id,x,y=CASES[kind]
            corridor=[a['args']['z'] for a in test['setup'] if a['id'].startswith('terrain-corridor-')]
            self.assertEqual(corridor,list(range(min(CARGO[kind][1],CARRIER[kind][1],y),max(CARGO[kind][1],CARRIER[kind][1],y)+1)))
            self.assertEqual([a['args']['until']['kind'] for a in test['actions'][:2]],
                             ['player-field','player-settled-at'])
            self.assertEqual(test['actions'][2]['args']['until']['stage'],'first-far-sample')
            self.assertEqual([a['id'] for a in test['actions']],
                ['walk-first-tile','walk-first-tile-settle','first-scheduled-far-sample',
                 'request-second-sample','request-second-sample-settle','scheduled-distance-removal'])
            for index in (0,3):
                self.assertEqual(test['actions'][index]['args']['keys'],['DOWN'] if kind==ROUTE else ['UP'])
                self.assertEqual(test['actions'][index]['args']['frames']+test['actions'][index+1]['args']['frames'],32)
                self.assertEqual(test['actions'][index+1]['args']['keys'],[])
            self.assertEqual(test['actions'][3]['args']['until']['value'],y+2*(EXIT[kind]//2))
            self.assertEqual(test['budgets']['maxFrames'],800)
            self.assertEqual(test['budgets']['noProgressFrames'],240)
            self.assertEqual(test['actions'][-1]['args']['frames'],240)
            self.assertEqual(test['actions'][-1]['budget']['maxFrames'],240)
            self.assertIn(kind,DISTANCE_KINDS)
            source=measurement_inputs(test,ROOT);self.assertEqual(set(source[kind]),set(SOURCE))
            evaluator=TestEvaluator(test);evaluator.install_measurements(source)
            self.assertIsInstance(evaluator.measurements[kind],DistanceDespawnMeasurement)
            adapter=get_adapter(kind);self.assertEqual(adapter.recipe_subjects(),test['subjects'])
            self.assertEqual(adapter.contract(),registry['sharedTests'][test['id']]['measurementContract'])

    def test_first_far_stage_requires_a_real_current_claim_backed_receipt(self):
        for kind in KINDS:
            recipe=json.loads((HERE.parents[1]/'tests/overworld/test-recipes'/(CASES[kind][0]+'.json')).read_text())
            meter=DistanceDespawnMeasurement(recipe,SOURCE)
            initial=sample(1,kind);meter.latest=deepcopy(initial);meter.context=deepcopy(initial['context'])
            meter.setup_index=len(setup(kind));meter.action_index=2
            meter.subjects={n:select_current_actor(initial,a) for n,a in zip(('cargo','carrier','unrelated'),initial['actors'])}
            row=stream(kind)[0];row['action']='first-scheduled-far-sample'
            row['samples']=row['samples'][:2];row['events']=[e for e in row['events'] if e['frame']<=3]
            row.update(completedGameFrames=2,observedFieldFrames=2,nativeCycles=2,cycleIntervals=row['cycleIntervals'][:2])
            self.assertFalse(meter.stage('first-far-sample'))
            result=meter.observe_record(row)
            self.assertEqual(result['failures'],[])
            self.assertTrue(meter.stage('first-far-sample'))
            self.assertEqual(result['farSamples'][0]['after'],1)
            # Neutral travel without the native maintenance event cannot arm
            # the later normal step or count as a far sample.
            cold=DistanceDespawnMeasurement(recipe,SOURCE)
            cold.latest=deepcopy(initial);cold.context=deepcopy(initial['context'])
            cold.setup_index=len(setup(kind));cold.action_index=2;cold.subjects=deepcopy(meter.subjects)
            absent=deepcopy(row);absent['events']=[e for e in absent['events'] if e['kind']!='native-observation']
            self.assertEqual(cold.observe_record(absent)['failures'],[])
            self.assertFalse(cold.stage('first-far-sample'))
            request=deepcopy(absent);request['action']='request-second-sample'
            self.assertIn('second request precedes',str(cold.observe_record(request)['failures']))
            with self.assertRaises(ValueError):meter.stage('unknown')

    def test_only_a_proved_zero_frame_first_far_wait_may_omit_its_row(self):
        for kind in KINDS:
            for fault in (None,'no-first-far','wrong-x','wrong-y','first-step','other-skip','reverse','deleted'):
                recipe=json.loads((HERE.parents[1]/'tests/overworld/test-recipes'/(CASES[kind][0]+'.json')).read_text())
                meter=DistanceDespawnMeasurement(recipe,SOURCE);initial=sample(1,kind)
                meter.latest=deepcopy(initial);meter.context=deepcopy(initial['context'])
                meter.setup_index=len(setup(kind));meter.action_index=0
                meter.subjects={n:select_current_actor(initial,a) for n,a in zip(('cargo','carrier','unrelated'),initial['actors'])}
                row=stream(kind)[0];row['action']='walk-first-tile-settle';row['samples']=row['samples'][:2]
                row['events']=[e for e in row['events'] if e['frame']<=3]
                row.update(completedGameFrames=2,observedFieldFrames=2,nativeCycles=2,cycleIntervals=row['cycleIntervals'][:2])
                for snap in row['samples']:snap['player']['y']=CASES[kind][3]+EXIT[kind]//2
                if fault=='no-first-far':row['events']=[e for e in row['events'] if e['kind']!='native-observation']
                self.assertEqual(meter.observe_record(row)['failures'],[])
                if fault is None:self.assertTrue(meter.stage('first-far-sample'))
                request=stream(kind)[0];request['action']='request-second-sample'
                request['samples']=request['samples'][2:3];request['events']=[]
                request.update(completedGameFrames=1,observedFieldFrames=1,nativeCycles=1,cycleIntervals=request['cycleIntervals'][2:3])
                if fault=='wrong-x':meter.latest['player']['x']+=1
                elif fault=='wrong-y':meter.latest['player']['y']+=1
                elif fault=='first-step':meter.action_index=0
                elif fault=='other-skip':request['action']='scheduled-distance-removal'
                elif fault=='reverse':meter.action_index=4
                elif fault=='deleted':meter.deleted=dict(frame=3)
                result=meter.observe_record(request)
                with self.subTest(kind=kind,fault=fault):
                    if fault:
                        expected='exact corridor tile' if fault in ('wrong-x','wrong-y') else 'stages skip or reverse'
                        self.assertIn(expected,' '.join(result['failures']))
                    else:
                        self.assertEqual(result['failures'],[])
                        self.assertEqual(meter.action_index,3)
                        self.assertFalse(result['ready']) # One far call cannot earn deletion proof.

    def test_empty_missing_terminal_wrong_distance_or_pointer_cannot_pass(self):
        for fault in ('empty','terminal','range','pointer'):
            rows=stream()
            if fault=='empty':rows[0]['events']=[]
            elif fault=='terminal':rows[0]['events']=[e for e in rows[0]['events'] if e.get('data',{}).get('event')!='CONTROL_RETURNED']
            else:
                data=rows[0]['events'][-1]['data'];raw=bytearray.fromhex(data['after']['telemetryHex'])
                if fault=='range':raw[16+35]=16
                else:struct.pack_into('<I',raw,16,0x2100300)
                data['after']['telemetryHex']=raw.hex()
            result=evaluate(rows);self.assertFalse(result['passed'],fault)

if __name__=='__main__':unittest.main()
