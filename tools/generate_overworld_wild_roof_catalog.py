#!/usr/bin/env python3
"""Generate the compact overworld-wild surface catalog from approved model templates.

The manifest describes reviewed, model-local roof planes or conservative authored
roof bounds or point perches. This script discovers every matching placement, samples
the rendered height at each authored tile center, coalesces equal-height nodes,
clips rectangles at 32x32 block boundaries, and emits compact runtime-compatible
catalog rows. Cross-block identity is encoded as an anchor-block delta.

Only build-time extraction happens here.  The game never parses land data or
NSBMD geometry at runtime.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
import sys
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import headbutt_tree_visual_model_probe as visual_probe  # noqa: E402
from narc_reader import NarcArchive  # noqa: E402


CELL_SIZE = 32
LAND_HEADER_SIZE = 0x14
LAND_MAGIC = 0x1234
OBJECT_RECORD_SIZE = 48
FX32_PER_TILE = 16 * 4096
MODEL_FX32_SCALE = 16
SURFACE_TYPES = {
    "rooftop": 0,
    "signpost": 1,
    "mailbox": 2,
    "flowerbed": 3,
}
NATIVE_GROUND_HEIGHT_PAGE = 0xFF


GEOMETRY_PARAM_COUNTS = visual_probe.GEOMETRY_PARAM_COUNTS


@dataclass(frozen=True)
class MatrixCell:
    matrix_id: int
    matrix_x: int
    matrix_y: int
    land_data_id: int
    altitude: int


@dataclass(frozen=True)
class BuildingPlacement:
    land_data_id: int
    object_index: int
    model_id: int
    x_fx32: int
    y_fx32: int
    z_fx32: int


@dataclass(frozen=True)
class CatalogInstance:
    land_data_id: int
    min_x: int
    min_y: int
    width: int
    height: int
    height_q4: int
    height_page: int
    anchor_block_dx: int
    anchor_block_dy: int
    anchor_local_surface_id: int
    surface_type: int
    logical_group: int
    source: str
    confidence: str


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def parse_int(value: Any, label: str) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise RuntimeError(f"{label}: invalid integer {value!r}") from exc
    raise RuntimeError(f"{label}: expected an integer")


def sign_extend(value: int, bits: int) -> int:
    sign_bit = 1 << (bits - 1)
    return (value ^ sign_bit) - sign_bit


def parse_display_faces(display_list: bytes) -> list[list[tuple[int, int, int]]]:
    """Decode GX primitives into faces in common 1/4096 model units.

    VTX_10 and VTX_DIFF have different fixed-point formats from VTX_16.  Faces
    are emitted only when a vertex command completes a primitive; non-vertex
    state commands must not duplicate strip faces.
    """

    faces: list[list[tuple[int, int, int]]] = []
    current = (0, 0, 0)
    mode: int | None = None
    vertices: list[tuple[int, int, int]] = []
    offset = 0

    def add_vertex(vertex: tuple[int, int, int]) -> None:
        nonlocal current
        current = vertex
        vertices.append(vertex)
        if mode == 0 and len(vertices) % 3 == 0:
            faces.append(vertices[-3:])
        elif mode == 1 and len(vertices) % 4 == 0:
            faces.append(vertices[-4:])
        elif mode == 2 and len(vertices) >= 3:
            faces.append(vertices[-3:])
        elif mode == 3 and len(vertices) >= 4 and len(vertices) % 2 == 0:
            faces.append([vertices[-4], vertices[-3], vertices[-1], vertices[-2]])

    while offset < len(display_list):
        command_ids = display_list[offset : offset + 4]
        offset += 4
        for command_id in command_ids:
            parameter_count = GEOMETRY_PARAM_COUNTS.get(command_id)
            require(parameter_count is not None, f"unknown GX command {command_id:#x}")
            byte_count = parameter_count * 4
            require(offset + byte_count <= len(display_list), "truncated GX command")
            parameters = [
                display_list[offset + index * 4 : offset + (index + 1) * 4]
                for index in range(parameter_count)
            ]
            offset += byte_count

            if command_id == 0x40:
                mode = struct.unpack_from("<I", parameters[0])[0]
                require(mode in (0, 1, 2, 3), f"unsupported primitive mode {mode}")
                vertices = []
            elif command_id == 0x41:
                mode = None
                vertices = []
            elif command_id == 0x23:
                x, y = struct.unpack_from("<hh", parameters[0])
                z, _padding = struct.unpack_from("<hh", parameters[1])
                add_vertex((x, y, z))
            elif command_id == 0x24:
                packed = struct.unpack_from("<I", parameters[0])[0]
                add_vertex(
                    (
                        sign_extend(packed & 0x3FF, 10) * 64,
                        sign_extend((packed >> 10) & 0x3FF, 10) * 64,
                        sign_extend((packed >> 20) & 0x3FF, 10) * 64,
                    )
                )
            elif command_id == 0x25:
                x, y = struct.unpack_from("<hh", parameters[0])
                add_vertex((x, y, current[2]))
            elif command_id == 0x26:
                x, z = struct.unpack_from("<hh", parameters[0])
                add_vertex((x, current[1], z))
            elif command_id == 0x27:
                y, z = struct.unpack_from("<hh", parameters[0])
                add_vertex((current[0], y, z))
            elif command_id == 0x28:
                packed = struct.unpack_from("<I", parameters[0])[0]
                add_vertex(
                    (
                        current[0] + sign_extend(packed & 0x3FF, 10) * 8,
                        current[1] + sign_extend((packed >> 10) & 0x3FF, 10) * 8,
                        current[2] + sign_extend((packed >> 20) & 0x3FF, 10) * 8,
                    )
                )

    return faces


def point_in_polygon_inclusive(
    point_x: float,
    point_y: float,
    polygon: list[tuple[float, float]],
) -> bool:
    epsilon = 1e-7
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        cross = (point_x - x1) * (y2 - y1) - (point_y - y1) * (x2 - x1)
        if (
            abs(cross) <= epsilon
            and min(x1, x2) - epsilon <= point_x <= max(x1, x2) + epsilon
            and min(y1, y2) - epsilon <= point_y <= max(y1, y2) + epsilon
        ):
            return True

    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > point_y) != (y2 > point_y):
            intersection = (x2 - x1) * (point_y - y1) / (y2 - y1) + x1
            if point_x < intersection:
                inside = not inside
    return inside


def read_matrix_cells(matrix_narc: NarcArchive, matrix_id: int) -> list[MatrixCell]:
    require(0 <= matrix_id < len(matrix_narc.files), f"matrix {matrix_id} is out of range")
    data = matrix_narc.files[matrix_id]
    require(len(data) >= 5, f"matrix {matrix_id} is truncated")
    width, height, has_headers, has_altitudes, name_length = data[:5]
    cell_count = width * height
    offset = 5 + name_length

    if has_headers:
        offset += cell_count * 2
    altitudes = [0] * cell_count
    if has_altitudes:
        require(offset + cell_count <= len(data), f"matrix {matrix_id} altitude grid is truncated")
        altitudes = list(data[offset : offset + cell_count])
        offset += cell_count
    require(offset + cell_count * 2 <= len(data), f"matrix {matrix_id} land grid is truncated")
    land_ids = struct.unpack_from(f"<{cell_count}H", data, offset)

    return [
        MatrixCell(matrix_id, index % width, index // width, int(land_id), altitudes[index])
        for index, land_id in enumerate(land_ids)
        if land_id != 0xFFFF
    ]


def read_land_objects(land_narc: NarcArchive, land_data_id: int) -> list[BuildingPlacement]:
    require(0 <= land_data_id < len(land_narc.files), f"land data {land_data_id} is out of range")
    data = land_narc.files[land_data_id]
    if not data:
        return []
    require(len(data) >= LAND_HEADER_SIZE, f"land data {land_data_id} is truncated")
    permission_size, object_size, model_size, bdhc_size = struct.unpack_from("<4I", data, 0)
    magic, unknown_size = struct.unpack_from("<HH", data, 16)
    require(magic == LAND_MAGIC, f"land data {land_data_id} has bad magic {magic:#x}")
    require(object_size % OBJECT_RECORD_SIZE == 0, f"land data {land_data_id} has partial object record")

    object_offset = LAND_HEADER_SIZE + unknown_size + permission_size
    expected_size = object_offset + object_size + model_size + bdhc_size
    require(expected_size <= len(data), f"land data {land_data_id} section sizes exceed the member")

    placements: list[BuildingPlacement] = []
    for object_index in range(object_size // OBJECT_RECORD_SIZE):
        offset = object_offset + object_index * OBJECT_RECORD_SIZE
        model_id, x_fx32, y_fx32, z_fx32 = struct.unpack_from("<Iiii", data, offset)
        rotation = data[offset + 16 : offset + 28]
        scale = struct.unpack_from("<iii", data, offset + 28)
        trailing = data[offset + 40 : offset + 48]
        require(not any(rotation), f"land {land_data_id} object {object_index} has unsupported rotation")
        require(scale == (4096, 4096, 4096), f"land {land_data_id} object {object_index} has unsupported scale")
        require(not any(trailing), f"land {land_data_id} object {object_index} has unsupported trailing transform")
        placements.append(
            BuildingPlacement(land_data_id, object_index, model_id, x_fx32, y_fx32, z_fx32)
        )
    return placements


def model_geometry(
    building_models: NarcArchive,
    model_id: int,
) -> tuple[str, int, list[tuple[int, list[tuple[int, int, int]], str]]]:
    require(0 <= model_id < len(building_models.files), f"building model {model_id} is out of range")
    data = building_models.files[model_id]
    models = visual_probe.parse_nsbmd_models(data)
    require(len(models) == 1, f"building model {model_id} does not contain exactly one model")
    model = models[0]

    mdl0_offset = struct.unpack_from("<I", data, 0x10)[0]
    mdl0 = data[mdl0_offset:]
    directory = visual_probe.parse_mdl0_model_directory(mdl0)
    require(len(directory) == 1, f"building model {model_id} MDL0 directory is not singular")
    model_offset = directory[0][1]
    position_scale = struct.unpack_from("<i", mdl0, model_offset + 28)[0]

    polygons = {polygon["index"]: polygon for polygon in model["polygons"]}
    horizontal_faces: list[tuple[int, list[tuple[int, int, int]], str]] = []
    for pair in model["render_pairs"]:
        require(pair["polygon_index"] in polygons, f"model {model_id} references a missing polygon")
        material_index = pair["material_index"]
        require(material_index < len(model["material_names"]), f"model {model_id} references a missing material")
        material = model["material_names"][material_index]
        for face in parse_display_faces(polygons[pair["polygon_index"]]["display_list"]):
            if len({vertex[1] for vertex in face}) == 1:
                horizontal_faces.append((face[0][1], face, material))
    return model["name"], position_scale, horizontal_faces


def model_all_faces(
    building_models: NarcArchive,
    model_id: int,
) -> tuple[str, int, list[tuple[list[tuple[int, int, int]], str]]]:
    require(0 <= model_id < len(building_models.files), f"building model {model_id} is out of range")
    data = building_models.files[model_id]
    models = visual_probe.parse_nsbmd_models(data)
    require(len(models) == 1, f"building model {model_id} does not contain exactly one model")
    model = models[0]

    mdl0_offset = struct.unpack_from("<I", data, 0x10)[0]
    mdl0 = data[mdl0_offset:]
    directory = visual_probe.parse_mdl0_model_directory(mdl0)
    require(len(directory) == 1, f"building model {model_id} MDL0 directory is not singular")
    position_scale = struct.unpack_from("<i", mdl0, directory[0][1] + 28)[0]

    polygons = {polygon["index"]: polygon for polygon in model["polygons"]}
    faces: list[tuple[list[tuple[int, int, int]], str]] = []
    for pair in model["render_pairs"]:
        require(pair["polygon_index"] in polygons, f"model {model_id} references a missing polygon")
        material_index = pair["material_index"]
        require(material_index < len(model["material_names"]), f"model {model_id} references a missing material")
        material = model["material_names"][material_index]
        faces.extend(
            (face, material)
            for face in parse_display_faces(polygons[pair["polygon_index"]]["display_list"])
        )
    require(faces, f"building model {model_id} has no rendered faces")
    return model["name"], position_scale, faces


def face_has_projected_area(face: list[tuple[int, int, int]]) -> bool:
    """Return whether a rendered face can support a point in the X/Z plane."""

    first = face[0]
    return any(
        (face[index][0] - first[0]) * (face[index + 1][2] - first[2])
        - (face[index][2] - first[2]) * (face[index + 1][0] - first[0])
        != 0
        for index in range(1, len(face) - 1)
    )


def connected_roof_component_faces(
    building_models: NarcArchive,
    spec: dict[str, Any],
) -> tuple[int, list[tuple[list[tuple[int, int, int]], str]]]:
    """Find the complete walkable mesh component seeded by the reviewed plane.

    Vertical faces are deliberately excluded from adjacency.  They connect a
    roof to the building facade, while sloped and horizontal faces form the
    continuous surface that a rooftop encounter may occupy.
    """

    _name, position_scale, all_faces = model_all_faces(building_models, spec["model_id"])
    excluded = spec["exclude_material_contains"]
    faces = [
        (face, material)
        for face, material in all_faces
        if not any(fragment in material.lower() for fragment in excluded)
        and face_has_projected_area(face)
    ]
    require(faces, f"model {spec['model_id']}: no projected roof faces remain")

    seed_indices = set()
    edge_to_face_indices: dict[
        tuple[tuple[int, int, int], tuple[int, int, int]], set[int]
    ] = defaultdict(set)
    for face_index, (face, _material) in enumerate(faces):
        if len({vertex[1] for vertex in face}) == 1:
            scaled_height = face[0][1] * position_scale * MODEL_FX32_SCALE
            require(
                scaled_height % 65536 == 0,
                f"model {spec['model_id']}: non-integral scaled height",
            )
            if scaled_height // 65536 == spec["relative_height_fx32"]:
                seed_indices.add(face_index)
        for first, second in zip(face, face[1:] + face[:1]):
            edge_to_face_indices[tuple(sorted((first, second)))].add(face_index)
    require(
        seed_indices,
        f"model {spec['model_id']}: selected plane has no projected seed faces",
    )

    component_indices = set(seed_indices)
    pending = list(seed_indices)
    while pending:
        face_index = pending.pop()
        face = faces[face_index][0]
        for first, second in zip(face, face[1:] + face[:1]):
            for neighbor in edge_to_face_indices[tuple(sorted((first, second)))]:
                if neighbor not in component_indices:
                    component_indices.add(neighbor)
                    pending.append(neighbor)

    return position_scale, [faces[index] for index in sorted(component_indices)]


def verify_model_template(
    building_models: NarcArchive,
    spec: dict[str, Any],
) -> dict[str, Any]:
    model_id = parse_int(spec["model_id"], "model_id")
    expected_name = str(spec["model_name"])
    relative_height = parse_int(spec["relative_height_fx32"], f"model {model_id} relative height")
    generation = str(spec.get("generation", "mesh_plane"))
    require(
        generation in ("mesh_plane", "authored_model_bounds", "authored_node"),
        f"model {model_id}: invalid generation mode {generation}",
    )
    model_name, position_scale, faces = model_geometry(building_models, model_id)
    require(model_name.lower() == expected_name.lower(), f"model {model_id}: expected {expected_name}, found {model_name}")

    confidence = str(spec["confidence"])
    require(confidence in ("mesh_verified", "authored_approximation"), f"model {model_id}: invalid confidence")
    require(
        (generation == "mesh_plane" and confidence == "mesh_verified")
        or (generation != "mesh_plane" and confidence == "authored_approximation"),
        f"model {model_id}: generation mode and confidence disagree",
    )
    surface_type_name = str(spec.get("surface_type", "rooftop"))
    require(
        surface_type_name in SURFACE_TYPES,
        f"model {model_id}: invalid surface type {surface_type_name}",
    )

    all_name, all_position_scale, all_faces = model_all_faces(building_models, model_id)
    require(all_name == model_name and all_position_scale == position_scale, f"model {model_id}: inconsistent model parse")
    component_faces: list[tuple[list[tuple[int, int, int]], str]] = []
    if generation == "mesh_plane":
        component_scale, component_faces = connected_roof_component_faces(
            building_models,
            {
                "model_id": model_id,
                "relative_height_fx32": relative_height,
                "exclude_material_contains": [
                    str(value).lower()
                    for value in spec.get("exclude_material_contains", ["kage"])
                ],
            },
        )
        require(component_scale == position_scale, f"model {model_id}: inconsistent component scale")
    max_scaled_y = max(vertex[1] for face, _material in all_faces for vertex in face) * position_scale * MODEL_FX32_SCALE
    require(max_scaled_y % 65536 == 0, f"model {model_id}: maximum height is not integral FX32")
    max_height = max_scaled_y // 65536
    if generation in ("authored_model_bounds", "authored_node"):
        require(
            relative_height == (max_height + 15) // 16 * 16,
            f"model {model_id}: authored safe height {relative_height:#x} is not the Q4 ceiling of model maximum {max_height:#x}",
        )

    plane_polygons: list[tuple[list[tuple[float, float]], str]] = []
    for raw_y, face, material in faces:
        scaled_height = raw_y * position_scale * MODEL_FX32_SCALE
        require(scaled_height % 65536 == 0, f"model {model_id}: non-integral scaled height")
        if scaled_height // 65536 != relative_height:
            continue
        polygon = [
            (
                vertex[0] * position_scale / 65536 / 4096,
                vertex[2] * position_scale / 65536 / 4096,
            )
            for vertex in face
        ]
        plane_polygons.append((polygon, material))
    if generation not in ("authored_model_bounds", "authored_node"):
        require(plane_polygons, f"model {model_id}: no horizontal faces at {relative_height:#x}")

    verified_offsets = []
    for index, pair in enumerate(spec.get("mesh_verified_centers_q16", [])):
        require(len(pair) == 2, f"model {model_id}: center {index} must contain x/z")
        x_q16 = parse_int(pair[0], f"model {model_id} center x")
        z_q16 = parse_int(pair[1], f"model {model_id} center z")
        point = (x_q16 / 16, z_q16 / 16)
        require(
            any(point_in_polygon_inclusive(point[0], point[1], polygon) for polygon, _ in plane_polygons),
            f"model {model_id}: verified center {point} misses the selected plane",
        )
        verified_offsets.append((x_q16, z_q16))

    rectangle = spec.get("rectangle")
    min_x_q16 = min_z_q16 = width = height = None
    if generation not in ("authored_model_bounds", "authored_node"):
        require(isinstance(rectangle, dict), f"model {model_id}: rectangle is required")
        min_x_q16 = parse_int(rectangle["min_center_x_q16"], f"model {model_id} rectangle x")
        min_z_q16 = parse_int(rectangle["min_center_z_q16"], f"model {model_id} rectangle z")
        width = parse_int(rectangle["width"], f"model {model_id} rectangle width")
        height = parse_int(rectangle["height"], f"model {model_id} rectangle height")
        require(1 <= width <= 32 and 1 <= height <= 32 and width * height <= 255, f"model {model_id}: invalid rectangle")
        dense_offsets = {
            (min_x_q16 + x * 16, min_z_q16 + y * 16)
            for y in range(height)
            for x in range(width)
        }
        verified_set = set(verified_offsets)
        if confidence == "mesh_verified":
            require(dense_offsets <= verified_set, f"model {model_id}: dense rectangle is not fully mesh-verified")
        else:
            require(verified_set <= dense_offsets, f"model {model_id}: verified centers fall outside the authored rectangle")

    default_widths = [1] if generation == "authored_node" else ([width] if width is not None else [])
    default_heights = [1] if generation == "authored_node" else ([height] if height is not None else [])
    allowed_widths = [
        parse_int(value, f"model {model_id} allowed width")
        for value in spec.get("allowed_widths", default_widths)
    ]
    allowed_heights = [
        parse_int(value, f"model {model_id} allowed height")
        for value in spec.get("allowed_heights", default_heights)
    ]
    require(allowed_widths and allowed_heights, f"model {model_id}: allowed dimensions are required")

    return {
        "model_id": model_id,
        "model_name": model_name,
        "generation": generation,
        "relative_height_fx32": relative_height,
        "position_scale": position_scale,
        "min_center_x_q16": min_x_q16,
        "min_center_z_q16": min_z_q16,
        "width": width,
        "height": height,
        "confidence": confidence,
        "surface_type": surface_type_name,
        "surface_type_id": SURFACE_TYPES[surface_type_name],
        "verified_center_count": len(verified_offsets),
        "dense_node_count": width * height if width is not None and height is not None else None,
        "materials": sorted({material for _polygon, material in plane_polygons}),
        "roof_component_face_count": len(component_faces),
        "roof_component_materials": sorted({material for _face, material in component_faces}),
        "exclude_placements": [
            {
                "land_data_id": parse_int(row["land_data_id"], f"model {model_id} exclusion land"),
                "object_index": parse_int(row["object_index"], f"model {model_id} exclusion object"),
                "reason": str(row["reason"]),
            }
            for row in spec.get("exclude_placements", [])
        ],
        "allowed_widths": allowed_widths,
        "allowed_heights": allowed_heights,
        "exclude_material_contains": [str(value).lower() for value in spec.get("exclude_material_contains", ["kage"])],
    }


def mesh_rectangle_for_placement(
    building_models: NarcArchive,
    spec: dict[str, Any],
    placement: BuildingPlacement,
) -> tuple[int, int, int, int, int]:
    """Rasterize the selected plane's full connected roof component."""

    _name, position_scale, horizontal_faces = model_geometry(building_models, placement.model_id)
    selected_plane_polygons: list[list[tuple[float, float]]] = []
    for raw_y, face, _material in horizontal_faces:
        scaled_height = raw_y * position_scale * MODEL_FX32_SCALE
        if scaled_height % 65536 != 0:
            continue
        if scaled_height // 65536 != spec["relative_height_fx32"]:
            continue
        selected_plane_polygons.append(
            [
                (
                    vertex[0] * position_scale / 65536 / 4096,
                    vertex[2] * position_scale / 65536 / 4096,
                )
                for vertex in face
            ]
        )
    require(
        selected_plane_polygons,
        f"model {placement.model_id}: selected plane disappeared",
    )

    component_scale, component_faces = connected_roof_component_faces(building_models, spec)
    require(component_scale == position_scale, f"model {placement.model_id}: inconsistent component scale")
    component_polygons = [
        [
            (
                vertex[0] * position_scale / 65536 / 4096,
                vertex[2] * position_scale / 65536 / 4096,
            )
            for vertex in face
        ]
        for face, _material in component_faces
    ]

    origin_x = 16 + placement.x_fx32 / FX32_PER_TILE
    origin_y = 16 + placement.z_fx32 / FX32_PER_TILE

    def rasterize(polygons: list[list[tuple[float, float]]]) -> set[tuple[int, int]]:
        minimum_x = math.floor(min(origin_x + x for polygon in polygons for x, _y in polygon)) - 1
        maximum_x = math.ceil(max(origin_x + x for polygon in polygons for x, _y in polygon)) + 1
        minimum_y = math.floor(min(origin_y + y for polygon in polygons for _x, y in polygon)) - 1
        maximum_y = math.ceil(max(origin_y + y for polygon in polygons for _x, y in polygon)) + 1
        return {
            (tile_x, tile_y)
            for tile_y in range(minimum_y, maximum_y + 1)
            for tile_x in range(minimum_x, maximum_x + 1)
            if any(
                point_in_polygon_inclusive(
                    tile_x + 0.5 - origin_x,
                    tile_y + 0.5 - origin_y,
                    polygon,
                )
                for polygon in polygons
            )
        }

    selected_plane_tiles = rasterize(selected_plane_polygons)
    component_tiles = rasterize(component_polygons)
    require(
        selected_plane_tiles,
        f"land {placement.land_data_id} object {placement.object_index}: selected plane has no tile centers",
    )
    require(
        selected_plane_tiles <= component_tiles,
        f"land {placement.land_data_id} object {placement.object_index}: connected roof omits selected plane centers",
    )
    min_x = min(x for x, _y in component_tiles)
    max_x = max(x for x, _y in component_tiles)
    min_y = min(y for _x, y in component_tiles)
    max_y = max(y for _x, y in component_tiles)
    width = max_x - min_x + 1
    height = max_y - min_y + 1
    require(
        len(component_tiles) == width * height,
        f"land {placement.land_data_id} object {placement.object_index}: connected roof component is not dense",
    )
    require(width in spec["allowed_widths"], f"land {placement.land_data_id} object {placement.object_index}: unexpected mesh width {width}")
    require(height in spec["allowed_heights"], f"land {placement.land_data_id} object {placement.object_index}: unexpected mesh height {height}")
    return min_x, min_y, width, height, len(component_tiles - selected_plane_tiles)


