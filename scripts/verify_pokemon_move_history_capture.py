#!/usr/bin/env python3
"""Task-3 static, host-fixture, relocation, and final hook verification."""

from __future__ import annotations

import argparse
import copy
import hashlib
import os
import re
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pokemon_move_history_build_manifest import (
    PACKAGED_ROM_LOGICAL_PATH,
    SCHEMA as BUILD_MANIFEST_SCHEMA,
    ManifestError,
    armips_dependency_paths,
    file_record,
    load_manifest,
    verify_manifest,
    verify_manifest_document,
)


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


def without_comments(source: str) -> str:
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)


def executable_function(source: str, name: str) -> str:
    return function_body(without_comments(source), name)


RECORDABLE_RETURN_RE = re.compile(
    r"\breturn\s+move\s*!=\s*MOVE_NONE"
    r"\s*&&\s*move\s*<\s*NUM_OF_MOVES"
    r"\s*&&\s*!\s*IsMoveUnimplemented\s*\(\s*move\s*\)\s*;"
)
APPEND_RECORDABLE_GUARD_RE = re.compile(
    r"\bif\s*\(\s*!PokemonMoveHistory_IsRecordableMove\s*\("
    r"\s*move\s*\)\s*\)\s*\{\s*return\s+FALSE\s*;\s*\}",
    re.S,
)
LEVEL_UP_SUCCESS_RE = re.compile(
    r"\bif\s*\(\s*ret\s*!=\s*\(u16\)\s*-\s*1u"
    r"\s*&&\s*ret\s*!=\s*\(u16\)\s*-\s*2u"
    r"\s*&&\s*ret\s*!=\s*MOVE_NONE\s*\)\s*\{",
    re.S,
)
LEVEL_UP_TRANSACTION_RE = re.compile(
    r"\bret\s*=\s*TryAppendMonMove\s*\(\s*mon\s*,\s*\*sp0\s*\)\s*;"
    r"\s*if\s*\(\s*ret\s*!=\s*\(u16\)\s*-\s*1u"
    r"\s*&&\s*ret\s*!=\s*\(u16\)\s*-\s*2u"
    r"\s*&&\s*ret\s*!=\s*MOVE_NONE\s*\)\s*\{"
    r"\s*SaveData\s*\*\s*saveData\s*=\s*SaveBlock2_get\s*\(\s*\)\s*;"
    r"\s*if\s*\(\s*saveData\s*!=\s*NULL\s*\)\s*\{"
    r"\s*PokemonMoveHistory_RecordMove\s*\("
    r"\s*saveData\s*,\s*&mon->box\s*,\s*\*sp0\s*\)\s*;"
    r"\s*\}\s*\}",
    re.S,
)
RECORD_MOVE_IMPL_RE = re.compile(
    r"^PokemonMoveHistory_RecordMoveImpl\s*\("
    r"\s*SaveData\s*\*\s*saveData\s*,"
    r"\s*struct\s+BoxPokemon\s*\*\s*pokemon\s*,"
    r"\s*u16\s+move\s*\)\s*\{"
    r"\s*PokemonMoveHistorySnapshot\s+snapshot\s*;"
    r"\s*struct\s+PokemonMoveHistoryRecord\s*\*\s*record\s*;"
    r"\s*if\s*\(\s*!PokemonMoveHistory_IsRecordableMove\s*\(\s*move\s*\)"
    r"\s*\)\s*\{\s*return\s+FALSE\s*;\s*\}"
    r"\s*if\s*\(\s*!PokemonMoveHistory_CaptureSnapshotImpl\s*\("
    r"\s*pokemon\s*,\s*&snapshot\s*\)\s*\)\s*\{"
    r"\s*return\s+FALSE\s*;\s*\}"
    r"\s*record\s*=\s*PokemonMoveHistory_ObserveSnapshot\s*\("
    r"\s*saveData\s*,\s*&snapshot\s*\)\s*;"
    r"\s*if\s*\(\s*record\s*==\s*NULL\s*\)\s*\{"
    r"\s*return\s+FALSE\s*;\s*\}"
    r"\s*PokemonMoveHistory_AppendMove\s*\("
    r"\s*saveData\s*,\s*&snapshot\s*,\s*record\s*,\s*move\s*\)\s*;"
    r"\s*return\s+TRUE\s*;\s*\}$",
    re.S,
)
PARTY_MENU_REPLACE_RE = re.compile(
    r"\bPokemonMoveHistory_ReplaceMove\s*\("
    r"\s*&mon->box\s*,\s*partyMenu->args->moveId\s*,\s*moveIdx\s*\)\s*;",
    re.S,
)
DELETE_MOVE_IMPL_RE = re.compile(
    r"^PokemonMoveHistory_DeleteMoveSlotImpl\s*\("
    r"\s*struct\s+PartyPokemon\s*\*\s*pokemon\s*,"
    r"\s*u32\s+slot\s*\)\s*\{"
    r"\s*if\s*\(\s*pokemon\s*==\s*NULL\s*\|\|\s*slot\s*>=\s*4\s*\)"
    r"\s*\{\s*return\s*;\s*\}"
    r"\s*PokemonMoveHistory_SeedImpl\s*\("
    r"\s*SaveBlock2_get\s*\(\s*\)\s*,\s*&pokemon->box\s*\)\s*;"
    r"\s*MonDeleteMoveSlot_Original\s*\(\s*pokemon\s*,\s*slot\s*\)\s*;"
    r"\s*\}$",
    re.S,
)
LEVEL_UP_COMMIT_REGION = (
    "if ((levelUpLearnset[*last_i] & LEVEL_UP_LEARNSET_LEVEL_MASK) == "
    "(level << LEVEL_UP_LEARNSET_LEVEL_SHIFT)) { "
    "*sp0 = LEVEL_UP_LEARNSET_MOVE(levelUpLearnset[*last_i]); "
    "(*last_i)++; "
    "#ifdef BLOCK_LEARNING_UNIMPLEMENTED_MOVES "
    "if (!IsMoveUnimplemented(*sp0)) "
    "#endif "
    "{ "
    "ret = TryAppendMonMove(mon, *sp0); "
    "if (ret != (u16)-1u && ret != (u16)-2u && ret != MOVE_NONE) { "
    "SaveData *saveData = SaveBlock2_get(); "
    "if (saveData != NULL) { "
    "PokemonMoveHistory_RecordMove( saveData, &mon->box, *sp0); "
    "} "
    "} "
    "} "
    "} "
    "sys_FreeMemoryEz(levelUpLearnset); "
    "return ret; "
    "}"
)
LEVEL_UP_EXECUTABLE_SHA256 = (
    "6a58f4e384533000ea32263208648e2eb77cec497c8aa9c383abbcfefad2847a"
)


def block_from_match(source: str, match: re.Match[str]) -> str:
    open_brace = source.find("{", match.start(), match.end())
    require(open_brace >= 0, "matched control block has no opening brace")
    cursor = open_brace + 1
    depth = 1
    while cursor < len(source) and depth:
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    require(depth == 0, "matched control block is unterminated")
    return source[match.start():cursor]


def predicate_contract_matches(history_source: str) -> bool:
    predicate_code = executable_function(
        history_source,
        "PokemonMoveHistory_IsRecordableMove",
    )
    return (
        len(RECORDABLE_RETURN_RE.findall(predicate_code)) == 1
        and predicate_code.count("IsMoveUnimplemented") == 1
    )


def append_guard_contract_matches(history_source: str) -> bool:
    append_code = executable_function(
        history_source,
        "PokemonMoveHistory_AppendMove",
    )
    return (
        len(APPEND_RECORDABLE_GUARD_RE.findall(append_code)) == 1
        and append_code.count("PokemonMoveHistory_IsRecordableMove") == 1
    )


def level_up_success_contract_matches(pokemon_source: str) -> bool:
    level_up_code = executable_function(
        pokemon_source,
        "MonTryLearnMoveOnLevelUp",
    )
    if re.match(
        r"^MonTryLearnMoveOnLevelUp\s*\("
        r"\s*struct\s+PartyPokemon\s*\*\s*mon\s*,"
        r"\s*int\s*\*\s*last_i\s*,\s*u16\s*\*\s*sp0\s*\)\s*\{",
        level_up_code,
        re.S,
    ) is None:
        return False
    transactions = list(LEVEL_UP_TRANSACTION_RE.finditer(level_up_code))
    if len(transactions) != 1:
        return False
    transaction = transactions[0]
    tail = level_up_code[transaction.end():]
    brace_depth = (
        level_up_code[:transaction.start()].count("{")
        - level_up_code[:transaction.start()].count("}")
    )
    containing_brace = level_up_code.rfind("{", 0, transaction.start())
    guard_prefix = level_up_code[:containing_brace]
    commit_region_start = level_up_code.rfind(
        "if ((levelUpLearnset[*last_i]"
    )
    normalized_commit_region = (
        " ".join(level_up_code[commit_region_start:].split())
        if commit_region_start >= 0
        else ""
    )
    normalized_function = " ".join(level_up_code.split()).encode()
    return (
        hashlib.sha256(normalized_function).hexdigest()
        == LEVEL_UP_EXECUTABLE_SHA256
        and level_up_code.count("TryAppendMonMove(") == 1
        and level_up_code.count("PokemonMoveHistory_RecordMove(") == 1
        and level_up_code.count("SaveBlock2_get(") == 1
        and brace_depth == 3
        and containing_brace >= 0
        and re.search(
            r"#ifdef\s+BLOCK_LEARNING_UNIMPLEMENTED_MOVES"
            r"\s*if\s*\(\s*!IsMoveUnimplemented\s*\(\s*\*sp0\s*\)\s*\)"
            r"\s*#endif\s*$",
            guard_prefix,
            re.S,
        )
        is not None
        and not level_up_code[
            containing_brace + 1:transaction.start()
        ].strip()
        and re.search(r"\b(?:ret|saveData)\s*=", tail) is None
        and normalized_commit_region == LEVEL_UP_COMMIT_REGION
        and re.search(
            r"\b(?:SetMonData|SetBoxMonData|MonSetMoveInSlot|"
            r"PartyMonSetMoveInSlot)\s*\(",
            level_up_code,
        )
        is None
    )


def record_move_contract_matches(history_source: str) -> bool:
    return (
        RECORD_MOVE_IMPL_RE.fullmatch(
            executable_function(
                history_source,
                "PokemonMoveHistory_RecordMoveImpl",
            )
        )
        is not None
    )


