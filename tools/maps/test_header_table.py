"""Tests for tools.maps.header_table (no build needed).

Run: python3 -B -m unittest tools.maps.test_header_table
"""

from __future__ import annotations

import re
import struct
import tempfile
import unittest
from pathlib import Path

from . import codecs, header_table as ht, narc

ARM9_SIZE = 0x112000
ROM = ht.REPO / "rom.nds"

# armips output of armips/asm/map_header_expansion.s for MAP_HEADER_COUNT 600 and
# 52 extension headers (recorded with the production armips on a stock arm9).
GOLDEN_STUB = bytes.fromhex("00490847f1fd0f02000000000000000000000000")
GOLDEN_ROUTINE_600_52 = bytes.fromhex(
    "87218900421a06d3142a05d3342a06d33c2a07d20120704705488018704705488018"
    "704708b525f781fb012008bd0000020600007c050000")
GETTER_CALL_SITES = (
    0x0203B27E, 0x0203B292, 0x0203B2AE, 0x0203B2C2, 0x0203B2D6, 0x0203B2EA,
    0x0203B2FE, 0x0203B312, 0x0203B326, 0x0203B346, 0x0203B35A, 0x0203B36E,
    0x0203B38A, 0x0203B3AA, 0x0203B3CA, 0x0203B3E6, 0x0203B402, 0x0203B41E,
    0x0203B43A, 0x0203B456, 0x0203B472, 0x0203B48E, 0x0203B4AA, 0x0203B4C6,
    0x0203B4DE, 0x0203B4FA, 0x0203B51E,
)


def install_hook_stubs(arm9: bytearray) -> None:
    """The hg-engine hooks that retire the reused blocks' stock readers."""
    for address, stub, _reader in ht.RETIRED_READER_STUBS:
        arm9[address - ht.ARM9_BASE:address - ht.ARM9_BASE + len(stub)] = stub


def stock_arm9() -> bytearray:
    """Synthetic arm9 with the stock pieces verify() and locate() inspect."""
    arm9 = bytearray(ARM9_SIZE)

    def put(address: int, data: bytes) -> None:
        arm9[address - ht.ARM9_BASE:address - ht.ARM9_BASE + len(data)] = data

    put(ht.BOUNDS_CHECK, bytes.fromhex("08b5872189008842 02d3eaf753f90120 08bd0000"))
    for site in GETTER_CALL_SITES:
        put(site, ht.thumb_bl(site, ht.BOUNDS_CHECK))
    for site, field in ht.GETTER_LITERALS.items():
        put(site, struct.pack("<I", ht.TABLE + field))
    install_hook_stubs(arm9)
    put(ht.MARKINGS_SITE, bytes.fromhex("87208000"))
    nothing = codecs.encode_header(sample_header(matrix=1))
    for map_id in range(ht.VANILLA_COUNT):
        row = nothing if map_id == ht.MAP_NOTHING else codecs.encode_header(sample_header(matrix=map_id))
        put(ht.TABLE + map_id * ht.HEADER_SIZE, row)
    return arm9


def sample_header(matrix: int = 0, events: int = 0) -> dict:
    spec = codecs.decode_header(bytes(ht.HEADER_SIZE))
    spec.update(matrixId=matrix, eventsBank=events)
    return spec


def ext_blob(count: int, first_matrix: int = 1000) -> bytes:
    return b"".join(codecs.encode_header(sample_header(matrix=first_matrix + i)) for i in range(count))


def overarm9(compressed_101: bool) -> bytes:
    table = bytearray(0x20 * 130)
    struct.pack_into("<I", table, 101 * 0x20 + 0x1C, 0x01000000 if compressed_101 else 0)
    return bytes(table)


def overlay101() -> bytearray:
    data = bytearray(0x13BC0)
    start = ht.TALK_SITE - ht.TALK_OVERLAY_BASE
    data[start:start + 4] = bytes.fromhex("87206400")
    return data


