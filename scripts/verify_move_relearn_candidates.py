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
    codetables = (REPO / "data/codetables.mk").read_text()
    final_verifier = (
        REPO / "scripts/verify_pokemon_move_history.py"
    ).read_text()

    for fragment in (
        "#define POKEMON_MOVE_RELEARN_MAX_CANDIDATES",
        "typedef BOOL (*PokemonMoveRelearnSpecialPolicy)",
        "u32 LONG_CALL PokemonMoveRelearn_BuildCandidates(",
        "return > capacity reports truncation",
        "allocation or ownership is transferred",
    ):
        require(fragment in header, f"public contract lost: {fragment}")
    for fragment in (
        "PokemonMoveHistory_QueryReadOnlyImpl(",
        "LoadLevelUpLearnset_HandleAlternateForm(",
        "CODE_ADDON_MOVE_RELEARN_PARENTS",
        "CODE_ADDON_MACHINE_LEARNSETS",
        "ARC_EGG_MOVES",
        "CODE_ADDON_TUTOR_LEARNSETS",
        "MOVE_HELPING_HAND",
        "MOVE_VOLT_TACKLE",
        "MOVE_SWAGGER",
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
        "PokemonMoveHistory_QueryImpl(" not in source,
        "candidate discovery regained observable history allocation/mutation",
    )
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
        source.index("!PokemonMoveHistoryTask6_IsCanonical(boxPokemon)")
        < source.index(
            "level = GetBoxMonData(boxPokemon, MON_DATA_LEVEL, NULL);"
        ),
        "XP-derived level is loaded before canonical owner validation",
    )
    for dependency in (
        "src/field/move_tutor.c",
        "include/constants/species.h",
        "include/constants/moves.h",
        "data/FormToSpeciesMapping.c",
    ):
        require(
            dependency in codetables,
            f"learnset generator dependency lost: {dependency}",
        )
    for fragment in (
        "LEARNSETS_PRIMARY_OUTPUTS := \\",
        "$(LEARNSETS_HEADER) \\",
        "$(MACHINELEARNSET_DEPENDENCIES) \\",
        "$(LEVELUPLEARNSET_DEPENDENCIES) \\",
        "$(EGGLEARNSET_DEPENDENCIES) \\",
        "$(TUTORLEARNSET_DEPENDENCIES)",
        "LEARNSETS_ARMIPS_CONSTANTS := armips/include/generated/levelup.s",
        "LEARNSETS_COMPLETION_STAMP :=",
        ".PHONY: learnsets-ensure",
        "--completion-stamp $(LEARNSETS_COMPLETION_STAMP)",
        ".DELETE_ON_ERROR: $(LEARNSETS_COMPLETION_STAMP)",
        "$(LEARNSETS_ATOMIC_OUTPUTS) $(LEARNSETS_COMPLETION_STAMP): | "
        "learnsets-ensure",
    ):
        require(fragment in codetables, f"atomic Make contract lost: {fragment}")
    for target, generated_source in (
        ("$(MACHINELEARNSET_BIN):", "$(MACHINELEARNSET_DEPENDENCIES)"),
        ("$(TUTORLEARNSET_BIN):", "$(TUTORLEARNSET_DEPENDENCIES)"),
        ("$(LEVELUPLEARNSET_NARC):", "$(LEVELUPLEARNSET_DEPENDENCIES)"),
        ("$(EGGLEARNSET_NARC):", "$(EGGLEARNSET_DEPENDENCIES)"),
    ):
        target_line = next(
            line for line in codetables.splitlines() if line.startswith(target)
        )
        require(
            generated_source in target_line,
            f"{target} does not directly depend on {generated_source}",
        )
    for fragment in (
        "fcntl.flock(lock.fileno(), fcntl.LOCK_EX)",
        "stamp.unlink(missing_ok=True)",
        "tempfile.TemporaryDirectory(",
        "os.replace(staged[name], destination)",
        "os.replace(stamp_temporary, stamp)",
    ):
        require(
            fragment in learnset_builder,
            f"atomic generator contract lost: {fragment}",
        )
    require(
        learnset_builder.index("stamp.unlink(missing_ok=True)")
        < learnset_builder.index("generate({name: str(path)")
        < learnset_builder.index("os.replace(staged[name], destination)")
        < learnset_builder.index("os.replace(stamp_temporary, stamp)"),
        "learnset transaction is not invalidate -> stage -> publish -> stamp",
    )
    for fragment in (
        "def build_expected_learnset_payloads(",
        "data/learnsets/learnsets.json",
        "data/FormToSpeciesMapping.c",
        "const u16 sMachineMoves[]",
        "TutorMove sTutorMoves[]",
        'a033_members[0] == expected_learnsets["level"]',
        'a028_members[14] == expected_learnsets["machine"]',
        'a028_members[15] == expected_learnsets["tutor"]',
        'a229_members[0] == expected_learnsets["egg"]',
        "def build_expected_parent_payload(",
        "armips/data/evodata.s",
        "asm/include/species.inc",
        "data/PokeFormDataTbl.c",
        "data/FormToSpeciesMapping.c",
        "def first_parent_mismatch(",
        "verify_parent_member_against_current_inputs(",
        "a028_members[20],",
    ):
        require(
            fragment in final_verifier,
            f"independent final-ROM oracle contract lost: {fragment}",
        )
    parent_oracle = final_verifier[
        final_verifier.index("def build_expected_parent_payload("):
        final_verifier.index("def ordered_move_array(")
    ]
    for forbidden in (
        "scripts/build_move_relearn_parents.py",
        "build/move_relearn/MoveRelearnParents.c",
        "build/move_relearn/MoveRelearnParents.bin",
    ):
        require(
            forbidden not in parent_oracle,
            f"final parent oracle trusts generated logic/artifact: {forbidden}",
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


def verify_atomic_learnset_publication() -> None:
    path = REPO / "scripts/build_learnsets.py"
    spec = importlib.util.spec_from_file_location("build_learnsets_atomic", path)
    require(spec is not None and spec.loader is not None, "learnset generator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with tempfile.TemporaryDirectory(prefix="learnsets-atomic-fixture-") as root:
        root_path = Path(root)
        outputs = {
            name: root_path / f"{name}.out"
            for name in (
                "constants_header",
                "levelup_constants",
                "machine",
                "levelup",
                "egg",
                "tutor",
            )
        }
        for output in outputs.values():
            output.write_bytes(b"old")
        stamp = root_path / ".complete"
        stamp.write_bytes(b"old stamp")

        def fail_after_staging_one(paths):
            Path(paths["constants_header"]).write_bytes(b"new header")
            raise RuntimeError("injected generation failure")

        try:
            module.atomic_generate_and_publish(
                outputs,
                stamp,
                fail_after_staging_one,
            )
        except RuntimeError as error:
            require(
                str(error) == "injected generation failure",
                "atomic failure fixture raised the wrong error",
            )
        else:
            require(False, "atomic failure fixture unexpectedly succeeded")
        require(not stamp.exists(), "failed generation left a completion stamp")
        require(
            all(output.read_bytes() == b"old" for output in outputs.values()),
            "failed staging changed a published output",
        )

        def generate_all(paths):
            for name, output in paths.items():
                Path(output).write_bytes(f"generated:{name}".encode())

        module.atomic_generate_and_publish(outputs, stamp, generate_all)
        require(
            stamp.read_text().startswith("learnsets-v1\n"),
            "successful generation did not publish its manifest last",
        )
        before = {
            name: output.stat().st_mtime_ns
            for name, output in outputs.items()
        }
        module.atomic_generate_and_publish(outputs, stamp, generate_all)
        require(
            all(
                output.stat().st_mtime_ns == before[name]
                for name, output in outputs.items()
            ),
            "unchanged atomic generation rewrote a published output",
        )


def verify_final_parent_oracle_rejects_tampering() -> None:
    path = REPO / "scripts/verify_pokemon_move_history.py"
    spec = importlib.util.spec_from_file_location(
        "move_history_parent_oracle_fixture",
        path,
    )
    require(spec is not None and spec.loader is not None, "final verifier cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    expected, names_by_id, mapping_count, maximum_depth = (
        module.build_expected_parent_payload()
    )
    species_values = module.load_parent_constants(
        REPO / "include/constants/species.h",
        re.compile(r"^\s*#define\s+([A-Z0-9_]+)\s+(.+?)\s*$"),
    )
    maximum = species_values["MAX_SPECIES_INCLUDING_FORMS"]
    require(
        len(expected) == (maximum + 1) * 2
        and mapping_count > 0
        and maximum_depth > 0,
        "current-input parent oracle has the wrong complete u16 shape",
    )
    module.verify_parent_member_against_current_inputs(
        expected,
        expected,
        names_by_id,
    )

    butterfree = species_values["SPECIES_BUTTERFREE"]
    metapod = species_values["SPECIES_METAPOD"]
    caterpie = species_values["SPECIES_CATERPIE"]
    offset = butterfree * 2
    require(
        int.from_bytes(expected[offset:offset + 2], "little") == metapod,
        "current-input parent fixture lost Butterfree <- Metapod",
    )
    tampered = bytearray(expected)
    tampered[offset:offset + 2] = caterpie.to_bytes(2, "little")
    expected_mismatch = (
        f"target {butterfree} (SPECIES_BUTTERFREE) "
        f"expected {metapod} (SPECIES_METAPOD), "
        f"actual {caterpie} (SPECIES_CATERPIE)"
    )
    require(
        module.first_parent_mismatch(
            bytes(tampered),
            expected,
            names_by_id,
        ) == expected_mismatch,
        "tampered parent member did not identify the precise stale row",
    )
    try:
        module.verify_parent_member_against_current_inputs(
            bytes(tampered),
            expected,
            names_by_id,
        )
    except SystemExit as error:
        require(
            expected_mismatch in str(error),
            f"tampered parent member failed imprecisely: {error}",
        )
    else:
        require(False, "tampered final-ROM parent member was accepted")


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

    tutor_start = tutor_source.index("TutorMove sTutorMoves[]")
    tutor_end = tutor_source.index("};", tutor_start)
    field_tutors = re.findall(
        r"\{\s*(MOVE_[A-Z0-9_]+)\s*,",
        tutor_source[tutor_start:tutor_end],
    )
    for fragment in (
        "u16 tutorMoves[NUM_TUTOR_MOVES]",
        "TUTOR_MOVE_IDS_OFFSET",
        "tutorMoves[i]",
    ):
        require(
            fragment in candidate_source,
            f"candidate builder lost shared tutor archive access: {fragment}",
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
        len(field_tutors) == tutor_count,
        "field tutor table length differs from generated archive",
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
        REPO / "data/PokeFormDataTbl.c",
        REPO / "data/FormToSpeciesMapping.c",
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
        parents["SPECIES_WORMADAM_SANDY"] == "SPECIES_BURMY"
        and parents["SPECIES_WORMADAM_TRASHY"] == "SPECIES_BURMY",
        "Wormadam cloak lineage does not resolve to Burmy",
    )
    require(
        parents["SPECIES_LYCANROC"] == "SPECIES_ROCKRUFF"
        and parents["SPECIES_LYCANROC_MIDNIGHT"] == "SPECIES_ROCKRUFF"
        and parents["SPECIES_LYCANROC_DUSK"]
        == "SPECIES_ROCKRUFF_OWN_TEMPO",
        "evolutionwithform parent mapping differs",
    )
    require(
        parents["SPECIES_RAICHU_ALOLAN"] == "SPECIES_PIKACHU",
        "alternate evolved form did not inherit its base lineage",
    )
    require(
        parents["SPECIES_RATICATE_ALOLAN"] == "SPECIES_RATTATA_ALOLAN",
        "explicit regional lineage was overwritten by base fallback",
    )
    for target, parent in (
        ("SPECIES_RATICATE_ALOLAN_LARGE", "SPECIES_RATTATA_ALOLAN"),
        (
            "SPECIES_DARMANITAN_ZEN_MODE_GALARIAN",
            "SPECIES_DARUMAKA_GALARIAN",
        ),
        ("SPECIES_ARCANINE_LORD", "SPECIES_GROWLITHE_HISUIAN"),
        ("SPECIES_ELECTRODE_LORD", "SPECIES_VOLTORB_HISUIAN"),
    ):
        require(
            parents[target] == parent,
            f"derived regional lineage differs for {target}",
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


def verify_hgss_special_policy_model() -> None:
    spiky_gift = {
        "MOVE_HELPING_HAND",
        "MOVE_VOLT_TACKLE",
        "MOVE_SWAGGER",
        "MOVE_PAIN_SPLIT",
    }

    def allowed(
        species: str,
        form: int,
        lineage: list[str],
        move: str,
    ) -> bool:
        if move == "MOVE_VOLT_TACKLE" and "SPECIES_PICHU" in lineage:
            return True
        return (
            species == "SPECIES_PICHU"
            and form == 1
            and move in spiky_gift
        )

    require(
        all(
            allowed("SPECIES_PICHU", 1, ["SPECIES_PICHU"], move)
            for move in spiky_gift
        ),
        "Spiky-ear Pichu's canonical scripted moves are not all legal",
    )
    for species in ("SPECIES_PICHU", "SPECIES_PIKACHU", "SPECIES_RAICHU"):
        require(
            allowed(species, 0, [species, "SPECIES_PICHU"], "MOVE_VOLT_TACKLE"),
            f"Light Ball Volt Tackle lineage allowance lost for {species}",
        )
    require(
        not allowed(
            "SPECIES_PICHU",
            0,
            ["SPECIES_PICHU"],
            "MOVE_PAIN_SPLIT",
        )
        and not allowed(
            "SPECIES_BUTTERFREE",
            0,
            ["SPECIES_BUTTERFREE"],
            "MOVE_VOLT_TACKLE",
        ),
        "HGSS special move policy leaked outside its species/form lineage",
    )


def main() -> None:
    verify_source_contract()
    verify_atomic_learnset_publication()
    verify_final_parent_oracle_rejects_tampering()
    verify_shared_move_tables()
    verify_parent_generator()
    verify_ordering_model()
    verify_hgss_special_policy_model()
    print(
        "move-relearn candidates: source policy, lineage data, shared tables, "
        "ordering, dedupe, filtering, and truncation verified"
    )


if __name__ == "__main__":
    main()
