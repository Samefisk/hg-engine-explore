"""Canonical Pokémon data adapter for the V2 workshop.

The game intentionally keeps species data in several authoritative source
files.  This module joins those sources for the UI without creating a second
database or normalising the source files on disk. The paired ``pokemon_writer``
consumes the registry paths exposed here; every value retains its source symbol
so writes can remain narrow and lossless.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable

import pokemon_writer
import pokemon_evolution_writer
import pokemon_learnset_writer
import pokemon_form_writer
import pokemon_asset_writer


POKEMON_SOURCE_RELATIVE_PATHS = (
    "armips/data/mondata.s",
    "armips/data/moves.s",
    "armips/data/evodata.s",
    "armips/data/babymons.s",
    "armips/include/constants.s",
    "asm/include/abilities.inc",
    "asm/include/items.inc",
    "asm/include/moves.inc",
    "asm/include/species.inc",
    "include/constants/species.h",
    "include/config.h",
    "src/pokemon.c",
    "data/BaseExperienceTable.c",
    "data/HiddenAbilityTable.c",
    "data/itemdata/itemdata.c",
    "data/FormToSpeciesMapping.c",
    "data/PokeFormDataTbl.c",
    "data/graphics/pokegra.mk",
    "src/field/overworld_table.c",
    "data/learnsets/learnsets.json",
)

ASSET_KINDS = {
    "00": "female-back",
    "01": "male-back",
    "02": "female-front",
    "03": "male-front",
}

# HeartGold/SoulSilver reserves 494/495 for party Egg records and 508-543 for
# empty future-species slots.  The twelve adjusted species in between are real
# runtime forms whose indices predate PokeFormDataTbl.
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

STAT_NAMES = ("hp", "attack", "defense", "speed", "specialAttack", "specialDefense")
LEARNSET_KEYS = {
    "LevelMoves": "level",
    "MachineMoves": "machine",
    "TutorMoves": "tutor",
    "EggMoves": "egg",
}

POKEMON_CAPABILITIES = {
    "accessMode": "partial-write",
    "commitEndpoint": "/api/v2/commit",
    "commitDomain": "pokemonUpdates",
    "commitDomains": {
        "fields": "pokemonUpdates",
        "evolution": "pokemonEvolutionUpdates",
        "learnsets": "pokemonLearnsetUpdates",
        "forms": "pokemonFormUpdates",
        "assets": "pokemonAssetUpdates",
    },
    "evolutionMutation": {
        "domain": "pokemonEvolutionUpdates",
        "recordKey": "symbol",
        "independentFields": {
            "edges": "pokemon[].evolutionAccess",
            "babySymbol": "pokemon[].babyAccess",
        },
        "atLeastOneFieldRequired": True,
    },
    "revisionField": "sourceRevision",
    "editorOptionsEndpoint": "/api/v2/pokemon-editor-options",
    "editorOptionsRevisionField": "optionRevision",
    "assetStagingEndpoint": "/api/v2/pokemon-assets/stage",
    "assetPreviewEndpointTemplate": "/api/v2/pokemon-assets/staged/{stagingToken}",
    "fieldValueRoot": "pokemon[].editable",
    "writableGroups": ["entry", "battle", "growth", "moves", "evolution", "forms", "assets"],
    "readOnlyGroups": [],
    "atomicWithWorkshop": True,
    "partialUpdates": True,
    "validationRules": [
        {
            "id": "ev-yield-total",
            "group": "battle",
            "pathPrefix": "battle.evYields.",
            "maximumTotal": 3,
            "message": "The six EV yields may total at most 3.",
        },
        {
            "id": "dex-entry-lines",
            "group": "entry",
            "path": "entry.dexEntry",
            "maximumLines": 3,
            "message": "The Pokédex entry supports at most three lines.",
        },
    ],
}


class PokemonDataset(dict[str, Any]):
    """Serializable dataset with revision-local parsed-source caches."""

    def __init__(self, value: dict[str, Any], *, learnsets: dict[str, Any]) -> None:
        super().__init__(value)
        self.learnsets = learnsets
        self.editor_options: dict[str, Any] | None = None
        self.editor_options_lock = threading.Lock()


def _field(
    path: str,
    label: str,
    group: str,
    component: str,
    kind: str,
    *,
    unit: str | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
    enum_source: str | None = None,
    help_text: str,
    source: str,
    required: bool = True,
    nullable: bool = False,
) -> dict[str, Any]:
    return {
        "path": path,
        "label": label,
        "group": group,
        "component": component,
        "kind": kind,
        "unit": unit,
        "min": minimum,
        "max": maximum,
        "enumSource": enum_source,
        "help": help_text,
        "source": source,
        "sourceProvenance": {"path": source, "authority": "canonical-source"},
        "writable": True,
        "required": required,
        "nullable": nullable,
    }


def field_registry() -> list[dict[str, Any]]:
    mondata = "armips/data/mondata.s"
    fields = [
        _field("entry.name", "Name", "entry", "text", "string", unit="characters", minimum=1, maximum=64, help_text="Display name written by the mondata header.", source=mondata),
        _field("entry.dexEntry", "Pokédex entry", "entry", "textarea", "string", unit="characters; max 3 lines", maximum=512, help_text="In-game Pokédex description; explicit line breaks are preserved.", source=mondata),
        _field("entry.classification", "Classification", "entry", "text", "string", unit="characters", maximum=96, help_text="Pokédex category, such as Seed Pokémon.", source=mondata),
        _field("entry.height", "Display height", "entry", "text", "string", unit="characters", maximum=32, help_text="Localized height text used by the Pokédex.", source=mondata),
        _field("entry.weight", "Display weight", "entry", "text", "string", unit="characters", maximum=32, help_text="Localized weight text used by the Pokédex.", source=mondata),
        _field("entry.genderRatio", "Gender ratio", "entry", "number", "integer", unit="raw ratio byte", minimum=0, maximum=255, help_text="Engine gender-threshold byte; use semantic presets in the UI.", source=mondata),
        _field("entry.flip", "Flip sprite", "entry", "toggle", "boolean", unit="on/off", minimum=0, maximum=1, help_text="Sets the high flip bit in colorflip.", source=mondata),
        _field("entry.bodyColor", "Body color", "entry", "select", "token", enum_source="enums.bodyColors", help_text="Pokédex body-color classification.", source=mondata),
        _field("growth.eggCycles", "Egg cycles", "growth", "number", "integer", unit="cycles", minimum=0, maximum=255, help_text="Base hatch-cycle count stored in personal data.", source=mondata),
        _field("growth.baseFriendship", "Base friendship", "growth", "number", "integer", unit="friendship", minimum=0, maximum=255, help_text="Initial friendship value.", source=mondata),
        _field("growth.growthRate", "Growth rate", "growth", "select", "token", enum_source="enums.growthRates", help_text="Experience growth-curve token.", source=mondata),
        _field("growth.eggGroups.primary", "Primary egg group", "growth", "select", "token", enum_source="enums.eggGroups", help_text="Primary breeding egg-group token.", source=mondata),
        _field("growth.eggGroups.secondary", "Secondary egg group", "growth", "select", "token", enum_source="enums.eggGroups", help_text="Secondary breeding egg-group token.", source=mondata),
    ]
    stat_labels = {
        "hp": "HP",
        "attack": "Attack",
        "defense": "Defense",
        "speed": "Speed",
        "spAttack": "Sp. Attack",
        "spDefense": "Sp. Defense",
    }
    for key, label in stat_labels.items():
        fields.append(
            _field(
                f"battle.baseStats.{key}",
                label,
                "battle",
                "stat-number",
                "integer",
                unit="base stat",
                minimum=0,
                maximum=255,
                help_text=f"{label} base stat stored in the personal record.",
                source=mondata,
            )
        )
    fields.extend(
        [
            _field("battle.catchRate", "Catch rate", "battle", "number", "integer", unit="catch value", minimum=0, maximum=255, help_text="Capture formula input stored in personal data.", source=mondata),
            _field("battle.runChance", "Run chance", "battle", "number", "integer", unit="chance value", minimum=0, maximum=255, help_text="Species flee/run chance byte.", source=mondata),
            _field("battle.baseExperience", "Base experience", "battle", "number", "integer", unit="experience", minimum=0, maximum=65535, help_text="Experience awarded for defeating this adjusted species.", source="data/BaseExperienceTable.c"),
        ]
    )
    for key, label in stat_labels.items():
        fields.append(
            _field(
                f"battle.evYields.{key}",
                f"{label} EV yield",
                "battle",
                "ev-number",
                "integer",
                unit="effort values",
                minimum=0,
                maximum=3,
                help_text="Two-bit EV yield; the six-stat total may not exceed 3.",
                source=mondata,
            )
        )
    for path, label in (("primary", "Primary type"), ("secondary", "Secondary type")):
        fields.append(_field(f"battle.types.{path}", label, "battle", "select", "token", enum_source="enums.types", help_text="Engine type token.", source=mondata))
    for path, label in (("common", "Common held item"), ("rare", "Rare held item")):
        fields.append(_field(f"battle.heldItems.{path}", label, "battle", "combobox", "token", enum_source="enums.items", help_text="Wild held-item token.", source=mondata))
    for path, label, source in (
        ("primary", "Primary ability", mondata),
        ("secondary", "Secondary ability", mondata),
        ("hidden", "Hidden ability", "data/HiddenAbilityTable.c"),
    ):
        fields.append(_field(f"battle.abilities.{path}", label, "battle", "combobox", "token", enum_source="enums.abilities", help_text="Ability token used by this adjusted species.", source=source))
    return fields


def _path_value(values: dict[str, Any], path: str) -> Any:
    current: Any = values
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_path_value(values: dict[str, Any], path: str, value: Any) -> None:
    current = values
    parts = path.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _access_reason_code(reason: str | None) -> str:
    value = reason or ""
    if " has no " in value and " directive for " in value:
        return "missing-source-directive"
    if value.startswith("missing ") and " assignment for " in value:
        return "missing-table-assignment"
    if " currently uses expression " in value:
        return "conditional-source-expression"
    return "unspecified" if not value else "other-source-constraint"


class AssetPathViolation(ValueError):
    """A graphics makefile attempted to reference outside the repository."""


@dataclass(frozen=True)
class AssetSnapshot:
    revision: str
    manifestDigest: str
    manifest: dict[int, dict[str, Path]]
    versions: dict[tuple[int, str], str]


ASSET_SNAPSHOT_LOCK = threading.Lock()
ASSET_SNAPSHOT_CACHE: dict[str, tuple[float, AssetSnapshot]] = {}
ASSET_SNAPSHOT_REFRESHES: dict[str, threading.Event] = {}
ASSET_SNAPSHOT_ERRORS: dict[str, Exception] = {}
ASSET_SNAPSHOT_TTL_SECONDS = 1.0


def source_paths(root: Path) -> tuple[Path, ...]:
    """Files whose content defines the read-only Pokémon model."""

    return tuple((root / relative).resolve() for relative in POKEMON_SOURCE_RELATIVE_PATHS)


def _strip_line_comment(line: str) -> str:
    """Remove an Armips // comment without treating // inside strings as one."""

    quoted = False
    escaped = False
    for index, character in enumerate(line[:-1]):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quoted:
            escaped = True
        elif character == '"':
            quoted = not quoted
        elif not quoted and character == "/" and line[index + 1] == "/":
            return line[:index]
    return line


