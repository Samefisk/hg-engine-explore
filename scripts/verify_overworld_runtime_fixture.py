#!/usr/bin/env python3
"""Fail closed when an overworld runtime test would use a stale ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import struct
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from dataclasses import dataclass
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ISOLATED_FLAGS = ("-I", "-S", "-B", "-X", "pycache_prefix=/dev/null")
BUILD_MANIFEST = REPO / "build/pokemon_move_history_capture_build.json"
DEBUG_DESCRIPTOR = REPO / "build/overworld-system.debug.json"
ACTOR_OVERLAY = REPO / "build/output_overworld_actor_system_overlay.bin"


@dataclass(frozen=True)
class ProductOutput:
    key: str
    path: str
    overlay_id: int


PRODUCT_OUTPUTS = (
    ProductOutput(
        "actor",
        "build/output_overworld_actor_system_overlay.bin",
        158,
    ),
    ProductOutput(
        "wildSpawns",
        "build/output_overworld_wild_spawns_overlay.bin",
        149,
    ),
    ProductOutput(
        "wildRuntime",
        "build/output_overworld_wild_runtime_overlay.bin",
        156,
    ),
    ProductOutput(
        "mount",
        "build/output_overworld_mount_overlay.bin",
        157,
    ),
    ProductOutput(
        "walk",
        "build/output_pokemon_move_history_overlay.bin",
        153,
    ),
    ProductOutput(
        "hopRoleController",
        "build/output_pokemon_move_history_task6_overlay.bin",
        155,
    ),
    ProductOutput(
        "helper",
        "build/output_overworld_wild_helper_overlay.bin",
        151,
    ),
    ProductOutput(
        "behavior",
        "build/output_overworld_wild_behavior_data_overlay.bin",
        150,
    ),
    ProductOutput(
        "selector",
        "build/output_overworld_follower_selector_overlay.bin",
        152,
    ),
    ProductOutput(
        "field",
        "build/output_field.bin",
        131,
    ),
)

LINKED_OUTPUTS = (
    ("actorLinked", "actor_linked", "build/overworld_actor_system_overlay_linked.o"),
    ("mountLinked", "mount_linked", "build/overworld_mount_overlay_linked.o"),
    ("walkLinked", "history_linked", "build/pokemon_move_history_overlay_linked.o"),
    ("walkHelperObject", "walk_module_object", "build/pokemon_move_history_overlay/overworld_walk_module.o"),
    (
        "selectorLinked",
        "follower_selector_linked",
        "build/overworld_follower_selector_overlay_linked.o",
    ),
    (
        "wildSpawnsLinked",
        "overworld_wild_spawns_linked",
        "build/overworld_wild_spawns_overlay_linked.o",
    ),
    (
        "wildRuntimeLinked",
        "overworld_wild_runtime_linked",
        "build/overworld_wild_runtime_overlay_linked.o",
    ),
    (
        "hopRoleControllerLinked",
        "task6_linked",
        "build/pokemon_move_history_task6_overlay_linked.o",
    ),
    (
        "behaviorLinked",
        "wild_behavior_data_linked",
        "build/overworld_wild_behavior_data_overlay_linked.o",
    ),
)


def file_record(path: Path, *, root: Path = REPO) -> dict[str, object]:
    if not path.is_file():
        return {"path": str(path), "present": False, "size": None, "sha256": None}
    data = path.read_bytes()
    try:
        display_path = path.relative_to(root).as_posix()
    except ValueError:
        display_path = str(path)
    return {
        "path": display_path,
        "present": True,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def data_record(data: bytes, path: str) -> dict[str, object]:
    return {
        "path": path,
        "present": True,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def packaged_overlay(rom: bytes, overlay_id: int) -> bytes:
    if len(rom) < 0x58:
        raise ValueError("ROM header is truncated")
    fat_offset, fat_size = struct.unpack_from("<2I", rom, 0x48)
    y9_offset, y9_size = struct.unpack_from("<2I", rom, 0x50)
    row_offset = y9_offset + overlay_id * 0x20
    if (
        y9_offset > len(rom)
        or y9_size > len(rom) - y9_offset
        or overlay_id * 0x20 + 0x20 > y9_size
        or row_offset + 0x20 > len(rom)
    ):
        raise ValueError(f"overlay {overlay_id} Y9 row is missing")
    row = struct.unpack_from("<8I", rom, row_offset)
    if row[0] != overlay_id:
        raise ValueError(
            f"overlay {overlay_id} Y9 row identifies overlay {row[0]}"
        )
    file_size = row[2]
    file_id = row[6]
    fat_row_offset = fat_offset + file_id * 8
    if (
        fat_offset > len(rom)
        or fat_size > len(rom) - fat_offset
        or file_id * 8 + 8 > fat_size
        or fat_row_offset + 8 > len(rom)
    ):
        raise ValueError(f"overlay {overlay_id} FAT row is missing")
    file_start, file_end = struct.unpack_from("<2I", rom, fat_row_offset)
    if (
        file_start >= file_end
        or file_end > len(rom)
        or file_end - file_start != file_size
    ):
        raise ValueError(f"overlay {overlay_id} payload bounds differ from Y9")
    return rom[file_start:file_end]


def stock_main_queue_probe_check(rom_path: Path) -> dict[str, object]:
    """Bind coherent frame observation to the actual stock main-queue return.

    LDR r0,[r4,#0x18]; BL SysTaskQueue_RunTasks; LDR r0,[r4,#0x24].
    The first queue is the main queue; the following load selects print tasks.
    A video-frame boundary alone can fall between main-queue object updates.
    """
    result = {"name": "stock-main-queue-observation", "passed": False,
              "returnAddress": 0x02000DEE}
    try:
        with rom_path.open("rb") as image:
            header = image.read(0x40)
            if len(header) != 0x40:
                raise ValueError("ROM header is truncated")
            offset, _entry, base, size = struct.unpack_from("<4I", header, 0x20)
            start = 0x02000DE8 - base
            expected = bytes.fromhex("a0 69 1e f0 49 fd 60 6a")
            if base != 0x02000000 or not 0 <= start < start + len(expected) <= size \
                    or offset < 0x40 or offset + size > rom_path.stat().st_size:
                raise ValueError("stock main-queue probe is outside packaged ARM9")
            image.seek(offset + start)
            actual = image.read(len(expected))
            result["bytes"] = actual.hex()
            if actual != expected:
                raise ValueError("stock main-queue call/return bytes differ")
            result["passed"] = True
    except (OSError, ValueError) as error:
        result["error"] = str(error)
    return result


def product_output_check(
    rom_path: Path,
    *,
    repo: Path = REPO,
) -> dict[str, object]:
    result: dict[str, object] = {
        "name": "overworld-product-outputs",
        "passed": False,
        "outputs": {},
    }
    if not rom_path.is_file():
        result["error"] = "packaged ROM is missing"
        return result
    rom = rom_path.read_bytes()
    outputs: dict[str, dict[str, object]] = {}
    errors: list[str] = []
    for output in PRODUCT_OUTPUTS:
        built_path = repo / output.path
        built = file_record(built_path, root=repo)
        record: dict[str, object] = {
            "overlayId": output.overlay_id,
            "output": built,
            "packaged": {
                "path": f"{rom_path.name}#overlay/{output.overlay_id}",
                "present": False,
                "size": None,
                "sha256": None,
            },
            "matched": False,
        }
        if not built_path.is_file():
            errors.append(f"{output.key}: built output is missing")
        else:
            try:
                packaged = packaged_overlay(rom, output.overlay_id)
            except ValueError as error:
                errors.append(f"{output.key}: {error}")
            else:
                packaged_record = data_record(
                    packaged,
                    f"{rom_path.name}#overlay/{output.overlay_id}",
                )
                record["packaged"] = packaged_record
                record["matched"] = (
                    built["size"] == packaged_record["size"]
                    and built["sha256"] == packaged_record["sha256"]
                )
                if not record["matched"]:
                    errors.append(
                        f"{output.key}: packaged overlay differs from built output"
                    )
        outputs[output.key] = record
    result["outputs"] = outputs
    result["passed"] = not errors and len(outputs) == len(PRODUCT_OUTPUTS)
    if errors:
        result["error"] = "; ".join(errors)
    return result


def linked_output_check(*, repo: Path = REPO) -> dict[str, object]:
    result: dict[str, object] = {
        "name": "runtime-linked-symbol-inputs",
        "passed": False,
        "outputs": {},
    }
    try:
        manifest = json.loads((repo / BUILD_MANIFEST.relative_to(REPO)).read_text())
        sealed = manifest["outputs"]
    except (KeyError, json.JSONDecodeError, OSError, TypeError) as error:
        result["error"] = f"sealed build manifest is invalid: {error}"
        return result
    errors: list[str] = []
    records: dict[str, object] = {}
    for key, role, relative in LINKED_OUTPUTS:
        actual = file_record(repo / relative, root=repo)
        expected = sealed.get(role)
        matched = (
            isinstance(expected, dict)
            and expected.get("path") == relative
            and actual.get("present") is True
            and actual.get("size") == expected.get("size")
            and actual.get("sha256") == expected.get("sha256")
        )
        records[key] = {
            "output": actual,
            "sealed": expected,
            "matched": matched,
        }
        if not matched:
            errors.append(f"{key}: linked symbol input differs from sealed build")
    result["outputs"] = records
    result["passed"] = not errors and len(records) == len(LINKED_OUTPUTS)
    if errors:
        result["error"] = "; ".join(errors)
    return result


def _run_bounded(command, *, repo=REPO, deadline=None, cancel_event=None):
    """Stop only this check's private process group on cancellation/deadline."""
    if deadline is None and cancel_event is None:
        try:
            return subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired as error:
            return SimpleNamespace(returncode=124, stdout=error.stdout or "", stderr="fixture-check-timeout")
    reason = "fixture-canceled" if cancel_event is not None and cancel_event.is_set() else \
             "fixture-wall-budget" if deadline is not None and time.monotonic() >= deadline else None
    if reason: return SimpleNamespace(returncode=124, stdout="", stderr=reason)
    process = subprocess.Popen(command, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    while True:
        reason = "fixture-canceled" if cancel_event is not None and cancel_event.is_set() else \
                 "fixture-wall-budget" if deadline is not None and time.monotonic() >= deadline else None
        if reason:
            try: os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                stdout, stderr = process.communicate(timeout=2)
            return SimpleNamespace(returncode=124, stdout=stdout, stderr=stderr + "\n" + reason)
        try:
            stdout, stderr = process.communicate(timeout=0.1)
            return SimpleNamespace(returncode=process.returncode, stdout=stdout, stderr=stderr)
        except subprocess.TimeoutExpired:
            continue


def run_check(name: str, command: list[str], *, deadline=None, cancel_event=None) -> dict[str, object]:
    completed = _run_bounded(command, deadline=deadline, cancel_event=cancel_event)
    return {
        "name": name,
        "passed": completed.returncode == 0,
        "returnCode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def runtime_runner_startup_check(*, repo: Path = REPO, deadline=None, cancel_event=None) -> dict[str, object]:
    """Authenticate the shared engine backend; never import a scenario runner."""
    python = repo / ".venv/bin/python3"
    command = [
        str(python),
        *ISOLATED_FLAGS,
        "-c",
        (
            "import importlib.util,sys; from pathlib import Path; "
            "repo=Path.cwd(); "
            "spec=importlib.util.spec_from_file_location('overworld_devtools_native',repo/'tools/overworld/devtools_native.py'); "
            "native=importlib.util.module_from_spec(spec); spec.loader.exec_module(native); "
            "sys.path.insert(0,str(repo)); "
            "from tools.overworld import devtools_engine; devtools_engine.initialize(native)"
        ),
    ]
    completed = _run_bounded(command, repo=repo, deadline=deadline, cancel_event=cancel_event)
    return {
        "name": "shared-devtools-isolated-startup",
        "passed": completed.returncode == 0,
        "returnCode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def descriptor_check(rom_path: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "name": "debug-descriptor-overlay",
        "passed": False,
        "descriptor": file_record(DEBUG_DESCRIPTOR),
        "overlay": file_record(ACTOR_OVERLAY),
    }
    if not DEBUG_DESCRIPTOR.is_file() or not ACTOR_OVERLAY.is_file():
        result["error"] = "debug descriptor or actor overlay is missing"
        return result
    try:
        descriptor = json.loads(DEBUG_DESCRIPTOR.read_text())
        expected = descriptor["overlay"]
        rom = rom_path.read_bytes()
        packaged = packaged_overlay(rom, 158)
        y9_offset, y9_size = struct.unpack_from("<2I", rom, 0x50)
        overlay_table = rom[y9_offset:y9_offset + y9_size]
        with tempfile.TemporaryDirectory(prefix="actor-descriptor-") as directory:
            temporary = Path(directory)
            packaged_path = temporary / "overlay_0158.bin"
            table_path = temporary / "overarm9.bin"
            generated_path = temporary / "overworld-system.debug.json"
            packaged_path.write_bytes(packaged)
            table_path.write_bytes(overlay_table)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO / "scripts/generate_overworld_actor_system_debug.py"),
                    "--linked", str(REPO / "build/overworld_actor_system_overlay_linked.o"),
                    "--binary", str(ACTOR_OVERLAY),
                    "--packaged", str(packaged_path),
                    "--overlay-table", str(table_path),
                    "--header", str(REPO / "include/overworld_actor_system.h"),
                    "--internal-header", str(REPO / "include/overworld_actor_system_internal.h"),
                    "--resolver-header", str(REPO / "include/overworld_behavior_resolver.h"),
                    "--motion-header", str(REPO / "include/overworld_motion_model.h"),
                    "--output", str(generated_path),
                ],
                cwd=REPO,
                capture_output=True,
                text=True,
            )
            generated = (
                json.loads(generated_path.read_text())
                if completed.returncode == 0 and generated_path.is_file()
                else None
            )
    except (KeyError, json.JSONDecodeError, OSError, TypeError, ValueError) as error:
        result["error"] = f"debug descriptor is invalid: {error}"
        return result
    actual = result["overlay"]
    result["expected"] = {
        "size": expected.get("fileSize"),
        "sha256": expected.get("sha256"),
    }
    result["passed"] = (
        actual["present"]
        and actual["size"] == expected.get("fileSize")
        and actual["sha256"] == expected.get("sha256")
        and generated == descriptor
    )
    if not result["passed"]:
        result["error"] = (
            "debug descriptor differs from current linked/header product truth"
            if generated is not None
            else "debug descriptor regeneration failed: "
                + completed.stderr.strip()
        )
    return result


