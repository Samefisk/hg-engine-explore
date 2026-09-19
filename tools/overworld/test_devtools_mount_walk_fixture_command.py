"""Mount lane setup is bounded and cannot be labelled normal gameplay."""
from copy import deepcopy
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from tools.overworld.devtools_contract import validate_command
from tools.overworld.devtools_records import validate_recipe
from tools.overworld.devtools_test_contract import validate_test, TestEvaluator
from tools.overworld.test_devtools_walk_reset_command import subject
from tools.overworld.test_devtools_test_contract import recipe, snapshot


class MountWalkFixtureCommandTests(unittest.TestCase):
    def test_runtime_routes_only_validated_fields_and_retains_memory_receipt(self):
        from tools.overworld.devtools_runtime import DevtoolsSession
        endpoint=dict(frame=20,nativeCycle=30,prepared=True)
        native=dict(prepared=True,acceptedProof=False,advancedFrames=0,beforeHex='01',afterHex='02')
        session=SimpleNamespace(prepared=False,snapshot=lambda radius,diagnostic_details:deepcopy(endpoint),
            _prepared_result_boundary=lambda receipt:receipt)
        with patch('tools.overworld.devtools_mount_walk_fixture.MountWalkFixture') as fixture:
            fixture.return_value.run.return_value=deepcopy(native)
            args=self.args();result=DevtoolsSession.mount_walk_configure(session,args)
            fixture.assert_called_once_with(session,args['subject'],1,4,None,
                                            turning=None,crash_sound=None)
        self.assertTrue(session.prepared)
        self.assertEqual(result,{**native,'snapshot':endpoint})

    def args(self):
        actor=subject();actor['role']='MOUNTED'
        return dict(subject=actor,directionMode=1,travelTime=4)

    def test_runtime_forwards_explicit_disabled_stomp_threshold(self):
        from tools.overworld.devtools_runtime import DevtoolsSession
        session=SimpleNamespace(prepared=False,snapshot=lambda *a,**k:{},
            _prepared_result_boundary=lambda receipt:receipt)
        with patch('tools.overworld.devtools_mount_walk_fixture.MountWalkFixture') as fixture:
            fixture.return_value.run.return_value={}
            args={**self.args(),'stompTime':0}
            DevtoolsSession.mount_walk_configure(session,args)
            fixture.assert_called_once_with(session,args['subject'],1,4,0,
                                            turning=None,crash_sound=None)

    def test_failed_native_receipt_reaches_worker_error_details(self):
        from tools.overworld.devtools_runtime import DevtoolsSession
        error=ValueError('failed write');error.receipt={'restoredOnError':{'clock':20}}
        session=SimpleNamespace(prepared=False)
        with patch('tools.overworld.devtools_mount_walk_fixture.MountWalkFixture') as fixture:
            fixture.return_value.run.side_effect=error
            with self.assertRaises(ValueError) as caught:
                DevtoolsSession.mount_walk_configure(session,self.args())
        self.assertIs(caught.exception,error)
        self.assertEqual(error.details,{'mountWalkFixture':error.receipt})

    def test_all_authored_bounds_and_no_addresses(self):
        for direction in range(3):
            for frames in range(1,33):
                args={**self.args(),'directionMode':direction,'travelTime':frames}
                self.assertEqual(validate_command('mount-walk.configure',args),args)
        for threshold in range(33):
            args={**self.args(),'stompTime':threshold}
            self.assertEqual(validate_command('mount-walk.configure',args),args)
        for field,values in [('directionMode',[-1,3,True]),('travelTime',[0,33,True]),
                             ('stompTime',[-1,33,True,1.5])]:
            for value in values:
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    validate_command('mount-walk.configure',{**self.args(),field:value})
        for extra in ('address','speed','profileHex'):
            with self.assertRaises(ValueError):
                validate_command('mount-walk.configure',{**self.args(),extra:1})

    def test_exact_mounted_subject_and_prepared_only(self):
        args=self.args()
        for key in args['subject']:
            bad=deepcopy(args);del bad['subject'][key]
            with self.subTest(key=key),self.assertRaises(ValueError):validate_command('mount-walk.configure',bad)
        for role in ('WILD','FOLLOWER'):
            bad=deepcopy(args);bad['subject']['role']=role
            with self.assertRaises(ValueError):validate_command('mount-walk.configure',bad)
        value=dict(schemaVersion=1,mode='prepared',actions=[dict(op='mount-walk.configure',args=args)])
        self.assertEqual(validate_recipe(value),value)
        with self.assertRaises(ValueError):validate_recipe({**value,'mode':'normal'})

    def test_checked_setup_resolves_current_bound_actor(self):
        value=recipe();value['mode']='prepared';value['subjects'][0]['role']='MOUNTED'
        action=dict(id='lane',op='mount-walk.configure',args=dict(subject='subject',directionMode=1),
            budget=dict(maxSeconds=5,maxFrames=1,noProgressFrames=1))
        value['setup']=[action]
        self.assertEqual(validate_test(value)['setup'],[action])
        for threshold in (0, 2, 32):
            configured=deepcopy(value)
            configured['setup'][0]['args']['stompTime']=threshold
            self.assertEqual(validate_test(configured)['setup'],configured['setup'])
        for threshold in (-1, 33, True):
            configured=deepcopy(value)
            configured['setup'][0]['args']['stompTime']=threshold
            with self.assertRaises(ValueError):validate_test(configured)
        evaluator=TestEvaluator(value);current=snapshot();current['actors'][0]['role']='MOUNTED'
        with self.assertRaises(ValueError):evaluator.mount_walk_fixture_args(action['args'],current)
        evaluator.bind('subject',current)
        resolved=evaluator.mount_walk_fixture_args(action['args'],current)
        self.assertEqual(resolved['subject']['handle'],current['actors'][0]['handle'])
        stale=deepcopy(current);stale['actors'][0]['authorityGeneration']+=1
        with self.assertRaises(ValueError):evaluator.mount_walk_fixture_args(action['args'],stale)
        for bad in ({**value,'mode':'normal'},{**value,'setup':[],'actions':[action]}):
            with self.assertRaises(ValueError):validate_test(bad)


if __name__=='__main__':unittest.main()
