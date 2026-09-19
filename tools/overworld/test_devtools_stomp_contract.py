"""Synthetic host controls; no fixture here is accepted native game proof."""
from copy import deepcopy
from pathlib import Path
import json
import struct
import unittest

from tools.overworld.devtools_stomp_contract import CASES, RULES, contract, validate_stomp, validate_feedback
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_mount_pacing_observer import ENGINE
from tools.overworld.test_devtools_test_contract import snapshot


def fixture():
    initial=snapshot(100);actor=initial['actors'][0]
    actor.update(species=155,role='MOUNTED',inputOwnership=1,motionKind='NONE',reservationId=0,
        movementPolicy=dict(pending=0),logical=dict(x=10,y=20),sourceIdentity=dict(object=0x02210000),
        engineIdentity=dict(pointer=0x02210000,anchorPointer=0x02220000,anchorInCurrentManager=True,
            current_manager=0x02270000,object_manager=0x02270000,manager_index=12,object_id=231,
            object_map_id=33,script_id=2074,in_manager=True,active=True))
    player={prefix+axis:0 for prefix in ('pos_','face_','unk88_','unk94_') for axis in 'xyz'}
    player.update(pos_x=100000,pos_z=200000,face_x=-32768,face_y=32768,facing=3)
    mount=dict(player,face_x=0,face_y=0)
    initial.update(player=player,actorFrame=200,nativeCycle=1000)
    actor['engineObject']=mount
    subject=select_current_actor(initial,actor)
    cases=[]
    for case in CASES:
        duration=case['duration'];end=deepcopy(initial)
        end.update(frame=initial['frame']+duration+1,actorFrame=initial['actorFrame']+duration+1,
            nativeCycle=initial['nativeCycle']+(duration+1)*10)
        end['actors'][0]['commitSequence']+=1;end['actors'][0]['logical']['x']+=1
        end['player']['pos_x']+=65536;end['actors'][0]['engineObject']['pos_x']+=65536
        poses=[]
        for i in range(1,duration+2):
            pose=deepcopy(end if i==duration+1 else initial)
            pose.update(frame=initial['frame']+i,actorFrame=initial['actorFrame']+i,nativeCycle=initial['nativeCycle']+i*10)
            poses.append(pose)
        events=[dict(event=name,reason='OK',valueA=1,valueB=1,subject=subject,sequence=case['index']*4+i+1,
            frame=initial['frame']+1 if i==0 else end['frame'],
            actorFrame=initial['actorFrame']+1 if i==0 else end['actorFrame'])
            for i,name in enumerate(('MOTION_STARTED','LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED'))]
        current=dict(subject=subject,publicSubject=deepcopy(actor),sourceIdentity=actor['sourceIdentity'],
            engineIdentity={k:actor['engineIdentity'][k] for k in ENGINE},
            worldContext=dict(initial['context'],fieldPointer=0x02280000,statePointer=0x02380000),mountPointer=0x02210000,
            playerPointer=0x02220000,avatarPointer=0x02230000)
        clock=dict(actorFrame=end['actorFrame'],nativeCycle=end['nativeCycle']-1)
        common=dict(before=current,entryClock=clock,returnClock=clock,completedFrame=end['frame']-1,
            caller=0x02300001,args=[0,0,0,0],normalReturn=True,returnValue=0)
        profile=bytearray(72);profile[7]=duration;profile[70]=2
        raw=bytearray(28);struct.pack_into('<HH',raw,0,1,28)
        raw[9]=3;raw[16]=1;raw[19]=0;raw[21]=int(case['index']==0)
        feedback={k:[] for k in ('dust','allocate','init','sound','soundStart')}
        if case['index']==0:
            context=bytearray(16);struct.pack_into('<I',context,12,0x02210000)
            data=bytearray(36);struct.pack_into('<II',data,28,0x02210000,0x02250000)
            feedback['dust']=[dict(deepcopy(common),kind='dust',args=[0x02210000,0,0,0])]
            feedback['allocate']=[dict(deepcopy(common),kind='allocate',returnValue=0x02240000,
                contextHex=context.hex(),positionHex='00'*12)]
            feedback['init']=[dict(deepcopy(common),kind='init',args=[0x02240000,0,0,0],returnValue=1,
                effectDataHex=data.hex(),renderPointer=0x02250000)]
            feedback['sound']=[dict(deepcopy(common),kind='sound',args=[2183,0,0,0])]
            feedback['soundStart']=[dict(deepcopy(common),kind='soundStart',soundId=2183,returnValue=1)]
        policy=dict(deepcopy(common),kind='policy',args=[0x02230000,0x02210000,0x02260000,0],
            policyHex=raw.hex(),profileHex=profile.hex(),stompTime=2,effect=raw[21],objectPointer=0x02210000,feedback=feedback)
        input_policy=deepcopy(policy);input_raw=bytearray(raw)
        input_raw[9]=2;input_raw[16]=1;input_raw[17]=3;input_raw[19]=duration;input_raw[21]=0
        input_policy.update(policyHex=input_raw.hex(),effect=0,feedback={k:[] for k in feedback})
        input_policy.update(completedFrame=initial['frame'],entryClock=dict(actorFrame=initial['actorFrame']+1,nativeCycle=initial['nativeCycle']+1),
            returnClock=dict(actorFrame=initial['actorFrame']+1,nativeCycle=initial['nativeCycle']+1))
        policies=[]
        for number,operation in enumerate((1,2,3)):
            outer=input_policy if operation!=3 else policy
            response=bytearray.fromhex(outer['policyHex']);response[9]=operation
            if operation==1:response[10]=3;response[16]=2
            request=bytearray(response);request[16:]=bytes(12)
            public=dict(actor,status='observed-public-subject')
            policies.append(dict(observation='walk-policy',sequence=case['index']*3+number+1,slot=subject['handle']['slot'],operation=operation,
                requestHex=request.hex(),responseHex=response.hex(),publicSubject=public,publicSubjectAfter=deepcopy(public),returnValue=1,
                laneHex=profile.hex(),frame=outer['completedFrame']+1,entryActorFrame=outer['entryClock']['actorFrame'],
                returnActorFrame=outer['returnClock']['actorFrame'],entryNativeCycle=outer['entryClock']['nativeCycle'],returnNativeCycle=outer['returnClock']['nativeCycle']))
        cases.append(dict(case=deepcopy(case),subject=subject,reservation=case['index']+1,events=events,policies=policies,
            initial=deepcopy(initial),terminal=end,input=dict(keys=['RIGHT'],requestedGameFrames=1,completedGameFrames=1,observedFieldFrames=1),
            steps=[dict(subject=subject,playerPointer=0x02220000,normalReturn=True,eventConsumed=0,
                frame=end['frame']-1,actorFrame=end['actorFrame'],nativeCycle=end['nativeCycle']-1)],poses=poses,
            feedback=dict(complete=True,startFrame=initial['frame'],endFrame=end['frame'],
                counts=dict(policy=2,**{k:len(v) for k,v in feedback.items()}),calls=[input_policy,policy])))
        initial=deepcopy(end)
    for case in cases:
        for s in [case['initial'],*case['poses']]:
            a=s['actors'][0]
            s['stompFeedback']=dict(latestCompletedPose=dict(subject=subject,publicSubject=deepcopy(a),
                sourceIdentity=a['sourceIdentity'],engineIdentity={k:a['engineIdentity'][k] for k in ENGINE},
                worldContext=dict(s['context'],fieldPointer=0x02280000,statePointer=0x02380000),
                playerPointer=0x02220000,mountPointer=0x02210000,avatarPointer=0x02230000,
                player=deepcopy(s['player']),mount=deepcopy(a['engineObject']),boundary='main-task-queue-completion',
                frame=s['frame'],actorFrame=s['actorFrame'],nativeCycle=s['nativeCycle']))
            for obj in (s['player'],a['engineObject']):
                del obj['unk88_z'];del obj['unk94_z']
        case['terminal']=case['poses'][-1]
    return cases,subject,cases[-1]['terminal']


