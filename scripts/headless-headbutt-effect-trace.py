#!/usr/bin/env python3
import argparse
import ctypes
import json
import os
import re
import sys
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
    if Path(sys.prefix).resolve() == venv.resolve():
        return
    if not venv_python.is_file():
        return
    os.execv(str(venv_python), [str(venv_python), *sys.argv])


ensure_repo_venv()

from desmume.controls import Keys, keymask
from desmume.emulator import DeSmuME


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

DEFAULT_HOOKS = {
    "effect_lookup_021F1450": 0x021F1450,
    "effect_context_from_object_021F146C": 0x021F146C,
    "effect_create_descriptor_021F1620": 0x021F1620,
    "effect_destroy_descriptor_021F1640": 0x021F1640,
    "headbutt_task_021FC748": 0x021FC748,
    "headbutt_avatar_wrapper_021FCFEC": 0x021FCFEC,
    "raw_ctor_FDA14": 0x021FDA14,
    "raw_dtor_FDA30": 0x021FDA30,
    "wrapper_FDA74": 0x021FDA74,
    "raw_ctor_FE590": 0x021FE590,
    "raw_dtor_FE5A4": 0x021FE5A4,
    "wrapper_FE66C": 0x021FE66C,
    "raw_ctor_FEEEC": 0x021FEEEC,
    "raw_dtor_FEF08": 0x021FEF08,
    "raw_ctor_FF854": 0x021FF854,
    "raw_dtor_FF870": 0x021FF870,
    "raw_ctor_FFC0C": 0x021FFC0C,
    "raw_dtor_FFC28": 0x021FFC28,
    "raw_ctor_22001E4": 0x022001E4,
    "raw_dtor_22001F8": 0x022001F8,
    "headbutt_leaf_ctor_candidate_22006A8": 0x022006A8,
    "headbutt_leaf_dtor_candidate_22006C4": 0x022006C4,
    "headbutt_leaf_restart_candidate_22006D4": 0x022006D4,
    "headbutt_leaf_wrapper_candidate_2200730": 0x02200730,
    "headbutt_avatar_effect_candidate_22008B4": 0x022008B4,
    "raw_ctor_2203A18": 0x02203A18,
    "raw_dtor_2203A38": 0x02203A38,
    "wrapper_2203A48": 0x02203A48,
    "raw_ctor_2203E40": 0x02203E40,
    "raw_dtor_2203E64": 0x02203E64,
    "wrapper_2203EA0": 0x02203EA0,
    "field_effect_create_wrapper_02068B0C": 0x02068B0C,
    "field_effect_destroy_02068B48": 0x02068B48,
    "field_effect_get_init_data_02068D98": 0x02068D98,
    "ov02_headbutt_leaf_burst_spawner_0224A9D8": 0x0224A9D8,
    "ov02_headbutt_leaf_create_one_0224AA44": 0x0224AA44,
    "ov02_headbutt_leaf_descriptor_init_0224AA80": 0x0224AA80,
    "ov02_headbutt_leaf_descriptor_update_0224AAC8": 0x0224AAC8,
    "ov02_headbutt_leaf_descriptor_dtor_0224AAD4": 0x0224AAD4,
    "ov02_headbutt_leaf_descriptor_noop_0224AB54": 0x0224AB54,
    "ov02_headbutt_leaf_controller_create_0224B72C": 0x0224B72C,
    "ov02_headbutt_leaf_controller_destroy_0224B768": 0x0224B768,
}

SYMBOL_PATTERN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(0x[0-9A-Fa-f]+)\s*\|\s*1\s*;")


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


def parse_range(value: str) -> tuple[int, int]:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("range format: START:SIZE")
    return parse_int(parts[0]), parse_int(parts[1])


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


def extract_raw_save(dsv_path: Path) -> bytes:
    data = dsv_path.read_bytes()
    marker_index = data.find(DSV_FOOTER_MARKER)
    if marker_index < 0:
        raise ValueError(f"{dsv_path} does not look like a DeSmuME .dsv")
    return data[:marker_index]


def key_constant(name: str) -> int:
    normalized = name.strip().upper()
    if normalized not in KEYS:
        valid = ", ".join(sorted(KEYS))
        raise ValueError(f"Unknown key {name!r}. Valid keys: {valid}")
    return KEYS[normalized]


