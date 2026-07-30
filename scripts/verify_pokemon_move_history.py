#!/usr/bin/env python3

import argparse
import re
import struct
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
OVERLAY_ID = 153
OVERLAY_BASE = 0x023BE400
OVERLAY_LIMIT = 0x023C0400
OVERLAY_GUARD = 0x1000
MAIN_RAM_START = 0x02000000
MAIN_ARENA_HIGH = 0x023E0000
DTCM_START = 0x027E0000
DTCM_END = DTCM_START + 0x4000
ROW_SIZE = 0x20


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"move-history verifier: {message}")


def align4(value: int) -> int:
    return (value + 3) & ~3


def ranges_overlap(
    first_start: int,
    first_end: int,
    second_start: int,
    second_end: int,
) -> bool:
    return first_start < second_end and second_start < first_end


def parse_define(source: str, name: str) -> int:
    match = re.search(
        rf"^#define {re.escape(name)} (0x[0-9a-fA-F]+|[0-9]+)$",
        source,
        re.MULTILINE,
    )
    require(match is not None, f"{name} is missing")
    return int(match.group(1), 0)


def checked_slice(
    data: bytes,
    offset: int,
    size: int,
    description: str,
) -> bytes:
    require(
        offset >= 0 and size >= 0 and offset + size <= len(data),
        f"{description} lies outside the completed ROM",
    )
    return data[offset:offset + size]


def read_u32(data: bytes, offset: int, description: str) -> int:
    require(offset >= 0 and offset + 4 <= len(data),
            f"{description} is outside its binary")
    return struct.unpack_from("<I", data, offset)[0]


def final_overlay(
    rom: bytes,
    fat: bytes,
    row: tuple[int, ...],
) -> bytes:
    file_id = row[6]
    entry_offset = file_id * 8
    require(entry_offset + 8 <= len(fat),
            f"overlay {row[0]} FAT entry {file_id} is missing")
    file_start, file_end = struct.unpack_from("<II", fat, entry_offset)
    require(file_start < file_end,
            f"overlay {row[0]} FAT entry is empty or reversed")
    return checked_slice(
        rom,
        file_start,
        file_end - file_start,
        f"overlay {row[0]} file",
    )


def serial_compare(first: int, second: int) -> int:
    difference = (first - second) & 0xFFFFFFFF
    require(
        difference != 0x80000000,
        "serial comparison fixture used the excluded half-range",
    )
    if difference == 0:
        return 0
    return 1 if difference < 0x80000000 else -1


