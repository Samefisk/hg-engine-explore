#!/usr/bin/env python3
"""Generate the compact reverse-evolution lookup used by move relearning."""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import re
from pathlib import Path


EVODATA_RE = re.compile(r"^\s*evodata\s+(SPECIES_[A-Z0-9_]+)\b")
EVOLUTION_RE = re.compile(
    r"^\s*evolution\s+([^,]+),\s*[^,]+,\s*(SPECIES_[A-Z0-9_]+)\b"
)
EVOLUTION_WITH_FORM_RE = re.compile(
    r"^\s*evolutionwithform\s+([^,]+),\s*[^,]+,\s*"
    r"(SPECIES_[A-Z0-9_]+)\s*,\s*([0-9]+)\b"
)
FORM_TABLE_RE = re.compile(
    r"\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*\{(.*?)\}",
    re.DOTALL,
)
FORM_SPECIES_RE = re.compile(
    r"(?:NEEDS_REVERSION\s*\|\s*)?(SPECIES_[A-Z0-9_]+)"
)
FORM_TO_SPECIES_RE = re.compile(
    r"\[(SPECIES_[A-Z0-9_]+)\s*-\s*SPECIES_MEGA_START\]\s*=\s*"
    r"(SPECIES_[A-Z0-9_]+)"
)

# These battle/cosmetic derivatives belong to a regional form family but do
# not have their own evolution edge. Name-based inference is deliberately
# avoided: labels such as LORD do not encode HISUIAN, while suffix matching
# would still misclassify regional Zen Mode.
DERIVED_FORM_PARENT_OVERRIDES = {
    "SPECIES_WORMADAM_SANDY": "SPECIES_BURMY",
    "SPECIES_WORMADAM_TRASHY": "SPECIES_BURMY",
    "SPECIES_RATICATE_ALOLAN_LARGE": "SPECIES_RATTATA_ALOLAN",
    "SPECIES_DARMANITAN_ZEN_MODE_GALARIAN": "SPECIES_DARUMAKA_GALARIAN",
    "SPECIES_ARCANINE_LORD": "SPECIES_GROWLITHE_HISUIAN",
    "SPECIES_ELECTRODE_LORD": "SPECIES_VOLTORB_HISUIAN",
}


