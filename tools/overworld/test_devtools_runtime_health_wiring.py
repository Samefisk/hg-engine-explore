"""Exercise the real shared cycle path; fake CPU, no emulator or screenshots."""
from types import SimpleNamespace
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure, FieldReturnBridge
from tools.overworld.devtools_runtime_health import RuntimeHealthMonitor


class RuntimeHealthWiringTests(unittest.TestCase):
    def test_boot_stall_keeps_cpu_before_core_close(self):
        with tempfile.TemporaryDirectory(prefix="boot-stall-") as directory:
            root = Path(directory)
            rom, save = root / "test.nds", root / "test.sav"
            rom.write_bytes(b"rom")
            save.write_bytes(b"save")
            core = object()
            calls = []
            rt = SimpleNamespace(REPO=root, ACTOR_DESCRIPTOR={"state": {
                "offsets": {"actors": 68, "fieldEpoch": 12}}},
                _zero_hp_save_record=lambda data: None,
                h=SimpleNamespace(create_emulator=lambda: core))
            rt.boot = lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("save reached field but actor clock stalled"))
            def diagnose(session):
                self.assertIs(session.emu, core)
                calls.append("read")
                return {"cpu": {"registers": {"pc": 0x023C1234}}}
            def close(session):
                calls.append("close")
                session.emu = None
            with patch.object(DevtoolsSession, "_load_package"), \
                    patch.object(DevtoolsSession, "diagnostics", diagnose), \
                    patch.object(DevtoolsSession, "close", close):
                with self.assertRaises(DevtoolsFailure) as caught:
                    DevtoolsSession(rt, str(rom), str(save), root)
            self.assertEqual(calls, ["read", "close"])
            self.assertEqual(caught.exception.code, "boot-actor-clock-stalled")
            self.assertTrue(caught.exception.fatal)
            self.assertEqual(caught.exception.details["diagnostics"]["cpu"]["registers"]["pc"],
                             0x023C1234)
            self.assertEqual(save.read_bytes(), b"save")

    def fixture(self, *, mode=0x1F, advancing=False):
        session = DevtoolsSession.__new__(DevtoolsSession)
        registers = SimpleNamespace(cpsr=mode, pc=0xFFFF010C, lr=0x023BF59A, sp=0)
        session.emu = SimpleNamespace(memory=SimpleNamespace(register_arm9=registers))
        session.completed_frames = 381
        session.native_bridge_active = False
        session.runtime_health = RuntimeHealthMonitor(381, 0)
        session.runtime_health_failure = None
        session._stock_save_write_active = lambda: False
        session.rt = SimpleNamespace(EXECUTED_FRAME_COUNT=0)
        def cycle(emu, frames, mask):
            self.assertIs(emu, session.emu)
            session.rt.EXECUTED_FRAME_COUNT += frames
            if advancing:
                session.completed_frames += frames
        session.rt.h = SimpleNamespace(cycle=cycle)
        session.diagnostics = lambda: {"cpu": {"registers": vars(registers).copy()},
                                       "lastCompletedGameFrame": session.completed_frames}
        return session

    def test_abort_stops_first_native_cycle_and_keeps_first_cpu_state(self):
        session = self.fixture(mode=0x97)
        with self.assertRaises(DevtoolsFailure) as caught:
            session.cycle(600)
        self.assertEqual(caught.exception.code, "arm9-abort")
        self.assertEqual(session.rt.EXECUTED_FRAME_COUNT, 1)
        self.assertEqual(caught.exception.details["diagnostics"]["cpu"]["registers"]["lr"], 0x023BF59A)
        session.emu.memory.register_arm9.cpsr = 0x1F
        with self.assertRaises(DevtoolsFailure):
            session.cycle(1)
        self.assertEqual(session.rt.EXECUTED_FRAME_COUNT, 1)

    def test_small_calls_cannot_reset_stall_deadline(self):
        session = self.fixture()
        for _ in range(119):
            session.cycle(1)
        with self.assertRaises(DevtoolsFailure) as caught:
            session.cycle(1)
        self.assertEqual(caught.exception.code, "main-queue-stalled")
        self.assertEqual(session.rt.EXECUTED_FRAME_COUNT, 120)

    def test_stock_save_write_gets_only_bounded_extra_time(self):
        session = self.fixture()
        session._stock_save_write_active = lambda: True
        for _ in range(2399):
            session.cycle(1)
        with self.assertRaises(DevtoolsFailure) as caught:
            session.cycle(1)
        self.assertEqual(caught.exception.code, "main-queue-stalled")
        self.assertEqual(caught.exception.details["stallLimit"], 2400)

    def test_normal_progress_and_irq_are_not_a_freeze(self):
        session = self.fixture(mode=0x92, advancing=True)
        session.cycle(600)
        self.assertEqual(session.completed_frames, 981)
        self.assertIsNone(session.runtime_health_failure)

    def bridge_fixture(self, **kwargs):
        session = self.fixture(**kwargs)
        class Hooks:
            error = None
            def __init__(self):
                self.callbacks = {}
            def add(self, address, callback):
                key = address & ~1
                self.callbacks.setdefault(key, []).append(callback)
                return key, callback
            def remove(self, token):
                self.callbacks[token[0]].remove(token[1])
        session.party_getter_hooks = Hooks()
        session.require_quiescent = lambda: None
        session._native_checkpoint_points = lambda: []
        session.target = lambda name: 0x02000001
        session.rt.h.set_key_mask = lambda emu, mask: None
        session.close = lambda: setattr(session, "emu", None)
        return session

    def test_real_bridge_waiting_for_missing_poll_cannot_exclude_stall(self):
        session = self.bridge_fixture()
        with patch("tools.overworld.devtools_runtime.native_cpu_diagnostics", return_value={}):
            with self.assertRaises(DevtoolsFailure) as caught:
                FieldReturnBridge(session).run(lambda scratch: iter(()))
        self.assertEqual(caught.exception.code, "main-queue-stalled")
        self.assertEqual(session.rt.EXECUTED_FRAME_COUNT, 120)
        self.assertIs(caught.exception, session.runtime_health_failure)
        self.assertEqual(caught.exception.details["nativeCyclesWithoutProgress"], 120)
        self.assertIsNone(session.emu)

    def test_real_bridge_retains_first_cpu_fault_through_close_and_later_call(self):
        session = self.bridge_fixture(mode=0x97)
        with patch("tools.overworld.devtools_runtime.native_cpu_diagnostics", return_value={}):
            with self.assertRaises(DevtoolsFailure) as caught:
                FieldReturnBridge(session).run(lambda scratch: iter(()))
        self.assertEqual(caught.exception.code, "arm9-abort")
        self.assertEqual(session.rt.EXECUTED_FRAME_COUNT, 1)
        self.assertIs(caught.exception, session.runtime_health_failure)
        self.assertEqual(caught.exception.details["diagnostics"]["cpu"]["registers"]["lr"], 0x023BF59A)
        self.assertIn("bridge", caught.exception.details)
        with self.assertRaises(DevtoolsFailure) as repeated:
            session.cycle(1)
        self.assertIs(repeated.exception, caught.exception)


