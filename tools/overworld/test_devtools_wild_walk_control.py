"""Paused calibration through actual Wild reader and shared native hook fixture."""
from pathlib import Path
import unittest

from tools.overworld import test_devtools_wild_walk_observer as observer_fixture
from tools.overworld.devtools_wild_walk_control import calibrate_wild_walk_clear, WildWalkControlError


class WildWalkControlTests(unittest.TestCase):
    def fixture(self, *, real_clear=True):
        test=observer_fixture.WildWalkObserverTests()
        reader,s,actor,engine,regs,put,calls,memory=test.fixture()
        reader.arm()
        for i in range(16):
            if not hasattr(regs,"r"+str(i)):setattr(regs,"r"+str(i),0)
        regs.cpsr=0x1F;regs.spsr=0x13
        s.native_bridge_active=False
        s.directory=Path("/tmp/ow-wild-control-host-fixture")
        s.rom=s.directory/"test.nds"
        active=0x0229000A
        original_read=s.read
        s.read=lambda address,size:bytes((memory[active],)) if address==active and size==1 else original_read(address,size)
        writes=[];aborts=[]
        def write(address,value):
            if address!=active or len(value)!=1:raise AssertionError("unexpected guest write")
            writes.append((address,bytes(value)));memory[address]=value[0]
        s.write=write
        s.abort_native_control=lambda error:aborts.append(str(error))
        if real_clear:
            test.invoke(reader,0x02300000)
            memory[active]=memory[0x022903D6]=0;memory[engine["pointer"]]=1
            test.invoke(reader,regs.lr & ~1)
        return reader,s,actor,regs,memory,writes,aborts

    def test_exact_fault_restore_without_advance(self):
        r,s,a,regs,memory,writes,aborts=self.fixture()
        before=vars(regs).copy();clock=r.observer._clock();frame=s.completed_frames
        receipt=calibrate_wild_walk_clear(r)
        self.assertEqual(receipt["state"],"complete")
        self.assertEqual(receipt["clean"],receipt["restored"])
        self.assertEqual(receipt["bad"]["active"],1)
        self.assertEqual(writes,[(0x0229000A,b"\1"),(0x0229000A,b"\0")])
        self.assertEqual(vars(regs),before)
        self.assertEqual(r.observer._clock(),clock);self.assertEqual(s.completed_frames,frame)
        self.assertEqual(receipt["guestInstructionAdvance"],0)
        self.assertFalse(receipt["cleanupPending"]);self.assertEqual(aborts,[])
        with self.assertRaises(WildWalkControlError):calibrate_wild_walk_clear(r)
        r.close()

    def test_real_clear_required_and_wrong_session_rejected_before_write(self):
        for fault in ("no-clear","source-rom","external-rom","bridge-active","closed"):
            r,s,a,regs,memory,writes,aborts=self.fixture(real_clear=fault!="no-clear")
            if fault=="source-rom":s.rom=s.rt.REPO/"test.nds"
            elif fault=="external-rom":s.rom=Path("/tmp/not-this-session/test.nds")
            elif fault=="bridge-active":s.native_bridge_active=True
            elif fault=="closed":r.close()
            with self.subTest(fault=fault),self.assertRaises(WildWalkControlError):calibrate_wild_walk_clear(r)
            self.assertEqual(writes,[]);r.close()

    def test_wrong_checker_rejected_but_byte_restored(self):
        r,s,a,regs,memory,writes,aborts=self.fixture()
        with self.assertRaisesRegex(WildWalkControlError,"accepted uncleared"):
            calibrate_wild_walk_clear(r,checker=lambda _:True)
        self.assertEqual(memory[0x0229000A],0)
        self.assertFalse(r.clear_calibration["cleanupPending"])
        self.assertEqual(r.clear_calibration["state"],"failed");r.close()

    def test_noop_or_wrong_owner_clear_cannot_calibrate(self):
        for fault in ("no-op","other-mode","other-owner"):
            r,s,a,regs,memory,writes,aborts=self.fixture()
            if fault=="no-op":r.latest_clear["before"]["active"]=0
            elif fault=="other-mode":r.latest_clear["before"]["mode"]=2
            else:r.latest_clear["after"]["current"]["runtimePointer"]+=4
            with self.subTest(fault=fault),self.assertRaisesRegex(WildWalkControlError,"matching real Walk clear"):
                calibrate_wild_walk_clear(r)
            self.assertEqual(writes,[]);r.close()

    def test_failure_to_restore_aborts_owned_core(self):
        r,s,a,regs,memory,writes,aborts=self.fixture()
        original=s.write
        def write(address,value):
            if value==b"\0":raise OSError("restore failed")
            original(address,value)
        s.write=write
        with self.assertRaisesRegex(WildWalkControlError,"restore failed"):calibrate_wild_walk_clear(r)
        self.assertTrue(aborts);self.assertTrue(r.clear_calibration["cleanupPending"])
        self.assertEqual(memory[0x0229000A],1);r.close()

    def test_changed_execution_boundary_or_owner_aborts(self):
        for fault in ("native-clock","completed-clock","register","owner"):
            r,s,a,regs,memory,writes,aborts=self.fixture()
            original=s.write
            def write(address,value):
                original(address,value)
                if value==b"\1":
                    if fault=="native-clock":s.rt.EXECUTED_FRAME_COUNT+=1
                    elif fault=="completed-clock":s.completed_frames+=1
                    elif fault=="register":regs.r7+=1
                    else:a["subjectIdentity"]+=1
            s.write=write
            with self.subTest(fault=fault),self.assertRaises(Exception):calibrate_wild_walk_clear(r)
            self.assertTrue(aborts);self.assertEqual(memory[0x0229000A],0)
            self.assertEqual(r.clear_calibration["state"],"failed");r.close()

    def test_no_fault_observed_fails_and_restores(self):
        r,s,a,regs,memory,writes,aborts=self.fixture()
        original=s.write
        s.write=lambda address,value:original(address,b"\0")
        with self.assertRaisesRegex(WildWalkControlError,"only the active-byte fault"):calibrate_wild_walk_clear(r)
        self.assertEqual(memory[0x0229000A],0)
        self.assertEqual(r.clear_calibration["state"],"failed");r.close()


if __name__=="__main__":unittest.main()
