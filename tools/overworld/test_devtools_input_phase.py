"""Manual pulses must cross a native poll before their queue is credited."""
import unittest
from unittest.mock import patch
import struct
from tools.overworld.devtools_runtime import DevtoolsFailure

from tools.overworld import test_devtools_runtime as runtime_tests


class InputPhaseTests(unittest.TestCase):
    def fixture(self):
        s, memory, boundary, reads, releases, trace = runtime_tests.CompletedFieldAvailabilityTests.fixture(self)
        s._install_input_poll_fence = lambda: None
        s.snapshot = lambda **kwargs: s.latest_frame
        s.diagnostics = lambda: {}
        s.drain_events = lambda: []
        s.read = lambda address, size: (0x20).to_bytes(4, "little")
        return s, boundary, releases

    def test_after_poll_partial_queue_does_not_release_or_credit_pulse(self):
        s, boundary, releases = self.fixture()
        cycles = []
        def cycle(frames, mask):
            cycles.append(mask)
            if len(cycles) == 1:
                boundary()  # Old poll: the game has not seen LEFT yet.
                self.assertEqual(releases, [])
            else:
                s._input_poll_entered()
                s._input_poll_returned()
                boundary()
        s.cycle = cycle
        result = s.step(1, ["LEFT"])
        self.assertEqual(result["completedGameFrames"], 2)
        self.assertEqual(result["inputConsumedGameFrames"], 1)
        self.assertEqual(len(result["samples"]), 2)
        self.assertEqual(result["nativeCycles"], 2)

    def test_continuous_and_neutral_steps_keep_original_frame_semantics(self):
        for keys, release in ((["LEFT"], False), ([], True)):
            s, boundary, releases = self.fixture()
            s.cycle = lambda frames, mask: boundary()
            result = s.step(1, keys, release_at_end=release)
            self.assertEqual(result["completedGameFrames"], 1)
            self.assertEqual(releases, [] if not release else [0, 0])

    def test_no_poll_or_unmatched_native_input_cannot_succeed(self):
        for fault in ("no-poll", "return-only", "zero-input", "folded"):
            with self.subTest(fault=fault):
                s, boundary, releases = self.fixture()
                if fault == "zero-input":
                    s.read = lambda *_: bytes(4)
                if fault == "folded":
                    s.read = lambda address, size: (0x20 if address == 0x021D1144 else 0).to_bytes(4, "little")
                def cycle(frames, mask):
                    if fault != "no-poll":
                        if fault != "return-only":
                            s._input_poll_entered()
                        s._input_poll_returned()
                    boundary()
                s.cycle = cycle
                with self.assertRaisesRegex(DevtoolsFailure, "only 0/1"):
                    s.step(1, ["LEFT"])
                self.assertIsNone(s.input_step_phase)
                self.assertEqual(releases, [0])

    def test_one_poll_cannot_credit_two_queues(self):
        s, boundary, releases = self.fixture()
        cycles = []
        def cycle(frames, mask):
            cycles.append(mask)
            if len(cycles) != 2:
                s._input_poll_entered()
                s._input_poll_returned()
            boundary()
        s.cycle = cycle
        result = s.step(2, ["LEFT"])
        self.assertEqual(result["completedGameFrames"], 3)
        self.assertEqual(result["inputConsumedGameFrames"], 2)

    def test_poll_hook_install_requires_exact_call_and_packaged_code(self):
        from tools.overworld.devtools_runtime import DevtoolsSession
        s, boundary, releases = self.fixture()
        image = bytearray(0x1A5E8)
        image[0xDB4:0xDB8] = bytes.fromhex("19 f0 92 fb")
        struct.pack_into("<I", image, 0xE64, 0x021D110C)
        hooks = {}
        s.emu.memory.register_exec = lambda address, callback: hooks.update({address: callback})
        s.packaged_code = lambda address, size: bytes(image[address - 0x02000000:address - 0x02000000 + size])
        s.read = s.packaged_code
        with patch("pathlib.Path.read_bytes", return_value=bytes(image)):
            DevtoolsSession._install_input_poll_fence(s)
        self.assertEqual(set(hooks), {0x02000DB4, 0x02000DB8})
        s.input_poll_fence_installed = False
        hooks.clear()
        s.packaged_code = lambda address, size: bytes([255]) * size
        with patch("pathlib.Path.read_bytes", return_value=bytes(image)):
            with self.assertRaisesRegex(DevtoolsFailure, "code differs"):
                DevtoolsSession._install_input_poll_fence(s)
        self.assertEqual(hooks, {})
        s.packaged_code = s.read
        s.read = lambda address, size: bytes([255]) * size
        with patch("pathlib.Path.read_bytes", return_value=bytes(image)):
            with self.assertRaisesRegex(DevtoolsFailure, "live native keypad poll code differs"):
                DevtoolsSession._install_input_poll_fence(s)
        self.assertEqual(hooks, {})


if __name__ == "__main__":
    unittest.main()
