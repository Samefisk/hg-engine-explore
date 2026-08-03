#!/usr/bin/env python3
"""Verify the live overworld-wild runtime integration source contract.

The verifier intentionally inspects named C structs, functions, guards, and
branches.  It is not a compiler, but it masks comments and literals while
preserving offsets so text that is not executable C cannot satisfy a gate.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT
    / "src"
    / "overworld_wild_spawns_overlay"
    / "overworld_wild_spawns_overlay.c"
)
OK = "OW_WILD_RUNTIME_STATUS_OK"
IDEMPOTENT = "OW_WILD_RUNTIME_STATUS_IDEMPOTENT"
APPLY_HELPER = "OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate"
PROJECT_HELPER = "OverworldWildSpawns_ProjectRuntimeEffectiveBehavior"
PRESENT_HELPER = "OverworldWildSpawns_PresentRuntimeTiredState"
CAPTURE_HELPER = "OverworldWildSpawns_CaptureMovementCommandOrigin"
CONSUME_HELPER = "OverworldWildSpawns_ConsumeMovementCommandOrigin"
INVALIDATE_HELPER = "OverworldWildSpawns_InvalidateMovementCommandOrigin"
INVALIDATE_ALL_HELPER = "OverworldWildSpawns_InvalidateAllMovementCommandOrigins"


class SourceShapeError(ValueError):
    """Raised when a requested named C region cannot be extracted."""


def mask_non_code(source: str) -> str:
    """Mask comments and string/character literals without changing offsets."""

    result = list(source)
    index = 0
    state = "code"
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == "/" and following == "/":
                result[index] = result[index + 1] = " "
                state = "line-comment"
                index += 2
                continue
            if char == "/" and following == "*":
                result[index] = result[index + 1] = " "
                state = "block-comment"
                index += 2
                continue
            if char == '"':
                result[index] = " "
                state = "string"
            elif char == "'":
                result[index] = " "
                state = "character"
        elif state == "line-comment":
            if char == "\n":
                state = "code"
            else:
                result[index] = " "
        elif state == "block-comment":
            if char == "*" and following == "/":
                result[index] = result[index + 1] = " "
                state = "code"
                index += 2
                continue
            if char != "\n":
                result[index] = " "
        else:
            if char == "\\":
                result[index] = " "
                if index + 1 < len(source):
                    if source[index + 1] != "\n":
                        result[index + 1] = " "
                    index += 2
                    continue
            if (state == "string" and char == '"') or (
                state == "character" and char == "'"
            ):
                result[index] = " "
                state = "code"
            elif char != "\n":
                result[index] = " "
        index += 1
    return "".join(result)


def mask_constant_false_preprocessor(source: str) -> str:
    """Mask known ``#if 0`` branches while retaining enabled ``#else`` text."""

    result = list(source)
    stack: list[tuple[bool, bool, bool]] = []
    disabled = False
    offset = 0
    for line in source.splitlines(keepends=True):
        directive = re.match(r"\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)", line)
        mask_line = disabled
        if directive:
            kind = directive.group(1)
            expression = directive.group(2).strip()
            if kind in {"if", "ifdef", "ifndef"}:
                known_false = kind == "if" and expression in {"0", "FALSE", "(0)", "(FALSE)"}
                parent_disabled = disabled
                disabled = parent_disabled or known_false
                stack.append((parent_disabled, known_false, disabled))
            elif kind == "else" and stack:
                parent_disabled, known_false, _ = stack[-1]
                disabled = parent_disabled if known_false else parent_disabled
                stack[-1] = (parent_disabled, known_false, disabled)
            elif kind == "elif" and stack:
                parent_disabled, known_false, _ = stack[-1]
                if known_false:
                    next_false = expression in {"0", "FALSE", "(0)", "(FALSE)"}
                    disabled = parent_disabled or next_false
                    stack[-1] = (parent_disabled, next_false, disabled)
                else:
                    disabled = parent_disabled
                    stack[-1] = (parent_disabled, known_false, disabled)
            elif kind == "endif" and stack:
                parent_disabled, _, _ = stack.pop()
                disabled = parent_disabled
            mask_line = True
        if mask_line:
            for index in range(offset, offset + len(line)):
                if source[index] != "\n":
                    result[index] = " "
        offset += len(line)
    return "".join(result)


def sanitize_source(source: str) -> str:
    return mask_constant_false_preprocessor(mask_non_code(source))


def matching_delimiter(source: str, start: int, opening: str, closing: str) -> int:
    if start >= len(source) or source[start] != opening:
        raise SourceShapeError(f"expected {opening!r} at offset {start}")
    depth = 1
    for index in range(start + 1, len(source)):
        if source[index] == opening:
            depth += 1
        elif source[index] == closing:
            depth -= 1
            if depth == 0:
                return index
    raise SourceShapeError(f"unclosed {opening!r} at offset {start}")


def skip_space(source: str, index: int) -> int:
    while index < len(source) and source[index].isspace():
        index += 1
    return index


def function_body(source: str, name: str) -> str:
    code = sanitize_source(source)
    pattern = re.compile(r"\b" + re.escape(name) + r"\s*\(")
    for match in pattern.finditer(code):
        opening = code.find("(", match.start())
        closing = matching_delimiter(code, opening, "(", ")")
        cursor = skip_space(code, closing + 1)
        if cursor < len(code) and code[cursor] == "{":
            end = matching_delimiter(code, cursor, "{", "}")
            return code[cursor + 1 : end]
    raise SourceShapeError(f"missing function definition {name}")


def function_body_preserving_preprocessor(source: str, name: str) -> str:
    """Extract code while retaining calls inside constant-false directives."""

    code = mask_non_code(source)
    pattern = re.compile(r"\b" + re.escape(name) + r"\s*\(")
    for match in pattern.finditer(code):
        opening = code.find("(", match.start())
        closing = matching_delimiter(code, opening, "(", ")")
        cursor = skip_space(code, closing + 1)
        if cursor < len(code) and code[cursor] == "{":
            end = matching_delimiter(code, cursor, "{", "}")
            return code[cursor + 1 : end]
    raise SourceShapeError(f"missing function definition {name}")


def function_body_span(source: str, name: str) -> tuple[int, int]:
    """Return the raw-source offsets of a named function's body."""

    code = sanitize_source(source)
    pattern = re.compile(r"\b" + re.escape(name) + r"\s*\(")
    for match in pattern.finditer(code):
        opening = code.find("(", match.start())
        closing = matching_delimiter(code, opening, "(", ")")
        cursor = skip_space(code, closing + 1)
        if cursor < len(code) and code[cursor] == "{":
            end = matching_delimiter(code, cursor, "{", "}")
            return cursor + 1, end
    raise SourceShapeError(f"missing function definition {name}")


def struct_body(source: str, name: str) -> str:
    code = sanitize_source(source)
    match = re.search(r"\btypedef\s+struct\s+" + re.escape(name) + r"\b", code)
    if match is None:
        raise SourceShapeError(f"missing struct {name}")
    opening = code.find("{", match.end())
    if opening < 0:
        raise SourceShapeError(f"missing body for struct {name}")
    closing = matching_delimiter(code, opening, "{", "}")
    return code[opening + 1 : closing]


def syntactic_call_positions(body: str, name: str) -> list[int]:
    return [
        match.start()
        for match in re.finditer(r"\b" + re.escape(name) + r"\s*\(", body)
    ]


def position_is_reachable(body: str, position: int) -> bool:
    for region in if_regions(body):
        if region.contains_in_then(position) and condition_is_disabled(region.condition):
            return False
        if region.contains_in_else(position) and condition_is_constant_true(region.condition):
            return False
    return True


def call_positions(body: str, name: str) -> list[int]:
    return [
        position
        for position in syntactic_call_positions(body, name)
        if position_is_reachable(body, position)
    ]


def call_count(body: str, name: str) -> int:
    return len(call_positions(body, name))


def call_index(body: str, name: str) -> int:
    positions = call_positions(body, name)
    return positions[0] if positions else -1


def call_arguments(body: str, name: str, position: int | None = None) -> str:
    start = call_index(body, name) if position is None else position
    if start < 0:
        raise SourceShapeError(f"missing call {name}")
    opening = body.find("(", start)
    closing = matching_delimiter(body, opening, "(", ")")
    return body[opening + 1 : closing]


