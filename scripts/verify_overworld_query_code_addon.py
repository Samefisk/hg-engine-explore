#!/usr/bin/env python3
"""Prove the exact field-owned query package, bootstrap and native cache ABI."""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import struct

if __package__:
    from .verify_overworld_field_capsule import (rom_overlays, overlay_span,
        frame_reader_contract, FRAME_ADDR, FRAME_SIZE)
    from .verify_pokemon_move_history_capture import (
        elf_bytes_at, elf_helper_bindings, overworld_core_helper_body, thumb_bl_target)
else:
    from verify_overworld_field_capsule import (rom_overlays, overlay_span,
        frame_reader_contract, FRAME_ADDR, FRAME_SIZE)
    from verify_pokemon_move_history_capture import (
        elf_bytes_at, elf_helper_bindings, overworld_core_helper_body, thumb_bl_target)

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ENTRY, STATE, CODE, END = 0x023C22F0, 0x023C2308, 0x023C2324, 0x023C2FF0
PUBLIC_ENTRY, GATE = 0x023C22A0, 0x023C22B8
DELEGATES = ("OverworldQueryCodeAddon_ConditionPrepare",
    "OverworldQueryCodeAddon_ConditionEvaluate", "OverworldQueryCodeAddon_ResolverCall",
    "OverworldQueryCodeAddon_ConditionNotify")
CACHE = (
    ("FlushData", "QueryAddon_DC_FlushRange", 0x020D2894,
     (0xE3A0C000, 0xE0811000, 0xE3C0001F, 0xEE07CF9A, 0xEE070F3E,
      0xE2800020, 0xE1500001, 0xBAFFFFFA, 0xE12FFF1E)),
    ("WaitWriteBuffer", "QueryAddon_DC_WaitWriteBufferEmpty", 0x020D28B8,
     (0xE3A00000, 0xEE070F9A, 0xE12FFF1E)),
    ("InvalidateCode", "QueryAddon_IC_InvalidateRange", 0x020D28D0,
     (0xE0811000, 0xE3C0001F, 0xEE070F35, 0xE2800020, 0xE1500001,
      0xBAFFFFFB, 0xE12FFF1E)),
)
WILD_ABSOLUTE_CALLBACKS = {
    "OverworldWildSpawns_MetatileBehavior": 0x02054919,
    "OverworldWildSpawnGuard_IsSurfBehavior": 0x023C03D1,
    "OverworldSpawnSpatial_IsPlayerTile": 0x023C7F61,
    "OverworldSpawnSpatial_IsPlayerFrontTile": 0x023C7F99,
    "OverworldSpawnSpatial_IsCurrentMapObject": 0x023C2201,
    "OverworldWildOccupancy_Query": 0x023C0185,
    "OverworldWildSpawns_PlayerX": 0x0205C67D,
    "OverworldWildSpawns_PlayerY": 0x0205C689,
    "OverworldWildSpawns_ResolveWalkPause": 0x023DFFCD,
    "OverworldWalk_DirectionFromDelta": 0x023BF68D,
    "OverworldActorWalkPolicy_SampleHopEffects": 0x01FFF551,
    "IsMetatileBlockedAt": 0x020548C1,
}
# These linker-defined aliases omit STT_FUNC. The real resident FUNC owners
# below authenticate their exact Thumb bodies in the packaged overlays.
WILD_NOTYPE_CALLBACKS = {
    "OverworldWildSpawns_ResolveWalkPause",
    "OverworldWalk_DirectionFromDelta",
}
WILD_ASM_CALLBACKS = {
    "OverworldWildSpawns_MountIsActive": 0x023CD0EF,
    "OverworldWildSpawns_ReduceWalk": 0x023CD111,
}
WILD_CALLBACK_TABLES = {
    "sOverworldWildHopOps": (16, 0, (
        "OverworldWildSpawns_StartNextSpotEmoteStep",
        "OverworldWildSpawns_EnsureFrameMovementTask", 0,
        "OverworldActorWalkPolicy_SampleHopEffects")),
    "sOverworldWildRouteOps": (84, 4, (
        "OverworldWildSpawns_IsPlayableMapMatrixTile",
        "OverworldWildSpawns_MetatileBehavior", "OverworldWildSpawns_QueryRouteSurface",
        "OverworldWildSpawns_ResolveRouteBaseY", "OverworldWildSpawnGuard_IsSurfBehavior",
        "OverworldSpawnSpatial_IsPlayerTile", "OverworldSpawnSpatial_IsPlayerFrontTile",
        "OverworldWildSpawns_IsLandMapTile", "OverworldWildSpawns_IsMountedPlayerScriptedLandingTile",
        "OverworldSpawnSpatial_IsCurrentMapObject", "OverworldWildOccupancy_Query",
        "OverworldWildSpawns_RouteActorState", "OverworldActorPolicy_Inspect",
        "OverworldWildSpawns_RequestHopPlan", 0x020549A9, 0x020FD4CC, 0x020FD4BC,
        "OverworldWildSpawns_PickupReach", 0x02054955, "IsMetatileBlockedAt")),
    "sOverworldWildCargoTargetOps": (24, 0, (
        "OverworldWildSpawns_PlayerX", "OverworldWildSpawns_PlayerY",
        "OverworldWildSpawns_IsCurrentSpawnObject", "OverworldWildSpawns_QueryPickupThrowTarget",
        "OverworldWildSpawns_TryGetCirclePlayerMovementTarget",
        "OverworldWildSpawns_TryGetPlayerAdjacentMovementTarget")),
    "sOverworldWildThrowHeldOps": (36, 0, (
        "OverworldWildSpawns_GetThrowBindingBody", 0x0205F63D,
        "OverworldWildSpawns_StartPreparedCustomJumpCommand", "OverworldWildSpawns_StartThrowRecovery",
        "OverworldWildSpawns_ReleaseThrowTargetAtCurrentTile", "OverworldWildSpawns_SetObjectFacing",
        "OverworldWildSpawns_ShowBubble", "OverworldWildSpawns_GetAlertBubbleIdForProfile",
        "OverworldWildSpawns_AbortThrow")),
    "sOverworldWildQueryCodeOps": (24, 0, (
        "OverworldWildSpawns_LoadCodeAddonBlob", 0x0201AB0D,
        0x020D2894, 0x020D28B8, 0x020D28D0, "OverworldWildSpawns_DrainQuery")),
    "sOverworldWildReturnOps": (60, 0, (
        "OverworldWildSpawns_IsPresentationFieldContextCurrent",
        "OverworldWildSpawns_IsCurrentSpawnObject", "OverworldWildSpawns_MountIsActive",
        "OverworldWildSpawns_QuerySurface", "OverworldWildSpawns_GetObjectGroundBaseYAt",
        "OverworldWildSpawns_ClassifyBehaviorHopLandingTile",
        "OverworldWildSpawns_StartPreparedCustomJumpCommandTimed",
        "OverworldWildSpawns_ClearStagedHopTargetLocal", "OverworldWildSpawns_InitPolicyCall",
        "OverworldWildSpawns_ReduceWalk", "OverworldWildSpawns_ResolveWalkPause",
        "OverworldWalk_DirectionFromDelta",
        "OverworldWildSpawns_ClearCustomJumpLocal",
        "OverworldWildSpawns_ExecuteWalkPolicy", "OverworldWildSpawns_CommitDeferredChainMovementPause")),
}
# Exact private Entry native table; RouteOps retains its separate v3/84 ABI.
WILD_ENTRY_NATIVE_TABLE = "sOverworldWildEntryNativeOps"
WILD_ENTRY_NATIVE_TABLE_OWNER = (37584708, 72, 'OBJECT')
WILD_ENTRY_NATIVE_CALLBACKS = ('OverworldWildSpawns_RouteActorState',
 'OverworldWildSpawns_InitRouteWorld',
 'OverworldWildSpawns_GetAllowedTileForSpotState',
 'OverworldWildSpawns_StartEntryEdge',
 'OverworldWildSpawns_FinishEntryArrival',
 'OverworldWildSpawns_RemoveEncounter',
 'OverworldWildSpawns_IsTileOccupiedByObject',
 'OverworldWildSpawns_ResolveSpawnBehaviorProfile',
 'OverworldWildSpawns_IsBehaviorLimitKeyAtOverworldLimit',
 'OverworldWildSpawns_TryApplySpawnDestination',
 'OverworldWildSpawns_GetObjectGroundBaseYAt',
 'OverworldWildSpawns_FinalizeEntryPersonality',
 'OverworldWildSpawns_TryPrepareSpawnWithHelper',
 'OverworldWildSpawns_EntryGuard',
 'OverworldWildSpawns_EntryPlacementBlocked',
 'OverworldWildSpawns_SpawnPreparedEncounter')
