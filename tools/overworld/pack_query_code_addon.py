"""Package only the typed Trigger/Cargo/route addon ARM image; no ROM edits."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

MAGIC, VERSION, HEADER, ENTRY = 0x51444F57, 9, 64, 196
BASE, MAX_IMAGE, MAX_BLOB, MAX_RECORDS = 0x02080000, 0x10C38, 0x11200, 256
CARGO_PREFIX_CAP = 0x8800
IMPORTS = {"memset": 0x023DEEA3, "memcpy": 0x023DEEBF, "__aeabi_uidivmod": 0x023DEE4D,
    "OverworldConditionPublication_InitResult": 0x01FF9A49,
    "OverworldConditionPublication_FoldResult": 0x01FF9C95,
    "OverworldConditionPublication_BlobValid": 0x01FFA39D,
    "OverworldConditionPublication_CapturePrior": 0x023C2F75,
    "OverworldConditionSubject_Populate": 0x02208201,
    "OverworldConditionVisibility_PlayerX": 0x0205C67D,
    "OverworldConditionVisibility_PlayerY": 0x0205C689,
    "OverworldConditionVisibility_TraceBlocked": 0x023C7EA9,
    "OverworldBehaviorPackedOptions_Apply": 0x01FFD2CD}
FUNCTIONS = (
    "OverworldTargetBindings_Init", "OverworldTargetBindings_CaptureEntry",
    "OverworldTargetBindings_Resolve", "OverworldTargetBindings_Clear",
    "OverworldTargetBindings_ClearAll", "OverworldPickupRoute_Begin",
    "OverworldPickupRoute_Resume", "OverworldPickupRouteNative_Classify",
    "OverworldPickupRouteNative_PickupGoal",
    "OverworldPickupRouteNative_Landing",
    "OverworldBehaviorCondition_PrepareActor", "OverworldBehaviorCondition_EvaluatePrepared",
    "OverworldBehaviorResolver_QueryCall", "OverworldBehaviorCondition_NotifyWorldEffect",
    "OverworldCargoQuery_Init", "OverworldCargoQuery_Clear", "OverworldCargoQuery_Tick",
    "OverworldPickupRouteWild_AtomicPickup",
    "OverworldCargoQueryWild_Tick",
    "OverworldPickupLandingWild_Classify",
    "OverworldCargoReadWild_Route", "OverworldCargoReadWild_Observe",
    "OverworldCargoReadWild_Reach", "OverworldCargoReadWild_ActorState",
    "OverworldCargoReadWild_Options",
    "OverworldCargoReadWild_Target",
    "OverworldThrowAwayWild_Read",
    "OverworldPlayerDamageCondition_Read",
    "OverworldConditionNative_Run",
    "OverworldThrowObservationQuery_Observe",
    "OverworldThrowHeldWild_Run",
    "OverworldPlayerDamageCondition_Publish",
    "OverworldContactGeometry_Intersects",
    "OverworldReturnMoveWild_Request", "OverworldReturnMoveWild_IsCurrent",
    "OverworldReturnMoveWild_TryStart", "OverworldReturnMoveWild_Finish",
    "OverworldReturnMoveWild_CombatWork",
    "OverworldHopClearance_Run",
)
# Preserve the existing five Return callback identities and byte offsets.
RETURN_FUNCTIONS = FUNCTIONS[33:38]
CALLBACK_OFFSETS = (*range(20, 76, 4), *range(84, 100, 4), *range(112, ENTRY, 4))
RETURN_CALLBACK_OFFSETS = CALLBACK_OFFSETS[33:38]
NATIVE_FUNCTIONS = (*RETURN_FUNCTIONS, "OverworldConditionNative_Run", "OverworldPickupRouteWild_AtomicPickup", "OverworldCargoReadWild_Observe", "OverworldBehaviorResolver_QueryCall", "OverworldBehaviorCondition_PrepareActor", "OverworldBehaviorCondition_EvaluatePrepared", "OverworldBehaviorCondition_NotifyWorldEffect")
NATIVE_CALLBACK_OFFSETS = (*RETURN_CALLBACK_OFFSETS, 152, CALLBACK_OFFSETS[17], CALLBACK_OFFSETS[21], CALLBACK_OFFSETS[12], 60, 64, 72)
ENTRY_FUNCTIONS = ("OverworldCargoQueryWild_Tick", "OverworldHopClearance_Run")
ENTRY_CALLBACK_OFFSETS = (112, 192)
# Only these typed owner edges may cross from the protected Cargo prefix to
# the new Entry tail. Every branch/word remains bound to exact F extents.
PREFIX_ENTRY_BINDINGS = (
    ("OverworldCargoReadWild_Route", "OverworldCargoQueryWild_Tick"),
    ("EdgePolicy", "OverworldPreparedMovement_Run"),
    ("EdgePolicy", "OverworldPreparedMovement_Begin"),
    ("EdgePolicy", "OverworldPreparedMovement_Step"),
)


def require(condition, reason):
    if not condition:
        raise ValueError("query code addon: " + reason)


def checksum(data):
    result = 2166136261
    for index, byte in enumerate(data):
        result = ((result ^ (0 if 44 <= index < 48 else byte)) * 16777619) & 0xFFFFFFFF
    return result


def _span(data, start, size):
    require(0 <= start <= len(data) and 0 <= size <= len(data) - start,
            "ELF span exceeds file")
    return data[start:start + size]


def _name(strings, offset):
    require(0 <= offset < len(strings), "ELF name offset differs")
    end = strings.find(b"\0", offset)
    require(end >= offset, "ELF name is unterminated")
    return strings[offset:end].decode("ascii")


def package(data):
    require(data[:7] == b"\x7fELF\x01\x01\x01" and len(data) >= 52,
            "expected little-endian ELF32")
    require(struct.unpack_from("<HH", data, 16) == (2, 40)
            and struct.unpack_from("<I", data, 36)[0] >> 24 == 5,
            "expected fully linked ARM EABI5")
    table = struct.unpack_from("<I", data, 32)[0]
    stride, count, names_index = struct.unpack_from("<HHH", data, 46)
    require(stride == 40 and names_index < count, "ELF section table differs")
    raw = _span(data, table, count * stride)
    sections = [struct.unpack_from("<10I", raw, index * stride) for index in range(count)]
    names = sections[names_index]
    strings = _span(data, names[4], names[5])
    text_indices = [index for index, row in enumerate(sections) if _name(strings, row[0]) == ".text"]
    require(len(text_indices) == 1, "expected one image section")
    text_index = text_indices[0]
    text = sections[text_index]
    require(text[1] == 1 and text[2] & 7 == 6 and text[3] == BASE
            and ENTRY <= text[5] <= MAX_IMAGE and text[5] % 4 == 0,
            "image address/flags/alignment/size differs")
    for index, row in enumerate(sections):
        require(index == text_index or not (row[2] & 2 and row[5]),
                "mutable data, BSS or another allocated section is unsupported")
    image = _span(data, text[4], text[5])
    require(struct.unpack_from("<I8H", image) == (MAGIC, VERSION, ENTRY, 60, 188, 24, 108, 36, 3),
            "typed entry or native value layouts differ")
    # The native shared layout is explicitly published by the built entry.
    # Caller/package validators bind its version and sizes to current headers.
    condition_version, world_size, prepared_size, result_size = struct.unpack_from("<4H", image, 76)
    require(condition_version == 13 and world_size == 248 and prepared_size == 88 and result_size == 540,
            "condition value layouts differ")
    require(struct.unpack_from("<6H", image, 100) == (2, 424, 40, 140, 24604, 0),
            "Cargo query value layouts differ")
    symbols_tables = [row for row in sections if row[1] == 2]
    require(len(symbols_tables) == 1, "expected one full symbol table")
    symbols_row = symbols_tables[0]
    require(symbols_row[9] == 16 and symbols_row[5] % 16 == 0
            and symbols_row[6] < count, "ELF symbols differ")
    symbol_strings = sections[symbols_row[6]]
    symbol_names = _span(data, symbol_strings[4], symbol_strings[5])
    raw_symbols = _span(data, symbols_row[4], symbols_row[5])
    symbols = []
    for offset in range(0, len(raw_symbols), 16):
        name, value, size, info, other, section = struct.unpack_from("<IIIBBH", raw_symbols, offset)
        symbols.append((_name(symbol_names, name), value, size, info & 15, section))
        if section == text_index and info & 15 == 2 and size:
            require(value & 1 and BASE + ENTRY <= (value & ~1) < BASE + len(image)
                    and size <= BASE + len(image) - (value & ~1),
                    "image contains ARM or out-of-bounds function code")
    by_name = {row[0]: row for row in symbols}
    cargo_end = by_name.get("__query_cargo_code_end")
    return_end = by_name.get("__query_return_code_end")
    entry_begin = by_name.get("__query_entry_code_begin")
    entry_end = by_name.get("__query_entry_code_end")
    require(all(row is not None and row[4] == 0xFFF1
                for row in (cargo_end, return_end, entry_begin, entry_end))
            and BASE + ENTRY <= cargo_end[1] <= BASE + CARGO_PREFIX_CAP
            and cargo_end[1] < return_end[1] == entry_begin[1] < entry_end[1]
            and entry_end[1] == BASE + len(image)
            and all(row[1] % 4 == 0 for row in (cargo_end, return_end, entry_begin, entry_end)),
            "authenticated Cargo prefix/return/Entry tail boundaries differ")
    # A unique typed containing owner is required for each new crossing; a
    # copied word in unrelated data/code cannot stand in for that owner.
    def prefix_entry_edge(site, target):
        matches=[]
        for caller, callee in PREFIX_ENTRY_BINDINGS:
            owners=[row for row in symbols if row[0] == caller
                and row[3] == 2 and row[4] == text_index
                and BASE + ENTRY <= (row[1] & ~1) < cargo_end[1]]
            targets=[row for row in symbols if row[0] == callee]
            if len(owners) != 1 or len(targets) != 1:
                continue
            owner, destination=owners[0], targets[0]
            if (owner[3] == destination[3] == 2
                    and owner[4] == destination[4] == text_index
                    and owner[1] & destination[1] & 1
                    and owner[2] > 0 and destination[2] > 0
                    and BASE + ENTRY <= (owner[1] & ~1) < cargo_end[1]
                    and owner[2] <= cargo_end[1] - (owner[1] & ~1)
                    and entry_begin[1] <= (destination[1] & ~1) < entry_end[1]
                    and destination[2] <= entry_end[1] - (destination[1] & ~1)
                    and (owner[1] & ~1) <= BASE + site
                    and BASE + site + 4 <= (owner[1] & ~1) + owner[2]
                    and target == (destination[1] & ~1)):
                matches.append((caller,callee))
        return len(matches) == 1
    cargo_bytes = cargo_end[1] - BASE
    entry = by_name.get("gOverworldQueryCodeAddonEntry")
    require(entry is not None and entry[1:] == (BASE, ENTRY, 1, text_index),
            "entry is not the exact hosted object")
    for index, name in enumerate(FUNCTIONS):
        symbol = by_name.get(name)
        require(symbol is not None and symbol[3] == 2 and symbol[4] == text_index
                and symbol[1] & 1 and symbol[2] > 0
                and struct.unpack_from("<I", image, CALLBACK_OFFSETS[index])[0] == symbol[1],
                "typed callback is not its exact hosted Thumb function: " + name)
        low, high = ((entry_begin[1], entry_end[1]) if name in ENTRY_FUNCTIONS
            else (cargo_end[1], return_end[1]) if name in NATIVE_FUNCTIONS
            else (BASE + ENTRY, cargo_end[1]))
        require(low <= (symbol[1] & ~1) < high
                and symbol[2] <= high - (symbol[1] & ~1),
                "typed callback crosses its Cargo/return code boundary: " + name)
    local, imported, calls = [], [], []
    relocation_sections = [row for row in sections if row[1] in (4, 9) and row[5]]
    require(relocation_sections, "--emit-relocs is required")
    for row in relocation_sections:
        require(row[1] == 9 and row[9] == 8 and row[5] % 8 == 0
                and row[7] == text_index and row[6] == sections.index(symbols_row),
                "unsupported relocation section")
        raw_relocations = _span(data, row[4], row[5])
        for offset in range(0, len(raw_relocations), 8):
            address, info = struct.unpack_from("<II", raw_relocations, offset)
            kind, symbol_index = info & 255, info >> 8
            require(symbol_index < len(symbols), "relocation symbol differs")
            name, value, _size, symbol_type, section = symbols[symbol_index]
            site = address - BASE
            require(0 <= site <= len(image) - 4, "relocation is outside image")
            if kind == 2:  # R_ARM_ABS32: local words or exact pinned imports only.
                require(site % 4 == 0, "ABS32 is not word aligned")
                word = struct.unpack_from("<I", image, site)[0]
                if section == text_index:
                    require(BASE <= (word & ~1) < BASE + len(image), "local ABS32 target is outside image")
                    require(site >= cargo_bytes or (word & ~1) < cargo_end[1]
                            or (site in NATIVE_CALLBACK_OFFSETS and (word & ~1) < return_end[1])
                            or (site in ENTRY_CALLBACK_OFFSETS and (word & ~1) >= entry_begin[1])
                            or (symbol_type == 2 and word == value
                                and prefix_entry_edge(site, word & ~1)),
                            "Cargo prefix references an unbound return/Entry tail")
                    local.append(site)
                else:
                    require(section == 0xFFF1 and symbol_type == 2 and name in IMPORTS
                            and value == word == IMPORTS[name], "unapproved or untyped fixed import")
                    imported.append((site, word))
            elif kind == 10:  # R_ARM_THM_CALL: relative and local; never rebased.
                require(section == text_index and symbol_type == 2 and value & 1,
                        "external/ARM Thumb call is unsupported")
                first, second = struct.unpack_from("<HH", image, site)
                require(first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800,
                        "local call is not direct Thumb BL")
                delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
                if delta & (1 << 22):
                    delta -= 1 << 23
                target = address + 4 + delta
                require(target == value & ~1, "local Thumb BL target differs from its function")
                require(site >= cargo_bytes or target < cargo_end[1]
                        or prefix_entry_edge(site,target),
                        "Cargo prefix calls an unbound return/Entry tail")
                calls.append((site, target - BASE))
            else:
                raise ValueError(f"query code addon: unsupported relocation kind {kind}")
    local.sort(); imported.sort()
    locations = local + [offset for offset, _ in imported]
    require(len(locations) == len(set(locations)) and len(local) <= MAX_RECORDS
            and len(imported) <= MAX_RECORDS, "duplicate or excessive relocations")
    require(set(CALLBACK_OFFSETS).issubset(local), "entry callback relocation is missing")
    relocation_offset = HEADER + len(image)
    import_offset = relocation_offset + len(local) * 4
    blob_size = import_offset + len(imported) * 8
    require(blob_size <= MAX_BLOB, "package exceeds loader allocation cap")
    header = struct.pack("<IHH10IHH3I", MAGIC, VERSION, HEADER,
        blob_size, len(image), BASE, 0, HEADER, relocation_offset, len(local),
        import_offset, len(imported), 0, VERSION, ENTRY, 0, 0, 0)
    blob = bytearray(header + image + b"".join(struct.pack("<I", offset) for offset in local)
        + b"".join(struct.pack("<II", *record) for record in imported))
    struct.pack_into("<I", blob, 44, checksum(blob))
    return bytes(blob), {"imageBytes": len(image), "packageBytes": len(blob),
        "cargoCodeBytes": cargo_bytes, "returnCodeBytes": return_end[1] - cargo_end[1],
        "entryCodeBytes": entry_end[1] - entry_begin[1],
        "entryNativeOpsVersion": 2, "entryNativeOpsBytes": 72,
        "prefixEntryBindings": PREFIX_ENTRY_BINDINGS,
        "localAbs32": local, "fixedImports": imported, "localThumbCalls": calls,
        "elfSha256": hashlib.sha256(data).hexdigest(), "packageSha256": hashlib.sha256(blob).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--header", type=Path)
    args = parser.parse_args()
    blob, receipt = package(args.elf.read_bytes())
    args.output.write_bytes(blob)
    if args.receipt:
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
    if args.header:
        args.header.write_text(
            "/* Generated by pack_query_code_addon.py; exact native package. */\n"
            "#ifndef OVERWORLD_QUERY_CODE_ADDON_PACKAGE_H\n"
            "#define OVERWORLD_QUERY_CODE_ADDON_PACKAGE_H\n"
            f"#define OVERWORLD_QUERY_CODE_ADDON_PACKAGE_BYTES {len(blob)}u\n"
            f"#define OVERWORLD_QUERY_CODE_ADDON_PACKAGE_IMAGE_BYTES {receipt['imageBytes']}u\n"
            f"#define OVERWORLD_QUERY_CODE_ADDON_PACKAGE_CHECKSUM 0x{checksum(blob):08X}u\n"
            "#endif\n")


if __name__ == "__main__":
    main()
