"""The dry-ground effect must reject a missing model without changing motion."""

from pathlib import Path
import subprocess
import tempfile
import unittest

import ndspy.code
import ndspy.rom


ROOT = Path(__file__).resolve().parents[2]
SITE = 0x021FF7EC
SYMBOL = "OverworldDustEffect_InitAllocationGuard"
SECTION = ".overworld_dust_effect_guard"
STOCK = bytes.fromhex("20 62 01 20 03 b0 30 bd")
GUARD = bytes.fromhex("00 28 02 d0 20 62 01 20 00 e0 00 20 03 b0 30 bd")


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
        offset = SITE - overlay.ramAddress
        self.assertEqual(bytes(overlay.data[offset:offset + 8]), STOCK)
        lines = [line.strip() for line in (ROOT / "hooks").read_text().splitlines()
                 if SYMBOL in line and not line.lstrip().startswith("#")]
        self.assertEqual(lines, [f"0001 {SYMBOL} {SITE:08X} 1"])

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
            self.assertEqual(binary_file.read_bytes(), GUARD)
        self.assertLessEqual(len(GUARD), 32)
        linker = (ROOT / "src/linker.ld").read_text()
        self.assertIn(f"KEEP(*({SECTION}))", linker)
        self.assertIn(f"ASSERT(SIZEOF({SECTION}) <= 32", linker)


if __name__ == "__main__":
    unittest.main()
