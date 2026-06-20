#!/usr/bin/env python3
"""Build and validate the pointerless OWBD resource."""

from __future__ import annotations

import argparse
import ast
import json
import re
import struct
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_overworld_wild_behavior_data import (
    DEFAULT_INPUT,
    DEFAULT_OUTPUT,
    MATCH_FIELDS,
    OVERRIDE_MASKS,
    PROFILE_FIELDS,
    emit_generated_c,
    import_c_source,
    load_profiles,
)

ROOT = Path(__file__).resolve().parents[1]
MAGIC = b"OWBD"
VERSION = 1
HEADER_FORMAT = "<4sHHIIHHHHIIIIHHHHI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
CHECKSUM_OFFSET = struct.calcsize("<4sHHIIHHHHIIIIHHHH")
CHECKSUM_SIZE = 4
PROFILE_FORMAT = "<" + "B" * len(PROFILE_FIELDS)
PROFILE_SIZE = struct.calcsize(PROFILE_FORMAT)
MATCH_FORMAT = "<I H B B B B B x"
MATCH_SIZE = struct.calcsize(MATCH_FORMAT)
# These formats intentionally preserve nested C struct padding.
CLASS_RULE_FORMAT = "<I H B B B B B x B 3x"
CLASS_RULE_SIZE = struct.calcsize(CLASS_RULE_FORMAT)
SPECIES_RULE_FORMAT = "<H B x"
SPECIES_RULE_SIZE = struct.calcsize(SPECIES_RULE_FORMAT)
OVERRIDE_FORMAT = "<I H B B B B B x I H 2x I " + ("B" * len(PROFILE_FIELDS)) + "2x"
OVERRIDE_SIZE = struct.calcsize(OVERRIDE_FORMAT)
EXPECTED_C_ABI_SIZES = {
    "profiles": 66,
    "matches": 12,
    "class_rules": 16,
    "species_rules": 4,
    "variable_overrides": 92,
}
EXPECTED_SECTION_SIZES = {
    "profiles": PROFILE_SIZE,
    "class_rules": CLASS_RULE_SIZE,
    "species_rules": SPECIES_RULE_SIZE,
    "variable_overrides": OVERRIDE_SIZE,
}
MAX_SECTION_COUNTS = {
    "profiles": 8,
    "class_rules": 2,
    "species_rules": 110,
    "variable_overrides": 2,
}

SECTION_NAMES = (
    "profiles",
    "class_rules",
    "species_rules",
    "variable_overrides",
)


class OwbdError(ValueError):
    pass


def assert_codec_abi_sizes() -> None:
    actual = {
        "profiles": PROFILE_SIZE,
        "matches": MATCH_SIZE,
        "class_rules": CLASS_RULE_SIZE,
        "species_rules": SPECIES_RULE_SIZE,
        "variable_overrides": OVERRIDE_SIZE,
    }
    if actual != EXPECTED_C_ABI_SIZES:
        raise OwbdError(f"OWBD codec ABI size mismatch: {actual} != {EXPECTED_C_ABI_SIZES}")


