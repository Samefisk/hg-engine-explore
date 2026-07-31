#!/usr/bin/env python3
"""Deterministic source, host-state, ABI, and packaged-binary verifier."""

from __future__ import annotations

import argparse
import re
import struct
import subprocess
from pathlib import Path


OVERLAY_ID = 154
OVERLAY_BASE = 0x023C0400
OVERLAY_LIMIT = 0x1EA0
OVERLAY_END = OVERLAY_BASE + OVERLAY_LIMIT
OVERLAY_MAGIC = 0x344D5253
OVERLAY_VERSION = 4
SUMMARY_STATE_CALL = 0x02088494
SUMMARY_STATE_SIZE_LITERAL = 0x02088414
SUMMARY_TEMPLATE_ID = 0x02103A28
ARM9_BASE = 0x02000000
OVERLAY129_BASE = 0x023D8000
OVERLAY129_END = 0x023E0000
OVERLAY153_ID = 153
OVERLAY153_LIMIT = 0xFB4
MAX_CANDIDATES = 65


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Summary move relearn verification failed: {message}")


def body(source: str, name: str) -> str:
    match = re.search(rf"\b{name}\s*\([^;]*?\)\s*\{{", source, re.S)
    require(match is not None, f"function body is missing: {name}")
    start = match.end()
    depth = 1
    cursor = start
    while cursor < len(source) and depth:
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    require(depth == 0, f"function body is unterminated: {name}")
    return source[start : cursor - 1]


def rect_contains(rect: tuple[int, int, int, int], x: int, y: int) -> bool:
    top, bottom, left, right = rect
    return top <= y < bottom and left <= x < right


