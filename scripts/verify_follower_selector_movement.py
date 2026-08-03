#!/usr/bin/env python3
"""A/B test Y-held walking by comparing final player map locations.

The verifier creates a fresh savestate from the exact ROM under test, then
runs direction-only and direction-plus-Y branches in separate emulator
processes. Both branches begin from the same state and hold the direction for
the same number of frames. The treatment adds Y only after walking has begun.
"""

import argparse
import hashlib
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
HARNESS_PATH = REPO_ROOT / "scripts/headless-overworld-test.py"
HARNESS_SPEC = importlib.util.spec_from_file_location(
    "headless_overworld_test",
    HARNESS_PATH,
)
HARNESS = importlib.util.module_from_spec(HARNESS_SPEC)
assert HARNESS_SPEC.loader is not None
HARNESS_SPEC.loader.exec_module(HARNESS)

from desmume.controls import Keys, keymask
from desmume.emulator import DeSmuME


VERIFY_VERSION = 4
FOLLOWER_RELEASE_SOURCE = (
    REPO_ROOT
    / "src/overworld_follower_release_overlay2/overworld_follower_release_overlay2.c"
)
SELECTOR_ENTRY = 0x023C0400
SELECTOR_MAGIC = 0x3153464F
SELECTOR_FLAGS = 0x023C8148
SELECTOR_ACTIVE_FLAG = 0x10
SELECTOR_DIRECT_LOADED_FLAG = 0x40
DIRECTION_KEYS = {
    "LEFT": Keys.KEY_LEFT,
    "RIGHT": Keys.KEY_RIGHT,
    "UP": Keys.KEY_UP,
    "DOWN": Keys.KEY_DOWN,
}


def linked_symbol_address(name: str) -> int:
    linked_object = REPO_ROOT / "build/linked.o"
    if not linked_object.is_file():
        raise RuntimeError(f"linked ROM symbols are unavailable: {linked_object}")
    output = subprocess.check_output(
        ["arm-none-eabi-nm", "-n", str(linked_object)],
        text=True,
    )
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[-1] == name:
            return int(parts[0], 16)
    raise RuntimeError(f"linked ROM symbol not found: {name}")


G_FIELD_SYS_PTR = linked_symbol_address("gFieldSysPtr")


