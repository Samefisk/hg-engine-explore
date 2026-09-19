"""The route must wait for checked effect restoration, not only actor IDLE."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.test_devtools_cadence_integration import installed, KIND
from tools.overworld.test_devtools_cadence_measurement import Route
from tools.overworld.test_devtools_crash_measurement import fixture


class CadenceCompletionTests(unittest.TestCase):
    def test_actual_route_end_waits_through_idle_crash_restore(self):
        root = Path(__file__).resolve().parents[2]
        recipe = json.loads((root / "tests/overworld/test-recipes/world.unmounted.long-travel-cadence.json").read_text())
        predicate = recipe["actions"][-1]["args"]["predicate"]
        route = Route(); route.setup_bind()
        evaluator = installed(route)
        for record in route.records:
            evaluator.observe_record(record)
        self.assertFalse(evaluator.failures)
        meter = evaluator.measurements[KIND]
        # Isolate the final wait seam. These fixture counters are not game
        # evidence; the unchanged normal route must still earn every floor.
        evaluator.frames = recipe["budgets"]["minObservedFrames"]
        meter.active_frames = 5428
        meter.tiles = set(range(85)); meter.cells = set(range(3)); meter.maps = {33, 67}
        meter.follower_motions = 1058
        meter.held_tiles = meter.held_cells = meter.held_maps = 1
        meter.handoffs = [{"recoveryTerminal": {}}]
        initial, previous, rows = fixture()

        def same_actor(value):
            actor = deepcopy(route.actor)
            actor.update(deepcopy(value))
            actor["handle"] = deepcopy(route.actor["handle"])
            actor["crashPresentation"]["handle"] = deepcopy(actor["handle"])
            actor["crashPresentation"]["objectPointer"] = actor["engineIdentity"]["pointer"]
            return actor

        previous = same_actor(previous)
        initial["context"] = deepcopy(route.context)
        meter.crash_presentation.observe(initial, previous, None)
        for index, (snapshot, value) in enumerate(rows):
            actor = same_actor(value)
            snapshot["context"] = deepcopy(route.context)
            meter.crash_presentation.observe(snapshot, actor, previous)
            latest = route.snapshot()
            latest.update(snapshot)
            latest["actors"] = [actor]
            evaluator.latest = latest
            meter.latest = deepcopy(latest)
            self.assertEqual(actor["motionPhase"], "IDLE")
            # Native timer10..1 must keep waiting despite the IDLE phase.
            # Only the exact timer0/base-pose observation may finish the run.
            self.assertEqual(evaluator.check(predicate), index == 10)
            previous = actor


if __name__ == "__main__":
    unittest.main()
