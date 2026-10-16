"""Canonical v92 behavior schema validation and deterministic code generation."""

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
    "strength": "level",
    "tile256PerFrame": "1/256 tile/frame",
    "hp": "HP",
}
FIELD_KEYS = {
    "id", "key", "path", "cType", "offset", "unit", "bounds", "lane",
    "operators", "featureId", "mask", "label", "editorNumeric", "introducedIn",
}
PACKED_FIELD_KEYS = {"bitOffset", "bitWidth"}
RESERVED_FIELD_KEYS = {"reserved"}
TOP_LEVEL_KEYS = {
    "schemaVersion", "name", "blobVersion", "compactCType", "compactSize",
    "tailPadding", "lanes", "operatorKinds", "featureIds", "fields", "profileSettings",
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
    _require(schema["schemaVersion"] == 2, "unsupported schemaVersion; expected 2")
    _require(schema["blobVersion"] == 92, "schema must describe blob v92")
    _require(schema["compactSize"] == 80, "compact layout must remain 80 bytes")
    _require(schema["tailPadding"] == 0, "compact v85 uses its final byte")
    _require(schema["compactCType"] == "OverworldWildBehaviorProfileData", "unexpected compact C type")
    settings = schema["profileSettings"]
    _require(isinstance(settings, list) and len(settings) == 1,
             "schema must describe one local conditional-profile setting")
    _require(isinstance(settings[0], dict)
             and type(settings[0].get("default")) is bool and settings[0] == {
        "key": "showRestTintDuringCooldown", "type": "boolean", "default": False,
        "profileKind": "conditional", "inherited": False,
        "blobTail": "restEnabledApplications", "introducedIn": 86,
        "label": "Show rest tint during cooldown",
    }, "cooldown tint must remain a local conditional-profile boolean")
    fields = schema["fields"]
    _require(isinstance(fields, list) and len(fields) == 94, "schema must contain exactly 94 fields")
    lanes = set(schema["lanes"])
    operators = set(schema["operatorKinds"])
    features = set(schema["featureIds"])
    seen_keys: set[str] = set()
    seen_paths: set[str] = set()
    seen_masks: set[tuple[int, int]] = set()
    occupied_bits: set[int] = set()
    for field_id, field in enumerate(fields):
        prefix = f"fields[{field_id}]"
        field_keys = set(field) if isinstance(field, dict) else set()
        reserved = field.get("reserved") is True
        expected_keys = FIELD_KEYS | (RESERVED_FIELD_KEYS if reserved else set())
        _require(
            field_keys == expected_keys
            or field_keys == expected_keys | PACKED_FIELD_KEYS,
            f"{prefix} keys are not exact",
        )
        _require(field["id"] == field_id, f"{prefix}.id must preserve field order")
        _require(re.fullmatch(r"[a-z][A-Za-z0-9]*", field["key"]) is not None, f"{prefix}.key is invalid")
        _require(field["key"] not in seen_keys, f"duplicate field key {field['key']}")
        expected_path_prefix = "reserved." if reserved else "profile."
        _require(field["path"].startswith(expected_path_prefix), f"{prefix}.path uses the wrong namespace")
        _require(field["path"] not in seen_paths, f"duplicate field path {field['path']}")
        _require(field["cType"] in TYPE_SIZES, f"{prefix}.cType is unsupported")
        _require(field["lane"] in lanes, f"{prefix}.lane is unknown")
        _require(field["featureId"] in features, f"{prefix}.featureId is unknown")
        _require(isinstance(field["operators"], list), f"{prefix}.operators must be an array")
        _require(reserved or field["operators"], f"{prefix}.operators is empty")
        _require(reserved or field["operators"][0] == "replace", f"{prefix} must allow replace first")
        _require(len(field["operators"]) == len(set(field["operators"])), f"{prefix}.operators has duplicates")
        _require(set(field["operators"]) <= operators, f"{prefix}.operators contains an unknown value")
        bounds = field["bounds"]
        _require(set(bounds) == {"min", "max"}, f"{prefix}.bounds keys are not exact")
        storage_max = (1 << (8 * TYPE_SIZES[field["cType"]])) - 1
        _require(0 <= bounds["min"] <= bounds["max"] <= storage_max, f"{prefix}.bounds exceed {field['cType']}")
        _require(isinstance(field["editorNumeric"], bool), f"{prefix}.editorNumeric must be boolean")
        _require(isinstance(field["introducedIn"], int) and field["introducedIn"] <= 92, f"{prefix}.introducedIn is invalid")
        mask = field["mask"]
        _require(set(mask) == {"word", "bit", "symbol"}, f"{prefix}.mask keys are not exact")
        _require(mask["word"] in (1, 2, 3) and 0 <= mask["bit"] < 32, f"{prefix}.mask position is invalid")
        _require((mask["word"], mask["bit"]) not in seen_masks, f"duplicate mask bit for {field['key']}")
        expected_prefix = "OW_WILD_BEHAVIOR_OVERRIDE" + ("" if mask["word"] == 1 else str(mask["word"])) + "_"
        if reserved:
            _require(mask["symbol"] is None, f"{prefix}.mask symbol must be null")
            _require(field["lane"] == "reserved", f"{prefix}.lane must be reserved")
            _require(field["featureId"] == "reserved", f"{prefix}.featureId must be reserved")
            _require(field["bounds"] == {"min": 0, "max": 0}, f"{prefix}.bounds must be zero")
        else:
            _require(isinstance(mask["symbol"], str) and mask["symbol"].startswith(expected_prefix), f"{prefix}.mask symbol uses the wrong word")
        size = TYPE_SIZES[field["cType"]]
        _require(isinstance(field["offset"], int), f"{prefix}.offset must be an integer")
        if PACKED_FIELD_KEYS <= field_keys:
            _require(size == 1, f"{prefix} packed fields must use u8 storage")
            bit_offset = field["bitOffset"]
            bit_width = field["bitWidth"]
            _require(
                isinstance(bit_offset, int) and isinstance(bit_width, int)
                and 0 <= bit_offset < 8 and 1 <= bit_width <= 8 - bit_offset,
                f"{prefix} packed bit range is invalid",
            )
            _require(
                bounds["max"] < (1 << bit_width),
                f"{prefix}.bounds exceed its packed bit width",
            )
        else:
            bit_offset = 0
            bit_width = size * 8
        field_bits = set(range(
            field["offset"] * 8 + bit_offset,
            field["offset"] * 8 + bit_offset + bit_width,
        ))
        _require(not field_bits & occupied_bits, f"{prefix} overlaps an earlier field")
        _require(max(field_bits) < schema["compactSize"] * 8, f"{prefix} exceeds compact layout")
        occupied_bits |= field_bits
        seen_keys.add(field["key"])
        seen_paths.add(field["path"])
        seen_masks.add((mask["word"], mask["bit"]))
    expected_bits = set(range((schema["compactSize"] - schema["tailPadding"]) * 8))
    # Byte 75 bits 1..5 remain fixed zero storage, with no authored field.
    expected_bits -= {75 * 8 + bit for bit in range(1, 6)}
    _require(occupied_bits == expected_bits, "fields must cover the compact layout exactly")
    expected_mask_counts = {1: 30, 2: 32, 3: 32}
    for word, count in expected_mask_counts.items():
        bits = sorted(bit for mask_word, bit in seen_masks if mask_word == word)
        _require(bits == list(range(count)), f"override mask word {word} must use contiguous bits 0-{count - 1}")


def _schema_digest(schema: dict[str, Any]) -> str:
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def editor_metadata(schema: dict[str, Any]) -> dict[str, Any]:
    fields = []
    for field in schema["fields"]:
        if field.get("reserved"):
            continue
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
        "profileSettings": schema["profileSettings"],
        "fields": fields,
        "overrideFieldKeys": [field["key"] for field in schema["fields"]],
        "numericProfileFieldKeys": [field["key"] for field in schema["fields"] if field["editorNumeric"]],
        "relativeOverrideFieldKeys": [field["key"] for field in schema["fields"] if "relative" in field["operators"]],
        "divideOverrideFieldKeys": [field["key"] for field in schema["fields"] if "divide" in field["operators"]],
        "boundedOverrideOperatorFieldKeys": [field["key"] for field in schema["fields"] if "atLeast" in field["operators"] or "atMost" in field["operators"]],
    }


