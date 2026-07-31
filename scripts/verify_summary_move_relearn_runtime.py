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
                == 1
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


def make_controlled_raw(
    baseline_raw: bytes,
) -> tuple[bytes, bytes, int, int, bytes]:
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

    valid_images = []
    for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS):
        image = baseline_raw[offset:offset + HISTORY_IMAGE_SIZE]
        if valid_history_image(image, mirror):
            valid_images.append(image)
    require(valid_images, "immutable fixture has no valid history mirror")
    payload = bytearray(valid_images[0][:HISTORY_FOOTER_OFFSET])
    index, _, _ = find_history_record(bytes(payload) + bytes(0x20), pid, ot_id)
    record_offset = HISTORY_HEADER_SIZE + index * HISTORY_RECORD_SIZE
    payload[record_offset + 14] = len(CONTROLLED_HISTORY_MOVES)
    payload[record_offset + 15] = 1
    payload[record_offset + 16:record_offset + 64] = bytes(48)
    struct.pack_into(
        f"<{len(CONTROLLED_HISTORY_MOVES)}H",
        payload,
        record_offset + 16,
        *CONTROLLED_HISTORY_MOVES,
    )
    for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS):
        counter = (
            active_counter
            if mirror == 0
            else (active_counter - 1) & 0xFFFFFFFF
        )
        image = history_image_for_mirror(bytes(payload), mirror, counter)
        raw[offset:offset + HISTORY_IMAGE_SIZE] = image
    return bytes(raw), controlled_party, pid, ot_id, bytes(payload)


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
    tap(emu, "A", 30)
    tap(emu, "A", 100)
    tap(emu, "RIGHT", 80)


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
        timeout=90,
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
    ) = make_controlled_raw(immutable_raw)
    baseline_counter, occupied, checked_party = PARTY.party_image(controlled_raw)
    require(checked_party == baseline_party, "controlled party selection differs")
    require(occupied == 5, f"fixture party count differs: {occupied}")
    baseline_summary = PARTY.summarize_party(baseline_party)
    baseline_checksums = validate_all_party_checksums(baseline_party)
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
        "summary_state_evidence": state_evidence,
        "immediate_touch_transitions": transition_evidence,
        "boundary_evidence": boundary_evidence,
        "key_only_evidence": key_only_evidence,
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
        choices=("empty", "identity", "position", "teardown", "keys"),
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
