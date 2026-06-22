#!/usr/bin/env python3
"""Verify L+R map teleport transition does not show the Fly white flash."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESTINATION_INDEX = 47


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
        return path.name


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
    parser.add_argument("--destination-index", type=int, default=DEFAULT_DESTINATION_INDEX)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--screenshot-dir", type=Path)
    parser.add_argument("--include-samples", action="store_true")
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
    parser.add_argument("--sample-frames", type=int, default=240)
    parser.add_argument("--sample-interval", type=int, default=3)
    parser.add_argument("--expect-request-frame", type=int, default=3)
    parser.add_argument("--min-nonblack-pixels", type=int, default=1000)
    parser.add_argument("--solid-white-min-channel", type=int, default=240)
    parser.add_argument("--show-emulator-log", action="store_true")
    return parser.parse_args()


def pixel_metrics(image: Any, args: argparse.Namespace) -> dict[str, Any]:
    pixels = list(image.getdata())
    total = len(pixels)
    red = sum(pixel[0] for pixel in pixels) / total
    green = sum(pixel[1] for pixel in pixels) / total
    blue = sum(pixel[2] for pixel in pixels) / total
    min_channel = min(min(pixel) for pixel in pixels)
    max_channel = max(max(pixel) for pixel in pixels)
    nonblack_pixels = sum(1 for r, g, b in pixels if r + g + b > 24)
    return {
        "mean_rgb": [round(red, 3), round(green, 3), round(blue, 3)],
        "min_channel": min_channel,
        "max_channel": max_channel,
        "nonblack_pixels": nonblack_pixels,
        "solid_white": min_channel >= args.solid_white_min_channel,
    }


def frame_metrics(image: Any, args: argparse.Namespace) -> dict[str, Any]:
    image = image.convert("RGB")
    width, height = image.size
    split_y = height // 2
    whole = pixel_metrics(image, args)
    top = pixel_metrics(image.crop((0, 0, width, split_y)), args)
    bottom = pixel_metrics(image.crop((0, split_y, width, height)), args)
    return {
        "whole": whole,
        "top": top,
        "bottom": bottom,
        "solid_white": (
            whole["solid_white"]
            or top["solid_white"]
            or bottom["solid_white"]
        ),
    }


def save_frame(
    screenshot_dir: Path | None,
    frame: int,
    image: Any,
) -> str | None:
    if screenshot_dir is None:
        return None
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    path = screenshot_dir / f"frame_{frame:03d}.png"
    image.save(path)
    return str(path)


def sample_phase(frame: int, args: argparse.Namespace) -> str:
    if frame < args.trigger_frames:
        return "hold"
    if frame < args.trigger_frames + args.release_frames:
        return "release"
    return "post_release"


def sample_transition(
    args: argparse.Namespace,
    emu: Any,
    status_before: dict[str, int],
    destination: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, Any] | None]:
    samples: list[dict[str, Any]] = []
    request_evidence: dict[str, Any] | None = None
    screenshot_dir = repo_path(args.screenshot_dir) if args.screenshot_dir else None
    key_mask = headless.combo_key_mask("L+R")
    total_frames = args.trigger_frames + args.release_frames + args.sample_frames

    if args.trigger_frames > 0:
        emu.input.keypad_add_key(key_mask)
    try:
        for frame in range(total_frames + 1):
            if frame % args.sample_interval == 0:
                status = verifier.read_status(emu)
                image = emu.screenshot()
                metrics = frame_metrics(image, args)
                path = save_frame(screenshot_dir, frame, image)
                if (
                    request_evidence is None
                    and verifier.request_count_changed(
                        status_before["request_count"],
                        status["request_count"],
                    )
                ):
                    request_evidence = {
                        "frame": frame,
                        "request_result": status["request_result"],
                        "destination_index": status["destination_index"],
                    }
                samples.append(
                    {
                        "frame": frame,
                        "keys_held": frame < args.trigger_frames,
                        "phase": sample_phase(frame, args),
                        "status": status,
                        "path": path,
                        **metrics,
                    }
                )

            if frame < total_frames:
                headless.cycle(emu, 1)
                if frame + 1 == args.trigger_frames:
                    emu.input.keypad_rm_key(key_mask)
    finally:
        emu.input.keypad_rm_key(key_mask)

    return samples, verifier.read_status(emu), request_evidence


def main() -> int:
    args = parse_args()
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    rom = repo_path(args.rom)
    if not rom.is_file():
        raise FileNotFoundError(f"ROM not found: {rom}")
    if args.dsv and args.sav:
        raise ValueError("Use either --dsv or --sav, not both.")
    if args.sample_interval <= 0:
        raise ValueError("sample interval must be greater than zero")
    if args.trigger_frames < 0 or args.release_frames < 0:
        raise ValueError("trigger and release frames must be non-negative")

    if args.sav:
        save_path = headless.find_sav(args.sav)
        raw_save = save_path.read_bytes()
        save_kind = "sav"
    else:
        save_path = headless.find_dsv(args.dsv)
        raw_save = headless.extract_raw_save(save_path)
        save_kind = "dsv"

    destinations = verifier.load_destinations(repo_path(args.destinations))
    if args.destination_index < 0 or args.destination_index >= len(destinations):
        raise IndexError(f"destination index {args.destination_index} outside destination table")
    destination = destinations[args.destination_index]

    started_at = time.monotonic()
    emu = None
    entry = verifier.empty_destination_entry()
    status_before = verifier.empty_status()
    ready_failure = "emulator was not opened"
    samples: list[dict[str, Any]] = []
    final_status = verifier.empty_status()
    request_evidence: dict[str, Any] | None = None

    with headless.silence_native_output(not args.show_emulator_log):
        try:
            for _attempt in range(1, args.ready_boot_attempts + 1):
                emu, _ready_frames, entry, status_before, ready_failure = (
                    verifier.open_ready_emulator(args, rom, raw_save)
                )
                if ready_failure is None:
                    break
                emu.destroy()
                emu = None
            if ready_failure is not None:
                raise RuntimeError(f"initial field state not ready: {ready_failure}")

            verifier.write_destination(emu, destination)
            verifier.force_debug_destination(emu)
            samples, final_status, request_evidence = sample_transition(
                args,
                emu,
                status_before,
                destination,
            )
        finally:
            if emu is not None:
                emu.destroy()

    solid_white_frames = [sample for sample in samples if sample["solid_white"]]
    whole_solid_white_frames = [
        sample for sample in samples if sample["whole"]["solid_white"]
    ]
    top_solid_white_frames = [
        sample for sample in samples if sample["top"]["solid_white"]
    ]
    bottom_solid_white_frames = [
        sample for sample in samples if sample["bottom"]["solid_white"]
    ]
    landed = verifier.status_matches_destination(destination, final_status)
    final_nonblack_ok = (
        samples[-1]["whole"]["nonblack_pixels"] >= args.min_nonblack_pixels
        if samples
        else False
    )
    request_ok = (
        request_evidence is not None
        and request_evidence["request_result"] == verifier.MAP_TELEPORT_RESULT_OK
    )
    request_frame_ok = (
        request_evidence is not None
        and request_evidence["frame"] == args.expect_request_frame
    )
    total_sample_frames = args.trigger_frames + args.release_frames + args.sample_frames
    summary = {
        "rom": display_path(rom),
        "save": display_path(save_path),
        "save_kind": save_kind,
        "destination_count": len(destinations),
        "destination_index": args.destination_index,
        "destination": {
            "symbol": destination["symbol"],
            "map_id": destination["map_id"],
            "x": destination["x"],
            "y": destination["y"],
        },
        "destination_entry": entry,
        "status_before": status_before,
        "request_evidence": request_evidence,
        "final_status": final_status,
        "trigger_frames": args.trigger_frames,
        "release_frames": args.release_frames,
        "post_release_sample_frames": args.sample_frames,
        "total_sample_frames": total_sample_frames,
        "sample_interval": args.sample_interval,
        "expect_request_frame": args.expect_request_frame,
        "request_frame_ok": request_frame_ok,
        "solid_white_frame_count": len(solid_white_frames),
        "solid_white_frames": [sample["frame"] for sample in solid_white_frames],
        "solid_white_whole_frame_count": len(whole_solid_white_frames),
        "solid_white_whole_frames": [
            sample["frame"] for sample in whole_solid_white_frames
        ],
        "solid_white_top_frame_count": len(top_solid_white_frames),
        "solid_white_top_frames": [
            sample["frame"] for sample in top_solid_white_frames
        ],
        "solid_white_bottom_frame_count": len(bottom_solid_white_frames),
        "solid_white_bottom_frames": [
            sample["frame"] for sample in bottom_solid_white_frames
        ],
        "whole_solid_white_frame_count": len(whole_solid_white_frames),
        "whole_solid_white_frames": [
            sample["frame"] for sample in whole_solid_white_frames
        ],
        "top_solid_white_frame_count": len(top_solid_white_frames),
        "top_solid_white_frames": [
            sample["frame"] for sample in top_solid_white_frames
        ],
        "bottom_solid_white_frame_count": len(bottom_solid_white_frames),
        "bottom_solid_white_frames": [
            sample["frame"] for sample in bottom_solid_white_frames
        ],
        "white_detection": {
            "whole": {
                "passed": len(whole_solid_white_frames) == 0,
                "frames": [sample["frame"] for sample in whole_solid_white_frames],
            },
            "top": {
                "passed": len(top_solid_white_frames) == 0,
                "frames": [sample["frame"] for sample in top_solid_white_frames],
            },
            "bottom": {
                "passed": len(bottom_solid_white_frames) == 0,
                "frames": [sample["frame"] for sample in bottom_solid_white_frames],
            },
        },
        "sample_count": len(samples),
        "landed": landed,
        "request_ok": request_ok,
        "final_nonblack_ok": final_nonblack_ok,
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
        "passed": (
            len(destinations) == verifier.DEFAULT_EXPECT_COUNT
            and entry["magic"] == verifier.ENCOUNTER_DESTINATION_MAGIC
            and entry["count"] == verifier.DEFAULT_EXPECT_COUNT
            and request_ok
            and request_frame_ok
            and landed
            and final_nonblack_ok
            and len(solid_white_frames) == 0
        ),
    }
    if args.include_samples:
        summary["samples"] = samples

    if args.json is not None:
        json_path = repo_path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
