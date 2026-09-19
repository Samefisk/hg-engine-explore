"""The corner reader is a bounded shared command, never a standalone runner."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from tools.overworld.devtools_contract import validate_command
from tools.overworld.devtools_records import validate_recipe
from tools.overworld.test_devtools_walk_reset_command import subject


class CornerCommandTests(unittest.TestCase):
    def args(self):
        actor=subject();actor.update(role='MOUNTED',species=155)
        return dict(subject=actor,maxFrames=600)

    def test_bounds_and_exact_actor(self):
        args=self.args();self.assertEqual(validate_command('walk-corner.arm',args),args)
        for frames in (0,601,True,1.5):
            with self.assertRaises(ValueError):validate_command('walk-corner.arm',{**args,'maxFrames':frames})
        for key in args['subject']:
            bad=deepcopy(args);del bad['subject'][key]
            with self.subTest(key=key),self.assertRaises(ValueError):validate_command('walk-corner.arm',bad)
        for key,value in [('role','WILD'),('role','FOLLOWER'),('species',56)]:
            bad=deepcopy(args);bad['subject'][key]=value
            with self.assertRaises(ValueError):validate_command('walk-corner.arm',bad)

    def test_prepared_only_and_no_addresses(self):
        for op,args in [('walk-corner.arm',self.args()),('walk-corner.close',{}),('walk-corner.calibrate',{}),
                        ('walk-corner.probe',{'subject':self.args()['subject']})]:
            self.assertEqual(validate_command(op,args),args)
            with self.assertRaises(ValueError):validate_command(op,{**args,'address':1})
            value=dict(schemaVersion=1,mode='prepared',actions=[dict(op=op,args=args)])
            self.assertEqual(validate_recipe(value),value)
            with self.assertRaises(ValueError):validate_recipe({**value,'mode':'normal'})

    def test_worker_runtime_once_and_zero_advance_close(self):
        from tools.overworld.devtools_runtime import DevtoolsSession,DevtoolsFailure
        class Reader:
            def __init__(self,*args):self.closed=False
            def arm(self):pass
            def close(self):self.closed=True
            def result(self):return dict(closed=self.closed,acceptedProof=False)
        current=dict(frame=10)
        session=SimpleNamespace(walk_corner=None,prepared=False,snapshot=lambda **kw:current)
        with patch('tools.overworld.devtools_records.select_current_actor',return_value=self.args()['subject']), \
                patch('tools.overworld.devtools_corner_observer.NativeCornerObserver',Reader):
            start=DevtoolsSession.walk_corner_arm(session,self.args())
            self.assertFalse(start['acceptedProof'])
            with self.assertRaises(DevtoolsFailure):DevtoolsSession.walk_corner_arm(session,self.args())
            end=DevtoolsSession.walk_corner_close(session)
        self.assertEqual(end['advancedFrames'],0)
        self.assertTrue(end['walkCorner']['closed'])
        self.assertEqual(end['snapshot'],current)

    def test_probe_is_one_prepared_bridge_receipt_not_movement_credit(self):
        from tools.overworld.devtools_runtime import DevtoolsSession
        endpoint=dict(frame=10,prepared=True)
        session=SimpleNamespace(prepared=False,bridge=SimpleNamespace(run=lambda recipe:{'value':{'completed':True}}),
            snapshot=lambda *args,**kw:endpoint,_prepared_result_boundary=lambda receipt:receipt)
        with patch('tools.overworld.devtools_corner_probe.CornerProbe') as probe:
            receipt=DevtoolsSession.walk_corner_probe(session,{'subject':self.args()['subject']})
            probe.assert_called_once_with(session,self.args()['subject'])
        self.assertTrue(session.prepared)
        self.assertFalse(receipt['acceptedProof'])
        self.assertEqual(receipt['value'],{'completed':True})
        self.assertEqual(receipt['snapshot'],endpoint)

    def test_calibration_is_terminal_even_when_the_control_fails(self):
        from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure
        for failed in (False, True):
            session = SimpleNamespace(walk_corner=object(), snapshot=lambda **kw: {'frame': 10})
            with patch('tools.overworld.devtools_corner_control.calibrate_corner_policy') as calibrate:
                if failed:
                    calibrate.side_effect = ValueError('bad observation')
                    with self.assertRaises(ValueError): DevtoolsSession.walk_corner_calibrate(session)
                else:
                    calibrate.return_value = {'restored': True}
                    receipt = DevtoolsSession.walk_corner_calibrate(session)
                    self.assertEqual(receipt['calibration'], {'restored': True})
                    self.assertEqual(receipt['advancedFrames'], 0)
                    self.assertFalse(receipt['acceptedProof'])
                self.assertTrue(session.walk_corner_calibrated)
                with self.assertRaises(DevtoolsFailure): DevtoolsSession.walk_corner_calibrate(session)


if __name__=='__main__':unittest.main()
