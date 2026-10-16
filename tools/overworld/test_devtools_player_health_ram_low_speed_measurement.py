"""Focused adjacent Ram boundary and copied-data rejection checks."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_player_health_ram_low_speed_measurement import (
    PlayerHealthRamLowSpeedMeasurement, RAM_MASK,
)
from tools.overworld.devtools_player_health_ram_low_speed_proof import (
    FAULTS, contract, faulted_rows,
)
from tools.overworld.devtools_test_contract import validate_test
from tools.overworld.test_devtools_player_health_ram_rest_measurement import (
    SOURCE, health, rows as ram_rows, step_row,
)


RECIPE = Path(__file__).resolve().parents[2] / \
    "tests/overworld/test-recipes/player-hp.ram-low-speed.json"


def rows():
    setup = deepcopy(ram_rows(onix_y=408)[:4])
    setup[1]["receipt"] = {"preparedOnly": True, "snapshot": setup[1]["snapshot"]}
    before = setup[3]["snapshot"]
    wait = step_row("wait-ram-application", 13, 5, 33, onix_y=408)
    for sample in wait["samples"]:
        sample["actors"][0]["matchedLayerMask"] = 1024
    wait["samples"][-1]["actors"][0]["matchedLayerMask"] = RAM_MASK
    neutral = step_row("allow-adjacent-ram", 18, 80, 33, onix_y=408)
    for index, sample in enumerate(neutral["samples"]):
        sample["actors"][0]["matchedLayerMask"] = (
            RAM_MASK if index < 34 else 1024)
    after = neutral["samples"][-1]
    return [
        *setup,
        {"phase": "observe", "action": "before-ram",
         "command": "player-health.observe", "snapshot": before,
         "receipt": {"playerHealth": health(before, 100, 0, 0, 0)}},
        wait, neutral,
        {"phase": "observe", "action": "after-ram",
         "command": "player-health.observe", "snapshot": after,
         "receipt": {"playerHealth": health(after, 100, 0, 0, 0)}},
    ]


def evaluate(stream):
    meter = PlayerHealthRamLowSpeedMeasurement(SOURCE)
    for row in stream:
        progress = meter.observe_record(row)
        if progress["failures"]:
            break
    return meter.finish(), meter.result()


class PlayerHealthRamLowSpeedMeasurementTests(unittest.TestCase):
    def test_recipe_and_contract_are_exact(self):
        recipe = validate_test(json.loads(RECIPE.read_text()))
        self.assertEqual(recipe["measurements"],
                         [{"kind": "player-health-ram-low-speed-v1",
                           "subject": "onix"}])
        self.assertEqual(recipe["budgets"]["minObservedFrames"], 81)
        self.assertEqual(set(contract()), {"live-actor-identity", "engine-boundary",
                                           "natural-input", "control-release"})

    def test_adjacent_active_ram_keeps_saved_and_live_hp(self):
        finished, result = evaluate(rows())
        self.assertTrue(finished["passed"], finished["failures"])
        self.assertEqual((result["observedFrames"], result["neutralFrames"],
                          result["activeFrames"], result["hpAfterWindow"],
                          result["acceptedHitsAfterWindow"]),
                         (85, 80, 34, 100, 0))

    def test_neutral_window_accepts_multiple_native_chunks(self):
        stream = rows()
        whole = stream[6]
        chunks = []
        for start, end in ((0, 15), (15, 80)):
            chunk = deepcopy(whole)
            chunk["samples"] = chunk["samples"][start:end]
            chunk["cycleIntervals"] = chunk["cycleIntervals"][start:end]
            chunk["completedGameFrames"] = end - start
            chunk["observedFieldFrames"] = end - start
            chunk["nativeCycles"] = end - start
            chunks.append(chunk)
        stream[6:7] = chunks
        finished, result = evaluate(stream)
        self.assertTrue(finished["passed"], finished["failures"])
        self.assertEqual(result["neutralFrames"], 80)

    def test_notice_layer_can_coexist_with_current_ram(self):
        stream = rows()
        for row in stream:
            snapshots = row.get("samples", []) + ([row["snapshot"]] if "snapshot" in row else [])
            for snap in snapshots:
                for actor in snap.get("actors", []):
                    actor.setdefault("matchedLayerMask", 0)
                    actor["matchedLayerMask"] |= 1 << 14
        finished, _ = evaluate(stream)
        self.assertTrue(finished["passed"], finished["failures"])

    def test_each_copied_bad_boundary_rejects(self):
        baseline = rows()
        for fault in FAULTS:
            with self.subTest(fault=fault):
                finished, _ = evaluate(faulted_rows(baseline, fault))
                self.assertFalse(finished["passed"])
                self.assertTrue(finished["failures"])

    def test_short_ram_window_rejects(self):
        stream = rows()
        for sample in stream[6]["samples"][33:]:
            sample["actors"][0]["matchedLayerMask"] = 1024
        finished, _ = evaluate(stream)
        self.assertFalse(finished["passed"])


if __name__ == "__main__":
    unittest.main()
