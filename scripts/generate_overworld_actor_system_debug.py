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
OVERLAY_LOAD_ADDRESS = 0x023B65A0
OVERLAY_BASE = 0x023B6B00
OVERLAY_END = 0x023BAB00
STATE_ADDRESS = OVERLAY_BASE + 0x3670
FILE_SIZE = STATE_ADDRESS - OVERLAY_LOAD_ADDRESS
ENTRY_ADDRESS = OVERLAY_BASE
COMPAT_ADDRESS = OVERLAY_BASE + 0x18
DEBUG_ADDRESS = OVERLAY_BASE + 0x38
SERVICE_DIRECTORY_ADDRESS = OVERLAY_BASE + 0x78
SERVICE_ENTRY_SIZE = 0x10
POLICY_STATE_SIZE = 32
SERVICE_NAMES = ("resolver", "motion", "population", "movementPolicy")
SERVICE_MAGICS = (0x5250574F, 0x534D574F, 0x5450574F, 0x504D574F)
RESOLVER_CALLBACKS = (
    "BehaviorResolver_Resolve",
    "BehaviorResolver_InspectClass",
)
MOTION_CALLBACKS = (
    "ActorSystem_RequestMotion",
    "ActorSystem_EngineBoundary",
)
POPULATION_CALLBACKS = (
    "OverworldActorSystem_PopulationFrameImpl",
    "OverworldActorSystem_PopulationControlImpl",
)
MOVEMENT_POLICY_SYMBOLS = (
    "sActorMovementPolicy",
    "gOverworldBehaviorConditionAdapterEntry",
)

