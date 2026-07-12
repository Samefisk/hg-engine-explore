"""Narrow, lossless writers for the first writable Pokédex fields.

The Pokémon model is assembled from several hand-maintained source files.
This module deliberately does not serialize that model back to disk.  It
locates the exact source token for every accepted field and replaces only that
token, preserving all surrounding whitespace, comments, ordering, and
preprocessor structure byte-for-byte.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MONDATA_RELATIVE = "armips/data/mondata.s"
BASE_EXPERIENCE_RELATIVE = "data/BaseExperienceTable.c"
HIDDEN_ABILITY_RELATIVE = "data/HiddenAbilityTable.c"

ENUM_SOURCE_RELATIVE_PATHS = {
    "TYPE_": "armips/include/constants.s",
    "BODY_COLOR_": "armips/include/constants.s",
    "GROWTH_": "armips/include/constants.s",
    "EGG_GROUP_": "armips/include/constants.s",
    "ITEM_": "asm/include/items.inc",
    "ABILITY_": "asm/include/abilities.inc",
}

# Armips personal data follows the historical HGSS spelling, while the C
# tables use the modern public constant.  Keep this explicit: fuzzy underscore
# normalization could silently alias two genuinely different future species.
SPECIES_TABLE_ALIASES = {
    "SPECIES_MIMEJR": "SPECIES_MIME_JR",
}
REVERSE_SPECIES_TABLE_ALIASES = {
    table_symbol: armips_symbol
    for armips_symbol, table_symbol in SPECIES_TABLE_ALIASES.items()
}


def canonical_species_symbol(symbol: str) -> str:
    """Return the canonical Armips identity for either public spelling."""

    normalized = symbol.strip().upper()
    if not normalized.startswith("SPECIES_"):
        normalized = f"SPECIES_{normalized}"
    return REVERSE_SPECIES_TABLE_ALIASES.get(normalized, normalized)

STAT_COMPONENTS = ("hp", "attack", "defense", "speed", "spAttack", "spDefense")


@dataclass(frozen=True)
class FieldSpec:
    source: str
    macro: str | None = None
    argument: int = 0
    kind: str = "integer"
    minimum: int | None = None
    maximum: int | None = None
    prefix: str | None = None
    max_length: int | None = None
    max_newlines: int = 0


@dataclass(frozen=True)
class TokenSpan:
    start: int
    end: int
    raw: str


@dataclass
class MonRecord:
    symbol: str
    header: tuple[TokenSpan, ...]
    directives: dict[str, tuple[TokenSpan, ...]]


@dataclass(frozen=True)
class NormalizedValue:
    semantic: Any
    token: str


@dataclass(frozen=True)
class Replacement:
    start: int
    end: int
    token: str
    field_path: str


@dataclass
class SourceIndex:
    root: Path
    paths: dict[str, Path]
    texts: dict[str, str]
    mon_records: dict[str, MonRecord]
    tables: dict[str, dict[str, TokenSpan]]
    enum_catalog: dict[str, dict[str, int | None]]
    table_aliases: dict[str, str]
    reverse_aliases: dict[str, str]


@dataclass(frozen=True)
class AccessDecision:
    writable: bool
    reason: str | None
    source: str | None = None
    span: TokenSpan | None = None


def _build_field_specs() -> dict[str, FieldSpec]:
    fields = {
        "entry.name": FieldSpec("mondata", "mondata", 1, "string", max_length=64),
        "entry.dexEntry": FieldSpec(
            "mondata", "mondexentry", 1, "string", max_length=512, max_newlines=2
        ),
        "entry.classification": FieldSpec(
            "mondata", "mondexclassification", 1, "string", max_length=96
        ),
        "entry.height": FieldSpec("mondata", "mondexheight", 1, "string", max_length=32),
        "entry.weight": FieldSpec("mondata", "mondexweight", 1, "string", max_length=32),
        "entry.genderRatio": FieldSpec("mondata", "genderratio", 0, "integer", 0, 255),
        "entry.bodyColor": FieldSpec(
            "mondata", "colorflip", 0, "enum", prefix="BODY_COLOR_"
        ),
        "entry.flip": FieldSpec("mondata", "colorflip", 1, "boolean"),
        "growth.eggCycles": FieldSpec("mondata", "eggcycles", 0, "integer", 0, 255),
        "growth.baseFriendship": FieldSpec(
            "mondata", "basefriendship", 0, "integer", 0, 255
        ),
        "growth.growthRate": FieldSpec(
            "mondata", "growthrate", 0, "enum", prefix="GROWTH_"
        ),
        "growth.eggGroups.primary": FieldSpec(
            "mondata", "egggroups", 0, "enum", prefix="EGG_GROUP_"
        ),
        "growth.eggGroups.secondary": FieldSpec(
            "mondata", "egggroups", 1, "enum", prefix="EGG_GROUP_"
        ),
        "battle.catchRate": FieldSpec("mondata", "catchrate", 0, "integer", 0, 255),
        "battle.baseExperience": FieldSpec(
            "baseExperience", kind="integer", minimum=0, maximum=65535
        ),
        "battle.heldItems.common": FieldSpec(
            "mondata", "items", 0, "enum", prefix="ITEM_"
        ),
        "battle.heldItems.rare": FieldSpec(
            "mondata", "items", 1, "enum", prefix="ITEM_"
        ),
        "battle.abilities.primary": FieldSpec(
            "mondata", "abilities", 0, "enum", prefix="ABILITY_"
        ),
        "battle.abilities.secondary": FieldSpec(
            "mondata", "abilities", 1, "enum", prefix="ABILITY_"
        ),
        "battle.abilities.hidden": FieldSpec(
            "hiddenAbility", kind="enum", prefix="ABILITY_"
        ),
        "battle.runChance": FieldSpec("mondata", "runchance", 0, "integer", 0, 255),
        "battle.types.primary": FieldSpec(
            "mondata", "types", 0, "enum", prefix="TYPE_"
        ),
        "battle.types.secondary": FieldSpec(
            "mondata", "types", 1, "enum", prefix="TYPE_"
        ),
    }
    for index, stat in enumerate(STAT_COMPONENTS):
        fields[f"battle.baseStats.{stat}"] = FieldSpec(
            "mondata", "basestats", index, "integer", 0, 255
        )
        fields[f"battle.evYields.{stat}"] = FieldSpec(
            "mondata", "evyields", index, "integer", 0, 3
        )
    return fields


FIELD_SPECS = _build_field_specs()
ALLOWED_FIELD_PATHS = frozenset(FIELD_SPECS)


def mutation_source_paths(root: Path) -> tuple[Path, ...]:
    """Return the complete source set this writer may mutate."""

    root = Path(root).resolve()
    return tuple(
        (root / relative).resolve()
        for relative in (
            MONDATA_RELATIVE,
            BASE_EXPERIENCE_RELATIVE,
            HIDDEN_ABILITY_RELATIVE,
        )
    )


def _comment_index(line: str) -> int:
    quoted = False
    escaped = False
    for index, character in enumerate(line[:-1]):
        if escaped:
            escaped = False
            continue
        if quoted and character == "\\":
            escaped = True
        elif character == '"':
            quoted = not quoted
        elif not quoted and character == "/" and line[index + 1] == "/":
            return index
    return len(line)


def _argument_spans(value: str, absolute_start: int) -> tuple[TokenSpan, ...]:
    boundaries: list[tuple[int, int]] = []
    start = 0
    quoted = False
    escaped = False
    depth = 0
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quoted and character == "\\":
            escaped = True
        elif character == '"':
            quoted = not quoted
        elif not quoted and character in "([":
            depth += 1
        elif not quoted and character in ")]":
            depth = max(0, depth - 1)
        elif not quoted and depth == 0 and character == ",":
            boundaries.append((start, index))
            start = index + 1
    if quoted or depth:
        raise ValueError("unterminated quoted string or expression in mondata source")
    boundaries.append((start, len(value)))

    spans: list[TokenSpan] = []
    for raw_start, raw_end in boundaries:
        while raw_start < raw_end and value[raw_start].isspace():
            raw_start += 1
        while raw_end > raw_start and value[raw_end - 1].isspace():
            raw_end -= 1
        if raw_start == raw_end:
            raise ValueError("empty argument in mondata source")
        spans.append(
            TokenSpan(
                absolute_start + raw_start,
                absolute_start + raw_end,
                value[raw_start:raw_end],
            )
        )
    return tuple(spans)


def _parse_mondata(text: str) -> dict[str, MonRecord]:
    records: dict[str, MonRecord] = {}
    current: MonRecord | None = None
    offset = 0
    for physical_line in text.splitlines(keepends=True):
        content = physical_line.rstrip("\r\n")
        code = content[: _comment_index(content)]
        header = re.match(r"^[ \t]*mondata[ \t]+(.+?)[ \t]*$", code)
        if header:
            spans = _argument_spans(header.group(1), offset + header.start(1))
            if len(spans) != 2 or not re.fullmatch(r"SPECIES_[A-Z0-9_]+", spans[0].raw):
                raise ValueError("malformed mondata record header")
            symbol = spans[0].raw
            if symbol in records:
                raise ValueError(f"duplicate mondata record for {symbol}")
            current = MonRecord(symbol, spans, {})
            records[symbol] = current
            offset += len(physical_line)
            continue

        if current is not None:
            directive = re.match(r"^[ \t]*([a-z][a-z0-9]*)[ \t]+(.+?)[ \t]*$", code, re.I)
            if directive:
                macro = directive.group(1).lower()
                spans = _argument_spans(directive.group(2), offset + directive.start(2))
                if macro in current.directives:
                    raise ValueError(f"duplicate {macro} directive for {current.symbol}")
                current.directives[macro] = spans
        offset += len(physical_line)

    if not records:
        raise ValueError("mondata source contains no records")
    return records


def _parse_indexed_table(text: str, label: str) -> dict[str, TokenSpan]:
    entries: dict[str, TokenSpan] = {}
    pattern = re.compile(
        r"(?m)^[ \t]*\[[ \t]*(SPECIES_[A-Z0-9_]+)[ \t]*\][ \t]*=[ \t]*"
        r"(?P<value>[^,\r\n]+?)(?=[ \t]*,)"
    )
    for match in pattern.finditer(text):
        symbol = match.group(1)
        raw = match.group("value")
        leading = len(raw) - len(raw.lstrip())
        trailing = len(raw.rstrip())
        start = match.start("value") + leading
        end = match.start("value") + trailing
        if symbol in entries:
            raise ValueError(f"duplicate {label} assignment for {symbol}")
        entries[symbol] = TokenSpan(start, end, text[start:end])
    if not entries:
        raise ValueError(f"{label} source contains no indexed assignments")
    return entries


def _parse_enum_constants(text: str, prefix: str, source_label: str) -> dict[str, int | None]:
    declarations: dict[str, int | None] = {}
    pattern = re.compile(
        rf"(?m)^[ \t]*\.equ[ \t]+({re.escape(prefix)}[A-Z0-9_]+)[ \t]*,[ \t]*([^/\r\n]+)"
    )
    for symbol, raw_value in pattern.findall(text):
        if symbol in declarations:
            raise ValueError(f"duplicate enum declaration for {symbol} in {source_label}")
        token = raw_value.strip()
        try:
            declarations[symbol] = int(token, 0)
        except ValueError:
            declarations[symbol] = None
    if not declarations:
        raise ValueError(f"{source_label} declares no {prefix} symbols")
    return declarations


def _load_enum_catalog(root: Path) -> dict[str, dict[str, int | None]]:
    source_text: dict[str, str] = {}
    catalog: dict[str, dict[str, int | None]] = {}
    for prefix, relative in ENUM_SOURCE_RELATIVE_PATHS.items():
        path = (root / relative).resolve()
        if not path.is_file():
            raise ValueError(f"missing Pokémon enum source: {relative}")
        if relative not in source_text:
            try:
                source_text[relative] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Pokémon enum source must be valid UTF-8: {relative}") from exc
        catalog[prefix] = _parse_enum_constants(source_text[relative], prefix, relative)
    return catalog


def _validated_aliases(
    mon_records: dict[str, MonRecord],
    tables: dict[str, dict[str, TokenSpan]],
) -> tuple[dict[str, str], dict[str, str]]:
    aliases = dict(SPECIES_TABLE_ALIASES)
    reverse: dict[str, str] = {}
    for mon_symbol, table_symbol in aliases.items():
        if mon_symbol in reverse or table_symbol in reverse:
            raise ValueError(f"species alias collides with another alias: {mon_symbol} -> {table_symbol}")
        if mon_symbol not in mon_records:
            raise ValueError(f"species alias source is missing from mondata: {mon_symbol}")
        if table_symbol in mon_records and table_symbol != mon_symbol:
            raise ValueError(
                f"species alias target collides with a mondata record: {table_symbol}"
            )
        if table_symbol in reverse:
            raise ValueError(f"duplicate species alias target: {table_symbol}")
        reverse[table_symbol] = mon_symbol
        for table_name, entries in tables.items():
            if mon_symbol in entries:
                raise ValueError(
                    f"species alias is ambiguous in {table_name}: both {mon_symbol} and {table_symbol} exist"
                )
            if table_symbol not in entries:
                raise ValueError(
                    f"species alias target is missing from {table_name}: {table_symbol}"
                )
    return aliases, reverse


def _load_source_index(root: Path) -> tuple[SourceIndex, dict[str, bytes]]:
    root = Path(root).resolve()
    paths = {
        "mondata": (root / MONDATA_RELATIVE).resolve(),
        "baseExperience": (root / BASE_EXPERIENCE_RELATIVE).resolve(),
        "hiddenAbility": (root / HIDDEN_ABILITY_RELATIVE).resolve(),
    }
    for label, path in paths.items():
        if not path.is_file():
            raise ValueError(f"missing Pokémon {label} source: {path.relative_to(root)}")
    original_bytes = {label: path.read_bytes() for label, path in paths.items()}
    try:
        texts = {label: body.decode("utf-8") for label, body in original_bytes.items()}
    except UnicodeDecodeError as exc:
        raise ValueError("Pokémon source files must be valid UTF-8") from exc
    mon_records = _parse_mondata(texts["mondata"])
    tables = {
        "baseExperience": _parse_indexed_table(texts["baseExperience"], "base experience"),
        "hiddenAbility": _parse_indexed_table(texts["hiddenAbility"], "hidden ability"),
    }
    aliases, reverse = _validated_aliases(mon_records, tables)
    return (
        SourceIndex(
            root=root,
            paths=paths,
            texts=texts,
            mon_records=mon_records,
            tables=tables,
            enum_catalog=_load_enum_catalog(root),
            table_aliases=aliases,
            reverse_aliases=reverse,
        ),
        original_bytes,
    )


def _integer(value: Any, field_path: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_path} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{field_path} must be between {minimum} and {maximum}")
    return value


def _source_string(value: Any, field_path: str, spec: FieldSpec) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_path} must be a string")
    if "\r" in value or "\x00" in value:
        raise ValueError(f"{field_path} contains an unsupported control character")
    for character in value:
        if ord(character) < 0x20 and character != "\n":
            raise ValueError(f"{field_path} contains an unsupported control character")
    if value.count("\n") > spec.max_newlines:
        if spec.max_newlines:
            raise ValueError(f"{field_path} supports at most {spec.max_newlines + 1} lines")
        raise ValueError(f"{field_path} must be a single line")
    if spec.max_length is not None and len(value) > spec.max_length:
        raise ValueError(f"{field_path} must be at most {spec.max_length} characters")
    if field_path == "entry.name" and not value:
        raise ValueError("entry.name cannot be empty")
    return value


def _enum_token(
    value: Any,
    field_path: str,
    prefix: str,
    enum_catalog: dict[str, dict[str, int | None]],
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_path} must be a {prefix} symbol")
    if not re.fullmatch(re.escape(prefix) + r"[A-Z0-9_]+", value):
        raise ValueError(f"{field_path} must use a valid {prefix} symbol")
    if value not in enum_catalog.get(prefix, {}):
        raise ValueError(f"{field_path} references nonexistent enum symbol {value}")
    return value


def _normalize_value(
    field_path: str,
    value: Any,
    spec: FieldSpec,
    enum_catalog: dict[str, dict[str, int | None]],
) -> NormalizedValue:
    if spec.kind == "integer":
        assert spec.minimum is not None and spec.maximum is not None
        normalized = _integer(value, field_path, spec.minimum, spec.maximum)
        return NormalizedValue(normalized, str(normalized))
    if spec.kind == "boolean":
        if isinstance(value, bool):
            normalized = int(value)
        elif isinstance(value, int) and not isinstance(value, bool) and value in (0, 1):
            normalized = value
        else:
            raise ValueError(f"{field_path} must be a boolean or 0/1")
        return NormalizedValue(bool(normalized), str(normalized))
    if spec.kind == "enum":
        assert spec.prefix is not None
        normalized = _enum_token(value, field_path, spec.prefix, enum_catalog)
        return NormalizedValue(normalized, normalized)
    if spec.kind == "string":
        normalized = _source_string(value, field_path, spec)
        return NormalizedValue(
            normalized,
            json.dumps(normalized, ensure_ascii=False, separators=(",", ":")),
        )
    raise AssertionError(f"unsupported field kind: {spec.kind}")


def _current_semantic(
    span: TokenSpan,
    field_path: str,
    spec: FieldSpec,
    enum_catalog: dict[str, dict[str, int | None]],
) -> Any:
    raw = span.raw.strip()
    if spec.kind in {"integer", "boolean"}:
        try:
            value = int(raw, 0)
        except ValueError as exc:
            raise ValueError(
                f"{field_path} currently uses expression {raw!r}; refusing a potentially lossy edit"
            ) from exc
        if spec.kind == "boolean":
            if value not in (0, 1):
                raise ValueError(f"{field_path} currently uses invalid boolean value {raw!r}")
            return bool(value)
        return value
    if spec.kind == "enum":
        assert spec.prefix is not None
        declarations = enum_catalog.get(spec.prefix, {})
        if raw in declarations:
            return raw
        if spec.prefix == "BODY_COLOR_":
            try:
                numeric = int(raw, 0)
            except ValueError:
                numeric = None
            if numeric is not None:
                matches = [
                    symbol for symbol, value in declarations.items() if value == numeric
                ]
                if len(matches) == 1:
                    return matches[0]
                if not matches:
                    raise ValueError(
                        f"{field_path} uses unknown numeric body color {raw!r}"
                    )
                raise ValueError(
                    f"{field_path} numeric body color {raw!r} is ambiguous: {', '.join(matches)}"
                )
        if re.fullmatch(re.escape(spec.prefix) + r"[A-Z0-9_]+", raw):
            raise ValueError(f"{field_path} currently references nonexistent enum symbol {raw}")
        else:
            raise ValueError(
                f"{field_path} currently uses expression {raw!r}; refusing a potentially lossy edit"
            )
    if spec.kind == "string":
        try:
            value = ast.literal_eval(raw)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(
                f"{field_path} is not stored as one safe quoted string; refusing a lossy edit"
            ) from exc
        if not isinstance(value, str):
            raise ValueError(f"{field_path} is not stored as a string")
        return value
    raise AssertionError(f"unsupported field kind: {spec.kind}")


def _directive_span(record: MonRecord, spec: FieldSpec, field_path: str) -> TokenSpan:
    if spec.macro == "mondata":
        arguments = record.header
    else:
        arguments = record.directives.get(spec.macro or "")
        if arguments is None:
            raise ValueError(
                f"{record.symbol} has no {spec.macro} directive for {field_path}; refusing to invent one"
            )
    if spec.argument >= len(arguments):
        raise ValueError(f"malformed {spec.macro} directive for {record.symbol}")
    if spec.macro and spec.macro.startswith("mondex"):
        if not arguments or arguments[0].raw != record.symbol:
            raise ValueError(f"{spec.macro} directive identity disagrees with {record.symbol}")
    return arguments[spec.argument]


def _current_ev_values(record: MonRecord) -> dict[str, int]:
    arguments = record.directives.get("evyields")
    if arguments is None or len(arguments) != len(STAT_COMPONENTS):
        raise ValueError("missing or malformed evyields directive")
    values: dict[str, int] = {}
    for stat, span in zip(STAT_COMPONENTS, arguments):
        try:
            value = int(span.raw, 0)
        except ValueError as exc:
            raise ValueError("EV yields use an expression") from exc
        if value < 0 or value > 3:
            raise ValueError(f"EV yield {stat} does not fit the packed 0..3 range")
        values[stat] = value
    if sum(values.values()) > 3:
        raise ValueError("EV yield total exceeds 3")
    return values


def _field_access(index: SourceIndex, symbol: str, field_path: str) -> AccessDecision:
    spec = FIELD_SPECS[field_path]
    record = index.mon_records.get(symbol)
    if record is None:
        return AccessDecision(False, "species is missing from mondata")
    try:
        if spec.source == "mondata":
            span = _directive_span(record, spec, field_path)
        else:
            table_symbol = index.table_aliases.get(symbol, symbol)
            span = index.tables[spec.source].get(table_symbol)
            if span is None:
                return AccessDecision(
                    False,
                    f"missing {spec.source} assignment for {table_symbol}",
                )
        current = _current_semantic(span, field_path, spec, index.enum_catalog)
        if spec.kind == "integer":
            assert spec.minimum is not None and spec.maximum is not None
            if current < spec.minimum or current > spec.maximum:
                return AccessDecision(
                    False,
                    f"current value {current} is outside {spec.minimum}..{spec.maximum}",
                )
        if field_path.startswith("battle.evYields."):
            _current_ev_values(record)
    except ValueError as exc:
        return AccessDecision(False, str(exc))
    return AccessDecision(True, None, spec.source, span)


def field_access_matrix(root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Return bulk, source-accurate writability for every mondata record.

    The matrix is keyed by the canonical Armips record symbol.  Each allowed
    field path reports ``writable`` and a stable human-readable ``reason`` (or
    ``None``).  The same private decision function gates actual writes.
    """

    index, _ = _load_source_index(Path(root).resolve())
    return {
        symbol: {
            field_path: {
                "writable": decision.writable,
                "reason": decision.reason,
            }
            for field_path in FIELD_SPECS
            for decision in (_field_access(index, symbol, field_path),)
        }
        for symbol in index.mon_records
    }


