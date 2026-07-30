#!/usr/bin/env python3
"""Task-3 static, host-fixture, relocation, and final hook verification."""

from __future__ import annotations

import argparse
import re
import struct
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
OVERLAY_BASE = 0x023BE400
OVERLAY_LIMIT = 0x1000


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"move-history capture verification failed: {message}")


def function_body(source: str, name: str) -> str:
    match = re.search(rf"\b{name}\s*\([^;]*?\)\s*\{{", source, re.S)
    require(match is not None, f"{name} body is missing")
    start = match.start()
    cursor = match.end()
    depth = 1
    while cursor < len(source) and depth:
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    require(depth == 0, f"{name} body is unterminated")
    return source[start:cursor]


def ordered(body: str, tokens: list[str], label: str) -> None:
    cursor = 0
    for token in tokens:
        found = body.find(token, cursor)
        require(found >= 0, f"{label} is missing ordered token {token!r}")
        cursor = found + len(token)


def source_contracts() -> None:
    header = (REPO / "include/pokemon_move_history.h").read_text()
    history = (
        REPO / "src/pokemon_move_history_overlay/pokemon_move_history.c"
    ).read_text()
    pokemon = (REPO / "src/pokemon.c").read_text()
    party_menu = (REPO / "src/party_menu.c").read_text()
    entry = (REPO / "asm/pokemon_move_history_overlay/entry.s").read_text()
    linker = (
        REPO / "src/pokemon_move_history_overlay/linker.ld"
    ).read_text()
    rom_ld = (REPO / "rom.ld").read_text()
    patches = (
        REPO / "armips/asm/pokemon_move_history_capture.s"
    ).read_text()
    hooks = (REPO / "hooks").read_text()
    makefile = (REPO / "Makefile").read_text()
    config = (REPO / "include/config.h").read_text()

    for api in (
        "PokemonMoveHistory_ReplaceMove",
        "PokemonMoveHistory_DeleteMoveSlot",
    ):
        require(
            re.search(rf"\bLONG_CALL\s+{api}\s*\(", header) is not None,
            f"{api} is not a typed long-call API",
        )

    append = function_body(history, "PokemonMoveHistory_AppendMove")
    require(
        "PokemonMoveHistory_IsRecordableMove(move)" in append,
        "history append bypasses the central valid/implemented predicate",
    )
    predicate = function_body(history, "PokemonMoveHistory_IsRecordableMove")
    for token in ("MOVE_NONE", "NUM_OF_MOVES", "IsMoveUnimplemented(move)"):
        require(token in predicate, f"recordable-move predicate misses {token}")
    require(
        re.search(
            r"^\s*#\s*define\s+BLOCK_LEARNING_UNIMPLEMENTED_MOVES(?:\s|$)",
            config,
            re.MULTILINE,
        )
        is not None,
        "host unimplemented-move fixture requires the runtime policy enabled",
    )

    replace = function_body(history, "PokemonMoveHistory_ReplaceMoveImpl")
    ordered(
        replace,
        [
            "PokemonMoveHistory_IsRecordableMove(move)",
            "PokemonMoveHistory_CaptureSnapshotImpl",
            "before.moves[slot] == move",
            "SaveBlock2_get()",
            "PokemonMoveHistory_ObserveSnapshot",
            "SetBoxMonData(pokemon, MON_DATA_MOVE1 + slot",
            "GetBoxMonData(pokemon, MON_DATA_MOVE1 + slot",
            "before.moves[slot] = move",
            "PokemonMoveHistory_AppendMove",
        ],
        "replacement transaction",
    )
    require(
        "if (!PokemonMoveHistory_CaptureSnapshotImpl" in replace,
        "snapshot failure does not stop replacement before mutation",
    )
    require(
        "if (before.moves[slot] == move)" in replace,
        "duplicate/no-op replacement is not stopped before mutation",
    )
    require(
        replace.count("SaveBlock2_get()") == 1,
        "replacement does not resolve exactly one current save per transaction",
    )
    delete = function_body(history, "PokemonMoveHistory_DeleteMoveSlotImpl")
    ordered(
        delete,
        [
            "PokemonMoveHistory_SeedImpl",
            "SaveBlock2_get()",
            "MonDeleteMoveSlot_Original",
        ],
        "move deletion transaction",
    )

    level_up = function_body(pokemon, "MonTryLearnMoveOnLevelUp")
    ordered(
        level_up,
        [
            "ret = TryAppendMonMove(mon, *sp0);",
            "ret != (u16)-1u",
            "ret != (u16)-2u",
            "ret != MOVE_NONE",
            "SaveBlock2_get()",
            "PokemonMoveHistory_RecordMove",
        ],
        "level-up append",
    )

    learn_slot = function_body(party_menu, "PartyMenu_LearnMoveToSlot")
    require(
        learn_slot.count("PokemonMoveHistory_ReplaceMove(") == 1,
        "TM/HM and rare-candy replacement do not share one transaction owner",
    )
    require(
        "SetMonData(" not in learn_slot,
        "party-menu replacement still mutates outside the central transaction",
    )

    seed_party = function_body(history, "PokemonMoveHistory_SeedParty")
    seed_party_code = re.sub(r"/\*.*?\*/|//[^\n]*", "", seed_party, flags=re.S)
    require(
        "Party_GetCount(party)" in seed_party_code
        and "Party_GetMonByIndex(party, i)" in seed_party_code,
        "party reconciliation does not use canonical accessors",
    )
    for forbidden in (
        "party->count",
        "party->members",
        "sizeof(struct PartyPokemon)",
        "0xEC",
        "0xF0",
    ):
        require(
            forbidden not in seed_party_code,
            f"party reconciliation contains forbidden stride/count access {forbidden}",
        )
    load_boundary = function_body(
        history,
        "PokemonMoveHistory_LoadAndSeedPartyImpl",
    )
    require(
        "PokemonMoveHistory_SeedParty" not in load_boundary,
        "party reconciliation runs before the active save is boot-stable",
    )
    save_boundary = function_body(
        history,
        "PokemonMoveHistory_PrepareSaveImpl",
    )
    ordered(
        save_boundary,
        [
            "PokemonMoveHistory_SeedParty(saveData);",
            "PokemonMoveHistory_CommitIfDirtyImpl(saveData);",
        ],
        "normal-save ownership reconciliation",
    )

    for offset, entry_name, alias_name in (
        (0x80, "ReplaceMove", "PokemonMoveHistory_ReplaceMove"),
        (0x88, "DeleteMoveSlot", "PokemonMoveHistory_DeleteMoveSlot"),
    ):
        require(
            f"MoveHistoryEntry_{entry_name}" in entry
            and f"ORIGIN(rom) + 0x{offset:X}" in linker
            and f"{alias_name} = 0x{OVERLAY_BASE + offset:08X} | 1;"
            in rom_ld,
            f"{entry_name} fixed overlay ABI is incomplete",
        )

    require(
        "PokemonMoveHistory_SetPartyMove" not in hooks,
        "obsolete full PartyMonSetMoveInSlot hook remains",
    )
    for address in (
        "0x0204DCCC",
        "0x020542E0",
        "0x020769F0",
        "0x02246344",
        "0x021E6158",
    ):
        require(address in patches, f"confirmed commit patch {address} is missing")
    for forbidden in (
        "021E60D8",  # yes/no prompt
        "022462D8",  # battle cancel/give-up neighborhood
        "PartyMenu_CheckCanLearnTMHMMove",
    ):
        require(
            forbidden not in patches,
            f"preview/cancel path unexpectedly owns history: {forbidden}",
        )
    reminder_patch = patches[
        patches.index(".org 0x021E6158"):patches.index(".endarea", patches.index(".org 0x021E6158"))
    ]
    require(
        "bl PokemonMoveHistory_ReplaceMove" in reminder_patch
        and re.search(r"\n\s+nop\s*(?:\n|$)", reminder_patch) is not None,
        "Move Reminder replacement does not fill the complete 14-byte span",
    )
    for helper, source in (
        ("PokemonMoveHistory_OverlayMemcpy", history),
        ("PokemonMoveHistory_OverlayMemcpy", (
            REPO / "src/pokemon_move_history_overlay/pokemon_move_relearn.c"
        ).read_text()),
        ("PokemonMoveHistory_OverlayMemset", (
            REPO / "src/pokemon_move_history_overlay/pokemon_move_relearn.c"
        ).read_text()),
    ):
        require(helper in source, f"overlay source does not call local {helper}")
    thumb_help = (
        REPO / "asm/pokemon_move_history_overlay/thumb_help.s"
    ).read_text()
    for helper in (
        "PokemonMoveHistory_OverlayMemcpy",
        "PokemonMoveHistory_OverlayMemset",
    ):
        require(
            f".global {helper}" in thumb_help,
            f"unique local bridge {helper} is missing",
        )
    require(
        re.search(r"(?m)^\.global\s+(?:memcpy|memset)\s*$", thumb_help)
        is None,
        "overlay bridge still collides with global memcpy/memset symbols",
    )
    package_command = "$(NDSTOOL) -c $(BUILDROM).tmp"
    verifier_command = (
        "scripts/verify_pokemon_move_history_capture.py \\\n"
        "\t\t--rom $(BUILDROM).tmp"
    )
    require(
        makefile.count("scripts/verify_pokemon_move_history_capture.py") == 1
        and package_command in makefile
        and verifier_command in makefile
        and makefile.index(package_command) < makefile.index(verifier_command),
        "capture verifier is not wired once after current ROM packaging",
    )


