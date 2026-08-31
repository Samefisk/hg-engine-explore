"""Canonical v72 behavior schema validation and deterministic code generation."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "tools/overworld/behavior_schema.json"
GENERATED_HEADER_PATH = ROOT / "include/generated/overworld_behavior_schema.h"
GENERATED_METADATA_PATH = ROOT / "tools/overworld/generated/behavior_schema.json"
TYPE_SIZES = {"u8": 1, "u16": 2}
DISPLAY_UNITS = {
    "frames": "frames",
    "tiles": "tiles",
    "percent": "%",
    "pixels": "px",
    "moves": "moves",
    "pokemon": "Pokémon",
}
FIELD_KEYS = {
    "id", "key", "path", "cType", "offset", "unit", "bounds", "lane",
    "operators", "featureId", "mask", "label", "editorNumeric", "introducedIn",
}
TOP_LEVEL_KEYS = {
    "schemaVersion", "name", "blobVersion", "compactCType", "compactSize",
    "tailPadding", "lanes", "operatorKinds", "featureIds", "fields",
}


class BehaviorSchemaError(ValueError):
    """A precise error in the canonical behavior schema."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BehaviorSchemaError(message)


def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BehaviorSchemaError(f"cannot read {path}: {exc}") from exc
    validate_schema(schema)
    return schema


def validate_schema(schema: dict[str, Any]) -> None:
    _require(isinstance(schema, dict), "schema root must be an object")
    _require(set(schema) == TOP_LEVEL_KEYS, "schema root keys are not exact")
    _require(schema["schemaVersion"] == 1, "unsupported schemaVersion")
    _require(schema["blobVersion"] == 72, "schema must describe blob v72")
    _require(schema["compactSize"] == 72, "compact layout must remain 72 bytes")
    _require(schema["tailPadding"] == 1, "compact v72 must retain one tail-padding byte")
    _require(schema["compactCType"] == "OverworldWildBehaviorProfileData", "unexpected compact C type")
    fields = schema["fields"]
    _require(isinstance(fields, list) and len(fields) == 67, "schema must contain exactly 67 fields")
    lanes = set(schema["lanes"])
    operators = set(schema["operatorKinds"])
    features = set(schema["featureIds"])
    seen_keys: set[str] = set()
    seen_paths: set[str] = set()
    seen_masks: set[tuple[int, int]] = set()
    occupied: set[int] = set()
    for field_id, field in enumerate(fields):
        prefix = f"fields[{field_id}]"
        _require(isinstance(field, dict) and set(field) == FIELD_KEYS, f"{prefix} keys are not exact")
        _require(field["id"] == field_id, f"{prefix}.id must preserve field order")
        _require(re.fullmatch(r"[a-z][A-Za-z0-9]*", field["key"]) is not None, f"{prefix}.key is invalid")
        _require(field["key"] not in seen_keys, f"duplicate field key {field['key']}")
        _require(field["path"].startswith("profile."), f"{prefix}.path must be a named profile path")
        _require(field["path"] not in seen_paths, f"duplicate field path {field['path']}")
        _require(field["cType"] in TYPE_SIZES, f"{prefix}.cType is unsupported")
        _require(field["lane"] in lanes, f"{prefix}.lane is unknown")
        _require(field["featureId"] in features, f"{prefix}.featureId is unknown")
        _require(isinstance(field["operators"], list) and field["operators"], f"{prefix}.operators is empty")
        _require(field["operators"][0] == "replace", f"{prefix} must allow replace first")
        _require(len(field["operators"]) == len(set(field["operators"])), f"{prefix}.operators has duplicates")
        _require(set(field["operators"]) <= operators, f"{prefix}.operators contains an unknown value")
        bounds = field["bounds"]
        _require(set(bounds) == {"min", "max"}, f"{prefix}.bounds keys are not exact")
        storage_max = (1 << (8 * TYPE_SIZES[field["cType"]])) - 1
        _require(0 <= bounds["min"] <= bounds["max"] <= storage_max, f"{prefix}.bounds exceed {field['cType']}")
        _require(isinstance(field["editorNumeric"], bool), f"{prefix}.editorNumeric must be boolean")
        _require(isinstance(field["introducedIn"], int) and field["introducedIn"] <= 72, f"{prefix}.introducedIn is invalid")
        mask = field["mask"]
        _require(set(mask) == {"word", "bit", "symbol"}, f"{prefix}.mask keys are not exact")
        _require(mask["word"] in (1, 2, 3) and 0 <= mask["bit"] < 32, f"{prefix}.mask position is invalid")
        _require((mask["word"], mask["bit"]) not in seen_masks, f"duplicate mask bit for {field['key']}")
        expected_prefix = "OW_WILD_BEHAVIOR_OVERRIDE" + ("" if mask["word"] == 1 else str(mask["word"])) + "_"
        _require(mask["symbol"].startswith(expected_prefix), f"{prefix}.mask symbol uses the wrong word")
        size = TYPE_SIZES[field["cType"]]
        _require(isinstance(field["offset"], int), f"{prefix}.offset must be an integer")
        field_bytes = set(range(field["offset"], field["offset"] + size))
        _require(not field_bytes & occupied, f"{prefix} overlaps an earlier field")
        _require(max(field_bytes) < schema["compactSize"], f"{prefix} exceeds compact layout")
        occupied |= field_bytes
        seen_keys.add(field["key"])
        seen_paths.add(field["path"])
        seen_masks.add((mask["word"], mask["bit"]))
    expected_bytes = set(range(schema["compactSize"] - schema["tailPadding"]))
    _require(occupied == expected_bytes, "fields must cover bytes 0-70 exactly")
    expected_mask_counts = {1: 27, 2: 15, 3: 25}
    for word, count in expected_mask_counts.items():
        bits = sorted(bit for mask_word, bit in seen_masks if mask_word == word)
        _require(bits == list(range(count)), f"override mask word {word} must use contiguous bits 0-{count - 1}")


