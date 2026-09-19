"""Host-only scope and state controls for optional spawn reader ablation."""
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from tools.overworld.devtools_spawn_cost_probe import LABELS, enable_spawn_cost_probe, gate


class SpawnCostProbeTests(TestCase):
    def fixture(self):
        session = SimpleNamespace(prepared=True, completed_frames=42,
                                  rt=SimpleNamespace(EXECUTED_FRAME_COUNT=99))
        observer = SimpleNamespace(session=session, installed=True,
            calls={label: {} for label in LABELS}, tokens=[object()],
            contexts=[], spawn_contexts=[], finalization_contexts=[],
            spawn_height_contexts=[], policy_contexts=[], reposition_contexts=[], return_tokens=[])
        session.native_observation = observer
        return session, observer

    def test_default_has_no_state_or_changes(self):
        session, observer = self.fixture()
        for label in LABELS + ("behavior-resolved", "walk-policy", "player-step-admitted"):
            self.assertTrue(gate(observer, label))
        self.assertFalse(hasattr(session, "spawn_cost_probe"))

    def test_both_modes_fixed_scope_immutable_metadata_and_no_guest_work(self):
        for mode in ("baseline", "omit-spawn-details"):
            session, observer = self.fixture()
            tokens, calls = observer.tokens, observer.calls.copy()
            receipt = enable_spawn_cost_probe(session, {"mode": mode})
            self.assertFalse(receipt["acceptedProof"])
            self.assertTrue(receipt["acceptanceForbidden"])
            for label in LABELS:
                self.assertEqual(gate(observer, label), mode == "baseline")
            for label in ("behavior-resolved", "main-queue-sampler", "player-step-admitted",
                          "chain-reposition-attempt", "health", "semantic-trace", "unknown"):
                self.assertTrue(gate(observer, label))
            result = session.spawn_cost_probe.result()
            self.assertEqual(set(result["counters"]), set(LABELS))
            self.assertTrue(all(v == {"entries": 1, "omitted": int(mode != "baseline")}
                                for v in result["counters"].values()))
            result["counters"][LABELS[0]]["entries"] = 500
            self.assertEqual(session.spawn_cost_probe.result()["counters"][LABELS[0]]["entries"], 1)
            self.assertIs(observer.tokens, tokens)
            self.assertEqual(observer.calls, calls)
            self.assertEqual((session.completed_frames, session.rt.EXECUTED_FRAME_COUNT), (42, 99))
            with self.assertRaises(AttributeError): session.spawn_cost_probe.mode = "baseline"
            for again in (mode, "baseline", "omit-spawn-details"):
                with self.assertRaises(ValueError): enable_spawn_cost_probe(session, {"mode": again})

    def test_bad_mode_and_inflight_work_rejected_without_enabling(self):
        for args in ({}, {"mode": "off"}, {"mode": True}, {"mode": "baseline", "extra": 1}, None):
            session, _ = self.fixture()
            with self.assertRaises(ValueError): enable_spawn_cost_probe(session, args)
            self.assertFalse(hasattr(session, "spawn_cost_probe"))
        for name in ("contexts", "spawn_contexts", "finalization_contexts", "spawn_height_contexts",
                     "policy_contexts", "reposition_contexts", "return_tokens"):
            session, observer = self.fixture()
            getattr(observer, name).append(object())
            with self.assertRaisesRegex(ValueError, "in-flight"):
                enable_spawn_cost_probe(session, {"mode": "baseline"})
            self.assertFalse(hasattr(session, "spawn_cost_probe"))
        for name, value in (("native_bridge_active", True), ("pending_samples", []), ("prepared", False)):
            session, _ = self.fixture()
            setattr(session, name, value)
            with self.assertRaises(ValueError): enable_spawn_cost_probe(session, {"mode": "baseline"})

    def test_changed_observer_and_counter_exhaustion_latch_failure(self):
        session, observer = self.fixture()
        enable_spawn_cost_probe(session, {"mode": "baseline"})
        with patch("tools.overworld.devtools_spawn_cost_probe.MAX_COUNT", 1):
            self.assertTrue(gate(observer, LABELS[0]))
            with self.assertRaises(ValueError) as first: gate(observer, LABELS[0])
            with self.assertRaises(ValueError) as later: gate(observer, "behavior-resolved")
            self.assertIs(first.exception, later.exception)
        self.assertIsNotNone(session.spawn_cost_probe.result()["failure"])
        session, observer = self.fixture()
        enable_spawn_cost_probe(session, {"mode": "baseline"})
        with self.assertRaisesRegex(ValueError, "observer changed"):
            gate(SimpleNamespace(session=session), LABELS[0])

    def test_real_installed_tap_omits_whole_reader_before_scope_without_unhooking(self):
        from tools.overworld.devtools_observer import NativeObservation
        for mode in ("baseline", "omit-spawn-details"):
            session, observer = self.fixture()
            address, code = 0x02001000, bytes(32)
            seen, callbacks = [], {}
            session.code_regions = [(address, code)]
            session.read = lambda *_: seen.append("read") or code
            session.emu = SimpleNamespace(memory=SimpleNamespace(
                register_arm9=SimpleNamespace(sp=0x027E1000, lr=0x02001101, r0=0)))
            def add(pc, callback):
                callbacks[pc] = callback
                return pc
            observer.hooks = SimpleNamespace(add=add, remove=lambda pc: callbacks.pop(pc))
            observer.MAX_DEPTH = 64
            observer.TIMED_CALLS = NativeObservation.TIMED_CALLS
            observer._guest_clock = lambda: seen.append("guest-clock") or {}
            observer._clock = lambda: dict(nativeCycle=99, actorFrame=20)
            observer._queue = lambda *_: seen.append("queue")
            NativeObservation._tap(observer, LABELS[0], address, code,
                lambda: seen.append("before") or {},
                lambda *_: seen.append("after") or {},
                scope=lambda: seen.append("scope") or True)
            enable_spawn_cost_probe(session, {"mode": mode})
            callbacks[address]()
            if mode == "baseline":
                self.assertEqual(seen, ["scope", "read", "before", "guest-clock"])
                callbacks[0x02001101]()
                self.assertEqual(seen, ["scope", "read", "before", "guest-clock",
                                        "read", "guest-clock", "after", "queue"])
            else:
                self.assertEqual(seen, [])
            self.assertEqual(set(callbacks), {address})
            self.assertEqual(observer.contexts, [])
            self.assertEqual(observer.return_tokens, [])


if __name__ == "__main__": main()