def _validate_payload(
    payload: Any,
    enum_catalog: dict[str, dict[str, int | None]],
    reverse_aliases: dict[str, str],
) -> list[tuple[str, dict[str, NormalizedValue]]]:
    if not isinstance(payload, dict):
        raise ValueError("Pokémon update payload must be an object")
    unknown_top_level = set(payload) - {"records"}
    if unknown_top_level:
        raise ValueError(f"unknown Pokémon update payload keys: {', '.join(sorted(unknown_top_level))}")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("Pokémon update payload must contain a non-empty records list")

    normalized_records: list[tuple[str, dict[str, NormalizedValue]]] = []
    seen_symbols: set[str] = set()
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            raise ValueError(f"records[{index}] must be an object")
        unknown_record_keys = set(item) - {"symbol", "fields"}
        if unknown_record_keys:
            raise ValueError(
                f"records[{index}] has unknown keys: {', '.join(sorted(unknown_record_keys))}"
            )
        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not re.fullmatch(r"SPECIES_[A-Z0-9_]+", symbol):
            raise ValueError(f"records[{index}].symbol must be a SPECIES_ symbol")
        symbol = reverse_aliases.get(symbol, symbol)
        if symbol in seen_symbols:
            raise ValueError(f"duplicate Pokémon update record for {symbol}")
        seen_symbols.add(symbol)
        fields = item.get("fields")
        if not isinstance(fields, dict) or not fields:
            raise ValueError(f"{symbol} must contain a non-empty fields object")

        normalized_fields: dict[str, NormalizedValue] = {}
        for field_path, value in fields.items():
            if not isinstance(field_path, str) or field_path not in FIELD_SPECS:
                raise ValueError(f"unsupported Pokémon field path for {symbol}: {field_path!r}")
            normalized_fields[field_path] = _normalize_value(
                field_path, value, FIELD_SPECS[field_path], enum_catalog
            )
        normalized_records.append((symbol, normalized_fields))
    return normalized_records


