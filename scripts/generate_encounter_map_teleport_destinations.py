#!/usr/bin/env python3
"""Generate vetted teleport destinations for every encounter-bearing map."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path

import ndspy.narc


CELL_SIZE = 32
HEADER_OFFSET = 0xF6BE0
HEADER_SIZE = 24
BAD_TILE_BEHAVIORS = {6, 16, 18, 21, 42}
FALLBACK_STAMPS = {
    "MAP_D24": "MAP_D24R0101",
    "MAP_D24R0201": "MAP_D24R0101",
}
VERIFIED_DESTINATIONS = {
    "MAP_R29": (592, 399),
    "MAP_R31": (560, 272),
    "MAP_T06": (1297, 295),
    "MAP_T21": (567, 400),
}
PACKED_MAP_BITS = 10
PACKED_X_BITS = 11
PACKED_Y_BITS = 10
PACKED_MAP_SHIFT = 0
PACKED_X_SHIFT = PACKED_MAP_SHIFT + PACKED_MAP_BITS
PACKED_Y_SHIFT = PACKED_X_SHIFT + PACKED_X_BITS
PACKED_MAP_LIMIT = 1 << PACKED_MAP_BITS
PACKED_X_LIMIT = 1 << PACKED_X_BITS
PACKED_Y_LIMIT = 1 << PACKED_Y_BITS
RUNTIME_RANDOM_RADIUS = 32
RUNTIME_RANDOM_MAX_OFFSET = RUNTIME_RANDOM_RADIUS - 1


@dataclass(frozen=True)
class MapHeader:
    wild_pokemon: int
    area_data_id: int
    matrix_id: int
    event_file_id: int


@dataclass(frozen=True)
class Stamp:
    matrix_id: int
    matrix_x: int
    matrix_y: int
    matrix_value: int
    land_file_id: int


@dataclass(frozen=True)
class Destination:
    symbol: str
    map_id: int
    data_id: int
    x: int
    y: int
    direction: int
    source: str
    matrix_id: int
    matrix_x: int
    matrix_y: int
    matrix_value: int
    land_file_id: int
    permission: int
    random_tiles: tuple[dict[str, int | str], ...] = ()


def read_define(source: str, name: str) -> int:
    match = re.search(rf"^#define\s+{re.escape(name)}\s+(\d+)\b", source, re.M)
    if not match:
        raise ValueError(f"missing define {name}")
    return int(match.group(1))


def read_map_constants(path: Path) -> dict[str, int]:
    constants: dict[str, int] = {}
    for line in path.read_text().splitlines():
        match = re.match(r"#define\s+(MAP_\w+)\s+(\d+)", line)
        if match:
            constants[match.group(1)] = int(match.group(2))
    return constants


def top_level_initializer_blocks(source: str, symbol: str) -> list[str]:
    start = source.index(symbol)
    equals = source.index("=", start)
    first = source.index("{", equals)
    blocks: list[str] = []
    depth = 0
    block_start: int | None = None
    for index in range(first, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
            if depth == 2:
                block_start = index + 1
        elif char == "}":
            if depth == 2 and block_start is not None:
                blocks.append(source[block_start:index])
                block_start = None
            depth -= 1
            if depth == 0:
                return blocks
    raise ValueError(f"unterminated initializer for {symbol}")


def read_authoritative_maps(
    source_path: Path,
    header_path: Path,
    maps: dict[str, int],
) -> list[tuple[str, int, int]]:
    header_source = header_path.read_text()
    expected_count = read_define(header_source, "OWED_ENCOUNTER_AREA_COUNT")
    source = source_path.read_text()
    blocks = top_level_initializer_blocks(source, "gOverworldWildEncounterLookupDataBlob")
    if len(blocks) < 3:
        raise ValueError("encounter lookup initializer is missing map/data arrays")

    symbols = re.findall(r"MAP_\w+", blocks[-2])
    data_ids = [int(value) for value in re.findall(r"\d+", blocks[-1])]
    if len(symbols) != expected_count or len(data_ids) != expected_count:
        raise ValueError(
            f"expected {expected_count} map/data entries, got {len(symbols)}/{len(data_ids)}"
        )
    if len(set(symbols)) != expected_count:
        raise ValueError("authoritative encounter map symbols are not unique")

    entries = []
    for symbol, data_id in zip(symbols, data_ids):
        if symbol not in maps:
            raise ValueError(f"unknown map symbol {symbol}")
        entries.append((symbol, maps[symbol], data_id))
    if len({map_id for _, map_id, _ in entries}) != expected_count:
        raise ValueError("authoritative encounter map ids are not unique")
    return entries


def read_matrix(matrix_narc: ndspy.narc.NARC, matrix_id: int) -> tuple[int, int, tuple[int, ...], tuple[int, ...]]:
    data = matrix_narc.files[matrix_id]
    width = data[0]
    height = data[1]
    name_len = data[4]
    offset = 5 + name_len
    cell_count = width * height
    values = struct.unpack_from(f"<{cell_count}H", data, offset)
    remaining = len(data) - offset
    if remaining == cell_count * 5:
        land_values = struct.unpack_from(f"<{cell_count}H", data, offset + cell_count * 3)
    elif remaining == cell_count * 2:
        land_values = values
    else:
        raise ValueError(f"matrix {matrix_id} has unexpected size layout")
    return width, height, values, land_values


def read_header(arm9: bytes, map_id: int) -> MapHeader:
    offset = HEADER_OFFSET + map_id * HEADER_SIZE
    if offset + HEADER_SIZE > len(arm9):
        raise ValueError(f"map {map_id} header is outside arm9.bin")
    record = arm9[offset : offset + HEADER_SIZE]
    return MapHeader(
        wild_pokemon=record[0],
        area_data_id=record[1],
        matrix_id=struct.unpack_from("<H", record, 4)[0],
        event_file_id=struct.unpack_from("<H", record, 0x10)[0],
    )


def read_permission_grid(land_narc: ndspy.narc.NARC, land_file_id: int) -> tuple[int, ...]:
    data = land_narc.files[land_file_id]
    permission_len = struct.unpack_from("<I", data, 0)[0]
    if permission_len != CELL_SIZE * CELL_SIZE * 2:
        raise ValueError(f"land file {land_file_id} has permission length {permission_len:#x}")
    return struct.unpack_from(f"<{CELL_SIZE * CELL_SIZE}H", data, 0x14)


def read_event_blocked_tiles(event_narc: ndspy.narc.NARC, event_file_id: int) -> set[tuple[int, int]]:
    if event_file_id >= len(event_narc.files):
        return set()
    data = event_narc.files[event_file_id]
    offset = 0
    blocked: set[tuple[int, int]] = set()
    try:
        count = struct.unpack_from("<I", data, offset)[0]
        offset += 4 + count * 0x14
        count = struct.unpack_from("<I", data, offset)[0]
        offset += 4 + count * 0x20
        count = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        for _ in range(count):
            x, y, _dest_header, _dest_anchor, _height = struct.unpack_from("<HHHHI", data, offset)
            offset += 0x0C
            blocked.add((x, y))
        count = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        for _ in range(count):
            x, y, width, height, _script = struct.unpack_from("<HHHHI", data, offset)
            offset += 0x10
            for tile_y in range(y, y + height):
                for tile_x in range(x, x + width):
                    blocked.add((tile_x, tile_y))
    except struct.error:
        return blocked
    return blocked


def is_passable(permission: int) -> bool:
    return (permission & 0x8000) == 0 and (permission & 0xFF) not in BAD_TILE_BEHAVIORS


def is_loaded_window_land_candidate(permission: int) -> bool:
    return (permission & 0xFF) not in BAD_TILE_BEHAVIORS


def find_stamps(
    matrix_narc: ndspy.narc.NARC,
    matrix_cache: dict[int, tuple[int, int, tuple[int, ...], tuple[int, ...]]],
    map_id: int,
    header: MapHeader,
    allow_header_wildcard: bool = True,
) -> list[Stamp]:
    matrix_ids = [header.matrix_id]
    matrix_ids.extend(index for index in range(len(matrix_narc.files)) if index != header.matrix_id)
    stamps: list[Stamp] = []
    for matrix_id in matrix_ids:
        if matrix_id not in matrix_cache:
            matrix_cache[matrix_id] = read_matrix(matrix_narc, matrix_id)
        width, _height, values, land_values = matrix_cache[matrix_id]
        for index, value in enumerate(values):
            if value == map_id:
                stamps.append(
                    Stamp(
                        matrix_id=matrix_id,
                        matrix_x=index % width,
                        matrix_y=index // width,
                        matrix_value=value,
                        land_file_id=land_values[index],
                    )
                )
    if stamps or header.matrix_id == 0 or not allow_header_wildcard:
        return stamps

    matrix_id = header.matrix_id
    if matrix_id not in matrix_cache:
        matrix_cache[matrix_id] = read_matrix(matrix_narc, matrix_id)
    width, _height, values, land_values = matrix_cache[matrix_id]
    for index, value in enumerate(values):
        stamps.append(
            Stamp(
                matrix_id=matrix_id,
                matrix_x=index % width,
                matrix_y=index // width,
                matrix_value=value,
                land_file_id=land_values[index],
            )
        )
    return stamps


def find_header_wildcard_stamps(
    matrix_narc: ndspy.narc.NARC,
    matrix_cache: dict[int, tuple[int, int, tuple[int, ...], tuple[int, ...]]],
    header: MapHeader,
) -> list[Stamp]:
    if header.matrix_id == 0:
        return []
    matrix_id = header.matrix_id
    if matrix_id not in matrix_cache:
        matrix_cache[matrix_id] = read_matrix(matrix_narc, matrix_id)
    width, _height, values, land_values = matrix_cache[matrix_id]
    return [
        Stamp(
            matrix_id=matrix_id,
            matrix_x=index % width,
            matrix_y=index // width,
            matrix_value=value,
            land_file_id=land_values[index],
        )
        for index, value in enumerate(values)
    ]


def candidate_dict(
    *,
    x: int,
    y: int,
    source: str,
    stamp: Stamp,
    permission: int,
) -> dict[str, int | str]:
    return {
        "x": x,
        "y": y,
        "source": source,
        "matrix_id": stamp.matrix_id,
        "matrix_x": stamp.matrix_x,
        "matrix_y": stamp.matrix_y,
        "matrix_value": stamp.matrix_value,
        "land_file_id": stamp.land_file_id,
        "permission": permission,
    }


def collect_land_candidates(
    *,
    source_map_id: int,
    source: str,
    matrix_narc: ndspy.narc.NARC,
    land_narc: ndspy.narc.NARC,
    event_narc: ndspy.narc.NARC,
    arm9: bytes,
    matrix_cache: dict[int, tuple[int, int, tuple[int, ...], tuple[int, ...]]],
    permission_cache: dict[int, tuple[int, ...]],
) -> list[tuple[int, int, int, int, int, int, int, int, int, Stamp, int, str]]:
    header = read_header(arm9, source_map_id)
    blocked = read_event_blocked_tiles(event_narc, header.event_file_id)
    candidates = []
    stamps = find_stamps(
        matrix_narc,
        matrix_cache,
        source_map_id,
        header,
        allow_header_wildcard=False,
    )

    def collect_candidates(candidate_stamps: list[Stamp], candidate_source: str) -> None:
        for stamp in candidate_stamps:
            if stamp.land_file_id >= len(land_narc.files):
                continue
            if stamp.land_file_id not in permission_cache:
                permission_cache[stamp.land_file_id] = read_permission_grid(land_narc, stamp.land_file_id)
            permissions = permission_cache[stamp.land_file_id]
            for local_y in range(CELL_SIZE):
                for local_x in range(CELL_SIZE):
                    world_x = stamp.matrix_x * CELL_SIZE + local_x
                    world_y = stamp.matrix_y * CELL_SIZE + local_y
                    if (world_x, world_y) in blocked:
                        continue
                    permission = permissions[local_y * CELL_SIZE + local_x]
                    if not is_passable(permission):
                        continue
                    neighbors = 0
                    center_distance = abs(local_x - 16) + abs(local_y - 16)
                    candidates.append(
                        (
                            -neighbors,
                            center_distance,
                            world_y,
                            world_x,
                            stamp.matrix_id,
                            stamp.matrix_x,
                            stamp.matrix_y,
                            stamp.land_file_id,
                            len(candidates),
                            stamp,
                            permission,
                            candidate_source,
                        )
                    )

    collect_candidates(stamps, "derived")
    if not candidates:
        collect_candidates(
            find_header_wildcard_stamps(matrix_narc, matrix_cache, header),
            "derived:header-wildcard",
        )
    return sorted(candidates)


def loaded_window_random_tile_candidates(
    *,
    center_x: int,
    center_y: int,
    loaded_map_id: int,
    fallback_map_id: int,
    source: str,
    matrix_narc: ndspy.narc.NARC,
    land_narc: ndspy.narc.NARC,
    event_narc: ndspy.narc.NARC,
    arm9: bytes,
    matrix_cache: dict[int, tuple[int, int, tuple[int, ...], tuple[int, ...]]],
    permission_cache: dict[int, tuple[int, ...]],
) -> tuple[dict[str, int | str], ...]:
    def collect_for_map(map_id: int, candidate_source: str) -> dict[tuple[int, int], dict[str, int | str]]:
        header = read_header(arm9, map_id)
        if header.matrix_id not in matrix_cache:
            matrix_cache[header.matrix_id] = read_matrix(matrix_narc, header.matrix_id)
        width, height, values, land_values = matrix_cache[header.matrix_id]
        blocked = read_event_blocked_tiles(event_narc, header.event_file_id)
        tiles: dict[tuple[int, int], dict[str, int | str]] = {}
        min_x = max(0, center_x - RUNTIME_RANDOM_RADIUS)
        min_y = max(0, center_y - RUNTIME_RANDOM_RADIUS)
        max_x = center_x + RUNTIME_RANDOM_MAX_OFFSET
        max_y = center_y + RUNTIME_RANDOM_MAX_OFFSET

        for y in range(min_y, max_y + 1):
            matrix_y = y // CELL_SIZE
            if matrix_y >= height:
                continue
            local_y = y % CELL_SIZE
            for x in range(min_x, max_x + 1):
                if x == center_x and y == center_y:
                    continue
                matrix_x = x // CELL_SIZE
                if matrix_x >= width or (x, y) in blocked:
                    continue
                cell_index = matrix_y * width + matrix_x
                land_file_id = land_values[cell_index]
                if land_file_id >= len(land_narc.files):
                    continue
                if land_file_id not in permission_cache:
                    permission_cache[land_file_id] = read_permission_grid(land_narc, land_file_id)
                permission = permission_cache[land_file_id][local_y * CELL_SIZE + (x % CELL_SIZE)]
                if not is_loaded_window_land_candidate(permission):
                    continue
                stamp = Stamp(
                    matrix_id=header.matrix_id,
                    matrix_x=matrix_x,
                    matrix_y=matrix_y,
                    matrix_value=values[cell_index],
                    land_file_id=land_file_id,
                )
                tiles[(x, y)] = candidate_dict(
                    x=x,
                    y=y,
                    source=candidate_source,
                    stamp=stamp,
                    permission=permission,
                )
        return tiles

    tiles = collect_for_map(loaded_map_id, f"{source}:loaded-window")
    if not tiles and fallback_map_id != loaded_map_id:
        tiles = collect_for_map(fallback_map_id, f"{source}:loaded-window-fallback")
    return tuple(tiles[key] for key in sorted(tiles))


def random_tile_evidence(random_tiles: tuple[dict[str, int | str], ...]) -> dict[str, object]:
    coordinates = sorted((int(tile["x"]), int(tile["y"])) for tile in random_tiles)
    digest = hashlib.sha256()
    for x, y in coordinates:
        digest.update(f"{x},{y}\n".encode("ascii"))
    evidence: dict[str, object] = {
        "count": len(coordinates),
        "sha256": digest.hexdigest(),
    }
    if coordinates:
        evidence["min_x"] = coordinates[0][0]
        evidence["max_x"] = max(x for x, _y in coordinates)
        evidence["min_y"] = min(y for _x, y in coordinates)
        evidence["max_y"] = max(y for _x, y in coordinates)
    return evidence


def choose_fixed_destination(
    *,
    symbol: str,
    map_id: int,
    data_id: int,
    source: str,
    source_map_id: int,
    x: int,
    y: int,
    matrix_narc: ndspy.narc.NARC,
    land_narc: ndspy.narc.NARC,
    event_narc: ndspy.narc.NARC,
    arm9: bytes,
    matrix_cache: dict[int, tuple[int, int, tuple[int, ...], tuple[int, ...]]],
    permission_cache: dict[int, tuple[int, ...]],
    random_candidates: list[tuple[int, int, int, int, int, int, int, int, int, Stamp, int, str]],
) -> Destination:
    header = read_header(arm9, source_map_id)
    blocked = read_event_blocked_tiles(event_narc, header.event_file_id)
    local_x = x % CELL_SIZE
    local_y = y % CELL_SIZE
    for stamp in find_stamps(matrix_narc, matrix_cache, source_map_id, header):
        if stamp.matrix_x != x // CELL_SIZE or stamp.matrix_y != y // CELL_SIZE:
            continue
        if stamp.land_file_id >= len(land_narc.files):
            break
        if stamp.land_file_id not in permission_cache:
            permission_cache[stamp.land_file_id] = read_permission_grid(land_narc, stamp.land_file_id)
        permission = permission_cache[stamp.land_file_id][local_y * CELL_SIZE + local_x]
        if (x, y) in blocked:
            raise RuntimeError(f"verified destination {symbol} {x},{y} is blocked by event data")
        random_tiles = loaded_window_random_tile_candidates(
            center_x=x,
            center_y=y,
            loaded_map_id=map_id,
            fallback_map_id=source_map_id,
            source=source,
            matrix_narc=matrix_narc,
            land_narc=land_narc,
            event_narc=event_narc,
            arm9=arm9,
            matrix_cache=matrix_cache,
            permission_cache=permission_cache,
        )
        return Destination(
            symbol=symbol,
            map_id=map_id,
            data_id=data_id,
            x=x,
            y=y,
            direction=1,
            source=source,
            matrix_id=stamp.matrix_id,
            matrix_x=stamp.matrix_x,
            matrix_y=stamp.matrix_y,
            matrix_value=stamp.matrix_value,
            land_file_id=stamp.land_file_id,
            permission=permission,
            random_tiles=random_tiles,
        )
    raise RuntimeError(f"verified destination {symbol} {x},{y} is outside source stamps")


def choose_destination(
    *,
    symbol: str,
    map_id: int,
    data_id: int,
    source: str,
    source_map_id: int,
    matrix_narc: ndspy.narc.NARC,
    land_narc: ndspy.narc.NARC,
    event_narc: ndspy.narc.NARC,
    arm9: bytes,
    matrix_cache: dict[int, tuple[int, int, tuple[int, ...], tuple[int, ...]]],
    permission_cache: dict[int, tuple[int, ...]],
    random_candidates: list[tuple[int, int, int, int, int, int, int, int, int, Stamp, int, str]],
) -> Destination | None:
    if not random_candidates:
        return None
    (
        _neighbors,
        _center,
        y,
        x,
        _matrix_id,
        _matrix_x,
        _matrix_y,
        _land_file_id,
        _candidate_index,
        stamp,
        permission,
        candidate_source,
    ) = random_candidates[0]
    random_tiles = loaded_window_random_tile_candidates(
        center_x=x,
        center_y=y,
        loaded_map_id=map_id,
        fallback_map_id=source_map_id,
        source=source,
        matrix_narc=matrix_narc,
        land_narc=land_narc,
        event_narc=event_narc,
        arm9=arm9,
        matrix_cache=matrix_cache,
        permission_cache=permission_cache,
    )
    return Destination(
        symbol=symbol,
        map_id=map_id,
        data_id=data_id,
        x=x,
        y=y,
        direction=1,
        source=source if candidate_source == "derived" else f"{source}:header-wildcard",
        matrix_id=stamp.matrix_id,
        matrix_x=stamp.matrix_x,
        matrix_y=stamp.matrix_y,
        matrix_value=stamp.matrix_value,
        land_file_id=stamp.land_file_id,
        permission=permission,
        random_tiles=random_tiles,
    )


def packed_destination_word(destination: Destination) -> int:
    if destination.direction != 1:
        raise ValueError(f"{destination.symbol} direction must stay implicit south")
    if not (0 <= destination.map_id < PACKED_MAP_LIMIT):
        raise ValueError(f"{destination.symbol} map id {destination.map_id} does not fit packed row")
    if not (0 <= destination.x < PACKED_X_LIMIT):
        raise ValueError(f"{destination.symbol} x {destination.x} does not fit packed row")
    if not (0 <= destination.y < PACKED_Y_LIMIT):
        raise ValueError(f"{destination.symbol} y {destination.y} does not fit packed row")
    return (
        (destination.map_id << PACKED_MAP_SHIFT)
        | (destination.x << PACKED_X_SHIFT)
        | (destination.y << PACKED_Y_SHIFT)
    )


def write_c(destinations: list[Destination], output: Path) -> None:
    lines = [
        '#include "../../include/map_teleport.h"',
        "",
        '#include "../../include/config.h"',
        '#include "../../include/constants/maps.h"',
        '#include "../../include/overworld_wild_behavior_data.h"',
        "",
        "#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS",
        "",
        "#define MAP_TELEPORT_ENCOUNTER_MAP_SHIFT 0",
        "#define MAP_TELEPORT_ENCOUNTER_MAP_MASK 0x000003FFu",
        "#define MAP_TELEPORT_ENCOUNTER_X_SHIFT 10",
            "#define MAP_TELEPORT_ENCOUNTER_X_MASK 0x000007FFu",
            "#define MAP_TELEPORT_ENCOUNTER_Y_SHIFT 21",
            "#define MAP_TELEPORT_ENCOUNTER_Y_MASK 0x000003FFu",
            "",
            "static const u32 sMapTeleportEncounterDestinations[OWED_ENCOUNTER_AREA_COUNT] = {",
        ]
    for destination in destinations:
        packed = packed_destination_word(destination)
        lines.append(
            f"    0x{packed:08X}u, // {destination.symbol} {destination.x},{destination.y}"
        )
    lines.extend(
        [
            "};",
            "",
            "BOOL MapTeleport_TrySelectEncounterDestinationByIndex(",
            "    u16 index,",
            "    MapTeleportDestination *destination)",
            "{",
            "    u32 packed;",
            "",
            "    if (destination == NULL || index >= OWED_ENCOUNTER_AREA_COUNT) {",
            "        return FALSE;",
            "    }",
            "",
            "    packed = sMapTeleportEncounterDestinations[index];",
            "    destination->mapId =",
            "        (u16)((packed >> MAP_TELEPORT_ENCOUNTER_MAP_SHIFT)",
            "            & MAP_TELEPORT_ENCOUNTER_MAP_MASK);",
            "    destination->x =",
            "        (u16)((packed >> MAP_TELEPORT_ENCOUNTER_X_SHIFT) & MAP_TELEPORT_ENCOUNTER_X_MASK);",
            "    destination->y =",
            "        (u16)((packed >> MAP_TELEPORT_ENCOUNTER_Y_SHIFT) & MAP_TELEPORT_ENCOUNTER_Y_MASK);",
            "    destination->direction = MAP_TELEPORT_DIRECTION_SOUTH;",
            "",
            "    return TRUE;",
            "}",
            "",
            "const MapTeleportEncounterDestinationEntry gMapTeleportEncounterDestinationEntry",
            '    __attribute__((section(".map_teleport_encounter_destination_entry"), used)) = {',
            "    MAP_TELEPORT_ENCOUNTER_DESTINATION_MAGIC,",
            "    MAP_TELEPORT_ENCOUNTER_DESTINATION_VERSION,",
            "    sizeof(MapTeleportEncounterDestinationEntry),",
            "    OWED_ENCOUNTER_AREA_COUNT,",
            "    0,",
            "};",
            "",
            "#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS",
            "",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def write_json(destinations: list[Destination], output: Path) -> None:
    def json_destination(destination: Destination) -> dict[str, object]:
        data = dict(destination.__dict__)
        data.pop("random_tiles")
        data["random_tile_evidence"] = random_tile_evidence(destination.random_tiles)
        data["random_tile_count"] = len(destination.random_tiles)
        return data

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "expected_count": len(destinations),
                "destinations": [json_destination(destination) for destination in destinations],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/OverworldWildEncounterLookupData.c"))
    parser.add_argument("--maps-header", type=Path, default=Path("include/constants/maps.h"))
    parser.add_argument("--data-header", type=Path, default=Path("include/overworld_wild_behavior_data.h"))
    parser.add_argument("--arm9", type=Path, default=Path("base/arm9.bin"))
    parser.add_argument("--matrix-narc", type=Path, default=Path("base/root/a/0/4/1"))
    parser.add_argument("--land-narc", type=Path, default=Path("base/root/a/0/6/5"))
    parser.add_argument("--event-narc", type=Path, default=Path("base/root/a/0/3/2"))
    parser.add_argument("--c-output", type=Path, default=Path("src/field/map_teleport_encounter_destinations.c"))
    parser.add_argument("--json-output", type=Path, default=Path("documentation/verification/encounter_map_teleport_destinations.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    maps = read_map_constants(args.maps_header)
    entries = read_authoritative_maps(args.source, args.data_header, maps)
    expected_count = read_define(args.data_header.read_text(), "OWED_ENCOUNTER_AREA_COUNT")
    if len(entries) != expected_count:
        raise ValueError(f"expected {expected_count} authoritative maps, got {len(entries)}")

    required_files = [args.arm9, args.matrix_narc, args.land_narc, args.event_narc]
    missing_files = [str(path) for path in required_files if not path.is_file()]
    if missing_files:
        raise FileNotFoundError(f"missing extracted ROM inputs: {', '.join(missing_files)}")

    arm9 = args.arm9.read_bytes()
    matrix_narc = ndspy.narc.NARC.fromFile(args.matrix_narc)
    land_narc = ndspy.narc.NARC.fromFile(args.land_narc)
    event_narc = ndspy.narc.NARC.fromFile(args.event_narc)
    matrix_cache: dict[int, tuple[int, int, tuple[int, ...], tuple[int, ...]]] = {}
    permission_cache: dict[int, tuple[int, ...]] = {}
    destinations: list[Destination] = []
    missing: list[str] = []

    for symbol, map_id, data_id in entries:
        source_symbol = FALLBACK_STAMPS.get(symbol, symbol)
        source_map_id = maps[source_symbol]
        source = "derived" if source_symbol == symbol else f"fallback:{source_symbol}"
        random_candidates = collect_land_candidates(
            source_map_id=source_map_id,
            source=source,
            matrix_narc=matrix_narc,
            land_narc=land_narc,
            event_narc=event_narc,
            arm9=arm9,
            matrix_cache=matrix_cache,
            permission_cache=permission_cache,
        )
        if symbol in VERIFIED_DESTINATIONS:
            x, y = VERIFIED_DESTINATIONS[symbol]
            destination = choose_fixed_destination(
                symbol=symbol,
                map_id=map_id,
                data_id=data_id,
                source=f"verified:{source}",
                source_map_id=source_map_id,
                x=x,
                y=y,
                matrix_narc=matrix_narc,
                land_narc=land_narc,
                event_narc=event_narc,
                arm9=arm9,
                matrix_cache=matrix_cache,
                permission_cache=permission_cache,
                random_candidates=random_candidates,
            )
        else:
            destination = choose_destination(
                symbol=symbol,
                map_id=map_id,
                data_id=data_id,
                source=source,
                source_map_id=source_map_id,
                matrix_narc=matrix_narc,
                land_narc=land_narc,
                event_narc=event_narc,
                arm9=arm9,
                matrix_cache=matrix_cache,
                permission_cache=permission_cache,
                random_candidates=random_candidates,
            )
        if destination is None:
            missing.append(symbol)
        else:
            destinations.append(destination)

    if missing:
        raise RuntimeError(f"no safe destination candidates for: {', '.join(missing)}")
    if len(destinations) != expected_count:
        raise RuntimeError(f"generated {len(destinations)} destinations, expected {expected_count}")

    write_c(destinations, args.c_output)
    write_json(destinations, args.json_output)
    print(
        json.dumps(
            {
                "expected_count": expected_count,
                "generated_count": len(destinations),
                "fallbacks": {
                    destination.symbol: destination.source
                    for destination in destinations
                    if destination.source.startswith("fallback:")
                },
                "random_tile_alternate_count": sum(
                    1 for destination in destinations if len(destination.random_tiles) > 1
                ),
                "random_tile_max_count": max(
                    len(destination.random_tiles) for destination in destinations
                ),
                "c_output": str(args.c_output),
                "json_output": str(args.json_output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
