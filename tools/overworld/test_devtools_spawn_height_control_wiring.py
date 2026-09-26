"""Host-only checks of native height callback wiring and fatal exit routing."""
from copy import deepcopy
import os
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.overworld.devtools_runtime import DevtoolsSession
from tools.overworld.devtools_spawn_height_control import NativeSpawnHeightReadControl
from tools.overworld.test_devtools_spawn_height_observer import SpawnHeightFixture


class SpawnHeightWiringTests(unittest.TestCase):
    def test_stderr_failure_cannot_prevent_fatal_worker_exit(self):
        with patch.object(os, "write", side_effect=OSError("closed stderr")), \
                patch.object(os, "_exit", side_effect=SystemExit(70)) as exit_worker:
            with self.assertRaises(SystemExit) as error:
                DevtoolsSession.abort_native_control(None, RuntimeError("restore failed"))
            self.assertEqual(error.exception.code, 70)
            exit_worker.assert_called_once_with(70)

    def test_internal_arm_has_no_raw_address_or_rearming(self):
        session = SimpleNamespace(prepared=False, native_bridge_active=False)
        value = DevtoolsSession.spawn_height_control_arm(session, {})
        self.assertEqual(value["state"], "armed")
        with self.assertRaises(Exception): DevtoolsSession.spawn_height_control_arm(session, {})
        for args, prepared, bridge in (({"address": 0x02210074}, False, False),
                                       ({}, True, False), ({}, False, True)):
            with self.assertRaises(Exception):
                DevtoolsSession.spawn_height_control_arm(
                    SimpleNamespace(prepared=prepared, native_bridge_active=bridge), args)

    def fixture(self):
        directory = tempfile.TemporaryDirectory(prefix="height-wiring-")
        self.addCleanup(directory.cleanup)
        f = SpawnHeightFixture(directory.name)
        f.source["species"] = 179
        f.actor["species"] = 179
        f.closed, f.native_bridge_active, f.completed_frames = False, False, 11
        f.spawn_height_control = NativeSpawnHeightReadControl()
        f.spawn_height_control.arm()
        pointer = f.source["object"]
        f.put(pointer + 0x74, struct.pack("<i", 8192))
        original_pose = f.rt.object_state
        def pose(emu, address):
            value = deepcopy(original_pose(emu, address))
            if address == pointer:
                value["pos_y"] = struct.unpack("<i", f.read(pointer + 0x74, 4))[0]
            return value
        f.rt.object_state = pose
        writes = []
        def write(emu, address, data):
            self.assertEqual((address, len(data)), (pointer + 0x74, 4))
            writes.append(bytes(data))
            f.put(address, data)
        f.rt.actor_memory_write = write
        return f, writes

    def test_installed_callback_reads_real_height_three_times_and_consumes_once(self):
        f, writes = self.fixture()
        f.start_initial(); f.height(caller=f.spawn_prepared); f.refresh(); f.surface(result=0)
        f.finish_height()
        self.assertIsNone(f.hooks.error)
        self.assertEqual(f.observer.spawn_height_contexts, [])
        events = f.finish_initial()
        self.assertIsNone(f.hooks.error)
        controls = [e["data"] for e in events if e["data"]["observation"] == "spawn-height-read-control"]
        self.assertEqual(len(controls), 1)
        control = controls[0]
        self.assertEqual(control["clean"], control["restored"])
        expected_bad = deepcopy(control["clean"])
        expected_bad["positionAfter"]["pos_y"] += 4096
        self.assertEqual(control["bad"], expected_bad)
        normal = next(e["data"] for e in events if e["data"]["observation"] == "spawn-landing-height")
        self.assertEqual(normal["positionAfter"], control["clean"]["positionAfter"])
        self.assertEqual(writes, [struct.pack("<i", 12288), struct.pack("<i", 8192)])

    def test_completed_boot_frames_retain_only_the_controlled_appear_hop(self):
        f, _ = self.fixture()
        f.start_initial(); f.height(caller=f.spawn_prepared); f.refresh(); f.surface(result=0)
        f.finish_height(); f.returned(1)
        commands = ((255, 0, 0), (48, 0, 0), (48, 4096, 1),
                    (62, 2048, 1), (74, 0, 1), (255, 0, 1),
                    (62, 0, 0), (255, 0, 0))
        for frame, (command, face_y, controller) in enumerate(commands, 12):
            actor = deepcopy(f.actor)
            actor.update(controllerState=controller)
            actor["engineObject"] = {**deepcopy(f.player), "movement_cmd": command,
                                     "face_y": face_y}
            snapshot = {"frame": frame, "nativeCycle": frame + 10,
                "actorFrame": frame + 100, "actors": [actor],
                "context": {"mapId": f.map_id, "fieldEpoch": 2,
                            "mapGeneration": 3},
                "observationBoundary": "main-task-queue-completion",
                "prepared": False}
            f.observer.completed_frame(frame)
            f.observer.completed_snapshot(snapshot)
        events = f.observer.drain()
        samples = [event for event in events
                   if event["data"]["observation"] == "spawn-appear-hop-frame"]
        self.assertEqual([event["data"]["actor"]["engineObject"]["movement_cmd"]
                          for event in samples], [48, 48, 62, 74, 255, 62, 255])
        self.assertTrue(f.observer.spawn_height_trace["complete"])

    def test_restore_failure_exits_from_callback_before_normal_publication(self):
        f, writes = self.fixture()
        real_write = f.rt.actor_memory_write
        def write(emu, address, data):
            if writes: raise OSError("restore failed")
            real_write(emu, address, data)
        f.rt.actor_memory_write = write
        exits = []
        def abort(error):
            exits.append(error)
            raise SystemExit(70)  # Model worker exit without ending the host test.
        f.abort_native_control = abort
        f.start_initial(); f.height(caller=f.spawn_prepared); f.refresh(); f.surface(result=0)
        with self.assertRaises(SystemExit): f.finish_height()
        self.assertEqual(len(exits), 1)
        self.assertTrue(exits[0].fatal)
        self.assertEqual(f.spawn_height_control.state, "failed")
        self.assertTrue(f.spawn_height_control.cleanup_pending)
        self.assertEqual(len(f.observer.spawn_height_contexts), 1)
        self.assertFalse(any(e.get("observation") in ("spawn-height-read-control", "spawn-landing-height")
                             for e in f.observer.pending))


if __name__ == "__main__":
    unittest.main()
