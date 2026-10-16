"""Tests for `tools.maps events`.  Run: python3 -B -m unittest tools.maps.test_events_edit

Every test uses a fresh temporary override tree; the real data/maps is never touched.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from . import cli, codecs, reach, world

ROM = cli.REPO / "rom.nds"
HAVE_ROM = ROM.exists()
ROUTE29, ROUTE29_BANK = 33, 30
UNUSED_MAP = 8  # shares events bank 0 with every other unused map


def _run(overrides: Path, *argv) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cli.main(["events", *argv, "--overrides", str(overrides)])
    return code, out.getvalue()


@unittest.skipUnless(HAVE_ROM, "needs rom.nds")
class EventsEdit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = world.load_base(world.RomSource(ROM), repo=cli.REPO)
        grid, seen = reach.reachable_by_matrix(cls.base)[cls.base.headers[ROUTE29]["matrixId"]]
        events = cls.base.member("events", ROUTE29_BANK)
        taken = {(item["x"], item["z"]) for kind in ("objects", "bgs", "warps") for item in events[kind]}
        cls.open_tile = cls.blocked_tile = None
        for z in range(395, 412):
            for x in range(600, 640):
                tile = cls.base.tile(ROUTE29, x, z)
                if tile is None or (x, z) in taken:
                    continue
                if cls.open_tile is None and not tile[0] and seen[z * grid.width + x]:
                    cls.open_tile = (x, z)
                if cls.blocked_tile is None and tile[0]:
                    cls.blocked_tile = (x, z)
        assert cls.open_tile and cls.blocked_tile

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = Path(self._tmp.name)
        self.events_file = self.tree / "events" / f"{ROUTE29_BANK:04d}.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _npc(self, tile, *extra):
        return _run(self.tree, "add-npc", "--map", str(ROUTE29), "--x", str(tile[0]), "--z", str(tile[1]),
                    "--sprite", "317", "--script", "7", "--facing", "left", *extra)

    def test_add_npc_on_open_reachable_tile_round_trips(self):
        code, out = self._npc(self.open_tile)
        self.assertEqual(code, 0, out)
        spec = json.loads(self.events_file.read_text())
        self.assertEqual(codecs.decode_events(codecs.encode_events(spec)), spec)
        added = world.apply_overrides(self.base, self.tree).member("events", ROUTE29_BANK)["objects"][-1]
        vanilla_ids = [o["id"] for o in self.base.member("events", ROUTE29_BANK)["objects"]]
        self.assertEqual((added["x"], added["z"], added["y"]), (*self.open_tile, 0))
        self.assertEqual((added["id"], added["spriteId"], added["scriptId"], added["facingDirection"]),
                         (max(vanilla_ids) + 1, 317, 7, 2))
        self.assertIn("whole tree: 0 error(s)", out)

    def test_npc_on_blocked_tile_refused(self):
        code, out = self._npc(self.blocked_tile)
        self.assertEqual(code, 1, out)
        self.assertIn("object-blocked", out)
        self.assertFalse(self.events_file.exists())

    def test_script_past_scr_seq_refused(self):
        code, out = _run(self.tree, "add-npc", "--map", str(ROUTE29), "--x", str(self.open_tile[0]),
                         "--z", str(self.open_tile[1]), "--sprite", "317", "--script", "1999")
        self.assertEqual(code, 1, out)
        self.assertIn("script-ref", out)

    def test_warp_to_missing_anchor_refused(self):
        code, out = _run(self.tree, "add-warp", "--map", str(ROUTE29), "--x", str(self.open_tile[0]),
                         "--z", str(self.open_tile[1]), "--to-map", "134", "--anchor", "99")
        self.assertEqual(code, 1, out)
        self.assertIn("warp-anchor", out)
        self.assertFalse(self.events_file.exists())

    def test_dry_run_writes_nothing(self):
        code, out = self._npc(self.open_tile, "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn('"spriteId": 317', out)
        self.assertEqual(list(self.tree.iterdir()), [])

    def test_move_and_remove(self):
        code, out = _run(self.tree, "move", "--map", str(ROUTE29), "--kind", "object", "--index", "0",
                         "--x", str(self.open_tile[0]), "--z", str(self.open_tile[1]))
        self.assertEqual(code, 0, out)
        objects = json.loads(self.events_file.read_text())["objects"]
        self.assertEqual((objects[0]["x"], objects[0]["z"]), self.open_tile)
        code, out = _run(self.tree, "move", "--map", str(ROUTE29), "--kind", "object", "--index", "0",
                         "--x", str(self.blocked_tile[0]), "--z", str(self.blocked_tile[1]))
        self.assertEqual(code, 1, out)
        code, out = _run(self.tree, "remove", "--map", str(ROUTE29), "--kind", "object", "--index", "0")
        self.assertEqual(code, 0, out)
        after = json.loads(self.events_file.read_text())["objects"]
        self.assertEqual(after, objects[1:])
        # Removing a warp that another map's warp targets would retarget it.
        code, out = _run(self.tree, "remove", "--map", str(ROUTE29), "--kind", "warp", "--index", "0")
        self.assertEqual(code, 1, out)
        self.assertIn("warp-anchor-shift", out)

    def test_shared_bank_refused_and_private_copy(self):
        args = ("add-sign", "--map", str(UNUSED_MAP), "--x", "0", "--z", "0", "--script", "1")
        code, out = _run(self.tree, *args)
        self.assertEqual(code, 1, out)
        self.assertIn("--private", out)
        self.assertEqual(list(self.tree.iterdir()), [])
        code, out = _run(self.tree, *args, "--private", "--force")
        self.assertEqual(code, 0, out)
        new_bank = len(self.base.raw["events"])
        header = json.loads((self.tree / "headers" / f"{UNUSED_MAP:04d}.json").read_text())
        self.assertEqual(header["eventsBank"], new_bank)
        edited = world.apply_overrides(self.base, self.tree)
        self.assertEqual(edited.headers[UNUSED_MAP]["eventsBank"], new_bank)
        self.assertEqual(len(edited.member("events", new_bank)["bgs"]), 1)
        self.assertEqual(edited.raw["events"][0], self.base.raw["events"][0])


if __name__ == "__main__":
    unittest.main()
