#!/usr/bin/env python3
"""Emit the checked overlay-161 layout used by shared player HP observation."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile


OVERLAY_ID = 161
BASE = 0x01FFA580
CAPACITY = 0x5A80
MAGIC = 0x484C5048
VERSION = 2
ENTRY_SIZE = 0x34
RUNTIME_SIZE = 0x3C
STATE_SIZE = 20
RUNTIME_FIELDS = (
    "PlayerHealthState health", "SaveData *saveData",
    "FieldSystem *fieldSystem", "SysTask *endTask",
    "LocalMapObject *playerObject", "u32 sequence", "s32 lastX",
    "s32 lastZ", "s32 beginX", "s32 beginZ", "u8 initialized",
    "u8 havePose", "u8 movedAtBegin",
)
STATE_FIELDS = (
    "u32 lastFrame", "u32 acceptedHits", "u16 restFrames",
    "u16 protectionFrames", "u16 healRemainder", "u8 hp",
    "u8 frameActive", "u8 hitThisFrame",
    "u8 protectionAdvancedThisFrame", "u8 recoveryPending",
    "u8 lastDamage",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def symbol_table(linked, objdump="arm-none-eabi-objdump"):
    output = subprocess.check_output([objdump, "-t", str(linked)], text=True)
    for name in ("__memset_from_thumb", "__memcpy_from_thumb"):
        if name in output:
            raise ValueError(f"player HP {name} call crosses into ARM state")
    wanted = {"gPlayerHealthOverlayEntry", "sPlayerHealth",
              "PlayerHealthField_GetState", "sPresentation",
              "PlayerHealthPresentation_GetReceipt", "sCombat",
              "gOverworldCombatEntry", "gOverworldWildResidentData"}
    found = {}
    for line in output.splitlines():
        parts = line.split()
        # Absolute imports omit the function/object column in objdump output.
        if len(parts) >= 5 and parts[-1] in wanted:
            found[parts[-1]] = (int(parts[0], 16), int(parts[-2], 16))
    if set(found) != wanted:
        raise ValueError("player HP linked symbols are missing")
    return found


def fields_from_source(source, type_name):
    text = source.read_text()
    match = re.search(r"typedef struct " + type_name + r"\s*\{(.*?)\}\s*"
                      + type_name + r"\s*;", text, re.S)
    if match is None:
        raise ValueError(type_name + " declaration is missing")
    return tuple(re.findall(r"^\s*([^/\n;]+);", match.group(1), re.M))


def checked_layout(runtime_source, model_header, save_header):
    if fields_from_source(runtime_source, "PlayerHealthFieldRuntime") != RUNTIME_FIELDS:
        raise ValueError("player HP runtime field order changed")
    if fields_from_source(model_header, "PlayerHealthState") != STATE_FIELDS:
        raise ValueError("player HP model field order changed")
    save = save_header.read_text()
    if not all(part in save for part in (
            "u8 playerHealthSignature[3]", "u8 playerHealthState[3]",
            "playerHealthSignature) == 0x2D5",
            "playerHealthState) == 0x2DD")):
        raise ValueError("player HP save record layout changed")
    max_hp = re.search(r"^#define PLAYER_HEALTH_MAX_HP\s+(\d+)\s*$",
                       model_header.read_text(), re.M)
    if max_hp is None or int(max_hp.group(1)) != 100:
        raise ValueError("player HP maximum changed")
    return {
        "stateSize": STATE_SIZE,
        "runtimeSize": RUNTIME_SIZE,
        "stateOffsets": {
            "lastFrame": 0, "acceptedHits": 4, "restFrames": 8,
            "protectionFrames": 10, "healRemainder": 12, "hp": 14,
            "frameActive": 15, "hitThisFrame": 16,
            "protectionAdvancedThisFrame": 17, "recoveryPending": 18,
            "lastDamage": 19,
        },
        "ownerOffsets": {"saveData": 20, "fieldSystem": 24,
                         "initialized": 56},
        "maxHp": 100,
        "save": {"dynamicRegion": 0x10, "arrayHeaders": 0x2F014,
                 "arrayHeaderSize": 0x10, "miscBlock": 9,
                 "signature": 0x2D5, "state": 0x2DD,
                 "magic": [ord("P"), ord("H"), 1],
                 "minSpawn": 1, "maxSpawn": 30},
    }



PRESENTATION_FIELDS = (
    "FieldSystem *field", "PlayerHealthCharBlock charBlock",
    "PlayerHealthPaletteData paletteData", "PlayerHealthPaletteTask paletteTask",
    "PlayerHealthPresentationReceipt receipt",
    "u8 bound", "u8 textureKey", "u8 paletteSlot",
)
RECEIPT_FIELDS = ("u8 requestedFill", "u8 drawnFill", "u8 danger",
                  "u8 submittedSprites")


def checked_presentation(symbols, image, source, header):
    if (fields_from_source(source, "PlayerHealthPresentationRuntime")
            != PRESENTATION_FIELDS
            or fields_from_source(header, "PlayerHealthPresentationReceipt")
            != RECEIPT_FIELDS):
        raise ValueError("player HP presentation layout changed")
    nested = {
        "PlayerHealthCharBlock": ("u32 size", "u32 offset", "u16 vram", "u16 isAtEnd"),
        "PlayerHealthPaletteData": ("u32 fmt", "BOOL extended", "u32 size", "void *raw"),
        "PlayerHealthPaletteTask": ("PlayerHealthPaletteData *data", "u32 vram", "int count", "int id"),
    }
    if any(fields_from_source(source, name) != fields
           for name, fields in nested.items()):
        raise ValueError("player HP presentation nested layout changed")
    address, size = symbols["sPresentation"]
    getter, getter_size = symbols["PlayerHealthPresentation_GetReceipt"]
    if (size != 0x38 or getter_size != 12 or address % 4 or getter % 4
            or not BASE + ENTRY_SIZE <= address <= BASE + len(image) - size
            or not BASE + ENTRY_SIZE <= getter <= BASE + len(image) - getter_size
            or not (getter + getter_size <= address or address + size <= getter)):
        raise ValueError("player HP presentation symbols are invalid")
    code = image[getter - BASE:getter - BASE + getter_size]
    # Authenticate the native getter: ldr r0,[pc,#4]; add r0,#0x30;
    # bx lr; nop; literal sPresentation. No native call is needed by readers.
    if code != struct.pack("<4HI", 0x4801, 0x3030, 0x4770, 0x46C0, address):
        raise ValueError("player HP presentation getter layout differs")
    return {"version": 3, "address": address, "size": size,
            "fieldOffset": 0, "receiptOffset": 0x30, "receiptSize": 4,
            "receiptOffsets": {"requestedFill": 0, "drawnFill": 1,
                               "danger": 2, "submittedSprites": 3},
            "boundOffset": 0x34, "textureKeyOffset": 0x35,
            "paletteSlotOffset": 0x36,
            "getter": {"address": getter, "size": getter_size,
                       "bytesHex": code.hex()}}


COMBAT_TARGET_FIELDS = (
    "u32 personality", "u16 mapId", "u16 mapGeneration",
    "u16 encounterGeneration", "u16 species", "u16 maxHp",
    "u16 currentHp", "u16 hitCount", "u8 form", "u8 level",
    "u8 initialized", "u8 immunityFrames", "u8 knockbackOptions",
    "u8 knockbackDirection", "u8 knockbackPending", "u8 lastDamage",
    "u16 crashMotionIdentity",
)
COMBAT_TARGET_OFFSETS = dict(personality=0, mapId=4, mapGeneration=6,
    encounterGeneration=8, species=10, maxHp=12, currentHp=14, hitCount=16,
    form=18, level=19, initialized=20, immunityFrames=21,
    knockbackOptions=22, knockbackDirection=23, knockbackPending=24,
    lastDamage=25, crashMotionIdentity=26)


def checked_combat(symbols, image, source):
    if (fields_from_source(source, "OverworldCombatTarget") != COMBAT_TARGET_FIELDS
            or fields_from_source(source, "OverworldCombatState") != (
                "FieldSystem *fieldSystem", "SaveData *saveData",
                "const OverworldWildSpawnState *frameState",
                "OverworldCombatTarget targets[OW_WILD_MAX_SPAWNS]")):
        raise ValueError("Pokémon combat field order changed")
    address, size = symbols["sCombat"]
    entry, entry_size = symbols["gOverworldCombatEntry"]
    resident, _ = symbols["gOverworldWildResidentData"]
    if (size != 292 or address % 4 or entry != 0x01FFD580
            or entry_size != 52 or not entry + entry_size <= address
            or address + size > BASE + len(image)
            or not 0x02000000 <= resident <= 0x02400000 - 22):
        raise ValueError("Pokémon combat symbols differ from the native layout")
    data = image[entry - BASE:entry - BASE + entry_size]
    if struct.unpack_from("<IHH", data) != (0x434F4D42, 1, entry_size):
        raise ValueError("Pokémon combat entry magic/version/size differs")
    return {"version": 1, "address": address, "size": size,
            "ownerOffsets": {"fieldSystem": 0, "saveData": 4, "frameState": 8},
            "targetOffset": 12, "targetCount": 10, "targetSize": 28,
            "targetOffsets": COMBAT_TARGET_OFFSETS,
            "wildSavedHpAddress": resident + 2,
            "entry": {"address": entry, "size": entry_size,
                      "bytesHex": data.hex()}}


def make_descriptor(linked, binary, runtime_source, model_header,
                    save_header, *, objdump="arm-none-eabi-objdump"):
    symbols = symbol_table(linked, objdump)
    image = binary.read_bytes()
    if not ENTRY_SIZE <= len(image) <= CAPACITY:
        raise ValueError("player HP image is outside its ITCM reservation")
    entry, entry_size = symbols["gPlayerHealthOverlayEntry"]
    runtime, runtime_size = symbols["sPlayerHealth"]
    getter, _ = symbols["PlayerHealthField_GetState"]
    if (entry, entry_size) != (BASE, ENTRY_SIZE):
        raise ValueError("player HP entry moved or changed size")
    if runtime_size != RUNTIME_SIZE or not BASE + ENTRY_SIZE <= runtime \
            <= BASE + len(image) - RUNTIME_SIZE:
        raise ValueError("player HP runtime moved outside image or changed size")
    if struct.unpack_from("<IHH", image) != (MAGIC, VERSION, ENTRY_SIZE):
        raise ValueError("player HP entry magic/version/size differs")
    if struct.unpack_from("<I", image, 16)[0] != getter | 1:
        raise ValueError("player HP getState callback differs from linked symbol")
    layout = checked_layout(runtime_source, model_header, save_header)
    presentation_source = runtime_source.parent / "player_health_presentation.c"
    presentation_header = model_header.parent / "player_health_presentation.h"
    presentation = checked_presentation(symbols, image, presentation_source,
                                        presentation_header)
    combat_source = runtime_source.parent / "player_health_pokemon.c"
    combat = checked_combat(symbols, image, combat_source)
    return {
        "formatVersion": 1,
        "overlay": {"id": OVERLAY_ID, "base": BASE, "capacity": CAPACITY,
                    "fileSize": len(image), "sha256": digest(image)},
        "entry": {"address": entry, "size": ENTRY_SIZE,
                  "magic": MAGIC, "version": VERSION,
                  "getState": getter | 1,
                  "bytesHex": image[:ENTRY_SIZE].hex()},
        "presentation": presentation,
        "combat": combat,
        "runtime": {"address": runtime, "size": runtime_size,
                    **layout},
        "sources": {name: digest(path.read_bytes()) for name, path in (
            ("linked", linked), ("runtime", runtime_source),
            ("model", model_header), ("save", save_header),
            ("presentation", presentation_source),
            ("presentationHeader", presentation_header),
            ("combat", combat_source))},
    }


def write_descriptor(path, descriptor):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix="player-health-", suffix=".json",
                                         dir=path.parent)
    try:
        with os.fdopen(handle, "w") as output:
            json.dump(descriptor, output, indent=2, sort_keys=True)
            output.write("\n")
        os.replace(temporary, path)
    except Exception:
        os.unlink(temporary)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--linked", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--runtime-source", type=Path, required=True)
    parser.add_argument("--model-header", type=Path, required=True)
    parser.add_argument("--save-header", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--objdump", default="arm-none-eabi-objdump")
    args = parser.parse_args()
    result = make_descriptor(args.linked, args.binary, args.runtime_source,
                             args.model_header, args.save_header,
                             objdump=args.objdump)
    write_descriptor(args.output, result)
    print("overlay 161 player HP descriptor:", result["overlay"]["sha256"])


if __name__ == "__main__":
    main()
