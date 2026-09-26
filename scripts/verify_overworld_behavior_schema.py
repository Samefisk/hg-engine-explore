#!/usr/bin/env python3
"""Prove the generated v79 behavior schema matches C and Workshop contracts."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.overworld.behavior_schema import (  # noqa: E402
    GENERATED_HEADER_PATH,
    GENERATED_METADATA_PATH,
    TYPE_SIZES,
    editor_metadata,
    load_schema,
    render_c_header,
    render_metadata_json,
    validator_metadata,
)

HEADER = ROOT / "include/overworld_wild_behavior_data.h"
VIEWER = ROOT / "scripts/overworld_behavior_profile_viewer.py"


def fail(message: str) -> None:
    raise AssertionError(message)


def parse_c_layout(text: str, c_type: str) -> list[tuple[str, str, int]]:
    match = re.search(rf"typedef struct {re.escape(c_type)}\s*\{{(.*?)\}}\s*{re.escape(c_type)}\s*;", text, re.S)
    if match is None:
        fail(f"missing C struct {c_type}")
    declarations = re.findall(r"^\s*(u8|u16)\s+([A-Za-z_][A-Za-z0-9_]*)\s*;", match.group(1), re.M)
    layout: list[tuple[str, str, int]] = []
    offset = 0
    max_alignment = 1
    for c_field_type, key in declarations:
        size = TYPE_SIZES[c_field_type]
        offset = (offset + size - 1) // size * size
        layout.append((key, c_field_type, offset))
        offset += size
        max_alignment = max(max_alignment, size)
    total_size = (offset + max_alignment - 1) // max_alignment * max_alignment
    if total_size != 72:
        fail(f"C compact layout is {total_size} bytes, expected 72")
    return layout


def parse_c_masks(text: str) -> dict[str, tuple[int, int]]:
    masks: dict[str, tuple[int, int]] = {}
    pattern = re.compile(r"^#define\s+(OW_WILD_BEHAVIOR_OVERRIDE(?P<word>[23])?_[A-Z0-9_]+)\s+\(1u\s*<<\s*(?P<bit>\d+)\)", re.M)
    for match in pattern.finditer(text):
        masks[match.group(1)] = (int(match.group("word") or "1"), int(match.group("bit")))
    return masks


def load_viewer_module():
    spec = importlib.util.spec_from_file_location("overworld_behavior_profile_viewer_schema_check", VIEWER)
    if spec is None or spec.loader is None:
        fail("cannot load Workshop backend")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    schema = load_schema()
    fields = schema["fields"]
    authoring_fields = [field for field in fields if not field.get("reserved")]
    rendered_header = render_c_header(schema)
    rendered_metadata = render_metadata_json(schema)
    if GENERATED_HEADER_PATH.read_text(encoding="utf-8") != rendered_header:
        fail("committed generated C header is stale")
    if GENERATED_METADATA_PATH.read_text(encoding="utf-8") != rendered_metadata:
        fail("committed generated host metadata is stale")
    header_text = HEADER.read_text(encoding="utf-8")
    actual_layout = parse_c_layout(header_text, schema["compactCType"])
    # Logical fields can share one physical byte. The schema assigns
    # non-overlapping bit ranges to each packed group.
    expected_layout = []
    seen_storage = set()
    for field in fields:
        storage = (field["offset"], field["cType"])
        if storage in seen_storage:
            continue
        seen_storage.add(storage)
        expected_layout.append((field["key"], field["cType"], field["offset"]))
    if actual_layout != expected_layout:
        fail("generated field order or offsets do not match the compact C layout")

    actual_masks = parse_c_masks(header_text)
    for field in authoring_fields:
        expected = (field["mask"]["word"], field["mask"]["bit"])
        actual = actual_masks.get(field["mask"]["symbol"])
        if actual != expected:
            fail(f"{field['key']} mask is {actual}, expected {expected}")

    generated_header = rendered_header
    for field in fields:
        constant = re.sub(r"(?<!^)(?=[A-Z])", "_", field["key"]).upper()
        if f"OW_BEHAVIOR_FIELD_{constant} = {field['id']}" not in generated_header:
            fail(f"generated C field ID is missing for {field['key']}")
    for field in authoring_fields:
        constant = re.sub(r"(?<!^)(?=[A-Z])", "_", field["key"]).upper()
        required = (
            f"OW_BEHAVIOR_FIELD_OFFSET_{constant} {field['offset']}",
            f"OW_BEHAVIOR_FIELD_MASK_WORD_{constant} {field['mask']['word']}",
            f"OW_BEHAVIOR_FIELD_MASK_{constant} (1u << {field['mask']['bit']})",
        )
        if any(fragment not in generated_header for fragment in required):
            fail(f"generated C metadata is incomplete for {field['key']}")

    validator = validator_metadata(schema)
    for word, expected in {"1": 0x3FFFFFFF, "2": 0x00007FFF, "3": 0x3FFFFFFF}.items():
        if validator["allowedOverrideMasks"][word] != expected:
            fail(f"generated allowed mask {word} is wrong")

    viewer = load_viewer_module()
    editor = editor_metadata(schema)
    keys = [field["key"] for field in authoring_fields]
    editor_fields_by_key = {field["key"]: field for field in editor["fields"]}
    if viewer.PROFILE_FIELDS != keys:
        fail("Workshop field order does not use the generated schema")
    authoring_keys = {field["key"] for field in authoring_fields}
    if set(viewer.OVERRIDE_SYMBOL_BY_FIELD) != authoring_keys:
        fail("Workshop override field set differs from the schema")
    for field in authoring_fields:
        key = field["key"]
        if viewer.OVERRIDE_SYMBOL_BY_FIELD[key] != field["mask"]["symbol"]:
            fail(f"Workshop override symbol differs for {key}")
        if viewer.OVERRIDE_WORD_BY_FIELD[key] != field["mask"]["word"]:
            fail(f"Workshop override word differs for {key}")
        generated_field = editor_fields_by_key[key]
        if viewer.FIELD_LABELS[key] != generated_field["label"]:
            fail(f"Workshop label differs for {key}")
        if viewer.FIELD_UNITS.get(key, "") != generated_field["unit"]:
            fail(f"Workshop unit differs for {key}")

    expected_numeric = set(editor["numericProfileFieldKeys"])
    actual_numeric = set(viewer.NUMERIC_PROFILE_FIELDS) & set(keys)
    if actual_numeric != expected_numeric:
        fail(f"Workshop numeric fields differ: {sorted(actual_numeric ^ expected_numeric)}")
    expected_relative = set(editor["relativeOverrideFieldKeys"])
    actual_relative = set(viewer.RELATIVE_OVERRIDE_PROFILE_FIELDS) & set(keys)
    if actual_relative != expected_relative:
        fail(f"Workshop relative operators differ: {sorted(actual_relative ^ expected_relative)}")
    expected_bounded = set(editor["boundedOverrideOperatorFieldKeys"])
    actual_bounded = set(viewer.BOUNDED_OVERRIDE_PROFILE_FIELDS) & set(keys)
    if actual_bounded != expected_bounded:
        fail(f"Workshop bounded operators differ: {sorted(actual_bounded ^ expected_bounded)}")
    for field in fields:
        key = field["key"]
        bounds = field["bounds"]
        if key in viewer.NUMERIC_PROFILE_FIELD_OPTION_MIN and viewer.NUMERIC_PROFILE_FIELD_OPTION_MIN[key] != bounds["min"]:
            fail(f"Workshop minimum differs for {key}")
        if key in viewer.NUMERIC_PROFILE_FIELD_OPTION_MAX and viewer.NUMERIC_PROFILE_FIELD_OPTION_MAX[key] != bounds["max"]:
            fail(f"Workshop maximum differs for {key}")

    required_turn_skid_macros = (
        "OW_WILD_BEHAVIOR_TURN_SKID_OPTIONS(tilesBeforeTurnSkid, planTurnSkidPath, stopSkid)",
        "OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID(options)",
        "OW_WILD_BEHAVIOR_PLANS_TURN_SKID_PATH(options)",
        "OW_WILD_BEHAVIOR_STOPS_WITH_SKID(options)",
    )
    if any(fragment not in header_text for fragment in required_turn_skid_macros):
        fail("C header does not publish the packed turn-skid option contract")

    print(f"behavior schema: {schema['compactSize']} bytes and {len(authoring_fields)} authoring fields match compact v{schema['blobVersion']} contracts")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, ValueError) as exc:
        print(f"behavior schema: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
