#!/usr/bin/env python3
"""Pre-filter fixed-width level-up rows using the freshly built move archive."""

from __future__ import annotations

import argparse
import os
import re
import struct
import tempfile
from pathlib import Path


LEVEL_UP_LEARNSET_END = 0xFFFF
BLOCK_DEFINE = "BLOCK_LEARNING_UNIMPLEMENTED_MOVES"
MOVE_FIELD_MACROS = (
    "battleeffect",
    "pss",
    "basepower",
    "type",
    "accuracy",
    "pp",
    "effectchance",
    "target",
    "priority",
    "flags",
    "appeal",
    "contesttype",
    "terminatedata",
)


def fail(message: str) -> None:
    raise SystemExit(f"level-up learnset prefilter failed: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def read_row_width(constants: Path) -> int:
    match = re.search(
        r"^\s*#\s*define\s+MAX_LEVELUP_MOVES\s+(\d+)\s*$",
        constants.read_text(),
        re.MULTILINE,
    )
    require(match is not None, f"MAX_LEVELUP_MOVES is missing from {constants}")
    width = int(match.group(1))
    require(width > 0, "MAX_LEVELUP_MOVES must be positive")
    return width


def filter_enabled(config: Path) -> bool:
    define = re.compile(rf"^\s*#\s*define\s+{BLOCK_DEFINE}(?:\s|$)")
    return any(define.match(line) for line in config.read_text().splitlines())


def emitted_macro_width(source: str, name: str) -> int:
    match = re.search(
        rf"^\.macro\s+{name}(?:,|\s|$)(.*?)^\.endmacro\s*$",
        source,
        re.MULTILINE | re.DOTALL,
    )
    require(match is not None, f"move-data macro {name} is missing")
    body = match.group(1)
    directives = re.findall(r"^\s*\.(byte|halfword)\b", body, re.MULTILINE)
    require(directives, f"move-data macro {name} emits no fixed-width field")
    return sum(1 if directive == "byte" else 2 for directive in directives)


def read_move_layout(battle_header: Path, move_macros: Path) -> tuple[int, int, int]:
    header = battle_header.read_text()
    struct_match = re.search(
        r"struct\s+__attribute__\(\(packed\)\)\s+BattleMove\s*\{(.*?)"
        r"\};\s*//\s*size\s*=\s*(0x[0-9A-Fa-f]+)",
        header,
        re.DOTALL,
    )
    require(struct_match is not None, "packed BattleMove layout is missing")
    flag_match = re.search(
        r"/\*\s*(0x[0-9A-Fa-f]+)\s*\*/\s*u8\s+flag\s*;",
        struct_match.group(1),
    )
    mask_match = re.search(
        r"^\s*#\s*define\s+FLAG_UNUSED_MOVE\s+\((0x[0-9A-Fa-f]+)\)",
        header,
        re.MULTILINE,
    )
    require(flag_match is not None, "BattleMove flag offset is missing")
    require(mask_match is not None, "FLAG_UNUSED_MOVE is missing")
    header_offset = int(flag_match.group(1), 16)
    header_size = int(struct_match.group(2), 16)
    mask = int(mask_match.group(1), 16)
    require(mask != 0 and mask & (mask - 1) == 0, "FLAG_UNUSED_MOVE is not one bit")

    macros = move_macros.read_text()
    widths = {name: emitted_macro_width(macros, name) for name in MOVE_FIELD_MACROS}
    macro_offset = sum(widths[name] for name in MOVE_FIELD_MACROS[:9])
    macro_size = sum(widths.values())
    unusable_masks = {
        int(value, 16)
        for value in re.findall(
            r"^FLAG_UNUSABLE_(?:IN_GEN_8|IN_GEN_9|UNIMPLEMENTED)\s+equ\s+"
            r"(0x[0-9A-Fa-f]+)\s*$",
            macros,
            re.MULTILINE,
        )
    }
    require(unusable_masks == {mask}, "Armips unusable-move masks differ from C")
    require(macro_offset == header_offset, "Armips/C BattleMove flag offsets differ")
    require(macro_size == header_size, "Armips/C BattleMove record sizes differ")
    return mask, header_offset, header_size


def read_move_flags(move_data_dir: Path, flag_offset: int, record_size: int) -> list[int]:
    rows: dict[int, int] = {}
    for path in move_data_dir.iterdir():
        match = re.fullmatch(r"move_(\d{3,})", path.name)
        require(match is not None, f"unexpected move-data entry {path.name}")
        require(path.is_file(), f"move-data entry {path.name} is not a file")
        move = int(match.group(1))
        require(move not in rows, f"duplicate move-data row {move}")
        data = path.read_bytes()
        require(
            len(data) == record_size,
            f"{path.name} is {len(data)} bytes instead of {record_size}",
        )
        rows[move] = data[flag_offset]

    require(rows, f"no move-data rows found in {move_data_dir}")
    require(
        sorted(rows) == list(range(max(rows) + 1)),
        "move-data row IDs are not contiguous from zero",
    )
    return [rows[index] for index in range(max(rows) + 1)]


def filter_blob(
    blob: bytes,
    row_width: int,
    move_flags: list[int],
    unused_move_mask: int,
) -> tuple[bytes, int]:
    row_size = row_width * sizeof_u32
    require(len(blob) % row_size == 0, f"learnset size {len(blob)} is not row-aligned")

    result = bytearray(blob)
    changed_rows = 0
    for row_index in range(len(blob) // row_size):
        offset = row_index * row_size
        values = list(struct.unpack_from(f"<{row_width}I", blob, offset))
        filtered = list(values)
        write_index = 0
        terminated = False

        for entry in values:
            move = entry & 0xFFFF
            if move == LEVEL_UP_LEARNSET_END:
                filtered[write_index] = entry
                terminated = True
                break
            require(
                move < len(move_flags),
                f"learnset row {row_index} references missing move {move}",
            )
            if move_flags[move] & unused_move_mask == 0:
                filtered[write_index] = entry
                write_index += 1

        require(terminated, f"learnset row {row_index} has no terminator")
        if filtered != values:
            changed_rows += 1
        struct.pack_into(f"<{row_width}I", result, offset, *filtered)

    return bytes(result), changed_rows


sizeof_u32 = struct.calcsize("<I")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--learnsets", type=Path, required=True)
    parser.add_argument("--move-data-dir", type=Path, required=True)
    parser.add_argument("--constants", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--battle-header", type=Path, required=True)
    parser.add_argument("--move-macros", type=Path, required=True)
    args = parser.parse_args()

    row_width = read_row_width(args.constants)
    original = args.learnsets.read_bytes()
    unused_move_mask, flag_offset, record_size = read_move_layout(
        args.battle_header,
        args.move_macros,
    )
    move_flags = read_move_flags(args.move_data_dir, flag_offset, record_size)
    enabled = filter_enabled(args.config)
    if enabled:
        filtered, changed_rows = filter_blob(
            original,
            row_width,
            move_flags,
            unused_move_mask,
        )
    else:
        filtered, changed_rows = original, 0

    if filtered != original:
        temporary_fd, temporary_name = tempfile.mkstemp(
            prefix=f".{args.learnsets.name}.",
            suffix=".tmp",
            dir=args.learnsets.parent.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(temporary_fd, "wb") as stream:
                stream.write(filtered)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, args.learnsets)
        finally:
            temporary.unlink(missing_ok=True)

    print(
        f"level-up learnset prefilter: {len(original) // (row_width * sizeof_u32)} rows; "
        f"{changed_rows} compacted; "
        f"{len(move_flags)} move records; "
        f"enabled={enabled}; mask=0x{unused_move_mask:02X}; "
        f"flags=0x{flag_offset:X}; record=0x{record_size:X}"
    )


if __name__ == "__main__":
    main()