def host_fixtures() -> None:
    max_moves = 24
    moves_header = (REPO / "include/constants/moves.h").read_text()
    canonical_match = re.search(
        r"^#define NUM_OF_CANONICAL_MOVES\s+(\d+)$",
        moves_header,
        re.MULTILINE,
    )
    custom_match = re.search(
        r"^#define NUM_OF_CUSTOM_MOVES\s+(\d+)$",
        moves_header,
        re.MULTILINE,
    )
    require(
        canonical_match is not None and custom_match is not None,
        "move-count constants are not simple deterministic integers",
    )
    num_moves = int(canonical_match.group(1)) + int(custom_match.group(1))
    unimplemented = {777}

    def valid(move: int) -> bool:
        return move != 0 and move < num_moves and move not in unimplemented

    def record(history: list[int], moves: list[int]) -> bool:
        changed = False
        for move in moves:
            if valid(move) and move not in history:
                if len(history) == max_moves:
                    history.pop(0)
                history.append(move)
                changed = True
        return changed

    def replace(
        history: list[int],
        current: list[int],
        slot: int,
        move: int,
        *,
        committed: bool = True,
        snapshot_ok: bool = True,
    ) -> tuple[list[int], list[int], bool, bool]:
        before = list(current)
        dirty = False
        mutated = False
        if (
            not committed
            or not valid(move)
            or not 0 <= slot < 4
            or not snapshot_ok
            or before[slot] == move
        ):
            return history, current, dirty, mutated
        dirty |= record(history, before)
        current[slot] = move
        mutated = True
        dirty |= record(history, [move])
        return history, current, dirty, mutated

    history: list[int] = []
    dirty = record(history, [10, 20, 30, 0])
    require(dirty and history == [10, 20, 30], "first observation order differs")
    dirty = record(history, [10, 20, 30, 40])
    require(dirty and history == [10, 20, 30, 40], "append order differs")
    before = list(history)
    require(
        not record(history, [10, 20, 30, 40]) and history == before,
        "second reconciliation churns history",
    )

    history, current, dirty, mutated = replace([], [1, 2, 3, 4], 1, 9)
    require(
        dirty
        and mutated
        and history == [1, 2, 3, 4, 9]
        and current == [1, 9, 3, 4],
        "replacement is not old-slot order followed by learned move",
    )
    before = (list(history), list(current))
    history, current, dirty, mutated = replace(history, current, 1, 9)
    require(
        not dirty and not mutated and (history, current) == before,
        "duplicate/no-op assignment changes Pokémon or history",
    )

    canceled_history, canceled_current, dirty, mutated = replace(
        [],
        [5, 6, 7, 8],
        2,
        9,
        committed=False,
    )
    require(
        not dirty
        and not mutated
        and canceled_history == []
        and canceled_current == [5, 6, 7, 8],
        "canceled prompt fixture changed state",
    )
    invalid_history = [31]
    invalid_before = list(invalid_history)
    dirty = record(invalid_history, [0, 777, num_moves])
    require(
        not dirty and invalid_history == invalid_before,
        "invalid-only observation dirties or changes history",
    )
    high_valid = num_moves - 23
    require(
        high_valid > 0
        and valid(high_valid)
        and record(invalid_history, [high_valid])
        and invalid_history == [31, high_valid],
        "implemented high move ID is incorrectly rejected",
    )
    for invalid_move in (0, 777, num_moves):
        invalid_history = [31]
        invalid_current = [1, 2, 3, 4]
        before_invalid = (list(invalid_history), list(invalid_current))
        (
            invalid_history,
            invalid_current,
            dirty,
            mutated,
        ) = replace(invalid_history, invalid_current, 1, invalid_move)
        require(
            not dirty
            and not mutated
            and (invalid_history, invalid_current) == before_invalid,
            f"invalid replacement {invalid_move} dirties or mutates state",
        )
    (
        capture_history,
        capture_current,
        dirty,
        mutated,
    ) = replace([], [1, 2, 3, 4], 1, 9, snapshot_ok=False)
    require(
        not dirty
        and not mutated
        and capture_history == []
        and capture_current == [1, 2, 3, 4],
        "snapshot failure mutates Pokémon or history",
    )

    delete_history: list[int] = []
    delete_current = [21, 22, 23, 24]
    require(
        record(delete_history, delete_current),
        "committed deletion did not capture the old slots",
    )
    delete_current = [21, 23, 24, 0]
    require(
        delete_history == [21, 22, 23, 24]
        and delete_current == [21, 23, 24, 0],
        "committed deletion lost the forgotten move or appended MOVE_NONE",
    )