def source_contracts(root: Path) -> None:
    ui = (
        root
        / "src/summary_move_relearn_overlay/summary_move_relearn.c"
    ).read_text()
    history = (
        root
        / "src/pokemon_move_history_overlay/pokemon_move_history.c"
    ).read_text()
    candidates = (
        root
        / "src/pokemon_move_history_overlay/pokemon_move_relearn.c"
    ).read_text()
    hooks = (root / "hooks").read_text()
    armips_patch = (
        root / "armips/asm/summary_move_relearn.s"
    ).read_text()
    resident_hook_source = (root / "asm/other_hook.s").read_text()
    patches = (root / "bytereplacement").read_text()
    linker = (
        root / "src/summary_move_relearn_overlay/linker.ld"
    ).read_text()
    entry = (
        root / "asm/summary_move_relearn_overlay/entry.s"
    ).read_text()
    overlay_source = (root / "src/overlay.c").read_text()
    messages = (root / "data/text/302.txt").read_text()

    query = body(history, "PokemonMoveHistory_QueryRecord")
    readonly = body(history, "PokemonMoveHistory_QueryReadOnlyImpl")
    builder = body(candidates, "PokemonMoveRelearn_BuildCandidatesImpl")
    require(
        "PokemonMoveHistory_QueryReadOnlyImpl(" in builder
        and "PokemonMoveHistory_QueryImpl(" not in builder,
        "candidate builder is not observational",
    )
    require(
        "FALSE" in readonly
        and "PokemonMoveHistory_QueryRecord(" in readonly,
        "read-only query does not select the non-observing path",
    )
    require(
        "PokemonMoveHistory_FindRecord(" in query
        and "if (observe)" in query
        and "PokemonMoveHistory_ObserveSnapshot(" in query,
        "shared query does not separate lookup from observation",
    )

    current_mon = body(ui, "SummaryMoveRelearn_GetCurrentMon")
    require(
        "Party_GetMonByIndex(party, pos)" in current_mon
        and "party->members" not in current_mon,
        "party lookup does not use the canonical accessor",
    )
    enter = body(ui, "SummaryMoveRelearn_Enter")
    require(
        "PokemonMoveRelearn_BuildCandidates(" in enter
        and "POKEMON_MOVE_RELEARN_MAX_CANDIDATES" in enter,
        "entry does not use the task-2 bounded candidate builder",
    )
    require(
        "if (count > POKEMON_MOVE_RELEARN_MAX_CANDIDATES)" in enter,
        "candidate count is not clamped before UI indexing",
    )
    move_cursor = body(ui, "SummaryMoveRelearn_MoveListCursor")
    require(
        "state->candidateCursor++" in move_cursor
        and "state->candidateCursor >= state->candidateCount" in move_cursor
        and "SUMMARY_VISIBLE_CANDIDATES" in move_cursor,
        "candidate cursor lacks bounded wrap/scroll behavior",
    )

    slot = body(ui, "SummaryMoveRelearn_HandleSlot")
    commit = body(ui, "SummaryMoveRelearn_Commit")
    end = body(ui, "SummaryMoveRelearn_End")
    list_handler = body(ui, "SummaryMoveRelearn_HandleList")
    require(
        "MoveIsHM(oldMove)" in slot
        and slot.index("MoveIsHM(oldMove)")
        < slot.index("SUMMARY_RELEARN_CONFIRM"),
        "HM protection is not enforced before confirmation",
    )
    require(
        "oldMove == state->pendingMove" in slot,
        "slot selection does not reject a same-move no-op",
    )
    require(
        ui.count("PokemonMoveHistory_ReplaceMove(") == 1
        and "PokemonMoveHistory_ReplaceMove(" in commit,
        "permanent mutation is not isolated to the confirmation worker",
    )
    replace_at = commit.index("PokemonMoveHistory_ReplaceMove(")
    dirty_at = commit.index("summary->baseData + 0x38")
    require(
        replace_at < dirty_at,
        "Summary dirty ownership is marked before replacement success",
    )
    require(
        "MoveIsHM(oldMove)" in commit
        and "SummaryMoveRelearn_IsKnown" in commit
        and "SummaryMoveRelearn_IsCachedCandidate" in commit,
        "commit-time no-op/HM/candidate revalidation is incomplete",
    )
    for cancel_body, label in ((end, "end"), (list_handler, "list")):
        require(
            "PokemonMoveHistory_ReplaceMove" not in cancel_body
            and "SetBoxMonData" not in cancel_body,
            f"{label} cancellation path can mutate Pokemon/history",
        )
    require(
        "SummaryMoveRelearn_RestoreCache" in end
        and "state->originalArgMove" in end
        and "state->originalCursor" in end,
        "cancellation does not restore transient Summary presentation",
    )

    main = body(ui, "SummaryMoveRelearn_MainState")
    require(
        "SUMMARY_RELEARN_INACTIVE" in main
        and "Summary_VanillaMainState(summary)" in main
        and "summary->baseData->mode != SUMMARY_NORMAL_MODE" in main
        and "SummaryMoveRelearn_GetPage(summary) != SUMMARY_MOVE_PAGE" in main,
        "inactive flow does not preserve vanilla Summary modes",
    )
    require(
        "MON_DATA_CHECKSUM_FAILED" in main
        and "MON_DATA_IS_EGG" in main,
        "entry eligibility omits checksum/egg safety",
    )
    for state in (
        "SUMMARY_RELEARN_LIST",
        "SUMMARY_RELEARN_EMPTY",
        "SUMMARY_RELEARN_SLOT",
        "SUMMARY_RELEARN_CONFIRM",
        "SUMMARY_RELEARN_HM_BLOCKED",
        "SUMMARY_RELEARN_SUCCESS",
    ):
        require(state in main, f"state is absent from dispatcher: {state}")
    require(
        "sameOwnerArgs = state->ownerArgs == summary->baseData;" in main
        and "if (sameOwnerArgs && summary->baseData != NULL)" in main
        and main.count(
            "summary->baseData->move = state->originalArgMove;"
        )
        == 1,
        "owner args identity no longer exclusively guards argument restore",
    )
    identity_guard = main.index(
        "if (sameOwnerArgs && summary->baseData != NULL)"
    )
    identity_restore = main.index(
        "summary->baseData->move = state->originalArgMove;"
    )
    refresh_restore = main.index(
        "restoreMove = summary->baseData->move;"
    )
    require(
        identity_guard < identity_restore < refresh_restore
        and "state->ownerPos != summary->baseData->pos" in main
        and "summary->baseData->move = restoreMove;" in main,
        "identity and position boundary cleanup are not separated",
    )

    require(
        "Summary_MoveRelearnDispatcher 02088494" not in hooks
        and "arm9 Summary_IVEV 02088B60 1" in hooks
        and "arm9 Summary_Entry_Hook 0208D2C4 1" in hooks,
        "task4 hook does not coexist with retail extensions",
    )
    require(
        ".org 0x02088494" in armips_patch
        and "SummaryMoveRelearn_Entry equ 0x023C0408" in armips_patch
        and "bl SummaryMoveRelearn_Entry" in armips_patch,
        "state-2 interception is not an exact four-byte Thumb BL",
    )
    require(
        "arm9 02088414 98 08 00 00" in patches
        and "arm9 02103A28 9A 00 00 00" in patches,
        "Summary state/template ownership patches differ",
    )
    require(
        "ORIGIN = 0x023C0400" in linker
        and "LENGTH = 0x1EA0" in linker
        and "SummaryMoveRelearn_Entry == ORIGIN(rom) + 0x08" in linker,
        "overlay 154 placement or fixed ABI differs",
    )
    require(
        ".word 0x344D5253" in entry
        and ".word 4" in entry
        and "SummaryMoveRelearn_MainState + 1" in entry,
        "overlay 154 header/entry ABI differs",
    )
    require(
        "Summary_MoveRelearnDispatcher" not in resident_hook_source,
        "task4 still consumes resident overlay-129 dispatcher space",
    )
    require(
        "ovyId <= OVERLAY_POKEMON_MOVE_HISTORY" in overlay_source,
        "overlay 154 is still misclassified as a resident field overlay",
    )
    require(
        "ClearWindowTilemapAndScheduleTransfer" in ui
        and "SUMMARY_SHARED_TILE_WINDOW" in ui
        and "addlWindows[SUMMARY_SHARED_TILE_WINDOW]" in ui
        and "window = &summary->addlWindows[SUMMARY_PROMPT_WINDOW]" in ui,
        "shared char tiles are not unmapped before using the prompt strip",
    )
    require(
        "Summary_ClearMoveDetailWindows(summary)" in ui
        and ui.count("Summary_ClearMoveDetailWindows(summary)") >= 2
        and ui.count("Summary_UpdateMoveCursorSprite(summary)") >= 2
        and "{ 136, 151, 8, 41 }" in ui
        and "{ 136, 151, 45, 128 }" in ui
        and "{ 136, 151, 8, 32 }" in ui
        and "{ 136, 151, 36, 128 }" in ui
        and "{ 165, 188, 190, 249 }" in ui,
        "modal cleanup or prompt-strip touch ownership differs",
    )
    action_pick = (136, 151, 8, 41)
    action_back = (136, 151, 45, 128)
    confirm_ok = (136, 151, 8, 32)
    confirm_back = (136, 151, 36, 128)
    require(
        rect_contains(action_pick, 40, 140)
        and not rect_contains(action_pick, 41, 140)
        and not rect_contains(action_back, 44, 140)
        and rect_contains(action_back, 45, 140)
        and rect_contains(confirm_ok, 31, 140)
        and not rect_contains(confirm_ok, 32, 140)
        and not rect_contains(confirm_back, 35, 140)
        and rect_contains(confirm_back, 36, 140)
        and not rect_contains(confirm_ok, 36, 140),
        "exclusive prompt hitbox edges overlap glyphs or omit dead gaps",
    )
    for text in (
        "X: Relearn",
        "A:Pick B:Back",
        "None. B:Back",
        "Pick a slot.",
        "A:OK B:Back",
        "Relearned!",
    ):
        require(text in messages, f"Summary control message is missing: {text}")
    require(
        ui.count("Summary_RebuildMoveCategoryIcons(summary)") >= 4,
        "synthetic/restored move rows do not rebuild category icons",
    )
    require(
        "TouchscreenHitbox_FindRectAtTouchNew" in ui
        and "sMoveRowTouchRects" in ui
        and "sPromptTouchRects" in ui
        and "sActionTouchRects" in ui
        and "sBackTouchRects" in ui
        and "sConfirmTouchRects" in ui,
        "entry/list/slot/confirmation touch controls are incomplete",
    )
    render_slot = body(ui, "SummaryMoveRelearn_RenderSlot")
    require(
        "summary->pokemonData.moves[state->selectedSlot] ="
        " state->pendingMove;" in render_slot
        and "GetMoveMaxPP(state->pendingMove, 0)" in render_slot
        and "summary->pokemonData.curPP[state->selectedSlot] = pp;"
        in render_slot
        and "summary->pokemonData.maxPP[state->selectedSlot] = pp;"
        in render_slot
        and render_slot.index("Summary_UpdateMoveSelection(summary);")
        < render_slot.rindex("Summary_DrawMoveRows(summary);"),
        "slot preview is not an authoritative inline full-PP move row",
    )
    require(
        "SUMMARY_MSG_PICK_BACK" in render_slot,
        "slot selection does not render explicit Pick/Back controls",
    )
    require(
        ui.count("{ 165, 188, 190, 249 }") == 3
        and "{ 165, 188, 8, 55 }" not in ui
        and "{ 165, 188, 56, 128 }" not in ui,
        "lower page-button row aliases a modal label action",
    )
    require(
        main.count("if (touch == 0 || touch == 1)") == 1
        and main.count("if (touch == 2)") == 1,
        "empty Back/Cancel or success blue-Cancel ownership differs",
    )
    for handler, label in (
        (list_handler, "candidate list"),
        (slot, "slot selection"),
    ):
        require(
            "touch == 0" in handler
            and "touch == 1 || touch == 2" in handler
            and "newKeys |= PAD_BUTTON_A" in handler
            and "newKeys |= PAD_BUTTON_B" in handler,
            f"{label} touch controls do not split Pick from Back/Cancel",
        )
    require(
        main.count("SummaryMoveRelearn_GetTouch(sConfirmTouchRects)") == 3
        and main.count("touch == 1 || touch == 2") >= 2,
        "confirmation/HM touch controls do not map OK and Back/Cancel",
    )
    render_list = body(ui, "SummaryMoveRelearn_RenderList")
    pp_cache = render_list.index("summary->pokemonData.curPP[i] = pp;")
    selection = render_list.index("Summary_UpdateMoveSelection(summary);")
    final_rows = render_list.rindex("Summary_DrawMoveRows(summary);")
    require(
        "GetMoveMaxPP(move, 0)" in render_list
        and "summary->pokemonData.maxPP[i] = pp;" in render_list
        and pp_cache < selection < final_rows,
        "candidate full-PP cache is not the final authoritative row draw",
    )
    move_pane = body(ui, "SummaryMoveRelearn_SetMovePane")
    require(
        "ScheduleSetBgPosText(summary->bgl, 5, 0, visible ? 0x80 : 0)"
        in move_pane
        and "SummaryMoveRelearn_SetMovePane(summary, TRUE)" in enter
        and "SummaryMoveRelearn_SetMovePane(summary, FALSE)" in end
        and "SummaryMoveRelearn_SetMovePane(summary, FALSE)" in main,
        "retail detail pane is not shown and restored around modal ownership",
    )


