#!/usr/bin/env python3
"""Prepare field-safe sounds used by overworld wild Pokémon systems.

Give the overworld Poké Ball sounds a small private bank: their original
BANK_SE_BATTLE wave archive does not fit in the field sound heap. Also preload
the movement sounds that already use BANK_SE_FIELD, so movement can play them
without synchronously loading sound-archive resources during gameplay.
"""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


CAPTURE_SEQUENCE_NAMES = (
    "SEQ_SE_DP_GETTING",
    "SEQ_SE_DP_NAGERU",
    "SEQ_SE_DP_BOWA2",
    "SEQ_SE_DP_BOWA4",
)
MOVEMENT_SEQUENCE_NAMES = (
    "SEQ_SE_DP_FPASA2",
    "SEQ_SE_PL_BALLOON03",
    "SEQ_SE_DP_WALL_HIT",
    "SEQ_SE_GS_IWAOTOSHI02",
)
SOURCE_BANK_NAME = "BANK_SE_BATTLE"
SOURCE_WAVE_ARCHIVE_NAME = "WAVE_ARC_SE_BATTLE"
PRIVATE_BANK_NAME = "BANK_SE_DP_GETTING_FIELD"
PRIVATE_WAVE_ARCHIVE_NAME = "WAVE_ARC_SE_DP_GETTING_FIELD"
SHARED_FIELD_BANK_NAME = "BANK_SE_FIELD"
FIELD_SOUND_GROUP_NAME = "GROUP_SE_FIELD"
# SDAT group item type 0 with sequence, bank, and wave loading enabled.
FIELD_SOUND_CAPTURE_SEQUENCE_LOAD_TYPE = 0x700
# The movement sequences share BANK_SE_FIELD and its resident wave archives.
# Load only each SSEQ; repeating the shared bank/wave loads wastes sound heap.
FIELD_SOUND_MOVEMENT_SEQUENCE_LOAD_TYPE = 0x100
FIELD_SOUND_SEQUENCE_LOAD_TYPES = {
    FIELD_SOUND_CAPTURE_SEQUENCE_LOAD_TYPE,
    FIELD_SOUND_MOVEMENT_SEQUENCE_LOAD_TYPE,
}
PRIVATE_BANK_SLOT = 749
PRIVATE_WAVE_ARCHIVE_SLOT = 749
INSTRUMENT_WAVES = {
    94: 7,
    95: 14,
    97: 19,
    72: 1,
    67: 25,
    98: 25,
}
SOURCE_WAVES = (7, 14, 19, 1, 25)
PSG_INSTRUMENT_TYPES = {113: "PSG1", 114: "PSG1", 122: "PSG2"}


def find_named(entries, name):
    return next(entry for entry in entries if entry.get("name") == name)


def find_named_index(entries, name):
    matches = [
        index for index, entry in enumerate(entries) if entry.get("name") == name
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one SDAT INFO entry named {name}, "
            f"found {len(matches)}"
        )
    return matches[0]


def require_full_field_bank_preload(group_entries, sequence_entries, bank_name):
    field_group = find_named(group_entries, FIELD_SOUND_GROUP_NAME)
    sub_group = field_group.get("subGroup")
    if not isinstance(sub_group, list):
        raise RuntimeError(
            f"{FIELD_SOUND_GROUP_NAME} has no valid subGroup list"
        )

    for item in sub_group:
        if (
            isinstance(item, dict)
            and item.get("type") == FIELD_SOUND_CAPTURE_SEQUENCE_LOAD_TYPE
            and isinstance(item.get("entry"), int)
            and 0 <= item["entry"] < len(sequence_entries)
            and sequence_entries[item["entry"]].get("bnk") == bank_name
        ):
            return
    raise RuntimeError(
        f"{FIELD_SOUND_GROUP_NAME} does not fully preload {bank_name}"
    )


