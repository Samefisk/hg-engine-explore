"""Copied native-shape priority checks; these do not grant game acceptance."""
from copy import deepcopy
import json,struct,unittest
from pathlib import Path
import sys
if __package__ in (None, ''):sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from unittest.mock import patch
from tools.overworld.devtools_follower_query_priority_measurement import (
    ACTIONS,CASE,KIND,REQUIREMENT,SETUP,SUBJECTS,FollowerQueryPriorityMeasurement,validate_recipe,
)
from tools.overworld.devtools_follower_query_priority_proof import (
    FAULTS,FollowerQueryPriorityNegative,contract,validate_negative_result,
)
from tools.overworld.devtools_follower_throw_measurement import (
    APPLICATION,FIND_CARGO,FOLLOWER,TRIGGER_CONDITION,CARGO_CONDITION,raw_handle,
)
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.test_devtools_damage_follower_measurement import sample as shared_sample,binding,native,motion
from tools.overworld.test_devtools_follower_throw_measurement import SOURCE,profile
from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor
from tools.overworld.test_devtools_cargo_route_continuity import query_event
ROOT=Path(__file__).resolve().parents[2]


def sample(frame=20):
    s=shared_sample(frame);m,src=s['actors'];src['species']=74
    old=actor(74,0,900,407)
    for key in ('logical','render','origin','target'):old[key]=dict(x=595,y=407)
    old['engineObject'].update(x=595,y=407,pos_x=(595<<16)+32768,pos_z=(407<<16)+32768,pos_y=65536,unk88_y=0)
    s['actors'].append(old);s['selector']=dict(rawHeld=0)
    row=s['pokemonCombat']['interactions']['carriers'][0]
    row['bindings']=dict(trigger=binding(None,0),cargo=binding(None,0))
    row['rawBindingsHex']=(raw_handle(m['handle'])+bytes(48)).hex()
    b=binding(m,TRIGGER_CONDITION);empty=binding(None,0)
    s['pokemonCombat']['interactions']['carriers'].append(dict(
        available=True,role='WILD',handle=deepcopy(old['handle']),slot=old['handle']['slot'],
        bindings=dict(trigger=b,cargo=empty),rawBindingsHex=(raw_handle(old['handle'])+bytes.fromhex(b['rawHex'])+bytes(24)).hex()))
    return s


def meter(s=None):
    s=s or sample();value=FollowerQueryPriorityMeasurement(SOURCE)
    value.latest=sample(s['frame']-1);value.context=deepcopy(s['context']);value.field=s['fieldControl']['fieldPointer']
    value.subjects={n:select_current_actor(s,a) for n,a in zip(('mankey','source','old-geodude'),s['actors'])}
    value._party_health(value.latest,value._actor(value.latest,'mankey'),initial=True)
    return value


def busy(value,s):
    old=s['actors'][2];e=query_event(s,old,SOURCE['queryImage'],nodes=1)
    for key in ('before','after'):e['data'][key]['workspace']['compatibility']['required']=0
    value._remember_busy(s,[e]);return e


def handoff(value,s,*,same_frame=False):
    e=query_event(s,s['actors'][0],SOURCE['queryImage'],nodes=1)
    e['data']['before']=deepcopy(value.busy_owner['query'])
    e['data']['before']=dict(subject=s['actors'][0]['handle'],worldSubject=s['actors'][0]['handle'],
        frameValid=True,worldFrame=s['actorFrame'],queryPointer=value.busy_owner['query']['queryPointer'],
        workspace=deepcopy(value.busy_owner['query']['workspace']))
    if same_frame:
        e['data']['before']['workspace']['stateFrame']=s['actorFrame']
        e['data']['after']['workspace']['stateSubject']=None
    return e


def sight(s,cargo=False):
    m,src=s['actors'][:2];r=s['pokemonCombat']['interactions']['carriers'][0]
    r['bindings']=dict(trigger=binding(src,TRIGGER_CONDITION),cargo=binding(src if cargo else None,CARGO_CONDITION))
    r['rawBindingsHex']=(raw_handle(m['handle'])+bytes.fromhex(r['bindings']['trigger']['rawHex'])+bytes.fromhex(r['bindings']['cargo']['rawHex'])).hex()
    return r


def rejected(error,fault):
    validate_negative_result(dict(passed=False,failures=[str(error)],measurements={KIND:dict(failures=[str(error)])}),fault)


