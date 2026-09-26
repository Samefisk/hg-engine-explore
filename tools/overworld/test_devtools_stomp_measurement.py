"""Synthetic stream controls. No generated row is accepted game evidence."""
from copy import deepcopy
from pathlib import Path
import json
import unittest

from tools.overworld.devtools_stomp_measurement import StompMeasurement, SINKS
from tools.overworld.devtools_mount_pacing_observer import ENGINE
from tools.overworld.test_devtools_stomp_contract import fixture as contract_fixture


def fixture(keys=('RIGHT','RIGHT')):
    cases,subject,_=contract_fixture();rows=[];seq=0;counts=dict.fromkeys(('policy',*SINKS),0);steps=0;latest=None
    if keys==('LEFT','RIGHT'):
        # A separate synthetic route fixture matching the sealed recipe.
        for index,c in enumerate(cases):
            for s in [c['initial'],*c['poses']]:
                if index==0:
                    s['actors'][0]['logical']['x']=20-s['actors'][0]['logical']['x']
                    for obj in (s['player'],s['actors'][0]['engineObject']):obj['pos_x']=200000-obj['pos_x']
                    if s is not c['initial']:
                        s['player'].update(facing=2,face_x=32768);s['actors'][0]['engineObject']['facing']=2
                else:
                    s['actors'][0]['logical']['x']-=2
                    for obj in (s['player'],s['actors'][0]['engineObject']):obj['pos_x']-=131072
            c['terminal']=c['poses'][-1]
        cases[1]['initial']=deepcopy(cases[0]['terminal'])
    start=cases[0]['initial']['frame'];previous=deepcopy(cases[0]['initial']);profile=bytearray(72);profile[12]=1
    def enrich(s,mask):
        s=deepcopy(s);s['selector']=dict(heldKeys=mask,rawHeld=mask,newKeys=mask,rawNew=mask,simulatedKeys=0)
        s['observationBoundary']='main-task-queue-completion'
        s['nativeObservation']=dict(sequence=seq,installedBeforeBoot=True,coverageComplete=True,error=None,eventsDropped=0,profilesEvicted=0)
        a=s['actors'][0];a['movementPolicy'].update(skid=0,pendingSkid=0)
        current=dict(subject=subject,publicSubject=deepcopy(a),sourceIdentity=a['sourceIdentity'],
            engineIdentity={k:a['engineIdentity'][k] for k in ENGINE},
            worldContext=dict(s['context'],fieldPointer=0x02280000,statePointer=0x02380000),
            playerPointer=a['engineIdentity']['anchorPointer'],mountPointer=a['engineIdentity']['pointer'],avatarPointer=0x02230000)
        native_pair=s['stompFeedback']['latestCompletedPose']
        player=dict(s['player'],**{k:native_pair['player'][k] for k in ('unk88_z','unk94_z')})
        mount=dict(a['engineObject'],**{k:native_pair['mount'][k] for k in ('unk88_z','unk94_z')})
        pose=dict(current,player=player,mount=mount,boundary='main-task-queue-completion',
            frame=s['frame'],actorFrame=s['actorFrame'],nativeCycle=s['nativeCycle'],input=dict(heldKeys=mask,newKeys=mask))
        s['stompFeedback']=dict(armed=True,closed=False,failure=None,subject=subject,startFrame=start,
            pending=0,counts=deepcopy(counts),playerStepCount=steps,latest=deepcopy(latest),latestCompletedPose=pose,
            acceptedProof=False,guestMemoryWrites=0)
        return s
    previous=enrich(previous,0)
    for index,c in enumerate(cases):
        duration=c['case']['duration'];before=bytearray(184);before[8:80]=profile
        for k,v in ((7,duration),(19,0),(50,0),(51,duration),(70,2)):profile[k]=v
        after=bytearray(before);after[8:80]=profile
        clock={k:previous[k] for k in ('frame','nativeCycle')}
        meta=dict(readiness=dict(actor=previous['actors'][0]),clock=clock,bindingHex=bytes(after[80:96]).hex(),sessionGeneration=1)
        q=dict(completed=True,prepared=True,acceptedProof=False,guestAdvanced=False,scope='prepared-idle-mounted-walk-fixture',
            subject=subject,directionMode=0,travelTime=duration,stompTime=2,changedOffsets=[7,19,50,51,70],
            before=dict(meta,mountStateHex=bytes(before).hex(),profileHex=bytes(before[8:80]).hex()),
            after=dict(meta,mountStateHex=bytes(after).hex(),profileHex=bytes(profile).hex()),expectedStateHex=bytes(after).hex())
        rows.append(dict(op='configure',receipt=q,snapshot=deepcopy(previous)))
        if index==0:rows.append(dict(op='arm',subject=subject,snapshot=deepcopy(previous),receipt=deepcopy(previous['stompFeedback'])))
        for i,base in enumerate(c['poses']):
            mask=(32 if keys[index]=='LEFT' else 16) if i==0 else 0
            rows.append(dict(op='command',request=dict(op='step',args=dict(frames=1,keys=[keys[index]] if mask else []),startFrame=previous['frame']),
                receipt=dict(requestedGameFrames=1,completedGameFrames=1,observedFieldFrames=1)))
            native_events=[]
            def shared(outer,operation):
                response=bytearray.fromhex(outer['policyHex']);response[9]=operation
                if operation==1:response[10]=response[17];response[16]=2
                request=bytearray(response);request[16:]=bytes(12)
                public=dict(outer['before']['publicSubject'],status='observed-public-subject')
                return dict(observation='walk-policy',slot=subject['handle']['slot'],operation=operation,
                    requestHex=request.hex(),responseHex=response.hex(),publicSubject=public,publicSubjectAfter=deepcopy(public),
                    laneHex=profile.hex(),returnValue=1,entryClock=outer['entryClock'],returnClock=outer['returnClock'])
            if i==0:
                d=deepcopy(c['feedback']['calls'][0]);clock=dict(actorFrame=base['actorFrame'],nativeCycle=base['nativeCycle']-1)
                raw=bytearray.fromhex(d['policyHex']);raw[17]=2 if keys[index]=='LEFT' else 3;d['policyHex']=raw.hex()
                d.update(entryClock=clock,returnClock=clock,completedFrame=previous['frame'],profileHex=profile.hex())
                native_events.extend((shared(d,1),shared(d,2),d))
            if i==len(c['poses'])-1:
                commit=deepcopy(c['feedback']['calls'][-1]);commit['profileHex']=profile.hex()
                native_events.append(shared(commit,3))
                for name in SINKS:native_events.extend(deepcopy(commit['feedback'][name]))
                native_events.append(commit)
                a=base['actors'][0];current=deepcopy(commit['before']);current['publicSubject']=deepcopy(a)
                native_events.append(dict(current,kind='playerStep',fieldPointer=current['worldContext']['fieldPointer'],
                    player=base['player'],mount=a['engineObject'],eventConsumed=0,normalReturn=True,
                    completedFrame=previous['frame'],entryClock=commit['entryClock'],returnClock=commit['returnClock'],returnValue=0))
            events=[]
            for d in native_events:
                kind=d.get('kind');seq+=1
                if kind=='playerStep':steps+=1
                elif kind:counts[kind]+=1
                if kind=='policy':latest=deepcopy(d)
                framed=dict(d,observation='stomp-'+kind if kind else 'walk-policy',sequence=seq,entryActorFrame=d['entryClock']['actorFrame'],
                    entryNativeCycle=d['entryClock']['nativeCycle'],returnActorFrame=d['returnClock']['actorFrame'],
                    returnNativeCycle=d['returnClock']['nativeCycle'],setupMode='prepared')
                events.append(dict(kind='native-observation',frame=base['frame'],data=framed))
            for e in c['events']:
                if e['frame']==base['frame']:
                    events.append(dict(kind='native',frame=base['frame'],data=dict(e,traceStream=1,
                        actorHandle=subject['handle']['value'],actor={k:v for k,v in subject['handle'].items() if k!='value'})))
            base=deepcopy(base)
            if i<len(c['poses'])-1:base['actors'][0].update(reservationId=index+1,motionKind='WALK',motionPhase='MOVING')
            previous=enrich(base,mask)
            rows.append(dict(op='observe',snapshot=previous,events=events))
    rows.append(dict(op='close',snapshot=deepcopy(previous),receipt=dict(closed=True,advancedFrames=0,acceptedProof=False,
        snapshot=deepcopy(previous),stompFeedback=dict(previous['stompFeedback'],closed=True))))
    return rows