# (odd hosted address, full extent, packaged overlay owner, full body SHA256)
WILD_ENTRY_NATIVE_OWNERS = {'OverworldWildSpawns_EntryGuard': (37550767,
                                    22,
                                    149,
                                    'a23885c9067794d449fb1bb9597564fa6abf4ffe44c345ab28209158af855fa2'),
 'OverworldWildSpawns_EntryPlacementBlocked': (37575429,
                                               74,
                                               149,
                                               '001a7672b33f606ddfca212f463b736e8546de208e53d6a1462d24b2cef10120'),
 'OverworldWildSpawns_FinalizeEntryPersonality': (37550789,
                                                  44,
                                                  149,
                                                  'bb57c3009cee7194ed954d33cfdcb2fd9d45fa5be0b2fa0ee373d5f042c0525f'),
 'OverworldWildSpawns_FinishEntryArrival': (37554553,
                                            92,
                                            149,
                                            'f870d356fe46e934c0efb68788e483a696eb9782281056de728c45f0bda4b706'),
 'OverworldWildSpawns_GetAllowedTileForSpotState': (37540645,
                                                    10,
                                                    149,
                                                    '487fbafdb57b788af601ca9f4283420d76102a5b0699a0bf3a6a4808062d3582'),
 'OverworldWildSpawns_GetObjectGroundBaseYAt': (37545551,
                                                54,
                                                149,
                                                '0f6d6f5cac778058251bc1bf71fb9d90866151b60d73441f6d69dd143a9cecec'),
 'OverworldWildSpawns_InitRouteWorld': (37545005,
                                        88,
                                        149,
                                        'ab5abde234cf1f0de912427432658a087d589cd2f0acb2b31045dcfbb5d54623'),
 'OverworldWildSpawns_IsBehaviorLimitKeyAtOverworldLimit': (37542287,
                                                            26,
                                                            149,
                                                            'fda3f50e12035567186578fc98cd9f2f37aa44a4274d746ab11690cc8d5f5951'),
 'OverworldWildSpawns_IsTileOccupiedByObject': (37545919,
                                                30,
                                                149,
                                                'de8f50ca92a5e24519fec15bbd014a46c870d4a3c96e577b28042e3957c7d9e5'),
 'OverworldWildSpawns_RemoveEncounter': (37560689,
                                         52,
                                         149,
                                         'd6f2f1f7d670b79aa49e26f72b2c02a5b63d9a3a5c2c769f6daa89965e81019a'),
 'OverworldWildSpawns_ResolveSpawnBehaviorProfile': (37551553,
                                                     160,
                                                     149,
                                                     '1920f54af1d3f6ff4c3f52c8411539fe5bc279b11334c5336bf1dc2218e328ba'),
 'OverworldWildSpawns_RouteActorState': (35685583,
                                         46,
                                         1,
                                         '5d1ca4d9d8adc7cb3415f72a64677b5b930f2de08023c7d6804cb1a36145dc85'),
 'OverworldWildSpawns_SpawnPreparedEncounter': (37566041,
                                                1204,
                                                149,
                                                'b18d2a881d1c8e2eda67ea16de97009b32b3d24a1e208b1d2fe04e69b593e10c'),
 'OverworldWildSpawns_StartEntryEdge': (37584289,
                                        250,
                                        149,
                                        '1957b75b832f3c7a8f6d590c477dc45cd7cae98269fbdbf415f0cf4ed4d1d9eb'),
 'OverworldWildSpawns_TryApplySpawnDestination': (37557721,
                                                  904,
                                                  149,
                                                  '47682804e907b0abb44dbffd54d03762ad563575c3ed201f0ff261c055be7ad6'),
 'OverworldWildSpawns_TryPrepareSpawnWithHelper': (37542789,
                                                   116,
                                                   149,
                                                   'ae51b8f4edc89442e30e4e383bff831ed4d7e7136e3f8c12a1d4a69585e6c7e3')}

MOUNT_ABSOLUTE_CALLBACKS = {
    "PlayCry": 0x02006219,
    "OverworldWildBubble_ShowQuiet": 0x01FFF3B1,
    "OverworldActorWalkPolicy_SampleHopEffects": 0x01FFF551,
}
MOUNT_CALLBACK_TABLES = {
    "sOverworldMountHopOps": (16, 0, (
        "OverworldMount_GetFollowerObject", "PlayCry",
        "OverworldWildBubble_ShowQuiet", "OverworldActorWalkPolicy_SampleHopEffects")),
}
# Named vanilla sub_02060DEC uses these exact direction predicate arrays.
DIRECTION_BLOCKS = {
    0x020FD4CC: (0x0205B8F5, 0x0205B919, 0x0205B93D, 0x0205B961),
    0x020FD4BC: (0x0205B919, 0x0205B8F5, 0x0205B961, 0x0205B93D),
}


def checked(condition, reason):
    if not condition:
        raise ValueError("query code addon: " + reason)


def borrowed_callback_contract(tables, symbols, contracts, absolute, notype=(), assembly=None):
    """Authenticate actual data words, not only Thumb metadata on ABS aliases.

    GAS folds a same-object absolute alias in .word without a relocation and
    omits its Thumb flag. BL metadata alone cannot prove an indirect call.
    """
    assembly = assembly or {}
    for table, (size, start, targets) in contracts.items():
        binding = symbols.get(table)
        checked(binding is not None and binding[1:3] == (size, "OBJECT")
                and binding[3] not in ("ABS", "UND"), "borrowed callback table owner/layout differs")
        raw = tables.get(table, b"")
        checked(len(raw) == size and (not start or raw[:4] == struct.pack("<HH", 3, 84)),
                "borrowed callback table ABI differs")
        for index, name in enumerate(targets):
            offset = start + index * 4
            pointer = struct.unpack_from("<I", raw, offset)[0]
            if isinstance(name, int):
                checked(pointer == name, f"{table}+{offset} fixed native target/mode differs")
                continue
            function = symbols.get(name)
            kind = "NOTYPE" if name in notype else "FUNC"
            checked(function is not None and function[2] == kind and function[0] & 1,
                    f"{table}+{offset} {name} lost Thumb function metadata")
            if name in absolute:
                checked(function == (absolute[name], 0, kind, "ABS"),
                        f"{name} absolute Thumb target differs")
            elif name in assembly:
                checked(function[:3] == (assembly[name], 0, "FUNC")
                        and function[3] not in ("ABS", "UND"),
                        f"{name} hosted assembly callback differs")
            else:
                checked(function[1] > 0 and function[3] not in ("ABS", "UND"),
                        f"{name} hosted callback owner differs")
            checked(pointer == function[0],
                    f"{table}+{offset} {name} callback word is not its exact Thumb function")


def wild_callback_contract(tables, symbols):
    borrowed_callback_contract(tables, symbols, WILD_CALLBACK_TABLES,
                               WILD_ABSOLUTE_CALLBACKS, WILD_NOTYPE_CALLBACKS,
                               WILD_ASM_CALLBACKS)