def _schema_digest(schema: dict[str, Any]) -> str:
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def editor_metadata(schema: dict[str, Any]) -> dict[str, Any]:
    fields = []
    for field in schema["fields"]:
        fields.append({
            "id": field["id"],
            "key": field["key"],
            "path": field["path"],
            "label": field["label"],
            "unit": DISPLAY_UNITS.get(field["unit"], ""),
            "semanticUnit": field["unit"],
            "min": field["bounds"]["min"],
            "max": field["bounds"]["max"],
            "lane": field["lane"],
            "featureId": field["featureId"],
            "operators": field["operators"],
            "numeric": field["editorNumeric"],
        })
    return {
        "schemaVersion": schema["schemaVersion"],
        "blobVersion": schema["blobVersion"],
        "fields": fields,
        "overrideFieldKeys": [field["key"] for field in schema["fields"]],
        "numericProfileFieldKeys": [field["key"] for field in schema["fields"] if field["editorNumeric"]],
        "relativeOverrideFieldKeys": [field["key"] for field in schema["fields"] if "relative" in field["operators"]],
        "boundedOverrideOperatorFieldKeys": [field["key"] for field in schema["fields"] if "atLeast" in field["operators"] or "atMost" in field["operators"]],
    }


def validator_metadata(schema: dict[str, Any]) -> dict[str, Any]:
    masks: dict[str, int] = {}
    operator_masks: dict[str, dict[str, int]] = {}
    for word in (1, 2, 3):
        word_fields = [field for field in schema["fields"] if field["mask"]["word"] == word]
        masks[str(word)] = sum(1 << field["mask"]["bit"] for field in word_fields)
        operator_masks[str(word)] = {
            operator: sum(1 << field["mask"]["bit"] for field in word_fields if operator in field["operators"])
            for operator in ("relative", "atLeast", "atMost")
        }
    return {
        "compactCType": schema["compactCType"],
        "compactSize": schema["compactSize"],
        "tailPadding": schema["tailPadding"],
        "allowedOverrideMasks": masks,
        "allowedOperatorMasks": operator_masks,
        "fields": [{
            "id": field["id"], "key": field["key"], "cType": field["cType"],
            "offset": field["offset"], "size": TYPE_SIZES[field["cType"]],
            "min": field["bounds"]["min"], "max": field["bounds"]["max"],
            "maskWord": field["mask"]["word"], "maskBit": field["mask"]["bit"],
        } for field in schema["fields"]],
    }


