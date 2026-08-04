#!/usr/bin/env python3
"""Identity and fixed-window gate for overworld-wild resident overlays."""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

CONFIG = {
    149: (0x023CD000, 0xB000, "gOverworldWildSpawnsOverlayEntry", 0x80),
    # The shared physical window is 0x1E00; 0xA0 is reserved for selector-152,
    # and the validator keeps another 0x60 of post-link growth margin.
    156: (0x023C0400, 0x1D60, "gOverworldWildBehaviorValidatorOverlayEntry", 0x60),
    # Frozen Task-8 validated-catalog owner and loader.
    157: (0x023BB980, 0x1A80, "OverworldWildBehavior_LoadValidatedBundle", 0x80),
    # Task-9 mutation/composition/cache/provenance service.
    158: (0x023B8400, 0x3580, "OverworldWildRuntime_ApplyStackDelta", 0x80),
    # Task-10 timer scheduler shard, followed by the retained 0x80 arena guard.
    159: (0x023BF480, 0xF80, "OverworldWildRuntime_GetTimerCount", 0x80),
}

TASK5_SCALAR_SYMBOLS = {
    "sOwbdStateValueMax": (0x023BDEAE, "OBJECT"),
    "sOwbdNumericFieldMasks": (0x023BDECC, "OBJECT"),
    "OwbdStaticValueValid": (0x023BDF8D, "FUNC"),
    "OwbdModifierPayloadValid": (0x023BE031, "FUNC"),
}

CORE_THUMB_HELPERS = (
    "memset",
    "memcpy",
    "__gnu_thumb1_case_uqi",
)

RETAINED_STATIC_RESOLVER = (
    "OverworldWildRuntime_ResolveRetainedStaticCache"
)
DESTRUCTIVE_WRAPPER = "OverworldWildRuntime_DestructivelyInvalidateSlot"
DESTRUCTIVE_HELPER = "OverworldWildRuntime_HandleSlotGenerationWrap"
TIMER_LAYER_IMPORT_APIS = (
    "OverworldWildRuntime_ApplyStackDeltaCompact",
    "OverworldWildRuntime_GetEffectiveCache",
    "OverworldWildRuntime_ValidateTimerQueryInternal",
    "OverworldWildRuntime_TimerExpiryTagInternal",
    "OverworldWildRuntime_PreflightTimerExpiryInternal",
    "OverworldWildRuntime_MakeTimerRemovalHandleInternal",
)
TIMER_CATALOG_IMPORT_APIS = (
    "OverworldWildRuntime_AcquireInstalledTransitionCatalog",
    "OverworldWildRuntime_MatchesPendingTimerExpiry",
)
TIMER_PUBLIC_APIS = (
    "OverworldWildRuntime_GetTimerCount",
    "OverworldWildRuntime_GetTimerByIndex",
    "OverworldWildRuntime_SetTimerPresentationGate",
    "OverworldWildRuntime_TickCandidateTimers",
    "OverworldWildRuntime_TickFrameTimers",
    "OverworldWildRuntime_TickCompletedMovementTimers",
    "OverworldWildRuntime_GetPendingTimerExpiryCount",
    "OverworldWildRuntime_GetPendingTimerExpiryByIndex",
    "OverworldWildRuntime_DispatchTransition",
    "OverworldWildRuntime_CaptureCommandOrigin",
    "OverworldWildRuntime_ConsumeCommandOrigin",
    "OverworldWildRuntime_InvalidateCommandOrigin",
    "OverworldWildRuntime_InvalidateAllCommandOrigins",
)

OVERLAY_149_PRELINK_TEXT_LIMIT = 0xAEC4
OVERLAY_149_PRELINK_RESIDENT_LIMIT = 0xAF80
OVERLAY_149_LINK_ORDER = (
    ".overworld_wild_spawns_entry", ".init", ".text", ".ctors", ".dtors",
    ".rodata", ".data", ".fini",
)


