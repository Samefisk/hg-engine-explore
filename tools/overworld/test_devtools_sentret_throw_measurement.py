"""Bounded copied-stream controls for the one combined Route30 case."""
from copy import deepcopy
from pathlib import Path
import json,struct,unittest
from tools.overworld.devtools_sentret_throw_measurement import (
    SentretThrowMeasurement, KIND, SETUP, ACTIONS, RETURN_SITE, SCOPE)
from tools.overworld.devtools_sentret_throw_proof import (
    FAULTS, SentretThrowNegative, contract, measurements, validate_negative_result)
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.test_devtools_follower_throw_measurement import snapshot as throw_snapshot, events as throw_events, SOURCE as BASE
from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor

ROOT=Path(__file__).resolve().parents[2]
RECIPE=json.loads((ROOT/'tests/overworld/test-recipes/world.route30.sentret-throw-pacing.json').read_text())
SOURCE=dict(BASE,sourceSaveSha256='f'*64)
FIRST,BIRTH=121,387

def snapshot(frame):
    relative=max(0,frame-BIRTH)
    sample=throw_snapshot(relative)
    sample.update(frame=frame,nativeCycle=1000+2*frame,actorFrame=frame,sourceSaveSha256='f'*64,
        nativeObservation=dict(coverageComplete=True,installedBeforeBoot=True,eventsDropped=0,
                               pendingUnframedEvents=0,profilesEvicted=0,error=None))
    sample['context']['mapId']=34
    m,c=sample['actors'];m.update(subjectIdentity=2920357538,level=3)
    for a in (m,c):
        for field in ('logical','render','origin','target'):
            a[field]['x']-=21;a[field]['y']-=31
        a['engineObject']['x']-=21;a['engineObject']['y']-=31
        a['engineObject']['pos_x']-=21<<16;a['engineObject']['pos_z']-=31<<16
        a['sourceIdentity'].update(map_id=34,personality=a['subjectIdentity'],level=a['level'])
    sample['party']=[dict(slot=2,personality=2920357538,species=56,identityVerified=True)]
    sample['player']=dict(x=565,y=376,x_prev=565,y_prev=376,pos_x=(565<<16)+32768,pos_z=(376<<16)+32768)
    if FIRST<=frame<FIRST+240:
        sample['player'].update(x_prev=564,pos_x=(565<<16)+frame*16)
    if frame<=FIRST+255:
        m['logical']=dict(x=565,y=375)
    sentret=[actor(161,slot,100+slot,370) for slot,admitted in ((0,FIRST-3),(1,FIRST-2),(3,FIRST-1)) if frame>=admitted]
    for a in sentret:a.update(level=3)
    # Another current Sentret can move or be held before the Bell exists.
    # Negative controls must not mutate that unrelated actor.
    unrelated=next((a for a in sentret if a["handle"]["slot"]==0),None)
    if unrelated is not None and FIRST+10<=frame<FIRST+15:
        unrelated.update(motionKind="HOP",motionPhase="MOVING",motionElapsed=frame-FIRST-10,
                         motionDuration=5,target=dict(x=100,y=371),reservationId=11)
        unrelated["engineObject"]["pos_z"]+=(frame-FIRST-10)*65536//5
    sample['actors']=[m,*sentret,*([c] if frame>=BIRTH else [])]
    combat=sample['pokemonCombat'];combat.update(frame=frame,nativeCycle=sample['nativeCycle'])
    combat['interactions'].update(frame=frame,nativeCycle=sample['nativeCycle'])
    if unrelated is not None:
        combat["movementTimers"].append(dict(handle=deepcopy(unrelated["handle"]),slot=0,
            sourceIdentity=deepcopy(unrelated.get("sourceIdentity",{})),
            movementActorControlMode=int(frame==FIRST+20)))
    for t in combat['targets']:
        raw=bytearray.fromhex(t['motion'].get('rawHex',''))
        if len(raw)==52:
            x0,y0,x1,y1=struct.unpack_from('<4h',raw,8)
            struct.pack_into('<4h',raw,8,x0-21,y0-31,x1-21,y1-31)
            t['motion']=decode_motion(bytes(raw))
    sample['terrain']=dict(cells=[dict(x=564,z=375,loaded=True,collision=False,behavior=0)])
    return sample