class HeapDiagnosticsTests(unittest.TestCase):
    def fixture(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.completed_frames = 381
        session.rt = SimpleNamespace(EXECUTED_FRAME_COUNT=921)
        data = bytearray(0x400000)
        reads = []

        def write(address, value):
            data[address - 0x02000000:address - 0x02000000 + len(value)] = value

        def read(address, size):
            reads.append((address, size))
            return bytes(data[address - 0x02000000:address - 0x02000000 + size])

        session.read = read
        stock = (Path(__file__).resolve().parents[2] / "base/arm9.bin").read_bytes()
        session.code_regions = []
        for address, size in ((0x0201AB0C, 0x74), (0x020B556C, 0x28)):
            code = stock[address - 0x02000000:address - 0x02000000 + size]
            self.assertEqual(len(code), size)
            write(address, code)
            session.code_regions.append((address, code))
        handles, maximum, total = 0x021F0000, 27, 64
        parents = handles + (maximum + 1) * 4
        raw = parents + maximum * 4
        counts = raw + maximum * 4
        indexes = counts + total * 2
        write(0x021D1584, struct.pack("<5I4H", handles, parents, raw,
                                    counts, indexes, total, 3, maximum, maximum))
        write(indexes, bytes([maximum]) * total)
        native = {3: (4, 0x02200000), 4: (6, 0x02204000), 11: (5, 0x02208000)}
        for heap_id, (index, handle) in native.items():
            write(indexes + heap_id, bytes([index]))
            write(handles + index * 4, struct.pack("<I", handle))
            if heap_id != 3:
                write(parents + index * 4, struct.pack("<I", native[3][1]))
                write(raw + index * 4, struct.pack("<I", handle))
            write(counts + heap_id * 2, struct.pack("<H", 17 + heap_id))
            header = bytearray(0x38)
            struct.pack_into("<I", header, 0, 0x45585048)
            start, tail = handle + 0x38, handle + 0x138
            struct.pack_into("<2I", header, 0x18, start, handle + 0x3000)
            struct.pack_into("<2I", header, 0x24, start, tail)
            write(handle, header)
            write(start, struct.pack("<HH3I", 0x4652, 0, 64, 0, tail))
            write(tail, struct.pack("<HH3I", 0x4652, 0, 128, start, 0))
        return session, write, reads, native, indexes

    def test_reads_real_heap_mapping_and_free_sizes_without_native_work(self):
        session, _write, reads, native, _indexes = self.fixture()
        session._control_diagnostics = lambda: {}
        session._mount_toggle_diagnostics = lambda: {}
        session.latest_frame = {}
        with patch("tools.overworld.devtools_runtime.native_cpu_diagnostics", return_value={}):
            result = session.diagnostics()["heaps"]
        self.assertTrue(result["known"])
        self.assertTrue(result["diagnosticOnly"])
        self.assertFalse(result["acceptedProof"])
        for row in result["heaps"]:
            self.assertEqual((row["heapIndex"], row["handle"]), native[row["heapId"]])
            self.assertEqual((row["freeBlockCount"], row["totalFreeBytes"],
                              row["largestFreeBytes"], row["largestUserAllocationBytes"]),
                             (2, 192, 128, 112))
            self.assertEqual(row["heapStart"], row["handle"] + 0x38)
            self.assertEqual(row["heapEnd"], row["handle"] + 0x3000)
            self.assertEqual(row["parentHeapIds"], [] if row["heapId"] == 3 else [3])
        self.assertEqual(result["bytesRead"], sum(size for _, size in reads))
        self.assertLessEqual(result["bytesRead"], 8192)
        self.assertEqual((session.completed_frames, session.rt.EXECUTED_FRAME_COUNT), (381, 921))

    def test_heap_code_mismatch_or_missing_code_stops_before_table_reads(self):
        for mutation in ("live", "package-and-live", "missing"):
            with self.subTest(mutation=mutation):
                session, write, reads, _native, _indexes = self.fixture()
                if mutation == "missing":
                    session.code_regions.pop()
                else:
                    address, code = session.code_regions[-1]
                    changed = bytes([code[0] ^ 1]) + code[1:]
                    write(address, changed)
                    if mutation == "package-and-live":
                        session.code_regions[-1] = (address, changed)
                result = session._heap_diagnostics()
                self.assertFalse(result["known"])
                self.assertEqual(result["heaps"], [])
                self.assertNotIn((0x021D1584, 28), reads)
                self.assertIn("reason", result)

    def test_invalid_free_block_links_and_extents_fail_closed(self):
        for mutation in ("signature", "previous", "tail", "cycle", "outside", "extent"):
            with self.subTest(mutation=mutation):
                session, write, reads, native, _indexes = self.fixture()
                handle = native[11][1]
                head, tail = handle + 0x38, handle + 0x138
                if mutation == "signature":
                    write(head, struct.pack("<H", 0x5544))
                elif mutation == "previous":
                    write(tail + 8, struct.pack("<I", 0))
                elif mutation == "tail":
                    write(handle + 0x28, struct.pack("<I", head))
                elif mutation == "cycle":
                    write(tail + 12, struct.pack("<I", head))
                elif mutation == "outside":
                    write(tail + 12, struct.pack("<I", 0x022F0000))
                else:
                    write(tail + 4, struct.pack("<I", 0x3000))
                result = session._heap_diagnostics()
                self.assertFalse(result["known"])
                row = result["heaps"][-1]
                self.assertFalse(row["known"])
                self.assertNotIn("totalFreeBytes", row)
                self.assertTrue(result["heaps"][0]["known"])
                self.assertNotIn((0x022F0000, 16), reads)

    def test_exact_node_limit_and_unallocated_heap(self):
        for count in (128, 129):
            with self.subTest(count=count):
                session, write, reads, native, indexes = self.fixture()
                write(indexes + 4, bytes([27]))
                handle = native[11][1]
                head = handle + 0x38
                write(handle + 0x28, struct.pack("<I", head + (count - 1) * 32))
                for n in range(count):
                    address = head + n * 32
                    write(address, struct.pack("<HH3I", 0x4652, 0, 16,
                        0 if n == 0 else address - 32, 0 if n == count - 1 else address + 32))
                result = session._heap_diagnostics()
                self.assertEqual(result["known"], count == 128)
                self.assertFalse(result["heaps"][1]["allocated"])
                self.assertIsNone(result["heaps"][1]["totalFreeBytes"])
                if count == 128:
                    self.assertEqual(result["heaps"][2]["totalFreeBytes"], 2048)
                else:
                    self.assertIn("node limit", result["heaps"][2]["reason"])
                    self.assertNotIn((head + 128 * 32, 16), reads)
                self.assertLessEqual(result["bytesRead"], 8192)


class QueryOwnerDiagnosticsTests(unittest.TestCase):
    TABLE = 0x023C22F0
    STATE = 0x023C2308
    FLAG = 0x023C8148
    WORDS = (0x02200000, 0x10860, 0x02200040, 0x022B16DC, 2, 2, 21, 1, bytes(3))

    @staticmethod
    def elf(base, data, values):
        """Small typed ELF fixture for the existing production symbol reader."""
        names = b"\0.text\0.symtab\0.strtab\0.shstrtab\0"
        strings, symbols = bytearray(b"\0"), bytearray(16)
        for name, address, size in values:
            label = len(strings)
            strings.extend(name.encode() + b"\0")
            symbols.extend(struct.pack("<IIIBBH", label, address, size, 1, 0, 1))
        image = bytearray(52)
        rows = [(0,) * 10]
        for name, kind, flags, address, content, link, stride in (
            (".text", 1, 7, base, data, 0, 0),
            (".symtab", 2, 0, 0, symbols, 3, 16),
            (".strtab", 3, 0, 0, strings, 0, 0),
            (".shstrtab", 3, 0, 0, names, 0, 0),
        ):
            rows.append((names.index(name.encode()), kind, flags, address, len(image),
                         len(content), link, 0, 4, stride))
            image.extend(content)
        offset = len(image)
        for row in rows:
            image.extend(struct.pack("<10I", *row))
        image[:7] = b"\x7fELF\x01\x01\x01"
        struct.pack_into("<I", image, 32, offset)
        struct.pack_into("<3H", image, 46, 40, len(rows), 4)
        return image

    def fixture(self, directory, *, words=None, state_size=28, state_home=None, table=None):
        build = Path(directory) / "build"
        build.mkdir()
        table = table or struct.pack("<IHH4I", 0x53444F57, 2, 24, self.STATE,
                                     0x023C2A4D, 0x023C2A3D, 0x023C2A29)
        linked = self.elf(self.TABLE, table + bytes(64), (
            ("gOverworldQueryCodeAddonServiceEntry", self.TABLE, 24),
            ("gOverworldQueryCodeAddonState", self.STATE if state_home is None else state_home,
             state_size)))
        (build / "overworld_follower_selector_overlay_linked.o").write_bytes(linked)
        (build / "field_linked.o").write_bytes(self.elf(self.FLAG, bytes(4), (
            ("gOverworldFollowerSelectorStateStorage", self.FLAG, 1),)))
        memory = {self.FLAG: b"\x40", self.TABLE: table,
                  self.STATE: struct.pack("<4I2HIB3s", *(self.WORDS if words is None else words))}
        reads = []
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.rt = SimpleNamespace(REPO=Path(directory), EXECUTED_FRAME_COUNT=921)
        session.completed_frames = 381
        session.code_regions = [(self.TABLE, table)]
        def read(address, size):
            reads.append((address, size))
            return memory[address][:size]
        session.read = read
        return session, memory, reads

    def test_existing_diagnostics_reads_only_typed_state_and_preserves_old_owner(self):
        with tempfile.TemporaryDirectory(prefix="query-owner-") as directory:
            session, memory, reads = self.fixture(directory)
            session._control_diagnostics = lambda: {}
            session._mount_toggle_diagnostics = lambda: {}
            session._heap_diagnostics = lambda: {}
            session.latest_frame = {}
            with patch("tools.overworld.devtools_runtime.native_cpu_diagnostics", return_value={}):
                result = session.diagnostics()["queryOwner"]
            self.assertTrue(result["known"], result)
            self.assertEqual({key: result[key] for key in (
                "blob", "blobSize", "entry", "fieldIdentity", "fieldEpoch", "mapGeneration",
                "memberId", "phase")}, dict(zip((
                "blob", "blobSize", "entry", "fieldIdentity", "fieldEpoch", "mapGeneration",
                "memberId", "phase"), self.WORDS[:-1])))
            self.assertEqual(result["rawHex"], memory[self.STATE].hex())
            self.assertEqual(reads, [(self.FLAG, 1), (self.TABLE, 24), (self.STATE, 28)])
            self.assertEqual(result["bytesRead"], 53)
            self.assertTrue(result["diagnosticOnly"])
            self.assertFalse(result["acceptedProof"])
            self.assertEqual((session.completed_frames, session.rt.EXECUTED_FRAME_COUNT), (381, 921))
            memory[self.STATE] = bytes(28)
            empty = session._query_owner_diagnostics()
            self.assertTrue(empty["known"], empty)
            self.assertEqual((empty["phase"], empty["blob"], empty["rawHex"]),
                             (0, 0, bytes(28).hex()))

    def test_final_package_extent_is_exact_without_data_pointer_follow(self):
        with tempfile.TemporaryDirectory(prefix="query-owner-") as directory:
            words = list(self.WORDS)
            words[1] = 69072
            session, _memory, reads = self.fixture(directory, words=words)
            result = session._query_owner_diagnostics()
            self.assertTrue(result["known"], result)
            self.assertEqual(result["blobSize"], 69072)
            self.assertEqual(reads, [(self.FLAG, 1), (self.TABLE, 24), (self.STATE, 28)])

    def test_boot_allocation_install_keeps_unknown_and_closes_partial_hooks(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.query_allocation_lifecycle = None
        calls = []
        class Observer:
            def __init__(self, subject):
                calls.append(subject)
            def install(self):
                calls.append("install")
                raise ValueError("exact final Query package is unavailable")
            def close(self):
                calls.append("close")
        with patch("tools.overworld.devtools_heap_free_observer.QueryAllocationLifecycleObserver", Observer):
            session._install_query_allocation_observer()
        self.assertEqual(calls, [session, "install", "close"])
        result = session._query_allocation_diagnostics()
        self.assertFalse(result["known"])
        self.assertFalse(result["acceptedProof"])
        self.assertIn("exact final Query package", result["reason"])

    def test_cold_selector_and_table_or_symbol_mismatch_stop_before_state(self):
        for fault in ("cold", "live", "package-and-live", "missing", "magic", "version",
                      "size", "pointer", "arm-callback", "callback-bounds", "state-size", "state-home"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(prefix="query-owner-") as directory:
                table = bytearray(struct.pack("<IHH4I", 0x53444F57, 2, 24, self.STATE,
                                              0x023C2A4D, 0x023C2A3D, 0x023C2A29))
                if fault in ("magic", "version", "size", "pointer", "arm-callback", "callback-bounds"):
                    offset, fmt, value = {"magic": (0, "I", 0), "version": (4, "H", 1),
                        "size": (6, "H", 28), "pointer": (8, "I", self.STATE + 4),
                        "arm-callback": (12, "I", 0x023C2A4C),
                        "callback-bounds": (12, "I", 0x023C3001)}[fault]
                    struct.pack_into("<" + fmt, table, offset, value)
                session, memory, reads = self.fixture(directory, table=bytes(table),
                    state_size=27 if fault == "state-size" else 28,
                    state_home=self.STATE + 4 if fault == "state-home" else None)
                if fault == "cold":
                    memory[self.FLAG] = bytes(1)
                elif fault == "missing":
                    session.code_regions = []
                elif fault in ("live", "package-and-live"):
                    memory[self.TABLE] = bytes([table[0] ^ 1]) + bytes(table[1:])
                    if fault == "package-and-live":
                        session.code_regions = [(self.TABLE, memory[self.TABLE])]
                result = session._query_owner_diagnostics()
                self.assertFalse(result["known"], result)
                self.assertNotIn((self.STATE, 28), reads)
                if fault == "cold":
                    self.assertEqual(reads, [(self.FLAG, 1)])
                self.assertIn("reason", result)

    def test_active_owner_bounds_and_partial_state_fail_closed_without_pointer_follow(self):
        faults = ((0, 0), (0, 0x01FFFFFC), (0, 0x02200001), (0, 0x023FFFC0),
                  (1, 259), (1, 69073), (2, 0x02200044), (3, 0), (3, 0x02400000),
                  (4, 0), (5, 0), (6, 20), (7, 4), (7, 0), (8, b"\x01\0\0"))
        for index, value in faults:
            with self.subTest(index=index, value=value), tempfile.TemporaryDirectory(prefix="query-owner-") as directory:
                words = list(self.WORDS)
                words[index] = value
                session, _memory, reads = self.fixture(directory, words=words)
                result = session._query_owner_diagnostics()
                self.assertFalse(result["known"], result)
                self.assertEqual(reads, [(self.FLAG, 1), (self.TABLE, 24), (self.STATE, 28)])
                self.assertLessEqual(result["bytesRead"], result["readBudgetBytes"])
                self.assertNotIn("blob", result)
        with tempfile.TemporaryDirectory(prefix="query-owner-") as directory:
            session, memory, reads = self.fixture(directory)
            memory[self.STATE] = memory[self.STATE][:-1]
            self.assertFalse(session._query_owner_diagnostics()["known"])
            self.assertEqual(reads[-1], (self.STATE, 28))