def read_allocated_input_sections(
        path: Path) -> list[tuple[str, int, int, bool]]:
    lines = subprocess.check_output(
        ["arm-none-eabi-objdump", "-h", path], text=True
    ).splitlines()
    rows = []
    for line_index, line in enumerate(lines):
        match = re.match(
            r"\s*\d+\s+(\S+)\s+([0-9A-Fa-f]+)\s+"
            r"[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+2\*\*(\d+)",
            line,
        )
        if match is not None:
            name, size_hex, alignment_power = match.groups()
            flags = lines[line_index + 1] if line_index + 1 < len(lines) else ""
            if "ALLOC" in flags:
                rows.append((
                    name,
                    int(size_hex, 16),
                    1 << int(alignment_power),
                    "CONTENTS" in flags,
                ))
    return rows


def read_linked_allocated_sections(
        path: Path) -> list[tuple[str, int, int, int, bool]]:
    """Return every SHF_ALLOC section with its exact linked alignment.

    objcopy's binary excludes NOBITS sections, while the resident arena must
    reserve both initialized bytes and BSS.  Keep those spans separate so the
    size gate cannot silently omit an aligned entry section or trailing BSS.
    """
    lines = subprocess.check_output(
        ["arm-none-eabi-objdump", "-h", path], text=True
    ).splitlines()
    rows = []
    for line_index, line in enumerate(lines):
        match = re.match(
            r"\s*\d+\s+(\S+)\s+([0-9A-Fa-f]+)\s+"
            r"([0-9A-Fa-f]+)\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+"
            r"2\*\*(\d+)",
            line,
        )
        if match is None:
            continue
        name, size_hex, address_hex, alignment_power = match.groups()
        flags = lines[line_index + 1] if line_index + 1 < len(lines) else ""
        if "ALLOC" not in flags:
            continue
        rows.append((
            name,
            int(size_hex, 16),
            int(address_hex, 16),
            1 << int(alignment_power),
            "CONTENTS" in flags,
        ))
    return rows


def verify_exact_production_link(args: argparse.Namespace) -> None:
    if args.production_object is None:
        raise SystemExit(
            f"overlay {args.overlay}: exact production object is required"
        )
    root = Path(__file__).resolve().parents[1]
    linker = {
        157: root / "src/overworld_wild_runtime_overlay/linker.ld",
        158: root / "src/overworld_wild_runtime_layers_overlay/linker.ld",
        159: root / "src/overworld_wild_runtime_timers_overlay/linker.ld",
    }[args.overlay]
    command = [
        "arm-none-eabi-ld",
        str(root / "rom_gen.ld"),
        "-T",
        str(linker),
    ]
    if args.core_owner is None:
        raise SystemExit(
            f"overlay {args.overlay}: same-build core owner is required"
        )
    if args.overlay == 157:
        if args.scalar_shard is None:
            raise SystemExit("overlay 157: scalar shard is required for exact link")
        command.append(f"--just-symbols={args.scalar_shard}")
    elif args.overlay == 158:
        if args.catalog_carrier is None or args.scalar_shard is None:
            raise SystemExit(
                "overlay 158: catalog/scalar carriers are required for exact link"
            )
        command.extend((
            f"--just-symbols={args.catalog_carrier}",
            f"--just-symbols={args.scalar_shard}",
        ))
    else:
        if args.task8_carrier is None or args.catalog_carrier is None:
            raise SystemExit(
                "overlay 159: layer/catalog carriers are required for exact link"
            )
        command.extend((
            f"--just-symbols={args.task8_carrier}",
            f"--just-symbols={args.catalog_carrier}",
        ))
    command.append(f"--just-symbols={args.core_owner}")
    with tempfile.TemporaryDirectory(prefix="ow-exact-overlay-link-") as temp:
        relinked = Path(temp) / "linked.o"
        binary = Path(temp) / "linked.bin"
        subprocess.run(
            [*command, "-o", str(relinked), str(args.production_object)],
            cwd=root,
            check=True,
        )
        subprocess.run([
            "arm-none-eabi-objcopy", "-O", "binary", str(relinked), str(binary)
        ], check=True)
        if (read_linked_allocated_sections(relinked)
                != read_linked_allocated_sections(args.elf)):
            raise SystemExit(
                f"overlay {args.overlay}: supplied ELF differs from exact production link"
            )
        if binary.read_bytes() != args.binary.read_bytes():
            raise SystemExit(
                f"overlay {args.overlay}: supplied binary differs from exact production link"
            )