class StompContractTests(unittest.TestCase):
    def test_all_six_original_registry_rows_unchanged(self):
        registry=json.loads((Path(__file__).resolve().parents[2]/'tools/overworld/runtime_proof_registry.json').read_text())
        self.assertEqual(contract(),registry['measurementContracts']['legacy.stomp'])
        cases,subject,terminal=fixture();result=validate_stomp(cases,subject,terminal)
        self.assertEqual(result['actuals'],[deepcopy(row[2]) for row in RULES])
        self.assertFalse(result['acceptedProof'])

    def test_copied_required_fact_faults(self):
        for fault in ('absent','identity','threshold','duration','travel-time','lifecycle','commit','input','step','pose','pose-gap',
            'coverage','count','negative-feedback','dust','allocation','init','sound','start','owner','clock','terminal',
            'native-engine','native-epoch','native-field','native-public','anchor'):
            cases,subject,terminal=fixture();c=cases[0];call=c['feedback']['calls'][-1]
            if fault=='absent':c['initial']['actors']=[]
            elif fault=='identity':c['initial']['actors'][0]['presentationAttached']=False
            elif fault=='threshold':c['case']['threshold']=3
            elif fault=='duration':c['case']['duration']=3
            elif fault=='travel-time':
                call=c['feedback']['calls'][0]
                raw=bytearray.fromhex(call['policyHex']);raw[19]=9;call['policyHex']=raw.hex()
            elif fault=='lifecycle':c['events'].pop()
            elif fault=='commit':c['terminal']['actors'][0]['commitSequence']+=1
            elif fault=='input':c['input']['completedGameFrames']=2
            elif fault=='step':c['steps'].append(deepcopy(c['steps'][0]))
            elif fault=='pose':c['poses'][0]['player']['pos_x']+=1
            elif fault=='pose-gap':c['poses'].pop(0)
            elif fault=='coverage':c['feedback']['complete']=False
            elif fault=='count':c['feedback']['counts']['policy']=0
            elif fault=='negative-feedback':cases[1]['feedback']['calls'].append(deepcopy(call))
            elif fault=='dust':call['feedback']['dust']=[]
            elif fault=='allocation':call['feedback']['allocate'][0]['returnValue']=0
            elif fault=='init':call['feedback']['init'][0]['returnValue']=0
            elif fault=='sound':call['feedback']['sound'][0]['args'][0]=1
            elif fault=='start':call['feedback']['soundStart'][0]['returnValue']=0
            elif fault=='owner':call['objectPointer']+=4
            elif fault=='clock':call['returnClock']['nativeCycle']=999999
            elif fault=='native-engine':call['before']['engineIdentity']['object_id']+=1
            elif fault=='native-epoch':call['before']['worldContext']['fieldEpoch']+=1
            elif fault=='native-field':call['before']['worldContext']['fieldPointer']+=4
            elif fault=='native-public':call['before']['publicSubject']['authorityGeneration']+=1
            elif fault=='anchor':call['before']['playerPointer']+=4
            else:terminal['actors'][0]['movementPolicy']['pending']=1
            with self.subTest(fault=fault),self.assertRaises((ValueError,KeyError)):
                validate_stomp(cases,subject,terminal)

    def test_sound_id_is_anchored_in_actual_public_header(self):
        header=(Path(__file__).resolve().parents[2]/'include/constants/sndseq.h').read_text()
        self.assertRegex(header,r'#define\s+SEQ_SE_GS_IWAOTOSHI02\s+2183\b')

    def test_fixture_keeps_native_projection_separate_from_public_binding(self):
        cases,subject,terminal=fixture()
        current=cases[0]['feedback']['calls'][0]['before']
        self.assertEqual(set(current['engineIdentity']),set(ENGINE))
        self.assertNotIn('anchorPointer',current['engineIdentity'])
        self.assertEqual(current['playerPointer'],subject['engineIdentity']['anchorPointer'])
        self.assertEqual(set(current['worldContext'])-set(cases[0]['initial']['context']),
            {'fieldPointer','statePointer'})
        validate_stomp(cases,subject,terminal)

    def test_sparse_queue_pose_still_checks_every_native_component(self):
        for fault in ('changed-z','missing-z','unknown-native-field'):
            cases,subject,terminal=fixture()
            pose=cases[0]['poses'][0]
            self.assertNotIn('unk88_z',pose['player'])
            player=pose['stompFeedback']['latestCompletedPose']['player']
            if fault=='changed-z':player['unk88_z']+=1
            elif fault=='missing-z':del player['unk88_z']
            else:player['unknown']=0
            with self.subTest(fault=fault),self.assertRaises(ValueError):validate_stomp(cases,subject,terminal)

    def test_retained_commits_validate_native_shape_but_cannot_supply_missing_input(self):
        root=Path(__file__).resolve().parents[2]/'build/overworld-devtools/session-a8jhx9sl'
        files=('event-details-db17be4c30b7.json','event-details-cdbf0b8c9eaf.json')
        if not all((root/name).exists() for name in files):self.skipTest('optional native Stomp pilot receipts absent')
        for index,name in enumerate(files):
            value=json.loads((root/name).read_text())
            call=value if index==0 else value['receipt']['calibration']['policyReceipt']
            raw=bytes.fromhex(call['policyHex'])
            self.assertEqual((raw[9],raw[16],raw[19],raw[21]),(3,1,0,1-index))
            before=call['before'];subject=before['subject']
            actor=dict(before['publicSubject'],sourceIdentity=before['sourceIdentity'])
            start=dict(frame=call['completedFrame'],actorFrame=call['entryClock']['actorFrame'],
                nativeCycle=call['entryClock']['nativeCycle'],actors=[actor],
                context={k:before['worldContext'][k] for k in ('fieldEpoch','mapGeneration','mapId')})
            end=dict(frame=call['completedFrame']+1,actorFrame=call['returnClock']['actorFrame'],
                nativeCycle=call['returnClock']['nativeCycle'])
            case=dict(case=CASES[index],subject=subject,initial=start,terminal=end)
            counts=dict(policy=1,**{k:len(v) for k,v in call['feedback'].items()})
            window=dict(complete=True,startFrame=start['frame'],endFrame=end['frame'],counts=counts,calls=[call])
            # These real unchanged COMMIT receipts have valid native sinks,
            # but this partial pilot did not retain START_RESULT or INPUT.
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,'native START_RESULT count differs'):
                validate_feedback(window,case,subject['engineIdentity'])


if __name__=='__main__':unittest.main()
