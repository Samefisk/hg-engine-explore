#!/usr/bin/env python3
"""Prove move-history startup/save hooks preserve serialized party records."""

from __future__ import annotations

import sys


def _isolated_helper_path() -> tuple[str, ...]:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    base = sys.base_prefix + "/lib/" + version
    paths = (base, base + "/lib-dynload")
    if globals().get("AUTHENTICATED_LIBDESMUME_PATH") is None:
        venv = sys.executable.rsplit("/bin/", 1)[0]
        paths += (venv + "/lib/" + version + "/site-packages",)
    return paths


def _normalize_isolated_helper_path() -> None:
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


def _isolated_helper_startup() -> bool:
    return (
        sys.flags.isolated == 1
        and sys.flags.ignore_environment == 1
        and sys.flags.no_site == 1
        and sys.dont_write_bytecode
        and sys.pycache_prefix == "/dev/null"
        and "site" not in sys.modules
        and tuple(sys.path) == _isolated_helper_path()
    )


if __name__ == "__main__" and not _isolated_helper_startup():
    import posix

    script = __file__
    if not script.startswith("/"):
        script = posix.getcwd() + "/" + script
    repo = script.rsplit("/scripts/", 1)[0]
    python = repo + "/.venv/bin/python3"
    posix.execve(
        python,
        [
            python,
            "-I",
            "-S",
            "-B",
            "-X",
            "pycache_prefix=/dev/null",
            script,
            *sys.argv[1:],
        ],
        {
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C",
            "SDL_AUDIODRIVER": "dummy",
        },
    )

import argparse
import hashlib
import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace


REPO = Path(__file__).resolve().parents[1]
RAW_SAVE_SIZE = 0x80000
SAVE_COPY_BASES = (0, 0x40000)
NORMAL_SAVE_SIZE = 0xFFA0
SAVE_MAGIC = 0x20060623
PARTY_OFFSET = 0x90
PARTY_HEADER_SIZE = 8
PARTY_RECORD_SIZE = 0xEC
PARTY_RECORD_COUNT = 6
PARTY_SIZE = PARTY_HEADER_SIZE + PARTY_RECORD_COUNT * PARTY_RECORD_SIZE
BOX_SIZE = 0x88
SAVE_DATA_POINTER = 0x021D2228
PARTY_SAVE_DATA_OFFSET = 0xA0
DSV_FOOTER_MARKER = (
    b"|<--Snip above here to create a raw sav by excluding this "
    b"DeSmuME savedata footer:"
)

SUBSTRUCT_OFFSETS = (
    (0x00, 0x20, 0x40, 0x60),
    (0x00, 0x20, 0x60, 0x40),
    (0x00, 0x40, 0x20, 0x60),
    (0x00, 0x60, 0x20, 0x40),
    (0x00, 0x40, 0x60, 0x20),
    (0x00, 0x60, 0x40, 0x20),
    (0x20, 0x00, 0x40, 0x60),
    (0x20, 0x00, 0x60, 0x40),
    (0x40, 0x00, 0x20, 0x60),
    (0x60, 0x00, 0x20, 0x40),
    (0x40, 0x00, 0x60, 0x20),
    (0x60, 0x00, 0x40, 0x20),
    (0x20, 0x40, 0x00, 0x60),
    (0x20, 0x60, 0x00, 0x40),
    (0x40, 0x20, 0x00, 0x60),
    (0x60, 0x20, 0x00, 0x40),
    (0x40, 0x60, 0x00, 0x20),
    (0x60, 0x40, 0x00, 0x20),
    (0x20, 0x40, 0x60, 0x00),
    (0x20, 0x60, 0x40, 0x00),
    (0x40, 0x20, 0x60, 0x00),
    (0x60, 0x20, 0x40, 0x00),
    (0x40, 0x60, 0x20, 0x00),
    (0x60, 0x40, 0x20, 0x00),
    (0x00, 0x20, 0x40, 0x60),
    (0x00, 0x20, 0x60, 0x40),
    (0x00, 0x40, 0x20, 0x60),
    (0x00, 0x60, 0x20, 0x40),
    (0x00, 0x40, 0x60, 0x20),
    (0x00, 0x60, 0x40, 0x20),
    (0x20, 0x00, 0x40, 0x60),
    (0x20, 0x00, 0x60, 0x40),
)


def ensure_repo_venv() -> None:
    venv = REPO / ".venv"
    venv_python = venv / "bin/python3"
    if (
        Path(os.path.abspath(sys.executable))
        != Path(os.path.abspath(venv_python))
        or not _isolated_helper_startup()
    ):
        raise RuntimeError(
            "party helper requires exact repository Python with "
            "-I -S -B -X pycache_prefix=/dev/null"
        )


