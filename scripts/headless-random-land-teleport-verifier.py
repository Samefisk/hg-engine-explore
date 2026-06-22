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
    parser.add_argument("--map-symbol", default=DEFAULT_MAP_SYMBOL)
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


def destination_random_tiles(destination: dict[str, Any]) -> list[dict[str, Any]]:
    tiles = destination.get("random_tiles")
    if isinstance(tiles, list) and tiles:
        return tiles

    generator = verifier.generator
    matrix_narc = generator.ndspy.narc.NARC.fromFile(repo_path("base/root/a/0/4/1"))
    land_narc = generator.ndspy.narc.NARC.fromFile(repo_path("base/root/a/0/6/5"))
    event_narc = generator.ndspy.narc.NARC.fromFile(repo_path("base/root/a/0/3/2"))
    arm9 = repo_path("base/arm9.bin").read_bytes()
    return list(
        generator.loaded_window_random_tile_candidates(
            center_x=int(destination["x"]),
            center_y=int(destination["y"]),
            loaded_map_id=int(destination["map_id"]),
            fallback_map_id=int(destination["map_id"]),
            source="verifier",
            matrix_narc=matrix_narc,
            land_narc=land_narc,
            event_narc=event_narc,
            arm9=arm9,
            matrix_cache={},
            permission_cache={},
        )
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
    entry_coordinate = (int(destination["x"]), int(destination["y"]))
    while frames_waited <= args.max_wait_frames:
        request_seen = verifier.request_count_changed(
            status_before["request_count"],
            observed["request_count"],
        )
        request_delta = (
            (observed["request_count"] - status_before["request_count"]) & 0xFFFF
        )
        if request_seen and observed["request_result"] != verifier.MAP_TELEPORT_RESULT_OK:
            return observed, frames_waited
        if (
            observed["ready"] != 0
            and observed["map_id"] == int(destination["map_id"])
            and (observed["x"], observed["y"]) != entry_coordinate
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
    valid_tiles: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int], int]:
    emu = None
    entry = verifier.empty_destination_entry()
    ready_frames = 0
    status_before = verifier.empty_status()
    ready_failure = "emulator was not opened"
    valid_coordinates = {(int(tile["x"]), int(tile["y"])) for tile in valid_tiles}
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
                failure_reason = None
                entry_coordinate = (int(destination["x"]), int(destination["y"]))
                relocated = coordinate != entry_coordinate
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
                elif not relocated:
                    failure_reason = "final coordinate stayed on the entry tile"
                elif coordinate not in valid_coordinates:
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
                        "entry_coordinate": {
                            "x": entry_coordinate[0],
                            "y": entry_coordinate[1],
                        },
                        "relocated_from_entry": relocated,
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
    index, destination = find_destination(destinations, args.map_symbol)
    valid_tiles = destination_random_tiles(destination)
    started_at = time.monotonic()

    results, entry, ready_frames = run_random_tile_sequence(
        args,
        rom,
        raw_save,
        index,
        destination,
        valid_tiles,
    )
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
        "destination_index": index,
        "destination": {
            "symbol": destination["symbol"],
            "map_id": destination["map_id"],
            "primary_x": destination["x"],
            "primary_y": destination["y"],
        },
        "valid_random_tile_evidence": coordinate_evidence(valid_tiles),
        "valid_random_tile_count": len(valid_tiles),
        "runs": args.runs,
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
            and len(valid_tiles) >= args.min_unique_coordinates
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
