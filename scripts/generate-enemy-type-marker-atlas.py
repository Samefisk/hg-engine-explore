#!/usr/bin/env python3

import argparse
import struct
import zlib
from pathlib import Path


LABELS = (
    "NOR", "FGT", "FLY", "PSN", "GND", "RCK", "BUG", "GHO", "STL",
    "FAI", "FIR", "WAT", "GRS", "ELC", "PSY", "ICE", "DRA", "DRK",
    "NUL", "STR",
)

PALETTE = (
    (0, 0, 0),
    (32, 40, 48),
    (248, 248, 248),
    (152, 152, 144),
    (184, 56, 48),
    (88, 144, 216),
    (144, 72, 176),
    (176, 128, 56),
    (128, 152, 48),
    (104, 88, 176),
    (112, 144, 160),
    (224, 112, 160),
    (232, 112, 40),
    (56, 152, 88),
    (232, 192, 40),
    (72, 184, 200),
)

TYPE_COLORS = (3, 4, 5, 6, 7, 7, 8, 9, 10, 11, 12, 5, 13, 14, 11, 15, 9, 1, 3, 15)

FONT = {
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "P": ("110", "101", "110", "100", "100"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "W": ("101", "101", "111", "111", "101"),
    "Y": ("101", "101", "010", "010", "010"),
}


def png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def build_png():
    width = 32
    height = len(LABELS) * 8
    pixels = [[0] * width for _ in range(height)]

    for type_id, label in enumerate(LABELS):
        top = type_id * 8
        color = TYPE_COLORS[type_id]
        for y in range(1, 7):
            for x in range(1, 31):
                pixels[top + y][x] = color
        for x in range(3, 6):
            for y in range(2, 6):
                pixels[top + y][x] = 2

        text_x = 10
        for letter in label:
            glyph = FONT[letter]
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == "1":
                        pixels[top + 1 + gy][text_x + gx] = 2
            text_x += 4

    packed_rows = []
    for row in pixels:
        packed = bytes((row[x] << 4) | row[x + 1] for x in range(0, width, 2))
        packed_rows.append(b"\x00" + packed)
    raw = b"".join(packed_rows)
    palette = b"".join(bytes(rgb) for rgb in PALETTE)

    data = b"\x89PNG\r\n\x1a\n"
    data += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 4, 3, 0, 0, 0))
    data += png_chunk(b"PLTE", palette)
    data += png_chunk(b"IDAT", zlib.compress(raw, 9))
    data += png_chunk(b"IEND", b"")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "rawdata/weather_icons/8_369_enemy_type_marker_hud.png"
    data = build_png()
    if args.check:
        if not output.is_file() or output.read_bytes() != data:
            raise SystemExit(f"stale generated asset: {output}")
    else:
        output.write_bytes(data)
