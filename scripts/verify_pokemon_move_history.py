#!/usr/bin/env python3

import argparse
import ast
from collections import defaultdict
import hashlib
import json
import re
import struct
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
OVERLAY_ID = 153
OVERLAY_BASE = 0x023BE400
OVERLAY_LIMIT = 0x023C0400
OVERLAY_GUARD = 0x1000
TASK6_OVERLAY_ID = 155
TASK6_OVERLAY_BASE = 0x023BD400
TASK6_OVERLAY_LIMIT = 0x023BE400
RUNTIME_OVERLAY_ID = 157
RUNTIME_OVERLAY_BASE = 0x023BB980
RUNTIME_OVERLAY_USABLE_END = 0x023BD380
RUNTIME_OVERLAY_LIMIT = 0x023BD400
RUNTIME_LAYERS_OVERLAY_ID = 158
RUNTIME_LAYERS_OVERLAY_BASE = 0x023B8400
RUNTIME_LAYERS_OVERLAY_USABLE_END = 0x023BB900
RUNTIME_LAYERS_OVERLAY_LIMIT = 0x023BB980
RUNTIME_TIMERS_OVERLAY_ID = 159
RUNTIME_TIMERS_OVERLAY_BASE = 0x023BF480
RUNTIME_TIMERS_OVERLAY_USABLE_END = 0x023C0380
RUNTIME_TIMERS_OVERLAY_LIMIT = 0x023C0400
EXPECTED_ARCHIVE_END = 0x023B7268
EXPECTED_ARCHIVE_MARGIN = 0x1198
EXPECTED_FREE_MARGIN = 0x198
MAIN_RAM_START = 0x02000000
MAIN_ARENA_HIGH = 0x023E0000
DTCM_START = 0x027E0000
DTCM_END = DTCM_START + 0x4000
ROW_SIZE = 0x20
RESIDENT_RUNTIME_HELPER_ADDRESS = 0x021102E0
RESIDENT_RUNTIME_HELPER_BYTES = bytes.fromhex(
    "38 B5 9D 24 21 1C FF F7 F5 FF 01 34 A0 2C F9 D3 38 BD FF FF"
)
RESIDENT_RUNTIME_HELPER_PADDING_ADDRESS = 0x021102F4
RESIDENT_RUNTIME_HELPER_PADDING_BYTES = b"\xFF" * 4
RESIDENT_RUNTIME_ADJACENT_WORD_ADDRESS = 0x021102F8
RESIDENT_RUNTIME_ADJACENT_WORD_BYTES = b"\x02\x00\x00\x00"
RESIDENT_RUNTIME_STARTUP_ADDRESS = 0x02110334
RESIDENT_RUNTIME_STARTUP_BYTES = bytes.fromhex(
    "04 B5 81 20 02 21 FF F7 C3 FF 9B 21 FF F7 C8 FF "
    "FF F7 CC FF 99 21 FF F7 C3 FF 00 20 03 21 04 BD"
)
RESIDENT_RUNTIME_STARTUP_PRESERVED_ADDRESS = 0x02110354
RESIDENT_RUNTIME_STARTUP_PRESERVED_BYTES = bytes.fromhex(
    "FF FF FF FF 02 00 00 00"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"move-history verifier: {message}")


def align4(value: int) -> int:
    return (value + 3) & ~3


def ranges_overlap(
    first_start: int,
    first_end: int,
    second_start: int,
    second_end: int,
) -> bool:
    return first_start < second_end and second_start < first_end


def parse_define(source: str, name: str) -> int:
    match = re.search(
        rf"^#define {re.escape(name)} (0x[0-9a-fA-F]+|[0-9]+)$",
        source,
        re.MULTILINE,
    )
    require(match is not None, f"{name} is missing")
    return int(match.group(1), 0)


def checked_slice(
    data: bytes,
    offset: int,
    size: int,
    description: str,
) -> bytes:
    require(
        offset >= 0 and size >= 0 and offset + size <= len(data),
        f"{description} lies outside the completed ROM",
    )
    return data[offset:offset + size]


def read_u32(data: bytes, offset: int, description: str) -> int:
    require(offset >= 0 and offset + 4 <= len(data),
            f"{description} is outside its binary")
    return struct.unpack_from("<I", data, offset)[0]


def read_u16(data: bytes, offset: int, description: str) -> int:
    require(offset >= 0 and offset + 2 <= len(data),
            f"{description} is outside its binary")
    return struct.unpack_from("<H", data, offset)[0]


def resident_runtime_bootstrap_bytes_match(
    arm9: bytes,
    arm9_ram: int,
) -> bool:
    expected_regions = (
        (RESIDENT_RUNTIME_HELPER_ADDRESS, RESIDENT_RUNTIME_HELPER_BYTES),
        (
            RESIDENT_RUNTIME_HELPER_PADDING_ADDRESS,
            RESIDENT_RUNTIME_HELPER_PADDING_BYTES,
        ),
        (
            RESIDENT_RUNTIME_ADJACENT_WORD_ADDRESS,
            RESIDENT_RUNTIME_ADJACENT_WORD_BYTES,
        ),
        (RESIDENT_RUNTIME_STARTUP_ADDRESS, RESIDENT_RUNTIME_STARTUP_BYTES),
        (
            RESIDENT_RUNTIME_STARTUP_PRESERVED_ADDRESS,
            RESIDENT_RUNTIME_STARTUP_PRESERVED_BYTES,
        ),
    )
    for address, expected in expected_regions:
        offset = address - arm9_ram
        if (offset < 0 or offset + len(expected) > len(arm9)
                or arm9[offset:offset + len(expected)] != expected):
            return False
    return True


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_boot_decoder_freshness(
    manifest_path: Path,
    rom: bytes,
    arm9: bytes,
    runtime_overlay: bytes,
    runtime_layers_overlay: bytes,
    runtime_timers_overlay: bytes,
    patched_arm9: bytes,
) -> None:
    require(manifest_path.is_file(),
            "packaged boot decoder requires the captured build manifest")
    manifest = json.loads(manifest_path.read_text())
    require(manifest.get("schema") == "pokemon-move-history-capture-build-v1",
            "packaged boot decoder build manifest schema differs")
    inputs = manifest.get("inputs", {})
    for path_text in (
        "armips/asm/syntheticoverlay.s",
        "src/overworld_wild_runtime_overlay/linker.ld",
        "src/overworld_wild_runtime_layers_overlay/linker.ld",
        "src/overworld_wild_runtime_timers_overlay/linker.ld",
        "src/overworld_wild_runtime_overlay/overworld_wild_runtime_layers.c",
        "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c",
        "src/overworld_wild_runtime_timers_overlay/overworld_wild_runtime_timers.c",
    ):
        data = (REPO / path_text).read_bytes()
        record = inputs.get(path_text)
        require(
            isinstance(record, dict)
            and record.get("size") == len(data)
            and record.get("sha256") == sha256(data),
            f"packaged boot decoder source is newer than capture: {path_text}",
        )
    outputs = manifest.get("outputs", {})
    for name, data in (
        ("patched_arm9", patched_arm9),
        ("overworld_wild_runtime_binary", runtime_overlay),
        ("overworld_wild_runtime_layers_binary", runtime_layers_overlay),
        ("overworld_wild_runtime_timers_binary", runtime_timers_overlay),
        ("packaged_rom", rom),
    ):
        record = outputs.get(name)
        require(
            isinstance(record, dict)
            and record.get("size") == len(data)
            and record.get("sha256") == sha256(data),
            f"packaged boot decoder artifact is outside its capture: {name}",
        )
    require(
        patched_arm9.startswith(arm9)
        and len(patched_arm9) - len(arm9) <= 12,
        "packaged ARM9 differs from the captured patched ARM9 span",
    )


def thumb_bl_target(
    image: bytes,
    image_base: int,
    address: int,
    description: str,
) -> int:
    offset = address - image_base
    first = read_u16(image, offset, description + " first halfword")
    second = read_u16(image, offset + 2, description + " second halfword")
    require(
        first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800,
        f"{description} is not a Thumb-1 BL",
    )
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & (1 << 22):
        displacement -= 1 << 23
    return address + 4 + displacement


def measure_boot_archive_layout(
    stock_overlay_end: int,
    full_save_size: int,
    heap3_size: int,
    fnt_size: int,
    fat_size: int,
) -> dict[str, int]:
    """Reproduce the SDK boot allocations that precede resident overlays."""
    cursor = align4(stock_overlay_end + 0x100)
    usable_heaps = 4 + 24
    total_heap_ids = 166
    heap_metadata_size = (
        (usable_heaps + 1) * 4
        + usable_heaps * 4
        + usable_heaps * 4
        + total_heap_ids * 2
        + total_heap_ids
    )
    cursor = align4(cursor + heap_metadata_size)
    for heap_size in (0xD200, full_save_size, 0x10, heap3_size):
        cursor = align4(cursor + heap_size)
    for task_count in (160, 32, 32, 4):
        cursor = align4(cursor + task_count * (28 + 4) + 52)
    archive_start = cursor
    archive_size = (fnt_size + fat_size + 0x3F) & ~0x1F
    archive_end = archive_start + archive_size
    return {
        "archive_start": archive_start,
        "archive_end": archive_end,
        "archive_size": archive_size,
        "heap_metadata_size": heap_metadata_size,
        "archive_margin": RUNTIME_LAYERS_OVERLAY_BASE - archive_end,
        "free_margin": (
            RUNTIME_LAYERS_OVERLAY_BASE - archive_end - OVERLAY_GUARD
        ),
    }


def final_overlay(
    rom: bytes,
    fat: bytes,
    row: tuple[int, ...],
) -> bytes:
    file_id = row[6]
    entry_offset = file_id * 8
    require(entry_offset + 8 <= len(fat),
            f"overlay {row[0]} FAT entry {file_id} is missing")
    file_start, file_end = struct.unpack_from("<II", fat, entry_offset)
    require(file_start < file_end,
            f"overlay {row[0]} FAT entry is empty or reversed")
    return checked_slice(
        rom,
        file_start,
        file_end - file_start,
        f"overlay {row[0]} file",
    )


