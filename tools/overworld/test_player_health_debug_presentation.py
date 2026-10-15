"""Presentation descriptor identity checks without a ROM build or game run."""
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from scripts.generate_player_health_debug import BASE, checked_presentation, symbol_table

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/player_health_presentation.c"
HEADER = ROOT / "include/player_health_presentation.h"


class PresentationDescriptorTest(unittest.TestCase):
    def setUp(self):
        self.image = bytearray(0x200)
        self.symbols = {"sPresentation": (BASE + 0x180, 0x38),
                        "PlayerHealthPresentation_GetReceipt": (BASE + 0x80, 12)}
        struct.pack_into("<4HI", self.image, 0x80,
                         0x4801, 0x3030, 0x4770, 0x46C0, BASE + 0x180)

    def check(self, source=SOURCE, header=HEADER):
        return checked_presentation(self.symbols, self.image, source, header)

    def test_linked_getter_authenticates_native_receipt_offset(self):
        result = self.check()
        self.assertEqual(result["address"] + result["receiptOffset"], BASE + 0x1B0)
        self.assertEqual(result["receiptSize"], 4)
        self.assertEqual(result["version"], 3)
        self.assertEqual(result["receiptOffsets"]["drawnFill"], 1)

    def test_wrong_getter_pointer_and_out_of_image_symbol_fail(self):
        struct.pack_into("<I", self.image, 0x88, BASE + 0x184)
        with self.assertRaisesRegex(ValueError, "getter layout"):
            self.check()
        self.symbols["sPresentation"] = (BASE + 0x1D0, 0x38)
        with self.assertRaisesRegex(ValueError, "symbols"):
            self.check()

    def test_reordered_public_receipt_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = Path(tmp) / "receipt.h"
            header.write_text(HEADER.read_text().replace(
                "u8 requestedFill;\n    u8 drawnFill;",
                "u8 drawnFill;\n    u8 requestedFill;"))
            with self.assertRaisesRegex(ValueError, "layout changed"):
                self.check(header=header)

    def test_nested_layout_change_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "presentation.c"
            source.write_text(SOURCE.read_text().replace("u16 vram;", "u32 vram;"))
            with self.assertRaisesRegex(ValueError, "nested layout"):
                self.check(source=source)

    def test_thumb_memset_veneer_fails_packaging(self):
        with patch("scripts.generate_player_health_debug.subprocess.check_output",
                   return_value="01ffbd38 l F .text 00000008 __memset_from_thumb\n"):
            with self.assertRaisesRegex(ValueError, "crosses into ARM state"):
                symbol_table(Path("linked.o"))

    def test_thumb_memcpy_veneer_fails_packaging(self):
        with patch("scripts.generate_player_health_debug.subprocess.check_output",
                   return_value="01ffc530 l F .text 00000008 __memcpy_from_thumb\n"):
            with self.assertRaisesRegex(ValueError, "crosses into ARM state"):
                symbol_table(Path("linked.o"))


if __name__ == "__main__":
    unittest.main()
