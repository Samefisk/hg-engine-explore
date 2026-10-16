"""Binary <-> spec codecs for HeartGold map data.

Each codec pair satisfies encode(decode(b)) == b for every vanilla member, and
the decoded spec is plain JSON data (dicts, lists, ints, strings). Layouts are
documented in documentation/map-system/formats.md.
"""

from __future__ import annotations

import struct

TILE_GRID = 32
HEADER_SIZE = 24
HEADER_TABLE_OFFSET_USA = 0xF6BE0
HEADER_COUNT = 540
BGS_SIGNATURE = 0x1234


class FormatError(ValueError):
    pass


def _pack(fmt: str, *values) -> bytes:
    """struct.pack that reports out-of-range fields as FormatError."""
    try:
        return struct.pack(fmt, *values)
    except struct.error as error:
        raise FormatError(f"value out of range for {fmt}: {values} ({error})") from None


def _rows(values: list, width: int) -> list[list]:
    return [values[i:i + width] for i in range(0, len(values), width)]


def _flat(rows: list[list]) -> list:
    return [v for row in rows for v in row]


# --- Map header (ARM9 table entry, 24 bytes) --------------------------------

# (name, bits) from LSB for the u32 flag word; see pokeheartgold MapHeader.
_HEADER_FLAG_BITS = (
    ("regionNo", 1), ("weather", 7), ("mapType", 4), ("cameraType", 6),
    ("followMode", 2), ("battleBg", 5), ("bikeAllowed", 1),
    ("runningAllowed_Unused", 1), ("escapeRopeAllowed", 1), ("flyAllowed", 1),
    ("outgoingCalls", 1), ("incomingCalls", 1), ("radioSignal", 1),
)


def _unpack_bits(value: int, fields) -> dict:
    out, shift = {}, 0
    for name, bits in fields:
        out[name] = (value >> shift) & ((1 << bits) - 1)
        shift += bits
    return out


def _pack_bits(spec: dict, fields) -> int:
    value, shift = 0, 0
    for name, bits in fields:
        field = spec[name]
        if not 0 <= field < (1 << bits):
            raise FormatError(f"{name}={field} does not fit in {bits} bits")
        value |= field << shift
        shift += bits
    return value


def decode_header(data: bytes) -> dict:
    if len(data) != HEADER_SIZE:
        raise FormatError(f"map header must be {HEADER_SIZE} bytes, got {len(data)}")
    (wild, area, packed_mm, matrix, scripts, script_header, msg, day, night,
     events, packed_sec, flags) = struct.unpack("<BBHHHHHHHHHI", data)
    spec = {
        "wildEncounterBank": wild,
        "areaDataBank": area,
        **_unpack_bits(packed_mm, (("moveModelBank", 4), ("worldMapX", 6), ("worldMapY", 6))),
        "matrixId": matrix,
        "scriptsBank": scripts,
        "scriptHeaderBank": script_header,
        "msgBank": msg,
        "dayMusicId": day,
        "nightMusicId": night,
        "eventsBank": events,
        **_unpack_bits(packed_sec, (("mapsec", 8), ("areaIcon", 4), ("momCallIntroParam", 4))),
    }
    spec.update(_unpack_bits(flags, _HEADER_FLAG_BITS))
    return spec


def encode_header(spec: dict) -> bytes:
    return _pack(
        "<BBHHHHHHHHHI",
        spec["wildEncounterBank"], spec["areaDataBank"],
        _pack_bits(spec, (("moveModelBank", 4), ("worldMapX", 6), ("worldMapY", 6))),
        spec["matrixId"], spec["scriptsBank"], spec["scriptHeaderBank"],
        spec["msgBank"], spec["dayMusicId"], spec["nightMusicId"], spec["eventsBank"],
        _pack_bits(spec, (("mapsec", 8), ("areaIcon", 4), ("momCallIntroParam", 4))),
        _pack_bits(spec, _HEADER_FLAG_BITS),
    )


def decode_header_table(arm9: bytes, names: bytes,
                        offset: int = HEADER_TABLE_OFFSET_USA) -> list[dict]:
    count = len(names) // 16
    table = []
    for map_id in range(count):
        start = offset + map_id * HEADER_SIZE
        entry = {"id": map_id, "name": names[map_id * 16:(map_id + 1) * 16].rstrip(b"\0").decode("latin-1")}
        entry.update(decode_header(arm9[start:start + HEADER_SIZE]))
        table.append(entry)
    return table