def model_bounds_rectangle_for_placement(
    building_models: NarcArchive,
    spec: dict[str, Any],
    placement: BuildingPlacement,
) -> tuple[int, int, int, int]:
    """Create a dense conservative rectangle from projected non-shadow geometry."""

    _name, position_scale, faces = model_all_faces(building_models, placement.model_id)
    excluded = spec["exclude_material_contains"]
    included_faces = [
        face
        for face, material in faces
        if not any(fragment in material.lower() for fragment in excluded)
    ]
    require(included_faces, f"model {placement.model_id}: all faces were excluded from authored bounds")
    vertices = [vertex for face in included_faces for vertex in face]
    x_values = [vertex[0] * position_scale / 65536 / 4096 for vertex in vertices]
    z_values = [vertex[2] * position_scale / 65536 / 4096 for vertex in vertices]
    origin_x = 16 + placement.x_fx32 / FX32_PER_TILE
    origin_y = 16 + placement.z_fx32 / FX32_PER_TILE
    min_x = math.ceil(origin_x + min(x_values) - 0.5)
    max_x = math.floor(origin_x + max(x_values) - 0.5)
    min_y = math.ceil(origin_y + min(z_values) - 0.5)
    max_y = math.floor(origin_y + max(z_values) - 0.5)
    width = max_x - min_x + 1
    height = max_y - min_y + 1
    require(width in spec["allowed_widths"], f"land {placement.land_data_id} object {placement.object_index}: unexpected authored width {width}")
    require(height in spec["allowed_heights"], f"land {placement.land_data_id} object {placement.object_index}: unexpected authored height {height}")
    require(1 <= width <= 32 and 1 <= height <= 32 and width * height <= 255, f"model {placement.model_id}: invalid authored bounds")
    return min_x, min_y, width, height