def validator_metadata(schema: dict[str, Any]) -> dict[str, Any]:
    masks: dict[str, int] = {}
    operator_masks: dict[str, dict[str, int]] = {}
    for word in (1, 2, 3):
        word_fields = [
            field for field in schema["fields"]
            if field["mask"]["word"] == word and not field.get("reserved")
        ]
        masks[str(word)] = sum(1 << field["mask"]["bit"] for field in word_fields)
        operator_masks[str(word)] = {
            operator: sum(1 << field["mask"]["bit"] for field in word_fields if operator in field["operators"])
            for operator in ("relative", "divide", "atLeast", "atMost")
        }
    return {
        "compactCType": schema["compactCType"],
        "profileSettings": schema["profileSettings"],
        "compactSize": schema["compactSize"],
        "tailPadding": schema["tailPadding"],
        "allowedOverrideMasks": masks,
        "allowedOperatorMasks": operator_masks,
        "fields": [{
            "id": field["id"], "key": field["key"], "cType": field["cType"],
            "offset": field["offset"], "size": TYPE_SIZES[field["cType"]],
            "min": field["bounds"]["min"], "max": field["bounds"]["max"],
            "maskWord": field["mask"]["word"], "maskBit": field["mask"]["bit"],
            "bitOffset": field.get("bitOffset", 0),
            "bitWidth": field.get("bitWidth", TYPE_SIZES[field["cType"]] * 8),
            "reserved": field.get("reserved", False),
        } for field in schema["fields"]],
    }


