"""Copied current native-shape controls for both fixed signed-height cases."""
from copy import deepcopy
import json,struct,unittest
from pathlib import Path
from tools.overworld.devtools_cross_height_throw_measurement import (
    KINDS,CASES,FOLLOWER,FIND_CARGO,RELEASE,TRIGGER_CONDITION,CARGO_CONDITION,
    CrossHeightThrowMeasurement,actions,setup,subjects,validate_recipe,
)
from tools.overworld.devtools_cross_height_throw_proof import (
    faults,CrossHeightThrowNegative,validate_negative_result,measurements,contract,
)
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_profile_feature_measurement import application_index
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.test_devtools_follower_throw_measurement import snapshot as old_snapshot,binding

SOURCE=dict(contractVersion=1,romSha256='a'*64,overlaySha256='b'*64,profileSha256='c'*64)
ROOT=Path(__file__).resolve().parents[2]


def motion(frame,kind,actor):
    raw=bytearray(52)
    if frame>=5:
        c=CASES[kind];start=65536 if c['sign']==1 else 267648;target=122880 if c['sign']==1 else 65536
        struct.pack_into('<HBBHH4h2iHH',raw,0,1,2,2 if c['sign']==1 else 1,1,0,*[actor[p][k] for p in ('origin','target') for k in ('x','y')],start,target,2,9)
        raw[28]=2 if c['sign']==1 else 1
        raw[29]=sum(abs(actor['target'][k]-actor['origin'][k]) for k in ('x','y'))
        struct.pack_into('<4H4B',raw,40,min(frame-5,2),0,0,int(frame>=7),2 if frame<7 else 0,0,int(frame>=7),0)
    return decode_motion(bytes(raw))


def snapshot(kind,frame):
    s=old_snapshot(9);s.update(frame=frame,actorFrame=frame+100,nativeCycle=frame+1000);s['context']['mapId']=67
    s['pokemonCombat'].update(frame=frame,nativeCycle=frame+1000,schemaVersion=1)
    case=CASES[kind];s['player'].update(x=case['player'][0],y=case['player'][1],pos_y=65536,facing=case['player'][2]);s['party'][0].update(level=20)
    m,t,c=s['actors'];t.update(species=case['trigger'],level=20);c.update(species=case['cargo'],level=20)
    initial=(555,398) if case['sign']==1 else (560,391)
    carrier=initial if frame<2 else ((554,398) if case['sign']==1 else (560,391))
    cargo=case['cargoTile'] if frame<2 else carrier if frame<7 else case['target']
    for a,xy,y in ((m,carrier,65536 if case['sign']==1 else 267648),
                   (t,case['target'],122880 if case['sign']==1 else 65536),
                   (c,cargo,65536 if case['sign']==1 else 267648)):
        a.update(logical=dict(x=xy[0],y=xy[1]),origin=dict(x=xy[0],y=xy[1]),target=dict(x=xy[0],y=xy[1]),
            motionKind='NONE',motionPhase='IDLE',motionElapsed=0,motionDuration=0,reservationId=0,commitSequence=0)
        a['engineObject'].update(x=xy[0],y=xy[1],pos_x=(xy[0]<<16)+32768,pos_z=(xy[1]<<16)+32768,pos_y=y,face_y=0,unk88_y=0)
    m['engineObject']['facing']=2 if case['sign']==1 else 1
    t['matchedLayerMask']=1<<application_index('apply-idle')
    m['matchedLayerMask']=FOLLOWER|(FIND_CARGO if frame<5 or frame>=9 else 0)|(RELEASE if frame in (3,4) else 0)
    if frame>=5:
        c.update(origin=dict(x=carrier[0],y=carrier[1]),target=dict(x=case['target'][0],y=case['target'][1]),
            motionKind='HOP',motionPhase='MOVING' if frame<7 else 'IDLE',motionElapsed=min(frame-5,2),motionDuration=2,
            reservationId=9 if frame<7 else 0,commitSequence=int(frame>=7))
        fraction=min(frame-5,2)
        for coord,axis in [('pos_x',0),('pos_z',1)]:
            c['engineObject'][coord]=((carrier[axis]<<16)+32768)+((case['target'][axis]-carrier[axis])<<16)*fraction//2
        start=65536 if case['sign']==1 else 267648;target=122880 if case['sign']==1 else 65536
        c['engineObject']['pos_y']=start+(target-start)*fraction//2
    bound=1<=frame<=4 or frame>=9
    trigger=binding(t if bound else None,TRIGGER_CONDITION);cargo_binding=binding(c if 1<=frame<=4 else None,CARGO_CONDITION)
    encoded=3 if frame==1 else 131 if frame==2 else 195 if frame in (3,4) else 0
    values=[0]*10;values[7]=encoded;mask=(4 if encoded else 0,128 if encoded else 0,128 if frame>=5 else 0)
    carrier_row=s['pokemonCombat']['interactions']['carriers'][0]
    carrier_row.update(bindings=dict(trigger=trigger,cargo=cargo_binding),
        rawBindingsHex=(raw_handle(m['handle'])+bytes.fromhex(trigger['rawHex'])+bytes.fromhex(cargo_binding['rawHex'])).hex(),
        throw=dict(targetRaw=encoded,targetSlot=2 if encoded else None,carried=bool(encoded&128),windup=bool(encoded&64),
                   targeted=False,carrier=bool(encoded),recovering=frame>=5))
    s['pokemonCombat']['interactions'].update(frame=frame,nativeCycle=frame+1000,
        throwState=dict(targets=values,targetMask=mask[0],carrierMask=mask[1],recoveringMask=mask[2],rawHex=(bytes(values)+struct.pack('<3H',*mask)).hex()))
    s['pokemonCombat']['targets']=[dict(handle=deepcopy(a['handle']),hp=80 if a is t and frame>=7 else 100,
        currentHp=80 if a is t and frame>=7 else 100,maxHp=100,hpSource='wild-resident',
        hitCount=int(a is t and frame>=7),lastDamage=20 if a is t and frame>=7 else 0,
        immunityFrames=60 if a is t and frame>=7 else 0,motion=motion(frame if a is c else 0,kind,c)) for a in (t,c)]
    return s


