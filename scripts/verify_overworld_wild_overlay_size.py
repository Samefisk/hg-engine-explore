#!/usr/bin/env python3
"""Identity and fixed-window gate for overworld-wild overlays 149, 156, and 157."""

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
    # Boot-resident Task-8 service. The final 0x80 and all but 0x140 of BSS
    # remain unavailable even though the linker owns the complete 0x2000 window.
    157: (0x023BB400, 0x2000, "OverworldWildBehavior_LoadValidatedBundle", 0x80),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("elf", type=Path)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--overlay", type=int, choices=CONFIG, required=True)
    parser.add_argument("--minimum-headroom", type=lambda value: int(value, 0))
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
            "OverworldWildRuntime_HandleSlotGenerationWrap",
            "OverworldWildRuntime_BindPrivateIdentity",
            "OverworldWildRuntime_ApplyStackDelta",
            "OverworldWildRuntime_Apply",
            "OverworldWildRuntime_Replace",
            "OverworldWildRuntime_Remove",
            "OverworldWildRuntime_RemoveOwner",
            "OverworldWildRuntime_ClearAllForSlot",
            "OverworldWildRuntime_GetLayerCount",
            "OverworldWildRuntime_GetLayerByIndex",
            "OverworldWildRuntime_FindLayer",
        ))
    missing = sorted(required - symbols.keys())
    if missing: raise SystemExit(f"overlay {args.overlay}: missing identity symbols: {', '.join(missing)}")
    if symbols["__text_start"] != origin or symbols[entry_name] != origin:
        raise SystemExit(f"overlay {args.overlay}: entry/text origin identity mismatch")
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
    if args.overlay == 157:
        bss_size = symbols["__bss_end__"] - symbols["__bss_start__"]
        if bss_size < 0 or bss_size > 0x140:
            raise SystemExit(
                f"overlay 157: BSS 0x{bss_size:X} exceeds fixed 0x140 budget"
            )
        if symbols["__bss_end__"] > 0x023BD380:
            raise SystemExit("overlay 157: complete image exceeds 0x023BD380")
        veneers = {
            name for name in symbols
            if "_from_thumb" in name or "veneer" in name.lower()
        }
        if veneers != {"__memcpy_from_thumb", "__memset_from_thumb"}:
            raise SystemExit(
                "overlay 157: interworking veneer inventory changed: "
                + ", ".join(sorted(veneers))
            )
        for name in veneers:
            if not origin <= symbols[name] < symbols["__text_end"]:
                raise SystemExit(f"overlay 157: {name} escaped the fixed image")
        relocations = subprocess.check_output(
            ["arm-none-eabi-objdump", "-r", args.elf], text=True
        )
        if "R_ARM_" in relocations:
            raise SystemExit("overlay 157: unresolved relocation remains after resident link")
    headroom = origin + length - end
    if headroom < minimum:
        raise SystemExit(f"overlay {args.overlay}: headroom {headroom} below required {minimum}")
    extra = ""
    if args.overlay == 157:
        extra = f" bss={symbols['__bss_end__'] - symbols['__bss_start__']}"
    print(f"overlay {args.overlay}: origin=0x{origin:08X} end=0x{end:08X} raw={raw_size} headroom={headroom}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
