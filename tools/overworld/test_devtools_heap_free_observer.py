"""Focused host checks for prepared ScriptWarp Heap_Free telemetry."""

from types import SimpleNamespace
import struct
import unittest

from tools.overworld.devtools_heap_free_observer import (
    HEAP_INFO, MAX_EVENTS, ScriptWarpHeapFreeObserver,
)
from tools.overworld.devtools_runtime import DevtoolsFailure, STOCK_CALLBACKS


class ScriptWarpHeapFreeObserverTests(unittest.TestCase):
    def fixture(self, *, handle=0x02220000):
        data = bytearray(0x400000)
        base = 0x02000000
        task, environment = 0x02202000, 0x02201010
        heap_handles, heap_indexes = 0x021F0000, 0x021F0100

        def write(address, value):
            data[address - base:address - base + len(value)] = value

        write(HEAP_INFO, struct.pack("<5I4H", heap_handles, 0x021F0200, 0x021F0300,
                                    0x021F0400, heap_indexes, 32, 4, 28, 28))
        write(heap_indexes + 11, bytes([5]))
        write(heap_handles + 5 * 4, struct.pack("<I", handle))
        write(task, struct.pack("<8I", 0x02203000, STOCK_CALLBACKS["script_warp_task"] | 1,
                                7, environment, 0, 0, 0x02200000, 0))
        write(environment, struct.pack("<6i", 2, 33, -1, 579, 394, 0))
        write(environment - 16, bytes(12) + bytes([11, 0, 0, 0]))
        session = SimpleNamespace(completed_frames=812, rt=SimpleNamespace(EXECUTED_FRAME_COUNT=2093))
        session.read = lambda address, size: bytes(data[address - base:address - base + size])
        constructor = {"tasks": [{
            "pointer": task, "function": STOCK_CALLBACKS["script_warp_task"] | 1,
            "environment": environment,
        }]}
        return ScriptWarpHeapFreeObserver(session, constructor), environment, write

    def test_captures_pointer_heap_handle_caller_and_script_warp_state(self):
        observer, pointer, _write = self.fixture()
        observer.observe(pointer, 0x02053779, 0x027E31E0)
        result = observer.finish()
        event = result["events"][0]
        self.assertEqual((event["pointer"], event["headerHeapId"], event["resolvedHandle"]),
                         (pointer, 11, 0x02220000))
        self.assertEqual(event["callerReturn"], 0x02053779)
        self.assertEqual(event["scriptWarp"]["transitionState"], 2)
        self.assertEqual(event["scriptWarp"]["taskState"], 7)
        self.assertTrue(event["ownedEnvironmentFree"])

    def test_invalid_resolved_handle_fails_closed_with_attempt(self):
        observer, pointer, _write = self.fixture(handle=0)
        with self.assertRaises(DevtoolsFailure) as caught:
            observer.observe(pointer, 0x02053779, 0x027E31E0)
        self.assertEqual(caught.exception.code, "script-warp-heap-free-invalid")
        self.assertTrue(caught.exception.fatal)
        self.assertEqual(caught.exception.details["attempt"]["pointer"], pointer)
        with self.assertRaises(DevtoolsFailure):
            observer.check()

    def test_invalid_pointer_fails_before_any_memory_read_is_published(self):
        observer, _pointer, _write = self.fixture()
        with self.assertRaises(DevtoolsFailure) as caught:
            observer.observe(0, 0x02053779, 0x027E31E0)
        self.assertEqual(caught.exception.details["heapFreeObservation"]["eventCount"], 0)

    def test_receipt_retains_only_the_bounded_tail(self):
        observer, pointer, write = self.fixture()
        other_pointer = 0x02210010
        write(other_pointer - 16, bytes(12) + bytes([11, 0, 0, 0]))
        for sequence in range(MAX_EVENTS + 1):
            observer.observe(other_pointer, 0x02053779 + sequence * 2, 0x027E31E0)
        observer.observe(pointer, 0x02053779, 0x027E31E0)
        result = observer.finish()
        self.assertEqual(result["eventCount"], MAX_EVENTS + 2)
        self.assertEqual(result["retainedEventCount"], MAX_EVENTS)
        self.assertEqual(result["droppedEventCount"], 2)


if __name__ == "__main__":
    unittest.main()