def _split_arguments(value: str) -> list[str]:
    arguments: list[str] = []
    start = 0
    quoted = False
    escaped = False
    depth = 0
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quoted:
            escaped = True
        elif character == '"':
            quoted = not quoted
        elif not quoted and character in "([":
            depth += 1
        elif not quoted and character in ")]":
            depth = max(0, depth - 1)
        elif not quoted and depth == 0 and character == ",":
            arguments.append(value[start:index].strip())
            start = index + 1
    arguments.append(value[start:].strip())
    return arguments


def _string(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return raw.strip('"')
    return str(value)


def _label(symbol: str, prefix: str = "") -> str:
    value = symbol.removeprefix(prefix).replace("_", " ").strip()
    special = {"HP": "HP", "SP": "Sp.", "MR": "Mr.", "JR": "Jr."}
    words = [special.get(word, word.capitalize()) for word in value.split()]
    return " ".join(words)


def _numeric(raw: str, macros: dict[str, int]) -> int | None:
    value = raw.strip()
    if value in macros:
        return int(macros[value])
    try:
        return int(value, 0)
    except ValueError:
        return None


def _resolved_token(raw: str, macros: dict[str, int]) -> str:
    """Resolve the simple configured ternaries used by personal-data fields."""

    value = raw.strip()
    ternary = re.fullmatch(
        r"\(?\s*([A-Z][A-Z0-9_]*)\s*\)?\s*\?\s*([A-Z][A-Z0-9_]*)\s*:\s*([A-Z][A-Z0-9_]*)",
        value,
    )
    if ternary:
        condition, when_true, when_false = ternary.groups()
        return when_true if macros.get(condition, 0) else when_false
    return value


def _enum(raw: str, macros: dict[str, int], prefix: str) -> dict[str, Any]:
    symbol = _resolved_token(raw, macros)
    numeric_value = _numeric(symbol, macros)
    if symbol not in macros and numeric_value is not None:
        matching_symbols = [
            candidate
            for candidate, value in macros.items()
            if candidate.startswith(prefix) and value == numeric_value
        ]
        if len(matching_symbols) == 1:
            symbol = matching_symbols[0]
    result = {"symbol": symbol, "value": _numeric(symbol, macros), "name": _label(symbol, prefix)}
    if symbol != raw.strip():
        result["raw"] = raw.strip()
    return result


def _form_suffix(form_symbol: str, base_symbol: str) -> str:
    form_parts = form_symbol.removeprefix("SPECIES_").split("_")
    base_parts = base_symbol.removeprefix("SPECIES_").split("_")
    for part in base_parts:
        if part in form_parts:
            form_parts.remove(part)
    return _label("_".join(form_parts)) or "Form"


def _parse_mondata(path: Path, macros: dict[str, int]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for source_line in path.read_text(encoding="utf-8").splitlines():
        line = _strip_line_comment(source_line).strip()
        if not line:
            continue
        match = re.match(r"mondata\s+([^,]+),\s*(.+)$", line)
        if match:
            if current is not None:
                records.append(current)
            symbol = match.group(1).strip()
            current = {
                "id": symbol,
                "symbol": symbol,
                "value": _numeric(symbol, macros),
                "name": _string(match.group(2)),
                "sourceOrder": len(records),
                "source": {"personal": path.relative_to(path.parents[2]).as_posix()},
            }
            continue
        if current is None:
            continue
        macro_match = re.match(r"([a-z][a-z0-9]*)\s+(.+)$", line, re.IGNORECASE)
        if not macro_match:
            continue
        macro, raw_arguments = macro_match.groups()
        args = _split_arguments(raw_arguments)
        if macro == "basestats" and len(args) == 6:
            values = [_numeric(item, macros) for item in args]
            current["baseStats"] = dict(zip(STAT_NAMES, values))
            current["baseStats"]["total"] = sum(item or 0 for item in values)
        elif macro == "types" and len(args) == 2:
            current["types"] = [_enum(item, macros, "TYPE_") for item in args]
        elif macro == "catchrate":
            current["catchRate"] = _numeric(args[0], macros)
        elif macro == "baseexp":
            current["personalBaseExperience"] = _numeric(args[0], macros)
        elif macro == "evyields" and len(args) == 6:
            values = [_numeric(item, macros) for item in args]
            current["evYields"] = dict(zip(STAT_NAMES, values))
            current["evYields"]["total"] = sum(item or 0 for item in values)
        elif macro == "items" and len(args) == 2:
            current["heldItems"] = [_enum(item, macros, "ITEM_") for item in args]
        elif macro == "genderratio":
            current["genderRatio"] = _numeric(args[0], macros)
        elif macro == "eggcycles":
            current["eggCycles"] = _numeric(args[0], macros)
        elif macro == "basefriendship":
            current["baseFriendship"] = _numeric(args[0], macros)
        elif macro == "growthrate":
            current["growthRate"] = _enum(args[0], macros, "GROWTH_")
        elif macro == "egggroups" and len(args) == 2:
            current["eggGroups"] = [_enum(item, macros, "EGG_GROUP_") for item in args]
        elif macro == "abilities" and len(args) == 2:
            current["abilities"] = {
                "primary": _enum(args[0], macros, "ABILITY_"),
                "secondary": _enum(args[1], macros, "ABILITY_"),
            }
        elif macro == "runchance":
            current["runChance"] = _numeric(args[0], macros)
        elif macro == "colorflip" and len(args) == 2:
            current["bodyColor"] = _enum(args[0], macros, "BODY_COLOR_")
            current["flipSprite"] = bool(_numeric(args[1], macros))
        elif macro == "mondexentry" and len(args) >= 2:
            current.setdefault("dex", {})["entry"] = _string(args[1])
        elif macro == "mondexclassification" and len(args) >= 2:
            current.setdefault("dex", {})["classification"] = _string(args[1])
        elif macro == "mondexheight" and len(args) >= 2:
            current.setdefault("dex", {})["height"] = _string(args[1])
        elif macro == "mondexweight" and len(args) >= 2:
            current.setdefault("dex", {})["weight"] = _string(args[1])
    if current is not None:
        records.append(current)
    return records


def _parse_indexed_table(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    pattern = re.compile(r"\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=\s*([A-Z0-9_x+-]+)")
    for symbol, value in pattern.findall(path.read_text(encoding="utf-8")):
        result[symbol] = value
    return result


def _parse_form_relationships(
    root: Path, macros: dict[str, int]
) -> tuple[dict[str, str], dict[str, list[dict[str, Any]]]]:
    direct: dict[str, str] = {}
    mapping_text = (root / "data/FormToSpeciesMapping.c").read_text(encoding="utf-8")
    for form, base in re.findall(
        r"\[\s*(SPECIES_[A-Z0-9_]+)\s*-\s*SPECIES_MEGA_START\s*\]\s*=\s*(SPECIES_[A-Z0-9_]+)",
        mapping_text,
    ):
        direct[form] = base

    forms_by_base: dict[str, list[dict[str, Any]]] = {}
    form_path = root / "data/PokeFormDataTbl.c"
    form_text = re.sub(r"/\*.*?\*/", "", form_path.read_text(), flags=re.S)
    condition_stack: list[bool] = [True]
    current_base = ""
    declared_index = 0
    runtime_index = 0
    for raw_line in form_text.splitlines():
        line = raw_line.strip()
        directive = re.match(r"#(ifdef|ifndef)\s+([A-Z][A-Z0-9_]*)", line)
        if directive:
            kind, name = directive.groups()
            enabled = bool(macros.get(name, 0))
            condition_stack.append(condition_stack[-1] and (enabled if kind == "ifdef" else not enabled))
            continue
        if line.startswith("#else") and len(condition_stack) > 1:
            parent = condition_stack[-2]
            condition_stack[-1] = parent and not condition_stack[-1]
            continue
        if line.startswith("#endif"):
            if len(condition_stack) > 1:
                condition_stack.pop()
            continue
        header = re.match(r"\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=\s*\{", line)
        if header:
            current_base = header.group(1)
            declared_index = 0
            runtime_index = 0
            forms_by_base.setdefault(current_base, [])
            continue
        if not current_base:
            continue
        if line.startswith("}"):
            current_base = ""
            continue
        symbols = re.findall(r"SPECIES_[A-Z0-9_]+", line)
        for symbol in symbols:
            enabled = condition_stack[-1]
            declared_index += 1
            if enabled:
                runtime_index += 1
            metadata = {
                "symbol": symbol,
                "declaredFormIndex": declared_index,
                "formIndex": runtime_index if enabled else None,
                "enabled": enabled,
                "registered": True,
                "needsReversion": "NEEDS_REVERSION" in line,
                "source": form_path.relative_to(root).as_posix(),
            }
            forms_by_base[current_base].append(metadata)
            direct.setdefault(symbol, current_base)

    # These adjusted forms are part of the original HGSS species layout, not
    # PokeFormDataTbl. Their order is the runtime form index contract.
    legacy_source = "src/pokemon.c"
    for base, forms in LEGACY_FORM_FAMILIES.items():
        family = forms_by_base.setdefault(base, [])
        for index, symbol in enumerate(forms, 1):
            direct[symbol] = base
            family.insert(
                index - 1,
                {
                    "symbol": symbol,
                    "declaredFormIndex": index,
                    "formIndex": index,
                    "enabled": True,
                    "registered": True,
                    "needsReversion": False,
                    "legacyAdjustedSpecies": True,
                    "source": legacy_source,
                    "constantsSource": "asm/include/species.inc",
                },
            )

    known_symbols = {entry["symbol"] for family in forms_by_base.values() for entry in family}
    for form, base in direct.items():
        if form in known_symbols:
            continue
        forms_by_base.setdefault(base, []).append(
            {
                "symbol": form,
                "declaredFormIndex": None,
                "formIndex": None,
                "enabled": False,
                "registered": False,
                "needsReversion": False,
                "source": "data/FormToSpeciesMapping.c",
            }
        )

    # Reserved Alcremie fillers are related personal records, but deliberately
    # have no runtime form index. Do not shift or invent their form numbers.
    for filler in ("SPECIES_ALCREMIE_FILLER_1", "SPECIES_ALCREMIE_FILLER_2"):
        direct[filler] = "SPECIES_ALCREMIE"
        forms_by_base.setdefault("SPECIES_ALCREMIE", []).append(
            {
                "symbol": filler,
                "declaredFormIndex": None,
                "formIndex": None,
                "enabled": False,
                "registered": False,
                "needsReversion": False,
                "placeholder": True,
                "source": "asm/include/species.inc",
            }
        )
    return direct, forms_by_base


def _validate_legacy_form_map(root: Path, macros: dict[str, int]) -> None:
    """Keep the adapter's legacy families tied to the runtime switch contract."""

    source = (root / "src/pokemon.c").read_text(encoding="utf-8")
    function = re.search(
        r"int\s+LONG_CALL\s+PokeOtherFormMonsNoGet\s*\([^)]*\)\s*\{(.*?)\n\}",
        source,
        re.S,
    )
    if not function:
        raise RuntimeError("could not find PokeOtherFormMonsNoGet in src/pokemon.c")
    body = function.group(1)
    for base, forms in LEGACY_FORM_FAMILIES.items():
        case = re.search(
            rf"case\s+{re.escape(base)}\s*:(.*?)(?=\n\s*case\s+SPECIES_|\n\s*default\s*:)",
            body,
            re.S,
        )
        if not case:
            raise RuntimeError(f"legacy form runtime case missing for {base}")
        limit = re.search(r"form_no\s*<=\s*(\d+)", case.group(1))
        offset = re.search(r"mons_no\s*=\s*(\d+)\s*\+\s*form_no", case.group(1))
        if not limit or not offset or int(limit.group(1)) != len(forms):
            raise RuntimeError(f"legacy form count disagrees with runtime for {base}")
        for index, symbol in enumerate(forms, 1):
            expected = int(offset.group(1)) + index
            if macros.get(symbol) != expected:
                raise RuntimeError(
                    f"legacy form id disagrees with runtime: {symbol} "
                    f"is {macros.get(symbol)}, expected {expected}"
                )


def _evolution_parameter(raw: str, macros: dict[str, int]) -> dict[str, Any]:
    try:
        return {"raw": raw, "value": int(raw, 0), "kind": "number", "symbol": None, "name": raw}
    except ValueError:
        pass
    prefix_and_kind = next(
        (
            (prefix, kind)
            for prefix, kind in (
                ("ITEM_", "item"),
                ("MOVE_", "move"),
                ("TYPE_", "type"),
                ("SPECIES_", "species"),
            )
            if raw.startswith(prefix)
        ),
        ("", "expression"),
    )
    prefix, kind = prefix_and_kind
    value = macros.get(raw)
    parameter: dict[str, Any] = {
        "raw": raw,
        "value": value,
        "kind": kind,
        "symbol": raw,
        "name": _label(raw, prefix),
    }
    if value is None:
        parameter["diagnostic"] = {
            "code": "unknown-evolution-parameter",
            "severity": "warning",
            "message": f"Could not resolve evolution parameter {raw}",
        }
    return parameter


def _parse_evolutions(path: Path, macros: dict[str, int]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    current = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = _strip_line_comment(raw_line).strip()
        header = re.match(r"evodata\s+(SPECIES_[A-Z0-9_]+)", line)
        if header:
            current = header.group(1)
            result.setdefault(current, [])
            continue
        edge = re.match(r"evolution(withform)?\s+(.+)$", line)
        if not current or not edge:
            continue
        args = _split_arguments(edge.group(2))
        if len(args) < 3 or args[0] == "EVO_NONE" or args[2] == "SPECIES_NONE":
            continue
        parameter_raw = args[1]
        item: dict[str, Any] = {
            "method": {
                "symbol": args[0],
                "value": macros.get(args[0]),
                "name": _label(args[0], "EVO_"),
            },
            "parameter": _evolution_parameter(parameter_raw, macros),
            "targetBaseSymbol": args[2],
            "targetSymbol": args[2],
            "source": path.as_posix(),
        }
        if edge.group(1) and len(args) >= 4:
            item["targetFormIndex"] = int(args[3], 0) if re.fullmatch(r"\d+", args[3]) else args[3]
        result[current].append(item)
    return result


def _parse_baby_species(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    pattern = re.compile(
        r"^\s*babymon\s+(SPECIES_[A-Z0-9_]+)\s*,\s*(SPECIES_[A-Z0-9_]+)",
        re.MULTILINE,
    )
    for symbol, baby_symbol in pattern.findall(path.read_text(encoding="utf-8")):
        if symbol in result:
            raise ValueError(f"duplicate babymon row for {symbol}")
        result[symbol] = baby_symbol
    if not result:
        raise ValueError("babymons source contains no rows")
    return result


def safe_repo_path(root: Path, candidate: Path, *, must_exist: bool = False) -> Path:
    """Validate a source path before callers inspect, hash, or serve it.

    Lexical traversal, symlinked components, and resolved paths outside the
    repository are rejected. Missing in-repo assets are allowed when parsing a
    manifest so availability can be represented without touching the path.
    """

    root_lexical = Path(os.path.abspath(root))
    candidate_lexical = Path(
        os.path.abspath(candidate if candidate.is_absolute() else root_lexical / candidate)
    )
    try:
        relative = candidate_lexical.relative_to(root_lexical)
    except ValueError as exc:
        raise AssetPathViolation(f"asset path escapes repository: {candidate}") from exc
    cursor = root_lexical
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise AssetPathViolation(f"symlinked asset path is not allowed: {candidate}")
        if not cursor.exists():
            break
    try:
        resolved = candidate_lexical.resolve(strict=must_exist)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise AssetPathViolation(f"invalid repository asset path: {candidate}") from exc
    if must_exist and not resolved.is_file():
        raise AssetPathViolation(f"asset is not a regular file: {candidate}")
    return resolved


def _parse_graphics_text(text: str, root: Path) -> dict[int, dict[str, Path]]:
    result: dict[int, dict[str, Path]] = {}
    for line in text.splitlines():
        icon = re.search(r"build/pokemonicon/1_(\d+)\.NCGR:\s+([^\s]+/icon\.png)", line)
        if icon:
            result.setdefault(int(icon.group(1)), {})["icon"] = safe_repo_path(
                root, root / icon.group(2)
            )
            continue
        sprite = re.search(r"build/pokemonpic/(\d+)-([0-3][0-9])\.NCGR:\s+([^\s]+\.png)", line)
        if sprite and sprite.group(2) in ASSET_KINDS:
            result.setdefault(int(sprite.group(1)), {})[
                ASSET_KINDS[sprite.group(2)]
            ] = safe_repo_path(root, root / sprite.group(3))
    return result


@lru_cache(maxsize=8)
def _cached_graphics(root_value: str, makefile_sha256: str) -> dict[int, dict[str, Path]]:
    root = Path(root_value)
    text = (root / "data/graphics/pokegra.mk").read_text(encoding="utf-8")
    # The digest participates in the cache key; verifying it here catches an
    # accidental caller mismatch rather than returning a stale manifest.
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != makefile_sha256:
        return graphics_manifest(root)
    return _parse_graphics_text(text, root)


def graphics_manifest(root: Path) -> dict[int, dict[str, Path]]:
    makefile = root / "data/graphics/pokegra.mk"
    body = makefile.read_bytes()
    return _cached_graphics(str(root.resolve()), hashlib.sha256(body).hexdigest())


def graphics_manifest_digest(root: Path) -> str:
    makefile = safe_repo_path(root, root / "data/graphics/pokegra.mk", must_exist=True)
    return hashlib.sha256(makefile.read_bytes()).hexdigest()


@lru_cache(maxsize=16384)
def _cached_file_digest(
    path_value: str,
    device: int,
    inode: int,
    size: int,
    mtime_ns: int,
    ctime_ns: int,
) -> str:
    del device, inode, size, mtime_ns, ctime_ns
    return hashlib.sha256(Path(path_value).read_bytes()).hexdigest()


def file_digest(root: Path, path: Path) -> str:
    validated = safe_repo_path(root, path, must_exist=True)
    for _ in range(3):
        before = validated.stat()
        identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        digest = _cached_file_digest(str(validated), *identity)
        after = validated.stat()
        if identity == (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            return digest
    raise RuntimeError(f"asset changed repeatedly while hashing: {validated.relative_to(root)}")


def _compute_asset_snapshot(root: Path, manifest_digest: str) -> AssetSnapshot:
    current_manifest_digest = graphics_manifest_digest(root)
    if current_manifest_digest != manifest_digest:
        manifest_digest = current_manifest_digest
    manifest = {
        species_value: dict(entries)
        for species_value, entries in _cached_graphics(
            str(root.resolve()), manifest_digest
        ).items()
    }
    species_values = pokemon_asset_writer.species_values(root)
    for symbol, follower_path in pokemon_asset_writer.follower_manifest(root).items():
        species_value = species_values.get(symbol)
        if species_value is not None:
            manifest.setdefault(species_value, {})["follower"] = follower_path
    entries: list[str] = []
    versions: dict[tuple[int, str], str] = {}
    for species_value, asset_entries in sorted(manifest.items()):
        for kind, candidate in sorted(asset_entries.items()):
            path = safe_repo_path(root, candidate)
            relative = path.relative_to(root.resolve()).as_posix()
            effective = path
            raw_state = "missing"
            raw_digest = "missing"
            if path.is_file():
                raw_digest = file_digest(root, path)
                raw_state = "empty" if path.stat().st_size == 0 else "explicit"
            fallback_marker = "direct"
            if path.is_file() and path.stat().st_size == 0 and kind.startswith("male-"):
                fallback = asset_entries.get(kind.replace("male-", "female-"))
                if fallback is not None and fallback.is_file() and fallback.stat().st_size:
                    effective = safe_repo_path(root, fallback, must_exist=True)
                    fallback_marker = (
                        "fallback:" + effective.relative_to(root.resolve()).as_posix()
                    )
            effective_digest = (
                file_digest(root, effective) if effective.is_file() else "missing"
            )
            if effective_digest != "missing":
                versions[(species_value, kind)] = effective_digest
            entries.append(
                f"{species_value}\0{kind}\0{relative}\0{raw_state}\0{raw_digest}"
                f"\0{fallback_marker}\0{effective_digest}\n"
            )
    revision = f"sha256:{hashlib.sha256(''.join(entries).encode('utf-8')).hexdigest()}"
    if graphics_manifest_digest(root) != manifest_digest:
        raise RuntimeError("graphics manifest changed while asset snapshot was assembled")
    return AssetSnapshot(
        revision=revision,
        manifestDigest=manifest_digest,
        manifest=manifest,
        versions=versions,
    )


def _store_asset_snapshot(root_key: str, snapshot: AssetSnapshot) -> None:
    ASSET_SNAPSHOT_CACHE[root_key] = (
        time.monotonic() + ASSET_SNAPSHOT_TTL_SECONDS,
        snapshot,
    )
    ASSET_SNAPSHOT_ERRORS.pop(root_key, None)


def _refresh_asset_snapshot(
    root: Path, root_key: str, manifest_digest: str, completed: threading.Event
) -> None:
    try:
        snapshot = _compute_asset_snapshot(root, manifest_digest)
        with ASSET_SNAPSHOT_LOCK:
            _store_asset_snapshot(root_key, snapshot)
    except Exception as exc:  # surfaced by force refresh; stale snapshot remains coherent
        with ASSET_SNAPSHOT_LOCK:
            ASSET_SNAPSHOT_ERRORS[root_key] = exc
            cached = ASSET_SNAPSHOT_CACHE.get(root_key)
            if cached is not None:
                ASSET_SNAPSHOT_CACHE[root_key] = (
                    time.monotonic() + ASSET_SNAPSHOT_TTL_SECONDS,
                    cached[1],
                )
    finally:
        with ASSET_SNAPSHOT_LOCK:
            ASSET_SNAPSHOT_REFRESHES.pop(root_key, None)
            completed.set()


def asset_snapshot(root: Path, *, force: bool = False) -> AssetSnapshot:
    """Return a coherent asset view and refresh expired views without blocking.

    The first request and explicit ``force=True`` validation are synchronous.
    Once a coherent snapshot exists, expiry or a manifest digest change starts
    at most one daemon refresh while callers continue using that snapshot.
    """

    root = root.resolve()
    root_key = str(root)
    manifest_digest = graphics_manifest_digest(root)
    while True:
        launch_background = False
        compute_synchronously = False
        wait_for: threading.Event | None = None
        with ASSET_SNAPSHOT_LOCK:
            cached = ASSET_SNAPSHOT_CACHE.get(root_key)
            refresh = ASSET_SNAPSHOT_REFRESHES.get(root_key)
            current = cached[1] if cached is not None else None
            expired = cached is None or time.monotonic() >= cached[0]
            manifest_changed = current is not None and current.manifestDigest != manifest_digest

            if force:
                if refresh is not None:
                    wait_for = refresh
                else:
                    refresh = threading.Event()
                    ASSET_SNAPSHOT_REFRESHES[root_key] = refresh
                    compute_synchronously = True
            elif current is None:
                if refresh is not None:
                    wait_for = refresh
                else:
                    refresh = threading.Event()
                    ASSET_SNAPSHOT_REFRESHES[root_key] = refresh
                    compute_synchronously = True
            elif expired or manifest_changed:
                if refresh is None:
                    refresh = threading.Event()
                    ASSET_SNAPSHOT_REFRESHES[root_key] = refresh
                    launch_background = True
                else:
                    return current
                result = current
            else:
                return current

        if wait_for is not None:
            wait_for.wait()
            with ASSET_SNAPSHOT_LOCK:
                error = ASSET_SNAPSHOT_ERRORS.get(root_key)
                cached = ASSET_SNAPSHOT_CACHE.get(root_key)
            if force and error is not None:
                raise error
            if cached is not None:
                return cached[1]
            continue
        if compute_synchronously:
            assert refresh is not None
            _refresh_asset_snapshot(root, root_key, manifest_digest, refresh)
            with ASSET_SNAPSHOT_LOCK:
                error = ASSET_SNAPSHOT_ERRORS.get(root_key)
                cached = ASSET_SNAPSHOT_CACHE.get(root_key)
            if error is not None:
                raise error
            if cached is None:  # defensive: refresh always stores or records an error
                raise RuntimeError("asset snapshot refresh produced no result")
            return cached[1]
        if launch_background:
            assert refresh is not None
            threading.Thread(
                target=_refresh_asset_snapshot,
                args=(root, root_key, manifest_digest, refresh),
                name="pokemon-asset-refresh",
                daemon=True,
            ).start()
            return result


def asset_revision(root: Path) -> str:
    return asset_snapshot(root).revision


def invalidate_asset_snapshot(root: Path) -> None:
    """Discard cached binary metadata after an asset write or rollback."""

    root_key = str(Path(root).resolve())
    with ASSET_SNAPSHOT_LOCK:
        ASSET_SNAPSHOT_CACHE.pop(root_key, None)
        ASSET_SNAPSHOT_ERRORS.pop(root_key, None)
    _cached_file_digest.cache_clear()


def asset_path(root: Path, species_value: int, kind: str) -> Path | None:
    """Resolve an allow-listed source PNG; callers never provide a filesystem path."""

    if kind not in {"icon", "follower", *ASSET_KINDS.values()}:
        return None
    if kind == "follower":
        symbol = next(
            (
                symbol
                for symbol, value in pokemon_asset_writer.species_values(root).items()
                if value == species_value
            ),
            None,
        )
        path = (
            pokemon_asset_writer.follower_manifest(root).get(symbol)
            if symbol
            else None
        )
    else:
        path = graphics_manifest(root).get(species_value, {}).get(kind)
    if path is None:
        return None
    try:
        path = safe_repo_path(root, path, must_exist=True)
        if path.stat().st_size == 0 and kind.startswith("male-"):
            fallback = graphics_manifest(root).get(species_value, {}).get(
                kind.replace("male-", "female-")
            )
            if fallback is not None:
                path = safe_repo_path(root, fallback, must_exist=True)
    except AssetPathViolation:
        return None
    return path


def _enum_list(
    symbols: Iterable[str],
    macros: dict[str, int],
    prefix: str,
    *,
    include_all: bool = False,
) -> list[dict[str, Any]]:
    unique = set(symbols)
    if include_all:
        unique.update(symbol for symbol in macros if symbol.startswith(prefix))
    return sorted(
        (_enum(symbol, macros, prefix) for symbol in unique),
        key=lambda item: (item["value"] is None, item["value"] or 0, item["symbol"]),
    )


def _national_dex_number(species_id: int | None) -> int | None:
    if species_id is None:
        return None
    if 1 <= species_id <= 493:
        return species_id
    if 544 <= species_id <= 1075:
        return species_id - 50
    return None


def _exclusion_reason(record: dict[str, Any]) -> str | None:
    symbol = record["symbol"]
    if symbol == "SPECIES_NONE":
        return "sentinel"
    if symbol in {"SPECIES_EGG", "SPECIES_BAD_EGG"}:
        return "party-placeholder"
    if re.fullmatch(r"SPECIES_\d+", symbol):
        return "reserved-slot"
    if record.get("isPlaceholder"):
        return "form-placeholder"
    return None


def _normalised_learnset(
    learnsets: dict[str, Any], symbol: str, base_symbol: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    symbol_alias = pokemon_learnset_writer.SPECIES_TABLE_ALIASES.get(symbol)
    base_alias = pokemon_learnset_writer.SPECIES_TABLE_ALIASES.get(base_symbol)
    source_symbol = next(
        (
            candidate
            for candidate in (symbol, symbol_alias, base_symbol, base_alias)
            if candidate and candidate in learnsets
        ),
        None,
    )
    raw = learnsets.get(source_symbol, {}) if source_symbol else {}
    provenance = (
        "explicit"
        if source_symbol in {symbol, symbol_alias}
        else ("inherited" if source_symbol else "missing")
    )
    counts = {label: len(raw.get(key, [])) for key, label in LEARNSET_KEYS.items()}
    summary = {"provenance": provenance, "sourceSymbol": source_symbol, "counts": counts}

    def move(symbol_value: str) -> dict[str, str]:
        return {"symbol": symbol_value, "name": _label(symbol_value, "MOVE_")}

    detail = {
        "provenance": provenance,
        "sourceSymbol": source_symbol,
        "levelMoves": [
            {"level": int(entry["Level"]), "move": move(str(entry["Move"]))}
            for entry in raw.get("LevelMoves", [])
        ],
        "machineMoves": [move(str(value)) for value in raw.get("MachineMoves", [])],
        "tutorMoves": [move(str(value)) for value in raw.get("TutorMoves", [])],
        "eggMoves": [move(str(value)) for value in raw.get("EggMoves", [])],
        "source": "data/learnsets/learnsets.json",
    }
    return summary, detail


def _evolution_families(records: list[dict[str, Any]]) -> None:
    public_by_symbol = {record["symbol"]: record for record in records}
    adjacency: dict[str, set[str]] = {record["baseSymbol"]: set() for record in records}
    incoming_bases: set[str] = set()
    for record in records:
        source = record["baseSymbol"]
        for edge in record.get("evolutions", []):
            target_record = public_by_symbol.get(edge["targetSymbol"])
            target = target_record["baseSymbol"] if target_record else edge["targetBaseSymbol"]
            if target in adjacency:
                adjacency[source].add(target)
                adjacency[target].add(source)
                incoming_bases.add(target)

    family_by_base: dict[str, dict[str, Any]] = {}
    visited: set[str] = set()
    for starting in adjacency:
        if starting in visited:
            continue
        stack = [starting]
        component: list[str] = []
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            stack.extend(adjacency[node] - visited)
        component.sort(key=lambda symbol: public_by_symbol.get(symbol, {}).get("nationalDexNumber") or 99999)
        roots = [symbol for symbol in component if symbol not in incoming_bases]
        identity = hashlib.sha1("\0".join(component).encode("utf-8")).hexdigest()[:12]
        family = {"id": f"evolution:{identity}", "baseSymbols": component, "rootSymbols": roots}
        for symbol in component:
            family_by_base[symbol] = family
    for record in records:
        record["evolutionFamily"] = family_by_base.get(record["baseSymbol"])


def _build_detail_editor_options(
    root: Path, legacy: ModuleType, dataset: dict[str, Any]
) -> dict[str, Any]:
    macros = legacy.evaluate_armips_equ(
        [
            root / "armips/include/constants.s",
            root / "asm/include/species.inc",
            root / "asm/include/items.inc",
            root / "asm/include/moves.inc",
        ]
    )
    accepted_learnset_moves = set(pokemon_learnset_writer.accepted_move_symbols(root))
    move_types: dict[str, str] = {}
    current_move: str | None = None
    for raw_line in (root / "armips/data/moves.s").read_text(encoding="utf-8").splitlines():
        move_match = re.match(r"\s*movedata\s+(MOVE_[A-Z0-9_]+)\s*,", raw_line)
        if move_match:
            current_move = move_match.group(1)
            continue
        type_match = re.match(r"\s*type\s+(TYPE_[A-Z0-9_]+)\b", raw_line)
        if current_move and type_match:
            move_types[current_move] = type_match.group(1)
            current_move = None
    learnset_moves = []
    for option in _enum_list((), macros, "MOVE_", include_all=True):
        if option["symbol"] not in accepted_learnset_moves:
            continue
        type_symbol = move_types.get(option["symbol"], "TYPE_NORMAL")
        learnset_moves.append(
            {
                **option,
                "typeSymbol": type_symbol,
                "type": _label(type_symbol, "TYPE_"),
            }
        )
    semantic = pokemon_evolution_writer.evolution_semantic_options(root)
    method_schemas: list[dict[str, Any]] = []
    enum_sources = {
        "item": "evolutionOptions.items",
        "move": "evolutionOptions.moves",
        "type": "evolutionOptions.types",
        "species": "evolutionOptions.species",
    }
    for symbol, contract in sorted(
        semantic["methods"].items(),
        key=lambda item: (macros.get(item[0], 99999), item[0]),
    ):
        parameter_kind = contract["parameterKind"]
        minimum = contract.get("minimum")
        maximum = contract.get("maximum")
        if parameter_kind == "integer" and minimum == maximum == 0:
            parameter = {
                "kind": "fixed",
                "value": 0,
                "min": 0,
                "max": 0,
                "enumSource": None,
            }
        elif parameter_kind in {"integer", "level"}:
            parameter = {
                "kind": "integer",
                "min": minimum,
                "max": maximum,
                "unit": "level" if parameter_kind == "level" else "value",
                "enumSource": None,
            }
        else:
            parameter = {
                "kind": "token",
                "min": None,
                "max": None,
                "enumSource": enum_sources[parameter_kind],
                "optionSymbols": contract.get("options", []),
            }
        method_schemas.append(
            {
                "symbol": symbol,
                "value": macros.get(symbol),
                "name": _label(symbol, "EVO_"),
                "parameter": parameter,
            }
        )
    canonical_species = set(semantic["species"])
    logical_forms_by_base: dict[str, list[dict[str, Any]]] = {}
    for logical_form in semantic.get("logicalForms", []):
        logical_forms_by_base.setdefault(logical_form["baseSymbol"], []).append(logical_form)
    species_options: list[dict[str, Any]] = []
    for record in dataset["pokemon"]:
        if record["isForm"] or record["symbol"] not in canonical_species:
            continue
        base_symbol = record["symbol"]
        actual_forms = [
            {
                "identity": f"{base_symbol}@FORM_{form['formIndex']}",
                "symbol": form["symbol"],
                "adjustedSymbol": form["symbol"],
                "baseSymbol": base_symbol,
                "formIndex": form["formIndex"],
                "name": form["name"],
                "label": form["name"],
                "adjustedRecord": True,
                "logicalAlias": False,
                "enabled": form.get("enabled", True),
            }
            for form in record.get("forms", [])
            if form.get("formIndex") is not None
        ]
        species_options.append(
            {
                "identity": base_symbol,
                "symbol": base_symbol,
                "baseSymbol": base_symbol,
                "formIndex": 0,
                "speciesId": record["speciesId"],
                "nationalDexNumber": record["nationalDexNumber"],
                "name": record["name"],
                "label": record["name"],
                "forms": actual_forms + logical_forms_by_base.get(base_symbol, []),
            }
        )
    enum_by_symbol = {
        key: {option["symbol"]: option for option in dataset["enums"][key]}
        for key in ("items", "types")
    }
    option_symbols: dict[str, set[str]] = {"item": set(), "move": set(), "type": set()}
    for contract in semantic["methods"].values():
        kind = contract["parameterKind"]
        if kind in option_symbols:
            option_symbols[kind].update(contract.get("options", ()))

    def canonical_enum(kind: str, dataset_key: str) -> list[dict[str, Any]]:
        known = enum_by_symbol[dataset_key]
        return [
            known.get(symbol)
            or {"symbol": symbol, "value": macros.get(symbol), "name": _label(symbol)}
            for symbol in sorted(option_symbols[kind], key=lambda item: (macros.get(item, 99999), item))
        ]

    return {
        "learnsetMoves": learnset_moves,
        "moves": [
            {"symbol": symbol, "value": macros.get(symbol), "name": _label(symbol, "MOVE_")}
            for symbol in sorted(option_symbols["move"], key=lambda item: (macros.get(item, 99999), item))
        ],
        "evolutionMethods": method_schemas,
        "items": canonical_enum("item", "items"),
        "types": canonical_enum("type", "types"),
        "species": species_options,
        "babySpecies": species_options,
        "forms": semantic["forms"],
        "maxEvolutionEdges": pokemon_evolution_writer.MAX_EVOLUTION_SLOTS,
    }


def _detail_editor_options(
    root: Path, legacy: ModuleType, dataset: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(dataset, PokemonDataset):
        return _build_detail_editor_options(root, legacy, dataset)
    with dataset.editor_options_lock:
        if dataset.editor_options is None:
            dataset.editor_options = _build_detail_editor_options(root, legacy, dataset)
        return dataset.editor_options


def build_editor_options(
    root: Path,
    legacy: ModuleType,
    *,
    assets: AssetSnapshot | None = None,
    dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the shared, revision-scoped catalog used by every detail editor."""

    dataset = dataset or build_dataset(root, legacy, assets=assets)
    editor_options = _detail_editor_options(root, legacy, dataset)
    return {
        "apiVersion": 2,
        "assetRevision": dataset["assetRevision"],
        "moveOptions": editor_options["learnsetMoves"],
        "evolutionOptions": {
            key: value
            for key, value in editor_options.items()
            if key != "learnsetMoves"
        },
    }


def build_dataset(
    root: Path,
    legacy: ModuleType,
    *,
    assets: AssetSnapshot | None = None,
    validate_writable: bool = False,
) -> dict[str, Any]:
    """Join all authoritative Pokémon sources into one normalized snapshot."""

    macros = legacy.evaluate_armips_equ(
        [
            root / "armips/include/config.s",
            root / "armips/include/constants.s",
            root / "asm/include/species.inc",
            root / "asm/include/abilities.inc",
            root / "asm/include/items.inc",
            root / "asm/include/moves.inc",
        ]
    )
    config_text = (root / "include/config.h").read_text(encoding="utf-8")
    for name, raw_value in re.findall(
        r"^\s*#define\s+([A-Z][A-Z0-9_]*)(?:\s+([^/\s]+))?", config_text, re.MULTILINE
    ):
        if not raw_value:
            macros[name] = 1
        else:
            try:
                macros[name] = int(raw_value, 0)
            except ValueError:
                pass
    _validate_legacy_form_map(root, macros)
    records = _parse_mondata(root / "armips/data/mondata.s", macros)
    by_symbol = {record["symbol"]: record for record in records}
    base_exp = _parse_indexed_table(root / "data/BaseExperienceTable.c")
    hidden_abilities = _parse_indexed_table(root / "data/HiddenAbilityTable.c")
    access_matrix = pokemon_writer.field_access_matrix(root)
    evolution_access_matrix = pokemon_evolution_writer.evolution_access_matrix(root)
    learnset_access_matrix = pokemon_learnset_writer.learnset_access_matrix(root)
    form_access_matrix = pokemon_form_writer.form_access_matrix(root)
    asset_access_matrix = pokemon_asset_writer.asset_access_matrix(
        root, [record["symbol"] for record in records]
    )
    baby_species = _parse_baby_species(root / "armips/data/babymons.s")
    direct_base, forms_by_base = _parse_form_relationships(root, macros)
    evolutions = _parse_evolutions(root / "armips/data/evodata.s", macros)
    learnsets = json.loads((root / "data/learnsets/learnsets.json").read_text(encoding="utf-8"))
    asset_data = assets or asset_snapshot(root)
    graphics = asset_data.manifest
    graphics_revision = asset_data.revision

    type_symbols: set[str] = set()
    ability_symbols: set[str] = set()
    item_symbols: set[str] = set()
    growth_symbols: set[str] = set()
    egg_symbols: set[str] = set()
    color_symbols: set[str] = set()
    evo_symbols: set[str] = set()

    for record in records:
        symbol = record["symbol"]
        value = record.get("value")
        base_symbol = direct_base.get(symbol, symbol)
        base_record = by_symbol.get(base_symbol)
        forms = forms_by_base.get(base_symbol, [])
        form_metadata = next((entry for entry in forms if entry["symbol"] == symbol), None)
        is_form = base_symbol != symbol
        record["order"] = record["sourceOrder"]
        record["speciesId"] = value
        record["baseSymbol"] = base_symbol
        record["baseSpeciesId"] = base_record.get("value") if base_record else value
        # Compatibility alias: value is always the internal adjusted-species id,
        # never a Pokédex number.
        record["baseValue"] = record["baseSpeciesId"]
        record["isForm"] = is_form
        record["formIndex"] = form_metadata.get("formIndex") if form_metadata else (0 if not is_form else None)
        record["formMetadata"] = form_metadata or {
            "symbol": symbol,
            "formIndex": 0,
            "declaredFormIndex": 0,
            "enabled": True,
            "registered": True,
            "needsReversion": False,
            "source": "armips/data/mondata.s",
        }
        record["isPlaceholder"] = bool(record["formMetadata"].get("placeholder"))
        record["nationalDexNumber"] = _national_dex_number(record["baseSpeciesId"])
        record["dexNumber"] = record["nationalDexNumber"]
        record["sourceName"] = record.get("name")
        if record.get("name") in {"", "-----"}:
            base_name = (base_record or {}).get("name")
            suffix = _form_suffix(symbol, base_symbol) if is_form else symbol.removeprefix("SPECIES_")
            record["name"] = f"{base_name} ({_label(suffix)})" if base_name and is_form else _label(symbol, "SPECIES_")

        table_symbol = pokemon_writer.SPECIES_TABLE_ALIASES.get(symbol, symbol)
        base_exp_raw = base_exp.get(table_symbol)
        record["baseExperience"] = _numeric(base_exp_raw, macros) if base_exp_raw else record.get("personalBaseExperience")
        hidden_raw = hidden_abilities.get(table_symbol, "ABILITY_NONE")
        record.setdefault("abilities", {})["hidden"] = _enum(hidden_raw, macros, "ABILITY_")
        record["evolutions"] = evolutions.get(symbol, [])
        record["babySymbol"] = baby_species.get(symbol)
        evolution_access = evolution_access_matrix.get(symbol) or {
            "writable": False,
            "reason": "missing evodata block",
            "capacity": pokemon_evolution_writer.MAX_EVOLUTION_SLOTS,
            "edgeCount": len(record["evolutions"]),
            "babyWritable": False,
            "babyReason": "missing babymon row",
            "physicalSlotCount": 0,
        }
        record["evolutionAccess"] = {
            key: evolution_access[key]
            for key in ("writable", "reason", "capacity", "edgeCount", "physicalSlotCount")
        }
        record["evolutionAccess"].update(
            {"commitDomain": "pokemonEvolutionUpdates", "payloadField": "edges"}
        )
        record["babyAccess"] = {
            "writable": evolution_access["babyWritable"],
            "reason": evolution_access["babyReason"],
            "commitDomain": "pokemonEvolutionUpdates",
            "payloadField": "babySymbol",
        }
        family_forms = forms_by_base.get(base_symbol, [])
        base_display_name = (base_record or {}).get("name") or _label(base_symbol, "SPECIES_")
        record["forms"] = [
            {
                **metadata,
                "value": macros.get(metadata["symbol"]),
                "speciesId": macros.get(metadata["symbol"]),
                "nationalDexNumber": record["nationalDexNumber"],
                "name": (
                    by_symbol.get(metadata["symbol"], {}).get("name")
                    if by_symbol.get(metadata["symbol"], {}).get("name") not in {None, "", "-----"}
                    else f"{base_display_name} ({_form_suffix(metadata['symbol'], base_symbol)})"
                ),
            }
            for metadata in family_forms
        ]
        form_access = form_access_matrix.get(base_symbol) or {
            "writable": False,
            "reason": "base species has no source-backed form registry block",
            "source": record["formMetadata"]["source"],
            "fields": {
                "declaredFormIndex": {"writable": False, "reason": "not source-backed by PokeFormDataTbl"},
                "enabled": {"writable": False, "reason": "derived from compile-time configuration"},
                "needsReversion": {"writable": False, "reason": "not source-backed by PokeFormDataTbl"},
            },
            "formCount": len(record["forms"]),
            "maxForms": pokemon_form_writer.MAX_FORMS,
        }
        record["formAccess"] = {
            **form_access,
            "writable": bool(form_access["writable"] and not is_form),
            "reason": (
                form_access["reason"]
                if not form_access["writable"]
                else ("edit forms from the canonical base record" if is_form else None)
            ),
            "commitDomain": "pokemonFormUpdates",
        }

        record["learnsetSummary"], _ = _normalised_learnset(learnsets, symbol, base_symbol)
        record["learnsetAccess"] = learnset_access_matrix.get(symbol) or {
            "writable": False,
            "reason": "species is missing from learnset writer access matrix",
            "provenance": "missing",
            "sourceSymbol": None,
            "materializationRequired": False,
            "canMaterialize": False,
            "canReturnToInheritance": False,
            "sections": {
                key: {"writable": False, "reason": "species is unavailable", "diagnostics": []}
                for key in pokemon_learnset_writer.PAYLOAD_SECTION_KEYS
            },
        }

        asset_entries: dict[str, Any] = {}
        for kind in ("icon", "follower", *ASSET_KINDS.values()):
            asset_value = record["baseSpeciesId"] if kind == "follower" else value
            available_assets = (
                graphics.get(asset_value, {}) if isinstance(asset_value, int) else {}
            )
            version = asset_data.versions.get((asset_value, kind))
            available = kind in available_assets and version is not None
            if kind == "icon":
                url = f"/icons/{value}.png?v={version[:16]}" if available and version else None
            elif kind == "follower":
                url = (
                    f"/pokemon-assets/{asset_value}/follower.png?v={version[:16]}"
                    if available and version
                    else None
                )
            else:
                url = (
                    f"/pokemon-assets/{value}/{kind}.png?v={version[:16]}"
                    if available and version
                    else None
                )
            asset_entries[kind] = {"available": available, "url": url, "version": version}
        record["assets"] = asset_entries
        record["assetAccess"] = asset_access_matrix[symbol]
        record["sources"] = {
            "personal": "armips/data/mondata.s",
            "baseExperience": "data/BaseExperienceTable.c",
            "hiddenAbility": "data/HiddenAbilityTable.c",
            "learnset": "data/learnsets/learnsets.json",
            "evolutions": "armips/data/evodata.s",
            "babySpecies": "armips/data/babymons.s",
            "forms": record["formMetadata"]["source"],
            "graphics": "data/graphics/pokegra.mk",
            "followerGraphics": "src/field/overworld_table.c",
        }
        base_stats = record.get("baseStats", {})
        ev_yields = record.get("evYields", {})
        type_values = record.get("types") or []
        held_item_values = record.get("heldItems") or []
        candidate_editable = {
            "entry": {
                "name": record.get("sourceName"),
                "dexEntry": record.get("dex", {}).get("entry"),
                "classification": record.get("dex", {}).get("classification"),
                "height": record.get("dex", {}).get("height"),
                "weight": record.get("dex", {}).get("weight"),
                "genderRatio": record.get("genderRatio"),
                "flip": record.get("flipSprite"),
                "bodyColor": record.get("bodyColor", {}).get("symbol"),
            },
            "battle": {
                "baseStats": {
                    "hp": base_stats.get("hp"),
                    "attack": base_stats.get("attack"),
                    "defense": base_stats.get("defense"),
                    "speed": base_stats.get("speed"),
                    "spAttack": base_stats.get("specialAttack"),
                    "spDefense": base_stats.get("specialDefense"),
                },
                "catchRate": record.get("catchRate"),
                "runChance": record.get("runChance"),
                "baseExperience": record.get("baseExperience"),
                "evYields": {
                    "hp": ev_yields.get("hp"),
                    "attack": ev_yields.get("attack"),
                    "defense": ev_yields.get("defense"),
                    "speed": ev_yields.get("speed"),
                    "spAttack": ev_yields.get("specialAttack"),
                    "spDefense": ev_yields.get("specialDefense"),
                },
                "types": {
                    "primary": type_values[0].get("symbol") if type_values else None,
                    "secondary": type_values[1].get("symbol") if len(type_values) > 1 else None,
                },
                "heldItems": {
                    "common": held_item_values[0].get("symbol") if held_item_values else None,
                    "rare": held_item_values[1].get("symbol") if len(held_item_values) > 1 else None,
                },
                "abilities": {
                    slot: record.get("abilities", {}).get(slot, {}).get("symbol")
                    for slot in ("primary", "secondary", "hidden")
                },
            },
            "growth": {
                "eggCycles": record.get("eggCycles"),
                "baseFriendship": record.get("baseFriendship"),
                "growthRate": record.get("growthRate", {}).get("symbol"),
                "eggGroups": {
                    "primary": (record.get("eggGroups") or [{}])[0].get("symbol"),
                    "secondary": (
                        (record.get("eggGroups") or [{}, {}])[1].get("symbol")
                        if len(record.get("eggGroups") or []) > 1
                        else None
                    ),
                },
            },
        }
        record_access = access_matrix.get(symbol) or {
            field["path"]: {
                "writable": False,
                "reason": "species is missing from writer access matrix",
            }
            for field in field_registry()
        }
        record["fieldAccess"] = record_access
        record["groupAccess"] = {
            group: {
                "writable": any(
                    decision.get("writable")
                    for path, decision in record_access.items()
                    if path.startswith(group + ".")
                ),
                "reason": None,
            }
            for group in ("entry", "battle", "growth")
        }
        for group, decision in record["groupAccess"].items():
            if not decision["writable"]:
                decision["reason"] = f"no writable {group} fields for this record"
        record["groupAccess"]["moves"] = {
            "writable": record["learnsetAccess"]["writable"],
            "reason": record["learnsetAccess"]["reason"],
        }
        evolution_group_writable = (
            record["evolutionAccess"]["writable"]
            or record["babyAccess"]["writable"]
        )
        record["groupAccess"]["evolution"] = {
            "writable": evolution_group_writable,
            "reason": (
                None
                if evolution_group_writable
                else record["evolutionAccess"]["reason"]
                or record["babyAccess"]["reason"]
            ),
        }
        record["groupAccess"]["forms"] = {
            "writable": record["formAccess"]["writable"],
            "reason": record["formAccess"]["reason"],
        }
        record["groupAccess"]["assets"] = {
            "writable": record["assetAccess"]["writable"],
            "reason": record["assetAccess"]["reason"],
        }
        record["writableGroups"] = [
            group for group, decision in record["groupAccess"].items() if decision["writable"]
        ]
        record["editable"] = {}
        for path, decision in record_access.items():
            if decision.get("writable"):
                _set_path_value(record["editable"], path, _path_value(candidate_editable, path))
        if validate_writable:
            unresolved_tokens = [
                item["symbol"]
                for item in (
                    *(record.get("types") or []),
                    *(record.get("heldItems") or []),
                    *record.get("abilities", {}).values(),
                    *(record.get("eggGroups") or []),
                    record.get("growthRate") or {},
                    record.get("bodyColor") or {},
                )
                if item and item.get("value") is None
            ]
            if unresolved_tokens:
                raise ValueError(
                    f"{symbol} contains unknown writable enum token(s): "
                    + ", ".join(unresolved_tokens)
                )

        type_symbols.update(item["symbol"] for item in record.get("types", []))
        ability_symbols.update(item["symbol"] for item in record.get("abilities", {}).values())
        item_symbols.update(item["symbol"] for item in record.get("heldItems", []))
        if record.get("growthRate"):
            growth_symbols.add(record["growthRate"]["symbol"])
        egg_symbols.update(item["symbol"] for item in record.get("eggGroups", []))
        if record.get("bodyColor"):
            color_symbols.add(record["bodyColor"]["symbol"])
        evo_symbols.update(edge["method"]["symbol"] for edge in record["evolutions"])

    # Resolve five-bit target form indexes to their adjusted-species records,
    # then materialise incoming edges. This is done after identity construction
    # so all modern and legacy form metadata is available.
    by_symbol = {record["symbol"]: record for record in records}
    diagnostics: list[dict[str, Any]] = []
    for record in records:
        for position, edge in enumerate(record["evolutions"]):
            target_base = edge["targetBaseSymbol"]
            logical_target: dict[str, Any] = {
                "baseSymbol": target_base,
                "formIndex": edge.get("targetFormIndex", 0),
                "alias": target_base,
                "resolved": True,
            }
            if "targetFormIndex" in edge:
                if edge["targetFormIndex"] == 0:
                    target_form = None
                    edge["targetSymbol"] = target_base
                    edge["targetFormResolved"] = True
                else:
                    target_form = next(
                        (
                            metadata
                            for metadata in forms_by_base.get(target_base, [])
                            if metadata.get("formIndex") == edge["targetFormIndex"]
                            and metadata.get("enabled")
                        ),
                        None,
                    )
                    base_form_alias = edge["targetFormIndex"] in (
                        pokemon_evolution_writer.BASE_FORM_INDEX_ALIASES.get(
                            target_base, set()
                        )
                    )
                    edge["targetSymbol"] = (
                        target_form["symbol"]
                        if target_form
                        else (target_base if base_form_alias else None)
                    )
                    edge["targetFormResolved"] = target_form is not None or base_form_alias
                    logical_target.update(
                        {
                            "alias": (
                                target_form["symbol"]
                                if target_form
                                else f"{target_base}@FORM_{edge['targetFormIndex']}"
                            ),
                            "resolved": target_form is not None or base_form_alias,
                            "baseFormAlias": base_form_alias,
                        }
                    )
                    if target_form is None and not base_form_alias:
                        diagnostic = {
                            "code": "unresolved-evolution-target-form",
                            "severity": "warning",
                            "sourceSymbol": record["symbol"],
                            "targetBaseSymbol": target_base,
                            "targetFormIndex": edge["targetFormIndex"],
                            "logicalTarget": logical_target["alias"],
                            "message": (
                                f"{record['symbol']} targets logical form "
                                f"{logical_target['alias']}, which has no adjusted-species record"
                            ),
                        }
                        edge["diagnostics"] = [diagnostic]
                        diagnostics.append(diagnostic)
            edge["logicalTarget"] = logical_target
            target_record = by_symbol.get(edge["targetSymbol"])
            edge["targetSpeciesId"] = target_record.get("speciesId") if target_record else None
            edge["targetNationalDexNumber"] = (
                target_record.get("nationalDexNumber") if target_record else None
            )
            edge["id"] = f"{record['symbol']}:{position}:{edge['targetSymbol']}"
            edge["source"] = "armips/data/evodata.s"
            parameter_diagnostic = edge["parameter"].get("diagnostic")
            if parameter_diagnostic:
                diagnostic = {
                    **parameter_diagnostic,
                    "sourceSymbol": record["symbol"],
                    "edgeId": edge["id"],
                }
                edge.setdefault("diagnostics", []).append(diagnostic)
                diagnostics.append(diagnostic)

    for record in records:
        record["incomingEvolutions"] = []
    for source_record in records:
        for edge in source_record["evolutions"]:
            target_record = by_symbol.get(edge["targetSymbol"])
            if target_record:
                target_record["incomingEvolutions"].append(
                    {
                        "id": edge["id"],
                        "sourceSymbol": source_record["symbol"],
                        "sourceSpeciesId": source_record["speciesId"],
                        "method": edge["method"],
                        "parameter": edge["parameter"],
                    }
                )

    type_limit = int(macros.get("NUMBER_OF_MON_TYPES", 20))
    type_symbols.update(
        symbol
        for symbol, value in macros.items()
        if re.fullmatch(r"TYPE_[A-Z]+", symbol) and isinstance(value, int) and 0 <= value < type_limit
    )

    source_descriptions = {
        "personal": "armips/data/mondata.s",
        "baseExperience": "data/BaseExperienceTable.c",
        "hiddenAbilities": "data/HiddenAbilityTable.c",
        "learnsets": "data/learnsets/learnsets.json",
        "evolutions": "armips/data/evodata.s",
        "babySpecies": "armips/data/babymons.s",
        "speciesConstants": ["asm/include/species.inc", "include/constants/species.h"],
        "moveConstants": "asm/include/moves.inc",
        "featureConfiguration": "include/config.h",
        "forms": [
            "asm/include/species.inc",
            "src/pokemon.c",
            "data/FormToSpeciesMapping.c",
            "data/PokeFormDataTbl.c",
        ],
        "graphics": {
            "manifest": "data/graphics/pokegra.mk",
            "assetRevision": graphics_revision,
            "versioning": "sha256-content",
        },
    }
    public_records: list[dict[str, Any]] = []
    excluded_counts: dict[str, int] = {}
    for record in records:
        reason = _exclusion_reason(record)
        if reason:
            excluded_counts[reason] = excluded_counts.get(reason, 0) + 1
        else:
            public_records.append(record)
    _evolution_families(public_records)
    field_access_summary: dict[str, Any] = {
        "recordCount": len(public_records),
        "decisionCount": 0,
        "writableCount": 0,
        "unwritableCount": 0,
        "fields": {},
    }
    for field in field_registry():
        path = field["path"]
        field_summary = {"writableCount": 0, "unwritableCount": 0, "reasons": {}}
        for record in public_records:
            decision = record["fieldAccess"][path]
            if decision["writable"]:
                field_summary["writableCount"] += 1
                field_access_summary["writableCount"] += 1
            else:
                field_summary["unwritableCount"] += 1
                field_access_summary["unwritableCount"] += 1
                reason_code = _access_reason_code(decision.get("reason"))
                field_summary["reasons"][reason_code] = (
                    field_summary["reasons"].get(reason_code, 0) + 1
                )
            field_access_summary["decisionCount"] += 1
        field_access_summary["fields"][path] = field_summary
    return PokemonDataset({
        "apiVersion": 2,
        "capabilities": POKEMON_CAPABILITIES,
        "fieldRegistry": field_registry(),
        "fieldAccessSummary": field_access_summary,
        "assetRevision": graphics_revision,
        "pokemon": public_records,
        "diagnostics": diagnostics,
        "enums": {
            "types": _enum_list(type_symbols, macros, "TYPE_"),
            "abilities": _enum_list(ability_symbols, macros, "ABILITY_", include_all=True),
            "items": _enum_list(item_symbols, macros, "ITEM_", include_all=True),
            "growthRates": _enum_list(growth_symbols, macros, "GROWTH_"),
            "eggGroups": _enum_list(egg_symbols, macros, "EGG_GROUP_"),
            "bodyColors": _enum_list(color_symbols, macros, "BODY_COLOR_"),
            "evolutionMethods": _enum_list(evo_symbols, macros, "EVO_"),
        },
        "sources": source_descriptions,
        "summary": {
            "pokemonCount": len(public_records),
            "baseSpeciesCount": sum(not record["isForm"] for record in public_records),
            "formCount": sum(record["isForm"] for record in public_records),
            "learnsetCount": len(learnsets),
            "excludedRecordCount": sum(excluded_counts.values()),
            "excludedByReason": excluded_counts,
        },
    }, learnsets=learnsets)


def build_detail(
    root: Path,
    legacy: ModuleType,
    symbol: str,
    *,
    assets: AssetSnapshot | None = None,
    validate_writable: bool = False,
    dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one index record plus its actual editable learnset arrays."""

    canonical_symbol = pokemon_writer.canonical_species_symbol(symbol)
    dataset = dataset or build_dataset(
        root, legacy, assets=assets, validate_writable=validate_writable
    )
    record = next((entry for entry in dataset["pokemon"] if entry["symbol"] == canonical_symbol), None)
    if record is None:
        raise ValueError(f"unknown public Pokemon species: {symbol}")
    learnsets = (
        dataset.learnsets
        if isinstance(dataset, PokemonDataset)
        else json.loads((root / "data/learnsets/learnsets.json").read_text(encoding="utf-8"))
    )
    summary, detail = _normalised_learnset(learnsets, record["symbol"], record["baseSymbol"])
    if summary != record["learnsetSummary"]:
        raise RuntimeError("learnset summary changed while detail was assembled")
    base_record = next(
        entry for entry in dataset["pokemon"] if entry["symbol"] == record["baseSymbol"]
    )
    form_access = base_record["formAccess"]
    form_editor = {
        "baseSymbol": base_record["symbol"],
        "access": {
            "writable": bool(form_access["writable"] and not record["isForm"]),
            "reason": (
                "edit this family from its canonical base record"
                if record["isForm"] and form_access["writable"]
                else form_access["reason"]
            ),
            "actionTargetSymbol": base_record["symbol"],
        },
        "forms": [
            {
                "identity": f"{base_record['symbol']}@FORM_{form.get('declaredFormIndex')}",
                "symbol": form["symbol"],
                "name": form["name"],
                "label": form["name"],
                "declaredFormIndex": form.get("declaredFormIndex"),
                "adjustedRecord": form.get("speciesId") is not None,
                "enabled": form.get("enabled", False),
                "needsReversion": form.get("needsReversion", False),
                "aliases": [],
                "flags": {
                    key: form.get(key, False)
                    for key in ("registered", "legacyAdjustedSpecies", "placeholder")
                },
                "source": form.get("source"),
                "access": {
                    **{
                        field: dict(decision)
                        for field, decision in form_access["fields"].items()
                    },
                    "identity": {"writable": False, "reason": "base/form identity is a runtime invariant"},
                    "symbol": {"writable": False, "reason": "form membership is fixed by source identity"},
                    "name": {"writable": False, "reason": "names are edited through the Entry domain"},
                    "aliases": {"writable": False, "reason": "aliases are derived from form mappings"},
                    "flags": {"writable": False, "reason": "registry and legacy flags are source-derived"},
                },
            }
            for form in base_record.get("forms", [])
        ],
        "aliases": [
            {
                "identity": f"{base_record['symbol']}@FORM_{form_index}",
                "baseSymbol": base_record["symbol"],
                "formIndex": form_index,
                "label": pokemon_evolution_writer.BASE_FORM_INDEX_ALIAS_LABELS.get(
                    (base_record["symbol"], form_index), f"Form {form_index}"
                ),
                "sourceBacked": False,
                "access": {
                    "writable": False,
                    "reason": "logical runtime alias has no adjusted form registry record",
                },
            }
            for form_index in sorted(
                pokemon_evolution_writer.BASE_FORM_INDEX_ALIASES.get(
                    base_record["symbol"], set()
                )
            )
        ],
        "rules": {
            "minFormIndex": 1,
            "maxFormIndex": 31,
            "maxForms": pokemon_form_writer.MAX_FORMS,
            "sourceFormCount": len(base_record.get("forms", [])),
            "membershipMutable": False,
            "orderMutable": False,
        },
    }
    asset_access = record["assetAccess"]
    asset_editor = {
        "access": {"writable": asset_access["writable"], "reason": asset_access["reason"]},
        "rules": {
            "allowedMimeTypes": ["image/png"],
            "maxBytes": pokemon_asset_writer.MAX_ASSET_BYTES,
            "slots": {
                slot: {"width": rule[1], "height": rule[2]}
                for slot, rule in pokemon_asset_writer.SLOT_RULES.items()
            },
        },
        "slots": {
            slot: {
                **metadata,
                "url": record["assets"].get(
                    pokemon_asset_writer.SLOT_RULES[slot][0], {}
                ).get("url"),
            }
            for slot, metadata in asset_access["slots"].items()
        },
    }
    return {
        "apiVersion": 2,
        "capabilities": POKEMON_CAPABILITIES,
        "fieldRegistry": field_registry(),
        "assetRevision": dataset["assetRevision"],
        "pokemon": record,
        "learnset": detail,
        "formEditor": form_editor,
        "assetEditor": asset_editor,
        "editorOptionsEndpoint": "/api/v2/pokemon-editor-options",
        "sources": dataset["sources"],
    }
