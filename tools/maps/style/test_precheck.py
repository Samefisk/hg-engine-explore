"""Tests for the layout pre-check (python3 -B -m unittest tools.maps.style.test_precheck).

Synthetic tests always run; the calibration against vanilla chunks, the
bench/showcase layouts and deliberately bad layouts needs the repository
rom.nds (and uses the build/map-style kit cache).
"""

from __future__ import annotations

import unittest

from . import precheck as P
from .kit import REPO

ROM = REPO / "rom.nds"


def blank(width=12, height=12, fill="T"):
    return [[fill] * width for _ in range(height)]


def rect(grid, x0, z0, w, h, ch):
    for z in range(z0, z0 + h):
        for x in range(x0, x0 + w):
            grid[z][x] = ch
    return grid


def rows(grid):
    return ["".join(r) for r in grid]


def vanilla_field():
    """A thick-walled field with a south ledge row landing on ground, and a pond."""
    g = rect(blank(), 2, 2, 8, 8, ".")
    rect(g, 3, 5, 6, 1, "v")
    rect(g, 4, 7, 3, 2, ",")
    return rows(g)


def vanilla_pond():
    g = rect(blank(), 2, 2, 8, 8, ".")
    rect(g, 4, 4, 4, 4, "~")
    return rows(g)


def vanilla():
    return P.Vanilla({10: vanilla_field(), 11: vanilla_pond()})


class WindowTests(unittest.TestCase):
    def test_seen_exact_wildcard_and_reduced(self):
        v = vanilla()
        self.assertTrue(v.seen("TT..", 2))
        self.assertTrue(v.seen("vv..", 2))
        self.assertTrue(v.seen("*~*.", 2))                  # '*' matches anything
        self.assertFalse(v.seen("v~**", 2))                 # nothing puts water beside a ledge
        self.assertFalse(v.seen(",,,......", 3))
        self.assertTrue(v.seen(",,,......", 3, reduced=True))  # grass reads as ground

    def test_vanilla_layouts_have_no_window_findings(self):
        v = vanilla()
        for land_rows in v.lands.values():
            self.assertEqual(P.check_windows(land_rows, v), [])

    def test_water_against_ledge_is_one_region_with_nearest_example(self):
        g = rect(blank(), 2, 2, 8, 8, ".")
        rect(g, 3, 4, 6, 1, "v")
        rect(g, 3, 5, 6, 2, "~")
        findings = P.check_windows(rows(g), vanilla())
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f["severity"], "warning")
        self.assertIn("water directly south of south ledge", f["message"])
        self.assertLessEqual(f["x"], 3)
        self.assertLessEqual(f["z"], 4)
        self.assertGreaterEqual(f["x"] + f["w"], 9)
        ex = f["example"]
        self.assertIn(ex["land"], (10, 11))
        self.assertEqual(len(ex["context"]), f["window"]["k"] + 2)
        # the example really is that vanilla window
        k = f["window"]["k"]
        land_rows = vanilla().lands[ex["land"]]
        got = "".join(land_rows[ex["z"] + dz][ex["x"]:ex["x"] + k] for dz in range(k))
        self.assertEqual(got, ex["window"])

    def test_nearest_prefers_smallest_cost(self):
        v = vanilla()
        near = v.nearest("vv~~", 2)
        self.assertEqual(near["window"], "vv..")  # water->ground costs 2 per tile; ledges cost 4
        self.assertEqual(near["cost"], 4.0)


class RuleTests(unittest.TestCase):
    def test_missing_classes(self):
        v = P.Vanilla({1: rows(rect(blank(), 2, 2, 8, 8, "."))})
        g = rect(rect(blank(), 2, 2, 8, 8, "."), 3, 3, 2, 2, "~")
        rect(g, 6, 6, 2, 2, ",")
        found = {f["message"].split(" cells")[0]: f["severity"] for f in P.check_classes(rows(g), v)}
        self.assertEqual(found, {"the tileset has no water": "error", "the tileset has no grass": "warning"})

    def test_ledge_landing_and_approach(self):
        g = rect(blank(), 2, 2, 8, 8, ".")
        rect(g, 3, 4, 3, 1, "v")
        rect(g, 3, 5, 3, 1, "T")      # lands on a wall
        kinds = [(f["kind"], f["tiles"]) for f in P.check_ledges(rows(g))]
        self.assertEqual(kinds, [("ledge-landing", 3)])
        ok = rect(rect(blank(), 2, 2, 8, 8, "."), 3, 4, 3, 1, "v")
        self.assertEqual(P.check_ledges(rows(ok)), [])

    def test_narrow_paths_and_walls(self):
        g = rect(blank(), 2, 2, 8, 3, ".")
        rect(g, 5, 5, 1, 3, ".")          # 1-wide corridor
        rect(g, 2, 8, 8, 2, ".")          # the border below stays 2 thick
        found = P.check_narrow(rows(g))
        self.assertEqual([(f["message"].split(" 1")[0], f["x"], f["z"], f["tiles"]) for f in found],
                         [("path", 5, 5, 3)])
        wide = rect(g, 5, 5, 2, 3, ".")
        self.assertEqual(P.check_narrow(rows(wide)), [])

    def test_pockets(self):
        g = rect(blank(), 1, 1, 4, 4, ".")
        rect(g, 7, 7, 3, 3, ".")
        found = P.check_pockets(rows(g))
        self.assertEqual([(f["severity"], f["tiles"]) for f in found], [("error", 9)])
        rect(g, 5, 3, 2, 1, "*")
        rect(g, 6, 4, 1, 4, "*")
        found = P.check_pockets(rows(g))
        self.assertEqual([(f["severity"], f["kind"]) for f in found], [("warning", "pocket-if-wild")])

    def test_points(self):
        g = rect(rect(blank(), 2, 2, 8, 8, "."), 4, 4, 1, 1, ",")
        found = P.check_points(rows(g), [(3, 3, "start"), (4, 4, "warp 0"), (0, 0, "warp 1"), (40, 0, "warp 2")])
        self.assertEqual([(f["severity"], f["kind"]) for f in found],
                         [("warning", "point-soft"), ("error", "point"), ("error", "point")])

    def test_structure_error(self):
        _, found = P.check_text("TTT\n...\n", vanilla())
        self.assertEqual([(f["severity"], f["kind"]) for f in found], [("error", "structure")])

    def test_format_text(self):
        g = rect(blank(), 2, 2, 8, 8, ".")
        rect(g, 3, 4, 6, 1, "v")
        rect(g, 3, 5, 6, 2, "~")
        text = P.format_text(P.check_rows(rows(g), vanilla()), "head")
        self.assertIn("vanilla land", text)
        self.assertTrue(text.endswith("warning(s)"))


