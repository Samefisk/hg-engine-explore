from types import SimpleNamespace
import unittest

from tools.overworld.devtools_cpu_work import CPUWorkProbe


class CPUWorkTests(unittest.TestCase):
    def fixture(self, maximum=2):
        toggles = []
        row = dict(enabled=True, complete=True, frameSequence=10, total=9,
                   unmapped=2, bins=[[0x02000100, 7]])
        session = SimpleNamespace(prepared=True, completed_frames=40,
            emu=SimpleNamespace(enable_instruction_profile=toggles.append,
                                instruction_profile=lambda: row,
                                memory=SimpleNamespace(register_arm9=SimpleNamespace(lr=0x02001235, r1=5))),
            native_observation=SimpleNamespace(hooks=SimpleNamespace(add=lambda *args: args,
                                                                     remove=lambda token: None)),
            packaged_code=lambda address, size: b"C" * size,
            read=lambda address, size: b"C" * size)
        return CPUWorkProbe(session, maximum), session, row, toggles

    def test_bounded_native_frames_auto_stop_and_detached_compact_result(self):
        probe, session, row, toggles = self.fixture()
        probe.observe_cycle()
        probe._mon_read()
        row["frameSequence"] += 1
        session.completed_frames += 1
        probe.observe_cycle()
        probe.observe_cycle()
        result = probe.result()
        self.assertEqual(toggles, [True, False])
        self.assertEqual(result["total"], 18)
        self.assertEqual(result["topBins"], [[0x02000100, 14]])
        self.assertEqual(result["observedNativeFrames"], 2)
        self.assertTrue(result["closed"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["monDataReaders"], [dict(caller=0x02001234, field=5, calls=1)])
        result["frames"].clear()
        self.assertEqual(len(probe.result()["frames"]), 2)

    def test_gap_and_partial_native_frame_stop_without_a_pass(self):
        for gap in (False, True):
            probe, session, row, toggles = self.fixture()
            probe.observe_cycle()
            row["frameSequence"] += 2 if gap else 1
            row["complete"] = gap
            with self.assertRaisesRegex(ValueError, "sequence|incomplete"):
                probe.observe_cycle()
            self.assertIsNotNone(probe.result()["failure"])
            self.assertEqual(toggles, [True, False])

    def test_requires_prepared_and_valid_bounded_scope(self):
        for maximum in (0, 1201, True):
            with self.assertRaises(ValueError):
                self.fixture(maximum)
        probe, session, _, _ = self.fixture()
        with self.assertRaises(ValueError):
            CPUWorkProbe(session, 2)
        session = SimpleNamespace(prepared=False)
        with self.assertRaises(ValueError):
            CPUWorkProbe(session, 2)
