#!/usr/bin/env python3
"""Verify the AnyBox PC placement de-duplication and its observable semantics."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import re
import struct
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path


ARM9_BASE = 0x02000000
EXPECTED_NUM_PC_BOXES = 30
EXPECTED_MAX_MON_MOVES = 4
RESTORE_BOX_MON_PP_SIZE = 0x4E
OVERLAY_129_ID = 129
OVERLAY_129_LOAD = 0x023D8000
OVERLAY_129_CORE_OFFSET = 0x600
ANYBOX_STOCK_HOOK_ADDRESS = 0x02073BB8
ANYBOX_HOOK_REGISTER = 2
OUTER_FUNCTION_SIZE = 0x6C
INNER_FUNCTION_SIZE = 0x8C
OUTER_FUNCTION_SHA256 = "f9e2db914242c7d88e3c520214f0adb56939dd70a34e1f59cf70655befc96ae9"
INNER_FUNCTION_MEMCPY_BL_NORMALIZED_SHA256 = (
    "8b5480d28330dc3fe3a3e7e7cc6b3bb78e66fad0b6f73b30902209a57e8f6291"
)
STOCK_RESTORE_BOX_MON_PP = bytes.fromhex(
    "f8 b5 82 b0 05 1c fb f7 85 fa 00 24 00 90 27 1c 01 ae "
    "21 1c 28 1c 36 31 3a 1c fb f7 af fe 00 28 0c d0 21 1c "
    "28 1c 42 31 00 22 fb f7 a7 fe 21 1c 30 70 28 1c 3a 31 "
    "01 aa fc f7 38 fa 64 1c 04 2c e7 db 00 99 28 1c fb f7 "
    "79 fa 02 b0 f8 bd"
)


class VerificationError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise VerificationError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def strip_comments(source: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def function_body(source: str, name: str, return_type: str = "BOOL") -> str:
    match = re.search(
        rf"\b{return_type}(?:\s+LONG_CALL)?\s+{name}\s*\([^;{{}}]*\)\s*\{{",
        source,
    )
    require(match is not None, f"{name} definition is missing")
    start = match.end() - 1
    depth = 0
    for position in range(start, len(source)):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1 : position]
    fail(f"{name} definition has unbalanced braces")


def compact(source: str) -> str:
    return re.sub(r"\s+", "", strip_comments(source))


def macro_integer(value: str, macros: dict[str, str], seen: set[str] | None = None) -> int:
    value = value.strip()
    if re.fullmatch(r"(?:0[xX][0-9A-Fa-f]+|\d+)[uUlL]*", value):
        return int(re.sub(r"[uUlL]+$", "", value), 0)
    if re.fullmatch(r"[A-Za-z_]\w*", value):
        if value not in macros:
            return 0
        seen = set() if seen is None else seen
        require(value not in seen, f"recursive macro value for {value}")
        seen.add(value)
        replacement = macros[value]
        return 1 if replacement == "" else macro_integer(replacement, macros, seen)
    fail(f"unsupported integer macro expression: {value}")


def preprocessor_condition(expression: str, macros: dict[str, str]) -> bool:
    expression = expression.strip()
    while expression.startswith("(") and expression.endswith(")"):
        expression = expression[1:-1].strip()
    defined = re.fullmatch(r"defined\s*\(?\s*([A-Za-z_]\w*)\s*\)?", expression)
    if defined is not None:
        return defined.group(1) in macros
    not_defined = re.fullmatch(
        r"!\s*defined\s*\(?\s*([A-Za-z_]\w*)\s*\)?", expression
    )
    if not_defined is not None:
        return not_defined.group(1) not in macros
    if expression.startswith("!"):
        return not preprocessor_condition(expression[1:], macros)
    return macro_integer(expression, macros) != 0


def evaluate_preprocessor(
    source: str,
    initial_macros: dict[str, str] | None = None,
    emit_active_source: bool = False,
) -> tuple[str, dict[str, str]]:
    output: list[str] = []
    macros = dict(initial_macros or {})
    # Each entry is (parent active, any branch taken, else already seen).
    stack: list[tuple[bool, bool, bool]] = []
    active = True
    source = strip_comments(source)
    for line_number, line in enumerate(source.splitlines(keepends=True), 1):
        directive = re.match(r"^\s*#\s*(\w+)(?:\s+(.*?))?\s*$", line)
        if directive is None:
            if active and emit_active_source:
                output.append(line)
            continue

        kind = directive.group(1)
        argument = (directive.group(2) or "").split("//", 1)[0].strip()
        if kind in ("ifdef", "ifndef"):
            require(
                re.fullmatch(r"[A-Za-z_]\w*", argument) is not None,
                f"malformed #{kind} at source line {line_number}",
            )
            condition = argument in macros
            if kind == "ifndef":
                condition = not condition
            stack.append((active, condition, False))
            active = active and condition
        elif kind == "if":
            condition = preprocessor_condition(argument, macros)
            stack.append((active, condition, False))
            active = active and condition
        elif kind == "else":
            require(bool(stack), f"unmatched #else at source line {line_number}")
            parent, condition, else_seen = stack[-1]
            require(not else_seen, f"duplicate #else at source line {line_number}")
            stack[-1] = (parent, condition, True)
            active = parent and not condition
        elif kind == "elif":
            require(bool(stack), f"unmatched #elif at source line {line_number}")
            parent, branch_taken, else_seen = stack[-1]
            require(not else_seen, f"#elif after #else at source line {line_number}")
            condition = preprocessor_condition(argument, macros)
            active = parent and not branch_taken and condition
            stack[-1] = (parent, branch_taken or condition, False)
        elif kind == "endif":
            require(bool(stack), f"unmatched #endif at source line {line_number}")
            parent, _condition, _else_seen = stack.pop()
            active = parent
        elif kind == "define" and active:
            definition = re.match(r"([A-Za-z_]\w*)(?:\([^)]*\))?(?:\s+(.*))?$", argument)
            require(definition is not None, f"malformed #define at source line {line_number}")
            name = definition.group(1)
            value = (definition.group(2) or "").strip()
            require(
                name not in macros or macros[name] == value,
                f"conflicting active definition for {name} at source line {line_number}",
            )
            macros[name] = value
        elif kind == "undef" and active:
            require(
                re.fullmatch(r"[A-Za-z_]\w*", argument) is not None,
                f"malformed #undef at source line {line_number}",
            )
            macros.pop(argument, None)
        elif active and emit_active_source:
            output.append(line)

    require(not stack, "unterminated preprocessor conditional in storage source")
    return "".join(output), macros


def verify_configuration(
    config_source: str, save_constants: str, party_header: str
) -> tuple[dict[str, str], int, int]:
    _config_output, config_macros = evaluate_preprocessor(config_source)
    for required in ("ALLOW_SAVE_CHANGES", "EXPAND_PC_BOXES"):
        require(required in config_macros, f"production config does not enable {required}")
    _save_output, save_macros = evaluate_preprocessor(save_constants)
    _party_output, party_macros = evaluate_preprocessor(party_header)
    require("NUM_PC_BOXES" in save_macros, "active NUM_PC_BOXES definition is missing")
    require("MAX_MON_MOVES" in party_macros, "active MAX_MON_MOVES definition is missing")
    num_boxes = macro_integer(save_macros["NUM_PC_BOXES"], save_macros)
    max_moves = macro_integer(party_macros["MAX_MON_MOVES"], party_macros)
    require(
        num_boxes == EXPECTED_NUM_PC_BOXES,
        f"NUM_PC_BOXES drifted from reviewed production value {EXPECTED_NUM_PC_BOXES}",
    )
    require(
        max_moves == EXPECTED_MAX_MON_MOVES,
        f"MAX_MON_MOVES drifted from reviewed production value {EXPECTED_MAX_MON_MOVES}",
    )
    return config_macros, num_boxes, max_moves


def verify_source(source: str) -> None:
    source = strip_comments(source)
    outer = compact(function_body(source, "PCStorage_PlaceMonInFirstEmptySlotInAnyBox"))
    inner = compact(function_body(source, "PCStorage_PlaceMonInBoxFirstEmptySlot"))
    set_modified = compact(function_body(source, "PCStorage_SetBoxModified", "void"))

    expected_outer = re.compile(
        r"^(?:s32|u32)i=storage->curBox;"
        r"do\{"
        r"if\(PCStorage_PlaceMonInBoxFirstEmptySlot\(storage,i,boxMon\)\)\{"
        r"returnTRUE;\}"
        r"i\+\+;"
        r"if\(i>=NUM_PC_BOXES\)\{i=0;\}"
        r"\}while\(i!=storage->curBox\);"
        r"returnFALSE;$"
    )
    require(
        expected_outer.fullmatch(outer) is not None,
        "AnyBox traversal is not the reviewed current-box/wraparound/full-storage loop",
    )
    require(
        outer.count("PCStorage_PlaceMonInBoxFirstEmptySlot(") == 1,
        "AnyBox must delegate exactly once per attempted box",
    )
    require(
        "RestoreBoxMonPP(" not in outer,
        "AnyBox still has a redundant outer RestoreBoxMonPP call",
    )
    require(
        "PCStorage_SetBoxModified(" not in outer,
        "AnyBox still has a redundant outer PCStorage_SetBoxModified call",
    )

    expected_inner = re.compile(
        r"^u32i;"
        r"RestoreBoxMonPP\(boxMon\);"
        r"if\(boxno==-1u\)\{boxno=storage->curBox;\}"
        r"for\(i=0;i<MONS_PER_BOX;i\+\+\)\{"
        r"if\(GetBoxMonData\(&storage->boxes\[boxno\]\.mons\[i\],"
        r"MON_DATA_SPECIES,NULL\)==SPECIES_NONE\)\{"
        r"storage->boxes\[boxno\]\.mons\[i\]=\*boxMon;"
        r"PCStorage_SetBoxModified\(storage,boxno\);"
        r"returnTRUE;\}"
        r"\}"
        r"returnFALSE;$"
    )
    require(
        expected_inner.fullmatch(inner) is not None,
        "inner first-empty placement no longer has the reviewed stock behavior",
    )
    require(
        inner.count("RestoreBoxMonPP(") == 1,
        "inner placement must restore PP exactly once per attempted box",
    )
    require(
        inner.count("PCStorage_SetBoxModified(") == 1,
        "inner placement must mark exactly the one successfully modified box",
    )
    expected_set_modified = re.compile(
        r"^if\(boxno>=NUM_PC_BOXES\)\{"
        r"GF_ASSERT\(0\);"
        r"return;\}"
        r"storage->boxModifiedFlag\|=1<<boxno;$"
    )
    require(
        expected_set_modified.fullmatch(set_modified) is not None,
        "PCStorage_SetBoxModified no longer bounds-checks then idempotently ORs one box bit",
    )


def linker_thumb_symbol(linker_script: str, name: str) -> int:
    match = re.search(
        rf"^\s*{name}\s*=\s*(0x[0-9A-Fa-f]+)\s*\|\s*1\s*;",
        strip_comments(linker_script),
        flags=re.MULTILINE,
    )
    require(match is not None, f"linked {name} address is missing")
    return int(match.group(1), 16)


def thumb_bl_target(code: bytes, function_address: int, call_offset: int) -> int:
    require(call_offset + 4 <= len(code), "authenticated Thumb BL is out of range")
    first, second = struct.unpack_from("<HH", code, call_offset)
    require(
        first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800,
        f"expected Thumb BL at RestoreBoxMonPP+0x{call_offset:X}",
    )
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & (1 << 22):
        displacement -= 1 << 23
    return function_address + call_offset + 4 + displacement


def verify_restore_box_pp_machine(arm9: bytes, linker_script: str, max_moves: int) -> None:
    restore_address = linker_thumb_symbol(linker_script, "RestoreBoxMonPP")
    get_box_data = linker_thumb_symbol(linker_script, "GetBoxMonData")
    set_box_data = linker_thumb_symbol(linker_script, "SetBoxMonData")
    offset = restore_address - ARM9_BASE
    require(
        offset >= 0 and offset + RESTORE_BOX_MON_PP_SIZE <= len(arm9),
        "linked RestoreBoxMonPP range is absent from ARM9",
    )
    code = arm9[offset : offset + RESTORE_BOX_MON_PP_SIZE]
    require(
        code == STOCK_RESTORE_BOX_MON_PP,
        "production RestoreBoxMonPP machine contract drifted",
    )

    # The exact stock helper is authenticated as:
    # acquire lock; loop move attrs 0x36..; for nonzero moves read max-PP attrs
    # 0x42.. and write current-PP attrs 0x3A..; then release the same lock.
    expected_calls = (
        (0x06, 0x0206DDD8, "AcquireBoxMonLock"),
        (0x1A, get_box_data, "GetBoxMonData(move)"),
        (0x2A, get_box_data, "GetBoxMonData(max PP)"),
        (0x38, set_box_data, "SetBoxMonData(current PP)"),
        (0x46, 0x0206DE00, "ReleaseBoxMonLock"),
    )
    for call_offset, expected_target, label in expected_calls:
        require(
            thumb_bl_target(code, restore_address, call_offset) == expected_target,
            f"RestoreBoxMonPP no longer calls authenticated {label}",
        )
    require(code[0x12:0x20] == bytes.fromhex("21 1c 28 1c 36 31 3a 1c fb f7 af fe 00 28"),
            "RestoreBoxMonPP move-presence predicate drifted")
    require(code[0x22:0x3C] == bytes.fromhex(
                "21 1c 28 1c 42 31 00 22 fb f7 a7 fe 21 1c 30 70 28 1c 3a 31 01 aa fc f7 38 fa"
            ),
            "RestoreBoxMonPP max-PP read/current-PP write contract drifted")
    require(
        code[0x3E:0x44] == bytes((max_moves, 0x2C, 0xE7, 0xDB, 0x00, 0x99)),
        "RestoreBoxMonPP loop bound does not match derived MAX_MON_MOVES",
    )


def linked_symbols(path: Path) -> dict[str, tuple[int, int]]:
    result = subprocess.run(
        ["arm-none-eabi-nm", "-S", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    symbols: dict[str, tuple[int, int]] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 4:
            symbols[parts[3]] = (int(parts[0], 16) & ~1, int(parts[1], 16))
        elif len(parts) == 3:
            symbols[parts[2]] = (int(parts[0], 16) & ~1, 0)
    return symbols


def elf_sections(elf: bytes) -> list[tuple[int, int, int, int]]:
    require(elf[:4] == b"\x7fELF", "linked object is not ELF")
    require(elf[4:6] == b"\x01\x01", "linked object is not 32-bit little-endian ELF")
    section_offset = struct.unpack_from("<I", elf, 0x20)[0]
    section_entry_size, section_count = struct.unpack_from("<HH", elf, 0x2E)
    require(section_entry_size >= 0x28, "linked ELF section-header size is invalid")
    require(
        section_offset + section_entry_size * section_count <= len(elf),
        "linked ELF section table is truncated",
    )
    sections = []
    for index in range(section_count):
        entry = section_offset + index * section_entry_size
        section_type, flags, address, file_offset, size = struct.unpack_from(
            "<IIIII", elf, entry + 4
        )
        require(file_offset + (0 if section_type == 8 else size) <= len(elf),
                "linked ELF section contents are truncated")
        sections.append((section_type, flags, address, file_offset, size))
    return sections


def elf_virtual_file_offset(elf: bytes, address: int, size: int) -> int:
    for section_type, _flags, section_address, file_offset, section_size in elf_sections(elf):
        if section_type != 8 and section_address <= address and (
            address + size <= section_address + section_size
        ):
            return file_offset + address - section_address
    fail(f"linked ELF range 0x{address:08X}+0x{size:X} is absent")


def elf_virtual_bytes(elf: bytes, address: int, size: int) -> bytes:
    offset = elf_virtual_file_offset(elf, address, size)
    return elf[offset : offset + size]


def elf_flat_binary(elf: bytes) -> tuple[int, bytes]:
    loadable = [
        section
        for section in elf_sections(elf)
        if section[1] & 0x2 and section[0] != 8 and section[4] > 0
    ]
    require(bool(loadable), "linked ELF has no allocated file-backed sections")
    start = min(section[2] for section in loadable)
    end = max(section[2] + section[4] for section in loadable)
    flat = bytearray(end - start)
    occupied = bytearray(end - start)
    for _section_type, _flags, address, file_offset, size in loadable:
        offset = address - start
        require(
            not any(occupied[offset : offset + size]),
            "linked ELF allocated sections overlap",
        )
        flat[offset : offset + size] = elf[file_offset : file_offset + size]
        occupied[offset : offset + size] = b"\x01" * size
    return start, bytes(flat)


def thumb_bl_calls(code: bytes, address: int) -> list[tuple[int, int]]:
    calls = []
    for offset in range(0, len(code) - 3, 2):
        first, second = struct.unpack_from("<HH", code, offset)
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            calls.append((offset, thumb_bl_target(code, address, offset)))
    return calls


def thumb_bl_displacement_normalized_sha256(
    code: bytes, call_offsets: list[int]
) -> str:
    """Hash exact machine code with selected BL displacements canonicalized."""
    normalized = bytearray(code)
    for offset in call_offsets:
        require(
            0 <= offset and offset + 4 <= len(normalized) and offset % 2 == 0,
            "authenticated Thumb BL offset is outside the function",
        )
        normalized[offset : offset + 4] = struct.pack("<HH", 0xF000, 0xF800)
    return hashlib.sha256(normalized).hexdigest()


def encode_thumb_bl(site: int, target: int) -> bytes:
    displacement = target - (site + 4)
    require(displacement % 2 == 0, "adversarial Thumb BL target is unaligned")
    require(-(1 << 22) <= displacement < (1 << 22), "adversarial Thumb BL is out of range")
    encoded = displacement & ((1 << 23) - 1)
    return struct.pack(
        "<HH", 0xF000 | ((encoded >> 12) & 0x7FF), 0xF800 | ((encoded >> 1) & 0x7FF)
    )


def hook_declaration(hooks_source: str) -> tuple[int, int]:
    matches = []
    for line in hooks_source.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "arm9" and parts[1] == (
            "PCStorage_PlaceMonInFirstEmptySlotInAnyBox"
        ):
            require(len(parts) == 4, "AnyBox hook declaration shape drifted")
            matches.append((int(parts[2], 16), int(parts[3], 0)))
    require(len(matches) == 1, "expected exactly one active AnyBox ARM9 hook declaration")
    return matches[0]


def verify_linked_and_packaged_artifacts(
    linked_elf: bytes,
    symbols: dict[str, tuple[int, int]],
    core: bytes,
    packaged_overlay: bytes,
    overlay_table: bytes,
    arm9: bytes,
    hooks_source: str,
    linker_script: str,
) -> None:
    outer_address, outer_size = symbols.get(
        "PCStorage_PlaceMonInFirstEmptySlotInAnyBox", (0, 0)
    )
    inner_address, inner_size = symbols.get(
        "PCStorage_PlaceMonInBoxFirstEmptySlot", (0, 0)
    )
    set_modified_address, _set_size = symbols.get("PCStorage_SetBoxModified", (0, 0))
    memcpy_address, _memcpy_size = symbols.get("memcpy", (0, 0))
    sub_address, sub_size = symbols.get("sub_02074128", (0, 0))
    require(
        outer_size == OUTER_FUNCTION_SIZE and inner_size == INNER_FUNCTION_SIZE,
        "linked AnyBox/inner function boundaries drifted",
    )
    require(
        all((outer_address, inner_address, set_modified_address, memcpy_address, sub_address)),
        "linked PC storage call-graph symbols are incomplete",
    )
    veneer_address = sub_address + sub_size
    require(
        elf_virtual_bytes(linked_elf, veneer_address, 2) == b"\x18\x47",
        "linked bx-r3 veneer used by inner storage drifted",
    )
    outer = elf_virtual_bytes(linked_elf, outer_address, outer_size)
    inner = elf_virtual_bytes(linked_elf, inner_address, inner_size)
    expected_outer_calls = [(0x2A, inner_address)]
    require(
        thumb_bl_calls(outer, outer_address) == expected_outer_calls,
        "linked AnyBox must contain exactly one BL and it must target inner placement",
    )
    require(
        hashlib.sha256(outer).hexdigest() == OUTER_FUNCTION_SHA256,
        "linked AnyBox exact machine/control-flow contract drifted",
    )
    restore_address = linker_thumb_symbol(linker_script, "RestoreBoxMonPP")
    require(
        struct.pack("<I", restore_address | 1) not in outer
        and struct.pack("<I", set_modified_address | 1) not in outer,
        "linked AnyBox retains an outer RestoreBoxMonPP/SetBoxModified target",
    )
    require(
        struct.unpack_from("<HHHHHH", outer, 0x54)
        == (0x42AB, 0xD1E5, 0xBDFE, 0x2001, 0xE7FC, 0x46C0),
        "linked AnyBox loop/failure/success return control flow drifted",
    )

    expected_inner_calls = [
        (0x0C, veneer_address),
        (0x42, veneer_address),
        (0x58, memcpy_address),
        (0x62, set_modified_address),
    ]
    require(
        thumb_bl_calls(inner, inner_address) == expected_inner_calls,
        "linked inner placement call boundaries/control flow drifted",
    )
    require(
        thumb_bl_displacement_normalized_sha256(inner, [0x58])
        == INNER_FUNCTION_MEMCPY_BL_NORMALIZED_SHA256,
        "linked inner placement exact machine/control-flow contract drifted",
    )
    require(
        inner.count(struct.pack("<I", restore_address | 1)) == 1
        and struct.unpack_from("<I", inner, 0x78)[0] == restore_address | 1,
        "linked inner placement must contain exactly one authenticated RestoreBoxMonPP call target",
    )
    get_box_data = linker_thumb_symbol(linker_script, "GetBoxMonData")
    require(
        struct.unpack_from("<I", inner, 0x88)[0] == get_box_data | 1,
        "linked inner first-empty scan GetBoxMonData target drifted",
    )
    require(
        sum(target == set_modified_address for _offset, target in expected_inner_calls) == 1,
        "linked inner placement must contain exactly one PCStorage_SetBoxModified call",
    )
    require(
        struct.unpack_from("<HHHHHHHH", inner, 0x66)
        == (0x2001, 0xBDFE, 0x3501, 0x3788, 0x2D1E, 0xD1E3, 0x2000, 0xE7F8),
        "linked inner success/failure/slot-loop control flow drifted",
    )

    core_address, linked_flat = elf_flat_binary(linked_elf)
    require(linked_flat == core, "build/output.bin differs from the linked ELF image")
    require(
        core_address == OVERLAY_129_LOAD + OVERLAY_129_CORE_OFFSET,
        "linked core start no longer matches overlay 129 package offset",
    )
    require(
        len(packaged_overlay) == OVERLAY_129_CORE_OFFSET + len(core)
        and packaged_overlay[OVERLAY_129_CORE_OFFSET:] == core,
        "packaged overlay 129 does not contain exact build/output.bin at +0x600",
    )
    require(len(overlay_table) % 0x20 == 0, "ARM9 overlay table row size is invalid")
    rows = [
        struct.unpack_from("<8I", overlay_table, offset)
        for offset in range(0, len(overlay_table), 0x20)
    ]
    overlay_rows = [row for row in rows if row[0] == OVERLAY_129_ID]
    require(len(overlay_rows) == 1, "ARM9 overlay table must contain exactly one overlay 129 row")
    require(
        overlay_rows[0]
        == (
            OVERLAY_129_ID,
            OVERLAY_129_LOAD,
            len(packaged_overlay),
            0,
            0,
            0,
            OVERLAY_129_ID,
            0,
        ),
        "overlay 129 y9 load/size/BSS/init/file/compression metadata drifted",
    )

    hook_address, hook_register = hook_declaration(hooks_source)
    require(
        (hook_address, hook_register)
        == (ANYBOX_STOCK_HOOK_ADDRESS, ANYBOX_HOOK_REGISTER),
        "AnyBox hook declaration must match independently pinned stock entry 0x02073BB8/r2",
    )
    hook_offset = ANYBOX_STOCK_HOOK_ADDRESS - ARM9_BASE
    expected_hook = struct.pack("<HHI", 0x4A00, 0x4710, outer_address | 1)
    require(
        0 <= hook_offset and hook_offset + len(expected_hook) <= len(arm9),
        "AnyBox ARM9 hook range is absent",
    )
    require(
        arm9[hook_offset : hook_offset + len(expected_hook)] == expected_hook,
        "ARM9 AnyBox hook/veneer does not target the linked outer function",
    )


@dataclass(frozen=True)
class Move:
    move_id: int
    base_pp: int
    pp_ups: int
    current_pp: int

    @property
    def maximum_pp(self) -> int:
        return self.base_pp + self.base_pp * self.pp_ups // 5


@dataclass(frozen=True)
class BoxMon:
    moves: tuple[Move, ...]


@dataclass(frozen=True)
class Result:
    stored: bool
    destination: int | None
    source: BoxMon
    stored_mon: BoxMon | None
    modified_flags: int
    restore_calls: int
    modified_calls: int
    attempts: int


def restore_pp(mon: BoxMon) -> BoxMon:
    return BoxMon(
        tuple(
            replace(move, current_pp=move.maximum_pp)
            if move.move_id != 0
            else move
            for move in mon.moves
        )
    )


def place(
    full_boxes: int,
    start: int,
    mon: BoxMon,
    modified_flags: int,
    redundant_outer_calls: bool,
    num_boxes: int,
) -> Result:
    box = start
    restores = 0
    modified = 0
    attempts = 0
    while True:
        attempts += 1
        if redundant_outer_calls:
            mon = restore_pp(mon)
            restores += 1

        # PCStorage_PlaceMonInBoxFirstEmptySlot is retained unchanged.
        mon = restore_pp(mon)
        restores += 1
        if not (full_boxes & (1 << box)):
            modified_flags |= 1 << box
            modified += 1
            stored_mon = mon
            if redundant_outer_calls:
                modified_flags |= 1 << box
                modified += 1
            return Result(
                True,
                box,
                mon,
                stored_mon,
                modified_flags,
                restores,
                modified,
                attempts,
            )

        box += 1
        if box >= num_boxes:
            box = 0
        if box == start:
            return Result(
                False,
                None,
                mon,
                None,
                modified_flags,
                restores,
                modified,
                attempts,
            )


def observable(result: Result) -> tuple[object, ...]:
    return (
        result.stored,
        result.destination,
        result.source,
        result.stored_mon,
        result.modified_flags,
        result.attempts,
    )


def compare_case(
    full_boxes: int, start: int, mon: BoxMon, flags: int, num_boxes: int
) -> None:
    before = place(full_boxes, start, mon, flags, True, num_boxes)
    after = place(full_boxes, start, mon, flags, False, num_boxes)
    require(observable(before) == observable(after), "de-duplication changed observable placement state")
    require(
        after.restore_calls == after.attempts,
        "optimized path does not restore exactly once per attempted box",
    )
    require(
        before.restore_calls == after.attempts * 2,
        "reference model does not contain the proven redundant outer restore",
    )
    expected_modified = 1 if after.stored else 0
    require(
        after.modified_calls == expected_modified,
        "optimized path does not mark exactly once on success and never on failure",
    )
    require(
        before.modified_calls == expected_modified * 2,
        "reference model does not contain the proven redundant outer mark",
    )


def move_fixture(move_count: int, pp_ups: tuple[int, ...], max_moves: int) -> BoxMon:
    base_pp = (5, 10, 15, 40)
    moves = []
    require(max_moves == len(base_pp), "move fixture does not match authenticated MAX_MON_MOVES")
    for slot in range(max_moves):
        if slot < move_count:
            moves.append(Move(slot + 1, base_pp[slot], pp_ups[slot], slot))
        else:
            # Empty move slots are deliberately nonzero to prove RestoreBoxMonPP leaves them alone.
            moves.append(Move(0, base_pp[slot], 0, 61 + slot))
    return BoxMon(tuple(moves))


def verify_semantics(num_boxes: int, max_moves: int) -> tuple[int, int]:
    representative = move_fixture(max_moves, (0, 1, 2, 3), max_moves)
    initial_flags = 0x15555555 & ((1 << num_boxes) - 1)
    traversal_cases = 0

    # Each possible first-empty distance is a complete traversal equivalence class:
    # only the full/empty status of boxes up to the first empty box is observable.
    for start in range(num_boxes):
        for distance in range(num_boxes):
            full_boxes = 0
            for step in range(distance):
                full_boxes |= 1 << ((start + step) % num_boxes)
            compare_case(full_boxes, start, representative, initial_flags, num_boxes)
            traversal_cases += 1
        compare_case((1 << num_boxes) - 1, start, representative, initial_flags, num_boxes)
        traversal_cases += 1

    move_cases = 0
    for move_count in range(max_moves + 1):
        for ups in itertools.product(range(4), repeat=move_count):
            padded_ups = ups + (0,) * (max_moves - move_count)
            mon = move_fixture(move_count, padded_ups, max_moves)
            # Current-box success, a wraparound success, and completely full storage.
            compare_case(0, 7, mon, 0, num_boxes)
            wrap_full = (1 << (num_boxes - 1)) | 1
            compare_case(wrap_full, num_boxes - 1, mon, 0x24, num_boxes)
            compare_case((1 << num_boxes) - 1, 11, mon, 0x24, num_boxes)
            move_cases += 3

    return traversal_cases, move_cases


def expect_rejected(action, label: str) -> None:
    try:
        action()
    except VerificationError:
        return
    fail(f"adversarial fixture was accepted: {label}")


def expect_accepted(action, label: str) -> None:
    try:
        action()
    except VerificationError as error:
        fail(f"valid active-preprocessor fixture was rejected ({label}): {error}")


def disable_define(source: str, name: str) -> str:
    mutated, count = re.subn(
        rf"^(\s*)#\s*define\s+{name}\b.*$",
        rf"\1// adversarially disabled {name}",
        source,
        count=1,
        flags=re.MULTILINE,
    )
    require(count == 1, f"could not construct disabled-{name} fixture")
    return mutated


def mutate_integer_define(source: str, name: str, replacement: int) -> str:
    mutated, count = re.subn(
        rf"(^\s*#\s*define\s+{name}\s+)[^\s/]+",
        rf"\g<1>{replacement}",
        source,
        count=1,
        flags=re.MULTILINE,
    )
    require(count == 1, f"could not construct {name}-drift fixture")
    return mutated


def replace_define(source: str, name: str, replacement: str) -> str:
    mutated, count = re.subn(
        rf"^\s*#\s*define\s+{name}\b.*$",
        replacement,
        source,
        count=1,
        flags=re.MULTILINE,
    )
    require(count == 1, f"could not construct {name} preprocessor fixture")
    return mutated


def verify_adversarial_fixtures(
    storage_source: str,
    config_source: str,
    save_constants: str,
    party_header: str,
    arm9: bytes,
    linker_script: str,
    config_macros: dict[str, str],
    max_moves: int,
) -> int:
    fixtures = 0
    for name in ("ALLOW_SAVE_CHANGES", "EXPAND_PC_BOXES"):
        expect_rejected(
            lambda name=name: verify_configuration(
                disable_define(config_source, name), save_constants, party_header
            ),
            f"disabled production config {name}",
        )
        fixtures += 1

    if_zero_feature = replace_define(
        config_source,
        "ALLOW_SAVE_CHANGES",
        "#if 0\n#define ALLOW_SAVE_CHANGES\n#endif",
    )
    expect_rejected(
        lambda: verify_configuration(if_zero_feature, save_constants, party_header),
        "required feature defined only inside #if 0",
    )
    fixtures += 1

    undefined_feature = replace_define(
        config_source,
        "EXPAND_PC_BOXES",
        "#if 1\n#define EXPAND_PC_BOXES\n#else\n"
        "#define ADVERSARIAL_OTHER_BRANCH\n#endif\n#undef EXPAND_PC_BOXES",
    )
    expect_rejected(
        lambda: verify_configuration(undefined_feature, save_constants, party_header),
        "required feature removed by active #undef after a branch",
    )
    fixtures += 1

    inactive_body = storage_source.replace(
        "#ifdef ALLOW_SAVE_CHANGES", "#ifdef ADVERSARIAL_DISABLED_BODY", 1
    )
    require(inactive_body != storage_source, "could not construct inactive-body fixture")
    expect_rejected(
        lambda: verify_source(
            evaluate_preprocessor(inactive_body, config_macros, True)[0]
        ),
        "reviewed function exists only in an inactive conditional body",
    )
    fixtures += 1


    inactive_reviewed_then_active_wrong = replace_define(
        save_constants,
        "NUM_PC_BOXES",
        f"#if 0\n#define NUM_PC_BOXES {EXPECTED_NUM_PC_BOXES}\n"
        f"#elif 1\n#define NUM_PC_BOXES {EXPECTED_NUM_PC_BOXES - 1}\n#endif",
    )
    expect_rejected(
        lambda: verify_configuration(
            config_source, inactive_reviewed_then_active_wrong, party_header
        ),
        "inactive reviewed NUM_PC_BOXES shadow before a different active value",
    )
    fixtures += 1

    inactive_wrong_then_active_reviewed = replace_define(
        save_constants,
        "NUM_PC_BOXES",
        f"#if 0\n#define NUM_PC_BOXES {EXPECTED_NUM_PC_BOXES - 1}\n#endif\n"
        f"#define NUM_PC_BOXES {EXPECTED_NUM_PC_BOXES}",
    )
    expect_accepted(
        lambda: verify_configuration(
            config_source, inactive_wrong_then_active_reviewed, party_header
        ),
        "inactive integer shadow is ignored",
    )
    fixtures += 1

    conflicting_active_constants = replace_define(
        save_constants,
        "NUM_PC_BOXES",
        f"#define NUM_PC_BOXES {EXPECTED_NUM_PC_BOXES}\n"
        f"#define NUM_PC_BOXES {EXPECTED_NUM_PC_BOXES - 1}",
    )
    expect_rejected(
        lambda: verify_configuration(
            config_source, conflicting_active_constants, party_header
        ),
        "conflicting active NUM_PC_BOXES definitions",
    )
    fixtures += 1

    undef_then_reviewed = replace_define(
        save_constants,
        "NUM_PC_BOXES",
        f"#define NUM_PC_BOXES {EXPECTED_NUM_PC_BOXES - 1}\n"
        f"#undef NUM_PC_BOXES\n#define NUM_PC_BOXES {EXPECTED_NUM_PC_BOXES}",
    )
    expect_accepted(
        lambda: verify_configuration(config_source, undef_then_reviewed, party_header),
        "an active #undef permits a later reviewed definition",
    )
    fixtures += 1

    expect_rejected(
        lambda: verify_configuration(
            config_source,
            mutate_integer_define(save_constants, "NUM_PC_BOXES", EXPECTED_NUM_PC_BOXES - 1),
            party_header,
        ),
        "NUM_PC_BOXES drift",
    )
    fixtures += 1
    expect_rejected(
        lambda: verify_configuration(
            config_source,
            save_constants,
            mutate_integer_define(party_header, "MAX_MON_MOVES", EXPECTED_MAX_MON_MOVES + 1),
        ),
        "MAX_MON_MOVES drift",
    )
    fixtures += 1

    modified_helper = storage_source.replace(
        "storage->boxModifiedFlag |= 1 << boxno;",
        "storage->boxModifiedFlag = 1 << boxno;",
        1,
    )
    require(modified_helper != storage_source, "could not construct modified-flag helper fixture")
    expect_rejected(
        lambda: verify_source(
            evaluate_preprocessor(modified_helper, config_macros, True)[0]
        ),
        "non-idempotent PCStorage_SetBoxModified helper",
    )
    fixtures += 1

    restore_address = linker_thumb_symbol(linker_script, "RestoreBoxMonPP")
    restore_offset = restore_address - ARM9_BASE
    mutated_arm9 = bytearray(arm9)
    require(
        0 <= restore_offset + 0x3E < len(mutated_arm9),
        "could not construct RestoreBoxMonPP machine fixture",
    )
    mutated_arm9[restore_offset + 0x3E] ^= 1
    expect_rejected(
        lambda: verify_restore_box_pp_machine(bytes(mutated_arm9), linker_script, max_moves),
        "RestoreBoxMonPP helper drift",
    )
    fixtures += 1
    return fixtures


def mutate_elf_range(elf: bytes, address: int, replacement: bytes) -> bytes:
    mutated = bytearray(elf)
    offset = elf_virtual_file_offset(elf, address, len(replacement))
    mutated[offset : offset + len(replacement)] = replacement
    return bytes(mutated)


def verify_artifact_adversarial_fixtures(
    linked_elf: bytes,
    symbols: dict[str, tuple[int, int]],
    core: bytes,
    packaged_overlay: bytes,
    overlay_table: bytes,
    arm9: bytes,
    hooks_source: str,
    linker_script: str,
) -> int:
    outer_address = symbols["PCStorage_PlaceMonInFirstEmptySlotInAnyBox"][0]
    inner_address = symbols["PCStorage_PlaceMonInBoxFirstEmptySlot"][0]
    memcpy_address = symbols["memcpy"][0]
    restore_address = linker_thumb_symbol(linker_script, "RestoreBoxMonPP")
    get_box_data = linker_thumb_symbol(linker_script, "GetBoxMonData")
    core_address, _linked_flat = elf_flat_binary(linked_elf)

    def coherent_machine_mutation(
        address: int, replacement: bytes
    ) -> tuple[bytes, bytes, bytes]:
        mutated_elf = mutate_elf_range(linked_elf, address, replacement)
        core_offset = address - core_address
        require(
            0 <= core_offset and core_offset + len(replacement) <= len(core),
            "coherent mutation is outside build/output.bin",
        )
        mutated_core = bytearray(core)
        mutated_core[core_offset : core_offset + len(replacement)] = replacement
        package_offset = OVERLAY_129_CORE_OFFSET + core_offset
        require(
            package_offset + len(replacement) <= len(packaged_overlay),
            "coherent mutation is outside packaged overlay 129",
        )
        mutated_package = bytearray(packaged_overlay)
        mutated_package[package_offset : package_offset + len(replacement)] = replacement
        return mutated_elf, bytes(mutated_core), bytes(mutated_package)

    def verify(
        elf: bytes = linked_elf,
        output: bytes = core,
        package: bytes = packaged_overlay,
        patched_arm9: bytes = arm9,
    ) -> None:
        verify_linked_and_packaged_artifacts(
            elf,
            symbols,
            output,
            package,
            overlay_table,
            patched_arm9,
            hooks_source,
            linker_script,
        )

    fixtures = 0
    wrong_outer_bl = mutate_elf_range(
        linked_elf,
        outer_address + 0x2A,
        encode_thumb_bl(outer_address + 0x2A, inner_address + 2),
    )
    expect_rejected(lambda: verify(elf=wrong_outer_bl), "outer BL targets wrong boundary")
    fixtures += 1

    wrong_inner_bl, wrong_inner_core, wrong_inner_package = coherent_machine_mutation(
        inner_address + 0x58,
        encode_thumb_bl(inner_address + 0x58, memcpy_address + 2),
    )
    expect_rejected(
        lambda: verify(
            elf=wrong_inner_bl,
            output=wrong_inner_core,
            package=wrong_inner_package,
        ),
        "coherent inner memcpy BL target drift",
    )
    fixtures += 1

    extra_outer_restore = mutate_elf_range(
        linked_elf,
        outer_address + 0x24,
        encode_thumb_bl(outer_address + 0x24, restore_address),
    )
    expect_rejected(
        lambda: verify(elf=extra_outer_restore),
        "outer call replaced by redundant RestoreBoxMonPP",
    )
    fixtures += 1

    missing_inner_restore = mutate_elf_range(
        linked_elf, inner_address + 0x78, struct.pack("<I", get_box_data | 1)
    )
    expect_rejected(
        lambda: verify(elf=missing_inner_restore), "inner RestoreBoxMonPP call removed"
    )
    fixtures += 1

    extra_inner_restore = mutate_elf_range(
        linked_elf, inner_address + 0x88, struct.pack("<I", restore_address | 1)
    )
    expect_rejected(
        lambda: verify(elf=extra_inner_restore), "inner gained a second RestoreBoxMonPP call"
    )
    fixtures += 1

    hook_address, _hook_register = hook_declaration(hooks_source)
    hook_offset = hook_address - ARM9_BASE
    drifted_arm9 = bytearray(arm9)
    drifted_arm9[hook_offset] ^= 1
    expect_rejected(
        lambda: verify(patched_arm9=bytes(drifted_arm9)), "ARM9 AnyBox hook drift"
    )
    fixtures += 1

    relocated_hook_address = 0x02073BC0
    relocated_hooks_source, replacement_count = re.subn(
        r"^(arm9\s+PCStorage_PlaceMonInFirstEmptySlotInAnyBox\s+)02073BB8(\s+2\s*)$",
        rf"\g<1>{relocated_hook_address:08X}\g<2>",
        hooks_source,
        count=1,
        flags=re.MULTILINE,
    )
    require(replacement_count == 1, "could not construct coordinated hook relocation fixture")
    relocated_arm9 = bytearray(arm9)
    relocated_offset = relocated_hook_address - ARM9_BASE
    relocated_arm9[relocated_offset : relocated_offset + 8] = struct.pack(
        "<HHI", 0x4A00, 0x4710, outer_address | 1
    )
    expect_rejected(
        lambda: verify_linked_and_packaged_artifacts(
            linked_elf,
            symbols,
            core,
            packaged_overlay,
            overlay_table,
            bytes(relocated_arm9),
            relocated_hooks_source,
            linker_script,
        ),
        "coordinated hooks declaration and valid veneer relocation away from stock entry",
    )
    fixtures += 1

    mismatched_package = bytearray(packaged_overlay)
    mismatched_package[OVERLAY_129_CORE_OFFSET] ^= 1
    expect_rejected(
        lambda: verify(package=bytes(mismatched_package)),
        "linked output/package mismatch",
    )
    fixtures += 1
    return fixtures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("src/pokemon_storage_system.c"),
        help="pokemon storage implementation to verify",
    )
    parser.add_argument("--config", type=Path, default=Path("include/config.h"))
    parser.add_argument(
        "--save-constants", type=Path, default=Path("include/constants/save.h")
    )
    parser.add_argument("--party-header", type=Path, default=Path("include/party_menu.h"))
    parser.add_argument("--arm9", type=Path, default=Path("base/arm9.bin"))
    parser.add_argument("--linker-script", type=Path, default=Path("rom.ld"))
    parser.add_argument("--hooks", type=Path, default=Path("hooks"))
    parser.add_argument("--linked-object", type=Path, default=Path("build/linked.o"))
    parser.add_argument("--core-binary", type=Path, default=Path("build/output.bin"))
    parser.add_argument(
        "--packaged-overlay129",
        type=Path,
        default=Path("base/overlay/overlay_0129.bin"),
    )
    parser.add_argument(
        "--overlay-table", type=Path, default=Path("base/overarm9.bin")
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        for path in (
            args.source,
            args.config,
            args.save_constants,
            args.party_header,
            args.arm9,
            args.linker_script,
            args.hooks,
            args.linked_object,
            args.core_binary,
            args.packaged_overlay129,
            args.overlay_table,
        ):
            require(path.is_file(), f"required input is missing: {path}")
        storage_source = args.source.read_text(encoding="utf-8")
        config_source = args.config.read_text(encoding="utf-8")
        save_constants = args.save_constants.read_text(encoding="utf-8")
        party_header = args.party_header.read_text(encoding="utf-8")
        arm9 = args.arm9.read_bytes()
        linker_script = args.linker_script.read_text(encoding="utf-8")
        hooks_source = args.hooks.read_text(encoding="utf-8")
        linked_elf = args.linked_object.read_bytes()
        symbols = linked_symbols(args.linked_object)
        core = args.core_binary.read_bytes()
        packaged_overlay = args.packaged_overlay129.read_bytes()
        overlay_table = args.overlay_table.read_bytes()

        config_macros, num_boxes, max_moves = verify_configuration(
            config_source, save_constants, party_header
        )
        active_source, _storage_macros = evaluate_preprocessor(
            storage_source, config_macros, True
        )
        verify_source(active_source)
        verify_restore_box_pp_machine(arm9, linker_script, max_moves)
        verify_linked_and_packaged_artifacts(
            linked_elf,
            symbols,
            core,
            packaged_overlay,
            overlay_table,
            arm9,
            hooks_source,
            linker_script,
        )
        traversal_cases, move_cases = verify_semantics(num_boxes, max_moves)
        adversarial_cases = verify_adversarial_fixtures(
            storage_source,
            config_source,
            save_constants,
            party_header,
            arm9,
            linker_script,
            config_macros,
            max_moves,
        )
        artifact_adversarial_cases = verify_artifact_adversarial_fixtures(
            linked_elf,
            symbols,
            core,
            packaged_overlay,
            overlay_table,
            arm9,
            hooks_source,
            linker_script,
        )
        print(
            "PC storage AnyBox verification passed: "
            f"active {num_boxes}-box/{max_moves}-move production config, "
            f"{traversal_cases} traversal cases, {move_cases} move/PP-Up cases, "
            f"{adversarial_cases} preprocessor/helper fixtures, and "
            f"{artifact_adversarial_cases} linked/package mutation fixtures"
        )
    except VerificationError as error:
        raise SystemExit(f"PC storage AnyBox verification failed: {error}") from error


if __name__ == "__main__":
    main()
