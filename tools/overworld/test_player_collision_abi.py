"""Independent stock Thumb ABI anchors; no ROM-derived assets are stored."""
from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parents[2]
BASE = 0x02000000
CALL = 0x0205D4C2
TARGET = 0x0205DA34
RETURN = 0x0205D4C6
MAPPING = 0x0205DA60


def validate_stock_collision_abi(arm9):
    """Decode the actual BL and six-instruction raw4-to-result2 branch."""
    def half(address):
        offset = address - BASE
        if offset < 0 or offset + 2 > len(arm9):
            raise ValueError("stock collision ABI is truncated")
        return struct.unpack_from("<H", arm9, offset)[0]

    hi, lo = half(CALL), half(CALL + 2)
    if hi >> 11 != 0b11110 or lo >> 11 != 0b11111:
        raise ValueError("player collision call is not Thumb BL")
    displacement = ((hi & 0x7ff) << 12) | ((lo & 0x7ff) << 1)
    if displacement & (1 << 22):
        displacement -= 1 << 23
    if CALL + 4 + displacement != TARGET or CALL + 4 != RETURN:
        raise ValueError("player collision call target/return differs")

    load, mask, test, branch, value, combine = (half(MAPPING + i * 2) for i in range(6))
    # Thumb ISA operand checks, not a copied ROM byte signature:
    # LDR r0,[sp,#0]; MOV r1,#4; TST r0,r1; BEQ continuation;
    # MOV r0,#2; ORR r4,r0. The continuation is just after ORR.
    if load >> 11 != 0b10011 or (load >> 8) & 7 != 0 or load & 0xff != 0:
        raise ValueError("raw collision result stack load differs")
    if mask >> 11 != 0b00100 or (mask >> 8) & 7 != 1 or mask & 0xff != 4:
        raise ValueError("raw object collision bit differs")
    if test >> 10 != 0b010000 or (test >> 6) & 15 != 8 or test & 7 != 0 or (test >> 3) & 7 != 1:
        raise ValueError("raw object collision test differs")
    if branch >> 12 != 0b1101 or (branch >> 8) & 15 != 0:
        raise ValueError("object collision branch condition differs")
    displacement = branch & 0xff
    if displacement & 0x80:
        displacement -= 0x100
    if MAPPING + 6 + 4 + displacement * 2 != MAPPING + 12:
        raise ValueError("object collision branch target differs")
    if value >> 11 != 0b00100 or (value >> 8) & 7 != 0 or value & 0xff != 2:
        raise ValueError("final object collision bit differs")
    if combine >> 10 != 0b010000 or (combine >> 6) & 15 != 12 \
            or combine & 7 != 4 or (combine >> 3) & 7 != 0:
        raise ValueError("final object collision accumulation differs")
    return {"call": CALL, "target": TARGET, "return": RETURN, "rawBit": mask & 0xff,
            "objectBit": value & 0xff}


class PlayerCollisionAbiTests(unittest.TestCase):
    def stock(self):
        path = ROOT / "build/arm9.bin"
        if not path.is_file():
            self.skipTest("stock build/arm9.bin is not available")
        return path.read_bytes()

    def test_actual_stock_call_and_object_mapping(self):
        self.assertEqual(validate_stock_collision_abi(self.stock()),
            {"call": CALL, "target": TARGET, "return": RETURN, "rawBit": 4, "objectBit": 2})

    def test_changed_call_mapping_registers_and_short_read_are_rejected(self):
        stock = self.stock()
        for address in (CALL, CALL + 2, *(MAPPING + i * 2 for i in range(6))):
            with self.subTest(address=hex(address)):
                changed = bytearray(stock)
                changed[address - BASE] ^= 1
                with self.assertRaises(ValueError):
                    validate_stock_collision_abi(changed)
        with self.assertRaises(ValueError):
            validate_stock_collision_abi(stock[:CALL - BASE + 2])

    def test_named_reference_abi_and_object_provenance(self):
        reference = ROOT / ".codex-reference/pokeheartgold"
        if not reference.is_dir():
            self.skipTest("optional named vanilla reference is not installed")
        header = (reference / "include/unk_02054648.h").read_text()
        self.assertRegex(header, r"BOOL\s+sub_02060BFC\(LocalMapObject\s*\*playerObj,\s*int xInFront,\s*int playerElev,\s*int yInFront\)")
        walking = (reference / "asm/unk_0205CB48.s").read_text()
        raw = walking.split("sub_0205DAA8: ;", 1)[1].split("thumb_func_end sub_0205DAA8", 1)[0]
        self.assertRegex(raw, r"bl sub_02060BFC\s+cmp r0, #1\s+bne _0205DB60\s+mov r0, #4\s+orr r4, r0")
        objects = (reference / "asm/unk_0205FD20.s").read_text()
        body = objects.split("sub_02060BFC: ;", 1)[1].split("thumb_func_end sub_02060BFC", 1)[0]
        for symbol in ("MapObject_GetManager", "MapObject_GetPreviousXCoord", "MapObject_GetPreviousZCoord"):
            self.assertIn("bl " + symbol, body)
        self.assertRegex(body, r"lsl r1, r1, #0x12\s+bl MapObject_GetFlagsBitsMask\s+cmp r0, #0\s+bne _02060C94")


if __name__ == "__main__":
    unittest.main()