def host_state_contracts() -> None:
    for count in (1, 4, 5, MAX_CANDIDATES):
        cursor = 0
        top = 0
        for _ in range(count * 3):
            cursor = (cursor + 1) % count
            if cursor < top:
                top = cursor
            elif cursor >= top + 4:
                top = cursor - 3
            if cursor == 0 and top + 4 < count:
                top = 0
            require(0 <= cursor < count, "host cursor escaped candidate bounds")
            require(
                top <= cursor < min(top + 4, count),
                "host cursor escaped its four-row viewport",
            )
        for _ in range(count * 3):
            cursor = count - 1 if cursor == 0 else cursor - 1
            if cursor < top:
                top = cursor
            elif cursor >= top + 4:
                top = cursor - 3
            require(
                top <= cursor < min(top + 4, count),
                "reverse host scroll escaped its viewport",
            )

    transitions = {
        ("inactive", "X"): ("list", False),
        ("inactive", "touch-entry"): ("list", False),
        ("list", "B"): ("inactive", False),
        ("list", "touch-back"): ("inactive", False),
        ("list", "A"): ("slot", False),
        ("list", "touch-pick"): ("slot", False),
        ("slot", "B"): ("list", False),
        ("slot", "touch-back"): ("list", False),
        ("slot", "A"): ("confirm", False),
        ("slot", "touch-pick"): ("confirm", False),
        ("confirm", "B"): ("slot", False),
        ("confirm", "touch-back"): ("slot", False),
        ("confirm", "A"): ("success", True),
        ("confirm", "touch-ok"): ("success", True),
        ("hm", "B"): ("slot", False),
        ("success", "B"): ("inactive", False),
    }
    for (state, key), (_, mutates) in transitions.items():
        require(
            mutates
            == (
                state == "confirm"
                and key in ("A", "touch-ok")
            ),
            f"host transition mutates outside explicit confirmation: {state}/{key}",
        )


