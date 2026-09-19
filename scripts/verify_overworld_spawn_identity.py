#!/usr/bin/env python3
"""S1: run the real spawn boundary with native object lifecycle stubs.

The stock lookup oracle follows map_object.c's first ACTIVE ID match excluding
flag25. This proves host lifecycle checks, not ARM packaging or game behavior.
"""
from pathlib import Path
import argparse
import os
import re
import shlex
import subprocess
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
SERVICE = ROOT / "src/pokemon_move_history_overlay/overworld_spawn_identity.c"
FIXTURE = ROOT / "tools/overworld/fixtures/spawn_identity_harness.c"
ENTRY = 0x023C0000
SYMBOL = "OverworldWildSpawnIdentity_PrepareSlot"


def checked(condition, reason):
    if not condition:
        raise ValueError("spawn identity package: " + reason)


def binding_contract(service, caller):
    checked(service is not None and service[0] == ENTRY | 1
            and 0 < service[1] <= 0x400 and service[2] == "FUNC"
            and service[3] not in ("ABS", "UND"), "hosted Thumb function differs")
    checked(caller == (ENTRY | 1, 0, "FUNC", "ABS"), "caller typed Thumb import differs")


def code_contract(linked, packaged):
    checked(bool(linked) and linked == packaged, "packaged function bytes differ")


def package_controls():
    good = (ENTRY | 1, 384, "FUNC", "4")
    caller = (ENTRY | 1, 0, "FUNC", "ABS")
    binding_contract(good, caller)
    bads = [(None, caller), ((ENTRY, 384, "FUNC", "4"), caller),
            ((ENTRY | 1, 0, "FUNC", "4"), caller),
            ((ENTRY | 1, 1025, "FUNC", "4"), caller),
            ((ENTRY | 1, 384, "FUNC", "ABS"), caller),
            (good, (ENTRY, 0, "FUNC", "ABS")),
            (good, (ENTRY | 1, 0, "NOTYPE", "ABS"))]
    for service, imported in bads:
        try:
            binding_contract(service, imported)
        except ValueError:
            continue
        raise AssertionError("wrong-mode/size/import control passed")
    for linked, packaged in ((b"a", b"b"), (b"", b""), (b"ab", b"a")):
        try:
            code_contract(linked, packaged)
        except ValueError:
            continue
        raise AssertionError("changed/missing package code control passed")
    print("PASS 10 package binding/body rejection controls (host fixtures)")


