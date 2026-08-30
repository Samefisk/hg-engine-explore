#!/usr/bin/env python3
"""Reject ARM/Thumb interworking thunks for the overworld direction helpers."""

import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OBJECT = ROOT / "build/overworld_wild_spawns_overlay_linked.o"
WALK_MODULE_SLOTS = {
    "OverworldWildSpawns_MovementDirectionDeltaX": 0x023BF424,
    "OverworldWildSpawns_MovementDirectionDeltaY": 0x023BF428,
}


def run(*args: str) -> str:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def fail(message: str) -> None:
    raise SystemExit(f"direction-delta call verification failed: {message}")


def main() -> None:
    if not OBJECT.is_file() or OBJECT.stat().st_size == 0:
        fail(f"missing linked overlay: {OBJECT}")

    nm = run("arm-none-eabi-nm", "-n", str(OBJECT))
    if re.search(r"__OverworldWildSpawns_MovementDirectionDelta[XY]_from_thumb", nm):
        fail("the linker generated an ARM-mode interworking thunk")

    section_match = re.search(
        r"\]\s+\.text\s+PROGBITS\s+([0-9A-Fa-f]+)",
        run("arm-none-eabi-readelf", "-SW", str(OBJECT)),
    )
    if section_match is None:
        fail("linked overlay has no .text section")
    try:
        text_address = int(section_match.group(1), 16)
    except ValueError as error:
        fail(f"could not parse .text address: {error}")

    symbols = {}
    for line in nm.splitlines():
        parts = line.split()
        if len(parts) != 3 or parts[2] not in WALK_MODULE_SLOTS:
            continue
        symbols[parts[2]] = (int(parts[0], 16), parts[1])

    with tempfile.TemporaryDirectory(prefix="ow-direction-delta-") as temp_dir:
        text_path = Path(temp_dir) / "text.bin"
        subprocess.run(
            [
                "arm-none-eabi-objcopy",
                "--dump-section",
                f".text={text_path}",
                str(OBJECT),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        text = text_path.read_bytes()

    for name, slot in WALK_MODULE_SLOTS.items():
        if name not in symbols:
            fail(f"missing symbol {name}")
        address, symbol_type = symbols[name]
        if symbol_type not in ("T", "t"):
            fail(f"{name} is {symbol_type}, not a Thumb function")
        offset = address - text_address
        if offset < 0 or offset + 12 > len(text):
            fail(f"{name} is outside .text")
        module = bytes((0xDF, 0xF8, 0x04, 0x30, 0x1B, 0x68, 0x18, 0x47)) \
            + slot.to_bytes(4, "little")
        actual = text[offset : offset + 12]
        if actual != module:
            fail(
                f"{name} wrapper bytes differ: "
                f"expected resident module {module.hex()}, got {actual.hex()}"
            )

    print("overworld wild direction-delta Thumb calls verified")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(error.stderr, file=sys.stderr)
        raise
