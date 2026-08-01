#!/usr/bin/env python3
"""Static verifier and exhaustive data oracle for the overworld learnset cache."""

from __future__ import annotations

import argparse
import importlib.util
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


ARM9_BASE = 0x02000000
HOOK_ADDR = 0x02071FC8
SLOT_ADDR = 0x02071FD8
NEXT_FUNCTION_ADDR = 0x02071FDC
STOCK_HOOK_BYTES = bytes.fromhex(
    "10 b5 14 1c 00 f0 32 fb 02 1c 20 1c 21 21 95 f7 97 fa 10 bd"
)
STOCK_NEXT_FUNCTION_PREFIX = bytes.fromhex(
    "70 b5 82 b0 06 1c 19 48 14 1c 0d 1c 84 42 21 d1"
)
PERSONAL_PARAM_HOOK_ADDR = 0x0206FBE8
PERSONAL_PARAM_SLOT_ADDR = 0x0206FBEC
PERSONAL_PARAM_FALLBACK_ADDR = 0x0206FBF0
PERSONAL_PARAM_NEXT_ADDR = 0x0206FC08
STOCK_PERSONAL_PARAM_BYTES = bytes.fromhex(
    "38 b5 0c 1c 00 21 ff f7 4d ff 05 1c 21 1c ff f7 "
    "57 ff 04 1c 28 1c ff f7 d7 ff 20 1c 38 bd 00 00"
)
STOCK_PERSONAL_PARAM_NEXT_PREFIX = bytes.fromhex(
    "f8 b5 05 1c 08 1c 11 1c 1e 1c 02 f0 0f fd 07 1c"
)
GET_PERSONAL_ATTR_ADDR = 0x0206FAA8
GET_PERSONAL_ATTR_END = 0x0206FBB0
GET_PERSONAL_ATTR_NEXT_END = 0x0206FBC4
GET_PERSONAL_ATTR_PATCHES = {
    0x0206FB80: (bytes.fromhex("a5 7d"), bytes.fromhex("e5 8a")),
    0x0206FB84: (bytes.fromhex("e5 7d"), bytes.fromhex("65 8b")),
}
STOCK_GET_PERSONAL_ATTR_NEXT_BYTES = bytes.fromhex(
    "10 b5 04 1c 01 d1 b5 f7 b1 fc 20 1c aa f7 a6 ff 10 bd 00 00"
)
FORM_LOAD_HOOK_ADDR = 0x020725B4
FORM_LOAD_NEXT_ADDR = 0x020725C8
STOCK_FORM_LOAD_BYTES = bytes.fromhex(
    "10 b5 14 1c 00 f0 3c f8 02 1c 20 1c 02 21 94 f7 a1 ff 10 bd"
)
STOCK_FORM_LOAD_NEXT_PREFIX = bytes.fromhex(
    "02 4b 02 1c 08 1c 22 21 18 47 c0 46 09 75 00 02"
)
ROW_COUNT = 1393
ROW_SIZE = 164
MEMBER_SIZE = ROW_COUNT * ROW_SIZE
PERSONAL_ROW_COUNT = 1393
PERSONAL_ROW_SIZE = 44
PERSONAL_ATTR_COUNT = 33
PERSONAL_FORM_WIDTH = 32
PERSONAL_NEEDS_REVERSION = 0x8000
MIN_OVERLAY_150_MARGIN = 198
OVERLAY_150_BASELINE_SIZE = 3526
MAX_OVERLAY_150_DELTA = 372
OVERLAY_150_FIXED_RESOLVER_MIN_MARGIN = 2
OVERLAY_150_BASE = 0x023C3000
OVERLAY_150_CAPACITY = 0x1000
OVERLAY_150_OVERLAP_RESOLVER_OFFSET = 0xEC
ARM9_OVERLAY_TABLE_ROW_SIZE = 0x20
OVERLAY_PACKAGING = {
    149: {
        "output": "output_overworld_wild_spawns_overlay.bin",
        "linked": "overworld_wild_spawns_overlay_linked.o",
        "load_address": 0x023CD000,
        "capacity": 0xB000,
    },
    150: {
        "output": "output_overworld_wild_behavior_data_overlay.bin",
        "linked": "overworld_wild_behavior_data_overlay_linked.o",
        "load_address": 0x023C3000,
        "capacity": 0x1000,
    },
    151: {
        "output": "output_overworld_wild_helper_overlay.bin",
        "linked": "overworld_wild_helper_overlay_linked.o",
        "load_address": 0x023C4000,
        "capacity": 0x4000,
    },
}
CACHE_NARC_PACKAGING = (
    (
        "ARC11 move data",
        "build/narc/a011.narc",
        "base/root/a/0/1/1",
        "narcs.mk",
        (
            "MOVEDATA_NARC := $(BUILD_NARC)/a011.narc",
            "MOVEDATA_TARGET := $(FILESYS)/a/0/1/1",
        ),
        "cp $(MOVEDATA_NARC) $(MOVEDATA_TARGET)",
    ),
    (
        "ARC2 personal",
        "build/narc/mondata.narc",
        "base/root/a/0/0/2",
        "narcs.mk",
        (
            "MONDATA_NARC := $(BUILD_NARC)/mondata.narc",
            "MONDATA_TARGET := $(FILESYS)/a/0/0/2",
        ),
        "cp $(MONDATA_NARC) $(MONDATA_TARGET)",
    ),
    (
        "ARC33 level-up learnset",
        "build/narc/a033.narc",
        "base/root/a/0/3/3",
        "data/codetables.mk",
        (
            "LEVELUPLEARNSET_NARC := $(BUILD_NARC)/a033.narc",
            "LEVELUPLEARNSET_TARGET := $(FILESYS)/a/0/3/3",
        ),
        "cp $(LEVELUPLEARNSET_NARC) $(LEVELUPLEARNSET_TARGET)",
    ),
)


