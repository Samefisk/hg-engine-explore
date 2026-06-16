#!/usr/bin/env python3
"""Dump deterministic Route 29 map-coordinate evidence from ROM data.

This is a coordinate/debug layer, not the visual tree detector. It intentionally
does not read the Headbutt archive because that data is not reliable for finding
individual visual trees.
"""

from __future__ import annotations

import argparse
import csv
import json
import struct
from collections import Counter
from pathlib import Path

import ndspy.narc


MAP_ID_ROUTE_29 = 33
MAIN_MATRIX_ID = 0
ROUTE_29_MATRIX_Y = 12
ROUTE_29_MATRIX_XS = (18, 19, 20)
CELL_SIZE = 32
NORTH_LABEL_PADDING_ROWS = 1
SOUTH_LABEL_PADDING_ROWS = 1
PERMISSION_GRID_OFFSET = 0x14
PERMISSION_GRID_BYTES = CELL_SIZE * CELL_SIZE * 2

def repo_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[1].joinpath(*parts)


def read_matrix_file(matrix_id: int) -> dict:
    matrix_narc = ndspy.narc.NARC.fromFile(repo_path("base", "root", "a", "0", "4", "1"))
    data = matrix_narc.files[matrix_id]
    width = data[0]
    height = data[1]
    flags = data[2]
    name_len = data[4]
    name = data[5:5 + name_len].decode("ascii")
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


def read_land_permission_grid(land_file_id: int) -> list[int]:
    land_narc = ndspy.narc.NARC.fromFile(repo_path("base", "root", "a", "0", "6", "5"))
    data = land_narc.files[land_file_id]
    permission_len, buildings_len, nsbmd_len, bdhc_len = struct.unpack_from("<4I", data, 0)
    if permission_len != PERMISSION_GRID_BYTES:
        raise RuntimeError(
            f"land file {land_file_id} has unexpected permission length "
            f"{permission_len:#x}"
        )
    if len(data) < PERMISSION_GRID_OFFSET + permission_len + buildings_len + nsbmd_len + bdhc_len:
        raise RuntimeError(f"land file {land_file_id} is shorter than its section lengths")
    return list(struct.unpack_from(f"<{CELL_SIZE * CELL_SIZE}H", data, PERMISSION_GRID_OFFSET))


def read_route29_map_stamps() -> list[dict]:
    matrix = read_matrix_file(MAIN_MATRIX_ID)
    stamps = []
    for matrix_x in ROUTE_29_MATRIX_XS:
        index = ROUTE_29_MATRIX_Y * matrix["width"] + matrix_x
        if matrix["land_data_values"] is None:
            raise RuntimeError(f"matrix {MAIN_MATRIX_ID} has no parsed land-data grid")
        map_value = matrix["matrix_values"][index]
        land_file_id = matrix["land_data_values"][index]
        stamps.append({
            "matrix_x": matrix_x,
            "matrix_y": ROUTE_29_MATRIX_Y,
            "map_value": map_value,
            "world_min_x": matrix_x * CELL_SIZE,
            "world_min_y": ROUTE_29_MATRIX_Y * CELL_SIZE,
            "world_max_x": matrix_x * CELL_SIZE + CELL_SIZE - 1,
            "world_max_y": ROUTE_29_MATRIX_Y * CELL_SIZE + CELL_SIZE - 1,
            "land_file_id": land_file_id,
        })
    return stamps


def build_world_permission_grid(stamps: list[dict]) -> tuple[dict[str, int], list[int]]:
    world_by_key: dict[str, int] = {}
    values: list[int] = []
    for stamp in stamps:
        local_grid = read_land_permission_grid(stamp["land_file_id"])
        for local_y in range(CELL_SIZE):
            for local_x in range(CELL_SIZE):
                world_x = stamp["world_min_x"] + local_x
                world_y = stamp["world_min_y"] + local_y
                value = local_grid[local_y * CELL_SIZE + local_x]
                world_by_key[f"{world_x},{world_y}"] = value
                values.append(value)
    return world_by_key, values


def permission_class(value: int) -> str:
    if value == 0:
        return "empty"
    if value == 0x8006:
        return "headbutt_or_blocked_8006"
    if value & 0x8000:
        return "blocked_high_bit"
    return "other_permission"


def svg_color(value: int) -> str:
    if value == 0:
        return "#ffffff"
    if value == 0x8006:
        return "#c8d0d8"
    if value & 0x8000:
        return "#dfe8f3"
    return "#f4e3b5"


