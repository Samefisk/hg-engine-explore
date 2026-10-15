"""Tests for tools.maps.  Run: python3 -B -m unittest tools.maps.test_codecs"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from . import cli, codecs, lint, narc, world

ROM = cli.REPO / "rom.nds"
HAVE_BASE = ROM.exists()


def _base_world():
    return world.load_base(world.RomSource(ROM))


def _vanilla(rel: str) -> bytes:
    return world.RomSource(ROM).read(rel)


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

    def test_game_buffer_limits(self):
        bdhc = {"points": [], "normals": [], "constants": [], "plates": [], "strips": [], "access": []}
        land = {"backgroundSound": "", "tiles": _blank_tiles(), "buildings": [], "bdhc": bdhc}
        codecs.encode_land(land, b"BMD0")
        with self.subTest("background sound"), self.assertRaises(codecs.FormatError):
            codecs.encode_land({**land, "backgroundSound": "00" * (codecs.BGS_MAX_BYTES + 4)}, b"BMD0")
        building = dict.fromkeys(codecs._BUILDING_FIELDS, 0)
        with self.subTest("buildings"), self.assertRaises(codecs.FormatError):
            codecs.encode_land({**land, "buildings": [building] * (codecs.MAX_BUILDINGS + 1)}, b"BMD0")
        with self.subTest("model"), self.assertRaises(codecs.FormatError):
            codecs.encode_land(land, b"\0" * (codecs.MODEL_MAX_BYTES + 4))
        points = [[0, 0]] * (codecs.BDHC_MAX_BYTES // 8 + 1)
        with self.subTest("bdhc"), self.assertRaises(codecs.FormatError):
            codecs.encode_bdhc({**bdhc, "points": points})

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


@unittest.skipUnless(HAVE_BASE, "rom.nds not present")
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

            before = narc.members(_vanilla("a/0/6/5"))
            after = narc.read_members(out_dir / "a/0/6/5")
            changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
            self.assertEqual(changed, [3])
            diff = [i for i, (a, b) in enumerate(zip(before[3], after[3])) if a != b]
            self.assertEqual(len(diff), 1)
            for rel in ("a/0/4/1", "a/0/4/2", "a/0/3/2"):
                self.assertEqual((out_dir / rel).read_bytes(), _vanilla(rel), rel)

    def test_pack_rejects_dangling_reference_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir, out_dir = Path(tmp) / "spec", Path(tmp) / "out"
            cli.main(["extract", "--out", str(spec_dir)])
            last = sorted((spec_dir / "events").glob("*.json"))[-1]
            last.unlink()  # some header still points at this events bank
            self.assertEqual(cli.main(["pack", "--spec", str(spec_dir), "--out", str(out_dir)]), 1)
            self.assertFalse(out_dir.exists())


@unittest.skipUnless(HAVE_BASE, "rom.nds not present")
class OverrideWorkflow(unittest.TestCase):
    def run_cli(self, overrides: Path, *argv: str) -> int:
        return cli.main(["--overrides", str(overrides), *argv])

    def test_checkout_apply_is_identity_and_lint_catches_new_defects(self):
        with tempfile.TemporaryDirectory() as tmp:
            overrides, out = Path(tmp) / "ov", Path(tmp) / "out"
            self.assertEqual(self.run_cli(overrides, "checkout", "--map", "33",
                                          "--parts", "events,land,header"), 0)
            self.assertEqual(self.run_cli(overrides, "lint"), 0)
            self.assertEqual(self.run_cli(overrides, "apply", "--out", str(out)), 0)
            for rel in ("a/0/3/2", "a/0/6/5"):
                self.assertEqual((out / "root" / rel).read_bytes(), _vanilla(rel), rel)
            self.assertEqual((out / "arm9.bin").read_bytes(), world.RomSource(ROM).arm9())

            events_path = overrides / "events/0030.json"
            events = json.loads(events_path.read_text())
            events["warps"][0]["anchor"] = 9          # Route 29 gate has 2 warps
            events["objects"][0]["x"] = 10_000         # far outside the matrix
            events_path.write_text(json.dumps(events))
            edited = world.apply_overrides(_base_world(), overrides)
            result = lint.lint(edited, _base_world())
            kinds = sorted(message.rsplit("[", 1)[1].split(":")[0] for message in result[lint.ERROR])
            self.assertEqual(kinds, ["outside-land", "warp-anchor"], result)
            self.assertEqual(self.run_cli(overrides, "apply", "--out", str(Path(tmp) / "out2")), 1)
            self.assertFalse((Path(tmp) / "out2").exists())

            # A waiver with a reason unblocks exactly the listed finding.
            keys = [message.rsplit("[", 1)[1].rstrip("]") for message in result[lint.ERROR]]
            (overrides / lint.WAIVER_FILE).write_text(json.dumps(
                {"waivers": [{"key": key, "reason": "test"} for key in keys]}))
            self.assertEqual(self.run_cli(overrides, "lint"), 0)

    def test_dynamic_and_shared_return_warps_do_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            overrides = Path(tmp)
            self.assertEqual(self.run_cli(overrides, "checkout", "--map", "33", "--parts", "events"), 0)
            events_path = overrides / "events/0030.json"
            events = json.loads(events_path.read_text())
            events["warps"].append({"x": 624, "z": 396, "header": lint.DYNAMIC_WARP_HEADER, "anchor": 256, "y": 0})
            events["warps"].append({"x": 625, "z": 396, "header": 60, "anchor": 0, "y": 0})  # New Bark: not back here
            events_path.write_text(json.dumps(events))
            result = lint.lint(world.apply_overrides(_base_world(), overrides), _base_world())
            self.assertEqual(result[lint.ERROR], [])
            self.assertEqual(len(result[lint.WARNING]), 1, result)

    def test_checkout_refuses_shared_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            overrides = Path(tmp)
            # Unused map 148 shares event bank 0 and its land with other maps.
            self.assertEqual(self.run_cli(overrides, "checkout", "--map", "148", "--parts", "events"), 1)
            self.assertFalse((overrides / "events").exists())
            self.assertEqual(self.run_cli(overrides, "checkout", "--map", "148", "--parts", "events", "--shared"), 0)
            self.assertEqual(self.run_cli(overrides, "checkout", "--map", "9999"), 1)

    def test_apply_in_place_on_build_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, arm9, overrides = Path(tmp) / "root", Path(tmp) / "arm9.bin", Path(tmp) / "ov"
            source = world.RomSource(ROM)
            for rel in (*world.ARCHIVE_PATHS.values(), world.NAMES_PATH):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_bytes(source.read(rel))
            arm9.write_bytes(source.arm9())
            build_args = ["--root", str(root), "--arm9", str(arm9), "--overrides", str(overrides)]
            self.assertEqual(cli.main([*build_args, "apply", "--in-place"]), 0)  # no overrides: no-op
            self.assertEqual(self.run_cli(overrides, "checkout", "--map", "33", "--parts", "header"), 0)
            header_path = overrides / "headers/0033.json"
            header = json.loads(header_path.read_text())
            header["weather"] = 1
            header_path.write_text(json.dumps(header))
            self.assertEqual(cli.main([*build_args, "apply", "--in-place"]), 0)
            patched = world.load_base(world.DirSource(root, arm9))
            self.assertEqual(patched.headers[33]["weather"], 1)
            self.assertEqual(patched.headers[34], _base_world().headers[34])
            self.assertEqual((root / world.NAMES_PATH).read_bytes(), source.read(world.NAMES_PATH))
            self.assertEqual((root / "a/0/6/5").read_bytes(), source.read("a/0/6/5"))

    def test_unreachable_and_bad_script_references_are_errors(self):
        from . import reach
        base = world.load_base(world.RomSource(ROM), repo=cli.REPO)
        grid, seen = reach.reachable_by_matrix(base)[0]
        matrix = base.matrix_for(42)
        cells = [(x, z) for z, row in enumerate(matrix["headers"]) for x, h in enumerate(row) if h == 42]
        sealed = next((x, z) for cx, cz in cells for z in range(cz * 32, cz * 32 + 32)
                      for x in range(cx * 32, cx * 32 + 32)
                      if base.tile(42, x, z) and not reach.near_reachable(grid, seen, x, z))
        with tempfile.TemporaryDirectory() as tmp:
            overrides = Path(tmp)
            self.assertEqual(self.run_cli(overrides, "checkout", "--map", "42", "--parts", "events"), 0)
            self.assertEqual(self.run_cli(overrides, "checkout", "--map", "33", "--parts", "events,header"), 0)
            route38 = next(p for p in (overrides / "events").glob("*.json") if p.name != "0030.json")
            events = json.loads(route38.read_text())
            events["bgs"].append({"scriptId": 0, "type": 0, "x": sealed[0], "z": sealed[1], "y": 0, "dir": 0})
            route38.write_text(json.dumps(events))
            route29 = overrides / "events/0030.json"
            events = json.loads(route29.read_text())
            available = base.script_entries[base.headers[33]["scriptsBank"]]
            events["objects"][0]["scriptId"] = available + 1
            route29.write_text(json.dumps(events))
            header = json.loads((overrides / "headers/0033.json").read_text())
            header["msgBank"] = base.archive_counts["text"]
            (overrides / "headers/0033.json").write_text(json.dumps(header))
            result = lint.lint(world.apply_overrides(base, overrides), base)
            kinds = sorted(m.rsplit("[", 1)[1].split(":")[0] for m in result[lint.ERROR])
            self.assertEqual(kinds, ["header-ref", "script-ref", "unreachable"], result)

    def test_vanilla_local_script_references_all_resolve(self):
        base = world.load_base(world.RomSource(ROM), repo=cli.REPO)
        self.assertEqual(base.script_ranges[-1][0], 2000)
        found = lint.findings(base)
        self.assertFalse([k for k in found if k[0] in ("script-ref", "header-ref", "matrix-land")])

    def test_new_map_id_writes_extension_file(self):
        from . import header_table
        with tempfile.TemporaryDirectory() as tmp:
            overrides, out = Path(tmp) / "ov", Path(tmp) / "out"
            self.assertEqual(self.run_cli(overrides, "checkout", "--map", "540", "--parts", "header"), 0)
            path = overrides / "headers/0540.json"
            header = json.loads(path.read_text())
            route29 = _base_world().headers[33]
            header.update({k: v for k, v in route29.items() if k not in ("id", "name")})
            header["name"] = "NEW540"
            header["weather"] = 1
            path.write_text(json.dumps(header))
            self.assertEqual(self.run_cli(overrides, "apply", "--out", str(out)), 0)
            blob = (out / header_table.EXT_FILE_NAME).read_bytes()
            self.assertEqual(len(blob), codecs.HEADER_SIZE)
            self.assertEqual(codecs.decode_header(blob)["weather"], 1)
            self.assertEqual(codecs.decode_header(blob)["matrixId"], route29["matrixId"])
            names = (out / "root" / world.NAMES_PATH).read_bytes()
            self.assertEqual(names[540 * 16:541 * 16].rstrip(b"\0"), b"NEW540")
            rock = narc.members((out / "root" / header_table.MAP_INDEXED_NARCS["rock smash"]).read_bytes())
            self.assertEqual(len(rock), header_table.configured_count())
            # The vanilla table rows are untouched.
            self.assertEqual((out / "arm9.bin").read_bytes(), world.RomSource(ROM).arm9())

    def test_append_must_be_contiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            overrides = Path(tmp)
            (overrides / "area").mkdir()
            spec = codecs.decode_area(narc.members(_vanilla("a/0/4/2"))[0])
            (overrides / "area/9999.json").write_text(json.dumps(spec))
            with self.assertRaises(codecs.FormatError):
                world.apply_overrides(_base_world(), overrides)


if __name__ == "__main__":
    unittest.main()
