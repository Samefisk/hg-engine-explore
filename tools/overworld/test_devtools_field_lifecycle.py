import struct
import unittest
from types import SimpleNamespace

from tools.overworld import devtools_field_lifecycle as d


class FieldLifecycleTests(unittest.TestCase):
    def fixture(self, execution=2, phase=0, ready=1):
        field, control, manager, terrain = 0x02210000, 0x02211000, 0x02212000, 0x02213000
        memory, reads = {}, []
        def put(address, value, size=4):
            for i, byte in enumerate(value.to_bytes(size, "little")):
                memory[address + i] = byte
        put(field, control)
        put(field + 0x6C, ready)
        put(field + 0x2C, terrain)
        put(control, manager)
        for i, value in enumerate((*d.FIELD_TEMPLATE, execution, phase, field, 0, 0, 0)):
            put(manager + i * 4, value)
        put(terrain + 0xB0, 1)
        def read(address, size):
            reads.append((address, size))
            return bytes(memory.get(address + i, 0) for i in range(size))
        return field, control, manager, terrain, put, read, reads

    def observe(self, fixture, authenticate=lambda *_: True):
        value = d.observe_field_lifecycle(fixture[5], authenticate, fixture[0], 10, 20)
        self.assertLessEqual(value["readBytes"], 512)
        self.assertFalse(value["acceptedProof"])
        return value

    def test_ready_retained_and_exit_pending_are_distinct(self):
        for ready, state in ((1, "field-ready-retained"), (0, "field-exit-pending")):
            f = self.fixture(ready=ready)
            self.assertEqual(self.observe(f)["state"], state)
            self.assertEqual(f[6][0], (f[0] + 0x6C, 4))

    def test_terrain_predicate_exact_cases(self):
        for ready, busy in ((0, 0), (1, 1), (2, 0), (1, 0)):
            f = self.fixture(3, 1, 0)
            f[4](f[3] + 0xB0, ready)
            f[4](f[3] + 0xA0, busy, 1)
            value = self.observe(f)
            self.assertTrue(value["known"])
            self.assertEqual(value["terrain"]["exitPredicate"], ready == 1 and busy == 0)

    def test_finalizer_never_reads_freed_terrain(self):
        f = self.fixture(3, 2, 0)
        f[4](f[0] + 0x2C, 3)
        self.assertEqual(self.observe(f)["state"], "field-exit-finalizing")
        self.assertNotIn((f[0] + 0x2C, 4), f[6])

    def test_unknown_controls_keep_first_ready_diagnostic(self):
        for target, offset, value in ((0, 0, 3), (1, 8, 2), (2, 0, 0),
                                      (2, 0x18, 0), (2, 0x10, 4), (2, 0x14, 9)):
            f = self.fixture()
            f[4](f[target] + offset, value)
            observed = self.observe(f)
            self.assertFalse(observed["known"])
            self.assertEqual(observed["fieldReady"], 1)

    def test_authentication_failure_does_not_read_terrain(self):
        f = self.fixture(3, 1, 0)
        value = self.observe(f, lambda *_: False)
        self.assertFalse(value["known"])
        self.assertIsNone(value["terrain"])

    def test_absent_and_initializing_managers(self):
        f = self.fixture()
        f[4](f[1], 0)
        self.assertEqual(self.observe(f)["state"], "field-manager-absent")
        self.assertEqual(self.observe(self.fixture(1, 3))["state"], "field-initializing")

    def test_short_reads_and_invalid_field_fail_closed(self):
        for field, read in ((3, lambda *_: bytes(4)), (0x02210000, lambda *_: b"")):
            self.assertFalse(d.observe_field_lifecycle(read, lambda *_: True, field, 1, 2)["known"])

    def test_shared_control_diagnostic_uses_current_field_and_clocks(self):
        from tools.overworld.devtools_runtime import DevtoolsSession
        f = self.fixture()
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.emu = object()
        session.read = f[5]
        session.field_pointer = lambda: f[0]
        session.completed_frames = 10
        session._authenticate_field_reader_code = lambda *_: True
        session.rt = SimpleNamespace(
            EXECUTED_FRAME_COUNT=20,
            unsigned=lambda emu, address, size=4: int.from_bytes(f[5](address, size), "little"),
            field_map_id=lambda emu: 69, player_ptr=lambda emu: 0x02214000,
            object_state=lambda emu, address: {"x": 8, "y": 19},
            ACTOR_DESCRIPTOR={"state": {"address": 0x02215000}})
        result = session._control_diagnostics()
        self.assertNotIn("diagnosticError", result)
        value = result["fieldLifecycle"]
        self.assertEqual((value["fieldPointer"], value["frame"], value["nativeCycle"]),
                         (f[0], 10, 20))
        self.assertEqual(value["state"], "field-ready-retained")
        self.assertEqual(value["boundary"], "paused-native-cycle-end")
        self.assertEqual(result["tasks"], [])


if __name__ == "__main__":
    unittest.main()