def replay(rows=None,close=True):
    meter=StompMeasurement(100)
    for row in rows or fixture():
        row=deepcopy(row);op=row.pop('op')
        if op=='close' and not close:break
        getattr(meter,op)(**row)
        if meter.failures:break
    return meter


def raw_records():
    """Return validated recipe and synthetic complete shared collector records.

    Every native cycle is retained, including the nine no-queue cycles before
    each synthetic completed queue. No row is accepted game evidence.
    """
    from tools.overworld.devtools_test_contract import validate_test
    from tools.overworld.devtools_records import select_current_actor
    root=Path(__file__).resolve().parents[2]
    test=validate_test(json.loads((root/'tests/overworld/test-recipes/walk.stomp.feedback.json').read_text()))
    direct=fixture(keys=('LEFT','RIGHT'))
    def fields(value):
        if isinstance(value,dict):
            if all(k in value for k in ('actors','player','frame','nativeCycle','actorFrame')):
                value.update(fieldAvailable=True,prepared=True,observationBoundary='main-task-queue-completion')
            for item in value.values():fields(item)
        elif isinstance(value,list):
            for item in value:fields(item)
    fields(direct)
    initial=deepcopy(direct[0]['snapshot']);records=[dict(phase='setup',initialSnapshot=initial,
        initialEvents=[],initialEventStartFrame=initial['frame'])]
    setup=test['setup'];actions=test['actions']
    for action in setup[:3]:
        receipt=dict(preparedOnly=True,prepared=True,acceptedProof=False,snapshot=deepcopy(initial),events=[],
            setupBoundary=dict(eventsDrained=True,traceSequences={},frame=initial['frame'],
                nativeCycle=initial['nativeCycle'],endpointNativeCycle=initial['nativeCycle']))
        records.append(dict(phase='setup',action=action['id'],command=action['op'],receipt=receipt,snapshot=deepcopy(initial)))
    subject=select_current_actor(initial,initial['actors'][0])
    records.append(dict(phase='setup',action=setup[3]['id'],command='bind',receipt=subject,snapshot=deepcopy(initial)))
    index=-1;previous=initial;request=None
    for row in direct:
        op=row['op']
        if op=='configure':
            index+=1;action=setup[4] if index==0 else actions[3]
            receipt=dict(row['receipt'],snapshot=deepcopy(row['snapshot']))
            records.append(dict(phase='setup' if index==0 else 'observe',action=action['id'],command='mount-walk.configure',
                receipt=receipt,snapshot=deepcopy(row['snapshot'])))
        elif op=='arm':
            records.append(dict(phase='observe',action=actions[0]['id'],command='stomp.arm',
                receipt=dict(armed=True,prepared=True,acceptedProof=False,snapshot=deepcopy(row['snapshot']),stompFeedback=row['receipt']),
                snapshot=deepcopy(row['snapshot'])))
        elif op=='command':request=row['request']
        elif op=='observe':
            sample=row['snapshot'];n=sample['nativeCycle']-previous['nativeCycle']
            intervals=[dict(cpuNs=100,wallNs=100,completedGameFrame=previous['frame']) for _ in range(n-1)]
            intervals.append(dict(cpuNs=100,wallNs=100,completedGameFrame=sample['frame']))
            action=actions[(1 if request['args']['keys'] else 2)+index*3]
            records.append(dict(phase='observe',action=action['id'],requestedGameFrames=1,completedGameFrames=1,
                observedFieldFrames=1,nativeCycles=n,cycleIntervals=intervals,samples=[sample],events=row['events']))
            previous=sample
        elif op=='close':
            records.append(dict(phase='observe',action=actions[-1]['id'],command='stomp.close',
                receipt=row['receipt'],snapshot=row['snapshot']))
    return test,records


