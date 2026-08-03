#!/usr/bin/env python3
"""Identity and fixed-window gate for overworld-wild resident overlays."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

CONFIG = {
    149: (0x023CD000, 0xB000, "gOverworldWildSpawnsOverlayEntry", 0x80),
    # The shared physical window is 0x1E00; 0xA0 is reserved for selector-152,
    # and the validator keeps another 0x60 of post-link growth margin.
    156: (0x023C0400, 0x1D60, "gOverworldWildBehaviorValidatorOverlayEntry", 0x60),
    # Frozen Task-8 validated-catalog owner and loader.
    157: (0x023BB400, 0x2000, "OverworldWildBehavior_LoadValidatedBundle", 0x80),
    # Task-9 mutation/composition/cache/provenance service.
    158: (0x023B8400, 0x3000, "OverworldWildRuntime_ApplyStackDelta", 0x80),
}

TASK5_SCALAR_SYMBOLS = {
    "sOwbdStateValueMax": (0x023BDEB0, "OBJECT"),
    "sOwbdNumericFieldMasks": (0x023BDECC, "OBJECT"),
    "OwbdStaticValueValid": (0x023BDF91, "FUNC"),
    "OwbdModifierPayloadValid": (0x023BE035, "FUNC"),
}

RETAINED_STATIC_RESOLVER = (
    "OverworldWildRuntime_ResolveRetainedStaticCache"
)
DESTRUCTIVE_WRAPPER = "OverworldWildRuntime_DestructivelyInvalidateSlot"
DESTRUCTIVE_HELPER = "OverworldWildRuntime_HandleSlotGenerationWrap"


def read_symbol_rows(path: Path) -> dict[str, tuple[int, int, str, str, str]]:
    rows = {}
    output = subprocess.check_output(
        ["arm-none-eabi-readelf", "-sW", path], text=True
    )
    for line in output.splitlines():
        parts = line.split()
        if (len(parts) >= 8 and parts[0].endswith(":")
                and parts[0][:-1].isdigit()):
            rows[parts[7]] = (
                int(parts[1], 16), int(parts[2]), parts[3], parts[4], parts[6]
            )
    return rows


def scalar_identity_error(owner, shard, consumer) -> str | None:
    for name, (address, kind) in TASK5_SCALAR_SYMBOLS.items():
        owner_row = owner.get(name)
        shard_row = shard.get(name)
        consumer_row = consumer.get(name)
        if (owner_row is None or owner_row[0] != address
                or owner_row[1] == 0 or owner_row[2] != kind
                or owner_row[3] != "GLOBAL" or owner_row[4] == "ABS"):
            return f"overlay 155 owns stale/mistyped Task-5 scalar symbol: {name}"
        for label, row in (("shard", shard_row), ("overlay 158", consumer_row)):
            if (row is None or row[0] != owner_row[0] or row[1] != 0
                    or row[2] != owner_row[2] or row[3] != "GLOBAL"
                    or row[4] != "ABS"):
                return f"{label} Task-5 scalar import differs from overlay 155: {name}"
    return None


def verify_scalar_identity(owner_path: Path, shard_path: Path, consumer_path: Path) -> None:
    owner = read_symbol_rows(owner_path)
    shard = read_symbol_rows(shard_path)
    consumer = read_symbol_rows(consumer_path)
    error = scalar_identity_error(owner, shard, consumer)
    if error is not None:
        raise SystemExit(error)

    # Keep the rejection path live: an address move and an ELF type change in
    # the real owner records must each fail the same comparison.
    moved = dict(owner)
    row = moved["sOwbdStateValueMax"]
    moved["sOwbdStateValueMax"] = (row[0] + 2, *row[1:])
    mistyped = dict(owner)
    row = mistyped["OwbdStaticValueValid"]
    mistyped["OwbdStaticValueValid"] = (row[0], row[1], "NOTYPE", *row[3:])
    if (scalar_identity_error(moved, shard, consumer) is None
            or scalar_identity_error(mistyped, shard, consumer) is None):
        raise SystemExit("Task-5 scalar owner negative identity fixture was accepted")


def resolver_owner_error(owner) -> str | None:
    resolver = owner.get(RETAINED_STATIC_RESOLVER)
    text_start = owner.get("__text_start")
    text_end = owner.get("__text_end")
    if text_start is None or text_end is None or text_end[0] <= text_start[0]:
        return "overlay 157 resolver owner has a malformed text span"
    if (resolver is None or resolver[1] == 0 or resolver[2] != "FUNC"
            or resolver[3] != "GLOBAL" or resolver[4] == "ABS"
            or resolver[0] & 1 == 0):
        return "overlay 157 retained-static API lacks owned Thumb FUNC typing"
    address = resolver[0] & ~1
    if address < text_start[0] or address + resolver[1] > text_end[0]:
        return "overlay 157 retained-static API escaped its complete owner text span"
    return None


def resolver_identity_error(owner, consumer) -> str | None:
    owner_error = resolver_owner_error(owner)
    if owner_error is not None:
        return owner_error
    owner_row = owner[RETAINED_STATIC_RESOLVER]
    consumer_row = consumer.get(RETAINED_STATIC_RESOLVER)
    if consumer_row is None:
        return "overlay 158 retained-static API import is missing"
    if consumer_row[0] != owner_row[0]:
        return "overlay 158 retained-static API value differs from overlay 157"
    if consumer_row[1] != owner_row[1]:
        return "overlay 158 retained-static API size differs from overlay 157"
    if consumer_row[2] != owner_row[2] or consumer_row[2] != "FUNC":
        return "overlay 158 retained-static API type differs from overlay 157"
    if consumer_row[3] != owner_row[3] or consumer_row[3] != "GLOBAL":
        return "overlay 158 retained-static API binding differs from overlay 157"
    if consumer_row[4] != "ABS":
        return "overlay 158 retained-static API import is not absolute"
    return None


def verify_catalog_identity(owner_path: Path, consumer_path: Path) -> None:
    owner = read_symbol_rows(owner_path)
    consumer = read_symbol_rows(consumer_path)
    error = resolver_identity_error(owner, consumer)
    if error is not None:
        raise SystemExit(error)

    owner_row = owner[RETAINED_STATIC_RESOLVER]
    consumer_row = consumer[RETAINED_STATIC_RESOLVER]
    negative_fixtures = []

    moved_consumer = dict(consumer)
    moved_consumer[RETAINED_STATIC_RESOLVER] = (
        consumer_row[0] + 2, *consumer_row[1:]
    )
    negative_fixtures.append((owner, moved_consumer))

    resized_consumer = dict(consumer)
    resized_consumer[RETAINED_STATIC_RESOLVER] = (
        consumer_row[0], consumer_row[1] + 2, *consumer_row[2:]
    )
    negative_fixtures.append((owner, resized_consumer))

    mistyped_consumer = dict(consumer)
    mistyped_consumer[RETAINED_STATIC_RESOLVER] = (
        consumer_row[0], consumer_row[1], "NOTYPE", *consumer_row[3:]
    )
    negative_fixtures.append((owner, mistyped_consumer))

    rebound_consumer = dict(consumer)
    rebound_consumer[RETAINED_STATIC_RESOLVER] = (
        *consumer_row[:3], "WEAK", consumer_row[4]
    )
    negative_fixtures.append((owner, rebound_consumer))

    sectioned_consumer = dict(consumer)
    sectioned_consumer[RETAINED_STATIC_RESOLVER] = (
        *consumer_row[:4], "1"
    )
    negative_fixtures.append((owner, sectioned_consumer))

    absolute_owner = dict(owner)
    absolute_owner[RETAINED_STATIC_RESOLVER] = (*owner_row[:4], "ABS")
    negative_fixtures.append((absolute_owner, consumer))

    truncated_owner = dict(owner)
    text_end = owner["__text_end"]
    truncated_owner["__text_end"] = (
        (owner_row[0] & ~1) + owner_row[1] - 2, *text_end[1:]
    )
    negative_fixtures.append((truncated_owner, consumer))

    if any(resolver_identity_error(candidate_owner, candidate_consumer) is None
           for candidate_owner, candidate_consumer in negative_fixtures):
        raise SystemExit(
            "retained-static catalog owner negative identity fixture was accepted"
        )


def imported_function_identity_error(
        owner,
        carrier,
        consumer,
        name: str,
        owner_label: str,
        start_name: str,
        end_name: str,
        expected_value: int | None = None,
        expected_size: int | None = None) -> str | None:
    owner_row = owner.get(name)
    carrier_row = carrier.get(name)
    consumer_row = consumer.get(name)
    span_start = owner.get(start_name)
    span_end = owner.get(end_name)
    if (span_start is None or span_end is None
            or span_end[0] <= span_start[0]):
        return f"{owner_label} has a malformed owner span for {name}"
    if (owner_row is None or owner_row[1] == 0 or owner_row[2] != "FUNC"
            or owner_row[3] != "GLOBAL" or owner_row[4] == "ABS"
            or owner_row[0] & 1 == 0):
        return f"{owner_label} lacks owned Thumb FUNC typing for {name}"
    address = owner_row[0] & ~1
    if address < span_start[0] or address + owner_row[1] > span_end[0]:
        return f"{owner_label} function escaped its complete owner span: {name}"
    if ((expected_value is not None and owner_row[0] != expected_value)
            or (expected_size is not None and owner_row[1] != expected_size)):
        return f"{owner_label} frozen value/size differs for {name}"
    if (carrier_row is None or carrier_row[:4] != owner_row[:4]
            or carrier_row[4] == "ABS"):
        return f"typed carrier differs from {owner_label}: {name}"
    if (consumer_row is None or consumer_row[:4] != owner_row[:4]
            or consumer_row[4] != "ABS"):
        return f"typed consumer differs from {owner_label}: {name}"
    return None


def symbol_disassembly(
        path: Path, name: str, include_relocations: bool = False) -> str:
    output = subprocess.check_output(
        ["arm-none-eabi-objdump", "-dr" if include_relocations else "-d", path],
        text=True,
    )
    lines = []
    found = False
    header = re.compile(r"^[0-9A-Fa-f]+ <([^>]+)>:$")
    for line in output.splitlines():
        match = header.match(line)
        if match is not None:
            if found:
                break
            found = match.group(1) == name
            continue
        if found:
            lines.append(line)
    if not found:
        raise SystemExit(f"missing disassembly for {name}")
    return "\n".join(lines)


def destructive_wrapper_disassembly_error(
        disassembly: str, require_object_relocation: bool = False) -> str | None:
    calls = re.findall(r"\bblx?\b[^\n]*<([^>]+)>", disassembly)
    if calls != [DESTRUCTIVE_HELPER]:
        return "overlay 155 destructive wrapper call inventory differs"
    if re.search(r"\b(?:str|strb|strh|stmia|stmdb)\b", disassembly):
        return "overlay 155 destructive wrapper retained inline writes"
    if len(re.findall(r"\bnop\b", disassembly)) != 18:
        return "overlay 155 destructive wrapper padding differs"
    branch = re.search(
        r"(?m)^\s*[0-9A-Fa-f]+:.*\bbeq(?:\.n)?\s+([0-9A-Fa-f]+)",
        disassembly,
    )
    if branch is None or re.search(
            rf"(?m)^\s*{re.escape(branch.group(1))}:.*\bpop\b.*\bpc\b",
            disassembly) is None:
        return "overlay 155 false branch does not return through its epilogue"
    relocations = re.findall(r"\b(R_ARM_\S+)\s+(\S+)", disassembly)
    if (require_object_relocation
            and relocations != [("R_ARM_THM_CALL", DESTRUCTIVE_HELPER)]):
        return "overlay 155 destructive wrapper relocation inventory differs"
    if require_object_relocation:
        mnemonics = re.findall(
            r"(?m)^\s*[0-9A-Fa-f]+:\s+(?:[0-9A-Fa-f]{4}\s+)+"
            r"([a-z][a-z0-9.]*)\b",
            disassembly,
        )
        if mnemonics != ["push", "cmp", "beq.n", "bl"] \
                + ["nop"] * 18 + ["pop"]:
            return "overlay 155 destructive wrapper instruction bytes differ"
    if not require_object_relocation and relocations:
        return "linked overlay 155 destructive wrapper retained relocations"
    return None


def verify_destructive_lifecycle_identity(
        owner_path: Path,
        carrier_path: Path,
        consumer_path: Path,
        lifecycle_object_path: Path,
        runtime_carrier_path: Path,
        spawns_consumer_path: Path) -> None:
    owner158 = read_symbol_rows(owner_path)
    carrier158 = read_symbol_rows(carrier_path)
    consumer155 = read_symbol_rows(consumer_path)
    error = imported_function_identity_error(
        owner158, carrier158, consumer155, DESTRUCTIVE_HELPER,
        "overlay 158", "__text_start", "__text_end")
    if error is not None:
        raise SystemExit(error)

    lifecycle_object = read_symbol_rows(lifecycle_object_path)
    object_row = lifecycle_object.get(DESTRUCTIVE_WRAPPER)
    if (object_row is None or object_row[1:4] != (0x30, "FUNC", "GLOBAL")
            or object_row[4] == "ABS" or object_row[0] & 1 == 0):
        raise SystemExit(
            "overlay 155 destructive wrapper source object row differs"
        )

    runtime_carrier = read_symbol_rows(runtime_carrier_path)
    spawns_consumer = read_symbol_rows(spawns_consumer_path)
    error = imported_function_identity_error(
        consumer155, runtime_carrier, spawns_consumer, DESTRUCTIVE_WRAPPER,
        "overlay 155", "__ow_wild_runtime_sidecars_start",
        "__ow_wild_runtime_sidecars_end", 0x023BDDD5, 0x30)
    if error is not None:
        raise SystemExit(error)

    disassembly = symbol_disassembly(consumer_path, DESTRUCTIVE_WRAPPER)
    disassembly_error = destructive_wrapper_disassembly_error(disassembly)
    if disassembly_error is not None:
        raise SystemExit(disassembly_error)
    object_disassembly = symbol_disassembly(
        lifecycle_object_path, DESTRUCTIVE_WRAPPER, True)
    object_disassembly_error = destructive_wrapper_disassembly_error(
        object_disassembly, True)
    if object_disassembly_error is not None:
        raise SystemExit(object_disassembly_error)

    helper_row = owner158[DESTRUCTIVE_HELPER]
    moved_consumer = dict(consumer155)
    moved_consumer[DESTRUCTIVE_HELPER] = (
        helper_row[0] + 2, *consumer155[DESTRUCTIVE_HELPER][1:]
    )
    resized_carrier = dict(carrier158)
    resized_carrier[DESTRUCTIVE_HELPER] = (
        helper_row[0], helper_row[1] + 2, *carrier158[DESTRUCTIVE_HELPER][2:]
    )
    mistyped_consumer = dict(consumer155)
    mistyped_consumer[DESTRUCTIVE_HELPER] = (
        helper_row[0], helper_row[1], "NOTYPE",
        *consumer155[DESTRUCTIVE_HELPER][3:]
    )
    rebound_carrier = dict(carrier158)
    rebound_carrier[DESTRUCTIVE_HELPER] = (
        *carrier158[DESTRUCTIVE_HELPER][:3], "WEAK",
        carrier158[DESTRUCTIVE_HELPER][4]
    )
    absolute_carrier = dict(carrier158)
    absolute_carrier[DESTRUCTIVE_HELPER] = (
        *carrier158[DESTRUCTIVE_HELPER][:4], "ABS"
    )
    sectioned_consumer = dict(consumer155)
    sectioned_consumer[DESTRUCTIVE_HELPER] = (
        *consumer155[DESTRUCTIVE_HELPER][:4], "1"
    )
    truncated_owner = dict(owner158)
    text_end = owner158["__text_end"]
    truncated_owner["__text_end"] = (
        (helper_row[0] & ~1) + helper_row[1] - 2, *text_end[1:]
    )
    negative_fixtures = (
        (owner158, carrier158, moved_consumer),
        (owner158, resized_carrier, consumer155),
        (owner158, carrier158, mistyped_consumer),
        (owner158, rebound_carrier, consumer155),
        (owner158, absolute_carrier, consumer155),
        (owner158, carrier158, sectioned_consumer),
        (truncated_owner, carrier158, consumer155),
    )
    if any(imported_function_identity_error(
            candidate_owner, candidate_carrier, candidate_consumer,
            DESTRUCTIVE_HELPER, "overlay 158", "__text_start", "__text_end")
            is None for candidate_owner, candidate_carrier, candidate_consumer
            in negative_fixtures):
        raise SystemExit(
            "destructive-helper negative identity fixture was accepted"
        )
    for mutation in (
        disassembly + "\n  0: f000 f800 bl 0 <" + DESTRUCTIVE_HELPER + ">",
        disassembly.replace(DESTRUCTIVE_HELPER, DESTRUCTIVE_WRAPPER),
        disassembly + "\n  0: 6001 str r1, [r0, #0]",
    ):
        if destructive_wrapper_disassembly_error(mutation) is None:
            raise SystemExit(
                "destructive-wrapper negative call/write fixture was accepted"
            )
    for mutation in (
        object_disassembly.replace("nop", "mov", 1),
        re.sub(r"(\bbeq(?:\.n)?\s+)[0-9A-Fa-f]+", r"\g<1>0",
            object_disassembly, count=1),
        re.sub(r"^.*R_ARM_THM_CALL.*$", "", object_disassembly,
            count=1, flags=re.MULTILINE),
    ):
        if destructive_wrapper_disassembly_error(mutation, True) is None:
            raise SystemExit(
                "destructive-wrapper negative object fixture was accepted"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("elf", type=Path)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--overlay", type=int, choices=CONFIG, required=True)
    parser.add_argument("--minimum-headroom", type=lambda value: int(value, 0))
    parser.add_argument("--task5-owner", type=Path)
    parser.add_argument("--lifecycle-consumer", type=Path)
    parser.add_argument("--lifecycle-object", type=Path)
    parser.add_argument("--scalar-shard", type=Path)
    parser.add_argument("--catalog-owner", type=Path)
    parser.add_argument("--task8-carrier", type=Path)
    parser.add_argument("--runtime-carrier", type=Path)
    parser.add_argument("--spawns-consumer", type=Path)
    args = parser.parse_args()
    origin, length, entry_name, default_headroom = CONFIG[args.overlay]
    minimum = default_headroom if args.minimum_headroom is None else args.minimum_headroom

    file_output = subprocess.check_output(["arm-none-eabi-objdump", "-f", args.elf], text=True)
    if "file format elf32-littlearm" not in file_output or "architecture: arm" not in file_output:
        raise SystemExit(f"overlay {args.overlay}: unrelated/non-ARM ELF")
    symbols = {}
    for line in subprocess.check_output(["arm-none-eabi-nm", "-n", args.elf], text=True).splitlines():
        parts = line.split()
        if len(parts) >= 3: symbols[parts[-1]] = int(parts[0], 16)
    required = {"__text_start", "__text_end", "_end", "__end__", entry_name}
    if args.overlay == 156:
        required.add("OverworldWildBehaviorValidator_LoadProjection")
    if args.overlay == 157:
        required.update((
            "__bss_start__",
            "__bss_end__",
            "OverworldWildBehavior_ReleaseValidatedBundle",
            "OverworldWildBehavior_FreeValidatedBundle",
            "OverworldWildRuntime_CopyInstalledDefinition",
            "OverworldWildRuntime_CopyInstalledCatalogIdentity",
            "OverworldWildRuntime_MarkResidentCold",
            "OverworldWildRuntime_CopyInstalledStaticComposition",
            "OverworldWildRuntime_ResolveRetainedStaticCache",
            "OverworldWildRuntime_CopyInstalledResolvedNode",
            "OverworldWildRuntime_CopyInstalledModifierOperations",
            "OverworldWildRuntime_CountInstalledTiredTranslations",
        ))
    if args.overlay == 158:
        required.update((
            "__bss_start__",
            "__bss_end__",
            "OverworldWildRuntime_HandleSlotGenerationWrap",
            "OverworldWildRuntime_ClearSlotStorage",
            "OverworldWildRuntime_InitializeStorage",
            "OverworldWildRuntime_BindPrivateIdentity",
            "OverworldWildRuntime_ApplyStackDelta",
            "OverworldWildRuntime_Apply",
            "OverworldWildRuntime_Replace",
            "OverworldWildRuntime_Remove",
            "OverworldWildRuntime_RemoveOwner",
            "OverworldWildRuntime_ClearAllForSlot",
            "OverworldWildRuntime_PrimeEffectiveCache",
            "OverworldWildRuntime_GetEffectiveCache",
            "OverworldWildRuntime_GetCapabilityMask",
            "OverworldWildRuntime_GetProvenance",
            "OverworldWildRuntime_GetLayerCount",
            "OverworldWildRuntime_GetLayerByIndex",
            "OverworldWildRuntime_FindLayer",
        ))
    missing = sorted(required - symbols.keys())
    if missing: raise SystemExit(f"overlay {args.overlay}: missing identity symbols: {', '.join(missing)}")
    if symbols["__text_start"] != origin:
        raise SystemExit(f"overlay {args.overlay}: entry/text origin identity mismatch")
    if args.overlay != 158 and symbols[entry_name] != origin:
        raise SystemExit(f"overlay {args.overlay}: entry origin identity mismatch")
    if args.overlay == 158 and not origin <= symbols[entry_name] < symbols["__text_end"]:
        raise SystemExit("overlay 158: mutation entry escaped its fixed image")
    if (args.overlay == 158
            and origin <= symbols.get("OverworldWildRuntime_MarkResidentCold", 0)
                < symbols["__text_end"]):
        raise SystemExit("overlay 158: resident cold helper has wrong owner")
    resolver_rows = read_symbol_rows(args.elf)
    if args.overlay == 157:
        owner_error = resolver_owner_error(resolver_rows)
        if owner_error is not None:
            raise SystemExit(owner_error)
    if symbols["__text_end"] < origin or symbols["_end"] < symbols["__text_end"] \
            or symbols["__end__"] != symbols["_end"]:
        raise SystemExit(f"overlay {args.overlay}: malformed end symbols")

    section_output = subprocess.check_output(["arm-none-eabi-objdump", "-h", args.elf], text=True)
    end = origin
    saw_text = False
    for line in section_output.splitlines():
        match = re.match(r"\s*\d+\s+(\S+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+", line)
        if match is None: continue
        name, size_hex, address_hex = match.groups()
        size, address = int(size_hex, 16), int(address_hex, 16)
        if name == ".text": saw_text = address == origin and size > 0
        if origin <= address < origin + length: end = max(end, address + size)
    end = max(end, symbols["_end"])
    if not saw_text or end > origin + length:
        raise SystemExit(f"overlay {args.overlay}: linked sections exceed or do not identify fixed window")
    raw_size = args.binary.stat().st_size
    if raw_size != max(0, end - origin):
        raise SystemExit(f"overlay {args.overlay}: raw size {raw_size} != linked span {end - origin}")
    if args.overlay == 149 and (end != 0x023D7F3C or raw_size != 0xAF3C):
        raise SystemExit(
            f"overlay 149: sealed boundary changed: end=0x{end:08X} raw=0x{raw_size:X}"
        )
    if args.overlay == 156:
        raw = args.binary.read_bytes()
        callback = int.from_bytes(raw[8:12], "little")
        expected_callback = symbols["OverworldWildBehaviorValidator_LoadProjection"] | 1
        if callback != expected_callback:
            raise SystemExit(f"overlay 156: callback 0x{callback:08X} != linked Thumb symbol 0x{expected_callback:08X}")
        readelf = subprocess.check_output(
            ["arm-none-eabi-readelf", "-sW", args.elf], text=True
        )
        linked_symbol_rows = {}
        for line in readelf.splitlines():
            parts = line.split()
            if len(parts) >= 8 and parts[0].endswith(":"):
                linked_symbol_rows[parts[7]] = parts[1:7]
        for name in (
            "OwbdCrcByte",
            "OwbdBoundedRead",
            "OwbdHasId",
            "OwbdStaticValueValid",
            "OwbdModifierPayloadValid",
        ):
            row = linked_symbol_rows.get(name)
            if row is None or row[2] != "FUNC" or row[5] != "ABS" \
                    or int(row[0], 16) & 1 == 0:
                raise SystemExit(
                    f"overlay 156: resident helper lacks imported Thumb FUNC typing: {name}"
                )
        for name in (
            "sOwbdSpecs",
            "sOwbdStateValueMax",
            "sOwbdNumericFieldMasks",
            "sOwbdGroupOrdinals",
            "sOwbdImportExpectedOwner",
            "sOwbdImportExpectedRecovery",
            "sOwbdImportExpectedSource",
            "sOwbdImportExpectedRole",
            "sOwbdImportExpectedLifetime",
            "sOwbdOverrideProvenance",
        ):
            row = linked_symbol_rows.get(name)
            if row is None or row[2] != "OBJECT" or row[5] != "ABS":
                raise SystemExit(
                    f"overlay 156: resident validation table lacks imported OBJECT typing: {name}"
                )
        if any("_from_thumb" in name or "veneer" in name.lower() for name in symbols):
            raise SystemExit("overlay 156: unexpected interworking veneer")
        relocations = subprocess.check_output(
            ["arm-none-eabi-objdump", "-r", args.elf], text=True
        )
        if "R_ARM_" in relocations:
            raise SystemExit("overlay 156: unresolved relocation remains after resident link")
    if args.overlay in (157, 158):
        bss_size = symbols["__bss_end__"] - symbols["__bss_start__"]
        if bss_size < 0 or bss_size > 0x140:
            raise SystemExit(
                f"overlay {args.overlay}: BSS 0x{bss_size:X} exceeds fixed 0x140 budget"
            )
        usable_end = 0x023BD380 if args.overlay == 157 else 0x023BB380
        if symbols["__bss_end__"] > usable_end:
            raise SystemExit(
                f"overlay {args.overlay}: complete image exceeds 0x{usable_end:08X}"
            )
        veneers = {
            name for name in symbols
            if "_from_thumb" in name or "veneer" in name.lower()
        }
        expected_veneers = {"__memcpy_from_thumb", "__memset_from_thumb"}
        if args.overlay == 157:
            expected_veneers.add("____gnu_thumb1_case_uqi_from_thumb")
        if args.overlay == 158:
            expected_veneers.add("____gnu_thumb1_case_uqi_from_thumb")
        if veneers != expected_veneers:
            raise SystemExit(
                f"overlay {args.overlay}: interworking veneer inventory changed: "
                + ", ".join(sorted(veneers))
            )
        for name in veneers:
            if not origin <= symbols[name] < symbols["__text_end"]:
                raise SystemExit(f"overlay {args.overlay}: {name} escaped the fixed image")
        relocations = subprocess.check_output(
            ["arm-none-eabi-objdump", "-r", args.elf], text=True
        )
        if "R_ARM_" in relocations:
            raise SystemExit(f"overlay {args.overlay}: unresolved relocation remains after resident link")
        if args.overlay == 158:
            if (args.task5_owner is None or args.scalar_shard is None
                    or args.lifecycle_consumer is None
                    or args.lifecycle_object is None
                    or args.catalog_owner is None
                    or args.task8_carrier is None
                    or args.runtime_carrier is None
                    or args.spawns_consumer is None):
                raise SystemExit(
                    "overlay 158: complete same-build typed owners are required"
                )
            verify_scalar_identity(args.task5_owner, args.scalar_shard, args.elf)
            verify_catalog_identity(args.catalog_owner, args.elf)
            verify_destructive_lifecycle_identity(
                args.elf, args.task8_carrier, args.lifecycle_consumer,
                args.lifecycle_object, args.runtime_carrier,
                args.spawns_consumer)
    headroom = origin + length - end
    if headroom < minimum:
        raise SystemExit(f"overlay {args.overlay}: headroom {headroom} below required {minimum}")
    extra = ""
    if args.overlay in (157, 158):
        extra = f" bss={symbols['__bss_end__'] - symbols['__bss_start__']}"
    print(f"overlay {args.overlay}: origin=0x{origin:08X} end=0x{end:08X} raw={raw_size} headroom={headroom}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
