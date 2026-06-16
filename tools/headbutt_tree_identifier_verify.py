#!/usr/bin/env python3
"""Verify headbutt tree detector output against a human-labeled fixture."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def point(tree: dict[str, Any]) -> tuple[float, float]:
    anchor = tree.get("anchor")
    if not isinstance(anchor, dict):
        raise ValueError(f"tree {tree.get('id', '<unknown>')} has no anchor object")
    return float(anchor["x"]), float(anchor["y"])


def tile_set(tree: dict[str, Any], *names: str) -> set[tuple[int, int]]:
    for name in names:
        value = tree.get(name)
        if value is None:
            continue

        tiles: set[tuple[int, int]] = set()
        for tile in value:
            if isinstance(tile, dict):
                tiles.add((int(tile["x"]), int(tile["y"])))
            else:
                tiles.add((int(tile[0]), int(tile[1])))
        return tiles
    return set()


def iou(a: set[tuple[int, int]], b: set[tuple[int, int]]) -> float | None:
    if not a and not b:
        return None
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax, ay = point(a)
    bx, by = point(b)
    return math.hypot(ax - bx, ay - by)


def pair_score(
    expected_tree: dict[str, Any],
    detected_tree: dict[str, Any],
    tolerance: float,
) -> tuple[bool, float, dict[str, Any]]:
    dist = distance(expected_tree, detected_tree)
    expected_footprint = tile_set(expected_tree, "footprint", "expected_footprint")
    detected_footprint = tile_set(detected_tree, "footprint", "predicted_footprint")

    footprint_iou = iou(expected_footprint, detected_footprint)
    anchor_match = dist <= tolerance
    footprint_match = footprint_iou is not None and footprint_iou >= 0.5

    metrics = {
        "anchor_distance": dist,
        "footprint_iou": footprint_iou,
    }
    if not anchor_match and not footprint_match:
        return False, 0.0, metrics

    score = 0.0
    if footprint_iou is not None:
        score += 5.0 * footprint_iou
    score += max(0.0, 2.0 * (1.0 - (dist / max(tolerance, 0.001))))
    return True, score, metrics


def in_bbox(tree: dict[str, Any], bbox: dict[str, Any]) -> bool:
    if any(bbox.get(key) is None for key in ("min_x", "min_y", "max_x", "max_y")):
        return False
    x, y = point(tree)
    return (
        float(bbox["min_x"]) <= x <= float(bbox["max_x"])
        and float(bbox["min_y"]) <= y <= float(bbox["max_y"])
    )


def match_trees(
    expected: list[dict[str, Any]],
    detected: list[dict[str, Any]],
    tolerance: float,
    minimum_footprint_iou: float,
) -> dict[str, Any]:
    pairs: list[tuple[float, int, int, dict[str, Any]]] = []
    for expected_index, expected_tree in enumerate(expected):
        for detected_index, detected_tree in enumerate(detected):
            is_candidate, score, metrics = pair_score(expected_tree, detected_tree, tolerance)
            if is_candidate:
                pairs.append((score, expected_index, detected_index, metrics))

    pairs.sort(key=lambda item: item[0], reverse=True)
    matched_expected: set[int] = set()
    matched_detected: set[int] = set()
    matches: list[dict[str, Any]] = []
    shape_errors: list[dict[str, Any]] = []

    for score, expected_index, detected_index, metrics in pairs:
        if expected_index in matched_expected or detected_index in matched_detected:
            continue
        matched_expected.add(expected_index)
        matched_detected.add(detected_index)
        match = {
            "expected_id": expected[expected_index].get("id"),
            "detected_id": detected[detected_index].get("id"),
            "score": score,
            **metrics,
        }
        matches.append(match)

        if metrics["footprint_iou"] is not None and metrics["footprint_iou"] < minimum_footprint_iou:
            shape_errors.append(match)

    duplicate_pressure: list[dict[str, Any]] = []
    for expected_index, expected_tree in enumerate(expected):
        nearby = [
            detected_tree.get("id")
            for detected_tree in detected
            if pair_score(expected_tree, detected_tree, tolerance)[0]
        ]
        if len(nearby) > 1:
            duplicate_pressure.append(
                {
                    "expected_id": expected_tree.get("id"),
                    "nearby_detected_ids": nearby,
                }
            )

    return {
        "matches": matches,
        "false_negatives": [
            expected[index] for index in range(len(expected)) if index not in matched_expected
        ],
        "false_positives": [
            detected[index] for index in range(len(detected)) if index not in matched_detected
        ],
        "duplicate_pressure": duplicate_pressure,
        "shape_errors": shape_errors,
    }


def verify_regions(
    fixture: dict[str, Any],
    detected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for region in fixture.get("regions", []):
        bbox = region.get("bbox", {})
        if any(bbox.get(key) is None for key in ("min_x", "min_y", "max_x", "max_y")):
            failures.append(
                {
                    "region_id": region.get("id"),
                    "reason": "missing_bounds",
                    "expected_count": region.get("expected_count"),
                    "actual_count": None,
                }
            )
            continue

        actual = [tree for tree in detected if in_bbox(tree, bbox)]
        expected_count = region.get("expected_count")
        if expected_count is not None and len(actual) != int(expected_count):
            failures.append(
                {
                    "region_id": region.get("id"),
                    "reason": "count_mismatch",
                    "expected_count": int(expected_count),
                    "actual_count": len(actual),
                    "detected_ids": [tree.get("id") for tree in actual],
                }
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--detections", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    fixture = load_json(args.fixture)
    detections = load_json(args.detections)

    if fixture.get("map_id") != detections.get("map_id"):
        raise SystemExit(
            f"map_id mismatch: fixture={fixture.get('map_id')} detections={detections.get('map_id')}"
        )
    if fixture.get("coordinate_space") != detections.get("coordinate_space"):
        raise SystemExit(
            "coordinate_space mismatch: "
            f"fixture={fixture.get('coordinate_space')} "
            f"detections={detections.get('coordinate_space')}"
        )

    expected = fixture.get("expected_trees", [])
    detected = detections.get("detected_trees", [])
    tolerance = float(fixture.get("match_tolerance_tiles", 1.0))
    minimum_footprint_iou = float(fixture.get("minimum_footprint_iou", 0.8))

    report = {
        "fixture": str(args.fixture),
        "detections": str(args.detections),
        "map_id": fixture.get("map_id"),
        "tolerance": tolerance,
        "minimum_footprint_iou": minimum_footprint_iou,
        "expected_count": len(expected),
        "detected_count": len(detected),
        **match_trees(
            expected,
            detected,
            tolerance,
            minimum_footprint_iou,
        ),
        "region_failures": verify_regions(fixture, detected),
    }

    failed = bool(
        report["false_negatives"]
        or report["false_positives"]
        or report["duplicate_pressure"]
        or report["shape_errors"]
        or report["region_failures"]
    )
    report["passed"] = not failed

    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
