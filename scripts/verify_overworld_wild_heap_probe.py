#!/usr/bin/env python3
"""Focused synthetic-RAM fixture for the read-only Task-8 heap probe."""

from __future__ import annotations

import argparse
import ast
import copy
import contextlib
import hashlib
import io
import json
import struct
from pathlib import Path
import sys
import tempfile
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
from overworld_wild_heap_probe import (  # noqa: E402
    DEFAULT_MUTATION_POINTS,
    EWRAM_END,
    EWRAM_START,
    EXPH_SIGNATURE,
    FREE_NODE_SIGNATURE,
    ExpHeapReader,
    HeapMarginProbe,
    HeapProbeError,
)

BASE = 0x02000000
SIZE = 0x40000
HEAP_INFO = BASE + 0x100
HANDLES = BASE + 0x200
INDEXES = BASE + 0x366
ACTIVE_MASK = BASE + 0x380


class UnsignedMemory:
    def __init__(
        self,
        data: bytearray,
        shape: str = "list",
        overrides: dict[tuple[int, int], object] | None = None,
    ):
        self.data = data
        self.shape = shape
        self.overrides = dict(overrides or {})
        self.accesses: list[tuple[int, int, int]] = []

    def __getitem__(self, key: slice) -> object:
        assert isinstance(key, slice) and key.start is not None and key.stop is not None
        assert key.step == 1
        width = key.stop - key.start
        self.accesses.append((key.start, width, key.step))
        if (key.start, width) in self.overrides:
            return self.overrides[(key.start, width)]
        offset = key.start - BASE
        raw = bytes(self.data[offset : offset + width])
        if self.shape == "list":
            return list(raw)
        if self.shape == "bytes":
            return raw
        if self.shape == "tuple":
            return tuple(raw)
        raise AssertionError(f"unsupported synthetic memory shape: {self.shape}")


class FixedUnsignedMemory:
    def __init__(self, value: object):
        self.value = value

    def __getitem__(self, key: slice) -> object:
        assert isinstance(key, slice) and key.step == 1
        return self.value


class FixedMemory:
    def __init__(self, value: object):
        self.unsigned = FixedUnsignedMemory(value)


class Memory:
    def __init__(
        self,
        data: bytearray,
        shape: str = "list",
        overrides: dict[tuple[int, int], object] | None = None,
    ):
        self.unsigned = UnsignedMemory(data, shape, overrides)
        self.register_arm9 = type("Registers", (), {"r0": 1})()
        self.callbacks = {}

    def register_exec(self, address, callback):
        self.callbacks[address] = callback


class Emulator:
    def __init__(
        self,
        data: bytearray,
        shape: str = "list",
        overrides: dict[tuple[int, int], object] | None = None,
    ):
        self.memory = Memory(data, shape, overrides)


def put(data: bytearray, address: int, fmt: str, *values: int) -> None:
    struct.pack_into("<" + fmt, data, address - BASE, *values)


def make_heap(
    data: bytearray,
    handle: int,
    start: int,
    end: int,
    nodes: tuple[tuple[int, int], ...],
) -> None:
    put(data, handle, "I", EXPH_SIGNATURE)
    put(data, handle + 0x18, "II", start, end)
    put(data, handle + 0x24, "II", nodes[0][0], nodes[-1][0])
    for index, (address, size) in enumerate(nodes):
        previous = nodes[index - 1][0] if index else 0
        following = nodes[index + 1][0] if index + 1 < len(nodes) else 0
        put(data, address, "HHIII", FREE_NODE_SIGNATURE, 0, size, previous, following)


def fixture_memory() -> bytearray:
    data = bytearray(SIZE)
    heap3 = BASE + 0x1000
    heap11 = BASE + 0x4000
    put(data, HEAP_INFO, "IIIIIHHHH", HANDLES, 0, 0, 0, INDEXES, 16, 2, 2, 2)
    put(data, HANDLES, "II", heap3, heap11)
    for heap_id in range(16):
        put(data, INDEXES + heap_id, "B", 2)
    put(data, INDEXES + 3, "B", 0)
    put(data, INDEXES + 11, "B", 1)
    put(data, ACTIVE_MASK, "H", 0x3FF)
    make_heap(data, heap3, BASE + 0x1040, BASE + 0x3000,
        ((BASE + 0x1100, 0x100), (BASE + 0x1400, 0x80)))
    make_heap(data, heap11, BASE + 0x4040, BASE + 0xA000,
        ((BASE + 0x4100, 0x5000),))
    return data