ensure_repo_venv()

from desmume.emulator import DeSmuME  # noqa: E402


def create_desmume() -> DeSmuME:
    authenticated = globals().get("AUTHENTICATED_LIBDESMUME_PATH")
    return DeSmuME(authenticated) if authenticated is not None else DeSmuME()


def load_headless_helpers():
    authenticated = globals().get("AUTHENTICATED_HEADLESS")
    if authenticated is not None:
        return authenticated
    path = REPO / "scripts/headless-overworld-test.py"
    source = path.read_bytes()
    module = ModuleType("headless_overworld")
    module.__file__ = str(path)
    module.__cached__ = None
    module.__loader__ = None
    module.__package__ = ""
    module.__spec__ = None
    sys.modules[module.__name__] = module
    exec(
        compile(
            source,
            str(path),
            "exec",
            dont_inherit=True,
            optimize=0,
        ),
        module.__dict__,
    )
    return module


HEADLESS = load_headless_helpers()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def require_exact(actual: bytes, expected: bytes, message: str) -> None:
    if actual == expected:
        return
    first = next(
        index
        for index, (actual_byte, expected_byte) in enumerate(zip(actual, expected))
        if actual_byte != expected_byte
    )
    raise RuntimeError(
        f"{message}; first difference +0x{first:X}: "
        f"expected 0x{expected[first]:02X}, got 0x{actual[first]:02X}"
    )


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def extract_raw_save(path: Path) -> bytes:
    data = path.read_bytes()
    marker = data.find(DSV_FOOTER_MARKER)
    raw = data[:marker] if marker >= 0 else data
    require(len(raw) >= RAW_SAVE_SIZE, f"{path} is shorter than a DS save image")
    return raw[:RAW_SAVE_SIZE]


def valid_normal_copies(raw: bytes) -> list[tuple[int, int]]:
    copies: list[tuple[int, int]] = []
    for base in SAVE_COPY_BASES:
        footer = base + NORMAL_SAVE_SIZE - 0x10
        counter, size, magic, slot, crc = struct.unpack_from("<IIIHH", raw, footer)
        if (
            size == NORMAL_SAVE_SIZE
            and magic == SAVE_MAGIC
            and slot == 0
            and crc == crc16_ccitt_false(raw[base:footer])
        ):
            copies.append((counter, base))
    return copies


def save_counter_compare(first: int, second: int) -> int:
    """Mirror retail SaveCounterCompare, including the single-step wrap."""
    if first == 0xFFFFFFFF and second == 0:
        return -1
    if first == 0 and second == 0xFFFFFFFF:
        return 1
    return (first > second) - (first < second)


def active_copy(raw: bytes) -> tuple[int, int]:
    copies = valid_normal_copies(raw)
    require(copies, "raw save has no valid normal save generation")
    selected = copies[0]
    for candidate in copies[1:]:
        if save_counter_compare(candidate[0], selected[0]) > 0:
            selected = candidate
    return selected


def party_image(raw: bytes) -> tuple[int, int, bytes]:
    counter, base = active_copy(raw)
    party = raw[base + PARTY_OFFSET:base + PARTY_OFFSET + PARTY_SIZE]
    require(len(party) == PARTY_SIZE, "party image is truncated")
    maximum, count = struct.unpack_from("<ii", party)
    require(maximum == PARTY_RECORD_COUNT, f"party capacity is {maximum}, not six")
    require(0 <= count <= maximum, f"party count {count} is invalid")
    return counter, count, party


def decrypt_box_payload(box: bytes) -> bytes:
    require(len(box) == BOX_SIZE, "BoxPokemon record has the wrong size")
    seed = struct.unpack_from("<H", box, 6)[0]
    payload = bytearray(box[8:])
    for offset in range(0, len(payload), 2):
        seed = (seed * 1103515245 + 24691) & 0xFFFFFFFF
        word = struct.unpack_from("<H", payload, offset)[0] ^ (seed >> 16)
        struct.pack_into("<H", payload, offset, word)
    return bytes(payload)