def replay_raw(rows=None,test=None):
    from tools.overworld.devtools_test_contract import TestEvaluator
    from tools.overworld.devtools_test_inputs import measurement_inputs
    if rows is None:test,rows=raw_records()
    evaluator=TestEvaluator(test)
    evaluator.install_measurements(measurement_inputs(test,Path(__file__).resolve().parents[2]))
    for row in rows:
        if evaluator.observe_record(row,full_report=False)['state']=='failed':break
    return evaluator.finish()


class StompMeasurementTests(unittest.TestCase):
    def test_saved_shared_input_with_old_sound_is_rejected(self):
        import gzip
        import hashlib
        from tools.overworld.devtools_test_contract import TestEvaluator,validate_test
        from tools.overworld.devtools_test_inputs import measurement_inputs
        root=Path(__file__).resolve().parents[2]
        directory=root/'build/overworld-devtools/test-9b3683ce5e384600aa8410e682442a4f'
        if not directory.exists():self.skipTest('optional saved Stomp first case absent')
        manifest=json.loads((directory/'manifest.json').read_text());artifact=directory/'observations.jsonl.gz'
        self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(),manifest['observationsArtifact']['sha256'])
        test=validate_test(json.loads((directory/'test.json').read_text()));e=TestEvaluator(test)
        e.install_measurements(measurement_inputs(test,root))
        for line in gzip.open(artifact,'rt'):
            report=e.observe_record(json.loads(line),full_report=False)
            if report['state']=='failed':break
        self.assertEqual(report['state'],'failed')
        self.assertIn('native stomp sound start failed',str(report['failures']))
    def test_saved_first_frame_replays_but_missing_remainder_does_not_pass(self):
        import gzip
        import hashlib
        from tools.overworld.devtools_test_contract import TestEvaluator,validate_test
        from tools.overworld.devtools_test_inputs import measurement_inputs
        root=Path(__file__).resolve().parents[2]
        directory=root/'build/overworld-devtools/test-0837e9d4fcbb48499751e0be893a3ae1'
        if not directory.exists():self.skipTest('optional saved first-frame failure absent')
        manifest=json.loads((directory/'manifest.json').read_text());artifact=directory/'observations.jsonl.gz'
        self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(),manifest['observationsArtifact']['sha256'])
        test=json.loads((directory/'test.json').read_text());e=TestEvaluator(validate_test(test))
        e.install_measurements(measurement_inputs(test,root))
        for line in gzip.open(artifact,'rt'):
            report=e.observe_record(json.loads(line),full_report=False)
            self.assertNotEqual(report['state'],'failed',report['failures'])
        self.assertEqual(e.frames,1)
        result=e.finish();self.assertFalse(result['passed'])
        self.assertIn('MOTION_STARTED',str(result['failures']))
    def test_complete_typed_raw_evaluator(self):
        result=replay_raw()
        self.assertTrue(result['passed'],result['failures'])
        self.assertFalse(result['measurements']['mounted-stomp-v1']['acceptedProof'])
    def test_typed_raw_collector_faults(self):
        for fault in ('cycle','counts','close'):
            test,rows=raw_records()
            sample=next(row for row in rows if 'samples' in row)
            if fault=='cycle':sample['cycleIntervals'].pop(0)
            elif fault=='counts':sample['samples'][0]['stompFeedback']['counts']['policy']+=1
            else:rows[-1]['receipt']['snapshot']['nativeCycle']+=1
            with self.subTest(fault=fault):
                result=replay_raw(rows,test)
                self.assertFalse(result['passed']);self.assertTrue(result['failures'])
    def test_complete_two_case_stream(self):
        m=replay();r=m.finish()
        self.assertTrue(r['passed'],r['failures']);self.assertFalse(r['acceptedProof'])
        self.assertEqual(r['playerStepCount'],2);self.assertEqual(len(r['proofEvidence']),6)
    def test_copied_stream_faults(self):
        for fault in ('sequence','pose','counts','pending','input','sink','step','profile','clock'):
            rows=fixture();sample=next(r for r in rows if r['op']=='observe')
            if fault=='sequence':sample['events'][0]['data']['sequence']+=1
            elif fault=='pose':sample['snapshot']['stompFeedback']['latestCompletedPose']['player']['pos_x']+=1
            elif fault=='counts':sample['snapshot']['stompFeedback']['counts']['policy']+=1
            elif fault=='pending':sample['snapshot']['stompFeedback']['pending']=1
            elif fault=='input':sample['snapshot']['selector']['rawHeld']=0
            elif fault=='profile':sample['events'][0]['data']['laneHex']='00'*72
            elif fault=='clock':sample['events'][0]['data']['returnNativeCycle']+=100
            else:
                sample=next(r for r in rows if r['op']=='observe' and any(e['data'].get('kind')=='playerStep' for e in r['events']))
                kind='dust' if fault=='sink' else 'playerStep'
                sample['events']=[e for e in sample['events'] if e['data'].get('kind')!=kind]
            with self.subTest(fault=fault):
                result=replay(rows).finish();self.assertFalse(result['passed']);self.assertTrue(result['failures'])
    def test_no_early_stage_before_real_step_and_release(self):
        m=replay(close=False)
        self.assertTrue(m.stage('case-complete'));self.assertTrue(m.ready);self.assertFalse(m.closed)
        m.current['events']=m.current['events'][:-1];m.cases.pop()
        self.assertIn('CONTROL_RETURNED',m.finish()['failures'][0])


if __name__=='__main__':unittest.main()