def _validate_ev_totals(
    requested: list[tuple[str, dict[str, NormalizedValue]]],
    index: SourceIndex,
) -> None:
    for symbol, fields in requested:
        updates = {
            field_path.removeprefix("battle.evYields."): int(value.semantic)
            for field_path, value in fields.items()
            if field_path.startswith("battle.evYields.")
        }
        if not updates:
            continue
        record = index.mon_records.get(symbol)
        if record is None:
            continue  # the normal planning pass reports the missing symbol
        try:
            values = _current_ev_values(record)
        except ValueError as exc:
            raise ValueError(f"{symbol} {exc}") from exc
        values.update(updates)
        if any(value < 0 or value > 3 for value in values.values()):
            raise ValueError(f"{symbol} EV yields must each fit the packed 0..3 range")
        if sum(values.values()) > 3:
            raise ValueError(f"{symbol} EV yield total cannot exceed 3")


def _apply_replacements(text: str, replacements: list[Replacement], source_label: str) -> str:
    ordered = sorted(replacements, key=lambda item: (item.start, item.end))
    for previous, current in zip(ordered, ordered[1:]):
        if current.start < previous.end:
            raise ValueError(
                f"overlapping edits in {source_label}: {previous.field_path} and {current.field_path}"
            )
    updated = text
    for replacement in reversed(ordered):
        updated = updated[: replacement.start] + replacement.token + updated[replacement.end :]
    return updated


