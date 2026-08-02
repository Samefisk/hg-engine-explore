#!/usr/bin/env python3
"""Deterministic source, host-state, ABI, and packaged-binary verifier."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.machinery
import importlib.util
import json
import marshal
import os
import re
import signal
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
import types
import zipfile
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
MAX_CANDIDATES = 458
NATIVE_BOOTSTRAP_EXPECTED_SHA256 = (
    "07f77f1773b9f89ef4f495f6d9ed4b22b87bd01afc2266925f693eaa500d32bc"
)
NATIVE_BOOTSTRAP_EXPECTED_CDHASH = (
    "5ae41135ff6408160f84717e28f339fbbc00e838"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Summary move relearn verification failed: {message}")


def native_code_signature_provenance(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) < 32 or struct.unpack_from("<I", data, 0)[0] != 0xFEEDFACF:
        raise ValueError("not the exact thin 64-bit Mach-O")
    command_count = struct.unpack_from("<I", data, 16)[0]
    command_bytes = struct.unpack_from("<I", data, 20)[0]
    cursor = 32
    command_end = cursor + command_bytes
    if command_end > len(data):
        raise ValueError("load commands are truncated")
    signature_ranges: list[tuple[int, int]] = []
    for _ in range(command_count):
        if cursor + 8 > command_end:
            raise ValueError("load command header is truncated")
        command, size = struct.unpack_from("<II", data, cursor)
        if size < 8 or cursor + size > command_end:
            raise ValueError("load command is malformed")
        if command == 0x1D:
            if size != 16:
                raise ValueError("code-sign command is malformed")
            signature_ranges.append(struct.unpack_from("<II", data, cursor + 8))
        cursor += size
    if cursor != command_end or len(signature_ranges) != 1:
        raise ValueError("code-sign command count differs")
    signature_offset, signature_size = signature_ranges[0]
    if (
        signature_size < 12
        or signature_offset > len(data)
        or signature_size > len(data) - signature_offset
    ):
        raise ValueError("code signature is out of bounds")
    allocation = data[signature_offset : signature_offset + signature_size]
    magic, logical_size, slot_count = struct.unpack_from(">III", allocation, 0)
    if (
        magic != 0xFADE0CC0
        or logical_size < 12 + slot_count * 8
        or logical_size > len(allocation)
    ):
        raise ValueError("signature superblob is malformed")
    logical = allocation[:logical_size]
    padding = allocation[logical_size:]
    if any(padding):
        raise ValueError("signature allocation padding is nonzero")
    slots: list[dict[str, object]] = []
    slot_types: list[int] = []
    occupied: list[tuple[int, int]] = []
    code_directory: bytes | None = None
    for index in range(slot_count):
        slot_type, offset = struct.unpack_from(">II", logical, 12 + index * 8)
        if offset < 12 + slot_count * 8 or offset + 8 > logical_size:
            raise ValueError("signature slot offset is malformed")
        blob_magic, blob_size = struct.unpack_from(">II", logical, offset)
        if blob_size < 8 or blob_size > logical_size - offset:
            raise ValueError("signature slot is truncated")
        if slot_type in slot_types:
            raise ValueError("signature slot is duplicated")
        if any(offset < end and start < offset + blob_size for start, end in occupied):
            raise ValueError("signature slots overlap")
        occupied.append((offset, offset + blob_size))
        slot_types.append(slot_type)
        blob = logical[offset : offset + blob_size]
        slots.append(
            {
                "type": slot_type,
                "magic": f"0x{blob_magic:08x}",
                "size": blob_size,
                "sha256": hashlib.sha256(blob).hexdigest(),
            }
        )
        if slot_type == 0:
            if blob_magic != 0xFADE0C02:
                raise ValueError("CodeDirectory magic differs")
            code_directory = blob
    entitlement_probe = subprocess.run(
        ["/usr/bin/codesign", "-d", "--entitlements", "-", str(path)],
        check=False,
        capture_output=True,
        timeout=30,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    if entitlement_probe.returncode != 0:
        raise ValueError("codesign entitlement inspection failed")
    if slot_types != [0, 2, 0x10000] or code_directory is None:
        raise ValueError("signature entitlement/slot set is not exactly empty")
    if entitlement_probe.stdout != b"":
        raise ValueError("entitlement dictionary is not exactly empty")
    return {
        "schema": "summary-move-relearn-code-signature-v1",
        "slots": slots,
        "code_directory": {
            "size": len(code_directory),
            "sha256": hashlib.sha256(code_directory).hexdigest(),
        },
        "superblob": {
            "size": logical_size,
            "sha256": hashlib.sha256(logical).hexdigest(),
        },
        "allocation": {
            "size": signature_size,
            "padding_size": len(padding),
            "padding_sha256": hashlib.sha256(padding).hexdigest(),
        },
        "entitlements": {
            "policy": "exactly-empty",
            "keys": [],
            "xml_slot": False,
            "der_slot": False,
            "codesign_stdout": {
                "size": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
            },
        },
    }


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
    task6 = (
        root
        / "src/pokemon_move_history_task6_overlay/"
        "pokemon_move_history_task6.c"
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
    summary_header = (root / "include/summary.h").read_text()
    storage = (root / "src/pokemon_storage_system.c").read_text()
    runtime = (
        root / "scripts/verify_summary_move_relearn_runtime.py"
    ).read_text()
    launcher = (
        root / "scripts/launch_summary_move_relearn_runtime.py"
    ).read_text()
    party_verifier = (
        root
        / "scripts/verify_pokemon_move_history_party_integrity.py"
    ).read_text()
    manifest_builder = (
        root / "scripts/pokemon_move_history_build_manifest.py"
    ).read_text()
    build_wrapper = (root / "docker-makerom.cmd").read_text()
    protected_spawn = (
        root / "scripts/summary_move_relearn_protected_spawn.py"
    ).read_text()
    protected_spawn_swift = (
        root / "scripts/summary_move_relearn_protected_spawn.swift"
    ).read_text()
    headless = (root / "scripts/headless-overworld-test.py").read_text()
    pokemon_core = (root / "src/pokemon.c").read_text()

    protected_tree = ast.parse(protected_spawn)
    protected_literals = [
        ast.literal_eval(node.value)
        for node in protected_tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "PROTECTED_SPAWN_SOURCE"
            for target in node.targets
        )
    ]
    require(
        protected_literals == [protected_spawn_swift],
        "Workshop and retained-runtime protected-spawn sources differ",
    )

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

    current_mon = body(ui, "SummaryMoveRelearn_GetCurrentBoxMon")
    require(
        current_mon.count("Summary_GetPokemonData(summary)") == 2
        and "Party_GetMonByIndex" not in current_mon
        and "storage->boxes" not in current_mon
        and "summary->baseData->dataType == SUMMARY_PARTY_DATA"
        in current_mon
        and "summary->baseData->dataType != SUMMARY_BOX_DATA"
        in current_mon
        and "summary->baseData->limit != MONS_PER_BOX" in current_mon
        and "count = Party_GetCount(party);" in current_mon
        and "count < 1" in current_mon
        and "count > SUMMARY_PARTY_CAPACITY" in current_mon
        and "limit < 1" in current_mon
        and "limit > SUMMARY_PARTY_CAPACITY" in current_mon
        and "pos >= (u32)count" in current_mon
        and "pos >= limit" in current_mon
        and "pos >= SUMMARY_PARTY_CAPACITY" in current_mon,
        "party/PC lookup does not use bounded canonical Summary ownership",
    )
    validity = body(
        task6,
        "PokemonMoveHistoryTask6_IsCanonicalImpl",
    )
    require(
        "species > MAX_MON_NUM" in validity
        and "SPECIES_BAD_EGG" in validity
        and "MON_DATA_CHECKSUM_FAILED" in validity
        and "MON_DATA_IS_EGG" in validity
        and "SanitizeFormNumber" in validity
        and "NEEDS_REVERSION" in validity
        and "SPECIES_CASTFORM" in validity
        and "SPECIES_CHERRIM" in validity,
        "checksummed species/form validation is not fail-closed",
    )
    entry_validity = body(ui, "SummaryMoveRelearn_IsValidEntryPokemon")
    require(
        "return PokemonMoveHistoryTask6_IsCanonical(pokemon);"
        in entry_validity,
        "entry-point record validation is incomplete",
    )
    require(
        "/* 0x30 */ void *menuInputState;" in summary_header
        and "/* 0x34 */ BOOL isFlag982Set;" in summary_header
        and "/* 0x38 */ BOOL pokemonChanged;" in summary_header,
        "Summary arguments do not name the retail PC ownership tail",
    )
    enter = body(ui, "SummaryMoveRelearn_Enter")
    build_mode = body(ui, "SummaryMoveRelearn_BuildCandidatesForMode")
    build_all = body(
        ui,
        "SummaryMoveRelearn_BuildAllCompatibleCandidates",
    )
    toggle_mode = body(ui, "SummaryMoveRelearn_ToggleCandidateMode")
    show_mode = body(ui, "SummaryMoveRelearn_ShowCandidateMode")
    require(
        "PokemonMoveRelearn_BuildCandidates(" in build_mode
        and "POKEMON_MOVE_RELEARN_MAX_CANDIDATES" in build_mode
        and "&options" in build_mode,
        "entry does not use the task-2 bounded candidate builder",
    )
    form_policy = body(ui, "SummaryMoveRelearn_AllowPersistentFormMove")
    for fragment in (
        "SPECIES_ROTOM",
        "MOVE_THUNDER_SHOCK",
        "MOVE_OVERHEAT",
        "MOVE_HYDRO_PUMP",
        "MOVE_BLIZZARD",
        "MOVE_AIR_SLASH",
        "MOVE_LEAF_STORM",
        "SPECIES_KYUREM",
        "MOVE_GLACIATE",
        "MOVE_SCARY_FACE",
        "MOVE_ICE_BURN",
        "MOVE_FUSION_FLARE",
        "MOVE_FREEZE_SHOCK",
        "MOVE_FUSION_BOLT",
    ):
        require(
            fragment in form_policy,
            f"persistent form policy lost: {fragment}",
        )
    require(
        "if (count > POKEMON_MOVE_RELEARN_MAX_CANDIDATES)" in build_mode,
        "candidate count is not clamped before UI indexing",
    )
    for fragment in (
        "PokemonMoveHistoryTask6_IsCanonical(pokemon)",
        "PokeOtherFormMonsNoGet(species, form)",
        "LoadLevelUpLearnset_HandleAlternateForm(",
        "CODE_ADDON_MACHINE_LEARNSETS",
        "sMachineMoves[i]",
        "ARC_EGG_MOVES",
        "CODE_ADDON_TUTOR_LEARNSETS",
        "TUTOR_MOVE_IDS_OFFSET",
        "tutorMoves[i]",
        "SPECIES_PICHU",
        "SPECIES_ROTOM",
        "SPECIES_KYUREM",
    ):
        require(fragment in build_all, f"Task-7 compatibility source lost: {fragment}")
    append_all = body(ui, "SummaryMoveRelearn_AppendAllCandidate")
    require(
        "PokemonMoveHistoryTask6_AppendCandidateCall(" in append_all
        and "POKEMON_MOVE_RELEARN_ALL_MAX_CANDIDATES" in append_all,
        "Task-7 canonical bounded append gate differs",
    )
    require(
        "PokemonMoveRelearn_GetParent" not in build_all
        and "CODE_ADDON_MOVE_RELEARN_PARENTS" not in build_all
        and build_all.index("PokemonMoveHistoryTask6_IsCanonical(pokemon)")
        < build_all.index("PokeOtherFormMonsNoGet(species, form)"),
        "Task-7 exact-form compatibility walks lineage or resolves before validation",
    )
    require(
        build_all.index("LoadLevelUpLearnset_HandleAlternateForm(")
        < build_all.index("CODE_ADDON_MACHINE_LEARNSETS")
        < build_all.index("ARC_EGG_MOVES")
        < build_all.index("TUTOR_MOVE_IDS_OFFSET")
        < build_all.index("if (species == SPECIES_PICHU)"),
        "Task-7 source-native ordering differs",
    )
    require(
        "state->allCompatible = !state->allCompatible;" in toggle_mode
        and "SummaryMoveRelearn_ShowCandidateMode(" in toggle_mode
        and "if (!preserveCandidateMode)" in enter
        and "state->allCompatible = FALSE;" in enter,
        "Task-7 toggle default/preservation contract differs",
    )
    require(
        "History SEL:All" in messages
        and "AllCompat SEL:Hist" in messages
        and "History None SEL:All" in messages
        and "AllCompat None SEL:Hist" in messages,
        "Task-7 mode labels are not discoverable and unambiguous",
    )
    move_cursor = body(ui, "SummaryMoveRelearn_MoveListCursor")
    require(
        "state->candidateCursor++" in move_cursor
        and "state->candidateCursor >= state->candidateCount" in move_cursor
        and "SUMMARY_VISIBLE_CANDIDATES" in move_cursor,
        "candidate cursor lacks bounded wrap/scroll behavior",
    )

    slot = body(ui, "SummaryMoveRelearn_HandleSlot")
    pulse_border = body(ui, "SummaryMoveRelearn_DrawRowBorder")
    pulse_phase = body(ui, "SummaryMoveRelearn_DrawSlotPhase")
    pulse_tick = body(ui, "SummaryMoveRelearn_TickPulse")
    pulse_stop = body(ui, "SummaryMoveRelearn_StopPulse")
    commit = body(ui, "SummaryMoveRelearn_Commit")
    end = body(ui, "SummaryMoveRelearn_End")
    finish_close = body(ui, "SummaryMoveRelearn_FinishClose")
    play_menu_se = body(ui, "SummaryMoveRelearn_PlayMenuSE")
    play_more_se = body(ui, "SummaryMoveRelearn_PlayMoreSE")
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
        "SUMMARY_PULSE_FRAMES" in pulse_tick
        and "state->pulseIncoming = !state->pulseIncoming;" in pulse_tick
        and "#define SUMMARY_BORDER_GREEN             9" in ui
        and "#define SUMMARY_BORDER_RED               5" in ui
        and "SUMMARY_BORDER_GREEN" in pulse_phase
        and "SUMMARY_BORDER_RED" in pulse_phase
        and pulse_border.count("FillWindowPixelRect(") == 4
        and "state->pulseActive = FALSE;" in pulse_stop
        and slot.count("SummaryMoveRelearn_StopPulse(") >= 3
        and "NEW-GRN A:Pick" in messages
        and "OLD-RED A:Pick" in messages,
        "replacement pulse phase, outline, labels, or cleanup differs",
    )
    require(
        ui.count("PokemonMoveHistory_ReplaceMove(") == 1
        and "PokemonMoveHistory_ReplaceMove(" in commit,
        "permanent mutation is not isolated to the confirmation worker",
    )
    replace_at = commit.index("PokemonMoveHistory_ReplaceMove(")
    dirty_at = commit.index("summary->baseData->pokemonChanged = TRUE;")
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
    navigation_cancel = body(
        ui,
        "SummaryMoveRelearn_CancelForNavigation",
    )
    for cancel_body, label in (
        (end, "end"),
        (list_handler, "list"),
        (navigation_cancel, "navigation"),
    ):
        require(
            "PokemonMoveHistory_ReplaceMove" not in cancel_body
            and "SetBoxMonData" not in cancel_body,
            f"{label} cancellation path can mutate Pokemon/history",
        )
    require(
        "SummaryMoveRelearn_RestoreCache" in end
        and "state->originalArgMove" in end
        and "state->originalCursor" in end
        and "state->mode = SUMMARY_RELEARN_CLOSING;" in end
        and "Summary_CloseMovePane(summary);" in end
        and "Summary_CloseMovePane(summary)" in finish_close
        and "state->mode = SUMMARY_RELEARN_INACTIVE;" in finish_close,
        "cancellation does not restore transient Summary presentation",
    )
    require(
        "PlaySE(sequence);" in play_menu_se
        and "IsSEPlaying(SEQ_SE_DP_KON)" in play_more_se
        and "state->successCueActive = FALSE;" in play_more_se
        and "PlaySE(SEQ_SE_DP_DECIDE);" in play_more_se
        and "SEQ_SE_DP_SELECT" in ui
        and "SEQ_SE_DP_DECIDE" in ui
        and "SEQ_SE_GS_GEARCANCEL" in ui
        and "SEQ_SE_DP_CUSTOM06" in ui
        and commit.count("PlaySE(SEQ_SE_DP_PIRORIRO2);") == 1
        and "PlaySE(SEQ_SE_DP_DECIDE)" not in commit,
        "Summary relearn sound mapping or fast success cue differs",
    )
    require(
        "SummaryMoveRelearn_End(summary, state);" in commit
        and "state->mode = SUMMARY_RELEARN_SUCCESS;" not in commit
        and "SummaryMoveRelearn_PrintStatus(summary, SUMMARY_MSG_SUCCESS);"
        not in commit,
        "confirmed learning does not exit the relearn modal immediately",
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
        and "MON_DATA_SPECIES_EXISTS" in main
        and "MON_DATA_IS_EGG" in main
        and "!PokemonMoveHistoryTask6_IsCanonical(pokemon)" in main
        and main.index(
            "!PokemonMoveHistoryTask6_IsCanonical(pokemon)"
        )
        < main.index("SummaryMoveRelearn_PrintStatus("),
        "entry eligibility omits fail-closed record validation before prompt",
    )
    require(
        "if (pokemon == NULL) {\n"
        "            SummaryMoveRelearn_RejectEntry(summary, state);\n"
        "            return 2;\n"
        "        }" in main,
        "invalid Summary ownership can still delegate into retail lookup",
    )
    pre_entry_checks = re.findall(
        r"if \(!SummaryMoveRelearn_IsValidEntryPokemon\(pokemon\)\) "
        r"\{\s*(?:SummaryMoveRelearn_PlayMenuSE\(\s*state,\s*"
        r"SEQ_SE_DP_CUSTOM06\);\s*)?"
        r"SummaryMoveRelearn_RejectEntry\(summary, state\);"
        r"\s*return 2;\s*\}\s*"
        r"(?:SummaryMoveRelearn_PlayMenuSE\(state, "
        r"SEQ_SE_DP_DECIDE\);\s*)?"
        r"SummaryMoveRelearn_Enter\(summary, state, pokemon, FALSE\);",
        main,
    )
    require(
        len(pre_entry_checks) == 2
        and main.count(
            "if (!SummaryMoveRelearn_IsValidEntryPokemon(pokemon))"
        )
        == 2
        and main.count(
            "SummaryMoveRelearn_Enter(summary, state, pokemon, FALSE);"
        )
        == 2
        and main.count(
            "SummaryMoveRelearn_Enter(summary, state, pokemon, TRUE);"
        )
        == 2,
        "both resume and key/touch entry paths must revalidate immediately",
    )
    success_handler = main[main.index(
        "state->mode == SUMMARY_RELEARN_SUCCESS"
    ):]
    require(
        "SummaryMoveRelearn_PlayMoreSE(state);" in success_handler
        and "SEQ_SE_GS_GEARCANCEL" in success_handler
        and success_handler.index("SEQ_SE_GS_GEARCANCEL")
        < success_handler.index("SummaryMoveRelearn_PlayMoreSE(state);"),
        "success More suppression or Done cancel sound mapping differs",
    )
    for state in (
        "SUMMARY_RELEARN_LIST",
        "SUMMARY_RELEARN_EMPTY",
        "SUMMARY_RELEARN_SLOT",
        "SUMMARY_RELEARN_CONFIRM",
        "SUMMARY_RELEARN_HM_BLOCKED",
        "SUMMARY_RELEARN_SUCCESS",
        "SUMMARY_RELEARN_CLOSING",
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
        and "state->ownerPokemon != pokemon" in main
        and "summary->baseData->move = restoreMove;" in main,
        "identity and position boundary cleanup are not separated",
    )
    require(
        "state->ownerArgs == summary->baseData" in navigation_cancel
        and "state->ownerPos == summary->baseData->pos"
        in navigation_cancel
        and "state->ownerPokemon\n            == "
        "SummaryMoveRelearn_GetCurrentBoxMon(summary)"
        in navigation_cancel
        and "state->resumeAfterSwitch = resumeAfterSwitch;"
        in navigation_cancel,
        "switch cancellation can restore UI cache to the wrong owner",
    )
    owns_touch = body(ui, "SummaryMoveRelearn_OwnsCurrentTouch")
    require(
        "SummaryMoveRelearn_OwnsCurrentTouch(summary, state)" in main
        and "Summary_GetTouchAction(summary)" in main
        and "Summary_GetPokemonSwitchTouch()" in main
        and "touchAction >= 4 && touchAction <= 9" in main
        and "repeatKeys & (PAD_KEY_LEFT | PAD_KEY_RIGHT)" not in main
        and "return Summary_VanillaMainState(summary);" in main
        and "SummaryMoveRelearn_GetTouch(sMoveRowTouchRects)" in owns_touch
        and "SummaryMoveRelearn_GetTouch(sConfirmTouchRects)" in owns_touch
        and "SummaryMoveRelearn_GetTouch(sSuccessTouchRects)" in owns_touch,
        "modal touch switching or disabled left/right contract differs",
    )
    success_dispatch = main[main.index(
        "state->mode == SUMMARY_RELEARN_SUCCESS"
    ):]
    require(
        "newKeys & PAD_BUTTON_B" in success_dispatch
        and "newKeys & (PAD_BUTTON_A | PAD_BUTTON_X)" in success_dispatch
        and "newKeys & (PAD_KEY_UP | PAD_KEY_DOWN)" in success_dispatch
        and "repeatKeys & (PAD_KEY_UP | PAD_KEY_DOWN)"
        not in success_dispatch
        and success_dispatch.count(
            "SummaryMoveRelearn_Enter(summary, state, pokemon, TRUE);"
        )
        == 2
        and "SummaryMoveRelearn_End(summary, state);" in success_dispatch,
        "success controls do not provide More/Done and directional recovery",
    )
    require(
        "if (state->resumeAfterSwitch)" in main
        and "SummaryMoveRelearn_Enter(summary, state, pokemon, FALSE);" in main
        and "state->ownerPokemon = pokemon;" in enter
        and "state->candidateCursor = 0;" in enter
        and "state->candidateTop = 0;" in enter
        and "state->pendingMove = 0;" in enter,
        "new identity does not receive a fresh candidate transaction",
    )
    require(
        "newKeys & PAD_BUTTON_SELECT" in list_handler
        and "repeatKeys & PAD_BUTTON_SELECT" not in list_handler
        and main.count("newKeys & PAD_BUTTON_SELECT") == 1
        and "state->allCompatible = FALSE;" in end
        and "state->allCompatible = FALSE;" in navigation_cancel
        and main.count("state->allCompatible = FALSE;") >= 2,
        "Task-7 new-press isolation or reset boundaries differ",
    )
    for runtime_contract in (
        '"count_negative_one"',
        '"count_zero"',
        '"count_seven"',
        '"limit_zero"',
        '"limit_seven"',
        '"position_six"',
        '"data_type_zero"',
        '"empty_record"',
        '"egg"',
        '"checksum_failure"',
        '"species_1076"',
        '"tentacool_form_31"',
        '"non_pc_box_limit_29"',
        '"position_30"',
        '"post_prompt_species_1076_key"',
        '"post_prompt_tentacool_form_31_touch"',
        '"immediate_post_injection_pre_frame"',
        '"position_30_hash_matches_owner_only_probes"',
        'label=f"party {label} LEFT"',
        'label=f"party {label} RIGHT"',
        'label=f"party {label} switch touch"',
        'label=f"PC {label} LEFT"',
        'label=f"PC {label} RIGHT"',
        'label=f"PC {label} switch touch"',
        '"party_fail_closed"',
        '"pc_fail_closed"',
        '"from_mode": 5',
        '"from_mode": 6',
        '"pc_teardown"',
        '"first_child"',
        '"second_child"',
        "SUMMARY_STATE_EXTENSION_SIZE",
    ):
        require(
            runtime_contract in runtime,
            f"runtime malformed/switch/lifecycle probe missing: "
            f"{runtime_contract}",
        )
    for sealed_runtime_input in (
        '"scripts/launch_summary_move_relearn_runtime.py"',
        '"scripts/verify_summary_move_relearn_runtime.py"',
        '"scripts/pokemon_move_history_build_manifest.py"',
        '"scripts/headless-overworld-test.py"',
        '"scripts/verify_pokemon_move_history_party_integrity.py"',
        '"scripts/summary_move_relearn_protected_spawn.py"',
    ):
        require(
            manifest_builder.count(sealed_runtime_input) == 1,
            f"runtime evidence input is not uniquely sealed: "
            f"{sealed_runtime_input}",
        )
    require(
        "importlib" not in runtime
        and "spec_from_file_location" not in runtime
        and "SourceFileLoader" not in runtime
        and "load_module" not in runtime
        and "BOOTSTRAP_REAUTHENTICATE()" in runtime
        and "BOOTSTRAP_LAUNCHER_PATH" in runtime
        and '"runtime_launcher"' in runtime
        and '"artifact_authentication"' in runtime
        and "final_authentication == authentication" in runtime
        and "arguments.result_json.unlink" not in runtime
        and "probe.get(\"artifact_authentication\")"
        in runtime
        and "evidence.get(\"artifact_authentication\")"
        in runtime
        and "verify_authenticated_result(probe)" in runtime
        and "verify_authenticated_result(evidence)" in runtime
        and "result = authenticate_result(result)" in runtime
        and '"summary-move-relearn-evidence-artifacts-v1"' in runtime
        and '"summary-move-relearn-result-v1"' in runtime
        and "EVIDENCE_ARTIFACTS.reauthenticate()" in runtime
        and '"BOOTSTRAP_LIBDESMUME_PATH"' in runtime
        and "DeSmuME(BOOTSTRAP_LIBDESMUME_PATH)" in runtime
        and "runtime closure changed after result publication" in runtime
        and "runtime closure changed after stdout publication" in runtime
        and "os.replace(temporary_path, path)" in runtime,
        "runtime evidence is not fail-closed against verifier/publication "
        "revision or atomic publication",
    )
    require(
        runtime.count("emu.backup.export_file(") == 1
        and "def export_backup_artifact(" in runtime
        and "def artifact_path(" in runtime
        and "return _atomic_artifact_path(" in runtime
        and '"screenshots": captures' in runtime
        and '"exported_raw_save": str(args.export_raw)' in runtime,
        "runtime screenshot/save evidence bypasses atomic content addressing",
    )
    require(
        launcher.index("_invalidate_results(sys.argv[1:])")
        < launcher.index("import hashlib")
        < launcher.index("_load_authenticated_buffers(")
        < launcher.index("_compile_buffers(")
        and "spec_from_file_location" not in launcher
        and '"SourcelessFileLoader"' in launcher
        and '"zipimporter"' in launcher
        and '"__pycache__" in parts' in launcher
        and "compile(" in launcher
        and "dont_inherit=True" in launcher
        and "optimize=0" in launcher
        and "exec(code, module.__dict__)" in launcher
        and "module.__cached__ = None" in launcher
        and "stream.read() == source" in launcher
        and "expected-runtime-launcher-sha256" in launcher
        and "expected-runtime-verifier-sha256" in launcher,
        "runtime launcher does not invalidate stale evidence before retained-"
        "buffer authentication and pycache-free execution",
    )
    require(
        'sys.pycache_prefix == "/dev/null"' in launcher
        and "sys.dont_write_bytecode" in launcher
        and "sys.flags.isolated == 1" in launcher
        and "sys.flags.ignore_environment == 1" in launcher
        and "sys.flags.no_site == 1" in launcher
        and '"site" not in sys.modules' in launcher
        and "_stage_zero_invalidate_results(sys.argv[1:])" in launcher
        and "posix.unlink(target)" in launcher
        and launcher.index("import sys")
        < launcher.index('sys.pycache_prefix == "/dev/null"')
        < launcher.index("_stage_zero_authenticate(sys.argv[1:])")
        < launcher.index("import os")
        and launcher.index("_stage_zero_tree_record(stdlib.get")
        < launcher.index("import os")
        and '"bytecode_policy"' in launcher
        and '"bytecode_reads_disabled": True' in launcher
        and '"absent_zip_paths"' in launcher
        and '"no_site": True' in launcher
        and '"pycache_prefix": "/dev/null"' in launcher
        and "runtime Python bytecode-bypass policy differs" in launcher
        and "NATIVE_BOOTSTRAP_AUTHENTICATION = _native_bootstrap_gate()"
        in launcher
        and "native bootstrap did not release Python execution" in launcher
        and 'runtime["native_bootstrap"]' in launcher
        and '"BOOTSTRAP_NATIVE_PREFIX": tuple(native_prefix)' in launcher
        and '"BOOTSTRAP_NATIVE_RUNNER"' in launcher
        and '"BOOTSTRAP_NATIVE_CDHASH"' in launcher
        and "run_native_bootstrap" in protected_spawn
        and "POSIX_SPAWN_START_SUSPENDED" in protected_spawn
        and "csops(child, 5" in protected_spawn
        and "liveCDHashText == expectedCDHash" in protected_spawn
        and "liveFlags == expectedFlags" in protected_spawn
        and "killAndReap(&childState)" in protected_spawn
        and "kill(child, SIGCONT)" in protected_spawn
        and "struct ChildState" in protected_spawn
        and "guard child.owned && !child.terminal" in protected_spawn
        and "errno == ECHILD" in protected_spawn
        and "clock_gettime(CLOCK_MONOTONIC" in protected_spawn
        and "waitpid(child.pid, &status, WNOHANG)" in protected_spawn
        and "while childState.owned" in protected_spawn
        and "start_new_session=True" in protected_spawn
        and "os.killpg(process.pid, signal.SIGKILL)" in protected_spawn
        and "process.wait(timeout=CONTROLLER_CLEANUP_TIMEOUT_SECONDS)"
        in protected_spawn
        and "if process.returncode != 0:" in protected_spawn
        and "POSIX_SPAWN_START_SUSPENDED" in protected_spawn_swift
        and "os.execve(" not in launcher
        and "capture_runtime_environment()" in launcher
        and "runtime binding requires -I -S -B -X" in manifest_builder
        and '"bytecode_policy"' in manifest_builder
        and '"bytecode_reads_disabled": True' in manifest_builder
        and '"absent_zip_paths": absent_zip_paths' in manifest_builder
        and "runtime zip import path must be absent" in manifest_builder
        and '"no_site": True' in manifest_builder
        and '"pycache_prefix": os.devnull' in manifest_builder
        and '"isolated": True' in manifest_builder
        and '"ignore_environment": True' in manifest_builder
        and "_validate_binding_modules(stdlib_root)" in manifest_builder
        and '"startup_bootstrap"' in manifest_builder
        and "_PINNED_STAGE_ZERO_LAUNCHER_SHA256" in manifest_builder
        and '"entry": "/tmp/hg-engine-venv/bin/python3"' in manifest_builder
        and '"repo": "/hg-engine"' in manifest_builder
        and '"shared_runtime": None' in manifest_builder
        and "24390712683ee2a599ec3140ad90abd246b8efee9c4782a2deb8f24a9a70d312"
        in manifest_builder
        and manifest_builder.index(
            'tree_record_zero(pinned["stdlib"]["root"])'
        )
        < manifest_builder.index("import argparse")
        and "import importlib" not in launcher
        and 'sys.modules.get("_frozen_importlib")' in launcher
        and launcher.index(
            "runtime_environment = _primitive_runtime_authentication(document)"
        )
        < launcher.index("compiled = _compile_buffers(buffers, paths)")
        < launcher.index("manifest_module = _execute_module(")
        and "_install_retained_package_loader(" in launcher
        and '"PIL"' in launcher
        and "runtime module differs from publication manifest" in launcher
        and "loaded mutable native image is outside sealed closure" in launcher
        and "runtime libdesmume changed across native load" in launcher
        and "_authenticate_loaded_python_modules(" in launcher
        and 'python["startup_bootstrap"]' in launcher
        and "_native_bootstrap_runtime_record()" in manifest_builder
        and "SUMMARY_MOVE_RELEARN_BOOTSTRAP_SELF_SHA256" in manifest_builder
        and "native bootstrap has a non-OS runtime dependency"
        in manifest_builder
        and "runtime import path/finder closure changed during execution"
        in launcher
        and '"BOOTSTRAP_LIBDESMUME_PATH": libdesmume_path' in launcher
        and "require_bound_runtime=True" in launcher
        and "create_desmume()" in headless
        and "create_desmume()" in party_verifier
        and "os.path.abspath(sys.executable)" in headless
        and "os.path.abspath(venv_python)" in headless
        and "os.path.abspath(sys.executable)" in party_verifier
        and "os.path.abspath(venv_python)" in party_verifier,
        "runtime launcher does not independently seal Python/DeSmuME/Pillow/"
        "native execution before retained-buffer helpers",
    )
    bind_index = build_wrapper.index("--bind-runtime")
    verify_bound_index = build_wrapper.index("--require-bound-runtime")
    delta_index = build_wrapper.index("./scripts/copy-test-nds-to-delta.sh")
    require(
        build_wrapper.count("--bind-runtime") == 1
        and build_wrapper.count("--require-bound-runtime") == 1
        and build_wrapper.count("/usr/bin/env -i") >= 3
        and build_wrapper.count("protected_native_bootstrap \\") == 2
        and build_wrapper.count("--expected-inventory-sha256") == 2
        and build_wrapper.count("--expected-self-sha256") == 2
        and 'runtime_python="$PWD/.venv/bin/python3"' in build_wrapper
        and "build_summary_move_relearn_native_bootstrap.sh" in build_wrapper
        and f'native_bootstrap_expected_sha256="{NATIVE_BOOTSTRAP_EXPECTED_SHA256}"'
        in build_wrapper
        and f'native_bootstrap_expected_cdhash="{NATIVE_BOOTSTRAP_EXPECTED_CDHASH}"'
        in build_wrapper
        and "authenticate_native_bootstrap" in build_wrapper
        and "SMR_PROTECTED_EXPECTED_CDHASH" in build_wrapper
        and "POSIX_SPAWN_START_SUSPENDED" not in build_wrapper
        and "/usr/bin/swift -" in build_wrapper
        and 'entitlements=$(/usr/bin/codesign -d --entitlements -'
        in build_wrapper
        and bind_index < verify_bound_index < delta_index,
        "managed build does not bind and verify the host runtime before Delta "
        "publication",
    )
    require(
        "AUTHENTICATED_HEADLESS" in party_verifier
        and "spec_from_file_location" not in party_verifier
        and "SourcelessFileLoader" not in party_verifier
        and "pycache_prefix=/dev/null" in party_verifier
        and "compile(" in party_verifier
        and "module.__cached__ = None" in party_verifier,
        "party-integrity helper can reload unauthenticated cached bytecode",
    )
    require(
        "subprocess.Popen" not in runtime
        and "multiprocessing" not in runtime
        and runtime.count("BOOTSTRAP_NATIVE_RUNNER(") == 2
        and runtime.count('            "-I",') == 2
        and runtime.count('            "-S",') == 2
        and runtime.count('            "-B",') == 2
        and runtime.count('            "-X",') == 2
        and runtime.count('            "pycache_prefix=/dev/null",') == 2
        and runtime.count("*BOOTSTRAP_NATIVE_PREFIX") == 2
        and "**os.environ" not in runtime
        and runtime.count(
            "child_environment=dict(BOOTSTRAP_CHILD_ENVIRONMENT)"
        ) == 2,
        "runtime child evidence is no longer blocking and serialized",
    )
    route_start = runtime.index("def open_retail_daycare_lady(")
    route_end = runtime.index(
        "\ndef open_retail_daycare_party_chooser(", route_start
    )
    daycare_route = runtime[route_start:route_end]
    cancel_start = runtime.index("def task6_daycare_cancel_evidence(")
    cancel_end = runtime.index(
        "\ndef task6_daycare_sanitize_evidence(", cancel_start
    )
    daycare_cancel = runtime[cancel_start:cancel_end]
    daycare_start = runtime.index("def task6_daycare_sanitize_evidence(")
    daycare_end = runtime.index(
        "\ndef task6_daycare_reload_evidence(", daycare_start
    )
    daycare_runtime = runtime[daycare_start:daycare_end]
    require(
        "register_exec(FUNC_EVENT_SET_SCRIPT, script_started)"
        in daycare_route
        and "script_hits == [9501]" in daycare_route
        and "(331, 0, 3, 12)" in daycare_route
        and "(331, 0, 3, 7, 0)" in daycare_route,
        "runtime daycare route does not authenticate the retail lady boundary",
    )
    require(
        daycare_cancel.index("open_retail_daycare_party_chooser(emu)")
        < daycare_cancel.index("before_party = wait_party_locked(emu)")
        < daycare_cancel.index('HEADLESS.tap_key(emu, "B", 24, 360)')
        and "after_party == before_party" in daycare_cancel
        and "after_daycare == before_daycare" in daycare_cancel
        and "after_metadata == before_metadata" in daycare_cancel,
        "runtime daycare cancel is not byte-exact at the chooser boundary",
    )
    for fragment in (
        'HEADLESS.tap_key(emu, "DOWN", 8, 60)',
        'HEADLESS.tap_key(emu, "A", 24, 90)',
        'HEADLESS.tap_key(emu, "A", 24, 900)',
        "deposited_moves == (57, 48, 282, 109)",
        "selected_moves == (57, 48, 109, 282)",
        "deposited_pp[3] == TASK6_DAYCARE_DEPOSITED_NEW_PP",
        "selected_pp[3] == TASK6_DAYCARE_PARTY_NEW_PP",
        "persisted_deposited_pp[3] == TASK6_DAYCARE_DEPOSITED_NEW_PP",
        "persisted_selected_pp[3] == TASK6_DAYCARE_PARTY_NEW_PP",
        "party_history_before + (282,)",
        "deposited_history_before + (109,)",
        "after_revision == before_revision + 2",
        "unrelated history record",
        "selected_persisted_history(persisted_raw)",
    ):
        require(
            fragment in daycare_runtime,
            f"runtime daycare sanitizer evidence lost {fragment}",
        )
    require(
        '"task6_daycare_cancel"' in runtime
        and '"task6_daycare_sanitize"' in runtime
        and '"task6_daycare_reload"' in runtime
        and "daycare_cancel_evidence = isolated_scenario_evidence("
        in runtime
        and "daycare_sanitize_evidence = isolated_scenario_evidence("
        in runtime
        and "daycare_reload_evidence = isolated_scenario_evidence("
        in runtime
        and '"task6_daycare_cancel_evidence": daycare_cancel_evidence'
        in runtime
        and '"task6_daycare_sanitize_evidence": daycare_sanitize_evidence'
        in runtime
        and '"task6_daycare_reload_evidence": daycare_reload_evidence'
        in runtime,
        "task-6 retail daycare evidence is not included in authenticated output",
    )
    walker_rom_start = runtime.index("def task6_pokewalker_rom_evidence(")
    walker_rom_end = runtime.index(
        "\n\ndef run_isolated_scenario(", walker_rom_start
    )
    walker_rom = runtime[walker_rom_start:walker_rom_end]
    for fragment in (
        "def invoke_packaged_mailbox_operation(",
        "TASK6_POKEWALKER_STAGE_ENTRY = 0x023BD420",
        "TASK6_POKEWALKER_ACK_FIRST_ENTRY = 0x023BD480",
        "TASK6_POKEWALKER_ACK_SECOND_ENTRY = 0x023BD488",
        "TASK6_POKEWALKER_RECOVERY_ENTRY = 0x023BD490",
        "TASK6_POKEWALKER_DIAGNOSTIC_POLL = 0x023BD4A0",
        "TASK6_POKEWALKER_MAILBOX = 0x023BD4A8",
        "TASK6_POKEWALKER_MAILBOX_MAGIC = 0x36574B50",
        "register_exec(entry, entry_hit)",
        "register_exec(TASK6_POKEWALKER_DIAGNOSTIC_POLL, poll_hit)",
        "TASK6_POKEWALKER_MAILBOX + 0x00",
        "invoke_packaged_mailbox_operation(",
        "complete_store_metadata_exact",
        "full_319_cancel",
        "oldest_record_exact",
        "second_revision_inert",
        "all_unrelated_records_exact",
        "diagnostic_mailbox_restored",
        "zero_magic_retail_inert",
        '"host_pc_or_register_write": False',
        "party_pc_history_restored",
        '"evidence_kind": "ROM-executed packaged task-6 transaction boundary"',
    ):
        require(
            fragment in runtime if fragment.startswith("def invoke_")
            or fragment.startswith("TASK6_")
            or fragment.startswith("register")
            or fragment.startswith("emu.")
            or fragment.startswith("registers.")
            else fragment in walker_rom,
            f"ROM-executed Pokewalker evidence lost {fragment}",
        )
    require(
        "set_next_instruction" not in runtime
        and "registers.r15" not in runtime
        and "registers.cpsr" not in runtime,
        "ROM diagnostic reintroduced unsafe host PC/CPSR control",
    )
    require(
        '"task6_pokewalker_rom"' in runtime
        and "pokewalker_rom_evidence = isolated_scenario_evidence(" in runtime
        and '"task6_pokewalker_rom_evidence": pokewalker_rom_evidence'
        in runtime,
        "ROM-executed Pokewalker evidence is not in authenticated output",
    )
    require(
        '"--expected-probe-raw-sha256"' in runtime
        and "raw_sha256 = hashlib.sha256(raw_before).hexdigest()" in runtime
        and 'evidence.get("probe_raw_sha256") == raw_sha256' in runtime
        and "hashlib.sha256(raw_path.read_bytes()).hexdigest() == raw_sha256"
        in runtime
        and '"exported_raw_sha256": persisted_raw_sha256' in runtime
        and '"sha256": hashlib.sha256(daycare_raw).hexdigest()' in runtime,
        "controlled task-6 fixtures are not parent/child content-pinned",
    )
    require(
        "def call_thumb_function(" not in runtime
        and "def task6_actual_hook_evidence(" not in runtime
        and "def task6_transaction_surrogate_evidence(" not in runtime,
        "runtime verifier retained an obsolete synthetic hook/model entry",
    )
    surrogate_start = runtime.index(
        "def task6_serialization_surrogate_evidence("
    )
    surrogate_end = runtime.index(
        "\ndef target_semantic_diff(", surrogate_start
    )
    task6_surrogate = runtime[surrogate_start:surrogate_end]
    for fragment in (
        "controlled_box_record(",
        "validate_box_checksum(record",
        "valid_pc_copies(",
        "history_image_for_mirror(",
        "valid_history_image(",
        "assert_serialized_path(",
        "trade_reparse_sha256",
        "form_reparse_sha256",
        "hatch_reparse_sha256",
        "not destination_accepts_trade",
        "walker_recovered == controlled_raw",
        "walker_state_fingerprint(",
        "walker_stage(missing_cancel, pending_box)",
        "walker_discard(missing_cancel)",
        "walker_stage(full_cancel, pending_box)",
        "HISTORY_RECORD_COUNT",
        "walker_ack(acknowledged)",
        '"missing_record_cancel_image_exact": True',
        '"full_319_cancel_image_exact": True',
        '"ack_commits_pending_once": True',
        '"duplicate_ack_inert": True',
        "history_identity_count(",
        "validate_all_boxed_checksums(",
        '"non-probative source-exact serialization oracle"',
        '"non-probative Python oracle; see ROM evidence"',
    ):
        require(
            fragment in task6_surrogate,
            f"authenticated task-6 serialization evidence lost {fragment}",
        )
    require(
        "task6_serialization_evidence = "
        "task6_serialization_surrogate_evidence(" in runtime
        and '"task6_serialization_surrogate_evidence":'
        in runtime,
        "task-6 serialized trade/form/egg/Pokéwalker evidence is not output",
    )
    require(
        "PCStorage_SetBoxModified" not in ui
        and storage.count("PCStorage_SetBoxModified(storage, boxno)") >= 3,
        "Summary bypasses PC ownership or canonical storage paths lost dirtying",
    )
    observe = body(history, "PokemonMoveHistory_ObserveSnapshot")
    capture = body(history, "PokemonMoveHistory_CaptureSnapshotImpl")
    require(
        "snapshot->personality =" in capture
        and "snapshot->otId =" in capture
        and "snapshot->personality" in observe
        and "snapshot->otId" in observe,
        "normal transfer continuity is not anchored to PID/OTID history identity",
    )

    require(
        "Summary_MoveRelearnDispatcher 02088494" not in hooks
        and "arm9 Summary_IVEV 02088B60 1" in hooks
        and "arm9 Summary_Entry_Hook 0208D2C4 1" in hooks,
        "Summary hook does not coexist with retail extensions",
    )
    require(
        ".org 0x02088494" in armips_patch
        and "SummaryMoveRelearn_Entry equ 0x023C0408" in armips_patch
        and "bl SummaryMoveRelearn_Entry" in armips_patch,
        "state-2 interception is not an exact four-byte Thumb BL",
    )
    require(
        "arm9 02088414 D8 0B 00 00" in patches
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
        "Summary relearn still consumes resident overlay-129 dispatcher space",
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
        and ui.count("Summary_UpdateMoveCursorSprite(summary)") >= 1
        and "Summary_CloseMovePane(summary)" in ui
        and "{ 136, 151, 8, 41 }" in ui
        and "{ 136, 151, 45, 128 }" in ui
        and "{ 136, 151, 8, 32 }" in ui
        and "{ 136, 151, 36, 128 }" in ui
        and "{ 136, 151, 40, 81 }" in ui
        and "{ 136, 151, 84, 128 }" in ui
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
        "Done! A:More B:Done",
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
        and "sConfirmTouchRects" in ui
        and "sSuccessTouchRects" in ui,
        "entry/list/slot/confirmation touch controls are incomplete",
    )
    render_slot = body(ui, "SummaryMoveRelearn_RenderSlot")
    render_phase = body(ui, "SummaryMoveRelearn_DrawSlotPhase")
    require(
        "summary->pokemonData.moves[state->selectedSlot] ="
        "\n            state->pendingMove;" in render_phase
        and "GetMoveMaxPP(state->pendingMove, 0)" in render_phase
        and "summary->pokemonData.curPP[state->selectedSlot] = pp;"
        in render_phase
        and "summary->pokemonData.maxPP[state->selectedSlot] = pp;"
        in render_phase
        and render_phase.index("Summary_UpdateMoveSelection(summary);")
        < render_phase.rindex("Summary_DrawMoveRows(summary);"),
        "slot preview is not an authoritative inline full-PP move row",
    )
    require(
        "SUMMARY_MSG_PULSE_NEW" in render_phase
        and "SUMMARY_MSG_PULSE_OLD" in render_phase,
        "slot selection does not render explicit Pick/Back controls",
    )
    require(
        ui.count("{ 165, 188, 190, 249 }") == 4
        and "{ 165, 188, 8, 55 }" not in ui
        and "{ 165, 188, 56, 128 }" not in ui,
        "lower page-button row aliases a modal label action",
    )
    require(
        main.count("if (touch == 0 || touch == 1)") == 1
        and "SummaryMoveRelearn_GetTouch(sSuccessTouchRects)" in main
        and main.count("if (touch == 0)") >= 3
        and main.count("touch == 1 || touch == 2") >= 3,
        "empty or success action/Back touch ownership differs",
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
        main.count("SummaryMoveRelearn_GetTouch(sConfirmTouchRects)") == 2
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
        and "SummaryMoveRelearn_SetMovePane(summary, TRUE)" in show_mode
        and "Summary_CloseMovePane(summary)" in end
        and "Summary_CloseMovePane(summary)" in finish_close
        and "SummaryMoveRelearn_SetMovePane(summary, FALSE)" in main,
        "retail detail pane is not shown and restored around modal ownership",
    )


def bootstrap_host_contracts(root: Path) -> None:
    native_source_path = (
        root / "scripts/summary_move_relearn_native_bootstrap.c"
    )
    native_build_path = (
        root / "scripts/build_summary_move_relearn_native_bootstrap.sh"
    )
    native_inventory_path = (
        root / "scripts/summary_move_relearn_native_inventory.txt"
    )
    native_generator_path = (
        root / "scripts/generate_summary_move_relearn_native_inventory.py"
    )
    native_source = native_source_path.read_text()
    native_build = native_build_path.read_text()
    native_generator = native_generator_path.read_text()
    require(
        all(
            token in native_source
            for token in (
                "SMR_EXPECTED_INVENTORY_SHA256",
                "O_NOFOLLOW_ANY",
                "EVFILT_VNODE",
                "NOTE_WRITE",
                "NOTE_RENAME",
                "SUMMARY_MOVE_RELEARN_PYTHON_READY_V1",
                "SUMMARY_MOVE_RELEARN_NATIVE_GO_V1",
                "validate_exec_chain",
                "validate_python_command",
                'strcmp(command[1], "-I")',
                'strcmp(command[2], "-S")',
                'strcmp(command[3], "-B")',
                'strcmp(command[4], "-X")',
                'strcmp(command[5], "pycache_prefix=/dev/null")',
                '"/scripts/launch_summary_move_relearn_runtime.py"',
                '"/scripts/pokemon_move_history_build_manifest.py"',
                "require_descriptor_capacity",
                "digest_directory",
                "AT_SYMLINK_NOFOLLOW",
                "MAX_DRAIN_EVENTS",
                "--self-test-event-backlog",
                "reauthenticate_inventory",
                "execve(inventory->alias->path",
                "collect_result_targets",
                "invalidate_result_path",
                "terminate_and_reap",
                "WNOHANG | WUNTRACED",
                "F_SETNOSIGPIPE",
                "ChildState",
            )
        )
        and "-Werror -pedantic" in native_build
        and "-Wl,-no_uuid" in native_build
        and "--options runtime,restrict,library,hard,kill" in native_build
        and "flags=0x12b02(adhoc,hard,kill,restrict,library-validation,runtime)"
        in native_build
        and "/usr/bin/codesign --verify --strict" in native_build
        and "/usr/lib/libSystem" in native_build,
        "native pre-Python trust-anchor source/build contract differs",
    )
    require(
        native_source.index("append_anchor(&inventory, options.inventory_path")
        < native_source.rindex("validate_parent_records(&inventory)"),
        "dynamic bootstrap anchors are not parent-validated",
    )
    require(
        "--print-self-record" not in native_build
        and "expected_self_sha256=$1" in native_build
        and "expected_cdhash=$2" in native_build
        and 'authenticate_binary "$temporary_path"' in native_build
        and 'authenticate_binary "$output_path"' in native_build
        and 'candidate_size=$(/usr/bin/stat' in native_build
        and '"$candidate_size" "$expected_self_sha256"' in native_build
        and "entitlement set is nonempty" in native_build,
        "native bootstrap publication still derives identity from execution",
    )
    require(
        "summary-move-relearn-native-bootstrap-inventory-v2" in native_generator
        and "DIRECTORY_DIGEST_DOMAIN" in native_generator
        and "add_directory_graph" in native_generator
        and "unsupported inventory graph symlink" in native_generator
        and "follow_symlinks=False" in native_generator,
        "native directory-membership inventory generator differs",
    )
    require(
        'add_membership_directory(records, REPO / "build/summary_move_relearn_native")'
        in native_generator,
        "published bootstrap parent is not an authored membership record",
    )
    if sys.platform != "darwin":
        return
    require(
        native_inventory_path.is_file(),
        "native bootstrap inventory is absent",
    )
    runtime_python = root / ".venv/bin/python3"
    require(runtime_python.is_file(), "repository runtime Python is absent")
    prebuild_sha256 = (
        hashlib.sha256(
            (
                root
                / "build/summary_move_relearn_native/"
                "summary_move_relearn_native_bootstrap"
            ).read_bytes()
        ).hexdigest()
        if (
            root
            / "build/summary_move_relearn_native/"
            "summary_move_relearn_native_bootstrap"
        ).is_file()
        else None
    )
    native_build_result = subprocess.run(
        [
            str(native_build_path),
            NATIVE_BOOTSTRAP_EXPECTED_SHA256,
            NATIVE_BOOTSTRAP_EXPECTED_CDHASH,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    require(
        native_build_result.returncode == 0,
        "native bootstrap did not compile: "
        + native_build_result.stderr[-1000:],
    )
    native_fields = native_build_result.stdout.strip().split()
    require(
        len(native_fields) == 4
        and native_fields[0].isdigit()
        and re.fullmatch(r"[0-9a-f]{64}", native_fields[1]) is not None
        and re.fullmatch(r"[0-9a-f]{64}", native_fields[2]) is not None
        and re.fullmatch(r"[0-9a-f]{40}", native_fields[3]) is not None
        and native_fields[1] == NATIVE_BOOTSTRAP_EXPECTED_SHA256
        and native_fields[3] == NATIVE_BOOTSTRAP_EXPECTED_CDHASH,
        "native bootstrap publication record is malformed",
    )
    native_bootstrap = (
        root
        / "build/summary_move_relearn_native/"
        "summary_move_relearn_native_bootstrap"
    )
    native_self_sha256 = native_fields[1]
    native_inventory_sha256 = native_fields[2]
    native_cdhash = native_fields[3]
    require(
        hashlib.sha256(native_bootstrap.read_bytes()).hexdigest()
        == native_self_sha256
        and hashlib.sha256(native_inventory_path.read_bytes()).hexdigest()
        == native_inventory_sha256,
        "native bootstrap publication digest differs",
    )
    repeated_build = subprocess.run(
        [
            str(native_build_path),
            NATIVE_BOOTSTRAP_EXPECTED_SHA256,
            NATIVE_BOOTSTRAP_EXPECTED_CDHASH,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    repeated_fields = repeated_build.stdout.strip().split()
    require(
        repeated_build.returncode == 0
        and repeated_fields == native_fields
        and (prebuild_sha256 is None or prebuild_sha256 == native_self_sha256)
        and hashlib.sha256(native_bootstrap.read_bytes()).hexdigest()
        == native_self_sha256,
        "native bootstrap compilation is not reproducible",
    )
    uuid_probe = subprocess.run(
        ["/usr/bin/otool", "-l", str(native_bootstrap)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    require(
        uuid_probe.returncode == 0 and "LC_UUID" not in uuid_probe.stdout,
        "native bootstrap contains a non-reproducible Mach-O UUID",
    )
    inventory_lines = native_inventory_path.read_text().splitlines()
    inventory_records = [
        line.split("\t", 3)
        for line in inventory_lines[1:]
        if len(line.split("\t", 3)) == 4
    ]
    membership_paths = {
        fields[3] for fields in inventory_records if fields[0] == "M"
    }
    regular_parent_paths = {
        str(Path(fields[3]).parent)
        for fields in inventory_records
        if fields[0] in {"F", "E"}
    }
    def graph_directories(graph_root: Path, prune: set[str]) -> set[str]:
        pending = [graph_root.resolve()]
        discovered: set[str] = set()
        while pending:
            directory = pending.pop()
            require(str(directory) not in discovered, "directory graph cycles")
            discovered.add(str(directory))
            with os.scandir(directory) as entries:
                for entry in entries:
                    metadata = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(metadata.st_mode) and entry.name not in prune:
                        pending.append(directory / entry.name)
                    else:
                        require(
                            stat.S_ISREG(metadata.st_mode)
                            or stat.S_ISLNK(metadata.st_mode)
                            or (
                                stat.S_ISDIR(metadata.st_mode)
                                and entry.name in prune
                            ),
                            f"unsupported directory graph member: {entry.path}",
                        )
        return discovered

    base = Path(sys.base_prefix).resolve()
    stdlib = base / "lib/python3.10"
    site_packages = root / ".venv/lib/python3.10/site-packages"
    expected_membership_paths = {
        str(root / ".venv"),
        str(root / "scripts"),
        str(root / "build/summary_move_relearn_native"),
        str(base),
        str(base / "lib"),
    }
    expected_membership_paths.update(
        graph_directories(stdlib, {"__pycache__", "site-packages"})
    )
    expected_membership_paths.update(
        graph_directories(site_packages / "desmume", {"__pycache__"})
    )
    expected_membership_paths.update(
        graph_directories(site_packages / "PIL", {"__pycache__"})
    )
    expected_membership_paths.update(regular_parent_paths)
    with tempfile.TemporaryDirectory(prefix="summary-relearn-inventory-") as generated_dir:
        generated_inventory = Path(generated_dir) / "inventory.txt"
        generated = subprocess.run(
            [
                str(runtime_python),
                "-I",
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
                str(native_generator_path),
                "--output",
                str(generated_inventory),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        require(
            generated.returncode == 0
            and generated_inventory.read_bytes() == native_inventory_path.read_bytes(),
            "committed native inventory differs from exact clean regeneration",
        )
    require(
        inventory_lines[0]
        == "summary-move-relearn-native-bootstrap-inventory-v2"
        and membership_paths == expected_membership_paths,
        "native directory-membership inventory coverage differs",
    )
    require(
        all(str(Path(fields[3]).parent) in membership_paths
            for fields in inventory_records if fields[0] in {"F", "E"}),
        "native regular/executable parent membership differs",
    )
    for _ in range(3):
        backlog_probe = subprocess.run(
            [str(native_bootstrap), "--self-test-event-backlog"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        require(
            backlog_probe.returncode == 0
            and "same-kqueue first-batch=64" in backlog_probe.stderr
            and "vnode event" in backlog_probe.stderr,
            "native same-kqueue event-backlog drain self-test failed",
        )
    require(
        "calibration_queue" not in native_source,
        "native backlog self-test still uses a different calibration queue",
    )
    signature_probe = subprocess.run(
        ["/usr/bin/codesign", "-d", "--verbose=4", str(native_bootstrap)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    signature_text = signature_probe.stdout + signature_probe.stderr
    try:
        signature_provenance = native_code_signature_provenance(native_bootstrap)
    except ValueError as error:
        raise SystemExit(
            "Summary move relearn verification failed: native bootstrap "
            f"signature provenance differs: {error}"
        ) from error
    require(
        signature_probe.returncode == 0
        and "flags=0x12b02(adhoc,hard,kill,restrict,library-validation,runtime)"
        in signature_text
        and "Runtime Version=" in signature_text,
        "native bootstrap pre-main restricted signature differs",
    )
    require(
        signature_provenance["entitlements"]
        == {
            "policy": "exactly-empty",
            "keys": [],
            "xml_slot": False,
            "der_slot": False,
            "codesign_stdout": {
                "size": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
            },
        }
        and signature_provenance["code_directory"]["sha256"][:40]
        == native_cdhash
        and f"CDHash={native_cdhash}" in signature_text,
        "native bootstrap exact-empty entitlement policy differs",
    )
    native_prefix = [
        str(native_bootstrap),
        "--inventory",
        str(native_inventory_path.resolve()),
        "--expected-inventory-sha256",
        native_inventory_sha256,
        "--expected-self-sha256",
        native_self_sha256,
    ]
    launcher_path = (
        root / "scripts/launch_summary_move_relearn_runtime.py"
    )
    launcher = types.ModuleType("summary_relearn_launcher_fixture")
    launcher.__file__ = str(launcher_path)
    launcher.__cached__ = None
    launcher.__loader__ = None
    launcher.__package__ = ""
    launcher.__spec__ = None
    exec(
        compile(
            launcher_path.read_bytes(),
            str(launcher_path),
            "exec",
            dont_inherit=True,
            optimize=0,
        ),
        launcher.__dict__,
    )
    def colocated_cache_path(source: Path) -> Path:
        return (
            source.parent
            / "__pycache__"
            / f"{source.stem}.{sys.implementation.cache_tag}.pyc"
        )

    source_only_environment = {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "SDL_AUDIODRIVER": "dummy",
    }
    source_only_probe = subprocess.run(
        [
            str(runtime_python),
            "-I",
            "-S",
            "-B",
            "-X",
            "pycache_prefix=/dev/null",
            "-v",
            "-c",
            "import hashlib, json, os, subprocess, tempfile, types",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=source_only_environment,
    )
    require(
        source_only_probe.returncode == 0
        and ".pyc" not in source_only_probe.stderr
        and "hashlib.py" in source_only_probe.stderr
        and "json/__init__.py" in source_only_probe.stderr,
        "runtime interpreter did not bypass filesystem pycache from startup",
    )

    def expect_failure(
        exception_type: type[BaseException],
        callback: object,
        label: str,
    ) -> None:
        try:
            callback()
        except exception_type:
            return
        except BaseException as error:
            require(
                False,
                f"{label} raised {type(error).__name__}, not "
                f"{exception_type.__name__}",
            )
        require(False, f"{label} did not fail closed")

    def invalidate_stale(
        stale: Path,
        callback: object,
        exception_type: type[BaseException],
        label: str,
    ) -> None:
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text('{"status": "passing-stale-evidence"}\n')
        invalidated = launcher._invalidate_results(
            [
                f"--result-json={stale}",
                "--result-json",
                str(stale),
            ]
        )
        require(
            invalidated
            == (os.path.realpath(os.path.abspath(stale)),)
            and not stale.exists(),
            f"{label} did not invalidate stale evidence first",
        )
        expect_failure(exception_type, callback, label)
        require(
            not stale.exists(),
            f"{label} recreated stale evidence after failure",
        )

    def make_fixture(
        fixture_root: Path,
        *,
        source_overrides: dict[str, bytes] | None = None,
        production_launcher: bool = False,
    ) -> tuple[
        Path,
        Path,
        dict[str, bytes],
        dict[str, Path],
        str,
        str,
        str,
    ]:
        fixture_root.mkdir(parents=True, exist_ok=True)
        sources: dict[str, bytes] = {}
        paths: dict[str, Path] = {}
        for index, relative in enumerate(
            launcher.AUTHENTICATED_SOURCES
        ):
            if production_launcher and relative == launcher.LAUNCHER_RELATIVE:
                source = launcher_path.read_bytes()
            else:
                source = f"FIXTURE_VALUE = {index}\n".encode()
            if source_overrides and relative in source_overrides:
                source = source_overrides[relative]
            path = fixture_root.joinpath(*relative.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source)
            sources[relative] = source
            paths[relative] = path
        rom = fixture_root / "fixture.nds"
        rom.write_bytes(b"authenticated fixture ROM")
        inputs = {
            relative: launcher._bytes_record(source)
            for relative, source in sources.items()
        }
        document = {
            "build_context": {},
            "inputs": inputs,
            "outputs": {
                "packaged_rom": {
                    "path": launcher.PACKAGED_ROM_LOGICAL_PATH,
                    **launcher._path_record(str(rom)),
                }
            },
            "runtime_environment": {
                "schema": (
                    "summary-move-relearn-runtime-environment-v1"
                ),
                "status": "unbound",
            },
            "schema": launcher.SCHEMA,
            "tools": {},
        }
        manifest = fixture_root / "publication-manifest.json"
        manifest_bytes = (
            json.dumps(document, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode()
        manifest.write_bytes(manifest_bytes)
        return (
            manifest,
            rom,
            sources,
            paths,
            hashlib.sha256(manifest_bytes).hexdigest(),
            hashlib.sha256(
                sources[launcher.LAUNCHER_RELATIVE]
            ).hexdigest(),
            hashlib.sha256(
                sources[launcher.VERIFIER_RELATIVE]
            ).hexdigest(),
        )

    def subprocess_failure_fixture(
        fixture_root: Path,
        *,
        source_overrides: dict[str, bytes] | None = None,
        mutate: object | None = None,
        arguments_only: bool = False,
        environment: dict[str, str] | None = None,
    ) -> None:
        sentinel = fixture_root / "runtime-executed"
        worker = (
            "from pathlib import Path\n"
            f"Path({str(sentinel)!r}).write_text('executed')\n"
        ).encode()
        overrides = {
            launcher.VERIFIER_RELATIVE: worker,
            **(source_overrides or {}),
        }
        (
            manifest,
            rom,
            _,
            paths,
            manifest_sha,
            launcher_sha,
            verifier_sha,
        ) = make_fixture(
            fixture_root,
            source_overrides=overrides,
            production_launcher=True,
        )
        if mutate is not None:
            mutate(paths)
        stale = fixture_root / "runtime-result.json"
        stale.write_text('{"status": "passing-stale-evidence"}\n')
        command = [
            *native_prefix,
            "--invalidate-result",
            str(stale),
            "--",
            str(runtime_python),
            "-I",
            "-S",
            "-B",
            "-X",
            "pycache_prefix=/dev/null",
            str(paths[launcher.LAUNCHER_RELATIVE]),
            "--result-json",
            str(stale),
        ]
        if not arguments_only:
            command.extend(
                (
                    "--rom",
                    str(rom),
                    "--publication-manifest",
                    str(manifest),
                    "--expected-publication-manifest-sha256",
                    manifest_sha,
                    "--expected-runtime-launcher-sha256",
                    launcher_sha,
                    "--expected-runtime-verifier-sha256",
                    verifier_sha,
                )
            )
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=(
                source_only_environment
                if environment is None
                else environment
            ),
        )
        require(
            completed.returncode != 0,
            f"{fixture_root.name} launcher fixture did not fail",
        )
        require(
            not stale.exists(),
            f"{fixture_root.name} launcher fixture retained stale result",
        )
        require(
            not sentinel.exists(),
            f"{fixture_root.name} launcher fixture executed runtime",
        )

    with tempfile.TemporaryDirectory(
        prefix="summary-relearn-bootstrap-"
    ) as temporary:
        temp = Path(temporary)

        protected_module_path = (
            root / "scripts/summary_move_relearn_protected_spawn.py"
        )
        protected_module = types.ModuleType(
            "summary_relearn_protected_spawn_fixture"
        )
        protected_module.__file__ = str(protected_module_path)
        exec(
            compile(
                protected_module_path.read_bytes(),
                str(protected_module_path),
                "exec",
                dont_inherit=True,
                optimize=0,
            ),
            protected_module.__dict__,
        )
        delimiter_result = temp / "post-delimiter-result.json"
        delimiter_result.write_text('{"status":"preserved"}\n')
        protected_module._invalidate_explicit_results(
            [
                str(native_bootstrap),
                "--",
                str(launcher_path),
                "--invalidate-result",
                str(delimiter_result),
            ]
        )
        require(
            delimiter_result.read_text() == '{"status":"preserved"}\n',
            "protected runner treated an entry argument as a native control",
        )

        original_subprocess = protected_module.subprocess
        original_killpg = protected_module.os.killpg

        class NonzeroController:
            pid = 991001
            returncode = 126

            def communicate(self, *, input, timeout):
                nonzero_stale.write_text('{"status":"recreated"}\n')
                return "", "rejected"

        nonzero_stale = temp / "protected-nonzero-stale.json"
        nonzero_stale.write_text('{"status":"stale"}\n')
        protected_module.subprocess = types.SimpleNamespace(
            PIPE=original_subprocess.PIPE,
            CompletedProcess=original_subprocess.CompletedProcess,
            Popen=lambda *arguments, **keywords: NonzeroController(),
        )
        try:
            nonzero_result = protected_module.run_native_bootstrap(
                [
                    str(native_bootstrap),
                    "--invalidate-result",
                    str(nonzero_stale),
                    "--print-self-record",
                ],
                expected_cdhash=native_cdhash,
                child_environment={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                capture_output=True,
                text=True,
                timeout=1,
            )
        finally:
            protected_module.subprocess = original_subprocess
        require(
            nonzero_result.returncode == 126 and not nonzero_stale.exists(),
            "nonzero protected controller retained recreated stale evidence",
        )

        class FailedClearController:
            pid = 991002
            returncode = 126

            def communicate(self, *, input, timeout):
                failed_clear_target.mkdir()
                later_clear_target.write_text('{"status":"recreated"}\n')
                return "", "rejected"

        failed_clear_target = temp / "protected-failed-clear"
        later_clear_target = temp / "protected-later-clear.json"
        later_clear_target.write_text('{"status":"stale"}\n')
        protected_module.subprocess = types.SimpleNamespace(
            PIPE=original_subprocess.PIPE,
            CompletedProcess=original_subprocess.CompletedProcess,
            Popen=lambda *arguments, **keywords: FailedClearController(),
        )
        failed_clear_propagated = False
        try:
            protected_module.run_native_bootstrap(
                [
                    str(native_bootstrap),
                    "--invalidate-result",
                    str(failed_clear_target),
                    "--invalidate-result",
                    str(later_clear_target),
                    "--print-self-record",
                ],
                expected_cdhash=native_cdhash,
                child_environment={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                capture_output=True,
                text=True,
                timeout=1,
            )
        except protected_module.ResultInvalidationError as error:
            failed_clear_propagated = (
                len(error.failures) == 1
                and error.failures[0][0] == str(failed_clear_target)
                and isinstance(error.failures[0][1], IsADirectoryError)
            )
        finally:
            protected_module.subprocess = original_subprocess
        require(
            failed_clear_propagated and not later_clear_target.exists(),
            "nonzero protected controller did not aggregate a clear failure "
            "after removing later stale evidence",
        )

        class UnreapedController:
            pid = 991003
            returncode = None
            wait_timeout = None

            def communicate(self, *, input, timeout):
                bounded_stale.write_text('{"status":"recreated"}\n')
                raise original_subprocess.TimeoutExpired("swift", timeout)

            def wait(self, *, timeout):
                self.wait_timeout = timeout
                raise original_subprocess.TimeoutExpired("swift", timeout)

        bounded_stale = temp / "protected-bounded-cleanup-stale.json"
        bounded_stale.write_text('{"status":"stale"}\n')
        unreaped = UnreapedController()
        killed_groups: list[tuple[int, int]] = []
        protected_module.subprocess = types.SimpleNamespace(
            PIPE=original_subprocess.PIPE,
            CompletedProcess=original_subprocess.CompletedProcess,
            Popen=lambda *arguments, **keywords: unreaped,
        )
        protected_module.os.killpg = (
            lambda pid, operation: killed_groups.append((pid, operation))
        )
        bounded_failure = False
        try:
            protected_module.run_native_bootstrap(
                [
                    str(native_bootstrap),
                    "--invalidate-result",
                    str(bounded_stale),
                    "--print-self-record",
                ],
                expected_cdhash=native_cdhash,
                child_environment={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                capture_output=True,
                text=True,
                timeout=0.01,
            )
        except RuntimeError as error:
            bounded_failure = "cleanup did not complete" in str(error)
        finally:
            protected_module.subprocess = original_subprocess
            protected_module.os.killpg = original_killpg
        require(
            bounded_failure
            and unreaped.wait_timeout
            == protected_module.CONTROLLER_CLEANUP_TIMEOUT_SECONDS
            and killed_groups == [(unreaped.pid, signal.SIGKILL)]
            and not bounded_stale.exists(),
            "protected controller cleanup wait was unbounded or fail-open",
        )

        timeout_stale = temp / "protected-timeout-stale.json"
        timeout_stale.write_text('{"status":"stale"}\n')
        timeout_spawned_fifo = temp / "protected-timeout-spawned.fifo"
        timeout_continue_fifo = temp / "protected-timeout-continue.fifo"
        os.mkfifo(timeout_spawned_fifo, 0o600)
        os.mkfifo(timeout_continue_fifo, 0o600)
        timeout_spawned_fd = os.open(
            timeout_spawned_fifo, os.O_RDONLY | os.O_NONBLOCK
        )
        timeout_expired = False
        try:
            try:
                protected_module.run_native_bootstrap(
                    [
                        *native_prefix,
                        "--invalidate-result",
                        str(timeout_stale),
                        "--",
                        str(runtime_python),
                        "-I",
                        "-S",
                        "-B",
                        "-X",
                        "pycache_prefix=/dev/null",
                        str(launcher_path),
                        "--rom",
                        str(root / "test.nds"),
                    ],
                    expected_cdhash=native_cdhash,
                    child_environment={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                    capture_output=True,
                    text=True,
                    timeout=0.5,
                    spawned_fifo=str(timeout_spawned_fifo),
                    continue_fifo=str(timeout_continue_fifo),
                )
            except subprocess.TimeoutExpired:
                timeout_expired = True
            timeout_notice = os.read(timeout_spawned_fd, 128)
        finally:
            os.close(timeout_spawned_fd)
        process_table = subprocess.run(
            ["/bin/ps", "-axo", "command="],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        ).stdout
        require(
            timeout_expired
            and timeout_notice == b"SPAWNED\n"
            and str(timeout_stale) not in process_table
            and not timeout_stale.exists(),
            "protected runner timeout did not terminate its owned process "
            "group and invalidate stale evidence",
        )

        actual_parent_sibling = native_bootstrap.parent / "hostile-sibling.dylib"
        parent_stale = temp / "bootstrap-parent-stale.json"
        require(
            not actual_parent_sibling.exists()
            and not actual_parent_sibling.is_symlink(),
            "actual bootstrap parent sibling fixture already exists",
        )
        parent_stale.write_text('{"status":"stale"}\n')
        actual_parent_sibling.write_bytes(b"hostile sibling")
        try:
            parent_result = protected_module.run_native_bootstrap(
                [
                    *native_prefix,
                    "--invalidate-result",
                    str(parent_stale),
                    "--",
                    str(runtime_python),
                    "-I",
                    "-S",
                    "-B",
                    "-X",
                    "pycache_prefix=/dev/null",
                    str(launcher_path),
                    "--rom",
                    str(root / "test.nds"),
                ],
                expected_cdhash=native_cdhash,
                child_environment={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                capture_output=True,
                text=True,
                timeout=30,
            )
        finally:
            actual_parent_sibling.unlink()
        require(
            parent_result.returncode != 0
            and "closure differs: " + str(native_bootstrap.parent)
            in parent_result.stderr
            and "runtime launcher failed" not in parent_result.stderr
            and not parent_stale.exists(),
            "actual bootstrap parent sibling did not reject before Python",
        )

        for entitlement_key, label in (
            ("com.apple.security.get-task-allow", "get-task-allow"),
            (
                "com.apple.security.cs.allow-unsigned-executable-memory",
                "allow-unsigned-executable-memory",
            ),
        ):
            entitled = temp / f"entitled-{label}-bootstrap"
            entitlement_plist = temp / f"entitled-{label}.plist"
            shutil.copy2(native_bootstrap, entitled)
            entitlement_plist.write_text(
                "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
                "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
                "<plist version=\"1.0\"><dict><key>"
                + entitlement_key
                + "</key><true/></dict></plist>\n"
            )
            entitled_sign = subprocess.run(
                [
                    "/usr/bin/codesign",
                    "--force",
                    "--sign",
                    "-",
                    "--timestamp=none",
                    "--options",
                    "runtime,restrict,library,hard,kill",
                    "--identifier",
                    "com.samefisk.hgengine.summary-relearn-bootstrap",
                    "--entitlements",
                    str(entitlement_plist),
                    str(entitled),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            )
            entitled_signature = subprocess.run(
                ["/usr/bin/codesign", "-d", "--verbose=4", str(entitled)],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            )
            entitled_text = (
                entitled_signature.stdout + entitled_signature.stderr
            )
            entitled_direct = subprocess.run(
                [str(entitled), "--print-self-record"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            )
            require(
                entitled_sign.returncode == 0
                and entitled_signature.returncode == 0
                and "flags=0x12b02(adhoc,hard,kill,restrict,"
                "library-validation,runtime)" in entitled_text
                and "allow-dyld-environment-variables" not in entitled_text
                and "disable-library-validation" not in entitled_text
                and entitled_direct.returncode == 0,
                f"{label} entitlement fixture did not calibrate",
            )
            try:
                native_code_signature_provenance(entitled)
            except ValueError as error:
                require(
                    "entitlement" in str(error) or "slot set" in str(error),
                    f"{label} fixture failed for an unrelated reason",
                )
            else:
                require(False, f"{label} entitlement fixture was accepted")

        def malformed_invalidation(arguments: list[str], label: str) -> subprocess.CompletedProcess[str]:
            completed = subprocess.run(
                arguments,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            )
            require(
                completed.returncode != 0,
                f"{label} invalidation fixture unexpectedly succeeded",
            )
            return completed

        malformed_stale = temp / "malformed-argv-result.json"
        malformed_stale.write_text('{"status":"stale"}\n')
        malformed_invalidation(
            [
                *native_prefix,
                "--invalidate-result",
                str(malformed_stale),
                "--unknown-bootstrap-option",
            ],
            "malformed argv",
        )
        require(
            not os.path.lexists(malformed_stale),
            "malformed argv retained stale result",
        )
        unknown_first_stale = temp / "unknown-first-result.json"
        unknown_first_stale.write_text('{"status":"stale"}\n')
        malformed_invalidation(
            [
                str(native_bootstrap),
                "--unknown-bootstrap-option",
                "--invalidate-result",
                str(unknown_first_stale),
            ],
            "unknown-before-result",
        )
        require(
            not os.path.lexists(unknown_first_stale),
            "unknown-before-result retained stale evidence",
        )
        missing_inventory_stale = temp / "missing-inventory-result.json"
        missing_inventory_stale.write_text('{"status":"stale"}\n')
        malformed_invalidation(
            [
                str(native_bootstrap),
                "--inventory",
                "--invalidate-result",
                str(missing_inventory_stale),
            ],
            "missing inventory before result",
        )
        require(
            not os.path.lexists(missing_inventory_stale),
            "missing inventory value consumed the result marker",
        )

        symlink_target = temp / "symlink-result-target.json"
        symlink_target_bytes = b'{"protected":true}\n'
        symlink_target.write_bytes(symlink_target_bytes)
        symlink_result = temp / "symlink-result.json"
        symlink_result.symlink_to(symlink_target)
        malformed_invalidation(
            [
                str(native_bootstrap),
                "--invalidate-result",
                str(symlink_result),
                "--unknown-bootstrap-option",
            ],
            "symlink result",
        )
        require(
            not os.path.lexists(symlink_result)
            and symlink_target.read_bytes() == symlink_target_bytes,
            "symlink result invalidation followed or retained the link",
        )

        fifo_result = temp / "fifo-result.json"
        os.mkfifo(fifo_result, 0o600)
        malformed_invalidation(
            [
                str(native_bootstrap),
                "--invalidate-result",
                str(fifo_result),
                "--unknown-bootstrap-option",
            ],
            "FIFO result",
        )
        require(
            not os.path.lexists(fifo_result),
            "FIFO result invalidation retained the node",
        )

        directory_result = temp / "directory-result.json"
        directory_result.mkdir()
        directory_child = directory_result / "protected"
        directory_child.write_bytes(b"protected")
        directory_blocked = malformed_invalidation(
            [
                str(native_bootstrap),
                "--invalidate-result",
                str(directory_result),
                "--unknown-bootstrap-option",
            ],
            "directory result",
        )
        require(
            "result invalidation failed" in directory_blocked.stderr
            and directory_child.read_bytes() == b"protected",
            "directory result invalidation did not fail closed",
        )

        locked_parent = temp / "locked-result-parent"
        locked_parent.mkdir(mode=0o700)
        locked_result = locked_parent / "stale.json"
        locked_result.write_text('{"status":"stale"}\n')
        removable_result = temp / "aggregate-removable-result.json"
        removable_result.write_text('{"status":"stale"}\n')
        os.chmod(locked_parent, 0o500)
        try:
            permission_blocked = malformed_invalidation(
                [
                    str(native_bootstrap),
                    "--invalidate-result",
                    str(locked_result),
                    "--invalidate-result",
                    str(removable_result),
                    "--unknown-bootstrap-option",
                ],
                "permission failure",
            )
            require(
                "result invalidation failed" in permission_blocked.stderr
                and os.path.lexists(locked_result)
                and not os.path.lexists(removable_result),
                "result invalidation did not aggregate permission failure",
            )
        finally:
            os.chmod(locked_parent, 0o700)

        overflow_results = [
            temp / f"overflow-result-{index:02d}.json" for index in range(66)
        ]
        overflow_arguments = [str(native_bootstrap)]
        for stale in overflow_results:
            stale.write_text('{"status":"stale"}\n')
            overflow_arguments.extend(["--invalidate-result", str(stale)])
        overflow_arguments.append("--unknown-bootstrap-option")
        malformed_invalidation(overflow_arguments, "result overflow")
        require(
            all(not os.path.lexists(stale) for stale in overflow_results),
            "stage-zero result overflow retained stale evidence",
        )
        empty_result = malformed_invalidation(
            [str(native_bootstrap), "--invalidate-result="],
            "empty result path",
        )
        require(
            "result invalidation failed" in empty_result.stderr,
            "empty result path did not fail closed before validation",
        )

        supervisor_root = (temp / "supervisor-state-machine").resolve()
        executable_parent = supervisor_root / "runtime"
        script_parent = supervisor_root / "scripts"
        absent_parent = supervisor_root / "absent"
        executable_parent.mkdir(parents=True)
        script_parent.mkdir()
        absent_parent.mkdir()
        fake_python_source = supervisor_root / "fake_python.c"
        fake_python = executable_parent / "fake-python"
        fake_alias = executable_parent / "python3"
        fake_launcher = script_parent / "launch_summary_move_relearn_runtime.py"
        fake_python_source.write_text(
            "#include <signal.h>\n#include <stdlib.h>\n#include <string.h>\n"
            "#include <unistd.h>\n"
            "int main(int argc, char **argv) {\n"
            "  const char *ready = getenv(\"SUMMARY_MOVE_RELEARN_BOOTSTRAP_READY_FD\");\n"
            "  const char *go = getenv(\"SUMMARY_MOVE_RELEARN_BOOTSTRAP_GO_FD\");\n"
            "  const char message[] = \"SUMMARY_MOVE_RELEARN_PYTHON_READY_V1\\n\";\n"
            "  int ready_fd = ready ? atoi(ready) : -1;\n"
            "  int go_fd = go ? atoi(go) : -1;\n"
            "  const char *mode = argc > 7 ? argv[7] : \"\";\n"
            "  if (strcmp(mode, \"stop-before-ready\") == 0) raise(SIGSTOP);\n"
            "  if (strcmp(mode, \"exit-before-ready\") == 0) return 42;\n"
            "  if (ready_fd < 0 || write(ready_fd, message, sizeof(message)-1) "
            "!= (ssize_t)(sizeof(message)-1)) return 43;\n"
            "  close(ready_fd);\n"
            "  if (strcmp(mode, \"ready-close-go\") == 0) { close(go_fd); sleep(30); return 0; }\n"
            "  if (strcmp(mode, \"ready-stop\") == 0) raise(SIGSTOP);\n"
            "  sleep(30); return 0;\n"
            "}\n"
        )
        fake_compile = subprocess.run(
            [
                "/usr/bin/xcrun",
                "--sdk",
                "macosx",
                "clang",
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-Wl,-no_uuid",
                str(fake_python_source),
                "-o",
                str(fake_python),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        require(
            fake_compile.returncode == 0,
            "supervisor fake Python did not compile: " + fake_compile.stderr[-1000:],
        )
        fake_sign = subprocess.run(
            [
                "/usr/bin/codesign",
                "--force",
                "--sign",
                "-",
                "--timestamp=none",
                str(fake_python),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        require(fake_sign.returncode == 0, "supervisor fake Python signing failed")
        fake_alias.symlink_to(fake_python.name)
        fake_launcher.write_text("# authenticated command-policy fixture\n")

        def membership_record(directory: Path) -> tuple[int, str]:
            members: list[tuple[bytes, bytes]] = []
            with os.scandir(directory) as entries:
                for entry in entries:
                    metadata = entry.stat(follow_symlinks=False)
                    kind = (
                        b"F" if stat.S_ISREG(metadata.st_mode)
                        else b"D" if stat.S_ISDIR(metadata.st_mode)
                        else b"L" if stat.S_ISLNK(metadata.st_mode)
                        else b"?"
                    )
                    require(kind != b"?", "supervisor inventory member differs")
                    members.append((os.fsencode(entry.name), kind))
            payload = bytearray(
                b"summary-move-relearn-directory-membership-v1\0"
            )
            for name, kind in sorted(members):
                payload.extend(kind)
                payload.extend(len(name).to_bytes(8, "big"))
                payload.extend(name)
            return len(payload), hashlib.sha256(payload).hexdigest()

        anchor_parent = supervisor_root / "anchors"
        anchor_parent.mkdir()
        fake_inventory = anchor_parent / "inventory.txt"
        fixture_bootstrap = anchor_parent / "native-bootstrap"
        fake_inventory.write_bytes(b"")
        fixture_bootstrap.write_bytes(b"")
        absent_path = absent_parent / "never-created"
        alias_target = os.readlink(fake_alias).encode()
        executable_bytes = fake_python.read_bytes()
        launcher_bytes = fake_launcher.read_bytes()
        executable_membership = membership_record(executable_parent)
        script_membership = membership_record(script_parent)
        anchor_membership = membership_record(anchor_parent)
        empty_sha256 = hashlib.sha256(b"").hexdigest()
        fake_inventory.write_text(
            "summary-move-relearn-native-bootstrap-inventory-v2\n"
            f"M\t{anchor_membership[0]}\t{anchor_membership[1]}\t{anchor_parent}\n"
            f"M\t{executable_membership[0]}\t{executable_membership[1]}\t{executable_parent}\n"
            f"E\t{len(executable_bytes)}\t{hashlib.sha256(executable_bytes).hexdigest()}\t{fake_python}\n"
            f"A\t{len(alias_target)}\t{hashlib.sha256(alias_target).hexdigest()}\t{fake_alias}\n"
            f"M\t{script_membership[0]}\t{script_membership[1]}\t{script_parent}\n"
            f"F\t{len(launcher_bytes)}\t{hashlib.sha256(launcher_bytes).hexdigest()}\t{fake_launcher}\n"
            f"D\t0\t{empty_sha256}\t{absent_parent}\n"
            f"N\t0\t{empty_sha256}\t{absent_path}\n"
        )
        fake_inventory_sha256 = hashlib.sha256(fake_inventory.read_bytes()).hexdigest()
        fixture_compile = subprocess.run(
            [
                "/usr/bin/xcrun",
                "--sdk",
                "macosx",
                "clang",
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-pedantic",
                "-Wl,-no_uuid",
                f'-DSMR_EXPECTED_INVENTORY_SHA256="{fake_inventory_sha256}"',
                str(native_source_path),
                "-o",
                str(fixture_bootstrap),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        require(
            fixture_compile.returncode == 0,
            "supervisor fixture bootstrap did not compile: "
            + fixture_compile.stderr[-1000:],
        )
        fixture_sign = subprocess.run(
            [
                "/usr/bin/codesign",
                "--force",
                "--sign",
                "-",
                "--timestamp=none",
                "--options",
                "runtime,restrict,library,hard,kill",
                "--identifier",
                "com.samefisk.hgengine.summary-relearn-supervisor-fixture",
                str(fixture_bootstrap),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        require(fixture_sign.returncode == 0, "supervisor fixture signing failed")
        fixture_bootstrap_sha256 = hashlib.sha256(
            fixture_bootstrap.read_bytes()
        ).hexdigest()
        for mode in (
            "stop-before-ready",
            "ready-close-go",
            "ready-stop",
            "exit-before-ready",
        ):
            supervisor_stale = supervisor_root / f"{mode}-stale.json"
            supervisor_stale.write_text('{"status":"stale"}\n')
            supervisor_command = [
                str(fixture_bootstrap),
                "--inventory",
                str(fake_inventory),
                "--expected-inventory-sha256",
                fake_inventory_sha256,
                "--expected-self-sha256",
                fixture_bootstrap_sha256,
                "--invalidate-result",
                str(supervisor_stale),
                "--ready-timeout-seconds",
                "1",
                "--",
                str(fake_alias),
                "-I",
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
                str(fake_launcher),
                mode,
            ]
            started = time.monotonic()
            process = subprocess.Popen(
                supervisor_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            )
            try:
                _, supervisor_stderr = process.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=5)
                require(False, f"{mode} supervisor fixture exceeded bound")
            elapsed = time.monotonic() - started
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                group_absent = True
            else:
                group_absent = False
            require(
                process.returncode != 0
                and process.returncode != -signal.SIGPIPE
                and elapsed < 7
                and group_absent
                and not os.path.lexists(supervisor_stale)
                and "authenticated child failed" in supervisor_stderr,
                f"{mode} child ownership/timeout cleanup differs: "
                f"rc={process.returncode} elapsed={elapsed:.3f} "
                f"group_absent={group_absent} "
                f"stale={os.path.lexists(supervisor_stale)} "
                f"stderr={supervisor_stderr[-500:]!r}",
            )

        publication_repo = temp / "publication-race-repo"
        publication_scripts = publication_repo / "scripts"
        publication_build = publication_repo / "build"
        publication_scripts.mkdir(parents=True)
        publication_build.mkdir()
        publication_helper = (
            publication_scripts / "build_summary_move_relearn_native_bootstrap.sh"
        )
        publication_source = (
            publication_scripts / "summary_move_relearn_native_bootstrap.c"
        )
        publication_inventory = (
            publication_scripts / "summary_move_relearn_native_inventory.txt"
        )
        shutil.copy2(native_build_path, publication_helper)
        shutil.copy2(native_source_path, publication_source)
        shutil.copy2(native_inventory_path, publication_inventory)
        malicious_source = temp / "publication_substitute.c"
        malicious_binary = temp / "publication-substitute"
        malicious_sentinel = temp / "publication-substitute.executed"
        malicious_source.write_text(
            "#include <fcntl.h>\n#include <stdio.h>\n#include <stdlib.h>\n"
            "#include <string.h>\n#include <unistd.h>\n"
            "__attribute__((constructor)) static void hostile(void) {\n"
            "  const char *path = getenv(\"SMR_HOSTILE_SENTINEL\");\n"
            "  if (path != NULL) { int fd = open(path, O_WRONLY | O_CREAT | "
            "O_TRUNC, 0600); if (fd >= 0) { (void)write(fd, \"executed\", 8); "
            "close(fd); } }\n}\n"
            "int main(int argc, char **argv) {\n"
            "  if (argc == 2 && strcmp(argv[1], \"--print-self-record\") == 0) {\n"
            f"    puts(\"72144\\t{native_self_sha256}\\t"
            f"{native_inventory_sha256}\\t"
            f"{signature_provenance['code_directory']['sha256'][:40]}\");\n"
            "    return 0;\n"
            "  }\n  return 0;\n}\n"
        )
        malicious_compile = subprocess.run(
            [
                "/usr/bin/xcrun",
                "--sdk",
                "macosx",
                "clang",
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-Wl,-no_uuid",
                str(malicious_source),
                "-o",
                str(malicious_binary),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        malicious_sign = subprocess.run(
            [
                "/usr/bin/codesign",
                "--force",
                "--sign",
                "-",
                "--timestamp=none",
                "--options",
                "runtime,restrict,library,hard,kill",
                "--identifier",
                "com.samefisk.hgengine.summary-relearn-bootstrap",
                str(malicious_binary),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        malicious_direct = subprocess.run(
            [str(malicious_binary), "--print-self-record"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env={
                "PATH": "/usr/bin:/bin",
                "LC_ALL": "C",
                "SMR_HOSTILE_SENTINEL": str(malicious_sentinel),
            },
        )
        require(
            malicious_compile.returncode == 0
            and malicious_sign.returncode == 0
            and malicious_direct.returncode == 0
            and len(malicious_direct.stdout.strip().split("\t")) == 4
            and malicious_sentinel.read_bytes() == b"executed"
            and hashlib.sha256(malicious_binary.read_bytes()).hexdigest()
            != native_self_sha256,
            "publication substitution fixture did not calibrate",
        )
        malicious_sentinel.unlink()
        published_fifo = temp / "publication-published.fifo"
        continue_fifo = temp / "publication-continue.fifo"
        os.mkfifo(published_fifo, 0o600)
        os.mkfifo(continue_fifo, 0o600)
        published_fd = os.open(published_fifo, os.O_RDONLY | os.O_NONBLOCK)
        publication_environment = {
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C",
            "LANG": "C",
            "SUMMARY_MOVE_RELEARN_NATIVE_PUBLISHED_FIFO": str(published_fifo),
            "SUMMARY_MOVE_RELEARN_NATIVE_CONTINUE_FIFO": str(continue_fifo),
        }
        publication_process = subprocess.Popen(
            [
                str(publication_helper),
                native_self_sha256,
                signature_provenance["code_directory"]["sha256"][:40],
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=publication_environment,
        )
        try:
            deadline = time.monotonic() + 90
            published_message = b""
            while time.monotonic() < deadline and not published_message:
                try:
                    published_message = os.read(published_fd, 128)
                except BlockingIOError:
                    pass
                if publication_process.poll() is not None:
                    break
                if not published_message:
                    time.sleep(0.01)
            require(
                published_message == b"PUBLISHED\n"
                and publication_process.poll() is None,
                "publication substitution fixture did not reach the barrier",
            )
            substituted = (
                publication_build
                / "summary_move_relearn_native/"
                "summary_move_relearn_native_bootstrap"
            )
            replacement = publication_build / "publication-substitute.tmp"
            shutil.copy2(malicious_binary, replacement)
            os.replace(replacement, substituted)
            continue_fd = os.open(continue_fifo, os.O_WRONLY)
            try:
                os.write(continue_fd, b"CONTINUE\n")
            finally:
                os.close(continue_fd)
            publication_stdout, publication_stderr = publication_process.communicate(
                timeout=30
            )
            require(
                publication_process.returncode != 0
                and publication_stdout == ""
                and "published binary SHA-256 differs" in publication_stderr,
                "published bootstrap substitution was accepted",
            )
        finally:
            os.close(published_fd)
            if publication_process.poll() is None:
                publication_process.kill()
                publication_process.communicate(timeout=5)

        authenticated_fifo = temp / "publication-authenticated.fifo"
        report_fifo = temp / "publication-report.fifo"
        os.mkfifo(authenticated_fifo, 0o600)
        os.mkfifo(report_fifo, 0o600)
        authenticated_fd = os.open(
            authenticated_fifo, os.O_RDONLY | os.O_NONBLOCK
        )
        authenticated_environment = {
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C",
            "LANG": "C",
            "SUMMARY_MOVE_RELEARN_NATIVE_AUTHENTICATED_FIFO": str(
                authenticated_fifo
            ),
            "SUMMARY_MOVE_RELEARN_NATIVE_REPORT_FIFO": str(report_fifo),
        }
        authenticated_process = subprocess.Popen(
            [
                str(publication_helper),
                native_self_sha256,
                signature_provenance["code_directory"]["sha256"][:40],
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=authenticated_environment,
        )
        try:
            deadline = time.monotonic() + 90
            authenticated_message = b""
            while time.monotonic() < deadline and not authenticated_message:
                try:
                    authenticated_message = os.read(authenticated_fd, 128)
                except BlockingIOError:
                    pass
                if authenticated_process.poll() is not None:
                    break
                if not authenticated_message:
                    time.sleep(0.01)
            require(
                authenticated_message == b"AUTHENTICATED\n"
                and authenticated_process.poll() is None,
                "post-authentication publication barrier was not reached",
            )
            substituted = (
                publication_build
                / "summary_move_relearn_native/"
                "summary_move_relearn_native_bootstrap"
            )
            replacement = publication_build / "post-auth-substitute.tmp"
            shutil.copy2(malicious_binary, replacement)
            os.replace(replacement, substituted)
            report_fd = os.open(report_fifo, os.O_WRONLY)
            try:
                os.write(report_fd, b"REPORT\n")
            finally:
                os.close(report_fd)
            receipt_stdout, receipt_stderr = authenticated_process.communicate(
                timeout=30
            )
            require(
                authenticated_process.returncode == 0
                and receipt_stdout.strip().split()[1:]
                == [native_self_sha256, native_inventory_sha256, native_cdhash]
                and "differs" not in receipt_stderr,
                "publication receipt was not object-bound",
            )

            protected_stale = temp / "protected-substitution-stale.json"
            protected_stale.write_text('{"status":"stale"}\n')
            protected_result = protected_module.run_native_bootstrap(
                [
                    str(substituted),
                    "--invalidate-result",
                    str(protected_stale),
                    "--print-self-record",
                ],
                expected_cdhash=native_cdhash,
                child_environment={
                    "PATH": "/usr/bin:/bin",
                    "LC_ALL": "C",
                    "SMR_HOSTILE_SENTINEL": str(malicious_sentinel),
                },
                capture_output=True,
                text=True,
                timeout=30,
            )
            require(
                protected_result.returncode == 126
                and protected_result.stdout == ""
                and "live process identity differs" in protected_result.stderr
                and not malicious_sentinel.exists()
                and not protected_stale.exists(),
                "protected post-publication launch executed substituted code "
                "or retained stale evidence: "
                f"rc={protected_result.returncode} "
                f"stdout={protected_result.stdout[-300:]!r} "
                f"stderr={protected_result.stderr[-500:]!r} "
                f"sentinel={malicious_sentinel.exists()} "
                f"stale={protected_stale.exists()}",
            )
        finally:
            os.close(authenticated_fd)
            if authenticated_process.poll() is None:
                authenticated_process.kill()
                authenticated_process.communicate(timeout=5)

        unsealed_stale = temp / "unsealed-startup-result.json"
        unsealed_stale.write_text('{"status": "stale"}\n')
        unsealed_environment = dict(os.environ)
        unsealed_environment.pop("PYTHONPYCACHEPREFIX", None)
        unsealed_environment.pop("PYTHONDONTWRITEBYTECODE", None)
        unsealed_start = subprocess.run(
            [
                *native_prefix,
                "--invalidate-result",
                str(unsealed_stale),
                "--",
                str(runtime_python),
                str(launcher_path),
                "--result-json",
                str(unsealed_stale),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=unsealed_environment,
        )
        require(
            unsealed_start.returncode != 0
            and "native bootstrap: Python invocation policy differs"
            in unsealed_start.stderr
            and not unsealed_stale.exists(),
            "runtime launcher accepted an unsealed startup or retained stale "
            "evidence",
        )

        hostile_root = temp / "hostile-python-startup"
        hostile_root.mkdir()

        def poison_source(sentinel: Path) -> str:
            return f"open({str(sentinel)!r}, 'w').write('executed')\n"

        attack_environments: list[tuple[str, dict[str, str], Path]] = []

        pythonpath_sentinel = hostile_root / "pythonpath-executed"
        pythonpath_root = hostile_root / "pythonpath"
        pythonpath_root.mkdir()
        (pythonpath_root / "hashlib.py").write_text(
            poison_source(pythonpath_sentinel)
        )
        attack_environments.append(
            (
                "hostile PYTHONPATH source",
                {**os.environ, "PYTHONPATH": str(pythonpath_root)},
                pythonpath_sentinel,
            )
        )

        for suffix in (".whl", ".arbitrary-python-archive"):
            sentinel = hostile_root / f"archive{suffix}.executed"
            archive = hostile_root / f"poison{suffix}"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("hashlib.py", poison_source(sentinel))
            attack_environments.append(
                (
                    f"hostile archive {suffix}",
                    {**os.environ, "PYTHONPATH": str(archive)},
                    sentinel,
                )
            )

        sourceless_sentinel = hostile_root / "sourceless-executed"
        sourceless_root = hostile_root / "sourceless"
        sourceless_root.mkdir()
        sourceless_code = compile(
            poison_source(sourceless_sentinel),
            str(sourceless_root / "hashlib.py"),
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        (sourceless_root / "hashlib.pyc").write_bytes(
            importlib.util.MAGIC_NUMBER + bytes(12) + marshal.dumps(sourceless_code)
        )
        attack_environments.append(
            (
                "hostile direct module.pyc",
                {**os.environ, "PYTHONPATH": str(sourceless_root)},
                sourceless_sentinel,
            )
        )

        site_sentinel = hostile_root / "sitecustomize-executed"
        site_root = hostile_root / "sitecustomize"
        site_root.mkdir()
        (site_root / "sitecustomize.py").write_text(poison_source(site_sentinel))
        attack_environments.append(
            (
                "hostile sitecustomize",
                {**os.environ, "PYTHONPATH": str(site_root)},
                site_sentinel,
            )
        )

        pth_sentinel = hostile_root / "pth-executed"
        user_base = hostile_root / "user-base"
        user_site = (
            user_base
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages"
        )
        user_site.mkdir(parents=True)
        (user_site / "poison.pth").write_text(
            "import builtins; " + poison_source(pth_sentinel)
        )
        attack_environments.append(
            (
                "hostile user-site .pth",
                {**os.environ, "PYTHONUSERBASE": str(user_base)},
                pth_sentinel,
            )
        )

        def isolated_policy_probe(
            label: str,
            environment: dict[str, str],
            sentinel: Path,
            flags: list[str],
        ) -> None:
            stale = hostile_root / (re.sub(r"\W+", "-", label) + ".json")
            stale.write_text('{"status":"stale"}\n')
            completed = subprocess.run(
                [
                    *native_prefix,
                    "--invalidate-result",
                    str(stale),
                    "--",
                    str(runtime_python),
                    *flags,
                    str(launcher_path),
                    "--result-json",
                    str(stale),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=environment,
            )
            require(
                completed.returncode != 0
                and not stale.exists()
                and not sentinel.exists(),
                f"{label} executed code or retained stale evidence",
            )

        exact_flags = [
            "-I",
            "-S",
            "-B",
            "-X",
            "pycache_prefix=/dev/null",
        ]
        for label, environment, sentinel in attack_environments:
            calibration_python = runtime_python
            calibration_code = (
                f"import site; site.addsitedir({str(user_site)!r})"
                if ".pth" in label
                else ("pass" if "sitecustomize" in label else "import hashlib")
            )
            calibration_flags = (
                ["-S", "-B"]
                if ".pth" in label
                else ([] if "sitecustomize" in label else ["-S", "-B"])
            )
            calibration = subprocess.run(
                [
                    str(calibration_python),
                    *calibration_flags,
                    "-c",
                    calibration_code,
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=environment,
            )
            require(
                calibration.returncode == 0 and sentinel.is_file(),
                f"{label} fixture did not calibrate executable attack code",
            )
            sentinel.unlink()
            isolated_policy_probe(label, environment, sentinel, exact_flags)

        flag_drop_env = {
            **os.environ,
            "PYTHONPATH": str(pythonpath_root),
        }
        for label, flags in (
            ("missing isolated flag", exact_flags[1:]),
            ("missing no-bytecode flag", ["-I", "-S", "-X", "pycache_prefix=/dev/null"]),
            ("missing pycache sink", ["-I", "-S", "-B"]),
        ):
            isolated_policy_probe(label, flag_drop_env, pythonpath_sentinel, flags)

        # Calibrate the exact pre-READY exposure that -S closes.  -I ignores
        # PYTHONPATH and user-site paths, so a PYTHONPATH sentinel cannot prove
        # the missing-no-site case.  A canonical venv site-packages .pth is
        # processed by the real interpreter when -S is absent.  The native
        # anchor must reject that argv before fork, while the exact flags must
        # skip the .pth and still invalidate the deliberately stale result.
        canonical_pth_sentinel = hostile_root / "canonical-pth-executed"
        canonical_site_packages = (
            runtime_python.parent.parent
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages"
        )
        canonical_flag_pth = (
            canonical_site_packages / "summary_move_relearn_flag_drop.pth"
        )
        require(
            canonical_site_packages.is_dir() and not canonical_flag_pth.exists(),
            "canonical flag-drop fixture path is unavailable",
        )
        canonical_flag_pth.write_text(
            "import builtins; " + poison_source(canonical_pth_sentinel)
        )
        try:
            calibration = subprocess.run(
                [
                    str(runtime_python),
                    "-I",
                    "-B",
                    "-X",
                    "pycache_prefix=/dev/null",
                    "-c",
                    "pass",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "PYTHONPATH": str(pythonpath_root)},
            )
            require(
                calibration.returncode == 0 and canonical_pth_sentinel.is_file(),
                "canonical missing-no-site fixture did not execute before script",
            )
            canonical_pth_sentinel.unlink()
            isolated_policy_probe(
                "canonical pth exact flags",
                dict(os.environ),
                canonical_pth_sentinel,
                exact_flags,
            )
            isolated_policy_probe(
                "missing no-site flag",
                dict(os.environ),
                canonical_pth_sentinel,
                ["-I", "-B", "-X", "pycache_prefix=/dev/null"],
            )
        finally:
            canonical_flag_pth.unlink(missing_ok=True)
            canonical_pth_sentinel.unlink(missing_ok=True)

        combined_hostile_environment = dict(os.environ)
        combined_hostile_environment["PYTHONPATH"] = os.pathsep.join(
            [
                str(pythonpath_root),
                str(hostile_root / "poison.whl"),
                str(hostile_root / "poison.arbitrary-python-archive"),
                str(sourceless_root),
                str(site_root),
            ]
        )
        combined_hostile_environment["PYTHONUSERBASE"] = str(user_base)
        subprocess_failure_fixture(
            temp / "subprocess-hostile-environment",
            environment=combined_hostile_environment,
        )
        require(
            all(not sentinel.exists() for _, _, sentinel in attack_environments),
            "hostile startup code executed during authenticated fixture",
        )

        # CPython's FileFinder resolves a package directory before a same-name
        # source module. Calibrate that exact rule with a self-removing
        # hashlib package, then prove sealed directory membership stops it
        # before the child is forked even though hashlib.py remains exact.
        canonical_stdlib = (
            Path(sys.base_prefix)
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
        ).resolve()
        canonical_hashlib = canonical_stdlib / "hashlib.py"
        hashlib_original = canonical_hashlib.read_text()
        hashlib_package = canonical_stdlib / "hashlib"
        hashlib_init = hashlib_package / "__init__.py"
        package_sentinel = temp / "package-before-module-executed"
        package_payload = (
            "import posix as _task6_posix\n"
            f"_task6_fd = _task6_posix.open({str(package_sentinel)!r}, "
            "_task6_posix.O_WRONLY | _task6_posix.O_CREAT | "
            "_task6_posix.O_TRUNC, 0o600)\n"
            "_task6_posix.write(_task6_fd, b'executed')\n"
            "_task6_posix.close(_task6_fd)\n"
            "_task6_posix.unlink(__file__)\n"
            f"_task6_posix.rmdir({str(hashlib_package)!r})\n"
            f"exec(compile({hashlib_original!r}, {str(canonical_hashlib)!r}, "
            "'exec'), globals(), globals())\n"
        )

        def install_package_shadow() -> None:
            require(
                canonical_hashlib.is_file()
                and not hashlib_package.exists(),
                "canonical hashlib membership was not sealed before fixture",
            )
            hashlib_package.mkdir()
            hashlib_init.write_text(package_payload)

        try:
            install_package_shadow()
            package_calibration = subprocess.run(
                [
                    str(runtime_python),
                    "-I",
                    "-S",
                    "-B",
                    "-X",
                    "pycache_prefix=/dev/null",
                    "-c",
                    "import hashlib; print(hashlib.sha256(b'x').hexdigest())",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=source_only_environment,
            )
            require(
                package_calibration.returncode == 0
                and package_sentinel.is_file()
                and not hashlib_package.exists()
                and canonical_hashlib.read_text() == hashlib_original,
                "package-before-module fixture did not calibrate direct execution",
            )
            package_sentinel.unlink()
            install_package_shadow()
            package_stale = temp / "package-before-module-result.json"
            package_stale.write_text('{"status":"stale"}\n')
            package_blocked = subprocess.run(
                [
                    *native_prefix,
                    "--invalidate-result",
                    str(package_stale),
                    "--",
                    str(runtime_python),
                    "-I",
                    "-S",
                    "-B",
                    "-X",
                    "pycache_prefix=/dev/null",
                    str(launcher_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=source_only_environment,
            )
            require(
                package_blocked.returncode != 0
                and "closure differs" in package_blocked.stderr
                and not package_sentinel.exists()
                and not package_stale.exists(),
                "native bootstrap accepted package-before-module membership",
            )
        finally:
            hashlib_init.unlink(missing_ok=True)
            if hashlib_package.exists():
                hashlib_package.rmdir()
            package_sentinel.unlink(missing_ok=True)
        require(
            canonical_hashlib.read_text() == hashlib_original,
            "package-before-module fixture changed hashlib.py",
        )

        def membership_negative(candidate: Path, create: object, label: str) -> None:
            stale = temp / f"{label}-result.json"
            sentinel = temp / f"{label}-executed"
            require(not candidate.exists() and not candidate.is_symlink(), label)
            create()
            stale.write_text('{"status":"stale"}\n')
            try:
                blocked = subprocess.run(
                    [
                        *native_prefix,
                        "--invalidate-result",
                        str(stale),
                        "--",
                        str(runtime_python),
                        "-I",
                        "-S",
                        "-B",
                        "-X",
                        "pycache_prefix=/dev/null",
                        str(launcher_path),
                        "--result-json",
                        str(sentinel),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=source_only_environment,
                )
                require(
                    blocked.returncode != 0
                    and "closure differs" in blocked.stderr
                    and not stale.exists()
                    and not sentinel.exists(),
                    f"native bootstrap accepted {label} membership",
                )
            finally:
                candidate.unlink(missing_ok=True)

        direct_pyc = canonical_stdlib / "task6_uninventoried.pyc"
        membership_negative(
            direct_pyc,
            lambda: direct_pyc.write_bytes(b"hostile-direct-bytecode"),
            "direct-pyc",
        )
        executable_parent_sibling = (
            base / "bin/task6_uninventoried_extension.so"
        )
        membership_negative(
            executable_parent_sibling,
            lambda: executable_parent_sibling.write_bytes(
                b"hostile executable-parent extension"
            ),
            "executable-parent-extension",
        )
        native_parent = (
            base / "Resources/Python.app/Contents/MacOS"
        )
        native_parent_package = native_parent / "task6_uninventoried_package"
        native_parent_init = native_parent_package / "__init__.py"
        native_parent_stale = temp / "native-parent-package-result.json"
        native_parent_sentinel = temp / "native-parent-package-executed"
        require(
            not native_parent_package.exists(),
            "native-parent package fixture already exists",
        )
        native_parent_package.mkdir()
        native_parent_init.write_text("raise SystemExit('untrusted package')\n")
        native_parent_stale.write_text('{"status":"stale"}\n')
        try:
            native_parent_blocked = subprocess.run(
                [
                    *native_prefix,
                    "--invalidate-result",
                    str(native_parent_stale),
                    "--",
                    str(runtime_python),
                    "-I",
                    "-S",
                    "-B",
                    "-X",
                    "pycache_prefix=/dev/null",
                    str(launcher_path),
                    "--result-json",
                    str(native_parent_sentinel),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=source_only_environment,
            )
            require(
                native_parent_blocked.returncode != 0
                and "closure differs" in native_parent_blocked.stderr
                and not native_parent_stale.exists()
                and not native_parent_sentinel.exists(),
                "native executable-parent package membership was accepted",
            )
        finally:
            native_parent_init.unlink(missing_ok=True)
            if native_parent_package.exists():
                native_parent_package.rmdir()
        unsupported_link = canonical_stdlib / "task6_uninventoried_link"
        membership_negative(
            unsupported_link,
            lambda: unsupported_link.symlink_to(canonical_hashlib),
            "new-symlink",
        )
        unsupported_link.symlink_to(canonical_hashlib)
        try:
            generated = temp / "unsupported-symlink-inventory.txt"
            generator_blocked = subprocess.run(
                [
                    str(runtime_python),
                    "-I",
                    "-S",
                    "-B",
                    "-X",
                    "pycache_prefix=/dev/null",
                    str(native_generator_path),
                    "--output",
                    str(generated),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                env=source_only_environment,
            )
            require(
                generator_blocked.returncode != 0
                and "unsupported inventory graph symlink"
                in generator_blocked.stderr
                and not generated.exists(),
                "inventory generator accepted an unsupported symlink member",
            )
        finally:
            unsupported_link.unlink(missing_ok=True)

        unsupported_fifo = canonical_stdlib / "task6_uninventoried_fifo"
        membership_negative(
            unsupported_fifo,
            lambda: os.mkfifo(unsupported_fifo, 0o600),
            "new-fifo",
        )
        os.mkfifo(unsupported_fifo, 0o600)
        try:
            generated = temp / "unsupported-fifo-inventory.txt"
            generator_blocked = subprocess.run(
                [
                    str(runtime_python),
                    "-I",
                    "-S",
                    "-B",
                    "-X",
                    "pycache_prefix=/dev/null",
                    str(native_generator_path),
                    "--output",
                    str(generated),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                env=source_only_environment,
            )
            require(
                generator_blocked.returncode != 0
                and "unsupported inventory directory member"
                in generator_blocked.stderr
                and not generated.exists(),
                "inventory generator accepted an unsupported entry type",
            )
        finally:
            unsupported_fifo.unlink(missing_ok=True)

        # Calibrate a constructor before native main against an intentionally
        # unprotected copy, then apply the identical DYLD environment to the
        # exact published hardened/restricted bootstrap. In-main environment
        # clearing cannot satisfy this fixture; only the CodeDirectory launch
        # policy can prevent the marker and dyld log.
        dyld_sentinel = temp / "dyld-pre-main-constructor-executed"
        dyld_log = temp / "dyld-pre-main.log"
        dyld_source = temp / "dyld_pre_main_probe.c"
        dyld_library = temp / "dyld_pre_main_probe.dylib"
        dyld_source.write_text(
            "#include <fcntl.h>\n#include <unistd.h>\n"
            "__attribute__((constructor)) static void task6_probe(void) {\n"
            f"  int fd = open({json.dumps(str(dyld_sentinel))}, "
            "O_WRONLY | O_CREAT | O_TRUNC, 0600);\n"
            "  if (fd >= 0) { (void)write(fd, \"executed\", 8); close(fd); }\n"
            "}\n"
        )
        dyld_compile = subprocess.run(
            [
                "/usr/bin/xcrun",
                "--sdk",
                "macosx",
                "clang",
                "-dynamiclib",
                str(dyld_source),
                "-o",
                str(dyld_library),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        require(
            dyld_compile.returncode == 0,
            "pre-main dyld constructor fixture did not compile: "
            + dyld_compile.stderr[-1000:],
        )
        dyld_sign = subprocess.run(
            [
                "/usr/bin/codesign",
                "--force",
                "--sign",
                "-",
                "--timestamp=none",
                str(dyld_library),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        require(dyld_sign.returncode == 0, "pre-main dyld fixture signing failed")
        unprotected_bootstrap = temp / "unprotected-native-bootstrap"
        shutil.copy2(native_bootstrap, unprotected_bootstrap)
        strip_policy = subprocess.run(
            [
                "/usr/bin/codesign",
                "--force",
                "--sign",
                "-",
                "--timestamp=none",
                str(unprotected_bootstrap),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        require(strip_policy.returncode == 0, "dyld calibration signing failed")
        dyld_environment = {
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C",
            "DYLD_INSERT_LIBRARIES": str(dyld_library),
            "DYLD_PRINT_LIBRARIES": "1",
            "DYLD_PRINT_TO_FILE": str(dyld_log),
            "DYLD_LIBRARY_PATH": str(temp),
            "DYLD_FRAMEWORK_PATH": str(temp),
            "DYLD_FALLBACK_LIBRARY_PATH": str(temp),
        }
        dyld_calibration = subprocess.run(
            [str(unprotected_bootstrap), "--print-self-record"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=dyld_environment,
        )
        require(
            dyld_calibration.returncode == 0
            and dyld_sentinel.is_file()
            and dyld_log.is_file(),
            "pre-main dyld constructor fixture did not calibrate",
        )
        dyld_sentinel.unlink()
        dyld_log.unlink()
        dyld_stale = temp / "dyld-protected-result.json"
        dyld_stale.write_text('{"status":"stale"}\n')
        dyld_protected = subprocess.run(
            [
                *native_prefix,
                "--invalidate-result",
                str(dyld_stale),
                "--",
                str(runtime_python),
                "-I",
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
                str(launcher_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=dyld_environment,
        )
        require(
            dyld_protected.returncode != 0
            and not dyld_sentinel.exists()
            and not dyld_log.exists()
            and not dyld_stale.exists()
            and "authenticated child failed" in dyld_protected.stderr,
            "restricted native bootstrap accepted pre-main dyld influence",
        )

        # Exercise the exact canonical CPython startup path.  The payload
        # restores the sealed source before returning, so any Python-only
        # post-start hash would miss it.  The native bootstrap must reject the
        # file before CPython starts and must invalidate stale evidence itself.
        canonical_abc = (
            Path(sys.base_prefix)
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "abc.py"
        ).resolve()
        abc_original = canonical_abc.read_bytes()
        abc_backup = canonical_abc.with_name(
            f".{canonical_abc.name}.task6-sealed-original-{os.getpid()}"
        )
        abc_sentinel = temp / "canonical-abc-self-restore-executed"
        abc_payload = (
            "import posix as _task6_posix\n"
            f"_task6_fd = _task6_posix.open({str(abc_sentinel)!r}, "
            "_task6_posix.O_WRONLY | _task6_posix.O_CREAT | "
            "_task6_posix.O_TRUNC, 0o600)\n"
            "_task6_posix.write(_task6_fd, b'executed')\n"
            "_task6_posix.close(_task6_fd)\n"
            f"_task6_posix.rename({str(abc_backup)!r}, __file__)\n"
            f"exec(compile({abc_original.decode('utf-8')!r}, __file__, "
            "'exec'), globals(), globals())\n"
        ).encode("utf-8")

        def install_abc_attack() -> None:
            require(
                canonical_abc.read_bytes() == abc_original
                and not abc_backup.exists(),
                "canonical abc.py was not sealed before attack fixture",
            )
            os.replace(canonical_abc, abc_backup)
            canonical_abc.write_bytes(abc_payload)

        try:
            install_abc_attack()
            abc_calibration = subprocess.run(
                [
                    str(runtime_python),
                    "-I",
                    "-S",
                    "-B",
                    "-X",
                    "pycache_prefix=/dev/null",
                    "-c",
                    "pass",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=source_only_environment,
            )
            require(
                abc_calibration.returncode == 0
                and abc_sentinel.is_file()
                and canonical_abc.read_bytes() == abc_original
                and not abc_backup.exists(),
                "canonical self-restoring abc.py fixture did not calibrate",
            )
            abc_sentinel.unlink()
            install_abc_attack()
            abc_stale = temp / "canonical-abc-bootstrap-result.json"
            abc_stale.write_text('{"status":"stale"}\n')
            abc_blocked = subprocess.run(
                [
                    *native_prefix,
                    "--invalidate-result",
                    str(abc_stale),
                    "--",
                    str(runtime_python),
                    "-I",
                    "-S",
                    "-B",
                    "-X",
                    "pycache_prefix=/dev/null",
                    "-c",
                    "pass",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=source_only_environment,
            )
            require(
                abc_blocked.returncode != 0
                and "closure differs" in abc_blocked.stderr
                and not abc_sentinel.exists()
                and not abc_stale.exists(),
                "native bootstrap accepted self-restoring canonical abc.py",
            )
        finally:
            if abc_backup.exists():
                if canonical_abc.exists():
                    canonical_abc.unlink()
                os.replace(abc_backup, canonical_abc)
            require(
                canonical_abc.read_bytes() == abc_original,
                "canonical abc.py fixture did not restore exact bytes",
            )

        # The native variant wraps the exact mutable libssl dependency, writes
        # a marker from its constructor, atomically restores the original
        # canonical dylib, and re-exports the original symbols.  Direct Python
        # proves the constructor really runs; the bootstrap must stop it first.
        canonical_ssl = (
            Path(sys.base_prefix) / "lib/libssl.1.1.dylib"
        ).resolve()
        ssl_original = canonical_ssl.read_bytes()
        ssl_backup = canonical_ssl.with_name(
            f".{canonical_ssl.name}.task6-sealed-original-{os.getpid()}"
        )
        ssl_sentinel = temp / "canonical-libssl-constructor-executed"
        ssl_source = temp / "self_restoring_ssl.c"
        ssl_wrapper = temp / "self_restoring_libssl.dylib"
        ssl_reexport = temp / "sealed_original_libssl.dylib"
        ssl_reexport.write_bytes(ssl_original)
        ssl_source.write_text(
            "#include <fcntl.h>\n#include <stdio.h>\n#include <unistd.h>\n"
            "__attribute__((constructor)) static void task6_probe(void) {\n"
            f"  int fd = open({json.dumps(str(ssl_sentinel))}, O_WRONLY | O_CREAT | "
            "O_TRUNC, 0600);\n"
            "  if (fd >= 0) { (void)write(fd, \"executed\", 8); close(fd); }\n"
            f"  (void)rename({json.dumps(str(ssl_backup))}, "
            f"{json.dumps(str(canonical_ssl))});\n"
            "}\n"
        )
        require(not ssl_backup.exists(), "native fixture backup already exists")
        ssl_compile = subprocess.run(
            [
                "/usr/bin/xcrun",
                "--sdk",
                "macosx",
                "clang",
                "-dynamiclib",
                str(ssl_source),
                f"-Wl,-reexport_library,{ssl_reexport}",
                "-o",
                str(ssl_wrapper),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        require(
            ssl_compile.returncode == 0,
            "self-restoring native fixture did not compile: "
            + ssl_compile.stderr[-1000:],
        )
        ssl_sign = subprocess.run(
            [
                "/usr/bin/codesign",
                "--force",
                "--sign",
                "-",
                "--timestamp=none",
                str(ssl_wrapper),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        require(ssl_sign.returncode == 0, "native fixture signing failed")
        ssl_wrapper_bytes = ssl_wrapper.read_bytes()

        def install_ssl_attack() -> None:
            require(
                canonical_ssl.read_bytes() == ssl_original,
                "canonical libssl was not sealed before attack fixture",
            )
            if not ssl_backup.exists():
                os.link(canonical_ssl, ssl_backup)
            temporary_wrapper = canonical_ssl.with_name(
                f".{canonical_ssl.name}.task6-poison-{os.getpid()}"
            )
            temporary_wrapper.write_bytes(ssl_wrapper_bytes)
            os.chmod(temporary_wrapper, 0o775)
            os.replace(temporary_wrapper, canonical_ssl)

        try:
            install_ssl_attack()
            ssl_calibration = subprocess.run(
                [
                    str(runtime_python),
                    "-I",
                    "-S",
                    "-B",
                    "-X",
                    "pycache_prefix=/dev/null",
                    "-c",
                    "import hashlib; print(hashlib.sha256(b'x').hexdigest())",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=source_only_environment,
            )
            require(
                ssl_calibration.returncode == 0
                and ssl_sentinel.is_file()
                and canonical_ssl.read_bytes() == ssl_original
                and not ssl_backup.exists(),
                "self-restoring libssl constructor fixture did not calibrate",
            )
            ssl_sentinel.unlink()
            install_ssl_attack()
            ssl_stale = temp / "canonical-libssl-bootstrap-result.json"
            ssl_stale.write_text('{"status":"stale"}\n')
            ssl_blocked = subprocess.run(
                [
                    *native_prefix,
                    "--invalidate-result",
                    str(ssl_stale),
                    "--",
                    str(runtime_python),
                    "-I",
                    "-S",
                    "-B",
                    "-X",
                    "pycache_prefix=/dev/null",
                    "-c",
                    "import hashlib",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=source_only_environment,
            )
            require(
                ssl_blocked.returncode != 0
                and "closure differs" in ssl_blocked.stderr
                and not ssl_sentinel.exists()
                and not ssl_stale.exists(),
                "native bootstrap accepted self-restoring libssl constructor",
            )
        finally:
            if ssl_backup.exists():
                if canonical_ssl.exists():
                    canonical_ssl.unlink()
                os.replace(ssl_backup, canonical_ssl)
            require(
                canonical_ssl.read_bytes() == ssl_original,
                "canonical libssl fixture did not restore exact bytes",
            )

        canonical_stdlib = temp / "canonical-stdlib-closure"
        canonical_stdlib.mkdir()
        canonical_hashlib = canonical_stdlib / "hashlib.py"
        canonical_hashlib.write_text('VALUE = "sealed-canonical-source"\n')
        canonical_record = launcher._stage_zero_tree_record(
            str(canonical_stdlib)
        )
        canonical_sentinel = canonical_stdlib / "poison-executed"
        canonical_hashlib.write_text(
            f"open({str(canonical_sentinel)!r}, 'w').write('executed')\n"
            'VALUE = "poisoned-canonical-source"\n'
        )
        canonical_loader = importlib.machinery.SourceFileLoader(
            "canonical_stdlib_poison_calibration",
            str(canonical_hashlib),
        )
        canonical_spec = importlib.util.spec_from_loader(
            canonical_loader.name,
            canonical_loader,
        )
        require(canonical_spec is not None, "canonical poison spec is absent")
        canonical_module = importlib.util.module_from_spec(canonical_spec)
        canonical_loader.exec_module(canonical_module)
        require(
            canonical_sentinel.is_file()
            and canonical_module.VALUE == "poisoned-canonical-source",
            "canonical stdlib poison fixture did not calibrate",
        )
        canonical_sentinel.unlink()
        invalidate_stale(
            temp / "canonical-stdlib-poison-result.json",
            lambda: launcher._require(
                launcher._stage_zero_tree_record(str(canonical_stdlib))
                == canonical_record,
                "stage-zero canonical stdlib closure differs",
            ),
            RuntimeError,
            "canonical stdlib stage-zero poison",
        )
        require(
            not canonical_sentinel.exists(),
            "canonical stdlib poison executed before authentication",
        )

        startup_root = temp / "startup-pycache"
        startup_root.mkdir()
        startup_source = startup_root / "startup_fixture.py"
        startup_source.write_text('VALUE = "authenticated-source"\n')
        startup_sentinel = startup_root / "poison-executed"
        startup_poison = compile(
            "from pathlib import Path\n"
            f"Path({str(startup_sentinel)!r}).write_text('executed')\n"
            'VALUE = "poisoned-pyc"\n',
            str(startup_source),
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        startup_stat = startup_source.stat()
        startup_cache = colocated_cache_path(startup_source)
        startup_cache.parent.mkdir(parents=True)
        startup_cache.write_bytes(
            importlib.util.MAGIC_NUMBER
            + struct.pack(
                "<III",
                0,
                int(startup_stat.st_mtime),
                startup_stat.st_size,
            )
            + marshal.dumps(startup_poison)
        )
        startup_command = (
            "import sys; "
            f"sys.path.insert(0, {str(startup_root)!r}); "
            "import startup_fixture; print(startup_fixture.VALUE)"
        )
        poisoned_environment = dict(os.environ)
        poisoned_environment.pop("PYTHONPYCACHEPREFIX", None)
        poisoned_environment.pop("PYTHONDONTWRITEBYTECODE", None)
        poison_calibration = subprocess.run(
            [str(runtime_python), "-S", "-B", "-c", startup_command],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=poisoned_environment,
        )
        require(
            poison_calibration.returncode == 0
            and poison_calibration.stdout.strip() == "poisoned-pyc"
            and startup_sentinel.is_file(),
            "startup pycache fixture did not calibrate the poisoned-bytecode "
            "risk",
        )
        startup_sentinel.unlink()
        source_only_execution = subprocess.run(
            [
                str(runtime_python),
                "-I",
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
                "-v",
                "-c",
                startup_command,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=source_only_environment,
        )
        require(
            source_only_execution.returncode == 0
            and source_only_execution.stdout.strip()
            == "authenticated-source"
            and not startup_sentinel.exists()
            and str(startup_cache) not in source_only_execution.stderr
            and str(startup_source) in source_only_execution.stderr,
            "source-only startup consulted timestamp-valid poisoned bytecode",
        )

        corrupted_root = temp / "corrupted-helper"
        (
            corrupt_manifest,
            corrupt_rom,
            _,
            corrupt_paths,
            corrupt_manifest_sha,
            corrupt_launcher_sha,
            corrupt_verifier_sha,
        ) = make_fixture(corrupted_root)
        corrupt_sentinel = corrupted_root / "helper-executed"
        corrupt_paths[launcher.MANIFEST_HELPER_RELATIVE].write_text(
            "from pathlib import Path\n"
            f"Path({str(corrupt_sentinel)!r}).write_text('executed')\n"
        )
        invalidate_stale(
            corrupted_root / "runtime-result.json",
            lambda: launcher._load_authenticated_buffers(
                str(corrupted_root),
                str(corrupt_manifest),
                str(corrupt_rom),
                corrupt_manifest_sha,
                corrupt_launcher_sha,
                corrupt_verifier_sha,
            ),
            RuntimeError,
            "corrupted manifest-helper source",
        )
        require(
            not corrupt_sentinel.exists(),
            "corrupted manifest helper executed before authentication",
        )
        subprocess_failure_fixture(
            temp / "subprocess-corrupted-helper",
            mutate=lambda paths: paths[
                launcher.MANIFEST_HELPER_RELATIVE
            ].write_text("CORRUPTED = True\n"),
        )

        syntax_root = temp / "syntax-failure"
        (
            _,
            _,
            syntax_sources,
            syntax_paths,
            _,
            _,
            _,
        ) = make_fixture(syntax_root)
        syntax_sources[launcher.HEADLESS_RELATIVE] = b"def broken(:\n"
        invalidate_stale(
            syntax_root / "runtime-result.json",
            lambda: launcher._compile_buffers(
                syntax_sources,
                {
                    relative: str(path)
                    for relative, path in syntax_paths.items()
                },
            ),
            SyntaxError,
            "authenticated source syntax failure",
        )
        subprocess_failure_fixture(
            temp / "subprocess-syntax-failure",
            source_overrides={
                launcher.HEADLESS_RELATIVE: b"def broken(:\n",
            },
        )

        import_root = temp / "import-failure"
        import_sentinel = import_root / "runtime-executed"
        invalidate_stale(
            import_root / "runtime-result.json",
            lambda: launcher._execute_module(
                "summary_relearn_missing_import_fixture",
                str(import_root / "missing.py"),
                compile(
                    "import summary_relearn_dependency_that_does_not_exist\n"
                    f"open({str(import_sentinel)!r}, 'w').close()\n",
                    str(import_root / "missing.py"),
                    "exec",
                    dont_inherit=True,
                    optimize=0,
                ),
            ),
            ModuleNotFoundError,
            "authenticated helper import failure",
        )
        require(
            not import_sentinel.exists(),
            "import failure reached runtime execution",
        )
        subprocess_failure_fixture(
            temp / "subprocess-import-failure",
            source_overrides={
                launcher.MANIFEST_HELPER_RELATIVE: (
                    b"import summary_relearn_dependency_that_does_not_exist\n"
                ),
            },
        )

        dependency_root = temp / "dependency-failure"
        (
            dependency_manifest,
            dependency_rom,
            _,
            dependency_paths,
            dependency_manifest_sha,
            dependency_launcher_sha,
            dependency_verifier_sha,
        ) = make_fixture(dependency_root)
        dependency_paths[launcher.PARTY_RELATIVE].unlink()
        invalidate_stale(
            dependency_root / "runtime-result.json",
            lambda: launcher._load_authenticated_buffers(
                str(dependency_root),
                str(dependency_manifest),
                str(dependency_rom),
                dependency_manifest_sha,
                dependency_launcher_sha,
                dependency_verifier_sha,
            ),
            FileNotFoundError,
            "authenticated helper dependency failure",
        )
        subprocess_failure_fixture(
            temp / "subprocess-dependency-failure",
            mutate=lambda paths: paths[
                launcher.PARTY_RELATIVE
            ].unlink(),
        )

        argument_root = temp / "argument-failure"
        invalidate_stale(
            argument_root / "runtime-result.json",
            lambda: launcher._extract_single_option(
                ["--rom"],
                "--rom",
            ),
            RuntimeError,
            "runtime argument failure",
        )
        subprocess_failure_fixture(
            temp / "subprocess-argument-failure",
            arguments_only=True,
        )

        runtime_leaf = temp / "runtime-leaf"
        runtime_leaf.write_bytes(b"sealed runtime leaf")
        runtime_leaf_record = {
            "path": str(runtime_leaf.resolve()),
            **launcher._path_record(str(runtime_leaf)),
        }
        runtime_leaf.write_bytes(b"substituted runtime leaf")
        invalidate_stale(
            temp / "runtime-leaf-result.json",
            lambda: launcher._validate_file_path_record(
                runtime_leaf_record,
                "substituted fixture",
            ),
            RuntimeError,
            "substituted runtime leaf",
        )
        runtime_leaf.write_bytes(b"sealed runtime leaf")
        runtime_alias = temp / "runtime-leaf-alias"
        runtime_alias.symlink_to(runtime_leaf)
        alias_record = {
            "path": str(runtime_alias),
            **launcher._path_record(str(runtime_alias)),
        }
        invalidate_stale(
            temp / "runtime-alias-result.json",
            lambda: launcher._validate_file_path_record(
                alias_record,
                "aliased fixture",
            ),
            RuntimeError,
            "runtime path alias",
        )

        pil_root = temp / "retained-pil" / "PIL"
        pil_root.mkdir(parents=True)
        (pil_root / "__init__.py").write_text("")
        pil_source = pil_root / "fixture.py"
        pil_source.write_text('VALUE = "retained-pillow-source"\n')
        pil_sentinel = temp / "retained-pil-poison-executed"
        poison = compile(
            "from pathlib import Path\n"
            f"Path({str(pil_sentinel)!r}).write_text('executed')\n"
            'VALUE = "poisoned-pyc"\n',
            str(pil_source),
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        source_stat = pil_source.stat()
        pil_cache = colocated_cache_path(pil_source)
        pil_cache.parent.mkdir(parents=True)
        pil_cache.write_bytes(
            importlib.util.MAGIC_NUMBER
            + struct.pack(
                "<III",
                0,
                int(source_stat.st_mtime),
                source_stat.st_size,
            )
            + marshal.dumps(poison)
        )
        prior_pil = {
            name: module
            for name, module in tuple(sys.modules.items())
            if name == "PIL" or name.startswith("PIL.")
        }
        for name in prior_pil:
            del sys.modules[name]
        retained_loader = launcher._install_retained_package_loader(
            {"packages": {"PIL": {"root": str(pil_root.resolve())}}},
            "PIL",
        )
        try:
            imported_pil = __import__("PIL.fixture", fromlist=["fixture"])
            require(
                imported_pil.VALUE == "retained-pillow-source"
                and imported_pil.__cached__ is None
                and not pil_sentinel.exists(),
                "retained Pillow loader consulted poisoned bytecode",
            )
            retained_loader.authenticate()
        finally:
            sys.meta_path.remove(retained_loader)
            for name in tuple(sys.modules):
                if name == "PIL" or name.startswith("PIL."):
                    del sys.modules[name]
            sys.modules.update(prior_pil)

        for helper_name in (
            "manifest",
            "headless",
            "party",
        ):
            pycache_root = temp / f"poisoned-pyc-{helper_name}"
            pycache_root.mkdir()
            source_path = pycache_root / f"{helper_name}_helper.py"
            retained_source = b'FIXTURE_VALUE = "retained-source"\n'
            source_path.write_bytes(retained_source)
            fixed_time = 1_700_000_000
            os.utime(source_path, (fixed_time, fixed_time))
            sentinel = pycache_root / "poison-executed"
            poison_source = (
                'FIXTURE_VALUE = "poisoned-pyc"\n'
                "from pathlib import Path\n"
                f"Path({str(sentinel)!r}).write_text('executed')\n"
            )
            poison_code = compile(
                poison_source,
                str(source_path),
                "exec",
                dont_inherit=True,
                optimize=0,
            )
            source_stat = source_path.stat()
            cached_path = colocated_cache_path(source_path)
            cached_path.parent.mkdir(parents=True)
            cached_path.write_bytes(
                importlib.util.MAGIC_NUMBER
                + struct.pack(
                    "<III",
                    0,
                    int(source_stat.st_mtime),
                    source_stat.st_size,
                )
                + marshal.dumps(poison_code)
            )
            loader_name = f"summary_relearn_loader_{helper_name}"
            loader = importlib.machinery.SourceFileLoader(
                loader_name,
                str(source_path),
            )
            spec = importlib.util.spec_from_loader(loader_name, loader)
            require(spec is not None, "could not create poison loader spec")
            loaded = importlib.util.module_from_spec(spec)
            prior_pycache_prefix = sys.pycache_prefix
            sys.pycache_prefix = None
            try:
                loader.exec_module(loaded)
            finally:
                sys.pycache_prefix = prior_pycache_prefix
            require(
                loaded.FIXTURE_VALUE == "poisoned-pyc"
                and sentinel.exists(),
                f"{helper_name} poison fixture did not prove loader risk",
            )
            sentinel.unlink()
            retained = launcher._execute_module(
                f"summary_relearn_retained_{helper_name}",
                str(source_path),
                compile(
                    retained_source,
                    str(source_path),
                    "exec",
                    dont_inherit=True,
                    optimize=0,
                ),
            )
            require(
                retained.FIXTURE_VALUE == "retained-source"
                and retained.__cached__ is None
                and not sentinel.exists(),
                f"{helper_name} retained-buffer execution consulted pycache",
            )
            source_path.write_text(
                "FIXTURE_VALUE = 'live-toctou-replacement'\n"
                f"open({str(sentinel)!r}, 'w').close()\n"
            )
            retained_again = launcher._execute_module(
                f"summary_relearn_retained_again_{helper_name}",
                str(source_path),
                compile(
                    retained_source,
                    str(source_path),
                    "exec",
                    dont_inherit=True,
                    optimize=0,
                ),
            )
            require(
                retained_again.FIXTURE_VALUE == "retained-source"
                and source_path.read_bytes() != retained_source
                and not sentinel.exists(),
                f"{helper_name} retained buffer was replaced by live source",
            )


def artifact_publication_host_contracts(root: Path) -> None:
    runtime_path = root / "scripts/verify_summary_move_relearn_runtime.py"
    parsed = ast.parse(runtime_path.read_bytes(), filename=str(runtime_path))
    selected_names = {
        "EvidenceArtifactRegistry",
        "_fsync_directory",
        "_atomic_artifact_path",
        "_canonical_result_payload",
        "authenticate_result",
        "verify_authenticated_result",
        "write_result_atomic",
    }
    selected = [
        node
        for node in parsed.body
        if (
            isinstance(node, (ast.ClassDef, ast.FunctionDef))
            and node.name in selected_names
        )
    ]
    require(
        {node.name for node in selected} == selected_names,
        "runtime evidence artifact fixture could not select production code",
    )

    def runtime_require(condition: bool, message: str) -> None:
        if not condition:
            raise RuntimeError(message)

    fixture = types.ModuleType("summary_relearn_evidence_artifact_fixture")
    fixture.__dict__.update(
        {
            "hashlib": hashlib,
            "json": json,
            "os": os,
            "Path": Path,
            "BOOTSTRAP_AUTHENTICATION": {"fixture": "exact"},
            "BOOTSTRAP_REAUTHENTICATE": lambda: {"fixture": "exact"},
            "require": runtime_require,
            "stat": __import__("stat"),
            "tempfile": tempfile,
        }
    )
    compiled = compile(
        ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])),
        str(runtime_path),
        "exec",
        dont_inherit=True,
        optimize=0,
    )
    exec(compiled, fixture.__dict__)

    def expect_runtime_failure(callback: object, label: str) -> None:
        try:
            callback()
        except (RuntimeError, FileNotFoundError, IsADirectoryError, OSError):
            return
        require(False, f"{label} did not fail closed")

    with tempfile.TemporaryDirectory(
        prefix="summary-relearn-evidence-artifacts-"
    ) as temporary:
        temp = Path(temporary).resolve()
        registry = fixture.EvidenceArtifactRegistry()
        fixture.EVIDENCE_ARTIFACTS = registry
        capture = temp / "capture.png"
        capture.write_bytes(b"stale screenshot")
        capture_record = fixture._atomic_artifact_path(
            capture,
            lambda temporary: temporary.write_bytes(
                b"authenticated screenshot"
            ),
        )
        require(
            capture_record
            == {
                "path": str(capture),
                "size": len(b"authenticated screenshot"),
                "sha256": hashlib.sha256(
                    b"authenticated screenshot"
                ).hexdigest(),
            },
            "runtime screenshot record is not exact",
        )
        expect_runtime_failure(
            lambda: fixture._atomic_artifact_path(
                capture,
                lambda temporary: temporary.write_bytes(b"replacement"),
            ),
            "frozen artifact overwrite",
        )
        authenticated = fixture.authenticate_result(
            {
                "screenshots": [str(capture)],
                "nested": {"capture": str(capture)},
            }
        )
        parent_registry = fixture.EvidenceArtifactRegistry()
        fixture.EVIDENCE_ARTIFACTS = parent_registry
        fixture.verify_authenticated_result(authenticated)
        require(
            authenticated["screenshots"] == [capture_record]
            and authenticated["nested"]["capture"] == capture_record,
            "runtime result did not replace every artifact path claim",
        )
        require(
            parent_registry.reauthenticate() == [capture_record],
            "parent did not adopt and reauthenticate the child artifact",
        )
        tampered_result = json.loads(json.dumps(authenticated))
        tampered_result["nested"]["label"] = "substituted"
        expect_runtime_failure(
            lambda: fixture.verify_authenticated_result(tampered_result),
            "tampered child result",
        )
        tampered_record = json.loads(json.dumps(authenticated))
        tampered_record["screenshots"][0]["sha256"] = "0" * 64
        expect_runtime_failure(
            lambda: fixture.verify_authenticated_result(tampered_record),
            "tampered child artifact record",
        )

        missing_registry = fixture.EvidenceArtifactRegistry()
        expect_runtime_failure(
            lambda: missing_registry.register(temp / "missing.png"),
            "missing evidence artifact",
        )
        directory = temp / "directory"
        directory.mkdir()
        expect_runtime_failure(
            lambda: missing_registry.register(directory),
            "directory evidence artifact",
        )
        alias = temp / "capture-alias.png"
        alias.symlink_to(capture)
        expect_runtime_failure(
            lambda: missing_registry.register(alias),
            "symlink evidence artifact",
        )
        hardlink_registry = fixture.EvidenceArtifactRegistry()
        hardlink_registry.register(capture)
        hardlink = temp / "capture-hardlink.png"
        os.link(capture, hardlink)
        expect_runtime_failure(
            lambda: hardlink_registry.register(hardlink),
            "hard-linked evidence artifact alias",
        )
        protected_registry = fixture.EvidenceArtifactRegistry()
        protected_registry.protect(capture)
        expect_runtime_failure(
            lambda: protected_registry.register(capture),
            "protected evidence artifact alias",
        )

        mutation = temp / "mutation.png"
        mutation.write_bytes(b"before")
        mutation_registry = fixture.EvidenceArtifactRegistry()
        mutation_registry.register(mutation)
        mutation.write_bytes(b"after")
        expect_runtime_failure(
            mutation_registry.reauthenticate,
            "post-capture artifact mutation",
        )
        substitution = temp / "substitution.png"
        substitution.write_bytes(b"original inode")
        substitution_registry = fixture.EvidenceArtifactRegistry()
        substitution_registry.register(substitution)
        replacement = temp / "replacement.png"
        replacement.write_bytes(b"replacement inode")
        os.replace(replacement, substitution)
        expect_runtime_failure(
            substitution_registry.reauthenticate,
            "post-capture path substitution",
        )

        publication = temp / "result.json"
        publication.write_text('{"stale":true}\n')
        publication_registry = fixture.EvidenceArtifactRegistry()
        fixture.EVIDENCE_ARTIFACTS = publication_registry
        published_artifact = temp / "published.png"
        published_artifact.write_bytes(b"before publication")
        publication_registry.register(published_artifact)
        original_reauthenticate = publication_registry.reauthenticate
        calls = 0

        def mutate_after_publication() -> list[dict[str, object]]:
            nonlocal calls
            calls += 1
            if calls == 2:
                published_artifact.write_bytes(b"after publication")
            return original_reauthenticate()

        publication_registry.reauthenticate = mutate_after_publication
        expect_runtime_failure(
            lambda: fixture.write_result_atomic(
                publication, '{"passing":true}\n'
            ),
            "post-publication artifact mutation",
        )
        require(
            not publication.exists(),
            "failed artifact reauthentication retained a published result",
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
        ("success", "A"): ("list", False),
        ("success", "X"): ("list", False),
        ("success", "held-Down"): ("success", False),
        ("success", "fresh-Down"): ("list", False),
        ("success", "touch-more"): ("list", False),
        ("success", "touch-done"): ("inactive", False),
        ("list", "party-touch-switch"): ("list", False),
        ("slot", "box-arrow-switch"): ("list", False),
        ("confirm", "party-touch-switch"): ("list", False),
        ("hm", "box-arrow-switch"): ("list", False),
        ("empty", "party-touch-switch"): ("list", False),
        ("success", "box-arrow-switch"): ("list", False),
        ("list", "page-change"): ("inactive", False),
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

    task7_modes = {
        ("inactive", "X", "history"): ("list", "history"),
        ("list", "fresh-SELECT", "history"): ("list", "all"),
        ("list", "fresh-SELECT", "all"): ("list", "history"),
        ("empty", "fresh-SELECT", "history"): ("list", "all"),
        ("list", "held-SELECT", "all"): ("list", "all"),
        ("success", "A-More", "all"): ("list", "all"),
        ("list", "B-exit", "all"): ("inactive", "history"),
        ("list", "switch", "all"): ("list", "history"),
        ("list", "page-change", "all"): ("inactive", "history"),
        ("list", "identity-change", "all"): ("inactive", "history"),
    }
    require(
        all(result[1] == "history" for key, result in task7_modes.items()
            if key[1] in ("B-exit", "switch", "page-change", "identity-change"))
        and task7_modes[("list", "held-SELECT", "all")]
        == ("list", "all")
        and task7_modes[("success", "A-More", "all")]
        == ("list", "all"),
        "Task-7 host default/preserve/reset/held-input model differs",
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
        == 0xBD8,
        "packaged Summary state size is not 0xBD8",
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
        "PokemonMoveHistoryTask6_IsCanonical",
        "PokemonMoveHistoryTask6_AppendCandidateCall",
        "ArchiveDataLoadOfs",
        "LoadLevelUpLearnset_HandleAlternateForm",
        "PokeOtherFormMonsNoGet",
        "Party_GetCount",
        "Summary_GetPokemonData",
        "Summary_GetTouchAction",
        "Summary_GetPokemonSwitchTouch",
        "Summary_VanillaMainState",
    ):
        require(
            re.search(rf"R_ARM_ABS32\s+{target}\b", relocations) is not None
            and re.search(
                rf"R_ARM_THM_CALL\s+{target}\b",
                relocations,
            ) is None,
            f"Summary relearn lacks a safe typed relocation to {target}",
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
    parser.add_argument("--task7-focused", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    source_contracts(root)
    if args.task7_focused:
        host_state_contracts()
        print(
            "Summary move relearn Task 7 verification passed: source, "
            "toggle/reset state, compatibility order, and bounds"
        )
        return
    bootstrap_host_contracts(root)
    artifact_publication_host_contracts(root)
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