def party_menu_contract_matches(party_source: str) -> bool:
    code = executable_function(party_source, "PartyMenu_LearnMoveToSlot")
    replacement = PARTY_MENU_REPLACE_RE.search(code)
    function_brace = code.find("{")
    return (
        re.match(
            r"^PartyMenu_LearnMoveToSlot\s*\("
            r"\s*struct\s+PartyMenu\s*\*\s*partyMenu\s*,"
            r"\s*struct\s+PartyPokemon\s*\*\s*mon\s*,"
            r"\s*int\s+moveIdx\s*\)\s*\{",
            code,
            re.S,
        )
        is not None
        and replacement is not None
        and len(PARTY_MENU_REPLACE_RE.findall(code)) == 1
        and code.count("PokemonMoveHistory_ReplaceMove(") == 1
        and function_brace >= 0
        and not code[function_brace + 1:replacement.start()].strip()
        and replacement.start()
        < code.find("if (partyMenu->args->itemId != ITEM_NONE)")
        and re.search(
            r"\b(?:SetMonData|SetBoxMonData|MonSetMoveInSlot|"
            r"PartyMonSetMoveInSlot)\s*\(",
            code,
        )
        is None
    )


def delete_move_contract_matches(history_source: str) -> bool:
    return (
        DELETE_MOVE_IMPL_RE.fullmatch(
            executable_function(
                history_source,
                "PokemonMoveHistory_DeleteMoveSlotImpl",
            )
        )
        is not None
    )