def events(frame):
    result=[]
    after=frame-1
    if FIRST<=after<=FIRST+600:
        clock=dict(version=1,running=True,scope='nds-scheduler-ticks-not-cpu-or-instructions',
                   arm9Timestamp=after*2240760,arm7Timestamp=after*100,frameSequence=after*2)
        interval=None if after==FIRST else dict(arm9Ticks=2240760,arm7Ticks=100,frameSequence=2,actorFrames=1,nativeCycles=2)
        result.append(dict(frame=frame,kind='native-observation',data=dict(
            sequence=after-FIRST+1,observation='stock-main-loop-pacing',loopId=after-FIRST+1,
            afterQueueFrame=after,flushedAtQueueFrame=frame,returnSite=RETURN_SITE,scope=SCOPE,
            diagnosticOnly=False,setupMode='prepared',windowIndex=0,frameCounter=2,
            actorFrame=after,nativeCycle=1000+after*2,guestClock=clock,intervalFromPrevious=interval)))
    if frame in (FIRST+10,BIRTH+37):
        species=161 if frame==FIRST+10 else 69
        c=next(a for a in snapshot(frame)['actors'] if a['species']==species)
        result.append(dict(frame=frame,kind='native',data=dict(actorHandle=c['handle']['value'],
            actor={k:v for k,v in c['handle'].items() if k!='value'},sequence=1 if species==161 else 2,
            traceStream=1,event='MOTION_STARTED',valueA=2,valueB=5)))
    return result

def raw(name,start,count):
    samples=[snapshot(f) for f in range(start,start+count)];intervals=[]
    for s in samples:
        intervals.extend([dict(completedGameFrame=s['frame']-1,cpuNs=1,wallNs=1),
                          dict(completedGameFrame=s['frame'],cpuNs=1,wallNs=1)])
    return dict(phase='observe',action=name,requestedInput=dict(frames=count,keys=next(args['keys'] for n,op,args in SETUP+ACTIONS if n==name),releaseAtEnd=False,diagnosticDetails=False),samples=samples,events=[e for s in samples for e in events(s['frame'])],
                completedGameFrames=count,observedFieldFrames=count,nativeCycles=2*count,cycleIntervals=intervals)

def records():
    rows=[dict(phase='setup',initialSnapshot=snapshot(100))];frame=100
    for name,op,args in SETUP:
        if op=='teleport':frame=101
        elif op=='spawn':frame+=1
        elif op=='step':
            count=args['frames'];row=raw(name,frame+1,count);row['phase']='setup'
            rows.append(row);frame+=count;continue
        sample=snapshot(frame);receipt={}
        if op=='spawn':
            slot={'spawn-sentret-a':0,'spawn-sentret-b':1,'spawn-sentret-c':3}[name]
            a=next(a for a in sample['actors'] if a['handle']['slot']==slot)
            receipt=dict(snapshot=deepcopy(sample),events=[],value=dict(species=161,slot=slot,personality=a['subjectIdentity'],entrySpawn=dict(
                frame=frame,receipt=dict(version=1,size=64,serial=slot+1,status=1,queued=0,
                    actor={**{k:a['handle'][k] for k in ('slot','generation','fieldEpoch','mapGeneration','encounterGeneration')},'reserved':0}))))
        elif op=='bind':
            slot={'sentret-a':0,'sentret-b':1,'sentret-c':3,'mankey':7}[args['subject']]
            receipt=select_current_actor(sample,next(a for a in sample['actors'] if a['handle']['slot']==slot))
        elif op=='main-loop-pacing.arm':receipt=dict(probe=dict(armedAtQueueFrame=frame,firstObservedQueueFrame=frame+1,lastObservedQueueFrame=frame+601,guestMemoryWrites=0))
        elif op=='cpu-work.start':receipt=dict(probe=dict(maxNativeFrames=1200,failure=None))
        rows.append(dict(phase='setup',action=name,command=op,receipt=receipt,snapshot=sample))
    for name,op,args in ACTIONS:
        if op=='step':
            count=args['frames'];rows.append(raw(name,frame+1,count));frame+=count;continue
        if op=='spawn':
            prior=frame;frame=BIRTH;sample=snapshot(frame);a=next(a for a in sample['actors'] if a['species']==69)
            receipt=dict(snapshot=deepcopy(sample),events=[e for f in range(prior+1,frame+1) for e in events(f)],
                value=dict(species=69,slot=2,personality=a['subjectIdentity'],entrySpawn=dict(frame=frame,receipt=dict(
                    version=1,size=64,serial=5,status=1,queued=0,actor={**{k:a['handle'][k] for k in ('slot','generation','fieldEpoch','mapGeneration','encounterGeneration')},'reserved':0}))))
        else:
            sample=snapshot(frame)
            if op=='bind':receipt=select_current_actor(sample,next(a for a in sample['actors'] if a['species']==69))
            else:receipt=dict(probe=dict(maxNativeFrames=1200,failure=None,closed=True,observedNativeFrames=1200,
                                        frames=[dict(nativeFrame=n) for n in range(1200)]))
        rows.append(dict(phase='observe',action=name,command=op,receipt=receipt,snapshot=sample))
    return rows