def nitrofs_file_id(fnt: bytes, path: str) -> int:
    require(len(fnt) >= 8, "final FNT has no root directory entry")
    directory_count = struct.unpack_from("<H", fnt, 6)[0]
    require(
        directory_count != 0 and directory_count * 8 <= len(fnt),
        "final FNT directory table is truncated",
    )
    directory_id = 0xF000
    components = [component for component in path.split("/") if component]
    require(components, "NitroFS path is empty")

    for component_index, component in enumerate(components):
        table_index = directory_id - 0xF000
        require(
            0 <= table_index < directory_count,
            f"NitroFS directory ID {directory_id:#x} is outside the FNT",
        )
        subtable, first_file_id, _parent = struct.unpack_from(
            "<IHH",
            fnt,
            table_index * 8,
        )
        require(subtable < len(fnt), f"FNT directory {directory_id:#x} has a bad subtable")
        cursor = subtable
        file_id = first_file_id
        matches: list[tuple[bool, int]] = []
        while True:
            require(cursor < len(fnt), f"FNT directory {directory_id:#x} is unterminated")
            length_and_type = fnt[cursor]
            cursor += 1
            if length_and_type == 0:
                break
            is_directory = (length_and_type & 0x80) != 0
            name_length = length_and_type & 0x7F
            require(
                name_length != 0 and cursor + name_length <= len(fnt),
                f"FNT directory {directory_id:#x} contains a truncated name",
            )
            name_bytes = fnt[cursor:cursor + name_length]
            cursor += name_length
            try:
                name = name_bytes.decode("ascii")
            except UnicodeDecodeError:
                require(False, f"FNT directory {directory_id:#x} has a non-ASCII name")
            if is_directory:
                require(
                    cursor + 2 <= len(fnt),
                    f"FNT child directory {name} has no directory ID",
                )
                child_id = struct.unpack_from("<H", fnt, cursor)[0]
                cursor += 2
                require(
                    0xF000 <= child_id < 0xF000 + directory_count,
                    f"FNT child directory {name} has invalid ID {child_id:#x}",
                )
                if name == component:
                    matches.append((True, child_id))
            else:
                if name == component:
                    matches.append((False, file_id))
                file_id += 1

        require(
            len(matches) == 1,
            f"NitroFS component {component!r} is missing or ambiguous in {path!r}",
        )
        is_directory, resolved = matches[0]
        if component_index + 1 == len(components):
            require(not is_directory, f"NitroFS path {path!r} resolves to a directory")
            return resolved
        require(is_directory, f"NitroFS component {component!r} is not a directory")
        directory_id = resolved

    raise AssertionError("unreachable")


def nitrofs_file(rom: bytes, fnt: bytes, fat: bytes, path: str) -> tuple[int, bytes]:
    file_id = nitrofs_file_id(fnt, path)
    entry_offset = file_id * 8
    require(entry_offset + 8 <= len(fat), f"NitroFS file {path!r} has no FAT entry")
    start, end = struct.unpack_from("<II", fat, entry_offset)
    require(start <= end, f"NitroFS file {path!r} has a reversed FAT range")
    return file_id, checked_slice(rom, start, end - start, f"NitroFS file {path}")


def narc_members(narc: bytes, label: str) -> list[bytes]:
    require(len(narc) >= 16, f"{label} archive is shorter than its NARC header")
    require(narc[:4] == b"NARC", f"{label} archive has no NARC header")
    require(
        narc[4:8] == bytes.fromhex("fe ff 00 01"),
        f"{label} NARC byte order/version differs",
    )
    declared_size, header_size, chunk_count = struct.unpack_from("<IHH", narc, 8)
    require(declared_size == len(narc), f"{label} NARC declared size differs")
    require((header_size, chunk_count) == (16, 3), f"{label} NARC header shape differs")
    require(narc[16:20] == b"BTAF", f"{label} archive has no BTAF")
    btaf_size = struct.unpack_from("<I", narc, 20)[0]
    file_count = struct.unpack_from("<H", narc, 24)[0]
    require(btaf_size == 12 + file_count * 8, f"{label} BTAF size/count differs")
    require(16 + btaf_size <= len(narc), f"{label} BTAF exceeds archive")
    ranges = [
        struct.unpack_from("<II", narc, 28 + index * 8)
        for index in range(file_count)
    ]
    btnf = 16 + btaf_size
    require(narc[btnf:btnf + 4] == b"BTNF", f"{label} archive has no BTNF")
    btnf_size = struct.unpack_from("<I", narc, btnf + 4)[0]
    require(
        btnf_size >= 8 and btnf + btnf_size <= len(narc),
        f"{label} BTNF exceeds archive",
    )
    gmif = btnf + btnf_size
    require(narc[gmif:gmif + 4] == b"GMIF", f"{label} archive has no GMIF")
    gmif_size = struct.unpack_from("<I", narc, gmif + 4)[0]
    require(
        gmif_size >= 8 and gmif + gmif_size == len(narc),
        f"{label} GMIF size differs",
    )
    payload = gmif + 8
    payload_size = gmif_size - 8
    previous_end = 0
    members: list[bytes] = []
    for index, (start, end) in enumerate(ranges):
        require(start <= end <= payload_size, f"{label} member {index} exceeds GMIF")
        require(
            start >= previous_end,
            f"{label} member {index} overlaps its predecessor",
        )
        members.append(narc[payload + start:payload + end])
        previous_end = end
    return members


def declaration_order_ids(path: Path, kind: str) -> dict[str, int]:
    identifiers: list[str] = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) <= 1:
            continue
        name = parts[1].strip()
        if kind == "species":
            include = (
                "SPECIES" in name
                and "_START" not in name
                and "_SPECIES_H" not in name
                and "_NUM (" not in line
                and "MAX_" not in name
            )
        else:
            include = (
                "MOVE" in name
                and "_START" not in name
                and "_MOVES_H" not in name
                and "NUM_OF" not in name
            )
        if include:
            require(name not in identifiers, f"duplicate {kind} constant {name}")
            identifiers.append(name)
    require(identifiers, f"no {kind} constants were found in {path}")
    return {name: index for index, name in enumerate(identifiers)}


