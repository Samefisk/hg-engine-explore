"""Surgical, source-preserving writes for Pokémon learnsets.

The canonical learnset file is a formatted JSON object keyed by adjusted
species symbol. Existing records are replaced at their top-level value span;
materialized inherited forms are appended without reserializing unrelated
records. Equal-level move order is always retained from the request.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pokemon_writer


LEARNSETS_RELATIVE = "data/learnsets/learnsets.json"
SPECIES_CONSTANTS_RELATIVE = "asm/include/species.inc"
MOVE_CONSTANTS_RELATIVE = "asm/include/moves.inc"
FORM_MAPPING_RELATIVE = "data/FormToSpeciesMapping.c"

# Armips personal/species constants retain the historical spelling while the
# generated learnset JSON uses the public C spelling. Accept either at the API
# boundary, but plan against the canonical Armips identity and patch the real
# top-level JSON key.
SPECIES_TABLE_ALIASES = pokemon_writer.SPECIES_TABLE_ALIASES
REVERSE_SPECIES_TABLE_ALIASES = pokemon_writer.REVERSE_SPECIES_TABLE_ALIASES

PAYLOAD_SECTION_KEYS = {
    "levelMoves": "LevelMoves",
    "machineMoves": "MachineMoves",
    "tutorMoves": "TutorMoves",
    "eggMoves": "EggMoves",
}
SOURCE_SECTION_KEYS = tuple(PAYLOAD_SECTION_KEYS.values())

LEGACY_FORM_BASES = {
    "SPECIES_DEOXYS_ATTACK": "SPECIES_DEOXYS",
    "SPECIES_DEOXYS_DEFENSE": "SPECIES_DEOXYS",
    "SPECIES_DEOXYS_SPEED": "SPECIES_DEOXYS",
    "SPECIES_WORMADAM_SANDY": "SPECIES_WORMADAM",
    "SPECIES_WORMADAM_TRASHY": "SPECIES_WORMADAM",
    "SPECIES_GIRATINA_ORIGIN": "SPECIES_GIRATINA",
    "SPECIES_SHAYMIN_SKY": "SPECIES_SHAYMIN",
    "SPECIES_ROTOM_HEAT": "SPECIES_ROTOM",
    "SPECIES_ROTOM_WASH": "SPECIES_ROTOM",
    "SPECIES_ROTOM_FROST": "SPECIES_ROTOM",
    "SPECIES_ROTOM_FAN": "SPECIES_ROTOM",
    "SPECIES_ROTOM_MOW": "SPECIES_ROTOM",
}


@dataclass(frozen=True)
class JsonEntrySpan:
    symbol: str
    value_start: int
    value_end: int
    value: dict[str, Any]


@dataclass(frozen=True)
class Replacement:
    start: int
    end: int
    text: str
    label: str


def mutation_source_paths(root: Path) -> tuple[Path, ...]:
    """Return the sole source file this writer can mutate."""

    return ((Path(root).resolve() / LEARNSETS_RELATIVE).resolve(),)


def _skip_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _top_level_entries(text: str) -> tuple[dict[str, JsonEntrySpan], int]:
    """Index strict JSON top-level value spans without normalizing the text."""

    decoder = json.JSONDecoder()
    index = _skip_whitespace(text, 0)
    if index >= len(text) or text[index] != "{":
        raise ValueError("learnsets source must be one top-level JSON object")
    index += 1
    entries: dict[str, JsonEntrySpan] = {}
    last_value_end: int | None = None
    while True:
        index = _skip_whitespace(text, index)
        if index >= len(text):
            raise ValueError("unterminated learnsets JSON object")
        if text[index] == "}":
            closing_brace = index
            index = _skip_whitespace(text, index + 1)
            if index != len(text):
                raise ValueError("unexpected content after learnsets JSON object")
            return entries, last_value_end if last_value_end is not None else closing_brace
        try:
            symbol, key_end = decoder.raw_decode(text, index)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid learnsets JSON key: {exc}") from exc
        if not isinstance(symbol, str):
            raise ValueError("learnsets top-level keys must be strings")
        if symbol in entries:
            raise ValueError(f"duplicate learnsets record for {symbol}")
        index = _skip_whitespace(text, key_end)
        if index >= len(text) or text[index] != ":":
            raise ValueError(f"missing colon after learnsets key {symbol}")
        value_start = _skip_whitespace(text, index + 1)
        try:
            value, value_end = decoder.raw_decode(text, value_start)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid learnsets record for {symbol}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"learnsets record for {symbol} must be an object")
        entries[symbol] = JsonEntrySpan(symbol, value_start, value_end, value)
        last_value_end = value_end
        index = _skip_whitespace(text, value_end)
        if index >= len(text):
            raise ValueError("unterminated learnsets JSON object")
        if text[index] == ",":
            index += 1
            continue
        if text[index] != "}":
            raise ValueError(f"expected comma after learnsets record {symbol}")


def _constant_symbols(path: Path, prefix: str) -> set[str]:
    if not path.is_file():
        raise ValueError(f"missing authoritative constants: {path}")
    pattern = re.compile(rf"^\s*\.equ\s+({re.escape(prefix)}[A-Z0-9_]+)\s*,", re.MULTILINE)
    symbols = set(pattern.findall(path.read_text(encoding="utf-8")))
    if not symbols:
        raise ValueError(f"no {prefix} symbols found in {path}")
    return symbols


def _form_bases(root: Path) -> dict[str, str]:
    path = root / FORM_MAPPING_RELATIVE
    if not path.is_file():
        raise ValueError(f"missing form mapping source: {path}")
    text = path.read_text(encoding="utf-8")
    mapping = dict(LEGACY_FORM_BASES)
    for form, base in re.findall(
        r"\[\s*(SPECIES_[A-Z0-9_]+)\s*-\s*SPECIES_MEGA_START\s*\]\s*=\s*"
        r"(SPECIES_[A-Z0-9_]+)",
        text,
    ):
        previous = mapping.get(form)
        if previous is not None and previous != base:
            raise ValueError(f"conflicting form base for {form}: {previous} and {base}")
        mapping[form] = base
    return mapping


def _valid_species(symbols: set[str]) -> set[str]:
    excluded = {"SPECIES_NONE", "SPECIES_EGG", "SPECIES_BAD_EGG"}
    return {
        symbol
        for symbol in symbols
        if symbol not in excluded
        and not re.fullmatch(r"SPECIES_\d+", symbol)
        and "_FILLER_" not in symbol
    }


def accepted_move_symbols(root: Path) -> tuple[str, ...]:
    """Return exactly the move symbols accepted by learnset payload validation."""

    moves = _constant_symbols(Path(root).resolve() / MOVE_CONSTANTS_RELATIVE, "MOVE_")
    accepted: list[str] = []
    for symbol in moves:
        try:
            _move_symbol(symbol, "move", moves)
        except ValueError:
            continue
        accepted.append(symbol)
    return tuple(sorted(accepted))


def _provenance(
    symbol: str,
    entries: dict[str, JsonEntrySpan],
    form_bases: dict[str, str],
) -> dict[str, Any]:
    source_alias = SPECIES_TABLE_ALIASES.get(symbol)
    explicit_source = symbol if symbol in entries else (source_alias if source_alias in entries else None)
    if explicit_source:
        return {
            "provenance": "explicit",
            "sourceSymbol": explicit_source,
            "canonicalSymbol": symbol,
            "baseSymbol": form_bases.get(symbol, symbol),
            "materializationRequired": False,
        }
    base = form_bases.get(symbol)
    base_alias = SPECIES_TABLE_ALIASES.get(base) if base else None
    inherited_source = base if base in entries else (base_alias if base_alias in entries else None)
    if base and inherited_source:
        return {
            "provenance": "inherited",
            "sourceSymbol": inherited_source,
            "canonicalSymbol": symbol,
            "baseSymbol": base,
            "materializationRequired": True,
        }
    return {
        "provenance": "missing",
        "sourceSymbol": None,
        "canonicalSymbol": symbol,
        "baseSymbol": base,
        "materializationRequired": False,
    }


def learnset_access_matrix(root: Path) -> dict[str, dict[str, Any]]:
    """Return provenance and independently truthful access for every section."""

    root = Path(root).resolve()
    species = _valid_species(_constant_symbols(root / SPECIES_CONSTANTS_RELATIVE, "SPECIES_"))
    moves = _constant_symbols(root / MOVE_CONSTANTS_RELATIVE, "MOVE_")
    text = (root / LEARNSETS_RELATIVE).read_text(encoding="utf-8")
    entries, _ = _top_level_entries(text)
    form_bases = _form_bases(root)
    result: dict[str, dict[str, Any]] = {}
    for symbol in species:
        provenance = _provenance(symbol, entries, form_bases)
        sections: dict[str, dict[str, Any]] = {}
        source_span = entries.get(provenance["sourceSymbol"])
        for payload_key, source_key in PAYLOAD_SECTION_KEYS.items():
            diagnostics: list[str] = []
            if source_span is None:
                access = {
                    "writable": False,
                    "reason": "no explicit or inheritable learnset",
                    "diagnostics": diagnostics,
                }
            elif source_key not in source_span.value:
                access = {
                    "writable": False,
                    "reason": f"source learnset is missing {source_key}",
                    "diagnostics": diagnostics,
                }
            else:
                value = source_span.value[source_key]
                try:
                    if source_key == "LevelMoves":
                        payload_value = [
                            {"level": entry["Level"], "move": entry["Move"]}
                            for entry in value
                        ]
                        _normalise_level_moves(payload_value, moves, payload_key)
                    else:
                        _normalise_move_list(value, moves, payload_key)
                    duplicates = _duplicate_counts(source_key, value)
                    if duplicates:
                        diagnostics.append(
                            "canonical duplicates preserved: "
                            + ", ".join(
                                f"{identity} ×{count}"
                                for identity, count in duplicates.items()
                            )
                        )
                    access = {
                        "writable": True,
                        "reason": None,
                        "diagnostics": diagnostics,
                    }
                except (KeyError, TypeError, ValueError) as exc:
                    access = {
                        "writable": False,
                        "reason": str(exc),
                        "diagnostics": diagnostics,
                    }
            sections[payload_key] = access
        writable = any(access["writable"] for access in sections.values())
        result[symbol] = {
            **provenance,
            "writable": writable,
            "reason": None if writable else "no writable learnset sections",
            "sections": sections,
            "canMaterialize": provenance["provenance"] == "inherited",
            "canReturnToInheritance": False,
        }
    return result


def learnset_access(root: Path, symbol: str) -> dict[str, Any]:
    canonical_symbol = REVERSE_SPECIES_TABLE_ALIASES.get(symbol, symbol)
    matrix = learnset_access_matrix(root)
    access = matrix.get(canonical_symbol)
    if access is None:
        raise ValueError(f"unknown or non-editable species symbol: {symbol}")
    return access


def _move_symbol(value: Any, field: str, moves: set[str]) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"MOVE_[A-Z0-9_]+", value):
        raise ValueError(f"{field} must be a MOVE_ symbol")
    if value == "MOVE_NONE" or value not in moves:
        raise ValueError(f"{field} references unknown or sentinel move {value}")
    return value


def _normalise_level_moves(value: Any, moves: set[str], label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    result: list[dict[str, Any]] = []
    previous_level = -1
    for index, entry in enumerate(value):
        if not isinstance(entry, dict) or set(entry) != {"level", "move"}:
            raise ValueError(f"{label}[{index}] must contain exactly level and move")
        level = entry["level"]
        if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 100:
            raise ValueError(f"{label}[{index}].level must be an integer from 0 to 100")
        if level < previous_level:
            raise ValueError(f"{label} must be ordered by nondecreasing level")
        previous_level = level
        move = _move_symbol(entry["move"], f"{label}[{index}].move", moves)
        result.append({"Level": level, "Move": move})
    return result


def _normalise_move_list(value: Any, moves: set[str], label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    result: list[str] = []
    for index, raw in enumerate(value):
        move = _move_symbol(raw, f"{label}[{index}]", moves)
        result.append(move)
    return result


def _duplicate_counts(source_key: str, value: Any) -> dict[Any, int]:
    counts: dict[Any, int] = {}
    if not isinstance(value, list):
        return counts
    identities = (
        ((entry.get("Level"), entry.get("Move")) for entry in value if isinstance(entry, dict))
        if source_key == "LevelMoves"
        else iter(value)
    )
    for identity in identities:
        counts[identity] = counts.get(identity, 0) + 1
    return {identity: count for identity, count in counts.items() if count > 1}


def _normalise_record(
    raw: Any,
    index: int,
    species: set[str],
    moves: set[str],
) -> tuple[str, dict[str, Any], bool]:
    if not isinstance(raw, dict):
        raise ValueError(f"records[{index}] must be an object")
    allowed = {"symbol", "materializeInherited", *PAYLOAD_SECTION_KEYS}
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"records[{index}] has unknown keys: {', '.join(sorted(unknown))}")
    raw_symbol = raw.get("symbol")
    symbol = REVERSE_SPECIES_TABLE_ALIASES.get(raw_symbol, raw_symbol) if isinstance(raw_symbol, str) else raw_symbol
    if not isinstance(symbol, str) or symbol not in species:
        raise ValueError(f"records[{index}].symbol must be a known editable SPECIES_ symbol")
    materialize = raw.get("materializeInherited", False)
    if not isinstance(materialize, bool):
        raise ValueError(f"{symbol}.materializeInherited must be a boolean")
    supplied = {key for key in PAYLOAD_SECTION_KEYS if key in raw}
    if not supplied:
        raise ValueError(f"{symbol} must provide at least one learnset section")
    sections: dict[str, Any] = {}
    for payload_key in PAYLOAD_SECTION_KEYS:
        if payload_key not in raw:
            continue
        source_key = PAYLOAD_SECTION_KEYS[payload_key]
        if payload_key == "levelMoves":
            sections[source_key] = _normalise_level_moves(raw[payload_key], moves, payload_key)
        else:
            sections[source_key] = _normalise_move_list(raw[payload_key], moves, payload_key)
    return symbol, sections, materialize


def _format_species_value(value: dict[str, Any], newline: str) -> str:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, separators=(",", ": "))
    lines = rendered.splitlines()
    # The first opening brace follows `"SPECIES_*": `. Remaining lines sit
    # one top-level indent deeper than json.dumps emits on its own.
    formatted = lines[0] + "\n" + "\n".join("  " + line for line in lines[1:])
    return formatted.replace("\n", newline)


def _apply_replacements(text: str, replacements: list[Replacement]) -> str:
    ordered = sorted(replacements, key=lambda item: (item.start, item.end))
    for previous, current in zip(ordered, ordered[1:]):
        if current.start < previous.end:
            raise ValueError(f"overlapping learnset updates: {previous.label}, {current.label}")
    updated = text
    for replacement in reversed(ordered):
        updated = updated[: replacement.start] + replacement.text + updated[replacement.end :]
    return updated


def _atomic_write(path: Path, body: bytes) -> None:
    mode = path.stat().st_mode & 0o7777
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            os.fchmod(output.fileno(), mode)
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply_learnset_updates(root: Path, payload: Any) -> dict[str, Any]:
    """Validate and surgically apply explicit or materialized learnset edits."""

    root = Path(root).resolve()
    if not isinstance(payload, dict) or set(payload) != {"records"}:
        raise ValueError("learnset update payload must contain exactly records")
    raw_records = payload.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        raise ValueError("learnset update records must be a non-empty array")

    path = root / LEARNSETS_RELATIVE
    if not path.is_file():
        raise ValueError(f"missing canonical learnsets source: {path}")
    original_bytes = path.read_bytes()
    try:
        text = original_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("learnsets source must be valid UTF-8") from exc
    entries, last_value_end = _top_level_entries(text)
    species = _valid_species(_constant_symbols(root / SPECIES_CONSTANTS_RELATIVE, "SPECIES_"))
    moves = _constant_symbols(root / MOVE_CONSTANTS_RELATIVE, "MOVE_")
    form_bases = _form_bases(root)

    requested: list[tuple[str, dict[str, Any], bool]] = []
    seen_symbols: set[str] = set()
    for index, raw in enumerate(raw_records):
        symbol, sections, materialize = _normalise_record(raw, index, species, moves)
        if symbol in seen_symbols:
            raise ValueError(f"duplicate learnset update record for {symbol}")
        seen_symbols.add(symbol)
        requested.append((symbol, sections, materialize))

    replacements: list[Replacement] = []
    materialized: list[tuple[str, dict[str, Any]]] = []
    planned_values: dict[str, dict[str, Any]] = {}
    planned_output_symbols: set[str] = set()
    changed_sections = 0
    for symbol, sections, materialize in requested:
        provenance = _provenance(symbol, entries, form_bases)
        if provenance["provenance"] == "missing":
            raise ValueError(f"{symbol} has no explicit or inheritable learnset")
        if provenance["provenance"] == "inherited" and not materialize:
            raise ValueError(
                f"{symbol} inherits from {provenance['sourceSymbol']}; "
                "set materializeInherited true to create an explicit record"
            )
        if provenance["provenance"] == "explicit" and materialize:
            raise ValueError(f"{symbol} is already explicit; materializeInherited is not valid")

        source_span = entries[provenance["sourceSymbol"]]
        updated_value = dict(source_span.value)
        section_changes = 0
        for source_key, value in sections.items():
            existing_duplicates = _duplicate_counts(
                source_key, updated_value.get(source_key, [])
            )
            requested_duplicates = _duplicate_counts(source_key, value)
            introduced = {
                identity: count
                for identity, count in requested_duplicates.items()
                if count > existing_duplicates.get(identity, 1)
            }
            if introduced:
                duplicate_labels = ", ".join(str(identity) for identity in introduced)
                raise ValueError(
                    f"{symbol} {source_key} introduces duplicate entries: "
                    f"{duplicate_labels}"
                )
            if updated_value.get(source_key) != value:
                updated_value[source_key] = value
                section_changes += 1
        if provenance["provenance"] == "explicit":
            if section_changes == 0:
                raise ValueError(f"no-op learnset edit for {symbol}")
            replacements.append(
                Replacement(
                    source_span.value_start,
                    source_span.value_end,
                    _format_species_value(updated_value, "\r\n" if "\r\n" in text else "\n"),
                    symbol,
                )
            )
            planned_values[provenance["sourceSymbol"]] = updated_value
            planned_output_symbols.add(provenance["sourceSymbol"])
            changed_sections += section_changes
        else:
            # Materialization changes the provenance of the complete four-part
            # effective learnset, even when a supplied section equals the base.
            materialized.append((symbol, updated_value))
            planned_values[symbol] = updated_value
            planned_output_symbols.add(symbol)
            changed_sections += len(SOURCE_SECTION_KEYS)

    if materialized:
        newline = "\r\n" if "\r\n" in text else "\n"
        insertion_parts: list[str] = []
        for symbol, value in materialized:
            rendered = _format_species_value(value, newline)
            insertion_parts.append(f'{newline}  {json.dumps(symbol)}: {rendered}')
        replacements.append(
            Replacement(
                last_value_end,
                last_value_end,
                "," + ",".join(insertion_parts),
                "materialized inherited learnsets",
            )
        )

    updated_text = _apply_replacements(text, replacements)
    if updated_text == text:
        raise ValueError("learnset update contains no source changes")
    try:
        parsed = json.loads(updated_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"patched learnsets JSON failed validation: {exc}") from exc
    if not isinstance(parsed, dict) or len(parsed) != len(entries) + len(materialized):
        raise ValueError("patched learnsets JSON changed the unexpected number of records")
    expected = {symbol: span.value for symbol, span in entries.items()}
    expected.update(planned_values)
    if parsed != expected:
        raise ValueError("patched learnsets JSON did not round-trip to the planned records")
    for symbol in planned_output_symbols:
        if symbol not in parsed:
            raise ValueError(f"patched learnsets JSON lost requested record {symbol}")

    _atomic_write(path, updated_text.encode("utf-8"))
    return {
        "saved": True,
        "changedRecords": len(requested),
        "changedSections": changed_sections,
        "sourceFiles": [LEARNSETS_RELATIVE],
    }
