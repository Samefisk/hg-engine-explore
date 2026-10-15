#!/usr/bin/env python3
"""Check the compiled Mom menu and completed-Rest healing handoff."""

import argparse
import struct
from pathlib import Path


def verify(script: bytes) -> None:
    def take(offset: int, fmt: str, expected: tuple[int, ...]) -> int:
        size = struct.calcsize(fmt)
        actual = struct.unpack_from(fmt, script, offset)
        if actual != expected:
            raise ValueError(f"script {offset:#x}: expected {expected}, got {actual}")
        return offset + size

    def branch(offset: int, opcode: int, condition: int | None = None) -> tuple[int, int]:
        if condition is None:
            offset = take(offset, "<H", (opcode,))
        else:
            offset = take(offset, "<HB", (opcode, condition))
        delta = struct.unpack_from("<i", script, offset)[0]
        return offset + 4, offset + 4 + delta

    # The stock menu setup is redirected; its four stock actions must stay intact.
    _, menu = branch(0x275, 22)
    if menu < 0x490:
        raise ValueError(f"Mom menu did not reach appended script: {menu:#x}")
    pos = take(menu, "<HB", (45, 20))  # Mom's menu prompt
    pos = take(pos, "<HHH", (795, 1, 1))
    pos = take(pos, "<H", (746,))
    pos = take(pos, "<HBBBBH", (750, 1, 1, 0, 1, 0x800C))
    for text_id, result in ((29, 0), (30, 1), (39, 4), (31, 2), (32, 3)):
        pos = take(pos, "<HHHH", (751, text_id, 255, result))
    pos = take(pos, "<H", (752,))
    pos = take(pos, "<HHH", (42, 0x8008, 0x800C))

    for result, target in enumerate((0x2DF, 0x335, 0x398, 0x3D1)):
        pos = take(pos, "<HHH", (17, 0x8008, result))
        pos, actual_target = branch(pos, 28, 1)
        if actual_target != target:
            raise ValueError(f"menu result {result} branches to {actual_target:#x}")
    pos = take(pos, "<HHH", (17, 0x8008, 4))
    pos, rest = branch(pos, 28, 1)
    pos, default = branch(pos, 22)
    if rest != pos or default != 0x3D1:
        raise ValueError("Rest or menu-cancel branch is not connected")

    # Standard 2069 heals the party and resumes this script. Only then may the
    # field service consume marker 2 and restore trainer HP/checkpoint.
    pos = take(pos, "<HHHHH", (796, 747, 53, 20, 2069))
    pos = take(pos, "<HHH", (41, 0x401F, 2))
    pos = take(pos, "<HBHHHH", (45, 40, 49, 53, 97, 2))
    if pos != len(script):
        raise ValueError(f"unexpected bytes after completed Rest: {len(script) - pos}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", nargs="?", type=Path, default=Path("build/a012/2_845"))
    args = parser.parse_args()
    verify(args.script.read_bytes())
    print(f"PASS: {args.script} Rest follows standard heal; marker 2 follows Rest")


if __name__ == "__main__":
    main()
