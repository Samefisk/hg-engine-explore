#!/usr/bin/env python3
"""Verify the resident mount controller and its profile-resolution bridge."""

from __future__ import annotations

import argparse
import re
import struct
import subprocess
from pathlib import Path

if __package__:
    from .verify_pokemon_move_history_capture import elf_bytes_at, elf_section_layout, layout_symbols, current_field_overlay_metadata
else:
    from verify_pokemon_move_history_capture import elf_bytes_at, elf_section_layout, layout_symbols, current_field_overlay_metadata


REPO = Path(__file__).resolve().parents[1]
OVERLAY_ID = 157
OVERLAY_BASE = 0x023BAB00
OVERLAY_ENTRY = 0x023BB600
OVERLAY_LIMIT = 0x023BC800
FIELD_OVERLAY_ID = 131
FIELD_OVERLAY_LIMIT = 0x023CCFD8
ENTRY_MAGIC = 0x544E554D
ENTRY_VERSION = 11
ENTRY_SIZE = 32
PLAYER_CONTROL_WRAPPER = OVERLAY_ENTRY + 0x20
PLAYER_STEP_WRAPPER = OVERLAY_ENTRY + 0xA0
PLAYER_STEP_RESIDENT_HANDLER = 0x023D9B69
PLAYER_STEP_RESIDENT_LITERAL = PLAYER_STEP_WRAPPER + 0x20
FIELD_INPUT_WRAPPER = OVERLAY_ENTRY + 0xE0
CRASH_SOUND_WRAPPER = OVERLAY_ENTRY + 0x140
TOGGLE_LATCH_WRAPPER = OVERLAY_BASE + 0xC78
TOGGLE_LATCH_ADDR = 0x023BC7DA
MOVE_CONTROL_CALL_SITES = (0x0203E1F0, 0x0203E260, 0x0203E2E4)
FIELD_INPUT_CALL_SITE = 0x0203E270
CRASH_SOUND_CALL_SITES = (0x0205D532, 0x0205D5C2)
HELD_MOVEMENT_HOOK = 0x0205DA1C
FIELD_OBJECT_OVERLAY_ID = 1
MOUNT_FACING_CALL_SITE = 0x021F8E68
MOUNT_FACING_WRAPPER = 0x023BD3EC
RUNTIME_ACK_TARGET = 0x023BD351
RUNTIME_ACK_WRAPPER_NAME = "OverworldMount_CallActorMotionBoundary"
FIXED_DIRECT_IMPORTS = {
    "memcpy": 0x023DEEBE,
    "memset": 0x023DEEA2,
    "OverworldActorPolicy_MountCommand": 0x023BA0E0,
    "OverworldMount_ResetMomentum": 0x01FF9AB0,
    "OverworldMount_GetSurfaceId": 0x01FF9A70,
    "OverworldMount_UpdatePlayerBaseHeight": 0x01FF97E0,
    "OverworldMount_ClearFollowerDecisionCooldown": 0x01FF97D0,
    "OverworldMount_GetOrdinaryDirection": 0x01FF9780,
    "OverworldMount_FinalizeIsPending": 0x01FF97C0,
    "OverworldMount_IsLandingTileAllowed": 0x01FF9620,
    "OverworldMount_ApplyWalkPolicyOutput": 0x01FF96C0,
    "OverworldMount_FinishOneFrameWalk": 0x023BA0BC,
    "OverworldWalkMount_RebaseMotionTarget": 0x023BFFEA,
    "OverworldWalk_DirectionFromDelta": 0x023BF68C,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"mount verifier: {message}")


def function_body(source: str, name: str) -> str:
    """Return a C function body while skipping prototypes and attributes."""
    start = -1
    while True:
        start = source.find(name, start + 1)
        require(start >= 0, f"function is missing: {name}")
        opening = source.find("{", start)
        declaration = source.find(";", start)
        if opening >= 0 and (declaration < 0 or opening < declaration):
            break
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    require(False, f"function body is incomplete: {name}")
    return ""


def decode_thumb_bl(arm9: bytes, load_address: int, address: int) -> int:
    offset = address - load_address
    require(0 <= offset <= len(arm9) - 4, f"BL site 0x{address:08X} is outside ARM9")
    high, low = struct.unpack_from("<HH", arm9, offset)
    require(
        high & 0xF800 == 0xF000 and low & 0xF800 == 0xF800,
        f"site 0x{address:08X} is not a Thumb-1 BL",
    )
    displacement = ((high & 0x7FF) << 12) | ((low & 0x7FF) << 1)
    if displacement & (1 << 22):
        displacement -= 1 << 23
    return address + 4 + displacement


def fixed_import_source_contract(source: str) -> None:
    for name, target in FIXED_DIRECT_IMPORTS.items():
        require(f".thumb_func\\n.thumb_set {name}, 0x{target:08X}\\n" in source,
                f"{name} lacks the exact fixed Thumb-function import")


def fixed_import_call_contract(
    kind: str, linked: bytes, packaged: bytes, address: int, target: int,
) -> None:
    require(kind == "R_ARM_THM_CALL" and linked == packaged and len(packaged) == 4,
            "fixed import changed relocation kind or packaged call bytes")
    require(decode_thumb_bl(packaged, address, address) == target,
            f"fixed import at 0x{address:08X} does not directly BL to 0x{target:08X}")


def fixed_import_source_fixtures(source: str) -> None:
    fixed_import_source_contract(source)
    for mutant in (
        source.replace(".thumb_func\\n.thumb_set memcpy", ".thumb_set memcpy"),
        source.replace("0x023DEEBE\\n", "0x023DEEC0\\n"),
    ):
        try:
            fixed_import_source_contract(mutant)
        except SystemExit:
            pass
        else:
            require(False, "wrong import target or Thumb mode passed its negative control")
    address, target = OVERLAY_BASE + 0x1000, FIXED_DIRECT_IMPORTS["memcpy"]
    delta = target - address - 4
    code = struct.pack("<HH", 0xF000 | ((delta >> 12) & 0x7FF),
                       0xF800 | ((delta >> 1) & 0x7FF))
    fixed_import_call_contract("R_ARM_THM_CALL", code, code, address, target)
    for kind, linked, packaged in (
        ("R_ARM_ABS32", code, code),
        ("R_ARM_THM_CALL", code, b"\x00\xf0\x00\xf8"),
        ("R_ARM_THM_CALL", b"\x00\xf0\x00\xf8", b"\x00\xf0\x00\xf8"),
        ("R_ARM_THM_CALL", code[:2] + b"\x00\xe8", code[:2] + b"\x00\xe8"),
    ):
        try:
            fixed_import_call_contract(kind, linked, packaged, address, target)
        except SystemExit:
            pass
        else:
            require(False, "wrong relocation, target, mode, or package passed its negative control")


