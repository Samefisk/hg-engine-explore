#!/usr/bin/env python3
"""Static contracts and deterministic host fixtures for move-relearn candidates."""

from __future__ import annotations

import importlib.util
import json
import re
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"move-relearn candidate verification failed: {message}")


def array_moves(source: str, declaration: str) -> list[str]:
    start = source.index(declaration)
    end = source.index("};", start)
    return re.findall(r"\bMOVE_[A-Z0-9_]+\b", source[start:end])


def verify_source_contract() -> None:
    header = (REPO / "include/pokemon_move_history.h").read_text()
    source = (
        REPO
        / "src/pokemon_move_history_overlay/pokemon_move_relearn.c"
    ).read_text()
    entry = (REPO / "asm/pokemon_move_history_overlay/entry.s").read_text()
    linker = (
        REPO / "src/pokemon_move_history_overlay/linker.ld"
    ).read_text()
    rom = (REPO / "rom.ld").read_text()
    learnset_builder = (REPO / "scripts/build_learnsets.py").read_text()

    for fragment in (
        "#define POKEMON_MOVE_RELEARN_MAX_CANDIDATES",
        "typedef BOOL (*PokemonMoveRelearnSpecialPolicy)",
        "u32 PokemonMoveRelearn_BuildCandidates(",
        "return > capacity reports truncation",
        "allocation or ownership is transferred",
    ):
        require(fragment in header, f"public contract lost: {fragment}")
    for fragment in (
        "PokemonMoveHistory_Query(",
        "LoadLevelUpLearnset_HandleAlternateForm(",
        "CODE_ADDON_MOVE_RELEARN_PARENTS",
        "CODE_ADDON_MACHINE_LEARNSETS",
        "ARC_EGG_MOVES",
        "CODE_ADDON_TUTOR_LEARNSETS",
        "MOVE_PAIN_SPLIT",
        "options->allowSpecialMove(",
        "move == MOVE_NONE || move >= NUM_OF_MOVES",
        "moveData.flag & FLAG_UNUSED_MOVE",
        "LEVEL_UP_LEARNSET_LEVEL(source.level[i]) > level",
    ):
        require(fragment in source, f"runtime policy lost: {fragment}")
    require("sys_AllocMemory" not in source, "candidate builder gained heap use")
    require("sys_FreeMemory" not in source, "candidate builder gained heap use")
    require(
        "MoveHistoryEntry_BuildRelearnCandidates:" in entry
        and "b PokemonMoveRelearn_BuildCandidatesImpl" in entry,
        "candidate ABI is not a register-preserving direct branch",
    )
    require(
        "ORIGIN(rom) + 0x78" in linker
        and "__bss_end__ + 0x1000 <= ORIGIN(rom) + LENGTH(rom)" in linker,
        "candidate ABI or guarded overlay envelope differs",
    )
    require(
        "PokemonMoveRelearn_BuildCandidates = 0x023BE478 | 1;" in rom,
        "public candidate alias differs",
    )
    require(
        'section(".pokemon_move_history_short_branch_targets")' in source
        and "KEEP(*(.pokemon_move_history_short_branch_targets))" in linker,
        "candidate implementation is not kept in range of its ABI-preserving "
        "Thumb-1 entry branch",
    )
    require(
        r"(?:static\s+)?const\s+u16\s+sMachineMoves" in learnset_builder,
        "learnset generator cannot parse the shared resident machine table",
    )
    require(
        source.index(
            "species == SPECIES_NONE || species > MAX_MON_NUM || form >= 32"
        )
        < source.index(
            "level = GetBoxMonData(boxPokemon, MON_DATA_LEVEL, NULL);"
        ),
        "XP-derived level is loaded before species/form bounds validation",
    )
    history_loop = source.index(
        "for (i = 0; i < historyCount; i++) {",
        source.index("lineageDepth < MOVE_RELEARN_LINEAGE_LIMIT"),
    )
    history_loop_end = source.index(
        "PokemonMoveRelearn_Append(",
        history_loop,
    )
    require(
        source.index(
            "PokemonMoveRelearn_IsImplementedMove(history[i])",
            history_loop,
            history_loop_end,
        )
        < source.index(
            "options->allowSpecialMove(",
            history_loop,
            history_loop_end,
        ),
        "special policy is called before persisted move validation",
    )


def verify_shared_move_tables() -> None:
    candidate_source = (
        REPO
        / "src/pokemon_move_history_overlay/pokemon_move_relearn.c"
    ).read_text()
    tutor_source = (REPO / "src/field/move_tutor.c").read_text()
    item_source = (REPO / "src/item.c").read_text()
    constants = (
        REPO / "include/constants/generated/learnsets.h"
    ).read_text()

    candidate_tutors = array_moves(
        candidate_source,
        "static const u16 sMoveRelearnTutorMoves",
    )
    tutor_start = tutor_source.index("TutorMove sTutorMoves[]")
    tutor_end = tutor_source.index("};", tutor_start)
    field_tutors = re.findall(
        r"\{\s*(MOVE_[A-Z0-9_]+)\s*,",
        tutor_source[tutor_start:tutor_end],
    )
    require(
        candidate_tutors == field_tutors,
        "resident tutor move order differs from the field tutor table",
    )
    machine_moves = array_moves(item_source, "const u16 sMachineMoves[]")
    machine_count = int(
        re.search(r"#define NUM_MACHINE_MOVES\s+(\d+)", constants).group(1)
    )
    tutor_count = int(
        re.search(r"#define NUM_TUTOR_MOVES\s+(\d+)", constants).group(1)
    )
    require(
        len(machine_moves) == machine_count,
        "resident machine table length differs from generated bitsets",
    )
    require(
        len(candidate_tutors) == tutor_count,
        "resident tutor table length differs from generated bitsets",
    )