class ConstantResolver:
    def __init__(self) -> None:
        self.defines: dict[str, str] = {}
        self.cache: dict[str, int] = {}

    def load_file(self, path: Path) -> None:
        text = path.read_text()
        define_re = re.compile(r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+(.*?))?\s*$")
        for raw_line in text.splitlines():
            line = raw_line.split("//", 1)[0].strip()
            match = define_re.match(line)
            if match is None:
                continue
            name, value = match.groups()
            if "(" in name:
                continue
            if value is None or not value.strip():
                continue
            self.defines[name] = value.strip()
        self._load_enums(text)

    def _load_enums(self, text: str) -> None:
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"//.*", "", text)
        for match in re.finditer(r"\benum(?:\s+[A-Za-z_][A-Za-z0-9_]*)?\s*{(.*?)}", text, re.S):
            value = -1
            for raw_item in match.group(1).split(","):
                item = raw_item.strip()
                if not item:
                    continue
                if "=" in item:
                    name, expr = [part.strip() for part in item.split("=", 1)]
                    value = self._resolve_expr(expr)
                else:
                    name = item
                    value += 1
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                    self.defines.setdefault(name, str(value))

    def resolve(self, value: object, label: str) -> int:
        if isinstance(value, int):
            resolved = value
        elif isinstance(value, str):
            resolved = self._resolve_expr(value)
        else:
            raise OwbdError(f"{label}: unsupported value {value!r}")

        if resolved < 0:
            raise OwbdError(f"{label}: negative value {resolved}")
        return resolved

    def _resolve_expr(self, expr: str) -> int:
        expr = expr.strip()
        if not expr:
            raise OwbdError("empty constant expression")
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", expr):
            return self._resolve_name(expr)

        clean = re.sub(r"\b(\d+)[uUlL]+\b", r"\1", expr)
        try:
            tree = ast.parse(clean, mode="eval")
        except SyntaxError as exc:
            raise OwbdError(f"unsupported constant expression {expr!r}") from exc
        return self._eval_ast(tree.body)

    def _resolve_name(self, name: str) -> int:
        if name in self.cache:
            return self.cache[name]
        if name not in self.defines:
            raise OwbdError(f"unknown constant token {name}")
        self.cache[name] = self._eval_ast(ast.parse("0", mode="eval").body)
        value = self._resolve_expr(self.defines[name])
        self.cache[name] = value
        return value

    def _eval_ast(self, node: ast.AST) -> int:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name):
            return self._resolve_name(node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -self._eval_ast(node.operand)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
            return self._eval_ast(node.operand)
        if isinstance(node, ast.BinOp):
            left = self._eval_ast(node.left)
            right = self._eval_ast(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
            if isinstance(node.op, ast.Div):
                if left % right != 0:
                    raise OwbdError("non-integral division in constant expression")
                return left // right
            if isinstance(node.op, ast.LShift):
                return left << right
            if isinstance(node.op, ast.RShift):
                return left >> right
            if isinstance(node.op, ast.BitOr):
                return left | right
            if isinstance(node.op, ast.BitAnd):
                return left & right
        raise OwbdError(f"unsupported constant expression node {ast.dump(node)}")


def default_resolver() -> ConstantResolver:
    resolver = ConstantResolver()
    for path in (
        ROOT / "include/constants/species.h",
        ROOT / "include/overworld_wild_behavior_data.h",
        ROOT / "src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c",
    ):
        resolver.load_file(path)
    return resolver


def require_u8(value: int, label: str) -> int:
    if value > 0xFF:
        raise OwbdError(f"{label}: value {value} exceeds u8")
    return value


def require_u16(value: int, label: str) -> int:
    if value > 0xFFFF:
        raise OwbdError(f"{label}: value {value} exceeds u16")
    return value


def normalize_profile(profile: dict[str, object], resolver: ConstantResolver, label: str) -> list[int]:
    return [
        require_u8(resolver.resolve(profile[field], f"{label}.{field}"), f"{label}.{field}")
        for field in PROFILE_FIELDS
    ]


def normalize_match(match: dict[str, object], resolver: ConstantResolver, label: str) -> tuple[int, int, int, int, int, int, int]:
    return (
        resolver.resolve(match["groupMask"], f"{label}.groupMask"),
        require_u16(resolver.resolve(match["species"], f"{label}.species"), f"{label}.species"),
        require_u8(resolver.resolve(match["terrain"], f"{label}.terrain"), f"{label}.terrain"),
        require_u8(resolver.resolve(match["minLevel"], f"{label}.minLevel"), f"{label}.minLevel"),
        require_u8(resolver.resolve(match["maxLevel"], f"{label}.maxLevel"), f"{label}.maxLevel"),
        require_u8(resolver.resolve(match["shiny"], f"{label}.shiny"), f"{label}.shiny"),
        require_u8(
            resolver.resolve(match["behaviorClass"], f"{label}.behaviorClass"),
            f"{label}.behaviorClass",
        ),
    )


def empty_profile() -> dict[str, int]:
    return {field: 0 for field in PROFILE_FIELDS}


def normalize_data(data: dict[str, object], resolver: ConstantResolver) -> dict[str, object]:
    class_profiles = [
        {
            "profile": normalize_profile(entry["profile"], resolver, f"classProfiles[{index}].profile")
        }
        for index, entry in enumerate(data["classProfiles"])
    ]

    class_rules = [
        {
            "match": normalize_match(entry["match"], resolver, f"classRules[{index}].match"),
            "behaviorClass": require_u8(
                resolver.resolve(entry["behaviorClass"], f"classRules[{index}].behaviorClass"),
                f"classRules[{index}].behaviorClass",
            ),
        }
        for index, entry in enumerate(data["classRules"])
    ]

    species_rules = [
        {
            "species": require_u16(
                resolver.resolve(entry["species"], f"speciesClassRules[{index}].species"),
                f"speciesClassRules[{index}].species",
            ),
            "behaviorClass": require_u8(
                resolver.resolve(entry["behaviorClass"], f"speciesClassRules[{index}].behaviorClass"),
                f"speciesClassRules[{index}].behaviorClass",
            ),
        }
        for index, entry in enumerate(data["speciesClassRules"])
    ]

    overrides = []
    for index, entry in enumerate(data["overrides"]):
        masks = {"mask": 0, "mask2": 0, "mask3": 0}
        profile = empty_profile()
        for field, value in entry["fields"].items():
            mask_name, macro = OVERRIDE_MASKS[field]
            masks[mask_name] |= resolver.resolve(macro, f"overrides[{index}].{field}.mask")
            profile[field] = require_u8(
                resolver.resolve(value, f"overrides[{index}].fields.{field}"),
                f"overrides[{index}].fields.{field}",
            )

        overrides.append(
            {
                "match": normalize_match(entry["match"], resolver, f"overrides[{index}].match"),
                "mask": masks["mask"],
                "mask2": masks["mask2"],
                "mask3": masks["mask3"],
                "profile": [profile[field] for field in PROFILE_FIELDS],
            }
        )

    return {
        "schemaVersion": 1,
        "classProfiles": class_profiles,
        "classRules": class_rules,
        "speciesClassRules": species_rules,
        "overrides": overrides,
    }


def checksum_for(blob: bytes) -> int:
    checksum_end = CHECKSUM_OFFSET + CHECKSUM_SIZE
    if len(blob) < checksum_end:
        raise OwbdError("OWBD blob is too small to contain a checksum field")
    work = bytearray(blob)
    work[CHECKSUM_OFFSET:checksum_end] = b"\0" * CHECKSUM_SIZE
    return zlib.crc32(work) & 0xFFFFFFFF


def pack_header(
    *,
    total_size: int = HEADER_SIZE,
    payload_size: int = 0,
    counts: tuple[int, int, int, int] = (0, 0, 0, 0),
    offsets: tuple[int, int, int, int] = (0, 0, 0, 0),
    element_sizes: tuple[int, int, int, int] = (0, 0, 0, 0),
    checksum: int = 0,
) -> bytes:
    return struct.pack(
        HEADER_FORMAT,
        MAGIC,
        VERSION,
        HEADER_SIZE,
        total_size,
        payload_size,
        *counts,
        *offsets,
        *element_sizes,
        checksum,
    )


def build_dummy_blob() -> bytes:
    blob = pack_header()
    return pack_header(checksum=checksum_for(blob))


def build_probe_blob(payload: bytes | None = None) -> bytes:
    if payload is None:
        payload = bytes(range(PROFILE_SIZE))
    if len(payload) != PROFILE_SIZE:
        raise OwbdError(f"probe payload must be {PROFILE_SIZE} bytes")
    blob = (
        pack_header(
            total_size=HEADER_SIZE + len(payload),
            payload_size=len(payload),
            counts=(1, 0, 0, 0),
            offsets=(HEADER_SIZE, 0, 0, 0),
            element_sizes=(PROFILE_SIZE, 0, 0, 0),
        )
        + payload
    )
    return (
        pack_header(
            total_size=len(blob),
            payload_size=len(payload),
            counts=(1, 0, 0, 0),
            offsets=(HEADER_SIZE, 0, 0, 0),
            element_sizes=(PROFILE_SIZE, 0, 0, 0),
            checksum=checksum_for(blob),
        )
        + payload
    )


def align4(data: bytearray) -> None:
    while len(data) % 4 != 0:
        data.append(0)


def section_offset(payload: bytearray, counts: list[int], index: int) -> int:
    if counts[index] == 0:
        return 0
    return HEADER_SIZE + len(payload)


def build_blob_from_data(data: dict[str, object], resolver: ConstantResolver | None = None) -> bytes:
    assert_codec_abi_sizes()
    resolver = resolver or default_resolver()
    normalized = normalize_data(data, resolver)
    count_by_section = {
        "profiles": len(normalized["classProfiles"]),
        "class_rules": len(normalized["classRules"]),
        "species_rules": len(normalized["speciesClassRules"]),
        "variable_overrides": len(normalized["overrides"]),
    }
    for name, count in count_by_section.items():
        if count > MAX_SECTION_COUNTS[name]:
            raise OwbdError(
                f"{name} count {count} exceeds fixed OWBD decode capacity "
                f"{MAX_SECTION_COUNTS[name]}"
            )
    counts = [count_by_section[name] for name in SECTION_NAMES]
    element_sizes = [
        PROFILE_SIZE if count_by_section["profiles"] else 0,
        CLASS_RULE_SIZE if count_by_section["class_rules"] else 0,
        SPECIES_RULE_SIZE if count_by_section["species_rules"] else 0,
        OVERRIDE_SIZE if count_by_section["variable_overrides"] else 0,
    ]
    payload = bytearray()
    offsets: list[int] = []

    offsets.append(section_offset(payload, counts, 0))
    for entry in normalized["classProfiles"]:
        payload.extend(struct.pack(PROFILE_FORMAT, *entry["profile"]))
    align4(payload)

    offsets.append(section_offset(payload, counts, 1))
    for entry in normalized["classRules"]:
        payload.extend(struct.pack(CLASS_RULE_FORMAT, *entry["match"], entry["behaviorClass"]))
    align4(payload)

    offsets.append(section_offset(payload, counts, 2))
    for entry in normalized["speciesClassRules"]:
        payload.extend(struct.pack(SPECIES_RULE_FORMAT, entry["species"], entry["behaviorClass"]))
    align4(payload)

    offsets.append(section_offset(payload, counts, 3))
    for entry in normalized["overrides"]:
        payload.extend(
            struct.pack(
                OVERRIDE_FORMAT,
                *entry["match"],
                entry["mask"],
                entry["mask2"],
                entry["mask3"],
                *entry["profile"],
            )
        )
    align4(payload)

    blob = pack_header(
        total_size=HEADER_SIZE + len(payload),
        payload_size=len(payload),
        counts=tuple(counts),
        offsets=tuple(offsets),
        element_sizes=tuple(element_sizes),
    ) + bytes(payload)
    return pack_header(
        total_size=len(blob),
        payload_size=len(payload),
        counts=tuple(counts),
        offsets=tuple(offsets),
        element_sizes=tuple(element_sizes),
        checksum=checksum_for(blob),
    ) + bytes(payload)


def build_blob_from_json(path: Path) -> bytes:
    return build_blob_from_data(load_profiles(path))


def read_header(blob: bytes) -> dict[str, object]:
    if len(blob) < HEADER_SIZE:
        raise OwbdError(f"OWBD blob is {len(blob)} bytes, expected at least {HEADER_SIZE}")

    (
        magic,
        version,
        header_size,
        total_size,
        payload_size,
        profile_count,
        class_rule_count,
        species_rule_count,
        variable_override_count,
        profiles_offset,
        class_rules_offset,
        species_rules_offset,
        variable_overrides_offset,
        profile_size,
        class_rule_size,
        species_rule_size,
        variable_override_size,
        checksum,
    ) = struct.unpack_from(HEADER_FORMAT, blob)

    return {
        "magic": magic,
        "version": version,
        "header_size": header_size,
        "total_size": total_size,
        "payload_size": payload_size,
        "counts": {
            "profiles": profile_count,
            "class_rules": class_rule_count,
            "species_rules": species_rule_count,
            "variable_overrides": variable_override_count,
        },
        "offsets": {
            "profiles": profiles_offset,
            "class_rules": class_rules_offset,
            "species_rules": species_rules_offset,
            "variable_overrides": variable_overrides_offset,
        },
        "element_sizes": {
            "profiles": profile_size,
            "class_rules": class_rule_size,
            "species_rules": species_rule_size,
            "variable_overrides": variable_override_size,
        },
        "checksum": checksum,
    }


def validate_blob(blob: bytes) -> dict[str, object]:
    assert_codec_abi_sizes()
    header = read_header(blob)

    if header["magic"] != MAGIC:
        raise OwbdError(f"bad magic {header['magic']!r}; expected {MAGIC!r}")
    if header["version"] != VERSION:
        raise OwbdError(f"unsupported OWBD version {header['version']}; expected {VERSION}")
    if header["header_size"] != HEADER_SIZE:
        raise OwbdError(
            f"bad header size {header['header_size']}; expected {HEADER_SIZE}"
        )
    if header["total_size"] != len(blob):
        raise OwbdError(f"total size {header['total_size']} does not match {len(blob)}")
    if header["payload_size"] != len(blob) - HEADER_SIZE:
        raise OwbdError(
            f"payload size {header['payload_size']} does not match "
            f"{len(blob) - HEADER_SIZE}"
        )
    if header["checksum"] != checksum_for(blob):
        raise OwbdError("checksum mismatch")

    ranges: list[tuple[int, int, str]] = []
    counts = header["counts"]
    offsets = header["offsets"]
    element_sizes = header["element_sizes"]

    for name in SECTION_NAMES:
        count = int(counts[name])
        offset = int(offsets[name])
        element_size = int(element_sizes[name])

        if count > MAX_SECTION_COUNTS[name]:
            raise OwbdError(
                f"{name} count {count} exceeds fixed OWBD decode capacity "
                f"{MAX_SECTION_COUNTS[name]}"
            )
        if count == 0:
            if offset != 0:
                raise OwbdError(f"{name} offset must be 0 when count is 0")
            if element_size != 0:
                raise OwbdError(f"{name} element size must be 0 when count is 0")
            continue

        if element_size == 0:
            raise OwbdError(f"{name} element size must be non-zero when count is non-zero")
        if element_size != EXPECTED_SECTION_SIZES[name]:
            raise OwbdError(
                f"{name} element size {element_size} does not match codec size "
                f"{EXPECTED_SECTION_SIZES[name]}"
            )
        if offset < HEADER_SIZE:
            raise OwbdError(f"{name} offset {offset} is before the end of the header")
        if offset % 4 != 0:
            raise OwbdError(f"{name} offset {offset} is not 4-byte aligned")

        byte_count = count * element_size
        end = offset + byte_count
        if end > len(blob):
            raise OwbdError(f"{name} range {offset}..{end} exceeds blob size {len(blob)}")
        ranges.append((offset, end, name))

    ranges.sort()
    for (_, previous_end, previous_name), (next_start, _, next_name) in zip(
        ranges, ranges[1:]
    ):
        if next_start < previous_end:
            raise OwbdError(f"{previous_name} overlaps {next_name}")

    return header


def decode_blob(blob: bytes) -> dict[str, object]:
    header = validate_blob(blob)
    counts = header["counts"]
    offsets = header["offsets"]
    element_sizes = header["element_sizes"]

    expected_sizes = {
        "profiles": PROFILE_SIZE,
        "class_rules": CLASS_RULE_SIZE,
        "species_rules": SPECIES_RULE_SIZE,
        "variable_overrides": OVERRIDE_SIZE,
    }
    for name, expected_size in expected_sizes.items():
        if counts[name] and element_sizes[name] != expected_size:
            raise OwbdError(
                f"{name} element size {element_sizes[name]} does not match decoder size {expected_size}"
            )

    class_profiles = []
    for index in range(counts["profiles"]):
        offset = offsets["profiles"] + index * PROFILE_SIZE
        class_profiles.append({"profile": list(struct.unpack_from(PROFILE_FORMAT, blob, offset))})

    class_rules = []
    for index in range(counts["class_rules"]):
        offset = offsets["class_rules"] + index * CLASS_RULE_SIZE
        values = struct.unpack_from(CLASS_RULE_FORMAT, blob, offset)
        class_rules.append({"match": values[:7], "behaviorClass": values[7]})

    species_rules = []
    for index in range(counts["species_rules"]):
        offset = offsets["species_rules"] + index * SPECIES_RULE_SIZE
        species, behavior_class = struct.unpack_from(SPECIES_RULE_FORMAT, blob, offset)
        species_rules.append({"species": species, "behaviorClass": behavior_class})

    overrides = []
    for index in range(counts["variable_overrides"]):
        offset = offsets["variable_overrides"] + index * OVERRIDE_SIZE
        values = struct.unpack_from(OVERRIDE_FORMAT, blob, offset)
        overrides.append(
            {
                "match": values[:7],
                "mask": values[7],
                "mask2": values[8],
                "mask3": values[9],
                "profile": list(values[10:]),
            }
        )

    return {
        "schemaVersion": 1,
        "classProfiles": class_profiles,
        "classRules": class_rules,
        "speciesClassRules": species_rules,
        "overrides": overrides,
    }


def generated_c_model(data: dict[str, object], resolver: ConstantResolver) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "overworld_wild_behavior_profiles.generated.inc"
        path.write_text(emit_generated_c(data))
        return normalize_data(import_c_source(path), resolver)


def checked_in_c_model(source_json: Path, resolver: ConstantResolver) -> dict[str, object] | None:
    if source_json.resolve() != DEFAULT_INPUT.resolve():
        return None
    if not DEFAULT_OUTPUT.exists():
        raise OwbdError(f"checked-in generated C include is missing: {DEFAULT_OUTPUT}")
    return normalize_data(import_c_source(DEFAULT_OUTPUT), resolver)


def validate_roundtrip(blob: bytes, source_json: Path) -> dict[str, object]:
    resolver = default_resolver()
    source = load_profiles(source_json)
    expected = normalize_data(source, resolver)
    decoded = decode_blob(blob)
    generated = generated_c_model(source, resolver)
    checked_in = checked_in_c_model(source_json, resolver)

    if decoded != expected:
        raise OwbdError("OWBD decoded model does not match JSON model")
    if decoded != generated:
        raise OwbdError("OWBD decoded model does not match generated C compatibility model")
    if checked_in is not None and decoded != checked_in:
        raise OwbdError("OWBD decoded model does not match checked-in generated C include")
    return decoded


def write_blob(output: Path, source_json: Path) -> None:
    blob = build_blob_from_json(source_json)
    validate_blob(blob)
    validate_roundtrip(blob, source_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(blob)
    print(f"wrote {output} ({len(blob)} bytes)")


def validate_path(path: Path, dump_json: bool, source_json: Path | None) -> None:
    blob = path.read_bytes()
    header = validate_blob(blob)
    decode_blob(blob)
    if source_json is not None:
        validate_roundtrip(blob, source_json)
    if dump_json:
        printable = {
            **header,
            "magic": header["magic"].decode("ascii"),
        }
        print(json.dumps(printable, indent=2, sort_keys=True))
    else:
        print(f"validated {path} ({header['total_size']} bytes)")


def run_probe() -> None:
    blob = build_probe_blob()
    header = validate_blob(blob)
    checksum_end = CHECKSUM_OFFSET + CHECKSUM_SIZE
    if checksum_end == len(blob):
        raise OwbdError("probe checksum field unexpectedly sits at EOF")

    mutated = bytearray(blob)
    mutated[-1] ^= 0xFF
    try:
        validate_blob(mutated)
    except OwbdError as exc:
        if "checksum mismatch" not in str(exc):
            raise
    else:
        raise OwbdError("probe accepted a payload mutation")

    trailing_zero_blob = build_probe_blob(bytes(range(PROFILE_SIZE - 4)) + b"\0\0\0\0")
    trailing_zero_header = validate_blob(trailing_zero_blob)
    old_style_checksum = zlib.crc32(trailing_zero_blob[:-4] + b"\0\0\0\0") & 0xFFFFFFFF
    if old_style_checksum == trailing_zero_header["checksum"]:
        raise OwbdError("probe checksum is still compatible with zeroing the last 4 bytes")

    malformed_cases = []
    malformed_cases.append((b"\0" * (HEADER_SIZE - 1), "expected at least"))
    bad_magic = bytearray(blob)
    bad_magic[0:4] = b"BAD!"
    malformed_cases.append((bad_magic, "bad magic"))
    bad_total = bytearray(blob)
    struct.pack_into("<I", bad_total, struct.calcsize("<4sHH"), len(blob) + 4)
    malformed_cases.append((bad_total, "total size"))
    bad_offset = bytearray(blob)
    struct.pack_into("<I", bad_offset, struct.calcsize("<4sHHIIHHHH"), HEADER_SIZE + 1)
    struct.pack_into("<I", bad_offset, CHECKSUM_OFFSET, checksum_for(bad_offset))
    malformed_cases.append((bad_offset, "not 4-byte aligned"))
    bad_range = bytearray(blob)
    struct.pack_into("<I", bad_range, struct.calcsize("<4sHHIIHHHH"), (len(blob) + 3) & ~3)
    struct.pack_into("<I", bad_range, CHECKSUM_OFFSET, checksum_for(bad_range))
    malformed_cases.append((bad_range, "exceeds blob size"))

    for malformed, expected in malformed_cases:
        try:
            validate_blob(bytes(malformed))
        except OwbdError as exc:
            if expected not in str(exc):
                raise
        else:
            raise OwbdError(f"probe accepted malformed blob expected to fail with {expected!r}")

    print(
        "validated non-empty OWBD probe "
        f"({header['total_size']} bytes, checksum offset {CHECKSUM_OFFSET})"
    )


def run_roundtrip(source_json: Path) -> None:
    blob = build_blob_from_json(source_json)
    decoded = validate_roundtrip(blob, source_json)
    print(
        "validated OWBD roundtrip "
        f"({len(blob)} bytes, "
        f"{len(decoded['classProfiles'])} profiles, "
        f"{len(decoded['classRules'])} class rules, "
        f"{len(decoded['speciesClassRules'])} species rules, "
        f"{len(decoded['overrides'])} overrides)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="write the OWBD blob")
    build_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    build_parser.add_argument("--output", required=True, type=Path)

    validate_parser = subparsers.add_parser("validate", help="validate an OWBD blob")
    validate_parser.add_argument("path", type=Path)
    validate_parser.add_argument("--json", action="store_true", help="dump parsed header")
    validate_parser.add_argument(
        "--source-json",
        type=Path,
        help="also validate that OWBD decodes to the JSON/generated-C model",
    )

    subparsers.add_parser(
        "probe",
        help="validate an in-memory non-empty OWBD blob with payload after the header",
    )
    roundtrip_parser = subparsers.add_parser(
        "roundtrip",
        help="validate JSON -> OWBD -> decoded model against generated C compatibility data",
    )
    roundtrip_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)

    args = parser.parse_args()

    try:
        if args.command == "build":
            write_blob(args.output, args.input)
        elif args.command == "validate":
            validate_path(args.path, args.json, args.source_json)
        elif args.command == "probe":
            run_probe()
        elif args.command == "roundtrip":
            run_roundtrip(args.input)
        else:
            parser.error(f"unknown command {args.command}")
    except OwbdError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