def verify_mount_surface_helper_abi() -> None:
    """The surface query lives in chain overlay 159, clear of core data."""
    helper_source = (REPO / "src/overworld_mount_chain_overlay/overworld_mount_surface_id.c").read_text()
    mount_source = (REPO / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text()
    linker = (REPO / "src/overworld_mount_chain_overlay/linker.ld").read_text()
    core_linker = (REPO / "src/linker.ld").read_text()
    linked_path = REPO / "build/overworld_mount_chain_overlay_linked.o"
    resident = layout_symbols(linked_path, "arm-none-eabi-objdump")
    core_symbols = layout_symbols(REPO / "build/linked.o", "arm-none-eabi-objdump")
    imports = layout_symbols(
        REPO / "build/overworld_mount_overlay/overworld_mount_overlay.o",
        "arm-none-eabi-objdump")
    packaged = (REPO / "build/output_overworld_mount_chain_overlay.bin").read_bytes()
    relocations = subprocess.check_output([
        "arm-none-eabi-objdump", "-r",
        str(REPO / "build/overworld_mount_overlay/overworld_mount_overlay.o")], text=True)
    name = "OverworldMount_GetSurfaceId"
    address = FIXED_DIRECT_IMPORTS[name]
    helper = resident.get(name)
    require(helper is not None and helper[0] == address
            and 0 < helper[1] <= 0x4C and helper[2:] == (".text", "F")
            and name not in core_symbols,
            "surface query is not bounded code outside core overlay 129")
    packaged_offset = address - 0x01FF9800
    require(packaged[packaged_offset:packaged_offset + helper[1]]
            == elf_bytes_at(linked_path, address, helper[1]),
            "surface query differs from packaged chain bytes")
    require(imports.get(name) == (address, 0, "*ABS*", "F")
            and 'section(".overworld_mount_surface_id")' in helper_source
            and "KEEP(*(.overworld_mount_surface_id))" in linker
            and "ASSERT(OverworldMount_GetSurfaceId == ORIGIN(rom) + 0x270"
                in linker
            and "ASSERT(. <= ORIGIN(rom) + 0x2B0" in linker
            and ".overworld_mount_surface_id" not in core_linker,
            "surface query lost its fixed chain-overlay bridge")
    require(len(re.findall(rf"R_ARM_THM_CALL\s+\*ABS\*0x{address:x}\b",
                           relocations, re.IGNORECASE)) == 1,
            "surface query no longer has one direct Mount caller")
    require("(const OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR"
                in helper_source
            and "state->fieldSystem" in helper_source
            and "state->surfaceCatalog" in helper_source
            and "OverworldMount_GetSurfaceId(int targetX, int targetY);"
                in mount_source
            and "+ SIZEOF(.overworld_effect_pool_capacity) <= 0x023DFFCC"
                in core_linker,
            "mounted surface query lost its read-only fixed-address bridge")


def verify_mount_action_helper_abi() -> None:
    """The split helpers retain bounded code and the Thumb callback bit."""
    action_base = 0x01FF8620
    linked_path = REPO / "build/overworld_mount_action_overlay_linked.o"
    object_path = REPO / "build/overworld_mount_overlay/overworld_mount_overlay.o"
    helper_path = REPO / "build/overworld_mount_action_overlay/overworld_mount_shared_helpers.o"
    packaged = (REPO / "build/output_overworld_mount_action_overlay.bin").read_bytes()
    resident = layout_symbols(linked_path, "arm-none-eabi-objdump")
    imports = layout_symbols(object_path, "arm-none-eabi-objdump")
    sections = elf_section_layout(linked_path)
    mount = (REPO / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text()
    helper_source = (REPO / "src/overworld_mount_action_overlay/overworld_mount_shared_helpers.c").read_text()
    linker = (REPO / "src/overworld_mount_action_overlay/linker.ld").read_text()
    ease_source = (REPO / "src/overworld_mount_action_overlay/overworld_mount_walk_ease.c").read_text()
    ease_object = REPO / "build/overworld_mount_action_overlay/overworld_mount_walk_ease.o"
    ease_imports = layout_symbols(ease_object, "arm-none-eabi-objdump")
    main_symbols = layout_symbols(REPO / "build/linked.o", "arm-none-eabi-objdump")
    ease_relocations = subprocess.check_output(
        ["arm-none-eabi-objdump", "-r", str(ease_object)], text=True)
    ease = resident.get("OverworldWalk_EaseMountedWalk")
    graphics_refresh = resident.get("OverworldWalk_RefreshMountedGraphics")
    shadow_refresh = resident.get("OverworldWalk_RefreshMountedShadow")
    require(
        ease is not None and ease[0] == 0x01FF8620
        and 0 < ease[1] <= 0x1E0 and ease[2:] == (".text", "F")
        and packaged[:ease[1]] == elf_bytes_at(linked_path, ease[0], ease[1])
        and main_symbols.get("__aeabi_uidiv", (None,))[0] == 0x023DEE4C
        and ease_imports.get("__aeabi_uidiv") == (0x023DEE4C, 0, "*ABS*", "F")
        and ".thumb_func\\n.thumb_set __aeabi_uidiv, 0x023DEE4C\\n" in ease_source
        and len(re.findall(r"R_ARM_THM_CALL\s+\*ABS\*0x23dee4c\b",
                           ease_relocations, re.IGNORECASE)) == 2,
        "mounted walk easing lost its resident Thumb division bridge")
    require(
        graphics_refresh is not None
        and graphics_refresh[0] == 0x01FF8700
        and 0 < graphics_refresh[1] <= 0x100
        and graphics_refresh[2:] == (".text", "F")
        and packaged[0xE0:0xE0 + graphics_refresh[1]]
            == elf_bytes_at(linked_path, graphics_refresh[0], graphics_refresh[1])
        and (0x021FA3E9).to_bytes(4, "little") in
            packaged[0xE0:0xE0 + graphics_refresh[1]]
        and shadow_refresh is not None
        and 0x01FF8700 < shadow_refresh[0] < 0x01FF8800
        and shadow_refresh[0] + shadow_refresh[1] <= 0x01FF8800
        and shadow_refresh[2:] == (".text", "F")
        and packaged[shadow_refresh[0] - 0x01FF8620:
                     shadow_refresh[0] - 0x01FF8620 + shadow_refresh[1]]
            == elf_bytes_at(linked_path, shadow_refresh[0], shadow_refresh[1])
        and "OverworldWalk_RefreshMountedShadow(mount);" in ease_source
        and "OverworldWalk_RefreshMountedGraphics(player, follower);" in
            (REPO / "src/overworld_mount_chain_overlay/overworld_mount_presentation.c").read_text()
        and re.search(
            r"follower->faceVec\[2\] = \(u32\)-offset;\s*"
            r"OverworldWalk_RefreshMountedGraphics\(player, follower\);",
            (REPO / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text()),
        "mounted graphics refresh lost its fixed entry or Thumb draw call")
    relocations = subprocess.check_output(
        ["arm-none-eabi-objdump", "-r", str(object_path)], text=True)
    helpers = (
        ("OverworldMount_IsLandingTileAllowed", 0x01FF9620,
         ".overworld_mount_landing_allowed", 0x40, 1),
        ("OverworldMount_ClassifyTeleportCandidate", 0x01FF9660,
         ".overworld_mount_teleport_classify", 0x60, 0),
        ("OverworldMount_ApplyWalkPolicyOutput", 0x01FF96C0,
         ".overworld_mount_walk_policy_output", 0xC0, 2),
        ("OverworldMount_GetOrdinaryDirection", 0x01FF9780,
         ".overworld_mount_ordinary_direction", 0x40, 1),
        ("OverworldMount_FinalizeIsPending", 0x01FF97C0,
         ".overworld_mount_finalize_pending", 0x20, 6),
        ("OverworldMount_ClearFollowerDecisionCooldown", 0x01FF97D0,
         ".overworld_mount_follower_cooldown", 0x10, 1),
        ("OverworldMount_UpdatePlayerBaseHeight", 0x01FF97E0,
         ".overworld_mount_player_base", 0x20, 1),
    )
    require("ASSERT(. <= 0x01FF95D0" in linker,
            "mounted action code can overlap the fixed helper tail")
    admission = resident.get("OverworldMount_ValidateConditionalAdmission")
    admission_address = 0x01FF95D0
    admission_section = ".overworld_mount_conditional_admission"
    admission_source = (REPO / "src/overworld_mount_action_overlay/overworld_mount_action_overlay.c").read_text()
    admission_header = (REPO / "include/overworld_mount_action_adapter.h").read_text()
    action_object = REPO / "build/overworld_mount_action_overlay/overworld_mount_action_overlay.o"
    action_imports = layout_symbols(action_object, "arm-none-eabi-objdump")
    action_relocations = subprocess.check_output(
        ["arm-none-eabi-objdump", "-r", str(action_object)], text=True)
    require(
        ".thumb_set memset, 0x023DEEA2" in admission_source
        and action_imports.get("memset") == (0x023DEEA2, 0, "*ABS*", "F")
        and not any(name.startswith("__memset_from_") for name in resident)
        and re.search(r"R_ARM_THM_CALL\s+\*ABS\*0x23deea2\b",
                      action_relocations, re.IGNORECASE),
        "mounted action memset lost its direct Thumb call")
    walk_corridor = resident.get("OverworldMountAction_WalkCorridor")
    object_corridor = action_imports.get("OverworldMountAction_WalkCorridor")
    require(walk_corridor is not None and object_corridor is not None,
            "mounted Walk corridor is missing")
    for name, target in (("OverworldWalk_DeltaX", 0x023BF59C),
                         ("OverworldWalk_DeltaY", 0x023BF5BE)):
        require(
            f".thumb_func\\n.thumb_set {name}, 0x{target:08X}\\n"
                in admission_source
            and action_imports.get(name) == (target, 0, "*ABS*", "F")
            and not any(symbol.startswith(f"__{name}_from_")
                        for symbol in resident),
            f"mounted Walk {name} lost its direct Thumb import")
        matches = re.findall(
            rf"([0-9a-fA-F]+)\s+(R_ARM_THM_CALL)\s+\*ABS\*0x{target:x}\b",
            action_relocations, re.IGNORECASE)
        require(len(matches) == 2,
                f"mounted Walk {name} lacks two direct Thumb callers")
        for offset, kind in matches:
            call_at = walk_corridor[0] + int(offset, 16) - object_corridor[0]
            packaged_offset = call_at - action_base
            fixed_import_call_contract(
                kind, elf_bytes_at(linked_path, call_at, 4),
                packaged[packaged_offset:packaged_offset + 4], call_at, target)
    require(admission is not None
            and admission[0] == admission_address
            and 0 < admission[1] <= 0x50
            and admission[2:] == (admission_section, "F")
            and any(kind == 1 and flags & 4 and location == admission_address
                    and admission[1] <= size <= 0x50
                    for kind, flags, location, size in sections)
            and packaged[admission_address - action_base:
                         admission_address - action_base + admission[1]]
                == elf_bytes_at(linked_path, admission_address, admission[1])
            and f'section("{admission_section}")' in admission_source
            and f"{admission_section} 0x{admission_address:08X}" in linker
            and "SIZEOF(.overworld_mount_conditional_admission) <= 0x50" in linker
            and "OVERWORLD_MOUNT_CONDITIONAL_ADMISSION_ENTRY_ADDR 0x01FF95D1" in admission_header,
            "mounted conditional-admission helper lost its fixed action ABI")
    for name, address, section, capacity, calls in helpers:
        symbol = resident.get(name)
        require(symbol is not None and symbol[0] == address
                and 0 < symbol[1] <= capacity
                and symbol[2:] == (section, "F")
                and any(kind == 1 and flags & 4 and location == address
                        and symbol[1] <= size <= capacity
                        for kind, flags, location, size in sections),
                f"{name} is not bounded code at its action-helper address")
        offset = address - action_base
        require(packaged[offset:offset + symbol[1]]
                == elf_bytes_at(linked_path, address, symbol[1]),
                f"{name} differs from packaged action bytes")
        require(f'section("{section}")' in helper_source
                and f"{section} 0x{address:08X}" in linker
                and f"SIZEOF({section}) <= 0x{capacity:X}" in linker,
                f"{name} lost its fixed-size action bridge")
        alias = address + (1 if calls == 0 else 0)
        require(imports.get(name) == (address, 0, "*ABS*", "F")
                and f".thumb_set {name}, 0x{alias:08X}" in mount,
                f"{name} lost its exact Thumb import")
        if calls:
            require(len(re.findall(
                rf"R_ARM_THM_CALL\s+\*ABS\*0x{address:x}\b",
                relocations, re.IGNORECASE)) == calls,
                f"{name} no longer has {calls} direct Thumb callers")
    callback = 0x01FF9661
    mount_text = elf_bytes_at(
        REPO / "build/overworld_mount_overlay_linked.o", OVERLAY_BASE, 0x1C40)
    require(mount_text.count(struct.pack("<I", callback)) == 1
            and "planCall.classify = OverworldMount_ClassifyTeleportCandidate;"
                in mount,
            "teleport classifier callback lost its Thumb entry bit")
    helper_imports = layout_symbols(helper_path, "arm-none-eabi-objdump")
    helper_relocations = subprocess.check_output(
        ["arm-none-eabi-objdump", "-r", str(helper_path)], text=True)
    for name, address in (
        ("OverworldMount_GetSurfaceId", 0x01FF9A70),
        ("OverworldMount_PlayCrashSound", 0x023BB740),
        ("OverworldActor_PlayStompSound", 0x023BA118),
    ):
        require(helper_imports.get(name) == (address, 0, "*ABS*", "F")
                and f".thumb_set {name}, 0x{address:08X}" in helper_source,
                f"{name} is not a direct Thumb import in action helpers")
        matches = re.findall(
            rf"([0-9a-fA-F]+)\s+(R_ARM_THM_CALL)\s+\*ABS\*0x{address:x}\b",
            helper_relocations, re.IGNORECASE)
        require(len(matches) == 1,
                f"{name} lacks one direct action-helper Thumb caller")
        section = (".overworld_mount_teleport_classify"
                   if name == "OverworldMount_GetSurfaceId"
                   else ".overworld_mount_walk_policy_output")
        call_at = next(item[1] for item in helpers if item[2] == section) + int(matches[0][0], 16)
        offset = call_at - action_base
        fixed_import_call_contract(
            matches[0][1], elf_bytes_at(linked_path, call_at, 4),
            packaged[offset:offset + 4], call_at, address)


def verify_fixed_direct_imports(packaged: bytes) -> None:
    linked_path = REPO / "build/overworld_mount_overlay_linked.o"
    object_path = REPO / "build/overworld_mount_overlay/overworld_mount_overlay.o"
    linked = layout_symbols(linked_path, "arm-none-eabi-objdump")
    original = layout_symbols(object_path, "arm-none-eabi-objdump")
    for name, target in FIXED_DIRECT_IMPORTS.items():
        imported = linked.get(name)
        require(original.get(name) == (target, 0, "*ABS*", "F")
                and imported is not None and imported[2] == "*ABS*"
                and imported[0] & ~1 == target,
                f"{name} changed its direct import or gained a local body")
        require(not any(symbol.startswith(f"__{name}_from_") for symbol in linked),
                f"{name} gained a redundant interworking veneer")
    origins = {}
    for name, symbol in original.items():
        if symbol[3] == "F" and symbol[1] > 0 and name in linked:
            origins.setdefault(symbol[2], set()).add(linked[name][0] - symbol[0])
    relocations = subprocess.check_output(
        ["arm-none-eabi-objdump", "-r", str(object_path)], text=True)
    targets = {target: name for name, target in FIXED_DIRECT_IMPORTS.items()}
    counts = dict.fromkeys(targets, 0)
    section = None
    for line in relocations.splitlines():
        heading = re.match(r"RELOCATION RECORDS FOR \[(.+)\]:", line)
        if heading:
            section = heading.group(1)
            continue
        call = re.match(r"([0-9a-fA-F]+)\s+(R_ARM_\w+)\s+\*ABS\*0x([0-9a-fA-F]+)$", line)
        if call is None or int(call.group(3), 16) not in targets:
            continue
        target = int(call.group(3), 16)
        require(len(origins.get(section, ())) == 1,
                f"cannot bind {section} call offsets to linked Mount code")
        address = next(iter(origins[section])) + int(call.group(1), 16)
        offset = address - OVERLAY_BASE
        fixed_import_call_contract(call.group(2), elf_bytes_at(linked_path, address, 4),
                                   packaged[offset:offset + 4], address, target)
        counts[target] += 1
    require(all(counts.values()), "a fixed direct import has no verified compiled caller")


def verify_chain_mount_imports() -> None:
    """The separately linked chain adapter must call current mount code."""
    mount = layout_symbols(REPO / "build/overworld_mount_overlay_linked.o",
                           "arm-none-eabi-objdump")
    chain = layout_symbols(REPO / "build/overworld_mount_chain_overlay_linked.o",
                           "arm-none-eabi-objdump")
    source = (REPO / "src/overworld_mount_chain_overlay/overworld_mount_chain_overlay.c").read_text()
    linker = (REPO / "src/overworld_mount_chain_overlay/linker.ld").read_text()
    for imported, implementation in (
        ("OverworldMount_ProcessPlayerControl", "OverworldMount_ProcessPlayerControl"),
        ("OverworldMount_TryStartCustomMotion", "OverworldMount_TryStartCustomMotion.constprop.0"),
        ("OverworldMount_GetInputDirection", "OverworldMount_GetInputDirection"),
    ):
        actual = mount.get(implementation)
        alias = chain.get(imported)
        require(actual is not None and alias is not None
                and actual[3] == "F" and actual[1] > 0
                and alias[0] == actual[0] | 1 and alias[2] == "*ABS*",
                f"mounted chain import {imported} misses its current mount body")
        address = f"0x{actual[0]:08X}"
        require(f".thumb_set {imported}, {address}" in source
                and f"{imported} = {address} | 1;" in linker,
                f"mounted chain import {imported} source/linker differs")


def custom_motion_source_contract(
    mount: str, actor: str, chain: str | None = None, action: str | None = None,
) -> None:
    """Bind mounted profile inputs and outputs through the owning planner ABI.

    Timing/flicker math belongs to the Actor planner, not the Mount adapter.
    This checks that route; it is not a runtime movement or timing test.
    """
    def compact(value: str) -> str:
        return re.sub(r"\s+", "", re.sub(r"/\*.*?\*/", "", value, flags=re.DOTALL))

    if action is None:
        action = (REPO / "src/overworld_mount_action_overlay/overworld_mount_action_overlay.c").read_text()
    start = compact(function_body(mount, "OverworldMount_TryStartCustomMotion"))
    hop_bridge = compact(function_body(mount, "OverworldMount_PlanHopTrajectory"))
    hop = compact(function_body(action, "OverworldMountAction_PlanHopTrajectory"))
    dispatch = compact(function_body(action, "OverworldMountActionAdapter_Dispatch"))
    teleport = compact(function_body(mount, "OverworldMount_RequestTeleportPlan"))
    service = compact(function_body(actor, "ActorSystem_RequestMotion"))
    for code, expected in (
        (start, "const OverworldWildBehaviorProfileData *lane = &sOverworldMountState.snapshot.profile;"),
        (start, "u8 rawLocomotion = lane->chillAction;"),
        (start, "OverworldMount_PlanHopTrajectory((u8)distance, &trajectory)"),
        (hop_bridge, "call.operation = OVERWORLD_MOUNT_ACTION_PLAN_HOP_TRAJECTORY;"),
        (hop_bridge, "call.action = distance;"),
        (hop_bridge, "call.state = &sOverworldMountState;"),
        (hop_bridge, "call.avatar = sOverworldMountState.fieldSystem->playerAvatar;"),
        (hop_bridge, "call.trajectory = trajectory;"),
        (hop_bridge, "return OVERWORLD_MOUNT_ACTION_ADAPTER_DISPATCH(&call);"),
        (dispatch, "call->result = OverworldMountAction_PlanHopTrajectory(call);"),
        (start, "if (!OverworldMount_RequestTeleportPlan(lane, player, direction, &teleportPlan)) { return FALSE; } actorMotionStarted = TRUE;"),
        (start, "frames = sOverworldMountState.walkEndState == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP ? (u32)lane->hopTime << 1 : trajectory & 0xFFFF;"),
        (start, "sOverworldMountState.motionArcHeightQ4 = (u8)(trajectory >> 16);"),
        (start, "frames = teleportPlan.duration;"),
        (start, "sOverworldMountState.motionTargetBaseY = teleportPlan.targetBaseY;"),
        (start, "sOverworldMountState.motionTargetX = teleportPlan.targetX;"),
        (start, "sOverworldMountState.motionTargetY = teleportPlan.targetY;"),
        (start, "sOverworldMountState.motionArcHeightQ4 = teleportPlan.pauseFrames;"),
        (start, "sOverworldMountState.motionFlicker = (u8)((teleportPlan.visibilityPolicy == OVERWORLD_MOTION_VISIBILITY_FLICKER) << 4);"),
        (start, "if (!actorMotionStarted && !OverworldMount_BeginSharedMotion(FALSE))"),
        (hop, "hopPlan.operation = OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY;"),
        (hop, "hopPlan.lane = &call->state->snapshot.profile;"),
        (hop, "hopPlan.object = call->avatar->mapObject;"),
        (hop, "hopPlan.distance = call->action;"),
        (hop, "request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_HOP;"),
        (hop, "request.hopPlan = &hopPlan;"),
        (hop, "*call->trajectory = hopPlan.trajectory;"),
        (teleport, "planCall.lane = lane;"),
        (teleport, "planCall.directions = &direction;"),
        (teleport, "planCall.classify = OverworldMount_ClassifyTeleportCandidate;"),
        (teleport, "planCall.targetMode = OVERWORLD_ACTOR_TELEPORT_TARGET_DIRECTIONAL;"),
        (teleport, "planCall.directionCount = 1;"),
        (teleport, "planCall.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_PLAYER;"),
        (teleport, "request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_TELEPORT;"),
        (teleport, "request.actorSlot = OW_WILD_FOLLOWER_SLOT;"),
        (teleport, "request.fieldEpoch = OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext());"),
        (teleport, "request.plan = plan;"),
        (teleport, "request.teleportPlan = &planCall;"),
        (teleport, "sOverworldMountState.motionIdentity = request.motionIdentity;"),
        (service, "call->decision = OverworldActorHopPlanner_Plan(call->hopPlan);"),
        (service, "call->decision = OverworldActorTeleportPlanner_Plan(call); if (call->decision != OVERWORLD_MOTION_DECISION_ACCEPTED) { goto motion_rejected; } goto plan_accepted;"),
    ):
        require(compact(expected) in code,
                f"mounted custom motion lost its owner-profile route: {expected}")
    for code in (hop, teleport):
        for expected in (
            "request.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;",
            "request.size = sizeof(request);",
            "if (OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&request) != OVERWORLD_ACTOR_RESULT_OK || request.decision != OVERWORLD_MOTION_DECISION_ACCEPTED) { return FALSE; }",
        ):
            require(compact(expected) in code, "mounted planner does not validate the Actor Motion ABI result")
    require("OVERWORLD_WILD_HOP_TRAJECTORY_ENTRY" not in mount,
            "mounted Hop restored the retired callback entry")
    if chain is None:
        chain = (REPO / "src/overworld_mount_chain_overlay/overworld_mount_chain_overlay.c").read_text()
    reset = compact(function_body(chain, "OverworldMount_ResetMomentum"))
    require(reset == compact("const OverworldMountRuntimeState *state = (const OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR; if (state->walkEndState != OVERWORLD_MOUNT_WALK_END_CHAIN_HOP || !state->presentationAttached) { (void)OverworldActorPolicy_MountCommand(OVERWORLD_ACTOR_WALK_POLICY_RESET, NULL); }"),
            "mounted momentum reset must preserve only an attached chain Hop")


def custom_motion_source_fixtures(mount: str, actor: str) -> None:
    custom_motion_source_contract(mount, actor)
    chain = (REPO / "src/overworld_mount_chain_overlay/overworld_mount_chain_overlay.c").read_text()
    action = (REPO / "src/overworld_mount_action_overlay/overworld_mount_action_overlay.c").read_text()
    mutations = (
        ("mount", "&sOverworldMountState.snapshot.profile;", "NULL;"),
        ("action", "hopPlan.lane = &call->state->snapshot.profile;", "hopPlan.lane = NULL;"),
        ("mount", "call.operation = OVERWORLD_MOUNT_ACTION_PLAN_HOP_TRAJECTORY;", "call.operation = OVERWORLD_MOUNT_ACTION_WALK_CORRIDOR;"),
        ("mount", "planCall.lane = lane;", "planCall.lane = NULL;"),
        ("action", "request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_HOP;", "request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST;"),
        ("mount", "request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_TELEPORT;", "request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST;"),
        ("action", "|| request.decision != OVERWORLD_MOTION_DECISION_ACCEPTED", "|| FALSE"),
        ("mount", "frames = teleportPlan.duration;", "frames = 1;"),
        ("mount", "motionArcHeightQ4 = teleportPlan.pauseFrames;", "motionArcHeightQ4 = 0;"),
        ("mount", "== OVERWORLD_MOTION_VISIBILITY_FLICKER) << 4", "!= OVERWORLD_MOTION_VISIBILITY_FLICKER) << 4"),
        ("mount", "!actorMotionStarted && !OverworldMount_BeginSharedMotion(FALSE)", "!OverworldMount_BeginSharedMotion(FALSE)"),
        ("mount", "sOverworldMountState.motionIdentity = request.motionIdentity;", "sOverworldMountState.motionIdentity = 0;"),
        ("chain", "OVERWORLD_ACTOR_WALK_POLICY_RESET, NULL", "OVERWORLD_ACTOR_WALK_POLICY_PUBLISH_EFFECT, NULL"),
        ("actor", "OverworldActorHopPlanner_Plan(call->hopPlan)", "OverworldActorHopPlanner_Plan(NULL)"),
        ("actor", "OverworldActorTeleportPlanner_Plan(call)", "OverworldActorTeleportPlanner_Plan(NULL)"),
    )
    for owner, old, new in mutations:
        source = {"mount": mount, "actor": actor, "chain": chain, "action": action}[owner]
        require(old in source, f"mounted custom-motion negative control no longer applies: {old}")
        mutant = source.replace(old, new)
        try:
            custom_motion_source_contract(mutant if owner == "mount" else mount,
                                          mutant if owner == "actor" else actor,
                                          mutant if owner == "chain" else chain,
                                          mutant if owner == "action" else action)
        except SystemExit:
            pass
        else:
            require(False, f"mounted custom-motion negative control passed: {old}")


def mounted_chain_source_contract(mount: str, actor: str, walk: str, runtime: str) -> None:
    """Mounted Walk commits the same chain receipt as Wild Walk."""
    commit = function_body(actor, "ActorSystem_TryAcknowledgeMotionCommit")
    require(re.search(
        r"if \(motion->plan.commitPolicy == OVERWORLD_MOTION_COMMIT_NORMAL\s*"
        r"&& policy->pendingStep == OVERWORLD_ACTOR_WALK_PENDING_NONE\s*"
        r"&& \(walkPolicy == NULL\s*\|\| \(walkPolicy->stepFlags & "
        r"OVERWORLD_ACTOR_WALK_STEP_SKID\) == 0\)\) \{\s*"
        r"policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_CHAIN;\s*\}",
        commit) is not None,
        "mounted logical commit does not enqueue a chain action")
    mounted_finish = function_body(actor, "ActorSystem_FinishMountedWalk")
    require("OverworldWalk_SkidTiles(policy->lastWalkTime)" in mounted_finish,
            "mounted skid distance ignores the last displayed Walk time")
    mounted_input = function_body(walk, "OverworldWalk_FilterMountedInput")
    mounted_commit = function_body(mount, "OverworldMount_CommitWalkBoundary")
    require("ActorSystem_Zero(output, sizeof(*output));" in mounted_finish
            and "PokemonMoveHistory_OverlayMemset(&call, 0, sizeof(call));" in mounted_input
            and "memset(&output, 0, sizeof(output));" in mounted_commit
            and "output.flags = OVERWORLD_ACTOR_WALK_POLICY_FLAG_WALK_ACCEPTED" in mounted_commit
            and "| OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED;" in mounted_commit,
            "mounted Walk does not enable chain handling")
    chain_adapter = (REPO / "src/overworld_mount_chain_overlay/overworld_mount_chain_overlay.c").read_text()
    require("OVERWORLD_ACTOR_WALK_POLICY_CHAIN_COMMIT" in chain_adapter
            and "OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING" in chain_adapter
            and "Chain_StartForwardHop" in chain_adapter
            and "OverworldMount_ChainControl(" in mount,
            "mounted chain adapter does not run the composed action")
    reduce_chain = function_body(runtime, "OverworldActorWalkPolicy_ReduceChain")
    require(re.search(
        r"if \(\(call->flags & OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED\) == 0"
        r".*?\{\s*policy->chainStepsRemaining = 0;\s*"
        r"policy->deferredChainPauseAction = 0;\s*return;\s*\}",
        reduce_chain, re.DOTALL) is not None,
        "shared policy does not clear disabled chain state")


def mounted_chain_source_fixtures(mount: str, actor: str, walk: str, runtime: str) -> None:
    sources = [mount, actor, walk, runtime]
    mounted_chain_source_contract(*sources)
    for index, old, new in (
        (1, "policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_CHAIN;",
         "policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_NONE;"),
        (0, "| OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED;",
         ";"),
        (1, "ActorSystem_Zero(output, sizeof(*output));", "/* missing initialization */"),
        (3, "if ((call->flags & OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED) == 0",
         "if ((call->flags & OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED) != 0"),
    ):
        require(old in sources[index], f"mounted chain negative control no longer applies: {old}")
        mutant = list(sources)
        mutant[index] = mutant[index].replace(old, new)
        try:
            mounted_chain_source_contract(*mutant)
        except SystemExit:
            pass
        else:
            require(False, f"mounted chain negative control passed: {old}")


def mounted_diagonal_admission_contract(source: str) -> None:
    body = function_body(source, "OverworldMount_TryStartWalkFromInput")
    body = re.sub(r"/\*.*?\*/|//[^\n]*", "", body, flags=re.DOTALL)
    compact = re.sub(r"\s+", "", body)
    guard = (
        "if(OverworldMount_CanControl(avatar)"
        "&&sOverworldMountState.snapshot.profile.chillAction==OW_WILD_BEHAVIOR_LOCOMOTION_WALK"
        "&&((sOverworldMountState.snapshot.profile.walkOptions"
        "&OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION)==0"
        "||!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL("
        "sOverworldMountState.snapshot.profile.hopAllowNonCardinal))"
        "&&OverworldWalk_ResolveMountedDiagonal("
        "&sOverworldMountState,avatar,newKeys,heldKeys)!=0){returnTRUE;}"
    )
    tail = (
        "OverworldMount_FilterMovementInput(avatar,newKeys,heldKeys);"
        "returnOverworldMount_TryHandleDiagonalWalk("
        "avatar,*newKeys,*heldKeys,advanceFirstFrame);"
    )
    require(compact == guard + tail,
            "mounted diagonal admission must consume rejected unlocked input before policy, "
            "preserve locked direction, and retain cardinal-only normalization")


def mounted_diagonal_admission_fixtures(source: str) -> None:
    mounted_diagonal_admission_contract(source)
    body = function_body(source, "OverworldMount_TryStartWalkFromInput")
    filter_call = "OverworldMount_FilterMovementInput(avatar, newKeys, heldKeys);"
    mutants = (
        filter_call + body.replace(filter_call, "", 1),
        body.replace("OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION) == 0",
                     "OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION) != 0", 1),
        re.sub(r"\(sOverworldMountState\.snapshot\.profile\.walkOptions\s*"
               r"& OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION\) == 0",
               "TRUE", body, count=1),
        body.replace("return TRUE;", "return FALSE;", 1),
        body.replace("!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(",
                     "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(", 1),
    )
    for mutant in mutants:
        require(mutant != body, "mounted admission negative control no longer applies")
        try:
            mounted_diagonal_admission_contract(source.replace(body, mutant, 1))
        except SystemExit:
            pass
        else:
            require(False, "mounted admission negative control passed")


def field_boundary_source_fixtures(source: str) -> None:
    def contract(value: str) -> None:
        require("ASSERT(ADDR(.bss) + SIZEOF(.bss) <= 0x023CCFD8" in value,
                "field overlay code and BSS boundary is not enforced by the linker")

    contract(source)
    for mutant in (
        source.replace("ASSERT(ADDR(.bss) + SIZEOF(.bss)",
                       "ASSERT(ADDR(.data) + SIZEOF(.data)"),
        source.replace("<= 0x023CCFD8", "<= 0x023CCFDC"),
    ):
        require(mutant != source, "field boundary negative control no longer applies")
        try:
            contract(mutant)
        except SystemExit:
            pass
        else:
            require(False, "field boundary negative control passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=REPO / "test.nds")
    parser.add_argument("--imports-source-only", action="store_true",
                        help="check fixed imports and their negative controls")
    parser.add_argument("--surface-helper-only", action="store_true",
                        help="check resident mount helpers and direct imports")
    parser.add_argument("--custom-motion-source-only", action="store_true",
                        help="check only the mounted Actor planner route and its negative controls")
    args = parser.parse_args()
    fixed_import_source_fixtures((REPO /
        "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text())
    if args.surface_helper_only:
        verify_mount_surface_helper_abi()
        verify_mount_action_helper_abi()
        print("Mount resident helpers: layout and direct Thumb calls passed")
        return
    if args.imports_source_only:
        print("Mount fixed imports: source and six negative controls passed")
        return
    if args.custom_motion_source_only:
        custom_motion_source_fixtures(
            (REPO / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text(),
            (REPO / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c").read_text())
        print("Mount Actor planner route: source and 15 negative controls passed")
        return

    rom = args.rom.read_bytes()
    fat_offset, fat_size = struct.unpack_from("<2I", rom, 0x48)
    y9_offset, y9_size = struct.unpack_from("<2I", rom, 0x50)
    require(y9_size >= (OVERLAY_ID + 1) * 0x20, "overlay 157 row is missing")
    require(fat_size >= (OVERLAY_ID + 1) * 8, "overlay 157 FAT row is missing")

    row = struct.unpack_from("<8I", rom, y9_offset + OVERLAY_ID * 0x20)
    overlay_id, load_address, file_size, bss_size, init_start, init_end, file_id, flags = row
    require(overlay_id == OVERLAY_ID, "overlay ID differs")
    require(load_address == OVERLAY_BASE, "load address differs")
    require(file_id == OVERLAY_ID, "file ID differs")
    require(init_start == 0 and init_end == 0 and flags == 0, "metadata differs")
    require(
        file_size > 0
        and bss_size > 0
        and load_address + file_size + bss_size <= OVERLAY_LIMIT,
        "code and state exceed the dedicated 4 KiB reservation",
    )

    field_row = struct.unpack_from(
        "<8I", rom, y9_offset + FIELD_OVERLAY_ID * 0x20
    )
    field_overlay_id, field_load, field_size, field_bss = field_row[:4]
    require(field_overlay_id == FIELD_OVERLAY_ID, "field overlay ID differs")
    require(
        field_load + field_size + field_bss <= FIELD_OVERLAY_LIMIT,
        "field overlay overlaps the overworld wild overlay prefix",
    )

    file_start, file_end = struct.unpack_from("<2I", rom, fat_offset + file_id * 8)
    require(file_end - file_start == file_size, "FAT size differs from y9")
    packaged = rom[file_start:file_end]
    field_elf = REPO / "build/field_linked.o"
    field_symbols = layout_symbols(field_elf, "arm-none-eabi-objdump")
    field_host = field_symbols.get("OverworldMount_ProcessFieldInput")
    require(
        field_host is not None and field_host[0] == 0x023CCE98
        and 0 < field_host[1] <= 0x100
        and field_host[2:] == (".overworld_mount_field_input_host", "F")
        and any(kind == 1 and flags & 4 and address == 0x023CCE98
                and size >= field_host[1]
                for kind, flags, address, size in elf_section_layout(field_elf)),
        "mount field-input host is not code at its fixed private entry",
    )
    field_start, field_end = struct.unpack_from(
        "<2I", rom, fat_offset + field_row[6] * 8)
    field_packaged = rom[field_start:field_end]
    field_layout = current_field_overlay_metadata()
    require(
        len(field_packaged) == field_size
        and (field_load, field_size, field_bss) == field_layout[:3]
        and field_packaged == (REPO / "build/output_field.bin").read_bytes()
        and field_packaged[0x023CCE98 - field_load:
            0x023CCE98 - field_load + field_host[1]]
            == elf_bytes_at(field_elf, 0x023CCE98, field_host[1])
        and struct.pack("<I", 0x023CCE99) in packaged[
            FIELD_INPUT_WRAPPER - OVERLAY_BASE:
            FIELD_INPUT_WRAPPER - OVERLAY_BASE + 0x60],
        "mount field-input host bytes, BSS boundary or Thumb dispatch differ",
    )
    built = (REPO / "build/output_overworld_mount_overlay.bin").read_bytes()
    require(packaged == built, "packaged overlay differs from linked output")
    verify_fixed_direct_imports(packaged)
    verify_mount_surface_helper_abi()
    verify_mount_action_helper_abi()
    verify_chain_mount_imports()
    require(
        struct.pack("<I", 0x023BF400) not in built,
        "mounted input still embeds the retired Walk table base",
    )
    mount_nm = subprocess.run(
        [
            "arm-none-eabi-nm",
            "-n",
            str(REPO / "build/overworld_mount_overlay_linked.o"),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    require(
        "__OverworldWildRuntime_ApplyMotionBoundary_from_thumb" not in mount_nm,
        "Actor Motion boundary uses an ARM-mode interworking thunk",
    )
    runtime_wrapper = None
    for line in mount_nm.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == RUNTIME_ACK_WRAPPER_NAME:
            runtime_wrapper = (int(parts[0], 16), parts[1])
            break
    require(runtime_wrapper is not None, "runtime acknowledgement wrapper is missing")
    runtime_wrapper_address, runtime_wrapper_type = runtime_wrapper
    require(runtime_wrapper_type in ("T", "t"), "runtime wrapper is not Thumb")
    runtime_wrapper_offset = runtime_wrapper_address - OVERLAY_BASE
    require(
        packaged[runtime_wrapper_offset:runtime_wrapper_offset + 16]
            == bytes((
                0x08, 0xB4, 0x02, 0x4B, 0x9C, 0x46, 0x08, 0xBC,
                0x60, 0x47, 0xC0, 0x46,
            )) + RUNTIME_ACK_TARGET.to_bytes(4, "little"),
        "runtime acknowledgement wrapper does not preserve r3 and tail-call "
        "the Thumb entry",
    )
    require(
        struct.unpack_from(
            "<I",
            packaged,
            PLAYER_STEP_RESIDENT_LITERAL - OVERLAY_BASE,
        )[0]
        == PLAYER_STEP_RESIDENT_HANDLER,
        "player-step bridge targets the wrong resident handler",
    )

    player_step_overlay_id = 129
    player_step_row = struct.unpack_from(
        "<8I", rom, y9_offset + player_step_overlay_id * 0x20)
    player_step_load = player_step_row[1]
    player_step_file_id = player_step_row[6]
    player_step_start, player_step_end = struct.unpack_from(
        "<2I", rom, fat_offset + player_step_file_id * 8)
    player_step_overlay = rom[player_step_start:player_step_end]
    require(
        decode_thumb_bl(
            player_step_overlay,
            player_step_load,
            0x023DD548,
        ) == PLAYER_STEP_WRAPPER,
        "canonical player-step call does not target the mount bridge",
    )
    object_row = struct.unpack_from(
        "<8I", rom, y9_offset + FIELD_OBJECT_OVERLAY_ID * 0x20
    )
    object_load = object_row[1]
    object_file_id = object_row[6]
    object_start, object_end = struct.unpack_from(
        "<2I", rom, fat_offset + object_file_id * 8
    )
    object_overlay = rom[object_start:object_end]
    require(
        decode_thumb_bl(
            object_overlay,
            object_load,
            MOUNT_FACING_CALL_SITE,
        ) == MOUNT_FACING_WRAPPER,
        "mounted follower facing vector is overwritten after synchronization",
    )

    entry_offset = OVERLAY_ENTRY - OVERLAY_BASE
    magic, version, size, *callbacks = struct.unpack_from(
        "<IHH6I", packaged, entry_offset)
    require(magic == ENTRY_MAGIC, "entry magic differs")
    require(version == ENTRY_VERSION, "entry version differs")
    require(size == ENTRY_SIZE, "entry size differs")
    require(
        all((callback & 1) != 0 for callback in callbacks),
        "entry contains a non-Thumb callback",
    )
    require(
        all(OVERLAY_BASE <= (callback & ~1) < OVERLAY_BASE + file_size
            for callback in callbacks),
        "entry callback lies outside the mount overlay",
    )
    require(
        callbacks[-1] & ~1 != PLAYER_CONTROL_WRAPPER
        and callbacks[-1] & ~1 != CRASH_SOUND_WRAPPER,
        "frame callback aliases a fixed player-control wrapper",
    )
    toggle_wrapper = packaged[
        TOGGLE_LATCH_WRAPPER - OVERLAY_BASE:
        TOGGLE_LATCH_WRAPPER - OVERLAY_BASE + 0x1C
    ]
    require(
        callbacks[-1] == TOGGLE_LATCH_WRAPPER + 1
        and toggle_wrapper[:0x14]
            == bytes.fromhex(
                "01 b4 04 4b 18 78 80 00 02 43 c0 46 c0 46 01 bc "
                "01 4b 18 47"
            )
        and struct.unpack_from("<I", toggle_wrapper, 0x14)[0]
            == TOGGLE_LATCH_ADDR
        and (
            OVERLAY_BASE
            <= (struct.unpack_from("<I", toggle_wrapper, 0x18)[0] & ~1)
            < OVERLAY_BASE + file_size
        ),
        "missed Select edges do not route through the resident mount latch",
    )

    arm9_offset, arm9_entry, arm9_load, arm9_size = struct.unpack_from(
        "<4I", rom, 0x20
    )
    del arm9_entry
    arm9 = rom[arm9_offset:arm9_offset + arm9_size]
    require(len(arm9) == arm9_size, "ARM9 image is truncated")
    for site in MOVE_CONTROL_CALL_SITES:
        require(
            decode_thumb_bl(arm9, arm9_load, site) == PLAYER_CONTROL_WRAPPER,
            f"player-control call at 0x{site:08X} does not target the mount wrapper",
        )
    require(
        decode_thumb_bl(arm9, arm9_load, FIELD_INPUT_CALL_SITE)
            == FIELD_INPUT_WRAPPER,
        "field-input processing does not target the mounted-Hop transition gate",
    )
    for site in CRASH_SOUND_CALL_SITES:
        require(
            decode_thumb_bl(arm9, arm9_load, site) == CRASH_SOUND_WRAPPER,
            f"crash-sound call at 0x{site:08X} does not target the mount wrapper",
        )
    hook_offset = HELD_MOVEMENT_HOOK - arm9_load
    require(
        arm9[hook_offset:hook_offset + 4] == b"\x00\x4b\x18\x47",
        "held-movement sink is not the bounded r3 trampoline",
    )
    hook_target = struct.unpack_from("<I", arm9, hook_offset + 4)[0]
    require(
        hook_target & 1 != 0
        and OVERLAY_BASE <= (hook_target & ~1) < OVERLAY_BASE + file_size,
        "held-movement hook target is outside the resident mount overlay",
    )

    save_constants = (REPO / "include/constants/save.h").read_text()
    require(
        re.search(r"^#define NEW_HEAP3_SIZE 0x106730$", save_constants, re.MULTILINE)
        is not None,
        "heap 3 does not reserve the actor and mount blocks",
    )
    startup = (REPO / "armips/asm/syntheticoverlay.s").read_text()
    require(
        "ResidentOverlayIds:" in startup
        and ".byte 158, 157, 159, 160, 155, 153, 156" in startup
        and "mov r5, #7" in startup
        and "bl LoadResidentOverlay" in startup,
        "actor, mount, and action overlays are not boot-loaded before runtime use",
    )
    field_service = (REPO / "src/field/map_teleport.c").read_text()
    require(
        "PAD_BUTTON_R | PAD_BUTTON_Y | PAD_BUTTON_SELECT" in field_service,
        "Select does not wake the resident overworld field service",
    )
    selector_source = (
        REPO
        / "src/overworld_follower_selector_overlay/follower_selector_input.c"
    ).read_text()
    require(
        "OverworldFollowerSelector_IsYReleasePending()" not in selector_source
        and "OverworldFollowerSelector_IsYPressPending() || mountSelection"
            in selector_source
        and "OVERWORLD_FOLLOWER_SELECTION_REQUEST_PENDING"
            in selector_source,
        "follower selection is not confirmed by a distinct second Y press",
    )
    require(
        "OVERWORLD_FOLLOWER_TRANSITION_QUEUE->reserved ="
            in selector_source
        and "OVERWORLD_FOLLOWER_SELECTION_REQUEST_MOUNT"
            in selector_source
        and "sFollowerRecall.selectorHighlightedSlot" in selector_source,
        "Select does not publish the highlighted mount request",
    )
    require(
        re.search(
            r"OverworldFollowerSelector_ClearYPressPending\(\);\s*"
            r"while \(sFollowerSelectorInputState\s*"
            r"== FOLLOWER_SELECTOR_INPUT_PREPARING\) \{\s*"
            r"(?:/\*.*?\*/\s*)?"
            r"OverworldFollowerSelectorInput_Task\(\s*"
            r"sFollowerSelectorTask,\s*fieldSystem\s*\);",
            selector_source,
            re.DOTALL,
        ) is not None,
        "active Y menu still waits for staged preload frames",
    )

    spawns = (
        REPO
        / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
    ).read_text()
    resident_spawns = (REPO / "src/overworld_wild_spawns.c").read_text()
    runtime_source = (
        REPO
        / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
    ).read_text()
    field_mount_source = (REPO / "src/field/map_teleport.c").read_text() + (
        REPO / "src/overworld_mount_chain_overlay/overworld_mount_presentation.c"
    ).read_text()
    field_stream_source = (
        REPO
        / "src/pokemon_move_history_overlay/overworld_field_terrain_stream.c"
    ).read_text()
    actor_source = (
        REPO
        / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c"
    ).read_text()
    require(
        re.search(
            r"view = \*current;\s*"
            r"OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->fillActorView\(\s*"
            r"fieldSystem, actorSource, slot, &view\s*\);",
            actor_source,
        ) is not None
        and re.search(
            r"view->active = spawn->active;\s*"
            r"if \(!view->active\) \{\s*return;\s*\}.*?"
            r"if \(view->motionPhase != OVERWORLD_MOTION_PHASE_IDLE\s*"
            r"&& view->motionPhase != OVERWORLD_MOTION_PHASE_CANCELED\) "
            r"\{.*?\} else \{.*?"
            r"view->logicalX = \(s16\)object->xCurr;.*?"
            r"view->logicalY = \(s16\)object->yCurr;",
            runtime_source,
            re.DOTALL,
        ) is not None,
        "active mounted motion can lose actor-owned logical path advances",
    )
    require(
        "OverworldWildSpawns_BeginMountSelectedFollower" in spawns
        and "OverworldWildSpawns_ResolveBehaviorProfileForContext" in spawns
        and "OVERWORLD_MOUNT_OVERLAY_ENTRY->begin" in spawns,
        "selected-follower profile bridge is missing",
    )
    mount_begin = spawns[
        spawns.rfind("OverworldWildSpawns_BeginMountSelectedFollower("):
        spawns.find("static u8 OverworldWildSpawns_GetBehaviorHopSpinSpeed(")]
    mounted_profile_snapshot = (
        re.search(
            r"conditionalAdmission = OVERWORLD_MOUNT_CONDITIONAL_ADMISSION\(\s*"
            r"conditions,\s*&role\.context\s*\);.*?"
            r"conditionalAdmission\s*==\s*"
            r"OVERWORLD_MOUNT_CONDITIONAL_ADMISSION_INVALID.*?"
            r"ResolveBehaviorProfileForContext\(\s*&role\.context,\s*"
            r"1u << OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_MOUNTED,\s*"
            r"conditionalAdmission,\s*&resolution\s*\)",
            mount_begin,
            re.DOTALL,
        )
        is not None
        and "GetBehaviorProfileAndPrimitivesForSlot" not in mount_begin
        and "1u << OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER" not in mount_begin
        and re.search(
            r"if \(spawn != NULL && spawn->active\).*?"
            r"terrain = spawn->terrain;",
            spawns,
            re.DOTALL,
        )
        is not None
        and re.search(
            r"role\.policyTransaction\.next\.behaviorFingerprint\s*=\s*"
            r"resolution\.fingerprint;.*?"
            r"role\.policyTransaction\.next\.matchedLayerMask\s*=\s*"
            r"resolution\.matchedClassRuleMask\s*"
            r"\| resolution\.appliedOverrideMask;.*?"
            r"OVERWORLD_MOUNT_OVERLAY_ENTRY->begin\(\s*"
            r"fieldSystem,\s*&binding,\s*&resolution\.profile,\s*"
            r"\(const OverworldWildSurfaceCatalog \*\)"
            r"behaviorData->surfaceModels,\s*"
            r"&role\.policyTransaction\)\)\s*\{\s*"
            r"return FALSE;\s*\}.*?"
            r"OverworldWildSpawns_ResetSlotMovementCommand\(\s*"
            r"state,\s*OW_WILD_FOLLOWER_SLOT,\s*TRUE\s*\);",
            mount_begin,
            re.DOTALL,
        )
        is not None
        and "OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_MOUNTED" in spawns
        and re.search(
            r"slot == OW_WILD_FOLLOWER_SLOT\s*"
            r"&& OverworldWildSpawns_MountIsActive\(\)\) \{\s*return 0;",
            spawns,
        )
        is not None
    )
    require(
        mounted_profile_snapshot,
        "mount does not resolve, consume, and bind the Mounted override",
    )
    mount_source = (
        REPO
        / "src/overworld_mount_overlay/overworld_mount_overlay.c"
    ).read_text()
    mount_linker = (
        REPO / "src/overworld_mount_overlay/linker.ld"
    ).read_text()
    mount_header = (REPO / "include/overworld_mount.h").read_text()
    mount_internal = (
        REPO / "include/overworld_mount_internal.h"
    ).read_text()
    actor_internal = (
        REPO / "include/overworld_actor_system_internal.h"
    ).read_text()
    actor_linker = (
        REPO / "src/overworld_actor_system_overlay/linker.ld"
    ).read_text()
    runtime_linker = (
        REPO / "src/overworld_wild_runtime_overlay/linker.ld"
    ).read_text()
    overworld_patch = (REPO / "armips/asm/overworlds.s").read_text()
    walk_module_source = (
        REPO
        / "src/pokemon_move_history_overlay/overworld_walk_module.c"
    ).read_text()
    walk_module_linker = (
        REPO / "src/pokemon_move_history_overlay/linker.ld"
    ).read_text()
    root_linker = (REPO / "rom.ld").read_text()
    mount_runtime_source = (
        mount_source + "\n" + walk_module_source + "\n" + runtime_source
    )
    issue_held_movement = re.search(
        r"void\s+OverworldMount_IssueHeldMovement\([^;]*?\)\s*"
        r"\{.*?^\}",
        mount_source,
        re.DOTALL | re.MULTILINE,
    )
    diagonal_walk = re.search(
        r"OverworldMount_TryHandleDiagonalWalk\([^;]*?\)\s*"
        r"\{.*?^\}",
        mount_source,
        re.DOTALL | re.MULTILINE,
    )
    mounted_flat_walk = re.search(
        r"OverworldWalk_StartMountedFlat\([^;]*?\)\s*"
        r"\{.*?^\}",
        walk_module_source,
        re.DOTALL | re.MULTILINE,
    )
    apply_walk_policy = re.search(
        r"OverworldMount_ApplyWalkPolicy\([^;]*?\)\s*"
        r"\{.*?^\}",
        mount_source,
        re.DOTALL | re.MULTILINE,
    )
    get_input_direction = function_body(
        mount_source,
        "OverworldMount_GetInputDirection",
    )
    filter_mounted_input = function_body(
        walk_module_source,
        "OverworldWalk_FilterMountedInput",
    )
    finish_mounted_walk = function_body(
        actor_source,
        "ActorSystem_FinishMountedWalk",
    )
    require(
        apply_walk_policy is not None
        and "->finishMountedWalk(" in apply_walk_policy.group(0)
        and "OverworldMount_ApplyWalkPolicyOutput(" in apply_walk_policy.group(0)
        and "output.decision != OVERWORLD_ACTOR_WALK_POLICY_IGNORED"
            in apply_walk_policy.group(0)
        and "OverworldWalkMountCall" not in mount_source
        and "OVERWORLD_WALK_MODULE_ENTRY" not in mount_source
        and "OVERWORLD_WALK_MOUNT_MODULE_ENTRY" not in mount_source,
        "mounted Walk still uses a retired table or remote completion reducer",
    )
    require(
        "OverworldWalk_DeltaX = 0x023BF59C | 1;" in mount_linker
        and "OverworldWalk_DeltaY = 0x023BF5BE | 1;" in mount_linker
        and "OverworldWalk_DirectionFromKeys = 0x023BF534 | 1;"
            in mount_linker
        and "OverworldWalk_StrictDiagonalAllowed = 0x023BF6CE | 1;"
            in mount_linker
        and "OverworldWalk_DiagonalFacing = 0x023BF74E | 1;"
            in mount_linker
        and "OverworldWalk_ResolveMountedDiagonal = 0x023BF780 | 1;"
            in mount_linker
        and "OverworldWalk_StartMountedFlat = 0x023BF840 | 1;"
            in mount_linker
        and "OverworldWalk_FilterMountedInput = 0x023BF9A0 | 1;"
            in mount_linker
        and "OverworldWalk_DeltaX = 0x023BF59C | 1;" in root_linker
        and "OverworldWalk_DeltaY = 0x023BF5BE | 1;" in root_linker,
        "mounted Walk direct Thumb helper imports are incomplete",
    )
    require(
        "0x023BF535" in get_input_direction
        and "ldr r3, [r3" not in get_input_direction
        and "0x023BF400" not in mount_source,
        "mounted input still dereferences the retired Walk table",
    )
    require(
        "sOverworldMountState.snapshot.profile = profile->owner;"
            in mount_source
        and "call.lane = &state->snapshot.profile;" in walk_module_source
        and "call->lane->chillSpeed" in runtime_source
        and "call->lane->tilesToAccelerate" in runtime_source
        and "call->lane->maxWalkSpeed" in runtime_source
        and "call->lane->walkOptions" in runtime_source,
        "mounted Walk does not consume the fully resolved owner profile",
    )
    require(
        "call.stepDirection = WALK_DIRECTION_NONE;" in walk_module_source
        and "call.facingDirection = WALK_DIRECTION_NONE;"
            in walk_module_source
        and re.search(
            r"call\.stepDirection != WALK_DIRECTION_NONE\s*"
            r"&& call\.decision == OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP",
            walk_module_source,
        ) is not None,
        "mounted input can force a movement without an accepted Walk proposal",
    )
    require(
        "OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX" in filter_mounted_input
        and "call.reserved[0]" in filter_mounted_input
        and "OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX" in finish_mounted_walk
        and "output->reserved[0]" in finish_mounted_walk,
        "mounted Walk does not preserve nominal policy time through START_RESULT",
    )
    require(
        '"OverworldWildSpawns_MountIsActive:\\n"' in spawns
        and '"ldr r3, [r3, #24]\\n"' in spawns
        and re.search(
            r"slot != OW_WILD_FOLLOWER_SLOT\s*"
            r"\|\| !OverworldWildSpawns_MountIsActive\(\)",
            spawns,
        ) is not None
        and re.search(
            r"frameWorkMask \|= movementInProgressBefore\s*"
            r"& ~state->movementInProgressMask;.*?"
            r"frameWorkMask &= ~roleOwnedMask;.*?"
            r"OverworldWildSpawns_TickMovementParams",
            spawns,
            re.DOTALL,
        ) is not None
        and re.search(
            r"!state->spawns\[slot\]\.active\s*"
            r"\|\| \(slot == OW_WILD_FOLLOWER_SLOT\s*"
            r"&& OverworldWildSpawns_MountIsActive\(\)\)",
            spawns,
        ) is not None,
        "wild movement can reclaim the mounted follower policy",
    )
    require(
        "MAPOBJECTFLAG_UNK18 | MAPOBJECTFLAG_UNK31" in field_mount_source
        and "follower->flags &= ~MAPOBJECTFLAG_UNK31;" in mount_source
        and "OverworldWildRuntime_SetFacingVectorUnlessMounted" in runtime_source
        and "2: .word 0x0205F97D" in runtime_source
        and ". = ORIGIN(rom) + 0xBEC;" in runtime_linker
        and "KEEP(*(.overworld_wild_runtime_mount_facing))" in runtime_linker
        and "bl 0x023BD3EC" in overworld_patch,
        "mounted facing-vector ownership is incomplete",
    )
    ground_probe = re.search(
        r"OverworldWildRuntime_GetGroundBaseY\([^;]*?\)\s*"
        r"\{.*?^\}",
        runtime_source,
        re.DOTALL | re.MULTILINE,
    )
    require(
        ground_probe is not None
        and "VecFx32 targetPosition;" in ground_probe.group(0)
        and "OW_WILD_RUNTIME_QUERY_NATIVE_HEIGHT(" in ground_probe.group(0)
        and "object->posVec[0] =" not in ground_probe.group(0)
        and "object->posVec[2] =" not in ground_probe.group(0),
        "mounted ground-height probe mutates the live render object",
    )
    custom_motion_source_fixtures(mount_source, actor_source)
    field_input_source = (REPO / "src/field/overworld_mount_field_input.c").read_text()
    require(
        "OverworldMount_FieldInputProcess" in mount_source
        and "OVERWORLD_MOUNT_FIELD_INPUT_MAP_TRANSITION" in field_input_source
        and "OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT" in field_input_source
        and "== OW_WILD_BEHAVIOR_LOCOMOTION_HOP" in mount_source,
        "mounted Hop does not suppress synthetic warp/step transitions",
    )
    require(
        "OverworldMount_TryNextHopLandingCandidate" in mount_source
        and "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(" in mount_source
        and "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(" in mount_source
        and "lateralMagnitude != search->distance" not in mount_source
        and "forwardX * search->distance - forwardY * lateral" in mount_source
        and "forwardY * search->distance + forwardX * lateral" in mount_source
        and "lateralMagnitude = search->lateral == maxDistance" in mount_source
        and "lateralMagnitude >= search->distance" in mount_source
        and "sideCount = lateralMagnitude == 0 ? 1 : 2" in mount_source
        and re.search(
            r"hopSearch\.lateral = 0;\s*"
            r"hopSearch\.distance = maxDistance;\s*"
            r"hopSearch\.side = 0;\s*"
            r"while \(OverworldMount_TryNextHopLandingCandidate\(.*?"
            r"OverworldMount_PlanHopTrajectory\(",
            mount_source,
            re.DOTALL,
        ) is not None,
        "mounted Hop does not widen landing candidates from cardinal to diagonal",
    )
    require(
        "motionStreamPreparing" in mount_runtime_source
        and "OverworldMount_UpdateLandStreamAnchor" in mount_source
        and "OverworldMount_ApplyTerrainStream" in mount_source
        and "OverworldMount_BeginTerrainStream" in mount_source
        and "OverworldMount_ReleaseTerrainStream" in mount_source
        and "OVERWORLD_FIELD_TERRAIN_STREAM_QUERY_IDLE" in mount_source
        and "OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN" in mount_source
        and "OVERWORLD_FIELD_TERRAIN_STREAM_POLL" in mount_source
        and "OVERWORLD_FIELD_TERRAIN_STREAM_CANCEL" in mount_source
        and "entry->terrainStream(&call)" in mount_source
        and "OverworldMount_GetLandDataManager" not in mount_source
        and "ov01_021F62E8" not in mount_source
        and "ov01_021F62E8" not in walk_module_source
        and "landDataManager" not in mounted_flat_walk.group(0)
        and "ov01_021F62E8" not in field_stream_source
        and field_stream_source.count(
            "*(VecFx32 **)((u8 *)manager + 0xDC)") == 2
        and "+ 0xA0" in field_stream_source
        and "+ 0xD0" in field_stream_source
        and "+ 0xD8" in field_stream_source
        and "runtime->watchedAnchor.x +=" in field_stream_source
        and "runtime->watchedAnchor.z +=" in field_stream_source
        and "OVERWORLD_FIELD_TERRAIN_STREAM_REBIND" in mount_source
        and "OverworldMount_DrainLandStream" in mount_source
        and mounted_flat_walk is not None
        and diagonal_walk is not None
        and "motionStreamPreparing" in diagonal_walk.group(0)
        and re.search(
            r"OverworldMount_UpdateLandStreamAnchor\(void\).*?"
            r"OVERWORLD_FIELD_TERRAIN_STREAM_POLL",
            mount_source,
            re.DOTALL,
        ) is not None
        and re.search(
            r"OverworldMount_CanToggle\([^;]*?\).*?"
            r"!sOverworldMountState\.motionStreamPreparing",
            mount_source,
            re.DOTALL,
        ) is not None
        and "started = OverworldWalk_StartMountedFlat(" in mount_source
        and "if (state->motionCooldown != 0" in walk_module_source
        and mounted_flat_walk.group(0).find(
            "if (!beginSharedMotion(advanceFirstFrame))"
        ) < mounted_flat_walk.group(0).find(
            "avatar->unk8 = WALK_MOUNT_FREEZE_COMMAND;"
        )
        and re.search(
            r"OverworldMount_UpdateCustomMotion\(\);\s*"
            r"OverworldMount_DrainLandStream\(\);",
            mount_source,
        ) is not None
        and re.search(
            r"if \(sOverworldMountState\.snapshot\.motionMode\s*"
            r"!= OVERWORLD_MOUNT_MOTION_WALK\) \{.*?"
            r"baseZ -= sample\.swayOffset;.*?"
            r"baseX -= sample\.swayOffset;.*?"
            r"if \(player->xCurr != baseX >> 16\s*"
            r"\|\| player->yCurr != baseZ >> 16\) \{\s*"
            r"player->xPrev = player->xCurr;\s*"
            r"player->yPrev = player->yCurr;",
            mount_source,
            re.DOTALL,
        ) is not None,
        "mounted custom motion does not pre-stream land data or logical history",
    )
    require(
        "OVERWORLD_MOUNT_MOTION_CRASH" in mount_source
        and "OverworldMount_ApplyCrashPresentation" in mount_source
        and "OW_WILD_BEHAVIOR_WALK_ALLOWS_TURNING" in mount_runtime_source
        and "lane->hopSwayWidth" in mount_source
        and "lane->hopSpinSpeed" in mount_source,
        "mounted Walk crash or player custom-Jump presentation is incomplete",
    )
    require(
        "validateHopLanding" in mount_runtime_source
        and "PlayerAvatar_ResetMovement" in mount_source
        and mount_runtime_source.count(
            "MapObject_SetPositionFromVectorAndDirection("
        ) >= 3
        and "memcpy(follower->posVec, player->posVec" in field_mount_source
        and "memcpy(&follower->xPrev, &player->xPrev" in field_mount_source,
        "mounted custom motion lacks landing or avatar-state safeguards",
    )
    require(
        re.search(
            r"motionDirection = direction;\s*"
            r"if \(\(sOverworldMountState\.motionFlicker & 0x0F\) != 0\) \{\s*"
            r"sOverworldMountState\.motionDirection = player->curFacing;",
            mount_source,
        ) is not None
        and re.search(
            r"OverworldMount_CommitMotionTarget\(LocalMapObject \*player\).*?"
            r"MapObject_SetPositionFromVectorAndDirection\(\s*"
            r"player,\s*\(VecFx32 \*\)player->posVec,\s*player->curFacing\);",
            mount_source,
            re.DOTALL,
        ) is not None,
        "mounted spinning Hop resets facing at takeoff or landing",
    )
    require(
        "bufferedDirection" in mount_runtime_source
        and "stopPending" in mount_runtime_source
        and "OVERWORLD_ACTOR_WALK_POLICY_FLAG_DEFER_STOP"
            in mount_runtime_source
        and "policy->stopPending = TRUE;" in mount_runtime_source
        and "MAPOBJECTFLAG_UNK7" in mount_source
        and "MapObject_SetPositionFromVectorAndDirection" in mount_source
        and "memcpy(follower->posVec, player->posVec" in field_mount_source
        and "memcpy(&follower->xPrev, &player->xPrev" in field_mount_source
        and "MapObject_StartMovementCommandInternal(\n        follower,\n"
            not in walk_module_source
        and "memcpy(&follower->xPrev, &player->xPrev"
            in field_mount_source
        and "OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND" in mount_source
        and mount_runtime_source.count(
            "MapObject_StartMovementCommandInternal("
        ) >= 4
        and issue_held_movement is not None
        and re.search(
            r"if \(trackedStep\) \{\s*"
            r"u8 facingDirection = direction;.*?"
            r"OverworldMount_InspectPolicy\(&policy\);\s*"
            r"if \(policy\.pendingStep == OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL\) \{\s*"
            r".*?facingDirection = sOverworldMountState\.reservedPolicyState\[\s*"
            r"OVERWORLD_MOUNT_WALK_FACING_DIRECTION_INDEX\];"
            r".*?\}.*?"
            r"OverworldMount_TryStartCustomMotion\(\s*"
            r"avatar,\s*direction,\s*facingDirection,\s*FALSE\)",
            issue_held_movement.group(0),
            re.DOTALL,
        ) is not None
        and "turnDirection" not in issue_held_movement.group(0),
        "mounted held Walk does not keep separate skid travel and facing",
    )
    mounted_diagonal_admission_fixtures(mount_source)
    require(
        "OverworldWalk_FilterMountedInput(" in mount_source
        and "avatar,\n            &newKeys,\n            &heldKeys" in mount_source
        and mounted_flat_walk is not None
        and "state->motionFrameCount = OverworldWalk_ClampTime("
            in mounted_flat_walk.group(0)
        and "OVERWORLD_MOUNT_WALK_TRAVEL_TIME_INDEX"
            in mounted_flat_walk.group(0)
        and "state->motionArcHeightQ4 = 0;" in mounted_flat_walk.group(0)
        and "OverworldWalk_StrictDiagonalAllowed" in walk_module_source
        and "Walk_CanCardinal(avatar, vertical)" in walk_module_source
        and "Walk_CanCardinal(avatar, horizontal)" in walk_module_source
        and "OverworldWalk_IsFortyFiveDegreeTurn("
            in runtime_source
        and "!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL("
            in runtime_source
        and "!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL("
            in runtime_source
        and "OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID(" in runtime_source
        and re.search(
            r"requestedDirection < 4.*?requestedDirection >= 4.*?"
            r"OverworldActorWalkPolicy_ResetState\(.*?"
            r"policy->bufferedDirection != OW_WILD_WALK_DIRECTION_NONE",
            runtime_source,
            re.DOTALL,
        ) is not None
        and diagonal_walk is not None
        and re.search(
            r"facingDirection = sOverworldMountState\.reservedPolicyState\[\s*"
            r"OVERWORLD_MOUNT_WALK_FACING_DIRECTION_INDEX\];.*?"
            r"OverworldMount_TryStartCustomMotion\(\s*"
            r"avatar,\s*requestedDirection,\s*facingDirection,\s*"
            r"advanceFirstFrame\)",
            diagonal_walk.group(0),
            re.DOTALL,
        ) is not None
        and "turnDirection" not in diagonal_walk.group(0),
        "mounted exact-frame diagonal Walk policy is incomplete",
    )
    require(
        re.search(
            r"intent\.facing = sOverworldMountState\.motionDirection;.*?"
            r"distanceX = sOverworldMountState\.motionTargetX\s*"
            r"- sOverworldMountState\.motionStartX;\s*"
            r"distanceY = sOverworldMountState\.motionTargetY\s*"
            r"- sOverworldMountState\.motionStartY;.*?"
            r"candidate\.direction = sOverworldMountState\.snapshot\.motionMode\s*"
            r"== OVERWORLD_MOUNT_MOTION_WALK\s*"
            r"\? OverworldWalk_DirectionFromDelta\(distanceX, distanceY\)\s*"
            r": sOverworldMountState\.motionDirection;.*?"
            r"if \(distanceX < 0\).*?"
            r"intent\.swayWidth = sOverworldMountState\.snapshot\.motionMode\s*"
            r"== OVERWORLD_MOUNT_MOTION_WALK.*?"
            r"intent\.pauseFrames = sOverworldMountState\.snapshot\.motionMode\s*"
            r"== OVERWORLD_MOUNT_MOTION_WALK",
            mount_source,
            re.DOTALL,
        ) is not None,
        "mounted skid plan mixes travel with facing or drops Walk presentation",
    )
    update_motion = re.search(
        r"OverworldMount_UpdateCustomMotion\(void\)\s*\{(?P<body>.*?)"
        r"typedef struct OverworldMountHopSearch",
        mount_source,
        re.DOTALL,
    )
    require(
        update_motion is not None
        and update_motion.group("body").find("motionElapsed++;")
            < update_motion.group("body").find(
                "Commit on the Nth update."
            )
            < update_motion.group("body").find(
                "OverworldMount_FinishCustomMotion();",
                update_motion.group("body").find("Commit on the Nth update."),
            )
        and "stationary player command stays" in update_motion.group("body"),
        "mounted flat Walk does not finish on its exact Nth frame",
    )
    require(
        "#define OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND 0x3E"
            in mount_source
        and "#define OVERWORLD_MOUNT_WALK_FREEZE_COMMAND 0x3C"
            in mount_source
        and "#define WALK_MOUNT_FREEZE_COMMAND 0x3C"
            in walk_module_source
        and mount_source.count("OverworldMount_CompletePendingStep(") == 4,
        "mounted Walk uses a fixed-delay boundary or has competing step consumers",
    )
    require(
        "ASSERT(. <= ORIGIN(rom) + 0x1C40" in mount_linker
        and ". = ORIGIN(rom) + 0x1C40;" in mount_linker,
        "mount overlay file size can drift from its packaged Y9/FAT metadata",
    )
    require(
        "#define OVERWORLD_MOUNT_OVERLAY_VERSION 11" in mount_header
        and "OverworldActorPolicy_MountCommand" in actor_source
        and "OVERWORLD_ACTOR_WALK_POLICY_SWAP_PROFILE" in actor_source
        and "section(\".overworld_actor_mount_profile_command\")" in actor_source
        and "KEEP(*(.overworld_actor_mount_profile_command))" in actor_linker
        and "OverworldActorPolicy_MountCommand = 0x023BA0E0 | 1;" in mount_linker
        and "OVERWORLD_ACTOR_WALK_POLICY_SWAP_PROFILE" in mount_source
        and "priorFollowerBehaviorFingerprint" in mount_source
        and "priorFollowerMatchedLayerMask" in mount_source
        and re.search(
            r"OverworldMount_Cancel\(u8 reason\).*?"
            r"OverworldMount_BindingMatchesFollower\(.*?"
            r"OVERWORLD_ACTOR_WALK_POLICY_BIND_PROFILE,\s*"
            r"&sOverworldMountState\.priorFollowerBehaviorFingerprint",
            mount_source,
            re.DOTALL,
        ) is not None,
        "mounted policy swap does not save and restore Follower identity",
    )
    require(
        re.search(
            r"if \(walkMotion\) \{.*?"
            r"player->posVec\[2\].*?"
            r"if \(walkMotion\) \{\s*"
            r"OverworldMount_FinishOneFrameWalk\(avatar\);\s*"
            r"\} else \{\s*"
            r"OverworldMount_ClearObjectCommand\(player\);\s*\}.*?"
            r"if \(follower != NULL\) \{\s*"
            r"OverworldMount_ClearObjectCommand\(follower\);\s*\}.*?"
            r"snapshot\.motionMode = OVERWORLD_MOUNT_MOTION_NONE;.*?"
            r"OverworldMount_SyncPresentation\(\);",
            mount_source,
            re.DOTALL,
        ) is not None
        and "section(\".overworld_mount_one_frame_walk\")" in actor_source
        and "player->movementCmd == 0x3C" in actor_source
        and "player->flags |= MAPOBJECTFLAG_UNK5;" in actor_source
        and "avatar->unk10 = 1;" in actor_source
        and "avatar->unk14 = 2;" in actor_source
        and "OverworldMount_FinishOneFrameWalk" in actor_linker
        and "policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED;"
            in runtime_source,
        "mounted flat Walk does not finish player and mount presentation together",
    )
    cancel_mount = re.search(
        r"static void OverworldMount_Cancel\(u8 reason\)\s*\{"
        r"(?P<body>.*?)\n\}",
        mount_source,
        re.DOTALL,
    )
    detach_mount = mount_source.split(
        "static void OverworldMount_DetachPresentation(void)", 1
    )[1].split("static void OverworldMount_Cancel", 1)[0]
    require(
        cancel_mount is not None
        and "OverworldWalkMount_RebaseMotionTarget(&sOverworldMountState);"
            in cancel_mount.group("body")
        and "OverworldMount_DetachPresentation();"
            in cancel_mount.group("body")
        and "OverworldMount_ClearObjectCommand(player);" in detach_mount
        and "OverworldMount_ResetAvatarAfterCancel(avatar);" in detach_mount
        and "OverworldMount_ClearFollowerDecisionCooldown();" in detach_mount
        and "OverworldMountReleaseHandoffFramesMustRemain1" in mount_source
        and "OverworldMountFollowerCooldownOffsetMustRemainF4" in mount_source
        and '"mov r2, #0\\n"' in function_body(
            (REPO / "src/overworld_mount_action_overlay/overworld_mount_shared_helpers.c").read_text(),
            "OverworldMount_ClearFollowerDecisionCooldown"
        )
        and '"1: .word sOverworldWildSpawnState + 0xF4\\n"'
            in function_body(
                (REPO / "src/overworld_mount_action_overlay/overworld_mount_shared_helpers.c").read_text(),
                "OverworldMount_ClearFollowerDecisionCooldown"
            )
        and '"mov r1, #1\\n"' in function_body(
            mount_source, "OverworldMount_EndSession"
        )
        and '"lsl r1, r1, #8\\n"' in function_body(
            mount_source, "OverworldMount_EndSession"
        )
        and "&& sOverworldMountState.snapshot.reserved != 0"
            in function_body(mount_source, "OverworldMount_Tick")
        and "sOverworldMountState.snapshot.reserved--;"
            in function_body(mount_source, "OverworldMount_Tick")
        and "if (sOverworldMountState.pendingStep)" not in detach_mount,
        "mounted cancellation can leave player or follower movement blocked",
    )
    require(
        "section(\".overworld_walk_mount_abort\")" in walk_module_source
        and "OverworldWalkMount_RebaseMotionTargetImpl"
            in walk_module_source
        and ". = ORIGIN(rom) + 0x1BEA;" in walk_module_linker
        and "KEEP(*(.overworld_walk_mount_abort))" in walk_module_linker
        and "OverworldWalkMount_RebaseMotionTarget = 0x023BFFEA | 1;"
            in root_linker,
        "mounted cancellation rollback helper is not fixed in resident code",
    )
    resume_follower = re.search(
        r"OverworldMount_ResumeCustomMotionAfterMapTransition\(void\)\s*\{"
        r"(?P<body>.*?)\n\}",
        mount_source,
        re.DOTALL,
    )
    require(
        resume_follower is not None
        and "!= OVERWORLD_MOUNT_MOTION_WALK"
            in resume_follower.group("body"),
        "mounted Walk transition resumes an independent follower command",
    )
    require(
        "movementCrashShakeTimers[OW_WILD_FOLLOWER_SLOT] = 0;"
            in field_mount_source,
        "mounted presentation can be overwritten by a stale crash shake",
    )
    require(
        re.search(
            r"KEEP\(\*\(\.overworld_mount_step\)\)\s*"
            r"KEEP\(\*\(\.overworld_mount_step_extra\)\)",
            mount_linker,
        ) is not None
        and re.search(
            r"KEEP\(\*\(\.overworld_mount_field_input\)\)\s*"
            r"KEEP\(\*\(\.overworld_mount_field_input_extra\)\)",
            mount_linker,
        ) is not None
        and re.search(
            r"KEEP\(\*\(\.overworld_mount_crash\)\)\s*"
            r"KEEP\(\*\(\.overworld_mount_crash_extra\)\)",
            mount_linker,
        ) is not None,
        "mount helper code is not kept inside the audited ABI reserves",
    )
    require(
        "OVERWORLD_MOUNT_TOGGLE_BUTTON PAD_BUTTON_SELECT" in mount_source
        and "beginMountSelectedFollower(fieldSystem, state)" in mount_source,
        "Select does not bind the current follower through the profile bridge",
    )
    require(
        "if (sOverworldMountState.motionCooldown != 0) {\n        "
            "/* Field input has already resolved its direction"
            in mount_source
        and "*newKeys &= ~PAD_PLUS_KEY_MASK;" not in mount_source
        and "*heldKeys &= ~PAD_PLUS_KEY_MASK;" not in mount_source,
        "landing pause can leak a stale direction into stock player control",
    )
    require(
        "The held-movement hook can run before the current exact-frame"
            in mount_source
        and re.search(
            r"if \(trackedStep\) \{.*?"
            r"snapshot.motionMode\s*!= OVERWORLD_MOUNT_MOTION_NONE"
            r".*?return;",
            mount_source,
            re.DOTALL,
        ) is not None,
        "held input can replace an active mounted Walk motion",
    )
    require(
        "/* Custom locomotion owns the player for its complete idle/move/pause"
            in mount_source
        and "Overlay 1 asks the stock avatar collision helper" in mount_source
        and re.search(
            r"if \(avatar->unk10 != OVERWORLD_MOUNT_PLAYER_MOVE_STATE_NONE"
            r".*?OverworldMount_ResetAvatarAfterCancel\(avatar\);",
            mount_source,
            re.DOTALL,
        ) is not None
        and re.search(
            r"OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT\(rawLocomotion\)\) \{"
            r".*?OverworldMount_TryStartCustomMotion\(.*?return TRUE;\s*\}",
            mount_source,
            re.DOTALL,
        ) is not None,
        "idle custom locomotion can fall through to stock player control",
    )
    require(
        "direction >= OVERWORLD_MOUNT_DIRECTION_NORTH_WEST\n"
            "        && direction <= OVERWORLD_MOUNT_DIRECTION_SOUTH_EAST"
            in mount_source,
        "no-direction input can be misread as a mounted diagonal",
    )
    capture_toggle = re.search(
        r"static void OverworldWildSpawns_CaptureMountToggle\([^;]*?\)\s*\{"
        r".*?\n\}",
        resident_spawns,
        re.DOTALL,
    )
    resident_field_ready_task = re.search(
        r"static void OverworldWildSpawns_FieldReadyTask\([^;]*?\)\s*\{"
        r".*?\n\}",
        resident_spawns,
        re.DOTALL,
    )
    require(
        "OVERWORLD_MOUNT_TOGGLE_LATCH_ADDR 0x023BC7DA" in mount_header
        and "u8 bufferedTogglePending;" in mount_internal
        and "u8 bufferedToggleDown;" in mount_internal
        and "bufferedTogglePending) == 0x96" in mount_internal
        and capture_toggle is not None
        and "reg_PAD_KEYINPUT & PAD_BUTTON_SELECT"
            in capture_toggle.group(0)
        and "fieldSystem->taskman == NULL" in capture_toggle.group(0)
        and "!OverworldFollowerSelector_IsActiveFlagSet()"
            in capture_toggle.group(0)
        and "OVERWORLD_MOUNT_TOGGLE_PENDING = TRUE;"
            in capture_toggle.group(0)
        and "u8 togglePressed = sOverworldMountState.bufferedTogglePending;"
            in mount_source
        and "sOverworldMountState.bufferedTogglePending = FALSE;"
            in mount_source
        and "u8 bufferedToggleDown = sOverworldMountState.bufferedToggleDown;"
            in mount_source
        and "sOverworldMountState.bufferedToggleDown = bufferedToggleDown;"
            in mount_source
        and resident_field_ready_task is not None
        and resident_field_ready_task.group(0).find(
            "OverworldWildSpawns_CaptureMountToggle(fieldSystem);"
        ) < resident_field_ready_task.group(0).find(
            "if (!sub_0203DF8C(fieldSystem))"
        )
        and "section(\".overworld_mount_toggle_latch\")" in mount_source
        and "OverworldMount_TickLatched" in mount_source
        and "__mount_state_start + 0x96 == 0x023BC7DA" in mount_linker
        and "OverworldMount_TickLatched," in mount_source
        and ". = ORIGIN(rom) + 0xC78;" in mount_linker
        and "KEEP(*(.overworld_mount_toggle_latch))" in mount_linker,
        "Select input can be lost while the mount frame service is stopped",
    )
    require(
        "u8 reservedPolicyState[9];" in mount_internal
        and "OverworldMountBoundaryStorageMustRemain9" in mount_internal
        and "motionStartX) == 0x98" in mount_internal
        and "motionTargetX) == 0x9C" in mount_internal
        and "motionStartBaseY) == 0xA0" in mount_internal
        and "motionTargetBaseY) == 0xA4" in mount_internal
        and "OVERWORLD_MOUNT_BOUNDARY_FLAGS_INDEX 0" in mount_internal
        and "OVERWORLD_MOUNT_BOUNDARY_APPLIED_LO_INDEX 1" in mount_internal
        and "OVERWORLD_MOUNT_BOUNDARY_APPLIED_HI_INDEX 2" in mount_internal
        and "OVERWORLD_MOUNT_BOUNDARY_MOTION_INDEX 3" in mount_internal
        and "OVERWORLD_MOUNT_BOUNDARY_PHASE_INDEX 4" in mount_internal
        and "OverworldActorRequiredBoundaryAcksMustRemainExact"
            in actor_internal,
        "mount boundary storage or the required ACK set changed layout",
    )
    require(
        "OVERWORLD_MOUNT_RIDER_SPRITE_MALE 178" in mount_source
        and "OVERWORLD_MOUNT_RIDER_SPRITE_FEMALE 179" in mount_source
        and "savedPlayerGfxId" in mount_source
        and "ChangeMapObjSprite(" in mount_source
        and "ChangeMapObjSprite(player, sOverworldMountState.savedPlayerGfxId)"
            in mount_source,
        "mounted rider does not apply and restore the swim hero/heroine sprite",
    )
    require(
        "OverworldMount_HandleFollowerSelectionRequest" in mount_source
        and "OVERWORLD_FOLLOWER_SELECTION_REQUEST_PENDING" in mount_source
        and "OVERWORLD_FOLLOWER_SELECTION_REQUEST_MOUNT" in mount_source
        and "OVERWORLD_FOLLOWER_TRANSITION_QUEUE_APPEND" in mount_source
        and "->beginMountSelectedFollower(fieldSystem, state)" in mount_source,
        "mount controller does not consume selector mount requests",
    )
    require(
        "OverworldMount_AdvanceMovementChain" not in mount_source
        and "OverworldMount_StartChainPause" not in mount_source
        and "OverworldMount_ApplyChainPauseInput" not in mount_source,
        "mounted movement still contains a chain executor",
    )
    behavior_data = (REPO / "data/OverworldWildBehaviorData.c").read_text()
    follower_override = re.search(
        r"/\* profile: Follower \*/(?P<body>.*?)"
        r"/\* profile:",
        behavior_data,
        re.DOTALL,
    )
    require(follower_override is not None, "follower override profile is missing")
    mounted_chain_source_fixtures(mount_source, actor_source, walk_module_source, runtime_source)
    repel_source = (REPO / "src/repel.c").read_text()
    require(
        "OverworldMount_PlayerStepBridgeEntry(fieldSystem)" in repel_source,
        "mounted Movement Chain does not use the test2824 player-step callback",
    )
    require(
        "OVERWORLD_MOUNT_CANCEL_FIELD_BUSY" in spawns
        and "OVERWORLD_MOUNT_CANCEL_MAP_CHANGE" in mount_source
        and "OVERWORLD_MOUNT_OVERLAY_ENTRY->transition(call)"
            in field_mount_source
        and "preserveTransitionPrepared" in mount_source
        and "binding->mapId = spawn->mapId;" in mount_source
        and "binding->mapGeneration = state->mapGeneration;" in mount_source
        and "OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST" in spawns
        and "OVERWORLD_MOUNT_CANCEL_OVERLAY_CLEANUP" in spawns,
        "lifecycle cancellation coverage is incomplete",
    )
    transition_prepare = re.search(
        r"static BOOL OverworldMount_Transition\(\s*"
        r"const OverworldActorTransitionCall \*call\)"
        r"(?P<body>.*?)"
        r"static void __attribute__\(\(noinline, section\(\"\.overworld_mount_motion\"\)\)\)\s*"
        r"OverworldMount_ResumeCustomMotionAfterMapTransition",
        mount_source,
        re.DOTALL,
    )
    require(
        transition_prepare is not None
        and "OverworldMount_FinishCustomMotion" not in transition_prepare.group("body")
        and "OVERWORLD_ACTOR_TRANSITION_CALL_VERSION"
            in transition_prepare.group("body")
        and "OVERWORLD_ACTOR_TRANSITION_WORK_CANONICALIZE"
            in transition_prepare.group("body")
        and "OVERWORLD_ACTOR_TRANSITION_WORK_REBIND"
            in transition_prepare.group("body")
        and "OVERWORLD_MOUNT_BOUNDARY_ENGINE_END_SEEN"
            in transition_prepare.group("body")
        and "OVERWORLD_ACTOR_TRANSITION_WORK_DISCARD"
            in transition_prepare.group("body")
        and "preserveTransitionPrepared = TRUE" in transition_prepare.group("body")
        and "OverworldMount_ResumeCustomMotionAfterMapTransition();"
            in mount_source
        and re.search(
            r"freezeCommand = sOverworldMountState\.snapshot\.motionMode\s*"
            r"== OVERWORLD_MOUNT_MOTION_WALK\s*"
            r"\? OVERWORLD_MOUNT_WALK_FREEZE_COMMAND\s*"
            r": OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND;",
            mount_source,
        ) is not None
        and mount_source.count(
            "OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND"
        ) >= 4,
        "mounted custom motion does not survive a preserved map-area transition",
    )
    wild_transition = function_body(
        spawns,
        "OverworldWildSpawns_ApplyTransitionWork",
    )
    require(
        "OVERWORLD_ACTOR_TRANSITION_WORK_RESUME"
            in transition_prepare.group("body")
        and "OverworldMount_UpdateCustomMotion();" in mount_source
        and "OverworldMount_SyncPresentation();" in mount_source
        and "OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING" in wild_transition
        and "gOverworldWildFieldIdleRearmPending" not in mount_source,
        "preserved map transition leaves mounted presentation one frame behind",
    )
    transition_headers = mount_header + mount_internal
    require(
        "BOOL (*transition)(const OverworldActorTransitionCall *call);"
            in transition_headers
        and "prepareMapTransition" not in transition_headers + mount_source + spawns
        and "OW_WILD_MAP_HEADER_CHANGE_" not in transition_headers + spawns
        and "ApplyMountTransitionCompatibility" not in spawns,
        "retired private mount/wild transition protocol remains",
    )
    refill_function = re.search(
        r"static BOOL [^;]*?OverworldWildSpawns_TryRefill\([^;]*?\)\s*\{"
        r".*?\n\}",
        spawns,
        re.DOTALL,
    )
    runtime_refill_timer = function_body(
        actor_source,
        "OverworldActorSystem_PopulationFrameImpl",
    )
    population_control = function_body(
        actor_source,
        "OverworldActorSystem_PopulationControlImpl",
    )
    population_field_event = function_body(
        actor_source,
        "ActorSystem_PublishPopulationFieldEvent",
    )
    actor_transition = function_body(
        actor_source,
        "OverworldActorSystem_CompatibilityTransitionImpl",
    )
    player_frame = function_body(
        spawns,
        "OverworldWildSpawns_OverlayOnPlayerFrame",
    )
    player_step = function_body(
        spawns,
        "OverworldWildSpawns_OverlayOnPlayerStep",
    )
    require(
        "#define OW_WILD_REFILL_BASE_INTERVAL_FRAMES 60" in spawns
        and refill_function is not None
        and "spawnCooldown--" not in refill_function.group(0)
        and "OW_WILD_REFILL_BASE_INTERVAL_FRAMES * sharedSpawnCount"
            in refill_function.group(0)
        and runtime_refill_timer
        and "OVERWORLD_POPULATION_INPUT_FRAME" in runtime_refill_timer
        and "OVERWORLD_POPULATION_INPUT_TIMER_ELIGIBLE"
            in runtime_refill_timer
        and "OVERWORLD_POPULATION_RESULT_REFILL_DUE"
            in runtime_refill_timer
        and "OVERWORLD_ACTOR_POPULATION_FRAME_TIMER_ELIGIBLE"
            in runtime_refill_timer
        and "OVERWORLD_ACTOR_POPULATION_FRAME_REFILL_DUE"
            in runtime_refill_timer
        and "gOverworldWildFieldIdleRearmPending" not in runtime_refill_timer
        and population_control
        and "OVERWORLD_POPULATION_INPUT_TAKE_WORK" in population_control
        and "ActorSystem_ApplyPopulationInput(&input, &result);"
            in population_control
        and "OverworldPopulationState population;" in actor_internal
        and "OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->populationControl("
            not in actor_source
        and "OverworldWildRuntime_PopulationControl" not in runtime_source
        and "entry->reservedPopulationControl == 0" in runtime_source
        and "OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL"
            in actor_source
        and "OVERWORLD_ACTOR_POPULATION_CONTROL_ADVANCE_MAINTENANCE"
            in actor_source
        and "OverworldRuntime_TickWildRefillTimer" not in mount_source
        and player_frame.count(
            "OVERWORLD_ACTOR_SYSTEM_POPULATION_ENTRY->frame("
        ) == 1
        and "gOverworldWildFieldIdleRearmPending == 0" in player_frame
        and "gOverworldWildFieldIdleRearmPending |=" in player_frame
        and "actorFrame == OVERWORLD_ACTOR_FRAME_PENDING" in player_frame
        and "OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING"
            in player_step
        and "OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING) == 0"
            in player_step
        and player_step.count(
            "OVERWORLD_ACTOR_POPULATION_CONTROL_REQUEST_MAINTENANCE"
        ) == 1,
        "wild refill cadence is still coupled to player-step calls",
    )
    require(
        refill_function.group(0).find(
            "OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL"
        )
            < refill_function.group(0).find(
                "OverworldWildSpawns_ReconcileFollowerSelection("
            ),
        "an early follower refill exit can leave the runtime timer locked",
    )
    require(
        "OVERWORLD_POPULATION_INPUT_FIELD_EVENT" in population_field_event
        and "ActorSystem_ApplyPopulationInput(&input, &result);"
            in population_field_event
        and "OVERWORLD_POPULATION_FIELD_SUSPEND" in actor_transition
        and "OVERWORLD_POPULATION_FIELD_REBIND" in actor_transition
        and "OVERWORLD_POPULATION_FIELD_RESUME" in actor_transition
        and "OVERWORLD_POPULATION_FIELD_DISCARD" in actor_transition
        and "OVERWORLD_ACTOR_POPULATION_CONTROL_REQUEST_MAINTENANCE"
            in player_step,
        "map transitions do not request an immediate population reconciliation",
    )
    field_ready_task = re.search(
        r"static void OverworldWildSpawns_FieldReadyTask\([^;]*?\)\s*\{"
        r".*?\n\}",
        resident_spawns,
        re.DOTALL,
    )
    resident_player_step = re.search(
        r"BOOL OverworldWildSpawns_OnPlayerStep\([^;]*?\)\s*\{"
        r".*?\n\}",
        resident_spawns,
        re.DOTALL,
    )
    cold_load_gate = re.search(
        r"if \(!IsOverlayLoaded\(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION\)\) \{"
        r"(?P<body>.*?)\n\s*\}",
        field_ready_task.group(0) if field_ready_task else "",
        re.DOTALL,
    )
    field_ready_before_poll = (
        field_ready_task.group(0).split(
            "OverworldFieldService_PollFrame(fieldSystem);", 1
        )[0]
        if field_ready_task is not None
        else ""
    )
    transition_tail = (
        field_ready_task.group(0).split(
            "sFieldReadyTaskMapId = currentMapId;", 1
        )[1].split("/* Overlay 131", 1)[0]
        if field_ready_task is not None
        and "sFieldReadyTaskMapId = currentMapId;"
            in field_ready_task.group(0)
        else "return;"
    )
    require(
        field_ready_task is not None
        and cold_load_gate is not None
        and "HandleLoadOverlay(" in cold_load_gate.group("body")
        and "return;" in cold_load_gate.group("body")
        and "OverworldFieldService_PollFrame(fieldSystem);"
            in field_ready_task.group(0)
        and resident_player_step is not None
        and "gOverworldWildFieldIdleRearmPending != 0"
            in resident_player_step.group(0)
        and "if (state->battleGraceSteps != 0) {\n        return FALSE;\n    }"
            not in player_step,
        "save-load refill can use a cold overlay in the load frame",
    )
    require(
        "gOverworldWildFieldIdleRearmPending != 0"
            in field_ready_before_poll
        and "OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->onPlayerStep("
            in field_ready_before_poll,
        "stale map context can reach Y or throw service before rearm",
    )
    follower_refill_branch = player_step.split(
        "OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING", 1
    )[1]
    follower_ball_tick = follower_refill_branch.find(
        "OverworldWildSpawns_TickPlayerBallProjectile("
    )
    follower_refill = follower_refill_branch.find(
        "OverworldWildSpawns_TryRefill("
    )
    require(
        0 <= follower_ball_tick < follower_refill,
        "follower refill retries before its release ball can advance",
    )
    require(
        field_ready_task is not None
        and "return;" in transition_tail
        and resident_player_step is not None
        and "OverworldWildSpawns_GetOverlayEntry(TRUE)"
            in resident_player_step.group(0),
        "map-header reconciliation can reach input or refill in the same frame",
    )
    require(
        "HandleLoadOverlay("
            in field_ready_before_poll
        and "OVERWORLD_FOLLOWER_SELECTOR_DIRECT_LOADED_FLAG"
            in field_ready_before_poll
        and "OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY->validate()"
            in field_ready_before_poll
        and field_ready_task.group(0).find(
            "OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->onPlayerStep("
        ) < field_ready_task.group(0).find(
            "OverworldFollowerSelectorTaskPollEntry(fieldSystem);"
        ) < field_ready_task.group(0).find(
            "OverworldFieldService_PollFrame(fieldSystem);"
        ),
        "first-ready map, selector, and input ordering is unsafe",
    )
    poll_frame = re.search(
        r"static BOOL OverworldFieldService_PollFrameImpl\([^;]*?\)\s*\{"
        r".*?\n\}",
        field_service,
        re.DOTALL,
    )
    poll_before_run = (
        poll_frame.group(0).split(
            "if (OverworldFollowerSelector_IsYPressPending()", 1
        )[0]
        if poll_frame is not None
        else "return TRUE;"
    )
    poll_after_run = (
        "if (OverworldFollowerSelector_IsYPressPending()"
        + poll_frame.group(0).split(
            "if (OverworldFollowerSelector_IsYPressPending()", 1
        )[1]
        if poll_frame is not None
        and "if (OverworldFollowerSelector_IsYPressPending()"
            in poll_frame.group(0)
        else ""
    )
    require(
        poll_frame is not None
        and "if (!HandleLoadOverlay("
            in poll_before_run
        and "return TRUE;" not in poll_before_run.split(
            "if (!HandleLoadOverlay(", 1
        )[1]
        and "return FALSE;"
            in poll_before_run.split("if (!HandleLoadOverlay(", 1)[1]
        and "OverworldFollowerSelector_IsYPressPending()"
            in poll_after_run
        and "OverworldFollowerSelector_IsDirectLoaded()"
            in poll_after_run
        and "OverworldFollowerSelector_ValidateLoaded()"
            in poll_after_run
        and poll_after_run.find(
            "OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY->inputFilter("
        ) < poll_after_run.find("entry->onPlayerFrame("),
        "cold Y or R input still waits a frame after overlay load",
    )
    field_linker = (REPO / "src/field/linker.ld").read_text()
    field_boundary_source_fixtures(field_linker)
    require(
        "(void)OverworldMount_UpdateLandStreamAnchor();" in mount_source
        and re.search(
            r"OverworldMount_Cancel\(u8 reason\).*?"
            r"if \(sOverworldMountState\.motionStreamPreparing.*?"
            r"OverworldMount_ReleaseTerrainStream\(\);",
            mount_source,
            re.DOTALL,
        ) is not None
        and re.search(
            r"OverworldMount_UpdateCustomMotion\(\);\s*"
            r"OverworldMount_DrainLandStream\(\);",
            mount_source,
        ) is not None,
        "landed custom motion does not release before its land stream drains",
    )
    complete_start = mount_source.find(
        "OverworldMount_CompletePendingStep(FIELD_PLAYER_AVATAR *avatar)\n{"
    )
    complete_end = mount_source.find(
        "static BOOL OverworldMount_CanControl", complete_start
    )
    complete_step = mount_source[complete_start:complete_end]
    walk_commit_start = mount_source.find(
        "OverworldMount_CommitWalkBoundary(FIELD_PLAYER_AVATAR *avatar)\n{"
    )
    walk_commit_end = mount_source.find(
        "OverworldMount_AcknowledgeSharedMotion(", walk_commit_start
    )
    walk_commit = mount_source[walk_commit_start:walk_commit_end]
    wild_walk_commit = function_body(
        spawns, "OverworldWildSpawns_HandleFinishedWalkMovement"
    )
    sync_start = mount_source.find("static void OverworldMount_SyncPresentation")
    sync_end = mount_source.find(
        "static void OverworldMount_RecordSkidPresentation", sync_start
    )
    sync_presentation = mount_source[sync_start:sync_end]
    drain_start = mount_source.find("OverworldMount_DrainLandStream(void)\n{")
    drain_end = mount_source.find(
        "static BOOL OverworldMount_BeginSharedMotion", drain_start
    )
    stream_drain = mount_source[drain_start:drain_end]
    finish_start = mount_source.find("OverworldMount_FinishCustomMotion(void)\n{")
    finish_end = mount_source.find(
        "static BOOL OverworldMount_TryFinalizeSharedMotion", finish_start
    )
    finish_motion = mount_source[finish_start:finish_end]
    finalizer_start = finish_end
    finalizer_end = mount_source.find(
        "OverworldMount_UpdateCustomMotion(void)\n{", finalizer_start
    )
    shared_finalizer = mount_source[finalizer_start:finalizer_end]
    player_step_bridge = function_body(
        mount_source, "OverworldMount_PlayerStepBridge"
    )
    on_player_step = function_body(
        (REPO / "src/field/overworld_mount_field_input.c").read_text(),
        "OverworldMount_ProcessFieldInput"
    )
    terminal_retry = function_body(mount_source, "OverworldMount_OnPlayerStep")
    player_control = function_body(
        mount_source, "OverworldMount_ProcessPlayerControl"
    )
    mount_tick = function_body(mount_source, "OverworldMount_Tick")
    require(
        complete_start >= 0
        and complete_end > complete_start
        and "MapObject_IsMovementPaused(avatar->mapObject)"
            not in complete_step
        and "MapObject_IsMovementPaused(follower)"
            not in complete_step
        and walk_commit_start >= 0
        and walk_commit_end > walk_commit_start
        and "OVERWORLD_ACTOR_BOUNDARY_ENGINE_END" in walk_commit
        and "OVERWORLD_MOTION_PHASE_IDLE" in complete_step
        and "OVERWORLD_MOTION_PHASE_SETTLING" in complete_step
        and "OverworldMount_CommitWalkBoundary(avatar)" in complete_step
        and "->terminalWalk(" in walk_commit
        and "ActorSystem_TerminalWalkBoundary(" in actor_source
        and "boundary.walkPolicy = walkPolicy;" in actor_source
        and "ActorSystem_EngineBoundary(&boundary)" in actor_source
        and "walkPolicy == NULL" in actor_source
        and "OVERWORLD_ACTOR_WALK_POLICY_RESULT_PHASE_INDEX" in actor_source
        and "walkPolicy->decision != OVERWORLD_ACTOR_WALK_POLICY_CONSUMED"
            in actor_source
        and "walkPolicy->decision != OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP"
            in actor_source
        and "->commitWalk" not in mount_source
        and "ActorSystem_CommitWalk" not in actor_source
        and "ActorSystem_TryAcknowledgeMotionCommit(" in actor_source
        and "MapObject_StartMovementCommandInternal(follower"
            not in walk_module_source
        and "memcpy(&follower->xPrev, &player->xPrev, 6 * sizeof(int));"
            in field_mount_source
        and "OVERWORLD_MOUNT_FIELD_INPUT_END_MOVEMENT" in on_player_step
        and "OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT" in on_player_step
        and "OVERWORLD_MOUNT_BOUNDARY_FINAL_WRITES_DONE" in on_player_step
        and "state->pendingFieldStep = TRUE;" in on_player_step
        and "OverworldMount_DrainLandStream();" in terminal_retry
        and "OverworldMount_CompletePendingStep(" in terminal_retry
        and terminal_retry.find("OverworldMount_DrainLandStream();")
            < terminal_retry.find("OverworldMount_CompletePendingStep(")
        and 0 <= on_player_step.find("OVERWORLD_MOUNT_OVERLAY_ENTRY->onPlayerStep()")
            < on_player_step.find("OVERWORLD_ACTOR_SYSTEM_ENTRY->inspect"),
        "mounted Walk completion does not use the one real player END",
    )
    require(
        "walkEndState" in mount_internal
        and "walkContinuationReady" not in mount_internal
        and "directionInputHeld" in mount_internal
        and "reservedFollowerCooldown" not in mount_internal
        and "previousToggleDown" not in mount_internal
        and "OVERWORLD_MOUNT_WALK_END_PENDING" not in function_body(
            mount_source, "OverworldMount_OnPlayerStep")
        and "OVERWORLD_WILD_PLAYER_STEP_HANDLER_ADDR" in player_step_bridge
        and player_step_bridge.find(
                "OVERWORLD_WILD_PLAYER_STEP_HANDLER_ADDR"
            )
            < player_step_bridge.find("walkEndState")
        and "if (eventConsumed && fieldSystem == sOverworldMountState.fieldSystem)"
            in player_step_bridge
        and "OVERWORLD_MOUNT_WALK_END_STOP" in player_step_bridge
        and "OVERWORLD_MOUNT_WALK_END_CONTINUATION_READY" in complete_step
        and "OVERWORLD_MOUNT_WALK_END_PENDING" in complete_step
        and "endState & OVERWORLD_MOUNT_WALK_END_PENDING" in complete_step
        and "OVERWORLD_MOUNT_WALK_END_CONTINUATION_READY" in player_control
        and "OVERWORLD_MOUNT_WALK_END_NONE" in player_control
        and "if (((newKeys | heldKeys) & PAD_PLUS_KEY_MASK) == 0)"
            in player_control
        and "if (!sOverworldMountState.directionInputHeld)"
            not in player_control
        and "OverworldMount_ResetMomentum();" not in player_control
        and player_control.find(
            "if (((newKeys | heldKeys) & PAD_PLUS_KEY_MASK) == 0)"
        ) < player_control.find("OverworldMount_TryStartWalkFromInput(")
        and "sOverworldMountState.directionInputHeld" in mount_tick
        and "physicalKeys & PAD_PLUS_KEY_MASK" in mount_tick
        and re.search(
            r"walkEndState = OVERWORLD_MOUNT_WALK_END_NONE;.*?"
            r"OverworldMount_TryStartWalkFromInput\(.*?FALSE\).*?"
            r"OverworldMount_UpdateCustomMotion\(\);.*?"
            r"OverworldMount_SyncPresentation\(\);",
            player_control,
            re.DOTALL,
        ) is not None
        and "walkEndState = OVERWORLD_MOUNT_WALK_END_NONE;" in function_body(
            mount_source, "OverworldMount_DetachPresentation"
        )
        and "walkFinalized" not in mount_tick,
        "mounted Walk continuation is not a one-shot normal-control receipt",
    )
    require(
        "->terminalWalk(" in wild_walk_commit
        and wild_walk_commit.find("->terminalWalk(")
            < wild_walk_commit.find("OVERWORLD_MOTION_PHASE_SETTLING")
            < wild_walk_commit.find(
                "OverworldWildSpawns_ClearCustomJumpLocal(state, slot);"
            ),
        "wild Walk clears shared ownership before the terminal actor commit",
    )
    require(
        "OverworldMount_CommitSharedMotion" not in mount_source
        and "acknowledgedPathAdvance = 0xFFFF" not in mount_source
        and "OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS" not in mount_source
        and re.search(
            r"intent.swayWidth = sOverworldMountState.snapshot.motionMode\s*"
            r"== OVERWORLD_MOUNT_MOTION_WALK\s*\?\s*"
            r"sOverworldMountState.snapshot.profile.walkSwayWidth",
            mount_source,
        ) is not None
        and re.search(
            r"intent.pauseFrames = sOverworldMountState.snapshot.motionMode\s*"
            r"== OVERWORLD_MOUNT_MOTION_WALK\s*\?\s*"
            r"OverworldWildSpawns_ResolveWalkPause\(",
            mount_source,
        ) is not None
        and "memset(&call, 0, sizeof(call));" in mount_source
        and "sample.lastPathAdvance" in mount_source
        and "OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED"
            in sync_presentation
        and "OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED" in sync_presentation
        and "(void)entry->sync(&call);" in sync_presentation
        and "memcpy(follower->posVec, player->posVec"
            in field_mount_source
        and "cardinal Walk remains bound to the normal" in stream_drain
        and "!sOverworldMountState.motionStreamPreparing" in stream_drain
        and "OVERWORLD_ACTOR_BOUNDARY_STREAM_READY" in stream_drain
        and stream_drain.find("OverworldMount_UpdateLandStreamAnchor()")
            < stream_drain.find("OVERWORLD_ACTOR_BOUNDARY_STREAM_READY")
        and "OverworldMount_ClearObjectCommand(player);" in finish_motion
        and "OVERWORLD_ACTOR_BOUNDARY_ENGINE_END" in finish_motion
        and finish_motion.find("OverworldMount_ClearObjectCommand(player);")
            < finish_motion.find("OVERWORLD_ACTOR_BOUNDARY_ENGINE_END")
        and "OVERWORLD_MOTION_PHASE_IDLE" in shared_finalizer
        and "OVERWORLD_MOTION_PHASE_SETTLING" in shared_finalizer
        and "finishedMotion == OVERWORLD_MOUNT_MOTION_WALK"
            in shared_finalizer
        and "OverworldMount_CompletePendingStep(avatar)"
            in shared_finalizer
        and "Only a receipt created by the real player-step bridge"
            in shared_finalizer
        and re.search(
            r"OverworldMount_DrainLandStream\(\);.*?"
            r"OverworldMount_TryFinalizeSharedMotion\(\);.*?"
            r"OverworldMount_SyncPresentation\(\);",
            mount_source,
            re.DOTALL,
        ) is not None,
        "mounted motion bypasses the typed exact engine-boundary protocol",
    )

    print(
        "mount verification passed: "
        f"load=0x{OVERLAY_BASE:08X}, entry=0x{OVERLAY_ENTRY:08X}, "
        f"file=0x{file_size:X}, "
        f"bss=0x{bss_size:X}, free=0x{OVERLAY_LIMIT - load_address - file_size - bss_size:X}"
    )


if __name__ == "__main__":
    main()