def expect_error(data: bytearray, message: str) -> None:
    global checks
    checks += 1
    try:
        ExpHeapReader(Memory(data), HEAP_INFO).inspect(3)
    except HeapProbeError:
        return
    raise SystemExit("heap probe fixture failed: " + message)


def expect_read_error(value: object, width: int, message: str) -> None:
    global checks
    checks += 1
    reader = ExpHeapReader(FixedMemory(value), HEAP_INFO)
    try:
        {1: reader.u8, 2: reader.u16, 4: reader.u32}[width](BASE)
    except HeapProbeError:
        return
    raise SystemExit("heap probe fixture failed: " + message)


def resolve_index_table_fixture(
    indexes: int,
    *,
    total_heaps: int = 16,
    index_value: object = [0],
    handle_value: int = BASE + 0x1000,
) -> int:
    data = fixture_memory()
    put(data, HEAP_INFO + 0x10, "I", indexes)
    put(data, HEAP_INFO + 0x14, "H", total_heaps)
    put(data, HANDLES, "I", handle_value)
    before = bytes(data)
    overrides = {(indexes + 3, 1): index_value}
    try:
        return ExpHeapReader(
            Memory(data, "list", overrides), HEAP_INFO
        ).resolve_handle(3)
    finally:
        require(bytes(data) == before,
            "heap index-table resolution mutated synthetic RAM")


def expect_index_table_error(
    indexes: int,
    message: str,
    *,
    total_heaps: int = 16,
    index_value: object = [0],
    handle_value: int = BASE + 0x1000,
) -> None:
    global checks
    checks += 1
    try:
        resolve_index_table_fixture(
            indexes,
            total_heaps=total_heaps,
            index_value=index_value,
            handle_value=handle_value,
        )
    except HeapProbeError:
        return
    raise SystemExit("heap probe fixture failed: " + message)