def read_bytes(emu: DeSmuME, address: int, length: int) -> bytes | None:
    if length <= 0:
        return b""
    try:
        return bytes(emu.memory.unsigned[address : address + length : 1])
    except Exception:
        return None


def is_main_ram(value: int) -> bool:
    return 0x02000000 <= value < 0x02400000


def is_code_or_overlay(value: int) -> bool:
    return 0x02000000 <= value < 0x02400000


def load_ld_symbols(path: Path) -> dict[int, list[str]]:
    symbols: dict[int, list[str]] = {}
    if not path.is_file():
        return symbols
    for line in path.read_text(errors="ignore").splitlines():
        match = SYMBOL_PATTERN.match(line)
        if match is None:
            continue
        name = match.group(1)
        address = int(match.group(2), 16) & ~1
        symbols.setdefault(address, []).append(name)
    return symbols


def effect_export_hooks(symbols: dict[int, list[str]]) -> dict[str, int]:
    hooks = {}
    interesting_prefixes = (
        "ov01_021F",
        "ov01_0220",
        "FieldEffect_",
    )
    for address, names in symbols.items():
        for name in names:
            if name.startswith(interesting_prefixes):
                hooks[name] = address
    return hooks


def parse_hook_spec(value: str) -> tuple[str, int]:
    if "=" in value:
        name, address = value.split("=", 1)
        return name, parse_int(address) & ~1
    address = parse_int(value) & ~1
    return f"hook_{address:08X}", address


def nearest_symbol(address: int, symbols: dict[int, list[str]]) -> str | None:
    if not symbols:
        return None
    best_addr = None
    for candidate in symbols:
        if candidate <= address and (best_addr is None or candidate > best_addr):
            best_addr = candidate
    if best_addr is None or address - best_addr > 0x200:
        return None
    names = "/".join(symbols[best_addr])
    delta = address - best_addr
    if delta == 0:
        return names
    return f"{names}+0x{delta:X}"


