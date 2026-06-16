#!/usr/bin/env python3
"""Probe map visual models for headbutt-tree candidates.

This tool intentionally does not read the Headbutt archive. It uses the map
matrix to find the land chunks for a map, then reads each chunk's BMD0/NSBMD
visual model and rasterizes polygons drawn with tree materials.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

import ndspy.narc


CELL_SIZE = 32
MODEL_ORIGIN_UNITS = 16 * 1024
TILE_MODEL_UNITS = 1024
PERMISSION_GRID_BYTES = CELL_SIZE * CELL_SIZE * 2
LAND_HEADER_SIZE = 0x14

GEOMETRY_PARAM_COUNTS = {
    0x00: 0,
    0x10: 1,
    0x11: 0,
    0x12: 1,
    0x13: 1,
    0x14: 1,
    0x15: 0,
    0x16: 16,
    0x17: 12,
    0x18: 16,
    0x19: 12,
    0x1A: 9,
    0x1B: 3,
    0x1C: 3,
    0x20: 1,
    0x21: 1,
    0x22: 1,
    0x23: 2,
    0x24: 1,
    0x25: 1,
    0x26: 1,
    0x27: 1,
    0x28: 1,
    0x29: 1,
    0x2A: 1,
    0x2B: 1,
    0x30: 1,
    0x31: 1,
    0x32: 1,
    0x33: 1,
    0x34: 32,
    0x40: 1,
    0x41: 0,
    0x50: 1,
    0x60: 1,
    0x70: 3,
    0x71: 2,
    0x72: 3,
}

RENDER_PARAM_COUNTS = {
    0x00: 0,
    0x01: 0,
    0x02: 2,
    0x03: 1,
    0x04: 1,
    0x05: 1,
    0x06: 3,
    0x07: 0,
    0x08: 0,
    0x0B: 0,
    0x0C: 1,
    0x0D: 1,
}


def repo_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[1].joinpath(*parts)


def read_matrix_file(matrix_id: int) -> dict[str, Any]:
    matrix_narc = ndspy.narc.NARC.fromFile(repo_path("base", "root", "a", "0", "4", "1"))
    data = matrix_narc.files[matrix_id]
    width = data[0]
    height = data[1]
    flags = data[2]
    name_len = data[4]
    name = data[5 : 5 + name_len].decode("ascii")
    offset = 5 + name_len
    cell_count = width * height
    matrix_values = struct.unpack_from(f"<{cell_count}H", data, offset)
    remaining = len(data) - offset
    land_data_values = None
    if remaining == cell_count * 5:
        land_data_offset = offset + cell_count * 3
        land_data_values = struct.unpack_from(f"<{cell_count}H", data, land_data_offset)
    elif remaining == cell_count * 2:
        land_data_values = matrix_values
    return {
        "id": matrix_id,
        "width": width,
        "height": height,
        "flags": flags,
        "name": name,
        "matrix_values": matrix_values,
        "land_data_values": land_data_values,
    }


def read_map_stamps(map_id: int, matrix_id: int) -> tuple[dict[str, Any], list[dict[str, int]]]:
    matrix = read_matrix_file(matrix_id)
    if matrix["land_data_values"] is None:
        raise RuntimeError(f"matrix {matrix_id} has no parsed land-data grid")

    stamps: list[dict[str, int]] = []
    for matrix_y in range(matrix["height"]):
        for matrix_x in range(matrix["width"]):
            index = matrix_y * matrix["width"] + matrix_x
            if matrix["matrix_values"][index] != map_id:
                continue
            stamps.append(
                {
                    "matrix_x": matrix_x,
                    "matrix_y": matrix_y,
                    "map_value": int(matrix["matrix_values"][index]),
                    "land_file_id": int(matrix["land_data_values"][index]),
                    "world_min_x": matrix_x * CELL_SIZE,
                    "world_min_y": matrix_y * CELL_SIZE,
                    "world_max_x": matrix_x * CELL_SIZE + CELL_SIZE - 1,
                    "world_max_y": matrix_y * CELL_SIZE + CELL_SIZE - 1,
                }
            )

    return matrix, stamps


def read_land_sections(land_file_id: int) -> dict[str, Any]:
    land_narc = ndspy.narc.NARC.fromFile(repo_path("base", "root", "a", "0", "6", "5"))
    data = land_narc.files[land_file_id]
    permission_len, buildings_len, nsbmd_len, bdhc_len = struct.unpack_from("<4I", data, 0)
    total_len = LAND_HEADER_SIZE + permission_len + buildings_len + nsbmd_len + bdhc_len
    if len(data) < total_len:
        raise RuntimeError(f"land file {land_file_id} is shorter than its section lengths")
    if permission_len != PERMISSION_GRID_BYTES:
        raise RuntimeError(
            f"land file {land_file_id} has unexpected permission length {permission_len:#x}"
        )

    permission_offset = LAND_HEADER_SIZE
    buildings_offset = permission_offset + permission_len
    nsbmd_offset = buildings_offset + buildings_len
    bdhc_offset = nsbmd_offset + nsbmd_len
    return {
        "land_file_id": land_file_id,
        "permission": struct.unpack_from(
            f"<{CELL_SIZE * CELL_SIZE}H", data, permission_offset
        ),
        "buildings": data[buildings_offset:nsbmd_offset],
        "nsbmd": data[nsbmd_offset:bdhc_offset],
        "bdhc": data[bdhc_offset : bdhc_offset + bdhc_len],
        "section_lengths": {
            "permission": permission_len,
            "buildings": buildings_len,
            "nsbmd": nsbmd_len,
            "bdhc": bdhc_len,
        },
    }


def unpack_model_header(data: bytes, model_off: int) -> dict[str, Any]:
    fields = struct.unpack_from("<5I16B4H6h8s", data, model_off)
    return {
        "model_size": fields[0],
        "render_offset": fields[1],
        "materials_offset": fields[2],
        "polygons_begin_offset": fields[3],
        "polygons_end_offset": fields[4],
        "objects_count": fields[8],
        "materials_count": fields[9],
        "polygons_count": fields[10],
        "vertices_count": fields[21],
        "surfaces_count": fields[22],
        "triangles_count": fields[23],
        "quads_count": fields[24],
        "bbox": {
            "x": fields[25],
            "y": fields[26],
            "z": fields[27],
            "width": fields[28],
            "height": fields[29],
            "depth": fields[30],
        },
    }


def parse_mdl0_model_directory(data: bytes) -> list[tuple[str, int]]:
    if not data.startswith(b"MDL0"):
        raise ValueError("MDL0 block expected")

    models_count, _info3d_size = struct.unpack_from("<xBH", data, 0x8)
    off = 0x0C
    _header_len, _block_len, block_magic = struct.unpack_from("<HHI", data, off)
    if block_magic != 0x17F:
        raise RuntimeError("unexpected MDL0 model directory block")
    off += 8 + 4 * models_count

    _section_len, _info_len = struct.unpack_from("<HH", data, off)
    model_offsets = [
        struct.unpack_from("<I", data, off + 4 + 4 * index)[0]
        for index in range(models_count)
    ]
    off += 4 + 4 * models_count

    names = [
        data[off + 16 * index : off + 16 * (index + 1)]
        .rstrip(b"\0")
        .decode("latin-1")
        for index in range(models_count)
    ]
    return list(zip(names, model_offsets))


def parse_name_offset_block(data: bytes, off: int) -> tuple[list[int], list[str], int]:
    count, _header_size = struct.unpack_from("<xBH", data, off)
    off += 4

    _block_header_len, _block_len, block_magic = struct.unpack_from("<HHI", data, off)
    if block_magic != 0x17F:
        raise RuntimeError("unexpected name-offset block")
    off += 8 + 4 * count

    offsets_header_len, _offsets_len = struct.unpack_from("<HH", data, off)
    if offsets_header_len != 4:
        raise RuntimeError("unexpected offset-table header length")
    off += 4

    offsets = [struct.unpack_from("<I", data, off + 4 * index)[0] for index in range(count)]
    off += 4 * count

    names = [
        data[off + 16 * index : off + 16 * (index + 1)]
        .rstrip(b"\0")
        .decode("latin-1")
        for index in range(count)
    ]
    off += 16 * count
    return offsets, names, off


def parse_material_names(data: bytes, model_off: int, materials_offset: int) -> list[str]:
    _offsets, names, _off = parse_name_offset_block(data, model_off + materials_offset + 4)
    return names


def parse_polygons(data: bytes, model_off: int, polygons_begin_offset: int) -> list[dict[str, Any]]:
    poly_offsets, poly_names, _off = parse_name_offset_block(data, model_off + polygons_begin_offset)
    polygons: list[dict[str, Any]] = []
    for poly_index, (poly_offset, name) in enumerate(zip(poly_offsets, poly_names)):
        poly_def_offset = model_off + polygons_begin_offset + poly_offset
        _unk_def_00, _unk_def_04, display_list_off, display_list_len = struct.unpack_from(
            "<4I", data, poly_def_offset
        )
        display_list = data[
            poly_def_offset + display_list_off : poly_def_offset + display_list_off + display_list_len
        ]
        polygons.append(
            {
                "index": poly_index,
                "name": name,
                "display_list_offset": display_list_off,
                "display_list_len": display_list_len,
                "display_list": display_list,
            }
        )
    return polygons


def parse_render_pairs(data: bytes, model_off: int, render_offset: int) -> list[dict[str, int]]:
    pairs: list[dict[str, int]] = []
    current_material: int | None = None
    # The model header points at an SBC/render-command block prefixed by a
    # little-endian byte length. The command stream itself starts after it.
    off = model_off + render_offset + 4
    guard = 0
    while off < len(data) and guard < 10000:
        guard += 1
        raw_cmd = data[off]
        off += 1
        cmd = raw_cmd & 0x1F

        if cmd == 0x01:
            break
        if cmd == 0x09:
            if off + 2 > len(data):
                break
            count = data[off + 1]
            off += 2 + 3 * count
            continue

        param_count = RENDER_PARAM_COUNTS.get(cmd)
        if param_count is None:
            raise RuntimeError(f"unknown render command {raw_cmd:#x} at {off - 1:#x}")
        params = list(data[off : off + param_count])
        off += param_count

        if cmd == 0x04 and params:
            current_material = params[0]
        elif cmd == 0x05 and params:
            if current_material is not None:
                pairs.append({"material_index": current_material, "polygon_index": params[0]})

    return pairs


def parse_nsbmd_models(nsbmd: bytes) -> list[dict[str, Any]]:
    if not nsbmd.startswith(b"BMD0"):
        raise ValueError("BMD0 file expected")

    _magic, _bom, version, _filesize, _headersize, num_blocks = struct.unpack_from(
        "<4sHHIHH", nsbmd, 0
    )
    if version != 2:
        raise RuntimeError(f"unsupported BMD0 version {version}")

    block_offsets = struct.unpack_from(f"<{num_blocks}I", nsbmd, 0x10)
    mdl0 = None
    for block_off in block_offsets:
        block_magic, block_len = struct.unpack_from("<4sI", nsbmd, block_off)
        if block_magic == b"MDL0":
            mdl0 = nsbmd[block_off : block_off + block_len]
            break
    if mdl0 is None:
        raise RuntimeError("BMD0 has no MDL0 block")

    models: list[dict[str, Any]] = []
    for model_name, model_off in parse_mdl0_model_directory(mdl0):
        header = unpack_model_header(mdl0, model_off)
        material_names = parse_material_names(mdl0, model_off, header["materials_offset"])
        polygons = parse_polygons(mdl0, model_off, header["polygons_begin_offset"])
        render_pairs = parse_render_pairs(mdl0, model_off, header["render_offset"])
        models.append(
            {
                "name": model_name,
                "offset": model_off,
                "header": header,
                "material_names": material_names,
                "polygons": polygons,
                "render_pairs": render_pairs,
            }
        )
    return models


def extract_bmd0(nsbmd: bytes) -> tuple[bytes | None, int | None]:
    offset = nsbmd.find(b"BMD0", 0, min(len(nsbmd), 0x80))
    if offset < 0:
        return None, None
    return nsbmd[offset:], offset


def sign_extend(value: int, bits: int) -> int:
    sign_bit = 1 << (bits - 1)
    return (value ^ sign_bit) - sign_bit


def read_s16_pair(param: bytes) -> tuple[int, int]:
    return struct.unpack_from("<hh", param, 0)


def decode_vtx_10(param: bytes) -> tuple[int, int, int]:
    value = struct.unpack_from("<I", param, 0)[0]
    x = sign_extend(value & 0x3FF, 10)
    y = sign_extend((value >> 10) & 0x3FF, 10)
    z = sign_extend((value >> 20) & 0x3FF, 10)
    return x, y, z


def decode_vtx_diff(param: bytes) -> tuple[int, int, int]:
    value = struct.unpack_from("<I", param, 0)[0]
    x = sign_extend(value & 0x3FF, 10) // 8
    y = sign_extend((value >> 10) & 0x3FF, 10) // 8
    z = sign_extend((value >> 20) & 0x3FF, 10) // 8
    return x, y, z


def parse_display_faces(display_list: bytes) -> list[list[tuple[int, int, int]]]:
    faces: list[list[tuple[int, int, int]]] = []
    current = (0, 0, 0)
    mode: int | None = None
    vertices: list[tuple[int, int, int]] = []
    off = 0

    def add_vertex(vertex: tuple[int, int, int]) -> None:
        nonlocal current
        current = vertex
        vertices.append(vertex)

    while off < len(display_list):
        command_ids = display_list[off : off + 4]
        off += 4
        for command_id in command_ids:
            param_count = GEOMETRY_PARAM_COUNTS.get(command_id)
            if param_count is None:
                raise RuntimeError(f"unknown geometry command {command_id:#x}")
            params = [display_list[off + 4 * index : off + 4 * (index + 1)] for index in range(param_count)]
            off += 4 * param_count

            if command_id == 0x40 and params:
                mode = struct.unpack_from("<I", params[0], 0)[0]
                vertices = []
            elif command_id == 0x41:
                mode = None
                vertices = []
            elif command_id == 0x23:
                x, y = read_s16_pair(params[0])
                z, _pad = read_s16_pair(params[1])
                add_vertex((x, y, z))
            elif command_id == 0x24:
                add_vertex(decode_vtx_10(params[0]))
            elif command_id == 0x25:
                x, y = read_s16_pair(params[0])
                add_vertex((x, y, current[2]))
            elif command_id == 0x26:
                x, z = read_s16_pair(params[0])
                add_vertex((x, current[1], z))
            elif command_id == 0x27:
                y, z = read_s16_pair(params[0])
                add_vertex((current[0], y, z))
            elif command_id == 0x28:
                dx, dy, dz = decode_vtx_diff(params[0])
                add_vertex((current[0] + dx, current[1] + dy, current[2] + dz))

            while mode is not None:
                if mode == 0 and len(vertices) >= 3:
                    faces.append(vertices[:3])
                    vertices = vertices[3:]
                elif mode == 1 and len(vertices) >= 4:
                    faces.append(vertices[:4])
                    vertices = vertices[4:]
                elif mode == 2 and len(vertices) >= 3:
                    faces.append(vertices[-3:])
                    break
                elif mode == 3 and len(vertices) >= 4:
                    faces.append(vertices[-4:])
                    break
                else:
                    break

    return faces


def parse_display_faces_with_uv(
    display_list: bytes,
) -> list[list[tuple[tuple[int, int, int], tuple[int, int]]]]:
    faces: list[list[tuple[tuple[int, int, int], tuple[int, int]]]] = []
    current = (0, 0, 0)
    current_uv = (0, 0)
    mode: int | None = None
    vertices: list[tuple[tuple[int, int, int], tuple[int, int]]] = []
    off = 0

    def add_vertex(vertex: tuple[int, int, int]) -> None:
        nonlocal current
        current = vertex
        vertices.append((vertex, current_uv))

    while off < len(display_list):
        command_ids = display_list[off : off + 4]
        off += 4
        for command_id in command_ids:
            param_count = GEOMETRY_PARAM_COUNTS.get(command_id)
            if param_count is None:
                raise RuntimeError(f"unknown geometry command {command_id:#x}")
            params = [display_list[off + 4 * index : off + 4 * (index + 1)] for index in range(param_count)]
            off += 4 * param_count

            if command_id == 0x22 and params:
                current_uv = struct.unpack_from("<hh", params[0], 0)
            elif command_id == 0x40 and params:
                mode = struct.unpack_from("<I", params[0], 0)[0]
                vertices = []
            elif command_id == 0x41:
                mode = None
                vertices = []
            elif command_id == 0x23:
                x, y = read_s16_pair(params[0])
                z, _pad = read_s16_pair(params[1])
                add_vertex((x, y, z))
            elif command_id == 0x24:
                add_vertex(decode_vtx_10(params[0]))
            elif command_id == 0x25:
                x, y = read_s16_pair(params[0])
                add_vertex((x, y, current[2]))
            elif command_id == 0x26:
                x, z = read_s16_pair(params[0])
                add_vertex((x, current[1], z))
            elif command_id == 0x27:
                y, z = read_s16_pair(params[0])
                add_vertex((current[0], y, z))
            elif command_id == 0x28:
                dx, dy, dz = decode_vtx_diff(params[0])
                add_vertex((current[0] + dx, current[1] + dy, current[2] + dz))

            while mode is not None:
                if mode == 0 and len(vertices) >= 3:
                    faces.append(vertices[:3])
                    vertices = vertices[3:]
                elif mode == 1 and len(vertices) >= 4:
                    faces.append(vertices[:4])
                    vertices = vertices[4:]
                elif mode == 2 and len(vertices) >= 3:
                    faces.append(vertices[-3:])
                    break
                elif mode == 3 and len(vertices) >= 4:
                    faces.append(vertices[-4:])
                    break
                else:
                    break

    return faces


def point_in_polygon(px: float, py: float, polygon: list[tuple[float, float]]) -> bool:
    inside = False
    count = len(polygon)
    for index in range(count):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % count]
        crosses = (y1 > py) != (y2 > py)
        if crosses:
            xinters = (x2 - x1) * (py - y1) / (y2 - y1) + x1
            if px < xinters:
                inside = not inside
    return inside


def rasterize_face(face: list[tuple[int, int, int]]) -> set[tuple[int, int]]:
    polygon = [
        (
            (x + MODEL_ORIGIN_UNITS) / TILE_MODEL_UNITS,
            (z + MODEL_ORIGIN_UNITS) / TILE_MODEL_UNITS,
        )
        for x, _y, z in face
    ]
    min_x = max(0, math.floor(min(x for x, _y in polygon)))
    max_x = min(CELL_SIZE - 1, math.floor(max(x for x, _y in polygon)))
    min_y = max(0, math.floor(min(y for _x, y in polygon)))
    max_y = min(CELL_SIZE - 1, math.floor(max(y for _x, y in polygon)))

    tiles: set[tuple[int, int]] = set()
    for tile_y in range(min_y, max_y + 1):
        for tile_x in range(min_x, max_x + 1):
            probes = (
                (tile_x + 0.5, tile_y + 0.5),
                (tile_x + 0.1, tile_y + 0.1),
                (tile_x + 0.9, tile_y + 0.1),
                (tile_x + 0.1, tile_y + 0.9),
                (tile_x + 0.9, tile_y + 0.9),
            )
            if any(point_in_polygon(px, py, polygon) for px, py in probes):
                tiles.add((tile_x, tile_y))
    return tiles


def uv_repeat_blocks(
    face: list[tuple[tuple[int, int, int], tuple[int, int]]],
) -> set[tuple[tuple[int, int], ...]]:
    points = [
        (
            (position[0] + MODEL_ORIGIN_UNITS) / TILE_MODEL_UNITS,
            (position[2] + MODEL_ORIGIN_UNITS) / TILE_MODEL_UNITS,
            uv[0],
            uv[1],
        )
        for position, uv in face
    ]
    polygon = [(x, y) for x, y, _s, _t in points]
    min_x = min(x for x, _y in polygon)
    max_x = max(x for x, _y in polygon)
    min_y = min(y for _x, y in polygon)
    max_y = max(y for _x, y in polygon)
    uv_span_s = max(s for _x, _y, s, _t in points) - min(s for _x, _y, s, _t in points)
    uv_span_t = max(t for _x, _y, _s, t in points) - min(t for _x, _y, _s, t in points)

    if max_x - min_x < 1.5 or max_y - min_y < 1.5:
        return set()
    if max(abs(uv_span_s), abs(uv_span_t)) < 512:
        return set()

    blocks: set[tuple[tuple[int, int], ...]] = set()
    start_x = int(round(min_x))
    start_y = int(round(min_y))
    end_x = int(round(max_x))
    end_y = int(round(max_y))
    for local_x in range(start_x, end_x, 2):
        for local_y in range(start_y, end_y, 2):
            if local_x < 0 or local_y < 0 or local_x + 1 >= CELL_SIZE or local_y + 1 >= CELL_SIZE:
                continue
            if not point_in_polygon(local_x + 1, local_y + 1, polygon):
                continue
            blocks.add(
                tuple(
                    sorted(
                        (
                            (local_x, local_y),
                            (local_x + 1, local_y),
                            (local_x, local_y + 1),
                            (local_x + 1, local_y + 1),
                        )
                    )
                )
            )
    return blocks


def connected_components(tiles: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    remaining = set(tiles)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        component = {start}
        queue: deque[tuple[int, int]] = deque([start])
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                neighbor = (nx, ny)
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        components.append(component)
    components.sort(key=lambda item: (min(y for _x, y in item), min(x for x, _y in item)))
    return components


def bbox_for_tiles(tiles: Iterable[tuple[int, int]]) -> dict[str, int]:
    tile_list = list(tiles)
    return {
        "min_x": min(x for x, _y in tile_list),
        "min_y": min(y for _x, y in tile_list),
        "max_x": max(x for x, _y in tile_list),
        "max_y": max(y for _x, y in tile_list),
    }


def pair_runs(mask: set[tuple[int, int]], min_x: int, max_x: int) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for x in range(min_x, max_x):
        ys = sorted({y for px, y in mask if px == x and (x + 1, y) in mask})
        if not ys:
            continue
        run_start = ys[0]
        previous = ys[0]
        for y in ys[1:] + [None]:
            if y is not None and y == previous + 1:
                previous = y
                continue
            if previous - run_start + 1 >= 2:
                runs.append({"x": x, "min_y": run_start, "max_y": previous})
            if y is not None:
                run_start = previous = y
    return runs


def chunk_run(run: dict[str, int]) -> list[set[tuple[int, int]]]:
    x = run["x"]
    y = run["min_y"]
    max_y = run["max_y"]
    chunks: list[set[tuple[int, int]]] = []
    while y <= max_y:
        remaining = max_y - y + 1
        if remaining == 1:
            break
        height = 3 if remaining % 2 == 1 and remaining >= 3 else 2
        chunks.append({(x, yy) for yy in range(y, y + height)} | {(x + 1, yy) for yy in range(y, y + height)})
        y += height
    return chunks


def simple_two_column_splitter(mask: set[tuple[int, int]]) -> list[dict[str, Any]]:
    if not mask:
        return []
    min_x = min(x for x, _y in mask)
    max_x = max(x for x, _y in mask)
    parity_scores: dict[int, int] = {}
    for parity in (0, 1):
        parity_scores[parity] = sum(
            1 for run in pair_runs(mask, min_x, max_x) if run["x"] % 2 == parity
        )
    selected_parity = max(parity_scores, key=parity_scores.get)

    candidates: list[set[tuple[int, int]]] = []
    used: set[tuple[int, int]] = set()
    for run in pair_runs(mask, min_x, max_x):
        if run["x"] % 2 != selected_parity:
            continue
        for chunk in chunk_run(run):
            if chunk & used:
                continue
            candidates.append(chunk)
            used |= chunk

    detected: list[dict[str, Any]] = []
    for index, footprint in enumerate(candidates, start=1):
        bbox = bbox_for_tiles(footprint)
        detected.append(
            {
                "id": f"visual-{index:04d}",
                "kind": "headbutt_tree_visual_model_candidate",
                "anchor": {
                    "x": (bbox["min_x"] + bbox["max_x"]) / 2,
                    "y": (bbox["min_y"] + bbox["max_y"]) / 2,
                },
                "bbox": bbox,
                "footprint": [{"x": x, "y": y} for x, y in sorted(footprint, key=lambda item: (item[1], item[0]))],
                "tile_count": len(footprint),
                "source": "visual_model_selected_material_two_column_splitter_experimental",
                "confidence": "experimental",
            }
        )
    return detected


def uv_block_splitter(
    blocks: set[tuple[tuple[int, int], ...]],
    selected_material: str,
    selected_source: str,
) -> list[dict[str, Any]]:
    detected: list[dict[str, Any]] = []
    for index, block in enumerate(sorted(blocks, key=lambda item: (min(y for _x, y in item), min(x for x, _y in item))), start=1):
        footprint = set(block)
        bbox = bbox_for_tiles(footprint)
        detected.append(
            {
                "id": f"visual-{index:04d}",
                "kind": "headbutt_tree_visual_model_candidate",
                "anchor": {
                    "x": (bbox["min_x"] + bbox["max_x"]) / 2,
                    "y": (bbox["min_y"] + bbox["max_y"]) / 2,
                },
                "bbox": bbox,
                "footprint": [{"x": x, "y": y} for x, y in sorted(footprint, key=lambda item: (item[1], item[0]))],
                "tile_count": len(footprint),
                "source": "visual_model_tree_material_uv_repeat_splitter_experimental",
                "confidence": "experimental",
                "evidence": {
                    "selected_material": selected_material,
                    "selected_material_source": selected_source,
                    "repeat_uv_units": 512,
                    "repeat_world_tiles": 2,
                },
            }
        )
    return detected


def tile_dicts(tiles: set[tuple[int, int]]) -> list[dict[str, int]]:
    return [{"x": x, "y": y} for x, y in sorted(tiles, key=lambda item: (item[1], item[0]))]


def inspect_visual_model(
    stamps: list[dict[str, int]],
    selected_material: str,
) -> tuple[
    dict[str, set[tuple[int, int]]],
    dict[str, set[tuple[tuple[int, int], ...]]],
    list[dict[str, Any]],
]:
    material_tiles: dict[str, set[tuple[int, int]]] = defaultdict(set)
    material_blocks: dict[str, set[tuple[tuple[int, int], ...]]] = defaultdict(set)
    evidence: list[dict[str, Any]] = []

    for stamp in stamps:
        sections = read_land_sections(stamp["land_file_id"])
        nsbmd = sections["nsbmd"]
        bmd0, bmd0_offset = extract_bmd0(nsbmd)
        if bmd0 is None:
            evidence.append(
                {
                    "matrix_x": stamp["matrix_x"],
                    "matrix_y": stamp["matrix_y"],
                    "land_file_id": stamp["land_file_id"],
                    "warning": "land_chunk_has_no_bmd0_visual_model",
                    "nsbmd_magic": nsbmd[:4].hex(),
                    "selected_material_match": False,
                }
            )
            continue
        models = parse_nsbmd_models(bmd0)
        for model in models:
            material_names = model["material_names"]
            polygons = {polygon["index"]: polygon for polygon in model["polygons"]}
            for pair in model["render_pairs"]:
                material_index = pair["material_index"]
                polygon_index = pair["polygon_index"]
                if material_index >= len(material_names) or polygon_index not in polygons:
                    continue
                material_name = material_names[material_index]
                if "tree" not in material_name.lower():
                    continue
                polygon = polygons[polygon_index]
                local_tiles: set[tuple[int, int]] = set()
                for face in parse_display_faces(polygon["display_list"]):
                    local_tiles |= rasterize_face(face)
                world_tiles = {
                    (stamp["world_min_x"] + x, stamp["world_min_y"] + y)
                    for x, y in local_tiles
                }
                world_blocks: set[tuple[tuple[int, int], ...]] = set()
                for face in parse_display_faces_with_uv(polygon["display_list"]):
                    for local_block in uv_repeat_blocks(face):
                        world_blocks.add(
                            tuple(
                                sorted(
                                    (stamp["world_min_x"] + x, stamp["world_min_y"] + y)
                                    for x, y in local_block
                                )
                            )
                        )
                material_tiles[material_name] |= world_tiles
                material_blocks[material_name] |= world_blocks
                evidence.append(
                    {
                        "matrix_x": stamp["matrix_x"],
                        "matrix_y": stamp["matrix_y"],
                        "land_file_id": stamp["land_file_id"],
                        "model": model["name"],
                        "material_index": material_index,
                        "material_name": material_name,
                        "polygon_index": polygon_index,
                        "polygon_name": polygon["name"],
                        "nsbmd_bmd0_offset": bmd0_offset,
                        "local_tile_count": len(local_tiles),
                        "world_tile_count": len(world_tiles),
                        "uv_repeat_block_count": len(world_blocks),
                        "selected_material_match": material_name == selected_material
                        or material_name.endswith(selected_material),
                    }
                )
    return material_tiles, material_blocks, evidence


def fixture_quality_warnings(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    fixture = json.loads(path.read_text(encoding="utf-8"))
    warnings: list[dict[str, Any]] = []
    for tree in fixture.get("expected_trees", []):
        tree_id = tree.get("id")
        tiles = {(int(tile["x"]), int(tile["y"])) for tile in tree.get("footprint", [])}
        if not tiles:
            warnings.append({"id": tree_id, "reason": "empty_footprint"})
            continue
        bbox = bbox_for_tiles(tiles)
        width = bbox["max_x"] - bbox["min_x"] + 1
        height = bbox["max_y"] - bbox["min_y"] + 1
        if len(connected_components(tiles)) != 1:
            warnings.append({"id": tree_id, "reason": "disconnected_footprint", "bbox": bbox})
        if width != 2 or height not in (2, 3, 4, 5):
            warnings.append(
                {
                    "id": tree_id,
                    "reason": "nonstandard_shape_for_tree_fixture",
                    "bbox": bbox,
                    "tile_count": len(tiles),
                }
            )
    return warnings


def build_output(args: argparse.Namespace) -> dict[str, Any]:
    matrix, stamps = read_map_stamps(args.map_id, args.matrix_id)
    if not stamps:
        raise RuntimeError(f"map {args.map_id} was not found in matrix {args.matrix_id}")

    material_tiles, material_blocks, evidence = inspect_visual_model(stamps, args.selected_material)
    selected_names = [
        material_name
        for material_name in material_tiles
        if material_name == args.selected_material or material_name.endswith(args.selected_material)
    ]
    selected_tiles: set[tuple[int, int]] = set()
    selected_blocks: set[tuple[tuple[int, int], ...]] = set()
    for material_name in selected_names:
        selected_tiles |= material_tiles.get(material_name, set())
        selected_blocks |= material_blocks.get(material_name, set())
    if not selected_tiles:
        for material_name, tiles in material_tiles.items():
            if material_name.endswith("_un"):
                selected_tiles |= tiles
                selected_blocks |= material_blocks.get(material_name, set())
        selected_source = "fallback_material_suffix_un"
    else:
        selected_source = "exact_or_suffix_material_name"

    detected_trees = (
        uv_block_splitter(selected_blocks, args.selected_material, selected_source)
        if args.emit_candidates
        else []
    )

    visual_masks = []
    for material_name, tiles in sorted(material_tiles.items()):
        visual_masks.append(
            {
                "material": material_name,
                "tile_count": len(tiles),
                "component_count": len(connected_components(tiles)),
                "bbox": bbox_for_tiles(tiles) if tiles else None,
                "tiles": tile_dicts(tiles),
            }
        )

    return {
        "schema_version": 1,
        "detector": "visual_model_tree_material_probe",
        "map_id": args.map_id,
        "coordinate_space": "world_tile",
        "matrix": {
            "id": args.matrix_id,
            "name": matrix["name"],
            "width": matrix["width"],
            "height": matrix["height"],
        },
        "map_stamps": stamps,
        "selected_material": args.selected_material,
        "selected_material_source": selected_source,
        "selected_mask_tile_count": len(selected_tiles),
        "selected_uv_repeat_block_count": len(selected_blocks),
        "selected_mask_component_count": len(connected_components(selected_tiles)),
        "selected_mask_bbox": bbox_for_tiles(selected_tiles) if selected_tiles else None,
        "visual_masks": visual_masks,
        "render_evidence": evidence,
        "detected_trees": detected_trees,
        "fixture_quality_warnings": fixture_quality_warnings(args.fixture),
        "notes": [
            "This probe does not read the Headbutt archive.",
            "visual_masks are direct evidence from BMD0/NSBMD tree-material polygons.",
            "detected_trees use experimental UV-repeat primitives and should not be treated as final gameplay data.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-id", type=int, required=True)
    parser.add_argument("--matrix-id", type=int, default=0)
    parser.add_argument("--selected-material", default="tree01_un")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--emit-candidates",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="emit experimental two-column tree candidates from the selected material mask",
    )
    args = parser.parse_args()

    output = build_output(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "map_id": output["map_id"],
                "stamps": len(output["map_stamps"]),
                "selected_material": output["selected_material"],
                "selected_mask_tile_count": output["selected_mask_tile_count"],
                "detected_tree_count": len(output["detected_trees"]),
                "fixture_quality_warnings": len(output["fixture_quality_warnings"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
