"""Tests for the cell kit (python3 -B -m unittest tools.maps.style.test_kit).

Synthetic tests always run; the vanilla fidelity gate needs the repository
rom.nds and uses the build/map-style kit cache.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from .. import codecs, nsbmd
from . import kit as K

ROM = K.REPO / "rom.nds"


def vert(x, z, s, t, y=16.0):
    return [x, y, z, s, t, 0.0, 1023 / 1024, 0.0, None, None, None]


def ground_quad(x0, z0, x1, z1, y=16.0):
    # vanilla upward winding: (x0,z1) (x1,z1) (x1,z0) (x0,z0); 1 texel per unit
    return [vert(x0, z1, x0, z1, y), vert(x1, z1, x1, z1, y), vert(x1, z0, x1, z0, y), vert(x0, z0, x0, z0, y)]


def synthetic_kit(cells):
    mat = nsbmd.make_material("m", "t", "p", 16, 16)  # one texture repeat per tile
    return {"tileset": 0, "areas": [], "materials": {"m": mat}, "cells": cells, "chunks": {},
            "materialOrder": ["m"], "periods": {"m": (16, 16)}, "skipped": {}}


class SyntheticTests(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(K.classify(0x02, False), ",")
        self.assertEqual(K.classify(0x15, False), "~")
        self.assertEqual(K.classify(0x3B, True), "v")
        self.assertEqual(K.classify(0x00, True), "T")
        self.assertEqual(K.classify(0x00, False), ".")
        self.assertEqual(K.classify(0x15, True), "?")

    def test_flat_ground_is_clipped_per_tile_with_interpolated_uv(self):
        quad = ground_quad(-256, -256, -232, -232)  # 1.5 x 1.5 tiles
        cells = K.slice_polys([("m", quad)])
        self.assertEqual(sorted(cells), [(0, 0), (0, 1), (1, 0), (1, 1)])
        area = sum(abs(K._area2(vs)) / 2 for pieces in cells.values() for _, vs in pieces)
        self.assertAlmostEqual(area, 24 * 24)
        for pieces in cells.values():
            for _, vs in pieces:
                for v in vs:
                    self.assertAlmostEqual(v[3], v[0])  # s follows x exactly
                    self.assertAlmostEqual(v[4], v[2])

    def test_non_flat_polygon_goes_to_centroid_cell_whole(self):
        wall = [vert(-256, -256, 0, 0), vert(-200, -256, 0, 0, y=40.0), vert(-200, -250, 0, 0, y=40.0)]
        cells = K.slice_polys([("m", wall)])
        self.assertEqual(list(cells), [(2, 0)])
        self.assertEqual(len(cells[(2, 0)][0][1]), 3)

    def test_pieces_recombine_into_one_quad(self):
        pieces = [vs for p in K.slice_polys([("m", ground_quad(-64, -64, 0, 0))]).values() for _, vs in p]
        self.assertEqual(len(pieces), 16)
        out = K._material_polys(pieces, (32, 32))
        self.assertEqual(len(out), 1)
        xs = sorted({v["pos"][0] for v in out[0]})
        self.assertEqual(xs, [-64, 0])

    def test_compose_validates_and_returns_layers(self):
        ground = {"sig": "g", "cls": ".", "behavior": 0, "collision": False, "secondary": 0,
                  "corners": [16.0] * 4, "count": 1,
                  "polys": [{"mat": "m", "verts": [vert(0, 16, 0, 16), vert(16, 16, 16, 16),
                                                    vert(16, 0, 16, 0), vert(0, 0, 0, 0)]}]}
        tree = dict(ground, sig="t", cls="T", collision=True, behavior=0x01)
        kit = synthetic_kit([ground, tree])
        grid = [[1 if (x + z) % 7 == 0 else 0 for x in range(32)] for z in range(32)]
        data, tiles, corners = K.compose(kit, grid, "synthetic")
        errors, _ = nsbmd.validate(data)
        self.assertEqual(errors, [])
        self.assertLessEqual(len(data), codecs.MODEL_MAX_BYTES)
        codecs.encode_tiles(tiles)
        self.assertEqual(tiles["collision"][0][0], "#")
        self.assertEqual(len(corners), 32)
        self.assertEqual(corners[5][5], [16.0] * 4)
        # 1024 equal ground tiles (minus trees) merge to far fewer polygons
        info = nsbmd.parse(data)["models"][0]["info"]
        self.assertLess(info["numPolygon"], 1024)

    def test_compose_reserves_area_animation_slots(self):
        # The area texture animation binds by material index: its materials must come
        # first, in order, even when the chunk does not use them.
        ground = {"sig": "g", "cls": ".", "behavior": 0, "collision": False, "secondary": 0,
                  "corners": [16.0] * 4, "count": 1,
                  "polys": [{"mat": "m", "verts": [vert(0, 16, 0, 16), vert(16, 16, 16, 16),
                                                    vert(16, 0, 16, 0), vert(0, 0, 0, 0)]}]}
        water = dict(ground, sig="w", polys=[dict(ground["polys"][0], mat="river")])
        kit = synthetic_kit([ground, water])
        kit["materials"]["river"] = dict(kit["materials"]["m"], name="river")
        kit["materialOrder"] = ["m", "river"]
        kit["periods"]["river"] = (16, 16)
        grid = [[1 if z == 3 else 0 for x in range(32)] for z in range(32)]
        data, _, _ = K.compose(kit, grid, "synthetic", anim_materials=["pond_on", "river"])
        self.assertEqual(nsbmd.validate(data)[0], [])
        names = [m["name"] for m in nsbmd.parse(data)["models"][0]["materials"]]
        self.assertEqual(names, ["pond_on", "river", "m", "river~2"])
        model = nsbmd.parse(data)["models"][0]
        textured = {i for t in model["textures"] for i in t["materials"]}
        self.assertFalse(textured & {0, 1})  # animation slots stay untextured

    def test_bdhc_corners_flat_plate(self):
        bdhc = {"points": [[-256 * 4096, -256 * 4096], [256 * 4096, 256 * 4096]],
                "normals": [[0, 4096, 0]], "constants": [-24 * 4096], "plates": [[0, 1, 0, 0]],
                "strips": [], "access": []}
        corners = K.tile_corners(bdhc)
        self.assertEqual(corners[3][7], [24.0] * 4)


@unittest.skipUnless(ROM.exists(), "needs the repository rom.nds")
class VanillaFidelityTests(unittest.TestCase):
    """compose(kit, kit['chunks'][land]) must reproduce vanilla chunks (style-system.md)."""

    @classmethod
    def setUpClass(cls):
        from .. import world
        cls.source = world.RomSource(ROM)

    def check_tileset(self, tileset, sample):
        kit = K.load_or_build_kit(self.source, tileset)
        lands = sorted(kit["chunks"])
        lands = lands[:: max(1, len(lands) // sample)][:sample]
        for row in K.fidelity(kit, self.source, lands):
            with self.subTest(land=row["land"]):
                self.assertNotIn("error", row)
                self.assertTrue(row["tilesEqual"])
                self.assertTrue(row["match"], row)
                self.assertLessEqual(row["bytes"], codecs.MODEL_MAX_BYTES)

    def test_route29_tileset(self):
        self.check_tileset(2, 6)  # map 33 (R29) uses area 2 -> mapTileset 2

    def test_indoor_tileset(self):
        self.check_tileset(42, 4)  # areaType 0


if __name__ == "__main__":
    unittest.main()