def run_routine(arm9: bytes, map_id: int) -> tuple[int, bool]:
    """Interpret the patched bounds check (stub + routine). Returns (r0, asserted)."""
    regs = [0] * 16
    regs[0] = map_id & 0xFFFFFFFF
    lr = 0xDEAD0000
    regs[14] = lr
    carry = zero = False
    asserted = False
    pc = ht.BOUNDS_CHECK
    stack: list[int] = []

    def half(address: int) -> int:
        return struct.unpack_from("<H", arm9, address - ht.ARM9_BASE)[0]

    for _ in range(64):
        op = half(pc)
        nxt = pc + 2
        if op & 0xF800 == 0x4800:      # ldr rd,[pc,#imm]
            rd, imm = (op >> 8) & 7, (op & 0xFF) * 4
            regs[rd] = struct.unpack_from("<I", arm9, ((pc + 4) & ~3) + imm - ht.ARM9_BASE)[0]
        elif op & 0xFF87 == 0x4700:    # bx rm
            target = regs[(op >> 3) & 15]
            if target == lr:
                return regs[0], asserted
            nxt = target & ~1
        elif op & 0xF800 == 0x2000:    # movs rd,#imm
            regs[(op >> 8) & 7] = op & 0xFF
        elif op & 0xF800 == 0x0000:    # lsls rd,rm,#imm
            regs[op & 7] = (regs[(op >> 3) & 7] << ((op >> 6) & 31)) & 0xFFFFFFFF
        elif op & 0xFE00 == 0x1A00:    # subs rd,rn,rm
            a, b = regs[(op >> 3) & 7], regs[(op >> 6) & 7]
            regs[op & 7] = (a - b) & 0xFFFFFFFF
            carry = a >= b
        elif op & 0xFE00 == 0x1800:    # adds rd,rn,rm
            regs[op & 7] = (regs[(op >> 3) & 7] + regs[(op >> 6) & 7]) & 0xFFFFFFFF
        elif op & 0xF800 == 0x2800:    # cmp rn,#imm
            a, b = regs[(op >> 8) & 7], op & 0xFF
            carry, zero = a >= b, a == b
        elif op & 0xF000 == 0xD000:    # b<cond>
            cond, offset = (op >> 8) & 15, op & 0xFF
            offset = offset - 256 if offset & 0x80 else offset
            taken = {0x2: carry, 0x3: not carry, 0x0: zero, 0x1: not zero}[cond]
            if taken:
                nxt = pc + 4 + offset * 2
        elif op == 0xB508:             # push {r3,lr}
            stack.append(regs[14])
        elif op == 0xBD08:             # pop {r3,pc}
            regs[15] = stack.pop()
            if regs[15] == lr:
                return regs[0], asserted
            nxt = regs[15]
        elif op & 0xF800 == 0xF000:    # bl
            target = ht._bl_target(arm9[pc - ht.ARM9_BASE:pc - ht.ARM9_BASE + 4], pc)
            if target != ht.GF_ASSERT_FAIL:
                raise AssertionError(f"unexpected bl 0x{target:08X}")
            asserted = True
            regs[14] = pc + 4
            nxt = pc + 4
        else:
            raise AssertionError(f"unhandled Thumb op 0x{op:04X} at 0x{pc:08X}")
        pc = nxt
    raise AssertionError("routine did not return")


