"""Tests for tools.maps.style.bdhc_gen.  Run: python3 -B -m unittest tools.maps.style.test_bdhc_gen"""

import bisect
import contextlib
import io
import unittest
from pathlib import Path

from tools.maps import codecs
from tools.maps.style import bdhc_gen as B

ROM = Path(__file__).resolve().parents[3] / "rom.nds"


def flat_grid(height=0.0):
    return [[[height] * 4 for _ in range(32)] for _ in range(32)]


class FxMath(unittest.TestCase):
    def test_mul_rounds_half_up(self):
        self.assertEqual(B.fx_mul(4096, 4096), 4096)
        self.assertEqual(B.fx_mul(1, 2048), 1)        # 0.5 LSB rounds up
        self.assertEqual(B.fx_mul(-1, 2048), 0)       # arithmetic shift of -2048 + 2048
        self.assertEqual(B.fx_mul(2896, 1048576), 741376)

    def test_div_rounds_and_truncates_like_the_divider(self):
        self.assertEqual(B.fx_div(4096, 4096), 4096)
        self.assertEqual(B.fx_div(-8192, 4096), -8192)
        self.assertEqual(B.fx_div(1, 3), 1365)         # 1/4096 / (3/4096) = 0.3333
        self.assertEqual(B.fx_div(-1, 3), -1365)
        self.assertEqual(B.fx_div(5, 0), (-1 + (1 << 19)) >> 20)

    def test_find_strip_is_bisect_right_clamped(self):
        for n in range(1, 40):
            scans = [i * 10 for i in range(n)]
            for z in range(-15, n * 10 + 15):
                self.assertEqual(B.find_strip(scans, z), min(bisect.bisect_right(scans, z), n - 1))
        self.assertIsNone(B.find_strip([], 0))


class Query(unittest.TestCase):
    def spec(self):
        # Plate 0: flat at y=8 over x,z in [-16, 16].  Plate 1: bridge at y=24 over x in [-16, 0].
        return {"points": [[B.to_fx(-16), B.to_fx(-16)], [B.to_fx(16), B.to_fx(16)], [B.to_fx(0), B.to_fx(16)]],
                "normals": [[0, 4096, 0]], "constants": [B.to_fx(-8), B.to_fx(-24)],
                "plates": [[0, 1, 0, 0], [0, 2, 0, 1]],
                "strips": [[B.to_fx(16), 2, 0]], "access": [0, 1]}

    def test_heights_and_modes(self):
        spec = self.spec()
        self.assertEqual(B.height_at(spec, 8, 0), 8.0)
        self.assertEqual(B.height_at(spec, -8, 0), 8.0)                 # nearest to 0
        self.assertEqual(B.height_at(spec, -8, 0, current_y=20), 24.0)  # nearest to 20
        self.assertEqual(B.height_at(spec, -8, 0, mode=B.HIGHEST), 24.0)
        self.assertEqual(B.height_at(spec, -8, 0, current_y=30, mode=B.LOWEST), 8.0)
        self.assertIsNone(B.height_at(spec, 20, 0))
        self.assertEqual(B.height_at(spec, 16, 16), 8.0)                # bounds are closed

    def test_tile_center_mapping(self):
        self.assertEqual(B.tile_center(0, 0), (-248.0, -248.0))
        self.assertEqual(B.tile_center(31, 31), (248.0, 248.0))


