"""Host-only stopped-reader controls; these fixtures are not game proof."""
import unittest

from tools.overworld.devtools_walk_matrix_control import calibrate_walk_matrix, BAD_ENUM
from tools.overworld import test_devtools_walk_matrix_observer as fixture_module

motion=fixture_module.motion


class WalkMatrixControlTests(unittest.TestCase):
    def fixture(self):
        helper=fixture_module.WalkMatrixTests()
        r,s,actor,regs,put=helper.fixture()
        helper.start(r,regs);helper.finish_tick(r,regs,put)
        put(r.motion_pointer,motion(1,1,0))
        actor.update(motionKind='NONE',motionPhase='IDLE',reservationId=0)
        s.completed_frames+=1
        s._selector_observation=lambda:dict(heldKeys=0,newKeys=0,rawHeld=0,rawNew=0,simulatedKeys=0)
        s.prepared=True
        for name in (*('r'+str(i) for i in range(16)),'cpsr','spsr'):
            if not hasattr(regs,name):setattr(regs,name,0)
        writes=[];aborts=[]
        def write(address,data):
            writes.append((address,data));put(address,data)
        s.write=write;s.abort_native_control=aborts.append
        r.completed_boundary()
        return r,s,actor,regs,put,writes,aborts

    def test_same_reader_rejects_then_restores_without_new_tick(self):
        r,s,actor,regs,put,writes,aborts=self.fixture()
        pending=list(r.observer.pending)
        result=calibrate_walk_matrix(r)
        self.assertEqual(result['state'],'complete')
        self.assertEqual(result['bad']['failure'],BAD_ENUM)
        self.assertEqual(result['clean'],result['restored'])
        self.assertEqual(result['clock'],result['restoredClock'])
        self.assertEqual(result['registers'],result['restoredRegisters'])
        self.assertEqual(writes,[(r.motion_pointer+48,b'\xff'),(r.motion_pointer+48,b'\x00')])
        self.assertEqual(result['guestMemoryWrites'],2)
        self.assertFalse(result['acceptedProof'])
        self.assertEqual(result['guestInstructionAdvance'],0)
        self.assertEqual(list(r.observer.pending),pending)
        self.assertEqual(aborts,[])
        self.assertEqual(r.result()['calibration'],result)
        with self.assertRaisesRegex(RuntimeError,'owned paused reader'):
            calibrate_walk_matrix(r)
        r.close()

    def test_missing_preconditions_do_not_write(self):
        for fault in ('tick','boundary','input','idle','private','bridge','epoch','code'):
            r,s,actor,regs,put,writes,aborts=self.fixture()
            if fault=='tick':r.last_moving_tick=None
            elif fault=='boundary':r.latest_completed=None
            elif fault=='input':s._selector_observation=lambda:dict(heldKeys=1,newKeys=0,rawHeld=0,rawNew=0,simulatedKeys=0)
            elif fault=='idle':put(r.motion_pointer,motion(1,1,2))
            elif fault=='private':s.rom=s.rt.REPO/'test.nds'
            elif fault=='bridge':s.native_bridge_active=True
            elif fault=='epoch':r.last_moving_tick['fieldEpoch']+=1
            else:put(r.code[0]+40,b'\xff')
            with self.subTest(fault=fault),self.assertRaises(Exception):calibrate_walk_matrix(r)
            self.assertEqual(writes,[])
            r.close()

    def test_reader_that_accepts_invalid_phase_fails_and_restores(self):
        r,s,actor,regs,put,writes,aborts=self.fixture()
        read=r._read_motion
        good=read(r.motion_pointer)
        r._read_motion=lambda pointer:good if s.read(pointer+48,1)==b'\xff' else read(pointer)
        with self.assertRaisesRegex(RuntimeError,'did not reject'):calibrate_walk_matrix(r)
        self.assertEqual(s.read(r.motion_pointer,52),motion(1,1,0))
        self.assertFalse(r.calibration['cleanupPending'])
        self.assertEqual(aborts,[])
        r.close()

    def test_owner_clock_register_or_unrelated_byte_changes_fail_closed(self):
        for fault in ('owner','clock','register','unrelated','restore'):
            r,s,actor,regs,put,writes,aborts=self.fixture()
            write=s.write
            def changed(address,data):
                if fault=='restore' and data==b'\x00':raise RuntimeError('restore failed')
                write(address,data)
                if data==b'\xff':
                    if fault=='owner':actor['authorityGeneration']+=1
                    elif fault=='clock':s.rt.EXECUTED_FRAME_COUNT+=1
                    elif fault=='register':regs.r7+=1
                    elif fault=='unrelated':put(r.motion_pointer+7,b'\x77')
            s.write=changed
            with self.subTest(fault=fault),self.assertRaises(Exception):calibrate_walk_matrix(r)
            self.assertEqual(r.calibration['state'],'failed')
            self.assertTrue(aborts)
            self.assertTrue(r.calibration['cleanupPending'])
            if fault!='restore':self.assertEqual(s.read(r.motion_pointer+48,1),b'\x00')
            r.close()


if __name__=='__main__':unittest.main()
