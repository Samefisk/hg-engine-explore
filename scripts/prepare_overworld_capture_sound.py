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
    "SEQ_SE_DP_BALL_OPEN",
    "SEQ_SE_DP_BALL_DRAW_IN",
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

# BOWA4 contains two independently useful sounds separated on every track at
# tick 60 (0.843 seconds at tempo 89). Keep BOWA4 intact for existing callers,
# and turn its two unused neighboring INFO slots into separately playable
# sequences. Both halves are described once here and emitted as matching text
# and SSEQ binaries below.
SPLIT_CAPTURE_SEQUENCES = (
    {
        "slot": 1793,
        "replaces": "SEQ_SE_DP_DUMMY16",
        "name": "SEQ_SE_DP_BALL_OPEN",
        "tracks": (
            (
                ("Poly", 0),
                ("Tempo", 89),
                ("Instrument", 67),
                ("Volume", 127),
                ("PitchSweep", 0),
                ("PitchBendRange", 2),
                ("PitchBend", 2),
                ("F_5", 90, 18),
                ("Delay", 24),
                ("F_5", 55, 12),
                ("Delay", 12),
                ("F_5", 30, 12),
                ("Delay", 24),
                ("TrackEnd",),
            ),
            (
                ("Poly", 0),
                ("Instrument", 114),
                ("Volume", 127),
                ("PitchBend", 0),
                ("F_6", 80, 12),
                ("Delay", 24),
                ("F_6", 30, 12),
                ("Delay", 36),
                ("TrackEnd",),
            ),
        ),
    },
    {
        "slot": 1794,
        "replaces": "SEQ_SE_DP_DUMMY17",
        "name": "SEQ_SE_DP_BALL_DRAW_IN",
        "tracks": (
            (
                ("Poly", 0),
                ("Tempo", 89),
                ("Instrument", 113),
                ("Volume", 127),
                ("PitchSweep", 64432),
                ("PitchBendRange", 2),
                ("PitchBend", 0),
                ("G_4", 100, 5),
                ("Delay", 6),
                ("F_5", 100, 11),
                ("Delay", 12),
                ("F_5", 50, 12),
                ("Delay", 12),
                ("TrackEnd",),
            ),
            (
                ("Poly", 0),
                ("Instrument", 72),
                ("Volume", 127),
                ("PitchBendRange", 12),
                ("PitchBend", 0),
                ("G_6", 50, 6),
                ("Delay", 6),
                ("C_5", 112, 6),
                ("Delay", 12),
                ("C_4", 90, 6),
                ("Delay", 6),
                ("TrackEnd",),
            ),
            (
                ("Poly", 0),
                ("Instrument", 122),
                ("Volume", 127),
                ("G_6", 50, 6),
                ("Delay", 6),
                ("G#7", 50, 6),
                ("Delay", 6),
                ("Instrument", 98),
                ("Volume", 16),
                ("PitchBendRange", 12),
                ("PitchBend", 98),
                ("G_5", 80, 12),
                ("Delay", 2),
                ("PitchBend", 68),
                ("Volume", 35),
                ("Delay", 1),
                ("PitchBend", 44),
                ("Volume", 57),
                ("Delay", 1),
                ("Volume", 80),
                ("PitchBend", 26),
                ("Delay", 1),
                ("Volume", 96),
                ("PitchBend", 40),
                ("Delay", 2),
                ("PitchBend", 66),
                ("Volume", 111),
                ("Delay", 1),
                ("PitchBend", 86),
                ("Volume", 123),
                ("Delay", 1),
                ("PitchBend", 108),
                ("Volume", 127),
                ("Delay", 2),
                ("PitchBend", 127),
                ("Delay", 7),
                ("G_5", 40, 6),
                ("Delay", 6),
                ("TrackEnd",),
            ),
        ),
    },
)

SSEQ_COMMANDS = {
    "Delay": (0x80, "var"),
    "Instrument": (0x81, "var"),
    "TrackEnd": (0xFF, None),
    "Volume": (0xC1, "byte"),
    "PitchBend": (0xC4, "byte"),
    "PitchBendRange": (0xC5, "byte"),
    "Poly": (0xC7, "byte"),
    "Tempo": (0xE1, "short"),
    "PitchSweep": (0xE3, "short"),
}
SSEQ_NOTE_NAMES = (
    "C_", "C#", "D_", "D#", "E_", "F_",
    "F#", "G_", "G#", "A_", "A#", "B_",
)


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
    expected_names = (
        (expected_name,)
        if isinstance(expected_name, str)
        else tuple(expected_name)
    )
    if current_name not in ("", *expected_names):
        raise RuntimeError(
            f"SDAT INFO slot {index} is occupied by {current_name}; "
            f"cannot reserve it for {replacement['name']}"
        )
    entries[index] = replacement


def upsert_file(file_entries, replacement):
    for index, entry in enumerate(file_entries):
        if entry.get("name") == replacement["name"]:
            file_entries[index] = replacement
            return
    file_entries.append(replacement)


def encode_sseq_variable_length(value):
    if not isinstance(value, int) or value < 0 or value > 0x0FFFFFFF:
        raise RuntimeError(f"Invalid SSEQ variable-length value {value!r}")
    encoded = [value & 0x7F]
    value >>= 7
    while value:
        encoded.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(encoded))