class HeadbuttTracer:
    def __init__(
        self,
        emu: DeSmuME,
        symbols: dict[int, list[str]],
        max_events: int,
        ptr_dump_len: int,
    ) -> None:
        self.emu = emu
        self.symbols = symbols
        self.max_events = max_events
        self.ptr_dump_len = ptr_dump_len
        self.frame = 0
        self.enabled = False
        self.events: list[dict[str, Any]] = []

    def cycle(self, frames: int) -> None:
        for _ in range(frames):
            self.emu.cycle(False)
            self.frame += 1

    def register_hooks(self, hooks: dict[str, int]) -> None:
        by_address: dict[int, list[str]] = {}
        for name, address in hooks.items():
            by_address.setdefault(address & ~1, []).append(name)

        for address, names in sorted(by_address.items()):
            hook_name = "/".join(sorted(set(names)))
            self.emu.memory.register_exec(address, self._make_callback(hook_name, address))

    def _make_callback(self, hook_name: str, expected_address: int):
        def callback(address: int, size: int) -> None:
            if not self.enabled or len(self.events) >= self.max_events:
                return

            regs = self._read_arm9_registers()
            event: dict[str, Any] = {
                "frame": self.frame,
                "hook": hook_name,
                "address": f"0x{address:08X}",
                "expected_address": f"0x{expected_address:08X}",
                "size": size,
                "nearest_symbol": nearest_symbol(address, self.symbols),
                "registers": {key: f"0x{value:08X}" for key, value in regs.items()},
            }

            pointed = {}
            for reg in ("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "lr"):
                value = regs[reg]
                if is_main_ram(value):
                    data = read_bytes(self.emu, value, self.ptr_dump_len)
                    pointed[reg] = {
                        "address": f"0x{value:08X}",
                        "nearest_symbol": nearest_symbol(value, self.symbols),
                        "bytes": data.hex() if data is not None else None,
                    }
                elif is_code_or_overlay(value):
                    pointed[reg] = {
                        "address": f"0x{value:08X}",
                        "nearest_symbol": nearest_symbol(value, self.symbols),
                    }
            if pointed:
                event["pointed"] = pointed

            self.events.append(event)

        return callback

    def _read_arm9_registers(self) -> dict[str, int]:
        reg = self.emu.memory.register_arm9
        return {
            "r0": reg.r0,
            "r1": reg.r1,
            "r2": reg.r2,
            "r3": reg.r3,
            "r4": reg.r4,
            "r5": reg.r5,
            "r6": reg.r6,
            "r7": reg.r7,
            "r8": reg.r8,
            "r9": reg.r9,
            "r10": reg.r10,
            "r11": reg.r11,
            "r12": reg.r12,
            "sp": reg.sp,
            "lr": reg.lr,
            "pc": reg.pc,
            "cpsr": reg.cpsr,
        }


def tap_key(tracer: HeadbuttTracer, key: str, hold_frames: int, release_frames: int) -> None:
    key_mask = keymask(key_constant(key))
    tracer.emu.input.keypad_add_key(key_mask)
    tracer.cycle(hold_frames)
    tracer.emu.input.keypad_rm_key(key_mask)
    tracer.cycle(release_frames)


def boot_to_ready(args: argparse.Namespace, tracer: HeadbuttTracer) -> int:
    start = tracer.frame
    tracer.cycle(args.boot_frames)
    for _ in range(args.ready_a_taps):
        tap_key(tracer, "A", args.tap_hold_frames, args.tap_gap_frames)
    tracer.cycle(args.load_frames)
    return tracer.frame - start


def save_screenshot(emu: DeSmuME, path_text: str) -> str:
    path = repo_path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    emu.screenshot().save(path)
    return str(path)


def read_watch_ranges(emu: DeSmuME, ranges: list[tuple[int, int]]) -> list[dict[str, Any]]:
    reads = []
    for start, size in ranges:
        data = read_bytes(emu, start, size)
        reads.append(
            {
                "start": f"0x{start:08X}",
                "size": size,
                "bytes": data.hex() if data is not None else None,
            }
        )
    return reads


def make_summary(result: dict[str, Any]) -> dict[str, Any]:
    events = result["events"]
    interesting_events = []
    interesting_terms = (
        "leaf",
        "02068B0C",
        "02068B48",
        "0224A9D8",
        "0224AA44",
        "0224B72C",
        "0224B768",
    )
    for event in events:
        hook = event["hook"]
        if any(term in hook for term in interesting_terms):
            regs = event["registers"]
            interesting_events.append(
                {
                    "frame": event["frame"],
                    "hook": hook,
                    "lr": regs.get("lr"),
                    "r0": regs.get("r0"),
                    "r1": regs.get("r1"),
                    "r2": regs.get("r2"),
                    "r3": regs.get("r3"),
                    "r7": regs.get("r7"),
                }
            )

    return {
        "output_json": result.get("output_json"),
        "rom": result["rom"],
        "dsv": result["dsv"],
        "ready_frames": result["ready_frames"],
        "total_frames": result["total_frames"],
        "elapsed_seconds": result["elapsed_seconds"],
        "hook_count": result["hook_count"],
        "hook_counts": result["hook_counts"],
        "interesting_events": interesting_events[:80],
        "interesting_event_count": len(interesting_events),
        "screenshots": result["screenshots"],
        "tap_markers": result["tap_markers"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Boot test.nds/test.dsv, press A at the headbutt tree, and trace "
            "actual effect-related ARM9 calls with register/RAM snapshots."
        )
    )
    parser.add_argument("--rom", default="test.nds")
    parser.add_argument("--dsv")
    parser.add_argument(
        "--output",
        default="documentation/verification_screenshots/headbutt_effect_trace.json",
    )
    parser.add_argument(
        "--screenshot-prefix",
        default="documentation/verification_screenshots/headbutt_effect_trace",
    )
    parser.add_argument("--boot-frames", type=int, default=420)
    parser.add_argument("--ready-a-taps", type=int, default=10)
    parser.add_argument("--tap-hold-frames", type=int, default=24)
    parser.add_argument("--tap-gap-frames", type=int, default=36)
    parser.add_argument("--load-frames", type=int, default=300)
    parser.add_argument("--headbutt-a-taps", type=int, default=8)
    parser.add_argument("--headbutt-hold-frames", type=int, default=18)
    parser.add_argument("--headbutt-gap-frames", type=int, default=42)
    parser.add_argument("--post-frames", type=int, default=240)
    parser.add_argument("--max-events", type=int, default=400)
    parser.add_argument("--ptr-dump-len", type=int, default=32)
    parser.add_argument(
        "--all-exported-effect-hooks",
        action="store_true",
        help="Also hook all ov01_021F*/ov01_0220*/FieldEffect_* symbols exported in rom.ld.",
    )
    parser.add_argument(
        "--hook",
        action="append",
        default=[],
        help="Additional exec hook as NAME=0xADDR or 0xADDR.",
    )
    parser.add_argument(
        "--watch",
        action="append",
        default=[],
        help="RAM range to dump at ready/before/after, format START:SIZE.",
    )
    parser.add_argument("--show-emulator-log", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    rom = repo_path(args.rom)
    if not rom.is_file():
        raise FileNotFoundError(f"ROM not found: {rom}")
    dsv = find_dsv(args.dsv)
    raw_save = extract_raw_save(dsv)
    symbols = load_ld_symbols(REPO_ROOT / "rom.ld")

    hooks = dict(DEFAULT_HOOKS)
    if args.all_exported_effect_hooks:
        hooks.update(effect_export_hooks(symbols))
    for spec in args.hook:
        name, address = parse_hook_spec(spec)
        hooks[name] = address

    watch_ranges = [parse_range(spec) for spec in args.watch]
    output_path = repo_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    screenshot_prefix = args.screenshot_prefix
    started_at = time.monotonic()

    with silence_native_output(not args.show_emulator_log):
        emu = DeSmuME()
        emu.volume_set(0)
        emu.open(str(rom))
        tracer = HeadbuttTracer(emu, symbols, args.max_events, args.ptr_dump_len)
        tracer.register_hooks(hooks)

        with tempfile.NamedTemporaryFile(suffix=".sav") as raw_file:
            raw_file.write(raw_save)
            raw_file.flush()
            emu.backup.import_file(raw_file.name, force_size=0)

            ready_frames = boot_to_ready(args, tracer)
            ready_screenshot = save_screenshot(
                emu,
                f"{screenshot_prefix}_00_ready.png",
            )
            ready_reads = read_watch_ranges(emu, watch_ranges)

            tracer.enabled = True
            before_reads = read_watch_ranges(emu, watch_ranges)
            tap_screenshots = []
            tap_markers = []
            for index in range(args.headbutt_a_taps):
                start_frame = tracer.frame
                tap_key(
                    tracer,
                    "A",
                    args.headbutt_hold_frames,
                    args.headbutt_gap_frames,
                )
                screenshot = save_screenshot(
                    emu,
                    f"{screenshot_prefix}_{index + 1:02d}_after_a.png",
                )
                tap_screenshots.append(screenshot)
                tap_markers.append(
                    {
                        "tap": index + 1,
                        "start_frame": start_frame,
                        "hold_end_frame": start_frame + args.headbutt_hold_frames,
                        "end_frame": tracer.frame,
                        "screenshot": screenshot,
                    }
                )
            tracer.cycle(args.post_frames)
            after_screenshot = save_screenshot(emu, f"{screenshot_prefix}_99_after.png")
            after_reads = read_watch_ranges(emu, watch_ranges)
            tracer.enabled = False
            emu.destroy()

    hook_counts: dict[str, int] = {}
    for event in tracer.events:
        hook_counts[event["hook"]] = hook_counts.get(event["hook"], 0) + 1

    result = {
        "rom": str(rom),
        "dsv": str(dsv),
        "ready_frames": ready_frames,
        "total_frames": tracer.frame,
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
        "hook_count": len(hooks),
        "hooks": {name: f"0x{address:08X}" for name, address in sorted(hooks.items())},
        "hook_counts": dict(sorted(hook_counts.items())),
        "output_json": str(output_path),
        "events": tracer.events,
        "screenshots": {
            "ready": ready_screenshot,
            "after_each_a": tap_screenshots,
            "after": after_screenshot,
        },
        "tap_markers": tap_markers,
        "watch_reads": {
            "ready": ready_reads,
            "before_trace": before_reads,
            "after_trace": after_reads,
        },
    }
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(make_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
