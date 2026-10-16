"""Compiler-owned append-only subject bank tail for behavior data.

The compiler includes every species that can be named by an authored
application; dynamic selectors remain subject to the ordinary runtime match.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


class BankCapacityError(ValueError):
    pass


def _species_values(header: Path) -> dict[str, int]:
    definitions: dict[str, str] = {}
    for line in header.read_text().splitlines():
        line = line.split("//", 1)[0].strip()
        match = re.fullmatch(r"#define\s+([A-Z][A-Z0-9_]*)\s+(.+)", line)
        if match:
            definitions[match[1]] = match[2].strip()
    cache: dict[str, int] = {}

    def evaluate(name: str) -> int:
        if name in cache:
            return cache[name]
        if name not in definitions:
            raise BankCapacityError(f"unknown species macro {name}")
        node = ast.parse(definitions[name], mode="eval").body

        def value(item: ast.AST) -> int:
            if isinstance(item, ast.Constant) and type(item.value) is int:
                return item.value
            if isinstance(item, ast.Name):
                return evaluate(item.id)
            if isinstance(item, ast.BinOp):
                left, right = value(item.left), value(item.right)
                if isinstance(item.op, ast.Add):
                    return left + right
                if isinstance(item.op, ast.Sub):
                    return left - right
                if isinstance(item.op, ast.LShift):
                    return left << right
                if isinstance(item.op, ast.BitOr):
                    return left | right
            raise BankCapacityError(f"unsupported species macro {name}")

        cache[name] = value(node)
        return cache[name]

    return {name: evaluate(name) for name in definitions if name.startswith("SPECIES_")}


def compile_bank(catalog: dict, species_header: Path) -> dict:
    profiles = {row["id"]: row for row in catalog["profiles"]}
    pools = {row["id"]: row for row in catalog.get("pools", [])}
    apps = {row["id"]: row for row in catalog["applications"]}
    numeric = _species_values(species_header)
    forced = {catalog["runtimeBindings"][name] for name in
              ("followerApplication", "mountedApplication", "forcedAsleepApplication")}
    tired_only = {catalog["runtimeBindings"]["defaultTiredApplication"]}
    tired_only.update(field["value"] for profile in catalog["profiles"]
        for name, field in profile.get("fields", {}).items()
        if name == "tiredProfile" and field.get("operator") == "replace")

    def members(selector: dict) -> set[str] | None:
        if "pool" in selector:
            selector = pools[selector["pool"]]
        if "application" in selector:
            selector = apps[selector["application"]].get("target", {})
        if selector.get("mode") == "disabled":
            return set()
        out = None if selector.get("mode") == "all" else set(selector.get("members", []))
        selected = selector.get("match", {}).get("species")
        if selected and selected != "OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES":
            out = {selected} if out is None else out & {selected}
        return out

    subjects = []
    condition_subjects = []
    for global_id, application in enumerate(catalog["applications"]):
        if application.get("enabled") is False:
            continue
        profile = profiles[application["profile"]]
        if application["id"] in tired_only - forced and profile["kind"] == "normal":
            continue
        if application["id"] in forced:
            selected = None
        else:
            selectors = ([row["subjects"] for row in profile["conditions"]]
                         if profile["kind"] == "conditional"
                         else [application.get("target", {})])
            selections = [members(row) for row in selectors]
            selected = None if None in selections else set().union(*selections)
        if profile["kind"] == "conditional":
            condition_subjects.extend(members(row["subjects"])
                for row in profile["conditions"])
        subjects.append((global_id, application["id"], selected))
    if len(catalog["applications"]) > 65535:
        raise BankCapacityError("global application count exceeds u16")
    if len(condition_subjects) > 65535:
        raise BankCapacityError("global condition entry count exceeds u16")
    mentioned = set().union(*(s for _, _, s in subjects if s is not None))
    mentioned.update(*(s for s in condition_subjects if s is not None))
    unknown = mentioned - numeric.keys()
    if unknown:
        raise BankCapacityError(f"unknown species: {sorted(unknown)}")
    subjects = [(global_id, name,
        None if selected is None else {numeric[symbol] for symbol in selected})
        for global_id, name, selected in subjects]
    condition_subjects = [None if selected is None else
        {numeric[symbol] for symbol in selected} for selected in condition_subjects]
    rows = []
    indexes = []
    for species in sorted({numeric[symbol] for symbol in mentioned}):
        bank = [global_id for global_id, _, selected in subjects
                if selected is None or species in selected]
        if len(bank) > 32:
            raise BankCapacityError(f"species {species} needs {len(bank)} local application bits")
        condition_count = sum(selected is None or species in selected
            for selected in condition_subjects)
        if condition_count > 32:
            raise BankCapacityError(f"species {species} needs {condition_count} local condition entries")
        rows.append((species, len(indexes), len(bank)))
        indexes.extend(bank)
    fallback = [global_id for global_id, _, selected in subjects
                if selected is None]
    if len(fallback) > 32:
        raise BankCapacityError("unlisted species needs more than 32 local application bits")
    fallback_condition_count = sum(selected is None for selected in condition_subjects)
    if fallback_condition_count > 32:
        raise BankCapacityError("unlisted species needs more than 32 local condition entries")
    rows.append(("0xFFFF", len(indexes), len(fallback)))
    indexes.extend(fallback)
    if len(rows) > 65535:
        raise BankCapacityError("bank directory count exceeds u16")
    if len(indexes) > 65535 or any(first > 65535 or first + count > 65535
                                   for _species, first, count in rows):
        raise BankCapacityError("bank index table exceeds u16 offset")
    return {"rows": rows, "indexes": indexes,
            "globalApplications": [name for _, name, _ in subjects]}


def render_tail(bank: dict, condition_global: list[int],
                subject_global: list[int], limit_keys: list[int],
                rest_tint: list[int], tired_class: list[int],
                tired_override: list[int]) -> str:
    for label, values in (("bank global application IDs", bank["indexes"]),
                          ("condition owner IDs", condition_global),
                          ("condition subject owner IDs", subject_global),
                          ("Tired class IDs", tired_class),
                          ("Tired override IDs", tired_override)):
        if len(values) > 65535 or any(not 0 <= value <= 65535 for value in values):
            raise BankCapacityError(f"{label} exceed u16 storage")
    if len(limit_keys) > 65535 or len(rest_tint) > 65535:
        raise BankCapacityError("application sidecars exceed u16 count")
    if len(condition_global) != len(subject_global):
        raise BankCapacityError("condition owner sidecars have different counts")
    directory = ",\n".join(
        f"        {{{species}, {first}, {count}, 0}}"
        for species, first, count in bank["rows"])
    indexes = ", ".join(str(index) for index in bank["indexes"])
    def values(items):
        return ", ".join(str(item) for item in (items or [0]))
    return ("    /* applicationBankDirectory */\n"
            "    {\n" + directory + "\n    },\n"
            "    /* applicationBankIndexes */\n"
            "    {" + indexes + "},\n"
            "    /* conditionGlobalApplications */\n"
            "    {" + values(condition_global) + "},\n"
            "    /* conditionGlobalSubjectApplications */\n"
            "    {" + values(subject_global) + "},\n"
            "    /* applicationLimitKeys */\n"
            "    {" + values(limit_keys) + "},\n"
            "    /* applicationRestTint */\n"
            "    {" + values(rest_tint) + "},\n"
            "    /* tiredClassGlobalIds */\n"
            "    {" + values(tired_class) + "},\n"
            "    /* tiredOverrideGlobalIds */\n"
            "    {" + values(tired_override) + "}\n")
