"""Tests for the offline walk check.

  python3 -B -m unittest tools.maps.test_walk

Synthetic tests run on a tiny fake grid. ROM-backed tests (rom.nds in the
repo root) replay the walks that were measured in melonDS: the showcase goal
checks and panel probe (tools/maps/showcase.py) and the Route 29 proof
(tools/maps/proof_route29.py), so the model's predictions stay tied to
observed game behavior.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from . import walk

ROM = walk.REPO / "rom.nds"

# ASCII tiles for the fake grid: (blocked, behavior)
LEGEND = {
    ".": (False, 0x00), "#": (True, 0x00),
    "v": (True, walk.B_JUMP_SOUTH), ">": (True, walk.B_JUMP_EAST),
    "~": (False, 0x15), "W": (True, 0x15),
    "P": (False, walk.B_WARP_PANEL), "D": (True, walk.B_DOOR),
    "M": (False, walk.B_ENTRANCE_SOUTH), "N": (False, walk.B_ENTRANCE_NORTH),
    "I": (False, walk.B_ICE), "s": (False, 0x33),   # 0x33 (51): blocks moving south off it / into it from the north
    "X": (False, 0xFF),
}


class FakeTerrain(walk.Terrain):
    """maps: {map: {"matrix": m, "events": {...}}}; grids: {matrix: ([rows], zones or None)}."""

    def __init__(self, grids, maps, heights=None):
        self.grids, self.maps, self.heights = grids, maps, heights or {}

    def matrix_id(self, map_id):
        return self.maps[map_id]["matrix"]

    def tile(self, matrix_id, x, z):
        rows = self.grids[matrix_id][0]
        if not (0 <= z < len(rows) and 0 <= x < len(rows[z])) or rows[z][x] == " ":
            return None
        return LEGEND[rows[z][x]]

    def height(self, matrix_id, x, z, current_y):
        if self.tile(matrix_id, x, z) is None:
            return None
        return self.heights.get((matrix_id, x, z), 0)

    def zone(self, matrix_id, loaded_map, x, z):
        zones = self.grids[matrix_id][1]
        return zones(x, z) if zones else loaded_map

    def events(self, map_id):
        return self.maps[map_id]["events"]

    def has_map(self, map_id):
        return map_id in self.maps


def _events(warps=(), objects=(), coords=()):
    return {"warps": [dict(w) for w in warps], "objects": [dict(o) for o in objects],
            "coords": [dict(c) for c in coords], "bgs": []}


def _warp(x, z, header, anchor):
    return {"x": x, "z": z, "header": header, "anchor": anchor, "y": 0}


def _final(result):
    f = result["final"]
    return [f["map"], f["x"], f["z"]]


ROOM = [
    "#######",
    "#.....#",
    "#..s..#",
    "#.....#",
    "#vvv>.#",
    "#.....#",
    "#.~~..#",
    "#.....#",
    "##D####",
]


def _one_map(rows=ROOM, events=None, heights=None):
    return FakeTerrain({0: (rows, None)}, {1: {"matrix": 0, "events": events or _events()}}, heights)


class SyntheticTests(unittest.TestCase):
    def kinds(self, result):
        return [e["kind"] for e in result["trace"]]

    def test_moves_and_collision(self):
        r = walk.walk(_one_map(), 1, 1, 1, "RIGHT 2, UP 1")
        self.assertEqual(_final(r), [1, 3, 1])
        self.assertEqual(self.kinds(r), ["moved", "moved", "blocked"])
        self.assertEqual(r["trace"][2]["reason"], "blocked by collision")
        self.assertTrue(r["trace"][0]["turned"])     # started facing down

    def test_map_edge(self):
        rows = ["...", "..."]
        r = walk.walk(_one_map(rows), 1, 0, 0, "LEFT 1, UP 1")
        self.assertEqual(_final(r), [1, 0, 0])
        self.assertEqual([e["reason"] for e in r["trace"]], ["map edge", "map edge"])

    def test_behavior_ff_blocks(self):
        r = walk.walk(_one_map([".X."]), 1, 0, 0, "RIGHT 1")
        self.assertEqual(r["trace"][0]["reason"], "blocked by behavior 0xff")

    def test_ledge_is_one_way_and_jumps_two(self):
        r = walk.walk(_one_map(), 1, 2, 3, "DOWN 1, UP 1")
        self.assertEqual(self.kinds(r), ["ledge jump", "blocked"])
        self.assertEqual(_final(r), [1, 2, 5])
        # The east ledge only works going east; going south over it is blocked.
        r = walk.walk(_one_map(), 1, 4, 3, "DOWN 1")
        self.assertEqual(self.kinds(r), ["blocked"])
        r = walk.walk(_one_map(), 1, 3, 5, "UP 1, FACE RIGHT")   # the landing row; ledges are blocked from below
        self.assertEqual(_final(r), [1, 3, 5])
        r = walk.walk(_one_map(), 1, 3, 4, "RIGHT 1")            # beside an east ledge: jump two tiles east
        self.assertEqual(_final(r), [1, 5, 4])

    def test_one_way_behavior(self):
        # 0x33 blocks leaving south and entering from the north side.
        r = walk.walk(_one_map(), 1, 3, 2, "DOWN 1")
        self.assertEqual(r["trace"][0]["reason"], "blocked by one-way behavior 0x33 (exit)")
        r = walk.walk(_one_map(), 1, 3, 3, "UP 1")
        self.assertEqual(r["trace"][0]["reason"], "blocked by one-way behavior 0x33 (entry)")
        r = walk.walk(_one_map(), 1, 3, 1, "DOWN 1, DOWN 1")
        self.assertEqual(_final(r), [1, 3, 2])

    def test_water_needs_surf(self):
        r = walk.walk(_one_map(), 1, 2, 5, "DOWN 1")
        self.assertEqual(r["trace"][0]["reason"], "surf needed")
        r = walk.walk(_one_map(), 1, 1, 6, "RIGHT 3", surf=True)
        self.assertEqual(self.kinds(r), ["surf mount", "moved", "surf dismount"])
        self.assertEqual(_final(r), [1, 4, 6])
        self.assertFalse(r["final"]["surfing"])

    def test_surf_blocked_by_collision_water(self):
        rows = ["~W."]
        r = walk.walk(_one_map(rows), 1, 0, 0, "RIGHT 1", surf=True)
        self.assertTrue(r["final"]["surfing"])
        self.assertEqual(r["trace"][0]["kind"], "blocked")

    def test_object_blocks_by_height(self):
        obj = {"id": 3, "x": 2, "z": 1, "y": 0, "eventFlag": 0}
        r = walk.walk(_one_map(events=_events(objects=[obj])), 1, 1, 1, "RIGHT 1")
        self.assertEqual(r["trace"][0]["reason"], "blocked by object id 3")
        r = walk.walk(_one_map(events=_events(objects=[obj])), 1, 1, 1, "RIGHT 1", objects=False)
        self.assertEqual(_final(r), [1, 2, 1])
        # An object two half-tile units above the player does not block.
        high = dict(obj, y=16 * 4096)
        terrain = _one_map(events=_events(objects=[high]), heights={(0, 2, 1): 16 * 4096})
        r = walk.walk(terrain, 1, 1, 1, "RIGHT 1")
        self.assertEqual(r["trace"][0]["kind"], "moved")

    def test_height_step_limit(self):
        # 1.25 tiles (0x14000) blocks; just under it walks.
        terrain = _one_map(heights={(0, 2, 1): 0x14000, (0, 1, 2): 0x13FFF})
        r = walk.walk(terrain, 1, 1, 1, "RIGHT 1, DOWN 1")
        self.assertEqual(r["trace"][0]["reason"], "height change (+1.25 tiles)")
        self.assertEqual(_final(r), [1, 1, 2])

    def test_door_hold_and_step_out(self):
        rows_a = ["...", ".D.", "...", "..."]
        # The door at (1,1) is entered by walking into it from the south.
        rows_b = ["#####", "#...#", "#.M.#", "##.##"]
        maps = {
            1: {"matrix": 0, "events": _events(warps=[_warp(1, 1, 2, 0)])},
            2: {"matrix": 1, "events": _events(warps=[_warp(2, 2, 1, 0)])},
        }
        terrain = FakeTerrain({0: (rows_a, None), 1: (rows_b, None)}, maps)
        r = walk.walk(terrain, 1, 1, 2, "UP 1", facing=walk.UP)
        self.assertEqual(_final(r), [2, 2, 2])
        self.assertEqual(r["trace"][0]["via"], [1, 1, 1])
        # Exit mat: DOWN with an open tile in front just walks off the mat ...
        r = walk.walk(terrain, 2, 2, 2, "DOWN 1")
        self.assertEqual(_final(r), [2, 2, 3])
        # ... while a blocked tile in front warps, and the door arrival steps south.
        rows_b2 = ["#####", "#...#", "#.M.#", "#####"]
        terrain = FakeTerrain({0: (rows_a, None), 1: (rows_b2, None)}, maps)
        r = walk.walk(terrain, 2, 2, 2, "DOWN 1")
        self.assertEqual(_final(r), [1, 1, 2])
        self.assertIn("stepped out of the door", r["trace"][0]["reason"])
        # Facing the wrong way on the mat (LEFT) does not warp.
        r = walk.walk(terrain, 2, 2, 2, "LEFT 1")
        self.assertEqual(_final(r), [2, 1, 2])

    def test_panel_and_plain_warp(self):
        rows = ["P..", "..."]
        maps = {1: {"matrix": 0, "events": _events(warps=[_warp(0, 0, 2, 0), _warp(2, 0, 2, 0)])},
                2: {"matrix": 1, "events": _events(warps=[_warp(1, 1, 1, 1)])}}
        terrain = FakeTerrain({0: (rows, None), 1: (["...", "...", "..."], None)}, maps)
        r = walk.walk(terrain, 1, 0, 1, "UP 1")            # onto the panel: warps
        self.assertEqual(_final(r), [2, 1, 1])
        self.assertEqual(r["trace"][0]["kind"], "warp")
        r = walk.walk(terrain, 1, 2, 1, "UP 1")            # plain tile with a warp: nothing
        self.assertEqual(_final(r), [1, 2, 0])
        self.assertEqual(r["trace"][0]["kind"], "moved")

    def test_step_on_north_entrance_warps(self):
        rows = [".N.", "..."]
        maps = {1: {"matrix": 0, "events": _events(warps=[_warp(1, 0, 2, 0)])},
                2: {"matrix": 1, "events": _events(warps=[_warp(0, 0, 1, 0)])}}
        terrain = FakeTerrain({0: (rows, None), 1: (["..", ".."], None)}, maps)
        r = walk.walk(terrain, 1, 1, 1, "UP 2")            # warp, then keep walking in map 2
        self.assertEqual([e["kind"] for e in r["trace"]], ["warp", "blocked"])
        self.assertEqual(_final(r), [2, 0, 0])

    def test_dynamic_warp_returns_to_origin(self):
        rows_a = ["P.P", "..."]
        maps = {1: {"matrix": 0, "events": _events(warps=[_warp(0, 0, 2, 0), _warp(2, 0, 2, 0)])},
                2: {"matrix": 1, "events": _events(warps=[_warp(1, 1, 0xFFF, 0x100), _warp(1, 0, 0xFFF, 0x100)])}}
        terrain = FakeTerrain({0: (rows_a, None), 1: (["#P#", ".P.", "..."], None)}, maps)
        r = walk.walk(terrain, 1, 2, 1, "UP 1, DOWN 1, UP 1")
        # Entered through warp 1 (2,0); the return panel sends us back onto it.
        self.assertEqual(r["trace"][0]["to"], [2, 1, 1])
        self.assertEqual(_final(r), [1, 2, 0])
        r = walk.walk(terrain, 2, 1, 2, "UP 1")
        self.assertEqual(r["status"], "unmodelled")

    def test_zone_change_on_shared_matrix(self):
        rows = ["......"]
        maps = {1: {"matrix": 0, "events": _events()}, 2: {"matrix": 0, "events": _events()}}
        terrain = FakeTerrain({0: (rows, lambda x, z: 1 if x < 3 else 2)}, maps)
        r = walk.walk(terrain, 1, 1, 0, "RIGHT 3")
        self.assertEqual(_final(r), [2, 4, 0])
        self.assertIn("zone 1 -> 2", r["trace"][1]["notes"])

    def test_unmodelled_ice_stops(self):
        r = walk.walk(_one_map([".I.."]), 1, 0, 0, "RIGHT 3")
        self.assertEqual(r["status"], "unmodelled")
        self.assertEqual(r["reason"], "unmodelled behavior 0x20")
        self.assertEqual(len(r["trace"]), 1)

    def test_coord_event_is_noted(self):
        events = _events(coords=[{"scriptId": 7, "x": 2, "z": 1, "w": 2, "h": 1, "y": 0, "val": 0, "var": 0x4000}])
        r = walk.walk(_one_map(events=events), 1, 1, 1, "RIGHT 1")
        self.assertIn("coord event script 7", r["trace"][0]["notes"][0])

    def test_face_only_turns(self):
        r = walk.walk(_one_map(), 1, 1, 1, "FACE RIGHT")
        self.assertEqual(_final(r), [1, 1, 1])
        self.assertEqual(r["final"]["facing"], "right")

    def test_parse_moves(self):
        self.assertEqual(walk.parse_moves("down 3, FACE left,RIGHT"),
                         [("step", walk.DOWN, 3), ("face", walk.LEFT, 1), ("step", walk.RIGHT, 1)])
        for bad in ("NORTH 2", "DOWN x", "FACE LEFT 2", "DOWN 1 2"):
            with self.assertRaises(ValueError):
                walk.parse_moves(bad)
        self.assertEqual(walk.walk(_one_map(), 1, 1, 1, "SIDEWAYS")["status"], "error")


# Measured in melonDS (showcase.goal_checks / showcase.probe, proof_route29.probe).
SHOWCASE_CASES = [
    {"name": "541 crosses chunk seam", "map": 541, "at": [29, 42], "facing": "right",
     "moves": "RIGHT 4", "expect": [541, 33, 42]},
    {"name": "542 terrace jump down", "map": 542, "at": [20, 5], "facing": "down",
     "moves": "DOWN 1", "expect": [542, 20, 7]},
    {"name": "542 terrace refuses the climb", "map": 542, "at": [20, 7], "facing": "up",
     "moves": "UP 1", "expect": [542, 20, 7]},
    {"name": "543 ledge drop", "map": 543, "at": [15, 10], "facing": "down",
     "moves": "DOWN 1", "expect": [543, 15, 12]},
]
PANELS = [(541, (559, 394), (32, 57)), (542, (561, 394), (5, 16)), (543, (563, 394), (16, 60))]
CHERRYGROVE_ARRIVAL = [67, 561, 393]
for _map, (_dx, _dz), (_ax, _az) in PANELS:
    SHOWCASE_CASES += [
        {"name": f"Cherrygrove panel -> {_map}", "map": 67, "at": [_dx, _dz - 1], "facing": "down",
         "moves": "DOWN 1", "expect": [_map, _ax, _az]},
        {"name": f"{_map} arrival does not bounce", "map": _map, "at": [_ax, _az], "facing": "down",
         "moves": "", "expect": [_map, _ax, _az]},
        {"name": f"{_map} return panel -> Cherrygrove", "map": 67, "at": [_dx, _dz - 1], "facing": "down",
         "moves": "DOWN 1, DOWN 1", "expect": CHERRYGROVE_ARRIVAL},
    ]

ROUTE29_VANILLA = [
    {"name": "Route 29 block tile walks on vanilla", "map": 33, "at": [628, 395], "facing": "up",
     "moves": "UP 1", "vanilla": True, "expect": [33, 628, 394]},
    {"name": "Route 29 open control steps", "map": 33, "at": [627, 395], "facing": "up",
     "moves": "UP 1", "vanilla": True, "expect": [33, 627, 394]},
    {"name": "Route 29 panel tile walks on vanilla", "map": 33, "at": [624, 395], "facing": "down",
     "moves": "DOWN 1", "vanilla": True, "expect": [33, 624, 396]},
]


@unittest.skipUnless(ROM.exists(), "rom.nds not present")
class RomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from . import world
        cls.base = world.load_base(world.RomSource(ROM))
        cls.edited = world.apply_overrides(cls.base, walk.REPO / "data/maps")
        cls.terrains = {True: walk.WorldTerrain(cls.base), False: walk.WorldTerrain(cls.edited)}

    def assertCases(self, cases, terrains=None):
        rows, ok = walk.run_checks(cases, terrains or self.terrains)
        bad = [(r["name"], r["expect"], r["got"], r["status"], r["reason"]) for r in rows if not r["pass"]]
        self.assertTrue(ok, bad)

    def test_showcase_measured_walks(self):
        self.assertCases(SHOWCASE_CASES)

    def test_route29_vanilla(self):
        self.assertCases(ROUTE29_VANILLA)

    def test_route29_proof_edit(self):
        from . import proof_route29, world
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                proof_route29.write(Path(tmp))
            edited = walk.WorldTerrain(world.apply_overrides(self.base, Path(tmp)))
        cases = [
            {"name": "blocked tile refuses the step", "map": 33, "at": [628, 395], "facing": "up",
             "moves": "UP 1", "expect": [33, 628, 395]},
            {"name": "open control steps", "map": 33, "at": [627, 395], "facing": "up",
             "moves": "UP 1", "expect": [33, 627, 394]},
            {"name": "panel warps to the gate", "map": 33, "at": [624, 395], "facing": "down",
             "moves": "DOWN 1", "expect": list(proof_route29.GATE_LANDING)},
        ]
        self.assertCases(cases, {False: edited, True: edited})
        r = walk.walk(edited, 33, 628, 395, "UP 1", walk.UP)
        self.assertEqual(r["trace"][0]["reason"], "blocked by collision")

    def test_pokemon_center_door_round_trip(self):
        # Cherrygrove save start faces the Pokémon Center door (showcase.SAVE_START).
        r = walk.walk(self.terrains[True], 67, 564, 392, "UP 1, DOWN 1", walk.UP)
        self.assertEqual([e["kind"] for e in r["trace"]], ["warp", "warp"])
        self.assertEqual(r["trace"][0]["via"], [67, 564, 391])
        self.assertEqual(_final(r), [67, 564, 392])
        self.assertIn("stepped out of the door", r["trace"][1]["reason"])

    def test_check_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.json"
            path.write_text(json.dumps({"cases": SHOWCASE_CASES[:2]}))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(walk.main(["--check", str(path)]), 0)
            wrong = [dict(SHOWCASE_CASES[0], expect=[541, 0, 0])]
            path.write_text(json.dumps(wrong))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(walk.main(["--check", str(path)]), 1)
            self.assertIn("FAIL", out.getvalue())


if __name__ == "__main__":
    unittest.main()
