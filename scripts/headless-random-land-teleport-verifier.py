#!/usr/bin/env python3
"""Verify L+R encounter-map teleport picks varied vetted land tiles."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP_SYMBOL = "MAP_R29"


def import_script(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verifier = import_script(
    REPO_ROOT / "scripts/headless-all-encounter-teleport-verifier.py",
    "headless_all_encounter_teleport_verifier",
)
headless = verifier.headless


def repo_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", default="test.nds")
    parser.add_argument("--dsv")
    parser.add_argument("--sav")
    parser.add_argument(
        "--destinations",
        type=Path,
        default=Path("documentation/verification/encounter_map_teleport_destinations.json"),
    )
    parser.add_argument("--map-symbol", dest="map_symbols", action="append")
    parser.add_argument("--runs", type=int, default=12)
    parser.add_argument("--min-unique-coordinates", type=int, default=2)
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("documentation/verification/random_land_teleport_verifier.json"),
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=Path("documentation/verification/random_land_teleport_verifier.jsonl"),
    )
    parser.add_argument("--boot-frames", type=int, default=420)
    parser.add_argument("--ready-a-taps", type=int, default=10)
    parser.add_argument("--tap-hold-frames", type=int, default=24)
    parser.add_argument("--tap-gap-frames", type=int, default=36)
    parser.add_argument("--load-frames", type=int, default=360)
    parser.add_argument("--post-ready-wait-frames", type=int, default=120)
    parser.add_argument("--ready-timeout-frames", type=int, default=240)
    parser.add_argument("--ready-boot-attempts", type=int, default=3)
    parser.add_argument("--trigger-frames", type=int, default=30)
    parser.add_argument("--release-frames", type=int, default=30)
    parser.add_argument("--max-wait-frames", type=int, default=360)
    parser.add_argument("--between-run-wait-frames", type=int, default=90)
    parser.add_argument("--sample-interval", type=int, default=12)
    parser.add_argument("--min-nonblack-pixels", type=int, default=1000)
    parser.add_argument("--show-emulator-log", action="store_true")
    return parser.parse_args()


class RandomTileOracle:
    def __init__(self) -> None:
        generator = verifier.generator
        self.generator = generator
        self.maps = generator.read_map_constants(repo_path("include/constants/maps.h"))
        self.matrix_narc = generator.ndspy.narc.NARC.fromFile(repo_path("base/root/a/0/4/1"))
        self.land_narc = generator.ndspy.narc.NARC.fromFile(repo_path("base/root/a/0/6/5"))
        self.event_narc = generator.ndspy.narc.NARC.fromFile(repo_path("base/root/a/0/3/2"))
        self.arm9 = repo_path("base/arm9.bin").read_bytes()
        self.matrix_cache: dict[int, tuple[int, int, tuple[int, ...], tuple[int, ...]]] = {}
        self.permission_cache: dict[int, tuple[int, ...]] = {}

    def tiles_for_center(
        self,
        destination: dict[str, Any],
        center_x: int,
        center_y: int,
        source: str,
        exclude_center: bool = True,
    ) -> list[dict[str, Any]]:
        return list(
            self.generator.loaded_window_random_tile_candidates(
                center_x=center_x,
                center_y=center_y,
                loaded_map_id=int(destination["map_id"]),
                fallback_map_id=verifier.static_fallback_map_id(destination, self.maps),
                source=source,
                matrix_narc=self.matrix_narc,
                land_narc=self.land_narc,
                event_narc=self.event_narc,
                arm9=self.arm9,
                matrix_cache=self.matrix_cache,
                permission_cache=self.permission_cache,
                exclude_center=exclude_center,
            )
        )

    def entry_tiles(self, destination: dict[str, Any]) -> list[dict[str, Any]]:
        return self.tiles_for_center(
            destination,
            int(destination["x"]),
            int(destination["y"]),
            "verifier-entry",
        )

    def strict_tiles_for_center(
        self,
        destination: dict[str, Any],
        center_x: int,
        center_y: int,
        source: str,
    ) -> list[dict[str, Any]]:
        return self.tiles_for_center(
            destination,
            center_x,
            center_y,
            source,
            exclude_center=False,
        )


def coordinate_evidence(tiles: list[dict[str, Any]]) -> dict[str, Any]:
    coordinates = sorted((int(tile["x"]), int(tile["y"])) for tile in tiles)
    digest = hashlib.sha256()
    for x, y in coordinates:
        digest.update(f"{x},{y}\n".encode("ascii"))
    evidence: dict[str, Any] = {
        "count": len(coordinates),
        "sha256": digest.hexdigest(),
    }
    if coordinates:
        evidence["bounds"] = {
            "min_x": coordinates[0][0],
            "max_x": max(x for x, _y in coordinates),
            "min_y": min(y for _x, y in coordinates),
            "max_y": max(y for _x, y in coordinates),
        }
        evidence["sample"] = [{"x": x, "y": y} for x, y in coordinates[:8]]
    return evidence


def host_land_classification(
    coordinate: tuple[int, int],
    tile_by_coordinate: dict[tuple[int, int], dict[str, Any]],
) -> dict[str, Any]:
    tile = tile_by_coordinate.get(coordinate)
    classification: dict[str, Any] = {
        "strict_loaded_cell_land": tile is not None,
        "predicate": (
            "same loaded 32x32 matrix cell as this run's selection center, "
            "in ROM random window, warp/coord-event-unblocked, permission high bit clear, "
            "behavior < 16, non-headbutt"
        ),
    }
    if tile is not None:
        permission = int(tile["permission"])
        classification.update(
            {
                "permission": f"0x{permission:04X}",
                "behavior": permission & 0xFF,
                "matrix_id": tile["matrix_id"],
                "matrix_x": tile["matrix_x"],
                "matrix_y": tile["matrix_y"],
                "matrix_value": tile["matrix_value"],
                "land_file_id": tile["land_file_id"],
                "source": tile["source"],
            }
        )
    return classification


def find_destination(
    destinations: list[dict[str, Any]],
    symbol: str,
) -> tuple[int, dict[str, Any]]:
    for index, destination in enumerate(destinations):
        if destination["symbol"] == symbol:
            return index, destination
    raise ValueError(f"destination symbol not found: {symbol}")


def write_forced_index(emu: Any, index: int) -> None:
    verifier.write_u16(emu, verifier.DEBUG_DESTINATION_INDEX_ADDR, index)


def wait_for_random_outcome(
    args: argparse.Namespace,
    emu: Any,
    destination: dict[str, Any],
    valid_coordinates: set[tuple[int, int]],
    status_before: dict[str, int],
) -> tuple[dict[str, int], int]:
    frames_waited = 0
    observed = verifier.read_status(emu)
    before_coordinate = (status_before["x"], status_before["y"])
    while frames_waited <= args.max_wait_frames:
        request_seen = verifier.request_count_changed(
            status_before["request_count"],
            observed["request_count"],
        )
        if (
            request_seen
            and observed["request_result"] == verifier.MAP_TELEPORT_RESULT_OK
            and observed["ready"] != 0
            and observed["map_id"] == int(destination["map_id"])
            and (observed["x"], observed["y"]) != before_coordinate
            and (observed["x"], observed["y"]) in valid_coordinates
        ):
            return observed, frames_waited
        if (
            observed["ready"] != 0
            and observed["map_id"] == int(destination["map_id"])
            and (observed["x"], observed["y"]) != before_coordinate
            and (observed["x"], observed["y"]) in valid_coordinates
        ):
            return observed, frames_waited
        if frames_waited == args.max_wait_frames:
            return observed, frames_waited
        wait_frames = min(args.sample_interval, args.max_wait_frames - frames_waited)
        headless.cycle(emu, wait_frames)
        frames_waited += wait_frames
        observed = verifier.read_status(emu)
    return observed, frames_waited


def run_random_tile_sequence(
    args: argparse.Namespace,
    rom: Path,
    raw_save: bytes,
    index: int,
    destination: dict[str, Any],
    oracle: RandomTileOracle,
) -> tuple[list[dict[str, Any]], dict[str, int], int]:
    emu = None
    entry = verifier.empty_destination_entry()
    ready_frames = 0
    status_before = verifier.empty_status()
    ready_failure = "emulator was not opened"
    results: list[dict[str, Any]] = []

    with headless.silence_native_output(not args.show_emulator_log):
        try:
            for _attempt in range(1, args.ready_boot_attempts + 1):
                emu, ready_frames, entry, status_before, ready_failure = (
                    verifier.open_ready_emulator(args, rom, raw_save)
                )
                if ready_failure is None:
                    break
                emu.destroy()
                emu = None
            if ready_failure is not None:
                raise RuntimeError(f"initial field state not ready: {ready_failure}")

            for run in range(args.runs):
                write_forced_index(emu, index)
                status_before = verifier.read_status(emu)
                entry_coordinate = (int(destination["x"]), int(destination["y"]))
                before_coordinate = (status_before["x"], status_before["y"])
                if status_before["map_id"] == int(destination["map_id"]):
                    selection_center = before_coordinate
                    selection_center_source = "status_before"
                    compact_coordinates: set[tuple[int, int]] = set()
                else:
                    selection_center = entry_coordinate
                    selection_center_source = "destination_entry"
                    compact_coordinates = {
                        entry_coordinate,
                        (entry_coordinate[0] + 1, entry_coordinate[1]),
                    }
                valid_tiles = oracle.tiles_for_center(
                    destination,
                    selection_center[0],
                    selection_center[1],
                    f"verifier-run-{run}",
                )
                strict_tiles = oracle.strict_tiles_for_center(
                    destination,
                    selection_center[0],
                    selection_center[1],
                    f"verifier-run-{run}-strict",
                )
                valid_coordinates = {
                    (int(tile["x"]), int(tile["y"]))
                    for tile in valid_tiles
                } | compact_coordinates
                tile_by_coordinate = {
                    (int(tile["x"]), int(tile["y"])): tile
                    for tile in strict_tiles
                }
                headless.hold_combo(emu, "L+R", args.trigger_frames, args.release_frames)
                observed, frames_waited = wait_for_random_outcome(
                    args,
                    emu,
                    destination,
                    valid_coordinates,
                    status_before,
                )
                headless.cycle(emu, args.between_run_wait_frames)
                pixels = verifier.nonblack_pixel_count(emu)
                request_seen = verifier.request_count_changed(
                    status_before["request_count"],
                    observed["request_count"],
                )
                request_delta = (
                    (observed["request_count"] - status_before["request_count"]) & 0xFFFF
                )
                coordinate = (observed["x"], observed["y"])
                host_classification = host_land_classification(coordinate, tile_by_coordinate)
                failure_reason = None
                relocated_from_before = coordinate != before_coordinate
                if (
                    request_seen
                    and observed["request_result"] != verifier.MAP_TELEPORT_RESULT_OK
                ):
                    failure_reason = (
                        "teleport request rejected: "
                        f"{verifier.request_result_name(observed['request_result'])}"
                    )
                elif observed["map_id"] != int(destination["map_id"]):
                    failure_reason = f"map mismatch: got {observed['map_id']}"
                elif not relocated_from_before:
                    failure_reason = "teleport request or coordinate relocation was not observed"
                elif not host_classification["strict_loaded_cell_land"]:
                    failure_reason = f"coordinate was not in generated random tile set: {coordinate}"
                elif pixels < args.min_nonblack_pixels:
                    failure_reason = f"screenshot looked black/unloaded: {pixels} nonblack pixels"

                results.append(
                    {
                        "run": run,
                        "destination_index": index,
                        "symbol": destination["symbol"],
                        "map_id": destination["map_id"],
                        "status_before": status_before,
                        "observed": observed,
                        "coordinate": {"x": observed["x"], "y": observed["y"]},
                        "frames_waited": frames_waited,
                        "nonblack_pixels": pixels,
                        "request_seen": request_seen,
                        "request_delta": request_delta,
                        "runtime_request_result_name": verifier.request_result_name(
                            observed["request_result"]
                        ),
                        "request_or_relocation_observed": request_seen
                        or relocated_from_before,
                        "counter_observability_limit": (
                            "request_count may reset across overlay reload; "
                            "stale runs are rejected unless the final coordinate "
                            "differs from the pre-trigger status"
                        ),
                        "host_land_classification": host_classification,
                        "valid_random_tile_count": len(valid_tiles),
                        "valid_random_tile_evidence": coordinate_evidence(valid_tiles),
                        "compact_cross_map_coordinates": [
                            {"x": x, "y": y}
                            for x, y in sorted(compact_coordinates)
                        ],
                        "forced_destination_index_written": index,
                        "random_selection_center": {
                            "x": selection_center[0],
                            "y": selection_center[1],
                            "source": selection_center_source,
                        },
                        "pre_trigger_coordinate": {
                            "x": before_coordinate[0],
                            "y": before_coordinate[1],
                        },
                        "coordinate_delta_from_pre_trigger": {
                            "dx": observed["x"] - before_coordinate[0],
                            "dy": observed["y"] - before_coordinate[1],
                        },
                        "entry_coordinate": {
                            "x": entry_coordinate[0],
                            "y": entry_coordinate[1],
                        },
                        "relocated_from_entry": coordinate != entry_coordinate,
                        "relocated_from_status_before": relocated_from_before,
                        "passed": failure_reason is None,
                        "failure_reason": failure_reason,
                    }
                )
        finally:
            if emu is not None:
                emu.destroy()

    return results, entry, ready_frames


def main() -> int:
    args = parse_args()
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    if args.runs <= 0:
        raise ValueError("--runs must be greater than zero")
    if args.min_unique_coordinates <= 0:
        raise ValueError("--min-unique-coordinates must be greater than zero")
    if args.sample_interval <= 0:
        raise ValueError("--sample-interval must be greater than zero")

    rom = repo_path(args.rom)
    if not rom.is_file():
        raise FileNotFoundError(f"ROM not found: {rom}")
    if args.dsv and args.sav:
        raise ValueError("Use either --dsv or --sav, not both.")
    if args.sav:
        save_path = headless.find_sav(args.sav)
        raw_save = save_path.read_bytes()
        save_kind = "sav"
    else:
        save_path = headless.find_dsv(args.dsv)
        raw_save = headless.extract_raw_save(save_path)
        save_kind = "dsv"

    destinations = verifier.load_destinations(repo_path(args.destinations))
    started_at = time.monotonic()
    symbols = args.map_symbols or [DEFAULT_MAP_SYMBOL]
    oracle = RandomTileOracle()
    all_results: list[dict[str, Any]] = []
    destination_summaries: list[dict[str, Any]] = []
    entry = verifier.empty_destination_entry()
    ready_frames = 0

    for symbol in symbols:
        index, destination = find_destination(destinations, symbol)
        valid_tiles = oracle.entry_tiles(destination)
        results, entry, ready_frames = run_random_tile_sequence(
            args,
            rom,
            raw_save,
            index,
            destination,
            oracle,
        )
        all_results.extend(results)
        destination_summaries.append(
            {
                "symbol": destination["symbol"],
                "map_id": destination["map_id"],
                "destination_index": index,
                "primary_x": destination["x"],
                "primary_y": destination["y"],
                "valid_random_tile_count": len(valid_tiles),
                "valid_random_tile_evidence": coordinate_evidence(valid_tiles),
                "runs": len(results),
                "passed_run_count": sum(1 for result in results if result["passed"]),
                "failed_run_count": sum(1 for result in results if not result["passed"]),
            }
        )
    results = all_results
    unique_coordinates = sorted(
        {
            (int(result["coordinate"]["x"]), int(result["coordinate"]["y"]))
            for result in results
            if result["passed"]
        }
    )
    failures = [result for result in results if not result["passed"]]
    summary = {
        "rom": display_path(rom),
        "save": display_path(save_path),
        "save_kind": save_kind,
        "destinations": display_path(repo_path(args.destinations)),
        "destination_count": len(destinations),
        "destinations_under_test": destination_summaries,
        "runs": args.runs,
        "total_runs": len(results),
        "passed_run_count": len(results) - len(failures),
        "failed_run_count": len(failures),
        "unique_coordinates": [
            {"x": x, "y": y}
            for x, y in unique_coordinates
        ],
        "unique_coordinate_count": len(unique_coordinates),
        "min_unique_coordinates": args.min_unique_coordinates,
        "destination_entry": entry,
        "ready_frames": ready_frames,
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
        "passed": (
            len(destinations) == verifier.DEFAULT_EXPECT_COUNT
            and entry["magic"] == verifier.ENCOUNTER_DESTINATION_MAGIC
            and entry["count"] == verifier.DEFAULT_EXPECT_COUNT
            and all(
                destination["valid_random_tile_count"] >= args.min_unique_coordinates
                for destination in destination_summaries
            )
            and len(failures) == 0
            and len(unique_coordinates) >= args.min_unique_coordinates
        ),
        "failures": failures,
    }

    json_path = repo_path(args.json)
    jsonl_path = repo_path(args.jsonl)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.write_text(
        "".join(json.dumps(result, sort_keys=True) + "\n" for result in results),
        encoding="utf-8",
    )
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