def add_sequences_to_field_group(group_entries, sequence_items):
    field_group_index = find_named_index(
        group_entries, FIELD_SOUND_GROUP_NAME
    )
    field_group = group_entries[field_group_index]
    sub_group = field_group.get("subGroup")
    if not isinstance(sub_group, list):
        raise RuntimeError(
            f"{FIELD_SOUND_GROUP_NAME} has no valid subGroup list"
        )
    if (
        not isinstance(field_group.get("count"), int)
        or field_group["count"] < 0
    ):
        raise RuntimeError(f"{FIELD_SOUND_GROUP_NAME} has no valid count")

    for item in sub_group:
        if not isinstance(item, dict):
            raise RuntimeError(
                f"{FIELD_SOUND_GROUP_NAME} contains a non-object item"
            )
        if not isinstance(item.get("type"), int) or not isinstance(
            item.get("entry"), int
        ):
            raise RuntimeError(
                f"{FIELD_SOUND_GROUP_NAME} contains an invalid item: {item!r}"
            )
        if item["type"] not in FIELD_SOUND_SEQUENCE_LOAD_TYPES:
            raise RuntimeError(
                f"{FIELD_SOUND_GROUP_NAME} contains unexpected item type "
                f"{item['type']:#x}"
            )

    target_load_types = {}
    for load_type, sequence_index in sequence_items:
        if load_type not in FIELD_SOUND_SEQUENCE_LOAD_TYPES:
            raise RuntimeError(f"Invalid field sequence load type {load_type:#x}")
        previous_type = target_load_types.setdefault(sequence_index, load_type)
        if previous_type != load_type:
            raise RuntimeError(
                f"Sequence {sequence_index} has conflicting field load types"
            )

    seen_target_entries = set()
    deduplicated_sub_group = []
    for item in sub_group:
        sequence_index = item["entry"]
        if sequence_index in target_load_types:
            if (
                item["type"] != target_load_types[sequence_index]
                or sequence_index in seen_target_entries
            ):
                continue
            seen_target_entries.add(sequence_index)
        deduplicated_sub_group.append(item)

    for load_type, sequence_index in sequence_items:
        if sequence_index in seen_target_entries:
            continue
        deduplicated_sub_group.append(
            {
                "type": load_type,
                "entry": sequence_index,
            }
        )
        seen_target_entries.add(sequence_index)

    field_group["subGroup"] = deduplicated_sub_group
    field_group["count"] = len(deduplicated_sub_group)


def reserve_slot(entries, index, expected_name, replacement):
    current_name = entries[index].get("name", "")
    if current_name not in ("", expected_name):
        raise RuntimeError(
            f"SDAT INFO slot {index} is occupied by {current_name}; "
            f"cannot reserve it for {expected_name}"
        )
    entries[index] = replacement


def upsert_file(file_entries, replacement):
    for index, entry in enumerate(file_entries):
        if entry.get("name") == replacement["name"]:
            file_entries[index] = replacement
            return
    file_entries.append(replacement)