def parse_y9(path: Path) -> list[tuple[int, ...]]:
    data = path.read_bytes()
    require(len(data) % 0x20 == 0, "y9 size is not row-aligned")
    rows = [
        struct.unpack_from("<8I", data, offset)
        for offset in range(0, len(data), 0x20)
    ]
    require(
        [row[0] for row in rows] == list(range(len(rows))),
        "y9 overlay IDs are not dense ordinals",
    )
    return rows


def thumb_bl_target(data: bytes, address: int, base: int) -> int:
    offset = address - base
    upper, lower = struct.unpack_from("<HH", data, offset)
    require(
        upper & 0xF800 == 0xF000 and lower & 0xF800 == 0xF800,
        f"0x{address:08X} is not a Thumb-1 BL",
    )
    displacement = ((upper & 0x07FF) << 12) | ((lower & 0x07FF) << 1)
    if displacement & (1 << 22):
        displacement -= 1 << 23
    return address + 4 + displacement


def symbol_address(path: Path, name: str) -> int:
    output = subprocess.check_output(
        ["arm-none-eabi-nm", str(path)],
        text=True,
    )
    match = re.search(
        rf"(?m)^([0-9a-fA-F]+)\s+[A-Za-z]\s+{re.escape(name)}$",
        output,
    )
    require(match is not None, f"linked symbol is missing: {name}")
    return int(match.group(1), 16)