def symbol_table(path: Path) -> dict[str, int]:
    output = subprocess.check_output(
        ["arm-none-eabi-nm", "-n", str(path)], text=True
    )
    symbols: dict[str, int] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            symbols[parts[2]] = int(parts[0], 16)
    return symbols


def thumb_bl_target(image: bytes, base: int, address: int) -> int:
    offset = address - base
    first, second = struct.unpack_from("<HH", image, offset)
    require(
        first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800,
        f"0x{address:08X} is not a Thumb-1 BL",
    )
    delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if delta & (1 << 22):
        delta -= 1 << 23
    return address + 4 + delta


def packaged_components(
    rom_path: Path,
) -> tuple[int, bytes, dict[int, tuple[int, bytes]]]:
    require(rom_path.is_file(), f"packaged ROM is absent: {rom_path}")
    rom = rom_path.read_bytes()
    require(len(rom) >= 0x160, "packaged ROM header is truncated")
    arm9_offset, _entry, arm9_base, arm9_size = struct.unpack_from(
        "<4I",
        rom,
        0x20,
    )
    fat_offset, fat_size = struct.unpack_from("<2I", rom, 0x48)
    overlay_offset, overlay_size = struct.unpack_from("<2I", rom, 0x50)
    require(
        arm9_offset + arm9_size <= len(rom),
        "packaged ARM9 extends past the ROM",
    )
    require(
        fat_offset + fat_size <= len(rom) and fat_size % 8 == 0,
        "packaged FAT is invalid",
    )
    require(
        overlay_offset + overlay_size <= len(rom)
        and overlay_size % 32 == 0,
        "packaged ARM9 overlay table is invalid",
    )
    overlays: dict[int, tuple[int, bytes]] = {}
    for offset in range(overlay_offset, overlay_offset + overlay_size, 32):
        fields = struct.unpack_from("<8I", rom, offset)
        overlay_id, ram_address, file_id = fields[0], fields[1], fields[6]
        require(
            file_id * 8 + 8 <= fat_size,
            f"overlay {overlay_id} file ID is outside the FAT",
        )
        start, end = struct.unpack_from(
            "<2I",
            rom,
            fat_offset + file_id * 8,
        )
        require(
            start <= end <= len(rom),
            f"overlay {overlay_id} file extent is invalid",
        )
        overlays[overlay_id] = (ram_address, rom[start:end])
    return arm9_base, rom[arm9_offset:arm9_offset + arm9_size], overlays


