"""Render-void gate tests (python3 -B -m unittest tools.maps.style.test_coverage).

Synthetic tests always run; the vanilla check needs rom.nds and the
build/map-style kit cache.
"""

from __future__ import annotations

import unittest

import numpy as np

from . import coverage

G = 32
SHOWN = (31 << 16) | (1 << 7)  # opaque, front faces drawn


def vert(x, y, z):
    return [x, y, z, None, None, None, None, None, None, None, None]


def top(y=0.0):
    return {"mat": "g", "verts": [vert(0, y, 16), vert(16, y, 16), vert(16, y, 0), vert(0, y, 0)]}


def south_face(y0, y1, reverse=False):
    vs = [vert(0, y0, 16), vert(16, y0, 16), vert(16, y1, 16), vert(0, y1, 16)]
    return {"mat": "g", "verts": vs[::-1] if reverse else vs}


def cell(*polys, cls="."):
    return {"cls": cls, "collision": cls == "T", "behavior": 0, "corners": [0, 0, 0, 0], "polys": list(polys)}


def kit_of(cells):
    return {"cells": cells, "chunks": {}, "materials": {"g": {"polyAttr": SHOWN}}}


class SyntheticTests(unittest.TestCase):
    def setUp(self):
        # 0 ground, 1 empty wall tile (no polygons), 2 plateau top without a south face,
        # 3 plateau top with its south face, 4 the same face wound backwards (culled)
        self.kit = kit_of([cell(top()), cell(cls="T"), cell(top(32.0), cls="T"),
                           cell(top(32.0), south_face(0.0, 32.0), cls="T"),
                           cell(top(32.0), south_face(0.0, 32.0, reverse=True), cls="T")])

    def test_ground_everywhere_is_clean(self):
        self.assertEqual(coverage.render_void_tiles(self.kit, np.zeros((G, G), int)), [])

    def test_hole_beside_ground_is_flagged(self):
        g = np.zeros((G, G), int)
        g[10, 12] = 1
        found = coverage.render_void(self.kit, g)
        self.assertEqual(found["top"], [(12, 10)])
        self.assertIn((12, 10), found["camera"])

    def test_hole_away_from_ground_and_at_the_edge_is_not(self):
        g = np.full((G, G), 3)  # plateau walls with their faces
        g[16:, :] = 0
        g[5, 5] = 1  # inside the wall region: nothing to stand beside
        g[20, 0] = g[20, 1] = 1  # beside ground, but inside the 2-tile border
        self.assertEqual(coverage.render_void_tiles(self.kit, g), [])

    def test_sealed_pool_is_not_ground(self):
        water = cell(top(), cls="~")
        kit = kit_of(self.kit["cells"] + [water])
        g = np.full((G, G), 3)
        g[20:, :] = 0
        g[8:11, 8:11] = 1
        g[9, 9] = 5  # pool tile inside empty walls, cut off from the land
        self.assertEqual(coverage.render_void_tiles(kit, g), [])
        g[11:20, 9] = 5  # now a channel joins it to the land
        self.assertNotEqual(coverage.render_void_tiles(kit, g), [])

    def test_missing_wall_face_shows_from_the_camera_only(self):
        g = np.zeros((G, G), int)
        for cell_id, expect in ((2, True), (3, False), (4, True)):
            g[10:13, 8:24] = cell_id
            found = coverage.render_void(self.kit, g)
            self.assertEqual(found["top"], [])
            self.assertEqual(bool(found["camera"]), expect, cell_id)
            if expect:  # the gap is seen south of the plateau's edge
                self.assertTrue(all(8 <= x < 24 and 10 <= z <= 14 for x, z in found["camera"]), found["camera"])

    def test_camera_pitch_is_the_field_preset(self):
        from .. import render
        ax = render.camera_preset(0)["angle"][0]
        self.assertAlmostEqual(coverage.PITCH, -render._angle(ax) % (2 * np.pi))


class VanillaRenderVoidTest(unittest.TestCase):
    """Vanilla chunks of the benchmark tilesets show no render void (no false alarms)."""

    def test_benchmark_tilesets(self):
        import json
        from . import kit as K
        if not (K.REPO / "rom.nds").exists():
            self.skipTest("rom.nds not present")
        from .. import world
        from . import lab, seams
        from .cli import _base, _tileset_of_map
        base = _base()
        tilesets = sorted({_tileset_of_map(base, c["map"]) for c in json.loads(lab.BENCH.read_text())["cases"]})
        problems = []
        for tileset in tilesets:
            kit = K.load_or_build_kit(world.RomSource(K.REPO / "rom.nds"), tileset)
            skip = set(seams.for_kit(kit).self_excluded) | coverage.building_lands(base, kit)
            for land, grid in sorted(kit["chunks"].items()):
                if land not in skip and coverage.render_void_tiles(kit, grid):
                    problems.append((tileset, land, coverage.render_void(kit, grid)))
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
