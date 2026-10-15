"""Focused native bar receipt and copied-fault checks."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from tools.overworld.control import _replay_shared_test
from tools.overworld.devtools_player_health_bar_measurement import (
    PlayerHealthBarMeasurement, OBSERVED_FRAMES, STEPS,
)
from tools.overworld.devtools_player_health_bar_proof import FAULTS, contract, faulted_rows
from tools.overworld.devtools_test_contract import validate_test
from tools.overworld.test_devtools_player_health_ram_rest_measurement import (
    OVERLAY, SOURCE, health, rows as ram_rows, snapshot, step_row,
)


RECIPE = Path(__file__).resolve().parents[2] / \
    "tests/overworld/test-recipes/player-hp.bar.json"


def bar(hp, fill):
    return {"barDraw": {"available": True, "receiptVersion": 2,
                        "requestedFill": fill, "drawnFill": fill,
                        "fillWidth": 44, "danger": False,
                        "submittedSprites": 1, "freshHealthFrame": True,
                        "completeSubmission": True,
                        "claim": "native-oam-submission", "hardwareApplied": None},
            "barResources": {"available": True, "bound": True,
                             "fieldOwner": 0x02130000, "fieldMatches": True,
                             "textureKey": hp * 2, "paletteSlot": 0,
                             "paletteSourceDmaReadable": True,
                             "paletteSourceHasColors": True,
                             "paletteVramMatchesSource": True}}


def rows():
    initial = snapshot(10, 33, onix=False)
    ram_tile = snapshot(11, 33, onix=False)
    spawn = deepcopy(ram_rows()[2])
    bound = deepcopy(ram_rows()[3])
    full_hp = health(spawn["snapshot"], 100, 0, 0, 0)
    full_hp.update(fieldSystem=0x02130000, **bar(100, 44))
    ram = snapshot(117, 33)
    injured_hp = health(ram, 67, 33, 1, 0)
    injured_hp.update(fieldSystem=0x02130000, **bar(67, 30))
    return [
        {"phase": "setup", "initialSnapshot": initial},
        {"phase": "setup", "action": "ram-tile", "command": "teleport",
         "snapshot": ram_tile, "receipt": {"preparedOnly": True, "snapshot": ram_tile}},
        spawn,
        bound,
        {"phase": "observe", "action": "before-ram", "command": "player-health.observe",
         "snapshot": spawn["snapshot"], "receipt": {"playerHealth": full_hp}},
        step_row("allow-natural-ram", 13, 105, 33),
        {"phase": "observe", "action": "after-ram", "command": "player-health.observe",
         "snapshot": ram, "receipt": {"playerHealth": injured_hp}},
    ]


def evaluate(stream):
    meter = PlayerHealthBarMeasurement(SOURCE)
    for row in stream:
        progress = meter.observe_record(row)
        if progress["failures"]:
            break
    return meter.finish(), meter.result()


class PlayerHealthBarMeasurementTests(unittest.TestCase):
    def test_exact_registered_recipe(self):
        recipe = validate_test(json.loads(RECIPE.read_text()))
        self.assertEqual(recipe["budgets"]["minObservedFrames"], OBSERVED_FRAMES)
        self.assertEqual(STEPS["allow-natural-ram"], 105)
        self.assertEqual(set(contract()), {"live-actor-identity", "engine-boundary",
                                           "natural-input", "control-release"})

    def test_full_then_real_ram_fill(self):
        finished, result = evaluate(rows())
        self.assertTrue(finished["passed"], finished["failures"])
        self.assertEqual((result["observedFrames"], result["hpAfterRam"],
                          result["fullFill"], result["injuredFill"]),
                         (105, 67, 44, 30))

    def test_copied_bad_receipts_reject(self):
        baseline = rows()
        for fault in FAULTS:
            with self.subTest(fault=fault):
                finished, _ = evaluate(faulted_rows(baseline, fault))
                self.assertFalse(finished["passed"])
                self.assertTrue(finished["failures"])

    def test_missing_game_frame_rejects(self):
        changed = rows()
        changed[5]["samples"][3]["frame"] += 1
        finished, _ = evaluate(changed)
        self.assertFalse(finished["passed"])

    def test_controller_replay_uses_same_meter_and_controls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "build").mkdir()
            (root / "test.nds").write_bytes(b"test-ROM")
            (root / "test.sav").write_bytes(b"old save")
            (root / "build/player-health.debug.json").write_text(json.dumps({
                "formatVersion": 1,
                "overlay": {"id": 161, "sha256": OVERLAY},
            }))
            recipe = json.loads(RECIPE.read_text())
            baseline = rows()
            replay = _replay_shared_test(recipe, baseline, repo=root)
            self.assertTrue(replay["passed"], replay["failures"])
            for fault in FAULTS:
                with self.subTest(fault=fault):
                    failed = _replay_shared_test(recipe, faulted_rows(baseline, fault),
                                                 repo=root)
                    self.assertFalse(failed["passed"])
                    self.assertTrue(failed["failures"])


if __name__ == "__main__":
    unittest.main()