def full_shape_fixture(
    shape: str,
) -> tuple[
    dict[str, object],
    tuple[tuple[int, int, int], ...],
    tuple[tuple[int, int, int], ...],
    bytes,
]:
    data = fixture_memory()
    before = bytes(data)
    memory = Memory(data, shape)
    reader = ExpHeapReader(memory, HEAP_INFO)
    heap3 = reader.inspect(3)
    heap11 = reader.inspect(11)
    require(heap3 is not None and heap3["total_free"] == 0x180,
        f"{shape} traversal heap 3 total differs")
    require(heap3["largest_block"] == 0x100 and heap3["block_count"] == 2,
        f"{shape} traversal heap 3 chain differs")
    require(heap11 is not None and heap11["total_free"] == 0x5000,
        f"{shape} traversal heap 11 total differs")
    require(reader.inspect(2) is None,
        f"{shape} traversal unallocated heap differs")
    required_accesses = {
        (HEAP_INFO, 4, 1),
        (HEAP_INFO + 0x14, 2, 1),
        (INDEXES + 3, 1, 1),
        (INDEXES + 11, 1, 1),
        (HANDLES, 4, 1),
        (HANDLES + 4, 4, 1),
        (BASE + 0x1000, 4, 1),
        (BASE + 0x1024, 4, 1),
        (BASE + 0x1100, 2, 1),
        (BASE + 0x110C, 4, 1),
        (BASE + 0x1400, 2, 1),
        (BASE + 0x140C, 4, 1),
        (BASE + 0x4000, 4, 1),
        (BASE + 0x4100, 2, 1),
    }
    require(required_accesses.issubset(set(memory.unsigned.accesses)),
        f"{shape} traversal skipped a required heap structure")
    direct_trace = tuple(memory.unsigned.accesses)

    emu = Emulator(data, shape)
    probe = HeapMarginProbe(
        emu,
        heap_info_address=HEAP_INFO,
        mutation_points=(BASE + 0x20,),
        minimum_total_free=0x40,
        minimum_largest_block=0x40,
        active_mask_address=ACTIVE_MASK,
    )
    probe.install_callbacks()
    probe.sample("shape_fixture")
    emu.memory.callbacks[BASE + 0x20](BASE + 0x20, 4)
    probe.frame_complete()
    report = probe.report()
    require(report["passed"] and not report["integrity_errors"],
        f"{shape} full report did not pass")
    require(report["ten_slot_fixture"]["proven"],
        f"{shape} full report did not prove ten slots")
    require(report["mutation_hits"][_hex(BASE + 0x20)] == 1,
        f"{shape} full report mutation callback differs")
    require(len(report["epochs"]) == 2
            and all(epoch["samples"] == 3 for epoch in report["epochs"]),
        f"{shape} full report epochs differ")
    require(all(epoch["peak_consumed"] == 0 for epoch in report["epochs"]),
        f"{shape} full report consumption differs")
    require(bytes(data) == before,
        f"{shape} full traversal mutated synthetic RAM")
    probe_trace = tuple(emu.memory.unsigned.accesses)
    published_report = (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return report, direct_trace, probe_trace, published_report


def malformed_traversal_fixture(
    shape: str,
    address: int,
    width: int,
    value: object,
    label: str,
    expected_missing: list[int],
) -> None:
    data = fixture_memory()
    before = bytes(data)
    overrides = {(address, width): value}
    messages = []
    for _ in range(2):
        try:
            ExpHeapReader(Memory(data, shape, overrides), HEAP_INFO).inspect(3)
        except HeapProbeError as error:
            messages.append(str(error))
        else:
            require(False, f"{label} malformed traversal was accepted")
    require(len(messages) == 2 and messages[0] == messages[1],
        f"{label} malformed traversal failure was nondeterministic")

    emu = Emulator(data, shape, overrides)
    probe = HeapMarginProbe(
        emu,
        heap_info_address=HEAP_INFO,
        heap_ids=(3, 11),
        mutation_points=(),
        minimum_total_free=0x40,
        minimum_largest_block=0x40,
    )
    probe.sample(label)
    report = probe.report()
    require(not report["passed"]
            and len(report["integrity_errors"]) == len(expected_missing),
        f"{label} malformed report was accepted")
    require(report["missing_heaps"] == expected_missing
            and all(epoch["heap_id"] not in expected_missing
                    for epoch in report["epochs"]),
        f"{label} malformed report retained partial accepted stats")
    require(sorted(epoch["heap_id"] for epoch in report["epochs"])
            == [heap_id for heap_id in (3, 11)
                if heap_id not in expected_missing],
        f"{label} malformed report lost unaffected heap stats")
    require(bytes(data) == before,
        f"{label} malformed traversal mutated synthetic RAM")


checks = 0


def require(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        raise SystemExit("heap probe fixture failed: " + message)


def main() -> None:
    require(ExpHeapReader(FixedMemory([0xA5]), HEAP_INFO).u8(BASE) == 0xA5,
        "live list u8 shape was not decoded")
    require(ExpHeapReader(FixedMemory([0x34, 0x12]), HEAP_INFO).u16(BASE)
            == 0x1234,
        "live list u16 shape was not decoded little-endian")
    require(ExpHeapReader(
        FixedMemory([0x78, 0x56, 0x34, 0x12]), HEAP_INFO).u32(BASE)
            == 0x12345678,
        "live list u32 shape was not decoded little-endian")
    require(ExpHeapReader(FixedMemory(b"\xEF\xBE"), HEAP_INFO).u16(BASE)
            == 0xBEEF,
        "documented unsigned bytes shape was not decoded little-endian")
    for value, width, message in (
        ([], 1, "empty list was accepted"),
        ([0x12], 2, "short list was accepted"),
        ([0x12, 0x34, 0x56], 2, "long list was accepted"),
        ([-1], 1, "negative byte was accepted"),
        ([0x100], 1, "out-of-range byte was accepted"),
        ([[0x12]], 1, "nested list was accepted"),
        ([True], 1, "boolean byte was accepted"),
        (123, 1, "scalar result was accepted"),
        ("\x12", 1, "string result was accepted"),
        (bytearray((0x12,)), 1, "unexpected bytearray was accepted"),
    ):
        expect_read_error(value, width, message)

    require(resolve_index_table_fixture(0x0226EF66) == BASE + 0x1000,
        "live-style unaligned heap index table was rejected")
    require(resolve_index_table_fixture(BASE + 0x300) == BASE + 0x1000,
        "aligned heap index table was rejected")
    require(resolve_index_table_fixture(EWRAM_START) == BASE + 0x1000,
        "lower-boundary heap index table was rejected")
    require(resolve_index_table_fixture(EWRAM_END - 16) == BASE + 0x1000,
        "complete upper-boundary heap index table was rejected")
    expect_index_table_error(
        EWRAM_START - 1,
        "below-EWRAM heap index table was accepted")
    expect_index_table_error(
        EWRAM_END - 15,
        "truncated upper-boundary heap index table was accepted")
    expect_index_table_error(
        EWRAM_END - 16,
        "heap index table span ignored total heap count",
        total_heaps=17)
    expect_index_table_error(
        EWRAM_END,
        "one-past-EWRAM heap index table was accepted")
    expect_index_table_error(
        0xFFFFFFF8,
        "overflowing heap index table was accepted")
    expect_index_table_error(
        0x0226EF66,
        "out-of-range heap index entry was accepted",
        index_value=[3])
    expect_index_table_error(
        0x0226EF66,
        "unaligned downstream heap handle was accepted",
        handle_value=BASE + 0x1001)

    shape_results = [
        full_shape_fixture(shape) for shape in ("list", "bytes", "tuple")
    ]
    shape_reports = [result[0] for result in shape_results]
    require(shape_reports[1:] == shape_reports[:1] * 2,
        "list/bytes/tuple full traversal reports differ")
    direct_traces = [result[1] for result in shape_results]
    require(direct_traces[1:] == direct_traces[:1] * 2,
        "list/bytes/tuple ordered direct-inspection traces differ")
    probe_traces = [result[2] for result in shape_results]
    require(probe_traces[1:] == probe_traces[:1] * 2,
        "list/bytes/tuple ordered probe/callback traces differ")
    published_reports = [result[3] for result in shape_results]
    require(published_reports[1:] == published_reports[:1] * 2,
        "list/bytes/tuple canonical published report bytes differ")
    malformed_traversal_fixture(
        "list", HEAP_INFO, 4, [0, 0, 0],
        "malformed_heap_info", [3, 11])
    malformed_traversal_fixture(
        "bytes", HANDLES, 4, b"\x00\x00\x00",
        "malformed_handle_table", [3])
    malformed_traversal_fixture(
        "tuple", BASE + 0x1000, 4, (0x48, 0x50, True, 0x45),
        "malformed_expheap_header", [3])
    malformed_traversal_fixture(
        "list", BASE + 0x140C, 4, [[0], 0, 0, 0],
        "malformed_free_node_chain", [3])

    data = fixture_memory()
    reader = ExpHeapReader(Memory(data), HEAP_INFO)
    heap3 = reader.inspect(3)
    heap11 = reader.inspect(11)
    require(heap3 is not None and heap3["total_free"] == 0x180,
        "heap 3 total free differs")
    require(heap3["largest_block"] == 0x100 and heap3["block_count"] == 2,
        "heap 3 largest/count differs")
    require(heap11 is not None and heap11["total_free"] == 0x5000,
        "heap 11 total free differs")
    require(reader.inspect(2) is None, "unallocated heap was not absent")

    corrupt = copy.deepcopy(data)
    put(corrupt, BASE + 0x1100, "H", 0)
    expect_error(corrupt, "bad free-node signature was accepted")
    corrupt = copy.deepcopy(data)
    put(corrupt, BASE + 0x1024, "I", BASE + 0x1400)
    expect_error(corrupt, "wrong free-list head was accepted")
    corrupt = copy.deepcopy(data)
    put(corrupt, BASE + 0x1408, "I", 0)
    expect_error(corrupt, "wrong previous link was accepted")
    corrupt = copy.deepcopy(data)
    put(corrupt, BASE + 0x110C, "I", BASE + 0x1800)
    expect_error(corrupt, "wrong next link was accepted")
    corrupt = copy.deepcopy(data)
    put(corrupt, BASE + 0x140C, "I", BASE + 0x1100)
    expect_error(corrupt, "free-list cycle was accepted")
    corrupt = copy.deepcopy(data)
    put(corrupt, BASE + 0x1028, "I", BASE + 0x1100)
    expect_error(corrupt, "bad free-list tail was accepted")
    corrupt = copy.deepcopy(data)
    put(corrupt, BASE + 0x1104, "I", 3)
    expect_error(corrupt, "unaligned free-node size was accepted")
    corrupt = copy.deepcopy(data)
    put(corrupt, BASE + 0x1000, "I", 0)
    expect_error(corrupt, "bad EXPH signature was accepted")

    emu = Emulator(data)
    probe = HeapMarginProbe(
        emu,
        heap_info_address=HEAP_INFO,
        mutation_points=(BASE + 0x20,),
        minimum_total_free=0x40,
        minimum_largest_block=0x40,
        active_mask_address=ACTIVE_MASK,
    )
    probe.install_callbacks()
    probe.sample("fixture")
    emu.memory.callbacks[BASE + 0x20](BASE + 0x20, 4)
    probe.frame_complete()
    report = probe.report()
    require(report["passed"], "valid synthetic heap report failed")
    require(report["ten_slot_fixture"]["proven"], "ten-slot mask was not proven")
    require(report["mutation_hits"][_hex(BASE + 0x20)] == 1,
        "mutation callback was not counted")
    require(len(report["epochs"]) == 2,
        "heap ID/handle epochs were not tracked independently")
    require(all(epoch["samples"] == 3 for epoch in report["epochs"]),
        "frame and allocator samples were not both retained")
    require(all(epoch["peak_consumed"] == 0 for epoch in report["epochs"]),
        "unchanged heap reported consumption")
    require(not report["allocation_failures"] and not report["integrity_errors"],
        "valid synthetic heap reported failure")

    failed_emu = Emulator(data)
    failed_emu.memory.register_arm9.r0 = 0
    failed_probe = HeapMarginProbe(
        failed_emu,
        heap_info_address=HEAP_INFO,
        mutation_points=(0x020B53C0,),
        minimum_total_free=0x40,
        minimum_largest_block=0x40,
    )
    failed_probe.install_callbacks()
    failed_emu.memory.callbacks[0x020B53C0](0x020B53C0, 4)
    failed_report = failed_probe.report()
    require(not failed_report["passed"]
            and len(failed_report["allocation_failures"]) == 1,
        "zero allocator return was not reported")

    probe_source = Path(__file__).with_name(
        "overworld_wild_heap_probe.py").read_text()
    headless_source = Path(__file__).with_name(
        "headless-overworld-test.py").read_text()
    launcher_source = Path(__file__).with_name(
        "launch_summary_move_relearn_runtime.py").read_text()
    runtime_source = Path(__file__).with_name(
        "verify_summary_move_relearn_runtime.py").read_text()
    require("DEFAULT_HEAP_IDS = (3, 11)" in probe_source,
        "heap 3/11 contract is not fixed")
    require(tuple(DEFAULT_MUTATION_POINTS) == (
        0x020B53C0, 0x020B53CC, 0x020B5400,
        0x020B5450, 0x020B5528, 0x020B5568,
    ), "allocator mutation-point inventory differs")
    require("def write" not in probe_source
            and ".write_" not in probe_source,
        "heap probe exposes a RAM write primitive")
    require("handle + 0x2C" not in probe_source
            and "handle + 0x2E" not in probe_source,
        "heap probe treats ExpHeap reserved header fields as list metadata")
    require("self._byte_span(indexes, total_heaps, \"heap index table\")"
            in probe_source
            and "self._aligned_pointer(indexes, \"heap index table\")"
            not in probe_source,
        "heap index table is not validated as a complete byte span")
    require("--heap-margin-report" in headless_source
            and "heap_phase" in headless_source
            and "NamedTemporaryFile(suffix=\".sav\")" in headless_source
            and "AUTHENTICATED_HEAP_PROBE_CLASS" in headless_source
            and "def run_namespace(" in headless_source,
        "headless heap integration/save isolation differs")
    require("HEAP_PROBE_RELATIVE" in launcher_source
            and "summary_relearn_heap_probe" in launcher_source
            and "AUTHENTICATED_HEAP_PROBE_CLASS" in launcher_source
            and "HEAP_PROBE_RELATIVE: dict(records[HEAP_PROBE_RELATIVE])"
            in launcher_source,
        "launcher does not retain and inject the authenticated heap probe")
    require("HEADLESS.run_namespace(namespace, publish_heap_report=False)"
            in runtime_source,
        "runtime heap mode does not dispatch through retained HEADLESS")

    runtime_tree = ast.parse(runtime_source)
    runtime_functions = {
        node.name: node for node in runtime_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {
            "parse_runtime_address",
            "validate_runtime_option_tokens",
            "validate_runtime_mode_tokens",
            "parse_args",
            "run_heap_diagnostic",
        }
    }
    require(len(runtime_functions) == 5,
        "runtime heap helper fixture surface differs")
    runtime_namespace = {
        "__builtins__": __builtins__,
        "argparse": argparse,
        "hashlib": hashlib,
        "json": json,
        "Path": Path,
        "REPO": Path.cwd(),
        "sys": sys,
        "require": lambda condition, message: (
            None if condition else (_ for _ in ()).throw(RuntimeError(message))
        ),
    }
    exec(compile(ast.Module(
        body=[runtime_functions[name] for name in (
            "parse_runtime_address",
            "validate_runtime_option_tokens",
            "validate_runtime_mode_tokens",
            "parse_args",
            "run_heap_diagnostic",
        )], type_ignores=[]), "<runtime-heap-fixture>", "exec"),
        runtime_namespace)

    parsed = runtime_namespace["parse_args"]([
        "--heap-diagnostic", "--heap-margin-report", "report.json",
        "--heap-info-address", "0x21d1584",
        "--heap-mutation-point", "0x20b53c0",
        "--heap-mutation-point", "0x20b53cc",
        "--heap-action", "wait:1",
        "--heap-action", "heap_phase:map_transition",
        "--no-screenshot",
    ])
    require(parsed.heap_diagnostic
            and parsed.heap_mutation_point == [0x020B53C0, 0x020B53CC]
            and parsed.heap_action
            == ["wait:1", "heap_phase:map_transition"],
        "valid heap option set did not parse canonically")
    for invalid in (
        ["--heap-diagnostic", "--heap-diagnostic"],
        ["--heap-diagnostic", "--heap-margin-report", "a.json",
         "--heap-margin-report", "b.json"],
        ["--heap-diagnostic", "--heap-info-address", "1",
         "--heap-info-address", "2"],
        ["--heap-diagnostic", "--heap-active-mask-address", "1",
         "--heap-active-mask-address", "2"],
        ["--heap-diagnostic", "--no-screenshot", "--no-screenshot"],
        ["--heap-info-address", "not-an-address"],
        ["--heap-action", "wait:1"],
        ["--heap-info-address", "0x21d1584"],
        ["--heap-margin-report", "report.json"],
        ["--heap-mutation-point", "0x20b53c0"],
        ["--heap-active-mask-address", "0x21d1584"],
        ["--no-screenshot"],
        ["--heap-diagnostic", "--expected-probe-raw-sha256", "00"],
        ["--heap-diagnostic", "--scenario", "empty"],
        ["--heap-diagnostic", "--export-raw", "output.sav"],
        ["--dsv", "first.dsv", "--dsv", "second.dsv"],
        ["--rom", "first.nds", "--rom", "second.nds"],
        ["--result-json", "first.json", "--result-json", "second.json"],
        ["--heap-mutation-point", "0x20b53c0",
         "--heap-mutation-point", "0x20b53c0"],
    ):
        rejected = False
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                runtime_namespace["parse_args"](invalid)
        except (RuntimeError, SystemExit):
            rejected = True
        require(rejected, "duplicate/malformed heap options were accepted")

    class RetainedHeadless:
        def __init__(self):
            self.calls = []

        def parse_args(self, arguments):
            self.calls.append(("parse", tuple(arguments)))
            return types.SimpleNamespace(arguments=tuple(arguments))

        def run_namespace(self, namespace, *, publish_heap_report):
            self.calls.append(("run", namespace, publish_heap_report))
            return {"passed": True, "heap_margin": {"passed": True}}

    with tempfile.TemporaryDirectory(prefix="heap-route-fixture-") as temporary:
        root = Path(temporary)
        rom = root / "fixture.nds"
        dsv = root / "fixture.dsv"
        report = root / "heap.json"
        rom.write_bytes(b"rom")
        dsv.write_bytes(b"dsv")
        retained = RetainedHeadless()
        runtime_namespace["HEADLESS"] = retained

        def atomic_report(path, writer):
            writer(path)
            return {
                "path": str(path), "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }

        runtime_namespace["_atomic_artifact_path"] = atomic_report
        arguments = types.SimpleNamespace(
            heap_diagnostic=True, heap_margin_report=report,
            no_screenshot=True, scenario=None, probe_raw=None,
            expected_dsv_sha256=None,
            heap_info_address=0x021D1584,
            heap_mutation_point=[0x020B53C0],
            heap_active_mask_address=None,
            heap_action=["wait:1"],
        )
        routed = runtime_namespace["run_heap_diagnostic"](
            arguments, rom, dsv)
        require(routed["passed"] and report.is_file()
                and retained.calls[-1][0] == "run"
                and retained.calls[-1][2] is False
                and rom.read_bytes() == b"rom" and dsv.read_bytes() == b"dsv",
            "authenticated heap mode did not use retained Namespace dispatch")

    launcher_tree = ast.parse(launcher_source)
    launcher_names = (
        "_stage_zero_result_targets", "_stage_zero_protected_inputs",
        "_stage_zero_canonical_path", "_stage_zero_same_file",
        "_stage_zero_classify_result_targets",
        "_stage_zero_invalidate_classified",
        "_stage_zero_invalidate_results", "_invalidate_results",
    )
    launcher_functions = {
        node.name: node for node in launcher_tree.body
        if isinstance(node, ast.FunctionDef) and node.name in launcher_names
    }
    require(len(launcher_functions) == len(launcher_names),
        "stage-zero heap invalidation fixture surface differs")
    launcher_namespace = {"__builtins__": __builtins__, "os": __import__("os")}
    exec(compile(ast.Module(
        body=[launcher_functions[name] for name in launcher_names],
        type_ignores=[]), "<launcher-heap-fixture>", "exec"),
        launcher_namespace)
    with tempfile.TemporaryDirectory(prefix="heap-invalidation-fixture-") as temporary:
        root = Path(temporary)
        protected = root / "fixture.nds"
        stale = root / "heap.json"
        protected.write_bytes(b"rom")
        stale.write_text("stale")
        failures = launcher_namespace["_stage_zero_invalidate_results"]([
            "--rom", str(protected), "--heap-margin-report", str(stale),
        ])
        require(not failures and not stale.exists(),
            "stale heap report was not invalidated before runtime parsing")
        failures = launcher_namespace["_stage_zero_invalidate_results"]([
            "--rom", str(protected),
            "--heap-margin-report", str(protected),
        ])
        require(bool(failures) and protected.read_bytes() == b"rom",
            "heap report/input alias was not rejected without input mutation")
        for option, name in (
            ("--rom", "fixture.nds"),
            ("--dsv", "fixture.dsv"),
            ("--publication-manifest", "fixture.json"),
        ):
            source = root / name
            source.write_bytes(option.encode())
            alias = root / "missing" / ".." / name
            failures = launcher_namespace["_stage_zero_invalidate_results"]([
                option, str(source), "--heap-margin-report", str(alias),
            ])
            require(bool(failures) and source.read_bytes() == option.encode(),
                f"nonexistent-component alias removed protected {option}")

        safe_result = root / "safe-result.json"
        safe_result.write_text("stale")
        protected_before = protected.read_bytes()
        failures = launcher_namespace["_stage_zero_invalidate_results"]([
            "--result-json", str(safe_result),
            "--heap-margin-report", str(protected),
            "--rom", str(protected),
        ])
        require(bool(failures) and not safe_result.exists()
                and protected.read_bytes() == protected_before,
            "protected report alias prevented safe result invalidation")
        safe_report = root / "safe-report.json"
        safe_report.write_text("stale")
        try:
            launcher_namespace["_invalidate_results"]([
                "--result-json", str(protected),
                "--heap-margin-report", str(safe_report),
                "--rom", str(protected),
            ])
        except RuntimeError:
            pass
        else:
            require(False, "later invalidator accepted a protected result alias")
        require(not safe_report.exists()
                and protected.read_bytes() == protected_before,
            "later invalidator changed classification or retained safe report")
    print(f"heap probe fixture: {checks} checks; read-only ExpHeap parser green")


def _hex(value: int) -> str:
    return f"0x{value:08X}"


if __name__ == "__main__":
    main()