def route_bounds(stamps: list[dict]) -> dict[str, int]:
    min_y = min(stamp["world_min_y"] for stamp in stamps) - NORTH_LABEL_PADDING_ROWS
    max_y = max(stamp["world_max_y"] for stamp in stamps) + SOUTH_LABEL_PADDING_ROWS
    return {
        "min_x": min(stamp["world_min_x"] for stamp in stamps),
        "min_y": min_y,
        "max_x": max(stamp["world_max_x"] for stamp in stamps),
        "max_y": max_y,
        "width": len(stamps) * CELL_SIZE,
        "height": max_y - min_y + 1,
    }


def write_svg(path: Path, stamps: list[dict], world_permissions: dict[str, int]) -> None:
    bounds = route_bounds(stamps)
    min_x = bounds["min_x"]
    min_y = bounds["min_y"]
    max_x = bounds["max_x"]
    max_y = bounds["max_y"]
    cell = 13
    margin_left = 54
    margin_top = 34
    width = margin_left + (max_x - min_x + 1) * cell + 330
    height = margin_top + (max_y - min_y + 1) * cell + 42

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f8fa"/>',
        '<style>text{font-family:Arial,sans-serif;font-size:11px;fill:#1f2933}.small{font-size:9px}.label{font-weight:700}</style>',
        '<text x="16" y="20" class="label">Route 29 coordinate audit: permission grid only, not the in-game visual map</text>',
    ]

    for x in range(min_x, max_x + 1, 2):
        sx = margin_left + (x - min_x) * cell
        lines.append(f'<text x="{sx + 2}" y="{margin_top - 8}" class="small">{x}</text>')
    for y in range(min_y, max_y + 1):
        sy = margin_top + (y - min_y) * cell
        lines.append(f'<text x="18" y="{sy + 10}" class="small">{y}</text>')

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            value = world_permissions.get(f"{x},{y}", 0)
            sx = margin_left + (x - min_x) * cell
            sy = margin_top + (y - min_y) * cell
            lines.append(
                f'<rect x="{sx}" y="{sy}" width="{cell}" height="{cell}" '
                f'fill="{svg_color(value)}" stroke="#cbd5e1" stroke-width="1"/>'
            )

    legend_x = margin_left + (max_x - min_x + 1) * cell + 26
    legend_y = margin_top
    legend = [
        ("#c8d0d8", "permission value 0x8006"),
        ("#dfe8f3", "blocked high-bit permission"),
        ("#f4e3b5", "other non-zero permission"),
    ]
    for index, (color, label) in enumerate(legend):
        y = legend_y + index * 24
        lines.append(f'<rect x="{legend_x}" y="{y}" width="16" height="16" fill="{color}" stroke="#94a3b8"/>')
        lines.append(f'<text x="{legend_x + 24}" y="{y + 12}">{label}</text>')
    lines.append(f'<text x="{legend_x}" y="{legend_y + 94}" class="small">This is not drawn from the visual layer.</text>')
    lines.append(f'<text x="{legend_x}" y="{legend_y + 110}" class="small">Do not use it to count trees.</text>')
    lines.append(f'<text x="{legend_x}" y="{legend_y + 126}" class="small">Use it only to confirm world coordinates.</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_label_sheet_svg(path: Path, stamps: list[dict]) -> None:
    bounds = route_bounds(stamps)
    min_x = bounds["min_x"]
    min_y = bounds["min_y"]
    max_x = bounds["max_x"]
    max_y = bounds["max_y"]
    cell = 22
    margin_left = 68
    margin_top = 46
    width = margin_left + bounds["width"] * cell + 310
    height = margin_top + bounds["height"] * cell + 58

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfcfe"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#17202a}.small{font-size:9px}.axis{font-size:10px}.label{font-size:13px;font-weight:700}.note{font-size:11px}</style>',
        '<text x="18" y="24" class="label">Route 29 manual tree-label sheet</text>',
        '<text x="18" y="39" class="note">Write one tree number inside every tile that belongs to that tree. Blank means not part of a tree.</text>',
    ]

    for x in range(min_x, max_x + 1):
        sx = margin_left + (x - min_x) * cell
        if x % 2 == 0:
            lines.append(f'<text x="{sx + 3}" y="{margin_top - 8}" class="axis">{x}</text>')
    for y in range(min_y, max_y + 1):
        sy = margin_top + (y - min_y) * cell
        lines.append(f'<text x="24" y="{sy + 14}" class="axis">{y}</text>')

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            sx = margin_left + (x - min_x) * cell
            sy = margin_top + (y - min_y) * cell
            fill = "#ffffff" if (x + y) % 2 == 0 else "#f8fafc"
            lines.append(
                f'<rect x="{sx}" y="{sy}" width="{cell}" height="{cell}" '
                f'fill="{fill}" stroke="#b8c2d1" stroke-width="1"/>'
            )

    for stamp in stamps[1:]:
        sx = margin_left + (stamp["world_min_x"] - min_x) * cell
        lines.append(
            f'<line x1="{sx}" y1="{margin_top}" x2="{sx}" '
            f'y2="{margin_top + bounds["height"] * cell}" stroke="#334155" stroke-width="2"/>'
        )

    legend_x = margin_left + bounds["width"] * cell + 28
    legend_y = margin_top
    lines.extend([
        f'<text x="{legend_x}" y="{legend_y}" class="label">Rules</text>',
        f'<text x="{legend_x}" y="{legend_y + 24}" class="note">Same number = one tree.</text>',
        f'<text x="{legend_x}" y="{legend_y + 42}" class="note">Different tree = different number.</text>',
        f'<text x="{legend_x}" y="{legend_y + 60}" class="note">Use world coordinates on axes.</text>',
        f'<text x="{legend_x}" y="{legend_y + 78}" class="note">Do not label canopy yet.</text>',
        f'<text x="{legend_x}" y="{legend_y + 110}" class="label">Chunks</text>',
    ])
    for index, stamp in enumerate(stamps):
        y = legend_y + 134 + index * 18
        lines.append(
            f'<text x="{legend_x}" y="{y}" class="note">'
            f'x {stamp["world_min_x"]}-{stamp["world_max_x"]}: land {stamp["land_file_id"]}</text>'
        )

    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_label_csv(path: Path, stamps: list[dict], world_permissions: dict[str, int]) -> None:
    bounds = route_bounds(stamps)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "x",
                "y",
                "tree_id",
                "tile_note",
                "permission_value_hex",
                "permission_class",
            ],
        )
        writer.writeheader()
        for y in range(bounds["min_y"], bounds["max_y"] + 1):
            for x in range(bounds["min_x"], bounds["max_x"] + 1):
                value = world_permissions.get(f"{x},{y}", 0)
                writer.writerow({
                    "x": x,
                    "y": y,
                    "tree_id": "",
                    "tile_note": "",
                    "permission_value_hex": f"0x{value:04x}",
                    "permission_class": permission_class(value),
                })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--svg-output", type=Path)
    parser.add_argument("--label-sheet-output", type=Path)
    parser.add_argument("--label-csv-output", type=Path)
    args = parser.parse_args()

    stamps = read_route29_map_stamps()
    world_permissions, permission_values = build_world_permission_grid(stamps)
    bounds = route_bounds(stamps)
    bounded_permissions = {
        f"{x},{y}": world_permissions.get(f"{x},{y}", 0)
        for y in range(bounds["min_y"], bounds["max_y"] + 1)
        for x in range(bounds["min_x"], bounds["max_x"] + 1)
    }
    permission_values = list(bounded_permissions.values())
    value_counts = Counter(permission_values)
    class_counts = Counter(permission_class(value) for value in permission_values)

    output = {
        "schema_version": 1,
        "map_id": MAP_ID_ROUTE_29,
        "map_name": "Route 29",
        "coordinate_space": "world_tile",
        "route_bounds": bounds,
        "matrix": {
            "id": MAIN_MATRIX_ID,
            "route_cells": stamps,
        },
        "permission_value_counts": {
            f"0x{value:04x}": count for value, count in sorted(value_counts.items())
        },
        "permission_class_counts": dict(sorted(class_counts.items())),
        "permission_by_world_tile": [
            {
                "x": int(key.split(",")[0]),
                "y": int(key.split(",")[1]),
                "value": value,
                "value_hex": f"0x{value:04x}",
                "class": permission_class(value),
            }
            for key, value in sorted(
                bounded_permissions.items(),
                key=lambda item: tuple(int(part) for part in item[0].split(",")),
            )
        ],
        "notes": [
            "This artifact is a coordinate/debug layer; it is not the final individual visual tree detector.",
            "It does not use the Headbutt archive.",
            "It does not resemble the in-game visual map because it is the permission grid, not the rendered map model.",
            "Route 29 map value 33 uses land files 1, 2, and 3 at matrix cells (18,12), (19,12), and (20,12).",
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    if args.svg_output is not None:
        args.svg_output.parent.mkdir(parents=True, exist_ok=True)
        write_svg(args.svg_output, stamps, bounded_permissions)
    if args.label_sheet_output is not None:
        args.label_sheet_output.parent.mkdir(parents=True, exist_ok=True)
        write_label_sheet_svg(args.label_sheet_output, stamps)
    if args.label_csv_output is not None:
        write_label_csv(args.label_csv_output, stamps, bounded_permissions)
    print(args.output)
    if args.svg_output is not None:
        print(args.svg_output)
    if args.label_sheet_output is not None:
        print(args.label_sheet_output)
    if args.label_csv_output is not None:
        print(args.label_csv_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
