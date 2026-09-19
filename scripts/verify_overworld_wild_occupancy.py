#!/usr/bin/env python3
"""Actual-C occupancy parity. Host checks are not runtime behavior proof."""
from pathlib import Path
import argparse
import os
import shlex
import struct
import subprocess
import tempfile

from verify_overworld_spawn_identity import function

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
SERVICE = ROOT / "src/pokemon_move_history_overlay/overworld_wild_occupancy.c"
FIXTURE = ROOT / "tools/overworld/fixtures/wild_occupancy_harness.c"
NAMES = ("IsTileOccupiedByObject", "IsTileOccupiedByNonPlayerObject", "IsTileOccupiedOnSurface")
ENTRY = 0x023C0184
SYMBOL = "OverworldWildOccupancy_Query"


def checked(value, reason):
    if not value:
        raise ValueError("Wild occupancy package: " + reason)


def binding_contract(service, caller):
    checked(service is not None and service[0] == ENTRY | 1
            and 0 < service[1] <= 636 and service[2] == "FUNC"
            and service[3] not in ("ABS", "UND"), "resident Thumb entry differs")
    checked(caller == (ENTRY | 1, 0, "FUNC", "ABS"), "caller typed Thumb import differs")


def code_contract(linked, packaged):
    checked(bool(linked) and linked == packaged, "packaged native bytes differ")


def package_controls():
    good = (ENTRY | 1, 214, "FUNC", "4")
    imported = (ENTRY | 1, 0, "FUNC", "ABS")
    binding_contract(good, imported)
    for service, caller in ((None, imported), ((ENTRY, 214, "FUNC", "4"), imported),
            ((ENTRY | 1, 0, "FUNC", "4"), imported),
            ((ENTRY | 1, 637, "FUNC", "4"), imported),
            ((ENTRY | 1, 214, "FUNC", "ABS"), imported),
            (good, (ENTRY, 0, "FUNC", "ABS")),
            (good, (ENTRY | 1, 0, "NOTYPE", "ABS"))):
        try:
            binding_contract(service, caller)
        except ValueError:
            continue
        raise AssertionError("invalid resident occupancy binding accepted")
    for left, right in ((b"", b""), (b"a", b"b"), (b"ab", b"a")):
        try:
            code_contract(left, right)
        except ValueError:
            continue
        raise AssertionError("invalid occupancy body accepted")
    print("PASS 10 occupancy package negative controls")


