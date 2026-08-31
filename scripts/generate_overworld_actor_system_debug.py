#!/usr/bin/env python3

"""Verify overlay 158's resident ABI and emit its agent debug descriptor."""

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import tempfile


OVERLAY_ID = 158
OVERLAY_BASE = 0x023B6B00
OVERLAY_END = 0x023BAB00
FILE_SIZE = 0x3000
STATE_ADDRESS = OVERLAY_BASE + FILE_SIZE
ENTRY_ADDRESS = OVERLAY_BASE
COMPAT_ADDRESS = OVERLAY_BASE + 0x18
DEBUG_ADDRESS = OVERLAY_BASE + 0x38
SERVICE_DIRECTORY_ADDRESS = OVERLAY_BASE + 0x78
SERVICE_ENTRY_SIZE = 0x10
SERVICE_NAMES = ("resolver", "motion", "population", "movementPolicy")
SERVICE_MAGICS = (0x5250574F, 0x534D574F, 0x5450574F, 0x504D574F)
RESOLVER_CALLBACKS = (
    "BehaviorResolver_Resolve",
    "BehaviorResolver_InspectClass",
)
MOTION_CALLBACKS = (
    "OverworldActorSystem_MotionDispatchImpl",
    "OverworldActorSystem_BeginLegacyMotion",
)
POPULATION_CALLBACKS = (
    "OverworldActorSystem_PopulationFrameImpl",
    "OverworldActorSystem_PopulationResetImpl",
)
MOVEMENT_POLICY_SYMBOLS = (
    "sActorMovementPolicy",
    "ActorSystem_ValidateMovementPolicy",
)