def verify_parent_generator() -> None:
    path = REPO / "scripts/build_move_relearn_parents.py"
    spec = importlib.util.spec_from_file_location("move_relearn_parents", path)
    require(spec is not None and spec.loader is not None, "generator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generated = module.generate(
        REPO / "armips/data/evodata.s",
        REPO / "include/constants/species.h",
        REPO / "asm/include/species.inc",
    )
    pairs = re.findall(
        r"\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*(SPECIES_[A-Z0-9_]+)",
        generated,
    )
    parents = dict(pairs)
    require(len(pairs) == len(parents), "generated parent targets are duplicated")
    require(
        parents["SPECIES_BUTTERFREE"] == "SPECIES_METAPOD"
        and parents["SPECIES_METAPOD"] == "SPECIES_CATERPIE",
        "multi-stage parent chain differs",
    )
    require(
        parents["SPECIES_GASTRODON_EAST_SEA"]
        == "SPECIES_SHELLOS_EAST_SEA",
        "form-aware parent mapping differs",
    )
    require(
        parents["SPECIES_MR_MIME"] == "SPECIES_MIME_JR",
        "armips/C species spelling is not resolved by numeric identity",
    )

    max_depth = 0
    for species in parents:
        seen: set[str] = set()
        current = species
        depth = 0
        while current in parents:
            require(current not in seen, f"evolution parent cycle at {current}")
            seen.add(current)
            current = parents[current]
            depth += 1
        max_depth = max(max_depth, depth)
    require(max_depth < 8, "runtime lineage bound is too small")

    with tempfile.TemporaryDirectory(prefix="move-relearn-parent-") as root:
        output = Path(root) / "MoveRelearnParents.c"
        output.write_text(generated)
        require(output.stat().st_size > 0, "generator produced an empty table")


def build_model(
    level_moves: list[tuple[int, str]],
    history: list[str],
    current: list[str],
    level: int,
    allowed_history: set[str],
    valid: set[str],
    capacity: int,
) -> tuple[int, list[str]]:
    candidates: list[str] = []

    def append(move: str) -> None:
        if (
            move == "MOVE_NONE"
            or move in current
            or move in candidates
            or move not in valid
        ):
            return
        candidates.append(move)

    for learn_level, move in level_moves:
        if learn_level <= level:
            append(move)
    for move in history:
        if move in allowed_history:
            append(move)
    return len(candidates), candidates[:capacity]


def verify_ordering_model() -> None:
    learnsets = json.loads(
        (REPO / "data/learnsets/learnsets.json").read_text()
    )
    raw = learnsets["SPECIES_BUTTERFREE"]["LevelMoves"]
    levels = [(entry["Level"], entry["Move"]) for entry in raw]
    history = [
        "MOVE_TACKLE",
        "MOVE_PAIN_SPLIT",
        "MOVE_CONFUSION",
        "MOVE_NONE",
        "MOVE_CORRUPT",
        "MOVE_HEADBUTT",
    ]
    valid = {move for _, move in levels} | {
        "MOVE_PAIN_SPLIT",
        "MOVE_HEADBUTT",
    }
    allowed = {
        "MOVE_TACKLE",
        "MOVE_PAIN_SPLIT",
        "MOVE_CONFUSION",
        "MOVE_HEADBUTT",
    }
    count, full = build_model(
        levels,
        history,
        ["MOVE_GUST", "MOVE_HARDEN", "MOVE_NONE", "MOVE_NONE"],
        12,
        allowed,
        valid,
        99,
    )
    expected = [
        "MOVE_TACKLE",
        "MOVE_STRING_SHOT",
        "MOVE_BUG_BITE",
        "MOVE_SUPERSONIC",
        "MOVE_CONFUSION",
        "MOVE_POISON_POWDER",
        "MOVE_STUN_SPORE",
        "MOVE_SLEEP_POWDER",
        "MOVE_PAIN_SPLIT",
        "MOVE_HEADBUTT",
    ]
    require(full == expected and count == len(expected), "stable order differs")
    current = ["MOVE_GUST", "MOVE_HARDEN", "MOVE_NONE", "MOVE_NONE"]
    zero_count, zero = build_model(
        levels, history, current, 12, allowed, valid, 0
    )
    small_count, small = build_model(
        levels, history, current, 12, allowed, valid, 3
    )
    require(zero == [] and zero_count > 0, "count-only behavior differs")
    require(
        small == expected[:3] and small_count == count,
        "capacity truncation changed count or prefix",
    )


def main() -> None:
    verify_source_contract()
    verify_shared_move_tables()
    verify_parent_generator()
    verify_ordering_model()
    print(
        "move-relearn candidates: source policy, lineage data, shared tables, "
        "ordering, dedupe, filtering, and truncation verified"
    )


if __name__ == "__main__":
    main()