MAIN_CALLBACKS = (
    "OverworldActorSystem_ValidateImpl",
    "OverworldActorSystem_ApplyImpl",
    "OverworldActorSystem_TickImpl",
    "OverworldActorSystem_InspectImpl",
)
COMPAT_CALLBACKS = (
    "OverworldActorSystem_CompatibilityBindImpl",
    None,
    "OverworldActorSystem_CompatibilityUnbindImpl",
    "OverworldActorSystem_CompatibilityTransitionImpl",
    "OverworldActorSystem_CompatibilityRecordTraceImpl",
    "OverworldActorSystem_CompatibilityGetContextImpl",
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
    "OverworldActorSystem_SelectMovementLocomotion": (
        OVERLAY_BASE + 0xB8, 0x0C),
    "OverworldActorSystem_SelectMovementTarget": (
        OVERLAY_BASE + 0xCC, 0x0C),
}
STATE_SYMBOL = "gOverworldActorSystemState"
PUBLIC_LAYOUT_MACROS = {
    "handle": "OVERWORLD_ACTOR_DEBUG_HANDLE_FORMAT",
    "actorState": "OVERWORLD_ACTOR_DEBUG_STATE_FORMAT",
}


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
    wanted.update(symbol for symbol in COMPAT_CALLBACKS if symbol is not None)
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
    if pointer & 1 == 0 or not (
        OVERLAY_LOAD_ADDRESS <= (pointer & ~1) < OVERLAY_END
    ):
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

    main = struct.unpack_from(
        "<IHH4I", image, ENTRY_ADDRESS - OVERLAY_LOAD_ADDRESS)
    if main[:3] != (0x5341574F, 2, 24):
        raise RuntimeError("public actor facade header changed")
    for pointer, symbol in zip(main[3:], MAIN_CALLBACKS):
        verify_pointer(pointer, symbol, symbols)

    compat = struct.unpack_from(
        "<IHH6I", image, COMPAT_ADDRESS - OVERLAY_LOAD_ADDRESS)
    if compat[:3] != (0x4341574F, 3, 32):
        raise RuntimeError("actor compatibility facade header changed")
    for pointer, symbol in zip(compat[3:], COMPAT_CALLBACKS):
        if symbol is None:
            if pointer != 0:
                raise RuntimeError("retired compatibility update slot is not zero")
        else:
            verify_pointer(pointer, symbol, symbols)

    debug = struct.unpack_from(
        "<IHHIII22H", image, DEBUG_ADDRESS - OVERLAY_LOAD_ADDRESS)
    if debug[:6] != (
        0x4C44574F, 1, 64, OVERLAY_BASE, OVERLAY_END, STATE_ADDRESS
    ):
        raise RuntimeError("actor debug layout header changed")
    if debug[6:9] != (10, 2, 16):
        raise RuntimeError("actor facade capacities changed")
    if debug[9:17] != (12, 32, 24, 24, 176, 88, 36, 32):
        raise RuntimeError("actor facade value-object sizes changed")
    if debug[23:27] != (0x78, SERVICE_ENTRY_SIZE, 4, 0x990):
        raise RuntimeError("actor private service directory layout changed")
    if debug[27] != debug[14] + 52 + 32:
        raise RuntimeError("actor runtime slot layout changed")
    if debug[17] != symbols[STATE_SYMBOL]["size"]:
        raise RuntimeError("debug layout state size differs from linked state symbol")

    services = []
    resolver = struct.unpack_from(
        "<IHHII", image, SERVICE_DIRECTORY_ADDRESS - OVERLAY_LOAD_ADDRESS)
    if resolver[:3] != (SERVICE_MAGICS[0], 2, SERVICE_ENTRY_SIZE):
        raise RuntimeError("resolver service entry header changed")
    for pointer, symbol in zip(resolver[3:], RESOLVER_CALLBACKS):
        verify_pointer(pointer, symbol, symbols)
    services.append({
        "name": SERVICE_NAMES[0],
        "address": SERVICE_DIRECTORY_ADDRESS,
        "size": SERVICE_ENTRY_SIZE,
        "version": 2,
        "status": "available",
        "callbacks": {
            name: symbols[symbol]["address"] | 1
            for name, symbol in zip(
                ("resolve", "inspectClass"), RESOLVER_CALLBACKS)
        },
    })

    motion = struct.unpack_from(
        "<IHHII",
        image,
        SERVICE_DIRECTORY_ADDRESS + SERVICE_ENTRY_SIZE - OVERLAY_LOAD_ADDRESS,
    )
    if motion[:3] != (SERVICE_MAGICS[1], 6, SERVICE_ENTRY_SIZE):
        raise RuntimeError("motion service entry header changed")
    for pointer, symbol in zip(motion[3:], MOTION_CALLBACKS):
        verify_pointer(pointer, symbol, symbols)
    services.append({
        "name": SERVICE_NAMES[1],
        "address": SERVICE_DIRECTORY_ADDRESS + SERVICE_ENTRY_SIZE,
        "size": SERVICE_ENTRY_SIZE,
        "version": 6,
        "status": "available",
        "callbacks": {
            name: symbols[symbol]["address"] | 1
            for name, symbol in zip(("request", "boundary"), MOTION_CALLBACKS)
        },
    })

    population = struct.unpack_from(
        "<IHHII",
        image,
        SERVICE_DIRECTORY_ADDRESS + SERVICE_ENTRY_SIZE * 2
            - OVERLAY_LOAD_ADDRESS,
    )
    if population[:3] != (SERVICE_MAGICS[2], 3, SERVICE_ENTRY_SIZE):
        raise RuntimeError("population service entry header changed")
    for pointer, symbol in zip(population[3:], POPULATION_CALLBACKS):
        verify_pointer(pointer, symbol, symbols)
    services.append({
        "name": SERVICE_NAMES[2],
        "address": OVERLAY_BASE + 0x98,
        "size": SERVICE_ENTRY_SIZE,
        "version": 3,
        "status": "available",
        "callbacks": {
            name: symbols[symbol]["address"] | 1
            for name, symbol in zip(("frame", "control"), POPULATION_CALLBACKS)
        },
    })

    movement = struct.unpack_from(
        "<IHHII",
        image,
        SERVICE_DIRECTORY_ADDRESS + SERVICE_ENTRY_SIZE * 3
            - OVERLAY_LOAD_ADDRESS,
    )
    if movement[:3] != (SERVICE_MAGICS[3], 5, SERVICE_ENTRY_SIZE):
        raise RuntimeError("movement-policy service entry header changed")
    expected_policy = symbols[MOVEMENT_POLICY_SYMBOLS[0]]["address"]
    expected_adapter = symbols[MOVEMENT_POLICY_SYMBOLS[1]]["address"]
    if movement[3] != expected_policy:
        raise RuntimeError("movement-policy data pointer changed")
    if movement[4] != expected_adapter:
        raise RuntimeError("condition-adapter data pointer changed")
    services.append({
        "name": SERVICE_NAMES[3],
        "address": OVERLAY_BASE + 0xA8,
        "size": SERVICE_ENTRY_SIZE,
        "version": 5,
        "status": "available",
        "policy": expected_policy,
        "conditionAdapter": expected_adapter,
    })
    return image, debug, services