def roof_triangles_for_model(
    building_models: NarcArchive,
    spec: dict[str, Any],
) -> list[tuple[tuple[Fraction, Fraction, Fraction], ...]]:
    """Triangulate eligible roof faces in exact model-local FX32 units."""

    if spec["generation"] == "mesh_plane":
        position_scale, faces = connected_roof_component_faces(building_models, spec)
    else:
        _name, position_scale, all_faces = model_all_faces(building_models, spec["model_id"])
        excluded = spec["exclude_material_contains"]
        faces = [
            (face, material)
            for face, material in all_faces
            if not any(fragment in material.lower() for fragment in excluded)
        ]

    factor = Fraction(position_scale, 4096)
    triangles: list[tuple[tuple[Fraction, Fraction, Fraction], ...]] = []
    for face, _material in faces:
        vertices = [
            (Fraction(x) * factor, Fraction(y) * factor, Fraction(z) * factor)
            for x, y, z in face
        ]
        triangles.extend(
            (vertices[0], vertices[index], vertices[index + 1])
            for index in range(1, len(vertices) - 1)
        )
    require(triangles, f"model {spec['model_id']}: no roof-sampling triangles remain")
    return triangles


def sample_triangle_height(
    x: Fraction,
    z: Fraction,
    triangle: tuple[tuple[Fraction, Fraction, Fraction], ...],
) -> Fraction | None:
    a, b, c = triangle
    denominator = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
    if denominator == 0:
        return None
    weight_a = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / denominator
    weight_b = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / denominator
    weight_c = 1 - weight_a - weight_b
    if min(weight_a, weight_b, weight_c) < 0:
        return None
    return weight_a * a[1] + weight_b * b[1] + weight_c * c[1]