def overlay_149_prelink_layout(
        rows: list[tuple[str, int, int, bool]]) -> tuple[int, int, int, int, int]:
    unexpected = sorted(
        name for name, _, _, _ in rows
        if name not in OVERLAY_149_LINK_ORDER
        and name != ".bss"
        and not name.startswith(".rodata.")
    )
    if unexpected:
        raise ValueError(
            "unexpected allocated input section(s): " + ", ".join(unexpected)
        )

    initialized_rows = []
    for section_name in OVERLAY_149_LINK_ORDER[:6]:
        initialized_rows.extend(
            row for row in rows if row[0] == section_name
        )
    initialized_rows.extend(
        row for row in rows if row[0].startswith(".rodata.")
    )
    for section_name in OVERLAY_149_LINK_ORDER[6:]:
        initialized_rows.extend(
            row for row in rows if row[0] == section_name
        )
    bss_rows = [row for row in rows if row[0] == ".bss"]

    cursor = 0
    for name, size, alignment, has_contents in initialized_rows:
        if size != 0 and not has_contents:
            raise ValueError(f"initialized section {name} is NOBITS")
        cursor = (cursor + alignment - 1) & ~(alignment - 1)
        cursor += size
    cursor = (cursor + 3) & ~3
    initialized = cursor

    packed_allocated = initialized
    linked_allocated = OVERLAY_149_PRELINK_TEXT_LIMIT
    for name, size, alignment, has_contents in bss_rows:
        if size != 0 and has_contents:
            raise ValueError(f"{name} unexpectedly contains initialized bytes")
        packed_allocated = (
            (packed_allocated + alignment - 1) & ~(alignment - 1)
        ) + size
        linked_allocated = (
            (linked_allocated + alignment - 1) & ~(alignment - 1)
        ) + size
    packed_allocated = (packed_allocated + 3) & ~3
    linked_allocated = (linked_allocated + 3) & ~3
    return (
        initialized,
        packed_allocated,
        linked_allocated,
        OVERLAY_149_PRELINK_TEXT_LIMIT - initialized,
        OVERLAY_149_PRELINK_RESIDENT_LIMIT - linked_allocated,
    )