def split_arguments(arguments: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depths = {"(": 0, "[": 0, "{": 0}
    pairs = {")": "(", "]": "[", "}": "{"}
    for index, char in enumerate(arguments):
        if char in depths:
            depths[char] += 1
        elif char in pairs:
            depths[pairs[char]] -= 1
        elif char == "," and all(depth == 0 for depth in depths.values()):
            parts.append(arguments[start:index].strip())
            start = index + 1
    parts.append(arguments[start:].strip())
    return parts


def normalized_expression(expression: str) -> str:
    return re.sub(r"\s+", "", expression)


def write_records(body: str, lvalue_pattern: str) -> list[tuple[int, str, str]]:
    """Return reachable writes to an lvalue as (position, operator, rhs)."""

    records: list[tuple[int, str, str]] = []
    escaped = rf"(?:{lvalue_pattern})"
    prefix = re.compile(rf"(?P<op>\+\+|--)\s*{escaped}")
    suffix = re.compile(
        rf"{escaped}\s*(?P<op>\+\+|--|<<=|>>=|\+=|-=|\*=|/=|%=|&=|\|=|\^=|=(?!=))"
    )
    for match in prefix.finditer(body):
        if position_is_reachable(body, match.start()):
            records.append((match.start(), match.group("op"), ""))
    for match in suffix.finditer(body):
        if not position_is_reachable(body, match.start()):
            continue
        operator = match.group("op")
        rhs = ""
        if operator.endswith("="):
            end = body.find(";", match.end())
            rhs = body[match.end() : end if end >= 0 else len(body)].strip()
        records.append((match.start(), operator, rhs))
    return sorted(records)


def exact_assignment(
    body: str, lvalue_pattern: str, rhs: str
) -> list[tuple[int, str, str]]:
    expected = normalized_expression(rhs)
    return [
        record
        for record in write_records(body, lvalue_pattern)
        if record[1] == "=" and normalized_expression(record[2]) == expected
    ]


def status_dataflow_intact(
    body: str, status_name: str, start: int, end: int
) -> bool:
    """Reject status overwrite/update/address escape before its guard."""

    if start < 0 or end < start:
        return False
    region = body[start:end]
    name = re.escape(status_name)
    write = rf"\b{name}\s*(?:\+\+|--|<<=|>>=|\+=|-=|\*=|/=|%=|&=|\|=|\^=|=(?!=))"
    prefix = rf"(?:\+\+|--)\s*\b{name}\b"
    # A pointer captured before the protected call can still overwrite its
    # result between the call and guard, so status address-taking is forbidden
    # throughout the function rather than only in the post-call slice.
    escape = rf"(?<!&)&(?!&)\s*(?:\(\s*)*\b{name}\b"
    return not re.search(escape, body) and not re.search(
        rf"(?:{write}|{prefix})", region
    )


def address_reference_count(body: str, lvalue_pattern: str) -> int:
    """Count reachable address-taking references to a protected lvalue."""

    return len(
        token_positions(
            body,
            rf"(?<!&)&(?!&)\s*(?:\(\s*)*(?:{lvalue_pattern})",
        )
    )


def has_nonindexed_array_reference(
    body: str, array_expression: str, index_expression: str
) -> bool:
    """Reject array decay/aliasing outside the required indexed element."""

    array = re.escape(array_expression)
    index = normalized_expression(index_expression)
    for match in re.finditer(array, body):
        if not position_is_reachable(body, match.start()):
            continue
        suffix = body[match.end() :]
        indexed = re.match(r"\s*\[([^]]+)\]", suffix)
        if indexed is None or normalized_expression(indexed.group(1)) != index:
            return True
    return False


def pointer_value_has_alias_reference(
    body: str,
    name: str,
    allowed_argument_calls: tuple[str, ...] = (),
) -> bool:
    """Reject bare pointer-value uses that can create an untracked output alias."""

    allowed_spans: list[tuple[int, int]] = []
    for call_name in allowed_argument_calls:
        for call in syntactic_call_positions(body, call_name):
            opening = body.find("(", call)
            closing = matching_delimiter(body, opening, "(", ")")
            allowed_spans.append((opening + 1, closing))

    for match in re.finditer(r"\b" + re.escape(name) + r"\b", body):
        position = match.start()
        if not position_is_reachable(body, position):
            continue
        if any(start <= position < end for start, end in allowed_spans):
            continue
        before = body[:position].rstrip()
        after = body[match.end() :].lstrip()
        if re.search(
            r"(?<!&)&(?!&)\s*(?:(?:\(\s*)?\*\s*)?$",
            before[-64:],
        ):
            return True
        if after.startswith("->") or after.startswith("["):
            continue
        if before.endswith("*") and not before.endswith("&*"):
            continue
        if after.startswith("==") or after.startswith("!="):
            continue
        if before.endswith("==") or before.endswith("!="):
            continue
        return True
    return False


def has_non_call_identifier_reference(source: str, name: str) -> bool:
    """Whether a reachable identifier use is not a direct syntactic call."""

    for match in re.finditer(r"\b" + re.escape(name) + r"\b", source):
        if not position_is_reachable(source, match.start()):
            continue
        if not source[match.end() :].lstrip().startswith("("):
            return True
    return False


def call_has_exact_arguments(body: str, name: str, expected: tuple[str, ...]) -> bool:
    positions = call_positions(body, name)
    if len(positions) != 1:
        return False
    actual = split_arguments(call_arguments(body, name, positions[0]))
    return [normalized_expression(value) for value in actual] == [
        normalized_expression(value) for value in expected
    ]


def call_is_compared_nonzero(body: str, name: str) -> bool:
    positions = call_positions(body, name)
    if len(positions) != 1:
        return False
    opening = body.find("(", positions[0])
    closing = matching_delimiter(body, opening, "(", ")")
    return re.match(r"\s*!=\s*0\b", body[closing + 1 :]) is not None


def condition_is_disabled(condition: str) -> bool:
    compact = re.sub(r"\s+", "", condition)
    return bool(
        compact in {"0", "FALSE", "(0)", "(FALSE)"}
        or re.search(r"(?:^|&&)\(?0\)?(?:&&|$)", compact)
        or re.search(r"(?:^|&&)\(?FALSE\)?(?:&&|$)", compact)
    )


def condition_is_constant_true(condition: str) -> bool:
    compact = re.sub(r"\s+", "", condition)
    return bool(
        compact in {"1", "TRUE", "(1)", "(TRUE)"}
        or re.search(r"(?:^|\|\|)\(?1\)?(?:\|\||$)", compact)
        or re.search(r"(?:^|\|\|)\(?TRUE\)?(?:\|\||$)", compact)
    )


def contains_constant_boolean_operand(expression: str) -> bool:
    compact = normalized_expression(expression)
    return re.search(
        r"(?:^|&&|\|\||\()(?:0|FALSE)(?:$|&&|\|\||\))", compact
    ) is not None


def condition_has_direct_positive_call(condition: str, name: str) -> bool:
    if call_count(condition, name) != 1 or "||" in condition or condition_is_disabled(condition):
        return False
    escaped = re.escape(name)
    rejected = (
        r"!\s*" + escaped,
        escaped + r"\s*\([^)]*\)\s*==\s*FALSE",
        escaped + r"\s*\([^)]*\)\s*!=\s*TRUE",
        r"FALSE\s*==\s*" + escaped,
        r"TRUE\s*!=\s*" + escaped,
    )
    return not any(re.search(pattern, condition) for pattern in rejected)


@dataclass(frozen=True)
class IfRegion:
    start: int
    end: int
    condition: str
    then_start: int
    then_end: int
    else_start: int | None
    else_end: int | None

    def contains_in_then(self, position: int) -> bool:
        return self.then_start <= position < self.then_end

    def contains_in_else(self, position: int) -> bool:
        return (
            self.else_start is not None
            and self.else_end is not None
            and self.else_start <= position < self.else_end
        )


@dataclass(frozen=True)
class LoopRegion:
    start: int
    end: int
    header: str
    body_start: int
    body_end: int

    def contains(self, position: int) -> bool:
        return self.body_start <= position < self.body_end


def if_regions(body: str) -> list[IfRegion]:
    regions: list[IfRegion] = []
    for match in re.finditer(r"\bif\s*\(", body):
        opening = body.find("(", match.start())
        closing = matching_delimiter(body, opening, "(", ")")
        cursor = skip_space(body, closing + 1)
        if cursor >= len(body) or body[cursor] != "{":
            continue
        then_end = matching_delimiter(body, cursor, "{", "}")
        end = then_end + 1
        else_start = None
        else_end = None
        after = skip_space(body, end)
        if re.match(r"else\b", body[after:]):
            else_cursor = skip_space(body, after + 4)
            if else_cursor < len(body) and body[else_cursor] == "{":
                else_close = matching_delimiter(body, else_cursor, "{", "}")
                else_start = else_cursor + 1
                else_end = else_close
                end = else_close + 1
        regions.append(
            IfRegion(
                match.start(),
                end,
                body[opening + 1 : closing],
                cursor + 1,
                then_end,
                else_start,
                else_end,
            )
        )
    return regions


def loop_regions(body: str) -> list[LoopRegion]:
    regions: list[LoopRegion] = []
    for match in re.finditer(r"\bfor\s*\(", body):
        opening = body.find("(", match.start())
        closing = matching_delimiter(body, opening, "(", ")")
        cursor = skip_space(body, closing + 1)
        if cursor >= len(body) or body[cursor] != "{":
            continue
        end = matching_delimiter(body, cursor, "{", "}")
        regions.append(
            LoopRegion(
                match.start(),
                end + 1,
                body[opening + 1 : closing],
                cursor + 1,
                end,
            )
        )
    return regions


def token_positions(body: str, token_pattern: str) -> list[int]:
    return [
        match.start()
        for match in re.finditer(token_pattern, body)
        if position_is_reachable(body, match.start())
    ]


def reachable_pattern(body: str, token_pattern: str) -> re.Match[str] | None:
    for match in re.finditer(token_pattern, body):
        if position_is_reachable(body, match.start()):
            return match
    return None


def effect_is_unconditional_in_range(
    body: str, start: int, end: int, token_pattern: str
) -> bool:
    """Whether a reachable effect is top-level in the accepted block."""

    for position in token_positions(body, token_pattern):
        if not (start <= position < end):
            continue
        nested_if = any(
            region.start >= start
            and region.end <= end
            and (region.contains_in_then(position) or region.contains_in_else(position))
            for region in if_regions(body)
        )
        nested_loop = any(
            loop.start >= start and loop.end <= end and loop.contains(position)
            for loop in loop_regions(body)
        )
        if not nested_if and not nested_loop:
            return True
    return False


def switch_case_bodies(body: str, selector: str, case_name: str) -> list[str]:
    cases: list[str] = []
    for match in re.finditer(r"\bswitch\s*\(", body):
        opening = body.find("(", match.start())
        closing = matching_delimiter(body, opening, "(", ")")
        if selector not in body[opening + 1 : closing]:
            continue
        cursor = skip_space(body, closing + 1)
        if cursor >= len(body) or body[cursor] != "{":
            continue
        end = matching_delimiter(body, cursor, "{", "}")
        switch_body = body[cursor + 1 : end]
        case = re.search(r"\bcase\s+" + re.escape(case_name) + r"\s*:", switch_body)
        if case is None:
            continue
        following = re.search(r"\b(?:case\s+[A-Za-z_]\w*|default)\s*:", switch_body[case.end() :])
        case_end = len(switch_body) if following is None else case.end() + following.start()
        cases.append(switch_body[case.end() : case_end])
    return cases


def switch_case_body(body: str, selector: str, case_name: str) -> str | None:
    cases = switch_case_bodies(body, selector, case_name)
    return cases[0] if cases else None


def function_definitions(source: str) -> dict[str, str]:
    code = sanitize_source(source)
    definitions: dict[str, str] = {}
    controls = {"if", "for", "while", "switch"}
    for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", code):
        name = match.group(1)
        if name in controls:
            continue
        try:
            opening = code.find("(", match.start())
            closing = matching_delimiter(code, opening, "(", ")")
            cursor = skip_space(code, closing + 1)
            if cursor < len(code) and code[cursor] == "{" and name not in definitions:
                end = matching_delimiter(code, cursor, "{", "}")
                definitions[name] = code[cursor + 1 : end]
        except SourceShapeError:
            # Preprocessor alternatives can make the unpreprocessed token stream
            # look unbalanced.  Skip that generic candidate; named extraction
            # still reports required definitions independently.
            continue
    return definitions


def reachable_call(source: str, root: str, target: str) -> bool:
    definitions = function_definitions(source)
    pending = [root]
    visited: set[str] = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        body = definitions.get(name, "")
        if call_count(body, target):
            return True
        for candidate in definitions:
            if candidate not in visited and call_count(body, candidate):
                pending.append(candidate)
    return False


def function_parameter_names(source: str, name: str) -> list[str]:
    """Return the declared parameter identifiers for a named definition."""

    code = sanitize_source(source)
    pattern = re.compile(r"\b" + re.escape(name) + r"\s*\(")
    for match in pattern.finditer(code):
        opening = code.find("(", match.start())
        closing = matching_delimiter(code, opening, "(", ")")
        cursor = skip_space(code, closing + 1)
        if cursor >= len(code) or code[cursor] != "{":
            continue
        parameters: list[str] = []
        for declaration in split_arguments(code[opening + 1 : closing]):
            identifiers = re.findall(r"\b[A-Za-z_]\w*\b", declaration)
            if not identifiers or identifiers == ["void"]:
                continue
            parameters.append(identifiers[-1])
        return parameters
    raise SourceShapeError(f"missing function definition {name}")


def expression_references_any_name(
    expression: str, names: set[str]
) -> bool:
    return any(
        re.search(r"\b" + re.escape(name) + r"\b", expression)
        for name in names
    )


def position_is_nested_in_control(body: str, position: int) -> bool:
    return any(
        region.contains_in_then(position) or region.contains_in_else(position)
        for region in if_regions(body)
    ) or any(loop.contains(position) for loop in loop_regions(body))


def local_value_aliases_at(
    body: str, seed_names: set[str], before: int, after: int = 0
) -> set[str]:
    """Track primary aliases in statement order, including clean reassignment."""

    aliases = set(seed_names)
    for assignment in re.finditer(
        r"\b([A-Za-z_]\w*)\s*=(?!=)\s*([^;]+);", body[after:before]
    ):
        position = after + assignment.start()
        if not position_is_reachable(body, position):
            continue
        target = assignment.group(1)
        if expression_references_any_name(assignment.group(2), aliases):
            aliases.add(target)
        elif not position_is_nested_in_control(body, position):
            aliases.discard(target)
    return aliases


def callable_alias_assignments(body: str) -> list[tuple[int, str, str]]:
    """Return local direct/function-pointer assignments in source order."""

    assignments: list[tuple[int, str, str]] = []
    covered: list[tuple[int, int]] = []
    pointer_pattern = re.compile(
        r"\(\s*\*\s*([A-Za-z_]\w*)\s*\)\s*\([^;=]*\)\s*=\s*([^;]+);"
    )
    for match in pointer_pattern.finditer(body):
        assignments.append((match.start(), match.group(1), match.group(2)))
        covered.append((match.start(), match.end()))
    for match in re.finditer(
        r"\b([A-Za-z_]\w*)\s*=(?!=)\s*([^;]+);", body
    ):
        if any(start <= match.start() < end for start, end in covered):
            continue
        assignments.append((match.start(), match.group(1), match.group(2)))
    return sorted(assignments)


def strip_balanced_outer_parentheses(expression: str) -> str:
    value = expression.strip()
    while value.startswith("("):
        try:
            closing = matching_delimiter(value, 0, "(", ")")
        except SourceShapeError:
            break
        if closing != len(value) - 1:
            break
        value = value[1:closing].strip()
    return value


def local_callable_aliases_at(
    body: str, function_names: set[str], before: int
) -> dict[str, set[str]]:
    """Resolve local callable aliases in statement order."""

    assignments = callable_alias_assignments(body)
    all_ifs = if_regions(body)
    all_loops = loop_regions(body)

    def rhs_targets(
        rhs: str, aliases: dict[str, set[str]]
    ) -> set[str]:
        targets: set[str] = set()
        for identifier in re.findall(r"\b[A-Za-z_]\w*\b", rhs):
            if identifier in aliases:
                targets.update(aliases[identifier])
            elif identifier in function_names:
                targets.add(identifier)
        return targets

    def merge_states(
        left: dict[str, set[str]], right: dict[str, set[str]]
    ) -> dict[str, set[str]]:
        return {
            name: set(left.get(name, set())) | set(right.get(name, set()))
            for name in set(left) | set(right)
            if left.get(name) or right.get(name)
        }

    def analyze_range(
        start: int,
        end: int,
        incoming: dict[str, set[str]],
    ) -> dict[str, set[str]]:
        state = {name: set(targets) for name, targets in incoming.items()}
        controls: list[tuple[int, int, object]] = []
        candidates: list[tuple[int, int, object]] = [
            (region.start, region.end, region)
            for region in all_ifs
            if start <= region.start < end
        ] + [
            (region.start, region.end, region)
            for region in all_loops
            if start <= region.start < end
        ]
        for candidate in candidates:
            if not any(
                other[0] <= candidate[0]
                and candidate[1] <= other[1]
                and other != candidate
                for other in candidates
            ):
                controls.append(candidate)
        events: list[tuple[int, int, object]] = [
            (control_start, 1, control)
            for control_start, _, control in controls
        ]
        for position, target, rhs in assignments:
            if not (start <= position < end):
                continue
            if any(
                control_start <= position < control_end
                for control_start, control_end, _ in controls
            ):
                continue
            events.append((position, 0, (target, rhs)))
        for _, event_kind, payload in sorted(
            events, key=lambda event: (event[0], event[1])
        ):
            if event_kind == 0:
                target, rhs = payload
                targets = rhs_targets(
                    strip_balanced_outer_parentheses(rhs), state
                )
                if targets:
                    state[target] = targets
                else:
                    state.pop(target, None)
                continue
            control = payload
            if isinstance(control, IfRegion):
                if control.end > end:
                    if control.then_start <= end < control.then_end:
                        state = analyze_range(control.then_start, end, state)
                    elif (
                        control.else_start is not None
                        and control.else_end is not None
                        and control.else_start <= end < control.else_end
                    ):
                        state = analyze_range(control.else_start, end, state)
                    continue
                then_state = analyze_range(
                    control.then_start, control.then_end, state
                )
                else_state = (
                    analyze_range(control.else_start, control.else_end, state)
                    if control.else_start is not None
                    and control.else_end is not None
                    else state
                )
                state = merge_states(then_state, else_state)
            else:
                if control.end > end:
                    if control.body_start <= end < control.body_end:
                        state = analyze_range(control.body_start, end, state)
                    continue
                loop_state = analyze_range(
                    control.body_start, control.body_end, state
                )
                state = merge_states(state, loop_state)
        return state

    return analyze_range(0, before, {})


def resolved_helper_calls(
    body: str, function_names: set[str]
) -> list[tuple[int, str, str]]:
    """Return direct and locally aliased helper calls as (position,target,args)."""

    calls: list[tuple[int, str, str]] = []
    candidates = set(function_names)
    candidates.update(
        target for _, target, _ in callable_alias_assignments(body)
    )
    for called_name in candidates:
        call_sites = [
            (
                position,
                call_arguments(body, called_name, position),
            )
            for position in call_positions(body, called_name)
        ]
        dereference_call = re.compile(
            r"\(\s*\*\s*" + re.escape(called_name) + r"\s*\)\s*\("
        )
        for match in dereference_call.finditer(body):
            if not position_is_reachable(body, match.start()):
                continue
            arguments_opening = body.rfind("(", match.start(), match.end())
            arguments_closing = matching_delimiter(
                body, arguments_opening, "(", ")"
            )
            call_sites.append(
                (
                    match.start(),
                    body[arguments_opening + 1 : arguments_closing],
                )
            )
        for position, argument_text in call_sites:
            targets = {called_name}
            if called_name not in function_names:
                targets = local_callable_aliases_at(
                    body, function_names, position
                ).get(called_name, set())
            for target in targets:
                calls.append(
                    (
                        position,
                        target,
                        argument_text,
                    )
                )
    return sorted(calls)


def tainted_delete_reachable(
    source: str,
    root: str,
    tainted_parameter_indexes: set[int],
    visited: set[tuple[str, tuple[int, ...]]] | None = None,
) -> bool:
    """Follow a primary-object value through helpers to DeleteMapObject."""

    if not tainted_parameter_indexes:
        return False
    if visited is None:
        visited = set()
    key = (root, tuple(sorted(tainted_parameter_indexes)))
    if key in visited:
        return False
    visited.add(key)
    definitions = function_definitions(source)
    body = definitions.get(root)
    if body is None:
        return False
    parameters = function_parameter_names(source, root)
    seed_names = {
        parameters[index]
        for index in tainted_parameter_indexes
        if index < len(parameters)
    }
    for delete_call in call_positions(body, "DeleteMapObject"):
        aliases = local_value_aliases_at(body, seed_names, delete_call)
        if expression_references_any_name(
            call_arguments(body, "DeleteMapObject", delete_call), aliases
        ):
            return True
    for helper_call, helper_name, argument_text in resolved_helper_calls(
        body, set(definitions)
    ):
        aliases = local_value_aliases_at(body, seed_names, helper_call)
        arguments = split_arguments(argument_text)
        tainted = {
            index
            for index, argument in enumerate(arguments)
            if expression_references_any_name(argument, aliases)
        }
        if tainted and tainted_delete_reachable(
            source, helper_name, tainted, visited
        ):
            return True
    return False


def has_nonzero_advance(body: str, expression: str, before: int | None = None) -> bool:
    region = body if before is None else body[:before]
    escaped = re.escape(expression)
    direct = reachable_pattern(
        region,
        escaped
        + r"\s*(?:\+\+|\+=\s*1\b|=\s*"
        + escaped
        + r"\s*\+\s*1\b)",
    )
    helper = reachable_pattern(
        region,
        r"\bOverworldWildSpawns_AdvanceNonzeroGeneration\s*\(\s*&\s*"
        + escaped,
    )
    if direct is None and helper is None:
        return False
    if helper is not None:
        return True
    advance_end = direct.end() if direct is not None else 0
    zero_test = reachable_pattern(region, escaped + r"\s*==\s*0")
    normalize = reachable_pattern(region, escaped + r"\s*=\s*1\b")
    return bool(
        zero_test
        and normalize
        and zero_test.start() > advance_end
        and normalize.start() > zero_test.start()
    )


def has_failure_guard(
    body: str,
    call_name: str,
    before_action: int,
    exit_word: str = "return",
    allow_idempotent: bool = False,
) -> bool:
    call = call_index(body, call_name)
    if call < 0:
        return False
    status_name = assigned_status_name(body, call)
    if status_name is None:
        return False
    opening = body.find("(", call)
    call_end = matching_delimiter(body, opening, "(", ")") + 1
    for region in if_regions(body):
        if not (call < region.start < before_action):
            continue
        if not status_dataflow_intact(
            body, status_name, call_end, region.start
        ):
            continue
        condition = region.condition
        compact = normalized_expression(condition).strip("()")
        ordinary = compact == f"{status_name}!={OK}"
        idempotent_parts = {
            f"{status_name}!={OK}",
            f"{status_name}!={IDEMPOTENT}",
        }
        idempotent = set(compact.split("&&")) == idempotent_parts and "||" not in compact
        if condition_is_disabled(condition):
            continue
        if allow_idempotent and not idempotent:
            continue
        if not allow_idempotent and not ordinary:
            continue
        if effect_is_unconditional_in_range(
            body,
            region.then_start,
            region.then_end,
            r"\b" + re.escape(exit_word) + r"\b",
        ):
            return True
    return False


def assigned_status_name(body: str, call_position: int) -> str | None:
    statement_start = max(
        body.rfind(";", 0, call_position), body.rfind("{", 0, call_position)
    ) + 1
    assignment = re.search(
        r"\b([A-Za-z_]\w*)\s*=\s*$", body[statement_start:call_position]
    )
    return None if assignment is None else assignment.group(1)


@dataclass
class Verification:
    source: str

    def __post_init__(self) -> None:
        self.code = sanitize_source(self.source)
        self.issues: list[str] = []

    def issue(self, category: str, message: str) -> None:
        self.issues.append(f"[{category}] {message}")

    def body(self, name: str, category: str) -> str | None:
        try:
            return function_body(self.code, name)
        except SourceShapeError as error:
            self.issue(category, str(error))
            return None

    def verify_identity_construction(
        self,
        body: str,
        stage_index: int,
        assignments: dict[str, str],
        category: str,
        operation: str,
    ) -> None:
        zero_calls: list[int] = []
        for position in call_positions(body, "memset"):
            arguments = split_arguments(
                call_arguments(body, "memset", position)
            )
            if arguments and normalized_expression(arguments[0]) == "&identity":
                zero_calls.append(position)
                if [normalized_expression(value) for value in arguments] != [
                    "&identity", "0", "sizeof(identity)"
                ]:
                    self.issue(
                        category,
                        f"{operation} identity must use exact zero construction",
                    )
        if len(zero_calls) != 1 or zero_calls[0] >= stage_index:
            self.issue(
                category,
                f"{operation} identity must be zero-constructed exactly once before Stage A",
            )
            zero_position = -1
        else:
            zero_position = zero_calls[0]

        ordered_positions: list[int] = []
        expected_total = len(assignments)
        for field, rhs in assignments.items():
            lvalue = rf"identity\s*\.\s*{re.escape(field)}"
            writes = write_records(body, lvalue)
            exact = exact_assignment(body, lvalue, rhs)
            if (
                len(writes) != 1
                or len(exact) != 1
                or not (zero_position < exact[0][0] < stage_index)
            ):
                self.issue(
                    category,
                    f"{operation} identity must write current {field} exactly once in construction order",
                )
            else:
                ordered_positions.append(exact[0][0])
        all_member_writes = write_records(
            body, r"identity\s*\.\s*[A-Za-z_]\w*"
        )
        if len(all_member_writes) != expected_total:
            self.issue(
                category,
                f"{operation} identity contains an extra field rewrite",
            )
        if write_records(body, r"\bidentity\b"):
            self.issue(
                category,
                f"{operation} identity must not be overwritten as a whole",
            )
        if len(ordered_positions) == expected_total and ordered_positions != sorted(
            ordered_positions
        ):
            self.issue(
                category,
                f"{operation} identity field construction order drifted",
            )
        pre_stage_escapes = token_positions(body[:stage_index], r"&\s*identity\b")
        if len(pre_stage_escapes) != 1:
            self.issue(
                category,
                f"{operation} identity escapes before the authenticated Stage A call",
            )

    def verify(self) -> list[str]:
        self.verify_layout()
        self.verify_capture_wrapper()
        self.verify_consume_wrapper()
        self.verify_invalidation_wrappers_and_sites()
        self.verify_publication_sites()
        self.verify_canonical_initialization()
        self.verify_projection()
        self.verify_routes()
        self.verify_frame_timers()
        self.verify_legacy_timer_ownership()
        self.verify_liveness()
        self.verify_postcommit_apply()
        return self.issues

    def verify_layout(self) -> None:
        category = "runtime-layout"
        try:
            body = struct_body(self.code, "OverworldWildOverlayRuntimeState")
        except SourceShapeError as error:
            self.issue(category, str(error))
            return
        declarations = {
            "movementCommandGenerations": r"\bu32\s+movementCommandGenerations\s*\[\s*OW_WILD_MAX_SPAWNS\s*\]\s*;",
            "movementCommandSerials": r"\bu32\s+movementCommandSerials\s*\[\s*OW_WILD_MAX_SPAWNS\s*\]\s*;",
            "movementObjectGenerations": r"\bu32\s+movementObjectGenerations\s*\[\s*OW_WILD_MAX_SPAWNS\s*\]\s*;",
            "movementCommandOrigins": r"\bOverworldWildRuntimeCommandOriginBank\s+movementCommandOrigins\s*;",
            "behaviorStackRuntime": r"\bOverworldWildBehaviorStackRuntime\s+behaviorStackRuntime\s*;",
        }
        positions: dict[str, int] = {}
        for field, pattern in declarations.items():
            match = reachable_pattern(body, pattern)
            positions[field] = -1 if match is None else match.start()
            if match is None:
                self.issue(category, f"runtime state is missing the exact {field} carrier")
        if all(position >= 0 for position in positions.values()):
            ordered = [
                positions["movementCommandGenerations"],
                positions["movementCommandSerials"],
                positions["movementObjectGenerations"],
                positions["movementCommandOrigins"],
                positions["behaviorStackRuntime"],
            ]
            if ordered != sorted(ordered):
                self.issue(category, "command identity/origin carriers must precede the resident suffix")
            if re.search(declarations["behaviorStackRuntime"] + r"\s*$", body) is None:
                self.issue(category, "behaviorStackRuntime must remain the final runtime field")

    def verify_capture_wrapper(self) -> None:
        category = "capture-wrapper"
        body = self.body(CAPTURE_HELPER, category)
        if body is None:
            return
        stage = "OverworldWildRuntime_CaptureCommandOrigin"
        stage_index = call_index(body, stage)
        if call_count(body, stage) != 1:
            self.issue(category, "capture wrapper must call the Stage A capture exactly once")
        if stage_index < 0:
            return
        if not call_has_exact_arguments(body, "OW_WILD_RUNTIME", ("state",)):
            self.issue(category, "capture must derive its runtime from the current state")
        if not call_has_exact_arguments(
            body,
            stage,
            (
                "&runtime->behaviorStackRuntime",
                "&runtime->movementCommandOrigins",
                "slot",
                "slotGeneration",
                "&identity",
            ),
        ):
            self.issue(category, "capture Stage A arguments must use current runtime/slot/generation/identity")
        get_cache = "OverworldWildRuntime_GetEffectiveCache"
        get_index = call_index(body, get_cache)
        first_advance = body.find("nextCommandGeneration = runtime->movementCommandGenerations[slot]")
        if call_count(body, get_cache) != 1 or get_index > first_advance:
            self.issue(category, "capture must authenticate effective identity before generation advance")
        elif not has_failure_guard(body, get_cache, first_advance):
            self.issue(category, "capture must reject non-OK effective-cache status")
        if not call_has_exact_arguments(
            body,
            get_cache,
            ("&runtime->behaviorStackRuntime", "slot", "slotGeneration", "&effective"),
        ):
            self.issue(category, "capture effective-cache query uses unrelated identity arguments")
        if address_reference_count(body, r"effective") != 1:
            self.issue(category, "capture effective-cache output must not acquire an alias")
        next_values = (
            ("nextCommandGeneration", "runtime->movementCommandGenerations[slot]"),
            ("nextCommandSerial", "runtime->movementCommandSerials[slot]"),
        )
        for local, carrier in next_values:
            if carrier not in body[:stage_index] or not has_nonzero_advance(
                body, local, stage_index
            ):
                self.issue(category, f"capture must prepare a nonzero advanced {local}")
        assignments = {
            "commandGeneration": "nextCommandGeneration",
            "commandSerial": "nextCommandSerial",
            "objectGeneration": "runtime->movementObjectGenerations[slot]",
            "staminaPolicyGeneration": "effective.effectiveGeneration",
            "staminaPolicyId": "effective.controllerId",
        }
        self.verify_identity_construction(
            body, stage_index, assignments, category, "capture"
        )
        after = body[stage_index:]
        success = re.search(r"\breturn\s+TRUE\s*;", after)
        success_index = len(body) if success is None else stage_index + success.start()
        if success is None or not has_failure_guard(body, stage, success_index):
            self.issue(category, "capture wrapper must return success only after an explicit OK status")
        for local, carrier in next_values:
            publication = reachable_pattern(
                body,
                re.escape(carrier) + r"\s*=\s*" + re.escape(local) + r"\s*;",
            )
            if (
                publication is None
                or publication.start() < stage_index
                or publication.start() > success_index
                or not has_failure_guard(body, stage, publication.start())
            ):
                self.issue(
                    category,
                    f"capture must publish {carrier} only after Stage A returns OK",
                )

    def verify_consume_wrapper(self) -> None:
        category = "consume-wrapper"
        body = self.body(CONSUME_HELPER, category)
        if body is None:
            return
        stage = "OverworldWildRuntime_ConsumeCommandOrigin"
        stage_index = call_index(body, stage)
        if call_count(body, stage) != 1:
            self.issue(category, "consume wrapper must call the Stage A consume exactly once")
        if stage_index < 0:
            return
        if not call_has_exact_arguments(body, "OW_WILD_RUNTIME", ("state",)):
            self.issue(category, "consume must derive its runtime from the current state")
        if not call_has_exact_arguments(
            body,
            stage,
            (
                "&runtime->behaviorStackRuntime",
                "&runtime->movementCommandOrigins",
                "slot",
                "slotGeneration",
                "&identity",
                "originOut",
            ),
        ):
            self.issue(category, "consume Stage A arguments must authenticate current identity/output")
        get_cache = "OverworldWildRuntime_GetEffectiveCache"
        get_index = call_index(body, get_cache)
        if call_count(body, get_cache) != 1 or get_index > stage_index:
            self.issue(category, "consume must authenticate current effective identity before Stage A")
        elif not has_failure_guard(body, get_cache, stage_index):
            self.issue(category, "consume must reject non-OK effective-cache status")
        if not call_has_exact_arguments(
            body,
            get_cache,
            ("&runtime->behaviorStackRuntime", "slot", "slotGeneration", "&effective"),
        ):
            self.issue(category, "consume effective-cache query uses unrelated identity arguments")
        if address_reference_count(body, r"effective") != 1:
            self.issue(category, "consume effective-cache output must not acquire an alias")
        if pointer_value_has_alias_reference(body, "originOut", (stage,)):
            self.issue(category, "consume output pointer must not acquire an alias")
        assignments = {
            "commandGeneration": "runtime->movementCommandGenerations[slot]",
            "commandSerial": "runtime->movementCommandSerials[slot]",
            "objectGeneration": "runtime->movementObjectGenerations[slot]",
            "staminaPolicyGeneration": "effective.effectiveGeneration",
            "staminaPolicyId": "effective.controllerId",
        }
        self.verify_identity_construction(
            body, stage_index, assignments, category, "consume"
        )
        opening = body.find("(", stage_index)
        closing = matching_delimiter(body, opening, "(", ")")
        if "originOut" not in body[opening:closing]:
            self.issue(category, "authenticated Stage A origin is not returned to the caller")
        success = re.search(r"\breturn\s+TRUE\s*;", body[stage_index:])
        success_index = len(body) if success is None else stage_index + success.start()
        if success is None or not has_failure_guard(body, stage, success_index):
            self.issue(category, "consume wrapper must reject stale/non-OK origin status")

    def verify_invalidation_wrappers_and_sites(self) -> None:
        category = "origin-invalidation"
        slot_wrapper = self.body(INVALIDATE_HELPER, category)
        if slot_wrapper is not None:
            stage = "OverworldWildRuntime_InvalidateCommandOrigin"
            stage_index = call_index(slot_wrapper, stage)
            if call_count(slot_wrapper, stage) != 1:
                self.issue(category, "slot invalidator must call Stage A invalidation exactly once")
            if stage_index >= 0:
                carrier = "runtime->movementCommandGenerations[slot]"
                if not has_nonzero_advance(slot_wrapper, carrier):
                    self.issue(category, "slot invalidation must advance command generation nonzero")
                elif slot_wrapper.find(carrier) < stage_index:
                    self.issue(category, "slot lifecycle advance must follow Stage A invalidation")
                zero = slot_wrapper.find("runtime->movementCommandSerials[slot] = 0")
                if zero < stage_index or not position_is_reachable(slot_wrapper, zero):
                    self.issue(category, "slot invalidation must clear command serial after Stage A invalidation")

        bulk_wrapper = self.body(INVALIDATE_ALL_HELPER, category)
        if bulk_wrapper is not None:
            stage = "OverworldWildRuntime_InvalidateAllCommandOrigins"
            stage_index = call_index(bulk_wrapper, stage)
            if call_count(bulk_wrapper, stage) != 1:
                self.issue(category, "bulk invalidator must call Stage A invalidation exactly once")
            if not re.search(r"\bfor\s*\([^;]*;[^;]*OW_WILD_MAX_SPAWNS", bulk_wrapper):
                self.issue(category, "bulk invalidation must visit every slot with a bounded loop")
            if not has_nonzero_advance(
                bulk_wrapper, "runtime->movementCommandGenerations[slot]"
            ):
                self.issue(category, "bulk invalidation must advance every command generation")
            elif bulk_wrapper.find("runtime->movementCommandGenerations[slot]") < stage_index:
                self.issue(category, "bulk lifecycle advances must follow Stage A invalidation")
            if "runtime->movementCommandSerials[slot] = 0" not in bulk_wrapper:
                self.issue(category, "bulk invalidation must clear every command serial")
            else:
                serial_clear = bulk_wrapper.find("runtime->movementCommandSerials[slot] = 0")
                if not position_is_reachable(bulk_wrapper, serial_clear):
                    self.issue(category, "bulk command-serial clear is unreachable")

        for function in (
            "OverworldWildSpawns_ResetSlotMovementCommand",
            "OverworldWildSpawns_ClearStagedHopMovementListTask",
            "OverworldWildSpawns_CancelNativeHeldMovementForSlot",
            "OverworldWildSpawns_ResetSlotState",
        ):
            body = self.body(function, category)
            if body is not None and call_count(body, INVALIDATE_HELPER) == 0:
                self.issue(category, f"{function} must invalidate its slot command origin")
        for function in (
            "OverworldWildSpawns_ResetAllMovementCommands",
            "OverworldWildSpawns_DetachAllMovementStateOnContextLoss",
        ):
            body = self.body(function, category)
            if body is not None and call_count(body, INVALIDATE_ALL_HELPER) == 0:
                self.issue(category, f"{function} must invalidate all command origins")

        replacement = self.body("OverworldWildSpawns_RecreateSpawnObjectAtTile", category)
        if replacement is not None:
            invalidate = call_index(replacement, INVALIDATE_HELPER)
            publication = replacement.find("state->spawns[slot].object = replacement")
            if invalidate < 0:
                self.issue(category, "object replacement must invalidate its command origin")
            if publication < 0:
                self.issue(category, "object replacement publication was not recognized")
            else:
                if invalidate > publication:
                    self.issue(category, "object invalidation must precede replacement publication")
                if not has_nonzero_advance(
                    replacement,
                    "runtime->movementObjectGenerations[slot]",
                    publication,
                ):
                    self.issue(category, "object generation must advance nonzero before replacement")

    def verify_publication_sites(self) -> None:
        category = "capture-before-publication"
        sites = (
            ("OverworldWildSpawns_StartMovementCommandForSlot", "MapObject_StartMovementCommandInternal"),
            ("OverworldWildSpawns_TryStartPhantomTeleportToTile", "OverworldWildSpawns_SetObjectTile"),
            ("OverworldWildSpawns_StartPreparedCustomJumpCommand", "MapObject_StartMovementCommand"),
            ("OverworldWildSpawns_StartWrappedCanopyJump2Probe", "MapObject_StartMovementList"),
        )
        for function, publication in sites:
            body = self.body(function, category)
            if body is None:
                continue
            capture_positions = call_positions(body, CAPTURE_HELPER)
            publication_index = call_index(body, publication)
            if len(capture_positions) != 1:
                self.issue(category, f"{function} must capture exactly once")
                continue
            capture = capture_positions[0]
            if publication_index < 0:
                self.issue(category, f"{function} publication call {publication} was not recognized")
                continue
            guarded = False
            for region in if_regions(body):
                if CAPTURE_HELPER not in region.condition:
                    continue
                negative = bool(
                    re.search(r"!\s*" + re.escape(CAPTURE_HELPER), region.condition)
                    or re.search(re.escape(CAPTURE_HELPER) + r"[^)]*\)\s*==\s*FALSE", region.condition)
                )
                exits = effect_is_unconditional_in_range(
                    body,
                    region.then_start,
                    region.then_end,
                    r"\breturn\b",
                )
                if (
                    negative
                    and not condition_is_disabled(region.condition)
                    and exits
                    and region.end < publication_index
                ):
                    guarded = True
            if not guarded:
                self.issue(
                    category,
                    f"{function} must abort failed capture before publishing {publication}",
                )
            if capture > publication_index:
                self.issue(category, f"{function} captures after command publication")

    def verify_canonical_initialization(self) -> None:
        category = "canonical-initialization"
        body = self.body("OverworldWildSpawns_InitSpawnSlotState", category)
        if body is None:
            return
        assignment_match = reachable_pattern(body, r"state->spawns\[slot\]\s*=\s*spawn")
        behavior_match = reachable_pattern(body, r"state->movementBehaviorClasses\[slot\]\s*=")
        limit_match = reachable_pattern(body, r"movementBehaviorLimitKeys\[slot\]\s*=")
        assignment = -1 if assignment_match is None else assignment_match.start()
        behavior = -1 if behavior_match is None else behavior_match.start()
        limit_key = -1 if limit_match is None else limit_match.start()
        mark = call_index(body, "OverworldWildRuntime_MarkSlotAssigned")
        prime = call_index(body, "OverworldWildRuntime_PrimeCanonicalEffectiveCache")
        if not call_has_exact_arguments(body, "OW_WILD_RUNTIME", ("state",)):
            self.issue(category, "assignment must derive the current runtime from state")
        if min(assignment, behavior, limit_key, mark) < 0:
            self.issue(category, "assignment/context publication markers are incomplete")
        if "OverworldWildRuntimeStaticContext" not in body:
            self.issue(category, "canonical priming must use a complete static context")
        if prime < 0:
            self.issue(category, "new encounter assignment must prime the canonical effective cache")
            return
        if not call_has_exact_arguments(
            body,
            "OverworldWildRuntime_PrimeCanonicalEffectiveCache",
            (
                "&runtime->behaviorStackRuntime",
                "slot",
                "slotGeneration",
                "&staticContext",
                "&resolved",
            ),
        ):
            self.issue(category, "canonical prime must use current runtime/slot/generation/context/output")
        static_context_zeroes = 0
        for zero_call in call_positions(body, "memset"):
            zero_arguments = split_arguments(
                call_arguments(body, "memset", zero_call)
            )
            if (
                zero_arguments
                and normalized_expression(zero_arguments[0]) == "&staticContext"
            ):
                static_context_zeroes += 1
        if (
            address_reference_count(body, r"staticContext")
                != 2 + static_context_zeroes
            or address_reference_count(body, r"resolved") != 1
        ):
            self.issue(
                category,
                "canonical context/output values must not acquire aliases around priming",
            )
        builder_position = -1
        for match in re.finditer(r"\b[A-Za-z_]\w*Build[A-Za-z_]*StaticContext\s*\(", body):
            if not position_is_reachable(body, match.start()):
                continue
            name = re.match(r"[A-Za-z_]\w*", body[match.start() :]).group(0)
            if split_arguments(call_arguments(body, name, match.start())) == ["&staticContext"]:
                builder_position = match.start()
                break
        if builder_position < max(assignment, behavior, limit_key, mark) or builder_position > prime:
            self.issue(category, "BuildStaticContext(&staticContext) must dominate prime after publication")
        if max(assignment, behavior, limit_key, mark) > prime:
            self.issue(category, "canonical cache must be primed after assignment and context publication")
        if assignment >= 0 and not has_nonzero_advance(
            body, "runtime->movementObjectGenerations[slot]", assignment
        ):
            self.issue(category, "new object assignment must prime a nonzero object generation")
        failure_region = None
        prime_status = assigned_status_name(body, prime)
        prime_opening = body.find("(", prime)
        prime_call_end = matching_delimiter(
            body, prime_opening, "(", ")"
        ) + 1
        for region in if_regions(body):
            compact = normalized_expression(region.condition).strip("()")
            expected = {
                f"{prime_status}!={OK}",
                f"{prime_status}!={IDEMPOTENT}",
            }
            if (
                prime < region.start
                and prime_status is not None
                and status_dataflow_intact(
                    body, prime_status, prime_call_end, region.start
                )
                and set(compact.split("&&")) == expected
                and "||" not in compact
                and not condition_is_disabled(region.condition)
            ):
                failure_region = region
                break
        if failure_region is None:
            self.issue(category, "canonical prime status must accept OK/IDEMPOTENT and reject failure")
        else:
            failure = body[failure_region.then_start : failure_region.then_end]
            reset_positions = call_positions(body, "OverworldWildSpawns_ResetSlotState")
            reset_ok = any(
                failure_region.then_start <= position < failure_region.then_end
                and effect_is_unconditional_in_range(
                    body,
                    failure_region.then_start,
                    failure_region.then_end,
                    r"\bOverworldWildSpawns_ResetSlotState\s*\(",
                )
                for position in reset_positions
            )
            return_ok = effect_is_unconditional_in_range(
                body,
                failure_region.then_start,
                failure_region.then_end,
                r"\breturn\b",
            )
            reset_in_branch = [
                position
                for position in reset_positions
                if failure_region.then_start <= position < failure_region.then_end
            ]
            returns_in_branch = [
                position
                for position in token_positions(body, r"\breturn\b")
                if failure_region.then_start <= position < failure_region.then_end
            ]
            ordered = bool(
                reset_in_branch
                and returns_in_branch
                and min(reset_in_branch) < min(returns_in_branch)
            )
            if not reset_ok or not return_ok or not ordered:
                self.issue(category, "failed canonical priming must roll back and not expose the spawn")

        caller = self.body("OverworldWildSpawns_SpawnPreparedEncounter", category)
        if caller is None:
            return
        init_name = "OverworldWildSpawns_InitSpawnSlotState"
        init_positions = call_positions(caller, init_name)
        init_arguments = (
            "state",
            "fieldSystem",
            "terrain",
            "slot",
            "object",
            "encounter",
            "prepared->shiny",
            "prepared->behaviorClass",
            "prepared->behaviorLimitKey",
            "prepared->playerBallCatchValue",
        )
        if not call_has_exact_arguments(
            caller,
            init_name,
            init_arguments,
        ):
            self.issue(
                category,
                "spawn caller must initialize exactly one slot from the newly created object",
            )
            return
        init = init_positions[0]
        rollback_region = None
        expected_condition = (
            "!"
            + init_name
            + "("
            + ",".join(normalized_expression(value) for value in init_arguments)
            + ")"
        )
        for region in if_regions(caller):
            if not (region.start <= init < region.then_start):
                continue
            if normalized_expression(region.condition) == expected_condition:
                rollback_region = region
                break
        if rollback_region is None:
            self.issue(
                category,
                "spawn caller must own an exact failure branch for slot initialization",
            )
            return

        delete_positions = call_positions(caller, "DeleteMapObject")
        perf_positions = call_positions(caller, "OW_WILD_PERF_INC")
        branch_delete = [
            position
            for position in delete_positions
            if rollback_region.then_start <= position < rollback_region.then_end
        ]
        branch_perf = [
            position
            for position in perf_positions
            if rollback_region.then_start <= position < rollback_region.then_end
        ]
        branch_returns = [
            match
            for match in re.finditer(r"\breturn\s+([A-Za-z_]\w*|[0-9]+)\s*;", caller)
            if position_is_reachable(caller, match.start())
            if rollback_region.then_start <= match.start() < rollback_region.then_end
        ]
        false_returns = [
            match for match in branch_returns if match.group(1) == "FALSE"
        ]
        exact_delete = bool(
            len(delete_positions) == 1
            and len(branch_delete) == 1
            and normalized_expression(
                call_arguments(caller, "DeleteMapObject", branch_delete[0])
            ) == "object"
            and effect_is_unconditional_in_range(
                caller,
                rollback_region.then_start,
                rollback_region.then_end,
                r"\bDeleteMapObject\s*\(",
            )
            and not has_non_call_identifier_reference(
                self.code, "DeleteMapObject"
            )
        )
        exact_accounting = bool(
            len(perf_positions) == 1
            and len(branch_perf) == 1
            and normalized_expression(
                call_arguments(caller, "OW_WILD_PERF_INC", branch_perf[0])
            ) == "sOverworldWildPerfMapObjectDeletesThisFrame"
            and effect_is_unconditional_in_range(
                caller,
                rollback_region.then_start,
                rollback_region.then_end,
                r"\bOW_WILD_PERF_INC\s*\(",
            )
        )
        delete_counter_positions = token_positions(
            caller, r"\bsOverworldWildPerfMapObjectDeletesThisFrame\b"
        )
        if branch_perf:
            perf_opening = caller.find("(", branch_perf[0])
            perf_closing = matching_delimiter(caller, perf_opening, "(", ")")
        else:
            perf_opening = perf_closing = -1
        exact_accounting = bool(
            exact_accounting
            and len(delete_counter_positions) == 1
            and perf_opening < delete_counter_positions[0] < perf_closing
        )
        success_reaches_primary_delete = False
        definitions = function_definitions(self.code)
        for helper_call, helper_name, argument_text in resolved_helper_calls(
            caller, set(definitions)
        ):
            if helper_call < rollback_region.end:
                continue
            primary_aliases = local_value_aliases_at(
                caller, {"object"}, helper_call, rollback_region.end
            )
            tainted_arguments = {
                index
                for index, argument in enumerate(
                    split_arguments(argument_text)
                )
                if expression_references_any_name(
                    argument, primary_aliases
                )
            }
            if tainted_delete_reachable(
                self.code, helper_name, tainted_arguments
            ):
                success_reaches_primary_delete = True
        exact_failure_return = bool(
            len(branch_returns) == 1
            and len(false_returns) == 1
            and effect_is_unconditional_in_range(
                caller,
                rollback_region.then_start,
                rollback_region.then_end,
                r"\breturn\s+FALSE\s*;",
            )
        )
        ordered_cleanup = bool(
            branch_delete
            and branch_perf
            and false_returns
            and branch_delete[0] < branch_perf[0] < false_returns[0].start()
        )
        if (
            not exact_delete
            or not exact_accounting
            or not exact_failure_return
            or not ordered_cleanup
            or success_reaches_primary_delete
        ):
            self.issue(
                category,
                "failed slot initialization must delete the primary object exactly once, account that deletion, then return without a success-path delete",
            )

    def verify_projection(self) -> None:
        category = "effective-projection"
        body = self.body(PROJECT_HELPER, category)
        if body is None:
            return
        get_cache = "OverworldWildRuntime_GetEffectiveCache"
        get_index = call_index(body, get_cache)
        converter_name = "OverworldWildSpawns_ConvertRuntimeEffectiveCacheToLegacyBehavior"
        converter_index = call_index(body, converter_name)
        if call_count(body, get_cache) != 1:
            self.issue(category, "projection must read one authenticated effective cache")
        if not call_has_exact_arguments(body, "OW_WILD_RUNTIME", ("state",)):
            self.issue(category, "projection must derive the current runtime from state")
        if not call_has_exact_arguments(
            body,
            get_cache,
            ("&runtime->behaviorStackRuntime", "slot", "slotGeneration", "&effective"),
        ):
            self.issue(category, "projection effective-cache query uses unrelated runtime identity")
        if get_index >= 0 and not has_failure_guard(body, get_cache, converter_index):
            self.issue(category, "projection must reject non-OK effective-cache status")
        if not call_has_exact_arguments(
            body,
            converter_name,
            ("&effective", "profileOut", "primitivesOut", "&spotState", "&capabilityMask"),
        ):
            self.issue(category, "Project must call the complete effective-cache conversion bridge")
        if (
            address_reference_count(body, r"effective") != 2
            or address_reference_count(body, r"spotState") != 1
            or address_reference_count(body, r"capabilityMask") != 1
            or address_reference_count(
                body, r"state->movementSpotStates\s*\[\s*slot\s*\]"
            ) != 0
            or address_reference_count(
                body, r"runtime->movementFrameDrivenActiveMask"
            ) != 0
        ):
            self.issue(
                category,
                "Project outputs must not acquire pointer aliases before publication",
            )
        converter_guard = False
        for region in if_regions(body):
            compact = normalized_expression(region.condition)
            if (
                compact.startswith("!" + converter_name + "(")
                and effect_is_unconditional_in_range(
                    body, region.then_start, region.then_end, r"\breturn\b"
                )
                and region.end < body.find("state->movementSpotStates[slot] = spotState")
            ):
                converter_guard = True
        if not converter_guard:
            self.issue(category, "Project must reject conversion failure before live publication")
        live_state_lvalue = r"state->movementSpotStates\s*\[\s*slot\s*\]"
        live_capability_lvalue = r"runtime->movementFrameDrivenActiveMask"
        if (
            len(write_records(body, live_state_lvalue)) != 1
            or len(exact_assignment(body, live_state_lvalue, "spotState")) != 1
            or len(write_records(body, live_capability_lvalue)) != 1
            or len(
                exact_assignment(
                    body, live_capability_lvalue, "capabilityMask"
                )
            ) != 1
        ):
            self.issue(category, "Project must publish converted live state and capability mapping")

        converter = self.body(converter_name, category)
        if converter is None:
            return
        if (
            pointer_value_has_alias_reference(converter, "effective")
            or pointer_value_has_alias_reference(
                converter,
                "profileOut",
                ("OverworldWildSpawns_ResolveBehaviorPrimitives",),
            )
            or pointer_value_has_alias_reference(converter, "primitivesOut")
            or pointer_value_has_alias_reference(converter, "spotStateOut")
            or pointer_value_has_alias_reference(converter, "capabilityMaskOut")
        ):
            self.issue(
                category,
                "conversion inputs/outputs must not acquire untracked pointer aliases",
            )
        controller_targets = (
            "alertState", "alertEmote", "alertTime", "alertness",
            "alertRange", "alertChance", "stamina", "restTime",
        )
        for index, target in enumerate(controller_targets):
            if len(exact_assignment(
                converter,
                rf"profileOut\s*->\s*{target}",
                f"effective->controllerValues[{index}]",
            )) != 1:
                self.issue(category, f"conversion is missing controllerValues[{index}] -> {target}")
        shared_state_targets = {
            4: "range", 5: "jumpLevel", 12: "hopTime",
            18: "attentiveChaseBoostDistance", 19: "attentiveChaseBoostSpeed",
            20: "attentiveCircleRadius", 21: "attentiveContinueWhenArrived",
            22: "attentiveAvoidPreviousTile", 23: "chainPauseAction",
            24: "chainMovementVariance", 25: "chainPauseVariance",
            26: "attentiveBattle", 27: "playerAdjacentDirectionMasks",
        }
        for index, target in shared_state_targets.items():
            if len(exact_assignment(
                converter,
                rf"profileOut\s*->\s*{target}",
                f"effective->stateValues[{index}]",
            )) != 1:
                self.issue(category, f"conversion is missing shared stateValues[{index}] -> {target}")
        role_mappings = {
            "OWBD_ROLE_CALM": (
                "OW_WILD_SPAWNER_SPOT_STATE_CHILL",
                {0: "chillState", 1: "chillAction", 2: "chillTarget", 3: "chillSpeed",
                 6: "chillAllowedTile", 7: "chillAllowedTile2", 8: "hopAllowNonCardinal",
                 9: "hopMinDistance", 10: "hopMaxDistance", 11: "hopPause",
                 13: "hopSpinSpeed", 14: "teleportTime", 15: "teleportPause",
                 16: "ramAccelerationSteps", 17: "ramMaxSpeed"},
            ),
            "OWBD_ROLE_ATTENTIVE": (
                "OW_WILD_SPAWNER_SPOT_STATE_ACTIVE",
                {0: "attentiveState", 1: "movementStyle", 2: "targetSelector", 3: "attentiveSpeed",
                 6: "attentiveAllowedTile", 7: "attentiveAllowedTile2", 8: "attentiveHopAllowNonCardinal",
                 9: "attentiveHopMinDistance", 10: "attentiveHopMaxDistance", 11: "attentiveHopPause",
                 13: "attentiveHopSpinSpeed", 14: "attentiveTeleportTime",
                 15: "attentiveTeleportPause", 16: "attentiveRamAccelerationSteps",
                 17: "attentiveRamMaxSpeed"},
            ),
            "OWBD_ROLE_TIRED": (
                "OW_WILD_SPAWNER_SPOT_STATE_TIRED",
                {0: "tiredState", 1: "specialAction", 3: "tiredSpeed",
                 6: "tiredAllowedTile", 7: "tiredAllowedTile2", 8: "tiredHopAllowNonCardinal",
                 9: "tiredHopMinDistance", 10: "tiredHopMaxDistance", 11: "tiredHopPause",
                 13: "hopSpinSpeed", 14: "tiredTeleportTime", 15: "tiredTeleportPause",
                 16: "tiredRamAccelerationSteps", 17: "tiredRamMaxSpeed"},
            ),
            "OWBD_ROLE_ASLEEP": (
                "OW_WILD_SPAWNER_SPOT_STATE_TIRED",
                {0: "tiredState", 1: "specialAction", 3: "tiredSpeed",
                 6: "tiredAllowedTile", 7: "tiredAllowedTile2", 8: "tiredHopAllowNonCardinal",
                 9: "tiredHopMinDistance", 10: "tiredHopMaxDistance", 11: "tiredHopPause",
                 13: "hopSpinSpeed", 14: "tiredTeleportTime", 15: "tiredTeleportPause",
                 16: "tiredRamAccelerationSteps", 17: "tiredRamMaxSpeed"},
            ),
        }
        for role, (spot_state, mappings) in role_mappings.items():
            case = switch_case_body(converter, "effective->semanticRole", role)
            if case is None:
                self.issue(category, f"conversion is missing {role} branch")
                continue
            if len(exact_assignment(
                case, r"\*\s*spotStateOut", spot_state
            )) != 1:
                self.issue(category, f"conversion has wrong live-state mapping for {role}")
            for index, target in mappings.items():
                if len(exact_assignment(
                    case,
                    rf"profileOut\s*->\s*{target}",
                    f"effective->stateValues[{index}]",
                )) != 1:
                    self.issue(category, f"conversion maps {role} stateValues[{index}] incorrectly")
        profile_write_pattern = (
            r"(?:profileOut\s*->|\(\s*\*\s*profileOut\s*\)\s*\."
            r"|profileOut\s*\[\s*0\s*\]\s*\.)[A-Za-z_]\w*"
        )
        expected_profile_writes = (
            len(controller_targets)
            + len(shared_state_targets)
            + sum(len(mappings) for _, mappings in role_mappings.values())
        )
        if len(write_records(converter, profile_write_pattern)) != expected_profile_writes:
            self.issue(category, "conversion contains an extra or aliased profile output write")
        spot_write_pattern = (
            r"(?:\*\s*spotStateOut|spotStateOut\s*\[\s*0\s*\]"
            r"|\*\s*\(\s*spotStateOut\s*\))"
        )
        if len(write_records(converter, spot_write_pattern)) != len(role_mappings):
            self.issue(category, "conversion contains an extra live-state output write")
        for index in range(28):
            if reachable_pattern(converter, rf"effective->stateValues\[{index}\]") is None:
                self.issue(category, f"conversion never consumes stateValues[{index}]")
        primitive_whole_lvalue = (
            r"(?:\*\s*primitivesOut|primitivesOut\s*\[\s*0\s*\]"
            r"|\*\s*\(\s*primitivesOut\s*\))"
        )
        if (
            len(write_records(converter, primitive_whole_lvalue)) != 1
            or len(exact_assignment(
                converter,
                primitive_whole_lvalue,
                "OverworldWildSpawns_ResolveBehaviorPrimitives(profileOut)",
            )) != 1
        ):
            self.issue(category, "conversion must derive the complete legacy primitives output")
        primitive_targets = {
            "OWBD_ROLE_CALM": ("chillLocomotion", "chillTarget", "alertReaction"),
            "OWBD_ROLE_ATTENTIVE": ("attentiveLocomotion", "attentiveTarget", "activeReaction"),
            "OWBD_ROLE_TIRED": ("tiredLocomotion", "tiredTarget", "tiredReaction"),
            "OWBD_ROLE_ASLEEP": ("tiredLocomotion", "tiredTarget", "tiredReaction"),
        }
        for role, targets in primitive_targets.items():
            cases = switch_case_bodies(converter, "effective->semanticRole", role)
            for index, target in enumerate(targets):
                if not any(
                    len(exact_assignment(
                        case,
                        rf"primitivesOut\s*->\s*{target}",
                        f"effective->primitives[{index}]",
                    )) == 1
                    for case in cases
                ):
                    self.issue(category, f"conversion maps {role} primitive[{index}] incorrectly")
        primitive_field_pattern = (
            r"(?:primitivesOut\s*->|\(\s*\*\s*primitivesOut\s*\)\s*\."
            r"|primitivesOut\s*\[\s*0\s*\]\s*\.)[A-Za-z_]\w*"
        )
        if len(write_records(converter, primitive_field_pattern)) != sum(
            len(targets) for targets in primitive_targets.values()
        ):
            self.issue(category, "conversion contains an extra or aliased primitive output write")
        primitive_validation = False
        expected_validation = {
            "effective->primitives[3]!=effective->stateValues[3]",
            "effective->primitives[4]!=effective->stateValues[4]",
        }
        for region in if_regions(converter):
            compact = normalized_expression(region.condition)
            if (
                set(compact.split("||")) == expected_validation
                and "&&" not in compact
                and effect_is_unconditional_in_range(
                    converter, region.then_start, region.then_end, r"\breturn\b"
                )
            ):
                primitive_validation = True
        if not primitive_validation:
            self.issue(category, "conversion must validate primitive[3] and primitive[4] semantics")
        capability_lvalue = (
            r"(?:\*\s*capabilityMaskOut|capabilityMaskOut\s*\[\s*0\s*\]"
            r"|\*\s*\(\s*capabilityMaskOut\s*\))"
        )
        if (
            len(write_records(converter, capability_lvalue)) != 1
            or len(exact_assignment(
                converter, capability_lvalue, "effective->capabilityMask"
            )) != 1
        ):
            self.issue(category, "conversion must publish the effective capability mask")
        for forbidden in (
            "OverworldWildSpawns_StoreBehaviorSlotCache",
            "movementBehaviorSlotCaches",
            "cache[slot] =",
        ):
            if forbidden in body or forbidden in converter:
                self.issue(category, "dynamic effective projection must not enter the static profile cache")

    def verify_routes(self) -> None:
        self.verify_stamina_route()
        self.verify_throw_route()
        self.verify_ram_route()
        self.verify_fled_route()

    def reject_direct_tired(self, body: str, function: str, category: str) -> None:
        if re.search(
            r"\bOverworldWildSpawns_StartTiredEmote(?:WithProfile)?\s*\(", body
        ):
            self.issue(category, f"{function} still directly owns tired presentation")

    def verify_stamina_route(self) -> None:
        category = "stamina-route"
        name = "OverworldWildSpawns_HandleFinishedMovementCommand"
        body = self.body(name, category)
        if body is None:
            return
        self.reject_direct_tired(body, name, category)
        consume = call_index(body, CONSUME_HELPER)
        runtime_ready = body.find("runtime = OW_WILD_RUNTIME")
        history = call_index(body, "OverworldWildSpawns_RecordFinishedMovementHistory")
        if consume < 0:
            self.issue(category, "completion must authenticate and consume the command origin")
            return
        if history >= 0 and consume > history:
            self.issue(category, "origin consumption must precede completion history")
        if runtime_ready >= 0:
            early = re.search(r"\breturn\b", body[runtime_ready:consume])
            if early:
                self.issue(category, "a normal-completion early return bypasses origin consumption")
        apply = call_index(body, APPLY_HELPER)
        if body.count("OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA") != 1 or apply < 0:
            self.issue(category, "authenticated stamina completion must apply one stamina candidate")
            return
        consume_guard_end = -1
        for region in if_regions(body):
            if (
                normalized_expression(region.condition)
                == normalized_expression(
                    "!OverworldWildSpawns_ConsumeMovementCommandOrigin(state, slot, &origin)"
                )
                and effect_is_unconditional_in_range(
                    body,
                    region.then_start,
                    region.then_end,
                    r"\breturn\b",
                )
                and region.end < apply
            ):
                consume_guard_end = region.end
        if consume_guard_end < 0:
            self.issue(category, "stamina recovery must be dominated by successful authenticated consume")
        get_cache = "OverworldWildRuntime_GetEffectiveCache"
        get_effective = call_index(body, get_cache)
        if not call_has_exact_arguments(
            body,
            get_cache,
            ("&runtime->behaviorStackRuntime", "slot", "slotGeneration", "&effective"),
        ) or not has_failure_guard(body, get_cache, apply):
            self.issue(category, "stamina completion must authenticate the current effective policy")
        active_steps_lvalue = r"state->movementActiveSteps\s*\[\s*slot\s*\]"
        charge_writes = write_records(body, active_steps_lvalue)
        if (
            address_reference_count(body, active_steps_lvalue) != 0
            or has_nonindexed_array_reference(
                body, "state->movementActiveSteps", "slot"
            )
            or address_reference_count(body, r"effective") != 1
            or address_reference_count(body, r"origin") != 2
        ):
            self.issue(
                category,
                "stamina policy/output/active-step values must not acquire aliases",
            )
        if len(charge_writes) != 1 or charge_writes[0][1] != "++":
            self.issue(category, "active stamina completion must charge exactly one step")
            charge = -1
        else:
            charge = charge_writes[0][0]
        guard_ends: dict[str, int] = {}
        compatibility_expected = {
            "origin.objectGeneration!=runtime->movementObjectGenerations[slot]",
            "origin.staminaPolicyId!=effective.controllerId",
            "origin.staminaPolicyGeneration!=effective.effectiveGeneration",
        }
        for region in if_regions(body):
            compact = normalized_expression(region.condition)
            exits = effect_is_unconditional_in_range(
                body, region.then_start, region.then_end, r"\breturn\b"
            )
            if not exits:
                continue
            if compact == "state->movementSpotStates[slot]!=OW_WILD_SPAWNER_SPOT_STATE_ACTIVE":
                guard_ends["active"] = region.end
            if compact == normalized_expression(
                "OverworldWildSpawns_CurrentSpotUsesRamLocomotion("
                "&primitives, state->movementSpotStates[slot])"
            ):
                guard_ends["ram"] = region.end
            if set(compact.split("||")) == compatibility_expected and "&&" not in compact:
                guard_ends["identity"] = region.end
            if compact == "effective.controllerValues[6]==0":
                guard_ends["stamina"] = region.end
            if compact == "state->movementActiveSteps[slot]<effective.controllerValues[6]":
                guard_ends["threshold"] = region.end
        for guard_name in ("active", "ram", "identity", "stamina"):
            if guard_name not in guard_ends or charge < guard_ends.get(guard_name, len(body)):
                self.issue(category, f"{guard_name} compatibility must return before stamina charge")
        if "threshold" not in guard_ends or apply < guard_ends.get("threshold", len(body)):
            self.issue(category, "stamina candidate resolution must occur only at effective exhaustion")
        if not call_has_exact_arguments(
            body,
            APPLY_HELPER,
            (
                "state",
                "slot",
                "OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA",
                "&origin",
            ),
        ):
            self.issue(category, "stamina exhaustion must apply once with its authenticated origin")
        if not (
            consume < get_effective < guard_ends.get("active", len(body))
            and guard_ends.get("ram", -1) < charge < guard_ends.get("threshold", len(body)) < apply
        ):
            self.issue(category, "stamina consume/compatibility/charge/threshold/apply order is invalid")

        staged = self.body("OverworldWildSpawns_FinishPendingStagedHop", category)
        if staged is not None:
            preload = reachable_pattern(
                staged,
                r"state->movementActiveSteps\[slot\]\s*=\s*effective\.controllerValues\[6\]\s*-\s*1\s*;",
            )
            staged_writes = write_records(staged, active_steps_lvalue)
            completion = call_positions(
                staged, "OverworldWildSpawns_HandleFinishedMovementCommand"
            )
            if (
                address_reference_count(staged, active_steps_lvalue) != 0
                or has_nonindexed_array_reference(
                    staged, "state->movementActiveSteps", "slot"
                )
                or address_reference_count(staged, r"effective")
                    != call_count(
                        staged, "OverworldWildRuntime_GetEffectiveCache"
                    )
                or address_reference_count(staged, r"status") != 0
            ):
                self.issue(
                    category,
                    "staged stamina status/output/active-step values must not acquire aliases",
                )
            preload_guarded = False
            if preload is not None:
                for region in if_regions(staged):
                    compact = normalized_expression(region.condition)
                    if (
                        "finishWithTired" in compact
                        and "effective.controllerValues[6]>0" in compact
                        and "||" not in compact
                        and region.contains_in_then(preload.start())
                    ):
                        preload_guarded = True
            if (
                preload is None
                or not preload_guarded
                or len(staged_writes) != 1
                or staged_writes[0][1] != "="
                or normalized_expression(staged_writes[0][2])
                    != "effective.controllerValues[6]-1"
            ):
                self.issue(category, "staged tired finish must preload effective stamina - 1")
            if len(completion) != 1 or (preload is not None and completion[0] < preload.start()):
                self.issue(category, "staged hop must perform one final authenticated completion")

    def verify_throw_route(self) -> None:
        category = "throw-route"
        name = "OverworldWildSpawns_TryStartFrameDrivenActiveMovementCommand"
        body = self.body(name, category)
        if body is None:
            return
        self.reject_direct_tired(body, name, category)
        apply_positions = call_positions(body, APPLY_HELPER)
        origin = "OW_WILD_RUNTIME_RECOVERY_ORIGIN_THROW_RECOVERY"
        if len(apply_positions) != 1 or body.count(origin) != 1:
            self.issue(category, "throw recovery must apply exactly once")
            return
        apply = apply_positions[0]
        arguments = call_arguments(body, APPLY_HELPER, apply)
        if re.search(r"\bslot\b", arguments) is None or re.search(
            r"\btargetSlot\b", arguments
        ):
            self.issue(category, "throw recovery must apply to the carrier slot, never the target")
        success_regions = [
            region
            for region in if_regions(body)
            if condition_has_direct_positive_call(
                region.condition,
                "OverworldWildSpawns_StartPreparedCustomJumpCommand",
            )
            and region.contains_in_then(apply)
        ]
        if not success_regions:
            self.issue(category, "throw recovery must be inside successful carrier publication")
            return
        region = success_regions[0]
        if region.else_start is not None:
            failure = body[region.else_start : region.else_end]
            if call_count(failure, APPLY_HELPER):
                self.issue(category, "throw failure/release branch must not apply a candidate")

    def verify_ram_route(self) -> None:
        category = "ram-route"
        name = "OverworldWildSpawns_EndRamCrash"
        body = self.body(name, category)
        if body is not None:
            self.reject_direct_tired(body, name, category)
            apply_positions = call_positions(body, APPLY_HELPER)
            origin = "OW_WILD_RUNTIME_RECOVERY_ORIGIN_RAM_CRASH"
            if len(apply_positions) != 1 or body.count(origin) != 1:
                self.issue(category, "RAM recovery must apply exactly once on its nonbattle active path")
            else:
                apply = apply_positions[0]
                impact_name = "OverworldWildSpawns_TryStartRamCrashBattleImpact"
                impact_calls = syntactic_call_positions(body, impact_name)
                try:
                    raw_body = function_body_preserving_preprocessor(
                        self.source, name
                    )
                    raw_impact_count = len(
                        syntactic_call_positions(raw_body, impact_name)
                    )
                except SourceShapeError:
                    raw_impact_count = 0
                if (
                    len(impact_calls) != 1
                    or not position_is_reachable(body, impact_calls[0])
                    or raw_impact_count != 1
                ):
                    self.issue(
                        category,
                        "EndRamCrash must contain exactly one reachable RAM battle-impact call",
                    )
                active_guard = False
                active_branch = False
                impact_guard = False
                for region in if_regions(body):
                    block = body[region.then_start : region.then_end]
                    if (
                        normalized_expression(region.condition)
                        == "state->movementSpotStates[slot]!=OW_WILD_SPAWNER_SPOT_STATE_ACTIVE"
                        and effect_is_unconditional_in_range(
                            body,
                            region.then_start,
                            region.then_end,
                            r"\breturn\b",
                        )
                        and region.end < apply
                    ):
                        active_guard = True
                    if (
                        normalized_expression(region.condition)
                        == "state->movementSpotStates[slot]==OW_WILD_SPAWNER_SPOT_STATE_ACTIVE"
                        and region.contains_in_then(apply)
                    ):
                        active_branch = True
                    if (
                        normalized_expression(region.condition)
                        == normalized_expression(
                            impact_name + "("
                            "state, state->movementFieldSystem, slot, object, "
                            "state->movementRamDirections[slot], profile)"
                        )
                        and effect_is_unconditional_in_range(
                            body,
                            region.then_start,
                            region.then_end,
                            r"\breturn\b",
                        )
                        and region.end < apply
                    ):
                        impact_guard = True
                if not active_guard:
                    self.issue(category, "chill/tired RAM completion must return before recovery")
                if not active_branch:
                    self.issue(category, "RAM recovery must be inside the exact spotState == ACTIVE branch")
                if not impact_guard:
                    self.issue(category, "successful RAM battle impact must return before recovery")
        impact = "OverworldWildSpawns_TryStartRamCrashBattleImpact"
        if has_non_call_identifier_reference(self.code, impact):
            self.issue(
                category,
                "RAM battle-impact helper must not escape through a function-pointer alias",
            )
        if reachable_call(self.code, impact, APPLY_HELPER):
            self.issue(category, "RAM battle impact reaches recovery directly or through a helper")

    def verify_fled_route(self) -> None:
        category = "fled-route"
        name = "OverworldWildSpawns_OverlayCleanupPendingBattle"
        body = self.body(name, category)
        if body is None:
            return
        self.reject_direct_tired(body, name, category)
        apply_positions = call_positions(body, APPLY_HELPER)
        origin = "OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED"
        if len(apply_positions) != 1 or body.count(origin) != 1:
            self.issue(category, "FLED cleanup must apply exactly one distinct candidate")
            return
        apply = apply_positions[0]
        canonical_regions = []
        for region in if_regions(body):
            if not region.contains_in_then(apply) or condition_is_disabled(region.condition):
                continue
            condition = region.condition
            if "||" in condition:
                continue
            if re.search(
                r"\bdisposition\s*==\s*OW_WILD_BATTLE_DISPOSITION_FLED\b",
                condition,
            ):
                canonical_regions.append(region)
        if not canonical_regions:
            self.issue(category, "FLED candidate must be dominated by exact FLED disposition")
            return
        conditions = canonical_regions[0].condition
        exact_bounds = bool(
            re.search(r"state->pendingSlot\s*>=\s*0", conditions)
            and re.search(
                r"state->pendingSlot\s*<\s*OW_WILD_MAX_SPAWNS", conditions
            )
        )
        exact_context = call_count(
            conditions, "OverworldWildSpawns_IsMovementFieldContextCurrent"
        ) == 1 and call_has_exact_arguments(
            conditions,
            "OverworldWildSpawns_IsMovementFieldContextCurrent",
            ("state", "fieldSystem"),
        )
        exact_object = call_count(
            conditions, "OverworldWildSpawns_IsCurrentSpawnObject"
        ) == 1 and call_has_exact_arguments(
            conditions,
            "OverworldWildSpawns_IsCurrentSpawnObject",
            ("fieldSystem", "&state->spawns[state->pendingSlot]"),
        )
        if not exact_bounds or not exact_context or not exact_object:
            self.issue(category, "FLED candidate must be dominated by retained-slot authentication")

    def verify_frame_timers(self) -> None:
        category = "frame-timers"
        frame = self.body("OverworldWildSpawns_FrameMovementTask", category)
        tick_helper = "OverworldWildSpawns_TickRuntimeFrameTimers"
        if frame is not None:
            ticks = call_positions(frame, tick_helper)
            if len(ticks) != 1:
                self.issue(category, f"FrameMovementTask must call {tick_helper} exactly once")
            else:
                tick = ticks[0]
                context_regions = [
                    region
                    for region in if_regions(frame)
                    if "OverworldWildSpawns_IsMovementFieldContextCurrent" in region.condition
                    and "!" in region.condition
                ]
                if not context_regions:
                    self.issue(category, "frame timer dominance needs the context-validity guard")
                else:
                    boundary = context_regions[0].end
                    if tick < boundary:
                        self.issue(category, "runtime timers must tick only after context validity")
                    elif any(
                        boundary < position < tick
                        for position in token_positions(frame, r"\breturn\b")
                    ):
                        self.issue(category, "a fast/heavy return after context validity bypasses timer tick")
                for marker in (
                    "presentationRestorePending",
                    "currentSpawnMask == 0",
                    "OverworldWildSpawns_TryStartCustomJumpRamProbe",
                    "heavyWorkMask == 0",
                ):
                    marker_index = frame.find(marker)
                    if marker_index >= 0 and tick > marker_index:
                        self.issue(category, f"runtime timer tick must dominate {marker} fast path")

        wrapper = self.body(tick_helper, category)
        if wrapper is not None:
            stage = "OverworldWildRuntime_TickFrameTimers"
            pending = "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries"
            if not call_has_exact_arguments(wrapper, "OW_WILD_RUNTIME", ("state",)):
                self.issue(category, "timer wrapper must derive the current runtime from state")
            stage_index = call_index(wrapper, stage)
            pending_index = call_index(wrapper, pending)
            if call_count(wrapper, stage) != 1:
                self.issue(category, "timer wrapper must call the all-slot Stage A tick exactly once")
            if not call_has_exact_arguments(
                wrapper,
                stage,
                (
                    "&runtime->behaviorStackRuntime",
                    "presentationGateMask",
                    "tickResults",
                ),
            ):
                self.issue(category, "all-slot timer tick must use current runtime/gates/results")
            if call_count(wrapper, pending) != 1 or pending_index < stage_index:
                self.issue(category, "pending expiry processing must follow the all-slot tick")
            elif stage_index >= 0 and not has_failure_guard(wrapper, stage, pending_index):
                self.issue(category, "pending expiry processing must require a successful all-slot tick")

        pending_body = self.body(
            "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", category
        )
        if pending_body is not None:
            if not call_has_exact_arguments(pending_body, "OW_WILD_RUNTIME", ("state",)):
                self.issue(category, "pending recovery must derive the current runtime from state")
            count_name = "OverworldWildRuntime_GetPendingTimerExpiryCount"
            query_name = "OverworldWildRuntime_GetPendingTimerExpiryByIndex"
            recover_name = "OverworldWildRuntime_RecoverExpiredTimer"
            if call_count(pending_body, count_name) != 1:
                self.issue(category, "pending pass must snapshot each slot pending count once")
            if call_count(pending_body, query_name) != 1:
                self.issue(category, "pending pass must query each bounded record once")
            if call_count(pending_body, recover_name) != 1:
                self.issue(category, "pending pass must recover each bounded record at most once")
            parsed_loops = loop_regions(pending_body)
            outer_loops = [
                loop
                for loop in parsed_loops
                if position_is_reachable(pending_body, loop.start)
                if normalized_expression(loop.header).startswith("slot=0;")
                and "slot<OW_WILD_MAX_SPAWNS" in normalized_expression(loop.header)
            ]
            if len(outer_loops) != 1:
                self.issue(category, "pending pass needs one all-slot outer bound")
            bounded = any(
                position_is_reachable(pending_body, loop.start)
                and "pendingCount" in loop.header
                and "OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT" in loop.header
                and "pendingIndex++" in normalized_expression(loop.header)
                for loop in parsed_loops
            )
            if not bounded or re.search(r"\bwhile\s*\(", pending_body):
                self.issue(category, "pending recovery must use one bounded index pass per frame")
            query = call_index(pending_body, query_name)
            recover = call_index(pending_body, recover_name)
            project = call_index(pending_body, PROJECT_HELPER)
            present = call_index(pending_body, PRESENT_HELPER)
            exact_flow = (
                call_has_exact_arguments(
                    pending_body,
                    count_name,
                    ("&runtime->behaviorStackRuntime", "slot", "slotGeneration"),
                )
                and call_has_exact_arguments(
                    pending_body,
                    query_name,
                    (
                        "&runtime->behaviorStackRuntime",
                        "slot",
                        "slotGeneration",
                        "pendingIndex",
                        "&expiry",
                    ),
                )
                and call_has_exact_arguments(
                    pending_body,
                    recover_name,
                    ("&runtime->behaviorStackRuntime", "&expiry", "&recovery"),
                )
                and call_has_exact_arguments(
                    pending_body,
                    PROJECT_HELPER,
                    ("state", "slot", "&recovery"),
                )
            )
            if not exact_flow:
                self.issue(category, "pending count/query/recover/projection must share runtime/slot/index/record")
            count_position = call_index(pending_body, count_name)
            count_statement = pending_body[
                pending_body.rfind(";", 0, count_position) + 1 : pending_body.find(";", count_position)
            ] if count_position >= 0 else ""
            if re.search(r"\bpendingCount\s*=", count_statement) is None:
                self.issue(category, "pending count must be snapshotted once before bounded iteration")
            if min(query, recover, project) < 0:
                self.issue(category, "pending recovery is missing query, recover, or projection")
            else:
                owning_loops = [
                    loop
                    for loop in parsed_loops
                    if position_is_reachable(pending_body, loop.start)
                    and loop.contains(query)
                    and loop.contains(recover)
                    and loop.contains(project)
                    and "pendingCount" in loop.header
                    and "OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT" in loop.header
                ]
                if not owning_loops or (
                    present >= 0 and not owning_loops[0].contains(present)
                ):
                    self.issue(
                        category,
                        "query/recover/project/presentation must stay in the same bounded pending-record loop",
                    )
                if not outer_loops or not (
                    outer_loops[0].contains(count_position)
                    and outer_loops[0].contains(query)
                    and outer_loops[0].contains(recover)
                ):
                    self.issue(
                        category,
                        "pending count/query/recover must execute inside the all-slot outer pass",
                    )
                if not has_failure_guard(pending_body, query_name, recover, "continue"):
                    self.issue(category, "pending recovery must skip records whose query status is not OK")
                if not has_failure_guard(pending_body, recover_name, project, "continue"):
                    self.issue(category, "projection must occur only after RecoverExpiredTimer returns OK")
                if present >= 0 and present < project:
                    self.issue(category, "pending presentation must follow successful recovery projection")

    def verify_legacy_timer_ownership(self) -> None:
        category = "legacy-timer-ownership"
        body = self.body("OverworldWildSpawns_TickTiredEmote", category)
        if body is None:
            return
        decrement = body.find("movementEmoteTimers[slot]--")
        if decrement < 0:
            self.issue(category, "legacy tired timer decrement was not recognized")
            return
        valid_guard = False
        for region in if_regions(body):
            if "OverworldWildSpawns_HasRuntimeTimerWork" not in region.condition:
                continue
            inverted = bool(
                re.search(r"!\s*OverworldWildSpawns_HasRuntimeTimerWork", region.condition)
                or "== 0" in region.condition
                or "== FALSE" in region.condition
            )
            block = body[region.then_start : region.then_end]
            if (
                not inverted
                and not condition_is_disabled(region.condition)
                and effect_is_unconditional_in_range(
                    body,
                    region.then_start,
                    region.then_end,
                    r"\breturn\b",
                )
                and region.end < decrement
            ):
                valid_guard = True
        if not valid_guard:
            self.issue(category, "runtime-owned tired timers must exit before the legacy decrement")

    def verify_liveness(self) -> None:
        category = "timer-task-liveness"
        body = self.body("OverworldWildSpawns_HasRuntimeTimerWork", category)
        if body is not None:
            if not call_has_exact_arguments(body, "OW_WILD_RUNTIME", ("state",)):
                self.issue(category, "timer liveness must derive the current runtime from state")
            timer = "OverworldWildRuntime_GetTimerCount"
            pending = "OverworldWildRuntime_GetPendingTimerExpiryCount"
            if call_count(body, timer) != 1 or call_count(body, pending) != 1:
                self.issue(category, "liveness must query actual timer and pending-expiry counts")
            expected_query_args = (
                "&runtime->behaviorStackRuntime",
                "slot",
                "slotGeneration",
            )
            if not call_has_exact_arguments(
                body, timer, expected_query_args
            ) or not call_has_exact_arguments(body, pending, expected_query_args):
                self.issue(category, "liveness queries must use current runtime/slot/generation")
            if not call_is_compared_nonzero(body, timer) or not call_is_compared_nonzero(
                body, pending
            ):
                self.issue(category, "timer and pending liveness counts must each be compared != 0")
            returns = re.findall(r"\breturn\s+([^;]+);", body, re.DOTALL)
            expected_return = normalized_expression(
                "OverworldWildRuntime_GetTimerCount("
                "&runtime->behaviorStackRuntime, slot, slotGeneration) != 0 || "
                "OverworldWildRuntime_GetPendingTimerExpiryCount("
                "&runtime->behaviorStackRuntime, slot, slotGeneration) != 0"
            )
            if (
                len(returns) != 1
                or normalized_expression(returns[0]) != expected_return
            ):
                self.issue(
                    category,
                    "liveness must return the exact logical nonzero timer/pending disjunction",
                )
        slot_work = self.body("OverworldWildSpawns_GetFrameMovementWorkForSlot", category)
        if slot_work is not None:
            helper = "OverworldWildSpawns_HasRuntimeTimerWork"
            helper_positions = call_positions(slot_work, helper)
            influenced = False
            if len(helper_positions) == 1:
                for region in if_regions(slot_work):
                    if normalized_expression(region.condition) != normalized_expression(
                        "OverworldWildSpawns_HasRuntimeTimerWork(state, slot)"
                    ):
                        continue
                    block = slot_work[region.then_start : region.then_end]
                    mutation = reachable_pattern(
                        block,
                        r"\bframeWorkMask\s*\|=\s*"
                        r"OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK\s*\(\s*slot\s*\)\s*;",
                    )
                    if mutation and re.search(
                        r"\breturn\s+frameWorkMask\s*;",
                        slot_work[region.end :],
                    ):
                        influenced = True
            if not influenced:
                self.issue(category, "HasRuntimeTimerWork must directly influence the returned frame-work mask")
        apply = self.body(APPLY_HELPER, category)
        if apply is not None:
            ensure = call_index(apply, "OverworldWildSpawns_EnsureFrameMovementTask")
            present = call_index(apply, PRESENT_HELPER)
            if ensure < present:
                self.issue(category, "successful recovery must keep the frame task live after commit")
        pending_body = self.body(
            "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", category
        )
        if pending_body is not None:
            keep_live = "OverworldWildSpawns_EnsureFrameMovementTask"
            if call_count(pending_body, keep_live) != 1 or not effect_is_unconditional_in_range(
                pending_body,
                0,
                len(pending_body),
                r"\b" + re.escape(keep_live) + r"\s*\(",
            ):
                self.issue(category, "pending expiry work must keep the frame task live")

    def verify_postcommit_apply(self) -> None:
        category = "postcommit-presentation"
        body = self.body(APPLY_HELPER, category)
        if body is None:
            return
        resolve = "OverworldWildRuntime_ResolveRecoveryCandidate"
        apply_name = "OverworldWildRuntime_Apply"
        resolve_index = call_index(body, resolve)
        apply_index = call_index(body, apply_name)
        project = call_index(body, PROJECT_HELPER)
        present = call_index(body, PRESENT_HELPER)
        ensure = call_index(body, "OverworldWildSpawns_EnsureFrameMovementTask")
        if call_count(body, resolve) != 1:
            self.issue(category, "common recovery helper must resolve one canonical candidate")
        if call_count(body, apply_name) != 1:
            self.issue(category, "common recovery helper must commit one runtime apply")
        if min(resolve_index, apply_index, project, present, ensure) < 0:
            self.issue(category, "common recovery helper is missing resolve/apply/project/present/liveness")
            return
        if not (resolve_index < apply_index < project < present < ensure):
            self.issue(category, "required order is resolve -> Apply -> project -> present -> keep-live")
        for effect in (PROJECT_HELPER, PRESENT_HELPER, "OverworldWildSpawns_EnsureFrameMovementTask"):
            if not effect_is_unconditional_in_range(
                body,
                0,
                len(body),
                r"\b" + re.escape(effect) + r"\s*\(",
            ):
                self.issue(category, f"successful recovery effect {effect} must execute unconditionally")
        if not has_failure_guard(body, resolve, apply_index):
            self.issue(category, "non-applicable/unresolved recovery must return without fallback")
        if not has_failure_guard(body, apply_name, project):
            self.issue(category, "projection/presentation must require successful runtime apply")
        for presentation in (
            "PlaySE",
            "PlayCry",
            "OverworldWildSpawns_ShowBubble",
            "OverworldWildSpawns_StartTiredEmote",
        ):
            index = call_index(body, presentation)
            if 0 <= index < apply_index:
                self.issue(category, f"{presentation} occurs before runtime commit")


def verify_source(source: str) -> list[str]:
    """Verify the direct-state, stackable-profile production cutover."""

    issues: list[str] = []
    code = sanitize_source(source)

    def issue(category: str, message: str) -> None:
        issues.append(f"[{category}] {message}")

    def body(name: str, category: str) -> str | None:
        try:
            return function_body(source, name)
        except SourceShapeError as error:
            issue(category, str(error))
            return None

    banned = (
        "OverworldWildBehaviorSlotCache",
        "movementBehaviorSlotCaches",
        "OverworldWildSpawns_ResolveBehaviorProfileForContext",
        "OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot",
        "OverworldWildSpawns_GetBehaviorProfile",
        "OverworldWildSpawns_ResolveBehaviorPrimitives",
        "OverworldWildSpawns_ConvertRuntimeEffectiveCacheToLegacyBehavior",
        "OverworldWildRuntime_RecoverExpiredTimer",
        "OverworldWildRuntime_ResolveRecoveryCandidate",
        "OverworldWildRuntime_CommitTimerExpiry",
    )
    for identifier in banned:
        if re.search(r"\b" + re.escape(identifier) + r"\b", code):
            issue("legacy-cutover", f"production source still references {identifier}")
    for identifier in (
        "OverworldWildBehaviorDataBlob",
        "OverworldWildBehaviorProfile",
        "OverworldWildBehaviorOverrideProfile",
        "classRules",
        "speciesClassRules",
        "classProfiles",
        "overrideProfiles",
        "overrideMembers",
        "OverworldWildSpawns_GetBehaviorClassForSpawn",
    ):
        if re.search(r"\b" + re.escape(identifier) + r"\b", source):
            issue(
                "legacy-projection",
                f"overlay 149 source still contains legacy projection {identifier}",
            )

    try:
        runtime_body = struct_body(source, "OverworldWildOverlayRuntimeState")
        if re.search(
            r"\bOverworldWildBehaviorStackRuntime\s+behaviorStackRuntime\s*;\s*$",
            runtime_body,
        ) is None:
            issue("runtime-layout", "behaviorStackRuntime must remain the resident suffix")
    except SourceShapeError as error:
        issue("runtime-layout", str(error))

    current = body("OverworldWildSpawns_GetCurrentBehavior", "direct-current")
    if current is not None:
        if call_count(current, "OverworldWildRuntime_GetEffectiveCache") != 1:
            issue("direct-current", "current behavior must use one authenticated effective-cache read")
        if not call_has_exact_arguments(
            current,
            "OverworldWildRuntime_GetEffectiveCache",
            ("&runtime->behaviorStackRuntime", "slot", "slotGeneration", "currentOut"),
        ):
            issue("direct-current", "current behavior read uses unrelated runtime identity")

    configuration = body(
        "OverworldWildSpawns_CopySpawnConfiguration", "spawn-configuration"
    )
    if configuration is not None:
        if "staticCache.spawnConfiguration" in configuration:
            issue("spawn-configuration", "overlay 149 must not read the static configuration directly")
        if not call_has_exact_arguments(
            configuration,
            "OverworldWildRuntime_CopyValidatedSpawnConfiguration",
            (
                "&runtimeSlot->staticCache",
                "runtimeSlot->staticContextGeneration",
                "configurationOut",
            ),
        ):
            issue(
                "spawn-configuration",
                "spawn configuration must use the authenticated runtime-core accessor",
            )

    callback = body("OverworldWildSpawns_TryStartSpawnerMovementCommand", "callback")
    if callback is not None:
        try:
            parameters = function_parameter_names(
                source, "OverworldWildSpawns_TryStartSpawnerMovementCommand"
            )
        except SourceShapeError as error:
            issue("callback", str(error))
            parameters = []
        if parameters != ["state", "fieldSystem", "slot", "directions", "directionCount"]:
            issue("callback", "movement callback must keep the exact five-argument ABI")
        if call_count(callback, "OverworldWildSpawns_GetCurrentBehavior") != 1:
            issue("callback", "movement callback must reacquire the authenticated current behavior")

    projection = body(PROJECT_HELPER, "effective-projection")
    if projection is not None:
        get_cache = call_index(projection, "OverworldWildRuntime_GetEffectiveCache")
        publication = projection.find("state->movementSpotStates[slot] = spotState")
        if call_count(projection, "OverworldWildRuntime_GetEffectiveCache") != 1:
            issue("effective-projection", "projection must read one authenticated effective cache")
        if not call_has_exact_arguments(
            projection,
            "OverworldWildRuntime_GetEffectiveCache",
            ("&runtime->behaviorStackRuntime", "slot", "slotGeneration", "&effective"),
        ):
            issue("effective-projection", "projection cache read uses unrelated runtime identity")
        if get_cache < 0 or publication < get_cache:
            issue("effective-projection", "presentation state must be derived after the cache read")
        if not re.search(
            r"status\s*!=\s*OW_WILD_RUNTIME_STATUS_OK[^{};]*\)\s*\{?\s*return\s+FALSE",
            projection,
            re.DOTALL,
        ):
            issue("effective-projection", "projection must reject a failed cache read")
        for role in (
            "OWBD_ROLE_CALM",
            "OWBD_ROLE_CARRIED",
            "OWBD_ROLE_FOLLOWER",
            "OWBD_ROLE_ATTENTIVE",
            "OWBD_ROLE_TIRED",
            "OWBD_ROLE_ASLEEP",
        ):
            if switch_case_body(
                projection, "effective.semanticRole", role
            ) is None:
                issue("effective-projection", f"projection is missing {role}")
        if publication < 0 or "runtime->movementFrameDrivenActiveMask = capabilityMask" not in projection:
            issue("effective-projection", "projection must publish spot state and frame capability")
        if "OverworldWildBehaviorProfile" in projection:
            issue("effective-projection", "projection must not rebuild a legacy multi-state profile")

    finalize = body("OverworldWildSpawns_FinalizePreparedSpawn", "spawn-prime")
    if finalize is not None:
        load = call_index(finalize, "OverworldWildSpawns_EnsureBehaviorDataLoaded")
        build = call_index(finalize, "OverworldWildSpawns_BuildSpawnStaticContext")
        mark = call_index(finalize, "OverworldWildRuntime_MarkSlotAssigned")
        prime = call_index(finalize, "OverworldWildRuntime_PrimeEffectiveCache")
        current_read = call_index(finalize, "OverworldWildSpawns_GetCurrentBehavior")
        if min(load, build, mark, prime, current_read) < 0 or not (
            load < build < mark < prime < current_read
        ):
            issue("spawn-prime", "spawn must build context, assign, prime, then read current behavior")
        if not call_has_exact_arguments(
            finalize,
            "OverworldWildRuntime_PrimeEffectiveCache",
            ("&runtime->behaviorStackRuntime", "slot", "slotGeneration", "&staticContext", "NULL"),
        ):
            issue("spawn-prime", "spawn prime must use the complete static context and canonical applicability")
        if "OverworldWildSpawns_CreateObject" in finalize:
            issue("spawn-prime", "object creation must not precede successful cache priming")
        follower = finalize.find("transitionEvent.trigger = OWBD_TRIGGER_FOLLOWER_APPLY")
        follower_route = finalize.find(
            "transitionEvent.systemRoute = OWBD_TRIGGER_FOLLOWER_APPLY"
        )
        dispatch = call_index(finalize, "OverworldWildRuntime_DispatchTransition")
        if (
            follower < prime
            or follower_route < follower
            or dispatch < follower_route
            or current_read < dispatch
        ):
            issue("spawn-prime", "follower override must dispatch after prime and before current-state use")
        for field in ("replayExpiry", "flags"):
            if re.search(r"transitionEvent\." + field + r"(?:\.|\s*=)", finalize):
                issue("ordinary-event", f"follower event writes replay-only field {field}")

    spawn = body("OverworldWildSpawns_SpawnPreparedEncounter", "spawn-prime")
    if spawn is not None:
        create = call_index(spawn, "OverworldWildSpawns_CreateObject")
        init = call_index(spawn, "OverworldWildSpawns_InitSpawnSlotState")
        if create < 0 or init < create:
            issue("spawn-prime", "spawn object must be created only from already primed state")
        if "OverworldWildRuntime_Prime" in spawn:
            issue("spawn-prime", "spawn object path must not own a second cache prime")
        project = call_index(spawn, PROJECT_HELPER)
        if project < init:
            issue("spawn-prime", "spawn state must be projected from the effective cache after slot initialization")
        deletes = syntactic_call_positions(spawn, "DeleteMapObject")
        if len(deletes) != 2 or any(position < create for position in deletes):
            issue(
                "spawn-rollback",
                "both post-create failure paths must delete the primary object exactly once",
            )
        rollback_deletes: set[int] = set()
        for failed_call in (
            "OverworldWildSpawns_InitSpawnSlotState",
            PROJECT_HELPER,
        ):
            branches = [
                region for region in if_regions(spawn)
                if failed_call in region.condition
                and re.search(r"!\s*" + re.escape(failed_call), region.condition)
            ]
            branch_deletes = []
            if len(branches) == 1:
                branch_deletes = [
                    position for position in deletes
                    if branches[0].contains_in_then(position)
                ]
            if len(branches) != 1 or len(branch_deletes) != 1:
                issue(
                    "spawn-rollback",
                    f"failed {failed_call} must own exactly one primary-object delete",
                )
            rollback_deletes.update(branch_deletes)
        if any(position not in rollback_deletes for position in deletes):
            issue(
                "spawn-rollback",
                "primary object must not be deleted outside a post-create failure branch",
            )

    attentive = body("OverworldWildSpawns_TryApplyRuntimeAttentiveCandidate", "attentive-dispatch")
    if attentive is not None:
        zero = call_index(attentive, "memset")
        trigger = attentive.find("event.trigger = trigger")
        dispatch = call_index(attentive, "OverworldWildRuntime_DispatchTransition")
        project = call_index(attentive, PROJECT_HELPER)
        if min(zero, trigger, dispatch, project) < 0 or not (zero < trigger < dispatch < project):
            issue("attentive-dispatch", "ordinary attentive events must be zeroed, dispatched, then projected")
        system_route = attentive.find("event.systemRoute = trigger")
        if system_route < trigger or system_route > dispatch:
            issue("attentive-dispatch", "AGGRO/HELP dispatch must publish its authored system route")
        route_guard = any(
            "OWBD_TRIGGER_AGGRO_APPLY" in region.condition
            and "OWBD_TRIGGER_HELP_CALL_APPLY" in region.condition
            and region.contains_in_then(system_route)
            for region in if_regions(attentive)
        )
        if not route_guard:
            issue("attentive-dispatch", "system route must be limited to AGGRO and HELP events")
        if not call_has_exact_arguments(
            attentive,
            "OverworldWildRuntime_DispatchTransition",
            ("&runtime->behaviorStackRuntime", "slot", "slotGeneration", "&event", "&transition"),
        ):
            issue("attentive-dispatch", "attentive dispatch uses unrelated runtime identity")
        for field in ("replayExpiry", "flags"):
            if re.search(r"event\." + field + r"(?:\.|\s*=)", attentive):
                issue("ordinary-event", f"attentive event writes replay-only field {field}")

    recovery = body(APPLY_HELPER, "recovery-dispatch")
    if recovery is not None:
        mappings = {
            "OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA": (
                "OWBD_TRIGGER_STAMINA_EXHAUSTED", True
            ),
            "OW_WILD_RUNTIME_RECOVERY_ORIGIN_RAM_CRASH": (
                "OWBD_TRIGGER_RAM_CRASH", True
            ),
            "OW_WILD_RUNTIME_RECOVERY_ORIGIN_THROW_RECOVERY": (
                "OWBD_TRIGGER_THROW_RECOVERY", True
            ),
            "OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED": (
                "OWBD_TRIGGER_FLED", True
            ),
        }
        for origin, (trigger_name, needs_route) in mappings.items():
            case = switch_case_body(recovery, "origin", origin)
            if case is None or len(exact_assignment(case, r"event\.trigger", trigger_name)) != 1:
                issue("recovery-dispatch", f"{origin} must dispatch {trigger_name}")
                continue
            if not effect_is_unconditional_in_range(
                case,
                0,
                len(case),
                rf"event\.trigger\s*=\s*{trigger_name}",
            ):
                issue(
                    "route-dominance",
                    f"{origin} trigger must unconditionally dominate dispatch",
                )
            route_count = len(
                exact_assignment(case, r"event\.systemRoute", trigger_name)
            )
            if needs_route and route_count != 1:
                issue(
                    "recovery-dispatch",
                    f"{origin} must publish system route {trigger_name}",
                )
            if needs_route and not effect_is_unconditional_in_range(
                case,
                0,
                len(case),
                rf"event\.systemRoute\s*=\s*{trigger_name}",
            ):
                issue(
                    "route-dominance",
                    f"{origin} system route must unconditionally dominate dispatch",
                )
            if not needs_route and write_records(case, r"event\.systemRoute"):
                issue(
                    "recovery-dispatch",
                    f"{origin} must leave systemRoute zero",
                )
        dispatch = call_index(recovery, "OverworldWildRuntime_DispatchTransition")
        zero = call_index(recovery, "memset")
        switch_start = recovery.find("switch (origin)")
        switch_end = -1
        if switch_start >= 0:
            switch_open = recovery.find("{", switch_start)
            if switch_open >= 0:
                switch_end = matching_delimiter(
                    recovery, switch_open, "{", "}"
                )
        if min(zero, switch_start, switch_end, dispatch) < 0 or not (
            zero < switch_start < switch_end < dispatch
        ):
            issue(
                "route-dominance",
                "the complete origin route switch must dominate generic dispatch",
            )
        elif (
            write_records(recovery[switch_end:dispatch], r"event\.trigger")
            or write_records(recovery[switch_end:dispatch], r"event\.systemRoute")
            or write_records(recovery[switch_end:dispatch], r"event")
            or re.search(
                r"&\s*event\b", recovery[switch_end:dispatch]
            )
            or call_count(
                recovery[switch_end:dispatch], "memset"
            ) != 0
        ):
            issue(
                "route-dominance",
                "the selected transition event must not be overwritten or aliased before dispatch",
            )
        project = call_index(recovery, PROJECT_HELPER)
        present = call_index(recovery, PRESENT_HELPER)
        if min(dispatch, project, present) < 0 or not (dispatch < project < present):
            issue("recovery-dispatch", "recovery must dispatch, project, then present")
        for field in ("replayExpiry", "flags"):
            if re.search(r"event\." + field + r"(?:\.|\s*=)", recovery):
                issue("ordinary-event", f"ordinary recovery event writes replay-only field {field}")
        pending_set = recovery.find(
            "runtime->movementPendingRuntimeTransitions[slot] = origin"
        )
        pending_clear = recovery.find(
            "runtime->movementPendingRuntimeTransitions[slot] =\n"
            "        OW_WILD_RUNTIME_TRANSITION_PENDING_NONE"
        )
        if pending_set < 0 or dispatch < pending_set or pending_clear < dispatch:
            issue(
                "transition-retry",
                "recovery must retain its logical pending origin until dispatch is accepted",
            )
        if "OW_WILD_RUNTIME_STATUS_IDEMPOTENT" not in recovery:
            issue("transition-retry", "recovery retry must accept idempotent completion")

    follower_dispatch = body(
        "OverworldWildSpawns_TryApplyRuntimeFollowerRemove", "follower-remove"
    )
    if follower_dispatch is not None:
        trigger = follower_dispatch.find(
            "event.trigger = OWBD_TRIGGER_FOLLOWER_REMOVE"
        )
        route = follower_dispatch.find(
            "event.systemRoute = OWBD_TRIGGER_FOLLOWER_REMOVE"
        )
        dispatch = call_index(
            follower_dispatch, "OverworldWildRuntime_DispatchTransition"
        )
        pending = follower_dispatch.find(
            "OW_WILD_RUNTIME_TRANSITION_PENDING_FOLLOWER_REMOVE"
        )
        clear = follower_dispatch.rfind(
            "OW_WILD_RUNTIME_TRANSITION_PENDING_NONE"
        )
        if min(trigger, route, dispatch, pending, clear) < 0 or not (
            pending < trigger < route < dispatch < clear
        ):
            issue(
                "follower-remove",
                "follower remove must retain intent and dispatch its authored route before clearing intent",
            )
        if "OW_WILD_RUNTIME_STATUS_IDEMPOTENT" not in follower_dispatch:
            issue("follower-remove", "follower remove must accept idempotent completion")

    remove_follower = body("OverworldWildSpawns_RemoveFollower", "follower-remove")
    if remove_follower is not None:
        dispatch = call_index(
            remove_follower, "OverworldWildSpawns_TryApplyRuntimeFollowerRemove"
        )
        quarantine = call_index(
            remove_follower, "OverworldWildSpawns_QuarantinePoisonedPresentation"
        )
        reset = call_index(remove_follower, "OverworldWildSpawns_ResetSlotState")
        delete = call_index(remove_follower, "DeleteMapObject")
        if min(dispatch, quarantine, reset, delete) < 0 or not (
            dispatch < quarantine < reset < delete
        ):
            issue(
                "follower-remove",
                "follower remove must dispatch before presentation deletion and destructive reset",
            )
        if "OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING" not in remove_follower:
            issue("follower-remove", "failed follower removal must retain retry intent")

    retry = body(
        "OverworldWildSpawns_RetryPendingRuntimeTransitions",
        "transition-retry",
    )
    if retry is not None:
        if call_count(retry, APPLY_HELPER) != 1 or call_count(
            retry, "OverworldWildSpawns_RemoveFollower"
        ) != 1:
            issue(
                "transition-retry",
                "retry loop must service recovery and follower-remove intent",
            )

    route_calls = (
        (
            "OverworldWildSpawns_TryStartFrameDrivenActiveMovementCommand",
            "OW_WILD_RUNTIME_RECOVERY_ORIGIN_THROW_RECOVERY",
        ),
        (
            "OverworldWildSpawns_EndRamCrash",
            "OW_WILD_RUNTIME_RECOVERY_ORIGIN_RAM_CRASH",
        ),
        (
            "OverworldWildSpawns_OverlayCleanupPendingBattle",
            "OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED",
        ),
    )
    for caller_name, origin in route_calls:
        caller = body(caller_name, "route-callsite")
        if caller is None:
            continue
        if not call_has_exact_arguments(
            caller,
            APPLY_HELPER,
            ("state", "slot", origin, "NULL"),
        ):
            issue(
                "route-callsite",
                f"{caller_name} must preserve the one-shot {origin} source",
            )
        if origin == "OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED":
            apply = call_index(caller, APPLY_HELPER)
            clear = caller.rfind("OverworldWildSpawns_ResetPendingBattle")
            if apply < 0 or clear < apply:
                issue(
                    "route-callsite",
                    "FLED intent must be recorded before pending battle cleanup",
                )
            authenticated = any(
                "OW_WILD_BATTLE_DISPOSITION_FLED" in region.condition
                and "OverworldWildSpawns_IsMovementFieldContextCurrent"
                    in region.condition
                and "OverworldWildSpawns_IsCurrentSpawnObject"
                    in region.condition
                and "&state->spawns[slot]" in region.condition
                and region.contains_in_then(apply)
                for region in if_regions(caller)
            )
            if not authenticated:
                issue(
                    "fled-auth",
                    "FLED dispatch must authenticate current field context and retained slot object",
                )

    capture = body(
        "OverworldWildSpawns_CaptureMovementCommandOrigin", "command-origin"
    )
    if capture is not None and not call_has_exact_arguments(
        capture,
        "OverworldWildRuntime_CaptureCommandOrigin",
        (
            "&runtime->behaviorStackRuntime",
            "&runtime->movementCommandOrigins",
            "slot",
            "slotGeneration",
            "&identity",
        ),
    ):
        issue("command-origin", "movement command origin capture lost runtime identity")
    consume = body(
        "OverworldWildSpawns_ConsumeMovementCommandOrigin", "command-origin"
    )
    if consume is not None and not call_has_exact_arguments(
        consume,
        "OverworldWildRuntime_ConsumeCommandOrigin",
        (
            "&runtime->behaviorStackRuntime",
            "&runtime->movementCommandOrigins",
            "slot",
            "slotGeneration",
            "&identity",
            "originOut",
        ),
    ):
        issue("command-origin", "movement command origin consume lost runtime identity")
    finished = body(
        "OverworldWildSpawns_HandleFinishedMovementCommand", "command-origin"
    )
    if finished is not None and call_count(
        finished, "OverworldWildSpawns_ConsumeMovementCommandOrigin"
    ) != 1:
        issue("command-origin", "completed movement must consume exactly one origin")
    reset_slot = body("OverworldWildSpawns_ResetSlotState", "command-origin")
    if reset_slot is not None:
        invalidate = call_index(
            reset_slot, "OverworldWildSpawns_InvalidateMovementCommandOrigin"
        )
        destructive = call_index(
            reset_slot, "OverworldWildRuntime_DestructivelyInvalidateSlot"
        )
        if invalidate < 0 or destructive < invalidate:
            issue(
                "command-origin",
                "slot reset must invalidate command origin before runtime destruction",
            )

    cleanup = body("OverworldWildSpawns_CleanupResidentData", "lifecycle")
    if cleanup is not None:
        prefix_clear = cleanup.find(
            "offsetof(OverworldWildOverlayRuntimeState, behaviorStackRuntime)"
        )
        cold = call_index(cleanup, "OverworldWildRuntime_MarkResidentCold")
        if prefix_clear < 0 or cold < prefix_clear:
            issue(
                "lifecycle",
                "resident cleanup must preserve the runtime suffix before marking it cold",
            )
        pending_mentions = [
            match.start()
            for match in re.finditer(
                r"movementPendingRuntimeTransitions", cleanup
            )
        ]
        if (
            len(pending_mentions) != 2
            or pending_mentions[0] > prefix_clear
            or pending_mentions[1] < prefix_clear
        ):
            issue(
                "lifecycle",
                "resident cleanup must preserve pending logical transitions across the cold boundary",
            )
    ensure = body("OverworldWildSpawns_EnsureRuntimeState", "lifecycle")
    if ensure is not None:
        if "OW_WILD_RUNTIME_LIFETIME_RESIDENT_COLD" not in ensure:
            issue("lifecycle", "cold runtime lifecycle guard is missing")
        if call_count(ensure, "OverworldWildRuntime_BindPrivateIdentity") != 2:
            issue(
                "lifecycle",
                "new and resident-cold runtimes must both bind private identity",
            )
        if call_count(
            ensure, "OverworldWildSpawns_InvalidateAllMovementCommandOrigins"
        ) != 1:
            issue("lifecycle", "resident-cold rebind must invalidate command origins")

    pending = body("OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "timer-replay")
    if pending is not None:
        if call_count(pending, "OverworldWildRuntime_DispatchTransition") != 1:
            issue("timer-replay", "each bounded expiry record must dispatch exactly once")
        assignments = {
            "replayExpiry": "expiry",
            "trigger": "OWBD_TRIGGER_TIRED_EXPIRED",
            "flags": "OW_WILD_RUNTIME_TRANSITION_EVENT_REPLAY",
        }
        for field, value in assignments.items():
            if len(exact_assignment(pending, rf"event\.{field}", value)) != 1:
                issue("timer-replay", f"timer replay must set event.{field} from {value}")
        if not call_has_exact_arguments(
            pending,
            "OverworldWildRuntime_DispatchTransition",
            ("&runtime->behaviorStackRuntime", "expiry.slotIndex", "expiry.slotGeneration", "&event", "&transition"),
        ):
            issue("timer-replay", "timer replay must dispatch the authenticated expiry slot/generation")
        if not call_has_exact_arguments(
            pending, PROJECT_HELPER, ("state", "slot", "&transition")
        ):
            issue("timer-replay", "timer replay must project transition.effectiveAfter")
        if "transition.actionFlags" not in pending:
            issue("timer-replay", "timer replay must consume typed transition actions")

    return issues


COMPLIANT_SOURCE = r"""
typedef struct OverworldWildOverlayRuntimeState {
    u32 movementCommandGenerations[OW_WILD_MAX_SPAWNS];
    u32 movementCommandSerials[OW_WILD_MAX_SPAWNS];
    u32 movementObjectGenerations[OW_WILD_MAX_SPAWNS];
    OverworldWildRuntimeCommandOriginBank movementCommandOrigins;
    OverworldWildBehaviorStackRuntime behaviorStackRuntime;
} OverworldWildOverlayRuntimeState;

static BOOL OverworldWildSpawns_CaptureMovementCommandOrigin(State *state, int slot) {
    Runtime *runtime = OW_WILD_RUNTIME(state);
    OverworldWildRuntimeCommandIdentity identity;
    OverworldWildRuntimeEffectiveCache effective;
    OverworldWildRuntimeStatus status;
    u32 nextCommandGeneration;
    u32 nextCommandSerial;
    status = OverworldWildRuntime_GetEffectiveCache(&runtime->behaviorStackRuntime,
        slot, slotGeneration, &effective);
    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }
    nextCommandGeneration = runtime->movementCommandGenerations[slot];
    nextCommandGeneration++;
    if (nextCommandGeneration == 0) { nextCommandGeneration = 1; }
    nextCommandSerial = runtime->movementCommandSerials[slot];
    nextCommandSerial++;
    if (nextCommandSerial == 0) { nextCommandSerial = 1; }
    memset(&identity, 0, sizeof(identity));
    identity.commandGeneration = nextCommandGeneration;
    identity.commandSerial = nextCommandSerial;
    identity.objectGeneration = runtime->movementObjectGenerations[slot];
    identity.staminaPolicyGeneration = effective.effectiveGeneration;
    identity.staminaPolicyId = effective.controllerId;
    status = OverworldWildRuntime_CaptureCommandOrigin(&runtime->behaviorStackRuntime,
        &runtime->movementCommandOrigins, slot, slotGeneration, &identity);
    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }
    runtime->movementCommandGenerations[slot] = nextCommandGeneration;
    runtime->movementCommandSerials[slot] = nextCommandSerial;
    return TRUE;
}
static BOOL OverworldWildSpawns_ConsumeMovementCommandOrigin(State *state, int slot,
    OverworldWildRuntimeCommandOrigin *originOut) {
    Runtime *runtime = OW_WILD_RUNTIME(state);
    OverworldWildRuntimeCommandIdentity identity;
    OverworldWildRuntimeEffectiveCache effective;
    OverworldWildRuntimeStatus status;
    status = OverworldWildRuntime_GetEffectiveCache(&runtime->behaviorStackRuntime,
        slot, slotGeneration, &effective);
    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }
    memset(&identity, 0, sizeof(identity));
    identity.commandGeneration = runtime->movementCommandGenerations[slot];
    identity.commandSerial = runtime->movementCommandSerials[slot];
    identity.objectGeneration = runtime->movementObjectGenerations[slot];
    identity.staminaPolicyGeneration = effective.effectiveGeneration;
    identity.staminaPolicyId = effective.controllerId;
    status = OverworldWildRuntime_ConsumeCommandOrigin(&runtime->behaviorStackRuntime,
        &runtime->movementCommandOrigins, slot, slotGeneration, &identity, originOut);
    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }
    return TRUE;
}
static void OverworldWildSpawns_InvalidateMovementCommandOrigin(State *state, int slot) {
    Runtime *runtime = OW_WILD_RUNTIME(state);
    OverworldWildRuntime_InvalidateCommandOrigin(&runtime->movementCommandOrigins, slot);
    runtime->movementCommandGenerations[slot]++;
    if (runtime->movementCommandGenerations[slot] == 0) { runtime->movementCommandGenerations[slot] = 1; }
    runtime->movementCommandSerials[slot] = 0;
}
static void OverworldWildSpawns_InvalidateAllMovementCommandOrigins(State *state) {
    Runtime *runtime = OW_WILD_RUNTIME(state);
    int slot;
    OverworldWildRuntime_InvalidateAllCommandOrigins(&runtime->movementCommandOrigins);
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        runtime->movementCommandGenerations[slot]++;
        if (runtime->movementCommandGenerations[slot] == 0) { runtime->movementCommandGenerations[slot] = 1; }
        runtime->movementCommandSerials[slot] = 0;
    }
}
static void OverworldWildSpawns_ResetSlotMovementCommand(void) { OverworldWildSpawns_InvalidateMovementCommandOrigin(); }
static void OverworldWildSpawns_ClearStagedHopMovementListTask(void) { OverworldWildSpawns_InvalidateMovementCommandOrigin(); }
static void OverworldWildSpawns_CancelNativeHeldMovementForSlot(void) { OverworldWildSpawns_InvalidateMovementCommandOrigin(); }
static void OverworldWildSpawns_ResetSlotState(void) { OverworldWildSpawns_InvalidateMovementCommandOrigin(); }
static void OverworldWildSpawns_ResetAllMovementCommands(void) { OverworldWildSpawns_InvalidateAllMovementCommandOrigins(); }
static void OverworldWildSpawns_DetachAllMovementStateOnContextLoss(void) { OverworldWildSpawns_InvalidateAllMovementCommandOrigins(); }
static void OverworldWildSpawns_RecreateSpawnObjectAtTile(void) {
    OverworldWildSpawns_InvalidateMovementCommandOrigin();
    runtime->movementObjectGenerations[slot]++;
    if (runtime->movementObjectGenerations[slot] == 0) { runtime->movementObjectGenerations[slot] = 1; }
    state->spawns[slot].object = replacement;
}
static BOOL OverworldWildSpawns_StartMovementCommandForSlot(void) {
    if (!OverworldWildSpawns_CaptureMovementCommandOrigin()) { return FALSE; }
    MapObject_StartMovementCommandInternal();
    return TRUE;
}
static BOOL OverworldWildSpawns_TryStartPhantomTeleportToTile(void) {
    if (!OverworldWildSpawns_CaptureMovementCommandOrigin()) { return FALSE; }
    OverworldWildSpawns_SetObjectTile();
    return TRUE;
}
static BOOL OverworldWildSpawns_StartPreparedCustomJumpCommand(void) {
    if (!OverworldWildSpawns_CaptureMovementCommandOrigin()) { return FALSE; }
    MapObject_StartMovementCommand();
    return TRUE;
}
static BOOL OverworldWildSpawns_StartWrappedCanopyJump2Probe(void) {
    if (!OverworldWildSpawns_CaptureMovementCommandOrigin()) { return FALSE; }
    MapObject_StartMovementList();
    return TRUE;
}
static void OverworldWildSpawns_InitSpawnSlotState(void) {
    OverworldWildRuntimeStaticContext staticContext;
    OverworldWildRuntimeStatus status;
    Runtime *runtime = OW_WILD_RUNTIME(state);
    runtime->movementObjectGenerations[slot]++;
    if (runtime->movementObjectGenerations[slot] == 0) { runtime->movementObjectGenerations[slot] = 1; }
    OverworldWildRuntime_MarkSlotAssigned();
    state->spawns[slot] = spawn;
    state->movementBehaviorClasses[slot] = behaviorClass;
    runtime->movementBehaviorLimitKeys[slot] = behaviorLimitKey;
    OverworldWildSpawns_BuildRuntimeStaticContext(&staticContext);
    status = OverworldWildRuntime_PrimeCanonicalEffectiveCache(&runtime->behaviorStackRuntime,
        slot, slotGeneration, &staticContext, &resolved);
    if (status != OW_WILD_RUNTIME_STATUS_OK
        && status != OW_WILD_RUNTIME_STATUS_IDEMPOTENT) {
        OverworldWildSpawns_ResetSlotState();
        return;
    }
}
static void OverworldWildSpawns_DeleteSpawnProxy(void *primaryObject) {
    void *proxyObject = GetSpawnProxy();
    (void)primaryObject;
    DeleteMapObject(proxyObject);
}
static void OverworldWildSpawns_DeleteReassignedProxy(void *primaryObject) {
    void *candidate = primaryObject;
    candidate = GetSpawnProxy();
    DeleteMapObject(candidate);
}
static void OverworldWildSpawns_DeleteVictim(void *victim) {
    DeleteMapObject(victim);
}
static void OverworldWildSpawns_KeepVictim(void *victim) {
    (void)victim;
}
static BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {
    object = OverworldWildSpawns_CreateObject();
    if (!OverworldWildSpawns_InitSpawnSlotState(
            state, fieldSystem, terrain, slot, object, encounter,
            prepared->shiny, prepared->behaviorClass,
            prepared->behaviorLimitKey, prepared->playerBallCatchValue)) {
        DeleteMapObject(object);
        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame);
        return FALSE;
    }
    OverworldWildSpawns_StartSpawnStartup(object);
    OverworldWildSpawns_DeleteSpawnProxy(object);
    OverworldWildSpawns_DeleteReassignedProxy(object);
    void (*conditionalSafe)(void *) = OverworldWildSpawns_DeleteVictim;
    if (keepObject) {
        conditionalSafe = OverworldWildSpawns_KeepVictim;
    } else {
        conditionalSafe = OverworldWildSpawns_KeepVictim;
    }
    conditionalSafe(object);
    void (*nestedSafe)(void *) = OverworldWildSpawns_DeleteVictim;
    if (outer) {
        if (inner) {
            nestedSafe = OverworldWildSpawns_KeepVictim;
        } else {
            nestedSafe = OverworldWildSpawns_KeepVictim;
        }
    } else {
        if (inner) {
            nestedSafe = OverworldWildSpawns_KeepVictim;
        } else {
            nestedSafe = OverworldWildSpawns_KeepVictim;
        }
    }
    nestedSafe(object);
    void (*branchLocalSafe)(void *) = OverworldWildSpawns_KeepVictim;
    if (outer) {
        branchLocalSafe = OverworldWildSpawns_DeleteVictim;
    } else {
        branchLocalSafe(object);
    }
    return TRUE;
}
static BOOL OverworldWildSpawns_ConvertRuntimeEffectiveCacheToLegacyBehavior(void) {
    profileOut->alertState = effective->controllerValues[0];
    profileOut->alertEmote = effective->controllerValues[1];
    profileOut->alertTime = effective->controllerValues[2];
    profileOut->alertness = effective->controllerValues[3];
    profileOut->alertRange = effective->controllerValues[4];
    profileOut->alertChance = effective->controllerValues[5];
    profileOut->stamina = effective->controllerValues[6];
    profileOut->restTime = effective->controllerValues[7];
    profileOut->range = effective->stateValues[4];
    profileOut->jumpLevel = effective->stateValues[5];
    profileOut->hopTime = effective->stateValues[12];
    profileOut->attentiveChaseBoostDistance = effective->stateValues[18];
    profileOut->attentiveChaseBoostSpeed = effective->stateValues[19];
    profileOut->attentiveCircleRadius = effective->stateValues[20];
    profileOut->attentiveContinueWhenArrived = effective->stateValues[21];
    profileOut->attentiveAvoidPreviousTile = effective->stateValues[22];
    profileOut->chainPauseAction = effective->stateValues[23];
    profileOut->chainMovementVariance = effective->stateValues[24];
    profileOut->chainPauseVariance = effective->stateValues[25];
    profileOut->attentiveBattle = effective->stateValues[26];
    profileOut->playerAdjacentDirectionMasks = effective->stateValues[27];
    switch (effective->semanticRole) {
    case OWBD_ROLE_CALM:
        profileOut->chillState = effective->stateValues[0];
        profileOut->chillAction = effective->stateValues[1];
        profileOut->chillTarget = effective->stateValues[2];
        profileOut->chillSpeed = effective->stateValues[3];
        profileOut->chillAllowedTile = effective->stateValues[6];
        profileOut->chillAllowedTile2 = effective->stateValues[7];
        profileOut->hopAllowNonCardinal = effective->stateValues[8];
        profileOut->hopMinDistance = effective->stateValues[9];
        profileOut->hopMaxDistance = effective->stateValues[10];
        profileOut->hopPause = effective->stateValues[11];
        profileOut->hopSpinSpeed = effective->stateValues[13];
        profileOut->teleportTime = effective->stateValues[14];
        profileOut->teleportPause = effective->stateValues[15];
        profileOut->ramAccelerationSteps = effective->stateValues[16];
        profileOut->ramMaxSpeed = effective->stateValues[17];
        *spotStateOut = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
        break;
    case OWBD_ROLE_ATTENTIVE:
        profileOut->attentiveState = effective->stateValues[0];
        profileOut->movementStyle = effective->stateValues[1];
        profileOut->targetSelector = effective->stateValues[2];
        profileOut->attentiveSpeed = effective->stateValues[3];
        profileOut->attentiveAllowedTile = effective->stateValues[6];
        profileOut->attentiveAllowedTile2 = effective->stateValues[7];
        profileOut->attentiveHopAllowNonCardinal = effective->stateValues[8];
        profileOut->attentiveHopMinDistance = effective->stateValues[9];
        profileOut->attentiveHopMaxDistance = effective->stateValues[10];
        profileOut->attentiveHopPause = effective->stateValues[11];
        profileOut->attentiveHopSpinSpeed = effective->stateValues[13];
        profileOut->attentiveTeleportTime = effective->stateValues[14];
        profileOut->attentiveTeleportPause = effective->stateValues[15];
        profileOut->attentiveRamAccelerationSteps = effective->stateValues[16];
        profileOut->attentiveRamMaxSpeed = effective->stateValues[17];
        *spotStateOut = OW_WILD_SPAWNER_SPOT_STATE_ACTIVE;
        break;
    case OWBD_ROLE_TIRED:
        profileOut->tiredState = effective->stateValues[0];
        profileOut->specialAction = effective->stateValues[1];
        profileOut->tiredSpeed = effective->stateValues[3];
        profileOut->tiredAllowedTile = effective->stateValues[6];
        profileOut->tiredAllowedTile2 = effective->stateValues[7];
        profileOut->tiredHopAllowNonCardinal = effective->stateValues[8];
        profileOut->tiredHopMinDistance = effective->stateValues[9];
        profileOut->tiredHopMaxDistance = effective->stateValues[10];
        profileOut->tiredHopPause = effective->stateValues[11];
        profileOut->hopSpinSpeed = effective->stateValues[13];
        profileOut->tiredTeleportTime = effective->stateValues[14];
        profileOut->tiredTeleportPause = effective->stateValues[15];
        profileOut->tiredRamAccelerationSteps = effective->stateValues[16];
        profileOut->tiredRamMaxSpeed = effective->stateValues[17];
        *spotStateOut = OW_WILD_SPAWNER_SPOT_STATE_TIRED;
        break;
    case OWBD_ROLE_ASLEEP:
        profileOut->tiredState = effective->stateValues[0];
        profileOut->specialAction = effective->stateValues[1];
        profileOut->tiredSpeed = effective->stateValues[3];
        profileOut->tiredAllowedTile = effective->stateValues[6];
        profileOut->tiredAllowedTile2 = effective->stateValues[7];
        profileOut->tiredHopAllowNonCardinal = effective->stateValues[8];
        profileOut->tiredHopMinDistance = effective->stateValues[9];
        profileOut->tiredHopMaxDistance = effective->stateValues[10];
        profileOut->tiredHopPause = effective->stateValues[11];
        profileOut->hopSpinSpeed = effective->stateValues[13];
        profileOut->tiredTeleportTime = effective->stateValues[14];
        profileOut->tiredTeleportPause = effective->stateValues[15];
        profileOut->tiredRamAccelerationSteps = effective->stateValues[16];
        profileOut->tiredRamMaxSpeed = effective->stateValues[17];
        *spotStateOut = OW_WILD_SPAWNER_SPOT_STATE_TIRED;
        break;
    default:
        return FALSE;
    }
    *primitivesOut = OverworldWildSpawns_ResolveBehaviorPrimitives(profileOut);
    switch (effective->semanticRole) {
    case OWBD_ROLE_CALM:
        primitivesOut->chillLocomotion = effective->primitives[0];
        primitivesOut->chillTarget = effective->primitives[1];
        primitivesOut->alertReaction = effective->primitives[2];
        break;
    case OWBD_ROLE_ATTENTIVE:
        primitivesOut->attentiveLocomotion = effective->primitives[0];
        primitivesOut->attentiveTarget = effective->primitives[1];
        primitivesOut->activeReaction = effective->primitives[2];
        break;
    case OWBD_ROLE_TIRED:
        primitivesOut->tiredLocomotion = effective->primitives[0];
        primitivesOut->tiredTarget = effective->primitives[1];
        primitivesOut->tiredReaction = effective->primitives[2];
        break;
    case OWBD_ROLE_ASLEEP:
        primitivesOut->tiredLocomotion = effective->primitives[0];
        primitivesOut->tiredTarget = effective->primitives[1];
        primitivesOut->tiredReaction = effective->primitives[2];
        break;
    }
    if (effective->primitives[3] != effective->stateValues[3]
        || effective->primitives[4] != effective->stateValues[4]) { return FALSE; }
    *capabilityMaskOut = effective->capabilityMask;
    return TRUE;
}
static BOOL OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(void) {
    Runtime *runtime = OW_WILD_RUNTIME(state);
    OverworldWildRuntimeEffectiveCache effective;
    OverworldWildRuntimeStatus status;
    status = OverworldWildRuntime_GetEffectiveCache(&runtime->behaviorStackRuntime,
        slot, slotGeneration, &effective);
    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }
    if (!OverworldWildSpawns_ConvertRuntimeEffectiveCacheToLegacyBehavior(
            &effective, profileOut, primitivesOut, &spotState, &capabilityMask)) { return FALSE; }
    state->movementSpotStates[slot] = spotState;
    runtime->movementFrameDrivenActiveMask = capabilityMask;
    return TRUE;
}
static void OverworldWildSpawns_HandleFinishedMovementCommand(void) {
    Runtime *runtime;
    OverworldWildRuntimeCommandOrigin origin;
    OverworldWildRuntimeEffectiveCache effective;
    OverworldWildRuntimeStatus status;
    runtime = OW_WILD_RUNTIME(state);
    if (!OverworldWildSpawns_ConsumeMovementCommandOrigin(state, slot, &origin)) { return; }
    OverworldWildSpawns_RecordFinishedMovementHistory();
    status = OverworldWildRuntime_GetEffectiveCache(&runtime->behaviorStackRuntime,
        slot, slotGeneration, &effective);
    if (status != OW_WILD_RUNTIME_STATUS_OK) { return; }
    if (state->movementSpotStates[slot] != OW_WILD_SPAWNER_SPOT_STATE_ACTIVE) { return; }
    if (OverworldWildSpawns_CurrentSpotUsesRamLocomotion(
            &primitives, state->movementSpotStates[slot])) { return; }
    if (origin.objectGeneration != runtime->movementObjectGenerations[slot]
        || origin.staminaPolicyId != effective.controllerId
        || origin.staminaPolicyGeneration != effective.effectiveGeneration) { return; }
    if (effective.controllerValues[6] == 0) { return; }
    state->movementActiveSteps[slot]++;
    if (state->movementActiveSteps[slot] < effective.controllerValues[6]) { return; }
    if (!OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(
            state, slot, OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA, &origin)) { return; }
}
static void OverworldWildSpawns_FinishPendingStagedHop(void) {
    if (finishWithTired && effective.controllerValues[6] > 0) {
        state->movementActiveSteps[slot] = effective.controllerValues[6] - 1;
    }
    OverworldWildSpawns_HandleFinishedMovementCommand(state, slot);
}
static void OverworldWildSpawns_TryStartFrameDrivenActiveMovementCommand(void) {
    if (OverworldWildSpawns_StartPreparedCustomJumpCommand()) {
        OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(
            state, slot, OW_WILD_RUNTIME_RECOVERY_ORIGIN_THROW_RECOVERY);
    } else {
        OverworldWildSpawns_ReleaseThrowTargetAtCurrentTile();
    }
}
static void OverworldWildSpawns_EndRamCrash(void) {
    if (state->movementSpotStates[slot] != OW_WILD_SPAWNER_SPOT_STATE_ACTIVE) { return; }
    if (state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_ACTIVE) {
        if (OverworldWildSpawns_TryStartRamCrashBattleImpact(
                state, state->movementFieldSystem, slot, object,
                state->movementRamDirections[slot], profile)) { return; }
        OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(
            OW_WILD_RUNTIME_RECOVERY_ORIGIN_RAM_CRASH);
    }
}
static void OverworldWildSpawns_TryStartRamCrashBattleImpact(void) { StartBattle(); }
static void OverworldWildSpawns_OverlayCleanupPendingBattle(void) {
    if (disposition == OW_WILD_BATTLE_DISPOSITION_FLED
        && state->pendingSlot >= 0 && state->pendingSlot < OW_WILD_MAX_SPAWNS
        && OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)
        && OverworldWildSpawns_IsCurrentSpawnObject(
            fieldSystem, &state->spawns[state->pendingSlot])) {
        OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(
            OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED);
    }
}
static BOOL OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(void) {
    OverworldWildRuntimeStatus status;
    status = OverworldWildRuntime_ResolveRecoveryCandidate(&context, origin, &candidate);
    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }
    status = OverworldWildRuntime_Apply();
    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }
    OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(state, slot, &applyResult);
    OverworldWildSpawns_PresentRuntimeTiredState();
    OverworldWildSpawns_EnsureFrameMovementTask();
    return TRUE;
}
static void OverworldWildSpawns_FrameMovementTask(void) {
    if (!OverworldWildSpawns_IsMovementFieldContextCurrent()) { Detach(); return; }
    OverworldWildSpawns_TickRuntimeFrameTimers();
    if (presentationRestorePending) { return; }
    if (currentSpawnMask == 0) { return; }
    if (OverworldWildSpawns_TryStartCustomJumpRamProbe()) { return; }
    if (heavyWorkMask == 0) { return; }
}
static void OverworldWildSpawns_TickRuntimeFrameTimers(void) {
    Runtime *runtime = OW_WILD_RUNTIME(state);
    status = OverworldWildRuntime_TickFrameTimers(&runtime->behaviorStackRuntime,
        presentationGateMask, tickResults);
    if (status != OW_WILD_RUNTIME_STATUS_OK) { return; }
    OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries();
}
static void OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries(void) {
    Runtime *runtime = OW_WILD_RUNTIME(state);
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        pendingCount = OverworldWildRuntime_GetPendingTimerExpiryCount(
            &runtime->behaviorStackRuntime, slot, slotGeneration);
        for (pendingIndex = 0;
             pendingIndex < pendingCount && pendingIndex < OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT;
             pendingIndex++) {
            status = OverworldWildRuntime_GetPendingTimerExpiryByIndex(
                &runtime->behaviorStackRuntime, slot, slotGeneration,
                pendingIndex, &expiry);
            if (status != OW_WILD_RUNTIME_STATUS_OK) { continue; }
            status = OverworldWildRuntime_RecoverExpiredTimer(
                &runtime->behaviorStackRuntime, &expiry, &recovery);
            if (status != OW_WILD_RUNTIME_STATUS_OK) { continue; }
            OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(state, slot, &recovery);
            OverworldWildSpawns_PresentRuntimeTiredState();
        }
    }
    OverworldWildSpawns_EnsureFrameMovementTask();
}
static void OverworldWildSpawns_TickTiredEmote(void) {
    if (OverworldWildSpawns_HasRuntimeTimerWork()) { return; }
    movementEmoteTimers[slot]--;
}
static BOOL OverworldWildSpawns_HasRuntimeTimerWork(void) {
    Runtime *runtime = OW_WILD_RUNTIME(state);
    return OverworldWildRuntime_GetTimerCount(
            &runtime->behaviorStackRuntime, slot, slotGeneration) != 0
        || OverworldWildRuntime_GetPendingTimerExpiryCount(
            &runtime->behaviorStackRuntime, slot, slotGeneration) != 0;
}
static int OverworldWildSpawns_GetFrameMovementWorkForSlot(void) {
    u32 frameWorkMask = movementInProgress;
    if (OverworldWildSpawns_HasRuntimeTimerWork(state, slot)) {
        frameWorkMask |= OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
    }
    return frameWorkMask;
}
"""


def replace_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise AssertionError(f"mutation expected one {old!r}, found {count}")
    return source.replace(old, new, 1)


def replace_once_in_function(
    source: str, function: str, old: str, new: str
) -> str:
    start, end = function_body_span(source, function)
    body = source[start:end]
    count = body.count(old)
    if count != 1:
        raise AssertionError(
            f"mutation in {function} expected one {old!r}, found {count}"
        )
    return source[:start] + body.replace(old, new, 1) + source[end:]


def disable_once_in_function(source: str, function: str, statement: str) -> str:
    return replace_once_in_function(
        source,
        function,
        statement,
        "    if (0) {\n" + statement + "\n    }",
    )


def preprocess_disable_once_in_function(
    source: str, function: str, statement: str
) -> str:
    return replace_once_in_function(
        source,
        function,
        statement,
        "#if 0\n" + statement + "\n#endif",
    )


def mutation_cases() -> list[tuple[str, str, str]]:
    source = COMPLIANT_SOURCE
    cases: list[tuple[str, str, str]] = []

    def add(label: str, old: str, new: str, category: str) -> None:
        cases.append((label, replace_once(source, old, new), category))

    def add_in(
        label: str, function: str, old: str, new: str, category: str
    ) -> None:
        cases.append(
            (
                label,
                replace_once_in_function(source, function, old, new),
                category,
            )
        )

    add("comment-only field", "    u32 movementCommandSerials[OW_WILD_MAX_SPAWNS];", "    /* u32 movementCommandSerials[OW_WILD_MAX_SPAWNS]; */", "runtime-layout")
    add("wrong field type", "    u32 movementObjectGenerations[OW_WILD_MAX_SPAWNS];", "    u16 movementObjectGenerations[OW_WILD_MAX_SPAWNS];", "runtime-layout")
    add("field order", "    u32 movementCommandGenerations[OW_WILD_MAX_SPAWNS];\n    u32 movementCommandSerials[OW_WILD_MAX_SPAWNS];", "    u32 movementCommandSerials[OW_WILD_MAX_SPAWNS];\n    u32 movementCommandGenerations[OW_WILD_MAX_SPAWNS];", "runtime-layout")
    add("resident suffix", "    OverworldWildBehaviorStackRuntime behaviorStackRuntime;\n}", "    OverworldWildBehaviorStackRuntime behaviorStackRuntime;\n    u32 illegalSuffix;\n}", "runtime-layout")
    add_in("capture Stage A comment", CAPTURE_HELPER, "    status = OverworldWildRuntime_CaptureCommandOrigin(&runtime->behaviorStackRuntime,", "    /* OverworldWildRuntime_CaptureCommandOrigin(); */\n    status = FakeCapture(&runtime->behaviorStackRuntime,", "capture-wrapper")
    add_in("capture generation no advance", CAPTURE_HELPER, "    nextCommandGeneration++;", "    nextCommandGeneration = nextCommandGeneration;", "capture-wrapper")
    add_in("capture serial no advance", CAPTURE_HELPER, "    nextCommandSerial++;", "    nextCommandSerial = 1;", "capture-wrapper")
    add_in("capture stale identity", CAPTURE_HELPER, "    identity.commandSerial = nextCommandSerial;", "    identity.commandSerial = 1;", "capture-wrapper")
    add_in("capture ignored status", CAPTURE_HELPER, "        &runtime->movementCommandOrigins, slot, slotGeneration, &identity);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    runtime->movementCommandGenerations[slot] = nextCommandGeneration;", "        &runtime->movementCommandOrigins, slot, slotGeneration, &identity);\n    runtime->movementCommandGenerations[slot] = nextCommandGeneration;", "capture-wrapper")
    add_in("capture effective-cache comment", CAPTURE_HELPER, "    status = OverworldWildRuntime_GetEffectiveCache(&runtime->behaviorStackRuntime,", "    /* OverworldWildRuntime_GetEffectiveCache(); */\n    status = FakeGetEffective(&runtime->behaviorStackRuntime,", "capture-wrapper")
    add_in("capture effective-cache ignored", CAPTURE_HELPER, "        slot, slotGeneration, &effective);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    nextCommandGeneration = runtime->movementCommandGenerations[slot];", "        slot, slotGeneration, &effective);\n    nextCommandGeneration = runtime->movementCommandGenerations[slot];", "capture-wrapper")
    add_in("capture carriers published before OK", CAPTURE_HELPER, "    status = OverworldWildRuntime_CaptureCommandOrigin(&runtime->behaviorStackRuntime,\n        &runtime->movementCommandOrigins, slot, slotGeneration, &identity);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    runtime->movementCommandGenerations[slot] = nextCommandGeneration;\n    runtime->movementCommandSerials[slot] = nextCommandSerial;", "    runtime->movementCommandGenerations[slot] = nextCommandGeneration;\n    runtime->movementCommandSerials[slot] = nextCommandSerial;\n    status = OverworldWildRuntime_CaptureCommandOrigin(&runtime->behaviorStackRuntime,\n        &runtime->movementCommandOrigins, slot, slotGeneration, &identity);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", "capture-wrapper")
    add_in("capture guard checks unrelated status", CAPTURE_HELPER, "&identity);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    runtime->movementCommandGenerations", "&identity);\n    if (otherStatus != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    runtime->movementCommandGenerations", "capture-wrapper")
    add_in("capture cache status overwritten", CAPTURE_HELPER, "        slot, slotGeneration, &effective);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    nextCommandGeneration", "        slot, slotGeneration, &effective);\n    status = OW_WILD_RUNTIME_STATUS_OK;\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    nextCommandGeneration", "capture-wrapper")
    add_in(
        "capture pre-call status pointer overwrite",
        CAPTURE_HELPER,
        "    status = OverworldWildRuntime_GetEffectiveCache(&runtime->behaviorStackRuntime,\n        slot, slotGeneration, &effective);",
        "    OverworldWildRuntimeStatus *statusAlias = &status;\n    status = OverworldWildRuntime_GetEffectiveCache(&runtime->behaviorStackRuntime,\n        slot, slotGeneration, &effective);\n    *statusAlias = OW_WILD_RUNTIME_STATUS_OK;",
        "capture-wrapper",
    )
    add_in(
        "capture effective output alias",
        CAPTURE_HELPER,
        "        slot, slotGeneration, &effective);\n    if (status != OW_WILD_RUNTIME_STATUS_OK)",
        "        slot, slotGeneration, &effective);\n    ObserveEffective(&effective);\n    if (status != OW_WILD_RUNTIME_STATUS_OK)",
        "capture-wrapper",
    )
    add_in("capture Stage A status overwritten", CAPTURE_HELPER, "        &runtime->movementCommandOrigins, slot, slotGeneration, &identity);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", "        &runtime->movementCommandOrigins, slot, slotGeneration, &identity);\n    status = OW_WILD_RUNTIME_STATUS_OK;\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", "capture-wrapper")
    add_in("capture Stage A status address escapes", CAPTURE_HELPER, "        &runtime->movementCommandOrigins, slot, slotGeneration, &identity);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", "        &runtime->movementCommandOrigins, slot, slotGeneration, &identity);\n    ObserveStatus(&status);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", "capture-wrapper")
    add_in("consume Stage A comment", CONSUME_HELPER, "    status = OverworldWildRuntime_ConsumeCommandOrigin(&runtime->behaviorStackRuntime,", "    /* OverworldWildRuntime_ConsumeCommandOrigin(); */\n    status = FakeConsume(&runtime->behaviorStackRuntime,", "consume-wrapper")
    add_in("consume stale identity", CONSUME_HELPER, "    identity.commandGeneration = runtime->movementCommandGenerations[slot];", "    identity.commandGeneration = 7;", "consume-wrapper")
    add_in("consume ignored status", CONSUME_HELPER, "        &runtime->movementCommandOrigins, slot, slotGeneration, &identity, originOut);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    return TRUE;", "        &runtime->movementCommandOrigins, slot, slotGeneration, &identity, originOut);\n    return TRUE;", "consume-wrapper")
    add_in("consume effective-cache comment", CONSUME_HELPER, "    status = OverworldWildRuntime_GetEffectiveCache(&runtime->behaviorStackRuntime,", "    /* OverworldWildRuntime_GetEffectiveCache(); */\n    status = FakeGetEffective(&runtime->behaviorStackRuntime,", "consume-wrapper")
    add_in("consume effective-cache ignored", CONSUME_HELPER, "        slot, slotGeneration, &effective);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    memset(&identity, 0, sizeof(identity));", "        slot, slotGeneration, &effective);\n    memset(&identity, 0, sizeof(identity));", "consume-wrapper")
    add_in("consume guard checks unrelated status", CONSUME_HELPER, "&identity, originOut);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    return TRUE;", "&identity, originOut);\n    if (otherStatus != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    return TRUE;", "consume-wrapper")
    add_in("consume cache status overwritten", CONSUME_HELPER, "        slot, slotGeneration, &effective);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    memset", "        slot, slotGeneration, &effective);\n    status = OW_WILD_RUNTIME_STATUS_OK;\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    memset", "consume-wrapper")
    add_in("consume Stage A status overwritten", CONSUME_HELPER, "        &runtime->movementCommandOrigins, slot, slotGeneration, &identity, originOut);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", "        &runtime->movementCommandOrigins, slot, slotGeneration, &identity, originOut);\n    status = OW_WILD_RUNTIME_STATUS_OK;\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", "consume-wrapper")
    add("native publication unguarded", "    if (!OverworldWildSpawns_CaptureMovementCommandOrigin()) { return FALSE; }\n    MapObject_StartMovementCommandInternal();", "    OverworldWildSpawns_CaptureMovementCommandOrigin();\n    MapObject_StartMovementCommandInternal();", "capture-before-publication")
    add_in("native publication disabled guard", "OverworldWildSpawns_StartMovementCommandForSlot", "if (!OverworldWildSpawns_CaptureMovementCommandOrigin())", "if (!OverworldWildSpawns_CaptureMovementCommandOrigin() && 0)", "capture-before-publication")
    add("phantom publication unguarded", "    if (!OverworldWildSpawns_CaptureMovementCommandOrigin()) { return FALSE; }\n    OverworldWildSpawns_SetObjectTile();", "    OverworldWildSpawns_CaptureMovementCommandOrigin();\n    OverworldWildSpawns_SetObjectTile();", "capture-before-publication")
    add("custom publication unguarded", "    if (!OverworldWildSpawns_CaptureMovementCommandOrigin()) { return FALSE; }\n    MapObject_StartMovementCommand();", "    OverworldWildSpawns_CaptureMovementCommandOrigin();\n    MapObject_StartMovementCommand();", "capture-before-publication")
    add("staged publication unguarded", "    if (!OverworldWildSpawns_CaptureMovementCommandOrigin()) { return FALSE; }\n    MapObject_StartMovementList();", "    OverworldWildSpawns_CaptureMovementCommandOrigin();\n    MapObject_StartMovementList();", "capture-before-publication")
    for label, function in (
        ("slot reset invalidation", "ResetSlotMovementCommand"),
        ("staged cancel invalidation", "ClearStagedHopMovementListTask"),
        ("native cancel invalidation", "CancelNativeHeldMovementForSlot"),
        ("destructive reset invalidation", "ResetSlotState"),
    ):
        add(label, f"static void OverworldWildSpawns_{function}(void) {{ OverworldWildSpawns_InvalidateMovementCommandOrigin(); }}", f"static void OverworldWildSpawns_{function}(void) {{ ClearFields(); }}", "origin-invalidation")
    add("bulk reset invalidation", "static void OverworldWildSpawns_ResetAllMovementCommands(void) { OverworldWildSpawns_InvalidateAllMovementCommandOrigins(); }", "static void OverworldWildSpawns_ResetAllMovementCommands(void) { ClearFields(); }", "origin-invalidation")
    add("detach invalidation", "static void OverworldWildSpawns_DetachAllMovementStateOnContextLoss(void) { OverworldWildSpawns_InvalidateAllMovementCommandOrigins(); }", "static void OverworldWildSpawns_DetachAllMovementStateOnContextLoss(void) { ClearFields(); }", "origin-invalidation")
    add_in("slot invalidator Stage A comment", INVALIDATE_HELPER, "    OverworldWildRuntime_InvalidateCommandOrigin(&runtime->movementCommandOrigins, slot);", "    /* OverworldWildRuntime_InvalidateCommandOrigin(); */", "origin-invalidation")
    add_in("slot invalidator no advance", INVALIDATE_HELPER, "    runtime->movementCommandGenerations[slot]++;", "    runtime->movementCommandGenerations[slot] = 1;", "origin-invalidation")
    add_in("slot invalidator reordered", INVALIDATE_HELPER, "    OverworldWildRuntime_InvalidateCommandOrigin(&runtime->movementCommandOrigins, slot);\n    runtime->movementCommandGenerations[slot]++;", "    runtime->movementCommandGenerations[slot]++;\n    OverworldWildRuntime_InvalidateCommandOrigin(&runtime->movementCommandOrigins, slot);", "origin-invalidation")
    add_in("bulk invalidator Stage A comment", INVALIDATE_ALL_HELPER, "    OverworldWildRuntime_InvalidateAllCommandOrigins(&runtime->movementCommandOrigins);", "    /* OverworldWildRuntime_InvalidateAllCommandOrigins(); */", "origin-invalidation")
    add_in("bulk invalidator no advance", INVALIDATE_ALL_HELPER, "        runtime->movementCommandGenerations[slot]++;", "        runtime->movementCommandGenerations[slot] = 1;", "origin-invalidation")
    bulk_reordered = replace_once_in_function(
        source,
        INVALIDATE_ALL_HELPER,
        "    OverworldWildRuntime_InvalidateAllCommandOrigins(&runtime->movementCommandOrigins);\n",
        "",
    )
    bulk_reordered = replace_once_in_function(
        bulk_reordered,
        INVALIDATE_ALL_HELPER,
        "        runtime->movementCommandSerials[slot] = 0;\n    }",
        "        runtime->movementCommandSerials[slot] = 0;\n    }\n    OverworldWildRuntime_InvalidateAllCommandOrigins(&runtime->movementCommandOrigins);",
    )
    cases.append(("bulk invalidator reordered", bulk_reordered, "origin-invalidation"))
    add("replacement lacks invalidation", "    OverworldWildSpawns_InvalidateMovementCommandOrigin();\n    runtime->movementObjectGenerations[slot]++;", "    runtime->movementObjectGenerations[slot]++;", "origin-invalidation")
    add_in("replacement generation after publication", "OverworldWildSpawns_RecreateSpawnObjectAtTile", "    runtime->movementObjectGenerations[slot]++;\n    if (runtime->movementObjectGenerations[slot] == 0) { runtime->movementObjectGenerations[slot] = 1; }\n    state->spawns[slot].object = replacement;", "    state->spawns[slot].object = replacement;\n    runtime->movementObjectGenerations[slot]++;\n    if (runtime->movementObjectGenerations[slot] == 0) { runtime->movementObjectGenerations[slot] = 1; }", "origin-invalidation")
    add_in("init object generation missing", "OverworldWildSpawns_InitSpawnSlotState", "    runtime->movementObjectGenerations[slot]++;\n    if (runtime->movementObjectGenerations[slot] == 0) { runtime->movementObjectGenerations[slot] = 1; }\n    OverworldWildRuntime_MarkSlotAssigned();", "    OverworldWildRuntime_MarkSlotAssigned();", "canonical-initialization")
    add("canonical prime missing", "    status = OverworldWildRuntime_PrimeCanonicalEffectiveCache(&runtime->behaviorStackRuntime,", "    status = FakePrime(&runtime->behaviorStackRuntime,", "canonical-initialization")
    early_prime = replace_once_in_function(
        source,
        "OverworldWildSpawns_InitSpawnSlotState",
        "    state->spawns[slot] = spawn;\n",
        "",
    )
    early_prime = replace_once_in_function(
        early_prime,
        "OverworldWildSpawns_InitSpawnSlotState",
        "    if (status != OW_WILD_RUNTIME_STATUS_OK\n",
        "    state->spawns[slot] = spawn;\n    if (status != OW_WILD_RUNTIME_STATUS_OK\n",
    )
    cases.append(("canonical prime too early", early_prime, "canonical-initialization"))
    add("canonical status ignored", "    if (status != OW_WILD_RUNTIME_STATUS_OK\n        && status != OW_WILD_RUNTIME_STATUS_IDEMPOTENT) {", "    if (0) {", "canonical-initialization")
    add("canonical status checks unrelated value", "    if (status != OW_WILD_RUNTIME_STATUS_OK\n        && status != OW_WILD_RUNTIME_STATUS_IDEMPOTENT) {", "    if (otherStatus != OW_WILD_RUNTIME_STATUS_OK\n        && otherStatus != OW_WILD_RUNTIME_STATUS_IDEMPOTENT) {", "canonical-initialization")
    add("canonical status uses OR", "    if (status != OW_WILD_RUNTIME_STATUS_OK\n        && status != OW_WILD_RUNTIME_STATUS_IDEMPOTENT) {", "    if (status != OW_WILD_RUNTIME_STATUS_OK\n        || status != OW_WILD_RUNTIME_STATUS_IDEMPOTENT) {", "canonical-initialization")
    add_in("canonical prime status overwritten", "OverworldWildSpawns_InitSpawnSlotState", "        slot, slotGeneration, &staticContext, &resolved);\n    if (status != OW_WILD_RUNTIME_STATUS_OK", "        slot, slotGeneration, &staticContext, &resolved);\n    status = OW_WILD_RUNTIME_STATUS_OK;\n    if (status != OW_WILD_RUNTIME_STATUS_OK", "canonical-initialization")
    add_in(
        "canonical pre-call status pointer overwrite",
        "OverworldWildSpawns_InitSpawnSlotState",
        "    status = OverworldWildRuntime_PrimeCanonicalEffectiveCache(&runtime->behaviorStackRuntime,\n        slot, slotGeneration, &staticContext, &resolved);",
        "    OverworldWildRuntimeStatus *statusAlias = &status;\n    status = OverworldWildRuntime_PrimeCanonicalEffectiveCache(&runtime->behaviorStackRuntime,\n        slot, slotGeneration, &staticContext, &resolved);\n    *statusAlias = OW_WILD_RUNTIME_STATUS_OK;",
        "canonical-initialization",
    )
    add_in(
        "canonical resolved output alias",
        "OverworldWildSpawns_InitSpawnSlotState",
        "        slot, slotGeneration, &staticContext, &resolved);",
        "        slot, slotGeneration, &staticContext, &resolved);\n    ObserveResolved(&resolved);",
        "canonical-initialization",
    )
    add("canonical failure exposed", "        OverworldWildSpawns_ResetSlotState();\n        return;", "        LogPrimeFailure();", "canonical-initialization")
    rollback = "OverworldWildSpawns_SpawnPreparedEncounter"
    add_in(
        "prime rollback missing primary delete",
        rollback,
        "        DeleteMapObject(object);\n",
        "",
        "canonical-initialization",
    )
    add_in(
        "prime rollback duplicate primary delete",
        rollback,
        "        DeleteMapObject(object);",
        "        DeleteMapObject(object);\n        DeleteMapObject(object);",
        "canonical-initialization",
    )
    add_in(
        "prime rollback deletes unrelated object",
        rollback,
        "        DeleteMapObject(object);",
        "        DeleteMapObject(otherObject);",
        "canonical-initialization",
    )
    add_in(
        "prime rollback conditional primary delete",
        rollback,
        "        DeleteMapObject(object);",
        "        if (cleanupReady) { DeleteMapObject(object); }",
        "canonical-initialization",
    )
    add_in(
        "prime rollback deletion after return",
        rollback,
        "        DeleteMapObject(object);\n        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame);\n        return FALSE;",
        "        return FALSE;\n        DeleteMapObject(object);\n        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame);",
        "canonical-initialization",
    )
    add_in(
        "prime rollback missing deletion accounting",
        rollback,
        "        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame);\n",
        "",
        "canonical-initialization",
    )
    add_in(
        "prime rollback wrong deletion counter",
        rollback,
        "OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame)",
        "OW_WILD_PERF_INC(sOverworldWildPerfMapObjectCreatesThisFrame)",
        "canonical-initialization",
    )
    add_in(
        "prime rollback duplicate deletion accounting",
        rollback,
        "        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame);",
        "        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame);\n        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame);",
        "canonical-initialization",
    )
    add_in(
        "prime rollback accounting before deletion",
        rollback,
        "        DeleteMapObject(object);\n        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame);",
        "        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame);\n        DeleteMapObject(object);",
        "canonical-initialization",
    )
    add_in(
        "prime success path deletes primary object",
        rollback,
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "    DeleteMapObject(object);\n    OverworldWildSpawns_StartSpawnStartup(object);",
        "canonical-initialization",
    )
    add_in(
        "prime success path deletion function alias",
        rollback,
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "    void (*deleteAlias)(void *) = DeleteMapObject;\n    deleteAlias(object);\n    OverworldWildSpawns_StartSpawnStartup(object);",
        "canonical-initialization",
    )
    helper_delete_source = replace_once(
        source,
        "static BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
        "static void DeletePrimaryLater(void *object) { DeleteMapObject(object); }\nstatic BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
    )
    helper_delete_source = replace_once_in_function(
        helper_delete_source,
        rollback,
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "    DeletePrimaryLater(object);\n    OverworldWildSpawns_StartSpawnStartup(object);",
    )
    cases.append(
        (
            "prime success path deletion helper",
            helper_delete_source,
            "canonical-initialization",
        )
    )
    pointer_helper_source = replace_once(
        source,
        "static BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
        "static void DeletePrimaryViaPointer(void **objectPtr) { DeleteMapObject(*objectPtr); }\nstatic BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
    )
    pointer_helper_source = replace_once_in_function(
        pointer_helper_source,
        rollback,
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "    DeletePrimaryViaPointer(&object);\n    OverworldWildSpawns_StartSpawnStartup(object);",
    )
    cases.append(
        (
            "prime success path pointer deletion helper",
            pointer_helper_source,
            "canonical-initialization",
        )
    )
    alias_helper_source = replace_once(
        source,
        "static BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
        "static void DeletePrimaryViaAlias(void *object) { void (*deleteAlias)(void *) = DeleteMapObject; deleteAlias(object); }\nstatic BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
    )
    alias_helper_source = replace_once_in_function(
        alias_helper_source,
        rollback,
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "    DeletePrimaryViaAlias(object);\n    OverworldWildSpawns_StartSpawnStartup(object);",
    )
    cases.append(
        (
            "prime success path aliased deletion helper",
            alias_helper_source,
            "canonical-initialization",
        )
    )
    renamed_alias_source = replace_once(
        source,
        "static BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
        "static void DeleteAliasedObject(void *victim) { DeleteMapObject(victim); }\nstatic BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
    )
    renamed_alias_source = replace_once_in_function(
        renamed_alias_source,
        rollback,
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "    void *objectAlias = object;\n    DeleteAliasedObject(objectAlias);\n    OverworldWildSpawns_StartSpawnStartup(object);",
    )
    cases.append(
        (
            "prime success path renamed object alias helper",
            renamed_alias_source,
            "canonical-initialization",
        )
    )
    callable_alias_source = replace_once(
        source,
        "static BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
        "static void DeleteVictim(void *victim) { DeleteMapObject(victim); }\nstatic BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
    )
    callable_alias_source = replace_once_in_function(
        callable_alias_source,
        rollback,
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "    void (*helperAlias)(void *) = DeleteVictim;\n    helperAlias(object);\n    OverworldWildSpawns_StartSpawnStartup(object);",
    )
    cases.append(
        (
            "prime success path delete-wrapper callable alias",
            callable_alias_source,
            "canonical-initialization",
        )
    )
    dereferenced_callable_source = replace_once(
        callable_alias_source,
        "    helperAlias(object);",
        "    (*helperAlias)(object);",
    )
    cases.append(
        (
            "prime success path dereferenced delete-wrapper alias",
            dereferenced_callable_source,
            "canonical-initialization",
        )
    )
    parenthesized_callable_source = replace_once(
        callable_alias_source,
        "= DeleteVictim;",
        "= (DeleteVictim);",
    )
    cases.append(
        (
            "prime success path parenthesized delete-wrapper alias",
            parenthesized_callable_source,
            "canonical-initialization",
        )
    )
    conditional_proxy_source = replace_once(
        source,
        "static BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
        "static void DeleteConditionallyReassigned(void *primaryObject) { void *candidate = primaryObject; if (useProxy) { candidate = GetSpawnProxy(); } DeleteMapObject(candidate); }\nstatic BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
    )
    conditional_proxy_source = replace_once_in_function(
        conditional_proxy_source,
        rollback,
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "    DeleteConditionallyReassigned(object);\n    OverworldWildSpawns_StartSpawnStartup(object);",
    )
    cases.append(
        (
            "prime conditional proxy reassignment retains primary taint",
            conditional_proxy_source,
            "canonical-initialization",
        )
    )
    conditional_callable_source = replace_once(
        source,
        "static BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
        "static void DeleteVictim(void *victim) { DeleteMapObject(victim); }\nstatic void KeepVictim(void *victim) { (void)victim; }\nstatic BOOL OverworldWildSpawns_SpawnPreparedEncounter(void) {",
    )
    conditional_callable_source = replace_once_in_function(
        conditional_callable_source,
        rollback,
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "    void (*helperAlias)(void *) = DeleteVictim;\n    if (keepObject) { helperAlias = KeepVictim; }\n    helperAlias(object);\n    OverworldWildSpawns_StartSpawnStartup(object);",
    )
    cases.append(
        (
            "prime conditional callable reassignment retains delete target",
            conditional_callable_source,
            "canonical-initialization",
        )
    )
    add_in(
        "prime ternary callable retains delete target",
        rollback,
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "    void (*ternaryAlias)(void *) = keepObject ? OverworldWildSpawns_DeleteVictim : OverworldWildSpawns_KeepVictim;\n    ternaryAlias(object);\n    OverworldWildSpawns_StartSpawnStartup(object);",
        "canonical-initialization",
    )
    add_in(
        "prime exhaustive callable branch retains one delete target",
        rollback,
        "    if (keepObject) {\n        conditionalSafe = OverworldWildSpawns_KeepVictim;\n    } else {\n        conditionalSafe = OverworldWildSpawns_KeepVictim;\n    }",
        "    if (keepObject) {\n        conditionalSafe = OverworldWildSpawns_KeepVictim;\n    } else {\n        conditionalSafe = OverworldWildSpawns_DeleteVictim;\n    }",
        "canonical-initialization",
    )
    add_in(
        "prime nested non-exhaustive callable branch retains delete target",
        rollback,
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "    void (*nestedUnsafe)(void *) = OverworldWildSpawns_DeleteVictim;\n"
        "    if (outer) {\n"
        "        if (inner) { nestedUnsafe = OverworldWildSpawns_KeepVictim; }\n"
        "        else { nestedUnsafe = OverworldWildSpawns_KeepVictim; }\n"
        "    }\n"
        "    nestedUnsafe(object);\n"
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "canonical-initialization",
    )
    add_in(
        "prime sibling branch reassignment does not hide delete target",
        rollback,
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "    void (*branchLocalUnsafe)(void *) = OverworldWildSpawns_DeleteVictim;\n"
        "    if (outer) {\n"
        "        branchLocalUnsafe = OverworldWildSpawns_KeepVictim;\n"
        "    } else {\n"
        "        branchLocalUnsafe(object);\n"
        "    }\n"
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "canonical-initialization",
    )
    add_in(
        "prime success path direct deletion accounting",
        rollback,
        "    OverworldWildSpawns_StartSpawnStartup(object);",
        "    sOverworldWildPerfMapObjectDeletesThisFrame++;\n    OverworldWildSpawns_StartSpawnStartup(object);",
        "canonical-initialization",
    )
    add_in(
        "prime rollback widened with OR",
        rollback,
        "            prepared->behaviorLimitKey, prepared->playerBallCatchValue)) {",
        "            prepared->behaviorLimitKey, prepared->playerBallCatchValue)\n        || cleanupRequested) {",
        "canonical-initialization",
    )
    add_in(
        "prime rollback widened with AND",
        rollback,
        "            prepared->behaviorLimitKey, prepared->playerBallCatchValue)) {",
        "            prepared->behaviorLimitKey, prepared->playerBallCatchValue)\n        && cleanupReady) {",
        "canonical-initialization",
    )
    add_in(
        "prime rollback returns success",
        rollback,
        "        return FALSE;",
        "        return TRUE;",
        "canonical-initialization",
    )
    add_in(
        "prime rollback conditional failure return",
        rollback,
        "        return FALSE;",
        "        if (cleanupReady) { return FALSE; }",
        "canonical-initialization",
    )
    add_in("effective cache comment-only", PROJECT_HELPER, "    status = OverworldWildRuntime_GetEffectiveCache(&runtime->behaviorStackRuntime,\n        slot, slotGeneration, &effective);", "    /* OverworldWildRuntime_GetEffectiveCache(); */\n    status = FakeGetEffective(&runtime->behaviorStackRuntime,\n        slot, slotGeneration, &effective);", "effective-projection")
    add_in(
        "effective cache ignored status",
        PROJECT_HELPER,
        "    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    if (!OverworldWildSpawns_ConvertRuntimeEffectiveCacheToLegacyBehavior(",
        "    if (!OverworldWildSpawns_ConvertRuntimeEffectiveCacheToLegacyBehavior(",
        "effective-projection",
    )
    add_in("projection cache status overwritten", PROJECT_HELPER, "        slot, slotGeneration, &effective);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", "        slot, slotGeneration, &effective);\n    status = OW_WILD_RUNTIME_STATUS_OK;\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", "effective-projection")
    add_in(
        "projection pre-call status pointer overwrite",
        PROJECT_HELPER,
        "    status = OverworldWildRuntime_GetEffectiveCache(&runtime->behaviorStackRuntime,\n        slot, slotGeneration, &effective);",
        "    OverworldWildRuntimeStatus *statusAlias = &status;\n    status = OverworldWildRuntime_GetEffectiveCache(&runtime->behaviorStackRuntime,\n        slot, slotGeneration, &effective);\n    *statusAlias = OW_WILD_RUNTIME_STATUS_OK;",
        "effective-projection",
    )
    add_in(
        "projection spot-state output alias",
        PROJECT_HELPER,
        "            &effective, profileOut, primitivesOut, &spotState, &capabilityMask)) { return FALSE; }",
        "            &effective, profileOut, primitivesOut, &spotState, &capabilityMask)) { return FALSE; }\n    u8 *spotAlias = &spotState;\n    *spotAlias = OW_WILD_SPAWNER_SPOT_STATE_ACTIVE;",
        "effective-projection",
    )
    add_in(
        "projection live-state pointer alias write",
        PROJECT_HELPER,
        "    state->movementSpotStates[slot] = spotState;",
        "    u8 *liveStateAlias = &state->movementSpotStates[slot];\n    *liveStateAlias = spotState;\n    state->movementSpotStates[slot] = spotState;",
        "effective-projection",
    )
    add_in(
        "projection capability pointer alias write",
        PROJECT_HELPER,
        "    runtime->movementFrameDrivenActiveMask = capabilityMask;",
        "    u32 *capabilityAlias = &runtime->movementFrameDrivenActiveMask;\n    *capabilityAlias = capabilityMask;\n    runtime->movementFrameDrivenActiveMask = capabilityMask;",
        "effective-projection",
    )
    converter = "OverworldWildSpawns_ConvertRuntimeEffectiveCacheToLegacyBehavior"
    add_in(
        "conversion profile output pointer alias write",
        converter,
        "    profileOut->alertState = effective->controllerValues[0];",
        "    OverworldWildBehaviorProfile *profileAlias = profileOut;\n    profileAlias->alertState = 0;\n    profileOut->alertState = effective->controllerValues[0];",
        "effective-projection",
    )
    add_in(
        "conversion profile element address alias write",
        converter,
        "    profileOut->alertState = effective->controllerValues[0];",
        "    OverworldWildBehaviorProfile *profileAlias = &profileOut[0];\n    profileAlias->alertState = 0;\n    profileOut->alertState = effective->controllerValues[0];",
        "effective-projection",
    )
    add_in(
        "conversion profile dereference address alias write",
        converter,
        "    profileOut->alertState = effective->controllerValues[0];",
        "    OverworldWildBehaviorProfile *profileAlias = &(*profileOut);\n    profileAlias->alertState = 0;\n    profileOut->alertState = effective->controllerValues[0];",
        "effective-projection",
    )
    add_in(
        "conversion primitive output pointer alias write",
        converter,
        "    *primitivesOut = OverworldWildSpawns_ResolveBehaviorPrimitives(profileOut);",
        "    OverworldWildBehaviorPrimitives *primitivesAlias = primitivesOut;\n    primitivesAlias->chillLocomotion = 0;\n    *primitivesOut = OverworldWildSpawns_ResolveBehaviorPrimitives(profileOut);",
        "effective-projection",
    )
    add_in(
        "conversion spot output pointer alias write",
        converter,
        "    profileOut->playerAdjacentDirectionMasks = effective->stateValues[27];\n    switch (effective->semanticRole) {",
        "    profileOut->playerAdjacentDirectionMasks = effective->stateValues[27];\n    u8 *spotAlias = spotStateOut;\n    *spotAlias = 0;\n    switch (effective->semanticRole) {",
        "effective-projection",
    )
    add_in(
        "conversion capability output pointer alias write",
        converter,
        "    *capabilityMaskOut = effective->capabilityMask;",
        "    u32 *capabilityAlias = capabilityMaskOut;\n    *capabilityAlias = 0;\n    *capabilityMaskOut = effective->capabilityMask;",
        "effective-projection",
    )
    add_in("projection missing controller mapping", converter, "    profileOut->stamina = effective->controllerValues[6];", "    localProfile.stamina = effective->controllerValues[6];", "effective-projection")
    add_in("projection wrong shared mapping", converter, "    profileOut->range = effective->stateValues[4];", "    profileOut->range = effective->stateValues[5];", "effective-projection")
    add_in("projection wrong calm mapping", converter, "        profileOut->chillState = effective->stateValues[0];", "        profileOut->activeState = effective->stateValues[0];", "effective-projection")
    add_in("projection wrong attentive mapping", converter, "        profileOut->attentiveState = effective->stateValues[0];", "        profileOut->chillState = effective->stateValues[0];", "effective-projection")
    add_in(
        "projection wrong tired mapping",
        converter,
        "    case OWBD_ROLE_TIRED:\n        profileOut->tiredState = effective->stateValues[0];",
        "    case OWBD_ROLE_TIRED:\n        profileOut->chillState = effective->stateValues[0];",
        "effective-projection",
    )
    add_in(
        "projection wrong asleep live state",
        converter,
        "        profileOut->tiredRamMaxSpeed = effective->stateValues[17];\n        *spotStateOut = OW_WILD_SPAWNER_SPOT_STATE_TIRED;\n        break;\n    default:",
        "        profileOut->tiredRamMaxSpeed = effective->stateValues[17];\n        *spotStateOut = OW_WILD_SPAWNER_SPOT_STATE_ACTIVE;\n        break;\n    default:",
        "effective-projection",
    )
    for label, old, new in (
        ("projection wrong calm primitive", "primitivesOut->chillLocomotion = effective->primitives[0];", "primitivesOut->chillLocomotion = effective->primitives[1];"),
        ("projection wrong attentive primitive", "primitivesOut->attentiveTarget = effective->primitives[1];", "primitivesOut->attentiveTarget = effective->primitives[0];"),
        ("projection wrong tired primitive", "    case OWBD_ROLE_TIRED:\n        primitivesOut->tiredLocomotion = effective->primitives[0];", "    case OWBD_ROLE_TIRED:\n        primitivesOut->tiredLocomotion = effective->primitives[1];"),
        ("projection wrong asleep primitive", "    case OWBD_ROLE_ASLEEP:\n        primitivesOut->tiredLocomotion = effective->primitives[0];", "    case OWBD_ROLE_ASLEEP:\n        primitivesOut->tiredLocomotion = effective->primitives[1];"),
    ):
        add_in(label, converter, old, new, "effective-projection")
    add_in("projection missing primitive resolver", converter, "    *primitivesOut = OverworldWildSpawns_ResolveBehaviorPrimitives(profileOut);", "    *primitivesOut = unrelatedPrimitives;", "effective-projection")
    add_in("projection bad primitive semantic validation", converter, "effective->primitives[4] != effective->stateValues[4]", "effective->primitives[4] == effective->stateValues[4]", "effective-projection")
    add_in("projection missing capability output", converter, "    *capabilityMaskOut = effective->capabilityMask;", "    localCapabilityMask = effective->capabilityMask;", "effective-projection")
    for label, old, new in (
        ("projection late controller overwrite", "    profileOut->stamina = effective->controllerValues[6];", "    profileOut->stamina = effective->controllerValues[6];\n    profileOut->stamina = 0;"),
        ("projection late shared overwrite", "    profileOut->range = effective->stateValues[4];", "    profileOut->range = effective->stateValues[4];\n    (*profileOut).range = 0;"),
        ("projection late calm overwrite", "        profileOut->chillState = effective->stateValues[0];", "        profileOut->chillState = effective->stateValues[0];\n        profileOut->chillState = 0;"),
        ("projection late attentive overwrite", "        profileOut->attentiveState = effective->stateValues[0];", "        profileOut->attentiveState = effective->stateValues[0];\n        profileOut[0].attentiveState = 0;"),
        ("projection late tired overwrite", "    case OWBD_ROLE_TIRED:\n        profileOut->tiredState = effective->stateValues[0];", "    case OWBD_ROLE_TIRED:\n        profileOut->tiredState = effective->stateValues[0];\n        profileOut->tiredState = 0;"),
        ("projection late asleep overwrite", "    case OWBD_ROLE_ASLEEP:\n        profileOut->tiredState = effective->stateValues[0];", "    case OWBD_ROLE_ASLEEP:\n        profileOut->tiredState = effective->stateValues[0];\n        profileOut->tiredState = 0;"),
        ("projection late calm primitive overwrite", "        primitivesOut->chillLocomotion = effective->primitives[0];", "        primitivesOut->chillLocomotion = effective->primitives[0];\n        primitivesOut[0].chillLocomotion = 0;"),
        ("projection late attentive primitive overwrite", "        primitivesOut->attentiveLocomotion = effective->primitives[0];", "        primitivesOut->attentiveLocomotion = effective->primitives[0];\n        primitivesOut->attentiveLocomotion = 0;"),
        ("projection late tired primitive overwrite", "    case OWBD_ROLE_TIRED:\n        primitivesOut->tiredLocomotion = effective->primitives[0];", "    case OWBD_ROLE_TIRED:\n        primitivesOut->tiredLocomotion = effective->primitives[0];\n        primitivesOut->tiredLocomotion = 0;"),
        ("projection late asleep primitive overwrite", "    case OWBD_ROLE_ASLEEP:\n        primitivesOut->tiredLocomotion = effective->primitives[0];", "    case OWBD_ROLE_ASLEEP:\n        primitivesOut->tiredLocomotion = effective->primitives[0];\n        primitivesOut->tiredLocomotion = 0;"),
        ("projection whole primitive overwritten", "    *primitivesOut = OverworldWildSpawns_ResolveBehaviorPrimitives(profileOut);", "    *primitivesOut = OverworldWildSpawns_ResolveBehaviorPrimitives(profileOut);\n    *primitivesOut = zeroPrimitives;"),
        ("projection capability zeroed late", "    *capabilityMaskOut = effective->capabilityMask;", "    *capabilityMaskOut = effective->capabilityMask;\n    capabilityMaskOut[0] = 0;"),
        ("projection spot state zeroed late", "    *capabilityMaskOut = effective->capabilityMask;", "    *capabilityMaskOut = effective->capabilityMask;\n    *spotStateOut = 0;"),
    ):
        add_in(label, converter, old, new, "effective-projection")
    add_in("projection inert live state", PROJECT_HELPER, "    state->movementSpotStates[slot] = spotState;", "    projectedState = spotState;", "effective-projection")
    add_in("projection inert live capability", PROJECT_HELPER, "    runtime->movementFrameDrivenActiveMask = capabilityMask;", "    localMask = capabilityMask;", "effective-projection")
    add_in("projection live state zeroed late", PROJECT_HELPER, "    state->movementSpotStates[slot] = spotState;", "    state->movementSpotStates[slot] = spotState;\n    state->movementSpotStates[slot] = 0;", "effective-projection")
    add_in("projection live capability zeroed late", PROJECT_HELPER, "    runtime->movementFrameDrivenActiveMask = capabilityMask;", "    runtime->movementFrameDrivenActiveMask = capabilityMask;\n    runtime->movementFrameDrivenActiveMask = 0;", "effective-projection")
    add_in("projection other runtime", PROJECT_HELPER, "&runtime->behaviorStackRuntime,\n        slot, slotGeneration, &effective", "&otherRuntime->behaviorStackRuntime,\n        slot, slotGeneration, &effective", "effective-projection")
    add_in("projection other slot", PROJECT_HELPER, "slot, slotGeneration, &effective", "otherSlot, slotGeneration, &effective", "effective-projection")
    add("dynamic projection cached", "    return TRUE;\n}\nstatic void OverworldWildSpawns_HandleFinishedMovementCommand", "    OverworldWildSpawns_StoreBehaviorSlotCache();\n    return TRUE;\n}\nstatic void OverworldWildSpawns_HandleFinishedMovementCommand", "effective-projection")
    add("completion return before consume", "    runtime = OW_WILD_RUNTIME(state);\n    if (!OverworldWildSpawns_ConsumeMovementCommandOrigin", "    runtime = OW_WILD_RUNTIME(state);\n    if (reservation) { return; }\n    if (!OverworldWildSpawns_ConsumeMovementCommandOrigin", "stamina-route")
    add("stamina outside consume", "    if (!OverworldWildSpawns_ConsumeMovementCommandOrigin(state, slot, &origin)) { return; }", "    if (!OverworldWildSpawns_ConsumeMovementCommandOrigin(state, slot, &origin)) { Log(); }", "stamina-route")
    add("stamina disabled consume guard", "    if (!OverworldWildSpawns_ConsumeMovementCommandOrigin(state, slot, &origin)) { return; }", "    if (!OverworldWildSpawns_ConsumeMovementCommandOrigin(state, slot, &origin) && 0) { return; }", "stamina-route")
    stamina = "OverworldWildSpawns_HandleFinishedMovementCommand"
    add_in("stamina effective status checks unrelated value", stamina, "    if (status != OW_WILD_RUNTIME_STATUS_OK) { return; }\n    if (state->movementSpotStates", "    if (otherStatus != OW_WILD_RUNTIME_STATUS_OK) { return; }\n    if (state->movementSpotStates", "stamina-route")
    add_in("stamina effective status overwritten", stamina, "        slot, slotGeneration, &effective);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return; }", "        slot, slotGeneration, &effective);\n    status = OW_WILD_RUNTIME_STATUS_OK;\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return; }", "stamina-route")
    add_in(
        "stamina active-step pointer alias write",
        stamina,
        "    state->movementActiveSteps[slot]++;",
        "    u8 *stepAlias = &state->movementActiveSteps[slot];\n    *stepAlias = 0;\n    state->movementActiveSteps[slot]++;",
        "stamina-route",
    )
    add_in(
        "stamina active-step array decay alias",
        stamina,
        "    state->movementActiveSteps[slot]++;",
        "    u8 *stepAlias = state->movementActiveSteps;\n    stepAlias[slot] = 0;\n    state->movementActiveSteps[slot]++;",
        "stamina-route",
    )
    add_in("stamina charges inactive movement", stamina, "state->movementSpotStates[slot] != OW_WILD_SPAWNER_SPOT_STATE_ACTIVE", "state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_ACTIVE", "stamina-route")
    add_in("stamina charges RAM movement", stamina, "if (OverworldWildSpawns_CurrentSpotUsesRamLocomotion(", "if (!OverworldWildSpawns_CurrentSpotUsesRamLocomotion(", "stamina-route")
    add_in("stamina omits object identity", stamina, "    if (origin.objectGeneration != runtime->movementObjectGenerations[slot]\n        || origin.staminaPolicyId", "    if (origin.staminaPolicyId", "stamina-route")
    add_in("stamina uses authored policy", stamina, "effective.controllerValues[6] == 0", "profile.stamina == 0", "stamina-route")
    add_in("stamina missing charge", stamina, "    state->movementActiveSteps[slot]++;", "    RecordStepWithoutCharging();", "stamina-route")
    add_in("stamina double charge", stamina, "    state->movementActiveSteps[slot]++;", "    state->movementActiveSteps[slot]++;\n    state->movementActiveSteps[slot]++;", "stamina-route")
    add_in("stamina compound charge", stamina, "    state->movementActiveSteps[slot]++;", "    state->movementActiveSteps[slot] += 1;", "stamina-route")
    add_in("stamina late reset", stamina, "    if (state->movementActiveSteps[slot] < effective.controllerValues[6]) { return; }", "    if (state->movementActiveSteps[slot] < effective.controllerValues[6]) { return; }\n    state->movementActiveSteps[slot] = 0;", "stamina-route")
    add_in("stamina wrong exhaustion threshold", stamina, "state->movementActiveSteps[slot] < effective.controllerValues[6]", "state->movementActiveSteps[slot] < profile.stamina", "stamina-route")
    add_in("stamina recovery before exhaustion", stamina, "    if (state->movementActiveSteps[slot] < effective.controllerValues[6]) { return; }", "    if (state->movementActiveSteps[slot] < effective.controllerValues[6]) { Log(); }", "stamina-route")
    add_in("stamina direct tired fallback", stamina, "    if (state->movementActiveSteps[slot] < effective.controllerValues[6]) { return; }", "    if (state->movementActiveSteps[slot] < effective.controllerValues[6]) { return; }\n    OverworldWildSpawns_StartTiredEmote();", "stamina-route")
    add_in("stamina duplicate apply", stamina, "    if (!OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(\n            state, slot, OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA, &origin)) { return; }", "    OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(\n            state, slot, OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA, &origin);\n    if (!OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(\n            state, slot, OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA, &origin)) { return; }", "stamina-route")
    staged = "OverworldWildSpawns_FinishPendingStagedHop"
    add_in("staged finish missing preload", staged, "        state->movementActiveSteps[slot] = effective.controllerValues[6] - 1;", "        RecordStagedFinish();", "stamina-route")
    add_in("staged finish wrong preload", staged, "effective.controllerValues[6] - 1", "effective.controllerValues[6] - 2", "stamina-route")
    add_in("staged finish later overwrite", staged, "        state->movementActiveSteps[slot] = effective.controllerValues[6] - 1;", "        state->movementActiveSteps[slot] = effective.controllerValues[6] - 1;\n        state->movementActiveSteps[slot] = 0;", "stamina-route")
    add_in(
        "staged active-step pointer alias write",
        staged,
        "        state->movementActiveSteps[slot] = effective.controllerValues[6] - 1;",
        "        u8 *stepAlias = &state->movementActiveSteps[slot];\n        *stepAlias = 0;\n        state->movementActiveSteps[slot] = effective.controllerValues[6] - 1;",
        "stamina-route",
    )
    add_in("staged finish duplicate completion", staged, "    OverworldWildSpawns_HandleFinishedMovementCommand(state, slot);", "    OverworldWildSpawns_HandleFinishedMovementCommand(state, slot);\n    OverworldWildSpawns_HandleFinishedMovementCommand(state, slot);", "stamina-route")
    add("stamina tired fallback", "    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    status = OverworldWildRuntime_Apply();", "    if (status != OW_WILD_RUNTIME_STATUS_OK) { OverworldWildSpawns_StartTiredEmote(); return FALSE; }\n    status = OverworldWildRuntime_Apply();", "postcommit-presentation")
    add("throw failure candidate", "    } else {\n        OverworldWildSpawns_ReleaseThrowTargetAtCurrentTile();", "    } else {\n        OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA);\n        OverworldWildSpawns_ReleaseThrowTargetAtCurrentTile();", "throw-route")
    add("throw target candidate", "static void OverworldWildSpawns_TryStartFrameDrivenActiveMovementCommand(void) {", "static void OverworldWildSpawns_TryStartFrameDrivenActiveMovementCommand(void) {\n    if (target) { OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA); }", "throw-route")
    add("throw direct tired", "        OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(\n            state, slot, OW_WILD_RUNTIME_RECOVERY_ORIGIN_THROW_RECOVERY);", "        OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(\n            state, slot, OW_WILD_RUNTIME_RECOVERY_ORIGIN_THROW_RECOVERY);\n        OverworldWildSpawns_StartTiredEmote();", "throw-route")
    add("throw recovery targets passenger", "            state, slot, OW_WILD_RUNTIME_RECOVERY_ORIGIN_THROW_RECOVERY);", "            state, targetSlot, OW_WILD_RUNTIME_RECOVERY_ORIGIN_THROW_RECOVERY);", "throw-route")
    add_in("RAM nonactive recovery", "OverworldWildSpawns_EndRamCrash", "state->movementSpotStates[slot] != OW_WILD_SPAWNER_SPOT_STATE_ACTIVE", "state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_ACTIVE", "ram-route")
    add_in("RAM disabled active guard", "OverworldWildSpawns_EndRamCrash", "state->movementSpotStates[slot] != OW_WILD_SPAWNER_SPOT_STATE_ACTIVE", "state->movementSpotStates[slot] != OW_WILD_SPAWNER_SPOT_STATE_ACTIVE && 0", "ram-route")
    add_in("RAM battle success falls through", "OverworldWildSpawns_EndRamCrash", "                state->movementRamDirections[slot], profile)) { return; }", "                state->movementRamDirections[slot], profile)) { Log(); }", "ram-route")
    add_in("RAM impact compound condition", "OverworldWildSpawns_EndRamCrash", "                state->movementRamDirections[slot], profile)) { return; }", "                state->movementRamDirections[slot], profile) && onlySometimes) { return; }", "ram-route")
    add_in("RAM impact wrong object", "OverworldWildSpawns_EndRamCrash", "state, state->movementFieldSystem, slot, object,", "state, state->movementFieldSystem, slot, otherObject,", "ram-route")
    ram_impact_call = "OverworldWildSpawns_TryStartRamCrashBattleImpact(\n                state, state->movementFieldSystem, slot, object,\n                state->movementRamDirections[slot], profile)"
    add_in("RAM duplicate impact call", "OverworldWildSpawns_EndRamCrash", f"        if ({ram_impact_call}) {{ return; }}", f"        if ({ram_impact_call}) {{ return; }}\n        {ram_impact_call};", "ram-route")
    add_in("RAM hidden duplicate impact call", "OverworldWildSpawns_EndRamCrash", f"        if ({ram_impact_call}) {{ return; }}", f"        if ({ram_impact_call}) {{ return; }}\n        if (0) {{ {ram_impact_call}; }}", "ram-route")
    add_in("RAM preprocessor-hidden duplicate impact call", "OverworldWildSpawns_EndRamCrash", f"        if ({ram_impact_call}) {{ return; }}", f"        if ({ram_impact_call}) {{ return; }}\n#if 0\n        {ram_impact_call};\n#endif", "ram-route")
    add_in("RAM duplicate wrong impact call", "OverworldWildSpawns_EndRamCrash", f"        if ({ram_impact_call}) {{ return; }}", f"        if ({ram_impact_call}) {{ return; }}\n        OverworldWildSpawns_TryStartRamCrashBattleImpact(state, fieldSystem, slot, wrongObject, direction, profile);", "ram-route")
    add_in(
        "RAM function-pointer impact alias",
        "OverworldWildSpawns_EndRamCrash",
        f"        if ({ram_impact_call}) {{ return; }}",
        "        BOOL (*impactAlias)(void) = OverworldWildSpawns_TryStartRamCrashBattleImpact;\n        impactAlias();\n"
        f"        if ({ram_impact_call}) {{ return; }}",
        "ram-route",
    )
    add("RAM impact direct recovery", "static void OverworldWildSpawns_TryStartRamCrashBattleImpact(void) { StartBattle(); }", "static void OverworldWildSpawns_TryStartRamCrashBattleImpact(void) { OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(); StartBattle(); }", "ram-route")
    add("RAM impact indirect recovery", "static void OverworldWildSpawns_TryStartRamCrashBattleImpact(void) { StartBattle(); }", "static void RamImpactHelper(void) { OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(); }\nstatic void OverworldWildSpawns_TryStartRamCrashBattleImpact(void) { RamImpactHelper(); StartBattle(); }", "ram-route")
    add("FLED wrong disposition", "disposition == OW_WILD_BATTLE_DISPOSITION_FLED", "disposition == OW_WILD_BATTLE_DISPOSITION_RETAIN", "fled-route")
    add("FLED disabled disposition", "disposition == OW_WILD_BATTLE_DISPOSITION_FLED", "disposition == OW_WILD_BATTLE_DISPOSITION_FLED && 0", "fled-route")
    add_in("FLED missing retained validation", "OverworldWildSpawns_OverlayCleanupPendingBattle", "        && OverworldWildSpawns_IsCurrentSpawnObject(\n            fieldSystem, &state->spawns[state->pendingSlot])", "        && TRUE", "fled-route")
    add("duplicate frame tick", "    OverworldWildSpawns_TickRuntimeFrameTimers();\n    if (presentationRestorePending)", "    OverworldWildSpawns_TickRuntimeFrameTimers();\n    OverworldWildSpawns_TickRuntimeFrameTimers();\n    if (presentationRestorePending)", "frame-timers")
    add("early return before frame tick", "    OverworldWildSpawns_TickRuntimeFrameTimers();", "    if (deferredWork) { return; }\n    OverworldWildSpawns_TickRuntimeFrameTimers();", "frame-timers")
    add_in("pending before all-slot tick", "OverworldWildSpawns_TickRuntimeFrameTimers", "    status = OverworldWildRuntime_TickFrameTimers(&runtime->behaviorStackRuntime,\n        presentationGateMask, tickResults);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return; }\n    OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries();", "    OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries();\n    status = OverworldWildRuntime_TickFrameTimers(&runtime->behaviorStackRuntime,\n        presentationGateMask, tickResults);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return; }", "frame-timers")
    add("tick failure ignored", "    if (status != OW_WILD_RUNTIME_STATUS_OK) { return; }\n    OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries();", "    OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries();", "frame-timers")
    add_in("all-slot tick comment-only", "OverworldWildSpawns_TickRuntimeFrameTimers", "    status = OverworldWildRuntime_TickFrameTimers(&runtime->behaviorStackRuntime,", "    /* OverworldWildRuntime_TickFrameTimers(); */\n    status = FakeTickFrameTimers(&runtime->behaviorStackRuntime,", "frame-timers")
    add_in("all-slot tick status overwritten", "OverworldWildSpawns_TickRuntimeFrameTimers", "        presentationGateMask, tickResults);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return; }", "        presentationGateMask, tickResults);\n    status = OW_WILD_RUNTIME_STATUS_OK;\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return; }", "frame-timers")
    add_in("pending query comment-only", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "            status = OverworldWildRuntime_GetPendingTimerExpiryByIndex(\n                &runtime->behaviorStackRuntime, slot, slotGeneration,\n                pendingIndex, &expiry);", "            /* OverworldWildRuntime_GetPendingTimerExpiryByIndex(); */\n            status = FakePendingQuery(\n                &runtime->behaviorStackRuntime, slot, slotGeneration,\n                pendingIndex, &expiry);", "frame-timers")
    add("pending unbounded", "        for (pendingIndex = 0;\n             pendingIndex < pendingCount && pendingIndex < OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT;\n             pendingIndex++) {", "        while (pendingIndex < pendingCount) {", "frame-timers")
    add_in("pending duplicate recovery", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "            status = OverworldWildRuntime_RecoverExpiredTimer(\n                &runtime->behaviorStackRuntime, &expiry, &recovery);", "            status = OverworldWildRuntime_RecoverExpiredTimer(\n                &runtime->behaviorStackRuntime, &expiry, &recovery);\n            status = OverworldWildRuntime_RecoverExpiredTimer(\n                &runtime->behaviorStackRuntime, &expiry, &recovery);", "frame-timers")
    add_in("pending projection on recovery failure", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "            if (status != OW_WILD_RUNTIME_STATUS_OK) { continue; }\n            OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(state, slot, &recovery);", "            if (status == OW_WILD_RUNTIME_STATUS_OK) { continue; }\n            OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(state, slot, &recovery);", "frame-timers")
    add_in("pending disabled recovery guard", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "            if (status != OW_WILD_RUNTIME_STATUS_OK) { continue; }\n            OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(state, slot, &recovery);", "            if (status != OW_WILD_RUNTIME_STATUS_OK && 0) { continue; }\n            OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(state, slot, &recovery);", "frame-timers")
    add_in("pending query failure ignored", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "            if (status != OW_WILD_RUNTIME_STATUS_OK) { continue; }\n            status = OverworldWildRuntime_RecoverExpiredTimer(", "            status = OverworldWildRuntime_RecoverExpiredTimer(", "frame-timers")
    add_in("pending projection outside loop", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "            OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(state, slot, &recovery);\n            OverworldWildSpawns_PresentRuntimeTiredState();\n        }\n    }\n    OverworldWildSpawns_EnsureFrameMovementTask();", "        }\n    }\n    OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(state, slot, &recovery);\n    OverworldWildSpawns_PresentRuntimeTiredState();\n    OverworldWildSpawns_EnsureFrameMovementTask();", "frame-timers")
    add("legacy timer guard inverted", "    if (OverworldWildSpawns_HasRuntimeTimerWork()) { return; }", "    if (!OverworldWildSpawns_HasRuntimeTimerWork()) { return; }", "legacy-timer-ownership")
    add("legacy timer guard disabled", "    if (OverworldWildSpawns_HasRuntimeTimerWork()) { return; }", "    if (OverworldWildSpawns_HasRuntimeTimerWork() && 0) { return; }", "legacy-timer-ownership")
    add("legacy timer guard comment-only", "    if (OverworldWildSpawns_HasRuntimeTimerWork()) { return; }", "    /* if (OverworldWildSpawns_HasRuntimeTimerWork()) { return; } */", "legacy-timer-ownership")
    add_in("liveness timer comment-only", "OverworldWildSpawns_HasRuntimeTimerWork", "    return OverworldWildRuntime_GetTimerCount(", "    /* OverworldWildRuntime_GetTimerCount(); */\n    return FakeTimerCount(", "timer-task-liveness")
    add_in("liveness constant false", "OverworldWildSpawns_HasRuntimeTimerWork", "    return OverworldWildRuntime_GetTimerCount(", "    return 0 && OverworldWildRuntime_GetTimerCount(", "timer-task-liveness")
    add_in("frame work liveness removed", "OverworldWildSpawns_GetFrameMovementWorkForSlot", "    if (OverworldWildSpawns_HasRuntimeTimerWork(state, slot)) {\n        frameWorkMask |= OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);\n    }", "    (void)OverworldWildSpawns_HasRuntimeTimerWork(state, slot);", "timer-task-liveness")
    add("pending keep-live removed", "    OverworldWildSpawns_EnsureFrameMovementTask();\n}\nstatic void OverworldWildSpawns_TickTiredEmote", "}\nstatic void OverworldWildSpawns_TickTiredEmote", "timer-task-liveness")
    add("recovery resolve no-op", "    status = OverworldWildRuntime_ResolveRecoveryCandidate(&context, origin, &candidate);", "    status = OW_WILD_RUNTIME_STATUS_OK;", "postcommit-presentation")
    add("apply no projection", "    OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(state, slot, &applyResult);\n    OverworldWildSpawns_PresentRuntimeTiredState();", "    OverworldWildSpawns_PresentRuntimeTiredState();", "postcommit-presentation")
    add("projection before apply status", "    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(state, slot, &applyResult);", "    OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(state, slot, &applyResult);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", "postcommit-presentation")

    capture_stage = "    status = OverworldWildRuntime_CaptureCommandOrigin(&runtime->behaviorStackRuntime,\n        &runtime->movementCommandOrigins, slot, slotGeneration, &identity);"
    cases.append(("capture disabled call", disable_once_in_function(source, CAPTURE_HELPER, capture_stage), "capture-wrapper"))
    cases.append(("capture preprocessor-disabled call", preprocess_disable_once_in_function(source, CAPTURE_HELPER, capture_stage), "capture-wrapper"))
    for field in (
        "commandGeneration", "commandSerial", "objectGeneration",
        "staminaPolicyGeneration", "staminaPolicyId",
    ):
        add_in(
            f"capture identity {field} rewritten",
            CAPTURE_HELPER,
            capture_stage,
            f"    identity.{field} = 0;\n" + capture_stage,
            "capture-wrapper",
        )
    add_in("capture identity zeroed after construction", CAPTURE_HELPER, capture_stage, "    memset(&identity, 0, sizeof(identity));\n" + capture_stage, "capture-wrapper")
    add_in("capture identity address escapes before Stage A", CAPTURE_HELPER, capture_stage, "    MutateIdentity(&identity);\n" + capture_stage, "capture-wrapper")
    add_in("capture disabled failure exit", CAPTURE_HELPER, "    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    runtime->movementCommandGenerations[slot] = nextCommandGeneration;", "    if (status != OW_WILD_RUNTIME_STATUS_OK) { if (0) { return FALSE; } }\n    runtime->movementCommandGenerations[slot] = nextCommandGeneration;", "capture-wrapper")
    consume_stage = "    status = OverworldWildRuntime_ConsumeCommandOrigin(&runtime->behaviorStackRuntime,\n        &runtime->movementCommandOrigins, slot, slotGeneration, &identity, originOut);"
    cases.append(("consume disabled call", disable_once_in_function(source, CONSUME_HELPER, consume_stage), "consume-wrapper"))
    for field in (
        "commandGeneration", "commandSerial", "objectGeneration",
        "staminaPolicyGeneration", "staminaPolicyId",
    ):
        add_in(
            f"consume identity {field} rewritten",
            CONSUME_HELPER,
            consume_stage,
            f"    identity.{field} = 0;\n" + consume_stage,
            "consume-wrapper",
        )
    add_in("consume identity zeroed after construction", CONSUME_HELPER, consume_stage, "    memset(&identity, 0, sizeof(identity));\n" + consume_stage, "consume-wrapper")
    add_in("consume identity address escapes before Stage A", CONSUME_HELPER, consume_stage, "    MutateIdentity(&identity);\n" + consume_stage, "consume-wrapper")
    add_in("consume conditional failure exit", CONSUME_HELPER, "    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    return TRUE;", "    if (status != OW_WILD_RUNTIME_STATUS_OK) { if (cleanupReady) { return FALSE; } }\n    return TRUE;", "consume-wrapper")
    prime_stage = "    status = OverworldWildRuntime_PrimeCanonicalEffectiveCache(&runtime->behaviorStackRuntime,\n        slot, slotGeneration, &staticContext, &resolved);"
    cases.append(("prime disabled call", disable_once_in_function(source, "OverworldWildSpawns_InitSpawnSlotState", prime_stage), "canonical-initialization"))
    add_in("prime disabled rollback", "OverworldWildSpawns_InitSpawnSlotState", "        OverworldWildSpawns_ResetSlotState();\n        return;", "        if (0) { OverworldWildSpawns_ResetSlotState(); }\n        return;", "canonical-initialization")
    add_in("prime conditional rollback", "OverworldWildSpawns_InitSpawnSlotState", "        OverworldWildSpawns_ResetSlotState();\n        return;", "        if (cleanupReady) { OverworldWildSpawns_ResetSlotState(); }\n        return;", "canonical-initialization")
    add_in("prime rollback after exposure return", "OverworldWildSpawns_InitSpawnSlotState", "        OverworldWildSpawns_ResetSlotState();\n        return;", "        return;\n        OverworldWildSpawns_ResetSlotState();", "canonical-initialization")
    project_stage = "    status = OverworldWildRuntime_GetEffectiveCache(&runtime->behaviorStackRuntime,\n        slot, slotGeneration, &effective);"
    cases.append(("projection disabled cache read", disable_once_in_function(source, PROJECT_HELPER, project_stage), "effective-projection"))
    add_in("projection disabled failure exit", PROJECT_HELPER, "    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    if (!OverworldWildSpawns_ConvertRuntimeEffectiveCacheToLegacyBehavior(", "    if (status != OW_WILD_RUNTIME_STATUS_OK) { if (0) { return FALSE; } }\n    if (!OverworldWildSpawns_ConvertRuntimeEffectiveCacheToLegacyBehavior(", "effective-projection")
    tick_call = "    OverworldWildSpawns_TickRuntimeFrameTimers();"
    cases.append(("frame disabled semantic tick", disable_once_in_function(source, "OverworldWildSpawns_FrameMovementTask", tick_call), "frame-timers"))
    pending_query = "            status = OverworldWildRuntime_GetPendingTimerExpiryByIndex(\n                &runtime->behaviorStackRuntime, slot, slotGeneration,\n                pendingIndex, &expiry);"
    cases.append(("pending disabled query", disable_once_in_function(source, "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", pending_query), "frame-timers"))
    add_in("pending query status overwritten", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", pending_query + "\n            if (status != OW_WILD_RUNTIME_STATUS_OK) { continue; }", pending_query + "\n            status = OW_WILD_RUNTIME_STATUS_OK;\n            if (status != OW_WILD_RUNTIME_STATUS_OK) { continue; }", "frame-timers")
    pending_recover = "            status = OverworldWildRuntime_RecoverExpiredTimer(\n                &runtime->behaviorStackRuntime, &expiry, &recovery);"
    cases.append(("pending disabled recovery", disable_once_in_function(source, "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", pending_recover), "frame-timers"))
    add_in("pending recovery status overwritten", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", pending_recover + "\n            if (status != OW_WILD_RUNTIME_STATUS_OK) { continue; }", pending_recover + "\n            status = OW_WILD_RUNTIME_STATUS_OK;\n            if (status != OW_WILD_RUNTIME_STATUS_OK) { continue; }", "frame-timers")
    add_in("pending recovery guard checks unrelated status", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "&runtime->behaviorStackRuntime, &expiry, &recovery);\n            if (status != OW_WILD_RUNTIME_STATUS_OK) { continue; }\n            OverworldWildSpawns_ProjectRuntimeEffectiveBehavior", "&runtime->behaviorStackRuntime, &expiry, &recovery);\n            if (otherStatus != OW_WILD_RUNTIME_STATUS_OK) { continue; }\n            OverworldWildSpawns_ProjectRuntimeEffectiveBehavior", "frame-timers")
    resolve_stage = "    status = OverworldWildRuntime_ResolveRecoveryCandidate(&context, origin, &candidate);"
    cases.append(("resolve disabled call", disable_once_in_function(source, APPLY_HELPER, resolve_stage), "postcommit-presentation"))
    add_in("resolve status overwritten", APPLY_HELPER, resolve_stage + "\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", resolve_stage + "\n    status = OW_WILD_RUNTIME_STATUS_OK;\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", "postcommit-presentation")
    apply_stage = "    status = OverworldWildRuntime_Apply();"
    cases.append(("apply disabled call", disable_once_in_function(source, APPLY_HELPER, apply_stage), "postcommit-presentation"))
    add_in("apply status overwritten", APPLY_HELPER, apply_stage + "\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", apply_stage + "\n    status = OW_WILD_RUNTIME_STATUS_OK;\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }", "postcommit-presentation")
    add_in("resolve guard checks unrelated status", APPLY_HELPER, "ResolveRecoveryCandidate(&context, origin, &candidate);\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    status = OverworldWildRuntime_Apply", "ResolveRecoveryCandidate(&context, origin, &candidate);\n    if (otherStatus != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    status = OverworldWildRuntime_Apply", "postcommit-presentation")
    add_in("apply guard checks unrelated status", APPLY_HELPER, "status = OverworldWildRuntime_Apply();\n    if (status != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    OverworldWildSpawns_ProjectRuntimeEffectiveBehavior", "status = OverworldWildRuntime_Apply();\n    if (otherStatus != OW_WILD_RUNTIME_STATUS_OK) { return FALSE; }\n    OverworldWildSpawns_ProjectRuntimeEffectiveBehavior", "postcommit-presentation")
    keep_live = "    OverworldWildSpawns_EnsureFrameMovementTask();"
    cases.append(("apply disabled keep-live", disable_once_in_function(source, APPLY_HELPER, keep_live), "timer-task-liveness"))
    add_in("legacy disabled exclusion exit", "OverworldWildSpawns_TickTiredEmote", "    if (OverworldWildSpawns_HasRuntimeTimerWork()) { return; }", "    if (OverworldWildSpawns_HasRuntimeTimerWork()) { if (0) { return; } }", "legacy-timer-ownership")
    liveness_disabled = replace_once_in_function(
        source,
        "OverworldWildSpawns_HasRuntimeTimerWork",
        "    return OverworldWildRuntime_GetTimerCount(\n            &runtime->behaviorStackRuntime, slot, slotGeneration) != 0",
        "    if (0) {\n        (void)OverworldWildRuntime_GetTimerCount(\n            &runtime->behaviorStackRuntime, slot, slotGeneration);\n    }\n    return 0 != 0",
    )
    cases.append(("liveness disabled timer query", liveness_disabled, "timer-task-liveness"))
    live_return = "    return OverworldWildRuntime_GetTimerCount(\n            &runtime->behaviorStackRuntime, slot, slotGeneration) != 0\n        || OverworldWildRuntime_GetPendingTimerExpiryCount(\n            &runtime->behaviorStackRuntime, slot, slotGeneration) != 0;"
    for label, replacement in (
        ("liveness whole expression and zero", "    return (OverworldWildRuntime_GetTimerCount(\n            &runtime->behaviorStackRuntime, slot, slotGeneration) != 0\n        || OverworldWildRuntime_GetPendingTimerExpiryCount(\n            &runtime->behaviorStackRuntime, slot, slotGeneration) != 0) && 0;"),
        ("liveness zero or expression", "    return 0 || OverworldWildRuntime_GetTimerCount(\n            &runtime->behaviorStackRuntime, slot, slotGeneration) != 0\n        || OverworldWildRuntime_GetPendingTimerExpiryCount(\n            &runtime->behaviorStackRuntime, slot, slotGeneration) != 0;"),
        ("liveness false operand", "    return FALSE && (OverworldWildRuntime_GetTimerCount(\n            &runtime->behaviorStackRuntime, slot, slotGeneration) != 0\n        || OverworldWildRuntime_GetPendingTimerExpiryCount(\n            &runtime->behaviorStackRuntime, slot, slotGeneration) != 0);"),
    ):
        add_in(label, "OverworldWildSpawns_HasRuntimeTimerWork", live_return, replacement, "timer-task-liveness")
    live_expression = live_return[len("    return ") : -1]
    for label, replacement in (
        ("liveness bitwise OR", live_return.replace("\n        ||", "\n        |")),
        ("liveness bitwise AND", live_return.replace("\n        ||", "\n        &")),
        ("liveness multiplied queries", live_return.replace("\n        ||", "\n        *")),
        ("liveness logical expression bitwise zero", f"    return ({live_expression}) & 0;"),
        ("liveness ternary", f"    return timerEnabled ? ({live_expression}) : 0;"),
        ("liveness constant-folded false", f"    return ({live_expression}) || FALSE;"),
    ):
        add_in(label, "OverworldWildSpawns_HasRuntimeTimerWork", live_return, replacement, "timer-task-liveness")
    cases.append(("pending disabled keep-live", disable_once_in_function(source, "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", keep_live), "timer-task-liveness"))

    for label, function, old, new, category in (
        ("capture other runtime", CAPTURE_HELPER, "&runtime->behaviorStackRuntime,\n        &runtime->movementCommandOrigins", "&otherRuntime->behaviorStackRuntime,\n        &runtime->movementCommandOrigins", "capture-wrapper"),
        ("capture other origin bank", CAPTURE_HELPER, "&runtime->movementCommandOrigins, slot", "&runtime->otherCommandOrigins, slot", "capture-wrapper"),
        ("capture other slot", CAPTURE_HELPER, "&runtime->movementCommandOrigins, slot, slotGeneration", "&runtime->movementCommandOrigins, otherSlot, slotGeneration", "capture-wrapper"),
        ("capture old generation", CAPTURE_HELPER, "slot, slotGeneration, &identity", "slot, oldGeneration, &identity", "capture-wrapper"),
        ("capture unrelated identity", CAPTURE_HELPER, "slotGeneration, &identity);", "slotGeneration, &otherIdentity);", "capture-wrapper"),
        ("capture cache old generation", CAPTURE_HELPER, "slot, slotGeneration, &effective);", "slot, oldGeneration, &effective);", "capture-wrapper"),
        ("consume other runtime", CONSUME_HELPER, "&runtime->behaviorStackRuntime,\n        &runtime->movementCommandOrigins", "&otherRuntime->behaviorStackRuntime,\n        &runtime->movementCommandOrigins", "consume-wrapper"),
        ("consume other slot", CONSUME_HELPER, "&runtime->movementCommandOrigins, slot, slotGeneration", "&runtime->movementCommandOrigins, otherSlot, slotGeneration", "consume-wrapper"),
        ("consume old generation", CONSUME_HELPER, "slot, slotGeneration, &identity, originOut", "slot, oldGeneration, &identity, originOut", "consume-wrapper"),
        ("consume unrelated output", CONSUME_HELPER, "&identity, originOut);", "&identity, &unrelatedOrigin);", "consume-wrapper"),
        ("consume cache other slot", CONSUME_HELPER, "slot, slotGeneration, &effective);", "otherSlot, slotGeneration, &effective);", "consume-wrapper"),
        ("prime other runtime", "OverworldWildSpawns_InitSpawnSlotState", "&runtime->behaviorStackRuntime,\n        slot, slotGeneration", "&otherRuntime->behaviorStackRuntime,\n        slot, slotGeneration", "canonical-initialization"),
        ("prime other slot", "OverworldWildSpawns_InitSpawnSlotState", "slot, slotGeneration, &staticContext", "otherSlot, slotGeneration, &staticContext", "canonical-initialization"),
        ("prime old generation", "OverworldWildSpawns_InitSpawnSlotState", "slot, slotGeneration, &staticContext", "slot, oldGeneration, &staticContext", "canonical-initialization"),
        ("prime other context", "OverworldWildSpawns_InitSpawnSlotState", "slotGeneration, &staticContext, &resolved", "slotGeneration, &otherContext, &resolved", "canonical-initialization"),
        ("prime unrelated output", "OverworldWildSpawns_InitSpawnSlotState", "&staticContext, &resolved);", "&staticContext, &otherResolved);", "canonical-initialization"),
        ("pending count other slot", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "&runtime->behaviorStackRuntime, slot, slotGeneration);", "&runtime->behaviorStackRuntime, otherSlot, slotGeneration);", "frame-timers"),
        ("pending count other runtime", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "pendingCount = OverworldWildRuntime_GetPendingTimerExpiryCount(\n            &runtime->behaviorStackRuntime", "pendingCount = OverworldWildRuntime_GetPendingTimerExpiryCount(\n            &otherRuntime->behaviorStackRuntime", "frame-timers"),
        ("pending query old generation", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "&runtime->behaviorStackRuntime, slot, slotGeneration,\n                pendingIndex, &expiry", "&runtime->behaviorStackRuntime, slot, oldGeneration,\n                pendingIndex, &expiry", "frame-timers"),
        ("pending query unrelated index", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "pendingIndex, &expiry);", "otherIndex, &expiry);", "frame-timers"),
        ("pending recover unrelated record", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "&runtime->behaviorStackRuntime, &expiry, &recovery", "&runtime->behaviorStackRuntime, &otherExpiry, &recovery", "frame-timers"),
        ("pending recover unrelated output", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "&expiry, &recovery);", "&expiry, &otherRecovery);", "frame-timers"),
        ("pending projection unrelated recovery", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "state, slot, &recovery);", "state, slot, &otherRecovery);", "frame-timers"),
    ):
        add_in(label, function, old, new, category)

    unbuilt_context = replace_once_in_function(
        source,
        "OverworldWildSpawns_InitSpawnSlotState",
        "    OverworldWildSpawns_BuildRuntimeStaticContext(&staticContext);\n",
        "",
    )
    cases.append(("prime uninitialized context", unbuilt_context, "canonical-initialization"))
    late_context = replace_once_in_function(
        source,
        "OverworldWildSpawns_InitSpawnSlotState",
        "    OverworldWildSpawns_BuildRuntimeStaticContext(&staticContext);\n",
        "",
    )
    late_context = replace_once_in_function(
        late_context,
        "OverworldWildSpawns_InitSpawnSlotState",
        prime_stage,
        prime_stage + "\n    OverworldWildSpawns_BuildRuntimeStaticContext(&staticContext);",
    )
    cases.append(("prime context built after use", late_context, "canonical-initialization"))

    for label, replacement in (
        ("throw compares false", "OverworldWildSpawns_StartPreparedCustomJumpCommand() == FALSE"),
        ("throw not true", "OverworldWildSpawns_StartPreparedCustomJumpCommand() != TRUE"),
        ("throw false first", "FALSE == OverworldWildSpawns_StartPreparedCustomJumpCommand()"),
        ("throw negated", "!OverworldWildSpawns_StartPreparedCustomJumpCommand()"),
        ("throw widened OR", "OverworldWildSpawns_StartPreparedCustomJumpCommand() || fallbackReady"),
    ):
        add(label, "OverworldWildSpawns_StartPreparedCustomJumpCommand()", replacement, "throw-route")
    add_in("RAM widened active predicate", "OverworldWildSpawns_EndRamCrash", "state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_ACTIVE) {", "state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_ACTIVE || allowRecovery) {", "ram-route")
    add_in("RAM impact false comparison", "OverworldWildSpawns_EndRamCrash", "                state->movementRamDirections[slot], profile)) { return; }", "                state->movementRamDirections[slot], profile) == FALSE) { return; }", "ram-route")
    add("FLED widened OR", "        && state->pendingSlot >= 0", "        || state->pendingSlot >= 0", "fled-route")
    add("FLED unrelated context", "OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)", "OverworldWildSpawns_IsMovementFieldContextCurrent(otherState, fieldSystem)", "fled-route")
    add("FLED unrelated object", "fieldSystem, &state->spawns[state->pendingSlot]", "fieldSystem, &otherState->spawns[state->pendingSlot]", "fled-route")

    add_in("pending wrong outer bound", "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", "for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++)", "for (slot = 0; slot < pendingCount; slot++)", "frame-timers")
    add_in("all-slot tick other runtime", "OverworldWildSpawns_TickRuntimeFrameTimers", "&runtime->behaviorStackRuntime,\n        presentationGateMask", "&otherRuntime->behaviorStackRuntime,\n        presentationGateMask", "frame-timers")
    add_in("timer liveness timer equals zero", "OverworldWildSpawns_HasRuntimeTimerWork", "slot, slotGeneration) != 0\n        ||", "slot, slotGeneration) == 0\n        ||", "timer-task-liveness")
    add_in("timer liveness pending greater zero", "OverworldWildSpawns_HasRuntimeTimerWork", "slot, slotGeneration) != 0;", "slot, slotGeneration) > 0;", "timer-task-liveness")
    add_in("frame liveness inverted", "OverworldWildSpawns_GetFrameMovementWorkForSlot", "if (OverworldWildSpawns_HasRuntimeTimerWork(state, slot))", "if (!OverworldWildSpawns_HasRuntimeTimerWork(state, slot))", "timer-task-liveness")
    add_in("frame liveness discarded by false", "OverworldWildSpawns_GetFrameMovementWorkForSlot", "if (OverworldWildSpawns_HasRuntimeTimerWork(state, slot))", "if (OverworldWildSpawns_HasRuntimeTimerWork(state, slot) && 0)", "timer-task-liveness")
    add_in("frame liveness bitwise condition", "OverworldWildSpawns_GetFrameMovementWorkForSlot", "if (OverworldWildSpawns_HasRuntimeTimerWork(state, slot))", "if (OverworldWildSpawns_HasRuntimeTimerWork(state, slot) & 1)", "timer-task-liveness")
    add_in("frame liveness ternary condition", "OverworldWildSpawns_GetFrameMovementWorkForSlot", "if (OverworldWildSpawns_HasRuntimeTimerWork(state, slot))", "if (OverworldWildSpawns_HasRuntimeTimerWork(state, slot) ? TRUE : FALSE)", "timer-task-liveness")
    add_in("timer liveness old generation", "OverworldWildSpawns_HasRuntimeTimerWork", "&runtime->behaviorStackRuntime, slot, slotGeneration) != 0\n        ||", "&runtime->behaviorStackRuntime, slot, oldGeneration) != 0\n        ||", "timer-task-liveness")
    return cases


def run_self_tests() -> tuple[int, list[str]]:
    source = DEFAULT_SOURCE.read_text(encoding="utf-8")
    baseline = verify_source(source)
    if baseline:
        raise AssertionError("repository baseline failed:\n  " + "\n  ".join(baseline))

    cases: list[tuple[str, str, str]] = []

    def add_in(
        label: str,
        function: str,
        old: str,
        new: str,
        category: str,
    ) -> None:
        cases.append(
            (
                label,
                replace_once_in_function(source, function, old, new),
                category,
            )
        )

    cases.append(
        (
            "legacy cache type restored",
            replace_once_in_function(
                source,
                "OverworldWildSpawns_CopySpawnConfiguration",
                "    OverworldWildRuntimeSlotSidecar *runtimeSlot;",
                "    OverworldWildRuntimeSlotSidecar *runtimeSlot;\n"
                "    OverworldWildBehaviorSlotCache *legacyCache;",
            ),
            "legacy-cutover",
        )
    )
    cases.append(
        (
            "runtime suffix displaced",
            replace_once(
                source,
                "    OverworldWildBehaviorStackRuntime behaviorStackRuntime;\n"
                "} OverworldWildOverlayRuntimeState;",
                "    OverworldWildBehaviorStackRuntime behaviorStackRuntime;\n"
                "    u32 trailingState;\n"
                "} OverworldWildOverlayRuntimeState;",
            ),
            "runtime-layout",
        )
    )
    add_in(
        "current cache read removed",
        "OverworldWildSpawns_GetCurrentBehavior",
        "OverworldWildRuntime_GetEffectiveCache(",
        "OverworldWildRuntime_GetUncheckedCache(",
        "direct-current",
    )
    add_in(
        "current cache uses stale generation",
        "OverworldWildSpawns_GetCurrentBehavior",
        "slot, slotGeneration, currentOut",
        "slot, oldGeneration, currentOut",
        "direct-current",
    )
    add_in(
        "configuration accessor removed",
        "OverworldWildSpawns_CopySpawnConfiguration",
        "OverworldWildRuntime_CopyValidatedSpawnConfiguration(",
        "OverworldWildRuntime_CopySpawnConfigurationUnchecked(",
        "spawn-configuration",
    )
    add_in(
        "configuration uses unrelated generation",
        "OverworldWildSpawns_CopySpawnConfiguration",
        "runtimeSlot->staticContextGeneration,",
        "otherStaticContextGeneration,",
        "spawn-configuration",
    )
    add_in(
        "movement callback skips current read",
        "OverworldWildSpawns_TryStartSpawnerMovementCommand",
        "OverworldWildSpawns_GetCurrentBehavior(",
        "OverworldWildSpawns_GetUncheckedBehavior(",
        "callback",
    )
    for label, role in (
        ("projection omits carried role", "OWBD_ROLE_CARRIED"),
        ("projection omits follower role", "OWBD_ROLE_FOLLOWER"),
        ("projection omits attentive role", "OWBD_ROLE_ATTENTIVE"),
    ):
        add_in(
            label,
            PROJECT_HELPER,
            "case " + role + ":",
            "case OWBD_ROLE_DISABLED:",
            "effective-projection",
        )
    add_in(
        "projection cache read removed",
        PROJECT_HELPER,
        "OverworldWildRuntime_GetEffectiveCache(",
        "OverworldWildRuntime_GetUncheckedCache(",
        "effective-projection",
    )
    add_in(
        "prime uses noncanonical applicability",
        "OverworldWildSpawns_FinalizePreparedSpawn",
        "&staticContext, NULL",
        "&staticContext, &applicability",
        "spawn-prime",
    )
    add_in(
        "follower omits authored route",
        "OverworldWildSpawns_FinalizePreparedSpawn",
        "        transitionEvent.systemRoute = OWBD_TRIGGER_FOLLOWER_APPLY;\n",
        "",
        "spawn-prime",
    )
    add_in(
        "spawn omits effective projection",
        "OverworldWildSpawns_SpawnPreparedEncounter",
        "OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(",
        "OverworldWildSpawns_ProjectLegacyBehavior(",
        "spawn-prime",
    )
    add_in(
        "aggro help route omitted",
        "OverworldWildSpawns_TryApplyRuntimeAttentiveCandidate",
        "        event.systemRoute = trigger;\n",
        "",
        "attentive-dispatch",
    )
    add_in(
        "help route guard omitted",
        "OverworldWildSpawns_TryApplyRuntimeAttentiveCandidate",
        "        || trigger == OWBD_TRIGGER_HELP_CALL_APPLY",
        "",
        "attentive-dispatch",
    )
    for label, trigger in (
        ("RAM route omitted", "OWBD_TRIGGER_RAM_CRASH"),
        ("throw route omitted", "OWBD_TRIGGER_THROW_RECOVERY"),
        ("fled route omitted", "OWBD_TRIGGER_FLED"),
    ):
        add_in(
            label,
            APPLY_HELPER,
            f"        event.systemRoute = {trigger};\n",
            "",
            "recovery-dispatch",
        )
    add_in(
        "stamina route omitted",
        APPLY_HELPER,
        "        event.systemRoute = OWBD_TRIGGER_STAMINA_EXHAUSTED;\n",
        "",
        "recovery-dispatch",
    )
    add_in(
        "stamina route mismatched",
        APPLY_HELPER,
        "        event.systemRoute = OWBD_TRIGGER_STAMINA_EXHAUSTED;\n",
        "        event.systemRoute = OWBD_TRIGGER_RAM_CRASH;\n",
        "recovery-dispatch",
    )
    for label, trigger in (
        ("stamina route made conditional", "OWBD_TRIGGER_STAMINA_EXHAUSTED"),
        ("RAM route made conditional", "OWBD_TRIGGER_RAM_CRASH"),
        ("throw route made conditional", "OWBD_TRIGGER_THROW_RECOVERY"),
        ("FLED route made conditional", "OWBD_TRIGGER_FLED"),
    ):
        add_in(
            label,
            APPLY_HELPER,
            f"        event.systemRoute = {trigger};\n",
            "        if (allowRoute) {\n"
            f"            event.systemRoute = {trigger};\n"
            "        }\n",
            "route-dominance",
        )
    add_in(
        "route overwritten after origin switch",
        APPLY_HELPER,
        "    if (runtime->movementPendingRuntimeTransitions[slot]\n",
        "    event.systemRoute = 0;\n"
        "    if (runtime->movementPendingRuntimeTransitions[slot]\n",
        "route-dominance",
    )
    add_in(
        "whole event overwritten after origin switch",
        APPLY_HELPER,
        "    if (runtime->movementPendingRuntimeTransitions[slot]\n",
        "    event = otherEvent;\n"
        "    if (runtime->movementPendingRuntimeTransitions[slot]\n",
        "route-dominance",
    )
    add_in(
        "event zeroed after origin switch",
        APPLY_HELPER,
        "    if (runtime->movementPendingRuntimeTransitions[slot]\n",
        "    memset(&event, 0, sizeof(event));\n"
        "    if (runtime->movementPendingRuntimeTransitions[slot]\n",
        "route-dominance",
    )
    add_in(
        "ordinary event writes replay record",
        "OverworldWildSpawns_TryApplyRuntimeAttentiveCandidate",
        "    event.trigger = trigger;\n",
        "    event.replayExpiry = otherExpiry;\n"
        "    event.trigger = trigger;\n",
        "ordinary-event",
    )
    add_in(
        "timer replay record omitted",
        "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries",
        "            event.replayExpiry = expiry;\n",
        "",
        "timer-replay",
    )
    add_in(
        "timer replay flag omitted",
        "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries",
        "            event.flags = OW_WILD_RUNTIME_TRANSITION_EVENT_REPLAY;\n",
        "",
        "timer-replay",
    )
    add_in(
        "timer replay uses live loop slot",
        "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries",
        "&runtime->behaviorStackRuntime, expiry.slotIndex,\n"
        "                expiry.slotGeneration, &event, &transition",
        "&runtime->behaviorStackRuntime, slot,\n"
        "                slotGeneration, &event, &transition",
        "timer-replay",
    )
    add_in(
        "timer replay projects unrelated slot",
        "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries",
        "state, slot, &transition",
        "state, otherSlot, &transition",
        "timer-replay",
    )
    cases.append(
        (
            "legacy profile projection restored",
            replace_once_in_function(
                source,
                "OverworldWildSpawns_EnsureBehaviorDataLoaded",
                "        void *projection = NULL;",
                "        void *projection = NULL;\n"
                "        OverworldWildBehaviorProfile legacyProfile;",
            ),
            "legacy-projection",
        )
    )
    add_in(
        "behavior catalog load skipped",
        "OverworldWildSpawns_FinalizePreparedSpawn",
        "OverworldWildSpawns_EnsureBehaviorDataLoaded()",
        "OverworldWildSpawns_AssumeBehaviorDataLoaded()",
        "spawn-prime",
    )
    add_in(
        "post-init rollback delete omitted",
        "OverworldWildSpawns_SpawnPreparedEncounter",
        "if (!OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(\n"
        "            state, slot, NULL)) {\n"
        "        DeleteMapObject(object);",
        "if (!OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(\n"
        "            state, slot, NULL)) {\n"
        "        (void)object;",
        "spawn-rollback",
    )
    delete_on_success = replace_once_in_function(
        source,
        "OverworldWildSpawns_SpawnPreparedEncounter",
        "if (!OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(\n"
        "            state, slot, NULL)) {\n"
        "        DeleteMapObject(object);",
        "if (!OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(\n"
        "            state, slot, NULL)) {\n"
        "        (void)object;",
    )
    delete_on_success = replace_once_in_function(
        delete_on_success,
        "OverworldWildSpawns_SpawnPreparedEncounter",
        "    OverworldWildSpawns_StartSpawnStartup(state, fieldSystem, slot, &prepared->startup);\n\n"
        "    return TRUE;",
        "    OverworldWildSpawns_StartSpawnStartup(state, fieldSystem, slot, &prepared->startup);\n"
        "    DeleteMapObject(object);\n\n"
        "    return TRUE;",
    )
    cases.append((
        "rollback delete moved onto success path",
        delete_on_success,
        "spawn-rollback",
    ))
    add_in(
        "recovery pending origin omitted",
        APPLY_HELPER,
        "    runtime->movementPendingRuntimeTransitions[slot] = origin;\n",
        "",
        "transition-retry",
    )
    add_in(
        "recovery pending clear omitted",
        APPLY_HELPER,
        "    runtime->movementPendingRuntimeTransitions[slot] =\n"
        "        OW_WILD_RUNTIME_TRANSITION_PENDING_NONE;\n",
        "",
        "transition-retry",
    )
    add_in(
        "retry loop drops recoveries",
        "OverworldWildSpawns_RetryPendingRuntimeTransitions",
        "OverworldWildSpawns_TryApplyRuntimeRecoveryCandidate(",
        "OverworldWildSpawns_DropPendingRuntimeRecovery(",
        "transition-retry",
    )
    add_in(
        "follower remove route omitted",
        "OverworldWildSpawns_TryApplyRuntimeFollowerRemove",
        "    event.systemRoute = OWBD_TRIGGER_FOLLOWER_REMOVE;\n",
        "",
        "follower-remove",
    )
    add_in(
        "follower remove dispatch skipped",
        "OverworldWildSpawns_RemoveFollower",
        "OverworldWildSpawns_TryApplyRuntimeFollowerRemove(state)",
        "OverworldWildSpawns_AssumeRuntimeFollowerRemoved(state)",
        "follower-remove",
    )
    for label, function, origin in (
        (
            "throw recovery callsite removed",
            "OverworldWildSpawns_TryStartFrameDrivenActiveMovementCommand",
            "OW_WILD_RUNTIME_RECOVERY_ORIGIN_THROW_RECOVERY",
        ),
        (
            "RAM recovery callsite removed",
            "OverworldWildSpawns_EndRamCrash",
            "OW_WILD_RUNTIME_RECOVERY_ORIGIN_RAM_CRASH",
        ),
        (
            "FLED recovery callsite removed",
            "OverworldWildSpawns_OverlayCleanupPendingBattle",
            "OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED",
        ),
    ):
        add_in(
            label,
            function,
            origin,
            "OW_WILD_RUNTIME_RECOVERY_ORIGIN_REMOVED",
            "route-callsite",
        )
    add_in(
        "FLED field authentication omitted",
        "OverworldWildSpawns_OverlayCleanupPendingBattle",
        "                && OverworldWildSpawns_IsMovementFieldContextCurrent(\n"
        "                    state, fieldSystem)\n",
        "",
        "fled-auth",
    )
    add_in(
        "FLED retained object authentication omitted",
        "OverworldWildSpawns_OverlayCleanupPendingBattle",
        "OverworldWildSpawns_IsCurrentSpawnObject(",
        "OverworldWildSpawns_AssumeCurrentSpawnObject(",
        "fled-auth",
    )
    add_in(
        "command origin capture removed",
        "OverworldWildSpawns_CaptureMovementCommandOrigin",
        "OverworldWildRuntime_CaptureCommandOrigin(",
        "OverworldWildRuntime_CaptureUncheckedOrigin(",
        "command-origin",
    )
    add_in(
        "command origin consume removed",
        "OverworldWildSpawns_ConsumeMovementCommandOrigin",
        "OverworldWildRuntime_ConsumeCommandOrigin(",
        "OverworldWildRuntime_ConsumeUncheckedOrigin(",
        "command-origin",
    )
    add_in(
        "completed command skips origin consume",
        "OverworldWildSpawns_HandleFinishedMovementCommand",
        "OverworldWildSpawns_ConsumeMovementCommandOrigin(",
        "OverworldWildSpawns_AssumeMovementCommandOrigin(",
        "command-origin",
    )
    add_in(
        "slot reset skips origin invalidation",
        "OverworldWildSpawns_ResetSlotState",
        "OverworldWildSpawns_InvalidateMovementCommandOrigin(state, slot)",
        "OverworldWildSpawns_AssumeMovementCommandOriginInvalid(state, slot)",
        "command-origin",
    )
    add_in(
        "resident cleanup omits cold mark",
        "OverworldWildSpawns_CleanupResidentData",
        "OverworldWildRuntime_MarkResidentCold(",
        "OverworldWildRuntime_AssumeResidentCold(",
        "lifecycle",
    )
    add_in(
        "resident cleanup drops pending transitions",
        "OverworldWildSpawns_CleanupResidentData",
        "            runtime->movementPendingRuntimeTransitions,\n"
        "            pendingTransitions,\n"
        "            sizeof(pendingTransitions));",
        "            pendingTransitions,\n"
        "            pendingTransitions,\n"
        "            sizeof(pendingTransitions));",
        "lifecycle",
    )
    add_in(
        "resident cold guard removed",
        "OverworldWildSpawns_EnsureRuntimeState",
        "OW_WILD_RUNTIME_LIFETIME_RESIDENT_COLD",
        "OW_WILD_RUNTIME_LIFETIME_UNKNOWN",
        "lifecycle",
    )
    add_in(
        "cold rebind keeps stale origins",
        "OverworldWildSpawns_EnsureRuntimeState",
        "OverworldWildSpawns_InvalidateAllMovementCommandOrigins(state)",
        "OverworldWildSpawns_AssumeAllMovementCommandOriginsInvalid(state)",
        "lifecycle",
    )

    categories: set[str] = set()
    for label, mutated_source, expected in cases:
        issues = verify_source(mutated_source)
        if not any(issue.startswith(f"[{expected}]") for issue in issues):
            raise AssertionError(f"mutation {label!r} missed {expected}: {issues}")
        categories.add(expected)
    return len(cases), sorted(categories)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--self-test-only",
        action="store_true",
        help="run mutation tests without checking the repository source",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        mutation_count, categories = run_self_tests()
    except (AssertionError, SourceShapeError) as error:
        print(f"verifier self-test failed: {error}", file=sys.stderr)
        return 2
    print(
        "live runtime integration verifier self-tests passed: "
        f"{mutation_count} mutations across {len(categories)} categories "
        f"({', '.join(categories)})"
    )
    if args.self_test_only:
        return 0
    try:
        source = args.source.read_text(encoding="utf-8")
    except OSError as error:
        print(f"could not read {args.source}: {error}", file=sys.stderr)
        return 2
    issues = verify_source(source)
    if issues:
        print(f"live runtime integration verification failed ({len(issues)} issue(s)):")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print(f"live runtime integration verified: {args.source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