def wild_entry_native_contract(raw, symbols, read):
    """Seal only the named synchronous private table and its real owners."""
    binding = symbols.get(WILD_ENTRY_NATIVE_TABLE)
    checked(binding is not None and binding[:3] == WILD_ENTRY_NATIVE_TABLE_OWNER
            and binding[3] not in ("ABS", "UND"),
            "Entry native table owner/layout differs")
    checked(len(raw) == 72 and struct.unpack_from("<IHH", raw)
            == (0x4E454F57, 1, 72), "Entry native table ABI differs")
    for index, name in enumerate(WILD_ENTRY_NATIVE_CALLBACKS):
        address, size, _overlay, sha = WILD_ENTRY_NATIVE_OWNERS[name]
        function = symbols.get(name)
        checked(function is not None and function[:3] == (address, size, "FUNC")
                and function[3] not in ("ABS", "UND"),
                "Entry native callback hosted owner/mode/extent differs: " + name)
        checked(struct.unpack_from("<I", raw, 8 + index * 4)[0] == address,
                "Entry native callback word differs: " + name)
        body = read(address & ~1, size)
        checked(len(body) == size and hashlib.sha256(body).hexdigest() == sha,
                "Entry native full callback body differs: " + name)


def mount_callback_contract(tables, symbols):
    borrowed_callback_contract(tables, symbols, MOUNT_CALLBACK_TABLES,
                               MOUNT_ABSOLUTE_CALLBACKS)


def verify_mount_hop_callbacks(build, overlays):
    mount = build / "overworld_mount_overlay_linked.o"
    names = tuple(MOUNT_CALLBACK_TABLES) + tuple(name for _size, _start, targets
                in MOUNT_CALLBACK_TABLES.values() for name in targets)
    symbols = elf_helper_bindings(mount, names)
    tables = {}
    for name, (size, _start, _targets) in MOUNT_CALLBACK_TABLES.items():
        binding = symbols.get(name)
        checked(binding is not None and binding[:3] == (0x01FFF7EC, 16, "OBJECT")
                and binding[3] not in ("ABS", "UND"),
                "private Mount Hop table owner/extent moved")
        tables[name] = elf_bytes_at(mount, binding[0], size)
        checked(tables[name] == overlay_span(overlays, 161, binding[0], size),
                "borrowed Mount Hop callback linked/package bytes differ")
    mount_callback_contract(tables, symbols)
    for name in ("OverworldMount_GetFollowerObject",):
        binding = symbols[name]
        body_contract = elf_bytes_at(mount, binding[0] & ~1, binding[1])
        checked(body_contract == overlay_span(overlays, 157, binding[0] & ~1, binding[1]),
                "borrowed Mount Hop callback owner linked/package bytes differ")


def verify_wild_callbacks(build, overlays):
    wild = build / "overworld_wild_spawns_overlay_linked.o"
    names = tuple(WILD_CALLBACK_TABLES) + tuple(name for _size, _start, targets
                in WILD_CALLBACK_TABLES.values() for name in targets if isinstance(name, str))
    names += (WILD_ENTRY_NATIVE_TABLE,) + WILD_ENTRY_NATIVE_CALLBACKS
    symbols = elf_helper_bindings(wild, names)
    native_raw = elf_bytes_at(wild, WILD_ENTRY_NATIVE_TABLE_OWNER[0], 72)
    checked(native_raw == overlay_span(overlays, 149, WILD_ENTRY_NATIVE_TABLE_OWNER[0], 72),
            "Entry native table linked/package bytes differ")
    wild_entry_native_contract(native_raw, symbols,
                              lambda address, size: elf_bytes_at(wild, address, size))
    for name, (address, size, overlay, _sha) in WILD_ENTRY_NATIVE_OWNERS.items():
        checked(elf_bytes_at(wild, address & ~1, size)
                == overlay_span(overlays, overlay, address & ~1, size),
                "Entry native callback linked/package bytes differ: " + name)
    tables = {}
    for name, (size, _start, _targets) in WILD_CALLBACK_TABLES.items():
        binding = symbols.get(name)
        checked(binding is not None, "borrowed callback table is missing")
        tables[name] = elf_bytes_at(wild, binding[0], size)
        overlay_id = 1 if name == "sOverworldWildHopOps" else 149
        if overlay_id == 1:
            checked(binding[:3] == (0x0220833C, 16, "OBJECT")
                    and binding[3] not in ("ABS", "UND"),
                    "private Wild Hop table owner/extent moved")
        checked(tables[name] == overlay_span(overlays, overlay_id, binding[0], size),
                "borrowed callback linked/package bytes differ")
    wild_callback_contract(tables, symbols)
    # Named assembly tail wrappers have no ELF .size. Their exact instruction
    # bytes and fixed service literals fully define the authenticated extents.
    wrapper = WILD_ASM_CALLBACKS["OverworldWildSpawns_MountIsActive"] & ~1
    expected = bytes.fromhex("014b9b691847") + struct.pack("<I", 0x023BB600)
    checked(elf_bytes_at(wild, wrapper, 10)
            == overlay_span(overlays, 149, wrapper, 10) == expected,
            "borrowed Mount assembly wrapper body/service pointer differs")
    mount = build / "overworld_mount_overlay_linked.o"
    active = elf_helper_bindings(mount, ("OverworldMount_IsActive",)).get("OverworldMount_IsActive")
    checked(active is not None and active[:3] == (0x023BB671, 12, "FUNC")
            and active[3] not in ("ABS", "UND"),
            "borrowed Mount assembly service owner/mode/extent differs")
    service = elf_bytes_at(mount, 0x023BB600, 32)
    checked(service == overlay_span(overlays, 157, 0x023BB600, 32)
            and struct.unpack_from("<IHH", service) == (0x544E554D, 11, 32)
            and struct.unpack_from("<I", service, 24)[0] == active[0],
            "borrowed Mount assembly service ABI/typed callback differs")
    checked(elf_bytes_at(mount, active[0] & ~1, active[1])
            == overlay_span(overlays, 157, active[0] & ~1, active[1]),
            "borrowed Mount assembly implementation linked/package bytes differ")
    wrapper = WILD_ASM_CALLBACKS["OverworldWildSpawns_ReduceWalk"] & ~1
    expected = bytes.fromhex("014b9b68db681847") + struct.pack("<I", 0x023B6BA8)
    checked(elf_bytes_at(wild, wrapper, 12)
            == overlay_span(overlays, 149, wrapper, 12) == expected,
            "borrowed Walk assembly wrapper body/service pointer differs")
    actor = build / "overworld_actor_system_overlay_linked.o"
    owner_names = ("gOverworldActorSystemMovementPolicyServiceEntry",
                   "sActorMovementPolicy", "ActorSystem_ReduceWalk")
    owner = elf_helper_bindings(actor, owner_names)
    for name, address, size, kind in (
        (owner_names[0], 0x023B6BA8, 16, "OBJECT"),
        (owner_names[1], 0x023B9FE8, 24, "OBJECT"),
        (owner_names[2], 0x023B719D, 100, "FUNC"),
    ):
        binding = owner.get(name)
        checked(binding is not None and binding[:3] == (address, size, kind)
                and binding[3] not in ("ABS", "UND"),
                "borrowed Walk assembly service owner/mode/extent differs")
        checked(elf_bytes_at(actor, address & ~1, size)
                == overlay_span(overlays, 158, address & ~1, size),
                "borrowed Walk assembly implementation linked/package bytes differ")
    service = elf_bytes_at(actor, 0x023B6BA8, 16)
    policy = elf_bytes_at(actor, 0x023B9FE8, 24)
    checked(struct.unpack_from("<IHH", service) == (0x504D574F, 5, 16)
            and struct.unpack_from("<I", service, 8)[0] == owner[owner_names[1]][0]
            and struct.unpack_from("<I", policy, 12)[0] == owner[owner_names[2]][0],
            "borrowed Walk assembly service ABI/typed callback differs")
    owners = (
        (153, "pokemon_move_history_overlay_linked.o", ("OverworldWildOccupancy_Query",
                                                      "OverworldWildSpawnGuard_IsSurfBehavior",
                                                      "OverworldWalk_DirectionFromDelta")),
        (151, "overworld_wild_helper_overlay_linked.o", ("OverworldSpawnSpatial_IsPlayerTile",
                                                      "OverworldSpawnSpatial_IsPlayerFrontTile")),
        (152, "overworld_follower_selector_overlay_linked.o", ("OverworldSpawnSpatial_IsCurrentMapObject",)),
        (129, "linked.o", ("OverworldWildSpawns_ResolveWalkPause",)),
    )
    for overlay, filename, owned_names in owners:
        elf = build / filename
        owned = elf_helper_bindings(elf, owned_names)
        for name in owned_names:
            function = owned.get(name)
            checked(function is not None and function[0] == WILD_ABSOLUTE_CALLBACKS[name]
                    and function[1] > 0 and function[2] == "FUNC"
                    and function[3] not in ("ABS", "UND"), "borrowed callback implementation differs")
            if name in WILD_NOTYPE_CALLBACKS:
                size = 46 if name == "OverworldWildSpawns_ResolveWalkPause" else 42
                checked(function[:3] == (WILD_ABSOLUTE_CALLBACKS[name], size, "FUNC"),
                        "borrowed fixed alias resident owner/mode/extent differs")
            checked(elf_bytes_at(elf, function[0] & ~1, function[1])
                    == overlay_span(overlays, overlay, function[0] & ~1, function[1]),
                    "borrowed callback implementation linked/package bytes differ")


