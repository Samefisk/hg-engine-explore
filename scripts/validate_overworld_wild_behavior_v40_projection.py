#!/usr/bin/env python3
"""Compare the streamed v40 runtime adapter with the frozen v39 source."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import re
import struct
from pathlib import Path

try:
    from overworld_wild_behavior_v39_frozen import FROZEN, load_frozen
except ModuleNotFoundError:
    from scripts.overworld_wild_behavior_v39_frozen import FROZEN, load_frozen

ROOT = Path(__file__).resolve().parents[1]
PROJECTION_SIZE = 3416
PROFILE_FIELDS = (
    "chillState", "alertState", "alertEmote", "alertTime", "alertness", "attentiveState",
    "stamina", "tiredState", "restTime", "chillSpeed", "attentiveSpeed", "tiredSpeed",
    "range", "jumpLevel", "profileId", "spawnState", "chillAction", "chillTarget",
    "alertRange", "playerAdjacentDirectionMasks", "targetSelector", "movementStyle",
    "alertChance", "spawnDestination", "attentiveBattle", "specialAction",
    "hopAllowNonCardinal", "hopMinDistance", "hopMaxDistance", "hopPause", "teleportTime",
    "teleportPause", "alertSpecialAction", "overworldLimit", "spawnDestinationMinDistance",
    "spawnDestinationMaxDistance", "ramAccelerationSteps", "ramMaxSpeed", "chainPauseAction",
    "chillAllowedTile", "attentiveAllowedTile", "tiredAllowedTile", "chillAllowedTile2",
    "attentiveAllowedTile2", "tiredAllowedTile2", "attentiveHopAllowNonCardinal",
    "attentiveHopMinDistance", "attentiveHopMaxDistance", "attentiveHopPause",
    "attentiveTeleportTime", "attentiveTeleportPause", "attentiveRamAccelerationSteps",
    "attentiveRamMaxSpeed", "tiredHopAllowNonCardinal", "tiredHopMinDistance",
    "tiredHopMaxDistance", "tiredHopPause", "tiredTeleportTime", "tiredTeleportPause",
    "tiredRamAccelerationSteps", "tiredRamMaxSpeed", "hopTime",
    "attentiveChaseBoostDistance", "attentiveChaseBoostSpeed", "hopSpinSpeed", "spawnHopTime",
    "attentiveHopSpinSpeed", "attentiveCircleRadius", "attentiveContinueWhenArrived",
    "attentiveAvoidPreviousTile", "chainMovementVariance", "chainPauseVariance",
)
FIELD_INDEX = {name: index for index, name in enumerate(PROFILE_FIELDS)}
OPERATORS = {"replace": 1, "relative": 2, "atLeast": 3, "atMost": 4}
DEAD_DIAGNOSTIC_FIELDS = {"profileId", "attentiveAvoidPreviousTile"}
MASK_BIT_BY_PROFILE_FIELD = (
    0,1,2,20,3,4,5,6,7,8,9,16,10,11,12,13,14,41,15,71,17,18,19,21,
    22,23,24,25,26,27,28,29,30,58,31,32,33,34,68,35,36,37,38,39,40,42,
    43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,59,60,61,62,63,64,65,
    66,67,69,70,
)
MASK_OFFSETS = ((20, 24, 28), (104, 108, 112), (116, 120, 124), (128, 132, 136))


def scalar(value):
    return value.get("value", 0) if isinstance(value, dict) else value


def match_bytes(match):
    return struct.pack("<IH5B", scalar(match["groupMask"]), scalar(match["species"]),
                       scalar(match["terrain"]), scalar(match["minLevel"]),
                       scalar(match["maxLevel"]), scalar(match["shiny"]),
                       scalar(match["behaviorClass"])) + b"\0"


def pack_profile(source):
    return bytes(scalar(source[name]) for name in PROFILE_FIELDS)


def set_mask(out, base, offset, group, bit):
    fmt = "<H" if group == 1 else "<I"
    value = struct.unpack_from(fmt, out, base + offset)[0] | (1 << bit)
    struct.pack_into(fmt, out, base + offset, value)


def has_mask(out, base, offset, group, bit):
    fmt = "<H" if group == 1 else "<I"
    return bool(struct.unpack_from(fmt, out, base + offset)[0] & (1 << bit))


def expected_projection(frozen=FROZEN):
    data = load_frozen(frozen)
    out = bytearray(PROJECTION_SIZE)
    for index, item in enumerate(data["classProfiles"]):
        out[index * 72:(index + 1) * 72] = pack_profile(item["sourceProfile"])
    generic = [item for item in data["classRules"] if item["storage"] == "full"]
    species = [item for item in data["classRules"] if item["storage"] != "full"]
    for index, item in enumerate(generic):
        base = 288 + index * 16
        out[base:base + 12] = match_bytes(item["match"])
        out[base + 12] = scalar(item["behaviorClass"])
        out[base + 13] = item["order"]
    for index, item in enumerate(species):
        struct.pack_into("<HBB", out, 320 + index * 4, scalar(item["match"]["species"]),
                         scalar(item["behaviorClass"]), item["order"])
    member_cursor = 0
    for index, override in enumerate(data["overrides"]):
        base = 772 + index * 212
        out[base:base + 12] = match_bytes(override["match"])
        struct.pack_into("<HHB", out, base + 12, member_cursor, len(override["members"]),
                         scalar(override["targetMode"]))
        for operation in override["operations"]:
            field_name = operation["field"]
            if field_name in DEAD_DIAGNOSTIC_FIELDS:
                continue
            field = FIELD_INDEX[field_name]
            operator = OPERATORS[operation["operator"]]
            mask_bit = MASK_BIT_BY_PROFILE_FIELD[field]
            group = 0 if mask_bit < 27 else 1 if mask_bit < 42 else 2
            bit = mask_bit if group == 0 else mask_bit - 27 if group == 1 else mask_bit - 42
            set_mask(out, base, MASK_OFFSETS[operator - 1][group], group, bit)
            value_offset = 32 + field
            if operator >= 3 and has_mask(out, base, MASK_OFFSETS[1][group], group, bit):
                value_offset = 140 + field
            out[base + value_offset] = scalar(operation["value"]) & 0xFF
        for member in override["members"]:
            struct.pack_into("<H", out, 3104 + member_cursor * 2, scalar(member))
            member_cursor += 1
    if member_cursor != 155:
        raise ValueError(f"frozen member count {member_cursor} != 155")
    return bytes(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--projection", type=Path)
    parser.add_argument("--generate-inc", type=Path)
    parser.add_argument("--frozen", type=Path, default=FROZEN)
    parser.add_argument("--source", type=Path, default=ROOT / "include" / "overworld_wild_behavior_data.h")
    args = parser.parse_args()
    expected = expected_projection(args.frozen)
    defines = {name: int(value, 0) for name, value in re.findall(
        r"^\s*#\s*define\s+(OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_(?:SIZE|MAX_SIZE|CHECKSUM))\s+"
        r"(0[xX][0-9A-Fa-f]+|[0-9]+)(?:u)?\b", args.source.read_text(), re.MULTILINE)}
    required = {"OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_SIZE",
                "OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_MAX_SIZE",
                "OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_CHECKSUM"}
    if set(defines) != required or defines["OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_SIZE"] != len(expected) \
            or len(expected) > defines["OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_MAX_SIZE"] \
            or defines["OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_CHECKSUM"] != binascii.crc32(expected) & 0xFFFFFFFF:
        raise SystemExit("runtime projection size/max/checksum header contract mismatch")
    if args.generate_inc is not None:
        rendered = ["/* Independently encoded frozen v39 runtime compatibility projection. */"]
        for offset in range(0, len(expected), 16):
            rendered.append("    " + ", ".join(f"0x{value:02X}" for value in expected[offset:offset + 16]) + ",")
        args.generate_inc.write_text("\n".join(rendered) + "\n")
        print(f"runtime compatibility projection generated: {len(expected)} bytes sha256={hashlib.sha256(expected).hexdigest()}")
        return
    if args.projection is None:
        raise SystemExit("--projection or --generate-inc is required")
    actual = args.projection.read_bytes()
    if actual != expected:
        mismatch = next(index for index, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]) \
            if len(actual) == len(expected) else min(len(actual), len(expected))
        raise SystemExit(f"runtime projection mismatch at byte {mismatch}: actual={len(actual)} expected={len(expected)}")
    print(f"runtime compatibility projection: {len(actual)} bytes match frozen v39 authored source")


if __name__ == "__main__":
    main()
