"""Natural getter receipt freshness, using the installed entry/return callbacks."""
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.overworld import devtools_runtime as runtime
from tools.overworld.devtools_engine import SUBSTRUCT_OFFSETS


def record(*, personality=123, species=155, hp=0, max_hp=20):
    box, party = bytearray(128), bytearray(100)
    a, _, _, _ = SUBSTRUCT_OFFSETS[(personality & 0x3E000) >> 13]
    struct.pack_into("<H", box, a, species)
    checksum = sum(struct.unpack("<64H", box)) & 0xFFFF
    party[4] = 5
    struct.pack_into("<HH", party, 6, hp, max_hp)
    return (struct.pack("<IHH", personality, 0, checksum)
            + runtime._crypt(box, checksum) + runtime._crypt(party, personality))


class Fixture:
    GETTER, RETURN, SAVE = 0x0206E540, 0x02001000, 0x02200000

    def __init__(self):
        self.callbacks, self.records = {}, {}
        self.regs = SimpleNamespace(r0=0, r1=0, sp=0x027E3800, lr=self.RETURN | 1)
        self.emu = SimpleNamespace(memory=SimpleNamespace(
            register_arm9=self.regs, register_exec=self.register))
        self.session = runtime.DevtoolsSession.__new__(runtime.DevtoolsSession)
        self.session.emu = self.emu
        self.session.rt = SimpleNamespace(
            unsigned=lambda emu, address: self.SAVE if address == 0x021D2228 else 0,
            EXECUTED_FRAME_COUNT=100)
        self.session.read = lambda pointer, size: self.records[pointer][:size]
        self.session.target = lambda name: self.GETTER
        self.session.party_offsets = SUBSTRUCT_OFFSETS
        self.session.party_getter_checks = {}
        self.session.native_bridge_active = False
        self.session.completed_frames = 10
        self.session._install_party_getter_checks()

    def register(self, address, callback):
        self.callbacks[address] = callback

    def put(self, slot, data):
        pointer = self.SAVE + 0xA0 + 8 + slot * 236
        self.records[pointer] = data
        return pointer

    def call(self, slot, attr, value):
        self.regs.r0 = self.SAVE + 0xA0 + 8 + slot * 236
        self.regs.r1 = attr
        self.callbacks[self.GETTER](self.GETTER, 2)
        self.regs.r0 = value
        if self.RETURN in self.callbacks:
            self.callbacks[self.RETURN](self.RETURN, 2)
        return self.session.party_getter_checks.get((slot, attr))


class PartyGetterReceiptTests(unittest.TestCase):
    def test_healed_hp_replaces_zero_receipt_and_max_hp_is_observed(self):
        f = Fixture()
        f.put(1, record())
        first = f.call(1, 163, 0)
        f.session.completed_frames, f.session.rt.EXECUTED_FRAME_COUNT = 20, 111
        f.put(1, record(hp=20))
        healed = f.call(1, 163, 20)
        self.assertEqual(healed["native"], 20)
        self.assertEqual(first["native"], 0)
        self.assertEqual((healed["personality"], healed["species"]), (123, 155))
        self.assertEqual((healed["frame"], healed["nativeCycle"]), (21, 111))
        self.assertEqual(healed["decodedAtFrame"], 21)
        self.assertEqual(healed["validation"], "fresh-decode")
        self.assertTrue(healed["passed"])
        maximum = f.call(1, 164, 20)
        self.assertEqual((maximum["field"], maximum["native"]), ("maxHp", 20))
        self.assertIsNone(f.session.party_getter_hooks.error)

    def test_unchanged_record_reuses_decode_but_not_receipt_time(self):
        f = Fixture()
        f.put(1, record(hp=20))
        with patch.object(runtime, "decode_party", wraps=runtime.decode_party) as decode:
            first = f.call(1, 163, 20)
            f.session.completed_frames, f.session.rt.EXECUTED_FRAME_COUNT = 12, 104
            latest = f.call(1, 163, 20)
            f.call(1, 161, 5)
        self.assertEqual(decode.call_count, 1)
        self.assertEqual(first["frame"], 11)
        self.assertEqual((latest["frame"], latest["nativeCycle"]), (13, 104))
        self.assertEqual(latest["decodedAtFrame"], 11)
        self.assertEqual(latest["validation"], "unchanged-record")

    def test_slot_replacement_revalidates_identity_and_drops_old_subject_fields(self):
        f = Fixture()
        f.put(1, record(hp=20))
        with patch.object(runtime, "decode_party", wraps=runtime.decode_party) as decode:
            f.call(1, 5, 155)
            f.call(1, 163, 20)
            f.put(1, record(personality=456, species=56, hp=20))
            latest = f.call(1, 163, 20)
        self.assertEqual(decode.call_count, 2)
        self.assertEqual((latest["personality"], latest["species"]), (456, 56))
        self.assertEqual(latest["validation"], "fresh-decode")
        self.assertNotIn((1, 5), f.session.party_getter_checks)

    def test_native_mismatch_is_failed_even_when_record_matches_cache(self):
        f = Fixture()
        f.put(1, record(hp=20))
        f.call(1, 163, 20)
        failed = f.call(1, 163, 19)
        self.assertFalse(failed["passed"])
        self.assertEqual((failed["native"], failed["decoded"]), (19, 20))
        self.assertIn("differs from native getter", f.session.party_getter_hooks.error)

    def test_changed_record_checksum_failure_is_not_hidden_by_cache(self):
        f = Fixture()
        f.put(1, record(hp=20))
        f.call(1, 163, 20)
        corrupt = bytearray(record(hp=20))
        corrupt[8] ^= 1
        f.put(1, bytes(corrupt))
        f.call(1, 163, 20)
        self.assertIn("checksum differs", f.session.party_getter_hooks.error)

    def test_synthetic_bridge_is_not_natural_evidence(self):
        f = Fixture()
        f.put(1, record())
        f.session.native_bridge_active = True
        self.assertIsNone(f.call(1, 163, 0))
        self.assertEqual(f.session.party_getter_checks, {})

    def test_receipts_are_bounded_to_six_slots_and_four_fields(self):
        f = Fixture()
        for repeat in range(3):
            for slot in range(6):
                f.put(slot, record(personality=slot + 1, hp=repeat))
                for attr, value in ((5, 155), (161, 5), (163, repeat), (164, 20)):
                    f.call(slot, attr, value)
        self.assertEqual(len(f.session.party_getter_checks), 24)
        self.assertIsNone(f.session.party_getter_hooks.error)


if __name__ == "__main__":
    unittest.main()