def encode_names(table: list[dict]) -> bytes:
    out = bytearray()
    for entry in table:
        raw = entry["name"].encode("latin-1")
        if len(raw) > 16:
            raise FormatError(f"map {entry['id']} name longer than 16 bytes")
        out += raw.ljust(16, b"\0")
    return bytes(out)


def encode_header_table(table: list[dict]) -> bytes:
    return b"".join(encode_header(entry) for entry in table)


# --- Map matrix (a/0/4/1) ---------------------------------------------------

def decode_matrix(data: bytes) -> dict:
    width, height, has_headers, has_altitudes, name_len = data[:5]
    pos = 5
    name = data[pos:pos + name_len].decode("latin-1")
    pos += name_len
    cells = width * height
    spec = {"width": width, "height": height, "name": name, "headers": None, "altitudes": None}
    if has_headers:
        spec["headers"] = _rows(list(struct.unpack_from(f"<{cells}H", data, pos)), width)
        pos += cells * 2
    if has_altitudes:
        spec["altitudes"] = _rows(list(data[pos:pos + cells]), width)
        pos += cells
    spec["landData"] = _rows(list(struct.unpack_from(f"<{cells}H", data, pos)), width)
    pos += cells * 2
    if pos != len(data):
        spec["trailing"] = data[pos:].hex()
    # Flags other than 0/1 would not survive a boolean view.
    if has_headers > 1 or has_altitudes > 1:
        spec["sectionFlags"] = [has_headers, has_altitudes]
    return spec


def encode_matrix(spec: dict) -> bytes:
    width, height = spec["width"], spec["height"]
    name = spec["name"].encode("latin-1")
    if len(name) > 16:
        raise FormatError("matrix name longer than 16 bytes")
    if width * height > 799:
        raise FormatError(f"matrix has {width * height} cells; the game limit is 799")
    if not (0 < width < 256 and 0 < height < 256):
        raise FormatError(f"matrix size {width}x{height} must be 1..255 per side")
    present = [int(spec["headers"] is not None), int(spec["altitudes"] is not None)]
    flags = spec.get("sectionFlags") or present
    if [int(bool(flag)) for flag in flags] != present:
        raise FormatError(f"sectionFlags {flags} disagree with which grids are present {present}")
    out = bytearray([width, height, flags[0], flags[1], len(name)]) + name
    for key in ("headers", "altitudes", "landData"):
        grid = spec[key]
        if grid is None:
            continue
        if len(grid) != height or any(len(row) != width for row in grid):
            raise FormatError(f"matrix {key} grid is not {width}x{height}")
        values = _flat(grid)
        out += _pack(f"<{len(values)}{'B' if key == 'altitudes' else 'H'}", *values)
    out += bytes.fromhex(spec.get("trailing", ""))
    return bytes(out)


# --- Area data (a/0/4/2) ----------------------------------------------------

def decode_area(data: bytes) -> dict:
    if len(data) != 8:
        raise FormatError(f"area data must be 8 bytes, got {len(data)}")
    buildings, textures, dynamic, area_type, light = struct.unpack("<HHHBB", data)
    return {"buildingsTileset": buildings, "mapTileset": textures,
            "dynamicTextureType": dynamic, "areaType": area_type, "lightType": light}


def encode_area(spec: dict) -> bytes:
    return _pack("<HHHBB", spec["buildingsTileset"], spec["mapTileset"],
                       spec["dynamicTextureType"], spec["areaType"], spec["lightType"])


# --- Zone events (a/0/3/2) --------------------------------------------------

_EVENT_LAYOUTS = (
    # dir is a u16 followed by two padding bytes (struct alignment).
    ("bgs", "<HHiiiHH", ("scriptId", "type", "x", "z", "y", "dir", "dirPadding")),
    ("objects", "<HHHHHHhHHHhhHHi",
     ("id", "spriteId", "movement", "type", "eventFlag", "scriptId", "facingDirection",
      "param0", "param1", "param2", "xRange", "yRange", "x", "z", "y")),
    ("warps", "<HHHHI", ("x", "z", "header", "anchor", "y")),
    ("coords", "<HhhHHHHH", ("scriptId", "x", "z", "w", "h", "y", "val", "var")),
)
EVENT_FILE_LIMIT = 0x800  # MapEvents.event_data; the loader requires size < limit


