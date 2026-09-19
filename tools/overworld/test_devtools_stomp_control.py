"""Stopped host-memory controls through the real native reader; not ROM proof."""
from pathlib import Path
import subprocess
import unittest

from tools.overworld.devtools_stomp_control import calibrate_stomp_policy, StompControlError, BAD_THRESHOLD
from tools.overworld.devtools_mount_walk_fixture import STATE_BYTES
from tools.overworld import test_devtools_stomp_observer as native_fixture


class StompControlTests(unittest.TestCase):
    def test_real_arm_profile_header_anchors_threshold_byte(self):
        root=Path(__file__).resolve().parents[2]
        source='#include "include/overworld_mount.h"\n'
        source+='_Static_assert(sizeof(OverworldWildBehaviorProfileData)==72,"profile size");\n'
        source+='_Static_assert(__builtin_offsetof(OverworldWildBehaviorProfileData,walkStompTime)==70,"threshold");\n'
        source+='_Static_assert(__builtin_offsetof(OverworldMountSnapshot,profile)==0,"owner profile");\n'
        run=subprocess.run(['clang','-target','armv5te-none-eabi','-fsyntax-only','-Wno-unknown-attributes',
            '-Wno-gnu-folding-constant','-I',str(root),'-x','c','-'],input=source,text=True,capture_output=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stderr)

    def fixture(self):
        helper=native_fixture.StompObserverTests()
        reader,s,actor,regs,put=helper.fixture()
        s.prepared=True;s.native_bridge_active=False
        s.directory=Path('/tmp/stomp-control-private-fixture');s.rom=s.directory/'session.nds'
        reader.arm();helper.start(reader,regs,put,0);helper.invoke(reader,0x02010000)
        for i in range(16):
            if not hasattr(regs,'r'+str(i)):setattr(regs,'r'+str(i),i)
        regs.cpsr,regs.spsr=32,0
        actor.update(motionPhase='IDLE',motionKind='NONE',reservationId=0)
        s.completed_frames+=1
        s._selector_observation=lambda:dict(heldKeys=0,newKeys=0,rawHeld=0,rawNew=0,simulatedKeys=0)
        reader.completed_boundary()
        writes=[];aborts=[]
        def write(address,data):
            self.assertEqual(address,reader.mount_state+78)
            self.assertEqual(len(data),1)
            writes.append(bytes(data));put(address,data)
        s.write=write;s.abort_native_control=lambda error:aborts.append(str(error))
        return reader,s,actor,regs,put,writes,aborts

    def test_same_profile_reader_rejects_restores_and_keeps_failure_latched(self):
        r,s,actor,regs,put,writes,aborts=self.fixture()
        original=s.read(r.mount_state,STATE_BYTES)
        result=calibrate_stomp_policy(r)
        self.assertEqual(result['state'],'complete')
        self.assertEqual(result['clean'],result['restored'])
        self.assertEqual(result['clock'],result['restoredClock'])
        self.assertEqual(result['registers'],result['restoredRegisters'])
        self.assertEqual(result['bad']['failure'],BAD_THRESHOLD)
        self.assertEqual(result['readerFailure'],BAD_THRESHOLD)
        self.assertEqual(r.failure,BAD_THRESHOLD)
        self.assertEqual(s.read(r.mount_state,STATE_BYTES),original)
        self.assertEqual(writes,[b'\xff',b'\x02'])
        self.assertEqual(result['guestMemoryWrites'],2)
        self.assertEqual(r.result()['guestMemoryWrites'],2)
        self.assertEqual(r.result()['calibration'],result)
        self.assertEqual(result['guestInstructionAdvance'],0)
        self.assertFalse(result['acceptedProof']);self.assertFalse(result['cleanupPending'])
        self.assertTrue(result['readerClosed']);self.assertTrue(r.closed)
        self.assertEqual(r.observer.hooks.callbacks,{})
        self.assertEqual(r.close(),r.result())
        self.assertEqual(aborts,[])
        with self.assertRaises(StompControlError):calibrate_stomp_policy(r)

    def test_missing_call_boundary_owner_input_or_private_session_cannot_write(self):
        for fault in ('call','pending','boundary','busy','input','private','bridge','bad-profile','code'):
            r,s,actor,regs,put,writes,aborts=self.fixture()
            if fault=='call':r.latest=None
            elif fault=='pending':r.active.append({})
            elif fault=='boundary':r.latest_completed_pose=None
            elif fault=='busy':actor['reservationId']=1
            elif fault=='input':s._selector_observation=lambda:dict(heldKeys=1)
            elif fault=='private':s.rom=s.rt.REPO/'test.nds'
            elif fault=='bridge':s.native_bridge_active=True
            elif fault=='bad-profile':put(r.mount_state+78,b'\xff')
            else:put(r.code['policy'][0],b'\xff')
            with self.subTest(fault=fault),self.assertRaises(Exception):calibrate_stomp_policy(r)
            self.assertEqual(writes,[])
            r.close()

    def test_unexpected_reader_error_or_acceptance_still_restores_and_closes(self):
        for fault in ('accepted','error'):
            r,s,actor,regs,put,writes,aborts=self.fixture()
            original=r._read_profile
            def read(current):
                if s.read(r.mount_state+78,1)==b'\xff':
                    if fault=='error':raise RuntimeError('unexpected profile read error')
                    return dict(profileHex=s.read(r.mount_state+8,72).hex(),stompTime=255)
                return original(current)
            r._read_profile=read
            with self.subTest(fault=fault),self.assertRaises(Exception):calibrate_stomp_policy(r)
            self.assertEqual(s.read(r.mount_state+78,1),b'\x02')
            self.assertEqual(writes,[b'\xff',b'\x02'])
            self.assertFalse(r.calibration['cleanupPending'])
            self.assertTrue(r.closed);self.assertEqual(aborts,[])

    def test_latched_reader_error_cannot_hide_hook_cleanup_failure(self):
        r,s,actor,regs,put,writes,aborts=self.fixture()
        target=r.entries[0]
        remove=r.observer.hooks.remove
        def fail_one(token):
            if token==target:raise RuntimeError('hook cleanup blocked')
            return remove(token)
        r.observer.hooks.remove=fail_one
        with self.assertRaisesRegex(StompControlError,'terminal reader cleanup'):
            calibrate_stomp_policy(r)
        self.assertEqual(writes,[b'\xff',b'\x02'])
        self.assertEqual(r.failure,BAD_THRESHOLD)
        self.assertTrue(r.calibration['cleanupPending'])
        self.assertEqual(r.calibration['state'],'failed')
        self.assertEqual(len(aborts),1)
        r.observer.hooks.remove=remove
        remove(target)

    def test_restore_failure_or_unrelated_change_aborts_without_clearing_latch(self):
        for fault in ('restore','owner','clock','register','other-byte','input','pose'):
            r,s,actor,regs,put,writes,aborts=self.fixture()
            write=s.write
            def corrupt(address,data):
                if len(writes)==1 and fault=='restore':raise RuntimeError('restore blocked')
                write(address,data)
                if len(writes)==1:
                    if fault=='owner':actor['authorityGeneration']+=1
                    elif fault=='clock':s.rt.EXECUTED_FRAME_COUNT+=1
                    elif fault=='register':regs.r4+=1
                    elif fault=='other-byte':put(r.mount_state+183,b'\xff')
                    elif fault=='input':s._selector_observation=lambda:dict(heldKeys=1)
                    elif fault=='pose':
                        original=s.rt.object_state
                        s.rt.object_state=lambda *args:dict(original(*args),pos_x=123)
            s.write=corrupt
            with self.subTest(fault=fault),self.assertRaises(Exception):calibrate_stomp_policy(r)
            self.assertEqual(len(aborts),1)
            self.assertTrue(r.calibration['cleanupPending'])
            self.assertTrue(r.closed)
            if fault!='restore':self.assertEqual(s.read(r.mount_state+78,1),b'\x02')
            # An unrelated-byte fault is caught before the bad profile read.
            if fault!='other-byte':self.assertIsNotNone(r.failure)


if __name__=='__main__':unittest.main()