def evaluate_parent_constant(
    expression: str,
    values: dict[str, int],
) -> int:
    def evaluate(node: ast.AST) -> int:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -evaluate(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return evaluate(node.left) + evaluate(node.right)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
            return evaluate(node.left) - evaluate(node.right)
        raise ValueError(f"unsupported parent-oracle constant: {expression}")

    return evaluate(ast.parse(expression, mode="eval").body)


def load_parent_constants(
    path: Path,
    pattern: re.Pattern[str],
) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in path.read_text().splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        name, expression = match.groups()
        expression = expression.split("//", 1)[0].strip()
        try:
            values[name] = evaluate_parent_constant(expression, values)
        except (SyntaxError, ValueError):
            continue
    return values


def without_source_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//.*", "", source)


def build_expected_parent_payload(
) -> tuple[bytes, dict[int, str], int, int]:
    species_header = REPO / "include/constants/species.h"
    species_values = load_parent_constants(
        species_header,
        re.compile(r"^\s*#define\s+([A-Z0-9_]+)\s+(.+?)\s*$"),
    )
    armips_values = load_parent_constants(
        REPO / "asm/include/species.inc",
        re.compile(r"^\s*\.equ\s+([A-Z0-9_]+)\s*,\s*(.+?)\s*$"),
    )
    require(
        "MAX_SPECIES_INCLUDING_FORMS" in species_values,
        "current species header has no reverse-parent table bound",
    )
    maximum = species_values["MAX_SPECIES_INCLUDING_FORMS"]
    require(
        0 <= maximum <= 0xFFFF,
        "current reverse-parent table bound does not fit u16 indexing",
    )
    names_by_id = {
        value: name
        for name, value in species_values.items()
        if name.startswith("SPECIES_")
    }
    require(
        set(range(maximum + 1)).issubset(names_by_id),
        "current C species IDs are not dense through the parent-table bound",
    )
    require(
        all(
            value in names_by_id
            for name, value in armips_values.items()
            if name.startswith("SPECIES_")
        ),
        "an Armips species ID has no C equivalent",
    )

    def canonical_id(symbol: str) -> int:
        require(
            symbol in armips_values,
            f"current evodata references unknown Armips species {symbol}",
        )
        value = armips_values[symbol]
        require(
            value in names_by_id,
            f"Armips species {symbol} ({value}) has no C equivalent",
        )
        return value

    form_source = without_source_comments(
        (REPO / "data/PokeFormDataTbl.c").read_text()
    )
    form_rows: dict[int, list[int]] = {}
    for base, body in re.findall(
        r"\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*\{(.*?)\}",
        form_source,
        re.DOTALL,
    ):
        require(
            base in species_values,
            f"form table references unknown base species {base}",
        )
        forms = re.findall(r"\bSPECIES_[A-Z0-9_]+\b", body)
        require(forms, f"form table row {base} has no species entries")
        require(
            all(form in species_values for form in forms),
            f"form table row {base} references an unknown species",
        )
        base_id = species_values[base]
        require(base_id not in form_rows, f"form table duplicates base {base}")
        form_rows[base_id] = [species_values[form] for form in forms]

    form_to_base_source = without_source_comments(
        (REPO / "data/FormToSpeciesMapping.c").read_text()
    )
    form_to_base: dict[int, int] = {}
    for form, base in re.findall(
        r"\[(SPECIES_[A-Z0-9_]+)\s*-\s*SPECIES_MEGA_START\]\s*=\s*"
        r"(SPECIES_[A-Z0-9_]+)",
        form_to_base_source,
    ):
        require(
            form in species_values and base in species_values,
            f"form-to-species row references an unknown species: {form} -> {base}",
        )
        form_id = species_values[form]
        base_id = species_values[base]
        require(
            form_id not in form_to_base,
            f"form-to-species mapping duplicates {form}",
        )
        form_to_base[form_id] = base_id

    parent_candidates: dict[int, list[int]] = defaultdict(list)
    current: int | None = None
    evodata = without_source_comments(
        (REPO / "armips/data/evodata.s").read_text()
    )
    evodata_re = re.compile(r"^\s*evodata\s+(SPECIES_[A-Z0-9_]+)\b")
    evolution_re = re.compile(
        r"^\s*evolution\s+([^,]+),\s*[^,]+,\s*(SPECIES_[A-Z0-9_]+)\b"
    )
    evolution_with_form_re = re.compile(
        r"^\s*evolutionwithform\s+([^,]+),\s*[^,]+,\s*"
        r"(SPECIES_[A-Z0-9_]+)\s*,\s*([0-9]+)\b"
    )
    for line in evodata.splitlines():
        match = evodata_re.match(line)
        if match is not None:
            current = canonical_id(match.group(1))
            continue
        match = evolution_re.match(line)
        form_match = evolution_with_form_re.match(line)
        if match is None and form_match is None:
            continue
        require(current is not None, "evolution appeared before evodata")
        if match is not None:
            if match.group(1).strip() == "EVO_NONE":
                continue
            target = canonical_id(match.group(2))
        else:
            assert form_match is not None
            if form_match.group(1).strip() == "EVO_NONE":
                continue
            target_base = canonical_id(form_match.group(2))
            form = int(form_match.group(3))
            forms = form_rows.get(target_base, [])
            target = (
                forms[form - 1]
                if form != 0 and form <= len(forms)
                else target_base
            )
        if current not in parent_candidates[target]:
            parent_candidates[target].append(current)

    parents: dict[int, int] = {}
    for target, candidates in parent_candidates.items():
        if len(candidates) == 1:
            parents[target] = candidates[0]
            continue

        candidate_bases = {
            form_to_base.get(candidate, candidate)
            for candidate in candidates
        }
        require(
            len(candidate_bases) == 1,
            f"{names_by_id[target]} has unrelated parent form families",
        )
        base_parent = next(iter(candidate_bases))
        require(
            base_parent in candidates,
            f"{names_by_id[target]} has form parents but no base parent",
        )
        parents[target] = base_parent
        parent_forms = form_rows.get(base_parent, [])
        target_forms = form_rows.get(target, [])
        for candidate in candidates:
            if candidate == base_parent:
                continue
            require(
                candidate in parent_forms,
                f"{names_by_id[candidate]} is absent from its numeric form family",
            )
            form_index = parent_forms.index(candidate)
            require(
                form_index < len(target_forms),
                f"{names_by_id[target]} has no matching numeric form slot "
                f"for {names_by_id[candidate]}",
            )
            form_target = target_forms[form_index]
            require(
                form_target not in parents or parents[form_target] == candidate,
                f"{names_by_id[form_target]} has conflicting numeric parents",
            )
            parents[form_target] = candidate

    # These policy-only derivatives have no evolution edge. Keep them
    # explicit here as a two-party policy gate: changing generator policy must
    # be reviewed independently in the final-ROM oracle.
    derived_overrides = {
        "SPECIES_WORMADAM_SANDY": "SPECIES_BURMY",
        "SPECIES_WORMADAM_TRASHY": "SPECIES_BURMY",
        "SPECIES_RATICATE_ALOLAN_LARGE": "SPECIES_RATTATA_ALOLAN",
        "SPECIES_DARMANITAN_ZEN_MODE_GALARIAN": "SPECIES_DARUMAKA_GALARIAN",
        "SPECIES_ARCANINE_LORD": "SPECIES_GROWLITHE_HISUIAN",
        "SPECIES_ELECTRODE_LORD": "SPECIES_VOLTORB_HISUIAN",
    }
    for target, parent in derived_overrides.items():
        require(
            target in species_values and parent in species_values,
            f"parent-oracle policy references unknown species: {target} -> {parent}",
        )
        parents.setdefault(species_values[target], species_values[parent])

    require(
        not (set(form_to_base) & set(form_to_base.values())),
        "chained form-to-species mappings make parent fallback order-dependent",
    )
    for form, base in sorted(form_to_base.items()):
        if form not in parents and base in parents:
            parents[form] = parents[base]

    runtime_source = (
        REPO
        / "src/pokemon_move_history_overlay/pokemon_move_relearn.c"
    ).read_text()
    limit_match = re.search(
        r"^#define MOVE_RELEARN_LINEAGE_LIMIT ([0-9]+)$",
        runtime_source,
        re.MULTILINE,
    )
    require(limit_match is not None, "runtime lineage limit is missing")
    lineage_limit = int(limit_match.group(1))

    maximum_depth = 0
    for target, parent in parents.items():
        require(
            0 < target <= maximum and 0 < parent <= maximum,
            f"current parent mapping is out of range: {target} -> {parent}",
        )
        require(target != parent, f"current parent mapping is self-referential: {target}")
        seen: set[int] = set()
        current_species = target
        depth = 0
        while current_species in parents:
            require(
                current_species not in seen,
                f"current parent mapping has a cycle at {names_by_id[current_species]}",
            )
            seen.add(current_species)
            current_species = parents[current_species]
            depth += 1
        maximum_depth = max(maximum_depth, depth)
    require(
        maximum_depth < lineage_limit,
        "current parent mapping exceeds the runtime lineage limit",
    )

    values = [0] * (maximum + 1)
    for target, parent in parents.items():
        values[target] = parent

    return (
        struct.pack(f"<{len(values)}H", *values),
        names_by_id,
        len(parents),
        maximum_depth,
    )


def first_parent_mismatch(
    member: bytes,
    expected: bytes,
    names_by_id: dict[int, str],
) -> str | None:
    if len(member) != len(expected):
        return f"size expected {len(expected)} bytes, actual {len(member)} bytes"
    row_count = len(expected) // 2
    for target in range(row_count):
        actual_parent = struct.unpack_from("<H", member, target * 2)[0]
        expected_parent = struct.unpack_from("<H", expected, target * 2)[0]
        if actual_parent == expected_parent:
            continue
        return (
            f"target {target} ({names_by_id.get(target, 'UNKNOWN')}) "
            f"expected {expected_parent} "
            f"({names_by_id.get(expected_parent, 'UNKNOWN')}), "
            f"actual {actual_parent} "
            f"({names_by_id.get(actual_parent, 'UNKNOWN')})"
        )
    return None


def verify_parent_member_against_current_inputs(
    member: bytes,
    expected: bytes,
    names_by_id: dict[int, str],
) -> None:
    mismatch = first_parent_mismatch(member, expected, names_by_id)
    require(
        mismatch is None,
        "final a028 member 20 differs from the current evolution/form input "
        f"oracle: {mismatch}",
    )


def ordered_move_array(path: Path, declaration: str) -> list[str]:
    source = path.read_text()
    start = source.index(declaration)
    end = source.index("};", start)
    moves = re.findall(r"\bMOVE_[A-Z0-9_]+\b", source[start:end])
    require(moves, f"{declaration} has no moves")
    return moves


def ordered_tutor_moves(path: Path) -> list[str]:
    source = path.read_text()
    start = source.index("TutorMove sTutorMoves[]")
    end = source.index("};", start)
    moves = re.findall(
        r"\{\s*(MOVE_[A-Z0-9_]+)\s*,",
        source[start:end],
    )
    require(moves, "field tutor table has no moves")
    return moves


def authoritative_move_layout() -> tuple[int, int, int]:
    header = (REPO / "include/battle.h").read_text()
    struct_match = re.search(
        r"struct\s+__attribute__\(\(packed\)\)\s+BattleMove\s*\{(.*?)"
        r"\};\s*//\s*size\s*=\s*(0x[0-9A-Fa-f]+)",
        header,
        re.DOTALL,
    )
    require(struct_match is not None, "authoritative packed BattleMove is missing")
    flag_match = re.search(
        r"/\*\s*(0x[0-9A-Fa-f]+)\s*\*/\s*u8\s+flag\s*;",
        struct_match.group(1),
    )
    mask_match = re.search(
        r"^#define FLAG_UNUSED_MOVE \((0x[0-9A-Fa-f]+)\)",
        header,
        re.MULTILINE,
    )
    require(
        flag_match is not None and mask_match is not None,
        "BattleMove flag ABI is missing",
    )
    c_offset = int(flag_match.group(1), 16)
    c_size = int(struct_match.group(2), 16)
    mask = int(mask_match.group(1), 16)

    macros = (REPO / "armips/include/movemacros.s").read_text()
    fields = (
        "battleeffect",
        "pss",
        "basepower",
        "type",
        "accuracy",
        "pp",
        "effectchance",
        "target",
        "priority",
        "flags",
        "appeal",
        "contesttype",
        "terminatedata",
    )
    widths = []
    for name in fields:
        match = re.search(
            rf"^\.macro\s+{name}(?:,|\s|$)(.*?)^\.endmacro\s*$",
            macros,
            re.MULTILINE | re.DOTALL,
        )
        require(match is not None, f"move macro {name} is missing")
        emissions = re.findall(
            r"^\s*\.(byte|halfword)\b",
            match.group(1),
            re.MULTILINE,
        )
        require(len(emissions) == 1, f"move macro {name} is not one field")
        widths.append(1 if emissions[0] == "byte" else 2)
    require(
        (sum(widths[:fields.index("flags")]), sum(widths))
        == (c_offset, c_size),
        "C and Armips BattleMove layouts differ",
    )
    return mask, c_offset, c_size


def compact_levelup_payload(
    payload: bytes,
    row_width: int,
    move_flags: list[int],
    unused_mask: int,
) -> bytes:
    row_size = row_width * 4
    require(len(payload) % row_size == 0, "expected level-up payload is misaligned")
    result = bytearray(payload)
    for row_offset in range(0, len(payload), row_size):
        values = list(struct.unpack_from(f"<{row_width}I", payload, row_offset))
        filtered = list(values)
        write = 0
        terminated = False
        for entry in values:
            move = entry & 0xFFFF
            if move == 0xFFFF:
                filtered[write] = entry
                terminated = True
                break
            require(move < len(move_flags), f"learnset references missing move {move}")
            if move_flags[move] & unused_mask == 0:
                filtered[write] = entry
                write += 1
        require(terminated, "expected learnset row has no terminator")
        struct.pack_into(f"<{row_width}I", result, row_offset, *filtered)
    return bytes(result)


def build_expected_learnset_payloads(
    move_data_members: list[bytes],
) -> tuple[dict[str, bytes], dict[str, int]]:
    species_ids = declaration_order_ids(
        REPO / "include/constants/species.h",
        "species",
    )
    move_ids = declaration_order_ids(
        REPO / "include/constants/moves.h",
        "moves",
    )
    require(len(species_ids) == max(species_ids.values()) + 1, "species IDs have gaps")
    learnsets = json.loads(
        (REPO / "data/learnsets/learnsets.json").read_text(encoding="utf-8")
    )
    form_source = (REPO / "data/FormToSpeciesMapping.c").read_text()
    form_to_base = dict(
        re.findall(
            r"\[(SPECIES_\w+)\s*-\s*SPECIES_MEGA_START\]\s*=\s*"
            r"(SPECIES_\w+),",
            form_source,
        )
    )
    for form_species, base_species in form_to_base.items():
        if form_species not in learnsets and base_species in learnsets:
            learnsets[form_species] = dict(learnsets[base_species])

    machine_moves = ordered_move_array(
        REPO / "src/item.c",
        "const u16 sMachineMoves[]",
    )
    tutor_moves = ordered_tutor_moves(REPO / "src/field/move_tutor.c")
    require(
        all(move in move_ids for move in machine_moves + tutor_moves),
        "machine/tutor table references an unknown move",
    )
    level_width = max(
        len(data.get("LevelMoves", [])) + 1
        for data in learnsets.values()
    )
    egg_width = max(
        len(data.get("EggMoves", [])) + 1
        for data in learnsets.values()
    )
    machine_words = (len(machine_moves) + 31) // 32
    tutor_words = (len(tutor_moves) + 31) // 32

    species_by_id = {value: name for name, value in species_ids.items()}
    level_values: list[int] = []
    egg_values: list[int] = []
    machine_values: list[int] = []
    tutor_values: list[int] = []
    tutor_indices = {move: index for index, move in enumerate(tutor_moves)}

    for species_id in range(len(species_ids)):
        species = species_by_id[species_id]
        data = learnsets.get(species, {})
        level_moves = data.get("LevelMoves", [])
        encoded_level = []
        for entry in level_moves:
            move = entry.get("Move", "").strip()
            require(move in move_ids, f"{species} has unknown level move {move}")
            encoded_level.append((int(entry["Level"]) << 16) | move_ids[move])
        encoded_level.append(0x0000FFFF)
        encoded_level.extend(
            [0x0000FFFF] * (level_width - len(encoded_level))
        )
        level_values.extend(encoded_level)

        encoded_egg = []
        for move in data.get("EggMoves", []):
            require(move in move_ids, f"{species} has unknown egg move {move}")
            encoded_egg.append(move_ids[move])
        encoded_egg.append(0xFFFF)
        encoded_egg.extend([0xFFFF] * (egg_width - len(encoded_egg)))
        egg_values.extend(encoded_egg)

        machine_compatible = {
            move.strip()
            for move in data.get("MachineMoves", [])
        }
        machine_compatible.update(
            entry["Move"]
            for entry in level_moves
            if "Move" in entry
        )
        machine_row = [0] * machine_words
        for index, move in enumerate(machine_moves):
            if move in machine_compatible:
                machine_row[index // 32] |= 1 << (index % 32)
        machine_values.extend(machine_row)

        tutor_row = [0] * tutor_words
        for move in data.get("TutorMoves", []):
            index = tutor_indices.get(move)
            if index is not None:
                tutor_row[index // 32] |= 1 << (index % 32)
        tutor_values.extend(tutor_row)

    raw_level = struct.pack(f"<{len(level_values)}I", *level_values)
    unused_mask, flag_offset, move_record_size = authoritative_move_layout()
    require(
        move_data_members
        and all(len(member) == move_record_size for member in move_data_members),
        "final ROM move-data members do not match BattleMove size",
    )
    move_flags = [member[flag_offset] for member in move_data_members]
    config = (REPO / "include/config.h").read_text()
    filter_enabled = re.search(
        r"^\s*#\s*define\s+BLOCK_LEARNING_UNIMPLEMENTED_MOVES(?:\s|$)",
        config,
        re.MULTILINE,
    ) is not None
    level = (
        compact_levelup_payload(
            raw_level,
            level_width,
            move_flags,
            unused_mask,
        )
        if filter_enabled
        else raw_level
    )
    payloads = {
        "level": level,
        "egg": struct.pack(f"<{len(egg_values)}H", *egg_values),
        "machine": struct.pack(f"<{len(machine_values)}I", *machine_values),
        "tutor": (
            struct.pack(f"<{len(tutor_values)}I", *tutor_values)
            + struct.pack(
                f"<{len(tutor_moves)}H",
                *(move_ids[move] for move in tutor_moves),
            )
        ),
    }
    dimensions = {
        "species": len(species_ids),
        "level_width": level_width,
        "egg_width": egg_width,
        "machine_words": machine_words,
        "tutor_words": tutor_words,
        "move_records": len(move_data_members),
    }
    return payloads, dimensions


def serial_compare(first: int, second: int) -> int:
    difference = (first - second) & 0xFFFFFFFF
    require(
        difference != 0x80000000,
        "serial comparison fixture used the excluded half-range",
    )
    if difference == 0:
        return 0
    return 1 if difference < 0x80000000 else -1


def source_contracts() -> None:
    history_source = (
        REPO
        / "src/pokemon_move_history_overlay/pokemon_move_history.c"
    ).read_text()
    history_header = (REPO / "include/pokemon_move_history.h").read_text()
    save_source = (REPO / "src/save.c").read_text()

    for public_api in (
        "PokemonMoveHistory_Init",
        "PokemonMoveHistory_Load",
        "PokemonMoveHistory_Reset",
        "PokemonMoveHistory_CaptureSnapshot",
        "PokemonMoveHistory_Seed",
        "PokemonMoveHistory_RecordMove",
        "PokemonMoveHistory_RecordSnapshot",
        "PokemonMoveHistory_ReplaceMove",
        "PokemonMoveHistory_DeleteMoveSlot",
        "PokemonMoveHistory_Query",
        "PokemonMoveHistory_CommitIfDirty",
        "PokemonMoveHistory_LoadAndSeedParty",
        "PokemonMoveHistory_PrepareSave",
        "PokemonMoveHistory_FinishSave",
        "PokemonMoveHistory_CancelSave",
        "PokemonMoveHistory_WriteSaveNow",
        "PokemonMoveRelearn_BuildCandidates",
    ):
        require(
            re.search(
                rf"\bLONG_CALL\s+{re.escape(public_api)}\s*\(",
                history_header,
            )
            is not None,
            f"{public_api} is not declared as an interworking-safe long call",
        )

    for first, second, expected in (
        (0, 0, 0),
        (5, 4, 1),
        (4, 5, -1),
        (0, 0xFFFFFFFF, 1),
        (1, 0xFFFFFFFE, 1),
        (0xFFFFFFFF, 1, -1),
        (0xFFFFFF00, 0x100, -1),
    ):
        require(
            serial_compare(first, second) == expected,
            f"serial comparison fixture failed for {first:#x}/{second:#x}",
        )
    compare_match = re.search(
        r"static int PokemonMoveHistory_CompareCounters.*?^}",
        history_source,
        re.MULTILINE | re.DOTALL,
    )
    require(compare_match is not None, "counter comparison implementation is missing")
    compare_source = compare_match.group(0)
    require(
        "difference = first - second;" in compare_source
        and "difference < 0x80000000" in compare_source
        and "2^31" in compare_source,
        "counter comparison is not documented modular serial arithmetic",
    )
    require(
        "first == 0xFFFFFFFF" not in compare_source
        and "second == 0xFFFFFFFF" not in compare_source,
        "obsolete single-wrap counter special case remains",
    )

    async_match = re.search(
        r"int Save_WriteFileAsync\(.*?^}",
        save_source,
        re.MULTILINE | re.DOTALL,
    )
    require(async_match is not None, "Save_WriteFileAsync is missing")
    require(
        "pokemonMoveHistorySaveReady" not in async_match.group(0)
        and "WRITE_STATUS_TOTAL_FAIL" not in async_match.group(0),
        "asynchronous primary saving is still gated by move history",
    )
    now_match = re.search(
        r"int PokemonMoveHistory_WriteSaveNowImpl\(.*?^}",
        history_source,
        re.MULTILINE | re.DOTALL,
    )
    require(now_match is not None, "WriteSaveNow implementation is missing")
    require(
        "pokemonMoveHistorySaveReady" not in now_match.group(0)
        and "WRITE_STATUS_TOTAL_FAIL" not in now_match.group(0),
        "synchronous primary saving is still gated by move history",
    )
    require(
        "(void)PokemonMoveHistory_PrepareSave(saveData);" in save_source,
        "primary save initialization does not explicitly ignore sidecar failure",
    )
    require(
        "saveData->pokemonMoveHistoryDirty = TRUE;"
        in history_source
        and "PokemonMoveHistory_LoadForCounter(\n"
            "            saveData,\n"
            "            saveData->saveCounter - 1);"
        in history_source,
        "sidecar failure retry/dirty recovery contract is missing",
    )
    seed_party_match = re.search(
        r"static void PokemonMoveHistory_SeedParty\(.*?^}",
        history_source,
        re.MULTILINE | re.DOTALL,
    )
    require(seed_party_match is not None, "party seeding implementation is missing")
    seed_party_source = seed_party_match.group(0)
    require(
        "Party_GetCount(party)" in seed_party_source
        and "Party_GetMonByIndex(party, i)" in seed_party_source
        and "party->count" not in seed_party_source
        and "party->members[" not in history_source
        and "persisted 0xEC record stride" in seed_party_source,
        "party seeding bypasses the retail 0xEC PartyPokemon accessor",
    )
    for layout_contract in (
        "sizeof(SaveData) == 0x2F320",
        "pokemonMoveHistory) == 0x2F30C",
        "pokemonMoveHistoryDirty) == 0x2F310",
        "pokemonMoveHistoryRevision) == 0x2F314",
        "pokemonMoveHistoryStagedRevision) == 0x2F318",
        "pokemonMoveHistoryStagedSaveCounter)\n        == 0x2F31C",
    ):
        require(
            layout_contract in history_source,
            f"SaveData layout contract lost: {layout_contract}",
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the packaged move-history sidecar integration")
    parser.add_argument(
        "--rom",
        required=True,
        type=Path,
        help="completed, repacked Nintendo DS ROM",
    )
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="capture manifest sealed for exactly this packaged ROM",
    )
    args = parser.parse_args()
    rom_path = args.rom.resolve()
    manifest_path = args.manifest.resolve()
    rom = rom_path.read_bytes()

    arm9_offset = read_u32(rom, 0x20, "ARM9 ROM offset")
    arm9_ram = read_u32(rom, 0x28, "ARM9 RAM address")
    arm9_size = read_u32(rom, 0x2C, "ARM9 size")
    fnt_offset = read_u32(rom, 0x40, "FNT offset")
    fnt_size = read_u32(rom, 0x44, "FNT size")
    fat_offset = read_u32(rom, 0x48, "FAT offset")
    fat_size = read_u32(rom, 0x4C, "FAT size")
    y9_offset = read_u32(rom, 0x50, "y9 offset")
    y9_size = read_u32(rom, 0x54, "y9 size")

    arm9 = checked_slice(rom, arm9_offset, arm9_size, "ARM9")
    fnt = checked_slice(rom, fnt_offset, fnt_size, "FNT")
    fat = checked_slice(rom, fat_offset, fat_size, "FAT")
    table = checked_slice(rom, y9_offset, y9_size, "y9 table")
    require(len(fat) % 8 == 0, "final FAT is not entry-aligned")
    require(len(table) % ROW_SIZE == 0, "final y9 table is not row-aligned")
    require(arm9_ram == MAIN_RAM_START, "final ARM9 has an unexpected RAM base")

    file_constants = (REPO / "include/constants/file.h").read_text()
    for name, expected in (
        ("ARC_MOVE_DATA", 11),
        ("ARC_CODE_ADDONS", 28),
        ("ARC_LEVELUP_LEARNSETS", 33),
        ("ARC_EGG_MOVES", 231),
        ("CODE_ADDON_MACHINE_LEARNSETS", 14),
        ("CODE_ADDON_TUTOR_LEARNSETS", 15),
        ("CODE_ADDON_MOVE_RELEARN_PARENTS", 20),
        ("OVERLAY_OVERWORLD_WILD_RUNTIME", 157),
        ("OVERLAY_OVERWORLD_WILD_RUNTIME_LAYERS", 158),
        ("OVERLAY_OVERWORLD_WILD_RUNTIME_TIMERS", 159),
    ):
        require(
            parse_define(file_constants, name) == expected,
            f"{name} no longer matches its authenticated archive/member index",
        )

    a033_id, packaged_a033 = nitrofs_file(rom, fnt, fat, "a/0/3/3")
    staged_a033 = (REPO / "base/root/a/0/3/3").read_bytes()
    generated_a033 = (REPO / "build/narc/a033.narc").read_bytes()
    require(
        packaged_a033 == staged_a033 == generated_a033,
        "final ROM level-up archive differs from staged/generated a033",
    )
    a033_entries = sorted(path.name for path in (REPO / "build/a033").iterdir())
    require(
        a033_entries == ["LevelupLearnsets.bin"],
        "build/a033 is not the exact one-file level-up packaging source",
    )
    a033_members = narc_members(packaged_a033, "final ROM a/0/3/3")
    require(len(a033_members) == 1, "final ROM level-up archive has multiple members")
    require(
        a033_members[0]
        == (REPO / "build/a033/LevelupLearnsets.bin").read_bytes(),
        "final ROM level-up member differs from generated LevelupLearnsets.bin",
    )

    a028_id, packaged_a028 = nitrofs_file(rom, fnt, fat, "a/0/2/8")
    staged_a028 = (REPO / "base/root/a/0/2/8").read_bytes()
    require(
        packaged_a028 == staged_a028,
        "final ROM a/0/2/8 differs from the staged code-addons archive",
    )
    a028_entries = sorted(path.name for path in (REPO / "build/a028").iterdir())
    require(
        len(a028_entries) == 21
        and all((REPO / "build/a028" / name).is_file() for name in a028_entries),
        "build/a028 is not the exact 21-file sorted packaging source",
    )
    for index, name in ((14, "9_14"), (15, "9_15"), (20, "9_20")):
        require(
            a028_entries[index] == name,
            f"a028 sorted member {index} is {a028_entries[index]!r}, not {name!r}",
        )
    a028_members = narc_members(packaged_a028, "final ROM a/0/2/8")
    require(len(a028_members) == 21, "final ROM a/0/2/8 does not have 21 members")
    for index, staged_name, generated_path in (
        (14, "9_14", REPO / "build/MachineMoveLearnsets.bin"),
        (15, "9_15", REPO / "build/TutorMoveLearnsets.bin"),
        (20, "9_20", REPO / "build/move_relearn/MoveRelearnParents.bin"),
    ):
        staged_member = (REPO / "build/a028" / staged_name).read_bytes()
        generated_member = generated_path.read_bytes()
        require(
            a028_members[index] == staged_member == generated_member,
            f"final a028 member {index} differs from staged/generated {staged_name}",
        )

    a229_id, packaged_a229 = nitrofs_file(rom, fnt, fat, "a/2/2/9")
    staged_a229 = (REPO / "base/root/a/2/2/9").read_bytes()
    generated_a229 = (REPO / "build/narc/a229.narc").read_bytes()
    require(
        packaged_a229 == staged_a229 == generated_a229,
        "final ROM egg archive differs from staged/generated a229",
    )
    a229_entries = sorted(path.name for path in (REPO / "build/a229").iterdir())
    require(
        a229_entries == ["EggLearnsets.bin"],
        "build/a229 is not the exact one-file egg packaging source",
    )
    a229_members = narc_members(packaged_a229, "final ROM a/2/2/9")
    require(len(a229_members) == 1, "final ROM egg archive has multiple members")
    require(
        a229_members[0] == (REPO / "build/a229/EggLearnsets.bin").read_bytes(),
        "final ROM egg member differs from generated EggLearnsets.bin",
    )

    a011_id, packaged_a011 = nitrofs_file(rom, fnt, fat, "a/0/1/1")
    a011_members = narc_members(packaged_a011, "final ROM a/0/1/1")
    expected_learnsets, learnset_dimensions = build_expected_learnset_payloads(
        a011_members,
    )
    require(
        a033_members[0] == expected_learnsets["level"],
        "final ROM level-up member differs from the current-input oracle",
    )
    require(
        a028_members[14] == expected_learnsets["machine"],
        "final ROM machine member differs from the current-input oracle",
    )
    require(
        a028_members[15] == expected_learnsets["tutor"],
        "final ROM tutor member differs from the current-input oracle",
    )
    require(
        a229_members[0] == expected_learnsets["egg"],
        "final ROM egg member differs from the current-input oracle",
    )
    expected_parents, parent_names, parent_mappings, parent_depth = (
        build_expected_parent_payload()
    )
    verify_parent_member_against_current_inputs(
        a028_members[20],
        expected_parents,
        parent_names,
    )
    parent_rows = len(expected_parents) // 2

    rows = [
        struct.unpack_from("<8I", table, offset)
        for offset in range(0, len(table), ROW_SIZE)
    ]
    overlay_ids = [row[0] for row in rows]
    require(
        len(set(overlay_ids)) == len(overlay_ids),
        "final y9 contains duplicate overlay IDs",
    )
    require(
        all(row[0] == index for index, row in enumerate(rows)),
        "final y9 overlay IDs are not dense and ordered",
    )
    require(OVERLAY_ID < len(rows), "final y9 has no overlay 153 row")
    require(
        TASK6_OVERLAY_ID < len(rows),
        "final y9 has no overlay 155 row",
    )
    require(
        RUNTIME_OVERLAY_ID < len(rows),
        "final y9 has no overlay 157 row",
    )
    require(
        RUNTIME_LAYERS_OVERLAY_ID < len(rows),
        "final y9 has no overlay 158 row",
    )
    require(
        RUNTIME_TIMERS_OVERLAY_ID < len(rows),
        "final y9 has no overlay 159 row",
    )

    runtime_row = rows[RUNTIME_OVERLAY_ID]
    runtime_overlay = final_overlay(rom, fat, runtime_row)
    runtime_built = (
        REPO / "build/output_overworld_wild_runtime_overlay.bin"
    ).read_bytes()
    require(
        runtime_overlay == runtime_built,
        "final ROM overlay 157 differs from linked output",
    )
    require(
        runtime_row == (
            RUNTIME_OVERLAY_ID,
            RUNTIME_OVERLAY_BASE,
            len(runtime_overlay),
            0,
            0,
            0,
            RUNTIME_OVERLAY_ID,
            0,
        ),
        "final overlay 157 row has unexpected metadata",
    )
    require(
        0 < len(runtime_overlay)
        and RUNTIME_OVERLAY_BASE + len(runtime_overlay)
            <= RUNTIME_OVERLAY_USABLE_END,
        "overlay 157 exceeds its fixed image/headroom gate",
    )

    runtime_layers_row = rows[RUNTIME_LAYERS_OVERLAY_ID]
    runtime_layers_overlay = final_overlay(rom, fat, runtime_layers_row)
    runtime_layers_built = (
        REPO / "build/output_overworld_wild_runtime_layers_overlay.bin"
    ).read_bytes()
    require(
        runtime_layers_overlay == runtime_layers_built,
        "final ROM overlay 158 differs from linked output",
    )
    require(
        runtime_layers_row == (
            RUNTIME_LAYERS_OVERLAY_ID,
            RUNTIME_LAYERS_OVERLAY_BASE,
            len(runtime_layers_overlay),
            0,
            0,
            0,
            RUNTIME_LAYERS_OVERLAY_ID,
            0,
        ),
        "final overlay 158 row has unexpected metadata",
    )
    require(
        0 < len(runtime_layers_overlay)
        and RUNTIME_LAYERS_OVERLAY_BASE + len(runtime_layers_overlay)
            <= RUNTIME_LAYERS_OVERLAY_USABLE_END,
        "overlay 158 exceeds its fixed image/headroom gate",
    )
    runtime_timers_row = rows[RUNTIME_TIMERS_OVERLAY_ID]
    runtime_timers_overlay = final_overlay(rom, fat, runtime_timers_row)
    runtime_timers_built = (
        REPO / "build/output_overworld_wild_runtime_timers_overlay.bin"
    ).read_bytes()
    require(runtime_timers_overlay == runtime_timers_built,
            "final ROM overlay 159 differs from linked output")
    require(
        runtime_timers_row == (
            RUNTIME_TIMERS_OVERLAY_ID,
            RUNTIME_TIMERS_OVERLAY_BASE,
            len(runtime_timers_overlay),
            0, 0, 0,
            RUNTIME_TIMERS_OVERLAY_ID,
            0,
        ),
        "final overlay 159 row has unexpected metadata",
    )
    require(
        0 < len(runtime_timers_overlay)
        and RUNTIME_TIMERS_OVERLAY_BASE + len(runtime_timers_overlay)
            <= RUNTIME_TIMERS_OVERLAY_USABLE_END,
        "overlay 159 exceeds its fixed image/headroom gate",
    )
    scalar_gate = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts/verify_overworld_wild_overlay_size.py"),
            str(REPO / "build/overworld_wild_runtime_layers_overlay_linked.o"),
            "--binary",
            str(REPO / "build/output_overworld_wild_runtime_layers_overlay.bin"),
            "--overlay", "158",
            "--task5-owner",
            str(REPO / "build/pokemon_move_history_task6_overlay_linked.o"),
            "--lifecycle-consumer",
            str(REPO / "build/pokemon_move_history_task6_overlay_linked.o"),
            "--lifecycle-object",
            str(REPO / "build/pokemon_move_history_task6_overlay/overworld_wild_behavior_support.o"),
            "--scalar-shard",
            str(REPO / "build/overworld_wild_runtime_layers_overlay/owbd_v40_scalar_symbols.o"),
            "--core-owner",
            str(REPO / "build/linked.o"),
            "--catalog-owner",
            str(REPO / "build/overworld_wild_runtime_overlay_linked.o"),
            "--catalog-carrier",
            str(REPO / "build/overworld_wild_runtime_overlay_catalog_symbols.o"),
            "--task8-carrier",
            str(REPO / "build/overworld_wild_runtime_layers_overlay_task8_symbols.o"),
            "--production-object",
            str(REPO / "build/overworld_wild_runtime_overlay/overworld_wild_runtime_layers.o"),
            "--runtime-carrier",
            str(REPO / "build/pokemon_move_history_task6_overlay_task7_runtime_symbols.o"),
            "--spawns-consumer",
            str(REPO / "build/overworld_wild_spawns_overlay_linked.o"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    require(
        scalar_gate.returncode == 0,
        "overlay 155/157/158 complete typed-owner identity gate failed: "
        + (scalar_gate.stderr.strip() or scalar_gate.stdout.strip()),
    )
    timer_gate = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts/verify_overworld_wild_overlay_size.py"),
            str(REPO / "build/overworld_wild_runtime_timers_overlay_linked.o"),
            "--binary",
            str(REPO / "build/output_overworld_wild_runtime_timers_overlay.bin"),
            "--overlay", "159",
            "--layers-owner",
            str(REPO / "build/overworld_wild_runtime_layers_overlay_linked.o"),
            "--task8-carrier",
            str(REPO / "build/overworld_wild_runtime_layers_overlay_task8_symbols.o"),
            "--catalog-owner",
            str(REPO / "build/overworld_wild_runtime_overlay_linked.o"),
            "--catalog-carrier",
            str(REPO / "build/overworld_wild_runtime_overlay_catalog_symbols.o"),
            "--core-owner",
            str(REPO / "build/linked.o"),
            "--timer-carrier",
            str(REPO / "build/overworld_wild_runtime_timers_overlay_timer_symbols.o"),
            "--timer-object",
            str(REPO / "build/overworld_wild_runtime_timers_overlay/overworld_wild_runtime_timers.o"),
            "--production-object",
            str(REPO / "build/overworld_wild_runtime_timers_overlay/overworld_wild_runtime_timers.o"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    require(
        timer_gate.returncode == 0,
        "overlay 158/159 complete typed-owner identity gate failed: "
        + (timer_gate.stderr.strip() or timer_gate.stdout.strip()),
    )
    verify_boot_decoder_freshness(
        manifest_path,
        rom,
        arm9,
        runtime_overlay,
        runtime_layers_overlay,
        runtime_timers_overlay,
        (REPO / "base/arm9.bin").read_bytes(),
    )

    task6_row = rows[TASK6_OVERLAY_ID]
    task6_overlay = final_overlay(rom, fat, task6_row)
    task6_built = (
        REPO / "build/output_pokemon_move_history_task6_overlay.bin"
    ).read_bytes()
    require(
        task6_overlay == task6_built,
        "final ROM overlay 155 differs from linked output",
    )
    require(
        task6_row == (
            TASK6_OVERLAY_ID,
            TASK6_OVERLAY_BASE,
            len(task6_overlay),
            0,
            0,
            0,
            TASK6_OVERLAY_ID,
            0,
        ),
        "final overlay 155 row has unexpected metadata",
    )
    require(
        0 < len(task6_overlay) <= (
            TASK6_OVERLAY_LIMIT - TASK6_OVERLAY_BASE
        ),
        "overlay 155 exceeds its fixed 0x1000 reservation",
    )

    row = rows[OVERLAY_ID]
    overlay = final_overlay(rom, fat, row)
    built = (
        REPO / "build/output_pokemon_move_history_overlay.bin"
    ).read_bytes()
    require(overlay == built,
            "final ROM overlay 153 differs from linked output")
    require(
        row == (
            OVERLAY_ID,
            OVERLAY_BASE,
            len(overlay),
            0,
            0,
            0,
            OVERLAY_ID,
            0,
        ),
        "final overlay 153 row has unexpected metadata",
    )
    require(
        0 < len(overlay)
        and OVERLAY_BASE + len(overlay) + OVERLAY_GUARD <= OVERLAY_LIMIT,
        "overlay 153 exceeds its reservation or upper growth guard",
    )
    resident_ranges = (
        (
            RUNTIME_LAYERS_OVERLAY_ID,
            runtime_layers_row[1],
            runtime_layers_row[1] + runtime_layers_row[2]
                + runtime_layers_row[3],
            RUNTIME_LAYERS_OVERLAY_BASE,
            RUNTIME_LAYERS_OVERLAY_LIMIT,
        ),
        (
            RUNTIME_OVERLAY_ID,
            runtime_row[1],
            runtime_row[1] + runtime_row[2] + runtime_row[3],
            RUNTIME_OVERLAY_BASE,
            RUNTIME_OVERLAY_LIMIT,
        ),
        (
            TASK6_OVERLAY_ID,
            task6_row[1],
            task6_row[1] + task6_row[2] + task6_row[3],
            TASK6_OVERLAY_BASE,
            TASK6_OVERLAY_LIMIT,
        ),
        (
            OVERLAY_ID,
            row[1],
            row[1] + row[2] + row[3],
            OVERLAY_BASE,
            OVERLAY_LIMIT - OVERLAY_GUARD,
        ),
        (
            RUNTIME_TIMERS_OVERLAY_ID,
            runtime_timers_row[1],
            runtime_timers_row[1] + runtime_timers_row[2]
                + runtime_timers_row[3],
            RUNTIME_TIMERS_OVERLAY_BASE,
            RUNTIME_TIMERS_OVERLAY_USABLE_END,
        ),
    )
    require(
        RUNTIME_LAYERS_OVERLAY_LIMIT == RUNTIME_OVERLAY_BASE
        and RUNTIME_OVERLAY_LIMIT == TASK6_OVERLAY_BASE
        and TASK6_OVERLAY_LIMIT == OVERLAY_BASE
        and OVERLAY_BASE < OVERLAY_LIMIT - OVERLAY_GUARD
        and OVERLAY_LIMIT - OVERLAY_GUARD
            < RUNTIME_TIMERS_OVERLAY_BASE
        and RUNTIME_TIMERS_OVERLAY_USABLE_END
            == RUNTIME_TIMERS_OVERLAY_LIMIT - 0x80,
        "resident overlay windows are not the audited contiguous layout",
    )
    for resident_id, resident_start, resident_end, window_start, window_end \
            in resident_ranges:
        require(
            window_start == resident_start < resident_end <= window_end,
            f"resident overlay {resident_id} escapes its owned window",
        )
    for index, first in enumerate(resident_ranges):
        for second in resident_ranges[index + 1:]:
            require(
                not ranges_overlap(first[1], first[2], second[1], second[2]),
                f"resident overlays {first[0]} and {second[0]} overlap",
            )

    linked_symbols = subprocess.check_output(
        [
            "arm-none-eabi-nm",
            str(REPO / "build/pokemon_move_history_overlay_linked.o"),
        ],
        text=True,
    )
    query_impl_match = re.search(
        r"^([0-9a-fA-F]+) T PokemonMoveHistory_QueryImpl$",
        linked_symbols,
        re.MULTILINE,
    )
    require(query_impl_match is not None, "Query implementation symbol is missing")
    query_instruction = struct.unpack_from("<H", overlay, 0x38)[0]
    require(
        query_instruction & 0xF800 == 0xE000,
        "Query entry is not a register-preserving Thumb branch",
    )
    query_delta = query_instruction & 0x7FF
    if query_delta & 0x400:
        query_delta -= 0x800
    query_target = OVERLAY_BASE + 0x38 + 4 + query_delta * 2
    require(
        query_target == (int(query_impl_match.group(1), 16) & ~1),
        "Query entry does not branch to QueryImpl",
    )
    candidate_impl_match = re.search(
        r"^([0-9a-fA-F]+) T PokemonMoveRelearn_BuildCandidatesImpl$",
        linked_symbols,
        re.MULTILINE,
    )
    require(
        candidate_impl_match is not None,
        "move-relearn candidate implementation symbol is missing",
    )
    candidate_instruction = struct.unpack_from("<H", overlay, 0x78)[0]
    require(
        candidate_instruction & 0xF800 == 0xE000,
        "candidate entry is not a register-preserving Thumb branch",
    )
    candidate_delta = candidate_instruction & 0x7FF
    if candidate_delta & 0x400:
        candidate_delta -= 0x800
    candidate_target = OVERLAY_BASE + 0x78 + 4 + candidate_delta * 2
    require(
        candidate_target
        == (int(candidate_impl_match.group(1), 16) & ~1),
        "candidate entry does not branch to BuildCandidatesImpl",
    )

    for other in rows:
        other_size = other[2] + other[3]
        if other[0] in (
                OVERLAY_ID, TASK6_OVERLAY_ID, RUNTIME_OVERLAY_ID,
                RUNTIME_LAYERS_OVERLAY_ID, RUNTIME_TIMERS_OVERLAY_ID
        ) or other_size == 0:
            continue
        other_start = other[1]
        other_end = other_start + other_size
        require(
            MAIN_RAM_START <= other_start < other_end <= MAIN_ARENA_HIGH,
            f"overlay {other[0]} lies outside audited ARM9 main RAM",
        )
        require(
            not ranges_overlap(
                other_start,
                other_end,
                RUNTIME_LAYERS_OVERLAY_BASE,
                OVERLAY_LIMIT,
            ),
            f"overlay {other[0]} overlaps the complete resident reservation",
        )

    save_constants = (REPO / "include/constants/save.h").read_text()
    full_save_size = parse_define(save_constants, "FULL_SAVE_SIZE")
    heap3_size = parse_define(save_constants, "NEW_HEAP3_SIZE")
    field2_heap_size = parse_define(
        save_constants, "NEW_FIELD2_HEAP_SIZE"
    )
    require(
        heap3_size == 0x108000
        and 0x110000 - heap3_size == 0x8000,
        "heap 3 does not explicitly reserve 0x8000 for overlays 158/157/155/153/159",
    )
    require(
        field2_heap_size == 0x19000
        and 0x1C000 - field2_heap_size
            == 0x10B000 - heap3_size == 0x3000,
        "heap 3/field2 reservation reduction is not the exact paired 0x3000",
    )

    def arm9_word(address: int, description: str) -> int:
        return read_u32(arm9, address - arm9_ram, description)

    require(
        arm9_word(0x020F62AC, "patched save heap size")
        == full_save_size,
        "patched save heap size differs from FULL_SAVE_SIZE",
    )
    require(
        arm9_word(0x020F62BC, "patched heap 3 size") == heap3_size,
        "patched heap 3 size differs from NEW_HEAP3_SIZE",
    )
    require(
        read_u16(
            arm9,
            0x0203DFE2 - arm9_ram,
            "patched FieldSystem_New FIELD2 size factor",
        ) == 0x2219
        and read_u16(
            arm9,
            0x0203DFEA - arm9_ram,
            "patched FieldSystem_New FIELD2 size shift",
        ) == 0x0312,
        "FieldSystem_New does not construct NEW_FIELD2_HEAP_SIZE 0x19000",
    )
    require(
        arm9_word(0x020D2C5C, "main arena low literal") == 0x0226EC40,
        "final ARM9 main arena low changed",
    )
    require(
        arm9_word(0x020D2BB0, "main arena high literal")
        == MAIN_ARENA_HIGH,
        "final ARM9 main arena high changed",
    )
    require(
        arm9_word(0x02000930, "DTCM stack base literal") == DTCM_START,
        "final ARM9 DTCM stack base changed",
    )

    stock_overlay_end = max(
        stock[1] + stock[2] + stock[3]
        for stock in rows[:129]
    )
    require(stock_overlay_end == 0x0226EC40,
            "stock overlay arena endpoint changed")
    boot_layout = measure_boot_archive_layout(
        stock_overlay_end,
        full_save_size,
        heap3_size,
        fnt_size,
        fat_size,
    )
    archive_start = boot_layout["archive_start"]
    archive_end = boot_layout["archive_end"]
    cached_fnt_start = (archive_start + 0x1F) & ~0x1F
    cached_fnt_end = cached_fnt_start + fnt_size
    cached_fat_start = cached_fnt_end
    cached_fat_end = cached_fat_start + fat_size
    require(
        cached_fat_end <= archive_end,
        "FNT/FAT caches exceed the SDK archive allocation",
    )
    require(
        archive_end == EXPECTED_ARCHIVE_END
        and boot_layout["archive_margin"] == EXPECTED_ARCHIVE_MARGIN
        and boot_layout["free_margin"] == EXPECTED_FREE_MARGIN,
        "reproduced heap/archive free-margin measurement changed",
    )
    require(
        boot_layout["free_margin"] >= 0,
        f"boot FNT+FAT allocation plus guard reaches 0x{archive_end:08X}",
    )

    arm9_end = arm9_ram + arm9_size
    require(
        not ranges_overlap(
            arm9_ram,
            arm9_end,
            RUNTIME_LAYERS_OVERLAY_BASE,
            OVERLAY_LIMIT,
        ),
        "final ARM9 load image overlaps resident overlays 158/157/155/153/159",
    )
    require(
        OVERLAY_LIMIT <= MAIN_ARENA_HIGH
        and not ranges_overlap(
            DTCM_START,
            DTCM_END,
            RUNTIME_LAYERS_OVERLAY_BASE,
            OVERLAY_LIMIT,
        ),
        "resident overlays 158/157/155/153/159 cross the main arena or DTCM stack boundary",
    )

    require(129 < len(rows), "final y9 has no overlay 129 row")
    row129 = rows[129]
    overlay129 = final_overlay(rom, fat, row129)
    generated_overlay129 = (
        REPO / "base/overlay/overlay_0129.bin"
    ).read_bytes()
    main_overlay = (REPO / "build/output.bin").read_bytes()
    require(
        overlay129 == generated_overlay129,
        "final ROM overlay 129 differs from the generated package",
    )
    require(
        row129 == (
            129,
            0x023D8000,
            len(overlay129),
            0,
            0,
            0,
            129,
            0,
        ),
        "final overlay 129 row has unexpected metadata",
    )
    require(
        len(overlay129) == 0x600 + len(main_overlay)
        and overlay129[0x600:] == main_overlay,
        "final overlay 129 does not contain the linked resident core",
    )
    require(
        len(main_overlay) <= 0x7A00
        and row129[1] + len(overlay129) <= MAIN_ARENA_HIGH,
        "resident overlay 129 exceeds the ARM9 main arena",
    )

    startup_entry = RESIDENT_RUNTIME_STARTUP_ADDRESS
    resident_loader = 0x021102D4
    require(
        thumb_bl_target(
            arm9,
            arm9_ram,
            0x02000CD0,
            "packaged Main startup hook",
        ) == startup_entry,
        "packaged Main startup hook does not reach resident overlay loader",
    )
    require(
        resident_runtime_bootstrap_bytes_match(arm9, arm9_ram),
        "complete resident-runtime bootstrap image differs",
    )
    resident_mov = read_u16(
        arm9,
        resident_loader - arm9_ram,
        "packaged resident-loader region setup",
    )
    resident_literal_load = read_u16(
        arm9,
        resident_loader + 2 - arm9_ram,
        "packaged resident-loader target load",
    )
    require(
        resident_mov == 0x2000
        and resident_literal_load & 0xFF00 == 0x4A00
        and read_u16(
            arm9,
            resident_loader + 4 - arm9_ram,
            "packaged resident-loader tail call",
        ) == 0x4710,
        "packaged resident loader is not mov-r0-zero/ldr-r2/bx-r2",
    )
    resident_literal_address = (
        ((resident_loader + 2 + 4) & ~3)
        + (resident_literal_load & 0xFF) * 4
    )
    require(
        arm9_word(
            resident_literal_address,
            "packaged LoadOverlayNoInit Thumb pointer",
        ) == 0x02007189,
        "packaged resident loader does not tail-call LoadOverlayNoInit",
    )

    rom_ld = (REPO / "rom.ld").read_text()
    for name, api_offset in (
        ("Init", 0x00),
        ("Load", 0x08),
        ("Reset", 0x10),
        ("CaptureSnapshot", 0x18),
        ("Seed", 0x20),
        ("RecordMove", 0x28),
        ("RecordSnapshot", 0x30),
        ("Query", 0x38),
        ("CommitIfDirty", 0x40),
        ("LoadAndSeedParty", 0x48),
        ("PrepareSave", 0x50),
        ("FinishSave", 0x58),
        ("CancelSave", 0x60),
        ("WriteSaveNow", 0x68),
        ("ReplaceMove", 0x80),
        ("DeleteMoveSlot", 0x88),
    ):
        require(
            f"PokemonMoveHistory_{name} = "
            f"0x{OVERLAY_BASE + api_offset:08X} | 1;"
            in rom_ld,
            f"{name} ABI alias is missing or moved",
        )
    require(
        "PokemonMoveRelearn_BuildCandidates = 0x023BE478 | 1;" in rom_ld,
        "move-relearn candidate ABI alias is missing or moved",
    )
    for name, api_offset in (
        ("PokemonMoveHistoryTask6_IsCanonical", 0x00),
        ("PokemonMoveHistoryTask6_DaycareDepositCommit", 0x08),
        ("PokemonMoveHistoryTask6_TradeReplacePartySlot", 0x10),
        ("PokemonMoveHistoryTask6_HatchClearEgg", 0x18),
        ("PokemonMoveHistoryTask6_PCStorageGetAndStage", 0x20),
        ("PokemonMoveHistoryTask6_PCStorageGetAndSeed", 0x20),
        ("PokemonMoveHistoryTask6_PCStoragePlaceAndSeed", 0x28),
        ("SwapPartyPokemonMove", 0x30),
        ("PokemonMoveHistoryTask6_PokewalkerRadioSuccess", 0x80),
        ("PokemonMoveHistoryTask6_PokewalkerRadioSuccessSecond", 0x88),
        ("PokemonMoveHistoryTask6_PokewalkerRecoverAndDiscard", 0x90),
        ("PokemonMoveHistoryTask6_PokewalkerDiagnosticReturn", 0x98),
    ):
        require(
            f"{name} = "
            f"0x{TASK6_OVERLAY_BASE + api_offset:08X} | 1;"
            in rom_ld,
            f"task-6 helper ABI alias is missing or moved: {name}",
        )
    save_trampoline = (
        REPO / "asm/pokemon_move_history_trampoline.s"
    ).read_text()
    require(
        ".word 0x023BE471" in save_trampoline,
        "SaveGameNormal resident trampoline is missing or moved",
    )

    core_symbols = subprocess.check_output(
        ["arm-none-eabi-nm", str(REPO / "build/linked.o")],
        text=True,
    )
    for object_name, symbols in (
        ("resident core", core_symbols),
        ("overlay 153", linked_symbols),
    ):
        require(
            "__PokemonMoveHistory_" not in symbols
            and "__PokemonMoveRelearn_" not in symbols,
            f"{object_name} contains an unsafe generated interworking veneer",
        )

    save_relocations = subprocess.check_output(
        ["arm-none-eabi-objdump", "-r", str(REPO / "build/save.o")],
        text=True,
    )
    require(
        re.search(r"R_ARM_THM_CALL\s+PokemonMoveHistory_", save_relocations)
        is None,
        "save.o still emits a short Thumb call to overlay 153",
    )
    for called_api in (
        "Init",
        "Reset",
        "LoadAndSeedParty",
        "PrepareSave",
        "FinishSave",
        "CancelSave",
    ):
        require(
            re.search(
                rf"R_ARM_ABS32\s+PokemonMoveHistory_{called_api}\b",
                save_relocations,
            )
            is not None,
            f"save.o does not use a typed long call for {called_api}",
        )

    candidate_relocations = subprocess.check_output(
        [
            "arm-none-eabi-objdump",
            "-r",
            str(
                REPO
                / "build/pokemon_move_history_overlay/pokemon_move_relearn.o"
            ),
        ],
        text=True,
    )
    require(
        re.search(
            r"R_ARM_THM_CALL\s+PokemonMoveHistory_QueryReadOnlyImpl\b",
            candidate_relocations,
        )
        is not None,
        "candidate builder does not call the read-only query within overlay 153",
    )
    require(
        re.search(
            r"\bPokemonMoveHistory_Query\b",
            candidate_relocations,
        )
        is None
        and "__PokemonMoveHistory_Query_from_thumb" not in candidate_relocations,
        "candidate builder still relocates through the public Query alias",
    )

    history_relocations = subprocess.check_output(
        [
            "arm-none-eabi-objdump",
            "-r",
            str(
                REPO
                / "build/pokemon_move_history_overlay/pokemon_move_history.o"
            ),
        ],
        text=True,
    )
    require(
        re.search(
            r"R_ARM_ABS32\s+Party_GetMonByIndex\b",
            history_relocations,
        )
        is not None,
        "party seeding binary does not use a typed long call to "
        "Party_GetMonByIndex",
    )
    require(
        re.search(
            r"R_ARM_ABS32\s+Party_GetCount\b",
            history_relocations,
        )
        is not None
        and re.search(
            r"R_ARM_THM_CALL\s+Party_GetCount\b",
            history_relocations,
        )
        is None,
        "party seeding binary does not use a typed long call to Party_GetCount",
    )
    require(
        re.search(
            r"R_ARM_THM_CALL\s+Party_GetMonByIndex\b",
            history_relocations,
        )
        is None,
        "party seeding binary emits an unsafe short Thumb call to "
        "Party_GetMonByIndex",
    )

    overlay_disassembly = subprocess.check_output(
        [
            "arm-none-eabi-objdump",
            "-d",
            str(REPO / "build/pokemon_move_history_overlay_linked.o"),
        ],
        text=True,
    )
    seed_party_disassembly = re.search(
        r"^[0-9a-fA-F]+ <PokemonMoveHistory_SeedParty>:\n"
        r"(.*?)(?=^\n[0-9a-fA-F]+ <|\Z)",
        overlay_disassembly,
        re.MULTILINE | re.DOTALL,
    )
    require(
        seed_party_disassembly is not None,
        "final linked party-seeding function is missing",
    )
    seed_party_body = seed_party_disassembly.group(1)
    require(
        ".word\t0x02074641" in seed_party_body
        and ".word\t0x02074645" in seed_party_body,
        "final linked party seeding does not target both canonical accessors",
    )
    require(
        all(
            stride not in seed_party_body
            for stride in (
                "#236",
                "#240",
                "#0xec",
                "#0xf0",
                "0x000000ec",
                "0x000000f0",
            )
        ),
        "final linked party seeding contains direct PartyPokemon stride arithmetic",
    )

    thumb_api_targets = {
        OVERLAY_BASE + offset
        for offset in range(0, 0x90, 8)
    }
    for object_path in (
        REPO / "build/linked.o",
        REPO / "build/pokemon_move_history_overlay_linked.o",
    ):
        disassembly = subprocess.check_output(
            ["arm-none-eabi-objdump", "-d", str(object_path)],
            text=True,
        )
        for line in disassembly.splitlines():
            arm_instruction = re.match(
                r"^\s*([0-9a-fA-F]+):\s+([0-9a-fA-F]{8})\s+"
                r"([a-zA-Z.][a-zA-Z0-9.]*)\b",
                line,
            )
            if arm_instruction is None:
                continue
            address = int(arm_instruction.group(1), 16)
            instruction = int(arm_instruction.group(2), 16)
            mnemonic = arm_instruction.group(3)
            # ARM B/BL (including all condition forms) have bits 27:25 = 101.
            # cond=0xF is BLX-immediate and intentionally targets the state
            # encoded by H, so it is not the unsafe ARM-to-even-Thumb case.
            if (
                mnemonic == ".word"
                or (instruction >> 25) & 0x7 != 0x5
                or instruction >> 28 == 0xF
            ):
                continue
            displacement = instruction & 0xFFFFFF
            if displacement & 0x800000:
                displacement -= 0x1000000
            target = (address + 8 + (displacement << 2)) & 0xFFFFFFFF
            require(
                target not in thumb_api_targets,
                f"{object_path.name} has an ARM branch to even Thumb API "
                f"0x{target:08X}",
            )
    match = re.search(
        r"^([0-9a-fA-F]+) T SaveGameNormal$",
        core_symbols,
        re.MULTILINE,
    )
    require(match is not None, "SaveGameNormal hook symbol was not generated")
    save_game_normal = int(match.group(1), 16) | 1
    hook_offset = 0x020273F0 - arm9_ram
    require(
        arm9[hook_offset:hook_offset + 4] == bytes.fromhex("00 49 08 47"),
        "SaveGameNormal hook is not the expected Thumb literal trampoline",
    )
    require(
        struct.unpack_from("<I", arm9, hook_offset + 4)[0]
        == save_game_normal,
        "SaveGameNormal hook does not target the resident trampoline",
    )

    source_contracts()
    print(
        "move-history post-package gate: "
        f"rom={rom_path} "
        f"fnt=0x{fnt_size:X} fat=0x{fat_size:X} "
        f"a011=file#{a011_id}/0x{len(packaged_a011):X}/"
        f"{learnset_dimensions['move_records']} "
        f"a033=file#{a033_id}/0x{len(packaged_a033):X}/1 "
        f"a028=file#{a028_id}/0x{len(packaged_a028):X}/21 "
        f"a229=file#{a229_id}/0x{len(packaged_a229):X}/1 "
        f"archive=0x{archive_start:08X}..0x{archive_end:08X} "
        f"fnt-cache=0x{cached_fnt_start:08X}.."
        f"0x{cached_fnt_end:08X} "
        f"fat-cache=0x{cached_fat_start:08X}.."
        f"0x{cached_fat_end:08X} "
        f"resident-margin=0x{boot_layout['archive_margin']:X}/"
        f"guard=0x{OVERLAY_GUARD:X}/free=0x{boot_layout['free_margin']:X} "
        f"learnsets={learnset_dimensions['species']}x"
        f"{learnset_dimensions['level_width']}/"
        f"{learnset_dimensions['egg_width']}/"
        f"{learnset_dimensions['machine_words']}/"
        f"{learnset_dimensions['tutor_words']} "
        f"parents={parent_mappings}/{parent_rows}/depth{parent_depth} "
        f"overlay153=0x{OVERLAY_BASE:08X}.."
        f"0x{OVERLAY_BASE + len(overlay):08X} "
        f"overlay157=0x{RUNTIME_OVERLAY_BASE:08X}.."
        f"0x{RUNTIME_OVERLAY_BASE + len(runtime_overlay):08X} "
        f"overlay158=0x{RUNTIME_LAYERS_OVERLAY_BASE:08X}.."
        f"0x{RUNTIME_LAYERS_OVERLAY_BASE + len(runtime_layers_overlay):08X} "
        f"overlay159=0x{RUNTIME_TIMERS_OVERLAY_BASE:08X}.."
        f"0x{RUNTIME_TIMERS_OVERLAY_BASE + len(runtime_timers_overlay):08X} "
        f"overlay129=0x{len(overlay129):X}/0x8000"
    )


if __name__ == "__main__":
    main()