def ceil_fraction(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def sample_roof_height_grid_q4(
    triangles: list[tuple[tuple[Fraction, Fraction, Fraction], ...]],
    placement: BuildingPlacement,
    min_x: int,
    min_y: int,
    width: int,
    height: int,
) -> tuple[list[list[int]], list[tuple[int, int]]]:
    """Sample the highest rendered surface at every authored tile center.

    A conservative authored rectangle can include centers just outside the
    projected mesh silhouette. Those explicit continuity nodes inherit the
    nearest sampled height; the returned coordinates keep that approximation
    visible in the generated audit report.
    """

    origin_x_fx32 = 16 * FX32_PER_TILE + placement.x_fx32
    origin_z_fx32 = 16 * FX32_PER_TILE + placement.z_fx32
    relative_heights: list[list[Fraction | None]] = []
    valid_samples: list[tuple[int, int, Fraction]] = []
    for grid_y in range(height):
        row: list[Fraction | None] = []
        for grid_x in range(width):
            tile_x = min_x + grid_x
            tile_y = min_y + grid_y
            query_x = Fraction(tile_x * FX32_PER_TILE + FX32_PER_TILE // 2 - origin_x_fx32)
            query_z = Fraction(tile_y * FX32_PER_TILE + FX32_PER_TILE // 2 - origin_z_fx32)
            hits = [
                sampled
                for triangle in triangles
                if (sampled := sample_triangle_height(query_x, query_z, triangle)) is not None
            ]
            height_fx32 = max(hits) if hits else None
            row.append(height_fx32)
            if height_fx32 is not None:
                valid_samples.append((grid_x, grid_y, height_fx32))
        relative_heights.append(row)

    fallback_nodes = [
        (grid_x, grid_y)
        for grid_y, row in enumerate(relative_heights)
        for grid_x, value in enumerate(row)
        if value is None
    ]
    require(valid_samples, f"land {placement.land_data_id} object {placement.object_index}: roof rectangle misses every rendered face")
    for grid_y, row in enumerate(relative_heights):
        for grid_x, value in enumerate(row):
            if value is not None:
                continue
            _nearest_x, _nearest_y, nearest_height = min(
                valid_samples,
                key=lambda sample: (
                    abs(sample[0] - grid_x) + abs(sample[1] - grid_y),
                    sample[1],
                    sample[0],
                ),
            )
            row[grid_x] = nearest_height

    height_grid_q4 = [
        [
            ceil_fraction((Fraction(placement.y_fx32) + value) / 16)
            for value in row
            if value is not None
        ]
        for row in relative_heights
    ]
    require(all(len(row) == width for row in height_grid_q4), "internal roof height fill failure")
    return height_grid_q4, fallback_nodes


def partition_constant_height_rectangles(
    height_grid: list[list[int]],
) -> list[tuple[int, int, int, int, int]]:
    """Greedily cover a tiny dense grid with large equal-height rectangles."""

    height = len(height_grid)
    require(height != 0 and height_grid[0], "cannot partition an empty height grid")
    width = len(height_grid[0])
    require(all(len(row) == width for row in height_grid), "height grid is ragged")
    remaining = {(x, y) for y in range(height) for x in range(width)}
    rectangles: list[tuple[int, int, int, int, int]] = []
    while remaining:
        best: tuple[int, int, int, int, int, int, int, int, int] | None = None
        for min_y in range(height):
            for min_x in range(width):
                if (min_x, min_y) not in remaining:
                    continue
                value = height_grid[min_y][min_x]
                for max_y in range(min_y, height):
                    for max_x in range(min_x, width):
                        cells = {
                            (x, y)
                            for y in range(min_y, max_y + 1)
                            for x in range(min_x, max_x + 1)
                        }
                        if not cells <= remaining or any(
                            height_grid[y][x] != value for x, y in cells
                        ):
                            continue
                        candidate = (
                            len(cells),
                            -min_y,
                            -min_x,
                            max_y - min_y + 1,
                            max_x - min_x + 1,
                            min_x,
                            min_y,
                            max_x,
                            max_y,
                        )
                        if best is None or candidate > best:
                            best = candidate
        require(best is not None, "height rectangle partition stalled")
        _area, _sort_y, _sort_x, rect_height, rect_width, min_x, min_y, max_x, max_y = best
        value = height_grid[min_y][min_x]
        rectangles.append((min_x, min_y, rect_width, rect_height, value))
        remaining -= {
            (x, y)
            for y in range(min_y, max_y + 1)
            for x in range(min_x, max_x + 1)
        }
    return rectangles


def partition_tile_rectangles(
    tiles: set[tuple[int, int]],
) -> list[tuple[int, int, int, int]]:
    """Greedily cover an arbitrary 32x32 tile mask with dense rectangles."""

    remaining = set(tiles)
    rectangles: list[tuple[int, int, int, int]] = []
    while remaining:
        best: tuple[int, int, int, int, int, int] | None = None
        for min_x, min_y in sorted(remaining, key=lambda point: (point[1], point[0])):
            maximum_width = 0
            while (min_x + maximum_width, min_y) in remaining:
                maximum_width += 1
            for width in range(1, maximum_width + 1):
                height = 1
                while min_y + height < CELL_SIZE and all(
                    (x, min_y + height) in remaining
                    for x in range(min_x, min_x + width)
                ):
                    height += 1
                candidate = (
                    width * height,
                    -min_y,
                    -min_x,
                    height,
                    width,
                    min_x,
                )
                if best is None or candidate > best:
                    best = candidate
        require(best is not None, "native-ground rectangle partition stalled")
        _area, neg_y, _neg_x, height, width, min_x = best
        min_y = -neg_y
        require(width * height <= 0xFF, "native-ground rectangle exceeds u8 node IDs")
        rectangles.append((min_x, min_y, width, height))
        remaining -= {
            (x, y)
            for y in range(min_y, min_y + height)
            for x in range(min_x, min_x + width)
        }
    return rectangles


def read_land_visual_models(
    land_narc: NarcArchive,
    land_data_id: int,
) -> list[tuple[dict[str, Any], int]]:
    """Read the embedded land NSBMD and return models with their position scale."""

    data = land_narc.files[land_data_id]
    permission_size, object_size, model_size, _bdhc_size = struct.unpack_from("<4I", data, 0)
    magic, unknown_size = struct.unpack_from("<HH", data, 16)
    require(magic == LAND_MAGIC, f"land data {land_data_id} has bad magic {magic:#x}")
    model_offset = LAND_HEADER_SIZE + unknown_size + permission_size + object_size
    model_data = data[model_offset : model_offset + model_size]
    bmd0, _bmd0_offset = visual_probe.extract_bmd0(model_data)
    require(bmd0 is not None, f"land data {land_data_id} has no embedded BMD0")
    models = visual_probe.parse_nsbmd_models(bmd0)
    mdl0_offset = struct.unpack_from("<I", bmd0, 0x10)[0]
    mdl0 = bmd0[mdl0_offset:]
    directory = visual_probe.parse_mdl0_model_directory(mdl0)
    require(len(models) == len(directory), f"land data {land_data_id} model directory mismatch")
    result = []
    for model, (directory_name, directory_offset) in zip(models, directory):
        require(model["name"] == directory_name, f"land data {land_data_id} model name mismatch")
        position_scale = struct.unpack_from("<i", mdl0, directory_offset + 28)[0]
        result.append((model, position_scale))
    return result


def project_land_vertex(raw: int, position_scale: int) -> float:
    return 16.0 + raw * position_scale / (65536.0 * 4096.0)


def horizontal_material_tiles(
    model: dict[str, Any],
    position_scale: int,
    material_pattern: re.Pattern[str],
) -> tuple[set[tuple[int, int]], set[str]]:
    """Decode reviewed flat flower quads from their stable UV base edge."""

    polygons = {polygon["index"]: polygon for polygon in model["polygons"]}
    tiles: set[tuple[int, int]] = set()
    matched_materials: set[str] = set()
    for pair in model["render_pairs"]:
        material = model["material_names"][pair["material_index"]]
        if material_pattern.fullmatch(material) is None:
            continue
        matched_materials.add(material)
        polygon = polygons[pair["polygon_index"]]
        for face in visual_probe.parse_display_faces_with_uv(polygon["display_list"]):
            require(len(face) == 4, f"material {material} contains a non-quad common flower face")
            span_u = max(uv[0] for _position, uv in face) - min(uv[0] for _position, uv in face)
            span_v = max(uv[1] for _position, uv in face) - min(uv[1] for _position, uv in face)
            texture_width = round(abs(span_u) / 256)
            texture_height = round(abs(span_v) / 256)
            require(texture_width > 0 and texture_height > 0, f"material {material} has an empty UV span")
            require(
                abs(abs(span_u) - texture_width * 256) <= 10
                and abs(abs(span_v) - texture_height * 256) <= 10,
                f"material {material} has a non-tile-aligned UV span",
            )
            projected_edge = [
                (
                    project_land_vertex(position[0], position_scale),
                    project_land_vertex(position[2], position_scale),
                )
                for position, _uv in face[-2:]
            ]
            edge_span_x = abs(projected_edge[1][0] - projected_edge[0][0])
            edge_span_y = abs(projected_edge[1][1] - projected_edge[0][1])
            if edge_span_x >= edge_span_y:
                require(
                    edge_span_y <= 0.05 and abs(edge_span_x - texture_width) <= 0.25,
                    f"material {material} has no stable horizontal C/D edge",
                )
                width, height = texture_width, texture_height
            else:
                require(
                    edge_span_x <= 0.05 and abs(edge_span_y - texture_height) <= 0.25,
                    f"material {material} has no stable vertical C/D edge",
                )
                width, height = texture_height, texture_width
            min_x = math.floor(min(point[0] for point in projected_edge) + 1e-6)
            min_y = math.floor(min(point[1] for point in projected_edge) + 1e-6)
            tiles |= {
                (x, y)
                for y in range(min_y, min_y + height)
                for x in range(min_x, min_x + width)
            }
    return tiles, matched_materials


def billboard_material_tiles(
    model: dict[str, Any],
    position_scale: int,
    material_names: set[str],
) -> tuple[set[tuple[int, int]], set[str]]:
    """Map each reviewed vertical flower billboard to the tile under its UV base."""

    polygons = {polygon["index"]: polygon for polygon in model["polygons"]}
    tiles: set[tuple[int, int]] = set()
    matched_materials: set[str] = set()
    for pair in model["render_pairs"]:
        material = model["material_names"][pair["material_index"]]
        if material not in material_names:
            continue
        matched_materials.add(material)
        polygon = polygons[pair["polygon_index"]]
        for face in visual_probe.parse_display_faces_with_uv(polygon["display_list"]):
            minimum_v = min(uv[1] for _position, uv in face)
            base_positions = [position for position, uv in face if uv[1] == minimum_v]
            require(len(base_positions) == 2, f"material {material} has an ambiguous UV base edge")
            projected = [
                (
                    project_land_vertex(position[0], position_scale),
                    project_land_vertex(position[2], position_scale),
                )
                for position in base_positions
            ]
            span_x = abs(projected[1][0] - projected[0][0])
            span_y = abs(projected[1][1] - projected[0][1])
            require(
                max(span_x, span_y) >= 0.75 and min(span_x, span_y) <= 0.05,
                f"material {material} has a non-axis-aligned or undersized UV base edge",
            )
            tile = (
                math.floor(min(point[0] for point in projected) + 1e-6),
                math.floor(min(point[1] for point in projected) + 1e-6),
            )
            require(
                0 <= tile[0] < CELL_SIZE and 0 <= tile[1] < CELL_SIZE,
                f"material {material} billboard base leaves its land block",
            )
            tiles.add(tile)
    return tiles, matched_materials


def generate_catalog(
    manifest: dict[str, Any],
    matrix_narc: NarcArchive,
    land_narc: NarcArchive,
    building_models: NarcArchive,
) -> tuple[list[CatalogInstance], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    matrix_ids = [parse_int(value, "matrix id") for value in manifest["matrix_ids"]]
    cells = [cell for matrix_id in matrix_ids for cell in read_matrix_cells(matrix_narc, matrix_id)]
    cell_by_location = {(cell.matrix_id, cell.matrix_x, cell.matrix_y): cell for cell in cells}
    cells_by_land: dict[int, list[MatrixCell]] = defaultdict(list)
    for cell in cells:
        cells_by_land[cell.land_data_id].append(cell)

    roof_specs = [verify_model_template(building_models, spec) for spec in manifest["models"]]
    point_specs = [
        verify_model_template(building_models, spec)
        for spec in manifest.get("point_surfaces", [])
    ]
    verified_specs = roof_specs + point_specs
    specs_by_model = {spec["model_id"]: spec for spec in verified_specs}
    require(len(specs_by_model) == len(verified_specs), "manifest repeats a building model")

    raw_native_ground = manifest.get("native_ground_material_surface")
    require(raw_native_ground is not None, "manifest has no native-ground material surface rule")
    native_ground_surface_type = str(raw_native_ground["surface_type"])
    require(native_ground_surface_type == "flowerbed", "native-ground material rule must use Flowerbed")
    native_ground_surface_type_id = SURFACE_TYPES[native_ground_surface_type]
    native_ground_confidence = str(raw_native_ground.get("confidence", "mesh_verified"))
    require(native_ground_confidence == "mesh_verified", "native-ground material rule must be mesh-verified")
    flat_material_pattern_text = raw_native_ground.get("flat_material_pattern")
    flat_material_pattern = None
    if flat_material_pattern_text is not None:
        flat_material_pattern_text = str(flat_material_pattern_text)
        require(
            flat_material_pattern_text.startswith("^") and flat_material_pattern_text.endswith("$"),
            "native-ground flat material pattern must be anchored",
        )
        flat_material_pattern = re.compile(flat_material_pattern_text, re.IGNORECASE)
    billboard_material_names = {str(name) for name in raw_native_ground.get("billboard_material_names", [])}

    placements: dict[int, list[BuildingPlacement]] = {}
    for land_data_id in sorted(cells_by_land):
        placements[land_data_id] = read_land_objects(land_narc, land_data_id)

    common_pattern = re.compile(
        str(manifest.get("common_model_name_pattern", r"(^|_)(pc|fs|h0[123])($|_)")),
        re.IGNORECASE,
    )
    discovered_common: dict[int, dict[str, Any]] = {}
    for source_cell in cells:
        for placement in placements[source_cell.land_data_id]:
            model_name, _position_scale, _faces = model_geometry(building_models, placement.model_id)
            if common_pattern.search(model_name):
                row = discovered_common.setdefault(
                    placement.model_id,
                    {"model_id": placement.model_id, "model_name": model_name, "placements": 0},
                )
                row["placements"] += 1

    roof_model_ids = {spec["model_id"] for spec in roof_specs}
    missing_common = sorted(set(discovered_common) - roof_model_ids)
    require(
        not missing_common,
        "manifest misses common outdoor building models: "
        + ", ".join(f"{model_id} ({discovered_common[model_id]['model_name']})" for model_id in missing_common),
    )
    extra_models = sorted(roof_model_ids - set(discovered_common))
    require(
        not extra_models,
        "manifest models have no matching outdoor placements: " + ", ".join(map(str, extra_models)),
    )
    discovered_placement_keys = {
        (placement.model_id, placement.land_data_id, placement.object_index)
        for source_cell in cells
        for placement in placements[source_cell.land_data_id]
        if placement.model_id in discovered_common
    }
    for spec in verified_specs:
        for exclusion in spec["exclude_placements"]:
            key = (spec["model_id"], exclusion["land_data_id"], exclusion["object_index"])
            require(key in discovered_placement_keys, f"model {spec['model_id']}: exclusion does not match a common placement: {key[1:]}")

    point_coverage: list[dict[str, Any]] = []
    for spec in point_specs:
        placement_count = sum(
            1
            for source_cell in cells
            for placement in placements[source_cell.land_data_id]
            if placement.model_id == spec["model_id"]
        )
        require(
            placement_count != 0,
            f"point surface model {spec['model_id']} has no outdoor placements",
        )
        point_coverage.append(
            {
                "model_id": spec["model_id"],
                "model_name": spec["model_name"],
                "surface_type": spec["surface_type"],
                "placements": placement_count,
            }
        )

    pending: list[dict[str, Any]] = []
    logical_groups: list[dict[str, Any]] = []
    next_group = 1
    excluded_occurrences = 0
    next_local_surface_id_by_anchor: dict[tuple[int, int, int], int] = defaultdict(lambda: 1)
    affected_cell_signatures: dict[tuple[int, int, int], set[tuple[Any, ...]]] = defaultdict(set)
    triangles_by_model: dict[int, list[tuple[tuple[Fraction, Fraction, Fraction], ...]]] = {}

    for source_cell in sorted(cells, key=lambda c: (c.matrix_id, c.matrix_y, c.matrix_x)):
        for placement in placements[source_cell.land_data_id]:
            spec = specs_by_model.get(placement.model_id)
            if spec is None:
                continue
            exclusion = next(
                (
                    row
                    for row in spec["exclude_placements"]
                    if row["land_data_id"] == placement.land_data_id
                    and row["object_index"] == placement.object_index
                ),
                None,
            )
            if exclusion is not None:
                excluded_occurrences += 1
                continue
            group_id = next_group
            next_group += 1
            anchor_key = (source_cell.matrix_id, source_cell.matrix_x, source_cell.matrix_y)
            anchor_local_surface_id = next_local_surface_id_by_anchor[anchor_key]
            require(
                anchor_local_surface_id <= 15,
                f"matrix {source_cell.matrix_id} block ({source_cell.matrix_x},{source_cell.matrix_y}) has more than 15 logical roofs",
            )
            next_local_surface_id_by_anchor[anchor_key] += 1
            group_name = (
                f"m{source_cell.matrix_id}_x{source_cell.matrix_x}_y{source_cell.matrix_y}_"
                f"land{source_cell.land_data_id}_obj{placement.object_index}_model{placement.model_id}"
            )
            if spec["generation"] == "mesh_plane":
                (
                    local_min_x,
                    local_min_y,
                    rectangle_width,
                    rectangle_height,
                    mesh_component_added_node_count,
                ) = mesh_rectangle_for_placement(building_models, spec, placement)
                world_min_x = source_cell.matrix_x * CELL_SIZE + local_min_x
                world_min_y = source_cell.matrix_y * CELL_SIZE + local_min_y
            elif spec["generation"] == "authored_model_bounds":
                local_min_x, local_min_y, rectangle_width, rectangle_height = model_bounds_rectangle_for_placement(
                    building_models, spec, placement
                )
                mesh_component_added_node_count = 0
                world_min_x = source_cell.matrix_x * CELL_SIZE + local_min_x
                world_min_y = source_cell.matrix_y * CELL_SIZE + local_min_y
            elif spec["generation"] == "authored_node":
                local_min_x = math.floor(16 + placement.x_fx32 / FX32_PER_TILE)
                local_min_y = math.floor(16 + placement.z_fx32 / FX32_PER_TILE)
                rectangle_width = 1
                rectangle_height = 1
                mesh_component_added_node_count = 0
                world_min_x = source_cell.matrix_x * CELL_SIZE + local_min_x
                world_min_y = source_cell.matrix_y * CELL_SIZE + local_min_y
            else:
                raise RuntimeError(
                    f"model {placement.model_id}: unsupported generation mode {spec['generation']}"
                )

            if spec["generation"] == "authored_node":
                height_grid_q4 = [[
                    (placement.y_fx32 + spec["relative_height_fx32"] + 15) // 16
                ]]
                fallback_nodes: list[tuple[int, int]] = []
            else:
                triangles = triangles_by_model.get(placement.model_id)
                if triangles is None:
                    triangles = roof_triangles_for_model(building_models, spec)
                    triangles_by_model[placement.model_id] = triangles
                height_grid_q4, fallback_nodes = sample_roof_height_grid_q4(
                    triangles,
                    placement,
                    local_min_x,
                    local_min_y,
                    rectangle_width,
                    rectangle_height,
                )
            height_rectangles = partition_constant_height_rectangles(height_grid_q4)
            logical_groups.append(
                {
                    "id": group_id,
                    "name": group_name,
                    "model_id": placement.model_id,
                    "model_name": spec["model_name"],
                    "surface_type": spec["surface_type"],
                    "source_land_data_id": source_cell.land_data_id,
                    "source_object_index": placement.object_index,
                    "anchor_local_surface_id": anchor_local_surface_id,
                    "width": rectangle_width,
                    "height": rectangle_height,
                    "height_rectangle_count": len(height_rectangles),
                    "mesh_fallback_node_count": len(fallback_nodes),
                    "mesh_fallback_nodes": [list(node) for node in fallback_nodes],
                    "mesh_component_added_node_count": mesh_component_added_node_count,
                    "minimum_height_fx32": min(min(row) for row in height_grid_q4) << 4,
                    "maximum_height_fx32": max(max(row) for row in height_grid_q4) << 4,
                    "confidence": spec["confidence"],
                }
            )

            for rectangle_x, rectangle_y, rectangle_width, rectangle_height, full_height_q4 in height_rectangles:
                require(0 < full_height_q4 <= 0xFFFFFF, f"{group_name}: Q4 height does not fit paged encoding")
                height_q4 = full_height_q4 & 0xFFFF
                height_page = full_height_q4 >> 16
                require(
                    height_page != NATIVE_GROUND_HEIGHT_PAGE,
                    f"{group_name}: height uses the native-ground sentinel page",
                )
                height_world_min_x = world_min_x + rectangle_x
                height_world_min_y = world_min_y + rectangle_y
                max_world_x = height_world_min_x + rectangle_width - 1
                max_world_y = height_world_min_y + rectangle_height - 1
                min_block_x, max_block_x = height_world_min_x // CELL_SIZE, max_world_x // CELL_SIZE
                min_block_y, max_block_y = height_world_min_y // CELL_SIZE, max_world_y // CELL_SIZE
                for block_y in range(min_block_y, max_block_y + 1):
                    for block_x in range(min_block_x, max_block_x + 1):
                        target_cell = cell_by_location.get((source_cell.matrix_id, block_x, block_y))
                        require(target_cell is not None, f"{group_name}: roof leaves matrix bounds at ({block_x},{block_y})")
                        clip_min_x = max(height_world_min_x, block_x * CELL_SIZE)
                        clip_max_x = min(max_world_x, (block_x + 1) * CELL_SIZE - 1)
                        clip_min_y = max(height_world_min_y, block_y * CELL_SIZE)
                        clip_max_y = min(max_world_y, (block_y + 1) * CELL_SIZE - 1)
                        fragment_min_x = clip_min_x - block_x * CELL_SIZE
                        fragment_min_y = clip_min_y - block_y * CELL_SIZE
                        width = clip_max_x - clip_min_x + 1
                        height = clip_max_y - clip_min_y + 1
                        anchor_block_dx = source_cell.matrix_x - block_x
                        anchor_block_dy = source_cell.matrix_y - block_y
                        require(-128 <= anchor_block_dx <= 127, f"{group_name}: anchor x delta does not fit s8")
                        require(-128 <= anchor_block_dy <= 127, f"{group_name}: anchor y delta does not fit s8")
                        signature = (
                            fragment_min_x,
                            fragment_min_y,
                            width,
                            height,
                            height_q4,
                            height_page,
                            anchor_block_dx,
                            anchor_block_dy,
                            anchor_local_surface_id,
                            spec["surface_type_id"],
                            placement.model_id,
                            placement.object_index,
                        )
                        affected_cell_signatures[(target_cell.matrix_id, block_x, block_y)].add(signature)
                        pending.append(
                            {
                                "target_cell": target_cell,
                                "min_x": fragment_min_x,
                                "min_y": fragment_min_y,
                                "width": width,
                                "height": height,
                                "height_q4": height_q4,
                                "height_page": height_page,
                                "anchor_block_dx": anchor_block_dx,
                                "anchor_block_dy": anchor_block_dy,
                                "anchor_local_surface_id": anchor_local_surface_id,
                                "surface_type": spec["surface_type_id"],
                                "logical_group": group_id,
                                "source": group_name,
                                "confidence": spec["confidence"],
                            }
                        )

    elevated_tiles_by_land: dict[int, set[tuple[int, int]]] = defaultdict(set)
    for row in pending:
        land_data_id = row["target_cell"].land_data_id
        elevated_tiles_by_land[land_data_id] |= {
            (x, y)
            for y in range(row["min_y"], row["min_y"] + row["height"])
            for x in range(row["min_x"], row["min_x"] + row["width"])
        }

    native_ground_material_audit: list[dict[str, Any]] = []
    unmatched_flower_like_materials: set[str] = set()
    native_tiles_by_land: dict[int, set[tuple[int, int]]] = defaultdict(set)
    native_materials_by_land: dict[int, set[str]] = defaultdict(set)
    native_ground_cross_block_audit: list[dict[str, Any]] = []
    for land_data_id in sorted(cells_by_land):
        for model, position_scale in read_land_visual_models(land_narc, land_data_id):
            if flat_material_pattern is None:
                flat_tiles, flat_materials = set(), set()
            else:
                flat_tiles, flat_materials = horizontal_material_tiles(
                    model, position_scale, flat_material_pattern
                )
            billboard_tiles, billboard_materials = billboard_material_tiles(
                model, position_scale, billboard_material_names
            )
            native_materials_by_land[land_data_id] |= flat_materials | billboard_materials
            for x, y in flat_tiles | billboard_tiles:
                if 0 <= x < CELL_SIZE and 0 <= y < CELL_SIZE:
                    native_tiles_by_land[land_data_id].add((x, y))
                    continue
                block_dx = x // CELL_SIZE
                block_dy = y // CELL_SIZE
                target_x = x % CELL_SIZE
                target_y = y % CELL_SIZE
                redirected_targets = set()
                for occurrence in cells_by_land[land_data_id]:
                    target_cell = cell_by_location.get(
                        (
                            occurrence.matrix_id,
                            occurrence.matrix_x + block_dx,
                            occurrence.matrix_y + block_dy,
                        )
                    )
                    require(
                        target_cell is not None,
                        f"native-ground material tile {(land_data_id, x, y)} leaves the mapped matrix",
                    )
                    redirected_targets.add((target_cell.land_data_id, target_x, target_y))
                require(
                    len(redirected_targets) == 1,
                    f"native-ground material tile {(land_data_id, x, y)} redirects differently across reused blocks",
                )
                target_land, target_x, target_y = next(iter(redirected_targets))
                if len(cells_by_land[target_land]) != 1:
                    native_ground_cross_block_audit.append(
                        {
                            "source_land_data_id": land_data_id,
                            "source_x": x,
                            "source_y": y,
                            "target_land_data_id": target_land,
                            "target_x": target_x,
                            "target_y": target_y,
                            "status": "excluded_reused_target_land",
                        }
                    )
                    continue
                native_tiles_by_land[target_land].add((target_x, target_y))
                native_ground_cross_block_audit.append(
                    {
                        "source_land_data_id": land_data_id,
                        "source_x": x,
                        "source_y": y,
                        "target_land_data_id": target_land,
                        "target_x": target_x,
                        "target_y": target_y,
                        "status": "represented",
                    }
                )
            for material in model["material_names"]:
                if "flower" in material.lower():
                    if (
                        (flat_material_pattern is None or flat_material_pattern.fullmatch(material) is None)
                        and material not in billboard_material_names
                    ):
                        unmatched_flower_like_materials.add(material)
    for land_data_id in sorted(native_tiles_by_land):
        flower_tiles = native_tiles_by_land[land_data_id]
        elevated_overlap = flower_tiles & elevated_tiles_by_land.get(land_data_id, set())
        flower_tiles -= elevated_overlap
        if not flower_tiles:
            continue
        rectangles = partition_tile_rectangles(flower_tiles)
        source_cell = sorted(
            cells_by_land[land_data_id],
            key=lambda cell: (cell.matrix_id, cell.matrix_y, cell.matrix_x),
        )[0]
        native_ground_material_audit.append(
            {
                "land_data_id": land_data_id,
                "materials": sorted(native_materials_by_land.get(land_data_id, set())),
                "nodes": len(flower_tiles),
                "rectangles": len(rectangles),
                "elevated_overlap_nodes_removed": len(elevated_overlap),
            }
        )
        for region_index, (min_x, min_y, width, height) in enumerate(rectangles):
            group_id = next_group
            next_group += 1
            group_name = f"land{land_data_id}_native_flower_rect{region_index}"
            logical_groups.append(
                {
                    "id": group_id,
                    "name": group_name,
                    "model_id": None,
                    "model_name": "native_ground_material",
                    "surface_type": native_ground_surface_type,
                    "source_land_data_id": land_data_id,
                    "source_object_index": None,
                    "anchor_local_surface_id": 0,
                    "width": width,
                    "height": height,
                    "height_rectangle_count": 1,
                    "height_mode": "native_ground",
                    "mesh_fallback_node_count": 0,
                    "mesh_fallback_nodes": [],
                    "mesh_component_added_node_count": 0,
                    "minimum_height_fx32": None,
                    "maximum_height_fx32": None,
                    "confidence": native_ground_confidence,
                }
            )
            signature = (
                min_x,
                min_y,
                width,
                height,
                0,
                NATIVE_GROUND_HEIGHT_PAGE,
                0,
                0,
                0,
                native_ground_surface_type_id,
                "native_ground_material",
            )
            for occurrence in cells_by_land[land_data_id]:
                affected_cell_signatures[
                    (occurrence.matrix_id, occurrence.matrix_x, occurrence.matrix_y)
                ].add(signature)
            pending.append(
                {
                    "target_cell": source_cell,
                    "min_x": min_x,
                    "min_y": min_y,
                    "width": width,
                    "height": height,
                    "height_q4": 0,
                    "height_page": NATIVE_GROUND_HEIGHT_PAGE,
                    "anchor_block_dx": 0,
                    "anchor_block_dy": 0,
                    "anchor_local_surface_id": 0,
                    "surface_type": native_ground_surface_type_id,
                    "logical_group": group_id,
                    "source": group_name,
                    "confidence": native_ground_confidence,
                }
            )

    # A catalog keyed only by land-data ID is safe only when every occurrence of
    # that ID receives the same local surface signatures.
    for land_data_id, land_cells in cells_by_land.items():
        signatures = [
            affected_cell_signatures.get((cell.matrix_id, cell.matrix_x, cell.matrix_y), set())
            for cell in land_cells
        ]
        if any(signatures):
            require(
                all(signature == signatures[0] for signature in signatures),
                f"land data {land_data_id} has occurrence-specific surface geometry",
            )

    unique: dict[tuple[Any, ...], CatalogInstance] = {}
    for row in pending:
        cell = row["target_cell"]
        key = (
            cell.land_data_id,
            row["min_x"],
            row["min_y"],
            row["width"],
            row["height"],
            row["height_q4"],
            row["height_page"],
            row["anchor_block_dx"],
            row["anchor_block_dy"],
            row["anchor_local_surface_id"],
            row["surface_type"],
        )
        unique[key] = CatalogInstance(
            cell.land_data_id,
            row["min_x"],
            row["min_y"],
            row["width"],
            row["height"],
            row["height_q4"],
            row["height_page"],
            row["anchor_block_dx"],
            row["anchor_block_dy"],
            row["anchor_local_surface_id"],
            row["surface_type"],
            row["logical_group"],
            row["source"],
            row["confidence"],
        )
    instances = sorted(unique.values(), key=lambda row: (row.land_data_id, row.min_y, row.min_x, row.source))

    by_land: dict[int, list[CatalogInstance]] = defaultdict(list)
    for instance in instances:
        by_land[instance.land_data_id].append(instance)
    for land_data_id, rows in by_land.items():
        require(len(rows) <= 255, f"land data {land_data_id} requires more than 255 instances")
        for left_index, left in enumerate(rows):
            for right in rows[left_index + 1 :]:
                overlaps = (
                    left.min_x < right.min_x + right.width
                    and right.min_x < left.min_x + left.width
                    and left.min_y < right.min_y + right.height
                    and right.min_y < left.min_y + left.height
                )
                require(not overlaps, f"land data {land_data_id} contains overlapping surface rectangles")

    coverage = {
        "pattern": common_pattern.pattern,
        "discovered_models": len(discovered_common),
        "manifest_models": len(roof_specs),
        "discovered_placements": sum(row["placements"] for row in discovered_common.values()),
        "excluded_placements": excluded_occurrences,
        "represented_placements": sum(
            group["surface_type"] == "rooftop" for group in logical_groups
        ),
        "represented_point_surfaces": sum(
            group["surface_type"] != "rooftop"
            and group.get("height_mode") != "native_ground"
            for group in logical_groups
        ),
        "represented_native_ground_surfaces": sum(
            group.get("height_mode") == "native_ground"
            for group in logical_groups
        ),
        "models": [discovered_common[model_id] for model_id in sorted(discovered_common)],
        "point_surface_models": point_coverage,
        "native_ground_material_pattern": (
            flat_material_pattern.pattern if flat_material_pattern is not None else None
        ),
        "native_ground_billboard_materials": sorted(billboard_material_names),
        "native_ground_material_audit": native_ground_material_audit,
        "native_ground_cross_block_audit": sorted(
            native_ground_cross_block_audit,
            key=lambda row: (row["source_land_data_id"], row["source_y"], row["source_x"]),
        ),
        "native_ground_nodes": sum(row["nodes"] for row in native_ground_material_audit),
        "native_ground_rectangles": sum(row["rectangles"] for row in native_ground_material_audit),
        "unmatched_flower_like_materials": sorted(unmatched_flower_like_materials),
    }
    require(
        coverage["represented_placements"] + coverage["excluded_placements"] == coverage["discovered_placements"],
        "common placement coverage count is inconsistent",
    )
    require(
        coverage["represented_point_surfaces"]
        == sum(row["placements"] for row in point_coverage),
        "point-surface placement coverage count is inconsistent",
    )
    require(
        coverage["represented_native_ground_surfaces"] == coverage["native_ground_rectangles"],
        "native-ground surface coverage count is inconsistent",
    )
    return instances, verified_specs, logical_groups, coverage


def render_outputs(
    instances: list[CatalogInstance],
    verified_specs: list[dict[str, Any]],
    logical_groups: list[dict[str, Any]],
    coverage: dict[str, Any],
) -> tuple[str, str, str]:
    template_shapes = sorted({(row.width, row.height) for row in instances})
    template_ids = {shape: index for index, shape in enumerate(template_shapes)}
    by_land: dict[int, list[CatalogInstance]] = defaultdict(list)
    for instance in instances:
        by_land[instance.land_data_id].append(instance)
    require(len(by_land) <= 0xFFFF, "roof catalog exceeds the u16 model-count field")
    require(len(instances) <= 0xFFFF, "roof catalog exceeds u16 instance addressing")
    require(len(template_shapes) <= 256, "roof catalog exceeds the u8 template ID")

    model_rows = []
    instance_rows = []
    report_instances = []
    first_instance = 0
    for land_data_id in sorted(by_land):
        rows = by_land[land_data_id]
        model_rows.append((land_data_id, first_instance, len(rows), 0))
        for row in rows:
            template_id = template_ids[(row.width, row.height)]
            instance_rows.append(
                (
                    row.min_x,
                    row.min_y,
                    template_id,
                    row.anchor_local_surface_id,
                    row.height_q4,
                    row.height_page,
                    row.surface_type,
                    row.anchor_block_dx,
                    row.anchor_block_dy,
                    row,
                )
            )
            report_instances.append(
                {
                    "land_data_id": land_data_id,
                    "min_x": row.min_x,
                    "min_y": row.min_y,
                    "width": row.width,
                    "height": row.height,
                    "height_fx32": None
                    if row.height_page == NATIVE_GROUND_HEIGHT_PAGE
                    else (row.height_page << 20) + (row.height_q4 << 4),
                    "height_mode": "native_ground"
                    if row.height_page == NATIVE_GROUND_HEIGHT_PAGE
                    else "catalog",
                    "height_q4": row.height_q4,
                    "height_page": row.height_page,
                    "anchor_block_dx": row.anchor_block_dx,
                    "anchor_block_dy": row.anchor_block_dy,
                    "template_id": template_id,
                    "local_surface_id": row.anchor_local_surface_id,
                    "surface_type": next(
                        name for name, value in SURFACE_TYPES.items()
                        if value == row.surface_type
                    ),
                    "logical_group": row.logical_group,
                    "source": row.source,
                    "confidence": row.confidence,
                }
            )
        first_instance += len(rows)

    header = "\n".join(
        [
            "#ifndef GUARD_GENERATED_OVERWORLD_WILD_ROOF_CATALOG_COUNTS_H",
            "#define GUARD_GENERATED_OVERWORLD_WILD_ROOF_CATALOG_COUNTS_H",
            "",
            f"#define OWBD_GENERATED_SURFACE_MODEL_COUNT {len(model_rows)}",
            f"#define OWBD_GENERATED_SURFACE_INSTANCE_COUNT {len(instance_rows)}",
            f"#define OWBD_GENERATED_SURFACE_TEMPLATE_COUNT {len(template_shapes)}",
            "",
            "#endif // GUARD_GENERATED_OVERWORLD_WILD_ROOF_CATALOG_COUNTS_H",
            "",
        ]
    )

    include_lines = [
        "/* Generated by tools/generate_overworld_wild_roof_catalog.py. */",
        "/* Do not edit by hand; edit data/overworld_wild_roof_catalog_manifest.json. */",
        "",
        "/* OverworldWildSurfaceModelDirectoryEntry initializers */",
        "#define OWBD_GENERATED_SURFACE_MODEL_ROWS \\",
    ]
    for index, (land_data_id, first, count, reserved) in enumerate(model_rows):
        suffix = " \\" if index + 1 < len(model_rows) else ""
        include_lines.append(f"    {{{land_data_id}, {first}, {count}, {reserved}}},{suffix}")
    include_lines.extend(["", "/* OverworldWildSurfaceInstance initializers */", "#define OWBD_GENERATED_SURFACE_INSTANCE_ROWS \\"])
    for index, (
        min_x,
        min_y,
        template_id,
        local_id,
        height_q4,
        height_page,
        surface_type,
        anchor_dx,
        anchor_dy,
        row,
    ) in enumerate(instance_rows):
        suffix = " \\" if index + 1 < len(instance_rows) else ""
        include_lines.append(
            f"    {{{min_x}, {min_y}, {template_id}, {local_id}, 0x{height_q4:04X}, "
            f"{height_page}, {surface_type}, {anchor_dx}, {anchor_dy}}}, "
            f"/* group {row.logical_group}: {row.source}; {row.confidence} */{suffix}"
        )
    include_lines.extend(["", "/* OverworldWildSurfaceTemplate initializers */", "#define OWBD_GENERATED_SURFACE_TEMPLATE_ROWS \\"])
    for index, (width, height) in enumerate(template_shapes):
        suffix = " \\" if index + 1 < len(template_shapes) else ""
        include_lines.append(f"    {{{width}, {height}}},{suffix}")
    include_lines.append("")

    report = {
        "schema_version": 2,
        "coverage": coverage,
        "height_sampling": {
            "method": "highest_eligible_triangle_at_tile_center",
            "quantization_fx32": 16,
            "quantization_direction": "ceiling",
            "missing_mesh_policy": "nearest_manhattan_then_topmost_leftmost",
            "mesh_footprint_method": "edge_connected_projected_faces_seeded_from_reviewed_plane",
            "mesh_triangle_source": "connected_roof_component",
            "authored_bounds_triangle_source": "all_non_shadow_faces",
        },
        "models": [
            {key: value for key, value in spec.items()}
            for spec in verified_specs
        ],
        "logical_groups": logical_groups,
        "templates": [
            {"template_id": index, "width": width, "height": height}
            for index, (width, height) in enumerate(template_shapes)
        ],
        "instances": report_instances,
        "counts": {
            "models": len(model_rows),
            "instances": len(instance_rows),
            "templates": len(template_shapes),
            "logical_groups": len(logical_groups),
            "authored_nodes": sum(
                group["width"] * group["height"] for group in logical_groups
            ),
            "height_rectangles": sum(
                group["height_rectangle_count"] for group in logical_groups
            ),
            "mesh_fallback_nodes": sum(
                group["mesh_fallback_node_count"] for group in logical_groups
            ),
            "mesh_component_added_nodes": sum(
                group["mesh_component_added_node_count"] for group in logical_groups
            ),
        },
    }
    return header, "\n".join(include_lines), json.dumps(report, indent=2, sort_keys=True) + "\n"


def write_or_check(path: Path, content: str, check: bool) -> None:
    if check:
        require(path.exists(), f"generated file is missing: {path}")
        require(path.read_text(encoding="utf-8") == content, f"generated file is stale: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=root / "data/overworld_wild_roof_catalog_manifest.json")
    parser.add_argument("--matrix-narc", type=Path, default=root / "base/root/a/0/4/1")
    parser.add_argument("--land-narc", type=Path, default=root / "base/root/a/0/6/5")
    parser.add_argument(
        "--building-model-narc",
        type=Path,
        default=root / "base/root/a/0/4/0",
    )
    parser.add_argument(
        "--counts-header",
        type=Path,
        default=root / "include/constants/generated/overworld_wild_roof_catalog_counts.h",
    )
    parser.add_argument(
        "--c-include",
        type=Path,
        default=root / "data/generated/overworld_wild_roof_catalog.inc",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=root / "data/generated/overworld_wild_roof_catalog.json",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    require(manifest.get("schema_version") == 2, "unsupported manifest schema")
    matrix_narc = NarcArchive.from_file(args.matrix_narc)
    land_narc = NarcArchive.from_file(args.land_narc)
    building_models = NarcArchive.from_file(args.building_model_narc)
    instances, verified_specs, logical_groups, coverage = generate_catalog(
        manifest, matrix_narc, land_narc, building_models
    )
    header, c_include, report = render_outputs(instances, verified_specs, logical_groups, coverage)
    write_or_check(args.counts_header, header, args.check)
    write_or_check(args.c_include, c_include, args.check)
    write_or_check(args.report, report, args.check)
    print(
        json.dumps(
            {
                "models": len(verified_specs),
                "common_placements": coverage["discovered_placements"],
                "excluded_placements": coverage["excluded_placements"],
                "logical_groups": len(logical_groups),
                "instances": len(instances),
                "check": args.check,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyError, OSError, RuntimeError, struct.error, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
