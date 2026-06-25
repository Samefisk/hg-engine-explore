#!/usr/bin/env python3
"""Generate warp-backed teleport destinations for encounter-bearing maps."""

from __future__ import annotations

import argparse
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path

import ndspy.narc


HEADER_OFFSET = 0xF6BE0
HEADER_SIZE = 24
PACKED_MAP_BITS = 10
PACKED_WARP_BITS = 6
PACKED_MAP_SHIFT = 0
PACKED_WARP_SHIFT = PACKED_MAP_SHIFT + PACKED_MAP_BITS
PACKED_MAP_LIMIT = 1 << PACKED_MAP_BITS
PACKED_WARP_LIMIT = 1 << PACKED_WARP_BITS
WARP_ID_Y_SENTINEL = 0x03FF


@dataclass(frozen=True)
class MapHeader:
    wild_pokemon: int
    area_data_id: int
    matrix_id: int
    event_file_id: int


@dataclass(frozen=True)
class WarpEvent:
    index: int
    x: int
    y: int
    dest_header: int
    dest_anchor: int
    height: int


@dataclass(frozen=True)
class IncomingWarp:
    source_map_id: int
    source_event_file_id: int
    warp: WarpEvent


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
    event_file_id: int = -1
    warp_index: int = -1
    warp_dest_header: int = -1
    warp_dest_anchor: int = -1
    warp_height: int = 0
    source_map_id: int = -1
    source_event_file_id: int = -1
    source_warp_index: int = -1
    source_warp_x: int = -1
    source_warp_y: int = -1


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


def read_event_warps(event_narc: ndspy.narc.NARC, event_file_id: int) -> list[WarpEvent]:
    if event_file_id >= len(event_narc.files):
        return []
    data = event_narc.files[event_file_id]
    offset = 0
    warps: list[WarpEvent] = []
    try:
        count = struct.unpack_from("<I", data, offset)[0]
        offset += 4 + count * 0x14
        count = struct.unpack_from("<I", data, offset)[0]
        offset += 4 + count * 0x20
        count = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        for index in range(count):
            x, y, dest_header, dest_anchor, height = struct.unpack_from("<HHHHI", data, offset)
            offset += 0x0C
            warps.append(
                WarpEvent(
                    index=index,
                    x=x,
                    y=y,
                    dest_header=dest_header,
                    dest_anchor=dest_anchor,
                    height=height,
                )
            )
    except struct.error as exc:
        raise ValueError(f"event file {event_file_id} has malformed warp data") from exc
    return warps


def build_incoming_warps(
    *,
    maps: dict[str, int],
    arm9: bytes,
    event_narc: ndspy.narc.NARC,
    target_map_ids: set[int],
) -> dict[int, list[IncomingWarp]]:
    incoming = {map_id: [] for map_id in target_map_ids}
    max_map_id = max(maps.values())

    for source_map_id in range(max_map_id + 1):
        try:
            header = read_header(arm9, source_map_id)
            warps = read_event_warps(event_narc, header.event_file_id)
        except ValueError:
            continue

        for warp in warps:
            if warp.dest_header in incoming:
                incoming[warp.dest_header].append(
                    IncomingWarp(
                        source_map_id=source_map_id,
                        source_event_file_id=header.event_file_id,
                        warp=warp,
                    )
                )

    return incoming


def choose_warp_destination(
    *,
    symbol: str,
    map_id: int,
    data_id: int,
    target_event_file_id: int,
    incoming_warps: dict[int, list[IncomingWarp]],
) -> Destination | None:
    warps = incoming_warps.get(map_id, [])
    if not warps:
        return None

    incoming = sorted(
        warps,
        key=lambda row: (
            row.source_map_id,
            row.warp.index,
            row.warp.dest_anchor,
        ),
    )[0]
    warp = incoming.warp
    return Destination(
        symbol=symbol,
        map_id=map_id,
        data_id=data_id,
        x=warp.dest_anchor,
        y=WARP_ID_Y_SENTINEL,
        direction=1,
        source="incoming-warp-anchor",
        matrix_id=0,
        matrix_x=0,
        matrix_y=0,
        matrix_value=map_id,
        land_file_id=0,
        permission=0,
        event_file_id=target_event_file_id,
        warp_index=warp.dest_anchor,
        warp_dest_header=warp.dest_header,
        warp_dest_anchor=warp.dest_anchor,
        warp_height=warp.height,
        source_map_id=incoming.source_map_id,
        source_event_file_id=incoming.source_event_file_id,
        source_warp_index=warp.index,
        source_warp_x=warp.x,
        source_warp_y=warp.y,
    )


def packed_destination_halfword(destination: Destination) -> int:
    if destination.direction != 1:
        raise ValueError(f"{destination.symbol} direction must stay implicit south")
    if not (0 <= destination.map_id < PACKED_MAP_LIMIT):
        raise ValueError(f"{destination.symbol} map id {destination.map_id} does not fit packed row")
    if destination.y != WARP_ID_Y_SENTINEL:
        raise ValueError(f"{destination.symbol} must use a warp-id destination")
    if not (0 <= destination.x < PACKED_WARP_LIMIT):
        raise ValueError(f"{destination.symbol} warp id {destination.x} does not fit packed row")
    return (
        (destination.map_id << PACKED_MAP_SHIFT)
        | (destination.x << PACKED_WARP_SHIFT)
    )


