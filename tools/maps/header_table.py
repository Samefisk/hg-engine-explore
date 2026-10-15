"""Expanded map header table: locate, read, write and verify map IDs 540+.

The patch is armips/asm/map_header_expansion.s; the design and every patched
address are in documentation/map-system/header-expansion.md.

The 540 vanilla rows stay at 0x020F6BE0. The stock bounds check at 0x0203B268
now jumps to a routine that returns a *row* for the getters to read at
0x020F6BE0 + row * 24:

  id < 540                     row = id
  540 <= id < 540 + defined    row = an extension slot (blocks B, then A)
  540 + defined <= id < count  row = 1 (MAP_NOTHING header, as before)
  id >= count                  GF_AssertFail, row = 1

Build flow: tools.maps writes the extension headers (IDs 540, 541, ...
contiguous) to base/map_header_ext.bin before armips; armips places them.

  python3 -B -m tools.maps.header_table verify --arm9 base/arm9.bin --root base/root
  python3 -B -m tools.maps.header_table show --arm9 base/arm9.bin
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from . import codecs

REPO = Path(__file__).resolve().parents[2]
PATCH_SOURCE = REPO / "armips/asm/map_header_expansion.s"
EXT_FILE_NAME = "map_header_ext.bin"  # next to base/arm9.bin

ARM9_BASE = 0x02000000
HEADER_SIZE = codecs.HEADER_SIZE
TABLE = ARM9_BASE + codecs.HEADER_TABLE_OFFSET_USA  # 0x020F6BE0
VANILLA_COUNT = 540
MAP_NOTHING = 1

BOUNDS_CHECK = 0x0203B268          # static MapNumberBoundsCheck, 20 bytes
BOUNDS_CHECK_END = 0x0203B27C      # first getter
GETTERS_END = 0x0203B540           # end of the last table getter
GF_ASSERT_FAIL = 0x0202551C
MARKINGS_SITE = 0x0202F376         # MapMarkingsSave_MapIDisValid: movs r0,#N/4
TALK_OVERLAY = 101
TALK_OVERLAY_BASE = 0x021E7740
TALK_SITE = 0x021F707C             # Pokemon Talk landmark loop: movs r0,#N/4

B_BASE, B_LIMIT, B_SLOTS = 0x020FFC10, 0x020FFE2B, 20   # dead stock icon-palette table
A_TOP, A_FLOOR, A_MAX_SLOTS = 0x020FF460, 0x020FF134, 32  # dead gSpeciesToOWNum tail
ROUTINE = B_BASE + B_SLOTS * HEADER_SIZE                  # 0x020FFDF0
ROUTINE_SIZE = 56
MAX_DEFINED = B_SLOTS + A_MAX_SLOTS                       # 52
MIN_COUNT, MAX_COUNT = VANILLA_COUNT + 4, VANILLA_COUNT + 252

# The 27 MapHeader_* getters keep their stock literal (table + field offset).
GETTER_LITERALS = {
    0x0203B28C: 0x1, 0x0203B2A8: 0x0, 0x0203B2BC: 0x4, 0x0203B2D0: 0xA,
    0x0203B2E4: 0x6, 0x0203B2F8: 0x8, 0x0203B30C: 0xC, 0x0203B320: 0xE,
    0x0203B340: 0x0, 0x0203B354: 0x0, 0x0203B368: 0x10, 0x0203B384: 0x0,
    0x0203B3A4: 0x0, 0x0203B3C4: 0x0, 0x0203B3E0: 0x0, 0x0203B3FC: 0x0,
    0x0203B418: 0x0, 0x0203B434: 0x0, 0x0203B450: 0x0, 0x0203B46C: 0x0,
    0x0203B488: 0x0, 0x0203B4A4: 0x0, 0x0203B4C0: 0x0, 0x0203B4D8: 0x0,
    0x0203B4F4: 0x0, 0x0203B514: 0x0, 0x0203B53C: 0x0,
}
GETTER_CALLS = 27

# Per-map NARCs read with the raw map ID as member index (no bounds check).
# Hook stubs (Thumb `ldr rN,[pc]; bx rN`) over the stock readers of the reused
# blocks. GetBattleMonIconPaletteEx (0x0207440C) is NOT hooked and still reads
# icon-palette bytes 0x020FFE2C..0x020FFE2F, so B_LIMIT must stay <= 0x020FFE2B.
RETIRED_READER_STUBS = (
    (0x02074364, bytes.fromhex("004b1847"), "GetMonIconPaletteEx (block B)"),
    (0x0206A304, bytes.fromhex("00490847"), "sModelIndexLUT reader (block A)"),
)
MAP_INDEXED_NARCS = {"headbutt": "a/2/5/2", "rock smash": "a/2/5/3"}
NAMES_PATH = "fielddata/maptable/mapname.bin"


class ExpansionError(ValueError):
    pass


# --- Thumb encoding ----------------------------------------------------------

def _h(*values: int) -> bytes:
    return struct.pack(f"<{len(values)}H", *values)


def thumb_bl(source: int, target: int) -> bytes:
    offset = target - (source + 4)
    if offset & 1 or not -(1 << 22) <= offset < (1 << 22):
        raise ExpansionError(f"bl 0x{target:08X} out of range from 0x{source:08X}")
    offset &= (1 << 23) - 1
    return _h(0xF000 | (offset >> 12), 0xF800 | ((offset >> 1) & 0x7FF))


def _bl_target(code: bytes, source: int) -> int | None:
    hi, lo = struct.unpack_from("<HH", code)
    if hi & 0xF800 != 0xF000 or lo & 0xF800 != 0xF800:
        return None
    offset = ((hi & 0x7FF) << 12) | ((lo & 0x7FF) << 1)
    if offset & (1 << 22):
        offset -= 1 << 23
    return source + 4 + offset


def stub_bytes() -> bytes:
    """0x0203B268: ldr r1,=routine|1; bx r1; pool; zero fill to the first getter."""
    stub = _h(0x4900, 0x4708) + struct.pack("<I", ROUTINE | 1)
    return stub.ljust(BOUNDS_CHECK_END - BOUNDS_CHECK, b"\0")


def routine_bytes(count: int, defined: int, b_defined: int, b_row: int, a_row: int) -> bytes:
    """The bounds check at ROUTINE, byte-identical to the armips output."""
    code = _h(
        0x2187, 0x0089,            # movs r1,#0x87; lsls r1,r1,#2   (540)
        0x1A42, 0xD306,            # subs r2,r0,r1; bcc vanilla
        0x2A00 | b_defined, 0xD305,  # cmp r2,#bDefined; blo slotB
        0x2A00 | defined, 0xD306,    # cmp r2,#defined; blo slotA
        0x2A00 | (count - VANILLA_COUNT), 0xD207,  # cmp r2,#count-540; bhs invalid
        0x2001, 0x4770,            # movs r0,#1; vanilla: bx lr
        0x4805, 0x1880, 0x4770,    # slotB: ldr r0,=bRow; adds r0,r0,r2; bx lr
        0x4805, 0x1880, 0x4770,    # slotA: ldr r0,=aRow; adds r0,r0,r2; bx lr
        0xB508,                    # invalid: push {r3,lr}
    )
    code += thumb_bl(ROUTINE + len(code), GF_ASSERT_FAIL)
    code += _h(0x2001, 0xBD08, 0x0000)  # movs r0,#1; pop {r3,pc}; pool alignment
    code += struct.pack("<II", b_row & 0xFFFFFFFF, a_row & 0xFFFFFFFF)
    assert len(code) == ROUTINE_SIZE
    return code


# --- Layout ------------------------------------------------------------------

@dataclass(frozen=True)
class Layout:
    count: int          # logical map IDs 0..count-1
    defined: int        # extension headers stored: IDs 540..540+defined-1
    b_defined: int
    b_row: int
    a_row: int

    @property
    def a_defined(self) -> int:
        return self.defined - self.b_defined

    @property
    def a_base(self) -> int:
        return A_TOP - self.a_defined * HEADER_SIZE

    @classmethod
    def plan(cls, count: int, defined: int) -> "Layout":
        if count % 4 or not MIN_COUNT <= count <= MAX_COUNT:
            raise ExpansionError(f"count {count} must be a multiple of 4 in {MIN_COUNT}..{MAX_COUNT}")
        if not 0 <= defined <= min(count - VANILLA_COUNT, MAX_DEFINED):
            raise ExpansionError(f"{defined} extension headers: at most "
                                 f"{min(count - VANILLA_COUNT, MAX_DEFINED)} fit")
        b_defined = min(defined, B_SLOTS)
        a_base = A_TOP - (defined - b_defined) * HEADER_SIZE
        return cls(count, defined, b_defined, (B_BASE - TABLE) // HEADER_SIZE,
                   (a_base - TABLE) // HEADER_SIZE - b_defined)

    def row(self, map_id: int) -> int:
        """The row the getters read for map_id (mirrors the routine)."""
        if map_id < VANILLA_COUNT:
            return map_id
        index = map_id - VANILLA_COUNT
        if index < self.b_defined:
            return self.b_row + index
        if index < self.defined:
            return self.a_row + index
        if index < self.count - VANILLA_COUNT:
            return MAP_NOTHING
        raise ExpansionError(f"map {map_id} is outside the {self.count}-entry table")

    def address(self, map_id: int) -> int:
        return TABLE + self.row(map_id) * HEADER_SIZE

    def file_offset(self, map_id: int) -> int:
        return self.address(map_id) - ARM9_BASE

    def is_stored(self, map_id: int) -> bool:
        """True when map_id has its own row (vanilla or an extension slot)."""
        return 0 <= map_id < VANILLA_COUNT + self.defined


def configured_count(source: Path = PATCH_SOURCE) -> int:
    match = re.search(r"(?m)^MAP_HEADER_COUNT\s+equ\s+(\d+)", source.read_text())
    if not match:
        raise ExpansionError(f"{source}: no MAP_HEADER_COUNT")
    return int(match.group(1))


def locate(arm9: bytes) -> Layout | None:
    """Layout of a patched arm9.bin; None for a stock (unpatched) table."""
    def at(address: int, size: int) -> bytes:
        return bytes(arm9[address - ARM9_BASE:address - ARM9_BASE + size])

    stub = at(BOUNDS_CHECK, BOUNDS_CHECK_END - BOUNDS_CHECK)
    if stub[:2] == _h(0xB508):
        return None
    if stub != stub_bytes():
        raise ExpansionError("bounds check at 0x0203B268 is neither stock nor the expansion stub")
    code = at(ROUTINE, ROUTINE_SIZE)
    b_defined, defined, span = code[8], code[12], code[16]
    b_row, a_row = struct.unpack_from("<II", code, 48)
    layout = Layout(VANILLA_COUNT + span, defined, b_defined, b_row, a_row)
    try:
        expected = Layout.plan(layout.count, defined)
    except ExpansionError as error:
        raise ExpansionError(f"expansion routine fields are invalid: {error}") from None
    if expected != layout:
        raise ExpansionError(f"expansion routine rows {layout} differ from the planned {expected}")
    if code != routine_bytes(layout.count, defined, b_defined, b_row, a_row):
        raise ExpansionError("expansion routine at 0x020FFDF0 differs from its template")
    return layout


def read_entry(arm9: bytes, map_id: int, layout: Layout | None = None) -> bytes:
    layout = layout or locate(arm9) or _stock_layout()
    start = layout.file_offset(map_id)
    return bytes(arm9[start:start + HEADER_SIZE])


def write_entry(arm9: bytearray, map_id: int, data: bytes, layout: Layout | None = None) -> None:
    """Patch one stored header in a built arm9 (post-armips edit)."""
    layout = layout or locate(arm9) or _stock_layout()
    if len(data) != HEADER_SIZE:
        raise ExpansionError(f"map header must be {HEADER_SIZE} bytes")
    if not layout.is_stored(map_id):
        raise ExpansionError(f"map {map_id} has no stored row (only 0..{VANILLA_COUNT + layout.defined - 1})")
    start = layout.file_offset(map_id)
    arm9[start:start + HEADER_SIZE] = data


def _stock_layout() -> Layout:
    return Layout(VANILLA_COUNT, 0, 0, 0, 0)


def logical_headers(arm9: bytes, names: bytes = b"", count: int | None = None) -> list[dict]:
    """Decoded headers 0..count-1, as codecs.decode_header_table entries.

    Works on a stock arm9 (rows 540+ are MAP_NOTHING placeholders, count from
    the patch source) and on a patched one (count from the routine). Entries
    without their own row carry "alias": 1.
    """
    layout = locate(arm9)
    if count is None:
        count = layout.count if layout else configured_count()
    stored = VANILLA_COUNT + (layout.defined if layout else 0)
    table = []
    for map_id in range(count):
        if map_id < stored:
            data = read_entry(arm9, map_id, layout or _stock_layout())
        else:
            data = read_entry(arm9, MAP_NOTHING, layout or _stock_layout())
        raw_name = names[map_id * 16:(map_id + 1) * 16]
        entry = {"id": map_id, "name": raw_name.rstrip(b"\0").decode("latin-1")}
        entry.update(codecs.decode_header(data))
        if map_id >= stored:
            entry["alias"] = MAP_NOTHING
        table.append(entry)
    return table


# --- Build inputs ------------------------------------------------------------

def extension_blob(headers: dict[int, bytes], nothing: bytes) -> bytes:
    """base/map_header_ext.bin: rows for IDs 540..max(headers), gaps = MAP_NOTHING copy."""
    ids = [i for i in headers if i >= VANILLA_COUNT]
    if not ids:
        return b""
    out = bytearray()
    for map_id in range(VANILLA_COUNT, max(ids) + 1):
        data = headers.get(map_id, nothing)
        if len(data) != HEADER_SIZE:
            raise ExpansionError(f"map {map_id} header must be {HEADER_SIZE} bytes")
        out += data
    if len(out) // HEADER_SIZE > MAX_DEFINED:
        raise ExpansionError(f"{len(out) // HEADER_SIZE} extension headers; the slots hold {MAX_DEFINED}")
    return bytes(out)


def write_extension_file(arm9_path: Path, headers: dict[int, bytes], nothing: bytes) -> Path:
    """Write (or remove when empty) the armips input next to arm9_path."""
    path = arm9_path.parent / EXT_FILE_NAME
    blob = extension_blob(headers, nothing)
    if blob:
        path.write_bytes(blob)
    elif path.exists():
        path.unlink()
    return path


def pad_narc(data: bytes, count: int, filler: bytes) -> bytes:
    """Append filler members until a per-map NARC has count members."""
    from . import narc
    members = narc.members(data)
    if len(members) >= count:
        return data
    return narc.build(members + [filler] * (count - len(members)))


# --- Reference patch (armips mirror, used by tests) ----------------------------

def apply_reference_patch(arm9: bytearray, count: int, blob: bytes = b"",
                          overarm9: bytes | None = None, overlay101: bytearray | None = None) -> Layout:
    """Apply the same bytes armips/asm/map_header_expansion.s writes."""
    if len(blob) % HEADER_SIZE:
        raise ExpansionError("extension blob is not whole headers")
    layout = Layout.plan(count, len(blob) // HEADER_SIZE)

    def put(address: int, data: bytes) -> None:
        arm9[address - ARM9_BASE:address - ARM9_BASE + len(data)] = data

    put(BOUNDS_CHECK, stub_bytes())
    split = layout.b_defined * HEADER_SIZE
    put(B_BASE, blob[:split].ljust(B_SLOTS * HEADER_SIZE, b"\0"))
    put(ROUTINE, routine_bytes(count, layout.defined, layout.b_defined, layout.b_row, layout.a_row))
    if layout.a_defined:
        put(layout.a_base, blob[split:])
    put(MARKINGS_SITE, bytes([count >> 2]))
    if overarm9 is not None and overlay101 is not None and not _compressed(overarm9, TALK_OVERLAY):
        start = TALK_SITE - TALK_OVERLAY_BASE
        overlay101[start:start + 1] = bytes([count >> 2])
    return layout


def _compressed(overarm9: bytes, overlay: int) -> bool:
    return bool(struct.unpack_from("<I", overarm9, overlay * 0x20 + 0x1C)[0] & 0x01000000)


# --- Verification ------------------------------------------------------------

def verify(arm9: bytes, root: Path | None = None, overarm9: bytes | None = None,
           overlay101: bytes | None = None, expected_count: int | None = None) -> tuple[list[str], list[str]]:
    """Static checks of a built arm9 (and filesystem). Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    def word(address: int) -> int:
        return struct.unpack_from("<I", arm9, address - ARM9_BASE)[0]

    try:
        layout = locate(arm9)
    except ExpansionError as error:
        return [str(error)], warnings
    if layout is None:
        return ["bounds check at 0x0203B268 is stock: the expansion patch is not applied"], warnings
    if expected_count is not None and layout.count != expected_count:
        errors.append(f"table has {layout.count} IDs; the patch source configures {expected_count}")

    calls = 0
    for source in range(BOUNDS_CHECK_END, GETTERS_END, 2):
        if _bl_target(arm9[source - ARM9_BASE:source - ARM9_BASE + 4], source) == BOUNDS_CHECK:
            calls += 1
    if calls != GETTER_CALLS:
        errors.append(f"{calls} getters call the bounds check; expected {GETTER_CALLS}")
    for site, field in GETTER_LITERALS.items():
        if word(site) != TABLE + field:
            errors.append(f"getter literal 0x{site:08X} is 0x{word(site):08X}, not table+0x{field:X}")

    # The stock readers of both slot blocks must stay replaced by hg-engine hooks;
    # make.py skips a hook whose symbol is missing, which would let them read
    # map headers as icon palettes / overworld numbers.
    for address, stub, reader in RETIRED_READER_STUBS:
        if bytes(arm9[address - ARM9_BASE:address - ARM9_BASE + len(stub)]) != stub:
            errors.append(f"{reader} at 0x{address:08X} is not hooked; its table holds map headers now")

    if not (B_BASE <= ROUTINE and ROUTINE + ROUTINE_SIZE <= B_LIMIT):
        errors.append("bounds routine leaves slot block B")
    if layout.a_defined and layout.a_base < A_FLOOR:
        errors.append(f"slot block A starts at 0x{layout.a_base:08X}, inside the pokedex.s code")
    for map_id in range(layout.count):
        address = layout.address(map_id)
        inside = (TABLE <= address < TABLE + VANILLA_COUNT * HEADER_SIZE
                  or B_BASE <= address < B_BASE + layout.b_defined * HEADER_SIZE
                  or layout.a_base <= address < A_TOP)
        if not inside:
            errors.append(f"map {map_id} resolves to 0x{address:08X}, outside the table and slots")
            break
        try:
            codecs.decode_header(read_entry(arm9, map_id, layout))
        except codecs.FormatError as error:
            errors.append(f"map {map_id}: {error}")

    markings = arm9[MARKINGS_SITE - ARM9_BASE:MARKINGS_SITE - ARM9_BASE + 4]
    if markings != bytes([layout.count >> 2, 0x20, 0x80, 0x00]):
        errors.append(f"map-marking bound at 0x{MARKINGS_SITE:08X} is {markings.hex()}, "
                      f"not movs r0,#{layout.count >> 2}; lsls r0,#2")

    if overarm9 is not None and overlay101 is not None:
        start = TALK_SITE - TALK_OVERLAY_BASE
        talk = overlay101[start:start + 4] if not _compressed(overarm9, TALK_OVERLAY) else b""
        if not talk:
            warnings.append("overlay 101 is compressed: Pokemon Talk samples map IDs < 540 only")
        elif talk[0] != layout.count >> 2 or talk[1] != 0x20:
            errors.append(f"Pokemon Talk bound at 0x{TALK_SITE:08X} is {talk.hex()}")

    if root is not None:
        stored_end = VANILLA_COUNT + layout.defined
        from . import narc
        for label, rel in MAP_INDEXED_NARCS.items():
            path = root / rel
            if not path.exists():
                warnings.append(f"{label} archive {rel} is missing")
                continue
            members = len(narc.read_members(path))
            if members < stored_end:
                errors.append(f"{label} archive {rel} has {members} members; maps up to "
                              f"{stored_end - 1} read it by map ID (out of bounds)")
            elif members < layout.count:
                warnings.append(f"{label} archive {rel} has {members} members for {layout.count} IDs")
        names = root / NAMES_PATH
        if names.exists() and len(names.read_bytes()) // 16 < stored_end:
            warnings.append(f"{NAMES_PATH} names {len(names.read_bytes()) // 16} maps; "
                            f"tools need {stored_end} (the game never reads it)")
    return errors, warnings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.header_table", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("verify", "show"):
        command = sub.add_parser(name)
        command.add_argument("--arm9", type=Path, required=True, help="built base/arm9.bin")
        command.add_argument("--root", type=Path, help="built base/root (verify: per-map archives)")
        command.add_argument("--overarm9", type=Path, help="default: overarm9.bin next to --arm9")
        command.add_argument("--overlay101", type=Path, help="default: overlay/overlay_0101.bin next to --arm9")
    args = parser.parse_args(argv)
    arm9 = args.arm9.read_bytes()
    if args.command == "show":
        layout = locate(arm9)
        if layout is None:
            print(f"stock table: {VANILLA_COUNT} IDs at 0x{TABLE:08X}")
            return 0
        print(f"IDs 0..{layout.count - 1}; stored 0..{VANILLA_COUNT + layout.defined - 1}; "
              f"extension slots B {layout.b_defined}/{B_SLOTS} at 0x{B_BASE:08X}, "
              f"A {layout.a_defined}/{A_MAX_SLOTS} at 0x{layout.a_base:08X}; routine 0x{ROUTINE:08X}")
        for map_id in range(VANILLA_COUNT, VANILLA_COUNT + layout.defined):
            print(f"  map {map_id}: 0x{layout.address(map_id):08X} (arm9 +0x{layout.file_offset(map_id):X})")
        return 0
    base = args.arm9.parent
    overarm9_path = args.overarm9 or base / "overarm9.bin"
    overlay_path = args.overlay101 or base / "overlay/overlay_0101.bin"
    overarm9 = overarm9_path.read_bytes() if overarm9_path.exists() else None
    overlay101 = overlay_path.read_bytes() if overlay_path.exists() else None
    errors, warnings = verify(arm9, args.root, overarm9, overlay101, configured_count())
    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    if errors:
        return 1
    layout = locate(arm9)
    print(f"map header table OK: {layout.count} IDs, {VANILLA_COUNT + layout.defined} stored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
