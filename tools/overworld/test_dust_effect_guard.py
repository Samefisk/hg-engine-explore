"""Dry-ground and step dirt must reject a missing model without changing motion."""

from pathlib import Path
import hashlib
import subprocess
import tempfile
import unittest

import ndspy.code
import ndspy.rom


ROOT = Path(__file__).resolve().parents[2]
SITES = (0x021FF7EC, 0x0220017C)
STOCK_INITS = (
    (0x021FF7B0, "b6d725349756d1804faaf36c7fca2e74a39f9bd3343971b213210c3980896bbc"),
    (0x02200140, "50f514419c2e353ac185160c34d9ff9077c383953f572da990c262b9c089fb0e"),
)
SYMBOL = "OverworldDustEffect_InitAllocationGuard"
SECTION = ".overworld_dust_effect_guard"
STOCK = bytes.fromhex("20 62 01 20 03 b0 30 bd")
GUARD = bytes.fromhex("00 28 02 d0 20 62 01 20 00 e0 00 20 03 b0 30 bd")


def execute_tail(code, model):
    """Execute only the assembled native tail; fail on other opcodes or stores."""
    regs = [0x11000000 + i * 4 for i in range(16)]
    work, stack, caller = 0x02210000, 0x023F0000, 0x02001001
    saved = (0x12345678, 0x23456789, caller)
    regs[0], regs[4], regs[13] = model, work, stack
    before = regs[:]
    memory = {work + 0x20: 0xA5A5A5A5}
    memory.update({stack + 12 + i * 4: value for i, value in enumerate(saved)})
    writes, pc, equal = [], 0, False
    for _ in range(12):
        if regs[15] == caller & ~1:
            return regs, before, memory, writes, work, saved
        if pc < 0 or pc + 2 > len(code):
            raise ValueError("dust tail escaped its exact body")
        op = int.from_bytes(code[pc:pc + 2], "little")
        next_pc = pc + 2
        if op == 0x2800:  # cmp r0,#0
            equal = regs[0] == 0
        elif op & 0xFF00 == 0xD000:  # beq
            delta = (op & 255) - (256 if op & 128 else 0)
            if equal:
                next_pc = pc + 4 + delta * 2
        elif op == 0x6220:  # str r0,[r4,#0x20]
            memory[regs[4] + 0x20] = regs[0]
            writes.append((regs[4] + 0x20, regs[0]))
        elif op & 0xFF00 == 0x2000:  # mov r0,#imm8
            regs[0] = op & 255
        elif op & 0xF800 == 0xE000:  # b
            delta = (op & 2047) - (2048 if op & 1024 else 0)
            next_pc = pc + 4 + delta * 2
        elif op == 0xB003:  # add sp,#0xC
            regs[13] += 12
        elif op == 0xBD30:  # pop {r4,r5,pc}
            for i, register in enumerate((4, 5, 15)):
                address = regs[13] + i * 4
                if address not in memory:
                    raise ValueError("dust tail used a different saved frame")
                regs[register] = memory[address]
            regs[13] += 12
            regs[15] &= ~1
        elif op != 0x46C0:  # copied NOP fault
            raise ValueError(f"unexpected dust opcode {op:04X}")
        pc = next_pc
    raise ValueError("dust tail exceeded its instruction bound")


def verify_tail(code, model):
    regs, before, memory, writes, work, saved = execute_tail(code, model)
    assert regs[0] == bool(model), "missing model was admitted"
    assert writes == ([(work + 0x20, model)] if model else []), "model ownership differs"
    assert memory[work + 0x20] == (model if model else 0xA5A5A5A5), "unowned model store"
    assert regs[4:6] == list(saved[:2]), "saved registers differ"
    assert regs[13] == before[13] + 24 and regs[15] == saved[2] & ~1, "stock return frame differs"
    assert all(regs[i] == before[i] for i in (1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 14)), "other registers changed"


