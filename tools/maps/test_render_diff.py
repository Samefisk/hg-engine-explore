"""Tests for the before/after map diff.

  python3 -B -m unittest tools.maps.test_render_diff

Synthetic tests always run; ROM-backed ones need rom.nds in the repo root.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from . import nsbmd, render, render_diff

ROM = render.REPO / "rom.nds"
MAP = 543  # Echo Cavern: lands 682/683 in data/maps/


class PureLogicTest(unittest.TestCase):
    def test_tile_layer_diff_maps_chunk_coordinates(self):
        tiles = {"collision": ["." * 32] * 32, "behavior": [" ".join(["00"] * 32)] * 32,
                 "secondary": [" ".join(["00"] * 32)] * 32}
        edited = json.loads(json.dumps(tiles))
        edited["collision"][3] = "." * 5 + "#" + "." * 26
        row = ["00"] * 32
        row[7] = "1a"
        edited["behavior"][4] = " ".join(row)
        out = render_diff.tile_layer_diff(tiles, edited, 1, 2)
        self.assertEqual(out, {(32 + 5, 64 + 3): {"collision"}, (32 + 7, 64 + 4): {"behavior"}})
        self.assertEqual(render_diff.tile_layer_diff(tiles, tiles, 0, 0), {})
        self.assertEqual(len(render_diff.tile_layer_diff(None, tiles, 0, 0)), 32 * 32)

    def test_pixel_tiles_uses_after_surface_then_before(self):
        a = np.zeros((4, 4, 3), np.uint8)
        b = a.copy()
        b[1, 2] = 200  # changed where the after side has ground
        b[3, 0] = 200  # changed where only the before side had ground
        b[0, 0] = 5    # under the threshold
        where_a = np.full((4, 4, 2), np.nan)
        where_b = np.full((4, 4, 2), np.nan)
        where_b[1, 2] = (40.0, 20.0)
        where_a[3, 0] = (100.0, 5.0)
        self.assertEqual(render_diff.pixel_tiles(a, b, where_a, where_b), {(2, 1), (6, 0)})
        self.assertEqual(render_diff.pixel_tiles(a, a, where_a, where_b), set())

    def test_cluster_groups_nearby_tiles_and_caps(self):
        tiles = [(0, 0), (1, 0), (3, 0), (20, 20), (21, 21)] + [(100 + 10 * i, 0) for i in range(8)]
        groups = render_diff.cluster(tiles, gap=2, cap=6)
        self.assertEqual(len(groups), 6)
        self.assertEqual(groups[0], {"center": (1, 0), "size": 3, "bbox": [0, 0, 3, 0]})
        self.assertEqual(groups[1]["size"], 2)
        self.assertIn(groups[1]["center"], [(20, 20), (21, 21)])
        self.assertEqual(render_diff.cluster([]), [])

    def test_void_change(self):
        out = render_diff.void_change({"top": [(1, 1)], "camera": [(2, 2), (1, 1)]},
                                      {"top": [(3, 3)], "camera": [(2, 2)]})
        self.assertEqual(out["before"], {"top": 1, "camera": 2})
        self.assertEqual(out["after"], {"top": 1, "camera": 1})
        self.assertEqual(out["newlyVoid"], [(3, 3)])
        self.assertEqual(out["fixed"], [(1, 1)])

    def test_materialize_directory_and_bad_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "repo" / "data/maps"
            tree.mkdir(parents=True)
            path, _ = render_diff.materialize(str(Path(tmp) / "repo"), Path(tmp), "HEAD")
            self.assertEqual(path, tree.resolve())
            with self.assertRaises(ValueError):
                render_diff.materialize("no-such-ref-xyz", Path(tmp), "HEAD")
            with self.assertRaises(FileNotFoundError):
                render_diff.materialize("snapshot:no-such-snapshot-xyz", Path(tmp), "HEAD")

    def test_snapshot_copies_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "maps"
            (src / "land").mkdir(parents=True)
            (src / "land/x.txt").write_text("1")
            with mock.patch.object(render_diff, "SNAPSHOT_DIR", Path(tmp) / "snaps"):
                dest = render_diff.snapshot("pre", src)
                self.assertEqual((dest / "land/x.txt").read_text(), "1")
                with self.assertRaises(FileExistsError):
                    render_diff.snapshot("pre", src)
                (src / "land/x.txt").write_text("2")
                render_diff.snapshot("pre", src, force=True)
                self.assertEqual((dest / "land/x.txt").read_text(), "2")
                path, label = render_diff.materialize("snapshot:pre", Path(tmp), "HEAD")
                self.assertEqual((path, label), (dest, "snapshot:pre"))
                with self.assertRaises(ValueError):
                    render_diff.snapshot("../x", src)

    def test_resolve_note_reads_last_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = {"land": 682, "lands": [682, 683], "resolves": [
                {"time": "t0", "seamRateBefore": 0.5, "seamRateAfter": 0.6, "regions": []},
                {"time": "t1", "seamRateBefore": 0.9, "seamRateAfter": 0.95,
                 "regions": [{"region": [1, 2, 3, 4], "accepted": True, "changedTiles": [[1, 2], [2, 2]]}]}]}
            (Path(tmp) / "report-0682.json").write_text(json.dumps(report))
            with mock.patch.object(render_diff, "REPORT_DIR", Path(tmp)):
                note = render_diff.resolve_note({683})
                self.assertIsNone(render_diff.resolve_note({5}))
        self.assertEqual((note["resolves"], note["time"], note["seamRateDelta"]), (2, "t1", 0.05))
        self.assertEqual(note["regions"], [{"region": [1, 2, 3, 4], "accepted": True, "changedTiles": 2}])


@unittest.skipUnless(ROM.exists(), "needs rom.nds")
class RomDiffTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.base = root / "base"
        shutil.copytree(render.REPO / "data/maps", cls.base)
        cls.edited = root / "edited"
        shutil.copytree(cls.base, cls.edited)
        land = cls.edited / "land/0682"
        spec = json.loads((land / "land.json").read_text())
        row = list(spec["tiles"]["collision"][10])
        row[12] = "#" if row[12] == "." else "."
        spec["tiles"]["collision"][10] = "".join(row)
        (land / "land.json").write_text(json.dumps(spec))
        model = nsbmd.parse((land / "model.nsbmd").read_bytes())
        shapes = model["models"][0]["shapes"]
        k = min(range(len(shapes)), key=lambda i: len(shapes[i]["dl"]))
        shapes[k]["dl"] = [[0]] * 4  # drop one small shape: a local geometry change
        (land / "model.nsbmd").write_bytes(nsbmd.write(model))
        cls.before = render.MapScene(MAP, cls.base)
        cls.after = render.MapScene(MAP, cls.edited)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_changed_tile_and_model_are_reported(self):
        out = render_diff.diff(self.before, self.after, ppt=4, with_voids=False)
        self.assertEqual(out["chunks"], [{"chunk": [0, 0], "land": [682, 682], "changed": ["model", "tiles"]}])
        why = {(t["x"], t["z"]): t["why"] for t in out["changedTiles"]}
        self.assertIn("collision", why[(12, 10)])
        pixel = [t for t, w in why.items() if any(r.startswith("pixels") for r in w)]
        self.assertTrue(pixel, "the dropped shape changes rendered pixels")
        self.assertTrue(all(x < 32 and z < 32 for x, z in pixel), "only chunk (0, 0) changed")
        self.assertLessEqual(len(out["regions"]), render_diff.MAX_VIEWS)
        self.assertTrue(any(r["bbox"][0] <= 12 <= r["bbox"][2] and r["bbox"][1] <= 10 <= r["bbox"][3]
                            for r in out["regions"]))

    def test_same_trees_give_no_changes(self):
        out = render_diff.diff(self.before, render.MapScene(MAP, self.base), ppt=4)
        self.assertEqual((out["chunks"], out["changedTiles"], out["regions"]), ([], [], []))
        self.assertEqual(out["voids"]["before"], out["voids"]["after"])
        self.assertEqual((out["voids"]["newlyVoid"], out["voids"]["fixed"]), ([], []))

    def test_cli_writes_image_and_summary(self):
        with tempfile.TemporaryDirectory() as out_dir:
            with contextlib.redirect_stdout(io.StringIO()):
                render_diff.main(["--map", str(MAP), "--before", str(self.base), "--after", str(self.edited),
                                  "--out", out_dir, "--views", "--no-voids", "--ppt", "4"])
            summary = json.loads((Path(out_dir) / f"summary-{MAP}.json").read_text())
            self.assertGreater(summary["changedTileCount"], 0)
            for name in (f"diff-{MAP}.png", f"views-{MAP}.png"):
                self.assertTrue((Path(out_dir) / name).stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