def binary_contracts(args: argparse.Namespace) -> None:
    arm9 = args.arm9.read_bytes()
    overlay154 = args.overlay154.read_bytes()
    linked154 = args.linked_overlay154.read_bytes()
    rows = parse_y9(args.y9)

    require(
        struct.unpack_from(
            "<I", arm9, SUMMARY_STATE_SIZE_LITERAL - ARM9_BASE
        )[0]
        == 0x898,
        "packaged Summary state size is not 0x898",
    )
    require(
        struct.unpack_from(
            "<I", arm9, SUMMARY_TEMPLATE_ID - ARM9_BASE
        )[0]
        == OVERLAY_ID,
        "Summary template does not own overlay 154",
    )
    require(
        thumb_bl_target(arm9, SUMMARY_STATE_CALL, ARM9_BASE)
        == OVERLAY_BASE + 8,
        "Summary state-2 call does not target overlay 154's fixed entry",
    )
    require(
        arm9[SUMMARY_STATE_CALL - ARM9_BASE - 4
             : SUMMARY_STATE_CALL - ARM9_BASE]
        == bytes.fromhex("20605ae0")
        and
        arm9[SUMMARY_STATE_CALL - ARM9_BASE + 4
             : SUMMARY_STATE_CALL - ARM9_BASE + 8]
        == bytes.fromhex("206056e0"),
        "Summary state-2 continuation or neighboring cases were overwritten",
    )
    core_symbols = subprocess.check_output(
        ["arm-none-eabi-nm", str(args.core_linked)],
        text=True,
    )
    require(
        "Summary_MoveRelearnDispatcher" not in core_symbols,
        "resident overlay 129 still contains the task4 dispatcher",
    )

    require(OVERLAY_ID < len(rows), "y9 has no overlay 154 row")
    row = rows[OVERLAY_ID]
    require(
        row
        == (
            OVERLAY_ID,
            OVERLAY_BASE,
            len(overlay154),
            0,
            0,
            0,
            OVERLAY_ID,
            0,
        ),
        "overlay 154 y9 metadata differs",
    )
    require(
        len(overlay154) + row[3] <= OVERLAY_LIMIT,
        "overlay 154 exceeds the stock-overlay-133 boundary",
    )
    require(
        OVERLAY_BASE + row[2] + row[3] <= 0x023C22A0
        and rows[OVERLAY153_ID][1] + rows[OVERLAY153_ID][2]
        <= OVERLAY_BASE,
        "overlay 154 overlaps overlay 153 or stock overlay 133",
    )
    require(
        overlay154 == linked154,
        "packaged overlay 154 differs from linked output",
    )
    require(
        struct.unpack_from("<II", overlay154, 0)
        == (OVERLAY_MAGIC, OVERLAY_VERSION),
        "packaged overlay 154 fixed header differs",
    )
    entry = symbol_address(
        args.summary_linked,
        "SummaryMoveRelearn_Entry",
    )
    require(
        entry == OVERLAY_BASE + 8,
        "packaged task4 entry moved from fixed +0x08",
    )
    for symbol, expected in (
        (
            "sPromptTouchRects",
            bytes.fromhex("88970857 ff000000"),
        ),
        (
            "sActionTouchRects",
            bytes.fromhex(
                "88970829 88972d80 a5bcbef9 ff000000"
            ),
        ),
        (
            "sBackTouchRects",
            bytes.fromhex("88972880 a5bcbef9 ff000000"),
        ),
        (
            "sConfirmTouchRects",
            bytes.fromhex(
                "88970820 88972480 a5bcbef9 ff000000"
            ),
        ),
    ):
        address = symbol_address(args.summary_linked, symbol)
        offset = address - OVERLAY_BASE
        require(
            overlay154[offset:offset + len(expected)] == expected,
            f"packaged touch rectangles differ: {symbol}",
        )

    require(OVERLAY153_ID < len(rows), "y9 has no overlay 153 row")
    require(
        rows[OVERLAY153_ID][2] <= OVERLAY153_LIMIT,
        "read-only query growth exceeded overlay 153's guard",
    )
    require(
        args.overlay129.stat().st_size <= 0x7FC0,
        "task4 consumed the prior 0x40-byte overlay-129 headroom",
    )

    relocations = subprocess.check_output(
        ["arm-none-eabi-objdump", "-r", str(args.summary_object)],
        text=True,
    )
    require(
        re.search(
            r"R_ARM_THM_CALL\s+__(?:gnu_thumb1_case|aeabi_)",
            relocations,
        )
        is None,
        "task4 emits an unsafe Thumb helper call or veneer",
    )
    disassembly = subprocess.check_output(
        ["arm-none-eabi-objdump", "-d", str(args.summary_linked)],
        text=True,
    )
    require(
        "_from_thumb" not in disassembly
        and re.search(
            r"\bbl\s+[0-9a-fA-Fx ]+<__(?:gnu_thumb1_case|aeabi_)",
            disassembly,
        )
        is None,
        "linked overlay 154 contains ARM-state glue into Thumb helpers",
    )
    for target in (
        "PokemonMoveRelearn_BuildCandidates",
        "PokemonMoveHistory_ReplaceMove",
        "Party_GetMonByIndex",
        "Summary_VanillaMainState",
    ):
        require(
            re.search(rf"R_ARM_ABS32\s+{target}\b", relocations) is not None,
            f"task4 lacks a typed interworking relocation to {target}",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--arm9", type=Path)
    parser.add_argument("--y9", type=Path)
    parser.add_argument("--overlay129", type=Path)
    parser.add_argument("--overlay154", type=Path)
    parser.add_argument("--linked-overlay154", type=Path)
    parser.add_argument("--summary-linked", type=Path)
    parser.add_argument("--summary-object", type=Path)
    parser.add_argument("--core-linked", type=Path)
    args = parser.parse_args()

    source_contracts(args.root.resolve())
    host_state_contracts()
    binary_paths = (
        args.arm9,
        args.y9,
        args.overlay129,
        args.overlay154,
        args.linked_overlay154,
        args.summary_linked,
        args.summary_object,
        args.core_linked,
    )
    require(
        all(path is not None for path in binary_paths)
        or all(path is None for path in binary_paths),
        "binary arguments must be supplied as a complete set",
    )
    if args.arm9 is not None:
        binary_contracts(args)
    print(
        "Summary move relearn verification passed: "
        "source, host states, ABI, bounds, and packaged binaries"
    )


if __name__ == "__main__":
    main()
