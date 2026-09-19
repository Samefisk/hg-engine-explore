"""Generator/native-memory fixtures, not emulator execution or parity proof."""
from pathlib import Path
from types import SimpleNamespace
import struct
import unittest

from tools.overworld.devtools_resolver_parity import CASE_NAMES
from tools.overworld.devtools_resolver_probe import (
    REQUEST,
    RESULT,
    STEPS,
    TRACE,
    ResolverProbe,
    ResolverProbeError,
)


class Session:
    def __init__(self):
        self.rt = SimpleNamespace(REPO=Path(__file__).resolve().parents[2], EXECUTED_FRAME_COUNT=100)
        self.emu = object(); self.native_heap_generation = 1; self.completed_frames = 20
        self.field = 0x02010000; self.native_allocations = {}; self.memory = {}; self.writes = []
        self.blob = b"native-blob" * 20; self.put(0x02020000, self.blob)

    def field_pointer(self): return self.field
    def put(self, address, data): self.memory.update({address + i: value for i, value in enumerate(data)})
    def read(self, address, size): return bytes(self.memory.get(address + i, 0) for i in range(size))
    def write(self, address, data): self.writes.append((address, len(data))); self.put(address, data)


class ResolverProbeTests(unittest.TestCase):
    def fixture(self):
        session = Session()
        probe = ResolverProbe(session, blob_address=0x02020000, blob_bytes=session.blob,
                              service_identity={"callerAuthenticated": True})
        return session, probe

    def run_recipe(self, session, probe, fault=None):
        call = lambda name, args: (name, args)
        generator = probe.recipe(None, call)
        self.assertEqual(next(generator), ("allocate_work_memory", (11, 8000)))
        pointer = 0x02040000
        pending = generator.send(pointer); calls = []
        while True:
            name, args = pending; calls.append(name)
            if name == "free":
                self.assertEqual(args, (pointer,))
                if fault == "free":
                    generator.throw(RuntimeError("native free did not return"))
                try: generator.send(0)
                except StopIteration as done: return calls, done.value
            self.assertEqual(name, "resolve_behavior")
            self.assertEqual(args, (0x02020000, len(session.blob),
                                    pointer + REQUEST, pointer + RESULT, pointer + TRACE))
            session.put(pointer + TRACE + 6, struct.pack("<H", 1))
            session.put(pointer + STEPS, struct.pack("<HBBB3x", 1, 0, 2, 3) + bytes(72))
            if fault == "guard": session.put(pointer, b"!")
            if fault == "end-guard": session.put(pointer + 7999, b"!")
            if fault == "request": session.put(pointer + REQUEST, b"!")
            if fault == "count": session.put(pointer + TRACE + 6, struct.pack("<H", 97))
            if fault == "drop": session.put(pointer + TRACE + 8, struct.pack("<H", 1))
            if fault == "trace-pointer": session.put(pointer + TRACE, bytes(4))
            if fault == "reserved": session.put(pointer + STEPS + 5, b"!")
            if fault == "blob": session.put(0x02020000, b"!")
            if fault == "owner": session.native_heap_generation += 1
            session.rt.EXECUTED_FRAME_COUNT += 1
            pending = generator.send(0)

    def test_exact_calls_owned_writes_and_free(self):
        session, probe = self.fixture()
        calls, result = self.run_recipe(session, probe)
        self.assertEqual(calls, ["resolve_behavior"] * len(CASE_NAMES) + ["free"])
        self.assertEqual(session.writes, [(0x02040000, 8000)] * len(CASE_NAMES))
        self.assertTrue(result["completed"]); self.assertFalse(result["acceptedProof"])
        self.assertEqual(len(result["receipts"]), len(CASE_NAMES))
        self.assertEqual(session.native_allocations, {})
        self.assertEqual(result["receipts"][0]["returnClock"]["nativeCycle"], 101)
        result["receipts"].clear(); self.assertEqual(len(probe.receipts), len(CASE_NAMES))
        with self.assertRaises(ResolverProbeError): next(probe.recipe(None, lambda *a: a))

    def test_bad_data_frees_before_propagating(self):
        for fault in ("guard", "end-guard", "request", "count", "drop", "trace-pointer", "reserved", "blob"):
            with self.subTest(fault=fault):
                session, probe = self.fixture()
                with self.assertRaises(ResolverProbeError): self.run_recipe(session, probe, fault)
                self.assertTrue(probe.released)
                self.assertEqual(session.native_allocations, {})
                self.assertFalse(probe.result()["completed"])

    def test_owner_change_never_frees_old_heap_and_free_failure_retains_ownership(self):
        session, probe = self.fixture()
        with self.assertRaises(ResolverProbeError) as error: self.run_recipe(session, probe, "owner")
        self.assertTrue(error.exception.fatal)
        self.assertFalse(probe.released); self.assertIn(0x02040000, session.native_allocations)
        session, probe = self.fixture()
        with self.assertRaises(RuntimeError): self.run_recipe(session, probe, "free")
        self.assertFalse(probe.result()["completed"])
        self.assertIn(0x02040000, session.native_allocations)

    def test_allocation_failure_never_writes_or_frees(self):
        session, probe = self.fixture()
        recipe = probe.recipe(None, lambda name, args: (name, args))
        next(recipe)
        with self.assertRaises(ResolverProbeError): recipe.send(0)
        self.assertEqual(session.writes, [])
        self.assertEqual(session.native_allocations, {})

    def test_trace_layout_is_anchored_to_public_header(self):
        session, _ = self.fixture()
        header = (session.rt.REPO / "include/overworld_behavior_resolver.h").read_text()
        trace = header.split("typedef struct BehaviorResolutionTrace {", 1)[1].split("} BehaviorResolutionTrace;", 1)[0]
        fields = ("BehaviorResolutionStep *steps;", "u16 capacity;", "u16 count;", "u16 dropped;", "u16 reserved;")
        self.assertEqual([trace.index(field) for field in fields], sorted(trace.index(field) for field in fields))
        step = header.split("typedef struct BehaviorResolutionStep {", 1)[1].split("} BehaviorResolutionStep;", 1)[0]
        fields = ("u16 sourceIndex;", "u8 lane;", "u8 kind;", "u8 flags;", "u8 reserved[3];", "OverworldWildBehaviorProfileData profile;")
        self.assertEqual([step.index(field) for field in fields], sorted(step.index(field) for field in fields))
