"""Map status checks.  python3 -B -m unittest tools.maps.test_status"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from . import status
from .cli import REPO

GRID = [[0] * 64 for _ in range(32)]  # 2x1 chunks: lands 700, 701


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Tree:
    """Temp override tree + report dir with two generated lands."""

    def __init__(self, tmp: Path, models=(b"a", b"b"), stored=(b"a", b"b"), layout=True, written=True):
        self.overrides, self.reports = tmp / "maps", tmp / "reports"
        self.reports.mkdir()
        for land, data in zip((700, 701), models):
            if data is not None:
                (self.overrides / "land" / f"{land:04d}").mkdir(parents=True)
                (self.overrides / "land" / f"{land:04d}" / "model.nsbmd").write_bytes(data)
        (self.overrides / "layouts").mkdir(parents=True, exist_ok=True)
        (self.overrides / "layouts" / "560-test.txt").write_text("." * 32 + "\n")
        report = {"map": 33, "tileset": 2, "land": 700, "grid": GRID, "relax": 1, "seedsTried": 4,
                  "written": ["x"] if written else False, "lands": [700, 701]}
        if stored is not None:
            report["modelHashes"] = {"700": sha(stored[0]), "701": sha(stored[1])}
        if layout:
            report["layout"] = ["." * 64] * 32
        self.path = self.reports / "report-0700.json"
        self.path.write_text(json.dumps(report))

    def check(self, composed=(b"a", b"b"), only=None):
        calls = []

        def recompose(report):
            calls.append(report["land"])
            return {"700": sha(composed[0]), "701": sha(composed[1])}
        entries, found = status.check_reports(self.reports, self.overrides, recompose, {700: [560], 701: [560]}, only)
        return entries, {f["name"]: f for f in found}, calls


class ReportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_matching_lands_need_nothing_and_skip_the_recompose(self):
        entries, found, calls = Tree(self.tmp).check()
        self.assertEqual(found, {})
        self.assertEqual(calls, [])
        self.assertEqual(entries[0]["state"], "ok")

    def test_stale_hashes_with_the_grid_on_disk_point_at_refresh(self):
        tree = Tree(self.tmp, stored=(b"old", b"b"))
        _, found, _ = tree.check()
        self.assertEqual(list(found), ["report-0700-hashes"])
        self.assertIn("[700]", found["report-0700-hashes"]["stale"])
        self.assertEqual(found["report-0700-hashes"]["fix"], f"{status.STATUS} --refresh-hashes")
        recompose = lambda r: {"700": sha(b"a"), "701": sha(b"b")}  # noqa: E731
        self.assertEqual(status.refresh_hashes(tree.reports, tree.overrides, recompose), ["report-0700.json"])
        self.assertEqual(tree.check()[1], {})

    def test_lands_changed_since_point_at_generate(self):
        tree = Tree(self.tmp, models=(b"hand-edited", b"b"))
        _, found, _ = tree.check()
        self.assertEqual(list(found), ["report-0700-lands"])
        fix = found["report-0700-lands"]["fix"]
        self.assertIn("generate --layout", fix)
        self.assertIn("560-test.txt --map 33 --land 700 --relax 1 --seeds 4", fix)
        self.assertIn(status.SHOWCASE_WRITE, fix)
        # refresh must not paper over a real mismatch
        recompose = lambda r: {"700": sha(b"a"), "701": sha(b"b")}  # noqa: E731
        self.assertEqual(status.refresh_hashes(tree.reports, tree.overrides, recompose), [])

    def test_missing_land_file_is_a_mismatch(self):
        _, found, _ = Tree(self.tmp, models=(b"a", None)).check()
        self.assertIn("missing: [701]", found["report-0700-lands"]["stale"])

    def test_old_report_without_hashes_compares_the_recomposed_grid(self):
        tree = Tree(self.tmp, stored=None)
        _, found, calls = tree.check()
        self.assertEqual((found, calls), ({}, [700]))
        self.assertIn("report-0700-lands", tree.check(composed=(b"x", b"b"))[1])

    def test_missing_layout_is_flagged(self):
        _, found, _ = Tree(self.tmp, layout=False).check()
        self.assertEqual(list(found), ["report-0700-layout"])

    def test_unwritten_report_is_informational(self):
        entries, found, _ = Tree(self.tmp, models=(b"z", b"z"), written=False).check()
        self.assertEqual((found, entries[0]["state"]), ({}, "never-written"))

    def test_map_filter(self):
        tree = Tree(self.tmp, models=(b"z", b"z"))
        self.assertEqual(tree.check(only={5})[0], [])
        self.assertEqual(len(tree.check(only={701})[0]), 1)


class RomFreshnessTests(unittest.TestCase):
    def test_rom_age_against_newest_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            overrides, rom = root / "maps", root / "test.nds"
            (overrides / "land").mkdir(parents=True)
            old, new = overrides / "events.json", overrides / "land" / "land.json"
            old.write_text("{}")
            new.write_text("{}")
            os.utime(old, (1000, 1000))
            os.utime(new, (3000, 3000))
            entry, found = status.check_rom(rom, overrides)
            self.assertEqual([f["name"] for f in found], ["rom-missing"])
            rom.write_bytes(b"")
            os.utime(rom, (2000, 2000))
            entry, found = status.check_rom(rom, overrides)
            self.assertEqual([f["name"] for f in found], ["rom-stale"])
            self.assertEqual(entry["newestOverride"], "land/land.json")
            self.assertIn("hg-engine-delta-build", found[0]["fix"])
            os.utime(rom, (4000, 4000))
            entry, found = status.check_rom(rom, overrides)
            self.assertEqual((found, entry["fresh"]), ([], True))


@unittest.skipUnless((REPO / "rom.nds").exists(), "needs rom.nds")
class RealTreeTests(unittest.TestCase):
    def test_json_shape(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = status.main(["--json"])
        result = json.loads(out.getvalue())
        self.assertEqual(code, 0 if result["ok"] else 1)
        self.assertEqual(set(result["checks"]), {"reports", "showcase", "lint", "rom", "lab"})
        for f in result["findings"]:
            self.assertEqual(set(f), {"name", "stale", "fix"})
            self.assertTrue(f["fix"])
        self.assertTrue(all({"report", "lands", "state"} <= set(r) for r in result["checks"]["reports"]))
        self.assertIsInstance(result["checks"]["lint"]["errors"], int)
        self.assertIn("codeMatches", result["checks"]["lab"])
        self.assertLess(result["seconds"], 60)


if __name__ == "__main__":
    unittest.main()
