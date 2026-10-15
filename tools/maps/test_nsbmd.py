"""Tests for tools.maps.nsbmd.  Run: python3 -B -m unittest tools.maps.test_nsbmd"""

from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

from . import nsbmd

ROM = Path(__file__).resolve().parents[2] / "rom.nds"
HAVE_ROM = ROM.exists()


def _grid_spec(**extra) -> dict:
    tiles = [["grass" if x < 16 else "road" for x in range(32)] for _ in range(32)]
    spec = {"name": "test_chunk", "tiles": tiles,
            "materials": {"grass": {"texture": "grass01", "palette": "grass01_pl", "size": [32, 32],
                                    "tilesPerRepeat": 2},
                          "road": {"texture": "road01", "palette": "road01_pl", "size": [16, 16],
                                   "lit": False}}}
    spec.update(extra)
    return spec


class Dictionaries(unittest.TestCase):
    def test_single_entry_tree_matches_vanilla_shape(self):
        # Vanilla land 0's MDL0 dictionary: root 7f/1/0/0, entry node 46/0/1/0.
        tree = nsbmd.patricia_tree([b"map21_12c".ljust(16, b"\0")])
        self.assertEqual(tree, [(127, 1, 0, 0), (0x46, 0, 1, 0)])

    def test_dict_round_trip_and_lookup(self):
        names = ["grass01", "grass01_a", "road01", "tree01_re", "a" * 16]
        entries = [struct.pack("<I", i * 4) for i in range(len(names))]
        blob = nsbmd.build_dict(names, entries, 4)
        got_names, got_entries, size = nsbmd.read_dict(blob, 0)
        self.assertEqual((got_names, got_entries, size), (names, entries, len(blob)))
        tree = nsbmd.patricia_tree([n.encode().ljust(16, b"\0") for n in names])
        for i, name in enumerate(names):  # the NNS search walk finds every entry
            key = name.encode().ljust(16, b"\0")
            p, x = 0, tree[0][1]
            while tree[p][0] > tree[x][0]:
                p, x = x, tree[x][2] if nsbmd._bit(key, tree[x][0]) else tree[x][1]
            self.assertEqual(tree[x][3], i)

    def test_duplicate_and_long_names_rejected(self):
        with self.assertRaises(nsbmd.NsbmdError):
            nsbmd.build_dict(["a", "a"], [b"\0" * 4] * 2, 4)
        with self.assertRaises(nsbmd.NsbmdError):
            nsbmd.build_dict(["x" * 17], [b"\0" * 4], 4)


class DisplayLists(unittest.TestCase):
    def test_pack_unpack(self):
        cmds = [[0x40, 1], [0x22, 0x100010], [0x21, 0x7FC00], [0x23, 0x10, 0x20],
                [0x41], [0], [0], [0]]
        raw = nsbmd.encode_dl(cmds)
        self.assertEqual(struct.unpack_from("<I", raw)[0], 0x23212240)
        self.assertEqual(len(raw), 4 * (1 + 5 + 1))  # word, 5 params, END word
        self.assertEqual(nsbmd.decode_dl(raw), cmds)

    def test_wrong_parameter_count_rejected(self):
        with self.assertRaises(nsbmd.NsbmdError):
            nsbmd.encode_dl([[0x23, 1]])
        with self.assertRaises(nsbmd.NsbmdError):
            nsbmd.decode_dl(struct.pack("<I", 0x23))  # VTX_16 without its 2 words

    def test_vertex_forms(self):
        cmds = [[0x40, 0], [0x24, (1 & 0x3FF) | ((2 & 0x3FF) << 10) | ((-3 & 0x3FF) << 20)],
                [0x28, 5], [0x26, 0x00070006], [0x41]]
        verts = nsbmd.dl_primitives(cmds)[0]["vertices"]
        self.assertEqual([v["pos"] for v in verts], [(64, 128, -192), (69, 128, -192), (6, 128, 7)])


