"""Known-bad memory through the real corner reader; host tests, not ROM proof."""
from copy import deepcopy
from pathlib import Path
import unittest

from tools.overworld.devtools_corner_control import calibrate_corner_policy, CornerControlError
from tools.overworld.devtools_corner_observer import check_corner_policy
from tools.overworld.devtools_mount_walk_fixture import STATE_BYTES
from tools.overworld.devtools_observer import NativeObservationError
from tools.overworld import test_devtools_corner_observer as native_fixture


class CornerControlTests(unittest.TestCase):
    def fixture(self):
        helper = native_fixture.CornerTests()
        reader,s,actor,regs,put = helper.fixture()
        s.prepared = True
        actor["reservationId"] = 0
        s.native_bridge_active = False
        s.directory = Path("/tmp/corner-policy-private-fixture")
        s.rom = s.directory / "session.nds"
        for i in range(16):
            if not hasattr(regs,"r"+str(i)):
                setattr(regs,"r"+str(i),i)
        regs.cpsr,regs.spsr = 32,0
        reader.arm()
        helper.strict(reader,regs)
        regs.sp -= 16
        regs.r0,regs.r1,regs.r2 = reader.owner["avatarPointer"],reader.owner["playerPointer"],0
        regs.lr = 0x02010101
        helper.invoke(reader,"stockCollision")
        regs.r0=1;helper.invoke(reader,0x02010100)
        regs.sp += 16;regs.r0=2 if reader.return_kind == "candidate-flags" else 0
        helper.invoke(reader,0x02010000)
        s.completed_frames += 1
        s._selector_observation = lambda: dict(heldKeys=0,newKeys=0,rawHeld=0,rawNew=0,simulatedKeys=0)
        reader.completed_boundary()
        writes = []
        def write(address,data):
            self.assertEqual(address,reader.mount_state+27)
            self.assertEqual(len(data),1)
            writes.append(bytes(data));put(address,data)
        s.write = write
        s.fatals = []
        s.abort_native_control = lambda error: s.fatals.append(str(error))
        return reader,s,actor,regs,put,writes

    def test_same_native_read_rejects_bad_policy_and_restores(self):
        r,s,a,regs,put,writes = self.fixture()
        original = s.read(r.mount_state,STATE_BYTES)
        result = calibrate_corner_policy(r)
        self.assertEqual(result["state"],"complete")
        self.assertEqual(result["clean"],result["restored"])
        self.assertEqual(result["bad"]["policy"]["profile19"],0)
        self.assertTrue(check_corner_policy(result["clean"]["policy"]))
        with self.assertRaisesRegex(ValueError,"direction profile"):
            check_corner_policy(result["bad"]["policy"])
        self.assertEqual(writes,[b"\0",b"\1"])
        self.assertEqual(s.read(r.mount_state,STATE_BYTES),original)
        self.assertEqual(result["clock"],result["restoredClock"])
        self.assertEqual(result["registers"],result["restoredRegisters"])
        self.assertFalse(result["cleanupPending"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(r.result()["guestMemoryWrites"],2)
        self.assertEqual(r.result()["policyCalibration"],result)
        with self.assertRaises(CornerControlError):
            calibrate_corner_policy(r)
        self.assertIsNone(r.close()["failure"])
        self.assertEqual(s.fatals,[])

    def test_calibrated_reader_cannot_resume_gameplay(self):
        r,s,a,regs,put,writes = self.fixture()
        calibrate_corner_policy(r)
        with self.assertRaisesRegex(NativeObservationError,"cannot resume gameplay"):
            r.completed_boundary()
        r.close()

    def test_bad_checker_or_unrelated_reader_change_still_restores(self):
        for fault in ("checker","reader"):
            r,s,a,regs,put,writes = self.fixture()
            kwargs = {}
            if fault == "checker":
                kwargs["checker"] = lambda value: True
            else:
                original = r._read_policy
                def read(current):
                    value = original(current)
                    if value["profile19"] == 0:
                        value["profileHex"] = "00"*72
                    return value
                r._read_policy = read
            with self.subTest(fault=fault),self.assertRaises(CornerControlError):
                calibrate_corner_policy(r,**kwargs)
            self.assertEqual(s.read(r.mount_state+27,1),b"\1")
            self.assertFalse(r.policy_calibration["cleanupPending"])
            self.assertEqual(s.fatals,[])
            r.close()

    def test_restore_owner_clock_register_and_unrelated_byte_failures_abort(self):
        for fault in ("restore","owner","clock","register","other-byte"):
            r,s,a,regs,put,writes = self.fixture()
            original = s.write
            def write(address,data):
                if len(writes) == 1 and fault == "restore":
                    raise RuntimeError("restore blocked")
                original(address,data)
                if len(writes) == 1:
                    if fault == "owner":a["authorityGeneration"] += 1
                    elif fault == "clock":s.rt.EXECUTED_FRAME_COUNT += 1
                    elif fault == "register":regs.r4 += 1
                    elif fault == "other-byte":put(r.mount_state+STATE_BYTES-1,b"\xff")
            s.write = write
            with self.subTest(fault=fault),self.assertRaises(Exception):
                calibrate_corner_policy(r)
            self.assertEqual(len(s.fatals),1)
            self.assertTrue(r.policy_calibration["cleanupPending"])
            if fault != "restore":self.assertEqual(s.read(r.mount_state+27,1),b"\1")
            r.close()

    def test_missing_real_call_wrong_boundary_input_and_source_do_not_write(self):
        for fault in ("call","boundary","input","source","bridge","profile","code"):
            r,s,a,regs,put,writes = self.fixture()
            if fault == "call":r.receipts.clear()
            elif fault == "boundary":r.latest_completed=None
            elif fault == "input":s._selector_observation=lambda:dict(heldKeys=1)
            elif fault == "source":s.rom=s.rt.REPO/"test.nds"
            elif fault == "bridge":s.native_bridge_active=True
            elif fault == "profile":put(r.mount_state+27,b"\0")
            elif fault == "code":put(r.code["OverworldWalk_StrictDiagonalAllowedBody"][0],b"\xff")
            with self.subTest(fault=fault),self.assertRaises(Exception):
                calibrate_corner_policy(r)
            self.assertEqual(writes,[])
            r.close()

    def test_policy_two_is_restored_exactly(self):
        r,s,a,regs,put,writes = self.fixture()
        put(r.mount_state+27,b"\2")
        raw = bytearray.fromhex(r.receipts[-1]["profileHex"]);raw[19]=2
        r.receipts[-1]["profileHex"]=raw.hex()
        result=calibrate_corner_policy(r)
        self.assertEqual(result["originalHex"],"02")
        self.assertEqual(writes,[b"\0",b"\2"])
        r.close()


if __name__ == "__main__":
    unittest.main()