MAIN_CALLBACKS = (
    "OverworldActorSystem_ValidateImpl",
    "OverworldActorSystem_ApplyImpl",
    "OverworldActorSystem_TickImpl",
    "OverworldActorSystem_InspectImpl",
)
COMPAT_CALLBACKS = (
    "OverworldActorSystem_CompatibilityBindImpl",
    "OverworldActorSystem_CompatibilityUpdateImpl",
    "OverworldActorSystem_CompatibilityUnbindImpl",
    "OverworldActorSystem_CompatibilityAdvanceFieldEpochImpl",
    "OverworldActorSystem_CompatibilityRecordTraceImpl",
    "OverworldActorSystem_CompatibilityGetFieldEpochImpl",
)
FIXED_SYMBOLS = {
    "gOverworldActorSystemEntry": (ENTRY_ADDRESS, 24),
    "gOverworldActorCompatibilityEntry": (COMPAT_ADDRESS, 32),
    "gOverworldActorSystemDebugLayout": (DEBUG_ADDRESS, 64),
    "gOverworldActorSystemResolverServiceEntry": (
        SERVICE_DIRECTORY_ADDRESS, SERVICE_ENTRY_SIZE),
    "gOverworldActorSystemMotionServiceEntry": (
        SERVICE_DIRECTORY_ADDRESS + SERVICE_ENTRY_SIZE, SERVICE_ENTRY_SIZE),
    "gOverworldActorSystemPopulationServiceEntry": (
        SERVICE_DIRECTORY_ADDRESS + SERVICE_ENTRY_SIZE * 2, SERVICE_ENTRY_SIZE),
    "gOverworldActorSystemMovementPolicyServiceEntry": (
        SERVICE_DIRECTORY_ADDRESS + SERVICE_ENTRY_SIZE * 3, SERVICE_ENTRY_SIZE),
}
STATE_SYMBOL = "gOverworldActorSystemState"


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--linked", required=True)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--packaged", required=True)
    parser.add_argument("--overlay-table", required=True)
    parser.add_argument("--header", required=True)
    parser.add_argument("--internal-header", required=True)
    parser.add_argument("--resolver-header", required=True)
    parser.add_argument("--motion-header", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--objdump", default="arm-none-eabi-objdump")
    return parser.parse_args()


def read_symbols(objdump, linked):
    wanted = set(FIXED_SYMBOLS)
    wanted.add(STATE_SYMBOL)
    wanted.update(MAIN_CALLBACKS)
    wanted.update(COMPAT_CALLBACKS)
    wanted.update(RESOLVER_CALLBACKS)
    wanted.update(MOTION_CALLBACKS)
    wanted.update(POPULATION_CALLBACKS)
    wanted.update(MOVEMENT_POLICY_SYMBOLS)
    symbols = {}
    output = subprocess.check_output([objdump, "-t", linked], text=True)
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[-1] in wanted:
            symbols[parts[-1]] = {
                "address": int(parts[0], 16),
                "size": int(parts[-2], 16),
            }
    missing = sorted(wanted.difference(symbols))
    if missing:
        raise RuntimeError("overlay 158 is missing symbols: " + ", ".join(missing))
    return symbols


def verify_fixed_symbols(symbols):
    for name, expected in FIXED_SYMBOLS.items():
        actual = (symbols[name]["address"], symbols[name]["size"])
        if actual != expected:
            raise RuntimeError(
                f"{name} changed: address=0x{actual[0]:08X} size={actual[1]}, "
                f"expected address=0x{expected[0]:08X} size={expected[1]}"
            )
    state = symbols[STATE_SYMBOL]
    if state["address"] != STATE_ADDRESS:
        raise RuntimeError(
            f"resident state moved to 0x{state['address']:08X}; "
            f"expected 0x{STATE_ADDRESS:08X}"
        )
    if state["address"] + state["size"] > OVERLAY_END:
        raise RuntimeError("resident state exceeds overlay 158's fixed block")


def verify_pointer(pointer, symbol, symbols):
    expected = symbols[symbol]["address"] | 1
    if pointer != expected:
        raise RuntimeError(
            f"ABI pointer for {symbol} is 0x{pointer:08X}; "
            f"expected 0x{expected:08X}"
        )
    if pointer & 1 == 0 or not (OVERLAY_BASE <= (pointer & ~1) < OVERLAY_END):
        raise RuntimeError(f"ABI pointer for {symbol} is not resident Thumb code")


def verify_binary(binary, packaged, symbols):
    with open(binary, "rb") as file:
        image = file.read()
    with open(packaged, "rb") as file:
        installed = file.read()
    if image != installed:
        raise RuntimeError("packaged overlay 158 differs from its linked binary")
    if len(image) != FILE_SIZE:
        raise RuntimeError(
            f"overlay 158 file size is 0x{len(image):X}; expected 0x{FILE_SIZE:X}"
        )

    main = struct.unpack_from("<IHH4I", image, 0)
    if main[:3] != (0x5341574F, 1, 24):
        raise RuntimeError("public actor facade header changed")
    for pointer, symbol in zip(main[3:], MAIN_CALLBACKS):
        verify_pointer(pointer, symbol, symbols)

    compat = struct.unpack_from("<IHH6I", image, 0x18)
    if compat[:3] != (0x4341574F, 1, 32):
        raise RuntimeError("actor compatibility facade header changed")
    for pointer, symbol in zip(compat[3:], COMPAT_CALLBACKS):
        verify_pointer(pointer, symbol, symbols)

    debug = struct.unpack_from("<IHHIII22H", image, 0x38)
    if debug[:6] != (
        0x4C44574F, 1, 64, OVERLAY_BASE, OVERLAY_END, STATE_ADDRESS
    ):
        raise RuntimeError("actor debug layout header changed")
    if debug[6:9] != (12, 8, 32):
        raise RuntimeError("actor facade capacities changed")
    if debug[9:17] != (12, 32, 24, 24, 176, 88, 36, 32):
        raise RuntimeError("actor facade value-object sizes changed")
    if debug[23:27] != (0x78, SERVICE_ENTRY_SIZE, 4, 0x1000):
        raise RuntimeError("actor private service directory layout changed")
    if debug[17] != symbols[STATE_SYMBOL]["size"]:
        raise RuntimeError("debug layout state size differs from linked state symbol")

    services = []
    resolver = struct.unpack_from("<IHHII", image, 0x78)
    if resolver[:3] != (SERVICE_MAGICS[0], 1, SERVICE_ENTRY_SIZE):
        raise RuntimeError("resolver service entry header changed")
    for pointer, symbol in zip(resolver[3:], RESOLVER_CALLBACKS):
        verify_pointer(pointer, symbol, symbols)
    services.append({
        "name": SERVICE_NAMES[0],
        "address": SERVICE_DIRECTORY_ADDRESS,
        "size": SERVICE_ENTRY_SIZE,
        "version": 1,
        "status": "available",
        "callbacks": {
            name: symbols[symbol]["address"] | 1
            for name, symbol in zip(
                ("resolve", "inspectClass"), RESOLVER_CALLBACKS)
        },
    })

    motion = struct.unpack_from("<IHHII", image, 0x88)
    if motion[:3] != (SERVICE_MAGICS[1], 1, SERVICE_ENTRY_SIZE):
        raise RuntimeError("motion service entry header changed")
    for pointer, symbol in zip(motion[3:], MOTION_CALLBACKS):
        verify_pointer(pointer, symbol, symbols)
    services.append({
        "name": SERVICE_NAMES[1],
        "address": SERVICE_DIRECTORY_ADDRESS + SERVICE_ENTRY_SIZE,
        "size": SERVICE_ENTRY_SIZE,
        "version": 1,
        "status": "available",
        "callbacks": {
            name: symbols[symbol]["address"] | 1
            for name, symbol in zip(
                ("dispatch", "beginLegacy"), MOTION_CALLBACKS)
        },
    })

    population = struct.unpack_from("<IHHII", image, 0x98)
    if population[:3] != (SERVICE_MAGICS[2], 1, SERVICE_ENTRY_SIZE):
        raise RuntimeError("population service entry header changed")
    for pointer, symbol in zip(population[3:], POPULATION_CALLBACKS):
        verify_pointer(pointer, symbol, symbols)
    services.append({
        "name": SERVICE_NAMES[2],
        "address": OVERLAY_BASE + 0x98,
        "size": SERVICE_ENTRY_SIZE,
        "version": 1,
        "status": "available",
        "callbacks": {
            name: symbols[symbol]["address"] | 1
            for name, symbol in zip(("frame", "reset"), POPULATION_CALLBACKS)
        },
    })

    movement = struct.unpack_from("<IHHII", image, 0xA8)
    if movement[:3] != (SERVICE_MAGICS[3], 1, SERVICE_ENTRY_SIZE):
        raise RuntimeError("movement-policy service entry header changed")
    expected_policy = symbols[MOVEMENT_POLICY_SYMBOLS[0]]["address"]
    if movement[3] != expected_policy:
        raise RuntimeError("movement-policy data pointer changed")
    verify_pointer(movement[4], MOVEMENT_POLICY_SYMBOLS[1], symbols)
    services.append({
        "name": SERVICE_NAMES[3],
        "address": OVERLAY_BASE + 0xA8,
        "size": SERVICE_ENTRY_SIZE,
        "version": 1,
        "status": "available",
        "policy": expected_policy,
        "callbacks": {
            "validate": symbols[MOVEMENT_POLICY_SYMBOLS[1]]["address"] | 1,
        },
    })
    return image, debug, services


def verify_overlay_table(path, state_size):
    with open(path, "rb") as file:
        file.seek(OVERLAY_ID * 0x20)
        row_bytes = file.read(0x20)
    if len(row_bytes) != 0x20:
        raise RuntimeError("overlay table does not contain overlay 158")
    row = struct.unpack("<8I", row_bytes)
    expected = (OVERLAY_ID, OVERLAY_BASE, FILE_SIZE, state_size, 0, 0,
                OVERLAY_ID, 0)
    if row != expected:
        raise RuntimeError(
            "overlay 158 table row changed: actual="
            + ",".join(f"0x{value:X}" for value in row)
        )
    if row[1] + row[2] + row[3] > OVERLAY_END:
        raise RuntimeError("overlay 158 package exceeds its resident memory block")
    return row


def parse_enums(headers):
    enums = {}
    pattern = re.compile(
        r"typedef\s+enum\s+(\w+)\s*\{(.*?)\}\s*\1\s*;",
        re.DOTALL,
    )
    item_pattern = re.compile(
        r"\b([A-Z][A-Z0-9_]+)\s*=\s*(0[xX][0-9A-Fa-f]+|\d+)\s*,")
    for header in headers:
        with open(header, "r", encoding="utf-8") as file:
            source = file.read()
        for match in pattern.finditer(source):
            values = {
                name: int(value, 0)
                for name, value in item_pattern.findall(match.group(2))
            }
            if values:
                enums[match.group(1)] = values
    if not enums:
        raise RuntimeError("no actor-system enums found for the debug descriptor")
    return enums


def write_descriptor(path, image, symbols, debug, services, row, enums):
    descriptor = {
        "formatVersion": 1,
        "overlay": {
            "id": OVERLAY_ID,
            "base": OVERLAY_BASE,
            "end": OVERLAY_END,
            "capacity": OVERLAY_END - OVERLAY_BASE,
            "fileSize": len(image),
            "bssSize": row[3],
            "sha256": hashlib.sha256(image).hexdigest(),
        },
        "facade": {
            "address": ENTRY_ADDRESS,
            "version": 1,
            "size": 24,
            "callbacks": {
                name: symbols[symbol]["address"] | 1
                for name, symbol in zip(
                    ("validate", "apply", "tick", "inspect"), MAIN_CALLBACKS)
            },
        },
        "compatibility": {
            "address": COMPAT_ADDRESS,
            "version": 1,
            "size": 32,
            "callbacks": {
                name: symbols[symbol]["address"] | 1
                for name, symbol in zip(
                    ("bind", "update", "unbind", "advanceFieldEpoch",
                     "recordTrace", "getFieldEpoch"), COMPAT_CALLBACKS)
            },
        },
        "debugLayout": {
            "address": DEBUG_ADDRESS,
            "version": 1,
            "size": 64,
        },
        "state": {
            "address": STATE_ADDRESS,
            "size": symbols[STATE_SYMBOL]["size"],
            "capacity": debug[26],
            "offsets": {
                "fieldEpoch": debug[18],
                "actors": debug[19],
                "traceHeader": debug[20],
                "traceEvents": debug[21],
                "commandQueue": debug[22],
            },
        },
        "capacities": {
            "actors": debug[6],
            "commands": debug[7],
            "traceEvents": debug[8],
        },
        "structures": {
            "handle": debug[9],
            "command": debug[10],
            "reply": debug[11],
            "query": debug[12],
            "snapshot": debug[13],
            "actorState": debug[14],
            "traceHeader": debug[15],
            "traceEvent": debug[16],
            "behaviorClassSelection": 8,
            "motionServiceCall": 44,
            "motionIntent": 18,
            "motionCandidate": 16,
            "motionPlan": 40,
            "motionState": 52,
            "motionSample": 36,
        },
        "privateServices": services,
        "enums": enums,
    }
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix="actor-system-", suffix=".json",
                                         dir=directory)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(descriptor, file, indent=2, sort_keys=True)
            file.write("\n")
        os.replace(temporary, path)
    except Exception:
        os.unlink(temporary)
        raise


def main():
    args = parse_arguments()
    symbols = read_symbols(args.objdump, args.linked)
    verify_fixed_symbols(symbols)
    image, debug, services = verify_binary(args.binary, args.packaged, symbols)
    row = verify_overlay_table(args.overlay_table, symbols[STATE_SYMBOL]["size"])
    enums = parse_enums((
        args.header,
        args.internal_header,
        args.resolver_header,
        args.motion_header,
    ))
    write_descriptor(args.output, image, symbols, debug, services, row, enums)
    print(
        "overlay 158 actor ABI gate: "
        f"entry=0x{ENTRY_ADDRESS:08X} state=0x{STATE_ADDRESS:08X} "
        f"sha256={hashlib.sha256(image).hexdigest()}"
    )


if __name__ == "__main__":
    main()
