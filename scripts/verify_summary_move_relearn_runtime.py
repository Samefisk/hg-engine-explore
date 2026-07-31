#!/usr/bin/env python3
"""Deterministic key/touch Summary relearn acceptance on a preserved DSV."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from types import SimpleNamespace


REPO = Path(__file__).resolve().parents[1]
SAVE_DATA_POINTER = 0x021D2228
SAVE_HISTORY_POINTER_OFFSET = 0x2F30C
SAVE_HISTORY_METADATA_SIZE = 0x14
HISTORY_IMAGE_SIZE = 0x5000
HISTORY_HEADER_SIZE = 0x20
HISTORY_RECORD_SIZE = 0x40
HISTORY_RECORD_COUNT = 319
PARTY_OFFSET = 0xA0
PARTY_SIZE = 8 + 6 * 0xEC
LOCAL_FIELD_DATA_OFFSET = 0x1424
PC_SAVE_OFFSET = 0x10000
PC_SAVE_SIZE = 0x1E4FC
PC_BOX_COUNT = 30
PC_BOX_SIZE = 0x1000
PC_MON_SIZE = 0x88
PC_MONS_PER_BOX = 30
PC_STORAGE_BOXES_SIZE = PC_BOX_COUNT * PC_BOX_SIZE
PC_FOOTER_SIZE = 0x10
PC_SAVE_SLOT = 1
SAVE_DYNAMIC_REGION_OFFSET = 0x10
PC_ACTIVE_BOX_OFFSET = PC_STORAGE_BOXES_SIZE
PC_MODIFIED_FLAGS_OFFSET = PC_STORAGE_BOXES_SIZE + 4
BOX_TARGET_SLOT = 0
BOX_SWITCH_SLOT = 1
BOX_TARGET_OT_ID_XOR = 0x13579BDF
BOX_SWITCH_OT_ID_XOR = 0x2468ACE0
TARGET_SLOT = 2
TARGET_SPECIES = 72
TARGET_REPLACEMENT_SLOT = 3
TARGET_MOVE = 40  # Poison Sting
CONTROLLED_MOVES = (57, 48, 352, 103)
CONTROLLED_PP = (8, 8, 8, 1)
CONTROLLED_PP_UPS = (0, 0, 0, 2)
CONTROLLED_HISTORY_MOVES = (
    57, 48, 352, 103, 62, 114, 229, 243
)
CONTROLLED_CANDIDATES = (40, 55, 51, 35, 62, 114, 229, 243)
PERSISTED_CANDIDATES = (55, 51, 35, 103, 62, 114, 229, 243)
HISTORY_MIRROR_OFFSETS = (0x3B000, 0x7B000)
HISTORY_FOOTER_OFFSET = 0x4FE0
HISTORY_FOOTER_MAGIC = 0x4D48464F
SUMMARY_STATE_ORIGINAL_MOVES_OFFSET = 134
SUMMARY_STATE_CANDIDATE_COUNT_OFFSET = 150
SUMMARY_STATE_CANDIDATE_CURSOR_OFFSET = 152
SUMMARY_STATE_CANDIDATE_TOP_OFFSET = 154
SUMMARY_STATE_PENDING_MOVE_OFFSET = 156
SUMMARY_STATE_ORIGINAL_ARG_MOVE_OFFSET = 158
SUMMARY_STATE_OWNER_POS_OFFSET = 160
SUMMARY_STATE_SELECTED_SLOT_OFFSET = 161
SUMMARY_STATE_MODE_OFFSET = 163
SUMMARY_STATE_RESUME_AFTER_SWITCH_OFFSET = 165
SUMMARY_STATE_OWNER_POKEMON_OFFSET = 168
SUMMARY_STATE_RETAIL_SIZE = 0x7D8
SUMMARY_OWNER_DIRTY_OFFSET = 0x38
SUMMARY_BASE_MOVE_OFFSET = 0x18
SUMMARY_BASE_POS_OFFSET = 0x14
SUMMARY_BASE_DATA_TYPE_OFFSET = 0x11
SUMMARY_BASE_POINTER_OFFSET = 0x22C
SUMMARY_PAGE_MODE_OFFSET = 0x7BC
SUMMARY_CACHE_MOVES_OFFSET = 0x264
SUMMARY_CACHE_CUR_PP_OFFSET = 0x26C
SUMMARY_CACHE_MAX_PP_OFFSET = 0x270
MAIN_OVERLAY_TABLE = 0x021D0DF0
OVERLAY_ENTRY_SIZE = 8
OVERLAY_SLOT_COUNT = 8
SUMMARY_RELEARN_OVERLAY_ID = 154


def ensure_repo_venv() -> None:
    venv = REPO / ".venv"
    python = venv / "bin/python3"
    if Path(sys.prefix).resolve() == venv.resolve() or not python.is_file():
        return
    os.execv(str(python), [str(python), *sys.argv])


ensure_repo_venv()

from desmume.emulator import DeSmuME  # noqa: E402


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import verifier helpers from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


HEADLESS = load_module(
    "summary_relearn_headless",
    REPO / "scripts/headless-overworld-test.py",
)
PARTY = load_module(
    "summary_relearn_party",
    REPO / "scripts/verify_pokemon_move_history_party_integrity.py",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def boot_arguments() -> SimpleNamespace:
    return SimpleNamespace(
        boot_frames=420,
        ready_a_taps=10,
        tap_hold_frames=24,
        tap_gap_frames=36,
        load_frames=300,
    )


def tap(emu: DeSmuME, key: str, gap: int = 60) -> None:
    HEADLESS.tap_key(emu, key, 2, gap)


def touch(emu: DeSmuME, x: int, y: int, gap: int = 60) -> None:
    emu.input.touch_set_pos(x, y)
    HEADLESS.cycle(emu, 8)
    emu.input.touch_release()
    HEADLESS.cycle(emu, gap)


def screenshot(emu: DeSmuME, root: Path, name: str) -> str:
    path = root / name
    emu.screenshot().save(path)
    return str(path)


def save_data_pointer(emu: DeSmuME) -> int:
    pointer = emu.memory.unsigned[
        SAVE_DATA_POINTER:SAVE_DATA_POINTER:4
    ]
    require(
        0x02000000 <= pointer < 0x02400000,
        f"invalid SaveData pointer 0x{pointer:08X}",
    )
    return pointer


def read_bytes(emu: DeSmuME, address: int, size: int) -> bytes:
    return bytes(emu.memory.unsigned[address:address + size:1])


def read_u8(emu: DeSmuME, address: int) -> int:
    return emu.memory.unsigned[address:address:1]


def read_u16(emu: DeSmuME, address: int) -> int:
    return emu.memory.unsigned[address:address:2]


def read_u32(emu: DeSmuME, address: int) -> int:
    return emu.memory.unsigned[address:address:4]


def write_bytes(emu: DeSmuME, address: int, data: bytes) -> None:
    emu.memory.unsigned[address:address + len(data):1] = data


def write_u8(emu: DeSmuME, address: int, value: int) -> None:
    write_bytes(emu, address, bytes((value & 0xFF,)))


def write_u16(emu: DeSmuME, address: int, value: int) -> None:
    write_bytes(emu, address, struct.pack("<H", value))


def write_u32(emu: DeSmuME, address: int, value: int) -> None:
    write_bytes(emu, address, struct.pack("<I", value))


def overlay_registry(emu: DeSmuME) -> list[tuple[int, int]]:
    return [
        (
            read_u32(emu, MAIN_OVERLAY_TABLE + index * OVERLAY_ENTRY_SIZE),
            read_u32(
                emu,
                MAIN_OVERLAY_TABLE + index * OVERLAY_ENTRY_SIZE + 4,
            ),
        )
        for index in range(OVERLAY_SLOT_COUNT)
    ]


def overlay_is_active(emu: DeSmuME, overlay_id: int) -> bool:
    return any(
        current_id == overlay_id and active == 1
        for current_id, active in overlay_registry(emu)
    )


def wait_overlay_active(
    emu: DeSmuME,
    overlay_id: int,
    expected: bool,
    maximum_frames: int = 600,
) -> int:
    for frame in range(maximum_frames + 1):
        if overlay_is_active(emu, overlay_id) == expected:
            return frame
        HEADLESS.cycle(emu, 1)
    raise RuntimeError(
        f"overlay {overlay_id} active={expected} not reached; "
        f"registry={overlay_registry(emu)}"
    )


def runtime_party(emu: DeSmuME) -> bytes:
    return read_bytes(emu, save_data_pointer(emu) + PARTY_OFFSET, PARTY_SIZE)


def runtime_pc_storage_address(emu: DeSmuME) -> int:
    return (
        save_data_pointer(emu)
        + SAVE_DYNAMIC_REGION_OFFSET
        + PC_SAVE_OFFSET
    )


def runtime_box_address(
    emu: DeSmuME,
    box: int,
    slot: int,
) -> int:
    require(0 <= box < PC_BOX_COUNT, f"invalid runtime box index {box}")
    require(0 <= slot < PC_MONS_PER_BOX, f"invalid runtime box slot {slot}")
    return (
        runtime_pc_storage_address(emu)
        + box * PC_BOX_SIZE
        + slot * PC_MON_SIZE
    )


def runtime_box_record(
    emu: DeSmuME,
    box: int,
    slot: int,
) -> bytes:
    return read_bytes(emu, runtime_box_address(emu, box, slot), PC_MON_SIZE)


def runtime_pc_modified_flags(emu: DeSmuME) -> int:
    return read_u32(
        emu,
        runtime_pc_storage_address(emu) + PC_MODIFIED_FLAGS_OFFSET,
    )


def runtime_history(emu: DeSmuME) -> tuple[bytes, bytes]:
    save = save_data_pointer(emu)
    metadata = read_bytes(
        emu,
        save + SAVE_HISTORY_POINTER_OFFSET,
        SAVE_HISTORY_METADATA_SIZE,
    )
    pointer = struct.unpack_from("<I", metadata)[0]
    require(
        0x02000000 <= pointer < 0x02400000,
        f"invalid move-history pointer 0x{pointer:08X}",
    )
    return metadata, read_bytes(emu, pointer, HISTORY_IMAGE_SIZE)


def wait_party_locked(
    emu: DeSmuME,
    maximum_frames: int = 90,
) -> bytes:
    for _ in range(maximum_frames + 1):
        party = runtime_party(emu)
        flags = [
            struct.unpack_from("<H", party, 8 + index * 0xEC + 4)[0]
            for index in range(6)
        ]
        if all((flag & 3) == 0 for flag in flags):
            return party
        emu.cycle(1)
    raise RuntimeError("party accessors did not restore encrypted record state")


def record_payload(record: bytes) -> tuple[bytes, tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    box = record[:0x88]
    pid = struct.unpack_from("<I", box)[0]
    payload = PARTY.decrypt_box_payload(box)
    permutation = (pid & 0x3E000) >> 13
    attacks = PARTY.SUBSTRUCT_OFFSETS[permutation][1]
    moves = struct.unpack_from("<4H", payload, attacks)
    pp = struct.unpack_from("<4B", payload, attacks + 8)
    pp_ups = struct.unpack_from("<4B", payload, attacks + 12)
    return payload, moves, pp, pp_ups


def party_record(party: bytes, slot: int) -> bytes:
    start = 8 + slot * 0xEC
    return party[start:start + 0xEC]


def encrypt_box_payload(payload: bytes, checksum: int) -> bytes:
    seed = checksum
    encrypted = bytearray(payload)
    for offset in range(0, len(encrypted), 2):
        seed = (seed * 1103515245 + 24691) & 0xFFFFFFFF
        word = struct.unpack_from("<H", encrypted, offset)[0]
        struct.pack_into("<H", encrypted, offset, word ^ (seed >> 16))
    return bytes(encrypted)


def controlled_party_record(record: bytes) -> bytes:
    payload, _, _, _ = record_payload(record)
    payload_data = bytearray(payload)
    pid = struct.unpack_from("<I", record)[0]
    permutation = (pid & 0x3E000) >> 13
    attacks = PARTY.SUBSTRUCT_OFFSETS[permutation][1]
    struct.pack_into("<4H", payload_data, attacks, *CONTROLLED_MOVES)
    struct.pack_into("<4B", payload_data, attacks + 8, *CONTROLLED_PP)
    struct.pack_into("<4B", payload_data, attacks + 12, *CONTROLLED_PP_UPS)
    checksum = sum(struct.unpack("<64H", payload_data)) & 0xFFFF
    controlled = bytearray(record)
    struct.pack_into("<H", controlled, 6, checksum)
    controlled[8:0x88] = encrypt_box_payload(payload_data, checksum)
    return bytes(controlled)


def box_identity(box: bytes) -> tuple[int, int, int]:
    require(len(box) == PC_MON_SIZE, "BoxPokemon record has the wrong size")
    pid = struct.unpack_from("<I", box)[0]
    payload = PARTY.decrypt_box_payload(box)
    permutation = (pid & 0x3E000) >> 13
    growth = PARTY.SUBSTRUCT_OFFSETS[permutation][0]
    species = struct.unpack_from("<H", payload, growth)[0]
    ot_id = struct.unpack_from("<I", payload, growth + 4)[0]
    return pid, ot_id, species


def box_record_payload(
    box: bytes,
) -> tuple[bytes, tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    return record_payload(box + bytes(0xEC - PC_MON_SIZE))


def controlled_box_record(
    record: bytes,
    *,
    ot_id_xor: int,
    moves: tuple[int, int, int, int] | None = None,
    pp: tuple[int, int, int, int] | None = None,
    pp_ups: tuple[int, int, int, int] | None = None,
) -> bytes:
    """Derive a distinct, authenticated BoxPokemon without changing its PID."""
    source = record[:PC_MON_SIZE]
    payload = bytearray(PARTY.decrypt_box_payload(source))
    pid = struct.unpack_from("<I", source)[0]
    permutation = (pid & 0x3E000) >> 13
    growth = PARTY.SUBSTRUCT_OFFSETS[permutation][0]
    attacks = PARTY.SUBSTRUCT_OFFSETS[permutation][1]
    original_ot_id = struct.unpack_from("<I", payload, growth + 4)[0]
    struct.pack_into("<I", payload, growth + 4, original_ot_id ^ ot_id_xor)
    if moves is not None:
        struct.pack_into("<4H", payload, attacks, *moves)
    if pp is not None:
        struct.pack_into("<4B", payload, attacks + 8, *pp)
    if pp_ups is not None:
        struct.pack_into("<4B", payload, attacks + 12, *pp_ups)
    checksum = sum(struct.unpack("<64H", payload)) & 0xFFFF
    controlled = bytearray(source)
    struct.pack_into("<H", controlled, 6, checksum)
    controlled[8:] = encrypt_box_payload(bytes(payload), checksum)
    validate_box_checksum(bytes(controlled), "controlled BoxPokemon")
    return bytes(controlled)


def validate_box_checksum(box: bytes, label: str) -> dict[str, int | bool]:
    require(len(box) == PC_MON_SIZE, f"{label} has the wrong serialized size")
    stored = struct.unpack_from("<H", box, 6)[0]
    payload = PARTY.decrypt_box_payload(box)
    calculated = sum(struct.unpack("<64H", payload)) & 0xFFFF
    require(
        stored == calculated,
        f"{label} checksum 0x{stored:04X} != 0x{calculated:04X}",
    )
    pid, ot_id, species = box_identity(box)
    return {
        "stored": stored,
        "calculated": calculated,
        "valid": True,
        "pid": pid,
        "ot_id": ot_id,
        "species": species,
    }


def pc_box_record(raw: bytes, base: int, box: int, slot: int) -> bytes:
    require(0 <= box < PC_BOX_COUNT, f"invalid box index {box}")
    require(0 <= slot < PC_MONS_PER_BOX, f"invalid box slot {slot}")
    start = base + PC_SAVE_OFFSET + box * PC_BOX_SIZE + slot * PC_MON_SIZE
    return raw[start:start + PC_MON_SIZE]


def valid_pc_copies(raw: bytes) -> list[tuple[int, int]]:
    copies: list[tuple[int, int]] = []
    for base in PARTY.SAVE_COPY_BASES:
        footer = base + PC_SAVE_OFFSET + PC_SAVE_SIZE - PC_FOOTER_SIZE
        counter, size, magic, slot, crc = struct.unpack_from(
            "<IIIHH", raw, footer
        )
        if (
            size == PC_SAVE_SIZE
            and magic == PARTY.SAVE_MAGIC
            and slot == PC_SAVE_SLOT
            and crc
            == PARTY.crc16_ccitt_false(
                raw[base + PC_SAVE_OFFSET:footer]
            )
        ):
            copies.append((counter, base))
    return copies


def active_pc_copy(raw: bytes) -> tuple[int, int]:
    copies = valid_pc_copies(raw)
    require(copies, "raw save has no valid authenticated PC generation")
    selected = copies[0]
    for candidate in copies[1:]:
        if PARTY.save_counter_compare(candidate[0], selected[0]) > 0:
            selected = candidate
    return selected


def validate_all_boxed_checksums(
    raw: bytes,
    base: int,
) -> list[dict[str, int | bool]]:
    results: list[dict[str, int | bool]] = []
    for box in range(PC_BOX_COUNT):
        for slot in range(PC_MONS_PER_BOX):
            record = pc_box_record(raw, base, box, slot)
            checked = validate_box_checksum(
                record, f"serialized PC box {box} slot {slot}"
            )
            results.append({"box": box, "slot": slot, **checked})
    return results


def validate_all_party_checksums(party: bytes) -> list[dict[str, int | bool]]:
    results: list[dict[str, int | bool]] = []
    for index in range(6):
        box = party_record(party, index)[:0x88]
        stored = struct.unpack_from("<H", box, 6)[0]
        payload = PARTY.decrypt_box_payload(box)
        calculated = sum(struct.unpack("<64H", payload)) & 0xFFFF
        require(
            stored == calculated,
            f"serialized party slot {index} checksum "
            f"0x{stored:04X} != 0x{calculated:04X}",
        )
        results.append(
            {
                "slot": index,
                "stored": stored,
                "calculated": calculated,
                "valid": True,
            }
        )
    return results


def locate_summary_relearn_state(
    emu: DeSmuME,
    original_moves: tuple[int, ...] = CONTROLLED_MOVES,
    owner_pos: int = TARGET_SLOT,
    minimum_candidates: int = 1,
) -> int:
    signature = struct.pack("<4H", *original_moves)
    for chunk_address in range(0x02000000, 0x02400000, 0x10000):
        chunk = read_bytes(emu, chunk_address, 0x10000)
        offset = chunk.find(signature)
        while offset >= 0:
            original_moves = chunk_address + offset
            state = original_moves - SUMMARY_STATE_ORIGINAL_MOVES_OFFSET
            if (
                state >= 0x02000000
                and read_u16(
                    emu,
                    state + SUMMARY_STATE_CANDIDATE_COUNT_OFFSET,
                ) >= minimum_candidates
                and read_u8(
                    emu,
                    state + SUMMARY_STATE_OWNER_POS_OFFSET,
                ) == owner_pos
            ):
                owner = read_u32(emu, state)
                require(
                    0x02000000 <= owner < 0x02400000,
                    f"invalid Summary owner pointer 0x{owner:08X}",
                )
                require(
                    state - SUMMARY_STATE_RETAIL_SIZE >= 0x02000000,
                    "Summary relearn state is not appended to retail state",
                )
                return state
            offset = chunk.find(signature, offset + 1)
    raise RuntimeError("could not locate live Summary relearn state")


def locate_inactive_summary_state(
    emu: DeSmuME,
    moves: tuple[int, ...] = CONTROLLED_MOVES,
    owner_pos: int = TARGET_SLOT,
    data_type: int = 1,
) -> int:
    signature = struct.pack("<4H", *moves)
    for chunk_address in range(0x02000000, 0x02400000, 0x10000):
        chunk = read_bytes(emu, chunk_address, 0x10000)
        offset = chunk.find(signature)
        while offset >= 0:
            summary = (
                chunk_address + offset - SUMMARY_CACHE_MOVES_OFFSET
            )
            owner = (
                read_u32(emu, summary + SUMMARY_BASE_POINTER_OFFSET)
                if summary >= 0x02000000
                else 0
            )
            if (
                0x02000000 <= owner < 0x02400000
                and read_u8(
                    emu, owner + SUMMARY_BASE_DATA_TYPE_OFFSET
                )
                == data_type
                and read_u8(emu, owner + SUMMARY_BASE_POS_OFFSET)
                == owner_pos
                and read_u8(emu, summary + SUMMARY_PAGE_MODE_OFFSET) == 1
            ):
                return summary + SUMMARY_STATE_RETAIL_SIZE
            offset = chunk.find(signature, offset + 1)
    raise RuntimeError("could not locate inactive Summary state")


def candidate_state(emu: DeSmuME, state: int) -> dict[str, object]:
    count = read_u16(emu, state + SUMMARY_STATE_CANDIDATE_COUNT_OFFSET)
    cursor = read_u16(emu, state + SUMMARY_STATE_CANDIDATE_CURSOR_OFFSET)
    top = read_u16(emu, state + SUMMARY_STATE_CANDIDATE_TOP_OFFSET)
    candidates = struct.unpack(
        f"<{count}H",
        read_bytes(emu, state + 4, count * 2),
    ) if count else ()
    summary = state - SUMMARY_STATE_RETAIL_SIZE
    cache_moves = struct.unpack(
        "<4H",
        read_bytes(emu, summary + SUMMARY_CACHE_MOVES_OFFSET, 8),
    )
    cache_cur = tuple(
        read_bytes(emu, summary + SUMMARY_CACHE_CUR_PP_OFFSET, 4)
    )
    cache_max = tuple(
        read_bytes(emu, summary + SUMMARY_CACHE_MAX_PP_OFFSET, 4)
    )
    return {
        "count": count,
        "cursor": cursor,
        "top": top,
        "candidates": candidates,
        "cache_moves": cache_moves,
        "cache_cur_pp": cache_cur,
        "cache_max_pp": cache_max,
    }


def assert_candidate_viewport(
    emu: DeSmuME,
    state: int,
    expected_cursor: int,
    expected_top: int,
    label: str,
) -> dict[str, object]:
    evidence = candidate_state(emu, state)
    require(
        evidence["cursor"] == expected_cursor
        and evidence["top"] == expected_top,
        f"{label} cursor/top differs: "
        f"{evidence['cursor']}/{evidence['top']}",
    )
    candidates = evidence["candidates"]
    visible = tuple(candidates[expected_top:expected_top + 4])
    padded = visible + (0,) * (4 - len(visible))
    require(
        evidence["cache_moves"] == padded,
        f"{label} visible candidate cache differs",
    )
    for index, move in enumerate(padded):
        current = evidence["cache_cur_pp"][index]
        maximum = evidence["cache_max_pp"][index]
        if move:
            require(
                current == maximum and maximum > 0,
                f"{label} candidate row {index} is not full PP: "
                f"{current}/{maximum}",
            )
        else:
            require(
                current == 0 and maximum == 0,
                f"{label} blank row has PP",
            )
    return evidence


def assert_prospective_slot(
    emu: DeSmuME,
    state: int,
    expected_slot: int,
    label: str,
) -> dict[str, object]:
    summary = state - SUMMARY_STATE_RETAIL_SIZE
    pending = read_u16(emu, state + SUMMARY_STATE_PENDING_MOVE_OFFSET)
    selected = read_u8(emu, state + SUMMARY_STATE_SELECTED_SLOT_OFFSET)
    moves = struct.unpack(
        "<4H",
        read_bytes(emu, summary + SUMMARY_CACHE_MOVES_OFFSET, 8),
    )
    current = tuple(
        read_bytes(emu, summary + SUMMARY_CACHE_CUR_PP_OFFSET, 4)
    )
    maximum = tuple(
        read_bytes(emu, summary + SUMMARY_CACHE_MAX_PP_OFFSET, 4)
    )
    require(selected == expected_slot, f"{label} selected slot differs")
    require(
        moves[selected] == pending and pending != 0,
        f"{label} does not show the pending move in the selected row",
    )
    require(
        current[selected] == maximum[selected] and maximum[selected] > 0,
        f"{label} prospective row is not full PP",
    )
    return {
        "label": label,
        "selected_slot": selected,
        "pending_move": pending,
        "displayed_moves": moves,
        "displayed_pp": current,
        "displayed_max_pp": maximum,
    }


def summary_state_evidence(
    emu: DeSmuME,
    state: int,
    expected_mode: int,
    expected_dirty: int,
    label: str,
) -> dict[str, int | str]:
    mode = read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET)
    owner = read_u32(emu, state)
    dirty = read_u32(emu, owner + SUMMARY_OWNER_DIRTY_OFFSET)
    require(mode == expected_mode, f"{label} mode {mode} != {expected_mode}")
    require(
        dirty == expected_dirty,
        f"{label} Summary dirty flag {dirty} != {expected_dirty}",
    )
    return {
        "label": label,
        "state": f"0x{state:08X}",
        "owner": f"0x{owner:08X}",
        "mode": mode,
        "owner_dirty": dirty,
    }


def wait_summary_identity(
    emu: DeSmuME,
    state: int,
    *,
    expected_pos: int,
    expected_mode: int,
    expected_owner_pokemon: int | None = None,
    maximum_frames: int = 360,
) -> dict[str, object]:
    summary = state - SUMMARY_STATE_RETAIL_SIZE
    for elapsed in range(maximum_frames + 1):
        owner = read_u32(emu, state)
        pos = (
            read_u8(emu, owner + SUMMARY_BASE_POS_OFFSET)
            if 0x02000000 <= owner < 0x02400000
            else 0xFF
        )
        mode = read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET)
        owner_pokemon = read_u32(
            emu, state + SUMMARY_STATE_OWNER_POKEMON_OFFSET
        )
        resume = read_u8(
            emu, state + SUMMARY_STATE_RESUME_AFTER_SWITCH_OFFSET
        )
        if (
            pos == expected_pos
            and mode == expected_mode
            and (
                expected_owner_pokemon is None
                or owner_pokemon == expected_owner_pokemon
            )
        ):
            return {
                "elapsed_frames": elapsed,
                "summary": f"0x{summary:08X}",
                "owner": f"0x{owner:08X}",
                "pos": pos,
                "mode": mode,
                "owner_pokemon": f"0x{owner_pokemon:08X}",
                "resume_after_switch": resume,
            }
        HEADLESS.cycle(emu, 1)
    raise RuntimeError(
        f"Summary identity pos={expected_pos} mode={expected_mode} "
        f"not reached; final pos={pos} mode={mode} "
        f"owner_pokemon=0x{owner_pokemon:08X} resume={resume}"
    )


def inactive_summary_evidence(
    emu: DeSmuME,
    state: int,
    label: str,
) -> dict[str, int | str]:
    summary = state - SUMMARY_STATE_RETAIL_SIZE
    owner = read_u32(emu, summary + SUMMARY_BASE_POINTER_OFFSET)
    mode = read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET)
    dirty = read_u32(emu, owner + SUMMARY_OWNER_DIRTY_OFFSET)
    require(mode == 0, f"{label} mode {mode} != 0")
    require(dirty == 0, f"{label} Summary dirty flag {dirty} != 0")
    return {
        "label": label,
        "state": f"0x{state:08X}",
        "owner": f"0x{owner:08X}",
        "mode": mode,
        "owner_dirty": dirty,
    }


def history_records(image: bytes) -> list[bytes]:
    return [
        image[
            HISTORY_HEADER_SIZE + index * HISTORY_RECORD_SIZE:
            HISTORY_HEADER_SIZE + (index + 1) * HISTORY_RECORD_SIZE
        ]
        for index in range(HISTORY_RECORD_COUNT)
    ]


def find_history_record(
    image: bytes,
    personality: int,
    ot_id: int,
) -> tuple[int, bytes, tuple[int, ...]]:
    for index, record in enumerate(history_records(image)):
        pid, owner = struct.unpack_from("<II", record)
        move_count = record[14]
        flags = record[15]
        if flags & 1 and pid == personality and owner == ot_id:
            moves = struct.unpack_from("<24H", record, 16)[:move_count]
            return index, record, moves
    raise RuntimeError("target move-history record is missing")


def valid_history_image(image: bytes, mirror: int) -> bool:
    if len(image) != HISTORY_IMAGE_SIZE:
        return False
    try:
        (
            magic,
            version,
            header_size,
            image_size,
            capacity,
            record_count,
            moves_per_record,
            record_size,
        ) = struct.unpack_from("<IHHIHHHH", image)
        (
            footer_magic,
            _,
            payload_size,
            payload_crc,
            _,
            footer_version,
            footer_size,
            footer_mirror,
            _,
            footer_crc,
        ) = struct.unpack_from("<IIIIIHHHHI", image, HISTORY_FOOTER_OFFSET)
    except struct.error:
        return False
    occupied = sum(record[15] == 1 for record in history_records(image))
    footer = image[HISTORY_FOOTER_OFFSET:]
    return (
        magic == 0x4D484953
        and version == 1
        and header_size == HISTORY_HEADER_SIZE
        and image_size == HISTORY_IMAGE_SIZE
        and capacity == HISTORY_RECORD_COUNT
        and record_count == occupied
        and moves_per_record == 24
        and record_size == HISTORY_RECORD_SIZE
        and footer_magic == HISTORY_FOOTER_MAGIC
        and footer_version == 1
        and footer_size == 0x20
        and footer_mirror == mirror
        and payload_size == HISTORY_FOOTER_OFFSET
        and payload_crc
        == (zlib.crc32(image[:HISTORY_FOOTER_OFFSET]) & 0xFFFFFFFF)
        and footer_crc
        == (zlib.crc32(footer[:0x1C]) & 0xFFFFFFFF)
    )


def history_image_for_mirror(
    payload: bytes,
    mirror: int,
    counter: int,
) -> bytes:
    require(
        len(payload) == HISTORY_FOOTER_OFFSET,
        "history payload has the wrong size",
    )
    image = bytearray(HISTORY_IMAGE_SIZE)
    image[:HISTORY_FOOTER_OFFSET] = payload
    struct.pack_into(
        "<IIIIIHHHHI",
        image,
        HISTORY_FOOTER_OFFSET,
        HISTORY_FOOTER_MAGIC,
        counter,
        HISTORY_FOOTER_OFFSET,
        zlib.crc32(payload) & 0xFFFFFFFF,
        0,
        1,
        0x20,
        mirror,
        0,
        0,
    )
    footer_crc = zlib.crc32(
        image[HISTORY_FOOTER_OFFSET:HISTORY_FOOTER_OFFSET + 0x1C]
    ) & 0xFFFFFFFF
    struct.pack_into("<I", image, HISTORY_FOOTER_OFFSET + 0x1C, footer_crc)
    require(valid_history_image(bytes(image), mirror), "constructed history invalid")
    return bytes(image)


def seed_history_record(
    payload: bytearray,
    box: bytes,
    moves: tuple[int, ...],
) -> int:
    pid, ot_id, species = box_identity(box)
    try:
        index, _, _ = find_history_record(
            bytes(payload) + bytes(HISTORY_IMAGE_SIZE - len(payload)),
            pid,
            ot_id,
        )
    except RuntimeError:
        index = next(
            (
                candidate
                for candidate, record in enumerate(
                    history_records(
                        bytes(payload)
                        + bytes(HISTORY_IMAGE_SIZE - len(payload))
                    )
                )
                if record[15] == 0
            ),
            -1,
        )
        require(index >= 0, "controlled history has no free record")
        record_count = struct.unpack_from("<H", payload, 14)[0]
        next_access = struct.unpack_from("<I", payload, 20)[0] + 1
        struct.pack_into("<H", payload, 14, record_count + 1)
        struct.pack_into("<I", payload, 20, next_access)
        record_offset = HISTORY_HEADER_SIZE + index * HISTORY_RECORD_SIZE
        payload[record_offset:record_offset + HISTORY_RECORD_SIZE] = bytes(
            HISTORY_RECORD_SIZE
        )
        struct.pack_into(
            "<IIIHBB",
            payload,
            record_offset,
            pid,
            ot_id,
            next_access,
            species,
            0,
            1,
        )
    record_offset = HISTORY_HEADER_SIZE + index * HISTORY_RECORD_SIZE
    require(
        len(moves) <= 24 and all(move != 0 for move in moves),
        "controlled history moves are invalid",
    )
    payload[record_offset + 14] = len(moves)
    payload[record_offset + 15] = 1
    payload[record_offset + 16:record_offset + 64] = bytes(48)
    struct.pack_into(
        f"<{len(moves)}H",
        payload,
        record_offset + 16,
        *moves,
    )
    return index


def make_controlled_raw(
    baseline_raw: bytes,
) -> tuple[bytes, bytes, int, int, bytes, dict[str, object]]:
    raw = bytearray(baseline_raw)
    copies = PARTY.valid_normal_copies(baseline_raw)
    require(copies, "immutable fixture has no valid normal save copy")
    active_counter, active_base = PARTY.active_copy(baseline_raw)

    for _, base in copies:
        start = base + PARTY.PARTY_OFFSET + 8 + TARGET_SLOT * 0xEC
        record = bytes(raw[start:start + 0xEC])
        raw[start:start + 0xEC] = controlled_party_record(record)
        footer = base + PARTY.NORMAL_SAVE_SIZE - 0x10
        crc = PARTY.crc16_ccitt_false(bytes(raw[base:footer]))
        struct.pack_into("<H", raw, footer + 0x0E, crc)

    controlled_party = bytes(
        raw[
            active_base + PARTY.PARTY_OFFSET:
            active_base + PARTY.PARTY_OFFSET + PARTY.PARTY_SIZE
        ]
    )
    validate_all_party_checksums(controlled_party)
    target = party_record(controlled_party, TARGET_SLOT)
    target_payload, moves, pp, pp_ups = record_payload(target)
    require(moves == CONTROLLED_MOVES, "controlled moves were not encoded")
    require(
        pp[TARGET_REPLACEMENT_SLOT] == 1
        and pp_ups[TARGET_REPLACEMENT_SLOT] == 2,
        "controlled depleted-PP/PP-Up precondition was not encoded",
    )
    pid = struct.unpack_from("<I", target)[0]
    growth = PARTY.SUBSTRUCT_OFFSETS[(pid & 0x3E000) >> 13][0]
    ot_id = struct.unpack_from("<I", target_payload, growth + 4)[0]

    target_box = controlled_box_record(
        target,
        ot_id_xor=BOX_TARGET_OT_ID_XOR,
        moves=CONTROLLED_MOVES,
        pp=CONTROLLED_PP,
        pp_ups=CONTROLLED_PP_UPS,
    )
    switch_source = party_record(controlled_party, 3)
    _, switch_moves, switch_pp, switch_pp_ups = record_payload(switch_source)
    switch_box = controlled_box_record(
        switch_source,
        ot_id_xor=BOX_SWITCH_OT_ID_XOR,
        moves=switch_moves,
        pp=switch_pp,
        pp_ups=switch_pp_ups,
    )
    target_box_identity = box_identity(target_box)
    switch_box_identity = box_identity(switch_box)
    require(
        target_box_identity[:2] != (pid, ot_id)
        and switch_box_identity[:2] != (pid, ot_id)
        and target_box_identity[:2] != switch_box_identity[:2],
        "controlled boxed identities are not distinct",
    )
    pc_copies = valid_pc_copies(baseline_raw)
    require(
        len(pc_copies) == len(PARTY.SAVE_COPY_BASES),
        "immutable fixture does not have both valid PC generations",
    )
    for _, base in pc_copies:
        box_start = base + PC_SAVE_OFFSET
        raw[
            box_start + BOX_TARGET_SLOT * PC_MON_SIZE:
            box_start + (BOX_TARGET_SLOT + 1) * PC_MON_SIZE
        ] = target_box
        raw[
            box_start + BOX_SWITCH_SLOT * PC_MON_SIZE:
            box_start + (BOX_SWITCH_SLOT + 1) * PC_MON_SIZE
        ] = switch_box
        struct.pack_into("<I", raw, box_start + PC_ACTIVE_BOX_OFFSET, 0)
        struct.pack_into("<I", raw, box_start + PC_MODIFIED_FLAGS_OFFSET, 0)
        footer = base + PC_SAVE_OFFSET + PC_SAVE_SIZE - PC_FOOTER_SIZE
        crc = PARTY.crc16_ccitt_false(
            bytes(raw[base + PC_SAVE_OFFSET:footer])
        )
        struct.pack_into("<H", raw, footer + 0x0E, crc)
    require(
        len(valid_pc_copies(bytes(raw))) == len(PARTY.SAVE_COPY_BASES),
        "controlled PC generations are not authenticated",
    )

    valid_images = []
    for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS):
        image = baseline_raw[offset:offset + HISTORY_IMAGE_SIZE]
        if valid_history_image(image, mirror):
            valid_images.append(image)
    require(valid_images, "immutable fixture has no valid history mirror")
    payload = bytearray(valid_images[0][:HISTORY_FOOTER_OFFSET])
    seed_history_record(
        payload,
        target[:PC_MON_SIZE],
        CONTROLLED_HISTORY_MOVES,
    )
    target_box_history_index = seed_history_record(
        payload,
        target_box,
        CONTROLLED_HISTORY_MOVES,
    )
    switch_box_history_index = seed_history_record(
        payload,
        switch_box,
        tuple(move for move in switch_moves if move != 0),
    )
    for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS):
        counter = (
            active_counter
            if mirror == 0
            else (active_counter - 1) & 0xFFFFFFFF
        )
        image = history_image_for_mirror(bytes(payload), mirror, counter)
        raw[offset:offset + HISTORY_IMAGE_SIZE] = image
    controlled_raw = bytes(raw)
    _, active_pc_base = active_pc_copy(controlled_raw)
    active_target = pc_box_record(
        controlled_raw, active_pc_base, 0, BOX_TARGET_SLOT
    )
    active_switch = pc_box_record(
        controlled_raw, active_pc_base, 0, BOX_SWITCH_SLOT
    )
    require(
        active_target == target_box and active_switch == switch_box,
        "controlled active PC generation differs",
    )
    return (
        controlled_raw,
        controlled_party,
        pid,
        ot_id,
        bytes(payload),
        {
            "active_base": active_pc_base,
            "target": target_box,
            "switch": switch_box,
            "target_identity": target_box_identity,
            "switch_identity": switch_box_identity,
            "target_history_index": target_box_history_index,
            "switch_history_index": switch_box_history_index,
        },
    )


def assert_cancel_exact(
    emu: DeSmuME,
    expected_party: bytes,
    expected_metadata: bytes,
    expected_history: bytes,
    label: str,
) -> None:
    actual_party, _ = PARTY.wait_for_runtime_party(
        emu,
        expected_party,
        maximum_frames=90,
    )
    metadata, history = runtime_history(emu)
    if actual_party != expected_party:
        differences = [
            index
            for index, (old, new) in enumerate(
                zip(expected_party, actual_party)
            )
            if old != new
        ]
        raise RuntimeError(
            f"{label} changed party bytes at "
            + ",".join(f"0x{index:X}" for index in differences[:32])
        )
    require(metadata == expected_metadata, f"{label} changed history metadata")
    require(history == expected_history, f"{label} changed history records")


def assert_box_cancel_exact(
    emu: DeSmuME,
    expected_target: bytes,
    expected_switch: bytes,
    expected_metadata: bytes,
    expected_history: bytes,
    label: str,
) -> None:
    actual_target = runtime_box_record(emu, 0, BOX_TARGET_SLOT)
    actual_switch = runtime_box_record(emu, 0, BOX_SWITCH_SLOT)
    require(actual_target == expected_target, f"{label} changed boxed target")
    require(actual_switch == expected_switch, f"{label} changed boxed switch peer")
    require(
        runtime_pc_modified_flags(emu) == 0,
        f"{label} dirtied PC storage before a committed replacement",
    )
    metadata, history = runtime_history(emu)
    require(metadata == expected_metadata, f"{label} changed history metadata")
    require(history == expected_history, f"{label} changed history records")


def normal_save(emu: DeSmuME, baseline_counter: int) -> None:
    # Summary B -> party, party B -> active start menu, then retail SAVE.
    tap(emu, "B", 150)
    tap(emu, "B", 120)
    tap(emu, "RIGHT", 36)
    tap(emu, "A", 90)
    tap(emu, "A", 60)
    tap(emu, "A", 90)
    for _ in range(8):
        tap(emu, "A", 120)
        if PARTY.save_counter_compare(
            PARTY.read_runtime_save_counter(emu),
            baseline_counter,
        ) > 0:
            break
    require(
        PARTY.save_counter_compare(
            PARTY.read_runtime_save_counter(emu),
            baseline_counter,
        ) > 0,
        "key-only retail save did not advance the normal save counter",
    )
    HEADLESS.cycle(emu, 600)


def open_summary_moves(emu: DeSmuME, party_slot: int) -> None:
    tap(emu, "X", 20)
    tap(emu, "A", 100)
    # The fixture party menu uses a two-column grid (0/1, 2/3, 4/5).
    for _ in range(party_slot // 2):
        tap(emu, "DOWN", 20)
    if party_slot % 2:
        tap(emu, "RIGHT", 20)
    tap(emu, "A", 30)
    tap(emu, "A", 100)
    tap(emu, "RIGHT", 80)


def hold(emu: DeSmuME, key: str, frames: int, gap: int = 20) -> None:
    HEADLESS.hold_key(emu, key, frames, gap)


def open_retail_pc_storage_menu(
    emu: DeSmuME,
    *,
    terminal_boot: bool = False,
) -> None:
    if not terminal_boot:
        # Key-only route from the immutable fixture through the actual Center
        # warp, followed by the east aisle that avoids the moving NPC at
        # T21PC0101 (11,16).
        for key, frames in (
            ("LEFT", 90),
            ("DOWN", 150),
            ("RIGHT", 60),
            ("DOWN", 100),
            ("LEFT", 140),
            ("UP", 60),
            ("LEFT", 90),
            ("UP", 140),
        ):
            hold(emu, key, frames, 12)
        HEADLESS.cycle(emu, 300)
        for key, frames in (
            ("UP", 30),
            ("RIGHT", 60),
            ("UP", 60),
            ("LEFT", 15),
        ):
            hold(emu, key, frames)
    else:
        # The boxed post-save reload was retail-saved at the same interaction
        # tile, so only restore the facing direction.
        HEADLESS.cycle(emu, 120)
    tap(emu, "UP", 20)
    tap(emu, "A", 80)

    # Boot text -> owner selection -> Someone's PC introduction.
    for _ in range(4):
        tap(emu, "A", 60)
    tap(emu, "A", 80)
    for _ in range(3):
        tap(emu, "A", 80)


def open_retail_pc_move_ui(
    emu: DeSmuME,
    *,
    terminal_boot: bool = False,
) -> None:
    open_retail_pc_storage_menu(emu, terminal_boot=terminal_boot)
    # The storage menu starts on Deposit. Down selects Move Pokémon.
    tap(emu, "DOWN", 30)
    tap(emu, "A", 180)


def open_retail_box_summary_moves(
    emu: DeSmuME,
    screenshot_root: Path,
    prefix: str,
    *,
    terminal_boot: bool = False,
) -> tuple[int, list[str]]:
    captures: list[str] = []
    open_retail_pc_move_ui(emu, terminal_boot=terminal_boot)
    captures.append(
        screenshot(emu, screenshot_root, f"{prefix}_pc_move_ui.png")
    )

    # Touch the actual first boxed record, then its retail Summary command.
    touch(emu, 16, 56, 60)
    touch(emu, 210, 76, 180)
    captures.append(
        screenshot(emu, screenshot_root, f"{prefix}_pc_summary_info.png")
    )
    hold(emu, "RIGHT", 5, 100)
    captures.append(
        screenshot(emu, screenshot_root, f"{prefix}_pc_summary_moves.png")
    )
    state = locate_inactive_summary_state(
        emu,
        moves=box_record_payload(
            runtime_box_record(emu, 0, BOX_TARGET_SLOT)
        )[1],
        owner_pos=BOX_TARGET_SLOT,
        data_type=2,
    )
    return state, captures


def exit_pc_and_retail_save(
    emu: DeSmuME,
    baseline_counter: int,
) -> None:
    # Context menu -> box UI -> "Continue Box operations?" -> No.
    tap(emu, "B", 60)
    tap(emu, "B", 60)
    tap(emu, "DOWN", 20)
    tap(emu, "A", 180)
    # Storage operation menu -> See Ya; PC owner menu -> Switch Off.
    touch(emu, 190, 145, 180)
    touch(emu, 100, 146, 180)
    retail_save_from_field(emu, baseline_counter)


def retail_save_from_field(
    emu: DeSmuME,
    baseline_counter: int,
) -> None:
    # Retail field Save touch, text advance, explicit Yes, and completion.
    touch(emu, 125, 80, 120)
    tap(emu, "A", 90)
    tap(emu, "A", 60)
    tap(emu, "A", 90)
    for _ in range(8):
        tap(emu, "A", 120)
        if (
            PARTY.save_counter_compare(
                PARTY.read_runtime_save_counter(emu),
                baseline_counter,
            )
            > 0
        ):
            break
    require(
        PARTY.save_counter_compare(
            PARTY.read_runtime_save_counter(emu),
            baseline_counter,
        )
        > 0,
        "retail save did not advance the normal save counter",
    )
    # The counter becomes visible before all backup pages finish writing.
    HEADLESS.cycle(emu, 2000)
    # Retail returns to the still-open field menu after saving. Close it so a
    # derived bootstrap always resumes in the overworld, never by navigating
    # a persisted menu with what are intended to be movement keys.
    tap(emu, "B", 120)


def new_emulator(
    rom: Path,
    raw: bytes,
) -> tuple[DeSmuME, tempfile.NamedTemporaryFile]:
    emu = DeSmuME()
    emu.volume_set(0)
    emu.open(str(rom))
    imported = tempfile.NamedTemporaryFile(suffix=".sav")
    PARTY.import_raw(emu, raw, imported)
    HEADLESS.boot_to_ready(boot_arguments(), emu)
    return emu, imported


def close_emulator(
    emu: DeSmuME,
    imported: tempfile.NamedTemporaryFile,
) -> None:
    emu.destroy()
    imported.close()


def selected_persisted_history(
    raw: bytes,
) -> tuple[int, int, bytes]:
    main_counter, _ = PARTY.active_copy(raw)
    valid: list[tuple[int, int, bytes]] = []
    for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS):
        image = raw[offset:offset + HISTORY_IMAGE_SIZE]
        if not valid_history_image(image, mirror):
            continue
        counter = struct.unpack_from("<I", image, HISTORY_FOOTER_OFFSET + 4)[0]
        if PARTY.save_counter_compare(counter, main_counter) <= 0:
            valid.append((counter, mirror, image))
    require(valid, "saved raw has no eligible authenticated history mirror")
    selected = valid[0]
    for candidate in valid[1:]:
        if PARTY.save_counter_compare(candidate[0], selected[0]) > 0:
            selected = candidate
    return selected


def assert_pp_pixels(path: Path) -> dict[str, object]:
    from PIL import Image

    image = Image.open(path).convert("RGB")
    # Candidate row 0's current/max PP glyphs on the combined 256x384 frame.
    crop = image.crop((84, 217, 112, 234))
    colors = crop.getcolors(maxcolors=2048) or []
    require(
        len(colors) >= 3,
        "candidate PP pixel crop lacks rendered text variation",
    )
    dark = sum(
        count
        for count, color in colors
        if max(color) - min(color) < 40 and sum(color) < 360
    )
    require(dark >= 4, "candidate PP crop lacks visible dark glyph pixels")
    return {
        "crop": [84, 217, 112, 234],
        "distinct_colors": len(colors),
        "dark_pixels": dark,
        "sha256": hashlib.sha256(crop.tobytes()).hexdigest(),
    }


def assert_control_pixels(
    path: Path,
    *,
    label: str,
    a_span: tuple[int, int],
    gap_span: tuple[int, int],
    b_span: tuple[int, int],
) -> dict[str, object]:
    from PIL import Image

    image = Image.open(path).convert("RGB")

    def dark_pixels(left: int, right: int) -> int:
        crop = image.crop((left, 192 + 139, right, 192 + 151))
        return sum(
            1
            for red, green, blue in crop.getdata()
            if max(red, green, blue) - min(red, green, blue) < 55
            and red + green + blue < 450
        )

    a_dark = dark_pixels(*a_span)
    gap_dark = dark_pixels(*gap_span)
    b_dark = dark_pixels(*b_span)
    require(a_dark > 0, f"{label} A/OK pixels are absent")
    require(gap_dark == 0, f"{label} dead gap contains glyph pixels")
    require(b_dark > 0, f"{label} Back-edge pixels are absent")
    return {
        "label": label,
        "y": [139, 151],
        "a_span": list(a_span),
        "gap_span": list(gap_span),
        "b_span": list(b_span),
        "a_dark_pixels": a_dark,
        "gap_dark_pixels": gap_dark,
        "b_dark_pixels": b_dark,
        "capture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def run_reload_probe(
    rom: Path,
    raw_path: Path,
    screenshot_path: Path,
) -> dict[str, object]:
    raw = raw_path.read_bytes()
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    with HEADLESS.silence_native_output(True):
        emu, imported = new_emulator(rom, raw)
        try:
            _, _, expected_party = PARTY.party_image(raw)
            party, _ = PARTY.wait_for_runtime_party(
                emu, expected_party, maximum_frames=90
            )
            require(
                party == expected_party,
                "reload probe runtime party differs from persisted bytes",
            )
            metadata, history = runtime_history(emu)
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot(emu, screenshot_path.parent, screenshot_path.name)
        finally:
            close_emulator(emu, imported)
    return {
        "party": party.hex(),
        "metadata": metadata.hex(),
        "history": history.hex(),
    }


def fresh_reload_evidence(
    rom: Path,
    raw_path: Path,
    screenshot_path: Path,
) -> tuple[bytes, bytes, bytes]:
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--rom",
            str(rom),
            "--probe-raw",
            str(raw_path),
            "--probe-screenshot",
            str(screenshot_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    require(
        completed.returncode == 0,
        "fresh reload probe failed: " + completed.stderr[-1000:],
    )
    probe = json.loads(completed.stdout)
    return (
        bytes.fromhex(probe["party"]),
        bytes.fromhex(probe["metadata"]),
        bytes.fromhex(probe["history"]),
    )


def run_isolated_scenario(
    rom: Path,
    raw_path: Path,
    name: str,
    screenshot_path: Path,
) -> dict[str, object]:
    raw = raw_path.read_bytes()
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    with HEADLESS.silence_native_output(True):
        emu, imported = new_emulator(rom, raw)
        try:
            _, _, expected_party = PARTY.party_image(raw)
            party, _ = PARTY.wait_for_runtime_party(
                emu, expected_party, maximum_frames=90
            )
            require(party == expected_party, f"{name} boot party differs")
            metadata, history = runtime_history(emu)
            require(metadata[4] == 0, f"{name} did not boot clean history")
            if name == "empty":
                open_summary_moves(emu, 0)
                party = wait_party_locked(emu)
                metadata, history = runtime_history(emu)
                _, moves, _, _ = record_payload(party_record(party, 0))
                touch(emu, 40, 140, 60)
                state = locate_summary_relearn_state(
                    emu, moves, owner_pos=0, minimum_candidates=0
                )
                summary_state_evidence(
                    emu, state, 2, 0, "natural empty candidate list"
                )
                require(
                    read_u16(
                        emu,
                        state + SUMMARY_STATE_CANDIDATE_COUNT_OFFSET,
                    )
                    == 0,
                    "empty mode retained candidates",
                )
                touch(emu, 220, 176, 50)
                summary_state_evidence(
                    emu, state, 0, 0, "touch empty Back"
                )
                detail = {"mode": 0, "candidate_count": 0}
            elif name == "keys":
                open_summary_moves(emu, TARGET_SLOT)
                party, _ = PARTY.wait_for_runtime_party(
                    emu, expected_party, maximum_frames=90
                )
                metadata, history = runtime_history(emu)
                inactive = locate_inactive_summary_state(emu)
                transitions: list[dict[str, object]] = []

                tap(emu, "X", 12)
                state = locate_summary_relearn_state(emu)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 1, 0, "key X entry"
                    )
                )
                initial = assert_candidate_viewport(
                    emu, state, 0, 0, "key X candidate list"
                )
                require(
                    initial["candidates"] == CONTROLLED_CANDIDATES,
                    "key-only candidate order differs",
                )
                assert_cancel_exact(
                    emu, party, metadata, history, "key X entry"
                )

                tap(emu, "A", 12)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 3, 0, "key A list to slot"
                    )
                )
                assert_prospective_slot(
                    emu, state, 0, "key A initial slot preview"
                )
                tap(emu, "B", 12)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 1, 0, "key B slot to list"
                    )
                )
                assert_cancel_exact(
                    emu, party, metadata, history, "key B slot cancel"
                )

                tap(emu, "A", 12)
                for selected in (1, 2, 3):
                    tap(emu, "DOWN", 12)
                    assert_prospective_slot(
                        emu,
                        state,
                        selected,
                        f"key DOWN slot {selected}",
                    )
                tap(emu, "A", 12)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 4, 0, "key A slot to confirmation"
                    )
                )
                tap(emu, "B", 12)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 3, 0, "key B confirmation to slot"
                    )
                )
                assert_cancel_exact(
                    emu, party, metadata, history, "key B confirmation cancel"
                )

                tap(emu, "B", 12)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 1, 0, "key B slot to list again"
                    )
                )
                tap(emu, "A", 12)
                for _ in range(3):
                    tap(emu, "DOWN", 12)
                tap(emu, "A", 12)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 4, 0, "key A confirmation before success"
                    )
                )
                assert_cancel_exact(
                    emu, party, metadata, history, "key confirmation pending"
                )
                tap(emu, "A", 20)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 6, 1, "key A confirmed success"
                    )
                )
                changed_party = wait_party_locked(emu)
                _, changed_moves, changed_pp, changed_pp_ups = record_payload(
                    party_record(changed_party, TARGET_SLOT)
                )
                require(
                    changed_moves == (57, 48, 352, TARGET_MOVE)
                    and changed_pp[TARGET_REPLACEMENT_SLOT] == 8
                    and changed_pp_ups[TARGET_REPLACEMENT_SLOT] == 0,
                    "key-only confirmed replacement differs",
                )
                changed_metadata, changed_history = runtime_history(emu)
                require(
                    changed_metadata[4] == 1
                    and changed_history != history,
                    "key-only success did not update history",
                )
                tap(emu, "B", 20)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 0, 1, "key B dismisses success"
                    )
                )
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                screenshot(emu, screenshot_path.parent, screenshot_path.name)
                return {
                    "label": name,
                    "entry_state": f"0x{inactive:08X}",
                    "transitions": transitions,
                    "candidate_order": list(initial["candidates"]),
                    "cancel_party_exact": True,
                    "cancel_history_exact": True,
                    "confirmed_moves": list(changed_moves),
                    "confirmed_pp": list(changed_pp),
                    "confirmed_pp_ups": list(changed_pp_ups),
                    "history_dirty_after_confirm": changed_metadata[4],
                }
            elif name == "party_switch":
                open_summary_moves(emu, TARGET_SLOT)
                party, _ = PARTY.wait_for_runtime_party(
                    emu, expected_party, maximum_frames=90
                )
                metadata, history = runtime_history(emu)
                tap(emu, "X", 20)
                state = locate_summary_relearn_state(emu)
                initial = candidate_state(emu, state)
                original_owner_pokemon = read_u32(
                    emu, state + SUMMARY_STATE_OWNER_POKEMON_OFFSET
                )
                switches: list[dict[str, object]] = []

                # The retail party icon hitboxes are actions 4..9. Slot 3 is
                # the right icon in the middle row and has no candidates.
                touch(emu, 224, 92, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=3, expected_mode=2
                )
                switched_candidates = candidate_state(emu, state)
                require(
                    read_u32(
                        emu,
                        state + SUMMARY_STATE_OWNER_POKEMON_OFFSET,
                    )
                    != original_owner_pokemon,
                    "party list switch retained the old BoxPokemon owner",
                )
                require(
                    switched_candidates["candidates"] == (),
                    "party list switch did not rebuild the peer empty state",
                )
                switches.append({"from_mode": 1, **switched})
                assert_cancel_exact(
                    emu,
                    party,
                    metadata,
                    history,
                    "party list real switch",
                )

                # Slot 2 is the left icon in the middle retail party row.
                touch(emu, 184, 84, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=TARGET_SLOT, expected_mode=1
                )
                require(
                    candidate_state(emu, state)["candidates"]
                    == initial["candidates"],
                    "party slot-state switch did not rebuild target candidates",
                )
                switches.append({"from_mode": 2, **switched})
                assert_cancel_exact(
                    emu,
                    party,
                    metadata,
                    history,
                    "party empty-state real switch",
                )

                tap(emu, "A", 12)
                require(
                    read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET) == 3,
                    "party target did not enter slot mode",
                )
                touch(emu, 224, 92, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=3, expected_mode=2
                )
                require(
                    candidate_state(emu, state)["candidates"] == (),
                    "party slot-state switch retained target candidates",
                )
                switches.append({"from_mode": 3, **switched})
                assert_cancel_exact(
                    emu,
                    party,
                    metadata,
                    history,
                    "party slot real switch",
                )

                touch(emu, 184, 84, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=TARGET_SLOT, expected_mode=1
                )
                require(
                    candidate_state(emu, state)["candidates"]
                    == initial["candidates"],
                    "party empty-state return did not rebuild target",
                )
                switches.append({"from_mode": 2, **switched})
                assert_cancel_exact(
                    emu,
                    party,
                    metadata,
                    history,
                    "party empty-state return",
                )

                tap(emu, "A", 12)
                for _ in range(3):
                    tap(emu, "DOWN", 8)
                tap(emu, "A", 12)
                require(
                    read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET) == 4,
                    "party target did not enter confirmation mode",
                )
                touch(emu, 224, 92, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=3, expected_mode=2
                )
                require(
                    candidate_state(emu, state)["candidates"] == (),
                    "party confirmation-state switch did not rebuild peer",
                )
                switches.append({"from_mode": 4, **switched})
                assert_cancel_exact(
                    emu,
                    party,
                    metadata,
                    history,
                    "party confirmation real switch",
                )
                tap(emu, "B", 20)
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                screenshot(emu, screenshot_path.parent, screenshot_path.name)
                return {
                    "label": name,
                    "switches": switches,
                    "initial_candidates": list(initial["candidates"]),
                    "peer_candidates": list(
                        switched_candidates["candidates"]
                    ),
                    "old_transactions_cancelled_exact": True,
                    "party_exact": True,
                    "history_exact": True,
                    "dirty": metadata[4],
                }
            elif name == "center_bootstrap":
                baseline_counter, _ = PARTY.active_copy(raw)
                for key, frames in (
                    ("LEFT", 90),
                    ("DOWN", 150),
                    ("RIGHT", 60),
                    ("DOWN", 100),
                    ("LEFT", 140),
                    ("UP", 60),
                    ("LEFT", 90),
                    ("UP", 140),
                ):
                    hold(emu, key, frames, 12)
                HEADLESS.cycle(emu, 300)
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                screenshot(emu, screenshot_path.parent, screenshot_path.name)
                retail_save_from_field(emu, baseline_counter)
                exported = screenshot_path.with_suffix(".sav")
                require(
                    emu.backup.export_file(str(exported)),
                    "could not export retail Center bootstrap",
                )
                saved_raw = PARTY.extract_raw_save(exported)
                saved_counter, saved_base = PARTY.active_copy(saved_raw)
                location = struct.unpack_from(
                    "<5i",
                    saved_raw,
                    saved_base + LOCAL_FIELD_DATA_OFFSET,
                )
                require(
                    location[:4] == (69, -1, 8, 19),
                    f"retail Center bootstrap location differs: {location}",
                )
                return {
                    "label": name,
                    "retail_save": True,
                    "location": list(location),
                    "generation": saved_counter,
                    "normal_copies_authenticated": len(
                        PARTY.valid_normal_copies(saved_raw)
                    ),
                    "exported_raw_save": str(exported),
                    "capture": str(screenshot_path),
                }
            elif name == "terminal_bootstrap":
                baseline_counter, _ = PARTY.active_copy(raw)
                for key, frames in (
                    ("UP", 30),
                    ("RIGHT", 30),
                    ("RIGHT", 30),
                    ("UP", 60),
                    ("LEFT", 15),
                ):
                    hold(emu, key, frames, 60)
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                screenshot(emu, screenshot_path.parent, screenshot_path.name)
                retail_save_from_field(emu, baseline_counter)
                exported = screenshot_path.with_suffix(".sav")
                require(
                    emu.backup.export_file(str(exported)),
                    "could not export retail terminal bootstrap",
                )
                saved_raw = PARTY.extract_raw_save(exported)
                saved_counter, saved_base = PARTY.active_copy(saved_raw)
                location = struct.unpack_from(
                    "<5i",
                    saved_raw,
                    saved_base + LOCAL_FIELD_DATA_OFFSET,
                )
                require(
                    location[:4] == (69, -1, 11, 13),
                    f"retail terminal bootstrap location differs: {location}",
                )
                return {
                    "label": name,
                    "retail_save": True,
                    "location": list(location),
                    "generation": saved_counter,
                    "normal_copies_authenticated": len(
                        PARTY.valid_normal_copies(saved_raw)
                    ),
                    "exported_raw_save": str(exported),
                    "capture": str(screenshot_path),
                }
            elif name == "transfer":
                baseline_counter, _ = PARTY.active_copy(raw)
                baseline_pc_counter, baseline_pc_base = active_pc_copy(raw)
                _, baseline_count, baseline_party = PARTY.party_image(raw)
                require(
                    baseline_count == 5,
                    "transfer input does not have one empty party slot",
                )
                expected_target = pc_box_record(
                    raw, baseline_pc_base, 0, BOX_TARGET_SLOT
                )
                target_pid, target_ot_id, target_species = box_identity(
                    expected_target
                )
                require(
                    target_species == TARGET_SPECIES,
                    "transfer input does not contain the boxed target",
                )
                metadata, initial_history = runtime_history(emu)
                history_index, _, initial_history_moves = find_history_record(
                    initial_history, target_pid, target_ot_id
                )
                require(
                    metadata[4] == 0
                    and initial_history_moves.count(TARGET_MOVE) == 1,
                    "transfer input history is not clean and singular",
                )
                captures: list[str] = []

                # Retail Withdraw: the storage menu starts on Deposit, and its
                # right-hand item is Withdraw. Box1 starts on slot zero and the
                # first context command is the canonical WITHDRAW operation.
                open_retail_pc_storage_menu(emu, terminal_boot=True)
                tap(emu, "RIGHT", 30)
                tap(emu, "A", 180)
                tap(emu, "A", 60)
                touch(emu, 210, 76, 180)
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_withdrawn.png",
                    )
                )
                withdrawn_party = wait_party_locked(emu)
                require(
                    struct.unpack_from("<i", withdrawn_party, 4)[0] == 6,
                    "retail Withdraw did not append party slot 5",
                )
                withdrawn_box = runtime_box_record(
                    emu, 0, BOX_TARGET_SLOT
                )
                require(
                    box_identity(withdrawn_box)[2] == 0,
                    "retail Withdraw did not empty Box1 slot 0",
                )
                withdrawn_target = party_record(withdrawn_party, 5)
                require(
                    box_identity(withdrawn_target[:PC_MON_SIZE])[:2]
                    == (target_pid, target_ot_id),
                    "retail Withdraw changed the target PID/OTID",
                )
                withdrawn_metadata, withdrawn_history = runtime_history(emu)
                require(
                    withdrawn_metadata[4] == 0
                    and withdrawn_history == initial_history,
                    "retail Withdraw dirtied or changed move history",
                )

                # Exit Withdraw mode and the PC, then view the moved identity
                # through the actual party Summary and rebuild its candidates.
                tap(emu, "B", 60)
                tap(emu, "DOWN", 20)
                tap(emu, "A", 180)
                touch(emu, 190, 145, 180)
                touch(emu, 100, 146, 180)
                open_summary_moves(emu, 5)
                party_state = locate_inactive_summary_state(
                    emu,
                    moves=record_payload(withdrawn_target)[1],
                    owner_pos=5,
                    data_type=1,
                )
                tap(emu, "X", 30)
                withdrawn_candidates = candidate_state(emu, party_state)
                require(
                    withdrawn_candidates["candidates"]
                    == PERSISTED_CANDIDATES,
                    "party Summary candidate order did not follow transfer",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_party_summary.png",
                    )
                )
                tap(emu, "B", 30)
                tap(emu, "B", 30)
                wait_overlay_active(
                    emu, SUMMARY_RELEARN_OVERLAY_ID, False
                )
                HEADLESS.cycle(emu, 120)
                tap(emu, "B", 120)
                tap(emu, "B", 120)

                # Retail Deposit: reopen the same terminal, choose Deposit,
                # select party slot 5, and use the first DEPOSIT command.
                open_retail_pc_storage_menu(emu, terminal_boot=True)
                touch(emu, 64, 48, 180)
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_deposit_party.png",
                    )
                )
                tap(emu, "DOWN", 30)
                tap(emu, "DOWN", 30)
                tap(emu, "RIGHT", 30)
                tap(emu, "A", 60)
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_deposit_context.png",
                    )
                )
                touch(emu, 210, 76, 180)
                tap(emu, "A", 180)
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_deposited.png",
                    )
                )
                deposited_party = wait_party_locked(emu)
                require(
                    deposited_party == baseline_party,
                    "retail Deposit did not restore the party byte-exact",
                )
                deposited_target = runtime_box_record(
                    emu, 0, BOX_TARGET_SLOT
                )
                require(
                    deposited_target == expected_target,
                    "retail Deposit did not restore Box1 slot 0 byte-exact",
                )
                require(
                    runtime_pc_modified_flags(emu) & 1,
                    "retail Withdraw/Deposit did not mark Box1 dirty",
                )
                deposited_metadata, deposited_history = runtime_history(emu)
                require(
                    deposited_metadata[4] == 0
                    and deposited_history == initial_history,
                    "retail Deposit dirtied or changed move history",
                )

                tap(emu, "B", 60)
                tap(emu, "DOWN", 20)
                tap(emu, "A", 180)
                touch(emu, 190, 145, 180)
                touch(emu, 100, 146, 180)
                retail_save_from_field(emu, baseline_counter)
                exported = screenshot_path.with_suffix(".sav")
                require(
                    emu.backup.export_file(str(exported)),
                    "could not export retail transfer save",
                )
                saved_raw = PARTY.extract_raw_save(exported)
                saved_counter, saved_count, saved_party = PARTY.party_image(
                    saved_raw
                )
                saved_pc_counter, saved_pc_base = active_pc_copy(saved_raw)
                require(
                    PARTY.save_counter_compare(
                        saved_counter, baseline_counter
                    )
                    > 0
                    and PARTY.save_counter_compare(
                        saved_pc_counter, baseline_pc_counter
                    )
                    > 0,
                    "retail transfer save did not advance save ownership",
                )
                require(
                    saved_count == 5 and saved_party == baseline_party,
                    "retail transfer save changed the restored party",
                )
                require(
                    saved_raw[
                        saved_pc_base + PC_SAVE_OFFSET:
                        saved_pc_base
                        + PC_SAVE_OFFSET
                        + PC_STORAGE_BOXES_SIZE
                    ]
                    == raw[
                        baseline_pc_base + PC_SAVE_OFFSET:
                        baseline_pc_base
                        + PC_SAVE_OFFSET
                        + PC_STORAGE_BOXES_SIZE
                    ],
                    "retail transfer save changed a boxed record",
                )
                saved_checksums = validate_all_boxed_checksums(
                    saved_raw, saved_pc_base
                )
                validate_all_party_checksums(saved_party)
                _, _, saved_history = selected_persisted_history(saved_raw)
                saved_history_index, _, saved_history_moves = (
                    find_history_record(
                        saved_history, target_pid, target_ot_id
                    )
                )
                require(
                    saved_history == initial_history
                    and saved_history_index == history_index
                    and saved_history_moves.count(TARGET_MOVE) == 1,
                    "retail transfer duplicated or orphaned history",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_after_save.png",
                    )
                )
                return {
                    "label": name,
                    "actual_retail_withdraw_and_deposit": True,
                    "identity": [target_pid, target_ot_id],
                    "party_slot_after_withdraw": 5,
                    "party_candidate_order": list(
                        withdrawn_candidates["candidates"]
                    ),
                    "box_slot_after_deposit": BOX_TARGET_SLOT,
                    "history_record_index": history_index,
                    "history_move_count": saved_history_moves.count(
                        TARGET_MOVE
                    ),
                    "history_unchanged": True,
                    "box1_dirty_before_save": True,
                    "party_restored_exact": True,
                    "all_900_saved_checksums_valid": len(
                        saved_checksums
                    )
                    == 900,
                    "saved_generation": saved_counter,
                    "saved_pc_generation": saved_pc_counter,
                    "exported_raw_save": str(exported),
                    "captures": captures,
                }
            elif name == "boxed":
                baseline_counter, _ = PARTY.active_copy(raw)
                baseline_pc_counter, baseline_pc_base = active_pc_copy(raw)
                expected_target = pc_box_record(
                    raw, baseline_pc_base, 0, BOX_TARGET_SLOT
                )
                expected_switch = pc_box_record(
                    raw, baseline_pc_base, 0, BOX_SWITCH_SLOT
                )
                target_pid, target_ot_id, _ = box_identity(expected_target)
                metadata, history = runtime_history(emu)
                require(metadata[4] == 0, "boxed scenario history is dirty")
                state, captures = open_retail_box_summary_moves(
                    emu,
                    screenshot_path.parent,
                    screenshot_path.stem,
                    terminal_boot=True,
                )
                inactive_summary_evidence(
                    emu, state, "actual PC Summary moves page"
                )
                assert_box_cancel_exact(
                    emu,
                    expected_target,
                    expected_switch,
                    metadata,
                    history,
                    "actual PC Summary entry",
                )
                transitions: list[dict[str, object]] = []

                # Touch entry, scroll deeply, and cancel byte-exact.
                touch(emu, 40, 140, 60)
                initial = assert_candidate_viewport(
                    emu, state, 0, 0, "boxed touch candidate list"
                )
                require(
                    initial["candidates"] == CONTROLLED_CANDIDATES,
                    "boxed candidate acquisition order differs",
                )
                for _ in range(5):
                    tap(emu, "DOWN", 10)
                scrolled = candidate_state(emu, state)
                require(
                    scrolled["cursor"] == 5 and scrolled["top"] == 2,
                    "boxed list did not scroll to the expected deep viewport",
                )
                tap(emu, "B", 30)
                summary_state_evidence(
                    emu, state, 0, 0, "boxed deep-list cancel"
                )
                assert_box_cancel_exact(
                    emu,
                    expected_target,
                    expected_switch,
                    metadata,
                    history,
                    "boxed deep-list cancel",
                )

                # Re-enter by key and use the actual PC next/previous arrows
                # from list, slot, HM, and confirmation states.
                tap(emu, "X", 30)
                initial = assert_candidate_viewport(
                    emu, state, 0, 0, "boxed key candidate list"
                )
                target_owner = read_u32(
                    emu, state + SUMMARY_STATE_OWNER_POKEMON_OFFSET
                )
                require(
                    target_owner
                    == runtime_box_address(emu, 0, BOX_TARGET_SLOT),
                    "boxed Summary target owner is not canonical PC storage",
                )
                for from_mode in (1, 3, 5, 4):
                    if from_mode == 3:
                        tap(emu, "A", 20)
                    elif from_mode == 5:
                        tap(emu, "A", 20)
                        tap(emu, "A", 30)
                    elif from_mode == 4:
                        tap(emu, "A", 20)
                        for _ in range(3):
                            tap(emu, "DOWN", 8)
                        tap(emu, "A", 30)
                    require(
                        read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET)
                        == from_mode,
                        f"boxed pre-switch mode {from_mode} was not reached",
                    )
                    touch(emu, 215, 115, 30)
                    switched = wait_summary_identity(
                        emu,
                        state,
                        expected_pos=BOX_SWITCH_SLOT,
                        expected_mode=2,
                        expected_owner_pokemon=runtime_box_address(
                            emu, 0, BOX_SWITCH_SLOT
                        ),
                    )
                    transitions.append(
                        {"from_mode": from_mode, "to": "empty", **switched}
                    )
                    assert_box_cancel_exact(
                        emu,
                        expected_target,
                        expected_switch,
                        metadata,
                        history,
                        f"boxed mode {from_mode} next switch",
                    )
                    touch(emu, 215, 50, 30)
                    switched_back = wait_summary_identity(
                        emu,
                        state,
                        expected_pos=BOX_TARGET_SLOT,
                        expected_mode=1,
                        expected_owner_pokemon=target_owner,
                    )
                    require(
                        candidate_state(emu, state)["candidates"]
                        == initial["candidates"],
                        f"boxed mode {from_mode} switch retained peer state",
                    )
                    transitions.append(
                        {"from_mode": 2, "to": "list", **switched_back}
                    )

                # Permanent mutation occurs only after this explicit confirm.
                tap(emu, "A", 20)
                for _ in range(3):
                    tap(emu, "DOWN", 8)
                tap(emu, "A", 30)
                tap(emu, "A", 120)
                summary_state_evidence(
                    emu, state, 6, 1, "boxed confirmed replacement"
                )
                changed_target = runtime_box_record(
                    emu, 0, BOX_TARGET_SLOT
                )
                _, changed_moves, changed_pp, changed_pp_ups = (
                    box_record_payload(changed_target)
                )
                require(
                    changed_moves == (57, 48, 352, TARGET_MOVE)
                    and changed_pp[TARGET_REPLACEMENT_SLOT] == 8
                    and changed_pp_ups[TARGET_REPLACEMENT_SLOT] == 0,
                    "boxed replacement move/PP/PP Ups differ",
                )
                validate_box_checksum(changed_target, "runtime boxed target")
                require(
                    runtime_box_record(emu, 0, BOX_SWITCH_SLOT)
                    == expected_switch,
                    "boxed replacement changed the switch peer",
                )
                require(
                    runtime_pc_modified_flags(emu) == 0,
                    "Summary dirtied PC storage before returning to its parent",
                )
                committed_metadata, committed_history = runtime_history(emu)
                history_index, _, history_moves_before = find_history_record(
                    history, target_pid, target_ot_id
                )
                committed_index, _, history_moves_after = find_history_record(
                    committed_history, target_pid, target_ot_id
                )
                require(
                    committed_index == history_index
                    and history_moves_after[
                        :len(history_moves_before)
                    ]
                    == history_moves_before
                    and history_moves_after.count(TARGET_MOVE) == 1,
                    "boxed replacement did not update one identity record once",
                )
                for index, (old, new) in enumerate(
                    zip(
                        history_records(history),
                        history_records(committed_history),
                    )
                ):
                    if index != history_index:
                        require(
                            old == new,
                            f"boxed replacement changed history record {index}",
                        )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_boxed_success.png",
                    )
                )

                # A real switch from success keeps the confirmed write, drops
                # only old modal state, and rebuilds the target without the
                # newly known move when switching back.
                touch(emu, 215, 115, 30)
                wait_summary_identity(
                    emu,
                    state,
                    expected_pos=BOX_SWITCH_SLOT,
                    expected_mode=2,
                )
                touch(emu, 215, 50, 30)
                wait_summary_identity(
                    emu,
                    state,
                    expected_pos=BOX_TARGET_SLOT,
                    expected_mode=1,
                )
                require(
                    TARGET_MOVE
                    not in candidate_state(emu, state)["candidates"],
                    "boxed success switch rebuilt a now-known candidate",
                )
                tap(emu, "B", 30)
                tap(emu, "B", 180)
                require(
                    runtime_pc_modified_flags(emu) & 1,
                    "PC Summary parent did not dirty the active box",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_pc_parent_dirty.png",
                    )
                )
                exit_pc_and_retail_save(emu, baseline_counter)
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_after_save.png",
                    )
                )
                exported = screenshot_path.with_suffix(".sav")
                require(
                    emu.backup.export_file(str(exported)),
                    "DeSmuME could not export boxed post-save battery",
                )
                saved_raw = PARTY.extract_raw_save(exported)
                saved_counter, saved_count, saved_party = PARTY.party_image(
                    saved_raw
                )
                saved_pc_counter, saved_pc_base = active_pc_copy(saved_raw)
                saved_target = pc_box_record(
                    saved_raw, saved_pc_base, 0, BOX_TARGET_SLOT
                )
                saved_switch = pc_box_record(
                    saved_raw, saved_pc_base, 0, BOX_SWITCH_SLOT
                )
                require(
                    PARTY.save_counter_compare(
                        saved_counter, baseline_counter
                    )
                    > 0
                    and PARTY.save_counter_compare(
                        saved_pc_counter, baseline_pc_counter
                    )
                    > 0,
                    "boxed retail save did not publish newer generations",
                )
                require(
                    saved_count == 5
                    and saved_party == expected_party,
                    "boxed path changed one or more party records",
                )
                validate_all_party_checksums(saved_party)
                require(
                    PARTY.summarize_party(saved_party)[4]["shiny"] is True,
                    "boxed path corrupted shiny Pidgey",
                )
                require(
                    saved_target == changed_target
                    and saved_switch == expected_switch,
                    "boxed replacement did not persist exactly",
                )
                for box in range(PC_BOX_COUNT):
                    for slot in range(PC_MONS_PER_BOX):
                        if box == 0 and slot == BOX_TARGET_SLOT:
                            continue
                        require(
                            pc_box_record(
                                saved_raw, saved_pc_base, box, slot
                            )
                            == pc_box_record(
                                raw, baseline_pc_base, box, slot
                            ),
                            f"unrelated PC box {box} slot {slot} changed",
                        )
                saved_checksums = validate_all_boxed_checksums(
                    saved_raw, saved_pc_base
                )
                _, _, persisted_history = selected_persisted_history(
                    saved_raw
                )
                persisted_index, _, persisted_moves = find_history_record(
                    persisted_history, target_pid, target_ot_id
                )
                require(
                    persisted_index == history_index
                    and persisted_moves.count(TARGET_MOVE) == 1,
                    "boxed history did not persist once",
                )
                return {
                    "label": name,
                    "actual_terminal_and_pc_ui": True,
                    "actual_box_summary": True,
                    "switch_transitions": transitions,
                    "candidate_order": list(initial["candidates"]),
                    "confirmed_moves": list(changed_moves),
                    "confirmed_pp": list(changed_pp),
                    "confirmed_pp_ups": list(changed_pp_ups),
                    "pc_parent_dirty_flags": 1,
                    "saved_pc_generation": saved_pc_counter,
                    "all_900_saved_checksums_valid": len(
                        saved_checksums
                    )
                    == 900,
                    "party_exact": True,
                    "shiny_pidgey_valid": True,
                    "history_record_index": history_index,
                    "history_move_count": history_moves_after.count(
                        TARGET_MOVE
                    ),
                    "exported_raw_save": str(exported),
                    "captures": captures,
                }
            elif name == "boxed_reload":
                _, persisted_pc_base = active_pc_copy(raw)
                persisted_target = pc_box_record(
                    raw, persisted_pc_base, 0, BOX_TARGET_SLOT
                )
                _, persisted_moves, persisted_pp, persisted_pp_ups = (
                    box_record_payload(persisted_target)
                )
                require(
                    persisted_moves == (57, 48, 352, TARGET_MOVE)
                    and persisted_pp[TARGET_REPLACEMENT_SLOT] == 8
                    and persisted_pp_ups[TARGET_REPLACEMENT_SLOT] == 0,
                    "boxed reload input lacks the persisted replacement",
                )
                state, captures = open_retail_box_summary_moves(
                    emu,
                    screenshot_path.parent,
                    screenshot_path.stem,
                    terminal_boot=True,
                )
                tap(emu, "X", 30)
                reloaded = candidate_state(emu, state)
                require(
                    TARGET_MOVE not in reloaded["candidates"],
                    "fresh PC Summary still offers the persisted move",
                )
                touch(emu, 215, 115, 30)
                wait_summary_identity(
                    emu,
                    state,
                    expected_pos=BOX_SWITCH_SLOT,
                    expected_mode=2,
                )
                touch(emu, 215, 50, 30)
                wait_summary_identity(
                    emu,
                    state,
                    expected_pos=BOX_TARGET_SLOT,
                    expected_mode=1,
                )
                tap(emu, "B", 30)
                metadata, persisted_history = runtime_history(emu)
                pid, ot_id, _ = box_identity(persisted_target)
                history_index, _, history_moves = find_history_record(
                    persisted_history, pid, ot_id
                )
                require(
                    history_moves.count(TARGET_MOVE) == 1,
                    "fresh reload history duplicated the boxed move",
                )
                _, _, reloaded_party = PARTY.party_image(raw)
                validate_all_party_checksums(reloaded_party)
                reloaded_checksums = validate_all_boxed_checksums(
                    raw, persisted_pc_base
                )
                require(
                    PARTY.summarize_party(reloaded_party)[4]["shiny"] is True,
                    "fresh boxed reload corrupted shiny Pidgey",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_persisted_summary.png",
                    )
                )
                return {
                    "label": name,
                    "actual_terminal_and_pc_ui": True,
                    "actual_box_summary": True,
                    "persisted_moves": list(persisted_moves),
                    "persisted_pp": list(persisted_pp),
                    "persisted_pp_ups": list(persisted_pp_ups),
                    "candidate_order_without_known_move": list(
                        reloaded["candidates"]
                    ),
                    "history_record_index": history_index,
                    "history_move_count": history_moves.count(TARGET_MOVE),
                    "history_dirty": metadata[4],
                    "all_900_checksums_valid": len(reloaded_checksums)
                    == 900,
                    "captures": captures,
                }
            elif name == "transfer_reload":
                _, persisted_pc_base = active_pc_copy(raw)
                persisted_target = pc_box_record(
                    raw, persisted_pc_base, 0, BOX_TARGET_SLOT
                )
                pid, ot_id, species = box_identity(persisted_target)
                require(
                    species == TARGET_SPECIES,
                    "transfer reload lost the boxed target",
                )
                _, count, persisted_party = PARTY.party_image(raw)
                require(
                    count == 5,
                    "transfer reload did not retain the restored party count",
                )
                validate_all_party_checksums(persisted_party)
                persisted_checksums = validate_all_boxed_checksums(
                    raw, persisted_pc_base
                )
                _, _, persisted_history = selected_persisted_history(raw)
                history_index, _, history_moves = find_history_record(
                    persisted_history, pid, ot_id
                )
                require(
                    history_moves.count(TARGET_MOVE) == 1,
                    "transfer reload duplicated or orphaned history",
                )
                state, captures = open_retail_box_summary_moves(
                    emu,
                    screenshot_path.parent,
                    screenshot_path.stem,
                    terminal_boot=True,
                )
                tap(emu, "X", 30)
                reloaded = candidate_state(emu, state)
                require(
                    reloaded["candidates"] == PERSISTED_CANDIDATES,
                    "boxed candidate order changed after transfer reload",
                )
                metadata, runtime_persisted_history = runtime_history(emu)
                require(
                    metadata[4] == 0
                    and runtime_persisted_history == persisted_history,
                    "transfer reload selected dirty or different history",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_continuity.png",
                    )
                )
                return {
                    "label": name,
                    "actual_terminal_and_pc_ui": True,
                    "actual_box_summary": True,
                    "identity": [pid, ot_id],
                    "box_slot": BOX_TARGET_SLOT,
                    "candidate_order": list(reloaded["candidates"]),
                    "history_record_index": history_index,
                    "history_move_count": history_moves.count(TARGET_MOVE),
                    "history_dirty": metadata[4],
                    "all_900_checksums_valid": len(
                        persisted_checksums
                    )
                    == 900,
                    "party_count": count,
                    "captures": captures,
                }
            else:
                require(
                    not overlay_is_active(emu, SUMMARY_RELEARN_OVERLAY_ID),
                    f"{name} overlay 154 active before Summary",
                )
                open_summary_moves(emu, TARGET_SLOT)
                wait_overlay_active(
                    emu, SUMMARY_RELEARN_OVERLAY_ID, True
                )
                party, _ = PARTY.wait_for_runtime_party(
                    emu, expected_party, maximum_frames=90
                )
                metadata, history = runtime_history(emu)
                touch(emu, 40, 140, 40)
                state = locate_summary_relearn_state(emu)
                owner = read_u32(emu, state)
                if name == "identity":
                    sentinel_move = 777
                    write_u16(
                        emu, owner + SUMMARY_BASE_MOVE_OFFSET, sentinel_move
                    )
                    write_u32(emu, state, owner + 4)
                    HEADLESS.cycle(emu, 10)
                    require(
                        read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET) == 0,
                        "pointer identity boundary retained modal state",
                    )
                    require(
                        read_u16(emu, owner + SUMMARY_BASE_MOVE_OFFSET)
                        == sentinel_move,
                        "pointer identity overwrote new-owner move",
                    )
                    detail = {
                        "mode": 0,
                        "new_owner_move_preserved": sentinel_move,
                    }
                elif name == "position":
                    original = read_u16(
                        emu,
                        state + SUMMARY_STATE_ORIGINAL_ARG_MOVE_OFFSET,
                    )
                    write_u8(emu, owner + 0x14, 1)
                    HEADLESS.cycle(emu, 10)
                    require(
                        read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET) == 0,
                        "position boundary retained modal state",
                    )
                    require(
                        read_u16(emu, owner + SUMMARY_BASE_MOVE_OFFSET)
                        == original,
                        "same-owner boundary did not restore args->move",
                    )
                    detail = {
                        "mode": 0,
                        "original_arg_move_restored": original,
                    }
                elif name == "teardown":
                    summary_state_evidence(
                        emu, state, 1, 0, "active before teardown"
                    )
                    tap(emu, "B", 20)
                    summary_state_evidence(
                        emu, state, 0, 0, "modal cancel before Summary exit"
                    )
                    assert_cancel_exact(
                        emu,
                        party,
                        metadata,
                        history,
                        "modal cancel before Summary exit",
                    )
                    tap(emu, "B", 20)
                    first_unload_frames = wait_overlay_active(
                        emu, SUMMARY_RELEARN_OVERLAY_ID, False
                    )
                    HEADLESS.cycle(emu, 150)
                    assert_cancel_exact(
                        emu,
                        party,
                        metadata,
                        history,
                        "real Summary exit",
                    )
                    party_exit_path = screenshot_path.with_name(
                        screenshot_path.stem
                        + "_party_exit"
                        + screenshot_path.suffix
                    )
                    screenshot(
                        emu, party_exit_path.parent, party_exit_path.name
                    )

                    # The returned Party menu retains the selected Pokémon.
                    tap(emu, "A", 30)
                    tap(emu, "A", 100)
                    tap(emu, "RIGHT", 80)
                    wait_overlay_active(
                        emu, SUMMARY_RELEARN_OVERLAY_ID, True
                    )
                    fresh_state = locate_inactive_summary_state(emu)
                    inactive_summary_evidence(
                        emu, fresh_state, "fresh Summary after overlay reload"
                    )
                    require(
                        read_u16(
                            emu,
                            fresh_state
                            + SUMMARY_STATE_CANDIDATE_COUNT_OFFSET,
                        )
                        == 0
                        and read_u16(
                            emu,
                            fresh_state
                            + SUMMARY_STATE_PENDING_MOVE_OFFSET,
                        )
                        == 0,
                        "fresh Summary retained prior modal data",
                    )
                    assert_cancel_exact(
                        emu,
                        party,
                        metadata,
                        history,
                        "fresh Summary after overlay reload",
                    )
                    tap(emu, "X", 20)
                    fresh_state = locate_summary_relearn_state(emu)
                    fresh_view = assert_candidate_viewport(
                        emu,
                        fresh_state,
                        0,
                        0,
                        "reloaded Summary candidate list",
                    )
                    tap(emu, "B", 20)
                    summary_state_evidence(
                        emu,
                        fresh_state,
                        0,
                        0,
                        "reloaded Summary modal cancel",
                    )
                    assert_cancel_exact(
                        emu,
                        party,
                        metadata,
                        history,
                        "reloaded Summary modal cancel",
                    )
                    tap(emu, "B", 20)
                    second_unload_frames = wait_overlay_active(
                        emu, SUMMARY_RELEARN_OVERLAY_ID, False
                    )
                    HEADLESS.cycle(emu, 120)
                    assert_cancel_exact(
                        emu,
                        party,
                        metadata,
                        history,
                        "second real Summary exit",
                    )
                    detail = {
                        "mode_before_exit": 1,
                        "overlay_active_before_exit": True,
                        "first_unload_frames": first_unload_frames,
                        "party_exit_screenshot": str(party_exit_path),
                        "overlay_reloaded": True,
                        "fresh_mode": 0,
                        "fresh_candidate_count": 0,
                        "fresh_pending_move": 0,
                        "reentry_candidate_count": fresh_view["count"],
                        "second_unload_frames": second_unload_frames,
                        "overlay_inactive_after_second_exit": True,
                    }
                else:
                    raise RuntimeError(f"unknown isolated scenario: {name}")
            assert_cancel_exact(
                emu, party, metadata, history, f"{name} scenario"
            )
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot(emu, screenshot_path.parent, screenshot_path.name)
            return {
                "label": name,
                **detail,
                "party_sha256": hashlib.sha256(party).hexdigest(),
                "history_sha256": hashlib.sha256(history).hexdigest(),
                "dirty": metadata[4],
            }
        finally:
            close_emulator(emu, imported)


def isolated_scenario_evidence(
    rom: Path,
    raw_path: Path,
    name: str,
    screenshot_path: Path,
) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--rom",
            str(rom),
            "--probe-raw",
            str(raw_path),
            "--scenario",
            name,
            "--probe-screenshot",
            str(screenshot_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=240
        if name in (
            "center_bootstrap",
            "terminal_bootstrap",
            "transfer",
            "transfer_reload",
            "boxed",
            "boxed_reload",
        )
        else 90,
    )
    require(
        completed.returncode == 0,
        f"{name} subprocess failed: " + completed.stderr[-1000:],
    )
    return json.loads(completed.stdout)


def target_semantic_diff(before: bytes, after: bytes) -> list[int]:
    before_payload, _, _, _ = record_payload(before)
    after_payload, _, _, _ = record_payload(after)
    return [
        index
        for index, (old, new) in enumerate(zip(before_payload, after_payload))
        if old != new
    ]


def run(args: argparse.Namespace) -> dict:
    rom = args.rom.resolve()
    dsv = args.dsv.resolve()
    require(rom.is_file(), f"ROM not found: {rom}")
    require(dsv.is_file(), f"DSV not found: {dsv}")
    source_dsv = dsv.read_bytes()
    source_hash = hashlib.sha256(source_dsv).hexdigest()
    if args.expected_dsv_sha256:
        require(
            source_hash == args.expected_dsv_sha256.lower(),
            f"preserved DSV hash differs: {source_hash}",
        )
    immutable_raw = PARTY.extract_raw_save(dsv)
    (
        controlled_raw,
        baseline_party,
        target_pid,
        target_ot_id,
        controlled_history_payload,
        box_fixture,
    ) = make_controlled_raw(immutable_raw)
    baseline_counter, occupied, checked_party = PARTY.party_image(controlled_raw)
    require(checked_party == baseline_party, "controlled party selection differs")
    require(occupied == 5, f"fixture party count differs: {occupied}")
    baseline_summary = PARTY.summarize_party(baseline_party)
    baseline_checksums = validate_all_party_checksums(baseline_party)
    controlled_pc_counter, controlled_pc_base = active_pc_copy(controlled_raw)
    baseline_box_checksums = validate_all_boxed_checksums(
        controlled_raw, controlled_pc_base
    )
    baseline_target_box = pc_box_record(
        controlled_raw, controlled_pc_base, 0, BOX_TARGET_SLOT
    )
    baseline_switch_box = pc_box_record(
        controlled_raw, controlled_pc_base, 0, BOX_SWITCH_SLOT
    )
    require(
        baseline_target_box == box_fixture["target"]
        and baseline_switch_box == box_fixture["switch"],
        "controlled active boxed records differ from fixture metadata",
    )
    require(
        baseline_summary[4]["shiny"] is True
        and baseline_summary[4]["species"] == 16,
        "fixture shiny Pidgey is missing or invalid",
    )
    before_target = party_record(baseline_party, TARGET_SLOT)
    before_payload, before_moves, before_pp, before_pp_ups = record_payload(
        before_target
    )
    require(
        before_moves == CONTROLLED_MOVES
        and before_pp[TARGET_REPLACEMENT_SLOT] == 1
        and before_pp_ups[TARGET_REPLACEMENT_SLOT] == 2,
        "controlled Tentacool PP/PP-Up precondition differs",
    )

    args.screenshot_dir.mkdir(parents=True, exist_ok=True)
    args.export_raw.parent.mkdir(parents=True, exist_ok=True)
    args.controlled_raw.parent.mkdir(parents=True, exist_ok=True)
    args.controlled_raw.write_bytes(controlled_raw)
    captures: list[str] = []
    state_evidence: list[dict[str, int | str]] = []
    transition_evidence: list[dict[str, object]] = []
    boundary_evidence: list[dict[str, object]] = []
    prospective_evidence: list[dict[str, object]] = []
    control_pixel_evidence: list[dict[str, object]] = []
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    # Main acceptance: every touch/key transition is asserted immediately.
    with HEADLESS.silence_native_output(True):
        emu, imported = new_emulator(rom, controlled_raw)
        try:
            boot_party, _ = PARTY.wait_for_runtime_party(
                emu,
                baseline_party,
                maximum_frames=90,
            )
            require(
                boot_party == baseline_party,
                "boot changed one or more serialized party records",
            )
            captures.append(
                screenshot(emu, args.screenshot_dir, "00_visible_boot.png")
            )

            open_summary_moves(emu, TARGET_SLOT)
            captures.append(
                screenshot(emu, args.screenshot_dir, "01_moves_prompt.png")
            )
            baseline_runtime_party = wait_party_locked(emu)
            baseline_metadata, baseline_history = runtime_history(emu)
            history_index, baseline_history_record, history_moves_before = (
                find_history_record(
                    baseline_history,
                    target_pid,
                    target_ot_id,
                )
            )
            revision_before = struct.unpack_from("<I", baseline_metadata, 8)[0]
            dirty_before = baseline_metadata[4]
            require(dirty_before == 0, "controlled history baseline is not clean")
            require(
                history_moves_before == CONTROLLED_HISTORY_MOVES,
                "controlled history acquisition order differs",
            )

            # Touch entry and full candidate PP presentation.
            inactive_state = locate_inactive_summary_state(emu)
            touch(emu, 40, 176, 40)
            transition_evidence.append(
                inactive_summary_evidence(
                    emu,
                    inactive_state,
                    "left page icon is not a relearn action",
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "non-action page icon touch",
            )
            # The vanilla page icon may navigate normally; return to Moves.
            tap(emu, "RIGHT", 80)
            require(
                read_u8(
                    emu,
                    inactive_state
                    - SUMMARY_STATE_RETAIL_SIZE
                    + SUMMARY_PAGE_MODE_OFFSET,
                )
                == 1,
                "vanilla page navigation did not return to Moves",
            )
            touch(emu, 40, 140, 80)
            summary_state = locate_summary_relearn_state(emu)
            state_evidence.append(
                summary_state_evidence(
                    emu,
                    summary_state,
                    1,
                    0,
                    "candidate list",
                )
            )
            initial_view = assert_candidate_viewport(
                emu, summary_state, 0, 0, "initial candidate list"
            )
            require(
                initial_view["count"] > 4,
                "controlled fixture does not exceed four visible candidates",
            )
            require(
                TARGET_MOVE in initial_view["candidates"],
                "controlled target move is not relearnable",
            )
            target_candidate_index = initial_view["candidates"].index(
                TARGET_MOVE
            )
            candidate_capture = Path(
                screenshot(
                    emu,
                    args.screenshot_dir,
                    "02_candidate_list_full_pp.png",
                )
            )
            captures.append(str(candidate_capture))
            pp_pixel_evidence = assert_pp_pixels(candidate_capture)
            control_pixel_evidence.append(
                assert_control_pixels(
                    candidate_capture,
                    label="candidate Pick/Back glyph boundaries",
                    a_span=(8, 40),
                    gap_span=(40, 44),
                    b_span=(44, 49),
                )
            )

            # Exact exclusive edges: x40..43 are blank; x44 is Back.
            for x in (40, 43):
                touch(emu, x, 140, 20)
                transition_evidence.append(
                    summary_state_evidence(
                        emu,
                        summary_state,
                        1,
                        0,
                        f"touch list dead gap x{x}",
                    )
                )
                assert_cancel_exact(
                    emu,
                    baseline_runtime_party,
                    baseline_metadata,
                    baseline_history,
                    f"list dead-gap touch x{x}",
                )
            touch(emu, 44, 140, 20)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 0, 0, "touch list Back glyph edge x44"
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "list Back glyph-edge cancellation",
            )

            # Blue Cancel from the list is exact and non-mutating.
            touch(emu, 40, 140, 30)
            touch(emu, 220, 176, 60)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 0, 0, "touch list Cancel"
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "touch candidate-list cancellation",
            )

            # Prompt touch -> list, Pick strip -> slot, Back strip -> list.
            touch(emu, 40, 140, 60)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 1, 0, "touch prompt entry"
                )
            )
            touch(emu, 39, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 3, 0, "touch list Pick edge x39"
                )
            )
            for x in (40, 43):
                touch(emu, x, 140, 20)
                transition_evidence.append(
                    summary_state_evidence(
                        emu,
                        summary_state,
                        3,
                        0,
                        f"touch slot dead gap x{x}",
                    )
                )
            touch(emu, 44, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu,
                    summary_state,
                    1,
                    0,
                    "touch slot Back glyph edge x44",
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "slot-to-list cancellation",
            )

            # Candidate row -> slot, HM row -> blocked; all visible dismissal
            # controls return to the slot without mutation.
            touch(emu, 50, 24, 60)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 3, 0, "touch candidate row"
                )
            )
            touch(emu, 50, 24, 60)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 5, 0, "touch HM-protected slot"
                )
            )
            hm_capture = Path(
                screenshot(emu, args.screenshot_dir, "03_hm_blocked.png")
            )
            captures.append(str(hm_capture))
            control_pixel_evidence.append(
                assert_control_pixels(
                    hm_capture,
                    label="HM OK/Back glyph boundaries",
                    a_span=(8, 31),
                    gap_span=(31, 35),
                    b_span=(35, 40),
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "HM-protected rejection",
            )
            touch(emu, 20, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 3, 0, "touch HM A:OK dismissal"
                )
            )
            touch(emu, 50, 24, 20)
            summary_state_evidence(
                emu, summary_state, 5, 0, "touch HM row for Back probe"
            )
            touch(emu, 35, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 3, 0, "touch HM B:Back edge x35"
                )
            )
            touch(emu, 50, 24, 20)
            summary_state_evidence(
                emu, summary_state, 5, 0, "touch HM row for blue Cancel"
            )
            touch(emu, 220, 176, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 3, 0, "touch HM blue Cancel"
                )
            )
            touch(emu, 44, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 1, 0, "touch slot Back after HM"
                )
            )
            touch(emu, 44, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 0, 0, "touch list Back after HM"
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "HM flow cancellation",
            )

            # Scroll through the four-row viewport with immediate bounds checks.
            touch(emu, 40, 140, 50)
            scroll_views: list[dict[str, object]] = []
            for cursor, top in ((1, 0), (2, 0), (3, 0), (4, 1)):
                tap(emu, "DOWN", 20)
                scroll_views.append(
                    assert_candidate_viewport(
                        emu, summary_state, cursor, top, f"scroll {cursor}"
                    )
                )
            captures.append(
                screenshot(emu, args.screenshot_dir, "04_candidate_scrolled.png")
            )
            for cursor, top in ((3, 1), (2, 1), (1, 1), (0, 0)):
                tap(emu, "UP", 20)
                scroll_views.append(
                    assert_candidate_viewport(
                        emu, summary_state, cursor, top, f"reverse scroll {cursor}"
                    )
                )

            # Navigate directly to the controlled learnset target.
            target_view = initial_view
            for cursor in range(1, target_candidate_index + 1):
                tap(emu, "DOWN", 20)
                top = 0 if cursor < 4 else cursor - 3
                target_view = assert_candidate_viewport(
                    emu,
                    summary_state,
                    cursor,
                    top,
                    f"target navigation {cursor}",
                )
            target_row_y = 24 + 32 * (
                target_view["cursor"] - target_view["top"]
            )

            # Row select -> slot 3 -> confirmation; Back is immediate/exact.
            touch(emu, 50, target_row_y, 40)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 3, 0, "touch candidate before confirm"
                )
            )
            prospective_evidence.append(
                assert_prospective_slot(
                    emu, summary_state, 0, "inline preview before slot choice"
                )
            )
            touch(emu, 50, 120, 40)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 4, 0, "touch replacement slot"
                )
            )
            confirmation_capture = Path(
                screenshot(emu, args.screenshot_dir, "05_confirmation.png")
            )
            captures.append(str(confirmation_capture))
            control_pixel_evidence.append(
                assert_control_pixels(
                    confirmation_capture,
                    label="confirmation OK/Back glyph boundaries",
                    a_span=(8, 31),
                    gap_span=(31, 35),
                    b_span=(35, 40),
                )
            )
            prospective_evidence.append(
                assert_prospective_slot(
                    emu, summary_state, 3, "inline preview at confirmation"
                )
            )
            for x in (31, 34):
                touch(emu, x, 140, 20)
                transition_evidence.append(
                    summary_state_evidence(
                        emu,
                        summary_state,
                        4,
                        0,
                        f"touch confirmation dead gap x{x}",
                    )
                )
                assert_cancel_exact(
                    emu,
                    baseline_runtime_party,
                    baseline_metadata,
                    baseline_history,
                    f"confirmation dead-gap touch x{x}",
                )
            touch(emu, 35, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu,
                    summary_state,
                    3,
                    0,
                    "touch confirmation Back glyph edge x35",
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "confirmation-to-slot cancellation",
            )
            touch(emu, 44, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 1, 0, "touch slot Back after confirm"
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "confirmation cancellation at list",
            )

            # Re-select and touch OK. This is the first permanent mutation.
            touch(emu, 50, target_row_y, 40)
            touch(emu, 50, 120, 40)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 4, 0, "confirmation before touch OK"
                )
            )
            touch(emu, 20, 140, 90)
            captures.append(
                screenshot(emu, args.screenshot_dir, "06_success.png")
            )
            committed_party = wait_party_locked(emu)
            committed_target = party_record(committed_party, TARGET_SLOT)
            _, committed_moves, committed_pp, committed_pp_ups = record_payload(
                committed_target
            )
            require(
                committed_moves == (57, 48, 352, TARGET_MOVE),
                f"confirmed replacement differs: {committed_moves}",
            )
            require(
                committed_pp[TARGET_REPLACEMENT_SLOT] == 8
                and committed_pp_ups[TARGET_REPLACEMENT_SLOT] == 0,
                "replacement PP/PP Ups do not match normal replacement",
            )
            committed_metadata, committed_history = runtime_history(emu)
            state_evidence.append(
                summary_state_evidence(
                    emu,
                    summary_state,
                    6,
                    1,
                    "successful replacement",
                )
            )
            revision_after = struct.unpack_from("<I", committed_metadata, 8)[0]
            dirty_after = committed_metadata[4]
            require(dirty_after == 1, "successful replacement did not dirty history")
            require(
                revision_after > revision_before,
                "successful replacement did not advance history revision",
            )
            new_index, new_history_record, history_moves_after = (
                find_history_record(
                    committed_history,
                    target_pid,
                    target_ot_id,
                )
            )
            require(new_index == history_index, "replacement changed history identity")
            require(
                history_moves_after[:len(history_moves_before)]
                == history_moves_before,
                "replacement reordered prior move history",
            )
            require(
                history_moves_after.count(TARGET_MOVE) == 1,
                "replacement history lacks exactly one confirmed move",
            )
            for index, (old, new) in enumerate(
                zip(
                    history_records(baseline_history),
                    history_records(committed_history),
                )
            ):
                if index != history_index:
                    require(old == new, f"history record {index} changed unexpectedly")

            touch(emu, 220, 176, 80)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 0, 1, "touch success blue Cancel"
                )
            )
            captures.append(
                screenshot(emu, args.screenshot_dir, "07_replaced_move_pp.png")
            )
            normal_save(emu, baseline_counter)
            captures.append(
                screenshot(emu, args.screenshot_dir, "08_after_save.png")
            )
            require(
                emu.backup.export_file(str(args.export_raw)),
                "DeSmuME could not export the post-save battery",
            )
        finally:
            close_emulator(emu, imported)

    # A separate no-touch path proves the documented modal X/A/B controls.
    key_capture = args.screenshot_dir / "09_key_only_scenario.png"
    key_only_evidence = isolated_scenario_evidence(
        rom,
        args.controlled_raw,
        "keys",
        key_capture,
    )
    captures.append(str(key_capture))

    party_switch_capture = (
        args.screenshot_dir / "09_party_real_switching.png"
    )
    party_switch_evidence = isolated_scenario_evidence(
        rom,
        args.controlled_raw,
        "party_switch",
        party_switch_capture,
    )
    captures.append(str(party_switch_capture))

    center_bootstrap_capture = (
        args.screenshot_dir / "10_retail_center_bootstrap.png"
    )
    center_bootstrap_evidence = isolated_scenario_evidence(
        rom,
        args.controlled_raw,
        "center_bootstrap",
        center_bootstrap_capture,
    )
    captures.append(str(center_bootstrap_capture))
    terminal_bootstrap_capture = (
        args.screenshot_dir / "11_retail_terminal_bootstrap.png"
    )
    terminal_bootstrap_evidence = isolated_scenario_evidence(
        rom,
        Path(center_bootstrap_evidence["exported_raw_save"]),
        "terminal_bootstrap",
        terminal_bootstrap_capture,
    )
    captures.append(str(terminal_bootstrap_capture))

    boxed_capture = args.screenshot_dir / "12_actual_boxed_summary.png"
    boxed_evidence = isolated_scenario_evidence(
        rom,
        Path(terminal_bootstrap_evidence["exported_raw_save"]),
        "boxed",
        boxed_capture,
    )
    captures.extend(boxed_evidence["captures"])
    boxed_reload_capture = (
        args.screenshot_dir / "13_actual_boxed_reload.png"
    )
    boxed_reload_evidence = isolated_scenario_evidence(
        rom,
        Path(boxed_evidence["exported_raw_save"]),
        "boxed_reload",
        boxed_reload_capture,
    )
    captures.extend(boxed_reload_evidence["captures"])
    transfer_capture = (
        args.screenshot_dir / "14_retail_box_party_box_transfer.png"
    )
    transfer_evidence = isolated_scenario_evidence(
        rom,
        Path(boxed_evidence["exported_raw_save"]),
        "transfer",
        transfer_capture,
    )
    captures.extend(transfer_evidence["captures"])
    transfer_reload_capture = (
        args.screenshot_dir / "15_retail_transfer_reload.png"
    )
    transfer_reload_evidence = isolated_scenario_evidence(
        rom,
        Path(transfer_evidence["exported_raw_save"]),
        "transfer_reload",
        transfer_reload_capture,
    )
    captures.extend(transfer_reload_evidence["captures"])

    # Each extra boundary/lifecycle scenario runs in a fresh emulator process.
    for scenario in ("empty", "identity", "position", "teardown"):
        scenario_capture = (
            args.screenshot_dir / f"09_{scenario}_scenario.png"
        )
        boundary_evidence.append(
            isolated_scenario_evidence(
                rom,
                args.controlled_raw,
                scenario,
                scenario_capture,
            )
        )
        captures.append(str(scenario_capture))

    # A fresh process also selects the unchanged controlled baseline exactly;
    # the teardown subprocess itself already proves two real unloads/reloads.
    teardown_probe_path = args.screenshot_dir / "09_teardown_reload.png"
    controlled_probe_party, controlled_probe_metadata, controlled_probe_history = (
        fresh_reload_evidence(
            rom,
            args.controlled_raw,
            teardown_probe_path,
        )
    )
    captures.append(str(teardown_probe_path))
    _, _, selected_controlled_history = selected_persisted_history(controlled_raw)
    require(
        controlled_probe_party == baseline_party
        and controlled_probe_metadata[4] == 0
        and controlled_probe_history == selected_controlled_history,
        "post-lifecycle fresh boot changed persisted party/history",
    )
    boundary_evidence.append(
        {
            "label": "post-lifecycle fresh boot",
            "party_exact": True,
            "history_exact": True,
            "dirty": controlled_probe_metadata[4],
        }
    )

    saved_raw = PARTY.extract_raw_save(args.export_raw)
    saved_counter, saved_count, saved_party = PARTY.party_image(saved_raw)
    saved_pc_counter, saved_pc_base = active_pc_copy(saved_raw)
    saved_box_checksums = validate_all_boxed_checksums(
        saved_raw, saved_pc_base
    )
    baseline_pc_image = controlled_raw[
        controlled_pc_base + PC_SAVE_OFFSET:
        controlled_pc_base + PC_SAVE_OFFSET + PC_STORAGE_BOXES_SIZE
    ]
    saved_pc_image = saved_raw[
        saved_pc_base + PC_SAVE_OFFSET:
        saved_pc_base + PC_SAVE_OFFSET + PC_STORAGE_BOXES_SIZE
    ]
    require(
        saved_pc_image == baseline_pc_image,
        "party-only acceptance changed one or more serialized PC records",
    )
    require(saved_count == occupied, "save changed occupied party count")
    require(
        PARTY.save_counter_compare(saved_counter, baseline_counter) > 0,
        "save counter did not advance",
    )
    saved_summary = PARTY.summarize_party(saved_party)
    saved_checksums = validate_all_party_checksums(saved_party)
    require(
        saved_summary[4] == baseline_summary[4]
        and saved_summary[4]["shiny"] is True,
        "shiny Pidgey identity/checksum changed",
    )
    saved_target = party_record(saved_party, TARGET_SLOT)
    _, saved_moves, saved_pp, saved_pp_ups = record_payload(saved_target)
    require(
        saved_moves == (57, 48, 352, TARGET_MOVE)
        and saved_pp[TARGET_REPLACEMENT_SLOT] == 8
        and saved_pp_ups[TARGET_REPLACEMENT_SLOT] == 0,
        "saved replacement move/PP/PP Ups differ",
    )
    require(
        saved_party[:8] == baseline_party[:8],
        "party header changed unexpectedly",
    )
    for index in range(6):
        if index != TARGET_SLOT:
            require(
                party_record(saved_party, index)
                == party_record(baseline_party, index),
                f"unrelated serialized party record {index} changed",
            )
    require(
        saved_target[0x88:] == before_target[0x88:],
        "unrelated target PartyPokemon battle/stat bytes changed",
    )
    semantic_differences = target_semantic_diff(before_target, saved_target)
    attacks = PARTY.SUBSTRUCT_OFFSETS[
        (struct.unpack_from("<I", before_target)[0] & 0x3E000) >> 13
    ][1]
    allowed_differences = {
        attacks + TARGET_REPLACEMENT_SLOT * 2,
        attacks + TARGET_REPLACEMENT_SLOT * 2 + 1,
        attacks + 8 + TARGET_REPLACEMENT_SLOT,
        attacks + 12 + TARGET_REPLACEMENT_SLOT,
    }
    require(
        set(semantic_differences) <= allowed_differences,
        "unrelated decrypted target bytes changed: "
        + ",".join(f"0x{offset:X}" for offset in semantic_differences),
    )

    selected_counter, selected_mirror, persisted_history = (
        selected_persisted_history(saved_raw)
    )
    require(
        selected_counter == saved_counter,
        "persisted history generation does not match normal save generation",
    )
    persisted_index, persisted_record, persisted_moves = find_history_record(
        persisted_history,
        target_pid,
        target_ot_id,
    )
    require(
        persisted_index == history_index
        and persisted_moves == history_moves_after
        and persisted_record == new_history_record,
        "persisted target history record differs from committed runtime record",
    )
    for index, (old, new) in enumerate(
        zip(
            history_records(baseline_history),
            history_records(persisted_history),
        )
    ):
        if index != history_index:
            require(old == new, f"persisted unrelated history record {index} changed")

    reload_screenshot = args.screenshot_dir / "10_saved_reload.png"
    reloaded_party, reloaded_metadata, reloaded_history = fresh_reload_evidence(
        rom,
        args.export_raw,
        reload_screenshot,
    )
    captures.append(str(reload_screenshot))
    require(reloaded_party == saved_party, "fresh reload changed saved party bytes")
    require(
        reloaded_metadata[4] == 0,
        "fresh reload did not select a clean authenticated history baseline",
    )
    require(
        reloaded_history == persisted_history,
        "fresh reload history differs from selected persisted mirror",
    )
    _, reloaded_record, reloaded_moves = find_history_record(
        reloaded_history,
        target_pid,
        target_ot_id,
    )
    require(
        reloaded_record == persisted_record
        and reloaded_moves == persisted_moves,
        "fresh reload target history revision/record differs",
    )
    reloaded_checksums = validate_all_party_checksums(reloaded_party)
    require(
        hashlib.sha256(dsv.read_bytes()).hexdigest() == source_hash,
        "preserved source DSV was mutated",
    )

    return {
        "rom": str(rom),
        "rom_sha256": hashlib.sha256(rom.read_bytes()).hexdigest(),
        "preserved_dsv": str(dsv),
        "preserved_dsv_sha256": source_hash,
        "source_dsv_unchanged": dsv.read_bytes() == source_dsv,
        "controlled_fixture": {
            "derivation": "temporary authenticated raw save; source DSV immutable",
            "path": str(args.controlled_raw),
            "history_dirty": dirty_before,
            "history_mirrors_valid": [
                valid_history_image(
                    controlled_raw[
                        offset:offset + HISTORY_IMAGE_SIZE
                    ],
                    mirror,
                )
                for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS)
            ],
            "moves": list(before_moves),
            "pp": list(before_pp),
            "pp_ups": list(before_pp_ups),
            "pc_generation": controlled_pc_counter,
            "pc_copies_authenticated": len(valid_pc_copies(controlled_raw)),
            "boxed_target_identity": list(
                box_fixture["target_identity"]
            ),
            "boxed_switch_identity": list(
                box_fixture["switch_identity"]
            ),
            "all_900_box_checksums_valid": len(baseline_box_checksums) == 900,
        },
        "baseline_save_counter": baseline_counter,
        "saved_save_counter": saved_counter,
        "candidate_navigation": {
            "count": initial_view["count"],
            "ordered": list(initial_view["candidates"]),
            "viewport_scroll_proven": True,
            "views": scroll_views,
            "live_full_pp": {
                "current": list(initial_view["cache_cur_pp"]),
                "maximum": list(initial_view["cache_max_pp"]),
            },
            "pixel_evidence": pp_pixel_evidence,
        },
        "cancel_paths_exact": [
            "candidate list touch Cancel",
            "slot to list",
            "confirmation to slot",
            "HM rejection",
            "empty list",
            "identity boundary",
            "position boundary",
            "real Summary exit, overlay unload/reload, and second exit",
        ],
        "replacement": {
            "party_slot": TARGET_SLOT,
            "species": TARGET_SPECIES,
            "move_slot": TARGET_REPLACEMENT_SLOT,
            "before_moves": list(before_moves),
            "after_moves": list(saved_moves),
            "after_pp": list(saved_pp),
            "after_pp_ups": list(saved_pp_ups),
            "semantic_changed_payload_offsets": semantic_differences,
        },
        "history": {
            "record_index": history_index,
            "revision_before": revision_before,
            "revision_after_commit": revision_after,
            "moves_before": list(history_moves_before),
            "moves_after": list(history_moves_after),
            "dirty_before": dirty_before,
            "dirty_after_commit": dirty_after,
            "unrelated_records_exact": True,
            "persisted_mirror": selected_mirror,
            "persisted_counter": selected_counter,
            "persisted_record_exact": True,
            "fresh_reload_dirty": reloaded_metadata[4],
            "fresh_reload_record_exact": True,
        },
        "party": {
            "serialized_stride": "0xEC",
            "all_six_checksum_valid": True,
            "baseline_checksums": baseline_checksums,
            "saved_checksums": saved_checksums,
            "reloaded_checksums": reloaded_checksums,
            "unrelated_records_exact": True,
            "fresh_reload_exact": True,
            "shiny_pidgey": saved_summary[4],
        },
        "pc_storage": {
            "serialized_box_stride": "0x1000",
            "serialized_box_mon_stride": "0x88",
            "baseline_generation": controlled_pc_counter,
            "saved_generation": saved_pc_counter,
            "both_baseline_copies_authenticated": True,
            "all_900_baseline_checksums_valid": len(
                baseline_box_checksums
            ) == 900,
            "all_900_saved_checksums_valid": len(saved_box_checksums) == 900,
            "party_only_path_records_exact": True,
        },
        "summary_state_evidence": state_evidence,
        "immediate_touch_transitions": transition_evidence,
        "boundary_evidence": boundary_evidence,
        "key_only_evidence": key_only_evidence,
        "party_switch_evidence": party_switch_evidence,
        "retail_center_bootstrap_evidence": center_bootstrap_evidence,
        "retail_terminal_bootstrap_evidence": terminal_bootstrap_evidence,
        "boxed_evidence": boxed_evidence,
        "boxed_reload_evidence": boxed_reload_evidence,
        "transfer_evidence": transfer_evidence,
        "transfer_reload_evidence": transfer_reload_evidence,
        "prospective_evidence": prospective_evidence,
        "control_pixel_evidence": control_pixel_evidence,
        "screenshots": captures,
        "exported_raw_save": str(args.export_raw),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=REPO / "test.nds")
    parser.add_argument("--dsv", type=Path)
    parser.add_argument("--expected-dsv-sha256")
    parser.add_argument("--probe-raw", type=Path)
    parser.add_argument(
        "--scenario",
        choices=(
            "empty",
            "identity",
            "position",
            "teardown",
            "keys",
            "party_switch",
            "center_bootstrap",
            "terminal_bootstrap",
            "transfer",
            "transfer_reload",
            "boxed",
            "boxed_reload",
        ),
    )
    parser.add_argument(
        "--probe-screenshot",
        type=Path,
        default=REPO
        / "build/diagnostics/task4_summary_relearn/reload-probe.png",
    )
    parser.add_argument(
        "--screenshot-dir",
        type=Path,
        default=REPO / "build/diagnostics/task4_summary_relearn",
    )
    parser.add_argument(
        "--export-raw",
        type=Path,
        default=REPO / "build/diagnostics/task4_summary_relearn/post-save.sav",
    )
    parser.add_argument(
        "--controlled-raw",
        type=Path,
        default=REPO
        / "build/diagnostics/task4_summary_relearn/controlled-baseline.sav",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        arguments = parse_args()
        if arguments.scenario is not None:
            require(arguments.probe_raw is not None, "--probe-raw is required")
            result = run_isolated_scenario(
                arguments.rom.resolve(),
                arguments.probe_raw.resolve(),
                arguments.scenario,
                arguments.probe_screenshot.resolve(),
            )
        elif arguments.probe_raw is not None:
            result = run_reload_probe(
                arguments.rom.resolve(),
                arguments.probe_raw.resolve(),
                arguments.probe_screenshot.resolve(),
            )
        else:
            require(arguments.dsv is not None, "--dsv is required")
            result = run(arguments)
        print(json.dumps(result, indent=2, sort_keys=True))
    except Exception as error:
        print(f"Summary relearn runtime verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