class Encoding(unittest.TestCase):
    def test_stub_and_routine_match_armips_output(self):
        self.assertEqual(ht.stub_bytes(), GOLDEN_STUB)
        layout = ht.Layout.plan(600, 52)
        self.assertEqual(ht.routine_bytes(600, 52, layout.b_defined, layout.b_row, layout.a_row),
                         GOLDEN_ROUTINE_600_52)

    def test_patch_source_constants_match_python(self):
        source = ht.PATCH_SOURCE.read_text()

        def equ(name: str) -> int:
            return int(re.search(rf"(?m)^{name}\s+equ\s+(0x[0-9A-Fa-f]+|\d+)", source).group(1), 0)

        self.assertEqual(equ("MAP_HEADER_TABLE"), ht.TABLE)
        self.assertEqual(equ("MAP_HEADER_VANILLA_COUNT"), ht.VANILLA_COUNT)
        self.assertEqual(equ("MAP_HEADER_EXT_B_BASE"), ht.B_BASE)
        self.assertEqual(equ("MAP_HEADER_EXT_B_SLOTS"), ht.B_SLOTS)
        self.assertEqual(equ("MAP_HEADER_EXT_B_LIMIT"), ht.B_LIMIT)
        self.assertEqual(equ("MAP_HEADER_EXT_A_TOP"), ht.A_TOP)
        self.assertEqual(equ("MAP_HEADER_EXT_A_MAX_SLOTS"), ht.A_MAX_SLOTS)
        self.assertEqual(equ("MAP_HEADER_EXT_A_FLOOR"), ht.A_FLOOR)
        self.assertEqual(equ("GF_AssertFail_Address"), ht.GF_ASSERT_FAIL)
        self.assertIn(f'"base/{ht.EXT_FILE_NAME}"', source)
        count = ht.configured_count()
        ht.Layout.plan(count, 0)  # configured count is valid

    def test_slot_blocks_are_row_aligned_and_fit(self):
        self.assertEqual((ht.B_BASE - ht.TABLE) % ht.HEADER_SIZE, 0)
        self.assertEqual((ht.A_TOP - ht.TABLE) % ht.HEADER_SIZE, 0)
        self.assertLessEqual(ht.ROUTINE + ht.ROUTINE_SIZE, ht.B_LIMIT)
        self.assertGreaterEqual(ht.A_TOP - ht.A_MAX_SLOTS * ht.HEADER_SIZE, ht.A_FLOOR)

    def test_plan_rejects_bad_counts(self):
        for count, defined in ((540, 0), (602, 0), (796, 0), (600, 53), (548, 9)):
            with self.subTest(count=count, defined=defined), self.assertRaises(ht.ExpansionError):
                ht.Layout.plan(count, defined)


class RoutineBehavior(unittest.TestCase):
    def test_machine_code_returns_planned_rows(self):
        for count, defined in ((544, 0), (544, 4), (600, 0), (600, 5), (600, 20),
                               (600, 25), (600, 52), (792, 52)):
            arm9 = stock_arm9()
            layout = ht.apply_reference_patch(arm9, count, ext_blob(defined))
            ids = {0, 1, 2, 539, 540, 541, 559, 560, 561, 591, 592,
                   count - 1, count, count + 1, 0xFFFF, 0xFFFFFFFF}
            ids |= set(range(540, 540 + defined))
            for map_id in sorted(ids):
                with self.subTest(count=count, defined=defined, map_id=map_id):
                    row, asserted = run_routine(arm9, map_id)
                    if map_id >= count:
                        self.assertTrue(asserted)
                        self.assertEqual(row, ht.MAP_NOTHING)
                    else:
                        self.assertFalse(asserted)
                        self.assertEqual(row, layout.row(map_id))

    def test_extension_rows_hold_their_headers(self):
        arm9 = stock_arm9()
        blob = ext_blob(30)
        layout = ht.apply_reference_patch(arm9, 600, blob)
        for index in range(30):
            map_id = 540 + index
            row, _ = run_routine(arm9, map_id)
            # Getter arithmetic: (table + field) + row * 24, 32-bit.
            address = (ht.TABLE + row * ht.HEADER_SIZE) & 0xFFFFFFFF
            got = bytes(arm9[address - ht.ARM9_BASE:address - ht.ARM9_BASE + ht.HEADER_SIZE])
            self.assertEqual(got, blob[index * 24:(index + 1) * 24])
            self.assertEqual(codecs.decode_header(got)["matrixId"], 1000 + index)
            self.assertEqual(ht.read_entry(arm9, map_id, layout), got)
        self.assertEqual(ht.read_entry(arm9, 570), ht.read_entry(arm9, ht.MAP_NOTHING))
        self.assertEqual(ht.read_entry(arm9, 539)[:24], codecs.encode_header(sample_header(matrix=539)))