def extract_c_function(source: str, name: str) -> str:
    signature = source.find(name)
    if signature < 0:
        raise RuntimeError(f"source contract function not found: {name}")
    body_start = source.find("{", signature)
    if body_start < 0:
        raise RuntimeError(f"source contract body not found: {name}")
    depth = 0
    for index in range(body_start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[signature : index + 1]
    raise RuntimeError(f"source contract body is incomplete: {name}")


def verify_aggro_intent_bridge_source() -> dict[str, Any]:
    body = extract_c_function(
        FOLLOWER_RELEASE_SOURCE.read_text(),
        "OverworldWildSpawns_EnterAggroState",
    )
    code = re.sub(r"/\*.*?\*/|//[^\n]*", "", body, flags=re.DOTALL)
    required = {
        "additive aggro/pending publication": (
            r"state->spawns\[slot\]\.active\s*\|=\s*"
            r"TRUE\s*\|\s*OW_WILD_SPAWN_AGGRO_FLAG\s*\|\s*"
            r"OW_WILD_SPAWN_AGGRO_PENDING_FLAG\s*;"
        ),
        "nullable release presentation": (
            r"if\s*\(spawnedFollower\s*!=\s*NULL\)\s*\{\s*"
            r"spawnedFollower->flags\s*\|=\s*BIT_VANISH\s*;\s*\}"
        ),
    }
    missing = [
        label for label, pattern in required.items()
        if re.search(pattern, code) is None
    ]
    forbidden = {
        "legacy behavior-controller state": "movementSpotStates",
        "pre-commit active-step reset": "movementActiveSteps",
        "pending-intent clear": "&=",
    }
    present = [label for label, text in forbidden.items() if text in code]
    if "state->spawns[slot].active =" in code:
        present.append("destructive spawn-state assignment")
    if missing or present:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if present:
            details.append("forbidden " + ", ".join(present))
        raise RuntimeError("aggro intent bridge source contract failed: " + "; ".join(details))
    return {
        "passed": True,
        "source": str(FOLLOWER_RELEASE_SOURCE),
        "repeated_calls_preserve_pending": True,
        "null_follower_supported": True,
        "behavior_authority_deferred": True,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def u8(emu: DeSmuME, address: int) -> int:
    return emu.memory.unsigned[address:address:1]


def u32(emu: DeSmuME, address: int) -> int:
    return emu.memory.unsigned[address:address:4]


def s32(emu: DeSmuME, address: int) -> int:
    return emu.memory.signed[address:address:4]


def player_map_location(emu: DeSmuME) -> tuple[int, int, int]:
    field_system = u32(emu, G_FIELD_SYS_PTR)
    avatar = u32(emu, field_system + 0x40) if field_system else 0
    map_object = u32(emu, avatar + 0x30) if avatar else 0
    if not field_system or not avatar or not map_object:
        raise RuntimeError("player map object is unavailable; save is not in the overworld")
    # LocalMapObject mapId/currentX/currentZ: the player's actual map location.
    return (
        s32(emu, map_object + 0x0C),
        s32(emu, map_object + 0x64),
        s32(emu, map_object + 0x6C),
    )


def open_booted_emulator(
    rom: Path,
    dsv: Path,
    args: argparse.Namespace,
) -> tuple[DeSmuME, tempfile.NamedTemporaryFile]:
    raw_save = HARNESS.extract_raw_save(dsv)
    emu = DeSmuME()
    emu.volume_set(0)
    emu.open(str(rom))
    raw_file = tempfile.NamedTemporaryFile(suffix=".sav")
    raw_file.write(raw_save)
    raw_file.flush()
    emu.backup.import_file(raw_file.name, force_size=0)
    HARNESS.boot_to_ready(args, emu)
    return emu, raw_file


def create_fresh_state(
    rom: Path,
    dsv: Path,
    state: Path,
    direction: str,
    walk_in_frames: int,
    args: argparse.Namespace,
) -> dict[str, Any]:
    emu, raw_file = open_booted_emulator(rom, dsv, args)
    direction_mask = keymask(DIRECTION_KEYS[direction])
    try:
        # The repeated A boot cadence can leave the field menu open depending
        # on frame timing. B closes it; in an already-idle overworld this is a
        # harmless no-op and keeps the movement start deterministic.
        HARNESS.tap_key(emu, "B", 2, 30)
        HARNESS.cycle(emu, args.preload_frames)
        if u32(emu, SELECTOR_ENTRY) != SELECTOR_MAGIC:
            raise RuntimeError("custom selector overlay entry is not loaded")
        if (u8(emu, SELECTOR_FLAGS) & SELECTOR_DIRECT_LOADED_FLAG) == 0:
            raise RuntimeError("custom selector overlay is not direct-loaded")
        emu.input.keypad_add_key(direction_mask)
        HARNESS.cycle(emu, walk_in_frames)
        start_position = player_map_location(emu)
        state.parent.mkdir(parents=True, exist_ok=True)
        emu.savestate.save_file(str(state))
        return {
            "start_position": list(start_position),
            "selector_flags": u8(emu, SELECTOR_FLAGS),
            "selector_magic": f"0x{u32(emu, SELECTOR_ENTRY):08X}",
        }
    finally:
        emu.input.keypad_rm_key(direction_mask)
        emu.destroy()
        raw_file.close()


def run_branch(args: argparse.Namespace) -> int:
    rom = Path(args.rom).resolve()
    state = Path(args.state).resolve()
    output = Path(args.branch_output).resolve()
    output_dir = Path(args.output_dir).resolve()
    actual_rom_hash = sha256_file(rom)
    if actual_rom_hash != args.expected_rom_sha256:
        raise RuntimeError(
            "ROM changed after the fresh state was created: "
            f"expected {args.expected_rom_sha256}, got {actual_rom_hash}"
        )
    if args.branch not in ("control", "treatment"):
        raise ValueError("internal branch must be control or treatment")

    direction_mask = keymask(DIRECTION_KEYS[args.direction])
    y_mask = keymask(Keys.KEY_Y)
    emu = DeSmuME()
    emu.volume_set(0)
    emu.open(str(rom))
    try:
        emu.savestate.load_file(str(state))
        emu.input.keypad_rm_key(direction_mask | y_mask)
        emu.input.keypad_add_key(direction_mask)
        rows = []
        screenshot_frames = {0, args.y_frame + 6, args.frames - 1}
        output_dir.mkdir(parents=True, exist_ok=True)
        for frame in range(args.frames):
            if args.branch == "treatment" and frame == args.y_frame:
                emu.input.keypad_add_key(y_mask)
            position = player_map_location(emu)
            rows.append(
                {
                    "frame": frame,
                    "map_location": list(position),
                    "selector_flags": u8(emu, SELECTOR_FLAGS),
                }
            )
            if frame in screenshot_frames:
                emu.screenshot().save(
                    output_dir / f"{args.branch}_{frame:03d}.png"
                )
            if frame + 1 < args.frames:
                HARNESS.cycle(emu, 1)
        emu.input.keypad_rm_key(direction_mask | y_mask)
    finally:
        emu.destroy()

    output.write_text(
        json.dumps(
            {
                "branch": args.branch,
                "rom_sha256": actual_rom_hash,
                "state": str(state),
                "rows": rows,
            },
            indent=2,
        )
    )
    return 0


def run_isolated_branch(
    args: argparse.Namespace,
    branch: str,
    rom: Path,
    rom_hash: str,
    state: Path,
    output: Path,
    output_dir: Path,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--internal-branch",
        branch,
        "--rom",
        str(rom),
        "--state",
        str(state),
        "--branch-output",
        str(output),
        "--expected-rom-sha256",
        rom_hash,
        "--direction",
        args.direction,
        "--frames",
        str(args.frames),
        "--y-frame",
        str(args.y_frame),
        "--output-dir",
        str(output_dir),
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=args.branch_timeout,
    )
    if completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"{branch} branch failed: {details}")
    return json.loads(output.read_text())


def compare_branches(
    control: dict[str, Any],
    treatment: dict[str, Any],
    y_frame: int,
) -> tuple[dict[str, Any], list[str]]:
    control_rows = control["rows"]
    treatment_rows = treatment["rows"]
    control_positions = [tuple(row["map_location"]) for row in control_rows]
    treatment_positions = [tuple(row["map_location"]) for row in treatment_rows]
    coordinate_differences = [
        frame
        for frame, (left, right) in enumerate(
            zip(control_positions, treatment_positions)
        )
        if left != right
    ]
    control_final_location = control_positions[-1]
    treatment_final_location = treatment_positions[-1]
    control_moved_after_y = any(
        position != control_positions[y_frame]
        for position in control_positions[y_frame + 1 :]
    )
    treatment_engaged = any(
        row["selector_flags"] & SELECTOR_ACTIVE_FLAG
        for row in treatment_rows[y_frame + 1 :]
    )
    treatment_active_frames = [
        row["frame"]
        for row in treatment_rows
        if row["selector_flags"] & SELECTOR_ACTIVE_FLAG
    ]
    selector_persisted_through_hold = bool(treatment_active_frames) \
        and treatment_active_frames[-1] == treatment_rows[-1]["frame"] \
        and treatment_active_frames == list(range(
            treatment_active_frames[0],
            treatment_rows[-1]["frame"] + 1,
        ))
    failures = []
    if not treatment_engaged:
        failures.append("selector active flag never engaged after Y")
    elif not selector_persisted_through_hold:
        failures.append(
            "selector did not remain continuously active through the final "
            "held-Y frame"
        )
    if not control_moved_after_y:
        failures.append(
            "control did not advance after the Y-injection frame; "
            "the route is not a valid walking test"
        )
    if control_final_location != treatment_final_location:
        failures.append(
            "final map locations differ: "
            f"control={control_final_location}, "
            f"treatment={treatment_final_location}"
        )

    summary = {
        "selector_engaged": treatment_engaged,
        "selector_persisted_through_hold": selector_persisted_through_hold,
        "selector_active_frames": treatment_active_frames,
        "coordinate_difference_frames": coordinate_differences,
        "final_map_location": {
            "fields": ["map_id", "x", "z"],
            "control": list(control_final_location),
            "treatment": list(treatment_final_location),
            "equal": control_final_location == treatment_final_location,
        },
        "control_moved_after_y_frame": control_moved_after_y,
    }
    return summary, failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A/B verify that pressing and holding Y while already walking does "
            "not stall the custom follower selector's overworld movement."
        )
    )
    parser.add_argument("--rom", default="test.nds")
    parser.add_argument("--dsv")
    parser.add_argument("--direction", choices=sorted(DIRECTION_KEYS), default="RIGHT")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--y-frame", type=int, default=23)
    parser.add_argument("--walk-in-frames", type=int, default=23)
    parser.add_argument("--preload-frames", type=int, default=0)
    parser.add_argument("--boot-frames", type=int, default=420)
    parser.add_argument("--ready-a-taps", type=int, default=10)
    parser.add_argument("--tap-hold-frames", type=int, default=24)
    parser.add_argument("--tap-gap-frames", type=int, default=36)
    parser.add_argument("--load-frames", type=int, default=300)
    parser.add_argument("--branch-timeout", type=int, default=60)
    parser.add_argument("--output-dir")
    parser.add_argument("--json")
    parser.add_argument("--show-emulator-log", action="store_true")
    parser.add_argument(
        "--source-contract-only",
        action="store_true",
        help="verify the fixed follower aggro intent bridge without launching a ROM",
    )
    parser.add_argument("--internal-branch", dest="branch", help=argparse.SUPPRESS)
    parser.add_argument("--state", help=argparse.SUPPRESS)
    parser.add_argument("--branch-output", help=argparse.SUPPRESS)
    parser.add_argument("--expected-rom-sha256", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    source_contract = verify_aggro_intent_bridge_source()
    if args.source_contract_only:
        print(json.dumps(source_contract, indent=2, sort_keys=True))
        return 0
    if args.branch:
        with HARNESS.silence_native_output(not args.show_emulator_log):
            return run_branch(args)

    started_at = time.monotonic()
    rom = HARNESS.repo_path(args.rom).resolve()
    if not rom.is_file():
        raise FileNotFoundError(f"ROM not found: {rom}")
    dsv = HARNESS.find_dsv(args.dsv).resolve()
    rom_hash = sha256_file(rom)
    dsv_hash = sha256_file(dsv)
    output_dir = (
        HARNESS.repo_path(args.output_dir).resolve()
        if args.output_dir
        else Path(tempfile.gettempdir())
        / f"follower_selector_movement_{rom_hash[:12]}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="follower_selector_verify_") as temp_text:
        temp_dir = Path(temp_text)
        state = temp_dir / f"state_v{VERIFY_VERSION}_{rom_hash}_{dsv_hash}.dst"
        with HARNESS.silence_native_output(not args.show_emulator_log):
            bootstrap = create_fresh_state(
                rom,
                dsv,
                state,
                args.direction,
                args.walk_in_frames,
                args,
            )
        manifest = {
            "verify_version": VERIFY_VERSION,
            "rom": str(rom),
            "rom_sha256": rom_hash,
            "dsv": str(dsv),
            "dsv_sha256": dsv_hash,
            "state": str(state),
        }
        (temp_dir / "state_manifest.json").write_text(json.dumps(manifest, indent=2))
        control = run_isolated_branch(
            args,
            "control",
            rom,
            rom_hash,
            state,
            temp_dir / "control.json",
            output_dir,
        )
        treatment = run_isolated_branch(
            args,
            "treatment",
            rom,
            rom_hash,
            state,
            temp_dir / "treatment.json",
            output_dir,
        )
        comparison, failures = compare_branches(control, treatment, args.y_frame)

    result = {
        "passed": not failures,
        "failures": failures,
        "rom": str(rom),
        "rom_sha256": rom_hash,
        "dsv": str(dsv),
        "dsv_sha256": dsv_hash,
        "fresh_state": True,
        "isolated_branch_processes": True,
        "direction": args.direction,
        "frames": args.frames,
        "y_frame": args.y_frame,
        "bootstrap": bootstrap,
        "g_field_sys_ptr": f"0x{G_FIELD_SYS_PTR:08X}",
        "aggro_intent_bridge_source": source_contract,
        "comparison": comparison,
        "screenshots": sorted(str(path) for path in output_dir.glob("*.png")),
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
    }
    result_text = json.dumps(result, indent=2, sort_keys=True)
    if args.json:
        json_path = HARNESS.repo_path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(result_text + "\n")
    print(result_text)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
