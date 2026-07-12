"""Lossless fixed-slot writers for Pokémon evolutions and baby mappings."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


EVODATA_RELATIVE = "armips/data/evodata.s"
BABYMONS_RELATIVE = "armips/data/babymons.s"
CONSTANTS_RELATIVE = "armips/include/constants.s"
SPECIES_RELATIVE = "asm/include/species.inc"
ITEMS_RELATIVE = "asm/include/items.inc"
MOVES_RELATIVE = "asm/include/moves.inc"
CONFIG_RELATIVE = "include/config.h"
FORM_DATA_RELATIVE = "data/PokeFormDataTbl.c"
ITEM_DATA_RELATIVE = "data/itemdata/itemdata.c"

MAX_EVOLUTION_SLOTS = 9

LEGACY_FORM_FAMILIES: dict[str, tuple[str, ...]] = {
    "SPECIES_DEOXYS": (
        "SPECIES_DEOXYS_ATTACK",
        "SPECIES_DEOXYS_DEFENSE",
        "SPECIES_DEOXYS_SPEED",
    ),
    "SPECIES_WORMADAM": ("SPECIES_WORMADAM_SANDY", "SPECIES_WORMADAM_TRASHY"),
    "SPECIES_GIRATINA": ("SPECIES_GIRATINA_ORIGIN",),
    "SPECIES_SHAYMIN": ("SPECIES_SHAYMIN_SKY",),
    "SPECIES_ROTOM": (
        "SPECIES_ROTOM_HEAT",
        "SPECIES_ROTOM_WASH",
        "SPECIES_ROTOM_FROST",
        "SPECIES_ROTOM_FAN",
        "SPECIES_ROTOM_MOW",
    ),
}

# Lycanroc's midday form is intentionally encoded as form 3 even though its
# adjusted-form table contains only Midnight (1) and Dusk (2).  At runtime the
# empty third entry resolves back to the base species, which is the midday form.
BASE_FORM_INDEX_ALIASES: dict[str, set[int]] = {"SPECIES_LYCANROC": {3}}
BASE_FORM_INDEX_ALIAS_LABELS: dict[tuple[str, int], str] = {
    ("SPECIES_LYCANROC", 3): "Midday Form",
}

ZERO_PARAMETER_METHODS = {
    "EVO_FRIENDSHIP",
    "EVO_FRIENDSHIP_DAY",
    "EVO_FRIENDSHIP_NIGHT",
    "EVO_TRADE",
    "EVO_LEVEL_ELECTRIC_FIELD",
    "EVO_LEVEL_MOSSY_STONE",
    "EVO_LEVEL_ICY_STONE",
}
STONE_PARAMETER_METHODS = {
    "EVO_STONE",
    "EVO_STONE_MALE",
    "EVO_STONE_FEMALE",
}
HELD_ITEM_PARAMETER_METHODS = {
    "EVO_TRADE_ITEM",
    "EVO_ITEM_DAY",
    "EVO_ITEM_NIGHT",
}
MOVE_PARAMETER_METHODS = {"EVO_HAS_MOVE"}
TYPE_PARAMETER_METHODS = {"EVO_HAS_MOVE_TYPE"}
SPECIES_PARAMETER_METHODS = {"EVO_OTHER_PARTY_MON", "EVO_TRADE_SPECIFIC_MON"}
LEVEL_PARAMETER_METHODS = {
    "EVO_LEVEL",
    "EVO_LEVEL_ATK_GT_DEF",
    "EVO_LEVEL_ATK_EQ_DEF",
    "EVO_LEVEL_ATK_LT_DEF",
    "EVO_LEVEL_PID_LO",
    "EVO_LEVEL_PID_HI",
    "EVO_LEVEL_NINJASK",
    "EVO_LEVEL_SHEDINJA",
    "EVO_LEVEL_MALE",
    "EVO_LEVEL_FEMALE",
    "EVO_LEVEL_DAY",
    "EVO_LEVEL_NIGHT",
    "EVO_LEVEL_DUSK",
    "EVO_LEVEL_RAIN",
    "EVO_LEVEL_DARK_TYPE_MON_IN_PARTY",
    "EVO_LEVEL_NATURE_AMPED",
    "EVO_LEVEL_NATURE_LOW_KEY",
}
BOUNDED_NUMERIC_METHODS = {
    "EVO_BEAUTY": (0, 255),
    "EVO_AMOUNT_OF_CRITICAL_HITS": (0, 65535),
    "EVO_HURT_IN_BATTLE_AMOUNT": (0, 65535),
}


@dataclass(frozen=True)
class SourceSpan:
    start: int
    end: int
    raw: str


@dataclass(frozen=True)
class EvolutionEdge:
    method: str
    parameter: int | str
    target_symbol: str
    has_form_index: bool = False
    target_form_index: int | None = None

    def key(self) -> tuple[Any, ...]:
        return (
            self.method,
            self.parameter,
            self.target_symbol,
            self.has_form_index,
            self.target_form_index,
        )

    def directive(self) -> str:
        if self.has_form_index:
            return (
                f"evolutionwithform {self.method}, {self.parameter}, "
                f"{self.target_symbol}, {self.target_form_index}"
            )
        return f"evolution {self.method}, {self.parameter}, {self.target_symbol}"


@dataclass(frozen=True)
class EvolutionSlot:
    span: SourceSpan
    macro: str
    arguments: tuple[str, ...]


@dataclass
class EvolutionBlock:
    symbol: str
    slots: list[EvolutionSlot]
    terminated: bool = False


@dataclass(frozen=True)
class BabyRow:
    species_symbol: str
    baby_span: SourceSpan


@dataclass
class EvolutionIndex:
    root: Path
    paths: dict[str, Path]
    texts: dict[str, str]
    blocks: dict[str, EvolutionBlock]
    baby_rows: dict[str, BabyRow]
    methods: set[str]
    species: set[str]
    items: set[str]
    moves: set[str]
    types: set[str]
    public_species: set[str]
    public_items: set[str]
    evolution_items: set[str]
    public_moves: set[str]
    public_types: set[str]
    forms_by_base: dict[str, set[int]]
    adjusted_to_base: dict[str, str]


@dataclass(frozen=True)
class Replacement:
    start: int
    end: int
    token: str


@dataclass(frozen=True)
class UpdateRequest:
    symbol: str
    edges: list[EvolutionEdge] | None
    baby_symbol: str | None


def mutation_source_paths(root: Path) -> tuple[Path, ...]:
    root = Path(root).resolve()
    return (
        (root / EVODATA_RELATIVE).resolve(),
        (root / BABYMONS_RELATIVE).resolve(),
    )


def _constant_symbols(path: Path, prefix: str) -> set[str]:
    if not path.is_file():
        raise ValueError(f"missing evolution constant source: {path}")
    text = path.read_text(encoding="utf-8")
    symbols = set(
        re.findall(rf"(?m)^[ \t]*\.equ[ \t]+({re.escape(prefix)}[A-Z0-9_]+)[ \t]*,", text)
    )
    if not symbols:
        raise ValueError(f"{path} declares no {prefix} symbols")
    return symbols


def _is_public_symbol(symbol: str, prefix: str) -> bool:
    if not re.fullmatch(rf"{re.escape(prefix)}[A-Z0-9_]+", symbol):
        return False
    suffix = symbol.removeprefix(prefix)
    if suffix.isdecimal():
        return False
    if symbol in {"SPECIES_EGG", "SPECIES_BAD_EGG"}:
        return False
    words = set(suffix.split("_"))
    return not words.intersection(
        {"NONE", "UNUSED", "FILLER", "PLACEHOLDER", "RESERVED", "UNKNOWN"}
    )


def _item_domains(path: Path) -> tuple[set[str], set[str]]:
    if not path.is_file():
        raise ValueError(f"missing item data source: {ITEM_DATA_RELATIVE}")
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^\[(ITEM_[A-Z0-9_]+)\][ \t]*=", text))
    public_items: set[str] = set()
    evolution_items: set[str] = set()
    for position, match in enumerate(matches):
        symbol = match.group(1)
        if not _is_public_symbol(symbol, "ITEM_"):
            continue
        public_items.add(symbol)
        end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
        if re.search(r"(?m)^[ \t]*\.evolve[ \t]*=[ \t]*TRUE[ \t]*,", text[match.end():end]):
            evolution_items.add(symbol)
    if not public_items or not evolution_items:
        raise ValueError("item data exposes no semantic evolution-item domain")
    return public_items, evolution_items


def _public_move_symbols(path: Path) -> set[str]:
    if not path.is_file():
        raise ValueError(f"missing move constant source: {MOVES_RELATIVE}")
    text = path.read_text(encoding="utf-8")
    boundary = text.find(".equ NUM_OF_CANONICAL_MOVES")
    if boundary < 0:
        raise ValueError("move constants are missing NUM_OF_CANONICAL_MOVES")
    symbols = set(
        re.findall(r"(?m)^[ \t]*\.equ[ \t]+(MOVE_[A-Z0-9_]+)[ \t]*,", text[:boundary])
    )
    result = {symbol for symbol in symbols if _is_public_symbol(symbol, "MOVE_")}
    if not result:
        raise ValueError("move constants expose no public moves")
    return result


def _comment_index(line: str) -> int:
    index = line.find("//")
    return len(line) if index < 0 else index


def _parse_evodata(text: str) -> dict[str, EvolutionBlock]:
    blocks: dict[str, EvolutionBlock] = {}
    current: EvolutionBlock | None = None
    offset = 0
    for physical_line in text.splitlines(keepends=True):
        content = physical_line.rstrip("\r\n")
        code = content[: _comment_index(content)]
        header = re.fullmatch(r"[ \t]*evodata[ \t]+(SPECIES_[A-Z0-9_]+)[ \t]*", code)
        if header:
            if current is not None and not current.terminated:
                raise ValueError(f"unterminated evodata block for {current.symbol}")
            symbol = header.group(1)
            if symbol in blocks:
                raise ValueError(f"duplicate evodata block for {symbol}")
            current = EvolutionBlock(symbol, [])
            blocks[symbol] = current
            offset += len(physical_line)
            continue
        if current is not None:
            terminator = re.fullmatch(r"[ \t]*terminateevodata[ \t]*", code)
            if terminator:
                if current.terminated:
                    raise ValueError(f"duplicate terminateevodata for {current.symbol}")
                current.terminated = True
                current = None
                offset += len(physical_line)
                continue
            directive = re.fullmatch(
                r"[ \t]*(evolution(?:withform)?)[ \t]+(.+?)[ \t]*", code
            )
            if directive:
                macro = directive.group(1)
                arguments = tuple(part.strip() for part in directive.group(2).split(","))
                expected = 4 if macro == "evolutionwithform" else 3
                if len(arguments) != expected or any(not part for part in arguments):
                    raise ValueError(f"malformed evolution slot for {current.symbol}")
                start = offset + directive.start(1)
                end = offset + directive.end(2)
                current.slots.append(EvolutionSlot(SourceSpan(start, end, text[start:end]), macro, arguments))
        offset += len(physical_line)
    if current is not None and not current.terminated:
        raise ValueError(f"unterminated evodata block for {current.symbol}")
    if not blocks:
        raise ValueError("evodata source contains no blocks")
    return blocks


def _parse_babymons(text: str) -> dict[str, BabyRow]:
    rows: dict[str, BabyRow] = {}
    pattern = re.compile(
        r"(?m)^[ \t]*babymon[ \t]+(SPECIES_[A-Z0-9_]+)[ \t]*,[ \t]*"
        r"(SPECIES_[A-Z0-9_]+)[ \t]*(?://.*)?$"
    )
    for match in pattern.finditer(text):
        species_symbol, baby_symbol = match.groups()
        if species_symbol in rows:
            raise ValueError(f"duplicate babymon row for {species_symbol}")
        rows[species_symbol] = BabyRow(
            species_symbol,
            SourceSpan(match.start(2), match.end(2), baby_symbol),
        )
    if not rows:
        raise ValueError("babymons source contains no rows")
    return rows


def _enabled_defines(root: Path) -> set[str]:
    text = (root / CONFIG_RELATIVE).read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return set(re.findall(r"(?m)^[ \t]*#define[ \t]+([A-Z][A-Z0-9_]*)\b", text))


def _parse_form_indexes(root: Path) -> tuple[dict[str, set[int]], dict[str, str]]:
    path = root / FORM_DATA_RELATIVE
    if not path.is_file():
        raise ValueError(f"missing form registry: {FORM_DATA_RELATIVE}")
    text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
    defined = _enabled_defines(root)
    active_stack = [True]
    current_base: str | None = None
    runtime_index = 0
    forms_by_base: dict[str, set[int]] = {}
    adjusted_to_base: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        directive = re.fullmatch(r"#(ifdef|ifndef)[ \t]+([A-Z][A-Z0-9_]*)", line)
        if directive:
            kind, name = directive.groups()
            enabled = name in defined
            active_stack.append(active_stack[-1] and (enabled if kind == "ifdef" else not enabled))
            continue
        if line.startswith("#else"):
            if len(active_stack) < 2:
                raise ValueError("orphan #else in form registry")
            active_stack[-1] = active_stack[-2] and not active_stack[-1]
            continue
        if line.startswith("#endif"):
            if len(active_stack) < 2:
                raise ValueError("orphan #endif in form registry")
            active_stack.pop()
            continue
        header = re.match(r"\[[ \t]*(SPECIES_[A-Z0-9_]+)[ \t]*\][ \t]*=[ \t]*\{", line)
        if header:
            current_base = header.group(1) if active_stack[-1] else None
            runtime_index = 0
            if current_base:
                forms_by_base.setdefault(current_base, {0})
            continue
        if current_base and line.startswith("}"):
            current_base = None
            continue
        if not current_base or not active_stack[-1]:
            continue
        for form_symbol in re.findall(r"SPECIES_[A-Z0-9_]+", line):
            runtime_index += 1
            forms_by_base[current_base].add(runtime_index)
            if form_symbol in adjusted_to_base:
                raise ValueError(f"duplicate adjusted form registration for {form_symbol}")
            adjusted_to_base[form_symbol] = current_base
    if len(active_stack) != 1:
        raise ValueError("unterminated conditional in form registry")
    for base, forms in LEGACY_FORM_FAMILIES.items():
        indexes = forms_by_base.setdefault(base, {0})
        for index, form_symbol in enumerate(forms, 1):
            indexes.add(index)
            existing = adjusted_to_base.get(form_symbol)
            if existing and existing != base:
                raise ValueError(f"form {form_symbol} belongs to multiple bases")
            adjusted_to_base[form_symbol] = base
    for base, indexes in BASE_FORM_INDEX_ALIASES.items():
        forms_by_base.setdefault(base, {0}).update(indexes)
    return forms_by_base, adjusted_to_base


def _load_index(root: Path) -> tuple[EvolutionIndex, dict[str, bytes]]:
    root = Path(root).resolve()
    paths = {
        "evolutions": (root / EVODATA_RELATIVE).resolve(),
        "babies": (root / BABYMONS_RELATIVE).resolve(),
    }
    for label, path in paths.items():
        if not path.is_file():
            raise ValueError(f"missing Pokémon {label} source: {path.relative_to(root)}")
    original = {label: path.read_bytes() for label, path in paths.items()}
    try:
        texts = {label: body.decode("utf-8") for label, body in original.items()}
    except UnicodeDecodeError as exc:
        raise ValueError("evolution sources must be valid UTF-8") from exc
    forms_by_base, adjusted_to_base = _parse_form_indexes(root)
    public_items, evolution_items = _item_domains(root / ITEM_DATA_RELATIVE)
    blocks = _parse_evodata(texts["evolutions"])
    species = _constant_symbols(root / SPECIES_RELATIVE, "SPECIES_")
    types = _constant_symbols(root / CONSTANTS_RELATIVE, "TYPE_")
    index = EvolutionIndex(
        root=root,
        paths=paths,
        texts=texts,
        blocks=blocks,
        baby_rows=_parse_babymons(texts["babies"]),
        methods=_constant_symbols(root / CONSTANTS_RELATIVE, "EVO_"),
        species=species,
        items=_constant_symbols(root / ITEMS_RELATIVE, "ITEM_"),
        moves=_constant_symbols(root / MOVES_RELATIVE, "MOVE_"),
        types=types,
        public_species={
            symbol
            for symbol in blocks
            if symbol in species and _is_public_symbol(symbol, "SPECIES_")
        },
        public_items=public_items,
        evolution_items=evolution_items,
        public_moves=_public_move_symbols(root / MOVES_RELATIVE),
        public_types={
            symbol for symbol in types if _is_public_symbol(symbol, "TYPE_")
        },
        forms_by_base=forms_by_base,
        adjusted_to_base=adjusted_to_base,
    )
    return index, original


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return value


def _validate_item_symbol(
    index: EvolutionIndex, symbol: Any, *, require_evolution_item: bool
) -> str:
    domain = index.evolution_items if require_evolution_item else index.public_items
    if not isinstance(symbol, str) or symbol not in domain:
        qualifier = "evolution-enabled " if require_evolution_item else "public "
        raise ValueError(f"item parameter must be a {qualifier}ITEM_ symbol")
    return symbol


def _validate_move_symbol(index: EvolutionIndex, symbol: Any) -> str:
    if not isinstance(symbol, str) or symbol not in index.public_moves:
        raise ValueError("move parameter must be a public, learnable MOVE_ symbol")
    return symbol


def _validate_species_symbol(index: EvolutionIndex, symbol: Any, label: str) -> str:
    if not isinstance(symbol, str) or symbol not in index.public_species:
        raise ValueError(f"{label} must be a public SPECIES_ source symbol")
    if symbol in index.adjusted_to_base:
        raise ValueError(f"{label} must use the base species symbol, not adjusted form {symbol}")
    return symbol


def _validate_form_index(index: EvolutionIndex, target_symbol: str, value: Any) -> int:
    form_index = _integer(value, "targetFormIndex", 0, 31)
    valid_indexes = index.forms_by_base.get(target_symbol)
    if valid_indexes is None or form_index not in valid_indexes:
        raise ValueError(f"unresolved target form: {target_symbol} form {form_index}")
    return form_index


def validate_evolution_item_symbol(
    root: Path, symbol: Any, *, require_evolution_item: bool = False
) -> str:
    """Validate and return a semantic item option used by an evolution method."""

    index, _ = _load_index(Path(root).resolve())
    return _validate_item_symbol(
        index, symbol, require_evolution_item=require_evolution_item
    )


def validate_evolution_move_symbol(root: Path, symbol: Any) -> str:
    """Validate and return a public move usable by EVO_HAS_MOVE."""

    index, _ = _load_index(Path(root).resolve())
    return _validate_move_symbol(index, symbol)


def validate_evolution_species_symbol(root: Path, symbol: Any) -> str:
    """Validate and return a public base species usable in evolution data."""

    index, _ = _load_index(Path(root).resolve())
    return _validate_species_symbol(index, symbol, "species")


def validate_evolution_form_target(
    root: Path, target_symbol: Any, target_form_index: Any
) -> tuple[str, int]:
    """Validate a base-species/form-index pair and return normalized values."""

    index, _ = _load_index(Path(root).resolve())
    target = _validate_species_symbol(index, target_symbol, "form target")
    return target, _validate_form_index(index, target, target_form_index)


def evolution_semantic_options(root: Path) -> dict[str, Any]:
    """Return canonical writer options and method-specific parameter domains."""

    index, _ = _load_index(Path(root).resolve())
    base_species = sorted(index.public_species - set(index.adjusted_to_base))
    methods: dict[str, dict[str, Any]] = {}
    for method in sorted(index.methods - {"EVO_NONE"}):
        if method in ZERO_PARAMETER_METHODS:
            contract: dict[str, Any] = {"parameterKind": "integer", "minimum": 0, "maximum": 0}
        elif method in LEVEL_PARAMETER_METHODS:
            contract = {"parameterKind": "level", "minimum": 0, "maximum": 100}
        elif method in BOUNDED_NUMERIC_METHODS:
            minimum, maximum = BOUNDED_NUMERIC_METHODS[method]
            contract = {"parameterKind": "integer", "minimum": minimum, "maximum": maximum}
        elif method in STONE_PARAMETER_METHODS:
            contract = {
                "parameterKind": "item",
                "options": sorted(index.evolution_items),
            }
        elif method in HELD_ITEM_PARAMETER_METHODS:
            contract = {"parameterKind": "item", "options": sorted(index.public_items)}
        elif method in MOVE_PARAMETER_METHODS:
            contract = {"parameterKind": "move", "options": sorted(index.public_moves)}
        elif method in TYPE_PARAMETER_METHODS:
            contract = {"parameterKind": "type", "options": sorted(index.public_types)}
        elif method in SPECIES_PARAMETER_METHODS:
            contract = {"parameterKind": "species", "options": base_species}
        else:
            continue
        methods[method] = contract
    return {
        "methods": methods,
        "species": base_species,
        "babySpecies": base_species,
        "forms": {
            symbol: sorted(indexes)
            for symbol, indexes in sorted(index.forms_by_base.items())
            if symbol in base_species
        },
        "logicalForms": [
            {
                "identity": f"{base_symbol}@FORM_{form_index}",
                "symbol": base_symbol,
                "adjustedSymbol": None,
                "baseSymbol": base_symbol,
                "formIndex": form_index,
                "name": BASE_FORM_INDEX_ALIAS_LABELS.get(
                    (base_symbol, form_index), f"Form {form_index}"
                ),
                "label": (
                    f"{base_symbol.removeprefix('SPECIES_').replace('_', ' ').title()} "
                    f"({BASE_FORM_INDEX_ALIAS_LABELS.get((base_symbol, form_index), f'Form {form_index}')})"
                ),
                "adjustedRecord": False,
                "logicalAlias": True,
                "enabled": True,
            }
            for base_symbol, indexes in sorted(BASE_FORM_INDEX_ALIASES.items())
            for form_index in sorted(indexes)
            if base_symbol in base_species
        ],
    }


def _parameter(index: EvolutionIndex, method: str, value: Any) -> int | str:
    label = f"{method} parameter"
    if method in ZERO_PARAMETER_METHODS:
        result = _integer(value, label, 0, 0)
    elif method in LEVEL_PARAMETER_METHODS:
        result = _integer(value, label, 0, 100)
    elif method in BOUNDED_NUMERIC_METHODS:
        minimum, maximum = BOUNDED_NUMERIC_METHODS[method]
        result = _integer(value, label, minimum, maximum)
    elif method in STONE_PARAMETER_METHODS:
        result = _validate_item_symbol(index, value, require_evolution_item=True)
    elif method in HELD_ITEM_PARAMETER_METHODS:
        result = _validate_item_symbol(index, value, require_evolution_item=False)
    elif method in MOVE_PARAMETER_METHODS:
        result = _validate_move_symbol(index, value)
    elif method in TYPE_PARAMETER_METHODS:
        if not isinstance(value, str) or value not in index.public_types:
            raise ValueError(f"{label} must be a public TYPE_ symbol")
        result = value
    elif method in SPECIES_PARAMETER_METHODS:
        result = _validate_species_symbol(index, value, label)
    else:
        raise ValueError(f"unsupported evolution method parameter contract: {method}")
    return result


def _validated_edge(
    index: EvolutionIndex,
    method: Any,
    parameter: Any,
    target_symbol: Any,
    has_form_index: bool,
    target_form_index: Any = None,
) -> EvolutionEdge:
    if not isinstance(method, str) or method not in index.methods or method == "EVO_NONE":
        raise ValueError(f"invalid evolution method: {method!r}")
    normalized_parameter = _parameter(index, method, parameter)
    target_symbol = _validate_species_symbol(index, target_symbol, "evolution target")
    form_index: int | None = None
    if has_form_index:
        form_index = _validate_form_index(index, target_symbol, target_form_index)
    return EvolutionEdge(method, normalized_parameter, target_symbol, has_form_index, form_index)


def _slot_edge(index: EvolutionIndex, slot: EvolutionSlot) -> EvolutionEdge | None:
    method, parameter, target_symbol, *form = slot.arguments
    if method == "EVO_NONE":
        if slot.macro != "evolution" or parameter != "0" or target_symbol != "SPECIES_NONE":
            raise ValueError("noncanonical EVO_NONE padding would be lost")
        return None
    if re.fullmatch(r"(?:0|[1-9][0-9]*)", parameter):
        parameter_value: int | str = int(parameter, 10)
    else:
        parameter_value = parameter
    form_value: int | None = None
    if form:
        if not re.fullmatch(r"(?:0|[1-9][0-9]*)", form[0]):
            raise ValueError("target form index uses an expression")
        form_value = int(form[0], 10)
    return _validated_edge(
        index,
        method,
        parameter_value,
        target_symbol,
        slot.macro == "evolutionwithform",
        form_value,
    )


def _block_edges(index: EvolutionIndex, block: EvolutionBlock) -> list[EvolutionEdge]:
    if not block.terminated:
        raise ValueError("missing terminateevodata")
    if len(block.slots) != MAX_EVOLUTION_SLOTS:
        raise ValueError(
            f"block has {len(block.slots)} slots; runtime requires {MAX_EVOLUTION_SLOTS}"
        )
    edges: list[EvolutionEdge] = []
    padding_started = False
    seen: set[tuple[Any, ...]] = set()
    for slot in block.slots:
        edge = _slot_edge(index, slot)
        if edge is None:
            padding_started = True
            continue
        if padding_started:
            raise ValueError("active evolution appears after EVO_NONE padding")
        if edge.key() in seen:
            raise ValueError("block contains duplicate evolution edges")
        seen.add(edge.key())
        edges.append(edge)
    return edges


def _baby_access(index: EvolutionIndex, symbol: str) -> tuple[bool, str | None]:
    if symbol not in index.public_species:
        return False, "species source is sentinel, reserved, filler, or non-public"
    row = index.baby_rows.get(symbol)
    if row is None:
        return False, "missing babymon row"
    if row.baby_span.raw not in index.species:
        return False, f"babymon target is not authoritative: {row.baby_span.raw}"
    if row.baby_span.raw not in index.blocks:
        return False, f"babymon target has no source record: {row.baby_span.raw}"
    return True, None


def _block_access(index: EvolutionIndex, symbol: str) -> tuple[bool, str | None, list[EvolutionEdge]]:
    if symbol not in index.public_species:
        return False, "species source is sentinel, reserved, filler, or non-public", []
    block = index.blocks.get(symbol)
    if block is None:
        return False, "missing evodata block", []
    try:
        edges = _block_edges(index, block)
    except ValueError as exc:
        return False, str(exc), []
    return True, None, edges


def evolution_access_matrix(root: Path) -> dict[str, dict[str, Any]]:
    index, _ = _load_index(Path(root).resolve())
    result: dict[str, dict[str, Any]] = {}
    for symbol, block in index.blocks.items():
        writable, reason, edges = _block_access(index, symbol)
        baby_writable, baby_reason = _baby_access(index, symbol)
        result[symbol] = {
            "writable": writable,
            "reason": reason,
            "capacity": MAX_EVOLUTION_SLOTS,
            "edgeCount": len(edges),
            "babyWritable": baby_writable,
            "babyReason": baby_reason,
            "physicalSlotCount": len(block.slots),
        }
    return result


def _payload_records(index: EvolutionIndex, payload: Any) -> list[UpdateRequest]:
    if not isinstance(payload, dict) or set(payload) != {"records"}:
        raise ValueError("evolution update payload must contain only records")
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise ValueError("evolution update records must be a non-empty list")
    normalized: list[UpdateRequest] = []
    seen_records: set[str] = set()
    for position, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"records[{position}] must be an object")
        unknown = set(record) - {"symbol", "edges", "babySymbol"}
        if unknown or "symbol" not in record:
            raise ValueError(f"records[{position}] has invalid keys")
        if "edges" not in record and "babySymbol" not in record:
            raise ValueError(
                f"records[{position}] must include edges, babySymbol, or both"
            )
        symbol = record["symbol"]
        if not isinstance(symbol, str) or symbol not in index.public_species:
            raise ValueError(f"unknown evolution source species: {symbol!r}")
        if symbol in seen_records:
            raise ValueError(f"duplicate evolution update record for {symbol}")
        seen_records.add(symbol)
        edges: list[EvolutionEdge] | None = None
        if "edges" in record:
            raw_edges = record["edges"]
            if not isinstance(raw_edges, list):
                raise ValueError(f"{symbol}.edges must be a list")
            if len(raw_edges) > MAX_EVOLUTION_SLOTS:
                raise ValueError(
                    f"{symbol} exceeds the {MAX_EVOLUTION_SLOTS}-edge runtime capacity"
                )
            edges = []
            seen_edges: set[tuple[Any, ...]] = set()
            for edge_position, raw_edge in enumerate(raw_edges):
                if not isinstance(raw_edge, dict):
                    raise ValueError(f"{symbol}.edges[{edge_position}] must be an object")
                unknown_edge = set(raw_edge) - {
                    "method", "parameter", "targetSymbol", "targetFormIndex"
                }
                required = {"method", "parameter", "targetSymbol"}
                if unknown_edge or not required.issubset(raw_edge):
                    raise ValueError(f"{symbol}.edges[{edge_position}] has invalid keys")
                edge = _validated_edge(
                    index,
                    raw_edge["method"],
                    raw_edge["parameter"],
                    raw_edge["targetSymbol"],
                    "targetFormIndex" in raw_edge,
                    raw_edge.get("targetFormIndex"),
                )
                if edge.key() in seen_edges:
                    raise ValueError(
                        f"{symbol} contains duplicate requested evolution edges"
                    )
                seen_edges.add(edge.key())
                edges.append(edge)
        baby_symbol = record.get("babySymbol")
        if "babySymbol" in record:
            baby_symbol = _validate_species_symbol(index, baby_symbol, "baby species")
        normalized.append(UpdateRequest(symbol, edges, baby_symbol))
    return normalized


def _base_symbol(index: EvolutionIndex, symbol: str) -> str:
    return index.adjusted_to_base.get(symbol, symbol)


def _graph_edges(index: EvolutionIndex, block: EvolutionBlock) -> list[EvolutionEdge]:
    """Read valid runtime edges without requiring the block to be rewritable."""

    edges: list[EvolutionEdge] = []
    seen: set[tuple[Any, ...]] = set()
    for slot in block.slots:
        try:
            edge = _slot_edge(index, slot)
        except ValueError:
            continue
        if edge is not None and edge.key() not in seen:
            seen.add(edge.key())
            edges.append(edge)
    return edges


def _final_family_graph(
    index: EvolutionIndex, requested: list[UpdateRequest]
) -> tuple[
    dict[str, set[str]],
    dict[str, set[str]],
    set[str],
]:
    overrides = {
        request.symbol: request.edges
        for request in requested
        if request.edges is not None
    }
    parents: dict[str, set[str]] = {}
    adjacent: dict[str, set[str]] = {}
    topology_seeds: set[str] = set()

    def connect(source: str, target: str) -> None:
        parents.setdefault(target, set()).add(source)
        parents.setdefault(source, set())
        adjacent.setdefault(source, set()).add(target)
        adjacent.setdefault(target, set()).add(source)

    for symbol, block in index.blocks.items():
        old_edges = _graph_edges(index, block)
        final_edges = overrides.get(symbol, old_edges)
        source = _base_symbol(index, symbol)
        old_targets = {_base_symbol(index, edge.target_symbol) for edge in old_edges}
        final_targets = {_base_symbol(index, edge.target_symbol) for edge in final_edges}
        if symbol in overrides and old_targets != final_targets:
            topology_seeds.add(source)
            topology_seeds.update(old_targets)
            topology_seeds.update(final_targets)
        parents.setdefault(source, set())
        adjacent.setdefault(source, set())
        for target in final_targets:
            connect(source, target)
    return parents, adjacent, topology_seeds


def _component(adjacent: dict[str, set[str]], start: str) -> set[str]:
    seen = {start}
    pending = [start]
    while pending:
        symbol = pending.pop()
        for neighbor in adjacent.get(symbol, set()):
            if neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)
    return seen


def _family_roots(parents: dict[str, set[str]], component: set[str]) -> set[str]:
    return {
        symbol
        for symbol in component
        if not (parents.get(symbol, set()) & component)
    }


def _validate_final_baby_families(
    index: EvolutionIndex, requested: list[UpdateRequest]
) -> None:
    parents, adjacent, topology_seeds = _final_family_graph(index, requested)
    baby_by_base: dict[str, str] = {}
    for symbol, row in index.baby_rows.items():
        source = _base_symbol(index, symbol)
        if symbol != source and source in index.baby_rows:
            continue
        baby_by_base[source] = _base_symbol(index, row.baby_span.raw)

    requested_baby_sources: set[str] = set()
    for request in requested:
        if request.baby_symbol is None:
            continue
        source = _base_symbol(index, request.symbol)
        baby = _base_symbol(index, request.baby_symbol)
        previous = baby_by_base.get(source)
        if source in requested_baby_sources and previous != baby:
            raise ValueError(f"conflicting baby mappings for normalized species {source}")
        requested_baby_sources.add(source)
        baby_by_base[source] = baby

    components: dict[str, tuple[set[str], set[str]]] = {}

    def family(symbol: str) -> tuple[set[str], set[str]]:
        component = _component(adjacent, symbol)
        key = min(component)
        if key not in components:
            components[key] = (component, _family_roots(parents, component))
        return components[key]

    for source in requested_baby_sources:
        component, roots = family(source)
        if len(roots) != 1:
            raise ValueError(
                f"baby family for {source} has {len(roots)} roots after evolution updates"
            )
        expected = next(iter(roots))
        if baby_by_base[source] != expected:
            raise ValueError(
                f"baby species for {source} must be final family root {expected}"
            )

    checked_components: set[str] = set()
    for seed in topology_seeds:
        component, roots = family(seed)
        key = min(component)
        if key in checked_components:
            continue
        checked_components.add(key)
        if len(roots) != 1:
            raise ValueError(
                f"evolution update creates a family with {len(roots)} baby roots"
            )
        expected = next(iter(roots))
        for member in component:
            actual = baby_by_base.get(member)
            if actual is not None and actual != expected:
                raise ValueError(
                    f"baby mapping for {member} must be updated to final family root {expected}"
                )


def _apply_replacements(text: str, replacements: list[Replacement], label: str) -> str:
    ordered = sorted(replacements, key=lambda item: (item.start, item.end))
    for left, right in zip(ordered, ordered[1:]):
        if right.start < left.end:
            raise ValueError(f"overlapping replacements in {label}")
    updated = text
    for replacement in reversed(ordered):
        updated = updated[: replacement.start] + replacement.token + updated[replacement.end :]
    return updated


def _atomic_write(path: Path, body: bytes) -> None:
    mode = path.stat().st_mode
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def apply_evolution_updates(root: Path, payload: Any) -> dict[str, Any]:
    index, original = _load_index(Path(root).resolve())
    requested = _payload_records(index, payload)
    replacements = {"evolutions": [], "babies": []}
    changed_evolution_records = 0
    changed_baby_records = 0
    changed_edge_count = 0

    for request in requested:
        symbol = request.symbol
        desired_edges = request.edges
        baby_symbol = request.baby_symbol
        edges_changed = False
        block: EvolutionBlock | None = None
        if desired_edges is not None:
            writable, reason, current_edges = _block_access(index, symbol)
            if not writable:
                raise ValueError(f"{symbol} evolution block is not writable: {reason}")
            block = index.blocks[symbol]
            edges_changed = [edge.key() for edge in desired_edges] != [
                edge.key() for edge in current_edges
            ]
        baby_changed = False
        if baby_symbol is not None:
            baby_writable, baby_reason = _baby_access(index, symbol)
            if not baby_writable:
                raise ValueError(f"{symbol} baby mapping is not writable: {baby_reason}")
            baby_changed = index.baby_rows[symbol].baby_span.raw != baby_symbol
        if not edges_changed and not baby_changed:
            raise ValueError(f"no-op evolution update for {symbol}")

        if edges_changed and desired_edges is not None and block is not None:
            desired_directives = [edge.directive() for edge in desired_edges]
            desired_directives.extend(
                ["evolution EVO_NONE, 0, SPECIES_NONE"]
                * (MAX_EVOLUTION_SLOTS - len(desired_directives))
            )
            for slot, directive in zip(block.slots, desired_directives):
                if slot.span.raw != directive:
                    replacements["evolutions"].append(
                        Replacement(slot.span.start, slot.span.end, directive)
                    )
            changed_evolution_records += 1
            changed_edge_count += len(desired_edges)
        if baby_changed and baby_symbol is not None:
            span = index.baby_rows[symbol].baby_span
            replacements["babies"].append(Replacement(span.start, span.end, baby_symbol))
            changed_baby_records += 1

    _validate_final_baby_families(index, requested)

    updated = {
        label: _apply_replacements(index.texts[label], replacements[label], label)
        for label in replacements
    }
    changed_sources = [label for label in replacements if updated[label] != index.texts[label]]
    if not changed_sources:
        raise ValueError("evolution update contains no source changes")

    # Full structural round-trip before any file replacement.
    updated_blocks = _parse_evodata(updated["evolutions"])
    updated_babies = _parse_babymons(updated["babies"])
    verification = EvolutionIndex(
        **{
            **index.__dict__,
            "texts": updated,
            "blocks": updated_blocks,
            "baby_rows": updated_babies,
        }
    )
    for request in requested:
        symbol = request.symbol
        desired_edges = request.edges
        baby_symbol = request.baby_symbol
        if desired_edges is not None:
            writable, reason, parsed_edges = _block_access(verification, symbol)
            if not writable or [edge.key() for edge in parsed_edges] != [
                edge.key() for edge in desired_edges
            ]:
                raise ValueError(
                    f"patched evolution block failed verification for {symbol}: {reason}"
                )
        if baby_symbol is not None and updated_babies[symbol].baby_span.raw != baby_symbol:
            raise ValueError(f"patched baby mapping failed verification for {symbol}")

    written: list[str] = []
    try:
        for label in changed_sources:
            _atomic_write(index.paths[label], updated[label].encode("utf-8"))
            written.append(label)
    except Exception:
        for label in reversed(written):
            _atomic_write(index.paths[label], original[label])
        raise

    return {
        "saved": True,
        "changedRecords": len(requested),
        "changedEvolutionRecords": changed_evolution_records,
        "changedBabyRecords": changed_baby_records,
        "changedEdges": changed_edge_count,
        "sourceFiles": sorted(
            index.paths[label].relative_to(index.root).as_posix() for label in changed_sources
        ),
    }
