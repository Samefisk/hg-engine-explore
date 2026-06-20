#!/usr/bin/env python3
"""Generate overlay-150 compatibility behavior data from semantic JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/overworld_wild_behavior/profiles.json"
DEFAULT_OUTPUT = (
    ROOT
    / "src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_profiles.generated.inc"
)

PROFILE_FIELDS = (
    "chillState",
    "alertState",
    "alertEmote",
    "alertTime",
    "alertness",
    "attentiveState",
    "stamina",
    "tiredState",
    "restTime",
    "chillSpeed",
    "attentiveSpeed",
    "tiredSpeed",
    "range",
    "jumpLevel",
    "profileId",
    "spawnState",
    "chillAction",
    "chillTarget",
    "alertRange",
    "attentiveAction",
    "targetSelector",
    "movementStyle",
    "chillCooldown",
    "attentiveCooldown",
    "alertChance",
    "spawnDestination",
    "chillBattle",
    "alertBattle",
    "attentiveBattle",
    "tiredBattle",
    "specialAction",
    "hopAllowNonCardinal",
    "hopMinDistance",
    "hopMaxDistance",
    "hopPause",
    "teleportTime",
    "teleportPause",
    "alertSpecialAction",
    "alertCallSpawnAmount",
    "alertCallSpawnState",
    "spawnDestinationMinDistance",
    "spawnDestinationMaxDistance",
    "ramAccelerationSteps",
    "ramMaxSpeed",
    "chillAllowedTile",
    "attentiveAllowedTile",
    "tiredAllowedTile",
    "chillAllowedTile2",
    "attentiveAllowedTile2",
    "tiredAllowedTile2",
    "attentiveHopAllowNonCardinal",
    "attentiveHopMinDistance",
    "attentiveHopMaxDistance",
    "attentiveHopPause",
    "attentiveTeleportTime",
    "attentiveTeleportPause",
    "attentiveRamAccelerationSteps",
    "attentiveRamMaxSpeed",
    "tiredHopAllowNonCardinal",
    "tiredHopMinDistance",
    "tiredHopMaxDistance",
    "tiredHopPause",
    "tiredTeleportTime",
    "tiredTeleportPause",
    "tiredRamAccelerationSteps",
    "tiredRamMaxSpeed",
)

MATCH_FIELDS = (
    "groupMask",
    "species",
    "terrain",
    "minLevel",
    "maxLevel",
    "shiny",
    "behaviorClass",
)

OVERRIDE_MASKS = {
    "chillState": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_CHILL_STATE"),
    "alertState": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_ALERT_STATE"),
    "alertEmote": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_ALERT_EMOTE"),
    "alertness": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_ALERTNESS"),
    "attentiveState": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_STATE"),
    "stamina": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_STAMINA"),
    "tiredState": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_TIRED_STATE"),
    "restTime": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_REST_TIME"),
    "chillSpeed": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED"),
    "attentiveSpeed": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_SPEED"),
    "range": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_RANGE"),
    "jumpLevel": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_JUMP_LEVEL"),
    "profileId": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_ID"),
    "spawnState": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_STATE"),
    "chillAction": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_CHILL_ACTION"),
    "alertRange": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_ALERT_RANGE"),
    "tiredSpeed": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_TIRED_SPEED"),
    "targetSelector": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_TARGET_SELECTOR"),
    "movementStyle": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_MOVEMENT_STYLE"),
    "chillCooldown": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_CHILL_COOLDOWN"),
    "attentiveCooldown": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_COOLDOWN"),
    "alertChance": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_ALERT_CHANCE"),
    "alertTime": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_ALERT_TIME"),
    "spawnDestination": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_DESTINATION"),
    "chillBattle": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_CHILL_BATTLE"),
    "alertBattle": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_ALERT_BATTLE"),
    "attentiveBattle": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_BATTLE"),
    "tiredBattle": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_TIRED_BATTLE"),
    "specialAction": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_SPECIAL_ACTION"),
    "hopAllowNonCardinal": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_HOP_ALLOW_NON_CARDINAL"),
    "hopMinDistance": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_HOP_MIN_DISTANCE"),
    "hopMaxDistance": ("mask", "OW_WILD_BEHAVIOR_OVERRIDE_HOP_MAX_DISTANCE"),
    "hopPause": ("mask2", "OW_WILD_BEHAVIOR_OVERRIDE2_HOP_PAUSE"),
    "teleportTime": ("mask2", "OW_WILD_BEHAVIOR_OVERRIDE2_TELEPORT_TIME"),
    "teleportPause": ("mask2", "OW_WILD_BEHAVIOR_OVERRIDE2_TELEPORT_PAUSE"),
    "alertSpecialAction": ("mask2", "OW_WILD_BEHAVIOR_OVERRIDE2_ALERT_SPECIAL_ACTION"),
    "alertCallSpawnAmount": ("mask2", "OW_WILD_BEHAVIOR_OVERRIDE2_ALERT_CALL_SPAWN_AMOUNT"),
    "spawnDestinationMinDistance": (
        "mask2",
        "OW_WILD_BEHAVIOR_OVERRIDE2_SPAWN_DESTINATION_MIN_DISTANCE",
    ),
    "spawnDestinationMaxDistance": (
        "mask2",
        "OW_WILD_BEHAVIOR_OVERRIDE2_SPAWN_DESTINATION_MAX_DISTANCE",
    ),
    "ramAccelerationSteps": ("mask2", "OW_WILD_BEHAVIOR_OVERRIDE2_RAM_ACCELERATION_STEPS"),
    "ramMaxSpeed": ("mask2", "OW_WILD_BEHAVIOR_OVERRIDE2_RAM_MAX_SPEED"),
    "chillAllowedTile": ("mask2", "OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TILE"),
    "attentiveAllowedTile": ("mask2", "OW_WILD_BEHAVIOR_OVERRIDE2_ATTENTIVE_ALLOWED_TILE"),
    "tiredAllowedTile": ("mask2", "OW_WILD_BEHAVIOR_OVERRIDE2_TIRED_ALLOWED_TILE"),
    "chillAllowedTile2": ("mask2", "OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TILE_2"),
    "attentiveAllowedTile2": (
        "mask2",
        "OW_WILD_BEHAVIOR_OVERRIDE2_ATTENTIVE_ALLOWED_TILE_2",
    ),
    "tiredAllowedTile2": ("mask2", "OW_WILD_BEHAVIOR_OVERRIDE2_TIRED_ALLOWED_TILE_2"),
    "chillTarget": ("mask2", "OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_TARGET"),
    "attentiveHopAllowNonCardinal": (
        "mask3",
        "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_ALLOW_NON_CARDINAL",
    ),
    "attentiveHopMinDistance": (
        "mask3",
        "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_MIN_DISTANCE",
    ),
    "attentiveHopMaxDistance": (
        "mask3",
        "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_MAX_DISTANCE",
    ),
    "attentiveHopPause": ("mask3", "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_PAUSE"),
    "attentiveTeleportTime": (
        "mask3",
        "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_TELEPORT_TIME",
    ),
    "attentiveTeleportPause": (
        "mask3",
        "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_TELEPORT_PAUSE",
    ),
    "attentiveRamAccelerationSteps": (
        "mask3",
        "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_RAM_ACCELERATION_STEPS",
    ),
    "attentiveRamMaxSpeed": (
        "mask3",
        "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_RAM_MAX_SPEED",
    ),
    "tiredHopAllowNonCardinal": (
        "mask3",
        "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_HOP_ALLOW_NON_CARDINAL",
    ),
    "tiredHopMinDistance": ("mask3", "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_HOP_MIN_DISTANCE"),
    "tiredHopMaxDistance": ("mask3", "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_HOP_MAX_DISTANCE"),
    "tiredHopPause": ("mask3", "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_HOP_PAUSE"),
    "tiredTeleportTime": ("mask3", "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_TELEPORT_TIME"),
    "tiredTeleportPause": ("mask3", "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_TELEPORT_PAUSE"),
    "tiredRamAccelerationSteps": (
        "mask3",
        "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_RAM_ACCELERATION_STEPS",
    ),
    "tiredRamMaxSpeed": ("mask3", "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_RAM_MAX_SPEED"),
    "alertCallSpawnState": ("mask3", "OW_WILD_BEHAVIOR_OVERRIDE3_ALERT_CALL_SPAWN_STATE"),
}


def c_value(value: object) -> str:
    if isinstance(value, bool):
        raise ValueError("boolean values are not valid C data tokens")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value:
        return value
    raise ValueError(f"invalid C data token: {value!r}")


def expression(parts: list[str]) -> str:
    if not parts:
        return "0"
    return " | ".join(parts)


def require_fields(obj: dict[str, object], expected: tuple[str, ...], label: str) -> None:
    actual = set(obj)
    wanted = set(expected)
    extra = sorted(actual - wanted)
    missing = sorted(wanted - actual)
    if extra or missing:
        raise ValueError(f"{label} field mismatch; missing={missing} extra={extra}")


def load_profiles(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text())
    if data.get("schemaVersion") != 1:
        raise ValueError(f"{path}: expected schemaVersion 1")

    for index, entry in enumerate(data.get("classProfiles", [])):
        require_fields(entry["profile"], PROFILE_FIELDS, f"classProfiles[{index}].profile")

    for index, entry in enumerate(data.get("classRules", [])):
        require_fields(entry["match"], MATCH_FIELDS, f"classRules[{index}].match")

    for index, entry in enumerate(data.get("overrides", [])):
        require_fields(entry["match"], MATCH_FIELDS, f"overrides[{index}].match")
        for field_name in entry["fields"]:
            if field_name not in PROFILE_FIELDS:
                raise ValueError(f"overrides[{index}] unknown profile field {field_name}")
            if field_name not in OVERRIDE_MASKS:
                raise ValueError(f"overrides[{index}] cannot encode override for {field_name}")
    return data


def emit_match(match: dict[str, object], indent: str) -> list[str]:
    lines = [f"{indent}{{"]
    for field in MATCH_FIELDS:
        lines.append(f"{indent}    {c_value(match[field])},")
    lines.append(f"{indent}}},")
    return lines


def emit_profile(profile: dict[str, object], indent: str) -> list[str]:
    lines = [f"{indent}{{"]
    for field in PROFILE_FIELDS:
        lines.append(f"{indent}    {c_value(profile[field])},")
    lines.append(f"{indent}}},")
    return lines


def emit_generated_c(data: dict[str, object]) -> str:
    lines = [
        "/*",
        " * DO NOT EDIT.",
        " * Generated by scripts/generate_overworld_wild_behavior_data.py",
        " * from data/overworld_wild_behavior/profiles.json.",
        " */",
        "",
        "static const OverworldWildBehaviorProfile sOverworldWildBehaviorClassProfiles[] = {",
    ]

    for entry in data["classProfiles"]:
        if "name" in entry:
            lines.append(f"    // {entry['name']}")
        lines.extend(emit_profile(entry["profile"], "    "))
    lines.extend(["};", ""])

    lines.append("static const OverworldWildBehaviorClassRule sOverworldWildBehaviorClassRules[] = {")
    for entry in data["classRules"]:
        lines.append("    {")
        lines.extend(emit_match(entry["match"], "        "))
        lines.append(f"        {c_value(entry['behaviorClass'])},")
        lines.append("    },")
    lines.extend(["};", ""])

    lines.append(
        "static const OverworldWildBehaviorSpeciesClassRule "
        "sOverworldWildBehaviorSpeciesClassRules[] = {"
    )
    for entry in data["speciesClassRules"]:
        lines.append(
            "    {"
            f"{c_value(entry['species'])}, "
            f"{c_value(entry['behaviorClass'])}"
            "},"
        )
    lines.extend(["};", ""])

    lines.append("// Broad behavior overrides should appear before narrower ones so later matches win.")
    lines.append("static const OverworldWildBehaviorOverride sOverworldWildBehaviorOverrides[] = {")
    for entry in data["overrides"]:
        fields = entry["fields"]
        masks: dict[str, list[str]] = {"mask": [], "mask2": [], "mask3": []}
        profile = {field: 0 for field in PROFILE_FIELDS}
        for field, value in fields.items():
            mask_name, macro = OVERRIDE_MASKS[field]
            masks[mask_name].append(macro)
            profile[field] = value

        lines.append("    {")
        lines.extend(emit_match(entry["match"], "        "))
        lines.append(f"        {expression(masks['mask'])},")
        lines.append(f"        {expression(masks['mask2'])},")
        lines.append(f"        {expression(masks['mask3'])},")
        lines.extend(emit_profile(profile, "        "))
        lines.append("    },")
    lines.extend(["};", ""])

    lines.extend(
        [
            "const OverworldWildBehaviorDataOverlayEntry gOverworldWildBehaviorDataOverlayEntry",
            '    __attribute__((section(".overworld_wild_behavior_data_entry"), used)) = {',
            "    OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC,",
            "    OVERWORLD_WILD_BEHAVIOR_DATA_VERSION,",
            "    sizeof(OverworldWildBehaviorDataOverlayEntry),",
            "    sOverworldWildBehaviorClassProfiles,",
            "    NELEMS(sOverworldWildBehaviorClassProfiles),",
            "    sOverworldWildBehaviorClassRules,",
            "    NELEMS(sOverworldWildBehaviorClassRules),",
            "    sOverworldWildBehaviorSpeciesClassRules,",
            "    NELEMS(sOverworldWildBehaviorSpeciesClassRules),",
            "    sOverworldWildBehaviorOverrides,",
            "    NELEMS(sOverworldWildBehaviorOverrides),",
            "    sOverworldWildEncounterAreaMapIds,",
            "    sOverworldWildEncounterAreaDataIds,",
            "    OW_WILD_ENCOUNTER_AREA_COUNT,",
            "};",
            "",
        ]
    )
    return "\n".join(lines)


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//.*", "", text)


def find_initializer(text: str, symbol: str) -> str:
    match = re.search(rf"\b{re.escape(symbol)}\s*\[\]\s*=\s*{{", text)
    if match is None:
        raise ValueError(f"could not find initializer for {symbol}")
    start = text.index("{", match.end() - 1)
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index]
    raise ValueError(f"unterminated initializer for {symbol}")


def split_top_level(text: str) -> list[str]:
    items = []
    start = None
    depth = 0
    for index, char in enumerate(text):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                items.append(text[start : index + 1])
                start = None
    return items


def split_values(text: str) -> list[str]:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1]
    values = []
    start = 0
    depth = 0
    for index, char in enumerate(text):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "," and depth == 0:
            value = text[start:index].strip()
            if value:
                values.append(value)
            start = index + 1
    tail = text[start:].strip()
    if tail:
        values.append(tail)
    return values


def mask_fields(mask_expression: str, mask_name: str) -> list[str]:
    mask_expression = mask_expression.strip()
    if mask_expression == "0":
        return []
    macros = [part.strip() for part in mask_expression.split("|")]
    fields = []
    for macro in macros:
        for field, (field_mask_name, field_macro) in OVERRIDE_MASKS.items():
            if field_mask_name == mask_name and field_macro == macro:
                fields.append(field)
                break
        else:
            raise ValueError(f"unknown {mask_name} macro: {macro}")
    return fields


def import_c_source(path: Path) -> dict[str, object]:
    text = strip_comments(path.read_text())

    profiles = []
    for index, entry in enumerate(split_top_level(find_initializer(text, "sOverworldWildBehaviorClassProfiles"))):
        values = split_values(entry)
        if len(values) != len(PROFILE_FIELDS):
            raise ValueError(f"profile {index} has {len(values)} values")
        profiles.append(
            {
                "name": f"class_{index}",
                "profile": dict(zip(PROFILE_FIELDS, values)),
            }
        )

    class_rules = []
    for entry in split_top_level(find_initializer(text, "sOverworldWildBehaviorClassRules")):
        values = split_values(entry)
        match_values = split_values(values[0])
        class_rules.append(
            {
                "match": dict(zip(MATCH_FIELDS, match_values)),
                "behaviorClass": values[1],
            }
        )

    species_rules = []
    for entry in split_top_level(find_initializer(text, "sOverworldWildBehaviorSpeciesClassRules")):
        species, behavior_class = split_values(entry)
        species_rules.append({"species": species, "behaviorClass": behavior_class})

    overrides = []
    for index, entry in enumerate(split_top_level(find_initializer(text, "sOverworldWildBehaviorOverrides"))):
        values = split_values(entry)
        match_values = split_values(values[0])
        profile_values = dict(zip(PROFILE_FIELDS, split_values(values[4])))
        fields = {}
        for mask_name, mask_expression in (("mask", values[1]), ("mask2", values[2]), ("mask3", values[3])):
            for field in mask_fields(mask_expression, mask_name):
                fields[field] = profile_values[field]
        overrides.append(
            {
                "name": f"override_{index}",
                "match": dict(zip(MATCH_FIELDS, match_values)),
                "fields": fields,
            }
        )

    return {
        "schemaVersion": 1,
        "classProfiles": profiles,
        "classRules": class_rules,
        "speciesClassRules": species_rules,
        "overrides": overrides,
    }


def write_if_changed(path: Path, text: str) -> bool:
    old = path.read_text() if path.exists() else None
    if old == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="fail if output is stale")
    parser.add_argument("--import-c-source", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--output-json", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.import_c_source:
        if args.output_json is None:
            parser.error("--import-c-source requires --output-json")
        data = import_c_source(args.import_c_source)
        text = json.dumps(data, indent=2) + "\n"
        write_if_changed(args.output_json, text)
        return 0

    data = load_profiles(args.input)
    generated = emit_generated_c(data)
    if args.check:
        if not args.output.exists():
            print(f"{args.output} does not exist", file=sys.stderr)
            return 1
        if args.output.read_text() != generated:
            print(f"{args.output} is stale; regenerate it", file=sys.stderr)
            return 1
        return 0

    write_if_changed(args.output, generated)
    return 0


if __name__ == "__main__":
    sys.exit(main())
