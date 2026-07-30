#!/usr/bin/env python3

import re
import struct
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
OVERLAY_ID = 153
OVERLAY_BASE = 0x023BE400
OVERLAY_LIMIT = 0x023C0400
ROW_SIZE = 0x20


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"move-history verifier: {message}")


def align4(value: int) -> int:
    return (value + 3) & ~3


def parse_define(source: str, name: str) -> int:
    match = re.search(
        rf"^#define {re.escape(name)} (0x[0-9a-fA-F]+|[0-9]+)$",
        source,
        re.MULTILINE,
    )
    require(match is not None, f"{name} is missing")
    return int(match.group(1), 0)


def main() -> None:
    table = (REPO / "base/overarm9.bin").read_bytes()
    overlay = (REPO / "base/overlay/overlay_0153.bin").read_bytes()
    built = (
        REPO / "build/output_pokemon_move_history_overlay.bin"
    ).read_bytes()
    main_overlay = (REPO / "build/output.bin").read_bytes()

    require(len(table) % ROW_SIZE == 0, "y9 table is not row-aligned")
    require(len(main_overlay) <= 0x7A00, "resident overlay 129 exceeds 0x023E0000")
    require(overlay == built, "packaged overlay 153 differs from linked output")
    require(0 < len(overlay) <= OVERLAY_LIMIT - OVERLAY_BASE,
            "overlay 153 exceeds its 0x2000-byte reservation")

    offset = OVERLAY_ID * ROW_SIZE
    require(offset + ROW_SIZE <= len(table), "y9 has no overlay 153 row")
    row = struct.unpack_from("<8I", table, offset)
    require(row[0] == OVERLAY_ID, "overlay 153 row has the wrong ID")
    require(row[1] == OVERLAY_BASE, "overlay 153 has the wrong load address")
    require(row[2] == len(overlay), "overlay 153 y9 size differs from its file")
    require(
        row[3:] == (0, 0, 0, OVERLAY_ID, 0),
        "overlay 153 has unexpected BSS/init/file/compression metadata",
    )
    require(row[1] + row[2] <= OVERLAY_LIMIT,
            "overlay 153 crosses into the custom overlay band")

    linked_symbols = subprocess.check_output(
        [
            "arm-none-eabi-nm",
            str(REPO / "build/pokemon_move_history_overlay_linked.o"),
        ],
        text=True,
    )
    query_impl_match = re.search(
        r"^([0-9a-fA-F]+) T PokemonMoveHistory_QueryImpl$",
        linked_symbols,
        re.MULTILINE,
    )
    require(query_impl_match is not None, "Query implementation symbol is missing")
    query_instruction = struct.unpack_from("<H", overlay, 0x38)[0]
    require(
        query_instruction & 0xF800 == 0xE000,
        "Query entry is not a register-preserving Thumb branch",
    )
    query_delta = query_instruction & 0x7FF
    if query_delta & 0x400:
        query_delta -= 0x800
    query_target = OVERLAY_BASE + 0x38 + 4 + query_delta * 2
    require(
        query_target == (int(query_impl_match.group(1), 16) & ~1),
        "Query entry does not branch to QueryImpl",
    )

    for other_offset in range(0, len(table), ROW_SIZE):
        other = struct.unpack_from("<8I", table, other_offset)
        if other[0] == OVERLAY_ID or other[2] + other[3] == 0:
            continue
        other_start = other[1]
        other_end = other_start + other[2] + other[3]
        require(
            other_end <= OVERLAY_BASE or other_start >= OVERLAY_LIMIT,
            f"overlay {other[0]} overlaps overlay 153's resident reservation",
        )

    # Derive the worst boot-time OS_ARENA_MAIN low endpoint. Heap_InitSystem
    # allocates entropy padding, metadata, and four fixed heaps; system init
    # then allocates four task queues and the ROM FNT table.
    stock_overlay_end = max(
        row_data[1] + row_data[2] + row_data[3]
        for row_offset in range(0, min(len(table), 129 * ROW_SIZE), ROW_SIZE)
        for row_data in [struct.unpack_from("<8I", table, row_offset)]
    )
    save_constants = (REPO / "include/constants/save.h").read_text()
    full_save_size = parse_define(save_constants, "FULL_SAVE_SIZE")
    heap3_size = parse_define(save_constants, "NEW_HEAP3_SIZE")
    arm9 = (REPO / "base/arm9.bin").read_bytes()
    require(
        struct.unpack_from("<I", arm9, 0x020F62AC - 0x02000000)[0]
            == full_save_size,
        "patched save heap size differs from FULL_SAVE_SIZE",
    )
    require(
        struct.unpack_from("<I", arm9, 0x020F62BC - 0x02000000)[0]
            == heap3_size,
        "patched heap 3 size differs from NEW_HEAP3_SIZE",
    )
    arena_end = align4(stock_overlay_end + 0x100)
    usable_heaps = 4 + 24
    total_heap_ids = 166
    heap_metadata_size = (
        (usable_heaps + 1) * 4
        + usable_heaps * 4
        + usable_heaps * 4
        + total_heap_ids * 2
        + total_heap_ids
    )
    arena_end = align4(arena_end + heap_metadata_size)
    for heap_size in (0xD200, full_save_size, 0x10, heap3_size):
        arena_end = align4(arena_end + heap_size)
    for task_count in (160, 32, 32, 4):
        arena_end = align4(arena_end + task_count * (28 + 4) + 52)
    header = (REPO / "base/header.bin").read_bytes()
    fnt_size = struct.unpack_from("<I", header, 0x44)[0]
    arena_end = align4(arena_end + fnt_size)
    require(
        arena_end <= OVERLAY_BASE,
        f"boot arena allocations reach 0x{arena_end:08X}",
    )

    startup = (REPO / "armips/asm/syntheticoverlay.s").read_text()
    require("mov r1, #153" in startup, "startup does not request overlay 153")
    require("0x02007188|1" in startup,
            "startup does not use the untracked no-init loader")

    rom_ld = (REPO / "rom.ld").read_text()
    for name, api_offset in (
        ("Init", 0x00),
        ("Load", 0x08),
        ("Reset", 0x10),
        ("CaptureSnapshot", 0x18),
        ("Seed", 0x20),
        ("RecordMove", 0x28),
        ("RecordSnapshot", 0x30),
        ("Query", 0x38),
        ("CommitIfDirty", 0x40),
        ("LoadAndSeedParty", 0x48),
        ("PrepareSave", 0x50),
        ("FinishSave", 0x58),
        ("CancelSave", 0x60),
        ("WriteSaveNow", 0x68),
    ):
        require(
            f"PokemonMoveHistory_{name} = "
            f"0x{OVERLAY_BASE + api_offset:08X} | 1;"
            in rom_ld,
            f"{name} ABI alias is missing or moved",
        )
    save_trampoline = (
        REPO / "asm/pokemon_move_history_trampoline.s"
    ).read_text()
    require(
        ".word 0x023BE471" in save_trampoline,
        "SaveGameNormal resident trampoline is missing or moved",
    )
    core_symbols = subprocess.check_output(
        ["arm-none-eabi-nm", str(REPO / "build/linked.o")],
        text=True,
    )
    match = re.search(
        r"^([0-9a-fA-F]+) T SaveGameNormal$",
        core_symbols,
        re.MULTILINE,
    )
    require(match is not None, "SaveGameNormal hook symbol was not generated")
    save_game_normal = int(match.group(1), 16) | 1
    hook_offset = 0x020273F0 - 0x02000000
    require(
        arm9[hook_offset:hook_offset + 4] == bytes.fromhex("00 49 08 47"),
        "SaveGameNormal hook is not the expected Thumb literal trampoline",
    )
    require(
        struct.unpack_from("<I", arm9, hook_offset + 4)[0]
            == save_game_normal,
        "SaveGameNormal hook does not target the resident trampoline",
    )

    print(
        "move-history static gate: "
        f"overlay153=0x{OVERLAY_BASE:08X}.."
        f"0x{OVERLAY_BASE + len(overlay):08X} "
        f"arena=0x{arena_end:08X} "
        f"overlay129=0x{len(main_overlay):X}/0x7A00"
    )


if __name__ == "__main__":
    main()
