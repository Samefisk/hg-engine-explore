#!/usr/bin/env python3
import sys


def _native_bootstrap_gate():
    if __name__ != "__main__":
        return
    import posix

    environment = posix.environ
    if environment.get(b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_PROTOCOL") != (
        b"summary-move-relearn-native-bootstrap-v1"
    ):
        raise SystemExit("headless helper requires the native bootstrap")
    try:
        ready_fd = int(
            environment[b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_READY_FD"].decode(
                "ascii"
            )
        )
        go_fd = int(
            environment[b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_GO_FD"].decode(
                "ascii"
            )
        )
    except (KeyError, ValueError, UnicodeDecodeError) as error:
        raise SystemExit("native bootstrap handshake is malformed") from error
    ready = b"SUMMARY_MOVE_RELEARN_PYTHON_READY_V1\n"
    expected = b"SUMMARY_MOVE_RELEARN_NATIVE_GO_V1\n"
    if ready_fd < 3 or go_fd < 3 or ready_fd == go_fd:
        raise SystemExit("native bootstrap handshake descriptors are invalid")
    if posix.write(ready_fd, ready) != len(ready):
        raise SystemExit("native bootstrap readiness write was incomplete")
    received = b""
    while len(received) < len(expected):
        chunk = posix.read(go_fd, len(expected) - len(received))
        if not chunk:
            break
        received += chunk
    posix.close(ready_fd)
    posix.close(go_fd)
    if received != expected:
        raise SystemExit("native bootstrap did not release helper execution")


_native_bootstrap_gate()


def _isolated_helper_path():
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    base = sys.base_prefix + "/lib/" + version
    paths = (base, base + "/lib-dynload")
    if globals().get("AUTHENTICATED_LIBDESMUME_PATH") is None:
        venv = sys.executable.rsplit("/bin/", 1)[0]
        paths += (venv + "/lib/" + version + "/site-packages",)
    return paths


def _normalize_isolated_helper_path():
    expected = _isolated_helper_path()
    startup = (
        sys.base_prefix
        + "/lib/python"
        + str(sys.version_info.major)
        + str(sys.version_info.minor)
        + ".zip",
        expected[0],
        expected[1],
    )
    if (
        sys.flags.isolated == 1
        and sys.flags.ignore_environment == 1
        and sys.flags.no_site == 1
        and sys.dont_write_bytecode
        and sys.pycache_prefix == "/dev/null"
        and tuple(sys.path) == startup
    ):
        sys.path[:] = expected
        external = sys.modules["_frozen_importlib_external"]
        sys.path_hooks[:] = [
            external.FileFinder.path_hook(
                (external.SourceFileLoader, external.SOURCE_SUFFIXES),
                (external.ExtensionFileLoader, external.EXTENSION_SUFFIXES),
            )
        ]
        sys.path_importer_cache.clear()


_normalize_isolated_helper_path()


def _isolated_helper_startup():
    expected = _isolated_helper_path()
    return (
        sys.flags.isolated == 1
        and sys.flags.ignore_environment == 1
        and sys.flags.no_site == 1
        and sys.dont_write_bytecode
        and sys.pycache_prefix == "/dev/null"
        and "site" not in sys.modules
        and tuple(sys.path) == expected
    )


if __name__ == "__main__" and not _isolated_helper_startup():
    raise SystemExit(
        "headless helper requires exact isolated Python from the native bootstrap"
    )

import argparse
import ctypes
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DSV_FOOTER_MARKER = (
    b"|<--Snip above here to create a raw sav by excluding this DeSmuME savedata footer:"
)


def ensure_repo_venv() -> None:
    venv = REPO_ROOT / ".venv"
    venv_python = venv / "bin/python3"
    if (
        Path(os.path.abspath(sys.executable))
        != Path(os.path.abspath(venv_python))
        or not _isolated_helper_startup()
    ):
        raise RuntimeError(
            "headless helper requires exact repository Python with "
            "-I -S -B -X pycache_prefix=/dev/null"
        )


ensure_repo_venv()

from desmume.controls import Keys, keymask
from desmume.emulator import DeSmuME


def create_desmume() -> DeSmuME:
    authenticated = globals().get("AUTHENTICATED_LIBDESMUME_PATH")
    return DeSmuME(authenticated) if authenticated is not None else DeSmuME()

KEYS = {
    "A": Keys.KEY_A,
    "B": Keys.KEY_B,
    "SELECT": Keys.KEY_SELECT,
    "START": Keys.KEY_START,
    "RIGHT": Keys.KEY_RIGHT,
    "LEFT": Keys.KEY_LEFT,
    "UP": Keys.KEY_UP,
    "DOWN": Keys.KEY_DOWN,
    "R": Keys.KEY_R,
    "L": Keys.KEY_L,
    "X": Keys.KEY_X,
    "Y": Keys.KEY_Y,
}

