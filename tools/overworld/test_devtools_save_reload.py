"""Private cartridge save/reload controls; no emulator or user save is used."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools.overworld.devtools import Service
from tools.overworld.devtools_evidence_stream import load_observations
from tools.overworld.devtools_runtime import DevtoolsSession
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test


def digest(data):
    return hashlib.sha256(data).hexdigest()


class CartridgeWorker:
    export_bytes = b"game-save-after-menu"
    loaded_override = None
    instances = []

    def __init__(self, root, directory):
        self.directory = directory
        self.save = directory / "game.sav"
        self.rom = directory / "game.nds"
        self.closed = False
        self.frame = 10
        self.calls = []
        self.instances.append(self)

    def snapshot(self):
        return {"frame": self.frame, "nativeCycle": self.frame,
                "fieldAvailable": True, "prepared": False,
                "romSha256": digest(self.rom.read_bytes()),
                "sourceSaveSha256": digest(self.save.read_bytes()),
                "context": {"fieldEpoch": 1, "mapGeneration": 1},
                "player": {"x": 1, "y": 1}, "actors": []}

    def call(self, op, args=None):
        self.calls.append(op)
        if op == "open":
            return {"snapshot": self.snapshot()}
        if op == "cartridge-save.export":
            data = self.export_bytes
            Path(args["path"]).write_bytes(data)
            return {"path": args["path"], "size": len(data), "sha256": digest(data),
                    "frame": self.frame, "nativeCycle": self.frame}
        if op == "cartridge-save.fingerprint":
            data = self.loaded_override or self.save.read_bytes()
            return {"size": len(data), "sha256": digest(data),
                    "frame": self.frame, "nativeCycle": self.frame}
        if op == "record.start":
            self.frame += 1
            return {"snapshot": self.snapshot(), "events": [], "recording": True}
        if op == "observation.prepare":
            return {"ready": True}
        if op == "step":
            samples = []
            for _ in range(args["frames"]):
                self.frame += 1
                samples.append(self.snapshot())
            return {"snapshot": samples[-1], "samples": samples, "events": [],
                    "completedGameFrames": len(samples), "requestedGameFrames": args["frames"],
                    "nativeCycles": len(samples),
                    "cycleIntervals": [{"nativeCycle": item["nativeCycle"], "cpuNs": 5,
                                        "wallNs": 10} for item in samples]}
        if op == "player-health.observe":
            return {"hp": 67, "sourceSaveSha256": digest(self.save.read_bytes())}
        if op == "release":
            return {"released": True}
        raise AssertionError(op)

    def close(self):
        self.closed = True


def reload_recipe():
    budget = {"maxSeconds": 10, "maxFrames": 100, "noProgressFrames": 20}
    return {"schemaVersion": 1, "id": "diagnostic.save-reload", "title": "Save reload",
            "mode": "normal", "fixture": {"rom": "test.nds", "save": "test.sav"},
            "expectationSource": "documentation/overworld-system/player-hp-implementation-plan.md",
            "requirements": [], "subjects": [], "measurements": [],
            "budgets": {**budget, "minObservedFrames": 1}, "setup": [],
            "actions": [
                {"id": "open-menu", "op": "step", "args": {"frames": 1, "keys": ["X"]}, "budget": budget},
                {"id": "confirm-save", "op": "step", "args": {"frames": 1, "keys": ["A"]}, "budget": budget},
                {"id": "reload", "op": "save.reload", "args": {}, "budget": budget},
                {"id": "read-hp", "op": "player-health.observe", "args": {}, "budget": budget},
            ], "assertions": [{"kind": "frame-count", "operator": "gte", "value": 1}]}


class SaveReloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "test.nds").write_bytes(b"rom-input")
        (self.root / "test.sav").write_bytes(b"save-input")
        CartridgeWorker.export_bytes = b"game-save-after-menu"
        CartridgeWorker.loaded_override = None
        CartridgeWorker.instances = []
        self.service = Service(self.root, CartridgeWorker)
        self.addCleanup(self.service._stop)

    def start(self):
        result = self.service.command({"op": "start", "args": {"rom": "test.nds",
                                      "save": "test.sav", "mode": "normal"}})
        self.assertTrue(result["ok"], result)
        return result["session"]

    def test_exported_bytes_reopen_in_new_private_session_with_three_matching_hashes(self):
        old = self.start()
        result = self.service.command({"op": "save.reload", "args": {}})
        self.assertTrue(result["ok"], result)
        boundary = result["result"]["saveReload"]
        new = result["session"]
        self.assertNotEqual(old["id"], new["id"])
        self.assertEqual(boundary["sourceSessionId"], old["id"])
        self.assertEqual(boundary["newSessionId"], new["id"])
        self.assertEqual(boundary["export"]["sha256"], digest(CartridgeWorker.export_bytes))
        self.assertEqual(boundary["loaded"]["sha256"], boundary["export"]["sha256"])
        self.assertEqual(new["identity"]["save"]["sha256"], boundary["export"]["sha256"])
        self.assertEqual(Path(boundary["export"]["path"]).read_bytes(), CartridgeWorker.export_bytes)
        self.assertEqual((self.root / "test.sav").read_bytes(), b"save-input")
        self.assertEqual(json.loads((Path(old["directory"]) / "session.json").read_text())["state"], "stopped")
        self.assertTrue(CartridgeWorker.instances[0].closed)
        self.assertFalse(CartridgeWorker.instances[1].closed)

    def test_runtime_export_uses_owned_new_file_and_current_core_bytes(self):
        directory = self.root / "private-session"
        directory.mkdir()
        session = object.__new__(DevtoolsSession)
        session.directory = directory.resolve()
        session.closed = False
        session.completed_frames = 7
        session.rt = SimpleNamespace(EXECUTED_FRAME_COUNT=9)
        data = b"current-cartridge"
        session.emu = SimpleNamespace(backup=SimpleNamespace(
            read_bytes=lambda: data,
            export_file=lambda path: Path(path).write_bytes(data)))
        target = directory / "export.sav"
        receipt = session.export_cartridge_save(str(target))
        self.assertEqual(receipt, {"path": str(target.resolve()), "size": len(data),
                                   "sha256": digest(data), "frame": 7, "nativeCycle": 9})
        self.assertEqual(session.cartridge_save_fingerprint()["sha256"], receipt["sha256"])
        with self.assertRaises(Exception):
            session.export_cartridge_save(str(target))
        with self.assertRaises(Exception):
            session.export_cartridge_save(str(self.root / "test.sav"))

    def test_unchanged_export_does_not_close_or_reopen_session(self):
        old = self.start()
        CartridgeWorker.export_bytes = b"save-input"
        result = self.service.command({"op": "save.reload", "args": {}})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "save-export-invalid")
        self.assertEqual(result["session"]["id"], old["id"])
        self.assertEqual(len(CartridgeWorker.instances), 1)
        self.assertEqual((self.root / "test.sav").read_bytes(), b"save-input")

    def test_loaded_core_mismatch_stops_new_session_and_keeps_export(self):
        self.start()
        CartridgeWorker.loaded_override = b"wrong-core-save"
        result = self.service.command({"op": "save.reload", "args": {}})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "save-reload-identity")
        self.assertEqual(result["session"]["state"], "stopped")
        self.assertEqual(len(CartridgeWorker.instances), 2)
        self.assertEqual((self.root / "test.sav").read_bytes(), b"save-input")
        old_dir = CartridgeWorker.instances[0].directory
        self.assertEqual(len(list(old_dir.glob("cartridge-reload-*.sav"))), 1)

    def test_checked_contract_requires_input_and_rejects_stale_boundary(self):
        value = validate_test(reload_recipe())
        evaluator = TestEvaluator(value)
        initial = {"frame": 10, "nativeCycle": 10, "fieldAvailable": True,
                   "prepared": False, "romSha256": digest(b"rom-input"),
                   "sourceSaveSha256": digest(b"save-input"),
                   "context": {"fieldEpoch": 1, "mapGeneration": 1},
                   "player": {"x": 1, "y": 1}, "actors": []}
        evaluator.observe(initial, count_frame=False)
        exported = digest(CartridgeWorker.export_bytes)
        new = {**deepcopy(initial), "frame": 11, "sourceSaveSha256": exported}
        boundary = {"state": "loaded", "sourceSessionId": "old", "newSessionId": "new",
                    "sourceFrame": initial["frame"], "sourceSaveSha256": initial["sourceSaveSha256"],
                    "sourceRomSha256": initial["romSha256"], "export": {"size": len(CartridgeWorker.export_bytes),
                    "sha256": exported}, "loaded": {"size": len(CartridgeWorker.export_bytes),
                    "sha256": exported}, "loadedSaveSha256": exported}
        self.assertEqual(evaluator.observe_save_reload({"saveReload": boundary, "snapshot": new})["saveReloads"], 1)
        altered = reload_recipe()
        altered["actions"][0]["args"]["keys"] = []
        with self.assertRaisesRegex(ValueError, "normal menu"):
            validate_test(altered)
        altered = reload_recipe()
        altered["actions"][2]["args"]["path"] = "/tmp/source.sav"
        with self.assertRaises(ValueError):
            validate_test(altered)
        evaluator = TestEvaluator(value)
        evaluator.observe(initial, count_frame=False)
        bad = deepcopy(boundary)
        bad["loaded"]["sha256"] = "0" * 64
        self.assertEqual(evaluator.observe_save_reload({"saveReload": bad, "snapshot": new})["state"], "failed")

    def test_checked_job_retains_reboot_boundary_and_post_load_hp_read(self):
        (self.root / "tools/overworld").mkdir(parents=True)
        (self.root / "tools/overworld/runtime_proof_registry.json").write_text('{"sharedTests": {}}')
        source = patch("tools.overworld.devtools_jobs.source_record",
                       return_value={"content": "host-source"})
        space = patch("tools.overworld.devtools_jobs.shutil.disk_usage",
                      return_value=SimpleNamespace(free=8 * 1024**3))
        source.start(); space.start()
        self.addCleanup(source.stop); self.addCleanup(space.stop)
        value = reload_recipe()
        self.service.tests.save(value["id"], value)
        reply = self.service.command({"op": "test.start", "args": {"name": value["id"]}})
        self.assertTrue(reply["ok"], reply)
        self.service.tests.thread.join(5)
        self.assertFalse(self.service.tests.thread.is_alive())
        done = self.service.tests.status()
        self.assertTrue(done["passed"], done)
        self.assertFalse(done["acceptedProof"])
        manifest = json.loads(Path(done["manifest"]).read_text())
        self.assertEqual(len(manifest["saveReloads"]), 1)
        rows = load_observations(Path(manifest["observationsArtifact"]["path"]))
        reload = next(row for row in rows if row.get("command") == "save.reload")
        post_hp = next(row for row in rows if row.get("command") == "player-health.observe")
        self.assertEqual(reload["receipt"]["saveReload"]["export"]["sha256"],
                         reload["snapshot"]["sourceSaveSha256"])
        self.assertEqual(post_hp["receipt"]["playerHealth"]["hp"], 67)
        self.assertEqual((self.root / "test.sav").read_bytes(), b"save-input")


if __name__ == "__main__":
    unittest.main()