def events(s):
    if s['frame'] not in (5,7):return []
    a=s['actors'][2];names=('MOTION_STARTED',) if s['frame']==5 else ('LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED')
    return [dict(frame=s['frame'],kind='native',data=dict(frame=s['actorFrame'],actorFrame=s['actorFrame'],actorHandle=a['handle']['value'],
        actor={k:v for k,v in a['handle'].items() if k!='value'},sequence=s['frame']*10+i,event=n,reason='OK',
        valueA=2 if n=='MOTION_STARTED' else 0 if n=='CONTROL_RETURNED' else 1,
        valueB=1 if n=='CONTROL_RETURNED' else 2)) for i,n in enumerate(names)]


def stream(kind):
    def raw(name,frames):
        samples=[snapshot(kind,f) for f in frames]
        return dict(phase='observe',action=name,samples=samples,events=[e for s in samples for e in events(s)],
            completedGameFrames=len(samples),observedFieldFrames=len(samples),nativeCycles=len(samples),
            cycleIntervals=[dict(completedGameFrame=s['frame'],cpuNs=1,wallNs=1) for s in samples])
    return [raw(actions(kind)[0][0],range(1,6)),raw(actions(kind)[1][0],range(6,10))]


def above_fixture(m,sample):
    t=sample['actors'][1]
    pot=dict(x=550,z=398,loaded=True,collision=True,
        provenance=dict(chunkModelLoaded=1,mapHeaderId=67,chunkMatrixIndex=581,currentMatrixIndex=581),
        surface=dict(known=True,present=True,finalHeightKnown=True,heightMode='absolute',
            type='flowerbed',surfaceId=9304,modelIndex=5,instanceIndex=130,anchorMatrixIndex=581,heightFx32=122880))
    clear=[dict(x=x,z=z,loaded=True,collision=False,
        provenance=dict(chunkModelLoaded=1,mapHeaderId=67,chunkMatrixIndex=581,currentMatrixIndex=581),
        surface=dict(known=True,present=False)) for x,z in [(x,398) for x in range(551,556)]+[CASES[KINDS[0]]['cargoTile']]]
    sample['terrain']=dict(cells=[pot]+clear,observation=dict(nativeCycle=sample['nativeCycle'],
        lastCompletedGameFrame=sample['frame'],context=deepcopy(sample['context'])))
    m.above_fixture=m._above_support(sample,t)


