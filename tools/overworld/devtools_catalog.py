"""Read-only authored constant discovery, not current-ROM support validation."""
from __future__ import annotations

from functools import lru_cache
import hashlib
from pathlib import Path
import re
import unicodedata

from scripts.build_move_relearn_parents import evaluate_constant, without_comments


CATALOGS = {
    "species": ("include/constants/species.h", "SPECIES_"),
    "maps": ("include/constants/maps.h", "MAP_"),
    "moves": ("include/constants/moves.h", "MOVE_"),
}
MAX_SOURCE_BYTES = 2 * 1024 * 1024


def _normalized(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).casefold()
    return "".join(character for character in text if character.isalnum())


def _expression(value: str) -> str:
    # Reuse the repository's small AST interpreter. Its supported grammar is
    # integer literals, known names, parentheses, unary minus, addition and
    # subtraction. These cover the three authored headers; never eval Python.
    value = re.sub(r"\b(0[xX][0-9a-fA-F]+|[0-9]+)[uUlL]+\b", r"\1", value)
    if len(value) > 512:
        raise ValueError("expression exceeds 512 characters")
    compact = re.sub(r"\s+", "", value)
    tokens = re.findall(r"0[xX][0-9a-fA-F]+|[0-9]+|[A-Z_][A-Z0-9_]*|[()+-]", compact)
    if "".join(tokens) != compact:
        raise ValueError("unsupported constant expression")
    return value


@lru_cache(maxsize=6)
def _parse(data: bytes, prefix: str) -> tuple[tuple, tuple]:
    source = without_comments(data.decode("utf-8")).replace("\\\n", "")
    expressions, invalid = {}, {}
    pattern = re.compile(r"^\s*#\s*define\s+([A-Z_][A-Z0-9_]*)([ \t]+)([^\n]+)$", re.M)
    for match in pattern.finditer(source):
        name, expression = match[1], match[3].strip()
        if name in expressions and expressions[name] != expression:
            invalid[name] = "conflicting authored definitions"
        expressions[name] = expression
    if len(expressions) > 10000:
        raise ValueError("authored catalog exceeds 10000 constants")
    pending, values = {}, {}
    for name, expression in expressions.items():
        if name in invalid:
            continue
        try:
            pending[name] = _expression(expression)
        except ValueError as error:
            invalid[name] = str(error)
    # Forward aliases resolve in later passes. Cycles and unsupported names
    # remain explicit gaps; one bad entry cannot silently become ID zero.
    for _ in range(len(pending) + 1):
        progressed = False
        for name, expression in list(pending.items()):
            try:
                value = evaluate_constant(expression, values)
            except (SyntaxError, ValueError, RecursionError):
                continue
            if type(value) is not int or not -0x80000000 <= value <= 0xFFFFFFFF:
                invalid[name] = "constant is outside the bounded integer range"
            else:
                values[name] = value
            del pending[name]
            progressed = True
        if not progressed:
            break
    invalid.update({name: "unresolved alias, cycle, or unsupported arithmetic" for name in pending})
    entries, unresolved = [], []
    for name in expressions:
        if not name.startswith(prefix) or name.endswith("_START"):
            continue
        if name in invalid or name not in values:
            unresolved.append((name, invalid.get(name, "unresolved constant")))
        elif not 0 <= values[name] <= 65535:
            unresolved.append((name, "ID is outside 0..65535"))
        else:
            label = " ".join(part.capitalize() for part in name[len(prefix):].split("_"))
            entries.append((values[name], label, name))
    return tuple(entries), tuple(unresolved)


def catalog(root: str | Path, kind: str, query: str = "", limit: int = 30) -> dict:
    """Find authored IDs by exact number, normalized name, prefix or substring.

    Alias symbols remain separate items with the same ID. Source hashes name
    the exact header read. No ROM, save, private data or build output is read.
    Map labels retain their authored tokens (for example R30 and T21).
    """
    if not isinstance(kind, str) or kind not in CATALOGS:
        raise ValueError("catalog kind must be species, maps or moves")
    if not isinstance(query, str) or len(query) > 128:
        raise ValueError("query must be text of at most 128 characters")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer in 1..100")
    relative, prefix = CATALOGS[kind]
    path = Path(root) / relative
    with path.open("rb") as source:
        data = source.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError("authored catalog header exceeds 2 MiB")
    entries, unresolved = _parse(data, prefix)
    normalized = _normalized(query)
    numeric = None
    if re.fullmatch(r"(?:0[xX][0-9a-fA-F]+|[0-9]+)", query.strip()):
        numeric = int(query.strip(), 16 if query.strip().lower().startswith("0x") else 10)
    matches = []
    for number, name, symbol in entries:
        names = (_normalized(name), _normalized(symbol))
        if numeric is not None:
            if number != numeric:
                continue
            rank = 0
        elif not normalized:
            rank = 0
        elif any(normalized == candidate for candidate in names):
            rank = 0
        elif any(candidate.startswith(normalized) for candidate in names):
            rank = 1
        elif any(normalized in candidate for candidate in names):
            rank = 2
        else:
            continue
        matches.append((rank, number, symbol, name))
    matches.sort()
    return {
        "kind": kind, "source": "authored-catalog", "schemaVersion": 1,
        "sourcePath": relative, "sourceSha256": hashlib.sha256(data).hexdigest(),
        "query": query, "normalizedQuery": normalized, "limit": limit,
        "items": [{"id": number, "name": name, "symbol": symbol}
                  for _, number, symbol, name in matches[:limit]],
        "total": len(entries), "matched": len(matches), "returned": min(limit, len(matches)),
        "truncated": len(matches) > limit, "complete": not unresolved,
        "unresolvedCount": len(unresolved),
        "unresolved": [{"symbol": name, "reason": reason} for name, reason in unresolved[:100]],
        "limitations": ["Authored constants only; current ROM support and operation eligibility are not verified.",
                        "Map names are authored symbols, not localized place labels.",
                        "Aliases share IDs. Range-start markers are excluded; ID zero may be a sentinel."],
    }