def source_contracts() -> None:
    history_source = (
        REPO
        / "src/pokemon_move_history_overlay/pokemon_move_history.c"
    ).read_text()
    save_source = (REPO / "src/save.c").read_text()

    for first, second, expected in (
        (0, 0, 0),
        (5, 4, 1),
        (4, 5, -1),
        (0, 0xFFFFFFFF, 1),
        (1, 0xFFFFFFFE, 1),
        (0xFFFFFFFF, 1, -1),
        (0xFFFFFF00, 0x100, -1),
    ):
        require(
            serial_compare(first, second) == expected,
            f"serial comparison fixture failed for {first:#x}/{second:#x}",
        )
    compare_match = re.search(
        r"static int PokemonMoveHistory_CompareCounters.*?^}",
        history_source,
        re.MULTILINE | re.DOTALL,
    )
    require(compare_match is not None, "counter comparison implementation is missing")
    compare_source = compare_match.group(0)
    require(
        "difference = first - second;" in compare_source
        and "difference < 0x80000000" in compare_source
        and "2^31" in compare_source,
        "counter comparison is not documented modular serial arithmetic",
    )
    require(
        "first == 0xFFFFFFFF" not in compare_source
        and "second == 0xFFFFFFFF" not in compare_source,
        "obsolete single-wrap counter special case remains",
    )

    async_match = re.search(
        r"int Save_WriteFileAsync\(.*?^}",
        save_source,
        re.MULTILINE | re.DOTALL,
    )
    require(async_match is not None, "Save_WriteFileAsync is missing")
    require(
        "pokemonMoveHistorySaveReady" not in async_match.group(0)
        and "WRITE_STATUS_TOTAL_FAIL" not in async_match.group(0),
        "asynchronous primary saving is still gated by move history",
    )
    now_match = re.search(
        r"int PokemonMoveHistory_WriteSaveNowImpl\(.*?^}",
        history_source,
        re.MULTILINE | re.DOTALL,
    )
    require(now_match is not None, "WriteSaveNow implementation is missing")
    require(
        "pokemonMoveHistorySaveReady" not in now_match.group(0)
        and "WRITE_STATUS_TOTAL_FAIL" not in now_match.group(0),
        "synchronous primary saving is still gated by move history",
    )
    require(
        "(void)PokemonMoveHistory_PrepareSave(saveData);" in save_source,
        "primary save initialization does not explicitly ignore sidecar failure",
    )
    require(
        "saveData->pokemonMoveHistoryDirty = TRUE;"
        in history_source
        and "PokemonMoveHistory_LoadForCounter(\n"
            "            saveData,\n"
            "            saveData->saveCounter - 1);"
        in history_source,
        "sidecar failure retry/dirty recovery contract is missing",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the packaged move-history sidecar integration")
    parser.add_argument(
        "--rom",
        required=True,
        type=Path,
        help="completed, repacked Nintendo DS ROM",
    )
    args = parser.parse_args()
    rom_path = args.rom.resolve()
    rom = rom_path.read_bytes()

    arm9_offset = read_u32(rom, 0x20, "ARM9 ROM offset")
    arm9_ram = read_u32(rom, 0x28, "ARM9 RAM address")
    arm9_size = read_u32(rom, 0x2C, "ARM9 size")
    fnt_offset = read_u32(rom, 0x40, "FNT offset")
    fnt_size = read_u32(rom, 0x44, "FNT size")
    fat_offset = read_u32(rom, 0x48, "FAT offset")
    fat_size = read_u32(rom, 0x4C, "FAT size")
    y9_offset = read_u32(rom, 0x50, "y9 offset")
    y9_size = read_u32(rom, 0x54, "y9 size")

    arm9 = checked_slice(rom, arm9_offset, arm9_size, "ARM9")
    checked_slice(rom, fnt_offset, fnt_size, "FNT")
    fat = checked_slice(rom, fat_offset, fat_size, "FAT")
    table = checked_slice(rom, y9_offset, y9_size, "y9 table")
    require(len(fat) % 8 == 0, "final FAT is not entry-aligned")
    require(len(table) % ROW_SIZE == 0, "final y9 table is not row-aligned")
    require(arm9_ram == MAIN_RAM_START, "final ARM9 has an unexpected RAM base")

    rows = [
        struct.unpack_from("<8I", table, offset)
        for offset in range(0, len(table), ROW_SIZE)
    ]
    require(
        all(row[0] == index for index, row in enumerate(rows)),
        "final y9 overlay IDs are not dense and ordered",
    )
    require(OVERLAY_ID < len(rows), "final y9 has no overlay 153 row")

    row = rows[OVERLAY_ID]
    overlay = final_overlay(rom, fat, row)
    built = (
        REPO / "build/output_pokemon_move_history_overlay.bin"
    ).read_bytes()
    require(overlay == built,
            "final ROM overlay 153 differs from linked output")
    require(
        row == (
            OVERLAY_ID,
            OVERLAY_BASE,
            len(overlay),
            0,
            0,
            0,
            OVERLAY_ID,
            0,
        ),
        "final overlay 153 row has unexpected metadata",
    )
    require(
        0 < len(overlay)
        and OVERLAY_BASE + len(overlay) + OVERLAY_GUARD <= OVERLAY_LIMIT,
        "overlay 153 exceeds its reservation or upper growth guard",
    )

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
    candidate_impl_match = re.search(
        r"^([0-9a-fA-F]+) T PokemonMoveRelearn_BuildCandidatesImpl$",
        linked_symbols,
        re.MULTILINE,
    )
    require(
        candidate_impl_match is not None,
        "move-relearn candidate implementation symbol is missing",
    )
    candidate_instruction = struct.unpack_from("<H", overlay, 0x78)[0]
    require(
        candidate_instruction & 0xF800 == 0xE000,
        "candidate entry is not a register-preserving Thumb branch",
    )
    candidate_delta = candidate_instruction & 0x7FF
    if candidate_delta & 0x400:
        candidate_delta -= 0x800
    candidate_target = OVERLAY_BASE + 0x78 + 4 + candidate_delta * 2
    require(
        candidate_target
        == (int(candidate_impl_match.group(1), 16) & ~1),
        "candidate entry does not branch to BuildCandidatesImpl",
    )

    for other in rows:
        other_size = other[2] + other[3]
        if other[0] == OVERLAY_ID or other_size == 0:
            continue
        other_start = other[1]
        other_end = other_start + other_size
        require(
            MAIN_RAM_START <= other_start < other_end <= MAIN_ARENA_HIGH,
            f"overlay {other[0]} lies outside audited ARM9 main RAM",
        )
        require(
            not ranges_overlap(
                other_start,
                other_end,
                OVERLAY_BASE,
                OVERLAY_LIMIT,
            ),
            f"overlay {other[0]} overlaps overlay 153's reservation",
        )

    save_constants = (REPO / "include/constants/save.h").read_text()
    full_save_size = parse_define(save_constants, "FULL_SAVE_SIZE")
    heap3_size = parse_define(save_constants, "NEW_HEAP3_SIZE")
    require(
        heap3_size == 0x10E000
        and 0x110000 - heap3_size == 0x2000,
        "heap 3 does not explicitly reserve 0x2000 for overlay 153",
    )

    def arm9_word(address: int, description: str) -> int:
        return read_u32(arm9, address - arm9_ram, description)

    require(
        arm9_word(0x020F62AC, "patched save heap size")
        == full_save_size,
        "patched save heap size differs from FULL_SAVE_SIZE",
    )
    require(
        arm9_word(0x020F62BC, "patched heap 3 size") == heap3_size,
        "patched heap 3 size differs from NEW_HEAP3_SIZE",
    )
    require(
        arm9_word(0x020D2C5C, "main arena low literal") == 0x0226EC40,
        "final ARM9 main arena low changed",
    )
    require(
        arm9_word(0x020D2BB0, "main arena high literal")
        == MAIN_ARENA_HIGH,
        "final ARM9 main arena high changed",
    )
    require(
        arm9_word(0x02000930, "DTCM stack base literal") == DTCM_START,
        "final ARM9 DTCM stack base changed",
    )

    stock_overlay_end = max(
        stock[1] + stock[2] + stock[3]
        for stock in rows[:129]
    )
    require(stock_overlay_end == 0x0226EC40,
            "stock overlay arena endpoint changed")
    archive_start = align4(stock_overlay_end + 0x100)
    usable_heaps = 4 + 24
    total_heap_ids = 166
    heap_metadata_size = (
        (usable_heaps + 1) * 4
        + usable_heaps * 4
        + usable_heaps * 4
        + total_heap_ids * 2
        + total_heap_ids
    )
    archive_start = align4(archive_start + heap_metadata_size)
    for heap_size in (0xD200, full_save_size, 0x10, heap3_size):
        archive_start = align4(archive_start + heap_size)
    for task_count in (160, 32, 32, 4):
        archive_start = align4(
            archive_start + task_count * (28 + 4) + 52)

    archive_size = (fnt_size + fat_size + 0x3F) & ~0x1F
    archive_end = archive_start + archive_size
    cached_fnt_start = (archive_start + 0x1F) & ~0x1F
    cached_fnt_end = cached_fnt_start + fnt_size
    cached_fat_start = cached_fnt_end
    cached_fat_end = cached_fat_start + fat_size
    require(
        cached_fat_end <= archive_end,
        "FNT/FAT caches exceed the SDK archive allocation",
    )
    require(
        archive_end + OVERLAY_GUARD <= OVERLAY_BASE,
        f"boot FNT+FAT allocation reaches 0x{archive_end:08X}",
    )

    arm9_end = arm9_ram + arm9_size
    require(
        not ranges_overlap(
            arm9_ram,
            arm9_end,
            OVERLAY_BASE,
            OVERLAY_LIMIT,
        ),
        "final ARM9 load image overlaps overlay 153",
    )
    require(
        OVERLAY_LIMIT <= MAIN_ARENA_HIGH
        and not ranges_overlap(
            DTCM_START,
            DTCM_END,
            OVERLAY_BASE,
            OVERLAY_LIMIT,
        ),
        "overlay 153 crosses the main arena or DTCM stack boundary",
    )

    require(129 < len(rows), "final y9 has no overlay 129 row")
    row129 = rows[129]
    overlay129 = final_overlay(rom, fat, row129)
    generated_overlay129 = (
        REPO / "base/overlay/overlay_0129.bin"
    ).read_bytes()
    main_overlay = (REPO / "build/output.bin").read_bytes()
    require(
        overlay129 == generated_overlay129,
        "final ROM overlay 129 differs from the generated package",
    )
    require(
        row129 == (
            129,
            0x023D8000,
            len(overlay129),
            0,
            0,
            0,
            129,
            0,
        ),
        "final overlay 129 row has unexpected metadata",
    )
    require(
        len(overlay129) == 0x600 + len(main_overlay)
        and overlay129[0x600:] == main_overlay,
        "final overlay 129 does not contain the linked resident core",
    )
    require(
        len(main_overlay) <= 0x7A00
        and row129[1] + len(overlay129) <= MAIN_ARENA_HIGH,
        "resident overlay 129 exceeds the ARM9 main arena",
    )

    startup = (REPO / "armips/asm/syntheticoverlay.s").read_text()
    require("mov r1, #153" in startup,
            "startup does not request overlay 153")
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
    require(
        "PokemonMoveRelearn_BuildCandidates = 0x023BE478 | 1;" in rom_ld,
        "move-relearn candidate ABI alias is missing or moved",
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
    hook_offset = 0x020273F0 - arm9_ram
    require(
        arm9[hook_offset:hook_offset + 4] == bytes.fromhex("00 49 08 47"),
        "SaveGameNormal hook is not the expected Thumb literal trampoline",
    )
    require(
        struct.unpack_from("<I", arm9, hook_offset + 4)[0]
        == save_game_normal,
        "SaveGameNormal hook does not target the resident trampoline",
    )

    source_contracts()
    print(
        "move-history post-package gate: "
        f"rom={rom_path} "
        f"fnt=0x{fnt_size:X} fat=0x{fat_size:X} "
        f"archive=0x{archive_start:08X}..0x{archive_end:08X} "
        f"fnt-cache=0x{cached_fnt_start:08X}.."
        f"0x{cached_fnt_end:08X} "
        f"fat-cache=0x{cached_fat_start:08X}.."
        f"0x{cached_fat_end:08X} "
        f"overlay153=0x{OVERLAY_BASE:08X}.."
        f"0x{OVERLAY_BASE + len(overlay):08X} "
        f"overlay129=0x{len(overlay129):X}/0x8000"
    )


if __name__ == "__main__":
    main()