def evaluate(rows):
    from tools.overworld.devtools_test_contract import TestEvaluator
    evaluator=TestEvaluator(RECIPE);evaluator.install_measurements({KIND:SOURCE})
    for row in rows:
        evaluator.observe_record(row)
        if evaluator.failures:break
    result=evaluator.finish()
    return result["measurements"][KIND]

class SentretThrowTests(unittest.TestCase):
    def test_same_window_and_existing_native_readers(self):
        result=evaluate(records());self.assertEqual(result['failures'],[]);self.assertTrue(result['passed'])
        self.assertEqual(len(result['pacing']),600);self.assertEqual(result['throw']['frame'],BIRTH+37)
        self.assertEqual(result['timingWindow'],[FIRST,FIRST+600])
        self.assertEqual(result['movingFrames'],240)
        meter=SentretThrowMeasurement(RECIPE,SOURCE)
        for row in records():
            if row.get('action')=='spawn-sentret-a':break
            meter.observe_record(row)
        self.assertEqual(meter.failures,[])
        self.assertIsNone(meter.first)
        self.assertEqual((meter.observed_frames,meter.moving_frames,meter.action_frames),(0,0,0))
        self.assertEqual(meter.latest['frame'],FIRST-4)
        replay=dict(passed=True,failures=[],observedFrames=600,measurements={KIND:result})
        record=dict(sessionId='owned',sessionCleanup=dict(sessionId='owned',closed=True,errors=[]))
        self.assertEqual(len(measurements(replay,record)),sum(map(len,contract().values())))
    def test_testjobs_independent_stream_replay_and_adapter(self):
        from tools.overworld.devtools_test_contract import TestEvaluator
        from tools.overworld.proof_adapters import get_adapter
        evaluator=TestEvaluator(RECIPE);evaluator.install_measurements({KIND:SOURCE})
        for row in records():
            result=evaluator.observe_record(row)
            self.assertEqual(result["failures"],[],row.get("action"))
        result=evaluator.finish();self.assertTrue(result["passed"],result["failures"])
        self.assertEqual(result["observedFrames"],600)
        adapter=get_adapter(KIND);self.assertEqual(adapter.contract(),contract())
        adapter.measurements(result,dict(sessionId="owned",sessionCleanup=dict(sessionId="owned",closed=True,errors=[])))

    def test_six_copied_faults_fail_for_their_claim(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                negative=SentretThrowNegative(fault);changed=[]
                for row in records():changed.append(negative.mutate(row,{}))
                self.assertTrue(negative.applied)
                result=evaluate(changed);self.assertFalse(result['passed'])
                validate_negative_result(dict(passed=False,failures=result['failures'],measurements={KIND:result}),fault)
    def test_copied_throw_faults_leave_unrelated_sentret_motion_and_held_untouched(self):
        for name in ("missing-held","missing-launch"):
            negative=SentretThrowNegative(KIND+":"+name);original=records();changed=[]
            for row in original:changed.append(negative.mutate(row,{}))
            self.assertTrue(negative.applied)
            early=next(r for r in changed if r.get("action")=="left120")
            event=next(e for e in early["events"] if e["kind"]=="native")
            self.assertEqual(event["data"]["actor"]["slot"],0)
            self.assertEqual(event["data"]["event"],"MOTION_STARTED")
            sample=next(s for s in early["samples"] if s["frame"]==FIRST+20)
            timer=next(t for t in sample["pokemonCombat"]["movementTimers"] if t["slot"]==0)
            self.assertEqual(timer["movementActorControlMode"],1)
            result=evaluate(changed)
            validate_negative_result(dict(passed=False,failures=result["failures"],measurements={KIND:result}),KIND+":"+name)

    def test_record_start_semantic_prefix_is_checked_without_motion_credit(self):
        rows=records();initial=rows[0];m=initial["initialSnapshot"]["actors"][0]
        initial.update(initialEventStartFrame=99,initialEvents=[dict(frame=100,kind="native",data=dict(
            actorHandle=m["handle"]["value"],actor={k:v for k,v in m["handle"].items() if k!="value"},
            traceStream=1,sequence=1,event="ACTOR_ATTACHED",valueA=1,valueB=m["subjectIdentity"]))])
        for row in rows[1:]:
            for event in row.get("events",[])+row.get("receipt",{}).get("events",[]):
                if event["kind"]=="native":event["data"]["sequence"]+=1
        self.assertTrue(evaluate(rows)["passed"])
        missing=deepcopy(rows);missing[0]["initialEvents"]=[]
        self.assertFalse(evaluate(missing)["passed"])
        stale=deepcopy(rows);stale[0]["initialEvents"][0]["frame"]=98
        self.assertFalse(evaluate(stale)["passed"])

    def test_strict_semantic_stream_and_trace_notices_use_existing_evaluator(self):
        faults=("sequence-gap","sequence-duplicate","wrong-handle","reset","filter","expired","unknown","unread-loss","incomplete","overwrite-missing-count")
        for fault in faults:
            rows=records();neutral=next(r for r in rows if r.get("action")=="neutral348")
            native=next(e for e in neutral["events"] if e["kind"]=="native")
            if fault=="sequence-gap":native["data"]["sequence"]+=1
            elif fault=="sequence-duplicate":neutral["events"].append(deepcopy(native));neutral["events"].sort(key=lambda e:e["frame"])
            elif fault=="wrong-handle":native["data"]["actorHandle"]+=1
            else:
                data=dict(code="ring-overwrite",traceStream=1,diagnosticOnly=True,count=1,unreadEventsLost=0)
                if fault=="reset":data["code"]="sequence-reset"
                elif fault=="filter":data["code"]="trace-filter-changed"
                elif fault=="expired":data.update(code="window-ended",reason="budget-expired-or-disarmed")
                elif fault=="unknown":data["code"]="unknown-notice"
                elif fault=="unread-loss":data["unreadEventsLost"]=1
                elif fault=="incomplete":data["coverageComplete"]=False
                elif fault=="overwrite-missing-count":del data["count"]
                neutral["events"].insert(0,dict(frame=neutral["samples"][0]["frame"],kind="trace-status",data=data))
            with self.subTest(fault=fault):self.assertFalse(evaluate(rows)["passed"])
        rows=records();neutral=next(r for r in rows if r.get("action")=="neutral348")
        neutral["events"].insert(0,dict(frame=neutral["samples"][0]["frame"],kind="trace-status",
            data=dict(code="ring-overwrite",traceStream=1,diagnosticOnly=True,count=7,unreadEventsLost=0)))
        self.assertTrue(evaluate(rows)["passed"])

    def test_drop_missing_loop_clock_and_full_identity(self):
        for change in ('loop-gap','clock','cargo-generation','sentret-lost','source-save','render-stall','wrong-keys','wrong-input-count','engine-replacement'):
            rows=records();neutral=next(r for r in rows if r.get('action')=='neutral348')
            if change=='loop-gap':neutral['events'].pop(0)
            elif change=='clock':neutral['events'][0]['data']['guestClock']['arm9Timestamp']+=1
            elif change=='cargo-generation':neutral['samples'][20]['actors'][-1]['handle']['generation']+=1
            elif change=='sentret-lost':neutral['samples'][20]['actors'][1]['active']=False
            elif change=='source-save':neutral['samples'][20]['sourceSaveSha256']='0'*64
            elif change=='wrong-keys':neutral['requestedInput']['keys']=['RIGHT']
            elif change=='wrong-input-count':neutral['requestedInput']['frames']-=1
            elif change=='engine-replacement':neutral['samples'][20]['actors'][1]['engineIdentity']['pointer']+=4
            else:
                left=next(r for r in rows if r.get('action')=='left120');left['samples'][1]['player']['pos_x']=left['samples'][0]['player']['pos_x']
            with self.subTest(change=change):self.assertFalse(evaluate(rows)['passed'])
    def test_permanent_scenario_and_exact_registration(self):
        from tools.overworld.validation import validate_scenario,validate_feature_manifest
        from tools.overworld.control import _shared_test_registration
        scenario_path=ROOT/'tests/overworld/scenarios/world.route30.sentret-throw-pacing.json'
        validate_scenario(json.loads(scenario_path.read_text()),scenario_path)
        feature_path=ROOT/'tools/overworld/system_features.yaml'
        validate_feature_manifest(json.loads(feature_path.read_text()),feature_path)
        registered,_=_shared_test_registration(RECIPE,ROOT)
        self.assertEqual(registered['measurementContract'],contract())
        bad=deepcopy(RECIPE);bad['requirements']=['current.unmounted-zero-stutter']
        with self.assertRaises(ValueError):_shared_test_registration(bad,ROOT)

    def test_exact_recipe_and_public_command_schema(self):
        from tools.overworld.devtools_test_contract import validate_test
        validate_test(RECIPE)
        for action in RECIPE['setup']+RECIPE['actions']:
            if action['op']!='bind':
                from tools.overworld.devtools_contract import validate_command
                self.assertEqual(validate_command(action['op'],action['args']),action['args'])
        self.assertEqual(RECIPE["setup"][0]["budget"]["maxFrames"],120)
        self.assertGreaterEqual(RECIPE["setup"][0]["budget"]["maxFrames"],46)
        bad=deepcopy(RECIPE);bad["setup"][0]["budget"].update(maxFrames=1,noProgressFrames=1)
        with self.assertRaises(ValueError):validate_test(bad)
        wait=RECIPE['setup'][1]
        self.assertEqual(wait,dict(id='route30-settle16',op='step',args=dict(frames=16,keys=[]),
                                  budget=dict(maxSeconds=90,maxFrames=16,noProgressFrames=16)))
        for change in ('keys','count','budget','missing','order'):
            bad=deepcopy(RECIPE)
            if change=='keys':bad['setup'][1]['args']['keys']=['LEFT']
            elif change=='count':bad['setup'][1]['args']['frames']=15
            elif change=='budget':bad['setup'][1]['budget']['maxFrames']=17
            elif change=='missing':bad['setup'].pop(1)
            else:bad['setup'][1],bad['setup'][2]=bad['setup'][2],bad['setup'][1]
            with self.subTest(setup=change),self.assertRaises(ValueError):validate_test(bad)
        for keys,frames in (([],119),(['RIGHT'],120)):
            bad=deepcopy(RECIPE);bad['actions'][0]['args']=dict(keys=keys,frames=frames)
            with self.assertRaises(ValueError):validate_test(bad)

if __name__=='__main__':unittest.main()
