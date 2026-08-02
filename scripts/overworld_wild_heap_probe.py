"""Read-only Nitro ExpHeap margin probe for Task-8 headless verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EXPH_SIGNATURE = 0x45585048
FREE_NODE_SIGNATURE = 0x4652
EWRAM_START = 0x02000000
EWRAM_END = 0x02400000
DEFAULT_HEAP_INFO_ADDRESS = 0x021D1584
DEFAULT_HEAP_IDS = (3, 11)
DEFAULT_MUTATION_POINTS = (
    0x020B53C0,
    0x020B53CC,
    0x020B5400,
    0x020B5450,
    0x020B5528,
    0x020B5568,
)
ALLOCATOR_RETURN_POINTS = frozenset((0x020B53C0, 0x020B53CC))
MINIMUM_MARGIN = 0x4000


class HeapProbeError(RuntimeError):
    pass


def _hex(value: int) -> str:
    return f"0x{value:08X}"


@dataclass
class HeapEpochStats:
    heap_id: int
    handle: int
    created_total_free: int
    minimum_total_free: int
    minimum_largest_block: int
    minimum_block_count: int
    maximum_block_count: int
    current_total_free: int
    current_largest_block: int
    current_block_count: int
    samples: int = 0
    phases: set[str] = field(default_factory=set)

    def update(self, sample: dict[str, int], phase: str) -> None:
        total = sample["total_free"]
        largest = sample["largest_block"]
        count = sample["block_count"]
        self.minimum_total_free = min(self.minimum_total_free, total)
        self.minimum_largest_block = min(self.minimum_largest_block, largest)
        self.minimum_block_count = min(self.minimum_block_count, count)
        self.maximum_block_count = max(self.maximum_block_count, count)
        self.current_total_free = total
        self.current_largest_block = largest
        self.current_block_count = count
        self.samples += 1
        self.phases.add(phase)

    def as_dict(self) -> dict[str, Any]:
        return {
            "heap_id": self.heap_id,
            "handle": _hex(self.handle),
            "created_total_free": self.created_total_free,
            "minimum_total_free": self.minimum_total_free,
            "minimum_largest_block": self.minimum_largest_block,
            "block_count": {
                "minimum": self.minimum_block_count,
                "maximum": self.maximum_block_count,
                "current": self.current_block_count,
            },
            "current_total_free": self.current_total_free,
            "current_largest_block": self.current_largest_block,
            "peak_consumed": max(
                0, self.created_total_free - self.minimum_total_free
            ),
            "samples": self.samples,
            "phases": sorted(self.phases),
        }


class ExpHeapReader:
    """Value-only RAM reader; this class deliberately has no write method."""

    def __init__(self, memory: Any, heap_info_address: int):
        self.memory = memory
        self.heap_info_address = heap_info_address

    def _read_unsigned(self, address: int, width: int) -> int:
        raw = self.memory.unsigned[address : address + width : 1]
        if isinstance(raw, bytes):
            values: bytes | list[int] | tuple[int, ...] = raw
        elif type(raw) in (list, tuple):
            values = raw
        else:
            raise HeapProbeError(
                f"u{width * 8} read returned unexpected type: "
                f"{type(raw).__name__}"
            )
        if len(values) != width:
            raise HeapProbeError(
                f"u{width * 8} read returned {len(values)} bytes, "
                f"expected {width}"
            )
        result = 0
        for index, value in enumerate(values):
            if type(value) is not int or not 0 <= value <= 0xFF:
                raise HeapProbeError(
                    f"u{width * 8} read byte {index} is not canonical u8"
                )
            result |= value << (index * 8)
        return result

    def u8(self, address: int) -> int:
        return self._read_unsigned(address, 1)

    def u16(self, address: int) -> int:
        return self._read_unsigned(address, 2)

    def u32(self, address: int) -> int:
        return self._read_unsigned(address, 4)

    @staticmethod
    def _aligned_pointer(value: int, label: str, *, nullable: bool = False) -> None:
        if nullable and value == 0:
            return
        if value & 3 or not EWRAM_START <= value < EWRAM_END:
            raise HeapProbeError(f"{label} is outside aligned EWRAM: {_hex(value)}")

    @staticmethod
    def _byte_span(value: int, size: int, label: str) -> None:
        if (size <= 0 or value < EWRAM_START
                or size > EWRAM_END - EWRAM_START
                or value > EWRAM_END - size):
            raise HeapProbeError(
                f"{label} span escapes EWRAM: {_hex(value)}+{size}"
            )

    def resolve_handle(self, heap_id: int) -> int:
        if not 0 <= heap_id <= 0xFF:
            raise HeapProbeError(f"heap ID is not u8: {heap_id}")
        handles = self.u32(self.heap_info_address + 0x00)
        indexes = self.u32(self.heap_info_address + 0x10)
        total_heaps = self.u16(self.heap_info_address + 0x14)
        max_heaps = self.u16(self.heap_info_address + 0x18)
        unallocated = self.u16(self.heap_info_address + 0x1A)
        if handles == 0 or indexes == 0 or total_heaps == 0:
            return 0
        self._aligned_pointer(handles, "heap handle table")
        # HeapInfo.heapIdxs is a byte-addressed u8[totalNumHeaps] allocation,
        # immediately following a u16 array.  Its base may therefore be odd;
        # only its complete runtime-sized span must remain inside EWRAM.
        self._byte_span(indexes, total_heaps, "heap index table")
        if heap_id >= total_heaps:
            raise HeapProbeError(
                f"heap {heap_id} exceeds total heap count {total_heaps}"
            )
        index = self.u8(indexes + heap_id)
        if index == unallocated:
            return 0
        if index >= max_heaps:
            raise HeapProbeError(
                f"heap {heap_id} index {index} exceeds handle count {max_heaps}"
            )
        handle = self.u32(handles + index * 4)
        if handle == 0:
            raise HeapProbeError(f"heap {heap_id} has an allocated index but null handle")
        self._aligned_pointer(handle, f"heap {heap_id} handle")
        return handle

    def inspect(self, heap_id: int) -> dict[str, int] | None:
        handle = self.resolve_handle(heap_id)
        if handle == 0:
            return None
        if self.u32(handle) != EXPH_SIGNATURE:
            raise HeapProbeError(
                f"heap {heap_id} handle {_hex(handle)} lacks EXPH signature"
            )
        heap_start = self.u32(handle + 0x18)
        heap_end = self.u32(handle + 0x1C)
        self._aligned_pointer(heap_start, f"heap {heap_id} start")
        self._aligned_pointer(heap_end, f"heap {heap_id} end")
        if not handle < heap_start < heap_end <= EWRAM_END:
            raise HeapProbeError(
                f"heap {heap_id} bounds are invalid: "
                f"{_hex(heap_start)}..{_hex(heap_end)}"
            )

        head = self.u32(handle + 0x24)
        tail = self.u32(handle + 0x28)
        if head == 0:
            if tail != 0:
                raise HeapProbeError(f"heap {heap_id} empty free-list metadata differs")
            return {
                "heap_id": heap_id,
                "handle": handle,
                "heap_start": heap_start,
                "heap_end": heap_end,
                "total_free": 0,
                "largest_block": 0,
                "block_count": 0,
            }

        total = 0
        largest = 0
        count = 0
        previous = 0
        previous_end = heap_start
        current = head
        seen: set[int] = set()
        while current != 0:
            self._aligned_pointer(current, f"heap {heap_id} free node")
            if current in seen:
                raise HeapProbeError(f"heap {heap_id} free-list cycle at {_hex(current)}")
            seen.add(current)
            if not heap_start <= current or current + 0x10 > heap_end:
                raise HeapProbeError(
                    f"heap {heap_id} free node {_hex(current)} escapes bounds"
                )
            if current < previous_end:
                raise HeapProbeError(
                    f"heap {heap_id} free-list ordering/overlap differs"
                )
            if self.u16(current) != FREE_NODE_SIGNATURE:
                raise HeapProbeError(
                    f"heap {heap_id} free node {_hex(current)} lacks FR signature"
                )
            size = self.u32(current + 0x04)
            prev_link = self.u32(current + 0x08)
            next_link = self.u32(current + 0x0C)
            if size == 0 or size & 3 or current + 0x10 + size > heap_end:
                raise HeapProbeError(
                    f"heap {heap_id} free node {_hex(current)} has invalid size {size}"
                )
            if prev_link != previous:
                raise HeapProbeError(
                    f"heap {heap_id} free node {_hex(current)} previous link differs"
                )
            if next_link != 0:
                self._aligned_pointer(next_link, f"heap {heap_id} next free node")
                if next_link <= current:
                    raise HeapProbeError(
                        f"heap {heap_id} free-list next link is unordered"
                    )
            total += size
            largest = max(largest, size)
            count += 1
            previous = current
            previous_end = current + 0x10 + size
            current = next_link
            if count > (heap_end - heap_start) // 0x10:
                raise HeapProbeError(
                    f"heap {heap_id} free-list count/cycle bound exceeded"
                )
        if previous != tail:
            raise HeapProbeError(
                f"heap {heap_id} free-list tail differs: "
                f"tail={_hex(tail)} visited={_hex(previous)}"
            )
        return {
            "heap_id": heap_id,
            "handle": handle,
            "heap_start": heap_start,
            "heap_end": heap_end,
            "total_free": total,
            "largest_block": largest,
            "block_count": count,
        }


class HeapMarginProbe:
    def __init__(
        self,
        emu: Any,
        *,
        heap_info_address: int = DEFAULT_HEAP_INFO_ADDRESS,
        heap_ids: tuple[int, ...] = DEFAULT_HEAP_IDS,
        mutation_points: tuple[int, ...] = DEFAULT_MUTATION_POINTS,
        minimum_total_free: int = MINIMUM_MARGIN,
        minimum_largest_block: int = MINIMUM_MARGIN,
        active_mask_address: int | None = None,
        expected_active_mask: int = 0x3FF,
    ):
        self.emu = emu
        self.reader = ExpHeapReader(emu.memory, heap_info_address)
        self.heap_info_address = heap_info_address
        self.heap_ids = heap_ids
        self.mutation_points = mutation_points
        self.minimum_total_free = minimum_total_free
        self.minimum_largest_block = minimum_largest_block
        self.active_mask_address = active_mask_address
        self.expected_active_mask = expected_active_mask
        self.frame = 0
        self.phase = "initial_load"
        self.stats: dict[tuple[int, int], HeapEpochStats] = {}
        self.integrity_errors: list[str] = []
        self.allocation_failures: list[dict[str, Any]] = []
        self.mutation_hits: dict[int, int] = {
            address: 0 for address in mutation_points
        }
        self.observed_phases: set[str] = set()
        self.ten_slot_proven = False
        self._callbacks: list[Any] = []

    def install_callbacks(self) -> None:
        for address in self.mutation_points:
            def callback(callback_address: int, _size: int, address=address) -> None:
                self._sample_mutation(address, callback_address)

            self._callbacks.append(callback)
            self.emu.memory.register_exec(address, callback)

    def set_phase(self, phase: str) -> None:
        if not phase or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_" for character in phase):
            raise ValueError("heap phase must be nonempty lowercase snake_case")
        self.phase = phase

    def _sample_mutation(self, configured_address: int, callback_address: int) -> None:
        self.mutation_hits[configured_address] += 1
        if configured_address in ALLOCATOR_RETURN_POINTS:
            result = int(self.emu.memory.register_arm9.r0) & 0xFFFFFFFF
            if result == 0:
                self.allocation_failures.append({
                    "frame": self.frame,
                    "phase": self.phase,
                    "address": _hex(callback_address),
                })
        self.sample(f"allocator@{configured_address:08X}")

    def sample(self, source: str = "frame") -> None:
        self.observed_phases.add(self.phase)
        if self.active_mask_address is not None:
            mask = self.reader.u16(self.active_mask_address)
            if mask == self.expected_active_mask:
                self.ten_slot_proven = True
        for heap_id in self.heap_ids:
            try:
                sample = self.reader.inspect(heap_id)
            except HeapProbeError as error:
                self.integrity_errors.append(
                    f"frame={self.frame} phase={self.phase} source={source}: {error}"
                )
                continue
            if sample is None:
                continue
            key = (heap_id, sample["handle"])
            stats = self.stats.get(key)
            if stats is None:
                stats = HeapEpochStats(
                    heap_id=heap_id,
                    handle=sample["handle"],
                    created_total_free=sample["total_free"],
                    minimum_total_free=sample["total_free"],
                    minimum_largest_block=sample["largest_block"],
                    minimum_block_count=sample["block_count"],
                    maximum_block_count=sample["block_count"],
                    current_total_free=sample["total_free"],
                    current_largest_block=sample["largest_block"],
                    current_block_count=sample["block_count"],
                )
                self.stats[key] = stats
            stats.update(sample, self.phase)

    def frame_complete(self) -> None:
        self.frame += 1
        self.sample()

    def report(self) -> dict[str, Any]:
        epochs = [stats.as_dict() for stats in self.stats.values()]
        missing_heaps = [
            heap_id for heap_id in self.heap_ids
            if not any(stats.heap_id == heap_id for stats in self.stats.values())
        ]
        below_margin = [
            {
                "heap_id": stats.heap_id,
                "handle": _hex(stats.handle),
                "minimum_total_free": stats.minimum_total_free,
                "minimum_largest_block": stats.minimum_largest_block,
            }
            for stats in self.stats.values()
            if stats.minimum_total_free < self.minimum_total_free
            or stats.minimum_largest_block < self.minimum_largest_block
        ]
        unhit_points = [
            _hex(address) for address, hits in self.mutation_hits.items()
            if hits == 0
        ]
        passed = not (
            missing_heaps
            or below_margin
            or self.integrity_errors
            or self.allocation_failures
        )
        return {
            "contract": "task8-expheap-read-only-v1",
            "heap_info_address": _hex(self.heap_info_address),
            "heap_ids": list(self.heap_ids),
            "minimum_total_free_required": self.minimum_total_free,
            "minimum_largest_block_required": self.minimum_largest_block,
            "frames_sampled": self.frame,
            "epochs": epochs,
            "mutation_hits": {
                _hex(address): hits
                for address, hits in self.mutation_hits.items()
            },
            "unhit_mutation_points": unhit_points,
            "allocation_failures": self.allocation_failures,
            "integrity_errors": self.integrity_errors,
            "missing_heaps": missing_heaps,
            "below_margin": below_margin,
            "observed_phases": sorted(self.observed_phases),
            "ten_slot_fixture": {
                "mask_address": (
                    _hex(self.active_mask_address)
                    if self.active_mask_address is not None else None
                ),
                "expected_mask": f"0x{self.expected_active_mask:X}",
                "proven": self.ten_slot_proven,
            },
            "passed": passed,
        }
