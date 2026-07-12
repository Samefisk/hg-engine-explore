"""Lossless writer for source-backed adjusted-form registry ordering and flags."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pokemon_writer


FORM_DATA_RELATIVE = "data/PokeFormDataTbl.c"
MAX_FORMS = 31


@dataclass(frozen=True)
class FormLine:
    symbol: str
    needs_reversion: bool
    raw: str
    indent: str
    newline: str
    trailing_comma: bool


@dataclass(frozen=True)
class FormBlock:
    base_symbol: str
    body_start: int
    body_end: int
    lines: tuple[FormLine, ...]
    writable: bool
    reason: str | None


def mutation_source_paths(root: Path) -> tuple[Path, ...]:
    return ((Path(root).resolve() / FORM_DATA_RELATIVE).resolve(),)


def _blocks(root: Path) -> tuple[str, dict[str, FormBlock]]:
    path = Path(root).resolve() / FORM_DATA_RELATIVE
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(?m)^\s*\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=\s*\{(?P<body>.*?)^\s*\},?",
        re.S,
    )
    result: dict[str, FormBlock] = {}
    entry = re.compile(
        r"^(?P<indent>\s*)(?:(?P<reversion>NEEDS_REVERSION)\s*\|\s*)?"
        r"(?P<symbol>SPECIES_[A-Z0-9_]+)\s*(?P<comma>,)?\s*(?://[^\r\n]*)?(?P<newline>\r?\n|$)"
    )
    for match in pattern.finditer(text):
        base = match.group(1)
        body = match.group("body")
        lines: list[FormLine] = []
        unsafe: list[str] = []
        cursor = 0
        for raw in body.splitlines(keepends=True):
            stripped = raw.strip()
            parsed = entry.fullmatch(raw)
            if parsed:
                lines.append(
                    FormLine(
                        parsed.group("symbol"),
                        parsed.group("reversion") is not None,
                        raw,
                        parsed.group("indent"),
                        "\r\n" if raw.endswith("\r\n") else ("\n" if raw.endswith("\n") else ""),
                        parsed.group("comma") is not None,
                    )
                )
            elif stripped:
                unsafe.append(stripped[:80])
            cursor += len(raw)
        reason = None
        if not lines:
            reason = "form block has no source-backed entries"
        elif unsafe:
            reason = "form block contains conditional or non-entry source structure"
        prefix_text = text[: match.start()]
        conditional_depth = 0
        for directive in re.findall(r"(?m)^\s*#\s*(ifn?def|if|endif)\b", prefix_text):
            conditional_depth += -1 if directive == "endif" else 1
        if reason is None and conditional_depth:
            reason = "form registry block is controlled by compile-time configuration"
        elif len(lines) > MAX_FORMS:
            reason = f"form block exceeds the {MAX_FORMS}-form runtime limit"
        elif any(not line.trailing_comma for line in lines[:-1]):
            reason = "non-final form entries must retain trailing commas"
        if base in result:
            reason = "base species has multiple form registry blocks"
        result[base] = FormBlock(
            base,
            match.start("body"),
            match.end("body"),
            tuple(lines),
            reason is None,
            reason,
        )
    return text, result


def form_access_matrix(root: Path) -> dict[str, dict[str, Any]]:
    _, blocks = _blocks(root)
    result: dict[str, dict[str, Any]] = {}
    for base, block in blocks.items():
        fields = {
            "declaredFormIndex": {
                "writable": False,
                "reason": "runtime form indexes are referenced cross-record; registry ordering is preserved",
            },
            "needsReversion": {"writable": block.writable, "reason": block.reason},
            "enabled": {
                "writable": False,
                "reason": "enabled state is derived from compile-time configuration",
            },
        }
        result[base] = {
            "writable": block.writable,
            "reason": block.reason,
            "source": FORM_DATA_RELATIVE,
            "fields": fields,
            "formCount": len(block.lines),
            "maxForms": MAX_FORMS,
        }
    return result


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


def apply_form_updates(root: Path, payload: Any) -> dict[str, Any]:
    root = Path(root).resolve()
    if not isinstance(payload, dict) or set(payload) != {"records"}:
        raise ValueError("form update payload must contain exactly records")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("form update records must be a non-empty array")
    text, blocks = _blocks(root)
    replacements: list[tuple[int, int, str, str]] = []
    seen: set[str] = set()
    changed_forms = 0
    for record_index, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != {"baseSymbol", "forms"}:
            raise ValueError(f"records[{record_index}] must contain exactly baseSymbol and forms")
        raw_base = record["baseSymbol"]
        if not isinstance(raw_base, str):
            raise ValueError(f"records[{record_index}].baseSymbol must be a species symbol")
        base = pokemon_writer.canonical_species_symbol(raw_base)
        if base in seen:
            raise ValueError(f"duplicate form update for {base}")
        seen.add(base)
        block = blocks.get(base)
        if block is None:
            raise ValueError(f"{base} has no PokeFormDataTbl registry block")
        if not block.writable:
            raise ValueError(f"{base} form registry is read-only: {block.reason}")
        forms = record["forms"]
        if not isinstance(forms, list) or not forms or len(forms) > MAX_FORMS:
            raise ValueError(f"{base}.forms must contain 1 to {MAX_FORMS} entries")
        source_by_symbol = {line.symbol: line for line in block.lines}
        if len(source_by_symbol) != len(block.lines):
            raise ValueError(f"{base} source contains duplicate form symbols")
        planned: list[tuple[FormLine, bool]] = []
        requested_symbols: list[str] = []
        for index, form in enumerate(forms, 1):
            if not isinstance(form, dict) or set(form) != {
                "symbol", "declaredFormIndex", "enabled", "needsReversion"
            }:
                raise ValueError(f"{base}.forms[{index - 1}] has an invalid shape")
            symbol = form["symbol"]
            if not isinstance(symbol, str) or symbol not in source_by_symbol:
                raise ValueError(f"{base}.forms[{index - 1}].symbol is not a source member")
            if (
                isinstance(form["declaredFormIndex"], bool)
                or not isinstance(form["declaredFormIndex"], int)
                or form["declaredFormIndex"] != index
            ):
                raise ValueError(f"{base} declaredFormIndex values must match contiguous array order")
            if not isinstance(form["enabled"], bool) or not form["enabled"]:
                raise ValueError(f"{base}.{symbol}.enabled is derived and cannot be changed")
            if not isinstance(form["needsReversion"], bool):
                raise ValueError(f"{base}.{symbol}.needsReversion must be a boolean")
            requested_symbols.append(symbol)
            planned.append((source_by_symbol[symbol], form["needsReversion"]))
        if set(requested_symbols) != set(source_by_symbol) or len(requested_symbols) != len(source_by_symbol):
            raise ValueError(f"{base} form membership and count must remain unchanged")
        if requested_symbols != [line.symbol for line in block.lines]:
            raise ValueError(
                f"{base} registry ordering is a cross-record runtime invariant and cannot be changed"
            )
        rendered: list[str] = []
        for source_line, needs_reversion in planned:
            raw = source_line.raw
            if needs_reversion and not source_line.needs_reversion:
                raw = (
                    raw[: len(source_line.indent)]
                    + "NEEDS_REVERSION | "
                    + raw[len(source_line.indent) :]
                )
            elif source_line.needs_reversion and not needs_reversion:
                raw = re.sub(
                    r"^(\s*)NEEDS_REVERSION\s*\|\s*",
                    r"\1",
                    raw,
                    count=1,
                )
            rendered.append(raw)
        body = ("\r\n" if "\r\n" in text else "\n") + "".join(rendered)
        if body == text[block.body_start:block.body_end]:
            raise ValueError(f"no-op form edit for {base}")
        replacements.append((block.body_start, block.body_end, body, base))
        changed_forms += sum(
            line.symbol != planned[index][0].symbol
            or line.needs_reversion != planned[index][1]
            for index, line in enumerate(block.lines)
        )
    for previous, current in zip(sorted(replacements), sorted(replacements)[1:]):
        if current[0] < previous[1]:
            raise ValueError("overlapping form registry updates")
    updated = text
    for start, end, body, _ in sorted(replacements, reverse=True):
        updated = updated[:start] + body + updated[end:]
    if updated.count("{") != text.count("{") or updated.count("}") != text.count("}"):
        raise ValueError("patched form registry changed structural brace counts")
    _atomic_write(root / FORM_DATA_RELATIVE, updated.encode("utf-8"))
    return {"saved": True, "changedRecords": len(records), "changedForms": changed_forms, "sourceFiles": [FORM_DATA_RELATIVE]}
