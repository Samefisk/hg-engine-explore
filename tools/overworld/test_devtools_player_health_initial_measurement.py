"""The registered old-save HP checker rejects wrong copied observations."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.overworld.control import _replay_shared_test
from tools.overworld.devtools_player_health_initial_proof import (
    FAULTS, faulted_rows, measurements,
)


RECIPE = Path(__file__).resolve().parents[2] / \
    "tests/overworld/test-recipes/player-hp.initial-state.json"


class PlayerHealthInitialMeasurementTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "build").mkdir()
        (self.root / "test.nds").write_bytes(b"current test ROM")
        (self.root / "test.sav").write_bytes(b"old save without HP")
        self.rom_sha = hashlib.sha256(b"current test ROM").hexdigest()
        self.overlay_sha = "a" * 64
        (self.root / "build/player-health.debug.json").write_text(json.dumps({
            "formatVersion": 1,
            "overlay": {"id": 161, "sha256": self.overlay_sha},
        }))
        self.test = json.loads(RECIPE.read_text())
        snapshot = {"observationBoundary": "main-task-queue-completion",
                    "fieldAvailable": True, "frame": 12, "nativeCycle": 100}
        hp = {"schemaVersion": 1,
              "identity": {"descriptorVersion": 1, "overlayId": 161,
                           "overlaySha256": self.overlay_sha,
                           "romSha256": self.rom_sha},
              "frame": 12, "nativeCycle": 100, "hp": 100, "savedHp": 100,
              "maxHp": 100, "checkpointSpawn": 23,
              "lastDamage": 0, "acceptedHits": 0,
              "recoveryPending": False, "restFrames": 0,
              "protectionFrames": 0}
        self.rows = [
            {"phase": "setup", "initialSnapshot": snapshot},
            {"phase": "observe", "action": "read-initial-health",
             "command": "player-health.observe",
             "receipt": {"playerHealth": hp}, "snapshot": snapshot},
        ]

    def replay(self, rows):
        return _replay_shared_test(self.test, rows, repo=self.root)

    def test_full_initial_state_and_all_wrong_data_controls(self):
        result = self.replay(self.rows)
        self.assertTrue(result["passed"])
        self.assertEqual(len(measurements(self.rows, result)["measurements"]), 5)
        for fault in FAULTS:
            with self.subTest(fault=fault):
                changed = self.replay(faulted_rows(self.rows, fault))
                self.assertFalse(changed["passed"])
                self.assertTrue(changed["failures"])

    def test_old_save_and_descriptor_are_required(self):
        (self.root / "test.sav").write_bytes(b"PH\x01")
        with self.assertRaisesRegex(ValueError, "already contains"):
            self.replay(self.rows)
        (self.root / "test.sav").write_bytes(b"old save")
        (self.root / "build/player-health.debug.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self.replay(self.rows)


if __name__ == "__main__":
    unittest.main()
