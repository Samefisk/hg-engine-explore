#!/usr/bin/env python3
"""Verify the resident mount controller and its profile-resolution bridge."""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
import subprocess
from pathlib import Path

if __package__:
    from .verify_pokemon_move_history_capture import elf_bytes_at, elf_section_layout, elf_helper_bindings, layout_symbols, current_field_overlay_metadata
else:
    from verify_pokemon_move_history_capture import elf_bytes_at, elf_section_layout, elf_helper_bindings, layout_symbols, current_field_overlay_metadata


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
PLAYER_STEP_RESIDENT_HANDLER = 0x023D9B0D
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
MOUNT_DIAGONAL_TAIL = 0x023BF780
MOUNT_NEWEST_INPUT = 0x023BF790
MOUNT_DIAGONAL_BODY = 0x01FFA000
MOUNT_DIAGONAL_BODY_THUMB = MOUNT_DIAGONAL_BODY | 1
MOUNT_CAPSULE_BASE = 0x01FFF580
MOUNT_BEGIN_ADDRESS = 0x01FFF980
MOUNT_CAPSULE_END = 0x01FFFB80
MOUNT_CONDITIONAL_ADMISSION_CODE = bytes.fromhex(
    "00281cd0002a1cd094460f4a8358002b15d00e4a801802699a4212d1c26863469a420ed102680b68"
    "9a420ad142684b689a4206d182688b689a4202d170470020704701207047c04638090000ac050000"
)
MOUNT_PREVIEW_NAME = "OverworldMount_DeferRawDiagonalGeometry"
FIXED_DIRECT_IMPORTS = {
    "OverworldMount_ClearPlayerPresentation": 0x0205E420,
    "memcpy": 0x023DEEBE,
    "memset": 0x023DEEA2,
    "OverworldActorPolicy_MountCommand": 0x023BA0E0,
    "OverworldMount_ResetMomentum": 0x01FF9AB0,
    "OverworldMount_GetSurfaceId": 0x01FF9A70,
    "OverworldMount_UpdatePlayerBaseHeight": 0x01FF97E0,
    "OverworldMount_ClearFollowerDecisionCooldown": 0x01FF97D0,
    "OverworldMount_GetOrdinaryDirection": 0x01FF9780,
    "OverworldMount_FinalizeIsPending": 0x01FF97C0,
    "OverworldMount_ApplyWalkPolicyOutput": 0x01FF96C0,
    "OverworldMount_FinishOneFrameWalk": 0x023BA0BC,
    "OverworldWalkMount_RebaseMotionTarget": 0x023BFFEA,
    "OverworldWalk_DirectionFromKeys": 0x023BF534,
    "OverworldWalk_SelectNewestMountedInput": MOUNT_NEWEST_INPUT,
    "OverworldWalk_DirectionFromDelta": 0x023BF68C,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"mount verifier: {message}")


def function_body(source: str, name: str) -> str:
    """Return a C function body while skipping prototypes and attributes."""
    identifier = name.rstrip().removesuffix("(").rstrip()
    matches = re.finditer(r"(?<![A-Za-z0-9_])" + re.escape(identifier) + r"\s*\(", source)
    opening = -1
    for match in matches:
        start = match.start()
        opening = source.find("{", start)
        declaration = source.find(";", start)
        if opening >= 0 and (declaration < 0 or opening < declaration):
            break
    else:
        require(False, f"function is missing: {name}")
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


def conditional_admission_contract(source: str, header: str, body: bytes) -> None:
    require(body == MOUNT_CONDITIONAL_ADMISSION_CODE,
            "mounted conditional admission changed its local-mask/context guards")
    require(
        "request) == 0x5AC" in source
        and "sizeof(u32) == 0x938" in source
        and "4: .word 0x00000938" in source
        and "5: .word 0x000005AC" in source
        and re.search(r"OverworldMount_ValidateConditionalAdmission\(\s*"
                      r"const OverworldWildBehaviorConditionRuntime \*conditions,\s*"
                      r"const OverworldWildBehaviorContext \*context,\s*"
                      r"u32 mountedMask\)", source) is not None
        and "Authenticated subject-bank one-bit Mounted mask" in header
        and "u32 mountedMask);" in header,
        "mounted conditional admission lost its typed authenticated-bank mask")


def conditional_admission_fixtures(source: str, header: str) -> None:
    conditional_admission_contract(source, header, MOUNT_CONDITIONAL_ADMISSION_CODE)
    for offset, replacement in (
        (4, bytes.fromhex("c046")),       # Missing local-mask zero guard.
        (0x1A, bytes.fromhex("c046")),    # Missing exact active-mask check.
        (0x22, bytes.fromhex("c046")),    # Missing exact forced local-mask check.
        (0x3A, bytes.fromhex("c046")),    # Missing final current-context word check.
        (0x48, (0x7D0).to_bytes(4, "little")),
        (0x4C, (0x444).to_bytes(4, "little")),
    ):
        mutant = bytearray(MOUNT_CONDITIONAL_ADMISSION_CODE)
        mutant[offset:offset + len(replacement)] = replacement
        try:
            conditional_admission_contract(source, header, bytes(mutant))
        except SystemExit:
            pass
        else:
            require(False, "mounted conditional admission negative control passed")


def stock_player_presentation_cleanup_contract(arm9: bytes, load_address: int) -> None:
    """Authenticate the stock clear-renderer seam used before Field retires heap4."""
    address, size = 0x0205E420, 0x74
    offset = address - load_address
    reference = (REPO / "build/arm9.bin").read_bytes()
    reference_offset = address - 0x02000000
    require(0 <= offset <= len(arm9) - size
            and arm9[offset:offset + size]
                == reference[reference_offset:reference_offset + size],
            "stock player presentation cleanup differs from current ARM9 bytes")
    # Vanilla sub_0205E420 destroys the old graphics callback while its sprite
    # key is intact, clears flag14, then saves INVALID and no-op callbacks.
    for call, target in (
        (0x0205E424, 0x0205F35C),  # MapObject_GetManager
        (0x0205E428, 0x0205F5D4),  # manager graphics active
        (0x0205E436, 0x0205F220),  # object flag14
        (0x0205E440, 0x0205F498),  # current renderer destructor
        (0x0205E44A, 0x0205F214),  # clear flag14
        (0x0205E452, 0x0205F258),  # save INVALID sprite key
        (0x0205E45A, 0x0205F468),
        (0x0205E462, 0x0205F47C),
        (0x0205E46A, 0x0205F490),
        (0x0205E472, 0x0205F4A4),
        (0x0205E47A, 0x0205F4B8),
    ):
        require(decode_thumb_bl(arm9, load_address, call) == target,
                "stock player presentation cleanup changed its native call order")
    require(struct.unpack_from("<5I", arm9, 0x0205E480 - load_address)
            == (0xFFFF, 0x0205FCC5, 0x0205FCC9, 0x0205FCCD, 0x0205FCD1),
            "stock player presentation cleanup changed its INVALID/no-op keys")


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


