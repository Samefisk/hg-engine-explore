#!/usr/bin/env python3
"""Verify structural deletion of duplicate overworld domain owners.

Adapter names do not prove ownership. Input, collision, streaming, world and
presentation adapters are expected to remain. This gate authenticates the
fixed owner ABIs, rejects direct private-state and owner-body access, rejects
retired entry tables even after renaming, and permits only byte-exact thunks.
With ``--rom`` it also authenticates every checked linked overlay against the
build output and packaged ROM.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
from typing import Iterable, Mapping, Sequence


REPO = Path(__file__).resolve().parents[1]
ROM_HEADER_FAT_OFFSET = 0x48
ROM_HEADER_Y9_OFFSET = 0x50
OVERLAY_ROW_SIZE = 0x20
PACKAGED_TYPES = frozenset("TtDdRrVvWw")
DEFINED_TYPES = frozenset("TtBbDdRrSsVvWw")

ACTOR_LOAD_BASE = 0x023B65A0
ACTOR_BASE = 0x023B6B00
ACTOR_END = 0x023BAB00
ACTOR_FACADE_ENTRY = ACTOR_BASE
ACTOR_COMPAT_ENTRY = ACTOR_BASE + 0x18
ACTOR_DEBUG_ENTRY = ACTOR_BASE + 0x38
ACTOR_MOTION_ENTRY = ACTOR_BASE + 0x88
ACTOR_POPULATION_ENTRY = ACTOR_BASE + 0x98
ACTOR_MOVEMENT_POLICY_ENTRY = ACTOR_BASE + 0xA8
WILD_RUNTIME_ENTRY = 0x023BC800
WALK_OWNER_ENTRY = 0x023BC834
MOTION_BOUNDARY_BRIDGE = 0x023BD350
MOTION_BOUNDARY_BRIDGE_END = 0x023BD3C4
WILD_MOTION_RECEIPT = 0x023BD3C4
WILD_MOTION_RECEIPT_END = 0x023BD3EC
WILD_HELPER_FLEE_FALLBACK_ENTRY = 0x023C40F8
WILD_SPAWNS_ENTRY = 0x023CD000
WILD_RUNTIME_POPULATION_CALLBACK_OFFSET = 24
WILD_RUNTIME_ACKNOWLEDGE_CALLBACK_OFFSET = 36
LEGACY_POPULATION_THUNK = b"\x01\x4b\xdb\x68\x18\x47\xc0\x46\x98\x6b\x3b\x02"


@dataclass(frozen=True)
class ModuleSpec:
    key: str
    linked: str
    output: str
    overlay_id: int
    base: int
    package_base: int | None = None

    @property
    def expected_package_base(self) -> int:
        return self.base if self.package_base is None else self.package_base


MODULES = (
    ModuleSpec("actor_system", "build/overworld_actor_system_overlay_linked.o", "build/output_overworld_actor_system_overlay.bin", 158, ACTOR_LOAD_BASE),
    ModuleSpec("mount", "build/overworld_mount_overlay_linked.o", "build/output_overworld_mount_overlay.bin", 157, 0x023BAB00),
    # Wild spawns is overlay 149. Overlay 131 is the field overlay.
    ModuleSpec("wild_spawns", "build/overworld_wild_spawns_overlay_linked.o", "build/output_overworld_wild_spawns_overlay.bin", 149, 0x023CCFD8),
    ModuleSpec("wild_runtime", "build/overworld_wild_runtime_overlay_linked.o", "build/output_overworld_wild_runtime_overlay.bin", 156, WILD_RUNTIME_ENTRY),
    ModuleSpec("walk_module", "build/pokemon_move_history_overlay_linked.o", "build/output_pokemon_move_history_overlay.bin", 153, 0x023BE400),
    ModuleSpec("role_controller", "build/pokemon_move_history_task6_overlay_linked.o", "build/output_pokemon_move_history_task6_overlay.bin", 155, 0x023BD400),
    ModuleSpec("wild_helper", "build/overworld_wild_helper_overlay_linked.o", "build/output_overworld_wild_helper_overlay.bin", 151, 0x023C4000),
    ModuleSpec("wild_behavior_data", "build/overworld_wild_behavior_data_overlay_linked.o", "build/output_overworld_wild_behavior_data_overlay.bin", 150, 0x023C3000),
    ModuleSpec("follower_selector", "build/overworld_follower_selector_overlay_linked.o", "build/output_overworld_follower_selector_overlay.bin", 152, 0x023C0400),
    ModuleSpec("field", "build/field_linked.o", "build/output_field.bin", 131, 0x023C8000),
    ModuleSpec("follower_selector_icons", "build/overworld_follower_selector_icons_overlay2_linked.o", "build/output_overworld_follower_selector_icons_overlay2.bin", 2, 0x0224EF98, 0x02245B80),
    ModuleSpec("follower_release", "build/overworld_follower_release_overlay2_linked.o", "build/output_overworld_follower_release_overlay2.bin", 2, 0x02250114, 0x02245B80),
)

CLIENT_MODULES = tuple(spec.key for spec in MODULES if spec.key != "actor_system")
MOTION_PLANNER_CLIENTS = tuple(
    key for key in CLIENT_MODULES if key != "role_controller"
)


@dataclass(frozen=True)
class Symbol:
    module: str
    address: int
    size: int
    kind: str
    name: str

    @property
    def stable_name(self) -> str:
        return re.sub(r"\.(?:isra|constprop|part|clone)\.\d+$", "", self.name)


@dataclass(frozen=True)
class RetiredEntry:
    capability: str
    module: str
    address: int
    size: int
    label: str


# Deployment ABIs for private mechanics that the completed roadmap removes.
# The old Walk table range now hosts direct typed helpers, so it is checked by
# the Walk ownership and package verifiers instead of as zero retired storage.
# The fixed mount-target rebase thunk at 0x023BFFEA is intentionally not here.
RETIRED_ENTRIES = (
    RetiredEntry("hop", "wild_behavior_data", 0x023C3F18, 0x28, "staged-Hop task pointers"),
    RetiredEntry("role", "mount", 0x023BB5E0, 0x10, "wild movement policy"),
    RetiredEntry("hop", "role_controller", 0x023BD4D8, 0x18, "wild Hop trajectory"),
    RetiredEntry("role", "wild_helper", WILD_HELPER_FLEE_FALLBACK_ENTRY, 0x08, "wild flee fallback policy"),
)

PRIVATE_WILD_STATE_SOURCE_CLIENTS = (
    (
        "walk_shadow_asm",
        "asm/pokemon_move_history_overlay/overworld_wild_shadow_filter.s",
    ),
    (
        "walk_module",
        "src/pokemon_move_history_overlay/overworld_walk_module.c",
    ),
)
WILD_NATIVE_SHADOW_OWNER_SOURCE = (
    "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
)
NATIVE_SHADOW_STOCK_PATCH_SOURCE = "armips/asm/overworld_wild_shadow.s"
ACTOR_SYSTEM_OWNER_SOURCE = (
    "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c"
)
MOUNT_STREAM_CLIENT_SOURCE = (
    "src/overworld_mount_overlay/overworld_mount_overlay.c"
)


def parse_nm(text: str, module: str) -> list[Symbol]:
    symbols: list[Symbol] = []
    with_size = re.compile(r"^\s*([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+([A-Za-z?])\s+(.+?)\s*$")
    without_size = re.compile(r"^\s*([0-9A-Fa-f]+)\s+([A-Za-z?])\s+(.+?)\s*$")
    for line in text.splitlines():
        match = with_size.match(line)
        if match is not None:
            address_text, size_text, kind, name = match.groups()
            size = int(size_text, 16)
        else:
            match = without_size.match(line)
            if match is None:
                continue
            address_text, kind, name = match.groups()
            size = 0
        if kind in DEFINED_TYPES:
            symbols.append(Symbol(module, int(address_text, 16), size, kind, name))
    return symbols


def _c_noncode_mask(source: str) -> str:
    """Preserve offsets while hiding comments and string/character literals."""
    result = list(source)
    index = 0
    state = "code"
    quote = ""
    while index < len(source):
        current = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if current == "/" and following == "/":
                result[index] = result[index + 1] = " "
                index += 2
                state = "line-comment"
                continue
            if current == "/" and following == "*":
                result[index] = result[index + 1] = " "
                index += 2
                state = "block-comment"
                continue
            if current in ('"', "'"):
                quote = current
                result[index] = " "
                index += 1
                state = "literal"
                continue
        elif state == "line-comment":
            if current == "\n":
                state = "code"
            else:
                result[index] = " "
            index += 1
            continue
        elif state == "block-comment":
            if current == "*" and following == "/":
                result[index] = result[index + 1] = " "
                index += 2
                state = "code"
                continue
            if current != "\n":
                result[index] = " "
            index += 1
            continue
        else:
            result[index] = " "
            if current == "\\" and following:
                if following != "\n":
                    result[index + 1] = " "
                index += 2
                continue
            if current == quote:
                state = "code"
            index += 1
            continue
        index += 1
    return "".join(result)


def _matching_delimiter(
    source: str, start: int, opening: str, closing: str
) -> int:
    depth = 0
    for index in range(start, len(source)):
        if source[index] == opening:
            depth += 1
        elif source[index] == closing:
            depth -= 1
            if depth == 0:
                return index
    return -1


def _c_function_body(source: str, name: str) -> str:
    """Return the last complete C definition, never a call or declaration."""
    clean = _c_noncode_mask(source)
    result = ""
    for match in re.finditer(rf"\b{re.escape(name)}\s*\(", clean):
        opening = clean.find("(", match.start())
        close = _matching_delimiter(clean, opening, "(", ")")
        if close < 0:
            continue
        cursor = close + 1
        while cursor < len(clean) and clean[cursor].isspace():
            cursor += 1
        if cursor >= len(clean) or clean[cursor] != "{":
            continue
        end = _matching_delimiter(clean, cursor, "{", "}")
        if end >= 0:
            result = source[match.start() : end + 1]
    return result


def _norm(address: int) -> int:
    return address & ~1


def _read_at(images: Mapping[str, bytes], specs: Mapping[str, ModuleSpec], module: str, address: int, size: int) -> bytes | None:
    image = images.get(module)
    spec = specs.get(module)
    if image is None or spec is None:
        return None
    offset = address - spec.base
    if offset < 0 or offset + size > len(image):
        return None
    return image[offset : offset + size]


def _symbol_by_name(symbols: Sequence[Symbol], module: str, name: str) -> Symbol | None:
    return next((item for item in symbols if item.module == module and item.stable_name == name), None)


def _function_at(symbols: Sequence[Symbol], module: str, address: int) -> Symbol | None:
    target = _norm(address)
    return next((item for item in symbols if item.module == module and item.kind in "Tt" and _norm(item.address) == target), None)


def _decode_thumb_bl(address: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    if encoded & (1 << 22):
        encoded -= 1 << 23
    return _norm(address + 4 + encoded)


def _references_to_range(image: bytes, base: int, module_symbols: Sequence[Symbol], start: int, end: int) -> list[dict]:
    references: list[dict] = []
    seen: set[tuple[str, int, int]] = set()
    for offset in range(0, len(image) - 3, 4):
        target = _norm(struct.unpack_from("<I", image, offset)[0])
        if start <= target < end:
            key = ("literal", base + offset, target)
            if key not in seen:
                references.append({"kind": "literal", "address": base + offset, "target": target})
                seen.add(key)
    for symbol in module_symbols:
        if symbol.kind not in "Tt" or symbol.size < 4:
            continue
        begin = max(0, _norm(symbol.address) - base)
        finish = min(len(image), begin + symbol.size)
        for offset in range(begin, finish - 3, 2):
            first, second = struct.unpack_from("<HH", image, offset)
            target = _decode_thumb_bl(base + offset, first, second)
            if target is None or not (start <= target < end):
                continue
            key = ("thumb-branch", base + offset, target)
            if key not in seen:
                references.append({"kind": "thumb-branch", "address": base + offset, "target": target})
                seen.add(key)
    return references


def audit_structure(
    symbols: Iterable[Symbol],
    linked_images: Mapping[str, bytes],
    module_specs: Sequence[ModuleSpec] = MODULES,
    private_client_sources: Mapping[str, str] | None = None,
) -> dict:
    inventory = list(symbols)
    specs = {spec.key: spec for spec in module_specs}
    names = ("linked-client-coverage", "facade", "motion", "population", "movement-policy", "walk-owner", "state-encapsulation", "legacy-callbacks", "retired-entry-slots")
    grouped: dict[str, list[dict]] = {name: [] for name in names}
    checked: set[tuple[str, str]] = set()

    def issue(capability: str, kind: str, message: str, **fields: object) -> None:
        grouped[capability].append({"kind": kind, "message": message, **fields})

    def header(capability: str, module: str, address: int, magic: int, version: int, size: int, label: str) -> bytes | None:
        raw = _read_at(linked_images, specs, module, address, size)
        if raw is None:
            issue(capability, "missing-fixed-entry", f"{label} is not present at 0x{address:08X}", module=module, address=address)
            return None
        actual = struct.unpack_from("<IHH", raw)
        if actual != (magic, version, size):
            issue(capability, "wrong-entry-shape", f"{label} has magic/version/size 0x{actual[0]:08X}/{actual[1]}/{actual[2]}; expected 0x{magic:08X}/{version}/{size}", module=module, address=address)
        return raw

    def named_pointer(capability: str, entry: bytes | None, offset: int, module: str, name: str, label: str) -> int | None:
        expected = _symbol_by_name(inventory, module, name)
        if expected is None:
            issue(capability, "missing-target-owner", f"{module} does not define {name}", module=module, symbol=name)
            return None
        checked.add((module, expected.name))
        if entry is None or offset + 4 > len(entry):
            return _norm(expected.address)
        actual = struct.unpack_from("<I", entry, offset)[0]
        if _norm(actual) != _norm(expected.address):
            issue(capability, "wrong-entry-pointer", f"{label} points to 0x{actual:08X}; expected {module}:{name} at 0x{expected.address:08X}", module=module, symbol=name, pointer=actual)
        return _norm(actual)

    for spec in module_specs:
        image = linked_images.get(spec.key)
        if image is None or len(image) == 0:
            issue(
                "linked-client-coverage",
                "missing-linked-client",
                f"{spec.key} linked image is missing from the ownership scan",
                module=spec.key,
            )

    facade = header("facade", "actor_system", ACTOR_FACADE_ENTRY, 0x5341574F, 2, 24, "actor facade entry")
    for offset, name in ((8, "OverworldActorSystem_ValidateImpl"), (12, "OverworldActorSystem_ApplyImpl"), (16, "OverworldActorSystem_TickImpl"), (20, "OverworldActorSystem_InspectImpl")):
        named_pointer("facade", facade, offset, "actor_system", name, name)
    compat = header("facade", "actor_system", ACTOR_COMPAT_ENTRY, 0x4341574F, 3, 32, "actor compatibility entry")
    for offset, name in ((8, "OverworldActorSystem_CompatibilityBindImpl"), (16, "OverworldActorSystem_CompatibilityUnbindImpl"), (20, "OverworldActorSystem_CompatibilityTransitionImpl"), (24, "OverworldActorSystem_CompatibilityRecordTraceImpl"), (28, "OverworldActorSystem_CompatibilityGetContextImpl")):
        named_pointer("facade", compat, offset, "actor_system", name, name)
    if compat is not None and struct.unpack_from("<I", compat, 12)[0] != 0:
        issue(
            "facade",
            "retired-compatibility-update-pointer",
            "actor compatibility entry still exports its retired update callback",
            module="actor_system",
            address=ACTOR_COMPAT_ENTRY + 12,
        )
    retired_update = _symbol_by_name(
        inventory, "actor_system", "OverworldActorSystem_CompatibilityUpdateImpl"
    )
    if retired_update is not None:
        issue(
            "facade",
            "retired-compatibility-update-symbol",
            "actor system still links its retired compatibility update body",
            module="actor_system",
            address=retired_update.address,
        )

    debug = header("state-encapsulation", "actor_system", ACTOR_DEBUG_ENTRY, 0x4C44574F, 1, 64, "actor debug layout")
    state_start = state_end = 0
    if debug is not None:
        overlay_base, overlay_end, state_start = struct.unpack_from("<III", debug, 8)
        state_size = struct.unpack_from("<H", debug, 42)[0]
        state_end = state_start + state_size
        if overlay_base != ACTOR_BASE or overlay_end != ACTOR_END or state_size == 0 or not (ACTOR_BASE <= state_start < state_end <= ACTOR_END):
            issue("state-encapsulation", "invalid-private-state-range", "debug layout does not describe one bounded actor-owned private state range", module="actor_system", stateStart=state_start, stateEnd=state_end)

    motion = header("motion", "actor_system", ACTOR_MOTION_ENTRY, 0x534D574F, 6, 16, "motion service entry")
    motion_targets = [item for item in (
        named_pointer("motion", motion, 8, "actor_system", "ActorSystem_RequestMotion", "motion request"),
        named_pointer("motion", motion, 12, "actor_system", "ActorSystem_EngineBoundary", "motion boundary"),
    ) if item is not None]
    population = header("population", "actor_system", ACTOR_POPULATION_ENTRY, 0x5450574F, 3, 16, "population service entry")
    population_targets = [item for item in (
        named_pointer("population", population, 8, "actor_system", "OverworldActorSystem_PopulationFrameImpl", "population frame"),
        named_pointer("population", population, 12, "actor_system", "OverworldActorSystem_PopulationControlImpl", "population control"),
    ) if item is not None]

    movement = header("movement-policy", "actor_system", ACTOR_MOVEMENT_POLICY_ENTRY, 0x504D574F, 5, 16, "movement-policy service entry")
    policy_address = named_pointer("movement-policy", movement, 8, "actor_system", "sActorMovementPolicy", "movement-policy table")
    adapter_address = named_pointer(
        "movement-policy",
        movement,
        12,
        "actor_system",
        "gOverworldBehaviorConditionAdapterEntry",
        "condition-adapter table",
    )
    policy = _read_at(linked_images, specs, "actor_system", policy_address, 24) if policy_address is not None else None
    if policy is None:
        issue("movement-policy", "invalid-policy-table", "movement-policy table is outside the actor overlay", module="actor_system", address=policy_address)
    policy_targets: list[int] = []
    for offset, name in ((0, "ActorSystem_BuildLookPlan"), (4, "ActorSystem_ResolveLook"), (8, "ActorSystem_ChooseWanderDirection"), (12, "ActorSystem_ReduceWalk"), (16, "ActorSystem_TerminalWalkBoundary"), (20, "ActorSystem_FinishMountedWalk")):
        target = named_pointer("movement-policy", policy, offset, "actor_system", name, name)
        if target is not None:
            policy_targets.append(target)
    adapter = (
        header(
            "movement-policy",
            "actor_system",
            adapter_address,
            0x4143574F,
            6,
            28,
            "condition-adapter table",
        )
        if adapter_address is not None
        else None
    )
    adapter_targets: list[int] = []
    for offset, name in (
        (8, "OverworldBehaviorConditionAdapter_PrepareActor"),
        (12, "OverworldBehaviorConditionAdapter_ClearActor"),
        (16, "OverworldBehaviorConditionAdapter_ClearAll"),
        (20, "OverworldBehaviorConditionAdapter_ClearResolution"),
        (24, "OverworldBehaviorConditionAdapter_EvaluateActor"),
    ):
        target = named_pointer(
            "movement-policy", adapter, offset, "actor_system", name, name)
        if target is not None:
            adapter_targets.append(target)

    runtime = header("walk-owner", "wild_runtime", WILD_RUNTIME_ENTRY, 0x3152574F, 17, 52, "wild runtime adapter entry")
    owner = header("walk-owner", "wild_runtime", WALK_OWNER_ENTRY, 0x5057574F, 1, 12, "Walk policy owner entry")
    walk_target: int | None = None
    if owner is not None:
        raw_target = struct.unpack_from("<I", owner, 8)[0]
        walk_target = _norm(raw_target)
        owner_symbol = _function_at(inventory, "wild_runtime", raw_target)
        runtime_spec = specs.get("wild_runtime")
        runtime_image = linked_images.get("wild_runtime", b"")
        if raw_target & 1 == 0 or runtime_spec is None or not (runtime_spec.base <= walk_target < runtime_spec.base + len(runtime_image)) or owner_symbol is None:
            issue("walk-owner", "invalid-walk-owner-pointer", "Walk owner reducer is not a packaged Thumb function in overlay 156", module="wild_runtime", pointer=raw_target)
        else:
            checked.add(("wild_runtime", owner_symbol.name))

    if runtime is not None:
        for offset, label in (
            (WILD_RUNTIME_POPULATION_CALLBACK_OFFSET, "populationControl"),
            (WILD_RUNTIME_ACKNOWLEDGE_CALLBACK_OFFSET, "acknowledgeMotion"),
        ):
            pointer = struct.unpack_from("<I", runtime, offset)[0]
            if pointer != 0:
                issue(
                    "legacy-callbacks",
                    "retired-runtime-callback",
                    f"wild runtime still exports retired {label} callback at byte offset {offset}",
                    module="wild_runtime",
                    address=WILD_RUNTIME_ENTRY + offset,
                    pointer=pointer,
                )
    runtime_image = linked_images.get("wild_runtime", b"")
    if LEGACY_POPULATION_THUNK in runtime_image:
        issue(
            "legacy-callbacks",
            "retired-population-thunk-body",
            "wild runtime still contains the retired population tail thunk",
            module="wild_runtime",
        )
    for symbol_name in (
        "OverworldWildRuntime_PopulationControl",
        "OverworldWildRuntime_AcknowledgeMotion",
    ):
        symbol = _symbol_by_name(inventory, "wild_runtime", symbol_name)
        if symbol is not None:
            issue(
                "legacy-callbacks",
                "retired-runtime-callback-symbol",
                f"wild runtime still links retired callback body {symbol_name}",
                module="wild_runtime",
                address=symbol.address,
                symbol=symbol_name,
            )

    by_module = {module: [item for item in inventory if item.module == module] for module in specs}
    receipt = _symbol_by_name(inventory, "wild_runtime", "OverworldWildSpawns_AcknowledgeSharedMotion")
    for name, start, end, expected in (
        ("OverworldWildRuntime_ApplyMotionBoundary", MOTION_BOUNDARY_BRIDGE,
         MOTION_BOUNDARY_BRIDGE_END, {"mount": 1, "wild_runtime": 1}),
        ("OverworldWildSpawns_AcknowledgeSharedMotion", WILD_MOTION_RECEIPT,
         WILD_MOTION_RECEIPT_END, {"wild_spawns": 11}),
    ):
        entry = _symbol_by_name(inventory, "wild_runtime", name)
        if entry is None or _norm(entry.address) != start or not 0 < entry.size <= end - start:
            issue("motion", "invalid-motion-boundary-bridge",
                  f"{name} is missing or outside its split fixed reserve",
                  module="wild_runtime", address=start)
        else:
            checked.add(("wild_runtime", entry.name))
        for module, spec in specs.items():
            references = _references_to_range(
                linked_images.get(module, b""), spec.base,
                by_module.get(module, ()), start, start + 1)
            count = expected.get(module, 0)
            if count and len(references) != count:
                issue("motion", "invalid-motion-boundary-client",
                      f"{module} must contain exactly {count} references to {name}",
                      module=module, pointer=start, referenceCount=len(references))
            elif not count and references:
                issue("motion", "unexpected-motion-boundary-client",
                      f"{module} bypasses its adapter and calls {name}",
                      module=module, pointer=start)
            if module == "wild_runtime" and start == MOTION_BOUNDARY_BRIDGE:
                if any(receipt is None or not (
                        WILD_MOTION_RECEIPT <= ref["address"]
                        < WILD_MOTION_RECEIPT + receipt.size) for ref in references):
                    issue("motion", "unexpected-motion-boundary-client",
                          "only the Wild capture adapter may call the shared bridge from wild_runtime",
                          module=module, pointer=start)
    hop_planner = _symbol_by_name(
        inventory, "role_controller", "OverworldActorHopPlanner_Plan"
    )
    if hop_planner is None or _norm(hop_planner.address) != 0x023BD4F0 or hop_planner.size != 8:
        issue(
            "motion",
            "invalid-hop-planner-entry",
            "Actor Motion Hop planner is not the exact 8-byte task-6 trampoline at 0x023BD4F0",
            module="role_controller",
        )
    else:
        checked.add(("role_controller", hop_planner.name))
        for module in MOTION_PLANNER_CLIENTS:
            if module not in linked_images or module not in specs:
                continue
            for reference in _references_to_range(
                linked_images[module],
                specs[module].base,
                by_module.get(module, ()),
                hop_planner.address,
                hop_planner.address + 1,
            ):
                issue(
                    "motion",
                    "direct-hop-planner-reference",
                    f"{module} bypasses the Actor Motion request seam for Hop planning",
                    module=module,
                    address=reference["address"],
                    pointer=hop_planner.address,
                    referenceKind=reference["kind"],
                )
    teleport_planner = _symbol_by_name(
        inventory, "role_controller", "OverworldActorTeleportPlanner_Plan"
    )
    if (
        teleport_planner is None
        or _norm(teleport_planner.address) != 0x023BD4F8
        or teleport_planner.size != 8
    ):
        issue(
            "motion",
            "invalid-teleport-planner-entry",
            "Actor Motion Teleport planner is not the exact 8-byte task-6 trampoline at 0x023BD4F8",
            module="role_controller",
        )
    else:
        checked.add(("role_controller", teleport_planner.name))
        for module in MOTION_PLANNER_CLIENTS:
            if module not in linked_images or module not in specs:
                continue
            for reference in _references_to_range(
                linked_images[module],
                specs[module].base,
                by_module.get(module, ()),
                teleport_planner.address,
                teleport_planner.address + 1,
            ):
                issue(
                    "motion",
                    "direct-teleport-planner-reference",
                    f"{module} bypasses the Actor Motion request seam for Teleport planning",
                    module=module,
                    address=reference["address"],
                    pointer=teleport_planner.address,
                    referenceKind=reference["kind"],
                )
    owner_ranges = (
        ("motion", "actor_system", motion_targets),
        ("population", "actor_system", population_targets),
        ("movement-policy", "actor_system", policy_targets + adapter_targets),
        ("walk-owner", "wild_runtime", [] if walk_target is None else [walk_target]),
    )
    for capability, owner_module, targets in owner_ranges:
        for target in targets:
            for module, image in linked_images.items():
                if module == owner_module or module not in specs:
                    continue
                for reference in _references_to_range(image, specs[module].base, by_module.get(module, ()), target, target + 1):
                    issue(capability, "direct-owner-body-reference", f"{module} directly references owner body 0x{target:08X}; it must use the fixed service entry", module=module, address=reference["address"], pointer=target, referenceKind=reference["kind"])

    if state_start and state_end > state_start:
        for module, image in linked_images.items():
            if module == "actor_system" or module not in specs:
                continue
            for reference in _references_to_range(image, specs[module].base, by_module.get(module, ()), state_start, state_end):
                issue("state-encapsulation", "direct-private-state-reference", f"{module} directly references actor private state 0x{reference['target']:08X}", module=module, address=reference["address"], pointer=reference["target"], referenceKind=reference["kind"])

    wild_state = _symbol_by_name(
        inventory, "wild_spawns", "sOverworldWildSpawnState"
    )
    if wild_state is not None:
        if wild_state.kind.isupper():
            issue(
                "state-encapsulation",
                "exported-wild-private-state",
                "wild spawns still exports its private parallel-array state",
                module="wild_spawns",
                address=wild_state.address,
            )
        if wild_state.size > 0:
            for module, image in linked_images.items():
                if module == "wild_spawns" or module not in specs:
                    continue
                for reference in _references_to_range(
                    image,
                    specs[module].base,
                    by_module.get(module, ()),
                    wild_state.address,
                    wild_state.address + wild_state.size,
                ):
                    issue(
                        "state-encapsulation",
                        "direct-wild-private-state-reference",
                        f"{module} directly references wild private state 0x{reference['target']:08X}",
                        module=module,
                        address=reference["address"],
                        pointer=reference["target"],
                        referenceKind=reference["kind"],
                    )

    if private_client_sources is not None:
        for module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS:
            source = private_client_sources.get(path)
            if source is None:
                issue(
                    "state-encapsulation",
                    "missing-private-client-source",
                    f"private-state client source is missing: {path}",
                    module=module,
                    source=path,
                )
            if module == "walk_shadow_asm" and source is not None \
                    and "bl OverworldWalk_CopyNativeShadowValue" not in source:
                issue(
                    "state-encapsulation",
                    "native-shadow-value-service-bypassed",
                    "native-shadow ASM does not use the typed value service",
                    module=module,
                    source=path,
                )
            if module == "walk_shadow_asm" and source is not None \
                    and "strh r2, [r4, #0xC]" not in source:
                issue(
                    "state-encapsulation",
                    "native-shadow-generation-storage-overwritten",
                    "native-shadow visibility updates do not preserve the encounter token",
                    module=module,
                    source=path,
                )
            if module == "walk_module" and source is not None:
                if not re.search(
                    r"IsOverlayLoaded\s*\(\s*"
                    r"OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION\s*\)",
                    source,
                ):
                    issue(
                        "state-encapsulation",
                        "native-shadow-service-overlay-unchecked",
                        "native-shadow client does not reject an unloaded Wild overlay",
                        module=module,
                        source=path,
                    )
                if (
                    "target != "
                    "(OVERWORLD_WILD_SPAWNS_COPY_NATIVE_SHADOW_VALUE_ADDR | 1u)"
                    not in source
                ):
                    issue(
                        "state-encapsulation",
                        "native-shadow-service-target-not-exact",
                        "native-shadow client does not require the exact Wild value callback",
                        module=module,
                        source=path,
                    )
            if source is not None \
                    and re.search(r"\bsOverworldWildSpawnState\b", source):
                issue(
                    "state-encapsulation",
                    "direct-wild-private-state-source-reference",
                    f"{path} names the private Wild spawn state directly",
                    module=module,
                    source=path,
                )
        owner_source = private_client_sources.get(
            WILD_NATIVE_SHADOW_OWNER_SOURCE
        )
        if owner_source is None:
            issue(
                "state-encapsulation",
                "missing-native-shadow-owner-source",
                "Wild native-shadow value-service source is missing",
                module="wild_spawns",
                source=WILD_NATIVE_SHADOW_OWNER_SOURCE,
            )
        else:
            owner_body = _c_function_body(
                owner_source,
                "OverworldWildSpawns_CopyNativeShadowValue",
            )
            owner_requirements = (
                (
                    "value->encounterGeneration != spawn->encounterGeneration",
                    "native-shadow-encounter-generation-unchecked",
                    "Wild native-shadow value service does not reject a recycled encounter",
                ),
                (
                    "spawn->object != object",
                    "native-shadow-object-identity-unchecked",
                    "Wild native-shadow value service does not bind the request to the live object",
                ),
                (
                    "GetMapObjectByID(fieldSystem->mapObjectMan, spawn->objectId)",
                    "native-shadow-manager-identity-unchecked",
                    "Wild native-shadow value service does not bind the object to the current manager",
                ),
                (
                    "OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(",
                    "native-shadow-map-generation-unchecked",
                    "Wild native-shadow value service does not reject a stale map generation",
                ),
            )
            for needle, kind, message in owner_requirements:
                if needle not in owner_body:
                    issue(
                        "state-encapsulation",
                        kind,
                        message,
                        module="wild_spawns",
                        source=WILD_NATIVE_SHADOW_OWNER_SOURCE,
                    )
        stock_patch = private_client_sources.get(
            NATIVE_SHADOW_STOCK_PATCH_SOURCE
        )
        if stock_patch is None:
            issue(
                "state-encapsulation",
                "missing-native-shadow-stock-patch",
                "native-shadow stock task patch source is missing",
                module="walk_shadow_asm",
                source=NATIVE_SHADOW_STOCK_PATCH_SOURCE,
            )
        else:
            hidden_read_requirements = (
                (".org 0x021FD7DC", 1),
                (".org 0x021FD840", 1),
                (".org 0x021FD986", 1),
                ("ldrh r0, [r2, 0xC]", 2),
                ("ldrh r1, [r4, 0xC]", 1),
            )
            for instruction, count in hidden_read_requirements:
                if stock_patch.count(instruction) != count:
                    issue(
                        "state-encapsulation",
                        "native-shadow-hidden-state-read-too-wide",
                        "native-shadow draw callbacks read the encounter token as hidden state",
                        module="walk_shadow_asm",
                        source=NATIVE_SHADOW_STOCK_PATCH_SOURCE,
                    )
                    break

        actor_source = private_client_sources.get(ACTOR_SYSTEM_OWNER_SOURCE)
        if actor_source is None:
            issue(
                "state-encapsulation",
                "missing-actor-owner-source",
                "Actor owner source is missing from the private-state audit",
                module="actor_system",
                source=ACTOR_SYSTEM_OWNER_SOURCE,
            )
        else:
            for marker, kind, message in (
                (
                    "gOverworldWildFieldIdleRearmPending",
                    "direct-wild-resident-flag-source-reference",
                    "Actor owner reads or writes the Wild-owned resident rearm flag",
                ),
                (
                    "OverworldWildSpawnState",
                    "direct-wild-state-type-source-reference",
                    "Actor owner exposes the Wild private state type",
                ),
                (
                    '#include "../../include/overworld_wild_spawns_internal.h"',
                    "direct-wild-internal-header-source-reference",
                    "Actor owner includes the Wild private state header",
                ),
            ):
                if marker in actor_source:
                    issue(
                        "state-encapsulation",
                        kind,
                        message,
                        module="actor_system",
                        source=ACTOR_SYSTEM_OWNER_SOURCE,
                    )
            for function_name in (
                "ActorSystem_SyncLegacyActor",
                "OverworldActorSystem_PopulationFrameImpl",
            ):
                body = _c_function_body(actor_source, function_name)
                if not body:
                    issue(
                        "state-encapsulation",
                        "missing-actor-adapter-function",
                        f"Actor private-state audit cannot find {function_name}",
                        module="actor_system",
                        source=ACTOR_SYSTEM_OWNER_SOURCE,
                        function=function_name,
                    )
                    continue
                for marker, kind in (
                    ("state->spawns", "direct-wild-spawn-state-source-reference"),
                    ("state->mapGeneration", "direct-wild-map-generation-source-reference"),
                    ("state->movementRuntimeState", "direct-wild-runtime-state-source-reference"),
                ):
                    if marker in body:
                        issue(
                            "state-encapsulation",
                            kind,
                            f"{function_name} reads Wild-owned private state through {marker}",
                            module="actor_system",
                            source=ACTOR_SYSTEM_OWNER_SOURCE,
                            function=function_name,
                        )

        mount_source = private_client_sources.get(MOUNT_STREAM_CLIENT_SOURCE)
        if mount_source is None:
            issue(
                "state-encapsulation",
                "missing-mount-stream-client-source",
                "Mount terrain-stream client source is missing from the ownership audit",
                module="mount",
                source=MOUNT_STREAM_CLIENT_SOURCE,
            )
        else:
            if "gOverworldWildFieldIdleRearmPending" in mount_source:
                issue(
                    "state-encapsulation",
                    "mount-wild-resident-flag-source-reference",
                    "Mount reads or writes the Wild-owned resident rearm flag",
                    module="mount",
                    source=MOUNT_STREAM_CLIENT_SOURCE,
                )
            for marker in (
                "OverworldMount_GetLandDataManager",
                "ov01_021F62E8",
                "+ 0xA0",
                "+ 0xD0",
                "+ 0xD8",
            ):
                if marker in mount_source:
                    issue(
                        "state-encapsulation",
                        "mount-private-terrain-stream-source-reference",
                        f"Mount owns private terrain-stream mechanics through {marker}",
                        module="mount",
                        source=MOUNT_STREAM_CLIENT_SOURCE,
                    )

    for retired in RETIRED_ENTRIES:
        raw = _read_at(linked_images, specs, retired.module, retired.address, retired.size)
        pointers: list[int] = []
        if raw is not None:
            sentinel_fill = (
                retired.module == "wild_behavior_data"
                and retired.address == 0x023C3F18
                and raw == b"\xAB\xCD" * (len(raw) // 2)
            )
            if raw != bytes(len(raw)) and not sentinel_fill:
                issue("retired-entry-slots", "retired-entry-not-empty", f"retired {retired.label} slot at 0x{retired.address:08X} is neither zero nor linker sentinel fill", module=retired.module, address=retired.address, retiredCapability=retired.capability)
            for offset in range(0, len(raw) - 3, 4):
                value = struct.unpack_from("<I", raw, offset)[0]
                if any(_function_at(inventory, module, value) is not None for module in specs):
                    pointers.append(value)
        if pointers:
            issue("retired-entry-slots", "retired-entry-shape", f"retired {retired.label} slot at 0x{retired.address:08X} still contains function pointers", module=retired.module, address=retired.address, retiredCapability=retired.capability, pointers=pointers)
        for module, image in linked_images.items():
            if module not in specs:
                continue
            for reference in _references_to_range(image, specs[module].base, by_module.get(module, ()), retired.address, retired.address + 1):
                issue("retired-entry-slots", "retired-entry-reference", f"{module} still references retired {retired.label} slot 0x{retired.address:08X}", module=module, address=reference["address"], pointer=retired.address, retiredCapability=retired.capability, referenceKind=reference["kind"])

    capabilities = [{"capability": name, "passed": not grouped[name], "issues": grouped[name]} for name in names]
    all_issues = [{"capability": name, **entry} for name in names for entry in grouped[name]]
    return {
        "passed": not all_issues,
        "capabilities": capabilities,
        "issues": all_issues,
        "checkedSymbols": [{"module": module, "symbol": name} for module, name in sorted(checked)],
    }


def checked_slice(data: bytes, offset: int, size: int, label: str) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError(f"{label} is outside the ROM")
    return data[offset : offset + size]


def extract_packaged_overlays(rom: bytes) -> dict[int, tuple[int, bytes]]:
    if len(rom) < ROM_HEADER_Y9_OFFSET + 8:
        raise ValueError("ROM header is truncated")
    fat_offset, fat_size = struct.unpack_from("<II", rom, ROM_HEADER_FAT_OFFSET)
    y9_offset, y9_size = struct.unpack_from("<II", rom, ROM_HEADER_Y9_OFFSET)
    if y9_size == 0 or y9_size % OVERLAY_ROW_SIZE != 0:
        raise ValueError("ARM9 overlay table has an invalid size")
    fat = checked_slice(rom, fat_offset, fat_size, "FAT")
    table = checked_slice(rom, y9_offset, y9_size, "ARM9 overlay table")
    overlays: dict[int, tuple[int, bytes]] = {}
    for offset in range(0, len(table), OVERLAY_ROW_SIZE):
        row = struct.unpack_from("<8I", table, offset)
        overlay_id, load_address, file_id = row[0], row[1], row[6]
        if overlay_id in overlays:
            raise ValueError(f"duplicate overlay ID {overlay_id}")
        fat_entry = file_id * 8
        if fat_entry + 8 > len(fat):
            raise ValueError(f"overlay {overlay_id} has no FAT entry {file_id}")
        file_start, file_end = struct.unpack_from("<II", fat, fat_entry)
        if file_start >= file_end:
            raise ValueError(f"overlay {overlay_id} has an empty FAT entry")
        overlays[overlay_id] = (load_address, checked_slice(rom, file_start, file_end - file_start, f"overlay {overlay_id}"))
    return overlays


def audit_packaging(rom: bytes, module_specs: Sequence[ModuleSpec], linked_images: Mapping[str, bytes], output_images: Mapping[str, bytes], checked_symbols: Iterable[Symbol]) -> dict:
    try:
        packaged = extract_packaged_overlays(rom)
    except ValueError as error:
        return {"passed": False, "modules": [], "issues": [{"kind": "invalid-rom", "message": str(error)}]}
    symbols_by_module: dict[str, list[Symbol]] = {}
    for symbol in checked_symbols:
        symbols_by_module.setdefault(symbol.module, []).append(symbol)
    issues: list[dict] = []
    module_results: list[dict] = []
    for spec in module_specs:
        found: list[dict] = []
        linked = linked_images.get(spec.key)
        output = output_images.get(spec.key)
        packaged_entry = packaged.get(spec.overlay_id)
        if linked is None:
            found.append({"kind": "missing-linked-image", "message": "linked image is missing"})
        if output is None:
            found.append({"kind": "missing-output-image", "message": "output image is missing"})
        if packaged_entry is None:
            found.append({"kind": "missing-packaged-overlay", "message": f"ROM has no overlay {spec.overlay_id}"})
        if linked is not None and output is not None and linked != output:
            found.append({"kind": "linked-output-mismatch", "message": "linked ELF image differs from the build output"})
        if output is not None and packaged_entry is not None:
            load_address, packaged_image = packaged_entry
            if spec.package_base is None:
                if output != packaged_image:
                    found.append({
                        "kind": "output-rom-mismatch",
                        "message": (
                            f"build output differs from packaged overlay "
                            f"{spec.overlay_id}"
                        ),
                    })
            else:
                package_offset = spec.base - load_address
                if package_offset < 0 or package_offset + len(output) > len(packaged_image):
                    found.append({
                        "kind": "package-slice-outside-overlay",
                        "message": (
                            f"module range 0x{spec.base:08X}.."
                            f"0x{spec.base + len(output):08X} is outside packaged "
                            f"overlay {spec.overlay_id}"
                        ),
                    })
                elif output != packaged_image[
                    package_offset : package_offset + len(output)
                ]:
                    found.append({
                        "kind": "output-rom-mismatch",
                        "message": (
                            f"build output differs from packaged overlay "
                            f"{spec.overlay_id} at 0x{spec.base:08X}"
                        ),
                    })
        if linked is not None and packaged_entry is not None:
            load_address, packaged_image = packaged_entry
            if load_address != spec.expected_package_base:
                found.append({"kind": "wrong-overlay-load-address", "message": f"overlay {spec.overlay_id} loads at 0x{load_address:08X}; expected 0x{spec.expected_package_base:08X}"})
            for symbol in symbols_by_module.get(spec.key, ()):
                if symbol.kind not in PACKAGED_TYPES:
                    continue
                start = _norm(symbol.address) - spec.base
                if linked is None or start < 0 or start + max(symbol.size, 1) > len(linked):
                    found.append({"kind": "symbol-outside-package", "symbol": symbol.name, "message": f"linked symbol {symbol.name} is outside module {spec.key} in overlay {spec.overlay_id}"})
        module_results.append({"module": spec.key, "overlayId": spec.overlay_id, "passed": not found, "issues": found})
        issues.extend({"module": spec.key, **entry} for entry in found)
    return {"passed": not issues, "modules": module_results, "issues": issues}


def read_linked_symbols(repo: Path, nm: str) -> list[Symbol]:
    inventory: list[Symbol] = []
    for spec in MODULES:
        path = repo / spec.linked
        if not path.is_file():
            continue
        result = subprocess.run([nm, "-S", "--defined-only", str(path)], check=True, capture_output=True, text=True)
        inventory.extend(parse_nm(result.stdout, spec.key))
    return inventory


def objcopy_image(path: Path, objcopy: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="overworld-owner-image-") as directory:
        output = Path(directory) / "linked.bin"
        subprocess.run([objcopy, "-O", "binary", str(path), str(output)], check=True, capture_output=True)
        return output.read_bytes()


def relevant_symbols(inventory: Iterable[Symbol], structural_result: Mapping[str, object]) -> list[Symbol]:
    keys = {(entry["module"], entry["symbol"]) for entry in structural_result["checkedSymbols"]}  # type: ignore[index]
    return [item for item in inventory if (item.module, item.name) in keys or (item.module, item.stable_name) in keys]


def verify(repo: Path, rom_path: Path | None, nm: str, objcopy: str) -> dict:
    try:
        inventory = read_linked_symbols(repo, nm)
        linked = {
            spec.key: objcopy_image(repo / spec.linked, objcopy)
            for spec in MODULES
            if (repo / spec.linked).is_file()
        }
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        return {"schemaVersion": 2, "passed": False, "ownership": {"passed": False, "capabilities": [], "issues": [{"kind": "linked-inventory-error", "message": str(error)}], "checkedSymbols": []}, "package": {"checked": False, "passed": False, "issues": []}}
    private_client_sources: dict[str, str] = {}
    for _module, relative_path in PRIVATE_WILD_STATE_SOURCE_CLIENTS:
        path = repo / relative_path
        if path.is_file():
            private_client_sources[relative_path] = path.read_text()
    owner_path = repo / WILD_NATIVE_SHADOW_OWNER_SOURCE
    if owner_path.is_file():
        private_client_sources[WILD_NATIVE_SHADOW_OWNER_SOURCE] = (
            owner_path.read_text()
        )
    stock_patch_path = repo / NATIVE_SHADOW_STOCK_PATCH_SOURCE
    if stock_patch_path.is_file():
        private_client_sources[NATIVE_SHADOW_STOCK_PATCH_SOURCE] = (
            stock_patch_path.read_text()
        )
    actor_source_path = repo / ACTOR_SYSTEM_OWNER_SOURCE
    if actor_source_path.is_file():
        private_client_sources[ACTOR_SYSTEM_OWNER_SOURCE] = (
            actor_source_path.read_text()
        )
    mount_source_path = repo / MOUNT_STREAM_CLIENT_SOURCE
    if mount_source_path.is_file():
        private_client_sources[MOUNT_STREAM_CLIENT_SOURCE] = (
            mount_source_path.read_text()
        )
    ownership = audit_structure(
        inventory,
        linked,
        private_client_sources=private_client_sources,
    )
    package: dict = {"checked": False, "passed": True, "modules": [], "issues": []}
    if rom_path is not None:
        try:
            outputs = {spec.key: (repo / spec.output).read_bytes() for spec in MODULES}
            package = {"checked": True, **audit_packaging(rom_path.read_bytes(), MODULES, linked, outputs, relevant_symbols(inventory, ownership))}
        except OSError as error:
            package = {"checked": True, "passed": False, "modules": [], "issues": [{"kind": "package-read-error", "message": str(error)}]}
    return {"schemaVersion": 2, "passed": bool(ownership["passed"] and package["passed"]), "ownership": ownership, "package": package}


def print_text(result: Mapping[str, object]) -> None:
    ownership = result["ownership"]
    for capability in ownership["capabilities"]:  # type: ignore[index]
        print(f"{'PASS' if capability['passed'] else 'FAIL'} {capability['capability']}")
        for entry in capability["issues"]:
            print(f"  - {entry['message']}")
    package = result["package"]
    if package["checked"]:  # type: ignore[index]
        print(f"{'PASS' if package['passed'] else 'FAIL'} linked/package identity")
        for entry in package["issues"]:
            print(f"  - {entry.get('module', 'ROM')}: {entry['message']}")
    else:
        print("SKIP linked/package identity (--rom was not supplied)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify structural deletion of duplicate overworld owners")
    parser.add_argument("--rom", type=Path, help="final ROM to authenticate")
    parser.add_argument("--repo-root", type=Path, default=REPO)
    parser.add_argument("--nm", default=os.environ.get("NM", "arm-none-eabi-nm"))
    parser.add_argument("--objcopy", default=os.environ.get("OBJCOPY", "arm-none-eabi-objcopy"))
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = verify(args.repo_root.resolve(), args.rom, args.nm, args.objcopy)
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else "", end="" if args.json else "")
    if not args.json:
        print_text(result)
    elif args.json:
        print()
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