def evaluate_constant(expression: str, values: dict[str, int]) -> int:
    def evaluate(node: ast.AST) -> int:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -evaluate(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return evaluate(node.left) + evaluate(node.right)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
            return evaluate(node.left) - evaluate(node.right)
        raise ValueError(f"unsupported constant expression: {expression}")

    return evaluate(ast.parse(expression, mode="eval").body)


def load_constants(path: Path, pattern: re.Pattern[str]) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in path.read_text().splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        name, expression = match.groups()
        expression = expression.split("//", 1)[0].strip()
        try:
            values[name] = evaluate_constant(expression, values)
        except (SyntaxError, ValueError):
            continue
    return values


def without_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//.*", "", source)


def load_form_table(path: Path) -> dict[str, list[str]]:
    source = without_comments(path.read_text())
    return {
        base: FORM_SPECIES_RE.findall(entries)
        for base, entries in FORM_TABLE_RE.findall(source)
    }


def load_form_bases(path: Path) -> dict[str, str]:
    return dict(FORM_TO_SPECIES_RE.findall(without_comments(path.read_text())))


def generate(
    source: Path,
    species_header: Path,
    armips_species_header: Path,
    form_data: Path,
    form_to_species: Path,
) -> str:
    c_values = load_constants(
        species_header,
        re.compile(r"^\s*#define\s+([A-Z0-9_]+)\s+(.+?)\s*$"),
    )
    armips_values = load_constants(
        armips_species_header,
        re.compile(r"^\s*\.equ\s+([A-Z0-9_]+)\s*,\s*(.+?)\s*$"),
    )
    c_by_value = {
        value: name
        for name, value in c_values.items()
        if name.startswith("SPECIES_")
    }

    def canonical(symbol: str) -> str:
        if symbol not in armips_values:
            raise ValueError(f"missing armips species constant {symbol}")
        value = armips_values[symbol]
        if value not in c_by_value:
            raise ValueError(
                f"armips species {symbol} ({value}) has no C equivalent"
            )
        return c_by_value[value]

    form_table = load_form_table(form_data)
    form_bases = load_form_bases(form_to_species)
    current: str | None = None
    parent_sets: dict[str, list[str]] = defaultdict(list)

    for line in without_comments(source.read_text()).splitlines():
        match = EVODATA_RE.match(line)
        if match:
            current = canonical(match.group(1))
            continue
        match = EVOLUTION_RE.match(line)
        form_match = EVOLUTION_WITH_FORM_RE.match(line)
        if match is None and form_match is None:
            continue
        if current is None:
            raise ValueError("evolution appeared before evodata")
        if match is not None:
            if match.group(1).strip() == "EVO_NONE":
                continue
            target = canonical(match.group(2))
        else:
            assert form_match is not None
            if form_match.group(1).strip() == "EVO_NONE":
                continue
            target_base = canonical(form_match.group(2))
            form = int(form_match.group(3))
            forms = form_table.get(target_base, [])
            # Mirrors PokeOtherFormMonsNoGet: form zero is the base species;
            # missing nonzero slots also fall back to the base species.
            target = (
                forms[form - 1]
                if form != 0 and form <= len(forms)
                else target_base
            )
        if current not in parent_sets[target]:
            parent_sets[target].append(current)

    known_species = set(c_by_value.values())
    parents: dict[str, str] = {}
    for target, candidates in parent_sets.items():
        base_parent = min(candidates, key=len)
        parents[target] = base_parent
        for candidate in candidates:
            if candidate == base_parent:
                continue
            if not candidate.startswith(base_parent + "_"):
                raise ValueError(
                    f"{target} has unrelated parents: {base_parent}, {candidate}"
                )
            form_target = target + candidate[len(base_parent):]
            if form_target not in known_species:
                raise ValueError(
                    f"missing form target {form_target} for parent {candidate}"
                )
            previous = parents.get(form_target)
            if previous is not None and previous != candidate:
                raise ValueError(
                    f"{form_target} has ambiguous parents: {previous}, {candidate}"
                )
            parents[form_target] = candidate

    for form_species, regional_parent in DERIVED_FORM_PARENT_OVERRIDES.items():
        if form_species not in known_species or regional_parent not in known_species:
            raise ValueError(
                f"derived form parent override references an unknown species: "
                f"{form_species} -> {regional_parent}"
            )
        parents.setdefault(form_species, regional_parent)

    # Some alternate evolved forms have an unformed parent and therefore no
    # explicit edge (for example Alolan Raichu <- Pikachu). After the explicit
    # regional-family derivatives above, inherit the base target's resolved
    # parent only when no evolution or form-family edge won.
    for form_species, base_species in sorted(form_bases.items()):
        if form_species not in parents and base_species in parents:
            parents[form_species] = parents[base_species]

    rows = [
        "// DO NOT MODIFY THIS FILE! Generated by build_move_relearn_parents.py",
        "",
        '#include "../../include/types.h"',
        '#include "../../include/constants/species.h"',
        "",
        "const u16 MoveRelearnParentSpecies[MAX_SPECIES_INCLUDING_FORMS + 1] = {",
    ]
    rows.extend(
        f"    [{target}] = {parent},"
        for target, parent in sorted(parents.items())
    )
    rows.extend(["};", ""])
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evodata", type=Path, required=True)
    parser.add_argument("--species-header", type=Path, required=True)
    parser.add_argument("--armips-species-header", type=Path, required=True)
    parser.add_argument("--form-data", type=Path, required=True)
    parser.add_argument("--form-to-species", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = generate(
        args.evodata,
        args.species_header,
        args.armips_species_header,
        args.form_data,
        args.form_to_species,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(output)
    temporary.replace(args.output)


if __name__ == "__main__":
    main()