def decode_events(data: bytes) -> dict:
    spec, pos = {}, 0
    for key, fmt, names in _EVENT_LAYOUTS:
        (count,) = struct.unpack_from("<I", data, pos)
        pos += 4
        size = struct.calcsize(fmt)
        spec[key] = [dict(zip(names, struct.unpack_from(fmt, data, pos + i * size))) for i in range(count)]
        pos += count * size
    if pos != len(data):
        spec["trailing"] = data[pos:].hex()
    return spec


def encode_events(spec: dict) -> bytes:
    out = bytearray()
    for key, fmt, names in _EVENT_LAYOUTS:
        items = spec.get(key, [])
        out += struct.pack("<I", len(items))
        for item in items:
            out += _pack(fmt, *(item.get(name, 0) if name == "dirPadding" else item[name] for name in names))
    out += bytes.fromhex(spec.get("trailing", ""))
    if len(out) >= EVENT_FILE_LIMIT:
        raise FormatError(f"event file is {len(out)} bytes; the game requires < {EVENT_FILE_LIMIT}")
    return bytes(out)


# --- Land data (a/0/6/5) ----------------------------------------------------

_BUILDING_FIELDS = ("modelId", "x", "y", "z", "rotX", "rotY", "rotZ",
                    "scaleX", "scaleY", "scaleZ", "unused0", "unused1")
_BUILDING_FORMAT = "<I" + "i" * 11
_BUILDING_SIZE = struct.calcsize(_BUILDING_FORMAT)  # 48

# Field loader buffers (src/field/map_load_manager.c, map_load_buffers.c,
# bdhc.c, map_prop_manager.c in the full decompilation under .codex-reference/):
BGS_MAX_BYTES = 0x200     # LoadedMap.soundplates.data
MAX_BUILDINGS = 32        # MAP_PROP_MAX
MODEL_MAX_BYTES = 0xF000  # MAP_LOAD_PRIMARY_BUFFER_SIZE, the model's buffer
BDHC_MAX_BYTES = 0x9000   # BDHC_BUFFER_SIZE: the six arrays after the 16-byte header


def decode_tiles(data: bytes) -> dict:
    values = struct.unpack(f"<{TILE_GRID * TILE_GRID}H", data)
    collision, behavior, secondary = [], [], []
    for row in _rows(list(values), TILE_GRID):
        collision.append("".join("#" if v & 0x8000 else "." for v in row))
        behavior.append(" ".join(f"{v & 0xFF:02x}" for v in row))
        secondary.append(" ".join(f"{(v >> 8) & 0x7F:02x}" for v in row))
    return {"collision": collision, "behavior": behavior, "secondary": secondary}


def encode_tiles(spec: dict) -> bytes:
    layers = (spec["collision"], spec["behavior"], spec["secondary"])
    if any(len(layer) != TILE_GRID for layer in layers):
        raise FormatError("tile layers must have 32 rows")
    values = []
    for coll_row, beh_row, sec_row in zip(*layers):
        behaviors = [int(v, 16) for v in beh_row.split()]
        secondaries = [int(v, 16) for v in sec_row.split()]
        if len(coll_row) != TILE_GRID or len(behaviors) != TILE_GRID or len(secondaries) != TILE_GRID:
            raise FormatError("tile rows must have 32 columns")
        for coll, beh, sec in zip(coll_row, behaviors, secondaries):
            if coll not in "#." or not 0 <= beh <= 0xFF or not 0 <= sec <= 0x7F:
                raise FormatError(f"invalid tile ({coll!r}, {beh:#x}, {sec:#x})")
            values.append(beh | (sec << 8) | (0x8000 if coll == "#" else 0))
    return struct.pack(f"<{len(values)}H", *values)


_BDHC_ARRAYS = (
    ("points", "<ii"), ("normals", "<iii"), ("constants", "<i"),
    ("plates", "<HHHH"), ("strips", "<iHH"), ("access", "<H"),
)


def decode_bdhc(data: bytes) -> dict:
    if data[:4] != b"BDHC":
        raise FormatError("BDHC magic missing")
    counts = struct.unpack_from("<6H", data, 4)
    spec, pos = {}, 16
    for (key, fmt), count in zip(_BDHC_ARRAYS, counts):
        size = struct.calcsize(fmt)
        items = [list(struct.unpack_from(fmt, data, pos + i * size)) for i in range(count)]
        spec[key] = [item[0] for item in items] if len(fmt) == 2 else items
        pos += count * size
    if pos != len(data):
        spec["trailing"] = data[pos:].hex()
    return spec