def migration_metadata(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "currentBlobVersion": schema["blobVersion"],
        "versions": [{
            "version": 79,
            "fieldKeys": [
                field["key"] for field in schema["fields"]
                if not field.get("reserved") and field["introducedIn"] <= 79
            ],
        }, {
            "version": 80,
            "fieldKeys": [
                field["key"] for field in schema["fields"]
                if not field.get("reserved") and field["introducedIn"] <= 80
            ],
        }, {
            "version": 81,
            "fieldKeys": [
                field["key"] for field in schema["fields"]
                if not field.get("reserved") and field["introducedIn"] <= 81
            ],
        }, {
            "version": 82,
            "fieldKeys": [
                field["key"] for field in schema["fields"]
                if not field.get("reserved") and field["introducedIn"] <= 82
            ],
        }, {
            "version": 83,
            "fieldKeys": [
                field["key"] for field in schema["fields"]
                if not field.get("reserved") and field["introducedIn"] <= 83
            ],
        }, {
            "version": 84,
            "fieldKeys": [
                field["key"] for field in schema["fields"]
                if not field.get("reserved") and field["introducedIn"] <= 84
            ] + ["knockback"],
        }, {
            "version": 85,
            "fieldKeys": [field["key"] for field in schema["fields"] if field["introducedIn"] <= 85],
        }, {
            "version": 86,
            "fieldKeys": [field["key"] for field in schema["fields"] if field["introducedIn"] <= 86],
        }, {
            "version": 87,
            "fieldKeys": [field["key"] for field in schema["fields"] if field["introducedIn"] <= 87],
        }, {
            "version": 88,
            "fieldKeys": [field["key"] for field in schema["fields"] if field["introducedIn"] <= 88],
        }, {
            "version": 89,
            "fieldKeys": [field["key"] for field in schema["fields"] if field["introducedIn"] <= 89],
        }, {
            "version": 90,
            "fieldKeys": [field["key"] for field in schema["fields"] if field["introducedIn"] <= 90],
        }, {
            "version": 91,
            "fieldKeys": [field["key"] for field in schema["fields"]],
        }],
        "v78ToV79": {
            "preservesCompactSize": True,
            "changes": [
                "Three reserved bytes become shared Vision range, cone, and adjacent-awareness fields.",
                "The compact profile remains 72 bytes.",
            ],
        },
        "v79ToV80": {
            "preservesCompactSize": True,
            "changes": [
                "The remaining reserved owner-lane byte becomes Walk horizontal sway.",
                "Walk sway no longer shares the packed Walk options field.",
            ],
        },
        "v80ToV81": {
            "preservesCompactSize": True,
            "changes": [
                "Reserved byte 16 stores four independent mounted Walk presentation controls.",
                "All existing movement fields and offsets remain unchanged.",
            ],
        },
        "v81ToV82": {
            "preservesCompactSize": False,
            "changes": [
                "Three appended bytes hold collision attack enable, minimum impact speed, and damage.",
                "The compact profile grows to 76 bytes, with one alignment byte.",
            ],
        },
        "v82ToV83": {
            "preservesCompactSize": False,
            "changes": [
                "Four appended bytes hold On reach and held-actor Throw tuning.",
                "The compact profile grows to 80 bytes, with one alignment byte.",
            ],
        },
        "v83ToV84": {
            "preservesCompactSize": True,
            "changes": [
                "The final alignment byte becomes a profile-owned knockback switch.",
                "The compact profile remains 80 bytes.",
            ],
        },
        "v84ToV85": {
            "preservesCompactSize": True,
            "changes": [
                "The knockback byte now packs motion type and tile distance.",
                "The compact profile remains 80 bytes.",
            ],
        },
        "v85ToV86": {
            "preservesCompactSize": True,
            "changes": [
                "An optional local conditional-profile boolean enables cooldown rest tint.",
                "A four-byte application mask follows the padded surface catalog; all existing blob offsets remain unchanged.",
                "The compact profile remains 80 bytes and the blob header remains 84 bytes.",
            ],
        },
        "v90ToV91": {
            "preservesCompactSize": True,
            "changes": [
                "Byte 57 bits 4 and 5 hold extra Hop in place hops.",
                "Byte 43 bits 1 through 7 hold their admission chance.",
                "Reposition count and previous-tile permission keep their low bits; the compact lane remains 80 bytes.",
            ],
        },
        "v89ToV90": {
            "preservesCompactSize": True,
            "changes": [
                "Byte 42 bits 2 through 5 hold Cargo target check interval in frames.",
                "Bits 6 and 7 hold the Cargo target switch advantage in tiles.",
                "Continue and return retain bits 0 and 1; all sizes and offsets stay fixed.",
            ],
        },
        "v88ToV89": {
            "preservesCompactSize": True,
            "changes": [
                "Return after each move uses bit 1 of the existing controller options byte.",
                "Continue when arrived keeps bit 0; bits 2 through 7 remain zero.",
                "The compact profile remains 80 bytes and the blob header remains 84 bytes.",
            ],
        },
    }