class LocateAndVerify(unittest.TestCase):
    def patched(self, defined: int = 3, compressed: bool = False):
        arm9, ov = stock_arm9(), overlay101()
        y9 = overarm9(compressed)
        ht.apply_reference_patch(arm9, 600, ext_blob(defined), y9, ov)
        return arm9, y9, ov

    def test_missing_reader_hook_is_an_error(self):
        arm9 = stock_arm9()
        ht.apply_reference_patch(arm9, 600, b"")
        address = ht.RETIRED_READER_STUBS[0][0]
        arm9[address - ht.ARM9_BASE:address - ht.ARM9_BASE + 4] = b"\x00" * 4
        errors, _ = ht.verify(bytes(arm9))
        self.assertTrue(any("not hooked" in error for error in errors), errors)

    def test_stock_arm9_has_no_layout(self):
        self.assertIsNone(ht.locate(stock_arm9()))
        errors, _ = ht.verify(bytes(stock_arm9()))
        self.assertTrue(errors and "stock" in errors[0])

    def test_patched_arm9_verifies(self):
        arm9, y9, ov = self.patched()
        self.assertEqual(ht.locate(arm9), ht.Layout.plan(600, 3))
        self.assertEqual(ht.verify(bytes(arm9), None, y9, bytes(ov), 600), ([], []))

    def test_compressed_overlay_101_is_a_warning(self):
        arm9, y9, ov = self.patched(compressed=True)
        errors, warnings = ht.verify(bytes(arm9), None, y9, bytes(ov), 600)
        self.assertEqual(errors, [])
        self.assertTrue(any("Pokemon Talk" in w for w in warnings))

    def test_verify_reports_each_broken_site(self):
        def broken(mutate) -> list[str]:
            arm9, y9, ov = self.patched()
            mutate(arm9, ov)
            return ht.verify(bytes(arm9), None, y9, bytes(ov), 600)[0]

        def off(address: int) -> int:
            return address - ht.ARM9_BASE

        self.assertTrue(broken(lambda a, o: a.__setitem__(off(ht.MARKINGS_SITE), 0x87)))
        self.assertTrue(broken(lambda a, o: o.__setitem__(ht.TALK_SITE - ht.TALK_OVERLAY_BASE, 0x87)))
        self.assertTrue(broken(lambda a, o: a.__setitem__(off(0x0203B28C), 0)))
        self.assertTrue(broken(lambda a, o: a.__setitem__(slice(off(GETTER_CALL_SITES[3]),
                                                                off(GETTER_CALL_SITES[3]) + 4), b"\0" * 4)))
        self.assertTrue(broken(lambda a, o: a.__setitem__(off(ht.ROUTINE) + 16, 0x3D)))
        self.assertTrue(broken(lambda a, o: a.__setitem__(off(ht.BOUNDS_CHECK) + 4, 0)))
        arm9, y9, ov = self.patched()
        self.assertTrue(ht.verify(bytes(arm9), None, y9, bytes(ov), 640)[0])

    def test_root_checks_per_map_archives(self):
        arm9, y9, ov = self.patched(defined=3)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ht.MAP_INDEXED_NARCS.values():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_bytes(narc.build([b"\0" * 4] * 540))
            errors, _ = ht.verify(bytes(arm9), root, y9, bytes(ov), 600)
            self.assertEqual(len(errors), 2)
            for rel in ht.MAP_INDEXED_NARCS.values():
                (root / rel).write_bytes(ht.pad_narc((root / rel).read_bytes(), 543, b"\0" * 4))
            errors, warnings = ht.verify(bytes(arm9), root, y9, bytes(ov), 600)
            self.assertEqual(errors, [])
            self.assertEqual(len([w for w in warnings if "members for 600" in w]), 2)

    def test_write_entry_round_trips_and_refuses_aliases(self):
        arm9, _, _ = self.patched(defined=25)
        data = codecs.encode_header(sample_header(matrix=77, events=5))
        for map_id in (12, 540, 559, 560, 564):
            ht.write_entry(arm9, map_id, data)
            self.assertEqual(ht.read_entry(arm9, map_id), data)
        with self.assertRaises(ht.ExpansionError):
            ht.write_entry(arm9, 565, data)

    def test_logical_headers(self):
        arm9, _, _ = self.patched(defined=2)
        table = ht.logical_headers(arm9)
        self.assertEqual(len(table), 600)
        self.assertEqual(table[540]["matrixId"], 1000)
        self.assertNotIn("alias", table[541])
        self.assertEqual(table[542]["alias"], ht.MAP_NOTHING)
        stock = ht.logical_headers(stock_arm9(), count=544)
        self.assertEqual([e.get("alias") for e in stock[539:]], [None, 1, 1, 1, 1])


