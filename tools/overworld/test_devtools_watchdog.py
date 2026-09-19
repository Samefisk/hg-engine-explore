"""Exercise the shared live step path; no ROM behavior claims."""
import unittest

from tools.overworld.devtools_runtime import DevtoolsFailure
from tools.overworld.test_devtools_runtime import TraceAndClockTests


class SharedStepWatchdogTests(unittest.TestCase):
    def test_a_missing_queue_does_not_consume_the_whole_requested_step(self):
        session, _ring = TraceAndClockTests().fixture()
        cycles, released = [], []
        session.cycle = lambda *args: cycles.append(args)
        session.rt.h.set_key_mask = lambda _emu, mask: released.append(mask)
        session.diagnostics = lambda: {"cpu": {"pc": 123}, "frame": 40}
        with self.assertRaises(DevtoolsFailure) as failed:
            # Checked jobs hold input continuously. Manual pulse/poll code
            # identity belongs to test_devtools_input_phase, not this clock fixture.
            session.step(600, ["RIGHT"], release_at_end=False)
        self.assertEqual(len(cycles), 120)
        self.assertEqual(released, [0])
        self.assertEqual(failed.exception.code, "game-frame-timeout")
        self.assertEqual(failed.exception.details["diagnostics"]["cpu"]["pc"], 123)
        self.assertEqual(len(failed.exception.details["cycleIntervals"]), 120)

    def test_real_cycles_keep_cpu_cost_separate_from_game_frames(self):
        session, _ring = TraceAndClockTests().fixture()
        cycles = []
        def cycle(_frames, _mask):
            cycles.append(1)
            if len(cycles) % 2 == 0:
                session.completed_frames += 1
                session.pending_samples.append({"frame": session.completed_frames})
        session.cycle = cycle
        result = session.step(3, [])
        self.assertEqual(result["completedGameFrames"], 3)
        self.assertEqual(len(result["cycleIntervals"]), 6)
        for sample in result["cycleIntervals"]:
            self.assertGreaterEqual(sample["cpuNs"], 0)
            self.assertGreaterEqual(sample["wallNs"], 0)


if __name__ == "__main__":
    unittest.main()
