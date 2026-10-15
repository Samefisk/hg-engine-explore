"""Tests for tools.maps.  Run: python3 -B -m unittest tools.maps.test_codecs"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from . import cli, codecs, narc

ROOT = cli.REPO / "base/root"
HAVE_BASE = (ROOT / "a/0/6/5").exists()


def _blank_tiles() -> dict:
    return {"collision": ["." * 32] * 32,
            "behavior": [" ".join(["00"] * 32)] * 32,
            "secondary": [" ".join(["00"] * 32)] * 32}


class SyntheticEdits(unittest.TestCase):
    def test_tile_bits(self):
        tiles = _blank_tiles()
        tiles["collision"][3] = "#" + "." * 31
        tiles["behavior"][3] = "02 " + " ".join(["00"] * 31)
        tiles["secondary"][3] = "06 " + " ".join(["00"] * 31)
        raw = codecs.encode_tiles(tiles)
        self.assertEqual(int.from_bytes(raw[3 * 64:3 * 64 + 2], "little"), 0x8000 | (6 << 8) | 0x02)
        self.assertEqual(codecs.decode_tiles(raw), tiles)

    def test_tile_validation(self):
        tiles = _blank_tiles()
        tiles["secondary"][0] = "80 " + " ".join(["00"] * 31)
        with self.assertRaises(codecs.FormatError):
            codecs.encode_tiles(tiles)

    def test_events_add_warp_and_limit(self):
        spec = {"bgs": [], "objects": [], "warps": [], "coords": []}
        spec["warps"].append({"x": 5, "z": 7, "header": 33, "anchor": 0, "y": 0})
        self.assertEqual(codecs.decode_events(codecs.encode_events(spec)), spec)
        obj = dict.fromkeys(("id", "spriteId", "movement", "type", "eventFlag", "scriptId",
                             "facingDirection", "param0", "param1", "param2", "xRange",
                             "yRange", "x", "z", "y"), 0)
        spec["objects"] = [obj] * 64  # 16 + 12 + 64*32 = 2076 bytes
        with self.assertRaises(codecs.FormatError):
            codecs.encode_events(spec)

    def test_matrix_limits(self):
        spec = {"width": 40, "height": 20, "name": "big", "headers": None, "altitudes": None,
                "landData": [[0] * 40] * 20}
        with self.assertRaises(codecs.FormatError):
            codecs.encode_matrix(spec)
        spec.update(width=2, height=1, landData=[[7, 8]], headers=[[33, 33]])
        self.assertEqual(codecs.decode_matrix(codecs.encode_matrix(spec)), spec)

    def test_matrix_flags_must_match_grids(self):
        spec = {"width": 1, "height": 1, "name": "a", "headers": None, "altitudes": None,
                "landData": [[0]], "sectionFlags": [2, 0]}
        with self.assertRaises(codecs.FormatError):
            codecs.encode_matrix(spec)

    def test_out_of_range_fields_are_format_errors(self):
        warp = {"x": -1, "z": 0, "header": 33, "anchor": 0, "y": 0}
        with self.assertRaises(codecs.FormatError):
            codecs.encode_events({"bgs": [], "objects": [], "warps": [warp], "coords": []})
        tiles = _blank_tiles()
        tiles["behavior"][0] = "-1 " + " ".join(["00"] * 31)
        with self.assertRaises(codecs.FormatError):
            codecs.encode_tiles(tiles)

    def test_bdhc_references_checked(self):
        bdhc = {"points": [[0, 0], [1, 1]], "normals": [[0, 4096, 0]], "constants": [0],
                "plates": [[0, 1, 0, 0]], "strips": [[0, 1, 0]], "access": [0]}
        self.assertEqual(codecs.decode_bdhc(codecs.encode_bdhc(bdhc)), bdhc)
        for key, bad in (("plates", [[0, 2, 0, 0]]), ("access", [1]), ("strips", [[0, 2, 0]]),
                         ("strips", [[5, 1, 0], [0, 0, 0]])):
            with self.subTest(key=key), self.assertRaises(codecs.FormatError):
                codecs.encode_bdhc({**bdhc, key: bad})

    def test_background_sound_alignment(self):
        bdhc = {"points": [], "normals": [], "constants": [], "plates": [], "strips": [], "access": []}
        land = {"backgroundSound": "01", "tiles": _blank_tiles(), "buildings": [], "bdhc": bdhc}
        with self.assertRaises(codecs.FormatError):
            codecs.encode_land(land, b"BMD0")

    def test_header_bitfield_overflow(self):
        spec = dict.fromkeys(("wildEncounterBank", "areaDataBank", "moveModelBank", "worldMapX",
                              "worldMapY", "matrixId", "scriptsBank", "scriptHeaderBank", "msgBank",
                              "dayMusicId", "nightMusicId", "eventsBank", "mapsec", "areaIcon",
                              "momCallIntroParam"), 0)
        spec.update({name: 0 for name, _ in codecs._HEADER_FLAG_BITS})
        self.assertEqual(codecs.decode_header(codecs.encode_header(spec)), spec)
        spec["battleBg"] = 32
        with self.assertRaises(codecs.FormatError):
            codecs.encode_header(spec)


@unittest.skipUnless(HAVE_BASE, "base/root not unpacked")
class VanillaRoundTrip(unittest.TestCase):
    def test_roundtrip_command_passes(self):
        self.assertEqual(cli.main(["roundtrip"]), 0)

    def test_extract_edit_pack(self):
        """Edit one land tile through the spec tree; only that byte changes."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir, out_dir = Path(tmp) / "spec", Path(tmp) / "out"
            self.assertEqual(cli.main(["extract", "--out", str(spec_dir)]), 0)
            land_path = spec_dir / "land/0003/land.json"
            land = json.loads(land_path.read_text())
            row = land["tiles"]["collision"][0]
            land["tiles"]["collision"][0] = ("." if row[0] == "#" else "#") + row[1:]
            land_path.write_text(json.dumps(land))
            self.assertEqual(cli.main(["pack", "--spec", str(spec_dir), "--out", str(out_dir)]), 0)

            before = narc.read_members(ROOT / "a/0/6/5")
            after = narc.read_members(out_dir / "a/0/6/5")
            changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
            self.assertEqual(changed, [3])
            diff = [i for i, (a, b) in enumerate(zip(before[3], after[3])) if a != b]
            self.assertEqual(len(diff), 1)
            for rel in ("a/0/4/1", "a/0/4/2", "a/0/3/2"):
                self.assertEqual((out_dir / rel).read_bytes(), (ROOT / rel).read_bytes(), rel)

    def test_pack_rejects_dangling_reference_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir, out_dir = Path(tmp) / "spec", Path(tmp) / "out"
            cli.main(["extract", "--out", str(spec_dir)])
            last = sorted((spec_dir / "events").glob("*.json"))[-1]
            last.unlink()  # some header still points at this events bank
            self.assertEqual(cli.main(["pack", "--spec", str(spec_dir), "--out", str(out_dir)]), 1)
            self.assertFalse(out_dir.exists())


if __name__ == "__main__":
    unittest.main()