def _bad(fill_steps) -> str:
    g = blank(32, 32)
    for x, z, w, h, ch in fill_steps:
        rect(g, x, z, w, h, ch)
    return "\n".join(rows(g)) + "\n"


# Deliberately bad layouts (the ones measured in the precheck report).
BAD_WATER_LEDGE = _bad([(3, 3, 26, 26, "."), (6, 10, 20, 1, "v"), (6, 11, 20, 5, "~"), (6, 20, 20, 1, ","),
                        (4, 24, 1, 4, "~")])
BAD_POCKET = _bad([(3, 3, 26, 12, ".")] + [(x, z, 1, 1, "T") for z in range(5, 12) for x in range(5, 26)
                                           if (x + z) % 2 == 0]
                  + [(15, 15, 1, 8, "."), (10, 23, 12, 5, "."), (24, 20, 4, 4, ".")])
BAD_CAVE = _bad([(4, 4, 24, 24, "."), (8, 8, 16, 6, ","), (6, 18, 20, 1, "^")])


@unittest.skipUnless(ROM.exists(), "needs rom.nds")
class CalibrationTests(unittest.TestCase):
    """Known-good layouts produce no errors and few warnings; bad layouts are flagged."""

    @classmethod
    def setUpClass(cls):
        cls.vanilla = {m: P.load_vanilla(m)[1] for m in (33, 46, 107)}

    def check(self, path_or_text, map_id, relax=0):
        text = (REPO / path_or_text).read_text() if path_or_text.endswith(".txt") else path_or_text
        return P.check_text(text, P.Vanilla(self.vanilla[map_id]), relax)[1]

    def test_bench_and_showcase_layouts(self):
        cases = [("tools/maps/style/bench_layouts/541-twinwood-crossing.txt", 33, 0),
                 ("tools/maps/style/bench_layouts/542-mirrorlake-basin.txt", 46, 0),
                 ("tools/maps/style/bench_layouts/543-echo-cavern.txt", 107, 0)]
        # (The showcase maps' own layouts were retired with the walk-class generator; they are
        # designed from briefs now, data/maps/designs/.)
        for path, map_id, relax in cases:
            with self.subTest(path=path, relax=relax):
                found = self.check(path, map_id, relax)
                self.assertEqual([f for f in found if f["severity"] == "error"], [])
                self.assertLessEqual(len(found), 4)

    def test_vanilla_chunks_leave_one_out(self):
        # Vanilla chunks are busier than authored layouts: a few unseen windows per
        # chunk against the others is the measured baseline, never an error-level
        # window finding.
        for map_id, lands in self.vanilla.items():
            with self.subTest(map=map_id):
                counts = P.calibrate(lands)
                windows = [c.get("unseen-window", 0) for c in counts.values()]
                self.assertLessEqual(sum(windows) / len(windows), 6)

    def test_bad_layouts_are_flagged(self):
        kinds = lambda found: {(f["severity"], f["kind"]) for f in found}
        water = kinds(self.check(BAD_WATER_LEDGE, 33))
        self.assertTrue({("warning", "ledge-landing"), ("warning", "unseen-window"), ("warning", "narrow")} <= water)
        pocket = kinds(self.check(BAD_POCKET, 33))
        self.assertIn(("error", "pocket"), pocket)
        self.assertIn(("warning", "narrow"), pocket)
        cave = self.check(BAD_CAVE, 107)
        self.assertIn(("error", "missing-class"), kinds(cave))
        self.assertTrue(any("grass" in f["message"] for f in cave))


if __name__ == "__main__":
    unittest.main()