def action_switch_import_contract(source: str, imported: tuple | None,
                                  linked: dict, calls: list) -> None:
    # The shared START/TICK arm fits the native switch in an unsigned-byte
    # table. Keep its one call direct and typed; an untyped alias adds a veneer.
    name, target = "__gnu_thumb1_case_uqi", 0x023DEE54
    alias = linked.get(name)
    require(f".thumb_func\\n.thumb_set {name}, 0x{target:08X}\\n" in source
            and imported == (target, 0, "*ABS*", "F")
            and alias is not None and alias[2] == "*ABS*"
            and alias[0] & ~1 == target
            and not any(symbol.startswith(f"__{name}_from_") for symbol in linked),
            "mounted Action switch lost its direct Thumb case helper")
    require(len(calls) == 1, "mounted Action switch lacks its one direct case-helper caller")
    for kind, linked_code, packaged_code, address in calls:
        fixed_import_call_contract(kind, linked_code, packaged_code, address, target)


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
         ".overworld_mount_landing_allowed", 0x40, 0),
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
    dispatch = resident.get("OverworldMountActionAdapter_Dispatch")
    original_dispatch = action_imports.get("OverworldMountActionAdapter_Dispatch")
    require(dispatch is not None and original_dispatch is not None
            and dispatch[0] == 0x01FF8800 and dispatch[3] == original_dispatch[3] == "F"
            and original_dispatch[2] == ".overworld_mount_action_entry",
            "mounted Action switch dispatcher layout differs")
    switch_calls = []
    for offset, kind in re.findall(
            r"([0-9a-fA-F]+)\s+(R_ARM_\w+)\s+\*ABS\*0x23dee54\b",
            action_relocations, re.IGNORECASE):
        call_at = dispatch[0] + int(offset, 16) - original_dispatch[0]
        require(dispatch[0] <= call_at <= dispatch[0] + dispatch[1] - 4,
                "mounted Action case-helper caller lies outside its dispatcher")
        packaged_offset = call_at - action_base
        switch_calls.append((kind, elf_bytes_at(linked_path, call_at, 4),
                             packaged[packaged_offset:packaged_offset + 4], call_at))
    action_switch_import_contract(admission_source,
        action_imports.get("__gnu_thumb1_case_uqi"), resident, switch_calls)
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
        require(len(matches) == 1,
                f"mounted Walk {name} lacks its direct Thumb caller")
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
    conditional_admission_contract(admission_source, admission_header,
        elf_bytes_at(linked_path, admission_address, admission[1]))
    conditional_admission_fixtures(admission_source, admission_header)
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


def preview_capsule_contract(original: dict, linked: dict, source: str,
                             linker: str, linked_body: bytes,
                             packaged_body: bytes) -> tuple[int, int]:
    """Bind the private preview's object section to its resident code bytes."""
    begin = linked.get("OverworldMount_Begin")
    original_preview = original.get(MOUNT_PREVIEW_NAME)
    preview = linked.get(MOUNT_PREVIEW_NAME)
    require(begin is not None and begin[0] == MOUNT_BEGIN_ADDRESS
            and 0 < begin[1] <= 0x200,
            "resident Begin entry moved or exceeded its capsule")
    require(original_preview is not None
            and original_preview[0] == 0
            and original_preview[1] > 0
            and original_preview[2:] == (".overworld_mount_preview", "F")
            and preview is not None
            and preview[1] == original_preview[1]
            and preview[2:] == (".overworld_mount_combat", "F"),
            "preview helper changed object section, body, or linked section")
    address, size = preview[:2]
    require(begin[0] + begin[1] <= address
            and address + size <= MOUNT_CAPSULE_END,
            "preview helper lies outside the resident capsule after Begin")
    require("KEEP(*(.overworld_mount_preview))" in linker
            and re.search(r"section\(\"\.overworld_mount_preview\"\)\)\)\s*"
                          + MOUNT_PREVIEW_NAME + r"\s*\(", source) is not None,
            "preview helper lost its resident section binding")
    body = function_body(source, MOUNT_PREVIEW_NAME)
    require("OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT" in body
            and "reduceWalk(&call)" in body,
            "preview helper lost its policy preview body")
    require(len(linked_body) == size and linked_body == packaged_body,
            "preview helper differs from resident capsule bytes")
    return address, size


def carrier_hit_capsule_contract(symbol, linked_body: bytes, packaged_body: bytes,
                                 caller: str, resident_tail: bytes = b"") -> None:
    require(symbol is not None and symbol[0] == 0x01FFF800
            and 0 < symbol[1] <= 0x180
            and symbol[2:] == (".overworld_wild_carrier_hit", "F")
            and len(linked_body) == symbol[1]
            and symbol[1] + len(resident_tail) <= 0x180
            and packaged_body == linked_body + resident_tail
                + bytes(0x180 - symbol[1] - len(resident_tail))
            and re.search(r"\bbl\s+1fff800\s+<OverworldWildSpawns_PrepareCarrierHit>", caller),
            "private carrier hit leaf has wrong address, extent, bytes or Thumb call")


def retained_mask_capsule_contract(symbol, linked_body: bytes, packaged_body: bytes,
                                   caller: str) -> None:
    require(symbol == (0x01FFF930, 28, ".overworld_wild_carrier_hit", "F")
            and len(linked_body) == 28
            and hashlib.sha256(linked_body).hexdigest()
                == "1edbd1908da0b08504c7de4f948799ab0d1940b3ebc83333bb2e0e8394c280b0"
            and packaged_body[0x130:0x14C] == linked_body
            and re.search(r"\b23d47ec:\s+[0-9a-f]+\s+[0-9a-f]+\s+bl\s+1fff930\s+"
                          r"<OverworldWildSpawns_RetainedMaskNamesActiveSpawns>", caller),
            "private retained mask leaf has wrong address, extent, bytes or Thumb call")


def retained_mask_call_owner_contract(symbol, binding, linked_body: bytes,
                                      packaged_body: bytes) -> None:
    """The reviewed T65 caller moved; its private leaf and target did not."""
    require(symbol == (0x023D4658, 1072, ".text", "F")
            and binding is not None and binding[:3] == (0x023D4659, 1072, "FUNC")
            and binding[3].isdigit() and int(binding[3]) > 0
            and len(linked_body) == 1072 and packaged_body == linked_body
            and hashlib.sha256(linked_body).hexdigest()
                == "52e9bb21680c42cea57add6b23976334dfebb99d76e80f2165900b8f306fcc81"
            and decode_thumb_bl(linked_body, 0x023D4658, 0x023D47EC) == 0x01FFF930,
            "private retained mask caller lost its exact Thumb owner, body, package or target")