class DustEffectGuardTests(unittest.TestCase):
    def test_effect_pool_capacity_hook_keeps_other_stock_budgets(self):
        rom = ndspy.rom.NintendoDSRom.fromFile(ROOT / "rom.nds")
        overlay = ndspy.code.loadOverlayTable(
            rom.arm9OverlayTable,
            lambda _id, file_id: rom.files[file_id],
            {1},
        )[1]
        site = 0x021E64D0
        self.assertEqual(bytes(overlay.data[site - overlay.ramAddress:
                                            site - overlay.ramAddress + 8]),
                         bytes.fromhex("04 21 13 1c 0a f0 5c ff"))
        lines = [line.strip() for line in (ROOT / "hooks").read_text().splitlines()
                 if "OverworldEffectPool_ExpandModelSlots" in line]
        self.assertEqual(lines, ["0001 OverworldEffectPool_ExpandModelSlots 021E64D0 1"])
        with tempfile.TemporaryDirectory(prefix="effect-pool-capacity-") as folder:
            object_file = Path(folder) / "capacity.o"
            binary_file = Path(folder) / "capacity.bin"
            subprocess.run(["arm-none-eabi-as", "-mthumb", "-o", str(object_file),
                            str(ROOT / "asm/overworld_effect_pool_capacity.s")],
                           check=True, capture_output=True, text=True)
            subprocess.run(["arm-none-eabi-objcopy", "-O", "binary", "-j",
                            ".overworld_effect_pool_capacity", str(object_file),
                            str(binary_file)],
                           check=True, capture_output=True, text=True)
            code = binary_file.read_bytes()
        self.assertEqual(len(code), 20)
        self.assertEqual(code[:6], bytes.fromhex("04 21 13 1c 30 22"))
        self.assertEqual(code[-4:], bytes.fromhex("d9 64 1e 02"))
        linker = (ROOT / "src/linker.ld").read_text()
        self.assertIn("KEEP(*(.overworld_effect_pool_capacity))", linker)
        self.assertIn("ASSERT(SIZEOF(.overworld_effect_pool_capacity) <= 20", linker)

    def test_stock_init_and_hook_are_bound_to_the_dust_effect(self):
        rom = ndspy.rom.NintendoDSRom.fromFile(ROOT / "rom.nds")
        overlay = ndspy.code.loadOverlayTable(
            rom.arm9OverlayTable,
            lambda _id, file_id: rom.files[file_id],
            {1},
        )[1]
        for (entry, digest), site in zip(STOCK_INITS, SITES):
            with self.subTest(site=f"{site:08X}"):
                offset = entry - overlay.ramAddress
                body = bytes(overlay.data[offset:offset + 68])
                self.assertEqual(hashlib.sha256(body).hexdigest(), digest)
                self.assertEqual(body[:8], bytes.fromhex("30 b5 83 b0 0c 1c 05 1c"))
                self.assertEqual(site - entry, 60)
                self.assertEqual(body[-8:], STOCK)
                destructor = bytes(overlay.data[offset + 68:offset + 80])
                self.assertEqual(destructor, bytes.fromhex("01 4b 08 6a 18 47 c0 46 a5 3d 02 02"))
        # Real creator FALSE clears the task/work without the model destructor.
        reference = (ROOT / ".codex-reference/pokeheartgold/asm/unk_020689C8.s").read_text()
        failure = reference.split("bl sub_02068CFC", 1)[1].split("_02068AF2:", 1)[0]
        self.assertIn("cmp r0, #0\n\tbne _02068AF2", failure)
        self.assertIn("bl SysTask_Destroy", failure)
        self.assertIn("bl sub_02068C6C", failure)
        self.assertNotIn("sub_02068D50", failure)
        lines = [line.strip() for line in (ROOT / "hooks").read_text().splitlines()
                 if SYMBOL in line and not line.lstrip().startswith("#")]
        self.assertEqual(lines, [f"0001 {SYMBOL} {site:08X} 1" for site in SITES])

    def test_assembled_guard_returns_false_for_null_and_keeps_success(self):
        with tempfile.TemporaryDirectory(prefix="dust-effect-guard-") as folder:
            object_file = Path(folder) / "guard.o"
            binary_file = Path(folder) / "guard.bin"
            subprocess.run(
                ["arm-none-eabi-as", "-mthumb", "-o", str(object_file),
                 str(ROOT / "asm/overworld_dust_effect_guard.s")],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["arm-none-eabi-objcopy", "-O", "binary", "-j", SECTION,
                 str(object_file), str(binary_file)],
                check=True, capture_output=True, text=True,
            )
            code = binary_file.read_bytes()
            self.assertEqual(code, GUARD)
            for model in (0, 0x02000000, 0x02212340, 0x023FFFFC):
                with self.subTest(model=f"{model:08X}"):
                    verify_tail(code, model)
        self.assertEqual(len(GUARD), 16)
        self.assertLessEqual(len(GUARD), 32)
        linker = (ROOT / "src/linker.ld").read_text()
        self.assertIn(f"KEEP(*({SECTION}))", linker)
        self.assertIn(f"ASSERT(SIZEOF({SECTION}) <= 32", linker)

    def test_stock_mov_one_and_missing_null_branch_fail(self):
        with self.assertRaisesRegex(AssertionError, "missing model was admitted"):
            verify_tail(STOCK, 0)
        missing_branch = GUARD[:2] + bytes.fromhex("c0 46") + GUARD[4:]
        with self.assertRaisesRegex(AssertionError, "missing model was admitted"):
            verify_tail(missing_branch, 0)
        # A copied changed stack cleanup must also fail, not hide behind FALSE.
        wrong_frame = GUARD[:12] + bytes.fromhex("c0 46") + GUARD[14:]
        with self.assertRaisesRegex(ValueError, "saved frame"):
            verify_tail(wrong_frame, 0)


if __name__ == "__main__":
    unittest.main()
