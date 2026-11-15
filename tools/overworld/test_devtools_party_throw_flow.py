"""Small recipe/reader controls for the two saved-follower Throw cases."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_party_throw_flow_measurement import (
    CASES,recipe,validate_recipe,check_query_returns)

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'TICKETS.md').is_file())


# Native-shaped host data. This is a deterministic evaluator control, not a
# recorded game pass. It uses the same raw Motion/binding/mask readers.
import struct
from scripts.overworld_behavior_profile_viewer import _stable_condition_id
from tools.overworld.devtools_application_bank import canonical_bank,local_application
from tools.overworld.devtools_profile_feature_measurement import application_index
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.normal_play_observer import arc_height
from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor as base_actor
from tools.overworld.devtools_party_throw_flow_measurement import PartyThrowFlowMeasurement,ROUTE34,FOLLOWER_CARGO
from tools.overworld.devtools_party_throw_flow_proof import PartyThrowFlowNegative,faults,validate_negative_result,measurements

SOURCE=dict(contractVersion=1,romSha256='a'*64,sourceSaveSha256='b'*64,profileSha256='c'*64,overlaySha256='d'*64,
    queryImage=dict(elfSha256='e'*64,packageSha256='f'*64))
BANK=canonical_bank(ROOT)
def appbit(species,name):return 1<<local_application(BANK,species,application_index(name))

def native_motion(a,kind=0,origin=None,target=None,duration=0,elapsed=0,reservation=0,phase=0,commit=0,pause=0,cancel=0):
 raw=bytearray(52);origin=origin or list(a['origin'].values());target=target or list(a['target'].values())
 struct.pack_into('<HBBHH',raw,0,1,kind,3,a['handle']['fieldEpoch'],a['behaviorFingerprint']&65535)
 struct.pack_into('<4h2iHH',raw,8,*origin,*target,65536,65536,duration,reservation)
 raw[28:38]=bytes([3,max(abs(x-y) for x,y in zip(origin,target)),16 if kind==2 else 0,0,0,0,pause,1,0,0])
 struct.pack_into('<4H4B',raw,40,elapsed,max(0,duration+pause-elapsed) if phase==4 else 0,0,commit,phase,0,int(phase in (0,4) and kind!=0),cancel)
 return decode_motion(bytes(raw))

def put_motion(a,kind,origin,target,duration,elapsed,reservation,phase,commit,pause=0,cancel=0):
 a.update(origin=dict(zip(('x','y'),origin)),target=dict(zip(('x','y'),target)),motionKind={0:'NONE',1:'WALK',2:'HOP'}[kind] if phase not in (0,6) else 'NONE',
     motionPhase={0:'IDLE',2:'MOVING',4:'SETTLING',6:'CANCELED'}[phase],motionDuration=duration,motionElapsed=elapsed,
     reservationId=reservation if phase==2 else 0,commitSequence=commit,inputOwnership=0)
 a['logical']=dict(zip(('x','y'),target if elapsed==duration and phase!=6 else origin))
 if phase!=6:
  for axis,key in enumerate(('pos_x','pos_z')):a['engineObject'][key]=(origin[axis]<<16)+32768+(target[axis]-origin[axis])*65536*elapsed//duration if duration else (origin[axis]<<16)+32768
  a['engineObject']['unk88_y']=arc_height(elapsed,duration)//16*16 if kind==2 else 0
 return native_motion(a,kind,origin,target,duration,elapsed,reservation,phase,commit,pause,cancel)

def binding(carrier,target,condition,kind='ACTOR'):
 bound=target is not None or kind=='PLAYER';app=application_index('apply-throw');local=local_application(BANK,carrier['species'],app)
 raw=(raw_handle(target['handle']) if target is not None else bytes(12))+bytes([2 if target is not None else 1 if bound else 0,0])+struct.pack('<HIBBBB',condition if bound else 0,0,local if bound else 0,0,int(bound),0)
 return dict(bound=bound,flags=int(bound),sourceConditionId=condition if bound else 0,sourceApplication=app if bound else None,sourceApplicationLocal=local if bound else 0,
     expiresAt=0,lifetime=0,reason=0,target=dict(kind=kind if bound else 'NONE',actor=deepcopy(target['handle']) if target else None),targetCurrent=bound,rawHex=raw.hex())

def sample(feature,frame,follow_start=17):
 case=CASES[feature];mapid=case['map'];m=base_actor(56,7,107,400);m.update(role='FOLLOWER',level=3)
 other=base_actor(69 if feature==ROUTE34 else 74,0,700,401)
 carrier,cargo=(m,other) if feature==ROUTE34 else (other,m)
 for a in (m,other):
  a.update(inputOwnership=0,matchedLayerMask=appbit(56,'apply-follower') if a is m else 0)
  a['engineObject'].update(pos_y=65536,unk88_y=0,face_y=0)
  a['sourceIdentity']=dict(object=a['engineIdentity']['pointer'],personality=a['subjectIdentity'],map_id=mapid,species=a['species'],form=a['form'],level=a['level'],active=1,object_id=224+a['handle']['slot'],encounter_generation=1)
 carrier['matchedLayerMask']|=appbit(carrier['species'],'apply-throw') if 1<=frame<=4 else (appbit(carrier['species'],'apply-throw-find-position')|(appbit(carrier['species'],'apply-throw-release') if frame==7 else 0)) if 5<=frame<=7 else 0
 if feature==ROUTE34 and 5<=frame<=7:carrier['matchedLayerMask']|=appbit(56,'apply-throw-away')
 for a in (m,other):a['behaviorFingerprint']=1000+a['species']*100+a['matchedLayerMask']
 motions={a['handle']['slot']:native_motion(a) for a in (m,other)}
 free_origin=[585,401];free_target=[586,401];launch_origin=[585,400];launch_target=[585,408]
 if frame<=4:
  motions[cargo['handle']['slot']]=put_motion(cargo,2,free_origin,free_target,20,frame,31,2,0)
 elif frame<=7:
  motions[cargo['handle']['slot']]=put_motion(cargo,2,free_origin,free_target,20,4,31,6,0,cancel=16)
 else:
  elapsed=min(6,frame-8);phase=2 if frame<14 else 4 if frame<16 else 0
  motions[cargo['handle']['slot']]=put_motion(cargo,2,launch_origin,launch_target,6,elapsed,55,phase,int(frame>=14),pause=2)
 if follow_start==16 and frame==15:
  previous=motions[cargo['handle']['slot']];raw=bytearray.fromhex(previous['rawHex'])
  struct.pack_into('<H',raw,42,1);motions[cargo['handle']['slot']]=decode_motion(bytes(raw))
 if frame>=follow_start:
  prior=1 if feature==FOLLOWER_CARGO else 0;origin=launch_target if feature==FOLLOWER_CARGO else [585,400];target=[origin[0]+2,origin[1]];elapsed=min(4,frame-follow_start);phase=2 if frame<follow_start+4 else 4 if frame<follow_start+5 else 0
  motions[7]=put_motion(m,2,origin,target,4,elapsed,88,phase,prior+int(frame>=follow_start+4),pause=1)
 code=(cargo['handle']['slot']+1)|(128 if 5<=frame<=7 else 0)|(64 if frame==7 else 0) if 1<=frame<=7 else 0
 targets=[0]*10;targets[carrier['handle']['slot']]=code
 targetmask=(1<<cargo['handle']['slot']) if 1<=frame<14 else 0;carriermask=(1<<carrier['handle']['slot']) if code else 0;recovery=(1<<carrier['handle']['slot']) if 8<=frame<16 else 0
 tm=dict(targets=targets,targetMask=targetmask,carrierMask=carriermask,recoveringMask=recovery,rawHex=(bytes(targets)+struct.pack('<3H',targetmask,carriermask,recovery)).hex())
 trigger=binding(carrier,cargo if feature==ROUTE34 and code else None,_stable_condition_id('throw','condition-throw-notices-pokemon' if feature==ROUTE34 else 'condition-throw-notices-player'),kind='ACTOR' if feature==ROUTE34 or not code else 'PLAYER')
 if not code:trigger=binding(carrier,None,0)
 cb=binding(carrier,cargo if code else None,_stable_condition_id('throw','condition-throw-picks-up-object-of-interest' if feature==ROUTE34 else 'condition-throw-selects-cargo'))
 flags=dict(targetRaw=code,targetSlot=cargo['handle']['slot'] if code else None,carried=bool(code&128),windup=bool(code&64),targeted=bool(targetmask&(1<<carrier['handle']['slot'])),carrier=bool(carriermask&(1<<carrier['handle']['slot'])),recovering=bool(recovery))
 row=dict(slot=carrier['handle']['slot'],handle=deepcopy(carrier['handle']),role=carrier['role'],available=True,bindings=dict(trigger=trigger,cargo=cb),throw=flags,rawBindingsHex=(raw_handle(carrier['handle'])+bytes.fromhex(trigger['rawHex'])+bytes.fromhex(cb['rawHex'])).hex())
 boundary='main-task-queue-completion';field=0x2200000
 combat=dict(schemaVersion=1,available=True,frame=frame,nativeCycle=frame+1000,observationBoundary=boundary,fieldSystem=field,identity=dict(romSha256=SOURCE['romSha256'],overlaySha256=SOURCE['overlaySha256']),
    targets=[dict(handle=deepcopy(a['handle']),role=a['role'],motion=motions[a['handle']['slot']]) for a in (m,other)],
    movementTimers=[dict(handle=deepcopy(a['handle']),slot=a['handle']['slot'],sourceIdentity=deepcopy(a['sourceIdentity']),movementActorControlMode=int(a is cargo and 5<=frame<14)) for a in (m,other)],
    interactions=dict(schemaVersion=1,available=True,frame=frame,nativeCycle=frame+1000,observationBoundary=boundary,fieldSystem=field,carriers=[row],throwState=tm))
 return dict(frame=frame,actorFrame=frame,nativeCycle=frame+1000,fieldAvailable=True,observationBoundary=boundary,romSha256=SOURCE['romSha256'],sourceSaveSha256=SOURCE['sourceSaveSha256'],
    context=dict(mapId=mapid,fieldEpoch=1,mapGeneration=1),fieldControl=dict(taskPointer=0,fieldPointer=field),actors=[m,other],player=dict(x=586,y=407),selector=dict(rawHeld=0,heldKeys=0,simulatedKeys=0),
    party=[dict(slot=2,personality=107,species=56,level=3,form=0,hp=15,identityVerified=True)],nativeObservation=dict(coverageComplete=True,installedBeforeBoot=True,error=None,eventsDropped=0,profilesEvicted=0,pendingUnframedEvents=0),pokemonCombat=combat)

def profiles(s):
 rows=[]
 for a in s['actors']:
  raw=bytearray(216);struct.pack_into('<II',raw,188,a['matchedLayerMask'],a['behaviorFingerprint'])
  rows.append(dict(observation='behavior-resolved',resolved=True,sourceSha256=SOURCE['profileSha256'],fingerprint=a['behaviorFingerprint'],appliedOverrides=a['matchedLayerMask'],resultHex=raw.hex(),lanes=[raw[:80].hex(),raw[80:160].hex()]))
 return rows

def event_table(feature,stop=43,follow_start=17):
 result={};sequence=0
 for f in range(stop):
  s=sample(feature,f,follow_start);case=CASES[feature];cargo=s['actors'][1] if feature==ROUTE34 else s['actors'][0];m=s['actors'][0];found=[]
  def add(a,name,x,y,reason=0):
   nonlocal sequence
   sequence+=1;found.append(dict(frame=f,kind='native',data=dict(event=name,actorHandle=a['handle']['value'],actor={k:v for k,v in a['handle'].items() if k!='value'},sequence=sequence,traceStream=1,traceFieldEpoch=1,frame=f,actorFrame=f,valueA=x,valueB=y,reasonId=reason,reason='CONTEXT_LOST' if reason else 'OK')))
  if f==5:add(cargo,'MOTION_CANCELED',2,0,16);add(cargo,'CONTROL_RETURNED',0,0,16)
  if f==8:add(cargo,'MOTION_STARTED',2,6)
  if f==14:add(cargo,'LOGICAL_COMMIT',1,2)
  if f==16:add(cargo,'MOTION_FINISHED',1,2);add(cargo,'CONTROL_RETURNED',0,1)
  commit=2 if feature==FOLLOWER_CARGO else 1
  if f==follow_start:
   if follow_start==16:
    add(m,'INTENT_CREATED',2,1)
    add(m,'PLAN_ACCEPTED',(m['target']['x']<<16)|m['target']['y'],4)
   add(m,'MOTION_STARTED',2,4)
  if f==follow_start+4:add(m,'LOGICAL_COMMIT',commit,2)
  if f==follow_start+5:add(m,'MOTION_FINISHED',commit,2);add(m,'CONTROL_RETURNED',0,commit)
  if f==2:
   carrier=m if feature==ROUTE34 else s['actors'][1]
   found.append(dict(frame=f,kind='native-observation',data=dict(observation='throw-cargo-query',subject=deepcopy(carrier['handle']),imageIdentity=deepcopy(SOURCE['queryImage']),status='REACHABLE',returnValue=1)))
  found += [dict(frame=f,kind='native-observation',data=p) for p in profiles(s)];result[f]=found
 return result

def rows(feature,follow_start=17):
 spec=recipe(feature)['actions'];result=[];ranges=[];cursor=1
 for action in spec:
  stage=action['args'].get('until',{}).get('stage')
  if stage and cursor>(8 if stage=='launched' else follow_start+5):
   ranges.append(range(cursor,cursor));continue
  count=(8 if cursor==1 else 1) if action['args'].get('until') else action['args']['frames']
  ranges.append(range(cursor,cursor+count));cursor+=count
 # The native-shaped lifecycle remains fixed; the exact ordinary input
 # actions must each complete their declared finite length.
 table=event_table(feature,cursor,follow_start)
 for action,frames in zip(spec,ranges):
  if not frames:continue
  samples=[sample(feature,f,follow_start) for f in frames];keys=action['args']['keys'];mask=sum(dict(RIGHT=16,LEFT=32)[key] for key in keys)
  for s in samples:s['selector'].update(rawHeld=mask,heldKeys=mask)
  result.append(dict(phase='observe',action=action['id'],requestedInput=dict(keys=keys),samples=samples,events=[e for f in frames for e in table[f]],completedGameFrames=len(samples),observedFieldFrames=len(samples),nativeCycles=len(samples),cycleIntervals=[dict(completedGameFrame=s['frame'],cpuNs=1,wallNs=1) for s in samples]))
 return result

def seeded(feature):
 meter=PartyThrowFlowMeasurement(SOURCE,feature);s=sample(feature,0);meter.latest=s;meter.setup_index=len(meter.test['setup'])
 meter.subjects={n:select_current_actor(s,next(a for a in s['actors'] if a['species']==species)) for n,species,_,_ in CASES[feature]['subjects']}
 meter.profiles={p['fingerprint']:p for p in profiles(s)}
 return meter

def evaluate(feature,records,negative=None):
 meter=seeded(feature)
 for row in records:
  meter.observe_record(negative.mutate(row,meter.subjects) if negative else row)
  if meter.failures:break
 m=meter.finish();return dict(passed=m['passed'],failures=m['failures'],observedFrames=m['observedFrames'],measurements={feature:m})

class PartyThrowFlowTests(unittest.TestCase):
    def test_progress_tracks_only_the_bound_saved_mankey(self):
        from types import SimpleNamespace
        from tools.overworld.devtools_jobs import TestJobs
        for feature in CASES:
            with self.subTest(feature=feature):
                meter=seeded(feature);current=sample(feature,0);action=recipe(feature)['actions'][-3]
                evaluator=SimpleNamespace(measurements={feature:meter})
                key=lambda s:TestJobs._progress_key(action,s,evaluator)
                self.assertEqual(meter.result()['subject'],meter.subjects['mankey'])
                before=key(current)
                unrelated=deepcopy(current);unrelated.update(frame=99,nativeCycle=9999)
                unrelated['pokemonCombat']['interactions']['throwState']['recoveringMask']=128
                unrelated['actors'][0]['lastDecision']=123
                other=next(a for a in unrelated['actors'] if a['handle']!=meter.subjects['mankey']['handle'])
                other['engineObject']['pos_x']+=65536;other['motionElapsed']+=1
                meter.query_returns+=100;meter.claim_frames+=100
                self.assertEqual(key(unrelated),before)
                moving=deepcopy(current)
                mankey=next(a for a in moving['actors'] if a['handle']==meter.subjects['mankey']['handle'])
                mankey['motionElapsed']+=1;mankey['engineObject']['pos_z']+=4096
                self.assertNotEqual(key(moving),before)
                # A missing/unbound primary subject cannot borrow another actor's motion.
                wrong=deepcopy(current);wrong['actors']=[a for a in wrong['actors']
                    if a['handle']!=meter.subjects['mankey']['handle']]
                wrong_key=key(wrong);wrong['actors'][0]['engineObject']['pos_x']+=65536
                self.assertEqual(key(wrong),wrong_key)
                meter.subjects.pop('mankey')
                self.assertIsNone(meter.result()['subject'])
                unbound_key=key(current)
                self.assertEqual(key(moving),unbound_key)
                self.assertEqual(recipe(feature)['budgets']['noProgressFrames'],360)
                self.assertEqual(action['budget']['maxFrames'],600)

    def test_already_proven_stage_waits_emit_no_fictitious_row(self):
        for feature in CASES:
            stream=rows(feature)
            self.assertNotIn('follow-after-throw',[r['action'] for r in stream])
            if feature==FOLLOWER_CARGO:
                self.assertNotIn('natural-pickup-and-launch',[r['action'] for r in stream])
                self.assertEqual([len(r['samples']) for r in stream],[8,40,32,32])
            positive=evaluate(feature,stream)
            self.assertTrue(positive['passed'],positive['failures'])

    def test_real_controller_accepts_both_exact_multi_actor_recipes(self):
        from tools.overworld.control import _shared_test_registration
        for feature, case in CASES.items():
            test = json.loads((ROOT/'tests/overworld/test-recipes'/(case['test']+'.json')).read_text())
            with self.subTest(feature=feature):
                registration, digest = _shared_test_registration(test, ROOT)
                self.assertEqual(registration['evaluator'], feature)
                self.assertEqual(len(digest), 64)

    def test_real_3709_route34_resource_failure_is_rejected(self):
        saved=json.loads((ROOT/'tools/overworld/fixtures/route34_pickup_3709_red.json').read_text())
        event=saved['event'];subject=dict(handle=saved['handle'])
        source=dict(queryImage=event['data']['imageIdentity'])
        with self.assertRaisesRegex(ValueError,'Cargo search exhausted memory'):
            check_query_returns([event],subject,source)
        current=deepcopy(event);current['data'].update(status='PENDING',returnValue=0)
        check_query_returns([current],subject,source)
        current['data']['imageIdentity']['packageSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'another code image'):
            check_query_returns([current],subject,source)

    def test_complete_native_shaped_flow_and_named_controls_for_both_roles(self):
        for feature in CASES:
            stream=rows(feature);positive=evaluate(feature,stream)
            with self.subTest(feature=feature):
                self.assertTrue(positive['passed'],positive['failures'])
                values=measurements(feature,positive,dict(sessionId='session-host',sessionCleanup=dict(sessionId='session-host',closed=True,errors=[])))
                self.assertTrue(all(v['passed'] for v in values))
                self.assertEqual(positive['measurements'][feature]['frames']['released'],14)
            for fault in faults(feature):
                negative=PartyThrowFlowNegative(feature,fault);bad=evaluate(feature,stream,negative)
                with self.subTest(feature=feature,fault=fault):
                    self.assertTrue(negative.applied)
                    self.assertFalse(bad['passed'],bad)
                    validate_negative_result(feature,bad,fault)

    def test_setup_order_busy_retry_and_boundary_profile_cache(self):
        meter=PartyThrowFlowMeasurement(SOURCE,ROUTE34);s=sample(ROUTE34,0);meter.latest=s
        wrong=dict(phase='setup',action='bind-mankey',command='bind',snapshot=s,receipt=select_current_actor(s,s['actors'][0]))
        self.assertIn('setup action order',str(meter.observe_record(wrong)['failures']))
        meter=seeded(ROUTE34);meter.setup_index=next(i for i,a in enumerate(meter.test['setup']) if a['op']=='spawn')
        meter.subjects.pop('bellsprout');name=meter.test['setup'][meter.setup_index]['id'];index=meter.setup_index
        refused=dict(phase='setup',action=name,command='spawn-refused',snapshot=deepcopy(meter.latest),receipt={})
        self.assertFalse(meter.observe_record(refused)['failures']);self.assertEqual(meter.setup_index,index)
        retry=rows(ROUTE34)[0];retry=deepcopy(retry);retry.update(phase='setup',action=name)
        retry['requestedInput']['keys']=[]
        self.assertFalse(meter.observe_record(retry)['failures']);self.assertEqual(meter.setup_index,index)
        boundary=sample(ROUTE34,0);boundary['nativeObservation']['resolvedProfiles']=profiles(boundary)
        meter.profiles.clear();meter._cache_profiles(dict(initialSnapshot=boundary))
        self.assertEqual(set(meter.profiles),{a['behaviorFingerprint'] for a in boundary['actors']})

    def test_bind_keeps_the_action_contract_separate_from_the_subject_contract(self):
        for feature in CASES:
            for name,species,role,_ in CASES[feature]['subjects']:
                meter=PartyThrowFlowMeasurement(SOURCE,feature);current=sample(feature,0)
                meter.latest=deepcopy(current)
                meter.setup_index=next(i for i,a in enumerate(meter.test['setup']) if a['id']=='bind-'+name)
                if name!='mankey':
                    meter.subjects['mankey']=select_current_actor(current,current['actors'][0])
                selected=select_current_actor(current,next(a for a in current['actors'] if a['species']==species))
                row=dict(phase='setup',action='bind-'+name,command='bind',snapshot=current,receipt=selected)
                before=meter.setup_index;result=meter.observe_record(row)
                with self.subTest(feature=feature,subject=name):
                    self.assertEqual(result['failures'],[])
                    self.assertEqual(meter.setup_index,before+1)
                    self.assertEqual(meter.subjects[name],selected)
                    self.assertFalse(result['passed'])
        meter=PartyThrowFlowMeasurement(SOURCE,ROUTE34);current=sample(ROUTE34,0)
        meter.latest=current;meter.setup_index=5
        wrong=dict(phase='setup',action='bind-mankey',command='bind',snapshot=current,
            receipt=select_current_actor(current,current['actors'][1]))
        self.assertIn('bound wrong species/role',str(meter.observe_record(wrong)['failures']))

    def test_native_setup_guards_complete_without_a_separate_wait_record(self):
        # Native player projection from test-882ce3061285413a89a9e867ceab0bad,
        # frame712 on ROM3710. The runner emits no row for this true wait.
        city=sample(ROUTE34,0);city['context']['mapId']=76
        city['player'].update(x=358,y=366,x_prev=358,y_prev=366,
            pos_x=23494656,pos_z=24018944,unk88_y=0,flags=536929329,movement_cmd=1)
        def initial(value):
            meter=PartyThrowFlowMeasurement(SOURCE,ROUTE34)
            meter.observe_record(dict(phase='setup',initialSnapshot=deepcopy(value)))
            return meter
        meter=initial(city)
        self.assertFalse(meter.failures);self.assertEqual(meter.setup_index,1)
        self.assertEqual(meter.setup_waits,[dict(action='saved-goldenrod-start',frame=0,
            observedFrames=0,predicate=recipe(ROUTE34)['setup'][0]['args']['predicate'])])
        chunk=deepcopy(rows(ROUTE34)[0]);chunk.update(phase='setup',action='walk-goldenrod')
        chunk['requestedInput']['keys']=['DOWN']
        self.assertFalse(meter.observe_record(chunk)['failures'])
        self.assertEqual((meter.setup_index,meter.setup_frames),(1,8))
        for fault in ('map','body','air','ready','rom','coverage','dropped','boundary'):
            wrong=deepcopy(city)
            if fault=='map':wrong['context']['mapId']=77
            elif fault=='body':wrong['player']['pos_x']+=1
            elif fault=='air':wrong['player']['unk88_y']=4096
            elif fault=='ready':wrong['player']['flags']=2
            elif fault=='rom':wrong['romSha256']='0'*64
            elif fault=='coverage':wrong['nativeObservation']['coverageComplete']=False
            elif fault=='dropped':wrong['nativeObservation']['eventsDropped']=1
            else:wrong['observationBoundary']='before-main-task'
            bad=initial(wrong);bad.observe_record(chunk)
            with self.subTest(fault=fault):self.assertTrue(bad.failures)
        duplicate=dict(phase='setup',action='saved-goldenrod-start',samples=[])
        self.assertIn('setup action order',str(initial(city).observe_record(duplicate)['failures']))
        wrong=deepcopy(chunk);wrong['requestedInput']['keys']=['RIGHT']
        self.assertIn('setup input differs',str(initial(city).observe_record(wrong)['failures']))

    def test_native_setup_wait_and_until_need_their_actual_end_predicate(self):
        # A neutral wait that really needs frames stays pending until the
        # exact current follower/party identity is idle in the native sample.
        s=sample(FOLLOWER_CARGO,0);m=s['actors'][0]
        m.update(motionPhase='IDLE',motionKind='NONE',reservationId=0)
        s['partyObservation']=dict(frame=0,boundary='main-task-queue-completion')
        s['party']=[dict(slot=i,species=0,personality=0,identityVerified=True,isEgg=False,
            form=0,level=0,hp=0,maxHp=0,status=0) for i in range(2)]+s['party']
        s['party'][2].update(isEgg=False,maxHp=15,status=0)
        s['selector']['activeFollowerPartySlot']=2
        m['engineIdentity'].update(in_manager=True,active=True,object_manager=0x02110000,
            current_manager=0x02110000,object_id=231,script_id=2074)
        meter=PartyThrowFlowMeasurement(SOURCE,FOLLOWER_CARGO)
        meter.latest=deepcopy(s);meter.setup_index=2
        meter._advance_setup_guards()
        self.assertFalse(meter.failures);self.assertEqual(meter.setup_index,3)
        self.assertEqual(meter.setup_waits[-1]['action'],'saved-follower')
        meter=PartyThrowFlowMeasurement(SOURCE,FOLLOWER_CARGO)
        meter.latest=deepcopy(s);meter.latest['actors'][0]['motionPhase']='MOVING';meter.setup_index=2
        meter._advance_setup_guards();self.assertEqual(meter.setup_index,2)
        wait=deepcopy(rows(FOLLOWER_CARGO)[0]);wait.update(phase='setup',action='saved-follower')
        wait['requestedInput']['keys']=[]
        for i,current in enumerate(wait['samples']):
            value=deepcopy(s);value.update(frame=current['frame'],nativeCycle=current['nativeCycle'])
            value['partyObservation']['frame']=value['frame']
            if i+1<len(wait['samples']):value['actors'][0]['motionPhase']='MOVING'
            wait['samples'][i]=value
        self.assertFalse(meter.observe_record(wait)['failures'])
        self.assertEqual(meter.setup_index,3);self.assertEqual(meter.setup_waits[-1]['observedFrames'],8)
        for fault in ('party','stale'):
            bad=PartyThrowFlowMeasurement(SOURCE,FOLLOWER_CARGO);bad.latest=deepcopy(s);bad.setup_index=2
            if fault=='party':bad.latest['party'][2]['personality']+=1
            else:bad.latest['partyObservation']['frame']+=1
            with self.subTest(fault=fault),self.assertRaises(ValueError):bad._advance_setup_guards()
        # Route entry has an early `until`, not a mandatory120-frame hold.
        for reaches in (False,True):
            meter=PartyThrowFlowMeasurement(SOURCE,ROUTE34);meter.latest=sample(ROUTE34,0);meter.setup_index=3
            chunk=deepcopy(rows(ROUTE34)[0]);chunk.update(phase='setup',action='enter-route34')
            chunk['requestedInput']['keys']=['DOWN']
            for current in chunk['samples']:current['player']['y']=385 if reaches else 384
            result=meter.observe_record(chunk)
            with self.subTest(reaches=reaches):
                self.assertFalse(result['failures']);self.assertEqual(meter.setup_index,4 if reaches else 3)
                self.assertEqual(meter.setup_frames,0 if reaches else 8)

    def test_first_native_pickup_may_resolve_held_profile_on_the_next_queue_only(self):
        for feature in CASES:
            stream=deepcopy(rows(feature));case=CASES[feature]
            before=next(a for a in sample(feature,4)['actors'] if a['species']==(56 if feature==ROUTE34 else 74))
            for row in stream:
                for current in row['samples']:
                    if current['frame']!=5:continue
                    carrier=next(a for a in current['actors'] if a['handle']==before['handle'])
                    carrier['matchedLayerMask']=before['matchedLayerMask'];carrier['behaviorFingerprint']=before['behaviorFingerprint']
                    row['events'].append(dict(frame=5,kind='native',data=dict(event='CONDITIONAL_RESOLVED',
                        actorHandle=carrier['handle']['value'],actor={k:v for k,v in carrier['handle'].items() if k!='value'},
                        sequence=0,traceStream=1,traceFieldEpoch=1,frame=5,actorFrame=5,valueA=0,valueB=0,reasonId=0)))
            sequence=0
            for row in stream:
                row['events'].sort(key=lambda e:e['frame'])
                for event in row['events']:
                    if event['kind']=='native':sequence+=1;event['data']['sequence']=sequence
            positive=evaluate(feature,stream)
            with self.subTest(feature=feature):
                self.assertTrue(positive['passed'],positive['failures'])
                self.assertEqual(positive['measurements'][feature]['pickupProfileEdge']['frame'],5)
            for fault in ('missing-native-edge','wrong-native-edge-frame','late-held-profile'):
                bad=deepcopy(stream)
                for row in bad:
                    for event in row['events']:
                        if event.get('data',{}).get('event')=='CONDITIONAL_RESOLVED':
                            if fault=='missing-native-edge':event['data']['event']='INTENT_ISSUED'
                            elif fault=='wrong-native-edge-frame':event['data']['actorFrame']=4
                    if fault=='late-held-profile':
                        for current in row['samples']:
                            if current['frame']!=6:continue
                            carrier=next(a for a in current['actors'] if a['handle']==before['handle'])
                            carrier['matchedLayerMask']=before['matchedLayerMask'];carrier['behaviorFingerprint']=before['behaviorFingerprint']
                result=evaluate(feature,bad)
                expected='next queue' if fault=='late-held-profile' else 'exact native free-to-HELD handoff'
                with self.subTest(feature=feature,fault=fault):
                    self.assertFalse(result['passed']);self.assertIn(expected,str(result['failures']))

    def test_native_launch_keeps_only_the_exact_prior_carried_pose_at_elapsed_zero(self):
        stream=deepcopy(rows(ROUTE34))
        for row in stream:
            for current in row['samples']:
                if current['frame'] not in (7,8):continue
                cargo=current['actors'][1];carrier=current['actors'][0]
                if current['frame']==7:
                    for k in ('pos_x','pos_y','pos_z'):cargo['engineObject'][k]=carrier['engineObject'][k]
                cargo['engineObject']['unk88_y']=32768
        positive=evaluate(ROUTE34,stream)
        self.assertTrue(positive['passed'],positive['failures'])
        self.assertEqual(positive['measurements'][ROUTE34]['flight']['launchHeightOffset'],32768)
        for fault in ('changed-launch-pose','wrong-held-lift','lift-after-launch'):
            changed=deepcopy(stream)
            frame=8 if fault=='changed-launch-pose' else 7 if fault=='wrong-held-lift' else 9
            current=next(s for row in changed for s in row['samples'] if s['frame']==frame)
            current['actors'][1]['engineObject']['unk88_y']+=1
            bad=evaluate(ROUTE34,changed)
            with self.subTest(fault=fault):
                self.assertFalse(bad['passed']);self.assertIn('wrong actual projectile pose/arc',str(bad['failures']))

    def test_projectile_and_follow_terminals_allow_only_an_exact_new_autonomous_lease(self):
        stream=deepcopy(rows(ROUTE34))
        for frame,slot,kind,lease in ((16,0,1,90),(22,7,2,91)):
            row=next(r for r in stream if any(s['frame']==frame for s in r['samples']))
            current=next(s for s in row['samples'] if s['frame']==frame)
            actor=next(a for a in current['actors'] if a['handle']['slot']==slot)
            origin=[actor['logical'][k] for k in ('x','y')];target=[origin[0]+1,origin[1]];commit=actor['commitSequence']
            motion=put_motion(actor,kind,origin,target,8,0,lease,2,commit)
            raw=bytearray.fromhex(motion['rawHex']);struct.pack_into('<H',raw,46,0)
            next(t for t in current['pokemonCombat']['targets'] if t['handle']==actor['handle'])['motion']=decode_motion(bytes(raw))
            for name,a,b in [('INTENT_CREATED',kind,1),('PLAN_ACCEPTED',(target[0]<<16)|target[1],8),('MOTION_STARTED',kind,8)]:
                row['events'].append(dict(frame=frame,kind='native',data=dict(event=name,actorHandle=actor['handle']['value'],
                    actor={k:v for k,v in actor['handle'].items() if k!='value'},sequence=0,traceStream=1,traceFieldEpoch=1,
                    frame=frame,actorFrame=frame,valueA=a,valueB=b,reasonId=0)))
        # The actual last landed pause snapshot has one frame remaining.
        prior=next(s for r in stream for s in r['samples'] if s['frame']==15)
        prior_motion=next(t for t in prior['pokemonCombat']['targets'] if t['handle']['slot']==0)
        raw=bytearray.fromhex(prior_motion['motion']['rawHex']);struct.pack_into('<H',raw,42,1)
        prior_motion['motion']=decode_motion(bytes(raw))
        def renumber(records):
            sequence=0
            for row in records:
                row['events'].sort(key=lambda e:e['frame'])
                for e in row['events']:
                    if e['kind']=='native':sequence+=1;e['data']['sequence']=sequence
        renumber(stream);positive=evaluate(ROUTE34,stream)
        self.assertTrue(positive['passed'],positive['failures'])
        measured=positive['measurements'][ROUTE34]
        self.assertEqual(measured['flight']['successor']['plan']['reservationId'],90)
        self.assertEqual(measured['followMotion']['successor']['plan']['reservationId'],91)
        for frame,slot,label in ((16,0,'projectile'),(22,7,'follow')):
            for fault in ('missing-accept','start-before-return','wrong-origin','wrong-landed-body'):
                changed=deepcopy(stream);row=next(r for r in changed if any(s['frame']==frame for s in r['samples']))
                current=next(s for s in row['samples'] if s['frame']==frame)
                actor=next(a for a in current['actors'] if a['handle']['slot']==slot)
                own=[e for e in row['events'] if e['kind']=='native' and e['frame']==frame and e['data']['actorHandle']==actor['handle']['value']]
                if fault=='missing-accept':next(e for e in own if e['data']['event']=='PLAN_ACCEPTED')['data']['event']='INTENT_CREATED'
                elif fault=='start-before-return':
                    start=next(e for e in own if e['data']['event']=='MOTION_STARTED');row['events'].remove(start)
                    row['events'].insert(row['events'].index(next(e for e in own if e['data']['event']=='CONTROL_RETURNED')),start)
                    renumber(changed)
                elif fault=='wrong-origin':
                    motion=next(t for t in current['pokemonCombat']['targets'] if t['handle']==actor['handle'])
                    raw=bytearray.fromhex(motion['motion']['rawHex']);struct.pack_into('<h',raw,8,actor['origin']['x']+1)
                    motion['motion']=decode_motion(bytes(raw))
                else:actor['engineObject']['pos_x']+=1
                bad=evaluate(ROUTE34,changed)
                with self.subTest(phase=label,fault=fault):
                    self.assertFalse(bad['passed']);self.assertIn('missing exact '+label,str(bad['failures']))

    def test_projectile_return_and_first_follower_admission_share_one_queue(self):
        # Current3713 frame898: the old projectile commit/finish/return and
        # the next normal Follower admission share one native trace queue.
        stream=rows(FOLLOWER_CARGO,follow_start=16)
        positive=evaluate(FOLLOWER_CARGO,stream)
        self.assertTrue(positive['passed'],positive['failures'])
        measured=positive['measurements'][FOLLOWER_CARGO]
        self.assertEqual(measured['frames']['landed'],16)
        self.assertEqual(measured['frames']['follow-start'],16)
        self.assertEqual(measured['frames']['follow-return'],21)
        self.assertEqual(measured['followMotion']['firstElapsed'],0)
        for fault in ('missing-projectile-return','wrong-follow-return'):
            changed=deepcopy(stream)
            for row in changed:
                for event in row['events']:
                    data=event.get('data',{})
                    if data.get('event')!='CONTROL_RETURNED':continue
                    if fault=='missing-projectile-return' and event['frame']==16:
                        data['event']='INTENT_CREATED'
                    elif fault=='wrong-follow-return' and event['frame']==21:
                        data['valueB']+=1
            bad=evaluate(FOLLOWER_CARGO,changed)
            with self.subTest(fault=fault):
                self.assertFalse(bad['passed'],'broken shared-queue lifecycle passed')
                self.assertIn('projectile' if fault=='missing-projectile-return' else 'follow',str(bad['failures']))

    def test_copied_follow_return_fault_tracks_nonzero_projectile_commit(self):
        # A saved follower can finish ordinary hops before this Throw. Its
        # projectile return is commit3 here, not a fixed commit1 sentinel.
        stream=deepcopy(rows(FOLLOWER_CARGO))
        mankey_value=stream[0]['samples'][0]['actors'][0]['handle']['value']
        def prior_hops(snapshot):
            mankey=next(a for a in snapshot['actors'] if a['handle']['slot']==7)
            mankey['commitSequence']+=2
            motion=next(t for t in snapshot['pokemonCombat']['targets'] if t['handle']==mankey['handle'])
            raw=bytearray.fromhex(motion['motion']['rawHex'])
            struct.pack_into('<H',raw,46,struct.unpack_from('<H',raw,46)[0]+2)
            motion['motion']=decode_motion(bytes(raw))
        for row in stream:
            for current in row['samples']:prior_hops(current)
            for event in row['events']:
                data=event.get('data',{})
                if event.get('kind')!='native' or data.get('actorHandle')!=mankey_value:continue
                if data.get('event') in ('LOGICAL_COMMIT','MOTION_FINISHED'):data['valueA']+=2
                elif data.get('event') in ('MOTION_CANCELED','CONTROL_RETURNED'):data['valueB']+=2
        def replay(negative=None):
            meter=seeded(FOLLOWER_CARGO);prior_hops(meter.latest);copied=[]
            for row in stream:
                current=negative.mutate(row,meter.subjects) if negative else row
                copied.append(current);meter.observe_record(current)
                if meter.failures:break
            result=meter.finish()
            return dict(passed=result['passed'],failures=result['failures'],measurements={FOLLOWER_CARGO:result}),copied
        positive,_=replay();self.assertTrue(positive['passed'],positive['failures'])
        for fault in ('wrong-follow-return','missing-return'):
            negative=PartyThrowFlowNegative(FOLLOWER_CARGO,fault);bad,copied=replay(negative)
            with self.subTest(fault=fault):
                self.assertTrue(negative.applied)
                self.assertEqual(negative.projectile_return_commit,3)
                validate_negative_result(FOLLOWER_CARGO,bad,fault)
                returns={e['frame']:e['data']['valueB'] for row in copied for e in row['events']
                    if e.get('kind')=='native' and e['data'].get('actorHandle')==mankey_value
                    and e['data'].get('event')=='CONTROL_RETURNED'}
                if fault=='wrong-follow-return':
                    self.assertEqual(returns[16],3,'copied follow fault changed the projectile return')
                    self.assertEqual(returns[22],5)
                else:self.assertNotIn(16,returns)

    def test_actual_projectile_xyz_and_follow_pose_are_required(self):
        for name,key,frame,subject in [('body','pos_z',9,'bellsprout'),('base','pos_y',9,'bellsprout'),('follow','pos_x',18,'mankey')]:
            stream=rows(ROUTE34)
            sample_at=next(s for row in stream for s in row['samples'] if s['frame']==frame)
            species=56 if subject=='mankey' else 69
            next(a for a in sample_at['actors'] if a['species']==species)['engineObject'][key]+=1
            result=evaluate(ROUTE34,stream)
            with self.subTest(name=name):
                self.assertFalse(result['passed'])
                self.assertIn('wrong actual '+('follow' if name=='follow' else 'projectile')+' pose/arc',str(result['failures']))

    def test_pursued_target_can_finish_and_start_its_next_free_move(self):
        meter=seeded(ROUTE34);before=sample(ROUTE34,4);cargo=before['actors'][1]
        old=put_motion(cargo,2,[585,401],[586,401],20,19,31,2,0)
        before['pokemonCombat']['targets'][1]['motion']=old
        meter.latest=before
        current=deepcopy(before);current.update(frame=5,actorFrame=5,nativeCycle=1005)
        combat=current['pokemonCombat'];combat.update(frame=5,nativeCycle=1005);combat['interactions'].update(frame=5,nativeCycle=1005)
        target=current['actors'][1];combat['targets'][1]['motion']=put_motion(target,2,[586,401],[587,401],20,0,32,2,1)
        events=[]
        for sequence,(name,a,b) in enumerate([('LOGICAL_COMMIT',1,2),('MOTION_FINISHED',1,2),('CONTROL_RETURNED',0,1),('MOTION_STARTED',2,20)],1):
            events.append(dict(frame=5,kind='native',data=dict(event=name,valueA=a,valueB=b,reasonId=0,sequence=sequence,traceStream=1,traceFieldEpoch=1,actorHandle=target['handle']['value'],actor={k:v for k,v in target['handle'].items() if k!='value'})))
        meter.profiles.update({p['fingerprint']:p for p in profiles(current)})
        meter._sample(current,events)
        self.assertFalse(meter.failures)
        self.assertEqual(meter.claim_frames,1)

    def test_new_free_claim_after_drop_checks_the_previous_queue_not_the_old_pickup(self):
        def dropped_or_reclaimed(frame,claimed=False):
            s=sample(ROUTE34,3 if claimed else 8)
            s.update(frame=frame,actorFrame=frame,nativeCycle=1000+frame)
            combat=s['pokemonCombat'];combat.update(frame=frame,nativeCycle=1000+frame)
            combat['interactions'].update(frame=frame,nativeCycle=1000+frame)
            cargo=s['actors'][1]
            combat['targets'][1]['motion']=put_motion(cargo,1,[585,400],[586,400],15,frame-8,98,2,8)
            combat['movementTimers'][1]['movementActorControlMode']=0
            if not claimed:
                state=combat['interactions']['throwState'];state['targetMask']=0
                state['rawHex']=(bytes(state['targets'])+struct.pack('<3H',0,state['carrierMask'],state['recoveringMask'])).hex()
            return s

        def prepared():
            meter=seeded(ROUTE34);table=event_table(ROUTE34)
            for frame in range(1,10):
                current=sample(ROUTE34,frame) if frame<8 else dropped_or_reclaimed(frame)
                meter.profiles.update({p['fingerprint']:p for p in profiles(current)})
                meter._sample(current,table[frame] if frame<8 else [])
            self.assertEqual(meter.frames['pickup'],5)
            self.assertIsNone(meter.flight)
            return meter

        meter=prepared();current=dropped_or_reclaimed(10,True)
        meter.profiles.update({p['fingerprint']:p for p in profiles(current)})
        meter._sample(current,[])
        self.assertEqual(meter.latest['frame'],10)
        self.assertTrue(meter.free_progress)
        self.assertFalse(meter.result()['ready'])

        for fault in ('frozen-pose','frozen-elapsed','mismatched-plan','stopped','current-cancel'):
            with self.subTest(fault=fault):
                meter=prepared();current=dropped_or_reclaimed(10,True);cargo=current['actors'][1]
                events=[]
                if fault=='frozen-pose':cargo['engineObject']=deepcopy(meter.latest['actors'][1]['engineObject'])
                elif fault in ('frozen-elapsed','mismatched-plan','stopped'):
                    current['pokemonCombat']['targets'][1]['motion']=put_motion(cargo,1,[585,400],[586,400],15,
                        1 if fault=='frozen-elapsed' else 2,99 if fault=='mismatched-plan' else 98,
                        0 if fault=='stopped' else 2,8)
                else:
                    events=[dict(frame=10,kind='native',data=dict(event='MOTION_CANCELED',
                        sequence=meter.trace_sequence+1,traceStream=1,traceFieldEpoch=1,
                        actorHandle=cargo['handle']['value'],actor={k:v for k,v in cargo['handle'].items() if k!='value'},
                        valueA=1,valueB=8,reasonId=16))]
                meter.profiles.update({p['fingerprint']:p for p in profiles(current)})
                with self.assertRaisesRegex(ValueError,'selection (froze|stopped|took)'):
                    meter._sample(current,events)

        def reclaimed():
            meter=prepared();current=dropped_or_reclaimed(10,True)
            meter.profiles.update({p['fingerprint']:p for p in profiles(current)})
            meter._sample(current,[])
            return meter

        def second_pickup(meter):
            current=sample(ROUTE34,5);current.update(frame=11,actorFrame=11,nativeCycle=1011)
            combat=current['pokemonCombat'];combat.update(frame=11,nativeCycle=1011)
            combat['interactions'].update(frame=11,nativeCycle=1011)
            carrier=deepcopy(meter.latest['actors'][0]);current['actors'][0]=carrier
            cargo=current['actors'][1]
            combat['targets'][1]['motion']=put_motion(cargo,1,[585,400],[586,400],15,3,98,6,8,cancel=16)
            cargo['engineObject']=deepcopy(carrier['engineObject']);cargo['engineObject']['unk88_y']+=32768
            events=[]
            for i,(actor,name,a,b,reason) in enumerate(((carrier,'CONDITIONAL_RESOLVED',0,0,0),
                    (cargo,'MOTION_CANCELED',1,8,16),(cargo,'CONTROL_RETURNED',0,8,16)),1):
                events.append(dict(frame=11,kind='native',data=dict(event=name,
                    sequence=meter.trace_sequence+i,traceStream=1,traceFieldEpoch=1,frame=11,actorFrame=11,
                    actorHandle=actor['handle']['value'],actor={k:v for k,v in actor['handle'].items() if k!='value'},
                    valueA=a,valueB=b,reasonId=reason,reason='CONTEXT_LOST' if reason else 'OK')))
            return current,events

        meter=reclaimed();current,events=second_pickup(meter)
        meter._sample(current,events)
        self.assertEqual(meter.frames['pickup'],5)
        self.assertEqual(meter.pickup_profile_edge['frame'],11)
        self.assertEqual(meter.moving_pickup['frame'],11)
        self.assertFalse(meter.result()['ready'])
        for fault in ('missing-edge','wrong-edge-frame','missing-cancel','late-held-profile'):
            with self.subTest(second_pickup=fault):
                meter=reclaimed();current,events=second_pickup(meter)
                if fault=='missing-edge':events[0]['data']['event']='INTENT_CREATED'
                elif fault=='wrong-edge-frame':events[0]['data']['actorFrame']=10
                elif fault=='missing-cancel':events[1]['data']['event']='INTENT_CREATED'
                if fault=='late-held-profile':
                    meter._sample(current,events)
                    current=deepcopy(current);current.update(frame=12,actorFrame=12,nativeCycle=1012)
                    combat=current['pokemonCombat'];combat.update(frame=12,nativeCycle=1012)
                    combat['interactions'].update(frame=12,nativeCycle=1012);events=[]
                with self.assertRaisesRegex(ValueError,'handoff|CANCEL|next queue'):
                    meter._sample(current,events)

    def test_recipe_cannot_replace_the_saved_follower_or_normal_trigger(self):
        for feature in CASES:
            original=recipe(feature);validate_recipe(original,feature)
            self.assertFalse(any(a['op']=='party' for a in original['setup']))
            for fault in ('party','target','input','condition','budget'):
                changed=deepcopy(original)
                if fault=='party':changed['setup'][0]['op']='party'
                elif fault=='target':changed['subjects'][0]['role']='WILD'
                elif fault=='input':changed['actions'][0]['args']['keys']=['B']
                elif fault=='condition':changed['requirements']=['unrelated']
                else:changed['budgets']['maxFrames']+=1
                with self.subTest(feature=feature,fault=fault),self.assertRaises(ValueError):
                    validate_recipe(changed,feature)


if __name__=='__main__':unittest.main()
