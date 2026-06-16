#!/usr/bin/env python3
"""Render a visual summary of visual-model headbutt tree evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rect(x: int, y: int, w: int, h: int, fill: str, stroke: str, sw: str = "1") -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cell-size", type=int, default=14)
    parser.add_argument(
        "--bounds",
        type=int,
        nargs=4,
        metavar=("MIN_X", "MIN_Y", "MAX_X", "MAX_Y"),
        help="render this inclusive world-tile rectangle",
    )
    args = parser.parse_args()

    probe = load_json(args.probe)
    fixture = load_json(args.fixture) if args.fixture else None
    selected_material = probe["selected_material"]
    selected_masks = [
        mask
        for mask in probe["visual_masks"]
        if mask["material"] == selected_material or mask["material"].endswith(selected_material)
    ]
    mask_tiles = {
        (int(tile["x"]), int(tile["y"]))
        for mask in selected_masks
        for tile in mask["tiles"]
    }
    any_tree_tiles = {
        (int(tile["x"]), int(tile["y"]))
        for mask in probe["visual_masks"]
        for tile in mask["tiles"]
    }

    candidates = []
    candidate_tiles: set[tuple[int, int]] = set()
    for tree in probe["detected_trees"]:
        footprint = {(int(tile["x"]), int(tile["y"])) for tile in tree["footprint"]}
        candidate_tiles |= footprint
        candidates.append((tree, footprint))

    warning_boxes = []
    for warning in probe.get("fixture_quality_warnings", []):
        bbox = warning.get("bbox")
        if bbox:
            warning_boxes.append((warning.get("id"), warning.get("reason"), bbox))

    bounds = probe["selected_mask_bbox"]
    fixture_trees = []
    if fixture:
        for tree in fixture.get("expected_trees", []):
            bbox = tree["bbox"]
            footprint = {(int(tile["x"]), int(tile["y"])) for tile in tree["footprint"]}
            fixture_trees.append((tree, bbox, footprint))
            bounds = {
                "min_x": min(bounds["min_x"], int(bbox["min_x"])),
                "min_y": min(bounds["min_y"], int(bbox["min_y"])),
                "max_x": max(bounds["max_x"], int(bbox["max_x"])),
                "max_y": max(bounds["max_y"], int(bbox["max_y"])),
            }
    for stamp in probe["map_stamps"]:
        bounds = {
            "min_x": min(bounds["min_x"], stamp["world_min_x"]),
            "min_y": min(bounds["min_y"], stamp["world_min_y"]),
            "max_x": max(bounds["max_x"], stamp["world_max_x"]),
            "max_y": max(bounds["max_y"], stamp["world_max_y"]),
        }

    if args.bounds:
        min_x, min_y, max_x, max_y = args.bounds
    else:
        min_x = bounds["min_x"]
        min_y = bounds["min_y"]
        max_x = bounds["max_x"]
        max_y = bounds["max_y"]
    cell = args.cell_size
    margin_left = 64
    margin_top = 58
    legend_w = 320
    width = margin_left + (max_x - min_x + 1) * cell + legend_w
    height = margin_top + (max_y - min_y + 1) * cell + 60

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        (
            '<style>'
            'text{font-family:Arial,sans-serif;fill:#1f2937}'
            '.title{font-size:15px;font-weight:700}'
            '.small{font-size:10px}'
            '.axis{font-size:9px;fill:#475569}'
            '.legend{font-size:11px}'
            '</style>'
        ),
        (
            f'<text x="18" y="24" class="title">Map {probe["map_id"]} '
            'visual-model headbutt tree evidence</text>'
        ),
        (
            f'<text x="18" y="42" class="small">'
            f'{selected_material}: {probe["selected_mask_tile_count"]} model-mask tiles, '
            f'{probe["selected_uv_repeat_block_count"]} UV-repeat candidates'
            '</text>'
        ),
    ]

    for x in range(min_x, max_x + 1):
        if x % 2 == 0:
            sx = margin_left + (x - min_x) * cell
            lines.append(f'<text x="{sx + 1}" y="{margin_top - 8}" class="axis">{x}</text>')
    for y in range(min_y, max_y + 1):
        sy = margin_top + (y - min_y) * cell
        lines.append(f'<text x="24" y="{sy + 10}" class="axis">{y}</text>')

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            sx = margin_left + (x - min_x) * cell
            sy = margin_top + (y - min_y) * cell
            fill = "#ffffff"
            if (x, y) in any_tree_tiles:
                fill = "#e2e8f0"
            if (x, y) in mask_tiles:
                fill = "#c7f0d8"
            if (x, y) in candidate_tiles:
                fill = "#6ee7a8"
            lines.append(rect(sx, sy, cell, cell, fill, "#cbd5e1"))

    for stamp in probe["map_stamps"][1:]:
        if stamp["world_max_y"] < min_y or stamp["world_min_y"] > max_y:
            continue
        sx = margin_left + (stamp["world_min_x"] - min_x) * cell
        if sx < margin_left or sx > margin_left + (max_x - min_x + 1) * cell:
            continue
        lines.append(
            f'<line x1="{sx}" y1="{margin_top}" x2="{sx}" '
            f'y2="{margin_top + (max_y - min_y + 1) * cell}" '
            'stroke="#334155" stroke-width="2"/>'
        )

    for tree, footprint in candidates:
        bbox = tree["bbox"]
        sx = margin_left + (bbox["min_x"] - min_x) * cell
        sy = margin_top + (bbox["min_y"] - min_y) * cell
        w = (bbox["max_x"] - bbox["min_x"] + 1) * cell
        h = (bbox["max_y"] - bbox["min_y"] + 1) * cell
        lines.append(
            f'<rect x="{sx + 2}" y="{sy + 2}" width="{w - 4}" height="{h - 4}" '
            'fill="none" stroke="#d97706" stroke-width="1.4" stroke-dasharray="3 2"/>'
        )

    for tree, bbox, footprint in fixture_trees:
        sx = margin_left + (int(bbox["min_x"]) - min_x) * cell
        sy = margin_top + (int(bbox["min_y"]) - min_y) * cell
        w = (int(bbox["max_x"]) - int(bbox["min_x"]) + 1) * cell
        h = (int(bbox["max_y"]) - int(bbox["min_y"]) + 1) * cell
        stroke = "#2563eb" if len(footprint) == 4 else "#7c3aed"
        lines.append(rect(sx + 3, sy + 3, w - 6, h - 6, "none", stroke, "1.8"))

    for warning_id, reason, bbox in warning_boxes:
        sx = margin_left + (int(bbox["min_x"]) - min_x) * cell
        sy = margin_top + (int(bbox["min_y"]) - min_y) * cell
        w = (int(bbox["max_x"]) - int(bbox["min_x"]) + 1) * cell
        h = (int(bbox["max_y"]) - int(bbox["min_y"]) + 1) * cell
        lines.append(rect(sx + 1, sy + 1, w - 2, h - 2, "none", "#dc2626", "2"))
        lines.append(
            f'<text x="{sx + 3}" y="{sy + 11}" class="small" fill="#dc2626">{warning_id}</text>'
        )

    legend_x = margin_left + (max_x - min_x + 1) * cell + 28
    legend_y = margin_top
    legend = [
        ("#e2e8f0", "any tree-material tile"),
        ("#c7f0d8", f"{selected_material} model-mask tile"),
        ("#6ee7a8", "UV-repeat candidate tile"),
        ("none", "UV-repeat 2x2 primitive"),
        ("none", "fixture tree outline, 2x2"),
        ("none", "fixture tree outline, 2x3+"),
        ("none", "fixture-quality warning"),
    ]
    for index, (fill, label) in enumerate(legend):
        y = legend_y + index * 28
        stroke = "#94a3b8"
        dash = ""
        if index == 2:
            stroke = "#d97706"
            dash = ' stroke-dasharray="3 2"'
        elif index == 3:
            stroke = "#2563eb"
        elif index == 4:
            stroke = "#7c3aed"
        elif index == 5:
            stroke = "#dc2626"
        lines.append(rect(legend_x, y, 18, 18, fill, stroke, "2" if index >= 2 else "1"))
        if dash:
            lines[-1] = lines[-1].replace("/>", f"{dash}/>")
        lines.append(f'<text x="{legend_x + 28}" y="{y + 13}" class="legend">{label}</text>')

    metric_lines = [
        f"map stamps: {len(probe['map_stamps'])}",
        f"selected components: {probe['selected_mask_component_count']}",
        f"UV-repeat primitives: {len(probe['detected_trees'])}",
        f"fixture trees: {len(fixture_trees) if fixture else 'not shown'}",
        f"fixture warnings: {len(probe.get('fixture_quality_warnings', []))}",
        "archive source: not used",
    ]
    for index, text in enumerate(metric_lines):
        lines.append(
            f'<text x="{legend_x}" y="{legend_y + 140 + index * 18}" '
            f'class="small">{text}</text>'
        )

    lines.append("</svg>")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
