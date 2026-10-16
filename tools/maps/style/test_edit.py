"""Local re-solve and tile inspection on a synthetic kit.  python3 -B -m unittest tools.maps.style.test_edit"""

from __future__ import annotations

import unittest

import numpy as np

from . import edit, score
from .test_solver import synthetic_kit

G = 32
ROWS = (["TT" * 16] * 4 + ["." * 32] * 6
        + ["." * 8 + "," * 8 + "." * 16] * 10 + ["." * 32] * 12)


def vanilla_grid(kit: dict) -> list[list[int]]:
    return [list(row) for row in kit["chunks"][0]]  # ROWS is its own class layout


def broken_grid(kit: dict) -> list[list[int]]:
    """Vanilla chunk 0 with a run of lone tree-left cells in open ground (24..27, 26)."""
    grid = vanilla_grid(kit)
    for x in range(24, 28):
        grid[26][x] = 2
    return grid


class ResolveTests(unittest.TestCase):
    def test_region_is_repaired_and_everything_else_pinned(self):
        kit = synthetic_kit()
        grid = broken_grid(kit)
        rows = [r if z != 26 else r[:24] + "****" + r[28:] for z, r in enumerate(ROWS)]  # free the spot
        out = edit.resolve_grid(kit, grid, rows, [(22, 24, 8, 6)], seeds=2)
        new = np.array(out["grid"])
        mask = np.ones(new.shape, dtype=bool)
        mask[24:30, 22:30] = False
        self.assertTrue(np.array_equal(new[mask], np.array(grid)[mask]))
        self.assertTrue(out["improved"])
        self.assertLess(out["after"]["badSeams"], out["before"]["badSeams"])
        region = out["regions"][0]
        self.assertTrue(region["accepted"])
        self.assertGreater(region["changedTiles"], 0)
        self.assertLess(edit.local_key(region["after"]), edit.local_key(region["before"]))

    def test_never_worse_on_a_clean_grid(self):
        kit = synthetic_kit()
        grid = vanilla_grid(kit)
        out = edit.resolve_grid(kit, grid, ROWS, [(0, 0, 8, 8), (8, 10, 8, 8)], seeds=2)
        self.assertFalse(out["improved"])
        self.assertEqual(out["grid"], grid)
        self.assertTrue(all(not r["accepted"] and r["changedTiles"] == 0 for r in out["regions"]))

    def test_set_changes_the_intent_inside_the_region(self):
        kit = synthetic_kit()
        grid = vanilla_grid(kit)
        out = edit.resolve_grid(kit, grid, ROWS, [(20, 20, 8, 8)], seeds=2, sets=[(22, 24, "T"), (23, 24, "T")])
        self.assertEqual(out["rows"][24][22:24], "TT")
        self.assertTrue(out["improved"])
        self.assertEqual(out["grid"][24][22:24], [2, 3])
        self.assertEqual(out["after"]["criticalMismatches"], 0)

    def test_unrealizable_set_is_refused(self):
        kit = synthetic_kit()  # has no ledge cells
        grid = vanilla_grid(kit)
        out = edit.resolve_grid(kit, grid, ROWS, [(20, 20, 4, 4)], seeds=1, sets=[(21, 21, "v")])
        self.assertFalse(out["improved"])
        self.assertEqual(out["grid"], grid)

    def test_set_outside_regions_and_bad_regions_are_errors(self):
        with self.assertRaises(edit.EditError):
            edit.apply_sets(ROWS, [(0, 0, "T")], [(10, 10, 4, 4)])
        with self.assertRaises(edit.EditError):
            edit.apply_sets(ROWS, [(10, 10, "Q")], [(10, 10, 4, 4)])
        with self.assertRaises(edit.EditError):
            edit.clip_region((40, 0, 4, 4), G, G)
        self.assertEqual(edit.clip_region((30, -2, 8, 8), G, G), (30, 0, 2, 6))


class InspectTests(unittest.TestCase):
    def test_bad_join_is_described_with_neighbourhood(self):
        kit = synthetic_kit()
        grid = broken_grid(kit)
        cell = edit.describe_cell(kit, grid, ROWS, 24, 26, radius=1,
                                  hotspots=score.hotspots(kit, grid))
        self.assertEqual(cell["cell"]["index"], 2)
        self.assertEqual(cell["realized"], "T")
        self.assertEqual(cell["wanted"], ".")
        self.assertTrue(cell["criticalMismatch"])
        self.assertIn("east", cell["badSides"])
        self.assertEqual(cell["cell"]["vanillaSources"][0], {"land": 0, "x": 0, "z": 0})
        self.assertIsNotNone(cell["hotspot"])
        hood = cell["neighbourhood"]
        self.assertEqual(hood["realized"], ["...", ".TT", "..."])
        self.assertEqual(hood["wanted"][1], "...")
        self.assertEqual(hood["problems"][1][1], "C")

    def test_clean_tile_has_no_problems(self):
        kit = synthetic_kit()
        grid = vanilla_grid(kit)
        cell = edit.describe_cell(kit, grid, ROWS, 12, 15)
        self.assertEqual(cell["badSides"], [])
        self.assertEqual(cell["rigidViolations"], [])
        self.assertFalse(cell["hole"] or cell["voidExposed"] or cell["bareEdge"] or cell["criticalMismatch"])
        self.assertIsNone(cell["hotspot"])
        corner = edit.describe_cell(kit, grid, None, 0, 0)
        self.assertIsNone(corner["seams"]["north"])
        self.assertIsNone(corner["wanted"])

    def test_report_coordinates_round_trip(self):
        report = {"land": 10, "lands": [10, 11, 12, 13], "grid": [[0] * 64 for _ in range(64)]}
        self.assertEqual(edit.grid_position(report, 13, 5, 6), (37, 38))
        self.assertEqual(edit.grid_land(report, 37, 38), (13, 5, 6))
        stale = {"land": 20, "grid": [[0] * 32 for _ in range(64)]}  # unwritten report: lands derived
        self.assertEqual(edit.report_lands(stale), [20, 21])
        self.assertEqual(edit.grid_land(stale, 3, 40), (21, 3, 8))


if __name__ == "__main__":
    unittest.main()
