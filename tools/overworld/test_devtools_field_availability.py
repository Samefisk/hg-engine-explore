"""The real queue sampler must not read freed field actors during teardown."""
import struct
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools.overworld.devtools_runtime import DevtoolsSession
from tools.overworld.devtools_field_lifecycle import FIELD_TEMPLATE
from tools.overworld.test_devtools_runtime import CompletedFieldAvailabilityTests


class FieldAvailabilityTests(unittest.TestCase):
    def fixture(self):
        session, _, boundary, actor_reads, _, _ = CompletedFieldAvailabilityTests.fixture(self)
        field, control, manager = 0x02003000, 0x02004000, 0x02005000
        memory = {field: struct.pack("<I", control), field + 0x6C: struct.pack("<I", 1),
                  control: struct.pack("<I", manager),
                  manager: struct.pack("<10I", *FIELD_TEMPLATE, 2, 0, field, 0, 0, 0)}
        code = bytes.fromhex("01680968002904d0c06e002801d001207047002070470000")
        session.arm9_code_region = (0x0203DF8C, code)
        session.dialogue_overlay_regions = {}
        memory[0x0203DF8C] = code
        accesses = []
        def read(address, size):
            accesses.append((address, size))
            return memory[address][:size]
        session.read = read
        session._field_actor_availability = DevtoolsSession._field_actor_availability.__get__(session)
        return session, boundary, memory, actor_reads, accesses

    def test_live_sampler_retains_unload_queue_without_actor_dereferences(self):
        session, boundary, memory, actor_reads, accesses = self.fixture()
        boundary()
        self.assertTrue(session.pending_samples[-1]["fieldAvailable"])
        actor_reads.clear()
        memory[0x0200306C] = bytes(4)
        # A real completed queue with a live global pointer but no manager.
        memory[0x02004000] = bytes(4)
        boundary()
        self.assertIsNone(session.sample_error)
        row = session.pending_samples[-1]
        self.assertFalse(row["fieldAvailable"])
        self.assertEqual(row["frame"], 5)
        self.assertEqual(row["nativeObservation"]["playerStepFrame"], 5)
        self.assertEqual(row["fieldAvailability"]["reasons"], ["field-manager-absent"])
        self.assertEqual(actor_reads, [])
        self.assertNotIn("player", row)
        self.assertNotIn("actors", row)
        self.assertIn((0x0203DF8C, 24), accesses)

    def test_initialization_and_all_exit_phases_are_absent(self):
        for execute, process, reason in ((0, 0, "field-initializing"),
                (1, 3, "field-initializing"), (2, 0, "field-exiting"),
                (3, 0, "field-exiting"), (3, 1, "field-exiting"), (3, 2, "field-exiting")):
            with self.subTest(execute=execute, process=process):
                session, boundary, memory, actor_reads, _ = self.fixture()
                memory[0x0200306C] = bytes(4)
                memory[0x02005000] = struct.pack("<10I", *FIELD_TEMPLATE, execute, process,
                                               0x02003000, 0, 0, 0)
                boundary()
                self.assertIsNone(session.sample_error)
                self.assertEqual(actor_reads, [])
                self.assertEqual(session.pending_samples[-1]["fieldAvailability"]["reasons"], [reason])

    def test_uninitialized_control_is_absent_without_dereferencing_it(self):
        session, boundary, memory, actor_reads, _ = self.fixture()
        memory[0x02003000] = memory[0x0200306C] = bytes(4)
        boundary()
        self.assertIsNone(session.sample_error)
        self.assertEqual(actor_reads, [])
        self.assertEqual(session.latest_frame["fieldAvailability"]["reasons"], ["field-control-absent"])

    def test_bad_code_pointer_flag_manager_or_short_data_is_error_not_absence(self):
        for fault in ("code", "package", "pointer", "ready", "template", "owner", "state", "short", "ready-no-manager"):
            with self.subTest(fault=fault):
                session, boundary, memory, actor_reads, _ = self.fixture()
                if fault == "code": memory[0x0203DF8C] = bytes(24)
                elif fault == "package":
                    session.arm9_code_region = (0x0203DF8C, bytes(24))
                    memory[0x0203DF8C] = bytes(24)
                elif fault == "pointer": memory[0x02003000] = struct.pack("<I", 3)
                elif fault == "ready": memory[0x0200306C] = struct.pack("<I", 2)
                elif fault == "short": memory[0x0200306C] = bytes(3)
                elif fault == "ready-no-manager": memory[0x02004000] = bytes(4)
                else:
                    data = list(struct.unpack("<10I", memory[0x02005000]))
                    data[{"template": 0, "owner": 6, "state": 4}[fault]] = 9
                    memory[0x02005000] = struct.pack("<10I", *data)
                boundary()
                self.assertIsNotNone(session.sample_error)
                self.assertEqual(session.pending_samples, [])
                self.assertEqual(actor_reads, [])

    def test_unavailable_field_never_calls_observer_control_actor_reader(self):
        session, boundary, memory, _, _ = self.fixture()
        memory[0x0200306C] = memory[0x02004000] = bytes(4)
        session.observer_control = SimpleNamespace(
            completed_boundary=lambda: self.fail("observer control read an absent actor"),
            result=lambda: {"state": "armed", "closed": False, "cleanupPending": False})
        boundary()
        self.assertIsNotNone(session.sample_error)
        self.assertFalse(session.pending_samples[-1]["fieldAvailable"])
        self.assertEqual(session.pending_samples[-1]["observationErrors"][0]["code"],
                         "observer-control-field-unavailable")

    def test_pending_observer_restore_aborts_before_freed_actor_access(self):
        session, boundary, memory, actor_reads, _ = self.fixture()
        memory[0x0200306C] = memory[0x02004000] = bytes(4)
        session.observer_control = SimpleNamespace(
            completed_boundary=lambda: self.fail("read freed actor"),
            result=lambda: {"state": "complete", "closed": False, "cleanupPending": True})
        class CoreAborted(BaseException): pass
        def abort(error):
            self.assertIn("restoration", str(error))
            raise CoreAborted()
        session.abort_native_control = abort
        with self.assertRaises(CoreAborted): boundary()
        self.assertEqual(actor_reads, [])

    def test_emitted_lifecycle_absence_rows_pass_strict_record_validator(self):
        from tools.overworld.devtools_records import validate_field_absence
        for execute, process in ((0, 0), (1, 3), (2, 0), (3, 2)):
            session, boundary, memory, _, _ = self.fixture()
            memory[0x0200306C] = bytes(4)
            memory[0x02005000] = struct.pack("<10I", *FIELD_TEMPLATE, execute, process,
                                           0x02003000, 0, 0, 0)
            boundary()
            validate_field_absence(session.latest_frame)

    def test_stock_source_anchors_ready_predicate_and_manager_template(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / ".codex-reference/pokeheartgold/src/field_system.c").read_text()
        body = source.split("BOOL sub_0203DF8C(FieldSystem *fieldSystem) {", 1)[1].split("}", 1)[0]
        self.assertIn("return fieldSystem->unk0->unk0 != NULL && fieldSystem->unk6C;", body)


if __name__ == "__main__":
    unittest.main()
