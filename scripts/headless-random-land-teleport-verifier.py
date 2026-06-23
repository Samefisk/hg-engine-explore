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
PROVED_DARK_RENDER_MAPS = {
    "MAP_D24R0202",
    "MAP_D42R0102",
    "MAP_D45R0102",
}


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
    parser.add_argument("--min-top-nonblack-pixels", type=int, default=12000)
    parser.add_argument("--max-top-black-ratio", type=float, default=0.45)
    parser.add_argument("--max-top-water-like-ratio", type=float, default=0.55)
    parser.add_argument("--max-top-center-black-ratio", type=float, default=0.55)
    parser.add_argument("--max-top-center-water-like-ratio", type=float, default=0.70)
    parser.add_argument("--movement-probe-frames", type=int, default=24)
    parser.add_argument("--movement-probe-release-frames", type=int, default=18)
    parser.add_argument("--min-render-probe-top-nonblack-pixels", type=int, default=2500)
    parser.add_argument("--max-render-probe-top-black-ratio", type=float, default=0.95)
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


def visual_metrics(image: Any) -> dict[str, Any]:
    image = image.convert("RGB")
    width, height = image.size
    top = image.crop((0, 0, width, height // 2))
    center = top.crop((width // 2 - 56, height // 4 - 48, width // 2 + 56, height // 4 + 48))

    def region_metrics(region: Any) -> dict[str, Any]:
        pixels = list(region.getdata())
        total = len(pixels)
        black = sum(1 for r, g, b in pixels if r + g + b <= 24)
        nonblack = total - black
        water_like = sum(
            1
            for r, g, b in pixels
            if (
                (b >= 130 and g >= 70 and r <= 120 and b > r + 40)
                or (g >= 140 and b >= 120 and r <= 120)
            )
        )
        return {
            "nonblack_pixels": nonblack,
            "black_ratio": round(black / total, 4),
            "water_like_ratio": round(water_like / total, 4),
        }

    top_metrics = region_metrics(top)
    center_metrics = region_metrics(center)
    return {
        "top_nonblack_pixels": top_metrics["nonblack_pixels"],
        "top_black_ratio": top_metrics["black_ratio"],
        "top_water_like_ratio": top_metrics["water_like_ratio"],
        "top_center_nonblack_pixels": center_metrics["nonblack_pixels"],
        "top_center_black_ratio": center_metrics["black_ratio"],
        "top_center_water_like_ratio": center_metrics["water_like_ratio"],
    }


def visual_failure_reason(args: argparse.Namespace, pixels: int, screen: dict[str, Any]) -> str | None:
    if pixels < args.min_nonblack_pixels:
        return f"screenshot looked black/unloaded: {pixels} nonblack pixels"
    if screen["top_nonblack_pixels"] < args.min_top_nonblack_pixels:
        return (
            "top screen looked black/unloaded: "
            f"{screen['top_nonblack_pixels']} nonblack pixels"
        )
    if screen["top_black_ratio"] > args.max_top_black_ratio:
        return f"top screen had too much black void: {screen['top_black_ratio']}"
    if screen["top_water_like_ratio"] > args.max_top_water_like_ratio:
        return f"top screen looked water/cyan dominated: {screen['top_water_like_ratio']}"
    if screen["top_center_black_ratio"] > args.max_top_center_black_ratio:
        return f"top center looked like black void: {screen['top_center_black_ratio']}"
    if screen["top_center_water_like_ratio"] > args.max_top_center_water_like_ratio:
        return (
            "top center looked water/cyan dominated: "
            f"{screen['top_center_water_like_ratio']}"
        )
    return None


def movement_probe(args: argparse.Namespace, emu: Any, start_status: dict[str, int]) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "enabled": args.movement_probe_frames > 0,
        "start_status": start_status,
        "attempts": [],
        "moved_on_same_map": False,
    }
    if args.movement_probe_frames <= 0:
        return evidence

    for direction in ("UP", "DOWN", "LEFT", "RIGHT"):
        before = verifier.read_status(emu)
        headless.hold_key(
            emu,
            direction,
            args.movement_probe_frames,
            args.movement_probe_release_frames,
        )
        after = verifier.read_status(emu)
        screen = visual_metrics(emu.screenshot())
        moved = (
            after["ready"] != 0
            and after["map_id"] == start_status["map_id"]
            and (after["x"], after["y"]) != (before["x"], before["y"])
        )
        evidence["attempts"].append(
            {
                "direction": direction,
                "before": before,
                "after": after,
                "moved_on_same_map": moved,
                "visual_metrics_after": screen,
            }
        )
        if moved:
            evidence["moved_on_same_map"] = True
            evidence["final_status"] = after
            evidence["final_visual_metrics"] = screen
            break
    else:
        evidence["final_status"] = verifier.read_status(emu)
        evidence["final_visual_metrics"] = visual_metrics(emu.screenshot())
    return evidence


def render_probe_allows_dark_map(
    args: argparse.Namespace,
    destination: dict[str, Any],
    visual_reason: str | None,
    screen: dict[str, Any],
    probe: dict[str, Any],
) -> bool:
    if destination["symbol"] not in PROVED_DARK_RENDER_MAPS:
        return False
    if visual_reason is None:
        return True
    if not (
        visual_reason.startswith("top screen had too much black void")
        or visual_reason.startswith("top screen looked black/unloaded")
    ):
        return False
    if screen["top_nonblack_pixels"] < args.min_render_probe_top_nonblack_pixels:
        return False
    if not probe.get("moved_on_same_map"):
        return False
    probe_screen = probe.get("final_visual_metrics", {})
    return (
        probe_screen.get("top_nonblack_pixels", 0)
        >= args.min_render_probe_top_nonblack_pixels
        and probe_screen.get("top_black_ratio", 1.0)
        <= args.max_render_probe_top_black_ratio
        and probe_screen.get("top_water_like_ratio", 1.0)
        <= args.max_top_water_like_ratio
    )


def host_land_classification(
    coordinate: tuple[int, int],
    broad_tile_by_coordinate: dict[tuple[int, int], dict[str, Any]],
    preferred_tile_by_coordinate: dict[tuple[int, int], dict[str, Any]],
) -> dict[str, Any]:
    preferred_available = bool(preferred_tile_by_coordinate)
    tile = (
        preferred_tile_by_coordinate.get(coordinate)
        if preferred_available
        else broad_tile_by_coordinate.get(coordinate)
    )
    broad_tile = broad_tile_by_coordinate.get(coordinate)
    classification: dict[str, Any] = {
        "strict_loaded_cell_land": tile is not None,
        "broad_loaded_cell_land": broad_tile is not None,
        "preferred_permission_nonzero_available": preferred_available,
        "predicate": (
            "same loaded 32x32 matrix cell as this run's selection center, "
            "in ROM random window, warp/coord-event-unblocked, permission high bit clear, "
            "behavior < 16, non-headbutt; when any same-cell candidate has nonzero "
            "permission, the advisory preferred subset records that evidence"
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
    elif broad_tile is not None:
        permission = int(broad_tile["permission"])
        classification.update(
            {
                "broad_permission": f"0x{permission:04X}",
                "broad_behavior": permission & 0xFF,
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
    staging_coordinates: set[tuple[int, int]],
    warp_anchor_hint: int | None,
    use_current_map_helper: bool,
    status_before: dict[str, int],
) -> tuple[dict[str, int], int]:
    frames_waited = 0
    observed = verifier.read_status(emu)
    before_coordinate = (status_before["x"], status_before["y"])
    while frames_waited <= args.max_wait_frames:
        coordinate = (observed["x"], observed["y"])
        request_seen = verifier.request_count_changed(
            status_before["request_count"],
            observed["request_count"],
        )
        request_delta = (
            (observed["request_count"] - status_before["request_count"]) & 0xFFFF
        )
        if (
            request_seen
            and observed["request_result"] == verifier.MAP_TELEPORT_RESULT_OK
            and observed["ready"] != 0
            and observed["map_id"] == int(destination["map_id"])
            and coordinate != before_coordinate
            and (
                use_current_map_helper
                or (warp_anchor_hint is None and coordinate in staging_coordinates)
                or warp_anchor_hint is not None
            )
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
                else:
                    selection_center = entry_coordinate
                    selection_center_source = "destination_entry"
                staging_coordinates = {
                    entry_coordinate,
                    (entry_coordinate[0] + 1, entry_coordinate[1]),
                }
                warp_anchor_hint = destination.get("warp_id")
                use_current_map_helper = (
                    warp_anchor_hint is None
                    and status_before["map_id"] == int(destination["map_id"])
                )
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
                tile_by_coordinate = {
                    (int(tile["x"]), int(tile["y"])): tile
                    for tile in strict_tiles
                }
                preferred_tiles = [
                    tile for tile in strict_tiles
                    if int(tile["permission"]) != 0
                ]
                preferred_tile_by_coordinate = {
                    (int(tile["x"]), int(tile["y"])): tile
                    for tile in preferred_tiles
                }
                headless.hold_combo(emu, "L+R", args.trigger_frames, args.release_frames)
                request_observed, frames_waited = wait_for_random_outcome(
                    args,
                    emu,
                    destination,
                    staging_coordinates,
                    warp_anchor_hint,
                    use_current_map_helper,
                    status_before,
                )
                headless.cycle(emu, args.between_run_wait_frames)
                settled_status = verifier.read_status(emu)
                screenshot = emu.screenshot()
                pixels = verifier.nonblack_pixel_count(emu)
                screen = visual_metrics(screenshot)
                probe = movement_probe(args, emu, settled_status)
                request_seen = verifier.request_count_changed(
                    status_before["request_count"],
                    request_observed["request_count"],
                )
                request_delta = (
                    (request_observed["request_count"] - status_before["request_count"]) & 0xFFFF
                )
                coordinate = (settled_status["x"], settled_status["y"])
                request_coordinate = (request_observed["x"], request_observed["y"])
                host_classification = host_land_classification(
                    coordinate,
                    tile_by_coordinate,
                    preferred_tile_by_coordinate,
                )
                screen_failure = visual_failure_reason(args, pixels, screen)
                render_probe_allowed = render_probe_allows_dark_map(
                    args,
                    destination,
                    screen_failure,
                    screen,
                    probe,
                )
                failure_reason = None
                relocated_from_before = coordinate != before_coordinate
                if request_observed["request_result"] != verifier.MAP_TELEPORT_RESULT_OK:
                    failure_reason = (
                        "teleport request rejected: "
                        f"{verifier.request_result_name(request_observed['request_result'])}"
                    )
                elif not request_seen:
                    failure_reason = "teleport request counter/result evidence was not observed"
                elif request_observed["map_id"] != int(destination["map_id"]):
                    failure_reason = f"request map mismatch: got {request_observed['map_id']}"
                elif request_coordinate == before_coordinate:
                    failure_reason = "request did not relocate from the pre-trigger coordinate"
                elif (
                    not use_current_map_helper
                    and warp_anchor_hint is None
                    and request_coordinate not in staging_coordinates
                ):
                    failure_reason = (
                        "direct compact-pair row landed outside generated pair: "
                        f"{request_coordinate}"
                    )
                elif (
                    not use_current_map_helper
                    and warp_anchor_hint is None
                    and coordinate not in staging_coordinates
                ):
                    failure_reason = (
                        "direct compact-pair row settled outside generated pair: "
                        f"{coordinate}"
                    )
                elif settled_status["map_id"] != int(destination["map_id"]):
                    failure_reason = f"settled map mismatch: got {settled_status['map_id']}"
                elif coordinate != request_coordinate:
                    failure_reason = (
                        "settled coordinate drifted after final request: "
                        f"request={request_coordinate} settled={coordinate}"
                    )
                elif screen_failure is not None and not render_probe_allowed:
                    failure_reason = screen_failure

                results.append(
                    {
                        "run": run,
                        "destination_index": index,
                        "symbol": destination["symbol"],
                        "map_id": destination["map_id"],
                        "status_before": status_before,
                        "observed": request_observed,
                        "settled_status": settled_status,
                        "coordinate": {"x": settled_status["x"], "y": settled_status["y"]},
                        "frames_waited": frames_waited,
                        "nonblack_pixels": pixels,
                        "visual_metrics": screen,
                        "visual_failure_reason": screen_failure,
                        "movement_probe": probe,
                        "render_probe_allows_dark_map": render_probe_allowed,
                        "request_seen": request_seen,
                        "request_delta": request_delta,
                        "runtime_request_result_name": verifier.request_result_name(
                            request_observed["request_result"]
                        ),
                        "request_or_relocation_observed": request_seen
                        or relocated_from_before,
                        "counter_observability_limit": (
                            "request_count is mirrored through persistent runtime "
                            "state; indexed random-land runs require a fresh OK "
                            "request for the generated compact pair or stock "
                            "warp-anchor feature path"
                        ),
                        "host_land_classification": host_classification,
                        "host_land_classification_role": (
                            "advisory static same-cell terrain/event evidence; "
                            "header-wildcard rooms proved this parser can disagree "
                            "with live rendered/walkable runtime state, so hard "
                            "acceptance uses runtime OK, non-staging relocation, "
                            "settled status, top-screen gates, and movement/"
                            "renderability probe evidence"
                        ),
                        "valid_random_tile_count": len(valid_tiles),
                        "valid_random_tile_evidence": coordinate_evidence(valid_tiles),
                        "strict_same_cell_tile_count": len(strict_tiles),
                        "preferred_nonzero_permission_tile_count": len(preferred_tiles),
                        "preferred_nonzero_permission_tile_evidence": coordinate_evidence(
                            preferred_tiles
                        ),
                        "staging_coordinates": [
                            {"x": x, "y": y}
                            for x, y in sorted(staging_coordinates)
                        ],
                        "warp_anchor_hint": warp_anchor_hint,
                        "feature_path": (
                            "stock-warp-anchor"
                            if warp_anchor_hint is not None
                            else "current-loaded-land-helper"
                            if use_current_map_helper
                            else "generated-compact-pair"
                        ),
                        "after_load_relocation_required": False,
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
                            "dx": settled_status["x"] - before_coordinate[0],
                            "dy": settled_status["y"] - before_coordinate[1],
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
        "land_authority_note": (
            "Host strict-land membership is advisory static same-cell terrain/event "
            "evidence. Header-wildcard rooms can disagree with live runtime "
            "permission/render state, so passing rows require runtime request_result "
            "OK, fresh request counter evidence, generated compact-pair acceptance "
            "or stock warp-anchor acceptance, settled coordinate stability, "
            "top-screen loaded/water/void gates, and movement/render probe evidence "
            "for black-heavy maps."
        ),
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
