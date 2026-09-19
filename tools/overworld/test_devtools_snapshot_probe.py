"""Paused diagnostic tests: fake memory boundary, no native core."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from tools.overworld.devtools_snapshot_probe import probe_snapshot


class SnapshotProbeTests(TestCase):
    def fixture(self):
        calls = []
        emu = SimpleNamespace(call=lambda *args: calls.append(args), handle=1)
        session = SimpleNamespace(emu=emu, completed_frames=12,
                                  rt=SimpleNamespace(EXECUTED_FRAME_COUNT=30))
        value = dict(frame=12, nativeCycle=30, actors=[dict(species=155)])
        def snapshot(radius, *, details):
            self.assertEqual((radius, details), (0, False))
            emu.call("md_read_bytes", 0, 0x02000000, object(), 4)
            emu.call("md_read_bytes", 0, 0x02000004, object(), 12)
            return deepcopy(value)
        session._snapshot = snapshot
        return session, calls, value

    def test_exact_actual_reader_calls_clocks_digest_and_restoration(self):
        session, calls, value = self.fixture()
        original = session.emu.call
        with patch("tools.overworld.devtools_snapshot_probe.time.process_time_ns", side_effect=[10, 30, 40, 60]), \
             patch("tools.overworld.devtools_snapshot_probe.time.thread_time_ns", side_effect=[12, 25, 42, 55]), \
             patch("tools.overworld.devtools_snapshot_probe.time.perf_counter_ns", side_effect=[0, 50, 60, 110]):
            result = probe_snapshot(session, {"iterations": 2})
        self.assertIs(session.emu.call, original)
        self.assertEqual(len(calls), 4)
        self.assertEqual(result["intervals"], [dict(cpuNs=20, threadCpuNs=13, wallNs=50,
                                                  readCalls=2, readBytes=16)] * 2)
        self.assertEqual((result["frame"], result["nativeCycle"]), (12, 30))
        self.assertTrue(result["snapshotsEqual"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(len(result["snapshotSha256"]), 64)
        self.assertNotIn("snapshot", result)

    def test_defaults_and_invalid_args(self):
        session, calls, _ = self.fixture()
        self.assertEqual(probe_snapshot(session, {})["iterations"], 128)
        for args in ({"iterations": 0}, {"iterations": 257}, {"iterations": True},
                     {"iterations": 1.0}, {"other": 1}, None):
            before = len(calls)
            with self.assertRaises(ValueError): probe_snapshot(session, args)
            self.assertEqual(len(calls), before)

    def test_different_output_or_clock_advance_fails_and_restores(self):
        for change in ("output", "frame", "cycle"):
            with self.subTest(change=change):
                session, _, value = self.fixture()
                original, read = session.emu.call, session._snapshot
                count = 0
                def snapshot(*args, **kwargs):
                    nonlocal count
                    count += 1
                    if count == 2:
                        if change == "output": value["actors"][0]["species"] = 56
                        if change == "frame": session.completed_frames += 1
                        if change == "cycle": session.rt.EXECUTED_FRAME_COUNT += 1
                    return read(*args, **kwargs)
                session._snapshot = snapshot
                with self.assertRaises(ValueError): probe_snapshot(session, {"iterations": 3})
                self.assertIs(session.emu.call, original)

    def test_mutations_blocked_before_native_call_even_if_reader_catches(self):
        for operation in ("md_write_bytes", "md_run_frame", "md_set_keys", "md_set_reg"):
            session, calls, value = self.fixture()
            original = session.emu.call
            def snapshot(*args, **kwargs):
                try: session.emu.call(operation, 0)
                except ValueError: pass
                return value
            session._snapshot = snapshot
            with self.assertRaisesRegex(ValueError, "forbidden"):
                probe_snapshot(session, {"iterations": 1})
            self.assertEqual(calls, [])
            self.assertIs(session.emu.call, original)

    def test_reader_error_and_bad_clock_restore_wrapper(self):
        session, _, _ = self.fixture()
        original = session.emu.call
        error = RuntimeError("first reader fault")
        with patch.object(session, "_snapshot", side_effect=error):
            with self.assertRaises(RuntimeError) as caught: probe_snapshot(session, {"iterations": 1})
        self.assertIs(caught.exception, error)
        self.assertIs(session.emu.call, original)
        with patch("tools.overworld.devtools_snapshot_probe.time.thread_time_ns", side_effect=[20, 10]):
            with self.assertRaises(ValueError): probe_snapshot(session, {"iterations": 1})
        self.assertIs(session.emu.call, original)


if __name__ == "__main__": main()
