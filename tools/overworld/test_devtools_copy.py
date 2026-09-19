"""Closed-session ROM cleanup checks; no emulator or product writes."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from tools.overworld.devtools_copy import remove_private_rom


class PrivateRomCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.directory = self.root / "build/overworld-devtools/session-example"
        self.directory.mkdir(parents=True)
        self.source = self.root / "test.nds"
        self.target = self.directory / "game.nds"
        self.source.write_bytes(b"ROM DATA")
        self.target.write_bytes(self.source.read_bytes())
        for name in ("game.sav", "session.json", "observations.jsonl"):
            (self.directory / name).write_bytes(b"PRESERVE " + name.encode())
        self.identity = {"path": str(self.source), "copy": str(self.target), "size": 8,
                         "sha256": hashlib.sha256(b"ROM DATA").hexdigest()}

    def remove(self, identity=None, directory=None):
        return remove_private_rom(directory or self.directory, identity or self.identity)

    def test_remove_and_repeat_leave_source_saves_and_evidence_unchanged(self):
        preserved = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file() and p != self.target}
        self.assertEqual(self.remove(), {"status": "removed", "bytes": 8, "sha256": self.identity["sha256"]})
        self.assertEqual(self.remove(), {"status": "absent", "bytes": 0, "sha256": self.identity["sha256"]})
        self.assertEqual(preserved, {p: p.read_bytes() for p in preserved})

    def test_rebuilt_or_missing_source_does_not_block_verified_private_copy(self):
        self.source.write_bytes(b"NEW BUILD")
        self.assertEqual(self.remove()["status"], "removed")
        self.target.write_bytes(b"ROM DATA")
        self.source.unlink()
        self.assertEqual(self.remove()["status"], "removed")

    def test_changed_identity_or_bytes_rejected(self):
        for changes in ({"size": 9}, {"sha256": "0" * 64}, {"size": True}, {"path": str(self.target)},
                        {"path": "unknown"}, {"copy": str(self.directory / "game.sav")},
                        {"copy": str(self.directory / "observations.jsonl")}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.remove({**self.identity, **changes})
            self.assertTrue(self.target.exists())
        self.target.write_bytes(b"BAD DATA")
        with self.assertRaisesRegex(ValueError, "hash"):
            self.remove()
        self.assertTrue(self.target.exists())

    def test_symlink_hardlink_and_nonregular_target_rejected(self):
        self.target.unlink()
        self.target.symlink_to(self.source)
        with self.assertRaises((ValueError, OSError)):
            self.remove()
        self.assertTrue(self.target.is_symlink())
        self.target.unlink()
        os.link(self.source, self.target)
        with self.assertRaises(ValueError):
            self.remove()
        self.assertTrue(self.target.exists())
        self.target.unlink()
        self.target.mkdir()
        with self.assertRaises((ValueError, OSError)):
            self.remove()
        self.assertTrue(self.target.is_dir())
        self.target.rmdir()
        os.mkfifo(self.target)
        with self.assertRaises(ValueError):
            self.remove()
        self.assertTrue(self.target.exists())

    def test_wrong_or_symlink_session_directory_rejected(self):
        alias = self.directory.parent / "session-alias"
        alias.symlink_to(self.directory, target_is_directory=True)
        for directory in (alias, self.root, Path("build/overworld-devtools/session-example")):
            with self.subTest(directory=directory), self.assertRaises(ValueError):
                self.remove(directory=directory)
        self.assertTrue(self.target.exists())


if __name__ == "__main__":
    unittest.main()
