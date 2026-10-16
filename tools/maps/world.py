"""Decoded map data: the base ROM files plus a sparse override tree.

The override tree (data/maps/ by default) holds only edited members, in the
same layout `extract` writes:

  headers/NNNN.json          one full map header entry (id = NNNN)
  matrix/NNNN.json, area/NNNN.json, events/NNNN.json
  land/NNNN/land.json        land.json; model.nsbmd is optional and falls
                             back to the base model of the same member

A member index may also append to an archive (index == current count).
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path

import ndspy.rom

from . import codecs, header_table, narc

ARCHIVE_PATHS = {"matrix": "a/0/4/1", "area": "a/0/4/2", "events": "a/0/3/2", "land": "a/0/6/5"}
NAMES_PATH = "fielddata/maptable/mapname.bin"
SCRIPT_ARCHIVE, TEXT_ARCHIVE = "a/0/1/2", "a/0/2/7"
_DECODERS = {"matrix": codecs.decode_matrix, "area": codecs.decode_area, "events": codecs.decode_events}
_ENCODERS = {"matrix": codecs.encode_matrix, "area": codecs.encode_area, "events": codecs.encode_events}


class DirSource:
    """An unpacked filesystem plus arm9.bin, as the build's base/ directory.

    Between builds base/ holds the *patched* output, so agent commands read
    the pristine rom.nds instead (RomSource); the build passes base/ itself.
    """

    def __init__(self, root: Path, arm9: Path):
        self.root, self.arm9_path = root, arm9

    def read(self, rel: str) -> bytes:
        return (self.root / rel).read_bytes()

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def arm9(self) -> bytes:
        return self.arm9_path.read_bytes()

    def __str__(self) -> str:
        return str(self.root)


class RomSource:
    """Files and decompressed ARM9 read straight from an .nds image."""

    def __init__(self, path: Path):
        self.path = path
        self.rom = ndspy.rom.NintendoDSRom.fromFile(str(path))

    def read(self, rel: str) -> bytes:
        return self.rom.getFileByName(rel)

    def exists(self, rel: str) -> bool:
        return self.rom.filenames.idOf(rel) is not None

    def arm9(self) -> bytes:
        return self.rom.loadArm9().save(compress=False)

    def __str__(self) -> str:
        return str(self.path)


@dataclass
class World:
    raw: dict[str, list[bytes]]          # encoded members per archive kind
    headers: list[dict]
    archive_counts: dict[str, int] = field(default_factory=dict)  # scripts/text
    script_entries: list = field(default_factory=list)  # per scr_seq bank; None = unknown
    script_ranges: list = field(default_factory=list)   # [(first script id, bank)], descending
    overridden: dict[str, set[int]] = field(default_factory=dict)
    # Land texture animation material names per a/1/4/0 member (AreaData field 3,
    # "dynamicTextureType" in the area codec). Bound to land models by material index.
    land_anims: list = field(default_factory=list)
    _cache: dict = field(default_factory=dict)

    def member(self, kind: str, index: int):
        key = (kind, index)
        if key not in self._cache:
            data = self.raw[kind][index]
            self._cache[key] = codecs.decode_land(data)[0] if kind == "land" else _DECODERS[kind](data)
        return self._cache[key]

    def matrix_for(self, map_id: int) -> dict:
        return self.member("matrix", self.headers[map_id]["matrixId"])

    def tile(self, map_id: int, x: int, z: int) -> tuple[bool, int] | None:
        """(blocked, behavior) at matrix-wide tile x/z, or None if outside land."""
        matrix = self.matrix_for(map_id)
        cx, cz = x // codecs.TILE_GRID, z // codecs.TILE_GRID
        if not (0 <= cx < matrix["width"] and 0 <= cz < matrix["height"]):
            return None
        land_id = matrix["landData"][cz][cx]
        if land_id == 0xFFFF or land_id >= len(self.raw["land"]):
            return None
        tiles = self.member("land", land_id)["tiles"]
        lx, lz = x % codecs.TILE_GRID, z % codecs.TILE_GRID
        blocked = tiles["collision"][lz][lx] == "#"
        behavior = int(tiles["behavior"][lz].split()[lx], 16)
        return blocked, behavior


# sScriptBankMapping (pokeheartgold src/fieldmap.c): 30 x {u16 firstId, scriptBank,
# msgBank}, descending. Found by its {10300, 734, 444} entry, the sixth.
SCRIPT_RANGE_COUNT = 30
_SCRIPT_RANGE_PROBE = struct.pack("<HHH", 10300, 734, 444)
SCRIPT_END_MARKER = 0xFD13


def script_count(data: bytes) -> int:
    """Entries in a scr_seq file: u32 offsets until the 0xFD13 end marker."""
    count = 0
    while 4 * count + 2 <= len(data) and struct.unpack_from("<H", data, 4 * count)[0] != SCRIPT_END_MARKER:
        count += 1
    return count


def script_ranges(arm9: bytes) -> list:
    at = arm9.find(_SCRIPT_RANGE_PROBE)
    if at < 0 or arm9.count(_SCRIPT_RANGE_PROBE) != 1:
        return []
    start = at - 5 * 6
    ranges = [struct.unpack_from("<HHH", arm9, start + 6 * k)[:2] for k in range(SCRIPT_RANGE_COUNT)]
    firsts = [first for first, _ in ranges]
    return ranges if firsts == sorted(firsts, reverse=True) else []


def apply_repo_banks(world: "World", repo: Path) -> None:
    """Account for banks the hg-engine build adds or replaces later.

    data/text/NNN.txt replaces or appends text banks; armips/scr_seq/
    scr_seq_NNNNN_*.s replaces script banks (their entry counts are unknown
    until assembled, so they are not checked).
    """
    text_ids = [int(p.stem) for p in (repo / "data/text").glob("*.txt") if p.stem.isdigit()]
    if text_ids and "text" in world.archive_counts:
        world.archive_counts["text"] = max(world.archive_counts["text"], max(text_ids) + 1)
    for path in (repo / "armips/scr_seq").glob("scr_seq_*.s"):
        bank = int(path.name.split("_")[2])
        while len(world.script_entries) <= bank:
            world.script_entries.append(None)
        world.script_entries[bank] = None
        world.archive_counts["scripts"] = max(world.archive_counts.get("scripts", 0), bank + 1)


LAND_ANIM_ARCHIVE = "a/1/4/0"


def load_base(source, header_offset: int = codecs.HEADER_TABLE_OFFSET_USA, repo: Path | None = None) -> World:
    raw = {kind: narc.members(source.read(rel)) for kind, rel in ARCHIVE_PATHS.items()}
    arm9 = source.arm9()
    if header_offset == codecs.HEADER_TABLE_OFFSET_USA:
        # IDs 540+ come from the expansion patch; unpatched ROMs show them as
        # MAP_NOTHING aliases ("alias": 1) up to the configured count.
        headers = header_table.logical_headers(arm9, source.read(NAMES_PATH))
    else:
        headers = codecs.decode_header_table(arm9, source.read(NAMES_PATH), header_offset)
    counts, entries = {}, []
    if source.exists(SCRIPT_ARCHIVE):
        scripts = narc.members(source.read(SCRIPT_ARCHIVE))
        counts["scripts"] = len(scripts)
        entries = [script_count(data) for data in scripts]
    if source.exists(TEXT_ARCHIVE):
        counts["text"] = len(narc.members(source.read(TEXT_ARCHIVE)))
    anims = []
    if source.exists(LAND_ANIM_ARCHIVE):
        from .style.kit import area_animation_materials
        anims = [area_animation_materials(source, i) for i in range(len(narc.members(source.read(LAND_ANIM_ARCHIVE))))]
    world = World(raw=raw, headers=headers, archive_counts=counts,
                  script_entries=entries, script_ranges=script_ranges(arm9), land_anims=anims)
    if repo is not None:
        apply_repo_banks(world, repo)
    return world


def _index(path: Path) -> int:
    stem = path.name if path.is_dir() else path.stem
    if not (len(stem) == 4 and stem.isdigit()):
        raise codecs.FormatError(f"{path}: override names must be 4-digit member numbers")
    return int(stem)


def apply_overrides(base: World, overrides: Path) -> World:
    """Return a new World with the override tree applied (base is untouched)."""
    raw = {kind: list(members) for kind, members in base.raw.items()}
    headers = [dict(entry) for entry in base.headers]
    overridden: dict[str, set[int]] = {kind: set() for kind in (*ARCHIVE_PATHS, "headers")}
    if not overrides.exists():
        return World(raw=raw, headers=headers, archive_counts=dict(base.archive_counts),
                     script_entries=list(base.script_entries), script_ranges=list(base.script_ranges),
                     overridden=overridden, land_anims=base.land_anims)

    for kind in ARCHIVE_PATHS:
        folder = overrides / kind
        if not folder.exists():
            continue
        paths = sorted(p for p in folder.iterdir() if (p.is_dir() if kind == "land" else p.suffix == ".json"))
        for path in paths:
            index = _index(path)
            try:
                if kind == "land":
                    spec = json.loads((path / "land.json").read_text())
                    model_path = path / "model.nsbmd"
                    if model_path.exists():
                        model = model_path.read_bytes()
                    elif index < len(base.raw["land"]):
                        model = codecs.decode_land_model(base.raw["land"][index])
                    else:
                        raise codecs.FormatError("new land member needs model.nsbmd")
                    data = codecs.encode_land(spec, model)
                else:
                    data = _ENCODERS[kind](json.loads(path.read_text()))
            except (codecs.FormatError, KeyError, ValueError, OSError) as error:
                raise codecs.FormatError(f"{path.relative_to(overrides)}: {error}") from None
            if index < len(raw[kind]):
                raw[kind][index] = data
            elif index == len(raw[kind]):
                raw[kind].append(data)
            else:
                raise codecs.FormatError(f"{path.relative_to(overrides)}: appends must be contiguous "
                                         f"({kind} has {len(raw[kind])} members)")
            overridden[kind].add(index)

    header_dir = overrides / "headers"
    if header_dir.exists():
        for path in sorted(header_dir.glob("*.json")):
            index = _index(path)
            try:
                entry = json.loads(path.read_text())
            except ValueError as error:
                raise codecs.FormatError(f"headers/{path.name}: {error}") from None
            if index >= len(headers):
                raise codecs.FormatError(f"headers/{path.name}: map IDs end at {len(headers) - 1} "
                                         "(MAP_HEADER_COUNT in armips/asm/map_header_expansion.s)")
            if index >= header_table.VANILLA_COUNT + header_table.MAX_DEFINED:
                raise codecs.FormatError(f"headers/{path.name}: only IDs below "
                                         f"{header_table.VANILLA_COUNT + header_table.MAX_DEFINED} can be stored")
            entry.pop("alias", None)
            entry["id"] = index
            try:
                codecs.encode_header(entry)
                codecs.encode_names([entry])
            except KeyError as error:
                raise codecs.FormatError(f"headers/{path.name}: missing field {error}") from None
            except codecs.FormatError as error:
                raise codecs.FormatError(f"headers/{path.name}: {error}") from None
            headers[index] = entry
            overridden["headers"].add(index)
    return World(raw=raw, headers=headers, archive_counts=dict(base.archive_counts),
                     script_entries=list(base.script_entries), script_ranges=list(base.script_ranges),
                     overridden=overridden, land_anims=base.land_anims)