def encode_sseq_event(event):
    command = event[0]
    if command in SSEQ_COMMANDS:
        opcode, argument_type = SSEQ_COMMANDS[command]
        if argument_type is None:
            if len(event) != 1:
                raise RuntimeError(f"{command} does not accept arguments")
            return bytes((opcode,))
        if len(event) != 2:
            raise RuntimeError(f"{command} requires one argument")
        value = event[1]
        if argument_type == "var":
            argument = encode_sseq_variable_length(value)
        elif argument_type == "byte":
            if not isinstance(value, int) or value < 0 or value > 0xFF:
                raise RuntimeError(f"Invalid byte argument for {command}: {value!r}")
            argument = bytes((value,))
        elif argument_type == "short":
            if not isinstance(value, int) or value < 0 or value > 0xFFFF:
                raise RuntimeError(f"Invalid short argument for {command}: {value!r}")
            argument = value.to_bytes(2, "little")
        else:
            raise RuntimeError(f"Unknown SSEQ argument type {argument_type!r}")
        return bytes((opcode,)) + argument

    note_name = command[:2]
    if note_name not in SSEQ_NOTE_NAMES or len(event) != 3:
        raise RuntimeError(f"Unsupported SSEQ event {event!r}")
    try:
        octave = int(command[2:])
    except ValueError as error:
        raise RuntimeError(f"Invalid SSEQ note {command!r}") from error
    note = SSEQ_NOTE_NAMES.index(note_name) + octave * 12
    velocity, duration = event[1:]
    if note < 0 or note > 0x7F or velocity < 0 or velocity > 0x7F:
        raise RuntimeError(f"Invalid SSEQ note event {event!r}")
    return bytes((note, velocity)) + encode_sseq_variable_length(duration)


def render_sseq_text(tracks):
    lines = []
    for track_index, events in enumerate(tracks, start=1):
        if track_index > 1:
            lines.append("")
        lines.append(f"Track_{track_index}:")
        for event in events:
            if event[0][:2] in SSEQ_NOTE_NAMES:
                lines.append(
                    f"\t{event[0]},{event[1]},{event[2]}"
                )
            elif len(event) == 1:
                lines.append(f"\t{event[0]}")
            else:
                lines.append(f"\t{event[0]} {event[1]}")
    return "\n".join(lines) + "\n"


def build_sseq(tracks):
    if not tracks or len(tracks) > 16:
        raise RuntimeError(f"Invalid SSEQ track count {len(tracks)}")
    encoded_tracks = [
        b"".join(encode_sseq_event(event) for event in track)
        for track in tracks
    ]
    if any(not track or track[-1] != 0xFF for track in encoded_tracks):
        raise RuntimeError("Every generated SSEQ track must end with TrackEnd")

    sequence = bytearray()
    if len(encoded_tracks) > 1:
        track_mask = (1 << len(encoded_tracks)) - 1
        sequence += b"\xFE" + track_mask.to_bytes(2, "little")
        first_track_offset = 3 + 5 * (len(encoded_tracks) - 1)
        next_track_offset = first_track_offset + len(encoded_tracks[0])
        for track_index, encoded_track in enumerate(encoded_tracks[1:], start=1):
            sequence += b"\x93" + bytes((track_index,))
            sequence += next_track_offset.to_bytes(3, "little")
            next_track_offset += len(encoded_track)
    sequence += b"".join(encoded_tracks)

    file_size = (0x1C + len(sequence) + 3) & ~3
    data_size = file_size - 0x10
    output = bytearray(b"SSEQ\xFF\xFE\x00\x01")
    output += file_size.to_bytes(4, "little")
    output += b"\x10\x00\x01\x00DATA"
    output += data_size.to_bytes(4, "little")
    output += (0x1C).to_bytes(4, "little")
    output += sequence
    output += bytes(file_size - len(output))
    return bytes(output)


def install_split_capture_sequences(info, file_block, files_dir):
    source = find_named(info["seqInfo"], "SEQ_SE_DP_BOWA4")
    sequence_dir = files_dir / "SEQ"
    sequence_dir.mkdir(parents=True, exist_ok=True)

    for definition in SPLIT_CAPTURE_SEQUENCES:
        sequence_name = definition["name"]
        file_name = f"{sequence_name}.sseq"
        sequence_bytes = build_sseq(definition["tracks"])
        reserve_slot(
            info["seqInfo"],
            definition["slot"],
            (definition["replaces"], sequence_name),
            {
                **source,
                "name": sequence_name,
                "fileName": file_name,
                "bnk": PRIVATE_BANK_NAME,
            },
        )
        (sequence_dir / f"{sequence_name}.txt").write_text(
            render_sseq_text(definition["tracks"])
        )
        (sequence_dir / file_name).write_bytes(sequence_bytes)
        upsert_file(
            file_block["file"],
            {
                "name": file_name,
                "type": "SEQ",
                "MD5": hashlib.md5(sequence_bytes).hexdigest(),
            },
        )


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
    install_split_capture_sequences(info, file_block, files_dir)
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
