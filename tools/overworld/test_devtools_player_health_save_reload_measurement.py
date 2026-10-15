"""Host checks for stock Save wait and injured HP cartridge persistence."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld.control import _replay_shared_test
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_player_health_save_reload_measurement import (
    OBSERVED_FRAMES, ORDER, STEPS, PlayerHealthSaveReloadMeasurement,
)
from tools.overworld.devtools_player_health_save_reload_proof import FAULTS, faulted_rows
from tools.overworld.devtools_runtime import DevtoolsSession
from tools.overworld.devtools_test_contract import validate_test
from tools.overworld.test_devtools_player_health_bar_measurement import bar
from tools.overworld.test_devtools_player_health_ram_rest_measurement import (
    ONIX, OVERLAY, SOURCE, health, rows as ram_rows, snapshot, step_row,
)


RECIPE = Path(__file__).resolve().parents[2] / \
    "tests/overworld/test-recipes/player-hp.save-reload.json"
OLD_SAVE = hashlib.sha256(b"old save").hexdigest()
NEW_SAVE = hashlib.sha256(b"written save").hexdigest()


def field(frame, *, onix=True, loaded=False):
    value = snapshot(frame, 33, onix=onix)
    value.update(romSha256=SOURCE["romSha256"],
                 sourceSaveSha256=NEW_SAVE if loaded else OLD_SAVE)
    return value


def step(action, start, count, *, onix=True, loaded=False):
    row = step_row(action, start, count, 33)
    row["samples"] = [field(start + n, onix=onix, loaded=loaded)
                      for n in range(count)]
    return row


def read(action, snap, *, damage=33, hits=1):
    value = health(snap, 67, damage, hits, 0)
    value.update(fieldSystem=0x02130000, **bar(67, 30))
    return {"phase": "observe", "action": action,
            "command": "player-health.observe", "snapshot": snap,
            "receipt": {"playerHealth": value}}


def rows():
    initial, tile, spawned = field(10, onix=False), field(11, onix=False), field(12)
    native = deepcopy(ram_rows()[2])
    native["snapshot"] = spawned
    native["receipt"]["snapshot"] = spawned
    bound = {"phase": "setup", "action": "bind-onix", "command": "bind",
             "snapshot": spawned, "receipt": select_current_actor(spawned, ONIX)}
    stream = [
        {"phase": "setup", "initialSnapshot": initial},
        {"phase": "setup", "action": "ram-tile", "command": "teleport",
         "snapshot": tile, "receipt": {"preparedOnly": True, "snapshot": tile}},
        native, bound,
    ]
    next_frame = 13
    last = spawned
    for action in ORDER:
        if action in STEPS:
            count, _ = STEPS[action]
            row = step(action, next_frame, count)
            stream.append(row)
            last = row["samples"][-1]
            next_frame += count
        elif action in ("before-save", "before-reload", "after-reload"):
            stream.append(read(action, last, damage=0 if action == "after-reload" else 33,
                               hits=0 if action == "after-reload" else 1))
        elif action == "wait-flash":
            new = field(next_frame)
            stream.append({"phase": "observe", "action": action, "command": "save.wait",
                           "snapshot": new, "receipt": {"schemaVersion": 1,
                           "startSaveState": 12, "endSaveState": 13,
                           "observedWriteState12": True, "nativeCycles": 1,
                           "completedGameFrames": 1,
                           "startNativeCycle": last["nativeCycle"], "snapshot": new}})
            last = new
            next_frame += 1
        elif action == "reload":
            loaded = field(10, onix=False, loaded=True)
            boundary = {"state": "loaded", "sourceSessionId": "old",
                        "newSessionId": "new", "sourceFrame": last["frame"],
                        "sourceSaveSha256": OLD_SAVE,
                        "sourceRomSha256": SOURCE["romSha256"],
                        "export": {"size": 12, "sha256": NEW_SAVE},
                        "loaded": {"size": 12, "sha256": NEW_SAVE},
                        "loadedSaveSha256": NEW_SAVE}
            stream.append({"phase": "observe", "action": action, "command": "save.reload",
                           "snapshot": loaded,
                           "receipt": {"saveReload": boundary, "snapshot": loaded,
                                       "recordingRestart": {"frame": 10,
                                                            "nativeCycle": loaded["nativeCycle"],
                                                            "advancedGameFrames": 0,
                                                            "eventCount": 0}}})
            last = loaded
            next_frame = 11
    return stream


class SaveWaitRuntimeTests(unittest.TestCase):
    def test_wait_requires_stock_write_and_stops_after_completion(self):
        session = object.__new__(DevtoolsSession)
        session.completed_frames = 20
        session.rt = type("RT", (), {"EXECUTED_FRAME_COUNT": 120,
                                     "h": type("H", (), {"set_key_mask": lambda *args: None})()})()
        session.emu = object()
        session.read = lambda *args: b""
        session.field_pointer = lambda: 0x02130000
        session.snapshot = lambda diagnostic_details=False: {"frame": session.completed_frames,
            "nativeCycle": session.rt.EXECUTED_FRAME_COUNT}
        states = [12, 12, 12, 13]
        def observe(*args):
            return {"save": {"state": states.pop(0) if len(states) > 1 else states[0]}}
        def cycle(*args):
            session.rt.EXECUTED_FRAME_COUNT += 1
            if session.rt.EXECUTED_FRAME_COUNT == 123:
                session.completed_frames += 1
        session.cycle = cycle
        with patch("tools.overworld.devtools_start_menu_observer.observe_save_app", observe):
            result = session.save_wait(10)
        self.assertEqual((result["nativeCycles"], result["endSaveState"],
                          result["completedGameFrames"]), (3, 13, 1))

    def test_wait_rejects_unrelated_app(self):
        session = object.__new__(DevtoolsSession)
        session.read = lambda *args: b""
        session.field_pointer = lambda: 0x02130000
        with patch("tools.overworld.devtools_start_menu_observer.observe_save_app",
                   return_value={"save": {"state": 7}}):
            with self.assertRaises(Exception):
                session.save_wait(10)


class SaveReloadMeasurementTests(unittest.TestCase):
    def test_exact_recipe_and_frame_floor(self):
        recipe = validate_test(json.loads(RECIPE.read_text()))
        self.assertEqual(recipe["budgets"]["minObservedFrames"], OBSERVED_FRAMES)
        self.assertEqual(OBSERVED_FRAMES, 681)

    def test_meter_and_controller_replay_reject_copied_faults(self):
        baseline = rows()
        meter = PlayerHealthSaveReloadMeasurement(SOURCE)
        for row in baseline:
            meter.observe_record(row)
        self.assertTrue(meter.finish()["passed"], meter.result()["failures"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "build").mkdir()
            (root / "test.nds").write_bytes(b"test-ROM")
            (root / "test.sav").write_bytes(b"old save")
            (root / "build/player-health.debug.json").write_text(json.dumps({
                "formatVersion": 1, "overlay": {"id": 161, "sha256": OVERLAY}}))
            recipe = json.loads(RECIPE.read_text())
            replay = _replay_shared_test(recipe, baseline, repo=root)
            self.assertTrue(replay["passed"], replay["failures"])
            for fault in FAULTS:
                with self.subTest(fault=fault):
                    failed = _replay_shared_test(recipe, faulted_rows(baseline, fault), repo=root)
                    self.assertFalse(failed["passed"])
                    self.assertTrue(failed["failures"])


if __name__ == "__main__":
    unittest.main()