class Generator(unittest.TestCase):
    def build(self, **extra) -> bytes:
        return nsbmd.write(nsbmd.grid_spec_to_model(_grid_spec(**extra), None))

    def test_flat_grid_merges_and_validates(self):
        data = self.build()
        errors, warnings = nsbmd.validate(data)
        self.assertEqual((errors, warnings), ([], []))
        model = nsbmd.parse(data)["models"][0]
        # grass: 32-texel texture over 2 tiles -> 16 tiles per merged run fits 2048 texels.
        self.assertEqual(model["info"]["numQuad"], model["info"]["numPolygon"])
        self.assertLessEqual(model["info"]["numPolygon"], 8)
        self.assertEqual(model["info"]["posScale"], 0x40000)
        self.assertEqual([t["name"] for t in model["textures"]], ["grass01", "road01"])
        self.assertEqual(model["shapes"][0]["flag"], 5)  # lit: normal + texcoord
        self.assertEqual(model["shapes"][1]["flag"], 6)  # unlit: color + texcoord
        for shape in model["shapes"]:
            self.assertEqual(shape["dl"][-4:], [[0]] * 4)

    def test_geometry_covers_chunk_and_faces_up(self):
        model = nsbmd.parse(self.build(merge=False))["models"][0]
        self.assertEqual(model["info"]["numQuad"], 1024)
        geo = nsbmd.geometry(model)
        area = 0
        for polys in geo.values():
            for poly in polys:
                (a, *_), (b, *_), (c, *_) = poly[0], poly[1], poly[2]
                cross_y = (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2])
                self.assertGreater(cross_y, 0)
                xs = [v[0][0] for v in poly]
                zs = [v[0][2] for v in poly]
                area += (max(xs) - min(xs)) * (max(zs) - min(zs))
        self.assertEqual(area, 512 * 512)

    def test_heights_and_explicit_quads(self):
        heights = [[0] * 33 for _ in range(33)]
        heights[10][10] = 16
        quads = [{"x": 0, "z": 0, "material": "road", "heights": [8, 8, 0, 0],
                  "uv": [[0, 0], [16, 0], [16, 16], [0, 16]]}]
        model = nsbmd.parse(self.build(heights=heights, quads=quads))["models"][0]
        self.assertEqual(nsbmd.validate(nsbmd.write({"version": 2, "models": [model]}))[0], [])
        ys = {v[0][1] for polys in nsbmd.geometry(model).values() for p in polys for v in p}
        self.assertEqual(ys, {0, 8, 16})
        self.assertEqual(model["info"]["box"][4] * model["info"]["boxPosScale"] // 4096, 16 * 4096)

    def test_bad_specs_rejected(self):
        with self.assertRaises(nsbmd.NsbmdError):
            self.build(tiles=[["grass"] * 31] * 32)
        with self.assertRaises(nsbmd.NsbmdError):
            self.build(tiles=[["lava"] * 32] * 32)
        texset = {"textures": {"grass01": {"width": 32, "height": 32, "format": 3}},
                  "palettes": ["grass01_pl"]}
        with self.assertRaises(nsbmd.NsbmdError):  # road01 is not in this texture set
            nsbmd.grid_spec_to_model(_grid_spec(), texset)


@unittest.skipUnless(HAVE_ROM, "needs rom.nds")
class Vanilla(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from .world import RomSource
        cls.src = RomSource(ROM)
        cls.models = nsbmd._land_models(cls.src)

    def test_every_land_model_round_trips_through_json(self):
        self.assertEqual(len(self.models), 676)
        for i, data in enumerate(self.models):
            spec = json.loads(json.dumps(nsbmd.parse(data)))
            self.assertEqual(nsbmd.write(spec), data, f"land {i}")

    def test_rebuilt_vanilla_geometry_is_identical(self):
        for i in (0, 4, 216, 257, 600):
            model = nsbmd.parse(self.models[i])["models"][0]
            rebuilt = nsbmd.parse(nsbmd.write(nsbmd.rebuild_vanilla(model)))["models"][0]
            self.assertEqual(nsbmd.geometry(rebuilt), nsbmd.geometry(model), f"land {i}")

    def test_generate_against_area_texture_set(self):
        texset = nsbmd._area_texset(self.src, 25)  # Elm's lab interiors
        tiles = [["floor" if x < 14 and z < 14 else None for x in range(32)] for z in range(32)]
        spec = {"tiles": tiles, "materials": {
            "floor": {"texture": "01yuka_14", "palette": "01yuka_14_pl", "lit": False}}}
        data = nsbmd.write(nsbmd.grid_spec_to_model(spec, texset))
        self.assertEqual(nsbmd.validate(data, texset), ([], []))
        mat = nsbmd.parse(data)["models"][0]["materials"][0]
        self.assertEqual((mat["origWidth"], mat["origHeight"]), (16, 16))


if __name__ == "__main__":
    unittest.main()
