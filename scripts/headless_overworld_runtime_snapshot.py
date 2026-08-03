#!/usr/bin/env python3
"""Run bounded overworld scenarios and snapshot the live profile stack.

The wrapper delegates emulation to ``headless-overworld-test.py``. It resolves
the resident state and heap symbols from the exact linked components packaged
in the ROM, then performs one bounded key-only scenario with pointer-relative,
read-only stack, timer, possession, and heap observations. Source ``test.dsv``
and the ROM must retain their exact hashes throughout the run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
HEADLESS = ROOT / "scripts/headless-overworld-test.py"
LINKED = ROOT / "build/linked.o"
SPAWNS_LINKED = ROOT / "build/overworld_wild_spawns_overlay_linked.o"
BUILT_ARM9 = ROOT / "build/arm9.bin"

MAX_SLOTS = 10
MAX_LAYERS = 8
STATE_SIZE = 0x458
STATE_RUNTIME_POINTER_OFFSET = 0xE4

# Frozen by compile-time size assertions in overworld_wild_runtime_sidecars.h
# and the resident-suffix assertion in the live overlay.
LIVE_STACK_OFFSET = 2056
STACK_HEADER_SIZE = 12
SLOT_SIZE = 1724
SLOT_LAYER_BANK_OFFSET = 36
SLOT_TIMER_BANK_OFFSET = 148
SLOT_EFFECTIVE_CACHE_OFFSET = 892
EFFECTIVE_ROLE_OFFSET = 58
LAYER_BANK_SIZE = 112
TIMER_BANK_SIZE = 192
PICKUP_RELATIONS_OFFSET = 1096
PICKUP_RELATION_SIZE = 44
STATE_MAP_ID_OFFSET = 212
STATE_MOVEMENT_IN_PROGRESS_OFFSET = 248
STATE_ACTIVE_STEPS_OFFSET = 354
STATE_MAP_GENERATION_OFFSET = 1096
LIVE_PRESENTATION_POSITIONS_OFFSET = 486
LIVE_MOVEMENT_OBJECT_GENERATIONS_OFFSET = 1056
TIMER_VALID = 1 << 0


@dataclass(frozen=True)
class Scenario:
    name: str
    frame_budget: int
    actions: tuple[str, ...]
    purpose: str


def _walk_cycle(frames: int = 150, sample_frames: int = 180) -> tuple[str, ...]:
    return tuple(
        f"combo_sample:{direction}:{frames}:{sample_frames}:30"
        for direction in ("LEFT", "DOWN", "RIGHT", "UP")
    )


SCENARIOS = {
    "spawn-freeze": Scenario(
        "spawn-freeze",
        5400,
        _walk_cycle() * 7,
        "Repeatedly cross spawn/despawn ranges and prove continued frame progress.",
    ),
    "alert-aggro-tired-recovery": Scenario(
        "alert-aggro-tired-recovery",
        4200,
        _walk_cycle(120, 180) * 4 + ("sample:720:30",),
        "Exercise nearby behavior transitions and observe role/layer/timer health.",
    ),
    "pickup-throw": Scenario(
        "pickup-throw",
        3000,
        _walk_cycle(90, 150) * 3
        + ("tap:A:18:30", "sample:720:30"),
        "Exercise pickup/throw-capable actors while observing possession tuples.",
    ),
    "lifecycle": Scenario(
        "lifecycle",
        3000,
        _walk_cycle(90, 150) * 3
        + ("tap:A:18:30", "sample:720:30"),
        "Exercise ordinary map/battle handoff opportunities and retained state.",
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_dsv(explicit: Path | None) -> Path:
    if explicit is not None:
        path = explicit if explicit.is_absolute() else ROOT / explicit
        if not path.is_file():
            raise FileNotFoundError(f"DSV not found: {path}")
        return path
    candidates = (
        ROOT / "test.dsv",
        Path.home() / "Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv",
        Path.home() / "Library/Application Support/DeSmuME/0.9.12/Battery/test.dsv",
        ROOT / ".headless_desmume/.config/desmume/test.dsv",
    )
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError("No test.dsv found; pass --dsv PATH")


def resolve_symbols(linked: Path, names: Iterable[str]) -> dict[str, tuple[int, int]]:
    requested = set(names)
    completed = subprocess.run(
        ["arm-none-eabi-nm", "-S", str(linked)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    resolved: dict[str, tuple[int, int]] = {}
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[-1] in requested:
            resolved[parts[-1]] = (int(parts[0], 16), int(parts[1], 16))
        elif len(parts) == 3 and parts[-1] in requested:
            resolved[parts[-1]] = (int(parts[0], 16), 0)
    missing = sorted(requested - resolved.keys())
    if missing:
        raise ValueError("linked object is missing symbols: " + ", ".join(missing))
    return resolved


def elf_binary(linked: Path) -> bytes:
    """Return the exact allocated ELF image emitted by the build linker."""

    with tempfile.TemporaryDirectory(prefix="ow-runtime-identity-") as directory:
        output = Path(directory) / "linked.bin"
        subprocess.run(
            ["arm-none-eabi-objcopy", "-O", "binary", str(linked), str(output)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return output.read_bytes()


def packaged_components(rom: bytes) -> tuple[tuple[int, bytes], dict[int, tuple[tuple[int, ...], bytes]]]:
    """Extract ARM9 and ARM9-overlay members with strict header bounds."""

    if len(rom) < 0x160:
        raise ValueError("ROM header is truncated")
    arm9_offset, _entry, arm9_base, arm9_size = struct.unpack_from("<4I", rom, 0x20)
    fat_offset, fat_size = struct.unpack_from("<2I", rom, 0x48)
    y9_offset, y9_size = struct.unpack_from("<2I", rom, 0x50)
    for offset, size, name in (
        (arm9_offset, arm9_size, "ARM9"),
        (fat_offset, fat_size, "FAT"),
        (y9_offset, y9_size, "y9"),
    ):
        if offset < 0 or size <= 0 or offset + size > len(rom):
            raise ValueError(f"ROM {name} range is invalid")
    if fat_size % 8 or y9_size % 32:
        raise ValueError("ROM FAT/y9 alignment is invalid")
    overlays: dict[int, tuple[tuple[int, ...], bytes]] = {}
    for offset in range(y9_offset, y9_offset + y9_size, 32):
        row = struct.unpack_from("<8I", rom, offset)
        overlay_id, file_id = row[0], row[6]
        if overlay_id in overlays or file_id * 8 + 8 > fat_size:
            raise ValueError("ROM overlay table has duplicate/invalid entries")
        start, end = struct.unpack_from("<2I", rom, fat_offset + file_id * 8)
        if start >= end or end > len(rom):
            raise ValueError(f"ROM overlay {overlay_id} FAT range is invalid")
        overlays[overlay_id] = (row, rom[start:end])
    return (arm9_base, rom[arm9_offset : arm9_offset + arm9_size]), overlays


def verify_component_identity(
    *,
    packaged_arm9: tuple[int, bytes],
    overlays: dict[int, tuple[tuple[int, ...], bytes]],
    built_arm9: bytes,
    linked129_image: bytes,
    linked149_image: bytes,
    linked129_text_start: int,
    linked149_text_start: int,
    state_address: int,
    state_size: int,
) -> dict[str, str]:
    """Cryptographically bind memory-layout inputs to packaged ROM bytes."""

    arm9_base, arm9 = packaged_arm9
    if arm9_base != 0x02000000:
        raise ValueError("packaged ARM9 RAM base differs")
    if not built_arm9.startswith(arm9) or len(built_arm9) - len(arm9) not in range(13):
        raise ValueError("packaged ARM9 differs from current built ARM9")
    if 129 not in overlays or 149 not in overlays:
        raise ValueError("ROM is missing required overworld overlays")
    row129, overlay129 = overlays[129]
    row149, overlay149 = overlays[149]
    base129, memory_size129 = row129[1], row129[2]
    offset129 = linked129_text_start - base129
    if (
        offset129 < 0
        or offset129 + len(linked129_image) > len(overlay129)
        or overlay129[offset129 : offset129 + len(linked129_image)] != linked129_image
    ):
        raise ValueError("ROM overlay 129 differs from current linked resident image")
    if not (base129 <= state_address and state_address + state_size <= base129 + memory_size129):
        raise ValueError("spawn-state symbol lies outside packaged overlay 129")
    if row149[1] != linked149_text_start or overlay149 != linked149_image:
        raise ValueError("ROM overlay 149 differs from current linked spawns image")
    return {
        "packaged_arm9_sha256": hashlib.sha256(arm9).hexdigest(),
        "built_arm9_sha256": hashlib.sha256(built_arm9).hexdigest(),
        "linked_overlay129_sha256": hashlib.sha256(linked129_image).hexdigest(),
        "packaged_overlay129_sha256": hashlib.sha256(overlay129).hexdigest(),
        "linked_overlay149_sha256": hashlib.sha256(linked149_image).hexdigest(),
        "packaged_overlay149_sha256": hashlib.sha256(overlay149).hexdigest(),
    }


def authenticate_rom_build_identity(
    rom: Path,
    linked129: Path,
    linked149: Path,
    built_arm9_path: Path,
    symbols129: dict[str, tuple[int, int]],
    symbols149: dict[str, tuple[int, int]],
) -> dict[str, str]:
    rom_bytes = rom.read_bytes()
    packaged_arm9, overlays = packaged_components(rom_bytes)
    return verify_component_identity(
        packaged_arm9=packaged_arm9,
        overlays=overlays,
        built_arm9=built_arm9_path.read_bytes(),
        linked129_image=elf_binary(linked129),
        linked149_image=elf_binary(linked149),
        linked129_text_start=symbols129["__text_start"][0],
        linked149_text_start=symbols149["__text_start"][0],
        state_address=symbols129["sOverworldWildSpawnState"][0],
        state_size=symbols129["sOverworldWildSpawnState"][1],
    )


def action_frames(action: str) -> int:
    parts = action.split(":")
    command = parts[0]
    try:
        if command == "tap":
            return (int(parts[2], 0) if len(parts) >= 3 else 18) + (
                int(parts[3], 0) if len(parts) >= 4 else 18
            )
        if command in {"hold", "combo"}:
            return int(parts[2], 0) + (
                int(parts[3], 0) if len(parts) >= 4 else 18
            )
        if command == "combo_sample":
            hold_frames = int(parts[2], 0)
            sample_frames = int(parts[3], 0)
            if hold_frames > sample_frames:
                raise ValueError("combo_sample hold exceeds sampled frames")
            return sample_frames
        if command in {"wait", "sample"}:
            return int(parts[1], 0)
        if command == "heap_phase" or command == "screenshot":
            return 0
    except (IndexError, ValueError) as error:
        raise ValueError(f"invalid action {action!r}") from error
    raise ValueError(f"unsupported bounded action {command!r}")


def validate_actions(actions: Iterable[str], budget: int) -> int:
    if budget <= 0 or budget > 7200:
        raise ValueError("frame budget must be in 1..7200")
    total = sum(action_frames(action) for action in actions)
    if total > budget:
        raise ValueError(f"scenario uses {total} frames, exceeding budget {budget}")
    return total


def read_specs(state_address: int) -> list[str]:
    runtime_pointer_address = state_address + STATE_RUNTIME_POINTER_OFFSET

    def runtime(label: str, read_type: str, offset: int) -> str:
        return f"{label}:{read_type}:{runtime_pointer_address:#x}:{offset:#x}"

    specs = [
        f"runtime_pointer_confirm:u32:{runtime_pointer_address:#x}",
        f"map_id:s32:{state_address + STATE_MAP_ID_OFFSET:#x}",
        f"map_generation:u16:{state_address + STATE_MAP_GENERATION_OFFSET:#x}",
        f"movement_in_progress:u16:{state_address + STATE_MOVEMENT_IN_PROGRESS_OFFSET:#x}",
        f"active_steps:bytes10:{state_address + STATE_ACTIVE_STEPS_OFFSET:#x}",
        runtime("runtime_epoch", "u32", LIVE_STACK_OFFSET),
        runtime("data_incarnation", "u32", LIVE_STACK_OFFSET + 4),
        runtime("lifetime_state", "u8", LIVE_STACK_OFFSET + 8),
        runtime(
            "pickup_relations",
            f"bytes{PICKUP_RELATION_SIZE * MAX_SLOTS}",
            PICKUP_RELATIONS_OFFSET,
        ),
        runtime(
            "presentation_positions",
            "bytes40",
            LIVE_PRESENTATION_POSITIONS_OFFSET,
        ),
        runtime(
            "movement_object_generations",
            "bytes40",
            LIVE_MOVEMENT_OBJECT_GENERATIONS_OFFSET,
        ),
    ]
    for index in range(MAX_SLOTS):
        base = LIVE_STACK_OFFSET + STACK_HEADER_SIZE + index * SLOT_SIZE
        specs.extend(
            (
                runtime(f"slot{index}_generation", "u32", base),
                runtime(f"slot{index}_layer_count", "u8", base + 30),
                runtime(f"slot{index}_lifecycle", "u8", base + 31),
                runtime(f"slot{index}_presentation_gate", "u8", base + 32),
                runtime(
                    f"slot{index}_role",
                    "u8",
                    base + SLOT_EFFECTIVE_CACHE_OFFSET + EFFECTIVE_ROLE_OFFSET,
                ),
                runtime(
                    f"slot{index}_layers",
                    f"bytes{LAYER_BANK_SIZE}",
                    base + SLOT_LAYER_BANK_OFFSET,
                ),
                runtime(
                    f"slot{index}_timers",
                    f"bytes{TIMER_BANK_SIZE}",
                    base + SLOT_TIMER_BANK_OFFSET,
                ),
            )
        )
    return specs


def parse_hex_bytes(value: str, expected: int) -> bytes:
    text = value.lower().removeprefix("0x")
    data = bytes.fromhex(text)
    if len(data) != expected:
        raise ValueError(f"read returned {len(data)} bytes, expected {expected}")
    return data


def parse_layer_bank(value: str) -> list[dict[str, int]]:
    data = parse_hex_bytes(value, LAYER_BANK_SIZE)
    arrays = {
        "entry_generation": struct.unpack_from("<8I", data, 0),
        "definition_id": struct.unpack_from("<8H", data, 32),
        "owner_id": struct.unpack_from("<8H", data, 48),
        "instance_key": struct.unpack_from("<8H", data, 64),
        "required_owner_id": struct.unpack_from("<8H", data, 80),
        "tired_origin": struct.unpack_from("<8B", data, 96),
        "flags": struct.unpack_from("<8B", data, 104),
    }
    return [
        {name: int(values[index]) for name, values in arrays.items()}
        for index in range(MAX_LAYERS)
    ]


def parse_timer_bank(value: str) -> list[dict[str, int]]:
    data = parse_hex_bytes(value, TIMER_BANK_SIZE)
    names = (
        "entry_generation",
        "timer_generation",
        "owner_id",
        "instance_key",
        "definition_id",
        "recovery_transition_id",
        "remaining_ticks",
        "armed_duration",
        "clock",
        "hidden_policy",
        "recovery_policy",
        "flags",
    )
    timers = []
    for index in range(MAX_LAYERS):
        values = struct.unpack_from("<IIHHHHBBBBBB2x", data, index * 24)
        timers.append({name: int(value) for name, value in zip(names, values)})
    return timers


def parse_pickup_relations(value: str) -> list[dict[str, int | bool]]:
    data = parse_hex_bytes(value, PICKUP_RELATION_SIZE * MAX_SLOTS)
    relations = []
    for index in range(MAX_SLOTS):
        offset = index * PICKUP_RELATION_SIZE
        handle = struct.unpack_from("<IIIIHHB3x", data, offset)
        generations = struct.unpack_from("<IIII", data, offset + 24)
        carrier, carried, cleanup, _ = struct.unpack_from("<BBBB", data, offset + 40)
        relations.append(
            {
                "runtime_epoch": handle[0],
                "slot_generation": handle[1],
                "entry_generation": handle[2],
                "validity_tag": handle[3],
                "owner_id": handle[4],
                "instance_key": handle[5],
                "slot_index": handle[6],
                "relation_generation": generations[0],
                "throw_relation_generation": generations[1],
                "throw_command_generation": generations[2],
                "throw_command_serial": generations[3],
                "carrier_slot_plus_one": carrier,
                "carried": bool(carried),
                "cleanup_pending": bool(cleanup),
            }
        )
    return relations


def snapshot_from_reads(read_records: list[dict[str, Any]], heap: Any = None) -> dict[str, Any]:
    reads = {record["label"]: record["value"] for record in read_records}
    slots = []
    for index in range(MAX_SLOTS):
        slots.append(
            {
                "slot": index,
                "generation": int(reads[f"slot{index}_generation"]),
                "layer_count": int(reads[f"slot{index}_layer_count"]),
                "lifecycle": int(reads[f"slot{index}_lifecycle"]),
                "presentation_gate": int(reads[f"slot{index}_presentation_gate"]),
                "role": int(reads[f"slot{index}_role"]),
                "layers": parse_layer_bank(reads[f"slot{index}_layers"]),
                "timers": parse_timer_bank(reads[f"slot{index}_timers"]),
            }
        )
    return {
        "runtime_pointer_confirm": int(reads["runtime_pointer_confirm"]),
        "map_id": int(reads["map_id"]),
        "map_generation": int(reads["map_generation"]),
        "movement_in_progress": int(reads["movement_in_progress"]),
        "active_steps": list(parse_hex_bytes(reads["active_steps"], 10)),
        "presentation_positions": list(
            struct.unpack("<20h", parse_hex_bytes(reads["presentation_positions"], 40))
        ),
        "movement_object_generations": list(
            struct.unpack(
                "<10I", parse_hex_bytes(reads["movement_object_generations"], 40)
            )
        ),
        "runtime_epoch": int(reads["runtime_epoch"]),
        "data_incarnation": int(reads["data_incarnation"]),
        "lifetime_state": int(reads["lifetime_state"]),
        "slots": slots,
        "pickup_relations": parse_pickup_relations(reads["pickup_relations"]),
        "heap": heap,
    }


def snapshot_from_result(result: dict[str, Any]) -> dict[str, Any]:
    return snapshot_from_reads(result["reads"], result.get("heap_margin"))


def sampled_timeline(result: dict[str, Any]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    sequence = 0
    for action_index, action in enumerate(result.get("actions", [])):
        for sample in action.get("samples", []):
            snapshot = snapshot_from_reads(sample["reads"])
            snapshot["sample_sequence"] = sequence
            snapshot["action_index"] = action_index
            snapshot["action_frame"] = sample.get("frame", 0)
            snapshot["keys_held"] = bool(sample.get("keys_held", False))
            timeline.append(snapshot)
            sequence += 1
    return timeline


def live_timers(slot: dict[str, Any]) -> list[dict[str, int]]:
    return [timer for timer in slot["timers"] if timer["flags"] & TIMER_VALID]


def relation_handle_is_current(snapshot: dict[str, Any], index: int) -> bool:
    relation = snapshot["pickup_relations"][index]
    slot = snapshot["slots"][index]
    return (
        relation["owner_id"] != 0
        and relation["runtime_epoch"] == snapshot["runtime_epoch"]
        and relation["slot_generation"] == slot["generation"]
        and relation["slot_index"] == index
        and relation["entry_generation"] != 0
        and relation["validity_tag"] != 0
        and any(
            layer["entry_generation"] == relation["entry_generation"]
            and layer["owner_id"] == relation["owner_id"]
            and layer["instance_key"] == relation["instance_key"]
            for layer in slot["layers"]
        )
    )


def progress_signature(snapshot: dict[str, Any]) -> tuple[Any, ...]:
    return (
        snapshot["map_id"],
        snapshot["map_generation"],
        snapshot["movement_in_progress"],
        tuple(snapshot["active_steps"]),
        tuple(snapshot["presentation_positions"]),
        tuple(snapshot["movement_object_generations"]),
        tuple(
            (
                slot["generation"],
                slot["lifecycle"],
                slot["role"],
                slot["layer_count"],
                tuple(
                    (timer["timer_generation"], timer["remaining_ticks"])
                    for timer in live_timers(slot)
                ),
            )
            for slot in snapshot["slots"]
        ),
        tuple(
            (
                relation["owner_id"],
                relation["relation_generation"],
                relation["carried"],
            )
            for relation in snapshot["pickup_relations"]
        ),
    )


def authenticated_slot(snapshot: dict[str, Any], slot: int, generation: int) -> bool:
    current = snapshot["slots"][slot]
    return (
        generation != 0
        and current["generation"] == generation
        and current["lifecycle"] == 1
        and current["role"] in range(1, 8)
    )


def rolling_progress_identities(
    timeline: list[dict[str, Any]],
) -> list[tuple[int, int, int, int]]:
    """Return slot generations with bounded progress through a late sample run."""
    identities: list[tuple[int, int, int, int]] = []
    for slot in range(MAX_SLOTS):
        generations = {
            int(sample["slots"][slot]["generation"])
            for sample in timeline
            if sample["slots"][slot]["lifecycle"] == 1
            and sample["slots"][slot]["generation"] != 0
        }
        for generation in generations:
            start = 0
            while start < len(timeline):
                if not authenticated_slot(timeline[start], slot, generation):
                    start += 1
                    continue
                end = start
                while end + 1 < len(timeline) and authenticated_slot(
                    timeline[end + 1], slot, generation
                ):
                    end += 1
                run = timeline[start : end + 1]
                signatures = [progress_signature(sample) for sample in run]
                changes = [
                    first != second
                    for first, second in zip(signatures, signatures[1:])
                ]
                rolling = all(any(changes[index : index + 3]) for index in range(len(run) - 3))
                if (
                    len(run) >= 4
                    and end >= len(timeline) - 2
                    and sum(changes) >= 2
                    and rolling
                ):
                    identities.append((slot, generation, start, end))
                start = end + 1
    return identities


def scenario_evidence(mode: str, timeline: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    if len(timeline) < 8 or not any(sample["keys_held"] for sample in timeline):
        return ["scenario is inconclusive: bounded key-held samples are missing"]
    progress_identities = rolling_progress_identities(timeline)
    if not progress_identities:
        issues.append(
            "scenario is inconclusive: the same assigned slot generation did not retain "
            "rolling gameplay progress into late samples"
        )

    if mode == "spawn-freeze":
        return issues

    if mode == "alert-aggro-tired-recovery":
        complete = False
        for slot, generation, start, end in progress_identities:
            observations = timeline[start : end + 1]
            roles = [sample["slots"][slot]["role"] for sample in observations]
            attentive = next((index for index, role in enumerate(roles) if role == 2), None)
            tired = next(
                (
                    index
                    for index, role in enumerate(roles)
                    if role in (3, 4) and attentive is not None and index > attentive
                ),
                None,
            )
            calm = next(
                (
                    index
                    for index, role in enumerate(roles)
                    if role == 1 and tired is not None and index > tired
                ),
                None,
            )
            timer_history: dict[tuple[int, int, int], list[int]] = {}
            for sample in observations:
                for timer in live_timers(sample["slots"][slot]):
                    key = (
                        timer["entry_generation"],
                        timer["owner_id"],
                        timer["timer_generation"],
                    )
                    timer_history.setdefault(key, []).append(timer["remaining_ticks"])
            countdown = any(
                len(values) >= 2 and min(values) < max(values)
                for values in timer_history.values()
            )
            if attentive is not None and tired is not None and calm is not None and countdown:
                complete = True
                break
        if not complete:
            issues.append(
                "alert/tired/recovery is inconclusive: one authenticated slot generation "
                "did not show ATTENTIVE, TIRED/ASLEEP, CALM, and a valid timer countdown"
            )
        return issues

    if mode == "pickup-throw":
        observed: list[tuple[int, int, int, int]] = []
        for index, sample in enumerate(timeline):
            for target, relation in enumerate(sample["pickup_relations"]):
                carrier = int(relation["carrier_slot_plus_one"]) - 1
                if (
                    relation["carried"]
                    and 0 <= carrier < MAX_SLOTS
                    and carrier != target
                    and relation_handle_is_current(sample, target)
                    and sample["slots"][target]["lifecycle"] == 1
                    and sample["slots"][carrier]["lifecycle"] == 1
                ):
                    observed.append(
                        (index, target, carrier, sample["slots"][target]["generation"])
                    )
        if not observed:
            issues.append("pickup/throw is inconclusive: no two-entity carried relation was observed")
        elif not any(
            later > index
            and authenticated_slot(timeline[later], target, generation)
            and not timeline[later]["pickup_relations"][target]["carried"]
            and timeline[later]["slots"][target]["role"] != 5
            and any(
                layer["entry_generation"] != 0
                for layer in timeline[later]["slots"][target]["layers"]
            )
            for index, target, _carrier, generation in observed
            for later in range(index + 1, len(timeline))
        ):
            issues.append(
                "pickup/throw is inconclusive: the same target generation did not reveal "
                "a non-CARRIED effective state/layer"
            )
        return issues

    if mode == "lifecycle":
        transitioned = any(
            first["map_id"] != second["map_id"]
            or first["map_generation"] != second["map_generation"]
            or first["runtime_epoch"] != second["runtime_epoch"]
            or first["data_incarnation"] != second["data_incarnation"]
            or first["lifetime_state"] != second["lifetime_state"]
            for first, second in zip(timeline, timeline[1:])
        )
        if not transitioned:
            issues.append("lifecycle is inconclusive: no map/battle boundary was observed")
        return issues
    return [f"unknown scenario mode {mode}"]


def evaluate_snapshot(
    snapshot: dict[str, Any],
    *,
    dsv_unchanged: bool,
    rom_unchanged: bool,
) -> list[str]:
    issues: list[str] = []
    if snapshot["runtime_pointer_confirm"] == 0 or snapshot["runtime_pointer_confirm"] & 3:
        issues.append("runtime pointer is zero or unaligned")
    if snapshot["runtime_epoch"] == 0 or snapshot["data_incarnation"] == 0:
        issues.append("runtime epoch/data incarnation is zero")
    if snapshot["lifetime_state"] not in (1, 2):
        issues.append("runtime is neither active nor resident-cold")
    for slot in snapshot["slots"]:
        layer_count = slot["layer_count"]
        live_layers = [layer for layer in slot["layers"] if layer["entry_generation"]]
        if layer_count > MAX_LAYERS or layer_count != len(live_layers):
            issues.append(f"slot {slot['slot']} layer count/bank differs")
        if slot["lifecycle"] == 1 and (
            slot["generation"] == 0 or slot["role"] not in range(1, 8)
        ):
            issues.append(f"slot {slot['slot']} assigned identity/effective role is invalid")
        if slot["lifecycle"] not in (0, 1, 2):
            issues.append(f"slot {slot['slot']} lifecycle value is invalid")
        layer_keys = {
            (
                layer["entry_generation"],
                layer["owner_id"],
                layer["instance_key"],
                layer["definition_id"],
            )
            for layer in live_layers
        }
        for timer in slot["timers"]:
            if not (timer["flags"] & TIMER_VALID):
                continue
            if timer["timer_generation"] == 0:
                issues.append(f"slot {slot['slot']} valid timer has generation zero")
                continue
            key = (
                timer["entry_generation"],
                timer["owner_id"],
                timer["instance_key"],
                timer["definition_id"],
            )
            if key not in layer_keys:
                issues.append(f"slot {slot['slot']} timer has no exact owning layer")
    for index, relation in enumerate(snapshot["pickup_relations"]):
        if relation["owner_id"] != 0 or relation["carried"] or relation["cleanup_pending"]:
            slot = snapshot["slots"][index]
            if not relation_handle_is_current(snapshot, index):
                issues.append(f"slot {index} carried relation lacks a current handle")
            if relation["carried"] and slot["role"] != 5:
                issues.append(f"slot {index} carried relation is not effective CARRIED")
    heap = snapshot.get("heap")
    if not isinstance(heap, dict) or not heap.get("passed", False):
        issues.append("heap 3/11 margin snapshot did not pass")
    if not dsv_unchanged:
        issues.append("source test.dsv changed during read-only verification")
    if not rom_unchanged:
        issues.append("ROM changed during verification")
    return issues


def parse_headless_json(stdout: str) -> dict[str, Any]:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise ValueError("headless helper did not return one JSON document") from error
    if not isinstance(value, dict) or "passed" not in value or "reads" not in value:
        raise ValueError("headless helper result is malformed")
    return value


def run_headless(
    helper: Path,
    rom: Path,
    dsv: Path,
    actions: tuple[str, ...],
    reads: list[str],
    *,
    screenshot: Path | None = None,
    heap_report: Path | None = None,
    heap_info_address: int | None = None,
) -> dict[str, Any]:
    command = [str(helper), "--rom", str(rom), "--dsv", str(dsv)]
    for action in actions:
        command.extend(("--action", action))
    for read in reads:
        command.extend(("--read", read))
    if screenshot is None:
        command.append("--no-screenshot")
    else:
        command.extend(("--screenshot", str(screenshot)))
    if heap_report is not None:
        command.extend(("--heap-margin-report", str(heap_report)))
        if heap_info_address is not None:
            command.extend(("--heap-info-address", hex(heap_info_address)))
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"headless helper failed ({completed.returncode}): {detail}")
    return parse_headless_json(completed.stdout)


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    scenario = SCENARIOS[args.mode]
    actions = scenario.actions + tuple(args.action)
    budget = args.frame_budget or scenario.frame_budget
    frames = validate_actions(actions, budget)
    rom = args.rom if args.rom.is_absolute() else ROOT / args.rom
    linked = args.linked if args.linked.is_absolute() else ROOT / args.linked
    spawns_linked = (
        args.spawns_linked
        if args.spawns_linked.is_absolute()
        else ROOT / args.spawns_linked
    )
    built_arm9 = args.built_arm9 if args.built_arm9.is_absolute() else ROOT / args.built_arm9
    if not rom.is_file():
        raise FileNotFoundError(f"ROM not found: {rom}")
    for path, label in (
        (linked, "resident linked object"),
        (spawns_linked, "spawns linked object"),
        (built_arm9, "built ARM9"),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{label} not found: {path}")
    dsv = find_dsv(args.dsv)
    symbols = resolve_symbols(
        linked, ("sOverworldWildSpawnState", "sHeapInfo", "__text_start")
    )
    spawns_symbols = resolve_symbols(spawns_linked, ("__text_start",))
    state_address, state_size = symbols["sOverworldWildSpawnState"]
    if state_size != STATE_SIZE:
        raise ValueError(
            f"same-build spawn-state size is {state_size:#x}, expected {STATE_SIZE:#x}"
        )
    identity = authenticate_rom_build_identity(
        rom,
        linked,
        spawns_linked,
        built_arm9,
        symbols,
        spawns_symbols,
    )
    return {
        "scenario": scenario,
        "actions": actions,
        "frame_budget": budget,
        "action_frames": frames,
        "rom": rom,
        "dsv": dsv,
        "linked": linked,
        "spawns_linked": spawns_linked,
        "built_arm9": built_arm9,
        "state_address": state_address,
        "heap_info_address": symbols["sHeapInfo"][0],
        "build_identity": identity,
    }


def parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=tuple(SCENARIOS), default="spawn-freeze")
    parser.add_argument("--rom", type=Path, default=Path("test.nds"))
    parser.add_argument("--dsv", type=Path)
    parser.add_argument("--linked", type=Path, default=Path("build/linked.o"))
    parser.add_argument(
        "--spawns-linked",
        type=Path,
        default=Path("build/overworld_wild_spawns_overlay_linked.o"),
    )
    parser.add_argument("--built-arm9", type=Path, default=Path("build/arm9.bin"))
    parser.add_argument("--headless-helper", type=Path, default=HEADLESS)
    parser.add_argument("--frame-budget", type=int)
    parser.add_argument("--action", action="append", default=[])
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument(
        "--plan-only", action="store_true", help="Print the bounded plan without emulation."
    )
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    args = parse_args(arguments)
    plan = build_plan(args)
    plan_json = {
        "mode": plan["scenario"].name,
        "purpose": plan["scenario"].purpose,
        "actions": plan["actions"],
        "action_frames": plan["action_frames"],
        "frame_budget": plan["frame_budget"],
        "rom": str(plan["rom"]),
        "dsv": str(plan["dsv"]),
        "linked": str(plan["linked"]),
        "spawns_linked": str(plan["spawns_linked"]),
        "built_arm9": str(plan["built_arm9"]),
        "build_identity": plan["build_identity"],
        "symbols": {
            "sOverworldWildSpawnState": f"{plan['state_address']:#x}",
            "sHeapInfo": f"{plan['heap_info_address']:#x}",
        },
    }
    if args.plan_only:
        print(json.dumps(plan_json, indent=2, sort_keys=True))
        return 0

    helper = args.headless_helper
    if not helper.is_absolute():
        helper = ROOT / helper
    before = {
        "rom": sha256_file(plan["rom"]),
        "dsv": sha256_file(plan["dsv"]),
    }
    with tempfile.TemporaryDirectory(prefix="ow-runtime-snapshot-") as directory:
        heap_report = Path(directory) / "heap.json"
        result = run_headless(
            helper,
            plan["rom"],
            plan["dsv"],
            plan["actions"],
            read_specs(plan["state_address"]),
            screenshot=args.screenshot,
            heap_report=heap_report,
            heap_info_address=plan["heap_info_address"],
        )
    after = {
        "rom": sha256_file(plan["rom"]),
        "dsv": sha256_file(plan["dsv"]),
    }
    snapshot = snapshot_from_result(result)
    timeline = sampled_timeline(result)
    issues = evaluate_snapshot(
        snapshot,
        dsv_unchanged=before["dsv"] == after["dsv"],
        rom_unchanged=before["rom"] == after["rom"],
    )
    issues.extend(scenario_evidence(plan["scenario"].name, timeline))
    output = {
        "schema": "overworld-stack-runtime-snapshot-v1",
        "plan": plan_json,
        "hashes": {"before": before, "after": after},
        "runtime_pointer": snapshot["runtime_pointer_confirm"],
        "snapshot": snapshot,
        "sample_count": len(timeline),
        "evidence": {
            "progress_changes": sum(
                progress_signature(first) != progress_signature(second)
                for first, second in zip(timeline, timeline[1:])
            ),
            "key_held_samples": sum(sample["keys_held"] for sample in timeline),
        },
        "issues": issues,
        "passed": not issues,
        "headless": {
            "snapshot_ready_frames": result.get("ready_frames"),
            "screenshot": result.get("screenshot"),
        },
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if not issues else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"runtime snapshot failed: {error}", file=sys.stderr)
        raise SystemExit(1)