def source_matcher_mutation_fixtures(
    history_source: str,
    pokemon_source: str,
    party_source: str,
) -> None:
    append_raw = function_body(
        history_source,
        "PokemonMoveHistory_AppendMove",
    )
    append_guard = APPEND_RECORDABLE_GUARD_RE.search(
        without_comments(append_raw)
    )
    require(append_guard is not None, "append mutation fixture lacks guard")
    executable_append = without_comments(append_raw)
    guard_text = append_guard.group(0)
    commented_append = executable_append.replace(
        guard_text,
        f"/* {guard_text} */",
        1,
    )
    ignored_append = executable_append.replace(
        guard_text,
        "PokemonMoveHistory_IsRecordableMove(move);",
        1,
    )
    require(
        not append_guard_contract_matches(
            history_source.replace(append_raw, commented_append, 1)
        ),
        "commented-out AppendMove guard passes source contracts",
    )
    require(
        not append_guard_contract_matches(
            history_source.replace(append_raw, ignored_append, 1)
        ),
        "ignored AppendMove predicate result passes source contracts",
    )

    predicate_raw = function_body(
        history_source,
        "PokemonMoveHistory_IsRecordableMove",
    )
    predicate_return = RECORDABLE_RETURN_RE.search(
        without_comments(predicate_raw)
    )
    require(
        predicate_return is not None,
        "predicate mutation fixture lacks executable return",
    )
    executable_predicate = without_comments(predicate_raw)
    return_text = predicate_return.group(0)
    comment_only_predicate = executable_predicate.replace(
        return_text,
        f"/* {return_text} */\n    return TRUE;",
        1,
    )
    ignored_implementation_result = executable_predicate.replace(
        return_text,
        "IsMoveUnimplemented(move);\n"
        "    return move != MOVE_NONE && move < NUM_OF_MOVES;",
        1,
    )
    require(
        not predicate_contract_matches(
            history_source.replace(
                predicate_raw,
                comment_only_predicate,
                1,
            )
        ),
        "comment-only recordable predicate passes source contracts",
    )
    require(
        not predicate_contract_matches(
            history_source.replace(
                predicate_raw,
                ignored_implementation_result,
                1,
            )
        ),
        "ignored IsMoveUnimplemented result passes source contracts",
    )

    level_up_raw = function_body(
        pokemon_source,
        "MonTryLearnMoveOnLevelUp",
    )
    executable_level_up = without_comments(level_up_raw)
    level_up_guard = LEVEL_UP_SUCCESS_RE.search(executable_level_up)
    require(
        level_up_guard is not None,
        "level-up mutation fixture lacks success guard",
    )
    level_up_header = executable_level_up[
        level_up_guard.start():executable_level_up.find(
            "{",
            level_up_guard.start(),
            level_up_guard.end(),
        )
    ]
    ignored_level_up = executable_level_up.replace(
        level_up_header,
        "ret != (u16)-1u;\n"
        "            ret != (u16)-2u;\n"
        "            ret != MOVE_NONE;\n"
        "            if (TRUE) ",
        1,
    )
    clobbered_level_up = (
        executable_level_up[:level_up_guard.start()]
        + "ret = 0;\n            "
        + executable_level_up[level_up_guard.start():]
    )
    save_assignment_text = "SaveData *saveData = SaveBlock2_get();"
    clobbered_save = executable_level_up.replace(
        save_assignment_text,
        save_assignment_text + "\n                saveData = NULL;",
        1,
    )
    wrong_record_arguments = executable_level_up.replace(
        "saveData,\n                        &mon->box,\n                        *sp0",
        "NULL,\n                        &mon->box,\n                        MOVE_NONE",
        1,
    )
    post_record_ret_clobber = executable_level_up.replace(
        "PokemonMoveHistory_RecordMove(\n"
        "                        saveData,\n"
        "                        &mon->box,\n"
        "                        *sp0);",
        "PokemonMoveHistory_RecordMove(\n"
        "                        saveData,\n"
        "                        &mon->box,\n"
        "                        *sp0);\n"
        "                    ret = 0;",
        1,
    )
    level_transaction = LEVEL_UP_TRANSACTION_RE.search(executable_level_up)
    require(
        level_transaction is not None,
        "level-up mutation fixture lacks exact transaction",
    )
    post_guard_save_clobber = (
        executable_level_up[:level_transaction.end()]
        + "\n            saveData = NULL;"
        + executable_level_up[level_transaction.end():]
    )
    wrapped_level_up = (
        executable_level_up[:level_transaction.start()]
        + "if (FALSE) {\n"
        + executable_level_up[
            level_transaction.start():level_transaction.end()
        ]
        + "\n            }"
        + executable_level_up[level_transaction.end():]
    )
    disabled_implementation_guard = executable_level_up.replace(
        "if (!IsMoveUnimplemented(*sp0))",
        "if (FALSE)",
        1,
    )
    unreachable_guard_prefix = executable_level_up.replace(
        "#ifdef BLOCK_LEARNING_UNIMPLEMENTED_MOVES",
        "goto skip_history;\n"
        "        #ifdef BLOCK_LEARNING_UNIMPLEMENTED_MOVES",
        1,
    ).replace(
        "    sys_FreeMemoryEz(levelUpLearnset);",
        "skip_history:;\n"
        "    sys_FreeMemoryEz(levelUpLearnset);",
        1,
    )
    post_transaction_raw_setter = executable_level_up.replace(
        "PokemonMoveHistory_RecordMove(\n"
        "                        saveData,\n"
        "                        &mon->box,\n"
        "                        *sp0);",
        "PokemonMoveHistory_RecordMove(\n"
        "                        saveData,\n"
        "                        &mon->box,\n"
        "                        *sp0);\n"
        "                    SetBoxMonData \n"
        "                        (&mon->box, MON_DATA_MOVE1, NULL);",
        1,
    )
    outer_region_skip = executable_level_up.replace(
        "if ((levelUpLearnset[*last_i]",
        "goto skip_all_history;\n"
        "    if ((levelUpLearnset[*last_i]",
        1,
    ).replace(
        "    sys_FreeMemoryEz(levelUpLearnset);",
        "skip_all_history:;\n"
        "    sys_FreeMemoryEz(levelUpLearnset);",
        1,
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, ignored_level_up, 1)
        ),
        "ignored level-up success results pass source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, clobbered_level_up, 1)
        ),
        "clobbered level-up helper result passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, clobbered_save, 1)
        ),
        "clobbered SaveBlock2_get result passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, wrong_record_arguments, 1)
        ),
        "wrong level-up RecordMove arguments pass source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, post_record_ret_clobber, 1)
        ),
        "post-record level-up ret clobber passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, post_guard_save_clobber, 1)
        ),
        "after-guard level-up saveData clobber passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, wrapped_level_up, 1)
        ),
        "unreachable wrapped level-up transaction passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(
                level_up_raw,
                disabled_implementation_guard,
                1,
            )
        ),
        "replaced level-up implementation guard passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(
                level_up_raw,
                unreachable_guard_prefix,
                1,
            )
        ),
        "unreachable prefix before level-up guard passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(
                level_up_raw,
                post_transaction_raw_setter,
                1,
            )
        ),
        "post-transaction level-up raw setter passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(
                level_up_raw,
                outer_region_skip,
                1,
            )
        ),
        "outer-prefix skip around level-up region passes source contracts",
    )

    record_raw = function_body(
        history_source,
        "PokemonMoveHistory_RecordMoveImpl",
    )
    executable_record = without_comments(record_raw)
    record_mutations = {
        "ignored predicate": executable_record.replace(
            "if (!PokemonMoveHistory_IsRecordableMove(move)) {\n"
            "        return FALSE;\n"
            "    }",
            "PokemonMoveHistory_IsRecordableMove(move);",
            1,
        ),
        "duplicate predicate": executable_record.replace(
            "if (!PokemonMoveHistory_IsRecordableMove(move)) {",
            "PokemonMoveHistory_IsRecordableMove(move);\n"
            "    if (!PokemonMoveHistory_IsRecordableMove(move)) {",
            1,
        ),
        "pre-predicate dirty mutation": executable_record.replace(
            "if (!PokemonMoveHistory_IsRecordableMove(move)) {",
            "saveData->pokemonMoveHistoryDirty = TRUE;\n"
            "    if (!PokemonMoveHistory_IsRecordableMove(move)) {",
            1,
        ),
        "post-guard saveData clobber": executable_record.replace(
            "if (!PokemonMoveHistory_CaptureSnapshotImpl",
            "saveData = NULL;\n"
            "    if (!PokemonMoveHistory_CaptureSnapshotImpl",
            1,
        ),
        "wrong append arguments": executable_record.replace(
            "saveData,\n        &snapshot,\n        record,\n        move",
            "NULL,\n        &snapshot,\n        record,\n        MOVE_NONE",
            1,
        ),
    }
    for label, mutation in record_mutations.items():
        require(
            not record_move_contract_matches(
                history_source.replace(record_raw, mutation, 1)
            ),
            f"{label} passes RecordMoveImpl source contracts",
        )

    delete_raw = function_body(
        history_source,
        "PokemonMoveHistory_DeleteMoveSlotImpl",
    )
    executable_delete = without_comments(delete_raw)
    delete_mutations = {
        "wrong seed save": executable_delete.replace(
            "SaveBlock2_get(),",
            "NULL,",
            1,
        ),
        "wrong seed Pokémon": executable_delete.replace(
            "&pokemon->box",
            "NULL",
            1,
        ),
        "wrong delete slot": executable_delete.replace(
            "MonDeleteMoveSlot_Original(pokemon, slot);",
            "MonDeleteMoveSlot_Original(pokemon, 0);",
            1,
        ),
        "reversed delete order": executable_delete.replace(
            "PokemonMoveHistory_SeedImpl(\n"
            "        SaveBlock2_get(),\n"
            "        &pokemon->box);\n"
            "    MonDeleteMoveSlot_Original(pokemon, slot);",
            "MonDeleteMoveSlot_Original(pokemon, slot);\n"
            "    PokemonMoveHistory_SeedImpl(\n"
            "        SaveBlock2_get(),\n"
            "        &pokemon->box);",
            1,
        ),
    }
    for label, mutation in delete_mutations.items():
        require(
            not delete_move_contract_matches(
                history_source.replace(delete_raw, mutation, 1)
            ),
            f"{label} passes DeleteMoveSlotImpl source contracts",
        )

    party_raw = function_body(party_source, "PartyMenu_LearnMoveToSlot")
    executable_party = without_comments(party_raw)
    for label, mutation in {
        "wrong Pokémon": executable_party.replace("&mon->box", "NULL", 1),
        "wrong learned move": executable_party.replace(
            "partyMenu->args->moveId",
            "moveIdx",
            1,
        ),
        "swapped move and slot": executable_party.replace(
            "partyMenu->args->moveId,\n        moveIdx",
            "moveIdx,\n        partyMenu->args->moveId",
            1,
        ),
        "duplicate replacement": executable_party.replace(
            "PokemonMoveHistory_ReplaceMove(",
            "PokemonMoveHistory_ReplaceMove(&mon->box, "
            "partyMenu->args->moveId, moveIdx);\n"
            "    PokemonMoveHistory_ReplaceMove(",
            1,
        ),
        "unreachable replacement": executable_party.replace(
            "PokemonMoveHistory_ReplaceMove(",
            "if (FALSE) {\n"
            "        PokemonMoveHistory_ReplaceMove(",
            1,
        ).replace(
            "moveIdx);\n    if (partyMenu->args->itemId",
            "moveIdx);\n    }\n"
            "    if (partyMenu->args->itemId",
            1,
        ),
        "raw pre-replacement setter": executable_party.replace(
            "PokemonMoveHistory_ReplaceMove(",
            "SetBoxMonData(&mon->box, MON_DATA_MOVE1 + moveIdx, NULL);\n"
            "    PokemonMoveHistory_ReplaceMove(",
            1,
        ),
        "spaced post-replacement setter": executable_party.replace(
            "moveIdx);\n    if (partyMenu->args->itemId",
            "moveIdx);\n"
            "    SetBoxMonData \n"
            "        (&mon->box, MON_DATA_MOVE1 + moveIdx, NULL);\n"
            "    if (partyMenu->args->itemId",
            1,
        ),
    }.items():
        require(
            not party_menu_contract_matches(
                party_source.replace(party_raw, mutation, 1)
            ),
            f"{label} passes PartyMenu replacement source contracts",
        )


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
    header_code = without_comments(header)
    history_code = without_comments(history)
    pokemon_code = without_comments(pokemon)
    party_menu_code = without_comments(party_menu)
    config_code = without_comments(config)

    for api in (
        "PokemonMoveHistory_ReplaceMove",
        "PokemonMoveHistory_DeleteMoveSlot",
    ):
        require(
            re.search(rf"\bLONG_CALL\s+{api}\s*\(", header_code) is not None,
            f"{api} is not a typed long-call API",
        )

    require(
        predicate_contract_matches(history),
        "recordable-move predicate is not the exact executable valid/range/"
        "implemented expression",
    )
    require(
        append_guard_contract_matches(history),
        "AppendMove does not execute and consume exactly one recordable-move "
        "predicate before mutation",
    )
    append = function_body(history_code, "PokemonMoveHistory_AppendMove")
    append_guard = APPEND_RECORDABLE_GUARD_RE.search(append)
    require(append_guard is not None, "AppendMove executable guard is missing")
    ordered(
        append,
        [
            append_guard.group(0),
            "for (i = 0; i < record->moveCount; i++)",
            "if (record->moveCount == POKEMON_MOVE_HISTORY_MAX_MOVES)",
            "record->moveCount--;",
            "store = saveData->pokemonMoveHistory;",
            "record->moves[record->moveCount++] = move;",
            "record->lastTouched = ++store->header.nextAccessSequence;",
            "saveData->pokemonMoveHistoryDirty = TRUE;",
            "saveData->pokemonMoveHistoryRevision++;",
        ],
        "AppendMove predicate and mutation transaction",
    )
    for mutation in (
        "PokemonMoveHistory_OverlayMemcpy(",
        "record->moveCount--;",
        "record->moves[record->moveCount++] = move;",
        "record->speciesSnapshot = snapshot->species;",
        "record->lastTouched = ++store->header.nextAccessSequence;",
        "saveData->pokemonMoveHistoryDirty = TRUE;",
        "saveData->pokemonMoveHistoryRevision++;",
    ):
        require(
            append.find(mutation) > append_guard.end(),
            f"AppendMove mutation {mutation!r} can precede its executable "
            "predicate",
        )
    require(
        re.search(
            r"^\s*#\s*define\s+BLOCK_LEARNING_UNIMPLEMENTED_MOVES(?:\s|$)",
            config_code,
            re.MULTILINE,
        )
        is not None,
        "host unimplemented-move fixture requires the runtime policy enabled",
    )
    source_matcher_mutation_fixtures(history, pokemon, party_menu)

    replace_code = function_body(
        history_code,
        "PokemonMoveHistory_ReplaceMoveImpl",
    )
    ordered(
        replace_code,
        [
            "PokemonMoveHistory_IsRecordableMove(move)",
            "GetBoxMonData(",
            "MON_DATA_MOVE1 + slot",
            "NULL) == move",
            "PokemonMoveHistory_CaptureSnapshotImpl",
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
        re.search(
            r"if\s*\(\s*\(u16\)\s*GetBoxMonData\s*\("
            r"\s*pokemon\s*,\s*MON_DATA_MOVE1\s*\+\s*slot\s*,"
            r"\s*NULL\s*\)\s*==\s*move\s*\)\s*\{"
            r"\s*return\s+FALSE\s*;\s*\}",
            replace_code,
            re.DOTALL,
        )
        is not None,
        "same-slot replacement does not return FALSE before full snapshot",
    )
    require(
        "before.moves[slot] == move" not in replace_code,
        "same-slot replacement still depends on the full snapshot",
    )
    require(
        re.search(
            r"if\s*\(\s*!PokemonMoveHistory_CaptureSnapshotImpl\s*\("
            r"[^)]*\)\s*\)\s*\{\s*return\s+FALSE\s*;\s*\}",
            replace_code,
            re.DOTALL,
        )
        is not None,
        "snapshot failure does not return FALSE before mutation",
    )
    require(
        replace_code.count("SaveBlock2_get()") == 1,
        "replacement does not resolve exactly one current save per transaction",
    )
    require(
        record_move_contract_matches(history),
        "RecordMoveImpl is not the exact guarded capture/observe/append "
        "transaction",
    )
    record_move_code = function_body(
        history_code,
        "PokemonMoveHistory_RecordMoveImpl",
    )
    ordered(
        record_move_code,
        [
            "PokemonMoveHistory_IsRecordableMove(move)",
            "PokemonMoveHistory_CaptureSnapshotImpl",
            "PokemonMoveHistory_ObserveSnapshot",
            "PokemonMoveHistory_AppendMove",
        ],
        "record-move transaction",
    )
    require(
        re.search(
            r"if\s*\(\s*!PokemonMoveHistory_IsRecordableMove\s*\("
            r"\s*move\s*\)\s*\)\s*\{\s*return\s+FALSE\s*;\s*\}",
            record_move_code,
            re.DOTALL,
        )
        is not None,
        "RecordMove invalid guard does not return FALSE before snapshot access",
    )
    require(
        delete_move_contract_matches(history),
        "DeleteMoveSlotImpl does not use the exact seed-before-delete call flow",
    )
    delete = function_body(
        history_code,
        "PokemonMoveHistory_DeleteMoveSlotImpl",
    )
    ordered(
        delete,
        [
            "PokemonMoveHistory_SeedImpl",
            "SaveBlock2_get()",
            "MonDeleteMoveSlot_Original",
        ],
        "move deletion transaction",
    )

    level_up = function_body(pokemon_code, "MonTryLearnMoveOnLevelUp")
    require(
        level_up_success_contract_matches(pokemon),
        "level-up history recording is not controlled by the exact successful "
        "append result",
    )
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

    learn_slot = function_body(
        party_menu_code,
        "PartyMenu_LearnMoveToSlot",
    )
    require(
        party_menu_contract_matches(party_menu),
        "party-menu learning does not call exact "
        "ReplaceMove(&mon->box, moveId, moveIdx)",
    )
    require(
        "SetMonData(" not in learn_slot,
        "party-menu replacement still mutates outside the central transaction",
    )

    seed_party_code = function_body(
        history_code,
        "PokemonMoveHistory_SeedParty",
    )
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
        history_code,
        "PokemonMoveHistory_LoadAndSeedPartyImpl",
    )
    require(
        "PokemonMoveHistory_SeedParty" not in load_boundary,
        "party reconciliation runs before the active save is boot-stable",
    )
    save_boundary = function_body(
        history_code,
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
    seal_command = "scripts/pokemon_move_history_build_manifest.py"
    verifier_command = (
        "scripts/verify_pokemon_move_history_capture.py \\\n"
        "\t\t--manifest $(MOVE_HISTORY_CAPTURE_MANIFEST) "
        "--rom $(BUILDROM).tmp"
    )
    final_verifier_command = (
        "scripts/verify_pokemon_move_history.py --rom $(BUILDROM).tmp"
    )
    publish_command = "mv $(BUILDROM).tmp $(BUILDROM)"
    seal_start = makefile.find(seal_command)
    verifier_start = makefile.find(verifier_command)
    seal_block = (
        makefile[seal_start:verifier_start]
        if seal_start >= 0 and verifier_start > seal_start
        else ""
    )
    require(
        makefile.count("scripts/verify_pokemon_move_history_capture.py") == 1
        and makefile.count(
            "scripts/pokemon_move_history_build_manifest.py"
        ) == 1
        and makefile.count(final_verifier_command) == 1
        and package_command in makefile
        and seal_command in makefile
        and "--seal $(MOVE_HISTORY_CAPTURE_MANIFEST) "
        "--rom $(BUILDROM).tmp" in seal_block
        and verifier_command in makefile
        and final_verifier_command in makefile
        and publish_command in makefile
        and makefile.index(package_command) < makefile.index(seal_command)
        < makefile.index(verifier_command)
        < makefile.index(final_verifier_command)
        < makefile.index(publish_command),
        "capture manifest/verifiers are not wired once in fail-closed "
        "post-package/publish order",
    )
    require(
        set(re.findall(r'--context\s+"([A-Z_]+)=', seal_block))
        == {
            "ARMIPS",
            "ARMIPS_FLAGS",
            "AS",
            "ASFLAGS",
            "CC",
            "CFLAGS",
            "LD",
            "LDFLAGS",
            "NDSTOOL",
            "OBJCOPY",
        },
        "manifest seal does not record the exact effective build context",
    )
    forced_objects_match = re.search(
        r"MOVE_HISTORY_CAPTURE_OBJECTS\s*=\s*\\\n"
        r"(.*?)"
        r"\n\.PHONY:\s*FORCE_MOVE_HISTORY_CAPTURE_OBJECTS",
        makefile,
        re.S,
    )
    require(
        forced_objects_match is not None
        and {
            "$(BUILD)/pokemon.o",
            "$(BUILD)/party_menu.o",
            "$(BUILD)/pokemon_move_history_overlay/pokemon_move_history.o",
            "$(BUILD)/pokemon_move_history_overlay/pokemon_move_relearn.o",
            "$(BUILD)/pokemon_move_history_overlay/entry.o",
            "$(BUILD)/pokemon_move_history_overlay/thumb_help.o",
        }
        == set(re.findall(r"\$\(BUILD\)/[^\s\\]+", forced_objects_match.group(1)))
        and "$(MOVE_HISTORY_CAPTURE_OBJECTS): "
        "FORCE_MOVE_HISTORY_CAPTURE_OBJECTS" in makefile,
        "task-3 provenance does not force exactly the six capture objects",
    )


def move_limits() -> tuple[int, int, int]:
    moves_header = (REPO / "include/constants/moves.h").read_text()
    executable = without_comments(moves_header)
    none_match = re.search(
        r"^#define\s+MOVE_NONE\s+(\d+)$",
        executable,
        re.MULTILINE,
    )
    canonical_match = re.search(
        r"^#define\s+NUM_OF_CANONICAL_MOVES\s+(\d+)$",
        executable,
        re.MULTILINE,
    )
    custom_match = re.search(
        r"^#define\s+NUM_OF_CUSTOM_MOVES\s+(\d+)$",
        executable,
        re.MULTILINE,
    )
    require(
        none_match is not None
        and canonical_match is not None
        and custom_match is not None,
        "move-count constants are not simple deterministic integers",
    )
    move_none = int(none_match.group(1))
    canonical = int(canonical_match.group(1))
    custom = int(custom_match.group(1))
    require(move_none == 0, "MOVE_NONE is no longer zero")
    require(canonical >= 2 and custom >= 0, "move-count constants are invalid")
    return canonical, custom, canonical + custom


def manifest_mutation_fixtures() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        input_path = root / "input.c"
        output_path = root / "linked.o"
        temporary_rom = root / "test.nds.tmp"
        final_rom = root / "test.nds"
        (root / "armips").mkdir()
        (root / "build").mkdir()
        armips_entry = root / "armips/global.s"
        armips_nested = root / "armips/nested.s"
        incbin_path = root / "build/payload.bin"
        importobj_path = root / "build/imported.o"
        armips_entry.write_text('.include "armips/nested.s"\n')
        armips_nested.write_text(
            '.incbin "build/payload.bin"\n'
            '.importobj "build/imported.o"\n'
        )
        incbin_path.write_bytes(b"generation-a incbin")
        importobj_path.write_bytes(b"generation-a imported object")
        fixture_input_paths = {
            "input.c",
            "armips/global.s",
            "armips/nested.s",
            "build/payload.bin",
            "build/imported.o",
        }
        require(
            armips_dependency_paths(root, armips_entry)
            == fixture_input_paths - {"input.c"},
            "ARMIPS fixture does not close over nested incbin inputs",
        )
        input_path.write_bytes(b"generation-a source")
        output_path.write_bytes(b"generation-a output")
        temporary_rom.write_bytes(b"generation-a packaged rom")
        document = {
            "schema": BUILD_MANIFEST_SCHEMA,
            "build_context": {"fixture-tool": "fixture-tool"},
            "inputs": {
                path: file_record(root / path)
                for path in sorted(fixture_input_paths)
            },
            "outputs": {
                "linked": {
                    "path": "linked.o",
                    **file_record(output_path),
                },
                "packaged_rom": {
                    "path": PACKAGED_ROM_LOGICAL_PATH,
                    **file_record(temporary_rom),
                },
            },
            "tools": {
                "fixture-tool": {
                    "command": "fixture-tool",
                    "version": "fixture 1",
                    "binary": {"size": 1, "sha256": "0" * 64},
                },
            },
        }

        def verify_fixture(candidate: dict[str, object], rom: Path) -> None:
            verify_manifest_document(
                candidate,
                root,
                fixture_input_paths,
                {"linked": "linked.o"},
                rom,
                {"fixture-tool"},
                {"fixture-tool"},
            )

        def must_reject(
            label: str,
            candidate: dict[str, object],
            rom: Path = final_rom,
        ) -> None:
            try:
                verify_fixture(candidate, rom)
            except ManifestError:
                return
            require(False, f"{label} passes full manifest schema verification")

        temporary_rom.rename(final_rom)
        verify_fixture(document, final_rom)

        os.utime(input_path, (1, 1))
        input_path.write_bytes(b"generation-b current source")
        os.utime(input_path, (1, 1))
        must_reject("coherent backdated stale generation", document)
        input_path.write_bytes(b"generation-a source")

        output_path.write_bytes(b"mutated output")
        os.utime(output_path, (2_000_000_000, 2_000_000_000))
        must_reject("future-dated changed output", document)
        output_path.write_bytes(b"generation-a output")

        incbin_path.write_bytes(b"mutated incbin")
        must_reject("changed recursively reached incbin", document)
        incbin_path.write_bytes(b"generation-a incbin")

        importobj_path.write_bytes(b"mutated imported object")
        must_reject("changed recursively reached importobj", document)
        importobj_path.write_bytes(b"generation-a imported object")

        missing_role = copy.deepcopy(document)
        del missing_role["outputs"]["linked"]
        must_reject("missing output role", missing_role)
        extra_role = copy.deepcopy(document)
        extra_role["outputs"]["extra"] = copy.deepcopy(
            document["outputs"]["linked"]
        )
        must_reject("unknown output role", extra_role)
        wrong_binding = copy.deepcopy(document)
        wrong_binding["inputs"]["input.c"]["sha256"] = "f" * 64
        must_reject("wrong input hash binding", wrong_binding)
        wrong_rom_path = copy.deepcopy(document)
        wrong_rom_path["outputs"]["packaged_rom"]["path"] = "test.nds.tmp"
        must_reject("temporary packaged-ROM path binding", wrong_rom_path)
        wrong_tool = copy.deepcopy(document)
        wrong_tool["tools"]["unknown"] = wrong_tool["tools"].pop(
            "fixture-tool"
        )
        must_reject("unknown tool role", wrong_tool)
        tampered_tool = copy.deepcopy(document)
        tampered_tool["tools"]["fixture-tool"]["command"] = "other-tool"
        must_reject("tool/build-context binding tamper", tampered_tool)
        malformed_tool_hash = copy.deepcopy(document)
        malformed_tool_hash["tools"]["fixture-tool"]["binary"]["sha256"] = "bad"
        must_reject("malformed tool identity hash", malformed_tool_hash)

        malformed = root / "malformed.json"
        malformed.write_text('{"schema":')
        try:
            load_manifest(malformed)
        except ManifestError:
            pass
        else:
            require(False, "truncated manifest JSON is accepted")


def host_fixtures() -> None:
    max_moves = 24
    _canonical, _custom, num_moves = move_limits()
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

    def make_public_state(existing_record: bool) -> dict[str, object]:
        return {
            "allocated": existing_record,
            "allocations": 0,
            "dirty": False,
            "revision": 0,
            "history": [31] if existing_record else [],
            "moves": [1, 2, 3, 4],
            "mutations": 0,
            "snapshot_reads": 0,
            "store_accesses": 0,
        }

    def clone_public_state(state: dict[str, object]) -> dict[str, object]:
        return {
            key: list(value) if isinstance(value, list) else value
            for key, value in state.items()
        }

    def public_append(state: dict[str, object], move: int) -> bool:
        history = state["history"]
        require(isinstance(history, list), "fixture history type differs")
        if not valid(move) or move in history:
            return False
        history.append(move)
        state["dirty"] = True
        state["revision"] = int(state["revision"]) + 1
        return True

    def public_observe(state: dict[str, object]) -> None:
        state["store_accesses"] = int(state["store_accesses"]) + 1
        if not state["allocated"]:
            state["allocated"] = True
            state["allocations"] = int(state["allocations"]) + 1
            state["dirty"] = True
            state["revision"] = int(state["revision"]) + 1
        moves = state["moves"]
        require(isinstance(moves, list), "fixture move-slot type differs")
        for current_move in moves:
            public_append(state, current_move)

    def record_move_public(state: dict[str, object], move: int) -> bool:
        if not valid(move):
            return False
        state["snapshot_reads"] = int(state["snapshot_reads"]) + 1
        public_observe(state)
        public_append(state, move)
        return True

    def replace_move_public(
        state: dict[str, object],
        slot: int,
        move: int,
    ) -> bool:
        moves = state["moves"]
        require(isinstance(moves, list), "fixture move-slot type differs")
        if not valid(move) or not 0 <= slot < 4:
            return False
        if moves[slot] == move:
            return False
        state["snapshot_reads"] = int(state["snapshot_reads"]) + 1
        public_observe(state)
        moves[slot] = move
        state["mutations"] = int(state["mutations"]) + 1
        public_append(state, move)
        return True

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
        for existing_record in (False, True):
            for public_path in (record_move_public, replace_move_public):
                public_state = make_public_state(existing_record)
                public_before = clone_public_state(public_state)
                if public_path is record_move_public:
                    success = record_move_public(public_state, invalid_move)
                else:
                    success = replace_move_public(
                        public_state,
                        1,
                        invalid_move,
                    )
                require(
                    not success
                    and public_state == public_before
                    and public_state["allocations"] == 0
                    and public_state["dirty"] is False
                    and public_state["revision"] == 0
                    and public_state["snapshot_reads"] == 0
                    and public_state["store_accesses"] == 0
                    and public_state["mutations"] == 0,
                    f"invalid {public_path.__name__} input {invalid_move} "
                    f"changes empty/existing={existing_record} state",
                )
    for existing_record in (False, True):
        same_slot_state = make_public_state(existing_record)
        same_slot_before = clone_public_state(same_slot_state)
        same_slot_success = replace_move_public(same_slot_state, 1, 2)
        require(
            not same_slot_success
            and same_slot_state == same_slot_before
            and same_slot_state["allocations"] == 0
            and same_slot_state["dirty"] is False
            and same_slot_state["revision"] == 0
            and same_slot_state["mutations"] == 0
            and same_slot_state["snapshot_reads"] == 0
            and same_slot_state["store_accesses"] == 0,
            f"same-slot ReplaceMove changes or accesses "
            f"empty/existing={existing_record} state",
        )
    valid_record_state = make_public_state(False)
    require(
        record_move_public(valid_record_state, high_valid)
        and valid_record_state["allocated"] is True
        and valid_record_state["allocations"] == 1
        and valid_record_state["dirty"] is True
        and int(valid_record_state["revision"]) > 0
        and valid_record_state["snapshot_reads"] == 1
        and valid_record_state["store_accesses"] == 1
        and valid_record_state["mutations"] == 0,
        "valid high-ID RecordMove control does not succeed and record state",
    )
    valid_replace_state = make_public_state(False)
    require(
        replace_move_public(valid_replace_state, 1, high_valid)
        and valid_replace_state["allocated"] is True
        and valid_replace_state["allocations"] == 1
        and valid_replace_state["dirty"] is True
        and int(valid_replace_state["revision"]) > 0
        and valid_replace_state["mutations"] == 1
        and valid_replace_state["snapshot_reads"] == 1
        and valid_replace_state["store_accesses"] == 1
        and valid_replace_state["moves"] == [1, high_valid, 3, 4],
        "valid high-ID ReplaceMove control does not mutate and record state",
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
    scanner_base = 0x02000000
    scanner_image = b"\x00\xf0\x00\xf8\x80\x47"
    require(
        packaged_thumb_calls(
            scanner_image,
            scanner_base,
            scanner_base,
            len(scanner_image),
        )
        == [
            (scanner_base, "bl", scanner_base + 4),
            (scanner_base + 4, "blx_reg", 0),
        ],
        "packaged call scanner does not decode BL and BLX-register forms",
    )
    manifest_mutation_fixtures()


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


def symbol_sizes(path: Path) -> dict[str, int]:
    output = subprocess.check_output(
        ["arm-none-eabi-nm", "-S", str(path)],
        text=True,
    )
    sizes: dict[str, int] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            sizes[parts[3]] = int(parts[1], 16)
    return sizes


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


def thumb_blx_target(image: bytes, base: int, address: int) -> int:
    offset = address - base
    first, second = struct.unpack_from("<HH", image, offset)
    require(
        first & 0xF800 == 0xF000 and second & 0xF800 == 0xE800,
        f"0x{address:08X} is not a Thumb-1 BLX immediate",
    )
    delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if delta & (1 << 22):
        delta -= 1 << 23
    return ((address + 4) & ~3) + delta


def thumb_conditional_branch(
    image: bytes,
    base: int,
    address: int,
    condition: int,
) -> int:
    halfword = struct.unpack_from("<H", image, address - base)[0]
    require(
        halfword & 0xF000 == 0xD000
        and (halfword >> 8) & 0xF == condition,
        f"0x{address:08X} is not the expected Thumb conditional branch",
    )
    delta = (halfword & 0xFF) << 1
    if delta & 0x100:
        delta -= 0x200
    return address + 4 + delta


def thumb_literal_load(
    image: bytes,
    base: int,
    address: int,
    register: int,
) -> tuple[int, int]:
    halfword = struct.unpack_from("<H", image, address - base)[0]
    require(
        halfword & 0xF800 == 0x4800
        and (halfword >> 8) & 0x7 == register,
        f"0x{address:08X} is not the expected Thumb literal load",
    )
    literal_address = ((address + 4) & ~3) + ((halfword & 0xFF) << 2)
    value = struct.unpack_from("<I", image, literal_address - base)[0]
    return literal_address, value


def encode_thumb_blx(address: int, target: int) -> bytes:
    delta = target - ((address + 4) & ~3)
    require(
        -(1 << 22) <= delta < (1 << 22)
        and delta % 4 == 0
        and target % 4 == 0,
        f"Thumb BLX 0x{address:08X}->0x{target:08X} is out of range/alignment",
    )
    first = 0xF000 | ((delta >> 12) & 0x7FF)
    second = 0xE800 | ((delta >> 1) & 0x7FF)
    return struct.pack("<HH", first, second)


def direct_thumb_calls(disassembly: str) -> list[tuple[int, str, int]]:
    call_line = re.compile(
        r"^\s*([0-9a-f]+):\s+"
        r"[0-9a-f]{4}(?:\s+[0-9a-f]{4})?\s+"
        r"(bl|blx)\s+([0-9a-f]+)\b"
    )
    calls: list[tuple[int, str, int]] = []
    for line in disassembly.splitlines():
        match = call_line.match(line)
        if match is not None:
            calls.append(
                (
                    int(match.group(1), 16),
                    match.group(2),
                    int(match.group(3), 16),
                )
            )
    return calls


def packaged_thumb_calls(
    image: bytes,
    base: int,
    address: int,
    size: int,
) -> list[tuple[int, str, int]]:
    calls: list[tuple[int, str, int]] = []
    cursor = address
    end = address + size
    while cursor + 2 <= end:
        halfword = struct.unpack_from("<H", image, cursor - base)[0]
        if cursor + 4 <= end and halfword & 0xF800 == 0xF000:
            second = struct.unpack_from("<H", image, cursor + 2 - base)[0]
            if second & 0xF800 == 0xF800:
                calls.append(
                    (
                        cursor,
                        "bl",
                        thumb_bl_target(image, base, cursor),
                    )
                )
                cursor += 4
                continue
            if second & 0xF800 == 0xE800:
                calls.append(
                    (
                        cursor,
                        "blx",
                        thumb_blx_target(image, base, cursor),
                    )
                )
                cursor += 4
                continue
        if halfword & 0xFF87 == 0x4780:
            calls.append((cursor, "blx_reg", (halfword >> 3) & 0xF))
        cursor += 2
    return calls


def elf_bytes_at(path: Path, address: int, size: int) -> bytes:
    image = path.read_bytes()
    require(image[:4] == b"\x7fELF", f"{path} is not ELF")
    require(image[4:6] == b"\x01\x01", f"{path} is not little-endian ELF32")
    section_offset = struct.unpack_from("<I", image, 0x20)[0]
    section_entry_size = struct.unpack_from("<H", image, 0x2E)[0]
    section_count = struct.unpack_from("<H", image, 0x30)[0]
    require(
        section_entry_size >= 40
        and section_offset + section_entry_size * section_count <= len(image),
        f"{path} section table is invalid",
    )
    for index in range(section_count):
        offset = section_offset + index * section_entry_size
        (
            _name,
            _type,
            _flags,
            section_address,
            file_offset,
            section_size,
        ) = struct.unpack_from("<6I", image, offset)
        if (
            section_address <= address
            and address + size <= section_address + section_size
        ):
            start = file_offset + address - section_address
            require(
                start + size <= len(image),
                f"{path} section payload is truncated",
            )
            return image[start:start + size]
    require(False, f"0x{address:08X}+0x{size:X} is absent from {path}")
    return b""


@dataclass(frozen=True)
class OverlayComponent:
    overlay_id: int
    ordinal: int
    ram_address: int
    ram_size: int
    bss_size: int
    static_init_start: int
    static_init_end: int
    file_id: int
    flags: int
    fat_start: int
    fat_end: int
    data: bytes


EXPECTED_OVERLAY_METADATA = {
    12: (
        0x022378C0,
        0x37380,
        0,
        0x0226EC08,
        0x0226EC10,
        12,
        0,
        0x1D3200,
        0x20A580,
    ),
    68: (
        0x021E5900,
        0x2800,
        0,
        0x021E80E4,
        0x021E80E8,
        68,
        0,
        0x2E4200,
        0x2E6A00,
    ),
    129: (
        0x023D8000,
        0x7FC0,
        0,
        0,
        0,
        129,
        0,
        0x3D5200,
        0x3DD1C0,
    ),
    153: (
        OVERLAY_BASE,
        0xFB4,
        0,
        0,
        0,
        153,
        0,
        0x41BE00,
        0x41CDB4,
    ),
}
OVERLAY129_THUNKS = {
    0x023DA86E: bytes.fromhex("18 47"),
    0x023DA874: bytes.fromhex("30 47"),
    0x023DCB1C: bytes.fromhex("18 47"),
    0x023DCB20: bytes.fromhex("28 47"),
}


def packaged_components_from_bytes(
    rom: bytes,
) -> tuple[int, bytes, dict[int, OverlayComponent]]:
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
    rows = [
        struct.unpack_from("<8I", rom, offset)
        for offset in range(
            overlay_offset,
            overlay_offset + overlay_size,
            32,
        )
    ]
    overlay_ids = [row[0] for row in rows]
    file_ids_list = [row[6] for row in rows]
    require(
        len(set(overlay_ids)) == len(overlay_ids),
        "packaged overlay table contains duplicate overlay IDs",
    )
    require(
        len(set(file_ids_list)) == len(file_ids_list),
        "packaged overlay table contains duplicate file IDs",
    )
    overlays: dict[int, OverlayComponent] = {}
    for ordinal, fields in enumerate(rows):
        (
            overlay_id,
            ram_address,
            ram_size,
            bss_size,
            static_init_start,
            static_init_end,
            file_id,
            flags,
        ) = fields
        require(
            overlay_id == ordinal,
            f"overlay ID {overlay_id} differs from ordinal {ordinal}",
        )
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
        component = OverlayComponent(
            overlay_id,
            ordinal,
            ram_address,
            ram_size,
            bss_size,
            static_init_start,
            static_init_end,
            file_id,
            flags,
            start,
            end,
            rom[start:end],
        )
        overlays[overlay_id] = component

    for overlay_id, expected in EXPECTED_OVERLAY_METADATA.items():
        require(
            overlay_id in overlays,
            f"packaged overlay {overlay_id} is absent",
        )
        component = overlays[overlay_id]
        actual = (
            component.ram_address,
            component.ram_size,
            component.bss_size,
            component.static_init_start,
            component.static_init_end,
            component.file_id,
            component.flags,
            component.fat_start,
            component.fat_end,
        )
        require(
            actual == expected,
            f"overlay {overlay_id} y9/FAT metadata differs",
        )
        require(
            component.ram_size == len(component.data),
            f"overlay {overlay_id} RAM size differs from uncompressed payload",
        )
    return arm9_base, rom[arm9_offset:arm9_offset + arm9_size], overlays


def packaged_components(
    rom_path: Path,
) -> tuple[int, bytes, dict[int, OverlayComponent]]:
    require(rom_path.is_file(), f"packaged ROM is absent: {rom_path}")
    return packaged_components_from_bytes(rom_path.read_bytes())


def bytes_at(image: bytes, base: int, address: int, size: int) -> bytes:
    offset = address - base
    require(
        offset >= 0 and offset + size <= len(image),
        f"0x{address:08X}..0x{address + size:08X} is outside its image",
    )
    return image[offset:offset + size]


def overlay129_predicate_matches(image: bytes, base: int) -> bool:
    address = 0x023D94C4
    if not (base <= address and address + 0x0E <= base + len(image)):
        return False
    try:
        target = thumb_bl_target(image, base, address + 4)
    except SystemExit:
        return False
    return (
        bytes_at(image, base, address, 0x0E)
        == bytes.fromhex("10 b5 09 21 ff f7 c0 ff 80 06 c0 0f 10 bd")
        and target == 0x023D944C
        and packaged_thumb_calls(image, base, address, 0x0E)
        == [(address + 4, "bl", 0x023D944C)]
    )


def overlay129_thunks_match(image: bytes, base: int) -> bool:
    return all(
        base <= address
        and address + len(expected) <= base + len(image)
        and image[address - base:address - base + len(expected)] == expected
        for address, expected in OVERLAY129_THUNKS.items()
    )


def packaged_metadata_mutation_fixtures(rom: bytes) -> None:
    y9_offset = struct.unpack_from("<I", rom, 0x50)[0]
    mutations: list[tuple[str, bytearray]] = []
    duplicate = bytearray(rom)
    struct.pack_into("<I", duplicate, y9_offset + 153 * 32, 152)
    mutations.append(("duplicate overlay ID", duplicate))
    wrong_size = bytearray(rom)
    struct.pack_into("<I", wrong_size, y9_offset + 153 * 32 + 8, 0xFB0)
    mutations.append(("overlay 153 RAM size", wrong_size))
    wrong_flags = bytearray(rom)
    struct.pack_into("<I", wrong_flags, y9_offset + 129 * 32 + 28, 1)
    mutations.append(("overlay 129 flags", wrong_flags))
    for label, mutation in mutations:
        try:
            packaged_components_from_bytes(bytes(mutation))
        except SystemExit:
            pass
        else:
            require(False, f"mutated {label} passes packaged metadata checks")


def binary_contracts(rom_path: Path, manifest_path: Path) -> None:
    linked = REPO / "build/pokemon_move_history_overlay_linked.o"
    overlay_path = REPO / "build/output_pokemon_move_history_overlay.bin"
    arm9_path = REPO / "base/arm9.bin"
    ov12_path = REPO / "base/overlay/overlay_0012.bin"
    ov68_path = REPO / "base/overlay/overlay_0068.bin"
    ov129_path = REPO / "base/overlay/overlay_0129.bin"
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
        ov129_path,
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
    try:
        verify_manifest(manifest_path, rom_path)
    except ManifestError as exc:
        require(False, f"content-addressed build manifest rejected: {exc}")

    overlay = overlay_path.read_bytes()
    require(
        len(overlay) <= OVERLAY_LIMIT,
        f"overlay 153 exceeds guarded 0x{OVERLAY_LIMIT:X}-byte envelope",
    )
    symbols = symbol_table(linked)
    linked_symbol_sizes = symbol_sizes(linked)
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

    rom_bytes = rom_path.read_bytes()
    arm9_base, packaged_arm9, packaged_overlays = (
        packaged_components_from_bytes(rom_bytes)
    )
    packaged_metadata_mutation_fixtures(rom_bytes)
    require(arm9_base == 0x02000000, "packaged ARM9 RAM base differs")
    ov12_component = packaged_overlays[12]
    ov68_component = packaged_overlays[68]
    ov129_component = packaged_overlays[129]
    ov153_component = packaged_overlays[153]
    ov12_base, packaged_ov12 = (
        ov12_component.ram_address,
        ov12_component.data,
    )
    ov68_base, packaged_ov68 = (
        ov68_component.ram_address,
        ov68_component.data,
    )
    ov129_base, packaged_ov129 = (
        ov129_component.ram_address,
        ov129_component.data,
    )
    ov153_base, packaged_ov153 = (
        ov153_component.ram_address,
        ov153_component.data,
    )
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
        packaged_ov129 == ov129_path.read_bytes(),
        "packaged overlay 129 differs from the current patched artifact",
    )
    require(
        packaged_ov153 == ov153_path.read_bytes() == overlay,
        "packaged overlay 153 differs from the current linked output",
    )

    expected = OVERLAY_BASE + 0x80
    require(
        bytes_at(packaged_arm9, arm9_base, 0x020769E2, 14)
        == bytes.fromhex("21 1c 22 1c 6c 31 6e 32 09 88 12 78 a0 6a")
        and thumb_bl_target(packaged_arm9, arm9_base, 0x020769F0)
        == expected
        and bytes_at(packaged_arm9, arm9_base, 0x020769F4, 2)
        == b"\x20\x1c",
        "evolution argument window, replacement BL, or continuation differs",
    )
    require(
        bytes_at(packaged_ov12, ov12_base, 0x02246336, 14)
        == bytes.fromhex("21 6c 62 6c 09 04 12 06 30 1c 09 0c 12 0e")
        and thumb_bl_target(packaged_ov12, ov12_base, 0x02246344)
        == expected
        and bytes_at(packaged_ov12, ov12_base, 0x02246348, 2)
        == b"\x61\x68",
        "battle argument window, replacement BL, or continuation differs",
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
        bytes_at(packaged_arm9, arm9_base, 0x0204DCBE, 12)
        == bytes.fromhex("e8 68 26 f0 20 fe 31 1c 26 f0 bd fc")
        and bytes_at(packaged_arm9, arm9_base, 0x0204DCCA, 6)
        == b"\x21\x1c\x70\xf3\xdc\xfb"
        and bytes_at(packaged_arm9, arm9_base, 0x0204DCD0, 4)
        == b"\x00\x20\x70\xbd",
        "Move Deleter argument window, replacement BL, or continuation differs",
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
        ov129_base <= implemented_check_target < ov129_base + len(packaged_ov129),
        "IsMoveUnimplemented is not resident in overlay 129",
    )
    implemented_address = implemented_check_target - 1
    require(
        implemented_address == 0x023D94C4
        and overlay129_predicate_matches(packaged_ov129, ov129_base),
        "overlay-129 IsMoveUnimplemented body/controlling data flow differs",
    )
    mutated_predicate = bytearray(packaged_ov129)
    mutated_predicate[implemented_address - ov129_base + 2] = 0
    require(
        not overlay129_predicate_matches(bytes(mutated_predicate), ov129_base),
        "always-false IsMoveUnimplemented mutation passes packaged checks",
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

    core_function_sizes = symbol_sizes(core_linked)
    packaged_function_specs = (
        (
            "PartyMenu_LearnMoveToSlot",
            core_linked,
            packaged_ov129,
            ov129_base,
            0x023DA154,
            0x6C,
            "fff8695ccb309e47286f0f4aeb8f67d1b1327c732a4b3896b3f91647e41f3357",
            [
                (0x023DA164, "bl", 0x023DA86E),
                (0x023DA180, "bl", 0x023DA874),
                (0x023DA188, "bl", 0x023DA86E),
                (0x023DA194, "bl", 0x023DA86E),
                (0x023DA19E, "bl", 0x023DA86E),
            ],
        ),
        (
            "MonTryLearnMoveOnLevelUp",
            core_linked,
            packaged_ov129,
            ov129_base,
            0x023DC704,
            0x158,
            "457614c6a8b8e13d158ca0dab84536a662443e233db5fd29570bf2df861d481c",
            [
                (0x023DC718, "bl", 0x023DCB1C),
                (0x023DC726, "bl", 0x023DCB20),
                (0x023DC732, "bl", 0x023DCB20),
                (0x023DC73E, "bl", 0x023DCB20),
                (0x023DC750, "bl", 0x023DCB1C),
                (0x023DC79E, "bl", 0x023DCB1C),
                (0x023DC7AC, "bl", 0x023DCB1C),
                (0x023DC7C4, "bl", 0x023DCB1C),
                (0x023DC806, "bl", 0x023DCB1C),
                (0x023DC81A, "bl", 0x023DCB1C),
                (0x023DC82A, "bl", 0x023DCB1C),
            ],
        ),
        (
            "PokemonMoveHistory_RecordMoveImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BEE0E,
            0x40,
            "ced2d2e052a86f717ab05b09c45715d1af3813af1f8393fdd10c913791f18571",
            [
                (0x023BEE1A, "bl", 0x023BE984),
                (0x023BEE2C, "bl", 0x023BED78),
                (0x023BEE38, "bl", 0x023BEC00),
                (0x023BEE46, "bl", 0x023BEB40),
            ],
        ),
        (
            "PokemonMoveHistory_ReplaceMoveImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BEE5A,
            0xE2,
            "e6e7567a8f66f2d7976ef3bfedab0a2f878c26bba5fd4d224fee58a2b461a7b9",
            [
                (0x023BEE7A, "bl", 0x023BE984),
                (0x023BEE90, "bl", 0x023BF2B4),
                (0x023BEEA2, "bl", 0x023BED78),
                (0x023BEEAC, "bl", 0x023BF2B4),
                (0x023BEEB4, "bl", 0x023BEC00),
                (0x023BEEC4, "bl", 0x023BF2B4),
                (0x023BEEDA, "bl", 0x023BF2B4),
                (0x023BEEE4, "bl", 0x023BF2B4),
                (0x023BEEF8, "bl", 0x023BF2B4),
                (0x023BEF04, "bl", 0x023BF2B4),
                (0x023BEF26, "bl", 0x023BEB40),
            ],
        ),
        (
            "PokemonMoveHistory_DeleteMoveSlotImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BEF3C,
            0x30,
            "c94dd14bb322c730304ef5b86976842f0e27a27a1e530d8339d67eaf5cf9daa0",
            [
                (0x023BEF4C, "bl", 0x023BF2B4),
                (0x023BEF52, "bl", 0x023BEDEC),
                (0x023BEF5C, "bl", 0x023BF2B4),
            ],
        ),
    )
    for (
        name,
        elf_path,
        image,
        image_base,
        address,
        size,
        expected_sha256,
        expected_calls,
    ) in packaged_function_specs:
        size_table = (
            core_function_sizes if elf_path == core_linked
            else linked_symbol_sizes
        )
        require(
            symbol_table(elf_path).get(name) == address
            and size_table.get(name) == size,
            f"{name} linked address/size differs",
        )
        packaged_body = bytes_at(image, image_base, address, size)
        require(
            packaged_body == elf_bytes_at(elf_path, address, size)
            and hashlib.sha256(packaged_body).hexdigest() == expected_sha256,
            f"{name} complete packaged body differs from authenticated ELF",
        )
        require(
            packaged_thumb_calls(image, image_base, address, size)
            == expected_calls,
            f"{name} packaged BL/BLX call allowlist differs",
        )

    party_body = bytes_at(packaged_ov129, ov129_base, 0x023DA154, 0x6C)
    require(
        overlay129_thunks_match(packaged_ov129, ov129_base),
        "overlay-129 interworking thunk bodies/registers differ",
    )
    mutated_thunk = bytearray(packaged_ov129)
    mutated_thunk[0x023DA86E - ov129_base] = 0x20
    require(
        not overlay129_thunks_match(bytes(mutated_thunk), ov129_base),
        "mutated overlay-129 thunk register passes exact authentication",
    )
    for target in (
        OVERLAY_BASE + 0x81,
        0x023D8987,
        0x020828ED,
        0x0206FE91,
        0x02097F0D,
    ):
        require(
            party_body.count(struct.pack("<I", target)) == 1,
            f"PartyMenu_LearnMoveToSlot target 0x{target:08X} differs",
        )
    level_body = bytes_at(packaged_ov129, ov129_base, 0x023DC704, 0x158)
    for target in (
        0x0201AA8D,
        0x0206E541,
        0x02071FC9,
        implemented_check_target,
        0x0201AB0D,
        0x0207137D,
        0x020272B1,
        OVERLAY_BASE + 0x29,
    ):
        require(
            level_body.count(struct.pack("<I", target)) == 1,
            f"MonTryLearnMoveOnLevelUp target 0x{target:08X} differs",
        )
    replace_start = symbols["PokemonMoveHistory_ReplaceMoveImpl"] - ov153_base
    delete_start = symbols["PokemonMoveHistory_DeleteMoveSlotImpl"] - ov153_base
    delete_end = symbols["PokemonMoveHistory_CommitIfDirtyImpl"] - ov153_base
    replace_bytes = packaged_ov153[replace_start:delete_start]
    delete_bytes = packaged_ov153[delete_start:delete_end]
    replace_address = symbols["PokemonMoveHistory_ReplaceMoveImpl"]
    replace_size = linked_symbol_sizes.get(
        "PokemonMoveHistory_ReplaceMoveImpl",
        0,
    )
    require(
        replace_size == 0xE2 and len(replace_bytes) == replace_size,
        "ReplaceMove packaged body size/layout differs from authenticated build",
    )
    false_address = replace_address + 0x12
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            false_address,
            8,
        )
        == bytes.fromhex("00 24 20 00 0d b0 f0 bd"),
        "ReplaceMove FALSE return block differs",
    )
    same_slot_start = replace_address + 0x28
    literal_address, literal_value = thumb_literal_load(
        packaged_ov153,
        ov153_base,
        replace_address + 0x2A,
        3,
    )
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            same_slot_start,
            2,
        )
        == bytes.fromhex("3e 00")
        and replace_address <= literal_address < replace_address + replace_size
        and literal_value == resolved_targets["GetBoxMonData"]
        and bytes_at(
            packaged_ov153,
            ov153_base,
            replace_address + 0x2C,
            10,
        )
        == bytes.fromhex("36 36 00 22 31 00 20 00 04 93"),
        "ReplaceMove early same-slot read setup differs",
    )
    same_slot_call = replace_address + 0x36
    same_slot_trampoline = thumb_bl_target(
        packaged_ov153,
        ov153_base,
        same_slot_call,
    )
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            same_slot_trampoline,
            2,
        )
        == bytes.fromhex("18 47")
        and bytes_at(
            packaged_ov153,
            ov153_base,
            replace_address + 0x3A,
            8,
        )
        == bytes.fromhex("2b 88 00 04 00 0c 83 42"),
        "ReplaceMove early same-slot call/compare differs",
    )
    equal_branch = replace_address + 0x42
    capture_call = replace_address + 0x48
    require(
        thumb_conditional_branch(
            packaged_ov153,
            ov153_base,
            equal_branch,
            0,
        )
        == false_address
        and bytes_at(
            packaged_ov153,
            ov153_base,
            replace_address + 0x44,
            4,
        )
        == bytes.fromhex("20 00 07 a9")
        and thumb_bl_target(
            packaged_ov153,
            ov153_base,
            capture_call,
        )
        == symbols["PokemonMoveHistory_CaptureSnapshotImpl"],
        "ReplaceMove equality edge does not return FALSE before snapshot access",
    )
    save_literal_address, save_literal_value = thumb_literal_load(
        packaged_ov153,
        ov153_base,
        replace_address + 0x50,
        3,
    )
    require(
        replace_address <= save_literal_address < replace_address + replace_size
        and save_literal_value == resolved_targets["SaveBlock2_get"]
        and thumb_bl_target(
            packaged_ov153,
            ov153_base,
            replace_address + 0x52,
        )
        == same_slot_trampoline
        and replace_address + 0x52 > capture_call,
        "ReplaceMove SaveBlock2_get call is not authenticated after snapshot",
    )
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
    recordable_address = symbols["PokemonMoveHistory_IsRecordableMove"]
    recordable_start = recordable_address - ov153_base
    recordable_size = linked_symbol_sizes.get(
        "PokemonMoveHistory_IsRecordableMove",
        0,
    )
    recordable_bytes = packaged_ov153[
        recordable_start:recordable_start + recordable_size
    ]
    require(
        recordable_size == 0x28
        and struct.pack("<I", implemented_check_target) in recordable_bytes,
        "recordable-move predicate does not resolve resident "
        "IsMoveUnimplemented",
    )
    range_literal_address, range_literal_value = thumb_literal_load(
        packaged_ov153,
        ov153_base,
        recordable_address + 0x02,
        1,
    )
    implemented_literal_address, implemented_literal_value = (
        thumb_literal_load(
            packaged_ov153,
            ov153_base,
            recordable_address + 0x12,
            3,
        )
    )
    recordable_false = recordable_address + 0x1E
    recordable_call = recordable_address + 0x16
    recordable_trampoline = thumb_bl_target(
        packaged_ov153,
        ov153_base,
        recordable_call,
    )
    _canonical_moves, _custom_moves, num_moves = move_limits()
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            recordable_address,
            16,
        )
        == bytes.fromhex(
            "43 1e 07 49 1b 04 02 00 10 b5 00 20 1b 0c 8b 42"
        )
        and range_literal_address == recordable_address + 0x20
        and range_literal_value == num_moves - 2
        and thumb_conditional_branch(
            packaged_ov153,
            ov153_base,
            recordable_address + 0x10,
            8,
        )
        == recordable_false,
        "recordable-move MOVE_NONE/range CFG does not return FALSE before "
        "the implementation check",
    )
    require(
        implemented_literal_address == recordable_address + 0x24
        and implemented_literal_value == implemented_check_target
        and bytes_at(
            packaged_ov153,
            ov153_base,
            recordable_address + 0x14,
            2,
        )
        == bytes.fromhex("10 00")
        and bytes_at(
            packaged_ov153,
            ov153_base,
            recordable_trampoline,
            2,
        )
        == bytes.fromhex("18 47")
        and bytes_at(
            packaged_ov153,
            ov153_base,
            recordable_address + 0x1A,
            6,
        )
        == bytes.fromhex("43 42 58 41 10 bd"),
        "IsMoveUnimplemented result does not control the final predicate "
        "return through the authenticated interworking call",
    )

    append_address = next(
        (
            address
            for name, address in symbols.items()
            if name == "PokemonMoveHistory_AppendMove"
            or name.startswith("PokemonMoveHistory_AppendMove.")
        ),
        None,
    )
    require(
        append_address is not None,
        "linked move-history append implementation is missing",
    )
    append_size = next(
        (
            size
            for name, size in linked_symbol_sizes.items()
            if name == "PokemonMoveHistory_AppendMove"
            or name.startswith("PokemonMoveHistory_AppendMove.")
        ),
        0,
    )
    require(
        append_size == 0xC0
        and bytes_at(
            packaged_ov153,
            ov153_base,
            append_address,
            14,
        )
        == bytes.fromhex(
            "f0 b5 06 00 85 b0 18 00 14 00 1f 00 00 91"
        )
        and thumb_bl_target(
            packaged_ov153,
            ov153_base,
            append_address + 0x0E,
        )
        == recordable_address
        and bytes_at(
            packaged_ov153,
            ov153_base,
            append_address + 0x12,
            2,
        )
        == bytes.fromhex("00 28")
        and thumb_conditional_branch(
            packaged_ov153,
            ov153_base,
            append_address + 0x14,
            0,
        )
        == append_address + 0x80,
        "AppendMove does not consume its sole predicate result before "
        "record access or mutation",
    )
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            append_address + 0x16,
            6,
        )
        == bytes.fromhex("00 23 a1 7b 8b 42")
        and thumb_conditional_branch(
            packaged_ov153,
            ov153_base,
            append_address + 0x1C,
            3,
        )
        == append_address + 0x84
        and thumb_conditional_branch(
            packaged_ov153,
            ov153_base,
            append_address + 0x20,
            1,
        )
        == append_address + 0x54
        and thumb_conditional_branch(
            packaged_ov153,
            ov153_base,
            append_address + 0x8E,
            0,
        )
        == append_address + 0x80
        and bytes_at(
            packaged_ov153,
            ov153_base,
            append_address + 0x80,
            4,
        )
        == bytes.fromhex("05 b0 f0 bd"),
        "AppendMove invalid/duplicate CFG can reach mutation",
    )
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            append_address + 0x1E,
            0x32,
        )
        == bytes.fromhex(
            "18 29 18 d1 00 25 23 00 6a 00 10 33 99 5a 00 9b "
            "00 9a 0a 33 12 32 18 88 88 42 37 d0 02 33 93 42 "
            "f9 d1 68 00 20 18 a3 7b 82 1c 01 35 01 92 9d 42 "
            "21 d3"
        )
        and bytes_at(
            packaged_ov153,
            ov153_base,
            append_address + 0x84,
            0x30,
        )
        == bytes.fromhex(
            "22 00 58 00 10 32 12 5a ba 42 f7 d0 01 33 c2 e7 "
            "01 9b 02 aa 1b 8a 91 1d 10 30 02 22 0b 80 00 f0 "
            "af fb 01 98 cc e7 01 35 18 2d b9 d1 00 25 c5 e7"
        ),
        "AppendMove duplicate/capacity/eviction CFG window differs",
    )
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            append_address + 0x50,
            0x30,
        )
        == bytes.fromhex(
            "01 3b a3 73 17 4b f2 58 a3 7b 59 1c 08 33 5b 00 "
            "a1 73 1f 53 00 9b 1b 89 a3 81 53 69 01 33 53 61 "
            "01 22 a3 60 10 4b f2 54 10 4a b3 58 01 33 b3 50"
        )
        and struct.unpack_from(
            "<III",
            packaged_ov153,
            append_address + 0xB4 - ov153_base,
        )
        == (0x0002F30C, 0x0002F310, 0x0002F314),
        "AppendMove history/store/dirty/revision mutation window differs",
    )

    disassembly = subprocess.check_output(
        ["arm-none-eabi-objdump", "-d", str(linked)],
        text=True,
    )
    linked_calls = [
        call
        for call in direct_thumb_calls(disassembly)
        if ov153_base <= call[0] < ov153_base + len(packaged_ov153)
    ]
    replace_calls = [
        call
        for call in linked_calls
        if replace_address <= call[0] < replace_address + replace_size
    ]
    recordable_calls = [
        call
        for call in linked_calls
        if recordable_address <= call[0] < recordable_address + recordable_size
    ]
    require(
        recordable_calls
        == [(recordable_call, "bl", recordable_trampoline)],
        "recordable-move predicate has extra/missing external calls",
    )
    append_calls = [
        call
        for call in linked_calls
        if append_address <= call[0] < append_address + append_size
    ]
    require(
        append_calls
        == [
            (append_address + 0x0E, "bl", recordable_address),
            (
                append_address + 0xA2,
                "bl",
                symbols["PokemonMoveHistory_OverlayMemcpy"],
            ),
        ],
        "AppendMove call graph differs or predicate is not uniquely first",
    )
    require(
        [
            address
            for address, mnemonic, target in replace_calls
            if mnemonic == "bl"
            and target == symbols["PokemonMoveHistory_CaptureSnapshotImpl"]
        ]
        == [capture_call],
        "ReplaceMove does not have exactly one authenticated snapshot call",
    )
    require(
        [
            (address, mnemonic, target)
            for address, mnemonic, target in replace_calls
            if address < equal_branch
        ]
        == [
            (
                replace_address + 0x20,
                "bl",
                symbols["PokemonMoveHistory_IsRecordableMove"],
            ),
            (same_slot_call, "bl", same_slot_trampoline),
        ],
        "ReplaceMove equality path gained an unauthenticated call",
    )
    for later_label, later_address in (
        (
            "PokemonMoveHistory_ObserveSnapshot",
            symbols["PokemonMoveHistory_ObserveSnapshot"],
        ),
        ("PokemonMoveHistory_AppendMove", append_address),
    ):
        require(
            [
                address
                for address, mnemonic, target in replace_calls
                if mnemonic == "bl" and target == later_address
            ]
            and all(
                address > capture_call
                for address, mnemonic, target in replace_calls
                if mnemonic == "bl" and target == later_address
            )
            and len(
                [
                    address
                    for address, mnemonic, target in replace_calls
                    if mnemonic == "bl" and target == later_address
                ]
            )
            == 1,
            f"ReplaceMove {later_label} call is not uniquely after snapshot",
        )
    for call_address, mnemonic, disassembly_target in linked_calls:
        packaged_target = (
            thumb_bl_target(packaged_ov153, ov153_base, call_address)
            if mnemonic == "bl"
            else thumb_blx_target(packaged_ov153, ov153_base, call_address)
        )
        require(
            packaged_target == disassembly_target,
            f"packaged {mnemonic} at 0x{call_address:08X} targets "
            f"0x{packaged_target:08X}, linked object says "
            f"0x{disassembly_target:08X}",
        )

    helper_specs = (
        ("PokemonMoveHistory_OverlayMemcpy", 3, 0x020E5AD8),
        ("PokemonMoveHistory_OverlayMemset", 1, 0x020E5B44),
    )
    helper_addresses: dict[str, int] = {}
    for helper, expected_count, retail_target in helper_specs:
        require(helper in symbols, f"local bridge symbol {helper} is absent")
        helper_address = symbols[helper]
        helper_addresses[helper] = helper_address
        require(
            OVERLAY_BASE <= helper_address < OVERLAY_BASE + len(packaged_ov153),
            f"local bridge {helper} is outside overlay 153",
        )
        calls = [
            call_address
            for call_address, mnemonic, target in linked_calls
            if mnemonic == "bl" and target == helper_address
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
        expected_body = (
            b"\x00\xb5"
            + encode_thumb_blx(helper_address + 2, retail_target)
            + b"\x00\xbd"
        )
        require(
            linked_symbol_sizes.get(helper) == 8
            and bytes_at(
                packaged_ov153,
                ov153_base,
                helper_address,
                8,
            )
            == expected_body
            and thumb_blx_target(
                packaged_ov153,
                ov153_base,
                helper_address + 2,
            )
            == retail_target,
            f"{helper} is not the exact 8-byte local interworking bridge",
        )

    raw_retail_targets = {0x020E5AD8, 0x020E5B44}
    expected_raw_calls = {
        (
            helper_addresses["PokemonMoveHistory_OverlayMemcpy"] + 2,
            0x020E5AD8,
        ),
        (
            helper_addresses["PokemonMoveHistory_OverlayMemset"] + 2,
            0x020E5B44,
        ),
    }
    observed_raw_calls = {
        (call_address, target)
        for call_address, _mnemonic, target in linked_calls
        if target in raw_retail_targets
    }
    require(
        observed_raw_calls == expected_raw_calls,
        "raw retail copy/clear calls differ from the two local bridge bodies",
    )
    for old_bridge in (0x023DEE42, 0x023DEE5E):
        require(
            all(target != old_bridge for _address, _mnemonic, target in linked_calls),
            f"overlay 153 still calls overlay-129 bridge 0x{old_bridge:08X}",
        )

    relocation_text = "\n".join(
        subprocess.check_output(
            ["arm-none-eabi-objdump", "-r", str(object_path)],
            text=True,
        )
        for object_path in (
            history_object,
            relearn_object,
            REPO / "build/pokemon_move_history_overlay/entry.o",
            REPO / "build/pokemon_move_history_overlay/thumb_help.o",
        )
    )
    relocation_names = re.findall(
        r"R_ARM_(?:ABS32|THM_CALL)\s+([A-Za-z0-9_.$]+)",
        relocation_text,
    )
    require(
        relocation_names.count("PokemonMoveHistory_OverlayMemcpy") == 3
        and relocation_names.count("PokemonMoveHistory_OverlayMemset") == 1
        and relocation_names.count("MIi_CpuClearFast") == 3,
        "overlay copy/clear relocation multiset differs",
    )
    require(
        not [
            name
            for name in relocation_names
            if re.search(
                r"(?:memcpy|memset|memmove|bcopy|bzero)",
                name,
                re.IGNORECASE,
            )
            and name
            not in {
                "PokemonMoveHistory_OverlayMemcpy",
                "PokemonMoveHistory_OverlayMemset",
            }
        ],
        "overlay contains an unapproved raw copy/clear relocation",
    )
    cpu_copy_clear_relocations = [
        name
        for name in relocation_names
        if re.fullmatch(r"MIi?_Cpu(?:Copy|Clear|Fill)[A-Za-z0-9_]*", name)
    ]
    require(
        cpu_copy_clear_relocations == ["MIi_CpuClearFast"] * 3,
        "overlay gained an unapproved raw CPU copy/clear/fill relocation",
    )
    require(
        packaged_ov153.count(struct.pack("<I", 0x020D4858)) == 3,
        "packaged overlay does not resolve exactly three MIi_CpuClearFast "
        "literals",
    )
    for forbidden_literal in (
        0x020E5AD8,
        0x020E5B44,
        0x023DEE42,
        0x023DEE43,
        0x023DEE5E,
        0x023DEE5F,
    ):
        require(
            struct.pack("<I", forbidden_literal) not in packaged_ov153,
            f"packaged overlay contains forbidden raw copy/clear literal "
            f"0x{forbidden_literal:08X}",
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
        "--manifest",
        type=Path,
        help="content-addressed build manifest; required with --rom",
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
    require(
        args.source_only == (args.manifest is None),
        "--manifest is required exactly when --rom is used",
    )
    source_contracts()
    host_fixtures()
    if args.source_only:
        print("move-history capture: source and host fixtures verified")
    else:
        binary_contracts(args.rom, args.manifest)


if __name__ == "__main__":
    main()