def verify_overlay_149_prelink_object(path: Path) -> None:
    rows = read_allocated_input_sections(path)
    sections = {name for name, _, _, _ in rows}
    entry_size = sum(
        size for name, size, _, _ in rows
        if name == ".overworld_wild_spawns_entry"
    )
    if entry_size != 28:
        raise SystemExit("overlay 149 pre-link gate: entry section is not 28 bytes")
    common_symbols = [
        line for line in subprocess.check_output(
            ["arm-none-eabi-nm", "-S", path], text=True
        ).splitlines()
        if re.search(r"\s[Cc]\s", line)
    ]
    if common_symbols:
        raise SystemExit(
            "overlay 149 pre-link gate: COMMON input is not allowed"
        )
    try:
        initialized, packed, linked, text_headroom, resident_headroom = (
            overlay_149_prelink_layout(rows)
        )
    except ValueError as error:
        raise SystemExit(f"overlay 149 pre-link gate: {error}") from error
    if text_headroom < 0:
        raise SystemExit(
            f"overlay 149 pre-link gate: initialized span 0x{initialized:X} exceeds "
            f"sealed 0x{OVERLAY_149_PRELINK_TEXT_LIMIT:X} budget by 0x{-text_headroom:X}"
        )
    if resident_headroom < 0:
        raise SystemExit(
            f"overlay 149 pre-link gate: linked allocation 0x{linked:X} exceeds "
            f"resident 0x{OVERLAY_149_PRELINK_RESIDENT_LIMIT:X} budget by "
            f"0x{-resident_headroom:X}"
        )
    text_negative = list(rows)
    text_negative.append((
        ".rodata.prelink_negative", text_headroom + 4, 1, True
    ))
    if overlay_149_prelink_layout(text_negative)[3] >= 0:
        raise SystemExit("overlay 149 pre-link negative budget fixture was accepted")
    bss_negative = [
        (name, size + resident_headroom + 4, alignment, contents)
        if name == ".bss" else (name, size, alignment, contents)
        for name, size, alignment, contents in rows
    ]
    if ".bss" not in sections:
        bss_negative.append((".bss", resident_headroom + 4, 4, False))
    if overlay_149_prelink_layout(bss_negative)[4] >= 0:
        raise SystemExit("overlay 149 pre-link BSS negative fixture was accepted")
    try:
        overlay_149_prelink_layout(
            rows + [(".unexpected_alloc", 4, 4, True)]
        )
    except ValueError:
        pass
    else:
        raise SystemExit(
            "overlay 149 pre-link unknown allocated-section fixture was accepted"
        )

    order_fixture_base = [(".text", 0xAA9C, 4, True)]
    aligned_then_byte = order_fixture_base + [
        (".rodata.z", 4, 1024, True),
        (".rodata.a", 1, 1, True),
    ]
    name_sorted_underestimate = order_fixture_base + [
        (".rodata.a", 1, 1, True),
        (".rodata.z", 4, 1024, True),
    ]
    aligned_first_span = overlay_149_prelink_layout(aligned_then_byte)[0]
    sorted_underestimate_span = overlay_149_prelink_layout(
        name_sorted_underestimate
    )[0]
    if aligned_first_span != 0xAC08 or sorted_underestimate_span != 0xAC04:
        raise SystemExit(
            "overlay 149 pre-link underestimated encounter-order fixture failed"
        )
    byte_then_aligned = order_fixture_base + [
        (".rodata.z", 1, 1, True),
        (".rodata.a", 4, 1024, True),
    ]
    name_sorted_overestimate = order_fixture_base + [
        (".rodata.a", 4, 1024, True),
        (".rodata.z", 1, 1, True),
    ]
    if (
        overlay_149_prelink_layout(byte_then_aligned)[0] != 0xAC04
        or overlay_149_prelink_layout(name_sorted_overestimate)[0] != 0xAC08
    ):
        raise SystemExit(
            "overlay 149 pre-link overestimated encounter-order fixture failed"
        )
    order_overflow_size = (
        OVERLAY_149_PRELINK_TEXT_LIMIT - aligned_first_span + 4
    )
    if order_overflow_size <= 0:
        raise SystemExit(
            "overlay 149 pre-link order fixture has no overflow headroom"
        )
    aligned_overflow = aligned_then_byte + [
        (".rodata.order_overflow", order_overflow_size, 1, True)
    ]
    byte_fits = name_sorted_underestimate + [
        (".rodata.order_overflow", order_overflow_size, 1, True)
    ]
    if (
        overlay_149_prelink_layout(aligned_overflow)[3] >= 0
        or overlay_149_prelink_layout(byte_fits)[3] < 0
    ):
        raise SystemExit(
            "overlay 149 pre-link aligned encounter-order overflow fixture failed"
        )
    print(
        f"overlay 149 pre-link: initialized=0x{initialized:X} "
        f"packed-allocated=0x{packed:X} linked-allocated=0x{linked:X} "
        f"text-headroom=0x{text_headroom:X} "
        f"resident-headroom=0x{resident_headroom:X}"
    )


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


def core_thumb_import_identity_error(owner, consumer) -> str | None:
    text_start = owner.get("__text_start")
    text_end = owner.get("__text_end")
    if (text_start is None or text_end is None
            or text_end[0] <= text_start[0]):
        return "core owner has a malformed text span"
    for name in CORE_THUMB_HELPERS:
        owner_row = owner.get(name)
        consumer_row = consumer.get(name)
        if (owner_row is None or owner_row[1] == 0
                or owner_row[2] != "FUNC" or owner_row[3] != "GLOBAL"
                or owner_row[4] in ("ABS", "UND") or owner_row[0] & 1 == 0):
            return f"core owner lacks a sectioned Thumb FUNC helper: {name}"
        address = owner_row[0] & ~1
        if address < text_start[0] or address + owner_row[1] > text_end[0]:
            return f"core Thumb helper escaped its owner text span: {name}"
        if (consumer_row is None or consumer_row[:4] != owner_row[:4]
                or consumer_row[4] != "ABS"):
            return f"resident core helper import differs from same-build owner: {name}"
    return None