def verify_overlay_table(path, state_size):
    with open(path, "rb") as file:
        file.seek(OVERLAY_ID * 0x20)
        row_bytes = file.read(0x20)
    if len(row_bytes) != 0x20:
        raise RuntimeError("overlay table does not contain overlay 158")
    row = struct.unpack("<8I", row_bytes)
    expected = (OVERLAY_ID, OVERLAY_LOAD_ADDRESS, FILE_SIZE, state_size, 0, 0,
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


def parse_public_layouts(header):
    with open(header, "r", encoding="utf-8") as file:
        source = file.read()
    layouts = {}
    for name, macro in PUBLIC_LAYOUT_MACROS.items():
        match = re.search(
            rf"^#define\s+{re.escape(macro)}\s+\"([^\"]+)\"\s*$",
            source,
            re.MULTILINE,
        )
        if match is None:
            raise RuntimeError(f"public debug layout macro is missing: {macro}")
        layout_format = match.group(1)
        layouts[name] = {
            "format": layout_format,
            "size": struct.calcsize(layout_format),
        }
    if layouts["handle"]["size"] != 12 or layouts["actorState"]["size"] != 88:
        raise RuntimeError("public debug layout format sizes differ from actor ABI")
    return layouts


def parse_context_offsets(header):
    with open(header, "r", encoding="utf-8") as file:
        source = file.read()
    match = re.search(r"^#define\s+OVERWORLD_ACTOR_DEBUG_MAP_GENERATION_OFFSET\s+(\d+)\s*$",
                      source, re.MULTILINE)
    if match is None:
        raise RuntimeError("native-checked map-generation debug offset is missing")
    offset = int(match.group(1))
    if offset % 2 or not 0 < offset < 0x990 - 1:
        raise RuntimeError("map-generation debug offset is outside the actor state")
    return {"mapGeneration": offset}


def input_record(path):
    with open(path, "rb") as file:
        data = file.read()
    return {
        "path": os.path.relpath(os.path.abspath(path), os.getcwd()),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def write_descriptor(
    path,
    image,
    symbols,
    debug,
    services,
    row,
    enums,
    public_layouts,
    generator_inputs,
    context_offsets,
):
    descriptor = {
        "formatVersion": 2,
        "overlay": {
            "id": OVERLAY_ID,
            "base": OVERLAY_LOAD_ADDRESS,
            "abiBase": OVERLAY_BASE,
            "end": OVERLAY_END,
            "capacity": OVERLAY_END - OVERLAY_LOAD_ADDRESS,
            "fileSize": len(image),
            "bssSize": row[3],
            "sha256": hashlib.sha256(image).hexdigest(),
        },
        "facade": {
            "address": ENTRY_ADDRESS,
            "version": 2,
            "size": 24,
            "callbacks": {
                name: symbols[symbol]["address"] | 1
                for name, symbol in zip(
                    ("validate", "apply", "tick", "inspect"), MAIN_CALLBACKS)
            },
        },
        "compatibility": {
            "address": COMPAT_ADDRESS,
            "version": 3,
            "size": 32,
            "callbacks": {
                name: 0 if symbol is None else symbols[symbol]["address"] | 1
                for name, symbol in zip(
                    ("bind", "update", "unbind", "transition",
                     "recordTrace", "getContext"), COMPAT_CALLBACKS)
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
            "actorStride": debug[27],
            "actorPolicyOffset": debug[27] - 32,
            "offsets": {
                **context_offsets,
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
            "actorPolicyState": 32,
        },
        "publicLayouts": public_layouts,
        "generatorInputs": generator_inputs,
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
    public_layouts = parse_public_layouts(args.header)
    generator_inputs = {
        "generator": input_record(os.path.abspath(__file__)),
        "linked": input_record(args.linked),
        "header": input_record(args.header),
        "internalHeader": input_record(args.internal_header),
        "resolverHeader": input_record(args.resolver_header),
        "motionHeader": input_record(args.motion_header),
    }
    write_descriptor(
        args.output,
        image,
        symbols,
        debug,
        services,
        row,
        enums,
        public_layouts,
        generator_inputs,
        parse_context_offsets(args.internal_header),
    )
    print(
        "overlay 158 actor ABI gate: "
        f"entry=0x{ENTRY_ADDRESS:08X} state=0x{STATE_ADDRESS:08X} "
        f"sha256={hashlib.sha256(image).hexdigest()}"
    )


if __name__ == "__main__":
    main()
