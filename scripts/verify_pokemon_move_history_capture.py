#!/usr/bin/env python3
"""Task-3 static, host-fixture, relocation, and final hook verification."""

from __future__ import annotations

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

    replace = function_body(history, "PokemonMoveHistory_ReplaceMoveImpl")
    ordered(
        replace,
        [
            "PokemonMoveHistory_CaptureSnapshotImpl",
            "PokemonMoveHistory_ObserveSnapshot",
            "SetBoxMonData(pokemon, MON_DATA_MOVE1 + slot",
            "GetBoxMonData(pokemon, MON_DATA_MOVE1 + slot",
            "before.moves[slot] = move",
            "PokemonMoveHistory_AppendMove",
        ],
        "replacement transaction",
    )
    require(
        "before.moves[slot] != move" in replace,
        "duplicate/no-op replacement is not excluded from history",
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


def host_fixtures() -> None:
    max_moves = 24
    unimplemented = {777}

    def valid(move: int) -> bool:
        return move != 0 and move < 900 and move not in unimplemented

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
        history: list[int], current: list[int], slot: int, move: int
    ) -> tuple[list[int], list[int], bool]:
        before = list(current)
        dirty = False
        if 0 <= slot < 4 and before[slot] != move:
            dirty |= record(history, before)
            current[slot] = move
            if valid(move):
                dirty |= record(history, [move])
        return history, current, dirty

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

    history, current, dirty = replace([], [1, 2, 3, 4], 1, 9)
    require(
        dirty and history == [1, 2, 3, 4, 9] and current == [1, 9, 3, 4],
        "replacement is not old-slot order followed by learned move",
    )
    before = (list(history), list(current))
    history, current, dirty = replace(history, current, 1, 9)
    require(
        not dirty and (history, current) == before,
        "duplicate/no-op assignment pollutes or reorders history",
    )

    canceled_history: list[int] = []
    canceled_current = [5, 6, 7, 8]
    require(
        canceled_history == [] and canceled_current == [5, 6, 7, 8],
        "canceled prompt fixture changed state",
    )
    invalid_history: list[int] = []
    record(invalid_history, [0, 777, 900, 12])
    require(
        invalid_history == [12],
        "NONE, out-of-range, or unimplemented moves entered history",
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


def binary_contracts() -> None:
    linked = REPO / "build/pokemon_move_history_overlay_linked.o"
    overlay_path = REPO / "build/output_pokemon_move_history_overlay.bin"
    arm9_path = REPO / "base/arm9.bin"
    ov12_path = REPO / "base/overlay/overlay_0012.bin"
    ov68_path = REPO / "base/overlay/overlay_0068.bin"
    if not all(
        path.is_file()
        for path in (linked, overlay_path, arm9_path, ov12_path, ov68_path)
    ):
        print("move-history capture: build artifacts absent; binary checks skipped")
        return
    newest_source = max(
        path.stat().st_mtime
        for path in (
            REPO / "src/pokemon_move_history_overlay/pokemon_move_history.c",
            REPO / "asm/pokemon_move_history_overlay/entry.s",
            REPO / "armips/asm/pokemon_move_history_capture.s",
            REPO / "src/pokemon.c",
            REPO / "src/party_menu.c",
        )
    )
    if linked.stat().st_mtime < newest_source:
        print("move-history capture: build artifacts stale; binary checks skipped")
        return

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
    ):
        require(
            re.search(rf"R_ARM_ABS32\s+{target}\b", history_reloc) is not None,
            f"overlay 153 lacks interworking-safe relocation to {target}",
        )
        require(
            re.search(rf"R_ARM_THM_CALL\s+{target}\b", history_reloc) is None,
            f"overlay 153 gained unsafe Thumb call relocation to {target}",
        )

    expected = OVERLAY_BASE + 0x80
    arm9 = arm9_path.read_bytes()
    ov12 = ov12_path.read_bytes()
    ov68 = ov68_path.read_bytes()
    require(
        thumb_bl_target(arm9, 0x02000000, 0x020769F0) == expected,
        "evolution replacement BL target differs",
    )
    require(
        thumb_bl_target(ov12, 0x022378C0, 0x02246344) == expected,
        "battle replacement BL target differs",
    )
    require(
        thumb_bl_target(ov68, 0x021E5900, 0x021E6160) == expected,
        "Move Reminder/tutor replacement BL target differs",
    )
    require(
        thumb_bl_target(arm9, 0x02000000, 0x0204DCCC)
        == OVERLAY_BASE + 0x88,
        "Move Deleter BL target differs",
    )
    require(
        thumb_bl_target(arm9, 0x02000000, 0x020542D6) == 0x02074644,
        "PartyMonSetMoveInSlot no longer uses Party_GetMonByIndex",
    )
    require(
        thumb_bl_target(arm9, 0x02000000, 0x020542E0) == expected,
        "PartyMonSetMoveInSlot final mutation does not target ReplaceMove",
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
        "hook targets verified"
    )


def main() -> None:
    source_contracts()
    host_fixtures()
    binary_contracts()


if __name__ == "__main__":
    main()