def verify_fixed_direct_imports(packaged: bytes, capsules: bytes,
                                inspect_packaged: bytes) -> None:
    linked_path = REPO / "build/overworld_mount_overlay_linked.o"
    object_path = REPO / "build/overworld_mount_overlay/overworld_mount_overlay.o"
    linked = layout_symbols(linked_path, "arm-none-eabi-objdump")
    original = layout_symbols(object_path, "arm-none-eabi-objdump")
    inspect = linked.get("OverworldMount_InspectPolicy")
    require(inspect == (0x01FFA4E0, 12, ".overworld_mount_private_inspect", "F")
            and original.get("OverworldMount_InspectPolicy")
                == (0, 12, ".overworld_mount_private_inspect", "F")
            and inspect_packaged == elf_bytes_at(linked_path, 0x01FFA4E0, 12),
            "private policy inspect has wrong owner, extent or packaged bytes")
    source = (REPO / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text()
    linker = (REPO / "src/overworld_mount_overlay/linker.ld").read_text()
    preview = linked.get(MOUNT_PREVIEW_NAME)
    require(preview is not None, "resident preview helper is missing")
    preview_bytes = elf_bytes_at(linked_path, preview[0], preview[1])
    preview_packaged = capsules[
        preview[0] - MOUNT_CAPSULE_BASE:
        preview[0] - MOUNT_CAPSULE_BASE + preview[1]]
    preview_capsule_contract(original, linked, source, linker,
                             preview_bytes, preview_packaged)
    for mutant_original, mutant_linked, mutant_source, mutant_bytes in (
        ({**original, MOUNT_PREVIEW_NAME:
            (0, preview[1], ".text", "F")}, linked, source, preview_packaged),
        (original, {**linked, MOUNT_PREVIEW_NAME:
            (MOUNT_CAPSULE_END - preview[1] + 1, preview[1],
             ".overworld_mount_combat", "F")}, source, preview_packaged),
        (original, linked, source.replace(
            "OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT",
            "OVERWORLD_ACTOR_WALK_POLICY_INPUT"), preview_packaged),
        (original, linked, source,
         bytes([preview_packaged[0] ^ 1]) + preview_packaged[1:]),
    ):
        try:
            preview_capsule_contract(mutant_original, mutant_linked,
                                     mutant_source, linker, preview_bytes,
                                     mutant_bytes)
        except SystemExit:
            pass
        else:
            require(False, "wrong preview section, body, range, or bytes passed")
    for name, target in FIXED_DIRECT_IMPORTS.items():
        imported = linked.get(name)
        require(original.get(name) == (target, 0, "*ABS*", "F")
                and imported is not None and imported[2] == "*ABS*"
                and imported[0] & ~1 == target,
                f"{name} changed its direct import or gained a local body")
        require(not any(symbol.startswith(f"__{name}_from_") for symbol in linked),
                f"{name} gained a redundant interworking veneer")
    restore_names = [name for name in linked
                     if name.startswith("OverworldMount_RestorePlayerSprite")]
    require(len(restore_names) == 1, "Mount sprite cleanup has no unique private body")
    restore_name = restore_names[0]
    restore = linked[restore_name]
    ground = linked["OverworldMount_GroundHitCrash"]
    require(ground[0] == 0x01FFF700
            and restore[2:] == (".overworld_mount_combat_tail", "F")
            and ground[0] + ground[1] <= restore[0]
            and 0 < restore[1] <= 0x01FFF800 - restore[0]
            and struct.pack("<I", 0x0205F259) in elf_bytes_at(
                linked_path, restore[0], restore[1])
            and struct.pack("<I", 0x021FA931) in elf_bytes_at(
                linked_path, restore[0], restore[1]),
            "Mount sprite cleanup moved Ground or changed its typed stock restore targets")
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
        if section in (".overworld_mount_combat", ".overworld_mount_preview",
                       ".overworld_mount_combat_tail"):
            body_name = {
                ".overworld_mount_combat": "OverworldMount_Begin",
                ".overworld_mount_preview": MOUNT_PREVIEW_NAME,
                ".overworld_mount_combat_tail": "OverworldMount_GroundHitCrash",
            }[section]
            if (section == ".overworld_mount_combat_tail"
                    and target == FIXED_DIRECT_IMPORTS["OverworldMount_ClearPlayerPresentation"]):
                body_name = restore_name
            body_start, body_size = linked[body_name][:2]
            require(body_start <= address <= body_start + body_size - 4,
                    "fixed import caller lies outside its resident body")
            offset = address - MOUNT_CAPSULE_BASE
            packaged_call = capsules[offset:offset + 4]
        elif section == ".overworld_mount_private_inspect":
            require(0x01FFA4E0 <= address <= 0x01FFA4EC - 4,
                    "fixed import caller lies outside its private policy inspect body")
            offset = address - 0x01FFA4E0
            packaged_call = inspect_packaged[offset:offset + 4]
        else:
            offset = address - OVERLAY_BASE
            packaged_call = packaged[offset:offset + 4]
        fixed_import_call_contract(call.group(2), elf_bytes_at(linked_path, address, 4),
                                   packaged_call, address, target)
        counts[target] += 1
    require(all(counts.values()), "a fixed direct import has no verified compiled caller")


def verify_chain_mount_imports() -> None:
    """The separately linked chain adapter must call current mount code."""
    mount = layout_symbols(REPO / "build/overworld_mount_overlay_linked.o",
                           "arm-none-eabi-objdump")
    chain = layout_symbols(REPO / "build/overworld_mount_chain_overlay_linked.o",
                           "arm-none-eabi-objdump")
    typed_motion = elf_helper_bindings(
        REPO / "build/overworld_mount_chain_overlay_linked.o",
        ("OverworldMount_TryStartCustomMotion",))
    source = (REPO / "src/overworld_mount_chain_overlay/overworld_mount_chain_overlay.c").read_text()
    linker = (REPO / "src/overworld_mount_chain_overlay/linker.ld").read_text()
    for imported, implementation in (
        ("OverworldMount_ProcessPlayerControl", "OverworldMount_ProcessPlayerControl"),
        ("OverworldMount_TryStartCustomMotion", "OverworldMount_TryStartCustomMotion.constprop.0"),
        ("OverworldMount_GetInputDirection", "OverworldMount_GetInputDirection"),
    ):
        actual = mount.get(implementation)
        alias = chain.get(imported)
        matches = (alias is not None and alias[0] == actual[0] | 1
                   and alias[2] == "*ABS*") if actual is not None else False
        if imported == "OverworldMount_TryStartCustomMotion" and actual is not None:
            # Objdump clears a FUNC symbol's Thumb bit in its display. Read
            # st_value for this unique typed import instead.
            matches = typed_motion.get(imported) == (actual[0] | 1, 0, "FUNC", "ABS")
        require(actual is not None and alias is not None
                and actual[3] == "F" and actual[1] > 0
                and matches,
                f"mounted chain import {imported} misses its current mount body")
        address = f"0x{actual[0]:08X}"
        require(f".thumb_set {imported}, {address}" in source
                and f"{imported} = {address} | 1;" in linker,
                f"mounted chain import {imported} source/linker differs")


def mounted_diagonal_tail_contract(stub: tuple | None, body: tuple | None,
                                   linked_stub: bytes, packaged_stub: bytes,
                                   linked_body: bytes, packaged_body: bytes) -> None:
    """The public four-argument tail must preserve r3 on its Thumb jump."""
    require(stub == (MOUNT_DIAGONAL_TAIL, 16, ".walk_helpers", "F"),
            "mounted diagonal tail moved, changed mode, or lost its 16-byte body")
    require(body is not None and body[0] == MOUNT_DIAGONAL_BODY
            and 0 < body[1] <= 0xF0
            and body[2:] == (".overworld_mount_gait", "F"),
            "mounted diagonal resolver body moved or changed type")
    expected = bytes((0x08, 0xB4, 0x02, 0x4B, 0x9C, 0x46,
                      0x08, 0xBC, 0x60, 0x47, 0xC0, 0x46)) \
        + MOUNT_DIAGONAL_BODY_THUMB.to_bytes(4, "little")
    require(linked_stub == expected and packaged_stub == linked_stub,
            "mounted diagonal tail lost r3 or differs from packaged Thumb code")
    require(len(linked_body) == body[1] and packaged_body == linked_body,
            "mounted diagonal resolver body differs from packaged code")


def newest_mounted_input_contract(original: tuple | None,
                                  linked: tuple | None, linked_code: bytes,
                                  packaged_code: bytes) -> None:
    require(original is not None and original[0] == 0
            and 0 < original[1] <= 0xB0
            and original[2:] == (".overworld_walk_newest_mounted_input", "F")
            and linked is not None
            and linked[0] == MOUNT_NEWEST_INPUT
            and linked[1] == original[1]
            and linked[2:] == (".walk_helpers", "F"),
            "newest mounted input helper lost its fixed Thumb code slot")
    require(len(linked_code) == linked[1] and linked_code == packaged_code,
            "newest mounted input helper differs from packaged code")


def verify_mounted_diagonal_tail(rom: bytes, fat_offset: int,
                                 y9_offset: int) -> None:
    walk_elf = REPO / "build/pokemon_move_history_overlay_linked.o"
    chain_elf = REPO / "build/overworld_mount_chain_overlay_linked.o"
    stub = layout_symbols(walk_elf, "arm-none-eabi-objdump").get(
        "OverworldWalk_ResolveMountedDiagonal")
    body = layout_symbols(chain_elf, "arm-none-eabi-objdump").get(
        "OverworldMount_ResolveMountedDiagonalBody")
    require(stub is not None and body is not None,
            "mounted diagonal tail or private resolver body is missing")

    def package(overlay_id: int, load: int, address: int,
                size: int) -> bytes:
        row = struct.unpack_from("<8I", rom, y9_offset + overlay_id * 0x20)
        start, end = struct.unpack_from("<2I", rom,
                                      fat_offset + row[6] * 8)
        offset = address - load
        require(row[0] == overlay_id and row[1] == load
                and end - start == row[2]
                and 0 <= offset <= row[2] - size,
                "mounted diagonal code is outside its packaged overlay")
        return rom[start + offset:start + offset + size]

    linked_stub = elf_bytes_at(walk_elf, MOUNT_DIAGONAL_TAIL, 16)
    linked_body = elf_bytes_at(chain_elf, MOUNT_DIAGONAL_BODY, body[1])
    packaged_stub = package(153, 0x023BE400, MOUNT_DIAGONAL_TAIL, 16)
    packaged_body = package(159, 0x01FF9800, MOUNT_DIAGONAL_BODY, body[1])
    mounted_diagonal_tail_contract(stub, body, linked_stub, packaged_stub,
                                   linked_body, packaged_body)
    old_stub = bytes((0x00, 0x4B, 0x18, 0x47)) \
        + MOUNT_DIAGONAL_BODY_THUMB.to_bytes(4, "little")
    for bad_stub, bad_body, bad_linked, bad_packaged, bad_body_bytes in (
        ((MOUNT_DIAGONAL_TAIL, 8, ".walk_helpers", "F"), body,
         old_stub, old_stub, packaged_body),
        (stub, body, old_stub + linked_stub[8:],
         old_stub + linked_stub[8:], packaged_body),
        (stub, body, linked_stub[:-4] + (MOUNT_DIAGONAL_BODY_THUMB + 2).to_bytes(4, "little"),
         packaged_stub, packaged_body),
        (stub, body, linked_stub, bytes([packaged_stub[0] ^ 1]) + packaged_stub[1:],
         packaged_body),
        (stub, (MOUNT_DIAGONAL_BODY + 2, body[1], body[2], body[3]),
         linked_stub, packaged_stub, packaged_body),
        (stub, body, linked_stub, packaged_stub,
         bytes([packaged_body[0] ^ 1]) + packaged_body[1:]),
    ):
        try:
            mounted_diagonal_tail_contract(bad_stub, bad_body, bad_linked,
                                           bad_packaged, linked_body,
                                           bad_body_bytes)
        except SystemExit:
            pass
        else:
            require(False, "bad mounted diagonal tail passed its negative control")

    helper_name = "OverworldWalk_SelectNewestMountedInput"
    walk_object = REPO / "build/pokemon_move_history_overlay/overworld_walk_module.o"
    walk_source = (REPO / "src/pokemon_move_history_overlay/overworld_walk_module.c").read_text()
    walk_linker = (REPO / "src/pokemon_move_history_overlay/linker.ld").read_text()
    walk_original = layout_symbols(walk_object, "arm-none-eabi-objdump")
    walk_linked = layout_symbols(walk_elf, "arm-none-eabi-objdump")
    original_helper = walk_original.get(helper_name)
    helper = walk_linked.get(helper_name)
    require(helper is not None, "newest mounted input helper is missing")
    helper_bytes = elf_bytes_at(walk_elf, MOUNT_NEWEST_INPUT, helper[1])
    helper_package = package(153, 0x023BE400, MOUNT_NEWEST_INPUT, helper[1])
    newest_mounted_input_contract(original_helper, helper,
                                  helper_bytes, helper_package)
    require('section(".overworld_walk_newest_mounted_input")' in walk_source
            and "KEEP(*(.overworld_walk_newest_mounted_input))" in walk_linker
            and "== ORIGIN(rom) + 0x1390" in walk_linker,
            "newest mounted input lost its fixed source/linker binding")
    for bad_original, bad_linked, bad_package in (
        ((0, helper[1], ".text", "F"), helper, helper_package),
        (original_helper,
         (MOUNT_NEWEST_INPUT + 2, helper[1], ".walk_helpers", "F"),
         helper_package),
        (original_helper, helper,
         bytes([helper_package[0] ^ 1]) + helper_package[1:]),
    ):
        try:
            newest_mounted_input_contract(bad_original, bad_linked,
                                          helper_bytes, bad_package)
        except SystemExit:
            pass
        else:
            require(False, "bad newest mounted input helper passed its control")

    chain_object = REPO / "build/overworld_mount_chain_overlay/overworld_mount_chain_overlay.o"
    chain_original = layout_symbols(chain_object, "arm-none-eabi-objdump")
    chain_linked = layout_symbols(chain_elf, "arm-none-eabi-objdump")
    chain_source = (REPO / "src/overworld_mount_chain_overlay/overworld_mount_chain_overlay.c").read_text()
    chain_entry = chain_linked.get("OverworldMount_ChainControl")
    original_entry = chain_original.get("OverworldMount_ChainControl")
    mount_source = (REPO / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text()
    require(chain_original.get(helper_name) == (MOUNT_NEWEST_INPUT, 0, "*ABS*", "F")
            and chain_linked.get(helper_name) is not None
            and chain_linked[helper_name][0] & ~1 == MOUNT_NEWEST_INPUT
            and chain_linked[helper_name][2:] == ("*ABS*", "F")
            and f".thumb_func\\n.thumb_set {helper_name}, 0x{MOUNT_NEWEST_INPUT:08X}\\n"
                in chain_source
            and not any(name.startswith(f"__{helper_name}_from_")
                        for name in chain_linked)
            and chain_entry is not None and original_entry is not None
            and original_entry[2:] == (".overworld_mount_chain_entry", "F")
            and chain_entry[2:] == (".text", "F")
            and f"{helper_name}(state, &newKeys, &heldKeys);" in
                function_body(chain_source, "OverworldMount_ChainControl")
            and f"{helper_name}(" in
                function_body(mount_source, "OverworldMount_Tick"),
            "mounted Chain lost its direct newest-input Thumb import")
    relocations = subprocess.check_output(
        ["arm-none-eabi-objdump", "-r", str(chain_object)], text=True)
    section = None
    calls = []
    for line in relocations.splitlines():
        heading = re.match(r"RELOCATION RECORDS FOR \[(.+)\]:", line)
        if heading:
            section = heading.group(1)
            continue
        call = re.match(
            rf"([0-9a-fA-F]+)\s+(R_ARM_\w+)\s+\*ABS\*0x{MOUNT_NEWEST_INPUT:x}\b",
            line, re.IGNORECASE)
        if call:
            require(section == ".overworld_mount_chain_entry",
                    "newest input call moved outside mounted Chain entry")
            calls.append((int(call.group(1), 16), call.group(2)))
    require(len(calls) == 1,
            "mounted Chain lacks one direct newest-input caller")
    call_at = chain_entry[0] + calls[0][0] - original_entry[0]
    require(chain_entry[0] <= call_at <= chain_entry[0] + chain_entry[1] - 4,
            "newest input call lies outside mounted Chain body")
    fixed_import_call_contract(
        calls[0][1], elf_bytes_at(chain_elf, call_at, 4),
        package(159, 0x01FF9800, call_at, 4), call_at, MOUNT_NEWEST_INPUT)


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
    hop_request = compact(function_body(action, "OverworldMountAction_RequestHopPlan"))
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
        (start, "frames = sOverworldMountState.walkEndState == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP ? (u32)lane->hopTime * distance : trajectory & 0xFFFF;"),
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
        (hop, "if (OverworldMountAction_RequestHopPlan(&hopPlan) != OVERWORLD_MOTION_DECISION_ACCEPTED) { return FALSE; }"),
        (hop_request, "request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_HOP;"),
        (hop_request, "request.hopPlan = hopPlan;"),
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
    for code in (hop_request, teleport):
        for expected in (
            "request.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;",
            "request.size = sizeof(request);",
        ):
            require(compact(expected) in code, "mounted planner does not validate the Actor Motion ABI result")
    require(compact("result = OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&request);") in hop_request
            and compact("if (result != OVERWORLD_ACTOR_RESULT_OK) { return result == OVERWORLD_ACTOR_RESULT_RETRY ? OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY : OVERWORLD_MOTION_DECISION_PROFILE; }") in hop_request
            and compact("return request.decision;") in hop_request,
            "mounted Hop request lost its checked Actor Motion result")
    require(compact("if (OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&request) != OVERWORLD_ACTOR_RESULT_OK || request.decision != OVERWORLD_MOTION_DECISION_ACCEPTED) { return FALSE; }") in teleport,
            "mounted Teleport planner does not validate the Actor Motion ABI result")
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
        ("action", "OverworldMountAction_RequestHopPlan(&hopPlan)\n            != OVERWORLD_MOTION_DECISION_ACCEPTED", "FALSE"),
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


def mounted_finish_body(actor: str, runtime: str) -> str:
    """Follow the facade wrapper to its boot-resident Walk implementation."""
    wrapper = function_body(actor, "ActorSystem_FinishMountedWalk")
    require(
        "returnOverworldMountWalkProposal_Finish(state,started,crashOnBlocked,output);"
        in re.sub(r"\s+", "", wrapper),
        "mounted Walk facade does not call the shared completion implementation",
    )
    return function_body(runtime, "OverworldMountWalkProposal_Finish")


def mounted_proposal_transport_contract(actor: str, walk: str, runtime: str,
                                        helpers: str) -> None:
    """All mounted proposal paths preserve nominal time and Linear state."""
    finish = mounted_finish_body(actor, runtime)
    filtered = function_body(walk, "OverworldWalk_FilterMountedInput")
    save_proposal = function_body(runtime, "Walk_MountSaveProposal")
    apply_output = function_body(helpers, "OverworldMount_ApplyWalkPolicyOutput")
    save = function_body(runtime, "OverworldMountWalkProposal_SaveReserved")
    restore = function_body(runtime, "OverworldMountWalkProposal_RestoreReserved")
    compact_finish = re.sub(r"\s+", "", finish)
    compact_save = re.sub(r"\s+", "", save)
    compact_restore = re.sub(r"\s+", "", restore)
    require(
        "OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX" in filtered
        and "call.reserved[0]" in filtered
        and "state->reservedPolicyProfile[OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX]"
            "=call->reserved[0];" in re.sub(r"\s+", "", apply_output)
        and "output->reserved[0]=state->reservedPolicyProfile["
            "OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX];" in compact_finish,
        "mounted Walk does not preserve nominal policy time through START_RESULT",
    )
    require(
        "OverworldMountWalkProposal_SaveReserved(policyCall);" in save_proposal
        and "OverworldMountWalkProposal_SaveReserved(call);" in apply_output
        and "OverworldMountWalkProposal_RestoreReserved(output);" in finish
        and "OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[0]=call->reserved[1];" in compact_save
        and "OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[1]=call->reserved[2];" in compact_save
        and "call->reserved[1]=OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[0];" in compact_restore
        and "call->reserved[2]=OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[1];" in compact_restore,
        "mounted Walk does not preserve Linear carry and turn elapsed through START_RESULT",
    )


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
    mounted_finish = mounted_finish_body(actor, runtime)
    walk_input = re.sub(r"\s+", "", function_body(
        runtime, "OverworldActorWalkPolicy_ReduceInput"))
    skid_picker = re.sub(r"\s+", "", function_body(
        runtime, "OverworldWalk_ProfileSkidTiles"))
    save = re.sub(r"\s+", "", function_body(
        runtime, "OverworldMountWalkProposal_SaveReserved"))
    require(
        "visibleSpeed=policy->lastWalkTime!=0?policy->lastWalkTime:state->speed;"
            in walk_input
        and "OverworldWalk_ProfileSkidTiles(visibleSpeed,call->lane,TRUE)"
            in walk_input
        and "OverworldWalk_ProfileSkidTiles(visibleSpeed,call->lane,FALSE)"
            in walk_input
        and "OverworldWalkTimingPolicy_ProfileSkidTiles(time,"
            "OW_WILD_BEHAVIOR_TURN_SKID_ONE_TIME(lane),"
            "OW_WILD_BEHAVIOR_TURN_SKID_TWO_TIME(lane),"
            "OW_WILD_BEHAVIOR_STOP_SKID_TIME(lane),stop);" in skid_picker
        and "OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[2]=call->distance;" in save
        and "output->distance=OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[2];"
            in re.sub(r"\s+", "", mounted_finish)
        and "OverworldWalk_SkidTiles(" not in mounted_finish,
        "mounted skid distance does not retain the profile INPUT proposal "
        "from the last displayed Walk time")
    mounted_input = function_body(walk, "OverworldWalk_FilterMountedInput")
    mounted_commit = function_body(mount, "OverworldMount_CommitWalkBoundary")
    require("OverworldWalkPolicy_Memset(output, 0, sizeof(*output));" in mounted_finish
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
        (3, "OverworldWalkPolicy_Memset(output, 0, sizeof(*output));", "/* missing initialization */"),
        (3, "if ((call->flags & OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED) == 0",
         "if ((call->flags & OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED) != 0"),
        (3, "OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[2] = call->distance;",
         "OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[2] = call->travelTime;"),
        (3, "output->distance = OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[2];",
         "output->distance = OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[1];"),
        (3, "output->distance = OVERWORLD_MOUNT_WALK_PROPOSAL_RESERVED[2];",
         "output->distance = OverworldWalk_SkidTiles(policy->lastWalkTime);"),
        (3, "? policy->lastWalkTime : state->speed;",
         "? state->speed : state->speed;"),
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
        "&&!OverworldMount_DeferRawDiagonalGeometry(*newKeys|*heldKeys)"
        "&&OverworldWalk_ResolveMountedDiagonal("
        "&sOverworldMountState,avatar,newKeys,heldKeys)!=0){returnTRUE;}"
    )
    tail = (
        "OverworldMount_FilterMovementInput(avatar,newKeys,heldKeys);"
        "returnOverworldMount_TryHandleDiagonalWalk("
        "avatar,*newKeys,*heldKeys,advanceFirstFrame);"
    )
    require(compact == guard + tail,
            "mounted diagonal admission must defer due skids before raw geometry, "
            "preserve ordinary rejection and locked direction, and retain cardinal normalization")


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
        body.replace("&& !OverworldMount_DeferRawDiagonalGeometry(*newKeys | *heldKeys)",
                     "", 1),
        body.replace("&& !OverworldMount_DeferRawDiagonalGeometry(*newKeys | *heldKeys)",
                     "&& OverworldMount_DeferRawDiagonalGeometry(*newKeys | *heldKeys)", 1),
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


def mounted_profile_source_contract(spawns: str, mount_begin: str) -> None:
    mounted_profile_snapshot = (
        re.search(
            r"GetBehaviorProfileAndPrimitivesForSlot\(\s*state,\s*"
            r"OW_WILD_FOLLOWER_SLOT,\s*&resolution\.profile,\s*"
            r"&resolution\.primitives\s*\);.*?"
            r"EvaluateConditionsForSlot\(\s*state,\s*fieldSystem,\s*"
            r"OW_WILD_FOLLOWER_SLOT,\s*&resolution\.profile,\s*"
            r"&resolution\.primitives,\s*-1\).*?"
            r"OW_WILD_CONDITION_RESULT_FAIL_CLOSED\).*?"
            r"ResolveBehaviorProfileForContext\(\s*"
            r"&conditions->request\.context,\s*"
            r"OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_MOUNTED,\s*"
            r"NULL,\s*&resolution\s*\)",
            mount_begin,
            re.DOTALL,
        )
        is not None
        and re.search(
            r"if \(spawn != NULL && spawn->active\).*?"
            r"terrain = spawn->terrain;",
            spawns,
            re.DOTALL,
        )
        is not None
        and re.search(
            r"policyTransaction\.next\.behaviorFingerprint\s*=\s*"
            r"resolution\.fingerprint;.*?"
            r"policyTransaction\.next\.matchedLayerMask\s*=\s*"
            r"resolution\.matchedClassRuleMask\s*"
            r"\| resolution\.appliedOverrideMask;.*?"
            r"OVERWORLD_MOUNT_OVERLAY_ENTRY->begin\(\s*"
            r"fieldSystem,\s*&binding,\s*&resolution\.profile,\s*"
            r"\(const OverworldWildSurfaceCatalog \*\)"
            r"behaviorData->surfaceModels,\s*"
            r"&policyTransaction\)\)\s*\{\s*"
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


def mounted_profile_source_fixtures(spawns: str, mount_begin: str) -> None:
    mounted_profile_source_contract(spawns, mount_begin)
    for old, new in (
        ("ResolveBehaviorProfileForContext(", "LostMountedResolve("),
        ("&conditions->request.context,", "&wrongContext,"),
        ("OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_MOUNTED,",
         "1u << OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_MOUNTED,"),
        ("OVERWORLD_MOUNT_OVERLAY_ENTRY->begin(", "LostMountedBind("),
        ("NULL,", "&conditions->request,"),
    ):
        require(old in mount_begin, f"Mounted context negative control no longer applies: {old}")
        try:
            mounted_profile_source_contract(spawns, mount_begin.replace(old, new))
        except SystemExit:
            pass
        else:
            require(False, f"Mounted context negative control passed: {old}")


def ground_probe_source_contract(runtime: str) -> None:
    ground = function_body(runtime, "OverworldWildRuntime_GetGroundBaseY")
    resolver = function_body(runtime, "OverworldWildRuntime_ResolveBaseYAt")
    compact_ground = re.sub(r"\s+", "", ground)
    compact_resolver = re.sub(r"\s+", "", resolver)
    require(
        "s32baseY=(s32)object->posVec[1];" in compact_ground
        and "OverworldWildRuntime_QuerySurface(fieldSystem,catalog,x,y,&hit)" in compact_ground
        and "knownSurface=&hit;" in compact_ground
        and "OverworldWildRuntime_ResolveBaseYAt(fieldSystem,knownSurface,"
            "baseY,object->flags,x,y,&baseY);returnbaseY;" in compact_ground
        and "VecFx32position;" in compact_resolver
        and "position.y=originBaseY;" in compact_resolver
        and "if(!OW_WILD_RUNTIME_QUERY_NATIVE_HEIGHT(fieldSystem,&position,"
            "(objectFlags&MAPOBJECTFLAG_UNK29)!=0))returnFALSE;" in compact_resolver
        and "*output=position.y+(knownSurface!=NULL?knownSurface->height:0);" in compact_resolver
        and re.search(r"object->posVec\[\d+\](?:=|\+=|-=|\+\+|--)", compact_ground) is None
        and "posVec" not in resolver,
        "mounted ground-height probe mutates the live render object or loses its shared owner",
    )


def ground_probe_source_fixtures(runtime: str) -> None:
    ground_probe_source_contract(runtime)
    for old, new in (
        ("baseY,object->flags,x,y,&baseY", "baseY,object->flags,x,y,NULL"),
        ("OW_WILD_RUNTIME_QUERY_NATIVE_HEIGHT(fieldSystem, &position,", "LostNativeHeight(fieldSystem, &position,"),
        ("return baseY;", "object->posVec[0] = 0; return baseY;"),
        ("return baseY;", "object->posVec[1] = 0; return baseY;"),
        ("return baseY;", "object->posVec[2] = 0; return baseY;"),
    ):
        require(old in runtime, f"ground-height negative control no longer applies: {old}")
        try:
            ground_probe_source_contract(runtime.replace(old, new))
        except SystemExit:
            pass
        else:
            require(False, f"ground-height negative control passed: {old}")


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
    health_row = struct.unpack_from("<8I", rom, y9_offset + 161 * 0x20)
    health_start, health_end = struct.unpack_from(
        "<2I", rom, fat_offset + health_row[6] * 8)
    capsules = (REPO / "build/overworld_combat_capsules.bin").read_bytes()
    require(
        health_row[1] == 0x01FFA580 and len(capsules) == 0x600
        and health_start + 0x5600 <= health_end
        and rom[health_start + 0x5000:health_start + 0x5600] == capsules,
        "resident actor capsules differ from their linked package",
    )
    wild_elf = REPO / "build/overworld_wild_spawns_overlay_linked.o"
    hit_adapter = layout_symbols(wild_elf, "arm-none-eabi-objdump").get(
        "OverworldWildSpawns_ApplyQueuedCombat")
    require(
        hit_adapter is not None and hit_adapter[0] == 0x01FFFB80
        and 0 < hit_adapter[1] <= 0x3A0
        and hit_adapter[2:] == (".overworld_wild_combat_tail", "F")
        and health_row[2] == 0x5A80
        and health_start + 0x5A80 == health_end
        and rom[health_start + 0x5600:health_start + 0x5600 + hit_adapter[1]]
            == elf_bytes_at(wild_elf, hit_adapter[0], hit_adapter[1]),
        "resident Wild hit adapter differs from its linked package",
    )
    carrier = layout_symbols(wild_elf, "arm-none-eabi-objdump").get(
        "OverworldWildSpawns_PrepareCarrierHit")
    require(carrier is not None, "private carrier hit leaf missing")
    carrier_body = elf_bytes_at(wild_elf, carrier[0], carrier[1])
    carrier_package = capsules[0x280:0x400]
    hit_calls = subprocess.check_output([
        "arm-none-eabi-objdump", "-d",
        "--disassemble=OverworldWildSpawns_ApplyQueuedCombat", str(wild_elf)], text=True)
    wild_symbols = layout_symbols(wild_elf, "arm-none-eabi-objdump")
    for name, address, size in (
        ("OverworldWildSpawns_PublishWalkCrash", 0x01FFF898, 60),
        ("OverworldWildSpawns_ClearWalkMovementState.constprop.0", 0x01FFF8D4, 54),
        ("OverworldWildSpawns_SetPreviousTile", 0x01FFF90A, 38),
        ("OverworldWildSpawns_RetainedMaskNamesActiveSpawns", 0x01FFF930, 28),
        ("OverworldWildSpawns_IsPreviousTileLockedAt", 0x01FFF94C, 52),
    ):
        require(wild_symbols.get(name) == (address, size, ".overworld_wild_carrier_hit", "F"),
                "resident Wild Walk tail has wrong owner, address, extent or mode")
    resident_tail = elf_bytes_at(wild_elf, 0x01FFF898, 232)
    carrier_hit_capsule_contract(carrier, carrier_body, carrier_package, hit_calls, resident_tail)
    retained_symbol = wild_symbols["OverworldWildSpawns_RetainedMaskNamesActiveSpawns"]
    retained_body = elf_bytes_at(wild_elf, retained_symbol[0], retained_symbol[1])
    transition_calls = subprocess.check_output([
        "arm-none-eabi-objdump", "-d",
        "--disassemble=OverworldWildSpawns_ApplyTransitionWork", str(wild_elf)], text=True)
    retained_mask_capsule_contract(retained_symbol, retained_body, carrier_package,
                                   transition_calls)
    transition_name = "OverworldWildSpawns_ApplyTransitionWork"
    transition_symbol = wild_symbols.get(transition_name)
    transition_binding = elf_helper_bindings(wild_elf, {transition_name}).get(transition_name)
    require(transition_symbol is not None, "private retained mask caller is missing")
    transition_body = elf_bytes_at(wild_elf, transition_symbol[0], transition_symbol[1])
    wild_row = struct.unpack_from("<8I", rom, y9_offset + 149 * 0x20)
    wild_start, wild_end = struct.unpack_from("<2I", rom, fat_offset + wild_row[6] * 8)
    require(wild_row == (149, 0x023CCFD8, 0xB000, 0x24, 0, 0, 149, 0)
            and 0 <= wild_start < wild_end <= len(rom)
            and wild_end - wild_start == wild_row[2],
            "private retained mask caller ROM owner metadata differs")
    transition_package = rom[wild_start + transition_symbol[0] - wild_row[1]:
                             wild_start + transition_symbol[0] - wild_row[1] + transition_symbol[1]]
    retained_mask_call_owner_contract(transition_symbol, transition_binding,
                                      transition_body, transition_package)
    for mutant_symbol, mutant_body, mutant_package, mutant_calls in (
        ((retained_symbol[0] + 2, *retained_symbol[1:]), retained_body, carrier_package, transition_calls),
        ((retained_symbol[0], 30, *retained_symbol[2:]), retained_body, carrier_package, transition_calls),
        ((retained_symbol[0], retained_symbol[1], ".text", "F"), retained_body, carrier_package, transition_calls),
        (retained_symbol, bytes([retained_body[0] ^ 1]) + retained_body[1:], carrier_package, transition_calls),
        (retained_symbol, retained_body, carrier_package[:0x130] + bytes([carrier_package[0x130] ^ 1]) + carrier_package[0x131:], transition_calls),
        (retained_symbol, retained_body, carrier_package, transition_calls.replace("23d47ec:", "23d47ce:")),
        (retained_symbol, retained_body, carrier_package, transition_calls.replace("bl\t1fff930", "blx\t1fff930")),
        (retained_symbol, retained_body, carrier_package, transition_calls.replace("1fff930", "1fff932")),
    ):
        try:
            retained_mask_capsule_contract(mutant_symbol, mutant_body, mutant_package, mutant_calls)
        except SystemExit:
            pass
        else:
            require(False, "wrong retained mask leaf body, owner, package or direct target passed")
    for mutant_symbol, mutant_binding, mutant_body, mutant_package in (
        ((transition_symbol[0] + 2, *transition_symbol[1:]), transition_binding, transition_body, transition_package),
        ((transition_symbol[0], 1070, *transition_symbol[2:]), transition_binding, transition_body, transition_package),
        (transition_symbol, (transition_binding[0] & ~1, *transition_binding[1:]), transition_body, transition_package),
        (transition_symbol, (*transition_binding[:2], "NOTYPE", transition_binding[3]), transition_body, transition_package),
        (transition_symbol, transition_binding, bytes([transition_body[0] ^ 1]) + transition_body[1:], transition_package),
        (transition_symbol, transition_binding, transition_body, transition_package[:-1]),
        (transition_symbol, transition_binding, transition_body[:0x196] + bytes([transition_body[0x196] ^ 1]) + transition_body[0x197:], transition_package),
    ):
        try:
            retained_mask_call_owner_contract(mutant_symbol, mutant_binding, mutant_body, mutant_package)
        except SystemExit:
            pass
        else:
            require(False, "wrong retained mask caller owner, extent, bytes, package or Thumb target passed")
    require(rom[health_start + 0x5280:health_start + 0x5400] == carrier_package,
            "ROM carrier hit leaf differs from its linked package")
    for mutant, payload, calls in (
        ((carrier[0] + 2, *carrier[1:]), carrier_package, hit_calls),
        ((carrier[0], 0x182, *carrier[2:]), carrier_package, hit_calls),
        ((carrier[0], carrier[1], ".text", "F"), carrier_package, hit_calls),
        (carrier, bytes([carrier_package[0] ^ 1]) + carrier_package[1:], hit_calls),
        (carrier, carrier_package, hit_calls.replace("1fff800", "1fff802")),
    ):
        try:
            carrier_hit_capsule_contract(mutant, carrier_body, payload, calls, resident_tail)
        except SystemExit:
            pass
        else:
            require(False, "wrong carrier hit address, extent, section, bytes or call passed")
    chain_row = struct.unpack_from("<8I", rom, y9_offset + 159 * 0x20)
    chain_start, chain_end = struct.unpack_from(
        "<2I", rom, fat_offset + chain_row[6] * 8)
    chain_packaged = rom[chain_start:chain_end]
    require(chain_row == (159, 0x01FF9800, 0xD48, 0, 0, 0, 159, 0)
            and 0 <= chain_start < chain_end <= len(rom)
            and chain_end - chain_start == 0xD48
            and chain_packaged == (REPO /
                "build/output_overworld_mount_chain_overlay.bin").read_bytes(),
            "private policy inspect host metadata or packaged Chain bytes differ")
    inspect_offset = 0x01FFA4E0 - 0x01FF9800
    verify_fixed_direct_imports(packaged, capsules,
                               chain_packaged[inspect_offset:inspect_offset + 12])
    verify_mount_surface_helper_abi()
    verify_mount_action_helper_abi()
    verify_chain_mount_imports()
    verify_mounted_diagonal_tail(rom, fat_offset, y9_offset)
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
    resident_step = layout_symbols(
        REPO / "build/linked.o", "arm-none-eabi-objdump"
    ).get("OverworldWildSpawns_OnPlayerStep")
    require(
        resident_step is not None
        and (resident_step[0] | 1) == PLAYER_STEP_RESIDENT_HANDLER
        and resident_step[3] == "F",
        "player-step bridge target differs from linked resident handler",
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
            0x023DD484,
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
        callbacks[0] == 0x01FFF981
        and all(OVERLAY_BASE <= (callback & ~1) < OVERLAY_BASE + file_size
            for callback in callbacks[1:]),
        "entry callback lies outside the mount overlay",
    )
    mount_elf = REPO / "build/overworld_mount_overlay_linked.o"
    begin = layout_symbols(mount_elf, "arm-none-eabi-objdump").get(
        "OverworldMount_Begin")
    require(
        begin is not None and begin[0] == 0x01FFF980
        and 0 < begin[1] <= 0x200
        and capsules[0x400:0x400 + begin[1]] == elf_bytes_at(
            mount_elf, begin[0], begin[1]),
        "mounted Begin callback differs from resident code",
    )
    require(
        callbacks[-1] & ~1 != PLAYER_CONTROL_WRAPPER
        and callbacks[-1] & ~1 != CRASH_SOUND_WRAPPER,
        "frame callback aliases a fixed player-control wrapper",
    )
    toggle_wrapper = packaged[
        TOGGLE_LATCH_WRAPPER - OVERLAY_BASE:
        TOGGLE_LATCH_WRAPPER - OVERLAY_BASE + 8
    ]
    require(
        callbacks[-1] == TOGGLE_LATCH_WRAPPER + 1
        and toggle_wrapper[:4] == bytes.fromhex("00 4b 18 47")
        and (
            OVERLAY_BASE
            <= (struct.unpack_from("<I", toggle_wrapper, 4)[0] & ~1)
            < OVERLAY_BASE + file_size
        ),
        "Select frame callback does not forward to the mounted tick",
    )

    arm9_offset, arm9_entry, arm9_load, arm9_size = struct.unpack_from(
        "<4I", rom, 0x20
    )
    del arm9_entry
    arm9 = rom[arm9_offset:arm9_offset + arm9_size]
    require(len(arm9) == arm9_size, "ARM9 image is truncated")
    stock_player_presentation_cleanup_contract(arm9, arm9_load)
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
        and ".byte 158, 157, 159, 160, 155, 153, 156, 161" in startup
        and "mov r5, #8" in startup
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
        "OverworldFollowerSelector_IsYReleasePending() || mountSelection"
            in selector_source
        and "OverworldFollowerSelector_IsYPressPending() || mountSelection"
            not in selector_source
        and "OVERWORLD_FOLLOWER_SELECTION_REQUEST_PENDING"
            in selector_source
        and "| OVERWORLD_FOLLOWER_SELECTOR_Y_RELEASE_PENDING_FLAG;"
            in field_service,
        "follower selection is not confirmed by releasing the held Y",
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
    ).read_text() + "\n" + (
        REPO / "src/player_health_overlay/overworld_walk_input_policy.c"
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
    mounted_profile_source_fixtures(spawns, mount_begin)
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
    finish_mounted_walk = mounted_finish_body(actor_source, runtime_source)
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
    mounted_proposal_transport_contract(
        actor_source, walk_module_source, runtime_source,
        (REPO / "src/overworld_mount_action_overlay/overworld_mount_shared_helpers.c").read_text(),
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
    ground_probe_source_fixtures(runtime_source)
    custom_motion_source_fixtures(mount_source, actor_source)
    field_input_source = (REPO / "src/field/overworld_mount_field_input.c").read_text()
    require(
        "OverworldMount_FieldInputProcess" in mount_source
        and "OVERWORLD_MOUNT_FIELD_INPUT_MAP_TRANSITION" in field_input_source
        and "OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT" in field_input_source
        and "== OW_WILD_BEHAVIOR_LOCOMOTION_HOP" in mount_source,
        "mounted Hop does not suppress synthetic warp/step transitions",
    )
    # Mounted Hop locomotion is retired: the rider jumps with B. Only the
    # chain-hop path (ledge Hop and B Jump) starts a mounted Hop, and a
    # cardinal one streams terrain live like cardinal Walk.
    require(
        "OverworldMount_TryNextHopLandingCandidate" not in mount_source
        and re.search(
            r"snapshot\.profile\.chillAction\s*== OW_WILD_BEHAVIOR_LOCOMOTION_HOP\)\s*\{\s*"
            r"sOverworldMountState\.snapshot\.profile\.chillAction =\s*"
            r"OW_WILD_BEHAVIOR_LOCOMOTION_WALK;",
            mount_source) is not None
        and "/* Only the ledge Hop and B Jump start a mounted Hop. */\n        return FALSE;" in mount_source
        and "if (!liveStream && !OverworldMount_BeginTerrainStream())" in mount_source
        and "(!liveStream && !OverworldMount_TerrainStreamIsIdle())" in mount_source,
        "mounted Hop locomotion or the live cardinal chain-hop stream differs",
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
            r"OverworldWalkInput_RefreshTuning\(policy, call, baseSpeed, linear\);.*?"
            r"policy->bufferedDirection != OW_WILD_WALK_DIRECTION_NONE",
            runtime_source,
            re.DOTALL,
        ) is not None
        and re.search(
            r"if \(state->speed == 0 \|\| state->spotState != call->laneState\) \{\s*"
            r"OverworldActorWalkPolicy_ResetState\(\s*"
            r"policy, TRUE, baseSpeed, call->laneState\);",
            function_body(runtime_source, "OverworldWalkInput_RefreshTuning"),
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
        r"OverworldMount_TryStartCustomMotion\(",
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
        "static void OverworldMount_DetachPresentation(u8 reason)", 1
    )[1].split("static void OverworldMount_Cancel", 1)[0]
    require(
        cancel_mount is not None
        and "OverworldWalkMount_RebaseMotionTarget(&sOverworldMountState);"
            in cancel_mount.group("body")
        and "OverworldMount_DetachPresentation(reason);"
            in cancel_mount.group("body")
        and "OverworldMount_RestorePlayerSprite(player, reason);" in detach_mount
        and re.search(
            r"if \(reason == OVERWORLD_MOUNT_CANCEL_OVERLAY_CLEANUP\) \{\s*"
            r"/\*.*?\*/\s*OverworldMount_ClearPlayerPresentation\(player\);\s*"
            r"MapObject_SetGfxID\(player, sOverworldMountState.savedPlayerGfxId\);\s*"
            r"\} else \{\s*ChangeMapObjSprite\(player, sOverworldMountState.savedPlayerGfxId\);",
            function_body(mount_source, "OverworldMount_RestorePlayerSprite"),
            re.DOTALL,
        ) is not None
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
        and '"add r3, #108\\n"' in function_body(
            mount_source, "OverworldMount_EndSession"
        )
        and '"strh r2, [r3, #18]\\n"' in function_body(
            mount_source, "OverworldMount_EndSession"
        )
        and "OverworldMountEndSessionOffsetsMustMatchAssembly" in mount_internal
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
        and "#define OVERWORLD_MOUNT_PLAYER_MOVE_STATE_NONE 0" in mount_source
        and re.search(
            r"if \(avatar->unk10 \| avatar->unk14\) \{"
            r"\s*OverworldMount_ResetAvatarAfterCancel\(avatar\);",
            mount_source,
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
        and "(*(vu32 *)0x021D1144 >> 2) & 1"
            in capture_toggle.group(0)
        and "(*(vu32 *)0x021D1148 >> 2) & 1"
            in capture_toggle.group(0)
        and "fieldSystem->taskman == NULL" not in capture_toggle.group(0)
        and "!OverworldFollowerSelector_IsActiveFlagSet()"
            in capture_toggle.group(0)
        and "if (state->mapId == fieldSystem->location->mapId) {\n"
            "        OVERWORLD_MOUNT_TOGGLE_PENDING = 0;"
            in function_body(spawns, "OverworldWildSpawns_OverlayOnFieldBusy")
        and "OVERWORLD_MOUNT_TOGGLE_RETRY_FRAMES" in mount_header
        and "OVERWORLD_MOUNT_TOGGLE_RETRY_FRAMES;"
            in capture_toggle.group(0)
        and "togglePressed = sOverworldMountState.bufferedTogglePending;"
            in mount_source
        and "--sOverworldMountState.bufferedTogglePending;"
            in mount_source
        and "OVERWORLD_FOLLOWER_TRANSITION_QUEUE->count == 0"
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
    entry_source = (REPO / "lib/overworld/overworld_entry_route.c").read_text()
    entry_header = (REPO / "include/overworld_entry_route.h").read_text()
    native_refill_delay = function_body(entry_source, "NativeRefillDelay")
    native_ordinary_refill = function_body(entry_source, "NativeOrdinaryRefill")
    refill_delay = function_body(spawns, "OverworldWildSpawns_ApplyRefillDelay")
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
        and "#define OVERWORLD_ENTRY_REFILL_BASE_FRAMES 60" in entry_header
        and "return OVERWORLD_ENTRY_REFILL_BASE_FRAMES*(count?count:1);"
            in native_refill_delay
        and "count+=state->spawns[slot].active;" in native_refill_delay
        and "slot<OW_WILD_LAND_SURF_MAX_SPAWNS" in native_refill_delay
        and "spawnCooldown--" not in native_ordinary_refill
        and "OVERWORLD_ENTRY_NATIVE_SPAWN" in refill_function.group(0)
        and "OVERWORLD_ENTRY_SPAWN_ORDINARY_REFILL" in refill_function.group(0)
        and "OverworldWildSpawns_EntryControl(state,fieldSystem,0,NULL,&c)"
            in refill_function.group(0)
        and "OverworldWildSpawns_ApplyRefillDelay(OVERWORLD_ENTRY_COMMIT_REFILL_DELAY(value));"
            in refill_function.group(0)
        and "OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL,delay-1"
            in refill_delay
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
        and "entry->resolveBaseYAt != NULL" in runtime_source
        and "reservedPopulationControl" not in runtime_source
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
    refill_body = refill_function.group(0)
    require(
        refill_body.find("OverworldWildSpawns_ReconcileFollowerSelection(")
            < refill_body.find("if (runtime->refillPositionChecksRemaining == 0")
            < refill_body.find("OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_REFILL_WAIT")
            < refill_body.find("OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL")
        and re.search(
            r"if \(runtime->refillPositionChecksRemaining == 0\s*"
            r"&& runtime->refillTerrainMask == 0\) \{.*?"
            r"if \(OverworldWildSpawns_PopulationControl\(\s*"
            r"OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_REFILL_WAIT, 0\)\) \{\s*"
            r"return TRUE;\s*\}",
            refill_body, re.DOTALL,
        ) is not None
        and refill_body.find("OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL")
            < refill_body.find("OVERWORLD_ENTRY_SPAWN_ORDINARY_REFILL")
        and native_ordinary_refill.find("if (runtime->refillPositionChecksRemaining != 0)")
            < native_ordinary_refill.find("while (runtime->refillTerrainMask != 0)")
        and "return gOverworldActorSystemState.population.refillArmed;"
            in population_control,
        "new ordinary refill bypasses its wait or blocks follower/started work",
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
    # The unchanged Wild terminal adapter is now physically hosted in Query.
    # Its typed callback table and packaged implementation are checked by the
    # Query package gate. Keep the terminal ACK-before-clear check here.
    return_move_source = (
        REPO / "lib/overworld/overworld_return_move_wild.c"
    ).read_text()
    wild_walk_commit = function_body(
        return_move_source, "OverworldReturnMoveWild_FinishWalk"
    )
    wild_walk_dispatch = function_body(
        spawns, "OverworldWildSpawns_FinishReturnMove"
    )
    wild_command_finish = function_body(
        spawns, "OverworldWildSpawns_HandleFinishedMovementCommand"
    )
    return_finish = function_body(
        return_move_source, "OverworldReturnMoveWild_Finish"
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
        and re.search(
            r"u32 noNewKeys = 0;\s*u32 heldKeys = physicalKeys;.*?"
            r"OverworldWalk_SelectNewestMountedInput\(\s*"
            r"&sOverworldMountState, &noNewKeys, &heldKeys\);\s*"
            r"physicalKeys = \(u16\)heldKeys;",
            mount_tick,
            re.DOTALL,
        ) is not None
        and "sOverworldMountState.directionInputHeld =" not in mount_tick
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
        "entry->returnFinish(&context, profile, primitives, flags)"
            in wild_walk_dispatch
        and "OverworldWildSpawns_FinishReturnMove(" in wild_command_finish
        and "OVERWORLD_RETURN_MOVE_WALK_TERMINAL" in wild_command_finish
        and re.search(
            r"if \(flags & OVERWORLD_RETURN_MOVE_WALK_TERMINAL\)\s*"
            r"return OverworldReturnMoveWild_FinishWalk\(",
            return_finish,
        ) is not None
        and "->terminalWalk(" in wild_walk_commit
        and 0 <= wild_walk_commit.find("->terminalWalk(")
            < wild_walk_commit.find("OVERWORLD_MOTION_PHASE_SETTLING")
            < wild_walk_commit.find(
                "input->ops->clearCustomJump(state, slot);"
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
