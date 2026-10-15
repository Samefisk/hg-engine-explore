"""The zero-HP trace reads only pinned overlay spans outside main RAM."""

import struct
import unittest

from tools.overworld.devtools_player_health_zero_load_trace import ZeroLoadRecoveryTrace

FIELD = 0x02100000
ROOT = 0x02110000
STOCK = 0x02110100
CHILD = 0x02110200
ENV = 0x02120000
CODE_ROOT = 0x01FFAE50
CODE_STOCK = 0x01FFAED8
OWNER = 0x01FFBAE4
FAILED = 0x01FFBAE0


def fixture():
    code = {"PlayerHealthRecovery_BlackoutTask": (CODE_ROOT, 4, b"ROOT"),
            "PlayerHealthRecovery_StockBlackoutTask": (CODE_STOCK, 4, b"STOK")}
    data = {"sBlackoutFieldSystem": (OWNER, 4, None),
            "sBlackoutFailed": (FAILED, 1, None)}
    memory = {}
    def put(address, value):
        memory.update({address + i: byte for i, byte in enumerate(value)})
    put(CODE_ROOT, b"ROOT")
    put(CODE_STOCK, b"STOK")
    put(OWNER, struct.pack("<I", FIELD))
    put(FAILED, b"\0")
    put(FIELD + 0x10, struct.pack("<I", CHILD))
    for task, previous, callback, state, env in (
            (ROOT, 0, CODE_ROOT | 1, 2, 0),
            (STOCK, ROOT, CODE_STOCK | 1, 4, 0),
            (CHILD, STOCK, 0x02030001, 0, ENV)):
        put(task, struct.pack("<8I", previous, callback, state, env, 0, 0, FIELD, 0))
    put(ENV, b"\2")
    reads = []
    def raw(address, size):
        reads.append((address, size))
        return bytes(memory.get(address + i, 0) for i in range(size))
    def main(address, size):
        if not 0x02000000 <= address <= address + size <= 0x02400000:
            raise ValueError("diagnostic read is outside main RAM/public stack")
        return raw(address, size)
    def overlay(address, size):
        if not 0x01FFA580 <= address <= address + size <= 0x01FFC180:
            raise ValueError("read outside pinned overlay")
        return raw(address, size)
    return ZeroLoadRecoveryTrace(code, data), memory, reads, main, overlay


class ZeroLoadTraceTests(unittest.TestCase):
    def test_exact_overlay_reads_and_main_ram_task_reads(self):
        trace, _, reads, main, overlay = fixture()
        row = trace.observe(main, FIELD, 1, 21, read_overlay=overlay)
        self.assertEqual(row["root"], {"pointer": ROOT, "state": 2})
        self.assertEqual(row["stock"], {"pointer": STOCK, "state": 4})
        self.assertTrue(row["messageInputReady"])
        self.assertEqual({(address, size) for address, size in reads if address < 0x02000000},
                         trace.overlay_reads)

    def test_wrong_overlay_code_and_owner_still_fail(self):
        for address, value, expected in ((CODE_ROOT, ord("X"), "live recovery code differs"),
                                         (OWNER, 1, "field owner differs"),
                                         (FAILED, 1, "failure flag is set")):
            with self.subTest(address=address):
                trace, memory, _, main, overlay = fixture()
                memory[address] = value
                with self.assertRaisesRegex(ValueError, expected):
                    trace.observe(main, FIELD, 1, 21, read_overlay=overlay)

    def test_overlay_callback_cannot_expand_task_pointer_range(self):
        trace, memory, _, main, overlay = fixture()
        memory[FIELD + 0x10] = CODE_ROOT & 0xFF
        for i, byte in enumerate(struct.pack("<I", CODE_ROOT)):
            memory[FIELD + 0x10 + i] = byte
        with self.assertRaisesRegex(ValueError, "task pointer is invalid"):
            trace.observe(main, FIELD, 1, 21, read_overlay=overlay)


if __name__ == "__main__":
    unittest.main()
