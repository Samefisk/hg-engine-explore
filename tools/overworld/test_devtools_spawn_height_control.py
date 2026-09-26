"""Faults pass through a native-memory-backed reader, not edited receipts."""
from copy import deepcopy
import struct
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_spawn_height_control import NativeSpawnHeightReadControl, SpawnHeightControlFailure


class SpawnHeightControlTests(unittest.TestCase):
    def setUp(self):
        self.pointer = 0x02210000
        self.memory = bytearray(struct.pack("<i", 12345))
        self.writes = []
        self.source = dict(object=self.pointer, species=179, form=0, level=5, personality=42,
                           active=True, encounter_generation=4, object_id=224, map_id=33)
        self.world = dict(fieldPointer=0x02110000, statePointer=0x02310000, mapId=33,
                          fieldEpoch=2, mapGeneration=3)
        self.engine = dict(pointer=self.pointer, active=True, in_manager=True,
                           object_manager=0x02200000, current_manager=0x02200000,
                           object_id=224, object_map_id=33, script_id=2074,
                           id_lookup=dict(status="complete", eligible_count=1, pointer_matches=True))
        prepared = {k: self.source[k] for k in ("species", "form", "level", "personality")}
        self.template = dict(status="observed", nativeReturnKind="void", returnValue=None,
            heightSource="native-refresh", slot=0, sourceIdentity=deepcopy(self.source),
            worldContext=self.world, engineIdentity=deepcopy(self.engine), engineIdentityAfter=deepcopy(self.engine),
            target=[4, 5], preparedPointer=0x02290000, preparedEncounter=prepared,
            surfaceQuery=dict(returnValue=0, hit=None),
            heightRefresh=dict(returnValue=1, objectPointer=self.pointer, positionBefore=dict(flags=1),
                               positionAfter=dict(pos_y=12345)), positionAfter=dict(x=4, y=5, pos_y=12345, flags=1))
        self.record = dict(sourceIdentity=deepcopy(self.source), target=[4, 5], initialPlacement=True, _spawn=dict(
            startup=dict(locomotion=7, target=[4, 5]), position=[4, 5], slot=0,
            worldContext=self.world, preparedPointer=0x02290000, preparedEncounter=prepared))
        rt = SimpleNamespace(ACTOR_DESCRIPTOR={"state": {"address": 0x02300000,
                                "offsets": {"fieldEpoch": 12, "mapGeneration": 46}}},
            G_FIELD_SYS_PTR=0x02010000, WILD_STATE=0x02310000, EXECUTED_FRAME_COUNT=20,
            unsigned=lambda emu, address, size=4: {0x02010000:0x02110000, 0x0230000C:2, 0x0230002E:3}[address],
            field_map_id=lambda emu:33, wild_spawn=lambda emu, slot:deepcopy(self.source),
            live_wild_object_identity=lambda emu, slot:deepcopy(self.engine), actor_memory_write=self.write)
        self.session = SimpleNamespace(rt=rt, emu=object(), closed=False, native_bridge_active=False,
                                       completed_frames=10, read=self.read)
        self.control = NativeSpawnHeightReadControl()
        self.control.arm()

    def read(self, address, size):
        self.assertEqual((address, size), (self.pointer + 0x74, 4))
        return bytes(self.memory)

    def write(self, emu, address, data):
        self.assertEqual(address, self.pointer + 0x74)
        self.assertEqual(len(data), 4)
        self.writes.append(bytes(data))
        self.memory[:] = data

    def reader(self):
        receipt = deepcopy(self.template)
        receipt["positionAfter"]["pos_y"] = struct.unpack("<i", self.memory)[0]
        return receipt

    def test_same_reader_observes_fault_and_restore_once_without_record_edits(self):
        before = deepcopy(self.record)
        clean = self.control.capture(self.session, self.record, self.reader)
        result = self.control.result()
        self.assertEqual(clean, self.template)
        self.assertEqual(result["state"], "complete")
        self.assertEqual(result["receipt"]["bad"]["positionAfter"]["pos_y"], 12345 + 4096)
        self.assertEqual(result["receipt"]["restored"], clean)
        self.assertEqual(self.record, before)
        self.assertFalse(result["cleanupPending"])
        self.control.capture(self.session, self.record, self.reader)
        self.assertEqual(len(self.writes), 2)
        with self.assertRaises(ValueError): self.control.arm()

    def test_unrelated_species_does_not_consume_arm(self):
        self.template["sourceIdentity"]["species"] = 10
        self.control.capture(self.session, self.record, self.reader)
        self.assertEqual(self.control.state, "armed")
        self.assertEqual(self.writes, [])

    def test_wrong_actor_and_missing_data_fail_before_write(self):
        for mutate in (lambda:self.source.update(personality=99), lambda:self.template.pop("heightRefresh")):
            self.setUp()
            mutate()
            with self.assertRaises(SpawnHeightControlFailure):
                self.control.capture(self.session, self.record, self.reader)
            self.assertEqual(self.writes, [])

    def test_bad_reader_or_exception_restores_memory(self):
        for raises in (False, True):
            self.setUp()
            def reader():
                if self.writes and len(self.writes) == 1:
                    if raises: raise ValueError("read failed")
                    return deepcopy(self.template)  # Wrong reader hides native fault.
                return self.reader()
            with self.assertRaises(SpawnHeightControlFailure):
                self.control.capture(self.session, self.record, reader)
            self.assertEqual(struct.unpack("<i", self.memory)[0], 12345)
            self.assertFalse(self.control.cleanup_pending)

    def test_restore_write_exception_is_fatal(self):
        def write(emu, address, data):
            if self.writes: raise OSError("restore unavailable")
            self.write(emu, address, data)
        self.session.rt.actor_memory_write = write
        with self.assertRaises(SpawnHeightControlFailure) as raised:
            self.control.capture(self.session, self.record, self.reader)
        self.assertTrue(raised.exception.fatal)
        self.assertTrue(self.control.cleanup_pending)

    def test_fault_reader_cannot_change_other_evidence(self):
        def reader():
            value = self.reader()
            if len(self.writes) == 1:
                value["heightRefresh"]["positionAfter"]["pos_y"] += 4096
            return value
        with self.assertRaisesRegex(SpawnHeightControlFailure, "only the height fault"):
            self.control.capture(self.session, self.record, reader)
        self.assertEqual(struct.unpack("<i", self.memory)[0], 12345)

    def test_partial_injection_write_failure_still_restores(self):
        def write(emu, address, data):
            self.write(emu, address, data)
            if len(self.writes) == 1: raise OSError("write completed but response failed")
        self.session.rt.actor_memory_write = write
        with self.assertRaises(SpawnHeightControlFailure):
            self.control.capture(self.session, self.record, self.reader)
        self.assertEqual(struct.unpack("<i", self.memory)[0], 12345)
        self.assertFalse(self.control.cleanup_pending)

    def test_changed_binding_is_restored_then_fatal(self):
        def reader():
            value = self.reader()
            if self.writes: self.source["personality"] = 99
            return value
        with self.assertRaises(SpawnHeightControlFailure) as raised:
            self.control.capture(self.session, self.record, reader)
        self.assertTrue(raised.exception.fatal)
        self.assertEqual(struct.unpack("<i", self.memory)[0], 12345)


if __name__ == "__main__":
    unittest.main()