def verify_package(rom_path):
    from verify_pokemon_move_history_capture import elf_bytes_at, elf_helper_bindings, direct_thumb_calls
    host = ROOT / "build/pokemon_move_history_overlay_linked.o"
    wild = ROOT / "build/overworld_wild_spawns_overlay_linked.o"
    service = elf_helper_bindings(host, (SYMBOL,)).get(SYMBOL)
    binding_contract(service, elf_helper_bindings(wild, (SYMBOL,)).get(SYMBOL))
    rom = Path(rom_path).read_bytes()
    checked(len(rom) >= 0x60, "ROM header missing")
    fat, fat_size, y9, y9_size = struct.unpack_from("<4I", rom, 0x48)
    checked(fat_size % 8 == 0 and fat + fat_size <= len(rom)
            and y9_size % 32 == 0 and y9 + y9_size <= len(rom), "ROM tables differ")

    def overlay(number, base):
        rows = [struct.unpack_from("<8I", rom, position)
                for position in range(y9, y9 + y9_size, 32)
                if struct.unpack_from("<I", rom, position)[0] == number]
        checked(len(rows) == 1, "overlay absent or duplicated")
        _, actual, size, bss, _, _, file_id, flags = rows[0]
        checked(actual == base and not flags & 0x01000000 and file_id < fat_size // 8,
                "overlay address or encoding differs")
        start, end = struct.unpack_from("<II", rom, fat + file_id * 8)
        checked(start <= end <= len(rom) and end - start == size, "overlay file bounds differ")
        checked(base + size + bss <= {149: 0x023D8000, 151: 0x023C8000,
                152: 0x023C22A0, 153: 0x023C0400}[number],
                "native reservation exceeded")
        return rom[start:end]

    host_image = overlay(153, 0x023BE400)
    code_contract(elf_bytes_at(host, ENTRY, service[1]),
                  host_image[ENTRY - 0x023BE400:ENTRY - 0x023BE400 + service[1]])
    wild_image = overlay(149, 0x023CCFD8)
    symbols = tuple("OverworldWildSpawns_" + name for name in NAMES)
    bindings = elf_helper_bindings(wild, symbols)
    for name in symbols:
        symbol = bindings.get(name)
        checked(symbol is not None and symbol[2] == "FUNC" and symbol[0] & 1 and symbol[1] > 0,
                name + " wrapper missing")
        address, size = symbol[0] & ~1, symbol[1]
        code_contract(elf_bytes_at(wild, address, size),
                      wild_image[address - 0x023CCFD8:address - 0x023CCFD8 + size])
        assembly = subprocess.check_output(["arm-none-eabi-objdump", "-d",
            f"--start-address={address}", f"--stop-address={address + size}", str(wild)], text=True)
        calls = [call for call in direct_thumb_calls(assembly) if call[2] == ENTRY]
        checked(len(calls) == 1 and calls[0][1] == "bl", name + " must call typed native host once")
    print(f"PASS S2 occupancy: 3 native wrappers, hosted Thumb body {service[1]} bytes")
    # Ordinary spawn work crosses one queue now. Its guard and the unchanged
    # spatial predicates share existing resident tails, not another owner.
    groups = (
        (153, 0x023BE400, host, (
            ("OverworldWildSpawnGuard_Read", 0x023C025C, 0x023C034C),
            ("OverworldWildSpawnGuard_IsNearActiveSpawn", 0x023C034C, 0x023C03D0),
            ("OverworldWildSpawnGuard_IsSurfBehavior", 0x023C03D0, 0x023C0400))),
        (151, 0x023C4000, ROOT / "build/overworld_wild_helper_overlay_linked.o", (
            ("OverworldSpawnSpatial_IsPlayerTile", 0x023C7F60, 0x023C7F98),
            ("OverworldSpawnSpatial_IsPlayerFrontTile", 0x023C7F98, 0x023C8000))),
        (152, 0x023C0400, ROOT / "build/overworld_follower_selector_overlay_linked.o", (
            ("OverworldSpawnSpatial_IsCurrentMapObject", 0x023C2200, 0x023C2230),
            ("OverworldSpawnSpatial_DistanceFromPlayer", 0x023C2230, 0x023C2264),
            ("OverworldSpawnSpatial_IsObjectOnPlayerTile", 0x023C2264, 0x023C22A0))),
    )
    for number, base, linked, entries in groups:
        image = overlay(number, base)
        names = tuple(row[0] for row in entries)
        definitions = elf_helper_bindings(linked, names)
        imports = elf_helper_bindings(wild, names)
        for name, address, end in entries:
            definition = definitions.get(name)
            checked(definition is not None and definition[0] == address | 1
                    and 0 < definition[1] <= end - address
                    and definition[2] == "FUNC" and definition[3] not in ("ABS", "UND"),
                    name + " resident slot or Thumb type differs")
            checked(imports.get(name) == (address | 1, 0, "FUNC", "ABS"),
                    name + " Wild Thumb import differs")
            code_contract(elf_bytes_at(linked, address, definition[1]),
                          image[address - base:address - base + definition[1]])
    print("PASS S2 queued spawn: 8 bounded resident Thumb entries match ROM and Wild imports")


def source():
    product = PRODUCT.read_text()
    pieces = []
    if SERVICE.exists():
        pieces.append(function(SERVICE.read_text(), "OverworldWildOccupancy_Query", "BOOL"))
    else:
        for name in ("IsMankeyTreeTopProxyObjectId", "IsIgnoredVisualObjectId"):
            pieces.append(function(product, "OverworldWildSpawns_" + name, "BOOL"))
    pieces.extend(function(product, "OverworldWildSpawns_" + name, "BOOL") for name in NAMES)
    return FIXTURE.read_text().replace("/* @ACTUAL_C@ */", "\n".join(pieces))


