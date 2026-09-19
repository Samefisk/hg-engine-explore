"""Host memory faults through the actual pair reader and production checker."""
from pathlib import Path
import unittest

from tools.overworld import test_devtools_mount_pacing_observer as pose_fixture
from tools.overworld.devtools_mount_pacing_control import calibrate_mounted_pose, MountedPoseControlError


class MountedPoseControlTests(unittest.TestCase):
    def fixture(self):
        r,s,a,e,regs,put,calls,poses=pose_fixture.MountPacingTests().fixture()
        s.native_bridge_active=False
        s.directory=Path('/tmp/mounted-pose-private-fixture')
        s.rom=s.directory/'session.nds'
        for i in range(16):setattr(regs,'r'+str(i),i)
        regs.cpsr=32;regs.spsr=0
        for pose in poses.values():
            pose.update({prefix+axis:0 for prefix in ('face_','unk88_','unk94_') for axis in 'xyz'})
            pose['facing']=3
        poses[s.rt.player_ptr(s.emu)]['face_y']=32768
        poses[s.rt.player_ptr(s.emu)]['face_x']=-32768
        address=e['pointer']+0x70
        old_read=s.read
        s.read=lambda at,size: poses[e['pointer']]['pos_x'].to_bytes(4,'little',signed=True) if at==address and size==4 else old_read(at,size)
        writes=[]
        def write(at,data):
            self.assertEqual(at,address);self.assertEqual(len(data),4)
            writes.append(bytes(data))
            poses[e['pointer']]['pos_x']=int.from_bytes(data,'little',signed=True)
        s.write=write
        s.fatals=[]
        def abort(error):s.fatals.append(str(error))
        s.abort_native_control=abort
        r.arm()
        return r,s,a,e,regs,poses,writes

    def test_actual_reader_bad_position_rejected_and_exactly_restored(self):
        r,s,a,e,regs,poses,writes=self.fixture()
        receipt=calibrate_mounted_pose(r)
        self.assertEqual(receipt['state'],'complete')
        self.assertEqual(receipt['clean'],receipt['restored'])
        self.assertEqual(receipt['bad']['mount']['pos_x'],101)
        self.assertEqual(receipt['clean']['mount']['pos_x'],100)
        self.assertEqual(receipt['clock'],receipt['restoredClock'])
        self.assertFalse(receipt['acceptedProof']);self.assertFalse(receipt['cleanupPending'])
        self.assertEqual(writes,[bytes((101,0,0,0)),bytes((100,0,0,0))])
        self.assertEqual(s.fatals,[])
        self.assertEqual(r.result()['guestMemoryWrites'],2)
        self.assertEqual(r.result()['poseCalibration']['state'],'complete')
        self.assertEqual(len(r.observer.pending),0)
        with self.assertRaises(MountedPoseControlError):calibrate_mounted_pose(r)
        r.close()

    def test_bad_checker_or_reader_still_restores(self):
        for fault in ('checker','reader'):
            r,s,a,e,regs,poses,writes=self.fixture()
            kwargs={}
            if fault=='checker':kwargs['checker']=lambda data:True
            else:
                actual=r._read_pose
                def read(current):
                    value=actual(current)
                    if value['mount']['pos_x']==101:value['player']['pos_z']+=1
                    return value
                r._read_pose=read
            with self.subTest(fault=fault),self.assertRaises(MountedPoseControlError):
                calibrate_mounted_pose(r,**kwargs)
            self.assertEqual(poses[e['pointer']]['pos_x'],100)
            self.assertFalse(r.pose_calibration['cleanupPending'])
            self.assertEqual(s.fatals,[])
            r.close()

    def test_restore_clock_register_and_owner_failures_abort(self):
        for fault in ('restore','clock','register','owner'):
            r,s,a,e,regs,poses,writes=self.fixture()
            actual=s.write
            def write(at,data):
                if len(writes)==1 and fault=='restore':raise RuntimeError('restore blocked')
                actual(at,data)
                if len(writes)==1:
                    if fault=='clock':s.rt.EXECUTED_FRAME_COUNT+=1
                    elif fault=='register':regs.r3+=1
                    elif fault=='owner':a['authorityGeneration']+=1
            s.write=write
            with self.subTest(fault=fault),self.assertRaises(Exception):calibrate_mounted_pose(r)
            self.assertEqual(len(s.fatals),1)
            self.assertTrue(r.pose_calibration['cleanupPending'])
            if fault!='restore':self.assertEqual(poses[e['pointer']]['pos_x'],100)
            r.close()

    def test_wrong_session_and_unclean_pose_do_not_write(self):
        for fault in ('bridge','source','pose'):
            r,s,a,e,regs,poses,writes=self.fixture()
            if fault=='bridge':s.native_bridge_active=True
            elif fault=='source':s.rom=s.rt.REPO/'test.nds'
            else:poses[e['pointer']]['pos_x']+=1
            with self.subTest(fault=fault),self.assertRaises((MountedPoseControlError,ValueError)):
                calibrate_mounted_pose(r)
            self.assertEqual(writes,[])
            r.close()


if __name__=='__main__':unittest.main()
