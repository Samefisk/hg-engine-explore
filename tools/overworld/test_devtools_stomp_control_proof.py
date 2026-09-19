"""Copied host-data controls; a green fixture is not accepted gameplay proof."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_stomp_control_proof import (KIND, REQUIREMENT, RULES, CONTROL_FAULTS, FAULTS,
    BASELINE_FAULTS, StompControlNegative, contract, measurements, validate_negative_result)
from tools.overworld.devtools_stomp_control_measurement import StompControlMeasurement
from tools.overworld.test_devtools_stomp_control_measurement import host_control_fixture, enrich_control_rows, control_receipt_for


def raw_control_records():
    """Current typed control recipe with synthetic memory rows, not live proof."""
    from tools.overworld.test_devtools_stomp_measurement import raw_records
    from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
    from tools.overworld.devtools_test_inputs import measurement_inputs
    root=Path(__file__).resolve().parents[2]
    _,rows=raw_records()
    test=validate_test(json.loads((root/'tests/overworld/test-recipes/observation.stomp-policy-control.json').read_text()))
    binding_raw,binding=enrich_control_rows(rows,rows[0]['initialSnapshot'])
    evaluator=TestEvaluator(test);evaluator.install_measurements(measurement_inputs(test,root))
    for row in rows[:-1]:
        result=evaluator.observe_record(row,full_report=False)
        if result['state']=='failed':raise AssertionError(result)
    meter=evaluator.measurements[KIND]
    _,receipt,terminal=control_receipt_for(meter,binding_raw,binding)
    rows.insert(-1,dict(phase='observe',action='threshold-control',command='stomp.calibrate',
        receipt=receipt,snapshot=terminal))
    rows[-1].update(receipt=dict(closed=True,advancedFrames=0,acceptedProof=False,snapshot=terminal,
        stompFeedback=receipt['stompFeedback']),snapshot=terminal)
    return test,rows


def good_result():
    meter,receipt,terminal=host_control_fixture()
    meter.calibrate(receipt,terminal)
    meter.close(dict(closed=True,advancedFrames=0,acceptedProof=False,snapshot=terminal,
        stompFeedback=receipt['stompFeedback']),terminal)
    return dict(passed=True,failures=[],measurements={KIND:meter.finish()}),dict(sessionId='host',
        sessionCleanup=dict(sessionId='host',closed=True,errors=[]))


class StompControlProofTests(unittest.TestCase):
    def test_current_typed_controller_and_all_23_copied_controls(self):
        from tools.overworld.control import _replay_shared_test
        test,rows=raw_control_records()
        baseline=_replay_shared_test(test,rows)
        self.assertTrue(baseline['passed'],baseline['failures'])
        record=dict(sessionId='host',sessionCleanup=dict(sessionId='host',closed=True,errors=[]))
        self.assertEqual(len(measurements(baseline,record)),3)
        for fault in FAULTS:
            with self.subTest(fault=fault):
                validate_negative_result(_replay_shared_test(test,rows,fault=fault),fault)

    def test_all_baseline_fault_causes_survive_control_wrapper(self):
        from tools.overworld.test_devtools_stomp_measurement import fixture
        for fault in BASELINE_FAULTS:
            meter=StompControlMeasurement(100);negative=StompControlNegative(fault);error=None
            for raw in fixture():
                row=deepcopy(raw);op=row.pop('op')
                if op=='close':break
                subjects={'actor':meter.subject} if meter.subject else {}
                if op=='configure':
                    value=negative.mutate(dict(command='mount-walk.configure',receipt=row['receipt']),subjects)
                    row['receipt']=value['receipt']
                elif op=='observe':
                    value=negative.mutate(dict(phase='observe',samples=[row['snapshot']],events=row['events']),subjects)
                    row.update(snapshot=value['samples'][0],events=value['events'])
                try:getattr(meter,op)(**row)
                except (ValueError,KeyError,TypeError) as caught:error=str(caught);break
                if meter.failures:break
            result=dict(passed=False,failures=[] if error is None else [error],measurements={KIND:meter.finish()})
            with self.subTest(fault=fault):
                self.assertTrue(negative.applied)
                validate_negative_result(result,fault)

    def test_exact_control_rows_and_json_roundtrip(self):
        replay,record=good_result()
        self.assertTrue(replay['measurements'][KIND]['passed'])
        rows=measurements(replay,record)
        self.assertEqual([(r['claim'],r['name']) for r in rows],list(RULES))
        self.assertEqual(len(rows),3)
        self.assertEqual(sum(map(len,contract().values())),3)
        self.assertEqual(measurements(json.loads(json.dumps(replay)),record),rows)
        self.assertEqual(replay,json.loads(json.dumps(replay)))
        self.assertEqual(REQUIREMENT,'shared.stomp-recorder-control-v1')

    def test_copied_control_faults_use_same_full_meter(self):
        for fault in CONTROL_FAULTS:
            meter,receipt,terminal=host_control_fixture()
            original=deepcopy(receipt);negative=StompControlNegative(fault)
            row=negative.mutate(dict(command='stomp.calibrate',receipt=receipt),{'actor':meter.subject})
            try:meter.calibrate(row['receipt'],terminal)
            except (ValueError,KeyError,TypeError) as error:
                result=dict(passed=False,failures=[str(error)],measurements={KIND:meter.finish()})
            else:self.fail('known bad Stomp control passed: '+fault)
            with self.subTest(fault=fault):
                self.assertEqual(receipt,original)
                self.assertTrue(negative.applied)
                validate_negative_result(result,fault)

    def test_green_summary_cannot_replace_positive_negative_or_restoration(self):
        for fault in ('positive','negative','clock','restore','guard','latch','snapshot','close'):
            replay,record=good_result();value=replay['measurements'][KIND]
            if fault=='positive':value['natural']['cases'][0]['feedback']['calls'][-1]['effect']=0
            elif fault=='negative':value['natural']['cases'][1]['feedback']['calls'][-1]['effect']=1
            elif fault=='clock':value['control']['restoredClock']['nativeCycle']+=1
            elif fault=='restore':value['control']['restored']['mountStateHex']='00'*184
            elif fault=='guard':value['calibrationReceipt']['terminalGuard']=False
            elif fault=='latch':value['cleanup']['stompFeedback']['failure']=None
            elif fault=='snapshot':value['cleanup']['snapshot']['player']['pos_x']+=1
            else:record['sessionCleanup']['closed']=False
            with self.subTest(fault=fault),self.assertRaises((ValueError,KeyError)):
                measurements(replay,record)

    def test_generic_failure_never_credits_any_control(self):
        for fault in FAULTS:
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                validate_negative_result(dict(passed=False,failures=['stomp control incomplete']),fault)


if __name__=='__main__':unittest.main()