def host_checks():
    with tempfile.TemporaryDirectory(prefix="wild-occupancy-") as directory:
        path = Path(directory)
        (path / "test.c").write_text(source())
        for disabled in (False, True):
            command = shlex.split(os.environ.get("HOST_CC", "cc")) + ["-std=c99", "-Wall", "-Wextra", "-Werror"]
            if disabled:
                command += ["-DDISABLE_FOLLOWER_POKEMON"]
            subprocess.run(command + [str(path / "test.c"), "-o", str(path / "test")], check=True)
            subprocess.run([str(path / "test")], check=True)


def negative_controls():
    text = source()
    mutations = (
        ("object != collisionIgnoredObject", "TRUE"),
        ("object != ignoredObject", "TRUE"),
        ("object != player", "TRUE"),
        ("&& (s32)player->posVec[1] == targetBaseY", "&& TRUE"),
        ("object->id != OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID", "TRUE"),
        ("OW_WILD_PERF_INC(sOverworldWildPerfTargetScansThisFrame);", ";"),
    )
    with tempfile.TemporaryDirectory(prefix="wild-occupancy-controls-") as directory:
        path = Path(directory)
        for old, new in mutations:
            checked(old in text, "mutation target missing")
            (path / "test.c").write_text(text.replace(old, new, 1))
            subprocess.run(shlex.split(os.environ.get("HOST_CC", "cc")) + ["-std=c99", str(path / "test.c"),
                            "-o", str(path / "test")], check=True, capture_output=True)
            result = subprocess.run([str(path / "test")], capture_output=True)
            checked(result.returncode != 0, "wrong production predicate escaped parity matrix")
    print("PASS 6 actual-C occupancy mutation controls")


def abi_checks():
    text = '''#include "overworld_wild_occupancy.h"
#include "map_events_internal.h"
typedef char modes[(OVERWORLD_WILD_OCCUPANCY_OBJECTS == 0
 && OVERWORLD_WILD_OCCUPANCY_NONPLAYER == 1 && OVERWORLD_WILD_OCCUPANCY_SURFACE == 2
 && OVERWORLD_WILD_OCCUPANCY_SURFACE_PLAYER == 3 && OW_WILD_MAX_SPAWNS == 10
 && OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID == 0xF0
 && OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START == 0xB0
 && OW_WILD_FOLLOWER_OBJECT_ID == 253) ? 1 : -1];
typedef char coords[(__builtin_offsetof(LocalMapObject, xCurr) == 0x64
 && __builtin_offsetof(LocalMapObject, yCurr) == 0x6C
 && sizeof(((LocalMapObject*)0)->xCurr) == 4) ? 1 : -1];
BOOL (*const query)(FieldSystem*,LocalMapObject*,LocalMapObject*,int,int,s32,int)
 = OverworldWildOccupancy_Query;
'''
    with tempfile.TemporaryDirectory(prefix="wild-occupancy-abi-") as directory:
        path = Path(directory)
        (path / "abi.c").write_text(text)
        subprocess.run(["arm-none-eabi-gcc", "-w", "-Werror=incompatible-pointer-types",
            "-mthumb", "-mcpu=arm7tdmi", "-I", str(ROOT / "include"), "-c",
            str(path / "abi.c"), "-o", str(path / "abi.o")], check=True)
    print("PASS actual ARM occupancy header/mode/native-coordinate ABI")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-only", action="store_true")
    parser.add_argument("--rom", type=Path)
    args = parser.parse_args()
    if args.package_only:
        if args.rom is None:
            parser.error("--package-only requires --rom")
        verify_package(args.rom)
    else:
        host_checks()
        negative_controls()
        abi_checks()
        package_controls()


if __name__ == "__main__":
    main()
