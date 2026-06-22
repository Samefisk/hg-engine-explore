#!/usr/bin/env python3
"""Verify L+R teleport destinations for every authoritative encounter map."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DESTINATION_ADDR = 0x023C8014
DEBUG_STATUS_ADDR = 0x023C801C
DEBUG_STATUS_MAGIC = 0x4D545053
DEBUG_STATUS_VERSION = 1
DEBUG_STATUS_SIZE = 24
ENCOUNTER_DESTINATION_ENTRY_ADDR = 0x023C8034
ENCOUNTER_DESTINATION_MAGIC = 0x4D544544
ENCOUNTER_DESTINATION_VERSION = 1
DEFAULT_EXPECT_COUNT = 150
MAP_TELEPORT_RESULT_OK = 0
MAP_TELEPORT_RESULT_NAMES = {
    0: "OK",
    1: "OVERLAY_UNAVAILABLE",
    2: "INVALID_FIELD",
    3: "FIELD_BUSY",
    4: "INVALID_DESTINATION",
    5: "UNSAFE_LOADED_TILE",
}


def ensure_repo_venv() -> None:
    venv = REPO_ROOT / ".venv"
    venv_python = venv / "bin/python3"
    if Path(sys.prefix).resolve() == venv.resolve():
        return
    if not venv_python.is_file():
        return
    os.execv(str(venv_python), [str(venv_python), *sys.argv])


ensure_repo_venv()

import generate_encounter_map_teleport_destinations as generator  # type: ignore  # noqa: E402
from desmume.emulator import DeSmuME  # type: ignore  # noqa: E402


def import_script(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


headless = import_script(REPO_ROOT / "scripts/headless-overworld-test.py", "headless_overworld_test")


def repo_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def read_u16(emu: DeSmuME, address: int) -> int:
    value = emu.memory.unsigned[address : address + 2 : 1]
    if isinstance(value, (bytes, bytearray)):
        return int.from_bytes(value, "little")
    if isinstance(value, list):
        return int(value[0]) | (int(value[1]) << 8)
    return int(value)


def read_u32(emu: DeSmuME, address: int) -> int:
    value = emu.memory.unsigned[address : address + 4 : 1]
    if isinstance(value, (bytes, bytearray)):
        return int.from_bytes(value, "little")
    if isinstance(value, list):
        return (
            int(value[0])
            | (int(value[1]) << 8)
            | (int(value[2]) << 16)
            | (int(value[3]) << 24)
        )
    return int(value)


def write_u16(emu: DeSmuME, address: int, value: int) -> None:
    value &= 0xFFFF
    emu.memory.unsigned[address : address + 2 : 1] = [value & 0xFF, value >> 8]


def read_status(emu: DeSmuME) -> dict[str, int]:
    return {
        "magic": read_u32(emu, DEBUG_STATUS_ADDR),
        "version": read_u16(emu, DEBUG_STATUS_ADDR + 4),
        "size": read_u16(emu, DEBUG_STATUS_ADDR + 6),
        "map_id": read_u16(emu, DEBUG_STATUS_ADDR + 8),
        "x": read_u16(emu, DEBUG_STATUS_ADDR + 10),
        "y": read_u16(emu, DEBUG_STATUS_ADDR + 12),
        "direction": read_u16(emu, DEBUG_STATUS_ADDR + 14),
        "request_result": read_u16(emu, DEBUG_STATUS_ADDR + 16),
        "request_count": read_u16(emu, DEBUG_STATUS_ADDR + 18),
        "ready": read_u16(emu, DEBUG_STATUS_ADDR + 20),
    }


def read_destination_entry(emu: DeSmuME) -> dict[str, int]:
    return {
        "magic": read_u32(emu, ENCOUNTER_DESTINATION_ENTRY_ADDR),
        "version": read_u16(emu, ENCOUNTER_DESTINATION_ENTRY_ADDR + 4),
        "size": read_u16(emu, ENCOUNTER_DESTINATION_ENTRY_ADDR + 6),
        "count": read_u16(emu, ENCOUNTER_DESTINATION_ENTRY_ADDR + 8),
    }


def write_destination(emu: DeSmuME, destination: dict[str, Any]) -> None:
    write_u16(emu, DEBUG_DESTINATION_ADDR, int(destination["map_id"]))
    write_u16(emu, DEBUG_DESTINATION_ADDR + 2, int(destination["x"]))
    write_u16(emu, DEBUG_DESTINATION_ADDR + 4, int(destination["y"]))
    write_u16(emu, DEBUG_DESTINATION_ADDR + 6, int(destination["direction"]))


def empty_status() -> dict[str, int]:
    return {
        "magic": 0,
        "version": 0,
        "size": 0,
        "map_id": 0,
        "x": 0,
        "y": 0,
        "direction": 0,
        "request_result": 0,
        "request_count": 0,
        "ready": 0,
    }


def empty_destination_entry() -> dict[str, int]:
    return {
        "magic": 0,
        "version": 0,
        "size": 0,
        "count": 0,
    }


def request_result_name(value: int) -> str:
    return MAP_TELEPORT_RESULT_NAMES.get(value, f"UNKNOWN_{value}")


def debug_status_failure_reason(status: dict[str, int]) -> str | None:
    if status["magic"] != DEBUG_STATUS_MAGIC:
        return f"debug status magic mismatch: 0x{status['magic']:08X}"
    if status["version"] != DEBUG_STATUS_VERSION or status["size"] != DEBUG_STATUS_SIZE:
        return f"debug status version/size mismatch: {status['version']}/{status['size']}"
    if status["ready"] == 0:
        return "field system was not ready"
    return None


def request_count_changed(before: int, after: int) -> bool:
    return before != after


def nonblack_pixel_count(emu: DeSmuME) -> int:
    image = emu.screenshot().convert("RGB")
    pixels = image.getdata()
    return sum(1 for red, green, blue in pixels if red + green + blue > 24)


def load_destinations(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    destinations = data.get("destinations", [])
    if not isinstance(destinations, list):
        raise ValueError(f"{path} does not contain a destinations list")
    return destinations


def authoritative_entries() -> list[tuple[str, int, int]]:
    maps = generator.read_map_constants(REPO_ROOT / "include/constants/maps.h")
    return generator.read_authoritative_maps(
        REPO_ROOT / "data/OverworldWildEncounterLookupData.c",
        REPO_ROOT / "include/overworld_wild_behavior_data.h",
        maps,
    )


def result_failure_reason(
    destination: dict[str, Any],
    status_before: dict[str, int],
    status: dict[str, int],
    nonblack_pixels: int,
    min_nonblack_pixels: int,
) -> str | None:
    ready_failure = debug_status_failure_reason(status_before)
    if ready_failure is not None:
        return f"initial field state not ready: {ready_failure}"
    status_failure = debug_status_failure_reason(status)
    if status_failure is not None:
        return status_failure
    request_seen = request_count_changed(
        status_before["request_count"],
        status["request_count"],
    )
    if request_seen and status["request_result"] != MAP_TELEPORT_RESULT_OK:
        return (
            "teleport request rejected: "
            f"{request_result_name(status['request_result'])} ({status['request_result']})"
        )
    if status["map_id"] != int(destination["map_id"]):
        return f"map mismatch: got {status['map_id']}"
    if status["x"] != int(destination["x"]) or status["y"] != int(destination["y"]):
        return f"position mismatch: got {status['x']},{status['y']}"
    if nonblack_pixels < min_nonblack_pixels:
        return f"screenshot looked black/unloaded: {nonblack_pixels} nonblack pixels"
    return None


def wait_for_ready_status(
    args: argparse.Namespace,
    emu: DeSmuME,
) -> tuple[dict[str, int], int, str | None]:
    if args.sample_interval <= 0:
        raise ValueError("sample interval must be greater than zero")

    frames_waited = 0
    status = read_status(emu)
    while frames_waited <= args.ready_timeout_frames:
        failure_reason = debug_status_failure_reason(status)
        if failure_reason is None:
            return status, frames_waited, None
        if frames_waited == args.ready_timeout_frames:
            return status, frames_waited, failure_reason
        wait_frames = min(args.sample_interval, args.ready_timeout_frames - frames_waited)
        headless.cycle(emu, wait_frames)
        frames_waited += wait_frames
        status = read_status(emu)

    return status, frames_waited, debug_status_failure_reason(status)


def wait_for_request_outcome(
    args: argparse.Namespace,
    emu: DeSmuME,
    destination: dict[str, Any],
    status_before: dict[str, int],
) -> tuple[dict[str, int], int]:
    if args.sample_interval <= 0:
        raise ValueError("sample interval must be greater than zero")

    frames_waited = 0
    observed = read_status(emu)
    while frames_waited <= args.max_wait_frames:
        request_seen = request_count_changed(
            status_before["request_count"],
            observed["request_count"],
        )
        if request_seen and observed["request_result"] != MAP_TELEPORT_RESULT_OK:
            return observed, frames_waited
        if (
            request_seen
            and observed["ready"] != 0
            and observed["map_id"] == int(destination["map_id"])
            and observed["x"] == int(destination["x"])
            and observed["y"] == int(destination["y"])
        ):
            return observed, frames_waited
        if frames_waited == args.max_wait_frames:
            return observed, frames_waited
        wait_frames = min(args.sample_interval, args.max_wait_frames - frames_waited)
        headless.cycle(emu, wait_frames)
        frames_waited += wait_frames
        observed = read_status(emu)

    return observed, frames_waited


def open_ready_emulator(
    args: argparse.Namespace,
    rom: Path,
    raw_save: bytes,
) -> tuple[DeSmuME, int, dict[str, int], dict[str, int], str | None]:
    emu = DeSmuME()
    emu.volume_set(0)
    emu.open(str(rom))
    with tempfile.NamedTemporaryFile(suffix=".sav") as raw_file:
        raw_file.write(raw_save)
        raw_file.flush()
        emu.backup.import_file(raw_file.name, force_size=0)
        ready_frames = headless.boot_to_ready(args, emu)
        headless.cycle(emu, args.post_ready_wait_frames)
        entry = read_destination_entry(emu)
        status_before, _ready_wait_frames, ready_failure = wait_for_ready_status(args, emu)
    return emu, ready_frames, entry, status_before, ready_failure


def run_destination(
    args: argparse.Namespace,
    rom: Path,
    raw_save: bytes,
    index: int,
    destination: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, int] | None, int]:
    emu: DeSmuME | None = None
    entry: dict[str, int] | None = None
    ready_frames = 0
    status_before = empty_status()
    observed = empty_status()
    frames_waited = 0
    pixels = 0
    failure_reason: str | None = None

    try:
        emu, ready_frames, entry, status_before, ready_failure = (
            open_ready_emulator(args, rom, raw_save)
        )
        if ready_failure is not None:
            observed = status_before
            failure_reason = f"initial field state not ready: {ready_failure}"
        else:
            write_destination(emu, destination)
            headless.hold_combo(emu, "L+R", args.trigger_frames, args.release_frames)
            observed, frames_waited = wait_for_request_outcome(
                args,
                emu,
                destination,
                status_before,
            )
            headless.cycle(emu, args.release_frames)
            observed = read_status(emu)
        pixels = nonblack_pixel_count(emu)
        if failure_reason is None:
            failure_reason = result_failure_reason(
                destination,
                status_before,
                observed,
                pixels,
                args.min_nonblack_pixels,
            )
    except Exception as exc:
        failure_reason = f"verifier error: {type(exc).__name__}: {exc}"
        if emu is not None:
            try:
                observed = read_status(emu)
            except Exception:
                observed = empty_status()
            try:
                pixels = nonblack_pixel_count(emu)
            except Exception:
                pixels = 0
    finally:
        if emu is not None:
            emu.destroy()

    result = {
        "index": index,
        "symbol": destination["symbol"],
        "map_id": destination["map_id"],
        "data_id": destination["data_id"],
        "destination": {
            "x": destination["x"],
            "y": destination["y"],
            "direction": destination["direction"],
            "source": destination["source"],
        },
        "status_before": status_before,
        "observed": observed,
        "frames_waited": frames_waited,
        "nonblack_pixels": pixels,
        "passed": failure_reason is None,
        "failure_reason": failure_reason,
    }
    return result, entry, ready_frames


def append_optional_arg(command: list[str], flag: str, value: Any) -> None:
    if value is not None:
        command.extend([flag, str(value)])


def append_required_arg(command: list[str], flag: str, value: Any) -> None:
    command.extend([flag, str(value)])


def worker_command(
    args: argparse.Namespace,
    worker_index: int,
    worker_output: Path,
) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker-index",
        str(worker_index),
        "--worker-output",
        str(worker_output),
    ]
    append_required_arg(command, "--rom", args.rom)
    append_optional_arg(command, "--dsv", args.dsv)
    append_optional_arg(command, "--sav", args.sav)
    append_required_arg(command, "--destinations", args.destinations)
    append_required_arg(command, "--expect-count", args.expect_count)
    append_required_arg(command, "--boot-frames", args.boot_frames)
    append_required_arg(command, "--ready-a-taps", args.ready_a_taps)
    append_required_arg(command, "--tap-hold-frames", args.tap_hold_frames)
    append_required_arg(command, "--tap-gap-frames", args.tap_gap_frames)
    append_required_arg(command, "--load-frames", args.load_frames)
    append_required_arg(command, "--post-ready-wait-frames", args.post_ready_wait_frames)
    append_required_arg(command, "--ready-timeout-frames", args.ready_timeout_frames)
    append_required_arg(command, "--trigger-frames", args.trigger_frames)
    append_required_arg(command, "--release-frames", args.release_frames)
    append_required_arg(command, "--max-wait-frames", args.max_wait_frames)
    append_required_arg(command, "--sample-interval", args.sample_interval)
    append_required_arg(command, "--min-nonblack-pixels", args.min_nonblack_pixels)
    return command


def run_destination_worker_process(
    args: argparse.Namespace,
    index: int,
    destination: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, int] | None, int]:
    with tempfile.NamedTemporaryFile(suffix=".json") as worker_file:
        command = worker_command(args, index, Path(worker_file.name))
        try:
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=args.worker_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            result = verifier_error_result(
                index,
                destination,
                f"worker timed out after {args.worker_timeout_seconds}s",
            )
            if exc.stdout:
                result["worker_stdout"] = exc.stdout[-2000:]
            if exc.stderr:
                result["worker_stderr"] = exc.stderr[-2000:]
            return result, None, 0

        if completed.returncode != 0:
            result = verifier_error_result(
                index,
                destination,
                f"worker exited with status {completed.returncode}",
            )
            if completed.stdout:
                result["worker_stdout"] = completed.stdout[-2000:]
            if completed.stderr:
                result["worker_stderr"] = completed.stderr[-2000:]
            return result, None, 0

        try:
            payload = json.loads(Path(worker_file.name).read_text())
            return (
                payload["result"],
                payload.get("destination_entry"),
                int(payload.get("ready_frames", 0)),
            )
        except Exception as exc:
            result = verifier_error_result(
                index,
                destination,
                f"worker output parse failed: {type(exc).__name__}: {exc}",
            )
            if completed.stdout:
                result["worker_stdout"] = completed.stdout[-2000:]
            if completed.stderr:
                result["worker_stderr"] = completed.stderr[-2000:]
            return result, None, 0


def verifier_error_result(
    index: int,
    destination: dict[str, Any],
    failure_reason: str,
) -> dict[str, Any]:
    return {
        "index": index,
        "symbol": destination["symbol"],
        "map_id": destination["map_id"],
        "data_id": destination["data_id"],
        "destination": {
            "x": destination["x"],
            "y": destination["y"],
            "direction": destination["direction"],
            "source": destination["source"],
        },
        "status_before": empty_status(),
        "observed": empty_status(),
        "frames_waited": 0,
        "nonblack_pixels": 0,
        "passed": False,
        "failure_reason": failure_reason,
        "ready_frames": 0,
        "ready_wait_frames": 0,
    }


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
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("documentation/verification/all_encounter_teleport_verifier.json"),
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=Path("documentation/verification/all_encounter_teleport_verifier.jsonl"),
    )
    parser.add_argument("--expect-count", type=int, default=DEFAULT_EXPECT_COUNT)
    parser.add_argument("--boot-frames", type=int, default=420)
    parser.add_argument("--ready-a-taps", type=int, default=10)
    parser.add_argument("--tap-hold-frames", type=int, default=24)
    parser.add_argument("--tap-gap-frames", type=int, default=36)
    parser.add_argument("--load-frames", type=int, default=360)
    parser.add_argument("--post-ready-wait-frames", type=int, default=120)
    parser.add_argument("--ready-timeout-frames", type=int, default=240)
    parser.add_argument("--trigger-frames", type=int, default=30)
    parser.add_argument("--release-frames", type=int, default=30)
    parser.add_argument("--max-wait-frames", type=int, default=360)
    parser.add_argument("--sample-interval", type=int, default=12)
    parser.add_argument("--min-nonblack-pixels", type=int, default=1000)
    parser.add_argument("--limit", type=int, help="Debug-only map limit; any value below expected count fails summary.")
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-timeout-seconds", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

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

    destinations = load_destinations(repo_path(args.destinations))
    authoritative = authoritative_entries()
    authoritative_symbols = [symbol for symbol, _map_id, _data_id in authoritative]
    destination_symbols = [destination["symbol"] for destination in destinations]

    if args.worker_index is not None:
        if args.worker_output is None:
            raise ValueError("--worker-output is required with --worker-index")
        if args.worker_index < 0 or args.worker_index >= len(destinations):
            raise IndexError(f"worker index {args.worker_index} outside destination table")
        with headless.silence_native_output(True):
            result, entry, ready_frames = run_destination(
                args,
                rom,
                raw_save,
                args.worker_index,
                destinations[args.worker_index],
            )
        payload = {
            "result": result,
            "destination_entry": entry if entry is not None else empty_destination_entry(),
            "ready_frames": ready_frames,
        }
        args.worker_output.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        return 0

    expected_count = args.expect_count
    results: list[dict[str, Any]] = []
    entry: dict[str, int] | None = None
    ready_frames = 0
    started_at = time.monotonic()

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.jsonl.open("w", encoding="utf-8") as jsonl:
        for index, destination in enumerate(destinations):
            if args.limit is not None and index >= args.limit:
                break

            result, run_entry, run_ready_frames = run_destination_worker_process(
                args,
                index,
                destination,
            )
            if entry is None and run_entry is not None:
                entry = run_entry
            if ready_frames == 0 and run_ready_frames != 0:
                ready_frames = run_ready_frames
            results.append(result)
            jsonl.write(json.dumps(result, sort_keys=True) + "\n")
            jsonl.flush()

    if entry is None:
        entry = empty_destination_entry()

    passed = sum(1 for result in results if result["passed"])
    failures = [result for result in results if not result["passed"]]
    summary = {
        "rom": str(rom),
        "save": str(save_path),
        "save_kind": save_kind,
        "destinations": str(repo_path(args.destinations)),
        "expected_count": expected_count,
        "authoritative_count": len(authoritative),
        "generated_destination_count": len(destinations),
        "runtime_checked_count": len(results),
        "runtime_pass_count": passed,
        "runtime_fail_count": len(failures),
        "ready_frames": ready_frames,
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
        "authoritative_symbols_match_destinations": authoritative_symbols == destination_symbols,
        "destination_entry": entry,
        "passed": (
            len(authoritative) == expected_count
            and len(destinations) == expected_count
            and len(results) == expected_count
            and passed == expected_count
            and authoritative_symbols == destination_symbols
            and entry["magic"] == ENCOUNTER_DESTINATION_MAGIC
            and entry["version"] == ENCOUNTER_DESTINATION_VERSION
            and entry["count"] == expected_count
        ),
        "failures": failures,
    }
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