def make_private_bank(source_bank_text):
    source_instruments = {}
    for line in source_bank_text.splitlines():
        match = re.match(r"^(\d+),\s+(Single|PSG1|PSG2),\s+(.*)$", line)
        if match:
            source_instruments[int(match.group(1))] = (
                match.group(2),
                match.group(3),
            )

    lines = []
    private_instruments = set(INSTRUMENT_WAVES) | set(PSG_INSTRUMENT_TYPES)
    for instrument in range(max(private_instruments) + 1):
        if instrument not in private_instruments:
            lines.append(f"{instrument}, NULL")
            continue

        if instrument not in source_instruments:
            raise RuntimeError(f"Missing source instrument {instrument}")
        instrument_type, instrument_data = source_instruments[instrument]
        if instrument in PSG_INSTRUMENT_TYPES:
            if instrument_type != PSG_INSTRUMENT_TYPES[instrument]:
                raise RuntimeError(
                    f"Expected {PSG_INSTRUMENT_TYPES[instrument]} instrument "
                    f"{instrument}, got {instrument_type}"
                )
            lines.append(f"{instrument}, {instrument_type}, {instrument_data}")
            continue

        source_wave = INSTRUMENT_WAVES[instrument]
        fields = [field.strip() for field in instrument_data.split(",")]
        if instrument_type != "Single":
            raise RuntimeError(
                f"Expected sampled instrument {instrument}, got {instrument_type}"
            )
        if int(fields[0]) != source_wave or int(fields[1]) != 1:
            raise RuntimeError(
                f"Unexpected source mapping for instrument {instrument}: {fields[:2]}"
            )
        fields[0] = str(SOURCE_WAVES.index(source_wave))
        lines.append(f"{instrument}, {instrument_type}, {', '.join(fields)}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sdat_dir", type=Path)
    args = parser.parse_args()

    info_path = args.sdat_dir / "InfoBlock.json"
    file_path = args.sdat_dir / "FileBlock.json"
    files_dir = args.sdat_dir / "Files"
    info = json.loads(info_path.read_text())
    file_block = json.loads(file_path.read_text())

    source_bank = find_named(info["bankInfo"], SOURCE_BANK_NAME)
    source_wave_archive = find_named(
        info["wavarcInfo"], SOURCE_WAVE_ARCHIVE_NAME
    )
    capture_sequence_indices = []
    for sequence_name in CAPTURE_SEQUENCE_NAMES:
        sequence_index = find_named_index(info["seqInfo"], sequence_name)
        info["seqInfo"][sequence_index]["bnk"] = PRIVATE_BANK_NAME
        capture_sequence_indices.append(sequence_index)

    movement_sequence_indices = []
    for sequence_name in MOVEMENT_SEQUENCE_NAMES:
        sequence_index = find_named_index(info["seqInfo"], sequence_name)
        sequence = info["seqInfo"][sequence_index]
        if sequence.get("bnk") != SHARED_FIELD_BANK_NAME:
            raise RuntimeError(
                f"Expected {sequence_name} to use {SHARED_FIELD_BANK_NAME}, "
                f"got {sequence.get('bnk')!r}"
            )
        movement_sequence_indices.append(sequence_index)

    # A pre-existing 0x700 sequence entry loads BANK_SE_FIELD and both wave
    # archives before the new movement SSEQ-only (0x100) entries are used.
    require_full_field_bank_preload(
        info["groupInfo"], info["seqInfo"], SHARED_FIELD_BANK_NAME
    )

    private_bank_file = f"{PRIVATE_BANK_NAME}.sbnk"
    private_wave_archive_file = f"{PRIVATE_WAVE_ARCHIVE_NAME}.swar"
    reserve_slot(
        info["bankInfo"],
        PRIVATE_BANK_SLOT,
        PRIVATE_BANK_NAME,
        {
            "name": PRIVATE_BANK_NAME,
            "fileName": private_bank_file,
            "unkA": source_bank["unkA"],
            "wa": ["", PRIVATE_WAVE_ARCHIVE_NAME, "", ""],
        },
    )
    reserve_slot(
        info["wavarcInfo"],
        PRIVATE_WAVE_ARCHIVE_SLOT,
        PRIVATE_WAVE_ARCHIVE_NAME,
        {
            "name": PRIVATE_WAVE_ARCHIVE_NAME,
            "fileName": private_wave_archive_file,
            "unkA": source_wave_archive["unkA"],
        },
    )
    add_sequences_to_field_group(
        info["groupInfo"],
        [
            *(
                (FIELD_SOUND_CAPTURE_SEQUENCE_LOAD_TYPE, sequence_index)
                for sequence_index in capture_sequence_indices
            ),
            *(
                (FIELD_SOUND_MOVEMENT_SEQUENCE_LOAD_TYPE, sequence_index)
                for sequence_index in movement_sequence_indices
            ),
        ],
    )

    source_bank_text = (
        files_dir / "BANK" / f"{SOURCE_BANK_NAME}.txt"
    ).read_text()
    private_bank_text = make_private_bank(source_bank_text)
    private_bank_txt_path = files_dir / "BANK" / f"{PRIVATE_BANK_NAME}.txt"
    private_bank_txt_path.write_text(private_bank_text)

    source_wave_dir = files_dir / "WAVARC" / SOURCE_WAVE_ARCHIVE_NAME
    private_wave_dir = files_dir / "WAVARC" / PRIVATE_WAVE_ARCHIVE_NAME
    private_wave_dir.mkdir(parents=True, exist_ok=True)
    private_wave_names = []
    wave_digest = hashlib.md5()
    for private_index, source_index in enumerate(SOURCE_WAVES):
        source_name = f"{source_index:02X}.swav"
        private_name = f"{private_index:02X}.swav"
        source_path = source_wave_dir / source_name
        private_path = private_wave_dir / private_name
        shutil.copyfile(source_path, private_path)
        private_wave_names.append(private_name)
        wave_digest.update(private_path.read_bytes())

    # Force SDATTool to rebuild these binaries from the text and individual waves.
    (files_dir / "BANK" / private_bank_file).unlink(missing_ok=True)
    (files_dir / "WAVARC" / private_wave_archive_file).unlink(missing_ok=True)

    upsert_file(
        file_block["file"],
        {
            "name": private_bank_file,
            "type": "BANK",
            "MD5": hashlib.md5(private_bank_text.encode()).hexdigest(),
        },
    )
    upsert_file(
        file_block["file"],
        {
            "name": private_wave_archive_file,
            "type": "WAVARC",
            "MD5": wave_digest.hexdigest(),
            "subFile": private_wave_names,
        },
    )

    info_path.write_text(json.dumps(info))
    file_path.write_text(json.dumps(file_block))


if __name__ == "__main__":
    main()
