#!/usr/bin/env python3
"""Check the packaged title save hooks and resident reset callback."""

import argparse
import struct
import subprocess
from pathlib import Path


ARM9_BASE = 0x02000000
HEALTH_BASE = 0x01FFA580
HEALTH_LIMIT = 0x02000000
HEALTH_MAGIC = 0x484C5048


def word(data, address):
    return struct.unpack_from("<I", data, address - ARM9_BASE)[0]


def halfword(data, address):
    return struct.unpack_from("<H", data, address - ARM9_BASE)[0]


def check_hook(data, entry, wrapper, old_target_literal):
    assert halfword(data, entry) == 0x4901, f"{entry:#x}: wrong literal load"
    assert halfword(data, entry + 2) == 0x4708, f"{entry:#x}: wrong tail branch"
    target = word(data, old_target_literal)
    assert target & 1, f"{entry:#x}: original Thumb target was lost"
    assert 0x023D8000 <= (target & ~1) < 0x023E0000, (
        f"{entry:#x}: original root target is outside overlay 129"
    )
    assert word(data, entry + 8) == wrapper | 1, (
        f"{entry:#x}: wrapper pointer is wrong"
    )
    assert halfword(data, wrapper) == 0xB510, (
        f"{wrapper:#x}: wrapper does not preserve r4/lr"
    )
    first_call = wrapper + 6
    second_call = wrapper + (12 if entry == 0x020274A8 else 18)
    slot_load = wrapper + (10 if entry == 0x020274A8 else 16)
    assert halfword(data, first_call) == 0x4798, "original save call is missing"
    assert halfword(data, second_call) == 0x4798, "reset callback call is missing"
    assert halfword(data, slot_load) == 0x6A5B, "wrong resident API slot"
    assert word(data, wrapper + (0x14 if entry == 0x020274A8 else 0x1C)) == HEALTH_BASE, (
        f"{wrapper:#x}: resident API base is wrong"
    )


def verify_session_reset(arm9, health, health_linked):
    assert len(health) <= HEALTH_LIMIT - HEALTH_BASE, "resident overlay is too large"
    assert word(arm9, 0x020D2C68) == HEALTH_LIMIT, "ITCM arena overlaps resident health code"
    assert struct.unpack_from("<I", health, 0)[0] == HEALTH_MAGIC
    version, size = struct.unpack_from("<HH", health, 4)
    assert (version, size) == (2, 0x34), "resident API layout changed"
    callback = struct.unpack_from("<I", health, 0x24)[0]
    assert callback & 1 and HEALTH_BASE <= (callback & ~1) < HEALTH_BASE + len(health), (
        "session reset callback is absent or outside resident overlay"
    )
    symbols = subprocess.check_output(
        ["arm-none-eabi-nm", str(health_linked)], text=True
    )
    reset_symbol = next(
        int(parts[0], 16)
        for line in symbols.splitlines()
        if (parts := line.split()) and parts[-1] == "PlayerHealthField_SessionReset"
    )
    assert callback == (reset_symbol | 1), "session reset slot targets another function"

    check_hook(arm9, 0x020274A8, 0x020274B4, 0x020274AC)
    check_hook(arm9, 0x02027AD4, 0x02027AE0, 0x02027AD8)
    assert halfword(arm9, 0x02027AEA) == 0xD004, (
        "failed Continue must skip the reset callback"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm9", type=Path, required=True)
    parser.add_argument("--health-overlay", type=Path, required=True)
    parser.add_argument("--health-linked", type=Path, required=True)
    args = parser.parse_args()
    verify_session_reset(args.arm9.read_bytes(),
                         args.health_overlay.read_bytes(), args.health_linked)
    print("player HP session reset hooks: packaged entries and callback pass")


if __name__ == "__main__":
    main()
