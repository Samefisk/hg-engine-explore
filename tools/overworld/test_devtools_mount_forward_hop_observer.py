"""Forward-Hop observation starts only after public mounted ownership."""
from copy import deepcopy
import struct
import unittest

from tools.overworld.devtools_mount_forward_hop_observer import (
    NativeMountForwardHopObserver, STATE_ADDRESS, STATE_BYTES,
)
from tools.overworld.devtools_observer import NativeObservationError
from tools.overworld import test_devtools_role_profile as role_fixture


class MountForwardHopObserverTests(unittest.TestCase):
    def fixture(self, *, mounted=False):
        roles, session, actor, source, engine, regs, put, _ = role_fixture.RoleProfileTests().fixture()
        actor["inputOwnership"] = int(mounted)
        actor["role"] = "MOUNTED" if mounted else "FOLLOWER"
        session.completed_frames = 785
        roles.observer.role_profiles = roles
        code = bytes.fromhex("00bf") * 16
        roles.observer._live_code = lambda address, expected: code
        roles.observer.calls = {"mounted-forward-hop": {"diagnosticCallsDropped": 0}}
        read_unsigned = session.rt.unsigned
        avatar = 0x02280000
        session.rt.unsigned = lambda emu, address, size=4: (
            avatar if address == session.field_pointer() + 0x40
            else read_unsigned(emu, address, size))
        regs.r0, regs.r1, regs.r2, regs.r3 = STATE_ADDRESS, avatar, 0x027E3040, 255
        regs.lr = 0x01FF9D01
        put(regs.sp, struct.pack("<I", 0))
        put(avatar, bytes(0x40))
        state = bytearray(STATE_BYTES)
        struct.pack_into("<I", state, 0, session.field_pointer())
        struct.pack_into("<IHHHHBBBB", state, 88,
                         source["personality"], actor["species"], 33, 3, 4,
                         actor["form"], actor["level"], 1, 0)
        struct.pack_into("<I", state, 104, 7)
        state[108] = 3
        put(STATE_ADDRESS, state)
        reader = NativeMountForwardHopObserver.__new__(NativeMountForwardHopObserver)
        reader.observer, reader.session = roles.observer, session
        reader.count, reader.address, reader.code = 0, 0x01FF9B00, code
        reader.provenance = dict(symbol="Chain_StartForwardHop", address=reader.address,
                                 size=len(code), stateAddress=STATE_ADDRESS,
                                 stateBytes=STATE_BYTES)
        return reader, session, actor, source, engine, regs, put

    def test_native_riding_before_public_sync_has_no_receipt_then_mount_is_observed(self):
        reader, session, actor, source, engine, regs, put = self.fixture()
        native_before = session.read(STATE_ADDRESS, STATE_BYTES)
        public_before = deepcopy(actor)
        self.assertIsNone(reader.before())
        self.assertEqual(reader.count, 0)
        self.assertEqual(actor, public_before)
        self.assertEqual(session.read(STATE_ADDRESS, STATE_BYTES), native_before)
        # The actual next Actor sync publishes role and input together. The
        # same full source/handle now earns a normal mounted return receipt.
        actor.update(role="MOUNTED", inputOwnership=1,
                     authorityGeneration=2, engineAnchorGeneration=2)
        before = reader.before()
        self.assertIsNotNone(before)
        self.assertEqual(reader.count, 1)
        result = reader.after(before, {"returnValue": 0})
        self.assertTrue(result["normalReturn"])
        self.assertTrue(result["diagnosticOnly"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["owner"]["publicSubject"]["handle"], actor["handle"])

    def test_transition_skip_requires_current_identity_and_exact_native_binding(self):
        for fault in ("pid", "engine", "field", "binding", "phase", "generation", "ownership"):
            reader, session, actor, source, engine, regs, put = self.fixture()
            if fault == "pid": source["personality"] += 1
            elif fault == "engine": engine["pointer"] += 4
            elif fault == "field": put(STATE_ADDRESS, struct.pack("<I", session.field_pointer() + 4))
            elif fault == "binding": put(STATE_ADDRESS + 88, struct.pack("<I", source["personality"] + 1))
            elif fault == "phase": put(STATE_ADDRESS + 108, b"\x02")
            elif fault == "generation": put(STATE_ADDRESS + 104, bytes(4))
            else: actor["inputOwnership"] = 1
            with self.subTest(fault=fault), self.assertRaises(NativeObservationError):
                reader.before()
            self.assertEqual(reader.count, 0)

    def test_mounted_entry_stays_strict(self):
        for fault in ("ownership", "absent", "presentation", "pid", "engine", "field", "statearg", "avatararg", "keys", "direction", "code"):
            reader, session, actor, source, engine, regs, put = self.fixture(mounted=True)
            if fault == "ownership": actor["inputOwnership"] = 0
            elif fault == "absent": actor["active"] = False
            elif fault == "presentation": actor["presentationAttached"] = False
            elif fault == "pid": source["personality"] += 1
            elif fault == "engine": engine["pointer"] += 4
            elif fault == "field": put(STATE_ADDRESS, struct.pack("<I", session.field_pointer() + 4))
            elif fault == "statearg": regs.r0 += 4
            elif fault == "avatararg": regs.r1 += 4
            elif fault == "keys": put(regs.sp, struct.pack("<I", 1 << 12))
            elif fault == "direction": regs.r3 = 8
            else: reader.observer._live_code = lambda address, expected: bytes(len(expected))
            with self.subTest(fault=fault), self.assertRaises(NativeObservationError):
                reader.before()

    def test_mounted_return_stays_strict(self):
        for fault in (None, "return", "frame", "role", "pid", "heap", "context", "state"):
            reader, session, actor, source, engine, regs, put = self.fixture(mounted=True)
            before = reader.before()
            if fault == "frame": session.completed_frames += 1
            elif fault == "role": actor.update(role="FOLLOWER", inputOwnership=0)
            elif fault == "pid": source["personality"] += 1
            elif fault == "heap": session.native_heap_generation += 1
            elif fault == "context": actor["handle"]["mapGeneration"] += 1
            elif fault == "state": put(STATE_ADDRESS + 108, b"\x02")
            result = {"returnValue": 3 if fault == "return" else 0}
            if fault is None:
                self.assertTrue(reader.after(before, result)["normalReturn"])
            else:
                with self.subTest(fault=fault), self.assertRaises(NativeObservationError):
                    reader.after(before, result)


if __name__ == "__main__":
    unittest.main()