def below_fixture(m,sample):
    cells=[]
    for x,z in ((560,391),CASES[KINDS[1]]['cargoTile']):
        cells.append(dict(x=x,z=z,loaded=True,collision=True,
            provenance=dict(chunkModelLoaded=1,mapHeaderId=67,chunkMatrixIndex=581,currentMatrixIndex=581),
            surface=dict(known=True,present=True,type='canopy',surfaceId=65534,modelIndex=5,
                instanceIndex=117,heightMode='native-ground-offset',heightOffsetFx32=202112)))
    for z in range(392,397):
        cells.append(dict(x=560,z=z,loaded=True,collision=False,
            provenance=dict(chunkModelLoaded=1,mapHeaderId=67,chunkMatrixIndex=581,currentMatrixIndex=581),
            surface=dict(known=True,present=False)))
    sample['terrain']=dict(cells=cells,observation=dict(nativeCycle=sample['nativeCycle'],
        lastCompletedGameFrame=sample['frame'],context=deepcopy(sample['context'])))
    m.below_fixture=m._below_carrier(sample,sample['actors'][0])
    m.below_target=m._below_trigger(sample,sample['actors'][1])


def native_spawn(sample,name,locomotion):
    a=sample['actors'][1 if name=='trigger' else 2];xy=[a['engineObject'][k] for k in ('x','y')]
    encounter={k:a[k] for k in ('species','form','level')};encounter['personality']=a['subjectIdentity']
    raw=bytearray(30);struct.pack_into('<ii',raw,0,*xy)
    struct.pack_into('<IHBB4hBB',raw,12,encounter['personality'],encounter['species'],encounter['form'],encounter['level'],*xy,*xy,locomotion,0)
    spawn=dict(slot=a['handle']['slot'],terrain=0,statePointer=1,fieldPointer=2,preparedPointer=3,
        worldContext=dict(fieldPointer=2,statePointer=1,**sample['context']),preparedPrefixHex=raw.hex(),
        preparedEncounter=encounter,startup=dict(target=xy,origin=xy,locomotion=locomotion,hopDirection=0,targetBaseY=0),
        position=xy,publicSubject=select_current_actor(sample,a),returnValue=1,sequence=2)
    final={k:deepcopy(v) for k,v in spawn.items() if k not in ('publicSubject',)}
    final.update(sequence=1,pairEligible=True,returnWorldContext=deepcopy(spawn['worldContext']))
    spawn['finalization']=dict(status='matched',receipt=final)
    return dict(value=dict(slot=a['handle']['slot'],personality=a['subjectIdentity'],species=a['species']),
        events=[dict(kind='native-observation',data=dict(observation='spawn-prepared',**spawn))])


def evaluate(kind,negative=None,setup_capture=False):
    m=CrossHeightThrowMeasurement(SOURCE,kind);m.latest=snapshot(kind,0);m.setup_index=len(setup(kind))
    m.subjects={n:select_current_actor(m.latest,next(a for a in m.latest['actors'] if a['species']==sp and a['role']==role)) for n,sp,role,_ in subjects(kind)}
    if kind==KINDS[0]:above_fixture(m,m.latest)
    else:below_fixture(m,m.latest)
    if setup_capture:
        row=dict(phase="setup",command="spawn",action="spawn-trigger",snapshot=snapshot(kind,1))
        m._probe((negative.mutate(row,m.subjects) if negative else row)["snapshot"])
    for row in stream(kind):
        m.observe_record(negative.mutate(row,m.subjects) if negative else row)
        if m.failures:break
    r=m.finish()
    return dict(passed=r['passed'],failures=r['failures'],observedFrames=r['observedFrames'],measurements={kind:r})