def verify_package(rom_path):
    if __package__:
        from .verify_pokemon_move_history_capture import elf_bytes_at, elf_helper_bindings, direct_thumb_calls
    else:
        from verify_pokemon_move_history_capture import elf_bytes_at, elf_helper_bindings, direct_thumb_calls
    host = ROOT / "build/pokemon_move_history_overlay_linked.o"
    wild = ROOT / "build/overworld_wild_spawns_overlay_linked.o"
    service = elf_helper_bindings(host, (SYMBOL,)).get(SYMBOL)
    imported = elf_helper_bindings(wild, (SYMBOL,)).get(SYMBOL)
    binding_contract(service, imported)
    rom = rom_path.read_bytes()
    checked(len(rom) >= 0x60, "ROM header is missing")
    fat_offset, fat_size, y9_offset, y9_size = struct.unpack_from("<4I", rom, 0x48)
    checked(fat_size % 8 == 0 and fat_offset + fat_size <= len(rom)
            and y9_size % 32 == 0 and y9_offset + y9_size <= len(rom), "ROM tables differ")

    def overlay(number, expected_base):
        rows = [struct.unpack_from("<8I", rom, pos)
                for pos in range(y9_offset, y9_offset + y9_size, 32)
                if struct.unpack_from("<I", rom, pos)[0] == number]
        checked(len(rows) == 1, f"overlay {number} missing/duplicated")
        _id, base, size, _bss, _init, _end, file_id, flags = rows[0]
        checked(base == expected_base and not flags & 0x01000000
                and file_id < fat_size // 8, f"overlay {number} metadata differs")
        start, end = struct.unpack_from("<II", rom, fat_offset + 8 * file_id)
        checked(start <= end <= len(rom) and end - start == size,
                f"overlay {number} file bounds differ")
        return base, rom[start:end]

    base, image = overlay(153, 0x023BE400)
    checked(base + len(image) <= 0x023C0400, "resident tail exceeds reserved overlay")
    linked = elf_bytes_at(host, ENTRY, service[1])
    code_contract(linked, image[ENTRY - base:ENTRY - base + service[1]])
    caller_name = "OverworldWildSpawns_SpawnPreparedEncounter"
    caller = elf_helper_bindings(wild, (caller_name,)).get(caller_name)
    checked(caller is not None and caller[2] == "FUNC" and caller[0] & 1, "spawn caller is not Thumb")
    address, size = caller[0] & ~1, caller[1]
    wild_base, wild_image = overlay(149, 0x023CCFD8)
    code_contract(elf_bytes_at(wild, address, size), wild_image[address - wild_base:address - wild_base + size])
    disassembly = subprocess.check_output(["arm-none-eabi-objdump", "-d",
        f"--start-address={address}", f"--stop-address={address + size}", str(wild)], text=True)
    calls = [call for call in direct_thumb_calls(disassembly) if call[2] == ENTRY]
    checked(len(calls) == 1 and calls[0][1] == "bl", "spawn caller does not make one typed direct BL")
    print(f"PASS S2 hosted Thumb lifecycle at0x{ENTRY:08X}, {service[1]} bytes; exact ROM caller/body")


def function(source, name, result):
    found = [match for match in re.finditer(r"\b" + name + r"\s*\([^;{}]*\)\s*\{", source)
             if not source[source.rfind("\n", 0, match.start()) + 1:match.start()]
             or source[source.rfind("\n", 0, match.start()) + 1:match.start()].startswith("static ")]
    if len(found) != 1:
        raise ValueError(f"expected exactly one {name} body")
    start = found[0]
    depth = 1
    for end in range(start.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if not depth:
            return f"static {result} " + source[start.start():end + 1]
    raise ValueError(f"unterminated {name}")


def source():
    product = PRODUCT.read_text()
    header = (ROOT / "include/overworld_wild_spawns_internal.h").read_text()
    names = ("OW_WILD_LAND_SURF_MAX_SPAWNS", "OW_WILD_HEADBUTT_MAX_SPAWNS",
             "OW_WILD_FISH_MAX_SPAWNS", "OW_WILD_HEADBUTT_SLOT_START",
             "OW_WILD_FISH_SLOT_START", "OW_WILD_FOLLOWER_SLOT", "OW_WILD_MAX_SPAWNS")
    constants = []
    for name in names:
        matches = re.findall(r"^#define " + name + r"\s+[^\n]+$", header, re.M)
        if len(matches) != 1:
            raise ValueError(f"missing production constant {name}")
        constants.extend(matches)
    matches = re.findall(
        r"^#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN\s+[^\n]+$",
        product,
        re.M,
    )
    if len(matches) != 1:
        raise ValueError("missing production off-screen Hop locomotion constant")
    constants.extend(matches)
    text = FIXTURE.read_text()
    for marker, body in {
        "/* @CONSTANTS@ */": "\n".join(constants),
        "/* @APPLY_SETUP@ */": function(product, "OverworldWildSpawns_ApplySpawnObjectSetup", "void"),
        "/* @PREPARE_IDENTITY@ */": function(SERVICE.read_text(), "OverworldWildSpawnIdentity_PrepareSlot", "int"),
        "/* @SPAWN@ */": function(product, "OverworldWildSpawns_SpawnPreparedEncounter", "BOOL"),
    }.items():
        if text.count(marker) != 1:
            raise ValueError(f"missing fixture marker {marker}")
        text = text.replace(marker, body)
    return text


def execute(text):
    with tempfile.TemporaryDirectory(prefix="overworld-spawn-identity-") as directory:
        path = Path(directory)
        (path / "test.c").write_text(text)
        compiled = subprocess.run([*shlex.split(os.environ.get("HOST_CC", "cc")),
                                   "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                                   str(path / "test.c"), "-o", str(path / "test")],
                                  capture_output=True, text=True, check=False)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout + compiled.stderr)
        return subprocess.run([str(path / "test")], capture_output=True, text=True, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-only", action="store_true")
    parser.add_argument("--rom", type=Path, default=ROOT / "test.nds")
    args = parser.parse_args()
    package_controls()
    if args.package_only:
        verify_package(args.rom)
        return 0
    text = source()
    result = execute(text)
    print(result.stdout + result.stderr, end="")
    if result.returncode:
        return result.returncode
    controls = {
        "remove orphan destruction": ("DeleteMapObject(candidate);", "(void)candidate;"),
        "accept foreign script": ("candidate->scriptId != OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT", "FALSE"),
        "ignore live presentation": ("state->spawns[j].object == candidate", "FALSE"),
        "ignore occupied slot": ("state->spawns[slot].active", "FALSE"),
        "ignore caller rejection": ("if (deleted < 0)", "if (FALSE)"),
        "drop deletion counter": ("while (deleted-- > 0)", "while (FALSE)"),
        "create off-screen Hop at landing": (
            "objectX = prepared->startup.startX;",
            "objectX = prepared->position.startX;",
        ),
    }
    for label, (old, new) in controls.items():
        if text.count(old) != 1:
            raise ValueError(f"control seam changed: {label}")
        mutant = execute(text.replace(old, new))
        if mutant.returncode != 1 or "spawn identity invariant failed" not in mutant.stderr:
            raise RuntimeError(f"known-bad control did not fail: {label}")
        print(f"PASS rejected known-bad: {label}")
    print("PASS S1 actual spawn boundary; native stubs, no gameplay claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