def bytes_at(image: bytes, base: int, address: int, size: int) -> bytes:
    offset = address - base
    require(
        offset >= 0 and offset + size <= len(image),
        f"0x{address:08X}..0x{address + size:08X} is outside its image",
    )
    return image[offset:offset + size]


def binary_contracts(rom_path: Path) -> None:
    linked = REPO / "build/pokemon_move_history_overlay_linked.o"
    overlay_path = REPO / "build/output_pokemon_move_history_overlay.bin"
    arm9_path = REPO / "base/arm9.bin"
    ov12_path = REPO / "base/overlay/overlay_0012.bin"
    ov68_path = REPO / "base/overlay/overlay_0068.bin"
    ov153_path = REPO / "base/overlay/overlay_0153.bin"
    pokemon_object = REPO / "build/pokemon.o"
    party_menu_object = REPO / "build/party_menu.o"
    history_object = (
        REPO / "build/pokemon_move_history_overlay/pokemon_move_history.o"
    )
    relearn_object = (
        REPO / "build/pokemon_move_history_overlay/pokemon_move_relearn.o"
    )
    core_linked = REPO / "build/linked.o"
    required_artifacts = (
        linked,
        overlay_path,
        arm9_path,
        ov12_path,
        ov68_path,
        ov153_path,
        pokemon_object,
        party_menu_object,
        history_object,
        relearn_object,
        core_linked,
        rom_path,
    )
    missing = [str(path) for path in required_artifacts if not path.is_file()]
    require(not missing, "required build artifacts are absent: " + ", ".join(missing))

    overlay_inputs = (
        REPO / "src/pokemon_move_history_overlay/pokemon_move_history.c",
        REPO / "src/pokemon_move_history_overlay/pokemon_move_relearn.c",
        REPO / "asm/pokemon_move_history_overlay/entry.s",
        REPO / "asm/pokemon_move_history_overlay/thumb_help.s",
        REPO / "src/pokemon_move_history_overlay/linker.ld",
        REPO / "include/pokemon_move_history.h",
        REPO / "include/pokemon.h",
        REPO / "rom.ld",
        REPO / "overlays.mk",
    )
    newest_overlay_input = max(
        path.stat().st_mtime
        for path in overlay_inputs
    )
    for artifact in (linked, overlay_path, ov153_path):
        require(
            artifact.stat().st_mtime >= newest_overlay_input,
            f"build artifact is stale: {artifact}",
        )
    object_inputs = (
        (pokemon_object, REPO / "src/pokemon.c"),
        (party_menu_object, REPO / "src/party_menu.c"),
        (
            history_object,
            REPO / "src/pokemon_move_history_overlay/pokemon_move_history.c",
        ),
        (
            relearn_object,
            REPO / "src/pokemon_move_history_overlay/pokemon_move_relearn.c",
        ),
    )
    for artifact, source in object_inputs:
        require(
            artifact.stat().st_mtime >= source.stat().st_mtime,
            f"object is stale relative to {source}: {artifact}",
        )
    patch_input = REPO / "armips/asm/pokemon_move_history_capture.s"
    for artifact in (arm9_path, ov12_path, ov68_path):
        require(
            artifact.stat().st_mtime >= patch_input.stat().st_mtime,
            f"patched binary is stale: {artifact}",
        )
    newest_packaged_input = max(
        path.stat().st_mtime
        for path in (arm9_path, ov12_path, ov68_path, ov153_path)
    )
    require(
        rom_path.stat().st_mtime >= newest_packaged_input,
        f"packaged ROM is stale relative to patched binaries: {rom_path}",
    )

    overlay = overlay_path.read_bytes()
    require(
        len(overlay) <= OVERLAY_LIMIT,
        f"overlay 153 exceeds guarded 0x{OVERLAY_LIMIT:X}-byte envelope",
    )
    symbols = symbol_table(linked)
    for name in (
        "PokemonMoveHistory_ReplaceMoveImpl",
        "PokemonMoveHistory_DeleteMoveSlotImpl",
    ):
        require(name in symbols, f"linked implementation {name} is missing")

    for object_name, api in (
        ("pokemon.o", "PokemonMoveHistory_RecordMove"),
        ("party_menu.o", "PokemonMoveHistory_ReplaceMove"),
    ):
        reloc = subprocess.check_output(
            [
                "arm-none-eabi-objdump",
                "-r",
                str(REPO / "build" / object_name),
            ],
            text=True,
        )
        require(
            re.search(rf"R_ARM_ABS32\s+{api}\b", reloc) is not None,
            f"{object_name} lacks long-call ABS32 relocation to {api}",
        )
        require(
            re.search(rf"R_ARM_THM_CALL\s+{api}\b", reloc) is None,
            f"{object_name} gained unsafe direct relocation to {api}",
        )
    pokemon_reloc = subprocess.check_output(
        [
            "arm-none-eabi-objdump",
            "-r",
            str(REPO / "build/pokemon.o"),
        ],
        text=True,
    )
    require(
        re.search(r"R_ARM_ABS32\s+SaveBlock2_get\b", pokemon_reloc)
        is not None,
        "pokemon.o lacks interworking-safe current-save resolution",
    )
    require(
        re.search(r"R_ARM_THM_CALL\s+SaveBlock2_get\b", pokemon_reloc)
        is None,
        "pokemon.o gained an unsafe direct SaveBlock2_get relocation",
    )

    history_reloc = subprocess.check_output(
        [
            "arm-none-eabi-objdump",
            "-r",
            str(REPO / "build/pokemon_move_history_overlay/pokemon_move_history.o"),
        ],
        text=True,
    )
    for target in (
        "SaveBlock2_get",
        "Party_GetCount",
        "Party_GetMonByIndex",
        "MonDeleteMoveSlot_Original",
        "IsMoveUnimplemented",
        "SetBoxMonData",
        "GetBoxMonData",
        "GetMoveMaxPP",
    ):
        require(
            re.search(rf"R_ARM_ABS32\s+{target}\b", history_reloc) is not None,
            f"overlay 153 lacks interworking-safe relocation to {target}",
        )
        require(
            re.search(rf"R_ARM_THM_CALL\s+{target}\b", history_reloc) is None,
            f"overlay 153 gained unsafe Thumb call relocation to {target}",
        )

    for object_path, expected_calls in (
        (history_object, ("PokemonMoveHistory_OverlayMemcpy",)),
        (
            relearn_object,
            (
                "PokemonMoveHistory_OverlayMemcpy",
                "PokemonMoveHistory_OverlayMemset",
            ),
        ),
    ):
        reloc = subprocess.check_output(
            ["arm-none-eabi-objdump", "-r", str(object_path)],
            text=True,
        )
        for target in expected_calls:
            require(
                re.search(rf"R_ARM_THM_CALL\s+{target}\b", reloc) is not None,
                f"{object_path.name} does not call local bridge {target}",
            )

    arm9_base, packaged_arm9, packaged_overlays = packaged_components(rom_path)
    require(arm9_base == 0x02000000, "packaged ARM9 RAM base differs")
    for overlay_id in (12, 68, 153):
        require(
            overlay_id in packaged_overlays,
            f"packaged overlay {overlay_id} is absent",
        )
    ov12_base, packaged_ov12 = packaged_overlays[12]
    ov68_base, packaged_ov68 = packaged_overlays[68]
    ov153_base, packaged_ov153 = packaged_overlays[153]
    require(ov12_base == 0x022378C0, "packaged overlay 12 base differs")
    require(ov68_base == 0x021E5900, "packaged overlay 68 base differs")
    require(ov153_base == OVERLAY_BASE, "packaged overlay 153 base differs")
    base_arm9 = arm9_path.read_bytes()
    require(
        base_arm9.startswith(packaged_arm9)
        and len(base_arm9) - len(packaged_arm9) <= 12,
        "packaged ARM9 bytes differ from the current patched ARM9",
    )
    require(
        packaged_ov12 == ov12_path.read_bytes(),
        "packaged overlay 12 differs from the current patched artifact",
    )
    require(
        packaged_ov68 == ov68_path.read_bytes(),
        "packaged overlay 68 differs from the current patched artifact",
    )
    require(
        packaged_ov153 == ov153_path.read_bytes() == overlay,
        "packaged overlay 153 differs from the current linked output",
    )

    expected = OVERLAY_BASE + 0x80
    require(
        thumb_bl_target(packaged_arm9, arm9_base, 0x020769F0) == expected
        and bytes_at(packaged_arm9, arm9_base, 0x020769F4, 2) == b"\x20\x1c",
        "evolution replacement BL target differs",
    )
    require(
        thumb_bl_target(packaged_ov12, ov12_base, 0x02246344) == expected
        and bytes_at(packaged_ov12, ov12_base, 0x02246348, 2) == b"\x61\x68",
        "battle replacement BL target differs",
    )
    require(
        bytes_at(packaged_ov68, ov68_base, 0x021E6158, 8)
        == b"\x20\x68\xc2\x7e\x00\x68\x00\x99"
        and thumb_bl_target(packaged_ov68, ov68_base, 0x021E6160)
        == expected
        and bytes_at(packaged_ov68, ov68_base, 0x021E6164, 4)
        == b"\xc0\x46\x00\x20",
        "Move Reminder/tutor full patch or 0x021E6166 continuation differs",
    )
    require(
        thumb_bl_target(packaged_arm9, arm9_base, 0x0204DCCC)
        == OVERLAY_BASE + 0x88,
        "Move Deleter BL target differs",
    )
    require(
        bytes_at(packaged_arm9, arm9_base, 0x0204DCCA, 6)
        == b"\x21\x1c\x70\xf3\xdc\xfb"
        and bytes_at(packaged_arm9, arm9_base, 0x0204DCD0, 4)
        == b"\x00\x20\x70\xbd",
        "Move Deleter continuation differs",
    )
    require(
        thumb_bl_target(packaged_arm9, arm9_base, 0x020542D6)
        == 0x02074644,
        "PartyMonSetMoveInSlot no longer uses Party_GetMonByIndex",
    )
    require(
        bytes_at(packaged_arm9, arm9_base, 0x020542D0, 6)
        == b"\x38\xb5\x15\x1c\x1c\x1c"
        and bytes_at(packaged_arm9, arm9_base, 0x020542DA, 6)
        == b"\x2a\x06\x21\x1c\x12\x0e"
        and thumb_bl_target(packaged_arm9, arm9_base, 0x020542E0)
        == expected
        and bytes_at(packaged_arm9, arm9_base, 0x020542E4, 2)
        == b"\x38\xbd",
        "PartyMonSetMoveInSlot final mutation does not target ReplaceMove",
    )

    for entry_offset, impl_name in (
        (0x80, "PokemonMoveHistory_ReplaceMoveImpl"),
        (0x88, "PokemonMoveHistory_DeleteMoveSlotImpl"),
    ):
        require(
            bytes_at(packaged_ov153, ov153_base, ov153_base + entry_offset, 4)
            == b"\x00\x4b\x18\x47",
            f"fixed entry 0x{entry_offset:X} instructions differ",
        )
        entry_target = struct.unpack_from(
            "<I",
            packaged_ov153,
            entry_offset + 4,
        )[0]
        require(
            entry_target == symbols[impl_name] + 1,
            f"fixed entry 0x{entry_offset:X} target differs",
        )

    core_symbols = symbol_table(core_linked)
    require(
        "IsMoveUnimplemented" in core_symbols,
        "resident core does not export IsMoveUnimplemented",
    )
    implemented_check_target = core_symbols["IsMoveUnimplemented"] + 1
    require(
        0x023D8000 <= implemented_check_target < 0x023E0000,
        "IsMoveUnimplemented is not resident in overlay 129",
    )
    resolved_targets = {
        "SaveBlock2_get": 0x020272B1,
        "GetBoxMonData": 0x0206E641,
        "SetBoxMonData": 0x0206ED71,
        "MonDeleteMoveSlot_Original": 0x020716C1,
        "GetMoveMaxPP": 0x0207332D,
        "IsMoveUnimplemented": implemented_check_target,
    }
    for name, address in resolved_targets.items():
        require(
            symbols.get(name) == address,
            f"final symbol {name} resolves to {symbols.get(name)!r}, "
            f"expected 0x{address:08X}",
        )
    replace_start = symbols["PokemonMoveHistory_ReplaceMoveImpl"] - ov153_base
    delete_start = symbols["PokemonMoveHistory_DeleteMoveSlotImpl"] - ov153_base
    delete_end = symbols["PokemonMoveHistory_CommitIfDirtyImpl"] - ov153_base
    replace_bytes = packaged_ov153[replace_start:delete_start]
    delete_bytes = packaged_ov153[delete_start:delete_end]
    for name in (
        "SaveBlock2_get",
        "GetBoxMonData",
        "SetBoxMonData",
        "GetMoveMaxPP",
    ):
        require(
            struct.pack("<I", resolved_targets[name]) in replace_bytes,
            f"ReplaceMove packaged body does not resolve {name}",
        )
    for name in ("SaveBlock2_get", "MonDeleteMoveSlot_Original"):
        require(
            struct.pack("<I", resolved_targets[name]) in delete_bytes,
            f"DeleteMoveSlot packaged body does not resolve {name}",
        )
    append_start = symbols["PokemonMoveHistory_AppendMove.isra.0"] - ov153_base
    observe_start = symbols["PokemonMoveHistory_ObserveSnapshot"] - ov153_base
    append_bytes = packaged_ov153[append_start:observe_start]
    require(
        struct.pack("<I", implemented_check_target) in append_bytes,
        "AppendMove packaged body does not resolve resident "
        "IsMoveUnimplemented",
    )

    disassembly = subprocess.check_output(
        ["arm-none-eabi-objdump", "-d", str(linked)],
        text=True,
    )
    helper_specs = (
        ("PokemonMoveHistory_OverlayMemcpy", 3, 0x020E5AD8),
        ("PokemonMoveHistory_OverlayMemset", 1, 0x020E5B44),
    )
    for helper, expected_count, retail_target in helper_specs:
        require(helper in symbols, f"local bridge symbol {helper} is absent")
        helper_address = symbols[helper]
        require(
            OVERLAY_BASE <= helper_address < OVERLAY_BASE + len(packaged_ov153),
            f"local bridge {helper} is outside overlay 153",
        )
        calls = [
            int(match.group(1), 16)
            for match in re.finditer(
                rf"(?m)^\s*([0-9a-f]+):.*\bbl\s+[0-9a-f]+\s+<{helper}>",
                disassembly,
            )
        ]
        require(
            len(calls) == expected_count,
            f"{helper} packaged call count is {len(calls)}, expected {expected_count}",
        )
        for call_address in calls:
            require(
                thumb_bl_target(
                    packaged_ov153,
                    ov153_base,
                    call_address,
                )
                == helper_address,
                f"0x{call_address:08X} does not target local {helper}",
            )
        require(
            re.search(
                rf"<{helper}>:.*?\bblx\s+{retail_target:x}\b",
                disassembly,
                re.DOTALL,
            )
            is not None,
            f"{helper} does not interwork to retail 0x{retail_target:08X}",
        )

    nm_all = subprocess.check_output(
        ["arm-none-eabi-nm", str(linked)], text=True
    )
    require(
        "__PokemonMoveHistory_" not in nm_all,
        "overlay 153 contains generated move-history veneers",
    )
    print(
        "move-history capture: source, fixtures, ABI relocations, and final "
        "packaged hook/helper targets verified"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rom",
        type=Path,
        help="current packaged ROM; required unless --source-only is used",
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="run deterministic source and host checks before packaging",
    )
    args = parser.parse_args()
    require(
        args.source_only != (args.rom is not None),
        "choose exactly one of --source-only or --rom",
    )
    source_contracts()
    host_fixtures()
    if args.source_only:
        print("move-history capture: source and host fixtures verified")
    else:
        binary_contracts(args.rom)


if __name__ == "__main__":
    main()