class BuildInputs(unittest.TestCase):
    def test_extension_blob_fills_gaps_with_nothing(self):
        nothing = codecs.encode_header(sample_header(matrix=1))
        a = codecs.encode_header(sample_header(matrix=900))
        b = codecs.encode_header(sample_header(matrix=901))
        blob = ht.extension_blob({12: a, 540: a, 542: b}, nothing)
        self.assertEqual(blob, a + nothing + b)
        self.assertEqual(ht.extension_blob({3: a}, nothing), b"")
        with self.assertRaises(ht.ExpansionError):
            ht.extension_blob({540 + 52: a}, nothing)

    def test_write_extension_file(self):
        nothing = codecs.encode_header(sample_header(matrix=1))
        with tempfile.TemporaryDirectory() as tmp:
            arm9_path = Path(tmp) / "arm9.bin"
            path = ht.write_extension_file(arm9_path, {540: nothing}, nothing)
            self.assertEqual(path.read_bytes(), nothing)
            ht.write_extension_file(arm9_path, {}, nothing)
            self.assertFalse(path.exists())

    def test_pad_narc(self):
        data = narc.build([b"\1\0\0\0"] * 3)
        padded = ht.pad_narc(data, 5, b"\0" * 4)
        self.assertEqual(narc.members(padded), [b"\1\0\0\0"] * 3 + [b"\0" * 4] * 2)
        self.assertIs(ht.pad_narc(data, 3, b""), data)


@unittest.skipUnless(ROM.exists(), "rom.nds not present")
class StockRom(unittest.TestCase):
    def test_stock_arm9_matches_the_patch_assumptions(self):
        import ndspy.codeCompression
        import ndspy.rom
        rom = ndspy.rom.NintendoDSRom.fromFile(str(ROM))
        arm9 = bytearray(ndspy.codeCompression.decompress(rom.arm9))
        self.assertIsNone(ht.locate(arm9))
        stock_check = arm9[ht.BOUNDS_CHECK - ht.ARM9_BASE:ht.BOUNDS_CHECK_END - ht.ARM9_BASE]
        self.assertEqual(stock_check[:4], bytes.fromhex("08b58721"))
        for site, field in ht.GETTER_LITERALS.items():
            self.assertEqual(struct.unpack_from("<I", arm9, site - ht.ARM9_BASE)[0], ht.TABLE + field)
        install_hook_stubs(arm9)  # base/arm9.bin gets these from hg-engine's hooks
        layout = ht.apply_reference_patch(arm9, 600, b"")
        self.assertEqual(ht.verify(bytes(arm9))[0], [])
        self.assertEqual(ht.read_entry(arm9, 599, layout), ht.read_entry(arm9, ht.MAP_NOTHING, layout))


if __name__ == "__main__":
    unittest.main()