def write_c(destinations: list[Destination], output: Path) -> None:
    lines = [
        '#include "../../include/map_teleport.h"',
        "",
        '#include "../../include/config.h"',
        '#include "../../include/constants/maps.h"',
        "",
        "#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS",
        "",
        "#define MAP_TELEPORT_ENCOUNTER_MAP_SHIFT 0",
        "#define MAP_TELEPORT_ENCOUNTER_MAP_MASK 0x03FFu",
        "#define MAP_TELEPORT_ENCOUNTER_WARP_SHIFT 10",
        "#define MAP_TELEPORT_ENCOUNTER_WARP_MASK 0x003Fu",
        f"#define MAP_TELEPORT_ENCOUNTER_DESTINATION_COUNT {len(destinations)}",
        "",
        "static const u16 sMapTeleportEncounterDestinations[MAP_TELEPORT_ENCOUNTER_DESTINATION_COUNT] = {",
    ]
    for destination in destinations:
        packed = packed_destination_halfword(destination)
        lines.append(
            "    "
            f"0x{packed:04X}u, // {destination.symbol} "
            f"warp-id {destination.warp_index} via map {destination.source_map_id} "
            f"warp {destination.source_warp_index} at "
            f"{destination.source_warp_x},{destination.source_warp_y}"
        )
    lines.extend(
        [
            "};",
            "",
            "static MapTeleportDestination sMapTeleportEncounterDestinationScratch;",
            "",
            "static u16 MapTeleport_EncounterDestinationPackedMapId(u16 packed)",
            "{",
            "    return (u16)((packed >> MAP_TELEPORT_ENCOUNTER_MAP_SHIFT)",
            "        & MAP_TELEPORT_ENCOUNTER_MAP_MASK);",
            "}",
            "",
            "static const MapTeleportDestination *MapTeleport_EncounterDestinationFromPacked(u16 packed)",
            "{",
            "    sMapTeleportEncounterDestinationScratch.mapId =",
            "        MapTeleport_EncounterDestinationPackedMapId(packed);",
            "    sMapTeleportEncounterDestinationScratch.x =",
            "        (u16)((packed >> MAP_TELEPORT_ENCOUNTER_WARP_SHIFT)",
            "            & MAP_TELEPORT_ENCOUNTER_WARP_MASK);",
            "    sMapTeleportEncounterDestinationScratch.y = MAP_TELEPORT_DESTINATION_WARP_ID_Y;",
            "    sMapTeleportEncounterDestinationScratch.direction = MAP_TELEPORT_DIRECTION_SOUTH;",
            "    return &sMapTeleportEncounterDestinationScratch;",
            "}",
            "",
            "static const MapTeleportDestination *MapTeleport_EncounterDestinationByIndex(u16 index)",
            "{",
            "    if (index >= MAP_TELEPORT_ENCOUNTER_DESTINATION_COUNT) {",
            "        return NULL;",
            "    }",
            "",
            "    return MapTeleport_EncounterDestinationFromPacked(sMapTeleportEncounterDestinations[index]);",
            "}",
            "",
            "const MapTeleportEncounterDestinationEntry gMapTeleportEncounterDestinationEntry",
            '    __attribute__((section(".map_teleport_encounter_destination_entry"), used)) = {',
            "    MAP_TELEPORT_ENCOUNTER_DESTINATION_MAGIC,",
            "    MAP_TELEPORT_ENCOUNTER_DESTINATION_VERSION,",
            "    sizeof(MapTeleportEncounterDestinationEntry),",
            "    MAP_TELEPORT_ENCOUNTER_DESTINATION_COUNT,",
            "    0,",
            "    MapTeleport_EncounterDestinationByIndex,",
            "    NULL,",
            "};",
            "",
            "#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS",
            "",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def write_json(
    destinations: list[Destination],
    output: Path,
    authoritative_count: int,
    skipped_no_warp_symbols: list[str],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "authoritative_count": authoritative_count,
                "destination_policy": "encounter maps with incoming game warp anchors only",
                "expected_count": len(destinations),
                "skipped_no_warp_count": len(skipped_no_warp_symbols),
                "skipped_no_warp_symbols": skipped_no_warp_symbols,
                "destinations": [destination.__dict__ for destination in destinations],
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

    required_files = [args.arm9, args.event_narc]
    missing_files = [str(path) for path in required_files if not path.is_file()]
    if missing_files:
        raise FileNotFoundError(f"missing extracted ROM inputs: {', '.join(missing_files)}")

    arm9 = args.arm9.read_bytes()
    event_narc = ndspy.narc.NARC.fromFile(args.event_narc)
    destinations: list[Destination] = []
    skipped_no_warps: list[str] = []
    target_map_ids = {map_id for _symbol, map_id, _data_id in entries}
    incoming_warps = build_incoming_warps(
        maps=maps,
        arm9=arm9,
        event_narc=event_narc,
        target_map_ids=target_map_ids,
    )

    for symbol, map_id, data_id in entries:
        header = read_header(arm9, map_id)
        destination = choose_warp_destination(
            symbol=symbol,
            map_id=map_id,
            data_id=data_id,
            target_event_file_id=header.event_file_id,
            incoming_warps=incoming_warps,
        )
        if destination is None:
            skipped_no_warps.append(symbol)
        else:
            destinations.append(destination)

    if not destinations:
        raise RuntimeError("no encounter maps had incoming warp anchors")

    write_c(destinations, args.c_output)
    write_json(destinations, args.json_output, expected_count, skipped_no_warps)
    print(
        json.dumps(
            {
                "authoritative_count": expected_count,
                "generated_count": len(destinations),
                "skipped_no_warp_count": len(skipped_no_warps),
                "skipped_no_warp_symbols": skipped_no_warps,
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
