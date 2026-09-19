"""Host checks of the full corner baseline and final policy-read calibration."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import unittest

from tools.overworld.test_devtools_corner_measurement import fixture as baseline_fixture
from tools.overworld.devtools_corner_control_measurement import CornerControlMeasurement, KIND, native_call
from tools.overworld.devtools_corner_control_proof import (CONTROL_FAULTS, CornerControlNegative,
    contract, measurements, validate_negative_result)
from tools.overworld.devtools_mount_walk_fixture import STATE_BYTES


def fixture():
    initial,subject,query,reader,rows=baseline_fixture()
    state_address=0x02290000
    for snapshot,events in rows:
        for call in snapshot['walkCorner']['calls']:call['statePointer']=state_address
        for event in events:
            if event['kind']=='native-observation' and event['data'].get('observation')=='walk-corner-strict':
                event['data']['statePointer']=state_address
    meter=CornerControlMeasurement(50);meter.probe(query,initial);meter.arm(subject,initial,reader)
    for index,(snapshot,events) in enumerate(rows):
        meter.observe(snapshot,events)
        if index==1:meter.begin_recovery(snapshot)
    start=initial['frame']
    for count,keys in ((1,['DOWN','LEFT']),(1,[]),(1,['LEFT']),(5,[])):
        meter.command(dict(op='step',args=dict(frames=count,keys=keys),startFrame=start),
            dict(requestedGameFrames=count,completedGameFrames=count,observedFieldFrames=count))
        start+=count
    terminal=deepcopy(rows[-1][0]);strict=deepcopy(meter.natural.calls[-1])
    clean=dict(current=deepcopy(strict['before']),mountBinding=deepcopy(strict['mountBinding']),
        policy=dict(profileHex=strict['profileHex'],profile19=1),
        mountStateHex=bytes.fromhex(query['before']['mountStateHex']).ljust(STATE_BYTES,b'\0').hex(),
        input=dict(heldKeys=0,newKeys=0,rawHeld=0,rawNew=0,simulatedKeys=0),
        player=deepcopy(terminal['player']),mount=deepcopy(terminal['actors'][0]['engineObject']))
    clean['current']['publicSubject']=deepcopy(terminal['actors'][0])
    bad=deepcopy(clean);raw=bytearray.fromhex(clean['mountStateHex']);raw[27]=0
    profile=bytearray.fromhex(clean['policy']['profileHex']);profile[19]=0
    bad.update(mountStateHex=raw.hex(),policy=dict(profileHex=profile.hex(),profile19=0))
    clock={k:terminal[k] for k in ('frame','actorFrame','nativeCycle')}
    registers={**{'r'+str(i):i for i in range(16)},'cpsr':32,'spsr':0}
    control=dict(state='complete',failure=None,cleanupPending=False,acceptedProof=False,
        guestInstructionAdvance=0,guestMemoryWrites=2,clean=clean,bad=bad,restored=deepcopy(clean),
        strictReceipt=native_call(strict),stateAddress=state_address,stateBytes=STATE_BYTES,policyAddress=state_address+8,
        changedAddress=state_address+27,changedOffset=19,originalHex='01',changedHex='00',
        clock=clock,restoredClock=deepcopy(clock),registers=registers,restoredRegisters=deepcopy(registers))
    calibrated=deepcopy(terminal);calibrated['walkCorner'].update(policyCalibration=control,guestMemoryWrites=2)
    calibrated['walkCorner']['calls']=[native_call(call) for call in calibrated['walkCorner']['calls']]
    receipt=dict(prepared=True,advancedFrames=0,acceptedProof=False,snapshot=calibrated,calibration=deepcopy(control))
    closed=deepcopy(calibrated);closed['walkCorner']['closed']=True
    cleanup=dict(closed=True,advancedFrames=0,acceptedProof=False,snapshot=closed,walkCorner=closed['walkCorner'])
    return meter,receipt,cleanup


class CornerControlMeasurementTests(unittest.TestCase):
    def test_framed_sequence_frame_and_cycle_still_fail_closed(self):
        for field,value,reason in (('sequence',999,'corner native sequence gap'),
                                   ('entryNativeCycle',999999,'corner native callback clock differs'),
                                   ('frame',999,'corner event completion frame differs')):
            initial,subject,query,reader,rows=baseline_fixture()
            event=rows[0][1][0]
            if field=='frame':event[field]=value
            else:event['data'][field]=value
            meter=CornerControlMeasurement(50)
            meter.probe(query,initial);meter.arm(subject,initial,reader)
            meter.observe(*rows[0])
            self.assertIn(reason,meter.failures)

    def test_raw_framed_join_preserves_native_policy_identity_and_clocks(self):
        for fault in ('policy','identity','clock','reader-clock'):
            meter,receipt,cleanup=fixture()
            strict=receipt['calibration']['strictReceipt']
            if fault=='policy':strict['profile19']=2
            elif fault=='identity':strict['before']['publicSubject']['handle']['generation']+=1
            elif fault=='clock':strict['returnClock']['nativeCycle']+=1
            else:receipt['snapshot']['walkCorner']['calls'][0]['returnClock']['nativeCycle']+=1
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,
                    'original strict policy read|calibrated reader differs'):
                meter.calibrate(receipt,receipt['snapshot'])

    def test_retained_real_raw_replays_through_calibration_without_inventing_close(self):
        from tools.overworld.devtools_test_contract import TestEvaluator
        from tools.overworld.devtools_test_inputs import measurement_inputs
        repo=Path(__file__).resolve().parents[2]
        directory=repo/'build/overworld-devtools/test-ab1f9c783e56431bba57d26afd9ae0c0'
        if not directory.exists():
            self.skipTest('optional private calibration failure memory data is absent')
        test=json.loads((directory/'test.json').read_text())
        evaluator=TestEvaluator(test)
        evaluator.install_measurements(measurement_inputs(test,repo))
        with gzip.open(directory/'observations.jsonl.gz','rt') as stream:
            for line in stream:
                last_record=json.loads(line)
                report=evaluator.observe_record(last_record,full_report=False)
                self.assertNotEqual(report['state'],'failed',report)
        meter=evaluator.measurements[KIND]
        self.assertTrue(meter.ready,meter.result())
        self.assertEqual(meter.failures,[])
        # The failed job stopped before its explicit reader-close command.
        # Replay diagnoses the join bug; it does not create accepted proof.
        self.assertFalse(meter.closed)
        self.assertFalse(meter.result()['passed'])
        self.assertFalse(meter.result()['acceptedProof'])
        # Host-only completion shape control. This close did NOT run in the
        # game; do not write it into the retained stream or issue acceptance.
        snapshot=deepcopy(last_record['snapshot'])
        snapshot['walkCorner']['closed']=True
        close=dict(closed=True,advancedFrames=0,acceptedProof=False,snapshot=snapshot,
                   walkCorner=snapshot['walkCorner'])
        report=evaluator.observe_record(dict(phase='observe',action='close-corner-reader',
            command='walk-corner.close',receipt=close,snapshot=snapshot),full_report=False)
        self.assertNotEqual(report['state'],'failed',report)
        result=evaluator.finish()
        self.assertTrue(result['passed'],result.get('failures'))
        proof_record=dict(sessionId='synthetic-host-close',sessionCleanup=dict(
            sessionId='synthetic-host-close',closed=True,errors=[]))
        self.assertEqual(len(measurements(result,proof_record)),3)
        for target in ('control-native-clock','cleanup-native-identity'):
            bad=deepcopy(result)
            measured=bad['measurements'][KIND]
            if target=='control-native-clock':
                measured['control']['strictReceipt']['returnClock']['nativeCycle']+=1
            else:
                measured['cleanup']['walkCorner']['calls'][0]['before']['publicSubject']['handle']['generation']+=1
            with self.subTest(target=target),self.assertRaises(ValueError):
                measurements(bad,proof_record)

    def test_complete_baseline_then_control_and_closed_private_session(self):
        meter,receipt,cleanup=fixture()
        self.assertTrue(meter.natural.ready,meter.natural.failures)
        self.assertFalse(meter.ready)
        meter.calibrate(receipt,receipt['snapshot']);meter.close(cleanup,receipt['snapshot'])
        result=meter.finish();self.assertTrue(result['passed'],result)
        replay=dict(passed=True,failures=[],measurements={KIND:result})
        record=dict(sessionId='private',sessionCleanup=dict(sessionId='private',closed=True,errors=[]))
        rows=measurements(replay,record)
        self.assertEqual(len(rows),3)
        self.assertEqual(set(contract()),{'live-actor-identity','controlled-action'})
        record['sessionCleanup']['closed']=False
        with self.assertRaises(ValueError):measurements(replay,record)

    def test_policy_control_copied_faults_fail_for_exact_meaning(self):
        for fault in CONTROL_FAULTS:
            meter,receipt,cleanup=fixture();control=CornerControlNegative(fault)
            row=control.mutate(dict(phase='observe',command='walk-corner.calibrate',receipt=receipt),
                {'actor':meter.natural.subject})
            with self.subTest(fault=fault):
                self.assertTrue(control.applied)
                try:meter.calibrate(row['receipt'],receipt['snapshot'])
                except (ValueError,KeyError,TypeError) as error:meter.failures.append(str(error))
                self.assertTrue(meter.failures)
                validate_negative_result(dict(passed=False,failures=[],measurements={KIND:meter.result()}),fault)

    def test_missing_baseline_events_keep_exact_failure_at_calibration(self):
        from tools.overworld.devtools_corner_proof import MEANINGS
        for fault,event in MEANINGS.items():
            with self.subTest(fault=fault):
                meter,receipt,cleanup=fixture()
                meter.natural.traces=[e for e in meter.natural.traces if e['data']['event']!=event]
                with self.assertRaises(ValueError) as caught:
                    meter.calibrate(receipt,receipt['snapshot'])
                result=dict(passed=False,failures=[dict(code='raw-observation-invalid',message=str(caught.exception))],
                            measurements={KIND:meter.finish()})
                validate_negative_result(result,fault)
                result['failures'][0]['message']='corner calibration lacks complete original baseline'
                with self.assertRaisesRegex(ValueError,'unrelated reason'):
                    validate_negative_result(result,fault)

    def test_retained_control_all_faults_use_controller_acceptance_loop(self):
        from tools.overworld.control import _replay_shared_test
        from tools.overworld.devtools_evidence_stream import load_observations
        from tools.overworld.devtools_corner_control_proof import FAULTS
        repo=Path(__file__).resolve().parents[2]
        directory=repo/'build/overworld-devtools/test-dc83388fdddd448ab8d5bb4fae848e30'
        if not directory.exists():
            self.skipTest('optional private completed corner control memory data is absent')
        test=json.loads((directory/'test.json').read_text())
        rows=load_observations(directory/'observations.jsonl.gz')
        self.assertTrue(_replay_shared_test(test,rows)['passed'])
        for fault in FAULTS:
            with self.subTest(fault=fault):
                validate_negative_result(_replay_shared_test(test,rows,fault=fault),fault)

    def test_post_control_gameplay_and_changed_cleanup_reject(self):
        meter,receipt,cleanup=fixture();meter.calibrate(receipt,receipt['snapshot'])
        meter.observe(receipt['snapshot'],[])
        self.assertIn('corner control observed gameplay after calibration',meter.failures)
        meter,receipt,cleanup=fixture();meter.calibrate(receipt,receipt['snapshot'])
        cleanup['walkCorner']['policyCalibration']['restoredClock']['frame']+=1
        with self.assertRaises(ValueError):meter.close(cleanup,receipt['snapshot'])

    def test_proof_checks_baseline_even_when_summary_claims_pass(self):
        meter,receipt,cleanup=fixture();meter.calibrate(receipt,receipt['snapshot']);meter.close(cleanup,receipt['snapshot'])
        result=meter.result();result['natural']['traces']=[e for e in result['natural']['traces'] if e['data']['event']!='CANDIDATE_REJECTED']
        with self.assertRaises(ValueError):measurements(dict(passed=True,failures=[],measurements={KIND:result}),
            dict(sessionId='private',sessionCleanup=dict(sessionId='private',closed=True,errors=[])))


if __name__=='__main__':unittest.main()
