#!/usr/bin/env python3
"""Verify L+R warp-backed encounter map teleport destinations."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
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
DEBUG_DESTINATION_INDEX_ADDR = DEBUG_STATUS_ADDR + 22
DEBUG_DESTINATION_INDEX_FORCED = 0xFFFE
DEBUG_DESTINATION_INDEX_NONE = 0xFFFF
ENCOUNTER_DESTINATION_ENTRY_ADDR = 0x023C8034
ENCOUNTER_DESTINATION_MAGIC = 0x4D544544
ENCOUNTER_DESTINATION_VERSION = 1
C_DESTINATION_TABLE_PATH = Path("src/field/map_teleport_encounter_destinations.c")
DEFAULT_EXPECT_COUNT = 150
FIELD_OVERLAY_MAX_SIZE = 0x5000
FIELD_OVERLAY_SIZE_PATHS = (
    Path("base/overlay/overlay_0131.bin"),
    Path("build/output_field.bin"),
)
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


def field_overlay_size_report() -> dict[str, Any]:
    checked: list[dict[str, Any]] = []
    existing_sizes: list[int] = []
    for path in FIELD_OVERLAY_SIZE_PATHS:
        absolute = repo_path(path)
        exists = absolute.is_file()
        size = absolute.stat().st_size if exists else None
        checked.append(
            {
                "path": str(absolute),
                "exists": exists,
                "size": size,
                "max_size": FIELD_OVERLAY_MAX_SIZE,
                "ok": exists and size is not None and size < FIELD_OVERLAY_MAX_SIZE,
            }
        )
        if size is not None:
            existing_sizes.append(size)

    ok = bool(existing_sizes) and all(size < FIELD_OVERLAY_MAX_SIZE for size in existing_sizes)
    return {
        "max_size": FIELD_OVERLAY_MAX_SIZE,
        "ok": ok,
        "checked": checked,
    }


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
        "destination_index": read_u16(emu, DEBUG_DESTINATION_INDEX_ADDR),
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


def force_debug_destination(emu: DeSmuME) -> None:
    write_u16(emu, DEBUG_DESTINATION_INDEX_ADDR, DEBUG_DESTINATION_INDEX_FORCED)


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
        "destination_index": DEBUG_DESTINATION_INDEX_NONE,
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


def destination_uses_warp_id(destination: dict[str, Any]) -> bool:
    return int(destination["y"]) == generator.WARP_ID_Y_SENTINEL


def status_matches_destination(destination: dict[str, Any], status: dict[str, int]) -> bool:
    if destination_uses_warp_id(destination):
        return status["map_id"] == int(destination["map_id"])
    return (
        status["map_id"] == int(destination["map_id"])
        and status["x"] == int(destination["x"])
        and status["y"] == int(destination["y"])
    )


def result_evidence(
    destination: dict[str, Any],
    status_before: dict[str, int],
    status: dict[str, int],
) -> dict[str, Any]:
    request_seen = request_count_changed(
        status_before["request_count"],
        status["request_count"],
    )
    request_result_ok = request_seen and status["request_result"] == MAP_TELEPORT_RESULT_OK
    started_at_destination = status_matches_destination(destination, status_before)
    ended_at_destination = status_matches_destination(destination, status)
    location_changed_to_destination = ended_at_destination and not started_at_destination
    if request_result_ok:
        pass_evidence_kind = "request_ok"
    elif location_changed_to_destination:
        pass_evidence_kind = "location_changed_to_destination"
    else:
        pass_evidence_kind = "none"
    return {
        "request_seen": request_seen,
        "request_result_ok": request_result_ok,
        "started_at_destination": started_at_destination,
        "ended_at_destination": ended_at_destination,
        "location_changed_to_destination": location_changed_to_destination,
        "pass_evidence_kind": pass_evidence_kind,
    }


def nonblack_pixel_count(emu: DeSmuME) -> int:
    image = emu.screenshot().convert("RGB")
    pixels = image.getdata()
    return sum(1 for red, green, blue in pixels if red + green + blue > 24)


def load_destination_payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    destinations = data.get("destinations", [])
    if not isinstance(destinations, list):
        raise ValueError(f"{path} does not contain a destinations list")
    data["destinations"] = destinations
    return data


def authoritative_entries() -> list[tuple[str, int, int]]:
    maps = generator.read_map_constants(REPO_ROOT / "include/constants/maps.h")
    return generator.read_authoritative_maps(
        REPO_ROOT / "data/OverworldWildEncounterLookupData.c",
        REPO_ROOT / "include/overworld_wild_behavior_data.h",
        maps,
    )


def warp_backing_failures(destinations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    arm9_path = REPO_ROOT / "base/arm9.bin"
    event_narc_path = REPO_ROOT / "base/root/a/0/3/2"
    if not arm9_path.is_file() or not event_narc_path.is_file():
        return [
            {
                "reason": "missing extracted ROM inputs",
                "arm9": str(arm9_path),
                "event_narc": str(event_narc_path),
            }
        ]

    arm9 = arm9_path.read_bytes()
    event_narc = generator.ndspy.narc.NARC.fromFile(event_narc_path)
    maps = generator.read_map_constants(REPO_ROOT / "include/constants/maps.h")
    target_map_ids = {int(destination["map_id"]) for destination in destinations}
    incoming_warps = generator.build_incoming_warps(
        maps=maps,
        arm9=arm9,
        event_narc=event_narc,
        target_map_ids=target_map_ids,
    )
    failures: list[dict[str, Any]] = []
    for destination in destinations:
        map_id = int(destination["map_id"])
        header = generator.read_header(arm9, map_id)
        warp_id = int(destination["x"])
        if int(destination.get("event_file_id", header.event_file_id)) != header.event_file_id:
            failures.append(
                {
                    "symbol": destination.get("symbol"),
                    "map_id": map_id,
                    "reason": "event file id mismatch",
                    "json_event_file_id": destination.get("event_file_id"),
                    "actual_event_file_id": header.event_file_id,
                }
            )
        if not destination_uses_warp_id(destination):
            failures.append(
                {
                    "symbol": destination.get("symbol"),
                    "map_id": map_id,
                    "reason": "destination is not encoded as a warp id",
                    "x": destination.get("x"),
                    "y": destination.get("y"),
                }
            )
            continue
        if int(destination.get("warp_index", -1)) != warp_id:
            failures.append(
                {
                    "symbol": destination.get("symbol"),
                    "map_id": map_id,
                    "reason": "warp index metadata does not match encoded warp id",
                    "warp_index": destination.get("warp_index"),
                    "encoded_warp_id": warp_id,
                }
            )
        matches = [
            incoming
            for incoming in incoming_warps.get(map_id, [])
            if incoming.warp.dest_anchor == warp_id
        ]
        if not matches:
            failures.append(
                {
                    "symbol": destination.get("symbol"),
                    "map_id": map_id,
                    "warp_id": warp_id,
                    "reason": "destination warp id is not backed by an incoming warp",
                }
            )
            continue
        if not any(
            incoming.source_map_id == int(destination.get("source_map_id", -1))
            and incoming.source_event_file_id == int(destination.get("source_event_file_id", -1))
            and incoming.warp.index == int(destination.get("source_warp_index", -1))
            and incoming.warp.x == int(destination.get("source_warp_x", -1))
            and incoming.warp.y == int(destination.get("source_warp_y", -1))
            and incoming.warp.dest_header == map_id
            and incoming.warp.dest_anchor == warp_id
            for incoming in matches
        ):
            failures.append(
                {
                    "symbol": destination.get("symbol"),
                    "map_id": map_id,
                    "warp_id": warp_id,
                    "reason": "incoming warp metadata does not match source event data",
                }
            )
    return failures


def skipped_no_warp_failures(
    authoritative: list[tuple[str, int, int]],
    skipped_symbols: list[str],
) -> list[dict[str, Any]]:
    symbol_to_map = {symbol: map_id for symbol, map_id, _data_id in authoritative}
    arm9_path = REPO_ROOT / "base/arm9.bin"
    event_narc_path = REPO_ROOT / "base/root/a/0/3/2"
    if not arm9_path.is_file() or not event_narc_path.is_file():
        return []

    arm9 = arm9_path.read_bytes()
    event_narc = generator.ndspy.narc.NARC.fromFile(event_narc_path)
    maps = generator.read_map_constants(REPO_ROOT / "include/constants/maps.h")
    incoming_warps = generator.build_incoming_warps(
        maps=maps,
        arm9=arm9,
        event_narc=event_narc,
        target_map_ids=set(symbol_to_map.values()),
    )
    failures: list[dict[str, Any]] = []
    for symbol in skipped_symbols:
        if symbol not in symbol_to_map:
            failures.append({"symbol": symbol, "reason": "skipped symbol is not authoritative"})
            continue
        map_id = symbol_to_map[symbol]
        warps = incoming_warps.get(map_id, [])
        if warps:
            failures.append(
                {
                    "symbol": symbol,
                    "map_id": map_id,
                    "reason": "skipped map has incoming warp anchors",
                    "warp_count": len(warps),
                }
            )
    return failures


def decode_c_packed_destination(packed: int) -> dict[str, int]:
    return {
        "map_id": (packed >> generator.PACKED_MAP_SHIFT) & (generator.PACKED_MAP_LIMIT - 1),
        "x": (packed >> generator.PACKED_X_SHIFT) & (generator.PACKED_X_LIMIT - 1),
        "y": (packed >> generator.PACKED_Y_SHIFT) & (generator.PACKED_Y_LIMIT - 1),
        "direction": 1,
    }


def c_table_failures(destinations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    path = repo_path(C_DESTINATION_TABLE_PATH)
    if not path.is_file():
        return [{"reason": "generated C table is missing", "path": str(path)}]

    source = path.read_text()
    failures: list[dict[str, Any]] = []
    count_match = re.search(
        r"#define\s+MAP_TELEPORT_ENCOUNTER_DESTINATION_COUNT\s+(\d+)\b",
        source,
    )
    if count_match is None:
        failures.append({"reason": "generated C table count define is missing"})
        expected_count = None
    else:
        expected_count = int(count_match.group(1))
        if expected_count != len(destinations):
            failures.append(
                {
                    "reason": "generated C table count mismatch",
                    "c_count": expected_count,
                    "json_count": len(destinations),
                }
            )

    body_match = re.search(
        r"sMapTeleportEncounterDestinations\[[^\]]+\]\s*=\s*\{(?P<body>.*?)\};",
        source,
        re.S,
    )
    if body_match is None:
        failures.append({"reason": "generated C table initializer is missing"})
        return failures

    c_rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(body_match.group("body").splitlines(), start=1):
        match = re.search(
            r"0x([0-9A-Fa-f]+)u,\s*//\s*(MAP_\w+)\s+warp-id\s+(-?\d+)"
            r"\s+via map\s+(-?\d+)\s+warp\s+(-?\d+)\s+at\s+(-?\d+),(-?\d+)",
            line,
        )
        if match is None:
            if line.strip():
                failures.append(
                    {
                        "reason": "unparsed generated C table row",
                        "line": line_number,
                        "text": line.strip(),
                    }
                )
            continue
        packed = int(match.group(1), 16)
        decoded = decode_c_packed_destination(packed)
        c_rows.append(
            {
                **decoded,
                "symbol_comment": match.group(2),
                "warp_index_comment": int(match.group(3)),
                "source_map_id_comment": int(match.group(4)),
                "source_warp_index_comment": int(match.group(5)),
                "source_warp_x_comment": int(match.group(6)),
                "source_warp_y_comment": int(match.group(7)),
            }
        )

    if expected_count is not None and len(c_rows) != expected_count:
        failures.append(
            {
                "reason": "generated C table row count mismatch",
                "c_rows": len(c_rows),
                "c_count": expected_count,
            }
        )
    if len(c_rows) != len(destinations):
        failures.append(
            {
                "reason": "generated C table row count differs from JSON",
                "c_rows": len(c_rows),
                "json_count": len(destinations),
            }
        )

    for index, (c_row, destination) in enumerate(zip(c_rows, destinations)):
        expected = {
            "map_id": int(destination["map_id"]),
            "x": int(destination["x"]),
            "y": int(destination["y"]),
            "direction": int(destination["direction"]),
        }
        actual = {
            "map_id": c_row["map_id"],
            "x": c_row["x"],
            "y": c_row["y"],
            "direction": c_row["direction"],
        }
        if actual != expected:
            failures.append(
                {
                    "reason": "generated C packed destination differs from JSON",
                    "index": index,
                    "symbol": destination.get("symbol"),
                    "actual": actual,
                    "expected": expected,
                }
            )
        if c_row["symbol_comment"] != destination.get("symbol"):
            failures.append(
                {
                    "reason": "generated C symbol comment differs from JSON",
                    "index": index,
                    "c_symbol": c_row["symbol_comment"],
                    "json_symbol": destination.get("symbol"),
                }
            )
        if (
            c_row["warp_index_comment"] != int(destination.get("warp_index", -1))
            or c_row["source_map_id_comment"] != int(destination.get("source_map_id", -1))
            or c_row["source_warp_index_comment"] != int(destination.get("source_warp_index", -1))
            or c_row["source_warp_x_comment"] != int(destination.get("source_warp_x", -1))
            or c_row["source_warp_y_comment"] != int(destination.get("source_warp_y", -1))
        ):
            failures.append(
                {
                    "reason": "generated C row comment metadata differs from JSON",
                    "index": index,
                    "symbol": destination.get("symbol"),
                }
            )

    return failures


def result_failure_reason(
    destination: dict[str, Any],
    status_before: dict[str, int],
    status: dict[str, int],
    nonblack_pixels: int,
    min_nonblack_pixels: int,
    evidence: dict[str, Any],
) -> str | None:
    ready_failure = debug_status_failure_reason(status_before)
    if ready_failure is not None:
        return f"initial field state not ready: {ready_failure}"
    status_failure = debug_status_failure_reason(status)
    if status_failure is not None:
        return status_failure
    if evidence["request_seen"] and status["request_result"] != MAP_TELEPORT_RESULT_OK:
        return (
            "teleport request rejected: "
            f"{request_result_name(status['request_result'])} ({status['request_result']})"
        )
    if status["map_id"] != int(destination["map_id"]):
        return f"map mismatch: got {status['map_id']}"
    if (
        not destination_uses_warp_id(destination)
        and (status["x"] != int(destination["x"]) or status["y"] != int(destination["y"]))
    ):
        return f"position mismatch: got {status['x']},{status['y']}"
    if nonblack_pixels < min_nonblack_pixels:
        return f"screenshot looked black/unloaded: {nonblack_pixels} nonblack pixels"
    if evidence["pass_evidence_kind"] == "none":
        if evidence["started_at_destination"]:
            return "teleport request was not observed and initial location already matched destination"
        return "teleport request was not observed and location did not move to destination"
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
        if request_seen and observed["ready"] != 0 and status_matches_destination(
            destination,
            observed,
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
    ready_attempts = 0

    try:
        if args.ready_boot_attempts <= 0:
            raise ValueError("ready boot attempts must be greater than zero")
        for ready_attempts in range(1, args.ready_boot_attempts + 1):
            emu, ready_frames, entry, status_before, ready_failure = (
                open_ready_emulator(args, rom, raw_save)
            )
            observed = status_before
            if ready_failure is None:
                break
            failure_reason = f"initial field state not ready: {ready_failure}"
            emu.destroy()
            emu = None

        if emu is not None and failure_reason is not None:
            failure_reason = None
        if emu is not None:
            write_destination(emu, destination)
            force_debug_destination(emu)
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
        evidence = result_evidence(destination, status_before, observed)
        if failure_reason is None:
            failure_reason = result_failure_reason(
                destination,
                status_before,
                observed,
                pixels,
                args.min_nonblack_pixels,
                evidence,
            )
    except Exception as exc:
        evidence = result_evidence(destination, status_before, observed)
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
            evidence = result_evidence(destination, status_before, observed)
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
        "ready_attempts": ready_attempts,
        **evidence,
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
    append_required_arg(command, "--ready-boot-attempts", args.ready_boot_attempts)
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
    status_before = empty_status()
    observed = empty_status()
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
        "status_before": status_before,
        "observed": observed,
        "frames_waited": 0,
        "nonblack_pixels": 0,
        "passed": False,
        "failure_reason": failure_reason,
        "ready_frames": 0,
        "ready_wait_frames": 0,
        **result_evidence(destination, status_before, observed),
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
    parser.add_argument("--expect-count", type=int)
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

    destination_payload = load_destination_payload(repo_path(args.destinations))
    destinations = destination_payload["destinations"]
    expected_count = (
        args.expect_count
        if args.expect_count is not None
        else int(destination_payload.get("expected_count", DEFAULT_EXPECT_COUNT))
    )
    args.expect_count = expected_count
    authoritative = authoritative_entries()
    authoritative_symbols = [symbol for symbol, _map_id, _data_id in authoritative]
    destination_symbols = [destination["symbol"] for destination in destinations]
    skipped_no_warp_symbols = [
        str(symbol) for symbol in destination_payload.get("skipped_no_warp_symbols", [])
    ]
    expected_destination_symbols = [
        symbol for symbol in authoritative_symbols if symbol not in set(skipped_no_warp_symbols)
    ]
    destination_symbols_match_expected = destination_symbols == expected_destination_symbols

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
    passed_with_request_ok = sum(
        1 for result in results
        if result["passed"] and result.get("pass_evidence_kind") == "request_ok"
    )
    passed_with_location_change = sum(
        1 for result in results
        if result["passed"]
        and result.get("pass_evidence_kind") == "location_changed_to_destination"
    )
    passed_without_evidence = sum(
        1 for result in results
        if result["passed"] and result.get("pass_evidence_kind") == "none"
    )
    stale_match_rejected = sum(
        1 for result in failures
        if result.get("started_at_destination")
        and not result.get("request_result_ok")
        and result.get("ended_at_destination")
    )
    all_passed_rows_have_evidence = passed_without_evidence == 0
    field_overlay_size = field_overlay_size_report()
    warp_failures = warp_backing_failures(destinations)
    no_warp_skip_failures = skipped_no_warp_failures(authoritative, skipped_no_warp_symbols)
    generated_c_table_failures = c_table_failures(destinations)
    summary = {
        "rom": str(rom),
        "save": str(save_path),
        "save_kind": save_kind,
        "destinations": str(repo_path(args.destinations)),
        "expected_count": expected_count,
        "authoritative_count": len(authoritative),
        "generated_destination_count": len(destinations),
        "skipped_no_warp_count": len(skipped_no_warp_symbols),
        "skipped_no_warp_symbols": skipped_no_warp_symbols,
        "runtime_checked_count": len(results),
        "runtime_pass_count": passed,
        "runtime_fail_count": len(failures),
        "passed_with_request_ok_count": passed_with_request_ok,
        "passed_with_location_change_count": passed_with_location_change,
        "passed_without_evidence_count": passed_without_evidence,
        "stale_match_rejected_count": stale_match_rejected,
        "all_passed_rows_have_evidence": all_passed_rows_have_evidence,
        "field_overlay_size": field_overlay_size,
        "ready_frames": ready_frames,
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
        "destination_symbols_match_expected": destination_symbols_match_expected,
        "all_destinations_warp_backed": not warp_failures,
        "warp_backing_failures": warp_failures,
        "skipped_no_warp_failures": no_warp_skip_failures,
        "generated_c_table_matches_json": not generated_c_table_failures,
        "generated_c_table_failures": generated_c_table_failures,
        "destination_entry": entry,
        "passed": (
            len(destinations) == expected_count
            and len(results) == expected_count
            and passed == expected_count
            and all_passed_rows_have_evidence
            and field_overlay_size["ok"]
            and destination_symbols_match_expected
            and not warp_failures
            and not no_warp_skip_failures
            and not generated_c_table_failures
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
