"""Solver and score tests on a synthetic kit.  python3 -B -m unittest tools.maps.style.test_solver"""

from __future__ import annotations

import unittest

from . import layout, score, wfc

G = layout.GRID


def synthetic_kit() -> dict:
    """Open ground, grass, and a 2-wide tree (left half, right half)."""
    cells = [
        {"cls": ".", "collision": False, "count": 50},   # 0 ground
        {"cls": ",", "collision": False, "count": 20},   # 1 grass
        {"cls": "T", "collision": True, "count": 5},     # 2 tree left
        {"cls": "T", "collision": True, "count": 5},     # 3 tree right
    ]
    chunk = []
    for z in range(G):
        row = []
        for x in range(G):
            if z < 4:
                row.append(2 if x % 2 == 0 else 3)        # tree wall rows
            elif 8 <= x < 16 and 10 <= z < 20:
                row.append(1)
            else:
                row.append(0)
        chunk.append(row)
    # A second chunk where trees stand alone in open ground.
    chunk2 = [[0] * G for _ in range(G)]
    for z in range(4, G, 4):
        chunk2[z][4:6] = [2, 3]
        chunk2[z][10:12] = [2, 3]
    return {"cells": cells, "chunks": {0: chunk, 1: chunk2}}


class SolverTests(unittest.TestCase):
    def test_solution_respects_layout_and_vanilla_pairs(self):
        kit = synthetic_kit()
        rows = (["TT" * 16] * 4 + ["." * 32] * 6
                + ["." * 8 + "," * 8 + "." * 16] * 10 + ["." * 32] * 12)
        grid = wfc.solve(kit, rows, seed=3)
        result = score.score(kit, grid, rows)
        self.assertEqual(result["edgeRate"], 1.0)
        self.assertEqual(result["layoutMatch"], 1.0)
        self.assertEqual(score.passes(result), [])
        for row in grid[:4]:  # tree halves always alternate (a chunk edge may cut a tree)
            self.assertTrue(all({a, b} == {2, 3} for a, b in zip(row, row[1:])), row)

    def test_impossible_transition_names_the_tile(self):
        kit = synthetic_kit()
        rows = ["." * 32] * 5 + ["." * 10 + "T" + "." * 21] + ["." * 32] * 26  # 1-wide tree
        with self.assertRaises(wfc.SolveError) as caught:
            wfc.solve(kit, rows, restarts=2, backtrack_budget=200)
        x, z = caught.exception.where
        self.assertLessEqual(abs(x - 10) + abs(z - 5), 1)  # at the 1-wide tree or its neighbour

    def test_relax_lets_solver_choose_tree_edges(self):
        rows = ["." * 32] * 5 + ["." * 10 + "TTT" + "." * 19] + ["." * 32] * 26
        relaxed = layout.relax(rows)
        self.assertEqual(relaxed[5][10:13], "***")
        grid = wfc.solve(synthetic_kit(), relaxed, seed=1)
        self.assertEqual(score.score(synthetic_kit(), grid, relaxed)["edgeRate"], 1.0)

    def test_strict_mode_uses_only_exact_vanilla_pairs(self):
        kit = synthetic_kit()
        model = wfc.learn(kit, strict=True)
        rows = (["TT" * 16] * 4 + ["." * 32] * 6
                + ["." * 8 + "," * 8 + "." * 16] * 10 + ["." * 32] * 12)
        grid = wfc.solve(kit, rows, seed=3, model=model)
        self.assertEqual(score.score(kit, grid, rows, model=model)["pairRate"], 1.0)

    def test_pinned_edge_must_be_compatible(self):
        kit = synthetic_kit()
        rows = ["*" * 32] * 32
        grid = wfc.solve(kit, rows, edges={"west": [2] * 32})  # tree-left cells to the west
        self.assertTrue(all(row[0] == 3 for row in grid))       # so our column 0 is tree-right

    def test_quilting_keeps_routes_and_reports_seams(self):
        from . import quilt
        kit = synthetic_kit()
        rows = (["TT" * 16] * 4 + ["." * 32] * 6
                + ["." * 8 + "," * 8 + "." * 16] * 10 + ["." * 32] * 12)
        grid = quilt.solve(kit, rows, seed=1)
        result = score.score(kit, grid, rows)
        self.assertEqual(result["criticalMismatches"], 0)
        self.assertEqual(score.passes(result), [])

    def test_mismatch_costs_rank_route_changes_above_cosmetics(self):
        from . import quilt
        self.assertLess(quilt.mismatch_cost(".", ","), quilt.mismatch_cost(".", "T"))
        self.assertLess(quilt.mismatch_cost(".", "T"), quilt.mismatch_cost(".", "v"))
        self.assertFalse(quilt.critical(".", ","))
        self.assertTrue(quilt.critical("T", "."))

    def test_walkable_components_counts_sealed_pockets(self):
        kit = synthetic_kit()
        grid = [[0] * G for _ in range(G)]
        for x in range(G):
            grid[16][x] = 2 if x % 2 == 0 else 3
        self.assertEqual(score.walkable_components(kit, grid), 2)

    def test_layout_parse_rejects_bad_input(self):
        with self.assertRaises(layout.LayoutError):
            layout.parse("abc")
        with self.assertRaises(layout.LayoutError):
            layout.parse("\n".join(["Q" * 32] * 32))


if __name__ == "__main__":
    unittest.main()
