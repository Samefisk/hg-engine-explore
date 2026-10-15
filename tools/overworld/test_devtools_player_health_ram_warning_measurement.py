"""Focused active-Ram amber receipt and copied-data controls."""

from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from tools.overworld.control import _replay_shared_test
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_player_health_ram_warning_measurement import (
    ACTIVE_MASK, PlayerHealthRamWarningMeasurement,
)
from tools.overworld.devtools_player_health_ram_warning_proof import (
    FAULTS, contract, faulted_rows,
)
from tools.overworld.devtools_test_contract import validate_test
from tools.overworld.test_devtools_player_health_bar_measurement import bar
from tools.overworld.test_devtools_player_health_ram_rest_measurement import (
    ONIX, OVERLAY, SOURCE, health, rows as ram_rows, snapshot, step_row,
)


RECIPE = Path(__file__).resolve().parents[2] / \
    "tests/overworld/test-recipes/player-hp.ram-warning.json"


def charge_actor(snap, *, active=False, walking=False):
    for actor in snap["actors"]:
        actor["logical"]["y"] = 412
        actor["matchedLayerMask"] = ACTIVE_MASK if active else 1024
        actor["motionKind"] = "WALK" if walking else "NONE"
        actor["motionPhase"] = "MOVING" if walking else "IDLE"
        actor["movementPolicy"] = {"direction": 0 if walking else 255}
    return snap


def rows():
    initial = snapshot(10, 33, onix=False)
    tile = snapshot(11, 33, onix=False)
    spawn = deepcopy(ram_rows()[2])
    spawn["snapshot"] = charge_actor(snapshot(12, 33))
    spawn["receipt"]["snapshot"] = spawn["snapshot"]
    native = spawn["receipt"]["events"][0]["data"]
    raw = bytearray.fromhex(native["preparedPrefixHex"])
    struct.pack_into("<i", raw, 4, 412)
    struct.pack_into("<h", raw, 22, 412)
    struct.pack_into("<h", raw, 26, 412)
    for receipt in (native, native["finalization"]["receipt"]):
        receipt["preparedPrefixHex"] = raw.hex()
        receipt["startup"]["target"] = [585, 412]
        receipt["startup"]["origin"] = [585, 412]
        receipt["position"] = [585, 412]
    native["publicSubject"] = select_current_actor(spawn["snapshot"], ONIX)
    bound = {"phase": "setup", "action": "bind-onix", "command": "bind",
             "snapshot": spawn["snapshot"], "receipt": native["publicSubject"]}
    application_wait = step_row("wait-ram-application", 13, 1, 33)
    for sample in application_wait["samples"]:
        charge_actor(sample)
    application = step_row("wait-ram-application", 14, 3, 33)
    for sample in application["samples"]:
        charge_actor(sample)
    charge_actor(application["samples"][-1], active=True)
    charge_wait = step_row("wait-active-charge", 17, 1, 33)
    for sample in charge_wait["samples"]:
        charge_actor(sample, active=True)
    charge = step_row("wait-active-charge", 18, 3, 33)
    for sample in charge["samples"]:
        charge_actor(sample, active=True)
    charge_actor(charge["samples"][-1], active=True, walking=True)
    current = charge["samples"][-1]
    hp = health(current, 100, 0, 0, 0)
    hp.update(fieldSystem=0x02130000, **bar(100, 44))
    hp["barDraw"]["danger"] = True
    hp["barResources"]["textureKey"] = 201
    return [
        {"phase": "setup", "initialSnapshot": initial},
        {"phase": "setup", "action": "ram-tile", "command": "teleport",
         "snapshot": tile, "receipt": {"preparedOnly": True, "snapshot": tile}},
        spawn, bound, application_wait, application, charge_wait, charge,
        {"phase": "observe", "action": "read-charge-warning",
         "command": "player-health.observe", "snapshot": current,
         "receipt": {"playerHealth": hp}},
    ]


def evaluate(stream):
    meter = PlayerHealthRamWarningMeasurement(SOURCE)
    for row in stream:
        result = meter.observe_record(row)
        if result["failures"]:
            break
    return meter.finish(), meter.result()


class PlayerHealthRamWarningMeasurementTests(unittest.TestCase):
    def test_registered_recipe_and_claims(self):
        recipe = validate_test(json.loads(RECIPE.read_text()))
        self.assertEqual(recipe["budgets"]["minObservedFrames"], 2)
        self.assertEqual(set(contract()), {"live-actor-identity", "engine-boundary",
                                           "natural-input", "control-release"})

    def test_active_charge_warns_before_hit(self):
        finished, result = evaluate(rows())
        self.assertTrue(finished["passed"], finished["failures"])
        self.assertEqual(result["observedFrames"], 8)
        self.assertTrue(result["warningSubmitted"])

    def test_notice_layer_can_coexist_with_current_ram(self):
        stream = rows()
        for row in stream:
            snapshots = row.get("samples", []) + ([row["snapshot"]] if "snapshot" in row else [])
            for snap in snapshots:
                for actor in snap.get("actors", []):
                    actor["matchedLayerMask"] |= 1 << 14
        finished, _ = evaluate(stream)
        self.assertTrue(finished["passed"], finished["failures"])

    def test_copied_bad_receipts_reject(self):
        baseline = rows()
        for fault in FAULTS:
            with self.subTest(fault=fault):
                finished, _ = evaluate(faulted_rows(baseline, fault))
                self.assertFalse(finished["passed"])
                self.assertTrue(finished["failures"])

    def test_registered_replay_and_copied_controls(self):
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