def verify_core_thumb_imports(owner_path: Path, consumer_path: Path,
                              production_object_path: Path) -> None:
    owner = read_symbol_rows(owner_path)
    consumer = read_symbol_rows(consumer_path)
    error = core_thumb_import_identity_error(owner, consumer)
    if error is not None:
        raise SystemExit(error)

    production = read_symbol_rows(production_object_path)
    undefined_helpers = {
        name for name in CORE_THUMB_HELPERS
        if name in production and production[name][4] == "UND"
    }
    relocations = subprocess.check_output(
        ["arm-none-eabi-objdump", "-r", production_object_path], text=True
    )
    helper_relocations: dict[str, set[str]] = {}
    for kind, name in re.findall(
            r"(?m)^\s*[0-9A-Fa-f]+\s+(R_ARM_\S+)\s+(\S+)", relocations):
        name = name.split("+")[0]
        if name in CORE_THUMB_HELPERS:
            helper_relocations.setdefault(name, set()).add(kind)
    if set(helper_relocations) != undefined_helpers:
        raise SystemExit(
            "resident core-helper undefined/relocation inventory differs: "
            f"undefined={sorted(undefined_helpers)}, "
            f"relocated={sorted(helper_relocations)}"
        )
    for name, kinds in helper_relocations.items():
        if kinds != {"R_ARM_THM_CALL"}:
            raise SystemExit(
                f"resident core helper {name} uses non-Thumb-call relocation(s): "
                + ", ".join(sorted(kinds))
            )

    # Keep address, type, binding, section, and size rejection paths live.
    representative = CORE_THUMB_HELPERS[0]
    owner_row = owner[representative]
    moved_consumer = dict(consumer)
    moved_consumer[representative] = (
        owner_row[0] + 2, *consumer[representative][1:]
    )
    mistyped_owner = dict(owner)
    mistyped_owner[representative] = (
        owner_row[0], owner_row[1], "NOTYPE", *owner_row[3:]
    )
    mistyped_consumer = dict(consumer)
    mistyped_consumer[representative] = (
        consumer[representative][0], consumer[representative][1], "NOTYPE",
        *consumer[representative][3:]
    )
    resized_consumer = dict(consumer)
    resized_consumer[representative] = (
        consumer[representative][0], consumer[representative][1] + 2,
        *consumer[representative][2:]
    )
    sectioned_consumer = dict(consumer)
    sectioned_consumer[representative] = (
        *consumer[representative][:4], owner_row[4]
    )
    if (core_thumb_import_identity_error(owner, moved_consumer) is None
            or core_thumb_import_identity_error(mistyped_owner, consumer) is None
            or core_thumb_import_identity_error(owner, mistyped_consumer) is None
            or core_thumb_import_identity_error(owner, resized_consumer) is None
            or core_thumb_import_identity_error(owner, sectioned_consumer) is None):
        raise SystemExit("resident core-helper negative identity fixture was accepted")


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


def timer_shard_identity_error(layers_owner, task8_carrier, timer_owner,
                               timer_carrier, catalog_owner,
                               catalog_carrier) -> str | None:
    carrier_exports = {
        name for name, row in timer_carrier.items()
        if row[2] == "FUNC" and row[3] == "GLOBAL"
    }
    if carrier_exports != set(TIMER_PUBLIC_APIS):
        return "overlay 159 timer carrier export inventory differs"
    for name in TIMER_LAYER_IMPORT_APIS:
        error = imported_function_identity_error(
            layers_owner, task8_carrier, timer_owner, name,
            "overlay 158", "__text_start", "__text_end")
        if error is not None:
            return error
    for name in TIMER_CATALOG_IMPORT_APIS:
        error = imported_function_identity_error(
            catalog_owner, catalog_carrier, timer_owner, name,
            "overlay 157", "__text_start", "__text_end")
        if error is not None:
            return error
    for name in TIMER_PUBLIC_APIS:
        owner_row = timer_owner.get(name)
        carrier_row = timer_carrier.get(name)
        text_start = timer_owner.get("__text_start")
        text_end = timer_owner.get("__text_end")
        if (text_start is None or text_end is None
                or text_end[0] <= text_start[0]):
            return "overlay 159 has a malformed timer owner span"
        if (owner_row is None or owner_row[1] == 0
                or owner_row[2] != "FUNC" or owner_row[3] != "GLOBAL"
                or owner_row[4] == "ABS" or owner_row[0] & 1 == 0):
            return f"overlay 159 lacks owned Thumb FUNC typing for {name}"
        address = owner_row[0] & ~1
        if address < text_start[0] or address + owner_row[1] > text_end[0]:
            return f"overlay 159 timer API escaped its owner span: {name}"
        if (carrier_row is None or carrier_row[:4] != owner_row[:4]
                or carrier_row[4] == "ABS"):
            return f"timer carrier differs from overlay 159: {name}"
    return None


