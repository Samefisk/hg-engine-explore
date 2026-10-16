"""Semantic pipeline tests (python3 -B -m unittest tools.maps.style.test_semantic).

The design tests are synthetic. The vanilla tests need rom.nds and use the
build/map-style kit cache.
"""

from __future__ import annotations

import random
import unittest

import numpy as np

from . import design, kit as kits, paint, semantic

ROM = kits.REPO / "rom.nds"


class TextTests(unittest.TestCase):
    def test_round_trip_keeps_levels_and_void(self):
        level = np.array([[2, 3], [semantic.VOID_LEVEL, 2]])
        sem = semantic.SemanticMap(["T.", " ="], level, ["T.", "T."])
        back = semantic.SemanticMap.from_text(sem.to_text())
        self.assertEqual(back.kind, sem.kind)
        self.assertEqual(back.walk, sem.walk)
        self.assertTrue((back.level == level).all())


class DesignTests(unittest.TestCase):
    def test_ledge_is_one_way(self):
        intent = np.array([[c] for c in "..v.."])  # a column: ground, a south ledge, ground
        top = design.reachable(intent, (0, 0))
        bottom = design.reachable(intent, (0, 4))
        self.assertTrue(top[4, 0], "jumping down the ledge reaches the bottom")
        self.assertFalse(bottom[0, 0], "the ledge cannot be climbed")

    def test_plan_reaches_every_exit_and_keeps_border(self):
        brief = {"template": 33, "kind": "route", "chunks": [1, 1], "seed": 4, "ledge": 1, "grass": 2,
                 "pond": 1, "exits": [{"side": "south", "at": 16}, {"side": "north", "at": 10}]}
        p = design.plan(brief)
        self.assertTrue(design._reaches_all(p.intent, p.exits, design.GROUND))
        exits = {t for _, _, ts in p.exits for t in ts}
        border = [(x, z) for z in range(32) for x in range(32) if x in (0, 31) or z in (0, 31)]
        self.assertFalse([t for t in border if t not in exits and p.intent[t[1], t[0]] != design.TREES])

    def test_cave_plan_has_no_staircase_walls(self):
        brief = {"template": 107, "kind": "cave", "chunks": [1, 2], "seed": 3, "clearings": 3,
                 "exits": [{"side": "south", "at": 16}, {"side": "north", "at": 12}]}
        p = design.plan(brief)
        open_ = np.isin(p.intent, list(design.WALKABLE_INTENTS) + list(design.LEDGES) + [design.ROCK])
        # A staircase is a 2x2 window with exactly two open tiles on a diagonal.
        a, b, c, d = open_[:-1, :-1], open_[:-1, 1:], open_[1:, :-1], open_[1:, 1:]
        diagonal = ((a & d & ~b & ~c) | (b & c & ~a & ~d))
        self.assertEqual(int(diagonal.sum()), 0)


@unittest.skipUnless(ROM.exists(), "needs the repository rom.nds")
class VanillaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from .. import world
        cls.kit = kits.load_or_build_kit(world.RomSource(ROM), 2)  # Route 29's tileset

    def test_walkable_tile_behind_a_tree_is_ground(self):
        sem = semantic.extract(self.kit, self.kit["chunks"][2])
        for z in range(32):
            for x in range(32):
                if sem.walk[z][x] in ".,":
                    self.assertNotEqual(sem.kind[z][x], "T", f"walkable tile {(x, z)} labelled as tree")

    def test_painting_vanilla_with_vanilla_reproduces_it(self):
        """With the chunk itself in the kit, its own description must come back exactly: every
        label, no bad seam, no overhang cut, no void. A regression here means the painter
        no longer prefers copying vanilla over inventing joins."""
        grid = np.array(self.kit["chunks"][2])[4:20, 4:20]
        target = semantic.extract(self.kit, grid)
        painter = paint.Painter(paint.source_for(self.kit), target, paint.Weights(sweeps=3))
        out = painter.solve()
        got = semantic.extract(self.kit, out)
        mismatches = sum(target.label(x, z) != got.label(x, z) for z in range(16) for x in range(16))
        self.assertLessEqual(mismatches, 3)
        report = painter.report()
        self.assertEqual(report["walkMismatches"], 0)
        self.assertLessEqual(report["badSeams"], 2)


if __name__ == "__main__":
    unittest.main()