def validate_bdhc(spec: dict) -> None:
    """Reference and ordering rules every vanilla BDHC satisfies."""
    counts = {key: len(spec[key]) for key, _ in _BDHC_ARRAYS}
    if any(count > 0xFFFF for count in counts.values()):
        raise FormatError("BDHC array longer than 65535 entries")
    for index, (p1, p2, normal, constant) in enumerate(spec["plates"]):
        if p1 >= counts["points"] or p2 >= counts["points"] or normal >= counts["normals"] \
                or constant >= counts["constants"]:
            raise FormatError(f"BDHC plate {index} references a missing point, normal or constant")
    scanlines = [strip[0] for strip in spec["strips"]]
    if scanlines != sorted(scanlines):
        raise FormatError("BDHC strips must be sorted by scanline")
    for index, (_, count, start) in enumerate(spec["strips"]):
        if start + count > counts["access"]:
            raise FormatError(f"BDHC strip {index} runs past the access list")
    if any(not 0 <= plate < counts["plates"] for plate in spec["access"]):
        raise FormatError("BDHC access list references a missing plate")


def encode_bdhc(spec: dict) -> bytes:
    validate_bdhc(spec)
    arrays = sum(len(spec[key]) * struct.calcsize(fmt) for key, fmt in _BDHC_ARRAYS)
    if arrays > BDHC_MAX_BYTES:
        raise FormatError(f"BDHC arrays are {arrays} bytes; the game's buffer holds {BDHC_MAX_BYTES:#x}")
    out = bytearray(b"BDHC")
    out += struct.pack("<6H", *(len(spec[key]) for key, _ in _BDHC_ARRAYS))
    for key, fmt in _BDHC_ARRAYS:
        for item in spec[key]:
            out += _pack(fmt, *(item if isinstance(item, list) else [item]))
    out += bytes.fromhex(spec.get("trailing", ""))
    return bytes(out)


def decode_land(data: bytes) -> tuple[dict, bytes]:
    """Return (spec, nsbmd). The model stays a binary sidecar."""
    tiles_size, buildings_size, model_size, bdhc_size = struct.unpack_from("<4I", data)
    signature, bgs_size = struct.unpack_from("<HH", data, 16)
    if signature != BGS_SIGNATURE:
        raise FormatError(f"background-sound signature {signature:#x} != {BGS_SIGNATURE:#x}")
    pos = 20
    bgs = data[pos:pos + bgs_size]
    pos += bgs_size
    sections = []
    for size in (tiles_size, buildings_size, model_size, bdhc_size):
        sections.append(data[pos:pos + size])
        pos += size
    if pos != len(data) or tiles_size != TILE_GRID * TILE_GRID * 2 or buildings_size % _BUILDING_SIZE:
        raise FormatError("land data section sizes do not match the file")
    tiles, buildings, model, bdhc = sections
    spec = {
        "backgroundSound": bgs.hex(),
        "tiles": decode_tiles(tiles),
        "buildings": [dict(zip(_BUILDING_FIELDS, struct.unpack_from(_BUILDING_FORMAT, buildings, i)))
                      for i in range(0, len(buildings), _BUILDING_SIZE)],
        "bdhc": decode_bdhc(bdhc),
    }
    return spec, model


def decode_land_model(data: bytes) -> bytes:
    return decode_land(data)[1]


def encode_land(spec: dict, model: bytes) -> bytes:
    bgs = bytes.fromhex(spec["backgroundSound"])
    if len(bgs) % 4 or len(bgs) > BGS_MAX_BYTES:
        raise FormatError(f"background-sound block is {len(bgs)} bytes; it must be a multiple of 4 "
                          f"(model alignment) and at most {BGS_MAX_BYTES:#x} (the game's buffer)")
    if len(spec["buildings"]) > MAX_BUILDINGS:
        raise FormatError(f"{len(spec['buildings'])} buildings; the game loads at most {MAX_BUILDINGS} per chunk")
    if len(model) > MODEL_MAX_BYTES:
        raise FormatError(f"model is {len(model)} bytes; the game's model buffer holds {MODEL_MAX_BYTES:#x}")
    tiles = encode_tiles(spec["tiles"])
    buildings = b"".join(_pack(_BUILDING_FORMAT, *(b[f] for f in _BUILDING_FIELDS))
                         for b in spec["buildings"])
    bdhc = encode_bdhc(spec["bdhc"])
    return (struct.pack("<4I", len(tiles), len(buildings), len(model), len(bdhc))
            + struct.pack("<HH", BGS_SIGNATURE, len(bgs)) + bgs
            + tiles + buildings + model + bdhc)
