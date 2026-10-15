"""Focused raw native emote controls. Synthetic data is not game proof."""
from copy import deepcopy
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_actor_inspect_probe import ENGINE_OWNER_KEYS, GENERATION_KEYS
from tools.overworld.devtools_emote_vram_diagnostics import STOCK_SEALS, decode_emote_owner
from tools.overworld.devtools_emote_three_probe import QUIET, EXTRA_SEALS, ORDER, EmoteThreeProbe
from tools.overworld.devtools_emote_three_measurement import (
    KIND, SUBJECTS, SETUP, ACTIONS, EmoteThreeMeasurement, checked_burst, checked_trigger)
from tools.overworld.devtools_emote_three_proof import (
    FAULTS, EmoteThreeNegative, contract, measurements, validate_negative_result)
from tools.overworld.devtools_records import select_current_actor

ROOT = Path(__file__).resolve().parents[2]
FIELD, CONTEXT, OWNER = 0x02210000, 0x02210100, 0x02210200


def snapshot(frame, names='abcd'):
    actors=[]
    for i,name in enumerate('abcd'):
        if name not in names:continue
        handle=dict(value=65536+i,slot=i,generation=1,fieldEpoch=1,mapGeneration=1,encounterGeneration=1)
        engine={key:1 for key in ENGINE_OWNER_KEYS};engine['pointer']=0x02220000+i*256
        engine.update(manager_index=i,object_id=100+i,script_id=100+i)
        actors.append(dict(handle=handle,subjectIdentity=100+i,species=155,role='WILD',active=True,
            identityVerified=True,presentationAttached=True,engineIdentity=engine,form=0,level=50,
            motionPhase='IDLE',logical=dict(x=584+2*(i%2),y=402+3*(i//2)),
            **{key:1 for key in GENERATION_KEYS}))
    return dict(frame=frame,nativeCycle=1000+frame,fieldAvailable=True,
        context=dict(mapId=33,fieldEpoch=1,mapGeneration=1),actors=actors)


def owner(count=0, retiring=False):
    words=[CONTEXT,count,0x02211000,0x02211100,0x02211200,0x02211300 if count else 0,0]
    for i in range(3):
        words.extend([OWNER,0x02220000+i*256,0 if retiring else 0x02230000+i*256,
            0 if retiring else 0x02240000+i*256,0x02250000+i*256,0x02260000+i*256,
            0x02270000+i*256,0x10040+i*64,0x20008+i*4,3 if retiring else 2] if i<count else [0]*10)
    return decode_emote_owner(OWNER,CONTEXT,struct.pack('<37I',*words))


def native_binding(i):
    slot=owner(3)['slots'][i];words=[0]*26
    words[11:16]=[slot['pointer'],CONTEXT,OWNER,slot['object'],slot['model']]
    words[20:25]=[slot['texture'],slot['animationFile'],slot['iconFile'],(slot['textureKey']&0xFFFF)<<3,512]
    return dict(subject='abc'[i],handle=deepcopy(snapshot(10)['actors'][i]['handle']),
        effect=slot['effect'],dataPointer=0x02280000+i*256,dataHex=struct.pack('<26I',*words).hex(),
        slot=slot['pointer'],model=slot['model'],object=slot['object'],owner=OWNER,
        textureKey=slot['textureKey'],paletteKey=slot['paletteKey'],modelKeys=[slot['textureKey'],0,slot['paletteKey']],
        modelActive=3,textureDestination=words[23],paletteDestination=(slot['paletteKey']&0xFFFF)<<3,frameBytes=512)


def burst():
    subjects={n:select_current_actor(snapshot(10),a) for n,a in zip('abcd',snapshot(10)['actors'])}
    code=[dict(address=a,size=n,sha256=h,name=name) for a,n,h,name in STOCK_SEALS]
    facts=dict(known=True,acceptedProof=False,fieldPointer=FIELD,contextPointer=CONTEXT,
        codeIdentity=code,bytesRead=4096,readBudgetBytes=24576,bubble=owner(),
        texture=dict(totalFreeBytes=4096),palette=dict(totalFreeBytes=1024))
    value=dict(schema=KIND,acceptedProof=False,diagnosticOnly=True,subjects=subjects,fieldPointer=FIELD,
        baseline=deepcopy(facts),final=deepcopy(facts),activeOwner=owner(3),requests=[],events=[],updates=[],draws=[],
        codeIdentity=[dict(address=a,size=n,sha256=h,name=name) for a,n,h,name in EXTRA_SEALS],
        quietIdentity=dict(address=QUIET[0],size=QUIET[1],sha256=QUIET[2]),
        normalStart=dict(frame=10,nativeCycle=1010),end=dict(frame=250,nativeCycle=1250),closed=True,
        modelBefore=dict(resourcePointer=0x02290000,managerPointer=0x02290100,capacity=16,count=0),
        modelAfter=dict(resourcePointer=0x02290000,managerPointer=0x02290100,capacity=16,count=0))
    seq=0
    def event(kind,args,frame=10,**fields):
        nonlocal seq
        seq+=1
        e=dict(kind=kind,sequence=seq,args=args,entry=dict(frame=frame,nativeCycle=frame+1000),parent=None,**fields)
        return e
    def returned(e,result=0):
        nonlocal seq
        seq+=1;e.update(returnSequence=seq,returnClock=deepcopy(e['entry']),result=result);return e
    for request,(name,icon) in enumerate(ORDER):
        i='abcd'.index(name);obj=subjects[name]['engineIdentity']['pointer']
        admit=event('admit',[CONTEXT,obj,icon,0],request=request,subject=name,handle=deepcopy(subjects[name]['handle']))
        accepted=request in (0,2,3)
        if accepted:
            b=native_binding(i);init=event('init',[b['effect'],b['dataPointer'],0,0])
            init.update(parent='admit',request=request,binding=b,effect=b['effect'],dataPointer=b['dataPointer'])
            for typ,dest,size in ((0,b['textureDestination'],512),(1,b['paletteDestination'],32)):
                t=event('transfer',[typ,dest,0x022A0000+i*256,size]);t['parent']='init';value['events'].append(returned(t,1))
            p=event('play',[1501,0,0,0]);p['parent']='init';value['events'].append(returned(p))
            value['events'].append(returned(init,1))
        admit.update(ownerHex=owner(1 if request<2 else 2 if request==2 else 3)['rawHex'])
        returned(admit,native_binding(i)['effect'] if accepted else 0);value['requests'].append(deepcopy(admit));value['events'].append(admit)
        stop=event('stop',[1501,0,0,0],request=request);value['events'].append(returned(stop))
    for kind,table in (('update','updates'),('draw','draws')):
        for i in range(3):
            b=native_binding(i);e=event(kind,[b['effect'],b['dataPointer'],0,0],11,binding=b)
            returned(e);value[table].append(dict(count=1,first=deepcopy(e),last=deepcopy(e)))
    for i in range(3):
        b=native_binding(i);d=event('destroy',[b['effect'],b['dataPointer'],0,0],40,binding=b)
        value['events'].append(returned(d))
    for i in range(3):
        slot=owner(3)['slots'][i];words=struct.unpack_from('<10I',bytes.fromhex(owner(3,True)['rawHex']),28+i*40)
        release=event('release',[slot['pointer'],0,0,0],41,slotHex=struct.pack('<10I',*words).hex(),queue=dict(count=0))
        release['parent']='collect'
        for kind,args in (('freeTexture',[slot['textureKey'],0,0,0]),('freePalette',[slot['paletteKey'],0,0,0]),
                          ('freeSource',[slot['animationFile'],0,0,0]),('freeSource',[slot['iconFile'],0,0,0])):
            e=event(kind,args,41,slot=slot['pointer'],queue=dict(count=0));e['parent']='release';value['events'].append(returned(e))
        value['events'].append(returned(release))
    return value


def bridge(value):
    sp,address=0x023E0000,0x022D0000
    return dict(boundary='native-field-command-trampoline',preparedOnly=True,acceptedProof=False,
        firstBadCheckpoint=None,firstInvalidThreadSwitch=None,nativeHeapAdaptation=[],
        trampoline=dict(address=address,bytes=1536,heapId=11,lifetime='field-system-heap11'),
        stackOwnership=dict(callSp=sp,hostRestoredFrameBytes=0,nativeFrameBytes=80,scratchBytes=268,
            thread=dict(mode=31,irqDepth=0,stackTop=sp-1024,stackBottom=sp+1024)),
        calls=[dict(routine='emote_quiet',address=QUIET[0],requestedArguments=[value['subjects'][n]['engineIdentity']['pointer'],icon],
            entryArguments=[value['subjects'][n]['engineIdentity']['pointer'],icon],entryStack=sp,entryLink=address+0x4C,
            entryCpsr=0x3F,entryBoundary='native-trampoline-BLX-entry') for n,icon in ORDER],
        value=dict(scope='six-fixed-native-quiet-admissions',acceptedProof=False),emotes=deepcopy(value))


def raw_records():
    v=burst();rows=[dict(phase='setup',initialSnapshot=snapshot(1,''))]
    for action,op,_args in SETUP:
        if op=='bind':receipt=deepcopy(v['subjects'][_args['subject']])
        elif op=='spawn':
            i='abcd'.index(action[-1]);a=snapshot(10)['actors'][i]
            encounter=dict(personality=a['subjectIdentity'],species=155,form=0,level=50)
            position=[_args['x'],_args['z']];world=dict(snapshot(10)['context'],statePointer=0x02040000,fieldPointer=FIELD)
            common=dict(slot=i,terrain=0,statePointer=world['statePointer'],fieldPointer=FIELD,
                preparedPointer=0x02060000,worldContext=world,preparedEncounter=encounter,position=position,returnValue=1,
                preparedPrefixHex=struct.pack('<iiB3xIHBB4hBB',*position,0,a['subjectIdentity'],155,0,50,*position,*position,7,0).hex(),
                startup=dict(target=position,origin=position,locomotion=7,hopDirection=0,targetBaseY=0))
            final=dict(deepcopy(common),sequence=1,pairEligible=True,returnWorldContext=deepcopy(world))
            native=dict(common,observation='spawn-prepared',sequence=2,publicSubject=deepcopy(a),
                finalization=dict(status='matched',receipt=final))
            receipt=dict(value=dict(slot=i,species=155,personality=a['subjectIdentity']),
                events=[dict(frame=10,kind='native-observation',data=native)])
        else:receipt={}
        rows.append(dict(phase='setup',action=action,command=op,receipt=receipt,snapshot=snapshot(10)))
    arm=bridge(v);arm['emotes']['closed']=False;arm['emotes']['final']=None
    rows.append(dict(phase='observe',action=ACTIONS[0][0],command=ACTIONS[0][1],receipt=arm,snapshot=snapshot(10)))
    rows.append(dict(phase='observe',action=ACTIONS[1][0],samples=[snapshot(f) for f in range(11,251)],
        completedGameFrames=240,observedFieldFrames=240,nativeCycles=240,events=[],
        cycleIntervals=[dict(completedGameFrame=f,cpuNs=1,wallNs=1) for f in range(11,251)]))
    rows.append(dict(phase='observe',action=ACTIONS[2][0],command=ACTIONS[2][1],receipt=dict(emotes=v),snapshot=snapshot(250)))
    return rows


def replay(rows):
    recipe=json.loads((ROOT/'tests/overworld/test-recipes/presentation.emote-three-slots.json').read_text())
    meter=EmoteThreeMeasurement(recipe)
    for row in rows:meter.observe_record(row)
    return meter.finish()


class EmoteThreeTests(unittest.TestCase):
    def test_all_three_actual_model_bindings_and_normal_cleanup(self):
        v=burst();self.assertEqual(checked_burst(v,v['subjects']),240)
        checked_trigger(bridge(v),v['subjects'])
        result=replay(raw_records());self.assertTrue(result['passed'],result)
        proof=measurements(dict(passed=True,failures=[],observedFrames=240,measurements={KIND:result}),
            dict(sessionId='host-fixture',sessionCleanup=dict(sessionId='host-fixture',closed=True,errors=[])))
        self.assertEqual(len(proof),3);self.assertEqual(len(contract()),3)

    def test_all_six_same_cycle_callbacks_use_exact_nesting_sequence(self):
        v=burst()
        self.assertEqual({(e['entry']['frame'],e['entry']['nativeCycle']) for e in v['events'] if e['kind']=='init'}, {(10,1010)})
        self.assertEqual(checked_burst(v,v['subjects']),240)
        bad=deepcopy(v);next(e for e in bad['events'] if e['kind']=='play')['sequence']=999999
        with self.assertRaisesRegex(ValueError,'sequence|nested'):checked_burst(bad,bad['subjects'])

    def test_every_copied_controller_fault_rejects(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                mutator=EmoteThreeNegative(fault);rows=[mutator.mutate(r,{}) for r in raw_records()]
                result=replay(rows);self.assertTrue(mutator.applied)
                self.assertFalse(result['passed'],fault)
                validate_negative_result(dict(passed=False,failures=result['failures']),fault)

    def test_missing_wrong_order_frames_identity_and_cleanup_reject(self):
        mutations=(lambda r:r.pop(-1),lambda r:r[1].update(action='other'),
            lambda r:r[-2]['samples'][15].update(frame=999),
            lambda r:r[-2]['samples'][12]['actors'][0]['engineIdentity'].update(pointer=0x02290000),
            lambda r:r[-1]['receipt']['emotes']['events'].append(deepcopy(next(e for e in r[-1]['receipt']['emotes']['events'] if e['kind']=='freeTexture'))),
            lambda r:next(e for e in r[-1]['receipt']['emotes']['events'] if e['kind']=='transfer')['args'].__setitem__(1,999))
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                rows=raw_records();mutate(rows);result=replay(rows);self.assertFalse(result['passed'],result)

    def test_exact_actual_reader_binding_rejects_bad_native_bytes(self):
        from tools.overworld.test_devtools_emote_vram_diagnostics import NativeBytes
        s=NativeBytes([]);probe=EmoteThreeProbe.__new__(EmoteThreeProbe)
        probe.s=s;probe.owner=OWNER;probe.context=CONTEXT;probe.reads=0
        v=burst();probe.subjects=v['subjects'];probe.objects={n:a['engineIdentity']['pointer'] for n,a in probe.subjects.items()}
        s.write(OWNER,bytes.fromhex(v['activeOwner']['rawHex']))
        b=native_binding(0);s.write(b['dataPointer'],bytes.fromhex(b['dataHex']))
        s.write_words(b['model']+0x94,*b['modelKeys']);s.write_words(b['model']+0xB4,3)
        self.assertEqual(probe.binding(b['effect'],b['dataPointer']),b)
        for at,word in ((b['model']+0x94,123),(b['dataPointer']+92,999),(b['slot'],OWNER+4),(b['dataPointer']+44,OWNER+29)):
            with self.subTest(address=at):
                old=s.read(at,4);s.write_words(at,word);probe.reads=0
                with self.assertRaises(ValueError):probe.binding(b['effect'],b['dataPointer'])
                s.write(at,old)

    def test_foreign_slot_reuse_and_global_ambient_work_do_not_change_owned_cleanup(self):
        v=burst();original=next(e for e in v['events'] if e['kind']=='release')
        foreign=deepcopy(original)
        words=list(struct.unpack('<10I',bytes.fromhex(foreign['slotHex'])))
        words[1]=0x02221000  # Different object, same reusable keys/assets/slot.
        foreign.update(sequence=1000,returnSequence=1010,
            entry=dict(frame=80,nativeCycle=1080),returnClock=dict(frame=80,nativeCycle=1080),
            slotHex=struct.pack('<10I',*words).hex())
        children=[deepcopy(e) for e in v['events'] if e['kind'] in ('freeTexture','freePalette','freeSource')
                  and original['sequence']<e['sequence']<e['returnSequence']<original['returnSequence']]
        for index,e in enumerate(children):
            e.update(sequence=1001+index*2,returnSequence=1002+index*2,
                entry=dict(frame=80,nativeCycle=1080),returnClock=dict(frame=80,nativeCycle=1080))
        v['events'].extend(children+[foreign])
        raw=bytearray.fromhex(owner(1)['rawHex'])
        struct.pack_into('<I',raw,32,words[1])
        v['final']['bubble']=decode_emote_owner(OWNER,CONTEXT,bytes(raw))
        v['modelAfter']['count']=3
        v['final']['texture']['totalFreeBytes']-=2048
        v['final']['palette']['totalFreeBytes']-=64
        self.assertEqual(checked_burst(v,v['subjects']),240)
        own_duplicate=deepcopy(next(e for e in v['events'] if e['kind']=='freeTexture'))
        v['events'].append(own_duplicate)
        with self.assertRaisesRegex(ValueError,'cleanup'):checked_burst(v,v['subjects'])

    def test_owned_model_assets_and_manager_identity_remain_strict(self):
        for fault in ('model-live','wrong-key','wrong-source','wrong-manager','missing-free'):
            v=burst()
            release=next(e for e in v['events'] if e['kind']=='release')
            if fault=='model-live':
                raw=bytearray.fromhex(release['slotHex']);struct.pack_into('<I',raw,12,owner(3)['slots'][0]['model']);release['slotHex']=raw.hex()
            elif fault=='wrong-key':next(e for e in v['events'] if e['kind']=='freeTexture')['args'][0]^=8
            elif fault=='wrong-source':next(e for e in v['events'] if e['kind']=='freeSource')['args'][0]^=4
            elif fault=='wrong-manager':v['modelAfter']['managerPointer']+=4
            else:v['events'].remove(next(e for e in v['events'] if e['kind']=='freePalette'))
            with self.subTest(fault=fault),self.assertRaises(ValueError):checked_burst(v,v['subjects'])

    def test_actual_reader_rejects_wrong_owner_and_keeps_original_object_incarnation(self):
        from tools.overworld.test_devtools_emote_vram_diagnostics import NativeBytes
        s=NativeBytes([]);probe=EmoteThreeProbe.__new__(EmoteThreeProbe)
        probe.s=s;probe.owner=OWNER;probe.reads=0
        binding=native_binding(0);probe.owned_slots={binding['slot']:binding}
        raw=bytearray.fromhex(next(e['slotHex'] for e in burst()['events'] if e['kind']=='release'))
        s.write(binding['slot'],bytes(raw))
        self.assertEqual(probe.owned_release_slot(binding['slot']),bytes(raw))
        struct.pack_into('<I',raw,4,0x02221000);s.write(binding['slot'],bytes(raw));probe.reads=0
        self.assertIsNone(probe.owned_release_slot(binding['slot']))
        struct.pack_into('<I',raw,0,OWNER+4);s.write(binding['slot'],bytes(raw));probe.reads=0
        with self.assertRaisesRegex(ValueError,'owner/state'):probe.owned_release_slot(binding['slot'])

    def test_existing_evaluator_uses_exact_native_spawn_and_dense_frames(self):
        from tools.overworld.devtools_test_contract import TestEvaluator
        recipe=json.loads((ROOT/'tests/overworld/test-recipes/presentation.emote-three-slots.json').read_text())
        evaluator=TestEvaluator(recipe);evaluator.install_measurements({KIND:dict(contractVersion=1)})
        samples=[]
        for row in raw_records():
            result=evaluator.observe_record(row,frame_callback=lambda s,e:samples.append((s['frame'],e.frames)))
            self.assertFalse(result['failures'],result)
        result=evaluator.finish();self.assertTrue(result['passed'],result)
        self.assertEqual(result['observedFrames'],240)
        self.assertEqual(samples,[(f,f-10) for f in range(11,251)])
        for mutate in (lambda rows:rows[2]['receipt']['value'].update(personality=999),
                       lambda rows:rows[2]['receipt']['events'][0]['data']['finalization']['receipt'].update(returnValue=0)):
            rows=raw_records();mutate(rows);e=TestEvaluator(recipe);e.install_measurements({KIND:dict(contractVersion=1)})
            for row in rows:e.observe_record(row)
            self.assertFalse(e.finish()['passed'])

    def test_authored_fixed_contract_and_registration(self):
        from tools.overworld.devtools_test_contract import validate_test
        from tools.overworld.devtools_contract import validate_command
        self.assertEqual(validate_command('emote-three.arm',dict(a=1,b=2,c=3,d=4)),dict(a=1,b=2,c=3,d=4))
        for bad in (dict(a=1,b=2,c=3),dict(a=1,b=2,c=3,d=4,address=QUIET[0]),dict(a=1,b=2,c=3,d=True)):
            with self.assertRaises(ValueError):validate_command('emote-three.arm',bad)
        from tools.overworld.validation import validate_feature_manifest,validate_scenario
        p=ROOT/'tests/overworld/test-recipes/presentation.emote-three-slots.json';recipe=json.loads(p.read_text())
        self.assertEqual(validate_test(recipe)['measurements'],[dict(kind=KIND,subject='a')])
        for mutate in (lambda r:r['setup'][1]['args'].update(species=16),lambda r:r['actions'][0]['args'].update(a='b'),
                       lambda r:r['actions'][1]['args'].update(frames=239),lambda r:r['measurements'][0].update(subject='b')):
            bad=deepcopy(recipe);mutate(bad)
            with self.assertRaises(ValueError):validate_test(bad)
        scenario_path=ROOT/'tests/overworld/scenarios/presentation.emote-three-slots.json'
        validate_scenario(json.loads(scenario_path.read_text()),scenario_path)
        feature_path=ROOT/'tools/overworld/system_features.yaml'
        validate_feature_manifest(json.loads(feature_path.read_text()),feature_path)
        registry=json.loads((ROOT/'tools/overworld/runtime_proof_registry.json').read_text())
        self.assertEqual(registry['sharedTests']['presentation.emote-three-slots']['measurementContract'],contract())


if __name__=='__main__':unittest.main()
