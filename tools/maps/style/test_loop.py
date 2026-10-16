"""Tests for lab scan / retro (tools/maps/style/loop.py).

  python3 -B -m unittest tools.maps.style.test_loop
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from . import lab, loop

ROM = loop.REPO / "rom.nds"


def _jsonl(path: Path, rows) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


class RetroTest(unittest.TestCase):
    def _retro(self, ledger, defects, runs=(), cuts=""):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "runs").mkdir()
            for run in runs:
                (tmp / "runs" / f"{run['id']}.json").write_text(json.dumps(run))
            (tmp / "PAPERCUTS.md").write_text(cuts)
            with mock.patch.object(lab, "LEDGER", _jsonl(tmp / "l.jsonl", ledger)), \
                    mock.patch.object(lab, "DEFECTS", _jsonl(tmp / "d.jsonl", defects)), \
                    mock.patch.object(lab, "RUNS", tmp / "runs"), \
                    mock.patch.object(loop, "PAPERCUTS", tmp / "PAPERCUTS.md"), \
                    mock.patch.object(lab, "code_hash", return_value="tree"):
                result = loop.retro(datetime(2026, 10, 20, tzinfo=timezone.utc))
        return {i["rubric"]: i for i in result["items"]}

    def test_flags_repeated_rejections_silent_lessons_and_old_defects(self):
        entry = {"run": "r1", "codeHash": "tree", "summary": {"quality": 0.9}}
        items = self._retro(
            [{**entry, "decision": "accepted", "note": "a: ok"},
             {**entry, "run": "r2", "decision": "rejected", "note": "void-cost: worse; lesson: x"},
             {**entry, "run": "r3", "decision": "rejected", "note": "void-cost: worse again"}],
            [{"id": "D1", "map": 1, "x": 0, "z": 0, "note": "user: looks wrong", "status": "open",
              "time": "2026-10-10T00:00:00Z"}])
        self.assertFalse(items["no idea rejected twice"]["pass"])
        self.assertIn("void-cost", items["no idea rejected twice"]["evidence"])
        self.assertFalse(items["rejections carry a lesson"]["pass"])
        self.assertFalse(items["no open defect older than 3 days"]["pass"])
        self.assertFalse(items["most defects found before the user"]["pass"])
        self.assertTrue(items["champion measured on the current tree"]["pass"])
        self.assertTrue(all(i["proposal"] for i in items.values() if not i["pass"]))

    def test_undecided_runs_and_papercuts(self):
        runs = [{"id": "old-idea", "codeHash": "old", "label": "idea", "quick": False},
                {"id": "old-baseline", "codeHash": "old", "label": "baseline", "quick": False},
                {"id": "quick", "codeHash": "old", "label": "idea", "quick": True}]
        items = self._retro([], [], runs, cuts="- 2026 codex feature/map-style-system: build overlay slow\n"
                                               "- 2026 codex main: tools.maps lint crashed on an empty tree\n")
        self.assertIn("old-idea", items["every full bench decided"]["evidence"])
        self.assertNotIn("old-baseline", items["every full bench decided"]["evidence"])
        self.assertIn("1 entries", items["no open map-tool papercuts"]["evidence"])


class ProposalTest(unittest.TestCase):
    def test_blocks_and_centre(self):
        blocks = loop._blocks([(1, 1), (7, 7), (8, 0)])
        self.assertEqual(sorted(blocks), [(0, 0), (1, 0)])
        p = loop._proposal(5, "detected", [(2, 2), (3, 2), (9, 9)], "why")
        self.assertEqual((p["x"], p["z"], p["tiles"], p["area"]), (3, 2, 3, [2, 2, 9, 9]))


@unittest.skipUnless(ROM.exists(), "needs rom.nds")
class ScanTest(unittest.TestCase):
    def test_scan_dry_run_merges_known_defects_and_writes_nothing(self):
        before = lab.DEFECTS.read_bytes()
        result = loop.scan([543], write=False)
        self.assertEqual(lab.DEFECTS.read_bytes(), before)
        (r,) = result["maps"]
        self.assertEqual(r["map"], 543)
        self.assertLessEqual(len(r["proposals"]), loop.PER_MAP)
        open_ids = {d["id"] for d in lab._read_jsonl(lab.DEFECTS) if d["map"] == 543 and d["status"] == "open"}
        self.assertTrue({m["defect"] for m in r["merged"]} <= open_ids)
        self.assertEqual(result["filed"], [])

    def test_scan_write_files_and_closes_scan_defects(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(lab, "DEFECTS", _jsonl(Path(tmp) / "d.jsonl", [
                    {"id": "D1", "map": 541, "x": 2, "z": 2, "note": "scan (detected): gone", "status": "open",
                     "source": "scan", "time": "2026-10-16T00:00:00Z"}])):
            result = loop.scan([541], write=True)
            rows = lab._read_jsonl(lab.DEFECTS)
        self.assertEqual(result["closed"], ["D1"])
        self.assertEqual(rows[0]["status"], "closed")
        filed = [d for d in rows if d["id"] in result["filed"]]
        self.assertTrue(filed and all(d["source"] == "scan" and d["evidence"] for d in filed))


if __name__ == "__main__":
    unittest.main()