def verify_direction_callbacks(arm9, base):
    for address, targets in DIRECTION_BLOCKS.items():
        offset = address - base
        checked(0 <= offset <= len(arm9) - 16
                and arm9[offset:offset + 16] == struct.pack("<4I", *targets),
                "native direction predicate table Thumb targets differ")


def packer():
    spec = importlib.util.spec_from_file_location(
        "query_addon_packer", ROOT / "tools/overworld/pack_query_code_addon.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generated_header(blob, receipt):
    return (
        "/* Generated by pack_query_code_addon.py; exact native package. */\n"
        "#ifndef OVERWORLD_QUERY_CODE_ADDON_PACKAGE_H\n"
        "#define OVERWORLD_QUERY_CODE_ADDON_PACKAGE_H\n"
        f"#define OVERWORLD_QUERY_CODE_ADDON_PACKAGE_BYTES {len(blob)}u\n"
        f"#define OVERWORLD_QUERY_CODE_ADDON_PACKAGE_IMAGE_BYTES {receipt['imageBytes']}u\n"
        f"#define OVERWORLD_QUERY_CODE_ADDON_PACKAGE_CHECKSUM 0x{packer().checksum(blob):08X}u\n"
        "#endif\n")


def hosted(symbol, address=None, size=None, low=CODE, high=END):
    checked(symbol is not None and symbol[2] == "FUNC" and symbol[0] & 1
            and symbol[3] not in ("ABS", "UND") and symbol[1] > 0
            and low <= symbol[0] & ~1 < high
            and symbol[1] <= high - (symbol[0] & ~1)
            and (address is None or symbol[0] == address | 1)
            and (size is None or symbol[1] == size),
            "bootstrap hosted Thumb function mode/extent differs")


def verify_selector(selector, packaged):
    names = ("gOverworldBehaviorConditionServiceEntry",
             "OverworldBehaviorConditionService_Get",
             "gOverworldQueryCodeAddonServiceEntry", "gOverworldQueryCodeAddonState",
             "__query_addon_bootstrap_end", "Service_Load", "Service_Acquire", "Service_Unload",
             "OverworldQueryCodeAddon_Load", "OverworldQueryCodeAddon_Acquire",
             "OverworldQueryCodeAddon_Unload", "OverworldVision_IsValidSpec", *DELEGATES,
             "OverworldQueryCodeAddon_Rebind", "OverworldQueryCodeAddonField_AcquireCurrent",
             "OverworldQueryCodeAddonField_Acquire",
             "OverworldQueryCodeAddonField_Unload",
             "OverworldThrowObservation_Observe", "OverworldThrowObservation_BindingPosition",
             "Addon_StockCoordinateImport",
             *("OverworldQueryCodeAddon_" + row[0] for row in CACHE),
             *(row[1] for row in CACHE))
    symbols = elf_helper_bindings(selector, names)
    checked(elf_bytes_at(selector, PUBLIC_ENTRY, 0x023C3000 - PUBLIC_ENTRY) == packaged,
            "complete linked/package bootstrap bytes differ")
    checked(symbols.get("gOverworldBehaviorConditionServiceEntry", ())[:3]
            == (PUBLIC_ENTRY, 24, "OBJECT"), "public Condition table moved")
    checked(symbols.get("gOverworldQueryCodeAddonServiceEntry", ())[:3]
            == (PRIVATE_ENTRY, 24, "OBJECT"), "private service table moved")
    checked(symbols.get("gOverworldQueryCodeAddonState", ())[:3]
            == (STATE, 28, "OBJECT") and elf_bytes_at(selector, STATE, 28) == bytes(28),
            "sole native addon state layout/initial value differs")
    checked(CODE < symbols.get("__query_addon_bootstrap_end", (END + 1,))[0] <= END,
            "bootstrap exceeds its owned code home")
    hosted(symbols.get("OverworldBehaviorConditionService_Get"), GATE,
           low=GATE, high=PRIVATE_ENTRY)
    hosted(symbols.get("OverworldVision_IsValidSpec"), 0x023C2280, 32,
           low=0x023C2280, high=PUBLIC_ENTRY)
    public = struct.unpack("<IHH4I", elf_bytes_at(selector, PUBLIC_ENTRY, 24))
    checked(public[:3] == (0x4342574F, 13, 24), "public Condition service ABI differs")
    for pointer, name in zip(public[3:], DELEGATES):
        hosted(symbols.get(name))
        checked(pointer == symbols[name][0], "public Condition callback is not its exact delegate")
    private = struct.unpack("<IHH4I", elf_bytes_at(selector, PRIVATE_ENTRY, 24))
    checked(private[:4] == (0x53444F57, 2, 24, STATE), "private service ABI/state pointer differs")
    for pointer, name in zip(private[4:], ("Service_Load", "Service_Acquire", "Service_Unload")):
        hosted(symbols.get(name))
        checked(pointer == symbols[name][0], "private service callback differs")
    for name in ("OverworldQueryCodeAddon_Load", "OverworldQueryCodeAddon_Acquire",
                 "OverworldQueryCodeAddon_Unload", "OverworldQueryCodeAddon_Rebind"):
        hosted(symbols.get(name))
    hosted(symbols.get("OverworldQueryCodeAddonField_AcquireCurrent"), 0x023C2A80, 96)
    hosted(symbols.get("OverworldQueryCodeAddon_Rebind"), 0x023C2EB0, 194)
    # The package byte count (70096) is a literal-pool word.
    hosted(symbols.get("OverworldQueryCodeAddonField_Acquire"), 0x023C2B00, 92)
    hosted(symbols.get("OverworldQueryCodeAddonField_Unload"), 0x023C2B70, 28)
    hosted(symbols.get("OverworldThrowObservation_Observe"), 0x023C2BA0, 124)
    hosted(symbols.get("OverworldThrowObservation_BindingPosition"), 0x023C2DA0, 238)
    hosted(symbols.get("Addon_StockCoordinateImport"), 0x023C2D80,
           low=0x023C2D80, high=0x023C2DA0)
    for suffix, imported, address, _words in CACHE:
        checked(symbols.get(imported) == (address, 0, "FUNC", "ABS"),
                "native cache import lost exact ARM metadata")
        wrapper = symbols.get("OverworldQueryCodeAddon_" + suffix)
        hosted(wrapper, size=12)
        checked(elf_bytes_at(selector, wrapper[0] & ~1, 12)
                == bytes.fromhex("10 b5 01 4b 98 47 10 bd") + struct.pack("<I", address),
                "cache wrapper is not its exact typed ARM BLX and literal")
    return symbols


def verify_current_acquire(selector, wild, packaged_selector, packaged_wild):
    symbols = verify_selector(selector, packaged_selector)
    name = "OverworldWildSpawns_QueryAddon"
    caller = elf_helper_bindings(wild, (name,)).get(name)
    checked(caller is not None and caller[2] == "FUNC" and caller[0] & 1
            and caller[3] not in ("ABS", "UND") and caller[1] > 0,
            "current-context caller is not a hosted Thumb function")
    body = elf_bytes_at(wild, caller[0] & ~1, caller[1])
    checked(body == packaged_wild, "current-context caller linked/package bytes differ")
    checked(body.count(struct.pack("<I", symbols["OverworldQueryCodeAddonField_AcquireCurrent"][0])) == 1,
            "current-context caller lacks its exact private Thumb borrow")
    return symbols



PUBLICATION_OWNERS = {
    "OverworldConditionPublication_InitResult": (159, "overworld_mount_chain_overlay_linked.o", 0x01FF9A49, 40, 40),
    "OverworldConditionPublication_FoldResult": (159, "overworld_mount_chain_overlay_linked.o", 0x01FF9C95, 72, 72),
    "OverworldConditionPublication_BlobValid": (159, "overworld_mount_chain_overlay_linked.o", 0x01FFA39D, 76, 100),
    "OverworldConditionPublication_CapturePrior": (152, "overworld_follower_selector_overlay_linked.o", 0x023C2F75, 78, 88),
    "OverworldConditionPublication_ChangedMask": (152, "overworld_follower_selector_overlay_linked.o", 0x023C2FCD, 36, 36),
}
FIXED_TABLE_IMPORTS = (0x023DEEA3, 0x023DEEBF, 0x023DEE4D,
                       0x01FF9A49, 0x01FF9C95, 0x01FFA39D, 0x023C2F75,
                       0x02208201, 0x023C7EA9)
CONDITION_IMPORT_OWNERS = {
    "OverworldBehaviorPackedOptions_Apply":
        (161, "player_health_overlay_linked.o", 0x01FFD2CD, 103, 106),
    "OverworldConditionSubject_Populate":
        (1, "overworld_field_capsule_linked.o", 0x02208201, 186, 192),
    "OverworldConditionVisibility_TraceBlocked":
        (151, "overworld_wild_helper_overlay_linked.o", 0x023C7EA9, 162, 184),
}
# Named vanilla PlayerAvatar_GetXCoord/GetZCoord. These Thumb wrappers read
# the current Player map object, then its current X/Z coordinate.
CONDITION_STOCK_IMPORTS = {
    "OverworldConditionVisibility_PlayerX":
        (0x0205C67D, bytes.fromhex("08b500f02df803f047f908bd")),
    "OverworldConditionVisibility_PlayerY":
        (0x0205C689, bytes.fromhex("08b500f027f803f051f908bd")),
}


def actor_evaluation_contract(binding, frame, linked, packaged):
    # The native condition adapter uses callback152 without changing its
    # fixed880-byte slot or current-frame reader at0x023B6930.
    checked(binding is not None and binding[:3] == (0x023B65C1, 880, "FUNC")
            and binding[3] not in ("ABS", "UND"), "Actor evaluation owner differs")
    checked(frame is not None and frame[:3] == (FRAME_ADDR | 1, FRAME_SIZE, "FUNC")
            and frame[3] not in ("ABS", "UND"), "Actor frame reader owner differs")
    checked(len(linked) == 880 and linked == packaged,
            "Actor evaluation linked/package bytes differ")
    checked(linked[0xA4:0xC2] == bytes.fromhex(
                "5820684331184c68a24b11941a69109710a80a919047022409900028afd0")
            and linked[0x330:0x340]
                == struct.pack("<4I", 0x023C22B9, 0x854, 0x023C22F0, 0x00380002),
            "Actor native condition borrow lacks its current owner/packet gate")
    checked(linked[0x108:0x120] == bytes.fromhex(
                "4e20012309990aaa8418983123700a6812a89047041e00d0")
            and linked[0x218:0x222] == bytes.fromhex("099a12a898321468a047"),
            "Actor native condition callback152 dispatch differs")
    base, size = binding[0] & ~1, binding[1]
    targets = []
    for offset in range(0, size - 3, 2):
        first, second = struct.unpack_from("<2H", linked, offset)
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            targets.append(thumb_bl_target(linked, base, base + offset))
    checked(targets.count(0x023C2FCC) == 1,
            "Actor does not borrow the exact publication mask once")
    checked(targets.count(0x023B6930) == 1
            and thumb_bl_target(linked, base, base + 0x84) == 0x023B6930,
            "Actor native condition lacks its one prior current Frame call")


def verify_publication_imports(build, overlays):
    """The four Query imports and Actor mask borrow have fixed native owners."""
    for name, (overlay, filename, address, size, extent) in PUBLICATION_OWNERS.items():
        elf = build / filename
        binding = elf_helper_bindings(elf, (name,)).get(name)
        checked(binding is not None and binding[:3] == (address, size, "FUNC")
                and binding[3] not in ("ABS", "UND"),
                "private publication helper mode/address/extent differs")
        checked(elf_bytes_at(elf, address & ~1, extent)
                == overlay_span(overlays, overlay, address & ~1, extent),
                "private publication helper linked/package bytes differ")
        if name == "OverworldConditionPublication_BlobValid":
            checked(elf_bytes_at(elf, address & ~1, extent)[size:] == b"\xff" * (extent - size),
                    "private blob validator exceeds its fixed 100-byte owner")
    chain = build / "overworld_mount_chain_overlay_linked.o"
    name = "gOverworldConditionPublicationImports"
    binding = elf_helper_bindings(chain, (name,)).get(name)
    expected = struct.pack("<9I", *FIXED_TABLE_IMPORTS)
    checked(binding is not None and binding[:3] == (0x01FF9CDC, 36, "OBJECT")
            and binding[3] not in ("ABS", "UND")
            and elf_bytes_at(chain, 0x01FF9CDC, 36)
                == overlay_span(overlays, 159, 0x01FF9CDC, 36) == expected,
            "exact nine-target native import whitelist differs")
    selector = build / "overworld_follower_selector_overlay_linked.o"
    for name in ("OverworldConditionPublication_InitResult", "OverworldConditionPublication_FoldResult"):
        address = packer().IMPORTS[name]
        checked(elf_helper_bindings(selector, (name,)).get(name)
                == (address, 0, "FUNC", "ABS"),
                "Selector publication borrow is not its exact Thumb alias")
    body = elf_bytes_at(selector, 0x023C2F74, 88)
    checked(thumb_bl_target(body, 0x023C2F74, 0x023C2F82) == 0x01FF9C94
            and thumb_bl_target(body, 0x023C2F74, 0x023C2FBC) == 0x01FF9A48,
            "Selector publication direct Thumb calls differ")
    actor = build / "overworld_actor_system_overlay_linked.o"
    name = "OverworldConditionPublication_ChangedMask"
    checked(elf_helper_bindings(actor, (name,)).get(name)
            == (0x023C2FCD, 0, "FUNC", "ABS"),
            "Actor publication mask borrow differs")
    name = "OverworldBehaviorConditionAdapter_EvaluateActor"
    binding = elf_helper_bindings(actor, (name,)).get(name)
    frame = elf_helper_bindings(actor,
        ("OverworldBehaviorConditionAdapter_BuildFrame",)).get(
            "OverworldBehaviorConditionAdapter_BuildFrame")
    actor_evaluation_contract(binding, frame,
        elf_bytes_at(actor, 0x023B65C0, 880),
        overlay_span(overlays, 158, 0x023B65C0, 880))
    frame_reader_contract(frame, elf_bytes_at(actor, FRAME_ADDR, FRAME_SIZE),
        overlay_span(overlays, 158, FRAME_ADDR, FRAME_SIZE))


# Entry196/39 keeps one heap image. Condition runtime now lives in its
# authenticated tail; only callbacks60/64/72 cross from the entry to this owner.
CONDITION_NATIVE_OWNERS = {'Native_HandleEquals': (34113304, 26),
 'Native_AccessObject': (34113330, 196),
 'Native_AccessPose': (34113526, 346),
 'OverworldBehaviorConditionAdapter_MovingAllowed': (34113872, 276),
 'OverworldBehaviorConditionAdapter_CollectWinningEntries': (34114148, 484),
 'Native_Visibility': (34114632, 224),
 'OverworldBehaviorConditionAdapter_EvaluateMovingNotice.constprop.0': (34114856, 440),
 'OverworldHopPresentation_Run': (34115296, 540),
 'OverworldConditionNative_Run': (34115836, 1580)}

CONDITION_NATIVE_SHA256 = {'Native_HandleEquals': '3fbada859dd3942e7716cbf087e3789c05b87ddd19b8a11b2127c956a7b07f59',
 'Native_AccessObject': '1e619897fe38cbe57bc2e7593dad2f947135c4117576d1a9b2e4359089a0bb7b',
 'Native_AccessPose': '90f18605bf261e380506bdb7e6852e91f01b503fe172a93a36fd390a581eb3a7',
 'OverworldBehaviorConditionAdapter_MovingAllowed': '642990625f53e0943a1f62e6cd70f020e7b7290547aeaf289087a8536089df9c',
 'OverworldBehaviorConditionAdapter_CollectWinningEntries': 'efdd617fa1dd4544c32a142d4a4b936b0e9be663e56f944fc69cb25b016e0ccb',
 'Native_Visibility': '19981bdfd6d32693509874c015ed1eeca296339c05e2c5a11765db483f8be583',
 'OverworldBehaviorConditionAdapter_EvaluateMovingNotice.constprop.0': '78c9b9be04d94658a80214e90a4495dfe0eea7a251a3811db6ebd344e3401d87',
 'OverworldHopPresentation_Run': '48a85b4fb68dfcdac84adbe7e1f3c7a969b4db13a9dbd5baad27ce3deb10a717',
 'OverworldConditionNative_Run': 'b917228445052ec3fe2b26f7befd00f2aaada86e3ff4e436d1d7c4bf3d9c712b'}

RESOLVER_NATIVE_OWNERS = {'BehaviorResolver_ReadFieldValue': (34117416, 58),
 'BehaviorResolver_MatchApplies': (34117474, 102),
 'BehaviorResolver_LegacySpawnDestinationMask': (34117576, 72),
 'BehaviorResolver_ApplyMask': (34117648, 592),
 'BehaviorResolver_NormalizeLane': (34118240, 414),
 'BehaviorResolver_BlobValid': (34118654, 66),
 'BehaviorResolver_RequestValid': (34118720, 584),
 'BehaviorResolver_FingerprintBytes': (34119304, 28),
 'BehaviorResolver_FingerprintU32': (34119332, 28),
 'BehaviorResolver_Trace': (34119360, 96),
 'BehaviorResolver_SelectClassInternal': (34119456, 192),
 'BehaviorResolver_ApplyRecorded': (34119648, 380),
 'OverworldBehaviorResolver_ValidateRequest': (34120028, 64),
 'BehaviorResolver_InspectClass': (34120092, 136),
 'BehaviorResolver_Resolve': (34120228, 1708),
 'OverworldBehaviorResolver_QueryCall': (34122116, 128)}

RESOLVER_NATIVE_SHA256 = {'BehaviorResolver_ReadFieldValue': 'c7388af36e377181844b83c82b3a6614cda0997d2600f704dc2780bd50f9460d',
 'BehaviorResolver_MatchApplies': '5d57a4efc86f716c7135df4def91ff36a1a4da9eb89697c65161f33bd7c84bf7',
 'BehaviorResolver_LegacySpawnDestinationMask': '0555dcc19ffc042cc0b7e9bef54857cd2a7ec8e8aa8cf042419fd13824b86565',
 'BehaviorResolver_ApplyMask': 'eb7ab788f1cc4fb9c0f5293ae2c3f8954513cfcdcd7ff569b52f68a5d9f14ff3',
 'BehaviorResolver_NormalizeLane': '9241b19a09c5ed1a81c3133004902e0c484c68e9fc6779d63921e1a12f846ef0',
 'BehaviorResolver_BlobValid': 'bba49407aff239dc196fecfddddd0a08d600c130614862161be4fdb931192aac',
 'BehaviorResolver_RequestValid': 'a8040865f2f30bcaa8e1191edbea631a1383afabb766531deb32cbf975dffc85',
 'BehaviorResolver_FingerprintBytes': '9f1aca64ade144669d6a8d71c27d5e436768fe2ecd9b33d448505ebf325c1133',
 'BehaviorResolver_FingerprintU32': '2633b90c9217749d305c93500d8ae8e3ca3255828982a73032c94cf5288b3c17',
 'BehaviorResolver_Trace': '0170ba10aba959692e6b5187067ebb58ac3fea488ed81f742911f325045a161a',
 'BehaviorResolver_SelectClassInternal': 'a3ffb6e34959f203bac75b1c0177795bd36e0f40bf24afcd12e7afbca85105bc',
 'BehaviorResolver_ApplyRecorded': 'a433fbfc55d90f5c317374d236c51187ddfc7d98218f95c034939503b56a06ba',
 'OverworldBehaviorResolver_ValidateRequest': '3a2c25ed0c421cb7170b6ad07c47c4724759947a376f59b9e6da23dc5ec7c5e4',
 'BehaviorResolver_InspectClass': '1f18a48bf30b0a4cee10e45ed9c586f19570e11b574a7859b050e22b80e11d83',
 'BehaviorResolver_Resolve': 'c4a2be5265eac11ac1d9eba2d03afe12caa7af878847595728d0f9119c763ee9',
 'OverworldBehaviorResolver_QueryCall': 'cd23f16bce460322ae6ad33ef9f6441b41fa87b2636b7a94aad14f6ade2c65c3'}

CONDITION_RUNTIME_CALLBACK_OWNERS = {'OverworldBehaviorCondition_PrepareActor': (34110956, 256),
 'OverworldBehaviorCondition_EvaluatePrepared': (34111212, 2092),
 'OverworldBehaviorCondition_NotifyWorldEffect': (34110528, 102)}
CONDITION_RUNTIME_CALLBACK_SHA256 = {'OverworldBehaviorCondition_PrepareActor': '52ce8405fc51a1017b9c002f41892c7dd1dd4149c581f166a45b73d910be1b85',
 'OverworldBehaviorCondition_EvaluatePrepared': '67779369b1413902fdb03d5d0f90752fd61cf5f5b00aefd5e535d35e7af4c2ae',
 'OverworldBehaviorCondition_NotifyWorldEffect': 'c71c7ee42b7e7f8c29d35766640974ffa56026923a89460bcbf3463aad844c16'}
CONDITION_NATIVE_OWNERS.update(CONDITION_RUNTIME_CALLBACK_OWNERS)
CONDITION_NATIVE_SHA256.update(CONDITION_RUNTIME_CALLBACK_SHA256)
CONDITION_NATIVE_OWNERS.update(RESOLVER_NATIVE_OWNERS)
CONDITION_NATIVE_SHA256.update(RESOLVER_NATIVE_SHA256)
RESOLVER_CODE_START, RESOLVER_CODE_END = 0x2089728, 0x208aa04
RESOLVER_CODE_SHA256 = "b6352e0034f3c958ff0b2afa29276bf9f4316f5a8902b9aa00e18975e0c03c64"

CONDITION_NATIVE_DIRECT_CALLS = {'Native_AccessObject': ((74, 34113304), (140, 34113304)),
 'OverworldBehaviorConditionAdapter_EvaluateMovingNotice.constprop.0': ((72,
                                                                         34113872),
                                                                        (172,
                                                                         34114632),
                                                                        (340,
                                                                         34114632)),
 'OverworldBehaviorConditionAdapter_MovingAllowed': ((146, 34113304),),
 'OverworldConditionNative_Run': ((172, 34113304),
                                  (378, 34115296),
                                  (926, 34113330),
                                  (994, 34113526),
                                  (1048, 34113330),
                                  (1112, 34113526),
                                  (1418, 34114856),
                                  (1506, 34114148))}

# The sole CargoWild Entry branch borrows this native reducer synchronously.
# Its original NULL-control Entry path and all ordinary Cargo work stay guarded.
ENTRY_NATIVE_QUERY_OWNERS = {'OverworldCargoQueryWild_Tick': (34128500, 5552),
 'OverworldEntryRoute_NativeControl': (34141536, 2692)}
ENTRY_NATIVE_QUERY_SHA256 = {'OverworldCargoQueryWild_Tick': 'b1e682e34fe4500290d1c4e39584e9701f54ece07232e3890567b1f7341806eb',
 'OverworldEntryRoute_NativeControl': 'aecd248fb30949a3c5da0012e0a3b5bf4098ea2231c4d143fd9784aa87ee8454'}

def entry_native_query_contract(native, read):
    low = native.get("__query_return_code_end", (0,))[0]
    high = native.get("__query_entry_code_end", (0,))[0]
    checked((low, high) == (0x208b0d8, 0x2090c08),
            "Entry native code boundaries differ")
    for name, (address, size) in ENTRY_NATIVE_QUERY_OWNERS.items():
        hosted(native.get(name), address, size, low=low, high=high)
        body = read(address, size)
        checked(len(body) == size and hashlib.sha256(body).hexdigest()
                == ENTRY_NATIVE_QUERY_SHA256[name],
                "Entry native full guarded body differs: " + name)
    cargo = read(0x208c274, 5552)
    checked(read(0x02080000 + 112, 4) == struct.pack("<I", 0x208c275)
            and cargo[0x2A:0x46] == bytes.fromhex(
                "5b7f1393012b01d000f0b3fe0d9b9e68002e09d0736d1793002b10d0")
            and cargo[0x4A:0x4E] == bytes.fromhex("8c4b9847")
            and cargo[0x27C:0x280] == struct.pack("<I", 0x208f561),
            "Entry native route1/NULL-control gate or typed long-call differs")


def condition_native_contract(native, read):
    """Seal the typed bank/Arc dispatcher and every current physical leaf."""
    low = native.get("__query_cargo_code_end", (0,))[0]
    high = native.get("__query_return_code_end", (0,))[0]
    checked((low, high) == (0x2085e5c, 0x208b0d8),
            "native Condition code boundaries differ")
    for name, (address, size) in CONDITION_NATIVE_OWNERS.items():
        hosted(native.get(name), address, size, low=low, high=high)
        body = read(address, size)
        checked(len(body) == size and hashlib.sha256(body).hexdigest()
                == CONDITION_NATIVE_SHA256[name],
                "native Condition full guarded body differs: " + name)
        for offset, target in CONDITION_NATIVE_DIRECT_CALLS.get(name, ()):
            checked(thumb_bl_target(body, address, address + offset) == target,
                    "native Condition bank/Arc direct target differs")
    for offset, name in ((60, "OverworldBehaviorCondition_PrepareActor"),
                         (64, "OverworldBehaviorCondition_EvaluatePrepared"),
                         (72, "OverworldBehaviorCondition_NotifyWorldEffect")):
        checked(read(0x02080000 + offset, 4)
                == struct.pack("<I", CONDITION_RUNTIME_CALLBACK_OWNERS[name][0] | 1),
                "native Condition runtime callback differs: " + name)
    checked(read(0x02080000 + 152, 4) == struct.pack("<I", 0x20890fd),
            "native Condition dispatcher is not the exact callback152")
    # Real Resolver runs after the Cargo boundary. Only its named callback68
    # enters this borrowed32B dispatch; packed merge remains one typed import.
    checked(read(0x02080000 + 68, 4) == struct.pack("<I", 0x208a985),
            "native Resolver is not its exact typed callback68")
    checked(native.get("OverworldBehaviorPackedOptions_Apply")
            == (0x01FFD2CD, 0, "FUNC", "ABS"),
            "native Resolver packed merge import lost exact odd Thumb metadata")
    checked(read(0x208a154, 4) == struct.pack("<I", 0x01FFD2CD)
            and read(0x208a0ac, 2) == bytes.fromhex("9847"),
            "native Resolver packed merge is not its exact odd BLX import")
    checked(hashlib.sha256(read(RESOLVER_CODE_START,
                RESOLVER_CODE_END-RESOLVER_CODE_START)).hexdigest() == RESOLVER_CODE_SHA256,
            "full Resolver guarded code/constants differ")
    dispatch = read(0x208a984, 128)
    checked(dispatch[0x6C:0x80] == struct.pack("<5I", 0x00200001,
                0x00FFFF00, 0x208a15d, 0x208a225, 0x208a19d),
            "Resolver32B packet/reserved/three typed operation targets differ")
    moving = read(0x2088d28, 440)
    checked(moving[0x94:0x9E] == bytes.fromhex("404f019300960a9bb847")
            and moving[0x198:0x19C] == struct.pack("<I", 0x02208201),
            "native moving Condition lacks its exact Subject population borrow")
    visibility = read(0x2088c48, 224)
    checked(visibility[0xD4:0xE0]
            == struct.pack("<3I", 0x0205C67D, 0x0205C689, 0x023C7EA9),
            "native moving visibility lacks its exact coordinate/solid trace imports")
    run = read(0x20890fc, 1580)
    # The real common packet gate dispatches op7 before the ordinary op0..2
    # arm. Arc validates its borrowed local map and full current subject;
    # it cannot call the resolver, publish metadata, or replace motion.
    # World84 extends the same local value by eight bytes: native stack188
    # and memcpy84 replace stack180/memcpy76; the packet/op gate is unchanged.
    checked(run[:0x34] == bytes.fromhex(
                "f0b50400afb0002803d1012738002fb0f0bd9c4b826a9a42f7d1"
                "03002f331f78002ff2d1013b1a78072a00d0a2e08368002bead0")
            and run[0x3BE:0x3C0] == bytes.fromhex("5422")
            and run[0x284:0x298] == struct.pack("<5I",
                0x00380002, 0x01FFA39D, 0x857, 0x6C6, 0x6BC),
            "native Condition bank/Arc packet/operation branch differs")

def verify_condition_imports(build, overlays, arm9, arm9_address):
    """Four exact synchronous native leaves supplement the fixed table."""
    image = build / "overworld_query_code_addon/image.elf"
    names = tuple(CONDITION_NATIVE_OWNERS) + ("__query_cargo_code_end", "__query_return_code_end",
        "OverworldBehaviorPackedOptions_Apply")
    condition_native_contract(elf_helper_bindings(image, names),
        lambda address, size: elf_bytes_at(image, address, size))
    entry_native_query_contract(elf_helper_bindings(image,
        tuple(ENTRY_NATIVE_QUERY_OWNERS) + ("__query_return_code_end", "__query_entry_code_end")),
        lambda address, size: elf_bytes_at(image, address, size))
    for name, (overlay, filename, address, size, extent) in CONDITION_IMPORT_OWNERS.items():
        owner = build / filename
        binding = elf_helper_bindings(owner, (name,)).get(name)
        checked(binding is not None and binding[:3] == (address, size, "FUNC")
                and binding[3] not in ("ABS", "UND"),
                "native Condition import owner mode/address/extent differs")
        checked(elf_bytes_at(owner, address & ~1, extent)
                == overlay_span(overlays, overlay, address & ~1, extent),
                "native Condition import linked/package bytes differ")
    stock = (build / "arm9.bin").read_bytes()
    for _name, (address, expected) in CONDITION_STOCK_IMPORTS.items():
        offset = (address & ~1) - arm9_address
        stock_offset = (address & ~1) - 0x02000000
        checked(0 <= offset <= len(arm9) - len(expected)
                and arm9[offset:offset + len(expected)] == expected
                and stock[stock_offset:stock_offset + len(expected)] == expected,
                "native Condition Player coordinate Thumb body differs")
    selector = build / "overworld_follower_selector_overlay_linked.o"
    name = "Addon_StockCoordinateImport"
    binding = elf_helper_bindings(selector, (name,)).get(name)
    hosted(binding, 0x023C2D80, low=0x023C2D80, high=0x023C2DA0)
    body = elf_bytes_at(selector, binding[0] & ~1, binding[1])
    # The same32B native leaf admits only the two stock coordinate targets
    # and the typed packed-options merge. No table or code home grows.
    checked(binding[1] == 32 and body == bytes.fromhex("054b984206d0054bc01a0c2802d043425841704701207047cdd2ff017dc60502"),
            "optional fixed import leaf lacks its exact three-target predicate")
    name = "OverworldQueryCodeAddon_Load"
    binding = elf_helper_bindings(selector, (name,)).get(name)
    hosted(binding)
    body = elf_bytes_at(selector, binding[0] & ~1, binding[1])
    extra = tuple(row[2] for row in CONDITION_IMPORT_OWNERS.values())\
        + tuple(row[0] for row in CONDITION_STOCK_IMPORTS.values())
    base = binding[0] & ~1
    calls = []
    for offset in range(0, binding[1] - 3, 2):
        first, second = struct.unpack_from("<2H", body, offset)
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            calls.append(thumb_bl_target(body, base, base + offset))
    checked(calls.count(0x023C2D80) == 1,
            "loader lacks its one exact stock coordinate import check")
    checked(set(packer().IMPORTS.values()) == set(FIXED_TABLE_IMPORTS) | set(extra)
            and len(packer().IMPORTS) == 12,
            "exact twelve-target Query import inventory differs")


def verify_package(build, rom, member):
    directory = build / "overworld_query_code_addon"
    blob, receipt = packer().package((directory / "image.elf").read_bytes())
    header = (ROOT / "include/overworld_query_code_addon.h").read_text()
    for key, value in {
        "VERSION": 9, "ENTRY_BYTES": 196, "CALLBACKS": 39,
        "MAX_IMAGE": 0x10C38, "MAX_BLOB": 0x11200,
        "MAX_RELOCATIONS": 256,
    }.items():
        match = re.search(r"^#define OVERWORLD_QUERY_CODE_ADDON_" + key + r"\s+(0x[0-9A-Fa-f]+|[0-9]+)\b", header, re.M)
        checked(match is not None and int(match.group(1), 0) == value,
                "public Query package ABI/cap differs: " + key)
    checked(member == blob == (directory / "query.bin").read_bytes()
            == (build / "a028/9_21").read_bytes(),
            "member21 does not match its exact linked/generated/staged package")
    checked(json.loads((directory / "package.json").read_text()) == json.loads(json.dumps(receipt)),
            "generated relocation/byte receipt differs")
    checked((directory / "overworld_query_code_addon_package.h").read_text()
            == generated_header(blob, receipt), "native exact-size/checksum header differs")
    overlays = rom_overlays(rom)
    verify_wild_callbacks(build, overlays)
    verify_mount_hop_callbacks(build, overlays)
    wild = build / "overworld_wild_spawns_overlay_linked.o"
    caller = elf_helper_bindings(wild, ("OverworldWildSpawns_QueryAddon",)).get("OverworldWildSpawns_QueryAddon")
    checked(caller is not None, "current-context caller is missing")
    verify_current_acquire(build / "overworld_follower_selector_overlay_linked.o", wild,
        overlay_span(overlays, 152, PUBLIC_ENTRY, 0x023C3000 - PUBLIC_ENTRY),
        overlay_span(overlays, 149, caller[0] & ~1, caller[1]))
    health = build / "player_health_overlay_linked.o"
    table = elf_helper_bindings(health, ("gPlayerHealthThrowServiceEntry",)).get("gPlayerHealthThrowServiceEntry")
    checked(table is not None and table[:3] == (0x01FFC180, 32, "OBJECT")
            and table[3] not in ("ABS", "UND"), "unchanged Throw service entry moved")
    raw_table = elf_bytes_at(health, 0x01FFC180, 32)
    checked(raw_table == overlay_span(overlays, 161, 0x01FFC180, 32),
            "Throw service linked/package table differs")
    fields = struct.unpack("<IHH6I", raw_table)
    checked(fields[:3] == (0x4F485450, 2, 32)
            and fields[3] == 0x023C2BA1 and fields[8] == 0x023C2DA1,
            "Throw service does not publish its exact private Thumb observations")
    # These exact stock ARM routines come from named NitroSDK os_cache.c.
    arm9_offset, _entry, arm9_address, arm9_size = struct.unpack_from("<4I", rom, 0x20)
    checked(arm9_offset + arm9_size <= len(rom), "ARM9 image exceeds the ROM")
    verify_direction_callbacks(rom[arm9_offset:arm9_offset + arm9_size], arm9_address)
    for _suffix, _name, address, words in CACHE:
        offset = address - arm9_address
        expected = struct.pack("<" + "I" * len(words), *words)
        checked(0 <= offset <= arm9_size - len(expected)
                and rom[arm9_offset + offset:arm9_offset + offset + len(expected)] == expected,
                "native cache instruction body differs")
    verify_publication_imports(build, overlays)
    verify_condition_imports(build, overlays,
        rom[arm9_offset:arm9_offset + arm9_size], arm9_address)
    imports = elf_helper_bindings(directory / "image.elf", packer().IMPORTS)
    core = build / "linked.o"
    resident = elf_helper_bindings(core, packer().IMPORTS)
    for name, address in packer().IMPORTS.items():
        checked(imports.get(name) == (address, 0, "FUNC", "ABS"),
                "addon fixed import is not typed Thumb")
        if name in PUBLICATION_OWNERS or name in CONDITION_IMPORT_OWNERS\
                or name in CONDITION_STOCK_IMPORTS:
            continue
        checked(resident.get(name, ())[:3] == (address, 8, "FUNC")
                and resident[name][3] not in ("ABS", "UND"),
                "addon fixed import has no exact resident owner")
        expected = overworld_core_helper_body(name)
        checked(elf_bytes_at(core, address & ~1, 8)
                == overlay_span(overlays, 129, address & ~1, 8) == expected,
                "addon native fixed-import body/mode differs")
    return receipt


def verify_two_bases(elf, second_image):
    blob, receipt = packer().package(elf.read_bytes())
    image = bytearray(blob[64:64 + receipt["imageBytes"]])
    for offset in receipt["localAbs32"]:
        word = struct.unpack_from("<I", image, offset)[0]
        struct.pack_into("<I", image, offset, word + 0x100000)
    checked(bytes(image) == second_image.read_bytes(),
            "relocated image differs from an independent second-base link")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--second-image", type=Path)
    args = parser.parse_args()
    checked(args.elf is not None and args.second_image is not None,
            "scratch proof needs both independently linked images")
    receipt = verify_two_bases(args.elf, args.second_image)
    print(f"PASS exact query addon relocation at two bases: {receipt['imageBytes']} image bytes")


if __name__ == "__main__":
    main()