def fail(message: str) -> None:
    raise SystemExit(f"learnset cache verification failed: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def read_at(image: bytes, address: int, size: int) -> bytes:
    offset = address - ARM9_BASE
    require(offset >= 0 and offset + size <= len(image), f"ARM9 range 0x{address:08X} missing")
    return image[offset : offset + size]


def symbols(path: Path) -> dict[str, tuple[int, int]]:
    result = subprocess.run(
        ["arm-none-eabi-nm", "-S", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    parsed: dict[str, tuple[int, int]] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 4:
            parsed[parts[3]] = (int(parts[0], 16), int(parts[1], 16))
        elif len(parts) == 3:
            parsed[parts[2]] = (int(parts[0], 16), 0)
    return parsed


def section_size(path: Path, section_name: str) -> int:
    result = subprocess.run(
        ["arm-none-eabi-objdump", "-h", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == section_name:
            return int(parts[2], 16)
    return 0


def has_authenticated_fixed_overlap_resolver(
    overlay: bytes,
    syms: dict[str, tuple[int, int]],
) -> bool:
    """Recognize the one ov150 ABI allowed to consume reserved growth space."""
    base = OVERLAY_150_BASE
    fixed_symbols = {
        "gOverworldWildBehaviorDataOverlayHeader": (base, 0x58),
        "gOverworldWildPersonalCacheOverlayEntry": (base + 0xE0, 12),
        "gOverworldWildOverlapResolverEntry": (
            base + OVERLAY_150_OVERLAP_RESOLVER_OFFSET,
            4,
        ),
    }
    if any(syms.get(name) != expected for name, expected in fixed_symbols.items()):
        return False
    for name, address in (
        ("OverworldWildBehavior_ValidateOverlay", base + 0x58),
        ("OverworldWildBehavior_CleanupOverlay", base + 0x100),
    ):
        symbol = syms.get(name)
        if symbol is None or symbol[0] != address or symbol[1] <= 0:
            return False

    target = syms.get("OverworldWildBehavior_TryResolveOverlap")
    if target is None or target[1] <= 0:
        return False
    target_address = target[0] & ~1
    if not (base + 0x100 <= target_address
            and target_address + target[1] <= base + len(overlay)):
        return False
    if len(overlay) < OVERLAY_150_OVERLAP_RESOLVER_OFFSET + 4:
        return False
    if struct.unpack_from(
        "<I", overlay, OVERLAY_150_OVERLAP_RESOLVER_OFFSET
    )[0] != (target_address | 1):
        return False

    if len(overlay) < 0xEC:
        return False
    if struct.unpack_from("<IHH", overlay, 0) != (0x4F57424F, 2, 8):
        return False
    if struct.unpack_from("<IHH", overlay, 0xE0) != (0x4F575043, 1, 12):
        return False
    return True


def verify_overlay_150_capacity_contract(
    footprint: int,
    linked_size: int,
    overlay: bytes,
    syms: dict[str, tuple[int, int]],
) -> None:
    """Enforce the legacy reserve unless the fixed resolver ABI is authenticated."""
    require(
        footprint <= OVERLAY_150_CAPACITY,
        f"overlay 150 RAM footprint is 0x{footprint:X}; capacity is "
        f"0x{OVERLAY_150_CAPACITY:X}",
    )
    fixed_resolver = has_authenticated_fixed_overlap_resolver(overlay, syms)
    min_margin = (
        OVERLAY_150_FIXED_RESOLVER_MIN_MARGIN
        if fixed_resolver
        else MIN_OVERLAY_150_MARGIN
    )
    max_linked_size = (
        OVERLAY_150_CAPACITY - OVERLAY_150_FIXED_RESOLVER_MIN_MARGIN
        if fixed_resolver
        else OVERLAY_150_BASELINE_SIZE + MAX_OVERLAY_150_DELTA
    )
    contract = (
        "authenticated fixed overlap-resolver ABI"
        if fixed_resolver
        else "legacy expansion reserve"
    )
    margin = OVERLAY_150_CAPACITY - footprint
    require(
        margin >= min_margin,
        f"overlay 150 has only 0x{margin:X} bytes free; {contract} requires "
        f"0x{min_margin:X}",
    )
    require(
        linked_size <= max_linked_size,
        f"overlay 150 linked output is 0x{linked_size:X}; {contract} allows "
        f"at most 0x{max_linked_size:X}",
    )


def linked_function_bytes(
    binary: bytes,
    image_base: int,
    syms: dict[str, tuple[int, int]],
    name: str,
) -> tuple[int, bytes]:
    address, size = syms[name]
    address &= ~1
    offset = address - image_base
    require(size > 0, f"{name} has no linked size")
    require(
        0 <= offset <= len(binary) - size,
        f"{name} lies outside its linked binary",
    )
    return address, binary[offset : offset + size]


def thumb_indirect_call_literals(
    binary: bytes,
    base: int,
    function_address: int,
    function_size: int,
) -> list[tuple[int, int]]:
    """Return (LDR address, literal target) for `ldr r3; bl veneer` calls."""
    calls = []
    start = function_address - base
    end = start + function_size
    require(0 <= start <= end <= len(binary), "Thumb function is outside binary")
    for offset in range(start, end - 5, 2):
        instruction = struct.unpack_from("<H", binary, offset)[0]
        if instruction & 0xF800 != 0x4800 or (instruction >> 8) & 7 != 3:
            continue
        bl_high, bl_low = struct.unpack_from("<HH", binary, offset + 2)
        if bl_high & 0xF800 != 0xF000 or bl_low & 0xF800 != 0xF800:
            continue
        instruction_address = base + offset
        calls.append(
            (instruction_address, thumb_literal(binary, base, instruction_address))
        )
    return calls


def thumb_bl_target(binary: bytes, base: int, instruction_address: int) -> int:
    """Decode a Thumb-1 two-halfword BL and return its even code target."""
    offset = instruction_address - base
    require(0 <= offset <= len(binary) - 4, "Thumb BL is outside binary")
    high, low = struct.unpack_from("<HH", binary, offset)
    require(
        high & 0xF800 == 0xF000 and low & 0xF800 == 0xF800,
        f"0x{instruction_address:08X} is not Thumb BL",
    )
    signed_high = high & 0x7FF
    if signed_high & 0x400:
        signed_high -= 0x800
    return instruction_address + 4 + (signed_high << 12) + ((low & 0x7FF) << 1)


def thumb_direct_calls(
    binary: bytes,
    base: int,
    function_address: int,
    function_size: int,
) -> list[tuple[int, int]]:
    """Return every decoded (BL address, even target) in a linked Thumb range."""
    calls = []
    start = function_address - base
    end = start + function_size
    require(0 <= start <= end <= len(binary), "Thumb function is outside binary")
    for offset in range(start, end - 3, 2):
        high, low = struct.unpack_from("<HH", binary, offset)
        if high & 0xF800 == 0xF000 and low & 0xF800 == 0xF800:
            address = base + offset
            calls.append((address, thumb_bl_target(binary, base, address)))
    return calls


def thumb_literal_store_addresses(
    binary: bytes,
    base: int,
    function_address: int,
    function_size: int,
    stored_value: int,
    destination: int,
) -> list[int]:
    """Find linked `ldr value; ldr destination; str value, [destination]` stores."""
    start = function_address - base
    end = start + function_size
    require(0 <= start <= end <= len(binary), "Thumb function is outside binary")
    loads: list[tuple[int, int, int]] = []
    stores: list[tuple[int, int, int]] = []
    for offset in range(start, end - 1, 2):
        instruction = struct.unpack_from("<H", binary, offset)[0]
        address = base + offset
        if instruction & 0xF800 == 0x4800:
            loads.append(
                (address, (instruction >> 8) & 7, thumb_literal(binary, base, address))
            )
        elif instruction & 0xF800 == 0x6000 and (instruction >> 6) & 0x1F == 0:
            stores.append((address, instruction & 7, (instruction >> 3) & 7))

    matches = []
    for store_address, source_register, base_register in stores:
        value_loads = [
            address
            for address, register, value in loads
            if register == source_register
            and value == stored_value
            and 0 < store_address - address <= 16
        ]
        destination_loads = [
            address
            for address, register, value in loads
            if register == base_register
            and value == destination
            and 0 < store_address - address <= 16
        ]
        if value_loads and destination_loads:
            matches.append(store_address)
    return matches


def thumb_conditional_branch_target(instruction: int, address: int) -> int:
    require(instruction & 0xF000 == 0xD000, f"0x{address:08X} is not a Thumb conditional branch")
    displacement = instruction & 0xFF
    if displacement & 0x80:
        displacement -= 0x100
    return address + 4 + (displacement << 1)


def decode_cleanup_dtor_provenance(
    binary: bytes,
    base: int,
    function_address: int,
    function_size: int,
    state_address: int,
) -> list[tuple[int, int]]:
    """Return (state handle byte offset, call LDR address) for guarded NARC_dtors."""
    start = function_address - base
    end = start + function_size
    require(0 <= start <= end <= len(binary), "cleanup function is outside binary")
    base_loads = []
    handle_loads = []
    for offset in range(start, end - 1, 2):
        instruction = struct.unpack_from("<H", binary, offset)[0]
        address = base + offset
        if instruction & 0xF800 == 0x4800 and (instruction >> 8) & 7 == 4:
            if thumb_literal(binary, base, address) == state_address:
                base_loads.append(address)
        if instruction & 0xF800 == 0x6800:
            target_register = instruction & 7
            source_register = (instruction >> 3) & 7
            if target_register == 0 and source_register == 4:
                handle_loads.append((address, ((instruction >> 6) & 0x1F) * 4))
    require(len(base_loads) == 1, "cleanup lacks one exact state-base literal load")

    dtor_calls = [
        (address, target)
        for address, target in thumb_indirect_call_literals(
            binary, base, function_address, function_size
        )
        if target == 0x0200770D
    ]
    require(len(dtor_calls) == 2, "cleanup does not contain exactly two NARC_dtor calls")
    result = []
    for call_address, _ in dtor_calls:
        candidates = [item for item in handle_loads if base_loads[0] < item[0] < call_address]
        require(candidates, f"NARC_dtor at 0x{call_address:08X} has no state-handle r0 provenance")
        load_address, handle_offset = candidates[-1]
        require(handle_offset in (0, 52), f"NARC_dtor uses unexpected state handle +{handle_offset}")
        load_offset = load_address - base
        if handle_offset == 0:
            compare = struct.unpack_from("<H", binary, load_offset + 2)[0]
            branch = struct.unpack_from("<H", binary, load_offset + 4)[0]
            require(compare == 0x2801, "personal NARC handle lacks exact sentinel/null cmp #1")
            require(branch & 0xFF00 == 0xD900, "personal NARC handle lacks exact unsigned <=1 guard")
            require(call_address == load_address + 6, "personal NARC guard/call adjacency differs")
            require(
                thumb_conditional_branch_target(branch, load_address + 4) == call_address + 6,
                "personal NARC sentinel/null guard does not skip its complete dtor call",
            )
        else:
            before = struct.unpack_from("<H", binary, load_offset - 2)[0]
            require(before == 0x2300, "learnset NARC handle lacks exact zero register setup")
            require(
                struct.unpack_from("<HH", binary, load_offset + 2) == (0x6023, 0x80A3),
                "learnset cleanup no longer clears personal handle/cache key before dtor",
            )
            compare = struct.unpack_from("<H", binary, load_offset + 6)[0]
            branch = struct.unpack_from("<H", binary, load_offset + 8)[0]
            require(compare == 0x4298, "learnset NARC handle lacks exact r0-vs-zero compare")
            require(branch & 0xFF00 == 0xD000, "learnset NARC handle lacks exact null guard")
            require(call_address == load_address + 10, "learnset NARC guard/call adjacency differs")
            require(
                thumb_conditional_branch_target(branch, load_address + 8) == call_address + 6,
                "learnset NARC null guard does not skip its complete dtor call",
            )
        result.append((handle_offset, call_address))
    require(
        [offset for offset, _ in result] == [0, 52],
        "cleanup does not destroy each distinct personal/learnset handle exactly once",
    )
    return result


def require_exact_lifecycle_events(
    warm_events: list[tuple[str, int]],
    cleanup_events: list[tuple[str, int]],
) -> None:
    """Reject missing, duplicated, or reordered externally visible cache events."""
    require(
        [name for name, _ in warm_events] == ["learnset_reset", "personal_publish"],
        "linked warm lifecycle is not learnset reset -> personal publish",
    )
    require(
        [name for name, _ in cleanup_events]
        == ["personal_reset", "learnset_reset", "personal_dtor", "learnset_dtor"],
        "linked cleanup lifecycle is not both resets -> both exact NARC_dtor calls",
    )
    require(
        all(
            events[index][1] < events[index + 1][1]
            for events in (warm_events, cleanup_events)
            for index in range(len(events) - 1)
        ),
        "linked lifecycle event addresses are not strictly ordered",
    )


def verify_exact_packaged_payload(generated: bytes, packaged: bytes, label: str) -> None:
    require(generated, f"{label} generated payload is empty")
    require(packaged, f"{label} packaged payload is empty")
    require(
        packaged == generated,
        f"{label} packaged payload is absent or stale relative to its generated NARC",
    )


def verify_packaged_cache_narcs(repo: Path) -> None:
    """Tie verified cache/form inputs to the exact files passed to ndstool."""
    makefile = (repo / "Makefile").read_text()
    for fragment in ("BUILD_NARC := $(BUILD)/narc", "BASE := base", "FILESYS := $(BASE)/root"):
        require(fragment in makefile, f"cache NARC Make variable contract differs: {fragment}")

    all_start = makefile.index("all: $(TOOLS) $(OUTPUT) $(OVERLAY_OUTPUTS)")
    all_end = makefile.index("\n\n####################### Restore clean base", all_start)
    all_recipe = makefile[all_start:all_end]
    require(
        all_recipe.index("$(MAKE) move_narc")
        < all_recipe.index("$(NARCHIVE) create $(FILESYS)/a/0/2/8 $(BUILD)/a028/ -nf"),
        "a028 packaging is not after move_narc",
    )
    require(
        all_recipe.index("$(NARCHIVE) create $(FILESYS)/a/0/2/8 $(BUILD)/a028/ -nf")
        < all_recipe.index("scripts/verify_overworld_learnset_cache.py")
        < all_recipe.index("$(NDSTOOL) -c $(BUILDROM)"),
        "mandatory verifier is not after fresh a028 creation and before final ROM packaging",
    )
    move_start = makefile.index("move_narc: $(NARC_FILES)")
    move_end = makefile.index("\n\nDUMP_SCRIPT_LOCATION :=", move_start)
    move_recipe = makefile[move_start:move_end]

    reports = []
    for label, generated_rel, packaged_rel, variables_rel, assignments, copy_rule in CACHE_NARC_PACKAGING:
        variable_source = (repo / variables_rel).read_text()
        for assignment in assignments:
            require(assignment in variable_source, f"{label} Make variable differs: {assignment}")
        require(copy_rule in move_recipe, f"{label} move_narc copy rule differs: {copy_rule}")
        generated_path = repo / generated_rel
        packaged_path = repo / packaged_rel
        require(generated_path.is_file(), f"{label} generated NARC is missing: {generated_path}")
        require(packaged_path.is_file(), f"{label} packaged NARC is missing: {packaged_path}")
        generated = generated_path.read_bytes()
        packaged = packaged_path.read_bytes()
        verify_exact_packaged_payload(generated, packaged, label)
        reports.append(f"{label}=0x{len(generated):X}")

    codetables = (repo / "data/codetables.mk").read_text()
    for fragment in (
        "POKEFORMDATATBL_TARGET := $(BUILD)/a028/9_11",
        "NARC_FILES += $(POKEFORMDATATBL_BIN)",
        "cp $(POKEFORMDATATBL_BIN) $(POKEFORMDATATBL_TARGET)",
        "MOVE_RELEARN_PARENTS_TARGET := $(BUILD)/a028/9_20",
        "NARC_FILES += $(MOVE_RELEARN_PARENTS_BIN)",
        "cp $(MOVE_RELEARN_PARENTS_BIN) $(MOVE_RELEARN_PARENTS_TARGET)",
    ):
        source = move_recipe if fragment.startswith("cp ") else codetables
        require(fragment in source, f"a028 dependency/copy contract differs: {fragment}")
    require(
        "NARCHIVE := $(PYTHON) tools/narcpy.py" in makefile,
        "a028 creator is not the authenticated narcpy path",
    )
    narcpy = (repo / "tools/narcpy.py").read_text()
    require(
        "for entry in sorted(os.listdir(args[2])):" in narcpy,
        "a028 member-index ordering is no longer sorted directory order",
    )
    a028_dir = repo / "build/a028"
    require(a028_dir.is_dir(), "verified a028 source directory is missing")
    entries = sorted(path.name for path in a028_dir.iterdir())
    require(
        all((a028_dir / entry).is_file() for entry in entries),
        "a028 source directory contains a non-file member",
    )
    require(len(entries) == 21, f"a028 source has {len(entries)} members instead of 21")
    require(entries[11] == "9_11", f"a028 member 11 is {entries[11]} instead of 9_11")
    require(entries[20] == "9_20", f"a028 member 20 is {entries[20]} instead of 9_20")
    a028_path = repo / "base/root/a/0/2/8"
    form_path = repo / "build/a028/9_11"
    parent_path = repo / "build/a028/9_20"
    require(a028_path.is_file(), f"fresh packaged a028 is missing: {a028_path}")
    require(form_path.is_file(), f"verified form table is missing: {form_path}")
    require(parent_path.is_file(), f"move-relearn parent table is missing: {parent_path}")
    require(
        parent_path.stat().st_size == ROW_COUNT * 2,
        "move-relearn parent table size differs from one u16 per species/form",
    )
    a028_members = narc_members(a028_path.read_bytes(), "packaged a028")
    require(
        len(a028_members) == len(entries) == 21,
        "packaged a028 member count differs from authenticated sorted source directory",
    )
    verify_exact_packaged_payload(form_path.read_bytes(), a028_members[11], "a028 member 11 (9_11)")
    verify_exact_packaged_payload(
        parent_path.read_bytes(),
        a028_members[20],
        "a028 member 20 (9_20)",
    )
    reports.append(
        f"a028[11]=9_11=0x{len(a028_members[11]):X}; "
        f"a028[20]=9_20=0x{len(a028_members[20]):X}/21 members"
    )
    print("cache packaged NARC gate: " + "; ".join(reports))


def learnset_filter_enabled(repo: Path) -> bool:
    define = re.compile(
        r"^\s*#\s*define\s+BLOCK_LEARNING_UNIMPLEMENTED_MOVES(?:\s|$)"
    )
    return any(
        define.match(line)
        for line in (repo / "include/config.h").read_text().splitlines()
    )


def verify_buildtime_learnset_filter_contract(repo: Path) -> None:
    """Authenticate fresh move-data ordering and the pre-NARC filtering step."""
    codetables = (repo / "data/codetables.mk").read_text()
    target_start = codetables.index("$(LEVELUPLEARNSET_NARC):")
    target_end = codetables.index("\n\nNARC_FILES += $(LEVELUPLEARNSET_NARC)", target_start)
    recipe = codetables[target_start:target_end]
    dependency_line = recipe.splitlines()[0]
    for dependency in (
        "$(LEARNSETS_HEADER)",
        "$(LEVELUPLEARNSET_DEPENDENCIES)",
        "$(BUILD_NARC)/a011.narc",
        "scripts/filter_levelup_learnsets.py",
        "scripts/create_narc_atomic.py",
        "tools/narcpy.py",
        "include/config.h",
        "include/battle.h",
        "armips/include/movemacros.s",
    ):
        require(dependency in dependency_line, f"level-up filter dependency lost: {dependency}")
    filter_command = (
        "$(PYTHON_NO_VENV) scripts/filter_levelup_learnsets.py \\\n"
        "\t\t--learnsets $(LEVELUPLEARNSET_BIN) \\\n"
        "\t\t--move-data-dir $(MOVEDATA_DIR) \\\n"
        "\t\t--constants $(LEARNSETS_HEADER) \\\n"
        "\t\t--config include/config.h \\\n"
        "\t\t--battle-header include/battle.h \\\n"
        "\t\t--move-macros armips/include/movemacros.s"
    )
    require(filter_command in recipe, "level-up prefilter command/inputs differ")
    atomic_command = (
        "$(PYTHON) scripts/create_narc_atomic.py \\\n"
        "\t\t--narcpy tools/narcpy.py \\\n"
        "\t\t--source $(LEVELUPLEARNSET_DIR) \\\n"
        "\t\t--output $@"
    )
    require(atomic_command in recipe, "level-up atomic NARC command/inputs differ")
    require(
        recipe.index("$(OBJCOPY) -O binary")
        < recipe.index(filter_command)
        < recipe.index(atomic_command),
        "level-up filtering is not ordered raw objcopy -> filter -> atomic NARC create",
    )
    require(
        ".DELETE_ON_ERROR: $(LEVELUPLEARNSET_NARC)" in codetables,
        "level-up NARC target lacks delete-on-error protection",
    )

    narcs = (repo / "narcs.mk").read_text()
    move_start = narcs.index("$(MOVEDATA_NARC):")
    move_end = narcs.index("\n\nNARC_FILES += $(MOVEDATA_NARC)", move_start)
    move_recipe = narcs[move_start:move_end]
    for dependency in (
        "armips/data/moves.s",
        "armips/include/macros.s",
        "armips/include/utf-8.txt",
        "armips/include/constants.s",
        "armips/include/config.s",
        "armips/include/movemacros.s",
        "asm/include/debug.inc",
        "asm/include/moves.inc",
        "asm/include/move_effects.inc",
        "scripts/create_narc_atomic.py",
        "tools/narcpy.py",
    ):
        require(dependency in narcs, f"move-data Armips dependency lost: {dependency}")
    require(
        move_recipe.count("$(ARMIPS) armips/data/moves.s") == 1
        and "$(ARMIPS) $^" not in move_recipe
        and "$(PYTHON) scripts/create_narc_atomic.py" in move_recipe
        and "--source $(MOVEDATA_DIR)" in move_recipe
        and "--output $@" in move_recipe,
        "move-data recipe lacks one root Armips invocation or atomic NARC publication",
    )

    script = (repo / "scripts/filter_levelup_learnsets.py").read_text()
    for fragment in (
        "LEVEL_UP_LEARNSET_END = 0xFFFF",
        "def read_move_layout(",
        "macro_offset == header_offset",
        "macro_size == header_size",
        "filtered[write_index] = entry",
        "move_flags[move] & unused_move_mask == 0",
        "dir=args.learnsets.parent.parent",
        "os.replace(temporary, args.learnsets)",
        "temporary.unlink(missing_ok=True)",
    ):
        require(fragment in script, f"level-up prefilter implementation contract lost: {fragment}")
    atomic = (repo / "scripts/create_narc_atomic.py").read_text()
    for fragment in (
        "dir=args.output.parent",
        "subprocess.run(",
        '"create",',
        "os.replace(temporary, args.output)",
        "temporary.unlink(missing_ok=True)",
    ):
        require(fragment in atomic, f"atomic NARC publication contract lost: {fragment}")

    database = subprocess.run(
        ["make", "-qp"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    require(database.returncode in (0, 1), "make -qp failed during graph authentication")
    effective_target = re.search(
        r"^build/narc/a033\.narc:(.*)$",
        database.stdout,
        re.MULTILINE,
    )
    require(effective_target is not None, "effective a033 Make target is missing")
    require(
        "build/narc/a011.narc" in effective_target.group(1).split(),
        "effective a033 Make graph lost its a011 prerequisite",
    )
    effective_move_target = re.search(
        r"^build/narc/a011\.narc:(.*)$",
        database.stdout,
        re.MULTILINE,
    )
    require(effective_move_target is not None, "effective a011 Make target is missing")
    effective_move_prerequisites = set(effective_move_target.group(1).split())
    expected_move_prerequisites = {
        "armips/data/moves.s",
        "armips/include/macros.s",
        "armips/include/utf-8.txt",
        "armips/include/constants.s",
        "armips/include/config.s",
        "armips/include/movemacros.s",
        "asm/include/debug.inc",
        "asm/include/moves.inc",
        "asm/include/move_effects.inc",
        "scripts/create_narc_atomic.py",
        "tools/narcpy.py",
    }
    require(
        effective_move_prerequisites == expected_move_prerequisites,
        "effective a011 prerequisite set differs",
    )
    incremental = subprocess.run(
        ["make", "-W", "armips/include/utf-8.txt", "-n", "build/narc/a033.narc"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    ordered = (
        "tools/armips armips/data/moves.s",
        "--source build/a011",
        "--output build/narc/a011.narc",
        "writing levelup moves",
        "scripts/filter_levelup_learnsets.py",
        "--source build/a033",
        "--output build/narc/a033.narc",
    )
    positions = [incremental.index(fragment) for fragment in ordered]
    require(positions == sorted(positions), "incremental a011 -> a033 rebuild order differs")

    print(
        "learnset build-time filter gate: fresh ARC11 dependency; "
        f"enabled={learnset_filter_enabled(repo)}"
    )


def derive_authoritative_move_layout(repo: Path) -> tuple[int, int, int]:
    """Independently derive mask/offset/size from both C and Armips sources."""
    header = (repo / "include/battle.h").read_text()
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
    require(flag_match is not None and mask_match is not None, "C move flag ABI is missing")
    c_offset = int(flag_match.group(1), 16)
    c_size = int(struct_match.group(2), 16)
    c_mask = int(mask_match.group(1), 16)
    require(c_mask != 0 and c_mask & (c_mask - 1) == 0, "unused-move mask is not one bit")

    macros = (repo / "armips/include/movemacros.s").read_text()
    ordered_fields = (
        "battleeffect", "pss", "basepower", "type", "accuracy", "pp",
        "effectchance", "target", "priority", "flags", "appeal",
        "contesttype", "terminatedata",
    )
    widths = []
    for name in ordered_fields:
        match = re.search(
            rf"^\.macro\s+{name}(?:,|\s|$)(.*?)^\.endmacro\s*$",
            macros,
            re.MULTILINE | re.DOTALL,
        )
        require(match is not None, f"authoritative Armips move macro {name} is missing")
        emissions = re.findall(r"^\s*\.(byte|halfword)\b", match.group(1), re.MULTILINE)
        require(len(emissions) == 1, f"Armips move macro {name} is not one fixed field")
        widths.append(1 if emissions[0] == "byte" else 2)
    armips_offset = sum(widths[: ordered_fields.index("flags")])
    armips_size = sum(widths)
    require((armips_offset, armips_size) == (c_offset, c_size), "C/Armips move layouts differ")
    for flag_name in (
        "FLAG_UNUSABLE_IN_GEN_8",
        "FLAG_UNUSABLE_IN_GEN_9",
        "FLAG_UNUSABLE_UNIMPLEMENTED",
    ):
        require(
            re.search(rf"^{flag_name}\s+equ\s+{c_mask:#04x}$", macros, re.MULTILINE),
            f"Armips {flag_name} mask differs from C",
        )
    return c_mask, c_offset, c_size


def verify_runtime_move_filter_contract(
    repo: Path,
    core_syms: dict[str, tuple[int, int]],
    layout: tuple[int, int, int],
) -> None:
    mask, _, _ = layout
    moves_source = (repo / "src/moves.c").read_text()
    get_start = moves_source.index("u32 LONG_CALL GetMoveData(u16 id, u32 field)\n{")
    get_end = moves_source.index("\n}\n\n/**", get_start)
    get_body = moves_source[get_start:get_end]
    require(
        "case MOVE_DATA_FLAGS:\n        ret = bm->flag;" in get_body,
        "GetMoveData no longer returns the BattleMove flag field",
    )
    filter_start = moves_source.index("BOOL LONG_CALL IsMoveUnimplemented(u16 move)\n{")
    filter_end = moves_source.index("\n}", filter_start)
    require(
        "GetMoveData(move, MOVE_DATA_FLAGS) & FLAG_UNUSED_MOVE"
        in moves_source[filter_start:filter_end],
        "runtime unimplemented-move source contract differs",
    )

    pokemon_header = (repo / "include/pokemon.h").read_text()
    enum_match = re.search(
        r"// BattleMove fields for GetMoveData below\s*enum\s*\{(.*?)\};",
        pokemon_header,
        re.DOTALL,
    )
    require(enum_match is not None, "BattleMove field enum is missing")
    fields = re.findall(r"\bMOVE_DATA_[A-Z0-9_]+\b", enum_match.group(1))
    require(fields.count("MOVE_DATA_FLAGS") == 1, "MOVE_DATA_FLAGS enum entry differs")
    field = fields.index("MOVE_DATA_FLAGS")
    require(mask.bit_count() == 1, "runtime filter mask must contain one bit")
    bit = mask.bit_length() - 1

    core = (repo / "build/output.bin").read_bytes()
    core_base = core_syms["__text_start"][0]
    address, code = linked_function_bytes(
        core,
        core_base,
        core_syms,
        "IsMoveUnimplemented",
    )
    require(len(code) == 14, "linked IsMoveUnimplemented shape differs")
    require(struct.unpack_from("<H", code, 0)[0] == 0xB510, "runtime filter prologue differs")
    require(
        struct.unpack_from("<H", code, 2)[0] == 0x2100 | field,
        "runtime filter requests a different move-data field",
    )
    require(
        thumb_bl_target(code, address, address + 4) == core_syms["GetMoveData"][0],
        "runtime filter no longer calls linked GetMoveData",
    )
    require(
        struct.unpack_from("<HHH", code, 8)
        == ((31 - bit) << 6, 0x0800 | (31 << 6), 0xBD10),
        "linked runtime filter tests a different move flag bit",
    )


def load_production_learnset_filter(repo: Path):
    path = repo / "scripts/filter_levelup_learnsets.py"
    spec = importlib.util.spec_from_file_location("production_learnset_filter", path)
    require(spec is not None and spec.loader is not None, "production filter import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_production_filter_black_box(repo: Path, layout: tuple[int, int, int]) -> None:
    production = load_production_learnset_filter(repo)
    mask, flag_offset, record_size = layout
    require(
        production.read_move_layout(
            repo / "include/battle.h",
            repo / "armips/include/movemacros.s",
        )
        == layout,
        "production and independent move-layout derivations differ",
    )

    def expect_rejection(action, label: str) -> None:
        try:
            action()
        except SystemExit:
            return
        fail(f"production filter negative fixture was accepted: {label}")

    raw_values = [
        0x00010002, 0x00020001, 0x00030002, 0x00040001,
        0x00050003, 0x0000FFFF, 0x00AA0003,
    ]
    raw_values.extend([0x00BB0003] * (41 - len(raw_values)))
    raw = struct.pack("<41I", *raw_values)
    expected_values = list(raw_values)
    expected_values[:4] = [raw_values[1], raw_values[3], raw_values[4], raw_values[5]]
    expected = struct.pack("<41I", *expected_values)
    flags = [0, 0, mask, 0]
    filtered, changed = production.filter_blob(raw, 41, flags, mask)
    require((filtered, changed) == (expected, 1), "production stable compaction fixture differs")
    require(
        production.filter_blob(filtered, 41, flags, mask) == (filtered, 0),
        "production filter is not idempotent",
    )
    sentinel = struct.pack("<41I", 0x0000FFFF, *([0x12340003] * 40))
    require(
        production.filter_blob(sentinel, 41, flags, mask) == (sentinel, 0),
        "production first-sentinel fixture changed",
    )
    missing = list(raw_values)
    missing[0] = 0x00010004
    expect_rejection(
        lambda: production.filter_blob(struct.pack("<41I", *missing), 41, flags, mask),
        "missing referenced move",
    )
    expect_rejection(
        lambda: production.filter_blob(struct.pack("<41I", *([1] * 41)), 41, flags, mask),
        "unterminated row",
    )

    with tempfile.TemporaryDirectory(prefix="learnset-filter-fixtures-") as root_name:
        root = Path(root_name)
        on = root / "on.h"
        off = root / "off.h"
        on.write_text("#define BLOCK_LEARNING_UNIMPLEMENTED_MOVES\n")
        off.write_text("//#define BLOCK_LEARNING_UNIMPLEMENTED_MOVES\n")
        require(production.filter_enabled(on), "production config-on fixture was disabled")
        require(not production.filter_enabled(off), "production config-off fixture was enabled")

        good = root / "good"
        good.mkdir()
        for move, flag in enumerate(flags):
            record = bytearray(record_size)
            record[flag_offset] = flag
            (good / f"move_{move:03d}").write_bytes(record)
        require(
            production.read_move_flags(good, flag_offset, record_size) == flags,
            "production move-row fixture differs",
        )

        malformed = root / "malformed"
        malformed.mkdir()
        (malformed / "garbage").write_bytes(bytes(record_size))
        expect_rejection(
            lambda: production.read_move_flags(malformed, flag_offset, record_size),
            "malformed move filename",
        )
        wrong_size = root / "wrong-size"
        wrong_size.mkdir()
        (wrong_size / "move_000").write_bytes(bytes(record_size - 1))
        expect_rejection(
            lambda: production.read_move_flags(wrong_size, flag_offset, record_size),
            "malformed move record",
        )
        missing_dir = root / "missing"
        missing_dir.mkdir()
        (missing_dir / "move_000").write_bytes(bytes(record_size))
        (missing_dir / "move_002").write_bytes(bytes(record_size))
        expect_rejection(
            lambda: production.read_move_flags(missing_dir, flag_offset, record_size),
            "missing move member",
        )
        duplicate = root / "duplicate"
        duplicate.mkdir()
        (duplicate / "move_001").write_bytes(bytes(record_size))
        (duplicate / "move_0001").write_bytes(bytes(record_size))
        expect_rejection(
            lambda: production.read_move_flags(duplicate, flag_offset, record_size),
            "duplicate numeric move member",
        )

        archive_dir = root / "archive"
        archive_dir.mkdir()
        learnsets = archive_dir / "LevelupLearnsets.bin"
        learnsets.write_bytes(raw)
        command = [
            sys.executable,
            str(repo / "scripts/filter_levelup_learnsets.py"),
            "--learnsets", str(learnsets),
            "--move-data-dir", str(good),
            "--constants", str(repo / "include/constants/generated/learnsets.h"),
            "--config", str(on),
            "--battle-header", str(repo / "include/battle.h"),
            "--move-macros", str(repo / "armips/include/movemacros.s"),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        require(learnsets.read_bytes() == expected, "production CLI config-on output differs")
        require(
            sorted(path.name for path in archive_dir.iterdir()) == [learnsets.name],
            "production filter left a temporary file inside the archived directory",
        )
        learnsets.write_bytes(raw)
        command[command.index(str(on))] = str(off)
        subprocess.run(command, check=True, capture_output=True, text=True)
        require(learnsets.read_bytes() == raw, "production CLI config-off output differs")

        malformed_command = list(command)
        move_dir_index = malformed_command.index("--move-data-dir") + 1
        malformed_command[move_dir_index] = str(wrong_size)
        learnsets.write_bytes(raw)
        malformed_result = subprocess.run(
            malformed_command,
            capture_output=True,
            text=True,
        )
        require(
            malformed_result.returncode != 0,
            "production CLI malformed-input fixture unexpectedly succeeded",
        )
        require(
            learnsets.read_bytes() == raw,
            "production CLI malformed-input failure changed the original learnset",
        )
        require(
            sorted(path.name for path in archive_dir.iterdir()) == [learnsets.name],
            "production CLI malformed-input failure left an archive-directory temp",
        )

    print("production learnset filter black-box fixtures: exact")


def verify_atomic_narc_black_box(repo: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="atomic-narc-fixtures-") as root_name:
        root = Path(root_name)
        source = root / "source"
        source.mkdir()
        (source / "00").write_bytes(b"source")
        output = root / "result.narc"
        prior = b"prior-published-archive"
        complete = b"complete-new-archive"
        partial = b"partial-new-archive"
        output.write_bytes(prior)

        successful_child = root / "successful_child.py"
        successful_child.write_text(
            "import pathlib, sys\n"
            f"pathlib.Path(sys.argv[2]).write_bytes({complete!r})\n"
        )
        failing_child = root / "failing_child.py"
        failing_child.write_text(
            "import pathlib, sys\n"
            f"pathlib.Path(sys.argv[2]).write_bytes({partial!r})\n"
            "raise SystemExit(7)\n"
        )

        command = [
            sys.executable,
            str(repo / "scripts/create_narc_atomic.py"),
            "--narcpy", str(failing_child),
            "--source", str(source),
            "--output", str(output),
        ]
        failed = subprocess.run(command, capture_output=True, text=True)
        require(failed.returncode != 0, "partial-child atomic fixture unexpectedly succeeded")
        require(
            output.read_bytes() == prior,
            "partial-child failure replaced the prior published archive",
        )
        require(
            not any(path.name.startswith(f".{output.name}.") for path in root.iterdir()),
            "partial-child failure left a sibling temporary file",
        )

        successful = list(command)
        successful[successful.index(str(failing_child))] = str(successful_child)
        subprocess.run(successful, check=True, capture_output=True, text=True)
        require(output.read_bytes() == complete, "atomic NARC success output differs")
        require(
            not any(path.name.startswith(f".{output.name}.") for path in root.iterdir()),
            "atomic NARC success left a sibling temporary file",
        )
    print("atomic NARC publication black-box fixtures: exact")


def verify_packaged_overlays(repo: Path) -> None:
    table_path = repo / "base/overarm9.bin"
    require(table_path.is_file(), "mandatory packaged overlay table is missing")
    table = table_path.read_bytes()
    require(
        len(table) % ARM9_OVERLAY_TABLE_ROW_SIZE == 0,
        f"overarm9.bin size 0x{len(table):X} is not 0x20-byte aligned",
    )

    reports = []
    for overlay_id, spec in OVERLAY_PACKAGING.items():
        output_path = repo / "build" / spec["output"]
        linked_path = repo / "build" / spec["linked"]
        packaged_path = repo / "base/overlay" / f"overlay_{overlay_id:04}.bin"
        for path, label in (
            (output_path, "linked output"),
            (linked_path, "linked ELF"),
            (packaged_path, "packaged payload"),
        ):
            require(path.is_file(), f"overlay {overlay_id} {label} is missing: {path}")

        output = output_path.read_bytes()
        packaged = packaged_path.read_bytes()
        require(
            packaged == output,
            f"packaged overlay {overlay_id} differs from {spec['output']} "
            f"(packaged=0x{len(packaged):X}, linked=0x{len(output):X})",
        )
        linked_symbols = symbols(linked_path)
        load_address = linked_symbols["__text_start"][0]
        require(
            load_address == spec["load_address"],
            f"overlay {overlay_id} linked origin is 0x{load_address:08X}",
        )
        bss_size = section_size(linked_path, ".bss")
        expected = (
            overlay_id,
            load_address,
            len(output),
            bss_size,
            0,
            0,
            overlay_id,
            0,
        )
        row_offset = overlay_id * ARM9_OVERLAY_TABLE_ROW_SIZE
        require(
            row_offset + ARM9_OVERLAY_TABLE_ROW_SIZE <= len(table),
            f"overarm9.bin has no indexed row for overlay {overlay_id}",
        )
        actual = struct.unpack_from("<8I", table, row_offset)
        require(
            actual == expected,
            f"overlay {overlay_id} y9 row mismatch: "
            f"actual={[f'0x{value:X}' for value in actual]} "
            f"expected={[f'0x{value:X}' for value in expected]}",
        )
        matching_ids = sum(
            struct.unpack_from("<I", table, offset)[0] == overlay_id
            for offset in range(0, len(table), ARM9_OVERLAY_TABLE_ROW_SIZE)
        )
        require(matching_ids == 1, f"overlay {overlay_id} occurs {matching_ids} times in y9")
        compressed_size = actual[7] & 0x00FFFFFF
        flags = actual[7] >> 24
        require(
            compressed_size == 0 and flags == 0,
            f"overlay {overlay_id} is unexpectedly compressed/flagged",
        )
        require(
            len(packaged) == actual[2],
            f"overlay {overlay_id} file size differs from y9 RAM size",
        )
        require(
            actual[1] + actual[2] + actual[3]
            <= spec["load_address"] + spec["capacity"],
            f"overlay {overlay_id} packaged RAM+BSS exceeds its reserved range",
        )
        if overlay_id == 150:
            verify_overlay_150_capacity_contract(
                actual[2] + actual[3],
                len(packaged),
                output,
                linked_symbols,
            )
        reports.append(
            f"{overlay_id}:load=0x{actual[1]:08X},file/ram=0x{actual[2]:X},"
            f"bss=0x{actual[3]:X},init=0x{actual[4]:X}-0x{actual[5]:X},"
            f"file_id={actual[6]},compressed=0x{compressed_size:X},flags=0x{flags:X}"
        )
    print("learnset packaged overlay gate: " + "; ".join(reports))


def thumb_literal(binary: bytes, base: int, instruction_address: int) -> int:
    offset = instruction_address - base
    instruction = struct.unpack_from("<H", binary, offset)[0]
    require(instruction & 0xF800 == 0x4800, f"0x{instruction_address:08X} is not Thumb LDR literal")
    literal_address = ((instruction_address + 4) & ~3) + (instruction & 0xFF) * 4
    literal_offset = literal_address - base
    require(0 <= literal_offset <= len(binary) - 4, "Thumb literal falls outside overlay")
    return struct.unpack_from("<I", binary, literal_offset)[0]


def expected_hook_bytes(fallback: int) -> bytes:
    # ldr r3, [pc, #4]; ldr r3, [r3]; bx r3; alignment; slot address;
    # unreachable area fill; mutable data slot initialized to odd fallback.
    return (
        bytes.fromhex("01 4b 1b 68 18 47 00 00")
        + struct.pack("<I", SLOT_ADDR)
        + b"\0" * 4
        + struct.pack("<I", fallback | 1)
    )


def verify_personal_stock_envelopes(repo: Path) -> None:
    stock = (repo / "build/arm9.bin").read_bytes()
    for address, expected, label in (
        (PERSONAL_PARAM_HOOK_ADDR, STOCK_PERSONAL_PARAM_BYTES, "PokePersonalParaGet"),
        (FORM_LOAD_HOOK_ADDR, STOCK_FORM_LOAD_BYTES, "LoadMonBaseStats_HandleAlternateForm"),
    ):
        require(
            read_at(stock, address, len(expected)) == expected,
            f"stock {label} envelope 0x{address:08X}..0x{address + len(expected) - 1:08X} differs",
        )
    require(
        len(STOCK_PERSONAL_PARAM_BYTES) == PERSONAL_PARAM_NEXT_ADDR - PERSONAL_PARAM_HOOK_ADDR,
        "stock PokePersonalParaGet envelope length differs",
    )
    require(
        len(STOCK_FORM_LOAD_BYTES) == FORM_LOAD_NEXT_ADDR - FORM_LOAD_HOOK_ADDR,
        "stock alternate-form loader envelope length differs",
    )
    require(
        read_at(stock, PERSONAL_PARAM_NEXT_ADDR, len(STOCK_PERSONAL_PARAM_NEXT_PREFIX))
        == STOCK_PERSONAL_PARAM_NEXT_PREFIX,
        "stock function after PokePersonalParaGet moved",
    )
    require(
        read_at(stock, FORM_LOAD_NEXT_ADDR, len(STOCK_FORM_LOAD_NEXT_PREFIX))
        == STOCK_FORM_LOAD_NEXT_PREFIX,
        "stock function after LoadMonBaseStats_HandleAlternateForm moved",
    )


def expected_personal_param_dispatch_bytes() -> bytes:
    return (
        bytes.fromhex("00 4b 18 47")
        + struct.pack("<I", PERSONAL_PARAM_FALLBACK_ADDR | 1)
        + bytes.fromhex("0a 1c 00 21 e6 e7")
        + b"\0" * 18
    )


def verify_get_personal_attr_bytes(
    stock_function: bytes,
    patched_function: bytes,
    stock_next_function: bytes,
    patched_next_function: bytes,
) -> None:
    expected_size = GET_PERSONAL_ATTR_END - GET_PERSONAL_ATTR_ADDR
    require(len(stock_function) == expected_size, "stock GetPersonalAttr boundary differs")
    require(len(patched_function) == expected_size, "patched GetPersonalAttr boundary differs")
    require(
        stock_next_function == STOCK_GET_PERSONAL_ATTR_NEXT_BYTES,
        "stock function immediately after GetPersonalAttr differs",
    )
    require(
        patched_next_function == STOCK_GET_PERSONAL_ATTR_NEXT_BYTES,
        "GetPersonalAttr patch corrupts the exact following stock function",
    )

    expected = bytearray(stock_function)
    expected_changed_halfwords = []
    for address, (stock_halfword, patched_halfword) in GET_PERSONAL_ATTR_PATCHES.items():
        offset = address - GET_PERSONAL_ATTR_ADDR
        require(
            stock_function[offset : offset + 2] == stock_halfword,
            f"stock GetPersonalAttr halfword at 0x{address:08X} differs",
        )
        expected[offset : offset + 2] = patched_halfword
        expected_changed_halfwords.append(offset)
    require(
        patched_function == bytes(expected),
        "patched GetPersonalAttr differs outside the two intended widened ability loads",
    )
    actual_changed_halfwords = [
        offset
        for offset in range(0, expected_size, 2)
        if stock_function[offset : offset + 2] != patched_function[offset : offset + 2]
    ]
    require(
        actual_changed_halfwords == sorted(expected_changed_halfwords),
        "GetPersonalAttr changed-halfword set is not exactly 0x0206FB80/0x0206FB84",
    )


def verify_get_personal_attr_envelope(stock: bytes, patched: bytes) -> None:
    verify_get_personal_attr_bytes(
        read_at(stock, GET_PERSONAL_ATTR_ADDR, GET_PERSONAL_ATTR_END - GET_PERSONAL_ATTR_ADDR),
        read_at(patched, GET_PERSONAL_ATTR_ADDR, GET_PERSONAL_ATTR_END - GET_PERSONAL_ATTR_ADDR),
        read_at(
            stock,
            GET_PERSONAL_ATTR_END,
            GET_PERSONAL_ATTR_NEXT_END - GET_PERSONAL_ATTR_END,
        ),
        read_at(
            patched,
            GET_PERSONAL_ATTR_END,
            GET_PERSONAL_ATTR_NEXT_END - GET_PERSONAL_ATTR_END,
        ),
    )


def verify_personal_dispatch_sources(repo: Path, patched_arm9: Path | None) -> None:
    hooks = (repo / "hooks").read_text()
    for name, address in (
        ("PokePersonalParaGet", "0206FBE8"),
        ("LoadMonBaseStats_HandleAlternateForm", "020725B4"),
    ):
        require(
            not re.search(rf"^arm9\s+{name}\s+{address}", hooks, re.MULTILINE),
            f"legacy generated hook still owns resident personal envelope {name}",
        )

    armips = (repo / "armips/asm/overworlds.s").read_text()
    required_fragments = (
        ".org 0x0206FBE8\n.area 0x08, 0x00",
        "ldr r3, =pokepersonalparaget_fallback | 1",
        ".org 0x0206FBF0\n.area 0x18, 0x00\npokepersonalparaget_fallback:",
        "mov r2, r1\n    mov r1, #0\n    b 0x0206FBC4",
    )
    for fragment in required_fragments:
        require(fragment in armips, f"missing exact personal dispatcher fragment: {fragment}")
    require(
        ".org 0x020725B4" not in armips
        and "loadmonbasestats_handlealternateform_fallback" not in armips,
        "Armips still patches the stock alternate-form base-stats function",
    )

    rom_ld = (repo / "rom.ld").read_text()
    for fragment in (
        "PokePersonalParaGet = 0x0206FBE8 |1;",
        "PokePersonalParaGet_Fallback = 0x0206FBF0 |1;",
        "GetPersonalAttr = 0x0206FAA8 |1;",
    ):
        require(fragment in rom_ld, f"resident personal symbol contract missing: {fragment}")

    header = (repo / "include/overworld_wild_behavior_data.h").read_text()
    for fragment in (
        "#define OVERWORLD_WILD_PERSONAL_CACHE_OVERLAY_MAGIC 0x4F575043",
        "#define OVERWORLD_WILD_PERSONAL_CACHE_OVERLAY_VERSION 1",
        "#define OVERWORLD_WILD_PERSONAL_PARAM_DISPATCH_SLOT_ADDR 0x0206FBEC",
        "#define OVERWORLD_WILD_PERSONAL_CACHE_ENTRY_ADDR 0x023C30E0",
    ):
        require(fragment in header, f"personal cache public ABI differs: {fragment}")
    require(
        "OVERWORLD_WILD_BASE_STATS_DISPATCH_SLOT_ADDR" not in header
        and "OverworldWildLoadBaseStatsFunc" not in header
        and "gOverworldWildBaseStatsLoader" not in header,
        "removed base-stats cache dispatcher remains in the public ABI",
    )

    expected_param = expected_personal_param_dispatch_bytes()
    require(
        len(expected_param) == PERSONAL_PARAM_NEXT_ADDR - PERSONAL_PARAM_HOOK_ADDR,
        "personal-param dispatcher/fallback does not fill its exact stock envelope",
    )
    require(
        expected_param[4:8] == struct.pack("<I", PERSONAL_PARAM_FALLBACK_ADDR | 1),
        "personal dispatcher slot does not default to the exact odd resident fallback",
    )
    if patched_arm9 is not None:
        stock = (repo / "build/arm9.bin").read_bytes()
        patched = patched_arm9.read_bytes()
        verify_get_personal_attr_envelope(stock, patched)
        require(
            read_at(patched, PERSONAL_PARAM_HOOK_ADDR, len(expected_param)) == expected_param,
            "patched PokePersonalParaGet dispatcher/fallback bytes differ",
        )
        require(
            read_at(patched, FORM_LOAD_HOOK_ADDR, len(STOCK_FORM_LOAD_BYTES))
            == STOCK_FORM_LOAD_BYTES,
            "patched ARM9 modifies the stock alternate-form base-stats function",
        )
        require(
            read_at(patched, PERSONAL_PARAM_NEXT_ADDR, len(STOCK_PERSONAL_PARAM_NEXT_PREFIX))
            == STOCK_PERSONAL_PARAM_NEXT_PREFIX,
            "personal-param patch corrupts the next stock function",
        )
        require(
            read_at(patched, FORM_LOAD_NEXT_ADDR, len(STOCK_FORM_LOAD_NEXT_PREFIX))
            == STOCK_FORM_LOAD_NEXT_PREFIX,
            "base-stats patch corrupts the next stock function",
        )


def verify_personal_overlay_source_contract(repo: Path) -> None:
    source = (repo / "src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c").read_text()
    linker = (repo / "src/overworld_wild_behavior_data_overlay/linker.ld").read_text()
    for fragment in (
        "#define OW_WILD_PERSONAL_ROW_COUNT (MAX_SPECIES_INCLUDING_FORMS + 1)",
        "#define OW_WILD_PERSONAL_ROW_SIZE 44",
        "#define OW_WILD_PERSONAL_ATTR_COUNT (PERSONAL_TM_ARRAY_4 + 1)",
        "#define OW_WILD_PERSONAL_CACHE_INVALID 0",
        "#define OW_WILD_PERSONAL_CACHE_FAILED ((void *)1)",
        "sizeof(OverworldWildPersonalCacheOverlayEntry) == 12",
        "sizeof(OverworldWildPersonalCacheState) == 52",
        "OW_WILD_PERSONAL_ROW_COUNT == 1393",
        "OW_WILD_PERSONAL_ATTR_COUNT == 33",
        "__attribute__((section(\".overworld_wild_personal_cache_entry\"), used)",
        "__attribute__((section(\".overworld_wild_overlap_resolver_entry\"), used)",
    ):
        require(fragment in source, f"personal cache source ABI contract lost: {fragment}")
    state_start = source.index("typedef struct OverworldWildPersonalCacheState {")
    state_end = source.index("} OverworldWildPersonalCacheState;", state_start)
    state = source[state_start:state_end]
    for fragment in (
        "void *narc;",
        "u16 cachedSpeciesPlusOne;",
        "u16 reserved;",
        "u8 row[OW_WILD_PERSONAL_ROW_SIZE];",
    ):
        require(fragment in state, f"personal cache state layout lost: {fragment}")
    require(
        state.index("void *narc;")
        < state.index("u16 cachedSpeciesPlusOne;")
        < state.index("u16 reserved;")
        < state.index("u8 row[OW_WILD_PERSONAL_ROW_SIZE];"),
        "personal cache state field order differs",
    )

    warm_start = source.index("static BOOL OverworldWildBehavior_WarmLevelUpLearnsetCache(void)\n{")
    warm_end = source.index("\n}\n\nstatic BOOL OverworldWildBehavior_LoadPersonalRow", warm_start)
    warm = source[warm_start:warm_end]
    warm_fragments = (
        "gOverworldWildLevelUpLearnsetLoader =\n        LoadLevelUpLearnset_HandleAlternateForm_Fallback;",
        "OverworldWildBehavior_PublishPersonalDispatchers();",
    )
    for fragment in warm_fragments:
        require(fragment in warm, f"personal warm publication contract lost: {fragment}")
    require(
        warm.index(warm_fragments[0]) < warm.index(warm_fragments[1]),
        "personal dispatch publishes before the warm path fails closed",
    )
    require("NARC_ctor(ARC_PERSONAL" not in warm, "ARC_PERSONAL is no longer lazy")

    helper_source = (repo / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c").read_text()
    auth_start = helper_source.index("static BOOL OverworldWildHelper_IsBehaviorOverlayAuthenticated(BOOL warmLearnsets)\n{")
    auth_end = helper_source.index("\n}\n\nstatic BOOL OverworldWildHelper_ValidateOverlay", auth_start)
    auth = helper_source[auth_start:auth_end]
    require(
        auth.index("OVERWORLD_WILD_BEHAVIOR_OVERLAY_VALIDATE()")
        < auth.index("if (warmLearnsets)")
        < auth.index("OVERWORLD_WILD_LEARNSET_CACHE_ENTRY->warm()"),
        "helper can publish personal targets before full overlay authentication",
    )
    publish_start = source.index("static void OverworldWildBehavior_PublishPersonalDispatchers(void)\n{")
    publish_end = source.index("\n}", publish_start)
    require(
        "gOverworldWildPersonalParamLoader = OverworldWildBehavior_GetPersonalParam;"
        in source[publish_start:publish_end],
        "authenticated personal publication target differs",
    )
    reset_start = source.index("static void OverworldWildBehavior_ResetPersonalDispatchers(void)\n{")
    reset_end = source.index("\n}", reset_start)
    require(
        "gOverworldWildPersonalParamLoader = PokePersonalParaGet_Fallback;"
        in source[reset_start:reset_end],
        "personal reset no longer restores the exact resident fallback",
    )
    require(
        "OverworldWildBehavior_LoadBaseStats" not in source
        and "gOverworldWildBaseStatsLoader" not in source,
        "removed base-stats cache target remains in overlay 150",
    )

    load_start = source.index("static BOOL OverworldWildBehavior_LoadPersonalRow(int species)\n{")
    load_end = source.index("\n}\n\nstatic u32 OverworldWildBehavior_GetPersonalParam", load_start)
    load = source[load_start:load_end]
    for fragment in (
        "(u32)species >= OW_WILD_PERSONAL_ROW_COUNT",
        "sOverworldWildPersonalCache.cachedSpeciesPlusOne == species + 1",
        "sOverworldWildPersonalCache.narc == OW_WILD_PERSONAL_CACHE_FAILED",
        "NARC_ctor(ARC_PERSONAL, HEAPID_WORLD)",
        "sOverworldWildPersonalCache.narc = OW_WILD_PERSONAL_CACHE_FAILED;",
        "NARC_GetFileCount(narc) != OW_WILD_PERSONAL_ROW_COUNT",
        "sOverworldWildPersonalCache.narc = narc;",
        "NARC_GetMemberSize(sOverworldWildPersonalCache.narc, species)\n        != OW_WILD_PERSONAL_ROW_SIZE",
        "NARC_ReadWholeMember(",
        "sOverworldWildPersonalCache.cachedSpeciesPlusOne = species + 1;",
    ):
        require(fragment in load, f"personal raw-row loader contract lost: {fragment}")
    require(
        load.index("NARC_ctor(ARC_PERSONAL, HEAPID_WORLD)")
        < load.index("NARC_GetFileCount")
        < load.index("sOverworldWildPersonalCache.narc = narc;")
        < load.index("NARC_GetMemberSize")
        < load.index("NARC_ReadWholeMember")
        < load.index("sOverworldWildPersonalCache.cachedSpeciesPlusOne = species + 1;"),
        "personal raw row is published before count/size/read validation",
    )

    get_start = source.index("static u32 OverworldWildBehavior_GetPersonalParam(int species, int parameter)\n{")
    get_end = source.index("\n}\n\nstatic void OverworldWildBehavior_LoadLevelUpLearnset", get_start)
    get_body = source[get_start:get_end]
    require(
        get_body.index("(u32)parameter >= OW_WILD_PERSONAL_ATTR_COUNT")
        < get_body.index("PokePersonalParaGet_Fallback(species, parameter)")
        < get_body.index("GetPersonalAttr(sOverworldWildPersonalCache.row, parameter)"),
        "personal parameter target does not validate/fallback before stock attribute extraction",
    )
    require(
        "PokeOtherFormMonsNoGet" not in get_body and "ResolveMonForm" not in get_body,
        "reduced personal dispatcher unexpectedly consumes the a028 form table",
    )

    learnset_start = source.index(
        "static void OverworldWildBehavior_LoadLevelUpLearnset(\n"
        "    int species,\n"
        "    int form,\n"
        "    u32 *levelUpLearnset)\n{"
    )
    learnset_end = source.index(
        "\n}\n\nstatic void OverworldWildBehavior_CleanupLevelUpLearnsetCache",
        learnset_start,
    )
    learnset_body = source[learnset_start:learnset_end]
    for fragment in (
        "PokeOtherFormMonsNoGet(species, form)",
        "LoadLevelUpLearnset_HandleAlternateForm_Fallback(",
        "NARC_ReadFromMember(",
        "memcpy(\n        levelUpLearnset,",
    ):
        require(fragment in learnset_body, f"learnset cached-copy contract lost: {fragment}")
    for forbidden in (
        "IsMoveUnimplemented",
        "GetMoveData",
        "BLOCK_LEARNING_UNIMPLEMENTED_MOVES",
        "writeIndex",
        "readIndex",
    ):
        require(
            forbidden not in learnset_body,
            f"caught-frame learnset loader still performs runtime filtering: {forbidden}",
        )

    cleanup_start = source.index("static void OverworldWildBehavior_CleanupLevelUpLearnsetCache(void)\n{")
    cleanup_end = source.index("\n}\n\nBOOL OverworldWildBehavior_ValidateOverlay", cleanup_start)
    cleanup = source[cleanup_start:cleanup_end]
    cleanup_resets = (
        "OverworldWildBehavior_ResetPersonalDispatchers();",
        "gOverworldWildLevelUpLearnsetLoader =\n        LoadLevelUpLearnset_HandleAlternateForm_Fallback;",
    )
    for fragment in cleanup_resets:
        require(fragment in cleanup, f"cleanup target reset lost: {fragment}")
    require(
        "sOverworldWildPersonalCache.narc != NULL\n"
        "        && sOverworldWildPersonalCache.narc != OW_WILD_PERSONAL_CACHE_FAILED"
        in cleanup,
        "cleanup may destruct the personal-cache failure sentinel",
    )
    require(
        max(cleanup.index(fragment) for fragment in cleanup_resets) < cleanup.index("NARC_dtor("),
        "cleanup can destroy a NARC before resetting every resident target",
    )
    clear_start = source.index("static void OverworldWildBehavior_ClearCustomJumpShadowEffectNoop(void)\n{")
    clear_end = source.index("\n}", clear_start)
    require(
        "OverworldWildBehavior_CleanupLevelUpLearnsetCache();" in source[clear_start:clear_end],
        "public cleanup chain no longer reaches personal/learnset cache teardown",
    )

    validate_start = source.index("BOOL OverworldWildBehavior_ValidateOverlay(void)\n{")
    validate_end = source.index("\n}\n\nvoid OverworldWildBehavior_CleanupOverlay", validate_start)
    validate_body = source[validate_start:validate_end]
    require(
        validate_body.index("OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR")
        < validate_body.index("OVERWORLD_WILD_PERSONAL_CACHE_ENTRY_ADDR")
        < validate_body.index("sizeof(OverworldWildPersonalCacheOverlayEntry)"),
        "validator does not authenticate the fixed personal-cache ABI extension",
    )
    exported_cleanup_start = source.index("void OverworldWildBehavior_CleanupOverlay(void)\n{")
    exported_cleanup_end = source.index("\n}", exported_cleanup_start)
    require(
        "OverworldWildBehavior_ClearCustomJumpShadowEffectNoop();"
        in source[exported_cleanup_start:exported_cleanup_end],
        "exported overlay cleanup no longer reaches the cache cleanup chain",
    )

    for fragment in (
        "ASSERT(. == ORIGIN(rom) + 0x58",
        "KEEP(*(.overworld_wild_personal_cache_dispatch))",
        "ASSERT(. <= ORIGIN(rom) + 0xE0",
        ". = ORIGIN(rom) + 0xE0;",
        "KEEP(*(.overworld_wild_personal_cache_entry))",
        "ASSERT(gOverworldWildPersonalCacheOverlayEntry\n                        == ORIGIN(rom) + 0xE0",
        "ASSERT(. == ORIGIN(rom) + 0xEC",
        "KEEP(*(.overworld_wild_overlap_resolver_entry))",
        "ASSERT(gOverworldWildOverlapResolverEntry\n                        == ORIGIN(rom) + 0xEC",
        "ASSERT(. == ORIGIN(rom) + 0xF0",
        ". = ORIGIN(rom) + 0x100;",
        "ASSERT(OverworldWildBehavior_CleanupOverlay\n                        == ORIGIN(rom) + 0x100",
    ):
        require(fragment in linker, f"personal cache linker ABI contract lost: {fragment}")


def verify_hook_sources(repo: Path, fallback: int, patched_arm9: Path | None) -> None:
    hooks = (repo / "hooks").read_text()
    require(
        not re.search(r"^arm9\s+LoadLevelUpLearnset_HandleAlternateForm\s+02071FC8", hooks, re.MULTILINE),
        "legacy generated hook still owns 0x02071FC8",
    )
    armips = (repo / "armips/asm/overworlds.s").read_text()
    required_fragments = (
        ".org 0x02071FC8",
        ".area 0x10, 0x00",
        "ldr r3, =0x02071FD8",
        "ldr r3, [r3]",
        "bx r3",
        ".org 0x02071FD8",
        ".area 0x04, 0x00",
        ".word loadleveluplearnset_handlealternateform_fallback | 1",
    )
    for fragment in required_fragments:
        require(fragment in armips, f"missing exact Armips hook fragment: {fragment}")
    rom_ld = (repo / "rom.ld").read_text()
    require(
        "LoadLevelUpLearnset_HandleAlternateForm = 0x02071FC8 | 1;" in rom_ld,
        "public loader is not linked to the resident trampoline",
    )
    generated = (repo / "armips/include/generated/c_symbols.s").read_text()
    match = re.search(
        r"^loadleveluplearnset_handlealternateform_fallback equ (0x[0-9a-fA-F]+)$",
        generated,
        re.MULTILINE,
    )
    require(match is not None, "generated Armips fallback symbol is missing")
    require(int(match.group(1), 16) == (fallback | 1), "generated Armips fallback pointer differs")

    stock = (repo / "build/arm9.bin").read_bytes()
    require(read_at(stock, HOOK_ADDR, len(STOCK_HOOK_BYTES)) == STOCK_HOOK_BYTES, "stock hook owner bytes differ")
    require(
        read_at(stock, NEXT_FUNCTION_ADDR, len(STOCK_NEXT_FUNCTION_PREFIX))
        == STOCK_NEXT_FUNCTION_PREFIX,
        "next stock function no longer begins exactly at 0x02071FDC",
    )
    expected = expected_hook_bytes(fallback)
    require(len(expected) == NEXT_FUNCTION_ADDR - HOOK_ADDR, "hook does not own exactly 0x14 bytes")
    # Execution leaves through bx r3 before either literal or slot; only the final
    # word is mutated at runtime, so no instruction-cache maintenance is needed.
    require(expected[4:6] == bytes.fromhex("18 47"), "dispatcher has no bx before data")
    if patched_arm9 is not None:
        actual = read_at(patched_arm9.read_bytes(), HOOK_ADDR, len(expected))
        require(actual == expected, "patched ARM9 trampoline/slot bytes differ")
        require(
            read_at(patched_arm9.read_bytes(), NEXT_FUNCTION_ADDR, len(STOCK_NEXT_FUNCTION_PREFIX))
            == STOCK_NEXT_FUNCTION_PREFIX,
            "patched ARM9 overlaps the next stock function",
        )


def verify_overlay_lifecycle(repo: Path, fallback: int, move_filter: int) -> int:
    overlay_path = repo / "build/output_overworld_wild_behavior_data_overlay.bin"
    linked_path = repo / "build/overworld_wild_behavior_data_overlay_linked.o"
    helper_path = repo / "build/output_overworld_wild_helper_overlay.bin"
    helper_linked_path = repo / "build/overworld_wild_helper_overlay_linked.o"
    overlay = overlay_path.read_bytes()
    syms = symbols(linked_path)
    helper = helper_path.read_bytes()
    helper_syms = symbols(helper_linked_path)
    base = 0x023C3000
    footprint = max(len(overlay), syms["__bss_end__"][0] - base)
    verify_overlay_150_capacity_contract(
        footprint,
        len(overlay),
        overlay,
        syms,
    )
    require(len(helper) <= 16384, f"overlay 151 is {len(helper)} bytes")
    require((repo / "build/output.bin").stat().st_size <= 31232, "custom main exceeds cap")
    require((repo / "build/output_overworld_wild_spawns_overlay.bin").stat().st_size <= 45056, "overlay 149 exceeds cap")

    magic, version, entry_size = struct.unpack_from("<IHH", overlay, 0)
    require((magic, version, entry_size) == (0x4F57424F, 2, 8), "behavior ABI header mismatch")
    cache_magic, cache_version, cache_size, loader, warm = struct.unpack_from("<IHHII", overlay, 0x48)
    require(
        (cache_magic, cache_version, cache_size) == (0x4F574C43, 1, 16),
        "learnset cache ABI entry mismatch",
    )
    require(loader & 1 and 0x023C3000 <= (loader & ~1) < 0x023C4000, "cache loader is not odd ov150 code")
    require(warm & 1 and 0x023C3000 <= (warm & ~1) < 0x023C4000, "cache warm is not odd ov150 code")
    require(syms["OverworldWildBehavior_ValidateOverlay"][0] == 0x023C3058, "validator ABI moved")
    require(syms["OverworldWildBehavior_CleanupOverlay"][0] == 0x023C3100, "cleanup ABI moved")
    require(syms["__bss_end__"][0] <= 0x023C4000, "overlay 150 BSS exceeds cap")

    personal_magic, personal_version, personal_size, get_param = struct.unpack_from(
        "<IHHI", overlay, 0xE0
    )
    require(
        (personal_magic, personal_version, personal_size) == (0x4F575043, 1, 12),
        "personal cache ABI entry mismatch",
    )
    require(
        syms["gOverworldWildPersonalCacheOverlayEntry"] == (0x023C30E0, 12),
        "personal cache ABI symbol moved or resized",
    )
    expected_get_param = syms["OverworldWildBehavior_GetPersonalParam"][0] | 1
    require(get_param == expected_get_param, "personal getParam ABI target differs from linked symbol")
    require(
        get_param & 1 and base <= (get_param & ~1) < 0x023C4000,
        "personal cache getParam is not odd overlay-150 code",
    )
    require(
        "OverworldWildBehavior_LoadBaseStats" not in syms,
        "removed base-stats cache target remains in linked overlay 150",
    )
    state_address, state_size = syms["sOverworldWildPersonalCache"]
    require(state_size == 52, f"personal cache linked state is {state_size} bytes")
    require(
        base <= state_address and state_address + state_size <= base + footprint,
        "personal cache linked state lies outside overlay-150 RAM footprint",
    )

    warm_addr, warm_size = syms["OverworldWildBehavior_WarmLevelUpLearnsetCache"]
    warm_bytes = overlay[warm_addr - base : warm_addr - base + warm_size]
    require(struct.pack("<I", SLOT_ADDR) in warm_bytes, "warm does not target resident slot")
    require(struct.pack("<I", fallback | 1) in warm_bytes, "warm lacks exact odd fallback")
    require(struct.pack("<I", loader) in warm_bytes, "warm lacks authenticated ov150 loader")
    for value, label in (
        (0x02007689, "NARC_ctor"),
        (0x020078E9, "NARC_GetFileCount"),
        (0x020077E9, "NARC_GetMemberSize"),
        (MEMBER_SIZE, "member size"),
    ):
        require(struct.pack("<I", value) in warm_bytes, f"warm lacks exact {label}")
    publish_addr, publish_size = syms["OverworldWildBehavior_PublishPersonalDispatchers"]
    publish_bytes = overlay[publish_addr - base : publish_addr - base + publish_size]
    require(
        0x023C3058 <= publish_addr < 0x023C30E0
        and publish_addr + publish_size <= 0x023C30E0,
        "authenticated personal publisher moved outside its fixed pre-ABI region",
    )
    for value, label in (
        (PERSONAL_PARAM_SLOT_ADDR, "personal-param slot"),
        (get_param, "personal-param target"),
    ):
        require(struct.pack("<I", value) in publish_bytes, f"publisher lacks exact {label}")

    reset_addr, reset_size = syms["OverworldWildBehavior_ResetPersonalDispatchers"]
    reset_bytes = overlay[reset_addr - base : reset_addr - base + reset_size]
    for value, label in (
        (PERSONAL_PARAM_SLOT_ADDR, "personal-param slot"),
        (PERSONAL_PARAM_FALLBACK_ADDR | 1, "personal-param fallback"),
    ):
        require(struct.pack("<I", value) in reset_bytes, f"reset lacks exact {label}")

    require(publish_size == 16, "personal publisher linked shape differs")
    require(reset_size == 16, "personal reset linked shape differs")
    require(
        thumb_literal_store_addresses(
            overlay, base, publish_addr, publish_size, get_param, PERSONAL_PARAM_SLOT_ADDR
        )
        == [publish_addr + 4],
        "personal publisher machine code does not perform its one exact target store",
    )
    require(
        thumb_literal_store_addresses(
            overlay,
            base,
            reset_addr,
            reset_size,
            PERSONAL_PARAM_FALLBACK_ADDR | 1,
            PERSONAL_PARAM_SLOT_ADDR,
        )
        == [reset_addr + 4],
        "personal reset machine code does not perform its one exact fallback store",
    )

    learnset_warm_stores = thumb_literal_store_addresses(
        overlay, base, warm_addr, warm_size, fallback | 1, SLOT_ADDR
    )
    publish_calls = [
        address
        for address, target in thumb_direct_calls(overlay, base, warm_addr, warm_size)
        if target == publish_addr
    ]
    require(len(learnset_warm_stores) == 1, "warm has no unique linked learnset reset store")
    require(len(publish_calls) == 1, "warm has no unique linked personal publish call")

    cleanup_cache_name = "OverworldWildBehavior_CleanupLevelUpLearnsetCache"
    if cleanup_cache_name not in syms or syms[cleanup_cache_name][1] == 0:
        cleanup_cache_name = "OverworldWildBehavior_ClearCustomJumpShadowEffectNoop"
    clear_addr, clear_size = syms[cleanup_cache_name]
    clear_bytes = overlay[clear_addr - base : clear_addr - base + clear_size]
    for value, label in (
        (SLOT_ADDR, "learnset slot"),
        (fallback | 1, "learnset fallback"),
        (0x0200770D, "NARC_dtor"),
    ):
        require(struct.pack("<I", value) in clear_bytes, f"cleanup lacks exact {label}")

    personal_reset_calls = [
        address
        for address, target in thumb_direct_calls(overlay, base, clear_addr, clear_size)
        if target == reset_addr
    ]
    learnset_cleanup_stores = thumb_literal_store_addresses(
        overlay, base, clear_addr, clear_size, fallback | 1, SLOT_ADDR
    )
    learnset_narc_address, learnset_narc_size = syms["sOverworldWildLevelUpLearnsetsNarc"]
    require(
        (learnset_narc_address, learnset_narc_size) == (state_address + 52, 4),
        "personal/learnset NARC state handles are not the exact linked +0/+52 fields",
    )
    dtor_provenance = decode_cleanup_dtor_provenance(
        overlay, base, clear_addr, clear_size, state_address
    )
    require(len(personal_reset_calls) == 1, "cleanup has no unique linked personal reset call")
    require(len(learnset_cleanup_stores) == 1, "cleanup has no unique linked learnset reset store")
    warm_events = sorted(
        [("learnset_reset", learnset_warm_stores[0]), ("personal_publish", publish_calls[0])],
        key=lambda event: event[1],
    )
    cleanup_events = sorted(
        [
            ("personal_reset", personal_reset_calls[0]),
            ("learnset_reset", learnset_cleanup_stores[0]),
            *[
                ("personal_dtor" if handle_offset == 0 else "learnset_dtor", address)
                for handle_offset, address in dtor_provenance
            ],
        ],
        key=lambda event: event[1],
    )
    require_exact_lifecycle_events(warm_events, cleanup_events)

    cleanup_overlay_addr, cleanup_overlay_size = syms["OverworldWildBehavior_CleanupOverlay"]
    cleanup_wrapper_calls = thumb_direct_calls(
        overlay, base, cleanup_overlay_addr, cleanup_overlay_size
    )
    require(
        cleanup_wrapper_calls == [(cleanup_overlay_addr + 2, clear_addr)],
        "exported cleanup machine code does not route exactly once through authenticated teardown",
    )
    text_end = syms["__text_end"][0]
    all_calls = thumb_direct_calls(overlay, base, base, text_end - base)
    for target, label in (
        (publish_addr, "personal publisher"),
        (reset_addr, "personal reset"),
        (clear_addr, "common cleanup"),
    ):
        require(
            sum(call_target == target for _, call_target in all_calls) == 1,
            f"linked overlay has an alternate or missing {label} path",
        )

    get_addr, get_size = syms["OverworldWildBehavior_GetPersonalParam"]
    get_bytes = overlay[get_addr - base : get_addr - base + get_size]
    if "OverworldWildBehavior_LoadPersonalRow" in syms:
        personal_row_addr, personal_row_size = syms["OverworldWildBehavior_LoadPersonalRow"]
        personal_row_bytes = overlay[
            personal_row_addr - base : personal_row_addr - base + personal_row_size
        ]
    else:
        personal_row_bytes = get_bytes
    for value, label in (
        (0x02007689, "NARC_ctor"),
        (0x020078E9, "NARC_GetFileCount"),
        (0x020077E9, "NARC_GetMemberSize"),
        (0x0200778D, "NARC_ReadWholeMember"),
    ):
        require(struct.pack("<I", value) in personal_row_bytes, f"personal row loader lacks {label}")

    for value, label in (
        (0x0206FAA9, "stock GetPersonalAttr"),
        (PERSONAL_PARAM_FALLBACK_ADDR | 1, "resident direct fallback"),
    ):
        require(struct.pack("<I", value) in get_bytes, f"personal getParam lacks {label}")
    require(
        struct.pack("<I", PERSONAL_PARAM_HOOK_ADDR | 1) not in get_bytes
        and struct.pack("<I", PERSONAL_PARAM_SLOT_ADDR) not in get_bytes,
        "personal getParam can recurse through its resident dispatcher",
    )

    load_addr = loader & ~1
    load_size = syms["OverworldWildBehavior_LoadLevelUpLearnset"][1]
    load_bytes = overlay[load_addr - base : load_addr - base + load_size]
    require(struct.pack("<I", 0x0200782D) in load_bytes, "loader lacks NARC_ReadFromMember")
    require(struct.pack("<I", fallback | 1) in load_bytes, "loader lacks direct fallback")
    require(
        struct.pack("<I", HOOK_ADDR | 1) not in load_bytes,
        "ov150 loader can recurse through the resident dispatcher",
    )
    require(
        struct.pack("<I", move_filter | 1) not in load_bytes,
        "loader still reaches the linked unimplemented-move filter",
    )

    validate_addr, validate_size = helper_syms["OverworldWildHelper_ValidateOverlay"]
    lifecycle_addr = helper_syms["OverworldWildHelper_OverlayLifecycle"][0]
    require(validate_addr == 0x023C4068, "helper validator ABI moved")
    require(validate_addr + validate_size <= 0x023C4100, "helper validator overlaps lifecycle")
    require(lifecycle_addr == 0x023C4100, "helper lifecycle ABI moved")
    auth_addr, auth_size = helper_syms["OverworldWildHelper_IsBehaviorOverlayAuthenticated"]
    auth_bytes = helper[auth_addr - 0x023C4000 : auth_addr - 0x023C4000 + auth_size]
    for value, label in (
        (0x4F57424F, "behavior magic"),
        (0x00080002, "behavior version/size"),
        (0x023C3059, "behavior validator"),
        (0x023C3048, "learnset cache entry"),
    ):
        require(struct.pack("<I", value) in auth_bytes, f"helper auth lacks exact {label}")

    helper_src = (repo / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c").read_text()
    auth_start = helper_src.index("static BOOL OverworldWildHelper_IsBehaviorOverlayAuthenticated(BOOL warmLearnsets)\n{")
    auth_end = helper_src.index("\n}\n\nstatic BOOL OverworldWildHelper_ValidateOverlay", auth_start)
    auth_body = helper_src[auth_start:auth_end]
    require(
        auth_body.index("OVERWORLD_WILD_BEHAVIOR_OVERLAY_VALIDATE()")
        < auth_body.index("if (warmLearnsets)")
        < auth_body.index("OVERWORLD_WILD_LEARNSET_CACHE_ENTRY->warm()"),
        "helper can warm before full behavior-overlay authentication",
    )
    require(
        helper_src.count("OverworldWildHelper_IsBehaviorOverlayAuthenticated(TRUE)") == 2,
        "helper warm is not restricted to existing/new authenticated load transitions",
    )
    return loader


def verify_core_control_flow(
    repo: Path,
    core_syms: dict[str, tuple[int, int]],
    fallback: int,
    overlay_loader: int,
) -> None:
    core = (repo / "build/output.bin").read_bytes()
    core_base = core_syms["__text_start"][0]

    unload_address, unload_bytes = linked_function_bytes(
        core,
        core_base,
        core_syms,
        "UnloadOverworldWildBehaviorOverlay",
    )
    unload_calls = thumb_indirect_call_literals(
        core,
        core_base,
        unload_address,
        len(unload_bytes),
    )
    ordered_targets = [target for _, target in unload_calls]
    validate = 0x023C3059
    cleanup = 0x023C3101
    fs_unload = core_syms["FS_UnloadOverlay"][0]
    for target, label in (
        (validate, "behavior validator"),
        (cleanup, "behavior cleanup"),
        (fs_unload, "FS_UnloadOverlay"),
    ):
        require(target in ordered_targets, f"unload machine code lacks {label} call")
    require(
        ordered_targets.index(validate)
        < ordered_targets.index(cleanup)
        < ordered_targets.index(fs_unload),
        "linked unload call order is not validate -> cleanup -> FS_UnloadOverlay",
    )

    fallback_address, fallback_bytes = linked_function_bytes(
        core,
        core_base,
        core_syms,
        "LoadLevelUpLearnset_HandleAlternateForm_Fallback",
    )
    archive_load = core_syms["ArchiveDataLoadOfs"][0] | 1
    require(
        struct.pack("<I", archive_load) in fallback_bytes,
        "fallback machine code lacks direct ArchiveDataLoadOfs target",
    )
    for forbidden, label in (
        (HOOK_ADDR | 1, "resident dispatcher"),
        (SLOT_ADDR, "resident dispatch slot"),
        (overlay_loader, "ov150 cache loader"),
        (core_syms["IsMoveUnimplemented"][0] | 1, "runtime unimplemented-move filter"),
    ):
        require(
            struct.pack("<I", forbidden) not in fallback_bytes,
            f"fallback can recurse through {label}",
        )

    pokemon_source = (repo / "src/pokemon.c").read_text()
    fallback_start = pokemon_source.index(
        "void LONG_CALL LoadLevelUpLearnset_HandleAlternateForm_Fallback("
    )
    fallback_end = pokemon_source.index("\n}\n", fallback_start)
    fallback_source = pokemon_source[fallback_start:fallback_end]
    require(
        fallback_source.count("ArchiveDataLoadOfs(") == 1,
        "fallback source no longer performs one exact archive row read",
    )
    for forbidden in (
        "IsMoveUnimplemented",
        "GetMoveData",
        "BLOCK_LEARNING_UNIMPLEMENTED_MOVES",
        "writeIndex",
        "readIndex",
    ):
        require(
            forbidden not in fallback_source,
            f"fallback still performs runtime learnset filtering: {forbidden}",
        )
    levelup_start = pokemon_source.index(
        "u32 MonTryLearnMoveOnLevelUp(struct PartyPokemon *mon, int *last_i, u16 *sp0)\n{"
    )
    levelup_end = pokemon_source.index("\n}\n\nconst u8 sTrainerGenders", levelup_start)
    levelup_source = pokemon_source[levelup_start:levelup_end]
    require(
        "#ifdef BLOCK_LEARNING_UNIMPLEMENTED_MOVES\n"
        "        if (!IsMoveUnimplemented(*sp0))\n"
        "#endif" in levelup_source,
        "level-up move learning lost its defensive runtime implementation check",
    )

    overlay_src = (repo / "src/overlay.c").read_text()
    start = overlay_src.index("u32 LONG_CALL UnloadOverworldWildBehaviorOverlay(void)\n{")
    end = overlay_src.index("\n}\n", start)
    body = overlay_src[start:end]
    require(
        body.index("OVERWORLD_WILD_BEHAVIOR_OVERLAY_CLEANUP()")
        < body.index("FS_UnloadOverlay(0, OVERLAY_OVERWORLD_WILD_BEHAVIOR_DATA)"),
        "source unload no longer cleans the learnset cache before FS unload",
    )


def narc_members(narc: bytes, label: str) -> list[bytes]:
    require(len(narc) >= 16, f"{label} archive is shorter than its NARC header")
    require(narc[:4] == b"NARC", f"{label} archive has no NARC header")
    require(narc[4:8] == bytes.fromhex("fe ff 00 01"), f"{label} NARC byte order/version differs")
    declared_size, header_size, chunk_count = struct.unpack_from("<IHH", narc, 8)
    require(declared_size == len(narc), f"{label} NARC declared size differs")
    require((header_size, chunk_count) == (16, 3), f"{label} NARC header shape differs")
    require(narc[16:20] == b"BTAF", f"{label} archive has no BTAF")
    btaf_size = struct.unpack_from("<I", narc, 20)[0]
    file_count = struct.unpack_from("<H", narc, 24)[0]
    require(btaf_size == 12 + file_count * 8, f"{label} BTAF size/count differs")
    require(16 + btaf_size <= len(narc), f"{label} BTAF exceeds archive")
    ranges = [struct.unpack_from("<II", narc, 28 + index * 8) for index in range(file_count)]
    btnf = 16 + btaf_size
    require(narc[btnf : btnf + 4] == b"BTNF", f"{label} archive has no BTNF")
    btnf_size = struct.unpack_from("<I", narc, btnf + 4)[0]
    require(btnf_size >= 8 and btnf + btnf_size <= len(narc), f"{label} BTNF exceeds archive")
    gmif = btnf + btnf_size
    require(narc[gmif : gmif + 4] == b"GMIF", f"{label} archive has no GMIF")
    gmif_size = struct.unpack_from("<I", narc, gmif + 4)[0]
    require(gmif_size >= 8 and gmif + gmif_size == len(narc), f"{label} GMIF size differs")
    payload = gmif + 8
    payload_size = gmif_size - 8
    previous_end = 0
    members = []
    for index, (start, end) in enumerate(ranges):
        require(start <= end <= payload_size, f"{label} member {index} exceeds GMIF")
        require(start >= previous_end, f"{label} member {index} overlaps its predecessor")
        members.append(narc[payload + start : payload + end])
        previous_end = end
    return members


def narc_member_zero(narc: bytes) -> bytes:
    members = narc_members(narc, "levelup")
    require(len(members) == 1, f"levelup archive has {len(members)} members")
    return members[0]


def filter_row(
    row: bytes,
    move_flags: dict[int, int],
    unused_move_mask: int,
) -> bytes:
    values = list(struct.unpack("<41I", row))
    write = 0
    terminated = False
    for entry in values:
        move = entry & 0xFFFF
        if move == 0xFFFF:
            values[write] = entry
            terminated = True
            break
        require(move in move_flags, f"learnset references missing move {move}")
        if move_flags[move] & unused_move_mask == 0:
            values[write] = entry
            write += 1
    require(terminated, "learnset row has no terminator")
    return struct.pack("<41I", *values)


def expected_buildtime_row(
    raw_row: bytes,
    move_flags: dict[int, int],
    unused_move_mask: int,
    enabled: bool,
) -> bytes:
    return filter_row(raw_row, move_flags, unused_move_mask) if enabled else raw_row


def raw_levelup_rows_from_generated_source(repo: Path) -> bytes:
    path = repo / "build/learnset/LevelupLearnsets.c"
    source = path.read_text()
    start = source.index("const u32 UNUSED LevelUpLearnsets[][MAX_LEVELUP_MOVES] = {")
    values = [
        int(value, 16)
        for value in re.findall(r"0x([0-9A-Fa-f]{8})", source[start:])
    ]
    require(
        len(values) == ROW_COUNT * 41,
        f"generated raw learnset source has {len(values)} entries instead of {ROW_COUNT * 41}",
    )
    return struct.pack(f"<{len(values)}I", *values)


def verify_exhaustive_oracle(repo: Path) -> None:
    direct = (repo / "build/a033/LevelupLearnsets.bin").read_bytes()
    levelup_member = narc_member_zero((repo / "build/narc/a033.narc").read_bytes())
    require(len(direct) == MEMBER_SIZE, f"direct learnsets are {len(direct)} bytes")
    require(levelup_member == direct, "NARC member 0 differs from generated direct rows")

    moves_header = (repo / "include/constants/moves.h").read_text()
    canonical_match = re.search(r"^#define NUM_OF_CANONICAL_MOVES (\d+)$", moves_header, re.MULTILINE)
    custom_match = re.search(r"^#define NUM_OF_CUSTOM_MOVES (\d+)$", moves_header, re.MULTILINE)
    require(canonical_match is not None and custom_match is not None, "move-count constants differ")
    expected_move_rows = int(canonical_match.group(1)) + int(custom_match.group(1)) + 1

    unused_move_mask, move_flags_offset, move_record_size = (
        derive_authoritative_move_layout(repo)
    )
    move_paths = sorted((repo / "build/a011").glob("move_*"))
    require(
        [path.name for path in move_paths]
        == [f"move_{move:03d}" for move in range(expected_move_rows)],
        "fresh move-data rows are not the exact contiguous move_000..NUM_OF_MOVES set",
    )
    move_flags: dict[int, int] = {}
    for path in move_paths:
        move = int(path.name.split("_")[1])
        data = path.read_bytes()
        require(len(data) == move_record_size, f"{path.name} is not a BattleMove")
        move_flags[move] = data[move_flags_offset]

    generated_arc11 = narc_members(
        (repo / "build/narc/a011.narc").read_bytes(),
        "generated ARC11",
    )
    require(len(generated_arc11) == len(move_paths), "generated ARC11 member count differs")
    for move, (move_member, path) in enumerate(zip(generated_arc11, move_paths)):
        require(
            move_member == path.read_bytes(),
            f"generated ARC11 member {move} differs from loose row",
        )
    packaged_arc11 = narc_members(
        (repo / "base/root/a/0/1/1").read_bytes(),
        "packaged ARC11",
    )
    require(packaged_arc11 == generated_arc11, "packaged ARC11 differs from generated ARC11")
    require(
        len(levelup_member) == MEMBER_SIZE and levelup_member == direct,
        "ARC11 verification clobbered the authenticated ARC33 member",
    )

    raw = raw_levelup_rows_from_generated_source(repo)
    enabled = learnset_filter_enabled(repo)
    cache = bytearray(ROW_SIZE)
    filtered_rows = 0
    for index in range(ROW_COUNT):
        raw_row = raw[index * ROW_SIZE : (index + 1) * ROW_SIZE]
        direct_row = direct[index * ROW_SIZE : (index + 1) * ROW_SIZE]
        archive_row = levelup_member[index * ROW_SIZE : (index + 1) * ROW_SIZE]
        cache[:] = archive_row  # exact cache miss NARC read
        expected = expected_buildtime_row(
            raw_row,
            move_flags,
            unused_move_mask,
            enabled,
        )
        require(direct_row == expected, f"build-time filtered row mismatch in row {index}")
        require(bytes(cache) == expected, f"cache-miss row mismatch in row {index}")
        require(bytes(cache) == expected, f"cache-hit row mismatch in row {index}")
        if enabled:
            require(
                filter_row(bytes(cache), move_flags, unused_move_mask) == bytes(cache),
                f"build-time filtered row {index} is not idempotent",
            )
        filtered_rows += expected != raw_row
    print(
        f"learnset oracle: {ROW_COUNT} generated raw rows -> {filtered_rows} rows "
        f"build-time compacted identically; runtime cache copy exact"
    )


def personal_attr(row: bytes, attr: int) -> int:
    """Model hg-engine's patched 44-byte BASE_STATS attribute ABI."""
    require(len(row) == PERSONAL_ROW_SIZE, "personal oracle row is not 44 bytes")
    require(0 <= attr < PERSONAL_ATTR_COUNT, f"personal attribute {attr} is out of range")
    if attr <= 9:
        return row[attr]
    if attr <= 15:
        ev_yields = struct.unpack_from("<H", row, 10)[0]
        return (ev_yields >> ((attr - 10) * 2)) & 3
    if attr <= 17:
        return struct.unpack_from("<H", row, 12 + (attr - 16) * 2)[0]
    if attr <= 23:
        return row[16 + (attr - 18)]
    if attr == 24:
        return struct.unpack_from("<H", row, 22)[0]
    if attr == 25:
        return struct.unpack_from("<H", row, 26)[0]
    if attr == 26:
        return row[24]
    if attr == 27:
        return row[25] & 0x7F
    if attr == 28:
        return row[25] >> 7
    return struct.unpack_from("<I", row, 28 + (attr - 29) * 4)[0]


def resolve_stock_personal_species(species: int, form: int) -> int:
    """Model HeartGold ResolveMonForm at the resident 0x02072634 target."""
    special = {
        386: (3, 495),  # Deoxys forms -> rows 496..498
        413: (2, 498),  # Wormadam forms -> rows 499..500
        487: (1, 500),  # Giratina Origin -> row 501
        492: (1, 501),  # Shaymin Sky -> row 502
        479: (5, 502),  # Rotom appliances -> rows 503..507
    }
    if species in special:
        maximum, base = special[species]
        return base + form if form and form <= maximum else species
    return species


def resolve_expanded_personal_species(species: int, form: int, form_table: bytes) -> int:
    """Model hg-engine PokeOtherFormMonsNoGet for already expanded callers."""
    resolved = resolve_stock_personal_species(species, form)
    if species in (386, 413, 487, 492, 479):
        return resolved
    if form == 0:
        return species
    offset = (PERSONAL_FORM_WIDTH * species + form - 1) * 2
    require(0 <= form <= PERSONAL_FORM_WIDTH, f"form {form} exceeds the 32-entry form ABI")
    require(offset + 2 <= len(form_table), f"form lookup ({species}, {form}) exceeds generated table")
    resolved = struct.unpack_from("<H", form_table, offset)[0] & ~PERSONAL_NEEDS_REVERSION
    return resolved if resolved else species


def verify_personal_source_contract(repo: Path) -> None:
    source = (repo / "src/pokemon.c").read_text()
    start = source.index("int LONG_CALL PokeOtherFormMonsNoGet(int mons_no, int form_no)\n{")
    end = source.index("\n}\n\n/**", start)
    body = source[start:end]
    fragments = (
        "case SPECIES_DEOXYS:",
        "mons_no = 495 + form_no;",
        "case SPECIES_WORMADAM:",
        "mons_no = 498 + form_no;",
        "case SPECIES_GIRATINA:",
        "mons_no = 500 + form_no;",
        "case SPECIES_SHAYMIN:",
        "mons_no = 501 + form_no;",
        "case SPECIES_ROTOM:",
        "mons_no = 502 + form_no;",
        "sizeof(u16) * (32 * mons_no + form_no - 1)",
        "newSpecies &= ~(NEEDS_REVERSION);",
    )
    for fragment in fragments:
        require(fragment in body, f"personal form resolver source contract lost: {fragment}")

    macros = (repo / "armips/include/macros.s").read_text()
    for fragment in (
        ".macro basestats,hp,atk,def,spd,spatk,spdef",
        ".halfword (hp | atk << 2 | def << 4 | spd << 6 | spatk << 8 | spdef << 10)",
        ".orga 0x16\n\t.halfword abi1",
        ".orga 0x1A\n\t.halfword abi2",
        ".orga 0x18\n\t.byte num",
        ".byte (color | flip << 7)",
        ".orga 0x1C",
    ):
        require(fragment in macros, f"personal row generator source contract lost: {fragment}")

    ability_patch = (repo / "armips/asm/abilities.s").read_text()
    require(
        ".org 0x0206FB80\nldrh r5, [r4, #0x16]" in ability_patch
        and ".org 0x0206FB84\nldrh r5, [r4, #0x1A]" in ability_patch,
        "widened personal-ability accessor patches differ",
    )

    reference = repo / ".codex-reference/pokeheartgold/src/pokemon.c"
    if reference.is_file():
        decomp = reference.read_text()
        require(
            "int GetPersonalAttr(const BASE_STATS *baseStats, int attr)" in decomp
            and "int GetMonBaseStat_HandleAlternateForm(int species, int form, int attr)" in decomp
            and "int GetMonBaseStat(int species, int attr)" in decomp,
            "local HeartGold decomp no longer contains the personal-data oracle",
        )
        resolve_start = decomp.index("int ResolveMonForm(int species, int form) {")
        resolve_end = decomp.index("\n}\n\nu32 MaskOfFlagNo", resolve_start)
        resolve_body = decomp[resolve_start:resolve_end]
        for fragment in (
            "case SPECIES_DEOXYS:",
            "return SPECIES_DEOXYS_ATK + form - DEOXYS_ATTACK;",
            "case SPECIES_WORMADAM:",
            "return SPECIES_WORMADAM_SANDY + form - WORMADAM_SANDY;",
            "case SPECIES_GIRATINA:",
            "case SPECIES_SHAYMIN:",
            "case SPECIES_ROTOM:",
            "return species;",
        ):
            require(fragment in resolve_body, f"local decomp ResolveMonForm contract lost: {fragment}")


def verify_personal_exhaustive_oracle(repo: Path) -> None:
    verify_personal_source_contract(repo)
    generated_paths = sorted((repo / "build/a002").glob("mondata_*"))
    require(len(generated_paths) == PERSONAL_ROW_COUNT, f"generated personal row count is {len(generated_paths)}")
    expected_names = [f"mondata_{index:04d}" for index in range(PERSONAL_ROW_COUNT)]
    require(
        [path.name for path in generated_paths] == expected_names,
        "generated personal row names are not the exact contiguous 0000..1392 set",
    )
    generated = [path.read_bytes() for path in generated_paths]
    for index, row in enumerate(generated):
        require(len(row) == PERSONAL_ROW_SIZE, f"generated personal row {index} is {len(row)} bytes")

    archive = narc_members((repo / "build/narc/mondata.narc").read_bytes(), "ARC_PERSONAL")
    require(len(archive) == PERSONAL_ROW_COUNT, f"ARC_PERSONAL has {len(archive)} members")
    for index, (member, direct) in enumerate(zip(archive, generated)):
        require(len(member) == PERSONAL_ROW_SIZE, f"ARC_PERSONAL member {index} is {len(member)} bytes")
        require(member == direct, f"ARC_PERSONAL member {index} differs from generated row")
        cache = bytes(member)
        for attr in range(PERSONAL_ATTR_COUNT):
            expected = personal_attr(direct, attr)
            require(personal_attr(cache, attr) == expected, f"personal cache-miss attr mismatch: row {index}, attr {attr}")
            require(personal_attr(cache, attr) == expected, f"personal cache-hit attr mismatch: row {index}, attr {attr}")
        require(
            tuple(personal_attr(cache, attr) for attr in range(6)) == tuple(direct[:6]),
            f"personal base-stat tuple mismatch in row {index}",
        )

    require(
        b"".join(archive) == b"".join(generated)
        and len(b"".join(archive)) == PERSONAL_ROW_COUNT * PERSONAL_ROW_SIZE,
        "ARC_PERSONAL exhaustive raw-row image differs",
    )

    form_table = (repo / "build/a028/9_11").read_bytes()
    require(
        len(form_table) % (PERSONAL_FORM_WIDTH * 2) == 0,
        "generated personal form table is not 32-u16-row aligned",
    )
    form_rows = len(form_table) // (PERSONAL_FORM_WIDTH * 2)
    resolved_expanded_forms = 0
    checked_expanded_forms = 0
    for species in range(form_rows):
        require(resolve_expanded_personal_species(species, 0, form_table) == species, f"form-zero changed species {species}")
        for form in range(1, PERSONAL_FORM_WIDTH + 1):
            resolved = resolve_expanded_personal_species(species, form, form_table)
            require(0 <= resolved < PERSONAL_ROW_COUNT, f"form ({species}, {form}) resolves to {resolved}")
            checked_expanded_forms += 1
            resolved_expanded_forms += resolved != species
            for attr in range(PERSONAL_ATTR_COUNT):
                require(
                    personal_attr(archive[resolved], attr) == personal_attr(generated[resolved], attr),
                    f"resolved-form attr mismatch: species {species}, form {form}, attr {attr}",
                )

    checked_stock_forms = 0
    resolved_stock_forms = 0
    for species in range(PERSONAL_ROW_COUNT):
        for form in range(PERSONAL_FORM_WIDTH + 1):
            resolved = resolve_stock_personal_species(species, form)
            require(0 <= resolved < PERSONAL_ROW_COUNT, f"stock form ({species}, {form}) resolves to {resolved}")
            require(archive[resolved] == generated[resolved], f"stock form row mismatch: species {species}, form {form}")
            checked_stock_forms += 1
            resolved_stock_forms += resolved != species
    print(
        f"personal oracle: ARC2 {PERSONAL_ROW_COUNT} members x {PERSONAL_ROW_SIZE} bytes exact; "
        f"{PERSONAL_ROW_COUNT * PERSONAL_ATTR_COUNT} direct attrs and "
        f"{checked_stock_forms} stock form loads exact ({resolved_stock_forms} non-base); "
        f"{checked_expanded_forms} expanded pre-resolutions exact "
        f"({resolved_expanded_forms} non-base)"
    )


def run_unit_fixtures() -> None:
    def expect_rejection(action, label: str) -> None:
        try:
            action()
        except SystemExit:
            return
        fail(f"negative unit fixture was accepted: {label}")

    legacy_size = OVERLAY_150_BASELINE_SIZE + MAX_OVERLAY_150_DELTA
    verify_overlay_150_capacity_contract(
        legacy_size,
        legacy_size,
        bytes(legacy_size),
        {},
    )
    expect_rejection(
        lambda: verify_overlay_150_capacity_contract(
            legacy_size + 1,
            legacy_size + 1,
            bytes(legacy_size + 1),
            {},
        ),
        "legacy overlay 150 consuming its expansion reserve",
    )

    resolver_payload = bytearray(
        OVERLAY_150_CAPACITY - OVERLAY_150_FIXED_RESOLVER_MIN_MARGIN
    )
    struct.pack_into("<IHH", resolver_payload, 0, 0x4F57424F, 2, 8)
    struct.pack_into("<IHH", resolver_payload, 0xE0, 0x4F575043, 1, 12)
    resolver_target = OVERLAY_150_BASE + 0x200
    struct.pack_into(
        "<I",
        resolver_payload,
        OVERLAY_150_OVERLAP_RESOLVER_OFFSET,
        resolver_target | 1,
    )
    resolver_symbols = {
        "gOverworldWildBehaviorDataOverlayHeader": (OVERLAY_150_BASE, 0x58),
        "OverworldWildBehavior_ValidateOverlay": (OVERLAY_150_BASE + 0x58, 0x20),
        "gOverworldWildPersonalCacheOverlayEntry": (OVERLAY_150_BASE + 0xE0, 12),
        "gOverworldWildOverlapResolverEntry": (OVERLAY_150_BASE + 0xEC, 4),
        "OverworldWildBehavior_CleanupOverlay": (OVERLAY_150_BASE + 0x100, 8),
        "OverworldWildBehavior_TryResolveOverlap": (resolver_target, 0x20),
    }
    verify_overlay_150_capacity_contract(
        len(resolver_payload),
        len(resolver_payload),
        bytes(resolver_payload),
        resolver_symbols,
    )
    expect_rejection(
        lambda: verify_overlay_150_capacity_contract(
            len(resolver_payload),
            len(resolver_payload),
            bytes(resolver_payload),
            {},
        ),
        "near-full overlay 150 without authenticated fixed resolver",
    )
    wrong_pointer_payload = bytearray(resolver_payload)
    struct.pack_into(
        "<I",
        wrong_pointer_payload,
        OVERLAY_150_OVERLAP_RESOLVER_OFFSET,
        resolver_target + 0x20 | 1,
    )
    expect_rejection(
        lambda: verify_overlay_150_capacity_contract(
            len(wrong_pointer_payload),
            len(wrong_pointer_payload),
            bytes(wrong_pointer_payload),
            resolver_symbols,
        ),
        "near-full overlay 150 with unauthenticated resolver target",
    )
    expect_rejection(
        lambda: verify_overlay_150_capacity_contract(
            len(resolver_payload) + 1,
            len(resolver_payload),
            bytes(resolver_payload),
            resolver_symbols,
        ),
        "fixed-resolver overlay 150 consuming its final two-byte guard",
    )

    learnset_values = [
        0x00010002,
        0x00020001,
        0x00030002,
        0x00040001,
        0x00050003,
        0x0000FFFF,
        0x00AA0003,
    ]
    learnset_values.extend([0x00BB0003] * (41 - len(learnset_values)))
    learnset_fixture = struct.pack("<41I", *learnset_values)
    filtered_values = list(learnset_values)
    filtered_values[0] = learnset_values[1]
    filtered_values[1] = learnset_values[3]
    filtered_values[2] = learnset_values[4]
    filtered_values[3] = learnset_values[5]
    expected_filtered = struct.pack("<41I", *filtered_values)
    fixture_unused_move_mask = 0x20
    fixture_move_flags = {1: 0, 2: fixture_unused_move_mask, 3: 0}
    require(
        filter_row(learnset_fixture, fixture_move_flags, fixture_unused_move_mask)
        == expected_filtered,
        "synthetic build-time filter lost order/duplicates/multiple removals/tail bytes",
    )
    require(
        filter_row(expected_filtered, fixture_move_flags, fixture_unused_move_mask)
        == expected_filtered,
        "synthetic build-time learnset filter is not idempotent",
    )
    require(
        expected_buildtime_row(
            learnset_fixture,
            fixture_move_flags,
            fixture_unused_move_mask,
            False,
        )
        == learnset_fixture,
        "synthetic config-off learnset row was filtered",
    )
    sentinel_first = struct.pack("<41I", 0x0000FFFF, *([0x12340003] * 40))
    require(
        filter_row(sentinel_first, fixture_move_flags, fixture_unused_move_mask)
        == sentinel_first,
        "synthetic first-sentinel learnset row changed",
    )
    missing_move = list(learnset_values)
    missing_move[0] = 0x00010004
    expect_rejection(
        lambda: filter_row(
            struct.pack("<41I", *missing_move),
            fixture_move_flags,
            fixture_unused_move_mask,
        ),
        "learnset row with missing move-data member",
    )
    expect_rejection(
        lambda: filter_row(
            struct.pack("<41I", *([1] * 41)),
            {1: 0},
            fixture_unused_move_mask,
        ),
        "unterminated learnset row",
    )

    row = bytearray(PERSONAL_ROW_SIZE)
    row[:10] = bytes(range(1, 11))
    ev_values = (0, 1, 2, 3, 0, 3)
    struct.pack_into("<H", row, 10, sum(value << (index * 2) for index, value in enumerate(ev_values)))
    struct.pack_into("<HH", row, 12, 0x1234, 0xABCD)
    row[16:22] = bytes(range(18, 24))
    struct.pack_into("<H", row, 22, 0x3456)
    row[24] = 0x77
    row[25] = 0x85
    struct.pack_into("<H", row, 26, 0x789A)
    tm_values = (0x01234567, 0x89ABCDEF, 0x13579BDF, 0x2468ACE0)
    struct.pack_into("<4I", row, 28, *tm_values)
    expected = (
        *range(1, 11),
        *ev_values,
        0x1234,
        0xABCD,
        *range(18, 24),
        0x3456,
        0x789A,
        0x77,
        5,
        1,
        *tm_values,
    )
    require(
        tuple(personal_attr(bytes(row), attr) for attr in range(PERSONAL_ATTR_COUNT)) == expected,
        "synthetic personal-attribute fixture differs",
    )

    first = bytes(row)
    second = bytes(reversed(row))
    btaf = b"BTAF" + struct.pack("<IHH", 28, 2, 0) + struct.pack("<4I", 0, 44, 44, 88)
    btnf = b"BTNF" + struct.pack("<I", 8)
    gmif = b"GMIF" + struct.pack("<I", 8 + len(first) + len(second)) + first + second
    total = 16 + len(btaf) + len(btnf) + len(gmif)
    header = b"NARC" + bytes.fromhex("fe ff 00 01") + struct.pack("<IHH", total, 16, 3)
    fixture_narc = header + btaf + btnf + gmif
    require(narc_members(fixture_narc, "fixture") == [first, second], "synthetic NARC fixture differs")
    corrupt_narc = bytearray(fixture_narc)
    struct.pack_into("<I", corrupt_narc, 8, len(corrupt_narc) + 1)
    expect_rejection(lambda: narc_members(bytes(corrupt_narc), "corrupt fixture"), "NARC size mismatch")
    expect_rejection(lambda: personal_attr(bytes(row), PERSONAL_ATTR_COUNT), "out-of-range personal attr")

    stock_accessor = bytearray(GET_PERSONAL_ATTR_END - GET_PERSONAL_ATTR_ADDR)
    patched_accessor = bytearray(stock_accessor)
    for address, (stock_halfword, patched_halfword) in GET_PERSONAL_ATTR_PATCHES.items():
        offset = address - GET_PERSONAL_ATTR_ADDR
        stock_accessor[offset : offset + 2] = stock_halfword
        patched_accessor[offset : offset + 2] = patched_halfword
    verify_get_personal_attr_bytes(
        bytes(stock_accessor), bytes(patched_accessor),
        STOCK_GET_PERSONAL_ATTR_NEXT_BYTES, STOCK_GET_PERSONAL_ATTR_NEXT_BYTES,
    )
    corrupt_accessor = bytearray(patched_accessor)
    corrupt_accessor[8] ^= 1
    expect_rejection(
        lambda: verify_get_personal_attr_bytes(
            bytes(stock_accessor), bytes(corrupt_accessor),
            STOCK_GET_PERSONAL_ATTR_NEXT_BYTES, STOCK_GET_PERSONAL_ATTR_NEXT_BYTES,
        ),
        "non-ability GetPersonalAttr byte corruption",
    )

    for label in ("fixture ARC2", "fixture ARC33", "fixture a028 member 11"):
        verify_exact_packaged_payload(b"generated", b"generated", label)
        expect_rejection(
            lambda label=label: verify_exact_packaged_payload(b"generated", b"stale", label),
            f"stale packaged {label}",
        )

    valid_warm = [("learnset_reset", 0x100), ("personal_publish", 0x104)]
    valid_cleanup = [
        ("personal_reset", 0x200), ("learnset_reset", 0x204),
        ("personal_dtor", 0x208), ("learnset_dtor", 0x20C),
    ]
    require_exact_lifecycle_events(valid_warm, valid_cleanup)
    expect_rejection(
        lambda: require_exact_lifecycle_events(list(reversed(valid_warm)), valid_cleanup),
        "reordered linked warm publication",
    )
    expect_rejection(
        lambda: require_exact_lifecycle_events(valid_warm, valid_cleanup[:-1]),
        "removed linked cleanup dtor",
    )
    expect_rejection(
        lambda: require_exact_lifecycle_events(
            valid_warm, [valid_cleanup[1], valid_cleanup[0], *valid_cleanup[2:]]
        ),
        "reordered linked cleanup resets",
    )

    linked_cleanup_fixture = bytes.fromhex(
        "10 b5 ff f7 f7 fe 0e 4b 0e 4a 0f 4c 13 60 20 68 "
        "01 28 02 d9 0d 4b 00 f0 8d fb 00 23 60 6b 23 60 "
        "a3 80 98 42 02 d0 09 4b 00 f0 84 fb 01 21 00 22 "
        "07 4b 49 42 62 63 19 80 62 64 ff f7 d1 ff 10 bd "
        "d1 ca 3d 02 d8 1f 07 02 e0 3d 3c 02 0d 77 00 02 "
        "cc 3e 3c 02"
    )
    require(
        decode_cleanup_dtor_provenance(
            linked_cleanup_fixture, 0x023C3314, 0x023C3314,
            len(linked_cleanup_fixture), 0x023C3DE0,
        )
        == [(0, 0x023C3328), (52, 0x023C333A)],
        "linked cleanup provenance fixture differs",
    )
    same_handle_cleanup = bytearray(linked_cleanup_fixture)
    same_handle_cleanup[0x1C : 0x1E] = bytes.fromhex("20 68")
    expect_rejection(
        lambda: decode_cleanup_dtor_provenance(
            bytes(same_handle_cleanup), 0x023C3314, 0x023C3314,
            len(same_handle_cleanup), 0x023C3DE0,
        ),
        "machine-level same-handle double NARC_dtor",
    )

    form_table = bytearray((493 * PERSONAL_FORM_WIDTH) * 2)
    struct.pack_into("<H", form_table, (25 * PERSONAL_FORM_WIDTH + 1) * 2, 0x8000 | 1234)
    require(resolve_expanded_personal_species(25, 2, bytes(form_table)) == 1234, "synthetic form-table fixture differs")
    require(resolve_stock_personal_species(25, 2) == 25, "stock non-vanilla form fixture differs")
    require(resolve_stock_personal_species(386, 3) == 498, "Deoxys form fixture differs")
    require(resolve_stock_personal_species(386, 4) == 386, "Deoxys invalid-form fixture differs")
    print("cache verifier unit fixtures: exact")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--patched-arm9", type=Path)
    parser.add_argument(
        "--require-patched-arm9",
        action="store_true",
        help="fail unless the authoritative post-Armips ARM9 is supplied",
    )
    parser.add_argument(
        "--self-test-only",
        action="store_true",
        help="run deterministic in-memory verifier fixtures without build artifacts",
    )
    args = parser.parse_args()
    repo = args.repo.resolve()

    run_unit_fixtures()
    if args.self_test_only:
        return

    verify_personal_overlay_source_contract(repo)
    verify_buildtime_learnset_filter_contract(repo)
    move_layout = derive_authoritative_move_layout(repo)
    verify_production_filter_black_box(repo, move_layout)
    verify_atomic_narc_black_box(repo)
    core_symbols = symbols(repo / "build/linked.o")
    verify_runtime_move_filter_contract(repo, core_symbols, move_layout)
    require(
        core_symbols["LoadLevelUpLearnset_HandleAlternateForm"][0] == 0x02071FC9,
        "public core loader symbol does not target the odd resident trampoline",
    )
    fallback = core_symbols["LoadLevelUpLearnset_HandleAlternateForm_Fallback"][0] | 1
    if args.require_patched_arm9 and args.patched_arm9 is None:
        fail("--require-patched-arm9 needs --patched-arm9 after Armips packaging")
    if args.require_patched_arm9:
        verify_packaged_cache_narcs(repo)
        verify_packaged_overlays(repo)
    verify_personal_stock_envelopes(repo)
    verify_personal_dispatch_sources(repo, args.patched_arm9)
    verify_hook_sources(repo, fallback, args.patched_arm9)
    overlay_loader = verify_overlay_lifecycle(
        repo,
        fallback,
        core_symbols["IsMoveUnimplemented"][0],
    )
    verify_core_control_flow(repo, core_symbols, fallback, overlay_loader)
    verify_exhaustive_oracle(repo)
    verify_personal_exhaustive_oracle(repo)
    if args.patched_arm9 is None:
        print(
            "learnset hook gate: static-only; the packaging target requires "
            "--patched-arm9 base/arm9.bin"
        )
    print(
        "learnset cache static gate: "
        f"hook=0x{HOOK_ADDR:08X} slot=0x{SLOT_ADDR:08X} "
        f"fallback=0x{fallback:08X} next=0x{NEXT_FUNCTION_ADDR:08X}"
    )


if __name__ == "__main__":
    main()
