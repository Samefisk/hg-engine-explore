"""Strict registration and exact fixture restore checks; no game run."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from tools.overworld.devtools_test_contract import TestEvaluator,validate_test,_valid_requested_raw_rows
from tools.overworld.devtools_contract import validate_command
from tools.overworld.control import _shared_test_registration
from tools.overworld.devtools_mount_teleport_fixture import MountTeleportFixture,MountTeleportRestoreFixture,STATE_ADDRESS,STATE_BYTES
from tools.overworld.test_devtools_mount_walk_fixture import session
from tools.overworld.test_devtools_warp_gate import sample
from tools.overworld.devtools_warp_gate_proof import KIND,measurements,WarpGateNegative

ROOT=Path(__file__).resolve().parents[2]

class WarpIntegrationTests(unittest.TestCase):
    def recipe(self):return json.loads((ROOT/'tests/overworld/test-recipes/warp.blocked-mid-motion.json').read_text())

    def test_registration_and_meter_routing(self):
        test=validate_test(self.recipe());registration,_=_shared_test_registration(test,ROOT)
        self.assertEqual(registration['evaluator'],KIND)
        evaluator=TestEvaluator(test);evaluator.install_measurements({KIND:{'contractVersion':1}})
        self.assertTrue(evaluator.uses_raw_records)
        result=sample();wrapped=dict(passed=True,failures=[],measurements={KIND:result})
        self.assertEqual(len(measurements(wrapped,dict(sessionId='x',sessionCleanup=dict(sessionId='x',closed=True,errors=[])))),5)

    def test_extra_raw_rows_require_a_loading_transition(self):
        loading=({'fieldAvailable':False},(),())
        normal=({'fieldAvailable':True},(),())
        self.assertTrue(_valid_requested_raw_rows([loading,loading],1))
        self.assertTrue(_valid_requested_raw_rows([loading,normal],1))
        self.assertFalse(_valid_requested_raw_rows([normal,normal],1))
        self.assertFalse(_valid_requested_raw_rows([loading],2))

    def test_route_changes_rejected(self):
        for fault in ('door','restore','input','budget','subject'):
            value=self.recipe()
            if fault=='door':value['setup'][0]['args']['x']+=1
            elif fault=='restore':value['actions'].pop(7)
            elif fault=='input':value['actions'][2]['args']['keys']=['RIGHT']
            elif fault=='budget':value['budgets']['maxFrames']=1201
            else:value['measurements'][0]['subject']='other'
            with self.subTest(fault=fault),self.assertRaises(ValueError):validate_test(value)

    def test_raw_bind_and_configuration_reach_meter(self):
        from tools.overworld.devtools_records import select_current_actor
        result=sample();snapshot=result['initial']
        evaluator=TestEvaluator(validate_test(self.recipe()))
        evaluator.install_measurements({KIND:{'contractVersion':1}})
        evaluator.observe_record(dict(phase='setup',initialSnapshot=snapshot,initialEvents=[]))
        selected=select_current_actor(snapshot,result['subject'])
        evaluator.observe_record(dict(phase='setup',action='bind',command='bind',snapshot=snapshot,receipt=selected))
        self.assertEqual(evaluator.failures,[])
        self.assertIsNotNone(evaluator.measurements[KIND].initial)
        config=deepcopy(result['journal'][0]['receipt'])
        config['subject']=selected
        for point in ('before','after'):config[point]['readiness']['subject']=selected
        evaluator.observe_record(dict(phase='observe',action='configure-up',command='mount-teleport.configure',snapshot=snapshot,receipt=config))
        self.assertEqual(evaluator.failures,[])
        self.assertIsNotNone(evaluator.measurements[KIND].config)

    def test_exact_original_restore_and_changed_neighbor_rejected(self):
        with patch('tools.overworld.devtools_mount_walk_fixture.authenticate_mount',return_value={'stateAddress':STATE_ADDRESS}),patch('tools.overworld.devtools_mount_teleport_fixture.authenticate_mount',return_value={'stateAddress':STATE_ADDRESS}):
            s=session();original=s.read(STATE_ADDRESS,STATE_BYTES);profile=original[8:80]
            MountTeleportFixture(s,s.subject,9,7,0).run()
            receipt=MountTeleportRestoreFixture(s,s.subject,profile).run()
            self.assertEqual(s.read(STATE_ADDRESS,STATE_BYTES),original)
            self.assertTrue(receipt['completed']);self.assertFalse(receipt['guestAdvanced'])
            MountTeleportFixture(s,s.subject,9,7,0).run();s.put(STATE_ADDRESS+8+13,b'\x7f')
            writes=len(s.writes)
            with self.assertRaisesRegex(ValueError,'outside fixture bytes'):MountTeleportRestoreFixture(s,s.subject,profile).run()
            self.assertEqual(len(s.writes),writes)

    def test_restore_command_has_no_caller_supplied_profile(self):
        from tools.overworld.devtools_records import select_current_actor
        result=sample();subject=select_current_actor(result['initial'],result['subject'])
        self.assertEqual(validate_command('mount-teleport.restore',dict(subject=subject))['subject'],subject)
        with self.assertRaises(ValueError):validate_command('mount-teleport.restore',dict(subject=subject,profileHex='00'*72))

    def test_raw_copied_control_mutates_real_teleport_sample(self):
        result=sample();snapshot=next(row['snapshot'] for row in result['journal'] if row['op']=='observe' and row['snapshot']['actors'][0]['motionKind']=='TELEPORT')
        control=WarpGateNegative('warp-mid-teleport');row=dict(samples=[snapshot],events=[])
        changed=control.mutate(row)
        self.assertTrue(control.applied);self.assertEqual(changed['samples'][0]['context']['mapId'],69)
        self.assertEqual(row['samples'][0]['context']['mapId'],67)

    def test_no_walk_control_removes_every_restored_up_frame(self):
        result=sample();control=WarpGateNegative('warp-no-walk-input');changed=[]
        for row in result['journal']:
            command='mount-teleport.restore' if row['op']=='restore' else None
            snapshot=row.get('snapshot')
            copied=control.mutate(dict(command=command,snapshot=snapshot,events=row.get('events',[])))
            if snapshot and snapshot.get('selector',{}).get('rawHeld')==64 and control.restored:
                changed.append(copied['snapshot']['selector']['rawHeld'])
        self.assertTrue(control.applied);self.assertTrue(changed);self.assertEqual(set(changed),{0})

if __name__=='__main__':unittest.main()
