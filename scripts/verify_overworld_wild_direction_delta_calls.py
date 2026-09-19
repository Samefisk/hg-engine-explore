#!/usr/bin/env python3
"""Verify fixed direct Thumb calls used by the Wild engine adapter."""

import argparse
import re
import struct
import subprocess
import sys
from pathlib import Path

if __package__:
    from .verify_pokemon_move_history_capture import elf_bytes_at, layout_symbols, thumb_bl_target
else:
    from verify_pokemon_move_history_capture import elf_bytes_at, layout_symbols, thumb_bl_target


ROOT = Path(__file__).resolve().parents[1]
OBJECT = ROOT / "build/overworld_wild_spawns_overlay_linked.o"
SOURCE_OBJECT = ROOT / "build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o"
FIXED_TARGETS = {
    "OverworldWildSpawns_MovementDirectionDeltaX": 0x023BF59D,
    "OverworldWildSpawns_MovementDirectionDeltaY": 0x023BF5BF,
    "OverworldWildSpawns_SelectMovementLocomotion": 0x023B6BB9,
    "OverworldWildSpawns_SelectMovementTarget": 0x023B6BCD,
    "OverworldWildSpawns_AcknowledgeSharedMotion": 0x023BD3C5,
}


def run(*args: str) -> str:
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True).stdout


def fail(message: str) -> None:
    raise SystemExit(f"wild fixed-call verification failed: {message}")


def source_contracts(source: str, linker: str, assembly: str) -> None:
    for name, target in FIXED_TARGETS.items():
        marker = f".thumb_func\\n.thumb_set {name}, 0x{target & ~1:08X}\\n"
        if marker not in source:
            fail(f"{name} lacks the exact Thumb-function import")
        if f"{name} = 0x{target & ~1:08X} | 1;" not in linker:
            fail(f"{name} linker target changed")
    if re.sub(r"//[^\n]*", "", assembly).strip() != ".text":
        fail("duplicate Wild bridge code or data remains")
    signature = re.compile(
        r"BOOL OverworldWildSpawns_AcknowledgeSharedMotion\(\s*int slot,\s*"
        r"u8 acknowledgements,\s*u16 appliedThrough,\s*"
        r"OverworldMotionSample \*sample,\s*u8 \*phase\);")
    if signature.search(source) is None:
        fail("the Wild receipt adapter's four register and fifth stack arguments changed")


def direct_call_contract(code: bytes, address: int, target: int) -> None:
    # A Thumb-1 BL updates only LR and PC: r0-r3 and SP reach the existing
    # callee unchanged. Reject BLX, veneers, and literal-loaded tail wrappers.
    if len(code) != 4 or thumb_bl_target(code, address, address) != target & ~1:
        fail(f"call at 0x{address:08X} does not directly enter Thumb target 0x{target:08X}")


def source_fixtures(source: str, linker: str, assembly: str) -> None:
    source_contracts(source, linker, assembly)
    mutations = [
        (source.replace(".thumb_func\\n.thumb_set OverworldWildSpawns_MovementDirectionDeltaX",
                        ".thumb_set OverworldWildSpawns_MovementDirectionDeltaX"), linker, assembly),
        (source.replace("0x023BD3C4\\n", "0x023BD3C6\\n"), linker, assembly),
        (source, linker, assembly + "\n bx r3\n"),
    ]
    for mutated in mutations:
        try:
            source_contracts(*mutated)
        except SystemExit:
            pass
        else:
            fail("a changed import or duplicate bridge passed its negative control")
    address, target = 0x023D0000, 0x023BD3C5
    delta = (target & ~1) - address - 4
    code = struct.pack("<HH", 0xF000 | ((delta >> 12) & 0x7FF),
                       0xF800 | ((delta >> 1) & 0x7FF))
    direct_call_contract(code, address, target)
    for mutated in (b"\x00\x4b\x18\x47", code[:2] + b"\x00\xe8",
                    struct.pack("<HH", 0xF000, 0xF800)):
        try:
            direct_call_contract(mutated, address, target)
        except SystemExit:
            pass
        else:
            fail("a tail wrapper, BLX, or wrong BL target passed its negative control")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    source = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
    linker = (ROOT / "src/overworld_wild_spawns_overlay/linker.ld").read_text()
    assembly = (ROOT / "asm/overworld_wild_spawns_overlay/thumb_help.s").read_text()
    source_fixtures(source, linker, assembly)
    if args.source_only:
        print("Wild direct Thumb imports: source and six negative controls passed")
        return
    for path in (OBJECT, SOURCE_OBJECT):
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"missing current build artifact: {path}")

    linked_symbols = layout_symbols(OBJECT, "arm-none-eabi-objdump")
    source_symbols = layout_symbols(SOURCE_OBJECT, "arm-none-eabi-objdump")
    for name, target in FIXED_TARGETS.items():
        linked = linked_symbols.get(name)
        imported = source_symbols.get(name)
        if (linked is None or linked[2] != "*ABS*" or linked[0] & ~1 != target & ~1
                or imported != (target & ~1, 0, "*ABS*", "F")):
            fail(f"{name} is not the exact metadata-bearing direct Thumb import")
    if any("_from_thumb" in name and any(
            token in name for token in ("MovementDirectionDelta", "SelectMovement", "ApplyMotionBoundary",
                                        "CallActorMotionBoundary", "AcknowledgeSharedMotion")) for name in linked_symbols):
        fail("the linker generated an interworking veneer for a fixed target")

    # Resolve the C input section from its real functions, not an assumed
    # linker prefix. Each recorded relocation must still be one direct BL.
    origins = {linked_symbols[name][0] - symbol[0]
               for name, symbol in source_symbols.items()
               if symbol[2:] == (".text", "F") and symbol[1] > 0 and name in linked_symbols}
    if len(origins) != 1:
        fail("cannot bind the C object's call offsets to its linked input section")
    origin = origins.pop()
    relocations = run("arm-none-eabi-objdump", "-r", "-j", ".text", str(SOURCE_OBJECT))
    targets = {target & ~1: name for name, target in FIXED_TARGETS.items()}
    counts = dict.fromkeys(targets, 0)
    for offset, kind, symbol in re.findall(
            r"^([0-9a-fA-F]+)\s+(R_ARM_\w+)\s+(\S+)", relocations, re.M):
        if not symbol.startswith("*ABS*0x"):
            continue
        target = int(symbol[7:], 16)
        if target not in targets:
            continue
        if kind != "R_ARM_THM_CALL":
            fail(f"{targets[target]} no longer uses a direct Thumb call")
        address = origin + int(offset, 16)
        direct_call_contract(elf_bytes_at(OBJECT, address, 4), address, target)
        counts[target] += 1
    if not all(counts.values()):
        fail(f"a fixed target has no verified compiled callers: {counts}")
    print(f"Wild direct Thumb calls verified: {sum(counts.values())} calls, five fixed targets, no local bridges")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(error.stderr, file=sys.stderr)
        raise
