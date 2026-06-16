#!/usr/bin/env python3
"""Build a Route 29 tree-top oracle from the manual tree labeler export."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def _connected_components(cells: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    components: list[set[tuple[int, int]]] = []
    pending = set(cells)
    while pending:
        start = pending.pop()
        stack = [start]
        component = {start}
        while stack:
            x, y = stack.pop()
            for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if neighbor in pending:
                    pending.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(component)
    return components


def _split_wide_components(
    tree_id: str,
    component: set[tuple[int, int]],
) -> list[tuple[str, set[tuple[int, int]], str]]:
    xs = [x for x, _ in component]
    ys = [y for _, y in component]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x + 1
    height = max_y - min_y + 1

    if height in (2, 3) and width > 2 and width % 2 == 0 and len(component) == width * height:
        chunks: list[tuple[str, set[tuple[int, int]], str]] = []
        for chunk_left in range(min_x, max_x + 1, 2):
            chunk = {(x, y) for x, y in component if chunk_left <= x < chunk_left + 2}
            chunks.append((tree_id, chunk, "split_wide_component"))
        return chunks

    return [(tree_id, component, "component")]


def load_oracle(labels_path: Path) -> dict:
    data = json.loads(labels_path.read_text())
    labels = [(int(item["x"]), int(item["y"]), str(item["tree_id"])) for item in data["labels"]]

    by_tree_id: dict[str, set[tuple[int, int]]] = collections.defaultdict(set)
    for x, y, tree_id in labels:
        by_tree_id[tree_id].add((x, y))

    raw_components: list[tuple[str, set[tuple[int, int]]]] = []
    for tree_id, cells in sorted(by_tree_id.items(), key=lambda item: int(item[0])):
        for component in _connected_components(cells):
            raw_components.append((tree_id, component))

    trees = []
    for tree_id, component in raw_components:
        for split_index, (source_tree_id, tree_cells, split_reason) in enumerate(
            _split_wide_components(tree_id, component)
        ):
            xs = [x for x, _ in tree_cells]
            ys = [y for _, y in tree_cells]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            top_tiles = [
                {"x": x, "y": min_y}
                for x, _ in sorted((x, y) for x, y in tree_cells if y == min_y)
            ]
            trees.append(
                {
                    "id": f"{source_tree_id}:{split_index}",
                    "source_tree_id": source_tree_id,
                    "split_reason": split_reason,
                    "bbox": {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
                    "width": max_x - min_x + 1,
                    "height": max_y - min_y + 1,
                    "tile_count": len(tree_cells),
                    "top_tiles": top_tiles,
                }
            )

    top_tiles = sorted(
        {(tile["x"], tile["y"]) for tree in trees for tile in tree["top_tiles"]},
        key=lambda item: (item[1], item[0]),
    )
    row_spans = []
    rows: dict[int, list[int]] = collections.defaultdict(list)
    for x, y in top_tiles:
        rows[y].append(x)

    for y in sorted(rows):
        xs = sorted(rows[y])
        start = end = xs[0]
        for x in xs[1:]:
            if x == end + 1:
                end = x
            else:
                row_spans.append({"y": y, "min_x": start, "max_x": end, "tile_count": end - start + 1})
                start = end = x
        row_spans.append({"y": y, "min_x": start, "max_x": end, "tile_count": end - start + 1})

    shape_counts = collections.Counter((tree["width"], tree["height"]) for tree in trees)
    route_bounds = data["route_bounds"]
    return {
        "schema_version": 1,
        "source": str(labels_path),
        "map_id": data["map_id"],
        "map_name": data["map_name"],
        "coordinate_space": data["coordinate_space"],
        "route_bounds": route_bounds,
        "raw_label_count": len(labels),
        "raw_tree_id_count": len(by_tree_id),
        "connected_component_count": len(raw_components),
        "normalized_tree_count": len(trees),
        "top_tile_count": len(top_tiles),
        "shape_counts": [
            {"width": width, "height": height, "count": count}
            for (width, height), count in sorted(shape_counts.items())
        ],
        "trees": sorted(trees, key=lambda tree: (tree["bbox"]["min_y"], tree["bbox"]["min_x"], tree["id"])),
        "top_tiles": [{"x": x, "y": y} for x, y in top_tiles],
        "row_spans": row_spans,
    }


def write_svg(oracle: dict, output_path: Path) -> None:
    top_tiles = {(tile["x"], tile["y"]) for tile in oracle["top_tiles"]}
    min_x = min(x for x, _ in top_tiles)
    max_x = max(x for x, _ in top_tiles)
    min_y = min(y for _, y in top_tiles)
    max_y = max(y for _, y in top_tiles)
    cell = 10
    label_w = 44
    top_h = 26
    width = label_w + (max_x - min_x + 1) * cell + 14
    height = top_h + (max_y - min_y + 1) * cell + 28
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="10" y="16" font-family="Arial" font-size="12" font-weight="700">Route 29 tree-top oracle: {oracle["normalized_tree_count"]} trees, {oracle["top_tile_count"]} top tiles</text>',
    ]
    for y in range(min_y, max_y + 1):
        grid_y = top_h + (y - min_y) * cell
        parts.append(f'<text x="8" y="{grid_y + 8}" font-family="Arial" font-size="8" fill="#334155">{y}</text>')
        for x in range(min_x, max_x + 1):
            grid_x = label_w + (x - min_x) * cell
            fill = "#86efac" if (x, y) in top_tiles else "#ffffff"
            stroke = "#cbd5e1"
            parts.append(
                f'<rect x="{grid_x}" y="{grid_y}" width="{cell}" height="{cell}" fill="{fill}" stroke="{stroke}" stroke-width="0.8"/>'
            )
    for x in range(min_x, max_x + 1, 2):
        grid_x = label_w + (x - min_x) * cell
        parts.append(f'<text x="{grid_x + 1}" y="{top_h - 3}" font-family="Arial" font-size="7" fill="#334155">{x}</text>')
    parts.append("</svg>")
    output_path.write_text("\n".join(parts))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--oracle-json", type=Path, required=True)
    parser.add_argument("--svg", type=Path, required=True)
    args = parser.parse_args()

    oracle = load_oracle(args.labels)
    args.oracle_json.write_text(json.dumps(oracle, indent=2) + "\n")
    write_svg(oracle, args.svg)
    print(
        f"wrote {oracle['normalized_tree_count']} trees, "
        f"{oracle['top_tile_count']} top tiles, {len(oracle['row_spans'])} spans"
    )


if __name__ == "__main__":
    main()