def verify(rom: Path, *, deadline=None, cancel_event=None) -> dict[str, object]:
    rom = rom if rom.is_absolute() else REPO / rom
    python = REPO / ".venv/bin/python3"
    deadline = deadline if deadline is not None else time.monotonic() + 120
    def bounded(name, command):
        return run_check(name, command, deadline=deadline, cancel_event=cancel_event)
    checks = [
        bounded("make-target-current", ["make", "-q", "test.nds"]),
        bounded(
            "sealed-build-manifest",
            [
                str(python),
                *ISOLATED_FLAGS,
                str(REPO / "scripts/pokemon_move_history_build_manifest.py"),
                "--verify",
                str(BUILD_MANIFEST),
                "--rom",
                str(rom),
            ],
        ),
        bounded(
            "packaged-actor-system",
            [
                sys.executable,
                str(REPO / "scripts/verify_pokemon_move_history.py"),
                "--rom",
                str(rom),
            ],
        ),
        bounded(
            "packaged-mount-system",
            [
                sys.executable,
                str(REPO / "scripts/verify_overworld_mount.py"),
                "--rom",
                str(rom),
            ],
        ),
        product_output_check(rom),
        linked_output_check(),
        bounded("walk-helper-input-alignment", [sys.executable,
            str(REPO / "scripts/verify_overworld_walk_helper_alignment.py")]),
        descriptor_check(rom),
        stock_main_queue_probe_check(rom),
        runtime_runner_startup_check(deadline=deadline, cancel_event=cancel_event),
    ]
    return {
        "schemaVersion": 1,
        "passed": all(check["passed"] for check in checks),
        "rom": file_record(rom),
        "buildManifest": file_record(BUILD_MANIFEST),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=Path("test.nds"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify(args.rom)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        for check in result["checks"]:
            print(("PASS" if check["passed"] else "FAIL") + " " + check["name"])
        print("PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
