"""Installed native publication tap controls; no emulator or game proof."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.overworld import devtools_runtime as runtime
from tools.overworld.test_devtools_trace import NativeRing, natives, notices


class PublicationTests(unittest.TestCase):
    def test_failed_install_does_not_skip_installation_on_retry(self):
        ring = NativeRing()
        session = runtime.DevtoolsSession.__new__(runtime.DevtoolsSession)
        session.rt = SimpleNamespace(REPO=Path(__file__).resolve().parents[2], ACTOR_DESCRIPTOR=ring.descriptor)
        session.read, session.semantic_trace = ring.read, None
        with patch.object(session, "_install_trace_publication", side_effect=[RuntimeError("install failed"), None]) as install:
            with self.assertRaisesRegex(RuntimeError, "install failed"):
                session._ensure_trace()
            self.assertIsNone(session.semantic_trace)
            session._ensure_trace()
            self.assertIsNotNone(session.semantic_trace)
            self.assertEqual(install.call_count, 2)

    def test_failed_native_dispatch_registration_can_retry(self):
        with patch.object(SimpleNamespace(register_exec=None), "register_exec", side_effect=[RuntimeError("native install failed"), None]) as register:
            hooks = runtime.DevtoolsHooks(None, SimpleNamespace(memory=SimpleNamespace(register_exec=register)))
            with self.assertRaisesRegex(RuntimeError, "native install failed"):
                hooks.add(0x02001000, lambda: None)
            self.assertEqual(hooks.callbacks, {})
            hooks.add(0x02001000, lambda: None)
            self.assertEqual(register.call_count, 2)

    def fixture(self):
        ring = NativeRing()
        entry, returned = 0x023B7028, 0x02001100
        code = bytes(range(128))
        callbacks = {}
        regs = SimpleNamespace(sp=0x027E3D00, lr=returned | 1)
        emu = SimpleNamespace(memory=SimpleNamespace(register_arm9=regs,
            register_exec=lambda address, callback: callbacks.__setitem__(address, callback)))
        session = runtime.DevtoolsSession.__new__(runtime.DevtoolsSession)
        session.rt = SimpleNamespace(REPO=Path(__file__).resolve().parents[2], ACTOR_DESCRIPTOR=ring.descriptor)
        session.emu = emu
        session.read = lambda address, size: code[address-entry:address-entry+size] if entry <= address < entry+128 else ring.read(address, size)
        session.packaged_code = lambda address, size: code[:size]
        session.party_getter_hooks = runtime.DevtoolsHooks(session.rt, emu)
        session.completed_frames = 40
        session.semantic_trace = ring.tap()
        session.semantic_trace.start(60)
        session.trace_observing = True
        session.trace_request = None
        session.trace_events, session.trace_events_dropped = [], 0
        session.native_observation = None
        with patch.object(runtime, "_elf_function_extent", return_value=(entry, 128)), \
                patch.object(runtime, "_elf_code", return_value=code):
            session._install_trace_publication()
        session._complete_trace_boundary()
        session.drain_events()
        def emit(count=1):
            for _ in range(count):
                callbacks[entry](entry, 2)
                ring.emit(13, frame=21)
                callbacks[returned](returned, 2)
        return session, ring, callbacks, emit

    def test_more_than_one_ring_in_one_game_frame_is_not_lost_or_published_early(self):
        session, ring, _, emit = self.fixture()
        writes = list(ring.writes)
        emit(44)
        self.assertEqual(session.drain_events(), [])
        session.completed_frames += 1
        session._complete_trace_boundary()
        result = session.drain_events()
        self.assertEqual([e["sequence"] for e in natives(result)], list(range(1, 45)))
        self.assertEqual({e["frame"] for e in result}, {41})
        self.assertEqual({e["actorFrame"] for e in natives(result)}, {21})
        self.assertNotIn("unread-events-lost", notices(result))
        self.assertEqual(ring.writes, writes)
        self.assertEqual(session.drain_events(), [])

    def test_missed_native_callback_still_reports_actual_loss(self):
        session, ring, _, _ = self.fixture()
        for _ in range(44): ring.emit(13)
        session.completed_frames += 1
        session._complete_trace_boundary()
        self.assertEqual(notices(session.drain_events())["unread-events-lost"]["count"], 28)

    def test_filtered_writer_return_does_not_invent_an_event(self):
        session, ring, callbacks, _ = self.fixture()
        for _ in range(24):
            callbacks[0x023B7028](0x023B7028, 2)
            callbacks[0x02001100](0x02001100, 2)
        session.completed_frames += 1
        session._complete_trace_boundary()
        self.assertEqual(session.drain_events(), [])

    def test_stop_keeps_pending_tail_and_stamps_only_the_completed_boundary(self):
        session, ring, _, emit = self.fixture()
        emit(44)
        session.trace_request = {"operation": "stop", "complete": False}
        session.completed_frames += 1
        session._complete_trace_boundary()
        result = session.drain_events()
        self.assertEqual([e["sequence"] for e in natives(result)], list(range(1, 45)))
        self.assertEqual({e["frame"] for e in result}, {41})
        self.assertIn("window-ended", notices(result))
        self.assertFalse(session.trace_observing)
        self.assertEqual(session.trace_pending, [])

    def test_changed_resident_entry_fails_without_reading_ring(self):
        session, ring, callbacks, _ = self.fixture()
        session.read = lambda address, size: bytes(size)
        callbacks[0x023B7028](0x023B7028, 2)
        self.assertIn("trace publication", session.party_getter_hooks.error)
        self.assertEqual(session.drain_events(), [])

    def test_return_with_wrong_stack_cannot_publish_partial_record(self):
        session, ring, callbacks, _ = self.fixture()
        callbacks[0x023B7028](0x023B7028, 2)
        for _ in range(8): ring.emit(13)
        session.emu.memory.register_arm9.sp -= 8
        callbacks[0x02001100](0x02001100, 2)
        self.assertEqual(session.drain_events(), [])
        session.emu.memory.register_arm9.sp += 8
        callbacks[0x02001100](0x02001100, 2)
        session.completed_frames += 1
        session._complete_trace_boundary()
        self.assertEqual(len(natives(session.drain_events())), 8)


if __name__ == "__main__": unittest.main()
