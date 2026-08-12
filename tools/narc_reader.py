#!/usr/bin/env python3
"""Small, dependency-free reader for Nitro NARC member data."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NarcArchive:
    files: tuple[bytes, ...]

    @classmethod
    def from_file(cls, path: Path | str) -> "NarcArchive":
        data = Path(path).read_bytes()
        if len(data) < 0x10 or data[:4] != b"NARC":
            raise RuntimeError(f"{path}: not a NARC archive")
        file_size, header_size, block_count = struct.unpack_from("<IHH", data, 8)
        if file_size != len(data) or header_size < 0x10 or block_count != 3:
            raise RuntimeError(f"{path}: invalid NARC header")

        fat_offset = header_size
        if fat_offset + 12 > len(data) or data[fat_offset : fat_offset + 4] != b"BTAF":
            raise RuntimeError(f"{path}: missing NARC file-allocation block")
        fat_size = struct.unpack_from("<I", data, fat_offset + 4)[0]
        member_count = struct.unpack_from("<H", data, fat_offset + 8)[0]
        if fat_size != 12 + member_count * 8 or fat_offset + fat_size > len(data):
            raise RuntimeError(f"{path}: invalid NARC file-allocation block")

        name_offset = fat_offset + fat_size
        if name_offset + 8 > len(data) or data[name_offset : name_offset + 4] != b"BTNF":
            raise RuntimeError(f"{path}: missing NARC filename block")
        name_size = struct.unpack_from("<I", data, name_offset + 4)[0]
        image_offset = name_offset + name_size
        if image_offset + 8 > len(data) or data[image_offset : image_offset + 4] != b"GMIF":
            raise RuntimeError(f"{path}: missing NARC file-image block")
        image_size = struct.unpack_from("<I", data, image_offset + 4)[0]
        image_data_offset = image_offset + 8
        image_data_size = image_size - 8
        if image_size < 8 or image_offset + image_size > len(data):
            raise RuntimeError(f"{path}: invalid NARC file-image block")

        files: list[bytes] = []
        for index in range(member_count):
            start, end = struct.unpack_from("<II", data, fat_offset + 12 + index * 8)
            if start > end or end > image_data_size:
                raise RuntimeError(f"{path}: NARC member {index} is outside the file image")
            files.append(data[image_data_offset + start : image_data_offset + end])
        return cls(tuple(files))
