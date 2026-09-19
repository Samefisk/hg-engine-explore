"""Bounded, read-only Heap_Free telemetry for one prepared ScriptWarp."""

from __future__ import annotations

from copy import deepcopy
import struct

from tools.overworld.devtools_runtime import DevtoolsFailure, STOCK_CALLBACKS, require


HEAP_INFO = 0x021D1584
MAIN_RAM_START = 0x02000000
MAIN_RAM_END = 0x02400000
MAX_EVENTS = 64


def _inside_main_ram(address, size):
    return (type(address) is int and type(size) is int and size >= 0
            and MAIN_RAM_START <= address <= address + size <= MAIN_RAM_END)


class ScriptWarpHeapFreeObserver:
    """Read the stock Heap_Free inputs while one owned ScriptWarp runs.

    The observer changes no guest register or memory. It keeps a bounded tail
    so a long field teardown cannot grow the host receipt without limit.
    """

    def __init__(self, session, constructor):
        self.session = session
        tasks = constructor.get("tasks", []) if isinstance(constructor, dict) else []
        require(len(tasks) > 0, "ScriptWarp constructor has no owned task", "transition-constructor-mismatch")
        task = tasks[0]
        self.task_pointer = task.get("pointer")
        self.environment = task.get("environment")
        self.callback = STOCK_CALLBACKS["script_warp_task"] | 1
        require(task.get("function") == self.callback,
                "ScriptWarp constructor callback differs", "transition-constructor-mismatch")
        require(_inside_main_ram(self.task_pointer, 32) and self.task_pointer % 4 == 0,
                "ScriptWarp task pointer is invalid", "transition-constructor-mismatch")
        require(_inside_main_ram(self.environment, 24) and self.environment % 4 == 0,
                "ScriptWarp environment pointer is invalid", "transition-constructor-mismatch")
        self.events = []
        self.total = 0
        self.dropped = 0
        self.environment_free_seen = False
        self.failure = None
        self.closed = False
        self._heap_layout = None

    def _fail(self, message, attempt, error=None):
        if self.failure is None:
            details = {"heapFreeObservation": self.result(), "attempt": deepcopy(attempt)}
            if error is not None:
                details["readError"] = f"{type(error).__name__}: {error}"
            self.failure = DevtoolsFailure(
                "script-warp-heap-free-invalid", message, fatal=True, details=details)
        raise self.failure

    def _read_exact(self, address, size):
        require(_inside_main_ram(address, size),
                "Heap_Free telemetry read is outside main RAM", "script-warp-heap-free-invalid")
        data = self.session.read(address, size)
        require(isinstance(data, (bytes, bytearray)) and len(data) == size,
                "Heap_Free telemetry read is incomplete", "script-warp-heap-free-invalid")
        return bytes(data)

    def _layout(self):
        if self._heap_layout is not None:
            return self._heap_layout
        data = self._read_exact(HEAP_INFO, 28)
        (heap_handles, _parents, _raw, _counts, heap_indexes,
         total_heaps, templates, max_heaps, unallocated) = struct.unpack("<5I4H", data)
        require(0 < total_heaps <= 0x100 and 0 < max_heaps < 0x100
                and templates <= max_heaps and unallocated == max_heaps,
                "stock heap table limits are invalid", "script-warp-heap-free-invalid")
        require(heap_handles % 4 == 0 and _inside_main_ram(heap_handles, (max_heaps + 1) * 4),
                "stock heap handle table is invalid", "script-warp-heap-free-invalid")
        require(_inside_main_ram(heap_indexes, total_heaps),
                "stock heap index table is invalid", "script-warp-heap-free-invalid")
        self._heap_layout = {
            "heapHandles": heap_handles, "heapIndexes": heap_indexes,
            "totalHeaps": total_heaps, "maxHeaps": max_heaps,
        }
        return self._heap_layout

    def _script_warp_state(self):
        task_data = self._read_exact(self.task_pointer, 32)
        previous, function, task_state, environment, _, _, field, _ = struct.unpack("<8I", task_data)
        require(function == self.callback and environment == self.environment,
                "owned ScriptWarp task identity changed", "script-warp-heap-free-invalid")
        transition_state, map_id, warp_id, x, z, facing = struct.unpack(
            "<6i", self._read_exact(self.environment, 24))
        require(0 <= transition_state <= 3,
                "owned ScriptWarp transition state is invalid", "script-warp-heap-free-invalid")
        return {
            "taskPointer": self.task_pointer, "previous": previous, "function": function,
            "taskState": task_state, "environment": environment, "fieldPointer": field,
            "transitionState": transition_state, "mapId": map_id, "warpId": warp_id,
            "x": x, "z": z, "facing": facing,
        }

    def observe(self, pointer, caller, sp):
        # The owned environment free is the last point at which its state can
        # be read. Ignore later TaskManager cleanup instead of reading freed
        # environment storage.
        if self.closed or self.environment_free_seen:
            return
        attempt = {
            "pointer": pointer & 0xFFFFFFFF, "callerReturn": caller & 0xFFFFFFFF,
            "sp": sp & 0xFFFFFFFF, "frame": self.session.completed_frames,
            "nativeCycle": self.session.rt.EXECUTED_FRAME_COUNT,
        }
        try:
            pointer = attempt["pointer"]
            require(pointer % 4 == 0 and _inside_main_ram(pointer - 16, 16),
                    "Heap_Free pointer is invalid", "script-warp-heap-free-invalid")
            header_address = pointer - 16
            header_heap_id = self._read_exact(header_address, 16)[12]
            layout = self._layout()
            require(header_heap_id < layout["totalHeaps"],
                    "Heap_Free header heap ID is invalid", "script-warp-heap-free-invalid")
            heap_index = self._read_exact(layout["heapIndexes"] + header_heap_id, 1)[0]
            require(heap_index < layout["maxHeaps"],
                    "Heap_Free resolved an unallocated heap index", "script-warp-heap-free-invalid")
            resolved_handle = struct.unpack("<I", self._read_exact(
                layout["heapHandles"] + heap_index * 4, 4))[0]
            require(resolved_handle % 4 == 0 and _inside_main_ram(resolved_handle, 4),
                    "Heap_Free resolved a null or invalid heap handle", "script-warp-heap-free-invalid")
            event = {**attempt, "headerAddress": header_address,
                     "headerHeapId": header_heap_id, "heapIndex": heap_index,
                     "resolvedHandle": resolved_handle,
                     "scriptWarp": self._script_warp_state(),
                     "ownedEnvironmentFree": pointer == self.environment}
        except Exception as error:
            self._fail("prepared ScriptWarp Heap_Free telemetry rejected invalid state", attempt, error)
        self.total += 1
        self.environment_free_seen |= event["ownedEnvironmentFree"]
        self.events.append(event)
        if len(self.events) > MAX_EVENTS:
            self.events.pop(0)
            self.dropped += 1

    def check(self):
        if self.failure is not None:
            raise self.failure

    def finish(self):
        self.check()
        require(self.environment_free_seen,
                "completed ScriptWarp did not free its owned environment",
                "script-warp-heap-free-missing")
        self.closed = True
        return self.result()

    def result(self):
        return {
            "schemaVersion": 1,
            "scope": "read-only Heap_Free entries during one prepared ScriptWarp",
            "taskPointer": self.task_pointer,
            "environment": self.environment,
            "eventCount": self.total,
            "retainedEventCount": len(self.events),
            "droppedEventCount": self.dropped,
            "maximumRetainedEvents": MAX_EVENTS,
            "ownedEnvironmentFreeSeen": self.environment_free_seen,
            "closed": self.closed,
            "events": deepcopy(self.events),
        }