def migration_metadata(schema: dict[str, Any]) -> dict[str, Any]:
    versions = (57, 58, 59, 62, 63, 64, 66, 67, 68, 71, 72)
    return {
        "currentBlobVersion": schema["blobVersion"],
        "versions": [{
            "version": version,
            "fieldKeys": [field["key"] for field in schema["fields"] if field["introducedIn"] <= version and not (version == 71 and field["key"] == "walkStompTime")],
        } for version in versions],
        "v71ToV72": {
            "preservesCompactSize": True,
            "changes": [
                "Walk speed tiers become exact travel-frame values.",
                "walkStompTime uses byte 70 and no longer shares packed Walk options.",
            ],
        },
    }


def trace_metadata(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": schema["schemaVersion"],
        "labels": [{
            "fieldId": field["id"], "key": field["key"], "path": field["path"],
            "label": field["label"], "featureId": field["featureId"],
        } for field in schema["fields"]],
    }


def generated_metadata(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "generatedFrom": str(SCHEMA_PATH.relative_to(ROOT)),
        "sourceSha256": _schema_digest(schema),
        "editor": editor_metadata(schema),
        "validator": validator_metadata(schema),
        "migration": migration_metadata(schema),
        "trace": trace_metadata(schema),
    }


def _constant_name(key: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", key).upper()


def render_c_header(schema: dict[str, Any]) -> str:
    lines = [
        "/* Generated by scripts/generate_overworld_behavior_schema.py. Do not edit. */",
        "#ifndef POKEHEARTGOLD_GENERATED_OVERWORLD_BEHAVIOR_SCHEMA_H",
        "#define POKEHEARTGOLD_GENERATED_OVERWORLD_BEHAVIOR_SCHEMA_H",
        "",
        f"#define OW_BEHAVIOR_SCHEMA_VERSION {schema['schemaVersion']}",
        f"#define OW_BEHAVIOR_SCHEMA_BLOB_VERSION {schema['blobVersion']}",
        f"#define OW_BEHAVIOR_SCHEMA_FIELD_COUNT {len(schema['fields'])}",
        f"#define OW_BEHAVIOR_SCHEMA_COMPACT_SIZE {schema['compactSize']}",
        "",
        "typedef enum OverworldBehaviorFieldId {",
    ]
    for field in schema["fields"]:
        lines.append(f"    OW_BEHAVIOR_FIELD_{_constant_name(field['key'])} = {field['id']},")
    lines += ["    OW_BEHAVIOR_FIELD_COUNT = OW_BEHAVIOR_SCHEMA_FIELD_COUNT", "} OverworldBehaviorFieldId;", ""]
    for field in schema["fields"]:
        name = _constant_name(field["key"])
        lines += [
            f"#define OW_BEHAVIOR_FIELD_OFFSET_{name} {field['offset']}",
            f"#define OW_BEHAVIOR_FIELD_MASK_WORD_{name} {field['mask']['word']}",
            f"#define OW_BEHAVIOR_FIELD_MASK_{name} (1u << {field['mask']['bit']})",
        ]
    lines += ["", "#define OW_BEHAVIOR_FIELD_LAYOUT(X) \\"]
    for index, field in enumerate(schema["fields"]):
        suffix = " \\" if index + 1 < len(schema["fields"]) else ""
        lines.append(f"    X({_constant_name(field['key'])}, {field['cType']}, {field['offset']}, {field['mask']['word']}, {field['mask']['bit']}){suffix}")
    lines += ["", "#endif", ""]
    return "\n".join(lines)


def render_metadata_json(schema: dict[str, Any]) -> str:
    return json.dumps(generated_metadata(schema), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def write_generated(schema: dict[str, Any], *, check: bool = False) -> list[Path]:
    outputs = {
        GENERATED_HEADER_PATH: render_c_header(schema),
        GENERATED_METADATA_PATH: render_metadata_json(schema),
    }
    stale: list[Path] = []
    for path, content in outputs.items():
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return stale
