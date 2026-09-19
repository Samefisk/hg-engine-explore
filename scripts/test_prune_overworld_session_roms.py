import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SPEC = importlib.util.spec_from_file_location(
    "prune", Path(__file__).with_name("prune_overworld_session_roms.py"))
prune = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prune)


class PruneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def session(self, name, content=b"ROM", state="stopped"):
        directory = self.root / ("session-" + name)
        directory.mkdir()
        rom = directory / "game.nds"
        rom.write_bytes(content)
        (directory / "game.sav").write_bytes(b"SAVE")
        (directory / "observations.jsonl").write_bytes(b"EVIDENCE")
        data = {"id": directory.name, "directory": str(directory), "state": state,
                "identity": {"sessionId": directory.name, "rom": {
                    "copy": str(rom), "sha256": hashlib.sha256(content).hexdigest(),
                    "size": len(content)}}}
        (directory / "session.json").write_text(json.dumps(data))
        return directory

    def test_plan_is_read_only_and_apply_keeps_one_per_hash_and_all_evidence(self):
        a, b, c = self.session("a"), self.session("b"), self.session("c", b"OTHER")
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        plan = prune.make_plan(self.root)
        self.assertEqual(len(plan["keepers"]), 2)
        self.assertEqual([r["path"] for r in plan["removals"]], [str(b / "game.nds")])
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        calls = []
        result = prune.apply_plan(plan, self.root / "journal.json", lambda: calls.append(True))
        self.assertEqual(result["removed"], [str(b / "game.nds")])
        self.assertEqual(len(calls), 2)
        for path, content in before.items():
            if path != b / "game.nds":
                self.assertEqual(path.read_bytes(), content)
        self.assertEqual(prune.make_plan(self.root)["removals"], [])

    def test_skip_ready_excluded_unknown_corrupt_and_symlink(self):
        self.session("good")
        self.session("ready", state="ready")
        self.session("_26__tej")
        bad = self.session("bad")
        (bad / "game.nds").write_bytes(b"BAD")
        link = self.session("link")
        (link / "game.nds").unlink()
        (link / "game.nds").symlink_to(self.root / "session-good/game.nds")
        unknown = self.session("unknown")
        (unknown / "session.json").write_text("{}")
        plan = prune.make_plan(self.root)
        self.assertEqual(len(plan["keepers"]), 1)
        self.assertEqual(len(plan["skipped"]), 5)
        self.assertEqual(plan["removals"], [])

    def test_changed_manifest_or_keeper_stops_apply(self):
        a, b = self.session("a"), self.session("b")
        plan = prune.make_plan(self.root)
        (a / "game.nds").write_bytes(b"NEW")
        with self.assertRaises(ValueError):
            prune.apply_plan(plan, self.root / "journal.json", lambda: None)
        self.assertTrue((b / "game.nds").exists())

    def test_live_status_or_unwritable_journal_prevents_removal(self):
        self.session("a")
        b = self.session("b")
        plan = prune.make_plan(self.root)
        def live():
            raise ValueError("live job")
        with self.assertRaises(ValueError):
            prune.apply_plan(plan, self.root / "journal.json", live)
        with self.assertRaises(FileExistsError):
            prune.apply_plan(plan, b / "game.nds", lambda: None)
        self.assertTrue((b / "game.nds").exists())

    def test_second_status_check_and_keeper_recheck_prevent_removal(self):
        a, b = self.session("a"), self.session("b")
        plan = prune.make_plan(self.root)
        calls = []
        def change():
            calls.append(True)
            if len(calls) == 2:
                (a / "game.nds").write_bytes(b"NEW")
        with self.assertRaises(ValueError):
            prune.apply_plan(plan, self.root / "journal.json", change)
        self.assertTrue((b / "game.nds").exists())

    def test_real_status_shapes_fail_closed(self):
        stopped = {"ok": True, "session": {"id": "session-x", "state": "stopped"},
                   "result": {"playing": False, "recording": False}}
        idle = {"ok": True, "result": {"state": "idle", "execution": "shared-devtools", "acceptedProof": False}}
        def check(session, job):
            replies = [SimpleNamespace(returncode=0, stdout=json.dumps(x)) for x in (session, job)]
            with patch.object(prune.subprocess, "run", side_effect=replies):
                return prune.shared_status()
        for state in ("completed", "failed", "canceled"):
            check(stopped, {"ok": True, "result": {"state": state, "phase": "terminal"}})
        check({**stopped, "session": None}, idle)
        for state in ("running", "starting", "canceling", "mystery"):
            with self.assertRaises(ValueError):
                check(stopped, {"ok": True, "result": {"state": state, "phase": "terminal"}})
        with self.assertRaises(ValueError):
            check({**stopped, "session": {"state": "ready"}}, idle)
        with self.assertRaises(ValueError):
            check({**stopped, "result": {"playing": True, "recording": False}}, idle)

    def test_empty_root_and_manifest_pointing_to_save_or_evidence_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "no verified"):
            prune.make_plan(self.root)
        self.session("keeper")
        for index, name in enumerate(("game.sav", "observations.jsonl")):
            directory = self.session(str(index))
            manifest = directory / "session.json"
            data = json.loads(manifest.read_text())
            data["identity"]["rom"]["copy"] = str(directory / name)
            manifest.write_text(json.dumps(data))
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        plan = prune.make_plan(self.root)
        self.assertEqual(len(plan["skipped"]), 2)
        self.assertEqual(plan["removals"], [])
        self.assertEqual(before, {p: p.read_bytes() for p in before})


if __name__ == "__main__":
    unittest.main()