class Generate(unittest.TestCase):
    def test_flat_chunk_is_one_plate(self):
        spec = B.bdhc_from_corners(flat_grid(32.0))
        self.assertEqual(len(spec["plates"]), 1)
        self.assertEqual(spec["strips"], [[B.to_fx(256), 1, 0]])
        q = B.Query(spec)
        for tx, tz in ((0, 0), (31, 31), (5, 17)):
            self.assertEqual(q.height(*B.tile_center(tx, tz)), 32.0)

    def test_stairs_and_ramps(self):
        grid = flat_grid(0.0)
        for tz in range(10, 14):          # south-facing stairs: rise 8 units per tile going north
            for tx in range(4, 8):
                top = 8.0 * (14 - tz)
                grid[tz][tx] = [top, top, top - 8, top - 8]
        for tz in range(0, 32):           # east ramp column, 4 units per tile
            grid[tz][20] = [0.0, 4.0, 4.0, 0.0]
            for tx in range(21, 32):
                grid[tz][tx] = [4.0] * 4
        spec = B.bdhc_from_corners(grid)
        codecs.encode_bdhc(spec)
        q = B.Query(spec)
        for tz in range(10, 14):
            cx, cz = B.tile_center(5, tz)
            self.assertAlmostEqual(q.height(cx, cz), 8.0 * (14 - tz) - 4, delta=2 / 4096)
        self.assertAlmostEqual(q.height(-256 + 16 * 20 + 4, 0), 1.0, delta=2 / 4096)
        self.assertEqual(q.height(*B.tile_center(25, 3)), 4.0)
        self.assertLess(len(spec["plates"]), 12)

    def test_holes_and_strip_rule(self):
        grid = flat_grid(0.0)
        for tz in range(8, 12):
            for tx in range(8, 12):
                grid[tz][tx] = None
        grid[3][3] = [16.0] * 4
        spec = B.bdhc_from_corners(grid)
        q = B.Query(spec)
        self.assertIsNone(q.height(*B.tile_center(9, 9)))
        self.assertEqual(q.height(*B.tile_center(3, 3)), 16.0)
        self.assert_vanilla_layout(spec)

    def test_non_planar_tile_is_rejected(self):
        grid = flat_grid(0.0)
        grid[4][7] = [0.0, 8.0, 0.0, 0.0]
        with self.assertRaisesRegex(B.NonPlanarTile, r"tile \(7, 4\)"):
            B.bdhc_from_corners(grid)

    def test_checkerboard_fits_the_buffer(self):
        grid = [[[float((x + z) % 2) * 8] * 4 for x in range(32)] for z in range(32)]
        spec = B.bdhc_from_corners(grid)
        self.assertEqual(len(spec["plates"]), 1024)
        self.assertLessEqual(B.bdhc_size(spec), codecs.BDHC_MAX_BYTES)

    def assert_vanilla_layout(self, spec):
        rects = []
        for p1, p2, _, _ in spec["plates"]:
            (x0, z0), (x1, z1) = spec["points"][p1], spec["points"][p2]
            self.assertLessEqual((x0, z0), (x1, z1))
            rects.append((z0, z1))
        zs = sorted({z for r in rects for z in r})
        self.assertEqual([s[0] for s in spec["strips"]], zs[1:])
        for i, (scan, count, start) in enumerate(spec["strips"]):
            lower = zs[i]
            want = [k for k, (z0, z1) in enumerate(rects) if z0 <= scan and z1 > lower]
            self.assertEqual(spec["access"][start:start + count], want)


@unittest.skipUnless(ROM.exists(), "rom.nds not present")
class Vanilla(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            cls.total = B.run_check(str(ROM))

    def test_vanilla_strip_layout_rule(self):
        from tools.maps import narc
        from tools.maps.world import RomSource
        members = narc.members(RomSource(ROM).read("a/0/6/5"))
        for data in members:
            Generate.assert_vanilla_layout(self, codecs.decode_land(data)[0]["bdhc"])

    def test_regenerated_heights_agree(self):
        t = self.total
        self.assertEqual(t["chunks"], 676)
        self.assertEqual(t["other"], 0)
        self.assertGreaterEqual(t["exact"] / t["points"], 0.997)
        self.assertLessEqual(t["max_rounding"], 1 / 64)
        self.assertLessEqual(t["max_size_generated"], codecs.BDHC_MAX_BYTES)


if __name__ == "__main__":
    unittest.main()