def timer_object_import_inventory(timer_object_path: Path) -> set[str]:
    if not timer_object_path.is_file():
        raise SystemExit(
            f"overlay 159 timer source object is absent: {timer_object_path}"
        )
    object_rows = read_symbol_rows(timer_object_path)
    undefined = {
        name for name, row in object_rows.items()
        if row[3] == "GLOBAL" and row[4] == "UND"
    }
    relocations = subprocess.check_output(
        ["arm-none-eabi-objdump", "-r", timer_object_path], text=True
    )
    relocation_types: dict[str, set[str]] = {}
    for kind, name in re.findall(
            r"(?m)^\s*[0-9A-Fa-f]+\s+(R_ARM_\S+)\s+(\S+)", relocations):
        relocation_types.setdefault(name.split("+")[0], set()).add(kind)
    if set(relocation_types) & undefined != undefined:
        raise SystemExit("overlay 159 has an undefined symbol without relocation")
    for name in undefined:
        if relocation_types[name] != {"R_ARM_THM_CALL"}:
            raise SystemExit(
                f"overlay 159 imported {name} through non-call relocation(s): "
                + ", ".join(sorted(relocation_types[name]))
            )
    expected_imports = set(
        TIMER_LAYER_IMPORT_APIS + TIMER_CATALOG_IMPORT_APIS)
    expected_undefined = expected_imports | {
        "memcpy", "memset",
    }
    if undefined != expected_undefined:
        raise SystemExit(
            "overlay 159 source-object import inventory differs: "
            f"missing={sorted(expected_undefined - undefined)}, "
            f"unexpected={sorted(undefined - expected_undefined)}"
        )
    return {name for name in undefined if name.startswith(
        "OverworldWildRuntime_")}