class FollowerPriorityTests(unittest.TestCase):
    def test_recipe_registration_and_unchanged_save_setup(self):
        from tools.overworld.devtools_test_contract import validate_test,TestEvaluator
        from tools.overworld.proof_adapters import ADAPTERS
        p=ROOT/'tests/overworld/test-recipes'/f'{CASE}.json';r=json.loads(p.read_text())
        validate_recipe(r);validate_test(r);e=TestEvaluator(r);e.install_measurements({KIND:SOURCE})
        self.assertIsInstance(e.measurements[KIND],FollowerQueryPriorityMeasurement)
        self.assertEqual(ADAPTERS[KIND].recipe_subjects(),r['subjects'])
        self.assertEqual(ADAPTERS[KIND].contract(),contract())
        for fault in ('party-write','y','different-cargo','longer-step'):
            bad=deepcopy(r)
            if fault=='party-write':bad['setup'].insert(1,dict(id='party',op='party',args=dict(slot=0,species=56,level=20)))
            elif fault=='y':next(r for r in bad['setup'] if r['id']=='first-natural-throw')['args']['keys']=['Y']
            elif fault=='different-cargo':next(r for r in bad['setup'] if r['id']=='spawn-source')['args']['species']=69
            else:bad['actions'][0]['args']['frames']+=1
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'unchanged Continue'):validate_recipe(bad)

    def test_full_current_old_owner_and_same_frame_handoff_keep_native_budget(self):
        s=sample();v=meter(s);busy(v,s);self.assertIsNotNone(v.busy_owner)
        current=sample(21);e=handoff(v,current,same_frame=True)
        self.assertEqual(v._queries(current,[e],current['actors'][0]),[])
        self.assertEqual(v.handoff['before']['workspace']['owner'],s['actors'][2]['handle'])
        self.assertEqual(v.handoff['after']['workspace']['owner'],current['actors'][0]['handle'])
        for fault in ('changed-storage','stale-old','double-native-work','claimed-old'):
            s=sample();v=meter(s);busy(v,s);current=sample(21);e=handoff(v,current,same_frame=True)
            if fault=='changed-storage':e['data']['after']['workspace']['storage']+=4
            elif fault=='stale-old':e['data']['before']['workspace']['owner']['generation']+=1
            elif fault=='double-native-work':
                raw=bytearray.fromhex(e['data']['resultHex']);raw[127]=1;e['data']['resultHex']=raw.hex()
            else:
                state=current['pokemonCombat']['interactions']['throwState'];state['carrierMask']|=1
                raw=bytearray.fromhex(state['rawHex']);struct.pack_into('<H',raw,12,state['carrierMask']);state['rawHex']=raw.hex()
            with self.subTest(fault=fault),self.assertRaises(ValueError):v._queries(current,[e],current['actors'][0])

    def test_logical_arrival_before_flight_return_does_not_grant_busy_owner(self):
        s=sample();v=meter(s);s['actors'][2]['motionPhase']='ACTIVE'
        busy(v,s);self.assertIsNone(v.busy_owner)
        s['actors'][2]['motionPhase']='IDLE';s['actors'][2]['reservationId']=12
        busy(v,s);self.assertIsNone(v.busy_owner)
        s['actors'][2]['reservationId']=0
        busy(v,s);self.assertIsNotNone(v.busy_owner)

    def test_source_ready_requires_idle_cone_pose_and_current_busy_owner(self):
        s=sample();v=meter(s);m=s['actors'][0]
        m['logical']=dict(x=587,y=406);m['engineObject']['facing']=0
        busy(v,s);v.latest=deepcopy(s)
        self.assertTrue(v.stage('source-ready'))
        for fault in ('motion','facing','cone','old-frame'):
            v.latest=deepcopy(s)
            if fault=='motion':v.latest['actors'][0]['motionPhase']='ACTIVE'
            elif fault=='facing':v.latest['actors'][0]['engineObject']['facing']=2
            elif fault=='cone':v.latest['actors'][0]['logical']['x']=596
            else:v.latest['frame']+=1
            with self.subTest(fault=fault):self.assertFalse(v.stage('source-ready'))

    def test_old_pending_owner_fault_rejects_and_exact_sight_target_is_required(self):
        s=sample();v=meter(s);busy(v,s);current=sample(21);r=sight(current)
        v._binding(current,r,current['actors'][1]);e=handoff(v,current)
        v._queries(current,[e],current['actors'][0]);self.assertIsNotNone(v.handoff)
        for fault in FAULTS[:2]:
            s=sample();v=meter(s);busy(v,s);current=sample(21);r=sight(current)
            v._binding(current,r,current['actors'][1]);v.binding['frame']=20
            row=dict(phase='observe',action=ACTIONS[0][0],samples=[current],events=[handoff(v,current)])
            negative=FollowerQueryPriorityNegative(fault);bad=negative.mutate(row,v.subjects);self.assertTrue(negative.applied)
            with self.subTest(fault=fault),self.assertRaises(ValueError) as error:
                if fault.endswith('wrong-target'):v._binding(bad['samples'][0],bad['samples'][0]['pokemonCombat']['interactions']['carriers'][0],bad['samples'][0]['actors'][1])
                else:v._queries(current,bad['events'],current['actors'][0])
            rejected(error.exception,fault)

    def test_lost_claim_fault_hits_the_pickup_claim_guard(self):
        s=sample();v=meter(s);busy(v,s);current=sample(21);m,src=current['actors'][:2]
        v.latest=deepcopy(s)
        r=sight(current,True);v.binding=dict(frame=1);v.frames['notice']=1;v.handoff={};v.admission={}
        m.update(matchedLayerMask=FOLLOWER|FIND_CARGO,behaviorFingerprint=1001)
        resolved=profile(m['matchedLayerMask'],m['behaviorFingerprint']);v.profiles[1001]=resolved
        state=current['pokemonCombat']['interactions']['throwState'];state['targets'][7]=src['handle']['slot']+1
        state.update(carrierMask=128,targetMask=1<<src['handle']['slot'])
        state['rawHex']=(bytes(state['targets'])+struct.pack('<3H',state['targetMask'],128,0)).hex()
        r['throw'].update(targetRaw=src['handle']['slot']+1,targetSlot=src['handle']['slot'],carrier=True)
        current['pokemonCombat']['movementTimers']=[dict(handle=m['handle'],movementEmoteTimer=0)]
        hp=deepcopy(next(r for r in current['pokemonCombat']['targets'] if r['handle']==m['handle']))
        motion(current,m,phase='IDLE');motion(current,src,phase='IDLE')
        next(r for r in current['pokemonCombat']['targets'] if r['handle']==m['handle']).update(
            {k:v for k,v in hp.items() if k!='motion'})
        negative=FollowerQueryPriorityNegative(FAULTS[2]);bad=negative.mutate(dict(phase='observe',action=ACTIONS[0][0],samples=[current],events=[]),v.subjects)
        v.action_frames[0]=1
        with patch.object(v,'_queries',return_value=[]),self.assertRaises(ValueError) as error:v._sample(bad['samples'][0],[],ACTIONS[0][0])
        self.assertTrue(negative.applied);rejected(error.exception,FAULTS[2])

    def test_flight_requires_commit_finish_control_and_exact_authored_hop_pause(self):
        s=sample();v=meter(s);src=s['actors'][1];mo=motion(s,src)
        w=v._start(s,src,mo,v._native(s,[native(src,20,'MOTION_STARTED',2,8,10)],src))
        w['moved']=True;current=sample(21);a=current['actors'][1];mo=motion(current,a,phase='IDLE',elapsed=8,commit=5)
        r=current['pokemonCombat']['interactions']['carriers'][0];r['throw']['recovering']=True
        events=[native(a,21,name,A,B,seq) for seq,name,A,B in (
            (11,'LOGICAL_COMMIT',5,2),(12,'MOTION_FINISHED',5,2),(13,'CONTROL_RETURNED',0,5))]
        v._advance(current,a,mo,v._native(current,events,a),deepcopy(w))
        fault=FAULTS[3];negative=FollowerQueryPriorityNegative(fault)
        bad=negative.mutate(dict(phase='observe',action=ACTIONS[0][0],samples=[current],events=events),v.subjects)
        with self.assertRaises(ValueError) as error:v._advance(current,a,mo,v._native(current,bad['events'],a),deepcopy(w))
        self.assertTrue(negative.applied);rejected(error.exception,fault)
        lane=bytes.fromhex(profile(FOLLOWER|FIND_CARGO,1001)['lanes'][0])
        move=dict(plan=dict(kind=2,origin=[0,0],target=[1,0],startBaseY=0,targetBaseY=0,duration=3,pauseFrames=5))
        v._hop_speed(move,lane,3)
        for field in ('duration','pauseFrames'):
            bad=deepcopy(move);bad['plan'][field]+=1
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'authored speed or pause'):v._hop_speed(bad,lane,3)


if __name__=='__main__':unittest.main()