def summarize_party(party: bytes) -> list[dict[str, int | bool | str]]:
    count = struct.unpack_from("<i", party, 4)[0]
    summaries: list[dict[str, int | bool | str]] = []
    for index in range(count):
        start = PARTY_HEADER_SIZE + index * PARTY_RECORD_SIZE
        record = party[start:start + PARTY_RECORD_SIZE]
        box = record[:BOX_SIZE]
        pid, flags, stored_checksum = struct.unpack_from("<IHH", box)
        payload = decrypt_box_payload(box)
        calculated_checksum = sum(struct.unpack("<64H", payload)) & 0xFFFF
        permutation = (pid & 0x3E000) >> 13
        block_a = SUBSTRUCT_OFFSETS[permutation][0]
        species = struct.unpack_from("<H", payload, block_a)[0]
        otid = struct.unpack_from("<I", payload, block_a + 4)[0]
        shiny_value = (
            (pid & 0xFFFF)
            ^ (pid >> 16)
            ^ (otid & 0xFFFF)
            ^ (otid >> 16)
        )
        require(
            stored_checksum == calculated_checksum,
            f"party slot {index} checksum {stored_checksum:#06x} "
            f"!= calculated {calculated_checksum:#06x}",
        )
        summaries.append(
            {
                "slot": index,
                "pid": f"0x{pid:08X}",
                "otid": f"0x{otid:08X}",
                "flags": f"0x{flags:04X}",
                "checksum": f"0x{stored_checksum:04X}",
                "species": species,
                "shiny": shiny_value < 8,
            }
        )
    require(any(entry["shiny"] for entry in summaries), "fixture has no shiny party member")
    require(
        any(not entry["shiny"] for entry in summaries),
        "fixture has no normal party member",
    )
    return summaries


def boot_arguments() -> SimpleNamespace:
    return SimpleNamespace(
        boot_frames=420,
        ready_a_taps=10,
        tap_hold_frames=24,
        tap_gap_frames=36,
        load_frames=300,
    )


def import_raw(emu: DeSmuME, raw: bytes, temporary: tempfile.NamedTemporaryFile) -> None:
    temporary.write(raw)
    temporary.flush()
    require(
        emu.backup.import_file(temporary.name, force_size=0),
        "DeSmuME rejected the temporary raw save",
    )


def read_runtime_party(emu: DeSmuME) -> bytes:
    save_data = emu.memory.unsigned[SAVE_DATA_POINTER:SAVE_DATA_POINTER:4]
    require(0x02000000 <= save_data < 0x02400000, "SaveData pointer is invalid")
    start = save_data + PARTY_SAVE_DATA_OFFSET
    return bytes(emu.memory.unsigned[start:start + PARTY_SIZE:1])


def wait_for_runtime_party(
    emu: DeSmuME,
    expected: bytes,
    maximum_frames: int = 60,
) -> tuple[bytes, int]:
    """Wait for any in-progress canonical accessor lock to re-encrypt."""
    actual = read_runtime_party(emu)
    for frame in range(maximum_frames + 1):
        if actual == expected:
            return actual, frame
        emu.cycle(1)
        actual = read_runtime_party(emu)
    return actual, maximum_frames + 1


def read_runtime_save_counter(emu: DeSmuME) -> int:
    save_data = emu.memory.unsigned[SAVE_DATA_POINTER:SAVE_DATA_POINTER:4]
    return emu.memory.unsigned[save_data + 0x2F010:save_data + 0x2F010:4]


def reload_party_in_fresh_process(
    rom: Path,
    raw: bytes,
    screenshot: Path,
) -> bytes:
    _, _, expected_party = party_image(raw)
    with tempfile.NamedTemporaryFile(suffix=".sav") as saved:
        saved.write(raw)
        saved.flush()
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
                str(REPO / "scripts/headless-overworld-test.py"),
                "--rom",
                str(rom),
                "--sav",
                saved.name,
                "--read",
                f"party:bytes{PARTY_SIZE}:{SAVE_DATA_POINTER:#x}:"
                f"{PARTY_SAVE_DATA_OFFSET:#x}",
                "--action",
                "sample:60:1",
                "--screenshot",
                str(screenshot),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env={
                "PATH": "/usr/bin:/bin",
                "LC_ALL": "C",
                "SDL_AUDIODRIVER": "dummy",
            },
        )
    require(
        completed.returncode == 0,
        "fresh-process reload failed: "
        + (completed.stderr.strip() or completed.stdout.strip()),
    )
    result = json.loads(completed.stdout)
    for sample in result["actions"][0]["samples"]:
        party = bytes.fromhex(sample["reads"][0]["value"])
        if party == expected_party:
            return party
    return bytes.fromhex(result["reads"][0]["value"])


