"""Exercise the real shared cycle path; fake CPU, no emulator or screenshots."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure, FieldReturnBridge
from tools.overworld.devtools_runtime_health import RuntimeHealthMonitor


class RuntimeHealthWiringTests(unittest.TestCase):
    def fixture(self, *, mode=0x1F, advancing=False):
        session = DevtoolsSession.__new__(DevtoolsSession)
        registers = SimpleNamespace(cpsr=mode, pc=0xFFFF010C, lr=0x023BF59A, sp=0)
        session.emu = SimpleNamespace(memory=SimpleNamespace(register_arm9=registers))
        session.completed_frames = 381
        session.native_bridge_active = False
        session.runtime_health = RuntimeHealthMonitor(381, 0)
        session.runtime_health_failure = None
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
