"""Copied host controls against the same-reader receipt validator."""
from copy import deepcopy
import unittest

from tools.overworld import test_devtools_walk_matrix_control as fixture_module
from tools.overworld.devtools_walk_matrix_control import calibrate_walk_matrix
from tools.overworld.devtools_walk_matrix_control_measurement import (
    WalkMatrixControlMeasurement, validate_control, moving_summary)


class MatrixControlMeasurementTests(unittest.TestCase):
    def fixture(self):
        r,s,actor,regs,put,writes,aborts=fixture_module.WalkMatrixControlTests().fixture()
        tick=deepcopy(r.observer.pending[-1]);control=calibrate_walk_matrix(r)
        terminal=dict(frame=s.completed_frames,actorFrame=control['clock']['actorFrame'],
            nativeCycle=control['clock']['nativeCycle'],actors=[deepcopy(actor)],
            player=control['clean']['player'])
        terminal['actors'][0]['engineObject']=control['clean']['mount']
        return r,control,tick,terminal

    def test_same_native_reader_receipt_validates(self):
        r,c,t,s=self.fixture()
        validate_control(c,t,s,r.subject,r.motion_pointer)
        self.assertEqual(moving_summary(t),r.last_moving_tick)
        r.close()

    def test_changed_native_fact_or_restoration_is_rejected(self):
        for fault in ('raw','owner','prior','bad','restored','clock','register','address','input','pose','advance'):
            r,c,t,s=self.fixture()
            if fault=='raw':c['clean']['motion']['elapsed']+=1
            elif fault=='owner':c['clean']['current']['subject']['handle']['generation']+=1
            elif fault=='prior':c['priorMovingTick']['entryElapsed']+=1
            elif fault=='bad':c['bad']['failure']='different error'
            elif fault=='restored':c['restored']['motion']['rawHex']='00'*52
            elif fault=='clock':c['restoredClock']['nativeCycle']+=1
            elif fault=='register':c['restoredRegisters']['r7']+=1
            elif fault=='address':c['changedAddress']+=1
            elif fault=='input':c['clean']['input']['heldKeys']=1
            elif fault=='pose':c['clean']['player']['pos_x']+=1
            else:c['guestInstructionAdvance']=1
            with self.subTest(fault=fault),self.assertRaises((ValueError,KeyError)):
                validate_control(c,t,s,r.subject,r.motion_pointer)
            r.close()

    def test_control_requires_baseline_and_no_post_control_gameplay(self):
        meter=WalkMatrixControlMeasurement(100)
        self.assertEqual(meter.case_limit,2)
        with self.assertRaisesRegex(ValueError,'two-case baseline'):meter.calibrate({}, {})
        meter.control={}
        with self.assertRaisesRegex(ValueError,'after calibration'):meter.command({}, {})
        with self.assertRaisesRegex(ValueError,'after calibration'):meter.configure({}, {})
        result=meter.observe({},[])
        self.assertFalse(result['passed'])
        self.assertIn('after calibration',result['failures'][0])

    def test_finish_keeps_exact_missing_baseline_lifecycle(self):
        meter=WalkMatrixControlMeasurement(100)
        meter.natural.current=dict(ticks=[{}],events=[dict(event=name) for name in
            ('MOTION_STARTED','LOGICAL_COMMIT','MOTION_FINISHED')])
        expected=['matrix exact lifecycle missing: CONTROL_RETURNED']
        for _ in range(2):
            result=meter.finish()
            self.assertEqual(result['failures'],expected)
            self.assertEqual(result['natural']['failures'],expected)
            self.assertFalse(result['passed'])
            self.assertFalse(result['acceptedProof'])

    def test_retained_pilot_plus_synthetic_terminal_control_is_host_only(self):
        from tools.overworld.test_devtools_walk_matrix_measurement import pilot
        from tools.overworld.devtools_walk_matrix_observer import decode_motion
        from tools.overworld.devtools_walk_matrix_control import BAD_ENUM
        meter=pilot(meter=WalkMatrixControlMeasurement(100),close=False)
        self.assertTrue(meter.natural.ready,meter.failures)
        terminal=deepcopy(meter.last);tick=meter.last_moving
        actor=next(a for a in terminal['actors'] if a['handle']==meter.subject['handle'])
        # This state and fault receipt are deliberately host-generated, not a
        # retained native calibration. Only the preceding two cases are real.
        raw=bytearray.fromhex(tick['after']['rawHex']);raw[48]=0
        current=deepcopy(tick['afterCurrent']);current['publicSubject']=deepcopy(actor)
        clean=dict(current=current,motion=decode_motion(bytes(raw)),player=terminal['player'],
            mount=actor['engineObject'],input=dict(heldKeys=0,newKeys=0,rawHeld=0,rawNew=0,simulatedKeys=0))
        bad=bytearray(raw);bad[48]=255
        clock={k:terminal[k] for k in ('frame','actorFrame','nativeCycle')}
        regs={k:0 for k in (*('r'+str(i) for i in range(16)),'cpsr','spsr')}
        control=dict(state='complete',failure=None,cleanupPending=False,acceptedProof=False,
            guestInstructionAdvance=0,guestMemoryWrites=2,clean=clean,restored=deepcopy(clean),
            bad=dict(rawHex=bad.hex(),failure=BAD_ENUM),priorMovingTick=moving_summary(tick),
            motionPointer=meter.motion_pointer,stateBytes=52,changedAddress=meter.motion_pointer+48,
            changedOffset=48,originalHex='00',changedHex='ff',clock=clock,restoredClock=deepcopy(clock),
            registers=regs,restoredRegisters=deepcopy(regs))
        # The saved last snapshot includes close; reopening here is host-only.
        reader=dict(terminal['walkMatrix'],closed=False,calibration=control,guestMemoryWrites=2,
            lastMovingTick=moving_summary(tick))
        terminal['walkMatrix']=reader
        receipt=dict(advancedFrames=0,acceptedProof=False,prepared=True,snapshot=terminal,calibration=control)
        meter.calibrate(receipt,terminal)
        close=dict(advancedFrames=0,acceptedProof=False,closed=True,snapshot=terminal,
            walkMatrix=dict(reader,closed=True))
        meter.close(close,terminal)
        result=meter.finish()
        self.assertTrue(result['passed'],result['failures'])
        self.assertFalse(result['acceptedProof'])
        self.assertTrue(result['natural']['prefixOnly'])


if __name__=='__main__':unittest.main()
