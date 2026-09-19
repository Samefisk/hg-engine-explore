"""Test exact package selection and completed-frame dialogue publication."""
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.overworld.devtools_runtime import DevtoolsSession


class DialogueWiringTests(unittest.TestCase):
    def fixture(self, task=0):
        s = DevtoolsSession.__new__(DevtoolsSession)
        field, table = 0x02280000, 0x021D1000
        image = bytearray(0x7148)
        struct.pack_into("<I", image, 0x713C, table)
        s.arm9_code_region = (0x02000000, bytes(image))
        s.dialogue_overlay_regions = {1: (0x021EF348, b"\x11" * 20)}
        memory = {field + 0x10: struct.pack("<I", task),
                  table: struct.pack("<16I", 1, 1, 27, 1, *([0] * 12)),
                  0x021EF348: b"\x11" * 20}
        reads = []
        def read(address, size):
            reads.append((address, size))
            if 0x02000000 <= address and address + size <= 0x02000000 + len(image):
                return bytes(image[address - 0x02000000:address - 0x02000000 + size])
            data = memory[address]
            self.assertEqual(len(data), size)
            return data
        s.read = read
        s.completed_frames = 17
        s.rt = SimpleNamespace(EXECUTED_FRAME_COUNT=23)
        return s, field, memory, reads

    def test_idle_skips_overlay_scan_and_passes_exact_clocks(self):
        s, field, memory, reads = self.fixture()
        with patch("tools.overworld.devtools_dialogue.observe_dialogue", return_value={"state": "idle"}) as reader:
            self.assertEqual(s._dialogue_observation(field), {"state": "idle"})
        self.assertEqual(reader.call_args.args[2:], (field, 17, 23, set()))
        self.assertEqual(reads, [(field + 0x10, 4)])

    def test_loaded_ids_and_exact_owner_package(self):
        s, field, memory, reads = self.fixture(task=0x02290000)
        def reader(read, authenticate, actual_field, frame, cycles, loaded):
            self.assertEqual(loaded, {1, 27})
            self.assertTrue(authenticate(0x021EF348, 20))
            return {"state": "printing"}
        with patch("tools.overworld.devtools_dialogue.observe_dialogue", side_effect=reader):
            self.assertEqual(s._dialogue_observation(field)["state"], "printing")
            memory[0x021EF348] = b"\x22" * 20
            # An unrelated overlapping overlay cannot authenticate the reader.
            s.code_regions = [(0x021EF348, b"\x22" * 20)]
            result = s._dialogue_observation(field)
            self.assertEqual(result["state"], "unknown")
            self.assertFalse(result["known"])
            self.assertEqual(result["frame"], 17)


if __name__ == "__main__":
    unittest.main()