def apply_pokemon_updates(root: Path, payload: Any) -> dict[str, Any]:
    """Validate and apply source-backed Pokémon field updates.

    ``payload`` must be ``{"records": [{"symbol": ..., "fields": {...}}]}``.
    Any malformed, unsupported, ambiguous, no-op, or potentially lossy edit
    rejects the complete call before a source file is written.
    """

    index, original_bytes = _load_source_index(Path(root).resolve())
    root = index.root
    paths = index.paths
    texts = index.texts
    requested = _validate_payload(payload, index.enum_catalog, index.reverse_aliases)
    _validate_ev_totals(requested, index)

    replacements: dict[str, list[Replacement]] = {label: [] for label in paths}
    changed_fields = 0
    for symbol, fields in requested:
        record = index.mon_records.get(symbol)
        if record is None:
            raise ValueError(f"unknown Pokémon symbol: {symbol}")
        for field_path, normalized in fields.items():
            spec = FIELD_SPECS[field_path]
            access = _field_access(index, symbol, field_path)
            if not access.writable or access.span is None or access.source is None:
                raise ValueError(
                    f"{symbol} {field_path} is not writable: {access.reason or 'unknown source constraint'}"
                )
            span = access.span
            current = _current_semantic(span, field_path, spec, index.enum_catalog)
            if current == normalized.semantic:
                raise ValueError(f"no-op Pokémon edit: {symbol} {field_path} is already {current!r}")
            replacements[access.source].append(
                Replacement(span.start, span.end, normalized.token, field_path)
            )
            changed_fields += 1

    updated_texts = {
        label: _apply_replacements(texts[label], replacements[label], path.relative_to(root).as_posix())
        for label, path in paths.items()
    }
    changed_sources = [label for label in paths if updated_texts[label] != texts[label]]
    if not changed_sources or changed_fields == 0:
        raise ValueError("Pokémon update contains no source changes")

    # Reparse the complete patched sources before touching disk.  This verifies
    # that token surgery did not alter record/table structure.
    _parse_mondata(updated_texts["mondata"])
    _parse_indexed_table(updated_texts["baseExperience"], "base experience")
    _parse_indexed_table(updated_texts["hiddenAbility"], "hidden ability")

    written: list[str] = []
    try:
        for label in changed_sources:
            paths[label].write_bytes(updated_texts[label].encode("utf-8"))
            written.append(label)
    except Exception:
        for label in reversed(written):
            paths[label].write_bytes(original_bytes[label])
        raise

    source_files = sorted(paths[label].relative_to(root).as_posix() for label in changed_sources)
    return {
        "saved": True,
        "changedRecords": len(requested),
        "changedFields": changed_fields,
        "sourceFiles": source_files,
    }