def verify_timer_shard_identity(layers_owner_path: Path,
                                task8_carrier_path: Path,
                                timer_owner_path: Path,
                                timer_carrier_path: Path,
                                catalog_owner_path: Path,
                                catalog_carrier_path: Path,
                                timer_object_path: Path) -> None:
    layers_owner = read_symbol_rows(layers_owner_path)
    task8_carrier = read_symbol_rows(task8_carrier_path)
    timer_owner = read_symbol_rows(timer_owner_path)
    timer_carrier = read_symbol_rows(timer_carrier_path)
    catalog_owner = read_symbol_rows(catalog_owner_path)
    catalog_carrier = read_symbol_rows(catalog_carrier_path)
    expected_imports = set(
        TIMER_LAYER_IMPORT_APIS + TIMER_CATALOG_IMPORT_APIS)
    actual_imports = timer_object_import_inventory(timer_object_path)
    if actual_imports != expected_imports:
        missing = sorted(expected_imports - actual_imports)
        unexpected = sorted(actual_imports - expected_imports)
        raise SystemExit(
            "overlay 159 cross-overlay call inventory differs: "
            f"missing={missing}, unexpected={unexpected}"
        )
    error = timer_shard_identity_error(
        layers_owner, task8_carrier, timer_owner, timer_carrier,
        catalog_owner, catalog_carrier)
    if error is not None:
        raise SystemExit(error)

    public = TIMER_PUBLIC_APIS[0]
    public_row = timer_owner[public]
    negative_fixtures = []

    moved_public_carrier = dict(timer_carrier)
    moved_public_carrier[public] = (
        public_row[0] + 2, *moved_public_carrier[public][1:])
    negative_fixtures.append((layers_owner, task8_carrier, timer_owner,
                              moved_public_carrier, catalog_owner,
                              catalog_carrier))
    absolute_public_carrier = dict(timer_carrier)
    absolute_public_carrier[public] = (
        *absolute_public_carrier[public][:4], "ABS")
    negative_fixtures.append((layers_owner, task8_carrier, timer_owner,
                              absolute_public_carrier, catalog_owner,
                              catalog_carrier))
    truncated_timer_owner = dict(timer_owner)
    text_end = timer_owner["__text_end"]
    truncated_timer_owner["__text_end"] = (
        (public_row[0] & ~1) + public_row[1] - 2, *text_end[1:])
    negative_fixtures.append((layers_owner, task8_carrier,
                              truncated_timer_owner, timer_carrier,
                              catalog_owner, catalog_carrier))
    extra_public_carrier = dict(timer_carrier)
    extra_public_carrier["UnexpectedTimerExport"] = public_row
    negative_fixtures.append((layers_owner, task8_carrier, timer_owner,
                              extra_public_carrier, catalog_owner,
                              catalog_carrier))

    if any(timer_shard_identity_error(*fixture) is None
           for fixture in negative_fixtures):
        raise SystemExit("overlay 159 typed-owner negative fixture was accepted")

    # Every actual cross-overlay call gets both drift and ELF-type negatives.
    # This makes coverage systematic instead of relying on one representative
    # API from each owner.
    for name in TIMER_LAYER_IMPORT_APIS + TIMER_CATALOG_IMPORT_APIS:
        row = timer_owner[name]
        if name in TIMER_LAYER_IMPORT_APIS:
            carrier = task8_carrier
            carrier_slot = 1
        else:
            carrier = catalog_carrier
            carrier_slot = 5
        moved_consumer = dict(timer_owner)
        moved_consumer[name] = (row[0] + 2, *row[1:])
        mistyped_consumer = dict(timer_owner)
        mistyped_consumer[name] = (
            row[0], row[1], "NOTYPE", *row[3:])
        carrier_row = carrier[name]
        moved_carrier = dict(carrier)
        moved_carrier[name] = (
            carrier_row[0] + 2, *carrier_row[1:])
        mistyped_carrier = dict(carrier)
        mistyped_carrier[name] = (
            carrier_row[0], carrier_row[1], "NOTYPE", *carrier_row[3:])
        for label, candidate_consumer, candidate_carrier in (
                ("consumer address drift", moved_consumer, carrier),
                ("consumer ELF mistyping", mistyped_consumer, carrier),
                ("carrier address drift", timer_owner, moved_carrier),
                ("carrier ELF mistyping", timer_owner, mistyped_carrier)):
            arguments = [layers_owner, task8_carrier, candidate_consumer,
                         timer_carrier, catalog_owner, catalog_carrier]
            arguments[carrier_slot] = candidate_carrier
            if timer_shard_identity_error(*arguments) is None:
                raise SystemExit(
                    f"overlay 159 accepted {label} for imported {name}"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("elf", type=Path)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--overlay", type=int, choices=CONFIG, required=True)
    parser.add_argument("--prelink-object", action="store_true")
    parser.add_argument("--minimum-headroom", type=lambda value: int(value, 0))
    parser.add_argument("--task5-owner", type=Path)
    parser.add_argument("--lifecycle-consumer", type=Path)
    parser.add_argument("--lifecycle-object", type=Path)
    parser.add_argument("--scalar-shard", type=Path)
    parser.add_argument("--core-owner", type=Path)
    parser.add_argument("--catalog-owner", type=Path)
    parser.add_argument("--catalog-carrier", type=Path)
    parser.add_argument("--task8-carrier", type=Path)
    parser.add_argument("--layers-owner", type=Path)
    parser.add_argument("--timer-carrier", type=Path)
    parser.add_argument("--timer-object", type=Path)
    parser.add_argument("--production-object", type=Path)
    parser.add_argument("--runtime-carrier", type=Path)
    parser.add_argument("--spawns-consumer", type=Path)
    args = parser.parse_args()
    if args.prelink_object:
        if args.overlay != 149 or args.binary is not None:
            raise SystemExit("pre-link object mode is exclusive to overlay 149")
        verify_overlay_149_prelink_object(args.elf)
        return 0
    if args.binary is None:
        raise SystemExit("--binary is required for linked overlay verification")
    if args.overlay in (157, 158, 159):
        verify_exact_production_link(args)
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
        required.add("OverworldWildBehaviorValidator_LoadCatalog")
    if args.overlay == 157:
        required.update((
            "__bss_start__",
            "__bss_end__",
            "OverworldWildBehavior_ReleaseValidatedBundle",
            "OverworldWildBehavior_FreeValidatedBundle",
            "OverworldWildRuntime_CopyInstalledDefinition",
            "OverworldWildRuntime_CopyInstalledCatalogIdentity",
            "OverworldWildRuntime_MarkResidentCold",
            "OverworldWildRuntime_ResolveRetainedStaticCache",
            "OverworldWildRuntime_CopyValidatedSpawnConfiguration",
            "OverworldWildRuntime_MatchesPendingTimerExpiry",
            "OverworldWildRuntime_CopyInstalledModifierOperations",
            "OverworldWildRuntime_AcquireInstalledTransitionCatalog",
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
            "OverworldWildRuntime_ApplyStackDeltaCompact",
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
    if args.overlay == 159:
        required.update(("__bss_start__", "__bss_end__", *TIMER_PUBLIC_APIS))
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

    allocated = read_linked_allocated_sections(args.elf)
    end = origin
    initialized_end = origin
    saw_text = False
    for name, size, address, alignment, has_contents in allocated:
        if size == 0:
            continue
        if (address < origin or address + size > origin + length
                or address % alignment != 0):
            raise SystemExit(
                f"overlay {args.overlay}: allocated section {name} escaped "
                "or violated its linked alignment"
            )
        if name == ".text":
            saw_text = address == origin
        end = max(end, address + size)
        if has_contents:
            initialized_end = max(initialized_end, address + size)
    end = max(end, symbols["_end"])
    if not saw_text or end > origin + length:
        raise SystemExit(
            f"overlay {args.overlay}: all allocated sections do not fit fixed window"
        )
    raw_size = args.binary.stat().st_size
    if raw_size != max(0, initialized_end - origin):
        raise SystemExit(
            f"overlay {args.overlay}: raw size {raw_size} != initialized "
            f"allocated span {initialized_end - origin}"
        )
    if args.overlay == 149 and (end != 0x023D7F3C or raw_size != 0xAF3C):
        raise SystemExit(
            f"overlay 149: sealed boundary changed: end=0x{end:08X} raw=0x{raw_size:X}"
        )
    if args.overlay == 156:
        raw = args.binary.read_bytes()
        callback = int.from_bytes(raw[8:12], "little")
        expected_callback = symbols["OverworldWildBehaviorValidator_LoadCatalog"] | 1
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
    if args.overlay in (157, 158, 159):
        verify_core_thumb_imports(
            args.core_owner, args.elf, args.production_object)
        bss_size = symbols["__bss_end__"] - symbols["__bss_start__"]
        bss_limit = 0 if args.overlay == 159 else 0x140
        if bss_size < 0 or bss_size > bss_limit:
            raise SystemExit(
                f"overlay {args.overlay}: BSS 0x{bss_size:X} exceeds fixed "
                f"0x{bss_limit:X} budget"
            )
        if symbols["__bss_end__"] != end:
            raise SystemExit(
                f"overlay {args.overlay}: allocated image end does not include "
                "the exact aligned BSS end"
            )
        usable_end = {
            157: 0x023BD380,
            158: 0x023BB900,
            159: 0x023C0380,
        }[args.overlay]
        if symbols["__bss_end__"] > usable_end:
            raise SystemExit(
                f"overlay {args.overlay}: complete image exceeds 0x{usable_end:08X}"
            )
        veneers = {
            name for name in symbols
            if "_from_thumb" in name or "veneer" in name.lower()
        }
        if veneers:
            raise SystemExit(
                f"overlay {args.overlay}: unexpected interworking veneer: "
                + ", ".join(sorted(veneers))
            )
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
        if args.overlay == 159:
            if (args.layers_owner is None or args.task8_carrier is None
                    or args.timer_carrier is None
                    or args.catalog_owner is None
                    or args.catalog_carrier is None
                    or args.timer_object is None):
                raise SystemExit(
                    "overlay 159: same-build source object, layers/catalog "
                    "owners, and typed carriers are required"
                )
            verify_timer_shard_identity(
                args.layers_owner, args.task8_carrier, args.elf,
                args.timer_carrier, args.catalog_owner,
                args.catalog_carrier, args.timer_object)
    headroom = origin + length - end
    if headroom < minimum:
        raise SystemExit(f"overlay {args.overlay}: headroom {headroom} below required {minimum}")
    extra = ""
    if args.overlay in (157, 158, 159):
        extra = (
            f" initialized={initialized_end - origin}"
            f" allocSections={len(allocated)}"
            f" bss={symbols['__bss_end__'] - symbols['__bss_start__']}"
        )
    print(f"overlay {args.overlay}: origin=0x{origin:08X} end=0x{end:08X} raw={raw_size} headroom={headroom}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
