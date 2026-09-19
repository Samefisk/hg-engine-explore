"""Same mounted _sample controls on host memory; no accepted ROM evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import unittest

from tools.overworld.devtools_mounted_crash_control import (
    calibrate_mounted_crash, MountedCrashControlError, BAD_MODE, EXPECTED_COUNTS)
from tools.overworld.devtools_mounted_crash_observer import MODE_OFFSET, STATE_BYTES
from tools.overworld import test_devtools_mounted_crash_observer as native_fixture
from tools.overworld import test_devtools_mounted_crash_measurement as retained_fixture


class MountedCrashControlTests(unittest.TestCase):
    def test_actual_arm_header_proves_mode_offset_and_full_state_size(self):
        native_fixture.MountedCrashObserverTests().test_header_offsets_are_current_arm_layout()
        self.assertEqual((MODE_OFFSET,STATE_BYTES),(102,184))

    def fixture(self):
        r,s,actor,regs,put=native_fixture.MountedCrashObserverTests().fixture()
        s.prepared=True;s.crash_calibrated=True;s.native_bridge_active=False
        s.directory=Path('/tmp/crash-control-private-fixture');s.rom=s.directory/'session.nds'
        s.emu.guest_clock=lambda:dict(version=1,running=False,arm9Timestamp=100,
            arm7Timestamp=50,frameSequence=30,scope='nds-scheduler-ticks-not-cpu-or-instructions')
        actor.update(logical=dict(x=1,y=2),reservationId=0)
        r.arm()
        put(r.mount_state+102,b'\x03');put(r.mount_state+144,struct.pack('<HH',32,32))
        value=r._entry('update')
        put(r.mount_state+102,b'\0');put(r.mount_state+144,b'\0'*4)
        r._returned(value,dict(returnValue=1,returned=r.observer._clock()))
        r.counts.update(EXPECTED_COUNTS)
        actor['commitSequence']+=1;actor['logical']['x']+=1
        poses=s.rt.object_state
        s.rt.object_state=lambda *args:dict(poses(*args),x=2,pos_x=65636)
        s.completed_frames+=1
        s._selector_observation=lambda:dict(heldKeys=0,newKeys=0,rawHeld=0,rawNew=0,simulatedKeys=0)
        for i in range(16):
            if not hasattr(regs,'r'+str(i)):setattr(regs,'r'+str(i),i)
        regs.cpsr,regs.spsr=32,0
        r.completed_boundary()
        writes=[];aborts=[]
        def write(address,data):
            self.assertEqual(address,r.mount_state+102);self.assertEqual(len(data),1)
            writes.append(bytes(data));put(address,data)
        s.write=write;s.abort_native_control=lambda error:aborts.append(str(error))
        return r,s,actor,regs,put,writes,aborts

    def test_same_sample_rejects_mode_restores_everything_and_keeps_latch(self):
        r,s,a,regs,put,writes,aborts=self.fixture();original=s.read(r.mount_state,184)
        result=calibrate_mounted_crash(r)
        self.assertEqual(result['state'],'complete')
        self.assertEqual(result['bad']['failure'],BAD_MODE)
        self.assertEqual(result['clean'],result['restored'])
        self.assertEqual(result['clock'],result['restoredClock'])
        self.assertEqual(result['registers'],result['restoredRegisters'])
        self.assertEqual(s.read(r.mount_state,184),original)
        self.assertEqual(writes,[b'\xff',b'\0'])
        self.assertEqual(result['guestMemoryWrites'],2)
        self.assertEqual(result['guestInstructionAdvance'],0)
        self.assertEqual(r.failure,BAD_MODE)
        self.assertTrue(result['readerClosed']);self.assertFalse(result['cleanupPending'])
        self.assertFalse(result['acceptedProof']);self.assertEqual(aborts,[])
        self.assertEqual(r.observer.hooks.callbacks,{})
        self.assertEqual(r.result()['calibration'],result)
        self.assertEqual(r.result()['guestMemoryWrites'],2)
        with self.assertRaises(MountedCrashControlError):calibrate_mounted_crash(r)

    def test_retained_completed_public_subject_has_no_movement_policy(self):
        raw=retained_fixture.PATH.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),retained_fixture.SHA)
        saved=next(s for s in json.loads(raw)['snapshots'] if s['frame']==847)
        public=saved['crashFeedback']['latestCompleted']['current']['publicSubject']
        self.assertNotIn('movementPolicy',public)
        for key,value in dict(species=155,role='MOUNTED',active=True,presentationAttached=True,
                inputOwnership=1,motionPhase='IDLE',motionKind='NONE',reservationId=0).items():
            self.assertEqual(public[key],value,key)
        r,s,a,regs,put,writes,aborts=self.fixture()
        self.assertNotIn('movementPolicy',a)
        self.assertLessEqual(set(a),set(public))
        self.assertEqual(calibrate_mounted_crash(r)['state'],'complete')
        self.assertEqual(writes,[b'\xff',b'\0'])

    def test_bad_preconditions_do_not_write(self):
        for fault in ('guard','call','counts','pending','boundary','busy','input','private','running','bridge','recovery','code'):
            r,s,a,regs,put,writes,aborts=self.fixture()
            if fault=='guard':s.crash_calibrated=False
            elif fault=='call':r.latest=None
            elif fault=='counts':r.counts['presentation']=31
            elif fault=='pending':r.active.append({})
            elif fault=='boundary':r.latest_completed=None
            elif fault=='busy':a['reservationId']=1
            elif fault=='input':s._selector_observation=lambda:dict(heldKeys=1)
            elif fault=='private':s.rom=s.rt.REPO/'test.nds'
            elif fault=='running':s.emu.guest_clock=lambda:dict(version=1,running=True)
            elif fault=='bridge':s.native_bridge_active=True
            elif fault=='recovery':a['commitSequence']-=1
            else:put(r.code['start'][0],b'\xff')
            with self.subTest(fault=fault),self.assertRaises(Exception):calibrate_mounted_crash(r)
            self.assertEqual(writes,[]);r.close()

    def test_idle_duration_is_not_the_injected_fault(self):
        r,s,a,regs,put,writes,aborts=self.fixture()
        put(r.mount_state+144,struct.pack('<H',65535))
        self.assertEqual(r._sample()['duration'],65535) # Existing reader permits it outside mode3.
        with self.assertRaises(MountedCrashControlError):calibrate_mounted_crash(r)
        self.assertEqual(writes,[])

    def test_unexpected_reader_error_or_acceptance_still_restores(self):
        for fault in ('error','accept'):
            r,s,a,regs,put,writes,aborts=self.fixture();original=r._sample;clean=original()
            def sample():
                if s.read(r.mount_state+102,1)==b'\xff':
                    if fault=='error':raise RuntimeError('unexpected sample failure')
                    return deepcopy(clean)
                return original()
            r._sample=sample
            with self.subTest(fault=fault),self.assertRaises(Exception):calibrate_mounted_crash(r)
            self.assertEqual(writes,[b'\xff',b'\0'])
            self.assertFalse(r.calibration['cleanupPending']);self.assertTrue(r.closed)
            self.assertEqual(aborts,[])

    def test_restore_failures_abort_and_do_not_clear_reader_failure(self):
        for fault in ('restore','byte','identity','clock','register','input','pose'):
            r,s,a,regs,put,writes,aborts=self.fixture();write=s.write
            def corrupt(address,data):
                if len(writes)==1 and fault=='restore':raise RuntimeError('restore blocked')
                write(address,data)
                if len(writes)==1:
                    if fault=='byte':put(r.mount_state+183,b'\xff')
                    elif fault=='identity':a['authorityGeneration']+=1
                    elif fault=='clock':s.rt.EXECUTED_FRAME_COUNT+=1
                    elif fault=='register':regs.r4+=1
                    elif fault=='input':s._selector_observation=lambda:dict(heldKeys=1)
                    elif fault=='pose':
                        prior=s.rt.object_state;s.rt.object_state=lambda *args:dict(prior(*args),pos_x=5)
            s.write=corrupt
            with self.subTest(fault=fault),self.assertRaises(Exception):calibrate_mounted_crash(r)
            self.assertEqual(len(aborts),1)
            self.assertTrue(r.calibration['cleanupPending']);self.assertTrue(r.closed)
            if fault!='restore':self.assertEqual(s.read(r.mount_state+102,1),b'\0')
            if fault!='byte':self.assertIsNotNone(r.failure,fault)

    def test_hook_cleanup_failure_is_not_hidden_by_expected_reader_latch(self):
        r,s,a,regs,put,writes,aborts=self.fixture();token=r.entries[0]
        remove=r.observer.hooks.remove
        def blocked(value):
            if value==token:raise RuntimeError('cleanup blocked')
            return remove(value)
        r.observer.hooks.remove=blocked
        with self.assertRaisesRegex(MountedCrashControlError,'terminal reader cleanup'):calibrate_mounted_crash(r)
        self.assertEqual(writes,[b'\xff',b'\0']);self.assertEqual(r.failure,BAD_MODE)
        self.assertEqual(len(aborts),1);self.assertTrue(r.calibration['cleanupPending'])
        r.observer.hooks.remove=remove;remove(token)


if __name__=='__main__':unittest.main()
