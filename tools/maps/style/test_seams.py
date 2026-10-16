"""Join-rule tests (python3 -B -m unittest tools.maps.style.test_seams).

Synthetic tests always run; the vanilla judge check needs rom.nds and the
build/map-style kit cache.
"""

from __future__ import annotations

import unittest

import numpy as np

from . import seams

G = 32


def vert(x, z, y=0.0, s=None, t=None):
    return [x, y, z, s, t, None, None, None, None, None, None]


def quad(x0, z0, x1, z1, mat="g", y=0.0, uv=True):
    def v(x, z):
        return vert(x, z, y, x if uv else None, z if uv else None)
    return {"mat": mat, "verts": [v(x0, z1), v(x1, z1), v(x1, z0), v(x0, z0)]}


def cell(*polys, cls="."):
    return {"cls": cls, "collision": cls == "T", "corners": [0, 0, 0, 0], "polys": list(polys), "count": 1}


def kit_of(cells, chunks):
    return {"cells": cells, "chunks": chunks, "periods": {"g": (16, 16), "r": (16, 16)}}


class ProfileTests(unittest.TestCase):
    def test_continuing_ground_joins_and_different_height_does_not(self):
        flat, high = cell(quad(0, 0, 16, 16)), cell(quad(0, 0, 16, 16, y=8.0))
        e = seams.profile(flat, "east", {"g": (16, 16)})
        w = seams.profile(flat, "west", {"g": (16, 16)})
        self.assertEqual(e, w)  # u = 16 on the east edge is u = 0 modulo the period
        self.assertNotEqual(e, seams.profile(high, "west", {"g": (16, 16)}))

    def test_overhang_footprint_and_cover(self):
        tree = cell({"mat": "g", "verts": [vert(-4, 20, 8), vert(20, 20, 8), vert(20, -4, 2), vert(-4, -4, 2)]})
        self.assertEqual(seams.footprint(tree), {(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0),
                                                 (-1, 1), (0, 1), (1, 1)})
        ground = cell(quad(0, 0, 32, 16))  # wider than its tile: covers its east neighbour's centre
        self.assertEqual(seams.covers(ground), {(0, 0), (1, 0)})


class SeamsTests(unittest.TestCase):
    def setUp(self):
        # 0 ground, 1 road, 2 tree owning a canopy over its east neighbour, 3 canopy receiver
        self.cells = [cell(quad(0, 0, 16, 16)), cell(quad(0, 0, 16, 16, mat="r")),
                      cell(quad(0, 0, 16, 16), {"mat": "g", "verts": [vert(4, 12, 9), vert(28, 12, 9),
                                                                         vert(28, 4, 9), vert(4, 4, 9)]}, cls="T"),
                      cell(quad(0, 0, 16, 16))]
        chunk = [[0] * G for _ in range(G)]
        for z in range(0, G, 4):
            chunk[z][10], chunk[z][11] = 2, 3
        chunk[20][5] = 1  # one road tile: road|ground joins exist only in this orientation
        self.kit = kit_of(self.cells, {0: chunk})
        self.s = seams.Seams(self.kit)

    def test_vanilla_is_clean(self):
        g = np.array(self.kit["chunks"][0])
        self.assertEqual(self.s.rigid_violations(g), [])
        self.assertEqual(self.s.holes(g), [])
        self.assertEqual(self.s.profile_seams(g)[0], 0)

    def test_cut_overhang_is_a_rigid_violation(self):
        g = np.zeros((G, G), dtype=np.int64)
        g[3, 3] = 2  # tree with ground (0) east of it instead of its receiver (3)
        self.assertEqual(self.s.rigid_violations(g), [(3, 3, 1, 0)])

    def test_unseen_material_join_is_a_seam(self):
        g = np.zeros((G, G), dtype=np.int64)
        g[5, 5], g[5, 6] = 1, 1  # road beside road: road's east never met road's west (u continues: equal)
        self.assertEqual(self.s.profile_seams(g)[0], 0)
        g = np.zeros((G, G), dtype=np.int64)
        g[5, 5] = 1
        self.assertEqual(self.s.profile_seams(g)[0], 0)  # road|ground and ground|road seen in vanilla
        self.assertTrue(self.s.pair_h(0, 0))


class VanillaJudgeTest(unittest.TestCase):
    """Every vanilla chunk scores perfectly against its own kit (no false alarms)."""

    def test_benchmark_tilesets(self):
        from . import kit as K
        if not (K.REPO / "rom.nds").exists():
            self.skipTest("rom.nds not present")
        from . import lab
        problems = lab.judge_check()
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
