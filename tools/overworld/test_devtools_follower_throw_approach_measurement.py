"""Finite native-shape approach controls. Synthetic data is never game proof."""
from copy import deepcopy
import json,sys,unittest
from pathlib import Path
if __package__ in (None,""):sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.overworld.devtools_follower_throw_approach_measurement import FollowerThrowApproachMeasurement,validate_recipe,TRIGGER_CONDITION,reachable_cargo_admission
from tools.overworld.devtools_cargo_route_continuity import packets
from tools.overworld.test_devtools_cargo_route_continuity import SOURCE,query_event
from tools.overworld.test_devtools_follower_throw_measurement import snapshot,raw,binding
from tools.overworld.devtools_test_contract import TestEvaluator
ROOT=Path(__file__).resolve().parents[2]


def fixture():
    m=FollowerThrowApproachMeasurement(SOURCE)
    # Method fixture only. The complete Hop reader owns actual pose/commit proof.
    m.approach_hop=dict(startFrame=83,duration=13,returnFrame=101,commitSequence=4,policyKey=123,queries=[])
    m.speed_witnesses['normal']=dict(returnFrame=101,commitAfter=4)
    return m


class ApproachTests(unittest.TestCase):
    def test_reachable_no_step_requires_current_in_range_distinct_pickup_goal(self):
        h=deepcopy(snapshot(9)['actors'][1]['handle'])
        row=dict(status='REACHABLE',hasNextStep=False,workspace=dict(origin=dict(x=584,y=399,baseY=65536),
                 compatibility=dict(cargo=h,pickupDistance=1,requestKey=0x11002)))
        cargo=dict(handle=h,x=583,y=399,baseY=65536)
        self.assertTrue(reachable_cargo_admission(row,cargo))
        for fault in ('far','same-tile','height','wrong-cargo','pending','wrong-reach'):
            bad=deepcopy(cargo);q=deepcopy(row)
            if fault=='far':bad['x']=582
            elif fault=='same-tile':bad['x']=584
            elif fault=='height':bad['baseY'] += 17<<12
            elif fault=='wrong-cargo':bad['handle']['generation'] += 1
            elif fault=='pending':q['status']='PENDING'
            else:q['workspace']['compatibility']['pickupDistance']=2
            with self.subTest(fault=fault):self.assertFalse(reachable_cargo_admission(q,bad))
        row['hasNextStep']=True;cargo['x']=580
        self.assertTrue(reachable_cargo_admission(row,cargo))

    def test_native_notice_may_follow_identity_bind_but_cannot_change_or_disappear(self):
        sample=snapshot(9);target=sample['actors'][1]
        meter=FollowerThrowApproachMeasurement(SOURCE)
        self.assertFalse(meter._notice(sample,binding(None,TRIGGER_CONDITION),target))
        self.assertIsNone(meter.notice)
        real=binding(target,TRIGGER_CONDITION)
        self.assertTrue(meter._notice(sample,real,target))
        self.assertEqual(meter.notice,dict(frame=9,binding=real))
        for fault in ('lost','wrong-target','stale','wrong-source'):
            bad=deepcopy(real)
            if fault=='lost':bad=binding(None,TRIGGER_CONDITION)
            elif fault=='wrong-target':bad['target']['actor']['generation'] += 1
            elif fault=='stale':bad['targetCurrent']=False
            else:bad['sourceConditionId'] += 1
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'native Onix Interest'):
                meter._notice(sample,bad,target)

    def test_setup_callback_updates_current_bind_without_observation_credit(self):
        recipe=json.loads((ROOT/'tests/overworld/test-recipes/follower.throw-approach-cargo.json').read_text())
        for fault in (None,'gap','corrupt'):
            with self.subTest(fault=fault):
                evaluator=TestEvaluator(recipe)
                evaluator.install_measurements({'follower-throw-approach-cargo-v1':SOURCE})
                before=snapshot(0);before['actors']=[]
                evaluator.observe_record(dict(phase='setup',initialSnapshot=deepcopy(before),initialEvents=[]))
                evaluator.observe_record(dict(phase='setup',action='throw-tile',command='teleport',
                                              receipt={},snapshot=deepcopy(before)))
                row=raw('ordinary-notice',[snapshot(f) for f in range(1,21)],phase='setup')
                if fault=='gap':row['samples'][-1]['frame'] += 1
                elif fault=='corrupt':row['samples'][0]['observationBoundary']='not-a-completed-queue'
                result=evaluator.observe_record(row)
                self.assertEqual(result['observedFrames'],0)
                self.assertEqual(result['sampledFrames'],0)
                if fault:
                    self.assertEqual(result['state'],'failed')
                    self.assertEqual(evaluator.latest,before)
                else:
                    self.assertEqual(result['failures'],[])
                    self.assertEqual(evaluator.latest,row['samples'][-1])
                    self.assertEqual(evaluator.latest['frame'],20)
                    bound=evaluator.bind('mankey',evaluator.latest)
                    self.assertEqual((bound['species'],bound['role'],bound['subjectIdentity']),(56,'FOLLOWER',107))

    def test_recipe_keeps_saved_follower_and_exact_input(self):
        r=json.loads((ROOT/'tests/overworld/test-recipes/follower.throw-approach-cargo.json').read_text());validate_recipe(r)
        for fault in ('party','y','longer'):
            bad=deepcopy(r)
            if fault=='party':bad['setup'].insert(1,dict(id='prepare',op='party',args=dict(slot=0,species=56,level=20)))
            elif fault=='y':bad['actions'][0]['args']['keys'].append('Y')
            else:bad['actions'][1]['args']['frames'] += 1
            with self.assertRaisesRegex(ValueError,'unchanged Continue'):validate_recipe(bad)

    def test_current_policy_survives_legitimate_scope_and_candidate_changes(self):
        m=fixture()
        for f in (83,84,90,101):
            s=snapshot(f);a=s['actors'][0]
            if f==90:a['engineObject'].update(x=587,y=409)
            e=query_event(s,a,SOURCE['queryImage']);q=e['data']
            if f==90:
                q['after']['workspace']['compatibility']['scopeRevision'] += 1
                q['after']['workspace']['compatibility']['cargo']['generation'] += 1
            rows=packets(s,[e],a,SOURCE['queryImage'],s['nativeCycle']-1,pending_ok=True)
            m._policy(s,a,rows)
        self.assertIsNotNone(m.approach_witness)

    def test_midpoint_and_return_policy_or_owner_faults_reject(self):
        for fault,reason in (('midpoint','unlimited route policy changed'),('return','unlimited route policy changed'),('owner','query result or current workspace')):
            m=fixture()
            for f in (83,84,101):
                s=snapshot(f);a=s['actors'][0];e=query_event(s,a,SOURCE['queryImage']);d=e['data']
                if f==(101 if fault=='return' else 84):
                    if fault=='owner':
                        d['after']['workspace']['owner']=deepcopy(d['after']['workspace']['owner']);d['after']['workspace']['owner']['generation'] += 1
                    else:d['before' if fault=='return' else 'after']['workspace']['compatibility']['movementPolicyRevision'] += 1
                    with self.assertRaisesRegex(ValueError,reason):
                        rows=packets(s,[e],a,SOURCE['queryImage'],s['nativeCycle']-1,pending_ok=True);m._policy(s,a,rows)
                    break
                m._policy(s,a,packets(s,[e],a,SOURCE['queryImage'],s['nativeCycle']-1,pending_ok=True))

    def test_early_interior_query_does_not_prove_native_tile_advance(self):
        m=fixture()
        for f in (83,84):
            s=snapshot(f);a=s['actors'][0];m._policy(s,a,packets(s,[query_event(s,a)],a,SOURCE['queryImage'],s['nativeCycle']-1,pending_ok=True))
        s=snapshot(101);a=s['actors'][0]
        with self.assertRaisesRegex(ValueError,'current-tile advance query'):
            m._policy(s,a,packets(s,[query_event(s,a)],a,SOURCE['queryImage'],s['nativeCycle']-1,pending_ok=True))

    def test_missing_native_return_query_earns_no_credit(self):
        m=fixture();s=snapshot(101)
        with self.assertRaisesRegex(ValueError,'exact native ordinary-Hop return query'):m._policy(s,s['actors'][0],[])

    def test_pending_stays_bounded_and_native_call_fits_between_queues(self):
        s=snapshot(84);a=s['actors'][0];e=query_event(s,a,SOURCE['queryImage'],nodes=0)
        self.assertEqual(len(packets(s,[e],a,SOURCE['queryImage'],s['nativeCycle']-2,pending_ok=True)),1)
        e['data']['entryNativeCycle'] -= 1
        self.assertEqual(len(packets(s,[e],a,SOURCE['queryImage'],s['nativeCycle']-2,pending_ok=True)),1)
        with self.assertRaisesRegex(ValueError,'owner, clock'):packets(s,[e],a,SOURCE['queryImage'],s['nativeCycle']-2)
        future=deepcopy(e);future['data']['returnNativeCycle'] += 1
        with self.assertRaisesRegex(ValueError,'owner, clock'):packets(s,[future],a,SOURCE['queryImage'],s['nativeCycle']-2,pending_ok=True)
        e['data']['entryNativeCycle'] -= 1
        with self.assertRaisesRegex(ValueError,'owner, clock'):packets(s,[e],a,SOURCE['queryImage'],s['nativeCycle']-2,pending_ok=True)
        e=query_event(s,a,SOURCE['queryImage'],nodes=0);raw=bytearray.fromhex(e['data']['resultHex']);raw[124]=17
        e['data']['resultHex']=raw.hex();e['data']['after']['workspace']['lastWorkHex']=raw[108:136].hex()
        with self.assertRaisesRegex(ValueError,'existing work budget'):packets(s,[e],a,SOURCE['queryImage'],s['nativeCycle']-1,pending_ok=True)

if __name__=='__main__':unittest.main()