READ_TYPES = {
    "u8": (1, False),
    "u16": (2, False),
    "u32": (4, False),
    "s8": (1, True),
    "s16": (2, True),
    "s32": (4, True),
}


@contextmanager
def silence_native_output(enabled: bool):
    if not enabled:
        yield
        return

    sys.stdout.flush()
    sys.stderr.flush()
    old_stdout = os.dup(1)
    old_stderr = os.dup(2)
    with open(os.devnull, "wb") as devnull:
        os.dup2(devnull.fileno(), 1)
        os.dup2(devnull.fileno(), 2)
        try:
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            ctypes.CDLL(None).fflush(None)
            os.dup2(old_stdout, 1)
            os.dup2(old_stderr, 2)
            os.close(old_stdout)
            os.close(old_stderr)


def repo_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def parse_int(value: str) -> int:
    return int(value, 0)


def find_dsv(explicit: str | None) -> Path:
    if explicit:
        path = repo_path(explicit)
        if not path.is_file():
            raise FileNotFoundError(f"DSV not found: {path}")
        return path

    candidates = [
        REPO_ROOT / "test.dsv",
        Path.home() / "Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv",
        Path.home() / "Library/Application Support/DeSmuME/0.9.12/Battery/test.dsv",
        REPO_ROOT / ".headless_desmume/.config/desmume/test.dsv",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise FileNotFoundError("No test.dsv found. Add ./test.dsv or pass --dsv PATH.")


def find_sav(explicit: str) -> Path:
    path = repo_path(explicit)
    if not path.is_file():
        raise FileNotFoundError(f"SAV not found: {path}")
    return path


def extract_raw_save(dsv_path: Path) -> bytes:
    data = dsv_path.read_bytes()
    marker_index = data.find(DSV_FOOTER_MARKER)
    if marker_index < 0:
        raise ValueError(
            f"{dsv_path} does not look like a DeSmuME .dsv with a savedata footer"
        )
    return data[:marker_index]


def cycle(emu: DeSmuME, frames: int, key_mask: int | None = None) -> None:
    for _ in range(frames):
        if key_mask is not None:
            # This DeSmuME build refreshes SDL input after every frame, so a
            # synthetic held key must be republished before each cycle.
            set_key_mask(emu, key_mask)
        emu.cycle(False)


def key_constant(name: str) -> int:
    normalized = name.strip().upper()
    if normalized not in KEYS:
        valid = ", ".join(sorted(KEYS))
        raise ValueError(f"Unknown key {name!r}. Valid keys: {valid}")
    return KEYS[normalized]


def set_key_mask(emu: DeSmuME, key_mask: int) -> None:
    """Publish the complete pressed-key mask for the next emulated frame.

    The ARM64 DeSmuME binding's keypad_get() exposes the active-low hardware
    register rather than the pressed-key mask expected by keypad_add_key().
    Updating the complete mask directly avoids combining those incompatible
    representations and makes X/Y presses reach the game reliably.
    """
    emu.input.keypad_update(key_mask)


def tap_key(emu: DeSmuME, key: str, hold_frames: int, release_frames: int) -> None:
    key_mask = keymask(key_constant(key))
    set_key_mask(emu, key_mask)
    cycle(emu, hold_frames, key_mask)
    set_key_mask(emu, 0)
    cycle(emu, release_frames)


def hold_key(emu: DeSmuME, key: str, frames: int, release_frames: int) -> None:
    key_mask = keymask(key_constant(key))
    set_key_mask(emu, key_mask)
    cycle(emu, frames, key_mask)
    set_key_mask(emu, 0)
    cycle(emu, release_frames)


def combo_key_mask(keys: str) -> int:
    mask = 0
    for key in keys.split("+"):
        mask |= keymask(key_constant(key))
    return mask


def hold_combo(emu: DeSmuME, keys: str, frames: int, release_frames: int) -> None:
    key_mask = combo_key_mask(keys)
    set_key_mask(emu, key_mask)
    cycle(emu, frames, key_mask)
    set_key_mask(emu, 0)
    cycle(emu, release_frames)


def screenshot_while_holding_combo(
    emu: DeSmuME,
    keys: str,
    reads: list[dict[str, Any]],
    hold_frames: int,
    path: str,
    release_frames: int,
) -> dict[str, Any]:
    """Capture UI and memory while a logical key combination is still held."""
    key_mask = combo_key_mask(keys)
    set_key_mask(emu, key_mask)
    cycle(emu, hold_frames, key_mask)
    result = {
        "path": save_screenshot(emu, path),
        "reads": [read_memory(emu, read) for read in reads],
    }
    set_key_mask(emu, 0)
    cycle(emu, release_frames, 0)
    return result


def boot_to_ready(args: argparse.Namespace, emu: DeSmuME) -> int:
    total_frames = 0
    cycle(emu, args.boot_frames)
    total_frames += args.boot_frames

    for _ in range(args.ready_a_taps):
        tap_key(emu, "A", args.tap_hold_frames, args.tap_gap_frames)
        total_frames += args.tap_hold_frames + args.tap_gap_frames

    cycle(emu, args.load_frames)
    total_frames += args.load_frames
    return total_frames


def parse_read(spec: str) -> dict[str, Any]:
    parts = spec.split(":")
    if len(parts) == 2:
        label = f"mem_{parts[1].lower()}"
        read_type, address = parts
    elif len(parts) == 3:
        label, read_type, address = parts
    elif len(parts) == 4:
        label, read_type, pointer_address, offset = parts
        address = pointer_address
    else:
        raise ValueError(
            f"Invalid read spec {spec!r}. Use label:type:address or "
            "label:type:pointer_address:offset"
        )

    read_type = read_type.lower()
    if not (read_type in READ_TYPES or read_type.startswith("bytes")):
        valid = ", ".join(sorted(READ_TYPES) + ["bytes<N>"])
        raise ValueError(f"Unknown read type {read_type!r}. Valid types: {valid}")

    read = {
        "label": label,
        "type": read_type,
        "address": parse_int(address),
    }
    if len(parts) == 4:
        read["pointer_address"] = parse_int(pointer_address)
        read["offset"] = parse_int(offset)
    return read


def read_memory(emu: DeSmuME, read: dict[str, Any]) -> dict[str, Any]:
    address = read["address"]
    if "pointer_address" in read:
        pointer_address = read["pointer_address"]
        pointer = emu.memory.unsigned[pointer_address:pointer_address:4]
        address = pointer + read["offset"]
    read_type = read["type"]
    result = {
        "label": read["label"],
        "type": read_type,
        "address": f"0x{address:08X}",
    }
    if "pointer_address" in read:
        result["pointer_address"] = f"0x{pointer_address:08X}"
        result["pointer"] = f"0x{pointer:08X}"
        result["offset"] = f"0x{read['offset']:X}"

    if read_type.startswith("bytes"):
        length_text = read_type.removeprefix("bytes")
        if not length_text:
            raise ValueError("Byte reads must specify a length, e.g. bytes16")
        length = int(length_text, 10)
        data = emu.memory.unsigned[address : address + length : 1]
        result["value"] = data.hex()
        result["length"] = length
        return result

    size, signed = READ_TYPES[read_type]
    accessor = emu.memory.signed if signed else emu.memory.unsigned
    value = accessor[address:address:size]
    result["value"] = value
    if not signed:
        result["hex"] = f"0x{value:0{size * 2}X}"
    return result


def save_screenshot(emu: DeSmuME, path_text: str) -> str:
    path = repo_path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    emu.screenshot().save(path)
    return str(path)


def sample_reads(
    emu: DeSmuME,
    reads: list[dict[str, Any]],
    frames: int,
    interval: int,
) -> list[dict[str, Any]]:
    samples = []
    if interval <= 0:
        raise ValueError("sample interval must be greater than zero")

    for frame in range(frames + 1):
        if frame % interval == 0:
            samples.append(
                {
                    "frame": frame,
                    "reads": [read_memory(emu, read) for read in reads],
                }
            )
        if frame < frames:
            cycle(emu, 1)
    return samples


def sample_while_holding_combo(
    emu: DeSmuME,
    keys: str,
    reads: list[dict[str, Any]],
    hold_frames: int,
    sample_frames: int,
    interval: int,
) -> list[dict[str, Any]]:
    samples = []
    key_mask = combo_key_mask(keys)
    if interval <= 0:
        raise ValueError("combo_sample interval must be greater than zero")
    if hold_frames < 0 or sample_frames < 0:
        raise ValueError("combo_sample frame counts must be non-negative")

    set_key_mask(emu, key_mask)
    for frame in range(sample_frames + 1):
        if frame % interval == 0:
            samples.append(
                {
                    "frame": frame,
                    "keys_held": frame < hold_frames,
                    "reads": [read_memory(emu, read) for read in reads],
                }
            )
        if frame == hold_frames:
            set_key_mask(emu, 0)
        if frame < sample_frames:
            cycle(emu, 1, key_mask if frame < hold_frames else 0)
    set_key_mask(emu, 0)
    return samples


def run_action(
    emu: DeSmuME,
    spec: str,
    reads: list[dict[str, Any]],
) -> dict[str, Any]:
    parts = spec.split(":")
    command = parts[0].lower()

    if command == "tap":
        if len(parts) not in (2, 3, 4):
            raise ValueError("tap action format: tap:KEY[:hold_frames[:release_frames]]")
        key = parts[1]
        hold_frames = parse_int(parts[2]) if len(parts) >= 3 else 18
        release_frames = parse_int(parts[3]) if len(parts) >= 4 else 18
        tap_key(emu, key, hold_frames, release_frames)
        return {
            "action": "tap",
            "key": key.upper(),
            "hold_frames": hold_frames,
            "release_frames": release_frames,
        }

    if command == "hold":
        if len(parts) not in (3, 4):
            raise ValueError("hold action format: hold:KEY:frames[:release_frames]")
        key = parts[1]
        frames = parse_int(parts[2])
        release_frames = parse_int(parts[3]) if len(parts) == 4 else 18
        hold_key(emu, key, frames, release_frames)
        return {
            "action": "hold",
            "key": key.upper(),
            "frames": frames,
            "release_frames": release_frames,
        }

    if command == "combo":
        if len(parts) not in (3, 4):
            raise ValueError("combo action format: combo:KEY+KEY:frames[:release_frames]")
        keys = parts[1]
        frames = parse_int(parts[2])
        release_frames = parse_int(parts[3]) if len(parts) == 4 else 18
        hold_combo(emu, keys, frames, release_frames)
        return {
            "action": "combo",
            "keys": [key.strip().upper() for key in keys.split("+")],
            "frames": frames,
            "release_frames": release_frames,
        }

    if command == "combo_sample":
        if len(parts) not in (4, 5):
            raise ValueError(
                "combo_sample action format: combo_sample:KEY+KEY:hold_frames:sample_frames[:interval]"
            )
        keys = parts[1]
        hold_frames = parse_int(parts[2])
        sample_frames = parse_int(parts[3])
        interval = parse_int(parts[4]) if len(parts) == 5 else 1
        return {
            "action": "combo_sample",
            "keys": [key.strip().upper() for key in keys.split("+")],
            "hold_frames": hold_frames,
            "sample_frames": sample_frames,
            "interval": interval,
            "samples": sample_while_holding_combo(
                emu,
                keys,
                reads,
                hold_frames,
                sample_frames,
                interval,
            ),
        }

    if command == "combo_screenshot":
        if len(parts) not in (4, 5):
            raise ValueError(
                "combo_screenshot action format: "
                "combo_screenshot:KEY+KEY:hold_frames:path[:release_frames]"
            )
        keys = parts[1]
        hold_frames = parse_int(parts[2])
        path = parts[3]
        release_frames = parse_int(parts[4]) if len(parts) == 5 else 18
        held = screenshot_while_holding_combo(
            emu,
            keys,
            reads,
            hold_frames,
            path,
            release_frames,
        )
        return {
            "action": "combo_screenshot",
            "keys": [key.strip().upper() for key in keys.split("+")],
            "hold_frames": hold_frames,
            "release_frames": release_frames,
            "held_reads": held["reads"],
            "path": held["path"],
        }

    if command == "wait":
        if len(parts) != 2:
            raise ValueError("wait action format: wait:frames")
        frames = parse_int(parts[1])
        cycle(emu, frames)
        return {"action": "wait", "frames": frames}

    if command == "sample":
        if len(parts) not in (2, 3):
            raise ValueError("sample action format: sample:frames[:interval]")
        frames = parse_int(parts[1])
        interval = parse_int(parts[2]) if len(parts) == 3 else 1
        return {
            "action": "sample",
            "frames": frames,
            "interval": interval,
            "samples": sample_reads(emu, reads, frames, interval),
        }

    if command == "screenshot":
        if len(parts) != 2:
            raise ValueError("screenshot action format: screenshot:path")
        return {"action": "screenshot", "path": save_screenshot(emu, parts[1])}

    raise ValueError(f"Unknown action {command!r}")


def parse_expectation(spec: str) -> tuple[str, str]:
    if "=" not in spec:
        raise ValueError("Expectation format: label=value")
    label, expected = spec.split("=", 1)
    return label, expected


def check_expectations(reads: list[dict[str, Any]], specs: list[str]) -> list[dict[str, Any]]:
    by_label = {read["label"]: read for read in reads}
    results = []

    for spec in specs:
        label, expected_text = parse_expectation(spec)
        if label not in by_label:
            raise ValueError(f"Expectation references unknown read label {label!r}")

        read = by_label[label]
        actual = read["value"]
        if isinstance(actual, int):
            expected: int | str = parse_int(expected_text)
        else:
            expected = expected_text.lower().removeprefix("0x")

        results.append(
            {
                "label": label,
                "expected": expected,
                "actual": actual,
                "passed": actual == expected,
            }
        )

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Boot test.nds with test.dsv to the overworld, run key-only actions, "
            "and read emulator memory."
        )
    )
    parser.add_argument("--rom", default="test.nds", help="ROM to boot. Default: test.nds")
    parser.add_argument(
        "--dsv",
        help=(
            "DeSmuME .dsv to load. Default search order: ./test.dsv, macOS "
            "DeSmuME 0.9.13, macOS DeSmuME 0.9.12, .headless_desmume copy."
        ),
    )
    parser.add_argument(
        "--sav",
        help=(
            "Raw .sav to import instead of a .dsv. This is opt-in; by default "
            "the verifier continues to load test.dsv."
        ),
    )
    parser.add_argument(
        "--screenshot",
        default="documentation/verification_screenshots/headless_overworld_test_latest.png",
        help="Native 256x384 screenshot path after boot/actions.",
    )
    parser.add_argument("--no-screenshot", action="store_true", help="Skip final screenshot.")
    parser.add_argument(
        "--read",
        action="append",
        default=[],
        help="Memory read: label:type:address. Types: u8,u16,u32,s8,s16,s32,bytes<N>.",
    )
    parser.add_argument(
        "--expect",
        action="append",
        default=[],
        help="Assert a memory read value by label, e.g. --expect flag=0.",
    )
    parser.add_argument(
        "--action",
        action="append",
        default=[],
        help=(
            "Key-only action: tap:KEY[:hold[:gap]], hold:KEY:frames[:gap], "
            "combo:KEY+KEY:frames[:gap], wait:frames, sample:frames[:interval], "
            "combo_sample:KEY+KEY:hold_frames:sample_frames[:interval], "
            "combo_screenshot:KEY+KEY:hold_frames:path[:release_frames], screenshot:path."
        ),
    )
    parser.add_argument("--boot-frames", type=int, default=420)
    parser.add_argument("--ready-a-taps", type=int, default=10)
    parser.add_argument("--tap-hold-frames", type=int, default=24)
    parser.add_argument("--tap-gap-frames", type=int, default=36)
    parser.add_argument("--load-frames", type=int, default=300)
    parser.add_argument(
        "--show-emulator-log",
        action="store_true",
        help="Let native DeSmuME stdout/stderr logs pass through.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    rom = repo_path(args.rom)
    if not rom.is_file():
        raise FileNotFoundError(f"ROM not found: {rom}")

    if args.dsv and args.sav:
        raise ValueError("Use either --dsv or --sav, not both.")

    dsv = None
    sav = None
    if args.sav:
        sav = find_sav(args.sav)
        raw_save = sav.read_bytes()
    else:
        dsv = find_dsv(args.dsv)
        raw_save = extract_raw_save(dsv)

    parsed_reads = [parse_read(spec) for spec in args.read]
    started_at = time.monotonic()

    with silence_native_output(not args.show_emulator_log):
        emu = create_desmume()
        emu.volume_set(0)
        emu.open(str(rom))
        with tempfile.NamedTemporaryFile(suffix=".sav") as raw_file:
            raw_file.write(raw_save)
            raw_file.flush()
            emu.backup.import_file(raw_file.name, force_size=0)

            ready_frames = boot_to_ready(args, emu)
            completed_actions = [
                run_action(emu, action, parsed_reads) for action in args.action
            ]
            reads = [read_memory(emu, read) for read in parsed_reads]
            screenshot = None
            if not args.no_screenshot:
                screenshot = save_screenshot(emu, args.screenshot)
            emu.destroy()

    expectations = check_expectations(reads, args.expect)
    elapsed_seconds = round(time.monotonic() - started_at, 3)
    result = {
        "rom": str(rom),
        "dsv": str(dsv) if dsv is not None else None,
        "sav": str(sav) if sav is not None else None,
        "save_kind": "sav" if sav is not None else "dsv",
        "ready_frames": ready_frames,
        "elapsed_seconds": elapsed_seconds,
        "actions": completed_actions,
        "reads": reads,
        "expectations": expectations,
        "passed": all(expectation["passed"] for expectation in expectations),
        "screenshot": screenshot,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