def trace_metadata(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": schema["schemaVersion"],
        "labels": [{
            "fieldId": field["id"], "key": field["key"], "path": field["path"],
            "label": field["label"], "featureId": field["featureId"],
        } for field in schema["fields"] if not field.get("reserved")],
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
        f"#define OW_BEHAVIOR_SCHEMA_AUTHORING_FIELD_COUNT {sum(not field.get('reserved') for field in schema['fields'])}",
        f"#define OW_BEHAVIOR_SCHEMA_COMPACT_SIZE {schema['compactSize']}",
        "",
        "typedef enum OverworldBehaviorFieldId {",
    ]
    for field in schema["fields"]:
        lines.append(f"    OW_BEHAVIOR_FIELD_{_constant_name(field['key'])} = {field['id']},")
    lines += ["    OW_BEHAVIOR_FIELD_COUNT = OW_BEHAVIOR_SCHEMA_FIELD_COUNT", "} OverworldBehaviorFieldId;", ""]
    for field in schema["fields"]:
        if field.get("reserved"):
            continue
        name = _constant_name(field["key"])
        lines += [
            f"#define OW_BEHAVIOR_FIELD_OFFSET_{name} {field['offset']}",
            f"#define OW_BEHAVIOR_FIELD_MASK_WORD_{name} {field['mask']['word']}",
            f"#define OW_BEHAVIOR_FIELD_MASK_{name} (1u << {field['mask']['bit']})",
            f"#define OW_BEHAVIOR_FIELD_BIT_OFFSET_{name} {field.get('bitOffset', 0)}",
            f"#define OW_BEHAVIOR_FIELD_BIT_WIDTH_{name} {field.get('bitWidth', TYPE_SIZES[field['cType']] * 8)}",
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
