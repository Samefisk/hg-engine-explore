"""Read and write nameless NARC archives byte-for-byte like the game's own.

ndspy reads these fine but writes a 20-byte BTNF block where vanilla uses 16,
so packing goes through this writer instead.
"""

from __future__ import annotations

import struct
from pathlib import Path

import ndspy.narc


def read_members(path: Path) -> list[bytes]:
    return list(ndspy.narc.NARC(path.read_bytes()).files)


def build(members: list[bytes], padding: bytes = b"\xff") -> bytes:
    fat = bytearray()
    image = bytearray()
    for member in members:
        start = len(image)
        image += member
        fat += struct.pack("<II", start, len(image))
        while len(image) % 4:
            image += padding
    btaf = b"BTAF" + struct.pack("<IHH", 12 + len(fat), len(members), 0) + fat
    btnf = b"BTNF" + struct.pack("<IIHH", 16, 4, 0, 1)
    gmif = b"GMIF" + struct.pack("<I", 8 + len(image)) + image
    body = btaf + btnf + gmif
    return b"NARC" + struct.pack("<HHIHH", 0xFFFE, 0x0100, 16 + len(body), 16, 3) + body
