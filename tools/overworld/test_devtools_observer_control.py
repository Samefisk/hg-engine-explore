"""Actual native readers and MotionRecorder over a small fake RAM transport."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_observer_control import NativeObserverControl, ObserverControlFailure
from tools.overworld.devtools_runtime import actor_identity_checks
from tools.overworld.normal_play_observer import MotionRecorder, live_identity


class ScalarMemory:
    def __init__(self, memory, signed=False):
        self.memory, self.signed = memory, signed

    def __getitem__(self, key):
        if key.start == key.stop:
            return int.from_bytes(self.memory.read(key.start, key.step), "little", signed=self.signed)
        assert key.step == 1
        return list(self.memory.read(key.start, key.stop - key.start))

    def __setitem__(self, key, values):
        assert key.step == 1 and key.stop - key.start == len(values)
        self.memory.writes.append((key.start, bytes(values)))
        self.memory.put(key.start, bytes(values))


class Memory:
    def __init__(self):
        self.data, self.writes = {}, []
        self.unsigned, self.signed = ScalarMemory(self), ScalarMemory(self, True)

    def put(self, address, data):
        self.data.update({address + offset: byte for offset, byte in enumerate(data)})

    def u32(self, address, value):
        self.put(address, struct.pack("<I", value & 0xFFFFFFFF))

    def u16(self, address, value):
        self.put(address, struct.pack("<H", value))

    def read(self, address, size):
        return bytes(self.data.get(address + offset, 0) for offset in range(size))


class NativeControlTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).with_name("devtools_engine.py")
        spec = importlib.util.spec_from_file_location("control_fixture_engine", path)
        rt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rt)
        self.mem = Memory()
        self.field, self.manager, self.objects = 0x02110000, 0x02200000, 0x02210000
        self.obj = self.objects + 17 * 0x12C
        rt.G_FIELD_SYS_PTR, rt.WILD_STATE = 0x02100000, 0x02220000
        rt.ACTOR_DESCRIPTOR = {"state": {"address": 0x02300000,
                               "offsets": {"fieldEpoch": 12, "mapGeneration": 46}}}
        rt.EXECUTED_FRAME_COUNT = 200
        self.actor = {"active": True, "role": "WILD", "species": 165, "form": 0, "level": 10,
                      "subjectIdentity": 55, "presentationAttached": True,
                      "authorityGeneration": 1, "engineAnchorGeneration": 1, "presentationGeneration": 1,
                      "handle": {"value": 65536, "slot": 0, "generation": 1,
                                 "fieldEpoch": 2, "mapGeneration": 3, "encounterGeneration": 4},
                      "motionKind": "WALK", "motionPhase": "MOVING", "motionElapsed": 0,
                      "motionDuration": 5, "origin": {"x": 0, "y": 0}, "target": {"x": 2, "y": 2},
                      "logical": {"x": 0, "y": 0}, "commitSequence": 0,
                      "behaviorFingerprint": 123, "reservationId": 2}
        rt.actor_state = lambda emu, slot: deepcopy(self.actor)
        for address, value in ((rt.G_FIELD_SYS_PTR, self.field), (self.field + 0x3C, self.manager),
                               (self.manager + 4, 64), (self.manager + 0x124, self.objects),
                               (self.field + rt.FIELD_LOCATION_OFFSET, 0x02120000),
                               (0x02120000, 33), (0x02300000, 0x5353574F),
                               (self.obj, 0x20000001), (self.obj + 8, 0xE0),
                               (self.obj + 12, 33), (self.obj + 32, 2074),
                               (self.obj + 0xB4, self.manager), (rt.WILD_STATE, self.obj),
                               (rt.WILD_STATE + 4, 55)):
            self.mem.u32(address, value)
        for address, value in ((0x0230000C, 2), (0x0230002E, 3),
                               (rt.WILD_STATE + 8, 33), (rt.WILD_STATE + 10, 165),
                               (rt.WILD_STATE + 18, 4)):
            self.mem.u16(address, value)
        self.mem.put(rt.WILD_STATE + 12, bytes([0, 10]))
        self.mem.put(rt.WILD_STATE + 16, bytes([1, 0xE0]))
        self.session = SimpleNamespace(rt=rt, emu=SimpleNamespace(memory=self.mem), closed=False,
                                       native_bridge_active=False, completed_frames=100)
        self.subject = {key: deepcopy(self.actor[key]) for key in
                        ("handle", "subjectIdentity", "species", "role")}
        self.pose(0)

    def pose(self, elapsed):
        value = 0x8000 + 2 * 0x10000 * elapsed // 5
        self.mem.u32(self.obj + 0x70, value)
        self.mem.u32(self.obj + 0x74, 1234)
        self.mem.u32(self.obj + 0x78, value)
        self.mem.u32(self.obj + 0x28, 1)

    def boundary(self, control, elapsed):
        self.actor["motionElapsed"] = elapsed
        self.pose(elapsed)  # Fake native engine applies a real advancing pose.
        self.session.completed_frames += 1
        self.session.rt.EXECUTED_FRAME_COUNT += 2
        receipts = control.completed_boundary() if control else []
        # Same readers as the real session snapshot, AFTER the fault callback.
        engine = self.session.rt.object_state(self.session.emu, self.obj)
        return receipts, engine

    def control(self, kind, **kwargs):
        control = NativeObserverControl(self.session, self.subject)
        control.arm(kind, **kwargs)
        return control

    def test_real_recorder_rejects_native_stall_but_accepts_positive_samples(self):
        positive = MotionRecorder()
        for elapsed in range(3):
            _, pose = self.boundary(None, elapsed)
            positive.observe(self.session.completed_frames, self.actor, pose)
        self.assertEqual(positive.failures, [])
        control = self.control("render-stall")
        recorder = MotionRecorder()
        for elapsed in range(3):
            receipts, pose = self.boundary(control, elapsed)
            recorder.observe(self.session.completed_frames, self.actor, pose)
        self.assertEqual([failure["reason"] for failure in recorder.failures], ["render-stall"] * 2)
        self.assertEqual(control.result()["state"], "complete")
        self.assertEqual(control.result()["writes"], 2)
        self.assertEqual(len(self.mem.writes), 4)
        self.assertEqual({address for address, _ in self.mem.writes}, {self.obj + 0x70, self.obj + 0x78})
        for row in control.result()["receipts"]:
            self.assertEqual(row["subject"], self.subject)
            self.assertEqual(row["sourceIdentity"]["object"], self.obj)
            self.assertEqual(row["engineIdentity"]["pointer"], self.obj)
        changed = control.result()["receipts"][-1]
        self.assertNotEqual(changed["beforePose"]["pos_x"], changed["afterPose"]["pos_x"])
        self.assertEqual(changed["afterPose"]["pos_y"], 1234)
        control.close()
        self.assertEqual(len(self.mem.writes), 4, "render cleanup cannot rewrite a later engine pose")

    def test_inactive_fault_reaches_real_identity_reader_and_restores_only_owned_bit(self):
        control = self.control("inactive-object")
        self.boundary(control, 0)
        rt, emu = self.session.rt, self.session.emu
        source, engine = rt.wild_spawn(emu, 0), rt.live_wild_object_identity(emu, 0)
        self.assertFalse(engine["active"])
        self.assertFalse(live_identity(self.actor, source, engine, species=165, role="WILD", current_epoch=2))
        checks = actor_identity_checks(self.actor, source, engine,
                                       {"fieldEpoch": 2, "mapGeneration": 3, "mapId": 33}, 0)
        self.assertEqual([name for name, passed in checks.items() if not passed], ["engineActive"])
        self.assertEqual(self.mem.read(self.obj, 4), struct.pack("<I", 0x20000000))
        self.mem.u32(self.obj, 0x20004000)  # A different native flag changes after the injection.
        control.close()
        self.assertEqual(self.mem.read(self.obj, 4), struct.pack("<I", 0x20004001))
        self.assertEqual({address for address, _ in self.mem.writes}, {self.obj})
        self.assertFalse(control.result()["cleanupPending"])
        self.assertEqual(control.result()["receipts"][-1]["action"], "active-bit-restored")
        before = len(self.mem.writes)
        control.close()
        self.assertEqual(len(self.mem.writes), before)

    def test_arming_has_no_writes_and_unknown_mode_or_subject_is_rejected(self):
        for key, value in (("species", 56), ("role", "MOUNTED")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                NativeObserverControl(self.session, {**self.subject, key: value})
        for kind, frames in (("write-memory", 10), ("render-stall", 0), ("render-stall", 5001)):
            with self.subTest(kind=kind, frames=frames), self.assertRaises(ValueError):
                NativeObserverControl(self.session, self.subject).arm(kind, max_frames=frames)
        control = self.control("render-stall")
        self.assertEqual(self.mem.writes, [])
        with self.assertRaises(ValueError):
            control.arm("inactive-object")

    def test_wild_same_species_replacement_cannot_receive_fault_or_cleanup(self):
        for change in ("handle", "personality", "pointer", "presentationGeneration", "manager"):
            with self.subTest(change=change):
                self.setUp()
                control = self.control("inactive-object")
                self.boundary(control, 0)
                count = len(self.mem.writes)
                if change == "handle":
                    self.actor["handle"].update(generation=2, value=131072)
                elif change == "personality":
                    self.actor["subjectIdentity"] = 66
                    self.mem.u32(self.session.rt.WILD_STATE + 4, 66)
                elif change == "pointer":
                    self.mem.u32(self.session.rt.WILD_STATE, self.obj + 0x12C)
                elif change == "manager":
                    self.mem.u32(self.field + 0x3C, self.manager + 4)
                else:
                    self.actor[change] += 1
                with self.assertRaises(ObserverControlFailure):
                    control.close()
                self.assertEqual(len(self.mem.writes), count)
                self.assertTrue(control.result()["cleanupPending"])
                self.assertIsNotNone(control.result()["failure"])

    def test_every_write_rechecks_owner_epoch_map_and_source(self):
        control = self.control("render-stall")
        self.boundary(control, 0)
        self.mem.u16(0x0230002E, 4)
        with self.assertRaises(ObserverControlFailure):
            self.boundary(control, 1)
        self.assertEqual(self.mem.writes, [])

    def test_first_id_duplicate_or_inactive_object_cannot_be_armed(self):
        for duplicate in (True, False):
            with self.subTest(duplicate=duplicate):
                self.setUp()
                if duplicate:
                    self.mem.u32(self.objects, 1)
                    self.mem.u32(self.objects + 8, 0xE0)
                else:
                    self.mem.u32(self.obj, 0)
                with self.assertRaises(ObserverControlFailure):
                    self.control("inactive-object")
                self.assertEqual(self.mem.writes, [])

    def test_wait_has_bounded_deadline_and_never_edits_reposition_or_hop(self):
        control = self.control("render-stall", max_frames=2)
        for kind in ("REPOSITION", "HOP"):
            self.actor["motionKind"] = kind
            self.boundary(control, 0)
        with self.assertRaisesRegex(ObserverControlFailure, "deadline"):
            self.boundary(control, 0)
        self.assertEqual(self.mem.writes, [])

    def test_short_walk_is_skipped_until_two_later_samples_are_available(self):
        control = self.control("render-stall")
        self.actor.update(motionKind="WALK", motionDuration=2)
        self.boundary(control, 0)
        self.assertEqual(control.result()["state"], "armed")
        self.assertEqual(self.mem.writes, [])
        self.actor.update(motionDuration=5, commitSequence=1)
        self.boundary(control, 0)
        self.assertEqual(control.result()["state"], "applying")
        self.assertEqual(self.mem.writes, [])

    def test_duplicate_callback_deduplicates_but_frame_gap_fails(self):
        control = self.control("render-stall")
        self.boundary(control, 0)
        before = control.result()
        self.assertEqual(control.completed_boundary(), [])
        self.assertEqual(control.result(), before)
        self.session.completed_frames += 2
        with self.assertRaisesRegex(ObserverControlFailure, "missed"):
            control.completed_boundary()

    def test_new_motion_cannot_be_substituted_after_pin(self):
        control = self.control("render-stall")
        self.boundary(control, 0)
        self.actor["target"]["x"] += 1
        with self.assertRaisesRegex(ObserverControlFailure, "exact motion"):
            self.boundary(control, 1)
        self.assertEqual(self.mem.writes, [])

    def test_incomplete_control_is_not_completed_by_close(self):
        control = self.control("render-stall")
        self.boundary(control, 0)
        with self.assertRaisesRegex(ObserverControlFailure, "before the fault"):
            control.close()
        self.assertEqual(control.result()["state"], "failed")

    def test_failed_write_is_explicit_and_does_not_report_completion(self):
        for kind in ("render-stall", "inactive-object"):
            with self.subTest(kind=kind):
                self.setUp()
                control = self.control(kind)
                if kind == "render-stall":
                    self.boundary(control, 0)
                self.session.rt.actor_memory_write = lambda *args: None
                with self.assertRaisesRegex(ObserverControlFailure, "readback"):
                    self.boundary(control, 1)
                self.assertEqual(control.result()["state"], "failed")
                self.assertIsNotNone(control.result()["failure"])

    def test_read_error_is_retained_before_fault_write(self):
        control = self.control("inactive-object")
        self.session.rt.wild_spawn = lambda *args: (_ for _ in ()).throw(ValueError("lost read"))
        with self.assertRaisesRegex(ObserverControlFailure, "native read failed"):
            self.boundary(control, 0)
        self.assertEqual(self.mem.writes, [])
        self.assertEqual(control.result()["state"], "failed")

    def test_exception_after_inactive_write_retains_cleanup_ownership(self):
        control = self.control("inactive-object")
        real_write = self.session.rt.actor_memory_write
        def write_then_fail(*args):
            real_write(*args)
            raise RuntimeError("transport uncertain after write")
        self.session.rt.actor_memory_write = write_then_fail
        with self.assertRaisesRegex(ObserverControlFailure, "write failed") as caught:
            self.boundary(control, 0)
        self.assertTrue(caught.exception.fatal)
        self.assertTrue(control.result()["cleanupPending"])
        self.session.rt.actor_memory_write = real_write
        control.close()
        self.assertFalse(control.result()["cleanupPending"])
        self.assertEqual(control.result()["state"], "failed", "cleanup cannot erase first failure")


if __name__ == "__main__":
    unittest.main()
