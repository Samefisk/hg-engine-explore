"""Copied calibration controls. Synthetic terminal receipt is not live proof."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_walk_matrix_control_proof import (KIND, RULES, CONTROL_FAULTS, FAULTS,
    MatrixControlNegative, contract, measurements, validate_negative_result)
from tools.overworld.devtools_walk_matrix_control_measurement import WalkMatrixControlMeasurement, moving_summary, validate_control
from tools.overworld.devtools_walk_matrix_control import BAD_ENUM
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.test_devtools_walk_matrix_measurement import pilot


def host_control():
    """Real retained two-case baseline followed by explicitly generated host control."""
    meter=pilot(meter=WalkMatrixControlMeasurement(100),close=False)
    if not meter.natural.ready:raise AssertionError(meter.failures)
    terminal=deepcopy(meter.last);tick=meter.last_moving
    actor=next(a for a in terminal['actors'] if a['handle']==meter.subject['handle'])
    raw=bytearray.fromhex(tick['after']['rawHex']);raw[48]=0
    current=deepcopy(tick['afterCurrent']);current['publicSubject']=deepcopy(actor)
    clean=dict(current=current,motion=decode_motion(bytes(raw)),player=terminal['player'],mount=actor['engineObject'],
        input=dict(heldKeys=0,newKeys=0,rawHeld=0,rawNew=0,simulatedKeys=0))
    bad=bytearray(raw);bad[48]=255
    clock={k:terminal[k] for k in ('frame','actorFrame','nativeCycle')}
    regs={k:0 for k in (*('r'+str(i) for i in range(16)),'cpsr','spsr')}
    control=dict(state='complete',failure=None,cleanupPending=False,acceptedProof=False,guestInstructionAdvance=0,
        guestMemoryWrites=2,clean=clean,restored=deepcopy(clean),bad=dict(rawHex=bad.hex(),failure=BAD_ENUM),
        priorMovingTick=moving_summary(tick),motionPointer=meter.motion_pointer,stateBytes=52,
        changedAddress=meter.motion_pointer+48,changedOffset=48,originalHex='00',changedHex='ff',
        clock=clock,restoredClock=deepcopy(clock),registers=regs,restoredRegisters=deepcopy(regs))
    reader=dict(terminal['walkMatrix'],closed=False,calibration=control,guestMemoryWrites=2,lastMovingTick=moving_summary(tick))
    terminal['walkMatrix']=reader
    receipt=dict(advancedFrames=0,acceptedProof=False,prepared=True,snapshot=terminal,calibration=control)
    return meter,receipt,terminal


class MatrixControlProofTests(unittest.TestCase):
    def test_accepted_control_replays_identical_to_its_stored_json_evaluation(self):
        from tools.overworld.control import _replay_shared_test, _shared_artifact, load_observations
        root=Path(__file__).resolve().parents[2]
        directory=root/'build/overworld-devtools/test-18cb7c5299404424b81d70471e1f05cb'
        if not directory.exists():self.skipTest('optional accepted control18cb memory data absent')
        test=json.loads((directory/'test.json').read_text())
        manifest=json.loads((directory/'manifest.json').read_text())
        rows=load_observations(_shared_artifact(manifest['observationsArtifact'],directory))
        self.assertTrue(manifest['acceptedProof'])
        replay=_replay_shared_test(test,rows,repo=root)
        self.assertTrue(replay['passed'],replay['failures'])
        self.assertEqual(replay,manifest['evaluation'])
        self.assertEqual(replay,json.loads(json.dumps(replay)))
        self.assertEqual(len(measurements(replay,manifest)),3)
        for fault in FAULTS:
            with self.subTest(fault=fault):
                validate_negative_result(_replay_shared_test(test,rows,fault=fault,repo=root),fault)

    def test_wrapper_finish_cause_survives_compact_natural_result(self):
        # Exact shape produced when missing first-case return reaches configure.
        # The wrapper has finished; its compact child still has no failure.
        result=dict(passed=False,failures=[dict(code='raw-observation-invalid',
            message='matrix configure before prior completion')],measurements={KIND:dict(
                failures=['matrix exact lifecycle missing: CONTROL_RETURNED'],natural=dict(failures=[]))})
        validate_negative_result(result,'matrix-missing-return')
        result['measurements'][KIND]['failures']=['matrix incomplete']
        with self.assertRaises(ValueError):validate_negative_result(result,'matrix-missing-return')

    def test_retained_checked_control_replays_all_copied_faults(self):
        from tools.overworld.control import _replay_shared_test, _shared_artifact, load_observations
        root=Path(__file__).resolve().parents[2]
        directory=root/'build/overworld-devtools/test-118d86e36f87421a93a73022e2dc41fd'
        if not directory.exists():self.skipTest('optional checked control118d memory data absent')
        test=json.loads((directory/'test.json').read_text())
        manifest=json.loads((directory/'manifest.json').read_text())
        rows=load_observations(_shared_artifact(manifest['observationsArtifact'],directory))
        baseline=_replay_shared_test(test,rows,repo=root)
        self.assertTrue(baseline['passed'],baseline['failures'])
        self.assertEqual(len(measurements(baseline,manifest)),3)
        for fault in FAULTS:
            with self.subTest(fault=fault):
                result=_replay_shared_test(test,rows,fault=fault,repo=root)
                self.assertFalse(result['passed'])
                validate_negative_result(result,fault)

    def test_original_prefix_plus_terminal_reader_control_maps_only_control_claim(self):
        meter,receipt,terminal=host_control()
        meter.calibrate(receipt,terminal)
        meter.close(dict(advancedFrames=0,acceptedProof=False,closed=True,snapshot=terminal,
            walkMatrix=dict(terminal['walkMatrix'],closed=True)),terminal)
        result=meter.finish()
        record=dict(sessionId='host',sessionCleanup=dict(sessionId='host',closed=True,errors=[]))
        rows=measurements(dict(passed=True,failures=[],measurements={KIND:result}),record)
        self.assertEqual([(r['claim'],r['name']) for r in rows],list(RULES))
        self.assertEqual(sum(map(len,contract().values())),3)
        self.assertTrue(result['natural']['prefixOnly'])
        self.assertEqual(result['natural']['completedCases'],2)
        for change in ('raw','baseline','cleanup'):
            copied=deepcopy(result)
            if change=='raw':copied['control']['bad']['rawHex']=copied['control']['clean']['motion']['rawHex']
            elif change=='baseline':copied['natural']['cases'][0]['ticks'][0]['before']['elapsed']=1
            else:copied['cleanup']['walkMatrix']['guestMemoryWrites']=0
            with self.subTest(change=change),self.assertRaises(ValueError):
                measurements(dict(passed=True,failures=[],measurements={KIND:copied}),record)

    def test_copied_calibration_faults_use_same_production_validator(self):
        for fault in CONTROL_FAULTS:
            meter,receipt,terminal=host_control()
            negative=MatrixControlNegative(fault)
            original=deepcopy(receipt)
            row=negative.mutate(dict(command='walk-matrix.calibrate',receipt=receipt),{'actor':meter.subject})
            self.assertEqual(receipt,original)
            try:
                validate_control(row['receipt'].get('calibration'),meter.last_moving,meter.last,
                    meter.subject,meter.motion_pointer)
            except (ValueError,KeyError,TypeError) as error:
                result=dict(passed=False,failures=[str(error)],measurements={})
            else:self.fail('known-bad calibration passed: '+fault)
            with self.subTest(fault=fault):
                self.assertTrue(negative.applied)
                validate_negative_result(result,fault)

    def test_no_generic_failure_credits_control(self):
        for fault in FAULTS:
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                validate_negative_result(dict(passed=False,failures=['matrix control incomplete']),fault)


if __name__=='__main__':unittest.main()
