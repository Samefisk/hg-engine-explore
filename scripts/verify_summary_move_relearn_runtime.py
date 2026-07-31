#!/usr/bin/env python3
"""Key-only Summary relearn acceptance against a preserved DeSmuME DSV."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import struct
import sys
import tempfile
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
SUMMARY_STATE_ORIGINAL_MOVES_OFFSET = 134
SUMMARY_STATE_CANDIDATE_COUNT_OFFSET = 150
SUMMARY_STATE_OWNER_POS_OFFSET = 160
SUMMARY_STATE_MODE_OFFSET = 163
SUMMARY_STATE_RETAIL_SIZE = 0x7D8
SUMMARY_OWNER_DIRTY_OFFSET = 0x38


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


def locate_summary_relearn_state(emu: DeSmuME) -> int:
    signature = struct.pack("<4H", 35, 48, 352, 103)
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
                ) == 3
                and read_u8(
                    emu,
                    state + SUMMARY_STATE_OWNER_POS_OFFSET,
                ) == TARGET_SLOT
                and struct.unpack(
                    "<3H",
                    read_bytes(emu, state + 4, 6),
                ) == (40, 55, 51)
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
    require(actual_party == expected_party, f"{label} changed party bytes")
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
    baseline_raw = PARTY.extract_raw_save(dsv)
    baseline_counter, occupied, baseline_party = PARTY.party_image(baseline_raw)
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
        before_moves == (35, 48, 352, 103),
        f"Tentacool fixture moves differ: {before_moves}",
    )

    args.screenshot_dir.mkdir(parents=True, exist_ok=True)
    args.export_raw.parent.mkdir(parents=True, exist_ok=True)
    captures: list[str] = []
    state_evidence: list[dict[str, int | str]] = []
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    with HEADLESS.silence_native_output(True):
        emu = DeSmuME()
        emu.volume_set(0)
        emu.open(str(rom))
        with tempfile.NamedTemporaryFile(suffix=".sav") as imported:
            PARTY.import_raw(emu, baseline_raw, imported)
            HEADLESS.boot_to_ready(boot_arguments(), emu)
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

            # Open party slot 2 -> Summary -> Moves, using keys only.
            tap(emu, "X", 20)
            tap(emu, "A", 100)
            tap(emu, "DOWN", 20)
            tap(emu, "A", 30)
            tap(emu, "A", 100)
            tap(emu, "RIGHT", 80)
            captures.append(
                screenshot(emu, args.screenshot_dir, "01_moves_prompt.png")
            )
            baseline_runtime_party = wait_party_locked(emu)
            baseline_metadata, baseline_history = runtime_history(emu)
            target_pid = struct.unpack_from("<I", before_target)[0]
            permutation = (target_pid & 0x3E000) >> 13
            growth = PARTY.SUBSTRUCT_OFFSETS[permutation][0]
            target_ot_id = struct.unpack_from(
                "<I", before_payload, growth + 4
            )[0]
            history_index, baseline_history_record, history_moves_before = (
                find_history_record(
                    baseline_history,
                    target_pid,
                    target_ot_id,
                )
            )
            revision_before = struct.unpack_from("<I", baseline_metadata, 8)[0]
            dirty_before = baseline_metadata[4]

            # Candidate list navigation and list cancellation.
            tap(emu, "X", 80)
            captures.append(
                screenshot(emu, args.screenshot_dir, "02_candidate_list.png")
            )
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
            tap(emu, "DOWN", 60)
            captures.append(
                screenshot(emu, args.screenshot_dir, "03_candidate_scrolled.png")
            )
            tap(emu, "B", 80)
            captures.append(
                screenshot(emu, args.screenshot_dir, "04_list_cancel.png")
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "candidate-list cancellation",
            )
            state_evidence.append(
                summary_state_evidence(
                    emu,
                    summary_state,
                    0,
                    0,
                    "candidate-list cancel",
                )
            )

            # Slot cancellation.
            tap(emu, "X", 60)
            tap(emu, "A", 80)
            captures.append(
                screenshot(emu, args.screenshot_dir, "05_slot_selection.png")
            )
            state_evidence.append(
                summary_state_evidence(
                    emu,
                    summary_state,
                    3,
                    0,
                    "slot selection",
                )
            )
            tap(emu, "B", 60)
            tap(emu, "B", 80)
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "slot-selection cancellation",
            )
            state_evidence.append(
                summary_state_evidence(
                    emu,
                    summary_state,
                    0,
                    0,
                    "slot-selection cancel",
                )
            )

            # Confirmation cancellation after choosing slot 3.
            tap(emu, "X", 60)
            tap(emu, "A", 60)
            tap(emu, "UP", 40)
            tap(emu, "A", 60)
            captures.append(
                screenshot(emu, args.screenshot_dir, "06_confirmation.png")
            )
            state_evidence.append(
                summary_state_evidence(
                    emu,
                    summary_state,
                    4,
                    0,
                    "confirmation",
                )
            )
            tap(emu, "B", 50)
            captures.append(
                screenshot(emu, args.screenshot_dir, "07_confirm_cancel.png")
            )
            tap(emu, "B", 50)
            tap(emu, "B", 80)
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "confirmation cancellation",
            )
            state_evidence.append(
                summary_state_evidence(
                    emu,
                    summary_state,
                    0,
                    0,
                    "confirmation cancel",
                )
            )

            # Confirm Poison Sting over slot 3.
            tap(emu, "X", 60)
            tap(emu, "A", 60)
            tap(emu, "UP", 40)
            tap(emu, "A", 50)
            tap(emu, "A", 90)
            captures.append(
                screenshot(emu, args.screenshot_dir, "08_success.png")
            )
            committed_party = wait_party_locked(emu)
            committed_target = party_record(committed_party, TARGET_SLOT)
            _, committed_moves, committed_pp, committed_pp_ups = record_payload(
                committed_target
            )
            require(
                committed_moves == (35, 48, 352, TARGET_MOVE),
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

            tap(emu, "B", 80)
            captures.append(
                screenshot(emu, args.screenshot_dir, "09_replaced_move_pp.png")
            )
            normal_save(emu, baseline_counter)
            captures.append(
                screenshot(emu, args.screenshot_dir, "10_after_save.png")
            )
            require(
                emu.backup.export_file(str(args.export_raw)),
                "DeSmuME could not export the post-save battery",
            )
        emu.destroy()

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
        saved_moves == (35, 48, 352, TARGET_MOVE)
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
    }
    require(
        set(semantic_differences) <= allowed_differences,
        "unrelated decrypted target bytes changed: "
        + ",".join(f"0x{offset:X}" for offset in semantic_differences),
    )

    reload_screenshot = args.screenshot_dir / "11_reload.png"
    reloaded_party = PARTY.reload_party_in_fresh_process(
        rom,
        saved_raw,
        reload_screenshot,
    )
    captures.append(str(reload_screenshot))
    require(reloaded_party == saved_party, "fresh reload changed saved party bytes")
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
        "baseline_save_counter": baseline_counter,
        "saved_save_counter": saved_counter,
        "candidate_navigation": "Poison Sting -> Water Gun -> Poison Sting",
        "cancel_paths_exact": [
            "candidate list",
            "slot selection",
            "confirmation",
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
        "screenshots": captures,
        "exported_raw_save": str(args.export_raw),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=REPO / "test.nds")
    parser.add_argument("--dsv", type=Path, required=True)
    parser.add_argument("--expected-dsv-sha256")
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
    return parser.parse_args()


if __name__ == "__main__":
    try:
        print(json.dumps(run(parse_args()), indent=2, sort_keys=True))
    except Exception as error:
        print(f"Summary relearn runtime verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