def run(args: argparse.Namespace) -> dict:
    rom = args.rom.resolve()
    dsv = args.dsv.resolve()
    require(rom.is_file(), f"ROM not found: {rom}")
    require(dsv.is_file(), f"DSV not found: {dsv}")
    source_hash = hashlib.sha256(dsv.read_bytes()).hexdigest()
    if args.expected_dsv_sha256:
        require(
            source_hash == args.expected_dsv_sha256.lower(),
            f"preserved DSV SHA-256 changed: {source_hash}",
        )

    baseline_raw = extract_raw_save(dsv)
    baseline_counter, occupied, baseline_party = party_image(baseline_raw)
    baseline_records = baseline_party[PARTY_HEADER_SIZE:]
    summaries = summarize_party(baseline_party)
    args.screenshot_dir.mkdir(parents=True, exist_ok=True)
    boot_screenshot = args.screenshot_dir / "party_integrity_boot.png"
    save_screenshot = args.screenshot_dir / "party_integrity_after_save.png"
    reload_screenshot = args.screenshot_dir / "party_integrity_reload.png"

    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    with HEADLESS.silence_native_output(True):
        emu = create_desmume()
        emu.volume_set(0)
        emu.open(str(rom))
        with tempfile.NamedTemporaryFile(suffix=".sav") as imported:
            import_raw(emu, baseline_raw, imported)
            HEADLESS.boot_to_ready(boot_arguments(), emu)
            runtime_party, stabilization_frames = wait_for_runtime_party(
                emu,
                baseline_party,
            )
            require_exact(
                runtime_party,
                baseline_party,
                "one or more of the six 0xEC party records changed during boot",
            )
            emu.screenshot().save(boot_screenshot)

            # Key-only retail save flow: open menu, select SAVE, advance the
            # prompt, and accept the already-selected YES choice.
            for key, gap in (
                ("X", 36),
                ("RIGHT", 36),
                ("A", 90),
                ("A", 60),
                ("A", 90),
            ):
                HEADLESS.tap_key(emu, key, 18, gap)
            for _ in range(6):
                HEADLESS.tap_key(emu, "A", 18, 120)
                if save_counter_compare(
                    read_runtime_save_counter(emu),
                    baseline_counter,
                ) > 0:
                    break
            require(
                save_counter_compare(
                    read_runtime_save_counter(emu),
                    baseline_counter,
                ) > 0,
                "key-only save confirmations never started a normal save",
            )
            HEADLESS.cycle(emu, 600)
            emu.screenshot().save(save_screenshot)
            with tempfile.TemporaryDirectory(prefix="move-history-export-") as export_root:
                exported = Path(export_root) / "post-save.sav"
                require(
                    emu.backup.export_file(str(exported)),
                    "DeSmuME could not export the post-save backup",
                )
                saved_raw = extract_raw_save(exported)
        emu.destroy()

    saved_counter, saved_occupied, saved_party = party_image(saved_raw)
    require(
        save_counter_compare(saved_counter, baseline_counter) > 0,
        "normal save did not advance its counter",
    )
    require(saved_occupied == occupied, "normal save changed the party count")
    require_exact(
        saved_party[PARTY_HEADER_SIZE:],
        baseline_records,
        "one or more serialized 0xEC party records changed during normal save",
    )
    require(
        summarize_party(saved_party) == summaries,
        "PID/OTID/flags/checksum/species/shiny metadata changed during save",
    )
    reloaded_party = reload_party_in_fresh_process(
        rom,
        saved_raw,
        reload_screenshot,
    )
    require_exact(
        reloaded_party,
        baseline_party,
        "one or more of the six 0xEC party records changed after reload",
    )

    require(
        hashlib.sha256(dsv.read_bytes()).hexdigest() == source_hash,
        "source DSV was mutated by verification",
    )
    return {
        "rom": str(rom),
        "preserved_dsv": str(dsv),
        "preserved_dsv_sha256": source_hash,
        "baseline_save_counter": baseline_counter,
        "saved_save_counter": saved_counter,
        "occupied_party_records": occupied,
        "serialized_record_stride": PARTY_RECORD_SIZE,
        "all_six_records_exact_after_boot": runtime_party == baseline_party,
        "party_stabilization_frames": stabilization_frames,
        "all_six_records_exact_after_save": saved_party[PARTY_HEADER_SIZE:] == baseline_records,
        "all_six_records_exact_after_reload": reloaded_party == baseline_party,
        "party_records_sha256": hashlib.sha256(baseline_records).hexdigest(),
        "party": summaries,
        "screenshots": [
            str(boot_screenshot),
            str(save_screenshot),
            str(reload_screenshot),
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Boot from a preserved DSV, perform a key-only normal save, reload, "
            "and require all six serialized party records to remain exact."
        )
    )
    parser.add_argument("--rom", type=Path, default=REPO / "test.nds")
    parser.add_argument("--dsv", type=Path, required=True)
    parser.add_argument("--expected-dsv-sha256")
    parser.add_argument(
        "--screenshot-dir",
        type=Path,
        default=REPO / "build/diagnostics/move_history_party_integrity",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
    except Exception as error:
        print(f"party-integrity verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
