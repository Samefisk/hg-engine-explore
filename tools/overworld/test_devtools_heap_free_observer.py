"""Focused host checks for prepared ScriptWarp Heap_Free telemetry."""

from types import SimpleNamespace
from copy import deepcopy
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld.devtools_heap_free_observer import (
    HEAP_INFO, MAX_EVENTS, ScriptWarpHeapFreeObserver, QueryAllocationLifecycleObserver,
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


class QueryAllocationLifecycleTests(unittest.TestCase):
    """Run real reader callbacks with a bounded fake native memory/heap."""

    def ops_fixture(self, *, kind=1, flags=6, size=24):
        address = 0x023D7E34
        body = struct.pack("<6I", 0x023CE295, 0x0201AB0D, 0x020D2894,
                           0x020D28B8, 0x020D28D0, 0x023CE05D)
        names = b"\0.text\0.symtab\0.strtab\0.shstrtab\0"
        labels = b"\0sOverworldWildQueryCodeOps\0"
        symbols = bytes(16) + struct.pack("<IIIBBH", 1, address, size, kind, 0, 1)
        image, sections = bytearray(52), [(0,) * 10]
        for name, section_kind, section_flags, base, data, link, entry in (
            (".text", 1, flags, address, body, 0, 0),
            (".symtab", 2, 0, 0, symbols, 3, 16),
            (".strtab", 3, 0, 0, labels, 0, 0),
            (".shstrtab", 3, 0, 0, names, 0, 0),
        ):
            sections.append((names.index(name.encode()), section_kind, section_flags,
                             base, len(image), len(data), link, 0, 4, entry))
            image.extend(data)
        table = len(image)
        for section in sections:
            image.extend(struct.pack("<10I", *section))
        image[:7] = b"\x7fELF\x01\x01\x01"
        struct.pack_into("<I", image, 32, table)
        struct.pack_into("<3H", image, 46, 40, len(sections), 4)
        return bytes(image), address, body

    def test_packaged_typed_data_ops_supply_exact_bytes_without_live_reads(self):
        image, address, body = self.ops_fixture()
        observer = QueryAllocationLifecycleObserver(SimpleNamespace(code_regions=[(address, body)]))
        with tempfile.TemporaryDirectory() as directory:
            linked = Path(directory) / "wild.o"
            linked.write_bytes(image)
            self.assertEqual(observer._linked_ops(linked), (address, body))

    def test_data_ops_reject_wrong_type_extent_section_or_rom(self):
        for fault in ("kind", "size", "section", "rom"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                image, address, body = self.ops_fixture(
                    kind=2 if fault == "kind" else 1,
                    size=20 if fault == "size" else 24,
                    flags=2 if fault == "section" else 6)
                observer = QueryAllocationLifecycleObserver(SimpleNamespace(
                    code_regions=[(address, bytes(24) if fault == "rom" else body)]))
                linked = Path(directory) / "wild.o"
                linked.write_bytes(image)
                with self.assertRaises((ValueError, DevtoolsFailure)):
                    observer._linked_ops(linked)

    def fixture(self):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY
        memory = {}
        def write(address, data):
            for i, byte in enumerate(data):
                memory[address + i] = byte
        def read(address, size):
            return bytes(memory.get(address + i, 0) for i in range(size))
        regs = SimpleNamespace(r0=0, r1=0, r2=0, r3=0, lr=0, sp=0x027E3000)
        heap = {"heapId": 4, "known": True, "allocated": True, "handle": 0x02200000,
                "heapStart": 0x02200040, "heapEnd": 0x02300000, "allocationCount": 10,
                "totalFreeBytes": 200000, "largestUserAllocationBytes": 160000}
        owner = {"known": True, "rawHex": bytes(28).hex(), "phase": 0, "blob": 0,
                 "fieldIdentity": 0x02202000, "entry": 0}
        class Hooks:
            def __init__(self):
                self.callbacks, self.removed = [], []
            def observe_call(self, address, before, after):
                token = (address, before, after)
                self.callbacks.append(token)
                return token
            def remove(self, token):
                self.removed.append(token)
        session = SimpleNamespace(completed_frames=381,
            rt=SimpleNamespace(EXECUTED_FRAME_COUNT=921, WILD_STATE=0x02320000),
            emu=SimpleNamespace(memory=SimpleNamespace(register_arm9=regs)),
            party_getter_hooks=Hooks(), read=read,
            field_pointer=lambda: 0x02202000,
            _query_owner_diagnostics=lambda: deepcopy(owner),
            _heap_diagnostics=lambda: {"known": True, "heaps": [deepcopy(heap)],
                                      "bytesRead": 400, "readBudgetBytes": 8192,
                                      "codeIdentity": []})
        session.packaged_code = read
        observer = QueryAllocationLifecycleObserver(session)
        observer.installed = True
        observer.bodies = {key: (address, bytes([i + 1]) * 200, False)
            for i, (key, address) in enumerate((("load", 0x023CE000),
                ("drain", 0x023CE200), ("unload", 0x023C2400), ("acquire", 0x02210080)))}
        for address, body, _dynamic in observer.bodies.values():
            write(address, body)
        observer.ops = (0x023D7E00, bytes(24))
        observer.elf = observer.staged = observer.member = b"fixture"
        observer.image = bytes(400)
        observer.receipt = {}
        observer.acquire_owner = (0x02080040, 156, "fixture")
        write(session.rt.WILD_STATE + 0xE0, struct.pack("<2I", 0x02202000, 0x022F0000))
        write(0x022F0000 + RUNTIME_QUERY, bytes(4))
        return observer, regs, heap, owner, write

    def allocated(self, fixture, pointer, size, caller):
        observer, regs, heap, _owner, write = fixture
        regs.r0, regs.r1, regs.lr = 4, size, caller | 1
        value = observer._allocate_before()
        write(pointer - 16, bytes(12) + bytes([4, 0, 0, 0]))
        heap["totalFreeBytes"] -= size + 32
        heap["allocationCount"] += 1
        regs.r0 = pointer
        observer._allocate_after(value)
        return value

    def package(self, fixture):
        observer, regs, _heap, owner, write = fixture
        regs.r0, regs.r1, regs.r2, regs.r3 = 21, observer.PACKAGE_BYTES, 0x027E2000, 0x027E2004
        load = observer._load_before()
        allocation = self.allocated(fixture, 0x02210010, observer.PACKAGE_BYTES,
                                    observer.bodies["load"][0] + 20)
        write(load["blobOut"], struct.pack("<I", allocation["pointer"]))
        write(load["sizeOut"], struct.pack("<I", observer.PACKAGE_BYTES))
        regs.r0 = 1
        observer._load_after(load)
        owner.update(rawHex="published", phase=1, blob=allocation["pointer"],
                     entry=allocation["pointer"] + 64)
        regs.r0 = owner["entry"]
        with patch("tools.overworld.devtools_query_observer.authenticate_loaded_query_functions",
                   return_value={"entry": owner["entry"]}), \
                patch("tools.overworld.devtools_query_observer.relocated_image", return_value=bytes(400)):
            observer._discover_after({})
        return allocation

    def workspace(self, fixture):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY
        observer, regs, _heap, _owner, write = fixture
        write(0x027E2100, struct.pack("<6I", 0x027E2200, 0, 0, observer.HEAP_ALLOC | 1,
                                     0x0201ABED, 4) + bytes(8))
        # Native World v3: Field at +4, State at +8.
        write(0x027E2200, struct.pack("<HH2I", 3, 84, observer.current["field"],
                                     observer.session.rt.WILD_STATE) + bytes(72))
        regs.r0 = 0x027E2100
        acquired = observer._acquire_before()
        allocation = self.allocated(fixture, 0x02230010, observer.WORKSPACE_BYTES,
                                    observer.bodies["acquire"][0] + 20)
        write(acquired["runtime"] + RUNTIME_QUERY, struct.pack("<I", allocation["pointer"]))
        regs.r0 = allocation["pointer"]
        observer._acquire_after(acquired)
        return allocation

    def freed(self, fixture, allocation, caller):
        observer, regs, heap, _owner, _write = fixture
        regs.r0, regs.lr = allocation["pointer"], caller | 1
        value = observer._free_before()
        heap["totalFreeBytes"] += allocation["bytes"] + 32
        heap["allocationCount"] -= 1
        observer._free_after(value)
        return value

    def test_exact_cold_load_workspace_drain_and_free_preserve_heap_owner(self):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY
        fixture = self.fixture()
        observer, regs, heap, owner, write = fixture
        package = self.package(fixture)
        workspace = self.workspace(fixture)
        self.assertFalse(observer.result()["complete"])
        owner["phase"] = 2
        regs.r0, regs.r1, regs.r2 = 0x023C2308, observer.ops[0], observer.current["runtime"]
        unload = observer._unload_before()
        regs.r0 = observer.current["runtime"]
        drain = observer._drain_before()
        self.freed(fixture, workspace, observer.bodies["drain"][0] + 20)
        write(drain["runtime"] + RUNTIME_QUERY, bytes(4))
        regs.r0 = 1
        observer._drain_after(drain)
        owner.update(rawHex=bytes(28).hex(), phase=0, blob=0)
        self.freed(fixture, package, observer.bodies["unload"][0] + 20)
        regs.r0 = 0
        observer._unload_after(unload)
        result = observer.result()
        self.assertTrue(result["known"])
        self.assertTrue(result["complete"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual([row["bytes"] for row in result["allocations"]], [70096, 43516])
        self.assertEqual([row["freeCount"] for row in result["allocations"]], [1, 1])
        self.assertEqual(heap["totalFreeBytes"], 200000)
        self.assertEqual(heap["allocationCount"], 10)
        self.assertEqual(package["ownerBeforeLoad"]["rawHex"], bytes(28).hex())
        self.assertEqual(package["heapBeforeLoad"]["boundary"], "native-LoadCodeAddonBlob-entry")
        self.assertEqual((observer.session.completed_frames, observer.session.rt.EXECUTED_FRAME_COUNT), (381, 921))

    def test_package_only_unload_binds_late_current_runtime_and_empty_drain(self):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY
        observer, regs, heap, owner, write = fixture = self.fixture()
        state = observer.session.rt.WILD_STATE
        runtime = 0x022F0000
        write(state + 0xE4, bytes(4))
        package = self.package(fixture)
        self.assertIsNone(observer.current["runtime"])
        # Native Wild creates its runtime after publishing the cold image.
        # No AcquireQuery or workspace allocation occurs before this unload.
        write(state + 0xE4, struct.pack("<I", runtime))
        write(runtime + RUNTIME_QUERY, bytes(4))
        owner["phase"] = 2
        regs.r0, regs.r1, regs.r2 = 0x023C2308, observer.ops[0], runtime
        unload = observer._unload_before()
        self.assertEqual(observer.current["runtime"], runtime)
        regs.r0 = runtime
        drain = observer._drain_before()
        self.assertIsNone(drain["allocation"])
        regs.r0 = 1
        observer._drain_after(drain)
        owner.update(rawHex=bytes(28).hex(), phase=0, blob=0)
        self.freed(fixture, package, observer.bodies["unload"][0] + 20)
        regs.r0 = 0
        observer._unload_after(unload)
        result = observer.result()
        self.assertTrue(result["known"])
        self.assertFalse(result["complete"])  # No workspace proof is inferred.
        self.assertFalse(result["acceptedProof"])
        self.assertEqual([row["kind"] for row in result["allocations"]], ["package"])
        self.assertEqual(result["allocations"][0]["freeCount"], 1)
        self.assertIsNone(observer.current)
        self.assertEqual((heap["totalFreeBytes"], heap["allocationCount"]), (200000, 10))

    def test_package_only_unload_rejects_foreign_field_runtime_and_workspace(self):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY
        for fault in ("owner-field", "wild-field", "argument-runtime", "invalid-runtime",
                      "workspace", "table", "ops", "blob", "phase"):
            with self.subTest(fault=fault):
                observer, regs, _heap, owner, write = fixture = self.fixture()
                self.package(fixture)
                runtime = 0x022F0000
                regs.r0, regs.r1, regs.r2 = 0x023C2308, observer.ops[0], runtime
                if fault == "owner-field": owner["fieldIdentity"] += 4
                if fault == "wild-field":
                    write(observer.session.rt.WILD_STATE + 0xE0, struct.pack("<I", owner["fieldIdentity"] + 4))
                if fault == "argument-runtime": regs.r2 = runtime + 4
                if fault == "invalid-runtime":
                    write(observer.session.rt.WILD_STATE + 0xE4, struct.pack("<I", runtime + 1))
                if fault == "workspace": write(runtime + RUNTIME_QUERY, struct.pack("<I", 0x02230010))
                if fault == "table": regs.r0 += 4
                if fault == "ops": regs.r1 += 4
                if fault == "blob": owner["blob"] += 4
                if fault == "phase": owner["phase"] = 3
                with self.assertRaisesRegex(DevtoolsFailure, "Unload owner differs|Wild runtime owner differs"):
                    observer._unload_before()
                self.assertIsNone(observer.current["runtime"])
                self.assertEqual(observer.unloads, [])
                self.assertEqual([row["kind"] for row in observer.allocations], ["package"])
                self.assertEqual(observer.allocations[0]["freeCount"], 0)

    def test_package_only_unload_preserves_null_runtime_and_known_runtime_rejection(self):
        observer, regs, _heap, _owner, write = fixture = self.fixture()
        self.package(fixture)
        write(observer.session.rt.WILD_STATE + 0xE4, bytes(4))
        regs.r0, regs.r1, regs.r2 = 0x023C2308, observer.ops[0], 0
        observer._unload_before()
        self.assertIsNone(observer.current["runtime"])
        regs.r0 = 0
        self.assertIsNone(observer._drain_before()["allocation"])
        # A previously observed workspace owner must never be replaced by
        # a different runtime, even if that other runtime has no workspace.
        observer, regs, _heap, _owner, _write = fixture = self.fixture()
        self.package(fixture)
        self.workspace(fixture)
        known = observer.current["runtime"]
        regs.r0, regs.r1, regs.r2 = 0x023C2308, observer.ops[0], known + 4
        with self.assertRaisesRegex(DevtoolsFailure, "Unload owner differs"):
            observer._unload_before()
        self.assertEqual(observer.current["runtime"], known)
        self.assertEqual(observer.unloads, [])

    def test_reserve_contiguous_space_wrong_heap_and_allocator_owner_reject(self):
        for fault in ("reserve", "largest", "heap", "caller", "count-limit"):
            with self.subTest(fault=fault):
                observer, regs, heap, _owner, _write = fixture = self.fixture()
                regs.r0, regs.r1, regs.r2, regs.r3 = 21, 70096, 0x027E2000, 0x027E2004
                observer._load_before()
                regs.r0, regs.r1, regs.lr = 4, 70096, observer.bodies["load"][0] + 21
                if fault == "reserve": heap["totalFreeBytes"] = 70096 + 32767
                if fault == "largest": heap["largestUserAllocationBytes"] = 69599
                if fault == "heap": regs.r0 = 11
                if fault == "caller": regs.lr = 0x0201AAAA
                if fault == "count-limit": observer.allocations = [{}] * observer.MAX_ALLOCATIONS
                with self.assertRaises(DevtoolsFailure): observer._allocate_before()
                if fault in ("heap", "caller", "count-limit"):
                    self.assertIsNone(observer.rejected_allocation_request)

    def test_rejected_workspace_request_keeps_exact_entry_heap_without_success_credit(self):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY
        for fault in ("reserve", "contiguous"):
            with self.subTest(fault=fault):
                observer, regs, heap, owner, write = fixture = self.fixture()
                self.package(fixture)
                workspace = self.workspace(fixture)
                owner["phase"] = 2
                regs.r0 = observer.current["runtime"]
                drain = observer._drain_before()
                self.freed(fixture, workspace, observer.bodies["drain"][0] + 20)
                write(drain["runtime"] + RUNTIME_QUERY, bytes(4))
                regs.r0 = 1
                observer._drain_after(drain)
                owner["phase"] = 1
                regs.r0 = 0x027E2100
                acquired = observer._acquire_before()
                self.assertIsNone(acquired["allocation"])
                heap.update(totalFreeBytes=100572, largestUserAllocationBytes=48020)
                if fault == "reserve": heap["totalFreeBytes"] = 43516 + 32767
                if fault == "contiguous": heap["largestUserAllocationBytes"] = 43515
                regs.r0, regs.r1, regs.lr = 4, 43516, observer.bodies["acquire"][0] + 21
                with self.assertRaisesRegex(DevtoolsFailure, "insufficient reserve/contiguous"):
                    observer._allocate_before()
                receipt = observer.result()["rejectedAllocationRequest"]
                self.assertEqual((receipt["kind"], receipt["bytes"], receipt["heapId"]), ("workspace", 43516, 4))
                self.assertEqual(receipt["callerReturn"], regs.lr)
                self.assertEqual(receipt["heapBeforeAllocation"]["boundary"], "native-Heap_Alloc-entry")
                self.assertEqual(receipt["heapBeforeAllocation"]["handle"], heap["handle"])
                self.assertEqual(receipt["heapBeforeAllocation"]["totalFreeBytes"], heap["totalFreeBytes"])
                self.assertEqual(receipt["heapBeforeAllocation"]["largestUserAllocationBytes"], heap["largestUserAllocationBytes"])
                self.assertEqual(receipt["insufficientReserve"], fault == "reserve")
                self.assertEqual(receipt["insufficientContiguousSpace"], fault == "contiguous")
                self.assertFalse(receipt["nativeReturnObserved"])
                self.assertEqual(receipt["ownerBefore"], owner)
                self.assertEqual([row["kind"] for row in observer.allocations], ["package", "workspace"])
                self.assertIsNone(acquired["allocation"])
                self.assertFalse(observer.result()["complete"])
                heap["totalFreeBytes"] = 0
                self.assertEqual(observer.result()["rejectedAllocationRequest"], receipt)
                observer.rejected_allocation_request["bytes"] = 1
                self.assertEqual(receipt["bytes"], 43516)

    def test_borrowed_world_runtime_and_callback_identity_reject(self):
        for fault in ("world", "field", "state", "swapped", "allocate", "free-size", "runtime"):
            with self.subTest(fault=fault):
                observer, regs, _heap, _owner, write = fixture = self.fixture()
                self.package(fixture)
                self.workspace(fixture)
                # Free no memory: this is a negative fresh Acquire input only.
                from tools.overworld.devtools_query_observer import RUNTIME_QUERY
                write(observer.current["runtime"] + RUNTIME_QUERY, bytes(4))
                if fault == "world": write(0x027E2200, struct.pack("<HH", 2, 84))
                if fault == "field": write(0x027E2204, struct.pack("<I", 0x02203000))
                if fault == "state": write(0x027E2208, struct.pack("<I", observer.session.rt.WILD_STATE + 4))
                if fault == "swapped": write(0x027E2204, struct.pack("<2I", observer.session.rt.WILD_STATE,
                                                                  observer.current["field"]))
                if fault == "allocate": write(0x027E210C, struct.pack("<I", observer.HEAP_ALLOC))
                if fault == "free-size": write(0x027E2110, struct.pack("<I", 0))
                if fault == "runtime": write(observer.session.rt.WILD_STATE + 0xE4, struct.pack("<I", 0x022E0000))
                regs.r0 = 0x027E2100
                with self.assertRaises(DevtoolsFailure): observer._acquire_before()

    def test_free_cannot_use_wrong_header_heap_caller_owner_or_repeat(self):
        for fault in ("header", "caller", "owner", "heap-owner", "repeat"):
            with self.subTest(fault=fault):
                observer, regs, heap, owner, write = fixture = self.fixture()
                self.package(fixture)
                workspace = self.workspace(fixture)
                owner["phase"] = 2
                regs.r0 = observer.current["runtime"]
                observer._drain_before()
                regs.r0, regs.lr = workspace["pointer"], observer.bodies["drain"][0] + 21
                if fault == "header": write(workspace["pointer"] - 16, bytes(12) + bytes([11, 0, 0, 0]))
                if fault == "caller": regs.lr = observer.bodies["unload"][0] + 21
                if fault == "owner": owner["phase"] = 1
                if fault == "heap-owner": heap["handle"] += 4
                if fault == "repeat": workspace["freeCount"] = 1
                with self.assertRaises(DevtoolsFailure): observer._free_before()

    def test_named_return_requires_actual_heap_free_and_workspace_clear(self):
        observer, regs, _heap, owner, _write = fixture = self.fixture()
        self.package(fixture)
        self.workspace(fixture)
        owner["phase"] = 2
        regs.r0 = observer.current["runtime"]
        drain = observer._drain_before()
        regs.r0 = 1
        with self.assertRaises(DevtoolsFailure): observer._drain_after(drain)
        self.assertFalse(observer.result()["complete"])

    def test_stale_dynamic_body_is_unknown_and_never_calls_guest(self):
        observer, _regs, _heap, _owner, write = fixture = self.fixture()
        self.package(fixture)
        token = observer.dynamic_token
        write(token[0], b"X")
        self.assertIsNone(token[1]())
        self.assertFalse(observer.result()["known"])
        self.assertIn("relocated owner", observer.result()["reason"])

    def test_other_overlay_at_static_address_is_skipped_before_package_or_owner_reads(self):
        observer, _regs, _heap, _owner, write = self.fixture()
        calls = []
        binding = observer.bodies["load"]
        observer.session.packaged_code = lambda *_args: calls.append("package")
        token = observer._watch(binding, lambda: calls.append("owner"), lambda _context: None)
        write(binding[0], b"X")
        self.assertIsNone(token[1]())
        self.assertEqual(calls, [])
        self.assertIsNone(observer.failure)
        self.assertEqual(observer.allocations, [])


if __name__ == "__main__":
    unittest.main()
