from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_condition_probe import (
    BUFFER_BYTES,
    CASE_NAMES,
    ConditionProbe,
    ConditionProbeError,
    WORLD_BYTES,
    buffer_layout,
    build_test_blob,
    fixture_patch_plan,
    world_bytes,
)


ROOT = Path(__file__).resolve().parents[2]


def source_blob():
    raw = bytearray(4096)
    struct.pack_into("<IHHI", raw, 0, 0x4F574244, 80, 84, len(raw))
    struct.pack_into("<IHH", raw, 36, 84, 4, 212)
    struct.pack_into("<IHH", raw, 44, 932, 1, 2)
    struct.pack_into("<IHH", raw, 52, 936, 4, 48)
    return bytes(raw)


class Session:
    def __init__(self):
        self.rt = SimpleNamespace(REPO=ROOT, EXECUTED_FRAME_COUNT=100)
        self.emu = object()
        self.native_heap_generation = 1
        self.completed_frames = 20
        self.field = 0x02010000
        self.native_allocations = {}
        self.memory = {}
        self.writes = []
        self.blob = source_blob()
        self.put(0x02020000, self.blob)

    def field_pointer(self):
        return self.field

    def put(self, address, data):
        self.memory.update({address + index: value
                            for index, value in enumerate(data)})

    def read(self, address, size):
        return bytes(self.memory.get(address + index, 0)
                     for index in range(size))

    def write(self, address, data):
        self.writes.append((address, len(data)))
        self.put(address, data)


class ConditionProbeTests(unittest.TestCase):
    def test_world_fixture_matches_current_vision_aware_layout(self):
        raw = world_bytes(100)
        self.assertEqual(len(raw), WORLD_BYTES)
        self.assertEqual(WORLD_BYTES, 240)
        self.assertEqual(raw[26:35], bytes((3, 8, 1, 2, 2, 3, 5, 3, 5)))
        self.assertEqual(raw[38:50], struct.pack("<6H", 1, 2, 3, 4, 12, 0))
        self.assertEqual(raw[54:58], bytes((1, 2, 3, 5)))
        self.assertEqual(raw[58:70], struct.pack("<6H", 2, 3, 3, 4, 13, 0))
        self.assertEqual(raw[74:78], bytes((1, 2, 3, 5)))

    def fixture(self):
        session = Session()
        probe = ConditionProbe(
            session,
            blob_address=0x02020000,
            blob_bytes=session.blob,
            service_identity={"version": 8},
        )
        return session, probe

    def run_recipe(self, session, probe, fault=None):
        generator = probe.recipe(None, lambda name, args: (name, args))
        self.assertEqual(next(generator),
                         ("allocate_work_memory", (11, BUFFER_BYTES)))
        pointer = 0x02040000
        pending = generator.send(pointer)
        layout = buffer_layout(len(session.blob))["regions"]
        calls = []
        evaluate_index = 0
        while True:
            name, args = pending
            calls.append(name)
            if name == "prepare_conditions":
                self.assertEqual(len(args), 5)
                self.assertEqual(args[0], 0x02020000)
                prepared = pointer + layout["prepared"]["offset"]
                session.put(prepared + 16, bytes((0, 1, 2, 3)))
                session.put(prepared + 48, bytes((4, 1, 4, 0)))
                status = 0
            elif name == "evaluate_conditions":
                self.assertEqual(len(args), 9)
                status = 3 if evaluate_index == 4 else 0
                evaluate_index += 1
            else:
                self.assertEqual(name, "free")
                self.assertEqual(args, (pointer,))
                try:
                    generator.send(0)
                except StopIteration as done:
                    return calls, done.value
                self.fail("condition recipe did not stop after free")
            if fault == "guard" and name == "evaluate_conditions":
                session.put(pointer, b"!")
                fault = None
            if fault == "source" and name == "evaluate_conditions":
                session.put(0x02020000, b"!")
                fault = None
            if fault == "owner" and name == "evaluate_conditions":
                session.native_heap_generation += 1
                fault = None
            session.rt.EXECUTED_FRAME_COUNT += 1
            pending = generator.send(status)

    def test_exact_bounded_calls_owned_writes_and_free(self):
        session, probe = self.fixture()
        calls, result = self.run_recipe(session, probe)
        self.assertEqual(calls, ["prepare_conditions"]
                         + ["evaluate_conditions"] * 6
                         + ["prepare_conditions", "evaluate_conditions", "free"])
        buffer_writes = [item for item in session.writes
                         if item[0] == 0x02040000]
        self.assertEqual(buffer_writes,
                         [(0x02040000, BUFFER_BYTES)] * 9)
        self.assertTrue(result["completed"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual([item["name"] for item in result["receipts"]],
                         list(CASE_NAMES))
        self.assertEqual(session.read(0x02020000, len(session.blob)),
                         session.blob)
        self.assertTrue(result["fixture"]["patched"])
        self.assertTrue(result["fixture"]["intactBeforeRestore"])
        self.assertTrue(result["fixture"]["restored"])
        self.assertEqual(session.native_allocations, {})
        with self.assertRaises(ConditionProbeError):
            next(probe.recipe(None, lambda *args: args))

    def test_bad_guard_and_source_free_before_failure(self):
        for fault in ("guard", "source"):
            with self.subTest(fault=fault):
                session, probe = self.fixture()
                with self.assertRaises(ConditionProbeError):
                    self.run_recipe(session, probe, fault)
                self.assertTrue(probe.released)
                self.assertTrue(probe.restored)
                self.assertEqual(session.read(0x02020000, len(session.blob)),
                                 session.blob)
                self.assertEqual(session.native_allocations, {})

    def test_owner_change_retains_old_heap_and_is_fatal(self):
        session, probe = self.fixture()
        with self.assertRaises(ConditionProbeError) as error:
            self.run_recipe(session, probe, "owner")
        self.assertTrue(error.exception.fatal)
        self.assertFalse(probe.released)
        self.assertTrue(probe.restored)
        self.assertEqual(session.read(0x02020000, len(session.blob)),
                         session.blob)
        self.assertIn(0x02040000, session.native_allocations)

    def test_allocation_failure_never_writes_or_frees(self):
        session, probe = self.fixture()
        recipe = probe.recipe(None, lambda name, args: (name, args))
        next(recipe)
        with self.assertRaises(ConditionProbeError):
            recipe.send(0)
        self.assertTrue(probe.restored)
        self.assertEqual(session.read(0x02020000, len(session.blob)),
                         session.blob)
        self.assertEqual(session.native_allocations, {})

    def test_temporary_blob_changes_only_declared_fixed_fixture_regions(self):
        source = source_blob()
        copied = build_test_blob(source)
        plan = fixture_patch_plan(source, copied)
        self.assertEqual(len(copied), len(source))
        self.assertEqual(struct.unpack_from("<H", copied, 56)[0], 4)
        self.assertEqual(copied[936 + 32:936 + 34], struct.pack("<H", 500))
        self.assertEqual(copied[936 + 48 + 32:936 + 48 + 34],
                         struct.pack("<H", 501))
        self.assertEqual(plan["rangeCount"], 3)
        self.assertEqual(plan["rangeBytes"], 2 + 4 * 212 + 4 * 48)
        self.assertEqual([item["name"] for item in plan["ranges"]],
                         ["condition-count", "profiles-0-3",
                          "conditions-0-3"])
        layout = buffer_layout(len(source))
        self.assertNotIn("blob", layout["regions"])
        self.assertLessEqual(layout["usedBytes"], BUFFER_BYTES)
        self.assertEqual(source, source_blob())


if __name__ == "__main__":
    unittest.main()