class CrossHeightThrowTests(unittest.TestCase):
    def test_above_and_below_native_shape_keep_aim_terminal_and_contact(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                r=evaluate(kind);self.assertTrue(r['passed'],r)
                record=dict(sessionId='owned',sessionCleanup=dict(sessionId='owned',closed=True,errors=[]))
                self.assertEqual(len(measurements(kind,r,record)),sum(map(len,contract(kind).values())))
                self.assertEqual(r['measurements'][kind]['frames']['vision'],1)

    def test_named_copied_controls_keep_strict_gates(self):
        for kind in KINDS:
            for fault in faults(kind):
                with self.subTest(fault=fault):
                    n=CrossHeightThrowNegative(kind,fault);r=evaluate(kind,n)
                    self.assertTrue(n.applied);self.assertFalse(r['passed'],r);validate_negative_result(kind,r,fault)

    def test_missing_vision_control_removes_setup_capture_before_observe(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                baseline=evaluate(kind,setup_capture=True);self.assertTrue(baseline["passed"],baseline)
                n=CrossHeightThrowNegative(kind,kind+":missing-vision")
                changed=evaluate(kind,n,setup_capture=True)
                self.assertTrue(n.applied);self.assertFalse(changed["passed"]);validate_negative_result(kind,changed,n.kind+":missing-vision")
                self.assertNotIn("vision",changed["measurements"][kind]["frames"])
                sample=snapshot(kind,1);row=dict(phase="setup",snapshot=sample)
                subject={"mankey":select_current_actor(sample,sample["actors"][0])}
                copied=n.mutate(row,subject)
                self.assertEqual(copied["snapshot"]["actors"],sample["actors"])
                self.assertEqual(row["snapshot"]["pokemonCombat"]["interactions"]["carriers"][0]["bindings"]["trigger"]["bound"],True)
                self.assertFalse(copied["snapshot"]["pokemonCombat"]["interactions"]["carriers"][0]["bindings"]["trigger"]["bound"])

    def test_position_y_latch_excludes_temporary_body_bob(self):
        kind=KINDS[0];m=CrossHeightThrowMeasurement(SOURCE,kind);m.latest=snapshot(kind,0);m.setup_index=len(setup(kind))
        m.subjects={n:select_current_actor(m.latest,next(a for a in m.latest["actors"] if a["species"]==sp and a["role"]==role)) for n,sp,role,_ in subjects(kind)}
        above_fixture(m,m.latest)
        for row in stream(kind):
            for sample in row["samples"]:
                sample["actors"][1]["engineObject"]["face_y"]=8192
                sample["actors"][1]["engineObject"]["unk88_y"]=4096
            m.observe_record(row)
        self.assertTrue(m.finish()["passed"],m.finish())
        self.assertEqual(m.windup["physicalY"],122880)

    def test_below_current_high_start_and_clear_ray_guards(self):
        for fault in (None,'flat-carrier','moving','wrong-facing','early-binding','blocked-ray','unknown-canopy','stale-terrain'):
            m=CrossHeightThrowMeasurement(SOURCE,KINDS[1]);sample=snapshot(KINDS[1],0);below_fixture(m,sample)
            actor=sample['actors'][0]
            if fault=='flat-carrier':actor['engineObject']['pos_y']=65536
            elif fault=='moving':actor['motionPhase']='MOVING';actor['reservationId']=1
            elif fault=='wrong-facing':actor['engineObject']['facing']=0
            elif fault=='early-binding':sample=snapshot(KINDS[1],1);sample['terrain']=deepcopy(m.latest['terrain']) if m.latest else {}
            elif fault=='blocked-ray':sample['terrain']['cells'][2]['collision']=True
            elif fault=='unknown-canopy':sample['terrain']['cells'][0]['surface']['known']=False
            elif fault=='stale-terrain':sample['terrain']['observation']['context']['mapGeneration']+=1
            with self.subTest(fault=fault):
                if fault:
                    with self.assertRaises(ValueError):
                        m._below_carrier(sample,sample['actors'][0]);m._below_trigger(sample,sample['actors'][1])
                else:self.assertEqual(m._below_carrier(sample,actor)['physicalY'],267648)

    def test_below_native_cargo_handoff_rejects_flat_or_replaced_encounter(self):
        kind=KINDS[1];sample=snapshot(kind,0)
        for fault in (None,'flat-cargo','wrong-identity','wrong-site','wrong-startup'):
            s=deepcopy(sample);m=CrossHeightThrowMeasurement(SOURCE,kind);below_fixture(m,s)
            m.latest=deepcopy(s);m.subjects={n:select_current_actor(s,s['actors'][i]) for i,n in enumerate(('mankey','trigger','cargo'))}
            receipt=native_spawn(s,'cargo',7)
            if fault=='wrong-identity':receipt['value']['personality']+=1
            elif fault=='wrong-site':s['actors'][2]['engineObject']['x']+=1
            elif fault=='wrong-startup':receipt=native_spawn(s,'cargo',3)
            m.setup_index=8
            m.observe_record(dict(phase='setup',action='spawn-cargo',command='spawn',snapshot=s,receipt=receipt))
            if fault=='flat-cargo':s['actors'][2]['engineObject']['pos_y']=65536
            if not m.failures:
                m.observe_record(dict(phase='setup',action='bind-cargo',command='bind',snapshot=s,receipt=select_current_actor(s,s['actors'][2])))
            with self.subTest(fault=fault):
                if fault:self.assertTrue(m.failures)
                else:self.assertFalse(m.failures,m.failures)

    def test_exact_recipes_factory_and_adapter_routing(self):
        from tools.overworld.devtools_test_contract import validate_test,TestEvaluator
        from tools.overworld.proof_adapters import get_adapter
        for kind in KINDS:
            recipe=json.loads((ROOT/('tests/overworld/test-recipes/'+CASES[kind]['id']+'.json')).read_text())
            t=validate_test(recipe);e=TestEvaluator(t);e.install_measurements({kind:SOURCE})
            self.assertTrue(e.uses_raw_records);self.assertIsInstance(e.measurements[kind],CrossHeightThrowMeasurement)
            self.assertEqual(get_adapter(kind).contract(),contract(kind))
            self.assertEqual(get_adapter(kind).recipe_subjects(),t["subjects"])
            from tools.overworld import control
            control._shared_test_registration(t,ROOT)
            for cargo in (70,161) if kind==KINDS[1] else (70,161):
                wrong=deepcopy(t);wrong["subjects"][-1]["species"]=cargo
                with self.subTest(kind=kind,cargo=cargo),self.assertRaises(ValueError):
                    control._shared_test_registration(wrong,ROOT)
            changed=deepcopy(recipe);changed['setup'][0]['args']['x']+=1
            with self.assertRaisesRegex(ValueError,'fixed fixture'):validate_test(changed)

    def test_above_current_pot_and_ground_facing_controls(self):
        kind=KINDS[0]
        for fault in (None,'catalog-only','wrong-pot','unknown-height','flat-native','active-ambush','stale-terrain','wrong-facing','blocked-ray','unknown-ray','missing-ray'):
            m=CrossHeightThrowMeasurement(SOURCE,kind);s=snapshot(kind,0);above_fixture(m,s)
            m.subjects={n:select_current_actor(s,next(a for a in s['actors'] if a['species']==sp and a['role']==role))
                for n,sp,role,_ in subjects(kind)}
            if fault=='catalog-only':s['terrain']={}
            elif fault=='wrong-pot':s['terrain']['cells'][0]['surface']['surfaceId']+=1
            elif fault=='unknown-height':s['terrain']['cells'][0]['surface']['finalHeightKnown']=False
            elif fault=='flat-native':s['actors'][1]['engineObject']['pos_y']=65536
            elif fault=='active-ambush':s['actors'][1]['matchedLayerMask']|=1<<application_index('apply-ambush')
            elif fault=='stale-terrain':s['terrain']['observation']['context']['mapGeneration']+=1
            elif fault=='wrong-facing':s['actors'][0]['engineObject']['facing']=0
            elif fault=='blocked-ray':s['terrain']['cells'][1]['collision']=True
            elif fault=='unknown-ray':s['terrain']['cells'][1]['surface']['known']=False
            elif fault=='missing-ray':del s['terrain']['cells'][1]
            if fault:
                with self.subTest(fault=fault),self.assertRaises(ValueError):
                    m._above_carrier(s,s['actors'][0]);m._above_support(s,s['actors'][1])
            else:
                m._above_carrier(s,s['actors'][0]);self.assertEqual(m._above_support(s,s['actors'][1])['physicalY'],122880)

    def test_above_passive_native_spawn_handoff_and_resampling_reject(self):
        from tools.overworld.devtools_test_contract import TestEvaluator,validate_test
        kind=KINDS[0];recipe=json.loads((ROOT/'tests/overworld/test-recipes/follower.throw-target-above.json').read_text())
        for fault in (None,'hop-startup','changed-destination','stale-id'):
            s=snapshot(kind,0);m=CrossHeightThrowMeasurement(SOURCE,kind);above_fixture(m,s)
            receipt=native_spawn(s,'trigger',0)
            if fault=='hop-startup':receipt=native_spawn(s,'trigger',7)
            elif fault=='changed-destination':
                s['actors'][1]['engineObject']['x']+=1;s['actors'][1]['logical']['x']+=1
                receipt=native_spawn(s,'trigger',0)
            elif fault=='stale-id':receipt['value']['personality']+=1
            row=dict(phase='setup',action='spawn-trigger',command='spawn',snapshot=s,receipt=receipt)
            e=TestEvaluator(validate_test(recipe));e.install_measurements({kind:SOURCE})
            e.measurements[kind].setup_index=4;e.measurements[kind].subjects={'mankey':select_current_actor(s,s['actors'][0])}
            result=e.observe_record(row)
            with self.subTest(fault=fault):
                if fault:self.assertTrue(result['failures'])
                else:self.assertFalse(result['failures'],result);self.assertIsNotNone(e.measurements[kind].above_fixture)

    def test_settled_flight_commit_then_return_and_new_walk(self):
        kind=KINDS[1]
        def run(fault=None,prior_commit=0):
            m=CrossHeightThrowMeasurement(SOURCE,kind);m.latest=snapshot(kind,0);below_fixture(m,m.latest)
            m.subjects={n:select_current_actor(m.latest,m.latest['actors'][i]) for i,n in enumerate(('mankey','trigger','cargo'))}
            for frame in range(1,9):
                s=snapshot(kind,frame);c=s['actors'][2];ev=events(s)
                if frame==7:
                    c['motionPhase']='SETTLING'
                    hp=next(h for h in s['pokemonCombat']['targets'] if h['handle']==c['handle'])
                    raw=bytearray.fromhex(hp['motion']['rawHex']);raw[48]=4;hp['motion']=decode_motion(bytes(raw))
                    ev=[e for e in ev if e['data']['event']=='LOGICAL_COMMIT']
                    if fault=='missing-commit':ev=[]
                if frame==8:
                    finished=dict(sequence=80,event='MOTION_FINISHED',reason='OK',valueA=prior_commit+1,valueB=2)
                    returned=dict(sequence=81,event='CONTROL_RETURNED',reason='OK',valueA=0,valueB=prior_commit+1)
                    started=dict(sequence=82,event='MOTION_STARTED',reason='OK',valueA=1,valueB=16)
                    ev=[dict(frame=frame,kind='native',data=dict(frame=s['actorFrame'],actorFrame=s['actorFrame'],actorHandle=c['handle']['value'],
                        actor={k:v for k,v in c['handle'].items() if k!='value'},**data)) for data in (finished,returned,started)]
                    hp=next(h for h in s['pokemonCombat']['targets'] if h['handle']==c['handle'])
                    raw=bytearray.fromhex(hp['motion']['rawHex']);raw[2]=1;raw[48]=2
                    struct.pack_into('<4h2iHH',raw,8,*CASES[kind]['target'],560,397,65536,65536,16,10);struct.pack_into('<H',raw,40,0)
                    hp['motion']=decode_motion(bytes(raw));c.update(motionKind='WALK',motionPhase='MOVING',reservationId=10,motionDuration=16,motionElapsed=0,origin=dict(x=560,y=396),target=dict(x=560,y=397))
                    if fault=='missing-finish':ev=ev[1:]
                    elif fault=='missing-control':ev=[ev[0],ev[2]]
                    elif fault=='early-start':ev[2]['data']['sequence']=79
                    elif fault=='wrong-cargo':ev[0]['data']['actor']['generation']+=1
                    elif fault=='wrong-reservation':c['reservationId']=11
                    elif fault=='wrong-plan':
                        raw=bytearray.fromhex(hp['motion']['rawHex']);struct.pack_into('<h',raw,8,559);hp['motion']=decode_motion(bytes(raw))
                    elif fault=='wrong-clock':ev[0]['data']['frame']+=1
                if frame==6 and fault=='early-overwrite':
                    hp=next(h for h in s['pokemonCombat']['targets'] if h['handle']==c['handle'])
                    raw=bytearray.fromhex(hp['motion']['rawHex']);raw[2]=1;hp['motion']=decode_motion(bytes(raw))
                c['commitSequence']+=prior_commit
                hp=next(h for h in s['pokemonCombat']['targets'] if h['handle']==c['handle'])
                raw=bytearray.fromhex(hp['motion']['rawHex']);struct.pack_into('<H',raw,46,c['commitSequence']);hp['motion']=decode_motion(bytes(raw))
                if frame==7:
                    for event in ev:event['data']['valueA']+=prior_commit
                try:m._sample(s,ev)
                except ValueError as error:return str(error)
            return m.result()
        for prior_commit in (0,7):self.assertTrue(run(prior_commit=prior_commit)['ready'],run(prior_commit=prior_commit))
        for fault in ('missing-commit','missing-finish','missing-control','early-start','wrong-cargo','wrong-reservation','wrong-plan','wrong-clock','early-overwrite'):
            with self.subTest(fault=fault):self.assertIsInstance(run(fault),str)

    def test_below_same_height_capture_and_late_recapture_do_not_earn_vision(self):
        kind=KINDS[1];m=CrossHeightThrowMeasurement(SOURCE,kind);m.latest=snapshot(kind,0)
        m.setup_index=len(setup(kind));below_fixture(m,m.latest)
        m.subjects={n:select_current_actor(m.latest,m.latest['actors'][i]) for i,n in enumerate(('mankey','trigger','cargo'))}
        for row in stream(kind):
            for sample in row['samples']:
                if sample['frame']<3:sample['actors'][1]['engineObject']['pos_y']=267648
            m.observe_record(row)
        self.assertFalse(m.finish()['passed']);self.assertNotIn('vision',m.frames)
        # Once flight starts, even a fresh lower rebind is not initial sight.
        m=CrossHeightThrowMeasurement(SOURCE,kind);sample=snapshot(kind,9);below_fixture(m,snapshot(kind,0))
        m.subjects={n:select_current_actor(sample,sample['actors'][i]) for i,n in enumerate(('mankey','trigger','cargo'))}
        m.flight={'frame':5};m._probe(sample);self.assertNotIn('vision',m.frames)


if __name__=='__main__':unittest.main()
