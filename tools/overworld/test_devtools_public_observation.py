"""Public native-buffer boundary controls, independent of retired collectors."""
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_observer import NativeObservationError, public_bytes


class PublicObservationBufferTests(unittest.TestCase):
    def test_public_buffers_preserve_exact_native_request_and_result_sizes(self):
        reads = []
        session = SimpleNamespace(read=lambda address, size: reads.append((address, size)) or bytes(size))
        for size in (20, 256, 28, 72):
            self.assertEqual(len(public_bytes(session, 0x027E368C, size)), size)
        self.assertEqual(reads, [(0x027E368C, size) for size in (20, 256, 28, 72)])

    def test_exact_public_ram_and_stack_endpoints_are_valid(self):
        session = SimpleNamespace(read=lambda address, size: bytes(size))
        for start, size in ((0x02000000, 20), (0x023FFF00, 256),
                            (0x027E0000, 20), (0x027E3EC0, 256), (0x027E3FA4, 28)):
            with self.subTest(start=hex(start), size=size):
                self.assertEqual(len(public_bytes(session, start, size)), size)

    def test_outside_reserved_crossing_and_unaligned_ranges_fail_before_read(self):
        reads = []
        session = SimpleNamespace(read=lambda *args: reads.append(args))
        for start, size in ((0x023FFFF0, 20), (0x02400000, 20), (0x027DFFFC, 20),
                            (0x027E3FB0, 28), (0x027E3FC0, 20), (0x027E3FFC, 20),
                            (0x027E4000, 20), (0x027FFFF0, 20), (0x04000000, 20),
                            (0x027E3000, 0), (0x027E3000, -4), (0x027E3001, 28),
                            (0x027E3002, 28)):
            with self.subTest(start=hex(start), size=size):
                with self.assertRaises(NativeObservationError):
                    public_bytes(session, start, size)
        self.assertEqual(reads, [])

    def test_partial_native_read_cannot_be_a_complete_public_result(self):
        session = SimpleNamespace(read=lambda address, size: bytes(size - 1))
        for size in (20, 256, 28, 72):
            with self.subTest(size=size), self.assertRaisesRegex(NativeObservationError, "expected"):
                public_bytes(session, 0x027E3000, size)


if __name__ == "__main__":
    unittest.main()
